# INU_tools.ops.chunk_ops — разделение карты/меша на чанки по XY-сетке.
#
# Адаптация ChunkTools (https://github.com/milevskiy27/ChunkTools,
# Apache License 2.0, © milevskiy27 + Google Gemini): нарезка меша на
# квадратные чанки по глобальной XY-сетке кратно `chunk_size`.
#
# Отличия от оригинала:
#  • разнос граней по объектам — через наш _make_fragment (копия объекта +
#    удаление чужих граней), поэтому UV / vertex-color / 2 UV / нормали /
#    материалы сохраняются как есть;
#  • режим EXACT режет всю сетку ОДНИМ проходом bisect (по каждой линии),
#    затем группирует грани по ячейкам — вместо 4 разрезов на КАЖДУЮ ячейку
#    (у оригинала это O(ячейки × меш));
#  • прогресс в статус-баре, локализация, имена `Base_Chunk_X_Y`.

import math

import bpy
import bmesh
from bpy.props import EnumProperty, FloatProperty, BoolProperty
from mathutils import Vector

from .. import T
from .fragment_ops import _make_fragment


def _world_bbox_xy(obj):
    """(min_x, max_x, min_y, max_y) объекта в мировых координатах."""
    mw = obj.matrix_world
    corners = [mw @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in corners]
    ys = [v.y for v in corners]
    return min(xs), max(xs), min(ys), max(ys)


def _bisect_world_grid(bm, mw, chunk_size, bbox):
    """Разрезать bmesh плоскостями по ВСЕМ внутренним линиям XY-сетки (мировые
    X=k·size, Y=k·size). Плоскости пересчитываются в локальные координаты меша
    (bmesh работает в них). Резы без удаления сторон — только делят грани."""
    inv = mw.inverted()
    rot = inv.to_3x3()
    min_x, max_x, min_y, max_y = bbox
    xk = range(math.floor(min_x / chunk_size) + 1, math.ceil(max_x / chunk_size))
    yk = range(math.floor(min_y / chunk_size) + 1, math.ceil(max_y / chunk_size))
    for k in xk:
        co = inv @ Vector((k * chunk_size, 0.0, 0.0))
        no = rot @ Vector((1.0, 0.0, 0.0))
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no,
                               clear_inner=False, clear_outer=False)
    for k in yk:
        co = inv @ Vector((0.0, k * chunk_size, 0.0))
        no = rot @ Vector((0.0, 1.0, 0.0))
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no,
                               clear_inner=False, clear_outer=False)


def _chunk_groups(mesh, mw, chunk_size):
    """dict[(cx, cy)] -> set(face_index): грань → ячейка глобальной сетки по
    МИРОВОМУ центру грани (floor(center / chunk_size))."""
    groups = {}
    for poly in mesh.polygons:
        w = mw @ poly.center
        cx = math.floor(w.x / chunk_size)
        cy = math.floor(w.y / chunk_size)
        groups.setdefault((cx, cy), set()).add(poly.index)
    return groups


