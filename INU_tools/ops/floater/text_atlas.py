# INU_tools.ops.floater.text_atlas
#
# blf-baked glyph atlas + GLSL text shader for the floater UI. Mirrors
# Blender's own native text rendering pixel-for-pixel by going through
# blf (the same FreeType pipeline native widgets use) to rasterise each
# glyph into a GPUOffScreen, then sampling that texture from a custom
# shader with `texelFetch` to avoid bilinear softening.
#
# Falls back to direct blf.draw() if either shader compilation or atlas
# baking fails at runtime — that path matches the look less precisely
# but keeps text visible on platforms with limited GPU support.
#
# Public surface used by `widgets.py` / `base.py`:
#   * `_text(x, y, s, color=..., size=None)`        — draw a string
#   * `_text_dims(s, size=None)` -> (w, cap_h)      — measure a string
#   * `_text_px_size(size=None)` -> int             — px size for size
#   * `_refresh_ui_text_style()`                    — call once per draw
#   * `_free_font_atlases()`                        — call from unregister

import math
import bpy
import blf
import gpu
import mathutils
from gpu_extras.batch import batch_for_shader

from . import theme as TH


# ── Text rendering tuned to match Blender's native UI ────────────────
#
# Blender's UI text in panels comes from `ui_styles[0].widget` (size,
# shadow, shadow_offset, shadow_alpha). It's also scaled by the global
# `system.ui_scale` so 4K monitors get readable text. blf font_id=0 is
# the same font Blender uses for the UI (Inter from 4.1+), but we have
# to apply size + shadow ourselves to match the look pixel-for-pixel.

# Cached per draw to avoid hitting preferences for every text call.
_UI_FONT_SIZE = 11
_UI_FONT_SCALE = 1.0
_UI_SHADOW_KIND = 0          # 0 / 3 / 5 — width of shadow blur kernel
_UI_SHADOW_OFFSET = (0, -1)  # pixel offset for the drop shadow
_UI_SHADOW_COLOR = (0.0, 0.0, 0.0, 0.5)


def _refresh_ui_text_style():
    """Read native widget text size + UI scale + shadow params from
    prefs. Called once per draw cycle so the floater follows live
    theme / scale changes."""
    global _UI_FONT_SIZE, _UI_FONT_SCALE
    global _UI_SHADOW_KIND, _UI_SHADOW_OFFSET, _UI_SHADOW_COLOR
    try:
        widget = bpy.context.preferences.ui_styles[0].widget
        _UI_FONT_SIZE = max(8, int(getattr(widget, 'points', 11)))
        _UI_SHADOW_KIND = int(getattr(widget, 'shadow', 0))
        ox = int(getattr(widget, 'shadow_offset_x', 0))
        oy = int(getattr(widget, 'shadow_offset_y', -1))
        _UI_SHADOW_OFFSET = (ox, oy)
        sa = float(getattr(widget, 'shadow_alpha', 0.5))
        sv = float(getattr(widget, 'shadow_value', 0.0))
        _UI_SHADOW_COLOR = (sv, sv, sv, sa)
    except Exception:
        pass
    # Use pixel_size (combined DPI × ui_scale that Blender uses internally
    # for UI rendering) rather than ui_scale alone — matches the actual
    # number of pixels Blender lays down for native panel text.
    try:
        _UI_FONT_SCALE = float(bpy.context.preferences.system.pixel_size)
    except Exception:
        try:
            _UI_FONT_SCALE = float(bpy.context.preferences.system.ui_scale)
        except Exception:
            _UI_FONT_SCALE = 1.0


# ── Runtime font atlas pipeline ──────────────────────────────────────
#
# Bake glyph atlas via Blender's blf at first request. Atlas lives in
# GPU memory only; nothing is read from disk.
#
# Why blf vs PIL: blf goes through Blender's own FreeType pipeline with
# the same hinting / stem darkening / advance metrics that Blender uses
# for every other piece of UI text. Glyphs come out pixel-identical to
# what the rest of the editor draws. PIL renders without hinting and
# produces visibly narrower, softer letters at small sizes.
#
# One atlas per requested px_size (target_pt × pixel_size). The text
# shader uses texelFetch, so as long as we bake at the exact size the
# caller asked for there is no resampling and no blur.

