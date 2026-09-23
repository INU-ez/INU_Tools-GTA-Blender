# INU_tools.ops.world_ops — Water .dat / flight.dat / track.dat / nodes / paths.ipl / convert_to_path / station marker.
#
# Phase 3 (2026-04-26): operators moved from __init__.py.

import ast
import os
import bpy
from bpy.props import (
    StringProperty, BoolProperty, EnumProperty, CollectionProperty,
)

from .. import T


class GTATOOLS_OT_import_water(bpy.types.Operator):
    """Импорт water.dat"""
    bl_idname = "gtatools.import_water"
    bl_label = "INU: Import Water"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .water_import import import_water
        try:
            objects = import_water(filepath=self.filepath, context=context)
            self.report({'INFO'}, f"Water: {len(objects)} objects imported")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Water import error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_export_water(bpy.types.Operator):
    """Экспорт water.dat"""
    bl_idname = "gtatools.export_water"
    bl_label = "INU: Export Water"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "water.dat"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .water_export import export_water
        try:
            objects = [o for o in context.selected_objects if o.type == 'MESH']
            if not objects:
                col = bpy.data.collections.get("Water")
                if col:
                    objects = [o for o in col.objects if o.type == 'MESH']
            count = export_water(filepath=self.filepath, objects=objects)
            # DAT-43..45 audit of what landed on disk (counts 301/6/1021,
            # ±3000, flow range, axis-aligned quads, 500-block grid).
            from .textdata_audit import audit_water_file
            audit_water_file(self, self.filepath)
            self.report({'INFO'}, f"Water: {count} polygons exported")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Water export error: {str(e)}")
            return {'CANCELLED'}


# =============================================================================
# PATH IO OPERATORS
# =============================================================================

class GTATOOLS_OT_import_track(bpy.types.Operator):
    """Импорт tracks.dat — железнодорожные пути"""
    bl_idname = "gtatools.import_track"
    bl_label = "INU: Import Train Track"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .path_import import import_track
        try:
            objects = import_track(filepath=self.filepath, context=context)
            self.report({'INFO'}, f"Track: {len(objects[0].data.splines[0].points) if objects else 0} nodes imported")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Track import error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_export_track(bpy.types.Operator):
    """Экспорт tracks.dat — железнодорожные пути"""
    bl_idname = "gtatools.export_track"
    bl_label = "INU: Export Train Track"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "tracks.dat"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .path_export import export_track
        try:
            obj = None
            for o in context.selected_objects:
                if o.type == 'CURVE' and o.get('path_type') == 'track':
                    obj = o
                    break
            if not obj:
                col = bpy.data.collections.get("Train Tracks")
                if col:
                    for o in col.objects:
                        if o.type == 'CURVE' and o.get('path_type') == 'track':
                            obj = o
                            break
            count = export_track(filepath=self.filepath, obj=obj)
            self.report({'INFO'}, f"Track: {count} nodes exported")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Track export error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_import_nodes(bpy.types.Operator):
    """Импорт nodes.dat — пешеходные/авто пути (мультивыбор)"""
    bl_idname = "gtatools.import_nodes"
    bl_label = "INU: Import Path Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .path_import import import_nodes
        wm = context.window_manager
        total_nodes = 0
        total_files = 0
        # Progress bar: cursor flips through the file count so user
        # gets visual feedback during a full-map import (64 zone files).
        # Blender's `wm.progress_*` only updates the cursor, not the
        # viewport, but it's the standard pattern and good enough
        # since import is a blocking single-threaded operation.
        n_files = max(1, len(self.files))
        wm.progress_begin(0, n_files)
        try:
            for idx, f in enumerate(self.files):
                wm.progress_update(idx)
                path = os.path.join(self.directory, f.name)
                if not os.path.isfile(path):
                    continue
                try:
                    objects = import_nodes(filepath=path, context=context)
                    total_nodes += sum(len(o.data.vertices) for o in objects if o.type == 'MESH')
                    total_files += 1
                except Exception as e:
                    self.report({'WARNING'}, f"{f.name}: {str(e)}")
        finally:
            wm.progress_end()
        self.report({'INFO'}, f"Nodes: {total_nodes} nodes from {total_files} files")
        return {'FINISHED'}


