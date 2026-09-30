# INU_tools.ops.map_ops — map-discovery and binary-IPL operators.
#
# Phase 3 of UI redesign. Holds every map-related Blender operator —
# auto-discovery, binary-IPL scan, BBox/Links viewport toggles + their
# draw handlers + globals, glTF load/build (modal), Import Map (modal
# with parallel TXD), Replace fake-with-DFF. Six heavy operators in this
# file came from __init__.py in batch 3b (2026-04-26).

import os
import bpy
from bpy.props import (
    BoolProperty, StringProperty,
)

from .. import T


class GTATOOLS_OT_discover_game(bpy.types.Operator):
    """Найти все IDE/IPL/IMG по gta.dat из корневой папки игры"""
    bl_idname = "gtatools.discover_game"
    bl_label = "INU: Auto-discover"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..core.gta_dat import find_all_resources
        scene = context.scene
        game_root = bpy.path.abspath(scene.inu_settings.gtatools_game_root)
        if not game_root or not os.path.isdir(game_root):
            self.report({'ERROR'}, T("Укажите корневую папку GTA SA"))
            return {'CANCELLED'}

        dat_path = os.path.join(game_root, 'data', 'gta.dat')
        if not os.path.isfile(dat_path):
            self.report({'ERROR'}, T("Не найден data/gta.dat в указанной папке"))
            return {'CANCELLED'}

        info = find_all_resources(game_root)

        ide_count = len([p for p in info.ide_paths if os.path.isfile(p)])
        ipl_count = len([p for p in info.ipl_paths if os.path.isfile(p)])
        img_count = len([p for p in info.img_paths if os.path.isfile(p)])

        # Auto-set main IMG path on first discover so the user doesn't
        # have to navigate to gta3.img by hand.
        if not scene.inu_settings.gtatools_img_path:
            for p in info.img_paths:
                if os.path.isfile(p) and 'gta3.img' in p.lower():
                    scene.inu_settings.gtatools_img_path = p
                    break

        self.report({'INFO'},
                    f"IDE: {ide_count}, IPL: {ipl_count}, IMG: {img_count}")
        return {'FINISHED'}


class GTATOOLS_OT_set_preset_dir(bpy.types.Operator):
    """Выбрать папку для хранения всех пресетов и данных INU Tools.
    Существующие пресеты копируются в новую папку."""
    bl_idname = "gtatools.set_preset_dir"
    bl_label = "INU: Set Preset Folder"
    bl_options = {'REGISTER'}

    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from ..tools import user_data
        target = bpy.path.abspath(self.directory).strip()
        if not target or not os.path.isdir(target):
            self.report({'ERROR'}, T("Выберите существующую папку"))
            return {'CANCELLED'}
        copied = user_data.copy_presets_to(target)
        user_data.set_preset_root_override(target)
        self.report({'INFO'},
                    T("Папка пресетов: {0} (скопировано файлов: {1})").format(
                        target, copied))
        return {'FINISHED'}


class GTATOOLS_OT_reset_preset_dir(bpy.types.Operator):
    """Вернуть папку пресетов к расположению по умолчанию"""
    bl_idname = "gtatools.reset_preset_dir"
    bl_label = "INU: Reset Preset Folder"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..tools import user_data
        user_data.set_preset_root_override(None)
        self.report({'INFO'},
                    T("Папка пресетов сброшена: {0}").format(
                        user_data.get_default_preset_root()))
        return {'FINISHED'}


class GTATOOLS_OT_open_preset_dir(bpy.types.Operator):
    """Открыть текущую папку пресетов в проводнике"""
    bl_idname = "gtatools.open_preset_dir"
    bl_label = "INU: Open Preset Folder"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..tools import user_data
        path = user_data.get_user_data_dir()
        try:
            bpy.ops.wm.path_open(filepath=path)
        except Exception:
            self.report({'WARNING'}, path)
            return {'CANCELLED'}
        return {'FINISHED'}


class GTATOOLS_OT_binary_ipl_toggle_all(bpy.types.Operator):
    """Включить или выключить все бинарные IPL в списке одной кнопкой"""
    bl_idname = "gtatools.binary_ipl_toggle_all"
    bl_label = "INU: Toggle All Binary IPLs"
    bl_options = {'REGISTER', 'UNDO'}

    enable: BoolProperty(default=True)

    def execute(self, context):
        for item in context.scene.inu_settings.gtatools_binary_ipls:
            item.enabled = self.enable
        return {'FINISHED'}


class GTATOOLS_OT_text_ipl_toggle_all(bpy.types.Operator):
    """Включить или выключить все текстовые IPL в списке одной кнопкой"""
    bl_idname = "gtatools.text_ipl_toggle_all"
    bl_label = "INU: Toggle All Text IPLs"
    bl_options = {'REGISTER', 'UNDO'}

    enable: BoolProperty(default=True)

    def execute(self, context):
        for item in context.scene.inu_settings.gtatools_text_ipls:
            item.enabled = self.enable
        return {'FINISHED'}


def _region_file_set(scene, game_root, info, errors=None):
    """IPL files of the picked region — the one set Scan lists, Import Map
    reads and Extract takes TXDs for (core/map_files.region_files, as the
    game links them): text IPLs of gta.dat in maps/<region>/ (or named
    after it) + their <stem>_stream<N>.ipl from every archive of the game
    folder in load order (gta_int.img included; a name in two archives is
    taken from the first). Returns (text [path], binary [(entry name,
    archive, entry)], archives); unreadable archives go to ``errors``."""
    from ..core.img import read_directory
    from ..core.map_files import game_archives, region_files
    s = scene.inu_settings
    region = getattr(s, 'gtatools_map_region', 'ALL')
    archives = game_archives(game_root, info.img_paths,
                             bpy.path.abspath(s.gtatools_img_path))

    def _entries(ip):
        try:
            return read_directory(ip)
        except Exception as ex:
            print(f"[MAP] {ip}: {ex}")
            if errors is not None:
                errors.append(f"{os.path.basename(ip)}: {ex}")
            return []

    text, binary = region_files(
        [p for p in info.ipl_paths if os.path.isfile(p)], archives, region,
        _entries, game_root)
    return text, binary, archives


