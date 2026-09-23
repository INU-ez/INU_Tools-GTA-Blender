# INU_tools.ops.inu_export — combined INU Import / Export operators.
#
# Phase 3 batch 5 (2026-04-26): 3 mega-operators from __init__.py.
#   - INU Import: file-extension-driven dispatch (.dff/.col/.txd/.ide/.ipl)
#   - Export All: bulk DFF+COL+LOD+TXD export to a folder
#   - INU Export: ExportHelper-based unified export with TXD bucketing
#
# Several small helpers (_ide_entry_from_obj, _ipl_entry_from_obj,
# _clean_model_name_ide, _clean_name_typed_ipl, _append_export_report)
# stay in __init__.py — pulled in lazily inside each method since
# loading order makes top-level `from .. import _foo` racy.

import os
import bpy
from bpy.props import (
    BoolProperty, CollectionProperty, EnumProperty, StringProperty,
)
from bpy_extras.io_utils import ImportHelper, ExportHelper

from .. import T
from ..tools.compat import safe_icon, inu_icon
from ..tools.model_utils import is_collision_mesh


# Формат-галочки в диалоге импорта: при переключении пересобираем
# filter_glob, и проводник показывает только выбранные расширения.
_INU_IMPORT_FILTERS = (
    ('f_dff', '*.dff'), ('f_col', '*.col'), ('f_cst', '*.cst'),
    ('f_txd', '*.txd'), ('f_ide', '*.ide'), ('f_ipl', '*.ipl'),
)


def _inu_import_update_filter(self, context):
    parts = [glob for attr, glob in _INU_IMPORT_FILTERS if getattr(self, attr)]
    # Пусто (все галочки сняты) → шаблон, который ничего не сопоставляет,
    # иначе Blender при пустом filter_glob показал бы вообще все файлы.
    glob = ';'.join(parts) if parts else '*.__none__'
    self.filter_glob = glob
    # Blender копирует filter_glob в params файлового браузера ОДИН раз при
    # открытии — смена свойства оператора потом туда не доходит. Колбэк
    # переключения галочки приходит НЕ обязательно в контексте файлового
    # браузера, поэтому ищем его по ВСЕМ окнам и пишем прямо в params +
    # форсим перерисовку, чтобы список перефильтровался сразу.
    wm = getattr(context, 'window_manager', None)
    for win in (wm.windows if wm else ()):
        scr = getattr(win, 'screen', None)
        if scr is None:
            continue
        for area in scr.areas:
            if area.type != 'FILE_BROWSER':
                continue
            for sp in area.spaces:
                if getattr(sp, 'type', '') == 'FILE_BROWSER' and sp.params:
                    try:
                        sp.params.use_filter = True
                        if hasattr(sp.params, 'use_filter_glob'):
                            sp.params.use_filter_glob = True
                        sp.params.filter_glob = glob
                    except Exception:
                        pass
            area.tag_redraw()
    # Запись в params не всегда перестраивает уже загруженный список —
    # форсим file.refresh отложенно (из update-колбэка вызывать оператор
    # нельзя, поэтому через таймер).
    _schedule_file_refresh()


def _schedule_file_refresh():
    def _refresh():
        wm = bpy.context.window_manager
        for win in (wm.windows if wm else ()):
            scr = getattr(win, 'screen', None)
            if scr is None:
                continue
            for area in scr.areas:
                if area.type != 'FILE_BROWSER':
                    continue
                region = next((r for r in area.regions
                               if r.type == 'WINDOW'), None)
                if region is None:
                    continue
                try:
                    with bpy.context.temp_override(window=win, area=area,
                                                   region=region):
                        bpy.ops.file.refresh()
                except Exception:
                    pass
        return None
    try:
        if not bpy.app.timers.is_registered(_refresh):
            bpy.app.timers.register(_refresh, first_interval=0.0)
    except Exception:
        pass


