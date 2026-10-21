"""Procedural bake regressions, without Blender: python dev/tests/test_bake_maps_unit.py."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import importlib.util
import sys
import types

SOURCE = Path(__file__).resolve().parents[2] / 'INU_tools/tools/bake/bake_maps.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
FUNCTIONS = {'_edge_distance_buffers', '_math_node', '_cavity_node',
             'build_dirt_material', 'build_edgewear_material',
             'build_curvature_material', 'build_highlight_material',
             'build_bevel_material', '_prepare_bevel', '_surface_pattern_output',
             '_pattern_weight', 'build_grunge_material', '_modulate_surface_output'}


class Socket:
    def __init__(self, node, output=False):
        self.node, self.output = node, output
        self.default_value, self.link = 0.0, None

    def value(self):
        if self.link:
            return self.link.value()
        if not self.output:
            return self.default_value
        n = self.node
        if n.kind == 'ShaderNodeAmbientOcclusion':
            return n.tree.ao_inside if n.inside else n.tree.ao_outside
        if n.kind == 'ShaderNodeNewGeometry':
            return n.tree.normal
        if n.kind == 'ShaderNodeAttribute':
            return n.tree.attributes[n.attribute_name]
        if n.kind == 'ShaderNodeTexCoord':
            return (0, 0, 0)
        if n.kind in ('ShaderNodeTexNoise', 'ShaderNodeTexVoronoi', 'ShaderNodeTexWave'):
            return n.tree.pattern
        a, b = n.inputs[0].value(), n.inputs[1].value()
        operations = {'SUBTRACT': lambda: a - b, 'MULTIPLY': lambda: a * b,
                      'ADD': lambda: a + b, 'MAXIMUM': lambda: max(a, b),
                      'MINIMUM': lambda: min(a, b), 'DIVIDE': lambda: a / b,
                      'POWER': lambda: a ** b,
                      'DOT_PRODUCT': lambda: sum(x * y for x, y in zip(a, b))}
        result = operations[n.operation]()
        return min(1.0, max(0.0, result)) if n.use_clamp else result


class Nodes(list):
    def new(self, kind):
        node = NS(kind=kind, tree=self.tree, use_clamp=False, inside=False)
        node.inputs = {k: Socket(node) for k in (0, 1, 'Color', 'Distance', 'Normal', 'Radius', 'Surface', 'Vector', 'Detail', 'Scale', 'Distortion')}
        node.outputs = {k: Socket(node, True) for k in ('Value', 'AO', 'Normal', 'True Normal', 'Fac', 'Emission', 'Object', 'Vector', 'Distance')}
        self.append(node)
        return node


class MapTests(unittest.TestCase):
    def setUp(self):
        self.tree = NS(normal=(0, 0, 1), ao_outside=1.0, ao_inside=1.0)
        self.tree.pattern = 0.25
        self.tree.nodes = Nodes()
        self.tree.nodes.tree = self.tree
        self.tree.links = NS(new=lambda src, dst: setattr(dst, 'link', src))
        self.emit = self.tree.nodes.new('ShaderNodeEmission')
        self.env = dict(math=math, DIRT_MAT_NAME='dirt', EDGEWEAR_MAT_NAME='wear',
                        CURVATURE_MAT_NAME='curve', GRUNGE_MAT_NAME='grunge',
                        _new_emit_mat=lambda name: (None, self.tree, self.emit))
        module = ast.Module(body=[n for n in TREE.body
                                 if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS],
                            type_ignores=[])
        exec(compile(module, str(SOURCE), 'exec'), self.env)

    def evaluate(self, name, params=None):
        self.env[name](params or {})
        return self.emit.inputs['Color'].value()

    def test_cavity_neutral_and_sign(self):
        self.assertEqual(self.evaluate('build_dirt_material'), 1)
        self.assertEqual(self.evaluate('build_edgewear_material'), 0)
        self.assertEqual(self.evaluate('build_curvature_material'), 0.5)
        self.tree.ao_outside = 0.9
        self.assertAlmostEqual(self.evaluate('build_dirt_material'), 0.6)
        self.assertLess(self.evaluate('build_curvature_material'), 0.5)
        self.tree.ao_outside, self.tree.ao_inside = 1.0, 0.9
        self.assertAlmostEqual(self.evaluate('build_edgewear_material'), 0.4)
        self.assertGreater(self.evaluate('build_curvature_material'), 0.5)

    def test_cavity_distance_and_geometric_normal(self):
        self.evaluate('build_dirt_material', {'cavity_distance': 0.2})
        ao = next(n for n in self.tree.nodes if n.kind == 'ShaderNodeAmbientOcclusion')
        self.assertTrue(ao.only_local)
        self.assertEqual(ao.inputs['Distance'].value(), 0.2)
        self.assertIsNotNone(ao.inputs['Normal'].link)

    def test_pattern_types_and_strength(self):
        for kind, node_type in (('NOISE', 'ShaderNodeTexNoise'),
                                ('VORONOI', 'ShaderNodeTexVoronoi'), ('WAVE', 'ShaderNodeTexWave')):
            params = dict(surface_pattern=kind, pattern_scale=12, pattern_detail=3,
                          pattern_contrast=2, pattern_strength=.5, pattern_seed=8)
            result = self.env['_pattern_weight'](self.tree, params)
            # .25 contrast 2 -> 0; strength .5 -> .5.
            self.assertAlmostEqual(result.value(), .5)
            texture = next(n for n in reversed(self.tree.nodes) if n.kind == node_type)
            self.assertEqual(texture.inputs['Scale'].value(), 12)
            coords = texture.inputs['Vector'].link.node
            self.assertEqual(coords.operation, 'ADD')
            self.assertAlmostEqual(coords.inputs[1].default_value[0], 8 * .754877)
            self.assertEqual(self.env['_pattern_weight'](self.tree, dict(params, pattern_strength=0)).value(), 1)

    def test_grunge_bakes_coverage_without_pattern(self):
        self.assertEqual(self.evaluate('build_grunge_material', {
            'surface_pattern': 'VORONOI', 'pattern_strength': 1}), (1, 1, 1, 1))
        self.assertFalse(any(n.kind.startswith('ShaderNodeTex') for n in self.tree.nodes))

    def test_pattern_preserves_geometry_neutral_values(self):
        for neutral in (0, .5, 1):
            source = self.env['_math_node'](self.tree, 'ADD', a=neutral, b=0).outputs['Value']
            result = self.env['_modulate_surface_output'](self.tree, source, neutral, {})
            self.assertEqual(result.value(), neutral)
        for value, neutral, expected in ((0, 1, .75), (1, 0, .25), (1, .5, .625)):
            source = self.env['_math_node'](self.tree, 'ADD', a=value, b=0).outputs['Value']
            result = self.env['_modulate_surface_output'](self.tree, source, neutral, {})
            self.assertEqual(result.value(), expected)
            identity = self.env['_modulate_surface_output'](self.tree, source, neutral, {'pattern_strength': 0})
            self.assertEqual(identity.value(), value)

    def test_highlight_direction_width_and_backside(self):
        params = {'highlight_elevation': 90, 'highlight_sharpness': 16}
        self.assertAlmostEqual(self.evaluate('build_highlight_material', params), 1)
        self.tree.normal = (0, 0, -1)
        self.assertEqual(self.evaluate('build_highlight_material', params), 0)
        self.tree.normal = (math.sqrt(0.5), 0, math.sqrt(0.5))
        wide = self.evaluate('build_highlight_material', dict(params, highlight_sharpness=2))
        narrow = self.evaluate('build_highlight_material', params)
        self.assertGreater(wide, narrow)
        self.tree.normal = (1, 0, 0)
        self.assertAlmostEqual(self.evaluate('build_highlight_material', {
            'highlight_azimuth': 0, 'highlight_elevation': 0}), 1)

    def distances(self, selected):
        mesh = NS(edges=[NS(index=i, select=i in selected, vertices=(i, (i + 1) % 4))
                         for i in range(4)],
                  loops=[NS(edge_index=i, vertex_index=i) for i in range(4)],
                  polygons=[NS(loop_indices=range(4))])
        return self.env['_edge_distance_buffers'](
            mesh, [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)], 0.1)

    def test_single_selected_edge_does_not_enable_adjacent_edges(self):
        values = self.distances({0})
        self.assertEqual(values, [[0, 0, 2, 2]])
        # Interpolate at the midpoint of the adjacent edge: no highlight.
        self.assertGreater((values[0][1] + values[0][2]) / 2, 0.1)

    def test_all_selected_edges_do_not_fill_face(self):
        values = self.distances(set(range(4)))
        self.assertEqual(len(values), 4)
        # Each field is affine: at face centre all edge distances are 1.
        self.assertEqual(min(sum(v) / 4 for v in values), 1)

    def test_empty_selection_is_neutral(self):
        self.assertEqual(self.distances(set()), [[0.1] * 4])

    def test_face_mode_covers_all_face_edges_without_edge_flags(self):
        mesh = NS(edges=[NS(index=i, select=False, vertices=(i,(i+1)%4)) for i in range(4)],
                  loops=[NS(edge_index=i,vertex_index=i) for i in range(4)],
                  polygons=[NS(loop_indices=range(4),select=True)])
        values=self.env['_edge_distance_buffers'](mesh,[(0,0,0),(1,0,0),(1,1,0),(0,1,0)],.1,True)
        self.assertEqual(len(values),4)

    def test_selected_bevel_shader_falloff(self):
        material = NS(node_tree=self.tree)
        self.env.update(BEVEL_MAT_NAME='bevel', bpy=NS(data=NS(
            materials=NS(get=lambda name: material))))
        self.tree.attributes = {'edge0': 0.05, 'edge1': 0.7}
        self.env['build_bevel_material']({
            'bevel_size': 0.1, 'bevel_edge_mask_attrs': ['edge0', 'edge1']})
        emit = next(n for n in self.tree.nodes if n.kind == 'ShaderNodeEmission')
        self.assertAlmostEqual(emit.inputs['Color'].value(), 0.5)
        self.tree.attributes['edge0'] = 0.1
        self.assertEqual(emit.inputs['Color'].value(), 0)
        self.tree.attributes['edge0'] = 0
        self.assertEqual(emit.inputs['Color'].value(), 1)

    def test_bevel_removes_temporary_attributes_when_builder_fails(self):
        removed = []
        def fail(params):
            raise RuntimeError('builder failed')
        self.env.update(_make_edge_mask_attr=lambda obj, radius, **kwargs: ['temp'],
                        _remove_edge_mask_attr=lambda obj, names: removed.extend(names),
                        build_bevel_material=fail, _swap_materials=lambda obj, mat: None)
        with self.assertRaises(RuntimeError):
            self.env['_prepare_bevel'](object(), {'bevel_selected_edges': True})
        self.assertEqual(removed, ['temp'])

    def test_shared_vertices_do_not_enable_unselected_face(self):
        mesh = NS(edges=[NS(index=0, select=True, vertices=(0, 1)),
                         NS(index=1, select=False, vertices=(1, 2)),
                         NS(index=2, select=False, vertices=(2, 0))],
                  loops=[NS(edge_index=0, vertex_index=0), NS(edge_index=1, vertex_index=1),
                         NS(edge_index=2, vertex_index=2), NS(edge_index=1, vertex_index=1)],
                  polygons=[NS(loop_indices=range(3)), NS(loop_indices=[3])])
        values = self.env['_edge_distance_buffers'](
            mesh, [(0, 0, 0), (1, 0, 0), (0, 1, 0)], 0.1)
        self.assertEqual(values[0][3], 0.1)

    def test_highlight_registry_defaults(self):
        # Load data definitions only; builders are placeholders in this test.
        from collections import OrderedDict
        from dataclasses import dataclass
        env = dict(OrderedDict=OrderedDict, dataclass=dataclass)
        for n in TREE.body:
            if isinstance(n, ast.FunctionDef):
                env[n.name] = lambda *args: None
        nodes = [n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'BakeMapDef'
                 or isinstance(n, ast.Assign) and any(
                     isinstance(t, ast.Name) and t.id == 'BAKE_MAPS' for t in n.targets)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), env)
        highlight = env['BAKE_MAPS']['HIGHLIGHT']
        self.assertEqual((highlight.bake_type, highlight.default_blend), ('EMIT', 'ADD'))
        self.assertEqual(highlight.default_opacity, 0.35)
        self.assertEqual(list(env['BAKE_MAPS'])[-2:], ['LIGHTMAP', 'HIGHLIGHT'])
        for mid in ('DIRT', 'EDGEWEAR', 'CURVATURE'):
            self.assertGreaterEqual(env['BAKE_MAPS'][mid].samples, 16)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        source = SOURCE.parents[2] / 'ops/bake_ops.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        names = {'_layer_faces_key', '_save_layer_faces', '_bevel_selection_attr',
                 '_stored_bevel_indices', '_save_bevel_selection', '_has_bevel_selection',
                 '_lkey', '_bake_layer_jobs'}
        self.env = {}
        composite = ast.parse((SOURCE.parent / 'bake_composite.py').read_text(encoding='utf-8'))
        helpers = [n for n in composite.body
                   if isinstance(n, ast.FunctionDef) and n.name in {'uses_bevel_mask', 'bevel_basis_key'}
                   or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                       and t.id == 'SURFACE_MAP_IDS' for t in n.targets)]
        exec(compile(ast.Module(body=helpers, type_ignores=[]), '<basis helpers>', 'exec'), self.env)
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                                     and n.name in names], type_ignores=[]), str(source), 'exec'), self.env)
        class Data(list):
            def foreach_set(self, name, values):
                for item, value in zip(self, values):
                    setattr(item, name, value)
        class Attributes(dict):
            def new(self, name, data_type, domain):
                attr = NS(name=name, domain=domain, data_type=data_type,
                          data=Data(NS(value=False) for _ in range(6 if domain == 'EDGE' else 3)))
                self[name] = attr
                return attr
            def remove(self, attr):
                del self[attr.name]
        class Object(dict):
            pass
        self.obj = Object()
        self.obj.data = NS(attributes=Attributes(), polygons=[None] * 3)

    def test_separate_layer_selections_and_rebake(self):
        save = self.env['_save_bevel_selection']
        read = self.env['_stored_bevel_indices']
        save(self.obj, 'one', faces=[1], edges=[0, 4])
        save(self.obj, 'two', edges=[2, 3])
        self.assertEqual(read(self.obj, 'one', 'EDGE'), [0, 4])
        self.assertEqual(read(self.obj, 'one', 'FACE'), [1])
        self.assertEqual(read(self.obj, 'two', 'EDGE'), [2, 3])
        save(self.obj, 'one', faces=[2])
        self.assertEqual(read(self.obj, 'one', 'FACE'), [2])
        self.assertEqual(read(self.obj, 'one', 'EDGE'), [])
        self.assertEqual(read(self.obj, 'two', 'EDGE'), [2, 3])

    def test_legacy_faces_and_empty_selection(self):
        read = self.env['_stored_bevel_indices']
        self.obj['inu_bake_faces_old'] = '0,2,99'
        self.assertEqual(read(self.obj, 'old', 'FACE'), [0, 2])
        self.env['_save_bevel_selection'](self.obj, 'old')
        self.assertEqual(read(self.obj, 'old', 'FACE'), [])
        self.assertFalse(self.env['_has_bevel_selection'](self.obj, 'old', 'FACE'))

    def test_topology_attribute_is_used_instead_of_stale_face_indices(self):
        self.env['_save_bevel_selection'](self.obj, 'one', faces=[1])
        attr = self.obj.data.attributes['inu_bake_face_one']
        # Model a topology edit moving the attribute value to another face.
        attr.data[1].value, attr.data[2].value = False, True
        self.assertEqual(self.env['_stored_bevel_indices'](self.obj, 'one', 'FACE'), [2])

    def test_bevel_basis_jobs_are_private_and_do_not_replace_own_masks(self):
        layers = [NS(uid='first', map_id='EDGEWEAR', effect_basis='BEVEL'),
                  NS(uid='second', map_id='DIRT', effect_basis='BEVEL'),
                  NS(uid='bevel', map_id='BEVEL', effect_basis='BEVEL'),
                  NS(uid='paint', map_id='PAINT', effect_basis='BEVEL'),
                  NS(uid='own', map_id='EDGEWEAR', effect_basis='SELF')]
        jobs = list(self.env['_bake_layer_jobs'](layers))
        self.assertEqual([(layer.uid, mid, key, auxiliary)
                          for layer, mid, key, auxiliary in jobs], [
            ('first', 'BEVEL', 'first__bevel_basis', True),
            ('first', 'EDGEWEAR', 'first', False),
            ('second', 'BEVEL', 'second__bevel_basis', True),
            ('second', 'DIRT', 'second', False),
            ('bevel', 'BEVEL', 'bevel', False),
            ('paint', 'PAINT', 'paint', False),
            ('own', 'EDGEWEAR', 'own', False)])


class UVTargetTests(unittest.TestCase):
    def test_texture_bake_does_not_create_or_repack_uvs(self):
        source=SOURCE.parents[2]/'ops/bake_ops.py'
        tree=ast.parse(source.read_text(encoding='utf8'))
        operator=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GTATOOLS_OT_bake_run')
        calls=[n.func.attr for n in ast.walk(operator) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Attribute)]
        self.assertFalse({'ensure_lightmap_uv','smart_project','lightmap_pack'} & set(calls))

    def test_new_uv_preserves_edge_selection_hidden_elements_and_render_uv(self):
        source=SOURCE.with_name('bake_uv.py')
        tree=ast.parse(source.read_text(encoding='utf8'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='ensure_lightmap_uv')
        class Elements(list):
            def foreach_get(self,key,buffer): buffer[:]=[getattr(e,key) for e in self]
            def foreach_set(self,key,values):
                for element,value in zip(self,values): setattr(element,key,value)
        class UVs(list):
            def get(self,name): return next((uv for uv in self if uv.name==name),None)
            def new(self,name):
                for uv in self: uv.active_render=False
                uv=NS(name=name,active_render=True);self.append(uv);return uv
        uvs=UVs([NS(name='Trim',active_render=True)])
        uvs.active=uvs[0]
        groups=[Elements([NS(select=True,hide=False),NS(select=False,hide=True)]) for _ in range(3)]
        mesh=NS(uv_layers=uvs,vertices=groups[0],edges=groups[1],polygons=groups[2],update=lambda:None)
        obj=NS(data=mesh,mode='OBJECT',selected=True)
        other=NS(selected=True)
        for item in (obj,other):
            item.select_set=lambda value,item=item:setattr(item,'selected',value)
            item.select_get=lambda item=item:item.selected
        class Objects(list): pass
        objects=Objects([obj,other]);objects.active=obj
        def select_all(**kwargs):
            for group in groups:
                for e in group: e.select=True
        def reveal(**kwargs):
            for group in groups:
                for e in group: e.hide=False
        calls=[]
        def smart(**kwargs): calls.append(('smart',kwargs)); return {'FINISHED'}
        def lightmap(**kwargs): calls.append(('lightmap',kwargs)); return {'FINISHED'}
        bpy=NS(context=NS(view_layer=NS(objects=objects)),ops=NS(
            object=NS(mode_set=lambda mode:setattr(obj,'mode',mode)),
            mesh=NS(select_all=select_all,reveal=reveal),
            uv=NS(lightmap_pack=lightmap,smart_project=smart)))
        env=dict(bpy=bpy,math=math,_UV_LAYER_CAP=8,LIGHTMAP_UV_NAME='LightMap')
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),env)
        self.assertEqual(env['ensure_lightmap_uv'](obj,name='Unique'),'Unique')
        self.assertEqual(uvs.active.name,'Trim')
        self.assertEqual([uv.name for uv in uvs if uv.active_render],['Trim'])
        for group in groups:
            self.assertEqual([(e.select,e.hide) for e in group],[(True,False),(False,True)])
        self.assertTrue(other.selected)
        self.assertEqual(obj.mode,'OBJECT')
        self.assertEqual(calls[0][0],'smart')
        self.assertEqual(calls[0][1]['margin_method'],'FRACTION')
        self.assertEqual(calls[0][1]['island_margin'],.002)
        self.assertEqual(len(calls),1)
        # A cancelled Smart Project must fall through to Lightmap Pack, whose
        # margin also accepts a UV fraction directly (not fraction * 1000).
        bpy.ops.uv.smart_project=lambda **kwargs:{'CANCELLED'}
        self.assertEqual(env['ensure_lightmap_uv'](obj,name='Fallback',margin=2/1024),'Fallback')
        self.assertEqual(calls[-1],('lightmap',dict(PREF_CONTEXT='ALL_FACES',PREF_MARGIN_DIV=2/1024)))

    def test_shared_footprints_and_tiling_need_unique_target(self):
        import numpy as np
        source=SOURCE.with_name('bake_uv.py')
        tree=ast.parse(source.read_text(encoding='utf-8'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='uv_needs_unique_target')
        env=dict(np=np)
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),env)
        class Data:
            def foreach_get(self,key,out): out[:]=self.coordinates
        data=Data()
        mesh=NS(loops=[None]*6,polygons=[NS(loop_indices=range(3)),NS(loop_indices=range(3,6))],
                uv_layers={'UV':NS(data=data)})
        data.coordinates=[0,0, .4,0, 0,.4, 0,.4, .4,0, 0,0]
        self.assertTrue(env['uv_needs_unique_target'](mesh,'UV'))
        data.coordinates=[0,0, .4,0, 0,.4, .6,.6, 1,.6, .6,1]
        self.assertFalse(env['uv_needs_unique_target'](mesh,'UV'))
        data.coordinates[0]=-0.2
        self.assertTrue(env['uv_needs_unique_target'](mesh,'UV'))
        data.coordinates=[0,0, .001,0, 0,.001, .5,.5, .501,.5, .5,.501]
        self.assertFalse(env['uv_needs_unique_target'](mesh,'UV'))
        self.assertTrue(env['uv_needs_unique_target'](mesh,'UV',minimum_fill=.05))


class StackedUVBevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package=types.ModuleType('bevel_raster_unit');package.__path__=[str(SOURCE.parent)]
        sys.modules[package.__name__]=package
        for name in ('bake_composite','bake_edge_mask'):
            spec=importlib.util.spec_from_file_location(package.__name__+'.'+name,SOURCE.with_name(name+'.py'))
            module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        cls.raster=staticmethod(module.rasterize_bevel_uv)
        cls.box_max=staticmethod(module._box_max)

    @classmethod
    def tearDownClass(cls):
        for name in tuple(sys.modules):
            if name.startswith('bevel_raster_unit'):sys.modules.pop(name,None)

    def setUp(self):
        import numpy as np
        self.np=np
        self.uv=np.array([(0,0),(1,0),(1,1),(0,1)]*2,dtype=float)
        self.triangles=[(0,1,2),(0,2,3),(4,5,6),(4,6,7)]

    def test_unselected_copy_cannot_erase_selected_edge(self):
        fields=[[0,0,1,1,.25,.25,.25,.25]]
        solo=self.raster(self.uv,self.triangles[:2],fields,.25,32,32)
        union=self.raster(self.uv,self.triangles,fields,.25,32,32)
        reversed_order=self.raster(self.uv,list(reversed(self.triangles)),fields,.25,32,32)
        self.np.testing.assert_array_equal(solo,union)
        self.np.testing.assert_array_equal(union,reversed_order)
        self.assertGreater(union[0,16,0],.8)
        self.assertEqual(union[16,16,0],0)

    def test_different_copies_contribute_different_edges(self):
        result=self.raster(self.uv,self.triangles,[[0,0,1,1,1,1,0,0]],.25,32,32)
        self.assertGreater(result[0,16,0],.8)
        self.assertGreater(result[-1,16,0],.8)
        self.assertEqual(result[16,16,0],0)

    def test_tiled_faces_repeat_without_changing_uv(self):
        original=self.uv.copy();self.uv[4:]+=1
        result=self.raster(self.uv,self.triangles,[[.25]*4+[0,0,1,1]],.25,32,32)
        self.assertGreater(result[0,16,0],.8)
        self.np.testing.assert_array_equal(self.uv[4:],original[4:]+1)

    def test_zero_radius_and_empty_selection_are_black(self):
        result=self.raster(self.uv,self.triangles,[[0]*8],0,8,8)
        self.assertFalse(self.np.any(result[...,:3]))
        result=self.raster(self.uv,self.triangles,[[.25]*8],.25,8,8)
        self.assertFalse(self.np.any(result[...,:3]))

    def test_padding_filter_matches_brute_force(self):
        source=self.np.arange(35,dtype=float).reshape(5,7)
        for radius in (1,2,4):
            expected=self.np.array([[source[max(0,y-radius):y+radius+1,max(0,x-radius):x+radius+1].max()
                                    for x in range(7)] for y in range(5)])
            self.np.testing.assert_array_equal(self.box_max(source,radius),expected)


class AlphaBakeTests(unittest.TestCase):
    def setUp(self):
        from contextlib import ExitStack
        functions = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in {
            '_prepare_alpha', '_prepare_map_for_bake', 'bake_one_map',
            '_tex_uv_name', '_find_alpha_source'}]
        self.removed = []
        self.env = dict(ExitStack=ExitStack, ALPHA_MAT_PREFIX='alpha_',
            _try_alpha_pixel_projection=lambda *args, **kwargs: False,
            bpy=NS(data=NS(materials=NS(remove=self.removed.append))))
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), 'exec'), self.env)

    def source(self, name, alpha):
        material = NS(name=name + '_material', alpha=alpha)
        return NS(name=name, type='MESH', material_slots=[NS(material=material)])

    def bake(self, fail=False):
        low = self.source('Low', 1.)
        high = self.source('Hi', .25)
        another = self.source('Hi_other', .7)
        original = [o.material_slots[0].material for o in (low, high, another)]
        self.env['_build_alpha_emit_material'] = lambda name, material: NS(
            name=name, alpha=material.alpha, users=0, temporary=True)
        self.env['prepare_map'] = lambda definition, obj, context, params, **kw: self.env['_prepare_alpha'](obj, params)
        sampled = []
        restored = []
        def cycles(*args, **kwargs):
            self.assertIs(low.material_slots[0].material, original[0])
            sampled.extend(o.material_slots[0].material.alpha for o in (high, another))
            self.assertTrue(all(o.material_slots[0].material.temporary for o in (high, another)))
            if fail:
                raise RuntimeError('projection failed')
        self.env['bake_core'] = NS(prepare_bake_targets=lambda obj, image: obj,
            run_cycles_bake=cycles, restore_bake_targets=restored.append,
            restore_active_uv=lambda token: None, unpin_image_nodes=lambda token: None)
        definition = NS(id='ALPHA', bake_type='EMIT', samples=1,
            pass_direct=False, pass_indirect=False, pass_color=True)
        try:
            self.env['bake_one_map'](NS(selected_objects=[low, high, another]), definition, low, {},
                params={}, selected_to_active=True, keep_visible=(high, another))
        finally:
            self.assertEqual([o.material_slots[0].material for o in (low, high, another)], original)
            self.assertEqual(len(self.removed), 2)
            self.assertEqual(restored, [low])
        return sampled

    def test_hilow_reads_each_hi_alpha_leaving_low_unchanged(self):
        self.assertEqual(self.bake(), [.25, .7])

    def test_failed_projection_restores_hi_materials(self):
        with self.assertRaisesRegex(RuntimeError, 'projection failed'):
            self.bake(fail=True)

    def test_source_setup_failure_restores_prepared_sources(self):
        high, other, low = self.source('Hi', .2), self.source('Other', .6), self.source('Low', 1.)
        restored = []
        def prepare(definition, obj, *args, **kwargs):
            if obj is other:
                raise RuntimeError('setup failed')
            return lambda: restored.append(obj)
        self.env['prepare_map'] = prepare
        with self.assertRaisesRegex(RuntimeError, 'setup failed'):
            self.env['_prepare_map_for_bake'](NS(id='ALPHA'), low, None, {},
                selected_to_active=True, keep_visible=(high, other))
        self.assertEqual(restored, [high])

    def test_uv_alpha_still_uses_target_material(self):
        seen = []
        self.env['prepare_map'] = lambda definition, obj, *args, **kwargs: seen.append(obj)
        low = self.source('Low', .4)
        self.env['_prepare_map_for_bake'](NS(id='ALPHA'), low, None, {})
        self.assertEqual(seen, [low])

    def test_partial_material_setup_is_cleaned_up(self):
        materials = [NS(alpha=.2), NS(alpha=.7)]
        obj = NS(material_slots=[NS(material=m) for m in materials])
        temporary = NS(users=0)
        def build(name, material):
            if material is materials[1]:
                raise RuntimeError('material setup failed')
            return temporary
        self.env['_build_alpha_emit_material'] = build
        with self.assertRaisesRegex(RuntimeError, 'material setup failed'):
            self.env['_prepare_alpha'](obj, {})
        self.assertEqual([s.material for s in obj.material_slots], materials)
        self.assertEqual(self.removed, [temporary])

    def test_hi_texture_alpha_uses_hi_explicit_uv(self):
        image = object()
        uv = NS(type='UVMAP', uv_map='HiUV')
        texture = NS(type='TEX_IMAGE', image=image, inputs={'Vector': NS(links=[NS(from_node=uv)])})
        alpha = NS(is_linked=True, links=[NS(from_node=texture)])
        bsdf = NS(type='BSDF_PRINCIPLED', inputs={'Alpha': alpha})
        material = NS(use_nodes=True, node_tree=NS(nodes=[bsdf, texture]))
        self.assertEqual(self.env['_find_alpha_source'](material), (image, 'HiUV', 1.))
        alpha.is_linked, alpha.default_value = False, .35
        self.assertEqual(self.env['_find_alpha_source'](material), (None, '', .35))


if __name__ == '__main__':
    unittest.main()
