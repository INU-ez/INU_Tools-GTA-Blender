"""LightMap bake feature — unit tests that run WITHOUT Blender.

The bake modules `import bpy` / `import mathutils` at module top, so we stub
those and load the files by path (bypassing the package __init__, which pulls
in the whole bake subsystem). Everything we assert here is pure-Python:
  * the LIGHTMAP entry in the BAKE_MAPS registry,
  * the bilinear UV sampler (numpy only),
  * denoise_image graceful fallback with no Blender window.
"""
import sys
import types
import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
BAKE_DIR = ROOT / "INU_tools" / "tools" / "bake"


# Fake parent package so `from . import bake_core` inside bake_maps resolves.
_PKG = "inu_bake_test_pkg"
if _PKG not in sys.modules:
    pkg = types.ModuleType(_PKG)
    pkg.__path__ = [str(BAKE_DIR)]
    sys.modules[_PKG] = pkg


def _load(mod_name, filename):
    spec = importlib.util.spec_from_file_location(
        f"{_PKG}.{mod_name}", BAKE_DIR / filename)
    m = importlib.util.module_from_spec(spec)
    sys.modules[f"{_PKG}.{mod_name}"] = m
    spec.loader.exec_module(m)
    return m


# Blender-module stubs are needed ONLY while exec'ing the three modules (they
# `import bpy` / `import mathutils` at top but never touch them at import
# time). We install them, load, then REMOVE the ones we added — leaving a
# global `bpy` stub behind would make sibling tests that `importorskip('bpy')`
# stop skipping and then fail. The loaded modules keep their own reference to
# the stub in their globals, so runtime calls (denoise fallback) still work.
_stub_added = []
for _name in ("bpy", "mathutils"):
    if _name not in sys.modules:
        sys.modules[_name] = types.ModuleType(_name)
        _stub_added.append(_name)

try:
    bake_core = _load("bake_core", "bake_core.py")
    bake_maps = _load("bake_maps", "bake_maps.py")
    bake_uv = _load("bake_uv", "bake_uv.py")
finally:
    for _name in _stub_added:               # unpollute sys.modules
        sys.modules.pop(_name, None)

# bake_composite is pure numpy (no bpy) — load it standalone for the blur test.
bake_composite = _load("bake_composite", "bake_composite.py")


# ── Registry ─────────────────────────────────────────────────────────

def test_lightmap_registered():
    assert "LIGHTMAP" in bake_maps.BAKE_MAPS


def test_lightmap_bakes_real_scene_light():
    md = bake_maps.BAKE_MAPS["LIGHTMAP"]
    # Full GI from real scene light: DIFFUSE direct+indirect, NO albedo.
    assert md.bake_type == "DIFFUSE"
    assert md.pass_direct is True
    assert md.pass_indirect is True
    assert md.pass_color is False
    # Must NOT build an internal rig / isolate the scene (that's the whole
    # point — it uses the user's actual lights).
    assert md.needs_light is False
    assert md.rig_kind == "NONE"
    # Multiplies over the diffuse; noisy → high samples.
    assert md.default_blend == "MULTIPLY"
    assert md.samples >= 64


# ── Bilinear UV sampler ──────────────────────────────────────────────
# Blender pixel order is bottom-up, so v maps to row directly: v=0 → arr[0]
# (bottom), v=1 → arr[h-1] (top).

def _grid_2x2():
    # arr[y, x] = [y, x, 0, 1]  → each corner distinct.
    arr = np.zeros((2, 2, 4), np.float32)
    for y in range(2):
        for x in range(2):
            arr[y, x] = (float(y), float(x), 0.0, 1.0)
    return arr


def test_sample_corners():
    arr = _grid_2x2()
    assert np.allclose(bake_uv.sample_image_uv(arr, 0.0, 0.0), arr[0, 0])
    assert np.allclose(bake_uv.sample_image_uv(arr, 1.0, 0.0), arr[0, 1])
    assert np.allclose(bake_uv.sample_image_uv(arr, 0.0, 1.0), arr[1, 0])
    assert np.allclose(bake_uv.sample_image_uv(arr, 1.0, 1.0), arr[1, 1])


def test_sample_center_is_average():
    arr = _grid_2x2()
    mid = bake_uv.sample_image_uv(arr, 0.5, 0.5)
    assert np.allclose(mid, arr.reshape(-1, 4).mean(axis=0))


def test_sample_clamps_out_of_range():
    arr = _grid_2x2()
    # UV outside [0,1] clamps to the edge texel, no crash / no wrap.
    assert np.allclose(bake_uv.sample_image_uv(arr, -5.0, -5.0), arr[0, 0])
    assert np.allclose(bake_uv.sample_image_uv(arr, 9.0, 9.0), arr[1, 1])