class GTATOOLS_OT_inu_import(bpy.types.Operator, ImportHelper):
    """Импорт GTA SA файлов (.dff/.col/.cst/.txd/.ide/.ipl) с авто-определением формата"""
    bl_idname = "gtatools.inu_import"
    bl_label = "INU: INU Import"
    # Без 'PRESET' — иначе сверху окна появляется строка «Пресеты оператора»,
    # которой нет в диалоге экспорта (Export All): держим вид одинаковым.
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".dff"
    filter_glob: StringProperty(
        default="*.dff;*.col;*.cst;*.txd;*.ide;*.ipl",
        options={'HIDDEN'}
    )

    # Фильтр-галочки форматов (см. _inu_import_update_filter).
    f_dff: BoolProperty(name="DFF", default=True, update=_inu_import_update_filter)
    f_col: BoolProperty(name="COL", default=True, update=_inu_import_update_filter)
    f_cst: BoolProperty(name="CST", default=True, update=_inu_import_update_filter)
    f_txd: BoolProperty(name="TXD", default=True, update=_inu_import_update_filter)
    f_ide: BoolProperty(name="IDE", default=True, update=_inu_import_update_filter)
    f_ipl: BoolProperty(name="IPL", default=True, update=_inu_import_update_filter)

    import_2dfx: BoolProperty(
        name=T("Импортировать 2DFX"),
        description=T("Создавать пустышки-эффекты 2DFX из DFF (лампы/короны, "
                      "частицы, ped attractor, sun glare, знаки и т.д.). "
                      "Выключи, чтобы импортировать модель без эффектов"),
        default=True)

    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')

    # Modal-loop state (mirrors _DFFImportModalMixin): the whole import
    # used to run inside one blocking execute(), so Blender showed "Not
    # Responding" for the entire parse+build of a heavy DFF with no
    # progress bar and no way to cancel — read by the user as a hang,
    # especially when «All» is fired on a lone .dff. Now the per-file work
    # is a generator driven from a timer modal: UI stays live, ESC aborts.
    _timer = None
    _gen = None
    _stats: dict = None

    def draw(self, context):
        """File-browser sidebar for «Import All».

        Import All — чистый диспетчер: импортирует РОВНО выбранные файлы,
        каждый по своему типу. Авто-подтягивания TXD/LOD/COL по имени тут
        нет (нужен TXD — отметь .txd в списке), поэтому и тумблера «Авто
        TXD» здесь нет: он управляет авто-TXD в Import DFF / drag-drop, а
        не тут."""
        # Тот же слитый box-стиль, что и в диалоге экспорта: верхний бокс —
        # игра + форматы, ниже — бокс опций импорта, ниже — подсказки.
        layout = self.layout
        scn = context.scene
        col = layout.column(align=True)

        # ── Верхний бокс: игра импорта + форматы (как в экспорте) ──
        top = col.box()
        top.label(text=T("Импорт из игры:"))
        # Две строки, как в экспорте: сверху Auto, снизу SA | VC | III
        # (ряд игр гаснет, когда Auto включён).
        g = top.column(align=True)
        g.row(align=True).prop(scn.inu_settings, "gtatools_import_auto_game",
                               text="Auto", toggle=True)
        # Платформа (PC | Mobile) — отдельным рядом МЕЖДУ Auto и версиями
        # игр, как в шапке N-панели. Не гаснет с Auto (платформа независима).
        g.row(align=True).prop(scn.inu_settings, "gtatools_platform",
                               expand=True)
        grow = g.row(align=True)
        grow.enabled = not scn.inu_settings.gtatools_import_auto_game
        grow.prop(scn.inu_settings, "gtatools_import_game", expand=True)
        top.label(text=T("Показывать форматы:"))
        # Кнопки-тумблеры в два ряда: DFF COL CST / TXD IDE IPL.
        r1 = top.row(align=True)
        r1.prop(self, "f_dff", text="DFF", toggle=True)
        r1.prop(self, "f_col", text="COL", toggle=True)
        r1.prop(self, "f_cst", text="CST", toggle=True)
        r2 = top.row(align=True)
        r2.prop(self, "f_txd", text="TXD", toggle=True)
        r2.prop(self, "f_ide", text="IDE", toggle=True)
        r2.prop(self, "f_ipl", text="IPL", toggle=True)

        # ── Бокс опций DFF (только когда DFF в выборке) ──
        # weld-тумблер — как в Import DFF / drag-drop (AddonPreferences,
        # глобально). 2DFX — импортировать ли эффекты (лампы/короны/частицы).
        if self.f_dff:
            box = col.box()
            from ..tools.user_data import get_addon_prefs
            _prefs = get_addon_prefs()
            if _prefs is not None:
                box.prop(_prefs, "import_weld_sharpen",
                         text=T("Стандартная модель GTA SA (vanilla)"))
                if not _prefs.import_weld_sharpen:
                    box.label(text=T("Кастом: связать + сохранить заборы"),
                              **inu_icon(safe_icon('INFO')))
            box.prop(self, "import_2dfx")

        # ── Подсказки ──
        info = col.box().column(align=True)
        info.scale_y = 0.85
        info.label(text=T("Импортируются только выбранные файлы"),
                   **inu_icon(safe_icon('INFO')))
        info.label(text=T(".dff .col .cst .txd .ide .ipl — каждый по своему типу"))
        info.label(text=T("Нужны текстуры — выдели .txd в списке"))

    def check(self, context):
        # Signal Blender to redraw/re-filter when a format toggle changes.
        return True

    def execute(self, context):
        file_list = [f.name for f in self.files if f.name] or [os.path.basename(self.filepath)]
        directory = self.directory or os.path.dirname(self.filepath)

        # Import order: TXD first (so a selected .txd loads before the
        # selected .dff and the DFF's materials pick up its images), then
        # DFF, COL, IDE, IPL.
        order = {'.txd': 0, '.dff': 1, '.col': 2, '.cst': 3, '.ide': 4, '.ipl': 5}
        file_list.sort(key=lambda n: order.get(os.path.splitext(n)[1].lower(), 99))

        from .dff_import import _init_import_stats
        self._stats = _init_import_stats({})
        self._gen = self._iter_import(file_list, directory, context, self._stats)

        wm = context.window_manager
        wm.progress_begin(0, 100)
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(T("INU Import: подготовка..."))
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC':
            self._finish(context)
            self.report({'WARNING'}, T("INU Import отменён"))
            return {'CANCELLED'}
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        import time
        wm = context.window_manager
        deadline = time.monotonic() + 0.05  # ~20 fps frame budget
        while time.monotonic() < deadline:
            try:
                current, total, label = next(self._gen)
            except StopIteration:
                self._finish(context)
                return self._report_done()
            except Exception as e:
                self._finish(context)
                self.report({'ERROR'}, f"INU Import: {e}")
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}
            wm.progress_update(int(100 * current / max(total, 1)))
            context.workspace.status_text_set(
                f"INU Import: {current}/{total} — {label}")
        return {'RUNNING_MODAL'}

    def _iter_import(self, file_list, directory, context, stats):
        """«Import All» as a generator yielding ``(current, total, label)``.

        PURE DISPATCHER: imports EXACTLY the files the user ticked in the
        browser, each through its own raw importer by extension. No
        name-based auto-pull of LOD/COL/TXD siblings — if the user wants a
        TXD/COL/LOD, they select it in the list. (DFF still goes through
        the shared ``import_dff`` core; the auto-TXD wrapper is reserved
        for Import DFF / drag-drop.)"""
        from .dff_import import import_dff as inu_import_dff
        from .col_import import import_col as inu_import_col
        from .txd_import import import_txd as inu_import_txd
        from .ide_import import import_ide as inu_import_ide
        from .ipl_import import import_ipl as inu_import_ipl
        from .cst_import import import_cst as inu_import_cst

        # One COL material cache shared across every .col in the batch —
        # vanilla COL uses only ~64 distinct surfaces, so without this each
        # file's faces would each spawn a fresh COL_N material datablock.
        col_material_cache = {}

        total = max(len(file_list), 1)
        for idx, fname in enumerate(file_list):
            fpath = os.path.join(directory, fname)
            ext = os.path.splitext(fname)[1].lower()
            yield (idx, total, fname)
            try:
                if ext == '.dff':
                    inu_import_dff(filepath=fpath, context=context,
                                   skip_2dfx=not self.import_2dfx)
                    stats['imported'] += 1
                    # Игра модели: принудительно из селектора или авто по RW —
                    # переключает режим сцены (на свежей сцене; готовый проект
                    # защищён внутри maybe_set_game_from_import).
                    try:
                        from ..core import game_versions as gv
                        s = context.scene.inu_settings
                        if s.gtatools_import_auto_game:
                            det = gv.detect_game_from_dff(fpath)
                        else:
                            det = s.gtatools_import_game
                        gv.maybe_set_game_from_import(context.scene, det)
                    except Exception:
                        pass
                elif ext == '.col':
                    inu_import_col(filepath=fpath, context=context,
                                   material_cache=col_material_cache)
                    stats['col_loaded'] += 1
                elif ext == '.cst':
                    created = inu_import_cst(filepath=fpath)
                    stats['col_loaded'] += 1
                    stats['infos'].append(f"{fname} ({len(created)} CST)")
                elif ext == '.txd':
                    images = inu_import_txd(filepath=fpath)
                    stats['txd_loaded'] += 1
                    stats['infos'].append(f"{fname} ({len(images)} tex)")
                elif ext == '.ide':
                    matched = inu_import_ide(filepath=fpath, context=context)
                    stats['infos'].append(f"{fname} ({len(matched)} matched)")
                elif ext == '.ipl':
                    placed = inu_import_ipl(filepath=fpath, context=context)
                    stats['infos'].append(f"{fname} ({len(placed)} placed)")
                else:
                    stats['errors'].append((fname, "unsupported extension"))
            except Exception as e:
                stats['errors'].append((fname, str(e)))

        # ── Final pass: alpha-link for all materials ──────────────────
        # Standalone .txd selected in the same batch may load BEFORE a DFF
        # creates its materials; re-run alpha-link once at the end when
        # both images and materials coexist. (import_one_dff already
        # alpha-links its own auto-TXD, so this only catches standalone
        # TXD + DFF combinations — idempotent either way.)
        if stats['txd_loaded']:
            yield (total, total, T("связывание альфы..."))
            print(f"[INU Import] post-import alpha-link pass: "
                  f"{len(bpy.data.materials)} materials in scene")
            from .texture_ops import (
                link_material_alpha_if_textured, clear_alpha_cache)
            clear_alpha_cache()  # каждую текстуру сканируем один раз за пасс
            n_changed = 0
            seen = set()
            all_mats = list(bpy.data.materials)
            for obj in bpy.data.objects:
                if obj.type != 'MESH':
                    continue
                for slot in obj.material_slots:
                    if slot.material and id(slot.material) not in seen:
                        seen.add(id(slot.material))
                        if slot.material not in all_mats:
                            all_mats.append(slot.material)
            for m in all_mats:
                if link_material_alpha_if_textured(m):
                    n_changed += 1
            print(f"[INU Import] alpha-link done: changed={n_changed} of {len(all_mats)} materials")

        yield (total, total, T("готово"))

    def _report_done(self):
        stats = self._stats or {}
        imported = stats.get('imported', 0)
        txd = stats.get('txd_loaded', 0)
        col = stats.get('col_loaded', 0)
        errors = stats.get('errors', [])
        for w in stats.get('warnings', []):
            self.report({'WARNING'}, w)
        if errors and not (imported or txd or col):
            self.report({'ERROR'},
                        '; '.join(f"{n}: {e}" for n, e in errors[:3]))
            return {'CANCELLED'}
        parts = []
        if imported:
            parts.append(f"DFF: {imported}")
        if txd:
            parts.append(f"TXD: {txd}")
        if col:
            parts.append(f"COL: {col}")
        if errors:
            parts.append(f"{len(errors)} {T('с ошибкой')}")
        self.report({'INFO'},
                    f"INU Import — {', '.join(parts) if parts else T('ничего')}")
        return {'FINISHED'}

    def _finish(self, context):
        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        try:
            context.window_manager.progress_end()
        except Exception:
            pass
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass
        self._gen = None


def menu_func_import(self, context):
    self.layout.operator(GTATOOLS_OT_inu_import.bl_idname,
                         text="INU Import (.dff/.col/.cst/.txd/.ide/.ipl)")


# ──────────────────── Shared group-export engine ─────────────────────
#
# ONE selection→groups→files engine behind Export All AND the single-
# format ops (Export DFF / Export LOD). Every entry point routes objects
# to the SAME core writers (`export_dff`/`export_col`/`export_txd`) by the
# SAME name-based grouping (`get_model_type`). The only difference between
# "Export DFF", "Export LOD" and "Export All" is which skip_* flags are
# set — mirroring how the import side funnels everything through one core.


def _write_txd_file(txd_path, context, backend, merge):
    """Write/merge a TXD. When ``merge`` and the file already exists, the
    scene's textures are ADDED/UPDATED into it while every other texture in
    the file (from other models) is kept — otherwise the file is fully
    overwritten. Returns export_txd's ``(result, message, transparent)``."""
    from ..tools.txd_export import export_txd
    if merge and os.path.isfile(txd_path):
        from ..tools.txd_export import update_txd
        return update_txd(txd_path, context, selected_only=True, backend=backend)
    return export_txd(txd_path, context, selected_only=True, backend=backend)


