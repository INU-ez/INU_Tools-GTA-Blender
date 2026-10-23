"""A textured alpha card must not erase a solid bar in Hi -> Low bakes."""
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
from INU_tools.tools.bake.bake_composite import srgb_to_linear
from INU_tools.tools import compat

def obj(name, vertices, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    result = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(result)
    return result

low = obj('AlphaRay_low', [(-1,-1,0), (1,-1,0), (1,1,0), (-1,1,0)], [(0,1,2,3)])
uv = low.data.uv_layers.new(name='LowUV')
uv.data.foreach_set('uv', np.asarray([(0,0),(1,0),(1,1),(0,1)], np.float32).ravel())
high = obj('AlphaRay_hi', [(-1,-1,.2), (1,-1,.2), (1,1,.2), (-1,1,.2),
    (-.25,-1,.1), (.25,-1,.1), (.25,1,.1), (-.25,1,.1)], [(0,1,2,3),(4,5,6,7)])
uvh = high.data.uv_layers.new(name='HiUV')
uvh.data.foreach_set('uv', np.asarray([(0,0),(1,0),(1,1),(0,1)]*2, np.float32).ravel())
source_pixels = np.zeros((8, 16, 4), np.float32)
source_pixels[..., 1] = 1.
source_pixels[:, 8:, 3] = 1.
texture = bpy.data.images.new('AlphaRay_GreenCard', width=16, height=8, float_buffer=True)
texture.colorspace_settings.name = 'Non-Color'
texture.alpha_mode = 'CHANNEL_PACKED'
B.write_numpy_to_image(texture, source_pixels, pack=False)
card = bpy.data.materials.new('AlphaRay_Card')
card.use_nodes = True
bsdf = next(n for n in card.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
bsdf.inputs['Specular IOR Level' if 'Specular IOR Level' in bsdf.inputs else 'Specular'].default_value = 0.
tex = card.node_tree.nodes.new('ShaderNodeTexImage')
tex.image, tex.interpolation = texture, 'Closest'
uvnode = card.node_tree.nodes.new('ShaderNodeUVMap')
uvnode.uv_map = 'HiUV'
card.node_tree.links.new(uvnode.outputs['UV'], tex.inputs['Vector'])
card.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
card.node_tree.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
bar = bpy.data.materials.new('AlphaRay_Bar')
bar.use_nodes = True
barbsdf = next(n for n in bar.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
barbsdf.inputs['Specular IOR Level' if 'Specular IOR Level' in barbsdf.inputs else 'Specular'].default_value = 0.
barbsdf.inputs['Base Color'].default_value = (.8, .1, .05, 1.)
high.data.materials.append(card)
high.data.materials.append(bar)
high.data.polygons[1].material_index = 1
render_modifier = high.modifiers.new('RenderOnlyTriangulation', 'TRIANGULATE')
render_modifier.show_viewport = False
render_modifier.show_render = True
for o in bpy.context.view_layer.objects:
    o.select_set(o == low)
bpy.context.view_layer.objects.active = low
high.hide_set(True)
original_uv = [loop.uv[:] for loop in high.data.uv_layers.active.data]
original_vertices = [v.co[:] for v in high.data.vertices]
original_materials = list(high.data.materials)

def bake(mid, floating=False, max_ray=0.):
    # Keep byte and float targets separate: setup_target_image intentionally
    # preserves an existing float image when reusing a datablock.
    image = B.setup_target_image('AlphaRay_'+mid+('_float' if floating else ''),
                                 32, 32, float_buffer=floating)
    image.colorspace_settings.name = 'Non-Color' if mid == 'ALPHA' else 'sRGB'
    with B.BakeStateGuard(bpy.context):
        B.bake_one_map(bpy.context, B.get_map(mid), low, image,
            params={}, selected_to_active=True, keep_visible=(high,),
            target_uv='LowUV', cage_extrusion=.5, max_ray=max_ray, margin=0)
    pixels = B.read_image_to_numpy(image)
    if floating and mid == 'DIFFUSE':
        from INU_tools.tools.bake.bake_composite import linear_to_srgb
        pixels[...,:3] = linear_to_srgb(pixels[...,:3])
    assert high.hide_get()
    assert not render_modifier.show_viewport and render_modifier.show_render
    assert original_vertices == [v.co[:] for v in high.data.vertices]
    assert original_uv == [loop.uv[:] for loop in high.data.uv_layers.active.data]
    assert list(high.data.materials) == original_materials
    return pixels

rgb = srgb_to_linear(bake('DIFFUSE')[...,:3])
alpha = bake('ALPHA')[...,0]
np.testing.assert_allclose(rgb[16,14], (.8,.1,.05), atol=.005)
np.testing.assert_allclose(rgb[16,18], (0.,1.,0.), atol=.005)
assert alpha[16,14] > .99 and alpha[16,18] > .99
assert alpha[16,2] < .01
assert np.max(bake('ALPHA', max_ray=.25)) == 0.

cage = obj('AlphaRay_cage', [(-1,-1,.6),(1,-1,.6),(1,1,.6),(-1,1,.6)], [(0,1,2,3)])
bpy.context.scene.render.bake.cage_object = cage
bpy.context.scene.render.bake.use_cage = True
assert bake('ALPHA')[16,14,0] > .99
bpy.context.scene.render.bake.use_cage = False
bpy.context.scene.render.bake.cage_object = None

source_pixels[:,:8,3] = .25
B.write_numpy_to_image(texture, source_pixels, pack=False)
rgb = srgb_to_linear(bake('DIFFUSE')[...,:3])
alpha = bake('ALPHA')[...,0]
np.testing.assert_allclose(rgb[16,14], (.6,.325,.0375), atol=.005)
assert alpha[16,14] > .99 and abs(alpha[16,2]-.25) < .005

# Source colour attributes / modern Mix retain the same albedo semantics.
colours = high.data.color_attributes.new(name='Day', type='FLOAT_COLOR', domain='CORNER')
colours.data.foreach_set('color', np.tile((.5,.5,.5,1.), len(colours.data)))
vc = bar.node_tree.nodes.new('ShaderNodeVertexColor')
vc.layer_name = 'Day'
mix = compat.make_mix_rgba(bar.node_tree.nodes, blend='MULTIPLY')
mix.factor.default_value = 1.
mix.a.default_value = (.8,.1,.05,1.)
bar.node_tree.links.new(vc.outputs['Color'], mix.b)
bar.node_tree.links.new(mix.result, barbsdf.inputs['Base Color'])
# Include the view-correction identity chain used by GTA PreLight baking.
bc = bar.node_tree.nodes.new('ShaderNodeBrightContrast')
gamma = bar.node_tree.nodes.new('ShaderNodeGamma')
gamma.inputs['Gamma'].default_value = 1.
sat = bar.node_tree.nodes.new('ShaderNodeHueSaturation')
bar.node_tree.links.new(vc.outputs['Color'], bc.inputs['Color'])
bar.node_tree.links.new(bc.outputs['Color'], gamma.inputs['Color'])
bar.node_tree.links.new(gamma.outputs['Color'], sat.inputs['Color'])
bar.node_tree.links.new(sat.outputs['Color'], mix.b)
source_pixels[:,:8,3] = 0.
B.write_numpy_to_image(texture, source_pixels, pack=False)
rgb = srgb_to_linear(bake('DIFFUSE')[...,:3])
np.testing.assert_allclose(rgb[16,14], (.4,.05,.025), atol=.005)

# Transparent BSDF + Mix Shader also follows the mask pixel.
out = next(n for n in card.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
transparent = card.node_tree.nodes.new('ShaderNodeBsdfTransparent')
shader_mix = card.node_tree.nodes.new('ShaderNodeMixShader')
card.node_tree.links.remove(bsdf.inputs['Alpha'].links[0])
bsdf.inputs['Alpha'].default_value = 1.
card.node_tree.links.new(tex.outputs['Alpha'], shader_mix.inputs[0])
card.node_tree.links.new(transparent.outputs[0], shader_mix.inputs[1])
card.node_tree.links.new(bsdf.outputs[0], shader_mix.inputs[2])
card.node_tree.links.new(shader_mix.outputs[0], out.inputs['Surface'])
assert bake('ALPHA')[16,14,0] > .99

# Opaque-only sources retain the native Cycles path.
high.data.materials[0] = bar
original_materials = list(high.data.materials)
native = bake('DIFFUSE')
assert np.isfinite(native).all()

# sRGB source pixels must match native Cycles colour conversion.
byte_image = bpy.data.images.new('AlphaRay_sRGB', width=16, height=8)
byte_image.colorspace_settings.name = 'sRGB'
byte_image.alpha_mode = 'STRAIGHT'
byte_pixels = source_pixels.copy()
byte_pixels[...,:3] = (.2,.4,.6)
B.write_numpy_to_image(byte_image, byte_pixels, pack=False)
byte_mat = bpy.data.materials.new('AlphaRay_sRGB_material')
byte_mat.use_nodes = True
byte_bsdf = next(n for n in byte_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
byte_bsdf.inputs['Specular IOR Level' if 'Specular IOR Level' in byte_bsdf.inputs else 'Specular'].default_value = 0.
byte_tex = byte_mat.node_tree.nodes.new('ShaderNodeTexImage')
byte_tex.image, byte_tex.interpolation = byte_image, 'Closest'
byte_mat.node_tree.links.new(byte_tex.outputs['Color'], byte_bsdf.inputs['Base Color'])
high.data.materials[0] = byte_mat
original_materials = list(high.data.materials)
native_colour = bake('DIFFUSE')[16,18,:3].copy()
byte_mat.node_tree.links.new(byte_tex.outputs['Alpha'], byte_bsdf.inputs['Alpha'])
pixel_colour = bake('DIFFUSE')[16,18,:3]
np.testing.assert_allclose(pixel_colour, native_colour, atol=.01)
np.testing.assert_allclose(bake('DIFFUSE', floating=True)[16,18,:3], native_colour, atol=.01)

# The Hi mapping node must affect the alpha test as well as the sampled colour.
mapping = byte_mat.node_tree.nodes.new('ShaderNodeMapping')
mapping.inputs['Location'].default_value = (.5,0.,0.)
mapped_uv = byte_mat.node_tree.nodes.new('ShaderNodeUVMap')
mapped_uv.uv_map = 'HiUV'
byte_mat.node_tree.links.new(mapped_uv.outputs[0], mapping.inputs['Vector'])
byte_mat.node_tree.links.new(mapping.outputs[0], byte_tex.inputs['Vector'])
mapped_alpha = bake('ALPHA')[...,0]
assert mapped_alpha[16,2] > .99 and mapped_alpha[16,29] < .01
mapping.inputs['Location'].default_value = (0.,0.,0.)

float_source = bpy.data.images.new('AlphaRay_float_source', width=16, height=8, float_buffer=True)
float_source.colorspace_settings.name = 'sRGB'
float_source.alpha_mode = 'CHANNEL_PACKED'
B.write_numpy_to_image(float_source, byte_pixels, pack=False)
byte_tex.image = float_source
float_pixel_before_native = bake('DIFFUSE')[16,18,:3].copy()
byte_mat.node_tree.links.remove(byte_bsdf.inputs['Alpha'].links[0])
float_native = bake('DIFFUSE')[16,18,:3].copy()
np.testing.assert_allclose(float_pixel_before_native, float_native, atol=.01)
byte_mat.node_tree.links.new(byte_tex.outputs['Alpha'], byte_bsdf.inputs['Alpha'])
np.testing.assert_allclose(bake('DIFFUSE')[16,18,:3], float_native, atol=.01)

view = bpy.context.preferences.view
saved_language, saved_translate = view.language, view.use_translate_interface
try:
    view.use_translate_interface = True
    for language, expected in [('en_US', 'flat image mapping'),
                               ('ru_RU', 'плоская проекция'),
                               ('es', 'mapeado plano')]:
        view.language = language
        byte_tex.projection = 'BOX'
        try:
            bake('DIFFUSE')
            raise AssertionError('Unsupported mapping was silently sampled')
        except RuntimeError as error:
            assert expected in str(error), (language, str(error))
finally:
    byte_tex.projection = 'FLAT'
    view.language, view.use_translate_interface = saved_language, saved_translate
assert high.hide_get() and not render_modifier.show_viewport
assert original_vertices == [v.co[:] for v in high.data.vertices]

# Large GTA world translations must not make the transparent-ray step round
# back onto the same triangle (there are only two surfaces in this fixture).
reference_alpha = bake('ALPHA').copy()
reference_rgb = bake('DIFFUSE').copy()
for target in (low, high, cage):
    target.location = (16384., -32768., 65536.)
bpy.context.view_layer.update()
np.testing.assert_allclose(bake('ALPHA'), reference_alpha, atol=.005)
np.testing.assert_allclose(bake('DIFFUSE'), reference_rgb, atol=.005)
bpy.context.scene.render.bake.cage_object = cage
bpy.context.scene.render.bake.use_cage = True
np.testing.assert_allclose(bake('ALPHA'), reference_alpha, atol=.005)
bpy.context.scene.render.bake.use_cage = False
bpy.context.scene.render.bake.cage_object = None
for target in (low, high, cage):
    target.location = (0., 0., 0.)
bpy.context.view_layer.update()

if '--bench' in sys.argv:
    import time
    import cProfile
    profiler = cProfile.Profile()
    if '--profile' in sys.argv:
        profiler.enable()
    before = time.perf_counter()
    size = 1024 if '--bench-1024' in sys.argv else 256
    for mid in ('DIFFUSE', 'ALPHA'):
        image = B.setup_target_image('AlphaRay_benchmark_'+mid, size, size)
        image.colorspace_settings.name = 'Non-Color' if mid == 'ALPHA' else 'sRGB'
        B.bake_one_map(bpy.context, B.get_map(mid), low, image,
            params={}, selected_to_active=True, keep_visible=(high,),
            target_uv='LowUV', cage_extrusion=.5, margin=0)
    print('ALPHA_RAY_BENCH_SECONDS', size, round(time.perf_counter()-before, 3), flush=True)
    if '--profile' in sys.argv:
        profiler.disable()
        profiler.dump_stats(str(ROOT / 'dev/tests/alpha-ray-profile.prof'))
print('ALPHA_RAY_PROJECTION_OK', bpy.app.version_string, flush=True)
