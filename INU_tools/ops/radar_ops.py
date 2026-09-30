# INU_tools.ops.radar_ops — X Radar Maker — generate minimap tiles + pack TXD.
#
# Phase 3 (2026-04-26): operators moved from __init__.py.

import os
import bpy
from bpy.props import (
    StringProperty,
)

from .. import T
from ..core import game_versions as gv


class GTATOOLS_OT_radar_generate(bpy.types.Operator):
    """Генерировать тайлы радара GTA SA"""
    bl_idname = "gtatools.radar_generate"
    bl_label = "INU: Generate Radars"
    bl_options = {'REGISTER'}

    mode: StringProperty(default='ALL')  # ALL, MENU, FULL, FULL_MENU, SPECIFIC

    def execute(self, context):
        scn = context.scene
        output_dir = bpy.path.abspath(scn.inu_settings.gtatools_radar_output)
        if not output_dir:
            self.report({'ERROR'}, T("Укажите папку для сохранения"))
            return {'CANCELLED'}
        os.makedirs(output_dir, exist_ok=True)

        height = scn.inu_settings.gtatools_radar_height
        size = scn.inu_settings.gtatools_radar_size

        # Radar coverage/grid by game: SA ±3000, 12×12; III/VC ±2000, 8×8
        # (tiles 500 m). Grid 0 = the game's own grid.
        grid, map_half = gv.radar_layout(
            gv.game_of_scene(scn), scn.inu_settings.gtatools_radar_grid)

        # Create temp camera
        cam_data = bpy.data.cameras.new("_RadarCam")
        cam_data.type = 'ORTHO'
        cam_data.clip_start = 1.0
        cam_data.clip_end = height + 5000.0
        cam_obj = bpy.data.objects.new("_RadarCam", cam_data)
        context.scene.collection.objects.link(cam_obj)
        cam_obj.location.z = height
        cam_obj.rotation_euler = (0, 0, 0)

        old_cam = scn.camera
        scn.camera = cam_obj

        # Save render settings
        old_x = scn.render.resolution_x
        old_y = scn.render.resolution_y
        old_path = scn.render.filepath
        old_format = scn.render.image_settings.file_format

        scn.render.image_settings.file_format = 'PNG'
        scn.render.resolution_x = size
        scn.render.resolution_y = size

        wm = context.window_manager
        count = 0

        if self.mode == 'FULL':
            # One full radar image
            cam_data.ortho_scale = map_half * 2
            cam_obj.location.x = 0
            cam_obj.location.y = 0
            filepath = os.path.join(output_dir, "FullRadar.png")
            scn.render.filepath = filepath
            bpy.ops.render.render(write_still=True)
            count = 1

        elif self.mode == 'FULL_MENU':
            cam_data.ortho_scale = map_half * 2
            cam_obj.location.x = 0
            cam_obj.location.y = 0
            filepath = os.path.join(output_dir, "FullMenuRadar.png")
            scn.render.filepath = filepath
            bpy.ops.render.render(write_still=True)
            count = 1

        elif self.mode == 'MENU':
            # 3x3 menu radar
            grid = 3
            sect_size = map_half * 2 / grid
            cam_data.ortho_scale = sect_size
            wm.progress_begin(0, grid * grid)
            names = [
                "MapTop01", "MapTop02", "MapTop03",
                "MapMid01", "MapMid02", "MapMid03",
                "MapBot01", "MapBot02", "MapBot03",
            ]
            idx = 0
            for y in range(grid):
                for x in range(grid):
                    cam_obj.location.x = -map_half + sect_size * (x + 0.5)
                    cam_obj.location.y = map_half - sect_size * (y + 0.5)
                    filepath = os.path.join(output_dir, names[idx] + ".png")
                    scn.render.filepath = filepath
                    bpy.ops.render.render(write_still=True)
                    idx += 1
                    wm.progress_update(idx)
            wm.progress_end()
            count = grid * grid

        elif self.mode == 'SPECIFIC':
            # Specific tiles by index
            sect_size = map_half * 2 / grid
            cam_data.ortho_scale = sect_size
            indices_str = scn.inu_settings.gtatools_radar_specific.strip()
            if not indices_str:
                self.report({'WARNING'}, T("Укажите индексы тайлов (например 0,1,8,9)"))
                bpy.data.objects.remove(cam_obj, do_unlink=True)
                bpy.data.cameras.remove(cam_data)
                scn.camera = old_cam
                scn.render.resolution_x = old_x
                scn.render.resolution_y = old_y
                scn.render.filepath = old_path
                scn.render.image_settings.file_format = old_format
                return {'CANCELLED'}
            indices = []
            for part in indices_str.split(','):
                part = part.strip()
                if part.isdigit():
                    idx = int(part)
                    if 0 <= idx < grid * grid:
                        indices.append(idx)

            wm.progress_begin(0, len(indices))
            for i, radar_idx in enumerate(indices):
                cam_obj.location.x, cam_obj.location.y = gv.radar_tile_center(
                    radar_idx, grid, map_half)
                name = f"radar{radar_idx:02d}"
                filepath = os.path.join(output_dir, name + ".png")
                scn.render.filepath = filepath
                bpy.ops.render.render(write_still=True)
                wm.progress_update(i + 1)
                count += 1
            wm.progress_end()

        else:
            # ALL: full grid
            sect_size = map_half * 2 / grid
            cam_data.ortho_scale = sect_size
            total = grid * grid
            wm.progress_begin(0, total)
            for y in range(grid):
                for x in range(grid):
                    radar_idx = y * grid + x
                    cam_obj.location.x, cam_obj.location.y = gv.radar_tile_center(
                        radar_idx, grid, map_half)
                    name = f"radar{radar_idx:02d}"
                    filepath = os.path.join(output_dir, name + ".png")
                    scn.render.filepath = filepath
                    bpy.ops.render.render(write_still=True)
                    wm.progress_update(radar_idx + 1)
                    count += 1
            wm.progress_end()

        # Cleanup
        scn.camera = old_cam
        scn.render.resolution_x = old_x
        scn.render.resolution_y = old_y
        scn.render.filepath = old_path
        scn.render.image_settings.file_format = old_format
        bpy.data.objects.remove(cam_obj, do_unlink=True)
        bpy.data.cameras.remove(cam_data)

        self.report({'INFO'}, f"Radar: {count} {T('тайлов сохранено')}")
        return {'FINISHED'}