def test_sample_batch_matches_scalar():
    arr = _grid_2x2()
    uvs = np.array([[0.0, 0.0], [1.0, 1.0], [0.5, 0.5], [0.25, 0.75]],
                   np.float32)
    batch = bake_uv.sample_image_uv_batch(arr, uvs)
    for i, (u, v) in enumerate(uvs):
        assert np.allclose(batch[i], bake_uv.sample_image_uv(arr, u, v))


# ── Denoise graceful fallback ────────────────────────────────────────

def test_denoise_fallback_without_blender():
    # No window / no bpy.context in the stub → must NOT raise, returns False.
    assert bake_core.denoise_image(None) is False


# ── Alpha map (transparency → alpha channel) ─────────────────────────

def test_alpha_registered():
    md = bake_maps.BAKE_MAPS["ALPHA"]
    # Baked as flat emission of the material's opacity (no light rig).
    assert md.bake_type == "EMIT"
    assert md.needs_light is False
    assert md.rig_kind == "NONE"
    # Has a material-swap builder (Cycles has no native alpha pass).
    assert callable(md.node_group_builder)


def test_composite_alpha_channel_from_alpha_map():
    # ALPHA layer feeds the output alpha channel and is EXCLUDED from the RGB
    # stack (a red diffuse stays red). The mask is a GTA cutout, not a
    # translucency ramp: >= 0.5 is solid, anything below it is a hole — the
    # same threshold bake_nodes applies when baking the map.
    LS = bake_composite.LayerSpec
    diffuse = np.array([[[1.0, 0.0, 0.0, 1.0],
                         [1.0, 0.0, 0.0, 1.0]]], np.float32)
    alpha = np.array([[[0.5, 0.5, 0.5, 1.0],     # on the threshold → solid
                       [0.4, 0.4, 0.4, 1.0]]], np.float32)   # Non-Color mask
    pixels = {"DIFFUSE": diffuse, "ALPHA": alpha}
    layers = [LS(map_id="ALPHA"), LS(map_id="DIFFUSE")]      # UI order: alpha on top
    out = bake_composite.composite_layers(pixels, layers, 2, 1, srgb=False)
    assert np.allclose(out[0, :, :3], [[1.0, 0.0, 0.0],
                                       [1.0, 0.0, 0.0]], atol=1e-5)
    assert abs(out[0, 0, 3] - 1.0) < 1e-5
    assert abs(out[0, 1, 3] - 0.0) < 1e-5


def test_composite_alpha_opacity_scales_strength():
    # opacity acts as an alpha-strength multiplier for the ALPHA layer.
    LS = bake_composite.LayerSpec
    diffuse = np.array([[[0.2, 0.2, 0.2, 1.0]]], np.float32)
    alpha = np.array([[[1.0, 1.0, 1.0, 1.0]]], np.float32)
    pixels = {"DIFFUSE": diffuse, "ALPHA": alpha}
    layers = [LS(map_id="ALPHA", opacity=0.25), LS(map_id="DIFFUSE")]
    out = bake_composite.composite_layers(pixels, layers, 1, 1, srgb=False)
    assert abs(out[0, 0, 3] - 0.25) < 1e-5


def test_composite_alpha_only_gives_black_rgb():
    # Only an ALPHA layer (e.g. a shadow decal alpha) → RGB black, alpha = the
    # cutout mask (0.8 is above the 0.5 threshold → solid, 0.2 → hole).
    LS = bake_composite.LayerSpec
    alpha = np.array([[[0.8, 0.8, 0.8, 1.0],
                       [0.2, 0.2, 0.2, 1.0]]], np.float32)
    out = bake_composite.composite_layers(
        {"ALPHA": alpha}, [LS(map_id="ALPHA")], 2, 1, srgb=False)
    assert np.allclose(out[0, :, :3], 0.0, atol=1e-5)
    assert abs(out[0, 0, 3] - 1.0) < 1e-5
    assert abs(out[0, 1, 3] - 0.0) < 1e-5


def test_composite_alpha_from_shadow_inverted():
    # Shadow decal: alpha sourced from Shadow map, inverted → lit=transparent,
    # shadowed=opaque. Shadow layer itself disabled in RGB (RGB stays black).
    LS = bake_composite.LayerSpec
    shadow = np.array([[[1.0, 1.0, 1.0, 1.0],    # lit
                        [0.0, 0.0, 0.0, 1.0]]], np.float32)   # shadowed (1,2,4)
    layers = [LS(map_id="ALPHA", alpha_source="SHADOW", alpha_invert=True),
              LS(map_id="SHADOW", enabled=False)]
    out = bake_composite.composite_layers({"SHADOW": shadow}, layers, 2, 1, srgb=False)
    assert np.allclose(out[0, 0, :3], [0.0, 0.0, 0.0], atol=1e-5)   # black decal
    assert abs(out[0, 0, 3] - 0.0) < 1e-5    # lit → transparent
    assert abs(out[0, 1, 3] - 1.0) < 1e-5    # shadow → opaque


