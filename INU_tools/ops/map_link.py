# INU_tools.ops.map_link — Blender side of the IDE / IPL sync (core/mapsync).
#
# Every operator that writes, removes, pulls or checks IDE/IPL rows goes
# through here, so there is exactly ONE set of rules:
#
#   * An object remembers what it last wrote (anchor props on obj.inu):
#       IPL: ipl_target_file, ipl_last_model_id / _name / _pos / _rot, and
#            ipl_owner = the object's name at that moment (tells a Shift+D
#            copy from the original — both carry the same ipl_uuid).
#       IDE: ide_target_file, ide_linked, ide_last_model_id / _name / …
#     No line numbers anywhere; the old .inu_cache sidecar is gone.
#   * A model's LOD always travels with it: the LOD partner is inu.lod_object,
#     or the scene's LOD mesh with the same base name. Each placement gets ITS
#     OWN LOD row at its own position.
#   * Rows owned by other scene objects are reserved, so a batch can never
#     overwrite a neighbour's row.

import os
import bpy

from .. import T


# ── small helpers ───────────────────────────────────────────────────────

def norm(path):
    return os.path.normcase(os.path.abspath(bpy.path.abspath(path or '')))


def scene_game(context):
    try:
        from ..core import game_versions as gv
        return gv.game_of_scene(context.scene)
    except Exception:
        return 'SA'


def _sid(o):
    return getattr(o, 'session_uid', None) or getattr(o, 'session_uuid', 0) or 0


def _mesh_objects():
    return [o for o in bpy.data.objects if o.type == 'MESH' and hasattr(o, 'inu')]


def model_type(obj):
    from ..tools.model_utils import get_model_type
    return get_model_type(obj)


def plain_name(obj):
    """Object name without Blender's .001 suffix."""
    from ..tools.model_utils import _strip_dup_suffix
    return _strip_dup_suffix(obj.name)


class Report:
    """Counts + messages of one sync run, shared by IDE and IPL ops."""

    def __init__(self):
        self.counts = {}
        self.messages = []          # (level, text)
        self.files = set()

    def add(self, key, n=1):
        self.counts[key] = self.counts.get(key, 0) + n

    def msg(self, level, text):
        self.messages.append((level, text))

    def problems(self):
        return [m for m in self.messages if m[0] in ('WARNING', 'ERROR')]

    def merge(self, other):
        for k, v in other.counts.items():
            self.add(k, v)
        self.messages += other.messages
        self.files |= other.files


# ── LOD partners ────────────────────────────────────────────────────────

class LodIndex:
    """base name (lower) → LOD meshes in the scene, built once per run."""

    def __init__(self):
        self.by_base = {}
        # Only THIS scene: a LOD mesh in another scene of the .blend is not
        # part of this map (and may carry that scene's stale stamps).
        for o in bpy.context.scene.objects:
            if o.type != 'MESH' or not hasattr(o, 'inu'):
                continue
            if 'lod' not in o.name.lower() and getattr(o.inu, 'type', '') != 'LOD':
                continue
            mt, base = model_type(o)
            if mt == 'LOD' and base:
                self.by_base.setdefault(base.lower(), []).append(o)

    def partner(self, dff):
        lodo = getattr(dff.inu, 'lod_object', None)
        if lodo is not None and lodo.type == 'MESH' and lodo.name in bpy.data.objects:
            return lodo
        _mt, base = model_type(dff)
        cands = self.by_base.get((base or '').lower(), [])
        if not cands:
            return None
        # Prefer the undecorated one (LODhouse over LODhouse.001).
        return min(cands, key=lambda o: (o.name != plain_name(o), o.name))

    def owners(self, lodo, dffs):
        """DFFs among *dffs* whose partner is *lodo*."""
        return [d for d in dffs if self.partner(d) is lodo]


