"""Run the cutter's bake with mesh data; Blender's boolean step is stubbed."""

import ast
import types
from pathlib import Path

import numpy as np
import pytest

from test_prelight_color_tools import _Mesh, _Compat


class _Vector(np.ndarray):
    def __new__(cls, co):
        return np.asarray(co, dtype=float).view(cls)

    @property
    def length(self):
        return float(np.linalg.norm(self))


class _Matrix:
    def inverted(self):
        return self

    def __matmul__(self, co):
        return _Vector(co)

    def __array__(self, dtype=None, copy=None):
        return np.eye(4, dtype=dtype)


class _Materials(list):
    def pop(self, index=-1):
        return super().pop(index)


def _bake(monkeypatch, mesh, radius):
    path = Path(__file__).parents[2] / "INU_tools/ops/light_ops.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    method = next(n for c in tree.body if isinstance(c, ast.ClassDef)
                  for n in c.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_knife_cut")
    method.decorator_list = []
    noop = lambda *args, **kwargs: None
    bm = types.SimpleNamespace(verts=[], faces=[], from_mesh=noop,
                               to_mesh=noop, free=noop)
    monkeypatch.setitem(__import__("sys").modules, "bmesh",
                        types.SimpleNamespace(new=lambda: bm,
                            ops=types.SimpleNamespace(remove_doubles=noop,
                                recalc_face_normals=noop, delete=noop)))
    monkeypatch.setitem(__import__("sys").modules, "mathutils",
                        types.SimpleNamespace(Vector=_Vector, Matrix=None))
    material = types.SimpleNamespace(users=0)
    bpy = types.SimpleNamespace(
        data=types.SimpleNamespace(materials=types.SimpleNamespace(
            new=lambda name: material, remove=noop)),
        ops=types.SimpleNamespace(
            object=types.SimpleNamespace(mode_set=noop),
            mesh=types.SimpleNamespace(select_all=noop, intersect=noop)))
    ns = {"bpy": bpy, "compat": _Compat}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), ns)
    mesh.materials = _Materials()
    mesh.update = noop
    ground = types.SimpleNamespace(data=mesh, matrix_world=_Matrix(),
        bound_box=[(-1, -1, 0), (1, 1, 0)], select_set=noop)
    ctx = types.SimpleNamespace(selected_objects=[],
        view_layer=types.SimpleNamespace(objects=types.SimpleNamespace(active=None)))
    return ns["_knife_cut"](None, ctx, ground, _Vector((0, 0, 0)),
        radius, 8, [], (0.3, 0.4, 0.2), rot=np.eye(3))


def test_cut_bake_changes_rgb_and_preserves_painted_alpha(monkeypatch):
    mesh = _Mesh(rgb=(0.1, 0.2, 0.3))
    colors = mesh.active.data.arrays["color"]
    colors[:, 3] = np.linspace(0, 1, len(colors))
    before = mesh.colors().copy()
    assert _bake(monkeypatch, mesh, 2.0) == 6
    assert np.all(mesh.colors()[:, :3] > before[:, :3])
    assert mesh.colors()[:, 3] == pytest.approx(before[:, 3])


def test_cut_new_layer_is_opaque_even_outside_the_radius(monkeypatch):
    mesh = _Mesh(layer=False)
    assert _bake(monkeypatch, mesh, 0.1) == 0
    assert mesh.colors()[:, 3] == pytest.approx(1.0)
    assert mesh.colors()[:, :3] == pytest.approx(0.0)