_FONT_ATLASES = {}  # px_size -> dict | False (failed); see _bake_font_atlas

_GLYPH_SET = (
    # ASCII printable
    "".join(chr(c) for c in range(0x20, 0x7F))
    # Cyrillic А..я
    + "".join(chr(c) for c in range(0x0410, 0x0450))
    # Ё/ё live outside the contiguous block
    + "Ёё"
    # Arrows + checkmark + radio + minus for collapse/close/checkbox/
    # menu glyphs and toggle buttons (eye visibility, etc.)
    + "▼▶►◄▲▽▷◁△×✓↓↑→←○●−✎"
    # Common typography
    + "—–…«»‹›„"
)


def _bake_font_atlas(px_size):
    """Render every glyph through blf into a GPUOffScreen; return
    {'metrics', 'texture'} or None on failure.

    The offscreen is copied to a standalone texture and freed in this
    draw context. Cell layout: each glyph gets a (advance_w × row_h)
    cell that includes both the ascender and the descender space, so
    the renderer can paste the whole cell at the baseline without
    per-glyph bearing math."""
    font_id = 0
    blf.size(font_id, px_size)
    blf.disable(font_id, blf.SHADOW)
    blf.disable(font_id, blf.CLIPPING)
    blf.disable(font_id, blf.WORD_WRAP)
    blf.disable(font_id, blf.MONOCHROME)
    blf.disable(font_id, blf.ROTATION)
    blf.aspect(font_id, 1.0)

    # blf has no public getmetrics — probe via reference chars. 'M' =
    # cap (no descender), 'Mp' = cap + descender, 'Ё' has an above-cap
    # diacritic that the cell needs to fit.
    _, cap_h = blf.dimensions(font_id, "M")
    _, ext_h = blf.dimensions(font_id, "Ёй")     # diacritic-topped Cyrillic
    _, full_h = blf.dimensions(font_id, "Mp")
    cap_h_i = int(math.ceil(cap_h))
    ascent = max(cap_h_i, int(math.ceil(ext_h))) + 1
    descent = max(1, int(math.ceil(full_h - cap_h))) + 1
    row_h = ascent + descent
    # NOTE: row_h must match the screen quad height in _build_glyph_quads
    # (st - sb = ascent + descent). If they differ even by 1 px, texelFetch
    # samples atlas pixels at slightly wrong cell coords and text appears
    # vertically squashed/stretched.

    # Row-pack glyphs left to right
    max_w = 512
    pad = 1
    placements = {}
    cur_x = pad
    cur_y = pad
    for ch in _GLYPH_SET:
        cw, _ = blf.dimensions(font_id, ch)
        cw_i = max(1, int(math.ceil(cw)))
        if cur_x + cw_i + pad > max_w:
            cur_y += row_h + pad
            cur_x = pad
        placements[ch] = {
            'x': cur_x,
            'y': cur_y,         # distance from atlas top (PIL-style)
            'w': cw_i,
            'advance': float(cw),
        }
        cur_x += cw_i + pad
    atlas_w = max_w
    atlas_h = ((cur_y + row_h + pad + 7) // 8) * 8

    try:
        offscreen = gpu.types.GPUOffScreen(atlas_w, atlas_h)
    except Exception as e:
        print(f"[INU Floater] atlas offscreen create failed @ {px_size}px: {e}")
        return None

    try:
        with offscreen.bind():
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=(0.0, 0.0, 0.0, 0.0))
            with gpu.matrix.push_pop_projection(), gpu.matrix.push_pop():
                # Ortho 2D: pixel coords (0,0)..(atlas_w, atlas_h) → NDC
                proj = mathutils.Matrix.Identity(4)
                proj[0][0] = 2.0 / atlas_w
                proj[1][1] = 2.0 / atlas_h
                proj[0][3] = -1.0
                proj[1][3] = -1.0
                gpu.matrix.load_projection_matrix(proj)
                gpu.matrix.load_matrix(mathutils.Matrix.Identity(4))

                blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
                for ch, p in placements.items():
                    # Offscreen Y is bottom-up. Convert the stored
                    # top-down cell_y to a baseline position from the
                    # bottom edge of the framebuffer.
                    cell_top_gl = atlas_h - p['y']
                    baseline_gl = cell_top_gl - ascent
                    blf.position(font_id, p['x'], baseline_gl, 0)
                    blf.draw(font_id, ch)
            # Copy the atlas out while the GPU context is valid. Keeping a
            # GPUOffScreen until unregister can access a destroyed context
            # during Blender shutdown (reported traceback on 4.5 LTS).
            pixels = fb.read_color(0, 0, atlas_w, atlas_h, 4, 0, 'FLOAT')
            texture = gpu.types.GPUTexture((atlas_w, atlas_h),
                                          format='RGBA16F', data=pixels)
    except Exception as e:
        print(f"[INU Floater] atlas bake failed @ {px_size}px: {e}")
        try:
            offscreen.free()
        except Exception:
            pass
        return None
    offscreen.free()

    metrics = {
        'px_size': px_size,
        'atlas_w': atlas_w,
        'atlas_h': atlas_h,
        'ascent': ascent,
        'descent': descent,
        'cap_h': cap_h_i,       # plain capital height (no diacritic) — for centering
        'row_h': row_h,
        'glyphs': placements,
    }
    print(f"[INU Floater] baked atlas @ {px_size}px: "
          f"{atlas_w}x{atlas_h}, {len(placements)} glyphs, "
          f"ascent={ascent} descent={descent}")
    return {
        'metrics': metrics,
        'texture': texture,
    }


