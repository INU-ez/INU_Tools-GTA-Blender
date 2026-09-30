# INU_tools.tools.map_export — unified scene → IPL + IDE + (optional) DFF / COL / TXD
#
# Orchestrates the individual format exporters so a user can publish a
# whole city district with one click. Per-object IDs, draw distance and
# TXD names are taken from `obj.inu` custom properties (same props that
# back the separate IDE/IPL exports).
#
# Auto-split: for very large scenes (50k+ DFF objects) a single district
# is impractical (long IPL files, monolithic TXD). Auto-split mode bins
# DFFs by their XY origin into a grid of `cell_size`-meter cells; each
# non-empty cell becomes its own subdirectory with its own IDE/IPL/COL/TXD.
# Game-side this just means loading several IPLs instead of one — engine
# behavior is identical.
#
# Every placement (copy) of a model is an IPL row of its own; the model's
# DFF, LOD (<LOD>.dff + its own IDE row and IPL rows), COL and TXD are
# written once, in the cell of its first placement. Models without a
# Model ID get one from the ID Manager's active preset (all or nothing,
# undoable). Files already in the folder are listed and asked about; a
# .txd is merged. Binary IPL (SA) is the game's pair: text <cell>.ipl
# with the LOD rows + binary <cell>_stream0.ipl with the models.

import math
import os
import re
from dataclasses import dataclass

import bpy

from .model_utils import get_model_type, _strip_dup_suffix
from .compat import safe_icon, inu_icon
from .. import T
from typing import Dict, List, Optional, Set, Tuple


# ──────────────────────────── grouping ────────────────────────────────

@dataclass
class MapGroup:
    """One placement (``dff``) of model ``base`` — the unit the split
    planners below bin into cells."""
    base: str
    # Forward-string refs — без future-import dataclass eager-eval'нул бы
    # bpy.types.Object на class-creation, что роняет unit-тесты со
    # стабленным bpy. Аннотации кокласса всё равно не используются как
    # runtime-типы (dataclass только читает имена полей).
    dff: "bpy.types.Object"
    lod: 'Optional["bpy.types.Object"]' = None
    col_objects: list = None   # list of COL/SHA meshes

    def __post_init__(self):
        if self.col_objects is None:
            self.col_objects = []


@dataclass
class MapModel:
    """One model of the export. Every placement (copy) of it is an IPL row
    of its own cell; its DFF, LOD, COL, TXD and IDE rows are written once,
    in the cell of its first placement (``home``)."""
    key: str                                  # model name, lower case
    name: str                                 # as in the IDE row / <name>.dff
    home: "bpy.types.Object"
    placements: list = None
    lod: 'Optional["bpy.types.Object"]' = None
    lod_name: str = ''
    lod_objs: list = None                     # the LOD + its copies (one Model ID)
    lod_own: bool = True                      # False — another model writes this LOD
    txd: str = ''
    lod_txd: str = ''
    cols: list = None                         # COL / SHA meshes + spheres / boxes — one collision

    def __post_init__(self):
        if self.placements is None:
            self.placements = [self.home]
        if self.lod_objs is None:
            self.lod_objs = [self.lod] if self.lod is not None else []
        if self.cols is None:
            self.cols = []


def _names(names, n: int = 8) -> str:
    more = len(names) - n
    return ", ".join(names[:n]) + (" " + T("… ещё {0}").format(more) if more > 0 else "")


def _pick_col_group(cands, home) -> list:
    """The collision of one model out of the scene's COL / SHA meshes with
    its name: the meshes standing together at one spot (a COL with its SHA,
    a collision split into several meshes) — never every copy (N overlapping
    meshes in the .col). The spot of ``home`` wins; else the spot of an
    undecorated mesh (house_COL, not house_COL.001); else the smallest name."""
    if not cands:
        return []

    def spot(o):
        t = o.matrix_world.translation
        return (round(t.x, 3), round(t.y, 3), round(t.z, 3))

    spots: Dict[tuple, list] = {}
    for o in cands:
        spots.setdefault(spot(o), []).append(o)
    here = spots.get(spot(home))
    if here:
        return here
    groups = list(spots.values())
    plain = [g for g in groups if any(o.name == _strip_dup_suffix(o.name) for o in g)]
    return min(plain or groups, key=lambda g: min(o.name for o in g))


# «<model>_sphere_N» / «<model>_box_N» — the names col_import gives a
# model's spheres / boxes.
_PRIM_NAME = re.compile(r'(.+)_(?:sphere|box)_\d+', re.IGNORECASE)


def _col_prim_index(objects, col_ids):
    """The scene's sphere / box empties (not a vehicle's frame dummy):
    ({id(COL / SHA mesh): its children}, {model (lower): loose ones}).
    A child of a collision mesh is that mesh's (Import Map parents them to
    it); the rest count by name, «.001» left out — another import's copy
    (Import COL leaves them loose, a model of spheres / boxes only too)."""
    by_parent: Dict[int, list] = {}
    by_name: Dict[str, list] = {}
    empties = [o for o in objects if o.type == 'EMPTY']
    if not empties:
        return by_parent, by_name
    from ..ops.dff_export import _is_col_primitive_empty
    for o in empties:
        if not _is_col_primitive_empty(o):
            continue
        if o.parent is not None and id(o.parent) in col_ids:
            by_parent.setdefault(id(o.parent), []).append(o)
            continue
        hit = _PRIM_NAME.fullmatch(o.name)
        if hit:
            by_name.setdefault(hit.group(1).lower(), []).append(o)
    return by_parent, by_name


