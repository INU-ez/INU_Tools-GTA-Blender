# INU_tools.ops.ide_ipl — IDE / IPL panel operators.
#
# Phase 3 batch 4 (2026-04-26): 11 operators moved from __init__.py.
# Three small helpers (_ide_entry_from_obj, _ipl_entry_from_obj,
# _clean_model_name_ide) stay in __init__.py because INU Import/Export
# and other ops still use them; this module pulls them in lazily.

import os
import bpy
from bpy.props import (
    BoolProperty, StringProperty, IntProperty, CollectionProperty,
)
from .. import T
from ..tools.compat import run_op_override
from . import map_link
from .map_link import ConfirmOnProblems


def _pub(op, level, msg):
    """``op.report`` (normal banner / Info log) AND mirror the same text
    into the floater status strip.

    The IDE/IPL/IMG floater dispatches these ops via ``bpy.ops``, where
    Blender suppresses the report banner — so the floater can't see the
    report. Routing the message through ``set_floater_status`` puts the
    SAME notification the N-panel shows ("Sync IPL: …", "IDE: обновлено …")
    into the active floater's bottom strip. (Calls ``op.report`` — the
    instance method — which works; ``bpy.types.Operator.report`` does not
    exist as a class attribute, so it can't be wrapped at class level.)"""
    op.report({level}, msg)
    try:
        from .floater.base import set_floater_status
        set_floater_status(str(msg), level)
    except Exception:
        pass


def _validate_model_ids(objs):
    """Validate model IDs of a selection about to be written to IDE/IPL.

    Returns ``(errors, warnings)`` — lists of human-readable strings.

    * ``errors`` → HARD STOP: an object that would be written with
      ``model_id == 0``. id 0 is the player model, so such a row corrupts the
      game. A DFF needs its own id; a LOD may borrow ``dff_id + 1``, so a LOD
      only errors when it has neither its own id nor a paired DFF with one.
    * ``warnings`` → a LOD that would auto-take ``dff_id + 1`` where that id is
      already owned by another mesh in the scene (silent clash, see #5).
    """
    from ..tools.model_utils import get_model_type

    by_base = {}
    for o in objs:
        mt, base = get_model_type(o)
        by_base.setdefault(base, {})[mt] = o

    # model_id → owners, across the whole scene (for the LOD+1 clash check).
    scene_ids = {}
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        mid = int(getattr(getattr(o, 'inu', None), 'model_id', 0) or 0)
        if mid > 0:
            scene_ids.setdefault(mid, []).append(o)

    errors, warnings = [], []
    for g in by_base.values():
        dff = g.get('DFF')
        lod = g.get('LOD')
        dff_id = int(getattr(dff.inu, 'model_id', 0) or 0) if dff else 0
        if dff is not None and dff_id == 0:
            errors.append(dff.name)
        if lod is not None:
            lod_id = int(getattr(lod.inu, 'model_id', 0) or 0)
            if lod_id == 0:
                if dff_id <= 0:
                    errors.append(lod.name)        # nothing to borrow id+1 from
                else:
                    owners = [o for o in scene_ids.get(dff_id + 1, [])
                              if o is not lod and o is not dff]
                    if owners:
                        warnings.append(
                            f"{lod.name} → id {dff_id + 1} "
                            f"({owners[0].name})")
    return errors, warnings


def _report_id_validation(op, objs):
    """Run :func:`_validate_model_ids` and report. Returns True if the caller
    must abort (a blocking id-0 error was found)."""
    errs, warns = _validate_model_ids(objs)
    if errs:
        op.report({'ERROR'}, T(
            "Model ID = 0 у: {0}. Назначь ID "
            "(ID Manager → Auto-Assign) перед "
            "добавлением.").format(
                ", ".join(errs[:6]) + ("…" if len(errs) > 6 else "")))
        return True
    for w in warns:
        op.report({'WARNING'},
                  T("LOD занимает уже "
                    "занятый ID: ") + w)
    return False


def _sel_meshes(context):
    return [o for o in context.selected_objects if o.type == 'MESH']


def _id_warnings(rep, objs):
    """LOD borrowing an id+1 that another mesh already owns (#5)."""
    _errs, warns = _validate_model_ids(objs)
    for w in warns:
        rep.msg('WARNING', T("LOD занимает уже занятый ID: ") + w)


class GTATOOLS_OT_add_to_map(bpy.types.Operator):
    """Добавить/обновить выделенное в файлах IDE + IPL одним действием: пишет и
    IDE (определение модели), и IPL (расстановку) в выбранные файлы. Обёртка
    над Add to IDE + Add to IPL — их логика (авто-LOD, маршрутизация,
    tracking) не дублируется. Не путать с «Export Map» (вся карта)."""
    bl_idname = "gtatools.add_to_map"
    bl_label = "INU: Добавить в IDE + IPL"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        r_ide = bpy.ops.gtatools.upsert_ide('EXEC_DEFAULT')
        r_ipl = bpy.ops.gtatools.upsert_ipl('EXEC_DEFAULT')
        # Оба под-оператора сами репортят свой итог/ошибки. Считаем действие
        # выполненным, если хоть один что-то записал.
        if 'CANCELLED' in r_ide and 'CANCELLED' in r_ipl:
            return {'CANCELLED'}
        return {'FINISHED'}


class GTATOOLS_OT_remove_from_map(bpy.types.Operator):
    """Убрать выделенное из файлов IDE и IPL (удаляет их записи)."""
    bl_idname = "gtatools.remove_from_map"
    bl_label = "INU: Убрать из IDE/IPL"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        r_ide = bpy.ops.gtatools.remove_ide('EXEC_DEFAULT')
        r_ipl = bpy.ops.gtatools.remove_ipl('EXEC_DEFAULT')
        if 'CANCELLED' in r_ide and 'CANCELLED' in r_ipl:
            return {'CANCELLED'}
        return {'FINISHED'}