def _get_atlas(px_size):
    """Return cached atlas for px_size, baking on first request.
    Returns None if baking failed (cached as False to avoid retries)."""
    a = _FONT_ATLASES.get(px_size)
    if a is False:
        return None
    if a is not None:
        return a
    a = _bake_font_atlas(px_size)
    _FONT_ATLASES[px_size] = a if a is not None else False
    # New atlas may flip _text_dims from blf-fallback to atlas-based for
    # this px_size — drop any stale blf entries so callers get fresh
    # dims on next lookup.
    if a is not None:
        try:
            _TEXT_DIMS_CACHE.clear()
        except NameError:
            pass
    return a


def _text_px_size(size=None):
    """Resolve the physical pixel size for a text call (pt × DPI scale)."""
    pt = _UI_FONT_SIZE if size is None else size
    return max(6, int(round(pt * _UI_FONT_SCALE)))


def _free_font_atlases():
    """Release all baked atlases — call from unregister()."""
    _FONT_ATLASES.clear()
    # Cached glyph batches reference the (now freed) atlas UVs — drop them
    # too so a re-register rebakes cleanly instead of drawing stale glyphs.
    _clear_glyph_batch_cache()


# ── Text shader (atlas sampler) ──────────────────────────────────────

_TEXT_VERT_SRC = """
void main() {
    v_uv = uv;
    gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
}
"""

_TEXT_FRAG_SRC = """
vec3 srgb_to_linear(vec3 c) {
    return pow(max(c, vec3(0.0)), vec3(2.2));
}

void main() {
    // Solid glyph interior — keep crisp & fully opaque (white text).
    // AA fringe — use the atlas's own edge alpha, just slightly fade it
    // so the transition to bg is softer. No neighbour blur (that was
    // expanding glyphs outward and leaving a dirty halo on the strokes).
    ivec2 ts = textureSize(atlas, 0);
    ivec2 px = ivec2(v_uv * vec2(ts));
    px = clamp(px, ivec2(0), ts - ivec2(1));
    float a = texelFetch(atlas, px, 0).a;
    if (a <= 0.001) discard;
    // Smoothstep keeps body alphas (a > ~0.5) near their natural value
    // — so even thin AA strokes still read as bright white — while the
    // outermost fringe (a < 0.3) gets faded harder for softer edges.
    float fade = mix(0.40, 1.0, smoothstep(0.0, 0.55, a));
    float final_a = a * fade;
    fragColor = vec4(srgb_to_linear(fg_color.rgb), fg_color.a * final_a);
}
"""