def collect_map_models(context, objects):
    """Selection → (models {key: MapModel} in first-placement order,
    placements [MapGroup(base=model key, dff=placement)], notes).

    Every DFF mesh is a placement; copies (house, house.001) are one model.
    A mesh some model points at as its LOD (``inu.lod_object`` — a LOD with
    a plain name) is that LOD, not a placement. A model's LOD comes from the
    scene even when it isn't selected (it travels with its model, as in Add
    to IDE / IPL); a LOD selected without its model is left out with a note.
    Collision — the scene's COL / SHA meshes with the model's name and their
    spheres / boxes (a model of spheres / boxes only has a collision too)."""
    from ..ops.ipl_export import _clean_model_name
    from ..ops.map_link import LodIndex, lod_model_name
    notes = []
    types, lod_refs = {}, set()
    for o in context.scene.objects:
        if o.type != 'MESH':
            continue
        types[id(o)] = (o, get_model_type(o))
        ref = getattr(getattr(o, 'inu', None), 'lod_object', None)
        if ref is not None and ref is not o:
            lod_refs.add(id(ref))

    def mtype(o):
        hit = types.get(id(o))
        return hit[1] if hit is not None else get_model_type(o)

    models: Dict[str, MapModel] = {}
    placements, lone, seen = [], [], set()
    for o in objects:
        if o.type != 'MESH' or id(o) in seen:
            continue
        seen.add(id(o))
        mt = mtype(o)[0]
        if mt == 'DFF' and id(o) not in lod_refs:
            name = _clean_model_name(o.name)
            m = models.get(name.lower())
            if m is None:
                models[name.lower()] = MapModel(key=name.lower(), name=name, home=o)
            else:
                m.placements.append(o)
            placements.append(MapGroup(base=name.lower(), dff=o))
        elif mt in ('DFF', 'LOD'):
            lone.append(o)

    # LOD — one per model (the partner of its first placement, as Add to
    # IPL finds it; each placement gets a LOD row). A LOD several models
    # share is written once, by the first. The copies' own pointers and
    # the scene's LOD meshes of the model's name are its LOD's copies.
    lodix = LodIndex()
    used, first = set(), {}
    # The ID each model keeps (its copies' smallest): a «LOD» carrying one
    # is that model (Shift+D renamed to LODfoo), and as the LOD's ID it
    # would give the IDE two rows with one ID.
    final = {}
    for m in models.values():
        ids = [int(p.inu.model_id) for p in m.placements if p.inu.model_id > 0]
        if ids:
            final.setdefault(min(ids), m.name)

    def twin_of(lo):
        return final.get(int(getattr(lo.inu, 'model_id', 0) or 0))

    for m in models.values():
        m.txd = (getattr(m.home.inu, 'txd_name', '') or '').strip() or m.name
        partners = [lo for lo in (getattr(p.inu, 'lod_object', None) for p in m.placements)
                    if lo is not None and lo.type == 'MESH']
        partners += lodix.by_base.get(m.key, [])
        # III/VC: a placement's LOD by the game's name rule (LODtower ↔
        # ap_tower) — the copy standing on it.
        if lodix.by_tail:
            partners += [lo for lo in map(lodix.partner, m.placements)
                         if lo is not None and all(lo is not x for x in partners)]
        used.update(id(lo) for lo in partners)
        lod = partners[0] if partners and partners[0] is m.home.inu.lod_object else None
        lod = lod or lodix.partner(m.home) or next(iter(partners), None)
        if lod is None:
            continue
        # Its name for THIS model (III/VC pair by name: house → LODse).
        lod_name = lod_model_name(lod, mtype(lod)[1] or m.name, hd=m.name)
        if lod_name.lower() == m.key or twin_of(lod):
            # Shift+D of the model renamed to LODfoo: a second row with the
            # model's ID / position crashes the game (see ipl_export dedupe).
            notes.append(('WARNING', T("«{0}»: у LOD «{1}» ID/имя самой модели "
                                       "— LOD пропущен").format(twin_of(lod) or m.name,
                                                                lod.name)))
            continue
        owner = first.setdefault(lod_name.lower(), m)
        m.lod, m.lod_name, m.lod_own = owner.lod or lod, lod_name, owner is m
        m.lod_txd = (getattr(m.lod.inu, 'txd_name', '') or '').strip() or m.txd
        if owner is m:
            m.lod_objs = []
        have = {id(lo) for lo in owner.lod_objs}
        for lo in [lod] + partners:
            if (lo is not None and id(lo) not in have and lod_model_name(
                    lo, mtype(lo)[1] or m.name, hd=m.name).lower() == lod_name.lower()):
                have.add(id(lo))
                if twin_of(lo):
                    notes.append(('WARNING', T("«{0}»: у LOD «{1}» ID/имя самой модели "
                                               "— LOD пропущен").format(twin_of(lo), lo.name)))
                    continue
                owner.lod_objs.append(lo)
        # One LOD per model: a copy pointing at a LOD of another name gets
        # the model's LOD in its row — say so instead of dropping it quietly.
        alien = []
        for p in m.placements:
            lo = getattr(p.inu, 'lod_object', None)
            if (lo is not None and lo.type == 'MESH' and lod_model_name(
                    lo, mtype(lo)[1] or m.name, hd=m.name).lower() != lod_name.lower()):
                alien.append(f"{p.name} → {lo.name}")
        if alien:
            notes.append(('WARNING', T("«{0}»: свой LOD у копий не взят ({1}) — у всех "
                                       "копий LOD «{2}»").format(m.name, _names(alien),
                                                                m.lod.name)))
    lone = [o.name for o in lone if id(o) not in used]
    if lone:
        notes.append(('WARNING', T("LOD без своей модели в экспорте — не "
                                   "экспортирован: {0}").format(_names(lone))))

    col_idx: Dict[str, list] = {}
    skip = {id(g.dff) for g in placements} | used
    for oid, (o, (mt, base)) in types.items():
        if mt == 'COL' and base and oid not in skip:
            col_idx.setdefault(base.lower(), []).append(o)
    by_parent, by_name = _col_prim_index(
        context.scene.objects, {oid for oid, (_o, (mt, _b)) in types.items() if mt == 'COL'})
    for m in models.values():
        group = _pick_col_group(col_idx.get(m.key, []), m.home)
        # + spheres / boxes, after the meshes: col_export measures them
        # from the COL mesh passed with them. Those of a COL copy left out
        # above stay out with it.
        m.cols = (group + [p for o in group for p in by_parent.get(id(o), ())]
                  + by_name.get(m.key, []))
    return models, placements, notes


# ──────────────────────────── auto-split grid ─────────────────────────

def compute_grid_cells(groups: List[MapGroup], cell_size: float
                       ) -> Dict[Tuple[int, int], List[MapGroup]]:
    """Bin map groups by XY cell index (grid origin = world (0,0)).

    Cell index for a group is taken from the DFF object's world origin.
    LOD/COL members travel with their DFF — they are not assigned
    independently. Returns a dict keyed by (cx, cy).
    """
    if cell_size <= 0:
        return {(0, 0): list(groups)}
    cells: Dict[Tuple[int, int], List[MapGroup]] = {}
    for g in groups:
        loc = g.dff.matrix_world.translation
        cx = int(math.floor(loc.x / cell_size))
        cy = int(math.floor(loc.y / cell_size))
        cells.setdefault((cx, cy), []).append(g)
    return cells


def format_cell_name(base_name: str, cx: int, cy: int) -> str:
    """Return a filesystem-safe sub-district name for a grid cell.

    Negative indices use 'm' (minus) prefix so the name does not start
    with a dash, which some tools/IPL parsers dislike.
    """
    def _fmt(n: int) -> str:
        return f"m{abs(n)}" if n < 0 else f"{n}"
    return f"{base_name}_x{_fmt(cx)}_y{_fmt(cy)}"


# ──────────────────────────── adaptive grid (quadtree) ────────────────

def compute_adaptive_cells(groups: List[MapGroup], *,
                           max_per_cell: int = 200,
                           min_cell_size: float = 16.0
                           ) -> Dict[tuple, List[MapGroup]]:
    """Density-aware quadtree subdivision: dense regions get small cells,
    sparse regions stay one big cell, every leaf cell holds at most
    ``max_per_cell`` DFFs (best-effort — see floor below).

    Starts with one cell covering the world-XY bbox of all groups and
    recursively splits 2×2 any cell exceeding ``max_per_cell``. Uses
    the DFF object's world-origin XY for binning; LOD/COL members
    travel with their DFF (same contract as :func:`compute_grid_cells`).

    Two safety floors prevent runaway recursion:

    * ``min_cell_size`` — cell side length below which we stop splitting
      even if the cell is over budget. Protects against pathological
      cases where many DFFs share an XY origin (e.g. stacked vertical
      buildings).
    * Implicit depth — cells are keyed by a tuple of quadrant indices
      ``(0=SW, 1=SE, 2=NW, 3=NE)`` so the path encodes the recursion
      history. The ``min_cell_size`` floor caps depth around
      ``log2(world_extent / min_cell_size)``.

    Returns a dict keyed by quadrant-path tuples (e.g. ``(0, 1, 3)`` for
    «SW → SE → NE» three subdivisions deep). The empty tuple ``()``
    means a single, unsplit cell holding everything — happens when the
    population fits in ``max_per_cell`` from the start.
    """
    if not groups:
        return {}

    locs = [g.dff.matrix_world.translation for g in groups]
    xs = [loc.x for loc in locs]
    ys = [loc.y for loc in locs]
    # Pad the bbox slightly so points exactly on the max edge stay
    # strictly inside the cell after midpoint splits (otherwise they
    # could escape into a non-existent neighbour cell on the boundary).
    pad = max(0.5, (max(xs) - min(xs) + max(ys) - min(ys)) * 1e-6)
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad

    cells: Dict[tuple, List[MapGroup]] = {}

    def _split(g_list, x0, x1, y0, y1, path):
        cell_size = min(x1 - x0, y1 - y0)
        if (len(g_list) <= max_per_cell
                or cell_size <= min_cell_size):
            cells[path] = g_list
            return
        xm = (x0 + x1) * 0.5
        ym = (y0 + y1) * 0.5
        buckets = [[], [], [], []]
        for g in g_list:
            loc = g.dff.matrix_world.translation
            qx = 1 if loc.x >= xm else 0
            qy = 1 if loc.y >= ym else 0
            buckets[qy * 2 + qx].append(g)
        for q, sub in enumerate(buckets):
            if not sub:
                continue
            qx = q & 1
            qy = (q >> 1) & 1
            sub_x0 = xm if qx else x0
            sub_x1 = x1 if qx else xm
            sub_y0 = ym if qy else y0
            sub_y1 = y1 if qy else ym
            _split(sub, sub_x0, sub_x1, sub_y0, sub_y1, path + (q,))

    _split(list(groups), x0, x1, y0, y1, ())
    return cells