class GTATOOLS_OT_chunk_map(bpy.types.Operator):
    """Разделить карту/меш на квадратные чанки по XY-сетке.

Каждый чанк — отдельный объект `Имя_Chunk_X_Y` (X/Y — индексы глобальной
сетки кратно размеру чанка, так соседние карты стыкуются). UV, vertex-color,
материалы сохраняются. Оригинал прячется (не удаляется)."""
    bl_idname = "gtatools.chunk_map"
    bl_label = "INU: Разделить на чанки"
    bl_options = {'REGISTER', 'UNDO'}

    chunk_size: FloatProperty(
        name=T("Размер чанка (м)"),
        description=T("Сторона квадратного чанка в метрах"),
        default=180.0, min=1.0, soft_max=1000.0)
    cut_mode: EnumProperty(
        name=T("Способ резки"),
        items=[
            ('EXACT', T("По линиям сетки"),
             T("Физически режет полигоны точно по границам ячеек")),
            ('TOPOLOGY', T("По существующей геометрии"),
             T("Не режет полигоны; относит грань к чанку по её центру")),
        ],
        default='EXACT')
    duplicate_materials: BoolProperty(
        name=T("Раздельные материалы"),
        description=T("Создать уникальные копии материалов для каждого чанка"),
        default=False)
    set_origin_center: BoolProperty(
        name=T("Центр origin"),
        description=T("Поставить точку origin в геометрический центр чанка"),
        default=True)
    hide_original: BoolProperty(
        name=T("Скрыть оригинал"),
        description=T("Спрятать исходный меш во вьюпорте и рендере после нарезки"),
        default=True)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and len(obj.data.polygons) > 0)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "chunk_size")
        layout.prop(self, "cut_mode")
        layout.separator()
        layout.prop(self, "duplicate_materials")
        layout.prop(self, "set_origin_center")
        layout.prop(self, "hide_original")

    def execute(self, context):
        src = context.active_object
        size = float(self.chunk_size)
        base_name = src.name

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        # Как в оригинале: применяем поворот/масштаб (не позицию), иначе
        # мировая сетка не совпадёт с геометрией. Позиция сохраняется.
        try:
            bpy.ops.object.transform_apply(location=False, rotation=True,
                                           scale=True)
        except Exception:                              # noqa: BLE001
            pass

        bbox = _world_bbox_xy(src)

        # EXACT: временная копия, разрезанная всей сеткой; из неё группируем и
        # разносим. TOPOLOGY: источник — сам меш, без разрезов.
        cut_obj = src
        temp = None
        if self.cut_mode == 'EXACT':
            temp = src.copy()
            temp.data = src.data.copy()
            temp.name = base_name + "__inu_chunk_tmp"
            for coll in src.users_collection:
                coll.objects.link(temp)
            bm = bmesh.new()
            bm.from_mesh(temp.data)
            _bisect_world_grid(bm, temp.matrix_world, size, bbox)
            bm.to_mesh(temp.data)
            bm.free()
            cut_obj = temp

        groups = {k: v for k, v in _chunk_groups(
            cut_obj.data, cut_obj.matrix_world, size).items() if v}

        if not groups:
            if temp is not None:
                bpy.data.objects.remove(temp, do_unlink=True)
            self.report({'WARNING'}, T("Не на что резать (нет граней)"))
            return {'CANCELLED'}

        wm = context.window_manager
        total = len(groups)
        wm.progress_begin(0, total)
        created = []
        for i, ((cx, cy), keep) in enumerate(sorted(groups.items())):
            wm.progress_update(i)
            context.workspace.status_text_set(
                T("Чанки: {0}/{1}").format(i + 1, total))
            frag = _make_fragment(cut_obj, keep, f"{base_name}_Chunk_{cx}_{cy}")
            if self.duplicate_materials:
                for slot in frag.material_slots:
                    if slot.material:
                        slot.material = slot.material.copy()
            created.append(frag)
        wm.progress_end()
        context.workspace.status_text_set(None)

        # Убрать временный разрезанный объект (его данные уже скопированы в чанки)
        if temp is not None:
            bpy.data.objects.remove(temp, do_unlink=True)

        if self.set_origin_center and created:
            bpy.ops.object.select_all(action='DESELECT')
            for o in created:
                o.select_set(True)
            context.view_layer.objects.active = created[0]
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

        if self.hide_original:
            src.hide_viewport = True
            src.hide_render = True

        # Выделить результат
        bpy.ops.object.select_all(action='DESELECT')
        for o in created:
            o.select_set(True)
        if created:
            context.view_layer.objects.active = created[0]

        self.report({'INFO'},
                    T("Карта разделена на {0} чанков").format(len(created)))
        return {'FINISHED'}


classes = (
    GTATOOLS_OT_chunk_map,
)
