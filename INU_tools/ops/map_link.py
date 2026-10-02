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
        self.touch = {}             # path → what a removal does there (confirm dialog)

    def add(self, key, n=1):
        self.counts[key] = self.counts.get(key, 0) + n

    def msg(self, level, text):
        self.messages.append((level, text))

    def plan(self, path, what):
        self.touch.setdefault(path, []).append(what)

    def problems(self):
        return [m for m in self.messages if m[0] in ('WARNING', 'ERROR')]

    def merge(self, other):
        for k, v in other.counts.items():
            self.add(k, v)
        self.messages += other.messages
        self.files |= other.files
        for p, w in other.touch.items():
            self.touch.setdefault(p, []).extend(w)


# ── LOD partners ────────────────────────────────────────────────────────

def _stands_on(lodo, dff):
    """*lodo* stands on *dff*: its place and rotation — where the model is now
    or its IPL row. A vanilla III/VC LOD isn't always placed like its model
    (VC: ~1 in 8 turned or moved, III more): a LOD row at the model's spot
    would turn / move it, so such a pair is left to the IPL as it is."""
    from ..core.mapsync import pos_close, rot_close
    lo, d = ipl_inst_of(lodo), ipl_inst_of(dff)
    spots = [((d.pos_x, d.pos_y, d.pos_z), (d.rot_x, d.rot_y, d.rot_z, d.rot_w))]
    if dff.inu.ipl_uuid:
        spots.append((tuple(dff.inu.ipl_last_pos), tuple(dff.inu.ipl_last_rot)))
    p, q = (lo.pos_x, lo.pos_y, lo.pos_z), (lo.rot_x, lo.rot_y, lo.rot_z, lo.rot_w)
    return any(pos_close(p, sp, 0.01) and rot_close(q, sq, 1e-4) for sp, sq in spots)


class LodIndex:
    """base name (lower) → LOD meshes in the scene, built once per run; in
    III/VC, none by base → the game's pairing by name (tail_partners).
    *mtype* — the classifier (panels pass the cached one)."""

    def __init__(self, mtype=None):
        self._mt = mtype or model_type
        self.by_base = {}
        # III/VC: the game pairs by name from the 4th character (LODtower ↔
        # ap_tower) — name[3:] of the LOD's names → LOD meshes.
        self.by_tail = {}
        self._models = None             # the scene's DFFs, see tail_partners
        game = scene_game(bpy.context)
        # Only THIS scene: a LOD mesh in another scene of the .blend is not
        # part of this map (and may carry that scene's stale stamps).
        for o in bpy.context.scene.objects:
            if o.type != 'MESH' or not hasattr(o, 'inu'):
                continue
            if 'lod' not in o.name.lower() and getattr(o.inu, 'type', '') != 'LOD':
                continue
            mt, base = self._mt(o)
            if mt == 'LOD' and base:
                self.by_base.setdefault(base.lower(), []).append(o)
                if game in ('III', 'VC'):
                    for nm in dict.fromkeys((lod_model_name(o, base, game=game),
                                             plain_name(o))):
                        if len(nm) > 3 and nm.lower().startswith('lod'):
                            self.by_tail.setdefault(nm[3:], []).append((nm, o))

    def partner(self, dff):
        lodo = getattr(dff.inu, 'lod_object', None)
        if lodo is not None and lodo.type == 'MESH' and lodo.name in bpy.data.objects:
            return lodo
        _mt, base = self._mt(dff)
        cands = self.by_base.get((base or '').lower(), [])
        if not cands:
            cands = self.tail_partners(dff, base or '')
        if not cands:
            return None
        # Prefer the undecorated one (LODhouse over LODhouse.001).
        return min(cands, key=lambda o: (o.name != plain_name(o), o.name))

    def tail_partners(self, dff, name):
        """III/VC: LOD meshes the game gives *dff* (model *name*) — same name
        from the 4th character, *name* the first such model of the scene by
        ID (core.ipl.lod_owner_by_tail: lodbackbit → lhsbackbit 1410, not
        havbackbit 1451) — that stand on it (_stands_on)."""
        from ..core.ipl import lod_owner_by_tail
        hits = self.by_tail.get(name[3:]) if len(name) > 3 else None
        if not hits:
            return []
        if self._models is None:
            self._models = {}           # name[3:] → [(model id, name)] of DFFs
            for o in bpy.context.scene.objects:
                if o.type == 'MESH' and hasattr(o, 'inu'):
                    mt, b = self._mt(o)
                    if mt == 'DFF' and b and len(b) > 3:
                        self._models.setdefault(b[3:], []).append(
                            (int(getattr(o.inu, 'model_id', 0) or 0), b))
        models = self._models.get(name[3:], [])
        return list({id(o): o for nm, o in hits
                     if lod_owner_by_tail(nm, models) == name
                     and _stands_on(o, dff)}.values())

    def owners(self, lodo, dffs):
        """DFFs among *dffs* whose partner is *lodo*."""
        return [d for d in dffs if self.partner(d) is lodo]


class IdeLods:
    """LOD definitions read from IDE files — for a model whose LOD mesh is not
    in this scene (made in another .blend, only the DFF brought over).

    Where to look, in order: the IDE the model is linked to, the IDE picked in
    the panel, the «IDE для экспорта» list. A LOD row is ``LOD<base>`` or any
    LOD-named row whose base is the model's (``lodcuntw05`` → ``cuntw05``);
    with several, the one with id = model id + 1 wins. III/VC, none by base:
    the row the game gives the model — same name from the 4th character
    (LODtower ↔ ap_tower), the model first by ID among that IDE's rows."""

    def __init__(self, context):
        s = context.scene.inu_settings
        self.common = []
        for p in ([getattr(s, 'gtatools_ide_path', '')]
                  + [it.path for it in getattr(s, 'gtatools_ide_sync_list', [])]):
            p = norm(p) if p else ''
            if p and p not in self.common and os.path.isfile(p):
                self.common.append(p)
        self.game = scene_game(context)
        self._by_file = {}            # path → {base lower: [(id, name)]}
        self._rows = {}               # path → [(id, name)] of objs/tobj

    def _index(self, path):
        if path not in self._by_file:
            from ..core.mapsync import IdeDoc
            from ..core.ipl import is_lod_name, strip_lod_marker
            idx, rows = {}, []
            try:
                doc = IdeDoc.load(path)
            except OSError:
                doc = None
            for r in (doc.rows if doc else ()):
                if r.section not in ('objs', 'tobj'):
                    continue
                rows.append((r.model_id, r.name))
                if not is_lod_name(r.name):
                    continue
                low = r.name.lower()
                bases = {strip_lod_marker(r.name).lower()}
                if low.startswith('lod'):
                    bases.add(low[3:].lstrip('_-'))
                    bases.add('~' + r.name[3:])     # III/VC: case kept
                for b in bases:
                    idx.setdefault(b, []).append((r.model_id, r.name))
            self._by_file[path] = idx
            self._rows[path] = rows
        return self._by_file[path]

    def find(self, dff, base):
        """(model_id, model_name, ide_path) of the LOD of *dff*, or None."""
        from ..core.ipl import lod_owner_by_tail
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
        if self.game not in ('III', 'VC') or len(base or '') <= 3:
            return None
        for path in files:
            idx, rows = self._index(path), self._rows[path]
            me = next((nm for _i, nm in rows if nm.lower() == base.lower()), None)
            if me is None:                      # the model not in this IDE
                me, rows = base, rows + [(did, base)]
            cands = [c for c in idx.get('~' + me[3:], ())
                     if lod_owner_by_tail(c[1], rows) == me]
            if cands:
                best = min(cands, key=lambda c: (c[0] != did + 1, c[0]))
                return best[0], best[1], path
        return None


def _lod_is_model(lod, dinst):
    """A «LOD» carrying the model's own id or name is the model — never
    write it as the LOD row (that produced a second copy of the model)."""
    return (int(lod.model_id) == int(dinst.model_id)
            or lod.model_name.lower() == dinst.model_name.lower())