def _export_model_group(context, directory, base_name, models,
                        skip_dff, skip_col, skip_lod, skip_txd,
                        backend, tri_warnings, skip_cst=True,
                        empty_col=False, txd_merge=False, txd_notes=None):
    """Export ONE model group (DFF + LOD + COL + TXD) into ``directory``,
    one file per format named from ``base_name``.

    DFF/geometry flags come straight from each object's ``obj.inu.*`` (the
    N-panel DFF Flags) — no separate export override. ``tri_warnings`` is
    appended to in-place with non-fatal high-triangle-count warnings."""
    exported = []
    errors = []

    # DFF (GTA SA RW version)
    if models['DFF'] and not skip_dff:
        dff_path = os.path.join(directory, f"{base_name}.dff")
        try:
            from .dff_export import export_dff as inu_export_dff, _resolve_export_version
            rw_ver = _resolve_export_version(context)
            tp = getattr(context.scene.inu_settings, 'gtatools_platform', 'PC')
            # Collect mesh + attached 2DFX child empties.
            dff_objects = [models['DFF']]
            for child in models['DFF'].children:
                if child.type == 'EMPTY' and getattr(child, 'inu', None) and child.inu.type == '2DFX':
                    dff_objects.append(child)
            inu_export_dff(filepath=dff_path, objects=dff_objects,
                           version=rw_ver, target_platform=tp)
            from ..core.dff import DFF_EXPORT_WARNINGS
            tri_warnings.extend(DFF_EXPORT_WARNINGS)
            exported.append(f"{base_name}.dff")
        except Exception as e:
            errors.append(f"{base_name}.dff: {str(e)}")

    # LOD (LOD-prefixed filename, RW version from scene)
    if models['LOD'] and not skip_lod:
        lod_path = os.path.join(directory, f"LOD{base_name}.dff")
        try:
            from .dff_export import export_dff as inu_export_dff, _resolve_export_version
            rw_ver = _resolve_export_version(context)
            tp = getattr(context.scene.inu_settings, 'gtatools_platform', 'PC')
            inu_export_dff(filepath=lod_path, objects=[models['LOD']],
                           version=rw_ver, target_platform=tp)
            from ..core.dff import DFF_EXPORT_WARNINGS
            tri_warnings.extend(DFF_EXPORT_WARNINGS)
            exported.append(f"LOD{base_name}.dff")
        except Exception as e:
            errors.append(f"LOD{base_name}.dff: {str(e)}")

    # COL / CST: normally driven by the group's COL mesh. In empty mode
    # we write a geometry-less record for the whole group (named from
    # base_name) even when there's no COL mesh — that's the point: a
    # model that needs a COL entry bound to it but no collision.
    col_obj = models['COL']
    col_present = col_obj is not None

    # COL (GTA SA COL3) — always written at origin, transform restored.
    if (col_present or empty_col) and not skip_col:
        col_path = os.path.join(directory, f"{base_name}.col")
        original_col_loc = col_obj.location.copy() if col_present else None
        try:
            from .col_export import export_col as inu_export_col, _resolve_col_version
            if col_present and not empty_col:
                col_obj.location = (0, 0, 0)
            # Empty COL → bounds from the visual model so GTA doesn't cull it.
            _bref = None
            if empty_col:
                _vis = models['DFF'] or models['LOD']
                _bref = [_vis] if _vis else None
            inu_export_col(
                filepath=col_path,
                objects=[col_obj] if col_present else [],
                version=_resolve_col_version(context),
                model_name=base_name,
                empty=empty_col,
                bounds_ref=_bref,
            )
            exported.append(f"{base_name}.col")
        except Exception as e:
            errors.append(f"{base_name}.col: {str(e)}")
        finally:
            if col_present and original_col_loc is not None:
                col_obj.location = original_col_loc

    # CST (collision as Collision File Editor II text format) — same COL
    # mesh as the .col, written at origin with the transform restored.
    if (col_present or empty_col) and not skip_cst:
        cst_path = os.path.join(directory, f"{base_name}.cst")
        original_cst_loc = col_obj.location.copy() if col_present else None
        try:
            from .cst_export import export_cst as inu_export_cst
            from .col_export import _resolve_col_version
            if col_present and not empty_col:
                col_obj.location = (0, 0, 0)
            inu_export_cst(
                filepath=cst_path,
                objects=[col_obj] if col_present else [],
                version=_resolve_col_version(context),
                model_name=base_name,
                empty=empty_col,
            )
            exported.append(f"{base_name}.cst")
        except Exception as e:
            errors.append(f"{base_name}.cst: {str(e)}")
        finally:
            if col_present and original_cst_loc is not None:
                col_obj.location = original_cst_loc

    # TXD (textures from DFF + LOD into one archive per model)
    if (models['DFF'] or models['LOD']) and not skip_txd:
        txd_path = os.path.join(directory, f"{base_name}.txd")
        prev_active = context.view_layer.objects.active
        prev_selected = [o for o in context.selected_objects]
        try:
            bpy.ops.object.select_all(action='DESELECT')
            if models['DFF']:
                models['DFF'].select_set(True)
                context.view_layer.objects.active = models['DFF']
            if models['LOD']:
                models['LOD'].select_set(True)
                if not models['DFF']:
                    context.view_layer.objects.active = models['LOD']
            result, message, _ = _write_txd_file(
                txd_path, context, backend, txd_merge)
            if result == {'FINISHED'}:
                exported.append(f"{base_name}.txd")
                # merge → update_txd вернул счётчики текстур (обновлено/
                # добавлено/всего); показываем их пользователю вместо
                # безликого «N файлов».
                if txd_merge and txd_notes is not None and message:
                    txd_notes.append(f"{base_name}.txd: {message}")
            elif 'No textures' in (message or ''):
                # У модели нет ни одной текстуры → .txd не создаётся. Для
                # коллизии/пустого меша это норма, но для обычной модели чаще
                # значит «забыл текстуру» — сообщаем, чтобы не гадать, почему в
                # игре модель без текстуры / «не экспортнулась».
                if txd_notes is not None:
                    txd_notes.append(
                        T("{0}: без текстуры — TXD не создан (добавь текстуру, "
                          "если модель должна быть текстурной)").format(base_name))
            else:
                errors.append(f"{base_name}.txd: {message}")
        except Exception as e:
            errors.append(f"{base_name}.txd: {str(e)}")
        finally:
            bpy.ops.object.select_all(action='DESELECT')
            for o in prev_selected:
                o.select_set(True)
            if prev_active is not None:
                context.view_layer.objects.active = prev_active

    return exported, errors


