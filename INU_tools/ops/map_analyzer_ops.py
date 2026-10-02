# INU_tools.ops.map_analyzer_ops
# Operators that drive the «Анализ карты» panel — gather IDE/IPL files
# from one of three sources, parse, run cross-reference lint, fill the
# results UIList. Reuses GTATOOLS_LintIssueItem from the file-scanner.

import os
import datetime
import bpy

from .. import T
from ..core.fs_ci import resolve as _ci


_NON_STREAMING_IMGS = {'anim.img', 'cuts.img', 'carrec.img', 'script.img',
                       'cutscene.img', 'player.img'}


def _asset_inputs(imgs, root, info=None, scan_folder=''):
    """Additional game resources: startup CDIMAGE/IMG and TEXDICTION,
    plus loose modloader overrides. Overrides count for presence only."""
    from ..core.gta_dat import find_all_resources
    loose = []
    infos = [info] if info is not None else []
    if root and os.path.isdir(root):
        infos.append(find_all_resources(root))
    imgs = list(imgs)
    for dat in infos:
        imgs.extend(p for p in dat.img_paths if os.path.isfile(p))
        loose.extend(p for p in dat.texdiction_paths if os.path.isfile(p))
        loose.extend(p for p in dat.modelfile_paths if os.path.isfile(p))
    mod_dirs = []
    if root:
        mod_dirs.append(_ci(os.path.join(root, 'modloader')))
    if scan_folder:
        # FOLDER can itself be a modloader subdirectory.
        if 'modloader' in scan_folder.replace('\\', '/').lower().split('/'):
            mod_dirs.append(scan_folder)
        mod_dirs.append(_ci(os.path.join(scan_folder, 'modloader')))
    for folder in mod_dirs:
        if not os.path.isdir(folder):
            continue
        for r, _dirs, files in os.walk(folder):
            for name in files:
                if name.lower().endswith(('.dff', '.txd')):
                    loose.append(os.path.join(r, name))
    return imgs, loose


