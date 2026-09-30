# Scatter Color / Листва (LIGHT-11, LIGHT-12 / BUG-17 в BLENDER_VS_MAX.md):
#  * цвета палитры — FloatVectorProperty COLOR_GAMMA (sRGB), а слой пишется
#    через .color (линейный): палитра 0.5 давала байт 188 вместо 128 —
#    в игре светлее выбранного. Операторы переводят sRGB → линейный
#    (кисть — только если её RNA-подтип COLOR_GAMMA);
#  * инструменты цвета не трогают альфу слоя: Листва ставила 1.0, Scatter
#    тянул альфу к 1.0 — стиралась нарисованная прозрачность вершин.
#
# tools/prelight.py и ops/light_ops.py импортируют bpy на уровне модуля,
# поэтому функции и операторы вынимаются через AST (как в
# test_prelight_bake_fixes.py) и гоняются на подставных объектах.

import ast
import builtins
import importlib.util
import io
import os
import sys
import types

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRELIGHT = os.path.join(ROOT, "INU_tools", "tools", "prelight.py")
LIGHT_OPS = os.path.join(ROOT, "INU_tools", "ops", "light_ops.py")
TIMECYC = os.path.join(ROOT, "INU_tools", "core", "timecyc.py")

_spec = importlib.util.spec_from_file_location("_inu_timecyc_for_test", TIMECYC)
timecyc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(timecyc)           # core/timecyc.py: только os, re

ALPHA = 0.3


def _tree(path):
    return ast.parse(io.open(path, encoding="utf-8").read())


def _extract(path, wanted, ns):
    keep = []
    for node in _tree(path).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name in wanted:
                keep.append(node)
    found = {n.name for n in keep}
    assert found == set(wanted), sorted(set(wanted) - found)
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), ns)
    return ns


def _builtins():
    """`from ..core.timecyc import srgb_to_linear` внутри _srgb3_to_linear."""
    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 2 and name == "core.timecyc":
            return timecyc
        return builtins.__import__(name, globals, locals, fromlist, level)
    return dict(vars(builtins), __import__=fake_import)


# ── подставной меш: квадрат из двух треугольников ────────────────────────

class _Seq:
    """bpy-коллекция: len + foreach_get / foreach_set по плоскому массиву."""

    def __init__(self, n, **arrays):
        self._n = n
        self.arrays = {k: np.asarray(v) for k, v in arrays.items()}
        self.items = []

    def __len__(self):
        return self._n

    def __iter__(self):
        return iter(self.items)

    def foreach_get(self, attr, out):
        out[:] = self.arrays[attr].reshape(-1)

    def foreach_set(self, attr, values):
        self.arrays[attr] = np.array(values, dtype=np.float32).reshape(self._n, -1)


class _Mesh:
    CO = np.float32([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)])
    TRIS = [(0, 1, 2), (0, 2, 3)]

    def __init__(self, rgb=(0.5, 0.5, 0.5), alpha=ALPHA, layer=True,
                 select=(True, True)):
        self.vertices = _Seq(4, co=self.CO)
        vidx = np.int32([v for tri in self.TRIS for v in tri])
        self.loops = _Seq(len(vidx), vertex_index=vidx)
        self.polygons = _Seq(2, loop_total=np.int32([3, 3]),
                             loop_start=np.int32([0, 3]),
                             material_index=np.int32([0, 0]),
                             select=np.bool_(select))
        self.polygons.items = [types.SimpleNamespace(select=s, vertices=list(t))
                               for s, t in zip(select, self.TRIS)]
        self.layers = []
        self.active = None
        if layer:
            col = np.tile(np.float32(tuple(rgb) + (alpha,)), (len(vidx), 1))
            self.active = self._layer("Day", col)
            self.layers.append(self.active)

    def _layer(self, name, col):
        return types.SimpleNamespace(name=name,
                                     data=_Seq(len(col), color=col))

    def colors(self):
        return self.active.data.arrays["color"].reshape(-1, 4)


class _Compat:
    @staticmethod
    def vcol_active(mesh, layer=None):
        if layer is None:
            return mesh.active
        mesh.active = layer
        return layer

    @staticmethod
    def vcol_list(mesh):
        return list(mesh.layers)

    @staticmethod
    def vcol_new(mesh, name):
        layer = mesh._layer(name, np.zeros((len(mesh.loops), 4), np.float32))
        mesh.layers.append(layer)
        return layer


def _obj(mesh):
    return types.SimpleNamespace(type="MESH", mode="OBJECT", data=mesh)


def _prelight():
    ns = {"np": np, "compat": _Compat,
          "bpy": types.SimpleNamespace(ops=None)}
    return _extract(PRELIGHT, {"prelight_foliage",
                               "scatter_color_from_selected"}, ns)