_text_shader = None


def _get_text_shader():
    global _text_shader
    if _text_shader is None:
        try:
            info = gpu.types.GPUShaderCreateInfo()
            info.push_constant('MAT4', 'ModelViewProjectionMatrix')
            info.push_constant('VEC4', 'fg_color')
            info.vertex_in(0, 'VEC2', 'pos')
            info.vertex_in(1, 'VEC2', 'uv')
            iface = gpu.types.GPUStageInterfaceInfo("inu_text_atlas_iface")
            iface.smooth('VEC2', 'v_uv')
            info.vertex_out(iface)
            info.sampler(0, 'FLOAT_2D', 'atlas')
            info.fragment_out(0, 'VEC4', 'fragColor')
            info.vertex_source(_TEXT_VERT_SRC)
            info.fragment_source(_TEXT_FRAG_SRC)
            _text_shader = gpu.shader.create_from_info(info)
            print("[INU Floater] text shader compile: OK")
        except Exception as e:
            print(f"[INU Floater] text shader compile failed: {e}")
            _text_shader = False
    return _text_shader if _text_shader else None


def _build_glyph_quads(text, x, y, atlas):
    """Build (verts, uvs) for `text` rendered at baseline (x, y) using
    `atlas` (one entry from _FONT_ATLASES). Each glyph quad is the full
    atlas cell — the cleared (alpha=0) margins above/below the glyph
    just don't paint anything, so we avoid per-glyph bearing math.
    """
    m = atlas['metrics']
    aw = float(m['atlas_w'])
    ah = float(m['atlas_h'])
    row_h = m['row_h']
    ascent = m['ascent']
    descent = m['descent']
    glyphs = m['glyphs']

    verts = []
    uvs = []
    pen_x = int(x)
    pen_y = int(y)  # baseline, screen Y-up

    for ch in text:
        g = glyphs.get(ch)
        if g is None:
            g = glyphs.get('?')
            if g is None:
                pen_x += 6
                continue

        gw = g['w']

        # Screen rect — full cell, baseline at pen_y. Top is ascent
        # above baseline, bottom is descent below.
        sl = pen_x
        sr = pen_x + gw
        sb = pen_y - descent
        st = pen_y + ascent

        # UV rect — atlas is GL bottom-up so v=1 is the top of the
        # texture. Cell_y was stored top-down (distance from atlas
        # top); convert to bottom-up pixel coords then normalise.
        cell_x = g['x']
        cell_top_gl_pix = ah - g['y']
        cell_bot_gl_pix = cell_top_gl_pix - row_h
        u0 = cell_x / aw
        u1 = (cell_x + gw) / aw
        v_bot = cell_bot_gl_pix / ah
        v_top = cell_top_gl_pix / ah

        verts.extend([
            (sl, sb), (sr, sb), (sr, st),
            (sl, sb), (sr, st), (sl, st),
        ])
        uvs.extend([
            (u0, v_bot), (u1, v_bot), (u1, v_top),
            (u0, v_bot), (u1, v_top), (u0, v_top),
        ])

        pen_x += int(round(g['advance']))

    return verts, uvs


# Cached glyph batches keyed by (text, x, y, px_size). Each label is drawn
# ~5× per frame (4 shadow passes + foreground) and re-tessellated every
# time — that buffer upload was the text half of the per-frame cost.
# Geometry is constant while a floater isn't being dragged, so during
# viewport navigation every lookup hits. Colour is a per-draw uniform (not
# in the batch). Cleared whenever the atlas is rebaked (size/scale change).
from collections import OrderedDict as _OD
_GLYPH_BATCH_CACHE = _OD()
_GLYPH_BATCH_CACHE_MAX = 8192
# Profiler counters (a MISS = a freshly tessellated glyph batch).
_GLYPH_STATS = {'hit': 0, 'miss': 0}


