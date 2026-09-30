# Texture Browser preview (ops/texture_browser_ops._refresh_preview) wrote
# the decoder's pixels as-is, while TXD import (ops/txd_import.py) swaps R↔B
# for paletted (PAL8/PAL4) D3D8 textures — GTA III. So the browser showed III
# textures with red and blue swapped (Grass_128HV turquoise instead of green).
# The preview now applies the same platform_id == 8 + palette rule.
#
# texture_browser_ops imports bpy at module level, so pull the function out by
# AST and run it against a fake bpy.data.images and a fake decoder.

import ast
import io
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TB = os.path.join(ROOT, "INU_tools", "ops", "texture_browser_ops.py")


def _extract(path, funcs, names):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    keep = [n for n in tree.body
            if (isinstance(n, ast.FunctionDef) and n.name in funcs)
            or (isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id in names
                        for t in n.targets))]
    assert len(keep) == len(funcs) + len(names), path
    ns = {"__name__": "INU_tools.ops.texture_browser_ops",
          "__package__": "INU_tools.ops"}
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), ns)
    return ns


NS = _extract(TB, {"_refresh_preview"}, {"_PREVIEW_IMG_NAME"})


class _Pixels:
    def __init__(self):
        self.data = None

    def foreach_set(self, seq):
        self.data = [float(v) for v in seq]


class _Image:
    def __init__(self, name, width, height):
        self.name = name
        self.size = [width, height]
        self.pixels = _Pixels()

    def update(self):
        pass

    def values(self):
        p = self.pixels
        return p.data if isinstance(p, _Pixels) else [float(v) for v in p]


class _Images(dict):
    def new(self, name, width, height, alpha=True):
        img = self[name] = _Image(name, width, height)
        return img

    def remove(self, img, do_unlink=True):
        self.pop(img.name, None)


@pytest.fixture
def run_preview(monkeypatch):
    """Run _refresh_preview on one fake texture; return the preview pixels."""
    images = _Images()
    monkeypatch.setitem(NS, "bpy", types.SimpleNamespace(
        data=types.SimpleNamespace(images=images)))

    def _run(tex):
        ti = types.ModuleType("INU_tools.core.texture_index")
        ti.decode_one_texture = lambda *_a: tex
        core = types.ModuleType("INU_tools.core")
        core.__path__ = []
        core.texture_index = ti
        pkg = types.ModuleType("INU_tools")
        pkg.__path__ = []
        pkg.core = core
        monkeypatch.setitem(sys.modules, "INU_tools", pkg)
        monkeypatch.setitem(sys.modules, "INU_tools.core", core)
        monkeypatch.setitem(sys.modules, "INU_tools.core.texture_index", ti)

        item = types.SimpleNamespace(archive_path="x.img", txd_name="t",
                                     texture_name="n")
        ctx = types.SimpleNamespace(
            window_manager=types.SimpleNamespace(
                gtatools_texture_browser_results=[item],
                gtatools_texture_browser_results_index=0),
            scene=None)
        NS["_refresh_preview"](ctx)
        return images[NS["_PREVIEW_IMG_NAME"]].values()

    return _run


def _tex(platform_id, raster_format, pixels, w=1, h=1):
    return types.SimpleNamespace(platform_id=platform_id,
                                 raster_format=raster_format,
                                 pixels=bytes(pixels), width=w, height=h)


def _expect(values, want):
    assert values == pytest.approx([v / 255.0 for v in want], abs=1e-6)


@pytest.mark.parametrize("raster_format", [0x2000, 0x4000, 0x2600, 0x4500])
def test_d3d8_paletted_swaps_rb(run_preview, raster_format):
    # PAL8 / PAL4 (with 8888 / 888 base) on D3D8 = GTA III → R↔B.
    _expect(run_preview(_tex(8, raster_format, [1, 2, 3, 4])), [3, 2, 1, 4])


@pytest.mark.parametrize("platform_id,raster_format", [
    (9, 0x2000),    # D3D9 palette (SA) — as import: no swap
    (8, 0x0200),    # D3D8 16-bit (VC) — no palette
    (9, 0x0500),    # D3D9 8888
])
def test_other_textures_untouched(run_preview, platform_id, raster_format):
    _expect(run_preview(_tex(platform_id, raster_format, [1, 2, 3, 4])),
            [1, 2, 3, 4])


def test_swap_keeps_row_flip(run_preview):
    # 1×2: top row first in the decoder, bottom row first in Blender.
    tex = _tex(8, 0x2000, [10, 20, 30, 40, 50, 60, 70, 80], w=1, h=2)
    _expect(run_preview(tex), [70, 60, 50, 80, 30, 20, 10, 40])


def test_fallback_without_numpy_swaps_too(run_preview, monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", None)   # import numpy → ImportError
    tex = _tex(8, 0x2000, [10, 20, 30, 40, 50, 60, 70, 80], w=1, h=2)
    _expect(run_preview(tex), [70, 60, 50, 80, 30, 20, 10, 40])
    _expect(run_preview(_tex(9, 0x2000, [1, 2, 3, 4])), [1, 2, 3, 4])
