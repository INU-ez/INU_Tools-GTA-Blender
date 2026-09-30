# INU_tools.ops.texture_browser_ops
# Operators driving the Texture Browser panel: scan TXDs from a chosen
# source, populate the WindowManager UIList, lazily decode the
# currently-selected texture into a Blender Image for preview.

import os
import bpy

from .. import T


# ── Source resolution ────────────────────────────────────────────

def _collect_sources(context):
    """Resolve the user's source mode into ``(img_paths, txd_folder,
    ide_paths)``. Returns ``(img_paths, folder, ides, err)`` — on
    error the first three are empty and ``err`` is a translated
    string for the caller to report.
    """
    s = context.scene.inu_settings
    mode = s.gtatools_texture_browser_source

    img_paths = []
    folder = ''
    ides = []

    if mode == 'DAT':
        from ..core.gta_dat import parse_gta_dat, resolve_paths
        dat_path = bpy.path.abspath(s.gtatools_map_analyzer_dat_path or '')
        if not dat_path or not os.path.isfile(dat_path):
            return [], '', [], T("Укажите gta.dat файл в Map Analyzer")
        root = bpy.path.abspath(getattr(s, 'gtatools_game_root', '') or '')
        if not root:
            root = os.path.dirname(os.path.dirname(dat_path))
        try:
            info = parse_gta_dat(dat_path)
        except Exception as e:
            return [], '', [], f"DAT parse error: {e}"
        info = resolve_paths(root, info)
        img_paths = [p for p in info.img_paths if os.path.isfile(p)]
        ides = [p for p in info.ide_paths if os.path.isfile(p)]
        return img_paths, '', ides, None

    if mode == 'FOLDER':
        folder = bpy.path.abspath(s.gtatools_texture_browser_folder or '')
        if not folder or not os.path.isdir(folder):
            return [], '', [], T("Укажите существующую папку")
        # Auto-find .img in the same folder (recursive). User typically
        # wants to scan a mod folder containing both .img and .txd
        # files at once.
        for root_dir, _dirs, files in os.walk(folder):
            for fn in files:
                if fn.lower().endswith('.img'):
                    img_paths.append(os.path.join(root_dir, fn))
        return img_paths, folder, [], None

    if mode == 'CUSTOM':
        items = [bpy.path.abspath(it.path)
                 for it in s.gtatools_texture_browser_custom if it.path]
        items = [p for p in items if os.path.isfile(p)]
        if not items:
            return [], '', [], T("Список файлов пуст — добавь .img / .txd кнопкой '+'")
        # Split by extension. Standalone .txd files are scanned
        # individually below by reading raw bytes; .img files use the
        # archive walker.
        txd_singles = []
        for p in items:
            low = p.lower()
            if low.endswith('.img'):
                img_paths.append(p)
            elif low.endswith('.txd'):
                txd_singles.append(p)
        # Stash standalone txd paths in a separate channel via the
        # operator-local convention: caller checks for these by
        # extension in the returned folder list. To keep the return
        # signature simple, we encode them as a synthetic folder
        # containing only those files. Simpler: scan them directly
        # at call site.
        return img_paths, '', [], ('__txd_singles__', txd_singles)

    return [], '', [], T("Неизвестный режим источника")


# ── Operators ────────────────────────────────────────────────────

class GTATOOLS_OT_scan_textures(bpy.types.Operator):
    """Просканировать TXD по выбранному источнику и заполнить
    Texture Browser метаданными (без декодинга пикселей)"""
    bl_idname = "gtatools.scan_textures"
    bl_label = "INU: Scan Textures"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Resolve sources first so we can fail fast without clearing
        # the current results on a misconfiguration.
        img_paths, folder, ides, err = _collect_sources(context)
        # CUSTOM mode encodes single .txd files via a tuple in the
        # err slot — unpack if present (not an actual error).
        txd_singles = []
        if isinstance(err, tuple) and err[0] == '__txd_singles__':
            txd_singles = err[1]
            err = None
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        from ..core import texture_index as ti

        s = context.scene.inu_settings
        wm = context.window_manager
        results = wm.gtatools_texture_browser_results
        results.clear()
        wm.gtatools_texture_browser_results_index = 0

        # ── Phase 1: scan archives & standalone TXDs ──────────────
        entries = []
        wm.progress_begin(0, 100)
        try:
            for ip in img_paths:
                entries.extend(ti.scan_img(ip))
            if folder:
                entries.extend(ti.scan_folder(folder, recursive=True))
            # Single .txd files come through CUSTOM-mode tuple route.
            for txd_path in txd_singles:
                try:
                    with open(txd_path, 'rb') as f:
                        raw = f.read()
                except OSError:
                    continue
                base = os.path.basename(txd_path).rsplit('.', 1)[0]
                entries.extend(ti.scan_txd_bytes(raw, txd_path, base))
        finally:
            wm.progress_end()

        # ── Phase 2: optional IDE cross-reference for usage_count ─
        usage_map = {}
        if s.gtatools_texture_browser_check_ide:
            # Prefer the scene's DAT-resolved IDE list if we just used
            # DAT mode; otherwise fall back to Map Analyzer's CUSTOM
            # IDE list so the user can pick the IDE set independently
            # of the TXD source.
            ide_paths = list(ides)
            if not ide_paths:
                ide_paths = [bpy.path.abspath(it.path)
                             for it in s.gtatools_map_analyzer_custom_ides
                             if it.path]
                ide_paths = [p for p in ide_paths if os.path.isfile(p)]
            if ide_paths:
                usage_map = ti.build_usage_map(ide_paths)

        # ── Phase 3: populate UIList ──────────────────────────────
        for e in entries:
            it = results.add()
            it.archive_path = e.archive_path
            it.txd_name = e.txd_name
            it.texture_name = e.texture_name
            it.width = e.width
            it.height = e.height
            it.depth = e.depth
            it.fourcc = e.fourcc
            it.num_levels = e.num_levels
            it.platform_id = e.platform_id
            it.format_label = e.format_label
            it.usage_count = len(usage_map.get(e.txd_name.lower(), []))

        # Trigger preview load for the first item (if any). Setting
        # index=0 is a no-op when already 0; bump-and-reset to force
        # the update callback to fire even when scan results sort
        # the same first item back to position 0.
        if len(results):
            wm.gtatools_texture_browser_results_index = 0
            _refresh_preview(context)

        msg = T("Текстур найдено") + f": {len(results)}"
        if usage_map:
            msg += " · " + T("IDE cross-ref активен")
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_clear_texture_browser(bpy.types.Operator):
    """Очистить результаты Texture Browser"""
    bl_idname = "gtatools.clear_texture_browser"
    bl_label = "INU: Clear Texture Browser"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        wm = context.window_manager
        wm.gtatools_texture_browser_results.clear()
        wm.gtatools_texture_browser_results_index = 0
        # Drop the preview image too — it carries pixels we no
        # longer need and would shadow any future preview if its
        # dimensions don't match.
        img = bpy.data.images.get(_PREVIEW_IMG_NAME)
        if img is not None:
            try:
                bpy.data.images.remove(img, do_unlink=True)
            except Exception:
                pass
        return {'FINISHED'}


