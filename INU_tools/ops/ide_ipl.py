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


def _find_inst_index_by_name(ipl, model_name):
    """Index of the first IPL instance whose model_name matches (case-
    insensitive), or -1. Used to recover a DFF's ``lod_index`` when its LOD
    isn't part of the current selection (#2)."""
    target = (model_name or '').lower()
    for i, inst in enumerate(ipl.instances):
        if (inst.model_name or '').lower() == target:
            return i
    return -1


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


class GTATOOLS_OT_upsert_ide(bpy.types.Operator):
    """Add: записать/обновить ВЫДЕЛЕННЫЕ модели в ВЫБРАННЫЙ .ide (id, txd, дистанция, флаги). Обновляет существующие строки на месте; LOD-пары связываются автоматически. Для новых моделей нужен Model ID. Отличие от Export: пишет в уже выбранный файл, а не создаёт новый"""
    bl_idname = "gtatools.upsert_ide"
    bl_label = "INU: Add to IDE"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Маршрутизация по объекту: уже связанную модель обновляем в ЕЁ IDE
        # (ide_target_file); новые — в выбранный gtatools_ide_path.
        single = bpy.path.abspath(context.scene.inu_settings.gtatools_ide_path) or ''
        if single and not single.lower().endswith('.ide'):
            self.report({'WARNING'},
                        T("Путь IDE — не .ide файл, проверь бокс IDE"))
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        # #1/#5: block writing a model_id == 0 row (id 0 = player model →
        # corrupts the game); warn on a LOD borrowing an already-owned id+1.
        if _report_id_validation(self, objs):
            return {'CANCELLED'}
        groups = {}
        redirected = 0
        for o in objs:
            inu = getattr(o, 'inu', None)
            tgt = (bpy.path.abspath(inu.ide_target_file)
                   if (inu and inu.ide_linked and inu.ide_target_file) else '')
            if single:
                # Chosen IDE wins (see upsert_ipl note) — no silent routing to
                # a previously-linked file.
                key = single
                if (tgt and os.path.isfile(tgt)
                        and os.path.normcase(tgt) != os.path.normcase(single)):
                    redirected += 1
            else:
                key = tgt if (tgt and os.path.isfile(tgt)) else ''
            if key:
                groups.setdefault(key, []).append(o)
        if not groups:
            self.report({'ERROR'}, T("Укажите путь к IDE файлу"))
            return {'CANCELLED'}
        total_u = total_a = total_dff = total_lod = 0
        for _fp, _grp in groups.items():
            u, a, ndff, nlod = self._upsert_into(context, _fp, _grp)
            total_u += u
            total_a += a
            total_dff += ndff
            total_lod += nlod
        msg = (f"IDE: {T('обновлено')} {total_u}, {T('добавлено')} {total_a} "
               f"(DFF {total_dff}, LOD {total_lod})")
        if redirected:
            msg += " — " + T("{0} были в другом IDE (проверь дубли)").format(redirected)
        _pub(self, 'INFO', msg)
        return {'FINISHED'}

    def _upsert_into(self, context, filepath, objs):
        """Upsert выделенных `objs` в IDE `filepath`. Возвращает (updated, added)."""
        from ..core.ide import upsert_ide

        entries = []
        n_dff = n_lod = 0     # для детального отчёта (сколько DFF / LOD строк)

        # Classify every object ONCE, then group by base name. This used
        # to be O(N²) — a nested get_model_type loop over the whole
        # selection — which froze the UI for minutes when a big map had
        # thousands of selected meshes. Now it's a single O(N) pass.
        from ..tools.model_utils import get_model_type
        from .. import _ide_entry_from_obj, _clean_model_name_ide

        by_base = {}   # base -> {'DFF': obj, 'LOD': obj}
        order = []     # base names in first-seen order
        for obj in objs:
            model_type, base_name = get_model_type(obj)
            slot = by_base.get(base_name)
            if slot is None:
                slot = {}
                by_base[base_name] = slot
                order.append(base_name)
            if model_type in ('DFF', 'LOD') and model_type not in slot:
                slot[model_type] = obj

        for base_name in order:
            slot = by_base[base_name]
            dff_obj = slot.get('DFF')
            lod_obj = slot.get('LOD')

            if dff_obj:
                entries.append(_ide_entry_from_obj(dff_obj))
                n_dff += 1
            if lod_obj:
                lod_entry = _ide_entry_from_obj(lod_obj)
                # LOD model name: LOD + base_name
                lod_entry.model_name = "LOD" + base_name
                # LOD shares the model's TXD: prefer the paired DFF's TXD,
                # then the LOD's own, else the cleaned base name.
                dff_txd = ((getattr(dff_obj.inu, 'txd_name', '') or '').strip()
                           if dff_obj else '')
                lod_txd = (lod_entry.txd_name or '').strip()
                lod_entry.txd_name = (dff_txd or lod_txd
                                      or _clean_model_name_ide(base_name))
                # LOD model_id = DFF model_id + 1 if the LOD has no ID.
                if lod_entry.model_id == 0 and dff_obj:
                    dff_id = getattr(dff_obj.inu, 'model_id', 0)
                    if dff_id > 0:
                        lod_entry.model_id = dff_id + 1
                # LOD дистанция: у парной DFF — из её LOD Dist. Без пары
                # _ide_entry_from_obj уже берёт lod_draw_distance самого LOD
                # (LOD-модель пишется по своей LOD Dist), отдельный форс не нужен.
                if dff_obj:
                    lod_entry.draw_distance = dff_obj.inu.lod_draw_distance
                entries.append(lod_entry)
                n_lod += 1

        # Validate model IDs
        zero_ids = [e for e in entries if e.model_id == 0]
        if zero_ids:
            self.report({'WARNING'}, f"{len(zero_ids)} {T('объектов с Model ID = 0, задайте ID в свойствах')}")

        # Какие model_id уже есть в файле ДО upsert — чтобы отличить реальное
        # обновление строки от дописывания дубликата (id не совпал).
        existing_ids = set()
        try:
            if os.path.isfile(filepath):
                from ..core.ide import read_ide
                existing_ids = {o.model_id for o in read_ide(filepath).objects}
        except Exception:                             # noqa: BLE001
            existing_ids = set()

        updated, added = upsert_ide(filepath, entries)

        # Предупреждение (A): объект уже был привязан к IDE (юзер ждал ОБНОВЛЕНИЯ),
        # но его model_id нет в файле → правка ушла НОВОЙ строкой-дубликатом, а
        # существующую не тронула. Частая причина «правка дистанции не
        # регистрируется». На первом добавлении (ide_linked=False) молчим.
        # ВАЖНО: считаем ДО штамповки ниже — она ставит ide_linked=True всем.
        dup = sorted({o.name for o in objs
                      if getattr(getattr(o, 'inu', None), 'ide_linked', False)
                      and getattr(o.inu, 'model_id', 0) > 0
                      and o.inu.model_id not in existing_ids})
        if dup:
            shown = ", ".join(dup[:3]) + ("…" if len(dup) > 3 else "")
            self.report({'WARNING'}, T(
                "IDE: id не найден в файле для: {0} — правка ушла в НОВУЮ строку "
                "(дубликат), существующая не обновлена. Проверь Model ID объекта"
            ).format(shown))

        # ── Record last-exported state for drift detection ──
        # After a successful upsert, stamp every selected obj with the
        # fields it just sent to IDE.  The N-panel uses these to show
        # a "В IDE / координаты разошлись / Не в IDE" status, and the
        # Sync operator uses them to pull file→Blender.
        for obj in objs:
            inu = getattr(obj, 'inu', None)
            if inu is None or inu.model_id <= 0:
                continue
            inu.ide_target_file = filepath
            inu.ide_last_draw_distance = inu.draw_distance
            inu.ide_last_txd_name = inu.txd_name
            inu.ide_last_flags = inu.ide_flags
            inu.ide_last_model_id = int(getattr(inu, 'model_id', 0) or 0)
            inu.ide_linked = True

        return updated, added, n_dff, n_lod


