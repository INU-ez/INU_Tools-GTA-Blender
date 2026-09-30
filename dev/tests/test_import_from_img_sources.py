"""Импорт из IMG: откуда берутся строки для расстановки.

Сетка «только по IDE» строится только из ЯВНО выбранных IDE (бокс IDE +
«Найти IDE»). Папка игры без IPL/IDE — ошибка, а не сетка всех моделей игры;
IPL без строк inst (occlu.ipl: только occl) — ошибка «В IPL нет моделей».

ops/img_ops.py грузится изолированно с заглушкой bpy (как test_img_col_index);
_work идёт до первой точки, где нужен Blender: сетка подменяется на sentinel.
"""

import sys
import types
from pathlib import Path
from types import SimpleNamespace
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
        img_ops = importlib.import_module('INU_tools.ops.img_ops')
        # _work импортирует их в начале; сами модули тянут весь Blender.
        dff = types.ModuleType('INU_tools.ops.dff_import')
        dff.import_dff = lambda *a, **k: None
        txd = types.ModuleType('INU_tools.ops.txd_import')
        txd.import_txd = lambda *a, **k: None
        sys.modules['INU_tools.ops.dff_import'] = dff
        sys.modules['INU_tools.ops.txd_import'] = txd
        ours = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)
    return img_ops, ours


img_ops, _OURS = _load_isolated()

_MATHUTILS = types.ModuleType('mathutils')
for _n in ('Matrix', 'Quaternion', 'Vector'):
    setattr(_MATHUTILS, _n, object)


@pytest.fixture(autouse=True)
def _our_modules():
    with mock.patch.dict(sys.modules, dict(_OURS, mathutils=_MATHUTILS)):
        yield


class _Grid(Exception):
    """Сетка вызвана — дальше нужен Blender, прогон останавливаем."""


class _Scene(dict):
    pass


def _run(tmp_path, *, ide='', ipl='', game_root='', found_ides=(),
         grid=True):
    scene = _Scene()
    scene['gtatools_found_ides'] = '\n'.join(str(p) for p in found_ides)
    scene.inu_settings = SimpleNamespace(
        gtatools_img_path='', gtatools_ide_path=str(ide),
        gtatools_ipl_path=str(ipl), gtatools_game_root=str(game_root),
        gtatools_ipl_sync_list=[], gtatools_img_use_gta_dat=False,
        gtatools_img_skip_lod=False, gtatools_img_load_txd=True,
        gtatools_map_load_col=True)
    op = SimpleNamespace(report=lambda *a: None, _final=None, _total=0,
                         _done=0)
    calls = []

    def _sentinel(ide_models, step=30.0):
        calls.append(sorted(ide_models))
        raise _Grid()

    patch = (mock.patch.object(img_ops, '_instances_from_ide', _sentinel)
             if grid else mock.patch.object(img_ops, '_instances_from_ide',
                                            img_ops._instances_from_ide))
    with patch:
        gen = img_ops.GTATOOLS_OT_import_from_img._work(
            op, SimpleNamespace(scene=scene))
        try:
            next(gen)
        except (StopIteration, _Grid):
            pass
    return op._final, calls


def _ide(path, ids):
    path.write_text('objs\n' + ''.join(
        f'{i}, m{i}, t{i}, 100, 0\n' for i in ids) + 'end\n')
    return path


def _game_root(tmp_path):
    root = tmp_path / 'game'
    (root / 'maps').mkdir(parents=True)
    _ide(root / 'maps' / 'a.ide', [10, 11])
    _ide(root / 'maps' / 'b.ide', [20])
    return root


def test_game_root_only_is_error_not_grid(tmp_path):
    final, calls = _run(tmp_path, game_root=_game_root(tmp_path))
    assert final == ('ERROR', 'Укажите IPL или IDE файл')
    assert calls == []


def test_ipl_without_inst_rows_is_error(tmp_path):
    ipl = tmp_path / 'occlu.ipl'
    ipl.write_text('occl\n100, 200, 10, 20, 30, 5, 0\nend\n')
    final, calls = _run(tmp_path, ipl=ipl, game_root=_game_root(tmp_path))
    assert final == ('ERROR', 'В IPL нет моделей')
    assert calls == []


def test_ide_box_builds_grid(tmp_path):
    ide = _ide(tmp_path / 'my.ide', [1, 2, 3])
    final, calls = _run(tmp_path, ide=ide, game_root=_game_root(tmp_path))
    assert calls == [[1, 2, 3]]


def test_found_ides_build_grid(tmp_path):
    found = _ide(tmp_path / 'found.ide', [7, 8])
    final, calls = _run(tmp_path, found_ides=[found])
    assert calls == [[7, 8]]


def test_ide_without_objs_is_error(tmp_path):
    ide = tmp_path / 'empty.ide'
    ide.write_text('objs\nend\n')
    final, calls = _run(tmp_path, ide=ide, grid=False)
    assert final == ('ERROR', 'В IDE нет моделей')


# ── «по gta.dat»: lod_index стрим-IPL из IMG — в его текстовый IPL ──────

def test_gta_dat_mode_rebases_stream_lod_index(tmp_path):
    import importlib
    ipl_mod = importlib.import_module('INU_tools.core.ipl')
    img_mod = importlib.import_module('INU_tools.core.img')
    root = tmp_path / 'game'
    (root / 'data' / 'maps').mkdir(parents=True)
    (root / 'models').mkdir()
    (root / 'data' / 'gta.dat').write_text(
        'IPL DATA/MAPS/one.ipl\nIPL DATA/MAPS/two.ipl\n')
    row = '{0}, m{0}, 0, 1, 2, 3, 0, 0, 0, 1, {1}\n'
    (root / 'data' / 'maps' / 'one.ipl').write_text(
        'inst\n' + row.format(1, -1) + row.format(2, -1) + 'end\n')
    (root / 'data' / 'maps' / 'two.ipl').write_text(
        'inst\n' + row.format(3, -1) + row.format(4, -1) + row.format(5, 0)
        + 'end\n')

    def _bin(*lods):
        return ipl_mod._write_binary_ipl(ipl_mod.IplFile(instances=[
            ipl_mod.IplInstance(model_id=90 + k, model_name='', lod_index=li)
            for k, li in enumerate(lods)]))

    img = str(root / 'models' / 'gta3.img')
    img_mod.create_img(img)
    with img_mod.ImgWriter(img) as w:
        w.add('two_stream0.ipl', _bin(1, -1, 7))    # 7 — вне two.ipl
        w.add('gone_stream0.ipl', _bin(0))          # текстового IPL нет
    scene = _Scene()
    scene.inu_settings = SimpleNamespace(
        gtatools_img_path=img, gtatools_ide_path='', gtatools_ipl_path='',
        gtatools_game_root=str(root), gtatools_ipl_sync_list=[],
        gtatools_img_use_gta_dat=True, gtatools_img_skip_lod=False,
        gtatools_img_load_txd=False, gtatools_map_load_col=False)
    op = SimpleNamespace(report=lambda *a: None, _final=None, _total=0,
                         _done=0)
    got = []

    def _stop(instances, binary_rows, ide_models):
        got.extend(instances)
        raise _Grid()

    with mock.patch.object(img_ops, '_name_binary_rows', _stop):
        gen = img_ops.GTATOOLS_OT_import_from_img._work(
            op, SimpleNamespace(scene=scene))
        with pytest.raises(_Grid):
            next(gen)
    # one.ipl: 0..1, two.ipl: 2..4 (его строка 0 → 2), стримы — после
    assert [i.lod_index for i in got] == [-1, -1, -1, -1, 2, 3, -1, -1, -1]