def run_group_export(context, directory, *, skip_dff, skip_col, skip_lod,
                     skip_txd, skip_cst=True, col_library=False,
                     col_library_name='collision', txd_shared=False,
                     txd_shared_name='textures', backend='numpy',
                     empty_col=False, txd_merge=False, name_override=''):
    """Find selected model groups and export them into ``directory``.

    THE shared engine: same name-based grouping, same core writers, same
    prelight handling for Export All / Export DFF / Export LOD — the caller
    only chooses which formats to skip. Returns
    ``(exported, errors, tri_warnings, txd_notes, num_groups)``;
    ``num_groups == 0`` means nothing was selected. ``txd_notes`` holds the
    per-file «обновлено/добавлено/всего» текстур lines when merging."""
    from ..tools.model_utils import find_all_selected_model_groups
    from ..tools.prelight import setup_prelight_preview
    from ..tools.txd_export import clear_dxt_cache

    # Сбрасываем кэш закодированных DXT перед каждым ручным экспортом: его
    # ключ (session_uid + размер) НЕ ловит правки пикселей «на месте», иначе
    # после редактирования текстуры в TXD уходит старая (закэшированная)
    # версия. Один сброс на нажатие — внутри прогона кэш ещё дедуплицирует.
    clear_dxt_cache()

    model_groups = find_all_selected_model_groups()
    if not model_groups:
        return [], [], [], 0

    # Клик по файлу в браузере задаёт базовое имя экспорта. Применимо только
    # к ОДНОЙ модели (одно имя на несколько групп не натянуть) — иначе
    # оставляем имена по моделям.
    if name_override and len(model_groups) == 1:
        _only = next(iter(model_groups.values()))
        model_groups = {name_override: _only}

    # Disable prelight preview on the meshes about to be exported.
    prelight_was_on = set()
    for base_name, models in model_groups.items():
        for model_type in ('DFF', 'LOD', 'COL'):
            obj = models[model_type]
            if obj and obj.type == 'MESH':
                for mat_slot in obj.material_slots:
                    mat = mat_slot.material
                    if mat and mat.use_nodes and mat.node_tree.nodes.get("Prelight_Mix"):
                        prelight_was_on.add(obj)
                        setup_prelight_preview(obj, enable=False)
                        break

    all_exported = []
    all_errors = []
    tri_warnings = []
    txd_notes = []
    wm = context.window_manager

    # Library COL / shared TXD divert per-group writes into one combined
    # file written after the loop; DFF/LOD still go per-group.
    library_col_objects = []
    if col_library and not skip_col:
        skip_col = True
        for _base, _models in model_groups.items():
            if _models['COL']:
                library_col_objects.append(_models['COL'])

    shared_txd_objects = []
    if txd_shared and not skip_txd:
        skip_txd = True
        for _base, _models in model_groups.items():
            if _models['DFF']:
                shared_txd_objects.append(_models['DFF'])
            if _models['LOD']:
                shared_txd_objects.append(_models['LOD'])

    def _group_steps(models):
        has_col = bool(models['COL']) or empty_col
        return sum([
            1 if models['DFF'] and not skip_dff else 0,
            1 if models['LOD'] and not skip_lod else 0,
            1 if has_col and not skip_col else 0,
            1 if has_col and not skip_cst else 0,
            1 if (models['DFF'] or models['LOD']) and not skip_txd else 0,
        ])

    total_steps = sum(_group_steps(m) for m in model_groups.values())
    current_step = 0
    wm.progress_begin(0, max(total_steps, 1))
    context.workspace.status_text_set(T("Экспорт..."))
    try:
        for group_idx, (base_name, models) in enumerate(model_groups.items()):
            wm.progress_update(current_step)
            context.workspace.status_text_set(
                f"{T('Экспорт:')} {group_idx + 1}/{len(model_groups)} {base_name}")
            exported, errors = _export_model_group(
                context, directory, base_name, models,
                skip_dff, skip_col, skip_lod, skip_txd, backend, tri_warnings,
                skip_cst=skip_cst, empty_col=empty_col, txd_merge=txd_merge,
                txd_notes=txd_notes)
            all_exported.extend(exported)
            all_errors.extend(errors)
            current_step += _group_steps(models)

        # Library COL — one multi-entry .col from every group's COL mesh.
        if col_library and library_col_objects:
            from .col_export import export_col_library, _resolve_col_version
            lib_path = os.path.join(directory, f"{col_library_name}.col")
            original_locations = {}
            try:
                for obj in library_col_objects:
                    original_locations[obj.name] = obj.location.copy()
                    obj.location = (0, 0, 0)
                count = export_col_library(lib_path, library_col_objects,
                                           version=_resolve_col_version(context),
                                           empty=empty_col)
                all_exported.append(f"{col_library_name}.col ({count} records)")
            except Exception as e:
                all_errors.append(f"{col_library_name}.col: {e}")
            finally:
                for obj in library_col_objects:
                    if obj.name in original_locations:
                        obj.location = original_locations[obj.name]

        # Shared TXD — every texture from every exported mesh into one file.
        if txd_shared and shared_txd_objects:
            shared_path = os.path.join(directory, f"{txd_shared_name}.txd")
            prev_active = context.view_layer.objects.active
            prev_selected = [o for o in context.selected_objects]
            try:
                bpy.ops.object.select_all(action='DESELECT')
                for src in shared_txd_objects:
                    src.select_set(True)
                context.view_layer.objects.active = shared_txd_objects[0]
                result, message, _ = _write_txd_file(
                    shared_path, context, backend, txd_merge)
                if result == {'FINISHED'}:
                    all_exported.append(
                        f"{txd_shared_name}.txd ({len(shared_txd_objects)} models)")
                    if txd_merge and message:
                        txd_notes.append(f"{txd_shared_name}.txd: {message}")
                else:
                    all_errors.append(f"{txd_shared_name}.txd: {message}")
            except Exception as e:
                all_errors.append(f"{txd_shared_name}.txd: {e}")
            finally:
                bpy.ops.object.select_all(action='DESELECT')
                for o in prev_selected:
                    o.select_set(True)
                if prev_active is not None:
                    context.view_layer.objects.active = prev_active
    finally:
        wm.progress_end()
        context.workspace.status_text_set(None)
        for obj in prelight_was_on:
            setup_prelight_preview(obj, enable=True)

    return all_exported, all_errors, tri_warnings, txd_notes, len(model_groups)


def _report_group_export(op, exported, errors, tri_warnings, num_groups,
                         txd_notes=None):
    """Shared operator reporting for the group-export engine."""
    if num_groups == 0:
        op.report({'ERROR'}, T("Выделите модели для экспорта!"))
        return {'CANCELLED'}
    if exported:
        op.report({'INFO'},
                  f"{T('Экспортировано:')} {len(exported)}"
                  f"{T(' файлов (')}{num_groups}{T(' моделей)')}")
    # При «Дописать в существующий TXD» — сколько текстур обновлено/добавлено.
    for note in (txd_notes or []):
        op.report({'INFO'}, note)
    if errors:
        preview = '; '.join(errors[:5])
        more = f" (+{len(errors) - 5})" if len(errors) > 5 else ""
        op.report({'WARNING'}, f"{T('Ошибки:')} {preview}{more}")
    for w in dict.fromkeys(tri_warnings):  # dedup, keep order
        op.report({'WARNING'}, w)
    return {'FINISHED'}


def _upsert_ide_ipl_objects(op, context, objs, ide_path='', ipl_path=''):
    """Write *objs* (+ their LODs) into the given IDE / IPL through the same
    sync rules as the IDE/IPL «Add» buttons (ops/map_link): rows found by
    content, each placement with its own LOD row, id conflicts reported.
    Returns short notes like «IDE: добавлено 2» for the export summary."""
    from . import map_link
    notes = []
    for kind, path, fn in (("IDE", ide_path, map_link.ide_write),
                           ("IPL", ipl_path, map_link.ipl_write)):
        if not path:
            continue
        try:
            rep = fn(context, objs, picked=path)
        except Exception as e:                              # noqa: BLE001
            notes.append(f"{kind} err: {e}")
            continue
        for level, text in rep.problems():
            op.report({level}, text)
        notes.append(map_link.summary(kind, rep))
        from .textdata_audit import audit_ide_file, audit_ipl_file
        for f in sorted(rep.files):
            if kind == "IDE":
                audit_ide_file(op, f)
            else:
                audit_ipl_file(op, f, context)
    return notes


