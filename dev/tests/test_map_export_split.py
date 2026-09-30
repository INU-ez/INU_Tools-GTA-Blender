"""Unit tests for the map-export split planners — the pure-Python
binning helpers that decide how many sub-districts a scene splits into
and what each one is named.

These tests stub bpy so the module imports cleanly without a real
Blender. We only exercise the geometry-driven helpers:

* ``compute_grid_cells`` — uniform XY grid (legacy 1.6.6 mode)
* ``compute_adaptive_cells`` — quadtree subdivision (new 1.7.0 mode)
* ``format_cell_name`` / ``format_adaptive_cell_name`` — naming

The Blender-coupled paths (operator, file IO) need a live Blender and
are out of scope for unit tests.
"""

from pathlib import Path
import math
import sys
import types
from dataclasses import dataclass, field

import pytest


ROOT = Path(__file__).resolve().parents[2]
# Add the addon dir so `tools.map_export` resolves; also stub a fake
# top-level package named `INU_tools` so that ``from .. import T`` in
# map_export.py (which would otherwise reach above top level when the
# module is imported as ``tools.map_export``) finds a usable T helper.
sys.path.insert(0, str(ROOT / "INU_tools"))


def _ensure_bpy_stubs():
    if 'bpy' in sys.modules:
        return
    bpy_mod = types.ModuleType('bpy')

    class _DummyClass:
        pass

    bpy_mod.types = types.SimpleNamespace(
        Operator=_DummyClass, Panel=_DummyClass,
        PropertyGroup=_DummyClass,
        # Object/Collection/Material referenced as forward-string
        # annotations in tools/map_export.py. Python 3.11 in CI evals
        # those during dataclass construction even when quoted, while
        # Python 3.14 locally doesn't — add stubs so both behave the
        # same.
        Object=_DummyClass, Collection=_DummyClass,
        Material=_DummyClass)
    bpy_mod.props = types.SimpleNamespace(
        StringProperty=lambda **kw: None,
        IntProperty=lambda **kw: None,
        FloatProperty=lambda **kw: None,
        BoolProperty=lambda **kw: None,
        EnumProperty=lambda **kw: None,
    )
    bpy_mod.context = types.SimpleNamespace(scene=None)
    sys.modules['bpy'] = bpy_mod
    sys.modules['bpy.types'] = bpy_mod.types
    sys.modules['bpy.props'] = bpy_mod.props
    # `tools.model_utils` imports bmesh at top — module-load-time only
    # uses the symbol indirectly via geometry checks we don't exercise.
    sys.modules.setdefault('bmesh', types.ModuleType('bmesh'))


_ensure_bpy_stubs()


# Re-route `tools.map_export` through a parent package so its
# ``from .. import T`` resolves. We do this by importing the addon as
# `INU_tools.tools.map_export` from the repo root rather than as a
# bare `tools.map_export`. The addon's __init__.py is heavy (defines
# every operator), so we install a *minimal* stub package that only
# exports T — enough for map_export's import-time resolution.
_pkg_root = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
_pkg_root.__path__ = [str(ROOT / "INU_tools")]
_pkg_root.T = lambda s, *_a, **_kw: s

from INU_tools.tools.map_export import (  # noqa: E402
    MapGroup,
    MapModel,
    compute_grid_cells,
    compute_adaptive_cells,
    format_cell_name,
    format_adaptive_cell_name,
    _plan_cells,
    _pick_col_group,
    assign_ids,
    existing_files,
    map_export_report,
    plan_files,
    plan_ipl_rows,
    stream_name_ok,
)
from INU_tools.core.ipl import IplInstance  # noqa: E402


# ── Mock objects ─────────────────────────────────────────────────

@dataclass
class _Loc:
    x: float
    y: float
    z: float = 0.0


@dataclass
class _Matrix:
    translation: _Loc


@dataclass
class _MockObj:
    name: str
    matrix_world: _Matrix


def _g(name: str, x: float, y: float) -> MapGroup:
    """Build a MapGroup with just enough state for the binning planners."""
    return MapGroup(
        base=name,
        dff=_MockObj(name=name, matrix_world=_Matrix(_Loc(x, y))),
    )


