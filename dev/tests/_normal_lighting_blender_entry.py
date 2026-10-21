"""GTA Normal lighting: live controls, colour export, and corners without support loops."""
from pathlib import Path
import runpy
import sys
import tempfile

import bpy
import numpy as np

state = runpy.run_path(str(Path(__file__).with_name('_normal_bake_blender_entry.py')))
B, low, layer, settings = (state[key] for key in ('B', 'low', 'layer', 'settings'))
from INU_tools.ops import bake_ops
from INU_tools.tools.bake.bake_composite import srgb_to_linear

# Upgrade a packed byte map while keeping users, name, metadata and pixels.
old = B.setup_target_image('NormalByteUpgrade', 16, 16)
old.colorspace_settings.name = 'Non-Color'
old['inu_bake_uv'] = 'OriginalUV'
byte_pixels = np.full((16, 16, 4), .6, dtype=np.float32)
B.write_numpy_to_image(old, byte_pixels)
saved_pixels = B.read_image_to_numpy(old).copy()
material = bpy.data.materials.new('NormalUpgradeUser')
material.use_nodes = True
image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
image_node.image = old
upgraded = B.setup_target_image('NormalByteUpgrade', 16, 16, float_buffer=True)
assert upgraded.is_float and image_node.image == upgraded
assert upgraded.name == 'NormalByteUpgrade' and upgraded['inu_bake_uv'] == 'OriginalUV'
np.testing.assert_array_equal(B.read_image_to_numpy(upgraded), saved_pixels)

base = low['inu_bake_base']
raw = bpy.data.images[f'{base}_{layer.uid}']
assert raw.colorspace_settings.name == 'Non-Color'
assert raw['inu_normal_space'] == 'OBJECT'
assert raw.is_float
normals_before = B.read_image_to_numpy(raw).copy()
diffuse = low.inu.gtatools_bake_layers.add()
diffuse.uid, diffuse.map_id = 'base_colour', 'DIFFUSE'
diffuse.enabled, diffuse.blend_mode = True, 'NORMAL'
image = B.setup_target_image(f'{base}_{diffuse.uid}', 1024, 1024)
image.colorspace_settings.name = 'Non-Color'
colour = np.empty((1024, 1024, 4), dtype=np.float32)
colour[:] = (.4, .2, .1, 1.)
B.write_numpy_to_image(image, colour)
image['inu_bake_uv'] = low['inu_bake_uv']
layer.normal_lighting = True
layer.desaturate = True  # Legacy toggle must not destroy RGB vector data.
layer.normal_diffuse = 0
layer.normal_specular = 0
layer.normal_ambient = 1
full = bake_ops._composite_stack_image(low.inu, base, 'NormalColourFull')
full_rgb = srgb_to_linear(B.read_image_to_numpy(full)[512, 512, :3])
np.testing.assert_allclose(full_rgb, (.4, .2, .1), atol=.012)
layer.normal_ambient = .5
dim = bake_ops._composite_stack_image(low.inu, base, 'NormalColourDim')
dim_rgb = srgb_to_linear(B.read_image_to_numpy(dim)[512, 512, :3])
np.testing.assert_allclose(dim_rgb, full_rgb * .5, atol=.012)
np.testing.assert_array_equal(normals_before, B.read_image_to_numpy(raw))
print('[NORMAL LIGHT] live ambient, RGB export parity and vector preservation: OK')

# Eight low vertices, no support edges, with smooth normals on every face.
bpy.ops.mesh.primitive_cube_add(size=2)
corner_low = bpy.context.object
corner_low.name = 'NoSupportCorners_low'
for face in corner_low.data.polygons:
    face.use_smooth = True