class GTATOOLS_OT_import_picked_ide(bpy.types.Operator):
    """Импортировать ВЫБРАННЫЙ в панели IDE-файл (без диалога — берёт путь из
    строки IDE). Сопоставляет определения с объектами сцены."""
    bl_idname = "gtatools.import_picked_ide"
    bl_label = "INU: Import picked IDE"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        p = bpy.path.abspath(context.scene.inu_settings.gtatools_ide_path)
        if not p or not os.path.isfile(p):
            self.report({'ERROR'}, T("Укажите IDE файл"))
            return {'CANCELLED'}
        from .ide_import import import_ide as inu_import_ide
        try:
            matched = inu_import_ide(filepath=p, context=context)
            self.report({'INFO'}, f"IDE: {len(matched)} objects matched")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"IDE import error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_import_picked_ipl(bpy.types.Operator):
    """Импортировать ВЫБРАННЫЙ в панели IPL-файл (без диалога — берёт путь из
    строки IPL). Расставляет объекты по IPL."""
    bl_idname = "gtatools.import_picked_ipl"
    bl_label = "INU: Import picked IPL"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        p = bpy.path.abspath(context.scene.inu_settings.gtatools_ipl_path)
        if not p or not os.path.isfile(p):
            self.report({'ERROR'}, T("Укажите IPL файл"))
            return {'CANCELLED'}
        from .ipl_import import import_ipl as inu_import_ipl
        try:
            placed = inu_import_ipl(filepath=p, context=context)
            self.report({'INFO'}, f"IPL: {len(placed)} objects placed")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"IPL import error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_upsert_ide(ConfirmOnProblems, bpy.types.Operator):
    """Add: записать/обновить ВЫДЕЛЕННЫЕ модели в ВЫБРАННЫЙ .ide (id, txd, дистанция, флаги). Обновляет свои строки на месте; LOD модели пишется вместе с ней. Чужую модель с тем же ID не перезаписывает — сообщает о конфликте. Отличие от Export: пишет в уже выбранный файл, а не создаёт новый"""
    bl_idname = "gtatools.upsert_ide"
    bl_label = "INU: Add to IDE"
    bl_options = {'REGISTER'}

    last_message = ""

    def _run(self, context, dry_run):
        picked = context.scene.inu_settings.gtatools_ide_path
        objs = _sel_meshes(context)
        rep = map_link.ide_write(context, objs, picked=picked, dry_run=dry_run)
        if picked and not picked.lower().endswith('.ide'):
            rep.msg('WARNING', T("Путь IDE — не .ide файл, проверь бокс IDE"))
        _id_warnings(rep, objs)
        return rep

    def execute(self, context):
        if not _sel_meshes(context):
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        rep = self._run(context, False)
        from .textdata_audit import audit_ide_file
        for f in sorted(rep.files):
            audit_ide_file(self, f)
        GTATOOLS_OT_upsert_ide.last_message = map_link.report_to(
            self, "IDE", rep, pub=_pub)
        return {'FINISHED'}


class GTATOOLS_OT_upsert_ipl(ConfirmOnProblems, bpy.types.Operator):
    """Add: записать/обновить РАССТАНОВКУ выделенных моделей в ВЫБРАННЫЙ .ipl (позиция + поворот). Перемещённую модель обновляет на месте (не плодит дубли); LOD модели ставится вместе с ней, у каждой копии — свой LOD в её точке. Отличие от Export: пишет в уже выбранный файл, а не создаёт новый"""
    bl_idname = "gtatools.upsert_ipl"
    bl_label = "INU: Add to IPL"
    bl_options = {'REGISTER'}

    last_message = ""

    def _run(self, context, dry_run):
        picked = context.scene.inu_settings.gtatools_ipl_path
        objs = _sel_meshes(context)
        rep = map_link.ipl_write(context, objs, picked=picked, dry_run=dry_run)
        if picked and not picked.lower().endswith('.ipl'):
            rep.msg('WARNING', T("Путь IPL — не .ipl файл, проверь бокс IPL"))
        _id_warnings(rep, objs)
        return rep

    def execute(self, context):
        if not _sel_meshes(context):
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        rep = self._run(context, False)
        from .textdata_audit import audit_ipl_file
        for f in sorted(rep.files):
            audit_ipl_file(self, f, context)
        # Текст кладётся в класс: при вызове через bpy.ops из другого
        # оператора Blender гасит баннер вложенного — обёртка берёт его отсюда.
        GTATOOLS_OT_upsert_ipl.last_message = map_link.report_to(
            self, "IPL", rep, pub=_pub)
        return {'FINISHED'}


class GTATOOLS_OT_pick_setting_path(bpy.types.Operator):
    """Выбрать файл и записать путь в настройку (для коротких меток путей
    IDE/IPL в боксах редактора — метку нельзя править инлайн)."""
    bl_idname = "gtatools.pick_setting_path"
    bl_label = "INU: Pick File"
    bl_options = {'REGISTER'}

    setting: StringProperty(default="")            # имя проперти в inu_settings
    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(
        default="*.ipl;*.IPL;*.ide;*.IDE;*.img;*.IMG", options={'HIDDEN'})

    # Per-box extension filter so the IDE box shows only .ide, the IPL box only
    # .ipl, etc. — otherwise it's easy to pick a .ipl for the IDE box and get
    # IPL content written into the IDE file (a swap that bit users).
    _SETTING_GLOB = {
        "gtatools_ide_path": "*.ide;*.IDE",
        "gtatools_ipl_path": "*.ipl;*.IPL",
        "gtatools_img_path": "*.img;*.IMG",
    }

    def invoke(self, context, event):
        self.filter_glob = self._SETTING_GLOB.get(
            self.setting, "*.ipl;*.IPL;*.ide;*.IDE;*.img;*.IMG")
        if self.setting:
            cur = getattr(context.scene.inu_settings, self.setting, '')
            if cur:
                self.filepath = bpy.path.abspath(cur)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.setting:
            try:
                setattr(context.scene.inu_settings, self.setting, self.filepath)
            except Exception as e:
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}
        return {'FINISHED'}


def _get_scene_game(context):
    try:
        from ..core import game_versions as gv
        return gv.game_of_scene(context.scene)
    except Exception:
        return 'SA'


# ── IPL link tracking operators ────────────────────────────────────


def _ipl_sync_targets(settings):
    """Resolve the ordered, de-duped list of IPL paths to sync against.

    The multi-IPL list (``gtatools_ipl_sync_list``) wins when populated;
    otherwise we fall back to the single ``gtatools_ipl_path`` so legacy
    scenes (and the combined IDE+IPL Sync) behave exactly as before.
    Returns ``(valid, missing)`` — both lists of absolute paths.
    """
    raw = []
    for it in settings.gtatools_ipl_sync_list:
        p = bpy.path.abspath(it.path) if it.path else ''
        if p:
            raw.append(p)
    # Плюс ВСЕ .ipl из папки игры (рекурсивно) — как «Обновить из IDE» ищет по
    # всем .ide. Иначе модель, чей IPL не добавлен в список вручную (например
    # maps\Upleft_obj\UPwn_hou.IPL), не находилась. Регистр расширения не важен
    # (.IPL заглавными тоже ловится через .lower()).
    root = bpy.path.abspath(getattr(settings, 'gtatools_game_root', '') or '')
    if root and os.path.isdir(root):
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.lower().endswith('.ipl'):
                    raw.append(os.path.join(dirpath, f))
    if not raw:
        single = bpy.path.abspath(settings.gtatools_ipl_path)
        if single:
            raw.append(single)

    valid, missing, seen = [], [], set()
    for p in raw:
        key = os.path.normcase(os.path.normpath(p))
        if key in seen:
            continue
        seen.add(key)
        (valid if os.path.isfile(p) else missing).append(p)
    return valid, missing


