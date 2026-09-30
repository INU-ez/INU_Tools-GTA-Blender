"""IPL sections (ops/ipl_sections.py) — re-import dedup and the export
links (enex exit marker, jump start → target / camera, zone info).

A second Import Map / Import sections of the same IPL used to create
every cull / enex / occl again, and Export sections then wrote each
record twice (SA pools: 400 enex, 72 mirror cull zones). Now every
imported record carries obj['ipl_row'] = its canonical line and
records already in the IPL_* collections are skipped; repeats inside
one file stay (the game loads them all).

bpy is stubbed; the module's ``bpy`` global is swapped per test for a
namespace with just the collections the code reads.
"""

from pathlib import Path
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

# bpy stub only for the import, then removed: neighbour test files
# install their own fuller stub when 'bpy' is not in sys.modules yet.
_own_bpy = 'bpy' not in sys.modules
if _own_bpy:
    _bpy = types.ModuleType('bpy')
    _bpy.types = types.SimpleNamespace()
    _bpy.context = types.SimpleNamespace(scene=None)
    sys.modules['bpy'] = _bpy
_pkg_root = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
_pkg_root.__path__ = [str(ROOT / "INU_tools")]
if not hasattr(_pkg_root, 'T'):
    _pkg_root.T = lambda s, *_a, **_kw: s

from INU_tools.ops import ipl_sections as ips        # noqa: E402
from INU_tools.core.ipl import read_ipl              # noqa: E402

if _own_bpy:
    del sys.modules['bpy']


IPL_A = """\
cull
1.7363, 29.5882, 198.602, 0, 8.15653, 198.602, 2.4303, 0, 203.101, 1, 0
end
enex
-2027.0, -40.8, 34.3, 0.0, 2.0, 2.0, 8.0, -2026.9, -44.2, 34.3, 180.0, 0, 4, "SFDOG", 0, 2, 0, 24
end
jump
0, 0, 0, 10, 10, 5, 50, 50, 0, 60, 60, 5, 30, 30, 20, 500
end
occl
100, 200, 10, 30, 40, 20, 0, 0, 0, 0
100, 200, 10, 30, 40, 20, 0, 0, 0, 0
end
"""

IPL_B = """\
cull
1640.38, -1899.78, 11.3458, -11.3957, 44.6585, 11.0143, 19.05, 4.81555, 22.1307, 8, 0
end
occl
500, 600, 10, 30, 40, 20, 0, 0, 0, 0
end
"""


@pytest.fixture
def ipls(tmp_path):
    a = tmp_path / "a.ipl"
    b = tmp_path / "b.ipl"
    a.write_text(IPL_A, encoding="utf-8")
    b.write_text(IPL_B, encoding="utf-8")
    return read_ipl(str(a)), read_ipl(str(a)), read_ipl(str(b))


_KINDS = (('cull', 'culls'), ('enex', 'enexs'), ('jump', 'jumps'),
          ('occl', 'occls'))


def _rows_of(ipl) -> set:
    """What import stamps: (kind, ipl_row) of every record."""
    return {(k, ips._ROW_FMT[k](e)) for k, attr in _KINDS
            for e in getattr(ipl, attr)}


# ── _filter_new ────────────────────────────────────────────────────

def test_empty_scene_keeps_everything_incl_in_file_repeat(ipls):
    a, _, _ = ipls
    kept, n = ips._filter_new('occl', a.occls, set())
    assert n == 0 and len(kept) == 2          # repeat inside a file stays
    for kind, attr in _KINDS:
        kept, n = ips._filter_new(kind, getattr(a, attr), set())
        assert kept == getattr(a, attr) and n == 0


def test_second_import_of_same_file_adds_nothing(ipls):
    a, a2, _ = ipls
    existing = _rows_of(a)
    snapshot = set(existing)
    for kind, attr in _KINDS:
        entries = getattr(a2, attr)
        kept, n = ips._filter_new(kind, entries, existing)
        assert kept == [] and n == len(entries)
    assert existing == snapshot                 # not mutated