def run_single_dff_export(context, directory, name_override='', *,
                          want_dff=True, want_txd=True, want_col=True,
                          backend='numpy', txd_merge=False):
    """Один DFF: вся выделенная иерархия (машина / пед / любая
    многокомпонентная модель) → ОДИН .dff. TXD (если включён) → один общий
    .txd; коллизия встраивается ВНУТРЬ .dff.

    Общий движок для «Экспорт всех выделенных» и INU Export — оба зовут эту
    функцию, чтобы результат был байт-в-байт одинаковым. Возвращает
    ``(out, errors, root, dropped)``; ``out is None`` — экспортировать нечего.
    """
    s = context.scene.inu_settings   # нужен только для платформы
    # Машине/педу нужен ОДИН root-фрейм. Берём корень = самый верхний
    # предок КРУПНЕЙШЕГО выделенного меша (кузова) и экспортируем всю его
    # иерархию. Так отсекаются посторонние верхнеуровневые объекты
    # (light-маркеры, пустышки, остатки): иначе они уходят в клапм как
    # фантомные root-фреймы и ломают машину — настоящий root перестаёт
    # быть кадром 0, камера и текстуры съезжают. Достаточно выделить любую
    # часть машины (или корень) — иерархия соберётся сама.
    picked = list(context.selected_objects)
    meshes0 = [o for o in picked if o.type == 'MESH']
    if not meshes0:
        return None, [T("Нет меш объектов для экспорта")], None, 0
    root = max(meshes0, key=lambda o: len(o.data.vertices))
    while root.parent is not None:
        root = root.parent
    sel, stack = [root], [root]
    while stack:
        o = stack.pop()
        for ch in o.children:
            sel.append(ch)
            stack.append(ch)
    # Collision objects live OUTSIDE the vehicle root subtree: the importer
    # creates the COL/SHA meshes AND the sphere/box primitives (SPHERE/CUBE
    # empties) all top-level and unparented. Gather the WHOLE set so the
    # complete collision embeds — пропустить сферы = машина проезжает сквозь
    # модели. Лишних фреймов они не добавят: _collect_frame_objects
    # пропускает COL/SHA-меши и сфера/бокс-empties.
    import re
    sel_set = set(sel)
    picked_set = set(picked)
    meshes0_set = set(meshes0)
    # 1) COL/SHA меши (top-level или выделенные) — запоминаем их имена
    col_mesh_names = []
    for o in context.scene.objects:
        if (o.type == 'MESH' and o not in sel_set
                and is_collision_mesh(o)
                and (o.parent is None or o in meshes0_set)):
            sel.append(o)
            sel_set.add(o)
            col_mesh_names.append(o.name)
    # 2) сфера/бокс-empties коллизии: отрезаем `_sphere_N`/`_box_N` от имени
    # и проверяем, что остаток — префикс имени одного из COL-мешей (импорт
    # называет их `<model>_sphere_N` рядом с `<model>_col`).
    def _owner(nm):
        m = re.match(r'^(.*)_(?:sphere|box)_\d+$', nm)
        return m.group(1) if m else nm
    for o in context.scene.objects:
        if (o.type == 'EMPTY' and o not in sel_set
                and getattr(o, 'empty_display_type', '') in ('SPHERE', 'CUBE')
                and (o.parent is None or o in picked_set)):
            base_e = _owner(o.name)
            if (not col_mesh_names
                    or any(cn.startswith(base_e) for cn in col_mesh_names)):
                sel.append(o)
                sel_set.add(o)
    dropped = sum(1 for o in picked if o not in sel_set)
    meshes = [o for o in sel if o.type == 'MESH']
    name = (name_override or getattr(root, 'name', '') or 'model')
    tp = getattr(s, 'gtatools_platform', 'PC')
    out, errors = [], []

    if want_dff:
        try:
            from .dff_export import (export_dff as inu_export_dff,
                                     _resolve_export_version)
            inu_export_dff(
                filepath=os.path.join(directory, name + '.dff'),
                objects=sel, version=_resolve_export_version(context),
                target_platform=tp)
            out.append(name + '.dff')
        except Exception as e:
            errors.append(f"{name}.dff: {e}")

    if want_txd:
        # TXD пишем из ТЕХ ЖЕ мешей, что и DFF (а не из текущего выделения,
        # которое export_txd берёт через selected_only) — иначе текстуры
        # берутся не из тех объектов. Временно выделяем meshes и
        # восстанавливаем выделение после.
        prev_sel = list(context.selected_objects)
        prev_active = context.view_layer.objects.active
        try:
            bpy.ops.object.select_all(action='DESELECT')
            for o in meshes:
                o.select_set(True)
            context.view_layer.objects.active = meshes[0]
            merge = bool(txd_merge)
            r, msg, _ = _write_txd_file(
                os.path.join(directory, name + '.txd'), context,
                getattr(s, 'gtatools_dxt_backend', 'numpy'), merge)
            if r == {'FINISHED'}:
                # merge → показать счётчики текстур вместо просто имени.
                out.append(f"{name}.txd ({msg})" if (merge and msg)
                           else name + '.txd')
            else:
                errors.append(f"{name}.txd: {msg}")
        except Exception as e:
            errors.append(f"{name}.txd: {e}")
        finally:
            bpy.ops.object.select_all(action='DESELECT')
            for o in prev_sel:
                try:
                    o.select_set(True)
                except Exception:
                    pass
            context.view_layer.objects.active = prev_active

    # COL: НЕ пишем отдельный .col. У машины/педа коллизия встраивается
    # ВНУТРЬ .dff (CHUNK_COLLISION_MODEL) — export_dff делает это сам, если
    # среди выделенных есть COL-меш (obj.inu.type == COL/SHA). Имя
    # встроенной коллизии = имя .dff.
    has_col = (any(is_collision_mesh(o) for o in meshes)
               or any(o.type == 'EMPTY'
                      and getattr(o, 'empty_display_type', '') in ('SPHERE', 'CUBE')
                      for o in sel))
    if has_col:
        out.append(name + '.dff (+collision)')
    elif want_col:
        # Пользователь просил COL, но COL-меша нет → коллизия НЕ встроена,
        # машина будет проезжать сквозь модели. Явно предупреждаем.
        errors.append(T("COL-меш не найден — коллизия не встроена в .dff"))

    return out, errors, root, dropped


def _report_single_dff(op, out, errors, root, dropped):
    """Отчёт оператора для run_single_dff_export (общий для обоих экспортов)."""
    if not out:
        op.report({'ERROR'}, T("Ничего не экспортировано")
                  + ((": " + "; ".join(errors[:3])) if errors else ""))
        return {'CANCELLED'}
    tail = ""
    if dropped:
        tail += f" | {T('вне иерархии корня, пропущено объектов')}: {dropped}"
    if errors:
        tail += " | " + "; ".join(errors[:2])
    op.report({'WARNING'} if (errors or dropped) else {'INFO'},
              f"{T('Экспортировано:')} {', '.join(out)} "
              f"({T('корень')}: {getattr(root, 'name', '?')}){tail}")
    return {'FINISHED'}


