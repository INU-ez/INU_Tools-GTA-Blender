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


class GTATOOLS_OT_scan_binary_ipls(bpy.types.Operator):
    """Сканировать IMG архивы и собрать список бинарных IPL для выбранного района. После скана можно галочками включать/выключать конкретные файлы"""
    bl_idname = "gtatools.scan_binary_ipls"
    bl_label = "INU: Scan Binary IPLs"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.gta_dat import find_all_resources
        from ..core.img import read_directory
        scene = context.scene

        game_root = bpy.path.abspath(getattr(scene.inu_settings, 'gtatools_game_root', ''))
        if not game_root or not os.path.isdir(game_root):
            self.report({'ERROR'}, T("Укажите корневую папку GTA SA"))
            return {'CANCELLED'}

        region = getattr(scene.inu_settings, 'gtatools_map_region', 'ALL')
        region_u = region.upper() if region != 'ALL' else 'ALL'

        info = find_all_resources(game_root)
        img_paths = []
        std = os.path.join(game_root, 'models', 'gta3.img')
        if os.path.isfile(std):
            img_paths.append(std)
        for p in info.img_paths:
            if os.path.isfile(p) and p not in img_paths:
                img_paths.append(p)

        # Remember previously enabled entries so rescans don't lose user picks
        prev_bin = {i.name.lower(): i.enabled
                    for i in scene.inu_settings.gtatools_binary_ipls}
        prev_txt = {i.name.lower(): i.enabled
                    for i in scene.inu_settings.gtatools_text_ipls}

        scene.inu_settings.gtatools_binary_ipls.clear()
        scene.inu_settings.gtatools_text_ipls.clear()
        total_checked = 0
        for ip in img_paths:
            try:
                for e in read_directory(ip):
                    nm = e.name.lower()
                    if not nm.endswith('.ipl'):
                        continue
                    total_checked += 1
                    # Peek first 4 bytes — bnry → binary; anything else
                    # → treat as text IPL.
                    try:
                        from ..core.img import extract_file
                        head = extract_file(ip, e.name)
                    except Exception:
                        continue
                    if not head:
                        continue
                    is_binary = head[:4] == b'bnry'
                    # IMG entry names have no path — region match falls
                    # back to basename prefix only.  Mod IPLs inside IMG
                    # rarely use region prefixes, so consider "ALL" the
                    # safer default for the IMG path; users still pick
                    # individual files via the checkbox list.
                    if region_u != 'ALL' and not e.name.upper().startswith(region_u):
                        continue
                    if is_binary:
                        item = scene.inu_settings.gtatools_binary_ipls.add()
                        item.name = e.name
                        item.img_source = ip
                        item.enabled = prev_bin.get(nm, True)
                    else:
                        item = scene.inu_settings.gtatools_text_ipls.add()
                        item.name = e.name
                        item.path = e.name  # name inside IMG
                        item.img_source = ip
                        item.enabled = prev_txt.get(nm, True)
            except Exception as ex:
                self.report({'WARNING'}, f"{os.path.basename(ip)}: {ex}")

        # Loose text IPLs — collected from two sources:
        #   1. ``info.ipl_paths`` (gta.dat references)
        #   2. Recursive disk scan of <game_root> for *.ipl files
        # Both sources are de-duped by absolute path; the recursive
        # walk catches mods that don't register in gta.dat or have
        # gta.dat in a non-standard location.
        loose_paths = set()
        from_gta_dat = 0
        for tp in info.ipl_paths:
            if os.path.isfile(tp):
                loose_paths.add(os.path.normcase(os.path.abspath(tp)))
                from_gta_dat += 1
        print(f"[Scan IPL] game_root: {game_root!r}")
        print(f"[Scan IPL] info.ipl_paths from gta.dat: {len(info.ipl_paths)}")
        print(f"[Scan IPL] found on disk via gta.dat refs: {from_gta_dat}")

        # Recursive disk fallback over the whole game_root.  Mod packs
        # drop IPLs in arbitrary places: data/maps/<custom>, models/,
        # CleanIDE/, custom roots.  We aggressively walk the whole
        # tree and only skip housekeeping dirs (.git etc.) — false
        # positives are basically free (regex match on extension).
        from_disk = 0
        before = len(loose_paths)
        # Folders that NEVER contain IPLs and would just slow us down.
        # NB: ``models/`` is NOT skipped — some mods store loose IPLs
        # there alongside their DFFs.
        SKIP_DIRS = {'.git', '.svn', '__pycache__',
                     'audio', 'movies', 'anim', 'text', 'fonts'}
        for dirpath, dirnames, filenames in os.walk(game_root):
            dirnames[:] = [d for d in dirnames
                           if d.lower() not in SKIP_DIRS]
            for fn in filenames:
                if not fn.lower().endswith('.ipl'):
                    continue
                full = os.path.normcase(os.path.abspath(
                    os.path.join(dirpath, fn)))
                if full not in loose_paths:
                    loose_paths.add(full)
                    from_disk += 1
        print(f"[Scan IPL] additionally found on disk: {from_disk}")
        print(f"[Scan IPL] total unique loose IPLs: {len(loose_paths)}")

        # Region filter: matches either by ``MAPS/<region>/`` segment
        # in the path (handles ``data/maps/Props_obj/foo.ipl`` where
        # the region is "PROPS_OBJ" picked from the folder name) OR
        # by basename prefix (handles ``LAn.ipl`` for region "LA").
        # The basename-only check used previously dropped 100% of mod
        # IPLs whose region is encoded in the folder path, not the name.
        def _matches_region(p: str) -> bool:
            if region_u == 'ALL':
                return True
            parts = p.replace('\\', '/').upper().split('/')
            for i, part in enumerate(parts):
                if part == 'MAPS' and i + 1 < len(parts):
                    return parts[i + 1] == region_u
            return os.path.basename(p).upper().startswith(region_u)

        region_filtered = 0
        for tp in sorted(loose_paths):
            base = os.path.basename(tp)
            nm = base.lower()
            if not _matches_region(tp):
                region_filtered += 1
                continue
            item = scene.inu_settings.gtatools_text_ipls.add()
            item.name = base
            item.path = tp        # absolute loose path
            item.img_source = ""  # empty → loose file marker
            item.enabled = prev_txt.get(nm, True)
        if region_filtered:
            print(f"[Scan IPL] region '{region}' filtered out: {region_filtered}")

        scene['gtatools_binary_ipls_region'] = region
        self.report({'INFO'},
                    f"{len(scene.inu_settings.gtatools_binary_ipls)} binary + "
                    f"{len(scene.inu_settings.gtatools_text_ipls)} text IPL(s) "
                    f"for region '{region}' (scanned {total_checked} IMG-entries)")
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
        from ..core.img import extract_file, read_directory
        from ..core.ide import read_ide
        from ..core.ipl import read_ipl, _read_binary_ipl
        from .ipl_sections import import_ipl_sections

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
        ide_models = {}
        for p in info.ide_paths:
            if os.path.isfile(p):
                try:
                    ide = read_ide(p)
                    for obj in ide.objects:
                        ide_models[obj.model_id] = obj
                    for anim in ide.anims:
                        if anim.model_id not in ide_models:
                            ide_models[anim.model_id] = anim
                except Exception:
                    pass

        # Region filter
        region = getattr(scene.inu_settings, 'gtatools_map_region', 'ALL')

        def _ipl_folder_matches_region(path: str) -> bool:
            """Vanilla rule: IPL physically lives in ``maps/<region>/`` (or,
            when the path has no MAPS folder, its basename starts with the
            region name)."""
            parts = path.replace('\\', '/').upper().split('/')
            for i, part in enumerate(parts):
                if part == 'MAPS' and i + 1 < len(parts):
                    return parts[i + 1] == region
            name = path.replace('\\', '/').rsplit('/', 1)[-1].upper()
            return name.startswith(region)

        # First pass: basenames of every IPL whose FOLDER is the region.
        # Streamed / child IPLs (``countn2_stream3``, ``countryw_stream8``)
        # usually live OUTSIDE ``maps/<region>/`` but are named
        # ``<base>_<suffix>`` after one of these base IPLs — so a plain
        # folder filter silently drops whole streamed chunks of the
        # district. We pull them back in by that name relationship.
        region_stems = set()
        if region != 'ALL':
            for _p in info.ipl_paths:
                if _ipl_folder_matches_region(_p):
                    _bn = os.path.splitext(os.path.basename(_p))[0].lower()
                    if _bn:
                        region_stems.add(_bn)

        def _ipl_matches_region(path: str) -> bool:
            if region == 'ALL':
                return True
            if _ipl_folder_matches_region(path):
                return True
            # ``<base>_<suffix>`` child of a base region IPL (e.g.
            # ``countn2`` → ``countn2_stream3``). The ``_`` guard keeps
            # ``countn`` from greedily matching ``countnXYZ`` unrelated.
            bn = os.path.splitext(os.path.basename(path))[0].lower()
            return any(bn.startswith(stem + '_') for stem in region_stems)

        # Read text IPL files.
        #
        # IPL ``lod_index`` is LOCAL to each file — it references a
        # position inside that same IPL's instance list. When we flatten
        # instances from many IPLs into one list, we MUST rebase each
        # lod_index onto the merged list, otherwise Map_LOD gets filled
        # with wrong models (indices from one file pointing into another
        # file's region). Do the same below for binary IPLs.
        #
        # Each instance gets ``_source_ipl`` (basename without extension)
        # tagged on so the optional Group-by-IPL collection scheme can
        # bin them later — this metadata is throwaway, dropped after
        # the import loop completes.
        #
        # ``gtatools_text_ipls`` (when the user populated it via Scan)
        # acts as a per-file allowlist: only loose IPL paths whose
        # basename appears as enabled in the collection are processed.
        # Empty collection = take everything that passes the region
        # filter (preserves the old behaviour for users who skip Scan).
        ti_entries = scene.inu_settings.gtatools_text_ipls
        ti_enabled_loose = {i.name.lower() for i in ti_entries
                            if i.enabled and not i.img_source}
        ti_enabled_img = {i.name.lower() for i in ti_entries
                          if i.enabled and i.img_source}
        ti_use_selection = len(ti_entries) > 0

        instances = []
        # Diagnostic: report which IPLs are dropped and why, so a district
        # that «didn't fully load» can be traced to the region filter or the
        # Scan selection rather than guessed at.
        _ipl_total = len(info.ipl_paths)
        _ipl_loaded = _ipl_skip_region = _ipl_skip_sel = 0
        print(f"[MAP] region filter = {region!r}; text-IPL selection "
              f"{'ON' if ti_use_selection else 'off'}; {_ipl_total} IPL paths")
        for p in info.ipl_paths:
            if not os.path.isfile(p):
                continue
            if not _ipl_matches_region(p):
                _ipl_skip_region += 1
                # Show WHAT got dropped and from where — so a missing
                # district chunk can be traced to the region filter's
                # folder rule vs the mod's actual IPL layout.
                try:
                    _rel = os.path.relpath(p, game_root)
                except Exception:
                    _rel = p
                print(f"[MAP] IPL dropped by region {region!r}: {_rel}")
                continue
            if ti_use_selection:
                base_lc = os.path.basename(p).lower()
                if base_lc not in ti_enabled_loose:
                    _ipl_skip_sel += 1
                    print(f"[MAP] IPL dropped (not in Scan selection): "
                          f"{os.path.basename(p)}")
                    continue
            _ipl_loaded += 1
            if True:
                try:
                    ipl = read_ipl(p)
                    base = len(instances)
                    n_local = len(ipl.instances)
                    ipl_basename = os.path.splitext(os.path.basename(p))[0]
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
                        import_ipl_sections(ipl)
                except Exception:
                    pass

        print(f"[MAP] text IPL: loaded={_ipl_loaded}, "
              f"dropped by region={_ipl_skip_region}, "
              f"dropped by selection={_ipl_skip_sel} "
              f"→ {len(instances)} instances")

        # Binary IPLs still live inside IMG archives — one-time scan
        # at invoke (NOT in the hot loop) to pull out their instance
        # lists. This doesn't count as "hitting IMG during import": it's
        # metadata gathering before the actual model import begins.
        bi_entries = scene.inu_settings.gtatools_binary_ipls
        bi_enabled = {i.name.lower() for i in bi_entries if i.enabled}
        bi_use_selection = len(bi_entries) > 0

        img_paths = []
        for p in info.img_paths:
            if os.path.isfile(p) and p not in img_paths:
                img_paths.append(p)
        std = os.path.join(game_root, 'models', 'gta3.img')
        if os.path.isfile(std) and std not in img_paths:
            img_paths.insert(0, std)
        fallback = bpy.path.abspath(scene.inu_settings.gtatools_img_path)
        if fallback and os.path.isfile(fallback) and fallback not in img_paths:
            img_paths.append(fallback)

        for ip in img_paths:
            try:
                for e in read_directory(ip):
                    key = e.name.lower()
                    if not key.endswith('.ipl'):
                        continue
                    # Format auto-detect happens below; first apply the
                    # right allowlist depending on whether THIS entry
                    # turns out binary or text.  We peek the file once
                    # and reuse the bytes to avoid double IMG read.
                    try:
                        ipl_data = extract_file(ip, e.name)
                    except Exception:
                        continue
                    if not ipl_data:
                        continue
                    is_binary = ipl_data[:4] == b'bnry'

                    # Per-format allowlist (if user populated the lists);
                    # otherwise fall back to region filter alone.
                    if is_binary and bi_use_selection:
                        if key not in bi_enabled:
                            continue
                    elif (not is_binary) and ti_use_selection:
                        if key not in ti_enabled_img:
                            continue
                    elif not _ipl_matches_region(key):
                        continue

                    try:
                        if is_binary:
                            ipl_parsed = _read_binary_ipl(ipl_data)
                        else:
                            # Text IPL inside IMG — decode and parse via
                            # the same loose-file path.  IPL parser
                            # accepts text body; we use a temp file to
                            # keep the public API single-purpose.
                            import tempfile
                            with tempfile.NamedTemporaryFile(
                                    mode='wb', suffix='.ipl',
                                    delete=False) as tf:
                                tf.write(ipl_data)
                                tmp_path = tf.name
                            try:
                                ipl_parsed = read_ipl(tmp_path)
                            finally:
                                try:
                                    os.unlink(tmp_path)
                                except OSError:
                                    pass

                        base = len(instances)
                        n_local = len(ipl_parsed.instances)
                        ipl_basename = os.path.splitext(e.name)[0]
                        for inst in ipl_parsed.instances:
                            if 0 <= inst.lod_index < n_local:
                                inst.lod_index = base + inst.lod_index
                            else:
                                inst.lod_index = -1
                            inst._source_ipl = ipl_basename
                            instances.append(inst)
                    except Exception:
                        pass
            except Exception:
                pass

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
        from ..core.ipl import is_lod_name
        from ..core.dff import read_dff
        from ..core.col import read_col
        from .dff_import import import_dff_from_clump
        from .col_import import import_col_from_models
        from mathutils import Quaternion
        from concurrent.futures import ThreadPoolExecutor

        instances = self._instances
        ide_models = self._ide_models
        skip_lod = self._skip_lod
        skip_2dfx = self._skip_2dfx
        scene = self._scene
        prof = self._profiler
        load_col = bool(getattr(scene.inu_settings, 'gtatools_map_load_col', False))
        # LOD detection by name only. ``is_lod_name`` already handles
        # all 4 vanilla naming patterns (LODfoo / foo_LOD / foo1LOD /
        # modeLODlaett). The IPL ``lod_index`` cross-reference used to
        # be an additional signal here, but vanilla IPL data turned out
        # noisy — it classified non-LOD models as LOD (see issue where
        # Map_LOD filled with airuntest_las, arhang_LAS etc.).

        # Cache-only import. Extract Resources must have run first;
        # anything not in the cache is counted as skipped. No IMG
        # reads, no disk round-trips beyond the cache itself.
        imported_models = {}
        # Per-model cache of imported COL objects, mirrors
        # imported_models. One unique model → one COL geometry,
        # copied per IPL instance.
        imported_col_models: dict = {}
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

        for idx, inst in enumerate(instances):
            with prof.stage('loop iter'):
                self._progress = idx + 1
                model_name = inst.model_name
                if not model_name:
                    self._skipped += 1
                    self._skip_noname += 1
                    _need_yield = (idx % 32 == 0)
                else:
                    is_lod = is_lod_name(model_name)
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
                                            if inst.model_id in ide_models:
                                                ide_obj = ide_models[inst.model_id]
                                                o.inu.draw_distance = ide_obj.draw_distance
                                                o.inu.ide_flags = ide_obj.flags
                                                o.inu.txd_name = ide_obj.txd_name
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

                            # COL: build/copy + place at the same
                            # transform as the DFF instance. Default mode
                            # uses one global Map_COL (lazy-created on
                            # first match); group-by-IPL routes the
                            # collision into the IPL's own Map_<ipl>_COL
                            # sub-collection.
                            if load_col:
                                col_model = col_by_name.get(model_name.lower())
                                if col_model is not None:
                                    map_col = self._pick_col_collection(inst)

                                    col_src = imported_col_models.get(model_name)
                                    if col_src is None:
                                        with prof.stage('build COL', note=model_name):
                                            col_src = import_col_from_models(
                                                [col_model],
                                                bulk_mode=True,
                                                target_collection=map_col,
                                                material_cache=col_material_cache,
                                            )
                                            imported_col_models[model_name] = col_src
                                        col_new = col_src
                                    else:
                                        with prof.stage('reuse COL'):
                                            col_new = []
                                            for src in col_src:
                                                co = src.copy()
                                                co.data = src.data
                                                map_col.objects.link(co)
                                                col_new.append(co)

                                    with prof.stage('COL transform'):
                                        for co in col_new:
                                            if co.type == 'MESH':
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