def _scale_note(obj, style, rep):
    """SA has no scale column; III/VC parse it but don't apply it either."""
    if any(abs(c - 1.0) > 1e-4 for c in obj.matrix_world.to_scale()):
        rep.msg('WARNING', T("«{0}»: игра не применяет масштаб из IPL "
                             "(модель в игре будет в масштабе 1)").format(obj.name))


def ide_draw_distance(obj, is_lod=None):
    """The LOD's panel field when set; old scenes keep Draw Dist."""
    inu = getattr(obj, 'inu', None)
    distance = getattr(inu, 'draw_distance', 299.0)
    if is_lod is None:
        is_lod = model_type(obj)[0] == 'LOD'
    lod_distance = getattr(inu, 'lod_draw_distance', 0.0)
    return lod_distance if is_lod and lod_distance > 0 else distance


def stamp_lod_ide(dff, hit):
    """Remember on the model that its LOD comes from the IDE (panel shows it)."""
    inu = dff.inu
    inu.lod_ide_id = int(hit[0])
    inu.lod_ide_name = hit[1]
    inu.lod_ide_file = hit[2]


def lod_model_name(lodo, base, hd='', game=None):
    """Model name of a LOD: the name it was imported/written with, else
    the addon's «LOD<base>» convention. *hd* — its model's name, when known:
    in III/VC the game pairs them by name (house → LODse), see
    core.ipl.lod_name_for — unless that name is taken (lod_name_taken).
    *game* — the scene's by default."""
    from ..core.ipl import lod_name_for
    nm = (getattr(lodo.inu, 'ide_last_name', '') or '').strip()
    if game is None:
        game = scene_game(getattr(bpy, 'context', None))
    own = plain_name(lodo) if (hd and game in ('III', 'VC')) else ''
    return lod_name_for(own, nm, hd, base, game,
                        taken=lambda n: lod_name_taken(n, hd, lodo, game))


def new_lod_name(hd, base, lodo=None, game=None):
    """Name of a LOD that has none of its own yet (Export to IMG's copy of
    the model, a group renamed in the file browser) — lod_model_name's
    rule: the game's name for *hd* in III/VC unless taken, else LOD<base>."""
    from ..core.ipl import lod_name_for
    if game is None:
        game = scene_game(bpy.context)
    return lod_name_for('', '', hd, base, game,
                        taken=lambda n: lod_name_taken(n, hd, lodo, game))


_IDE_NAMES = {}     # IDE path → ((mtime, size), {name lower: [(id, name)]},
                    #             {name[3:]: [(id, name)]}) of objs/tobj rows


def _ide_names(path):
    """Model names of the IDE *path* (cached while the file is unchanged)."""
    try:
        st = os.stat(path)
    except OSError:
        return {}, {}
    hit = _IDE_NAMES.get(path)
    if hit is None or hit[0] != (st.st_mtime_ns, st.st_size):
        from ..core.mapsync import IdeDoc
        by_name, by_tail = {}, {}
        try:
            rows = [r for r in IdeDoc.load(path).rows
                    if r.section in ('objs', 'tobj')]
        except Exception:                                   # noqa: BLE001
            rows = []                                       # unreadable: skip
        for r in rows:
            by_name.setdefault(r.name.lower(), []).append((int(r.model_id), r.name))
            if len(r.name) > 3:
                by_tail.setdefault(r.name[3:], []).append((int(r.model_id), r.name))
        hit = _IDE_NAMES[path] = ((st.st_mtime_ns, st.st_size), by_name, by_tail)
    return hit[1], hit[2]


def _known_ides(objs, game, *, context=None):
    """IDE files a new LOD name is checked against: those *objs* are linked
    to, the panel's IDE and «IDE для экспорта» list, and every IDE the game
    of the game folder loads (its vanilla names)."""
    s = getattr((context or bpy.context).scene, 'inu_settings', None)
    paths = [ide_linked_file(o) for o in objs]
    paths += [getattr(s, 'gtatools_ide_path', '')]
    paths += [it.path for it in getattr(s, 'gtatools_ide_sync_list', [])]
    root = getattr(s, 'gtatools_game_root', '') or ''
    root = bpy.path.abspath(root) if root else ''
    if root and os.path.isdir(root):
        from ..core.gta_dat import dat_game, game_ide_paths
        if dat_game(root) == game:
            paths += game_ide_paths(root)[0]
    out = []
    for p in paths:
        p = norm(p) if p else ''
        if p and p not in out and os.path.isfile(p):
            out.append(p)
    return out


def lod_name_taken(name, hd, lodo=None, game=None):
    """III/VC: who keeps a NEW LOD of the model *hd* from the name *name*
    (the game's, core.ipl.default_lod_name) — '' when nobody:
    * a model of the scene with the same name from the 4th character (any
      case) that comes first by ID — the game gives the name to it, and one
      IMG holds one file of that name (dt_house1 / ne_house1 → LODhouse1);
    * another object of the scene called or written so;
    * a row of a known IDE (_known_ides) with that name and another ID —
      the vanilla LODhotel (of havhotel) for my_hotel — or the model the
      game gives that name there (VC: in an IDE of *hd* only).
    *lodo* — the LOD object (its copies are itself), None for a new one."""
    from ..core.ipl import lod_owner_by_tail
    if len(hd) <= 3:
        return ''                       # the game pairs nothing to it anyway
    if game is None:
        game = scene_game(bpy.context)
    low, tail = name.lower(), hd[3:].lower()
    me = plain_name(lodo).lower() if lodo is not None else ''
    peers, linked = {hd.lower(): (0, hd)}, [lodo] if lodo is not None else []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or not hasattr(o, 'inu'):
            continue
        pn = plain_name(o).lower()
        if me and pn == me:
            continue
        if low in (pn, (getattr(o.inu, 'ide_last_name', '') or '').strip().lower()):
            return o.name
        if tail not in pn:
            continue
        mt, b = model_type(o)
        if mt != 'DFF' or not b or b[3:].lower() != tail:
            continue
        mid = int(getattr(o.inu, 'model_id', 0) or 0)
        old = peers.get(b.lower())
        if old is None or (mid > 0 and (old[0] <= 0 or mid < old[0])):
            peers[b.lower()] = (mid, b)
        if b.lower() == hd.lower():
            linked.append(o)
    first = min(peers.values(), key=lambda p: (p[0] <= 0, p[0], p[1].lower()))
    if first[1].lower() != hd.lower():
        return first[1]
    hid = peers[hd.lower()][0]
    lid = int(getattr(lodo.inu, 'model_id', 0) or 0) if lodo is not None else 0
    if lid <= 0:
        lid = hid + 1 if hid > 0 else 0
    for path in _known_ides(linked, game):
        by_name, by_tail = _ide_names(path)
        f = os.path.basename(path)
        for mid, nm in by_name.get(low, ()):
            if mid != lid:
                return "{0}, {1}".format(nm, f)
        if game == 'VC' and hd.lower() not in by_name:
            continue
        cands = [c for c in by_tail.get(hd[3:], ()) if c[1].lower() != low]
        owner = lod_owner_by_tail(name, cands + [(hid, hd)])
        if owner is not None and owner.lower() != hd.lower():
            return "{0}, {1}".format(owner, f)
    return ''


def lod_name_note(lodo, name, hd, game=None):
    """III/VC: why the game won't pair the LOD written as *name* with its
    model *hd* — '' when it will (or SA, or the model unknown). Add to IDE
    and the exports show it."""
    from ..core.ipl import default_lod_name, lod_pairs_by_name
    if game is None:
        game = scene_game(bpy.context)
    if not hd or game not in ('III', 'VC'):
        return ''
    if len(hd) <= 3:
        return T("«{0}»: имя короче 4 символов — в III/VC игра "
                 "не свяжет с ним LOD").format(hd)
    if lod_pairs_by_name(name, hd):
        return ''
    want = default_lod_name(hd, game)
    who = lod_name_taken(want, hd, lodo, game)
    if who:
        return T("«{0}»: имя LOD по правилу III/VC «{1}» уже занято ({2}) — "
                 "LOD записан как «{3}» и в игре не свяжется, переименуй "
                 "модель").format(hd, want, who, name)
    return T("«{0}»: LOD «{1}» не свяжется в игре — III/VC сравнивают имена "
             "с 4-го символа, нужно «{2}»").format(hd, name, want)