class GTATOOLS_OT_upsert_ipl(bpy.types.Operator):
    """Add: записать/обновить РАССТАНОВКУ выделенных моделей в ВЫБРАННЫЙ .ipl (позиция + поворот). Перемещённую модель обновляет на месте (не плодит дубли), LOD-привязка авто. Отличие от Export: пишет в уже выбранный файл, а не создаёт новый"""
    bl_idname = "gtatools.upsert_ipl"
    bl_label = "INU: Add to IPL"
    bl_options = {'REGISTER'}

    last_message = ""

    def execute(self, context):
        # ── Маршрутизация по объекту ──
        # Уже отслеживаемую модель обновляем в ЕЁ файле (ipl_target_file),
        # даже если справа выбран другой IPL; новые (без файла) — в выбранный
        # gtatools_ipl_path. Группируем по файлу → один upsert на файл.
        single = bpy.path.abspath(context.scene.inu_settings.gtatools_ipl_path) or ''
        if single and not single.lower().endswith('.ipl'):
            self.report({'WARNING'},
                        T("Путь IPL — не .ipl файл, проверь бокс IPL"))
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        # Подтянуть LOD-партнёров: у выделенных DFF с заполненным «LOD partner»
        # (inu.lod_object) их LOD тоже уходит в IPL и связывается по lod_index,
        # даже если сам LOD не выделен. Если у LOD ещё нет Model ID — назначаем
        # DFF+1 (та же эвристика, что и при записи LOD; видно в поле «LOD ID»,
        # при коллизии оператор предупредит ниже).
        _present = {id(o) for o in objs}
        _lod_extra = []
        for o in objs:
            _lodo = getattr(getattr(o, 'inu', None), 'lod_object', None)
            if (_lodo is None or getattr(_lodo, 'type', None) != 'MESH'
                    or id(_lodo) in _present):
                continue
            _lodi = getattr(_lodo, 'inu', None)
            if _lodi is None:
                continue
            if int(getattr(_lodi, 'model_id', 0) or 0) == 0:
                _did = int(getattr(o.inu, 'model_id', 0) or 0)
                if _did > 0:
                    _lodi.model_id = _did + 1
            _lod_extra.append(_lodo)
            _present.add(id(_lodo))
        objs += _lod_extra
        # #1/#5: block writing a model_id == 0 row (id 0 = player model →
        # corrupts the game); warn on a LOD borrowing an already-owned id+1.
        if _report_id_validation(self, objs):
            return {'CANCELLED'}
        groups = {}
        redirected = 0
        for o in objs:
            tgt = (bpy.path.abspath(o.inu.ipl_target_file)
                   if o.inu.ipl_target_file else '')
            if single:
                # The explicitly chosen IPL wins. Routing each object back to
                # its remembered `ipl_target_file` silently «wrote to other
                # files» AND split a DFF from its LOD across files, which broke
                # LOD linking. Per-object routing now only kicks in when no
                # file is picked.
                key = single
                if (tgt and os.path.isfile(tgt)
                        and os.path.normcase(tgt) != os.path.normcase(single)):
                    redirected += 1
            else:
                key = tgt if (tgt and os.path.isfile(tgt)) else ''
            if key:
                groups.setdefault(key, []).append(o)
        if not groups:
            self.report({'ERROR'}, T("Укажите путь к IPL файлу"))
            return {'CANCELLED'}
        total_u = total_a = total_dff = total_lod = 0
        for _fp, _grp in groups.items():
            u, a, ndff, nlod = self._upsert_into(context, _fp, _grp)
            total_u += u
            total_a += a
            total_dff += ndff
            total_lod += nlod
        if redirected:
            self.report({'WARNING'},
                        T("{0} объектов были привязаны к другому IPL — записаны "
                          "в выбранный (проверь дубли в старом файле)").format(
                              redirected))
        # (model_id == 0 is now blocked up-front in execute() before any
        # write — see _report_id_validation.)
        msg = (f"IPL: {T('обновлено')} {total_u}, {T('добавлено')} {total_a} "
               f"(DFF {total_dff}, LOD {total_lod})")
        if len(groups) > 1:
            msg += " — " + T("записи разнесены по {0} IPL-файлам").format(len(groups))
        # Текст кладётся в класс: когда этот оператор вызывают через
        # bpy.ops из другого (кнопка «Add» в боксе модели идёт через
        # ipl_sync_export), Blender баннер вложенного оператора гасит, и
        # пользователь не видит ничего. Обёртка достаёт текст отсюда.
        GTATOOLS_OT_upsert_ipl.last_message = msg
        _pub(self, 'INFO', msg)
        return {'FINISHED'}

    def _upsert_into(self, context, filepath, objs):
        """Upsert выделенных `objs` в IPL `filepath`. Возвращает (updated, added)."""
        from ..core.ipl import read_ipl, write_ipl
        from ..core import ipl_links as iplinks

        # ── IPL link tracking: sidecar lookup ──
        # The sidecar (one JSON next to .blend in .inu_cache/) maps
        # per-object UUIDs to ``(line_idx, model_id, last_pos)`` so
        # repeated ``Add to IPL`` of a moved object overwrites its
        # existing row instead of appending a duplicate.  When the
        # IPL was edited externally the hash mismatches and we
        # fall back to content-match (model_id + last_pos within 0.5 m).
        blend_path = bpy.data.filepath
        sidecar = iplinks.load_sidecar(blend_path)
        file_links = sidecar.file_links(filepath, create=True)

        # Read existing IPL once — needed both for upsert math and for
        # the reconcile pass below.
        try:
            existing_ipl = read_ipl(filepath) if os.path.isfile(filepath) else None
        except Exception:
            existing_ipl = None

        if existing_ipl is not None:
            current_hash = iplinks.hash_ipl_file(filepath)
            if file_links.ipl_hash and file_links.ipl_hash != current_hash:
                # External edit detected — re-validate every link.
                repaired, removed = iplinks.reconcile_file_links(
                    file_links, existing_ipl, current_hash)
                if repaired or removed:
                    self.report({'INFO'},
                                T("IPL правили извне: {0} ссылок исправлено, {1} удалено").format(
                                    repaired, len(removed)))
            elif not file_links.ipl_hash:
                file_links.ipl_hash = current_hash

        # De-dupe copies across the WHOLE scene — не только внутри батча.
        # Shift+D / Ctrl+D наследуют ipl_uuid оригинала. Если экспортируется
        # только копия (оригинала нет в выделении), батч-локальная проверка
        # её не видит и Branch 2 ОБНОВЛЯЕТ строку оригинала вместо добавления
        # нового инстанса. Поэтому смотрим все живые объекты: если один uuid
        # держат несколько — оригинал это самый ранний объект (наименьший
        # session_uid; копия Ctrl+D всегда получает более новый/больший),
        # остальным выдаём новый uuid и чистим link-состояние → они уходят в
        # Branch 1 (APPEND) как новые инстансы.
        def _obj_sid(o):
            return (getattr(o, 'session_uid', None)
                    or getattr(o, 'session_uuid', 0) or 0)

        uuid_holders = {}
        for _o in bpy.data.objects:
            _u = getattr(_o.inu, 'ipl_uuid', '')
            if _u:
                uuid_holders.setdefault(_u, []).append(_o)

        for o in objs:
            u = o.inu.ipl_uuid
            if not u:
                continue
            holders = uuid_holders.get(u, ())
            if len(holders) <= 1:
                continue
            owner = min(holders, key=_obj_sid)   # самый ранний = оригинал
            if o is not owner:
                o.inu.ipl_uuid = iplinks.new_uuid()
                # свежий инстанс: сбросить старые ссылки, чтобы был APPEND,
                # а не content-match по позиции оригинала (Branch 3).
                o.inu.ipl_last_pos = (0.0, 0.0, 0.0)
                o.inu.ipl_last_model_id = 0

        # ── UUID-aware upsert ──
        # Three branches per object:
        #   1. No uuid yet → mint one, APPEND to IPL, record link
        #   2. uuid in sidecar + line_idx still valid → UPDATE that row
        #      (regardless of whether the object's transform changed —
        #      `Add to IPL` always pushes Blender state to the file)
        #   3. uuid present but link lost → content-match
        #      (model_id + ipl_last_pos within 0.5 m); on hit UPDATE,
        #      on miss APPEND as new placement
        from ..tools.model_utils import get_model_type
        from .. import _ipl_entry_from_obj

        if existing_ipl is None:
            from ..core.ipl import IplFile
            existing_ipl = IplFile()

        # Pre-pass: separate DFFs from LODs and group LODs by base
        # name so a single LOD entry can be referenced by many DFF
        # placements (vanilla R* pattern).
        lod_per_base = {}     # base_name → LOD obj
        dff_objs = []
        base_of = {}          # id(obj) → base, so builders don't re-classify
        for obj in objs:
            mt, base = get_model_type(obj)
            base_of[id(obj)] = base
            if mt == 'LOD':
                lod_per_base[base] = obj
            elif mt == 'COL':
                # Collision is bound to its DFF by name — it is NEVER placed
                # in the IPL inst section. (Previously COL fell through to
                # dff_objs and got its own placement line.)
                continue
            else:
                dff_objs.append((obj, base))

        # ── LOD entries: upsert each base's LOD first, remember idx ──
        # The LOD entry needs to be findable to fill ``lod_index`` on
        # its DFF siblings.  We upsert LODs with the same uuid-track
        # logic.
        lod_idx_per_base = {}
        lost_lod_links = []   # DFFs whose LOD link couldn't be resolved (#2)
        updated = 0
        added = 0

        def _upsert_entry(obj, build_fn):
            """Returns (final_line_idx, was_update_or_append)."""
            nonlocal updated, added
            entry = build_fn(obj)
            uuid = obj.inu.ipl_uuid
            link_rec = file_links.links.get(uuid) if uuid else None

            # Branch 2: known link, still valid?
            if (link_rec
                    and 0 <= link_rec.line_idx < len(existing_ipl.instances)):
                existing_ipl.instances[link_rec.line_idx] = entry
                link_rec.line_idx = link_rec.line_idx  # unchanged
                link_rec.model_id = entry.model_id
                link_rec.model_name = entry.model_name
                link_rec.last_pos = (entry.pos_x, entry.pos_y, entry.pos_z)
                _record_last_state(obj, entry)
                updated += 1
                return link_rec.line_idx

            # Branch 3: uuid known, line lost → content-match
            if uuid and any(obj.inu.ipl_last_pos):
                idx = iplinks.find_inst_by_content(
                    existing_ipl,
                    obj.inu.ipl_last_model_id or entry.model_id,
                    tuple(obj.inu.ipl_last_pos))
                if idx >= 0:
                    existing_ipl.instances[idx] = entry
                    file_links.links[uuid] = iplinks.IplLinkRecord(
                        idx, entry.model_id, entry.model_name,
                        (entry.pos_x, entry.pos_y, entry.pos_z))
                    _record_last_state(obj, entry)
                    updated += 1
                    return idx

            # Branch 1: APPEND
            if not uuid:
                uuid = iplinks.new_uuid()
                obj.inu.ipl_uuid = uuid
            existing_ipl.instances.append(entry)
            idx = len(existing_ipl.instances) - 1
            file_links.links[uuid] = iplinks.IplLinkRecord(
                idx, entry.model_id, entry.model_name,
                (entry.pos_x, entry.pos_y, entry.pos_z))
            _record_last_state(obj, entry)
            added += 1
            return idx

        def _record_last_state(obj, entry):
            obj.inu.ipl_last_pos = (entry.pos_x, entry.pos_y, entry.pos_z)
            obj.inu.ipl_last_rot = (entry.rot_x, entry.rot_y,
                                    entry.rot_z, entry.rot_w)
            obj.inu.ipl_last_model_id = entry.model_id
            obj.inu.ipl_target_file = filepath

        # LOD builder: keep "LOD<base>" name + auto model_id (DFF id + 1).
        def _lod_builder(lod_obj):
            base = base_of.get(id(lod_obj))
            if base is None:
                _, base = get_model_type(lod_obj)
            e = _ipl_entry_from_obj(lod_obj)
            e.model_name = "LOD" + base
            e.lod_index = -1
            # LOD-инстанс стоит В ТОЙ ЖЕ точке, что и основная модель: сам
            # LOD-объект в сцене обычно лежит в 0,0,0 (его не размещают), поэтому
            # берём позицию/поворот у DFF-сиблинга с тем же base.
            _dff_sib = next((d for d, b in dff_objs if b == base), None)
            if _dff_sib is not None:
                _de = _ipl_entry_from_obj(_dff_sib)
                e.pos_x, e.pos_y, e.pos_z = _de.pos_x, _de.pos_y, _de.pos_z
                e.rot_x, e.rot_y, e.rot_z, e.rot_w = (
                    _de.rot_x, _de.rot_y, _de.rot_z, _de.rot_w)
            # Auto-assign LOD model_id from first DFF sibling + 1.
            if e.model_id == 0:
                for dff_obj, dff_base in dff_objs:
                    if dff_base == base:
                        dff_id = getattr(dff_obj.inu, 'model_id', 0)
                        if dff_id > 0:
                            e.model_id = dff_id + 1
                            break
            return e

        # (#2) When the LOD isn't in THIS selection (separate click / not
        # selected), don't silently wipe the link to -1: recover it from an
        # existing "LOD<base>" row in the same file, else keep the DFF's
        # previously stored valid index.
        def _resolve_lod_index(o, base):
            li = lod_idx_per_base.get(base, -1)
            if li >= 0:
                return li
            li = _find_inst_index_by_name(existing_ipl, "LOD" + base)
            if li >= 0:
                return li
            prev = int(getattr(o.inu, 'lod_index', -1) or -1)
            if 0 <= prev < len(existing_ipl.instances):
                return prev
            return -1

        def _dff_builder(o):
            e = _ipl_entry_from_obj(o)
            base = base_of.get(id(o))
            if base is None:
                _, base = get_model_type(o)
            e.lod_index = _resolve_lod_index(o, base)
            return e

        # Place the MAIN (DFF) rows FIRST, then the LODs — so in the file the
        # main model's inst line comes BEFORE its LOD's, matching the IDE order
        # (was reversed: LOD first). The main's lod_index is a forward
        # reference to the LOD line, back-filled once the LOD row exists.
        dff_placed = []   # (dff_obj, base, dff_idx, had_lod)
        for dff_obj, base in dff_objs:
            had_lod = int(getattr(dff_obj.inu, 'lod_index', -1) or -1) >= 0
            dff_idx = _upsert_entry(dff_obj, _dff_builder)
            dff_placed.append((dff_obj, base, dff_idx, had_lod))

        for base, lod_obj in lod_per_base.items():
            lod_idx = _upsert_entry(lod_obj, _lod_builder)
            lod_idx_per_base[base] = lod_idx

        # Back-fill each DFF's lod_index now that both rows exist; mirror onto
        # inu so the text-only IPL export path stays in sync.
        for dff_obj, base, dff_idx, had_lod in dff_placed:
            li = _resolve_lod_index(dff_obj, base)
            if 0 <= dff_idx < len(existing_ipl.instances):
                existing_ipl.instances[dff_idx].lod_index = li
            dff_obj.inu.lod_index = li
            if li < 0 and had_lod:
                lost_lod_links.append(dff_obj.name)

        if lost_lod_links:
            self.report({'WARNING'}, T(
                "LOD-связь потеряна (lod_index = -1) у: {0}. Выдели DFF "
                "и его LOD вместе, или держи их в одном IPL.").format(
                    ", ".join(lost_lod_links[:5])))

        # #7: emit the FLA 12th `realInterior` column when any object in this
        # write actually uses it, OR the file already had it — otherwise stay
        # vanilla 11-column. (vanilla SA ignores the extra column.)
        fla = (any(int(getattr(o.inu, 'real_interior', 0) or 0) for o in objs)
               or any(int(getattr(i, 'real_interior', 0) or 0)
                      for i in existing_ipl.instances))

        # Write IPL + sidecar.
        try:
            write_ipl(filepath, existing_ipl,
                      game=_get_scene_game(context), fla_extended=fla)
        except TypeError:
            # write_ipl signature without ``game``/``fla_extended`` — fall back.
            write_ipl(filepath, existing_ipl)
        file_links.ipl_hash = iplinks.hash_ipl_file(filepath)
        iplinks.save_sidecar(blend_path, sidecar)

        # updated/added — всего строк; n_dff/n_lod — сколько из них DFF и LOD
        # (для детального отчёта в статус-баре).
        return updated, added, len(dff_placed), len(lod_idx_per_base)


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


