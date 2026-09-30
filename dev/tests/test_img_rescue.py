"""Импорт из IMG: добор текстур из ВСЕХ архивов, не только из основного IMG.

`_rescue_textures_from_img(archives, img_index, …)` ищет недостающие текстуры
во всех архивах, учитывает только выигравшую копию TXD (ту, что в img_index)
и импортирует из TXD только недостающие текстуры (name_filter).

ops/img_ops.py грузится изолированно с заглушкой bpy.
"""

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _is_ours(name):
    return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))


def _load_isolated():
    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for key in saved:
        del sys.modules[key]
    try:
        bpy = types.ModuleType('bpy')
        bpy.types = types.SimpleNamespace(Operator=type('Operator', (), {}))
        props = types.ModuleType('bpy.props')
        for _n in ('BoolProperty', 'StringProperty', 'IntProperty',
                   'FloatProperty', 'EnumProperty', 'CollectionProperty',
                   'PointerProperty'):
            setattr(props, _n, lambda *a, **k: None)
        bpy.props = props
        bpy.path = types.SimpleNamespace(abspath=lambda p: p)
        bpy.data = types.SimpleNamespace(materials=[])
        sys.modules['bpy'] = bpy
        sys.modules['bpy.props'] = props
        pkg = types.ModuleType('INU_tools')
        pkg.__path__ = [str(ROOT / 'INU_tools')]
        pkg.T = lambda s: s
        sys.modules['INU_tools'] = pkg
        import importlib
        return importlib.import_module('INU_tools.ops.img_ops')
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)


img_ops = _load_isolated()


class _Mat(dict):
    """Материал с именем текстуры из DFF, но без картинки."""
    use_nodes = False
    node_tree = None


class _Calls:
    def __init__(self, blobs):
        self.blobs, self.extracted, self.imported = blobs, [], []

    def extract_file(self, arch, name):
        self.extracted.append((arch, name))
        return self.blobs.get((arch, name))

    def import_txd(self, filepath, name_filter=None):
        self.imported.append((Path(filepath).name, name_filter))


@pytest.fixture
def scene(monkeypatch):
    def _setup(tex_names, tex_index):
        mats = [_Mat(dff_texture_name=t) for t in tex_names]
        monkeypatch.setattr(img_ops.bpy, 'data',
                            SimpleNamespace(materials=mats), raising=False)
        asked = []

        def _idx(arch):
            asked.append(arch)
            return tex_index.get(arch, {})
        monkeypatch.setattr(img_ops, '_get_img_texture_index', _idx)
        return asked
    return _setup


def test_txd_only_in_second_archive(scene, tmp_path):
    scene(['Bark'], {'B.img': {'bark': {'trees'}}})
    img_index = {'trees.txd': ('B.img', 'Trees.txd')}
    c = _Calls({('B.img', 'Trees.txd'): b'txd'})
    n = img_ops._rescue_textures_from_img(['A.img', 'B.img'], img_index,
                                          str(tmp_path), c.extract_file,
                                          c.import_txd)
    assert n == 1
    assert c.extracted == [('B.img', 'Trees.txd')]
    assert c.imported == [('trees.txd', {'bark'})]


def test_only_winning_copy_is_used(scene, tmp_path):
    # TXD в обоих архивах; img_index берёт его из A — копия из B не в счёт.
    scene(['grass'], {'A.img': {'grass': {'veg'}},
                      'B.img': {'grass': {'veg'}}})
    img_index = {'veg.txd': ('A.img', 'veg.txd')}
    c = _Calls({('A.img', 'veg.txd'): b'a', ('B.img', 'veg.txd'): b'b'})
    img_ops._rescue_textures_from_img(['A.img', 'B.img'], img_index,
                                      str(tmp_path), c.extract_file,
                                      c.import_txd)
    assert c.extracted == [('A.img', 'veg.txd')]

    # Текстура есть только в проигравшей копии — её не добираем.
    scene(['moss'], {'B.img': {'moss': {'veg'}}})
    c = _Calls({('B.img', 'veg.txd'): b'b'})
    n = img_ops._rescue_textures_from_img(['A.img', 'B.img'], img_index,
                                          str(tmp_path), c.extract_file,
                                          c.import_txd)
    assert n == 0 and c.extracted == []


def test_nothing_missing_skips_index(scene, tmp_path):
    asked = scene([], {'A.img': {'x': {'y'}}})
    c = _Calls({})
    assert img_ops._rescue_textures_from_img(['A.img'], {}, str(tmp_path),
                                             c.extract_file,
                                             c.import_txd) == 0
    assert asked == [] and c.extracted == []


def test_found_archive_without_main_img(scene, tmp_path):
    # Основной IMG пуст (строки IMG нет) — архивы только из «Найти IMG».
    scene(['wall', 'roof'], {'custom.img': {'wall': {'house'},
                                            'roof': {'house', 'misc'}}})
    img_index = {'house.txd': ('custom.img', 'house.txd'),
                 'misc.txd': ('custom.img', 'misc.txd')}
    c = _Calls({('custom.img', 'house.txd'): b'h'})
    n = img_ops._rescue_textures_from_img(['custom.img'], img_index,
                                          str(tmp_path), c.extract_file,
                                          c.import_txd)
    # Один TXD покрывает обе текстуры (greedy set-cover).
    assert n == 1
    assert c.imported == [('house.txd', {'wall', 'roof'})]
