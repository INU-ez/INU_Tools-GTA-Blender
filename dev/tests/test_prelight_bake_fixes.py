# Prelight Bake — три правки (LIGHT-1..3 / BUG-16 в BLENDER_VS_MAX.md):
#  * позиция лампы — мировая (matrix_world), а не .location: у лампы с
#    родителем / constraint / delta свет шёл из неверной точки, хотя
#    направление уже бралось из matrix_world; превью-лампы 2DFX (дети 2DFX
#    Empty с .location = 0) не запекаются — как в Max, где 2DFX хелперы;
#  * быстрое «Запечь поверх» не прибавляет Ambient второй раз — он уже в
#    прилайте-основе (каждое нажатие поднимало всю модель на Ambient);
#  * все тумблеры Point/Sun/Spot/Area выкл. = ламп нет + сообщение (пустой
#    набор читался как «все типы»); запекание одного HDRI при этом работает.
#
# tools/prelight.py и ops/light_ops.py импортируют bpy на уровне модуля,
# поэтому функции и операторы вынимаются через AST (как в
# test_material_color_export.py) и гоняются на подставных объектах.

import ast
import builtins
import io
import math
import os
import types

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRELIGHT = os.path.join(ROOT, "INU_tools", "tools", "prelight.py")
LIGHT_OPS = os.path.join(ROOT, "INU_tools", "ops", "light_ops.py")
LOCALES = [os.path.join(ROOT, "INU_tools", "locale", n)
           for n in ("eng.py", "spa.py")]

FULL = "GTATOOLS_OT_bake_vertex_colors"
FAST = "GTATOOLS_OT_bake_vertex_colors_simple"
MSG_TYPES_OFF = ("Все типы ламп выключены (Point / Sun / Spot / Area) — "
                 "запекать нечего")
MSG_NO_LIGHTS = "Нечего запекать: в сцене нет видимых ламп"


def _tree(path):
    return ast.parse(io.open(path, encoding="utf-8").read())


def _extract(path, wanted, ns):
    keep = []
    for node in _tree(path).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name in wanted:
                keep.append(node)
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id in wanted
                   for t in node.targets):
                keep.append(node)
    found = {getattr(n, "name", None) or n.targets[0].id for n in keep}
    assert found == set(wanted), sorted(set(wanted) - found)
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), ns)
    return ns


# ── tools/prelight.py на подставных mesh / лампах ──────────────────────

class _Mat:
    """Как mathutils.Matrix: строки, translation, to_3x3 / inverted /
    transposed, M @ v."""

    def __init__(self, m):
        self.m = np.asarray(m, dtype=np.float64)

    @classmethod
    def at(cls, x, y, z):
        m = np.eye(4)
        m[:3, 3] = (x, y, z)
        return cls(m)

    @property
    def translation(self):
        return tuple(self.m[:3, 3])

    def to_3x3(self):
        return _Mat(self.m[:3, :3])

    def inverted(self):
        return _Mat(np.linalg.inv(self.m))

    def transposed(self):
        return _Mat(self.m.T)

    def __matmul__(self, other):
        return self.m @ np.asarray(other, dtype=np.float64)

    def __array__(self, dtype=None, copy=None):
        return self.m if dtype is None else self.m.astype(dtype)


class _Seq:
    """bpy-коллекция: len + foreach_get / foreach_set по плоскому массиву."""

    def __init__(self, n, **arrays):
        self._n = n
        self.arrays = {k: np.asarray(v) for k, v in arrays.items()}

    def __len__(self):
        return self._n

    def foreach_get(self, attr, out):
        out[:] = self.arrays[attr].reshape(-1)

    def foreach_set(self, attr, values):
        self.arrays[attr] = np.array(values, dtype=np.float32).reshape(self._n, -1)


class _Quad:
    """Квадрат 2×2 в плоскости z=0, нормаль +Z, один канал «Day»."""

    CO = np.float32([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)])

    def __init__(self):
        self.vertices = _Seq(4, co=self.CO, normal=np.tile(np.float32((0, 0, 1)), (4, 1)))
        self.loops = _Seq(4, vertex_index=np.int32([0, 1, 2, 3]))
        day = types.SimpleNamespace(name="Day", data=_Seq(4, color=np.zeros((4, 4), np.float32)))
        self.colors = [day]
        self.active_color = day

    def calc_normals_split(self):
        pass

    def rgb(self):
        return self.active_color.data.arrays["color"][:, :3]