class IdeLods:
    """LOD definitions read from IDE files — for a model whose LOD mesh is not
    in this scene (made in another .blend, only the DFF brought over).

    Where to look, in order: the IDE the model is linked to, the IDE picked in
    the panel, the «IDE для экспорта» list. A LOD row is ``LOD<base>`` or any
    LOD-named row whose base is the model's (``lodcuntw05`` → ``cuntw05``);
    with several, the one with id = model id + 1 wins."""

    def __init__(self, context):
        s = context.scene.inu_settings
        self.common = []
        for p in ([getattr(s, 'gtatools_ide_path', '')]
                  + [it.path for it in getattr(s, 'gtatools_ide_sync_list', [])]):
            p = norm(p) if p else ''
            if p and p not in self.common and os.path.isfile(p):
                self.common.append(p)
        self._by_file = {}            # path → {base lower: [(id, name)]}

    def _index(self, path):
        if path not in self._by_file:
            from ..core.mapsync import IdeDoc
            from ..core.ipl import is_lod_name, strip_lod_marker
            idx = {}
            try:
                doc = IdeDoc.load(path)
            except OSError:
                doc = None
            for r in (doc.rows if doc else ()):
                if r.section not in ('objs', 'tobj') or not is_lod_name(r.name):
                    continue
                low = r.name.lower()
                bases = {strip_lod_marker(r.name).lower()}
                if low.startswith('lod'):
                    bases.add(low[3:].lstrip('_-'))
                for b in bases:
                    idx.setdefault(b, []).append((r.model_id, r.name))
            self._by_file[path] = idx
        return self._by_file[path]

    def find(self, dff, base):
        """(model_id, model_name, ide_path) of the LOD of *dff*, or None."""
        files = []
        own = ide_linked_file(dff)
        if own and os.path.isfile(own):
            files.append(own)
        files += [p for p in self.common if p not in files]
        did = int(getattr(dff.inu, 'model_id', 0) or 0)
        for path in files:
            cands = self._index(path).get((base or '').lower())
            if cands:
                best = min(cands, key=lambda c: (c[0] != did + 1, c[0]))
                return best[0], best[1], path
        return None


def _lod_is_model(lod, dinst):
    """A «LOD» carrying the model's own id or name is the model — never
    write it as the LOD row (that produced a second copy of the model)."""
    return (int(lod.model_id) == int(dinst.model_id)
            or lod.model_name.lower() == dinst.model_name.lower())


def stamp_lod_ide(dff, hit):
    """Remember on the model that its LOD comes from the IDE (panel shows it)."""
    inu = dff.inu
    inu.lod_ide_id = int(hit[0])
    inu.lod_ide_name = hit[1]
    inu.lod_ide_file = hit[2]


def lod_model_name(lodo, base):
    """Model name of a LOD: the name it was imported/written with, else
    the addon's «LOD<base>» convention."""
    from ..core.ipl import is_lod_name
    nm = (getattr(lodo.inu, 'ide_last_name', '') or '').strip()
    return nm if (nm and is_lod_name(nm)) else ("LOD" + base)


def lod_model_id(lodo, dff):
    mid = int(getattr(lodo.inu, 'model_id', 0) or 0)
    if mid > 0:
        return mid
    did = int(getattr(dff.inu, 'model_id', 0) or 0) if dff else 0
    return did + 1 if did > 0 else 0


# ── IPL anchors ─────────────────────────────────────────────────────────

def ipl_linked_file(obj):
    inu = obj.inu
    if not inu.ipl_uuid or not inu.ipl_target_file:
        return ''
    return norm(inu.ipl_target_file)


def ipl_anchor(obj):
    from ..core.mapsync import Anchor
    inu = obj.inu
    if not inu.ipl_uuid:
        return None
    mid = int(inu.ipl_last_model_id or 0) or int(inu.model_id or 0)
    rot = tuple(inu.ipl_last_rot)
    if not any(rot):
        rot = None
    return Anchor(mid, inu.ipl_last_name or '', tuple(inu.ipl_last_pos), rot)


def stamp_ipl(obj, path, inst, lod_index=None, *, fresh=False):
    """Link *obj* to the row *inst* of *path*. *fresh* mints a new identity
    (imports: a linked duplicate would otherwise inherit its source's)."""
    import uuid
    inu = obj.inu
    if fresh or not inu.ipl_uuid:
        inu.ipl_uuid = uuid.uuid4().hex
    inu.ipl_target_file = path
    inu.ipl_last_model_id = int(inst.model_id)
    inu.ipl_last_name = inst.model_name
    inu.ipl_last_pos = (inst.pos_x, inst.pos_y, inst.pos_z)
    inu.ipl_last_rot = (inst.rot_x, inst.rot_y, inst.rot_z, inst.rot_w)
    inu.ipl_owner = obj.name
    if lod_index is not None:
        inu.lod_index = int(lod_index)


def clear_ipl(obj):
    inu = obj.inu
    inu.ipl_uuid = ''
    inu.ipl_target_file = ''
    inu.ipl_last_model_id = 0
    inu.ipl_last_name = ''
    inu.ipl_last_pos = (0.0, 0.0, 0.0)
    inu.ipl_last_rot = (0.0, 0.0, 0.0, 1.0)
    inu.ipl_owner = ''
    inu.lod_index = -1


_holders = None     # ipl_uuid → [objects]; rebuilt per run (reset_copies)