class GTATOOLS_OT_radar_pack_txd(bpy.types.Operator):
    """Упаковать тайлы радара в TXD архивы (1 тайл = 1 TXD)"""
    bl_idname = "gtatools.radar_pack_txd"
    bl_label = "INU: Pack Radar to TXD"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scn = context.scene
        output_dir = bpy.path.abspath(scn.inu_settings.gtatools_radar_output)
        if not output_dir:
            self.report({'ERROR'}, T("Укажите папку для сохранения"))
            return {'CANCELLED'}

        grid, _ = gv.radar_layout(
            gv.game_of_scene(scn), scn.inu_settings.gtatools_radar_grid)
        backend = getattr(scn.inu_settings, 'gtatools_dxt_backend', 'numpy')

        txd_dir = os.path.join(output_dir, "txd")
        os.makedirs(txd_dir, exist_ok=True)

        wm = context.window_manager
        total = grid * grid
        wm.progress_begin(0, total)
        packed = 0

        # Create temp object with temp material for TXD export
        temp_mesh = bpy.data.meshes.new("_radar_tmp")
        temp_obj = bpy.data.objects.new("_radar_tmp", temp_mesh)
        context.scene.collection.objects.link(temp_obj)

        for radar_idx in range(total):
            name = f"radar{radar_idx:02d}"
            png_path = os.path.join(output_dir, name + ".png")

            if not os.path.isfile(png_path):
                wm.progress_update(radar_idx + 1)
                continue

            # Load image
            img = bpy.data.images.load(png_path, check_existing=False)
            img.name = name

            # Create temp material
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            bsdf = None
            for n in nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    bsdf = n
                    break
            if bsdf:
                tex_node = nodes.new('ShaderNodeTexImage')
                tex_node.image = img
                mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])

            # Assign to temp object
            temp_obj.data.materials.clear()
            temp_obj.data.materials.append(mat)

            # Select only temp object
            bpy.ops.object.select_all(action='DESELECT')
            temp_obj.select_set(True)
            context.view_layer.objects.active = temp_obj

            # Export TXD
            txd_path = os.path.join(txd_dir, name + ".txd")
            try:
                from ..tools.txd_export import export_txd
                result, msg, _ = export_txd(txd_path, context, selected_only=True, backend=backend)
                if result == {'FINISHED'}:
                    packed += 1
            except Exception as e:
                print(f"[Radar TXD] {name}: {e}")

            # Cleanup temp material and image
            bpy.data.materials.remove(mat)
            bpy.data.images.remove(img)
            wm.progress_update(radar_idx + 1)

        # Remove temp object
        bpy.data.objects.remove(temp_obj, do_unlink=True)
        bpy.data.meshes.remove(temp_mesh)

        wm.progress_end()
        self.report({'INFO'}, f"TXD: {packed} {T('архивов создано')}")
        return {'FINISHED'}


