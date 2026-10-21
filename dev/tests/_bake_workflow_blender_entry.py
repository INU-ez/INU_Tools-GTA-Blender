"""Native workflow regression. Pass -- --ui to inspect the resulting scene."""
import json
import os
from pathlib import Path
import sys
import tempfile

import addon_utils
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
addon_utils.enable('INU_tools', default_set=False,
    handle_error=lambda error: (_ for _ in ()).throw(error))
from INU_tools.ops import bake_ops as ops
from INU_tools.ops.bake_workflow_ops import _apply_rows, GTATOOLS_OT_bake_batch
from INU_tools.tools import bake as B
from INU_tools.tools.bake.bake_workflow import STAMP, bake_stamp, stack_data, stamp_status, mesh_digest

obj = bpy.context.active_object
obj.name = 'Workflow_A'
s = bpy.context.scene.inu_settings
s.gtatools_bake_mode = 'UV'
s.gtatools_bake_res_x = s.gtatools_bake_res_y = 32
s.gtatools_bake_aa = '1'
s.gtatools_bake_samples = 1
s.gtatools_bake_margin = 1
s.gtatools_bake_denoise = False
s.gtatools_bake_selected_edges = False
s.gtatools_bake_selected_faces = False
uv = obj.data.uv_layers.active.name
obj['inu_bake_base'], obj['inu_bake_uv'] = obj.name, uv
layers = obj.inu.gtatools_bake_layers
base = layers.add()
base.uid, base.map_id, base.blend_mode = 'base', 'DIFFUSE', 'NORMAL'
dirt = layers.add()
dirt.uid, dirt.map_id, dirt.blend_mode = 'dirt', 'DIRT', 'MULTIPLY'
layers.move(1, 0)
dirt = layers[0]
base = layers[1]
dirt.use_color = True
dirt.color_dark = (.12, .04, .01)
dirt.color_light = (1., 1., 1.)
dirt.effect_basis = 'DIRECTION'
dirt.direction_mode = 'BOTTOM'
dirt.ramp_low, dirt.ramp_high, dirt.ramp_smooth = .1, .9, True
mask = dirt.masks.add()
mask.basis = 'PATTERN'
dirt.surface_pattern = 'NOISE'
dirt.pattern_strength = .5
for layer in layers:
    image = ops._ensure_paint_image(f'{obj.name}_{layer.uid}', 32, 32)
    image[STAMP] = json.dumps(bake_stamp(obj, s, layer, uv))
obj['inu_bake_mode_live'] = 1
ops._apply_result_material(obj)

# Check registered control/property bindings through Python, without desktop input.
from INU_tools.ui.bake_workflow_ui import (draw_workflow, draw_status,
    draw_surface_controls, draw_game_preview)
class LayoutProbe:
    def row(self, **kwargs): return self
    def column(self, **kwargs): return self
    def box(self): return self
    def prop(self, owner, key, **kwargs):
        assert hasattr(owner, key), key
    def label(self, **kwargs): pass
    def operator(self, name, **kwargs):
        module, operation = name.split('.')
        rna = getattr(getattr(bpy.ops, module), operation).get_rna_type()
        class Proxy:
            def __setattr__(self, key, value):
                assert key in rna.properties, (name, key)
        return Proxy()
probe_layout = LayoutProbe()
draw_workflow(probe_layout, bpy.context, obj)
draw_status(probe_layout, bpy.context, obj, dirt, None)
draw_surface_controls(probe_layout, dirt)
draw_game_preview(probe_layout, s, obj)
first_material = obj.active_material
first_nodes = [n.as_pointer() for n in first_material.node_tree.nodes]

# Independent raw, composite and overlay previews, including inactive owners.
other = obj.copy()
other.data = obj.data.copy()
other.name = 'Workflow_B'
bpy.context.scene.collection.objects.link(other)
other['inu_bake_base'] = other.name
for layer in other.inu.gtatools_bake_layers:
    ops._ensure_paint_image(f'{other.name}_{layer.uid}', 32, 32)