def lod_name_notes(objs):
    """lod_name_note of every LOD mesh among *objs* (Export IDE / IPL) —
    the first 5, then how many more."""
    if scene_game(bpy.context) not in ('III', 'VC'):
        return []
    hd_of, out = lod_hd_names(objs), []
    for o in objs:
        mt, base = model_type(o) if o.type == 'MESH' else (None, '')
        hd = hd_of.get(id(o), '')
        if mt == 'LOD' and hd:
            note = lod_name_note(o, lod_model_name(o, base, hd=hd), hd)
            if note and note not in out:
                out.append(note)
    if len(out) > 5:
        out[5:] = ["(+{0})".format(len(out) - 5)]
    return out


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


def stamp_map_import(obj, is_lod, ide_obj, ide_path, arch, model_name):
    """Import Map: what a placed mesh knows about its model, as the Import
    tab sets it — the IMG it came from (``arch``), the IDE row's values (a
    LOD row's distance is its LOD Dist) and the link to that row's IDE
    (``ide_path``, normalized). No IDE row → unlinked, TXD = model name.
    The distance stays in draw_distance too: Export IDE and the Ariane
    bridge read that field on every mesh (a LOD included)."""
    inu = obj.inu
    if arch:
        inu.img_target_file = arch
    if ide_obj is None:
        clear_ide(obj)
        if not inu.txd_name:
            inu.txd_name = model_name
        return
    inu.draw_distance = ide_obj.draw_distance
    if is_lod:
        inu.lod_draw_distance = ide_obj.draw_distance
    inu.ide_flags = ide_obj.flags
    inu.txd_name = ide_obj.txd_name
    if ide_path:
        stamp_ide(obj, ide_path, ide_obj)
    else:
        clear_ide(obj)


_holders = None     # ipl_uuid → [objects]; rebuilt per run (reset_copies)


def reset_copies():
    global _holders, _places
    _holders = None
    _places = None
    _place_of.clear()


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


def _original_file(copy):
    """IPL a Shift+D *copy* goes to: its original's current file (the copy's
    own link may be stale — the original moved since). '' when that file is
    gone, so no new file appears silently at the old path."""
    u = copy.inu.ipl_uuid
    path = ipl_linked_file(copy)
    for o in (_holders or {}).get(u, ()):
        if o.inu.ipl_uuid == u and not is_copy(o):
            path = ipl_linked_file(o) or path
            break
    return path if os.path.isfile(path) else ''


# ── a model of several meshes ──────────────────────────────────────────
#
# The game draws every atomic of a map model at its IPL row's matrix
# (core.mapsync.groups), so the meshes of one model standing together
# (bar_barrier10: …_L0 + …_dam) are ONE placement: one row, one name, one
# IDE row — written by one of them, the main (main_of).

_places = None      # model id → the scene's meshes of it; per run (reset_copies)
_place_of = {}      # id(mesh) → (main, meshes at its spot), per model id asked


def main_rank(o):
    """Order of the meshes of a placement for its main when none is linked:
    not the damaged part (…_dam), the first atomic of the DFF, the name.
    Import from IMG stamps the IPL row on the same one."""
    from ..core.mapsync import is_damage_part
    order = o.get('inu_atomic_order') if hasattr(o, 'get') else None
    return (is_damage_part(o.name),
            order if isinstance(order, int) else 1 << 30, o.name)


def _spot_mains(meshes, copy_of, mtype):
    """{id(mesh): (main, meshes at its spot)} for the *meshes* (one model id)
    that stand with another DFF mesh — the same row (core.mapsync
    group_instances). Main: a linked mesh that is no copy — each one its own,
    two rows at one spot stay two — else a linked one (a copy: its row goes
    into its original's file), else main_rank. *copy_of* — is_copy."""
    from .. import _ipl_entry_from_obj
    from ..core.mapsync import group_instances
    items = []
    for o in meshes:
        e = _ipl_entry_from_obj(o)
        items.append((o, int(e.model_id), (e.pos_x, e.pos_y, e.pos_z),
                      (e.rot_w, e.rot_x, e.rot_y, e.rot_z)))
    out = {}
    for spot in group_instances(items):
        if len(spot) > 1:
            spot = [o for o in spot if mtype(o)[0] == 'DFF']
        if len(spot) < 2:
            continue
        linked = [o for o in spot if o.inu.ipl_uuid]
        own = {id(o) for o in linked if not copy_of(o)}
        head = min([o for o in linked if id(o) in own] or linked or spot,
                   key=main_rank)
        for o in spot:
            out[id(o)] = (o if id(o) in own else head, spot)
    return out


def _place(o):
    """(main, meshes at its spot) of the mesh *o* — per run."""
    global _places
    hit = _place_of.get(id(o))
    if hit is not None:
        return hit
    if _places is None:
        _places = {}
        for p in getattr(bpy.context.scene, 'objects', ()):
            if p.type == 'MESH':
                mid = int(getattr(getattr(p, 'inu', None), 'model_id', 0) or 0)
                if mid > 0:
                    _places.setdefault(mid, []).append(p)
    peers = _places.pop(int(getattr(o.inu, 'model_id', 0) or 0), None)
    if peers is not None and len(peers) > 1:        # each model id once
        _place_of.update(_spot_mains(peers, is_copy, model_type))
    return _place_of.get(id(o)) or (o, [o])


def _place_now(o):
    """_place without the per-run cache (panels): only the meshes of *o*'s
    model id near it are looked at."""
    from ..core.mapsync import SPOT_POS_TOL
    mid = int(getattr(o.inu, 'model_id', 0) or 0)
    if mid <= 0 or model_type_cached(o)[0] != 'DFF':
        return o, [o]
    t, near = o.matrix_world.translation, []
    for p in getattr(bpy.context.scene, 'objects', ()):
        if (p.type != 'MESH' or int(getattr(getattr(p, 'inu', None),
                                             'model_id', 0) or 0) != mid):
            continue
        pt = p.matrix_world.translation
        if max(abs(pt.x - t.x), abs(pt.y - t.y), abs(pt.z - t.z)) <= SPOT_POS_TOL:
            near.append(p)
    if len(near) < 2:
        return o, [o]
    return _spot_mains(near, lambda m: is_copy(m, cached=False),
                       model_type_cached).get(id(o)) or (o, [o])


def main_of(o, *, cached=True):
    """The mesh that stands for *o*'s placement — *o* itself for a model of
    one mesh. Panels pass cached=False (the per-run cache would go stale
    between redraws)."""
    return (_place(o) if cached else _place_now(o))[0]


def panel_main(o):
    """main_of for the panels' IPL state: a linked mesh is its own; else
    memoised (tools.draw_cache — a name, never the object) by the mesh's
    name, matrix and the scene's object count, so a redraw doesn't walk
    the scene."""
    inu = o.inu
    if inu.ipl_uuid or int(getattr(inu, 'model_id', 0) or 0) <= 0:
        return o
    from ..tools import draw_cache
    key = ('ipl_main', o.name,
           tuple(round(v, 4) for row in o.matrix_world for v in row),
           len(bpy.context.scene.objects))
    name = draw_cache.memo(key, lambda: main_of(o, cached=False).name)
    return bpy.data.objects.get(name) or o


def _followers(main):
    """The other meshes of *main*'s placement — they move with it."""
    return [m for m in _place(main)[1] if m is not main and _place(m)[0] is main]


def placement_name(o, ide=False):
    """Model name of *o*'s placement when its model has several meshes at the
    spot — not a mesh's own name (bar_barrier10_L0): the name its IPL row
    (*ide*: its IDE row) was imported / last written with, else the game's
    name of the main mesh (core.mapsync.game_model_name). '' for a model of
    one mesh — its own name stands."""
    main, spot = _place(o)
    if len(spot) < 2:
        return ''
    inu = main.inu
    if not ide and inu.ipl_last_name:
        return inu.ipl_last_name
    if inu.ide_linked and inu.ide_last_name:
        return inu.ide_last_name
    from .. import _clean_model_name_ide
    from ..core.mapsync import game_model_name
    return game_model_name(_clean_model_name_ide(main.name))


