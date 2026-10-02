"""D3D palettes follow librw: PAL4 streams 32 RGBA entries, PAL8 256.
D3D8 retains the historical core swap paired with txd_import's correction.
Vanilla III/VC/SA checks compare actual Blender pixel buffers to baseline3.
"""

import ast
import importlib
import sys
import types
from pathlib import Path
from struct import pack

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'INU_tools'))
from core import txd
from core.img import ImgReader


def _chunk(kind, body):
    return pack('<III', kind, len(body), 0x1803FFFF) + body


def _paletted(platform, pal4):
    count = 32 if pal4 else 256
    palette = bytes([250, 7, 19, 255, 11, 173, 91, 64]) + bytes((count - 2) * 4)
    indices = bytes([0, 1, 0, 1])
    header = (pack('<II', platform, 0) + b'colors'.ljust(32, b'\0') + bytes(32)
        + pack('<IIHHBBBB', txd.RASTER_8888 | (txd.RASTER_PAL4 if pal4 else txd.RASTER_PAL8),
               1 if platform == 8 else 41, 2, 2, 8, 1, 4, 0))
    native = _chunk(0x15, _chunk(1, header + palette + pack('<I', len(indices)) + indices) + _chunk(3, b''))
    return _chunk(0x16, _chunk(1, pack('<HH', 1, 0)) + native + _chunk(3, b''))


def _blender_pixels(textures):
    """Run the real upload/color correction method, without starting bpy."""
    node = next(n for n in ast.parse((ROOT / 'INU_tools/ops/txd_import.py').read_text(encoding='utf-8')).body
                if isinstance(n, ast.FunctionDef) and n.name == '_textures_to_blender_images')
    class Image:
        def __init__(self, *_a, **_kw):
            self.pixels = types.SimpleNamespace(foreach_set=lambda v: setattr(self, 'values', v.copy()))
        def pack(self): pass
        def update(self): pass
    images = types.SimpleNamespace(get=lambda _n: None, new=lambda *_a, **_kw: Image())
    ns = {'np': np, 'bpy': types.SimpleNamespace(data=types.SimpleNamespace(images=images)), '_SWAP_RB': False}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<txd upload>', 'exec'), ns)
    return [im.values for im in ns['_textures_to_blender_images'](textures, swap_rb=False)]


@pytest.mark.parametrize('platform', [8, 9])
@pytest.mark.parametrize('pal4', [False, True])
def test_palettes_have_correct_size_and_blender_channel_order(platform, pal4):
    textures = txd.read_txd(_paletted(platform, pal4))
    assert len(textures) == 1
    assert len(textures[0].pixels) == 16
    expected = np.array([[250, 7, 19, 255], [11, 173, 91, 64]] * 2, dtype=np.float32) / 255
    assert np.array_equal(_blender_pixels(textures)[0].reshape(-1, 4), expected)
    if platform == 9:
        assert textures[0].pixels[:4] == bytes([250, 7, 19, 255])


@pytest.mark.parametrize('game', ['III', 'Vice City', 'San Andreas'])
def test_vanilla_pixels_identical_to_previous_addon(game):
    baseline = Path(r'C:\Users\q3726\AppData\Local\Temp\claude\f--GitHub-INU-Tools-GTA-sa-\2264538f-8eea-40e1-b7a0-eb02385c8a89\scratchpad\baseline3\blender_INU_tools')
    archive = Path('D:/Grand Theft Auto ' + game + '/models/gta3.img')
    if not archive.is_file() or not (baseline / 'core/txd.py').is_file():
        pytest.skip('local vanilla game / baseline3 unavailable')
    pkg = types.ModuleType('_txd_palette_baseline')
    pkg.__path__ = [str(baseline)]
    sys.modules[pkg.__name__] = pkg
    old = importlib.import_module(pkg.__name__ + '.core.txd')
    compared = 0
    with ImgReader(str(archive)) as reader:
        for entry in reader.entries:
            if not entry.name.lower().endswith('.txd'):
                continue
            data = reader.read(entry.name)
            before, after = old.read_txd(data), txd.read_txd(data)
            if not before:
                continue
            assert [t.name for t in before] == [t.name for t in after]
            for x, y in zip(_blender_pixels(before), _blender_pixels(after)):
                assert np.array_equal(x, y), (game, entry.name)
            compared += 1
            if compared == 3:
                break
    assert compared == 3