class GTATOOLS_OT_ipl_sync_from_file(bpy.types.Operator):
    """Синхронизация IPL → Blender.

    Привязанные модели находят свою строку в своём IPL (по содержимому) и
    получают её позицию/поворот. Непривязанные привязываются к ближайшей
    свободной строке своей модели (в пределах 0.5 м) из списка IPL / папки
    игры / выбранного файла. Работает по выделению, пустое выделение — вся
    сцена."""
    bl_idname = "gtatools.ipl_sync_from_file"
    bl_label = "INU: Sync from IPL"
    bl_options = {'REGISTER', 'UNDO'}

    last_message = ""

    def execute(self, context):
        valid, missing = _ipl_sync_targets(context.scene.inu_settings)
        sel = _sel_meshes(context) or [o for o in bpy.data.objects
                                        if o.type == 'MESH']
        rep = map_link.ipl_pull(context, sel, valid, move=True)
        if missing:
            rep.msg('WARNING', T("файлов не найдено: {0}").format(len(missing)))
        GTATOOLS_OT_ipl_sync_from_file.last_message = map_link.report_to(
            self, "Sync IPL", rep, pub=_pub)
        return {'FINISHED'}


class GTATOOLS_OT_ipl_restore_coords(bpy.types.Operator):
    """Вернуть выделенные модели на их координаты из IPL (позиция и поворот).

Привязанная модель берёт свою строку из своего IPL. Непривязанная — ближайшую
свободную строку своей модели во всех IPL (список / папка игры / выбранный)"""
    bl_idname = "gtatools.ipl_restore_coords"
    bl_label = "INU: Restore coords from IPL"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sel = _sel_meshes(context)
        if not sel:
            self.report({'ERROR'}, T("Выделите модель"))
            return {'CANCELLED'}
        valid, _missing = _ipl_sync_targets(context.scene.inu_settings)
        rep = map_link.ipl_pull(context, sel, valid, move=True, far='nearest')
        map_link.report_to(self, T("Координаты из IPL"), rep, pub=_pub)
        return {'FINISHED'}


class GTATOOLS_OT_ipl_sync_add(bpy.types.Operator):
    """Добавить один или несколько IPL в список синхронизации.
    Файловый диалог поддерживает множественный выбор (Ctrl/Shift)."""
    bl_idname = "gtatools.ipl_sync_add"
    bl_label = "INU: Add IPL to Sync List"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: StringProperty(subtype='FILE_PATH')
    directory: StringProperty(subtype='DIR_PATH')
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    filter_glob: StringProperty(default='*.ipl', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        coll = context.scene.inu_settings.gtatools_ipl_sync_list

        # Multi-select arrives via ``files`` + ``directory``; a single
        # pick may only populate ``filepath``.
        raw = []
        if self.directory and self.files:
            for f in self.files:
                if f.name:
                    raw.append(os.path.join(self.directory, f.name))
        if self.filepath:
            raw.append(self.filepath)

        # Оставляем ТОЛЬКО реально существующие .ipl. Файловый диалог держит в
        # поле имени текущий .blend («Без имени.blend»), и при выборе ПАПКИ без
        # выделения файла это имя утекало в список как «IPL» — фильтруем.
        paths = [p for p in raw
                 if p.lower().endswith('.ipl')
                 and os.path.isfile(bpy.path.abspath(p))]

        # Валидных .ipl не выбрано, но указана папка с .ipl → добавить ВСЕ .ipl
        # из неё (пользователь «выбрал папку с IPL»). Без рекурсии — для
        # рекурсии есть отдельная кнопка «Папка».
        if not paths and self.directory:
            d = bpy.path.abspath(self.directory)
            if os.path.isdir(d):
                for f in sorted(os.listdir(d)):
                    fp = os.path.join(d, f)
                    if f.lower().endswith('.ipl') and os.path.isfile(fp):
                        paths.append(fp)

        if not paths:
            self.report({'WARNING'}, T("Не выбрано ни одного .ipl"))
            return {'CANCELLED'}

        existing = {os.path.normcase(os.path.normpath(bpy.path.abspath(it.path)))
                    for it in coll if it.path}
        added = 0
        for p in paths:
            key = os.path.normcase(os.path.normpath(bpy.path.abspath(p)))
            if key in existing:
                continue
            existing.add(key)
            coll.add().path = p
            added += 1
        self.report({'INFO'}, T("Добавлено IPL: {0}").format(added))
        return {'FINISHED'}


class GTATOOLS_OT_ipl_sync_add_folder(bpy.types.Operator):
    """Добавить в список синхронизации ВСЕ .ipl из выбранной папки —
    по умолчанию включая подпапки (рекурсивно)."""
    bl_idname = "gtatools.ipl_sync_add_folder"
    bl_label = "INU: Add IPL folder to Sync List"
    bl_options = {'REGISTER', 'INTERNAL'}

    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(default='*.ipl', options={'HIDDEN'})
    recursive: BoolProperty(
        name="Включая подпапки", default=True,
        description="Искать .ipl и во всех вложенных папках")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        self.layout.prop(self, "recursive")

    def execute(self, context):
        d = bpy.path.abspath(self.directory) if self.directory else ''
        if not d or not os.path.isdir(d):
            self.report({'ERROR'}, T("Укажи папку с IPL"))
            return {'CANCELLED'}
        found = []
        if self.recursive:
            for root, _dirs, files in os.walk(d):
                for f in files:
                    if f.lower().endswith('.ipl'):
                        found.append(os.path.join(root, f))
        else:
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp) and f.lower().endswith('.ipl'):
                    found.append(fp)
        coll = context.scene.inu_settings.gtatools_ipl_sync_list
        existing = {os.path.normcase(os.path.normpath(bpy.path.abspath(it.path)))
                    for it in coll if it.path}
        added = 0
        for p in sorted(found):
            key = os.path.normcase(os.path.normpath(bpy.path.abspath(p)))
            if key in existing:
                continue
            existing.add(key)
            coll.add().path = p
            added += 1
        self.report({'INFO'}, T("Добавлено IPL из папки: {0} (найдено {1})").format(
            added, len(found)))
        return {'FINISHED'}


class GTATOOLS_OT_ipl_sync_remove(bpy.types.Operator):
    """Убрать IPL из списка синхронизации."""
    bl_idname = "gtatools.ipl_sync_remove"
    bl_label = "INU: Remove IPL from Sync List"
    bl_options = {'REGISTER', 'INTERNAL'}

    index: IntProperty(default=-1)

    def execute(self, context):
        coll = context.scene.inu_settings.gtatools_ipl_sync_list
        if self.index < 0:
            coll.clear()
        elif 0 <= self.index < len(coll):
            coll.remove(self.index)
        return {'FINISHED'}