def format_adaptive_cell_name(base_name: str, path: tuple) -> str:
    """Encode a quadtree path as a filesystem-safe district suffix.

    The empty path (single root cell) returns the bare ``base_name`` so
    a small scene that doesn't need subdivision doesn't sprout a noisy
    ``_q0`` directory. Otherwise the suffix is ``_q`` followed by the
    quadrant indices joined: ``_q0123`` means «SW → SE → NW → NE».
    """
    if not path:
        return base_name
    return f"{base_name}_q{''.join(str(q) for q in path)}"


def _build_top_collection_lookup(scene) -> dict:
    """Map every collection name in the scene to its topmost user
    collection (the one directly under ``scene.collection``).

    Blender's data API does not expose a parent pointer on
    :class:`bpy.types.Collection`, so we walk down once from the scene
    root and remember which top-level branch each descendant belongs
    to. The result is keyed by collection *name* — collection refs
    are tracked separately by Blender so identity-keying is unsafe
    across operator invocations.
    """
    top_map: dict = {}

    def _walk(top, current):
        top_map[current.name] = top
        for child in current.children:
            _walk(top, child)

    for top in scene.collection.children:
        _walk(top, top)
    return top_map


def compute_collection_cells(groups: List[MapGroup], scene
                             ) -> Dict[str, List[MapGroup]]:
    """Bin map groups by the name of their topmost user collection.

    Picks each DFF object's first :attr:`bpy.types.Object.users_collection`
    membership (Blender's «main collection» order); then maps that
    collection to its top-level ancestor via
    :func:`_build_top_collection_lookup`. Groups whose DFF lives only
    in the scene root collection (or in no collection at all) land
    under the bin name ``"unsorted"``.

    Prints a one-line summary to the system console — handy for
    diagnosing «everything fell into one bucket» issues without
    sprinkling debug calls in the operator.
    """
    top_map = _build_top_collection_lookup(scene)
    cells: Dict[str, List[MapGroup]] = {}
    for g in groups:
        bucket: Optional[str] = None
        for coll in getattr(g.dff, 'users_collection', ()) or ():
            top = top_map.get(coll.name)
            if top is not None:
                bucket = top.name
                break
        if bucket is None:
            bucket = "unsorted"
        cells.setdefault(bucket, []).append(g)
    return cells


# ──────────────────────────── selection resolver ──────────────────────

def _gather_outliner_selected_collections(context) -> list:
    """Return all Collections currently selected in any outliner area.

    ``context.selected_ids`` only reports the outliner's selection when
    *that outliner* is the active region — so calling it from a sidebar
    panel button (or after a file dialog stole focus) often returns just
    the active collection, missing the other Ctrl-clicked ones. We work
    around that by scanning every screen area, locating outliners, and
    re-reading ``selected_ids`` under each one's :func:`temp_override`.

    Filters outliners to ``display_mode == 'VIEW_LAYER'`` so a Properties
    Editor's tiny outliner pane doesn't steal the selection.

    Returns a deduplicated list preserving outliner order.
    """
    found: list = []
    seen: set = set()

    def _push(coll):
        key = coll.name
        if key not in seen:
            seen.add(key)
            found.append(coll)

    # Direct read first — costs nothing and works when the operator
    # was triggered with the outliner as active region.
    try:
        for did in context.selected_ids or ():
            if isinstance(did, bpy.types.Collection):
                _push(did)
    except AttributeError:
        pass

    # Then sweep every outliner on every open window so Ctrl-click
    # selections survive the «click sidebar button» workflow. We pass
    # both ``area`` and ``region`` to ``temp_override`` — without the
    # WINDOW region some Blender builds skip the outliner-specific
    # context callback and ``selected_ids`` ends up empty even though
    # the area is correctly overridden.
    try:
        windows = list(context.window_manager.windows)
    except Exception:
        windows = []

    for win in windows:
        screen = getattr(win, 'screen', None)
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != 'OUTLINER':
                continue
            space = area.spaces.active if area.spaces else None
            display_mode = getattr(space, 'display_mode', None)
            if display_mode and display_mode != 'VIEW_LAYER':
                continue
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            try:
                kwargs = {'window': win, 'area': area}
                if region is not None:
                    kwargs['region'] = region
                with context.temp_override(**kwargs):
                    for did in bpy.context.selected_ids or ():
                        if isinstance(did, bpy.types.Collection):
                            _push(did)
            except (AttributeError, RuntimeError, TypeError):
                pass

    return found


def _resolve_export_objects(context) -> list:
    """Pick the mesh objects to export based on the user's outliner state.

    Resolution order:
      1. **Two or more collections selected in the outliner** — gather
         their nested meshes via ``Collection.all_objects``. This wins
         over viewport selection so «select 2 collections in outliner +
         click Export Map in sidebar» does the obvious thing.
      2. Currently selected mesh objects (``context.selected_objects``).
      3. Single selected collection (or active collection fallback) —
         gather its meshes.
      4. Last resort: every mesh in the scene.
    """
    outliner_colls = _gather_outliner_selected_collections(context)

    def _gather(colls):
        gathered: Dict[int, bpy.types.Object] = {}
        for coll in colls:
            for obj in coll.all_objects:
                if obj.type == 'MESH':
                    gathered[id(obj)] = obj
        return list(gathered.values())

    # ── (1) Multi-collection selection wins ──
    if len(outliner_colls) >= 2:
        gathered = _gather(outliner_colls)
        if gathered:
            return gathered

    # ── (2) Viewport-selected meshes ──
    selected = [o for o in context.selected_objects if o.type == 'MESH']
    if selected:
        return selected

    # ── (3) Single outliner collection or active collection fallback ──
    fallback_colls = list(outliner_colls)
    if not fallback_colls:
        active = getattr(context, 'collection', None)
        scene_root = context.scene.collection if context and context.scene else None
        if active is not None and active is not scene_root:
            fallback_colls.append(active)

    if fallback_colls:
        gathered = _gather(fallback_colls)
        if gathered:
            return gathered

    # ── (4) Final fallback ──
    return [o for o in context.scene.objects if o.type == 'MESH']


# ──────────────────────────── ID helpers ──────────────────────────────

def assign_ids(models, allocate, skip):
    """Model IDs for Export Map (bpy-free — tested without Blender).

    ``models`` — [(key, name, have, prefer, own)] in export order (a model,
    then its LOD): ``have`` = the Model IDs its objects (copies) carry;
    ``prefer`` = the ID a LOD would like (its model's + 1, or ``own`` —
    the ID its own IDE row already holds) or None. ``skip`` = IDs in use
    (scene, IDE files); a ``prefer`` in it is dropped unless ``own``.
    ``allocate(requests, skip)`` → [ID] for [(name, prefer)] from the ID
    Manager — all or nothing (None).

    Copies share one ID: the one they carry (the smallest, with a note, if
    they differ), else a new one. Returns (ids {key: ID}, notes, left):
    ``left`` = names without an ID when the preset ran out — then nothing
    was allocated and ``ids`` is empty."""
    ids, notes, need = {}, [], []
    skip = set(skip)
    for _k, _n, have, _p, _o in models:
        skip.update(i for i in have if i > 0)
    for key, name, have, prefer, own in models:
        have = sorted({i for i in have if i > 0})
        if not have:
            need.append((key, name, prefer, own))
            continue
        ids[key] = have[0]
        if len(have) > 1:
            notes.append(('WARNING', T("«{0}»: у копий разные ID ({1}) — взят {2}").format(
                name, ", ".join(str(i) for i in have), have[0])))
    if not need:
        return ids, notes, []
    got = allocate([(n, p if p is not None and (own or p not in skip) else None)
                    for _k, n, p, own in need], skip)
    if got is None:
        return {}, notes, [n for _k, n, _p, _o in need]
    for (key, name, prefer, _own), nid in zip(need, got):
        ids[key] = nid
        if prefer is not None and nid != prefer:
            notes.append(('INFO', T("«{0}»: ID {1} недоступен — LOD получил {2}").format(
                name, prefer, nid)))
    return ids, notes, []


