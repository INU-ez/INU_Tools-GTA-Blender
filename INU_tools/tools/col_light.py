# INU_tools.tools.col_light — COL Light preview and baking

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader

from .. import T
from . import compat


# =============================================================================
# COL LIGHT PREVIEW — green overlay + numbers on polygons
# =============================================================================

_col_light_preview_handlers = []
_col_light_preview_active = False
_col_light_preview_cache = {'key': None, 'faces': []}
_col_light_transform_watch = {'prev_mat': None, 'cur_mat': None}


def _col_light_watch_transform():
    """Timer: detect when object stops moving and invalidate cache."""
    if not _col_light_preview_active:
        return None  # Stop timer
    obj = bpy.context.active_object
    if not obj or obj.type != 'MESH':
        return 0.3
    watch = _col_light_transform_watch
    mat = tuple(obj.matrix_world[i][j] for i in range(4) for j in range(4))
    if watch['cur_mat'] != mat:
        # Object is still moving — just record current matrix
        watch['cur_mat'] = mat
    elif watch['prev_mat'] != mat:
        # Matrix stabilized (same as last check) — object stopped moving
        watch['prev_mat'] = mat
        _col_light_preview_cache['key'] = None
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
    return 0.2  # Check every 0.2 sec


def _col_light_invalidate_preview(self, context):
    """Invalidate preview cache when settings change."""
    _col_light_preview_cache['key'] = None
    if _col_light_preview_active:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


# ── Яркость грани → уровень COL-света: ОДНА формула для превью и запекания
# (раньше «Порог» был только в превью — запечённое расходилось с цифрами).

def _col_gamma(edge):
    """Гамма из «Края»: ≥ 0 — расширить светлое (гамма < 1), < 0 — сжать."""
    if edge >= 0:
        return 1.0 / (1.0 + edge * 4.0)
    return 1.0 + abs(edge) * 4.0


def _col_threshold(slider):
    """Слайдер «Порог» 0..100 → доля яркости (100 − s) / 10000; 100 = без порога."""
    s = int(slider)
    return (100 - s) / 10000.0 if s < 100 else 0.0


def _col_level(avg, vmin, vmax, gamma=1.0, contrast=0.0, threshold=0.0):
    """Средняя яркость грани 0..1 → уровень света COL 0..15:
    гамма «Края», S-контраст, порог (ниже — 0, выше — растяжка в Min..Max)."""
    avg = min(1.0, max(0.0, avg))
    if avg > 0.0 and gamma != 1.0:
        avg = avg ** gamma
    if contrast > 0.0:
        k = 1.0 + contrast * 10.0
        if avg < 0.5:
            avg = 0.5 * (2.0 * avg) ** k
        else:
            avg = 1.0 - 0.5 * (2.0 * (1.0 - avg)) ** k
    if threshold > 0.0 and avg < threshold:
        return 0
    if 0.0 < threshold < 1.0:
        avg = (avg - threshold) / (1.0 - threshold)
    return min(15, max(0, round(vmin + avg * (vmax - vmin))))


def _poly_avg(mesh, brightness, domain='CORNER'):
    """Calculate per-polygon average brightness.

    ``brightness`` is indexed by loop for CORNER-domain attributes and
    by vertex for POINT-domain attributes, so resolve the right index
    per loop depending on ``domain``.
    """
    per_vertex = (domain == 'POINT')
    loops = mesh.loops
    result = {}
    for poly in mesh.polygons:
        avg = 0.0
        for loop_idx in poly.loop_indices:
            idx = loops[loop_idx].vertex_index if per_vertex else loop_idx
            avg += brightness[idx]
        avg /= len(poly.loop_indices)
        result[poly.index] = avg
    return result


