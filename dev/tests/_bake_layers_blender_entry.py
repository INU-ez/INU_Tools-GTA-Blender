"""Native Blender regression checks for painted layers and packed apply.

blender --background --factory-startup --python-exit-code 1 --python <this file>
Pass -- --ui to leave a test scene open for panel inspection.
"""
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import addon_utils
addon_utils.enable('INU_tools', default_set=False, handle_error=lambda e: (_ for _ in ()).throw(e))
from INU_tools.ops import bake_ops
from INU_tools.tools import bake as B

obj = bpy.context.active_object
obj.name = 'BakeLayerCheck'
obj['inu_bake_base'] = 'BakeLayerCheck'
obj['inu_bake_uv'] = obj.data.uv_layers.active.name
layers = obj.inu.gtatools_bake_layers
layers.clear()
parent = layers.add()
parent.uid = 'diffuse_check'
parent.map_id = 'DIFFUSE'
parent.blend_mode = 'NORMAL'
source = bake_ops._ensure_paint_image('BakeLayerCheck_diffuse_check', 8, 8)
source_pixels = B.read_image_to_numpy(source).copy()

def paint(uid):
    assert bpy.ops.gtatools.bake_paint_layer(uid=uid) == {'FINISHED'}
    assert obj.mode == 'TEXTURE_PAINT'
    bpy.ops.object.mode_set(mode='OBJECT')

paint('diffuse_check')
assert len(layers) == 2
mask_uid = layers[0].paint_mask_uid
assert layers[1].uid == mask_uid and layers[1].name == 'Маска'
assert layers[1].map_id == 'PAINT'
mask = bpy.data.images['BakeLayerCheck_' + mask_uid]
mat = obj.active_material
assert mat.node_tree.nodes.active.image is mask
assert np.allclose(B.read_image_to_numpy(mask), 1.0)
paint('diffuse_check')
paint(mask_uid)
assert len(layers) == 2, 'Repeated painting must reuse the mask'
assert np.array_equal(B.read_image_to_numpy(source), source_pixels)

# A dark mask must affect NORMAL/Diffuse too, without changing its source.
pixels = np.ones((8, 8, 4), dtype=np.float32)
pixels[..., :3] = 0.25
B.write_numpy_to_image(mask, pixels, pack=False)
assert bpy.ops.gtatools.bake_save_apply() == {'FINISHED'}
final = bpy.data.images[obj['inu_bake_image']]
assert final.packed_file and mask.packed_file
assert obj['inu_bake_mode_live'] == 0
assert np.allclose(B.read_image_to_numpy(final)[..., :3], 0.25, atol=0.01)
assert np.array_equal(B.read_image_to_numpy(source), source_pixels)
assert any(n.type == 'BSDF_PRINCIPLED' for n in obj.active_material.node_tree.nodes)
assert any(n.type == 'TEX_IMAGE' and n.image is final for n in obj.active_material.node_tree.nodes)
assert any(n.type == 'UVMAP' and n.uv_map == obj['inu_bake_uv'] for n in obj.active_material.node_tree.nodes)

layers[1].enabled = False
assert bpy.ops.gtatools.bake_save_apply() == {'FINISHED'}
assert np.allclose(B.read_image_to_numpy(final)[..., :3], 1.0, atol=0.01)
layers[1].enabled = True

# Recreating a deleted mask must replace the stale reference.
layers.remove(1)
paint('diffuse_check')
assert len(layers) == 2 and layers[1].uid != mask_uid
assert layers[0].paint_mask_uid == layers[1].uid
assert bpy.ops.gtatools.bake_save_apply() == {'FINISHED'}
for factor in (2, 4, 8):
    assert bpy.ops.gtatools.bake_save_apply(save_scale=str(factor)) == {'FINISHED'}
    saved = bpy.data.images[obj['inu_bake_image']]
    assert tuple(saved.size) == (8 // factor, 8 // factor)
    assert saved.packed_file
    assert tuple(source.size) == (8, 8) and tuple(mask.size) == (8, 8)
    assert np.array_equal(B.read_image_to_numpy(source), source_pixels)
    assert np.allclose(B.read_image_to_numpy(saved)[...,:3], 1., atol=.01)
# Reapplying must start from the full stack, not shrink the previous result again.
assert bpy.ops.gtatools.bake_save_apply(save_scale='2') == {'FINISHED'}
assert tuple(bpy.data.images[obj['inu_bake_image']].size) == (4, 4)
copy = bake_ops._downscaled_bake_copy(source, 4)
assert tuple(copy.size) == (2, 2) and tuple(source.size) == (8, 8)
bpy.data.images.remove(copy)
output = ROOT / 'dev/tests/.blender_bake_runtime'
output.mkdir(exist_ok=True)
blend = output / 'packed_layers.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
if '--ui' not in sys.argv:
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    obj = bpy.data.objects['BakeLayerCheck']
    assert bpy.data.images[obj['inu_bake_image']].packed_file
    assert tuple(bpy.data.images[obj['inu_bake_image']].size) == (4, 4)
    assert len(obj.inu.gtatools_bake_layers) == 2
    print('BAKE_LAYER_CHECKS_OK: mask creation/reuse/recreation, paint target, source preservation, packed apply, UV, save/reopen')
else:
    obj.inu.gtatools_bake_layers[0].expanded = True
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.show_region_ui = True
            for region in area.regions:
                if region.type == 'UI' and hasattr(region, 'active_panel_category'):
                    try:
                        region.active_panel_category = 'GTA Tools'
                    except AttributeError:
                        # Blender 4.2 exposes this property as read-only.
                        # Select the GTA Tools tab manually for UI inspection.
                        pass
