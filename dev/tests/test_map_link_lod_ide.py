"""ops/map_link — the IDE row of a LOD, run without Blender.

bpy is a private stub, scene objects are SimpleNamespaces; the entry builders
(_ide_entry_from_obj / _ipl_entry_from_obj / _clean_model_name_ide) are the
REAL ones, cut out of INU_tools/__init__.py; files go through the real
core/mapsync.

* a LOD keeps its OWN TXD (vanilla LAn2.ide: the model uses dtbuil1_lan2,
  its LOD lod_lan2) — «Add» with the model selected used to write the
  model's TXD over it, and the LOD lost its textures in the game;
* a LOD keeps its own LOD Dist, and its row is the same whether it is
  selected alone or with its model;
* a LOD with Model ID 0 is written as model id + 1 — that id is now kept
  on the LOD (IDE and IPL «Add»).
"""

from pathlib import Path
import ast
import importlib
import io
import re
import sys
import types
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[2]
WANTED = {'_ide_entry_from_obj', '_ipl_entry_from_obj', '_clean_model_name_ide'}


def _plain(name):
    return re.sub(r'\.\d+$', '', name)


def _model_type(obj):
    n = _plain(obj.name)
    if n.lower().startswith('lod'):
        return 'LOD', n[3:]
    return 'DFF', n


def _load():
    """Import INU_tools.ops.map_link against a private bpy stub, a minimal
    INU_tools package and a stub tools.model_utils. Other test files install
    their own stubs, so these modules go back into sys.modules only while a
    test here runs."""
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
        mu.get_model_type_cached = _model_type
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
    return bpy, pkg, mod, mods, mu


BPY, PKG, ml, MODS, MU = _load()
IdeDoc = MODS['INU_tools.core.mapsync'].IdeDoc
IplDoc = MODS['INU_tools.core.mapsync'].IplDoc

# Vanilla data\maps\LA\LAn2.ide: the LOD has its own TXD.
LAN2 = ("objs\r\n"
        "4682, LAdtbuild3_LAn2, dtbuil1_lan2, 120, 0\r\n"
        "4686, LODLAdtbuild3_LAn2, lod_lan2, 1500, 0\r\n"
        "end\r\n")


# ── fake scene ─────────────────────────────────────────────────────

class _Objects(list):
    """bpy_collection stand-in: ``name in objects`` works."""

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
    def __init__(self, pos, quat=(1.0, 0.0, 0.0, 0.0)):
        self.translation = NS(x=pos[0], y=pos[1], z=pos[2])
        self._q = quat

    def to_quaternion(self):
        return _Quat(*self._q)

    def to_scale(self):
        return (1.0, 1.0, 1.0)


def _obj(name, *, sid, pos=(0.0, 0.0, 0.0), **kw):
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
              matrix_world=_Matrix(pos))


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
    return ctx, objs


def _stamp_as_imported(o, path, dd):
    """What the IMG import leaves on an object with an IDE row."""
    inu = o.inu
    inu.ide_linked = True
    inu.ide_target_file = path
    inu.ide_last_model_id = inu.model_id
    inu.ide_last_name = o.name
    inu.ide_last_draw_distance = dd
    inu.ide_last_txd_name = inu.txd_name
    inu.ide_last_flags = inu.ide_flags


def _lan2(tmp_path, objs):
    ide = tmp_path / 'LAn2.ide'
    ide.write_bytes(LAN2.encode())
    lod = _obj('LODLAdtbuild3_LAn2', sid=2, model_id=4686,
               txd_name='lod_lan2', lod_draw_distance=1500.0)
    model = _obj('LAdtbuild3_LAn2', sid=1, model_id=4682,
                 txd_name='dtbuil1_lan2', draw_distance=120.0,
                 lod_draw_distance=1500.0, lod_object=lod)
    _stamp_as_imported(model, str(ide), 120.0)
    _stamp_as_imported(lod, str(ide), 1500.0)
    objs += [model, lod]
    return ide, model, lod


def _entry(objs_sel, who):
    for o, e, parent in ml.ide_entries(objs_sel, ml.Report()):
        if o is who:
            return e, parent
    raise AssertionError(f"{who.name} not in ide_entries")


def _row(e):
    return (int(e.model_id), e.model_name, e.txd_name, float(e.draw_distance))


# ── TXD and draw distance: the LOD's own, whatever is selected ─────

@pytest.mark.parametrize('pick', ['model+lod', 'lod', 'lod+model'])
def test_vanilla_lod_row_is_its_own(scene, tmp_path, pick):
    _ctx, objs = scene
    _ide, model, lod = _lan2(tmp_path, objs)
    sel = {'model+lod': [model, lod], 'lod': [lod],
           'lod+model': [lod, model]}[pick]
    e, parent = _entry(sel, lod)
    assert _row(e) == (4686, 'LODLAdtbuild3_LAn2', 'lod_lan2', 1500.0)
    assert parent is model