class GTATOOLS_OT_ide_sync_add(bpy.types.Operator):
    """Добавить один или несколько IDE в список синхронизации.
    Файловый диалог поддерживает множественный выбор (Ctrl/Shift)."""
    bl_idname = "gtatools.ide_sync_add"
    bl_label = "INU: Add IDE to Sync List"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: StringProperty(subtype='FILE_PATH')
    directory: StringProperty(subtype='DIR_PATH')
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    filter_glob: StringProperty(default='*.ide', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        coll = context.scene.inu_settings.gtatools_ide_sync_list
        paths = []
        if self.directory and self.files:
            for f in self.files:
                if f.name:
                    paths.append(os.path.join(self.directory, f.name))
        if not paths and self.filepath:
            paths.append(self.filepath)
        if not paths:
            return {'CANCELLED'}
        existing = {os.path.normcase(os.path.normpath(bpy.path.abspath(it.path)))
                    for it in coll if it.path}
        added = 0
        for p in paths:
            key = os.path.normcase(os.path.normpath(bpy.path.abspath(p)))
            if key in existing:
                continue
            existing.add(key)
            coll.add().path = p
            added += 1
        self.report({'INFO'}, T("Добавлено IDE: {0}").format(added))
        return {'FINISHED'}


class GTATOOLS_OT_ide_sync_add_folder(bpy.types.Operator):
    """Добавить в список синхронизации ВСЕ .ide из выбранной папки —
    по умолчанию включая подпапки (рекурсивно)."""
    bl_idname = "gtatools.ide_sync_add_folder"
    bl_label = "INU: Add IDE folder to Sync List"
    bl_options = {'REGISTER', 'INTERNAL'}

    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(default='*.ide', options={'HIDDEN'})
    recursive: BoolProperty(
        name="Включая подпапки", default=True,
        description="Искать .ide и во всех вложенных папках")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        self.layout.prop(self, "recursive")

    def execute(self, context):
        d = bpy.path.abspath(self.directory) if self.directory else ''
        if not d or not os.path.isdir(d):
            self.report({'ERROR'}, T("Укажи папку с IDE"))
            return {'CANCELLED'}
        found = []
        if self.recursive:
            for root, _dirs, files in os.walk(d):
                for f in files:
                    if f.lower().endswith('.ide'):
                        found.append(os.path.join(root, f))
        else:
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp) and f.lower().endswith('.ide'):
                    found.append(fp)
        coll = context.scene.inu_settings.gtatools_ide_sync_list
        existing = {os.path.normcase(os.path.normpath(bpy.path.abspath(it.path)))
                    for it in coll if it.path}
        added = 0
        for p in sorted(found):
            key = os.path.normcase(os.path.normpath(bpy.path.abspath(p)))
            if key in existing:
                continue
            existing.add(key)
            coll.add().path = p
            added += 1
        self.report({'INFO'}, T("Добавлено IDE из папки: {0} (найдено {1})").format(
            added, len(found)))
        return {'FINISHED'}


class GTATOOLS_OT_ide_sync_remove(bpy.types.Operator):
    """Убрать IDE из списка синхронизации."""
    bl_idname = "gtatools.ide_sync_remove"
    bl_label = "INU: Remove IDE from Sync List"
    bl_options = {'REGISTER', 'INTERNAL'}

    index: IntProperty(default=-1)

    def execute(self, context):
        coll = context.scene.inu_settings.gtatools_ide_sync_list
        if self.index < 0:
            coll.clear()
        elif 0 <= self.index < len(coll):
            coll.remove(self.index)
        return {'FINISHED'}


class GTATOOLS_OT_ide_sync_export(ConfirmOnProblems, bpy.types.Operator):
    """Экспорт «каждая модель в свой IDE»: обновляет строки выделенных моделей
    в тех IDE, к которым они привязаны (импортом или прошлым Add). Модели без
    своего IDE не пишутся — добавь их через «Add» в выбранный IDE."""
    bl_idname = "gtatools.ide_sync_export"
    bl_label = "INU: Export models to their IDEs"
    bl_options = {'REGISTER'}

    def _run(self, context, dry_run):
        return map_link.ide_write(context, _sel_meshes(context), dry_run=dry_run)

    def execute(self, context):
        if not _sel_meshes(context):
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        rep = self._run(context, False)
        from .textdata_audit import audit_ide_file
        for f in sorted(rep.files):
            audit_ide_file(self, f)
        map_link.report_to(self, "IDE", rep, pub=_pub)
        return {'FINISHED'}


class GTATOOLS_OT_ipl_sync_export(ConfirmOnProblems, bpy.types.Operator):
    """Обновить координаты выделенных моделей в их родных IPL.

Каждая модель пишется в тот IPL, к которому привязана (импортом или прошлым
Add) — новая позиция и поворот, LOD переезжает вместе с ней. Файл, выбранный в
боксе IPL, при этом не используется"""
    bl_idname = "gtatools.ipl_sync_export"
    bl_label = "INU: Export placements to their IPLs"
    bl_options = {'REGISTER'}

    def _run(self, context, dry_run):
        return map_link.ipl_write(context, _sel_meshes(context), dry_run=dry_run)

    def execute(self, context):
        if not _sel_meshes(context):
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        rep = self._run(context, False)
        from .textdata_audit import audit_ipl_file
        for f in sorted(rep.files):
            audit_ipl_file(self, f, context)
        msg = map_link.report_to(self, "IPL", rep, pub=_pub)
        _show_status_text(context, msg)
        return {'FINISHED'}


class GTATOOLS_OT_ipl_remove_link(ConfirmOnProblems, bpy.types.Operator):
    """Удалить выделенные объекты из их IPL и снять привязку.

Объекты остаются в Blender, их inst-строки удаляются из того IPL, к которому
они привязаны. LOD модели удаляется тоже (если он не нужен другой модели).
lod_index всех остальных строк пересчитывается"""
    bl_idname = "gtatools.ipl_remove_link"
    bl_label = "INU: Remove from IPL"
    bl_options = {'REGISTER'}

    last_message = ""

    # Оставлено для совместимости вызовов из панели: каждая модель и так
    # удаляется из СВОЕГО IPL; пустой — то же самое.
    target_file: StringProperty(default="", options={'HIDDEN'})

    def _run(self, context, dry_run):
        return map_link.ipl_remove(
            context, _sel_meshes(context),
            picked=context.scene.inu_settings.gtatools_ipl_path,
            dry_run=dry_run)

    def execute(self, context):
        if not _sel_meshes(context):
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        rep = self._run(context, False)
        GTATOOLS_OT_ipl_remove_link.last_message = map_link.report_to(
            self, "IPL", rep, pub=_pub)
        return {'FINISHED'}