corner_high = corner_low.copy()
corner_high.data = corner_low.data.copy()
corner_high.name = 'NoSupportCorners_hi'
bpy.context.scene.collection.objects.link(corner_high)
bevel = corner_high.modifiers.new('SourceBevel', 'BEVEL')
bevel.width, bevel.segments = .15, 8
bevel.harden_normals = True
bevel.face_strength_mode = 'FSTR_ALL'
weighted = corner_high.modifiers.new('SourcePlanes', 'WEIGHTED_NORMAL')
weighted.keep_sharp = True
weighted.use_face_influence = True
for obj in bpy.context.view_layer.objects:
    obj.select_set(obj == corner_low)
bpy.context.view_layer.objects.active = corner_low
settings.gtatools_bake_mode = 'HILOW'
settings.gtatools_bake_resolution = '256'
normal_layer = corner_low.inu.gtatools_bake_layers.add()
normal_layer.uid, normal_layer.map_id = 'normal_corners', 'NORMAL'
normal_layer.enabled = True
normal_layer.normal_specular = .3
normal_layer.expanded = True
normal_layer.desaturate = False
original_coords = [tuple(vertex.co) for vertex in corner_low.data.vertices]
assert bpy.ops.gtatools.bake_run(only_uid=normal_layer.uid) == {'FINISHED'}
corner_base = corner_low['inu_bake_base']
corner_raw = bpy.data.images[f'{corner_base}_{normal_layer.uid}']
pixels = B.read_image_to_numpy(corner_raw)
uv = corner_low.data.uv_layers.active
face_samples = []
for face in corner_low.data.polygons:
    points = np.array([uv.data[i].uv[:] for i in face.loop_indices])
    for a, b in ((.35, .35), (.65, .35), (.35, .65), (.65, .65)):
        point = points[0]*(1-a)*(1-b) + points[1]*a*(1-b) + points[2]*a*b + points[3]*(1-a)*b
        x, y = np.clip((point * 256).astype(int), 0, 255)
        face_samples.append((x, y, np.array(face.normal)))
assert len(corner_low.data.vertices) == 8
assert original_coords == [tuple(vertex.co) for vertex in corner_low.data.vertices]
assert all(face.use_smooth for face in corner_low.data.polygons)
print('[NORMAL CORNERS] eight vertices, smooth low, no support loops: OK')
# Smooth source normals retain more than byte precision on curved pixels.
fractional = np.abs(pixels[..., :3] * 255 - np.round(pixels[..., :3] * 255))
assert corner_raw.is_float and np.count_nonzero(fractional > .05) > 100

