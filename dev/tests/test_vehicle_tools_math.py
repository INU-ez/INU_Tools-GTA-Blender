# Mirror L↔R and Vehicle Scale — the frame math behind both, on numpy.
#
# Mirror L↔R set basis @ diag(−1,1,1,1): only the local X axis flipped, the
# position did not, so wheel_rf_dummy landed on top of wheel_lf_dummy with a
# negative scale. It now mirrors in the parent's space (S @ local @ S: x → −x,
# det +1), a child of a mirrored frame goes under that frame's twin, and a
# mesh copy mirrors its geometry (x → −x exactly, winding reversed, corner
# normals along) and re-keys its reflective-overlay faces to match.
# Vehicle Scale multiplied the root's location too (a car away from the
# origin drifted off) and reset matrix_parent_inverse without folding it in
# (a part parented with Keep Transform jumped, even at ×1).
#
# Both modules import bpy at module level, so the pieces are pulled out by
# AST and run on numpy stand-ins for mathutils matrices.

import ast
import io
import math
import os
import sys
import types

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRAME_HIER = os.path.join(ROOT, "INU_tools", "ops", "frame_hierarchy.py")
VEH_SCALE = os.path.join(ROOT, "INU_tools", "tools", "vehicle_scale.py")
DFF_EXPORT = os.path.join(ROOT, "INU_tools", "ops", "dff_export.py")

S = np.diag((-1.0, 1.0, 1.0, 1.0))


def _cut(path, names, ns):
    """Exec just the named top-level functions/classes of *path* into *ns*."""
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    keep = [n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert {n.name for n in keep} == set(names)
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), ns)
    return ns


# ── numpy stand-ins for mathutils / Blender objects ────────────────────

class _Mat(np.ndarray):
    """4×4 matrix with mathutils' in-place identity()."""

    def __new__(cls, a):
        return np.array(a, dtype=float).view(cls)

    def identity(self):
        self[...] = np.eye(4)