def _ide_file_ids(context) -> Dict[str, Set[int]]:
    """{IDE path: its Model IDs} for the IDE files in use — the IDE box,
    «IDE для экспорта», the IDE each scene model is linked to. A new ID
    must not repeat one of them: a second row with the same ID overrides
    the model in the game."""
    from ..ops.map_link import norm, ide_linked_file
    from ..core.ide import read_ide
    s = context.scene.inu_settings
    paths = {norm(p) for p in ([getattr(s, 'gtatools_ide_path', '')]
                               + [it.path for it in getattr(s, 'gtatools_ide_sync_list', [])])
             if p}
    paths |= {ide_linked_file(o) for o in context.scene.objects
              if o.type == 'MESH' and hasattr(o, 'inu') and o.inu.ide_linked}
    out: Dict[str, Set[int]] = {}
    for p in sorted(x for x in paths if x):
        if not os.path.isfile(p):
            continue
        try:
            ide = read_ide(p)
        except Exception as e:                                  # noqa: BLE001
            print(f"[map_export] IDE {os.path.basename(p)}: {e!r}")
            continue
        out[p] = {int(e.model_id) for sec in (ide.objects, ide.anims, ide.cars, ide.peds,
                                              ide.weaps, ide.hiers) for e in sec}
    return out


def assign_map_ids(context, prep):
    """Model ID for every model / LOD of *prep* that has none — from the
    active ID Manager preset (like Assign), all or nothing, before any file
    is written. Copies get one ID; a LOD prefers its model's ID + 1.
    Returns (objects changed, notes, error text)."""
    if not any(kind in ('ide', 'ipl', 'bnry') for kind, _d in prep.plan.values()):
        return 0, [], ''             # no IDE / IPL — DFF, COL, TXD carry no Model ID
    from ..ops.map_link import ide_linked_file
    groups = []                          # (key, name, objects, owner key)
    for m in prep.models.values():
        groups.append((('DFF', m.key), m.name, m.placements, None))
        if m.lod is not None and m.lod_own:
            groups.append((('LOD', m.lod_name.lower()), m.lod_name, m.lod_objs,
                           ('DFF', m.key)))

    def mid(o):
        return int(getattr(o.inu, 'model_id', 0) or 0)

    have = {key: [mid(o) for o in objs] for key, _n, objs, _ow in groups}
    need = [g for g in groups if not any(i > 0 for i in have[g[0]])]
    scene_ids, skip, per_file = set(), set(), {}
    if need:
        from .. import _id_preset_sync
        _id_preset_sync(context)
        scene_ids = {mid(o) for o in bpy.data.objects
                     if o.type == 'MESH' and hasattr(o, 'inu') and mid(o) > 0}
        per_file = _ide_file_ids(context)
        skip = scene_ids.union(*per_file.values())
    rows = []
    for key, name, objs, owner in groups:
        prefer, own = None, False
        if owner is not None and not any(i > 0 for i in have[key]):
            # Its own IDE row (Add to IDE wrote it at model + 1 while the
            # LOD had no ID) is its ID, not someone else's.
            for o in objs:
                path, oid = ide_linked_file(o), int(o.inu.ide_last_model_id or 0)
                if (oid > 0 and oid not in scene_ids and oid in per_file.get(path, ())
                        and not any(oid in ids for p, ids in per_file.items() if p != path)):
                    prefer, own = oid, True
                    break
            if prefer is None and any(i > 0 for i in have[owner]):
                prefer = min(i for i in have[owner] if i > 0) + 1
        rows.append((key, name, have[key], prefer, own))
    from ..data.id_manager import allocate_ids
    ids, notes, left = assign_ids(rows, allocate_ids, skip)
    if left:
        return 0, notes, T("Нет свободных ID в активном пресете ID Manager для: {0} — "
                           "ничего не записано. Заполните пресет: «База ID и сервис» → "
                           "«Создать ID» (или «Расширить FLA»)").format(_names(left))
    changed = 0
    for key, _n, objs, _ow in groups:
        for o in objs:
            if ids.get(key) and mid(o) != ids[key]:
                o.inu.model_id = ids[key]
                changed += 1
    if need:
        notes.append(('INFO', T("ID из ID Manager: моделей {0}").format(len(need))))
    return changed, notes, ''


# ──────────────────────────── files and IPL rows ──────────────────────

# IplDef.m_szName (0x10..0x21): 17 characters — a longer <cell>_stream0
# doesn't pair with its text IPL (CIplStore::SetupRelatedIpls 0x404DE0).
STREAM_NAME_MAX = 17


def stream_name_ok(cell: str) -> bool:
    return len(cell + '_stream0') <= STREAM_NAME_MAX


def plan_ipl_rows(pairs, pair: bool):
    """IPL rows of one cell (bpy-free — tested without Blender).

    ``pairs`` = [(model IplInstance, its LOD IplInstance or None)] in
    placement order. A placement with the ID and position (to the mm) of an
    earlier one is dropped with its LOD — SA crashes on such doubles; such a
    LOD row (models at one spot sharing a LOD) is written once and each of
    them points at it.
    pair=False → (models + LODs, [], dup): one text IPL, a model's lod_index
    points at its LOD row after the models. pair=True (SA Binary IPL) →
    (LODs, models, dup): the text <cell>.ipl holds the LOD rows, the binary
    <cell>_stream0.ipl the models, lod_index = row in the text IPL
    (CIplStore::LoadIpl 0x406080 resolves it in the related IPL)."""
    import copy

    def spot(r):
        return (r.model_id, round(r.pos_x, 3), round(r.pos_y, 3), round(r.pos_z, 3))

    mains, lods, seen, dup = [], [], set(), 0
    lod_at = {}                          # spot → its row in lods
    for main, lod in pairs:
        key = spot(main)
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        main = copy.copy(main)
        main.lod_index = -1
        if lod is not None:
            if spot(lod) not in lod_at:
                lod_at[spot(lod)] = len(lods)
                lod = copy.copy(lod)
                lod.lod_index = -1
                lods.append(lod)
            main.lod_index = lod_at[spot(lod)]
        mains.append(main)
    if pair:
        return lods, mains, dup
    for m in mains:
        if m.lod_index >= 0:
            m.lod_index += len(mains)
    return mains + lods, [], dup


def plan_files(models, cells, *, export_dff=True, export_col=True,
               col_library=False, export_txd=True, export_ide=True,
               export_ipl=True, pair=False) -> dict:
    """What Export Map writes (bpy-free — tested without Blender):
    {path: (kind, payload)} in write order, cell by cell.

    ``models`` — {key: MapModel}; ``cells`` — [(cell name, dir,
    [MapGroup(base=key, dff=placement)])]. A model's DFF, LOD, COL, TXD and
    IDE row go to the cell of its first placement; every placement is an IPL
    row of its own cell. TXD — one file per TXD name (the LOD's own TXD too,
    vanilla lanroad → lanlod)."""
    home_cell = {}
    for cell_name, _d, groups in cells:
        for g in groups:
            m = models.get(g.base)
            if m is not None and g.dff is m.home:
                home_cell[m.key] = cell_name
    plan = {}
    for cell_name, cell_dir, groups in cells:
        mine = [m for m in models.values() if home_cell.get(m.key) == cell_name]
        lods = [m for m in mine if m.lod is not None and m.lod_own]
        if export_dff:
            for m in mine:
                plan[os.path.join(cell_dir, m.name + '.dff')] = ('dff', m)
            for m in lods:
                plan[os.path.join(cell_dir, m.lod_name + '.dff')] = ('lod', m)
        if export_col:
            with_col = [m for m in mine if m.cols]
            if with_col and col_library:
                plan[os.path.join(cell_dir, cell_name + '.col')] = ('col_lib', with_col)
            elif with_col:
                for m in with_col:
                    plan[os.path.join(cell_dir, m.name + '.col')] = ('col', m)
        if export_txd:
            buckets = {}
            for m in mine:
                buckets.setdefault(m.txd.lower(), (m.txd, []))[1].append(m.home)
            for m in lods:
                buckets.setdefault(m.lod_txd.lower(), (m.lod_txd, []))[1].append(m.lod)
            for _k, (tname, objs) in sorted(buckets.items()):
                plan[os.path.join(cell_dir, tname + '.txd')] = ('txd', objs)
        if export_ide and mine:
            plan[os.path.join(cell_dir, cell_name + '.ide')] = ('ide', mine)
        if export_ipl:
            plan[os.path.join(cell_dir, cell_name + '.ipl')] = ('ipl', groups)
            if pair:
                plan[os.path.join(cell_dir, cell_name + '_stream0.ipl')] = ('bnry', groups)
    return plan


