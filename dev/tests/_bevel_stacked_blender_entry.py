"""Native Bevel/Bevel-basis selection regression with stacked UVs; no game assets."""
from pathlib import Path
import sys
import tempfile

import bpy
import numpy as np
import addon_utils

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
addon_utils.enable('INU_tools', default_set=False,
    handle_error=lambda error: (_ for _ in ()).throw(error))
from INU_tools.tools import bake as B

mesh = bpy.data.meshes.new('StackedBevelTest')
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                  (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], [],
                 [(0, 1, 2, 3), (4, 5, 6, 7)])
obj = bpy.data.objects.new('StackedBevelTest', mesh)
bpy.context.scene.collection.objects.link(obj)
for other in bpy.context.view_layer.objects:
    other.select_set(other == obj)
bpy.context.view_layer.objects.active = obj
uv = mesh.uv_layers.new(name='Trim')
coordinates = np.array([(0, 0), (1, 0), (1, 1), (0, 1)] * 2, dtype=np.float32)
uv.data.foreach_set('uv', coordinates.ravel())
settings = bpy.context.scene.inu_settings
settings.gtatools_bake_mode = 'UV'
settings.gtatools_bake_res_x = 64
settings.gtatools_bake_res_y = 64
settings.gtatools_bake_aa = '2'
settings.gtatools_bake_margin = 2
settings.gtatools_bake_bevel_size = .2
settings.gtatools_bake_selected_edges = True
settings.gtatools_bake_selected_faces = False
layer = obj.inu.gtatools_bake_layers.add()
layer.uid = 'edge_test'
layer.map_id = 'BEVEL'
layer.blend_mode = 'ADD'

def bake():
    assert bpy.ops.gtatools.bake_run(only_uid=layer.uid) == {'FINISHED'}
    assert len(mesh.uv_layers) == 1
    after = np.empty_like(coordinates).ravel()
    uv.data.foreach_get('uv', after)
    assert np.array_equal(coordinates, after.reshape(-1, 2))
    assert not any(a.name.startswith('INU_BevelEdgeMask') for a in mesh.attributes)
    return B.read_image_to_numpy(bpy.data.images[f"{obj['inu_bake_base']}_{layer.uid}"])

for edge in mesh.edges:
    edge.select = set(edge.vertices) == {0, 1}
result = bake()
assert result[2, 32, 0] > .5       # First face's edge survives the black copy.
assert result[32, 32, 0] == 0

for edge in mesh.edges:
    edge.select = False
empty = bake()                     # Also tests replacing a packed target image.
assert not np.any(empty[..., :3])

settings.gtatools_bake_selected_edges = False
settings.gtatools_bake_selected_faces = True
for face in mesh.polygons:
    face.select = face.index == 0
faces = bake()
assert faces[2, 32, 0] > .5 and faces[-3, 32, 0] > .5
assert faces[32, 32, 0] == 0
assert not any(o.name.endswith('__bake_sel') for o in bpy.data.objects)
print('[STACKED BEVEL] selected edges, empty packed rebake and selected faces: OK')

# Effects using a Bevel basis retain independent masks and selections, without
# requiring a visible Bevel layer. Rebaking another effect must not replace them.
from INU_tools.ops.bake_ops import _stored_bevel_indices
obj.inu.gtatools_bake_layers.clear()
settings.gtatools_bake_samples = 16
settings.gtatools_bake_denoise = False
settings.gtatools_bake_selected_edges = True
settings.gtatools_bake_selected_faces = False

def effect(uid, mid):
    item = obj.inu.gtatools_bake_layers.add()
    item.uid, item.map_id = uid, mid
    item.effect_basis = 'BEVEL'
    item.blend_mode = 'ADD'
    return item

def basis_image(uid):
    return bpy.data.images[f"{obj['inu_bake_base']}_{uid}__bevel_basis"]

first = effect('wear_first', 'EDGEWEAR')
second = effect('wear_second', 'EDGEWEAR')
dirt = effect('dirt_faces', 'DIRT')
for edge in mesh.edges:
    edge.select = set(edge.vertices) == {0, 1}
first_indices = [edge.index for edge in mesh.edges if edge.select]
assert bpy.ops.gtatools.bake_run(only_uid=first.uid) == {'FINISHED'}
first_mask = B.read_image_to_numpy(basis_image(first.uid)).copy()
assert first_mask[2, 32, 0] > .5 and first_mask[-3, 32, 0] == 0
assert _stored_bevel_indices(obj, first.uid, 'EDGE') == first_indices
for edge in mesh.edges:
    edge.select = set(edge.vertices) == {2, 3}
second_indices = [edge.index for edge in mesh.edges if edge.select]
assert bpy.ops.gtatools.bake_run(only_uid=second.uid) == {'FINISHED'}
second_mask = B.read_image_to_numpy(basis_image(second.uid))
assert second_mask[-3, 32, 0] > .5 and second_mask[2, 32, 0] == 0
np.testing.assert_array_equal(first_mask, B.read_image_to_numpy(basis_image(first.uid)))
assert _stored_bevel_indices(obj, first.uid, 'EDGE') == first_indices
assert _stored_bevel_indices(obj, second.uid, 'EDGE') == second_indices

settings.gtatools_bake_selected_edges = False
settings.gtatools_bake_selected_faces = True
for face in mesh.polygons:
    face.select = face.index == 1
assert bpy.ops.gtatools.bake_run(only_uid=dirt.uid) == {'FINISHED'}
assert _stored_bevel_indices(obj, dirt.uid, 'FACE') == [1]
assert not _stored_bevel_indices(obj, dirt.uid, 'EDGE')
assert B.read_image_to_numpy(basis_image(dirt.uid))[2, 32, 0] > .5

def restore(uid, domain, expected):
    assert bpy.ops.gtatools.bake_select_area(uid=uid, domain=domain) == {'FINISHED'}
    assert obj.mode == 'EDIT'
    bpy.ops.object.mode_set(mode='OBJECT')
    elements = mesh.edges if domain == 'EDGE' else mesh.polygons
    assert [element.index for element in elements if element.select] == expected

restore(first.uid, 'EDGE', first_indices)
restore(second.uid, 'EDGE', second_indices)
restore(dirt.uid, 'FACE', [1])
with tempfile.TemporaryDirectory(prefix='inu_bevel_basis_') as folder:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(folder) / 'basis.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(Path(folder) / 'basis.blend'))
    obj = bpy.data.objects['StackedBevelTest']
    mesh = obj.data
    restore('wear_first', 'EDGE', first_indices)
    restore('dirt_faces', 'FACE', [1])
    np.testing.assert_array_equal(first_mask, B.read_image_to_numpy(basis_image('wear_first')))
    assert basis_image('wear_first').packed_file is not None
    assert len(mesh.uv_layers) == 1
    after = np.empty_like(coordinates).ravel()
    mesh.uv_layers['Trim'].data.foreach_get('uv', after)
    np.testing.assert_array_equal(coordinates, after.reshape(-1, 2))
print('[BEVEL BASIS] independent edges/faces, restore and packed masks after reopen: OK')
