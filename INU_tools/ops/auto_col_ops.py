# INU_tools.ops.auto_col_ops — авто-генерация коллизии (COL) из модели.
#
# Выделяешь модель → кнопка → создаётся редактируемый <имя>_COL:
#   CONVEX — выпуклая оболочка (bmesh.ops.convex_hull);
#   BOX    — осевой габаритный бокс (AABB).
# Меш помечается inu.type='COL' и дальше идёт в обычный COL-экспорт
# (col_export._collect_mesh). Всё на встроенном bmesh/numpy — без внешнего кода
# (clean-room: никаких сторонних исходников).
#
# ВАЖНО: НЕ добавлять `from __future__ import annotations`.

import bpy
import bmesh
from mathutils import Vector
from bpy.props import EnumProperty

from .. import T


def _bbox_local(obj):
    """AABB меша в ЛОКАЛЬНЫХ координатах (COL пишется в локальном пространстве)."""
    bb = [Vector(c) for c in obj.bound_box]
    mn = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    mx = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    return mn, mx


def _box_mesh(name, mn, mx):
    verts = [(mn.x, mn.y, mn.z), (mx.x, mn.y, mn.z), (mx.x, mx.y, mn.z), (mn.x, mx.y, mn.z),
             (mn.x, mn.y, mx.z), (mx.x, mn.y, mx.z), (mx.x, mx.y, mx.z), (mn.x, mx.y, mx.z)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    return me


def _hull_mesh(name, src):
    """Выпуклая оболочка меша `src` (bmesh.ops.convex_hull), локальные координаты."""
    bm = bmesh.new()
    bm.from_mesh(src.data)
    if not bm.verts:
        bm.free()
        return None
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    # оставляем только оболочку: удаляем внутренние/неиспользованные вершины
    to_del = list(set(res.get('geom_interior', []) + res.get('geom_unused', [])))
    if to_del:
        bmesh.ops.delete(bm, geom=to_del, context='VERTS')
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return me


def _make_col_object(src, base_name, mode):
    """Создать/обновить <base>_COL из `src` по режиму. Возвращает объект или None."""
    cname = base_name + "_COL"
    if cname == src.name:               # источник сам является COL — не трогаем
        return None
    if mode == 'BOX':
        mn, mx = _bbox_local(src)
        me = _box_mesh(cname, mn, mx)
    else:                               # CONVEX
        me = _hull_mesh(cname, src)
        if me is None:                  # пустой меш → fallback на бокс
            mn, mx = _bbox_local(src)
            me = _box_mesh(cname, mn, mx)
    me.name = cname
    existing = bpy.data.objects.get(cname)
    if existing is not None:            # перегенерация: подменяем меш у существующего
        old = existing.data
        existing.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
        # новая форма — сохранённые границы старого COL (col_import) сбрасываем,
        # иначе экспорт возьмёт их вместо пересчитанных
        existing.pop('inu_col_bounds', None)
        obj = existing
    else:
        obj = bpy.data.objects.new(cname, me)
        obj.matrix_world = src.matrix_world.copy()
        for c in (list(src.users_collection) or [bpy.context.scene.collection]):
            c.objects.link(obj)
    if hasattr(obj, 'inu'):
        obj.inu.type = 'COL'
    return obj


class GTATOOLS_OT_auto_col(bpy.types.Operator):
    """Сгенерировать коллизию (<имя>_COL) из выделенной модели: выпуклая оболочка или габаритный бокс. Меш редактируемый, дальше идёт в COL-экспорт."""
    bl_idname = "gtatools.auto_col"
    bl_label = "INU: Сгенерировать COL"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name=T("Тип коллизии"),
        items=[
            ('CONVEX', T("Выпуклая оболочка"),
             T("Выпуклая оболочка вокруг модели — точнее по форме, чем бокс")),
            ('BOX', T("Габаритный бокс"),
             T("Осевой габаритный бокс — самый дешёвый, для простых/дальних моделей")),
        ],
        default='CONVEX',
    )

    @classmethod
    def poll(cls, context):
        return any(getattr(o, 'type', None) == 'MESH'
                   for o in context.selected_objects)

    def execute(self, context):
        from ..tools.model_utils import find_all_selected_model_groups
        groups = find_all_selected_model_groups()
        made, done = 0, set()
        for base_name, models in groups.items():
            src = models['DFF'] or models['LOD'] or models['COL']
            if src is None or base_name in done:
                continue
            done.add(base_name)
            try:
                if _make_col_object(src, base_name, self.mode) is not None:
                    made += 1
            except Exception as exc:                      # noqa: BLE001
                print(f"[INU auto-col] failed for {base_name}: {exc}")
        if made:
            self.report({'INFO'}, T("Коллизия создана: {0}").format(made))
        else:
            self.report({'WARNING'}, T("Нет модели для коллизии"))
        return {'FINISHED'}