def existing_files(plan) -> list:
    """Paths of *plan* already on disk — the operator asks before replacing."""
    return [p for p in plan if os.path.isfile(p)]


def _txd_readable(path) -> bool:
    """An existing .txd update_txd can merge into (a Texture Dictionary)."""
    from ..core.txd import split_txd_sections
    try:
        with open(path, 'rb') as f:
            return split_txd_sections(f.read())[0] is not None
    except OSError:
        return False


# ──────────────────────────── main export ─────────────────────────────


def _plan_cells(groups, *, base_name: str, target_dir: str,
                split_mode: str, cell_size: float, scene,
                max_per_cell: int = 200,
                min_cell_size: float = 16.0):
    """Split groups into a flat list of (cell_name, cell_dir, cell_groups).

    ``split_mode`` is one of:

    * ``'NONE'`` — single cell named ``base_name`` covering all groups.
    * ``'GRID'`` — bin DFFs into ``cell_size``-meter XY cells. Multi-cell
      result is emitted in deterministic order. Single-cell result
      degrades to the NONE layout so flipping GRID on a small scene
      doesn't produce a dead subdirectory.
    * ``'ADAPTIVE'`` — quadtree subdivision driven by per-cell DFF count.
      Dense areas get small cells, sparse areas stay big. Each leaf
      cell holds at most ``max_per_cell`` DFFs (best-effort, capped by
      ``min_cell_size`` to avoid infinite recursion on stacked
      buildings). Single-leaf scenes degrade to the NONE layout.
    * ``'COLLECTION'`` — bin DFFs by their topmost user collection.
      Each cell gets the collection's name as its district name and
      its own subdirectory (always, even when only one bucket is
      produced — keeps the round-trip output structure consistent
      with the user's mental model of «my collection name = the IPL
      filename»).
    """
    mode = (split_mode or 'NONE').upper()

    if mode == 'GRID' and cell_size > 0:
        cells = compute_grid_cells(groups, cell_size)
        if len(cells) > 1:
            return [
                (format_cell_name(base_name, cx, cy),
                 os.path.join(target_dir, format_cell_name(base_name, cx, cy)),
                 cell_groups)
                for (cx, cy), cell_groups in sorted(cells.items())
            ]

    if mode == 'ADAPTIVE' and max_per_cell > 0:
        adaptive = compute_adaptive_cells(
            groups,
            max_per_cell=max_per_cell,
            min_cell_size=max(1.0, min_cell_size),
        )
        # Single-leaf scene means «didn't need to split» — fall through
        # to the bare base_name layout instead of emitting a single
        # «<base>` (no suffix) subdirectory; that's identical to NONE.
        if len(adaptive) > 1:
            return [
                (format_adaptive_cell_name(base_name, path),
                 os.path.join(target_dir,
                              format_adaptive_cell_name(base_name, path)),
                 cell_groups)
                for path, cell_groups in sorted(adaptive.items())
            ]

    if mode == 'COLLECTION' and scene is not None:
        cells = compute_collection_cells(groups, scene)
        if cells:
            # Always emit subfolders in COLLECTION mode — even one bucket
            # gets its own ``target_dir/<bucket>/`` directory so the user
            # immediately sees if all groups landed in the same bucket
            # (e.g. an «unsorted» fallback) and can fix the scene layout.
            return [
                (cell_name, os.path.join(target_dir, cell_name), cell_groups)
                for cell_name, cell_groups in sorted(cells.items())
            ]

    return [(base_name, target_dir, groups)]


class MapExportPrep:
    """One Export Map run, planned without touching the scene or the disk
    (:func:`prepare_map_export`) — the operator lists the files that
    already exist from ``plan`` and asks before anything is written."""

    def __init__(self, target_dir: str = ''):
        self.target_dir = target_dir
        self.models = {}            # key → MapModel
        self.placements = []        # [MapGroup(base=key, dff=placement)]
        self.cells = []             # [(cell name, dir, [MapGroup])]
        self.plan = {}              # path → (kind, payload), in write order
        self.notes = []             # [(level, text)]
        self.error = ''
        self.game = 'SA'
        self.pair = False           # SA Binary IPL: <cell>.ipl + <cell>_stream0.ipl
        self.split = False          # a split mode produced several cells
        self.fla = False


def prepare_map_export(context, target_dir: str, objects=None, *,
                       export_dff: bool = True,
                       export_col: bool = True,
                       col_library: bool = False,
                       export_txd: bool = True,
                       export_ipl: bool = True,
                       export_ide: bool = True,
                       binary_ipl: bool = False,
                       fla_extended_ipl: bool = False,
                       base_name: str = "district",
                       split_mode: str = 'NONE',
                       cell_size: float = 256.0,
                       max_per_cell: int = 200,
                       min_cell_size: float = 16.0) -> MapExportPrep:
    """Models, cells and the file plan of one export — no ID handed out,
    nothing written (that's :func:`assign_map_ids` / :func:`iter_export_map`)."""
    from ..ops.map_link import scene_game
    prep = MapExportPrep(target_dir)
    if objects is None:
        objects = list(context.selected_objects) or list(context.scene.objects)
    prep.models, prep.placements, prep.notes = collect_map_models(context, objects)
    if not prep.placements:
        prep.error = T("Нет моделей DFF для экспорта")
        return prep
    prep.game = scene_game(context)
    prep.pair = bool(export_ipl and binary_ipl) and prep.game == 'SA'
    prep.fla = bool(fla_extended_ipl)
    if export_col:
        bare = [m.name for m in prep.models.values() if not m.cols]
        if bare:
            prep.notes.append(('WARNING', T("Нет коллизии (COL) у моделей: {0}").format(
                _names(bare))))
    prep.cells = _plan_cells(prep.placements, base_name=base_name,
                             target_dir=target_dir, split_mode=split_mode,
                             cell_size=cell_size,
                             scene=getattr(context, 'scene', None),
                             max_per_cell=max_per_cell,
                             min_cell_size=min_cell_size)
    prep.split = (split_mode or 'NONE').upper() != 'NONE' and len(prep.cells) > 1
    if export_ipl and binary_ipl and not prep.pair:
        prep.notes.append(('INFO', T("Binary IPL — только для SA: для {0} записан "
                                     "текстовый IPL").format(prep.game)))
    for cell_name, _d, _g in (prep.cells if prep.pair else ()):
        if not stream_name_ok(cell_name):
            prep.notes.append(('WARNING', T(
                "{0}.ipl: имя длиннее {1} символов — игра не свяжет его с "
                "текстовым IPL. Сократите имя района").format(
                    cell_name + '_stream0', STREAM_NAME_MAX)))
    prep.plan = plan_files(prep.models, prep.cells, export_dff=export_dff,
                           export_col=export_col, col_library=col_library,
                           export_txd=export_txd, export_ide=export_ide,
                           export_ipl=export_ipl, pair=prep.pair)
    return prep