class GTATOOLS_OT_scan_binary_ipls(bpy.types.Operator):
    """Сканировать IMG архивы и собрать список бинарных IPL для выбранного района. После скана можно галочками включать/выключать конкретные файлы"""
    bl_idname = "gtatools.scan_binary_ipls"
    bl_label = "INU: Scan Binary IPLs"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.gta_dat import find_all_resources
        scene = context.scene

        game_root = bpy.path.abspath(getattr(scene.inu_settings, 'gtatools_game_root', ''))
        if not game_root or not os.path.isdir(game_root):
            self.report({'ERROR'}, T("Укажите корневую папку GTA SA"))
            return {'CANCELLED'}

        region = getattr(scene.inu_settings, 'gtatools_map_region', 'ALL')

        # The same files Import Map and Extract read for this region:
        # text IPLs of gta.dat + their <stem>_stream<N>.ipl from the
        # archives. Mission IPLs of gta3.img (barriers1, crack…) are not
        # linked to a text IPL — the game loads them from a script only.
        info = find_all_resources(game_root)
        errors = []
        text, binary, archives = _region_file_set(scene, game_root, info,
                                                  errors)
        for msg in errors:
            self.report({'WARNING'}, msg)

        # Remember previously enabled entries so rescans don't lose user picks
        prev_bin = {i.name.lower(): i.enabled
                    for i in scene.inu_settings.gtatools_binary_ipls}
        prev_txt = {i.name.lower(): i.enabled
                    for i in scene.inu_settings.gtatools_text_ipls}

        scene.inu_settings.gtatools_binary_ipls.clear()
        scene.inu_settings.gtatools_text_ipls.clear()
        for n, ip, _e in binary:
            item = scene.inu_settings.gtatools_binary_ipls.add()
            item.name = n
            item.img_source = ip
            item.enabled = prev_bin.get(n.lower(), True)
        for tp in text:
            base = os.path.basename(tp)
            item = scene.inu_settings.gtatools_text_ipls.add()
            item.name = base
            item.path = tp        # absolute loose path
            item.img_source = ""  # empty → loose file marker
            item.enabled = prev_txt.get(base.lower(), True)
        print(f"[Scan IPL] game_root: {game_root!r}, region {region!r}: "
              f"{len(text)} text IPL(s) of gta.dat, {len(binary)} streamed "
              f"from {len(archives)} archive(s)")

        scene['gtatools_binary_ipls_region'] = region
        self.report({'INFO'},
                    f"{len(scene.inu_settings.gtatools_binary_ipls)} binary + "
                    f"{len(scene.inu_settings.gtatools_text_ipls)} text IPL(s) "
                    f"for region '{region}' (scanned {len(archives)} IMG archive(s))")
        return {'FINISHED'}


# ─────────────── Map viewport / glTF / import ops ─────────────────
# Block below moved verbatim from __init__.py (batch 3b). Two helpers
# defined far down in __init__.py (_get_cache_dir, _sort_map_objects,
# _load_textures_from_cache) are pulled in lazily inside each method
# that uses them — top-level `from .. import _foo` would race with
# __init__.py's own initialization order.

_bbox_mode_active = False
_bbox_last_selection = set()


_bbox_near_set = set()


def _bbox_meshes():
    """Every mesh object BBox mode manages. Scans ALL meshes in the file, not
    just the `Map_*` collections — Group-by-IPL trees and IMG-import put
    objects in differently-named collections, so the old prefix filter left
    them untouched and BBox mode «did nothing».

    Хелперы НЕ трогаем: превью-объекты (inu.type='NON' — 2DFX короны и т.п.)
    и меши с намеренно нестандартным display_type (WIRE-кубы секций IPL,
    INU_LightCutter, SOLID-прокси) — иначе toggle-off сбрасывал бы их в
    TEXTURED, затирая задуманный режим отрисовки. Управляем только
    TEXTURED↔BOUNDS."""
    out = []
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        inu = getattr(o, 'inu', None)
        if inu is not None and getattr(inu, 'type', 'OBJ') == 'NON':
            continue
        if o.display_type not in ('TEXTURED', 'BOUNDS'):
            continue
        out.append(o)
    return out


@bpy.app.handlers.persistent
def _bbox_selection_handler(scene, depsgraph):
    """Keep selected + nearby (300m) objects as TEXTURED, rest as BOUNDS.

    Hooked into ``depsgraph_update_post`` because Blender does not expose a
    clean event for «selection set changed» — there's no RNA property an
    ``update=`` callback could attach to. The handler is registered only
    while BBox mode is ON (see ``GTATOOLS_OT_toggle_bbox``) and removed on
    toggle-off, so it does NOT poll the scene continuously.
    """
    global _bbox_last_selection, _bbox_near_set
    if not _bbox_mode_active:
        return
    # Only recompute in OBJECT mode. In Edit/Sculpt/Paint the object-level
    # selection can't change anyway, and running this on EVERY mesh-edit
    # depsgraph tick — each call builds `context.selected_objects`, which is
    # O(number of objects) — is what made Edit Mode lag on big maps.
    if getattr(bpy.context, 'mode', 'OBJECT') != 'OBJECT':
        return

    try:
        selected = {o.name for o in bpy.context.selected_objects if o.type == 'MESH'}
    except Exception:
        return
    if selected == _bbox_last_selection:
        return
    _bbox_last_selection = selected

    sel_positions = []
    for name in selected:
        obj = bpy.data.objects.get(name)
        if obj:
            sel_positions.append(obj.location)

    new_near = set()
    radius = 300.0

    for obj in _bbox_meshes():
        if obj.name in selected:
            new_near.add(obj.name)
        elif sel_positions and any((obj.location - sp).length <= radius for sp in sel_positions):
            new_near.add(obj.name)

    # Objects that left the near zone → BOUNDS
    for name in _bbox_near_set - new_near:
        obj = bpy.data.objects.get(name)
        if obj and obj.type == 'MESH':
            obj.display_type = 'BOUNDS'

    # Objects that entered the near zone → TEXTURED
    for name in new_near - _bbox_near_set:
        obj = bpy.data.objects.get(name)
        if obj and obj.type == 'MESH':
            obj.display_type = 'TEXTURED'

    _bbox_near_set = new_near


# ── Model Links Visualization ────────────────────────────────────────

_links_draw_handler = None
# Mirror of scene.inu_settings.gtatools_links_active for legacy readers.
# Authoritative state lives in the scene property so it persists with
# the .blend; this global is refreshed in the toggle operator and on
# load_post (re-registers the draw handler on file open if active).
_links_active = False


