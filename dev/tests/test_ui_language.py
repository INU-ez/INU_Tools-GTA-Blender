"""Language selection and RNA source strings without importing Blender."""

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('inu_ui_language_test', ROOT/'INU_tools/tools/ui_language.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


def test_rna_labels_are_english_and_keep_property_identifiers():
    english = {'Пути': 'Paths', 'Описание': 'Description', 'Ширина': 'Width'}
    translate = ui.source_translator(english, [english, {'Пути': 'Rutas'}])
    prop = SimpleNamespace(keywords=dict(name='Ширина', description='Описание',
        items=[('ID', 'Пути', 'Описание', 3, 4), None], default='ID'))
    cls = type('Panel', (), dict(bl_label='Rutas', bl_description='Описание',
                                __annotations__={'width': prop}))
    ui.prepare_class(cls, translate)
    assert cls.bl_label == 'Paths' and cls.bl_description == 'Description'
    assert prop.keywords['name'] == 'Width'
    assert prop.keywords['items'] == [('ID', 'Paths', 'Description', 3, 4), None]
    assert prop.keywords['default'] == 'ID'
    assert prop.keywords['translation_context'] == ui.CONTEXT
    ui.prepare_class(cls, translate)
    assert cls.bl_label == 'Paths'


def test_callable_enums_and_custom_contexts_are_preserved():
    callback = lambda *_: []
    prop = SimpleNamespace(keywords=dict(items=callback, translation_context='Custom'))
    cls = type('Settings', (), {'__annotations__': {'mode': prop}})
    ui.prepare_class(cls, lambda x: x)
    assert prop.keywords['items'] is callback
    assert prop.keywords['translation_context'] == 'Custom'


def test_postponed_properties_translate_only_display_text():
    english = {'Пути': 'Paths', 'Описание': 'Description'}
    cls = type('Operator', (), {'__annotations__': {'mode':
        'EnumProperty(name=T("Пути"), description="Описание", items=[("ID", T("Пути"), "Описание")], default="ID")'}})
    ui.prepare_class(cls, ui.source_translator(english, [english]))
    call = ast.parse(cls.__annotations__['mode'], mode='eval').body
    keywords = {kw.arg: kw.value for kw in call.keywords}
    assert keywords['name'].value == 'Paths'
    assert keywords['description'].value == 'Description'
    assert keywords['default'].value == 'ID'
    assert keywords['translation_context'].value == ui.CONTEXT
    assert keywords['items'].elts[0].elts[1].value == 'Paths'


def test_english_source_translates_back_to_russian_and_spanish():
    english = {'Пути': 'Paths'}
    assert ui.translation_entries(english, {}, (ui.CONTEXT,), russian=True)[ui.CONTEXT, 'Paths'] == 'Пути'
    assert ui.translation_entries(english, {'Пути': 'Rutas'}, (ui.CONTEXT,))[ui.CONTEXT, 'Paths'] == 'Rutas'


@pytest.mark.parametrize('language, enabled, detected, expected', [
    ('en_US', True, 'ru_RU', 'en_US'),
    ('ru_RU', False, 'ru_RU', 'en_US'),
    ('es', True, 'en_US', 'es'),
    ('DEFAULT', True, 'ru_RU', 'ru_RU'),
])
def test_explicit_ui_language_wins_over_detected_locale(language, enabled, detected, expected):
    tree = ast.parse((ROOT/'INU_tools/__init__.py').read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'get_locale')
    view = SimpleNamespace(language=language, use_translate_interface=enabled)
    bpy = SimpleNamespace(context=SimpleNamespace(preferences=SimpleNamespace(view=view)),
                          app=SimpleNamespace(translations=SimpleNamespace(locale=detected)))
    ns = {'bpy': bpy}
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'get_locale', 'exec'), ns)
    assert ns['get_locale']() == expected