def _col_light_get_preview_data(context):
    """Compute or return cached per-polygon night light values."""
    obj = context.active_object
    if not obj or obj.type != 'MESH' or not compat.vcol_list(obj.data):
        return []

    scene = context.scene
    mesh = obj.data

    # Use active color attribute to determine Day or Night range
    active_attr = compat.vcol_active(mesh)
    if active_attr is None:
        return []

    if active_attr.name == "Night":
        val_min = scene.inu_settings.gtatools_col_night_min
        val_max = scene.inu_settings.gtatools_col_night_max
    else:
        val_min = scene.inu_settings.gtatools_col_day_min
        val_max = scene.inu_settings.gtatools_col_day_max

    edge = getattr(scene.inu_settings, 'gtatools_col_light_edge', 0.0)
    contrast = getattr(scene.inu_settings, 'gtatools_col_light_contrast', 0.0)
    # Threshold slider: 0=max cutoff, 100=no cutoff. Real threshold = (100 - slider) / 10000
    threshold = _col_threshold(
        getattr(scene.inu_settings, 'gtatools_col_light_threshold', 0))

    cache = _col_light_preview_cache
    key = (id(obj), obj.name, active_attr.name, val_min, val_max, edge, contrast, threshold, len(obj.data.polygons))
    if cache['key'] == key:
        return cache['faces']

    color_attr = active_attr

    # Gamma from edge: positive = expand (gamma<1), negative = contract (gamma>1)
    gamma = _col_gamma(edge)

    # Brightness per element: per loop (CORNER) or per vertex (POINT)
    loop_brightness = []
    for i in range(len(color_attr.data)):
        c = color_attr.data[i].color
        loop_brightness.append(max(c[0], c[1], c[2]))

    mat_w = obj.matrix_world

    # First pass: compute light value per polygon — same formula as the bake.
    # Домен слоя учитывается: у POINT-слоя data по вершинам, не по углам
    # (индекс угла давал IndexError в draw-хендлере → пустое превью).
    avgs = _poly_avg(mesh, loop_brightness, compat.vcol_domain(color_attr))
    poly_vals = {}
    for poly in mesh.polygons:
        poly_vals[poly.index] = _col_level(avgs[poly.index], val_min, val_max,
                                           gamma, contrast, threshold)

    # Build adjacency: vertex → polygons
    vert_to_polys = {}
    for poly in mesh.polygons:
        for vi in poly.vertices:
            vert_to_polys.setdefault(vi, []).append(poly.index)

    # Show text only on border polygons (where value differs from a neighbor)
    show_text = {}
    for poly in mesh.polygons:
        val = poly_vals[poly.index]
        is_border = False
        for vi in poly.vertices:
            for pi in vert_to_polys.get(vi, []):
                if pi != poly.index and poly_vals.get(pi, val) != val:
                    is_border = True
                    break
            if is_border:
                break
        show_text[poly.index] = is_border

    # Build face data
    faces = []
    for poly in mesh.polygons:
        night_val = poly_vals[poly.index]
        center = mat_w @ poly.center
        normal_offset = poly.normal * 0.02
        verts = [mat_w @ (mesh.vertices[vi].co + normal_offset) for vi in poly.vertices]

        tris = []
        for i in range(1, len(verts) - 1):
            tris.append(((verts[0].x, verts[0].y, verts[0].z),
                         (verts[i].x, verts[i].y, verts[i].z),
                         (verts[i+1].x, verts[i+1].y, verts[i+1].z)))

        faces.append((night_val, (center.x, center.y, center.z), tris, show_text[poly.index]))

    cache['key'] = key
    cache['faces'] = faces
    return faces


def _draw_col_light_faces():
    """Draw green transparent overlay on COL polygons."""
    if not _col_light_preview_active:
        return

    context = bpy.context
    faces = _col_light_get_preview_data(context)
    if not faces:
        return


    positions = []
    colors = []

    for night_val, center, tris, _show in faces:
        intensity = night_val / 15.0
        color = (0.0, intensity * 0.9, 0.0, 0.4)

        for v0, v1, v2 in tris:
            positions.extend([v0, v1, v2])
            colors.extend([color, color, color])

    if not positions:
        return

    shader = gpu.shader.from_builtin('SMOOTH_COLOR')
    batch = batch_for_shader(shader, 'TRIS', {"pos": positions, "color": colors})

    gpu.state.blend_set('ALPHA')
    shader.bind()
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def _draw_col_light_text():
    """Draw night light numbers at polygon centers."""
    if not _col_light_preview_active:
        return

    context = bpy.context
    if not getattr(context.scene.inu_settings, 'gtatools_col_light_show_numbers', True):
        return

    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from mathutils import Vector

    region = context.region
    rv3d = context.region_data

    if not region or not rv3d:
        return

    faces = _col_light_get_preview_data(context)
    if not faces:
        return

    font_id = 0
    font_size = getattr(context.scene.inu_settings, 'gtatools_col_light_font_size', 13)
    blf.size(font_id, font_size)

    for night_val, center, tris, show in faces:
        if not show:
            continue

        coord_2d = location_3d_to_region_2d(region, rv3d, Vector(center))
        if coord_2d is None:
            continue

        text = str(night_val)
        # Shadow
        blf.color(font_id, 0.0, 0.0, 0.0, 0.9)
        blf.position(font_id, coord_2d.x + 1, coord_2d.y - 1, 0)
        blf.draw(font_id, text)
        # Main text
        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
        blf.position(font_id, coord_2d.x, coord_2d.y, 0)
        blf.draw(font_id, text)