def reset_copies():
    global _holders
    _holders = None


def is_copy(obj, *, cached=True):
    """True when *obj* carries another object's IPL link (Shift+D / Ctrl+D).

    The owner is the holder whose name was stamped at write time; for links
    made before that stamp existed, the oldest object (lowest session uid).
    Panels pass cached=False (the per-run cache would go stale between
    redraws)."""
    global _holders
    u = obj.inu.ipl_uuid
    if not u:
        return False
    if not cached:
        holders = [o for o in bpy.data.objects
                   if getattr(getattr(o, 'inu', None), 'ipl_uuid', '') == u]
    else:
        if _holders is None:
            _holders = {}
            for o in _mesh_objects():
                if o.inu.ipl_uuid:
                    _holders.setdefault(o.inu.ipl_uuid, []).append(o)
        holders = [o for o in _holders.get(u, ()) if o.inu.ipl_uuid == u]
    if len(holders) <= 1:
        return False
    stamped = [o for o in holders if o.inu.ipl_owner and o.name == o.inu.ipl_owner]
    owner = stamped[0] if stamped else min(holders, key=_sid)
    return obj is not owner


def split_copies(objs):
    """Detach copies in *objs* from the original's row → they become new
    placements. Returns how many were detached."""
    reset_copies()
    copies = [o for o in objs if is_copy(o)]
    for o in copies:
        clear_ipl(o)
    reset_copies()
    return len(copies)


def ipl_inst_of(obj):
    from .. import _ipl_entry_from_obj
    return _ipl_entry_from_obj(obj)


def lod_inst_for(dff, lodo, base):
    """LOD row for *dff*: the LOD model, at the DFF's transform."""
    from .. import _ipl_entry_from_obj
    e = _ipl_entry_from_obj(lodo)
    d = _ipl_entry_from_obj(dff)
    e.model_name = lod_model_name(lodo, base)
    e.model_id = lod_model_id(lodo, dff)
    e.pos_x, e.pos_y, e.pos_z = d.pos_x, d.pos_y, d.pos_z
    e.rot_x, e.rot_y, e.rot_z, e.rot_w = d.rot_x, d.rot_y, d.rot_z, d.rot_w
    e.interior = d.interior
    e.real_interior = d.real_interior
    e.lod_index = -1
    return e


def _reserve_others(ed, path, batch):
    """Reserve rows of every linked scene object not in *batch*."""
    ids = {id(o) for o in batch}
    for o in _mesh_objects():
        if id(o) in ids or ipl_linked_file(o) != path or is_copy(o):
            continue
        a = ipl_anchor(o)
        if a is not None:
            ed.reserve(a)


def _load_ipl(path, rep):
    from ..core.mapsync import IplDoc, IplBinaryError
    try:
        return IplDoc.load(path)
    except IplBinaryError:
        rep.msg('ERROR', T("{0}: бинарный IPL (из IMG) — редактировать "
                           "нельзя").format(os.path.basename(path)))
    except OSError as e:
        rep.msg('ERROR', f"{os.path.basename(path)}: {e}")
    return None


def _commit(ed, path, rep, dry_run, context):
    new = ed.commit()
    for m in ed.messages:
        rep.msg(m.level, T(m.fmt).format(*m.args))
    if dry_run:
        return True
    if ed.doc.exists and new.to_text() == ed.doc.tl.to_text():
        return True                      # nothing changed — leave the file be
    try:
        new.write(path)
    except OSError as e:
        rep.msg('ERROR', f"{os.path.basename(path)}: {e}")
        return False
    rep.files.add(path)
    return True


# ── IPL: write ─────────────────────────────────────────────────────────

def ipl_expand(objs, rep):
    """Selection → (DFF placements, LOD-only selections).

    COL never goes into ``inst``. A LOD selected without its model updates the
    LOD rows of the already-linked models that use it."""
    dffs, lods = [], []
    seen = set()
    for o in objs:
        if o.type != 'MESH' or id(o) in seen:
            continue
        seen.add(id(o))
        mt, _b = model_type(o)
        if mt == 'COL':
            continue
        (lods if mt == 'LOD' else dffs).append(o)
    return dffs, lods


