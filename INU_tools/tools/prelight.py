# INU_tools.tools.prelight — Vertex colors, baking, fill, scatter light

import bpy
import bmesh
import math
import numpy as np
from mathutils import Vector

from . import compat


# =============================================================================
# PRELIGHT
# =============================================================================

class GTASAPrelight:
    def __init__(self, obj, split_angle=90.0, normal_threshold=0.1,
                 top_color=(0.8235, 0.7608, 0.7137), bottom_color=(0.3, 0.3, 0.3),
                 ambient_color=(0.5, 0.5, 0.5)):
        self.obj = obj
        self.split_angle = math.radians(split_angle)
        self.normal_threshold = normal_threshold
        self.top_color = top_color
        self.bottom_color = bottom_color
        self.ambient_color = ambient_color

    def are_faces_coplanar(self, face1, face2, angle_threshold=0.01):
        dot = abs(face1.normal.dot(face2.normal))
        return dot > (1.0 - angle_threshold)

    def split_by_angle(self):
        bpy.context.view_layer.objects.active = self.obj
        self.obj.select_set(True)
        bpy.ops.object.mode_set(mode='OBJECT')

        mesh = self.obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Mark sharp edges (compatible with 4.4+)
        if hasattr(bm.edges[0] if bm.edges else None, 'smooth'):
            # Blender < 4.1 — use edge.smooth
            for edge in bm.edges:
                edge.smooth = True
        else:
            pass  # 4.1+ — sharp via attribute below

        sharp_count = 0
        for edge in bm.edges:
            if len(edge.link_faces) != 2:
                continue
            face1, face2 = edge.link_faces[0], edge.link_faces[1]
            if self.are_faces_coplanar(face1, face2):
                continue
            dot = face1.normal.dot(face2.normal)
            dot = max(-1.0, min(1.0, dot))
            angle = math.acos(dot)
            if angle >= self.split_angle:
                if hasattr(edge, 'smooth'):
                    edge.smooth = False
                sharp_count += 1

        # Blender 4.1+: set sharp_edge attribute
        if bpy.app.version >= (4, 1, 0) and sharp_count > 0:
            bm.to_mesh(mesh)
            # Use sharp_edge attribute
            if 'sharp_edge' not in mesh.attributes:
                mesh.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
            sharp_attr = mesh.attributes['sharp_edge']
            bm2 = bmesh.new()
            bm2.from_mesh(mesh)
            bm2.edges.ensure_lookup_table()
            bm2.faces.ensure_lookup_table()
            for edge in bm2.edges:
                if len(edge.link_faces) != 2:
                    continue
                face1, face2 = edge.link_faces[0], edge.link_faces[1]
                dot = face1.normal.dot(face2.normal)
                dot = max(-1.0, min(1.0, dot))
                angle = math.acos(dot)
                if angle >= self.split_angle:
                    sharp_attr.data[edge.index].value = True
            bm2.free()

        if bpy.app.version < (4, 1, 0):
            bm.to_mesh(mesh)
            bm.free()
        else:
            if not hasattr(self, '_bm2_used'):
                bm.to_mesh(mesh)
                bm.free()

        # Split edges by sharp marks (compatible 4.4+)
        if bpy.app.version >= (4, 1, 0):
            # Use Split Edges by sharp attribute
            bpy.context.view_layer.objects.active = self.obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            try:
                bpy.ops.mesh.split_normals()
            except (RuntimeError, AttributeError):
                # Op poll can fail (nothing selected) and the op itself is
                # absent on some builds — neither is fatal for the preview.
                pass
            bpy.ops.object.mode_set(mode='OBJECT')
        else:
            edge_split = self.obj.modifiers.new(name="EdgeSplit_Prelight", type='EDGE_SPLIT')
            edge_split.use_edge_angle = False
            edge_split.use_edge_sharp = True
            bpy.ops.object.modifier_apply(modifier=edge_split.name)

    def group_coplanar_faces(self, bm, normal_threshold=0.01):
        face_groups = []
        processed = set()

        for start_face in bm.faces:
            if start_face.index in processed:
                continue
            group = []
            frontier = [start_face]
            while frontier:
                face = frontier.pop(0)
                if face.index in processed:
                    continue
                processed.add(face.index)
                group.append(face.index)
                for edge in face.edges:
                    for linked_face in edge.link_faces:
                        if linked_face.index in processed:
                            continue
                        dot = abs(face.normal.dot(linked_face.normal))
                        if dot > (1.0 - normal_threshold):
                            frontier.append(linked_face)
            if group:
                avg_normal = Vector((0, 0, 0))
                for face_idx in group:
                    avg_normal += bm.faces[face_idx].normal
                avg_normal.normalize()
                face_groups.append((avg_normal, group))
        return face_groups

    def lerp_color(self, color1, color2, factor):
        return tuple(c1 + (c2 - c1) * factor for c1, c2 in zip(color1, color2))

    def apply_vertex_colors(self):
        mesh = self.obj.data

        color_layer = compat.vcol_get(mesh, "Prelight")
        if color_layer is None:
            color_layer = compat.vcol_new(mesh, "Prelight")

        compat.vcol_active(mesh, color_layer)

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()

        face_groups = self.group_coplanar_faces(bm)

        global_z_min = min(v.co.z for v in bm.verts)
        global_z_max = max(v.co.z for v in bm.verts)
        z_range = global_z_max - global_z_min if global_z_max != global_z_min else 1.0

        loop_colors = {}

        for group_normal, face_indices in face_groups:
            normal_z = group_normal.z
            group_colors = []

            for face_idx in face_indices:
                face = bm.faces[face_idx]
                for loop in face.loops:
                    vert = loop.vert
                    z_factor = (vert.co.z - global_z_min) / z_range

                    if normal_z > 0.3:
                        base_color = self.lerp_color(self.bottom_color, self.top_color, z_factor)
                        brightness = 0.1 + 0.2 * normal_z
                        color = tuple(min(1.0, c + brightness) for c in base_color)
                    elif normal_z < -0.3:
                        darkness = 0.3 * abs(normal_z)
                        base_color = self.lerp_color(self.bottom_color, self.ambient_color, z_factor * 0.5)
                        color = tuple(max(0.0, c - darkness) for c in base_color)
                    else:
                        color = self.lerp_color(self.bottom_color, self.ambient_color, z_factor)

                    group_colors.append(color)

            if group_colors:
                avg_color = (
                    sum(c[0] for c in group_colors) / len(group_colors),
                    sum(c[1] for c in group_colors) / len(group_colors),
                    sum(c[2] for c in group_colors) / len(group_colors)
                )
                for face_idx in face_indices:
                    face = bm.faces[face_idx]
                    for loop in face.loops:
                        loop_colors[loop.index] = avg_color

        bm.free()

        for poly in mesh.polygons:
            for loop_idx in poly.loop_indices:
                if loop_idx in loop_colors:
                    color = loop_colors[loop_idx]
                    color_layer.data[loop_idx].color = (color[0], color[1], color[2], 1.0)

    def run(self):
        self.split_by_angle()
        self.apply_vertex_colors()


def average_colors_on_coplanar_faces(obj, normal_threshold=0.01):
    if obj is None or obj.type != 'MESH':
        return False

    mesh = obj.data
    if not compat.vcol_list(mesh):
        return False

    color_layer = compat.vcol_active(mesh)
    if color_layer is None:
        color_layer = compat.vcol_list(mesh)[0]

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    face_groups = []
    processed = set()

    for start_face in bm.faces:
        if start_face.index in processed:
            continue
        group = []
        frontier = [start_face]
        while frontier:
            face = frontier.pop(0)
            if face.index in processed:
                continue
            processed.add(face.index)
            group.append(face.index)
            for edge in face.edges:
                for linked_face in edge.link_faces:
                    if linked_face.index in processed:
                        continue
                    dot = abs(face.normal.dot(linked_face.normal))
                    if dot > (1.0 - normal_threshold):
                        frontier.append(linked_face)
        if group:
            face_groups.append(group)

    bm.free()

    for group in face_groups:
        group_loops = []
        for face_idx in group:
            poly = mesh.polygons[face_idx]
            group_loops.extend(poly.loop_indices)

        if not group_loops:
            continue

        colors = []
        for loop_idx in group_loops:
            c = color_layer.data[loop_idx].color
            colors.append((c[0], c[1], c[2]))

        avg_color = (
            sum(c[0] for c in colors) / len(colors),
            sum(c[1] for c in colors) / len(colors),
            sum(c[2] for c in colors) / len(colors)
        )

        for loop_idx in group_loops:
            # Keep each loop's own alpha — averaging RGB across coplanar
            # faces must not flatten painted vertex transparency.
            a = color_layer.data[loop_idx].color[3]
            color_layer.data[loop_idx].color = (avg_color[0], avg_color[1], avg_color[2], a)

    return True


# =============================================================================
# UV2 TO VERTEX COLOR
# =============================================================================

def encode_uv2_to_color_16bit(obj):
    if not obj or obj.type != 'MESH':
        return False, "Select a mesh!"

    mesh = obj.data

    if len(mesh.uv_layers) < 2:
        return False, "Need 2 UV layers!"

    uv_layer = mesh.uv_layers[1]

    color_name = "UV2_Color"
    existing = compat.vcol_get(mesh, color_name)
    if existing is not None:
        compat.vcol_remove(mesh, existing)

    color_attr = compat.vcol_new(mesh, color_name)
    compat.vcol_active(mesh, color_attr)

    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            uv = uv_layer.data[loop_idx].uv
            u = max(0.0, min(1.0, uv[0]))
            v = max(0.0, min(1.0, uv[1]))

            u_16 = int(u * 65535)
            v_16 = int(v * 65535)

            r = (u_16 >> 8) / 255.0
            g = (u_16 & 0xFF) / 255.0
            b = (v_16 >> 8) / 255.0
            a = (v_16 & 0xFF) / 255.0

            color_attr.data[loop_idx].color = (r, g, b, a)

    return True, f"Encoded {len(mesh.polygons)} faces"


# =============================================================================
# PRELIGHT SCENE LIGHTS
# =============================================================================

def create_prelight_scene_lights(center, distance=100.0):
    """Создать 8 источников света для запекания prelight вокруг объекта"""

    # Color #BCBCBC = RGB(188, 188, 188) = (0.737, 0.737, 0.737)
    light_color = (0.737, 0.737, 0.737)

    cx, cy, cz = center

    # Light positions and intensities
    # Format: (name, offset (x, y, z), intensity)
    # Right = +X, Left = -X, Front = +Y, Back = -Y, Up = +Z, Down = -Z
    lights_config = [
        ("Prelight_TopRightBack",    ( distance,  -distance,  distance), 11),
        ("Prelight_BottomRightBack", ( distance,  -distance, -distance), 8),
        ("Prelight_TopLeftBack",     (-distance,  -distance,  distance), 10),
        ("Prelight_BottomLeftBack",  (-distance,  -distance, -distance), 7),
        ("Prelight_TopRightFront",   ( distance,   distance,  distance), 11),
        ("Prelight_BottomRightFront",( distance,   distance, -distance), 11),
        ("Prelight_TopLeftFront",    (-distance,   distance,  distance), 9),
        ("Prelight_BottomLeftFront", (-distance,   distance, -distance), 7),
    ]

    created_lights = []

    # Create collection for lights
    collection_name = "Prelight_Lights"
    if collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
        # Remove existing lights in collection
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    else:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    for name, offset, intensity in lights_config:
        # Create light data
        light_data = bpy.data.lights.new(name=name, type='POINT')
        light_data.color = light_color
        light_data.energy = intensity

        # Create light object with position relative to object center
        light_obj = bpy.data.objects.new(name=name, object_data=light_data)
        light_obj.location = (cx + offset[0], cy + offset[1], cz + offset[2])

        # Link to collection
        collection.objects.link(light_obj)
        created_lights.append(name)

    return created_lights


def remove_prelight_scene_lights():
    """Удалить все источники света prelight"""
    collection_name = "Prelight_Lights"
    if collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)
        return True
    return False


# Имя SUN-лампы prelight (отдельно от 8 точек, включается своей кнопкой).
PRELIGHT_SUN_NAME = "Prelight_Sun"


def create_prelight_sun(center, energy=9.0):
    """Создать направленное «солнце» для prelight (тип SUN).

    Светит так же, как 8 точечных ламп (тот же цвет #BCBCBC), но как
    направленный источник под углом «сверху-спереди» (как солнце GTA SA).
    Энергия по умолчанию ≈ среднему 8 точек (7..11 → ~9): у SUN нет
    затухания по расстоянию (atten=1 против ~0.33 у точек на d=100),
    поэтому одно солнце примерно повторяет суммарную яркость лит-поверхности
    восьмёрки. Точная подгонка — параметром energy.

    Живёт в ОТДЕЛЬНОЙ коллекции Prelight_Sun (не в Prelight_Lights), чтобы
    тумблер «8 ламп» (он сносит всю коллекцию восьмёрки) не удалял солнце —
    включается/выключается полностью независимо. Запекание берёт лампы по
    сцене (и POINT, и SUN), коллекция роли не играет.
    Положение роли не играет (солнце направленное) — ставим над центром
    для наглядности; направление задаёт rotation_euler."""
    light_color = (0.737, 0.737, 0.737)   # #BCBCBC — как у 8 точек

    collection_name = "Prelight_Sun"
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    # get-or-replace по имени (без .001-дубликатов)
    old = bpy.data.objects.get(PRELIGHT_SUN_NAME)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)

    sun_data = bpy.data.lights.new(name=PRELIGHT_SUN_NAME, type='SUN')
    sun_data.color = light_color
    sun_data.energy = energy

    sun_obj = bpy.data.objects.new(name=PRELIGHT_SUN_NAME, object_data=sun_data)
    cx, cy, cz = center
    sun_obj.location = (cx, cy, cz + 100.0)     # косметика (на свет не влияет)
    # Угол «сверху-спереди», как ключевое солнце (тот же, что в bake-риге).
    sun_obj.rotation_euler = (math.radians(50.0), 0.0, math.radians(40.0))
    collection.objects.link(sun_obj)
    return sun_obj


def remove_prelight_sun():
    """Удалить только SUN-лампу prelight (8 точек не трогаем). Пустую
    коллекцию Prelight_Sun после этого убираем."""
    sun = bpy.data.objects.get(PRELIGHT_SUN_NAME)
    if sun is None:
        return False
    bpy.data.objects.remove(sun, do_unlink=True)
    coll = bpy.data.collections.get("Prelight_Sun")
    if coll is not None and len(coll.objects) == 0:
        bpy.data.collections.remove(coll)
    return True


def _eval_loop_normals(obj):
    """Loop normals from the EVALUATED mesh — respects «Smooth by Angle»
    modifier (Blender 4.1+), legacy auto_smooth, manual sharp marks,
    and any custom split normals.

    Falls back to source mesh's loop normals if the evaluated mesh's
    loop count differs (topology-changing modifier upstream of ours,
    e.g. Subdivision Surface — bake doesn't support those anyway because
    we'd have nowhere to write the colors back to).
    """
    import numpy as np
    src = obj.data
    n_loops_src = len(src.loops)
    if n_loops_src == 0:
        return np.zeros((0, 3), dtype=np.float32), False

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = None
    used_eval = False
    try:
        eval_mesh = eval_obj.to_mesh()
        if len(eval_mesh.loops) == n_loops_src:
            try:
                eval_mesh.calc_normals_split()
            except Exception:
                pass
            arr = np.empty(n_loops_src * 3, dtype=np.float32)
            eval_mesh.loops.foreach_get('normal', arr)
            used_eval = True
        else:
            arr = None
    except Exception:
        arr = None
    finally:
        if eval_mesh is not None:
            try:
                eval_obj.to_mesh_clear()
            except Exception:
                pass

    if arr is None:
        # Fallback — source mesh loop normals.
        try:
            src.calc_normals_split()
        except Exception:
            pass
        arr = np.empty(n_loops_src * 3, dtype=np.float32)
        src.loops.foreach_get('normal', arr)

    return arr.reshape(n_loops_src, 3), used_eval


def _snapshot_smooth_state(mesh):
    """Save mesh.use_auto_smooth + edge.use_edge_sharp before sharpening
    for bake. Returns dict that ``_restore_smooth_state`` consumes."""
    import numpy as np
    n_edges = len(mesh.edges)
    sharp = np.zeros(n_edges, dtype=bool)
    if n_edges:
        flat = np.empty(n_edges, dtype=bool)
        mesh.edges.foreach_get('use_edge_sharp', flat)
        sharp = flat.copy()
    return {
        'use_auto_smooth': bool(getattr(mesh, 'use_auto_smooth', False)),
        'auto_smooth_angle': float(getattr(mesh, 'auto_smooth_angle', 0.0)),
        'sharp': sharp,
    }