ops._apply_result_material(other)
assert other.active_material != first_material
other.inu.gtatools_bake_layers[0].opacity = .2
assert first_nodes == [n.as_pointer() for n in first_material.node_tree.nodes]
# Linked duplicates share geometry but must have separate material overrides.
linked = obj.copy()
linked.name = 'Workflow_Linked'
bpy.context.scene.collection.objects.link(linked)
ops._restore_materials(linked)
original_materials = list(obj.data.materials)
ops._apply_result_material(linked)
assert linked.data == obj.data and linked.active_material != obj.active_material
assert list(obj.data.materials) == original_materials
ops._restore_materials(linked)
assert obj.active_material == first_material
linked.hide_render = True
linked.hide_set(True)
other['inu_bake_mode_live'] = 0
other['inu_bake_image'] = other.name + '_base'
ops._apply_result_material(other)
raw_other = other.active_material
obj['inu_bake_mode_live'] = 0
obj['inu_bake_image'] = obj.name + '_base'
ops._apply_result_material(obj)
assert obj.active_material != raw_other
obj['inu_bake_mode_live'] = 1
ops._apply_result_material(obj)

# Live colour/pattern edits keep the geometry stamp ready; width and UV don't.
image = bpy.data.images[obj.name + '_dirt']
saved = bake_stamp(obj, s, dirt, uv)
dirt.opacity = .8
dirt.pattern_seed += 1
assert stamp_status(image, bake_stamp(obj, s, dirt, uv)) == 'READY'
coord = obj.data.uv_layers.active.data[0].uv.copy()
obj.data.uv_layers.active.data[0].uv.x += .01
assert stamp_status(image, bake_stamp(obj, s, dirt, uv)) == 'STALE'
obj.data.uv_layers.active.data[0].uv = coord
assert mesh_digest(obj, uv) == saved['mesh']
bpy.ops.object.mode_set(mode='EDIT')
assert mesh_digest(obj, uv) == saved['mesh'], 'Edit-mode digest differs without edits'
bpy.ops.object.mode_set(mode='OBJECT')

# RGB/alpha export uses live mask operations, rather than the raw white mask.
original_uvs = np.array([loop.uv[:] for loop in obj.data.uv_layers.active.data])
for mode in ('TOP', 'BOTTOM', 'SLOPE', 'STREAK'):
    dirt.direction_mode = mode
    output = ops._composite_stack_image(obj.inu, obj.name, 'Workflow_RGB')
    assert output and np.isfinite(B.read_image_to_numpy(output)).all()
pixels_bottom = None
dirt.direction_mode = 'BOTTOM'
dirt.pattern_strength = 0.
output = ops._composite_stack_image(obj.inu, obj.name, 'Workflow_RGB')
pixels_bottom = B.read_image_to_numpy(output).copy()
dirt.direction = (0., 0., -1.)
output = ops._composite_stack_image(obj.inu, obj.name, 'Workflow_RGB')
assert np.max(np.abs(pixels_bottom - B.read_image_to_numpy(output))) > .05
dirt.direction = (0., 0., 1.)
for operation in ('MULTIPLY', 'ADD', 'SUBTRACT'):
    mask.operation = operation
    output = ops._composite_stack_image(obj.inu, obj.name, 'Workflow_RGB')
    assert output is not None
assert np.array_equal(original_uvs, [loop.uv[:] for loop in obj.data.uv_layers.active.data])