def _collect_inputs(context):
    """Resolve the user's chosen input mode into (ide_paths, ipl_paths,
    img_files_set or None). Returns ``(ides, ipls, img, error_msg)``;
    on error ides/ipls/img are None and error_msg is a string for the
    operator to ``self.report``."""
    s = context.scene.inu_settings
    mode = s.gtatools_map_analyzer_mode

    if mode == 'DAT':
        from ..core.gta_dat import parse_gta_dat, resolve_paths, GtaDatInfo
        dat_path = bpy.path.abspath(s.gtatools_map_analyzer_dat_path or '')
        if not dat_path or not os.path.isfile(dat_path):
            return None, None, None, T("Укажите существующий .dat файл")
        # Game root is the parent of the .dat's parent dir typically.
        # Use scene's gtatools_game_root if set, else .dat's parent.
        root = bpy.path.abspath(getattr(s, 'gtatools_game_root', '') or '')
        if not root:
            root = os.path.dirname(os.path.dirname(dat_path))
        try:
            info = parse_gta_dat(dat_path)
        except Exception as e:
            return None, None, None, f"DAT parse error: {e}"
        info = resolve_paths(root, info)
        ides = [p for p in info.ide_paths if os.path.isfile(p)]
        ipls = [p for p in info.ipl_paths if os.path.isfile(p)]
        # The game registers models/gta3.img (and gta_int.img in SA) itself,
        # ahead of the IMG lines — vanilla gta.dat doesn't list them (if a
        # .dat does, _gather_img_files reads the archive once).
        own = [_ci(os.path.join(root, 'models', n)) for n in ('gta3.img', 'gta_int.img')]
        img_paths = [p for p in own + info.img_paths if os.path.isfile(p)]
        img_files = None
        if s.gtatools_map_analyzer_check_img:
            imgs, loose = _asset_inputs(img_paths, root, info)
            img_files = _gather_img_files(imgs, loose)
        return ides, ipls, img_files, None

    if mode == 'FOLDER':
        folder = bpy.path.abspath(s.gtatools_map_analyzer_folder or '')
        if not folder or not os.path.isdir(folder):
            return None, None, None, T("Укажите существующую папку")
        ides, ipls, imgs = [], [], []
        recursive = bool(s.gtatools_map_analyzer_recursive)
        # Walk once and triage by extension. Recursive flag controls
        # whether subfolders are visited; same flag applies to IMGs.
        if recursive:
            for root_dir, _dirs, files in os.walk(folder):
                for fn in files:
                    low = fn.lower()
                    p = os.path.join(root_dir, fn)
                    if low.endswith('.ide'): ides.append(p)
                    elif low.endswith('.ipl'): ipls.append(p)
                    elif low.endswith('.img') and low not in _NON_STREAMING_IMGS: imgs.append(p)
        else:
            for fn in os.listdir(folder):
                low = fn.lower()
                p = os.path.join(folder, fn)
                if low.endswith('.ide'): ides.append(p)
                elif low.endswith('.ipl'): ipls.append(p)
                elif low.endswith('.img') and low not in _NON_STREAMING_IMGS: imgs.append(p)
        img_files = None
        if s.gtatools_map_analyzer_check_img:
            # FOLDER analyses the chosen folder, independent of another
            # game's root still selected in the scene.
            imgs, loose = _asset_inputs(imgs, folder, scan_folder=folder)
            # Startup lists can also contain cutscene/script archives.
            imgs = [p for p in imgs if os.path.basename(p).lower() not in _NON_STREAMING_IMGS]
            img_files = _gather_img_files(imgs, loose)
        return ides, ipls, img_files, None

    if mode == 'CUSTOM':
        ides = [bpy.path.abspath(it.path) for it in s.gtatools_map_analyzer_custom_ides if it.path]
        ipls = [bpy.path.abspath(it.path) for it in s.gtatools_map_analyzer_custom_ipls if it.path]
        ides = [p for p in ides if os.path.isfile(p)]
        ipls = [p for p in ipls if os.path.isfile(p)]
        if not ides and not ipls:
            return None, None, None, T("Список IDE/IPL пуст — добавь файлы кнопкой '+'")
        img_files = None
        if s.gtatools_map_analyzer_check_img:
            # Walk parent dirs of the IDE/IPL files (and gta_root if
            # set) to auto-find IMGs without making the user specify.
            roots = set()
            for p in (ides + ipls):
                roots.add(os.path.dirname(p))
            game_root = bpy.path.abspath(getattr(s, 'gtatools_game_root', '') or '')
            if game_root and os.path.isdir(game_root):
                roots.add(game_root)
            imgs = []
            for r in roots:
                if not os.path.isdir(r):
                    continue
                for root_dir, _dirs, files in os.walk(r):
                    for fn in files:
                        if fn.lower().endswith('.img'):
                            imgs.append(os.path.join(root_dir, fn))
            imgs, loose = _asset_inputs(imgs, game_root)
            img_files = _gather_img_files(imgs, loose)
        return ides, ipls, img_files, None

    return None, None, None, T("Неизвестный режим input")


def _gather_img_files(img_paths, loose_paths=()):
    """Read entry names from each .img and return ``{archive_path: {names}}``.

    Per-archive dict (rather than flat set) is required so map_lint
    can run the cross-archive shadowing check. Failures are silent —
    bad archives just don't appear in the result. An archive reached
    twice under different spellings (CUSTOM walks the IDE folders AND
    the game root) is read once — else it would shadow itself.
    """
    from ..core.img import ImgReader
    out = {}
    seen = set()
    for path in img_paths:
        key = os.path.normcase(os.path.realpath(path))
        if key in seen:
            continue
        seen.add(key)
        try:
            with ImgReader(path) as reader:      # the directory is read in open()
                out[path] = {e.name.lower() for e in reader.entries}
        except Exception:
            continue
    loose = {os.path.basename(p).lower() for p in loose_paths
             if os.path.isfile(p)}
    if loose:
        out['<loose>'] = loose
    return out