def ipl_inst_of(obj):
    from .. import _ipl_entry_from_obj
    return _ipl_entry_from_obj(obj)


def lod_inst_for(dff, lodo, base, dinst):
    """LOD row for *dff*: the LOD model, at the DFF's transform — *dinst*,
    the model's own row as it will be written (snapped to its file row)."""
    from .. import _ipl_entry_from_obj
    e = _ipl_entry_from_obj(lodo)
    e.model_name = lod_model_name(lodo, base, hd=dinst.model_name)
    e.model_id = lod_model_id(lodo, dff)
    e.pos_x, e.pos_y, e.pos_z = dinst.pos_x, dinst.pos_y, dinst.pos_z
    e.rot_x, e.rot_y, e.rot_z, e.rot_w = (dinst.rot_x, dinst.rot_y,
                                          dinst.rot_z, dinst.rot_w)
    e.interior = dinst.interior
    e.real_interior = dinst.real_interior
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


def file_game(doc, default):
    """Row layout of an IPL file (SA / VC / III) — the one most of its inst
    rows use; an empty or new file takes *default* (the scene's game). New
    rows follow the file: VC drops an 11-column SA row, SA misreads a
    13-column VC row."""
    counts = {}
    for row in doc.rows:
        if row.inst is not None:
            counts[row.style] = counts.get(row.style, 0) + 1
    if not counts:
        return default
    return max(counts, key=lambda k: counts[k])


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
    LOD rows of the already-linked models that use it. A model of several
    meshes at one spot is one placement — its main (main_of)."""
    dffs, lods = [], []
    seen, mains = set(), set()
    for o in objs:
        if o.type != 'MESH' or id(o) in seen:
            continue
        seen.add(id(o))
        mt, _b = model_type(o)
        if mt == 'COL':
            continue
        if mt == 'LOD':
            lods.append(o)
            continue
        o = main_of(o)
        if id(o) not in mains:
            mains.add(id(o))
            dffs.append(o)
    return dffs, lods


# Snapping a placement onto its own file row (see _snap_to_row). Position:
# the panel's «координаты разошлись» threshold (core.mapsync POS_EPS, see
# ipl_status), so a snapped object never shows as drifted.
IPL_POS_EPS = 1e-4
IPL_ROT_EPS = 1e-5


def _f32(v):
    """*v* as Blender stores it (float32); None when out of float32 range."""
    import struct
    try:
        return struct.unpack('<f', struct.pack('<f', v))[0]
    except (OverflowError, struct.error):
        return None


def _snap_to_row(inst, ref):
    """Scene values within float32 noise of the object's file row *ref* →
    the row's own values, so Add leaves an untouched row byte-for-byte.

    Transforms and anchors are float32 in Blender (2233.8032 comes back as
    2233.80322265625 and would be written 2233.803223); the file row is the
    only full-precision copy. Position is compared with f32(row) — what the
    anchor will hold. Quaternion: q and −q are one rotation and
    to_quaternion() always gives w ≥ 0, so the sign follows the row first."""
    pos = (inst.pos_x, inst.pos_y, inst.pos_z)
    rpos = (ref.pos_x, ref.pos_y, ref.pos_z)
    fpos = [_f32(r) for r in rpos]
    if None not in fpos and all(abs(p - f) <= IPL_POS_EPS
                                for p, f in zip(pos, fpos)):
        inst.pos_x, inst.pos_y, inst.pos_z = rpos
    q = (inst.rot_x, inst.rot_y, inst.rot_z, inst.rot_w)
    rq = (ref.rot_x, ref.rot_y, ref.rot_z, ref.rot_w)
    if sum(a * b for a, b in zip(q, rq)) < 0:
        q = tuple(-a for a in q)
    if all(abs(a - b) <= IPL_ROT_EPS for a, b in zip(q, rq)):
        q = rq
    inst.rot_x, inst.rot_y, inst.rot_z, inst.rot_w = q


def _stream_prefix(path, context, cache):
    """SA: binary ``<name>_stream*.ipl`` in the game's IMGs point at the inst
    rows of the text IPL *path* by NUMBER (their LOD index) — deleting a row
    there shifts every later one. Returns that prefix when such files exist,
    else ''. The game: the folder *path* lies in (with models/gta3.img), else
    the scene's game folder; none → '' (a file outside the game)."""
    from ..core.img import read_directory
    from ..core.gta_dat import find_all_resources
    from ..core.fs_ci import resolve as _ci
    roots = []
    d = os.path.dirname(path)
    for _ in range(6):
        if os.path.isfile(_ci(os.path.join(d, 'models', 'gta3.img'))):
            roots.append(d)
            break
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    s = getattr(context.scene.inu_settings, 'gtatools_game_root', '') or ''
    if s:
        roots.append(bpy.path.abspath(s))
    root = next((r for r in roots if os.path.isdir(r)), '')
    if not root:
        return ''
    names = cache.get(root)
    if names is None:
        names = set()
        imgs = [_ci(os.path.join(root, 'models', 'gta3.img')),
                _ci(os.path.join(root, 'models', 'gta_int.img'))]
        try:
            imgs += find_all_resources(root).img_paths
        except OSError:
            pass
        for p in dict.fromkeys(os.path.normcase(os.path.normpath(p)) for p in imgs):
            if not os.path.isfile(p):
                continue
            try:
                names.update(e.name.lower() for e in read_directory(p))
            except Exception:                               # noqa: BLE001
                continue                                    # broken IMG: skip
        cache[root] = names
    prefix = os.path.splitext(os.path.basename(path))[0].lower() + '_stream'
    return prefix if any(n.startswith(prefix) for n in names) else ''


def _lod_row_apart(doc, mrow, lod_id):
    """III/VC: the IPL has rows of the LOD model *lod_id*, none on the model's
    row *mrow* (its place and rotation) — a vanilla LOD placed apart from its
    model (see _stands_on): a LOD row at the model's spot would move / turn
    it, or add a second one."""
    from ..core.mapsync import pos_close, rot_close
    p = (mrow.pos_x, mrow.pos_y, mrow.pos_z)
    q = (mrow.rot_x, mrow.rot_y, mrow.rot_z, mrow.rot_w)
    rows = [r.inst for r in doc.rows
            if r.inst is not None and int(r.inst.model_id) == int(lod_id)]
    return bool(rows) and not any(
        pos_close((r.pos_x, r.pos_y, r.pos_z), p, 0.01)
        and rot_close((r.rot_x, r.rot_y, r.rot_z, r.rot_w), q, 1e-4) for r in rows)


