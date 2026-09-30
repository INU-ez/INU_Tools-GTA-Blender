# paths.ipl export used to take every node's properties (width, lanes,
# flags, spawn …) from pn_0_* and write them into all nodes, so a flag set
# on point 3 with path_node_flag never reached the file and the per-node
# values read on import were lost. Each curve point now keeps its own
# pn_<slot>_* (same point → slot mapping as path_node_flag: slots with
# pn_<j>_type > 0 in order); points past the imported slots get node 0's,
# minus its per-point roadblock / traffic-light bits.
#
# path_export imports bpy at module level, so pull the functions out by AST
# and hand them fake curve objects.

import ast
import io
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "INU_tools", "ops", "path_export.py")
sys.path.insert(0, os.path.join(ROOT, "INU_tools"))

from core.paths import (  # noqa: E402
    PathIPLFile, PathIPLGroup, PathIPLNode, write_paths_ipl, read_paths_ipl,
    PATH_FLAG_ROADBLOCK, PATH_FLAG_TRAFFIC_MASK, PATH_FLAG_TRAFFIC_SHIFT,
)


# ── minimal stand-ins for Blender curve objects ────────────────────────

class _Co:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def to_3d(self):
        return self


class _Identity:
    def __matmul__(self, co):
        return co


class _Obj(dict):
    type = 'CURVE'

    def __init__(self, n_points, **props):
        super().__init__(path_type='path_ipl', group_type=1, group_index=0,
                         **props)
        pts = [types.SimpleNamespace(co=_Co(10.0 * k, 5.0, 1.0))
               for k in range(n_points)]
        self.data = types.SimpleNamespace(
            splines=[types.SimpleNamespace(points=pts)])
        self.matrix_world = _Identity()


def _slots(slot_types, per_slot=None):
    """pn_<j>_* as import_paths_ipl stores them; per_slot = {j: {field: v}}."""
    d = {'pn_count': len(slot_types)}
    for j, t in enumerate(slot_types):
        vals = dict(type=t, link=-1, area=0, unk=0.0, width=1, ll=1, rl=1,
                    mw=0, flags=1, spawn=0)
        vals.update((per_slot or {}).get(j, {}))
        for k, v in vals.items():
            d[f'pn_{j}_{k}'] = v
    return d


def _load():
    tree = ast.parse(io.open(MODULE, encoding="utf-8").read())
    names = {"_path_ipl_real_to_full", "_path_ipl_node_props",
             "export_paths_ipl"}
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in keep} == names
    ns = {
        "bpy": types.SimpleNamespace(),
        "PathIPLFile": PathIPLFile, "PathIPLGroup": PathIPLGroup,
        "PathIPLNode": PathIPLNode, "write_paths_ipl": write_paths_ipl,
        "PATH_FLAG_ROADBLOCK": PATH_FLAG_ROADBLOCK,
        "PATH_FLAG_TRAFFIC_MASK": PATH_FLAG_TRAFFIC_MASK,
    }
    exec(compile(ast.Module(body=keep, type_ignores=[]), MODULE, "exec"), ns)
    return ns["export_paths_ipl"]


export_paths_ipl = _load()

NODE0 = dict(width=4, ll=2, rl=2, mw=6, flags=7, spawn=9, unk=0.5, area=0)
NODE3 = dict(flags=1 | PATH_FLAG_ROADBLOCK, width=2, ll=3, unk=5.0, area=1)


def _roundtrip(tmp_path, obj):
    path = tmp_path / "paths.ipl"
    export_paths_ipl(str(path), objects=[obj])
    return read_paths_ipl(str(path)).groups


def _fields(n):
    return (n.area_id, n.unknown, n.width, n.left_lanes, n.right_lanes,
            n.median_width, n.flags, n.spawn_rate)