def _draw_model_links():
    """Draw lines between DFF↔LOD↔COL related models."""
    import gpu
    from gpu_extras.batch import batch_for_shader

    if not _links_active:
        return

    from ..tools.model_utils import get_model_type

    # Group objects by base name
    groups = {}  # base_name → {'DFF': obj, 'LOD': obj, 'COL': obj}
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        mt, base = get_model_type(obj)
        if not base:
            continue
        base_clean = base.rstrip('_').lower()
        if base_clean not in groups:
            groups[base_clean] = {'DFF': None, 'LOD': None, 'COL': None}
        if mt and groups[base_clean][mt] is None:
            groups[base_clean][mt] = obj

    # Build dashed lines
    verts = []
    colors = []
    dash_len = 0.5
    gap_len = 0.3

    def _add_dashed(p1, p2, color):
        from mathutils import Vector
        a = Vector(p1)
        b = Vector(p2)
        d = b - a
        total = d.length
        if total < 0.01:
            return
        step = dash_len + gap_len
        n = d.normalized()
        t = 0.0
        while t < total:
            seg_start = a + n * t
            seg_end = a + n * min(t + dash_len, total)
            verts.extend([seg_start, seg_end])
            colors.extend([color, color])
            t += step

    for base, g in groups.items():
        dff = g['DFF']
        lod = g['LOD']
        col = g['COL']

        if dff and lod:
            _add_dashed(dff.location, lod.location, (0.2, 0.6, 1.0, 0.8))  # blue
        if dff and col:
            _add_dashed(dff.location, col.location, (1.0, 0.3, 0.1, 0.8))  # red
        if lod and col and not dff:
            _add_dashed(lod.location, col.location, (1.0, 0.6, 0.0, 0.8))  # orange

    if not verts:
        return

    shader = gpu.shader.from_builtin('FLAT_COLOR')
    batch = batch_for_shader(shader, 'LINES', {"pos": verts, "color": colors})
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(3.0)
    shader.bind()
    batch.draw(shader)
    gpu.state.blend_set('NONE')
    gpu.state.line_width_set(1.0)


class GTATOOLS_OT_toggle_links(bpy.types.Operator):
    """Показать/скрыть линии связей DFF↔LOD↔COL"""
    bl_idname = "gtatools.toggle_links"
    bl_label = "INU: Toggle Model Links"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global _links_active, _links_draw_handler

        settings = context.scene.inu_settings
        new_active = not settings.gtatools_links_active
        settings.gtatools_links_active = new_active
        _links_active = new_active

        if _links_active:
            if _links_draw_handler is None:
                _links_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                    _draw_model_links, (), 'WINDOW', 'POST_VIEW')
            self.report({'INFO'}, "Model Links: ON")
        else:
            if _links_draw_handler is not None:
                bpy.types.SpaceView3D.draw_handler_remove(_links_draw_handler, 'WINDOW')
                _links_draw_handler = None
            self.report({'INFO'}, "Model Links: OFF")

        # Force viewport redraw
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}


class GTATOOLS_OT_toggle_bbox(bpy.types.Operator):
    """Переключить все Map_ объекты между Bounding Box и Textured"""
    bl_idname = "gtatools.toggle_bbox"
    bl_label = "INU: Toggle Bounding Box"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global _bbox_mode_active, _bbox_last_selection, _bbox_near_set

        _bbox_mode_active = not _bbox_mode_active

        selected = {o.name for o in context.selected_objects if o.type == 'MESH'}

        if _bbox_mode_active:
            sel_positions = []
            for name in selected:
                obj = bpy.data.objects.get(name)
                if obj:
                    sel_positions.append(obj.location)

            radius = 300.0
            count = 0
            near = set()
            for obj in _bbox_meshes():
                is_near = (obj.name in selected or
                           (sel_positions and any((obj.location - sp).length <= radius for sp in sel_positions)))
                obj.display_type = 'TEXTURED' if is_near else 'BOUNDS'
                if is_near:
                    near.add(obj.name)
                count += 1

            _bbox_last_selection = selected
            _bbox_near_set = near
            if _bbox_selection_handler not in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.append(_bbox_selection_handler)
        else:
            count = 0
            for obj in _bbox_meshes():
                obj.display_type = 'TEXTURED'
                count += 1

            _bbox_last_selection = set()
            _bbox_near_set = set()
            if _bbox_selection_handler in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(_bbox_selection_handler)

        self.report({'INFO'}, f"BBox: {'ON' if _bbox_mode_active else 'OFF'} ({count})")
        return {'FINISHED'}


def _map_key(model_name, inst):
    """Метка размещения: «имя модели|x|y|z» с точностью до сантиметра.

    Имя объекта для опознания не годится — Blender вешает на дубли
    суффиксы .001, а у моделей из DFF имена берутся от фреймов, а не от
    имени модели."""
    return "%s|%.2f|%.2f|%.2f" % (
        (model_name or "").lower(), inst.pos_x, inst.pos_y, inst.pos_z)


