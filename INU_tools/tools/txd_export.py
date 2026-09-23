# INU_tools.tools.txd_export — TXD texture archive export

import bpy
import struct
import os
import time
import numpy as np
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from .. import T


# ─────────────────────────────────────────────────────────────────────
# Per-session DXT cache — keyed by Image.session_uid + name + size +
# alpha-mode + backend. Hit-path skips the entire prepare→encode→assemble
# pipeline and reuses the previously emitted tex_native bytes.
#
# Invalidation comes for free from Blender: session_uid changes whenever
# the user reloads/replaces an Image datablock (Image > Reload, importing
# a new file under the same name, etc.). It does NOT detect in-place
# pixel edits in the Image Editor — fine for game-modding workflow where
# textures originate from .png/.dds files.
#
# LRU with a soft cap so a long Blender session iterating over many
# different texture sets doesn't grow memory unbounded. Each entry is
# ~50KB–1MB depending on resolution; cap × 256 ≈ 200MB worst case.
# ─────────────────────────────────────────────────────────────────────

_TEXTURE_CACHE = OrderedDict()
_TEXTURE_CACHE_LIMIT = 256


def _cache_key(name, image, use_alpha, backend):
    """Stable cache key. ``None`` means "don't cache" (older Blender)."""
    try:
        uid = image.session_uid
    except AttributeError:
        return None  # Pre-4.0 Blender — no stable per-datablock UID
    # lib_id / platform are baked into the cached bytes — a game switch
    # (SA→VC) must not hand back a D3D9 native written for SA.
    return (uid, name, image.size[0], image.size[1], bool(use_alpha), backend,
            _active_lib_id, _active_platform)


def _cache_get(key):
    if key is None or key not in _TEXTURE_CACHE:
        return None
    _TEXTURE_CACHE.move_to_end(key)
    return _TEXTURE_CACHE[key]


def _cache_set(key, value):
    if key is None:
        return
    _TEXTURE_CACHE[key] = value
    _TEXTURE_CACHE.move_to_end(key)
    while len(_TEXTURE_CACHE) > _TEXTURE_CACHE_LIMIT:
        _TEXTURE_CACHE.popitem(last=False)


def clear_dxt_cache():
    """Drop all cached tex_native bytes. Useful after manual pixel edits
    in the Image Editor that the session_uid heuristic doesn't catch."""
    _TEXTURE_CACHE.clear()

# =============================================================================
# TXD EXPORTER
# =============================================================================

RW_TEXDICTIONARY = 0x16
RW_TEXTURENATIVE = 0x15
RW_STRUCT = 0x01
RW_EXTENSION = 0x03
# Encoded library-ID form (RW version + build): 0x1803FFFF = SA + 0xFFFF
# build. III/VC use lower encodings — see ``_resolve_lib_id_for_scene``.
# Kept as the historical name + value for backward compatibility with
# any external callers; new code reads ``_active_lib_id`` instead.
RW_VERSION = 0x1803FFFF
_active_lib_id = RW_VERSION   # mutated transiently by export_txd
PLATFORM_D3D8 = 8             # III / VC PC (RW 3.3–3.5: no D3D9 driver)
PLATFORM_D3D9 = 9             # SA
_active_platform = PLATFORM_D3D9   # mutated transiently by export_txd
RASTER_565 = 0x0200
RASTER_4444 = 0x0300
RASTER_8888 = 0x0500
RASTER_MIPMAP = 0x8000
FILTER_LINEAR = 0x02             # билинейно, БЕЗ мипов (рябь вдали)
FILTER_LINEARMIPLINEAR = 0x06    # трилинейно: мипы + плавный переход (гладко)
ADDRESS_WRAP = 0x01


def _resolve_lib_id_for_scene(scene) -> int:
    """Compute the RW library-ID for TXD chunk headers based on the
    scene's active game. Falls back to SA for missing/unknown values."""
    try:
        from ..core import game_versions as gv
        from ..core.dff import make_library_id
        game = gv.game_of_scene(scene)
        return make_library_id(gv.rw_version_for_game(game))
    except Exception:
        return RW_VERSION


def _resolve_platform_for_scene(scene) -> int:
    """Texture-native platform id for the scene's game: III/VC read only
    the D3D8 native (their RW has no D3D9 driver — `_rwD3D8NativeTextureRead`
    is the only registered reader), SA reads both but is written as D3D9."""
    try:
        from ..core import game_versions as gv
        return PLATFORM_D3D9 if gv.game_of_scene(scene) == gv.GAME_SA else PLATFORM_D3D8
    except Exception:
        return PLATFORM_D3D9


def make_filter_flags(mip_count=1):
    """Флаги фильтра+адресации текстуры. При наличии мип-цепочки (mip_count>1)
    ставим LINEARMIPLINEAR (трилинейный) — иначе движок мипы игнорирует и вдали
    идёт рябь. Один мип → обычный LINEAR."""
    flt = FILTER_LINEARMIPLINEAR if mip_count > 1 else FILTER_LINEAR
    return flt | (ADDRESS_WRAP << 8) | (ADDRESS_WRAP << 12)


def write_rw_section_header(data, section_type, size):
    # Reads the module-level ``_active_lib_id`` so per-texture helpers
    # don't each need a lib_id parameter threaded through. export_txd
    # sets it once at the top and restores in `finally`.
    data.extend(struct.pack('<III', section_type, size, _active_lib_id))