class _Compat:
    @staticmethod
    def vcol_active(mesh, layer=None):
        if layer is None:
            return mesh.active_color
        mesh.active_color = layer
        return layer

    @staticmethod
    def vcol_list(mesh):
        return list(mesh.colors)


def _lamp(kind, *, local, world, props=None, parent=None, inu_type="OBJ",
          energy=1.0):
    """Лампа с родителем: .location локальная, matrix_world — мировая.
    SPOT без поворота светит вдоль -Z (вниз). props — ID-свойства (obj.get)."""
    data = types.SimpleNamespace(type=kind, color=(1.0, 1.0, 1.0), energy=energy,
                                 spot_size=math.radians(90.0), spot_blend=0.15)
    return types.SimpleNamespace(type="LIGHT", data=data, location=local,
                                 matrix_world=_Mat.at(*world),
                                 hide_render=False, visible_get=lambda: True,
                                 get=dict(props or {}).get, parent=parent,
                                 inu=types.SimpleNamespace(type=inu_type))


def _prelight(lamps=(), env=None):
    rays = []

    def ray_cast(depsgraph, origin, direction, distance=0.0):
        rays.append(np.asarray(direction, dtype=np.float64))
        return (False, None, None, None, None, None)

    bpy = types.SimpleNamespace(
        data=types.SimpleNamespace(objects=list(lamps)),
        context=types.SimpleNamespace(
            scene=types.SimpleNamespace(ray_cast=ray_cast),
            evaluated_depsgraph_get=lambda: object()))
    ns = {
        "np": np, "bpy": bpy, "compat": _Compat,
        "Vector": lambda v: np.array(v, dtype=np.float64),
        "_eval_loop_normals": lambda obj: (
            np.tile(np.float32((0, 0, 1)), (len(obj.data.loops), 1)), True),
        "_world_env_sample": lambda no: (
            None if env is None else np.tile(np.float32(env), (no.shape[0], 1))),
    }
    _extract(PRELIGHT, {"_BAKE_LIGHT_TYPES", "_light_world_pos",
                        "_is_2dfx_preview_lamp",
                        "_allowed_light_types", "_spot_cone_factor",
                        "bake_vertex_colors_from_lights",
                        "bake_vertex_colors_simple"}, ns)
    ns["rays"] = rays
    return ns


def _quad_obj():
    return types.SimpleNamespace(type="MESH", data=_Quad(),
                                 matrix_world=_Mat(np.eye(4)))


def _point_expected(lamp_pos, full):
    """Lambert + затухание из prelight.py для лампы в lamp_pos над квадратом
    (энергия 1, белый цвет)."""
    ld = np.float32(lamp_pos) - _Quad.CO
    dist = np.linalg.norm(ld, axis=1)
    ndl = ld[:, 2] / dist
    if full:
        return ndl / (1.0 + dist * 0.01 + dist * dist * 0.0001)
    return ndl / (1.0 + dist * dist * 0.0001)


def test_light_world_pos_reads_matrix_world():
    ns = _prelight()
    lamp = _lamp("POINT", local=(0.0, 0.0, 0.0), world=(10.0, 0.0, 5.0))
    pos = ns["_light_world_pos"](lamp)
    assert pos.dtype == np.float32
    assert pos.tolist() == [10.0, 0.0, 5.0]


def test_allowed_light_types():
    f = _prelight()["_allowed_light_types"]
    assert f(None) == {"POINT", "SUN", "SPOT", "AREA"}
    assert f(set()) == set()           # все тумблеры выкл. — не «все типы»
    assert f({"SUN"}) == {"SUN"}
    assert f(("POINT", "AREA")) == {"POINT", "AREA"}


@pytest.mark.parametrize("kind", ["POINT", "SPOT", "AREA"])
def test_fast_bake_lights_from_world_position(kind):
    # Родитель на (0,0,10), своя .location = 0: по .location лампа лежала бы
    # в плоскости квадрата (n·L = 0, у SPOT ещё и вне конуса) → чёрный.
    lamp = _lamp(kind, local=(0.0, 0.0, 0.0), world=(0.0, 0.0, 10.0))
    ns = _prelight([lamp])
    obj = _quad_obj()
    ok, msg = ns["bake_vertex_colors_simple"](
        obj, ambient=0.0, intensity_mult=1.0, gamma=1.0, use_shadows=False)
    assert ok, msg
    want = _point_expected((0.0, 0.0, 10.0), full=False)
    for ch in range(3):
        assert obj.data.rgb()[:, ch] == pytest.approx(want, rel=1e-5)


