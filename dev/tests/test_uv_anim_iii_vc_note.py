# GTA III/VC have no RpUVAnim plugin (re3/reVC PluginAttach), so the DFF
# writer skips the UV Anim Dict (0x2B) and material PLG 0x135 below RW 3.5.
# That used to happen silently; export now reports the dropped animations.
# _uv_anim_dropped_names decides what to report.
#
# dff_export imports bpy at module level, so pull the function out by AST.

import ast
import io
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "INU_tools", "ops", "dff_export.py")
sys.path.insert(0, os.path.join(ROOT, "INU_tools"))

from core.dff import DffClump, UVAnim, UVAnimDict  # noqa: E402

KEY = 'UV-анимация не записана: в GTA III/VC её нет ({0})'

III, VC, SA = 0x33002, 0x34003, 0x36003


def _load():
    tree = ast.parse(io.open(MODULE, encoding="utf-8").read())
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "_uv_anim_dropped_names"]
    assert keep, "_uv_anim_dropped_names not found in dff_export.py"
    ns = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), MODULE, "exec"), ns)
    return ns["_uv_anim_dropped_names"]


dropped = _load()


def _clump(version, names=("water",)):
    c = DffClump(version=version)
    c.uv_anim_dict = UVAnimDict(anims=[UVAnim(name=n) for n in names]) if names else None
    return c


def test_iii_reports_names():
    assert dropped(_clump(III), III) == ["water"]


def test_vc_reports_names():
    assert dropped(_clump(VC, ("water", "belt")), VC) == ["water", "belt"]


def test_sa_reports_nothing():
    assert dropped(_clump(SA), SA) == []


def test_no_dict_reports_nothing():
    assert dropped(_clump(VC, None), VC) == []
    assert dropped(_clump(VC, ()), VC) == []
    assert dropped(object(), III) == []


def _first_chunk_id(clump):
    return struct.unpack_from("<I", clump.to_bytes(), 0)[0]


def test_core_skips_dict_below_rw35():
    # The note matches what the writer actually does.
    assert _first_chunk_id(_clump(III)) == 0x10
    assert _first_chunk_id(_clump(VC)) == 0x10
    assert _first_chunk_id(_clump(SA)) == 0x2B


def test_note_key_translated_and_used():
    for name in ("eng", "spa"):
        ns = {}
        path = os.path.join(ROOT, "INU_tools", "locale", name + ".py")
        exec(compile(io.open(path, encoding="utf-8").read(), path, "exec"), ns)
        assert "{0}" in ns["LANG"][KEY]
    for rel in (("ops", "dff_export.py"), ("ops", "img_ops.py")):
        src = io.open(os.path.join(ROOT, "INU_tools", *rel), encoding="utf-8").read()
        assert "T('" + KEY + "')" in src
