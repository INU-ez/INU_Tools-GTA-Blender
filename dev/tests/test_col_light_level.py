# PreLight COL (LIGHT-15 / BUG-18 в BLENDER_VS_MAX.md): «Порог» учитывался
# только в превью — Bake COL Light писал Day/Night Min там, где превью
# показывало 0 (при ползунке по умолчанию t = 0.01). Теперь превью и
# запекание считают уровень ОДНОЙ функцией _col_level (как col_levels в Max).
# Попутно: превью брало яркость по индексу угла и падало (IndexError в
# draw-хендлере) на слое с доменом POINT — теперь через общий _poly_avg.
#
# tools/col_light.py импортирует bpy/gpu/blf на уровне модуля, поэтому
# функции и оператор вынимаются через AST (как test_material_color_export.py).

import ast
import io
import itertools
import json
import os
import types

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "INU_tools", "tools", "col_light.py")
LOCALES = [os.path.join(ROOT, "INU_tools", "locale", n)
           for n in ("eng.py", "spa.py")]
SETTINGS = os.path.join(ROOT, "INU_tools", "scene_settings.py")
TIP = "Порог яркости (учитывается и при запекании — результат совпадает с превью)"


def _tree(path):
    return ast.parse(io.open(path, encoding="utf-8").read())


def _load(wanted, ns=None):
    ns = {} if ns is None else ns
    keep = []
    for node in _tree(MODULE).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name in wanted:
                keep.append(node)
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id in wanted
                   for t in node.targets):
                keep.append(node)
    found = {getattr(n, "name", None) or n.targets[0].id for n in keep}
    assert found == set(wanted), sorted(set(wanted) - found)
    exec(compile(ast.Module(body=keep, type_ignores=[]), MODULE, "exec"), ns)
    return ns


NS = _load({"_col_gamma", "_col_threshold", "_col_level", "_poly_avg"})
col_gamma = NS["_col_gamma"]
col_threshold = NS["_col_threshold"]
col_level = NS["_col_level"]
poly_avg = NS["_poly_avg"]


# ── формула ────────────────────────────────────────────────────────────

def test_threshold_slider():
    assert col_threshold(0) == pytest.approx(0.01)
    assert col_threshold(50) == pytest.approx(0.005)
    assert col_threshold(99) == pytest.approx(0.0001)
    assert col_threshold(100) == 0.0


def test_gamma_from_edge():
    assert col_gamma(0.0) == 1.0
    assert col_gamma(0.25) == pytest.approx(0.5)
    assert col_gamma(-0.5) == pytest.approx(3.0)


@pytest.mark.parametrize("avg, vmin, vmax, gamma, contrast, thr, want", [
    (0.005, 10, 15, 1.0, 0.0, 0.01, 0),    # ниже порога → 0, не Day Min
    (0.5, 10, 15, 1.0, 0.0, 0.01, 12),     # (0.5−t)/(1−t) = 0.4949 → 12.47
    (0.005, 10, 15, 1.0, 0.0, 0.0, 10),    # без порога — как старое запекание
    (0.0, 10, 15, 1.0, 0.0, 0.0, 10),
    (1.0, 10, 15, 1.0, 0.0, 0.01, 15),
    (0.36, 0, 15, 0.5, 0.0, 0.0, 9),       # край +0.25: √0.36 = 0.6 → 9
    (0.5, 0, 15, 3.0, 0.0, 0.0, 2),        # край −0.5: 0.5³ = 0.125 → 1.875
    (0.25, 10, 15, 1.0, 0.3, 0.0, 10),     # k=4: 0.5·0.5⁴ = 0.03125
    (0.75, 10, 15, 1.0, 0.3, 0.0, 15),     # 1 − 0.03125 = 0.96875 → 14.84
    (0.25, 10, 15, 1.0, 0.3, 0.01, 10),    # 0.03125 > t: (0.03125−t)/(1−t)
    (0.1, 10, 15, 1.0, 0.3, 0.01, 0),      # контраст опустил под порог: 0.0008
    (2.0, 0, 5, 1.0, 0.0, 0.01, 5),        # яркость > 1 обрезается
    (-1.0, 3, 5, 1.0, 0.0, 0.0, 3),
])
def test_col_level_values(avg, vmin, vmax, gamma, contrast, thr, want):
    assert col_level(avg, vmin, vmax, gamma, contrast, thr) == want