def _linear_to_srgb(c):
    """scene-linear → sRGB (C1). Вход/выход float-массив в [0,1].

    ``image.pixels`` отдаёт значения в scene-linear для sRGB-картинок, а
    TXD (и движок) хранит ОТОБРАЖАЕМЫЕ sRGB-байты. Без этой конвертации
    `linear*255` пишется как sRGB → текстура выходит заметно ТЕМНЕЕ. Альфу
    конвертировать нельзя — она не цвет."""
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92,
                    1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def _img_needs_srgb_encode(image):
    """True, если ``image.pixels`` лежат в scene-LINEAR и их нужно
    перекодировать в sRGB для отображаемых байтов TXD.

    Так бывает у FLOAT-картинок, помеченных как цвет (sRGB): 16/32-битные
    PNG, EXR, запечённые результаты — Blender отдаёт их pixels уже
    линеаризованными, и запись `linear*255` делает текстуру ТЁМНОЙ. Обычные
    8-битные картинки отдают pixels уже в sRGB — их пишем как есть (иначе
    наоборот пересветлим). Non-Color/данные не трогаем."""
    if not getattr(image, 'is_float', False):
        return False
    cs = getattr(getattr(image, 'colorspace_settings', None), 'name', 'sRGB')
    return cs == 'sRGB'


def is_texture_connected_to_alpha(tex_node):
    # Alpha выход - индекс 1 у TEX_IMAGE
    if len(tex_node.outputs) < 2:
        return False
    alpha_output = tex_node.outputs[1]
    if not alpha_output.is_linked:
        return False
    # Проверяем что подключено к Principled BSDF (любой вход с alpha в имени)
    for link in alpha_output.links:
        to_node = link.to_socket.node
        if to_node.type == 'BSDF_PRINCIPLED':
            # Проверяем по индексу или имени (Alpha вход ~индекс 21, но лучше по имени)
            socket_name = link.to_socket.name.lower()
            socket_id = link.to_socket.identifier.lower() if hasattr(link.to_socket, 'identifier') else ''
            if 'alpha' in socket_name or 'alpha' in socket_id or 'альфа' in socket_name:
                return True
    return False


def check_image_has_transparent_pixels(image):
    try:
        pixels = np.array(image.pixels[:])
        if len(pixels) < 4:
            return False
        alpha = pixels[3::4]
        return np.any(alpha < 0.99)
    except (RuntimeError, ValueError, MemoryError):
        # RuntimeError: image has no loaded pixel buffer (missing file,
        # generated-but-unevaluated). MemoryError: huge texture.
        return False


def is_node_connected(node):
    """Проверить, подключена ли нода к чему-либо (любой выход)"""
    for output in node.outputs:
        if output.is_linked:
            return True
    return False


def collect_textures(selected_only=False):
    textures = {}
    transparent_textures = set()

    if selected_only:
        materials = set()
        for obj in bpy.context.selected_objects:
            if hasattr(obj, 'material_slots'):
                for slot in obj.material_slots:
                    if slot.material:
                        materials.add(slot.material)
        materials = list(materials)
    else:
        materials = bpy.data.materials

    # First pass: gather every texture used by a connected image node, and
    # remember the "main" image of each material (its first connected
    # texture). The main image's basename is what paintjob alts attach
    # to in pass 2.
    material_main_image = {}

    for mat in materials:
        if not mat.use_nodes or not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                # Пропускаем лайтмап превью ноды (не экспортировать в TXD)
                if node.name in ("LM_Texture", "Lightmap_Texture"):
                    continue
                # Игнорировать ноды которые ни к чему не подключены
                if not is_node_connected(node):
                    continue

                img = node.image
                # Имя текстуры в TXD — из НОДЫ (label), иначе из картинки.
                # Должно совпадать с тем, что пишет DFF-экспорт (_read_texture),
                # иначе игра не свяжет текстуру с моделью.
                from ..core.tex_name import clean_texture_name
                name = clean_texture_name((node.label or "").strip()
                                          or img.name)
                alpha_connected = is_texture_connected_to_alpha(node)
                has_transparent = check_image_has_transparent_pixels(img)
                if has_transparent:
                    transparent_textures.add(img.name)
                # DXT3 только если альфа подключена И есть прозрачные пиксели
                uses_alpha = alpha_connected and has_transparent
                if name in textures:
                    existing_alpha = textures[name][1]
                    textures[name] = (img, existing_alpha or uses_alpha)
                else:
                    textures[name] = (img, uses_alpha)

                # Record this material's main image (first one we see).
                if mat not in material_main_image:
                    material_main_image[mat] = name

    # Second pass: vehicle paintjob alts — pack them with derived names so
    # the game's runtime swap works: <base>_paintjob1 / <base>_paintjob2.
    # Materials without a main image are skipped (no <base> to attach to).
    for mat in materials:
        inu = getattr(mat, 'inu', None)
        if inu is None:
            continue
        alt1 = getattr(inu, 'paintjob_alt_1', None)
        alt2 = getattr(inu, 'paintjob_alt_2', None)
        if not (alt1 or alt2):
            continue
        base = material_main_image.get(mat)
        if not base:
            # Material has paintjob alts but no main texture — silently
            # skip; the validator operator surfaces this to the user.
            continue
        for alt_img, suffix in ((alt1, '_paintjob1'), (alt2, '_paintjob2')):
            if not alt_img:
                continue
            tex_name = f"{base}{suffix}"
            has_transparent = check_image_has_transparent_pixels(alt_img)
            if has_transparent:
                transparent_textures.add(alt_img.name)
            # Paintjobs swap into the body slot — use same alpha mode
            # as the base texture so DXT format matches.
            base_uses_alpha = textures.get(base, (None, False))[1]
            uses_alpha = base_uses_alpha or has_transparent
            textures[tex_name] = (alt_img, uses_alpha)

    return textures, list(transparent_textures)


