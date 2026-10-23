"""Native EEVEE camera bake: colour, alpha border and state restoration."""
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
from INU_tools.tools import compat

obj = bpy.context.active_object
mat = bpy.data.materials.new('CameraBakeRegression')
compat.material_enable_nodes(mat)
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
bsdf.inputs['Base Color'].default_value = (.6, .2, .1, 1.)
obj.data.materials.clear()
obj.data.materials.append(mat)
uvs = [tuple(loop.uv) for loop in obj.data.uv_layers.active.data]
scene = bpy.context.scene
original_camera, original_engine = scene.camera, scene.render.engine
image = B.setup_target_image('CameraBakeRegression', 32, 32)
B.render_one_map_camera(bpy.context, B.get_map('DIFFUSE'), obj, image,
                        samples=8, padding=.15)
pixels = B.read_image_to_numpy(image)
assert np.isfinite(pixels).all()
assert pixels[16,16,0] > pixels[16,16,2] > 0., pixels[16,16]
assert pixels[16,16,3] > .9, pixels[16,16]
assert pixels[0,0,3] < .1, pixels[0,0]
assert scene.camera == original_camera and scene.render.engine == original_engine
assert obj.data.materials[0] == mat
assert uvs == [tuple(loop.uv) for loop in obj.data.uv_layers.active.data]
print('CAMERA_BAKE_OK', bpy.app.version_string)