def _T(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return _Mat(m)


def _Rz(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    m = np.eye(4)
    m[:2, :2] = ((c, -s), (s, c))
    return _Mat(m)


_MATHUTILS = types.ModuleType("mathutils")
_MATHUTILS.Matrix = types.SimpleNamespace(
    Diagonal=lambda d: _Mat(np.diag(d)),
    Scale=lambda f, n: _Mat(np.diag((f, f, f, 1.0))),
)


class _Mesh:
    def __init__(self):
        self.users = 1
        self.transforms = []

    def copy(self):
        return _Mesh()

    def transform(self, m):
        self.transforms.append(np.array(m))


class _Obj(dict):
    """Custom props in the dict; identity semantics like bpy objects."""
    __eq__ = object.__eq__
    __hash__ = object.__hash__

    def __init__(self, name, data=None, parent=None, basis=None, pinv=None):
        super().__init__()
        self.name = name
        self.data = data
        self.type = 'EMPTY' if data is None else 'MESH'
        self.parent = parent
        self.children = []
        if parent is not None:
            parent.children.append(self)
        self.matrix_basis = _Mat(np.eye(4) if basis is None else basis)
        self.matrix_parent_inverse = _Mat(np.eye(4) if pinv is None else pinv)
        self.empty_display_type = 'PLAIN_AXES'
        self.empty_display_size = 1.0
        self.scale = (1.0, 1.0, 1.0)
        self.users_collection = []


class _Objects(dict):
    """bpy.data.objects: by name, .get(name, default), .new(name, data)."""

    def new(self, name, data):
        self[name] = _Obj(name, data)
        return self[name]

    def add(self, *a, **kw):
        o = _Obj(*a, **kw)
        self[o.name] = o
        return o


def _world(o):
    m = np.array(o.matrix_basis, dtype=float)
    if o.parent is not None:
        m = _world(o.parent) @ np.array(o.matrix_parent_inverse) @ m
    return m


# ── Mirror L↔R ─────────────────────────────────────────────────────────

@pytest.fixture
def mirror(monkeypatch):
    monkeypatch.setitem(sys.modules, "mathutils", _MATHUTILS)
    objects = _Objects()
    ns = {"bpy": types.SimpleNamespace(
              types=types.SimpleNamespace(Operator=object),
              data=types.SimpleNamespace(objects=objects)),
          "T": lambda s: s}
    _cut(FRAME_HIER, ["_mirror_frame_x", "_mirror_overlay_key",
                      "_frame_depth", "GTATOOLS_OT_frame_mirror_lr"], ns)
    mirrored = []
    ns["_mirror_mesh_x"] = mirrored.append      # bmesh work, not run here

    def run(selected):
        op = ns["GTATOOLS_OT_frame_mirror_lr"]()
        op.report = lambda level, msg: None
        ctx = types.SimpleNamespace(selected_objects=list(selected))
        assert op.execute(ctx) == {'FINISHED'}

    return types.SimpleNamespace(ns=ns, objects=objects, run=run,
                                 mirrored=mirrored)


def test_mirror_frame_flips_position_and_keeps_det(mirror):
    f = mirror.ns["_mirror_frame_x"]
    local = _T(-0.8, 1.2, -0.3) @ _Rz(20)
    out = f(local, S)
    assert np.allclose(out[:3, 3], (0.8, 1.2, -0.3))
    assert np.linalg.det(out[:3, :3]) == pytest.approx(1.0)
    assert np.allclose(out[:3, :3], _Rz(-20)[:3, :3])
    assert np.allclose(f(out, S), local)
    # The old basis @ S: position unchanged, det −1.
    old = local @ S
    assert np.allclose(old[:3, 3], (-0.8, 1.2, -0.3))
    assert np.linalg.det(old[:3, :3]) < 0


def test_wheel_twin_lands_on_the_other_side(mirror):
    car = mirror.objects.add("car")
    lf = mirror.objects.add("wheel_lf_dummy", parent=car,
                            basis=_T(-0.8, 1.2, -0.3))
    lf["dff_frame_flags"] = 0
    mirror.run([lf])
    rf = mirror.objects["wheel_rf_dummy"]
    assert rf.parent is car
    assert rf["dff_frame_flags"] == 0
    w = _world(rf)
    assert np.allclose(w[:3, 3], (0.8, 1.2, -0.3))
    assert np.allclose(w[:3, :3], np.eye(3))


def test_door_part_goes_under_the_twin_dummy(mirror):
    # Car away from the origin and turned; the part was parented with
    # Keep Transform (parent inverse ≠ I) and is listed before its dummy.
    car = mirror.objects.add("car", basis=_T(5.0, -3.0, 0.0) @ _Rz(30))
    dummy = mirror.objects.add("door_lf_dummy", parent=car,
                               basis=_T(-0.9, 0.6, 0.1) @ _Rz(15))
    part = mirror.objects.add("door_lf_ok", data=_Mesh(), parent=dummy,
                              pinv=np.linalg.inv(_T(0.1, 0.0, 0.0)),
                              basis=_T(0.05, -0.5, 0.0) @ _Rz(5))
    mirror.run([part, dummy])

    rd = mirror.objects["door_rf_dummy"]
    rp = mirror.objects["door_rf_ok"]
    assert rd.parent is car
    assert rp.parent is rd                  # not door_lf_dummy
    assert mirror.mirrored == [rp.data]
    wc = _world(car)
    for src, twin in ((dummy, rd), (part, rp)):
        want = wc @ S @ np.linalg.inv(wc) @ _world(src) @ S
        got = _world(twin)
        assert np.allclose(got, want)
        assert np.linalg.det(got[:3, :3]) == pytest.approx(1.0)
        assert np.allclose(twin.matrix_parent_inverse, np.eye(4))


def test_existing_twin_is_left_alone(mirror):
    car = mirror.objects.add("car")
    lb = mirror.objects.add("wheel_lb_dummy", parent=car,
                            basis=_T(-0.8, -1.3, -0.3))
    rb = mirror.objects.add("wheel_rb_dummy", parent=car,
                            basis=_T(0.7, -1.3, -0.3))
    mirror.run([lb])
    assert mirror.objects["wheel_rb_dummy"] is rb
    assert np.allclose(rb.matrix_basis, _T(0.7, -1.3, -0.3))
    assert set(mirror.objects) == {"car", "wheel_lb_dummy", "wheel_rb_dummy"}


def test_overlay_keys_follow_the_mirrored_mesh(mirror):
    # The exporter keys each reflective-overlay face by its rounded vertex
    # positions; the re-keyed entry must equal the key of the same face on
    # the mirrored mesh (x negated exactly in float32, winding reversed) —
    # zeros, ±tiny values and a changed sort order included.
    key = _cut(DFF_EXPORT, ["overlay_face_key"], {})["overlay_face_key"]
    mk = mirror.ns["_mirror_overlay_key"]
    rng = np.random.default_rng(7)
    pts = rng.uniform(-2.0, 2.0, size=(400, 3)).astype(np.float32)
    pts[:40, 0] = 0.0
    pts[40:80, 0] = -0.0
    pts[80:160, 0] = rng.choice(
        np.array([1e-5, -1e-5, 4.9e-5, -4.9e-5, 5e-5, -5e-5, 0.00015],
                 dtype=np.float32), 80)
    verts = [tuple(float(c) for c in p) for p in pts]
    mverts = [(float(-p[0]), float(p[1]), float(p[2])) for p in pts]
    checked = 0
    for a, b, c in rng.integers(0, len(verts), size=(3000, 3)):
        if len({a, b, c}) < 3:
            continue
        assert mk(key(verts, a, b, c)) == key(mverts, a, c, b)
        checked += 1
    assert checked > 2500


# ── Mirror L↔R: the mesh copy (bmesh stand-in) ─────────────────────────

class _BMVert(dict):
    """Shape-layer values by layer; co with settable x/y/z."""

    def __init__(self, co):
        super().__init__()
        self.co = types.SimpleNamespace(x=co[0], y=co[1], z=co[2])


class _BMLoop(dict):
    def __init__(self, vert):
        super().__init__()
        self.vert = vert


class _Layers(dict):
    def new(self, name):
        self[name] = name
        return name


class _Seq(list):
    pass


class _BMesh:
    """from_mesh / to_mesh over _MeshData; loops keep their own data."""

    def from_mesh(self, me):
        self.verts = _Seq(_BMVert(co) for co in me.positions)
        self.verts.layers = types.SimpleNamespace(
            shape=_Layers((n, n) for n in me.shapes))
        for n, cos in me.shapes.items():
            for v, co in zip(self.verts, cos):
                v[n] = tuple(co)
        self.loops = types.SimpleNamespace(layers=types.SimpleNamespace(
            float_vector=_Layers((n, n) for n in me.corner)))
        self.faces = _Seq()
        c = 0
        for poly in me.polys:
            f = types.SimpleNamespace(loops=[])
            for vi in poly:
                lp = _BMLoop(self.verts[vi])
                for n, vals in me.corner.items():
                    lp[n] = tuple(vals[c])
                f.loops.append(lp)
                c += 1
            self.faces.append(f)

    def to_mesh(self, me):
        index = {id(v): i for i, v in enumerate(self.verts)}
        corners = [lp for f in self.faces for lp in f.loops]
        me.positions = [(v.co.x, v.co.y, v.co.z) for v in self.verts]
        me.shapes = {n: [v[n] for v in self.verts] for n in me.shapes}
        me.polys = [[index[id(lp.vert)] for lp in f.loops] for f in self.faces]
        me.corner = {n: [lp[n] for lp in corners]
                     for n in self.loops.layers.float_vector}

    def free(self):
        pass


def _reverse_faces(bm, faces):
    for f in faces:            # like BMesh: l_first stays, the cycle runs back
        f.loops[1:] = f.loops[:0:-1]


class _MeshData(dict):
    """Mesh stand-in: corner → vertex polygons, corner float3 attributes,
    shape keys, loop normals (MeshLoop.normal); ID props in the dict."""

    def __init__(self, positions, polys, normals, authored, shapes):
        super().__init__()
        self.positions, self.polys, self.shapes = positions, polys, shapes
        self.corner = {'inu_authored_normal': authored}
        self.normals = normals
        self.custom = None
        self.has_custom_normals = True
        self.attributes = types.SimpleNamespace(
            get=lambda n: n if n in self.corner else None,
            remove=lambda n: self.corner.pop(n))

    @property
    def loops(self):
        return [types.SimpleNamespace(normal=n) for n in self.normals]

    def normals_split_custom_set(self, normals):
        self.custom = [tuple(n) for n in normals]


def _newell(pts):
    n = np.zeros(3)
    for i, p in enumerate(pts):
        n += np.cross(p, pts[(i + 1) % len(pts)])
    return n


def test_mirror_mesh_copy(monkeypatch):
    import json
    monkeypatch.setitem(sys.modules, "bmesh", types.SimpleNamespace(
        new=_BMesh, ops=types.SimpleNamespace(reverse_faces=_reverse_faces)))
    ns = _cut(FRAME_HIER, ["_mirror_overlay_key", "_mirror_mesh_x"], {})
    key = _cut(DFF_EXPORT, ["overlay_face_key"], {})["overlay_face_key"]

    pos = [(0.0, 0.0, 0.0), (0.5, 0.0, 0.0), (0.5, 1.0, 0.25),
           (-0.0, 1.0, 0.0), (1e-05, 2.0, 0.0)]
    polys = [[0, 1, 2, 3], [3, 2, 4]]
    corners = [(i, vi) for i, p in enumerate(polys) for vi in p]
    nrm = [(0.1 * c + 0.05, 0.2, 0.9) for c in range(len(corners))]
    auth = [(0.3, -0.1 * c, 0.8) for c in range(len(corners))]
    shapes = {"Basis": list(pos),
              "Key 1": [(x + 0.1, y, z) for x, y, z in pos]}
    me = _MeshData(list(pos), [list(p) for p in polys], nrm, auth, shapes)
    me['inu_overlay_faces'] = json.dumps(
        [[key(pos, 3, 2, 4), 2], [key(pos, 0, 1, 2), 1]])

    ns["_mirror_mesh_x"](me)

    # x negated exactly — the sign of zero too (the overlay keys rely on it)
    for (x0, y0, z0), (x1, y1, z1) in zip(pos, me.positions):
        assert (x1, y1, z1) == (-x0, y0, z0)
        assert math.copysign(1.0, x1) == -math.copysign(1.0, x0)
    for n in shapes:
        assert me.shapes[n] == [(-x, y, z) for x, y, z in shapes[n]]
    # winding reversed: every face still faces out, mirrored
    for old, new in zip(polys, me.polys):
        assert sorted(old) == sorted(new) and old != new
        want = S[:3, :3] @ _newell([np.array(pos[v]) for v in old])
        assert np.allclose(_newell([np.array(me.positions[v]) for v in new]),
                           want)
    # corner normals mirrored and still on their own (face, vertex) corner
    src_n = dict(zip(corners, nrm))
    src_a = dict(zip(corners, auth))
    new_corners = [(i, vi) for i, p in enumerate(me.polys) for vi in p]
    assert me.custom == [(-src_n[c][0], src_n[c][1], src_n[c][2])
                         for c in new_corners]
    assert me.corner['inu_authored_normal'] == [
        (-src_a[c][0], src_a[c][1], src_a[c][2]) for c in new_corners]
    assert set(me.corner) == {'inu_authored_normal'}    # temp layer dropped
    # the exporter finds the reflective-overlay faces on the mirrored mesh
    assert json.loads(me['inu_overlay_faces']) == [
        [key(me.positions, 3, 2, 4), 2], [key(me.positions, 0, 1, 2), 1]]


# ── Vehicle Scale ──────────────────────────────────────────────────────

def _scale_tree():
    car = _Obj("car", basis=_T(10.0, 5.0, 0.0) @ _Rz(90))
    chassis = _Obj("chassis_dummy", parent=car, basis=_T(0.0, 0.0, 0.2))
    body = _Obj("chassis", data=_Mesh(), parent=chassis)
    wheel = _Obj("wheel_lf_dummy", parent=car, basis=_T(-0.8, 1.2, -0.3))
    door = _Obj("door_lf_dummy", parent=car,
                basis=_T(-0.9, 0.6, 0.1) @ _Rz(10))
    # Parented with Keep Transform: inverse of the dummy's world at that
    # time, the part's old world as basis.
    w_door = _world(door)
    panel = _Obj("door_lf_ok", data=_Mesh(), parent=door,
                 pinv=np.linalg.inv(w_door),
                 basis=w_door @ _T(0.05, -0.5, 0.0) @ _Rz(3))
    return [car, chassis, body, wheel, door, panel]


@pytest.fixture
def rescale():
    ns = {"Matrix": _MATHUTILS.Matrix, "bpy": types.SimpleNamespace()}
    _cut(VEH_SCALE, ["_walk", "_scaled_local", "_rescale_hierarchy"], ns)
    return ns["_rescale_hierarchy"]


@pytest.mark.parametrize("factor", [2.0, 1.0, 0.5])
def test_scale_about_the_root(rescale, factor):
    tree = _scale_tree()
    before = [_world(o) for o in tree]
    meshes, empties = rescale(tree[0], factor, dummies_only=False)
    assert (meshes, empties) == (2, 4)

    root = before[0][:3, 3]
    assert np.allclose(_world(tree[0]), before[0])          # root stays
    for o, w0 in zip(tree[1:], before[1:]):
        w = _world(o)
        assert np.allclose(w[:3, 3], root + factor * (w0[:3, 3] - root)), o.name
        assert np.allclose(w[:3, :3], w0[:3, :3]), o.name
        assert np.allclose(o.matrix_parent_inverse, np.eye(4)), o.name
    for o in tree:
        if o.data is not None:
            assert len(o.data.transforms) == 1
            assert np.allclose(o.data.transforms[0],
                               np.diag((factor, factor, factor, 1.0)))