class _KDTree:
    """mathutils.kdtree.KDTree перебором: find → (co, index, dist)."""

    def __init__(self, n):
        self.pts = []

    def insert(self, co, index):
        self.pts.append((np.asarray(co, dtype=np.float64), index))

    def balance(self):
        pass

    def find(self, co):
        co = np.asarray(co, dtype=np.float64)
        best = min(self.pts, key=lambda p: np.linalg.norm(p[0] - co))
        return best[0], best[1], float(np.linalg.norm(best[0] - co))


@pytest.fixture
def mathutils_stub(monkeypatch):
    # scatter_color_from_selected делает `import mathutils` внутри функции.
    stub = types.SimpleNamespace(
        Vector=lambda v: tuple(v),
        kdtree=types.SimpleNamespace(KDTree=_KDTree))
    monkeypatch.setitem(sys.modules, "mathutils", stub)
    return stub


LIN = (0.21, 0.6, 0.05)


def test_foliage_color_keeps_alpha():
    ns = _prelight()
    mesh = _Mesh()
    ok, msg = ns["prelight_foliage"](
        _obj(mesh), mode="COLOR", blend="REPLACE", tint_strength=1.0,
        light_tint=LIN, shadow_tint=LIN)
    assert ok, msg
    c = mesh.colors()
    assert c[:, :3] == pytest.approx(np.tile(LIN, (6, 1)), abs=1e-6)
    assert c[:, 3] == pytest.approx(ALPHA)


@pytest.mark.parametrize("mode", ["SHADE", "BOTH"])
def test_foliage_shade_keeps_alpha(mode):
    ns = _prelight()
    mesh = _Mesh()
    ok, msg = ns["prelight_foliage"](_obj(mesh), mode=mode, blend="MULTIPLY",
                                     tint_strength=0.5, light_tint=LIN,
                                     shadow_tint=LIN)
    assert ok, msg
    assert mesh.colors()[:, 3] == pytest.approx(ALPHA)


def test_foliage_new_layer_starts_opaque_white():
    # Слоя нет → создаётся (нулевой буфер): стартует белым и непрозрачным.
    ns = _prelight()
    mesh = _Mesh(layer=False)
    ok, msg = ns["prelight_foliage"](
        _obj(mesh), mode="COLOR", blend="REPLACE", tint_strength=1.0,
        light_tint=LIN, shadow_tint=LIN)
    assert ok, msg
    c = mesh.colors()
    assert c[:, :3] == pytest.approx(np.tile(LIN, (6, 1)), abs=1e-6)
    assert c[:, 3] == pytest.approx(1.0)


def test_scatter_full_strength_keeps_alpha(mathutils_stub):
    ns = _prelight()
    mesh = _Mesh()
    ok, msg = ns["scatter_color_from_selected"](
        _obj(mesh), LIN + (1.0,), strength=1.0, distance=1.0)
    assert ok, msg
    c = mesh.colors()
    assert c[:, :3] == pytest.approx(np.tile(LIN, (6, 1)), abs=1e-6)
    assert c[:, 3] == pytest.approx(ALPHA)


def test_scatter_blends_rgb_only(mathutils_stub):
    # Выделен один треугольник (вершины 0, 1, 2), радиус ~0: вершина 3 не
    # задета; сила 0.5 — половина пути к цели. Альфа везде прежняя.
    ns = _prelight()
    mesh = _Mesh(rgb=(0.5, 0.5, 0.5), select=(True, False))
    ok, msg = ns["scatter_color_from_selected"](
        _obj(mesh), (1.0, 0.0, 0.0), strength=0.5, distance=0.0)
    assert ok, msg
    c = mesh.colors()
    vidx = mesh.loops.arrays["vertex_index"]
    for li, v in enumerate(vidx):
        want = (0.75, 0.25, 0.25) if v != 3 else (0.5, 0.5, 0.5)
        assert c[li, :3] == pytest.approx(want, abs=1e-6)
    assert c[:, 3] == pytest.approx(ALPHA)


# ── ops/light_ops.py: палитра / кисть → линейный ───────────────────────────

def test_srgb3_to_linear():
    f = _extract(LIGHT_OPS, {"_srgb3_to_linear"},
                 {"__builtins__": _builtins()})["_srgb3_to_linear"]
    got = f((0.5, 0.5, 0.5))
    assert got == pytest.approx((0.21404,) * 3, abs=1e-5)
    assert len(f((0.2, 0.4, 0.6, 1.0))) == 3            # альфа отбрасывается
    assert f((0.0, 1.0, 0.04)) == pytest.approx((0.0, 1.0, 0.04 / 12.92))