def ipl_write(context, objs, *, picked='', dry_run=False):
    """Add / update the placements of *objs* (+ their LODs).

    *picked* — the IPL chosen in the panel: when set, every object goes there
    (the picked file wins); otherwise each linked object goes to its own IPL."""
    reset_copies()
    rep = Report()
    game = scene_game(context)
    picked = norm(picked) if picked else ''
    lodix = LodIndex()
    dffs, lods = ipl_expand(objs, rep)

    # A LOD selected alone → update its linked models' rows (in THEIR files).
    via_lod = set()
    if lods:
        dff_ids = {id(d) for d in dffs}
        linked = [o for o in _mesh_objects() if o.inu.ipl_uuid
                  and model_type(o)[0] == 'DFF']
        for lodo in lods:
            if any(lodix.partner(d) is lodo for d in dffs):
                continue
            owners = lodix.owners(lodo, linked)
            if not owners:
                rep.msg('WARNING', T("«{0}»: LOD без основной модели — выдели "
                                     "основную модель").format(lodo.name))
            for d in owners:
                if id(d) not in dff_ids:
                    dffs.append(d)
                    dff_ids.add(id(d))
                    via_lod.add(id(d))

    if not dry_run:
        n = split_copies(dffs)
        if n:
            rep.msg('INFO', T("{0} копий — добавлены новыми расстановками").format(n))

    groups = {}
    for d in dffs:
        own = ipl_linked_file(d)
        if dry_run and is_copy(d):
            own = ''
        path = own if id(d) in via_lod else (picked or own)
        if not path:
            rep.msg('ERROR', T("«{0}»: нет своего IPL — выбери файл в панели IPL").format(d.name))
            continue
        if (own and picked and own != picked and id(d) not in via_lod
                and os.path.isfile(own)):
            rep.msg('WARNING', T("«{0}» была в {1} — записана в выбранный "
                                 "{2}, в старом файле строка осталась").format(
                d.name, os.path.basename(own), os.path.basename(picked)))
        groups.setdefault(path, []).append(d)

    ide_lods = IdeLods(context)
    for path, batch in groups.items():
        doc = _load_ipl(path, rep)
        if doc is None:
            continue
        fla = any(int(getattr(o.inu, 'real_interior', 0) or 0) for o in batch)
        ed = doc.editor(game=game, fla=fla or None)
        _reserve_others(ed, path, batch)
        placed = []
        for d in batch:
            if int(getattr(d.inu, 'model_id', 0) or 0) <= 0:
                rep.msg('ERROR', T("«{0}»: Model ID = 0 — не записана").format(d.name))
                continue
            copy_now = dry_run and is_copy(d)
            anchor = (ipl_anchor(d) if (ipl_linked_file(d) == path and not copy_now)
                      else None)
            _mt, base = model_type(d)
            lodo = lodix.partner(d)
            lod = None
            dinst = ipl_inst_of(d)
            if lodo is not None:
                lod = lod_inst_for(d, lodo, base)
                if lod.model_id <= 0:
                    rep.msg('WARNING', T("«{0}»: у LOD нет Model ID — LOD не "
                                         "записан").format(lodo.name))
                    lod = None
                elif _lod_is_model(lod, dinst):
                    rep.msg('WARNING', T("«{0}»: у LOD «{1}» ID/имя самой модели "
                                         "— взят LOD из IDE").format(
                                             d.name, lodo.name))
                    lod, lodo = None, None
            if lod is None:
                # No LOD mesh in this scene → its definition in the IDE.
                hit = ide_lods.find(d, base)
                if hit is not None:
                    lod = ipl_inst_of(d)
                    lod.model_id, lod.model_name = hit[0], hit[1]
                    lod.lod_index = -1
                    if _lod_is_model(lod, dinst):
                        lod = None
                    else:
                        rep.msg('INFO', T("«{0}»: LOD взят из IDE — {1} (ID {2}, "
                                          "{3})").format(d.name, hit[1], hit[0],
                                                         os.path.basename(hit[2])))
                        if not dry_run:
                            stamp_lod_ide(d, hit)
            res = ed.place(d, dinst, anchor=anchor, lod=lod)
            placed.append(res)
        if not _commit(ed, path, rep, dry_run, context):
            continue
        for res in placed:
            rep.add(res.action)
            if res.lod_action in ('add', 'update'):
                rep.add('lod_' + res.lod_action)
            if not dry_run:
                stamp_ipl(res.tag, path, res.inst, res.lod_index)
    return rep


# ── IPL: remove ────────────────────────────────────────────────────────