def _alpha_weighted_mean(blocks, axes):
    """Average an RGBA block over ``axes``, weighting RGB by alpha.

    A plain box average treats a fully-transparent texel's RGB the same
    as an opaque one. Transparent texels usually carry black/garbage RGB
    (nothing was drawn there), so that colour leaks into the smaller mip
    and shows up as dark halos around the edges of alpha cut-outs — the
    classic "MagicTXD mipmaps look wrong" artifact.

    Weighting RGB by alpha (Σ rgb·a / Σ a) drops fully-transparent texels
    out of the COLOUR average entirely, so only actually-visible colour
    survives into the mip. Alpha itself stays a plain average (coverage
    must shrink smoothly). Where a whole block is transparent (Σ a = 0)
    we fall back to the plain RGB mean so the colour stays defined — it's
    invisible anyway.

    For a fully-opaque texture (all alpha=255) this is identical to the
    old plain average, so opaque textures are unaffected.
    """
    f = blocks.astype(np.float32)
    rgb = f[..., :3]
    a = f[..., 3:4]
    wsum = a.sum(axis=axes)                 # (.., 1)
    rgb_weighted = (rgb * a).sum(axis=axes)  # (.., 3)
    rgb_plain = rgb.mean(axis=axes)          # (.., 3)
    out_rgb = np.where(wsum > 0, rgb_weighted / np.maximum(wsum, 1.0), rgb_plain)
    out_a = a.mean(axis=axes)               # (.., 1)
    out = np.concatenate([out_rgb, out_a], axis=-1)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)  # +0.5 → round, not truncate