def iter_export_map(context, target_dir: str, *, objects=None,
                    export_dff: bool = True,
                    export_col: bool = True,
                    col_library: bool = False,
                    export_txd: bool = True,
                    export_ipl: bool = True,
                    export_ide: bool = True,
                    binary_ipl: bool = False,
                    fla_extended_ipl: bool = False,
                    base_name: str = "district",
                    split_mode: str = 'NONE',
                    cell_size: float = 256.0,
                    max_per_cell: int = 200,
                    min_cell_size: float = 16.0,
                    stats: Optional[dict] = None,
                    prepared: Optional[MapExportPrep] = None):
    """Generator-driven map export.

    Yields ``(current, total, status_label)`` after every file written.
    Caller drives it from a modal timer to keep the viewport responsive
    and update the workspace status bar between files. Pass an empty
    ``stats`` dict to have it filled with counts and ``notes`` in place.

    ``prepared`` — a plan from :func:`prepare_map_export` whose models
    already have their IDs (the operator asks about existing files, hands
    out IDs with an undo step, then runs this). Without it the generator
    plans and hands out IDs itself — the synchronous ``export_map(...)``
    wrapper exhausts it in one go for callers that don't need progress.
    """
    if stats is None:
        stats = {}
    for k in ('models', 'placements', 'dff', 'lod', 'col', 'txd', 'ide', 'ipl', 'rows'):
        stats.setdefault(k, 0)
    notes = stats.setdefault('notes', [])

    prep = prepared
    if prep is None:
        prep = prepare_map_export(
            context, target_dir, objects, export_dff=export_dff,
            export_col=export_col, col_library=col_library,
            export_txd=export_txd, export_ipl=export_ipl,
            export_ide=export_ide, binary_ipl=binary_ipl,
            fla_extended_ipl=fla_extended_ipl, base_name=base_name,
            split_mode=split_mode, cell_size=cell_size,
            max_per_cell=max_per_cell, min_cell_size=min_cell_size)
        if not prep.error:
            _n, id_notes, prep.error = assign_map_ids(context, prep)
            prep.notes[:0] = id_notes
    if prep.error:
        stats['error'] = prep.error
        return
    notes.extend(prep.notes)
    stats['models'] = len(prep.models)
    stats['placements'] = len(prep.placements)
    stats['pair'] = prep.pair
    if prep.split:
        stats['cells'] = len(prep.cells)
    plan = prep.plan
    kinds = {kind for kind, _d in plan.values()}
    total = max(1, len(plan))

    # ── Lazy imports (so the generator doesn't pull bpy heavy modules
    # in until it's actually run) ──
    if kinds & {'dff', 'lod'}:
        from ..ops.dff_export import export_dff as _export_dff, _resolve_export_version
        # Resolve RW version + platform once for the whole map export —
        # bulk export honours scene's gtatools_game + gtatools_platform.
        _map_export_rw_version = _resolve_export_version()
        try:
            import bpy as _bpy
            _map_export_platform = getattr(
                _bpy.context.scene.inu_settings, 'gtatools_platform', 'PC')
        except Exception:
            _map_export_platform = 'PC'
    if kinds & {'col', 'col_lib'}:
        from ..ops.col_export import (_resolve_col_version, export_col as _export_col,
                                      export_col_library as _export_col_lib)
        _map_export_col_version = _resolve_col_version()
    if 'txd' in kinds:
        from ..tools.txd_export import export_txd as _export_txd, update_txd as _update_txd
        # DXT compression backend — read once at the top so every bucket
        # uses the same encoder. Default 'numpy' is the vectorized core.dxt
        # path (no external binaries, ToS-clean for extensions.blender.org).
        _txd_backend = getattr(
            getattr(getattr(context, 'scene', None), 'inu_settings', None),
            'gtatools_dxt_backend', 'numpy')
    if kinds & {'ide', 'ipl', 'bnry'}:
        from ..ops import map_link as _ml
        from ..core.ide import IdeFile, write_ide
        from ..core.ipl import IplFile, write_ipl

    def _write(path, kind, data):
        fname = os.path.basename(path)
        if kind == 'dff':
            # The model alone — no LOD / COL inside (the game keeps one
            # atomic per model, an embedded COL crashes a map model);
            # 2DFX children are picked up by the DFF builder.
            _export_dff(path, [data.home], version=_map_export_rw_version,
                        target_platform=_map_export_platform)
            stats['dff'] += 1
        elif kind == 'lod':
            _export_dff(path, [data.lod], version=_map_export_rw_version,
                        target_platform=_map_export_platform)
            stats['lod'] += 1
        elif kind == 'col':
            _export_col(path, data.cols, version=_map_export_col_version,
                        model_name=data.name)
            stats['col'] += 1
        elif kind == 'col_lib':
            stats['col'] += _export_col_lib(path, [o for m in data for o in m.cols],
                                            version=_map_export_col_version)
        elif kind == 'txd':
            # Merged INTO an existing .txd: textures of models that aren't
            # in this export stay (one lanlod.txd serves hundreds of LODs).
            if os.path.isfile(path) and not _txd_readable(path):
                res, msg, _t = _export_txd(path, context, selected_only=True,
                                           backend=_txd_backend, objects=data)
                if res == {'FINISHED'}:
                    notes.append(('WARNING', T("{0}: существующий файл не TXD — "
                                               "заменён").format(fname)))
            else:
                res, msg, _t = _update_txd(path, context, selected_only=True,
                                           backend=_txd_backend, objects=data)
            if res == {'FINISHED'}:
                stats['txd'] += 1
            else:
                notes.append(('WARNING', f"{fname}: {msg}"))
        elif kind == 'ide':
            # A model, then its LOD — the rows of map_link.ide_entries, but
            # for exactly the LOD this export writes (its .dff, its TXD).
            from .. import _ide_entry_from_obj
            rows = []
            for m in data:
                ents = [_ide_entry_from_obj(m.home)]
                if m.lod is not None and m.lod_own:
                    le = _ide_entry_from_obj(m.lod)
                    le.model_name, le.txd_name = m.lod_name, m.lod_txd
                    le.model_id = _ml.lod_model_id(m.lod, m.home)
                    le.draw_distance = m.home.inu.lod_draw_distance
                    ents.append(le)
                for e in ents:
                    if e.model_id <= 0:
                        notes.append(('ERROR', T("«{0}»: Model ID = 0 — не записана").format(
                            e.model_name)))
                    else:
                        rows.append(e)
            write_ide(path, IdeFile(objects=rows), game=prep.game)
            stats['ide'] += 1
        elif kind in ('ipl', 'bnry'):
            pairs = []
            for g in data:
                m = prep.models[g.base]
                main = _ml.ipl_inst_of(g.dff)
                lod = None
                if m.lod is not None:
                    # Each placement gets its own LOD row, at its transform.
                    lod = _ml.lod_inst_for(g.dff, m.lod, m.name, main)
                    lod.model_name = m.lod_name
                    if lod.model_id <= 0 or _ml._lod_is_model(lod, main):
                        lod = None
                pairs.append((main, lod))
            text_rows, bin_rows, dup = plan_ipl_rows(pairs, prep.pair)
            rows = bin_rows if kind == 'bnry' else text_rows
            if dup and kind == 'ipl':
                notes.append(('WARNING', T("{0}: {1} одинаковых расстановок (тот же ID и "
                                           "позиция) записаны один раз").format(fname, dup)))
            write_ipl(path, IplFile(instances=rows), binary=(kind == 'bnry'),
                      game=prep.game, fla_extended=prep.fla and kind == 'ipl')
            stats['ipl'] += 1
            stats['rows'] += len(rows)

    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError:
            pass
    for d in sorted({os.path.dirname(p) for p in plan}):
        os.makedirs(d, exist_ok=True)

    labels = {'dff': 'DFF', 'lod': 'LOD', 'col': 'COL', 'col_lib': 'COL',
              'txd': 'TXD', 'ide': 'IDE', 'ipl': 'IPL', 'bnry': 'IPL'}
    for current, (path, (kind, data)) in enumerate(plan.items(), start=1):
        fname = os.path.basename(path)
        yield current, total, f"{labels[kind]} {fname}"
        try:
            _write(path, kind, data)
        except Exception as e:
            notes.append(('WARNING', f"{T('Ошибка экспорта')} {fname}: {e}"))
            print(f"[map_export] {fname} failed: {e}")


