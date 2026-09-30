# COL surface bytes on export (ops/col_export.py).
#
# 1. The writer packs material / flags / brightness / light with '<4B', and
#    the object/material IntProperties behind them have no min/max — a value
#    past 0..255 (material «Яркость» is editable in the UI) aborted the whole
#    COL / DFF / IMG export with struct.error. _u8 now clamps every byte.
# 2. 'AUTO' collision light puts the scene day/night of spheres/boxes into
#    the byte SA loads as CColSphere/CColBox m_nLighting: the 3rd
#    (brightness) for COL2/COL3 (records copied as is, gta_sa 0x412AA0),
#    the 4th (light) for COL1 (loader 0x537580 passes it to Set);
#    'MATERIAL' keeps the object's bytes.
#
# col_export imports bpy at module level, so pull the functions out by AST
# (with whatever module-level helpers they call).

import ast
import io
import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "INU_tools", "ops", "col_export.py")
sys.path.insert(0, os.path.join(ROOT, "INU_tools"))

import core.col as col  # noqa: E402
from core.col import (  # noqa: E402
    ColModel, ColFace, Surface, Vec3, write_col, read_col,
)

WANTED = {"_u8", "_apply_auto_light", "_get_surface_from_material",
          "_collect_sphere", "_collect_box"}


def _load():
    tree = ast.parse(io.open(MODULE, encoding="utf-8").read())
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    need, todo = set(), list(WANTED)
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
    ns = {k: getattr(col, k) for k in dir(col) if not k.startswith("__")}
    ns["T"] = lambda s: s
    exec(compile(ast.Module(body=keep, type_ignores=[]), MODULE, "exec"), ns)
    return ns


NS = _load()
u8 = NS["_u8"]


# ── stand-ins for bpy objects ────────────────────────────────────────────

class _V:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def __iter__(self):
        return iter((self.x, self.y, self.z))


def _empty(**inu):
    return SimpleNamespace(location=_V(1.0, 2.0, 3.0), scale=_V(1.0, 1.0, 1.0),
                           empty_display_size=0.5,
                           empty_display_type='SPHERE',
                           inu=SimpleNamespace(**inu))


def _material(**inu):
    inu.setdefault('col_source_game', '')
    return SimpleNamespace(inu=SimpleNamespace(**inu))


def _surf(s):
    return (s.material, s.flags, s.brightness, s.light)


@pytest.fixture
def auto_light(monkeypatch):
    """Scene in 'AUTO' collision-light mode (day/night settable)."""
    st = SimpleNamespace(gtatools_col_light_mode='AUTO',
                         gtatools_col_auto_day=14, gtatools_col_auto_night=4)
    fake = SimpleNamespace(context=SimpleNamespace(
        scene=SimpleNamespace(inu_settings=st)))
    monkeypatch.setitem(NS, "bpy", fake)
    return st


# ── _u8 ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("v, want", [
    (300, 255), (256, 255), (-1, 0), (7, 7), (0, 0), (255, 255),
    (0x4E, 0x4E), (0xBB, 0xBB),
])
def test_u8(v, want):
    assert u8(v) == want


# ── material surface (faces) ─────────────────────────────────────────────

def test_material_surface_clamped():
    mat = _material(col_mat_index=1, col_flags=300, col_brightness=300,
                    col_day_light=14, col_night_light=4)
    assert _surf(NS["_get_surface_from_material"](mat)) == (1, 255, 255, 0x4E)


def test_material_surface_valid_unchanged():
    mat = _material(col_mat_index=9, col_flags=3, col_brightness=0xBB,
                    col_day_light=11, col_night_light=11)
    assert _surf(NS["_get_surface_from_material"](mat)) == (9, 3, 0xBB, 0xBB)


def _tri_model(version, surface, shadow=False):
    m = ColModel(version=version, model_name="t")
    verts = [Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)]
    if shadow:
        m.shadow_vertices = verts
        m.shadow_faces = [ColFace(0, 1, 2, surface)]
    else:
        m.vertices = verts
        m.faces = [ColFace(0, 1, 2, surface)]
    return m


@pytest.mark.parametrize("game", ["III", "SA"])
def test_col1_face_out_of_range_writes(game):
    # COL1 faces carry the full 4-byte surface — brightness 300 used to
    # raise struct.error here.
    mat = _material(col_mat_index=1, col_flags=300, col_brightness=300,
                    col_day_light=14, col_night_light=4)
    surface = NS["_get_surface_from_material"](mat)
    parsed = read_col(write_col([_tri_model(1, surface)], target_game=game))[0]
    assert _surf(parsed.faces[0].surface) == (1, 255, 255, 0x4E)


