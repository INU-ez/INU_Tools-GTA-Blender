# Prelight Bake с HDRI мира (CHK-B9 / LIGHT-6, LIGHT-7 в BLENDER_VS_MAX.md):
#  * развёртка equirect как у Cycles direction_to_equirectangular
#    (u = 0.5 - az/2π: +X в центре, +Y левее центра) — была зеркальной
#    (+Y → u 0.75), свет от HDRI запекался с другой стороны по оси Y;
#  * поворот мира узлом Mapping перед Environment Texture теперь учитывается
#    (по Z, правила Cycles svm/mapping_util.h: POINT/VECTOR/NORMAL — R·v,
#    TEXTURE — Rᵀ·v).
#
# tools/prelight.py импортирует bpy на уровне модуля, поэтому функции
# вынимаются через AST (как в test_prelight_bake_fixes.py).

import ast
import io
import math
import os
import types

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRELIGHT = os.path.join(ROOT, "INU_tools", "tools", "prelight.py")


def _extract(wanted, ns):
    keep = []
    for node in ast.parse(io.open(PRELIGHT, encoding="utf-8").read()).body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in wanted for t in node.targets):
            keep.append(node)
    found = {getattr(n, "name", None) or n.targets[0].id for n in keep}
    assert found == set(wanted), sorted(set(wanted) - found)
    exec(compile(ast.Module(body=keep, type_ignores=[]), PRELIGHT, "exec"), ns)
    return ns


@pytest.fixture
def pl():
    ns = {"np": np, "bpy": types.SimpleNamespace(context=None),
          "_viewport_hdri_sample": lambda no: None}
    return _extract({"_sample_equirect", "_MAPPING_WARNED",
                     "_env_mapping_z_offset", "_world_env_sample"}, ns)


class _Pixels:
    """image.pixels: foreach_get заполняет (H, W, 4), R = столбец, G = строка
    (строка 0 = низ картинки, как у Blender)."""

    def __init__(self, W, H):
        px = np.zeros((H, W, 4), np.float32)
        px[..., 0] = np.arange(W)[None, :]
        px[..., 1] = np.arange(H)[:, None]
        px[..., 3] = 1.0
        self.px = px

    def foreach_get(self, out):
        out[:] = self.px.reshape(-1)


def _img(W=16, H=8):
    return types.SimpleNamespace(size=(W, H), pixels=_Pixels(W, H))


def _dir(az_deg, z=0.0):
    c = math.sqrt(1.0 - z * z)
    a = math.radians(az_deg)
    return [c * math.cos(a), c * math.sin(a), z]


def _col_row(pl, img, dirs, offset=0.0):
    out = pl["_sample_equirect"](img, np.array(dirs, np.float64), azimuth_offset=offset)
    return [(int(r), int(g)) for r, g, _ in out]


def _rz(theta):
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


# ── развёртка ───────────────────────────────────────────────────────────

def test_equirect_matches_cycles_projection(pl):
    """Центр каждого пикселя: Cycles u = 0.5 - az/2π, v = 0.5 + asin(z)/π
    (camera/projection.h) — должен вернуться тот же пиксель."""
    W, H = 16, 8
    dirs, want = [], []
    for j in range(H):
        z = math.sin(math.pi * ((j + 0.5) / H - 0.5))
        for i in range(W):
            az = math.pi - 2.0 * math.pi * (i + 0.5) / W
            dirs.append(_dir(math.degrees(az), z))
            want.append((i, j))
    assert _col_row(pl, _img(W, H), dirs) == want


def test_plus_y_is_left_of_centre(pl):
    W = 16
    (left, _), (right, _) = _col_row(pl, _img(W), [_dir(80.0), _dir(-80.0)])
    assert left < W // 2 <= right


def test_zenith_top_nadir_bottom(pl):
    H = 8
    (_, top), (_, bottom) = _col_row(pl, _img(16, H), [[0, 0, 1], [0, 0, -1]])
    assert (top, bottom) == (H - 1, 0)


def test_azimuth_offset_rotates_lookup(pl):
    img = _img()
    assert (_col_row(pl, img, [_dir(10.0)], math.radians(70.0))
            == _col_row(pl, img, [_dir(80.0)]))


@pytest.mark.parametrize("theta", [0.3, 1.2, -2.0, 3.0])
def test_offset_equals_rotated_direction(pl, theta):
    rng = np.random.default_rng(7)
    d = rng.normal(size=(2000, 3))
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    img = _img(64, 32)
    a = pl["_sample_equirect"](img, d, azimuth_offset=theta)
    b = pl["_sample_equirect"](img, d @ _rz(theta).T)
    assert np.array_equal(a, b)


# ── узел Mapping мира ───────────────────────────────────────────────────