def map_export_report(stats) -> list:
    """[(level, text)] for the operator: the notes, then the summary last
    (the line the status bar keeps)."""
    head = T("Моделей {0}, расстановок {1} → DFF {2}, LOD {3}, COL {4}, TXD {5}, "
             "IDE {6}, IPL {7} (строк {8})").format(
        stats.get('models', 0), stats.get('placements', 0), stats.get('dff', 0),
        stats.get('lod', 0), stats.get('col', 0), stats.get('txd', 0),
        stats.get('ide', 0), stats.get('ipl', 0), stats.get('rows', 0))
    if stats.get('cells'):
        head = T("Ячеек {0}: ").format(stats['cells']) + head
    out, seen = [], set()
    for level, text in stats.get('notes', ()):
        if text not in seen:
            seen.add(text)
            out.append((level, text))
    if stats.get('pair') and stats.get('ipl'):
        out.append(('INFO', T(
            "Binary IPL: <ячейка>_stream0.ipl положите в IMG, который gta.dat "
            "грузит до строк IPL (например gta3.img); текстовый <ячейка>.ipl — "
            "строкой IPL в gta.dat, путь через обратный слэш")))
    warn = any(level in ('WARNING', 'ERROR') for level, _t in out)
    out.append(('WARNING' if warn else 'INFO', head))
    return out


def export_map(target_dir: str, *, objects=None,
               export_dff: bool = True,
               export_col: bool = True,
               col_library: bool = False,
               export_txd: bool = True,
               export_ipl: bool = True,
               export_ide: bool = True,
               binary_ipl: bool = False,
               fla_extended_ipl: bool = False,
               base_name: str = "district",
               split_mode: str = 'NONE',
               cell_size: float = 256.0,
               max_per_cell: int = 200,
               min_cell_size: float = 16.0) -> dict:
    """Synchronous wrapper around :func:`iter_export_map` for callers
    that don't need progress reporting (scripts, INU Export, etc.).

    Drives the generator to exhaustion in one go and returns the stats
    dict — including the ``cells`` count when a split mode was applied.
    No question about existing files (a .txd is merged, the rest
    replaced); models without an ID get one from the ID Manager.
    """
    stats: dict = {}
    for _ in iter_export_map(
            bpy.context, target_dir, objects=objects,
            export_dff=export_dff, export_col=export_col,
            col_library=col_library, export_txd=export_txd,
            export_ipl=export_ipl, export_ide=export_ide,
            binary_ipl=binary_ipl, fla_extended_ipl=fla_extended_ipl,
            base_name=base_name, split_mode=split_mode,
            cell_size=cell_size,
            max_per_cell=max_per_cell, min_cell_size=min_cell_size,
            stats=stats):
        pass
    return stats


# ──────────────────────────── operator + panel ───────────────────────