def _sync_one_ipl(context, filepath, sel, claimed_uuids=None,
                  relink_orphan_uuids=True, link_only=False):
    """Reconcile *sel* objects against ONE IPL file.

    *link_only* — только СВЯЗАТЬ несвязанные объекты по (model_id+позиция),
    НЕ трогая уже связанные (Branch B — подтяжку позиции из файла в объект —
    пропускаем). Нужно для «Проверки»: она должна распознать, что объект
    размещён в IPL, но НЕ двигать ничего в сцене.

    Extracted from the operator so a list of IPLs can be processed in a
    loop.  *claimed_uuids* holds uuids already linked by an earlier file
    in a multi-file run: objects carrying one are skipped so a placement
    that lives in IPL #1 isn't re-stolen by a coincidental content match
    in IPL #2.  Pass ``None`` (single-file) to disable that guard.

    Returns a dict with the same per-reason skip counters the operator
    used to compute itself, plus the sets the multi-file caller needs to
    aggregate across files: ``touched_uuids`` (for the claimed guard) and
    ``linked_names`` / ``synced_names`` (object names, for an accurate
    cross-file "skipped = matched nothing" tally).

    *relink_orphan_uuids* — when True (single-file), an object that
    carries a uuid not found in this file's links is re-matched by
    content and gets a fresh uuid (recovery after a lost link).  Multi-
    file passes False so such an object is left untouched: it almost
    certainly belongs to one of the OTHER IPLs in the run, which will
    claim it via its own Branch B — minting here would overwrite that
    link.
    """
    from ..core.ipl import read_ipl
    from ..core import ipl_links as iplinks
    from mathutils import Quaternion

    if claimed_uuids is None:
        claimed_uuids = set()

    linked = synced = skipped = 0
    skip_reasons = {'no_model_id': 0, 'no_match': 0,
                    'occupied': 0, 'line_lost': 0}
    touched_uuids = set()
    linked_names = set()
    synced_names = set()
    debug_samples = []

    blend_path = bpy.data.filepath
    sidecar = iplinks.load_sidecar(blend_path)
    file_links = sidecar.file_links(filepath, create=True)

    ipl = read_ipl(filepath)
    # Reconcile in case the IPL has been edited externally.
    current_hash = iplinks.hash_ipl_file(filepath)
    if file_links.ipl_hash and current_hash != file_links.ipl_hash:
        iplinks.reconcile_file_links(file_links, ipl, current_hash)
    elif not file_links.ipl_hash:
        file_links.ipl_hash = current_hash

    # ── Garbage-collect orphan sidecar entries ──
    # A previous Sync / Add might have left uuid→line records that no
    # longer correspond to any Blender object (file reopened, objects
    # deleted, undo).  Keeping them blocks fresh content-match: an
    # unused line shows as "occupied" by a ghost uuid, so a new attempt
    # to link a matching object skips it.  Drop these before computing
    # the occupied set so only LIVE links count as occupied territory.
    live_uuids = set()
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        u = getattr(o.inu, 'ipl_uuid', '')
        if u:
            live_uuids.add(u)
    orphans_dropped = 0
    for u in list(file_links.links.keys()):
        if u not in live_uuids:
            del file_links.links[u]
            orphans_dropped += 1
    if orphans_dropped:
        print(f"[IPL Sync] {os.path.basename(filepath)}: "
              f"dropped {orphans_dropped} orphan sidecar links")

    # Index occupied IPL line indices — only LIVE uuids count.
    occupied = {rec.line_idx for rec in file_links.links.values()}

    for obj in sel:
        uuid = getattr(obj.inu, 'ipl_uuid', '')

        # Multi-file guard: this object already belongs to an IPL
        # processed earlier in the same run — leave it alone.
        if uuid and uuid in claimed_uuids:
            continue

        # Branch B: already linked → pull position from IPL.
        if uuid and uuid in file_links.links:
            if link_only:
                # «Проверка»: связь есть — ничего не двигаем, идём дальше.
                continue
            rec = file_links.links[uuid]
            if not (0 <= rec.line_idx < len(ipl.instances)):
                skip_reasons['line_lost'] += 1
                skipped += 1
                continue
            inst = ipl.instances[rec.line_idx]
            obj.location = (inst.pos_x, inst.pos_y, inst.pos_z)
            q = Quaternion((inst.rot_w, -inst.rot_x, -inst.rot_y, -inst.rot_z))
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = q
            obj.inu.ipl_last_pos = (inst.pos_x, inst.pos_y, inst.pos_z)
            obj.inu.ipl_last_rot = (inst.rot_x, inst.rot_y, inst.rot_z, inst.rot_w)
            obj.inu.ipl_last_model_id = inst.model_id
            obj.inu.ipl_target_file = filepath
            rec.last_pos = (inst.pos_x, inst.pos_y, inst.pos_z)
            synced += 1
            touched_uuids.add(uuid)
            synced_names.add(obj.name)
            continue

        # Multi-file: don't content-match (and thus re-mint a uuid for)
        # an object that already carries one — it belongs to another IPL
        # in this run, which will claim it via its own Branch B.
        if uuid and not relink_orphan_uuids:
            continue

        # Branch A: no uuid → content-match by (model_id, world pos).
        model_id = getattr(obj.inu, 'model_id', 0)
        if model_id <= 0:
            skipped += 1
            skip_reasons['no_model_id'] += 1
            if len(debug_samples) < 5:
                debug_samples.append(
                    f"  {obj.name!r}: model_id=0 (Map Import не выставил ID — "
                    f"проверь Object Properties → INU Tools → Model ID)")
            continue
        world_pos = obj.matrix_world.translation
        idx = iplinks.find_inst_by_content(
            ipl, model_id,
            (world_pos.x, world_pos.y, world_pos.z),
            occupied=occupied)   # пропускать занятые строки (кластеры наложенных деревьев)
        if idx < 0 and link_only:
            # «Проверка»: строгого совпадения по позиции нет (модель сдвинута
            # относительно IPL), но строка с этим ID в файле есть — привязываем
            # к БЛИЖАЙШЕЙ свободной строке того же ID. Объект НЕ двигаем: панель
            # покажет «В IPL, координаты разошлись» и включит кнопку 🔄, которой
            # можно подтянуть модель к координатам из IPL. Так распознаётся
            # drag-drop/сдвинутая модель, а не только стоящая точно на месте.
            best_i, best_d = -1, float('inf')
            for i, inst in enumerate(ipl.instances):
                if i in occupied:
                    continue
                if int(getattr(inst, 'model_id', -1)) != int(model_id):
                    continue
                d2 = ((inst.pos_x - world_pos.x) ** 2
                      + (inst.pos_y - world_pos.y) ** 2
                      + (inst.pos_z - world_pos.z) ** 2)
                if d2 < best_d:
                    best_d, best_i = d2, i
            idx = best_i
        if idx < 0:
            skipped += 1
            skip_reasons['no_match'] += 1
            if len(debug_samples) < 5:
                # Show closest same-id row in the IPL for diagnosis.
                nearest = None
                nearest_d = float('inf')
                for i, inst in enumerate(ipl.instances):
                    if int(getattr(inst, 'model_id', -1)) != int(model_id):
                        continue
                    d2 = ((inst.pos_x - world_pos.x) ** 2
                          + (inst.pos_y - world_pos.y) ** 2
                          + (inst.pos_z - world_pos.z) ** 2)
                    if d2 < nearest_d:
                        nearest_d = d2
                        nearest = inst
                if nearest is not None:
                    debug_samples.append(
                        f"  {obj.name!r}: model_id={model_id}, "
                        f"pos=({world_pos.x:.3f},{world_pos.y:.3f},{world_pos.z:.3f}); "
                        f"ближайшая IPL-строка с тем же ID на расстоянии "
                        f"{nearest_d ** 0.5:.3f} m: "
                        f"({nearest.pos_x:.3f},{nearest.pos_y:.3f},{nearest.pos_z:.3f})")
                else:
                    debug_samples.append(
                        f"  {obj.name!r}: model_id={model_id} ОТСУТСТВУЕТ в IPL "
                        f"(в файле нет ни одной строки с этим ID)")
            continue
        # (Заняты ли строки — теперь учитывает сам find_inst_by_content.)
        inst = ipl.instances[idx]
        new_uuid = iplinks.new_uuid()
        obj.inu.ipl_uuid = new_uuid
        obj.inu.ipl_last_pos = (inst.pos_x, inst.pos_y, inst.pos_z)
        obj.inu.ipl_last_rot = (inst.rot_x, inst.rot_y, inst.rot_z, inst.rot_w)
        obj.inu.ipl_last_model_id = inst.model_id
        obj.inu.ipl_target_file = filepath
        file_links.links[new_uuid] = iplinks.IplLinkRecord(
            idx, inst.model_id, inst.model_name,
            (inst.pos_x, inst.pos_y, inst.pos_z))
        occupied.add(idx)
        linked += 1
        touched_uuids.add(new_uuid)
        linked_names.add(obj.name)

    iplinks.save_sidecar(blend_path, sidecar)

    # Console diagnostics — surfaced when skipped > 0 so the user can
    # see why content-match failed without opening a debugger.
    if skipped > 0:
        print(f"[IPL Sync] {os.path.basename(filepath)} skipped breakdown:")
        print(f"  no_model_id : {skip_reasons['no_model_id']}")
        print(f"  no_match    : {skip_reasons['no_match']}")
        print(f"  occupied    : {skip_reasons['occupied']}")
        print(f"  line_lost   : {skip_reasons['line_lost']}")
        print(f"  IPL: {filepath}  (instances: {len(ipl.instances)})")
        if debug_samples:
            print("[IPL Sync] sample skips:")
            for s in debug_samples:
                print(s)

    return {
        'linked': linked, 'synced': synced, 'skipped': skipped,
        'reasons': skip_reasons,
        'touched_uuids': touched_uuids,
        'linked_names': linked_names,
        'synced_names': synced_names,
    }