def ipl_write(context, objs, *, picked='', dry_run=False, move=False):
    """Add / update the placements of *objs* (+ their LODs).

    *picked* — the IPL chosen in the panel: when set, every object goes there
    (the picked file wins); otherwise each linked object goes to its own IPL.
    *move* (the IPL «Add» buttons): a model linked to another IPL moves — its
    row and LOD leave the old file, or the game would place it twice."""
    reset_copies()
    rep = Report()
    game = scene_game(context)
    picked = norm(picked) if picked else ''
    lodix = LodIndex()
    dffs, lods = ipl_expand(objs, rep)

    # A LOD selected alone → update its linked models' rows (in THEIR files).
    # Copies have no row of their own yet — left alone (as in ipl_remove).
    via_lod = set()
    if lods:
        dff_ids = {id(d) for d in dffs}
        linked = [o for o in _mesh_objects() if o.inu.ipl_uuid
                  and model_type(o)[0] == 'DFF' and not is_copy(o)]
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

    # A copy goes as a new row into its original's IPL (split_copies below
    # clears its link, so remember the file first).
    copy_file = {id(d): _original_file(d) for d in dffs if is_copy(d)}
    if not dry_run:
        n = split_copies(dffs)
        if n:
            rep.msg('INFO', T("{0} копий — добавлены новыми расстановками").format(n))

    groups = {}
    moved, streams = {}, {}     # id → (model, old file, its row there)
    for d in dffs:
        own = ipl_linked_file(d)
        if dry_run and is_copy(d):
            own = ''
        home = own or copy_file.get(id(d), '')
        path = home if id(d) in via_lod else (picked or home)
        if not path:
            rep.msg('ERROR', T("«{0}»: нет своего IPL — выбери файл в панели IPL").format(d.name))
            continue
        if (own and picked and own != picked and id(d) not in via_lod
                and os.path.isfile(own)):
            stream = _stream_prefix(own, context, streams) if move else ''
            if move and not stream:
                moved[id(d)] = (d, own, ipl_anchor(d))
                rep.msg('INFO', T("«{0}»: переносится из {1} в {2}").format(
                    d.name, os.path.basename(own), os.path.basename(picked)))
            elif move:
                rep.msg('WARNING', T("«{0}»: строка оставлена в {1} — на номера "
                                     "строк этого файла ссылаются потоковые IPL "
                                     "({2}*); удаление сдвинет их LOD").format(
                    d.name, os.path.basename(own), stream))
            else:
                rep.msg('WARNING', T("«{0}» была в {1} — записана в выбранный "
                                     "{2}, в старом файле строка осталась").format(
                    d.name, os.path.basename(own), os.path.basename(picked)))
        groups.setdefault(path, []).append(d)

    ide_lods = IdeLods(context)
    move_docs = {}
    written = {}                # id(model) → its new row got a LOD
    for path, batch in groups.items():
        doc = _load_ipl(path, rep)
        if doc is None:
            continue
        fla = any(int(getattr(o.inu, 'real_interior', 0) or 0) for o in batch)
        ed = doc.editor(game=file_game(doc, game), fla=fla or None)
        _reserve_others(ed, path, batch)
        placed = []
        lod_of = {}         # model → its scene LOD mesh that wrote the LOD row
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
            # A model of several meshes: its name, not the main mesh's.
            pn = placement_name(d)
            dinst.model_name, base = pn or dinst.model_name, pn or base
            mrow = None                 # the model's row in the file
            if anchor is not None:
                i = doc.find(anchor)
                if i >= 0 and doc.rows[i].inst is not None:
                    mrow = doc.rows[i].inst
                    _snap_to_row(dinst, mrow)
            if lodo is not None:
                lod = lod_inst_for(d, lodo, base, dinst)
                if lod.model_id <= 0:
                    rep.msg('WARNING', T("«{0}»: у LOD нет Model ID — LOD не "
                                         "записан").format(lodo.name))
                    lod = None
                elif _lod_is_model(lod, dinst):
                    rep.msg('WARNING', T("«{0}»: у LOD «{1}» ID/имя самой модели "
                                         "— взят LOD из IDE").format(
                                             d.name, lodo.name))
                    lod, lodo = None, None
                else:
                    lod_of[id(d)] = lodo
            if lod is None:
                # No LOD mesh in this scene → its definition in the IDE.
                hit = ide_lods.find(d, base)
                if hit is not None:
                    import copy
                    lod = copy.copy(dinst)
                    lod.model_id, lod.model_name = hit[0], hit[1]
                    lod.lod_index = -1
                    if _lod_is_model(lod, dinst):
                        lod = None
                    elif (game in ('III', 'VC') and mrow is not None
                          and _lod_row_apart(doc, mrow, hit[0])):
                        lod = None
                        rep.msg('INFO', T("«{0}»: LOD {1} стоит в IPL не на модели — "
                                          "его строка оставлена как есть").format(
                            d.name, hit[1]))
                    else:
                        rep.msg('INFO', T("«{0}»: LOD взят из IDE — {1} (ID {2}, "
                                          "{3})").format(d.name, hit[1], hit[0],
                                                         os.path.basename(hit[2])))
                        own_ide = ide_linked_file(d)
                        if game == 'VC' and own_ide and own_ide != hit[2]:
                            # VC looks for a LOD's model in the LOD's own IDE only.
                            rep.msg('WARNING', T("«{0}»: LOD {1} — в другом IDE ({2}), "
                                                 "VC их не свяжет").format(
                                d.name, hit[1], os.path.basename(hit[2])))
                        if not dry_run:
                            stamp_lod_ide(d, hit)
            if id(d) in moved and file_game(doc, game) == 'SA':
                # Moving a linked placement into another file keeps the
                # source LOD's offset too (the destination has no row yet).
                from ..core.mapsync.ipl_doc import _lod_moved
                _d, old_path, old_anchor = moved[id(d)]
                if old_path not in move_docs:
                    move_docs[old_path] = _load_ipl(old_path, rep)
                old_doc = move_docs[old_path]
                old_i = old_doc.find(old_anchor) if old_doc is not None else -1
                old_row = old_doc.rows[old_i] if old_i >= 0 else None
                if old_row is not None and old_row.lod is not None and old_row.lod.inst is not None:
                    carried = _lod_moved(old_row.lod.inst, old_row.inst, dinst)
                    if lod is None:
                        lod = carried
                    else:
                        lod.pos_x, lod.pos_y, lod.pos_z = carried.pos_x, carried.pos_y, carried.pos_z
                        lod.rot_x, lod.rot_y, lod.rot_z, lod.rot_w = (
                            carried.rot_x, carried.rot_y, carried.rot_z, carried.rot_w)
            res = ed.place(d, dinst, anchor=anchor, lod=lod)
            placed.append(res)
            _scale_note(d, res._row.style, rep)
        if not _commit(ed, path, rep, dry_run, context):
            continue
        for res in placed:
            rep.add(res.action)
            if res.lod_action in ('add', 'update'):
                rep.add('lod_' + res.lod_action)
            written[id(res.tag)] = res.lod_action in ('add', 'update',
                                                      'unchanged', 'kept')
            if not dry_run:
                stamp_ipl(res.tag, path, res.inst, res.lod_index)
                # A LOD with Model ID 0 was written as model id + 1 — keep
                # that id on the LOD (its IDE status / next Add use it).
                lo = lod_of.get(id(res.tag))
                if (lo is not None and res.lod_inst is not None
                        and int(getattr(lo.inu, 'model_id', 0) or 0) <= 0):
                    lo.inu.model_id = int(res.lod_inst.model_id)

    # Moved into the picked IPL: its old row (and that row's LOD) goes, else
    # the game places the model twice. Only once the new row is written.
    olds = {}
    for key, (d, old, anchor) in moved.items():
        if key in written:
            olds.setdefault(old, []).append((d, anchor))
    for old, items in olds.items():
        doc = _load_ipl(old, rep)
        if doc is None:
            continue
        ed = doc.editor(game=file_game(doc, game))
        _reserve_others(ed, old, [d for d, _a in items])
        results = [ed.remove(d, a) for d, a in items]
        if not _commit(ed, old, rep, dry_run, context):
            continue
        for r in results:
            if r.removed:
                rep.add('moved')
            if r.lod_removed:
                rep.add('lod_removed')
                if not written[id(r.tag)]:
                    rep.msg('WARNING', T("«{0}»: LOD не перенесён — в {1} строка "
                                         "записана без LOD").format(
                        r.tag.name, os.path.basename(picked)))
    return rep


# ── IPL: remove ────────────────────────────────────────────────────────