class GTATOOLS_OT_export_all(bpy.types.Operator):
    """Экспорт всех выделенных моделей (DFF + COL + LOD + TXD)"""
    bl_idname = "gtatools.export_all"
    bl_label = "INU: Export All (DFF+COL+LOD+TXD)"
    bl_options = {'REGISTER'}

    directory: StringProperty(subtype='DIR_PATH')
    # Клик по файлу в браузере заполняет это поле (а не только папку). Если
    # выбран .txd — текстуры всех моделей пишутся именно в него (merge при
    # включённой галочке). Для папочного экспорта по моделям остаётся пустым.
    filename: StringProperty(subtype='FILE_NAME')
    # Фильтр расширений браузера: галочки форматов (DFF/COL/LOD/TXD/CST)
    # сужают список файлов. Начальное значение ставим в invoke по текущим
    # настройкам, дальше его живьём пересобирает _export_all_filter_update.
    filter_glob: StringProperty(default="", options={'HIDDEN'})
    to_img: BoolProperty(
        name="All → IMG",
        description=T("Экспортировать прямо в .img архив, путь к которому "
                      "задан в настройках аддона. Выбор папки при этом "
                      "игнорируется"),
        default=False)

    def invoke(self, context, event):
        # Имя экспорта из ВЫДЕЛЕННОЙ модели. Считаем ЗДЕСЬ (в 3D-контексте, где
        # есть selected_objects — в draw файлового браузера их уже нет) и
        # храним в self._export_name / self._n_groups для draw. Имя также
        # кладём в поле имени файла внизу. Несколько групп одним именем не
        # назвать → имя пустое, имена пишутся по моделям.
        name = ''
        n_groups = 0
        try:
            from ..tools.model_utils import (find_all_selected_model_groups,
                                             get_model_type)
            groups = find_all_selected_model_groups()
            n_groups = len(groups)
            if n_groups == 1:
                name = next(iter(groups.keys()))
            elif n_groups == 0:
                # Фолбэк: активный/первый выделенный объект без суффикса
                # (_DFF/_LOD/_COL/.00x) — на случай, если группировка не
                # распознала объект.
                ao = context.active_object or (
                    context.selected_objects[0]
                    if context.selected_objects else None)
                if ao is not None:
                    _t, base = get_model_type(ao)
                    name = (base or ao.name).rstrip('_')
                    if name:
                        n_groups = 1
        except Exception:
            pass
        self._n_groups = n_groups
        self._export_name = name
        if name:
            self.filename = name
        # Начальный фильтр браузера по включённым форматам (LOD тоже .dff).
        s = context.scene.inu_settings
        parts = []
        for flag, glob in (
            (s.gtatools_export_all_dff, '*.dff'),
            (s.gtatools_export_all_lod, '*.dff'),
            (s.gtatools_export_all_col, '*.col'),
            (s.gtatools_export_all_txd, '*.txd'),
            (getattr(s, 'gtatools_export_all_cst', False), '*.cst'),
        ):
            if flag and glob not in parts:
                parts.append(glob)
        self.filter_glob = ';'.join(parts) if parts else '*.__none__'
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        # File browser sidebar — the 4 format toggles + conditional
        # library/shared rows used to live on the main panel; moved
        # here so the panel collapses to just two target buttons and
        # the format pick happens at the moment of export.
        layout = self.layout
        scn = context.scene
        # Всё в одну плотную align-колонку — боксы примыкают вплотную, без
        # зазоров браузера. Заголовки/форматы/имя — в одном верхнем боксе.
        col = layout.column(align=True)
        from .dff_export import draw_export_game_rows, draw_dff_flags_block
        top = col.box()
        draw_export_game_rows(top, context)
        top.label(text=T("Что экспортировать:"))
        # Кнопки-тумблеры (не чекбоксы) — иначе в узком сайдбаре текст
        # DFF/COL/LOD/TXD/CST обрезается в «D…/C…».
        row = top.row(align=True)
        row.prop(scn.inu_settings, "gtatools_export_all_dff", text="DFF", toggle=True)
        row.prop(scn.inu_settings, "gtatools_export_all_col", text="COL", toggle=True)
        row.prop(scn.inu_settings, "gtatools_export_all_lod", text="LOD", toggle=True)
        row.prop(scn.inu_settings, "gtatools_export_all_txd", text="TXD", toggle=True)
        row.prop(scn.inu_settings, "gtatools_export_all_cst", text="CST", toggle=True)
        top.prop(scn.inu_settings, "gtatools_export_all_ide_ipl",
                 text=T("Также в IDE / IPL (пути из панели)"))
        top.prop(scn.inu_settings, "gtatools_export_all_single_dff",
                 text=T("Один DFF (машина/пед)"))
        # Имя экспорта — компактной строкой в том же боксе (без отдельного).
        n_groups = getattr(self, '_n_groups', 0)
        name = (getattr(self, '_export_name', '')
                or os.path.splitext((self.filename or '').strip())[0])
        if n_groups > 1:
            nrow = top.row(); nrow.enabled = False
            nrow.label(text=T("Несколько моделей — имена по моделям"),
                       **inu_icon(safe_icon('INFO')))
        elif name:
            top.label(text=f"{T('Имя экспорта:')} {name}",
                      **inu_icon(safe_icon('FILE')))
        else:
            nrow = top.row(); nrow.enabled = False
            nrow.label(text=T("Модель не выделена"),
                       **inu_icon(safe_icon('INFO')))
        # Настройки коллизии — общие для .COL и .CST (одни и те же значения),
        # поэтому показываем блок при любом из двух включённых форматов.
        if scn.inu_settings.gtatools_export_all_col or scn.inu_settings.gtatools_export_all_cst:
            box = col.box()
            # Название COL-библиотеки (только для .COL) — внутри бокса, сверху.
            if scn.inu_settings.gtatools_export_all_col:
                row = box.row(align=True)
                row.prop(scn.inu_settings, "gtatools_export_all_col_library",
                         text="", **inu_icon(safe_icon('PACKAGE')))
                row.prop(scn.inu_settings, "gtatools_export_all_col_library_name",
                         text="", placeholder="collision")
            box.prop(scn.inu_settings, "gtatools_export_all_col_empty",
                     text=T("Пустая коллизия"))
            from .col_export import _draw_col_auto_light
            sub = box.column()
            sub.enabled = not scn.inu_settings.gtatools_export_all_col_empty
            _draw_col_auto_light(sub, context)
        if scn.inu_settings.gtatools_export_all_txd:
            box = col.box()
            # Раньше «общий TXD» был голой иконкой-коробкой без подписи —
            # его просто не находили, и текстуры уходили в отдельные файлы.
            box.prop(scn.inu_settings, "gtatools_export_all_txd_shared",
                     text=T("Общий TXD — все модели в один файл"),
                     **inu_icon(safe_icon('PACKAGE')))
            sub = box.row(align=True)
            sub.enabled = bool(scn.inu_settings.gtatools_export_all_txd_shared)
            sub.prop(scn.inu_settings, "gtatools_export_all_txd_shared_name",
                     text=T("Имя"), placeholder="textures")
            box.prop(scn.inu_settings, "gtatools_export_all_txd_merge",
                     text=T("Дописать в существующий TXD"))
            if (not scn.inu_settings.gtatools_export_all_txd_shared
                    and getattr(self, '_n_groups', 0) > 1):
                note = box.row()
                note.enabled = False
                note.label(text=T("Текстуры пойдут в отдельные .txd по моделям"),
                           **inu_icon(safe_icon('INFO')))

        # ── Pipeline + DFF flags — shared N-panel mirror ──
        # Показываем только когда включён формат, к которому флаги
        # относятся (DFF или LOD — оба пишутся как DFF-геометрия).
        if (scn.inu_settings.gtatools_export_all_dff
                or scn.inu_settings.gtatools_export_all_lod):
            draw_dff_flags_block(col, context)

        # ── All → IMG (в самом низу, после DFF Flags) ──
        box = col.box()
        box.prop(self, "to_img", text=T("All → IMG"),
                 **inu_icon(safe_icon('PACKAGE')))
        if self.to_img:
            img_path = bpy.path.abspath(scn.inu_settings.gtatools_img_path or '')
            if img_path:
                box.label(text=os.path.basename(img_path) or img_path,
                          **inu_icon(safe_icon('FILE_ARCHIVE')))
                box.label(text=T("Папка игнорируется — экспорт в этот IMG"),
                          **inu_icon(safe_icon('INFO')))
            else:
                box.label(text=T("Путь к .img не задан в настройках аддона"),
                          **inu_icon(safe_icon('ERROR')))

    def _export_single_dff(self, context, name_override):
        """Один DFF — общий движок run_single_dff_export."""
        s = context.scene.inu_settings
        out, errors, root, dropped = run_single_dff_export(
            context, self.directory, name_override,
            want_dff=bool(s.gtatools_export_all_dff),
            want_txd=bool(s.gtatools_export_all_txd),
            want_col=bool(s.gtatools_export_all_col),
            backend=getattr(s, 'gtatools_dxt_backend', 'numpy'),
            txd_merge=bool(getattr(s, 'gtatools_export_all_txd_merge', False)))
        return _report_single_dff(self, out, errors, root, dropped)

    def execute(self, context):
        s = context.scene.inu_settings

        # All → IMG: вместо записи в выбранную папку пишем прямо в .img
        # архив из настроек. Переиспользуем gtatools.export_to_img через
        # EXEC_DEFAULT (без его диалога): при пустом TXD-плане он берёт
        # имена .txd по моделям и включает все группы по умолчанию.
        if self.to_img:
            img_path = bpy.path.abspath(s.gtatools_img_path or '')
            if not img_path or not os.path.isfile(img_path):
                self.report({'ERROR'},
                            T("Укажите путь к .img архиву в настройках аддона"))
                return {'CANCELLED'}
            context.window_manager.gtatools_txd_export_plan.clear()
            res = bpy.ops.gtatools.export_to_img(
                'EXEC_DEFAULT',
                shared_txd=bool(getattr(s, 'gtatools_export_all_txd_shared', False)),
                shared_txd_name=(getattr(s, 'gtatools_export_all_txd_shared_name', '')
                                 or 'textures'))
            if getattr(s, 'gtatools_export_all_ide_ipl', False):
                self._also_upsert_ide_ipl(context)
            return res

        # Клик по файлу в браузере → его имя (без расширения) становится
        # базовым именем экспорта для ОДНОЙ выделенной модели: DFF/COL/LOD/
        # TXD/CST пишутся как <имя>.<ext> в ту же папку (TXD — с merge при
        # включённой галочке). Несколько моделей одним именем не назвать —
        # тогда override игнорируется и работают имена по моделям.
        picked = (self.filename or '').strip()
        name_override = os.path.splitext(picked)[0] if picked else ''
        # Браузер по умолчанию подставляет имя .blend-файла в поле имени —
        # его нельзя пускать как имя экспорта (иначе модель уйдёт под именем
        # карты). Сбрасываем override → имена берутся по моделям.
        blendbase = os.path.splitext(os.path.basename(
            bpy.data.filepath or ''))[0]
        if name_override and blendbase and name_override == blendbase:
            name_override = ''

        # Один DFF (машина/пед): вся выделенная иерархия → один .dff, без
        # разбивки по именам моделей.
        if getattr(s, 'gtatools_export_all_single_dff', False):
            return self._export_single_dff(context, name_override)

        # Выбранный (или вписанный) в браузере <имя>.txd = «все текстуры в ЭТОТ
        # файл», сколько бы моделей ни было выделено. Раньше имя работало только
        # для ОДНОЙ модели, а на нескольких молча игнорировалось и каждая писала
        # свой <имя модели>.txd — и получались «те же текстуры в разных TXD».
        txd_shared = bool(getattr(s, 'gtatools_export_all_txd_shared', False))
        txd_shared_name = (getattr(s, 'gtatools_export_all_txd_shared_name', '')
                           or 'textures')
        if name_override and picked.lower().endswith('.txd'):
            txd_shared = True
            txd_shared_name = name_override

        exported, errors, tri_warnings, txd_notes, num_groups = run_group_export(
            context, self.directory,
            skip_dff=not s.gtatools_export_all_dff,
            skip_col=not s.gtatools_export_all_col,
            skip_lod=not s.gtatools_export_all_lod,
            skip_txd=not s.gtatools_export_all_txd,
            skip_cst=not getattr(s, 'gtatools_export_all_cst', False),
            col_library=bool(getattr(s, 'gtatools_export_all_col_library', False)),
            col_library_name=getattr(s, 'gtatools_export_all_col_library_name', '') or 'collision',
            txd_shared=txd_shared,
            txd_shared_name=txd_shared_name,
            backend=getattr(s, 'gtatools_dxt_backend', 'numpy'),
            empty_col=bool(getattr(s, 'gtatools_export_all_col_empty', False)),
            txd_merge=bool(getattr(s, 'gtatools_export_all_txd_merge', False)),
            name_override=name_override)
        if getattr(s, 'gtatools_export_all_ide_ipl', False):
            self._also_upsert_ide_ipl(context)
        return _report_group_export(self, exported, errors, tri_warnings,
                                    num_groups, txd_notes)

    def _also_upsert_ide_ipl(self, context):
        """After export, upsert the selected models into the panel-picked
        IDE/IPL files (gtatools_ide_path / gtatools_ipl_path). Same entry
        logic as the IDE/IPL 'Add' buttons (LOD id+1, lod_index)."""
        s = context.scene.inu_settings
        ide_path = bpy.path.abspath(getattr(s, 'gtatools_ide_path', '') or '')
        ipl_path = bpy.path.abspath(getattr(s, 'gtatools_ipl_path', '') or '')
        if not ide_path and not ipl_path:
            self.report({'WARNING'},
                        T("IDE/IPL: файлы не выбраны в панели — пропущено"))
            return
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            from ..tools.model_utils import _get_active_collection_objects
            objs = [o for o in _get_active_collection_objects()
                    if o.type == 'MESH']
        parts = _upsert_ide_ipl_objects(self, context, objs,
                                        ide_path=ide_path, ipl_path=ipl_path)
        if parts:
            self.report({'INFO'}, "  ".join(parts))