def ipl_remove(context, objs, *, picked='', target='', dry_run=False):
    """Remove the placements of *objs* (their LOD rows go too when unused).

    File per object: *target* if given, else the object's own IPL, else
    *picked*. A LOD selected alone is detached from its linked models."""
    reset_copies()
    from ..core.mapsync import Anchor, MATCH_TOL
    rep = Report()
    game = scene_game(context)
    lodix = LodIndex()
    dffs, lods = ipl_expand(objs, rep)
    target = norm(target) if target else ''
    picked = norm(picked) if picked else ''
    if not dry_run:
        split_copies(dffs)

    groups = {}        # path → [(obj, anchor, tol, kind)]
    for d in dffs:
        own = '' if (dry_run and is_copy(d)) else ipl_linked_file(d)
        path = target or own or picked
        if not path or not os.path.isfile(path):
            rep.msg('WARNING', T("«{0}»: нет IPL-файла").format(d.name))
            continue
        if own == path:
            groups.setdefault(path, []).append((d, ipl_anchor(d), None, 'dff'))
        else:
            # Not linked to this file: find the row at the object's position.
            e = ipl_inst_of(d)
            a = Anchor(int(d.inu.model_id or 0), e.model_name,
                       (e.pos_x, e.pos_y, e.pos_z), None)
            groups.setdefault(path, []).append((d, a, MATCH_TOL, 'dff'))
    if lods:
        linked = [o for o in _mesh_objects() if o.inu.ipl_uuid
                  and model_type(o)[0] == 'DFF' and not is_copy(o)]
        sel = {id(d) for d in dffs}
        for lodo in lods:
            for d in lodix.owners(lodo, linked):
                if id(d) in sel:
                    continue
                path = target or ipl_linked_file(d)
                if path and os.path.isfile(path):
                    groups.setdefault(path, []).append(
                        (d, ipl_anchor(d), None, 'lod'))

    for path, items in groups.items():
        doc = _load_ipl(path, rep)
        if doc is None:
            continue
        ed = doc.editor(game=game)
        _reserve_others(ed, path, [it[0] for it in items])
        results = []
        for obj, anchor, tol, kind in items:
            if kind == 'lod':
                results.append((obj, kind, ed.detach_lod(obj, anchor)))
            elif tol is None:
                results.append((obj, kind, ed.remove(obj, anchor)))
            else:
                results.append((obj, kind, ed.remove(obj, anchor, tol=tol)))
        if not _commit(ed, path, rep, dry_run, context):
            continue
        for obj, kind, r in results:
            if kind == 'dff' and r.removed:
                rep.add('removed')
                if not dry_run and ipl_linked_file(obj) == path:
                    clear_ipl(obj)
            if r.lod_removed:
                rep.add('lod_removed')
            if kind == 'lod' and not dry_run and r._row is not None:
                obj.inu.lod_index = -1
    return rep


# ── IPL: read back (sync / restore / verify) ───────────────────────────

class IplCache:
    def __init__(self, rep):
        self.rep = rep
        self.docs = {}

    def get(self, path):
        key = norm(path)
        if key not in self.docs:
            self.docs[key] = _load_ipl(key, self.rep) if os.path.isfile(key) else None
        return self.docs[key]


def ipl_locate(obj, cache, claimed):
    """(path, row index) of a linked object's row, or ('', -1)."""
    from ..core.mapsync import RELINK_TOL
    path = ipl_linked_file(obj)
    if not path or is_copy(obj):
        return '', -1
    doc = cache.get(path)
    if doc is None:
        return path, -1
    ex = claimed.setdefault(path, set())
    a = ipl_anchor(obj)
    i = doc.find(a, exclude=ex)
    if i < 0:
        i = doc.find(a, exclude=ex, tol=RELINK_TOL)
    if i >= 0:
        ex.add(i)
    return path, i


def apply_inst_transform(obj, inst):
    from mathutils import Quaternion
    obj.location = (inst.pos_x, inst.pos_y, inst.pos_z)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = Quaternion(
        (inst.rot_w, -inst.rot_x, -inst.rot_y, -inst.rot_z))