class GTATOOLS_OT_ipl_sync_from_file(bpy.types.Operator):
    """Синхронизация Blender ↔ IPL.

    Bi-directional:
      • Если у объекта НЕТ uuid и его (model_id + позиция) совпадает с
        какой-то строкой IPL — линкует: генерирует uuid, регистрирует в
        sidecar. Это автолинковка после Map Import.
      • Если у объекта uuid есть — подтягивает позицию ИЗ IPL в Blender
        (после внешней правки файла).

    Если заполнен список «Sync несколько IPL» — проходит по всем файлам
    из него; иначе по единственному gtatools_ipl_path. Работает по
    выделению (или по всем mesh-объектам если selection пуст).
    """
    bl_idname = "gtatools.ipl_sync_from_file"
    bl_label = "INU: Sync from IPL"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.inu_settings
        valid, missing = _ipl_sync_targets(settings)
        if not valid:
            self.report({'ERROR'}, T("IPL файл не найден"))
            return {'CANCELLED'}

        # Selection scope — if user has objects selected, work on those;
        # otherwise sweep every mesh in the scene.  Importing a 383-obj
        # map then clicking Sync with nothing selected should still link
        # everything.  Computed once so every IPL shares the same scope.
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        if not sel:
            sel = [o for o in bpy.data.objects if o.type == 'MESH']

        # ── Single-file path: identical behaviour/report as before ──
        if len(valid) == 1:
            r = _sync_one_ipl(context, valid[0], sel)
            reasons = r['reasons']
            skipped = r['skipped']
            msg = T("Sync IPL: обновлено {1}, новых связей {0}, пропущено {2}").format(
                r['linked'], r['synced'], skipped)
            # Тревожный варнинг — только если совсем ничего не сопоставлено.
            if skipped and r['linked'] == 0 and r['synced'] == 0:
                if reasons['no_model_id'] == skipped:
                    msg += " — " + T("все без Model ID")
                elif reasons['no_match'] == skipped:
                    msg += " — " + T("ни одного совпадения по (model_id+pos) в этом IPL")
                elif reasons['occupied'] == skipped:
                    msg += " — " + T("все целевые строки уже заняты другими объектами")
            if missing:
                msg += " — " + T("файлов не найдено: {0}").format(len(missing))
            GTATOOLS_OT_ipl_sync_from_file.last_message = msg
            _pub(self, 'INFO', msg)
            return {'FINISHED'}

        # ── Multi-file path ──
        # Each object belongs to at most one IPL in the set, so a plain
        # sum of per-file skip counts would over-count massively (an
        # object placed in IPL #2 is a "no_match" for IPL #1).  Instead
        # we union the linked/synced object names across files and treat
        # everything still untouched as the real "skipped" set.
        claimed = set()
        linked_names, synced_names = set(), set()
        for fp in valid:
            r = _sync_one_ipl(context, fp, sel, claimed,
                              relink_orphan_uuids=False)
            claimed |= r['touched_uuids']
            linked_names |= r['linked_names']
            synced_names |= r['synced_names']

        done = linked_names | synced_names
        skipped_objs = [o for o in sel if o.name not in done]
        no_id = sum(1 for o in skipped_objs
                    if int(getattr(o.inu, 'model_id', 0) or 0) <= 0)
        no_match = len(skipped_objs) - no_id

        msg = T("Sync IPL: обновлено {1}, новых связей {0}, пропущено {2}").format(
            len(linked_names), len(synced_names), len(skipped_objs))
        msg += " " + T("({0} IPL)").format(len(valid))
        # Тревожный варнинг — ТОЛЬКО когда совсем ничего не сопоставлено
        # (linked+обновлено = 0). Иначе «пропущено N» — это просто часть, не
        # нашедшая места, при успешной синхронизации остальных.
        if skipped_objs and not done:
            if no_id == len(skipped_objs):
                msg += " — " + T("все без Model ID")
            else:
                msg += " — " + T("ни одного совпадения по (model_id+pos)")
        if missing:
            msg += " — " + T("файлов не найдено: {0}").format(len(missing))
        GTATOOLS_OT_ipl_sync_from_file.last_message = msg
        _pub(self, 'INFO', msg)
        return {'FINISHED'}