def _lod_owner_at(lodo, dffs, tol, lodix=None):
    """III/VC: the placement LOD object *lodo* belongs to — its own by
    inu.lod_object, else the nearest model of its base (or, with *lodix*,
    the model the game gives it by name — LODtower ↔ ap_tower, as Add pairs
    them: LodIndex.tail_partners) standing on it (where it is now or its row
    in the file, within *tol*); on a tie the earlier in *dffs*. None when no
    model stands there."""
    base = (model_type(lodo)[1] or '').lower()
    p = tuple(lodo.matrix_world.translation)
    best, best_d = None, tol * tol
    for d in dffs:
        lo = d.inu.lod_object
        if lo is lodo:
            return d
        b = model_type(d)[1] or ''
        if lo is not None or (b.lower() != base and not (
                lodix is not None
                and any(o is lodo for o in lodix.tail_partners(d, b)))):
            continue
        spots = [tuple(d.matrix_world.translation)]
        if d.inu.ipl_uuid:
            spots.append(tuple(d.inu.ipl_last_pos))
        for s in spots:
            d2 = sum((a - b) ** 2 for a, b in zip(s, p))
            if d2 < best_d or (best is None and d2 == best_d):
                best, best_d = d, d2
    return best


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
            e.model_name = placement_name(d) or e.model_name
            a = Anchor(int(d.inu.model_id or 0), e.model_name,
                       (e.pos_x, e.pos_y, e.pos_z), None)
            groups.setdefault(path, []).append((d, a, MATCH_TOL, 'dff'))
    if lods:
        linked = [o for o in _mesh_objects() if o.inu.ipl_uuid
                  and model_type(o)[0] == 'DFF' and not is_copy(o)]
        sel = {id(d) for d in dffs}
        for lodo in lods:
            if game in ('III', 'VC'):
                # No lod_index: partner() pairs by name, one LOD object for
                # every placement → the LOD is the row of the model on it.
                d = _lod_owner_at(lodo, dffs + linked, MATCH_TOL, lodix)
                owners = [d] if d is not None else []
            elif any(lodix.partner(d) is lodo for d in dffs):
                continue        # goes with its model (remove drops the LOD row)
            else:
                owners = lodix.owners(lodo, linked)
            if not owners:
                rep.msg('WARNING', T("«{0}»: LOD без основной модели — выдели "
                                     "основную модель").format(lodo.name))
            for d in owners:
                if id(d) in sel:
                    continue
                path = target or ipl_linked_file(d)
                if path and os.path.isfile(path):
                    groups.setdefault(path, []).append(
                        (d, ipl_anchor(d), None, 'lod'))
                else:
                    rep.msg('WARNING', T("«{0}»: нет IPL-файла").format(d.name))

    streams = {}
    for path, items in groups.items():
        doc = _load_ipl(path, rep)
        if doc is None:
            continue
        stream = (_stream_prefix(path, context, streams)
                  if file_game(doc, game) == 'SA' else '')
        if stream:
            rep.msg('WARNING', T("{0}: строки сохранены — {1}*.ipl ссылаются "
                                 "на их номера; удаление сдвинет LOD "
                                 "потоковых моделей").format(os.path.basename(path), stream))
            continue
        ed = doc.editor(game=file_game(doc, game))
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
        # What goes from this file (confirm dialog). After commit: only then
        # is it known whether a LOD row goes too (unused by other rows).
        n_rm = sum(1 for _o, k, r in results if k == 'dff' and r.removed)
        n_det = sum(1 for _o, k, r in results if k == 'lod' and r._row is not None)
        n_lod = sum(1 for _o, _k, r in results if r.lod_removed)
        if n_rm:
            rep.plan(path, T("удалить расстановок: {0}").format(n_rm))
        if n_det:
            rep.plan(path, T("отвязать LOD: {0}").format(n_det))
        if n_lod:
            rep.plan(path, T("удалить LOD: {0}").format(n_lod))
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
    """IPL row → the object's WORLD placement (the row is written from
    matrix_world, so a parent / delta transform is accounted for); the
    object's scale and rotation mode are kept."""
    from mathutils import Matrix, Quaternion
    q = Quaternion((inst.rot_w, -inst.rot_x, -inst.rot_y, -inst.rot_z))
    # to_matrix() doesn't normalize: 0.7071,0.7071 would shrink the object.
    q = q.normalized() if q.magnitude > 1e-8 else Quaternion()
    mw = obj.matrix_world
    s = mw.to_scale()
    if mw.is_negative:
        s = -s                  # to_scale() is always positive: keep a mirror
    obj.matrix_world = (Matrix.Translation((inst.pos_x, inst.pos_y, inst.pos_z))
                        @ q.to_matrix().to_4x4()
                        @ Matrix.Diagonal((s.x, s.y, s.z, 1.0)))


def _parent_depth(o):
    d, p = 0, getattr(o, 'parent', None)
    while p is not None:
        d, p = d + 1, p.parent
    return d


def ipl_pull(context, objs, files, *, move=True, far=None, clear_lost=False):
    """Link / refresh *objs* against their IPL rows.

    Linked objects: the row is found again by anchor (in the object's own
    file). With *move* the object takes the row's transform.
    Unlinked objects: linked to the nearest free row of their model in *files*
    within 0.5 m. *far* widens that when nothing is that close:
      'nearest' — the nearest free row at any distance (restore coords);
      'unique'  — only if it is the ONE free row of that model and within
                  2 m (verify): a copy far away must not take over another
                  placement's row.
    *clear_lost* drops the link of objects whose row is gone; a linked file
    that is missing or unreadable keeps its links (one warning per file).
    Report counts: synced, linked, lost, skipped."""
    from ..core.mapsync import MATCH_TOL, RELINK_TOL
    reset_copies()
    rep = Report()
    cache = IplCache(rep)
    claimed = {}
    objs = [o for o in objs if o.type == 'MESH' and model_type(o)[0] == 'DFF']
    # A model of several meshes: only its main takes a row, the rest move
    # with it (_followers) — grouped here, before anything moves.
    objs = list({id(m): m for m in map(main_of, objs)}.values())
    # Parents first: a child placed before its parent would move with it.
    objs.sort(key=_parent_depth)
    unlinked = []
    kept = {}                            # missing / unreadable file → links kept
    for o in objs:
        if not o.inu.ipl_uuid or is_copy(o):
            unlinked.append(o)
            continue
        path, i = ipl_locate(o, cache, claimed)
        doc = cache.get(path) if path else None
        if i < 0 or doc is None:
            rep.add('lost')
            if clear_lost:
                if doc is None and path:
                    kept[path] = kept.get(path, 0) + 1
                    continue
                clear_ipl(o)
                if path:
                    rep.msg('WARNING', T("«{0}»: строки нет в {1} (и в {2:g} м) "
                                         "— связь снята").format(
                        o.name, os.path.basename(path), RELINK_TOL))
            else:
                unlinked.append(o)
            continue
        inst = doc.rows[i].inst
        if move:
            for m in [o] + _followers(o):
                apply_inst_transform(m, inst)
        stamp_ipl(o, path, inst, inst.lod_index)
        rep.add('synced')
    for path, n in kept.items():
        rep.msg('WARNING', T("{0}: файла нет или он не читается — связи {1} "
                             "моделей оставлены").format(os.path.basename(path), n))
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
                        r = doc.rows[i].inst
                        d2 = ((r.pos_x - pos[0]) ** 2 + (r.pos_y - pos[1]) ** 2
                              + (r.pos_z - pos[2]) ** 2)
                        if d2 > RELINK_TOL * RELINK_TOL:
                            i = -1       # the one free row is someone else's
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
            for m in [o] + _followers(o):
                apply_inst_transform(m, inst)
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
    * A file that is missing right now is skipped — its links stay (an
      editor re-saving it, a renamed folder); a file deleted for good is
      unlinked by «Проверить IPL».

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
            continue                     # missing right now: links stay
        doc = cache.get(path)
        if doc is None:                  # binary / unreadable: leave as is
            continue
        taken = set()
        misses = []
        # Exact matches first, so a nudged row can't be stolen by a neighbour.
        for o in objs:
            i = doc.find(ipl_anchor(o), exclude=taken)
            if i >= 0:
                taken.add(i)
            else:
                misses.append(o)
        for o in misses:
            i = doc.find(ipl_anchor(o), exclude=taken, tol=RELINK_TOL)
            if i < 0:
                clear_ipl(o)
                ipl_lost += 1
                continue
            taken.add(i)
            inst = doc.rows[i].inst
            stamp_ipl(o, path, inst, inst.lod_index)

    ide_lost = 0
    for path, objs in ide_by_file.items():
        if not os.path.isfile(path):
            continue                     # missing right now: links stay
        try:
            doc = IdeDoc.load(path)
        except OSError:
            continue
        for o in objs:
            inu = o.inu
            mid = int(inu.ide_last_model_id or 0) or int(inu.model_id or 0)
            row = doc.by_id(mid)
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