def ipl_pull(context, objs, files, *, move=True, far=None, clear_lost=False):
    """Link / refresh *objs* against their IPL rows.

    Linked objects: the row is found again by anchor (in the object's own
    file). With *move* the object takes the row's transform.
    Unlinked objects: linked to the nearest free row of their model in *files*
    within 0.5 m. *far* widens that when nothing is that close:
      'nearest' — the nearest free row at any distance (restore coords);
      'unique'  — only if it is the ONE free row of that model (verify).
    *clear_lost* drops the link of objects whose row is gone.
    Report counts: synced, linked, lost, skipped."""
    from ..core.mapsync import MATCH_TOL
    reset_copies()
    rep = Report()
    cache = IplCache(rep)
    claimed = {}
    objs = [o for o in objs if o.type == 'MESH' and model_type(o)[0] == 'DFF']
    unlinked = []
    for o in objs:
        if not o.inu.ipl_uuid or is_copy(o):
            unlinked.append(o)
            continue
        path, i = ipl_locate(o, cache, claimed)
        doc = cache.get(path) if path else None
        if i < 0 or doc is None:
            rep.add('lost')
            if clear_lost:
                clear_ipl(o)
            else:
                unlinked.append(o)
            continue
        inst = doc.rows[i].inst
        if move:
            apply_inst_transform(o, inst)
        stamp_ipl(o, path, inst, inst.lod_index)
        rep.add('synced')
    # Rows of linked objects outside *objs* must not be taken by the unlinked.
    in_objs = {id(o) for o in objs}
    for o in _mesh_objects():
        if o.inu.ipl_uuid and id(o) not in in_objs and not is_copy(o):
            ipl_locate(o, cache, claimed)
    for o in unlinked:
        mid = int(o.inu.model_id or 0)
        if mid <= 0:
            rep.add('skipped')
            continue
        wp = o.matrix_world.translation
        pos = (wp.x, wp.y, wp.z)
        hit = None
        # Near match in any file first, then the wider fallbacks.
        for mode in ('near', far):
            if mode is None or hit is not None:
                continue
            for fp in files:
                doc = cache.get(fp)
                if doc is None:
                    continue
                ex = claimed.setdefault(norm(fp), set())
                if mode == 'near':
                    i = doc.nearest(mid, pos, exclude=ex, max_dist=MATCH_TOL)
                elif mode == 'nearest':
                    i = doc.nearest(mid, pos, exclude=ex, max_dist=1e9)
                else:
                    free = [k for k in doc.rows_of(mid) if k not in ex]
                    i = free[0] if len(free) == 1 else -1
                if i >= 0:
                    hit = (norm(fp), doc, i)
                    ex.add(i)
                    break
        if hit is None:
            rep.add('skipped')
            continue
        path, doc, i = hit
        if is_copy(o):
            o.inu.ipl_uuid = ''          # a copy: gets its own identity
        inst = doc.rows[i].inst
        if move:
            apply_inst_transform(o, inst)
        stamp_ipl(o, path, inst, inst.lod_index)
        rep.add('linked')
    reset_copies()
    return rep


def refresh_links(files=None):
    """Re-check the links of the scene's LINKED models against their files
    (read-only — nothing is written to disk, nothing is moved).

    * IPL: row gone from the file → the link is dropped (status «Не в IPL»);
      row edited in the file (moved ≤ 2 m) → the link follows it, so the
      status shows «координаты разошлись» against the scene.
    * IDE: the model's id is gone, or now belongs to another name → the link
      is dropped (status «Не в IDE»).

    *files* — only these (normalized) paths; None = every linked file.
    Returns (ipl_lost, ide_lost)."""
    from ..core.mapsync import IdeDoc, RELINK_TOL
    reset_copies()
    rep = Report()
    cache = IplCache(rep)
    want = None if files is None else set(files)
    ipl_by_file, ide_by_file = {}, {}
    for o in _mesh_objects():
        p = ipl_linked_file(o)
        if p and (want is None or p in want) and not is_copy(o):
            ipl_by_file.setdefault(p, []).append(o)
        q = ide_linked_file(o)
        if q and (want is None or q in want):
            ide_by_file.setdefault(q, []).append(o)

    ipl_lost = 0
    for path, objs in ipl_by_file.items():
        if not os.path.isfile(path):
            doc = None
        else:
            doc = cache.get(path)
            if doc is None:              # binary / unreadable: leave as is
                continue
        taken = set()
        misses = []
        # Exact matches first, so a nudged row can't be stolen by a neighbour.
        for o in objs:
            i = doc.find(ipl_anchor(o), exclude=taken) if doc else -1
            if i >= 0:
                taken.add(i)
            else:
                misses.append(o)
        for o in misses:
            i = (doc.find(ipl_anchor(o), exclude=taken, tol=RELINK_TOL)
                 if doc else -1)
            if i < 0:
                clear_ipl(o)
                ipl_lost += 1
                continue
            taken.add(i)
            inst = doc.rows[i].inst
            stamp_ipl(o, path, inst, inst.lod_index)

    ide_lost = 0
    for path, objs in ide_by_file.items():
        doc = None
        if os.path.isfile(path):
            try:
                doc = IdeDoc.load(path)
            except OSError:
                continue
        for o in objs:
            inu = o.inu
            mid = int(inu.ide_last_model_id or 0) or int(inu.model_id or 0)
            row = doc.by_id(mid) if doc else None
            names = {n.lower() for n in (inu.ide_last_name,) if n}
            if row is None or (names and row.name.lower() not in names):
                clear_ide(o)
                ide_lost += 1
    reset_copies()
    return ipl_lost, ide_lost


