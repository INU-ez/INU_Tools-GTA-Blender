# COL spheres/boxes live in the model's space, measured from the COL mesh.
#
# ops/col_export.py: _collect_mesh writes the mesh in its own local space
# (object location/rotation = the model's placement, dropped), so the
# primitives are taken relative to that mesh (_prim_anchor): moving the
# whole collision leaves the file unchanged, as in Max. Without a mesh the
# old raw obj.location path stays.
# ops/col_import.py: a single-file import onto a placed scene model moves
# the mesh AND its spheres/boxes (_place_on_models); a model without a
# mesh stays put, matching the raw obj.location export.
# Library grouping: an unparented «x_sphere_0» joins model x.
#
# Both modules import bpy at module level, so the functions are pulled out
# by AST (with whatever module-level helpers they call).

import ast
import io
import os
import re
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OPS = os.path.join(ROOT, "INU_tools", "ops")
sys.path.insert(0, os.path.join(ROOT, "INU_tools"))

import core.col as col  # noqa: E402
from core.col import ColModel, write_col, read_col  # noqa: E402
from core.model_classify import classify_model  # noqa: E402


def _load(path, wanted, ns):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    need, todo = set(), list(wanted)
    while todo:
        name = todo.pop()
        if name in need:
            continue
        need.add(name)
        for sub in ast.walk(defs[name]):
            if isinstance(sub, ast.Name) and sub.id in defs:
                todo.append(sub.id)
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name in need]
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), ns)
    return ns


_PKG = "_colprim_pkg"
EXP = _load(os.path.join(OPS, "col_export.py"),
            {"_prim_local_xyz", "_prim_box_local", "_prim_base_name",
             "_prim_anchor", "_collect_sphere", "_collect_box",
             "_group_objects_by_base", "_is_import_prim"},
            dict({k: getattr(col, k) for k in dir(col) if not k.startswith("__")},
                 T=lambda s: s, __package__=_PKG + ".ops",
                 __name__=_PKG + ".ops.col_export"))
IMP = _load(os.path.join(OPS, "col_import.py"), {"_place_on_models"}, {})

local_xyz = EXP["_prim_local_xyz"]
box_local = EXP["_prim_box_local"]
base_name = EXP["_prim_base_name"]

IDENT = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
RZ90 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))   # rows


def _approx(a, b):
    return all(x == pytest.approx(y, abs=1e-9) for x, y in zip(a, b))


# ── stand-ins for bpy / mathutils ────────────────────────────────────────

class _V:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __add__(self, o):
        return _V(self.x + o.x, self.y + o.y, self.z + o.z)

    def copy(self):
        return _V(self.x, self.y, self.z)


class _Q:
    def __init__(self, rows):
        self.rows = rows

    def to_matrix(self):
        return [tuple(r) for r in self.rows]


class _M3:
    def __init__(self, cols):
        self.col = cols


class _Mat:
    """What the collectors read off a mathutils world matrix: T·R·S."""

    def __init__(self, t=(0.0, 0.0, 0.0), rot=IDENT, scale=(1.0, 1.0, 1.0)):
        self.t, self.rot, self.s = tuple(t), rot, tuple(scale)

    @property
    def translation(self):
        return _V(*self.t)

    def _rot_size(self):
        # mathutils mat3_to_rot_size: column lengths, and with det < 0 the
        # rotation AND all three sizes are negated (scale (-1,1,1) → -1,-1,-1)
        neg = -1.0 if self.s[0] * self.s[1] * self.s[2] < 0 else 1.0
        rot = [tuple(self.rot[i][j] * (1.0 if self.s[j] >= 0 else -1.0) * neg
                     for j in range(3)) for i in range(3)]
        return rot, tuple(abs(v) * neg for v in self.s)

    def decompose(self):
        rot, size = self._rot_size()
        return _V(*self.t), _Q(rot), _V(*size)

    def to_scale(self):
        return _V(*self._rot_size()[1])

    def to_3x3(self):
        return _M3([tuple(self.rot[i][j] * self.s[j] for i in range(3))
                    for j in range(3)])


class _Obj:
    """Hashable fake bpy object (SimpleNamespace is not hashable)."""

    def __init__(self, name, type='EMPTY', inu_type='OBJ', parent=None,
                 location=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0),
                 display='SPHERE', size=1.0, mw=None):
        self.name, self.type, self.parent = name, type, parent
        self.inu = types.SimpleNamespace(type=inu_type)
        self.location, self.scale = _V(*location), _V(*scale)
        self.empty_display_type, self.empty_display_size = display, size
        self.matrix_world = mw or _Mat(location, IDENT, scale)


