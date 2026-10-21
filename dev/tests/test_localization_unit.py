"""Check translation dictionaries and static UI text without Blender."""
import ast
from collections import Counter
from pathlib import Path
import re
import string
import unittest

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / 'INU_tools'
EXCLUDED = {'geo_panels.py', 'geo_curb_ops.py', 'geo_building_ops.py',
            'autobuilding_ui.py'}  # Not registered or shipped in this release.


def language_items(code):
    tree = ast.parse((ADDON / 'locale' / (code + '.py')).read_text(encoding='utf-8'))
    dictionary = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'LANG'
                              for t in n.targets))
    return [(ast.literal_eval(k), ast.literal_eval(v))
            for k, v in zip(dictionary.keys, dictionary.values)]


def ui_literals():
    result = set()
    for path in ADDON.rglob('*.py'):
        if 'locale' in path.parts or path.name in EXCLUDED:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Name) and node.func.id in {'T', '_projection_error'}
                        and node.args and isinstance(node.args[0], ast.Constant)):
                    result.add(node.args[0].value)
                if getattr(node.func, 'id', '').endswith('Property'):
                    for keyword in node.keywords:
                        if (keyword.arg in ('name', 'description')
                                and isinstance(keyword.value, ast.Constant)):
                            result.add(keyword.value.value)
            elif isinstance(node, ast.Assign):
                if (any(isinstance(t, ast.Name)
                        and t.id in ('bl_label', 'bl_description') for t in node.targets)
                        and isinstance(node.value, ast.Constant)):
                    result.add(node.value.value)
            elif isinstance(node, ast.ClassDef):
                if any(ast.unparse(base) == 'bpy.types.Operator' for base in node.bases):
                    doc = ast.get_docstring(node, clean=False)
                    if doc:
                        result.add(doc.strip())
    return {s for s in result if isinstance(s, str) and re.search('[А-Яа-яЁё]', s)}


class LocalizationTests(unittest.TestCase):
    def test_dictionary_keys_are_unique(self):
        for code in ('eng', 'spa'):
            with self.subTest(language=code):
                duplicates = [key for key, count in
                              Counter(k for k, _ in language_items(code)).items()
                              if count > 1]
                self.assertEqual(duplicates, [])

    def test_active_static_ui_literals_have_translations(self):
        literals = ui_literals()
        for code in ('eng', 'spa'):
            with self.subTest(language=code):
                self.assertEqual(sorted(literals - dict(language_items(code)).keys()), [])

    def test_format_fields_are_preserved(self):
        formatter = string.Formatter()

        def fields(text):
            try:
                return Counter(field for _, field, _, _ in formatter.parse(text)
                               if field is not None)
            except ValueError:
                return None  # Some entries contain literal code or braces.

        for code in ('eng', 'spa'):
            mismatches = [source for source, translated in language_items(code)
                          if fields(source) != fields(translated)]
            with self.subTest(language=code):
                self.assertEqual(mismatches, [])


if __name__ == '__main__':
    unittest.main()