class GTATOOLS_OT_ipl_restore_coords(bpy.types.Operator):
    """Вернуть выделенные модели на их координаты из IPL (позиция и поворот).

Ищет строку модели: сначала по связи (uuid) в её родном IPL, иначе по Model ID
в родном файле, а если не нашлось — во всех IPL папки игры. Один инстанс —
ставит по нему; несколько — берёт ближайший к текущему положению"""
    bl_idname = "gtatools.ipl_restore_coords"
    bl_label = "INU: Restore coords from IPL"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..core.ipl import read_ipl
        from ..core import ipl_links as iplinks
        from mathutils import Quaternion

        settings = context.scene.inu_settings
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        if not sel:
            self.report({'ERROR'}, T("Выделите модель"))
            return {'CANCELLED'}

        valid, _missing = _ipl_sync_targets(settings)
        _cache = {}

        def _get(fp):
            if fp not in _cache:
                try:
                    _cache[fp] = read_ipl(fp)
                except Exception:
                    _cache[fp] = None
            return _cache[fp]

        sidecar = iplinks.load_sidecar(bpy.data.filepath)

        def _apply(obj, inst):
            obj.location = (inst.pos_x, inst.pos_y, inst.pos_z)
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = Quaternion(
                (inst.rot_w, -inst.rot_x, -inst.rot_y, -inst.rot_z))
            obj.inu.ipl_last_pos = (inst.pos_x, inst.pos_y, inst.pos_z)
            obj.inu.ipl_last_rot = (inst.rot_x, inst.rot_y,
                                    inst.rot_z, inst.rot_w)

        restored = not_found = ambiguous = 0
        for obj in sel:
            inst = None
            uuid = getattr(obj.inu, 'ipl_uuid', '')
            tgt = bpy.path.abspath(obj.inu.ipl_target_file or '')

            # 1) По uuid-связи в родном файле — точная строка.
            if uuid and tgt and os.path.isfile(tgt):
                ipl = _get(tgt)
                if ipl is not None:
                    fl = sidecar.file_links(tgt, create=True)
                    rec = fl.links.get(uuid)
                    if rec and 0 <= rec.line_idx < len(ipl.instances):
                        inst = ipl.instances[rec.line_idx]

            # 2) По Model ID: родной файл, затем все IPL папки игры.
            if inst is None:
                mid = int(getattr(obj.inu, 'model_id', 0) or 0)
                if mid > 0:
                    files = []
                    if tgt and os.path.isfile(tgt):
                        files.append(tgt)
                    _tk = os.path.normcase(os.path.normpath(tgt)) if tgt else ''
                    for f in valid:
                        if os.path.normcase(os.path.normpath(f)) != _tk:
                            files.append(f)
                    matches = []
                    for fp in files:
                        ipl = _get(fp)
                        if ipl is None:
                            continue
                        fm = [i for i in ipl.instances
                              if int(getattr(i, 'model_id', -1)) == mid]
                        if fm:
                            matches.extend((fp, i) for i in fm)
                            if fp == tgt:
                                break   # родной файл в приоритете
                    if len(matches) == 1:
                        inst = matches[0][1]
                        obj.inu.ipl_target_file = matches[0][0]
                    elif len(matches) > 1:
                        wp = obj.matrix_world.translation
                        fp, inst = min(
                            matches,
                            key=lambda m: (m[1].pos_x - wp.x) ** 2
                            + (m[1].pos_y - wp.y) ** 2
                            + (m[1].pos_z - wp.z) ** 2)
                        obj.inu.ipl_target_file = fp
                        ambiguous += 1

            if inst is not None:
                _apply(obj, inst)
                restored += 1
            else:
                not_found += 1

        msg = T("Вернул координаты из IPL: {0}, не найдено: {1}").format(
            restored, not_found)
        if ambiguous:
            msg += " " + T("(неоднозначных: {0} — взят ближайший)").format(
                ambiguous)
        _pub(self, 'WARNING' if (not_found and not restored) else 'INFO', msg)
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