class GTATOOLS_OT_quick_single_export(bpy.types.Operator):
    """Быстрый экспорт одной модели (машина / пед) в ОДИН .dff.

    Включает режим «Один DFF» + формат DFF и сразу открывает диалог Export All
    — остаётся выбрать папку/имя и нажать Export. Коллизия машины (меш +
    сферы) встраивается в .dff автоматически. Кнопка для тематических вкладок
    («Машины», «Скины»), чтобы не искать экспорт в общем меню."""
    bl_idname = "gtatools.quick_single_export"
    bl_label = "INU: Экспорт (один DFF)"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        s = context.scene.inu_settings
        s.gtatools_export_all_single_dff = True
        s.gtatools_export_all_dff = True
        return bpy.ops.gtatools.export_all('INVOKE_DEFAULT')


class GTATOOLS_OT_export_dff_models(bpy.types.Operator):
    """Экспорт выделенных моделей в .dff — по одному файлу на модель.

    Зеркало импорта: выделил несколько моделей → получил несколько .dff
    (имена из имён моделей), части одной модели (иерархия) → в один файл.
    Тот же общий движок, что и Export All, только включён один формат."""
    bl_idname = "gtatools.export_dff_models"
    bl_label = "INU: Export DFF (по моделям)"
    bl_options = {'REGISTER'}

    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        from .dff_export import draw_export_game_block, draw_dff_flags_block
        draw_export_game_block(layout, context)
        col = layout.column(align=True)
        col.scale_y = 0.85
        col.label(text=T("Каждая выделенная модель → свой .dff"),
                  **inu_icon(safe_icon('INFO')))
        draw_dff_flags_block(layout, context)

    def execute(self, context):
        backend = getattr(context.scene.inu_settings, 'gtatools_dxt_backend', 'numpy')
        exported, errors, tri_warnings, txd_notes, num_groups = run_group_export(
            context, self.directory,
            skip_dff=False, skip_col=True, skip_lod=True, skip_txd=True,
            backend=backend)
        return _report_group_export(self, exported, errors, tri_warnings,
                                    num_groups, txd_notes)


