"""«Sync from IDE» (ops/map_link.ide_sync_from_file) — на подставном bpy.

* своя связанная IDE выигрывает у более ранней в списке;
* имя в двух IDE с разными ID и без совпадения с Model ID — не связано,
  предупреждение; совпал Model ID — связано с этой строкой;
* копия со сменённым ID не откатывается к строке оригинала;
* смена Model ID из файла — строка INFO; LOD — только со строкой LOD;
* путь связи нормализован (map_link.norm);
* своя IDE недоступна — строка с другим ID модель не забирает (связь
  остаётся, одно предупреждение на файл); тот же ID в другом файле —
  перепривязка.
"""

from pathlib import Path
from types import SimpleNamespace
import importlib
import re
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _is_ours(name):
    return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))


def _install_stubs():
    bpy = types.ModuleType('bpy')
    bpy.app = SimpleNamespace(version=(4, 2, 0), translations=None)
    bpy.path = SimpleNamespace(abspath=lambda p: p)
    bpy.data = SimpleNamespace(objects=[], filepath='x.blend')
    bpy.context = SimpleNamespace(scene=None)
    sys.modules['bpy'] = bpy
    pkg = types.ModuleType('INU_tools')
    pkg.__path__ = [str(ROOT / 'INU_tools')]
    pkg.T = lambda s, *a, **k: s
    sys.modules['INU_tools'] = pkg


def _load_isolated():
    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for k in saved:
        del sys.modules[k]
    try:
        _install_stubs()
        for name in ('INU_tools.ops.map_link', 'INU_tools.core.ide',
                     'INU_tools.core.mapsync.ide_match',
                     'INU_tools.core.model_classify'):
            importlib.import_module(name)
        mods = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for k in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    return mods


_MODS = _load_isolated()
ml = _MODS['INU_tools.ops.map_link']
_classify = _MODS['INU_tools.core.model_classify'].classify_model


def _mtype(o):
    return _classify(re.sub(r'\.\d+$', '', o.name), has_texture=True,
                     inu_type=o.inu.type)


@pytest.fixture(autouse=True)
def _our_modules(monkeypatch):
    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for k in saved:
        del sys.modules[k]
    sys.modules.update(_MODS)
    pkg = _MODS['INU_tools']
    monkeypatch.setattr(pkg, '_clean_model_name_ide',
                        lambda n: _mtype(SimpleNamespace(
                            name=n, inu=SimpleNamespace(type='OBJ')))[1],
                        raising=False)
    monkeypatch.setattr(ml, 'model_type', _mtype)
    try:
        yield
    finally:
        for k in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)


A_TEXT = ("objs\r\n"
          "100, house, house_a, 100, 0\r\n"
          "101, LODhouse, house_a, 300, 0\r\n"
          "60, tree, trees, 80, 4\r\n"
          "end\r\n")
B_TEXT = "objs\r\n200, house, house_b, 150, 0\r\nend\r\n"


def _obj(name, *, mid=0, ide='', last_id=0, last_name='', typ='OBJ'):
    inu = SimpleNamespace(
        type=typ, model_id=mid, draw_distance=0.0, lod_draw_distance=0.0,
        txd_name='', ide_flags=0,
        ide_linked=bool(ide), ide_target_file=ide,
        ide_last_model_id=last_id, ide_last_name=last_name,
        ide_last_draw_distance=0.0, ide_last_txd_name='', ide_last_flags=0)
    return SimpleNamespace(name=name, type='MESH', inu=inu)


@pytest.fixture
def ides(tmp_path):
    a = tmp_path / 'a.ide'
    b = tmp_path / 'b.ide'
    a.write_bytes(A_TEXT.encode())
    b.write_bytes(B_TEXT.encode())
    return str(a), str(b)


def test_ambiguous_name_not_linked(ides):
    o = _obj('house')
    linked, skipped, rep = ml.ide_sync_from_file([o], list(ides))
    assert (linked, skipped) == (0, 1)
    assert o.inu.model_id == 0 and not o.inu.ide_linked
    assert [lv for lv, _t in rep.messages] == ['WARNING']
    assert '«house»' in rep.messages[0][1]


