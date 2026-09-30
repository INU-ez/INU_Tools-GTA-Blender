"""IDE / IPL status of the active object («Выделенная модель»), without Blender.

The status compares an object's stamps with what «Add» would write NOW, not
with its raw props:

* IDE: an empty TXD goes into the file as the model name, flags are
  translated to the scene's game, a LOD with Model ID 0 is written as the
  model's id + 1 — each used to show a false «изменено» / «сменился ID»;
* IPL: rotation counts too (a rotated model showed «В IPL»), with q and −q
  one rotation and float32 / 4-digit quaternions not a change.

core/mapsync pos_close / rot_close / inst_drifted are pure; ide_status /
ipl_status run on a stubbed bpy with the REAL entry builders cut out of
INU_tools/__init__.py (as in test_map_link_lod_ide.py).
"""

from pathlib import Path
import ast
import importlib
import io
import math
import re
import struct
import sys
import types
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[2]
WANTED = {'_ide_entry_from_obj', '_ipl_entry_from_obj', '_clean_model_name_ide'}
CALLS = {'uncached': []}


def _plain(name):
    return re.sub(r'\.\d+$', '', name)


def _model_type(obj):
    CALLS['uncached'].append(obj)
    return _model_type_cached(obj)


def _model_type_cached(obj):
    n = _plain(obj.name)
    if n.lower().startswith('lod'):
        return 'LOD', n[3:]
    return 'DFF', n