def linked_files():
    """Every IDE/IPL file some scene object is linked to (normalized)."""
    out = set()
    for o in _mesh_objects():
        for p in (ipl_linked_file(o), ide_linked_file(o)):
            if p:
                out.add(p)
    return out


# ── IDE ────────────────────────────────────────────────────────────────

def ide_linked_file(obj):
    inu = obj.inu
    if not inu.ide_linked or not inu.ide_target_file:
        return ''
    return norm(inu.ide_target_file)


def stamp_ide(obj, path, entry):
    inu = obj.inu
    inu.ide_target_file = path
    inu.ide_linked = True
    inu.ide_last_model_id = int(entry.model_id)
    inu.ide_last_name = entry.model_name
    inu.ide_last_draw_distance = float(entry.draw_distance)
    inu.ide_last_txd_name = entry.txd_name
    inu.ide_last_flags = int(entry.flags)


def clear_ide(obj):
    inu = obj.inu
    inu.ide_target_file = ''
    inu.ide_linked = False
    inu.ide_last_model_id = 0
    inu.ide_last_name = ''
    inu.ide_last_draw_distance = 0.0
    inu.ide_last_txd_name = ''
    inu.ide_last_flags = 0


def ide_entries(objs, rep):
    """Selection → [(obj, IdeObject, parent DFF or None)]: models + their LOD
    partners, one entry per object (copies of a model collapse onto one row in
    the editor). *parent* is set for a LOD pulled in by its model."""
    from .. import _ide_entry_from_obj, _clean_model_name_ide
    lodix = LodIndex()
    out, seen = [], set()
    dff_of_lod = {}
    ordered = []
    for o in objs:
        if o.type != 'MESH':
            continue
        mt, base = model_type(o)
        if mt == 'COL':
            continue
        ordered.append((o, mt, base))
        if mt == 'DFF':
            lodo = lodix.partner(o)
            if lodo is not None:
                dff_of_lod.setdefault(id(lodo), o)
                ordered.append((lodo, 'LOD', model_type(lodo)[1] or base))
    for o, mt, base in ordered:
        if id(o) in seen:
            continue
        seen.add(id(o))
        e = _ide_entry_from_obj(o)
        if mt == 'LOD':
            dff = dff_of_lod.get(id(o))
            e.model_name = lod_model_name(o, base)
            e.model_id = lod_model_id(o, dff)
            dff_txd = (getattr(dff.inu, 'txd_name', '') or '').strip() if dff else ''
            e.txd_name = dff_txd or (e.txd_name or '').strip() or _clean_model_name_ide(base)
            if dff is not None:
                e.draw_distance = dff.inu.lod_draw_distance
        if e.model_id <= 0:
            rep.msg('ERROR', T("«{0}»: Model ID = 0 — не записана").format(o.name))
            continue
        out.append((o, e, dff_of_lod.get(id(o)) if mt == 'LOD' else None))
    return out


def ide_write(context, objs, *, picked='', dry_run=False):
    rep = Report()
    game = scene_game(context)
    picked = norm(picked) if picked else ''
    groups = {}
    for o, e, parent in ide_entries(objs, rep):
        own = ide_linked_file(o)
        path = picked or own or (ide_linked_file(parent) if parent else '')
        if not path:
            rep.msg('ERROR', T("«{0}»: нет своего IDE — выбери файл в панели IDE").format(o.name))
            continue
        if own and picked and own != picked and os.path.isfile(own):
            rep.msg('WARNING', T("«{0}» была в {1} — записана в выбранный "
                                 "{2}").format(o.name, os.path.basename(own),
                                               os.path.basename(picked)))
        groups.setdefault(path, []).append((o, e))
    from ..core.mapsync import IdeDoc
    for path, items in groups.items():
        try:
            doc = IdeDoc.load(path)
        except OSError as ex:
            rep.msg('ERROR', f"{os.path.basename(path)}: {ex}")
            continue
        ed = doc.editor(game=game)
        results = []
        for o, e in items:
            same = ide_linked_file(o) == path
            results.append(ed.write(
                o, e,
                anchor_id=int(o.inu.ide_last_model_id or 0) if same else 0,
                anchor_name=(o.inu.ide_last_name or '') if same else ''))
        if not _commit(ed, path, rep, dry_run, context):
            continue
        for r in results:
            rep.add(r.action)
            if not dry_run and r.action != 'conflict':
                stamp_ide(r.tag, path, r.entry)
    return rep