# ── pure math ────────────────────────────────────────────────────────────

def test_local_xyz_translation_only():
    assert local_xyz((101.0, 50.0, 2.0), (100.0, 50.0, 0.0), IDENT) == (1.0, 0.0, 2.0)


def test_local_xyz_rotated_anchor():
    # model turned +90° about Z: its +X points along world +Y
    assert _approx(local_xyz((100.0, 1.0, 0.0), (100.0, 0.0, 0.0), RZ90),
                   (1.0, 0.0, 0.0))


def test_box_local_identity_matches_loc_pm_scale():
    lo, hi = box_local((1.25, -2.5, 0.75),
                       ((2.0, 0, 0), (0, 0.5, 0), (0, 0, 3.0)),
                       (0.0, 0.0, 0.0), IDENT)
    assert lo == (1.25 - 2.0, -2.5 - 0.5, 0.75 - 3.0)
    assert hi == (1.25 + 2.0, -2.5 + 0.5, 0.75 + 3.0)


def test_box_local_rotated_anchor_swaps_extents():
    # world-aligned box 2×1×1 (half) next to a model turned 90° → in model
    # space it lies along Y
    lo, hi = box_local((10.0, 1.0, 0.0),
                       ((2.0, 0, 0), (0, 1.0, 0), (0, 0, 1.0)),
                       (10.0, 0.0, 0.0), RZ90)
    assert _approx(lo, (0.0, -2.0, -1.0))
    assert _approx(hi, (2.0, 2.0, 1.0))


@pytest.mark.parametrize("name, want", [
    ("lamp_sphere_0", "lamp"),
    ("LAMP_Box_12", "LAMP"),
    ("lamp_sphere_0.001", "lamp"),
    ("wheel", "wheel"),
    ("wheel.002", "wheel"),
    ("my_sphere_x", "my_sphere_x"),
])
def test_prim_base_name(name, want):
    assert base_name(name) == want


# ── anchor choice ────────────────────────────────────────────────────────

def test_anchor_col_mesh_wins_over_shadow():
    sha = _Obj("x_sha", "MESH", "SHA")
    colm = _Obj("x_COL", "MESH", "COL")
    assert EXP["_prim_anchor"]([sha, _Obj("x_sphere_0"), colm]) is colm


def test_anchor_shadow_only():
    sha = _Obj("x_sha", "MESH")        # shadow by name suffix alone
    assert EXP["_prim_anchor"]([_Obj("x_sphere_0"), sha]) is sha


def test_anchor_none_without_mesh():
    assert EXP["_prim_anchor"]([_Obj("x_sphere_0"), _Obj("x_box_0")]) is None


# ── collectors with an anchor ────────────────────────────────────────────

def test_sphere_relative_to_moved_mesh():
    anchor = _Obj("x_COL", "MESH", "COL", location=(100.0, 50.0, 0.0))
    sph = _Obj("x_sphere_0", location=(101.0, 50.0, 2.0), size=0.5)
    m = ColModel(version=3, model_name="x")
    EXP["_collect_sphere"](sph, m, anchor)
    s = m.spheres[0]
    assert (s.center.x, s.center.y, s.center.z) == (1.0, 0.0, 2.0)
    assert s.radius == 0.5


def test_sphere_rotated_mesh():
    anchor = _Obj("x_COL", "MESH", mw=_Mat((100.0, 0.0, 0.0), RZ90))
    sph = _Obj("x_sphere_0", location=(100.0, 1.0, 0.0), size=0.5)
    m = ColModel(version=3, model_name="x")
    EXP["_collect_sphere"](sph, m, anchor)
    c = m.spheres[0].center
    assert _approx((c.x, c.y, c.z), (1.0, 0.0, 0.0))


def test_sphere_child_of_scaled_mesh_scales_like_verts():
    # mesh scale 2 → _collect_mesh doubles the verts; a child sphere at
    # local (1,0,0) sits at world (2,0,0) with world scale 2
    anchor = _Obj("x_COL", "MESH", mw=_Mat(scale=(2.0, 2.0, 2.0)))
    sph = _Obj("x_sphere_0", size=0.5, parent=anchor,
               mw=_Mat((2.0, 0.0, 0.0), IDENT, (2.0, 2.0, 2.0)))
    m = ColModel(version=3, model_name="x")
    EXP["_collect_sphere"](sph, m, anchor)
    s = m.spheres[0]
    assert (s.center.x, s.center.y, s.center.z, s.radius) == (2.0, 0.0, 0.0, 1.0)


