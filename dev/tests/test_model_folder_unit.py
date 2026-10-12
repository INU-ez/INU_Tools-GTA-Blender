"""Python checks for loose map import, without starting Blender."""
import ast
import inspect
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


class StopBeforeBlenderGeometry(Exception):
    pass


class FolderImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the existing isolated operator loader, without importing pytest.
        tree = ast.parse((ROOT / 'dev/tests/test_import_from_img_sources.py').read_text(encoding='utf-8'))
        definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                       and n.name in ('_is_ours', '_load_isolated')]
        namespace = dict(ROOT=ROOT, sys=sys, types=types)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), '<isolated loader>', 'exec'), namespace)
        cls.ops, cls.modules = namespace['_load_isolated']()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'dev/tests')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        mathutils = types.SimpleNamespace(Quaternion=object, Vector=object, Matrix=object)
        self.patch = mock.patch.dict(sys.modules, dict(self.modules, mathutils=mathutils))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_recursive_sources_and_col_library(self):
        from INU_tools.core.model_folder import ModelFolder
        folder = self.root / 'models'
        (folder / 'nested').mkdir(parents=True)
        (folder / 'Gate.DFF').write_bytes(b'first')
        (folder / 'nested/gate.dff').write_bytes(b'duplicate')
        (folder / 'nested/shared.TXD').write_bytes(b'textures')
        (folder / 'other.img').write_bytes(b'ignored')
        record = b'COLL' + struct.pack('<I', 24) + b'Gate'.ljust(22, b'\0') + struct.pack('<H', 10)
        (folder / 'nested/library.col').write_bytes(record)
        source = ModelFolder(str(folder))
        self.assertEqual(set(source.files), {'gate.dff', 'shared.txd', 'library.col'})
        self.assertEqual(source.extract_file(str(folder), 'GATE.dff'), b'first')
        self.assertTrue(source.duplicates)
        self.assertEqual(source.col_index()['gate'][1:], ('library.col', 0, 32))

    def test_exclusive_path_callbacks(self):
        tree = ast.parse((ROOT / 'INU_tools/scene_settings.py').read_text(encoding='utf-8'))
        names = ('_game_import_root_changed', '_models_import_root_changed')
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        namespace = {'_save_paths_proxy': lambda *args: None}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<path callbacks>', 'exec'), namespace)
        class Settings:
            def __setattr__(self, key, value):
                object.__setattr__(self, key, value)
                callback = names[0] if key == 'gtatools_game_root' else names[1]
                namespace[callback](self, None)
        settings = Settings()
        object.__setattr__(settings, 'gtatools_game_root', '')
        object.__setattr__(settings, 'gtatools_models_root', '')
        settings.gtatools_game_root = 'game'
        settings.gtatools_models_root = 'models'
        self.assertEqual((settings.gtatools_game_root, settings.gtatools_models_root), ('', 'models'))
        settings.gtatools_game_root = 'game2'
        self.assertEqual((settings.gtatools_game_root, settings.gtatools_models_root), ('game2', ''))
        settings.gtatools_models_root = ''
        self.assertEqual(settings.gtatools_game_root, 'game2')

    def check_import_sources(self, binary=False):
        from INU_tools.core import img, ipl
        folder = self.root / 'models'
        (folder / 'nested').mkdir(parents=True)
        (folder / 'nested/Gate.DFF').write_bytes(b'geometry')
        ide = self.root / 'selected.ide'
        ide.write_text('objs\n10, Gate, shared, 100, 0\nend\n')
        ipl_path = self.root / 'map.ipl'
        if binary:
            ipl_path.write_bytes(ipl._write_binary_ipl(ipl.IplFile(instances=[
                ipl.IplInstance(model_id=10, model_name='', lod_index=-1)])))
        else:
            ipl_path.write_text('inst\n10, Gate, 0, 1, 2, 3, 0, 0, 0, 1, -1\nend\n')
        stale_img = self.root / 'stale.img'
        stale_img.write_bytes(b'not an archive')
        class Scene(dict):
            pass
        scene = Scene(gtatools_found_imgs=str(stale_img))
        scene.inu_settings = types.SimpleNamespace(
            gtatools_img_path=str(stale_img), gtatools_models_root=str(folder),
            gtatools_game_root='', gtatools_ide_path='', gtatools_ipl_path=str(ipl_path),
            gtatools_ide_sync_list=[types.SimpleNamespace(path=str(ide))],
            gtatools_ipl_sync_list=[], gtatools_img_use_gta_dat=True,
            gtatools_img_skip_lod=False, gtatools_img_load_txd=False, gtatools_map_load_col=False)
        snapshot = {}
        def stop_at_collection(name):
            state = inspect.currentframe().f_back.f_back.f_locals
            snapshot.update({key: state[key] for key in ('archives', 'img_index', 'ide_models', 'instances')})
            raise StopBeforeBlenderGeometry()
        self.modules['bpy'].data.collections = types.SimpleNamespace(get=stop_at_collection)
        op = types.SimpleNamespace(report=lambda *args: None, _final=None, _total=0, _done=0)
        with mock.patch.object(img, 'read_directory', side_effect=AssertionError('IMG must not be opened')):
            with self.assertRaises(StopBeforeBlenderGeometry):
                next(self.ops.GTATOOLS_OT_import_from_img._work(op, types.SimpleNamespace(scene=scene)))
        self.assertEqual(snapshot['archives'], [str(folder)])
        self.assertEqual(snapshot['img_index']['gate.dff'], (str(folder), 'Gate.DFF'))
        self.assertEqual(snapshot['ide_models'][10].txd_name, 'shared')
        self.assertEqual(snapshot['instances'][0].model_name.lower(), 'gate')
        if not binary:
            instance = snapshot['instances'][0]
            self.assertEqual((instance.pos_x, instance.pos_y, instance.pos_z), (1.0, 2.0, 3.0))

    def test_folder_import_ignores_stale_img_and_uses_selected_ide(self):
        self.check_import_sources()

    def test_binary_ipl_gets_model_name_from_selected_ide(self):
        self.check_import_sources(binary=True)

    def test_both_folders_are_rejected_before_import(self):
        settings = types.SimpleNamespace(gtatools_img_path='', gtatools_game_root='game',
                                          gtatools_models_root='models')
        reports = []
        operator = types.SimpleNamespace(report=lambda *args: reports.append(args))
        context = types.SimpleNamespace(scene=types.SimpleNamespace(inu_settings=settings))
        self.assertEqual(self.ops.GTATOOLS_OT_import_from_img.execute(operator, context), {'CANCELLED'})
        self.assertEqual(len(reports), 1)

    def test_existing_img_import_regressions(self):
        pytest_stub = types.SimpleNamespace(fixture=lambda **kw: lambda function: function,
                                            raises=self.assertRaises)
        path = ROOT / 'dev/tests/test_import_from_img_sources.py'
        with mock.patch.dict(sys.modules, {'pytest': pytest_stub}):
            spec = importlib.util.spec_from_file_location('img_source_regression', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with mock.patch.dict(sys.modules, dict(module._OURS, mathutils=module._MATHUTILS)):
                tests = [getattr(module, name) for name in dir(module) if name.startswith('test_')]
                for function in tests:
                    directory = self.root / function.__name__
                    directory.mkdir()
                    function(directory)
                self.assertEqual(len(tests), 6)


if __name__ == '__main__':
    unittest.main()