def _clear_glyph_batch_cache():
    _GLYPH_BATCH_CACHE.clear()


def _glyph_batch(shader, text, x, y, px_size, atlas):
    key = (text, int(round(x)), int(round(y)), px_size)
    b = _GLYPH_BATCH_CACHE.get(key)
    if b is None:
        _GLYPH_STATS['miss'] += 1
        verts, uvs = _build_glyph_quads(text, x, y, atlas)
        if not verts:
            return None
        b = batch_for_shader(shader, 'TRIS', {"pos": verts, "uv": uvs})
        _GLYPH_BATCH_CACHE[key] = b
        if len(_GLYPH_BATCH_CACHE) > _GLYPH_BATCH_CACHE_MAX:
            _GLYPH_BATCH_CACHE.popitem(last=False)
    else:
        _GLYPH_STATS['hit'] += 1
        _GLYPH_BATCH_CACHE.move_to_end(key)
    return b


def _draw_text_atlas(x, y, text, color, px_size):
    """Render `text` at baseline (x, y) via the blf-baked atlas for
    `px_size`. Returns True on success."""
    atlas = _get_atlas(px_size)
    if atlas is None:
        return False
    shader = _get_text_shader()
    if shader is None:
        return False
    if not text:
        return True

    batch = _glyph_batch(shader, text, x, y, px_size, atlas)
    if batch is None:
        return True

    try:
        gpu.state.blend_set('ALPHA')
        shader.bind()
        mvp = (gpu.matrix.get_projection_matrix()
               @ gpu.matrix.get_model_view_matrix())
        shader.uniform_float('ModelViewProjectionMatrix', mvp)
        shader.uniform_sampler('atlas', atlas['texture'])
        shader.uniform_float('fg_color', color)
        batch.draw(shader)
        gpu.state.blend_set('NONE')
        return True
    except Exception as e:
        print(f"[INU Floater] atlas text draw failed: {e}")
        return False


def _text_dims_atlas(text, atlas):
    """(width, cap_height) for `text` in `atlas`'s native pixel size.

    Height is plain cap-height (height of 'M'), NOT ascent — callers use
    this for visual centring inside widgets. Including the diacritic
    headroom in the height would push every label DOWN inside its row by
    1-2 px, making it look bottom-anchored vs native Blender."""
    m = atlas['metrics']
    glyphs = m['glyphs']
    total_w = 0.0
    for ch in text:
        g = glyphs.get(ch) or glyphs.get('?')
        if g is None:
            total_w += 6
            continue
        total_w += g['advance']
    return (total_w, float(m['cap_h']))


# Memoise `_text_dims` results by (text, px_size). The widget code calls
# this for every label, button, glyph during layout AND inside the
# shadow loop, so without caching a single redraw walks every label
# string ~5× looking up per-character advance metrics.
_TEXT_DIMS_CACHE = {}


def _text_dims(text, size=None):
    """Return (width, height) of `text` as _text() will draw it."""
    px = _text_px_size(size)
    key = (text, px)
    cached = _TEXT_DIMS_CACHE.get(key)
    if cached is not None:
        return cached
    atlas = _get_atlas(px)
    if atlas is not None:
        result = _text_dims_atlas(text, atlas)
    else:
        font_id = 0
        blf.size(font_id, px)
        result = blf.dimensions(font_id, text)
    if len(_TEXT_DIMS_CACHE) > 1024:
        # Hard cap — avoids unbounded growth if some pathological caller
        # feeds us unique strings every frame.
        _TEXT_DIMS_CACHE.clear()
    _TEXT_DIMS_CACHE[key] = result
    return result


def _draw_glyph_string(font_id, text, x, y, char_spacing):
    """Draw `text` either as a single blf string (char_spacing == 0,
    preserves font kerning) or character-by-character with explicit
    +N pixel gaps. Used both for shadow passes and the main glyphs."""
    if char_spacing <= 0:
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, text)
        return
    cur_x = x
    for ch in text:
        blf.position(font_id, cur_x, y, 0)
        blf.draw(font_id, ch)
        cw, _ = blf.dimensions(font_id, ch)
        cur_x += int(cw) + char_spacing