def test_other_file_records_pass(ipls):
    a, _, b = ipls
    existing = _rows_of(a)
    for kind, attr in (('cull', 'culls'), ('occl', 'occls')):
        kept, n = ips._filter_new(kind, getattr(b, attr), existing)
        assert kept == getattr(b, attr) and n == 0


def test_same_kind_only(ipls):
    a, _, _ = ipls
    line = ips._ROW_FMT['occl'](a.occls[0])
    kept, n = ips._filter_new('occl', a.occls, {('cull', line)})
    assert n == 0 and len(kept) == 2


# ── import_ipl_sections orchestration ──────────────────────────────

@pytest.fixture
def fake_import(monkeypatch):
    """import_* stubs that return what they were given."""
    calls = {}

    def _mk(kind):
        def _imp(entries, *a, **kw):
            calls[kind] = (list(entries), kw)
            return list(entries)
        return _imp

    for fn, kind in (('import_cull_zones', 'cull'), ('import_garages', 'grge'),
                     ('import_enexs', 'enex'), ('import_pickups', 'pick'),
                     ('import_cars', 'cars'), ('import_auzos', 'auzo'),
                     ('import_jumps', 'jump'), ('import_occls', 'occl'),
                     ('import_zones', 'zone')):
        monkeypatch.setattr(ips, fn, _mk(kind))
    return calls


def test_import_sections_counts_skipped(ipls, fake_import):
    a, a2, b = ipls
    existing = _rows_of(a)
    res = ips.import_ipl_sections(a2, existing=existing, game='SA')
    assert res.pop('_skipped') == 1 + 1 + 1 + 2
    assert all(v == [] for v in res.values())
    res = ips.import_ipl_sections(b, existing=existing, game='SA')
    assert res.pop('_skipped') == 0
    assert len(res['cull']) == 1 and len(res['occl']) == 1
    assert fake_import['cull'][1] == {'game': 'SA'}


def test_import_sections_skip_off(ipls, fake_import):
    a, a2, _ = ipls
    res = ips.import_ipl_sections(a2, skip_existing=False,
                                  existing=_rows_of(a), game='VC')
    assert res.pop('_skipped') == 0
    assert len(res['occl']) == 2 and len(res['enex']) == 1
    assert fake_import['cull'][1] == {'game': 'VC'}


# ── _existing_rows ─────────────────────────────────────────────────

class _Obj(dict):
    """Blender object stand-in: custom props via dict + attributes."""

    def __init__(self, name, props, loc=(0, 0, 0), dim=(1, 1, 1), rz=0.0,
                 linked=True):
        super().__init__(props)
        self.name = name
        self.location = types.SimpleNamespace(x=loc[0], y=loc[1], z=loc[2])
        self.dimensions = types.SimpleNamespace(x=dim[0], y=dim[1], z=dim[2])
        self.rotation_euler = types.SimpleNamespace(x=0.0, y=0.0, z=rz)
        self.users_collection = [object()] if linked else []


def _bpy_with(collections: dict):
    cols = {k: types.SimpleNamespace(objects=v) for k, v in collections.items()}
    return types.SimpleNamespace(
        data=types.SimpleNamespace(collections=types.SimpleNamespace(
            get=cols.get)),
        context=types.SimpleNamespace(scene=None))