class GTATOOLS_OT_inu_export(bpy.types.Operator, ExportHelper):
    """Единый экспорт INU — DFF, COL, TXD, IDE, IPL в одну папку"""
    bl_idname = "gtatools.inu_export"
    bl_label = "INU: INU Export"
    bl_options = {'REGISTER', 'PRESET'}

    filename_ext = ""
    use_filter_folder = True

    # ── Format checkboxes ── те же, что у «Экспорта всех выделенных»
    export_dff: BoolProperty(name="DFF", default=True, description="Export DFF models")
    export_col: BoolProperty(name="COL", default=True, description="Export COL collision")
    export_lod: BoolProperty(name="LOD", default=True,
        description=T("Экспортировать LOD-модели (LOD<имя>.dff)"))
    from ..tools.txd_export import export_txd
    export_txd: BoolProperty(name="TXD", default=True, description="Export TXD textures")
    export_cst: BoolProperty(name="CST", default=False,
        description=T("Коллизия текстом для Collision File Editor II (.cst)"))
    export_ide: BoolProperty(name="IDE", default=False, description="Export IDE definitions")
    export_ipl: BoolProperty(name="IPL", default=False, description="Export IPL placements")
    single_dff: BoolProperty(
        name=T("Один DFF (машина/пед)"),
        description=T("Вся выделенная иерархия — в ОДИН .dff, коллизия внутрь него"),
        default=False)

    # ── Source ──
    source: EnumProperty(
        name="Source",
        items=[
            ('SELECTED', "Selected", "Export selected objects"),
            ('COLLECTION', "Active Collection", "Export objects from active collection"),
            ('SCENE', "Entire Scene", "Export all mesh objects in scene"),
        ],
        default='SELECTED',
    )

    # ── COL settings ──
    col_library: BoolProperty(
        name=T("COL Library"),
        description=T("Писать все коллизии в один .col файл (multi-entry library). Каждая запись в файле — отдельная коллизия со своим model_id, сопоставляется с DFF по ID"),
        default=False,
    )
    col_library_name: StringProperty(
        name=T("Имя library .col"),
        description=T("Имя общего .col файла без расширения (например 'district' → district.col)"),
        default="collision",
    )
    col_empty: BoolProperty(
        name=T("Пустая коллизия"),
        description=T("Записать запись без геометрии (границы — по видимой модели)"),
        default=False)

    # Старые поля — только чтобы сохранённые пресеты оператора не падали на
    # неизвестном атрибуте. Не рисуются и ни на что не влияют: текстуры всегда
    # берутся из экспортируемых моделей, 2DFX-дети всегда идут в DFF, LOD — галочка LOD.
    txd_selected_only: BoolProperty(name="Selected Only", default=True,
                                    options={'HIDDEN', 'SKIP_SAVE'})
    dff_include_2dfx: BoolProperty(name="Include 2DFX", default=True,
                                   options={'HIDDEN', 'SKIP_SAVE'})
    dff_auto_lod: BoolProperty(name="Auto-LOD", default=True,
                               options={'HIDDEN', 'SKIP_SAVE'})

    # ── TXD settings ──
    txd_shared: BoolProperty(
        name=T("Общий TXD"),
        description=T(
            "Все текстуры экспортируемых моделей — в ОДИН файл с именем ниже.\n"
            "Без этой галочки каждая модель получает свой <имя>.txd"),
        default=False)
    txd_shared_name: StringProperty(
        name=T("Имя"),
        description=T("Имя общего TXD без .txd"),
        default="")
    txd_merge: BoolProperty(
        name=T("Дописать в существующий"),
        description=T(
            "Если TXD уже есть — добавить/обновить в нём текстуры сцены, "
            "сохранив остальные (от других моделей). Иначе файл перезаписывается целиком"),
        default=False)

    # ── IDE/IPL settings ──
    ide_ipl_upsert: BoolProperty(name="Upsert (add/update)", default=False,
        description="Add or update entries in existing IDE/IPL files instead of creating new ones")
    ide_upsert_path: StringProperty(name="IDE File", subtype='FILE_PATH',
        description="Path to existing IDE file for upsert")
    ipl_upsert_path: StringProperty(name="IPL File", subtype='FILE_PATH',
        description="Path to existing IPL file for upsert")

    def invoke(self, context, event):
        preset = getattr(context.scene.inu_settings,
                         'gtatools_shared_txd_name', '').strip()
        if preset and not self.txd_shared_name:
            self.txd_shared_name = preset
        return super().invoke(context, event)

    def draw(self, context):
        layout = self.layout

        # Целевая игра/платформа — в самом верху окна экспорта.
        from .dff_export import draw_export_game_block
        draw_export_game_block(layout, context)

        # Format — тот же набор, что у основного экспорта (+ IDE/IPL)
        box = layout.box()
        box.label(text=T("Формат:"), **inu_icon(safe_icon('EXPORT')))
        row = box.row(align=True)
        row.prop(self, "export_dff", toggle=True)
        row.prop(self, "export_col", toggle=True)
        row.prop(self, "export_lod", toggle=True)
        row.prop(self, "export_txd", toggle=True)
        row.prop(self, "export_cst", toggle=True)
        row = box.row(align=True)
        row.prop(self, "export_ide", toggle=True)
        row.prop(self, "export_ipl", toggle=True)
        box.prop(self, "single_dff")

        # Source
        box = layout.box()
        box.label(text=T("Источник:"), **inu_icon(safe_icon('OBJECT_DATA')))
        box.prop(self, "source", text="")

        # DFF settings
        if self.export_dff or self.export_lod:
            box = layout.box()
            box.label(text="DFF:", **inu_icon(safe_icon('MESH_DATA')))
            # Pipeline buttons + DFF flags column — shared N-panel mirror.
            from .dff_export import draw_dff_flags_block
            draw_dff_flags_block(box, context)

        # COL settings (те же, что у основного: library / пустая / авто-свет)
        if self.export_col or self.export_cst:
            box = layout.box()
            box.label(text="COL:", **inu_icon(safe_icon('MESH_ICOSPHERE')))
            if self.export_col:
                box.prop(self, "col_library")
                if self.col_library:
                    box.prop(self, "col_library_name")
            box.prop(self, "col_empty")
            from .col_export import _draw_col_auto_light
            sub = box.column()
            sub.enabled = not self.col_empty
            _draw_col_auto_light(sub, context)

        # TXD settings
        if self.export_txd:
            box = layout.box()
            box.label(text="TXD:", **inu_icon(safe_icon('IMAGE_DATA')))
            box.prop(self, "txd_shared")
            if self.txd_shared:
                box.prop(self, "txd_shared_name")
            box.prop(self, "txd_merge")
            backend = getattr(context.scene.inu_settings, 'gtatools_dxt_backend', 'numpy')
            backend_label = {
                'numpy':      "Numpy (range-fit mip0 + bbox mip1+)",
                'numpy_fast': "Numpy fast (bbox-int)",
                'gpu':        "GPU compute",
            }.get(backend, backend)
            box.label(text=f"DXT: {backend_label}", **inu_icon(safe_icon('INFO')))

        # IDE/IPL settings
        if self.export_ide or self.export_ipl:
            box = layout.box()
            box.label(text="IDE / IPL:", **inu_icon(safe_icon('TEXT')))
            box.prop(self, "ide_ipl_upsert")
            if self.ide_ipl_upsert:
                if self.export_ide:
                    box.prop(self, "ide_upsert_path")
                if self.export_ipl:
                    box.prop(self, "ipl_upsert_path")

    def _get_source_objects(self, context):
        """Get objects based on source setting."""
        if self.source == 'SELECTED':
            return [o for o in context.selected_objects if o.type in ('MESH', 'EMPTY')]
        elif self.source == 'COLLECTION':
            col = context.view_layer.active_layer_collection.collection
            return [o for o in col.objects if o.type in ('MESH', 'EMPTY')]
        else:  # SCENE
            return [o for o in context.scene.objects if o.type in ('MESH', 'EMPTY')]

    def execute(self, context):
        # ЕДИНЫЙ движок с основным экспортом: DFF/LOD/COL/CST/TXD пишет
        # run_group_export (тот же, что у «Экспорта всех выделенных»), INU
        # Export добавляет к нему выбор источника и IDE/IPL. Раньше здесь была
        # СВОЯ копия цикла: без общего TXD и дописывания (TXD всегда падал
        # отдельным файлом на каждую модель), без CST, пустой коллизии,
        # одного DFF и без предупреждений о треугольниках.
        from ..tools.model_utils import find_all_selected_model_groups
        directory = os.path.dirname(self.filepath) if self.filepath else self.filepath
        if not directory or not os.path.isdir(directory):
            self.report({'ERROR'}, T("Выберите папку для экспорта"))
            return {'CANCELLED'}

        source_objects = self._get_source_objects(context)
        mesh_objects = [o for o in source_objects if o.type == 'MESH']
        if not mesh_objects:
            self.report({'ERROR'}, T("Нет меш объектов для экспорта"))
            return {'CANCELLED'}

        s = context.scene.inu_settings
        backend = getattr(s, 'gtatools_dxt_backend', 'numpy')
        shared_name = (self.txd_shared_name.strip()
                       or getattr(s, 'gtatools_shared_txd_name', '').strip()
                       or 'textures')
        if shared_name.lower().endswith('.txd'):
            shared_name = shared_name[:-4]

        # Движок работает по ВЫДЕЛЕНИЮ — на время экспорта выделяем
        # объекты источника (выделенное / коллекция / сцена) и возвращаем как было.
        prev_selected = list(context.selected_objects)
        prev_active = context.view_layer.objects.active
        groups = {}
        try:
            bpy.ops.object.select_all(action='DESELECT')
            for o in mesh_objects:
                try:
                    o.select_set(True)
                except RuntimeError:
                    pass
            context.view_layer.objects.active = mesh_objects[0]

            groups = find_all_selected_model_groups()

            if self.single_dff:
                out, errors, root, dropped = run_single_dff_export(
                    context, directory, '',
                    want_dff=self.export_dff, want_txd=self.export_txd,
                    want_col=self.export_col, backend=backend,
                    txd_merge=self.txd_merge)
                result = _report_single_dff(self, out, errors, root, dropped)
            else:
                exported, errors, tri_warnings, txd_notes, num_groups = \
                    run_group_export(
                        context, directory,
                        skip_dff=not self.export_dff,
                        skip_col=not self.export_col,
                        skip_lod=not self.export_lod,
                        skip_txd=not self.export_txd,
                        skip_cst=not self.export_cst,
                        col_library=bool(self.col_library),
                        col_library_name=self.col_library_name or 'collision',
                        txd_shared=bool(self.txd_shared),
                        txd_shared_name=shared_name,
                        backend=backend,
                        empty_col=bool(self.col_empty),
                        txd_merge=bool(self.txd_merge))
                result = _report_group_export(self, exported, errors,
                                              tri_warnings, num_groups,
                                              txd_notes)
        finally:
            bpy.ops.object.select_all(action='DESELECT')
            for o in prev_selected:
                try:
                    o.select_set(True)
                except RuntimeError:
                    pass
            if prev_active is not None:
                try:
                    context.view_layer.objects.active = prev_active
                except Exception:
                    pass

        # ── IDE / IPL ── чего у основного экспорта нет: либо дописывание в
        # выбранные файлы, либо objects.ide / objects.ipl рядом с моделями.
        notes = []
        if self.export_ide and groups:
            if self.ide_ipl_upsert and self.ide_upsert_path:
                notes += _upsert_ide_ipl_objects(
                    self, context, mesh_objects,
                    ide_path=bpy.path.abspath(self.ide_upsert_path))
            else:
                ide_path = os.path.join(directory, "objects.ide")
                try:
                    from .ide_export import export_ide as inu_export_ide
                    inu_export_ide(filepath=ide_path, objects=mesh_objects)
                    notes.append("objects.ide")
                    from .textdata_audit import audit_ide_file
                    audit_ide_file(self, ide_path)
                except Exception as e:
                    notes.append(f"IDE err: {e}")

        if self.export_ipl and groups:
            if self.ide_ipl_upsert and self.ipl_upsert_path:
                notes += _upsert_ide_ipl_objects(
                    self, context, mesh_objects,
                    ipl_path=bpy.path.abspath(self.ipl_upsert_path))
            else:
                ipl_path = os.path.join(directory, "objects.ipl")
                try:
                    from .ipl_export import export_ipl as inu_export_ipl
                    inu_export_ipl(filepath=ipl_path, objects=mesh_objects)
                    notes.append("objects.ipl")
                    from .textdata_audit import audit_ipl_file
                    audit_ipl_file(self, ipl_path, context)
                except Exception as e:
                    notes.append(f"IPL err: {e}")

        if notes:
            self.report({'INFO'}, "  ".join(notes))
        return result


