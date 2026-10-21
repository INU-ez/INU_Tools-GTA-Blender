"""Native Normal Map stays at the requested size, including packed Hi→Low rebakes."""
from pathlib import Path
import sys

import addon_utils
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
addon_utils.enable('INU_tools', default_set=False,
    handle_error=lambda error: (_ for _ in ()).throw(error))
from INU_tools.tools import bake as B

mesh = bpy.data.meshes.new('NormalSizeTest')
mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
low = bpy.data.objects.new('NormalSizeTest_low', mesh)
bpy.context.scene.collection.objects.link(low)
uv = mesh.uv_layers.new(name='OriginalUV')
coords = np.array([(0, 0), (1, 0), (1, 1), (0, 1)], dtype=np.float32)
uv.data.foreach_set('uv', coords.ravel())
high = low.copy()
high.data = mesh.copy()
high.name = 'NormalSizeTest_hi'
bpy.context.scene.collection.objects.link(high)
for vertex in high.data.vertices:
    vertex.co.z = .25 + vertex.co.x * .1
for other in bpy.context.view_layer.objects:
    other.select_set(other == low)
bpy.context.view_layer.objects.active = low

settings = bpy.context.scene.inu_settings
settings.gtatools_bake_res_x = 1024
settings.gtatools_bake_res_y = 1024
settings.gtatools_bake_aa = '4'
settings.gtatools_bake_margin = 8
settings.gtatools_bake_denoise = False
settings.gtatools_bake_selected_edges = False
settings.gtatools_bake_selected_faces = False
settings.gtatools_bake_cage_extrusion = 1
layer = low.inu.gtatools_bake_layers.add()
layer.uid = 'normal_size'
layer.map_id = 'NORMAL'
layer.desaturate = False
layer.enabled = True
layer.blend_mode = 'NORMAL'

original_bake = B.bake_one_map
calls = []
def checked_bake(context, definition, obj, image, **kwargs):
    assert definition.id == 'NORMAL'
    assert tuple(image.size) == (1024, 1024), tuple(image.size)
    calls.append(bool(kwargs.get('selected_to_active')))
    return original_bake(context, definition, obj, image, **kwargs)
B.bake_one_map = checked_bake

initial_engine = bpy.context.scene.render.engine
try:
    for mode in ('UV', 'HILOW', 'HILOW'):
        settings.gtatools_bake_mode = mode
        if mode == 'HILOW':
            high.hide_set(True)
            high.hide_render = True
        assert bpy.ops.gtatools.bake_run(only_uid=layer.uid) == {'FINISHED'}
        if mode == 'HILOW':
            assert high.hide_get() and high.hide_render
        image = bpy.data.images[f"{low['inu_bake_base']}_{layer.uid}"]
        assert tuple(image.size) == (1024, 1024)
        assert image.packed_file is not None
        pixels = B.read_image_to_numpy(image)
        assert np.isfinite(pixels).all() and pixels[..., :3].max() > .5
        assert settings.gtatools_bake_aa == '4'
        assert bpy.context.scene.render.engine == initial_engine
        after = np.empty_like(coords).ravel()
        uv.data.foreach_get('uv', after)
        np.testing.assert_array_equal(coords, after.reshape(-1, 2))
    assert calls == [False, True, True]
    assert not any(image.name.endswith('.001') and 'normal_size' in image.name
                   for image in bpy.data.images)
finally:
    B.bake_one_map = original_bake
print('[NORMAL BAKE] 1024 with AA4, UV, Hi→Low, packed rebake and UV preservation: OK')