# ── Uniform GRID — legacy regression coverage ──────────────────────

def test_grid_cells_empty_groups_are_one_empty_bucket():
    cells = compute_grid_cells([], 256.0)
    assert cells == {}


def test_grid_cells_zero_cell_size_collapses_to_origin():
    """cell_size <= 0 disables binning — all groups land in (0, 0)."""
    groups = [_g("a", 100, 100), _g("b", -500, 0)]
    cells = compute_grid_cells(groups, 0.0)
    assert cells == {(0, 0): groups}


def test_grid_cells_bin_by_origin():
    groups = [
        _g("a", 50, 50),       # cell (0, 0)
        _g("b", 300, 50),      # cell (1, 0)
        _g("c", 50, 300),      # cell (0, 1)
        _g("d", -10, -10),     # cell (-1, -1)
    ]
    cells = compute_grid_cells(groups, 256.0)
    assert (0, 0) in cells
    assert (1, 0) in cells
    assert (0, 1) in cells
    assert (-1, -1) in cells
    assert sum(len(v) for v in cells.values()) == 4


def test_format_cell_name_negative_uses_m_prefix():
    assert format_cell_name("vegas", 0, 0) == "vegas_x0_y0"
    assert format_cell_name("vegas", -1, 2) == "vegas_xm1_y2"
    assert format_cell_name("vegas", 5, -3) == "vegas_x5_ym3"


# ── Adaptive (quadtree) — new in 1.7.0 ─────────────────────────────

def test_adaptive_empty_returns_empty_dict():
    assert compute_adaptive_cells([]) == {}


def test_adaptive_below_threshold_stays_one_cell():
    """A small population fits in the root cell — empty path key,
    single cell holds everything."""
    groups = [_g(f"m{i}", i * 10, 0) for i in range(10)]
    cells = compute_adaptive_cells(groups, max_per_cell=200)
    assert cells == {(): groups}