def test_full_bake_shadow_rays_aim_at_world_position():
    lamp = _lamp("POINT", local=(0.0, 0.0, 0.0), world=(0.0, 0.0, 10.0))
    ns = _prelight([lamp])
    obj = _quad_obj()
    ok, msg = ns["bake_vertex_colors_from_lights"](obj, use_shadows=True)
    assert ok, msg
    assert len(ns["rays"]) == 4
    for d in ns["rays"]:                # от вершины вверх, к лампе
        assert d[2] > 0.99
    want = _point_expected((0.0, 0.0, 10.0), full=True)
    assert obj.data.rgb()[:, 0] == pytest.approx(want, rel=1e-5)


def test_all_types_off_means_no_lamps():
    lamp = _lamp("POINT", local=(0.0, 0.0, 10.0), world=(0.0, 0.0, 10.0))
    ns = _prelight([lamp])
    for fn in ("bake_vertex_colors_simple", "bake_vertex_colors_from_lights"):
        obj = _quad_obj()
        ok, msg = ns[fn](obj, allowed_types=set(), use_hdri=False)
        assert not ok
        assert _ops()[0]["_bake_fail_text"](msg) == MSG_NO_LIGHTS
        assert not obj.data.rgb().any()          # канал не тронут


def test_empty_mesh_reason_reaches_operator_text():
    lamp = _lamp("POINT", local=(0.0, 0.0, 10.0), world=(0.0, 0.0, 10.0))
    ns = _prelight([lamp])
    empty = types.SimpleNamespace(
        type="MESH", data=types.SimpleNamespace(vertices=[], loops=[]),
        matrix_world=_Mat(np.eye(4)))
    for fn in ("bake_vertex_colors_simple", "bake_vertex_colors_from_lights"):
        ok, msg = ns[fn](empty)
        assert not ok
        assert _ops()[0]["_bake_fail_text"](msg) == "У меша нет граней"


def test_hdri_only_bake_ignores_lamps():
    lamp = _lamp("POINT", local=(0.0, 0.0, 10.0), world=(0.0, 0.0, 10.0))
    ns = _prelight([lamp], env=(0.2, 0.2, 0.2))
    obj = _quad_obj()
    ok, msg = ns["bake_vertex_colors_simple"](
        obj, ambient=0.0, intensity_mult=1.0, gamma=1.0, use_shadows=False,
        allowed_types=set(), use_hdri=True)
    assert ok, msg
    assert obj.data.rgb() == pytest.approx(np.full((4, 3), 0.2), rel=1e-5)


_FX_EMPTY = types.SimpleNamespace(inu=types.SimpleNamespace(type="2DFX"))


def _fx_preview_lamp(world, legacy=False):
    """Превью-лампа 2DFX, как её строит fx_preview.create_light_preview:
    POINT-ребёнок 2DFX Empty, .location = 0, energy = shadow_size*5,
    inu.type NON (+ маркер inu_2dfx_preview, у легаси-ригов его нет)."""
    return _lamp("POINT", local=(0.0, 0.0, 0.0), world=world,
                 props=None if legacy else {"inu_2dfx_preview": 1},
                 parent=_FX_EMPTY, inu_type="NON", energy=40.0)


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("fn", ["bake_vertex_colors_simple",
                                "bake_vertex_colors_from_lights"])
def test_2dfx_preview_lamp_not_baked(fn, legacy):
    # Модель на карте, превью-лампа фонаря в 3 м над ней: из мировой позиции
    # она выжгла бы прилайт в белое. Печётся только настоящая лампа.
    user = _lamp("POINT", local=(0.0, 0.0, 10.0), world=(0.0, 0.0, 10.0))
    fx = _fx_preview_lamp((0.0, 0.0, 3.0), legacy=legacy)
    ns = _prelight([fx, user])
    obj = _quad_obj()
    kw = {"use_shadows": False}
    if fn == "bake_vertex_colors_simple":
        kw.update(ambient=0.0, intensity_mult=1.0, gamma=1.0)
    ok, msg = ns[fn](obj, **kw)
    assert ok, msg
    want = _point_expected((0.0, 0.0, 10.0), full=fn != "bake_vertex_colors_simple")
    assert obj.data.rgb()[:, 0] == pytest.approx(want, rel=1e-5)