@pytest.mark.parametrize('pick', ['model+lod', 'lod'])
def test_vanilla_pair_add_changes_nothing(scene, tmp_path, pick):
    ctx, objs = scene
    ide, model, lod = _lan2(tmp_path, objs)
    sel = [model, lod] if pick == 'model+lod' else [lod]
    rep = ml.ide_write(ctx, sel)
    assert not rep.problems()
    assert not rep.counts.get('update') and not rep.counts.get('add')
    assert rep.counts.get('unchanged') == len(sel)
    assert ide.read_bytes() == LAN2.encode()
    assert lod.inu.ide_last_txd_name == 'lod_lan2'


def test_lod_own_draw_distance_wins(scene, tmp_path):
    _ctx, objs = scene
    _ide, model, lod = _lan2(tmp_path, objs)
    lod.inu.lod_draw_distance = 1800.0         # edited on the LOD (its field)
    for sel in ([model, lod], [lod]):
        e, _p = _entry(sel, lod)
        assert float(e.draw_distance) == 1800.0


def test_lod_without_own_txd_takes_models(scene, tmp_path):
    _ctx, objs = scene
    _ide, model, lod = _lan2(tmp_path, objs)
    lod.inu.txd_name = ''
    for sel in ([model, lod], [lod]):
        e, _p = _entry(sel, lod)
        assert e.txd_name == 'dtbuil1_lan2'


def test_lod_without_txd_or_model_takes_base_name(scene):
    _ctx, objs = scene
    lod = _obj('LODhouse', sid=1, model_id=101)
    objs.append(lod)
    e, parent = _entry([lod], lod)
    assert (e.txd_name, parent) == ('house', None)


# ── Model ID 0: written as model id + 1, and kept on the LOD ───────

def _new_pair(objs):
    lod = _obj('LODhouse', sid=2, model_id=0, txd_name='lod_house',
               lod_draw_distance=500.0)
    model = _obj('house', sid=1, model_id=5000, txd_name='house',
                 pos=(10.0, 20.0, 3.0), lod_object=lod)
    objs += [model, lod]
    return model, lod


def test_ide_write_keeps_lod_id(scene, tmp_path):
    ctx, objs = scene
    model, lod = _new_pair(objs)
    a = tmp_path / 'a.ide'
    rep = ml.ide_write(ctx, [model, lod], picked=str(a), dry_run=True)
    assert not rep.problems()
    assert lod.inu.model_id == 0                  # dry run: nothing stamped
    rep = ml.ide_write(ctx, [model, lod], picked=str(a))
    assert not rep.problems() and rep.counts.get('add') == 2
    assert lod.inu.model_id == 5001
    assert lod.inu.ide_last_model_id == 5001
    row = IdeDoc.load(str(a)).by_id(5001)
    assert (row.name, row.obj.txd_name) == ('LODhouse', 'lod_house')


def test_lod_alone_goes_to_its_models_ide(scene, tmp_path):
    ctx, objs = scene
    model, lod = _new_pair(objs)
    a = tmp_path / 'a.ide'
    a.write_bytes(b"objs\r\n5000, house, house, 299, 0\r\nend\r\n")
    _stamp_as_imported(model, str(a), 299.0)      # the model only is linked
    lod.inu.txd_name = ''
    rep = ml.ide_write(ctx, [lod])                # no file picked, not linked
    assert not rep.problems()
    row = IdeDoc.load(str(a)).by_id(5001)
    assert (row.name, row.obj.txd_name) == ('LODhouse', 'house')
    assert lod.inu.model_id == 5001


def test_ipl_write_keeps_lod_id(scene, tmp_path):
    ctx, objs = scene
    model, lod = _new_pair(objs)
    b = tmp_path / 'b.ipl'
    rep = ml.ipl_write(ctx, [model], picked=str(b), dry_run=True)
    assert not rep.problems()
    assert lod.inu.model_id == 0
    rep = ml.ipl_write(ctx, [model], picked=str(b))
    assert not rep.problems()
    rows = IplDoc.load(str(b)).rows
    assert [(r.inst.model_id, r.inst.model_name) for r in rows] == [
        (5000, 'house'), (5001, 'LODhouse')]
    assert lod.inu.model_id == 5001


def test_ipl_write_leaves_a_set_lod_id(scene, tmp_path):
    ctx, objs = scene
    model, lod = _new_pair(objs)
    lod.inu.model_id = 7777
    ml.ipl_write(ctx, [model], picked=str(tmp_path / 'b.ipl'))
    assert lod.inu.model_id == 7777