# Extra horizontal pixels inserted between consecutive characters when
# drawing floater text. 0 = use blf's natural advance with kerning
# preserved (single-string draw). Forced spacing experiments looked
# worse than letting blf own the spacing — kept the dial in case we
# need it but currently disabled.
_LETTER_SPACING = 0


def _text(x, y, text, color=TH._C_TEXT, size=None):
    """Draw text. Prefers our blf-baked atlas + GLSL shader; falls
    back to direct blf if the atlas isn't available.

    Atlas path does 2-pass shadow (offset draws of the same glyph list)
    + foreground. Both passes go through the same GPU shader so there
    are no blf-state surprises after offscreen / custom shader use.
    """
    ix, iy = int(x), int(y)
    px_size = _text_px_size(size)
    atlas = _get_atlas(px_size)

    if atlas is not None and _get_text_shader() is not None:
        # Multi-pass faux-Gaussian drop shadow.
        #
        # Renders the same glyph list at several low-alpha offsets
        # below + diagonal-below the foreground. Diagonals (±1, -1)
        # land in the inter-letter gap at the bottom row and bleed
        # shadow alpha there — same darkening native UI text shows
        # between letters, without halo above letter tops (we never
        # sample above the foreground row).
        #
        #                  GG GG GG       ← foreground
        #                 . .  GG . .     ← diagonals + main bottom
        #                  .  ..  .       ← far falloff
        #
        # Forced on regardless of pref's `widget.shadow` (which is 0 in
        # default Blender themes) — native popups render with a visible
        # shadow under text and we want the same baseline contrast.
        #
        # Trimmed to 2 passes (was 4 with diagonals). The diagonals
        # added inter-letter darkening, but each pass renders the full
        # glyph batch — at 25+ labels per frame, 4 passes meant 100+
        # text draws per redraw and caused a noticeable freeze on first
        # open. 2 passes keep the depth feel without the cost.
        ox = _UI_SHADOW_OFFSET[0]
        oy = _UI_SHADOW_OFFSET[1] if _UI_SHADOW_OFFSET[1] != 0 else -1
        sr, sg, sb, _ = _UI_SHADOW_COLOR
        sa = 1.0
        shadow_passes = (
            (ox, oy - 1, 0.12),    # 2 px below — far falloff
            (ox - 1, oy, 0.18),    # 1 px left  — weaker side halo
            (ox + 1, oy, 0.18),    # 1 px right — weaker side halo
            (ox, oy,     0.40),    # main bottom — strongest (drawn last)
        )
        for dx, dy, mult in shadow_passes:
            _draw_text_atlas(ix + dx, iy + dy, text,
                             (sr, sg, sb, sa * mult), px_size)
        # Foreground glyphs
        _draw_text_atlas(ix, iy, text, color, px_size)
        return

    # ── blf fallback ──
    font_id = 0
    pt = _UI_FONT_SIZE if size is None else size
    blf.size(font_id, int(round(pt * _UI_FONT_SCALE)))
    try:
        blf.disable(font_id, blf.MONOCHROME)
        blf.disable(font_id, blf.SHADOW)
        blf.disable(font_id, blf.ROTATION)
        blf.disable(font_id, blf.CLIPPING)
        blf.disable(font_id, blf.WORD_WRAP)
        blf.aspect(font_id, 1.0)
    except Exception:
        pass

    cs = _LETTER_SPACING
    if _UI_SHADOW_KIND:
        ox, oy = _UI_SHADOW_OFFSET
        sr, sg, sb, sa = _UI_SHADOW_COLOR
        for px, py, mult in (
            (ox, oy - 1, 0.20),
            (ox, oy,     0.55),
        ):
            blf.color(font_id, sr, sg, sb, sa * mult)
            _draw_glyph_string(font_id, text, ix + px, iy + py, cs)
    blf.color(font_id, *color)
    _draw_glyph_string(font_id, text, ix, iy, cs)