# ── Operators ────────────────────────────────────────────────────

class GTATOOLS_OT_analyze_map(bpy.types.Operator):
    """Cross-reference IDE/IPL files: orphans, conflicts, missing assets"""
    bl_idname = "gtatools.analyze_map"
    bl_label = "INU: Analyze Map"
    bl_options = {'REGISTER'}

    def execute(self, context):
        ides, ipls, img_files, err = _collect_inputs(context)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        wm = context.window_manager
        results = wm.gtatools_map_analyzer_results
        results.clear()
        wm.gtatools_map_analyzer_results_index = 0

        from ..core.map_lint import analyze_files
        from ..core import game_versions as gv
        profile = getattr(context.scene.inu_settings,
                          'gtatools_lint_profile', 'STANDARD')
        game = gv.game_of_scene(context.scene)
        try:
            issues, stats = analyze_files(ides, ipls, img_files,
                                          profile=profile, game=game)
        except Exception as e:
            self.report({'ERROR'}, f"Analyze error: {e}")
            return {'CANCELLED'}

        # Snapshot stats on WM for the panel to read. Multi-line — UI
        # splits on \n and renders each as its own row with tight
        # spacing.
        def _fmt(n):
            return f"{n:,}".replace(',', ' ')   # 14827 → "14 827"
        # Build summary lines. Show LOD chain breakage on its own row
        # only when something's actually broken — otherwise we'd waste
        # a row on "0 битых" for the common clean case. The active
        # game prefix the file row so user can tell at a glance which
        # surface_id_max / model_id_max ceilings were applied.
        _game_label = {'SA': 'San Andreas', 'VC': 'Vice City', 'III': 'GTA III'}.get(game, game)
        lines = [
            f"Игра:     {_game_label}",
            f"Файлы:    IDE {stats.ide_files} • IPL {stats.ipl_files}",
            f"Модели:   {_fmt(stats.defined_models)} опр. • {_fmt(stats.placed_instances)} разм.",
            f"Проблемы: {stats.orphan_placements} сирот • {_fmt(stats.unused_models)} не исп. • {stats.duplicate_ids} дубл.",
        ]
        lod_part = f"{_fmt(stats.lod_pairs)} LOD-пар"
        if stats.lod_chain_broken:
            lod_part += f" • {stats.lod_chain_broken} битых"
        lines.append(f"Прочее:   {stats.interiors_used} interior • {lod_part}")
        wm.gtatools_map_analyzer_stats_summary = '\n'.join(lines)

        for iss in issues:
            item = results.add()
            item.severity = iss.severity
            item.code = iss.code
            item.file = iss.file
            item.where = iss.where
            item.message = iss.message

        n_err = sum(1 for x in issues if x.severity == 'ERROR')
        n_warn = sum(1 for x in issues if x.severity == 'WARN')
        n_info = sum(1 for x in issues if x.severity == 'INFO')
        if not issues:
            self.report({'INFO'}, T("Анализ завершён: проблем не найдено"))
        else:
            self.report({'INFO'},
                f"{T('Анализ карты завершён')}: {n_err} ERROR, {n_warn} WARN, {n_info} INFO")
        return {'FINISHED'}


class GTATOOLS_OT_map_analyzer_add_ide(bpy.types.Operator):
    """Добавить IDE файл в список Custom"""
    bl_idname = "gtatools.map_analyzer_add_ide"
    bl_label = "INU: Add IDE"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.ide', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}
        coll = context.scene.inu_settings.gtatools_map_analyzer_custom_ides
        norm = os.path.normcase(os.path.normpath(self.filepath))
        for existing in coll:
            if os.path.normcase(os.path.normpath(existing.path)) == norm:
                self.report({'INFO'},
                            T("Уже в списке: {0}").format(os.path.basename(self.filepath)))
                return {'CANCELLED'}
        item = coll.add()
        item.path = self.filepath
        return {'FINISHED'}


