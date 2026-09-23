# INU_tools.ops.geo_building_ops — здания на базе Auto-Building.
#
# Генерацию домов делает Auto-Building (нод-группы GN_Auto-Building и
# компания, лицензия GPL-2.0-or-later — совместима с нашей GPL-3.0).
# Свой генератор мы не пишем: их система работает по ГРАНЯМ с материалами
# ID_WallA…ID_WallH, меряет размер куска прямо в графе через Bound Box и
# раскладывает тайлы по UV-развёртке грани. Это снимает разом и обход
# контура, и углы, и разъезд кусков.
#
# Наша часть — то, чего у них нет и не должно быть: подготовка кусков из
# домов GTA SA, сборка результата в обычный меш и дальше обычный конвейер
# аддона (вершинные цвета, COL, LOD, IDE/IPL).
#
# Заготовка берётся из их файла assets/Auto-Building_1.2.6_Start.blend —
# тем же способом, что и в самом Auto-Building: append объекта плюс
# схлопывание дублей материалов и нод-групп (иначе каждый append плодит
# ID_WallA.001, GN_Auto-Building.001 и связи расходятся).

import os

import bpy

from .. import T

from ..data.autobuilding_ui import MODIFIER, REALIZE  # noqa: F401

START_BLEND = "Auto-Building_1.2.6_Start.blend"
BASE_OBJECT = "Auto-Building_START"

# Префиксы, дубли которых после append надо схлопывать обратно.
_DEDUPE = ("ID_", "Grey")


def start_file(settings):
    """Путь к Auto-Building_1.2.6_Start.blend или пустая строка."""
    root = bpy.path.abspath(
        getattr(settings, 'gtatools_building_assets', '') or '')
    if not root:
        return ""
    if os.path.isfile(root):
        return root
    candidate = os.path.join(root, START_BLEND)
    return candidate if os.path.isfile(candidate) else ""


def _dedupe():
    """Схлопнуть ID_WallA.001 обратно в ID_WallA — и то же для нод-групп.

    Blender при append не переиспользует локальные датаблоки, поэтому
    второе здание в сцене приезжает с собственными копиями материалов и
    нод-групп. Материалы у Auto-Building не косметика, а разметка стен:
    разошлись копии — грани перестают попадать в свой тип стены."""
    for materials, prefixes in ((bpy.data.materials, _DEDUPE),
                                (bpy.data.node_groups, ("GN_",))):
        for item in list(materials):
            original, _, ext = item.name.rpartition(".")
            if not ext.isnumeric() or original not in materials:
                continue
            if not any(original.startswith(p) or p in original
                       for p in prefixes):
                continue
            item.user_remap(materials[original])
            materials.remove(item)


def _append(context, kind, name):
    """Притащить датаблок из их Start-файла. (объекты, ошибка)."""
    path = start_file(context.scene.inu_settings)
    if not path:
        return [], T("Укажи папку assets Auto-Building")

    before = set(bpy.data.objects)
    try:
        bpy.ops.wm.append(
            filepath=os.path.join(path, kind, name),
            directory=os.path.join(path, kind, ''),
            filename=name,
            check_existing=False, do_reuse_local_id=False, autoselect=True)
    except RuntimeError as exc:
        return [], str(exc)

    _dedupe()
    return [o for o in bpy.data.objects if o not in before], ""


class GTATOOLS_OT_building_example(bpy.types.Operator):
    """Притащить коллекцию примеров Auto-Building — готовые здания,
    по которым видно, как размечены грани и что лежит в наборах"""
    bl_idname = "gtatools.building_example"
    bl_label = "Примеры"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        fresh, error = _append(context, 'Collection',
                               'Auto-Building_EXAMPLE')
        if error:
            self.report({'WARNING'}, error)
            return {'CANCELLED'}
        self.report({'INFO'}, "%s %d" % (T("Объектов:"), len(fresh)))
        return {'FINISHED'}


class GTATOOLS_OT_building_base(bpy.types.Operator):
    """Притащить Auto-Base — заготовку основания под здание"""
    bl_idname = "gtatools.building_base"
    bl_label = "Auto-Base"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        fresh, error = _append(context, 'Object', 'Auto-Base_START')
        if error:
            self.report({'WARNING'}, error)
            return {'CANCELLED'}
        for obj in fresh:
            obj.location = context.scene.cursor.location
        if fresh:
            context.view_layer.objects.active = fresh[0]
        self.report({'INFO'}, T("Основание добавлено"))
        return {'FINISHED'}


class GTATOOLS_OT_building_new(bpy.types.Operator):
    """Поставить в сцену заготовку Auto-Building. Дальше форму дома лепишь
    как обычный меш, а гранями с материалами ID_WallA…ID_WallH говоришь,
    какая стена из какого набора кусков собирается"""
    bl_idname = "gtatools.building_new"
    bl_label = "Новое здание"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        fresh, error = _append(context, 'Object', BASE_OBJECT)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}
        if not fresh:
            self.report({'WARNING'}, T("В файле нет объекта заготовки"))
            return {'CANCELLED'}
        for obj in fresh:
            obj.location = context.scene.cursor.location
        context.view_layer.objects.active = fresh[0]
        self.report({'INFO'}, T("Заготовка здания добавлена"))
        return {'FINISHED'}


class GTATOOLS_OT_building_to_mesh(bpy.types.Operator):
    """Собрать здание в обычный меш — копией, рядом с оригиналом.
    Оригинал с модификатором остаётся живым, а копия идёт в обычный
    экспорт DFF со всем нашим конвейером"""
    bl_idname = "gtatools.building_to_mesh"
    bl_label = "Собрать в меш"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (context.mode == 'OBJECT' and obj is not None
                and obj.type == 'MESH' and bool(obj.modifiers))

    def execute(self, context):
        source = context.object

        copy = source.copy()
        copy.data = source.data.copy()
        copy.name = "%s_меш" % source.name
        (source.users_collection[0] if source.users_collection
         else context.scene.collection).objects.link(copy)

        # Без Realize Instances модификатор отдаёт инстансы, и Convert
        # даёт пустой меш. Auto-Building включает этот же флаг в своей
        # кнопке Apply modifier.
        mod = copy.modifiers.get(MODIFIER)
        if mod is not None and REALIZE in mod:
            mod[REALIZE] = True

        for obj in context.selected_objects:
            obj.select_set(False)
        copy.select_set(True)
        context.view_layer.objects.active = copy
        bpy.ops.object.convert(target='MESH')
        try:
            bpy.ops.object.material_slot_remove_unused()
        except RuntimeError:
            pass

        faces = len(copy.data.polygons)
        if not faces:
            # Гео-ноды могут отдавать инстансы, а Convert их не
            # материализует. У Auto-Building за это отвечает свой
            # переключатель — подсказываем, а не молчим.
            self.report({'WARNING'},
                        T("Меш пустой — включи вывод реальной геометрии "
                          "в модификаторе"))
            return {'CANCELLED'}
        self.report({'INFO'}, "%s %d" % (T("Полигонов:"), faces))
        return {'FINISHED'}