diffuse_layer = corner_low.inu.gtatools_bake_layers.add()
diffuse_layer.uid, diffuse_layer.map_id = 'colour', 'DIFFUSE'
diffuse_layer.enabled, diffuse_layer.blend_mode = True, 'NORMAL'
diffuse_image = B.setup_target_image(f'{corner_base}_colour', 256, 256)
diffuse_image.colorspace_settings.name = 'Non-Color'
yy, xx = np.indices((256, 256))
pattern = .75 + .25 * ((xx // 12 + yy // 12) % 2)
diffuse_pixels = np.ones((256, 256, 4), dtype=np.float32)
diffuse_pixels[..., :3] = np.array((.38, .17, .07)) * pattern[..., None]
B.write_numpy_to_image(diffuse_image, diffuse_pixels)
diffuse_image['inu_bake_uv'] = corner_low['inu_bake_uv']
bake_ops.rebuild_live_composite(corner_low)

from INU_tools.tools.bake.bake_normal import normal_light_directions
for mode in ('EDGES', 'ALL_SIDES', 'DIRECTIONAL'):
    normal_layer.normal_light_mode = mode
    normal_layer.normal_ambient = .65
    normal_layer.normal_diffuse = .45
    normal_layer.normal_specular = 0
    result = bake_ops._composite_stack_image(corner_low.inu, corner_base, 'NormalMode_' + mode)
    output = srgb_to_linear(B.read_image_to_numpy(result)[..., :3])
    light, _ = normal_light_directions(bake_ops._layer_pattern_settings(normal_layer))
    for x, y, face_normal in face_samples:
        factor = (1. if mode == 'EDGES' else (.65 + .45 / 2 if mode == 'ALL_SIDES'
                   else .65 + .45 * max(0., float(face_normal @ light))))
        np.testing.assert_allclose(output[y, x], diffuse_pixels[y, x, :3] * factor, atol=.012)
normal_layer.normal_light_mode = 'DIRECTIONAL'
normal_layer.normal_specular = .3
print('[NORMAL MODES] decoded smooth Low normals preserve planes in all light modes: OK')

# UV mode generates a temporary rounded source from the user's selection.
bpy.ops.mesh.primitive_cube_add(size=2, location=(6, 0, 0))
generated = bpy.context.object
generated.name = 'GeneratedRounding'
for face in generated.data.polygons:
    face.use_smooth = True
for other in bpy.context.view_layer.objects:
    other.select_set(other == generated)
bpy.context.view_layer.objects.active = generated
settings.gtatools_bake_mode = 'UV'
generated_layer = generated.inu.gtatools_bake_layers.add()
generated_layer.uid, generated_layer.map_id = 'generated_edges', 'NORMAL'
generated_layer.normal_bevel = True
generated_layer.normal_bevel_width = .2
generated_layer.normal_light_mode = 'EDGES'
coords_before = [vertex.co[:] for vertex in generated.data.vertices]
uv_before = [item.uv[:] for item in generated.data.uv_layers.active.data]
objects_before, meshes_before = set(bpy.data.objects), set(bpy.data.meshes)
for edge in generated.data.edges:
    edge.select = edge.index == 0
from INU_tools.tools.bake.bake_normal import make_normal_bevel_source
source = make_normal_bevel_source(bpy.context, generated, dict(normal_bevel_width=.2))
evaluated = source.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
for face in evaluated.polygons:
    if face.area > 1:
        assert all(evaluated.corner_normals[i].vector.dot(face.normal) > .999
                   for i in face.loop_indices), face.index
source_mesh = source.data
bpy.data.objects.remove(source, do_unlink=True)
bpy.data.meshes.remove(source_mesh)
assert bpy.ops.gtatools.bake_run(only_uid=generated_layer.uid) == {'FINISHED'}
generated_base = generated['inu_bake_base']
generated_raw = bpy.data.images[f'{generated_base}_{generated_layer.uid}']
selected_pixels = B.read_image_to_numpy(generated_raw).copy()
assert bake_ops._stored_bevel_indices(generated, generated_layer.uid, 'EDGE') == [0]
assert set(bpy.data.objects) == objects_before and set(bpy.data.meshes) == meshes_before
assert bpy.ops.gtatools.bake_select_area(uid=generated_layer.uid, domain='EDGE') == {'FINISHED'}
bpy.ops.object.mode_set(mode='OBJECT')
assert [edge.index for edge in generated.data.edges if edge.select] == [0]
generated_layer.normal_bevel_width = .08
generated_layer.normal_bevel_profile = .7
assert bpy.ops.gtatools.bake_run(only_uid=generated_layer.uid) == {'FINISHED'}
changed_pixels = B.read_image_to_numpy(generated_raw).copy()
assert np.count_nonzero(np.abs(changed_pixels - selected_pixels) > .03) > 100
selected_pixels = changed_pixels

face_layer = generated.inu.gtatools_bake_layers.add()
face_layer.uid, face_layer.map_id = 'generated_faces', 'NORMAL'
face_layer.normal_bevel = True
face_layer.normal_bevel_selection = 'FACE'
face_layer.normal_bevel_width = .12
for face in generated.data.polygons:
    face.select = face.index == 2
assert bpy.ops.gtatools.bake_run(only_uid=face_layer.uid) == {'FINISHED'}
assert bake_ops._stored_bevel_indices(generated, face_layer.uid, 'FACE') == [2]
np.testing.assert_array_equal(B.read_image_to_numpy(generated_raw), selected_pixels)
assert coords_before == [vertex.co[:] for vertex in generated.data.vertices]
assert uv_before == [item.uv[:] for item in generated.data.uv_layers.active.data]
assert all(face.use_smooth for face in generated.data.polygons)
face_raw = bpy.data.images[f'{generated_base}_{face_layer.uid}']
assert np.count_nonzero(np.abs(B.read_image_to_numpy(face_raw) - selected_pixels) > .03) > 100
assert set(bpy.data.objects) == objects_before and set(bpy.data.meshes) == meshes_before
print('[NORMAL GENERATED] selected edges/faces, independent maps, restore, no Hi, unchanged low and UV: OK')
for edge in generated.data.edges:
    edge.select = False
try:
    make_normal_bevel_source(bpy.context, generated, {})
except RuntimeError:
    pass
else:
    raise AssertionError('Empty rounding selection must be reported')
assert set(bpy.data.objects) == objects_before and set(bpy.data.meshes) == meshes_before

# Rotated and mirrored faces share the entire UV square. Absolute normals
# would turn flat sides into false bevels; relative vectors must stay neutral.
bpy.ops.mesh.primitive_cube_add(size=2, location=(12, 0, 0))
stacked = bpy.context.object
stacked.name = 'StackedNormal'
for face in stacked.data.polygons:
    face.use_smooth = False
    for index, loop in enumerate(face.loop_indices):
        u, v = ((0,0), (1,0), (1,1), (0,1))[index]
        stacked.data.uv_layers.active.data[loop].uv = (1-u if face.index % 2 else u, v)
uv_stacked = [item.uv[:] for item in stacked.data.uv_layers.active.data]
stacked_layer = stacked.inu.gtatools_bake_layers.add()
stacked_layer.uid, stacked_layer.map_id = 'stacked_normal', 'NORMAL'
stacked_layer.normal_bevel = True
stacked_layer.normal_bevel_width = .15
stacked_layer.normal_light_mode = 'EDGES'
assert bpy.ops.gtatools.bake_run(only_uid=stacked_layer.uid) == {'FINISHED'}
stacked_base = stacked['inu_bake_base']
stacked_image = bpy.data.images[f'{stacked_base}_{stacked_layer.uid}']
assert stacked_image['inu_normal_space'] == 'TANGENT'
stacked_pixels = B.read_image_to_numpy(stacked_image)
np.testing.assert_allclose(stacked_pixels[128,128,:3], (.5,.5,1.), atol=.002)
assert stacked_pixels[...,2].min() < .95  # The map also contains actual rounding.
stacked_diffuse = stacked.inu.gtatools_bake_layers.add()
stacked_diffuse.uid, stacked_diffuse.map_id = 'stacked_colour', 'DIFFUSE'
stacked_diffuse.blend_mode = 'NORMAL'
stacked_colour = B.setup_target_image(f'{stacked_base}_{stacked_diffuse.uid}', 256, 256)
stacked_colour.colorspace_settings.name = 'Non-Color'
colour = np.ones((256,256,4), dtype=np.float32)
colour[..., :3] = (.4,.2,.1)
B.write_numpy_to_image(stacked_colour, colour)
for mode, factor in (('EDGES', 1.), ('ALL_SIDES', .65 + .45 / 2)):
    stacked_layer.normal_light_mode = mode
    result = bake_ops._composite_stack_image(stacked.inu, stacked_base, 'StackedMode_' + mode)
    output = srgb_to_linear(B.read_image_to_numpy(result)[..., :3])
    np.testing.assert_allclose(output[128,128], np.array((.4,.2,.1))*factor, atol=.01)
assert uv_stacked == [item.uv[:] for item in stacked.data.uv_layers.active.data]
print('[NORMAL STACKED] rotated/mirrored shared UV, neutral planes, rounding and RGB export: OK')

# Oversized rounding on neighbouring posts must not project the other post's
# bevels into flat faces (requested width 5 used to produce a cage offset 10).
vertices, faces = [], []
for x1,y0,y1 in ((2.,0.,2.),(1.,3.,4.)):
    start = len(vertices)
    vertices.extend([(0,y0,-2),(x1,y0,-2),(x1,y1,-2),(0,y1,-2),
                     (0,y0,2),(x1,y0,2),(x1,y1,2),(0,y1,2)])
    faces.extend([tuple(start+i for i in face) for face in
                  ((0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))])
post_mesh = bpy.data.meshes.new('NeighbourNormal')
post_mesh.from_pydata(vertices,[],faces)
posts = bpy.data.objects.new('NeighbourNormal',post_mesh)
bpy.context.scene.collection.objects.link(posts)
post_uv = post_mesh.uv_layers.new(name='StackedStrips')
for face in post_mesh.polygons:
    row = 0 if face.index < 4 else .5
    for loop,(u,v) in zip(face.loop_indices,((0,0),(0,.5),(1,.5),(1,0))):
        post_uv.data[loop].uv = (u,row+v)
for edge in post_mesh.edges:
    edge.select = abs(post_mesh.vertices[edge.vertices[0]].co.z
                      -post_mesh.vertices[edge.vertices[1]].co.z)>1
for other in bpy.context.view_layer.objects: other.select_set(other==posts)
bpy.context.view_layer.objects.active = posts
post_layer = posts.inu.gtatools_bake_layers.add()
post_layer.uid,post_layer.map_id = 'nearby_rounding','NORMAL'
post_layer.normal_bevel=True
post_layer.normal_bevel_width=5
post_layer.normal_bevel_segments=2
post_layer.normal_bevel_profile=.99
assert bpy.ops.gtatools.bake_run(only_uid=post_layer.uid)=={'FINISHED'}
post_image=bpy.data.images[f'{posts["inu_bake_base"]}_{post_layer.uid}']
post_pixels=B.read_image_to_numpy(post_image)
assert post_pixels[...,2].min()*2-1 > .68
print('[NORMAL NEIGHBOURS] oversized width, nearby posts, projection stays on local rounding: OK')

# Put the visual example back on the original corner cube.
settings.gtatools_bake_mode = 'UV'
for other in bpy.context.view_layer.objects:
    other.select_set(other == corner_low)
bpy.context.view_layer.objects.active = corner_low
normal_layer.normal_bevel = True
normal_layer.normal_bevel_width = .15
for edge in corner_low.data.edges:
    edge.select = True
assert bpy.ops.gtatools.bake_run(only_uid=normal_layer.uid) == {'FINISHED'}
bake_ops.rebuild_live_composite(corner_low)

artifact_arg = next((arg.split('=', 1)[1] for arg in sys.argv if arg.startswith('--artifacts=')), None)
if artifact_arg:
    from mathutils import Vector
    out_dir = Path(artifact_arg)
    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.camera_add(location=(4, -6, 4))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type, camera.data.ortho_scale = 'ORTHO', 4.2
    bpy.context.scene.camera = camera
    corner_high.hide_render = True
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj != corner_low:
            obj.hide_render = True
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 8
    scene.render.resolution_x = scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'Standard'
    scene.render.filepath = str(out_dir / 'normal-corners-lighting.png')
    bpy.ops.render.render(write_still=True)
    for obj in bpy.context.view_layer.objects:
        obj.select_set(obj == corner_low)
    bpy.context.view_layer.objects.active = corner_low
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'MATERIAL'
                area.spaces.active.show_region_ui = True
    bpy.ops.wm.save_as_mainfile(filepath=str(out_dir / 'normal-rounding-demo.blend'))

with tempfile.TemporaryDirectory(prefix='inu_normal_float_') as folder:
    name = generated_raw.name
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(folder) / 'normal.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(Path(folder) / 'normal.blend'))
    reopened = bpy.data.images[name]
    assert reopened.is_float and reopened.packed_file is not None
    np.testing.assert_allclose(B.read_image_to_numpy(reopened), selected_pixels, atol=1e-6)
    assert bake_ops._stored_bevel_indices(bpy.data.objects['GeneratedRounding'], 'generated_edges', 'EDGE') == [0]
print('[NORMAL PERSISTENCE] packed float vectors and selection survive reopening: OK')