class GTATOOLS_OT_map_analyzer_add_ipl(bpy.types.Operator):
    """Добавить IPL файл в список Custom"""
    bl_idname = "gtatools.map_analyzer_add_ipl"
    bl_label = "INU: Add IPL"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.ipl', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}
        coll = context.scene.inu_settings.gtatools_map_analyzer_custom_ipls
        norm = os.path.normcase(os.path.normpath(self.filepath))
        for existing in coll:
            if os.path.normcase(os.path.normpath(existing.path)) == norm:
                self.report({'INFO'},
                            T("Уже в списке: {0}").format(os.path.basename(self.filepath)))
                return {'CANCELLED'}
        item = coll.add()
        item.path = self.filepath
        return {'FINISHED'}


class GTATOOLS_OT_map_analyzer_remove_ide(bpy.types.Operator):
    """Удалить запись IDE из Custom списка"""
    bl_idname = "gtatools.map_analyzer_remove_ide"
    bl_label = "INU: Remove IDE"
    bl_options = {'REGISTER', 'INTERNAL'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        coll = context.scene.inu_settings.gtatools_map_analyzer_custom_ides
        if 0 <= self.index < len(coll):
            coll.remove(self.index)
        return {'FINISHED'}


class GTATOOLS_OT_map_analyzer_remove_ipl(bpy.types.Operator):
    """Удалить запись IPL из Custom списка"""
    bl_idname = "gtatools.map_analyzer_remove_ipl"
    bl_label = "INU: Remove IPL"
    bl_options = {'REGISTER', 'INTERNAL'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        coll = context.scene.inu_settings.gtatools_map_analyzer_custom_ipls
        if 0 <= self.index < len(coll):
            coll.remove(self.index)
        return {'FINISHED'}


class GTATOOLS_OT_map_analyzer_clear(bpy.types.Operator):
    """Очистить список результатов"""
    bl_idname = "gtatools.map_analyzer_clear"
    bl_label = "INU: Clear Map Analyzer Results"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        wm = context.window_manager
        wm.gtatools_map_analyzer_results.clear()
        wm.gtatools_map_analyzer_results_index = 0
        wm.gtatools_map_analyzer_stats_summary = ""
        return {'FINISHED'}


class GTATOOLS_OT_map_analyzer_save_report(bpy.types.Operator):
    """Сохранить результаты анализа в .txt"""
    bl_idname = "gtatools.map_analyzer_save_report"
    bl_label = "INU: Save Map Analysis Report"
    bl_options = {'REGISTER'}

    def execute(self, context):
        wm = context.window_manager
        results = wm.gtatools_map_analyzer_results
        if not results:
            self.report({'ERROR'}, T("Нет результатов для сохранения — сначала запустите анализ"))
            return {'CANCELLED'}

        if not bpy.data.filepath:
            self.report({'ERROR'},
                T("Сцена не сохранена — сохраните .blend, отчёт пишется рядом"))
            return {'CANCELLED'}

        report_dir = os.path.dirname(bpy.data.filepath)
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = os.path.join(report_dir, f"inu_map_lint_{ts}.txt")

        n_err = sum(1 for x in results if x.severity == 'ERROR')
        n_warn = sum(1 for x in results if x.severity == 'WARN')
        n_info = sum(1 for x in results if x.severity == 'INFO')

        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(f"INU Tools — Map Cross-Reference Report\n")
                f.write(f"Generated: {ts}\n")
                f.write(f"Stats:     {wm.gtatools_map_analyzer_stats_summary}\n")
                f.write(f"Issues:    {n_err} ERROR, {n_warn} WARN, {n_info} INFO\n")
                f.write("=" * 78 + "\n\n")
                for it in results:
                    f.write(f"[{it.severity}] {it.code}\n")
                    f.write(f"  file:    {it.file}\n")
                    if it.where:
                        f.write(f"  where:   {it.where}\n")
                    f.write(f"  message: {it.message}\n\n")
        except OSError as e:
            self.report({'ERROR'}, f"{e.__class__.__name__}: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"{T('Отчёт сохранён:')} {out_path}")
        return {'FINISHED'}