def test_composite_alpha_from_shadow_not_inverted():
    # Without invert: lit=opaque, shadowed=transparent (opposite direction).
    LS = bake_composite.LayerSpec
    shadow = np.array([[[1.0, 1.0, 1.0, 1.0],
                        [0.0, 0.0, 0.0, 1.0]]], np.float32)
    layers = [LS(map_id="ALPHA", alpha_source="SHADOW", alpha_invert=False)]
    out = bake_composite.composite_layers({"SHADOW": shadow}, layers, 2, 1, srgb=False)
    assert abs(out[0, 0, 3] - 1.0) < 1e-5    # lit → opaque
    assert abs(out[0, 1, 3] - 0.0) < 1e-5    # shadow → transparent


def test_composite_decal_layer_threshold_removes_gray():
    # as_decal directly on the Shadow layer: threshold removes the gray floor,
    # keeps only the dark cast shadow. Layer excluded from RGB (RGB black).
    LS = bake_composite.LayerSpec
    shadow = np.array([[[0.1, 0.1, 0.1, 1.0],    # dark shadow
                        [0.5, 0.5, 0.5, 1.0],    # gray floor (light falloff)
                        [0.9, 0.9, 0.9, 1.0]]], np.float32)   # lit
    layers = [LS(map_id="SHADOW", as_decal=True,
                 decal_threshold=0.3, decal_softness=0.05)]
    out = bake_composite.composite_layers({"SHADOW": shadow}, layers, 3, 1, srgb=False)
    assert np.allclose(out[0, 0, :3], 0.0, atol=1e-5)   # black decal RGB
    assert out[0, 0, 3] > 0.9    # shadow → opaque
    assert out[0, 1, 3] < 0.1    # gray floor → removed
    assert out[0, 2, 3] < 0.1    # lit → removed


def test_composite_decal_hard_cut_softness_zero():
    # Softness 0 → hard binary cut: shadow fully black+opaque, rest fully
    # transparent (no gray gradient).
    LS = bake_composite.LayerSpec
    shadow = np.array([[[0.1, 0.1, 0.1, 1.0],    # dark
                        [0.6, 0.6, 0.6, 1.0]]], np.float32)   # light
    layers = [LS(map_id="SHADOW", as_decal=True,
                 decal_threshold=0.4, decal_softness=0.0)]
    out = bake_composite.composite_layers({"SHADOW": shadow}, layers, 2, 1, srgb=False)
    assert out[0, 0, 3] == 1.0    # dark → fully opaque
    assert out[0, 1, 3] == 0.0    # light → fully transparent
    assert np.allclose(out[0, 0, :3], 0.0)   # pure black


def test_composite_decal_invert_shows_light():
    LS = bake_composite.LayerSpec
    shadow = np.array([[[0.1, 0.1, 0.1, 1.0],
                        [0.9, 0.9, 0.9, 1.0]]], np.float32)
    layers = [LS(map_id="SHADOW", as_decal=True, decal_invert=True,
                 decal_threshold=0.3, decal_softness=0.05)]
    out = bake_composite.composite_layers({"SHADOW": shadow}, layers, 2, 1, srgb=False)
    assert out[0, 0, 3] < 0.1    # dark → hidden (inverted)
    assert out[0, 1, 3] > 0.9    # light → shown


def test_composite_without_alpha_keeps_base_coverage():
    # No ALPHA layer → alpha comes from the base layer's coverage (unchanged).
    LS = bake_composite.LayerSpec
    diffuse = np.array([[[0.3, 0.3, 0.3, 0.7]]], np.float32)
    out = bake_composite.composite_layers(
        {"DIFFUSE": diffuse}, [LS(map_id="DIFFUSE")], 1, 1, srgb=False)
    assert abs(out[0, 0, 3] - 0.7) < 1e-5


def test_denoise_fallback_accepts_feature_passes():
    # New albedo/normal kwargs must be accepted and still fail gracefully.
    assert bake_core.denoise_image(None, albedo=None, normal=None) is False


# ── Gaussian blur (LightMap softening post-process) ──────────────────

def _img(h, w, ch, fill):
    a = np.zeros((h, w, ch), np.float32)
    a[...] = fill
    return a


def test_blur_radius_zero_is_identity():
    a = np.random.rand(8, 8, 4).astype(np.float32)
    out = bake_composite.gaussian_blur(a, 0)
    assert out is a or np.array_equal(out, a)


def test_blur_preserves_constant_rgb():
    # A flat colour must survive a blur unchanged (edge-clamp, normalised kernel).
    a = _img(16, 16, 4, 0.5)
    out = bake_composite.gaussian_blur(a, 2.0)
    assert np.allclose(out[..., :3], 0.5, atol=1e-4)