def test_each_point_keeps_its_own_node(tmp_path):
    obj = _Obj(5, **_slots([2] * 5 + [0] * 7, {0: NODE0, 3: NODE3}))
    g, = _roundtrip(tmp_path, obj)
    real = [n for n in g.nodes if n.node_type > 0]
    assert len(real) == 5
    # Point 3 carries its roadblock flag, width, lanes, unk and area.
    assert _fields(real[3]) == (1, 5.0, 2, 3, 1, 0, 4097, 0)
    assert real[3].flags & PATH_FLAG_ROADBLOCK
    # Node 0 keeps its own values and no longer leaks into the others.
    assert _fields(real[0]) == (0, 0.5, 4, 2, 2, 6, 7, 9)
    assert _fields(real[1]) == (0, 0.0, 1, 1, 1, 0, 1, 0)
    assert [n.link_id for n in real] == [1, 2, 3, 4, -1]


def test_point_past_imported_slots_gets_node0(tmp_path):
    obj = _Obj(6, **_slots([2] * 5 + [0] * 7, {0: NODE0, 3: NODE3}))
    g, = _roundtrip(tmp_path, obj)
    real = [n for n in g.nodes if n.node_type > 0]
    assert len(real) == 6
    # Node 0's width/lanes/flags/spawn; area and unk fall back to 0.
    assert _fields(real[5]) == (0, 0.0, 4, 2, 2, 6, 7, 9)


def test_empty_slot_shifts_mapping_like_path_node_flag(tmp_path):
    # Slot 2 is empty padding: point 2 → slot 3, point 3 → slot 4.
    obj = _Obj(4, **_slots([2, 2, 0, 2, 2] + [0] * 7,
                           {0: NODE0, 3: NODE3, 4: dict(flags=33)}))
    g, = _roundtrip(tmp_path, obj)
    real = [n for n in g.nodes if n.node_type > 0]
    assert _fields(real[2]) == (1, 5.0, 2, 3, 1, 0, 4097, 0)
    assert real[3].flags == 33


def test_split_groups_keep_per_node_values(tmp_path):
    # 12 points → groups of 10 + 2; point 10 is node 0 of the second group.
    obj = _Obj(12, **_slots([2] * 12, {0: NODE0, 10: NODE3}))
    g0, g1 = _roundtrip(tmp_path, obj)
    assert _fields(g1.nodes[0]) == (1, 5.0, 2, 3, 1, 0, 4097, 0)
    assert _fields(g1.nodes[1]) == (0, 0.0, 1, 1, 1, 0, 1, 0)
    # Synthesized external links still use node 0's values.
    ext = [n for n in g0.nodes if n.node_type == 1]
    assert len(ext) == 1 and ext[0].flags == 7 and ext[0].width == 4


def test_node0_toggles_do_not_leak_past_slots(tmp_path):
    # Add Path (IPL) makes 2 slots; the curve is then drawn out to 6 points
    # and point 0 gets a roadblock + traffic light via path_node_flag.
    light = 1 << PATH_FLAG_TRAFFIC_SHIFT
    obj = _Obj(6, **_slots([2, 2], {0: dict(
        width=4, flags=1 | PATH_FLAG_ROADBLOCK | light)}))
    g, = _roundtrip(tmp_path, obj)
    real = [n for n in g.nodes if n.node_type > 0]
    assert [n.flags for n in real] == [1 | PATH_FLAG_ROADBLOCK | light,
                                       1, 1, 1, 1, 1]
    # The rest of node 0 (width, speed bits) still fills the extra points.
    assert [n.width for n in real] == [4, 1, 4, 4, 4, 4]


def test_external_link_drops_node0_toggles(tmp_path):
    obj = _Obj(12, **_slots([2] * 12, {0: dict(
        flags=3 | PATH_FLAG_ROADBLOCK | PATH_FLAG_TRAFFIC_MASK)}))
    g0, g1 = _roundtrip(tmp_path, obj)
    assert g0.nodes[0].flags & PATH_FLAG_ROADBLOCK
    ext = [n for n in g0.nodes + g1.nodes if n.node_type == 1]
    assert len(ext) == 2 and all(n.flags == 3 for n in ext)


def test_curve_without_slots_uses_old_defaults(tmp_path):
    g, = _roundtrip(tmp_path, _Obj(3))
    real = [n for n in g.nodes if n.node_type > 0]
    assert [_fields(n) for n in real] == [(0, 0.0, 1, 1, 1, 0, 1, 0)] * 3