# The same live mask also drives decal alpha in stack and single-layer export.
mask.operation = 'MULTIPLY'
dirt.as_decal = True
decal_full = ops._composite_stack_image(obj.inu, obj.name, 'Workflow_DecalFull')
decal_single = ops._single_layer_composite_image(obj.inu, obj.name, dirt, 'Workflow_DecalSingle')
alpha = B.read_image_to_numpy(decal_single)[..., 3].copy()
assert alpha.max() > .5 and alpha.min() < .1
np.testing.assert_allclose(alpha, B.read_image_to_numpy(decal_full)[..., 3], atol=.01)
dirt.direction = (0., 0., -1.)
decal_single = ops._single_layer_composite_image(obj.inu, obj.name, dirt, 'Workflow_DecalSingle')
assert np.max(np.abs(alpha - B.read_image_to_numpy(decal_single)[..., 3])) > .2
dirt.direction = (0., 0., 1.)
dirt.as_decal = False

# A secondary Bevel input must bake a private mask and remember its own area.
from INU_tools.tools.bake.bake_composite import bevel_basis_key
edge_state = [edge.select for edge in obj.data.edges]
for edge in obj.data.edges:
    edge.select = edge.index == 0
s.gtatools_bake_selected_edges = True
mask.basis = 'BEVEL'
assert bpy.ops.gtatools.bake_run(only_uid=dirt.uid) == {'FINISHED'}
assert bpy.data.images.get(f"{obj.get('inu_bake_base')}_{bevel_basis_key(dirt.uid)}")
assert ops._stored_bevel_indices(obj, dirt.uid, 'EDGE') == [0]
mask.basis = 'PATTERN'
s.gtatools_bake_selected_edges = False
for edge, selected in zip(obj.data.edges, edge_state):
    edge.select = selected

# Portable presets preserve scalar/vector parameters and mask links, not UIDs.
paint = layers.add()
paint.map_id, paint.uid, paint.name = 'PAINT', 'paint', 'Маска'
dirt.paint_mask_uid = paint.uid
data = stack_data(layers)
version_tag = f'{bpy.app.version[0]}_{bpy.app.version[1]}'
path = Path(tempfile.gettempdir()) / f'inu_workflow_preset_{version_tag}.json'
assert bpy.ops.gtatools.bake_preset_save(filepath=str(path)) == {'FINISHED'}
_apply_rows(other, data, True)
copy = other.inu.gtatools_bake_layers
assert copy[0].uid != dirt.uid and copy[0].direction[:] == dirt.direction[:]
assert copy[0].masks[0].operation == mask.operation
assert copy[0].paint_mask_uid == copy[-1].uid
assert not ops._has_bevel_selection(other, copy[0].uid, 'EDGE')
bpy.context.view_layer.objects.active = other
assert bpy.ops.gtatools.bake_preset_load(filepath=str(path), replace=True) == {'FINISHED'}
assert len(copy) == len(layers) and copy[0].paint_mask_uid == copy[-1].uid
bpy.context.view_layer.objects.active = obj
old_uids = [layer.uid for layer in copy]
invalid = json.loads(json.dumps(data))
invalid['layers'][0]['masks'][0]['operation'] = 'INVALID'
try:
    _apply_rows(other, invalid, True)
    raise AssertionError('Invalid preset accepted')
except (TypeError, ValueError):
    pass
assert old_uids == [layer.uid for layer in copy], 'Failed preset damaged the previous stack'

# Diagnostics are read-only; face selection survives edit-mode transitions.
obj.inu.gtatools_bake_layers_index = 0
assert bpy.ops.gtatools.bake_diagnose() == {'FINISHED'}
assert np.array_equal(original_uvs, [loop.uv[:] for loop in obj.data.uv_layers.active.data])
assert 'complete' in json.loads(obj['inu_bake_diagnostics'])

# Queue bakes actual 32px Diffuse for both models and restores active/selection.
for target in (obj, other):
    ops._restore_materials(target)
    target.inu.gtatools_bake_layers.clear()
    layer = target.inu.gtatools_bake_layers.add()
    layer.uid, layer.map_id, layer.blend_mode = 'batch', 'DIFFUSE', 'NORMAL'
    target.select_set(True)
