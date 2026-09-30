"""Вкладка Import и «Найти IMG»: двоичный IPL (стрим-IPL SA из IMG).

В двоичном IPL нет имён моделей — только ID; игра берёт имя из IDE. Его
lod_index указывает в ТЕКСТОВЫЙ IPL района (CIplStore::LoadIpl:
IplEntityIndexArrays[relatedIpl]), а не в сам файл. Поэтому при слиянии
выбранных IPL строки двоичного получают lod_index -1, имя — из IDE по ID и не
привязываются к строке (Add/Sync двоичный IPL не пишут). У текстового lod_index
сдвигается на смещение файла, а ссылка за пределы своего файла — -1.

ops/img_ops.py грузится изолированно с заглушкой bpy (как
test_import_from_img_sources); _work прогоняется целиком на строках, которые
не доходят до Blender (нет имени / нет DFF в IMG).
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
        bpy.data = types.SimpleNamespace(
            materials=[],
            collections=types.SimpleNamespace(get=lambda n: object()))
        sys.modules['bpy'] = bpy
        sys.modules['bpy.props'] = props
        pkg = types.ModuleType('INU_tools')
        pkg.__path__ = [str(ROOT / 'INU_tools')]
        pkg.T = lambda s: s
        sys.modules['INU_tools'] = pkg
        import importlib
        mods = {n: importlib.import_module('INU_tools.' + n)
                for n in ('ops.img_ops', 'core.ipl', 'core.img')}
        # _work импортирует их лениво; сами модули тянут весь Blender.
        dff = types.ModuleType('INU_tools.ops.dff_import')
        dff.import_dff = lambda *a, **k: None
        txd = types.ModuleType('INU_tools.ops.txd_import')
        txd.import_txd = lambda *a, **k: None
        mu = types.ModuleType('INU_tools.tools.model_utils')
        mu._strip_dup_suffix = lambda n: n
        sys.modules['INU_tools.ops.dff_import'] = dff
        sys.modules['INU_tools.ops.txd_import'] = txd
        sys.modules['INU_tools.tools.model_utils'] = mu
        ours = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)
    return mods, ours


_MODS, _OURS = _load_isolated()
img_ops = _MODS['ops.img_ops']
core_ipl = _MODS['core.ipl']
core_img = _MODS['core.img']


class _Quat:
    def __init__(self, *a):
        pass

    def conjugated(self):
        return self


_MATHUTILS = types.ModuleType('mathutils')
_MATHUTILS.Quaternion = _Quat
_MATHUTILS.Matrix = _MATHUTILS.Vector = object


@pytest.fixture(autouse=True)
def _our_modules():
    with mock.patch.dict(sys.modules, dict(_OURS, mathutils=_MATHUTILS)):
        yield


def _bin_ipl(path, rows):
    """Двоичный IPL: rows — (model_id, lod_index)."""
    ipl = core_ipl.IplFile()
    for mid, lod in rows:
        ipl.instances.append(core_ipl.IplInstance(
            model_id=mid, model_name='', lod_index=lod))
    core_ipl.write_binary_ipl(str(path), ipl)
    return str(path)


def _text_ipl(path, rows):
    """Текстовый IPL SA: rows — (model_id, имя, lod_index)."""
    path.write_text('inst\n' + ''.join(
        f'{mid}, {nm}, 0, 1.0, 2.0, 3.0, 0, 0, 0, 1, {lod}\n'
        for mid, nm, lod in rows) + 'end\n')
    return str(path)


def _ide(path, rows):
    """IDE: rows — (model_id, имя)."""
    path.write_text('objs\n' + ''.join(
        f'{mid}, {nm}, tex, 100, 0\n' for mid, nm in rows) + 'end\n')
    return str(path)


# ── _merge_ipl_instances / _name_binary_rows ──

def test_text_then_binary(tmp_path):
    t = _text_ipl(tmp_path / 'la.ipl',
                  [(1, 'a', 1), (2, 'lodA', -1), (3, 'c', -1)])
    b = _bin_ipl(tmp_path / 'la_stream0.ipl', [(100, 5), (101, 0)])
    inst, src, brows = img_ops._merge_ipl_instances([t, b])
    assert [i.lod_index for i in inst] == [1, -1, -1, -1, -1]
    assert brows == [3, 4]
    assert src == {0: (t, 0), 1: (t, 0), 2: (t, 0)}
    assert [i.model_name for i in inst[3:]] == ['', '']


def test_binary_first_keeps_text_base(tmp_path):
    b = _bin_ipl(tmp_path / 'la_stream0.ipl', [(100, 2), (101, 1)])
    t = _text_ipl(tmp_path / 'la.ipl',
                  [(1, 'a', 2), (2, 'b', -1), (3, 'lodA', -1)])
    inst, src, brows = img_ops._merge_ipl_instances([b, t])
    # Двоичный lod 2 раньше сдвигался в общий список и делал LOD чужой
    # текстовой строкой (idx 2 = 'a').
    assert [i.lod_index for i in inst] == [-1, -1, 4, -1, -1]
    assert brows == [0, 1]
    assert src == {2: (t, 2), 3: (t, 2), 4: (t, 2)}
    assert core_ipl.lod_instance_indices(inst) == {4}


def test_text_lod_outside_own_file_is_dropped(tmp_path):
    t1 = _text_ipl(tmp_path / 'a.ipl',
                   [(1, 'a', 3), (2, 'b', 99), (3, 'c', -1)])
    t2 = _text_ipl(tmp_path / 'b.ipl', [(4, 'd', 1), (5, 'lodD', -1)])
    inst, src, brows = img_ops._merge_ipl_instances([t1, t2])
    # lod 3 у файла из 3 строк раньше утекал в соседний файл (строка 'd').
    assert [i.lod_index for i in inst] == [-1, -1, -1, 4, -1]
    assert brows == []
    assert src[3] == (t2, 3) and src[4] == (t2, 3)


def test_unreadable_ipl_is_skipped(tmp_path):
    t = _text_ipl(tmp_path / 'a.ipl', [(1, 'a', -1)])
    inst, src, brows = img_ops._merge_ipl_instances(
        [str(tmp_path / 'missing.ipl'), t])
    assert len(inst) == 1 and src == {0: (t, 0)} and brows == []


def test_name_binary_rows(tmp_path):
    t = _text_ipl(tmp_path / 'la.ipl', [(100, 'keepme', -1)])
    b = _bin_ipl(tmp_path / 'la_stream0.ipl',
                 [(100, -1), (999, -1), (998, -1)])
    inst, _src, brows = img_ops._merge_ipl_instances([t, b])
    assert brows == [1, 2, 3]
    inst[2].model_name = 'already'
    brows.append(0)     # строки с именем не перезаписываются
    img_ops._name_binary_rows(
        inst, brows, {100: SimpleNamespace(model_name='lahouse'),
                      999: SimpleNamespace(model_name='other')})
    # 998 нет в IDE — остаётся без имени (импорт пропустит строку).
    assert [i.model_name for i in inst] == ['keepme', 'lahouse', 'already', '']


# ── _work: имена из IDE, пропуск «нет имени модели» ──

class _Scene(dict):
    pass


def _settings(**kw):
    base = dict(
        gtatools_img_path='', gtatools_ide_path='', gtatools_ipl_path='',
        gtatools_game_root='', gtatools_ipl_sync_list=[],
        gtatools_img_use_gta_dat=False, gtatools_img_skip_lod=False,
        gtatools_img_load_txd=False, gtatools_map_load_col=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _run_work(ipls, *, ide='', game_root='', found_ides=(), skip_lod=False):
    scene = _Scene()
    scene['gtatools_found_ides'] = '\n'.join(found_ides)
    scene.objects = []
    scene.inu_settings = _settings(
        gtatools_ide_path=ide, gtatools_game_root=str(game_root),
        gtatools_ipl_sync_list=[SimpleNamespace(path=p) for p in ipls],
        gtatools_img_skip_lod=skip_lod)
    op = SimpleNamespace(report=lambda *a: None, _final=None, _total=0,
                         _done=0)
    for _ in img_ops.GTATOOLS_OT_import_from_img._work(
            op, SimpleNamespace(scene=scene)):
        pass
    return op._final


def test_work_names_binary_rows_from_game_ides(tmp_path, capsys):
    root = tmp_path / 'game'
    (root / 'maps').mkdir(parents=True)
    _ide(root / 'maps' / 'la.ide', [(100, 'lahouse')])
    # Двоичный первым: его lod 2/3 раньше делали LOD текстовые cube1/cube2.
    b = _bin_ipl(tmp_path / 'la_stream0.ipl', [(100, 2), (999, 3)])
    t = _text_ipl(tmp_path / 'la.ipl', [(1, 'cube1', -1), (2, 'cube2', -1)])
    level, msg = _run_work([b, t], game_root=root, skip_lod=True)
    assert level == 'INFO'
    assert 'пропущено: 4' in msg
    assert '3 нет DFF в IMG' in msg
    assert '1 нет имени модели (нет в IDE)' in msg
    assert 'LOD' not in msg
    # Строка 100 искала lahouse.dff, а не «.dff».
    assert "'lahouse'" in capsys.readouterr().out


def test_work_names_binary_rows_from_found_ides(tmp_path, capsys):
    box = _ide(tmp_path / 'my.ide', [(5, 'boxmodel')])
    found = _ide(tmp_path / 'found.ide', [(100, 'fromfound')])
    b = _bin_ipl(tmp_path / 'la_stream0.ipl', [(100, -1)])
    level, msg = _run_work([b], ide=box, found_ides=[found])
    assert '1 нет DFF в IMG' in msg and 'нет имени' not in msg
    assert "'fromfound'" in capsys.readouterr().out


# ── «Найти IMG» ──

def _make_img(path, names):
    core_img.create_img(str(path))
    with core_img.ImgWriter(str(path)) as w:
        for n in names:
            w.add(n, b'\0' * 16)
    return str(path)


def _scan_img(ipls, root, *, ide=''):
    scene = _Scene()
    scene.inu_settings = _settings(
        gtatools_ide_path=ide, gtatools_game_root=str(root),
        gtatools_ipl_sync_list=[SimpleNamespace(path=p) for p in ipls])
    reports = []
    op = SimpleNamespace(report=lambda lvl, m: reports.append(m))
    res = img_ops.GTATOOLS_OT_scan_img_for_ipl.execute(
        op, SimpleNamespace(scene=scene))
    return res, scene.get('gtatools_found_imgs', ''), reports


def _scan_game(tmp_path):
    root = tmp_path / 'game'
    (root / 'maps').mkdir(parents=True)
    (root / 'models').mkdir()
    _ide(root / 'maps' / 'la.ide', [(100, 'LAhouse')])
    gta3 = _make_img(root / 'models' / 'gta3.img', ['lahouse.dff'])
    mod = _make_img(root / 'models' / 'mod.img', ['cube1.dff', 'boxed.dff'])
    return root, gta3, mod


def test_find_img_names_binary_rows_from_game_ides(tmp_path):
    root, gta3, mod = _scan_game(tmp_path)
    b = _bin_ipl(tmp_path / 'la_stream0.ipl', [(100, -1), (999, -1)])
    t = _text_ipl(tmp_path / 'la.ipl', [(1, 'cube1', -1)])
    res, found, reports = _scan_img([b, t], root)
    assert res == {'FINISHED'}
    assert set(found.split('\n')) == {gta3, mod}
    assert reports == ['Найдено IMG: 2 · моделей покрыто 2/2']


def test_find_img_ide_box_wins_like_import(tmp_path):
    root, gta3, mod = _scan_game(tmp_path)
    box = _ide(tmp_path / 'my.ide', [(100, 'boxed')])
    b = _bin_ipl(tmp_path / 'la_stream0.ipl', [(100, -1)])
    res, found, reports = _scan_img([b], root, ide=box)
    assert found == mod
