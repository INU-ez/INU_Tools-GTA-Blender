"""tools.txd_export — per-game texture-native platform.

III/VC PC (RW 3.3–3.5) register only the D3D8 native reader, so a TXD
written for them must carry platform id 8 with the D3D8 struct layout
(``hasAlpha`` word instead of a D3DFORMAT fourcc, DXT number instead of
the D3D9 flags byte). SA keeps the D3D9 layout. Each variant is run
through ``core.txd_lint.check_txd`` for the matching game — the same
audit the export operator applies — and must come back with no fatals.
Also pins the game-profile facts behind the writer choices.
"""

from pathlib import Path
from struct import pack, unpack_from
import sys
import types

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))


def _ensure_bpy_stubs():
    bpy_mod = sys.modules.get('bpy')
    if bpy_mod is None:
        bpy_mod = types.ModuleType('bpy')
        sys.modules['bpy'] = bpy_mod
    if not hasattr(bpy_mod, 'types'):
        class _D:  # noqa: D401
            pass
        bpy_mod.types = types.SimpleNamespace(Operator=_D, Panel=_D, PropertyGroup=_D)
        sys.modules['bpy.types'] = bpy_mod.types
    if not hasattr(bpy_mod, 'props'):
        bpy_mod.props = types.SimpleNamespace(
            StringProperty=lambda **kw: None, IntProperty=lambda **kw: None,
            FloatProperty=lambda **kw: None, BoolProperty=lambda **kw: None,
            EnumProperty=lambda **kw: None)
        sys.modules['bpy.props'] = bpy_mod.props
    if not hasattr(bpy_mod, 'context'):
        bpy_mod.context = types.SimpleNamespace(scene=None)


_ensure_bpy_stubs()
_pkg_root = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
_pkg_root.__path__ = [str(ROOT / "INU_tools")]
_pkg_root.T = lambda s, *_a, **_kw: s

from INU_tools.tools import txd_export as tx           # noqa: E402
from INU_tools.core.txd_lint import check_txd          # noqa: E402
from INU_tools.core import game_versions as gv         # noqa: E402
from INU_tools.core.dff import make_library_id         # noqa: E402


# ── helpers ──────────────────────────────────────────────────────

def _scene(game):
    return types.SimpleNamespace(inu_settings=types.SimpleNamespace(gtatools_game=game))


def _fake_bc1(pixels, mip_index):
    h, w = pixels.shape[:2]
    return b'\x00' * (max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8)


def _fake_bc2(pixels, mip_index):
    h, w = pixels.shape[:2]
    return b'\x00' * (max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16)


def _native(game, use_alpha, w=16, h=8):
    """One tex-native section (0x15 header + struct + extension) written
    the way export_txd would for ``game``."""
    tx._active_lib_id = make_library_id(gv.rw_version_for_game(game))
    tx._active_platform = tx._resolve_platform_for_scene(_scene(game))
    pixels = np.zeros((h, w, 4), dtype=np.uint8)
    pixels[..., 3] = 255
    body = tx._build_tex_native_from_pixels(('tex', pixels, w, h, use_alpha),
                                            _fake_bc1, _fake_bc2)
    sect = bytearray()
    tx.write_rw_section_header(sect, tx.RW_TEXTURENATIVE, len(body))
    sect.extend(body)
    return bytes(sect)


def _txd(game, sections):
    lib = tx._active_lib_id
    struct_body = pack('<HH', len(sections), 0)
    struct_sect = pack('<III', tx.RW_STRUCT, len(struct_body), lib) + struct_body
    ext = pack('<III', tx.RW_EXTENSION, 0, lib)
    content = struct_sect + b''.join(sections) + ext
    return pack('<III', tx.RW_TEXDICTIONARY, len(content), lib) + content


def _struct_fields(section):
    """(platform, word_after_raster_format, last_byte) of the native struct."""
    p = 12 + 12                       # 0x15 header + struct header
    platform = unpack_from('<I', section, p)[0]
    word = unpack_from('<I', section, p + 8 + 64 + 4)[0]
    last = section[p + 8 + 64 + 4 + 4 + 4 + 3]
    return platform, word, last


# ── platform selection ───────────────────────────────────────────

def test_platform_by_game():
    assert tx._resolve_platform_for_scene(_scene('SA')) == tx.PLATFORM_D3D9
    assert tx._resolve_platform_for_scene(_scene('VC')) == tx.PLATFORM_D3D8
    assert tx._resolve_platform_for_scene(_scene('III')) == tx.PLATFORM_D3D8
    assert tx._resolve_platform_for_scene(None) == tx.PLATFORM_D3D9


def test_sa_native_keeps_d3d9_layout():
    s = _native('SA', use_alpha=True)
    platform, word, last = _struct_fields(s)
    assert platform == 9
    assert word == 0x33545844          # 'DXT3' fourcc
    assert last == 0x09                # compressed | alpha


@pytest.mark.parametrize('game', ['VC', 'III'])
@pytest.mark.parametrize('use_alpha,want_alpha,want_dxt', [(False, 0, 1), (True, 1, 3)])
def test_d3d8_native_layout(game, use_alpha, want_alpha, want_dxt):
    s = _native(game, use_alpha)
    platform, word, last = _struct_fields(s)
    assert platform == 8
    assert word == want_alpha          # hasAlpha, no fourcc on D3D8
    assert last == want_dxt            # DXT number, not the D3D9 flags byte


@pytest.mark.parametrize('game', ['SA', 'VC', 'III'])
def test_lint_accepts_native_for_its_game(game):
    sections = [_native(game, False), _native(game, True)]
    fatal, _warn = check_txd(_txd(game, sections), target=game)
    assert fatal == [], fatal


def test_lint_rejects_sa_native_for_vc():
    """The pre-fix behaviour: a D3D9 native handed to VC fails to load."""
    sections = [_native('SA', False)]
    fatal, _ = check_txd(_txd('SA', sections), target='VC')
    assert any('TXD-PLATFORM' in f for f in fatal)


def test_cache_key_separates_games():
    img = types.SimpleNamespace(session_uid=7, size=(16, 16))
    tx._active_platform = tx.PLATFORM_D3D9
    k_sa = tx._cache_key('t', img, False, 'numpy')
    tx._active_platform = tx.PLATFORM_D3D8
    k_vc = tx._cache_key('t', img, False, 'numpy')
    assert k_sa != k_vc


# ── game profiles the writers rely on ────────────────────────────

def test_profiles_iii_vc_facts():
    """re3/reVC: FileLoader asserts 'COLL'; MODELINFOSIZE 5500/6500;
    VC inst = 13 columns (interior); VC has Extra Vert Colours."""
    vc, iii, sa = gv.profile_for('VC'), gv.profile_for('III'), gv.profile_for('SA')
    assert vc.col_version == 1 and iii.col_version == 1 and sa.col_version == 3
    assert iii.model_id_max == 5500 and vc.model_id_max == 6500
    assert iii.ipl_inst_columns == 12 and vc.ipl_inst_columns == 13 and sa.ipl_inst_columns == 11
    assert vc.dff_supports_night_vertex_colors and not iii.dff_supports_night_vertex_colors


def test_detect_game_from_col_magic(tmp_path):
    for magic, want in ((b'COL3', 'SA'), (b'COL2', 'SA'), (b'COLL', None)):
        f = tmp_path / (magic.decode() + '.col')
        f.write_bytes(magic + b'\x00' * 60)
        assert gv.detect_game_from_col(str(f)) == want