class GTATOOLS_OT_export_nodes(bpy.types.Operator):
    """Экспорт nodes.dat — группировка по имени файла или авто-разбиение по зонам"""
    bl_idname = "gtatools.export_nodes"
    bl_label = "INU: Export Path Nodes"
    bl_options = {'REGISTER'}

    directory: StringProperty(subtype='DIR_PATH')
    fla4: BoolProperty(
        name="FLA4 Format",
        description=T("Писать nodes*.dat в расширенном FLA4 формате (spawn/speed/lanes per-node)"),
        default=False,
    )

    def invoke(self, context, event):
        # Auto-detect FLA4 from selected imported objects so the user
        # doesn't have to remember the format of the file they loaded.
        # Without this, re-exporting an FLA4 source silently downgrades
        # to vanilla format (losing spawn/speed/lane per-node fields).
        for obj in context.selected_objects:
            if obj.get('fla4', False):
                self.fla4 = True
                break
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "fla4")

    def execute(self, context):
        from .path_export import export_nodes

        objects = [o for o in context.selected_objects
                   if o.type == 'MESH' and o.get('path_type', '').startswith('nodes_')]
        if not objects:
            self.report({'ERROR'}, T("Выделите объекты с нодами"))
            return {'CANCELLED'}

        # Group by nodes_filename
        groups = {}  # filename → [objects]
        auto_split = []  # objects without filename
        for obj in objects:
            fname = obj.get('nodes_filename', '')
            if fname:
                groups.setdefault(fname, []).append(obj)
            else:
                auto_split.append(obj)

        exported = 0

        # Export objects with known filename
        for fname, objs in groups.items():
            filepath = os.path.join(self.directory, fname)
            try:
                count = export_nodes(filepath=filepath, objects=objs, fla4=self.fla4)
                exported += count
            except Exception as e:
                self.report({'WARNING'}, f"{fname}: {e}")

        # Auto-split objects by zone (8x8 grid)
        if auto_split:
            from ..core.paths import NodesFile, PathNode, write_nodes
            zones = {}  # zone_idx → NodesFile
            for obj in auto_split:
                path_type = obj.get('path_type', '')
                mat_w = obj.matrix_world
                for vert in obj.data.vertices:
                    co = mat_w @ vert.co
                    gx = max(0, min(7, int((co.x + 3000) / 750)))
                    gy = max(0, min(7, int((3000 - co.y) / 750)))
                    zone = gy * 8 + gx
                    if zone not in zones:
                        zones[zone] = NodesFile()
                        zones[zone].fla4 = self.fla4
                    node = PathNode(x=co.x, y=co.y, z=co.z)
                    if path_type == 'nodes_vehicle':
                        zones[zone].vehicle_nodes.append(node)
                    elif path_type == 'nodes_ped':
                        zones[zone].ped_nodes.append(node)

            for zone_idx, nf in zones.items():
                fname = f"nodes{zone_idx}.dat"
                filepath = os.path.join(self.directory, fname)
                try:
                    write_nodes(filepath, nf)
                    exported += len(nf.vehicle_nodes) + len(nf.ped_nodes)
                except Exception as e:
                    self.report({'WARNING'}, f"{fname}: {e}")

        self.report({'INFO'}, f"Nodes: {exported} nodes exported")
        return {'FINISHED'}