def downsample_image(pixels, width, height):
    new_w = max(1, width // 2)
    new_h = max(1, height // 2)
    if width == 1 and height == 1:
        return None, 0, 0
    if width > 1 and height > 1:
        reshaped = pixels[:new_h*2, :new_w*2].reshape(new_h, 2, new_w, 2, 4)
        downsampled = _alpha_weighted_mean(reshaped, axes=(1, 3))
    elif width > 1:
        reshaped = pixels[:1, :new_w*2].reshape(1, new_w, 2, 4)
        downsampled = _alpha_weighted_mean(reshaped, axes=(2,))
    elif height > 1:
        reshaped = pixels[:new_h*2, :1].reshape(new_h, 2, 1, 4)
        downsampled = _alpha_weighted_mean(reshaped, axes=(1,))
    else:
        return None, 0, 0
    return downsampled, new_w, new_h


def pad_to_4x4(pixels, width, height):
    if width >= 4 and height >= 4:
        return pixels, width, height
    pad_w = max(4, width)
    pad_h = max(4, height)
    padded = np.zeros((pad_h, pad_w, 4), dtype=np.uint8)
    padded[:height, :width] = pixels
    if width < pad_w:
        padded[:height, width:] = pixels[:, -1:, :]
    if height < pad_h:
        padded[height:, :width] = pixels[-1:, :, :]
    if width < pad_w and height < pad_h:
        padded[height:, width:] = pixels[-1, -1, :]
    return padded, pad_w, pad_h


# Alpha-test reference the GTA engine compares against (0.5 of 255).
_ALPHA_TEST_REF = 128


def dilate_alpha_edges(pixels, max_iters=32, opaque_thresh=1):
    """"Solidify alpha": overwrite the RGB of (semi-)transparent texels with
    the colour of the nearest fully-opaque texels, iteratively. Alpha is
    never touched — only hidden/edge RGB changes.

    ``opaque_thresh`` decides what counts as a trustworthy colour source
    and which texels get rewritten:

    * ``1`` (gentle) — only fully-transparent texels (alpha==0) are filled.
      Semi-transparent texels keep their own RGB. Use for alpha-BLEND
      textures (glass/smoke) where partial-alpha colour is meaningful.

    * ``~250`` (aggressive) — only fully-opaque texels seed the colour, and
      EVERY sub-opaque texel (including the anti-aliased edge) is rewritten
      with leaf colour. This is what kills the WHITE FRINGE on alpha-test
      cut-outs: artists author foliage on a white matte, so the soft edge
      texels carry white RGB that bilinear filtering smears into a halo.
      Use for binary alpha-test textures.

    ``max_iters`` caps how far the colour spreads (px). Returns a new array.
    """
    h, w, _ = pixels.shape
    rgb = pixels[..., :3].astype(np.float32)
    known = pixels[..., 3] >= opaque_thresh
    if known.all() or not known.any():
        return pixels  # nothing to seed from, or nothing to fill
    for _ in range(max_iters):
        acc = np.zeros((h, w, 3), dtype=np.float32)
        cnt = np.zeros((h, w), dtype=np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            acc += np.roll(rgb, (dy, dx), axis=(0, 1)) * \
                np.roll(known, (dy, dx), axis=(0, 1)).astype(np.float32)[..., None]
            cnt += np.roll(known, (dy, dx), axis=(0, 1)).astype(np.float32)
        fill = (~known) & (cnt > 0)
        if not fill.any():
            break
        rgb[fill] = acc[fill] / cnt[fill][..., None]
        known = known | fill
    out = pixels.copy()
    out[..., :3] = np.clip(rgb + 0.5, 0, 255).astype(np.uint8)
    return out


def _is_binary_alpha(alpha, lo=24, hi=232, mid_frac=0.05):
    """True when alpha is essentially binary (alpha-test cut-out) rather
    than a smooth gradient (alpha-blend). Coverage preservation must only
    touch the former — rescaling a glass/smoke gradient's alpha is wrong."""
    mid = np.count_nonzero((alpha > lo) & (alpha < hi))
    return mid <= mid_frac * alpha.size


def _alpha_coverage(alpha, ref=_ALPHA_TEST_REF):
    """Fraction of texels that pass the alpha test at ``ref``."""
    return float(np.count_nonzero(alpha >= ref)) / max(alpha.size, 1)


def _scale_alpha_for_coverage(pixels, target_cov, ref=_ALPHA_TEST_REF):
    """Rescale a mip's alpha so the same fraction of texels passes the
    alpha test as in the base image (Castaño/NVIDIA technique).

    Without this, alpha-test cut-outs (foliage, fences, lattice) lose
    coverage as mips shrink and thin out / vanish at distance. We binary-
    search a single alpha multiplier that restores the base coverage.
    """
    alpha = pixels[..., 3].astype(np.float32)
    if target_cov <= 0.0 or target_cov >= 1.0:
        return pixels  # nothing passing, or everything passing — no fix needed
    n = max(alpha.size, 1)
    lo, hi = 0.0, 8.0
    best_scale, best_err = 1.0, 2.0
    for _ in range(16):
        mid = 0.5 * (lo + hi)
        cov = float(np.count_nonzero(alpha * mid >= ref)) / n
        err = abs(cov - target_cov)
        if err < best_err:  # keep the multiplier whose coverage is CLOSEST,
            best_err = err  # not just the first that overshoots — fewer mips
            best_scale = mid  # come out thicker than the base.
        if cov < target_cov:
            lo = mid
        else:
            hi = mid
    out = pixels.copy()
    out[..., 3] = np.clip(alpha * best_scale + 0.5, 0, 255).astype(np.uint8)
    return out


def compress_miplevel_bc1_numpy(pixels, fast=False):
    """Vectorized BC1/DXT1 via core.dxt — drop-in for compress_miplevel_dxt1."""
    from ..core.dxt import encode_bc1
    return encode_bc1(pixels, fast=fast)


def compress_miplevel_bc2_numpy(pixels, fast=False):
    """Vectorized BC2/DXT3 via core.dxt — drop-in for compress_miplevel_dxt3.
    Matches the existing on-disk format (fourcc 'DXT3', 4-bit explicit alpha)."""
    from ..core.dxt import encode_bc2
    return encode_bc2(pixels, fast=fast)


def compress_miplevel_bc3_numpy(pixels, fast=False):
    """Vectorized BC3/DXT5 via core.dxt — interpolated alpha, fourcc 'DXT5'."""
    from ..core.dxt import encode_bc3
    return encode_bc3(pixels, fast=fast)


def prepare_texture_data(name, image, use_alpha):
    """Main thread only: fast pixel read via ``image.pixels.foreach_get``.

    Returns ``(name, flat_float32, width, height, use_alpha)`` — the
    reshape + uint8 conversion + vertical flip is deferred to worker
    threads (see ``_flat_to_uint8``) so only the bpy-touching part stays
    on the main thread, and only as long as foreach_get takes (one
    C-level memcpy, ~5ms even on a 1024² image).

    Replaces the old ``np.array(image.pixels[:])`` path, which iterated
    the pixel sequence in pure Python and could take 100–500ms per
    1024² image — bottleneck for the entire export."""
    width, height = image.size[0], image.size[1]
    flat = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(flat)
    # scene-linear → sRGB (только RGB) для float-картинок, иначе тёмные.
    # Делаем здесь, на главном потоке, пока есть доступ к свойствам image.
    if _img_needs_srgb_encode(image):
        view = flat.reshape(-1, 4)
        view[:, :3] = _linear_to_srgb(view[:, :3])
    return (name, flat, width, height, use_alpha)


def _flat_to_uint8(flat, width, height):
    """Worker thread: float32 [0,1] flat buffer → (h, w, 4) uint8, flipped vertically.
    Pure numpy, releases GIL → genuine parallel speedup across textures."""
    arr = (flat.reshape(height, width, 4) * 255).astype(np.uint8)
    return np.flipud(arr)


def _build_tex_native_from_pixels(texture_data, cmp_dxt1, cmp_dxt3):
    """Shared mip-chain + texture-native assembly.

    Encoder callbacks have signature ``cmp(pixels, mip_index) → bytes``.
    The ``mip_index`` argument lets backends route differently per mip
    (e.g., the hybrid GPU/numpy encoder uses GPU for mip 0 and numpy
    for the smaller mips where dispatch overhead dominates).
    """
    name, pixels, width, height, use_alpha = texture_data

    new_w = (width + 3) // 4 * 4
    new_h = (height + 3) // 4 * 4

    if new_w != width or new_h != height:
        padded = np.zeros((new_h, new_w, 4), dtype=np.uint8)
        padded[:height, :width] = pixels
        if width < new_w:
            padded[:height, width:] = pixels[:, -1:, :]
        if height < new_h:
            padded[height:, :] = padded[height-1:height, :]
        pixels = padded
        width, height = new_w, new_h

    # ── Alpha-quality pre-pass (only for textures that carry alpha) ──────
    #   1. dilate: bleed real colour under the transparency so DXT blocks
    #      and mip averaging never pull garbage colour into edges;
    #   2. coverage: if the alpha is a binary cut-out (auto-detected),
    #      remember the base coverage so each mip's alpha can be rescaled
    #      to keep foliage/fences from thinning out at distance.
    preserve_cov = False
    base_cov = 0.0
    if use_alpha:
        binary = _is_binary_alpha(pixels[..., 3])
        # Aggressive edge-bleed for alpha-test cut-outs (rewrites the white
        # matte on the anti-aliased edge → no fringe); gentle bleed for
        # alpha-blend so semi-transparent colour is preserved.
        pixels = dilate_alpha_edges(pixels, opaque_thresh=250 if binary else 1)
        if binary:
            preserve_cov = True
            base_cov = _alpha_coverage(pixels[..., 3])

    mip_levels = []
    current_pixels = pixels
    current_w, current_h = width, height
    mip_index = 0

    while current_w >= 1 and current_h >= 1:
        compress_pixels, _, _ = pad_to_4x4(current_pixels, current_w, current_h)
        if use_alpha:
            compressed = cmp_dxt3(compress_pixels, mip_index)
        else:
            compressed = cmp_dxt1(compress_pixels, mip_index)
        mip_levels.append(compressed)
        current_pixels, current_w, current_h = downsample_image(current_pixels, current_w, current_h)
        if current_pixels is None:
            break
        # Restore alpha-test coverage on the freshly downsampled mip before
        # it is compressed on the next iteration. (mip 0 above is the
        # reference, so it is never rescaled.)
        if preserve_cov:
            current_pixels = _scale_alpha_for_coverage(current_pixels, base_cov)
        mip_index += 1

    if use_alpha:
        # DXT3 must be flagged 4444/16-bit, NOT 8888/32-bit. 8888+depth32
        # is the signature of an UNCOMPRESSED A8R8G8B8 raster, so pairing
        # it with a DXT3 fourcc gives a self-contradicting header: the
        # raster format says "uncompressed 32-bit", d3dFormat says "DXT3".
        # RW chokes on it and the texture silently never arrives in game
        # (the model draws that material's bare colour — reads as white).
        # Verified against 1257 stock SA TXDs: all 356 DXT3 textures are
        # 0x0300 / depth 16, and 0x0500 / depth 32 is used only by the
        # uncompressed A8R8G8B8 rasters (fourcc D3DFMT_A8R8G8B8, flag 0x01).
        raster_format = RASTER_4444 | RASTER_MIPMAP
        depth = 16
        fourcc = b'DXT3'
    else:
        raster_format = RASTER_565 | RASTER_MIPMAP
        depth = 16
        fourcc = b'DXT1'

    tex_name = name[:31].encode('ascii', errors='replace').ljust(32, b'\x00')
    mip_count = len(mip_levels)

    platform = _active_platform
    struct_data = bytearray()
    struct_data.extend(struct.pack('<II', platform,
                                   make_filter_flags(mip_count)))
    struct_data.extend(tex_name)
    struct_data.extend(b'\x00' * 32)
    struct_data.extend(struct.pack('<I', raster_format))
    if platform == PLATFORM_D3D8:
        # D3D8 native (III/VC): the word after rasterFormat is ``hasAlpha``
        # (no D3DFORMAT fourcc), and the trailing byte is the DXT number
        # (0 = uncompressed, 1 = DXT1, 3 = DXT3) instead of a flags byte.
        # Both engines support DXTn via the D3D8 driver (III just never
        # shipped compressed textures).
        struct_data.extend(struct.pack('<I', 1 if use_alpha else 0))
    else:
        struct_data.extend(fourcc)
    struct_data.extend(struct.pack('<HH', width, height))
    struct_data.extend(struct.pack('<B', depth))
    struct_data.extend(struct.pack('<B', mip_count))
    struct_data.extend(struct.pack('<B', 4))  # raster type
    if platform == PLATFORM_D3D8:
        struct_data.extend(struct.pack('<B', 3 if use_alpha else 1))
    else:
        # D3D format flag: 0x08 for DXT1, 0x09 for DXT3 (with alpha)
        struct_data.extend(struct.pack('<B', 0x09 if use_alpha else 0x08))

    for mip_data in mip_levels:
        struct_data.extend(struct.pack('<I', len(mip_data)))
        struct_data.extend(mip_data)

    tex_native = bytearray()
    write_rw_section_header(tex_native, RW_STRUCT, len(struct_data))
    tex_native.extend(struct_data)
    write_rw_section_header(tex_native, RW_EXTENSION, 0)
    return bytes(tex_native)


def process_texture_parallel(texture_data, backend='numpy'):
    """Worker thread: float-flat → uint8 → mip chain → texture-native bytes.

    ``backend``:
        'numpy'      — range-fit on mip 0 only (best quality where it
                       matters), bbox-int on mip 1+ (4×4..8×8..32×32 etc.,
                       where the algorithmic difference is invisible).
        'numpy_fast' — bbox-int everywhere (~2× faster than full range-fit)
    """
    name, flat, width, height, use_alpha = texture_data
    fast_all = (backend == 'numpy_fast')

    _t0 = time.perf_counter()
    pixels = _flat_to_uint8(flat, width, height)
    _numpy_timing['flat_to_uint8'] += time.perf_counter() - _t0

    encode_acc = {'enc': 0.0}

    # Smart mip routing: on default 'numpy', upgrade only mip 0 to range-fit
    # (where the highest detail lives) and use bbox-int for everything below.
    # Saves ~17% of encode-aggregate at no perceptible quality cost.
    def _use_fast(mip_index):
        return fast_all or mip_index > 0

    def _bc1(p, mip_index):
        _et = time.perf_counter()
        result = compress_miplevel_bc1_numpy(p, fast=_use_fast(mip_index))
        encode_acc['enc'] += time.perf_counter() - _et
        return result

    def _bc2(p, mip_index):
        _et = time.perf_counter()
        result = compress_miplevel_bc2_numpy(p, fast=_use_fast(mip_index))
        encode_acc['enc'] += time.perf_counter() - _et
        return result

    _t0 = time.perf_counter()
    result = _build_tex_native_from_pixels(
        (name, pixels, width, height, use_alpha), _bc1, _bc2)
    total = time.perf_counter() - _t0
    _numpy_timing['encode'] += encode_acc['enc']
    _numpy_timing['assemble'] += total - encode_acc['enc']
    _numpy_timing['count'] += 1
    return result


# Granular numpy export timing — accumulated across all worker threads.
# Helps decompose where the 500ms-on-54-textures actually goes:
#   prepare        — main-thread foreach_get pixel reads
#   flat_to_uint8  — reshape + *255 + flipud (worker)
#   encode         — encode_bc1/bc2 (worker, the real BC1 cost)
#   assemble       — mip downsampling + struct packing (worker)
_numpy_timing = {'prepare': 0.0, 'flat_to_uint8': 0.0, 'encode': 0.0,
                 'assemble': 0.0, 'count': 0}


def reset_numpy_timing():
    global _numpy_timing
    _numpy_timing = {'prepare': 0.0, 'flat_to_uint8': 0.0, 'encode': 0.0,
                     'assemble': 0.0, 'count': 0}


def print_numpy_timing():
    n = _numpy_timing['count']
    if n == 0:
        return
    total = sum(v for k, v in _numpy_timing.items() if k != 'count')
    print(f"[numpy timing] {n} textures, total={total:.3f}s")
    for phase in ('prepare', 'flat_to_uint8', 'encode', 'assemble'):
        t = _numpy_timing[phase]
        print(f"  {phase:14s} {t*1000:8.1f}ms ({100*t/total:5.1f}%)  avg/tex {t*1000/n:6.2f}ms")


def _pad_mip0(pixels, width, height):
    """Right/bottom-edge replicate to 4×4 alignment for mip 0. Mirrors
    the same padding that ``_build_tex_native_from_pixels`` applies
    internally so pre-encoded GPU mip 0 bytes are byte-compatible
    with what the assembly pass expects."""
    new_w = (width + 3) // 4 * 4
    new_h = (height + 3) // 4 * 4
    if new_w == width and new_h == height:
        return pixels, width, height
    padded = np.zeros((new_h, new_w, 4), dtype=np.uint8)
    padded[:height, :width] = pixels
    if width < new_w:
        padded[:height, width:] = pixels[:, -1:, :]
    if height < new_h:
        padded[height:, :] = padded[height-1:height, :]
    return padded, new_w, new_h


def compress_textures_gpu(dxt1_data, dxt3_data, wm, total, dxt1_count):
    """Hybrid GPU encoder, three-phase:

      Phase A (main thread, serial) — GPU mip 0 dispatch + read():
        GPU resources can only be touched from main thread. We dispatch
        the compute shader and call out_tex.read() (which blocks for
        GPU work) but DON'T iterate the returned Buffer yet. Returns a
        ``handle`` per texture: (raw_buffer, blocks_x, blocks_y).

      Phase B (worker threads, parallel) — Buffer→bytes finalize:
        The slow Python iteration over the Buffer (read_iter, was 57%
        of GPU phase time) is moved off main thread. While the main
        thread queues more dispatches, workers process previous
        results. Pure Python+numpy, no GPU calls, safe in workers.

      Phase C (worker threads, parallel) — numpy mip 1+ + assembly:
        Same workers also do the smaller mip levels and assemble the
        final texture-native byte blobs. This was the previous Phase B.

    Phases B and C are merged into a single worker task per texture."""
    from ..core.dxt_gpu import (
        encode_bc1_gpu_dispatch, encode_bc1_gpu_finalize,
        encode_bc2_gpu_dispatch, encode_bc2_gpu_finalize,
        reset_timing, print_timing,
    )

    reset_timing()

    # ── Phase A: dispatch + GPU sync for every texture, main thread ──
    # data is now (name, flat_float, w, h, use_alpha) per the foreach_get
    # change; we have to materialize uint8 pixels here (small numpy cost
    # per texture, dominated by GPU work that follows).
    handle_map = {}  # id(data) -> ('bc1' | 'bc2', deferred handle)
    for i, data in enumerate(dxt1_data):
        wm.progress_update(total + i)
        try:
            name, flat, w, h, _ = data
            pixels = _flat_to_uint8(flat, w, h)
            padded, _, _ = _pad_mip0(pixels, w, h)
            handle_map[id(data)] = ('bc1', encode_bc1_gpu_dispatch(padded))
        except Exception as e:
            print(f"TXD GPU mip0 dispatch ERROR ({data[0]}): {e}")
            handle_map[id(data)] = ('bc1', None)
    for i, data in enumerate(dxt3_data):
        wm.progress_update(total + dxt1_count + i)
        try:
            name, flat, w, h, _ = data
            pixels = _flat_to_uint8(flat, w, h)
            padded, _, _ = _pad_mip0(pixels, w, h)
            handle_map[id(data)] = ('bc2', encode_bc2_gpu_dispatch(padded))
        except Exception as e:
            print(f"TXD GPU mip0 dispatch ERROR ({data[0]}): {e}")
            handle_map[id(data)] = ('bc2', None)

    print_timing()  # GPU dispatch+read phase only

    # ── Phase B+C: finalize + numpy mips 1+ + assembly (workers) ──
    def _build_one(data):
        # Reshape flat float buffer to uint8 image inside the worker.
        name, flat, w, h, use_alpha = data
        pixels = _flat_to_uint8(flat, w, h)
        tex_data = (name, pixels, w, h, use_alpha)

        kind, handle = handle_map[id(data)]
        if handle is not None:
            mip0 = (encode_bc1_gpu_finalize(handle) if kind == 'bc1'
                    else encode_bc2_gpu_finalize(handle))
        else:
            mip0 = None

        def _bc1(p, mip_index):
            if mip_index == 0 and mip0 is not None:
                return mip0
            return compress_miplevel_bc1_numpy(p)

        def _bc2(p, mip_index):
            if mip_index == 0 and mip0 is not None:
                return mip0
            return compress_miplevel_bc2_numpy(p)

        return _build_tex_native_from_pixels(tex_data, _bc1, _bc2)

    results = []
    num_workers = min(8, os.cpu_count() or 4)
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(_build_one, d) for d in dxt1_data]
        futures += [executor.submit(_build_one, d) for d in dxt3_data]
        for fut in futures:
            try:
                results.append(fut.result())
            except Exception as e:
                print(f"TXD hybrid Phase B+C ERROR: {e}")
    return results


def export_txd(filepath, context, selected_only=False, backend=None, **_legacy):
    """Export textures to a .txd archive.

    ``backend``: 'numpy' (vectorized CPU, default) or 'gpu' (bpy.gpu
    compute shader, WIP). Anything else routes to numpy.

    ``**_legacy`` swallows obsolete kwargs like ``use_gpu`` from older
    callers we haven't migrated yet — keeps things from breaking.
    """
    textures, transparent_list = collect_textures(selected_only)
    if not textures:
        msg = "No textures found on selected objects" if selected_only else "No textures found in scene"
        return {'CANCELLED'}, msg, []

    scene = context.scene

    # Resolve TXD lib-ID from scene's gtatools_game and stash it on the
    # module-level slot read by write_rw_section_header. Restored in
    # `finally` below so nested / concurrent exports don't leak state.
    global _active_lib_id, _active_platform
    _saved_lib_id = _active_lib_id
    _saved_platform = _active_platform
    _active_lib_id = _resolve_lib_id_for_scene(scene)
    _active_platform = _resolve_platform_for_scene(scene)

    if backend is None:
        backend = getattr(scene.inu_settings, 'gtatools_dxt_backend', 'numpy')

    if backend == 'gpu':
        try:
            from ..core.dxt_gpu import gpu_compute_available
            if not gpu_compute_available():
                print("[TXD] GPU compute недоступен — fallback на numpy")
                backend = 'numpy'
        except Exception as e:
            print(f"[TXD] GPU compute import failed ({e}) — fallback на numpy")
            backend = 'numpy'

    mode_name = {
        'numpy':      "Numpy (range-fit mip0 + bbox mip1+)",
        'numpy_fast': "Numpy fast (bbox-int)",
        'gpu':        "GPU compute",
    }.get(backend, "Numpy")

    wm = context.window_manager
    total = len(textures)
    wm.progress_begin(0, total * 2)

    # Two buckets per alpha mode: ``cached`` skips the pipeline entirely;
    # ``data + key`` lists carry textures that need encoding (key is the
    # cache slot we'll fill after encoding succeeds).
    cached_dxt1 = []
    cached_dxt3 = []
    dxt1_data = []
    dxt3_data = []
    cache_keys_dxt1 = []   # parallel to dxt1_data
    cache_keys_dxt3 = []   # parallel to dxt3_data
    reset_numpy_timing()
    skipped_textures = []
    cache_hits = 0
    for i, (name, (image, uses_alpha)) in enumerate(textures.items()):
        wm.progress_update(i)
        w, h = image.size[0], image.size[1]
        if w % 4 != 0 or h % 4 != 0:
            print(f"[TXD] ПРОПУСК {name}: размер {w}x{h} не кратен 4")
            skipped_textures.append(f"{name} ({w}x{h})")
            continue

        key = _cache_key(name, image, uses_alpha, backend)
        cached = _cache_get(key)
        if cached is not None:
            if uses_alpha:
                cached_dxt3.append(cached)
            else:
                cached_dxt1.append(cached)
            cache_hits += 1
            continue

        print(f"[TXD] {name}: {w}x{h}, uses_alpha={uses_alpha}")
        try:
            _t0 = time.perf_counter()
            prepared = prepare_texture_data(name, image, uses_alpha)
            _numpy_timing['prepare'] += time.perf_counter() - _t0
            if uses_alpha:
                dxt3_data.append(prepared)
                cache_keys_dxt3.append(key)
            else:
                dxt1_data.append(prepared)
                cache_keys_dxt1.append(key)
        except Exception as e:
            print(f"TXD PREPARE ERROR: {name}: {e}")

    dxt1_to_encode = len(dxt1_data)
    dxt3_to_encode = len(dxt3_data)
    if cache_hits:
        print(f"[TXD] cache: {cache_hits} hit, "
              f"{dxt1_to_encode + dxt3_to_encode} miss")

    # Phase 2: Compression — only for cache misses.
    encoded_dxt1 = []
    encoded_dxt3 = []
    t_compress_start = time.perf_counter()

    if backend == 'gpu':
        # bpy.gpu compute shader — main thread, serial. GPU path returns
        # a flat list with DXT1 first, DXT3 second; split it back.
        gpu_results = compress_textures_gpu(
            dxt1_data, dxt3_data, wm, total, dxt1_to_encode)
        encoded_dxt1 = gpu_results[:dxt1_to_encode]
        encoded_dxt3 = gpu_results[dxt1_to_encode:]
    else:
        # numpy / numpy_fast — parallel via ThreadPoolExecutor.
        num_workers = min(8, os.cpu_count() or 4)
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(process_texture_parallel, data, backend)
                       for data in dxt1_data]
            for i, future in enumerate(futures):
                wm.progress_update(total + i)
                try:
                    encoded_dxt1.append(future.result())
                except Exception as e:
                    print(f"TXD numpy ERROR: {e}")
                    encoded_dxt1.append(None)
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(process_texture_parallel, data, backend)
                       for data in dxt3_data]
            for i, future in enumerate(futures):
                wm.progress_update(total + dxt1_to_encode + i)
                try:
                    encoded_dxt3.append(future.result())
                except Exception as e:
                    print(f"TXD numpy ERROR: {e}")
                    encoded_dxt3.append(None)
        if dxt1_to_encode + dxt3_to_encode > 0:
            print_numpy_timing()

    # Persist freshly-encoded results for the next export.
    for tex_native, key in zip(encoded_dxt1, cache_keys_dxt1):
        if tex_native is not None:
            _cache_set(key, tex_native)
    for tex_native, key in zip(encoded_dxt3, cache_keys_dxt3):
        if tex_native is not None:
            _cache_set(key, tex_native)

    # Assemble final list: DXT1 (cached + encoded) then DXT3 (cached +
    # encoded). DXT order matters for engine readers; within a bucket
    # the relative order of cached vs freshly-encoded textures does not.
    tex_natives = []
    tex_natives.extend(cached_dxt1)
    tex_natives.extend(t for t in encoded_dxt1 if t is not None)
    tex_natives.extend(cached_dxt3)
    tex_natives.extend(t for t in encoded_dxt3 if t is not None)

    elapsed = time.perf_counter() - t_compress_start
    print(f"[TXD] backend={mode_name}: {len(tex_natives)} textures "
          f"encoded in {elapsed:.3f}s")

    wm.progress_end()

    if not tex_natives:
        _active_lib_id = _saved_lib_id  # restore before bailing
        _active_platform = _saved_platform
        return {'CANCELLED'}, "No textures could be processed", []

    tex_natives_data = bytearray()
    for tex_native in tex_natives:
        write_rw_section_header(tex_natives_data, RW_TEXTURENATIVE, len(tex_native))
        tex_natives_data.extend(tex_native)

    struct_section = bytearray()
    dict_struct = struct.pack('<HH', len(tex_natives), 0)
    write_rw_section_header(struct_section, RW_STRUCT, len(dict_struct))
    struct_section.extend(dict_struct)

    extension_data = bytearray()
    write_rw_section_header(extension_data, RW_EXTENSION, 0)

    with open(filepath, 'wb') as f:
        content_size = len(struct_section) + len(tex_natives_data) + len(extension_data)
        # Top-level Texture Dictionary header uses the same lib_id we
        # stashed earlier — same value as every nested chunk.
        f.write(struct.pack('<III', RW_TEXDICTIONARY, content_size, _active_lib_id))
        f.write(struct_section)
        f.write(tex_natives_data)
        f.write(extension_data)

    # Restore the prior lib_id so nested / concurrent exports don't see
    # this run's value bleed into theirs. Done after the file is closed
    # so any tail logic in write_rw_section_header has already finished.
    _active_lib_id = _saved_lib_id
    _active_platform = _saved_platform

    msg = f"Exported {len(tex_natives)} textures ({mode_name})"
    if skipped_textures:
        msg += f"\nПРОПУЩЕНО (размер не кратен 4): {', '.join(skipped_textures)}"
    return {'FINISHED'}, msg, transparent_list