def test_shadow_face_material_over_255_writes():
    # Shadow faces skip the target-game surface clamp in core.col.
    mat = _material(col_mat_index=300, col_flags=0, col_brightness=0,
                    col_day_light=0, col_night_light=0)
    surface = NS["_get_surface_from_material"](mat)
    assert surface.material == 255
    write_col([_tri_model(3, surface, shadow=True)], target_game="SA")


# ── spheres / boxes ──────────────────────────────────────────────────────

@pytest.mark.parametrize("collect, attr",
                         [("_collect_sphere", "spheres"), ("_collect_box", "boxes")])
def test_prim_out_of_range_material_mode(collect, attr):
    # No bpy scene → 'MATERIAL': bytes come from the object, clamped.
    obj = _empty(col_material=12, col_flags=-1, col_brightness=300,
                 col_light=256)
    for version in (1, 2, 3):
        model = ColModel(version=version, model_name="t")
        NS[collect](obj, model)
        prim = getattr(model, attr)[0]
        assert _surf(prim.surface) == (12, 0, 255, 255)
        parsed = read_col(write_col([model], target_game="SA"))[0]
        assert _surf(getattr(parsed, attr)[0].surface) == (12, 0, 255, 255)


@pytest.mark.parametrize("collect, attr",
                         [("_collect_sphere", "spheres"), ("_collect_box", "boxes")])
def test_prim_valid_bytes_kept_material_mode(collect, attr):
    obj = _empty(col_material=5, col_flags=0, col_brightness=0xBB,
                 col_light=0x41)
    model = ColModel(version=3, model_name="t")
    NS[collect](obj, model)
    assert _surf(getattr(model, attr)[0].surface) == (5, 0, 0xBB, 0x41)


@pytest.mark.parametrize("collect, attr",
                         [("_collect_sphere", "spheres"), ("_collect_box", "boxes")])
def test_prim_auto_light_goes_to_third_byte(auto_light, collect, attr):
    obj = _empty(col_material=5, col_flags=0, col_brightness=0xBB,
                 col_light=0x41)
    for version in (2, 3):
        model = ColModel(version=version, model_name="t")
        NS[collect](obj, model)
        # day 14 / night 4 → 0x4E in brightness; the 4th byte stays as is
        assert _surf(getattr(model, attr)[0].surface) == (5, 0, 0x4E, 0x41)
        parsed = read_col(write_col([model], target_game="SA"))[0]
        assert getattr(parsed, attr)[0].surface.brightness == 0x4E


@pytest.mark.parametrize("collect, attr",
                         [("_collect_sphere", "spheres"), ("_collect_box", "boxes")])
def test_prim_auto_light_col1_goes_to_fourth_byte(auto_light, collect, attr):
    # SA's COL1 loader hands the 4th byte to CColSphere/CColBox::Set as
    # the lighting; the 3rd stays as the object has it.
    obj = _empty(col_material=5, col_flags=0, col_brightness=0xBB,
                 col_light=0x41)
    model = ColModel(version=1, model_name="t")
    NS[collect](obj, model)
    assert _surf(getattr(model, attr)[0].surface) == (5, 0, 0xBB, 0x4E)
    parsed = read_col(write_col([model], target_game="SA"))[0]
    assert getattr(parsed, attr)[0].surface.light == 0x4E


def test_auto_light_custom_day_night(auto_light):
    auto_light.gtatools_col_auto_day = 15
    auto_light.gtatools_col_auto_night = 0
    s = Surface(material=1, flags=2, brightness=0, light=300)
    NS["_apply_auto_light"](s)
    assert (s.brightness, s.light) == (0x0F, 300)
    s = Surface(material=1, flags=2, brightness=0xBB, light=0)
    NS["_apply_auto_light"](s, 1)
    assert (s.brightness, s.light) == (0xBB, 0x0F)


def test_auto_light_material_mode_untouched():
    for version in (1, 3):
        s = Surface(material=1, flags=2, brightness=0xBB, light=0x41)
        NS["_apply_auto_light"](s, version)
        assert _surf(s) == (1, 2, 0xBB, 0x41)


# ── «День»/«Ночь» tooltips of the 'AUTO' mode are translated ─────────────

def test_auto_light_tooltips_translated():
    tree = ast.parse(io.open(os.path.join(ROOT, "INU_tools", "scene_settings.py"),
                             encoding="utf-8").read())
    descs = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id in ("gtatools_col_auto_day",
                                       "gtatools_col_auto_night")):
            for kw in node.annotation.keywords:
                if kw.arg == "description":
                    descs[node.target.id] = kw.value.args[0].value
    assert len(descs) == 2
    langs = []
    for name in ("eng", "spa"):
        ns = {}
        path = os.path.join(ROOT, "INU_tools", "locale", name + ".py")
        exec(compile(io.open(path, encoding="utf-8").read(), path, "exec"), ns)
        langs.append(ns["LANG"])
    for text in descs.values():
        assert "байта освещения" in text
        assert all(text in lang for lang in langs)