def ide_remove(context, objs, *, picked='', target='', dry_run=False):
    rep = Report()
    game = scene_game(context)
    target = norm(target) if target else ''
    picked = norm(picked) if picked else ''
    groups = {}
    entries = [(o, e) for o, e, _p in ide_entries(objs, Report())]
    removing = {int(e.model_id) for _o, e in entries}
    for o, e in entries:
        path = target or ide_linked_file(o) or picked
        if not path or not os.path.isfile(path):
            rep.msg('WARNING', T("«{0}»: нет IDE-файла").format(o.name))
            continue
        groups.setdefault(path, []).append((o, e))
    # Placements that still use a model being removed from its IDE.
    sel = {id(o) for o, _e in entries}
    users = {}
    for o in _mesh_objects():
        mid = int(o.inu.model_id or 0)
        if mid in removing and id(o) not in sel and o.inu.ipl_uuid:
            users[mid] = users.get(mid, 0) + 1
    for mid, n in users.items():
        rep.msg('WARNING', T("ID {0} ещё стоит в IPL у {1} объектов").format(mid, n))
    from ..core.mapsync import IdeDoc
    for path, items in groups.items():
        doc = IdeDoc.load(path)
        ed = doc.editor(game=game)
        done = []
        for o, e in items:
            same = ide_linked_file(o) == path
            ok = ed.remove(o, int(e.model_id), e.model_name,
                           anchor_name=(o.inu.ide_last_name or '') if same else '')
            done.append((o, ok))
        if not _commit(ed, path, rep, dry_run, context):
            continue
        for o, ok in done:
            if ok:
                rep.add('removed')
                if not dry_run:
                    clear_ide(o)
    return rep


# ── report text ────────────────────────────────────────────────────────

def summary(prefix, rep):
    c = rep.counts
    parts = []
    if c.get('add'):
        s = T("добавлено {0}").format(c['add'])
        parts.append(s)
    if c.get('update'):
        parts.append(T("обновлено {0}").format(c['update']))
    if c.get('lod_add') or c.get('lod_update'):
        parts.append(T("LOD +{0} ~{1}").format(c.get('lod_add', 0),
                                               c.get('lod_update', 0)))
    if c.get('removed'):
        parts.append(T("удалено {0}").format(c['removed']))
    if c.get('lod_removed'):
        parts.append(T("LOD удалено {0}").format(c['lod_removed']))
    if c.get('unchanged') or c.get('same'):
        parts.append(T("без изменений {0}").format(
            c.get('unchanged', 0) + c.get('same', 0)))
    if c.get('conflict'):
        parts.append(T("конфликтов {0}").format(c['conflict']))
    if c.get('synced'):
        parts.append(T("обновлено из файла {0}").format(c['synced']))
    if c.get('linked'):
        parts.append(T("новых связей {0}").format(c['linked']))
    if c.get('lost'):
        parts.append(T("строка не найдена {0}").format(c['lost']))
    if c.get('skipped'):
        parts.append(T("пропущено {0}").format(c['skipped']))
    if not parts:
        parts.append(T("нечего делать"))
    return f"{prefix}: " + ", ".join(parts)


def report_to(op, prefix, rep, *, pub=None):
    """Push *rep* into the operator's reports; returns the summary line."""
    line = summary(prefix, rep)
    seen = set()
    for level, text in rep.messages:
        if (level, text) in seen:
            continue
        seen.add((level, text))
        op.report({level if level in ('WARNING', 'ERROR') else 'INFO'}, text)
    level = 'WARNING' if rep.problems() else 'INFO'
    if pub is not None:
        pub(op, level, line)
    else:
        op.report({level}, line)
    return line


# ── confirmation dialog («only when there are problems») ───────────────

class ConfirmOnProblems:
    """Mixin for operators: invoke() does a dry run; if it finds problems a
    dialog lists them before anything is written. Clean runs write at once.
    Subclasses implement ``_run(context, dry_run) -> Report``."""

    _problem_lines = []

    def invoke(self, context, event):
        try:
            rep = self._run(context, True)
        except Exception:                                   # noqa: BLE001
            return self.execute(context)
        probs = [t for lvl, t in rep.problems()]
        if not probs:
            return self.execute(context)
        type(self)._problem_lines = probs[:12] + (
            [T("… ещё {0}").format(len(probs) - 12)] if len(probs) > 12 else [])
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=T("Перед записью найдены проблемы:"), icon='ERROR')
        for line in type(self)._problem_lines:
            col.label(text=line)
        col.separator()
        col.label(text=T("Остальное будет записано. Продолжить?"))