def test_only_2dfx_preview_lamps_means_no_lights():
    ns = _prelight([_fx_preview_lamp((0.0, 0.0, 3.0))])
    ok, msg = ns["bake_vertex_colors_simple"](_quad_obj(), ambient=0.1)
    assert not ok
    assert _ops()[0]["_bake_fail_text"](msg) == MSG_NO_LIGHTS


def test_user_lamp_under_2dfx_empty_is_baked():
    # Своя лампа, привязанная к 2DFX Empty (inu.type OBJ, без маркера), —
    # обычная лампа запекания, не превью.
    ns = _prelight()
    lamp = _lamp("POINT", local=(0.0, 0.0, 0.0), world=(0.0, 0.0, 3.0),
                 parent=_FX_EMPTY)
    assert not ns["_is_2dfx_preview_lamp"](lamp)
    assert ns["_is_2dfx_preview_lamp"](_fx_preview_lamp((0.0, 0.0, 3.0)))
    assert ns["_is_2dfx_preview_lamp"](_fx_preview_lamp((0.0, 0.0, 3.0), legacy=True))
    assert not ns["_is_2dfx_preview_lamp"](
        _lamp("POINT", local=(0.0, 0.0, 3.0), world=(0.0, 0.0, 3.0), inu_type="NON"))
    # «Don't export»-лампа под обычным объектом — тоже запекается.
    mesh_parent = types.SimpleNamespace(inu=types.SimpleNamespace(type="OBJ"))
    assert not ns["_is_2dfx_preview_lamp"](
        _lamp("POINT", local=(0.0, 0.0, 3.0), world=(0.0, 0.0, 3.0),
              parent=mesh_parent, inu_type="NON"))
    # Маркер решает сам по себе (rename-safe, как в fx_preview._is_preview_child).
    assert ns["_is_2dfx_preview_lamp"](
        _lamp("POINT", local=(0.0, 0.0, 3.0), world=(0.0, 0.0, 3.0),
              props={"inu_2dfx_preview": 1}))


def test_prelight_never_reads_lamp_location():
    """Позиция лампы только через _light_world_pos (matrix_world)."""
    reads = [n.lineno for n in ast.walk(_tree(PRELIGHT))
             if isinstance(n, ast.Attribute) and n.attr == "location"
             and isinstance(n.value, ast.Name) and n.value.id == "light_obj"
             and isinstance(n.ctx, ast.Load)]
    assert reads == []


# ── ops/light_ops.py: операторы «Запечь» / «Запечь поверх» ─────────────

class _Obj:
    def __init__(self, active=True):
        self.type = "MESH"
        self.data = types.SimpleNamespace(
            active=types.SimpleNamespace(name="Day") if active else None)
        self.gtatools_v_offset_day = 0.0
        self.gtatools_v_offset_night = 0.0
        self.props = {}

    def __setitem__(self, key, value):
        self.props[key] = value


def _ops(bake_result=(True, "ok")):
    calls = {"bake": [], "force_mode": 0, "add_over": []}

    def fake_bake(obj, *args, **kw):
        calls["bake"].append((args, kw))
        return bake_result

    def force_mode(context):
        calls["force_mode"] += 1
        return None, None

    # execute() делает `from ..tools.prelight import apply_brightness_offset`
    prelight_mod = types.SimpleNamespace(apply_brightness_offset=lambda o, v: None)

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 2 and name == "tools.prelight":
            return prelight_mod
        return builtins.__import__(name, globals, locals, fromlist, level)

    ns = {
        "__builtins__": dict(vars(builtins), __import__=fake_import),
        "bpy": types.SimpleNamespace(types=types.SimpleNamespace(Operator=object)),
        "BoolProperty": lambda **kw: None,
        "T": lambda s: s,
        "_pub": lambda op, kind, msg: op.msgs.append((set(kind), msg)),
        "_force_object_mode": force_mode,
        "_restore_mode": lambda prev_mode, prev_obj: None,
        "_bake_snapshot_active": lambda obj: (
            None if obj.data.active is None else np.zeros(4, np.float32)),
        "_bake_add_over": lambda obj, snap: calls["add_over"].append(obj) or True,
        "compat": types.SimpleNamespace(vcol_active=lambda mesh: mesh.active),
        "bake_vertex_colors_simple": fake_bake,
        "bake_vertex_colors_from_lights": fake_bake,
    }
    _extract(LIGHT_OPS, {"_prelight_allowed_types", "_bake_ambient",
                         "_bake_fail_text", FULL, FAST}, ns)
    return ns, calls


