# INU_tools.ops.light_ops — Prelight, Vertex Color, Itera, Lightmap,
# Vertex Paint, Scatter Light, Color Attribute operators.
#
# Phase 3 batch 6 (2026-04-26): 38 operators + 1 helper moved from
# __init__.py. Big-picture: anything that touches vertex colors, light
# baking, lightmap textures, itera materials, or vertex-paint mode
# tooling lives here. Material save/restore lives here too because
# they're paired with itera workflow.

import os
import bpy
from bpy.props import (
    StringProperty, BoolProperty, FloatProperty, EnumProperty,
)
from mathutils import Vector

from .. import T
from ..tools import compat
from ..tools.model_utils import find_selected_models
from ..tools.prelight import (
    average_colors_on_coplanar_faces,
    create_prelight_scene_lights, remove_prelight_scene_lights,
    create_prelight_sun, remove_prelight_sun, PRELIGHT_SUN_NAME,
    bake_vertex_colors_from_lights, bake_vertex_colors_simple,
    apply_brightness_offset, analyze_vertex_colors,
    smooth_vertex_colors, adjust_vertex_colors_contrast,
    adjust_vertex_colors_brightness, adjust_vertex_colors_gamma,
    lift_shadows,
    setup_prelight_preview,
    setup_alpha_preview, scene_vertex_alpha_objects,
    cleanup_orphan_alpha_nodes,
    add_scatter_layer, remove_scatter_layer, clear_scatter_layers,
    remove_fill_color_by_index, get_selected_faces_color,
    fill_selected_faces_with_backup, restore_filled_faces,
    scatter_light_from_selected,
    scatter_color_from_selected,
    prelight_foliage,
)


def _pub(op, type_set, msg):
    """``op.report(type_set, msg)`` AND mirror the text into the active
    floater's status strip (so a button pressed in the Lighting floater
    shows the same notification the N-panel shows). The mirror is a no-op
    unless the op was launched from a floater button."""
    op.report(type_set, msg)
    try:
        from .floater.base import set_floater_status
        lvl = ('ERROR' if 'ERROR' in type_set
               else 'WARNING' if 'WARNING' in type_set else 'INFO')
        set_floater_status(str(msg), lvl)
    except Exception:
        pass


def _force_object_mode(context):
    """Switch active object out of EDIT (or other non-OBJECT) mode and
    return a `(prev_mode, prev_obj)` tuple for later restore.

    Bake helpers iterate `mesh.color_attributes.data` via foreach_set;
    в EDIT mode mesh-данные стейджатся в BMesh, поэтому foreach_set
    видит 0-length массив → cryptic TypeError. Принудительный выход
    в OBJECT — единственный надёжный способ.

    Returns ``(None, None)`` если переключение не нужно или невозможно.
    """
    obj = context.active_object
    if obj is None:
        return None, None
    prev_mode = obj.mode
    if prev_mode == 'OBJECT':
        return None, None
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except RuntimeError:
        return None, None
    return prev_mode, obj


def _restore_mode(prev_mode, prev_obj):
    """Restore mode captured by `_force_object_mode`. Silent no-op on
    failure (e.g., объект удалён, mode недоступен)."""
    if not prev_mode or prev_obj is None:
        return
    try:
        # Make sure the object that was in edit mode is still active —
        # other ops in the batch could have changed selection.
        if bpy.context.view_layer.objects.active is not prev_obj:
            bpy.context.view_layer.objects.active = prev_obj
        bpy.ops.object.mode_set(mode=prev_mode)
    except (RuntimeError, ReferenceError):
        pass


# Снимок прилайта для операции «Цвет»: obj.name -> (attr_name, np.float32 flat).
# «Запечь цвет» кладёт сюда состояние ДО применения, «Сброс» восстанавливает.
_FOLIAGE_COLOR_BACKUP = {}


def _foliage_snapshot(obj):
    """Сохранить текущий активный color attribute в память (до изменений)."""
    import numpy as np
    mesh = obj.data
    attr = compat.vcol_active(mesh)
    if attr is None:
        return False
    flat = np.empty(len(attr.data) * 4, dtype=np.float32)
    attr.data.foreach_get('color', flat)
    _FOLIAGE_COLOR_BACKUP[obj.name] = (attr.name, flat)
    return True


def _foliage_restore(obj):
    """Вернуть прилайт к снимку, сделанному при «Запечь цвет»."""
    data = _FOLIAGE_COLOR_BACKUP.get(obj.name)
    if not data:
        return False, T("Нет сохранённого прилайта — сначала «Запечь цвет»")
    attr_name, flat = data
    mesh = obj.data
    attr = compat.vcol_get(mesh, attr_name) or compat.vcol_active(mesh)
    if attr is None or len(attr.data) * 4 != len(flat):
        return False, T("Сохранённый прилайт не подходит (меш изменился)")
    attr.data.foreach_set('color', flat)
    mesh.update()
    return True, T("Прилайт сброшен к состоянию до «Запечь цвет»")


class GTATOOLS_OT_prelight_foliage(bpy.types.Operator):
    """Прилайт листвы: темнее в центре кроны, светлее на периферии,
    + опциональная смена цвета листвы (tint). Геометрический градиент,
    без света сцены — для billboard-листвы деревьев."""
    bl_idname = "gtatools.prelight_foliage"
    bl_label = "INU: Прилайтить листву"
    bl_options = {'REGISTER', 'UNDO'}

    # Режим: SHADE — только затенение кроны (свой материал), COLOR — только
    # цвет листвы (свой материал), BOTH — всё сразу (старое поведение).
    mode: bpy.props.EnumProperty(
        items=[('SHADE', "Крона", "Только затенение кроны"),
               ('COLOR', "Цвет", "Только цвет листвы"),
               ('BOTH', "Всё", "Затенение + цвет")],
        default='BOTH', options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        s = context.scene.inu_settings
        obj = context.active_object

        # Материал по режиму: затенение и цвет — независимые операции со
        # своими полями материала.
        if self.mode == 'COLOR':
            name = s.gtatools_foliage_color_material_name.strip()
        else:
            name = s.gtatools_foliage_material_name.strip()
        # Имя материала → индекс слота (пусто = без фильтра по материалу)
        mat_index = None
        if name:
            for i, slot in enumerate(obj.material_slots):
                if slot.material and slot.material.name == name:
                    mat_index = i
                    break
            if mat_index is None:
                _pub(self, {'WARNING'},
                            f"Материал «{name}» не найден на объекте")
                return {'CANCELLED'}

        # foreach_set по color_attributes требует OBJECT mode (в EDIT
        # данные стейджатся в BMesh — см. _force_object_mode).
        prev_mode, prev_obj = _force_object_mode(context)
        try:
            # «Запечь цвет»: запоминаем прилайт ДО применения, чтобы «Сброс»
            # мог вернуть модель к этому состоянию.
            if self.mode == 'COLOR':
                _foliage_snapshot(obj)
            ok, msg = prelight_foliage(
                obj,
                material_index=mat_index,
                select_only=s.gtatools_foliage_select_only,
                inside=s.gtatools_foliage_inside,
                outside=s.gtatools_foliage_outside,
                gamma=s.gtatools_foliage_gamma,
                height_dark=s.gtatools_foliage_height_dark,
                color_height_dark=s.gtatools_foliage_color_height_dark,
                top_bright=s.gtatools_foliage_top_bright,
                top_height=s.gtatools_foliage_top_height,
                variation=s.gtatools_foliage_variation,
                light_tint=tuple(s.gtatools_foliage_light_tint),
                shadow_tint=tuple(s.gtatools_foliage_shadow_tint),
                tint_strength=s.gtatools_foliage_tint_strength,
                metric=s.gtatools_foliage_metric,
                blend=s.gtatools_foliage_blend,
                both_sides=s.gtatools_foliage_both_sides,
                mode=self.mode,
            )
        finally:
            if prev_obj is not None and prev_mode is not None:
                try:
                    context.view_layer.objects.active = prev_obj
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass

        if not ok:
            _pub(self, {'WARNING'}, msg)
            return {'CANCELLED'}
        _pub(self, {'INFO'}, msg)
        # Обновить вьюпорт, если включён prelight-preview
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class GTATOOLS_OT_foliage_color_reset(bpy.types.Operator):
    """Сбросить прилайт модели к состоянию, сохранённому при «Запечь цвет»."""
    bl_idname = "gtatools.foliage_color_reset"
    bl_label = "INU: Сброс цвета листвы"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and obj.name in _FOLIAGE_COLOR_BACKUP)

    def execute(self, context):
        obj = context.active_object
        prev_mode, prev_obj = _force_object_mode(context)
        try:
            ok, msg = _foliage_restore(obj)
        finally:
            if prev_obj is not None and prev_mode is not None:
                try:
                    context.view_layer.objects.active = prev_obj
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass
        if not ok:
            _pub(self, {'WARNING'}, msg)
            return {'CANCELLED'}
        _pub(self, {'INFO'}, msg)
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class GTATOOLS_OT_lightcut_ring_add(bpy.types.Operator):
    """Добавить кольцо в список резака света"""
    bl_idname = "gtatools.lightcut_ring_add"
    bl_label = "INU: + Кольцо"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.inu_settings
        rl = s.gtatools_lightcut_ringlist
        item = rl.add()
        n = len(rl)
        # равномерный дефолт между центром и краем
        item.radius = max(0.05, min(0.95, n / (n + 1.0)))
        s.gtatools_lightcut_ring_index = n - 1
        rebuild_lightcutter(context)
        return {'FINISHED'}


class GTATOOLS_OT_lightcut_ring_remove(bpy.types.Operator):
    """Удалить кольцо из списка резака света"""
    bl_idname = "gtatools.lightcut_ring_remove"
    bl_label = "INU: - Кольцо"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        s = context.scene.inu_settings
        rl = s.gtatools_lightcut_ringlist
        i = self.index if self.index >= 0 else int(s.gtatools_lightcut_ring_index)
        if 0 <= i < len(rl):
            rl.remove(i)
            s.gtatools_lightcut_ring_index = max(0, i - 1)
        rebuild_lightcutter(context)
        return {'FINISHED'}


def _lightcut_radii(s):
    """Доли радиусов колец (0..1), по возрастанию, + внешнее (1.0)."""
    fr = set()
    for r in s.gtatools_lightcut_ringlist:
        fr.add(min(1.0, max(0.0, float(r.radius))))
    fr.add(1.0)
    return sorted(f for f in fr if f > 1.0e-4)