class GTATOOLS_OT_toggle_nodes_viz(bpy.types.Operator):
    """Создать или скрыть геометрию визуализации путей"""
    bl_idname = "gtatools.toggle_nodes_viz"
    bl_label = "INU: Toggle Path Nodes Visualization"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Walk every path-node mesh in scene (vehicle + ped).
        path_meshes = [
            o for o in context.scene.objects
            if o.type == 'MESH'
            and o.get('path_type', '') in ('nodes_vehicle', 'nodes_ped')
        ]
        if not path_meshes:
            self.report({'INFO'}, "No path nodes meshes in scene")
            return {'CANCELLED'}

        # Determine current state: any Skin modifier with show_viewport
        # = True means visualisation is currently ON. State machine:
        #   OFF → ON  : ensure Skin exists + show. Lazy-creates the
        #               modifier on the first toggle so import stays
        #               cheap (heavy geometry only when user asks).
        #   ON  → OFF : hide existing modifiers but keep them so the
        #               next ON click is instant (no rebuild).
        any_on = False
        for obj in path_meshes:
            for mod in obj.modifiers:
                if mod.type == 'SKIN' and mod.show_viewport:
                    any_on = True
                    break
            if any_on:
                break
        new_state = not any_on

        n_changed = 0
        if new_state:
            # OFF → ON
            from .path_import import _add_skin_modifier
            for obj in path_meshes:
                mod = next((m for m in obj.modifiers if m.type == 'SKIN'), None)
                if mod is None:
                    # First toggle for this object — create from
                    # scratch. Edges already live on the mesh from
                    # import; reuse them so Skin tubes the same graph.
                    edges = [(e.vertices[0], e.vertices[1])
                             for e in obj.data.edges]
                    radius = (0.5 if obj.get('path_type') == 'nodes_vehicle'
                              else 0.35)
                    _add_skin_modifier(obj, edges, radius=radius)
                    n_changed += 1
                elif not mod.show_viewport:
                    mod.show_viewport = True
                    n_changed += 1
        else:
            # ON → OFF
            for obj in path_meshes:
                for mod in obj.modifiers:
                    if mod.type == 'SKIN' and mod.show_viewport:
                        mod.show_viewport = False
                        n_changed += 1

        verb = "shown" if new_state else "hidden"
        self.report({'INFO'},
                    f"Path nodes geometry {verb} ({n_changed} obj)")
        return {'FINISHED'}


class GTATOOLS_OT_import_paths_ipl(bpy.types.Operator):
    """Импорт paths.ipl — пути для gta.dat"""
    bl_idname = "gtatools.import_paths_ipl"
    bl_label = "INU: Import Paths IPL"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.ipl", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .path_import import import_paths_ipl
        try:
            objects = import_paths_ipl(filepath=self.filepath, context=context)
            self.report({'INFO'}, f"Paths IPL: {len(objects)} groups imported")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Paths IPL import error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_export_paths_ipl(bpy.types.Operator):
    """Экспорт paths.ipl — пути для gta.dat"""
    bl_idname = "gtatools.export_paths_ipl"
    bl_label = "INU: Export Paths IPL"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.ipl", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "paths_custom.ipl"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .path_export import export_paths_ipl
        try:
            # Selected objects first, then fall back to "Path IPL" collection
            objects = [o for o in context.selected_objects
                       if o.type == 'CURVE' and o.get('path_type') == 'path_ipl']
            if not objects:
                col = bpy.data.collections.get("Path IPL")
                if col:
                    objects = [o for o in col.objects
                               if o.type == 'CURVE' and o.get('path_type') == 'path_ipl']
            count = export_paths_ipl(filepath=self.filepath, objects=objects)
            self.report({'INFO'}, f"Paths IPL: {count} groups exported")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Paths IPL export error: {str(e)}")
            return {'CANCELLED'}


