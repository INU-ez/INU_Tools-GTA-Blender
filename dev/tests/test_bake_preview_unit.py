"""Run with Python, without launching Blender: python dev/tests/test_bake_preview_unit.py."""
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BAKE = ROOT / 'INU_tools/tools/bake'


class Image(types.SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, 'properties', {}).get(key, default)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Socket:
    def __init__(self, node, name):
        self.node, self.name, self.link = node, name, None
        self.default_value = 0.0

    def value(self):
        if self.link:
            return self.link.value()
        node = self.node
        if self not in node.outputs.values():
            return self.default_value
        if node.kind == 'ShaderNodeTexImage':
            px = node.image.array[0, node.image.sample]
            rgb = px[:3]
            if getattr(node.image, 'linear_color', False):
                rgb = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
            return rgb if self.name == 'Color' else px[3]
        if node.kind == 'ShaderNodeRGBToBW':
            color = np.asarray(node.inputs['Color'].value())
            color = np.repeat(color, 3) if color.ndim == 0 else color[:3]
            return float(np.dot(color, [.2126, .7152, .0722]))
        if node.kind == 'ShaderNodeNewGeometry':
            return np.array((0., 0., 1.))
        if node.kind == 'ShaderNodeVectorTransform':
            return node.inputs['Vector'].value()
        if node.kind == 'MixRGBA':
            def rgb(value):
                array = np.asarray(value)
                return np.repeat(array, 3) if array.ndim == 0 else array[:3]
            a, b = rgb(node.inputs['a'].value()), rgb(node.inputs['b'].value())
            fac = node.inputs['factor'].value()
            top = {'MIX': lambda: b, 'MULTIPLY': lambda: a * b,
                   'ADD': lambda: a + b}[node.blend]()
            return a * (1 - fac) + top * fac
        if node.kind in ('ShaderNodeSeparateColor', 'ShaderNodeSeparateRGB'):
            return node.inputs[0].value()[0]
        a, b = node.inputs[0].value(), node.inputs[1].value()
        if node.kind == 'ShaderNodeVectorMath':
            a, b = np.asarray(a), np.asarray(b)
            return {'MULTIPLY_ADD': lambda: a * b + node.inputs[2].value(),
                    'NORMALIZE': lambda: a / max(float(np.linalg.norm(a)), 1e-8),
                    'DOT_PRODUCT': lambda: float(a @ b)}[node.operation]()
        if node.kind == 'ShaderNodeMath':
            a = float(np.mean(np.asarray(a)))
            b = float(np.mean(np.asarray(b)))
        result = {'LESS_THAN': lambda: float(a < b), 'GREATER_THAN': lambda: float(a > b),
                  'SUBTRACT': lambda: a - b, 'MULTIPLY': lambda: a * b,
                  'ADD': lambda: a + b, 'ABSOLUTE': lambda: abs(a),
                  'MAXIMUM': lambda: max(a, b), 'POWER': lambda: a ** b,
                  'DIVIDE': lambda: a / b if b else 0.}[node.operation]()
        return np.clip(result, 0, 1) if getattr(node, 'use_clamp', False) else result


