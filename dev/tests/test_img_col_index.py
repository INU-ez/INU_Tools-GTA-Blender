"""Импорт из IMG: индекс коллизии по заголовкам моделей COL.

Ванильная коллизия лежит в библиотеках (одна запись .col на много моделей),
игра привязывает модель COL по имени из её заголовка. `_col_names_in_img`
читает эти заголовки без разбора геометрии, `_col_index_for` сводит их по
архивам (первый по порядку побеждает — как img_index).

ops/img_ops.py грузится изолированно с заглушкой bpy; размещение сфер и
боксов на повёрнутом инстансе проверяется руками в Blender.
"""

import os
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _is_ours(name):
    return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))


def _load_isolated():
    """Заглушка bpy + пакет INU_tools с T; после загрузки sys.modules
    возвращается как был, свои модули — в _OURS (на время теста)."""
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
        mods = {n: importlib.import_module('INU_tools.' + n)
                for n in ('ops.img_ops', 'core.img', 'core.col')}
        ours = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)
    return mods, ours


_MODS, _OURS = _load_isolated()
img_ops = _MODS['ops.img_ops']
core_img = _MODS['core.img']
core_col = _MODS['core.col']


@pytest.fixture(autouse=True)
def _our_modules():
    # Функции img_ops импортируют ..core.* лениво — на время теста наши модули.
    with mock.patch.dict(sys.modules, _OURS):
        yield
    img_ops._col_names_cache.clear()


def _col_model(name, x):
    """Модель COL с одной сферой (write_col пишет непустую запись)."""
    V = core_col.Vec3
    m = core_col.ColModel(version=3, model_name=name)
    m.spheres.append(core_col.ColSphere(center=V(x, 0.0, 0.0), radius=1.5))
    m.bounds = core_col.Bounds(center=V(x, 0.0, 0.0), radius=1.5,
                               bb_min=V(x - 1.5, -1.5, -1.5),
                               bb_max=V(x + 1.5, 1.5, 1.5))
    return m


def _make_img(path, entries):
    core_img.create_img(path)
    with core_img.ImgWriter(path) as w:
        for name, data in entries.items():
            w.add(name, data)
    return path


def test_library_entry_lists_every_model(tmp_path):
    aaa = core_col.write_col([_col_model('aaa', 1.0)])
    bbb = core_col.write_col([_col_model('bbb', 2.0)])
    lib = aaa + bbb
    arch = _make_img(str(tmp_path / 'gta3.img'), {
        'lib.col': lib,
        'ccc.col': core_col.write_col([_col_model('ccc', 3.0)]),
        'house.dff': b'\0' * 64,
    })
    names = img_ops._col_names_in_img(arch)
    assert names['lib.col'] == [['aaa', 0, len(aaa)],
                                ['bbb', len(aaa), len(bbb)]]
    # Своя карта: <модель>.col с именем в заголовке находится как раньше.
    assert [m[0] for m in names['ccc.col']] == ['ccc']
    assert 'house.dff' not in names

    # Срез по смещению/длине — ровно модель bbb.
    idx = img_ops._col_index_for([arch])
    a, entry, off, ln = idx['bbb']
    assert (a, entry) == (arch, 'lib.col')
    data = core_img.extract_file(a, entry)
    got = core_col.read_col(data[off:off + ln])
    assert [m.model_name for m in got] == ['bbb']
    assert got[0].spheres[0].center.x == pytest.approx(2.0)
    assert idx['ccc'][1] == 'ccc.col'


def test_first_archive_wins_like_img_index(tmp_path):
    first = _make_img(str(tmp_path / 'a.img'),
                      {'lib_a.col': core_col.write_col([_col_model('dup', 1.0)])})
    second = _make_img(str(tmp_path / 'b.img'),
                       {'lib_b.col': core_col.write_col([_col_model('dup', 9.0),
                                                         _col_model('only_b', 5.0)])})
    idx = img_ops._col_index_for([first, second])
    assert idx['dup'][:2] == (first, 'lib_a.col')
    assert idx['only_b'][:2] == (second, 'lib_b.col')
    idx = img_ops._col_index_for([second, first])
    assert idx['dup'][:2] == (second, 'lib_b.col')


def test_cache_follows_file_change(tmp_path):
    arch = _make_img(str(tmp_path / 'x.img'),
                     {'x.col': core_col.write_col([_col_model('one', 1.0)])})
    assert [m[0] for m in img_ops._col_names_in_img(arch)['x.col']] == ['one']
    core_img.replace_or_add(arch, 'y.col',
                            core_col.write_col([_col_model('two', 1.0)]))
    os.utime(arch, (1, 1))       # другой mtime/размер → новый ключ кэша
    assert 'y.col' in img_ops._col_names_in_img(arch)


def test_broken_archive_is_skipped(tmp_path):
    bad = tmp_path / 'bad.img'
    bad.write_bytes(b'NOPE' + b'\0' * 60)
    good = _make_img(str(tmp_path / 'good.img'),
                     {'g.col': core_col.write_col([_col_model('g', 0.0)])})
    idx = img_ops._col_index_for([str(bad), good])
    assert list(idx) == ['g']
