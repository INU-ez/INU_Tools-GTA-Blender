"""Day/Night preview regression, including a saved-style dangling Night input."""
from pathlib import Path
import sys

import addon_utils
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
addon_utils.enable('INU_tools', default_set=False,
    handle_error=lambda error: (_ for _ in ()).throw(error))
from INU_tools.tools.prelight import setup_prelight_preview
from INU_tools.tools import timecyc_prelight as tp

obj = bpy.context.active_object
for name, colour in [('Day', (.7, .5, .3, 1.)), ('Night', (.15, .25, .4, 1.))]:
    attr = obj.data.color_attributes.new(name=name, type='FLOAT_COLOR', domain='CORNER')
    attr.data.foreach_set('color', np.tile(colour, len(attr.data)))
obj.data.color_attributes.active_color = obj.data.color_attributes['Night']
source = {a.name: [tuple(c.color) for c in a.data] for a in obj.data.color_attributes}
mat = bpy.data.materials.new('PrelightRegression')
mat.use_nodes = True
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
texture = mat.node_tree.nodes.new('ShaderNodeTexImage')
texture.image = bpy.data.images.new('PrelightRegressionWhite', width=2, height=2)
texture.image.pixels[:] = [1.] * 16
mat.node_tree.links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])
obj.data.materials.clear()
obj.data.materials.append(mat)
scene = bpy.context.scene
scene.inu_settings.gtatools_timecyc.prelight_daynight = True
scene.inu_settings.gtatools_timecyc.game_look = True
scene.inu_settings.prelight_view_bright = 0.
scene.inu_settings.prelight_view_contrast = 0.
scene.inu_settings.prelight_view_gamma = 1.
scene.inu_settings.prelight_view_saturation = 1.
assert setup_prelight_preview(obj, True)[0]
nodes, links = mat.node_tree.nodes, mat.node_tree.links
group = nodes[tp.NODE_NAME]
for label in ('Day', 'Night'):
    assert group.inputs[label].links[0].from_node.attribute_name == label
assert nodes['Prelight_VertexColor'].attribute_name == 'Night'
before = [(l.from_socket.as_pointer(), l.to_socket.as_pointer()) for l in links]
setup_prelight_preview(obj, True)
assert before == [(l.from_socket.as_pointer(), l.to_socket.as_pointer()) for l in links]

# Reproduce an already-built old graph: the fast path must repair it too.
for link in list(group.inputs['Night'].links):
    links.remove(link)
group.inputs['Night'].default_value = (0., 0., 0., 1.)
tp.set_balance(scene, 1.)
tp.set_ambient(scene, (0., 0., 0.))
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 1
scene.render.resolution_x = scene.render.resolution_y = 32
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'Standard'
scene.render.image_settings.file_format = 'PNG'
scene.world.use_nodes = True
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = 0.
for light in (o for o in scene.objects if o.type == 'LIGHT'):
    light.hide_render = True
camera = scene.camera
camera.location = (0., 0., 5.)
camera.rotation_euler = (0., 0., 0.)
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 3.
output = ROOT / 'dev/tests/.blender_bake_runtime/prelight'
output.mkdir(exist_ok=True)

def render(name):
    scene.render.filepath = str(output / (name + '.png'))
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(scene.render.filepath, check_existing=False)
    values = np.asarray(image.pixels[:]).reshape(32, 32, 4)
    colour = values[16, 16, :3].copy()
    bpy.data.images.remove(image)
    return colour

black = render('night_broken')
assert setup_prelight_preview(obj, True)[0]
night = render('night_fixed')
assert float(black.max()) < .02, black
assert float(night.min()) > .1, night
assert group.inputs['Night'].is_linked
tp.set_balance(scene, 0.)
day = render('day_fixed')
assert not np.allclose(day, night, atol=.03), (day, night)
setup_prelight_preview(obj, False)
assert bsdf.inputs['Base Color'].links[0].from_node == texture
assert all(nodes.get(name) is None for name in (tp.NODE_NAME, tp.DAY_NODE_NAME, tp.NIGHT_NODE_NAME))
assert source == {a.name: [tuple(c.color) for c in a.data] for a in obj.data.color_attributes}
print('PRELIGHT_PREVIEW_OK', bpy.app.version_string, 'black', black, 'night', night, 'day', day)