@pytest.mark.parametrize("v", [0.2, 0.5, 0.55, 0.8])
def test_swatch_equals_game_byte(v):
    # Слой BYTE_COLOR хранит sRGB-байт от линейного .color: переведённый
    # свотч даёт ровно байт свотча (без перевода 0.5 → 188).
    lin = timecyc.srgb_to_linear(v)
    assert round(timecyc.linear_to_srgb(lin) * 255) == round(v * 255)
    assert round(timecyc.linear_to_srgb(v) * 255) != round(v * 255)


class _Props(dict):
    """bl_rna.properties: .get(name) → свойство с .subtype."""


def _brush(color, subtype):
    props = _Props()
    if subtype is not None:
        props["color"] = types.SimpleNamespace(subtype=subtype)
    return types.SimpleNamespace(color=color,
                                 bl_rna=types.SimpleNamespace(properties=props))


def _scatter_op(brush, palette=(0.5, 0.5, 0.5)):
    calls = []

    def fake_scatter(obj, color, strength=1.0, distance=1.0):
        calls.append(color)
        return True, "ok"

    ns = {
        "__builtins__": _builtins(),
        "bpy": types.SimpleNamespace(types=types.SimpleNamespace(Operator=object)),
        "T": lambda s: s,
        "_pub": lambda op, kind, msg: None,
        "scatter_color_from_selected": fake_scatter,
    }
    _extract(LIGHT_OPS, {"_srgb3_to_linear", "GTATOOLS_OT_scatter_color"}, ns)
    st = types.SimpleNamespace(gtatools_scatter_color_color=palette,
                               gtatools_scatter_color_strength=1.0,
                               gtatools_scatter_color_distance=0.5)
    vp = types.SimpleNamespace(brush=brush)
    ctx = types.SimpleNamespace(
        active_object=types.SimpleNamespace(type="MESH"),
        scene=types.SimpleNamespace(inu_settings=st),
        tool_settings=types.SimpleNamespace(vertex_paint=vp))
    assert ns["GTATOOLS_OT_scatter_color"]().execute(ctx) == {"FINISHED"}
    return calls[0]


L05 = timecyc.srgb_to_linear(0.5)


@pytest.mark.parametrize("brush, want", [
    (None, (L05, L05, L05)),                                     # палитра
    (_brush((0.5, 0.5, 0.5), "COLOR_GAMMA"), (L05, L05, L05)),    # кисть sRGB
    (_brush((0.25, 0.5, 1.0), "COLOR"), (0.25, 0.5, 1.0)),        # уже линейная
    (_brush((0.25, 0.5, 1.0), None), (0.25, 0.5, 1.0)),           # нет в RNA
])
def test_scatter_operator_color_space(brush, want):
    color = _scatter_op(brush)
    assert color[:3] == pytest.approx(want, abs=1e-6)


def test_foliage_operator_passes_linear_tints():
    got = {}

    def fake_foliage(obj, **kw):
        got.update(kw)
        return True, "ok"

    class _St:
        gtatools_foliage_color_material_name = ""
        gtatools_foliage_material_name = ""
        gtatools_foliage_light_tint = (0.55, 0.8, 0.3)
        gtatools_foliage_shadow_tint = (0.2, 0.35, 0.12)
        gtatools_foliage_metric = "SPHERE"
        gtatools_foliage_blend = "MULTIPLY"

        def __getattr__(self, name):              # прочие ползунки
            return 0.0

    ns = {
        "__builtins__": _builtins(),
        "bpy": types.SimpleNamespace(
            types=types.SimpleNamespace(Operator=object),
            props=types.SimpleNamespace(EnumProperty=lambda **kw: None)),
        "_pub": lambda op, kind, msg: None,
        "_force_object_mode": lambda ctx: (None, None),
        "_foliage_snapshot": lambda obj: True,
        "prelight_foliage": fake_foliage,
    }
    _extract(LIGHT_OPS, {"_srgb3_to_linear", "GTATOOLS_OT_prelight_foliage"}, ns)
    op = ns["GTATOOLS_OT_prelight_foliage"]()
    op.mode = "COLOR"
    ctx = types.SimpleNamespace(
        scene=types.SimpleNamespace(inu_settings=_St()),
        active_object=types.SimpleNamespace(type="MESH", material_slots=[]),
        screen=types.SimpleNamespace(areas=[]))
    assert op.execute(ctx) == {"FINISHED"}
    lin = timecyc.srgb_to_linear
    assert got["light_tint"] == pytest.approx(tuple(lin(v) for v in (0.55, 0.8, 0.3)))
    assert got["shadow_tint"] == pytest.approx(tuple(lin(v) for v in (0.2, 0.35, 0.12)))