def _load():
    """map_link on a private bpy stub (see test_map_link_lod_ide._load)."""
    def ours(name):
        return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))

    saved = {k: v for k, v in sys.modules.items() if ours(k)}
    for k in saved:
        del sys.modules[k]
    try:
        bpy = types.ModuleType('bpy')
        bpy.path = NS(abspath=lambda p: p)
        bpy.data = NS(objects=[])
        bpy.context = NS(scene=None)
        sys.modules['bpy'] = bpy
        pkg = types.ModuleType('INU_tools')
        pkg.__path__ = [str(ROOT / 'INU_tools')]
        pkg.T = lambda s, *_a, **_kw: s
        sys.modules['INU_tools'] = pkg
        tools = types.ModuleType('INU_tools.tools')
        tools.__path__ = [str(ROOT / 'INU_tools' / 'tools')]
        mu = types.ModuleType('INU_tools.tools.model_utils')
        mu.get_model_type = _model_type
        mu.get_model_type_cached = _model_type_cached
        mu._strip_dup_suffix = _plain
        sys.modules['INU_tools.tools'] = tools
        sys.modules['INU_tools.tools.model_utils'] = mu
        mod = importlib.import_module('INU_tools.ops.map_link')
        for name in ('INU_tools.core.ipl', 'INU_tools.core.ide',
                     'INU_tools.core.mapsync', 'INU_tools.core.game_versions',
                     'INU_tools.core.ide_flag_translate'):
            importlib.import_module(name)
        src = ROOT / 'INU_tools' / '__init__.py'
        tree = ast.parse(io.open(src, encoding='utf-8').read())
        keep = [n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name in WANTED]
        assert {n.name for n in keep} == WANTED
        ns = {'__name__': 'INU_tools', '__package__': 'INU_tools',
              'bpy': bpy, 'get_model_type': _model_type}
        exec(compile(ast.Module(body=keep, type_ignores=[]), str(src), 'exec'), ns)
        for name in WANTED:
            setattr(pkg, name, ns[name])
        mods = {k: v for k, v in sys.modules.items() if ours(k)}
    finally:
        for k in [k for k in sys.modules if ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    return bpy, mod, mods


BPY, ml, MODS = _load()
MS = MODS['INU_tools.core.mapsync']
Anchor, IplDoc = MS.Anchor, MS.IplDoc
IplInstance = MODS['INU_tools.core.ipl'].IplInstance
translate_flags = MODS['INU_tools.core.ide_flag_translate'].translate_flags


def f32(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


def zrot(deg):
    """IPL-row quaternion (x, y, z, w) of a turn about Z."""
    h = math.radians(deg) / 2
    return (0.0, 0.0, math.sin(h), math.cos(h))


# ── core: pos_close / rot_close / inst_drifted ─────────────────────

def test_pos_close():
    assert MS.pos_close((1.0, 2.0, 3.0), (1.0, 2.0, 3.0))
    assert MS.pos_close((2233.8032, 0, 0), (f32(2233.8032), 0, 0))
    assert MS.pos_close((1.0, 2.0, 3.0), (1.0 + 5e-5, 2.0, 3.0))
    assert not MS.pos_close((1.0, 2.0, 3.0), (1.0, 2.0, 3.0 + 1e-3))


def test_rot_close_sign_and_normalization():
    q = zrot(90)
    assert MS.rot_close(q, q)
    assert MS.rot_close(tuple(-c for c in q), q)            # −q: same turn
    assert MS.rot_close((0.0, 0.0, 0.7071, 0.7071), q)      # 4-digit file
    assert MS.rot_close(q, (0.0, 0.0, -0.7071, -0.7071))
    assert MS.rot_close(tuple(f32(c) for c in q), q)        # float32 props


def test_rot_close_real_turn_and_zero():
    assert not MS.rot_close(zrot(91), zrot(90))            # 1°
    assert not MS.rot_close(zrot(0.01), zrot(0))
    assert not MS.rot_close((0.0, 0.0, 0.0, 0.0), zrot(0))
    assert not MS.rot_close(zrot(0), (0.0, 0.0, 0.0, 0.0))


def test_inst_drifted():
    x, y, z, w = zrot(30)
    inst = IplInstance(model_id=1, model_name='a', pos_x=10.0, pos_y=0.0,
                       pos_z=0.0, rot_x=x, rot_y=y, rot_z=z, rot_w=w)
    assert not MS.inst_drifted(inst, Anchor(1, 'a', (10.0, 0.0, 0.0), zrot(30)))
    assert MS.inst_drifted(inst, Anchor(1, 'a', (10.0, 0.0, 0.0), zrot(0)))
    assert MS.inst_drifted(inst, Anchor(1, 'a', (10.01, 0.0, 0.0), zrot(30)))
    # no rotation stamped → position only
    assert not MS.inst_drifted(inst, Anchor(1, 'a', (10.0, 0.0, 0.0), None))


# ── fake scene ─────────────────────────────────────────────────────

class _Objects(list):
    def __contains__(self, key):
        if isinstance(key, str):
            return any(o.name == key for o in self)
        return list.__contains__(self, key)


class _Quat:
    def __init__(self, w, x, y, z):
        self.w, self.x, self.y, self.z = w, x, y, z

    def conjugated(self):
        return _Quat(self.w, -self.x, -self.y, -self.z)


class _Matrix:
    """matrix_world: Blender's rotation is the conjugate of the IPL row's."""

    def __init__(self, pos, row_rot=(0.0, 0.0, 0.0, 1.0)):
        self.set(pos, row_rot)

    def set(self, pos, row_rot=(0.0, 0.0, 0.0, 1.0)):
        self.translation = NS(x=pos[0], y=pos[1], z=pos[2])
        x, y, z, w = row_rot
        self._q = (w, -x, -y, -z)

    def to_quaternion(self):
        return _Quat(*self._q)

    def to_scale(self):
        return (1.0, 1.0, 1.0)


def _obj(name, *, sid, pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0, 1.0), **kw):
    inu = dict(model_id=0, txd_name='', draw_distance=299.0,
               lod_draw_distance=300.0, ide_flags=0, ide_flags_source_game='',
               type='OBJ', lod_object=None, ide_linked=False,
               ide_target_file='', ide_last_model_id=0, ide_last_name='',
               ide_last_draw_distance=0.0, ide_last_txd_name='',
               ide_last_flags=0, interior_id=0, real_interior=0, lod_index=-1,
               ipl_uuid='', ipl_target_file='', ipl_last_model_id=0,
               ipl_last_name='', ipl_last_pos=(0.0, 0.0, 0.0),
               ipl_last_rot=(0.0, 0.0, 0.0, 1.0), ipl_owner='')
    inu.update(kw)
    return NS(type='MESH', name=name, session_uid=sid, inu=NS(**inu),
              matrix_world=_Matrix(pos, rot))


@pytest.fixture
def scene(monkeypatch):
    for k, v in MODS.items():
        monkeypatch.setitem(sys.modules, k, v)
    objs = _Objects()
    ctx = NS(scene=NS(objects=objs, inu_settings=NS(
        gtatools_game='SA', gtatools_ide_path='', gtatools_ide_sync_list=[])))
    monkeypatch.setattr(BPY, 'data', NS(objects=objs))
    monkeypatch.setattr(BPY, 'context', ctx)
    ml.reset_copies()
    CALLS['uncached'].clear()
    return ctx, objs


def _ide(obj):
    text, arg, _icon, changed = ml.ide_status(obj)
    return text.format(arg), changed


def _ipl(obj):
    text, arg, _icon = ml.ipl_status(obj)
    return text.format(arg)


# ── IDE status ─────────────────────────────────────────────────────

def test_ide_not_linked(scene):
    _ctx, objs = scene
    o = _obj('house', sid=1, model_id=100)
    objs.append(o)
    assert _ide(o) == ("Не в IDE", False)


def test_ide_empty_txd_is_not_a_change(scene, tmp_path):
    ctx, objs = scene
    o = _obj('house', sid=1, model_id=100)       # txd_name empty
    objs.append(o)
    rep = ml.ide_write(ctx, [o], picked=str(tmp_path / 'a.ide'))
    assert not rep.problems()
    assert o.inu.ide_last_txd_name == 'house'   # written as the model name
    assert _ide(o) == ("В IDE (a.ide)", False)


def test_ide_translated_flags_are_not_a_change(scene, tmp_path):
    ctx, objs = scene
    o = _obj('house', sid=1, model_id=100, txd_name='house', ide_flags=0x14,
             ide_flags_source_game='III')         # scene is SA
    objs.append(o)
    assert translate_flags(0x14, 'III', 'SA') != 0x14
    ml.ide_write(ctx, [o], picked=str(tmp_path / 'a.ide'))
    assert _ide(o) == ("В IDE (a.ide)", False)
    o.inu.ide_flags = 0x40                        # a real edit
    assert _ide(o) == ("В IDE, изменено: Flags", False)


def test_ide_real_changes_listed(scene, tmp_path):
    ctx, objs = scene
    o = _obj('house', sid=1, model_id=100, txd_name='house')
    objs.append(o)
    ml.ide_write(ctx, [o], picked=str(tmp_path / 'a.ide'))
    o.inu.draw_distance = 150.0
    o.inu.txd_name = 'other'
    assert _ide(o) == ("В IDE, изменено: DrawDist, TXD", False)
    o.inu.model_id = 200
    assert _ide(o) == ("Не в IDE — сменился ID (был 100)", True)


def test_ide_lod_without_id(scene, tmp_path):
    ctx, objs = scene
    lod = _obj('LODhouse', sid=2, model_id=0, lod_draw_distance=500.0)
    model = _obj('house', sid=1, model_id=5000, txd_name='house',
                 lod_object=lod)
    objs += [model, lod]
    ml.ide_write(ctx, [model, lod], picked=str(tmp_path / 'a.ide'))
    assert lod.inu.model_id == 5001
    assert _ide(lod) == ("В IDE (a.ide)", False)
    # Even with the id not kept on the LOD (older scenes), the status
    # derives it from the model: no false «сменился ID».
    lod.inu.model_id = 0
    assert _ide(lod) == ("В IDE (a.ide)", False)
    assert _ide(model) == ("В IDE (a.ide)", False)


def test_ide_lod_status_uses_cached_types(scene, tmp_path):
    ctx, objs = scene
    lod = _obj('LODhouse', sid=2, model_id=0, lod_draw_distance=500.0)
    model = _obj('house', sid=1, model_id=5000, lod_object=lod)
    others = [_obj(f'tree{i}', sid=10 + i, model_id=600 + i) for i in range(5)]
    objs += [model, lod] + others
    ml.ide_write(ctx, [model, lod], picked=str(tmp_path / 'a.ide'))
    lod.inu.model_id = 0
    CALLS['uncached'].clear()
    assert ml.ide_status(lod)[0] == "В IDE ({0})"   # found its model
    # The scene scan (every redraw) classifies through the cache; only the
    # active object itself (and name-only mocks) go uncached.
    scanned = [o for o in CALLS['uncached'] if any(o is s for s in objs)]
    assert scanned and all(o is lod for o in scanned)


# ── IPL status ─────────────────────────────────────────────────────

def _linked(ctx, objs, tmp_path, rot=(0.0, 0.0, 0.0, 1.0)):
    o = _obj('house', sid=1, model_id=100, pos=(10.0, 20.0, 3.0), rot=rot)
    objs.append(o)
    rep = ml.ipl_write(ctx, [o], picked=str(tmp_path / 'a.ipl'))
    assert not rep.problems()
    return o


def test_ipl_in_file(scene, tmp_path):
    ctx, objs = scene
    o = _linked(ctx, objs, tmp_path, rot=zrot(45))
    assert _ipl(o) == "В IPL (a.ipl)"


def test_ipl_rotation_counts(scene, tmp_path):
    ctx, objs = scene
    o = _linked(ctx, objs, tmp_path)
    o.matrix_world.set((10.0, 20.0, 3.0), zrot(1))    # turned 1°, not moved
    assert _ipl(o) == "В IPL, координаты разошлись"
    o.matrix_world.set((10.0, 20.0, 3.0), (0.0, 0.0, 0.0, -1.0))   # −q
    assert _ipl(o) == "В IPL (a.ipl)"


def test_ipl_position_tolerance(scene, tmp_path):
    ctx, objs = scene
    o = _linked(ctx, objs, tmp_path)
    o.matrix_world.set((10.00005, 20.0, 3.0))
    assert _ipl(o) == "В IPL (a.ipl)"
    o.matrix_world.set((10.001, 20.0, 3.0))
    assert _ipl(o) == "В IPL, координаты разошлись"


def test_ipl_vanilla_four_digit_quaternion(scene, tmp_path):
    """A row as R* wrote it (4 digits, norm ≠ 1), the object placed from it
    and stamped from it (IMG import): not «разошлись»."""
    _ctx, objs = scene
    ipl = tmp_path / 'lan2.ipl'
    ipl.write_bytes(b"inst\r\n4682, LAdtbuild3_LAn2, 0, 2233.8032, -1117.8828,"
                    b" 102.0391, 0, 0, -0.7071, 0.7071, -1\r\nend\r\n")
    row = IplDoc.load(str(ipl)).rows[0].inst
    n = math.sqrt(sum(c * c for c in (row.rot_x, row.rot_y, row.rot_z, row.rot_w)))
    o = _obj('LAdtbuild3_LAn2', sid=1, model_id=4682,
             pos=tuple(f32(c) for c in (row.pos_x, row.pos_y, row.pos_z)),
             rot=tuple(f32(c / n) for c in (row.rot_x, row.rot_y, row.rot_z,
                                            row.rot_w)))
    objs.append(o)
    ml.stamp_ipl(o, str(ipl), row, -1, fresh=True)
    o.inu.ipl_last_pos = tuple(f32(c) for c in o.inu.ipl_last_pos)
    o.inu.ipl_last_rot = tuple(f32(c) for c in o.inu.ipl_last_rot)
    assert _ipl(o) == "В IPL (lan2.ipl)"


def test_ipl_not_linked_lod_and_copy(scene, tmp_path):
    ctx, objs = scene
    o = _linked(ctx, objs, tmp_path)
    lod = _obj('LODhouse', sid=2, model_id=101)
    tree = _obj('tree', sid=3, model_id=300)
    copy = _obj('house.001', sid=4, model_id=100, **{
        k: getattr(o.inu, k) for k in ('ipl_uuid', 'ipl_target_file',
                                       'ipl_last_model_id', 'ipl_last_name',
                                       'ipl_last_pos', 'ipl_last_rot',
                                       'ipl_owner')})
    objs += [lod, tree, copy]
    assert _ipl(lod) == "LOD — пишется вместе с моделью"
    assert _ipl(tree) == "Не в IPL"
    assert _ipl(copy) == "Копия — добавится новым инстансом"
    assert _ipl(o) == "В IPL (a.ipl)"