def test_sphere_mirrored_keeps_positive_radius():
    # wheel sphere Shift+D, S X -1: world scale (-1,1,1) → to_scale() gives
    # (-1,-1,-1); a negative radius never collides in game
    anchor = _Obj("x_COL", "MESH", "COL")
    sph = _Obj("x_sphere_1", location=(-1.0, 0.0, 0.0),
               scale=(-1.0, 1.0, 1.0), size=0.4)
    m = ColModel(version=3, model_name="x")
    EXP["_collect_sphere"](sph, m, anchor)
    s = m.spheres[0]
    assert s.radius == pytest.approx(0.4)
    assert (s.center.x, s.center.y, s.center.z) == (-1.0, 0.0, 0.0)


def test_sphere_on_mirrored_mesh_follows_mesh_verts():
    # mesh S X -1: _collect_mesh writes verts × to_scale() = −v, so a sphere
    # sitting on vertex v must come out at −v too
    anchor = _Obj("x_COL", "MESH", mw=_Mat(scale=(-1.0, 1.0, 1.0)))
    sph = _Obj("x_sphere_0", location=(-1.0, 2.0, 3.0), size=0.5)
    m = ColModel(version=3, model_name="x")
    EXP["_collect_sphere"](sph, m, anchor)
    s = m.spheres[0]
    assert _approx((s.center.x, s.center.y, s.center.z), (-1.0, -2.0, -3.0))
    assert s.radius == pytest.approx(0.5)


def test_box_rotated_mesh():
    anchor = _Obj("x_COL", "MESH", mw=_Mat((10.0, 0.0, 0.0), RZ90))
    box = _Obj("x_box_0", display='CUBE', location=(10.0, 1.0, 0.0),
               scale=(2.0, 1.0, 1.0))
    m = ColModel(version=3, model_name="x")
    EXP["_collect_box"](box, m, anchor)
    b = m.boxes[0]
    assert _approx((b.bb_min.x, b.bb_min.y, b.bb_min.z), (0.0, -2.0, -1.0))
    assert _approx((b.bb_max.x, b.bb_max.y, b.bb_max.z), (2.0, 2.0, 1.0))


def test_mesh_at_origin_same_bytes_as_legacy():
    # untouched import (mesh at 0,0,0): anchor path == old obj.location path
    anchor = _Obj("x_COL", "MESH", "COL")
    sph = _Obj("x_sphere_0", location=(0.1234567, -3.3, 7.77), size=0.618)
    box = _Obj("x_box_0", display='CUBE', location=(1.1, 2.2, -0.3),
               scale=(0.45, 1.7, 0.05))
    new, old = ColModel(version=3, model_name="x"), ColModel(version=3, model_name="x")
    for m, a in ((new, anchor), (old, None)):
        EXP["_collect_sphere"](sph, m, a)
        EXP["_collect_box"](box, m, a)
    assert write_col([new], target_game="SA") == write_col([old], target_game="SA")


def test_import_then_export_round_trip_after_move():
    # import places mesh + sphere on the model at (100,50,0); export gives
    # the sphere back in COL space
    src = ColModel(version=3, model_name="x")
    src.spheres.append(col.ColSphere(center=col.Vec3(1.5, -2.0, 0.25),
                                     radius=0.75, surface=col.Surface()))
    anchor = _Obj("x_COL", "MESH", "COL")
    sph = _Obj("x_sphere_0", location=(1.5, -2.0, 0.25), size=0.75)
    placed = IMP["_place_on_models"](
        [("x", [anchor, sph])],
        {"x": _Obj("x", "MESH", mw=_Mat((100.0, 50.0, 0.0)))}, {anchor, sph})
    assert placed == 1
    for o in (anchor, sph):
        o.matrix_world = _Mat(tuple(o.location), IDENT, tuple(o.scale))
    m = ColModel(version=3, model_name="x")
    EXP["_collect_sphere"](sph, m, anchor)
    got = read_col(write_col([m], target_game="SA"))[0].spheres[0]
    want = read_col(write_col([src], target_game="SA"))[0].spheres[0]
    assert (got.center.x, got.center.y, got.center.z) == pytest.approx(
        (want.center.x, want.center.y, want.center.z), abs=1e-5)
    assert got.radius == want.radius


# ── import placement ─────────────────────────────────────────────────────