def test_adaptive_dense_scene_splits():
    """50 DFFs spread across a big bbox with cap=10 → must split into
    multiple leaf cells (>1) and every leaf is at most cap large."""
    groups = []
    for i in range(50):
        # 5×10 grid spanning 1000×2000 m
        groups.append(_g(f"m{i}",
                         (i % 5) * 200.0,
                         (i // 5) * 200.0))
    cells = compute_adaptive_cells(groups, max_per_cell=10)
    assert len(cells) > 1
    for path, leaf in cells.items():
        # cap is best-effort — min_cell_size floor can leave a cell
        # over budget. With 200 m grid and 16 m floor we shouldn't
        # hit that here.
        assert len(leaf) <= 10, (
            f"leaf {path} holds {len(leaf)} > cap 10")


def test_adaptive_partition_is_complete():
    """Sum of leaves equals input population (no losses, no doubles)."""
    groups = [_g(f"m{i}", i * 30.0, (i * 17) % 800) for i in range(80)]
    cells = compute_adaptive_cells(groups, max_per_cell=15)
    total = sum(len(v) for v in cells.values())
    assert total == len(groups)
    seen = set()
    for leaf in cells.values():
        for g in leaf:
            assert id(g) not in seen, "group counted twice"
            seen.add(id(g))


def test_adaptive_min_cell_size_floor_stops_recursion():
    """Many DFFs at the SAME XY origin would loop infinitely without
    the min_cell_size floor. The floor must terminate even when the
    cap is exceeded."""
    groups = [_g(f"stack{i}", 0.0, 0.0) for i in range(50)]
    cells = compute_adaptive_cells(
        groups, max_per_cell=5, min_cell_size=4.0)
    # Floor reached → one leaf with all 50, over budget but bounded.
    assert len(cells) == 1
    only_leaf = next(iter(cells.values()))
    assert len(only_leaf) == 50


def test_adaptive_path_keys_describe_quadrants():
    """Path tuple uses 0=SW, 1=SE, 2=NW, 3=NE — one DFF per quadrant
    of the bbox should produce four distinct length-1 paths."""
    groups = [
        _g("sw", -100, -100),  # SW
        _g("se",  100, -100),  # SE
        _g("nw", -100,  100),  # NW
        _g("ne",  100,  100),  # NE
    ]
    cells = compute_adaptive_cells(groups, max_per_cell=1)
    assert set(cells.keys()) == {(0,), (1,), (2,), (3,)}


def test_adaptive_naming_omits_suffix_for_single_cell():
    """When the scene fits in one cell the path is empty — name stays
    the bare base_name (no _q suffix), so flipping ADAPTIVE on a small
    scene doesn't sprout a noise directory."""
    assert format_adaptive_cell_name("dist", ()) == "dist"


def test_adaptive_naming_encodes_path():
    assert format_adaptive_cell_name("dist", (0,)) == "dist_q0"
    assert format_adaptive_cell_name("dist", (1, 3)) == "dist_q13"
    assert (format_adaptive_cell_name("dist", (0, 1, 2, 3))
            == "dist_q0123")


def test_adaptive_dense_cluster_subdivides_more_than_sparse():
    """Real motivation for adaptive split: a scene with one packed
    cluster + a few outliers should produce small cells inside the
    cluster while the outliers each get their own coarse cell, NOT
    the other way around."""
    groups = []
    # Cluster: 40 DFFs in a 20×20 m box around origin
    for i in range(40):
        groups.append(_g(f"c{i}",
                         (i % 8) * 2.5, (i // 8) * 2.5))
    # Outliers: 2 single DFFs far away
    groups.append(_g("far_a", 5000.0, 0.0))
    groups.append(_g("far_b", 0.0, 5000.0))

    cells = compute_adaptive_cells(groups, max_per_cell=15,
                                   min_cell_size=1.0)
    # Cluster forces multiple subdivisions; outliers occupy their
    # own (or shared) coarse cell. Total leaves should comfortably
    # exceed 2.
    assert len(cells) >= 3
    # Every leaf still respects the cap (min_cell_size=1m gives
    # plenty of room to subdivide the 20m cluster).
    for leaf in cells.values():
        assert len(leaf) <= 15


# ── Export Map: IPL rows per placement, own LOD, binary pair ─────────

def _inst(mid, x=0.0, lod_index=-1):
    return IplInstance(model_id=mid, model_name=f"m{mid}", pos_x=x,
                       lod_index=lod_index)


def test_ipl_rows_every_placement_with_its_lod():
    """Two placements of a model with a LOD → [m, m, L, L]; each model
    row points at its own LOD row after the models."""
    text, binary, dup = plan_ipl_rows(
        [(_inst(100, 0), _inst(101, 0)), (_inst(100, 50), _inst(101, 50))], False)
    assert [r.model_id for r in text] == [100, 100, 101, 101]
    assert [r.lod_index for r in text] == [2, 3, -1, -1]
    assert text[2].pos_x == 0 and text[3].pos_x == 50
    assert binary == [] and dup == 0


def test_ipl_rows_binary_pair():
    """SA Binary IPL: text <cell>.ipl = the LOD rows, binary
    <cell>_stream0.ipl = the models, lod_index into the text IPL."""
    text, binary, dup = plan_ipl_rows(
        [(_inst(100, 0), _inst(101, 0)), (_inst(100, 50), _inst(101, 50))], True)
    assert [r.model_id for r in text] == [101, 101]
    assert [r.lod_index for r in text] == [-1, -1]
    assert [(r.model_id, r.lod_index) for r in binary] == [(100, 0), (100, 1)]
    assert dup == 0


def test_ipl_rows_double_placement_dropped_with_its_lod():
    """Same ID and position (to the mm) twice → SA crashes; the second
    one is dropped and so is its LOD row."""
    text, _b, dup = plan_ipl_rows(
        [(_inst(100, 5.0), _inst(101, 5.0)), (_inst(100, 5.0004), _inst(101, 5.0004))],
        False)
    assert dup == 1
    assert [(r.model_id, r.lod_index) for r in text] == [(100, 1), (101, -1)]


def test_ipl_rows_without_lod_and_inputs_untouched():
    main = _inst(100, 0, lod_index=7)           # stale lod_index from an import
    text, _b, _d = plan_ipl_rows([(main, None)], False)
    assert [r.lod_index for r in text] == [-1]
    assert main.lod_index == 7                  # the caller's rows are copies
    # Binary pair without any LOD: empty text IPL, every model row -1.
    text, binary, _d = plan_ipl_rows([(_inst(100, 0), None), (_inst(102, 9), None)], True)
    assert text == [] and [r.lod_index for r in binary] == [-1, -1]


def test_ipl_rows_models_sharing_a_lod_at_one_spot_share_its_row():
    """Two models at one spot with a shared LOD: one LOD row (a second one
    with the same ID and position is the double SA crashes on), both
    models point at it."""
    pairs = [(_inst(100, 5), _inst(300, 5)), (_inst(200, 5), _inst(300, 5)),
             (_inst(100, 9), _inst(300, 9))]
    text, _b, dup = plan_ipl_rows(pairs, False)
    assert dup == 0
    assert [(r.model_id, r.lod_index) for r in text] == [
        (100, 3), (200, 3), (100, 4), (300, -1), (300, -1)]
    text, binary, _d = plan_ipl_rows(pairs, True)
    assert [r.pos_x for r in text] == [5, 9]
    assert [(r.model_id, r.lod_index) for r in binary] == [(100, 0), (200, 0), (100, 1)]


def test_stream_name_fits_iplDef_name():
    assert stream_name_ok("abcdefghi")          # abcdefghi_stream0 = 17
    assert not stream_name_ok("abcdefghij")


# ── Export Map: which files get written ─────────────────────────────

def _o(name, x=0.0, y=0.0, z=0.0, model_id=0):
    o = _MockObj(name=name, matrix_world=_Matrix(_Loc(x, y, z)))
    o.inu = types.SimpleNamespace(model_id=model_id)
    return o


def _rel(plan, root):
    import os
    return {os.path.relpath(p, root).replace('\\', '/') for p in plan}


def _two_models():
    a, b = _o("a"), _o("b", 50)
    models = {"a": MapModel(key="a", name="a", home=a, txd="shared",
                            cols=[_o("a_COL")]),
              "b": MapModel(key="b", name="b", home=b, txd="b")}
    return models, [MapGroup(base="a", dff=a), MapGroup(base="b", dff=b)]


def test_plan_files_one_district(tmp_path):
    models, groups = _two_models()
    plan = plan_files(models, [("district", str(tmp_path), groups)])
    assert _rel(plan, tmp_path) == {"a.dff", "a.col", "b.dff", "shared.txd",
                                    "b.txd", "district.ide", "district.ipl"}
    assert plan[str(tmp_path / "district.ipl")] == ("ipl", groups)
    assert plan[str(tmp_path / "shared.txd")] == ("txd", [models["a"].home])
    # Planning hands out no IDs.
    assert models["a"].home.inu.model_id == 0


def test_plan_files_col_library_and_flags(tmp_path):
    models, groups = _two_models()
    cells = [("district", str(tmp_path), groups)]
    lib = _rel(plan_files(models, cells, col_library=True), tmp_path)
    assert "district.col" in lib and "a.col" not in lib
    only = plan_files(models, cells, export_dff=False, export_col=False,
                      export_txd=False, export_ide=False)
    assert _rel(only, tmp_path) == {"district.ipl"}


def test_plan_files_lod_gets_its_own_dff_and_txd(tmp_path):
    a, la = _o("a"), _o("LODa")
    m = MapModel(key="a", name="a", home=a, lod=la, lod_name="LODa",
                 txd="a", lod_txd="alod")
    cells = [("d", str(tmp_path), [MapGroup(base="a", dff=a)])]
    plan = plan_files({"a": m}, cells, pair=True)
    assert _rel(plan, tmp_path) == {"a.dff", "LODa.dff", "a.txd", "alod.txd",
                                    "d.ide", "d.ipl", "d_stream0.ipl"}
    assert plan[str(tmp_path / "LODa.dff")] == ("lod", m)
    assert plan[str(tmp_path / "alod.txd")] == ("txd", [la])
    assert plan[str(tmp_path / "d_stream0.ipl")][0] == "bnry"
    # The same TXD for both (case aside) → one file with both objects.
    m.lod_txd = "A"
    assert plan_files({"a": m}, cells)[str(tmp_path / "a.txd")] == ("txd", [a, la])
    # A LOD another model writes: no .dff / TXD of it here.
    m.lod_own = False
    assert _rel(plan_files({"a": m}, cells), tmp_path) == {"a.dff", "a.txd", "d.ide", "d.ipl"}


def test_plan_files_grid_copy_in_other_cell_is_only_a_row(tmp_path):
    """A copy standing in another cell: the model's files stay in the cell
    of its first placement, the other cell gets only its IPL row."""
    a, a2 = _o("a", 10), _o("a.001", 300)
    m = MapModel(key="a", name="a", home=a, placements=[a, a2], txd="a")
    groups = [MapGroup(base="a", dff=a), MapGroup(base="a", dff=a2)]
    cells = _plan_cells(groups, base_name="d", target_dir=str(tmp_path),
                        split_mode="GRID", cell_size=256.0, scene=None)
    assert [c[0] for c in cells] == ["d_x0_y0", "d_x1_y0"]
    assert _rel(plan_files({"a": m}, cells), tmp_path) == {
        "d_x0_y0/a.dff", "d_x0_y0/a.txd", "d_x0_y0/d_x0_y0.ide", "d_x0_y0/d_x0_y0.ipl",
        "d_x1_y0/d_x1_y0.ipl"}


def test_existing_files_are_listed(tmp_path):
    models, groups = _two_models()
    plan = plan_files(models, [("district", str(tmp_path), groups)])
    (tmp_path / "a.dff").write_bytes(b"x")
    (tmp_path / "shared.txd").write_bytes(b"x")
    assert _rel(existing_files(plan), tmp_path) == {"a.dff", "shared.txd"}


def test_pick_col_group_one_collision_per_model():
    home = _o("a", 10)
    here = [_o("a_COL.001", 10), _o("a_SHA.001", 10)]
    other = [_o("a_COL", 99), _o("a_COL.002", 5)]
    assert _pick_col_group(other + here, home) == here          # home's spot
    assert _pick_col_group(other, home) == [other[0]]            # undecorated
    assert _pick_col_group([_o("a_COL.003", 1), _o("a_COL.002", 2)], home)[0].name == "a_COL.002"
    assert _pick_col_group([], home) == []


# ── Export Map: Model IDs from the ID Manager ────────────────────────

def _alloc(pool):
    """allocate_ids() semantics over an in-memory pool (all or nothing)."""
    seen = []

    def allocate(requests, skip):
        seen.append((list(requests), set(skip)))
        free, skip, out = list(pool), set(skip), []
        for _name, prefer in requests:
            if prefer is not None and prefer in free:
                nid = prefer
            else:
                nid = next((i for i in free if i not in skip), None)
                if nid is None:
                    return None
            free.remove(nid)
            skip.add(nid)
            out.append(nid)
        return out
    return allocate, seen


def test_assign_ids_copies_share_one_and_existing_kept():
    allocate, _s = _alloc([500, 501, 502])
    ids, notes, left = assign_ids([
        ("a", "a", [0, 0], None, False),
        ("b", "b", [700, 0], None, False),
    ], allocate, set())
    assert ids == {"a": 500, "b": 700} and left == [] and notes == []


def test_assign_ids_different_copy_ids_take_smallest_with_note():
    allocate, seen = _alloc([500])
    ids, notes, _l = assign_ids([("a", "a", [900, 800], None, False)], allocate, set())
    assert ids == {"a": 800}
    assert seen == []                       # nothing to allocate
    assert notes and notes[0][0] == "WARNING" and "800" in notes[0][1]


def test_assign_ids_never_repeats_an_id_in_use():
    """Regression: a model without an ID listed before a model that has
    20000 must not get 20000 too; nor an ID of the scene / IDE files."""
    allocate, seen = _alloc([20000, 20001, 20002, 20003])
    ids, _n, _l = assign_ids([
        ("new", "new", [0], None, False),
        ("old", "old", [20000], None, False),
    ], allocate, {20001})
    assert ids == {"new": 20002, "old": 20000}
    assert {20000, 20001} <= seen[0][1]


def test_assign_ids_lod_prefers_model_plus_one():
    allocate, seen = _alloc([300, 501, 502])
    ids, notes, _l = assign_ids([
        ("m", "m", [500], None, False),
        ("L", "LODm", [0], 501, False),
    ], allocate, set())
    assert ids["L"] == 501 and notes == []
    # N+1 used elsewhere → not asked for, first free, with a note.
    allocate, seen = _alloc([300, 501, 502])
    ids, notes, _l = assign_ids([("L", "LODm", [0], 501, False)], allocate, {501})
    assert seen[0][0] == [("LODm", None)] and ids["L"] == 300
    assert notes[0][0] == "INFO" and "501" in notes[0][1]
    # …unless it is the LOD's own IDE row.
    allocate, seen = _alloc([300, 501])
    ids, _n, _l = assign_ids([("L", "LODm", [0], 501, True)], allocate, {501})
    assert seen[0][0] == [("LODm", 501)] and ids["L"] == 501


def test_assign_ids_out_of_ids_gives_nothing():
    allocate, _s = _alloc([500])
    ids, _n, left = assign_ids([
        ("a", "a", [0], None, False),
        ("b", "b", [0], None, False),
        ("c", "c", [42], None, False),
    ], allocate, set())
    assert ids == {} and left == ["a", "b"]


# ── Export Map: models of a scene ────────────────────────────────────

def _mesh(name, x=0.0, *, textured=True, model_id=0, lod_object=None):
    mats = [types.SimpleNamespace(inu=types.SimpleNamespace(texture_name="t"))]
    return types.SimpleNamespace(
        name=name, type="MESH", matrix_world=_Matrix(_Loc(x, 0.0)),
        data=types.SimpleNamespace(materials=mats if textured else []),
        inu=types.SimpleNamespace(type="OBJ", model_id=model_id, lod_object=lod_object,
                                  txd_name="", ide_last_name=""))


def test_collect_map_models(monkeypatch):
    from INU_tools.tools import map_export
    from INU_tools.ops import map_link
    lod, lod2 = _mesh("LODhouse"), _mesh("LODhouse.001", 50)
    far = _mesh("far_barn", 100)
    house, house2 = _mesh("house"), _mesh("house.001", 50, lod_object=lod2)
    barn = _mesh("barn", 100, lod_object=far)
    tree, tree_lod = _mesh("tree", 200, model_id=700), _mesh("LODtree", 200, model_id=700)
    cols = [_mesh("house_COL.001", 50, textured=False), _mesh("house_COL", 0, textured=False),
            _mesh("house_SHA", 0, textured=False)]
    shed_lod = _mesh("LODshed", 300)
    scene = types.SimpleNamespace(
        objects=[house, house2, lod, lod2, far, barn, tree, tree_lod, shed_lod] + cols,
        inu_settings=types.SimpleNamespace())
    ctx = types.SimpleNamespace(scene=scene)
    for fn in (map_export.get_model_type, map_link.LodIndex.__init__):
        monkeypatch.setattr(fn.__globals__["bpy"], "context", ctx, raising=False)

    # The selection: models, the LOD-by-pointer «far_barn», a lone LOD.
    models, placements, notes = map_export.collect_map_models(
        ctx, [house, house2, barn, far, tree, shed_lod])
    assert list(models) == ["house", "barn", "tree"]
    assert [g.dff.name for g in placements] == ["house", "house.001", "barn", "tree"]
    h = models["house"]
    assert h.placements == [house, house2]
    assert h.lod is lod and h.lod_name == "LODhouse" and h.lod_own
    assert h.lod_objs == [lod, lod2]                 # one ID for the LOD's copies
    assert [c.name for c in h.cols] == ["house_COL", "house_SHA"]   # one collision
    assert models["barn"].lod is far                 # LOD by pointer, not a model
    assert models["tree"].lod is None                # LOD with the model's own ID
    text = " | ".join(t for _l, t in notes)
    assert "LODtree" in text and "LODshed" in text and "far_barn" not in text


def _collect(monkeypatch, scene_objects, selection):
    from INU_tools.tools import map_export
    from INU_tools.ops import map_link
    ctx = types.SimpleNamespace(scene=types.SimpleNamespace(
        objects=scene_objects, inu_settings=types.SimpleNamespace()))
    for fn in (map_export.get_model_type, map_link.LodIndex.__init__):
        monkeypatch.setattr(fn.__globals__["bpy"], "context", ctx, raising=False)
    return map_export.collect_map_models(ctx, selection)


def test_collect_lod_copy_with_a_model_id_is_not_the_lod(monkeypatch):
    """Shift+D of the model renamed to LODhouse (→ LODhouse.001) keeps the
    model's ID: it must not hand that ID to the LOD (two IDE rows with
    one ID). Same for another exported model's ID."""
    for lod_id in (0, 501):
        house, tree = _mesh("house", model_id=500), _mesh("tree", 90, model_id=700)
        lod, twin = _mesh("LODhouse", model_id=lod_id), _mesh("LODhouse.001", model_id=500)
        other = _mesh("LODhouse.002", 40, model_id=700)
        models, _p, notes = _collect(monkeypatch, [house, tree, lod, twin, other],
                                     [house, tree])
        h = models["house"]
        assert h.lod is lod and h.lod_objs == [lod]
        text = " | ".join(t for _l, t in notes)
        assert "«house»" in text and "LODhouse.001" in text
        assert "«tree»" in text and "LODhouse.002" in text
    # The chosen LOD itself with another exported model's ID → no LOD.
    house, tree = _mesh("house", model_id=500), _mesh("tree", 90, model_id=700)
    lod = _mesh("LODhouse", model_id=700)
    models, _p, notes = _collect(monkeypatch, [house, tree, lod], [house, tree])
    assert models["house"].lod is None and "LODhouse" in notes[0][1]


def test_collect_copy_with_its_own_other_lod_is_reported(monkeypatch):
    """One LOD per model: a copy pointing at a LOD of another name gets the
    model's LOD in its IPL row — said in the report, not silently."""
    lod, alt = _mesh("LODhouse"), _mesh("LODhouse_alt", 50)
    house, house2 = _mesh("house"), _mesh("house.001", 50, lod_object=alt)
    models, _p, notes = _collect(monkeypatch, [house, house2, lod, alt], [house, house2])
    assert models["house"].lod is lod and models["house"].lod_objs == [lod]
    text = " | ".join(t for _l, t in notes)
    assert "house.001" in text and "LODhouse_alt" in text


def test_assign_map_ids_needs_ide_or_ipl():
    """No IDE / IPL written → no Model ID needed: nothing is asked of the
    ID Manager (an empty preset must not block a DFF / COL / TXD export)."""
    from INU_tools.tools.map_export import MapExportPrep, assign_map_ids
    a = _o("a")
    prep = MapExportPrep("x")
    prep.models = {"a": MapModel(key="a", name="a", home=a)}
    prep.plan = {"x/a.dff": ("dff", prep.models["a"]), "x/a.txd": ("txd", [a])}
    assert assign_map_ids(None, prep) == (0, [], '')
    assert a.inu.model_id == 0


def test_map_export_report_summary_last():
    lines = map_export_report({
        "models": 2, "placements": 3, "dff": 2, "lod": 1, "ipl": 2, "rows": 5,
        "pair": True, "notes": [("WARNING", "x"), ("WARNING", "x"), ("INFO", "y")]})
    assert [t for _l, t in lines[:2]] == ["x", "y"]
    assert "_stream0" in lines[2][1]
    assert lines[-1][0] == "WARNING" and lines[-1][1].startswith("Моделей 2, расстановок 3")


# ── Export Map: spheres / boxes of a model's collision ───────────────

class _Empty(types.SimpleNamespace):
    """An EMPTY; ``in`` reads its ID props (``'dff_frame_pos' in obj``)."""
    def __contains__(self, key):
        return key in self.props


def _prim(name, parent=None, kind="SPHERE", **props):
    return _Empty(name=name, type="EMPTY", empty_display_type=kind, parent=parent,
                  props=props, matrix_world=_Matrix(_Loc(0.0, 0.0)))


@pytest.fixture
def prim_check(monkeypatch):
    """ops/dff_export imports bpy_extras & co. at module level: its real
    _is_col_primitive_empty is pulled out by AST."""
    import ast
    path = ROOT / "INU_tools" / "ops" / "dff_export.py"
    fn = next(n for n in ast.parse(path.read_text(encoding="utf-8")).body
              if isinstance(n, ast.FunctionDef) and n.name == "_is_col_primitive_empty")
    stub = types.ModuleType("INU_tools.ops.dff_export")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), stub.__dict__)
    monkeypatch.setitem(sys.modules, "INU_tools.ops.dff_export", stub)


def test_collect_col_spheres_boxes_go_with_the_collision(monkeypatch, prim_check):
    """Spheres / boxes are the model's collision (col_export measures them
    from the COL mesh passed with them): the children of the chosen COL
    mesh (Import Map) whatever their name, loose ones named after the model
    (Import COL, one parented to the DFF) — not a «.001» copy, not the
    children of a COL copy left out, not a frame dummy or a plain empty."""
    house, house2 = _mesh("house"), _mesh("house.001", 50)
    col, col2 = _mesh("house_COL", textured=False), _mesh("house_COL.001", 50, textured=False)
    child = _prim("house_sphere_0", parent=col)
    moved = _prim("lamp_box_7", parent=col, kind="CUBE")           # the parent wins
    copy_child = _prim("house_sphere_0.001", parent=col2)
    copy_named = _prim("house_box_1", parent=col2, kind="CUBE")    # the copy's
    loose = _prim("House_box_0", kind="CUBE")
    loose_dup = _prim("house_box_0.001", kind="CUBE")
    on_dff = _prim("house_sphere_3", parent=house)
    dummy = _prim("house_box_2", kind="CUBE", dff_frame_pos=(0.0, 0.0, 0.0))
    axes = _prim("house_sphere_4", kind="PLAIN_AXES")
    lamp, lamp_ball = _mesh("lamp", 100), _prim("lamp_sphere_0")    # no mesh at all
    scene = [house, house2, col, col2, lamp, child, moved, copy_child, copy_named,
             loose, loose_dup, on_dff, dummy, axes, lamp_ball]
    models, _p, _n = _collect(monkeypatch, scene, [house, house2, lamp])
    assert models["house"].cols == [col, child, moved, loose, on_dff]
    assert models["lamp"].cols == [lamp_ball]


def test_prims_only_models_get_their_col(monkeypatch, prim_check, tmp_path):
    """A model of spheres / boxes only — under Import Map's mesh without
    faces, under its shadow mesh, or loose — is written a .col (own file or
    a library record) and isn't reported as «no collision»."""
    from INU_tools.tools import map_export
    from INU_tools.ops import map_link
    lampx, holder = _mesh("lampx"), _mesh("lampx_COL", textured=False)
    holder.inu.type = "COL"
    box = _prim("lampx_box_0", parent=holder, kind="CUBE")
    bin_, sha = _mesh("bin", 30), _mesh("bin_sha", 30, textured=False)
    ball = _prim("bin_sphere_0", parent=sha)
    post, ring = _mesh("post", 60), _prim("post_sphere_0")
    bare = _mesh("bare", 90)
    ctx = types.SimpleNamespace(scene=types.SimpleNamespace(
        objects=[lampx, holder, box, bin_, sha, ball, post, ring, bare],
        inu_settings=types.SimpleNamespace()))
    for fn in (map_export.get_model_type, map_link.LodIndex.__init__):
        monkeypatch.setattr(fn.__globals__["bpy"], "context", ctx, raising=False)
    sel = [lampx, bin_, post, bare]
    prep = map_export.prepare_map_export(ctx, str(tmp_path), sel)
    ms = prep.models
    assert ms["lampx"].cols == [holder, box] and ms["bin"].cols == [sha, ball]
    assert ms["post"].cols == [ring] and ms["bare"].cols == []
    cols = {p for p in _rel(prep.plan, tmp_path) if p.endswith(".col")}
    assert cols == {"lampx.col", "bin.col", "post.col"}
    assert prep.plan[str(tmp_path / "post.col")] == ("col", ms["post"])
    bare_note = [t for _l, t in prep.notes if t.startswith("Нет коллизии")]
    assert bare_note == ["Нет коллизии (COL) у моделей: bare"]
    lib = map_export.prepare_map_export(ctx, str(tmp_path), sel, col_library=True)
    kind, with_col = lib.plan[str(tmp_path / "district.col")]
    assert kind == "col_lib" and [m.name for m in with_col] == ["lampx", "bin", "post"]
