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
            return px[:3] if self.name == 'Color' else px[3]
        if node.kind in ('ShaderNodeSeparateColor', 'ShaderNodeSeparateRGB'):
            return node.inputs[0].value()[0]
        a, b = node.inputs[0].value(), node.inputs[1].value()
        result = {'LESS_THAN': lambda: float(a < b), 'GREATER_THAN': lambda: float(a > b),
                  'SUBTRACT': lambda: a - b, 'MULTIPLY': lambda: a * b}[node.operation]()
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
            'ShaderNodeBsdfTransparent': ([], [0]),
            'ShaderNodeMixShader': (['Fac', 1, 2], [0]),
        }[kind]
        node = types.SimpleNamespace(kind=kind)
        node.inputs = {key: Socket(node, key) for key in inputs}
        node.outputs = {key: Socket(node, key) for key in outputs}
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

    @classmethod
    def tearDownClass(cls):
        for key in list(sys.modules):
            if key == 'bpy' or key.startswith('inu_preview_unit'):
                if key in cls.saved_modules:
                    sys.modules[key] = cls.saved_modules[key]
                else:
                    sys.modules.pop(key, None)

    def check_alpha(self, array, invert=False, opacity=1.0):
        image = types.SimpleNamespace(array=array, sample=0)
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
        namespace = dict(
            bpy=types.SimpleNamespace(data=types.SimpleNamespace(materials=types.SimpleNamespace(
                get=materials.get, new=new_material))),
            _build_standard_material=lambda image, uv, vcol, name: materials[name],
            _prelight_attr_name=lambda obj: None,
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