assert bpy.ops.gtatools.bake_batch(only_stale=False) == {'FINISHED'}
assert bpy.context.active_object == obj
assert all(target.select_get() for target in (obj, other))
for target in (obj, other):
    image = bpy.data.images[f'{target.get("inu_bake_base")}_batch']
    assert image.size[:] == (32, 32)
    assert stamp_status(image, bake_stamp(target, s, target.inu.gtatools_bake_layers[0], uv)) == 'READY'

calls = []
original_bake = B.bake_one_map
def recording_bake(*args, **kwargs):
    calls.append(args[2].name)
    return original_bake(*args, **kwargs)
B.bake_one_map = recording_bake
try:
    assert bpy.ops.gtatools.bake_batch(only_stale=True) == {'FINISHED'}
    assert not calls, 'Queue rebaked unchanged layers'
    # Explicit cancellation between jobs must unwind both generators.
    from types import SimpleNamespace
    probe = SimpleNamespace(only_stale=False, only_uid='', only_map_id='', report=lambda *args: None)
    selected_before = set(bpy.context.selected_objects)
    hidden_before = {target: target.hide_render for target in bpy.context.scene.objects}
    generator = GTATOOLS_OT_bake_batch._bake_iter(probe, bpy.context)
    next(generator)
    generator.close()
    assert len(calls) == 1, 'Cancelled queue continued to another model'
    assert bpy.context.active_object == obj and set(bpy.context.selected_objects) == selected_before
    assert all(target.hide_render == value for target, value in hidden_before.items())
finally:
    B.bake_one_map = original_bake

# Final preview is a separate image, supports alpha/mips and material restore.
s.gtatools_bake_game_size = '256'
s.gtatools_bake_game_mip = 2
assert bpy.ops.gtatools.bake_game_preview() == {'FINISHED'}
game = bpy.data.images[ops._preview_material_name(obj, 'GameImage')]
assert game.size[:] == (8, 8)
assert bpy.data.images[f'{obj.get("inu_bake_base")}_batch'].size[:] == (32, 32)
s.gtatools_bake_game_alpha = True
assert bpy.ops.gtatools.bake_game_preview() == {'FINISHED'}
assert bpy.ops.gtatools.bake_game_preview(original=True) == {'FINISHED'}
assert not obj.get('inu_bake_preview_on')

# Leave a useful interactive scene for UI checks.
_apply_rows(obj, data, True)
obj['inu_bake_base'] = obj.name
for layer in obj.inu.gtatools_bake_layers:
    ops._ensure_paint_image(f'{obj.name}_{layer.uid}', 256, 256)
    layer.expanded = False
dirt = obj.inu.gtatools_bake_layers[0]
dirt.expanded = True
dirt.paint_mask_uid = ''
dirt.masks[0].operation = 'MULTIPLY'
mask = dirt.masks.add()
mask.basis = 'DIRECTION'
obj['inu_bake_mode_live'] = 1
ops._apply_result_material(obj)
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.show_region_ui = True
        area.spaces.active.shading.type = 'MATERIAL'
        area.spaces.active.region_3d.view_distance = 8.
bpy.context.workspace.name = 'Bake Workflow Check'
output = Path(os.environ.get('INU_TEST_OUTPUT', tempfile.gettempdir())) / f'Bake_Workflow_Check_{version_tag}.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
print('BAKE_WORKFLOW_OK', output, flush=True)
if '--ui' not in sys.argv:
    expected_uid = dirt.uid
    bpy.ops.wm.open_mainfile(filepath=str(output))
    reopened = bpy.data.objects['Workflow_A']
    assert reopened.inu.gtatools_bake_layers[0].uid == expected_uid
    assert len(reopened.inu.gtatools_bake_layers[0].masks) == 2
    assert reopened.get('inu_bake_prev_slot_links')
    ops._restore_materials(reopened)
    assert not reopened.get('inu_bake_preview_on')
    assert all(slot.link == 'DATA' for slot in reopened.material_slots)
    print('BAKE_WORKFLOW_REOPEN_OK', flush=True)
    bpy.ops.wm.quit_blender()