def lod_owners(lodix, mtype=None):
    """id(LOD mesh) → its model in this scene (LodIndex.partner), the first
    by name — so a LOD selected alone writes the row it gets with its model.
    III/VC: its copies (LODhouse.001) too — the LOD's name there depends on
    its model (lod_model_name)."""
    mtype = mtype or model_type
    out, by_name = {}, {}
    meshes = sorted((o for o in bpy.context.scene.objects
                     if o.type == 'MESH' and hasattr(o, 'inu')),
                    key=lambda o: o.name)
    for d in meshes:
        if mtype(d)[0] != 'DFF':
            continue
        p = lodix.partner(d)
        if p is not None:
            out.setdefault(id(p), d)
            by_name.setdefault(plain_name(p).lower(), d)
    if by_name and scene_game(bpy.context) in ('III', 'VC'):
        for o in meshes:
            d = by_name.get(plain_name(o).lower())
            if d is not None and id(o) not in out and mtype(o)[0] == 'LOD':
                out[id(o)] = d
    return out


def lod_hd_names(objs):
    """III/VC: id(LOD mesh) → its model's name (the *hd* of lod_model_name)
    — its partner among *objs*, else its model in the scene, as «Add» finds
    it (ide_entries). SA: {} — there a LOD's name doesn't depend on it."""
    if scene_game(bpy.context) not in ('III', 'VC'):
        return {}
    lodix, out = LodIndex(), {}
    for d in objs:
        mt, base = model_type(d) if d.type == 'MESH' else (None, '')
        if mt == 'DFF' and base:
            p = lodix.partner(d)
            if p is not None:
                out.setdefault(id(p), base)
    for k, d in lod_owners(lodix).items():
        out.setdefault(k, model_type(d)[1] or '')
    return out


def _ide_entry(o, mt, base, dff, hd=None):
    """The IdeObject «Add» writes for *o*; *dff* — the model of a LOD, *hd* —
    that model's name (None: its mesh's)."""
    from .. import _ide_entry_from_obj, _clean_model_name_ide
    e = _ide_entry_from_obj(o)
    e.draw_distance = ide_draw_distance(o, mt == 'LOD')
    if mt == 'LOD':
        if hd is None:
            hd = _clean_model_name_ide(dff.name) if dff else ''
        e.model_name = lod_model_name(o, base, hd=hd)
        e.model_id = lod_model_id(o, dff)
        # The LOD's own TXD first (vanilla LODs have their own: lod_lan2),
        # then its model's. Draw distance stays its own LOD Dist — the field
        # shown on the LOD (_ide_entry_from_obj already took it).
        own = (getattr(o.inu, 'txd_name', '') or '').strip()
        dff_txd = (getattr(dff.inu, 'txd_name', '') or '').strip() if dff else ''
        e.txd_name = own or dff_txd or _clean_model_name_ide(base)
    return e


def _lod_link_notes(lodo, e, dff, rep, hd=None):
    """III/VC: what keeps the game from pairing the LOD row *e* with its
    model *dff* (named *hd*, None: its mesh's name) — the name (compared from
    the 4th character) or a LOD Dist of 300 and less (only a farther model
    looks for its pair)."""
    from .. import _clean_model_name_ide
    game = scene_game(bpy.context)
    if game not in ('III', 'VC'):
        return
    if hd is None:
        hd = _clean_model_name_ide(dff.name) if dff is not None else ''
    note = lod_name_note(lodo, e.model_name, hd, game)
    if note:
        rep.msg('WARNING', note)
    if float(e.draw_distance) <= 300.0:
        rep.msg('WARNING', T("«{0}»: LOD Dist {1} — III/VC связывают LOD с "
                             "моделью, только если больше 300").format(
            lodo.name, "{:g}".format(float(e.draw_distance))))


def ide_entries(objs, rep):
    """Selection → [(obj, IdeObject, parent DFF or None)]: models + their LOD
    partners, one entry per object (copies of a model collapse onto one row in
    the editor). *parent* is set for a LOD — pulled in by its model, or found
    in the scene when the LOD is selected alone (same row either way). A model
    of several meshes at one spot is one row, its main's (main_of), with the
    model's name, not a mesh's (placement_name)."""
    reset_copies()
    lodix = LodIndex()
    out, seen = [], set()
    dff_of_lod = {}
    owner_of = None
    ordered = []
    for o in objs:
        if o.type != 'MESH':
            continue
        mt, base = model_type(o)
        if mt == 'COL':
            continue
        if mt == 'DFF' and main_of(o) is not o:
            o = main_of(o)
            base = model_type(o)[1] or base
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
        dff = None
        if mt == 'LOD':
            dff = dff_of_lod.get(id(o))
            if dff is None:
                if owner_of is None:
                    owner_of = lod_owners(lodix)
                dff = owner_of.get(id(o))
        hd = (placement_name(dff, ide=True) or None) if dff is not None else None
        e = _ide_entry(o, mt, base, dff, hd)
        if mt == 'DFF':
            e.model_name = placement_name(o, ide=True) or e.model_name
        if e.model_id <= 0:
            rep.msg('ERROR', T("«{0}»: Model ID = 0 — не записана").format(o.name))
            continue
        if mt == 'LOD':
            _lod_link_notes(o, e, dff, rep, hd)
        out.append((o, e, dff))
    return out


def ide_write(context, objs, *, picked='', dry_run=False):
    rep = Report()
    game = scene_game(context)
    picked = norm(picked) if picked else ''
    from ..core.fs_ci import path_key
    entries = ide_entries(objs, rep)
    models = [o for o, _e, _parent in entries]
    models += [parent for _o, _e, parent in entries if parent is not None]
    other_ides = [(path_key(p), p, _ide_names(p)[0])
                  for p in _known_ides(models, game, context=context)]
    groups = {}
    for o, e, parent in entries:
        own = ide_linked_file(o)
        path = picked or own or (ide_linked_file(parent) if parent else '')
        if not path:
            rep.msg('ERROR', T("«{0}»: нет своего IDE — выбери файл в панели IDE").format(o.name))
            continue
        target_key = path_key(path)
        for source_key, source, names in other_ides:
            if source_key == target_key:
                continue
            found = bool(names.get(e.model_name.lower()))
            # A renamed linked model still owns its old row. A copied
            # model given another ID must not inherit that old identity.
            if (not found and source == own
                    and int(o.inu.ide_last_model_id or 0) == int(e.model_id)):
                found = any(mid == int(e.model_id) for mid, _name in
                            names.get((o.inu.ide_last_name or '').lower(), ()))
            if found:
                rep.msg('WARNING', T("«{0}»: модель уже существует в другом IDE "
                                     "({1}); старая строка остаётся").format(o.name, source))
        groups.setdefault(path, []).append((o, e))
    from ..core.mapsync import IdeDoc
    for path, items in groups.items():
        try:
            doc = IdeDoc.load(path)
        except OSError as ex:
            rep.msg('ERROR', f"{os.path.basename(path)}: {ex}")
            continue
        ed = doc.editor(game=doc.file_game(game))
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
                # A LOD with Model ID 0 went in as model id + 1: keep it.
                if int(getattr(r.tag.inu, 'model_id', 0) or 0) <= 0:
                    r.tag.inu.model_id = int(r.entry.model_id)
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
        try:
            doc = IdeDoc.load(path)
        except OSError as ex:
            rep.msg('ERROR', f"{os.path.basename(path)}: {ex}")
            continue
        ed = doc.editor(game=doc.file_game(game))
        done = []
        for o, e in items:
            same = ide_linked_file(o) == path
            ok = ed.remove(o, int(e.model_id), e.model_name,
                           anchor_name=(o.inu.ide_last_name or '') if same else '')
            done.append((o, ok))
        n_rm = sum(1 for _o, ok in done if ok)
        if n_rm:
            rep.plan(path, T("удалить определений: {0}").format(n_rm))
        if not _commit(ed, path, rep, dry_run, context):
            continue
        for o, ok in done:
            if ok:
                rep.add('removed')
                if not dry_run:
                    clear_ide(o)
    return rep