class GTATOOLS_OT_convert_to_path(bpy.types.Operator):
    """Конвертировать кривую или рёбра меша в путь paths.ipl"""
    bl_idname = "gtatools.convert_to_path"
    bl_label = "INU: Convert to Path"
    bl_options = {'REGISTER', 'UNDO'}

    group_type: EnumProperty(
        name="Type",
        items=[
            ('1', T("Авто"), ""),
            ('0', T("Пешеходный"), ""),
        ],
        default='1',
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False
        if obj.type == 'CURVE':
            return True
        if obj.type == 'MESH':
            # Allow only if no faces (edges/verts only)
            return len(obj.data.polygons) == 0
        return False

    def execute(self, context):
        obj = context.active_object
        is_veh = self.group_type == '1'

        if obj.type == 'MESH':
            # Convert edges-only mesh to curve first
            if len(obj.data.polygons) > 0:
                self.report({'ERROR'}, T("Нельзя конвертировать меш с полигонами"))
                return {'CANCELLED'}

            # Convert to curve
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.object.convert(target='CURVE')
            obj = context.active_object  # Now it's a curve

        if obj.type != 'CURVE':
            self.report({'ERROR'}, "Not a curve")
            return {'CANCELLED'}

        # Set path properties
        obj['path_type'] = 'path_ipl'
        obj['group_type'] = int(self.group_type)
        obj['group_index'] = 0
        obj['external_index'] = -1

        # Count real points
        total_pts = sum(len(s.points) if s.type == 'POLY' else len(s.bezier_points)
                        for s in obj.data.splines)
        for i in range(total_pts):
            obj[f'pn_{i}_type'] = 2
            obj[f'pn_{i}_link'] = (i + 1) if i < total_pts - 1 else -1
            obj[f'pn_{i}_area'] = 0
            obj[f'pn_{i}_unk'] = 0.0
            obj[f'pn_{i}_width'] = 1
            obj[f'pn_{i}_ll'] = 1
            obj[f'pn_{i}_rl'] = 1
            obj[f'pn_{i}_mw'] = 0
            obj[f'pn_{i}_flags'] = 1
            obj[f'pn_{i}_spawn'] = 0
        obj['pn_count'] = total_pts

        # Apply curve style
        from .path_import import _setup_path_curve
        _setup_path_curve(obj.data)

        # Material
        mat_name = 'VehiclePath_IPL_Mat' if is_veh else 'PedPath_IPL_Mat'
        color = (0.0, 0.5, 1.0, 0.8) if is_veh else (0.0, 1.0, 0.3, 0.8)
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            for n in mat.node_tree.nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    n.inputs['Base Color'].default_value = color
                    break
            mat.diffuse_color = color
        if not obj.data.materials:
            obj.data.materials.append(mat)

        # Move to Path IPL collection
        col = bpy.data.collections.get("Path IPL")
        if not col:
            col = bpy.data.collections.new("Path IPL")
            context.scene.collection.children.link(col)
        # Unlink from current collections
        for c in obj.users_collection:
            c.objects.unlink(obj)
        col.objects.link(obj)

        label = T("Авто") if is_veh else T("Пешеходный")
        self.report({'INFO'}, f"{obj.name} → {label} path ({total_pts} pts)")
        return {'FINISHED'}


class GTATOOLS_OT_add_path_ipl(bpy.types.Operator):
    """Создать новый путь для paths.ipl"""
    bl_idname = "gtatools.add_path_ipl"
    bl_label = "INU: Add Path (IPL)"
    bl_options = {'REGISTER', 'UNDO'}

    group_type: EnumProperty(
        name="Type",
        items=[
            ('1', T("Авто"), T("Автомобильный путь")),
            ('0', T("Пешеходный"), T("Пешеходный путь")),
        ],
        default='1',
    )

    def execute(self, context):
        is_veh = self.group_type == '1'
        prefix = "VehPath" if is_veh else "PedPath"

        curve = bpy.data.curves.new(f"{prefix}_new", type='CURVE')
        curve.dimensions = '3D'
        spline = curve.splines.new('POLY')
        spline.points.add(1)
        loc = context.scene.cursor.location
        spline.points[0].co = (loc.x, loc.y, loc.z, 1.0)
        spline.points[1].co = (loc.x + 30, loc.y, loc.z, 1.0)

        obj = bpy.data.objects.new(f"{prefix}_new", curve)
        obj['path_type'] = 'path_ipl'
        obj['group_type'] = int(self.group_type)
        obj['group_index'] = 0
        obj['external_index'] = -1

        # Default node props for 2 internal nodes
        for i in range(2):
            obj[f'pn_{i}_type'] = 2  # internal
            obj[f'pn_{i}_link'] = (i + 1) if i < 1 else -1
            obj[f'pn_{i}_area'] = 0
            obj[f'pn_{i}_unk'] = 0.0
            obj[f'pn_{i}_width'] = 1
            obj[f'pn_{i}_ll'] = 1
            obj[f'pn_{i}_rl'] = 1
            obj[f'pn_{i}_mw'] = 0
            obj[f'pn_{i}_flags'] = 1
            obj[f'pn_{i}_spawn'] = 0
        obj['pn_count'] = 2

        from .path_import import _setup_path_curve
        _setup_path_curve(curve)
        mat_name = 'VehiclePath_IPL_Mat' if is_veh else 'PedPath_IPL_Mat'
        color = (0.0, 0.5, 1.0, 0.8) if is_veh else (0.0, 1.0, 0.3, 0.8)
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            for n in mat.node_tree.nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    n.inputs['Base Color'].default_value = color
                    break
            mat.diffuse_color = color
        curve.materials.append(mat)

        col = bpy.data.collections.get("Path IPL")
        if not col:
            col = bpy.data.collections.new("Path IPL")
            context.scene.collection.children.link(col)
        col.objects.link(obj)

        context.view_layer.objects.active = obj
        obj.select_set(True)

        label = T("Авто") if is_veh else T("Пешеходный")
        self.report({'INFO'}, f"{label} path created. Edit in Edit Mode, max 12 points")
        return {'FINISHED'}


class GTATOOLS_OT_add_track(bpy.types.Operator):
    """Создать новый ж/д путь (кривая)"""
    bl_idname = "gtatools.add_track"
    bl_label = "INU: Add Train Track"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        curve = bpy.data.curves.new("Track_New", type='CURVE')
        curve.dimensions = '3D'
        spline = curve.splines.new('POLY')
        # Start with 2 points at cursor
        spline.points.add(1)
        loc = context.scene.cursor.location
        spline.points[0].co = (loc.x, loc.y, loc.z, 1.0)
        spline.points[1].co = (loc.x + 50, loc.y, loc.z, 1.0)
        spline.use_cyclic_u = True

        obj = bpy.data.objects.new("Track_New", curve)
        obj['path_type'] = 'track'
        obj['station_indices'] = '[]'

        from .path_import import _setup_path_curve
        _setup_path_curve(curve)

        # Material
        mat = bpy.data.materials.get('TrainTrack_Mat')
        if not mat:
            mat = bpy.data.materials.new('TrainTrack_Mat')
            mat.use_nodes = True
            for n in mat.node_tree.nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    n.inputs['Base Color'].default_value = (0.6, 0.3, 0.0, 0.8)
                    break
            mat.diffuse_color = (0.6, 0.3, 0.0, 0.8)
        curve.materials.append(mat)

        col = bpy.data.collections.get("Train Tracks")
        if not col:
            col = bpy.data.collections.new("Train Tracks")
            context.scene.collection.children.link(col)
        col.objects.link(obj)

        context.view_layer.objects.active = obj
        obj.select_set(True)

        self.report({'INFO'}, T("Ж/д путь создан. Редактируйте в Edit Mode"))
        return {'FINISHED'}


class GTATOOLS_OT_mark_station(bpy.types.Operator):
    """Отметить/снять выбранные точки кривой как станции (flag=1)"""
    bl_idname = "gtatools.mark_station"
    bl_label = "INU: Toggle Station"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'CURVE' and obj.get('path_type') == 'track'
                and context.mode == 'EDIT_CURVE')

    def execute(self, context):
        obj = context.active_object
        raw = obj.get('station_indices', '[]')
        try:
            stations = set(ast.literal_eval(raw))
        except Exception:
            stations = set()

        # Toggle selected points
        idx = 0
        toggled = 0
        for spline in obj.data.splines:
            for point in spline.points:
                if point.select:
                    if idx in stations:
                        stations.discard(idx)
                    else:
                        stations.add(idx)
                    toggled += 1
                idx += 1

        obj['station_indices'] = str(sorted(stations))
        self.report({'INFO'}, f"{toggled} points toggled, {len(stations)} stations total")
        return {'FINISHED'}