def _ctx(objs, *, point=True, sun=True, spot=True, area=True, hdri=False):
    st = types.SimpleNamespace(
        gtatools_prelight_use_point=point, gtatools_prelight_use_sun=sun,
        gtatools_prelight_use_spot=spot, gtatools_prelight_use_area=area,
        gtatools_prelight_use_hdri=hdri, gtatools_bake_ambient=0.1,
        gtatools_bake_intensity=0.05, gtatools_bake_gamma=0.5)
    return types.SimpleNamespace(selected_objects=objs, active_object=None,
                                 scene=types.SimpleNamespace(inu_settings=st))


def _run(ns, cls_name, ctx, **props):
    op = ns[cls_name]()
    op.msgs = []
    op.over = False
    op.use_shadows = True
    for key, value in props.items():
        setattr(op, key, value)
    return op.execute(ctx), op.msgs


def test_helpers():
    ns, _ = _ops()
    st = types.SimpleNamespace(
        gtatools_prelight_use_point=False, gtatools_prelight_use_sun=False,
        gtatools_prelight_use_spot=False, gtatools_prelight_use_area=False)
    assert ns["_prelight_allowed_types"](st) == set()
    assert ns["_bake_ambient"](0.1, True) == 0.0
    assert ns["_bake_ambient"](0.1, False) == pytest.approx(0.1)


@pytest.mark.parametrize("over, active, ambient", [
    (False, True, 0.1),     # «Запечь» — Ambient с панели
    (True, True, 0.0),      # «Запечь поверх» — Ambient уже в основе
    (True, False, 0.1),     # поверх, но активного канала нет → обычный bake
])
def test_fast_bake_over_skips_ambient(over, active, ambient):
    ns, calls = _ops()
    obj = _Obj(active=active)
    result, _msgs = _run(ns, FAST, _ctx([obj]), over=over)
    assert result == {"FINISHED"}
    assert calls["bake"][0][0][0] == pytest.approx(ambient)
    assert calls["add_over"] == ([obj] if over and active else [])


@pytest.mark.parametrize("cls_name", [FULL, FAST])
def test_all_types_off_cancels_with_message(cls_name):
    ns, calls = _ops()
    ctx = _ctx([_Obj()], point=False, sun=False, spot=False, area=False)
    result, msgs = _run(ns, cls_name, ctx)
    assert result == {"CANCELLED"}
    assert msgs == [({"WARNING"}, MSG_TYPES_OFF)]
    assert calls["bake"] == [] and calls["force_mode"] == 0


@pytest.mark.parametrize("cls_name", [FULL, FAST])
def test_all_types_off_hdri_only_still_bakes(cls_name):
    ns, calls = _ops()
    ctx = _ctx([_Obj()], point=False, sun=False, spot=False, area=False,
               hdri=True)
    result, _msgs = _run(ns, cls_name, ctx)
    assert result == {"FINISHED"}
    kw = calls["bake"][0][1]
    assert kw["allowed_types"] == set() and kw["use_hdri"] is True


@pytest.mark.parametrize("cls_name", [FULL, FAST])
def test_toggles_reach_bake(cls_name):
    ns, calls = _ops()
    _run(ns, cls_name, _ctx([_Obj()], spot=False, area=False))
    kw = calls["bake"][0][1]
    assert kw["allowed_types"] == {"POINT", "SUN"} and kw["use_hdri"] is False


@pytest.mark.parametrize("cls_name", [FULL, FAST])
@pytest.mark.parametrize("reason, text", [
    ("No visible lights in scene!", MSG_NO_LIGHTS),
    ("Mesh has no loops", "У меша нет граней"),
    ("Select a mesh object!", "Нет vertex colors"),
])
def test_failure_reason_reported(cls_name, reason, text):
    ns, _ = _ops(bake_result=(False, reason))
    result, msgs = _run(ns, cls_name, _ctx([_Obj()]))
    assert result == {"CANCELLED"}
    assert msgs == [({"WARNING"}, text)]


# ── locale ─────────────────────────────────────────────────────────────

def _lang(path):
    for node in _tree(path).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "LANG" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("no LANG in " + path)


@pytest.mark.parametrize("path", LOCALES)
def test_messages_translated(path):
    lang = _lang(path)
    for key in (MSG_TYPES_OFF, MSG_NO_LIGHTS, "У меша нет граней",
                "Нет vertex colors"):
        assert lang.get(key), key