def test_place_moves_mesh_and_primitives():
    mesh = _Obj("x_COL", "MESH", "COL")
    sha = _Obj("x_sha", "MESH", "SHA")
    sph = _Obj("x_sphere_0", location=(1.0, 2.0, 3.0))
    box = _Obj("x_box_0", display='CUBE', location=(-1.0, 0.0, 0.5))
    child = _Obj("x_sphere_1", location=(0.5, 0.0, 0.0), parent=mesh)
    other = _Obj("y_COL", "MESH", "COL", location=(4.0, 4.0, 4.0))
    model = _Obj("x_dff", "MESH", mw=_Mat((100.0, 50.0, 10.0)))
    own = {mesh, sha, sph, box, child, other}
    n = IMP["_place_on_models"](
        [("x", [mesh, sha, sph, box, child]), ("y", [other])],
        {"x_dff": model}, own)
    assert n == 1
    assert tuple(mesh.location) == (100.0, 50.0, 10.0)
    assert tuple(sha.location) == (100.0, 50.0, 10.0)
    assert tuple(sph.location) == (101.0, 52.0, 13.0)
    assert tuple(box.location) == (99.0, 50.0, 10.5)
    assert tuple(child.location) == (0.5, 0.0, 0.0)     # follows its parent
    assert tuple(other.location) == (4.0, 4.0, 4.0)     # no scene model «y»


def test_place_skips_own_objects_as_match():
    mesh = _Obj("x", "MESH", "COL")
    sph = _Obj("x_sphere_0", location=(1.0, 0.0, 0.0))
    n = IMP["_place_on_models"]([("x", [mesh, sph])], {"x": mesh}, {mesh, sph})
    assert n == 0
    assert tuple(sph.location) == (1.0, 0.0, 0.0)


def test_place_skips_model_without_mesh_and_round_trips():
    # lamp.col = one box, no mesh; DFF «lamp» at (100,50,0). Export has no
    # mesh to measure from (raw obj.location), so import must not move it.
    box = _Obj("lamp_box_0", display='CUBE', location=(0.5, 0.0, 1.0),
               scale=(0.2, 0.2, 1.0))
    n = IMP["_place_on_models"](
        [("lamp", [box])],
        {"lamp": _Obj("lamp", "MESH", mw=_Mat((100.0, 50.0, 0.0)))}, {box})
    assert n == 0
    assert tuple(box.location) == (0.5, 0.0, 1.0)
    m = ColModel(version=3, model_name="lamp")
    EXP["_collect_box"](box, m, EXP["_prim_anchor"]([box]))
    b = m.boxes[0]
    assert _approx((b.bb_min.x, b.bb_min.y, b.bb_min.z), (0.3, -0.2, 0.0))
    assert _approx((b.bb_max.x, b.bb_max.y, b.bb_max.z), (0.7, 0.2, 2.0))


# ── library grouping ─────────────────────────────────────────────────────

_STRIP_DUP = re.compile(r'\.\d{3,}$')


@pytest.fixture
def fake_pkg(monkeypatch):
    """`from ..tools.model_utils import get_model_type` inside
    _group_objects_by_base → a stand-in over the pure classifier."""
    mu = types.ModuleType(_PKG + ".tools.model_utils")
    mu.get_model_type = lambda o: classify_model(
        _STRIP_DUP.sub('', o.name), has_texture=False, inu_type=o.inu.type)
    for name, mod in ((_PKG, types.ModuleType(_PKG)),
                      (_PKG + ".ops", types.ModuleType(_PKG + ".ops")),
                      (_PKG + ".tools", types.ModuleType(_PKG + ".tools")),
                      (_PKG + ".tools.model_utils", mu)):
        mod.__path__ = []
        monkeypatch.setitem(sys.modules, name, mod)


def test_group_primitives_join_their_model(fake_pkg):
    x_col = _Obj("x_COL", "MESH", "COL")
    x_sha = _Obj("x_sha", "MESH", "SHA")
    s0 = _Obj("x_sphere_0")
    b1 = _Obj("x_box_1.001", display='CUBE')
    child = _Obj("wheel_rf", parent=x_col)
    y_s = _Obj("y_sphere_0")
    stray = _Obj("Empty.003", display='PLAIN_AXES')
    groups = EXP["_group_objects_by_base"](
        [x_col, x_sha, s0, b1, child, y_s, stray])
    assert list(groups) == ["x", "y", "Empty"]
    assert groups["x"] == [x_col, x_sha, s0, b1, child]
    assert groups["y"] == [y_s]


@pytest.mark.parametrize("name, type, want", [
    ("lamp_box_0", "EMPTY", True),
    ("lamp_Sphere_3.001", "EMPTY", True),
    ("Empty.003", "EMPTY", False),
    ("a.b", "EMPTY", False),
    ("my_sphere_x", "EMPTY", False),
    ("x_box_0", "MESH", False),
])
def test_is_import_prim(name, type, want):
    # split Export COL writes a spheres/boxes-only model only if it is one
    # from an import, not a stray empty
    assert EXP["_is_import_prim"](_Obj(name, type)) is want