def _assemble_txd_file(filepath, lib_id, sections):
    """Write a TXD from pre-built ``(name, full_0x15_section_bytes)`` tuples.

    Each ``section`` already includes its 12-byte Texture-Native header, so
    we just concatenate them, prepend the dictionary Struct (texture count)
    and append the empty Extension — the same container layout
    :func:`export_txd` emits, but from verbatim section bytes instead of
    freshly-encoded ones. Used by :func:`update_txd` to merge."""
    global _active_lib_id
    saved = _active_lib_id
    _active_lib_id = lib_id          # write_rw_section_header reads this
    try:
        tex_data = bytearray()
        for _name, sect in sections:
            tex_data.extend(sect)

        struct_section = bytearray()
        dict_struct = struct.pack('<HH', len(sections), 0)
        write_rw_section_header(struct_section, RW_STRUCT, len(dict_struct))
        struct_section.extend(dict_struct)

        extension_data = bytearray()
        write_rw_section_header(extension_data, RW_EXTENSION, 0)

        with open(filepath, 'wb') as f:
            content_size = (len(struct_section) + len(tex_data)
                            + len(extension_data))
            f.write(struct.pack('<III', RW_TEXDICTIONARY,
                                content_size, lib_id))
            f.write(struct_section)
            f.write(tex_data)
            f.write(extension_data)
    finally:
        _active_lib_id = saved