class GTATOOLS_OT_ipl_verify_links(bpy.types.Operator):
    """Проверить IPL-привязки, ничего не двигая.

Привязанные модели ищут свою строку; если её больше нет — привязка снимается.
Непривязанные узнаются по строке своей модели рядом (0.5 м) или по
единственной свободной строке этой модели. Пустое выделение — вся сцена"""
    bl_idname = "gtatools.ipl_verify_links"
    bl_label = "INU: Verify IPL Links"
    bl_options = {'REGISTER'}

    last_message = ""

    def execute(self, context):
        valid, _missing = _ipl_sync_targets(context.scene.inu_settings)
        sel = _sel_meshes(context) or [o for o in bpy.data.objects
                                        if o.type == 'MESH']
        rep = map_link.ipl_pull(context, sel, valid, move=False, far='unique',
                                clear_lost=True)
        GTATOOLS_OT_ipl_verify_links.last_message = map_link.report_to(
            self, T("IPL Проверка"), rep, pub=_pub)
        return {'FINISHED'}


class GTATOOLS_OT_ide_sync_from_file(bpy.types.Operator):
    """Синхронизация Blender ↔ IDE.

    Bi-directional, аналогично Sync для IPL:
      • Если model_id объекта найден в IDE → подтягивает draw_distance,
        txd_name, flags из IDE в obj.inu props.  Это автолинковка после
        Map Import и кейс пост-внешней-правки IDE.
      • Если model_id не найден → пропускает (записи нет, нечего тянуть).

    Работает по выделению; пустое выделение = всё meshes сцены.
    """
    bl_idname = "gtatools.ide_sync_from_file"
    bl_label = "INU: Sync from IDE"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..core.ide import read_ide
        s = context.scene.inu_settings
        root = bpy.path.abspath(s.gtatools_game_root)
        single = bpy.path.abspath(s.gtatools_ide_path)
        # Все IDE: если задана папка игры — ВСЕ .ide из неё (по gta.dat/скан);
        # иначе — один выбранный файл.
        ide_files = []
        if root and os.path.isdir(root):
            from ..core.gta_dat import list_ide_files
            ide_files = [p for p in list_ide_files(root) if os.path.isfile(p)]
        if not ide_files and single and os.path.isfile(single):
            ide_files = [single]
        if not ide_files:
            self.report({'ERROR'}, T("Нет IDE: укажи файл или папку игры"))
            return {'CANCELLED'}

        # model_id → (entry, файл-источник). objs+anims в одном id-пространстве.
        # Первый источник побеждает.
        # Матч и по id, и по ИМЕНИ модели: объект без Model ID тоже подтянется,
        # если его имя есть в IDE (заодно проставим ему id из IDE).
        from .. import _clean_model_name_ide
        from ..core.ipl import is_lod_name, strip_lod_marker
        from ..tools.model_utils import get_model_type
        by_id = {}
        by_name = {}
        lod_by_base = {}     # LOD-строки IDE по базовому имени модели
        for fp in ide_files:
            try:
                ide = read_ide(fp)
            except Exception:
                continue
            for e in list(ide.objects) + list(ide.anims):
                by_id.setdefault(int(e.model_id), (e, fp))
                nm = (getattr(e, 'model_name', '') or '').strip().lower()
                if nm:
                    by_name.setdefault(nm, (e, fp))
                    if is_lod_name(nm):
                        lod_by_base.setdefault(
                            strip_lod_marker(nm).lower(), (e, fp))

        sel = [o for o in context.selected_objects if o.type == 'MESH']
        if not sel:
            sel = [o for o in context.scene.objects if o.type == 'MESH']

        linked = 0
        skipped = 0
        skip_reasons = {'not_found': 0}
        for obj in sel:
            inu = getattr(obj, 'inu', None)
            if inu is None:
                skipped += 1
                continue
            mid = int(inu.model_id) if inu.model_id else 0
            cname = _clean_model_name_ide(obj.name).lower()
            is_lod_obj = get_model_type(obj)[0] == 'LOD'
            # Имя — стабильный ключ (ловит ИЗМЕНЁННЫЙ в IDE id); id — запасной
            # (если объект переименован в Blender, а имя уже не совпадает).
            # LOD-объект сопоставляется ТОЛЬКО со строкой LOD (раньше базовое
            # имя «rialto_3_LOD» → «rialto_3» цепляло строку самой модели, и
            # LOD получал её ID/имя → в IPL вместо LOD писалась копия модели).
            if is_lod_obj:
                entry_src = (by_name.get('lod' + cname)
                             or lod_by_base.get(cname))
            else:
                entry_src = by_name.get(cname)
            if entry_src is None and mid > 0:
                entry_src = by_id.get(mid)
            if entry_src is not None:
                _enm = str(getattr(entry_src[0], 'model_name', '') or '')
                if is_lod_name(_enm) != is_lod_obj:
                    entry_src = None      # модель ↔ LOD-строка: не пара
            if entry_src is None:
                skipped += 1
                skip_reasons['not_found'] += 1
                continue
            entry, src_file = entry_src
            # Файл — источник истины: подтягиваем Model ID из IDE (в т.ч. если
            # его поменяли в файле или у объекта его не было).
            _eid = int(getattr(entry, 'model_id', 0))
            if _eid > 0 and _eid != mid:
                inu.model_id = _eid
            # Pull file → Blender. У LOD дистанция из IDE — это его LOD Dist.
            _dd = float(getattr(entry, 'draw_distance', 0.0))
            if is_lod_obj:
                inu.lod_draw_distance = _dd
            else:
                inu.draw_distance = _dd
            inu.txd_name = str(getattr(entry, 'txd_name', '') or '')
            inu.ide_flags = int(getattr(entry, 'flags', 0))
            inu.ide_target_file = src_file
            inu.ide_last_draw_distance = _dd
            inu.ide_last_txd_name = inu.txd_name
            inu.ide_last_flags = inu.ide_flags
            inu.ide_last_model_id = int(getattr(inu, 'model_id', 0) or 0)
            inu.ide_last_name = str(getattr(entry, 'model_name', '') or '')
            inu.ide_linked = True
            linked += 1

        if skipped:
            print(f"[IDE Sync] skipped (нет ни по id, ни по имени): "
                  f"{skip_reasons['not_found']}")
        msg = T("Sync IDE: linked {0}, пропущено {1} ({2} IDE)").format(
            linked, skipped, len(ide_files))
        GTATOOLS_OT_ide_sync_from_file.last_message = msg
        _pub(self, 'INFO', msg)
        return {'FINISHED'}