def _apply_sharp_for_bake(mesh, angle_rad):
    """Mark edges with face-angle ≥ ``angle_rad`` as sharp and enable
    auto_smooth so ``mesh.calc_normals_split()`` produces face-aligned
    loop normals at those edges. Bake reads loop normals, so the
    resulting per-loop colors will differ across the sharp edge —
    which the DFF exporter's ``_needs_split`` detects and splits the
    vertices in the binary."""
    import numpy as np
    import bmesh

    snapshot = _snapshot_smooth_state(mesh)

    # Compute face-pair angle per edge via bmesh (cheap on small/medium
    # meshes; manual loop on Python wins over per-edge RNA traversal).
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.edges.ensure_lookup_table()
        n_edges = len(bm.edges)
        new_sharp = np.zeros(n_edges, dtype=bool)
        for i, e in enumerate(bm.edges):
            if len(e.link_faces) != 2:
                continue
            try:
                ang = e.calc_face_angle(0.0)
            except (ValueError, RuntimeError):
                continue
            if ang >= angle_rad:
                new_sharp[i] = True
        # OR with previously-sharp edges so existing manual marks
        # still hold (don't unmark anything the user marked).
        new_sharp |= snapshot['sharp']
        mesh.edges.foreach_set('use_edge_sharp', new_sharp.astype(np.bool_).tolist() if hasattr(new_sharp, 'tolist') else list(new_sharp))
    finally:
        bm.free()

    # auto_smooth was removed in Blender 4.1 — set only on older builds.
    if hasattr(mesh, 'use_auto_smooth'):
        mesh.use_auto_smooth = True
        # Set angle ≥ ours so calc_normals_split honours our explicit
        # sharp marks regardless of soft auto_smooth threshold.
        if hasattr(mesh, 'auto_smooth_angle'):
            mesh.auto_smooth_angle = max(angle_rad, snapshot['auto_smooth_angle'])

    return snapshot


def _restore_smooth_state(mesh, snapshot):
    """Restore the mesh's auto_smooth + per-edge sharp flags to whatever
    they were before ``_apply_sharp_for_bake``. The per-loop colors
    written during bake are NOT touched — they keep the per-face values
    so the DFF export still splits at corners. Removing the visual
    sharp/auto_smooth here just hides the smoothing artefacts in the
    viewport."""
    if snapshot is None:
        return
    if hasattr(mesh, 'use_auto_smooth'):
        mesh.use_auto_smooth = snapshot['use_auto_smooth']
        if hasattr(mesh, 'auto_smooth_angle'):
            mesh.auto_smooth_angle = snapshot['auto_smooth_angle']
    sharp = snapshot.get('sharp')
    if sharp is not None and len(sharp) == len(mesh.edges):
        try:
            import numpy as np
            mesh.edges.foreach_set('use_edge_sharp', np.asarray(sharp, dtype=bool))
        except Exception:
            for i, val in enumerate(sharp):
                mesh.edges[i].use_edge_sharp = bool(val)


def _sun_loop_intensity(light_obj, loop_world_no, loop_vidx, world_pos,
                        vert_world_no, n_verts, use_shadows, depsgraph):
    """Per-loop вклад SUN-лампы: n·L БЕЗ затухания по расстоянию (солнце
    направленное), с теневым raycast'ом per-vertex.

    Направление НА солнце = локальный +Z лампы (Blender светит вдоль -Z).
    Тень — луч от вершины в сторону солнца на большую дистанцию (1e4).
    Возвращает (n_loops,) float32 = n_dot_l · shadow. Множитель цвета/энергии
    накладывает вызывающий — как и для POINT, чтобы код света был единым."""
    import numpy as np
    Lv = light_obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    Lv.normalize()
    L_np = np.array((Lv.x, Lv.y, Lv.z), dtype=np.float32)

    shadow_per_vert = np.ones(n_verts, dtype=np.float32)
    if use_shadows and depsgraph is not None:
        ray_dir = Vector((float(L_np[0]), float(L_np[1]), float(L_np[2])))
        for i in range(n_verts):
            wp = world_pos[i]
            ray_start = wp + vert_world_no[i] * 0.02
            hit = bpy.context.scene.ray_cast(
                depsgraph,
                Vector((float(ray_start[0]), float(ray_start[1]), float(ray_start[2]))),
                ray_dir, distance=1.0e4)[0]
            if hit:
                shadow_per_vert[i] = 0.0

    n_dot_l = np.maximum(loop_world_no @ L_np, 0.0)
    return n_dot_l * shadow_per_vert[loop_vidx]


_BAKE_LIGHT_TYPES = ('POINT', 'SUN', 'SPOT', 'AREA')


def _light_world_pos(light_obj):
    """Мировая позиция лампы (родитель / constraint / delta учтены).
    .location — координаты относительно родителя: лампа с родителем
    светила из неверной точки, хотя направление уже шло из matrix_world."""
    return np.array(light_obj.matrix_world.translation, dtype=np.float32)


def _is_2dfx_preview_lamp(light_obj):
    """Превью-лампа 2DFX-света (fx_preview.create_light_preview) — подсветка
    вьюпорта, не источник прилайта (2DFX-свет игра рисует сама; в Max 2DFX —
    хелперы и не запекаются). Её .location = (0,0,0) у 2DFX Empty: раньше
    она пеклась из мирового центра, из мировой позиции — выжигала бы пятно
    у каждого фонаря. Маркер inu_2dfx_preview; риги до маркера — ребёнок
    2DFX Empty с inu.type NON."""
    if light_obj.get("inu_2dfx_preview"):
        return True
    par = light_obj.parent
    return (par is not None
            and getattr(getattr(par, 'inu', None), 'type', '') == '2DFX'
            and getattr(getattr(light_obj, 'inu', None), 'type', '') == 'NON')


def _allowed_light_types(allowed_types):
    """Типы ламп для запекания. None — все (_BAKE_LIGHT_TYPES); явный набор
    соблюдается, даже пустой: все тумблеры Point/Sun/Spot/Area выкл. =
    ламп нет (раньше пустой набор читался как «все типы»)."""
    return set(_BAKE_LIGHT_TYPES) if allowed_types is None else set(allowed_types)


def _spot_cone_factor(light_obj, loop_world_pos):
    """Per-loop множитель конуса SPOT (1 внутри, 0 снаружи, мягкий край по
    spot_blend). Для НЕ-SPOT возвращает None (полный вклад). AREA и POINT
    считаются как точечный источник (без направленного конуса)."""
    import math
    light = light_obj.data
    if light.type != 'SPOT':
        return None
    fwd = np.array(light_obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0)),
                   dtype=np.float32)
    fn = float(np.linalg.norm(fwd))
    if fn < 1e-6:
        return None
    fwd /= fn
    lp = _light_world_pos(light_obj)
    d = loop_world_pos - lp[None, :]           # направление свет → поверхность
    dn = np.linalg.norm(d, axis=1, keepdims=True)
    dn[dn < 1e-6] = 1.0
    d = d / dn
    cos_a = np.sum(d * fwd[None, :], axis=1)
    half = float(light.spot_size) * 0.5
    cos_out = math.cos(half)
    cos_in = math.cos(half * (1.0 - float(light.spot_blend)))
    denom = (cos_in - cos_out) or 1e-4
    return np.clip((cos_a - cos_out) / denom, 0.0, 1.0).astype(np.float32)


def _sample_equirect(image, dirs, azimuth_offset=0.0):
    """Сэмпл equirectangular HDRI по направлениям dirs (n,3) → (n,3) RGB.
    Nearest-выборка, векторизовано. Развёртка как у Cycles
    direction_to_equirectangular / EEVEE node_tex_environment_equirectangular:
    +X → u 0.5, +Y → u 0.25, зенит → верхняя строка. azimuth_offset = a
    (радианы): поиск идёт по az' = az + a (как Vector Rotate / Mapping POINT
    по Z). None если картинка недоступна."""
    import math
    try:
        W, H = int(image.size[0]), int(image.size[1])
        if W <= 0 or H <= 0:
            return None
        px = np.empty(W * H * 4, dtype=np.float32)
        image.pixels.foreach_get(px)
        px = px.reshape(H, W, 4)          # строка 0 = низ картинки
    except Exception:
        return None
    d = dirs.astype(np.float32)
    nrm = np.linalg.norm(d, axis=1, keepdims=True)
    nrm[nrm < 1e-6] = 1.0
    d = d / nrm
    u = 0.5 - (np.arctan2(d[:, 1], d[:, 0]) + float(azimuth_offset)) / (2.0 * math.pi)
    u = np.mod(u, 1.0)                     # заворот по горизонтали
    v = 0.5 + np.arcsin(np.clip(d[:, 2], -1.0, 1.0)) / math.pi
    ix = np.clip((u * W).astype(np.int32), 0, W - 1)
    iy = np.clip((v * H).astype(np.int32), 0, H - 1)
    return px[iy, ix, :3].astype(np.float32)


def _find_view3d_shading():
    """Shading первого VIEW_3D (вьюпорта). None если не найден."""
    try:
        wm = bpy.context.window_manager
        for win in wm.windows:
            scr = getattr(win, 'screen', None)
            if not scr:
                continue
            for area in scr.areas:
                if area.type != 'VIEW_3D':
                    continue
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        return space.shading
    except Exception:
        pass
    return None


def _studio_light_path(name):
    """Путь к .exr studio-light типа WORLD по имени. None если нет."""
    try:
        for sl in bpy.context.preferences.studio_lights:
            if sl.name == name and sl.type == 'WORLD':
                return sl.path
    except Exception:
        pass
    return None


def _viewport_hdri_sample(loop_world_no):
    """Сэмпл HDRI из «Окружение сцены» вьюпорта (studio-light материал-
    превью) — та самая HDRI, что юзер выбирает в выпадашке Шейдинг
    вьюпорта. Учитывает поворот и интенсивность. None если не применимо."""
    shading = _find_view3d_shading()
    if shading is None:
        return None
    stype = getattr(shading, 'type', '')
    # Если рендер-режим с реальным миром сцены — HDRI берётся из scene.world
    # (обработается ниже). Здесь только превью-мир (studio light).
    if stype == 'RENDERED' and getattr(shading, 'use_scene_world', True):
        return None
    if stype == 'MATERIAL' and getattr(shading, 'use_scene_world', False):
        return None
    if stype not in ('MATERIAL', 'RENDERED'):
        return None
    path = _studio_light_path(getattr(shading, 'studio_light', ''))
    if not path:
        return None
    try:
        img = bpy.data.images.load(path, check_existing=True)
    except Exception:
        return None
    rot = float(getattr(shading, 'studiolight_rotate_z', 0.0))
    intensity = float(getattr(shading, 'studiolight_intensity', 1.0))
    col = _sample_equirect(img, loop_world_no, azimuth_offset=rot)
    if col is None:
        return None
    return col * intensity


_MAPPING_WARNED = set()


def _env_mapping_z_offset(env, world_name=''):
    """Поворот мира по Z из узла Mapping на входе Vector у Environment
    Texture → azimuth_offset для _sample_equirect. Cycles (svm/mapping_util.h):
    POINT/VECTOR/NORMAL — R·v (поиск по az + rz), TEXTURE — Rᵀ·v (az − rz).
    Берётся только Z; X/Y, связанный Rotation, Location и неравномерный /
    отрицательный Scale не учитываются (одна строка в консоль на узел).
    0.0 если Mapping нет, он выключен (mute) или что-то не прочиталось."""
    try:
        sock = env.inputs['Vector']
        if not sock.is_linked:
            return 0.0
        node = sock.links[0].from_node
        for _ in range(16):
            if node.type != 'REROUTE' or not node.inputs[0].links:
                break
            node = node.inputs[0].links[0].from_node
        if node.type != 'MAPPING' or getattr(node, 'mute', False):
            return 0.0
        vt = node.vector_type
        rot = node.inputs['Rotation']
        rz = float(rot.default_value[2])
        try:
            key = (world_name, node.name)
            if key not in _MAPPING_WARNED:
                rx, ry = rot.default_value[0], rot.default_value[1]
                sx, sy, sz = node.inputs['Scale'].default_value
                ignored = (rot.is_linked
                           or abs(rx) > 1e-6 or abs(ry) > 1e-6
                           or abs(sx - sy) > 1e-6 or abs(sx - sz) > 1e-6
                           or min(sx, sy, sz) <= 0.0)
                if vt in ('POINT', 'TEXTURE') and not ignored:
                    ignored = any(abs(c) > 1e-6
                                  for c in node.inputs['Location'].default_value)
                if ignored:
                    _MAPPING_WARNED.add(key)
                    print("[INU prelight] World Mapping: only Z rotation is used "
                          "(X/Y rotation, linked Rotation, location, "
                          "non-uniform/negative scale ignored)")
        except Exception:
            pass
        return -rz if vt == 'TEXTURE' else rz
    except Exception:
        return 0.0


def _world_env_sample(loop_world_no):
    """Вклад мира/HDRI (World) на каждый loop по направлению нормали.
    Приоритет — HDRI вьюпорта (то, что юзер выбирает в Шейдинг вьюпорта),
    затем scene.world. Возвращает (n_loops,3) float32 или None. Всё в try —
    бейк не должен падать из-за мира."""
    try:
        vp = _viewport_hdri_sample(loop_world_no)
        if vp is not None:
            return vp
        scene = bpy.context.scene
        world = scene.world if scene else None
        if world is None:
            return None
        n = loop_world_no.shape[0]
        if getattr(world, 'use_nodes', False) and world.node_tree:
            nt = world.node_tree
            env = next((nd for nd in nt.nodes
                        if nd.type == 'TEX_ENVIRONMENT'
                        and getattr(nd, 'image', None)), None)
            bg = next((nd for nd in nt.nodes if nd.type == 'BACKGROUND'), None)
            strength = 1.0
            if bg is not None:
                try:
                    strength = float(bg.inputs['Strength'].default_value)
                except Exception:
                    strength = 1.0
            if env is not None:
                col = _sample_equirect(
                    env.image, loop_world_no,
                    azimuth_offset=_env_mapping_z_offset(
                        env, getattr(world, 'name', '')))
                if col is not None:
                    return col * strength
            if bg is not None:
                c = bg.inputs['Color'].default_value
                base = np.array((c[0], c[1], c[2]), dtype=np.float32) * strength
                return np.tile(base, (n, 1))
            return None
        # legacy: плоский цвет мира
        c = world.color
        base = np.array((c[0], c[1], c[2]), dtype=np.float32)
        return np.tile(base, (n, 1))
    except Exception:
        return None