def update_txd(filepath, context, selected_only=True, backend=None):
    """Merge the scene's textures INTO an existing TXD.

    Same-named textures are REPLACED with the freshly-encoded ones, brand-new
    names are APPENDED, and every OTHER texture already in the file is kept
    byte-for-byte. This is the "add/update textures without nuking the other
    models' textures" path. If ``filepath`` doesn't exist yet, falls back to
    a normal full export.

    Returns ``({'FINISHED'|'CANCELLED'}, message, transparent_list)``."""
    import os
    from .. import T
    from ..core.txd import split_txd_sections

    if not os.path.isfile(filepath):
        # Nothing to merge into — behave like a plain export.
        return export_txd(filepath, context, selected_only, backend=backend)

    # 1. Encode the scene's textures into a TEMP TXD (reuse the full
    #    encoder so DXT/alpha handling is identical), then read it back.
    tmp = filepath + ".inu_tmp"
    try:
        result, message, transparent = export_txd(
            tmp, context, selected_only, backend=backend)
        if result != {'FINISHED'}:
            return result, message, transparent
        with open(tmp, 'rb') as f:
            new_bytes = f.read()
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

    # 2. Split existing + new into named, verbatim Texture-Native sections.
    with open(filepath, 'rb') as f:
        base_bytes = f.read()
    base_lib, base_sections = split_txd_sections(base_bytes)
    _new_lib, new_sections = split_txd_sections(new_bytes)
    if base_lib is None:
        return {'CANCELLED'}, T("Не удалось прочитать существующий TXD"), []
    if not new_sections:
        return {'CANCELLED'}, T("Нет текстур для добавления"), []

    # 3. Merge by name (case-insensitive — TXD names are case-folded by
    #    the engine). Existing order preserved; matches replaced in place;
    #    new names appended in scene order.
    new_by_name = {}
    for name, sect in new_sections:
        new_by_name[name.lower()] = (name, sect)

    merged, used = [], set()
    n_replaced = 0
    for name, sect in base_sections:
        key = name.lower()
        if key in new_by_name:
            merged.append(new_by_name[key])
            used.add(key)
            n_replaced += 1
        else:
            merged.append((name, sect))

    n_added = 0
    for name, sect in new_sections:
        key = name.lower()
        if key not in used:
            merged.append((name, sect))
            used.add(key)
            n_added += 1

    # 4. Re-emit, keeping the EXISTING file's RW library version.
    _assemble_txd_file(filepath, base_lib, merged)

    msg = (f"{T('TXD обновлён')}: {n_replaced} {T('обновлено')}, "
           f"{n_added} {T('добавлено')}, {len(merged)} {T('всего')}")
    return {'FINISHED'}, msg, transparent