def _build_lightcutter_mesh(s, me):
    """Перестроить меш резака (концентрические цилиндры по кольцам, или
    сфера) из настроек. Каждое кольцо — отдельный вертикальный цилиндр,
    чтобы кольца были ВИДНЫ как цилиндры."""
    import bmesh
    import math
    typ = s.gtatools_lightcut_type
    R = max(0.001, float(s.gtatools_lightcut_radius) or 3.0)
    segs = max(3, int(s.gtatools_lightcut_segments))
    bm = bmesh.new()
    if typ == 'SPHERE':
        try:
            bmesh.ops.create_uvsphere(
                bm, u_segments=segs, v_segments=max(3, segs // 2), radius=R)
        except TypeError:
            bmesh.ops.create_uvsphere(
                bm, u_segments=segs, v_segments=max(3, segs // 2), diameter=R)
    else:
        radii = [f * R for f in _lightcut_radii(s)]   # кольца + внешний
        h = R * 0.5
        for rr in radii:
            top, bot = [], []
            for k in range(segs):
                a = 2.0 * math.pi * k / segs
                x = rr * math.cos(a)
                y = rr * math.sin(a)
                top.append(bm.verts.new((x, y, h)))
                bot.append(bm.verts.new((x, y, -h)))
            for k in range(segs):
                nk = (k + 1) % segs
                bm.edges.new((top[k], top[nk]))
                bm.edges.new((bot[k], bot[nk]))
                bm.edges.new((top[k], bot[k]))
    bm.to_mesh(me)
    bm.free()
    me.update()


def rebuild_lightcutter(context):
    """Живое обновление: перестроить меш INU_LightCutter из настроек, если
    он существует (вызывается из update-колбэков свойств)."""
    obj = bpy.data.objects.get("INU_LightCutter")
    if obj is None or obj.type != 'MESH':
        return
    s = getattr(getattr(context, 'scene', None), 'inu_settings', None)
    if s is not None:
        _build_lightcutter_mesh(s, obj.data)


class GTATOOLS_OT_lightcut_create(bpy.types.Operator):
    """Создать вайр-резак света (цилиндр с кольцами или сфера). Меняй
    радиус/сегменты/кольца — он обновляется вживую. Двигай куда нужно,
    затем «Нарезать по резаку»."""
    bl_idname = "gtatools.lightcut_create"
    bl_label = "INU: Создать резак света"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.inu_settings
        ao = context.active_object
        if ao is not None and ao.type == 'LIGHT':
            center = ao.matrix_world.translation.copy()
        else:
            center = context.scene.cursor.location.copy()

        old = bpy.data.objects.get("INU_LightCutter")
        if old is not None:
            try:
                bpy.data.objects.remove(old, do_unlink=True)
            except Exception:
                pass

        me = bpy.data.meshes.new("INU_LightCutter")
        _build_lightcutter_mesh(s, me)
        obj = bpy.data.objects.new("INU_LightCutter", me)
        obj.location = center
        obj.display_type = 'WIRE'
        obj.show_in_front = True
        obj['inu_lightcutter'] = True
        context.collection.objects.link(obj)
        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        _pub(self, {'INFO'},
             T("Резак создан — крути настройки (обновляется), потом «Нарезать»"))
        return {'FINISHED'}


class GTATOOLS_OT_light_topo_cut(bpy.types.Operator):
    """Нарезать по резаку: либо чистый отдельный диск (кольца+заливка,
    повторяет рельеф), либо врезать кольца в пол. Запекает радиальный
    градиент света (центр ярко → край тёмно, кольца = ступени плавности)."""
    bl_idname = "gtatools.light_topo_cut"
    bl_label = "INU: Нарезать по резаку"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from mathutils import Vector
        s = context.scene.inu_settings
        R = max(0.001, float(s.gtatools_lightcut_radius) or 3.0)
        segs = max(3, int(s.gtatools_lightcut_segments))
        ring_fracs = _lightcut_radii(s)

        # центр: резак-объект → активная лампа → 3D-курсор
        cutter = bpy.data.objects.get("INU_LightCutter")
        ao = context.active_object
        lamp_rgb = (1.0, 1.0, 1.0)
        rot = None   # cutter orientation → tilted cut; None = vertical (legacy)
        if cutter is not None:
            center = cutter.matrix_world.translation.copy()
            # Full orientation (rotation only, scale dropped) so a tilted
            # cutter cuts a tilted pool instead of a straight-down projection.
            rot = cutter.matrix_world.to_quaternion().to_matrix()
        elif ao is not None and ao.type == 'LIGHT':
            center = ao.matrix_world.translation.copy()
        else:
            center = context.scene.cursor.location.copy()
        if ao is not None and ao.type == 'LIGHT':
            lamp_rgb = tuple(ao.data.color)

        target = getattr(s, 'gtatools_lightcut_target', None)
        if target is None or getattr(target, 'type', None) != 'MESH':
            target = None

        prev_mode, prev_obj = _force_object_mode(context)
        try:
            if s.gtatools_lightcut_separate:
                obj = self._build_clean_disc(
                    context, center, R, segs, ring_fracs, target, lamp_rgb)
                if obj is None:
                    _pub(self, {'WARNING'}, T("Не удалось построить диск"))
                    return {'CANCELLED'}
                msg = f"Диск света создан: {obj.name}"
            else:
                if target is None:
                    _pub(self, {'WARNING'},
                         T("Для реза в пол укажи «Геометрия»"))
                    return {'CANCELLED'}
                n = self._knife_cut(context, target, center, R, segs,
                                    ring_fracs, lamp_rgb, rot)
                msg = f"Врезано в пол: {n} loops"
        except Exception as exc:
            _pub(self, {'ERROR'}, f"Резак: {exc}")
            return {'CANCELLED'}
        finally:
            if prev_obj is not None and prev_mode is not None:
                try:
                    context.view_layer.objects.active = prev_obj
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass

        _pub(self, {'INFO'}, msg)
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}

    # ── чистый отдельный диск (генерируемый веер) ──
    @staticmethod
    def _conform_z(context, target, x, y, z_above, fallback):
        from mathutils import Vector
        origin = Vector((x, y, z_above))
        down = Vector((0.0, 0.0, -1.0))
        if target is not None:
            mw = target.matrix_world
            mw_inv = mw.inverted()
            o_l = mw_inv @ origin
            d_l = (mw_inv.to_3x3() @ down).normalized()
            hit, loc_l, _n, _fi = target.ray_cast(o_l, d_l, distance=1.0e7)
            if hit:
                return (mw @ loc_l).z
        else:
            dg = context.evaluated_depsgraph_get()
            hit, loc, _n, _fi, _ob, _m = context.scene.ray_cast(
                dg, origin, down, distance=1.0e7)
            if hit:
                return loc.z
        return fallback

    @classmethod
    def _build_clean_disc(cls, context, center, R, segs, ring_fracs,
                          target, lamp_rgb):
        import bmesh
        import math
        import numpy as np
        radii = [f * R for f in ring_fracs]      # по возрастанию, последний = R
        z_above = center.z + R + 1.0
        LIFT = 0.02                               # чуть выше пола (без z-fight)

        me = bpy.data.meshes.new("LightCut")
        bm = bmesh.new()
        cz = cls._conform_z(context, target, center.x, center.y, z_above,
                            center.z) + LIFT
        cv = bm.verts.new((center.x, center.y, cz))
        rings = []
        for r in radii:
            row = []
            for k in range(segs):
                a = 2.0 * math.pi * k / segs
                x = center.x + r * math.cos(a)
                y = center.y + r * math.sin(a)
                z = cls._conform_z(context, target, x, y, z_above,
                                   center.z) + LIFT
                row.append(bm.verts.new((x, y, z)))
            rings.append(row)
        # центр → первое кольцо (веер)
        for k in range(segs):
            nk = (k + 1) % segs
            bm.faces.new((cv, rings[0][k], rings[0][nk]))
        # кольцо i → i+1 (квады)
        for i in range(len(rings) - 1):
            a_row, b_row = rings[i], rings[i + 1]
            for k in range(segs):
                nk = (k + 1) % segs
                bm.faces.new((a_row[k], b_row[k], b_row[nk], a_row[nk]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()

        obj = bpy.data.objects.new("LightCut", me)
        context.collection.objects.link(obj)

        # bake: яркость = 1 - dist/R (центр ярко → край тёмно)
        attr = compat.vcol_new(me, "Day")
        compat.vcol_active(me, attr)
        n_loops = len(me.loops)
        if n_loops:
            lv = np.empty(n_loops, dtype=np.int32)
            me.loops.foreach_get('vertex_index', lv)
            nv = len(me.vertices)
            co = np.empty(nv * 3, dtype=np.float32)
            me.vertices.foreach_get('co', co)
            co = co.reshape(nv, 3)
            lp = co[lv]
            d = np.sqrt((lp[:, 0] - center.x) ** 2 + (lp[:, 1] - center.y) ** 2)
            bright = np.clip(1.0 - d / max(R, 1e-6), 0.0, 1.0)
            flat = np.empty(n_loops * 4, dtype=np.float32)
            for c in range(3):
                flat[c::4] = bright * float(lamp_rgb[c])
            flat[3::4] = 1.0
            attr.data.foreach_set('color', flat)

        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return obj

    # ── врезка колец прямо в пол (knife-intersect, EXACT) ──
    @classmethod
    def _knife_cut(cls, context, ground, center, R, segs, ring_fracs,
                   lamp_rgb, rot=None):
        import bmesh
        import math
        import numpy as np
        from mathutils import Vector, Matrix
        if rot is None:
            rot = Matrix.Identity(3)   # vertical cut (straight down)
        me = ground.data
        wm = ground.matrix_world
        wm_inv = wm.inverted()
        # Wall half-length along the cutter's axis — long enough to cross the
        # whole ground even when tilted (world bbox diagonal is a safe bound).
        world_bb = [wm @ Vector(c) for c in ground.bound_box]
        diag = max((p - q).length for p in world_bb for q in world_bb) or 1.0
        H = diag + R + 1.0
        axis_w = rot @ Vector((0.0, 0.0, 1.0))   # cutter's local Z, in world

        cut_mat = bpy.data.materials.new("__INU_CUT__")
        me.materials.append(cut_mat)
        ci = len(me.materials) - 1

        bm = bmesh.new()
        bm.from_mesh(me)
        for f in ring_fracs:
            r = f * R   # world-space radius
            if r <= 1.0e-4:
                continue
            rt, rb = [], []
            for k in range(segs):
                a = 2.0 * math.pi * k / segs
                # ring offset in the cutter's (possibly tilted) XY plane,
                # walls run along the cutter's axis instead of straight down
                off_w = rot @ Vector((r * math.cos(a), r * math.sin(a), 0.0))
                p_top = center + off_w + axis_w * H
                p_bot = center + off_w - axis_w * H
                rt.append(bm.verts.new(wm_inv @ p_top))
                rb.append(bm.verts.new(wm_inv @ p_bot))
            for k in range(segs):
                nk = (k + 1) % segs
                fc = bm.faces.new((rt[k], rt[nk], rb[nk], rb[k]))
                fc.material_index = ci
        # Пред-очистка: склейка совпадающих вершин + пересчёт нормалей.
        # Грязная/вырожденная геометрия — главный триггер падения точного
        # булеана Blender (краш trimesh_nary_intersect по NULL).
        try:
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1.0e-5)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        except Exception:
            pass
        bm.to_mesh(me)
        bm.free()
        me.update()

        context.view_layer.objects.active = ground
        for o in list(context.selected_objects):
            o.select_set(False)
        ground.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        try:
            bpy.ops.mesh.intersect(mode='SELECT', separate_mode='NONE',
                                   solver='EXACT')
        except TypeError:
            bpy.ops.mesh.intersect()
        bpy.ops.object.mode_set(mode='OBJECT')

        bm = bmesh.new()
        bm.from_mesh(me)
        cut_faces = [f for f in bm.faces if f.material_index == ci]
        if cut_faces:
            bmesh.ops.delete(bm, geom=cut_faces, context='FACES')
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bm.to_mesh(me)
        bm.free()
        me.update()
        try:
            me.materials.pop(index=ci)
        except Exception:
            pass
        try:
            if cut_mat.users == 0:
                bpy.data.materials.remove(cut_mat)
        except Exception:
            pass

        # bake только на грани, целиком в радиусе
        attr = compat.vcol_active(me) or compat.vcol_new(me, "Day")
        compat.vcol_active(me, attr)
        n_loops = len(me.loops)
        if not n_loops:
            return 0
        lv = np.empty(n_loops, dtype=np.int32)
        me.loops.foreach_get('vertex_index', lv)
        nv = len(me.vertices)
        co = np.empty(nv * 3, dtype=np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(nv, 3)
        lp = co[lv]
        # Radius measured IN THE CUTTER'S PLANE: ground-local → world →
        # cutter-local, then XY distance — so a tilted pool fades correctly
        # along its own plane, not the world's.
        Mw = np.array(wm, dtype=np.float32)
        lp_h = np.column_stack([lp, np.ones(len(lp), dtype=np.float32)])
        lp_world = (lp_h @ Mw.T)[:, :3]
        rel = lp_world - np.array(center, dtype=np.float32)
        cl = rel @ np.array(rot, dtype=np.float32)
        d = np.sqrt(cl[:, 0] ** 2 + cl[:, 1] ** 2)
        n_poly = len(me.polygons)
        ls = np.empty(n_poly, dtype=np.int32)
        lt = np.empty(n_poly, dtype=np.int32)
        me.polygons.foreach_get('loop_start', ls)
        me.polygons.foreach_get('loop_total', lt)
        ok = (d <= R).astype(np.int8)
        poly_in = np.minimum.reduceat(ok, ls) == 1
        within = np.repeat(poly_in, lt)
        bright = np.clip(1.0 - d / max(R, 1e-6), 0.0, 1.0)
        flat = np.empty(n_loops * 4, dtype=np.float32)
        attr.data.foreach_get('color', flat)
        f4 = flat.reshape(n_loops, 4)
        add = np.zeros((n_loops, 3), dtype=np.float32)
        for c in range(3):
            add[:, c] = bright * float(lamp_rgb[c])
        f4[within, 0:3] = np.clip(f4[within, 0:3] + add[within], 0.0, 1.0)
        f4[within, 3] = 1.0
        attr.data.foreach_set('color', f4.ravel())
        return int(within.sum())


class GTATOOLS_OT_lightmap_generate(bpy.types.Operator):
    """Сгенерировать код lightmap для выделенного объекта"""
    bl_idname = "gtatools.lightmap_generate"
    bl_label = "INU: Generate Lightmap Code"

    def execute(self, context):
        scene = context.scene
        obj = context.active_object

        if not obj:
            _pub(self, {'WARNING'}, "No object selected")
            scene.inu_settings.gtatools_lightmap_result = "Error: no object selected"
            return {'CANCELLED'}

        textures = self.get_textures_from_object(obj)

        if not textures:
            _pub(self, {'WARNING'}, "No textures found")
            scene.inu_settings.gtatools_lightmap_result = "Error: no textures found"
            return {'CANCELLED'}

        lightmap_path = scene.inu_settings.gtatools_lightmap_path if scene.inu_settings.gtatools_lightmap_path else "lightmaps/lightmap.png"
        model_id = scene.inu_settings.gtatools_model_id if scene.inu_settings.gtatools_model_id else "0"

        code = self.generate_code(textures, lightmap_path, model_id)
        scene.inu_settings.gtatools_lightmap_result = code

        _pub(self, {'INFO'}, f"Found {len(textures)} textures")
        return {'FINISHED'}

    def get_textures_from_object(self, obj):
        textures = []
        if not obj.data or not hasattr(obj.data, 'materials'):
            return textures

        for mat_slot in obj.material_slots:
            mat = mat_slot.material
            if not mat or not mat.use_nodes:
                continue

            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    from ..core.tex_name import clean_texture_name
                    tex_name = clean_texture_name(node.image.name)
                    if tex_name not in textures:
                        textures.append(tex_name)

        return textures

    def generate_code(self, textures, lightmap_path, model_id):
        lines = []
        lines.append("    {")
        lines.append("        textures = {")
        for tex in textures:
            lines.append(f'            "{tex}",')
        lines.append("        },")
        lines.append(f'        lightmap = "{lightmap_path}",')
        lines.append(f"        models = {{{model_id}}}")
        lines.append("    },")
        return '\n'.join(lines)


class GTATOOLS_OT_lightmap_copy(bpy.types.Operator):
    """Копировать результат в буфер обмена"""
    bl_idname = "gtatools.lightmap_copy"
    bl_label = "INU: Copy to Clipboard"

    def execute(self, context):
        scene = context.scene
        if scene.inu_settings.gtatools_lightmap_result:
            context.window_manager.clipboard = scene.inu_settings.gtatools_lightmap_result
            _pub(self, {'INFO'}, "Copied to clipboard")
        return {'FINISHED'}


class GTATOOLS_OT_lightmap_clear(bpy.types.Operator):
    """Очистить сгенерированный код"""
    bl_idname = "gtatools.lightmap_clear"
    bl_label = "INU: Clear"

    def execute(self, context):
        context.scene.inu_settings.gtatools_lightmap_result = ""
        _pub(self, {'INFO'}, T("Код очищен"))
        return {'FINISHED'}


class GTATOOLS_OT_toggle_prelight_lights(bpy.types.Operator):
    """Toggle 8-light setup: создать если ламп нет, удалить если есть"""
    bl_idname = "gtatools.toggle_prelight_lights"
    bl_label = "INU: Toggle Prelight Lights"
    bl_options = {'REGISTER', 'UNDO'}

    distance: FloatProperty(
        name="Distance",
        description=T("Расстояние ламп от центра"),
        default=100.0, min=1.0, max=1000.0)

    def execute(self, context):
        coll = bpy.data.collections.get("Prelight_Lights")
        has_lights = bool(coll and len(coll.objects) > 0)
        if has_lights:
            remove_prelight_scene_lights()
            _pub(self, {'INFO'}, T("Лампы удалены"))
            return {'FINISHED'}

        obj = context.active_object
        if obj is None:
            # No active object → use scene origin so the toggle still
            # works and produces a usable lamp ring.
            world_center = Vector((0.0, 0.0, 0.0))
        else:
            bbox_center = sum((Vector(b) for b in obj.bound_box), Vector()) / 8
            world_center = obj.matrix_world @ bbox_center
        lights = create_prelight_scene_lights(world_center, self.distance)
        _pub(self, {'INFO'}, f"Created {len(lights)} lights")
        return {'FINISHED'}


class GTATOOLS_OT_toggle_prelight_sun(bpy.types.Operator):
    """Создать/удалить «солнце» для prelight (отдельно от 8 точек).

    Направленный источник под углом «сверху-спереди» (как солнце GTA), цвет
    как у 8 ламп. Запекается теми же кнопками (POINT и SUN считаются вместе).
    Энергию подгони, если ярче/темнее восьмёрки."""
    bl_idname = "gtatools.toggle_prelight_sun"
    bl_label = "INU: Toggle Prelight Sun"
    bl_options = {'REGISTER', 'UNDO'}

    energy: FloatProperty(
        name="Energy",
        description=T("Яркость солнца (≈ среднему 8 точек)"),
        default=9.0, min=0.0, max=100.0)

    def execute(self, context):
        if bpy.data.objects.get(PRELIGHT_SUN_NAME) is not None:
            remove_prelight_sun()
            _pub(self, {'INFO'}, T("Солнце удалено"))
            return {'FINISHED'}

        obj = context.active_object
        if obj is None:
            world_center = Vector((0.0, 0.0, 0.0))
        else:
            bbox_center = sum((Vector(b) for b in obj.bound_box), Vector()) / 8
            world_center = obj.matrix_world @ bbox_center
        create_prelight_sun(world_center, self.energy)
        _pub(self, {'INFO'}, T("Солнце создано"))
        return {'FINISHED'}


def _bake_snapshot_active(obj):
    """Snapshot the active colour attr (``color_srgb``) as a float32 buffer
    before a bake, so the «over» mode can add the bake on top of it."""
    a = compat.vcol_active(obj.data)
    if a is None or not len(a.data):
        return None
    import numpy as np
    buf = np.empty(len(a.data) * 4, dtype=np.float32)
    a.data.foreach_get('color_srgb', buf)
    return buf


def _bake_add_over(obj, snapshot):
    """Add the freshly-baked active colour ON TOP of *snapshot* (Add blend,
    full strength): rgb = clamp(snapshot + baked), alpha kept from
    snapshot. Used by the «Запечь поверх» buttons."""
    a = compat.vcol_active(obj.data)
    if a is None or snapshot is None or len(a.data) * 4 != snapshot.size:
        return False
    import numpy as np
    baked = np.empty(snapshot.size, dtype=np.float32)
    a.data.foreach_get('color_srgb', baked)
    for ch in (0, 1, 2):
        baked[ch::4] = np.clip(snapshot[ch::4] + baked[ch::4], 0.0, 1.0)
    baked[3::4] = snapshot[3::4]
    a.data.foreach_set('color_srgb', baked)
    obj.data.update()
    return True


def _prelight_allowed_types(st):
    """Множество типов ламп для запекания прилайта по тумблерам панели."""
    allowed = set()
    if getattr(st, 'gtatools_prelight_use_point', True):
        allowed.add('POINT')
    if getattr(st, 'gtatools_prelight_use_sun', True):
        allowed.add('SUN')
    if getattr(st, 'gtatools_prelight_use_spot', True):
        allowed.add('SPOT')
    if getattr(st, 'gtatools_prelight_use_area', True):
        allowed.add('AREA')
    return allowed


class GTATOOLS_OT_bake_vertex_colors(bpy.types.Operator):
    """Запечь освещение от Point источников в vertex colors"""
    bl_idname = "gtatools.bake_vertex_colors"
    bl_label = "INU: Bake Vertex Colors"
    bl_options = {'REGISTER', 'UNDO'}

    use_shadows: BoolProperty(
        name="Use Shadows",
        description=T("Рассчитать тени (медленнее, но точнее)"),
        default=True
    )
    over: BoolProperty(
        name="Over Existing",
        description=T("Запечь поверх существующего прилайта (сложение), "
                      "а не перезаписывать"),
        default=False
    )

    @classmethod
    def description(cls, context, properties):
        if getattr(properties, 'over', False):
            return T("Запечь свет от ламп и солнца ПОВЕРХ существующего "
                     "прилайта (сложение, Add) с расчётом теней. Текущий "
                     "цвет НЕ стирается — к нему добавляется освещённость. "
                     "Пишет в активный канал (Day/Night), значения "
                     "зажимаются в 0–1")
        return T("Запечь свет от ламп и солнца в активный канал "
                 "(Day/Night) с расчётом теней. ПЕРЕЗАПИСЫВАЕТ текущий "
                 "цвет")

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            _pub(self, {'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        # Loop normals are read from EVALUATED mesh inside the bake
        # function — respects «Smooth by Angle» modifier and sharp
        # marks. No pre-bake topology mangling needed.
        from ..tools.prelight import apply_brightness_offset

        prev_mode, prev_obj = _force_object_mode(context)
        try:
            baked = 0
            for obj in mesh_objects:
                snap = _bake_snapshot_active(obj) if self.over else None
                _st = context.scene.inu_settings
                success, message = bake_vertex_colors_from_lights(
                    obj, self.use_shadows,
                    allowed_types=_prelight_allowed_types(_st),
                    use_hdri=getattr(_st, 'gtatools_prelight_use_hdri', False))
                if success:
                    if self.over and snap is not None:
                        # Add bake on top of the snapshot — no v_offset reset.
                        _bake_add_over(obj, snap)
                    else:
                        act = compat.vcol_active(obj.data)
                        if act:
                            attr_name = act.name
                            # Свежие колоры → applied-state = 0.
                            obj[f"v_offset_{attr_name}"] = 0.0
                            # Сохранить пользовательский V-offset: накладываем
                            # его поверх свежих колоров через apply_brightness_offset
                            # (он сам обновит obj["v_offset_<name>"]).
                            if attr_name == "Day" and obj.gtatools_v_offset_day != 0.0:
                                apply_brightness_offset(obj, obj.gtatools_v_offset_day)
                            elif attr_name == "Night" and obj.gtatools_v_offset_night != 0.0:
                                apply_brightness_offset(obj, obj.gtatools_v_offset_night)
                    baked += 1
        finally:
            _restore_mode(prev_mode, prev_obj)

        if baked:
            _pub(self, {'INFO'}, f"Baked from lights: {baked} objects")
            return {'FINISHED'}
        else:
            _pub(self, {'WARNING'}, T("Нет vertex colors"))
            return {'CANCELLED'}


class GTATOOLS_OT_bake_vertex_colors_simple(bpy.types.Operator):
    """Быстрое запекание vertex colors от Point источников (без теней)"""
    bl_idname = "gtatools.bake_vertex_colors_simple"
    bl_label = "INU: Bake Vertex Colors (Fast)"
    bl_options = {'REGISTER', 'UNDO'}

    over: BoolProperty(
        name="Over Existing",
        description=T("Запечь поверх существующего прилайта (сложение), "
                      "а не перезаписывать"),
        default=False
    )

    @classmethod
    def description(cls, context, properties):
        if getattr(properties, 'over', False):
            return T("Запечь свет от ламп ПОВЕРХ существующего прилайта "
                     "(сложение, Add), без теней. Текущий цвет НЕ "
                     "стирается — к нему добавляется освещённость. Пишет "
                     "в активный канал (Day/Night), значения зажимаются "
                     "в 0–1")
        return T("Быстро запечь свет от ламп в активный канал "
                 "(Day/Night), без теней. ПЕРЕЗАПИСЫВАЕТ текущий цвет")

    def execute(self, context):
        scene = context.scene
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            _pub(self, {'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        # Get settings from panel. "Запечь" — быстрый режим без теней;
        # для теней нужно жать кнопку «С тенями» рядом.
        ambient = scene.inu_settings.gtatools_bake_ambient
        intensity = scene.inu_settings.gtatools_bake_intensity
        gamma = scene.inu_settings.gtatools_bake_gamma
        use_shadows = False

        # Loop normals are read from EVALUATED mesh inside the bake
        # function — respects «Smooth by Angle» modifier and sharp marks.
        from ..tools.prelight import apply_brightness_offset

        prev_mode, prev_obj = _force_object_mode(context)
        try:
            baked = 0
            for obj in mesh_objects:
                snap = _bake_snapshot_active(obj) if self.over else None
                success, message = bake_vertex_colors_simple(
                    obj, ambient, intensity, gamma, use_shadows,
                    allowed_types=_prelight_allowed_types(scene.inu_settings),
                    use_hdri=getattr(scene.inu_settings,
                                     'gtatools_prelight_use_hdri', False))
                if success:
                    if self.over and snap is not None:
                        _bake_add_over(obj, snap)
                    else:
                        act = compat.vcol_active(obj.data)
                        if act:
                            attr_name = act.name
                            obj[f"v_offset_{attr_name}"] = 0.0
                            # Сохранить пользовательский V-offset поверх
                            # свежих колоров (см. полный комментарий выше).
                            if attr_name == "Day" and obj.gtatools_v_offset_day != 0.0:
                                apply_brightness_offset(obj, obj.gtatools_v_offset_day)
                            elif attr_name == "Night" and obj.gtatools_v_offset_night != 0.0:
                                apply_brightness_offset(obj, obj.gtatools_v_offset_night)
                    baked += 1
        finally:
            _restore_mode(prev_mode, prev_obj)

        if baked:
            _act = compat.vcol_active(mesh_objects[0].data)
            attr_name = _act.name if _act else "?"
            _pub(self, {'INFO'}, f"Baked to '{attr_name}' from {baked} objects")
            return {'FINISHED'}
        else:
            _pub(self, {'WARNING'}, T("Нет vertex colors"))
            return {'CANCELLED'}


class GTATOOLS_OT_reset_bake_settings(bpy.types.Operator):
    """Сбросить настройки запекания по умолчанию"""
    bl_idname = "gtatools.reset_bake_settings"
    bl_label = "INU: Reset to Default"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        scene.inu_settings.gtatools_bake_ambient = 0.10
        scene.inu_settings.gtatools_bake_intensity = 0.05
        scene.inu_settings.gtatools_bake_gamma = 0.50
        _pub(self, {'INFO'}, T("Настройки сброшены по умолчанию"))
        return {'FINISHED'}


class GTATOOLS_OT_reset_scatter_settings(bpy.types.Operator):
    """Сбросить настройки Scatter Light по умолчанию"""
    bl_idname = "gtatools.reset_scatter_settings"
    bl_label = "INU: Reset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        scene.inu_settings.gtatools_scatter_intensity = 1.0
        scene.inu_settings.gtatools_scatter_falloff = 1.5
        scene.inu_settings.gtatools_scatter_iterations = 3
        scene.inu_settings.gtatools_scatter_radius = 0.0
        _pub(self, {'INFO'}, "Scatter settings reset")
        return {'FINISHED'}


class GTATOOLS_OT_vc_smooth(bpy.types.Operator):
    """Сгладить vertex colors между соседними вершинами"""
    bl_idname = "gtatools.vc_smooth"
    bl_label = "INU: Smooth Vertex Colors"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            mesh_objects = [context.active_object] if context.active_object and context.active_object.type == 'MESH' else []
        iterations = context.scene.inu_settings.gtatools_vc_smooth_iterations
        factor = context.scene.inu_settings.gtatools_vc_smooth_factor
        count = 0
        for obj in mesh_objects:
            success, _ = smooth_vertex_colors(obj, iterations, factor)
            if success:
                count += 1
        _pub(self, {'INFO'}, f"Smooth: {count} objects")
        return {'FINISHED'} if count else {'CANCELLED'}


class GTATOOLS_OT_vc_contrast(bpy.types.Operator):
    """Применить контраст к vertex colors"""
    bl_idname = "gtatools.vc_contrast"
    bl_label = "INU: Apply Contrast"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            mesh_objects = [context.active_object] if context.active_object and context.active_object.type == 'MESH' else []
        contrast = context.scene.inu_settings.gtatools_vc_contrast
        count = 0
        for obj in mesh_objects:
            success, _ = adjust_vertex_colors_contrast(obj, contrast)
            if success:
                count += 1
        _pub(self, {'INFO'}, f"Contrast: {count} objects")
        return {'FINISHED'} if count else {'CANCELLED'}


class GTATOOLS_OT_vc_brightness(bpy.types.Operator):
    """Применить яркость к vertex colors"""
    bl_idname = "gtatools.vc_brightness"
    bl_label = "INU: Apply Brightness"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            mesh_objects = [context.active_object] if context.active_object and context.active_object.type == 'MESH' else []
        brightness = context.scene.inu_settings.gtatools_vc_brightness
        count = 0
        for obj in mesh_objects:
            success, _ = adjust_vertex_colors_brightness(obj, brightness)
            if success:
                count += 1
        _pub(self, {'INFO'}, f"Brightness: {count} objects")
        return {'FINISHED'} if count else {'CANCELLED'}


class GTATOOLS_OT_vc_gamma(bpy.types.Operator):
    """Применить гамма-коррекцию к vertex colors"""
    bl_idname = "gtatools.vc_gamma"
    bl_label = "INU: Apply Gamma"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            mesh_objects = [context.active_object] if context.active_object and context.active_object.type == 'MESH' else []
        gamma = context.scene.inu_settings.gtatools_vc_gamma

        count = 0
        for obj in mesh_objects:
            success, _ = adjust_vertex_colors_gamma(obj, gamma)
            if success:
                count += 1
        _pub(self, {'INFO'}, f"Gamma: {count} objects")
        return {'FINISHED'} if count else {'CANCELLED'}


class GTATOOLS_OT_lift_shadows(bpy.types.Operator):
    """Подтянуть тёмные участки к ярким, сохраняя шаг между гранями"""
    bl_idname = "gtatools.lift_shadows"
    bl_label = "INU: Lift Shadows"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            mesh_objects = [context.active_object] if context.active_object and context.active_object.type == 'MESH' else []
        strength = context.scene.inu_settings.gtatools_lift_shadows_strength
        count = 0
        for obj in mesh_objects:
            success, _ = lift_shadows(obj, strength)
            if success:
                count += 1
        _pub(self, {'INFO'}, f"Lift shadows: {count} objects (strength={strength:.2f})")
        return {'FINISHED'} if count else {'CANCELLED'}


class GTATOOLS_OT_vc_smooth_between(bpy.types.Operator):
    """Сгладить vertex colors на стыках между выделенными объектами"""
    bl_idname = "gtatools.vc_smooth_between"
    bl_label = "INU: Smooth Between Objects"
    bl_options = {'REGISTER', 'UNDO'}

    tolerance: FloatProperty(
        name="Tolerance",
        description=T("Максимальное расстояние между вершинами для сопоставления"),
        default=0.001,
        min=0.0001,
        max=1.0
    )

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if len(mesh_objects) < 2:
            _pub(self, {'ERROR'}, T("Выделите минимум 2 меш объекта"))
            return {'CANCELLED'}

        # Collect all boundary vertex data: (world_pos, obj, loop_indices, color_attr)
        from mathutils import kdtree

        all_points = []  # [(world_co, obj_index, vert_index)]
        obj_data = []    # [(obj, color_attr, {vert_idx: [loop_indices]})]

        for oi, obj in enumerate(mesh_objects):
            mesh = obj.data
            color_attr = compat.vcol_active(mesh)
            if color_attr is None:
                continue

            # Build vert -> loop indices map
            vert_loops = {}
            for poly in mesh.polygons:
                for vi, li in zip(poly.vertices, poly.loop_indices):
                    vert_loops.setdefault(vi, []).append(li)

            obj_data.append((obj, color_attr, vert_loops))

            mat_w = obj.matrix_world
            for vi, vert in enumerate(mesh.vertices):
                world_co = mat_w @ vert.co
                all_points.append((world_co, len(obj_data) - 1, vi))

        if not obj_data:
            _pub(self, {'WARNING'}, T("Нет vertex colors"))
            return {'CANCELLED'}

        # Build KD-tree from all vertices
        kd = kdtree.KDTree(len(all_points))
        for i, (co, _, _) in enumerate(all_points):
            kd.insert(co, i)
        kd.balance()

        # Find matching vertices and average their colors
        processed = set()
        smoothed_count = 0
        tol = self.tolerance

        for i, (co, oi, vi) in enumerate(all_points):
            if i in processed:
                continue

            # Find all vertices at this position
            matches = kd.find_range(co, tol)
            if len(matches) < 2:
                continue

            # Check if matches span multiple objects
            match_indices = [idx for _, idx, _ in matches]
            obj_indices = set(all_points[idx][1] for idx in match_indices)
            if len(obj_indices) < 2:
                continue

            # Collect all colors from matching vertices
            colors = []
            match_data = []  # [(obj_data_index, loop_indices)]
            for idx in match_indices:
                _, m_oi, m_vi = all_points[idx]
                obj, color_attr, vert_loops = obj_data[m_oi]
                loops = vert_loops.get(m_vi, [])
                for li in loops:
                    c = color_attr.data[li].color
                    colors.append((c[0], c[1], c[2], c[3]))
                match_data.append((m_oi, loops))
                processed.add(idx)

            if not colors:
                continue

            # Average
            avg = [sum(c[ch] for c in colors) / len(colors) for ch in range(4)]

            # Apply averaged color back
            for m_oi, loops in match_data:
                _, color_attr, _ = obj_data[m_oi]
                for li in loops:
                    color_attr.data[li].color = avg

            smoothed_count += 1

        # Update meshes
        for obj, _, _ in obj_data:
            obj.data.update()

        _pub(self, {'INFO'}, f"{T('Сглажено стыков:')} {smoothed_count}")
        return {'FINISHED'}


def wire_lightmap_material(mat, image, uv_name=None):
    """Повесить lightmap-текстуру `image` в материал `mat`: UV-нода (2-й
    канал) → Image Texture → Multiply поверх Base Color. ЕДИНАЯ точка
    прошивки для «Load Lightmap» (LP_-файл с диска) и «Применить LightMap»
    (запечённая bake-текстура); GTATOOLS_OT_remove_lightmap снимает ноды по
    этим же именам (Lightmap_UV / Lightmap_Texture / Lightmap_Mix).

    Идемпотентно: повторный вызов лишь обновляет картинку/UV существующих нод.

    ВАЖНО: сокеты Mix-нод берём ТОЛЬКО через compat.mix_input_a/b /
    mix_output_result — на 3.4+ `inputs['A']` по имени возвращает скрытый
    Float-сокет (у ShaderNodeMix три пары A/B; см. compat.py), из-за чего
    multiply не работал, а default_value падал с TypeError.

    Prelight_Mix учитываем ТОЛЬКО когда он реально питает Base Color —
    осиротевшая нода в старых сценах иначе утаскивала lightmap в висящую
    ветку без видимого эффекта (успех рапортовался, картинка не менялась).

    `uv_name` — имя UV-канала лайтмапа (пусто → активный UV меша).
    Возвращает True, если материал прошит/обновлён."""
    if not mat or not mat.use_nodes:
        return False
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if principled is None:
        return False

    existing = nodes.get("Lightmap_Texture")
    if existing is not None:               # уже прошит — обновить картинку/UV
        existing.image = image
        uvn = nodes.get("Lightmap_UV")
        if uvn is not None and uv_name:
            uvn.uv_map = uv_name
        return True

    base_in = principled.inputs['Base Color']
    prelight_mix = None
    original_socket = None
    if base_in.links:
        src_node = base_in.links[0].from_node
        original_socket = base_in.links[0].from_socket
        if src_node is not None and src_node.name == "Prelight_Mix":
            prelight_mix = src_node
            a_in = compat.mix_input_a(prelight_mix)
            original_socket = (a_in.links[0].from_socket
                               if (a_in is not None and a_in.is_linked)
                               else None)

    uv_node = nodes.new('ShaderNodeUVMap')
    uv_node.name = "Lightmap_UV"
    uv_node.label = "UV2"
    if uv_name:
        uv_node.uv_map = uv_name

    lm_tex = nodes.new('ShaderNodeTexImage')
    lm_tex.name = "Lightmap_Texture"
    lm_tex.label = "Lightmap"
    lm_tex.image = image

    mix_node = nodes.new(compat.MIX_NODE_TYPE)
    compat.setup_mix_rgba_node(mix_node, blend='MULTIPLY')
    compat.mix_input_factor(mix_node).default_value = 1.0
    mix_node.name = "Lightmap_Mix"
    mix_node.label = "Lightmap Mix"
    in_a = compat.mix_input_a(mix_node)
    in_b = compat.mix_input_b(mix_node)
    out_r = compat.mix_output_result(mix_node)

    anchor = original_socket.node if original_socket is not None else principled
    uv_node.location = (anchor.location.x - 700, anchor.location.y - 300)
    lm_tex.location = (anchor.location.x - 500, anchor.location.y - 300)
    mix_node.location = (anchor.location.x - 200, anchor.location.y - 150)

    links.new(uv_node.outputs['UV'], lm_tex.inputs['Vector'])
    if original_socket is not None:
        links.new(original_socket, in_a)
    else:
        in_a.default_value = (1.0, 1.0, 1.0, 1.0)
    links.new(lm_tex.outputs['Color'], in_b)
    if prelight_mix is not None:
        pa = compat.mix_input_a(prelight_mix)
        if pa is not None:
            links.new(out_r, pa)
        else:
            links.new(out_r, base_in)
    else:
        links.new(out_r, base_in)
    return True


class GTATOOLS_OT_load_lightmap(bpy.types.Operator):
    """Загрузить Lightmap из папки с .blend файлом (текстуры с приставкой LP_)"""
    bl_idname = "gtatools.load_lightmap"
    bl_label = "INU: Load Lightmap"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object

        if obj is None or obj.type != 'MESH':
            _pub(self, {'ERROR'}, T("Выберите меш объект!"))
            return {'CANCELLED'}

        # Get path to .blend file
        blend_path = bpy.data.filepath
        if not blend_path:
            _pub(self, {'ERROR'}, T("Сохраните .blend файл сначала!"))
            return {'CANCELLED'}

        blend_dir = os.path.dirname(blend_path)

        # Ищем текстуры с приставкой LP_
        lightmap_files = []
        supported_ext = ('.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tif', '.tiff')

        for filename in os.listdir(blend_dir):
            if filename.upper().startswith('LP_') and filename.lower().endswith(supported_ext):
                lightmap_files.append(filename)

        if not lightmap_files:
            _pub(self, {'ERROR'}, f"{T('Текстуры с приставкой LP_ не найдены в папке:')} {blend_dir}")
            return {'CANCELLED'}

        # Берём первую найденную текстуру
        lightmap_filename = lightmap_files[0]
        lightmap_path = os.path.join(blend_dir, lightmap_filename)

        # Загружаем текстуру
        lightmap_image = bpy.data.images.load(lightmap_path, check_existing=True)

        # Применяем лайтмап ко всем материалам объекта — общей прошивкой
        # wire_lightmap_material (она же в «Применить LightMap» bake_ops).
        # UV2: лайтмап ложится по второму UV-каналу (или единственному).
        uvl = obj.data.uv_layers
        uv_name = (uvl[1].name if len(uvl) >= 2
                   else (uvl[0].name if len(uvl) == 1 else ""))
        applied_count = 0
        for mat_slot in obj.material_slots:
            if wire_lightmap_material(mat_slot.material, lightmap_image,
                                      uv_name):
                applied_count += 1

        if applied_count > 0:
            _pub(self, {'INFO'}, f"Lightmap '{lightmap_filename}' applied to {applied_count} material(s)")
            return {'FINISHED'}
        else:
            _pub(self, {'WARNING'}, T("Не удалось применить лайтмап - нет подходящих материалов"))
            return {'CANCELLED'}


class GTATOOLS_OT_remove_lightmap(bpy.types.Operator):
    """Удалить Lightmap из материалов объекта"""
    bl_idname = "gtatools.remove_lightmap"
    bl_label = "INU: Remove Lightmap"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object

        if obj is None or obj.type != 'MESH':
            _pub(self, {'ERROR'}, T("Выберите меш объект!"))
            return {'CANCELLED'}

        removed_count = 0
        for mat_slot in obj.material_slots:
            mat = mat_slot.material
            if not mat or not mat.use_nodes:
                continue

            nodes = mat.node_tree.nodes
            links = mat.node_tree.links

            # Find lightmap nodes
            lm_tex = nodes.get("Lightmap_Texture")
            lm_mix = nodes.get("Lightmap_Mix")
            lm_uv = nodes.get("Lightmap_UV")

            if not lm_mix:
                continue

            # Находим Principled BSDF
            principled = None
            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled = node
                    break

            if principled:
                # Восстанавливаем оригинальное подключение
                base_color_input = principled.inputs['Base Color']
                prelight_mix = nodes.get("Prelight_Mix")

                # Находим что было подключено к входу (оригинальная текстура)
                _in1 = 'A' if 'A' in lm_mix.inputs else 'Color1'
                original_socket = None
                if lm_mix.inputs[_in1].links:
                    original_link = lm_mix.inputs[_in1].links[0]
                    original_socket = original_link.from_socket

                # Удаляем связи с Mix нодой
                for link in list(links):
                    if link.to_node == lm_mix or link.from_node == lm_mix:
                        links.remove(link)

                # Восстанавливаем оригинальное подключение
                if original_socket:
                    if prelight_mix:
                        # Если есть Prelight_Mix - подключаем к его входу A
                        links.new(original_socket, prelight_mix.inputs['A'])
                    else:
                        # Иначе напрямую к Base Color
                        links.new(original_socket, base_color_input)

            # Удаляем ноды лайтмапа
            if lm_tex:
                nodes.remove(lm_tex)
            if lm_mix:
                nodes.remove(lm_mix)
            if lm_uv:
                nodes.remove(lm_uv)

            removed_count += 1

        if removed_count > 0:
            _pub(self, {'INFO'}, f"{T('Lightmap удалён из ')}{removed_count}{T(' материал(ов)')}")
            return {'FINISHED'}
        else:
            _pub(self, {'WARNING'}, T("Lightmap не найден в материалах"))
            return {'CANCELLED'}


class GTATOOLS_OT_fill_prelight(bpy.types.Operator):
    """Залить прилайт одним плоским цветом: Day своим цветом, Night своим.

    RGB пишется напрямую в `color_srgb` (байт-в-байт, без gamma —
    значения COLOR_GAMMA-пропа уже в sRGB), вертекс-альфа сохраняется.
    Дефолты — доминирующие тона из test.dff (день 124, ночь 83)."""
    bl_idname = "gtatools.fill_prelight"
    bl_label = "INU: Fill Prelight"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import numpy as np
        s = context.scene.inu_settings
        day = tuple(s.gtatools_fill_prelight_day)      # sRGB 0-1 (COLOR_GAMMA)
        night = tuple(s.gtatools_fill_prelight_night)

        if s.gtatools_fill_prelight_selected_only:
            objs = [o for o in context.selected_objects if o.type == 'MESH']
        else:
            objs = [o for o in context.scene.objects if o.type == 'MESH']
        if not objs:
            _pub(self, {'ERROR'}, T("Нет мешей для заливки"))
            return {'CANCELLED'}

        def _fill(mesh, name, rgb):
            n = len(mesh.loops)
            if not n:
                return False
            attr = compat.vcol_get(mesh, name)
            created = attr is None
            if created:
                attr = compat.vcol_new(mesh, name)   # CORNER / BYTE_COLOR
            buf = np.empty(n * 4, dtype=np.float32)
            if created:
                buf[3::4] = 1.0                       # новый слой → альфа = 1
            else:
                attr.data.foreach_get('color_srgb', buf)  # читаем, чтобы СОХРАНИТЬ альфу
            buf[0::4] = rgb[0]                         # R \
            buf[1::4] = rgb[1]                         # G  } альфу (buf[3::4]) не трогаем
            buf[2::4] = rgb[2]                         # B /
            attr.data.foreach_set('color_srgb', buf)
            return True

        # foreach_set по color_attributes требует OBJECT mode (в EDIT
        # данные стейджатся в BMesh → 0-length массив).
        prev_mode, prev_obj = _force_object_mode(context)
        count = 0
        try:
            done_meshes = set()
            for o in objs:
                me = o.data
                if me.name in done_meshes:   # один и тот же меш (linked dup) — один раз
                    continue
                done_meshes.add(me.name)
                ok = _fill(me, "Day", day)
                _fill(me, "Night", night)
                me.update()
                if ok:
                    count += 1
                    da = compat.vcol_get(me, "Day")
                    if da is not None:
                        compat.vcol_active(me, da)
                # флаги экспорта — гарантируем, что Day/Night уйдут в DFF
                try:
                    if not o.inu.day_cols:
                        o.inu.day_cols = True
                    if not o.inu.night_cols:
                        o.inu.night_cols = True
                except Exception:
                    pass
        finally:
            _restore_mode(prev_mode, prev_obj)

        d8 = tuple(int(round(c * 255)) for c in day)
        n8 = tuple(int(round(c * 255)) for c in night)
        _pub(self, {'INFO'},
                    T("Прилайт залит: {0} мешей. День={1} Ночь={2}").format(count, d8, n8))
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


# ── Multi-object prelight painting (merge proxy ↔ split-back) ─────────
# Native Vertex Paint only paints the active object. To paint prelight on
# many models at once we build a throw-away proxy = a COPY of every
# selected mesh, merged into one object overlaying the scene, and hide the
# originals. The user paints the proxy with the full native brush; «Split»
# copies the painted Day/Night colours back onto each original by loop
# range and deletes the proxy. Originals are never modified until split,
# so their names / origins / data come back byte-for-byte.

_PRELIGHT_MERGE_TAG = 'prelight_merge'


class GTATOOLS_OT_prelight_merge_paint(bpy.types.Operator):
    """Объединить выделенные меши во временную модель для покраски прилайта
    кистью сразу по всем. Оригиналы сохраняются (скрыты); «Разъединить»
    вернёт их как были — со своими именами и центрами."""
    bl_idname = "gtatools.prelight_merge_paint"
    bl_label = "INU: Merge for Prelight Paint"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import json
        import numpy as np
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        if len(sel) < 2:
            self.report({'ERROR'}, T("Выделите 2+ меша"))
            return {'CANCELLED'}
        if any(o.get(_PRELIGHT_MERGE_TAG) for o in context.scene.objects):
            self.report({'ERROR'},
                        T("Уже есть объединение — сначала «Разъединить»"))
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass

        # Direct numpy mesh build — NO bpy.ops.object.join (that re-evals
        # the growing proxy on every call → O(N²), minutes on a 1.5M-poly
        # map). Read each source via foreach_get, concatenate, foreach_set
        # once. Same fast path the DFF importer uses.
        metas = []
        tv = tl = tp = 0
        for o in sel:
            me = o.data
            nv, nl, npg = len(me.vertices), len(me.loops), len(me.polygons)
            metas.append((o, me, nv, nl, npg, tv, tl, tp))
            tv += nv
            tl += nl
            tp += npg
        if tv == 0 or tl == 0:
            self.report({'ERROR'}, T("Пустые меши"))
            return {'CANCELLED'}

        # Unique materials across all sources → proxy slots (so textures
        # show on the merged model). Keyed by name (materials are unique
        # by name).
        global_mats = []
        mat_to_idx = {}
        for o in sel:
            for ms in o.material_slots:
                m = ms.material
                if m is not None and m.name not in mat_to_idx:
                    mat_to_idx[m.name] = len(global_mats)
                    global_mats.append(m)

        co = np.empty(tv * 3, dtype=np.float32)
        lvi = np.empty(tl, dtype=np.int32)
        pls = np.empty(tp, dtype=np.int32)
        plt = np.empty(tp, dtype=np.int32)
        mat_idx = np.zeros(tp, dtype=np.int32)
        uv = np.zeros(tl * 2, dtype=np.float32)
        has_uv = False
        day = np.empty(tl * 4, dtype=np.float32)
        night = np.empty(tl * 4, dtype=np.float32)

        ranges = []
        for (o, me, nv, nl, npg, v0, l0, p0) in metas:
            c = np.empty(nv * 3, dtype=np.float32)
            me.vertices.foreach_get('co', c)
            c = c.reshape(-1, 3)
            M = np.array(o.matrix_world, dtype=np.float32)
            cw = c @ M[:3, :3].T + M[:3, 3]      # local → world
            co[v0 * 3:(v0 + nv) * 3] = cw.ravel()

            vi = np.empty(nl, dtype=np.int32)
            me.loops.foreach_get('vertex_index', vi)
            lvi[l0:l0 + nl] = vi + v0

            if npg:
                ls = np.empty(npg, dtype=np.int32)
                lt = np.empty(npg, dtype=np.int32)
                me.polygons.foreach_get('loop_start', ls)
                me.polygons.foreach_get('loop_total', lt)
                pls[p0:p0 + npg] = ls + l0
                plt[p0:p0 + npg] = lt
                # material_index → remap this object's slots onto the
                # global proxy slot list.
                slot_mats = [ms.material for ms in o.material_slots]
                if slot_mats:
                    mi = np.empty(npg, dtype=np.int32)
                    me.polygons.foreach_get('material_index', mi)
                    remap = np.array(
                        [mat_to_idx.get(m.name, 0) if m is not None else 0
                         for m in slot_mats], dtype=np.int32)
                    mi = np.clip(mi, 0, len(remap) - 1)
                    mat_idx[p0:p0 + npg] = remap[mi]

            # UV (active / first layer) — for texture display on the proxy.
            uvl = me.uv_layers.active or (me.uv_layers[0] if me.uv_layers else None)
            if uvl is not None and len(uvl.data) == nl:
                u = np.empty(nl * 2, dtype=np.float32)
                uvl.data.foreach_get('uv', u)
                uv[l0 * 2:(l0 + nl) * 2] = u
                has_uv = True

            for arr, nm in ((day, "Day"), (night, "Night")):
                a = compat.vcol_get(me, nm)
                if a is not None and len(a.data) == nl:
                    b = np.empty(nl * 4, dtype=np.float32)
                    a.data.foreach_get('color_srgb', b)
                    arr[l0 * 4:(l0 + nl) * 4] = b
                else:
                    arr[l0 * 4:(l0 + nl) * 4] = 1.0   # white where missing

            ranges.append({"name": o.name, "start": l0, "count": nl})

        pm = bpy.data.meshes.new("Prelight_Merge")
        pm.vertices.add(tv)
        pm.vertices.foreach_set('co', co)
        pm.loops.add(tl)
        pm.polygons.add(tp)
        pm.loops.foreach_set('vertex_index', lvi)
        pm.polygons.foreach_set('loop_start', pls)
        pm.polygons.foreach_set('loop_total', plt)
        # NOTE: no validate() — it could drop degenerate loops and break the
        # loop-range mapping. Sources are already valid, so concatenation is.
        pm.update(calc_edges=True)
        # Materials (shared, not copied) + per-poly index → textures show.
        for m in global_mats:
            pm.materials.append(m)
        if global_mats:
            pm.polygons.foreach_set('material_index', mat_idx)
        # UV layer for the texture mapping.
        if has_uv:
            pm.uv_layers.new(name="UVMap").data.foreach_set('uv', uv)
        da = compat.vcol_new(pm, "Day")
        da.data.foreach_set('color_srgb', day)
        na = compat.vcol_new(pm, "Night")
        na.data.foreach_set('color_srgb', night)
        compat.vcol_active(pm, da)
        pm.update()

        proxy = bpy.data.objects.new("Prelight_Merge", pm)
        proxy[_PRELIGHT_MERGE_TAG] = json.dumps(ranges)
        context.collection.objects.link(proxy)

        for o in sel:
            try:
                o.hide_set(True)
            except Exception:
                pass

        for x in list(context.selected_objects):
            x.select_set(False)
        proxy.select_set(True)
        context.view_layer.objects.active = proxy
        # Stay in OBJECT mode so the textured merged model is visible — the
        # user enters Vertex Paint themselves when ready (in VP the viewport
        # shows the colour attribute, not the texture).
        self.report({'INFO'},
                    f"{T('Объединено для покраски')}: {len(sel)} "
                    f"({T('войдите в Vertex Paint')})")
        return {'FINISHED'}


class GTATOOLS_OT_prelight_split_paint(bpy.types.Operator):
    """Разъединить: перенести покраску прилайта обратно на оригиналы (Day и
    Night), вернуть их видимыми со своими именами/центрами, удалить
    временную модель."""
    bl_idname = "gtatools.prelight_split_paint"
    bl_label = "INU: Split Prelight Paint"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import json
        import numpy as np
        ao = context.active_object
        proxy = ao if (ao is not None and ao.get(_PRELIGHT_MERGE_TAG)) else None
        if proxy is None:
            proxy = next((o for o in context.scene.objects
                          if o.get(_PRELIGHT_MERGE_TAG)), None)
        if proxy is None:
            self.report({'ERROR'}, T("Нет объединённой модели"))
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass

        try:
            ranges = json.loads(proxy[_PRELIGHT_MERGE_TAG])
        except Exception:
            ranges = []

        pm = proxy.data
        n_loops = len(pm.loops)
        for attr_name in ("Day", "Night"):
            pa = compat.vcol_get(pm, attr_name)
            if pa is None:
                continue
            buf = np.empty(n_loops * 4, dtype=np.float32)
            pa.data.foreach_get('color_srgb', buf)
            for r in ranges:
                orig = bpy.data.objects.get(r["name"])
                if orig is None or orig.type != 'MESH':
                    continue
                cnt = int(r["count"])
                if len(orig.data.loops) != cnt:
                    continue
                oa = compat.vcol_get(orig.data, attr_name)
                if oa is None:
                    oa = compat.vcol_new(orig.data, attr_name)
                s = int(r["start"]) * 4
                try:
                    oa.data.foreach_set('color_srgb', buf[s:s + cnt * 4])
                    orig.data.update()
                except Exception:
                    pass

        for x in list(context.selected_objects):
            x.select_set(False)
        for r in ranges:
            orig = bpy.data.objects.get(r["name"])
            if orig is not None:
                try:
                    orig.hide_set(False)
                    orig.select_set(True)
                except Exception:
                    pass
        if ranges:
            first = bpy.data.objects.get(ranges[0]["name"])
            if first is not None:
                context.view_layer.objects.active = first

        try:
            mesh = proxy.data
            bpy.data.objects.remove(proxy, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        except Exception:
            pass
        self.report({'INFO'}, f"{T('Разъединено')}: {len(ranges)}")
        return {'FINISHED'}


class GTATOOLS_OT_copy_color_attr(bpy.types.Operator):
    """Копировать vertex colors из одного атрибута в другой (Day ↔ Night)"""
    bl_idname = "gtatools.copy_color_attr"
    bl_label = "INU: Copy Color Attribute"
    bl_options = {'REGISTER', 'UNDO'}

    source: StringProperty(name="Source", default="Day")
    target: StringProperty(name="Target", default="Night")

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            obj = context.active_object
            if obj and obj.type == 'MESH':
                mesh_objects = [obj]
        if not mesh_objects:
            _pub(self, {'ERROR'}, T("Выберите меш объект!"))
            return {'CANCELLED'}

        copied = 0
        for obj in mesh_objects:
            mesh = obj.data
            src_attr = compat.vcol_get(mesh, self.source)
            if not src_attr:
                continue

            tgt_attr = compat.vcol_get(mesh, self.target)
            if not tgt_attr:
                tgt_attr = compat.vcol_new(mesh, self.target)

            # Copy all colors
            n = min(len(src_attr.data), len(tgt_attr.data))
            for i in range(n):
                c = src_attr.data[i].color
                tgt_attr.data[i].color = (c[0], c[1], c[2], c[3])
            copied += 1

        _pub(self, {'INFO'}, f"{self.source} → {self.target}: {copied} {T('объектов')}")
        return {'FINISHED'}


class GTATOOLS_OT_copy_vertex_alpha(bpy.types.Operator):
    """Перенести АЛЬФУ вершин с активного цветового атрибута (Day/Night)
    на второй, сохранив его RGB. Направление определяется тем, какой
    атрибут сейчас выбран радиокнопкой: активный Day → льёт альфу в Night,
    активный Night → в Day. Если атрибута-приёмника ещё нет — он создаётся
    полной копией активного (RGB+альфа), чтобы не остался мусорный цвет.
    Работает по всем выделенным мешам (у каждого свой активный атрибут)."""
    bl_idname = "gtatools.copy_vertex_alpha"
    bl_label = "INU: Copy Vertex Alpha to other layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            obj = context.active_object
            if obj and obj.type == 'MESH':
                mesh_objects = [obj]
        if not mesh_objects:
            _pub(self, {'ERROR'}, T("Выберите меш объект!"))
            return {'CANCELLED'}

        pairs = {"Day": "Night", "Night": "Day"}
        done = 0
        for obj in mesh_objects:
            mesh = obj.data
            active_attr = compat.vcol_active(mesh)
            if not active_attr or active_attr.name not in pairs:
                continue
            src_attr = compat.vcol_get(mesh, active_attr.name)
            if not src_attr:
                continue
            tgt_name = pairs[active_attr.name]
            tgt_attr = compat.vcol_get(mesh, tgt_name)
            if not tgt_attr:
                # Приёмника нет — создаём полной копией (RGB+альфа), иначе
                # его RGB был бы неинициализированным мусором.
                tgt_attr = compat.vcol_new(mesh, tgt_name)
                n = min(len(src_attr.data), len(tgt_attr.data))
                for i in range(n):
                    c = src_attr.data[i].color
                    tgt_attr.data[i].color = (c[0], c[1], c[2], c[3])
                done += 1
                continue
            # Приёмник есть — переносим ТОЛЬКО альфу, RGB приёмника сохраняем.
            n = min(len(src_attr.data), len(tgt_attr.data))
            for i in range(n):
                a = src_attr.data[i].color[3]
                t = tgt_attr.data[i].color
                tgt_attr.data[i].color = (t[0], t[1], t[2], a)
            done += 1

        if not done:
            _pub(self, {'WARNING'},
                 T("Активным должен быть атрибут Day или Night"))
            return {'CANCELLED'}
        _pub(self, {'INFO'}, f"{T('Альфа вершин перенесена')}: "
                             f"{done} {T('объектов')}")
        return {'FINISHED'}


class GTATOOLS_OT_clear_vertex_alpha(bpy.types.Operator):
    """Полностью убрать альфу вершин из АКТИВНОГО цветового атрибута:
    залить альфа-канал в 1.0 (непрозрачно), RGB сохранить. Так модель
    экспортируется без вертекс-альфы (полностью непрозрачной). Работает по
    всем выделенным мешам (у каждого — свой активный атрибут)."""
    bl_idname = "gtatools.clear_vertex_alpha"
    bl_label = "INU: Clear Vertex Alpha"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            obj = context.active_object
            if obj and obj.type == 'MESH':
                mesh_objects = [obj]
        if not mesh_objects:
            _pub(self, {'ERROR'}, T("Выберите меш объект!"))
            return {'CANCELLED'}

        done = 0
        for obj in mesh_objects:
            attr = compat.vcol_active(obj.data)
            if not attr:
                continue
            for i in range(len(attr.data)):
                c = attr.data[i].color
                attr.data[i].color = (c[0], c[1], c[2], 1.0)
            done += 1

        if not done:
            _pub(self, {'WARNING'}, T("Нет активного цветового атрибута"))
            return {'CANCELLED'}
        _pub(self, {'INFO'}, f"{T('Альфа вершин очищена')}: "
                             f"{done} {T('объектов')}")
        return {'FINISHED'}


class GTATOOLS_OT_prelight_preview(bpy.types.Operator):
    """Переключить превью prelight - показать vertex colors с текстурами"""
    bl_idname = "gtatools.prelight_preview"
    bl_label = "INU: Toggle Prelight Preview"
    # No 'UNDO': non-destructive viewport preview, and the undo snapshot
    # (whole-scene on big maps) was the main cost per click — same reason
    # as GTATOOLS_OT_alpha_preview below. Обратный ход — та же кнопка.
    bl_options = {'REGISTER'}

    enable: BoolProperty(
        name="Enable",
        description=T("Включить или выключить превью prelight"),
        default=True
    )

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            # Fallback to active object
            obj = context.active_object
            if obj and obj.type == 'MESH':
                mesh_objects = [obj]

        count = 0
        for obj in mesh_objects:
            success, message = setup_prelight_preview(obj, self.enable)
            if success:
                count += 1

        if count:
            state = "enabled" if self.enable else "disabled"
            _pub(self, {'INFO'}, f"Prelight preview {state} on {count} materials")
            return {'FINISHED'}

        # Single object error
        obj = context.active_object
        success, message = setup_prelight_preview(obj, self.enable)
        if success:
            _pub(self, {'INFO'}, message)
            return {'FINISHED'}
        else:
            _pub(self, {'ERROR'}, message)
            return {'CANCELLED'}


class GTATOOLS_OT_alpha_preview(bpy.types.Operator):
    """Показать прозрачность по альфе вершин во вьюпорте, независимо от
    превью prelight (RGB). Заводит альфа-канал активного слоя в Alpha
    материала и включает blended-режим отрисовки.

    ⚠ ПРИ ПЕРВОЙ ПОКРАСКЕ альфы на модели, у которой её ещё не было,
    мазок не появится сразу — переключи превью (выключи и включи), чтобы
    материал подцепил новый альфа-канал. Дальше рисование обновляется
    вживую без переключений."""
    bl_idname = "gtatools.alpha_preview"
    bl_label = "INU: Toggle Vertex Alpha Preview"
    # No 'UNDO': this is a non-destructive viewport-preview toggle, and the
    # undo snapshot (whole-scene on big maps) was the main cost per click.
    bl_options = {'REGISTER'}

    enable: BoolProperty(
        name="Enable",
        description=T("Включить или выключить превью альфы вершин"),
        default=True
    )

    def execute(self, context):
        # Scene-wide: find every mesh that actually HAS vertex alpha
        # (Day/Night layer with values < 255) and toggle the preview on
        # just those. Solid map geometry (alpha all 255) is never touched,
        # so it can't go transparent/black.
        targets = scene_vertex_alpha_objects(context)

        if self.enable:
            # Check first: drop AlphaView nodes from materials that no longer
            # have real vertex alpha (e.g. the user erased it since last time),
            # so re-enabling never leaves dead nodes behind.
            cleanup_orphan_alpha_nodes(context)
            if not targets:
                _pub(self, {'WARNING'},
                            T("В сцене нет моделей с вертекс-альфой"))
                return {'CANCELLED'}
            count = 0
            for obj, layer in targets:
                ok, _ = setup_alpha_preview(obj, True, color_name=layer)
                if ok:
                    count += 1
            context.scene['inu_alpha_preview_on'] = True
            _pub(self, {'INFO'},
                        f"{T('Альфа вершин: моделей')} {count}")
            return {'FINISHED'}

        # Disable: sweep ALL scene meshes (an object may have been wired
        # earlier and since changed), idempotent no-op where not wired.
        count = 0
        for obj in context.scene.objects:
            if obj.type != 'MESH' or obj.data is None:
                continue
            ok, _ = setup_alpha_preview(obj, False)
            if ok:
                count += 1
        context.scene['inu_alpha_preview_on'] = False
        _pub(self, {'INFO'}, f"{T('Альфа вершин выключена')}")
        return {'FINISHED'}


class GTATOOLS_OT_alpha_cleanup(bpy.types.Operator):
    """Проверить сцену и удалить ноды превью альфы (AlphaView_*) из всех
    материалов, которым они больше не нужны — где вертекс-альфа стёрта или
    меш стал полностью непрозрачным. Материалы, ещё используемые
    прозрачными мешами, не трогаются."""
    bl_idname = "gtatools.alpha_cleanup"
    bl_label = "INU: Cleanup Vertex Alpha Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        purged = cleanup_orphan_alpha_nodes(context)
        if purged:
            _pub(self, {'INFO'},
                 f"{T('Очищено материалов: ')}{purged}")
        else:
            _pub(self, {'INFO'},
                 T("Лишних нодов альфы не найдено"))
        return {'FINISHED'}


class GTATOOLS_OT_fix_itera_collection(bpy.types.Operator):
    """Исправить коллекцию освещения Itera Tools — сделать локальной и привязать к сцене"""
    bl_idname = "gtatools.fix_itera_collection"
    bl_label = "INU: Fix Itera Light Collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import bpy
        # Find all Itera collections (including .001, .002, etc.)
        itera_cols = [c for c in bpy.data.collections if c.name.startswith("Template Scene - Vertex Lights")]
        if not itera_cols:
            _pub(self, {'WARNING'}, T("Коллекция 'Template Scene - Vertex Lights' не найдена"))
            return {'CANCELLED'}

        fixed = 0
        for col in itera_cols:
            if col.library:
                try:
                    col.make_local()
                    for obj in col.objects:
                        obj.make_local()
                except Exception:
                    bpy.ops.object.make_local(type='ALL')
                    col = bpy.data.collections.get(col.name)
                    if col is None:
                        continue

            if col.name not in context.scene.collection.children:
                context.scene.collection.children.link(col)
                fixed += 1

        _pub(self, {'INFO'}, T("Коллекции Itera привязаны к сцене") + f": {fixed}")
        return {'FINISHED'}


def _find_itera_blend_path():
    """Find the Itera Tools 3 blend file from Blender asset libraries."""
    for lib in bpy.context.preferences.filepaths.asset_libraries:
        if "itera" in lib.name.lower() or "itera" in lib.path.lower():
            blend_path = os.path.join(lib.path, "Vertex Light 3.0.89.blend")
            if os.path.isfile(blend_path):
                return blend_path
            # Try to find any blend file with "Vertex Light" in name
            for f in os.listdir(lib.path):
                if f.startswith("Vertex Light") and f.endswith(".blend"):
                    return os.path.join(lib.path, f)
    return None


class GTATOOLS_OT_apply_itera_material(bpy.types.Operator):
    """Применить Itera материал из библиотеки к выделенным объектам"""
    bl_idname = "gtatools.apply_itera_material"
    bl_label = "INU: Apply Itera Material"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(
        name="Preset",
        items=[
            ('VERTEX_LIT_LINEAR', "Vertex Lit Linear UV",
             T("Линейное освещение вершин с UV текстурой")),
        ],
        default='VERTEX_LIT_LINEAR'
    )

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        blend_path = _find_itera_blend_path()
        if not blend_path:
            _pub(self, {'ERROR'}, T("Itera Tools 3 не найден в библиотеках ассетов"))
            return {'CANCELLED'}

        # Remember selection before append (append can change selection)
        saved_selected = [obj for obj in context.selected_objects]
        saved_active = context.active_object

        mat_names = {
            'VERTEX_LIT_LINEAR': "Vertex Lit Linear UV Texture",
        }
        target_name = mat_names[self.preset]

        # Check if already loaded
        itera_mat = bpy.data.materials.get(target_name)

        if itera_mat is None:
            # Append from blend file (more reliable than libraries.load for assets)
            try:
                bpy.ops.wm.append(
                    filepath=os.path.join(blend_path, "Material", target_name),
                    directory=os.path.join(blend_path, "Material") + os.sep,
                    filename=target_name,
                    link=False,
                    do_reuse_local_id=True,
                )
                itera_mat = bpy.data.materials.get(target_name)
            except Exception as e:
                _pub(self, {'ERROR'}, f"{T('Ошибка загрузки:')} {e}")
                return {'CANCELLED'}

            # Restore selection after append
            bpy.ops.object.select_all(action='DESELECT')
            for obj in saved_selected:
                obj.select_set(True)
            if saved_active:
                context.view_layer.objects.active = saved_active

        if itera_mat is None:
            _pub(self, {'ERROR'}, f"{T('Материал не найден:')} {target_name}")
            return {'CANCELLED'}

        # Apply to selected mesh objects
        applied = 0
        for obj in saved_selected:
            if obj.type != 'MESH':
                continue

            # Save original materials + face assignments before replacing
            import json
            if not obj.get("gtatools_saved_materials"):
                orig = {
                    "materials": [slot.material.name if slot.material else "" for slot in obj.material_slots],
                    "face_indices": [p.material_index for p in obj.data.polygons]
                }
                obj["gtatools_saved_materials"] = json.dumps(orig)

            # Clear existing slots and add Itera material
            obj.data.materials.clear()
            obj.data.materials.append(itera_mat)
            applied += 1

        _pub(self, {'INFO'}, f"Itera '{self.preset}': {applied} {T('объектов')}")
        return {'FINISHED'}


class GTATOOLS_OT_apply_itera_quickstart(bpy.types.Operator):
    """Применить Quickstart Vertex Lightable Surface — модификатор + коллекция со светом"""
    bl_idname = "gtatools.apply_itera_quickstart"
    bl_label = "INU: Apply Itera Quickstart"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        blend_path = _find_itera_blend_path()
        if not blend_path:
            _pub(self, {'ERROR'}, T("Itera Tools 3 не найден в библиотеках ассетов"))
            return {'CANCELLED'}

        ng_name = "Quickstart Vertex Lightable Surface"
        col_name = "Template Scene - Vertex Lights"

        # Remember selection before append (append can change selection)
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        # 1. Load node group if not already in blend
        node_group = bpy.data.node_groups.get(ng_name)
        if node_group is None:
            try:
                with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
                    if ng_name in data_from.node_groups:
                        data_to.node_groups = [ng_name]
                node_group = bpy.data.node_groups.get(ng_name)
            except Exception as e:
                _pub(self, {'ERROR'}, f"{T('Ошибка загрузки node group:')} {e}")
                return {'CANCELLED'}

        if node_group is None:
            _pub(self, {'ERROR'}, f"{T('Node group не найден:')} {ng_name}")
            return {'CANCELLED'}

        # 2. Load light collection if not already present
        light_col = None
        for c in bpy.data.collections:
            if c.name.startswith(col_name):
                light_col = c
                break

        if light_col is None:
            try:
                with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
                    if col_name in data_from.collections:
                        data_to.collections = [col_name]
                light_col = bpy.data.collections.get(col_name)
            except Exception:
                pass

        # 3. Link collection to scene if needed
        if light_col and light_col.name not in context.scene.collection.children:
            context.scene.collection.children.link(light_col)

        # 4. Add modifier only to MESH objects (not lights)
        applied = 0
        for obj in mesh_objects:
            # Check if modifier already exists
            has_mod = any(m.type == 'NODES' and m.node_group and
                         m.node_group.name == ng_name for m in obj.modifiers)
            if has_mod:
                continue

            mod = obj.modifiers.new(name=ng_name, type='NODES')
            mod.node_group = node_group

            # Set Light Collection input if available
            if light_col:
                for item in mod.node_group.interface.items_tree:
                    if hasattr(item, 'socket_type') and item.socket_type == 'NodeSocketCollection':
                        mod[item.identifier] = light_col
                        break

            applied += 1

        _pub(self, {'INFO'}, f"Quickstart: {applied} {T('объектов')}")
        return {'FINISHED'}


class GTATOOLS_OT_remove_itera_material(bpy.types.Operator):
    """Убрать Itera материал и восстановить оригинальные"""
    bl_idname = "gtatools.remove_itera_material"
    bl_label = "INU: Remove Itera Material"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        import json
        restored = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            # Remove Quickstart modifier
            quickstart_mods = [m for m in obj.modifiers
                               if m.type == 'NODES' and m.node_group
                               and "Quickstart" in m.node_group.name]
            for mod in quickstart_mods:
                obj.modifiers.remove(mod)

            # Restore saved materials + face assignments
            saved = obj.get("gtatools_saved_materials")
            if saved:
                data = json.loads(saved)
                names = data["materials"] if isinstance(data, dict) else data
                face_indices = data.get("face_indices", []) if isinstance(data, dict) else []

                obj.data.materials.clear()
                for name in names:
                    mat = bpy.data.materials.get(name)
                    obj.data.materials.append(mat)

                # Restore face material assignments
                if face_indices:
                    for i, idx in enumerate(face_indices):
                        if i < len(obj.data.polygons):
                            obj.data.polygons[i].material_index = idx

                del obj["gtatools_saved_materials"]
                restored += 1
            else:
                # No saved data — just clear Itera materials
                itera_names = {"Vertex Lit Linear UV Texture"}
                to_remove = []
                for i, slot in enumerate(obj.material_slots):
                    if slot.material and slot.material.name in itera_names:
                        to_remove.append(i)
                for i in reversed(to_remove):
                    obj.active_material_index = i
                    bpy.ops.object.material_slot_remove()

            if quickstart_mods:
                restored += 1

        _pub(self, {'INFO'}, f"{T('Восстановлено:')} {restored} {T('объектов')}")
        return {'FINISHED'}


class GTATOOLS_OT_eyedropper_color(bpy.types.Operator):
    """Кликните на полигон чтобы взять его цвет"""
    bl_idname = "gtatools.eyedropper_color"
    bl_label = "INU: Pick Color from Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            # Показываем курсор пипетки
            context.window.cursor_set('EYEDROPPER')

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # Делаем raycast под курсором
            result = self.pick_color_at_cursor(context, event)
            if result:
                context.window.cursor_set('DEFAULT')
                return {'FINISHED'}
            else:
                _pub(self, {'WARNING'}, "No mesh under cursor")
                return {'RUNNING_MODAL'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Отмена
            context.window.cursor_set('DEFAULT')
            _pub(self, {'INFO'}, "Color pick cancelled")
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            _pub(self, {'ERROR'}, "Use in 3D View!")
            return {'CANCELLED'}

        context.window.cursor_set('EYEDROPPER')
        context.window_manager.modal_handler_add(self)
        _pub(self, {'INFO'}, "Click on polygon to pick color (ESC to cancel)")
        return {'RUNNING_MODAL'}

    def pick_color_at_cursor(self, context, event):
        """Raycast и получение цвета полигона под курсором"""
        from bpy_extras import view3d_utils

        region = context.region
        rv3d = context.region_data

        # Координаты мыши в 3D
        coord = event.mouse_region_x, event.mouse_region_y
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

        # Raycast по всем объектам
        depsgraph = context.evaluated_depsgraph_get()
        result, location, normal, face_index, obj, matrix = context.scene.ray_cast(
            depsgraph, ray_origin, view_vector
        )

        if not result or obj is None or obj.type != 'MESH':
            return False

        mesh = obj.data
        if not compat.vcol_list(mesh):
            _pub(self, {'ERROR'}, "Object has no vertex colors!")
            return False

        color_attr = compat.vcol_active(mesh)
        if color_attr is None:
            _pub(self, {'ERROR'}, "No active color layer!")
            return False

        if face_index < 0 or face_index >= len(mesh.polygons):
            return False

        # Считываем цвета вершин этой грани
        colors = []
        poly = mesh.polygons[face_index]
        for loop_idx in poly.loop_indices:
            c = color_attr.data[loop_idx].color
            colors.append((c[0], c[1], c[2]))

        # Усредняем цвет
        if colors:
            avg_r = sum(c[0] for c in colors) / len(colors)
            avg_g = sum(c[1] for c in colors) / len(colors)
            avg_b = sum(c[2] for c in colors) / len(colors)

            context.scene.inu_settings.gtatools_fill_color = (avg_r, avg_g, avg_b)
            _pub(self, {'INFO'}, f"Color picked: RGB({int(avg_r*255)}, {int(avg_g*255)}, {int(avg_b*255)})")
            return True

        return False


class GTATOOLS_OT_fill_faces(bpy.types.Operator):
    """Залить выделенные грани цветом"""
    bl_idname = "gtatools.fill_faces"
    bl_label = "INU: Fill Selected Faces"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        scene = context.scene
        color = scene.inu_settings.gtatools_fill_color

        success, message = fill_selected_faces_with_backup(obj, color)

        if success:
            _pub(self, {'INFO'}, message)
            return {'FINISHED'}
        else:
            _pub(self, {'ERROR'}, message)
            return {'CANCELLED'}


class GTATOOLS_OT_restore_fill(bpy.types.Operator):
    """Восстановить цвета, изменённые заливкой"""
    bl_idname = "gtatools.restore_fill"
    bl_label = "INU: Restore Fill"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object

        success, message = restore_filled_faces(obj)

        if success:
            _pub(self, {'INFO'}, message)
            return {'FINISHED'}
        else:
            _pub(self, {'ERROR'}, message)
            return {'CANCELLED'}


class GTATOOLS_OT_remove_fill_color(bpy.types.Operator):
    """Удалить цвет из списка и восстановить оригинальные цвета"""
    bl_idname = "gtatools.remove_fill_color"
    bl_label = "INU: Remove Fill Color"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            _pub(self, {'ERROR'}, T("Выберите меш!"))
            return {'CANCELLED'}

        # Switch to Object Mode for data writing
        original_mode = obj.mode
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        success, message = remove_fill_color_by_index(obj, self.index)

        # Возвращаемся в исходный режим
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        if success:
            _pub(self, {'INFO'}, message)
            return {'FINISHED'}
        else:
            _pub(self, {'ERROR'}, message)
            return {'CANCELLED'}


class GTATOOLS_OT_select_fill_color(bpy.types.Operator):
    """Выделить полигоны с этим цветом"""
    bl_idname = "gtatools.select_fill_color"
    bl_label = "INU: Select Faces by Color"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            _pub(self, {'ERROR'}, T("Выберите меш!"))
            return {'CANCELLED'}

        if not (0 <= self.index < len(obj.gtatools_fill_colors)):
            return {'CANCELLED'}

        target_color = obj.gtatools_fill_colors[self.index].color
        tolerance = 0.01

        # Switch to Object Mode for data reading
        original_mode = obj.mode
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        mesh = obj.data
        if not compat.vcol_active(mesh):
            _pub(self, {'ERROR'}, T("Нет vertex colors!"))
            if original_mode == 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            return {'CANCELLED'}

        color_attr = compat.vcol_active(mesh)

        # Find polygons with this color
        selected_count = 0
        for poly in mesh.polygons:
            has_color = False
            for loop_idx in poly.loop_indices:
                c = color_attr.data[loop_idx].color
                if (abs(c[0] - target_color[0]) < tolerance and
                    abs(c[1] - target_color[1]) < tolerance and
                    abs(c[2] - target_color[2]) < tolerance):
                    has_color = True
                    break

            if has_color:
                poly.select = True
                selected_count += 1
            else:
                poly.select = False

        # Switch to Edit Mode to show selection
        bpy.ops.object.mode_set(mode='EDIT')

        _pub(self, {'INFO'}, f"{T('Выделено')} {selected_count} {T('полигонов')}")
        return {'FINISHED'}


class GTATOOLS_OT_delete_fill_color_level(bpy.types.Operator):
    """Удалить scatter уровень (пересчитать цвета)"""
    bl_idname = "gtatools.delete_fill_color_level"
    bl_label = "INU: Delete Scatter Level"
    bl_options = {'REGISTER', 'UNDO'}

    color_index: bpy.props.IntProperty()
    level: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            _pub(self, {'ERROR'}, T("Выберите меш!"))
            return {'CANCELLED'}

        if not (0 <= self.color_index < len(obj.gtatools_fill_colors)):
            return {'CANCELLED'}

        color = obj.gtatools_fill_colors[self.color_index].color

        # Switch to Object Mode
        original_mode = obj.mode
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        success, message = remove_scatter_layer(obj, color, self.level)

        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        if success:
            _pub(self, {'INFO'}, message)
            return {'FINISHED'}
        else:
            _pub(self, {'ERROR'}, message)
            return {'CANCELLED'}


class GTATOOLS_OT_clear_fill_color_levels(bpy.types.Operator):
    """Очистить все scatter уровни цвета"""
    bl_idname = "gtatools.clear_fill_color_levels"
    bl_label = "INU: Clear Scatter Levels"
    bl_options = {'REGISTER', 'UNDO'}

    color_index: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            _pub(self, {'ERROR'}, T("Выберите меш!"))
            return {'CANCELLED'}

        if not (0 <= self.color_index < len(obj.gtatools_fill_colors)):
            return {'CANCELLED'}

        color = obj.gtatools_fill_colors[self.color_index].color

        # Switch to Object Mode
        original_mode = obj.mode
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        success, message = clear_scatter_layers(obj, color)

        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        if success:
            _pub(self, {'INFO'}, message)
            return {'FINISHED'}
        else:
            _pub(self, {'ERROR'}, message)
            return {'CANCELLED'}


class GTATOOLS_OT_scatter_color(bpy.types.Operator):
    """Рассеять выбранный цвет вокруг выделенных полигонов с убыванием по расстоянию"""
    bl_idname = "gtatools.scatter_color"
    bl_label = "INU: Scatter Color"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        scene = context.scene
        if not obj or obj.type != 'MESH':
            _pub(self, {'ERROR'}, T("Выберите меш!"))
            return {'CANCELLED'}

        # Pull color from active Vertex Paint brush. Fallback на scene
        # prop если режим не Vertex Paint (например, юзер запустил
        # оператор из Edit mode).
        color = None
        try:
            ts = context.tool_settings
            vp = getattr(ts, 'vertex_paint', None)
            if vp and getattr(vp, 'brush', None) is not None:
                c = vp.brush.color
                color = (c[0], c[1], c[2])
        except (AttributeError, RuntimeError):
            pass
        if color is None:
            color = tuple(scene.inu_settings.gtatools_scatter_color_color)

        strength = float(scene.inu_settings.gtatools_scatter_color_strength)
        distance = float(scene.inu_settings.gtatools_scatter_color_distance)
        success, message = scatter_color_from_selected(
            obj, (color[0], color[1], color[2], 1.0),
            strength=strength, distance=distance)
        if success:
            _pub(self, {'INFO'}, message)
            return {'FINISHED'}
        _pub(self, {'ERROR'}, message)
        return {'CANCELLED'}


class GTATOOLS_OT_scatter_light(bpy.types.Operator):
    """Рассеять свет от выделенных граней к соседним"""
    bl_idname = "gtatools.scatter_light"
    bl_label = "INU: Scatter Light"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        scene = context.scene

        if not obj or obj.type != 'MESH':
            _pub(self, {'ERROR'}, T("Выберите меш!"))
            return {'CANCELLED'}

        # Switch to Object Mode for data reading
        original_mode = obj.mode
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Определяем цвет выделенных полигонов
        selected_color = get_selected_faces_color(obj)

        # Сохраняем цвета ДО scatter для вычисления дельты
        pre_scatter_colors = {}
        mesh = obj.data
        if compat.vcol_active(mesh):
            color_attr = compat.vcol_active(mesh)
            for loop_idx in range(len(color_attr.data)):
                c = color_attr.data[loop_idx].color
                pre_scatter_colors[loop_idx] = (c[0], c[1], c[2], c[3])

        intensity = scene.inu_settings.gtatools_scatter_intensity
        falloff = scene.inu_settings.gtatools_scatter_falloff
        iterations = scene.inu_settings.gtatools_scatter_iterations
        radius = scene.inu_settings.gtatools_scatter_radius

        success, message, affected_loops = scatter_light_from_selected(obj, intensity, falloff, iterations, radius)

        level_info = ""

        # Вычисляем дельты ДО переключения режима (пока данные mesh актуальны)
        if success and selected_color and affected_loops:
            deltas = {}
            color_attr = compat.vcol_active(mesh)
            for loop_idx in affected_loops:
                if loop_idx in pre_scatter_colors and loop_idx < len(color_attr.data):
                    old = pre_scatter_colors[loop_idx]
                    new = color_attr.data[loop_idx].color
                    delta = (new[0] - old[0], new[1] - old[1], new[2] - old[2], 0.0)
                    # Сохраняем только если дельта не нулевая
                    if abs(delta[0]) > 0.001 or abs(delta[1]) > 0.001 or abs(delta[2]) > 0.001:
                        deltas[loop_idx] = delta

            # Сохраняем дельты как scatter слой
            if deltas:
                scatter_level = add_scatter_layer(obj, selected_color, deltas)
                if scatter_level > 0:
                    level_info = f" | Level {scatter_level}"

        # Возвращаемся в исходный режим
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        if success:
            _pub(self, {'INFO'}, f"{message}{level_info}")
            return {'FINISHED'}
        else:
            _pub(self, {'ERROR'}, message)
            return {'CANCELLED'}


class GTATOOLS_OT_toggle_face_select(bpy.types.Operator):
    """Переключить режим выделения граней в Vertex Paint"""
    bl_idname = "gtatools.toggle_face_select"
    bl_label = "INU: Toggle Face Selection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            _pub(self, {'ERROR'}, "Select a mesh object!")
            return {'CANCELLED'}

        # Toggle face selection masking in paint mode
        obj.data.use_paint_mask = not obj.data.use_paint_mask

        if obj.data.use_paint_mask:
            _pub(self, {'INFO'}, "Face selection ON - Click faces to select")
        else:
            _pub(self, {'INFO'}, "Face selection OFF")

        return {'FINISHED'}


class GTATOOLS_OT_switch_to_edit(bpy.types.Operator):
    """Переключить в Edit Mode для выделения граней"""
    bl_idname = "gtatools.switch_to_edit"
    bl_label = "INU: Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.active_object:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='FACE')
        return {'FINISHED'}


class GTATOOLS_OT_switch_to_vpaint(bpy.types.Operator):
    """Переключить в Vertex Paint Mode"""
    bl_idname = "gtatools.switch_to_vpaint"
    bl_label = "INU: Vertex Paint Mode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.active_object:
            bpy.ops.object.mode_set(mode='VERTEX_PAINT')
        return {'FINISHED'}


class GTATOOLS_OT_select_color_attribute(bpy.types.Operator):
    """Выбрать color attribute и обновить превью prelight"""
    bl_idname = "gtatools.select_color_attribute"
    bl_label = "INU: Select Color Attribute"
    bl_options = {'REGISTER', 'UNDO'}

    attribute_name: StringProperty(name="Attribute Name")

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            obj = context.active_object
            if obj and obj.type == 'MESH':
                mesh_objects = [obj]

        if not mesh_objects:
            _pub(self, {'ERROR'}, "Select mesh object(s)!")
            return {'CANCELLED'}

        switched = 0
        for obj in mesh_objects:
            mesh = obj.data
            color_attr = compat.vcol_get(mesh, self.attribute_name)
            if color_attr is not None:
                compat.vcol_active(mesh, color_attr)
                self.update_prelight_preview(obj, self.attribute_name)
                switched += 1

        _pub(self, {'INFO'}, f"Active: {self.attribute_name} ({switched} objects)")
        return {'FINISHED'}

    def update_prelight_preview(self, obj, color_name):
        """Перенаправить ноды превью на новый активный слой (Day/Night).

        Обновляем И RGB-ноду прилайта (Prelight_VertexColor), И ноду превью
        АЛЬФЫ (AlphaView_VC) — иначе альфа-превью продолжает читать старый
        слой, и при переключении День/Ночь альфа визуально не разделяется."""
        def _set_layer(node):
            if not node:
                return
            if hasattr(node, 'attribute_name'):
                node.attribute_name = color_name
            elif hasattr(node, 'layer_name'):
                node.layer_name = color_name

        for mat_slot in obj.material_slots:
            mat = mat_slot.material
            if not mat or not mat.use_nodes:
                continue
            nodes = mat.node_tree.nodes
            _set_layer(nodes.get("Prelight_VertexColor"))
            _set_layer(nodes.get("AlphaView_VC"))


class GTATOOLS_OT_create_color_attr(bpy.types.Operator):
    """Создать color attribute"""
    bl_idname = "gtatools.create_color_attr"
    bl_label = "INU: Create Color Attribute"
    bl_options = {'REGISTER', 'UNDO'}

    attr_name: StringProperty(default="Day")

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            _pub(self, {'ERROR'}, "Select a mesh object!")
            return {'CANCELLED'}

        mesh = obj.data

        if compat.vcol_get(mesh, self.attr_name) is not None:
            _pub(self, {'INFO'}, f"{self.attr_name} already exists")
            return {'CANCELLED'}

        # Create attribute
        attr = compat.vcol_new(mesh, self.attr_name)
        # Fill with white
        for i in range(len(attr.data)):
            attr.data[i].color = (1.0, 1.0, 1.0, 1.0)

        # Set as active
        compat.vcol_active(mesh, attr)

        _pub(self, {'INFO'}, f"Created: {self.attr_name}")
        return {'FINISHED'}


class GTATOOLS_OT_remove_color_attr(bpy.types.Operator):
    """Удалить color attribute по имени на всех выделенных объектах"""
    bl_idname = "gtatools.remove_color_attr"
    bl_label = "INU: Remove Color Attribute"
    bl_options = {'REGISTER', 'UNDO'}

    attr_name: StringProperty(default="")

    def execute(self, context):
        mesh_objects = [o for o in context.selected_objects if o.type == 'MESH']
        if not mesh_objects:
            obj = context.active_object
            if obj and obj.type == 'MESH':
                mesh_objects = [obj]

        if not mesh_objects:
            _pub(self, {'ERROR'}, "Select mesh object(s)!")
            return {'CANCELLED'}

        removed = 0
        for obj in mesh_objects:
            mesh = obj.data
            attr = compat.vcol_get(mesh, self.attr_name)
            if attr is not None:
                compat.vcol_remove(mesh, attr)
                removed += 1

        if removed:
            _pub(self, {'INFO'}, f"Removed '{self.attr_name}' from {removed} objects")
        else:
            _pub(self, {'ERROR'}, f"{self.attr_name} not found")
            return {'CANCELLED'}
        return {'FINISHED'}