class GTATOOLS_OT_ide_remove_link(ConfirmOnProblems, bpy.types.Operator):
    """Удалить выделенные модели из их IDE и снять привязку.
    Строка удаляется, только если под этим ID в файле именно эта модель.
    LOD модели удаляется вместе с ней."""
    bl_idname = "gtatools.ide_remove_link"
    bl_label = "INU: Unlink from IDE"
    bl_options = {'REGISTER'}

    last_message = ""

    # Совместимость с панелью: каждая модель удаляется из СВОЕГО IDE.
    target_file: StringProperty(default="", options={'HIDDEN'})

    def _run(self, context, dry_run):
        return map_link.ide_remove(
            context, _sel_meshes(context),
            picked=context.scene.inu_settings.gtatools_ide_path,
            dry_run=dry_run)

    def execute(self, context):
        if not _sel_meshes(context):
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        rep = self._run(context, False)
        GTATOOLS_OT_ide_remove_link.last_message = map_link.report_to(
            self, "IDE", rep, pub=_pub)
        return {'FINISHED'}


class GTATOOLS_OT_ide_verify_links(bpy.types.Operator):
    """Проверить, что model_id всех выделенных объектов есть в IDE.
    Сообщает: present (есть), missing (нет), zero_id (Model ID не задан)."""
    bl_idname = "gtatools.ide_verify_links"
    bl_label = "INU: Verify IDE Links"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.ide import read_ide
        picked = bpy.path.abspath(context.scene.inu_settings.gtatools_ide_path)

        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            objs = [o for o in bpy.data.objects if o.type == 'MESH']

        # Кэш прочитанных id по файлу — объекты могут ссылаться на РАЗНЫЕ IDE.
        _ids_cache = {}

        def _ids_for(fp):
            fp = bpy.path.abspath(fp or '')
            if not fp or not os.path.isfile(fp):
                return None
            key = os.path.normcase(fp)
            if key not in _ids_cache:
                try:
                    ide = read_ide(fp)
                    ids = set()
                    for e in ide.objects:
                        ids.add(int(e.model_id))
                    for e in ide.anims:
                        ids.add(int(e.model_id))
                    _ids_cache[key] = ids
                except Exception:
                    _ids_cache[key] = None
            return _ids_cache[key]

        present = missing = zero_id = cleared = 0
        missing_samples = []
        for o in objs:
            inu = o.inu
            mid = int(getattr(inu, 'model_id', 0) or 0)
            if mid <= 0:
                zero_id += 1
                continue
            # Проверяем в РОДНОМ IDE модели (ide_target_file), иначе в выбранном.
            ids = _ids_for(getattr(inu, 'ide_target_file', '') or picked)
            if ids is None:
                continue
            if mid in ids:
                present += 1
            else:
                missing += 1
                # model_id больше нет в этом IDE (напр. скопировал модель и
                # сменил ID) → снять устаревшую привязку, чтобы статус стал
                # «Не в IDE».
                if getattr(inu, 'ide_linked', False):
                    inu.ide_linked = False
                    cleared += 1
                if len(missing_samples) < 5:
                    missing_samples.append(f"{o.name!r} (id={mid})")

        if missing_samples:
            print("[IDE Verify] missing sample:")
            for s in missing_samples:
                print(f"  {s}")
        msg = T("IDE Verify: есть {0}, нет {1}, снято {3}, без ID {2}").format(
            present, missing, zero_id, cleared)
        GTATOOLS_OT_ide_verify_links.last_message = msg
        _pub(self, 'INFO', msg)
        return {'FINISHED'}


def _run_with_override(context, op_callable):
    """Invoke ``op_callable`` via ``bpy.ops`` with the wrapper's live
    context explicitly forwarded.

    Wrappers (link_sync / link_unlink / link_verify) are invoked from
    the floater through ``bpy.app.timers``.  The timer callback runs
    on an idle tick — by then Blender's ``context`` for ``bpy.ops``
    has been reset to a stripped-down "background" form that no
    longer exposes ``selected_objects`` / ``active_object``.  Nested
    ``bpy.ops.x.y('EXEC_DEFAULT')`` from inside our wrapper's
    ``execute()`` inherits THAT stripped context and silently does
    nothing.

    ``context.temp_override(**state)`` (Blender 3.2+) tells the
    bpy.ops dispatcher to use the supplied attributes for the
    duration of the nested call.  We forward the scene-level prop
    bag, the selection, and the active object — enough for any
    operator that reads ``context.selected_objects`` or
    ``context.scene``.
    """
    override = {
        'scene': context.scene,
        'window': context.window,
        'screen': context.screen,
        'area': context.area,
        'region': context.region,
        'view_layer': context.view_layer,
        'selected_objects': list(getattr(context, 'selected_objects', [])),
        'active_object': getattr(context, 'active_object', None),
        'object': getattr(context, 'object', None),
    }
    # Drop None entries — temp_override rejects them silently but a
    # cleaner dict makes debugging easier.
    override = {k: v for k, v in override.items() if v is not None}
    # temp_override (3.2+) с fallback на legacy dict-override для 2.83-3.1.
    run_op_override(op_callable, override, 'EXEC_DEFAULT')


def _show_status_text(context, text: str, hold_seconds: float = 6.0):
    """Push *text* to Blender's bottom status bar via
    ``window_manager.status_text_set`` and auto-clear after a few
    seconds.

    Why: operator ``self.report({'INFO'}, ...)`` from inside a
    wrapper invoked from ``bpy.app.timers`` lands in the Info log
    but DOES NOT update the status bar shown at the bottom of the
    Blender window — that bar is driven by the user-invoked
    operator's last report only.  Setting ``status_text_set``
    explicitly bypasses the dispatch chain and writes the text
    directly onto the visible bar so the user sees the same line
    they'd see when clicking the N-panel button.
    """
    try:
        wm = context.window_manager
        if wm is None:
            return
        wm.status_text_set(text)
    except Exception as ex:
        print(f"[INU] status_text_set failed: {ex}")
        return

    def _clear():
        try:
            wm.status_text_set(None)
        except Exception:
            pass
        return None

    try:
        bpy.app.timers.register(_clear, first_interval=hold_seconds)
    except Exception:
        pass


class GTATOOLS_OT_link_sync(bpy.types.Operator):
    """Sync для обоих файлов: IDE + IPL.

    Не добавляет свой собственный финальный report — это бы перетёрло
    детальный отчёт inner-операторов в status-bar Blender'а
    («Sync: linked 0, обновлено 0, пропущено 2 — все без Model ID»).
    Сохраняем info-сообщение последнего inner-вызова видимым.
    """
    bl_idname = "gtatools.link_sync"
    bl_label = "INU: Sync IDE+IPL"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        GTATOOLS_OT_ide_sync_from_file.last_message = ""
        GTATOOLS_OT_ipl_sync_from_file.last_message = ""
        try:
            _run_with_override(context, bpy.ops.gtatools.ide_sync_from_file)
        except Exception as ex:
            GTATOOLS_OT_ide_sync_from_file.last_message = str(ex)
        try:
            _run_with_override(context, bpy.ops.gtatools.ipl_sync_from_file)
        except Exception as ex:
            GTATOOLS_OT_ipl_sync_from_file.last_message = str(ex)
        parts = [m for m in (
            GTATOOLS_OT_ide_sync_from_file.last_message,
            GTATOOLS_OT_ipl_sync_from_file.last_message,
        ) if m]
        if parts:
            msg = "  |  ".join(parts)
            _pub(self, 'INFO', msg)
            _show_status_text(context, msg)
        return {'FINISHED'}


