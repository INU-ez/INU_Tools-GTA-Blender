# water.dat holds only triangles and quads. export_water used to drop every
# face with more vertices silently — a water plane cut with the knife or
# dissolved into an n-gon lost part of its surface in the game while the
# operator still reported success. It now counts them and returns
# (count, skipped); the operator warns when skipped > 0.
#
# water_export imports bpy / bmesh at module level, so pull the function out
# by AST and hand it fake bpy / bmesh objects.

import ast
import io
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "INU_tools", "ops", "water_export.py")
sys.path.insert(0, os.path.join(ROOT, "INU_tools"))

from core.water import (  # noqa: E402
    WaterFile, WaterPolygon, WaterVertex, write_water, read_water,
)


# ── minimal stand-ins for bmesh / bpy objects ──────────────────────────

class _Vert:
    def __init__(self, x, y, z=0.0):
        self.co = types.SimpleNamespace(x=x, y=y, z=z)


class _Face:
    def __init__(self, *coords):
        self.verts = [_Vert(x, y) for x, y in coords]


class _Verts(list):
    layers = types.SimpleNamespace(float={})  # .get(name) → None

    def ensure_lookup_table(self):
        pass


class _BM:
    # obj.data here is simply the list of fake faces.
    def from_mesh(self, mesh):
        self.faces = mesh
        self.verts = _Verts(v for f in mesh for v in f.verts)

    def free(self):
        pass


class _Identity:
    def __matmul__(self, co):
        return co


class _Obj(dict):
    def __init__(self, faces):
        super().__init__(water_flag=1)
        self.data = faces
        self.matrix_world = _Identity()


def _load():
    tree = ast.parse(io.open(MODULE, encoding="utf-8").read())
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "export_water"]
    ns = {
        "bpy": types.SimpleNamespace(),
        "bmesh": types.SimpleNamespace(new=_BM),
        "WaterFile": WaterFile, "WaterPolygon": WaterPolygon,
        "WaterVertex": WaterVertex, "write_water": write_water,
    }
    exec(compile(ast.Module(body=keep, type_ignores=[]), MODULE, "exec"), ns)
    return ns["export_water"]


export_water = _load()


def test_ngon_is_counted_not_silently_dropped(tmp_path):
    faces = [
        _Face((0, 0), (10, 0), (10, 10)),                      # triangle
        _Face((0, 0), (10, 0), (10, 10), (0, 10)),             # quad
        _Face((0, 0), (10, 0), (15, 5), (10, 10), (0, 10)),    # 5-gon
    ]
    path = tmp_path / "water.dat"
    assert export_water(str(path), objects=[_Obj(faces)]) == (2, 1)
    assert len(read_water(str(path)).polygons) == 2


def test_no_ngons_skipped_is_zero(tmp_path):
    faces = [_Face((0, 0), (10, 0), (10, 10), (0, 10))]
    path = tmp_path / "water.dat"
    assert export_water(str(path), objects=[_Obj(faces)]) == (1, 0)
