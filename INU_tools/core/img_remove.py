"""
Remove from IMG — what to delete from each archive, and deleting it.

A model goes from its OWN archive: its .dff, its TXD only when nothing else
needs it (other models of the game IDEs / the scene, a txdp child, a model
of the same name still in the archive), its collision records out of every
.col of the archive (a library left empty is deleted). A LOD goes only when
it is removed itself — one LOD often serves several models.

No Blender dependency — pure Python.
"""

import os

from .col_library import col_splice
from .ide import read_ide
from .img import ImgReader, ImgWriter, remove_file


def txd_users(ide_paths):
    """Who uses each TXD according to IDE files: ``({TXD lower: {model
    lower}}, [unreadable paths])``. Every section with a TXD column counts
    (objs/tobj, anim, cars, peds, weap, hier); a txdp child loads its
    parent, so the parent is used by «txdp <child>». Paths are
    de-duplicated case-insensitively, missing files skipped."""
    users, bad, seen = {}, [], set()
    for p in ide_paths:
        if not p:
            continue
        key = os.path.normcase(os.path.normpath(p))
        if key in seen or not os.path.isfile(p):
            continue
        seen.add(key)
        try:
            ide = read_ide(p)
        except Exception:
            bad.append(p)
            continue
        for sec in (ide.objects, ide.anims, ide.cars, ide.peds, ide.weaps,
                    ide.hiers):
            for e in sec:
                txd = (e.txd_name or '').strip().lower()
                model = (e.model_name or '').strip().lower()
                if txd and model:
                    users.setdefault(txd, set()).add(model)
        for e in ide.txdps:
            child = (e.txd_name or '').strip().lower()
            parent = (e.parent_txd_name or '').strip().lower()
            if child and parent:
                users.setdefault(parent, set()).add('txdp ' + child)
    return users, bad


def scene_txd_users(dffs, lods):
    """Who uses each TXD among the scene's models, by the rule Export to IMG
    writes them: a model — its txd_name, else its own name; a LOD — its
    txd_name, else the TXD of its model.

    *dffs* — [(model name, txd_name)]; *lods* — [(LOD model name, txd_name,
    model name of its DFF or '')]. Returns {TXD lower: {model lower}}."""
    users, dff_txd = {}, {}
    for name, txd in dffs:
        txd = (txd or '').strip() or name
        dff_txd.setdefault(name.lower(), txd)
        users.setdefault(txd.lower(), set()).add(name.lower())
    for name, txd, owner in lods:
        txd = (txd or '').strip() or dff_txd.get((owner or '').lower(), '')
        if txd:
            users.setdefault(txd.lower(), set()).add(name.lower())
    return users


def remove_plan(parts, names_by_arch, col_idx_by_arch, users):
    """What to delete from each archive.

    *parts* — one dict per model to remove: ``kind`` 'dff' / 'lod' / 'col'
    (a COL mesh selected on its own), ``arch`` (its archive), ``name`` (model
    name), ``txd`` (its TXD, dff/lod) and, for a DFF whose LOD stays, ``lod``
    (the LOD's model name — reported, never removed).
    *names_by_arch* — {arch: {entry name lower: entry name}}; a part whose
    archive is missing there is skipped. *col_idx_by_arch* — {arch: {model
    lower: [.col entry names]}}. *users* — {TXD lower: {model lower}}.

    A DFF / LOD whose .dff is not in its archive is not removed at all — its
    TXD and collision may serve the model where it really is; it is listed
    in ``missing`` instead.

    Returns {arch: {'entries': [entry names], 'libs': {.col entry: [model
    names]}, 'kept_txd': [(TXD entry, example user, number of users)],
    'kept_lod': [LOD model names], 'missing': [model names]}}."""
    def present(p):
        names = names_by_arch.get(p['arch'])
        return names is not None and p['name'].lower() + '.dff' in names

    removing = {p['name'].lower() for p in parts
                if p['kind'] in ('dff', 'lod') and present(p)}
    # A DFF not in its archive keeps its collision there even when its COL
    # mesh is selected too.
    missing = {(p['arch'], p['name'].lower()) for p in parts
               if p['kind'] == 'dff' and not present(p)}
    plan, decided = {}, set()
    for p in parts:
        arch = p['arch']
        names = names_by_arch.get(arch)
        if names is None:
            continue
        t = plan.setdefault(arch, {'entries': [], 'libs': {}, 'kept_txd': [],
                                   'kept_lod': [], 'missing': []})
        kind, name = p['kind'], p['name']
        if kind in ('dff', 'lod'):
            fn = names.get(name.lower() + '.dff')
            if not fn:
                if name not in t['missing']:
                    t['missing'].append(name)
                continue
            if fn not in t['entries']:
                t['entries'].append(fn)
            txd = (p.get('txd') or '').strip()
            fn = names.get(txd.lower() + '.txd') if txd else None
            if fn and (arch, fn.lower()) not in decided:
                decided.add((arch, fn.lower()))
                others = set(users.get(txd.lower(), ())) - removing
                # «model and its TXD share a name» — a model of that name
                # staying in the archive keeps the TXD.
                if txd.lower() + '.dff' in names and txd.lower() not in removing:
                    others.add(txd.lower())
                if others:
                    t['kept_txd'].append((fn, sorted(others)[0], len(others)))
                else:
                    t['entries'].append(fn)
        if kind in ('dff', 'col') and (arch, name.lower()) not in missing:
            for lib in col_idx_by_arch.get(arch, {}).get(name.lower(), ()):
                models = t['libs'].setdefault(lib, [])
                if name.lower() not in {m.lower() for m in models}:
                    models.append(name)
        lod = (p.get('lod') or '').strip() if kind == 'dff' else ''
        if (lod and lod.lower() + '.dff' in names and lod.lower() not in removing
                and lod not in t['kept_lod']):
            t['kept_lod'].append(lod)
    return plan


def remove_entries(arch, entries, libs, done):
    """Delete *entries* from IMG *arch* and cut the records of the models in
    *libs* ({.col entry: [model names]}) out of those libraries; a library
    left with no records is deleted. Appends to *done* as it goes — entry
    names, then ``(library, models)`` pairs — so when it fails half-way
    (PermissionError: the game holds the archive) the caller still knows
    what is already gone."""
    for fn in entries:
        if remove_file(arch, fn):
            done.append(fn)
    if not libs:
        return
    with ImgReader(arch) as rd:
        datas = {lib: rd.read(lib) or b'' for lib in libs}
    cut, emptied = {}, []
    for lib, models in libs.items():
        data, hit, left = datas[lib], 0, 0
        for m in models:
            data, n, left = col_splice(data, m, lambda _mid: None)
            hit += n
        if hit and left:
            cut[lib] = (data, models)
        elif hit:
            emptied.append((lib, models))
    if cut:
        with ImgWriter(arch) as w:
            for lib, (data, _models) in cut.items():
                w.add(lib, data)
        done.extend((lib, models) for lib, (_data, models) in cut.items())
    # After the writer has written its directory — a remove_file inside
    # the block would be undone by it.
    for lib, models in emptied:
        if remove_file(arch, lib):
            done.append((lib, models))