def test_blur_leaves_alpha_untouched():
    a = _img(16, 16, 4, 0.5)
    a[..., 3] = np.linspace(0, 1, 16)[None, :].repeat(16, 0)  # varying alpha
    alpha_before = a[..., 3].copy()
    out = bake_composite.gaussian_blur(a, 2.0)
    assert np.array_equal(out[..., 3], alpha_before)   # alpha not blurred


def test_blur_spreads_energy_and_conserves_mean():
    # A single bright texel should spread to neighbours; total energy ~preserved.
    a = np.zeros((16, 16, 3), np.float32)
    a[8, 8, :] = 1.0
    out = bake_composite.gaussian_blur(a, 1.5)
    assert out[8, 8, 0] < 1.0          # peak spread out
    assert out[8, 9, 0] > 0.0          # neighbour lit
    assert abs(out[..., 0].sum() - 1.0) < 0.05   # energy ~conserved (edge-clamp)


def test_blur_does_not_mutate_input():
    a = _img(8, 8, 3, 0.3)
    a[4, 4, :] = 1.0
    ref = a.copy()
    bake_composite.gaussian_blur(a, 2.0)
    assert np.array_equal(a, ref)      # input untouched (returns new array)


# ── Bilateral denoise (numpy fallback for the OIDN compositor) ───────

def test_bilateral_preserves_constant():
    a = _img(16, 16, 4, 0.5)
    out = bake_composite.bilateral_denoise(a)
    assert np.allclose(out[..., :3], 0.5, atol=1e-4)


def test_bilateral_leaves_alpha_untouched():
    a = _img(16, 16, 4, 0.5)
    a[..., 3] = np.linspace(0, 1, 16)[None, :].repeat(16, 0)
    alpha = a[..., 3].copy()
    out = bake_composite.bilateral_denoise(a)
    assert np.array_equal(out[..., 3], alpha)


def test_bilateral_reduces_noise_variance():
    # A noisy constant field: denoise should cut variance while keeping the mean.
    rng = np.random.RandomState(0)
    base = 0.5
    a = np.clip(base + rng.normal(0, 0.15, (32, 32, 3)), 0, 1).astype(np.float32)
    out = bake_composite.bilateral_denoise(a, radius=3)
    assert out[..., :3].var() < a[..., :3].var()          # smoother
    assert abs(out[..., :3].mean() - a[..., :3].mean()) < 0.03   # mean kept


def test_bilateral_does_not_mutate_input():
    a = _img(8, 8, 3, 0.3)
    a[4, 4, :] = 1.0
    ref = a.copy()
    bake_composite.bilateral_denoise(a)
    assert np.array_equal(a, ref)


def test_bilateral_radius_zero_identity():
    a = np.random.rand(8, 8, 4).astype(np.float32)
    out = bake_composite.bilateral_denoise(a, radius=0)
    assert out is a or np.array_equal(out, a)


# ── sRGB↔linear + linear-space composite (over-base ↔ node preview match) ──

def test_srgb_linear_roundtrip():
    x = np.linspace(0.0, 1.0, 64).astype(np.float32)
    back = bake_composite.srgb_to_linear(bake_composite.linear_to_srgb(x))
    assert np.allclose(back, x, atol=1e-5)
    back2 = bake_composite.linear_to_srgb(bake_composite.srgb_to_linear(x))
    assert np.allclose(back2, x, atol=1e-5)


def test_composite_single_layer_is_identity():
    # One layer, no cg / no blend → output RGB == input (the srgb→linear→srgb
    # roundtrip must not change a lone layer). Guards the linear-space switch.
    px = np.random.rand(8, 8, 4).astype(np.float32)
    spec = bake_composite.LayerSpec(map_id='AO')
    out = bake_composite.composite_layers({'AO': px}, [spec], 8, 8, srgb=True)
    assert np.allclose(out[..., :3], px[..., :3], atol=1e-4)
    assert np.allclose(out[..., 3], px[..., 3], atol=1e-6)   # alpha from base


def test_composite_contrast_applied_in_linear():
    # Contrast pivots at LINEAR 0.5. A mid-sRGB-gray input (~0.5 sRGB ≈ 0.214
    # linear) under contrast>1 should move AWAY from linear 0.5 → darker, not
    # brighter (which is what an sRGB-space pivot would give). Pins the space.
    px = np.full((4, 4, 4), 0.5, np.float32)      # sRGB 0.5
    spec = bake_composite.LayerSpec(map_id='AO', contrast=2.0)
    out = bake_composite.composite_layers({'AO': px}, [spec], 4, 4, srgb=True)
    # linear 0.214, contrast 2 → (0.214-0.5)*2+0.5 = -0.072 → clip 0 → srgb 0
    assert out[..., :3].mean() < 0.4