class GTATOOLS_OT_map_export(bpy.types.Operator):
    """Экспортировать выделение как готовый район GTA SA (DFF + COL + TXD + IDE + IPL в одну папку)"""
    bl_idname = "gtatools.map_export"
    bl_label = "INU: Export Map…"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    base_name: bpy.props.StringProperty(name="Base Name", default="district")
    include_dff: bpy.props.BoolProperty(name="DFF", default=True)
    include_col: bpy.props.BoolProperty(name="COL", default=True)
    col_library: bpy.props.BoolProperty(
        name=T("COL Library"),
        description=T("OFF (по умолчанию): каждая DFF получает свой отдельный <model>.col файл — соответствует ванильному SA где у большинства моделей коллизии в собственных файлах.\nON: все коллизии группируются в .col-библиотеки по inu.col_name (vegasN.col, LAs.col, …). Полезно когда есть осознанная shared collision на много моделей"),
        default=False,
    )
    include_txd: bpy.props.BoolProperty(name="TXD", default=True)
    include_ide: bpy.props.BoolProperty(name="IDE", default=True)
    include_ipl: bpy.props.BoolProperty(name="IPL", default=True)
    binary_ipl: bpy.props.BoolProperty(
        name="Binary IPL",
        description=T(
            "Только SA — пара, как в игре: модели в бинарный "
            "<ячейка>_stream0.ipl (игра берёт его только из IMG), строки LOD "
            "в текстовый <ячейка>.ipl (подключается в gta.dat). Для III/VC "
            "пишется текстовый IPL"),
        default=False,
    )
    fla_extended_ipl: bpy.props.BoolProperty(
        name=T("FLA: real_interior"),
        description=T(
            "Записать 12-ю колонку realInterior в каждой inst-строке IPL. "
            "Fastman92 Limit Adjuster читает её, vanilla SA молча "
            "игнорирует. Значение берётся из obj.inu.real_interior"),
        default=False,
    )
    split_mode: bpy.props.EnumProperty(
        name=T("Разбиение"),
        description=T("Как разбить выделение на отдельные district'ы при экспорте"),
        items=[
            ('NONE', T("Без разбиения"),
             T("Один общий district, все DFF в корне target_dir. base_name используется для имён IDE/IPL/COL/TXD")),
            ('GRID', T("XY-сетка"),
             T("Биннить DFF по XY-координате origin'а на ячейки cell_size метров. Каждая непустая ячейка получает подпапку <base>_x<cx>_y<cy> со своими IDE/IPL/COL/TXD")),
            ('ADAPTIVE', T("Адаптивная сетка"),
             T("Quadtree-разбиение по плотности: ячейка делится 2×2 пока в ней больше max_per_cell DFF. Плотные районы получают мелкие ячейки, разреженные остаются одной большой. Гарантирует число DFF на ячейку вместо равномерного пространственного разбиения. Имена подпапок: <base>_q<path>, где path — путь по квадрантам (0=SW, 1=SE, 2=NW, 3=NE)")),
            ('COLLECTION', T("По коллекциям"),
             T("Биннить DFF по имени верхней (top-level) коллекции, в которой объект лежит. Имя коллекции становится именем district'а — идеально для round-trip с Group-by-IPL импортом (vegasn_stream0 в Blender → vegasn_stream0.ipl на выходе)")),
        ],
        default='NONE',
    )
    cell_size: bpy.props.FloatProperty(
        name=T("Размер ячейки (м)"),
        description=T("Сторона квадратной ячейки в метрах для разбиения по XY-сетке. 256 м соответствует ванильному радиусу стриминга. Уменьшай для более мелких чанков, увеличивай если районов получается слишком много"),
        default=256.0, min=16.0, soft_max=2048.0, max=8192.0,
    )
    max_per_cell: bpy.props.IntProperty(
        name=T("Макс. DFF на ячейку"),
        description=T("Целевой потолок DFF в одной адаптивной ячейке. Когда число превышено — ячейка делится на 4. Меньше = больше мелких ячеек (тоньше streaming, но больше IPL-файлов). Больше = крупные ячейки. Vanilla SA streaming-радиус хорошо работает с ~150-300 DFF на IPL"),
        default=200, min=10, soft_max=2000, max=10000,
    )
    min_cell_size: bpy.props.FloatProperty(
        name=T("Мин. размер ячейки (м)"),
        description=T("Минимальная сторона ячейки для адаптивной сетки — нижняя граница рекурсии. Защищает от бесконечного деления когда много DFF разделяют одну XY-точку (вертикально стопкой, как небоскрёбы). При достижении этого предела ячейка остаётся, даже если в ней больше max_per_cell"),
        default=16.0, min=1.0, soft_max=256.0, max=2048.0,
    )

    # ENUM_FLAG = multi-checkbox in the operator dialog. Wins over outliner
    # state because the user picks the collections explicitly with a stable
    # UI element instead of relying on Blender's brittle outliner-context
    # selection forwarding (which gets cleared the moment focus shifts to
    # the sidebar button or the file browser).
    target_collections: bpy.props.EnumProperty(
        name=T("Целевые коллекции"),
        description=T("Какие top-level коллекции экспортировать. Авто-инициализация по выделению в outliner; если не угадало — отметь галочками вручную. Имеет смысл вместе с режимом «По коллекциям»"),
        items=lambda self, context: [
            (c.name, c.name, '')
            for c in context.scene.collection.children
        ][:32],  # ENUM_FLAG hard limit at 32 bits
        options={'ENUM_FLAG'},
        # No `default=` — Blender 5.x rejects non-int defaults when
        # `items` is a callable. Empty set is the natural default for
        # an ENUM_FLAG with dynamic items.
    )

    _timer = None
    _gen = None
    _stats: dict = None
    _captured_objects: list = None
    _prepared = None
    _ask_overwrite = False       # set by invoke — a script's EXEC run doesn't ask
    _confirm_lines: list = []    # existing files → draw() shows the question

    def invoke(self, context, event):
        type(self)._confirm_lines = []
        self._ask_overwrite = True
        self._prepared = None
        # Capture the user's outliner / viewport selection BEFORE the
        # file browser steals focus and clears it. Two-pronged: the
        # snapshot serves as a fallback when ``target_collections`` is
        # left empty in the dialog, and is also used to PRE-CHECK the
        # multi-select so the user sees their outliner selection
        # already mirrored.
        self._captured_objects = _resolve_export_objects(context)

        # Try to pre-populate the dialog's multi-checkbox from the
        # outliner state — best-effort, the user can correct it.
        outliner_colls = _gather_outliner_selected_collections(context)
        scene_top = {c.name for c in context.scene.collection.children}
        prefilled = {c.name for c in outliner_colls if c.name in scene_top}
        if prefilled:
            self.target_collections = prefilled

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        if type(self)._confirm_lines:
            # Second step (after the file browser): files already there.
            col = layout.column(align=True)
            col.label(text=T("Эти файлы уже есть и будут заменены (.txd — слиянием):"),
                      **inu_icon(safe_icon('ERROR')))
            for line in type(self)._confirm_lines:
                col.label(text=line)
            col.separator()
            col.label(text=T("Продолжить?"))
            return

        # Top-level collections multi-checkbox FIRST — most reliable
        # way to express «export these N collections» when the outliner
        # auto-detection fails to capture the user's Ctrl-clicked set
        # (Blender's selected_ids context is brittle from sidebar buttons).
        box = layout.box()
        box.label(text=T("Целевые коллекции:"), **inu_icon(safe_icon('OUTLINER_COLLECTION')))
        col = box.column(align=True)
        col.prop(self, "target_collections", expand=True)
        if not self.target_collections:
            box.label(
                text=T("(пусто = выделение из outliner на момент нажатия)"),
                **inu_icon(safe_icon('INFO')),
            )

        layout.separator()
        layout.prop(self, "base_name")
        row = layout.row(align=True)
        row.prop(self, "include_dff", toggle=True)
        row.prop(self, "include_col", toggle=True)
        row.prop(self, "include_txd", toggle=True)
        row = layout.row(align=True)
        row.prop(self, "include_ide", toggle=True)
        row.prop(self, "include_ipl", toggle=True)
        layout.prop(self, "col_library")
        layout.prop(self, "binary_ipl")
        layout.prop(self, "fla_extended_ipl")
        if self.include_ide or self.include_ipl:
            preset = getattr(context.scene.inu_settings, 'gtatools_id_preset', '') or 'default'
            layout.label(text=T("Модели без ID получат ID из пресета ID Manager «{0}»").format(
                preset), **inu_icon(safe_icon('INFO')))
        layout.separator()
        layout.prop(self, "split_mode")
        if self.split_mode == 'GRID':
            layout.prop(self, "cell_size")
        elif self.split_mode == 'ADAPTIVE':
            sub = layout.column(align=True)
            sub.prop(self, "max_per_cell")
            sub.prop(self, "min_cell_size")

    def execute(self, context):
        if not self.directory or not os.path.isdir(self.directory):
            self.report({'ERROR'}, "Pick a target folder")
            return {'CANCELLED'}

        prep = self._prepared        # second pass: OK in the «files exist» dialog
        if prep is None:
            prep = self._prepare(context)
        if prep.error:
            self.report({'ERROR'}, prep.error)
            return {'CANCELLED'}

        # Files already in the folder → list + question before anything is
        # written or any ID handed out (.txd is merged, the rest replaced).
        existing = existing_files(prep.plan)
        if existing and self._ask_overwrite:
            self._ask_overwrite = False
            self._prepared = prep
            shown = [os.path.relpath(p, self.directory) for p in existing[:20]]
            if len(existing) > 20:
                shown.append(T("… ещё {0}").format(len(existing) - 20))
            type(self)._confirm_lines = shown
            return context.window_manager.invoke_props_dialog(self, width=520)
        type(self)._confirm_lines = []
        self._prepared = None

        # Model IDs from the ID Manager — all or nothing, own undo step
        # (the operator has no UNDO flag: ESC after this, or Adjust Last
        # Operation re-running the whole export, would lose / redo it).
        changed, id_notes, err = assign_map_ids(context, prep)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        if changed:
            try:
                bpy.ops.ed.undo_push(message="INU: Export Map IDs")
            except Exception as e:
                print(f"[map_export] undo_push failed: {e}")
        prep.notes[:0] = id_notes

        # Modal generator pattern (same shape as Import Map): yield-driven
        # work loop fed by a window-manager timer keeps the viewport
        # responsive and the workspace status text fresh between writes.
        self._stats = {}
        self._gen = iter_export_map(context, self.directory, stats=self._stats,
                                    prepared=prep)

        wm = context.window_manager
        wm.progress_begin(0, 100)
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(T("Map Export: подготовка..."))
        return {'RUNNING_MODAL'}

    def _prepare(self, context):
        # Source of truth, in priority order:
        #   1. Explicit dialog checkboxes (``target_collections``) — the
        #      user picked these in the operator panel, ignore everything
        #      else. Most reliable path for multi-collection exports.
        #   2. Snapshot captured at invoke() time, before the file dialog
        #      stole focus.
        #   3. Live resolve (only when the operator was triggered via
        #      ``bpy.ops.gtatools.map_export()`` from a script).
        if self.target_collections:
            collections = []
            for name in self.target_collections:
                coll = bpy.data.collections.get(name)
                if coll is None:
                    coll = next((c for c in context.scene.collection.children
                                 if c.name == name), None)
                if coll is not None:
                    collections.append(coll)
            gathered: dict = {}
            for coll in collections:
                for obj in coll.all_objects:
                    if obj.type == 'MESH':
                        gathered[id(obj)] = obj
            selected = list(gathered.values())
        else:
            selected = self._captured_objects
            if not selected:
                selected = _resolve_export_objects(context)

        return prepare_map_export(
            context, self.directory, selected,
            export_dff=self.include_dff,
            export_col=self.include_col,
            col_library=self.col_library,
            export_txd=self.include_txd,
            export_ide=self.include_ide,
            export_ipl=self.include_ipl,
            binary_ipl=self.binary_ipl,
            fla_extended_ipl=self.fla_extended_ipl,
            base_name=self.base_name,
            split_mode=self.split_mode,
            cell_size=self.cell_size,
            max_per_cell=self.max_per_cell,
            min_cell_size=self.min_cell_size,
        )

    def modal(self, context, event):
        if event.type == 'ESC':
            self._finish(context)
            self.report({'WARNING'}, T("Отменено"))
            return {'CANCELLED'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        import time
        wm = context.window_manager
        deadline = time.monotonic() + 0.05  # ~20 fps frame budget

        while time.monotonic() < deadline:
            try:
                current, total, label = next(self._gen)
            except StopIteration:
                self._finish(context)
                stats = self._stats or {}
                if stats.get('error'):
                    self.report({'ERROR'}, stats['error'])
                    return {'CANCELLED'}
                lines = map_export_report(stats)
                for level, text in lines[:-1][:20] + lines[-1:]:
                    self.report({level if level in ('WARNING', 'ERROR') else 'INFO'}, text)
                # Mobile: TXD карты всё равно PC-формата (как в Export TXD) —
                # после сводки, последним (строка состояния).
                from .txd_export import mobile_txd_warning
                _mob = mobile_txd_warning(getattr(
                    context.scene.inu_settings, 'gtatools_platform', 'PC'),
                    stats.get('txd', 0))
                if _mob:
                    self.report({'WARNING'}, _mob)
                return {'FINISHED'}
            except Exception as e:
                self._finish(context)
                self.report({'ERROR'}, f"{T('Ошибка экспорта')}: {e}")
                print(f"[map_export] aborted: {e}")
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}

            pct = int(100 * current / max(total, 1))
            wm.progress_update(pct)
            context.workspace.status_text_set(
                f"Map Export: {current}/{total} — {label}")

        return {'RUNNING_MODAL'}

    def _finish(self, context):
        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        try:
            context.window_manager.progress_end()
        except Exception:
            pass
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass
        self._gen = None