class GTATOOLS_OT_preview_col_light(bpy.types.Operator):
    """Превью COL Night Light — зелёная визуализация и числа на полигонах"""
    bl_idname = "gtatools.preview_col_light"
    bl_label = "INU: Preview COL Light"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and bool(compat.vcol_list(obj.data))

    def execute(self, context):
        global _col_light_preview_active, _col_light_preview_handlers

        _col_light_preview_active = not _col_light_preview_active
        _col_light_preview_cache['key'] = None

        if _col_light_preview_active:
            if not _col_light_preview_handlers:
                h1 = bpy.types.SpaceView3D.draw_handler_add(
                    _draw_col_light_faces, (), 'WINDOW', 'POST_VIEW')
                h2 = bpy.types.SpaceView3D.draw_handler_add(
                    _draw_col_light_text, (), 'WINDOW', 'POST_PIXEL')
                _col_light_preview_handlers.extend([h1, h2])
            # Start transform watcher
            obj = context.active_object
            if obj:
                mat = tuple(obj.matrix_world[i][j] for i in range(4) for j in range(4))
                _col_light_transform_watch['prev_mat'] = mat
                _col_light_transform_watch['cur_mat'] = mat
            if not bpy.app.timers.is_registered(_col_light_watch_transform):
                bpy.app.timers.register(_col_light_watch_transform, first_interval=0.2)
            self.report({'INFO'}, T("Превью COL Light включено"))
        else:
            for h in _col_light_preview_handlers:
                bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
            _col_light_preview_handlers.clear()
            self.report({'INFO'}, T("Превью COL Light выключено"))

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}


class GTATOOLS_OT_bake_col_light(bpy.types.Operator):
    """Конвертировать vertex colors в COL Day/Night Light (разбиение материалов по яркости)"""
    bl_idname = "gtatools.bake_col_light"
    bl_label = "INU: Bake COL Light"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and bool(compat.vcol_list(obj.data))

    def _read_brightness(self, color_attr):
        """Read per-loop brightness from a color attribute."""
        result = []
        for i in range(len(color_attr.data)):
            c = color_attr.data[i].color
            result.append(max(c[0], c[1], c[2]))
        return result

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        scene = context.scene

        day_min = scene.inu_settings.gtatools_col_day_min
        day_max = scene.inu_settings.gtatools_col_day_max
        night_min = scene.inu_settings.gtatools_col_night_min
        night_max = scene.inu_settings.gtatools_col_night_max

        # Edge/contrast/threshold settings — те же, что у превью
        edge = getattr(scene.inu_settings, 'gtatools_col_light_edge', 0.0)
        contrast = getattr(scene.inu_settings, 'gtatools_col_light_contrast', 0.0)
        gamma = _col_gamma(edge)
        threshold = _col_threshold(
            getattr(scene.inu_settings, 'gtatools_col_light_threshold', 0))

        # Day source: "Day" layer or active
        day_attr = compat.vcol_get(mesh, "Day") or compat.vcol_active(mesh)
        if day_attr is None:
            self.report({'ERROR'}, "No vertex color layer found")
            return {'CANCELLED'}

        # Night source: "Night" layer (optional, falls back to Day)
        night_attr = compat.vcol_get(mesh, "Night") or day_attr

        day_brightness = self._read_brightness(day_attr)
        night_brightness = self._read_brightness(night_attr)

        day_avg = _poly_avg(mesh, day_brightness, compat.vcol_domain(day_attr))
        night_avg = _poly_avg(mesh, night_brightness, compat.vcol_domain(night_attr))

        # Calculate per-polygon levels
        poly_levels = {}
        for poly in mesh.polygons:
            d = _col_level(day_avg[poly.index], day_min, day_max,
                           gamma, contrast, threshold)
            n = _col_level(night_avg[poly.index], night_min, night_max,
                           gamma, contrast, threshold)
            poly_levels[poly.index] = (d, n)

        # Group polygons by (material_index, day_level, night_level)
        groups = {}
        for poly in mesh.polygons:
            key = (poly.material_index, poly_levels[poly.index][0], poly_levels[poly.index][1])
            if key not in groups:
                groups[key] = []
            groups[key].append(poly.index)

        # Find which materials need splitting
        mat_levels = {}
        for (mat_idx, d, n), poly_indices in groups.items():
            if mat_idx not in mat_levels:
                mat_levels[mat_idx] = {}
            mat_levels[mat_idx][(d, n)] = poly_indices

        new_mat_map = {}
        created_names = []

        for mat_idx, levels in mat_levels.items():
            if mat_idx >= len(obj.material_slots):
                continue

            orig_mat = obj.material_slots[mat_idx].material
            if orig_mat is None:
                continue

            if len(levels) == 1:
                d, n = list(levels.keys())[0]
                orig_mat.inu.col_day_light = d
                orig_mat.inu.col_night_light = n
            else:
                sorted_levels = sorted(levels.keys(), key=lambda x: x[0], reverse=True)
                highest = sorted_levels[0]

                orig_mat.inu.col_day_light = highest[0]
                orig_mat.inu.col_night_light = highest[1]

                new_mat_map[(mat_idx, highest)] = mat_idx

                for (d, n) in sorted_levels[1:]:
                    copy_mat = orig_mat.copy()
                    copy_mat.name = f"{orig_mat.name}_d{d}_n{n}"
                    created_names.append(copy_mat.name)

                    copy_mat.inu.col_mat_index = orig_mat.inu.col_mat_index
                    copy_mat.inu.col_flags = orig_mat.inu.col_flags
                    copy_mat.inu.col_brightness = orig_mat.inu.col_brightness
                    copy_mat.inu.col_day_light = d
                    copy_mat.inu.col_night_light = n

                    obj.data.materials.append(copy_mat)
                    new_slot_idx = len(obj.material_slots) - 1
                    new_mat_map[(mat_idx, (d, n))] = new_slot_idx

        # Reassign polygons to new materials
        for (mat_idx, level_key), new_slot_idx in new_mat_map.items():
            for poly_idx in mat_levels[mat_idx][level_key]:
                mesh.polygons[poly_idx].material_index = new_slot_idx

        # Store created material names on object for cleanup
        import json
        existing = json.loads(obj.get("gtatools_col_light_mats", "[]"))
        existing.extend(created_names)
        obj["gtatools_col_light_mats"] = json.dumps(existing)

        total_new = len(created_names)
        self.report({'INFO'}, f"COL Light baked: {total_new} new materials, {len(mesh.polygons)} polygons")
        return {'FINISHED'}