# ── Custom-list add/remove (CUSTOM source mode) ──────────────────

class GTATOOLS_OT_texture_browser_add_file(bpy.types.Operator):
    """Добавить .img / .txd в список Custom"""
    bl_idname = "gtatools.texture_browser_add_file"
    bl_label = "INU: Add Texture Source"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default='*.img;*.txd', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}
        coll = context.scene.inu_settings.gtatools_texture_browser_custom
        item = coll.add()
        item.path = self.filepath
        return {'FINISHED'}


class GTATOOLS_OT_texture_browser_remove_file(bpy.types.Operator):
    """Удалить запись из Custom-списка"""
    bl_idname = "gtatools.texture_browser_remove_file"
    bl_label = "INU: Remove Texture Source"
    bl_options = {'REGISTER', 'INTERNAL'}

    index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        coll = context.scene.inu_settings.gtatools_texture_browser_custom
        if 0 <= self.index < len(coll):
            coll.remove(self.index)
        return {'FINISHED'}


# ── Lazy preview ─────────────────────────────────────────────────

# Single shared Blender Image used as the preview surface. Reused
# across selections — we rewrite its pixels on every index change
# rather than creating a fresh Image (the latter leaves data-blocks
# accumulating in the .blend / outliner).
_PREVIEW_IMG_NAME = 'INU_TextureBrowser_Preview'


def _refresh_preview(context):
    """Decode the currently-selected texture and write its pixels
    into the shared preview Image. Called from the index update
    callback and right after scan_textures finishes.
    """
    wm = context.window_manager
    results = wm.gtatools_texture_browser_results
    idx = wm.gtatools_texture_browser_results_index
    if not (0 <= idx < len(results)):
        return
    item = results[idx]

    from ..core import texture_index as ti
    tex = ti.decode_one_texture(item.archive_path, item.txd_name,
                                item.texture_name)
    if tex is None or not tex.pixels:
        return

    # R<->B swap, same rule as TXD import (txd_import.py): paletted
    # (PAL8/PAL4) D3D8 textures (GTA III) come out of the decoder with
    # R and B swapped. Without it the preview showed them in different
    # colours than after import.
    px = tex.pixels
    if (getattr(tex, 'platform_id', 0) == 8
            and getattr(tex, 'raster_format', 0) & 0x6000):  # PAL8|PAL4
        buf = bytearray(px)
        buf[0::4], buf[2::4] = px[2::4], px[0::4]
        px = bytes(buf)

    # Build / resize the preview Image. Blender requires a fresh
    # Image when dimensions change — scale() trims/extends pixel
    # buffer but the pixel layout is float[width*height*4] which
    # only matches new dims after .pixels assignment.
    img = bpy.data.images.get(_PREVIEW_IMG_NAME)
    w, h = tex.width, tex.height
    if img is None or img.size[0] != w or img.size[1] != h:
        if img is not None:
            try:
                bpy.data.images.remove(img, do_unlink=True)
            except Exception:
                pass
        img = bpy.data.images.new(
            _PREVIEW_IMG_NAME, width=w, height=h, alpha=True)

    # Pixel format conversion: tex.pixels is uint8 RGBA top-to-bottom,
    # Blender expects float [0..1] bottom-to-top.
    try:
        import numpy as np
        arr = np.frombuffer(px, dtype=np.uint8).astype(np.float32) / 255.0
        arr = arr.reshape((h, w, 4))[::-1]   # flip Y
        img.pixels.foreach_set(arr.ravel())
    except Exception:
        # Fallback: pure-python conversion. Slow but works without
        # numpy if a future Blender build excludes it.
        flat = []
        row_bytes = w * 4
        for y in range(h - 1, -1, -1):
            row = px[y * row_bytes : (y + 1) * row_bytes]
            for b in row:
                flat.append(b / 255.0)
        img.pixels = flat

    img.update()


def on_index_update(self, context):
    """update= callback wired onto
    ``WindowManager.gtatools_texture_browser_results_index``. Fires on
    every selection change in the UIList; we decode + render the
    selected texture's pixels into the shared preview Image.

    Wrapped in try/except so a bad TXD entry can't break the panel —
    failed previews just leave the previous preview visible.
    """
    try:
        _refresh_preview(context)
    except Exception:
        pass