def _sock(value=None, links=()):
    return types.SimpleNamespace(default_value=value, links=list(links),
                                 is_linked=bool(links))


def _mapping(vt="POINT", rz=0.7, rot=(0.0, 0.0), scale=(1.0, 1.0, 1.0),
             loc=(0.0, 0.0, 0.0), mute=False):
    return types.SimpleNamespace(
        type="MAPPING", name="Mapping", vector_type=vt, mute=mute,
        inputs={"Rotation": _sock((rot[0], rot[1], rz)),
                "Scale": _sock(scale), "Location": _sock(loc)})


def _link(node):
    return types.SimpleNamespace(from_node=node)


def _env(src=None, img=None):
    vec = _sock(links=[_link(src)] if src is not None else ())
    return types.SimpleNamespace(type="TEX_ENVIRONMENT", image=img,
                                 inputs={"Vector": vec})


@pytest.mark.parametrize("vt,want", [("POINT", 0.7), ("VECTOR", 0.7),
                                     ("NORMAL", 0.7), ("TEXTURE", -0.7)])
def test_mapping_offset_by_vector_type(pl, vt, want):
    assert pl["_env_mapping_z_offset"](_env(_mapping(vt))) == pytest.approx(want)


def test_mapping_offset_ignored_cases(pl):
    f = pl["_env_mapping_z_offset"]
    assert f(_env()) == 0.0                                   # Vector не связан
    assert f(_env(_mapping(mute=True))) == 0.0                # Mapping выключен
    tex = types.SimpleNamespace(type="TEX_COORD", name="Texture Coordinate")
    assert f(_env(tex)) == 0.0                                # не Mapping
    assert f(types.SimpleNamespace(inputs={})) == 0.0         # не прочиталось


def test_mapping_through_reroutes(pl):
    node = _mapping()
    for _ in range(2):
        node = types.SimpleNamespace(type="REROUTE", name="Reroute",
                                     inputs=[_sock(links=[_link(node)])])
    assert pl["_env_mapping_z_offset"](_env(node)) == pytest.approx(0.7)


@pytest.mark.parametrize("kw,warn", [
    ({}, False),
    ({"scale": (2.0, 2.0, 2.0)}, False),                      # вектор нормализуется
    ({"vt": "VECTOR", "loc": (5.0, 0.0, 0.0)}, False),        # VECTOR без Location
    ({"rot": (0.3, 0.0)}, True),
    ({"scale": (1.0, 2.0, 1.0)}, True),
    ({"scale": (-1.0, -1.0, -1.0)}, True),
    ({"loc": (5.0, 0.0, 0.0)}, True),
])
def test_mapping_warning_once(pl, capsys, kw, warn):
    f = pl["_env_mapping_z_offset"]
    env = _env(_mapping(**kw))
    f(env, "World")
    f(env, "World")
    assert capsys.readouterr().out.count("[INU prelight] World Mapping") == int(warn)


# ── _world_env_sample: мир сцены с Mapping ──────────────────────────────

def _scene_world(pl, env, strength=1.0):
    bg = types.SimpleNamespace(type="BACKGROUND",
                               inputs={"Strength": _sock(strength),
                                       "Color": _sock((0.0, 0.0, 0.0, 1.0))})
    world = types.SimpleNamespace(
        name="World", use_nodes=True,
        node_tree=types.SimpleNamespace(nodes=[env, bg]))
    pl["bpy"].context = types.SimpleNamespace(
        scene=types.SimpleNamespace(world=world))


@pytest.mark.parametrize("vt,col", [(None, 1), ("POINT", 0), ("TEXTURE", 2)])
def test_world_env_sample_uses_mapping(pl, vt, col):
    # (1,1,0): az 45° → u 0.375 (столбец 1); POINT Z=90° → поиск 135°
    # (u 0.125, столбец 0); TEXTURE → поиск −45° (u 0.625, столбец 2).
    src = None if vt is None else _mapping(vt, rz=math.pi / 2)
    _scene_world(pl, _env(src, _img(4, 2)), strength=2.0)
    out = pl["_world_env_sample"](np.array([[1.0, 1.0, 0.0]]))
    assert out[0, 0] == pytest.approx(2.0 * col)


def test_world_env_sample_point_mapping_is_rotation(pl):
    """Mapping POINT по Z = Cycles R·v: выборка = выборка повёрнутой нормали."""
    theta = 1.1
    img = _img(64, 32)
    _scene_world(pl, _env(_mapping("POINT", rz=theta), img))
    rng = np.random.default_rng(3)
    d = rng.normal(size=(500, 3))
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    got = pl["_world_env_sample"](d)
    assert np.array_equal(got, pl["_sample_equirect"](img, d @ _rz(theta).T))