class GTATOOLS_OT_import_map(bpy.types.Operator):
    """Импорт карты GTA SA: автопоиск IDE/IPL/IMG по папке игры"""
    bl_idname = "gtatools.import_map"
    bl_label = "INU: Import Map"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _gen = None

    def invoke(self, context, event):
        from ..core.gta_dat import find_all_resources
        from ..core.ide import read_ide
        from ..core.ipl import read_ipl
        from ..core.map_files import (binary_stem, read_entry, read_ipl_bytes,
                                      rebase_binary_lod)
        from .ipl_sections import import_ipl_sections, _existing_rows

        scene = context.scene
        game_root = bpy.path.abspath(scene.inu_settings.gtatools_game_root)
        skip_lod = getattr(scene.inu_settings, 'gtatools_img_skip_lod', False)
        # Read «Без 2DFX» once here in a reliable context and pass it
        # explicitly to the builder. Relying on import_dff_from_clump's
        # fallback (bpy.context.scene read) is fragile: in the modal/bulk
        # path that scene can read back as None → skip_2dfx silently
        # becomes False and 2DFX load even with the toggle ON.
        skip_2dfx = getattr(scene.inu_settings, 'gtatools_map_skip_2dfx', False)
        skip_dupes = getattr(scene.inu_settings,
                             'gtatools_map_skip_dupes', False)

        if not game_root or not os.path.isdir(game_root):
            self.report({'ERROR'}, T("Укажите корневую папку GTA SA"))
            return {'CANCELLED'}

        dat_path = os.path.join(game_root, 'data', 'gta.dat')
        if not os.path.isfile(dat_path):
            self.report({'ERROR'}, T("Не найден data/gta.dat в указанной папке"))
            return {'CANCELLED'}

        # Cache check — cache-only import requires Extract Resources
        # to have been run first; otherwise we'd just skip everything.
        from .. import _get_cache_dir
        cache_dir = _get_cache_dir()
        has_cached_dff = False
        if os.path.isdir(cache_dir):
            try:
                for name in os.listdir(cache_dir):
                    if name.lower().endswith('.dff'):
                        has_cached_dff = True
                        break
            except Exception:
                pass
        if not has_cached_dff:
            # Soft warning instead of hard cancel — IDE/IPL still
            # produce useful Empty placeholders even without DFFs,
            # and the user may want to skim the layout before
            # spending minutes on extraction.
            self.report(
                {'WARNING'},
                T("Кеш пуст — будут расставлены только Empty по "
                  "IPL без геометрии. Для полной карты сначала "
                  "запустите «Извлечь ресурсы»"))

        info = find_all_resources(game_root)

        # Read all IDE files
        from .map_link import norm
        ide_models = {}
        # model_id → IDE file of the row in ide_models (same «last wins»):
        # the placed model gets linked to it, as on the Import tab.
        ide_source = {}
        for p in info.ide_paths:
            if os.path.isfile(p):
                pn = norm(p)
                try:
                    ide = read_ide(p)
                    for obj in ide.objects:
                        ide_models[obj.model_id] = obj
                        ide_source[obj.model_id] = pn
                    for anim in ide.anims:
                        if anim.model_id not in ide_models:
                            ide_models[anim.model_id] = anim
                            ide_source[anim.model_id] = pn
                except Exception:
                    pass

        # Region filter
        region = getattr(scene.inu_settings, 'gtatools_map_region', 'ALL')

        # IPL files of the region — the same set Scan lists and Extract
        # reads: text IPLs of gta.dat in maps/<region>/ + their
        # <stem>_stream<N>.ipl from the archives (as the game links them).
        text_ipls, bin_ipls, _archives = _region_file_set(
            scene, game_root, info)

        # Archive each cached DFF came from (Extract's index) → «В IMG» and
        # the default target of Export to IMG, as the Import tab sets them.
        # A DFF the index lacks (cache of an older Extract, or one stopped
        # by ESC) → the game's winner in the archive directories.
        from ..core.map_files import extract_winners, load_index
        src_arch = {k: v[0] for k, v in
                    load_index(cache_dir).get('files', {}).items()
                    if isinstance(v, list) and v and k.endswith('.dff')}
        from ..core.img import read_directory

        def _dir(ip):
            try:
                return read_directory(ip)
            except Exception:
                return []
        for k, (a, _e) in extract_winners(_archives, _dir,
                                          exts=('.dff',)).items():
            src_arch.setdefault(k, a)

        # Read text IPL files.
        #
        # IPL ``lod_index`` is LOCAL to each file — it references a
        # position inside that same IPL's instance list. When we flatten
        # instances from many IPLs into one list, we MUST rebase each
        # lod_index onto the merged list, otherwise Map_LOD gets filled
        # with wrong models (indices from one file pointing into another
        # file's region). Streamed IPLs below point into their text IPL.
        #
        # Each instance gets ``_source_ipl`` (basename without extension)
        # tagged on so the optional Group-by-IPL collection scheme can
        # bin them later — this metadata is throwaway, dropped after
        # the import loop completes.
        #
        # Scan checkboxes (``gtatools_text_ipls`` / ``gtatools_binary_ipls``)
        # switch single files off: a file missing from the list stays ON,
        # and lists scanned for another region are ignored (the dynamic
        # region enum can shift without calling its update callback).
        use_lists = scene.get('gtatools_binary_ipls_region', '') == region
        ti_off = {i.name.lower() for i in scene.inu_settings.gtatools_text_ipls
                  if not i.enabled} if use_lists else set()
        bi_off = {i.name.lower() for i in scene.inu_settings.gtatools_binary_ipls
                  if not i.enabled} if use_lists else set()

        instances = []
        # IPL sections already in the scene — one snapshot for the whole
        # run: a re-import adds nothing, equal lines of two files both stay
        _sec_existing = None
        # Where each text IPL landed in ``instances``: (first index, rows).
        text_base = {}
        # Diagnostic: report which IPLs are dropped and why, so a district
        # that «didn't fully load» can be traced to the region filter or the
        # Scan selection rather than guessed at.
        _ipl_total = len(info.ipl_paths)
        _ipl_loaded = _ipl_skip_sel = 0
        _ipl_skip_region = _ipl_total - len(text_ipls)
        print(f"[MAP] region filter = {region!r}; Scan checkboxes "
              f"{'ON' if use_lists else 'off'}; {_ipl_total} IPL paths")
        for p in text_ipls:
            if os.path.basename(p).lower() in ti_off:
                _ipl_skip_sel += 1
                print(f"[MAP] IPL dropped (unchecked in Scan): "
                      f"{os.path.basename(p)}")
                continue
            _ipl_loaded += 1
            if True:
                try:
                    ipl = read_ipl(p)
                    base = len(instances)
                    n_local = len(ipl.instances)
                    ipl_basename = os.path.splitext(os.path.basename(p))[0]
                    text_base[ipl_basename.lower()] = (base, n_local)
                    for inst in ipl.instances:
                        if 0 <= inst.lod_index < n_local:
                            inst.lod_index = base + inst.lod_index
                        else:
                            inst.lod_index = -1
                        inst._source_ipl = ipl_basename
                        # Loose text IPL → the placed model gets linked to
                        # this row (map_link.stamp_ipl) right away.
                        inst._source_path = p
                        inst._source_base = base
                        instances.append(inst)
                    if any([ipl.culls, ipl.garages, ipl.enexs, ipl.pickups,
                            ipl.cars, ipl.jumps, ipl.auzos, ipl.occls]):
                        if _sec_existing is None:
                            _sec_existing = _existing_rows()
                        from ..core import game_versions as gv
                        import_ipl_sections(
                            ipl, existing=_sec_existing,
                            game=gv.game_of_scene(scene))
                except Exception:
                    pass

        print(f"[MAP] text IPL: loaded={_ipl_loaded}, "
              f"dropped by region={_ipl_skip_region}, "
              f"dropped by selection={_ipl_skip_sel} "
              f"→ {len(instances)} instances")

        # Streamed IPLs live inside the archives — one-time read at invoke
        # (NOT in the hot loop), grouped per archive. Their lod_index
        # points into the text IPL they belong to (CIplStore::LoadIpl takes
        # the LOD from the related text IPL's rows), not into themselves:
        # rebase it onto that text IPL; text IPL unchecked → no LOD.
        # Read by directory record (the one the game streams), not by name.
        by_arch = {}
        for n, ip, e in bin_ipls:
            if n.lower() not in bi_off:
                by_arch.setdefault(ip, []).append((n, e))
        n_bin_lod = n_bin_lost = 0
        for ip, recs in by_arch.items():
            try:
                with open(ip, 'rb') as fh:
                    for n, e in recs:
                        try:
                            ipl_parsed = read_ipl_bytes(read_entry(fh, e))
                        except Exception:
                            continue
                        tb = text_base.get(binary_stem(n) or '')
                        ipl_basename = os.path.splitext(n)[0]
                        for inst in ipl_parsed.instances:
                            li = inst.lod_index
                            inst.lod_index = rebase_binary_lod(li, tb)
                            if inst.lod_index >= 0:
                                n_bin_lod += 1
                            elif li >= 0:
                                n_bin_lost += 1
                            inst._source_ipl = ipl_basename
                            instances.append(inst)
            except Exception:
                pass
        if n_bin_lost:
            print(f"[MAP] streamed IPL rows whose LOD row is in an unloaded "
                  f"text IPL: {n_bin_lost}")

        if not instances:
            self.report({'WARNING'}, T("IPL файл пуст или не указан"))
            return {'CANCELLED'}

        for inst in instances:
            if not inst.model_name and inst.model_id in ide_models:
                inst.model_name = ide_models[inst.model_id].model_name

        # Create collections
        def _get_col(name):
            c = bpy.data.collections.get(name)
            if not c:
                c = bpy.data.collections.new(name)
                context.scene.collection.children.link(c)
            return c

        # Group-by-IPL mode swaps the static draw-distance buckets
        # (Map_DFF_Far / Mid / Near) for one collection per source IPL
        # (Map_LAn / Map_LAs / Map_SF / …). Per-IPL collections are
        # created lazily as instances are bucketed in _work — empty
        # IPLs never produce empty collections.
        group_by_ipl = bool(getattr(scene.inu_settings, 'gtatools_map_group_by_ipl', True))

        if group_by_ipl:
            dff_far = dff_mid = dff_near = lod_col = None
            ipl_collections: dict = {}
        else:
            dff_far = _get_col("Map_DFF_Far")
            dff_mid = _get_col("Map_DFF_Mid")
            dff_near = _get_col("Map_DFF_Near")
            lod_col = _get_col("Map_LOD")
            ipl_collections = None

            # Hide collections during import
            dff_far.hide_viewport = True
            dff_mid.hide_viewport = True
            dff_near.hide_viewport = True
            lod_col.hide_viewport = True

        # Map_COL is created lazily in _work only if load_col is on AND
        # at least one match is found — keeps the outliner clean when
        # the user doesn't need collisions.
        map_col_collection = None

        # Store state
        self._instances = instances
        self._ide_models = ide_models
        self._ide_source = ide_source
        self._src_arch = src_arch
        self._skip_lod = skip_lod
        # Что уже стоит в сцене: (ID модели, позиция с точностью до
        # сантиметра). Имя объекта для этого не годится — Blender вешает
        # на дубли суффиксы .001, а ID и координаты остаются прежними.
        self._skip_dupes = skip_dupes
        self._placed = set()
        self._placed_keys = set()
        # Печатается ВСЕГДА, даже при выключенной галочке: по этой строке
        # сразу видно и что сборка свежая, и в каком положении тумблер.
        print("[INU map] «Без дублей» = %s" % ("ВКЛ" if skip_dupes else "выкл"))
        if skip_dupes:
            # scene.objects, а не bpy.data.objects: скрытые и лежащие в
            # выключенных коллекциях сюда входят (hide_viewport и exclude на
            # состав сцены не влияют), а объекты ДРУГИХ сцен — нет. Иначе
            # вторая сцена с той же картой молча съела бы весь импорт.
            for _o in scene.objects:
                if _o.type != 'MESH':
                    continue
                _inu = getattr(_o, 'inu', None)
                _mk = str(getattr(_inu, 'map_key', '') or '')
                if _mk:
                    self._placed_keys.add(_mk)
                _mid = int(getattr(_inu, 'model_id', 0) or 0)
                if _mid <= 0:
                    continue
                _l = _o.matrix_world.translation
                self._placed.add((_mid, round(_l.x, 2), round(_l.y, 2),
                                  round(_l.z, 2)))
            print("[INU map] «Без дублей»: в сцене найдено %d размещений "
                  "по метке и %d по (ID, позиция)"
                  % (len(self._placed_keys), len(self._placed)))
        self._skip_2dfx = skip_2dfx
        self._group_by_ipl = group_by_ipl
        self._ipl_collections = ipl_collections
        self._dff_far = dff_far
        self._dff_mid = dff_mid
        self._dff_near = dff_near
        self._lod_col = lod_col
        self._map_col_collection = map_col_collection
        self._imported = 0
        self._skipped = 0
        # Skip-reason breakdown:
        self._skip_noname = 0   # model_id has no name in the IDE
        self._skip_nocache = 0  # DFF not found in the loaded IMG/cache
        self._skip_error = 0    # DFF parse raised
        self._skip_lodname = 0  # detected as LOD name + «Skip LOD» is on
        self._skip_dupe = 0     # размещение уже есть в сцене
        self._n_bin_lod = n_bin_lod  # streamed rows linked to their LOD
        self._progress = 0
        self._total = len(instances)
        self._scene = scene

        # Profiler — same pattern as Extract Resources.
        from ..tools.profiler import Profiler
        self._profiler = Profiler(
            f"Import Map ({region})",
            enabled=bool(getattr(scene.inu_settings, 'gtatools_profile_enabled', False)),
        )

        self._gen = self._work(context)
        wm = context.window_manager
        wm.progress_begin(0, len(instances))
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(T("Импорт карты..."))
        return {'RUNNING_MODAL'}

    def _get_ipl_subcol(self, ipl_basename: str, kind: str):
        """Lazily fetch / create a sub-collection inside <ipl>.

        Layout (no ``Map_`` prefix — keeps round-trip readable, the
        parent collection name matches the original IPL filename so
        re-export with «split by collection» writes back to the same
        district name):

            <ipl>/                  (parent, hidden during import)
              <ipl>_DFF
              <ipl>_LOD
              <ipl>_COL

        ``kind`` is 'dff' / 'lod' / 'col'. The parent + the requested
        sub-collection are created on demand — IPLs without LOD or COL
        models never produce empty containers.
        """
        cache = self._ipl_collections
        entry = cache.get(ipl_basename)
        if entry is None:
            parent = bpy.data.collections.get(ipl_basename)
            if parent is None:
                parent = bpy.data.collections.new(ipl_basename)
                self._scene.collection.children.link(parent)
                parent.hide_viewport = True
            entry = {'parent': parent}
            cache[ipl_basename] = entry

        sub = entry.get(kind)
        if sub is None:
            sub_name = f"{ipl_basename}_{kind.upper()}"
            sub = bpy.data.collections.get(sub_name)
            if sub is None:
                sub = bpy.data.collections.new(sub_name)
                entry['parent'].children.link(sub)
            entry[kind] = sub
        return sub

    def _pick_target_col(self, inst, is_lod: bool):
        """Route an IPL instance to its destination collection.

        Group-by-IPL mode: instance lands in Map_<ipl>/Map_<ipl>_DFF or
        Map_<ipl>_LOD depending on ``is_lod``. Default mode: LODs go to
        ``Map_LOD``, non-LODs are bucketed by draw-distance into
        Map_DFF_Far / Mid / Near.
        """
        if self._group_by_ipl:
            ipl = getattr(inst, '_source_ipl', None) or 'unknown'
            return self._get_ipl_subcol(ipl, 'lod' if is_lod else 'dff')
        if is_lod:
            return self._lod_col
        ide_models = self._ide_models
        model_id = inst.model_id
        if model_id in ide_models:
            dd = ide_models[model_id].draw_distance
            if dd >= 300:
                return self._dff_far
            elif dd >= 100:
                return self._dff_mid
            else:
                return self._dff_near
        return self._dff_far

    def _pick_col_collection(self, inst):
        """Return the COL bucket for an instance.

        Group-by-IPL: each IPL's own ``Map_<ipl>/Map_<ipl>_COL`` sub.
        Default: lazy global ``Map_COL`` (created on first match).
        """
        if self._group_by_ipl:
            ipl = getattr(inst, '_source_ipl', None) or 'unknown'
            return self._get_ipl_subcol(ipl, 'col')

        if self._map_col_collection is None:
            mc = bpy.data.collections.get("Map_COL")
            if mc is None:
                mc = bpy.data.collections.new("Map_COL")
                self._scene.collection.children.link(mc)
                mc.hide_viewport = True
            self._map_col_collection = mc
        return self._map_col_collection

    def _work(self, context):
        from ..core.ipl import is_lod_name, lod_instance_indices
        from ..core.dff import read_dff
        from ..core.col import read_col
        from .dff_import import import_dff_from_clump
        from .col_import import import_col_from_models
        from . import map_link
        from mathutils import Quaternion
        from concurrent.futures import ThreadPoolExecutor

        instances = self._instances
        ide_models = self._ide_models
        ide_source = self._ide_source
        src_arch = self._src_arch
        skip_lod = self._skip_lod
        skip_2dfx = self._skip_2dfx
        scene = self._scene
        prof = self._profiler
        load_col = bool(getattr(scene.inu_settings, 'gtatools_map_load_col', False))
        # LOD = a row another row points at through ``lod_index`` (as the
        # game counts LOD children), or a LOD name — ``is_lod_name``
        # handles all 4 vanilla patterns (LODfoo / foo_LOD / foo1LOD /
        # modeLODlaett). The lod_index signal was once dropped as «noisy»
        # (Map_LOD filled with airuntest_las, arhang_LAS etc.): that noise
        # came from rebasing streamed IPLs' lod_index inside their own
        # file — they point into their text IPL (see invoke).

        # Cache-only import. Extract Resources must have run first;
        # anything not in the cache is counted as skipped. No IMG
        # reads, no disk round-trips beyond the cache itself.
        imported_models = {}
        # Models whose COL is already built (lower-case, as col_by_name):
        # one collision per model, at its first placement — like Max.
        col_done: set = set()
        # Shared material cache for COL bulk import — same surface
        # tuple across many models reuses one datablock. See
        # _create_mesh_from_col / project_col_import_perf.
        col_material_cache: dict = {}
        from .. import _get_cache_dir
        tmpdir = _get_cache_dir()
        tex_cache = os.path.join(tmpdir, 'textures')
        tex_cache_exists = os.path.isdir(tex_cache)
        load_txd = getattr(scene.inu_settings, 'gtatools_img_load_txd', True)

        # Shared material cache — dedupes materials across DFFs by
        # (texture_name, rgba). Same texture used by 500 different
        # buildings ⇒ one Blender material, not 500.
        material_cache: dict = {}
        # Materials whose texture-alpha link was already evaluated (so we
        # run the per-pixel alpha check once per material, not per instance).
        alpha_linked: set = set()

        # ── Parallel DFF parse pipeline ────────────────────────────
        # numpy's zero-copy frombuffer + zlib decompress inside
        # read_dff both release the GIL, so N worker threads can
        # actually parse DFF binaries in parallel while the main
        # thread is busy creating bpy objects for the previous one.
        # We pre-submit all unique models' parse jobs; the pool
        # scheduler fans them out to up to 4 workers. Main loop
        # below fetches results via .result() which blocks only
        # if the worker hasn't finished yet — usually it's already
        # done by the time we reach it.
        seen = set()
        unique_models = []
        for inst in instances:
            mn = inst.model_name
            if mn and mn not in seen:
                seen.add(mn)
                unique_models.append(mn)

        def _parse_dff_path(path):
            with open(path, 'rb') as f:
                return read_dff(f.read())

        self._parse_pool = ThreadPoolExecutor(
            max_workers=min(os.cpu_count() or 4, 4))
        parse_pool = self._parse_pool
        parse_futures: dict = {}
        # COL map: model_name → ColModel. Populated from parallel
        # parse of every .col file in cache. A single .col file often
        # contains many ColModel entries (Rockstar ships district-wide
        # lib-COLs like LAs.col with hundreds of entries), so we key
        # by the inner model_name rather than by filename.
        col_by_name: dict = {}
        with prof.stage('submit parse jobs'):
            # Build cache-file set in one syscall instead of 3000+
            # os.path.isfile() probes. Set membership check is then
            # a dict lookup per model.
            try:
                cache_listing = os.listdir(tmpdir)
            except OSError:
                cache_listing = []
            cached_dffs = {
                n.lower() for n in cache_listing
                if n.lower().endswith('.dff')
            }
            cached_cols = [
                n for n in cache_listing
                if n.lower().endswith('.col')
            ]
            for name in unique_models:
                dff_key = (name + '.dff').lower()
                if dff_key in cached_dffs:
                    path = os.path.join(tmpdir, name + '.dff')
                    parse_futures[name] = parse_pool.submit(
                        _parse_dff_path, path)

            # Submit COL parse jobs and collect results into
            # col_by_name. Parsing happens in workers, aggregation on
            # the main thread after all futures are done — .col files
            # are fewer (~50 for SA) so we can afford to wait for
            # all of them before entering the main loop.
            if load_col and cached_cols:
                def _parse_col_path(path):
                    with open(path, 'rb') as f:
                        return read_col(f.read())
                col_futs = [
                    parse_pool.submit(_parse_col_path,
                                      os.path.join(tmpdir, n))
                    for n in cached_cols
                ]
                with prof.stage('parse COL files'):
                    for fut in col_futs:
                        try:
                            models = fut.result()
                        except Exception:
                            continue
                        for m in models:
                            mname = (m.model_name or '').lower()
                            if mname and mname not in col_by_name:
                                col_by_name[mname] = m

        # 'loop iter' wraps ALL code executed per instance. Compared
        # against total wall time this tells us how much time is eaten
        # by modal-tick overhead / viewport redraw / depsgraph work
        # happening OUTSIDE the generator (i.e. between yields).
        # Track which Blender object got created for each source IPL
        # instance — needed AFTER the loop to wire ``inu.lod_object``
        # PointerProperty from the source IPL's lod_index. Without this
        # the re-export's IPL writes lod_index = -1 for every entry and
        # SA stops swapping in low-poly LODs at long range.
        instance_to_main_obj: list = [None] * len(instances)
        lod_refs = lod_instance_indices(instances)

        for idx, inst in enumerate(instances):
            with prof.stage('loop iter'):
                self._progress = idx + 1
                model_name = inst.model_name
                if not model_name:
                    self._skipped += 1
                    self._skip_noname += 1
                    _need_yield = (idx % 32 == 0)
                else:
                    is_lod = idx in lod_refs or is_lod_name(model_name)
                    _dupe = False
                    if self._skip_dupes:
                        _mk = _map_key(model_name, inst)
                        _key = (int(inst.model_id or 0),
                                round(inst.pos_x, 2), round(inst.pos_y, 2),
                                round(inst.pos_z, 2))
                        _dupe = (_mk in self._placed_keys
                                 or (_key[0] > 0 and _key in self._placed))
                    if skip_lod and is_lod:
                        self._skipped += 1
                        self._skip_lodname += 1
                        _need_yield = (idx % 32 == 0)
                    elif _dupe:
                        self._skipped += 1
                        self._skip_dupe += 1
                        _need_yield = (idx % 32 == 0)
                    else:
                        _need_yield = True
                        target = self._pick_target_col(inst, is_lod)
                        dff_fn = model_name + '.dff'
                        dff_path = os.path.join(tmpdir, dff_fn)

                        new_objs = None
                        if model_name in imported_models:
                            with prof.stage('reuse (copy)'):
                                new_objs = []
                                for src in imported_models[model_name]:
                                    o = src.copy()
                                    o.data = src.data
                                    # The copy carries the first placement's
                                    # IPL link (uuid, file, raw lod_index):
                                    # drop it — a text IPL row stamps its own
                                    # below, a streamed one stays unlinked.
                                    if hasattr(o, 'inu'):
                                        map_link.clear_ipl(o)
                                        o.inu.lod_object = None
                                    target.objects.link(o)
                                    new_objs.append(o)
                        else:
                            fut = parse_futures.pop(model_name, None)
                            if fut is None:
                                # No parse future = either DFF not in
                                # cache, or we already consumed it
                                # (happens when imported_models check
                                # above misses due to exception path).
                                self._skipped += 1
                                self._skip_nocache += 1
                                print(f"[MAP] no DFF in cache: id={inst.model_id} "
                                      f"name={model_name!r}")
                            else:
                                clump = None
                                try:
                                    with prof.stage('parse wait', note=model_name):
                                        clump = fut.result()
                                except Exception as _ex:
                                    self._skipped += 1
                                    self._skip_error += 1
                                    print(f"[MAP] DFF parse failed: id={inst.model_id} "
                                          f"name={model_name!r}: {_ex}")

                                if clump is not None:
                                    try:
                                        # bulk_mode=True skips per-model view_layer.update()
                                        # and select_all(DESELECT). target_collection=target
                                        # links straight into Map_DFF_* / Map_LOD. material_cache
                                        # and profiler get threaded in so sub-stages (build_mesh)
                                        # appear in the profile report.
                                        with prof.stage('build objects', note=model_name):
                                            new_objs = import_dff_from_clump(
                                                clump, model_name,
                                                skip_2dfx=skip_2dfx,
                                                bulk_mode=True,
                                                target_collection=target,
                                                material_cache=material_cache,
                                                profiler=prof,
                                                fix_winding=True,
                                            )

                                        if load_txd and tex_cache_exists:
                                            with prof.stage('TXD cache load'):
                                                from .. import _load_textures_from_cache
                                                _load_textures_from_cache(tex_cache, new_objs)
                                            # Wire texture-alpha → BSDF alpha
                                            # for foliage/fences/windows
                                            # (textures with a real alpha
                                            # channel). Once per material.
                                            with prof.stage('alpha link'):
                                                from .texture_ops import link_material_alpha_if_textured
                                                for _o in new_objs:
                                                    if _o.type != 'MESH':
                                                        continue
                                                    for _sl in _o.material_slots:
                                                        _m = _sl.material
                                                        if _m is None or _m.name in alpha_linked:
                                                            continue
                                                        alpha_linked.add(_m.name)
                                                        try:
                                                            link_material_alpha_if_textured(_m)
                                                        except Exception:
                                                            pass

                                        # LOD-именование (<base>_LOD вместо
                                        # LOD…_DFF) теперь централизовано в
                                        # import_dff_from_clump → _fallback_name,
                                        # так что отдельный relabel тут не нужен.
                                        imported_models[model_name] = new_objs
                                    except Exception:
                                        new_objs = None

                        if new_objs:
                            with prof.stage('transform apply'):
                                pos = (inst.pos_x, inst.pos_y, inst.pos_z)
                                _mk_now = _map_key(model_name, inst)
                                if self._skip_dupes:
                                    self._placed_keys.add(_mk_now)
                                    self._placed.add(
                                        (int(inst.model_id or 0),
                                         round(inst.pos_x, 2),
                                         round(inst.pos_y, 2),
                                         round(inst.pos_z, 2)))
                                rot = Quaternion((inst.rot_w, inst.rot_x, inst.rot_y, inst.rot_z)).conjugated()
                                main_obj = None
                                for o in new_objs:
                                    if o.type == 'MESH':
                                        o.location = pos
                                        o.rotation_mode = 'QUATERNION'
                                        o.rotation_quaternion = rot
                                        if main_obj is None:
                                            main_obj = o
                                        if hasattr(o, 'inu'):
                                            o.inu.model_id = inst.model_id
                                            # Метка размещения: по ней
                                            # «Без дублей» узнаёт этот кусок
                                            # карты в следующий раз, даже
                                            # если ID модели не проставлен.
                                            o.inu.map_key = _mk_now
                                            map_link.stamp_map_import(
                                                o, is_lod,
                                                ide_models.get(inst.model_id),
                                                ide_source.get(inst.model_id, ''),
                                                src_arch.get(dff_fn.lower(), ''),
                                                model_name)
                                # Stash reference for the post-loop LOD
                                # wire-up pass; first MESH child stands
                                # in for the whole instance.
                                instance_to_main_obj[idx] = main_obj
                                _sp = getattr(inst, '_source_path', '')
                                if (_sp and not is_lod and main_obj is not None
                                        and hasattr(main_obj, 'inu')):
                                    from .map_link import stamp_ipl, norm
                                    _li = inst.lod_index
                                    stamp_ipl(main_obj, norm(_sp), inst,
                                              _li - inst._source_base
                                              if _li >= 0 else -1, fresh=True)

                            # COL: built once per model, at its first
                            # placement (like Max) — the mesh plus the
                            # spheres/boxes as its children, so they
                            # follow it; later placements get no copy.
                            # Default mode uses one global Map_COL
                            # (lazy-created on first match); group-by-IPL
                            # routes the collision into the IPL's own
                            # Map_<ipl>_COL sub-collection.
                            _cn = model_name.lower()
                            if load_col and _cn not in col_done:
                                col_model = col_by_name.get(_cn)
                                if col_model is not None:
                                    col_done.add(_cn)
                                    map_col = self._pick_col_collection(inst)

                                    with prof.stage('build COL', note=model_name):
                                        col_new = import_col_from_models(
                                            [col_model],
                                            bulk_mode=True,
                                            target_collection=map_col,
                                            material_cache=col_material_cache,
                                            with_prims=True,
                                        )

                                    with prof.stage('COL transform'):
                                        for co in col_new:
                                            if co.parent is None:
                                                co.location = pos
                                                co.rotation_mode = 'QUATERNION'
                                                co.rotation_quaternion = rot
                            self._imported += 1
            if _need_yield:
                yield

        # ── LOD wire-up pass ────────────────────────────────────────
        # IPL ``lod_index`` is a position pointer into the same IPL's
        # instance list. Now that every instance has its main Blender
        # object captured in ``instance_to_main_obj``, walk the
        # original instance list and resolve each lod_index → object
        # → store as PointerProperty so re-export can recompute the
        # position (which will differ — different IPL ordering /
        # filtering). Without this, every re-exported instance has
        # lod_index = -1 and SA never streams in low-poly LODs.
        with prof.stage('LOD wire-up'):
            n_inst = len(instances)
            for idx, inst in enumerate(instances):
                main_obj = instance_to_main_obj[idx]
                if main_obj is None:
                    continue
                lod_idx = getattr(inst, 'lod_index', -1)
                if 0 <= lod_idx < n_inst:
                    lod_obj = instance_to_main_obj[lod_idx]
                    if lod_obj is not None and hasattr(main_obj, 'inu'):
                        try:
                            main_obj.inu.lod_object = lod_obj
                            # LOD Dist of the model = its LOD's (from the
                            # LOD's IDE row above), as on the Import tab; a
                            # LOD row pointing at a super-LOD keeps its own.
                            if hasattr(lod_obj, 'inu') and not (
                                    idx in lod_refs
                                    or is_lod_name(inst.model_name)):
                                main_obj.inu.lod_draw_distance = \
                                    lod_obj.inu.lod_draw_distance
                        except Exception:
                            pass

        # Shut the parse pool down — at this point all consumed futures
        # have been popped; any leftovers belong to models we skipped.
        parse_pool.shutdown(wait=False, cancel_futures=True)

        # Report — saved to .inu_cache/_profile.log when enabled, plus stdout.
        if prof.enabled:
            prof.print_report()
            prof.save_log(os.path.join(tmpdir, '_profile.log'))

    def modal(self, context, event):
        if event.type == 'ESC':
            self._finish(context)
            self.report({'WARNING'}, T("Отменено"))
            return {'CANCELLED'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        import time
        wm = context.window_manager
        deadline = time.monotonic() + 0.1

        while time.monotonic() < deadline:
            try:
                next(self._gen)
            except StopIteration:
                self._progress = self._total
                wm.progress_update(self._total)
                self._finish(context)
                msg = f"{T('Импортировано:')} {self._imported}"
                if self._skipped:
                    msg += f", {T('пропущено:')} {self._skipped}"
                    # Spell out the non-LOD skip reasons — these explain a
                    # district that «didn't fully load».
                    reasons = []
                    if self._skip_dupe:
                        reasons.append(
                            f"{self._skip_dupe} {T('уже есть в сцене')}")
                    if self._skip_lodname:
                        reasons.append(
                            f"{self._skip_lodname} {T('LOD — снимите «Skip LOD»')}")
                    if self._skip_noname:
                        reasons.append(f"{self._skip_noname} {T('без имени в IDE')}")
                    if self._skip_nocache:
                        reasons.append(f"{self._skip_nocache} {T('нет DFF в IMG')}")
                    if self._skip_error:
                        reasons.append(f"{self._skip_error} {T('ошибка DFF')}")
                    if reasons:
                        msg += " (" + ", ".join(reasons) + ")"
                if self._n_bin_lod:
                    msg += (f", {T('строк бинарных IPL связано с LOD своего текстового IPL:')} "
                            f"{self._n_bin_lod}")
                self.report({'INFO'}, msg)
                return {'FINISHED'}

        wm.progress_update(self._progress)
        context.workspace.status_text_set(
            f"{T('Импорт карты:')} {self._progress}/{self._total}")
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.window_manager.progress_end()
        context.workspace.status_text_set(None)

        # Always shut the parse pool down, even on cancel — otherwise
        # ESC leaves worker threads alive until Blender GC runs.
        pool = getattr(self, '_parse_pool', None)
        if pool is not None:
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._parse_pool = None

        # Re-enable viewport
        buckets: list = []
        if getattr(self, '_group_by_ipl', False):
            for entry in (self._ipl_collections or {}).values():
                parent = entry.get('parent')
                if parent is not None:
                    buckets.append(parent)
        else:
            buckets.extend([self._dff_far, self._dff_mid, self._dff_near,
                            self._lod_col])
        buckets.append(self._map_col_collection)
        for col in buckets:
            if col:
                col.hide_viewport = False

        context.view_layer.update()


