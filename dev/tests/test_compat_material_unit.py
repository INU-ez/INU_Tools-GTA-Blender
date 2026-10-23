"""Material node usage checks without importing or starting Blender."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'INU_tools/tools/compat.py'


class MaterialNodeUsageTests(unittest.TestCase):
    def check_material(self, version, material):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        function = next(n for n in tree.body
                        if isinstance(n, ast.FunctionDef)
                        and n.name == 'material_uses_nodes')
        namespace = {'BL': version}
        exec(compile(ast.Module(body=[function], type_ignores=[]),
                     str(SOURCE), 'exec'), namespace)
        return namespace['material_uses_nodes'](material)

    def test_disabled_nodes_with_retained_tree_before_blender_5(self):
        for version in ((2, 83, 0), (3, 6, 0), (4, 2, 0), (4, 5, 0)):
            with self.subTest(version=version):
                material = SimpleNamespace(node_tree=object(), use_nodes=False)
                self.assertFalse(self.check_material(version, material))
                material.use_nodes = True
                self.assertTrue(self.check_material(version, material))

    def test_missing_material_or_tree_is_not_node_based(self):
        for version in ((4, 2, 0), (5, 0, 0), (5, 2, 3)):
            with self.subTest(version=version):
                self.assertFalse(self.check_material(version, None))
                self.assertFalse(self.check_material(
                    version, SimpleNamespace(node_tree=None, use_nodes=True)))

    def test_blender_5_does_not_read_deprecated_use_nodes(self):
        class Material:
            node_tree = object()

            @property
            def use_nodes(self):
                raise AssertionError('Deprecated property was read')

        for version in ((5, 0, 0), (5, 2, 3)):
            with self.subTest(version=version):
                self.assertTrue(self.check_material(version, Material()))


if __name__ == '__main__':
    unittest.main()