def ide_sync_from_file(objs, ide_files):
    """IDE → objects: Model ID, draw distance, TXD, flags («Sync from IDE»).

    The model's own linked IDE first; otherwise every file of *ide_files*. A
    name found in several IDEs with different ids is not linked (message),
    unless one of them has the object's Model ID (core.mapsync.ide_match).
    A changed Model ID is reported. A model whose own IDE is missing or
    unreadable keeps its link unless its id is found elsewhere (one warning
    per file). Returns ``(linked, skipped, rep)``."""
    from ..core.ide import read_ide
    from ..core.mapsync.ide_match import build_index, match_ide_row
    from .. import _clean_model_name_ide
    rep = Report()
    parsed, owns = {}, {}

    def rows(fp):
        k = norm(fp)
        if k not in parsed:
            try:
                ide = read_ide(fp)
                parsed[k] = list(ide.objects) + list(ide.anims)
            except Exception:
                parsed[k] = None
        return parsed[k]

    def own_index(fp):
        if fp not in owns:
            r = rows(fp) if os.path.isfile(fp) else None
            owns[fp] = build_index([(fp, r)]) if r is not None else None
        return owns[fp]

    index = build_index((fp, rows(fp)) for fp in ide_files)
    linked = skipped = 0
    kept = {}                            # own IDE missing / unreadable → links kept
    for obj in objs:
        inu = getattr(obj, 'inu', None)
        if inu is None:
            skipped += 1
            continue
        is_lod = model_type(obj)[0] == 'LOD'
        mid = int(inu.model_id or 0)
        own = ide_linked_file(obj)
        own_ix = own_index(own) if own else None
        hit, ambiguous = match_ide_row(
            own_ix, index, _clean_model_name_ide(obj.name),
            inu.ide_last_name, inu.ide_last_model_id, mid, is_lod)
        if own and own_ix is None and (
                hit is None or (mid > 0 and int(hit[0].model_id) != mid)):
            # Its own IDE is gone right now (renamed folder, moved .blend):
            # a row of another id elsewhere (vanilla «bench») must not take
            # the model over. Same model (same id) in another file — relink.
            kept[own] = kept.get(own, 0) + 1
            skipped += 1
            continue
        if hit is None:
            skipped += 1
            if ambiguous == 'id':
                rep.msg('WARNING', T("«{0}»: ID {1} есть в нескольких IDE под "
                                     "разными именами — не связана").format(
                    obj.name, mid))
            elif ambiguous:
                rep.msg('WARNING', T("«{0}»: найдена в нескольких IDE с разными "
                                     "ID — не связана").format(obj.name))
            continue
        e, fp = hit
        # Файл — источник истины: Model ID тоже из IDE (смена — в отчёт).
        eid = int(e.model_id)
        if eid > 0 and eid != mid:
            if mid > 0:
                rep.msg('INFO', T("«{0}»: Model ID {1} → {2} (из {3})").format(
                    obj.name, mid, eid, os.path.basename(fp)))
            inu.model_id = eid
        # У LOD дистанция из IDE — это его LOD Dist.
        dd = float(e.draw_distance)
        if is_lod:
            inu.lod_draw_distance = dd
        else:
            inu.draw_distance = dd
        inu.txd_name = str(e.txd_name or '')
        inu.ide_flags = int(e.flags)
        stamp_ide(obj, norm(fp), e)
        linked += 1
    for path, n in kept.items():
        rep.msg('WARNING', T("{0}: файла нет или он не читается — связи {1} "
                             "моделей оставлены").format(os.path.basename(path), n))
    return linked, skipped, rep


# ── panel status of the active object ─────────────────────────────────
#
# Compared with what «Add» would write now (TXD falling back to the model
# name, flags translated to the scene's game, a LOD's id = model id + 1,
# rotation too) — raw props gave false «изменено» / missed a rotated model.
# Returns (Russian text for T(), its {0} argument, icon, …).

def model_type_cached(obj):
    from ..tools.model_utils import get_model_type_cached
    return get_model_type_cached(obj)


def ide_status(obj):
    """(text, arg, icon, id_changed) of the IDE row."""
    inu = obj.inu
    mt, base = model_type_cached(obj)
    dff = None
    # A LOD's model matters only for a missing id / TXD — skip the scene
    # scan otherwise (this runs on every redraw).
    if mt == 'LOD' and (int(inu.model_id or 0) <= 0
                        or not (inu.txd_name or '').strip()):
        dff = lod_owners(LodIndex(model_type_cached),
                         model_type_cached).get(id(obj))
    e = _ide_entry(obj, mt, base, dff)
    last = int(inu.ide_last_model_id or 0)
    if inu.ide_linked and last > 0 and int(e.model_id) != last:
        return "Не в IDE — сменился ID (был {0})", last, 'DUPLICATE', True
    if not inu.ide_linked or int(e.model_id) <= 0:
        return "Не в IDE", '', 'RADIOBUT_OFF', False
    diff = []
    if abs(float(e.draw_distance) - float(inu.ide_last_draw_distance)) > 1e-3:
        diff.append("DrawDist")
    if (e.txd_name or '') != (inu.ide_last_txd_name or ''):
        diff.append("TXD")
    if int(e.flags) != int(inu.ide_last_flags):
        diff.append("Flags")
    if diff:
        return "В IDE, изменено: {0}", ", ".join(diff), 'ERROR', False
    return ("В IDE ({0})", os.path.basename(inu.ide_target_file or '') or '?',
            'CHECKMARK', False)


def ipl_status(obj):
    """(text, arg, icon) of the IPL row."""
    from ..core.mapsync import inst_drifted
    inu = obj.inu
    if not inu.ipl_uuid:
        # A LOD has no link of its own: its row goes with the model's.
        if model_type_cached(obj)[0] == 'LOD':
            return "LOD — пишется вместе с моделью", '', 'LINKED'
        return "Не в IPL", '', 'RADIOBUT_OFF'
    if is_copy(obj, cached=False):
        return "Копия — добавится новым инстансом", '', 'DUPLICATE'
    if inst_drifted(ipl_inst_of(obj), ipl_anchor(obj)):
        return "В IPL, координаты разошлись", '', 'ERROR'
    return ("В IPL ({0})", os.path.basename(inu.ipl_target_file or '') or '?',
            'CHECKMARK')


# ── report text ────────────────────────────────────────────────────────

def summary(prefix, rep):
    c = rep.counts
    parts = []
    if c.get('add'):
        s = T("добавлено {0}").format(c['add'])
        parts.append(s)
    if c.get('update'):
        parts.append(T("обновлено {0}").format(c['update']))
    if c.get('moved'):
        parts.append(T("перенесено из другого файла {0}").format(c['moved']))
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
    Subclasses implement ``_run(context, dry_run) -> Report``.

    ``_always_confirm`` (the trash buttons): rows are never deleted without
    the question — the dialog lists per file what goes (``Report.plan``)."""

    _problem_lines = []
    _always_confirm = False
    _header = ''
    _question = ''

    def invoke(self, context, event):
        cls = type(self)
        try:
            rep = self._run(context, True)
        except Exception as ex:                             # noqa: BLE001
            if cls._always_confirm:
                # No list to show — don't delete without asking.
                self.report({'ERROR'}, str(ex))
                return {'CANCELLED'}
            return self.execute(context)
        probs = [t for lvl, t in rep.problems()]
        lines = ([f"{os.path.basename(p)}: {'; '.join(w)}"
                  for p, w in sorted(rep.touch.items())]
                 if cls._always_confirm else [])
        if not probs and not lines:
            return self.execute(context)
        shown = probs[:12] + (
            [T("… ещё {0}").format(len(probs) - 12)] if len(probs) > 12 else [])
        if lines:
            cls._header = T("Строки будут УДАЛЕНЫ из файлов:")
            cls._problem_lines = lines[:12] + (
                [T("… ещё {0}").format(len(lines) - 12)] if len(lines) > 12
                else []) + (['', T("Проблемы:")] + shown if shown else [])
            cls._question = T("Удалить эти строки?")
            if bpy.app.version >= (4, 2, 0):
                # Deleting: Enter = Cancel (Max defaults to «No» too).
                return context.window_manager.invoke_props_dialog(
                    self, width=520, confirm_text=T("Удалить"),
                    cancel_default=True)
        else:
            cls._header = T("Перед записью найдены проблемы:")
            cls._problem_lines = shown
            cls._question = T("Остальное будет записано. Продолжить?")
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=type(self)._header, icon='ERROR')
        for line in type(self)._problem_lines:
            col.label(text=line)
        col.separator()
        col.label(text=type(self)._question)