# Копии прежних формул (до правки) — для сверки на сетке входов.

def _old_preview(avg, val_min, val_max, gamma, contrast, threshold):
    avg = min(1.0, max(0.0, avg))
    if avg > 0.0:
        avg = avg ** gamma
    if contrast > 0.0:
        k = 1.0 + contrast * 10.0
        if avg < 0.5:
            avg = 0.5 * (2.0 * avg) ** k
        else:
            avg = 1.0 - 0.5 * (2.0 * (1.0 - avg)) ** k
    if threshold > 0.0 and avg < threshold:
        return 0
    if threshold > 0.0 and threshold < 1.0:
        avg = (avg - threshold) / (1.0 - threshold)
    value = val_min + avg * (val_max - val_min)
    return min(15, max(0, round(value)))


def _old_bake(avg, light_min, light_max, gamma=1.0, contrast=0.0):
    avg = min(1.0, max(0.0, avg))
    if avg > 0.0 and gamma != 1.0:
        avg = avg ** gamma
    if contrast > 0.0:
        k = 1.0 + contrast * 10.0
        if avg < 0.5:
            avg = 0.5 * (2.0 * avg) ** k
        else:
            avg = 1.0 - 0.5 * (2.0 * (1.0 - avg)) ** k
    value = light_min + avg * (light_max - light_min)
    return min(15, max(0, round(value)))


_AVGS = [i / 400.0 for i in range(401)] + [0.0005, 0.005, 0.0099, 0.0101]
_RANGES = [(10, 15), (0, 5), (0, 15), (15, 0), (7, 7)]
_EDGES = [0.0, 0.25, 1.0, -0.5, -1.0]
_CONTRASTS = [0.0, 0.3, 1.0]


def test_same_numbers_as_old_preview():
    for slider in (0, 37, 99, 100):
        t = col_threshold(slider)
        for (lo, hi), edge, c in itertools.product(_RANGES, _EDGES, _CONTRASTS):
            g = col_gamma(edge)
            for a in _AVGS:
                assert col_level(a, lo, hi, g, c, t) == _old_preview(a, lo, hi, g, c, t)


def test_same_numbers_as_old_bake_without_threshold():
    for (lo, hi), edge, c in itertools.product(_RANGES, _EDGES, _CONTRASTS):
        g = col_gamma(edge)
        for a in _AVGS:
            assert col_level(a, lo, hi, g, c, 0.0) == _old_bake(a, lo, hi, g, c)
            assert col_level(a, lo, hi, g, c, col_threshold(100)) == _old_bake(a, lo, hi, g, c)


# ── подставной куб: 8 вершин, 6 квадов, 24 угла ──────────────────────────

class _V:
    """mathutils.Vector: +, * число, .x/.y/.z."""

    def __init__(self, a):
        self.a = np.asarray(a, dtype=np.float64)

    def __add__(self, o):
        return _V(self.a + o.a)

    def __mul__(self, k):
        return _V(self.a * k)

    x = property(lambda s: float(s.a[0]))
    y = property(lambda s: float(s.a[1]))
    z = property(lambda s: float(s.a[2]))


class _M:
    """matrix_world: M @ Vector."""

    def __init__(self, m=None):
        self.m = np.eye(4) if m is None else np.asarray(m, dtype=np.float64)

    def __matmul__(self, v):
        return _V(self.m[:3, :3] @ v.a + self.m[:3, 3])

    def __getitem__(self, i):
        return self.m[i]


