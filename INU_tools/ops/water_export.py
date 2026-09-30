# INU_tools.ops.water_export — Export Blender mesh to water.dat

import bpy
import bmesh
from ..core.water import WaterFile, WaterPolygon, WaterVertex, write_water


def export_water(filepath: str, objects=None):
    """Export selected mesh objects as water.dat.

    Reads water parameters from vertex custom float layers.
    Each face becomes a water polygon (3 or 4 vertices).
    Water flag from object custom property 'water_flag'.
    Returns ``(count, skipped)`` — polygons written and faces dropped
    because water.dat holds only triangles and quads.
    """
    if objects is None:
        objects = [o for o in bpy.context.selected_objects if o.type == 'MESH']

    water = WaterFile()
    skipped = 0

    for obj in objects:
        flag = obj.get('water_flag', 1)

        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()

        # Get parameter layers
        speed_x_layer = bm.verts.layers.float.get('water_speed_x')
        speed_y_layer = bm.verts.layers.float.get('water_speed_y')
        speed_z_layer = bm.verts.layers.float.get('water_speed_z')
        wave_layer = bm.verts.layers.float.get('water_wave_height')

        mat_w = obj.matrix_world

        for face in bm.faces:
            if len(face.verts) not in (3, 4):
                skipped += 1
                continue

            poly = WaterPolygon(flag=flag)

            verts_list = list(face.verts)
            # Restore original water.dat vertex order
            # Import swaps verts 2,3 for correct Blender normals — reverse here
            if len(verts_list) == 4:
                verts_list = [verts_list[0], verts_list[1], verts_list[3], verts_list[2]]
            elif len(verts_list) == 3:
                verts_list = [verts_list[0], verts_list[2], verts_list[1]]

            for vert in verts_list:
                co = mat_w @ vert.co
                wv = WaterVertex(
                    x=co.x, y=co.y, z=co.z,
                    speed_x=vert[speed_x_layer] if speed_x_layer else 0.0,
                    speed_y=vert[speed_y_layer] if speed_y_layer else 0.0,
                    speed_z=vert[speed_z_layer] if speed_z_layer else 0.0,
                    wave_height=vert[wave_layer] if wave_layer else 0.0,
                )
                poly.vertices.append(wv)

            water.polygons.append(poly)

        bm.free()

    count = write_water(filepath, water)
    return count, skipped