class GTATOOLS_OT_ide_sync_export(bpy.types.Operator):
    """Экспорт «каждая модель в свой IDE»: обновляет строки выделенных моделей
    в тех IDE, откуда они пришли (ide_target_file, проставляется импортом). Модели
    без IDE (новые) не пишутся — о них сообщается, добавь их через «Add» в
    выбранный IDE."""
    bl_idname = "gtatools.ide_sync_export"
    bl_label = "INU: Export models to their IDEs"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from .. import _ide_entry_from_obj
        from ..core.ide import upsert_ide
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        groups = {}          # ide_file -> [obj]
        new_models = []      # модели без своего IDE
        for o in objs:
            inu = getattr(o, 'inu', None)
            tgt = (bpy.path.abspath(inu.ide_target_file)
                   if (inu and inu.ide_linked and inu.ide_target_file) else '')
            if tgt and os.path.isfile(tgt) and getattr(inu, 'model_id', 0) > 0:
                groups.setdefault(tgt, []).append(o)
            else:
                new_models.append(o)
        total_u = total_a = 0
        for fp, grp in groups.items():
            entries = [_ide_entry_from_obj(o) for o in grp]
            u, a = upsert_ide(fp, entries)
            total_u += u
            total_a += a
            # Обновить снимок last_* (для статуса «параметры разошлись»).
            for o in grp:
                _inu = o.inu
                _inu.ide_last_draw_distance = _inu.draw_distance
                _inu.ide_last_txd_name = _inu.txd_name
                _inu.ide_last_flags = _inu.ide_flags
        msg = T("IDE: обновлено {0}, добавлено {1}, файлов {2}").format(
            total_u, total_a, len(groups))
        if new_models:
            msg += " · " + T("новых вне IDE: {0} (добавь через «Add»)").format(
                len(new_models))
        self.report({'WARNING'} if new_models else {'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_ipl_sync_export(bpy.types.Operator):
    """Обновить координаты выделенных моделей в их родных IPL.

Каждая модель пишется в тот IPL, откуда её импортировали — записывается новая
позиция и поворот. Удобно после того как подвинул модель в сцене. Файл,
выбранный в боксе IPL, при этом не используется"""
    bl_idname = "gtatools.ipl_sync_export"
    bl_label = "INU: Export placements to their IPLs"
    bl_options = {'REGISTER'}

    def execute(self, context):
        s = context.scene.inu_settings
        saved = s.gtatools_ipl_path
        try:
            # Пусто → upsert_ipl роутит каждый объект в его ipl_target_file.
            s.gtatools_ipl_path = ""
            # Ловим RuntimeError от upsert_ipl (например «Укажите путь к IPL»,
            # когда у модели ещё нет своего IPL) — показываем мягкое
            # предупреждение вместо красной ошибки с трейсбеком.
            try:
                GTATOOLS_OT_upsert_ipl.last_message = ""
                res = bpy.ops.gtatools.upsert_ipl('EXEC_DEFAULT')
                msg = GTATOOLS_OT_upsert_ipl.last_message
                if msg:
                    _pub(self, 'INFO', msg)
                    _show_status_text(context, msg)
                return res
            except RuntimeError:
                self.report(
                    {'WARNING'},
                    T("У выделенной модели нет своего IPL — сначала добавь её "
                      "в IPL кнопкой «Add»"))
                return {'CANCELLED'}
        finally:
            s.gtatools_ipl_path = saved


class GTATOOLS_OT_ipl_remove_link(bpy.types.Operator):
    """Удалить выделенные объекты из IPL и очистить ссылки.

Объекты остаются в Blender, но их inst-строки удаляются из IPL. Парный LOD
модели удаляется тоже (если он не нужен другой оставшейся модели). Индексы
строк и lod_index у остальных пересчитываются заново, чтобы ссылки не съехали"""
    bl_idname = "gtatools.ipl_remove_link"
    bl_label = "INU: Remove from IPL"
    bl_options = {'REGISTER'}

    # Переопределение файла (пусто → gtatools_ipl_path). Позволяет 🗑 в боксе
    # «Выделенная модель» удалять из РОДНОГО IPL модели.
    target_file: StringProperty(default="", options={'HIDDEN'})

    def execute(self, context):
        from ..core.ipl import read_ipl, write_ipl
        from ..core import ipl_links as iplinks
        filepath = bpy.path.abspath(
            self.target_file or context.scene.inu_settings.gtatools_ipl_path)
        if not filepath or not os.path.isfile(filepath):
            self.report({'ERROR'}, T("IPL файл не найден"))
            return {'CANCELLED'}

        objs = [o for o in context.selected_objects
                if o.type == 'MESH' and o.inu.ipl_uuid]
        if not objs:
            self.report({'ERROR'}, T("Выделите объекты с привязкой к IPL"))
            return {'CANCELLED'}

        blend_path = bpy.data.filepath
        sidecar = iplinks.load_sidecar(blend_path)
        file_links = sidecar.file_links(filepath, create=False)
        if file_links is None:
            self.report({'INFO'}, T("Нет связанных объектов для этого IPL"))
            return {'CANCELLED'}

        ipl = read_ipl(filepath)
        current_hash = iplinks.hash_ipl_file(filepath)
        if current_hash != file_links.ipl_hash:
            iplinks.reconcile_file_links(file_links, ipl, current_hash)

        # Collect indices to drop (descending so deletion preserves
        # remaining indices of links we keep).
        drop_idx = set()
        cleared_uuids = []
        for o in objs:
            u = o.inu.ipl_uuid
            rec = file_links.links.get(u)
            idx = -1
            if rec is not None and 0 <= rec.line_idx < len(ipl.instances):
                idx = rec.line_idx
            elif any(o.inu.ipl_last_pos):
                # Запись в сайдкаре потеряна (файл правили снаружи, .blend
                # переименовали, сайдкар не доехал) — ищем строку по
                # содержимому, ровно как это делает «Add». Без этого
                # удаление молчало «не найдено записей», хотя строка в IPL
                # была, и лечилось только повторным Add.
                idx = iplinks.find_inst_by_content(
                    ipl,
                    int(getattr(o.inu, 'ipl_last_model_id', 0) or 0)
                    or int(getattr(o.inu, 'model_id', 0) or 0),
                    tuple(o.inu.ipl_last_pos),
                    occupied=drop_idx)
            if idx >= 0:
                drop_idx.add(idx)
            if u:
                cleared_uuids.append(u)

        if not drop_idx:
            self.report({'INFO'}, T("Не найдено записей для удаления"))
            return {'CANCELLED'}

        # Заодно удалить ПАРНЫЙ LOD каждой убираемой модели (строку, на
        # которую указывает её lod_index) — но только если этот LOD не нужен
        # какой-то ОСТАЮЩЕЙСЯ модели (общий LOD не трогаем).
        _models_dropped = len(drop_idx)
        _lod_candidates = set()
        for i in list(drop_idx):
            li = ipl.instances[i].lod_index
            if li is not None and 0 <= li < len(ipl.instances) and li not in drop_idx:
                _lod_candidates.add(li)
        for li in _lod_candidates:
            still_used = any(
                j != li and j not in drop_idx
                and ipl.instances[j].lod_index == li
                for j in range(len(ipl.instances)))
            if not still_used:
                drop_idx.add(li)
        _lods_dropped = len(drop_idx) - _models_dropped

        # Build remap old_idx → new_idx for survivors.
        survivors = [i for i in range(len(ipl.instances)) if i not in drop_idx]
        remap = {old: new for new, old in enumerate(survivors)}
        ipl.instances = [ipl.instances[i] for i in survivors]
        # Patch lod_index pointers — they reference inst positions in
        # the same IPL; surviving rows pointing at a dropped index lose
        # their LOD link.
        for inst in ipl.instances:
            if inst.lod_index >= 0:
                inst.lod_index = remap.get(inst.lod_index, -1)
        # Update sidecar link records for survivors.
        for u, rec in list(file_links.links.items()):
            if u in cleared_uuids:
                del file_links.links[u]
                continue
            rec.line_idx = remap.get(rec.line_idx, -1)
            if rec.line_idx < 0:
                del file_links.links[u]

        try:
            write_ipl(filepath, ipl, game=_get_scene_game(context))
        except TypeError:
            write_ipl(filepath, ipl)
        file_links.ipl_hash = iplinks.hash_ipl_file(filepath)
        iplinks.save_sidecar(blend_path, sidecar)

        # Clear per-object link state.
        for o in objs:
            o.inu.ipl_uuid = ""
            o.inu.ipl_target_file = ""
            o.inu.ipl_last_pos = (0.0, 0.0, 0.0)
            o.inu.ipl_last_rot = (0.0, 0.0, 0.0, 1.0)
            o.inu.ipl_last_model_id = 0

        if _lods_dropped:
            msg = T("Удалено из IPL: {0} (+ {1} LOD), осталось: {2}").format(
                _models_dropped, _lods_dropped, len(ipl.instances))
        else:
            msg = T("Удалено из IPL: {0}, осталось записей: {1}").format(
                len(drop_idx), len(ipl.instances))
        GTATOOLS_OT_ipl_remove_link.last_message = msg
        _pub(self, 'INFO', msg)
        return {'FINISHED'}


class GTATOOLS_OT_ipl_verify_links(bpy.types.Operator):
    """Проверить все ссылки sidecar'а на валидность. Сообщает orphan'ы
    (uuid в sidecar, объект удалён из Blender) и broken links
    (line_idx за пределами IPL или content не совпадает)."""
    bl_idname = "gtatools.ipl_verify_links"
    bl_label = "INU: Verify IPL Links"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.ipl import read_ipl
        from ..core import ipl_links as iplinks
        settings = context.scene.inu_settings

        # Scope: выделение, иначе все меши сцены.
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        if not sel:
            sel = [o for o in bpy.data.objects if o.type == 'MESH']

        # 1) Link-only content-match: распознать объекты, УЖЕ размещённые в
        #    IPL (совпал model_id + позиция), но ещё не связанные — так же, как
        #    IDE-проверка находит модель по ID. Раньше Check смотрел ТОЛЬКО на
        #    сохранённые uuid, поэтому drag-drop модель (есть имя+ID, стоит на
        #    своём месте) значилась «Не в IPL». link_only=True → ничего не двигаем.
        valid, _missing = _ipl_sync_targets(settings)
        claimed = set()
        newly_linked = set()
        for fp in valid:
            r = _sync_one_ipl(context, fp, sel, claimed,
                              relink_orphan_uuids=(len(valid) == 1),
                              link_only=True)
            claimed |= r['touched_uuids']
            newly_linked |= r['linked_names']

        # 2) Orphan/broken verify по одиночному выбранному пути (как раньше).
        filepath = bpy.path.abspath(settings.gtatools_ipl_path)
        ok_links = repaired = removed_n = orphans_n = 0
        if filepath and os.path.isfile(filepath):
            blend_path = bpy.data.filepath
            sidecar = iplinks.load_sidecar(blend_path)
            file_links = sidecar.file_links(filepath, create=False)
            if file_links is not None and file_links.links:
                ipl = read_ipl(filepath)
                current_hash = iplinks.hash_ipl_file(filepath)
                repaired, removed = iplinks.reconcile_file_links(
                    file_links, ipl, current_hash)
                removed_n = len(removed)
                uuid_to_obj = {o.inu.ipl_uuid for o in bpy.data.objects
                               if o.type == 'MESH' and getattr(o.inu, 'ipl_uuid', '')}
                orphans = [u for u in file_links.links if u not in uuid_to_obj]
                orphans_n = len(orphans)
                ok_links = len(file_links.links) - orphans_n
                iplinks.save_sidecar(blend_path, sidecar)

        msg = T("IPL Проверка: связано новых {0}, ОК {1}, исправлено {2}, удалено {3}, orphan {4}").format(
            len(newly_linked), ok_links, repaired, removed_n, orphans_n)
        GTATOOLS_OT_ipl_verify_links.last_message = msg
        _pub(self, 'INFO', msg)
        return {'FINISHED'}


# Wrapper-friendly message stash.  When an inner operator (ide_sync,
# ipl_sync, …) runs inside ``link_sync`` via ``bpy.ops`` + temp_override,
# Blender's status bar shows only the OUTER operator's last report —
# the inner ``self.report({'INFO'}, ...)`` becomes invisible.  The
# inner ops mirror their final message onto ``last_message`` so the
# wrapper can read it post-call and re-emit it as its own report.
# Naming: ``<OperatorClassName>.last_message`` — accessed directly,
# no helper.  ClassVar in spirit; not annotated to keep PropertyGroup
# scanners from picking it up.

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
        by_id = {}
        by_name = {}
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

        sel = [o for o in context.selected_objects if o.type == 'MESH']
        if not sel:
            sel = [o for o in bpy.data.objects if o.type == 'MESH']

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
            # Имя — стабильный ключ (ловит ИЗМЕНЁННЫЙ в IDE id); id — запасной
            # (если объект переименован в Blender, а имя уже не совпадает).
            entry_src = by_name.get(cname)
            if entry_src is None and mid > 0:
                entry_src = by_id.get(mid)
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
            # Pull file → Blender.
            inu.draw_distance = float(getattr(entry, 'draw_distance', 0.0))
            inu.txd_name = str(getattr(entry, 'txd_name', '') or '')
            inu.ide_flags = int(getattr(entry, 'flags', 0))
            inu.ide_target_file = src_file
            inu.ide_last_draw_distance = inu.draw_distance
            inu.ide_last_txd_name = inu.txd_name
            inu.ide_last_flags = inu.ide_flags
            inu.ide_last_model_id = int(getattr(inu, 'model_id', 0) or 0)
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


class GTATOOLS_OT_ide_remove_link(bpy.types.Operator):
    """Удалить выделенные объекты из IDE и очистить tracking-поля.
    Объекты остаются в Blender, но их записи в IDE удаляются по model_id."""
    bl_idname = "gtatools.ide_remove_link"
    bl_label = "INU: Unlink from IDE"
    bl_options = {'REGISTER'}

    # Переопределение файла (пусто → gtatools_ide_path). Для 🗑 в боксе —
    # удалять из РОДНОГО IDE модели.
    target_file: StringProperty(default="", options={'HIDDEN'})

    def execute(self, context):
        from ..core.ide import remove_ide
        filepath = bpy.path.abspath(
            self.target_file or context.scene.inu_settings.gtatools_ide_path)
        if not filepath or not os.path.isfile(filepath):
            self.report({'ERROR'}, T("IDE файл не найден"))
            return {'CANCELLED'}

        objs = [o for o in context.selected_objects
                if o.type == 'MESH' and getattr(o.inu, 'model_id', 0) > 0]
        if not objs:
            self.report({'ERROR'}, T("Выделите объекты с Model ID > 0"))
            return {'CANCELLED'}

        model_ids = set()
        for o in objs:
            model_ids.add(int(o.inu.model_id))
            # Also drop the auto-paired LOD id (DFF+1) if user linked
            # via Add to IDE; this mirrors the LOD-pair behaviour there.
            if o.inu.ide_linked:
                model_ids.add(int(o.inu.model_id) + 1)

        removed = remove_ide(filepath, list(model_ids))

        # Clear per-object IDE link state.
        for o in objs:
            o.inu.ide_target_file = ""
            o.inu.ide_last_draw_distance = 0.0
            o.inu.ide_last_txd_name = ""
            o.inu.ide_last_flags = 0
            o.inu.ide_linked = False

        msg = T("IDE: удалено {0} записей").format(removed)
        GTATOOLS_OT_ide_remove_link.last_message = msg
        _pub(self, 'INFO', msg)
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
    """Verify обоих: IDE-ссылок (по model_id) + IPL-ссылок (по uuid+sidecar)."""
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


class GTATOOLS_OT_remove_ide(bpy.types.Operator):
    """Del: удалить строки ВЫДЕЛЕННЫХ моделей из выбранного .ide (по Model ID)"""
    bl_idname = "gtatools.remove_ide"
    bl_label = "INU: Remove from IDE"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.ide import remove_ide
        filepath = bpy.path.abspath(context.scene.inu_settings.gtatools_ide_path)
        if not filepath:
            self.report({'ERROR'}, T("Укажите путь к IDE файлу"))
            return {'CANCELLED'}

        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        model_ids = set()
        for o in objs:
            inu = getattr(o, 'inu', None)
            mid = getattr(inu, 'model_id', 0) if inu else 0
            if mid > 0:
                model_ids.add(mid)

        if not model_ids:
            self.report({'ERROR'}, T("Нет объектов с Model ID > 0"))
            return {'CANCELLED'}

        removed = remove_ide(filepath, model_ids)
        _pub(self, 'INFO', f"IDE: {T('удалено')} {removed}")
        return {'FINISHED'}


class GTATOOLS_OT_remove_ipl(bpy.types.Operator):
    """Del: удалить расстановку ВЫДЕЛЕННЫХ моделей из выбранного .ipl"""
    bl_idname = "gtatools.remove_ipl"
    bl_label = "INU: Remove from IPL"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core.ipl import read_ipl, write_ipl
        from ..core import ipl_links as iplinks

        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        single = bpy.path.abspath(context.scene.inu_settings.gtatools_ipl_path) or ''
        blend_path = bpy.data.filepath
        sidecar = iplinks.load_sidecar(blend_path)

        # Маршрутизация по объекту: удаляем из ЕГО файла (ipl_target_file),
        # иначе из выбранного пути. Удаляем КОНКРЕТНУЮ строку (по uuid→строка,
        # иначе по контенту model_id+поз), а НЕ все строки этого Model ID.
        groups = {}
        for o in objs:
            tgt = (bpy.path.abspath(o.inu.ipl_target_file)
                   if o.inu.ipl_target_file else '')
            fp = tgt if (tgt and os.path.isfile(tgt)) else single
            if fp and os.path.isfile(fp):
                groups.setdefault(fp, []).append(o)
        if not groups:
            self.report({'ERROR'}, T("Укажите путь к IPL файлу"))
            return {'CANCELLED'}

        removed = 0
        for fp, group in groups.items():
            try:
                ipl = read_ipl(fp)
            except Exception:
                continue
            fl = sidecar.file_links(fp, create=True)
            n = len(ipl.instances)

            to_remove = set()           # индексы строк к удалению в этом файле
            removed_objs = []           # (obj, uuid) чьи строки удаляем
            for o in group:
                uuid = o.inu.ipl_uuid
                li = -1
                if uuid:
                    rec = fl.links.get(uuid)
                    if (rec and 0 <= rec.line_idx < n
                            and rec.line_idx not in to_remove):
                        li = rec.line_idx
                if li < 0:              # нет ссылки → ищем по контенту
                    mid = int(getattr(o.inu, 'model_id', 0) or 0)
                    wp = o.matrix_world.translation
                    li = iplinks.find_inst_by_content(
                        ipl, mid, (wp.x, wp.y, wp.z), occupied=to_remove)
                if li >= 0:
                    to_remove.add(li)
                    removed_objs.append((o, uuid))
            if not to_remove:
                continue

            # Удаляем по убыванию индекса (чтобы не съезжали).
            for li in sorted(to_remove, reverse=True):
                del ipl.instances[li]
                removed += 1

            # Sidecar: убрать ссылки удалённых, сдвинуть остальные.
            rm_uuids = {u for (_o, u) in removed_objs if u}
            for u in rm_uuids:
                fl.links.pop(u, None)
            for rec in fl.links.values():
                rec.line_idx -= sum(1 for li in to_remove if li < rec.line_idx)

            try:
                write_ipl(fp, ipl, game=_get_scene_game(context))
            except TypeError:
                write_ipl(fp, ipl)
            fl.ipl_hash = iplinks.hash_ipl_file(fp)

            # Снять трекинг с удалённых объектов.
            for o, _u in removed_objs:
                o.inu.ipl_uuid = ''
                o.inu.ipl_target_file = ''
                o.inu.lod_index = -1

        iplinks.save_sidecar(blend_path, sidecar)
        _pub(self, 'INFO', f"IPL: {T('удалено')} {removed}")
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