_CUBE_CO = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
_CUBE_FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
               (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


class _Layer:
    def __init__(self, name, domain, values):
        self.name = name
        self.domain = domain
        self.data = [types.SimpleNamespace(color=(v, v * 0.5, 0.0, 1.0))
                     for v in values]


class _Cube:
    def __init__(self, layers, mat_index=0):
        self.vertices = [types.SimpleNamespace(co=_V(c)) for c in _CUBE_CO]
        self.loops = []
        self.polygons = []
        for fi, vs in enumerate(_CUBE_FACES):
            start = len(self.loops)
            for v in vs:
                self.loops.append(types.SimpleNamespace(vertex_index=v))
            co = np.mean([_CUBE_CO[v] for v in vs], axis=0)
            self.polygons.append(types.SimpleNamespace(
                index=fi, vertices=list(vs),
                loop_indices=range(start, start + len(vs)),
                center=_V(co), normal=_V(co), material_index=mat_index))
        self.layers = list(layers)
        self.active = self.layers[0] if self.layers else None
        self.materials = []


class _Compat:
    @staticmethod
    def vcol_list(mesh):
        return list(mesh.layers)

    @staticmethod
    def vcol_active(mesh):
        return mesh.active

    @staticmethod
    def vcol_get(mesh, name):
        return next((l for l in mesh.layers if l.name == name), None)

    @staticmethod
    def vcol_domain(layer):
        return layer.domain


def _point_values():
    return [0.1 * (i + 1) for i in range(8)]          # по вершинам


def _corner_values(mesh):
    return [0.02 * (i + 1) for i in range(len(mesh.loops))]


def test_poly_avg_point_domain_uses_vertex_index():
    mesh = _Cube([])
    vals = _point_values()
    got = poly_avg(mesh, vals, "POINT")                # 8 значений, 24 угла
    for fi, vs in enumerate(_CUBE_FACES):
        assert got[fi] == pytest.approx(np.mean([vals[v] for v in vs]))


def test_poly_avg_corner_domain_uses_loop_index():
    mesh = _Cube([])
    vals = _corner_values(mesh)
    got = poly_avg(mesh, vals, "CORNER")
    for poly in mesh.polygons:
        assert got[poly.index] == pytest.approx(
            np.mean([vals[i] for i in poly.loop_indices]))
    with pytest.raises(IndexError):                     # то, на чём падало превью
        poly_avg(mesh, _point_values(), "CORNER")


# ── превью и запекание на одном меше ─────────────────────────────────────

def _settings(slider, edge=0.0, contrast=0.0):
    return types.SimpleNamespace(
        gtatools_col_day_min=10, gtatools_col_day_max=15,
        gtatools_col_night_min=0, gtatools_col_night_max=5,
        gtatools_col_light_edge=edge, gtatools_col_light_contrast=contrast,
        gtatools_col_light_threshold=slider)


class _Mat:
    def __init__(self, name):
        self.name = name
        self.inu = types.SimpleNamespace(
            col_mat_index=0, col_flags=0, col_brightness=0,
            col_day_light=-1, col_night_light=-1)

    def copy(self):
        m = _Mat(self.name + ".copy")
        m.inu = types.SimpleNamespace(**vars(self.inu))
        return m


class _Obj:
    type = "MESH"
    name = "col_obj"

    def __init__(self, mesh):
        self.data = mesh
        self.matrix_world = _M()
        self.props = {}
        mesh.materials.append(_Mat("floor"))

    @property
    def material_slots(self):
        return [types.SimpleNamespace(material=m) for m in self.data.materials]

    def get(self, key, default=None):
        return self.props.get(key, default)

    def __setitem__(self, key, value):
        self.props[key] = value


def _ctx(obj, settings):
    return types.SimpleNamespace(active_object=obj,
                                 scene=types.SimpleNamespace(inu_settings=settings))


def _preview(obj, settings):
    ns = _load({"_col_light_preview_cache", "_col_gamma", "_col_threshold",
                "_col_level", "_poly_avg", "_col_light_get_preview_data"},
               {"compat": _Compat})
    faces = ns["_col_light_get_preview_data"](_ctx(obj, settings))
    return [f[0] for f in faces]


def _bake(obj, settings):
    bpy = types.SimpleNamespace(types=types.SimpleNamespace(Operator=object))
    ns = _load({"_col_gamma", "_col_threshold", "_col_level", "_poly_avg",
                "GTATOOLS_OT_bake_col_light"},
               {"compat": _Compat, "bpy": bpy})
    op = ns["GTATOOLS_OT_bake_col_light"]()
    op.report = lambda kind, msg: None
    assert op.execute(_ctx(obj, settings)) == {"FINISHED"}
    mats = obj.data.materials
    return [(mats[p.material_index].inu.col_day_light,
             mats[p.material_index].inu.col_night_light)
            for p in obj.data.polygons]


def test_preview_point_domain_no_index_error():
    mesh = _Cube([_Layer("Day", "POINT", _point_values())])
    vals = _preview(_Obj(mesh), _settings(100))
    want = [col_level(np.mean([_point_values()[v] for v in vs]), 10, 15)
            for vs in _CUBE_FACES]
    assert vals == want


def test_bake_uses_threshold_near_black():
    # Почти чёрная модель: превью при ползунке 0 показывает 0 — запекание
    # раньше писало Day Min 10.
    dark = [0.005] * 24
    mesh = _Cube([_Layer("Day", "CORNER", dark), _Layer("Night", "CORNER", dark)])
    obj = _Obj(mesh)
    assert _preview(obj, _settings(0)) == [0] * 6
    assert _bake(obj, _settings(0)) == [(0, 0)] * 6
    mesh = _Cube([_Layer("Day", "CORNER", dark), _Layer("Night", "CORNER", dark)])
    assert _bake(_Obj(mesh), _settings(100)) == [(10, 0)] * 6   # без порога


@pytest.mark.parametrize("slider, edge, contrast", [
    (0, 0.0, 0.0), (0, 0.25, 0.3), (50, -0.5, 0.0), (100, 0.0, 1.0)])
@pytest.mark.parametrize("domain", ["CORNER", "POINT"])
def test_bake_matches_preview(slider, edge, contrast, domain):
    # Грани разной яркости (от почти чёрной до белой) → разные уровни,
    # запекание делит материал; уровень каждой грани = цифра превью.
    if domain == "POINT":
        day = [0.0, 0.004, 0.02, 0.3, 0.45, 0.7, 0.9, 1.0]
    else:
        day = [0.0] * 4 + [0.008] * 4 + [0.05] * 4 + [0.3] * 4 + [0.6] * 4 + [1.0] * 4
    s = _settings(slider, edge, contrast)
    mesh = _Cube([_Layer("Day", domain, day), _Layer("Night", domain, day)])
    obj = _Obj(mesh)
    shown = _preview(obj, s)
    baked = _bake(obj, s)
    assert [d for d, _n in baked] == shown
    assert len(set(shown)) > 1
    # Ночь — тот же расчёт в своём диапазоне 0..5 (превью активного «Night»).
    shown_night = _preview(_Obj(_Cube([_Layer("Night", domain, day)])), s)
    assert [n for _d, n in baked] == shown_night
    assert json.loads(obj.props["gtatools_col_light_mats"])     # копии созданы


# ── подсказка ползунка ─────────────────────────────────────────────────────

def _lang(path):
    for node in _tree(path).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "LANG" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("no LANG in " + path)


def test_threshold_tooltip_translated():
    assert 'description=T("%s")' % TIP in io.open(SETTINGS, encoding="utf-8").read()
    for path in LOCALES:
        assert _lang(path).get(TIP), path