class GTATOOLS_OT_link_unlink(bpy.types.Operator):
    """Unlink из обоих файлов: IDE + IPL для выделенных объектов."""
    bl_idname = "gtatools.link_unlink"
    bl_label = "INU: Unlink IDE+IPL"
    bl_options = {'REGISTER'}

    def execute(self, context):
        GTATOOLS_OT_ide_remove_link.last_message = ""
        GTATOOLS_OT_ipl_remove_link.last_message = ""
        try:
            _run_with_override(context, bpy.ops.gtatools.ide_remove_link)
        except Exception as ex:
            GTATOOLS_OT_ide_remove_link.last_message = str(ex)
        try:
            _run_with_override(context, bpy.ops.gtatools.ipl_remove_link)
        except Exception as ex:
            GTATOOLS_OT_ipl_remove_link.last_message = str(ex)
        parts = [m for m in (
            GTATOOLS_OT_ide_remove_link.last_message,
            GTATOOLS_OT_ipl_remove_link.last_message,
        ) if m]
        if parts:
            msg = "  |  ".join(parts)
            _pub(self, 'INFO', msg)
            _show_status_text(context, msg)
        return {'FINISHED'}


class GTATOOLS_OT_link_verify(bpy.types.Operator):
    """Verify обоих: IDE-ссылок (по model_id) + IPL-ссылок (строка ищется по содержимому)."""
    bl_idname = "gtatools.link_verify"
    bl_label = "INU: Verify IDE+IPL Links"
    bl_options = {'REGISTER'}

    def execute(self, context):
        GTATOOLS_OT_ide_verify_links.last_message = ""
        GTATOOLS_OT_ipl_verify_links.last_message = ""
        try:
            _run_with_override(context, bpy.ops.gtatools.ide_verify_links)
        except Exception as ex:
            GTATOOLS_OT_ide_verify_links.last_message = str(ex)
        try:
            _run_with_override(context, bpy.ops.gtatools.ipl_verify_links)
        except Exception as ex:
            GTATOOLS_OT_ipl_verify_links.last_message = str(ex)
        parts = [m for m in (
            GTATOOLS_OT_ide_verify_links.last_message,
            GTATOOLS_OT_ipl_verify_links.last_message,
        ) if m]
        if parts:
            msg = "  |  ".join(parts)
            _pub(self, 'INFO', msg)
            _show_status_text(context, msg)
        return {'FINISHED'}


class GTATOOLS_OT_remove_ide(ConfirmOnProblems, bpy.types.Operator):
    """Del: удалить строки ВЫДЕЛЕННЫХ моделей (и их LOD) из выбранного .ide. Удаляет только если под этим ID в файле именно эта модель"""
    bl_idname = "gtatools.remove_ide"
    bl_label = "INU: Remove from IDE"
    bl_options = {'REGISTER'}

    def _run(self, context, dry_run):
        return map_link.ide_remove(
            context, _sel_meshes(context),
            target=context.scene.inu_settings.gtatools_ide_path,
            dry_run=dry_run)

    def execute(self, context):
        if not _sel_meshes(context):
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        rep = self._run(context, False)
        map_link.report_to(self, "IDE", rep, pub=_pub)
        return {'FINISHED'}


class GTATOOLS_OT_remove_ipl(ConfirmOnProblems, bpy.types.Operator):
    """Del: удалить расстановку ВЫДЕЛЕННЫХ моделей (и их LOD) из выбранного .ipl. Выделенный LOD без модели — отвязывается от своих моделей"""
    bl_idname = "gtatools.remove_ipl"
    bl_label = "INU: Remove from IPL"
    bl_options = {'REGISTER'}

    def _run(self, context, dry_run):
        return map_link.ipl_remove(
            context, _sel_meshes(context),
            target=context.scene.inu_settings.gtatools_ipl_path,
            dry_run=dry_run)

    def execute(self, context):
        if not _sel_meshes(context):
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        rep = self._run(context, False)
        map_link.report_to(self, "IPL", rep, pub=_pub)
        return {'FINISHED'}


def _ensure_extension(filepath: str, ext: str) -> str:
    """Append ``ext`` (e.g. '.ide') to ``filepath`` if it isn't already
    there (case-insensitive). Operators here don't use ExportHelper so
    Blender's file dialog happily accepts ``hospital_1a`` without the
    extension and we'd silently write an extensionless file — which the
    user has to rename by hand before the game / IMG editor will load
    it.

    Edge cases:
      * Empty / None input → returned as-is (caller already handles
        empty paths elsewhere).
      * Path already ends with ``ext`` (any casing) → unchanged.
      * Path ends with a different extension (e.g. user typed
        ``foo.txt``) → still appended so we get ``foo.txt.ide``. The
        ``filter_glob='*.ide'`` makes that unlikely in practice but
        keeping the rule simple beats "smart" replacement that could
        mangle filenames with dots in them.
    """
    if not filepath:
        return filepath
    if filepath.lower().endswith(ext.lower()):
        return filepath
    return filepath + ext