def test_mid_picks_matching_row(ides):
    a, b = ides
    o = _obj('house', mid=200)
    linked, skipped, rep = ml.ide_sync_from_file([o], [a, b])
    assert (linked, skipped) == (1, 0) and rep.messages == []
    assert o.inu.ide_target_file == ml.norm(b)
    assert o.inu.draw_distance == 150.0 and o.inu.txd_name == 'house_b'


def test_own_linked_ide_wins(ides):
    a, b = ides
    o = _obj('house', mid=200, ide=ml.norm(b), last_id=200,
             last_name='house')
    linked, _s, rep = ml.ide_sync_from_file([o], [a, b])
    assert linked == 1 and rep.messages == []
    assert o.inu.ide_target_file == ml.norm(b) and o.inu.model_id == 200


def test_stale_copy_not_snapped_back(ides):
    a, _b = ides
    o = _obj('house2', mid=300, ide=ml.norm(a), last_id=100,
             last_name='house')
    linked, skipped, rep = ml.ide_sync_from_file([o], [a])
    assert (linked, skipped) == (0, 1) and rep.messages == []
    assert o.inu.model_id == 300


def test_changed_id_reported(ides):
    a, _b = ides
    o = _obj('tree', mid=50)
    linked, _s, rep = ml.ide_sync_from_file([o], [a])
    assert linked == 1 and o.inu.model_id == 60
    assert rep.messages[0][0] == 'INFO' and '50 → 60' in rep.messages[0][1]
    assert o.inu.ide_flags == 4 and o.inu.ide_last_model_id == 60
    assert o.inu.ide_last_name == 'tree'


def test_lod_object_takes_lod_row(ides):
    a, _b = ides
    o = _obj('LODhouse')
    linked, _s, _rep = ml.ide_sync_from_file([o], [a])
    assert linked == 1 and o.inu.model_id == 101
    assert o.inu.lod_draw_distance == 300.0 and o.inu.draw_distance == 0.0


def test_path_normalized(ides, tmp_path):
    a, _b = ides
    raw = str(tmp_path) + '/./a.ide'
    o = _obj('tree', mid=60)
    ml.ide_sync_from_file([o], [raw])
    assert o.inu.ide_target_file == ml.norm(a)


def test_own_ide_missing_keeps_link(ides, tmp_path):
    """Своя «tree» 19000, mod.ide пропал: ванильная tree 60 её не забирает."""
    a, _b = ides
    gone = ml.norm(str(tmp_path / 'mod' / 'mod.ide'))
    objs = [_obj(n, mid=19000, ide=gone, last_id=19000, last_name='tree')
            for n in ('tree', 'tree.001')]
    linked, skipped, rep = ml.ide_sync_from_file(objs, [a])
    assert (linked, skipped) == (0, 2)
    assert all(o.inu.model_id == 19000 and o.inu.ide_target_file == gone
               for o in objs)
    assert [lv for lv, _t in rep.messages] == ['WARNING']
    assert rep.messages[0][1].startswith('mod.ide:') and ' 2 ' in rep.messages[0][1]


def test_own_ide_missing_same_id_elsewhere_relinks(ides, tmp_path):
    a, _b = ides
    gone = ml.norm(str(tmp_path / 'old' / 'a.ide'))
    o = _obj('tree', mid=60, ide=gone, last_id=60, last_name='tree')
    linked, _s, rep = ml.ide_sync_from_file([o], [a])
    assert linked == 1 and rep.messages == []
    assert o.inu.ide_target_file == ml.norm(a) and o.inu.model_id == 60


def test_one_id_under_different_names_message(tmp_path):
    x, y = tmp_path / 'x.ide', tmp_path / 'y.ide'
    x.write_bytes(b"objs\r\n700, shed, shed, 100, 0\r\nend\r\n")
    y.write_bytes(b"objs\r\n700, kiosk, kiosk, 100, 0\r\nend\r\n")
    o = _obj('renamed', mid=700)
    linked, skipped, rep = ml.ide_sync_from_file([o], [str(x), str(y)])
    assert (linked, skipped) == (0, 1) and o.inu.model_id == 700
    assert [lv for lv, _t in rep.messages] == ['WARNING']
    assert '«renamed»' in rep.messages[0][1] and 'ID 700' in rep.messages[0][1]