class GTATOOLS_OT_clear_col_light_mats(bpy.types.Operator):
    """Удалить COL light материалы, созданные Bake COL Light"""
    bl_idname = "gtatools.clear_col_light_mats"
    bl_label = "INU: Clear COL Light"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH'

    def execute(self, context):
        import json
        import re

        obj = context.active_object
        mesh = obj.data

        # Get stored list of created materials
        stored_names = set(json.loads(obj.get("gtatools_col_light_mats", "[]")))

        # Also detect by pattern _dN_nN as fallback
        pattern = re.compile(r'^(.+)_d(\d{1,2})_n(\d{1,2})$')

        merge_map = {}  # slot_idx -> original_slot_idx

        for i, slot in enumerate(obj.material_slots):
            if slot.material is None:
                continue

            is_col_light = slot.material.name in stored_names

            if not is_col_light:
                m = pattern.match(slot.material.name)
                if m and int(m.group(2)) <= 15 and int(m.group(3)) <= 15:
                    is_col_light = True

            if is_col_light:
                m = pattern.match(slot.material.name)
                if m:
                    orig_name = m.group(1)
                    for j, orig_slot in enumerate(obj.material_slots):
                        if orig_slot.material and orig_slot.material.name == orig_name:
                            merge_map[i] = j
                            break

        if not merge_map:
            self.report({'INFO'}, "No COL light materials to clear")
            return {'FINISHED'}

        # Reassign polygons back to original materials
        for poly in mesh.polygons:
            if poly.material_index in merge_map:
                poly.material_index = merge_map[poly.material_index]

        # Remove unused material slots (from end to start)
        removed = 0
        for slot_idx in sorted(merge_map.keys(), reverse=True):
            mat = obj.material_slots[slot_idx].material
            obj.active_material_index = slot_idx
            bpy.ops.object.material_slot_remove()
            if mat and mat.users == 0:
                bpy.data.materials.remove(mat)
            removed += 1

        # Clear stored list
        if "gtatools_col_light_mats" in obj:
            del obj["gtatools_col_light_mats"]

        self.report({'INFO'}, f"Cleared {removed} COL light materials")
        return {'FINISHED'}