class GTATOOLS_OT_export_ide(bpy.types.Operator):
    """Export: сохранить определения ВЫДЕЛЕННЫХ моделей в НОВЫЙ .ide-файл (диалог сохранения). Отличие от Add: создаёт отдельный файл, а не дописывает в уже выбранный"""
    bl_idname = "gtatools.export_ide"
    bl_label = "INU: Export IDE (.ide)"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.ide", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "model.ide"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .ide_export import export_ide as inu_export_ide
        self.filepath = _ensure_extension(self.filepath, ".ide")
        try:
            objs = [o for o in context.selected_objects if o.type == 'MESH']
            inu_export_ide(filepath=self.filepath, objects=objs)
            from .textdata_audit import audit_ide_file
            audit_ide_file(self, self.filepath)
            self.report({'INFO'}, f"Exported IDE: {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"IDE export error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_export_ipl(bpy.types.Operator):
    """Export: сохранить расстановку ВЫДЕЛЕННЫХ моделей в НОВЫЙ .ipl-файл (диалог сохранения). Отличие от Add: создаёт отдельный файл, а не дописывает в уже выбранный"""
    bl_idname = "gtatools.export_ipl"
    bl_label = "INU: Export IPL (.ipl)"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.ipl", options={'HIDDEN'})
    binary: BoolProperty(
        name="Binary (bnry)",
        description=T("Писать IPL в бинарном формате (только inst+cars)"),
        default=False,
    )

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "model.ipl"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "binary")

    def execute(self, context):
        from .ipl_export import export_ipl as inu_export_ipl
        self.filepath = _ensure_extension(self.filepath, ".ipl")
        try:
            objs = [o for o in context.selected_objects if o.type == 'MESH']
            inu_export_ipl(filepath=self.filepath, objects=objs, binary=self.binary)
            from .textdata_audit import audit_ipl_file
            audit_ipl_file(self, self.filepath, context, binary=self.binary)
            self.report({'INFO'}, f"Exported IPL: {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"IPL export error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_import_ipl_sections(bpy.types.Operator):
    """Импорт секций IPL (cull, grge, enex, pick, cars, auzo, jump, occl)"""
    bl_idname = "gtatools.import_ipl_sections"
    bl_label = "INU: Import IPL Sections"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.ipl", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from ..core.ipl import read_ipl
        from .ipl_sections import import_ipl_sections
        try:
            ipl = read_ipl(self.filepath)
            result = import_ipl_sections(ipl)
            total = sum(len(v) for v in result.values())
            sections = ", ".join(f"{k}: {len(v)}" for k, v in result.items() if v)
            self.report({'INFO'}, f"{T('Импортировано:')} {total} ({sections})")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"IPL sections import: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_export_ipl_sections(bpy.types.Operator):
    """Экспорт секций IPL из коллекций IPL_* в файл"""
    bl_idname = "gtatools.export_ipl_sections"
    bl_label = "INU: Export IPL Sections"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.ipl", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "sections.ipl"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from ..core.ipl import IplFile, write_ipl
        from .ipl_sections import export_ipl_sections
        self.filepath = _ensure_extension(self.filepath, ".ipl")
        try:
            sections = export_ipl_sections()
            ipl = IplFile(
                culls=sections.get('cull', []),
                garages=sections.get('grge', []),
                enexs=sections.get('enex', []),
                pickups=sections.get('pick', []),
                cars=sections.get('cars', []),
                auzos=sections.get('auzo', []),
                jumps=sections.get('jump', []),
                occls=sections.get('occl', []),
                zones=sections.get('zone', []),
            )
            from ..core import game_versions as gv
            write_ipl(self.filepath, ipl,
                      game=gv.game_of_scene(context.scene))
            from .textdata_audit import audit_ipl_file
            audit_ipl_file(self, self.filepath, context)
            total = sum(len(v) for v in sections.values())
            self.report({'INFO'}, f"Exported {total} IPL section entries")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"IPL sections export: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_import_ide(bpy.types.Operator):
    """Import: загрузить .ide (диалог) и сопоставить определения (id, txd, дистанция, флаги) с моделями в сцене по имени. Геометрию не грузит — только свойства"""
    bl_idname = "gtatools.import_ide"
    bl_label = "INU: Import IDE (.ide)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.ide", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .ide_import import import_ide as inu_import_ide
        try:
            matched = inu_import_ide(filepath=self.filepath, context=context)
            self.report({'INFO'}, f"IDE: {len(matched)} objects matched")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"IDE import error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_import_ipl(bpy.types.Operator):
    """Import: загрузить .ipl (диалог) и расставить объекты по позициям из файла (модели без геометрии — как Empty-заглушки). Геометрию тянет «Импорт из IMG»"""
    bl_idname = "gtatools.import_ipl"
    bl_label = "INU: Import IPL (.ipl)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.ipl", options={'HIDDEN'})

    import_game: bpy.props.EnumProperty(
        name=T("Игра"),
        description=T("Из какой игры импортируем IPL. Auto — по числу колонок в inst-секции"),
        items=[
            ('AUTO', T("Авто-определение"), ""),
            ('III',  "GTA III",  ""),
            ('VC',   "Vice City", ""),
            ('SA',   "San Andreas", ""),
        ],
        default='AUTO')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        self.layout.prop(self, "import_game")

    def execute(self, context):
        from .ipl_import import import_ipl as inu_import_ipl
        try:
            placed = inu_import_ipl(filepath=self.filepath, context=context)
            from ..core import game_versions as gv
            if self.import_game == 'AUTO':
                detected = gv.detect_game_from_ipl(self.filepath)
            else:
                detected = self.import_game
            switched = gv.maybe_set_game_from_import(context.scene, detected)
            tag = f" → game={detected}" if switched else ""
            self.report({'INFO'}, f"IPL: {len(placed)} objects placed{tag}")
            if not switched:
                warn = gv.check_game_mismatch_warning(context.scene, detected)
                if warn:
                    self.report({'WARNING'}, warn)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"IPL import error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_replace_ipl_placeholders(bpy.types.Operator):
    """Заменить IPL Empty-плейсхолдеры на модели из сцены"""
    bl_idname = "gtatools.replace_ipl_placeholders"
    bl_label = "INU: Replace IPL Placeholders"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        replaced = 0
        # Build lookup from scene meshes
        mesh_lookup = {}
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                from .. import _clean_name_typed_ipl
                clean, stype = _clean_name_typed_ipl(obj.name)
                low = clean.lower()
                if low not in mesh_lookup:
                    mesh_lookup[low] = {}
                if stype not in mesh_lookup[low]:
                    mesh_lookup[low][stype] = obj

        for obj in list(bpy.data.objects):
            if obj.type != 'EMPTY' or not obj.get('ipl_placeholder'):
                continue

            model_name = obj.get('ipl_model_name', obj.name.replace('_empty', ''))
            key = model_name.lower()
            from ..core.ipl import is_lod_name, strip_lod_marker
            is_lod = is_lod_name(model_name)

            # Find matching mesh
            mesh_obj = None
            if is_lod:
                base = strip_lod_marker(model_name).lower()
                variants = mesh_lookup.get(base, {})
                mesh_obj = variants.get('LOD') or variants.get('DFF')
            else:
                variants = mesh_lookup.get(key, {})
                mesh_obj = variants.get('DFF') or variants.get('OTHER')

            if not mesh_obj:
                continue

            # Move existing model to placeholder position
            mesh_obj.location = obj.location.copy()
            mesh_obj.rotation_mode = 'QUATERNION'
            mesh_obj.rotation_quaternion = obj.rotation_quaternion.copy()

            # Copy IPL properties
            mesh_obj.inu.model_id = obj.inu.model_id
            mesh_obj.inu.interior_id = obj.inu.interior_id
            mesh_obj.inu.lod_index = obj.inu.lod_index

            # Remove placeholder
            bpy.data.objects.remove(obj, do_unlink=True)
            replaced += 1

        self.report({'INFO'}, f"{T('Заменено:')} {replaced}")
        return {'FINISHED'}