def bake_vertex_colors_from_lights(obj, use_shadows=True,
                                   allowed_types=None, use_hdri=False):
    """Запечь освещение от Point/Sun/Spot/Area источников в vertex colors.

    Lambert per-corner (loop.normal сохраняет smooth shading), но
    теневой raycast выполняется один раз на вершину — corner'ы одной
    вершины делят результат. Запись цвета — пакетная через
    foreach_set, без поэлементного RNA-доступа.
    """
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    allowed = _allowed_light_types(allowed_types)
    lights = []
    for light_obj in bpy.data.objects:
        if light_obj.type == 'LIGHT' and light_obj.data.type in allowed:
            if not light_obj.visible_get():
                continue
            if light_obj.hide_render:
                continue
            if _is_2dfx_preview_lamp(light_obj):
                continue
            lights.append(light_obj)

    if not lights and not use_hdri:
        return False, "No visible lights in scene!"

    mesh = obj.data
    n_verts = len(mesh.vertices)
    n_loops = len(mesh.loops)
    if n_loops == 0:
        return False, "Mesh has no loops"

    # Пишем в АКТИВНЫЙ канал (Day/Night/Col), как и быстрый bake_..._simple.
    # Раньше функция всегда удаляла и пересоздавала "BakedLight" и делала его
    # активным — из-за этого «Запечь поверх с тенями» складывал снимок с чужим
    # ПЕРЕСОЗДАННЫМ атрибутом, активный канал юзера (Day) не менялся, а
    # следующее «Запечь» уходило уже в "BakedLight" вместо Day.
    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        existing = compat.vcol_list(mesh)
        if existing:
            color_attr = existing[0]
        else:
            color_attr = compat.vcol_new(mesh, "Col")
        compat.vcol_active(mesh, color_attr)
    # Сохранить альфу активного канала — bake обновляет только RGB.
    prev_alpha = None
    if len(color_attr.data) == n_loops:
        _tmp = np.empty(n_loops * 4, dtype=np.float32)
        color_attr.data.foreach_get('color', _tmp)
        prev_alpha = _tmp[3::4].copy()

    world_matrix = obj.matrix_world
    normal_matrix = world_matrix.to_3x3().inverted().transposed()

    try:
        mesh.calc_normals_split()
    except Exception:
        pass

    depsgraph = bpy.context.evaluated_depsgraph_get() if use_shadows else None

    # ── Vectorized geometry pull ─────────────────────────────────
    vert_co = np.empty(n_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', vert_co)
    vert_co = vert_co.reshape(n_verts, 3)
    M = np.array(world_matrix, dtype=np.float32)
    homo = np.concatenate(
        [vert_co, np.ones((n_verts, 1), dtype=np.float32)], axis=1)
    world_pos = (homo @ M.T)[:, :3]

    NM = np.array(normal_matrix, dtype=np.float32)

    vert_no = np.empty(n_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get('normal', vert_no)
    vert_no = vert_no.reshape(n_verts, 3)
    vert_world_no = vert_no @ NM.T
    norms = np.linalg.norm(vert_world_no, axis=1, keepdims=True)
    norms[norms < 1e-6] = 1.0
    vert_world_no /= norms

    # Loop normals — read from EVALUATED mesh to respect «Smooth by
    # Angle» modifier / legacy auto_smooth / sharp-edge marks. Without
    # this the bake ignores the user's smoothing setup and always
    # produces smooth corners regardless of viewport shading.
    loop_no, _used_eval = _eval_loop_normals(obj)
    loop_world_no = loop_no @ NM.T
    norms = np.linalg.norm(loop_world_no, axis=1, keepdims=True)
    norms[norms < 1e-6] = 1.0
    loop_world_no /= norms

    loop_vidx = np.empty(n_loops, dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', loop_vidx)
    loop_world_pos = world_pos[loop_vidx]

    total = np.zeros((n_loops, 3), dtype=np.float32)

    for light_obj in lights:
        light = light_obj.data
        light_color = np.array(light.color, dtype=np.float32) * light.energy

        # ── SUN: направленный свет (n·L, без затухания) ──
        if light.type == 'SUN':
            sun_i = _sun_loop_intensity(
                light_obj, loop_world_no, loop_vidx, world_pos,
                vert_world_no, n_verts, use_shadows, depsgraph)
            total += sun_i[:, None] * light_color[None, :]
            continue

        light_pos = _light_world_pos(light_obj)

        # ── Per-vertex shadow raycast (cached, reused by all corners)
        shadow_per_vert = np.ones(n_verts, dtype=np.float32)
        if use_shadows and depsgraph is not None:
            for i in range(n_verts):
                wp = world_pos[i]
                ld = light_pos - wp
                dist = float(np.linalg.norm(ld))
                if dist < 1e-3:
                    continue
                ld_n = ld / dist
                ray_start = wp + vert_world_no[i] * 0.02
                result = bpy.context.scene.ray_cast(
                    depsgraph,
                    Vector((float(ray_start[0]), float(ray_start[1]), float(ray_start[2]))),
                    Vector((float(ld_n[0]), float(ld_n[1]), float(ld_n[2]))),
                    distance=dist - 0.04,
                )[0]
                if result:
                    shadow_per_vert[i] = 0.0

        # ── Per-loop Lambert (vectorized) ────────────────────────
        ld = light_pos[None, :] - loop_world_pos
        dist = np.linalg.norm(ld, axis=1)
        valid = dist >= 1e-3
        dist_safe = np.where(valid, dist, 1.0)
        ld_n = ld / dist_safe[:, None]
        n_dot_l = np.maximum(np.sum(loop_world_no * ld_n, axis=1), 0.0)
        n_dot_l = np.where(valid, n_dot_l, 0.0)
        atten = 1.0 / (1.0 + dist * 0.01 + dist * dist * 0.0001)
        shadow_for_loop = shadow_per_vert[loop_vidx]
        intensity = atten * n_dot_l * shadow_for_loop
        _spot = _spot_cone_factor(light_obj, loop_world_pos)
        if _spot is not None:
            intensity = intensity * _spot
        total += intensity[:, None] * light_color[None, :]

    # ── HDRI / World: цвет неба по направлению нормали ──
    if use_hdri:
        env = _world_env_sample(loop_world_no)
        if env is not None:
            total += env

    np.clip(total, 0.0, 1.0, out=total)
    flat = np.empty(n_loops * 4, dtype=np.float32)
    flat[0::4] = total[:, 0]
    flat[1::4] = total[:, 1]
    flat[2::4] = total[:, 2]
    flat[3::4] = prev_alpha if prev_alpha is not None else 1.0
    color_attr.data.foreach_set('color', flat)

    _hdri = " + HDRI" if use_hdri else ""
    return True, f"Baked lighting from {len(lights)} lights{_hdri}"


def bake_vertex_colors_simple(obj, ambient=0.05, intensity_mult=0.008, gamma=1.8,
                              use_shadows=True, allowed_types=None, use_hdri=False):
    """Быстрое запекание vertex colors от Point источников.

    Та же оптимизация что и в bake_vertex_colors_from_lights — Lambert
    per-corner, теневой raycast per-vertex, batch foreach_set."""
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    allowed = _allowed_light_types(allowed_types)
    lights = []
    for light_obj in bpy.data.objects:
        if light_obj.type == 'LIGHT' and light_obj.data.type in allowed:
            if not light_obj.visible_get():
                continue
            if light_obj.hide_render:
                continue
            if _is_2dfx_preview_lamp(light_obj):
                continue
            lights.append(light_obj)

    if not lights and not use_hdri:
        return False, "No visible lights in scene!"

    mesh = obj.data
    n_verts = len(mesh.vertices)
    n_loops = len(mesh.loops)
    if n_loops == 0:
        return False, "Mesh has no loops"

    created = False
    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        existing = compat.vcol_list(mesh)
        if existing:
            color_attr = existing[0]
        else:
            color_attr = compat.vcol_new(mesh, "Col")
            created = True
        compat.vcol_active(mesh, color_attr)
    color_name = color_attr.name

    world_matrix = obj.matrix_world
    normal_matrix = world_matrix.to_3x3().inverted().transposed()

    try:
        mesh.calc_normals_split()
    except Exception:
        pass

    depsgraph = bpy.context.evaluated_depsgraph_get() if use_shadows else None

    vert_co = np.empty(n_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', vert_co)
    vert_co = vert_co.reshape(n_verts, 3)
    M = np.array(world_matrix, dtype=np.float32)
    homo = np.concatenate(
        [vert_co, np.ones((n_verts, 1), dtype=np.float32)], axis=1)
    world_pos = (homo @ M.T)[:, :3]

    NM = np.array(normal_matrix, dtype=np.float32)

    vert_no = np.empty(n_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get('normal', vert_no)
    vert_no = vert_no.reshape(n_verts, 3)
    vert_world_no = vert_no @ NM.T
    norms = np.linalg.norm(vert_world_no, axis=1, keepdims=True)
    norms[norms < 1e-6] = 1.0
    vert_world_no /= norms

    # Loop normals from EVALUATED mesh (respects Smooth-by-Angle modifier
    # and sharp marks; see _eval_loop_normals).
    loop_no, _used_eval = _eval_loop_normals(obj)
    loop_world_no = loop_no @ NM.T
    norms = np.linalg.norm(loop_world_no, axis=1, keepdims=True)
    norms[norms < 1e-6] = 1.0
    loop_world_no /= norms

    loop_vidx = np.empty(n_loops, dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', loop_vidx)
    loop_world_pos = world_pos[loop_vidx]

    total = np.full((n_loops, 3), ambient, dtype=np.float32)

    for light_obj in lights:
        light = light_obj.data
        light_color = np.array(light.color, dtype=np.float32) * (
            light.energy * intensity_mult)

        # ── SUN: направленный свет (n·L, без затухания) ──
        if light.type == 'SUN':
            sun_i = _sun_loop_intensity(
                light_obj, loop_world_no, loop_vidx, world_pos,
                vert_world_no, n_verts, use_shadows, depsgraph)
            total += sun_i[:, None] * light_color[None, :]
            continue

        light_pos = _light_world_pos(light_obj)

        shadow_per_vert = np.ones(n_verts, dtype=np.float32)
        if use_shadows and depsgraph is not None:
            for i in range(n_verts):
                wp = world_pos[i]
                ld = light_pos - wp
                dist = float(np.linalg.norm(ld))
                if dist < 1e-3:
                    continue
                ld_n = ld / dist
                ray_start = wp + vert_world_no[i] * 0.02
                result = bpy.context.scene.ray_cast(
                    depsgraph,
                    Vector((float(ray_start[0]), float(ray_start[1]), float(ray_start[2]))),
                    Vector((float(ld_n[0]), float(ld_n[1]), float(ld_n[2]))),
                    distance=dist - 0.04,
                )[0]
                if result:
                    shadow_per_vert[i] = 0.0

        ld = light_pos[None, :] - loop_world_pos
        dist = np.linalg.norm(ld, axis=1)
        valid = dist >= 1e-3
        dist_safe = np.where(valid, dist, 1.0)
        ld_n = ld / dist_safe[:, None]
        n_dot_l = np.maximum(np.sum(loop_world_no * ld_n, axis=1), 0.0)
        n_dot_l = np.where(valid, n_dot_l, 0.0)
        atten = 1.0 / (1.0 + dist * dist * 0.0001)
        shadow_for_loop = shadow_per_vert[loop_vidx]
        intensity = atten * n_dot_l * shadow_for_loop
        _spot = _spot_cone_factor(light_obj, loop_world_pos)
        if _spot is not None:
            intensity = intensity * _spot
        total += intensity[:, None] * light_color[None, :]

    # ── HDRI / World: цвет неба по направлению нормали ──
    if use_hdri:
        env = _world_env_sample(loop_world_no)
        if env is not None:
            total += env

    # Gamma + clamp (negatives clipped first so pow is well-defined)
    np.clip(total, 0.0, None, out=total)
    total = np.power(total, 1.0 / gamma, dtype=np.float32)
    np.clip(total, 0.0, 1.0, out=total)

    flat = np.empty(n_loops * 4, dtype=np.float32)
    # Preserve the layer's existing alpha — baking prelight into the active
    # Day/Night layer must NOT wipe painted vertex transparency. Only a
    # freshly-created layer (no prior alpha) starts opaque.
    if created or len(color_attr.data) != n_loops:
        flat[3::4] = 1.0
    else:
        color_attr.data.foreach_get('color', flat)
    flat[0::4] = total[:, 0]
    flat[1::4] = total[:, 1]
    flat[2::4] = total[:, 2]
    color_attr.data.foreach_set('color', flat)

    return True, f"Baked to '{color_name}' from {len(lights)} lights"


def prelight_foliage(obj, *, material_index=None, select_only=False,
                     inside=0.25, outside=1.0, gamma=1.0, height_dark=0.0,
                     color_height_dark=0.0,
                     top_bright=0.0, top_height=1.0, variation=0.0,
                     light_tint=(1.0, 1.0, 1.0), shadow_tint=(1.0, 1.0, 1.0),
                     tint_strength=0.0, metric='SPHERE', blend='MULTIPLY',
                     both_sides=False, mode='BOTH'):
    """Радиальный prelight листвы: темнее в центре кроны, светлее на
    периферии (+ опциональный tint оттенка листвы).

    Не использует свет сцены — чисто геометрический градиент по
    расстоянию вершины от центра кроны. Идеален для billboard-листвы
    GTA-деревьев, где обычный AO-bake шумит на alpha-картах.

    Параметры:
      material_index — красить ТОЛЬКО loops с этим material_index
                       (None = без фильтра по материалу).
      select_only    — красить только выделенные полигоны (Edit-выделение).
      inside/outside — яркость в центре кроны / на периферии [0..1].
      gamma          — кривизна градиента; >1 расширяет светлую зону,
                       <1 — тёмную.
      height_dark    — доп. затемнение НИЗА кроны [0..1] (самозатенение
                       сверху); 0 = выкл.
      light_tint / shadow_tint — цвет листвы, ЛИНЕЙНЫЙ RGB 0..1 (оператор
                       переводит sRGB палитры); подмешивается multiply,
                       сохраняя затенение.
      tint_strength  — сила tint [0..1]; 0 = цвет не меняется.
      metric         — 'SPHERE' (3D-расстояние от центроида) или
                       'CYLINDER' (горизонтальное от вертикальной оси
                       ствола через центроид).
      blend          — 'MULTIPLY' (поверх существующего прилайта —
                       затенение и tint множатся на текущий vcol,
                       запечённый свет сохраняется) или 'REPLACE'
                       (заменить vcol целиком).

    Пишет в активный color attribute (как bake_vertex_colors_*). Loops
    вне маски (ствол, не-выделенное) сохраняют прежний цвет; альфа слоя
    (нарисованная прозрачность) не трогается (новый слой — белый, альфа 1).

    Возвращает (ok: bool, message: str)."""
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"
    mesh = obj.data
    n_loops = len(mesh.loops)
    n_polys = len(mesh.polygons)
    if n_loops == 0:
        return False, "Mesh has no loops"

    created = False
    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        existing = compat.vcol_list(mesh)
        if existing:
            color_attr = existing[0]
        else:
            color_attr = compat.vcol_new(mesh, "Col")
            created = True
        compat.vcol_active(mesh, color_attr)
    color_name = color_attr.name

    # ── loop → vertex / material / select ────────────────────────────
    loop_vidx = np.empty(n_loops, dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', loop_vidx)

    loop_total = np.empty(n_polys, dtype=np.int32)
    mesh.polygons.foreach_get('loop_total', loop_total)
    # Loops хранятся последовательно по полигонам (poly.loop_start —
    # кумулятивная сумма), поэтому np.repeat даёт per-loop атрибут.
    poly_mat = np.empty(n_polys, dtype=np.int32)
    mesh.polygons.foreach_get('material_index', poly_mat)
    loop_mat = np.repeat(poly_mat, loop_total)

    # ── позиции вершин (local — масштаб не влияет на нормализованный t) ─
    n_verts = len(mesh.vertices)
    vco = np.empty(n_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', vco)
    vco = vco.reshape(n_verts, 3)
    loop_pos = vco[loop_vidx]                 # (n_loops, 3)

    # ── маска ГРАНЕЙ: материал + выделение ──
    poly_mask = np.ones(n_polys, dtype=bool)
    if material_index is not None:
        poly_mask &= (poly_mat == int(material_index))
    if select_only:
        poly_sel = np.empty(n_polys, dtype=bool)
        mesh.polygons.foreach_get('select', poly_sel)
        poly_mask &= poly_sel

    # «Обе стороны»: GTA-листья часто дублированы — задняя «карта» лежит в той
    # же точке, но с перевёрнутой намоткой (видна с обратной стороны). Красим
    # обе.
    #
    # Полигоны триангулированы, и передняя/задняя карты могут быть разбиты по
    # РАЗНЫМ диагоналям — тогда у треугольников разные центроиды, и матч по
    # грани/центроиду срывается. Поэтому работаем по ПОЗИЦИЯМ ВЕРШИН:
    #   1) собираем множество позиций вершин закрашенной области (квантованных
    #      по сетке + соседние ячейки — снимает float-погрешность и границу);
    #   2) добавляем в маску любую грань, ВСЕ вершины которой лежат в этом
    #      множестве. Дубль листа (как угодно триангулированный) проходит, а
    #      ствол — нет (у него совпадают лишь отдельные вершины, не все).
    if both_sides and poly_mask.any():
        TOL = 1.0e-3                              # размер ячейки, лок. ед.
        q = np.round(vco / TOL).astype(np.int64)  # (n_verts, 3) квантованные
        qt = [(int(a), int(b), int(c)) for a, b, c in q.tolist()]

        masked_loops = np.repeat(poly_mask, loop_total)
        masked_vids = np.unique(loop_vidx[masked_loops])
        pos_set = set()
        for vid in masked_vids:
            bx, by, bz = qt[int(vid)]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        pos_set.add((bx + dx, by + dy, bz + dz))

        loop_start = np.empty(n_polys, dtype=np.int32)
        mesh.polygons.foreach_get('loop_start', loop_start)
        for fi in range(n_polys):
            if poly_mask[fi]:
                continue
            ls = int(loop_start[fi])
            lt = int(loop_total[fi])
            if all(qt[int(v)] in pos_set for v in loop_vidx[ls:ls + lt]):
                poly_mask[fi] = True

    mask = np.repeat(poly_mask, loop_total)
    if not mask.any():
        return False, "No matching faces (material / selection empty)"

    fol = loop_pos[mask]                        # позиции loops листвы
    center = fol.mean(axis=0)                   # центроид кроны

    if metric == 'CYLINDER':
        # горизонтальное расстояние от вертикальной оси через центроид
        delta = loop_pos[:, :2] - center[:2]
        dist = np.linalg.norm(delta, axis=1)
    else:                                       # 'SPHERE'
        dist = np.linalg.norm(loop_pos - center, axis=1)

    dmax = float(dist[mask].max())
    if dmax < 1e-9:
        dmax = 1.0
    t = np.clip(dist / dmax, 0.0, 1.0)
    g = max(float(gamma), 1e-3)
    tgrad = (t ** g).astype(np.float32)         # 0 = центр кроны, 1 = периферия

    apply_shade = mode in ('SHADE', 'BOTH')      # затенение (градиент яркости)
    apply_color = mode in ('COLOR', 'BOTH')      # цвет листвы (свет/тень)

    # ── вертикальный градиент кроны (0 = низ, 1 = верх) ──
    # Нужен и затемнению низа (затенение), и подсветке верха (цвет).
    z = loop_pos[:, 2]
    zf = z[mask]
    zmin, zmax = float(zf.min()), float(zf.max())
    if zmax - zmin > 1e-9:
        zt = np.clip((z - zmin) / (zmax - zmin), 0.0, 1.0).astype(np.float32)
    else:
        zt = np.zeros(n_loops, dtype=np.float32)

    # ── затенение кроны: радиальный градиент яркости (блок «Крона») ──
    if apply_shade:
        bright = float(inside) + (float(outside) - float(inside)) * tgrad
        if height_dark > 0.0:                    # затемнить низ — настройка кроны
            bright = bright * ((1.0 - float(height_dark))
                               + float(height_dark) * zt)
        bright = np.clip(bright, 0.0, 1.0).astype(np.float32)
    else:
        bright = np.ones(n_loops, dtype=np.float32)   # цвет-режим: базовая яркость 1

    # ── модификаторы вида листвы (блок «Цвет»): низ / верх / разброс ──
    # Все три — мультипликаторы яркости; работают и поверх затенения (BOTH),
    # и на чистой белой базе (только «Цвет»). Итоговый клип к [0..1] — в конце.
    if apply_color:
        if color_height_dark > 0.0:              # затемнить низ — настройка цвета
            bright = bright * ((1.0 - float(color_height_dark))
                               + float(color_height_dark) * zt)
        if top_bright > 0.0:                     # подсветить макушку (>1 = ярче)
            thr = 1.0 - float(np.clip(top_height, 0.0, 1.0))
            zt_top = np.clip((zt - thr) / max(1.0 - thr, 1e-6), 0.0, 1.0)
            bright = bright * (1.0 + float(top_bright) * zt_top)
        if variation > 0.0:                      # случайный разброс ПО ВЕРШИНАМ
            rng = np.random.default_rng(1234)
            vrand = rng.uniform(1.0 - float(variation), 1.0,
                                size=n_verts).astype(np.float32)
            bright = bright * vrand[loop_vidx]

    # ── цвет листвы: тень (центр) → свет (периферия) по градиенту ──
    if apply_color:
        light_rgb = np.array(light_tint, dtype=np.float32)
        shadow_rgb = np.array(shadow_tint, dtype=np.float32)
        s = float(np.clip(tint_strength, 0.0, 1.0))
        tint_per = (shadow_rgb[None, :] * (1.0 - tgrad[:, None])
                    + light_rgb[None, :] * tgrad[:, None])      # (n_loops, 3)
        eff_tint = (1.0 - s) * np.ones((1, 3), dtype=np.float32) + s * tint_per
    else:
        eff_tint = np.ones((1, 3), dtype=np.float32)            # затенение-режим: цвет не трогаем

    # ── читаем текущие цвета, переписываем только loops маски ─────────
    flat = np.empty(n_loops * 4, dtype=np.float32)
    color_attr.data.foreach_get('color', flat)
    flat4 = flat.reshape(n_loops, 4)
    # Свежесозданный attr инициализируется нулями (чёрный) — для MULTIPLY
    # это дало бы чёрный результат, поэтому стартуем с белой базы.
    if created:
        flat4[:, 0:3] = 1.0
        flat4[:, 3] = 1.0

    shade = bright[:, None] * eff_tint               # затенение × оттенок (per-loop)
    if blend == 'MULTIPLY':
        # AO кроны + tint множатся на существующий прилайт (свет остаётся)
        out = flat4[:, 0:3] * shade
    else:                                            # 'REPLACE'
        out = shade
    flat4[mask, 0:3] = np.clip(out[mask], 0.0, 1.0)
    color_attr.data.foreach_set('color', flat4.ravel())

    n_painted = int(mask.sum())
    return True, f"Foliage prelight → '{color_name}' ({n_painted} loops)"


def apply_brightness_offset(obj, v_offset):
    """Apply V (brightness) offset to vertex colors like 3Ds Max Adjust Color

    In 3Ds Max, V offset works as percentage:
    - V = -80 means keep 20% of brightness (multiply by 0.2)
    - V = +50 means increase brightness by 50% (multiply by 1.5)

    Tracks current V offset to allow adjusting in any direction.
    """
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    mesh = obj.data
    if not compat.vcol_list(mesh):
        return False, "No vertex colors found!"

    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        return False, "No active color layer!"

    # Get current V offset stored on the layer (default 0 = no offset applied yet)
    prop_name = f"v_offset_{color_attr.name}"
    current_v = obj.get(prop_name, 0.0)

    # Calculate multipliers
    # V=-80 -> multiplier 0.2, V=0 -> multiplier 1.0, V=+50 -> multiplier 1.5
    current_mult = 1.0 + (current_v / 100.0)
    target_mult = 1.0 + (v_offset / 100.0)

    current_mult = max(0.001, current_mult)  # Avoid division by zero
    target_mult = max(0.0, target_mult)

    # Calculate conversion multiplier (from current state to target state)
    conversion = target_mult / current_mult

    # Apply conversion to all vertex colors
    for i, data in enumerate(color_attr.data):
        c = data.color
        r = min(1.0, max(0.0, c[0] * conversion))
        g = min(1.0, max(0.0, c[1] * conversion))
        b = min(1.0, max(0.0, c[2] * conversion))
        color_attr.data[i].color = (r, g, b, c[3])

    # Store the new V offset
    obj[prop_name] = v_offset

    return True, f"V: {current_v:.0f} → {v_offset:.0f} (x{conversion:.2f})"


def analyze_vertex_colors(obj):
    """Анализировать vertex colors выделенного объекта"""
    if obj is None or obj.type != 'MESH':
        return None

    mesh = obj.data
    if not compat.vcol_list(mesh):
        return None

    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        existing = compat.vcol_list(mesh)
        if existing:
            color_attr = existing[0]

    if color_attr is None:
        return None

    # Collect all colors
    colors = []
    for data in color_attr.data:
        c = data.color
        brightness = (c[0] + c[1] + c[2]) / 3.0
        colors.append({
            'r': c[0], 'g': c[1], 'b': c[2],
            'brightness': brightness
        })

    if not colors:
        return None

    # Calculate statistics
    brightnesses = [c['brightness'] for c in colors]
    min_bright = min(brightnesses)
    max_bright = max(brightnesses)
    avg_bright = sum(brightnesses) / len(brightnesses)

    return {
        'count': len(colors),
        'min_brightness': min_bright,
        'max_brightness': max_bright,
        'avg_brightness': avg_bright,
        'layer_name': color_attr.name
    }


# =============================================================================
# POST-PROCESSING VERTEX COLORS
# =============================================================================

def smooth_vertex_colors(obj, iterations=1, factor=0.5):
    """Сгладить vertex colors между соседними вершинами"""
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    mesh = obj.data
    if not compat.vcol_list(mesh):
        return False, "No vertex colors found!"

    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        return False, "No active color layer!"

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Build vertex -> loop indices mapping and vertex -> color mapping
    # color_attr.data is per-loop (face corner)
    loop_idx = 0
    vert_loops = {}  # vert_index -> [loop_indices]
    for face in bm.faces:
        for vert in face.verts:
            if vert.index not in vert_loops:
                vert_loops[vert.index] = []
            vert_loops[vert.index].append(loop_idx)
            loop_idx += 1

    for iteration in range(iterations):
        # Collect current per-vertex average colors
        vert_colors = {}
        for vi, loops in vert_loops.items():
            r, g, b = 0.0, 0.0, 0.0
            for li in loops:
                c = color_attr.data[li].color
                r += c[0]
                g += c[1]
                b += c[2]
            n = len(loops)
            vert_colors[vi] = (r / n, g / n, b / n)

        # For each vertex, compute smoothed color from neighbors
        smoothed = {}
        for vert in bm.verts:
            vi = vert.index
            if vi not in vert_colors:
                continue
            neighbors = []
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if other.index in vert_colors:
                    neighbors.append(vert_colors[other.index])

            if not neighbors:
                smoothed[vi] = vert_colors[vi]
                continue

            # Average of neighbors
            avg_r = sum(c[0] for c in neighbors) / len(neighbors)
            avg_g = sum(c[1] for c in neighbors) / len(neighbors)
            avg_b = sum(c[2] for c in neighbors) / len(neighbors)

            # Blend: original * (1 - factor) + avg * factor
            orig = vert_colors[vi]
            smoothed[vi] = (
                orig[0] * (1.0 - factor) + avg_r * factor,
                orig[1] * (1.0 - factor) + avg_g * factor,
                orig[2] * (1.0 - factor) + avg_b * factor,
            )

        # Write smoothed colors back to all loops
        for vi, color in smoothed.items():
            for li in vert_loops[vi]:
                c = color_attr.data[li].color
                color_attr.data[li].color = (color[0], color[1], color[2], c[3])

    bm.free()
    return True, f"Smoothed {iterations}x (factor {factor:.2f})"


def adjust_vertex_colors_contrast(obj, contrast=1.0):
    """Применить контраст к vertex colors.
    contrast=1 — без изменений, <1 — меньше контраста, >1 — больше.
    """
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    mesh = obj.data
    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        return False, "No active color layer!"

    # Compute average brightness
    total_r, total_g, total_b = 0.0, 0.0, 0.0
    count = len(color_attr.data)
    if count == 0:
        return True, "No vertex data"
    for data in color_attr.data:
        c = data.color
        total_r += c[0]
        total_g += c[1]
        total_b += c[2]

    avg_r = total_r / count
    avg_g = total_g / count
    avg_b = total_b / count

    # Apply contrast: new = avg + (old - avg) * contrast
    for i, data in enumerate(color_attr.data):
        c = data.color
        r = max(0.0, min(1.0, avg_r + (c[0] - avg_r) * contrast))
        g = max(0.0, min(1.0, avg_g + (c[1] - avg_g) * contrast))
        b = max(0.0, min(1.0, avg_b + (c[2] - avg_b) * contrast))
        color_attr.data[i].color = (r, g, b, c[3])

    return True, f"Contrast: {contrast:.2f}"


def adjust_vertex_colors_brightness(obj, brightness=0.0):
    """Применить яркость к vertex colors. brightness — смещение (-1..+1)."""
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    mesh = obj.data
    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        return False, "No active color layer!"

    for i, data in enumerate(color_attr.data):
        c = data.color
        r = max(0.0, min(1.0, c[0] + brightness))
        g = max(0.0, min(1.0, c[1] + brightness))
        b = max(0.0, min(1.0, c[2] + brightness))
        color_attr.data[i].color = (r, g, b, c[3])

    return True, f"Brightness: {brightness:+.2f}"


def adjust_vertex_colors_gamma(obj, gamma=1.0):
    """Применить гамма-коррекцию к vertex colors.
    gamma=1 — без изменений, <1 — светлее, >1 — темнее.
    """
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    mesh = obj.data
    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        return False, "No active color layer!"

    if gamma <= 0:
        return False, "Gamma must be > 0"

    for i, data in enumerate(color_attr.data):
        c = data.color
        r = pow(max(0.0, c[0]), gamma)
        g = pow(max(0.0, c[1]), gamma)
        b = pow(max(0.0, c[2]), gamma)
        color_attr.data[i].color = (min(1.0, r), min(1.0, g), min(1.0, b), c[3])

    return True, f"Gamma: {gamma:.2f}"


def lift_shadows(obj, strength=0.5):
    """«Подтянуть тени» — pull each loop's brightness toward the
    mesh-wide max by ``strength``. Hue is preserved (colour scaled
    proportionally), so a dark wall stays the same warm/cool tone but
    becomes less dark.

    strength=0 → no-op
    strength=1 → every loop reaches the max → fully uniform brightness
                 (loses the per-face step entirely; not recommended)
    Typical 0.3-0.5 → dark faces noticeably lifted, contrast step kept.

    Operates on the active color attribute (Day or Night). Black loops
    (brightness ~0) are excluded — multiplying 0 by anything stays 0,
    and trying to interpolate hue from pure black is meaningless.
    """
    import numpy as np
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"
    if strength <= 0.0:
        return True, "Strength is zero — nothing to do"

    mesh = obj.data
    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        return False, "No active color layer!"

    n = len(color_attr.data)
    if n == 0:
        return False, "No loops"

    flat = np.empty(n * 4, dtype=np.float32)
    color_attr.data.foreach_get('color', flat)
    flat = flat.reshape(n, 4)

    rgb = flat[:, :3]
    brightness = rgb.mean(axis=1)
    target = float(brightness.max())
    if target <= 1e-6:
        return True, "All colours are black — nothing to lift"

    # Mask out near-black loops (would scale 0×k = 0 anyway).
    valid = brightness > 1e-4
    new_b = brightness + (target - brightness) * float(strength)
    # Per-loop scale to lift brightness while preserving hue.
    scale = np.ones(n, dtype=np.float32)
    scale[valid] = new_b[valid] / brightness[valid]

    rgb_out = rgb * scale[:, None]
    np.clip(rgb_out, 0.0, 1.0, out=rgb_out)
    flat[:, :3] = rgb_out

    color_attr.data.foreach_set('color', flat.reshape(-1))
    return True, f"Lifted shadows: strength={strength:.2f}"


# ── Modulate Color presets ──────────────────────────────────────
# Хардкод значений из ванильного timecyc.dat (EXTRASUNNY_LA),
# чтобы пользователю не нужно было ничего настраивать.
# Источник: pcBuildingVS.hlsl + CPostEffects::ColourFilter
# (gta-reversed-modern).
_MODULATE_PRESETS = {
    'DAY': {
        # Midday — цвет ambient_obj. Сила (mix) задаётся слайдером
        # пользователем. Post-fx тинты пока отключены (pf1a/pf2a=0):
        # аддитивные фуллскрин-overlay из движка после AgX-тонмапа
        # Blender'а уходят в whiteout, поэтому в preview не годятся.
        'ambient': (210/255, 194/255, 182/255),
        'pf1':  (66/255, 66/255, 48/255), 'pf1a': 0.0,
        'pf2':  (166/255, 129/255, 60/255), 'pf2a': 0.0,
    },
    'NIGHT': {
        # Midnight — то же без post-fx.
        'ambient': (220/255, 212/255, 130/255),
        'pf1':  (87/255, 87/255, 87/255), 'pf1a': 0.0,
        'pf2':  (60/255, 121/255, 122/255), 'pf2a': 0.0,
    },
}


def _modulate_preset_values(mode, mix=0.15, contrast=0.0, gamma=1.0):
    """Return shader values for the given preset mode (OFF/DAY/NIGHT).

    Returns: (amb_b, amb_factor, pf1_b, pf1_f, pf2_b, pf2_f, contrast, gamma).
    OFF мод обнуляет ambient/post-fx и сбрасывает contrast/gamma в нейтраль."""
    p = _MODULATE_PRESETS.get(mode)
    if p is None:
        return ((0.0, 0.0, 0.0, 0.0), 0.0,
                (0.0, 0.0, 0.0, 0.0), 0.0,
                (0.0, 0.0, 0.0, 0.0), 0.0,
                0.0, 1.0)
    return ((p['ambient'][0], p['ambient'][1], p['ambient'][2], 0.0), mix,
            (p['pf1'][0],     p['pf1'][1],     p['pf1'][2],     0.0), p['pf1a'],
            (p['pf2'][0],     p['pf2'][1],     p['pf2'][2],     0.0), p['pf2a'],
            contrast, gamma)


# Ноды старого «Modulate»-превью (8 нод). В актуальном графе их быть не
# должно: их наличие = материал из старого .blend, граф надо пересобрать.
# Prelight_Mix / Prelight_VertexColor сюда НЕ входят — это ноды нового
# минимального превью.
PRELIGHT_LEGACY_NODES = (
    "Prelight_Bright", "Prelight_Ambient", "Prelight_PostFx1",
    "Prelight_PostFx2", "Prelight_BrightContrast", "Prelight_Gamma",
)


# ── Визуальная коррекция превью прилайта (ТОЛЬКО вьюпорт) ─────────────
# III и VC хранят очень тёмный prelight → в блендере он почти чёрный.
# Ноды Prelight_ViewBC (Bright/Contrast) + Prelight_ViewGamma встраиваются
# на путь vertex-color ПЕРЕД умножением на текстуру и вытягивают его
# ВИЗУАЛЬНО. На ЭКСПОРТ НЕ ВЛИЯЮТ — экспорт читает реальные vertex colors и
# текстуру мимо этих нод (dff_export идёт через Prelight_Mix.A/vcol-слой).
# Это постоянная часть графа: нейтраль (0,0,1) = pass-through, поэтому
# структура не зависит от значений — их крутят ползунки без пересборки.
#
# (bright, contrast, gamma, saturation) per-game. Дефолты, что грузятся в
# ползунки при смене игры; ползунками можно крутить живьём поверх.
PRELIGHT_VIEW_NEUTRAL = (0.0, 0.0, 1.0, 1.0)
PRELIGHT_VIEW_CORRECTION = {
    'SA':  (0.004, 0.0, 1.0, 1.0),
    'VC':  (0.004, 0.0, 1.0, 1.0),
    'III': (0.004, 0.0, 1.0, 1.0),
}


def _current_view_correction(scene):
    """(bright, contrast, gamma, saturation) для превью — из ползунков сцены
    (их дефолты грузятся из PRELIGHT_VIEW_CORRECTION при смене игры)."""
    ins = getattr(scene, 'inu_settings', None) if scene is not None else None
    if ins is None:
        return PRELIGHT_VIEW_NEUTRAL
    return (float(getattr(ins, 'prelight_view_bright', 0.0)),
            float(getattr(ins, 'prelight_view_contrast', 0.0)),
            float(getattr(ins, 'prelight_view_gamma', 1.0)),
            float(getattr(ins, 'prelight_view_saturation', 1.0)))


def _set_view_correction_values(bc, gm, sat, bright, contrast, gamma, saturation):
    try:
        bc.inputs['Bright'].default_value = bright
        bc.inputs['Contrast'].default_value = contrast
        gm.inputs['Gamma'].default_value = gamma
        sat.inputs['Saturation'].default_value = saturation
    except Exception:                          # noqa: BLE001
        pass


def _prelight_color_source(mat, nodes, vc_node):
    """Что питает цепочку коррекции — socket ноды Prelight_VertexColor.

    Врезку смеси Day↔Night делает timecyc_prelight.wire_material(), которую
    setup_prelight_preview зовёт следом (перевязывает вход Prelight_ViewBC).
    Раньше здесь была попытка врезать её и тут — через timecyc_prelight.
    is_enabled(), которой НЕ СУЩЕСТВУЕТ: вызов падал AttributeError, гасился
    except'ом и всё равно возвращал этот же socket, попутно вешая исключение
    и лишнюю перевязку на каждый материал. Убрано."""
    if vc_node is None:
        return None
    return vc_node.outputs['Color']


def _ensure_view_correction_nodes(nodes, links, vc_node, mix_node, correction,
                                  color_source=None):
    """Создать (если нет) и связать ноды визуальной коррекции на пути
    vertex-color → ViewBC → ViewGamma → ViewSat → Mix.B. Возвращает (bc,gm,sat)."""
    bright, contrast, gamma, saturation = correction
    bc = nodes.get("Prelight_ViewBC")
    if bc is None:
        bc = nodes.new('ShaderNodeBrightContrast')
        bc.name = "Prelight_ViewBC"
        bc.label = "Prelight View B/C (превью)"
        bc.location = (vc_node.location.x + 200, vc_node.location.y)
    gm = nodes.get("Prelight_ViewGamma")
    if gm is None:
        gm = nodes.new('ShaderNodeGamma')
        gm.name = "Prelight_ViewGamma"
        gm.label = "Prelight View Gamma (превью)"
        gm.location = (vc_node.location.x + 400, vc_node.location.y)
    sat = nodes.get("Prelight_ViewSat")
    if sat is None:
        sat = nodes.new('ShaderNodeHueSaturation')
        sat.name = "Prelight_ViewSat"
        sat.label = "Prelight View Saturation (превью)"
        sat.location = (vc_node.location.x + 600, vc_node.location.y)
    _set_view_correction_values(bc, gm, sat, bright, contrast, gamma, saturation)
    links.new(color_source or vc_node.outputs['Color'], bc.inputs['Color'])
    links.new(bc.outputs['Color'], gm.inputs['Color'])
    links.new(gm.outputs['Color'], sat.inputs['Color'])
    links.new(sat.outputs['Color'], compat.mix_input_b(mix_node))
    return bc, gm, sat


def apply_prelight_view_correction(scene=None):
    """Live-обновление ЗНАЧЕНИЙ коррекции во всех материалах с превью —
    для ползунков (без пересборки графа/перекомпиляции шейдера).
    Returns кол-во обновлённых материалов."""
    if scene is None:
        scene = getattr(bpy.context, 'scene', None)
    if scene is None:
        return 0
    bright, contrast, gamma, saturation = _current_view_correction(scene)
    count = 0
    for mat in bpy.data.materials:
        if not mat or not getattr(mat, 'use_nodes', False):
            continue
        nt = mat.node_tree
        if nt is None:
            continue
        bc = nt.nodes.get("Prelight_ViewBC")
        gm = nt.nodes.get("Prelight_ViewGamma")
        sat = nt.nodes.get("Prelight_ViewSat")
        if bc is None or gm is None or sat is None:
            continue
        _set_view_correction_values(bc, gm, sat, bright, contrast, gamma, saturation)
        count += 1
    return count


def load_view_correction_for_game(scene, game):
    """Загрузить per-game дефолт коррекции в ползунки и применить."""
    ins = getattr(scene, 'inu_settings', None) if scene is not None else None
    if ins is None:
        return
    bright, contrast, gamma, saturation = PRELIGHT_VIEW_CORRECTION.get(
        game, PRELIGHT_VIEW_NEUTRAL)
    try:
        ins.prelight_view_bright = bright
        ins.prelight_view_contrast = contrast
        ins.prelight_view_gamma = gamma
        ins.prelight_view_saturation = saturation
    except Exception:                          # noqa: BLE001
        pass
    apply_prelight_view_correction(scene)




# Имя инстанса группы Day↔Night — ЕДИНЫЙ источник в timecyc_prelight.NODE_NAME
# (его ставит та же timecyc_prelight). Импортируем, а не дублируем литерал:
# idempotency-проверка _preview_graph_is_current сверяет узел по этому имени —
# разъедься они, и каждый объект перевязывал бы общий материал (recompile-шторм).
# timecyc_prelight не импортирует prelight, поэтому цикла нет.
from .timecyc_prelight import NODE_NAME as PRELIGHT_DAYNIGHT_NODE
PRELIGHT_FOG_NODE = "Prelight_GameFog"


def _preview_graph_is_current(nodes, principled, base_color,
                              vc_node, mix_node, color_name,
                              mat_game_look=False):
    """True, если граф превью в материале УЖЕ собран как надо.

    Нужно, чтобы `setup_prelight_preview` был идемпотентным: материалы в
    GTA-сценах общие на сотни объектов, и без этой проверки каждый объект
    заново перевязывал links в одном и том же material.node_tree — каждая
    правка помечает дерево грязным, и EEVEE перекомпилирует шейдер. На карте
    в 1500+ объектов это выливалось в бесконечную «загрузку нодов»."""
    if vc_node is None or mix_node is None:
        return False
    if any(nodes.get(nm) is not None for nm in PRELIGHT_LEGACY_NODES):
        return False   # остатки старого modulate-графа — пересобрать

    if hasattr(vc_node, 'layer_name'):
        if vc_node.layer_name != color_name:
            return False
    elif hasattr(vc_node, 'attribute_name'):
        if vc_node.attribute_name != color_name:
            return False
    else:
        return False

    # Mix.B должен приходить через ноды визуальной коррекции:
    #   vc → Prelight_ViewBC → Prelight_ViewGamma → Prelight_ViewSat → Mix.B.
    # Их отсутствие/прямой vc→Mix.B (старый граф) → пересобрать, чтобы
    # коррекция встроилась.
    b = compat.mix_input_b(mix_node)
    bc = nodes.get("Prelight_ViewBC")
    gm = nodes.get("Prelight_ViewGamma")
    sat = nodes.get("Prelight_ViewSat")
    if bc is None or gm is None or sat is None:
        return False
    if not b.is_linked or b.links[0].from_node is not sat:
        return False
    sat_in = sat.inputs['Color']
    if not sat_in.is_linked or sat_in.links[0].from_node is not gm:
        return False
    gm_in = gm.inputs['Color']
    if not gm_in.is_linked or gm_in.links[0].from_node is not bc:
        return False
    bc_in = bc.inputs['Color']
    if not bc_in.is_linked:
        return False
    bc_src = bc_in.links[0].from_node
    # В режиме «прилайт по времени суток» цвет приходит не из vc_node, а
    # из общей группы Day↔Night — это тоже актуальный граф.
    if bc_src is not vc_node and bc_src.name != PRELIGHT_DAYNIGHT_NODE:
        return False
    if mat_game_look:
        # «Как в игре»: цвет идёт в Emission (через туман, если он есть),
        # а Base Color намеренно пуст — это тоже собранный граф.
        emit = compat.principled_emission_input(principled)
        if emit is None or not emit.is_linked:
            return False
        emit_src = emit.links[0].from_node
        if emit_src is not mix_node and emit_src.name != PRELIGHT_FOG_NODE:
            return False
    elif not base_color.is_linked or base_color.links[0].from_node is not mix_node:
        return False

    # Mix.A без текстуры допустим только если текстуры в графе и правда нет
    # (иначе — материал сменили/починили, надо перевязать).
    a = compat.mix_input_a(mix_node)
    if not a.is_linked and _find_base_image_socket(nodes, principled) is not None:
        return False
    return True


def _preview_graph_is_absent(nodes, principled, base_color,
                            vc_node, mix_node, mat):
    """True, если в материале уже нет ни наших нод, ни следов превью —
    выключать нечего. Парная к `_preview_graph_is_current` проверка,
    чтобы повторное «выключить» не дёргало общий материал по кругу."""
    if vc_node is not None or mix_node is not None:
        return False
    if any(nodes.get(nm) is not None for nm in PRELIGHT_LEGACY_NODES):
        return False
    if 'prelight_alpha_mode' in mat or 'prelight_orig_blend' in mat:
        return False
    if nodes.get("Prelight_AlphaMult") is not None:
        return False
    # Base Color должен уже вести к текстуре (или ни к чему, если её нет).
    if not base_color.is_linked and \
            _find_base_image_socket(nodes, principled) is not None:
        return False
    return True


def setup_prelight_preview(obj, enable=True):
    """Превью прилайта: умножает vertex colors на текстуру в Material Preview.

    Минимальный граф — 2 ноды на материал:
        Attribute(vertex color) → MixRGB(Multiply) ×текстура → Base Color.
    Лёгкий для компиляции шейдера, поэтому переключение моделей не тормозит.
    (Старый режим «Modulate» с 8 нодами убран; оставшиеся modulate-ноды из
    старых .blend здесь вычищаются.)

    Идемпотентно: материал, уже находящийся в нужном состоянии, не трогается
    вовсе — ни одной правки нод/links, значит и ни одной перекомпиляции
    шейдера. Это принципиально для карт, где один материал висит на сотнях
    объектов и функция вызывается для каждого из них.
    """
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    mesh = obj.data
    if not compat.vcol_list(mesh):
        return False, "No vertex colors on object!"

    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        color_attr = compat.vcol_list(mesh)[0]
    color_name = color_attr.name

    # Устаревшие modulate-ноды — могли остаться в файлах со старым превью.
    _LEGACY = PRELIGHT_LEGACY_NODES

    # Визуальная коррекция (яркость/контраст/гамма) — одна на всю сцену.
    view_corr = _current_view_correction(getattr(bpy.context, 'scene', None))

    modified_count = 0

    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if not mat or not mat.use_nodes:
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        principled = next(
            (n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if principled is None:
            continue
        base_color = principled.inputs.get('Base Color')
        if base_color is None:
            continue

        vc_node = nodes.get("Prelight_VertexColor")
        mix_node = nodes.get("Prelight_Mix")

        # Уже в нужном состоянии — не трогаем граф (см. докстринг).
        if enable:
            if _preview_graph_is_current(nodes, principled, base_color,
                                         vc_node, mix_node, color_name,
                                         mat_game_look=bool(mat.get('inu_tc_game_look'))):
                continue
        else:
            if _preview_graph_is_absent(nodes, principled, base_color,
                                        vc_node, mix_node, mat):
                continue

        if enable:
            # Текстура: сохранённый вход Mix.A (если превью уже стоит), иначе
            # то, что сейчас идёт в Base Color (но не наш Mix).
            tex_socket = None
            if mix_node is not None:
                ma = compat.mix_input_a(mix_node)
                if ma.is_linked:
                    tex_socket = ma.links[0].from_socket
            if tex_socket is None and base_color.is_linked:
                src_node = base_color.links[0].from_node
                if src_node is not mix_node:
                    tex_socket = base_color.links[0].from_socket
            if tex_socket is None:
                # Фоллбэк для старых/битых графов: текстура висит отключённой
                # (Base Color ни к чему не привязан). Берём её прямо из ноды
                # Image Texture — иначе превью = vertex color × белый, без
                # текстуры (как на скрине старой сцены).
                tex_socket = _find_base_image_socket(nodes, principled)

            if vc_node is None:
                vc_node = _make_color_attr_node(nodes, color_name)
                vc_node.name = "Prelight_VertexColor"
                vc_node.label = "Prelight"
                vc_node.location = (principled.location.x - 600,
                                    principled.location.y - 220)
            else:
                if hasattr(vc_node, 'layer_name'):
                    vc_node.layer_name = color_name
                elif hasattr(vc_node, 'attribute_name'):
                    vc_node.attribute_name = color_name

            if mix_node is None:
                mix_node = nodes.new(compat.MIX_NODE_TYPE)
                mix_node.name = "Prelight_Mix"
                mix_node.label = "Prelight Multiply"
                compat.setup_mix_rgba_node(mix_node, blend='MULTIPLY')
                mix_node.location = (principled.location.x - 300,
                                     principled.location.y)
                compat.mix_input_factor(mix_node).default_value = 1.0

            # A = текстура, B = vertex color (через ноды визуальной коррекции)
            if tex_socket is not None:
                links.new(tex_socket, compat.mix_input_a(mix_node))
            else:
                compat.mix_input_a(mix_node).default_value = (1.0, 1.0, 1.0, 1.0)
            # vc → Prelight_ViewBC → Prelight_ViewGamma → Mix.B.
            # Ноды коррекции — постоянная часть графа (нейтраль = pass-through),
            # только вьюпорт. Значения потом крутят ползунки.
            _ensure_view_correction_nodes(
                nodes, links, vc_node, mix_node, view_corr,
                color_source=_prelight_color_source(mat, nodes, vc_node))

            # Mix → Base Color
            for lnk in list(base_color.links):
                links.remove(lnk)
            links.new(compat.mix_output_result(mix_node), base_color)

            # Вычистить устаревшие modulate-ноды.
            for nm in _LEGACY:
                n = nodes.get(nm)
                if n is not None:
                    nodes.remove(n)

            # Режим тайм-цикла («как в игре», туман, Day↔Night) дособерёт
            # свою часть: без этого включение превью на объекте сбивало бы
            # игровой вид обратно в PBR.
            try:
                from . import timecyc_prelight
                timecyc_prelight.wire_material(mat)
            except Exception as exc:
                # Не глушим молча: сбой врезки Day↔Night / игрового вида —
                # это как раз «материал стал чёрным без причины», должно быть
                # видно в системной консоли.
                print("[INU timecyc] wire_material(%s): %s" % (mat.name, exc))
            modified_count += 1

        else:
            # Выключение: вернуть текстуру на Base Color и удалить наши ноды.
            tex_socket = None
            if mix_node is not None:
                ma = compat.mix_input_a(mix_node)
                if ma.is_linked:
                    tex_socket = ma.links[0].from_socket
            if tex_socket is None:
                tex_socket = _find_base_image_socket(nodes, principled)
            for lnk in list(base_color.links):
                links.remove(lnk)
            if tex_socket is not None:
                links.new(tex_socket, base_color)

            # Инстанс группы Day↔Night ставит tools/timecyc_prelight;
            # без превью он висел бы в материале ни к чему не подключён.
            for nm in (PRELIGHT_DAYNIGHT_NODE, PRELIGHT_FOG_NODE):
                extra = nodes.get(nm)
                if extra is not None:
                    nodes.remove(extra)
            # Игровой unlit-вид держится на Emission — вернуть материал
            # в PBR обязаны здесь же, иначе он останется светящимся.
            if mat.get('inu_tc_game_look'):
                emit = compat.principled_emission_input(principled)
                if emit is not None:
                    for lnk in list(emit.links):
                        links.remove(lnk)
                    emit.default_value = (0.0, 0.0, 0.0, 1.0)
                strength = principled.inputs.get('Emission Strength')
                if strength is not None and not strength.is_linked:
                    strength.default_value = float(mat.get('inu_tc_prev_emit', 1.0))
                # Вернуть Base Color, обнулённый game-look'ом. Без этого у
                # бестекстурного материала (relink выше нечего было цеплять)
                # Base Color остаётся чёрным, экспорт пишет цвет материала = 0,
                # и с флагом MODULATE прилайт умножается на ноль → чёрная модель.
                if not base_color.is_linked:
                    prev_base = mat.get('inu_tc_prev_base')
                    if prev_base is not None:
                        base_color.default_value = tuple(prev_base)
                    elif tuple(base_color.default_value)[:3] == (0.0, 0.0, 0.0):
                        # Старый .blend без сохранённого цвета: не оставлять
                        # чёрным — белый нейтрален для prelit×MODULATE.
                        base_color.default_value = (1.0, 1.0, 1.0, 1.0)
                for key in ('inu_tc_game_look', 'inu_tc_prev_emit',
                            'inu_tc_prev_base'):
                    if key in mat:
                        del mat[key]

            # Legacy alpha cleanup (Prelight_AlphaMult / prelight_alpha_mode).
            alpha_mode = mat.get('prelight_alpha_mode')
            alpha_input = principled.inputs.get('Alpha')
            alpha_mult = nodes.get("Prelight_AlphaMult")
            if alpha_mode == 'mult' and alpha_mult and alpha_input:
                orig_socket = None
                if alpha_mult.inputs[0].is_linked:
                    orig_socket = alpha_mult.inputs[0].links[0].from_socket
                for lnk in list(alpha_input.links):
                    links.remove(lnk)
                if orig_socket:
                    links.new(orig_socket, alpha_input)
                nodes.remove(alpha_mult)
            elif alpha_mode == 'direct' and alpha_input:
                for lnk in list(alpha_input.links):
                    if vc_node is not None and lnk.from_node == vc_node:
                        links.remove(lnk)
                alpha_input.default_value = 1.0
            if 'prelight_alpha_mode' in mat:
                del mat['prelight_alpha_mode']
            if 'prelight_orig_blend' in mat:
                if hasattr(mat, 'blend_method'):
                    try:
                        mat.blend_method = mat['prelight_orig_blend']
                    except Exception:
                        mat.blend_method = 'OPAQUE'
                del mat['prelight_orig_blend']

            # Удалить наши ноды (минимальные + коррекция + устаревшие modulate).
            for nm in ("Prelight_VertexColor", "Prelight_Mix",
                       "Prelight_ViewBC", "Prelight_ViewGamma",
                       "Prelight_ViewSat") + _LEGACY:
                n = nodes.get(nm)
                if n is not None:
                    nodes.remove(n)
            modified_count += 1

    # Флаг состояния на каждом материале — кнопки UI смотрят на него.
    # Пишем только если значение реально меняется: запись ID-свойства метит
    # материал грязным, а на карте один материал общий для сотен объектов.
    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if mat is None:
            continue
        if enable:
            if not mat.get('prelight_preview_active'):
                mat['prelight_preview_active'] = True
        else:
            try:
                if 'prelight_preview_active' in mat:
                    del mat['prelight_preview_active']
            except Exception:
                mat['prelight_preview_active'] = False

    if enable:
        return True, f"Prelight preview enabled on {modified_count} materials"
    return True, f"Prelight preview disabled on {modified_count} materials"


def _make_color_attr_node(nodes, color_name):
    """Create a vertex-colour reader node (Attribute on 4.0+, Vertex Color
    below) wired to ``color_name``. Returns the node — caller positions
    it and reads ``.outputs['Color']`` / ``.outputs['Alpha']``."""
    if bpy.app.version >= (4, 0, 0):
        node = nodes.new('ShaderNodeAttribute')
        node.attribute_type = 'GEOMETRY'
        node.attribute_name = color_name
    else:
        node = nodes.new('ShaderNodeVertexColor')
        node.layer_name = color_name
    return node


def _find_base_image_socket(nodes, principled):
    """Найти выход 'Color' основной текстуры материала — даже если она сейчас
    НЕ подключена (старые/битые графы, где текстура висит отдельно).

    Предпочтение: TEX_IMAGE, идущая в Base Color (если связь ещё цела), иначе
    первая TEX_IMAGE, имя которой не похоже на env/bump/spec/refl-карту, иначе
    любая первая TEX_IMAGE. Возвращает socket или None."""
    def _color_out(n):
        out = n.outputs.get('Color')
        if out is None and len(n.outputs):
            out = n.outputs[0]
        return out

    # 1) то, что прямо сейчас в Base Color
    if principled is not None:
        bc = principled.inputs.get('Base Color')
        if bc is not None and bc.is_linked:
            src = bc.links[0].from_node
            if src.type == 'TEX_IMAGE':
                return _color_out(src)

    tex_nodes = [n for n in nodes if n.type == 'TEX_IMAGE']
    if not tex_nodes:
        return None
    # 2) первая «не служебная» текстура
    skip = ('env', 'bump', 'spec', 'refl', 'norm', 'dual')
    for n in tex_nodes:
        nm = ((n.image.name if n.image else '') + ' ' + n.name).lower()
        if not any(s in nm for s in skip):
            return _color_out(n)
    # 3) хоть какая-то
    return _color_out(tex_nodes[0])


def _enable_alpha_on_material(mat, color_name):
    """Wire vertex-colour ALPHA of layer ``color_name`` into ``mat``'s
    Principled BSDF Alpha (× any existing texture alpha) and flip the
    material to a blended draw mode, so per-vertex transparency shows in
    the viewport.

    Idempotent and side-effect-isolated: own node namespace ``AlphaView_*``
    + bookkeeping keys (``alphaview_mode``/``alphaview_orig_blend``/
    ``alpha_preview_active``). If the Prelight preview already drives Alpha
    (``prelight_alpha_mode``) we leave it and just mark ``shared``. Shared
    by the manual toggle (`setup_alpha_preview`) and the import-time
    auto-viz (`wire_mesh_vertex_alpha`). Returns True if the material was
    handled (already-wired counts as handled)."""
    if not mat or not mat.use_nodes:
        return False
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    principled = next(
        (n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not principled:
        return False
    alpha_input = principled.inputs.get('Alpha')
    if alpha_input is None:
        return False

    # Alpha is now owned solely by this preview — the Prelight preview no
    # longer touches the Alpha input, so there's no `prelight_alpha_mode`
    # to defer to. Clean up any leftover legacy Prelight alpha wiring so it
    # doesn't double-drive Alpha (older .blend files toggled before the
    # systems were decoupled).
    if mat.get('prelight_alpha_mode') is not None:
        legacy_mult = nodes.get("Prelight_AlphaMult")
        if legacy_mult is not None:
            for lnk in list(alpha_input.links):
                links.remove(lnk)
            nodes.remove(legacy_mult)
        else:
            for lnk in list(alpha_input.links):
                links.remove(lnk)
        del mat['prelight_alpha_mode']

    # Already wired by us — skip so we don't churn the node tree (and
    # trigger a redundant EEVEE shader recompile) on a no-op.
    if (mat.get('alpha_preview_active')
            and mat.get('alphaview_mode') in ('direct', 'mult')):
        return True

    vc_node = nodes.get("AlphaView_VC")
    mult_node = nodes.get("AlphaView_Mult")

    if not vc_node:
        vc_node = _make_color_attr_node(nodes, color_name)
        vc_node.name = "AlphaView_VC"
        vc_node.label = "Vertex Alpha"
        vc_node.location = (principled.location.x - 350,
                            principled.location.y - 400)
    else:
        if hasattr(vc_node, 'attribute_name'):
            vc_node.attribute_name = color_name
        elif hasattr(vc_node, 'layer_name'):
            vc_node.layer_name = color_name

    if 'Alpha' not in vc_node.outputs:
        return False  # node type without an Alpha output — bail safely

    # Remember the draw mode once so disable can restore it, then switch to
    # the project's alpha standard: Метод рендеринга Смешанный + Перекрытие
    # прозрачности ВЫКЛ. Через compat — на 4.2+ (EEVEE Next) запись одного
    # blend_method ничего не даёт, и превью вершинной альфы не появлялось.
    if 'alphaview_orig_blend' not in mat:
        mat['alphaview_orig_blend'] = compat.blend_method_of(mat)
        mat['alphaview_orig_overlap'] = compat.transparency_overlap(mat)
    compat.make_material_alpha(mat)

    if alpha_input.is_linked:
        # Texture alpha already feeds Alpha — multiply it by the vertex
        # alpha so both contribute (tex_a × vc_a → Alpha).
        orig_socket = alpha_input.links[0].from_socket
        if not mult_node:
            mult_node = nodes.new('ShaderNodeMath')
            mult_node.name = "AlphaView_Mult"
            mult_node.label = "Vertex Alpha Mult"
            mult_node.operation = 'MULTIPLY'
            mult_node.location = (principled.location.x - 180,
                                  principled.location.y - 400)
        for lnk in list(alpha_input.links):
            links.remove(lnk)
        links.new(orig_socket, mult_node.inputs[0])
        links.new(vc_node.outputs['Alpha'], mult_node.inputs[1])
        links.new(mult_node.outputs[0], alpha_input)
        mat['alphaview_mode'] = 'mult'
    else:
        links.new(vc_node.outputs['Alpha'], alpha_input)
        mat['alphaview_mode'] = 'direct'

    mat['alpha_preview_active'] = True
    return True


def _disable_alpha_on_material(mat):
    """Undo :func:`_enable_alpha_on_material` on one material: restore the
    original Alpha source + draw mode, drop the bookkeeping keys, and FULLY
    REMOVE the ``AlphaView_*`` nodes so the graph is left clean (no orphan
    nodes lingering after the preview is turned off). Returns True if any
    AlphaView node/bookkeeping was found and removed.

    Earlier this kept the nodes in place for a «cheap re-enable»; that left
    dead nodes in materials whose vertex alpha was later erased. Re-enable
    just recreates the 1–2 nodes anyway, so removal is the right default."""
    if not mat or not mat.use_nodes:
        return False
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    principled = next(
        (n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not principled:
        return False
    alpha_input = principled.inputs.get('Alpha')
    if alpha_input is None:
        return False

    vc_node = nodes.get("AlphaView_VC")
    mult_node = nodes.get("AlphaView_Mult")
    mode = mat.get('alphaview_mode')

    # Nothing of ours here — report «not handled» so callers can count.
    if (vc_node is None and mult_node is None
            and mode is None and 'alpha_preview_active' not in mat):
        return False

    if mode == 'mult' and mult_node:
        orig_socket = None
        if mult_node.inputs[0].is_linked:
            orig_socket = mult_node.inputs[0].links[0].from_socket
        for lnk in list(alpha_input.links):
            links.remove(lnk)
        if orig_socket:
            links.new(orig_socket, alpha_input)
    elif mode == 'direct':
        for lnk in list(alpha_input.links):
            if vc_node is not None and lnk.from_node == vc_node:
                links.remove(lnk)
        alpha_input.default_value = 1.0

    # Physically delete our nodes. Removing a node also drops any remaining
    # links to it, so do this AFTER restoring the original alpha wiring.
    for n in (mult_node, vc_node):
        if n is not None:
            try:
                nodes.remove(n)
            except Exception:
                pass

    # Safety: if Alpha ended up driven by nothing, make the material opaque
    # again rather than leaving a stale 0 default (invisible material).
    if not alpha_input.is_linked and alpha_input.default_value <= 0.0:
        alpha_input.default_value = 1.0

    # Restore draw mode only if WE changed it (shared mode left it to the
    # Prelight preview, which restores it on its own toggle).
    if mode != 'shared' and 'alphaview_orig_blend' in mat:
        prev = mat['alphaview_orig_blend']
        if prev not in ('OPAQUE', 'CLIP', 'HASHED', 'BLEND'):
            prev = 'OPAQUE'
        compat.set_blend_method(mat, prev)
        compat.set_transparency_overlap(
            mat, bool(mat.get('alphaview_orig_overlap', False)))
    for key in ('alphaview_mode', 'alphaview_orig_blend',
                'alphaview_orig_overlap', 'alpha_preview_active'):
        if key in mat:
            del mat[key]
    return True


def cleanup_orphan_alpha_nodes(context=None):
    """The «check»: walk all scene meshes and remove ``AlphaView_*`` nodes
    from every material that still carries them but is no longer used by ANY
    mesh with real per-vertex alpha (Day/Night layer < 255).

    Materials shared between a transparent and an opaque mesh are kept (they
    are still needed by the transparent one). Returns the number of
    materials cleaned. Safe to call any time — idempotent."""
    ctx = context or bpy.context

    # Materials still needed: used by at least one slot whose own faces fade
    # (per-slot, not per-mesh — an opaque slot sharing a mesh with a faded
    # one must NOT keep its nodes).
    needed = set()
    for obj in ctx.scene.objects:
        if obj.type != 'MESH' or obj.data is None:
            continue
        layer = _mesh_vertex_alpha_layer(obj.data)
        if layer is None:
            continue
        alpha_idx = _alpha_material_indices(obj.data, layer)
        for i, mat_slot in enumerate(obj.material_slots):
            if i in alpha_idx and mat_slot.material is not None:
                needed.add(mat_slot.material.name)

    purged = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        nodes = mat.node_tree.nodes
        has_nodes = (nodes.get("AlphaView_VC") is not None
                     or nodes.get("AlphaView_Mult") is not None
                     or 'alpha_preview_active' in mat)
        if not has_nodes or mat.name in needed:
            continue
        if _disable_alpha_on_material(mat):
            purged += 1
    return purged


def _alpha_material_indices(mesh, layer_name, threshold=0.999):
    """Set of ``material_index`` values whose FACES actually carry alpha
    ``< threshold`` on ``layer_name``.

    This is what stops nodes landing on the wrong slot: a mesh can mix a
    faded material (foliage, glass) with a fully-opaque one, and earlier we
    wired EVERY slot whenever the mesh had any alpha anywhere. Now we wire
    only the slots whose own polygons fade. Empty set → no slot needs it."""
    attr = compat.vcol_get(mesh, layer_name)
    data = getattr(attr, 'data', None) if attr else None
    n = len(data) if data else 0
    if n == 0:
        return set()
    import numpy as np
    flat = np.empty(n * 4, dtype=np.float32)
    try:
        data.foreach_get('color', flat)
    except Exception:
        return set()
    alpha = flat[3::4]
    na = len(alpha)
    domain = getattr(attr, 'domain', 'CORNER')
    nmats = max(1, len(mesh.materials))
    # FastMesh (Plumber и пр. нестандартные меши) не даёт доступа к
    # mesh.polygons → пер-слотовую проверку сделать нельзя; заводим альфу
    # на ВСЕ слоты (грубо, но работает и не падает).
    try:
        polys = mesh.polygons
        if len(polys) == 0:
            return set(range(nmats))
    except Exception:
        return set(range(nmats))
    result = set()
    for poly in polys:
        mi = poly.material_index
        if mi in result:
            continue
        if domain == 'POINT':
            idxs = poly.vertices
        else:  # CORNER — indexed by loop
            idxs = range(poly.loop_start, poly.loop_start + poly.loop_total)
        for i in idxs:
            if i < na and alpha[i] < threshold:
                result.add(mi)
                break
        if len(result) >= nmats:
            break
    return result


def setup_alpha_preview(obj, enable=True, color_name=None):
    """Toggle a viewport-only preview of vertex-colour ALPHA, independent
    of the RGB Prelight preview. See :func:`_enable_alpha_on_material`.

    ``color_name`` selects the layer; ``None`` follows the active colour
    attribute (so the preview tracks the Day/Night selector), falling back
    to "Day" then the first layer. Returns ``(ok: bool, message: str)``.

    On enable, only material slots whose OWN faces fade are wired
    (per-slot check via :func:`_alpha_material_indices`) — opaque slots on
    a mixed mesh are left untouched."""
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    mesh = obj.data
    if not compat.vcol_list(mesh):
        return False, "No vertex colors on object!"

    if color_name is None:
        color_attr = compat.vcol_active(mesh)
        if color_attr is None:
            color_attr = compat.vcol_get(mesh, "Day") or compat.vcol_list(mesh)[0]
        color_name = color_attr.name

    modified_count = 0
    if enable:
        alpha_idx = _alpha_material_indices(mesh, color_name)
        for i, mat_slot in enumerate(obj.material_slots):
            if i not in alpha_idx:
                continue  # this slot's faces are opaque — don't wire it
            if _enable_alpha_on_material(mat_slot.material, color_name):
                modified_count += 1
    else:
        for mat_slot in obj.material_slots:
            if _disable_alpha_on_material(mat_slot.material):
                modified_count += 1

    if enable:
        return True, f"Vertex-alpha preview enabled on {modified_count} materials"
    return True, f"Vertex-alpha preview disabled on {modified_count} materials"


def _mesh_vertex_alpha_layer(mesh, threshold=0.999):
    """Name of a colour attribute that carries REAL per-vertex alpha (any
    value < ``threshold``), or ``None`` if the mesh is fully opaque.
    ``threshold`` defaults just under 1.0 so only byte 255 (→ exactly 1.0)
    counts as opaque; byte 254 (≈0.996) and below count as alpha.

    Проверяем Day/Night В ПЕРВУЮ ОЧЕРЕДЬ (канонические prelit-слои), а затем
    ЛЮБОЙ другой цветовой атрибут — модели часто хранят альфу в слое с иным
    именем (например `vertex_alpha`), и раньше такие не находились вовсе.

    This is the gate that keeps the scene-wide preview off solid map
    geometry: a mesh whose every colour attribute is all-255 alpha returns
    None and is never wired. Only models that actually fade — foliage,
    fences, glass, LOD edges — come back with a layer name."""
    import numpy as np
    # Порядок проверки: Day, Night, затем все остальные атрибуты.
    names = []
    for n in ("Day", "Night"):
        if compat.vcol_get(mesh, n):
            names.append(n)
    try:
        for a in compat.vcol_list(mesh):
            if a.name not in names:
                names.append(a.name)
    except Exception:
        pass
    for name in names:
        attr = compat.vcol_get(mesh, name)
        data = getattr(attr, 'data', None) if attr else None
        n = len(data) if data else 0
        if n == 0:
            continue
        flat = np.empty(n * 4, dtype=np.float32)
        try:
            data.foreach_get('color', flat)
        except Exception:
            continue
        if float(flat[3::4].min()) < threshold:
            return name
    return None


def scene_vertex_alpha_objects(context=None):
    """``[(obj, layer_name), …]`` for every mesh in the scene that has
    real vertex alpha (see :func:`_mesh_vertex_alpha_layer`). The
    scene-wide «Альфа вершин» toggle drives exactly this set — found
    automatically, so the user never has to hand-select the transparent
    models out of a whole map."""
    ctx = context or bpy.context
    out = []
    for obj in ctx.scene.objects:
        if obj.type != 'MESH' or obj.data is None:
            continue
        layer = _mesh_vertex_alpha_layer(obj.data)
        if layer:
            out.append((obj, layer))
    return out


def wire_mesh_vertex_alpha(mesh, color_name="Day"):
    """Import-time auto-visualisation of vertex alpha — wire every material
    on ``mesh`` so a model's per-vertex transparency is visible right after
    import on EVERY path (single DFF, map/IPL, IMG, library) since they all
    funnel through ``_build_mesh``.

    Uses the same ``AlphaView_*`` mechanism as the manual «Альфа вершин»
    toggle, so the button reflects the state and can switch it off.
    Idempotent — safe on cached/shared materials reused across many map
    models. Returns the number of materials wired."""
    n = 0
    for mat in mesh.materials:
        if _enable_alpha_on_material(mat, color_name):
            n += 1
    return n


def apply_modulate_preview(scene=None):
    """Push Modulate Color preview values into every material that has a
    Prelight_Ambient node.

    Сценарий: пользователь крутит slider/color-picker → надо
    мгновенно обновить ambient во всех уже настроенных материалах
    без переотрисовки графа. Дешевле чем повторно вызывать
    setup_prelight_preview на каждом меше.

    Returns: (count, color_used) для отчёта в UI/коллбэке.
    """
    if scene is None:
        scene = getattr(bpy.context, 'scene', None)
    if scene is None:
        return 0, (0.0, 0.0, 0.0)

    mode = getattr(scene.inu_settings, 'gtatools_modulate_mode', 'OFF')
    mix = float(getattr(scene.inu_settings, 'gtatools_modulate_mix', 0.15))
    contrast = float(getattr(scene.inu_settings, 'gtatools_modulate_contrast', 0.0))
    gamma = float(getattr(scene.inu_settings, 'gtatools_modulate_gamma', 1.0))
    (amb_b, amb_factor, pf1_b, pf1_f, pf2_b, pf2_f,
     bc_contrast, gm_gamma) = _modulate_preset_values(mode, mix, contrast, gamma)

    count = 0
    for mat in bpy.data.materials:
        if not mat or not getattr(mat, 'use_nodes', False):
            continue
        nt = mat.node_tree
        if nt is None:
            continue
        bright_n = nt.nodes.get("Prelight_Bright")
        mix_n = nt.nodes.get("Prelight_Mix")
        # No prelight setup at all → пропускаем
        if not (bright_n and mix_n):
            continue
        amb_n = nt.nodes.get("Prelight_Ambient")
        pf1_n = nt.nodes.get("Prelight_PostFx1")
        pf2_n = nt.nodes.get("Prelight_PostFx2")
        bc_n = nt.nodes.get("Prelight_BrightContrast")
        gm_n = nt.nodes.get("Prelight_Gamma")
        # Find Principled BSDF for inserting post-fx/contrast/gamma nodes
        principled = None
        for n in nt.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                principled = n
                break

        # Lazy upgrade: вставить Prelight_Ambient если отсутствует.
        if amb_n is None:
            amb_n = nt.nodes.new(compat.MIX_NODE_TYPE)
            amb_n.name = "Prelight_Ambient"
            amb_n.label = "Ambient (Modulate)"
            compat.setup_mix_rgba_node(amb_n, blend='ADD')
            amb_n.location = (mix_n.location.x - 80, mix_n.location.y - 100)
            for lnk in list(compat.mix_input_b(mix_n).links):
                nt.links.remove(lnk)
            nt.links.new(compat.mix_output_result(bright_n), compat.mix_input_a(amb_n))
            nt.links.new(compat.mix_output_result(amb_n), compat.mix_input_b(mix_n))

        # Lazy upgrade: вставить PostFx1+PostFx2+BrightContrast+Gamma
        # после mix_n, перед Principled.Base Color если их нет.
        need_chain = principled is not None and (
            pf1_n is None or pf2_n is None or bc_n is None or gm_n is None)
        if need_chain:
            base_input = principled.inputs.get('Base Color')
            if base_input is not None:
                if pf1_n is None:
                    pf1_n = nt.nodes.new(compat.MIX_NODE_TYPE)
                    pf1_n.name = "Prelight_PostFx1"
                    pf1_n.label = "PostFx1 (Add)"
                    compat.setup_mix_rgba_node(pf1_n, blend='ADD')
                    pf1_n.location = (
                        principled.location.x - 200, principled.location.y - 50)
                if pf2_n is None:
                    pf2_n = nt.nodes.new(compat.MIX_NODE_TYPE)
                    pf2_n.name = "Prelight_PostFx2"
                    pf2_n.label = "PostFx2 (Add)"
                    compat.setup_mix_rgba_node(pf2_n, blend='ADD')
                    pf2_n.location = (
                        principled.location.x - 150, principled.location.y - 50)
                if bc_n is None:
                    bc_n = nt.nodes.new('ShaderNodeBrightContrast')
                    bc_n.name = "Prelight_BrightContrast"
                    bc_n.label = "Contrast"
                    bc_n.location = (
                        principled.location.x - 100, principled.location.y - 50)
                    bc_n.inputs['Bright'].default_value = 0.0
                if gm_n is None:
                    gm_n = nt.nodes.new('ShaderNodeGamma')
                    gm_n.name = "Prelight_Gamma"
                    gm_n.label = "Gamma"
                    gm_n.location = (
                        principled.location.x - 50, principled.location.y - 50)
                # Перевязать: mix → pf1 → pf2 → bc → gm → Base Color
                for lnk in list(base_input.links):
                    nt.links.remove(lnk)
                for lnk in list(compat.mix_input_a(pf1_n).links):
                    nt.links.remove(lnk)
                for lnk in list(compat.mix_input_a(pf2_n).links):
                    nt.links.remove(lnk)
                for lnk in list(bc_n.inputs['Color'].links):
                    nt.links.remove(lnk)
                for lnk in list(gm_n.inputs['Color'].links):
                    nt.links.remove(lnk)
                nt.links.new(compat.mix_output_result(mix_n), compat.mix_input_a(pf1_n))
                nt.links.new(compat.mix_output_result(pf1_n), compat.mix_input_a(pf2_n))
                nt.links.new(compat.mix_output_result(pf2_n), bc_n.inputs['Color'])
                nt.links.new(bc_n.outputs['Color'], gm_n.inputs['Color'])
                nt.links.new(gm_n.outputs['Color'], base_input)

        try:
            compat.mix_input_factor(amb_n).default_value = amb_factor
            compat.mix_input_b(amb_n).default_value = amb_b
            if pf1_n is not None:
                compat.mix_input_factor(pf1_n).default_value = pf1_f
                compat.mix_input_b(pf1_n).default_value = pf1_b
            if pf2_n is not None:
                compat.mix_input_factor(pf2_n).default_value = pf2_f
                compat.mix_input_b(pf2_n).default_value = pf2_b
            if bc_n is not None:
                bc_n.inputs['Contrast'].default_value = bc_contrast
            if gm_n is not None:
                gm_n.inputs['Gamma'].default_value = gm_gamma
            count += 1
        except (KeyError, AttributeError, RuntimeError):
            continue
    return count, amb_b[:3]


def fill_selected_faces(obj, color):
    """Залить выделенные грани цветом в режиме vertex paint"""
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    mesh = obj.data
    if not compat.vcol_list(mesh):
        return False, "No vertex colors found!"

    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        return False, "No active color layer!"

    # Get selected faces from bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    selected_faces = [f for f in bm.faces if f.select]

    if not selected_faces:
        bm.free()
        return False, "No faces selected!"

    # Get selected face indices
    selected_indices = set(f.index for f in selected_faces)
    bm.free()

    # Fill selected faces with color
    filled_count = 0
    for poly in mesh.polygons:
        if poly.index in selected_indices:
            for loop_idx in poly.loop_indices:
                color_attr.data[loop_idx].color = (color[0], color[1], color[2], 1.0)
            filled_count += 1

    return True, f"Filled {filled_count} faces"


# =============================================================================
# НОВАЯ АРХИТЕКТУРА СЛОЁВ
# =============================================================================
# Формула: ИТОГ = (База ИЛИ Fill) + Σ Scatter
#
# База — исходный цвет вершин, неизменный
# Fill — заменяет базу локально (не складывается)
# Scatter — дельта, всегда прибавляется
# =============================================================================

# Исходные цвета вершин (сохраняются при первой операции, никогда не меняются)
# Structure: {obj_name: {loop_idx: (r,g,b,a), ...}}
_base_colors = {}

# Fill слои - заменяют базу для своих loops
# Structure: {obj_name: {loop_idx: (r,g,b,a), ...}}
_fill_layers = {}

# Scatter слои - дельты которые прибавляются
# Structure: {obj_name: {color_tuple: {level_num: {loop_idx: (dr,dg,db,da), ...}, ...}, ...}}
_scatter_layers = {}


def ensure_base_colors(obj):
    """Сохранить базовые цвета если ещё не сохранены"""
    if obj is None or obj.type != 'MESH':
        return False

    obj_key = obj.name
    if obj_key in _base_colors:
        return True  # Уже сохранены

    mesh = obj.data
    if not compat.vcol_active(mesh):
        return False

    color_attr = compat.vcol_active(mesh)

    _base_colors[obj_key] = {}
    for loop_idx in range(len(color_attr.data)):
        c = color_attr.data[loop_idx].color
        _base_colors[obj_key][loop_idx] = (c[0], c[1], c[2], c[3])

    return True


def recalculate_loop_color(obj_key, loop_idx):
    """Пересчитать цвет одного loop: ИТОГ = (База ИЛИ Fill) + Σ Scatter"""
    # Получаем базу
    if obj_key not in _base_colors or loop_idx not in _base_colors[obj_key]:
        return None

    base = _base_colors[obj_key][loop_idx]

    # Проверяем есть ли Fill для этого loop
    fill = None
    if obj_key in _fill_layers and loop_idx in _fill_layers[obj_key]:
        fill = _fill_layers[obj_key][loop_idx]

    # Основа = Fill если есть, иначе База
    r, g, b, a = fill if fill else base

    # Добавляем все Scatter дельты
    if obj_key in _scatter_layers:
        for color_tuple, levels in _scatter_layers[obj_key].items():
            for level_num, deltas in levels.items():
                if loop_idx in deltas:
                    dr, dg, db, da = deltas[loop_idx]
                    r += dr
                    g += dg
                    b += db

    # Clamp to [0, 1]
    r = max(0.0, min(1.0, r))
    g = max(0.0, min(1.0, g))
    b = max(0.0, min(1.0, b))
    a = max(0.0, min(1.0, a))

    return (r, g, b, a)


def recalculate_colors(obj, loop_indices=None):
    """Пересчитать цвета для указанных loops (или всех если не указано)"""
    if obj is None or obj.type != 'MESH':
        return False

    obj_key = obj.name
    mesh = obj.data

    if not compat.vcol_active(mesh):
        return False

    color_attr = compat.vcol_active(mesh)

    # Если loops не указаны - пересчитать все
    if loop_indices is None:
        loop_indices = range(len(color_attr.data))

    for loop_idx in loop_indices:
        new_color = recalculate_loop_color(obj_key, loop_idx)
        if new_color and loop_idx < len(color_attr.data):
            color_attr.data[loop_idx].color = new_color

    return True


def add_fill_layer(obj, color, loop_indices):
    """Добавить Fill слой для указанных loops"""
    if obj is None:
        return False

    obj_key = obj.name
    color_tuple = (round(color[0], 3), round(color[1], 3), round(color[2], 3))

    # Сохраняем базу если ещё не сохранена
    ensure_base_colors(obj)

    # Инициализируем хранилище
    if obj_key not in _fill_layers:
        _fill_layers[obj_key] = {}

    # Записываем Fill цвет для каждого loop
    for loop_idx in loop_indices:
        _fill_layers[obj_key][loop_idx] = (color[0], color[1], color[2], 1.0)

    # Добавляем в UI список если новый цвет
    color_exists = False
    for item in obj.gtatools_fill_colors:
        existing = (round(item.color[0], 3), round(item.color[1], 3), round(item.color[2], 3))
        if existing == color_tuple:
            color_exists = True
            break

    if not color_exists:
        new_item = obj.gtatools_fill_colors.add()
        new_item.color = color_tuple

    return True


def add_scatter_layer(obj, color, deltas):
    """Добавить Scatter слой (дельты) для цвета
    deltas = {loop_idx: (dr, dg, db, da), ...}
    """
    if obj is None or not deltas:
        return -1

    obj_key = obj.name
    color_tuple = (round(color[0], 3), round(color[1], 3), round(color[2], 3))

    # Сохраняем базу если ещё не сохранена
    ensure_base_colors(obj)

    # Инициализируем хранилище
    if obj_key not in _scatter_layers:
        _scatter_layers[obj_key] = {}
    if color_tuple not in _scatter_layers[obj_key]:
        _scatter_layers[obj_key][color_tuple] = {}

    # Находим следующий номер уровня
    existing_levels = list(_scatter_layers[obj_key][color_tuple].keys())
    next_level = max(existing_levels) + 1 if existing_levels else 1

    # Сохраняем дельты
    _scatter_layers[obj_key][color_tuple][next_level] = deltas

    return next_level


def get_scatter_levels(obj, color):
    """Получить список уровней scatter для цвета"""
    if obj is None:
        return []

    obj_key = obj.name
    color_tuple = (round(color[0], 3), round(color[1], 3), round(color[2], 3))

    if obj_key not in _scatter_layers:
        return []
    if color_tuple not in _scatter_layers[obj_key]:
        return []

    return sorted(_scatter_layers[obj_key][color_tuple].keys())


def remove_scatter_layer(obj, color, level):
    """Удалить Scatter слой и пересчитать цвета"""
    if obj is None:
        return False, "No object"

    obj_key = obj.name
    color_tuple = (round(color[0], 3), round(color[1], 3), round(color[2], 3))

    if obj_key not in _scatter_layers:
        return False, "No scatter layers"
    if color_tuple not in _scatter_layers[obj_key]:
        return False, "No scatter layers for this color"
    if level not in _scatter_layers[obj_key][color_tuple]:
        return False, f"Level {level} not found"

    # Получаем loops которые были затронуты этим слоем
    affected_loops = list(_scatter_layers[obj_key][color_tuple][level].keys())

    # Удаляем слой
    del _scatter_layers[obj_key][color_tuple][level]

    # Пересчитываем цвета для затронутых loops
    recalculate_colors(obj, affected_loops)

    return True, f"Level {level} removed"


def clear_scatter_layers(obj, color):
    """Удалить все Scatter слои для цвета и пересчитать"""
    if obj is None:
        return False, "No object"

    obj_key = obj.name
    color_tuple = (round(color[0], 3), round(color[1], 3), round(color[2], 3))

    if obj_key not in _scatter_layers:
        return False, "No scatter layers"
    if color_tuple not in _scatter_layers[obj_key]:
        return False, "No scatter layers for this color"

    # Собираем все затронутые loops
    affected_loops = set()
    for level_data in _scatter_layers[obj_key][color_tuple].values():
        affected_loops.update(level_data.keys())

    # Удаляем все слои
    _scatter_layers[obj_key][color_tuple] = {}

    # Пересчитываем цвета
    recalculate_colors(obj, affected_loops)

    return True, "All scatter levels removed"


def remove_fill_color(obj, color):
    """Удалить Fill цвет и все его Scatter слои, пересчитать"""
    if obj is None:
        return False, "No object"

    obj_key = obj.name
    color_tuple = (round(color[0], 3), round(color[1], 3), round(color[2], 3))

    affected_loops = set()

    # Собираем loops из Fill
    if obj_key in _fill_layers:
        for loop_idx, fill_color in list(_fill_layers[obj_key].items()):
            fill_tuple = (round(fill_color[0], 3), round(fill_color[1], 3), round(fill_color[2], 3))
            if fill_tuple == color_tuple:
                affected_loops.add(loop_idx)
                del _fill_layers[obj_key][loop_idx]

    # Собираем loops из Scatter и удаляем
    if obj_key in _scatter_layers:
        if color_tuple in _scatter_layers[obj_key]:
            for level_data in _scatter_layers[obj_key][color_tuple].values():
                affected_loops.update(level_data.keys())
            del _scatter_layers[obj_key][color_tuple]

    # Пересчитываем цвета
    if affected_loops:
        recalculate_colors(obj, affected_loops)

    return True, "Fill color removed"


def remove_fill_color_by_index(obj, index):
    """Удалить цвет из списка по индексу"""
    if obj is None:
        return False, "No object"

    if not (0 <= index < len(obj.gtatools_fill_colors)):
        return False, "Invalid index"

    # Получаем цвет
    color_item = obj.gtatools_fill_colors[index]
    color_tuple = (color_item.color[0], color_item.color[1], color_item.color[2])

    # Удаляем цвет и пересчитываем
    remove_fill_color(obj, color_tuple)

    # Удаляем из UI списка
    obj.gtatools_fill_colors.remove(index)

    return True, "Color removed"


def get_selected_faces_color(obj):
    """Получить Fill цвет выделенных полигонов"""
    if obj is None or obj.type != 'MESH':
        return None

    mesh = obj.data

    # Получаем выделенные полигоны
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    selected_faces = [f for f in bm.faces if f.select]
    if not selected_faces:
        bm.free()
        return None

    selected_face_indices = set(f.index for f in selected_faces)
    bm.free()

    # Получаем loops выделенных полигонов
    selected_loops = set()
    for poly in mesh.polygons:
        if poly.index in selected_face_indices:
            for loop_idx in poly.loop_indices:
                selected_loops.add(loop_idx)

    if not selected_loops:
        return None

    obj_key = obj.name

    # Проверяем какой Fill цвет есть у этих loops
    if obj_key in _fill_layers:
        for loop_idx in selected_loops:
            if loop_idx in _fill_layers[obj_key]:
                fill_color = _fill_layers[obj_key][loop_idx]
                return (round(fill_color[0], 3), round(fill_color[1], 3), round(fill_color[2], 3))

    # Fallback: по текущему цвету
    color_attr = compat.vcol_active(mesh)
    if color_attr is not None:
        first_loop = next(iter(selected_loops))
        c = color_attr.data[first_loop].color
        color_tuple = (round(c[0], 3), round(c[1], 3), round(c[2], 3))

        # Проверяем есть ли в списке Fill цветов
        for item in obj.gtatools_fill_colors:
            existing = (round(item.color[0], 3), round(item.color[1], 3), round(item.color[2], 3))
            if existing == color_tuple:
                return color_tuple

    return None


def fill_selected_faces_with_backup(obj, color):
    """Залить выделенные грани цветом через систему слоёв"""
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    # Запоминаем режим и переключаемся в Object если нужно
    original_mode = obj.mode
    if original_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mesh = obj.data
    if not compat.vcol_list(mesh):
        return False, "No vertex colors found!"

    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        return False, "No active color layer!"

    # Get selected faces from bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    selected_faces = [f for f in bm.faces if f.select]

    if not selected_faces:
        bm.free()
        return False, "No faces selected!"

    selected_indices = set(f.index for f in selected_faces)
    bm.free()

    # Собираем loop indices выделенных полигонов
    loop_indices = []
    for poly in mesh.polygons:
        if poly.index in selected_indices:
            for loop_idx in poly.loop_indices:
                loop_indices.append(loop_idx)

    filled_count = len(selected_indices)

    # Добавляем Fill слой (сохраняет базу автоматически)
    add_fill_layer(obj, color, loop_indices)

    # Применяем цвет напрямую (быстрее чем пересчёт)
    for loop_idx in loop_indices:
        color_attr.data[loop_idx].color = (color[0], color[1], color[2], 1.0)

    # Возвращаемся в исходный режим
    if original_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    return True, f"Filled {filled_count} faces"


def restore_filled_faces(obj):
    """Восстановить все цвета к базовым (удалить fill и scatter слои)"""
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    obj_key = obj.name

    # Проверяем есть ли база
    if obj_key not in _base_colors:
        return False, "No base colors saved!"

    # Запоминаем режим и переключаемся в Object если нужно
    original_mode = obj.mode
    if original_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mesh = obj.data
    if not compat.vcol_list(mesh):
        return False, "No vertex colors found!"

    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        return False, "No active color layer!"

    # Очищаем fill слои
    if obj_key in _fill_layers:
        _fill_layers[obj_key] = {}

    # Очищаем scatter слои
    if obj_key in _scatter_layers:
        _scatter_layers[obj_key] = {}

    # Восстанавливаем из базы
    base = _base_colors[obj_key]
    restored_count = 0
    for loop_idx, base_color in base.items():
        if loop_idx < len(color_attr.data):
            color_attr.data[loop_idx].color = base_color
            restored_count += 1

    # Удаляем все цвета из UI
    obj.gtatools_fill_colors.clear()

    # Возвращаемся в исходный режим
    if original_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    return True, f"Restored {restored_count} vertices to base"


def scatter_light_from_selected(obj, intensity=1.0, falloff=2.0, iterations=3, radius=0.0):
    """Scatter light from selected faces to vertices with distance-based falloff

    Paints vertices based on distance from light source faces.
    Creates smooth gradient - closer vertices are brighter.
    """
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!", []

    # Запоминаем режим и переключаемся в Object если нужно
    original_mode = obj.mode
    if original_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mesh = obj.data
    if not compat.vcol_list(mesh):
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        return False, "No vertex colors found!", []

    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        return False, "No active color layer!", []

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    selected_faces = [f for f in bm.faces if f.select]

    if not selected_faces:
        bm.free()
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        return False, "No faces selected! Select light source faces!", []

    # Get source face indices
    source_indices = set(f.index for f in selected_faces)

    # Collect light source points (centers of selected faces)
    light_sources = []
    for f in selected_faces:
        light_sources.append(f.calc_center_median())

    # Calculate average color of selected faces (light source color)
    source_colors = []
    for poly in mesh.polygons:
        if poly.index in source_indices:
            for loop_idx in poly.loop_indices:
                c = color_attr.data[loop_idx].color
                source_colors.append((c[0], c[1], c[2]))

    if not source_colors:
        bm.free()
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        return False, "Could not read source colors!", []

    # Average light color
    light_color = (
        sum(c[0] for c in source_colors) / len(source_colors),
        sum(c[1] for c in source_colors) / len(source_colors),
        sum(c[2] for c in source_colors) / len(source_colors)
    )
    light_brightness = (light_color[0] + light_color[1] + light_color[2]) / 3.0

    # Calculate auto-radius if not specified
    if radius <= 0:
        total_area = sum(f.calc_area() for f in selected_faces)
        avg_size = math.sqrt(total_area / len(selected_faces)) if selected_faces else 1.0
        radius = avg_size * iterations * 2.0

    # Get vertices from source faces (these won't be modified)
    source_verts = set()
    for f in selected_faces:
        for v in f.verts:
            source_verts.add(v.index)

    # Calculate light factor for each vertex based on distance
    # vertex_light[vert_index] = light_factor
    vertex_light = {}

    for vert in bm.verts:
        if vert.index in source_verts:
            continue  # Skip source vertices

        vert_pos = vert.co

        # Find minimum distance to any light source
        min_dist = float('inf')
        for light_pos in light_sources:
            dist = (vert_pos - light_pos).length
            if dist < min_dist:
                min_dist = dist

        # Only affect vertices within radius
        if min_dist < radius:
            # Calculate falloff based on distance
            # Normalize distance to 0-1 range within radius
            norm_dist = min_dist / radius

            # Apply falloff curve (higher falloff = faster decay)
            # factor goes from intensity (at distance 0) to 0 (at radius)
            factor = intensity * pow(1.0 - norm_dist, falloff)

            vertex_light[vert.index] = factor

    bm.free()

    # Build vertex index to loop indices mapping
    vert_to_loops = {}
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            vert_idx = mesh.loops[loop_idx].vertex_index
            if vert_idx not in vert_to_loops:
                vert_to_loops[vert_idx] = []
            vert_to_loops[vert_idx].append(loop_idx)

    # Apply light to vertices
    modified_count = 0
    affected_loops = []  # Track affected loop indices

    for vert_idx, factor in vertex_light.items():
        if vert_idx not in vert_to_loops:
            continue

        for loop_idx in vert_to_loops[vert_idx]:
            affected_loops.append(loop_idx)

            c = color_attr.data[loop_idx].color

            # Add light but don't exceed source brightness
            add_r = light_color[0] * factor * 0.5
            add_g = light_color[1] * factor * 0.5
            add_b = light_color[2] * factor * 0.5

            new_r = c[0] + add_r
            new_g = c[1] + add_g
            new_b = c[2] + add_b

            # Clamp so we don't exceed light source brightness
            new_brightness = (new_r + new_g + new_b) / 3.0
            if new_brightness > light_brightness:
                scale = light_brightness / new_brightness if new_brightness > 0 else 1.0
                new_r *= scale
                new_g *= scale
                new_b *= scale

            new_r = min(1.0, max(0.0, new_r))
            new_g = min(1.0, max(0.0, new_g))
            new_b = min(1.0, max(0.0, new_b))

            color_attr.data[loop_idx].color = (new_r, new_g, new_b, c[3])

        modified_count += 1

    # Возвращаемся в исходный режим
    if original_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    return True, f"Light scattered to {modified_count} vertices (radius: {radius:.2f})", affected_loops


def scatter_color_from_selected(obj, color, strength=1.0, distance=1.0):
    """Paint a chosen color around selected faces with linear falloff.

    Use case: добавить локальный тинт/свечение в зону вокруг выбранных
    полигонов — не тащит prelight под ногами, а замешивает указанный
    цвет с убыванием по расстоянию.

    color   — (r, g, b[, a]) target color, линейный 0..1; смешивается
              только RGB — альфа слоя сохраняется (a не используется).
    strength — 0..1, сила вклада в центре (0 — ничего не делать,
               1 — полная замена цвета на target в центре).
    distance — 0..1, радиус как доля половины bbox-диагонали меша.
               0 = тинт только на выделенных вершинах; 1 = расходится
               на половину диагонали меша.

    Existing vcols blended (not replaced); рассчитывается per-vertex
    Euclidean distance до ближайшей выбранной вершины через mathutils
    KDTree. Запись через foreach_set.
    """
    if obj is None or obj.type != 'MESH':
        return False, "Select a mesh object!"

    original_mode = obj.mode
    if original_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mesh = obj.data
    color_attr = compat.vcol_active(mesh)
    if color_attr is None:
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        return False, "No active color layer!"

    n_verts = len(mesh.vertices)
    n_loops = len(mesh.loops)
    if n_loops == 0:
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        return False, "Mesh has no loops"

    # Selected vertex set (any face that's selected contributes its verts)
    selected_verts = []
    for poly in mesh.polygons:
        if poly.select:
            selected_verts.extend(poly.vertices)
    selected_verts = list(set(selected_verts))
    if not selected_verts:
        if original_mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        return False, "No faces selected"

    # Bulk read vertex positions
    coords = np.empty(n_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', coords)
    coords = coords.reshape(n_verts, 3)

    # BBox half-diagonal — radius scale
    bbox_min = coords.min(axis=0)
    bbox_max = coords.max(axis=0)
    half_diag = float(np.linalg.norm(bbox_max - bbox_min)) * 0.5
    max_radius = max(0.001, half_diag * float(distance))

    # KDTree on selected vertex coords for nearest-neighbor distance
    import mathutils
    kd = mathutils.kdtree.KDTree(len(selected_verts))
    for i, vi in enumerate(selected_verts):
        kd.insert(mathutils.Vector(coords[vi].tolist()), i)
    kd.balance()

    # Per-vertex blend factor: 1 at sel vert, linearly down to 0 at max_radius
    sel_set = set(selected_verts)
    vert_blend = np.zeros(n_verts, dtype=np.float32)
    for vi in range(n_verts):
        if vi in sel_set:
            vert_blend[vi] = 1.0
            continue
        co = coords[vi]
        _, _, dist = kd.find(mathutils.Vector(co.tolist()))
        if dist is None:
            continue
        if dist <= max_radius:
            vert_blend[vi] = 1.0 - (dist / max_radius)
    vert_blend *= float(strength)

    # Per-loop expansion via vertex_index
    loop_vidx = np.empty(n_loops, dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', loop_vidx)
    loop_blend = vert_blend[loop_vidx]

    # Read existing vcols, blend toward target color
    flat = np.empty(n_loops * 4, dtype=np.float32)
    color_attr.data.foreach_get('color', flat)
    existing = flat.reshape(n_loops, 4)

    target = np.array((color[0], color[1], color[2]), dtype=np.float32)

    # Только RGB: альфа (нарисованная прозрачность) остаётся как была.
    f = loop_blend[:, None]
    new_colors = existing.copy()
    new_colors[:, :3] = existing[:, :3] * (1.0 - f) + target[None, :] * f
    color_attr.data.foreach_set('color', new_colors.ravel())

    if original_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    affected = int(np.count_nonzero(vert_blend))
    return True, f"Scattered color around {len(selected_verts)} selected → {affected} affected verts (radius {max_radius:.2f})"