class Nodes(list):
    modern_separate = True

    def new(self, kind):
        if (kind == 'ShaderNodeSeparateColor' and not self.modern_separate
                or kind == 'ShaderNodeSeparateRGB' and self.modern_separate):
            raise RuntimeError('Node type is unavailable in this Blender version')
        inputs, outputs = {
            'ShaderNodeOutputMaterial': (['Surface'], []),
            'ShaderNodeEmission': (['Color'], ['Emission']),
            'ShaderNodeTexImage': (['Vector'], ['Color', 'Alpha']),
            'ShaderNodeSeparateColor': ([0], [0]),
            'ShaderNodeSeparateRGB': ([0], [0]),
            'ShaderNodeMath': ([0, 1], [0]),
            'ShaderNodeVectorMath': ([0, 1, 2], ['Vector', 'Value']),
            'ShaderNodeNewGeometry': ([], ['True Normal']),
            'ShaderNodeVectorTransform': (['Vector'], ['Vector']),
            'ShaderNodeBsdfTransparent': ([], [0]),
            'ShaderNodeMixShader': (['Fac', 1, 2], [0]),
            'ShaderNodeRGBToBW': (['Color'], ['Val']),
            'MixRGBA': (['factor', 'a', 'b'], ['result']),
            'ShaderNodeUVMap': ([], ['UV']),
        }[kind]
        node = types.SimpleNamespace(kind=kind)
        node.inputs = {key: Socket(node, key) for key in inputs}
        node.outputs = {key: Socket(node, key) for key in outputs}
        if kind == 'ShaderNodeMath':
            node.outputs['Value'] = node.outputs[0]
        self.append(node)
        return node


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_modules = dict(sys.modules)
        package = types.ModuleType('inu_preview_unit')
        package.__path__ = [str(BAKE.parent)]
        sys.modules[package.__name__] = package
        bake_package = types.ModuleType('inu_preview_unit.bake')
        bake_package.__path__ = [str(BAKE)]
        sys.modules[bake_package.__name__] = bake_package
        cls.composite = load('inu_preview_unit.bake.bake_composite', BAKE / 'bake_composite.py')
        sys.modules['inu_preview_unit.compat'] = types.SimpleNamespace(
            make_material_alpha=lambda mat: None, set_blend_method=lambda *args: None)
        sys.modules['inu_preview_unit.bake.bake_core'] = types.SimpleNamespace(
            read_image_to_numpy=lambda image: image.array)
        cls.images = {}
        cls.mat = types.SimpleNamespace(node_tree=types.SimpleNamespace(
            nodes=Nodes(), links=types.SimpleNamespace(new=lambda source, target: setattr(target, 'link', source))))
        sys.modules['bpy'] = types.SimpleNamespace(data=types.SimpleNamespace(
            images=cls.images, materials=types.SimpleNamespace(get=lambda name: cls.mat)))
        cls.nodes = load('inu_preview_unit.bake.bake_nodes', BAKE / 'bake_nodes.py')
        maps = types.ModuleType('inu_preview_unit.bake.bake_maps')
        cls.pattern_parameters = []
        def pattern(tree, params):
            cls.pattern_parameters.append(dict(params))
            node = tree.nodes.new('ShaderNodeMath')
            node.operation = 'ADD'
            node.inputs[0].default_value = float(params.get('pattern_scale', 8)) / 100
            return node.outputs[0]
        env = dict(_pattern_weight=pattern)
        tree = ast.parse((BAKE / 'bake_maps.py').read_text(encoding='utf-8'))
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('_math_node', '_modulate_surface_output')]
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<surface nodes>', 'exec'), env)
        maps._math_node = env['_math_node']
        maps._modulate_surface_output = env['_modulate_surface_output']
        maps._pattern_weight = pattern
        sys.modules[maps.__name__] = maps
        def mix(nodes, blend, label=''):
            node = nodes.new('MixRGBA')
            node.blend = blend
            return types.SimpleNamespace(node=node, factor=node.inputs['factor'],
                                         a=node.inputs['a'], b=node.inputs['b'],
                                         result=node.outputs['result'])
        sys.modules['inu_preview_unit.compat'].make_mix_rgba = mix

    @classmethod
    def tearDownClass(cls):
        for key in list(sys.modules):
            if key == 'bpy' or key.startswith('inu_preview_unit'):
                if key in cls.saved_modules:
                    sys.modules[key] = cls.saved_modules[key]
                else:
                    sys.modules.pop(key, None)

    def check_alpha(self, array, invert=False, opacity=1.0):
        image = Image(array=array, sample=0)
        self.images['check_alpha'] = image
        spec = dict(map_id='ALPHA', uid='alpha', enabled=True, alpha_source='MATERIAL',
                    alpha_invert=invert, opacity=opacity)
        mat = self.nodes.build_composite_material([spec], 'check', '')
        fac = next(n for n in mat.node_tree.nodes if n.kind == 'ShaderNodeMixShader').inputs['Fac']
        layer = self.composite.LayerSpec(map_id='ALPHA', uid='alpha',
                                        alpha_invert=invert, opacity=opacity)
        expected = self.composite.composite_layers({'alpha': array, 'ALPHA': array},
                                                  [layer], array.shape[1], 1)[0, :, 3]
        actual = []
        for image.sample in range(array.shape[1]):
            actual.append(fac.value())
        np.testing.assert_allclose(actual, expected)

    def test_rgb_mask_ignores_opaque_alpha(self):
        self.check_alpha(np.array([[[0, 0, 0, 1], [1, 1, 1, 1], [.5, .5, .5, 1]]], np.float32))

    def test_coverage_fallback(self):
        self.check_alpha(np.array([[[0, 0, 0, 0], [0, 0, 0, 1]]], np.float32))

    def test_material_alpha_bake_retains_holes_and_fully_transparent_hi(self):
        source = np.array([[[v, v, v, 1.] for v in (0., .3, 1.)]], np.float32)
        pixels = self.composite.material_alpha_rgba(source)
        np.testing.assert_allclose(pixels[..., 3], source[..., 0])
        np.testing.assert_array_equal(source[..., 3], 1.)
        self.check_alpha(pixels)
        fully_transparent = self.composite.material_alpha_rgba(np.array([[[0., 0., 0., 1.]]], np.float32))
        self.check_alpha(fully_transparent)
        layer = self.composite.LayerSpec(map_id='ALPHA', uid='alpha', alpha_source='MATERIAL')
        result = self.composite.composite_layers(
            {'alpha': fully_transparent, 'ALPHA': fully_transparent}, [layer], 1, 1)
        self.assertEqual(float(result[0, 0, 3]), 0.)

    def test_old_blender_separate_fallback(self):
        nodes = self.mat.node_tree.nodes
        nodes.modern_separate = False
        try:
            self.check_alpha(np.array([[[0, 0, 0, 1], [1, 1, 1, 1]]], np.float32))
            self.assertTrue(any(n.kind == 'ShaderNodeSeparateRGB' for n in nodes))
        finally:
            nodes.modern_separate = True

    def test_invert_and_strength(self):
        self.check_alpha(np.array([[[0, 0, 0, 1], [1, 1, 1, 1]]], np.float32), True, .25)

    def test_effect_colours_match_preview_and_flatten(self):
        pixels = np.array([[[v, v, v, 1] for v in (0, .25, .5, 1)]], np.float32)
        image = Image(array=pixels, sample=0, linear_color=True)
        self.images['colour_fx'] = image
        for mid in ('DIRT', 'EDGEWEAR', 'CURVATURE', 'BEVEL', 'HIGHLIGHT'):
            spec = dict(map_id=mid, uid='fx', enabled=True, opacity=1.0,
                        use_color=True, color_dark=(.16, .06, .02), color_light=(1, .9, .7))
            material = self.nodes.build_composite_material([spec], 'colour', '')
            emit = next(n for n in material.node_tree.nodes if n.kind == 'ShaderNodeEmission')
            actual = []
            for image.sample in range(4):
                actual.append(emit.inputs['Color'].value())
            layer = self.composite.LayerSpec(**{k: v for k, v in spec.items()})
            expected = self.composite.composite_layers({'fx': pixels}, [layer], 4, 1, srgb=False)
            np.testing.assert_allclose(actual, expected[0, :, :3], atol=1e-6)
            np.testing.assert_array_equal(expected[0, :, 3], 1)

    def test_live_mask_operations_preserve_neutral_and_signed_curvature(self):
        import importlib
        surface = importlib.import_module('inu_preview_unit.bake.bake_surface')
        nt = self.mat.node_tree
        def output(mid, value, operation='MULTIPLY', strength=1., invert=False):
            color = surface.math_node(nt, 'ADD', value, 0.)
            mask = dict(basis='AO', operation=operation, strength=strength, invert=invert)
            return surface.combine_masks(nt, color, dict(map_id=mid, masks=[mask]),
                lambda basis: surface.math_node(nt, 'ADD', .25, 0.)).value()
        self.assertAlmostEqual(output('DIRT', .2), .8)
        self.assertAlmostEqual(output('DIRT', 1.), 1.)
        self.assertAlmostEqual(output('EDGEWEAR', 0.), 0.)
        self.assertAlmostEqual(output('EDGEWEAR', .4, 'ADD'), .65)
        self.assertAlmostEqual(output('EDGEWEAR', .4, 'SUBTRACT'), .15)
        self.assertAlmostEqual(output('EDGEWEAR', .4, strength=0.), .4)
        self.assertAlmostEqual(output('EDGEWEAR', .4, invert=True), .3)
        self.assertAlmostEqual(output('CURVATURE', .25), .4375)
        self.assertAlmostEqual(output('CURVATURE', .75), .5625)
        self.assertAlmostEqual(output('CURVATURE', .5), .5)

    def test_live_colour_transition_bounds_and_smoothing(self):
        import importlib
        surface = importlib.import_module('inu_preview_unit.bake.bake_surface')
        nt = self.mat.node_tree
        for value, expected in ((0., 0.), (.2, 0.), (.5, .5), (.8, 1.), (1., 1.)):
            socket = surface.math_node(nt, 'ADD', value, 0.)
            self.assertAlmostEqual(surface.levels(nt, socket, .2, .8, True).value(), expected)

    def test_coloured_dirt_preserves_unoccluded_base(self):
        source = np.ones((1, 2, 4), np.float32)
        source[0, 0, :3] = 0
        base = np.ones((1, 2, 4), np.float32)
        base[..., :3] = .5
        layer = self.composite.LayerSpec(map_id='DIRT', use_color=True,
            color_dark=(.16, .06, .02), blend_mode='MULTIPLY')
        result = self.composite.composite_layers({'DIRT': source, 'DIFFUSE': base},
            [layer, self.composite.LayerSpec(map_id='DIFFUSE')], 2, 1, srgb=False)
        linear_base = self.composite.srgb_to_linear(base[..., :3])
        np.testing.assert_allclose(result[0, 1, :3], linear_base[0, 1], atol=1e-6)
        np.testing.assert_allclose(result[0, 0, :3], linear_base[0, 0] * [.16, .06, .02], atol=1e-6)

    def test_pattern_changes_live_without_modifying_baked_image(self):
        pixels = np.array([[[1, 1, 1, 1]]], np.float32)
        self.images['live_fx'] = Image(array=pixels, sample=0)
        spec = dict(map_id='BEVEL', uid='fx', enabled=True, opacity=1,
                    surface_pattern='VORONOI', pattern_scale=20, pattern_seed=143)
        def value():
            material = self.nodes.build_composite_material([spec], 'live', '')
            return next(n for n in material.node_tree.nodes if n.kind == 'ShaderNodeEmission').inputs['Color'].value()
        self.assertAlmostEqual(value(), .2)
        spec['pattern_scale'] = 60
        self.assertAlmostEqual(value(), .6)
        self.assertEqual(self.pattern_parameters[-1]['pattern_seed'], 143)
        np.testing.assert_array_equal(pixels, [[[1, 1, 1, 1]]])

    def test_effect_basis_reuses_baked_ao_or_bevel(self):
        self.images['basis_dirt'] = Image(array=np.array([[[.4, .4, .4, 1]]]), sample=0)
        self.images['basis_ao'] = Image(array=np.array([[[.8, .8, .8, 1]]]), sample=0)
        self.images['basis_edge'] = Image(array=np.array([[[.7, .7, .7, 1]]]), sample=0)
        spec = dict(map_id='DIRT', uid='dirt', enabled=True, opacity=1, effect_basis='AO')
        references = [dict(map_id='AO', uid='ao', enabled=False),
                      dict(map_id='BEVEL', uid='edge', enabled=False)]
        def value():
            material = self.nodes.build_composite_material([spec]+references, 'basis', '')
            return next(n for n in material.node_tree.nodes if n.kind == 'ShaderNodeEmission').inputs['Color'].value()
        self.assertAlmostEqual(value(), .8)
        spec['effect_basis'] = 'BEVEL'
        self.assertAlmostEqual(value(), .3)
        spec['basis_invert'] = True
        self.assertAlmostEqual(value(), .7)

    def test_each_image_keeps_its_sampling_uv(self):
        self.images['uv_one'] = Image(array=np.ones((1,1,4)), sample=0, properties={'inu_bake_uv': 'Trim'})
        self.images['uv_two'] = Image(array=np.ones((1,1,4)), sample=0, properties={'inu_bake_uv': 'Unique'})
        specs = [dict(map_id='DIFFUSE',uid='one',enabled=True,opacity=1,blend_mode='NORMAL'),
                 dict(map_id='BEVEL',uid='two',enabled=True,opacity=1,blend_mode='ADD')]
        material = self.nodes.build_composite_material(specs, 'uv', 'Unique')
        sampled = {n.image.get('inu_bake_uv'): n.inputs['Vector'].link.node.uv_map
                   for n in material.node_tree.nodes if n.kind=='ShaderNodeTexImage'}
        self.assertEqual(sampled, {'Trim':'Trim','Unique':'Unique'})

    def test_bevel_basis_uses_each_layers_private_mask(self):
        self.images['private_global'] = Image(array=np.full((1, 1, 4), .9), sample=0)
        for uid, strength in (('first', .2), ('second', .8)):
            self.images[f'private_{uid}'] = Image(array=np.full((1, 1, 4), .4), sample=0)
            self.images[f'private_{uid}__bevel_basis'] = Image(
                array=np.full((1, 1, 4), strength), sample=0,
                properties={'inu_bake_uv': 'Trim'})
            spec = dict(map_id='EDGEWEAR', uid=uid, enabled=True, opacity=1,
                        effect_basis='BEVEL')
            references = [dict(map_id='BEVEL', uid='global', enabled=False)]
            def value():
                material = self.nodes.build_composite_material([spec] + references, 'private', '')
                return next(n for n in material.node_tree.nodes
                            if n.kind == 'ShaderNodeEmission').inputs['Color'].value()
            np.testing.assert_allclose(value(), strength)
            # Toggling the live basis retains the effect's original geometry mask.
            spec['effect_basis'] = 'SELF'
            np.testing.assert_allclose(value(), .4)
            spec['effect_basis'] = 'BEVEL'
            spec['map_id'] = 'DIRT'
            np.testing.assert_allclose(value(), 1 - strength)
            spec['map_id'] = 'BEVEL'
            np.testing.assert_allclose(value(), .4)

    def test_normal_lighting_preserves_colour_and_raw_vectors(self):
        raw = np.array([[[.5, .5, 1., 1.], [1., .5, .5, 1.]]])
        self.images['light_normal'] = Image(array=raw.copy(), sample=0)
        self.images['light_diffuse'] = Image(array=np.array([[[.4, .2, .1, 1.]] * 2]), sample=0)
        normal = dict(map_id='NORMAL', uid='normal', enabled=True, opacity=1.,
                      blend_mode='NORMAL', normal_lighting=True, normal_ambient=1.,
                      normal_diffuse=0., normal_specular=0., desaturate=True)
        diffuse = dict(map_id='DIFFUSE', uid='diffuse', enabled=True, opacity=1., blend_mode='NORMAL')
        def value():
            material = self.nodes.build_composite_material([normal, diffuse], 'light', '')
            return next(n for n in material.node_tree.nodes
                        if n.kind == 'ShaderNodeEmission').inputs['Color'].value()
        np.testing.assert_allclose(value(), [.4, .2, .1])
        normal['normal_ambient'] = .5
        np.testing.assert_allclose(value(), [.2, .1, .05])
        normal.update(normal_ambient=0., normal_diffuse=1., normal_light_elevation=90.)
        np.testing.assert_allclose(value(), [.4, .2, .1], atol=1e-7)
        self.images['light_normal'].sample = 1
        self.images['light_diffuse'].sample = 1
        np.testing.assert_allclose(value(), [0., 0., 0.], atol=1e-7)
        normal.update(normal_diffuse=0., normal_specular=.2, normal_shininess=1.,
                      normal_light_azimuth=0., normal_light_elevation=0.)
        highlight = np.asarray(value())
        self.assertGreater(highlight.max(), .05)
        np.testing.assert_allclose(highlight, np.repeat(highlight[0], 3))
        np.testing.assert_array_equal(self.images['light_normal'].array, raw)

    def test_normal_rounding_light_modes_preserve_planes(self):
        normal_module = load('inu_preview_unit.bake.bake_normal', BAKE / 'bake_normal.py')
        tree = types.SimpleNamespace(nodes=Nodes(), links=types.SimpleNamespace(
            new=lambda a, b: setattr(b, 'link', a)))
        image = Image(array=np.array([[[.5, .5, 1., 1.],
                          [.5 + .5 / np.sqrt(2), .5, .5 + .5 / np.sqrt(2), 1.]]]), sample=0)
        source = tree.nodes.new('ShaderNodeTexImage')
        source.image = image
        for mode, flat in (('EDGES', 1.), ('ALL_SIDES', .65 + .45 / 2)):
            shade, spec = normal_module.normal_lighting_nodes(tree, source.outputs['Color'],
                dict(normal_light_mode=mode, normal_diffuse=.45, normal_specular=.15))
            image.sample = 0
            self.assertAlmostEqual(shade.value(), flat)
            self.assertAlmostEqual(spec.value(), 0.)
            image.sample = 1
            self.assertGreater(spec.value(), .1)
            if mode == 'EDGES':
                self.assertLess(shade.value(), flat)
            else:
                self.assertGreater(shade.value(), flat)

    def test_pattern_callbacks_are_live(self):
        source = ast.parse((ROOT / 'INU_tools/scene_settings.py').read_text(encoding='utf-8'))
        layer = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name=='INUBakeLayer')
        fields = {'surface_pattern','pattern_scale','pattern_strength','pattern_detail','pattern_contrast',
                  'pattern_seed','effect_basis','basis_invert'}
        for n in layer.body:
            if isinstance(n, ast.AnnAssign) and n.target.id in fields:
                update = next(k.value for k in n.annotation.keywords if k.arg=='update')
                self.assertEqual(update.id, '_bake_live_update')
                fields.remove(n.target.id)
        self.assertFalse(fields)

    def test_alpha_export_uses_same_mask_without_transparent_shader(self):
        image = Image(array=np.array([[[0,0,0,1],[1,1,1,1]]],np.float32), sample=0)
        self.images['alpha_export_a'] = image
        spec = dict(map_id='ALPHA', uid='a', enabled=True, opacity=.4, alpha_source='MATERIAL')
        material = self.nodes.build_composite_material([spec], 'alpha_export', '',
            opaque_for_bake=True, alpha_only_for_bake=True)
        emit = next(n for n in material.node_tree.nodes if n.kind=='ShaderNodeEmission')
        self.assertEqual(emit.inputs['Color'].value(),0)
        image.sample=1
        self.assertAlmostEqual(emit.inputs['Color'].value(),.4)
        self.assertFalse(any(n.kind=='ShaderNodeMixShader' for n in material.node_tree.nodes))

    def test_live_export_rasterizes_rgb_and_alpha_and_restores_state(self):
        from dataclasses import dataclass
        from unittest.mock import patch
        @dataclass
        class Definition:
            id: str = 'GRUNGE'
            node_group_builder: object = None
        class Item(dict):
            pass
        class Images(dict):
            def new(self,name,width,height,**kwargs):
                item=Item(); item.name=name; item.array=np.ones((height,width,4),np.float32)
                item.colorspace_settings=types.SimpleNamespace(name='sRGB')
                self[name]=item
                return item
            def remove(self,item): del self[item.name]
        class Materials(dict):
            def new(self,name):
                item=types.SimpleNamespace(name=name,users=0)
                self[name]=item
                return item
            def remove(self,item): del self[item.name]
        obj=Item(inu_bake_uv='Unique')
        obj.mode='EDIT';obj.hide_render=True;obj.selected=True
        obj.select_set=lambda value:setattr(obj,'selected',value)
        active=types.SimpleNamespace(active=obj)
        context=types.SimpleNamespace(selected_objects=[obj],view_layer=types.SimpleNamespace(objects=active),
            scene=types.SimpleNamespace(inu_settings=types.SimpleNamespace(gtatools_bake_margin=5)))
        images,materials=Images(),Materials()
        class Guard:
            def __init__(self,ctx): self.ctx=ctx
            def __enter__(self): self.mode=obj.mode;return self
            def __exit__(self,*args): obj.mode=self.mode
        def builder(specs,base,uv,**kwargs):
            material=materials[kwargs['material_name']]
            material.alpha_only=kwargs['alpha_only_for_bake']
            self.assertEqual(uv,'Unique')
            self.assertTrue(kwargs['opaque_for_bake'])
            return material
        current=[]; calls=[]
        def swap(source,material):
            current.append(material); material.users=1
            def restore():
                material.users=0; materials.remove(material)
            return restore
        def bake(ctx,definition,source,image,**kwargs):
            restore=definition.node_group_builder(source,{})
            try:
                calls.append((current[-1].alpha_only,kwargs['target_uv']))
                image.array[...,:3]=.6 if current[-1].alpha_only else .25
            finally: restore()
        api=types.ModuleType('export_unit.tools.bake')
        api.setup_target_image=lambda name,w,h,**kwargs:images.new(name,w,h)
        api.BakeStateGuard=Guard;api.get_map=lambda mid:Definition()
        api.bake_one_map=bake;api.read_image_to_numpy=lambda im:im.array.copy()
        api.write_numpy_to_image=lambda im,arr,**kwargs:setattr(im,'array',arr.copy())
        api.bake_maps=types.SimpleNamespace(_swap_materials=swap)
        api.bake_nodes=types.SimpleNamespace(build_composite_material=builder)
        tools=types.ModuleType('export_unit.tools');tools.bake=api
        source=ast.parse((ROOT/'INU_tools/ops/bake_ops.py').read_text(encoding='utf8'))
        function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='_bake_live_composite_image')
        env=dict(__package__='export_unit.ops',bpy=types.SimpleNamespace(context=context,
            data=types.SimpleNamespace(images=images,materials=materials),
            ops=types.SimpleNamespace(object=types.SimpleNamespace(mode_set=lambda mode:setattr(obj,'mode',mode)))))
        with patch.dict(sys.modules,{'export_unit.tools':tools,'export_unit.tools.bake':api}):
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<export>', 'exec'),env)
            output=env['_bake_live_composite_image'](obj,[],'base','result',2,1)
        np.testing.assert_allclose(output.array[...,:3],.25)
        np.testing.assert_allclose(output.array[...,3],.6)
        self.assertEqual(calls,[(False,'Unique'),(True,'Unique')])
        self.assertEqual((obj.mode,obj.hide_render,obj.selected),('EDIT',True,True))
        self.assertEqual(set(images),{'result'})
        self.assertFalse(materials)

    def test_mask_icon_precedes_eye(self):
        source = ast.parse((ROOT / 'INU_tools/ui/panels.py').read_text(encoding='utf-8'))
        function = next(n for n in source.body if isinstance(n, ast.FunctionDef)
                        and n.name == '_draw_bake_layer_eye')
        namespace = dict(safe_icon=lambda icon: icon, inu_icon=lambda icon: {'icon': icon})
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<ui helper>', 'exec'), namespace)
        calls = []
        row = types.SimpleNamespace(label=lambda **kw: calls.append(('label', kw['icon'])),
                                    prop=lambda *args, **kw: calls.append(('eye', kw['icon'])))
        parent = types.SimpleNamespace(uid='parent', map_id='BEVEL', paint_mask_uid='mask', enabled=True)
        mask = types.SimpleNamespace(uid='mask', map_id='PAINT', paint_mask_uid='', enabled=True)
        namespace['_draw_bake_layer_eye'](row, mask, [parent, mask])
        self.assertEqual(calls, [('label', 'CON_LOCLIMIT'), ('eye', 'HIDE_OFF')])
        calls.clear()
        namespace['_draw_bake_layer_eye'](row, parent, [parent, mask])
        self.assertEqual(calls, [('eye', 'HIDE_OFF')])

    def test_blender_42_transparency_settings(self):
        source = ast.parse((ROOT / 'INU_tools/tools/compat.py').read_text(encoding='utf-8'))
        names = {'set_blend_method', 'blend_method_of', 'transparency_overlap',
                 'set_transparency_overlap', 'make_material_alpha'}
        functions = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names]
        namespace = {'ALPHA_BLEND_MODE': 'CLIP'}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<compat>', 'exec'), namespace)
        mat = types.SimpleNamespace(blend_method='OPAQUE', surface_render_method='BLENDED',
                                    use_transparency_overlap=True, show_transparent_back=True)
        self.assertTrue(namespace['make_material_alpha'](mat))
        self.assertEqual(mat.surface_render_method, 'DITHERED')
        self.assertFalse(mat.use_transparency_overlap)
        self.assertFalse(mat.show_transparent_back)

    def test_blender_42_naming_dialog_signature(self):
        source = ast.parse((ROOT / 'INU_tools/ops/bake_ops.py').read_text(encoding='utf-8'))
        operator = next(n for n in source.body if isinstance(n, ast.ClassDef)
                        and n.name == 'GTATOOLS_OT_bake_save_apply')
        invoke = next(n for n in operator.body if isinstance(n, ast.FunctionDef) and n.name == 'invoke')
        namespace = {}
        exec(compile(ast.Module(body=[invoke], type_ignores=[]), '<save dialog>', 'exec'), namespace)
        calls = []
        def invoke_props_dialog(operator, width=300, title='', confirm_text='',
                                cancel_default=False, text_ctxt='', translate=True):
            calls.append((operator.texture_name, width))
            return {'RUNNING_MODAL'}
        context = types.SimpleNamespace(active_object={'inu_bake_base': 'Gate'},
                                        window_manager=types.SimpleNamespace(invoke_props_dialog=invoke_props_dialog))
        self.assertEqual(namespace['invoke'](types.SimpleNamespace(), context, None), {'RUNNING_MODAL'})
        self.assertEqual(calls, [('Gate', 360)])

    def test_saved_material_is_permanent_and_named_after_texture(self):
        source = ast.parse((ROOT / 'INU_tools/ops/bake_ops.py').read_text(encoding='utf-8'))
        function = next(n for n in source.body if isinstance(n, ast.FunctionDef)
                        and n.name == '_apply_saved_material')
        materials = {}
        def new_material(name):
            candidate, suffix = name, 1
            while candidate in materials:
                candidate = f'{name}.{suffix:03d}'
                suffix += 1
            mat = types.SimpleNamespace(name=candidate, users=1)
            materials[candidate] = mat
            return mat
        restored = []
        def restore(obj):
            restored.append(True)
            obj.data.materials[:] = ['old material']
            obj['inu_bake_preview_on'] = 0
        cleared = []
        material_inputs = []
        def build_material(image, uv, vcol, name):
            material_inputs.append((image.name, uv, vcol))
            return materials[name]
        namespace = dict(
            bpy=types.SimpleNamespace(data=types.SimpleNamespace(materials=types.SimpleNamespace(
                get=materials.get, new=new_material))),
            _build_standard_material=build_material,
            _prelight_attr_name=lambda obj: 'Day',
            _restore_materials=restore, _clear_mat_idx_attr=lambda data: cleared.append(True))
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<saved material>', 'exec'), namespace)
        class Object(dict):
            pass
        obj = Object(inu_bake_preview_on=1, inu_bake_mode_live=1, inu_bake_overbase_on=1,
                     inu_bake_prev_mats='old', inu_bake_prev_render_uv='UV1', inu_bake_prev_mat_idx='old')
        obj.data = types.SimpleNamespace(materials=['preview'], uv_layers=[
            types.SimpleNamespace(name='UV1', active_render=True),
            types.SimpleNamespace(name='UV2', active_render=False)])
        image = types.SimpleNamespace(name='Fence')
        material = namespace['_apply_saved_material'](obj, image, 'UV2')
        self.assertEqual(material_inputs, [('Fence', 'UV2', None)],
                         'Applying a flattened texture must not multiply it by vertex colours again')
        self.assertEqual(material.name, 'Fence')
        self.assertEqual(obj.data.materials, [material])
        self.assertEqual(restored, [True])
        self.assertEqual(cleared, [True])
        self.assertEqual((obj['inu_bake_preview_on'], obj['inu_bake_mode_live'],
                          obj['inu_bake_overbase_on'], obj['inu_bake_preview_kind']), (0, 0, 0, ''))
        self.assertFalse(any(key.startswith('inu_bake_prev_') for key in obj))
        self.assertEqual([uv.active_render for uv in obj.data.uv_layers], [False, True])
        self.assertIs(namespace['_apply_saved_material'](obj, image, 'UV2'), material)
        self.assertEqual(len(materials), 1)
        material.users = 2
        other = namespace['_apply_saved_material'](obj, image, 'UV2')
        self.assertIsNot(other, material)
        self.assertFalse(other.name.startswith('INU_BakeStandard_'))


if __name__ == '__main__':
    unittest.main()