def test_existing_rows_scans_only_ipl_collections(monkeypatch):
    enter = _Obj('Enex_A_enter', {'ipl_type': 'enex', 'ipl_row': 'E'})
    ex = _Obj('Enex_A_exit', {'ipl_type': 'enex_exit'})
    start = _Obj('Jump_000_start', {'ipl_type': 'jump', 'ipl_row': 'J'})
    tgt = _Obj('Jump_000_target', {'ipl_type': 'jump_target'})
    cam = _Obj('Jump_000_camera', {'ipl_type': 'jump_camera'})
    old = _Obj('Cull_000', {'ipl_type': 'cull'})          # pre-fix scene
    alien = _Obj('Cull_x', {'ipl_type': 'cull', 'ipl_row': 'X'})
    monkeypatch.setattr(ips, 'bpy', _bpy_with({
        'IPL_Enex': [enter, ex], 'IPL_Jump': [start, tgt, cam],
        'IPL_Cull': [old], 'Other': [alien]}))
    assert ips._existing_rows() == {('enex', 'E'), ('jump', 'J')}


# ── export links ───────────────────────────────────────────────────

def test_enex_exit_marker_move_is_exported(monkeypatch):
    props = {'ipl_type': 'enex', 'enex_exit_x': 1.0, 'enex_exit_y': 2.0,
             'enex_exit_z': 3.0, 'enex_exit_angle': 90.0, 'enex_name': 'A'}
    import math
    ex = _Obj('A_exit', {'ipl_type': 'enex_exit'}, loc=(1.0, 2.0, 3.0),
              rz=math.radians(90.0))
    enter = _Obj('A_enter', dict(props, enex_exit_obj=ex))
    monkeypatch.setattr(ips, 'bpy', _bpy_with({'IPL_Enex': [enter, ex]}))
    e = ips.export_enexs()[0]
    assert (e.x2, e.y2, e.z2, e.exit_angle) == (1.0, 2.0, 3.0, 90.0)
    ex.location.x, ex.rotation_euler.z = 11.5, math.radians(45.0)
    e = ips.export_enexs()[0]
    assert e.x2 == 11.5 and e.exit_angle == pytest.approx(45.0)
    ex.users_collection = []                     # marker deleted
    e = ips.export_enexs()[0]
    assert (e.x2, e.exit_angle) == (1.0, 90.0)


def _jump(tag, idx, x, linked=True):
    s = _Obj(f'J{tag}_start', {'ipl_type': 'jump', 'jump_index': idx},
             loc=(x, 0, 0))
    t = _Obj(f'J{tag}_target', {'ipl_type': 'jump_target', 'jump_index': idx},
             loc=(x + 100, 0, 0))
    c = _Obj(f'J{tag}_camera', {'ipl_type': 'jump_camera', 'jump_index': idx},
             loc=(x + 50, 0, 20))
    if linked:
        s['jump_target_obj'], s['jump_camera_obj'] = t, c
    return [s, t, c]


def test_jumps_from_two_imports_keep_their_pairs(monkeypatch):
    # both imports numbered their jumps from 0
    objs = _jump('a', 0, 0.0) + _jump('b', 0, 1000.0)
    monkeypatch.setattr(ips, 'bpy', _bpy_with({'IPL_Jump': objs}))
    js = ips.export_jumps()
    assert len(js) == 2
    for j in js:
        start_x = (j.start_lower_x + j.start_upper_x) / 2
        assert (j.target_lower_x + j.target_upper_x) / 2 == start_x + 100
        assert j.camera_x == start_x + 50


def test_jumps_old_scene_pairs_by_index(monkeypatch):
    objs = _jump('a', 0, 0.0, linked=False) + _jump('b', 1, 1000.0,
                                                    linked=False)
    monkeypatch.setattr(ips, 'bpy', _bpy_with({'IPL_Jump': objs}))
    js = ips.export_jumps()
    assert [j.camera_x for j in js] == [50.0, 1050.0]


def test_zone_info_round_trips(monkeypatch):
    z = _Obj('Zone_GAN1', {'ipl_type': 'zone', 'zone_name': 'GAN1',
                           'zone_info': 'GAN'}, loc=(5, 5, 5), dim=(10, 10, 10))
    monkeypatch.setattr(ips, 'bpy', _bpy_with({'IPL_Zone': [z]}))
    assert ips.export_zones()[0].info == 'GAN'
