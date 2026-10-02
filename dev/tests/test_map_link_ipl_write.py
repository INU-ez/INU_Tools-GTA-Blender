"""ops/map_link — the Blender bridge of IPL «Add», run without Blender.

bpy is a private stub, scene objects are SimpleNamespaces, the IPL files are
real (tmp_path) and go through the real core/mapsync:

* new rows take the layout of the FILE, not of the scene's game
  (``file_game``): VC drops an 11-column SA row, SA misreads a 13-column one;
* «Add» for a Shift+D copy writes a new row into the original's IPL
  (before: «нет своего IPL»); a LOD selected alone leaves copies alone;
* a scaled object written into an SA row (no scale column) is reported;
* the IPL «Add» (move=True) into another file moves the model: its old row
  and LOD leave the old file — unless SA stream IPLs number that file's rows.
"""

from pathlib import Path
import importlib
import re
import struct
import sys
import types
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    """Import INU_tools.ops.map_link against a private bpy stub and a minimal
    INU_tools package (only T). Other test files install their own stubs, so
    these modules go back into sys.modules only while a test here runs."""
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
        mod = importlib.import_module('INU_tools.ops.map_link')
        # map_link imports these inside its functions
        for name in ('INU_tools.core.ipl', 'INU_tools.core.mapsync',
                     'INU_tools.core.game_versions', 'INU_tools.core.img',
                     'INU_tools.core.gta_dat'):
            importlib.import_module(name)
        mods = {k: v for k, v in sys.modules.items() if ours(k)}
    finally:
        for k in [k for k in sys.modules if ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    return bpy, pkg, mod, mods


BPY, PKG, ml, MODS = _load()
IplInstance = MODS['INU_tools.core.ipl'].IplInstance
_tokens = MODS['INU_tools.core.ipl']._tokens
IplDoc = MODS['INU_tools.core.mapsync'].IplDoc

SA_TEXT = (
    "# test map\r\n"
    "inst\r\n"
    "100, house, 0, 10.000000, 0.000000, 0.000000, 0.000000, 0.000000, "
    "0.000000, 1.000000, 1\r\n"
    "101, LODhouse, 0, 10.000000, 0.000000, 0.000000, 0.000000, 0.000000, "
    "0.000000, 1.000000, -1\r\n"
    "end\r\n"
    "cull\r\n"
    "end\r\n")

VC_TEXT = (
    "inst\r\n"
    "100, house, 0, 10.000000, 0.000000, 0.000000, 1.000000, 1.000000, "
    "1.000000, 0.000000, 0.000000, 0.000000, 1.000000\r\n"
    "101, LODhouse, 0, 10.000000, 0.000000, 0.000000, 1.000000, 1.000000, "
    "1.000000, 0.000000, 0.000000, 0.000000, 1.000000\r\n"
    "end\r\n")

III_TEXT = (
    "inst\r\n"
    "100, house, 10.000000, 0.000000, 0.000000, 1.000000, 1.000000, "
    "1.000000, 0.000000, 0.000000, 0.000000, 1.000000\r\n"
    "end\r\n")


# ── fake scene ─────────────────────────────────────────────────────

def _plain(name):
    return re.sub(r'\.\d+$', '', name)


def _model_type(obj):
    n = _plain(obj.name)
    if n.lower().startswith('lod'):
        return 'LOD', n[3:]
    return 'DFF', n


def _entry_from_obj(obj):
    """What __init__._ipl_entry_from_obj builds, from the fake's fields."""
    x, y, z = obj.pos
    return IplInstance(model_id=obj.inu.model_id, model_name=_plain(obj.name),
                       interior=obj.inu.interior_id, pos_x=x, pos_y=y, pos_z=z,
                       lod_index=obj.inu.lod_index,
                       real_interior=obj.inu.real_interior)


class _Matrix:
    """matrix_world stand-in: map_link only reads to_scale() from it."""

    def __init__(self, scale=(1.0, 1.0, 1.0)):
        self._scale = tuple(scale)

    def to_scale(self):
        return self._scale


def _obj(name, mid, pos, *, sid, scale=(1.0, 1.0, 1.0)):
    inu = NS(model_id=mid, interior_id=0, real_interior=0, lod_index=-1,
             lod_object=None, type='', ide_linked=False, ide_target_file='',
             ide_last_name='', ipl_uuid='', ipl_target_file='',
             ipl_last_model_id=0, ipl_last_name='',
             ipl_last_pos=(0.0, 0.0, 0.0), ipl_last_rot=(0.0, 0.0, 0.0, 1.0),
             ipl_owner='')
    return NS(type='MESH', name=name, session_uid=sid, inu=inu,
              pos=tuple(pos), matrix_world=_Matrix(scale))


def _shift_d(orig, name, pos, sid):
    """Blender duplicate: same custom props (so the same IPL link)."""
    return NS(type='MESH', name=name, session_uid=sid,
              inu=NS(**vars(orig.inu)), pos=tuple(pos),
              matrix_world=_Matrix())


@pytest.fixture
def scene(monkeypatch):
    for k, v in MODS.items():
        monkeypatch.setitem(sys.modules, k, v)
    objs = []
    ctx = NS(scene=NS(objects=objs, inu_settings=NS(
        gtatools_game='SA', gtatools_ide_path='', gtatools_ide_sync_list=[])))
    monkeypatch.setattr(BPY, 'data', NS(objects=objs))
    monkeypatch.setattr(BPY, 'context', ctx)
    monkeypatch.setattr(PKG, '_ipl_entry_from_obj', _entry_from_obj,
                        raising=False)
    monkeypatch.setattr(ml, 'model_type', _model_type)
    monkeypatch.setattr(ml, 'plain_name', lambda o: _plain(o.name))
    ml.reset_copies()
    return ctx, objs


def _house_with_copy(tmp_path, objs, text=SA_TEXT):
    """a.ipl with house + its LOD; the scene: house (linked to row 0), its
    LOD mesh and a Shift+D copy of house moved to x=50."""
    a = tmp_path / 'a.ipl'
    a.write_bytes(text.encode())
    house = _obj('house', 100, (10.0, 0.0, 0.0), sid=1)
    lod = _obj('LODhouse', 101, (10.0, 0.0, 0.0), sid=2)
    row = IplDoc.load(str(a)).rows[0].inst
    ml.stamp_ipl(house, str(a), row, row.lod_index)
    copy = _shift_d(house, 'house.001', (50.0, 0.0, 0.0), sid=3)
    objs += [house, lod, copy]
    return a, house, lod, copy


def _levels(rep, level):
    return [t for lv, t in rep.messages if lv == level]


# ── file_game: layout of the file, not of the scene ────────────────

def _new_row(text, game, fla=None):
    doc = IplDoc.from_text(text)
    ed = doc.editor(game=ml.file_game(doc, game), fla=fla)
    ed.place('tree', IplInstance(model_id=200, model_name='tree', pos_x=50.0))
    out = ed.commit().to_text()
    rows = [ln for ln in out.split('\r\n') if ln.startswith('200,')]
    assert len(rows) == 1
    return out, rows[0]


def test_file_game_reads_the_rows():
    assert ml.file_game(IplDoc.from_text(VC_TEXT), 'SA') == 'VC'
    assert ml.file_game(IplDoc.from_text(III_TEXT), 'SA') == 'III'
    assert ml.file_game(IplDoc.from_text(SA_TEXT), 'VC') == 'SA'


def test_file_game_empty_file_takes_scene_game():
    assert ml.file_game(IplDoc.new(), 'VC') == 'VC'
    assert ml.file_game(IplDoc.new(), 'III') == 'III'
    junk = "inst\r\n# only a comment\r\nnot, a, row\r\nend\r\n"
    assert ml.file_game(IplDoc.from_text(junk), 'VC') == 'VC'


def test_file_game_mixed_file_takes_majority():
    vc_row = VC_TEXT.split('\r\n')[1]
    sa_row = SA_TEXT.split('\r\n')[2]
    text = "inst\r\n" + "\r\n".join([sa_row, vc_row, vc_row]) + "\r\nend\r\n"
    assert ml.file_game(IplDoc.from_text(text), 'SA') == 'VC'


@pytest.mark.parametrize('text, scene_game, ntok', [
    (VC_TEXT, 'SA', 13),
    (III_TEXT, 'SA', 12),
    (SA_TEXT, 'VC', 11),
], ids=['vc-file', 'iii-file', 'sa-file'])
def test_new_row_in_files_layout_old_rows_kept(text, scene_game, ntok):
    out, row = _new_row(text, scene_game)
    assert len(_tokens(row)) == ntok
    old = [ln for ln in text.split('\r\n') if ln[:4] in ('100,', '101,')]
    for ln in old:
        assert ln + '\r\n' in out                       # byte for byte


def test_vc_file_fla_adds_no_column():
    _out, row = _new_row(VC_TEXT, 'SA', fla=True)
    assert len(_tokens(row)) == 13


def test_ipl_write_sa_scene_into_vc_file(scene, tmp_path):
    ctx, objs = scene
    path = tmp_path / 'vc.ipl'
    path.write_bytes(VC_TEXT.encode())
    tree = _obj('tree', 300, (5.0, 6.0, 7.0), sid=1)
    objs.append(tree)
    rep = ml.ipl_write(ctx, [tree], picked=str(path))
    assert not rep.problems()
    lines = path.read_bytes().decode().split('\r\n')
    assert lines[1:3] == VC_TEXT.split('\r\n')[1:3]
    new = [ln for ln in lines if ln.startswith('300,')]
    assert len(new) == 1 and len(_tokens(new[0])) == 13


def test_ipl_write_vc_scene_into_sa_file(scene, tmp_path):
    ctx, objs = scene
    ctx.scene.inu_settings.gtatools_game = 'VC'
    path = tmp_path / 'sa.ipl'
    path.write_bytes(SA_TEXT.encode())
    tree = _obj('tree', 300, (5.0, 6.0, 7.0), sid=1)
    objs.append(tree)
    ml.ipl_write(ctx, [tree], picked=str(path))
    new = [ln for ln in path.read_bytes().decode().split('\r\n')
           if ln.startswith('300,')]
    assert len(new) == 1 and len(_tokens(new[0])) == 11


def test_ipl_remove_from_vc_file(scene, tmp_path):
    ctx, objs = scene
    a, house, _lod, copy = _house_with_copy(tmp_path, objs, VC_TEXT)
    objs.remove(copy)
    rep = ml.ipl_remove(ctx, [house])
    assert rep.counts.get('removed') == 1
    assert rep.counts.get('lod_removed') == 1
    assert IplDoc.load(str(a)).rows == []
    assert house.inu.ipl_uuid == ''


# ── Shift+D copy: new row in the original's IPL ────────────────────

def test_copy_row_add_goes_into_originals_ipl(scene, tmp_path):
    ctx, objs = scene
    a, house, _lod, copy = _house_with_copy(tmp_path, objs)
    uid = house.inu.ipl_uuid
    rep = ml.ipl_write(ctx, [copy])                 # row «Add»: no picked file
    assert not rep.problems()
    lines = a.read_bytes().decode().split('\r\n')
    assert lines[2:4] == SA_TEXT.split('\r\n')[2:4]   # original rows untouched
    doc = IplDoc.load(str(a))
    assert len(doc.rows) == 4
    new = doc.rows[2].inst
    assert (new.model_id, new.pos_x) == (100, 50.0)
    lod_row = doc.rows[new.lod_index].inst
    assert (lod_row.model_name, lod_row.pos_x) == ('LODhouse', 50.0)
    assert copy.inu.ipl_uuid and copy.inu.ipl_uuid != uid
    assert copy.inu.ipl_target_file == ml.norm(str(a))
    assert house.inu.ipl_uuid == uid


def test_copy_dry_run_has_no_error_and_writes_nothing(scene, tmp_path):
    ctx, objs = scene
    a, house, _lod, copy = _house_with_copy(tmp_path, objs)
    before = a.read_bytes()
    rep = ml.ipl_write(ctx, [copy], dry_run=True)
    assert not rep.problems()
    assert rep.counts.get('add') == 1
    assert a.read_bytes() == before
    assert copy.inu.ipl_uuid == house.inu.ipl_uuid     # still a copy


def test_copy_into_picked_file_no_false_warning(scene, tmp_path):
    ctx, objs = scene
    a, _house, _lod, copy = _house_with_copy(tmp_path, objs)
    before = a.read_bytes()
    b = tmp_path / 'b.ipl'
    for dry in (True, False):
        rep = ml.ipl_write(ctx, [copy], picked=str(b), dry_run=dry)
        assert not rep.problems()     # never had a row in a.ipl: no «была в»
    assert a.read_bytes() == before
    doc = IplDoc.load(str(b))
    assert [r.inst.model_id for r in doc.rows] == [100, 101]
    assert copy.inu.ipl_target_file == ml.norm(str(b))


def test_original_and_copy_together(scene, tmp_path):
    ctx, objs = scene
    a, house, _lod, copy = _house_with_copy(tmp_path, objs)
    house.pos = (12.0, 0.0, 0.0)
    rep = ml.ipl_write(ctx, [house, copy])
    assert not rep.problems()
    assert rep.counts.get('update') == 1 and rep.counts.get('add') == 1
    doc = IplDoc.load(str(a))
    xs = [(r.inst.model_id, r.inst.pos_x) for r in doc.rows]
    assert xs == [(100, 12.0), (101, 12.0), (100, 50.0), (101, 50.0)]
    assert doc.rows[0].inst.lod_index == 1 and doc.rows[2].inst.lod_index == 3


def test_lod_selected_alone_leaves_copies_alone(scene, tmp_path):
    ctx, objs = scene
    a, house, lod, copy = _house_with_copy(tmp_path, objs)
    before = a.read_bytes()
    rep = ml.ipl_write(ctx, [lod])
    assert not rep.problems()
    assert not rep.counts.get('add')
    assert a.read_bytes() == before
    assert copy.inu.ipl_uuid == house.inu.ipl_uuid     # not split off


def test_copy_follows_original_moved_to_other_file(scene, tmp_path):
    ctx, objs = scene
    a, house, _lod, copy = _house_with_copy(tmp_path, objs)
    b = tmp_path / 'b.ipl'
    ml.ipl_write(ctx, [house], picked=str(b))          # the original moves
    assert house.inu.ipl_target_file == ml.norm(str(b))
    assert ml.ipl_linked_file(copy) == ml.norm(str(a))  # the copy's is stale
    a_before, b_before = a.read_bytes(), b.read_bytes()
    rep = ml.ipl_write(ctx, [copy], dry_run=True)
    assert not rep.problems() and rep.counts.get('add') == 1
    assert (a.read_bytes(), b.read_bytes()) == (a_before, b_before)
    rep = ml.ipl_write(ctx, [copy])
    assert not rep.problems()
    assert a.read_bytes() == a_before
    xs = [(r.inst.model_id, r.inst.pos_x) for r in IplDoc.load(str(b)).rows]
    assert xs == [(100, 10.0), (101, 10.0), (100, 50.0), (101, 50.0)]
    assert copy.inu.ipl_target_file == ml.norm(str(b))


def test_copy_originals_file_gone_no_new_file(scene, tmp_path):
    ctx, objs = scene
    a, _house, _lod, copy = _house_with_copy(tmp_path, objs)
    a.unlink()
    for dry in (True, False):
        rep = ml.ipl_write(ctx, [copy], dry_run=dry)
        assert [t for t in _levels(rep, 'ERROR') if 'нет своего IPL' in t]
        assert not a.exists()
    b = tmp_path / 'b.ipl'                              # a picked file still works
    rep = ml.ipl_write(ctx, [copy], picked=str(b))
    assert not rep.problems()
    assert [r.inst.model_id for r in IplDoc.load(str(b)).rows] == [100, 101]


# ── scale: an SA row has no scale column ───────────────────────────

@pytest.mark.parametrize('style, scale, warned', [
    ('SA', (2.0, 1.0, 1.0), True),
    ('SA', (1.0, 1.0, 0.5), True),
    ('VC', (2.0, 1.0, 1.0), True),
    ('III', (2.0, 1.0, 1.0), True),
    ('SA', (1.00005, 1.0, 1.0), False),
    ('SA', (1.0, 1.0, 1.0), False),
])
def test_scale_note(style, scale, warned):
    rep = ml.Report()
    obj = NS(name='house', matrix_world=_Matrix(scale))
    ml._scale_note(obj, style, rep)
    msgs = _levels(rep, 'WARNING')
    assert len(msgs) == int(warned)
    if warned:
        assert 'house' in msgs[0] and 'масштаб' in msgs[0]


@pytest.mark.parametrize('dry', [True, False])
def test_scaled_object_into_sa_file_warns(scene, tmp_path, dry):
    ctx, objs = scene
    path = tmp_path / 'sa.ipl'
    path.write_bytes(SA_TEXT.encode())
    tree = _obj('tree', 300, (5.0, 6.0, 7.0), sid=1, scale=(2.0, 2.0, 2.0))
    objs.append(tree)
    rep = ml.ipl_write(ctx, [tree], picked=str(path), dry_run=dry)
    assert [t for t in _levels(rep, 'WARNING') if 'масштаб' in t]
    assert rep.counts.get('add') == 1                  # still written


def test_scaled_object_into_vc_file_warns_game_ignores_scale(scene, tmp_path):
    ctx, objs = scene
    path = tmp_path / 'vc.ipl'
    path.write_bytes(VC_TEXT.encode())
    tree = _obj('tree', 300, (5.0, 6.0, 7.0), sid=1, scale=(2.0, 2.0, 2.0))
    objs.append(tree)
    rep = ml.ipl_write(ctx, [tree], picked=str(path))
    assert any('игра не применяет масштаб' in t for t in _levels(rep, 'WARNING'))


# ── IPL «Add» into another file: the model moves ───────────────────

NEIGHBOUR_TEXT = (
    "inst\r\n"
    "100, house, 0, 10.000000, 0.000000, 0.000000, 0.000000, 0.000000, "
    "0.000000, 1.000000, 2\r\n"
    "300, tree, 0, 50.000000, 0.000000, 0.000000, 0.000000, 0.000000, "
    "0.000000, 1.000000, 3\r\n"
    "101, LODhouse, 0, 10.000000, 0.000000, 0.000000, 0.000000, 0.000000, "
    "0.000000, 1.000000, -1\r\n"
    "301, LODtree, 0, 50.000000, 0.000000, 0.000000, 0.000000, 0.000000, "
    "0.000000, 1.000000, -1\r\n"
    "end\r\n")


def _moving_house(tmp_path, objs, text=SA_TEXT, folder=None):
    """a.ipl (in *folder*) with house (row 0) + its LOD; the scene: house
    linked to it and its LOD mesh. Returns (a, b = the picked file, house)."""
    folder = folder or tmp_path
    folder.mkdir(parents=True, exist_ok=True)
    a = folder / 'a.ipl'
    a.write_bytes(text.encode())
    house = _obj('house', 100, (10.0, 0.0, 0.0), sid=1)
    lod = _obj('LODhouse', 101, (10.0, 0.0, 0.0), sid=2)
    row = IplDoc.load(str(a)).rows[0].inst
    ml.stamp_ipl(house, str(a), row, row.lod_index)
    objs += [house, lod]
    return a, tmp_path / 'b.ipl', house


def _img(path, names):
    """A VER2 IMG holding only a directory of *names*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    recs = b''.join(struct.pack('<IHH', 1, 1, 0) + n.encode().ljust(24, b'\0')
                    for n in names)
    path.write_bytes(b'VER2' + struct.pack('<I', len(names)) + recs)


@pytest.mark.parametrize('text', [SA_TEXT, VC_TEXT], ids=['sa', 'vc'])
def test_move_takes_row_and_lod_out_of_old_file(scene, tmp_path, text):
    ctx, objs = scene
    a, b, house = _moving_house(tmp_path, objs, text)
    rep = ml.ipl_write(ctx, [house], picked=str(b), move=True)
    assert not rep.problems()
    assert [t for t in _levels(rep, 'INFO') if 'переносится' in t]
    assert rep.counts.get('moved') == 1 and rep.counts.get('lod_removed') == 1
    assert IplDoc.load(str(a)).rows == []
    assert [r.inst.model_id for r in IplDoc.load(str(b)).rows] == [100, 101]
    assert house.inu.ipl_target_file == ml.norm(str(b))
    assert 'перенесено из другого файла 1' in ml.summary('IPL', rep)


def test_move_dry_run_touches_nothing(scene, tmp_path):
    ctx, objs = scene
    a, b, house = _moving_house(tmp_path, objs)
    before = a.read_bytes()
    rep = ml.ipl_write(ctx, [house], picked=str(b), dry_run=True, move=True)
    assert not rep.problems()
    assert rep.counts.get('moved') == 1
    assert a.read_bytes() == before and not b.exists()
    assert house.inu.ipl_target_file == str(a)


def test_move_keeps_neighbours_and_renumbers_their_lod(scene, tmp_path):
    ctx, objs = scene
    a, b, house = _moving_house(tmp_path, objs, NEIGHBOUR_TEXT)
    tree = _obj('tree', 300, (50.0, 0.0, 0.0), sid=5)
    row = IplDoc.load(str(a)).rows[1].inst
    ml.stamp_ipl(tree, str(a), row, row.lod_index)
    objs.append(tree)
    rep = ml.ipl_write(ctx, [house], picked=str(b), move=True)
    assert not rep.problems()
    rows = [r.inst for r in IplDoc.load(str(a)).rows]
    assert [(r.model_id, r.lod_index) for r in rows] == [(300, 1), (301, -1)]


def test_move_without_lod_mesh_carries_existing_sa_lod(scene, tmp_path):
    ctx, objs = scene
    a, b, house = _moving_house(tmp_path, objs)
    objs[:] = [house]               # the LOD's existing file row is enough
    rep = ml.ipl_write(ctx, [house], picked=str(b), move=True)
    assert not rep.problems()
    assert IplDoc.load(str(a)).rows == []
    assert [r.inst.model_id for r in IplDoc.load(str(b)).rows] == [100, 101]


def test_move_skipped_when_new_row_not_written(scene, tmp_path):
    ctx, objs = scene
    a, b, house = _moving_house(tmp_path, objs)
    house.inu.model_id = 0
    before = a.read_bytes()
    rep = ml.ipl_write(ctx, [house], picked=str(b), move=True)
    assert [t for t in _levels(rep, 'ERROR') if 'Model ID = 0' in t]
    assert a.read_bytes() == before
    assert not rep.counts.get('moved')


def test_no_move_keeps_old_row_and_warns(scene, tmp_path):
    """INU Export (move=False): old behaviour — row written, old one kept."""
    ctx, objs = scene
    a, b, house = _moving_house(tmp_path, objs)
    before = a.read_bytes()
    rep = ml.ipl_write(ctx, [house], picked=str(b))
    assert [t for t in _levels(rep, 'WARNING')
            if 'в старом файле строка осталась' in t]
    assert a.read_bytes() == before
    assert not rep.counts.get('moved')
    assert [r.inst.model_id for r in IplDoc.load(str(b)).rows] == [100, 101]


def test_copy_is_not_moved(scene, tmp_path):
    ctx, objs = scene
    a, house, _lod, copy = _house_with_copy(tmp_path, objs)
    before = a.read_bytes()
    b = tmp_path / 'b.ipl'
    for dry in (True, False):
        rep = ml.ipl_write(ctx, [copy], picked=str(b), dry_run=dry, move=True)
        assert not rep.problems() and not rep.counts.get('moved')
    assert a.read_bytes() == before
    assert house.inu.ipl_target_file == str(a)


@pytest.mark.parametrize('dry', [True, False])
def test_move_blocked_by_sa_stream_ipls(scene, tmp_path, dry):
    ctx, objs = scene
    game = tmp_path / 'game'
    _img(game / 'models' / 'gta3.img',
         ['house.dff', 'a_stream0.ipl', 'a_stream1.ipl'])
    a, b, house = _moving_house(tmp_path, objs, folder=game / 'data' / 'maps')
    before = a.read_bytes()
    rep = ml.ipl_write(ctx, [house], picked=str(b), dry_run=dry, move=True)
    warns = [t for t in _levels(rep, 'WARNING') if 'a_stream*' in t]
    assert len(warns) == 1 and 'a.ipl' in warns[0]
    assert a.read_bytes() == before
    assert not rep.counts.get('moved')
    assert rep.counts.get('add') == 1                  # still written into b


def test_move_allowed_when_game_has_no_stream_of_file(scene, tmp_path):
    ctx, objs = scene
    game = tmp_path / 'game'
    _img(game / 'models' / 'gta3.img', ['lan2_stream0.ipl', 'aa_stream0.ipl'])
    a, b, house = _moving_house(tmp_path, objs, folder=game / 'data' / 'maps')
    rep = ml.ipl_write(ctx, [house], picked=str(b), move=True)
    assert not rep.problems()
    assert rep.counts.get('moved') == 1
    assert IplDoc.load(str(a)).rows == []


def test_stream_prefix_game_folder_and_gta_dat(scene, tmp_path):
    ctx, _objs = scene
    game = tmp_path / 'game'
    _img(game / 'models' / 'gta_int.img', ['gen_int1_stream0.ipl'])
    (game / 'data').mkdir(parents=True)
    (game / 'data' / 'gta.dat').write_text("IMG MODELS\\custom.img\n")
    _img(game / 'models' / 'custom.img', ['my_stream0.ipl'])
    ipl = tmp_path / 'elsewhere' / 'GEN_INT1.IPL'
    assert ml._stream_prefix(str(ipl), ctx, {}) == ''     # outside any game
    ctx.scene.inu_settings.gtatools_game_root = str(game)
    assert ml._stream_prefix(str(ipl), ctx, {}) == 'gen_int1_stream'
    mine = tmp_path / 'elsewhere' / 'my.ipl'
    assert ml._stream_prefix(str(mine), ctx, {}) == 'my_stream'
    assert ml._stream_prefix(str(tmp_path / 'x.ipl'), ctx, {}) == ''


@pytest.mark.parametrize('dry', [True, False])
@pytest.mark.parametrize('only_lod', [True, False])
def test_remove_keeps_sa_rows_numbered_by_stream_ipls(scene, tmp_path, dry, only_lod):
    ctx, objs = scene
    game = tmp_path / 'game'
    _img(game / 'models' / 'gta3.img', ['a_stream0.ipl'])
    a, _b, house = _moving_house(tmp_path, objs, folder=game / 'data' / 'maps')
    before = a.read_bytes()
    target = objs[-1] if only_lod else house
    rep = ml.ipl_remove(ctx, [target], dry_run=dry)
    assert a.read_bytes() == before
    assert not rep.counts.get('removed') and not rep.counts.get('lod_removed')
    assert house.inu.ipl_target_file == str(a)
    assert house.inu.lod_index == 1
    assert any('a_stream*.ipl' in msg and 'строки сохранены' in msg
               for msg in _levels(rep, 'WARNING'))


def test_sa_add_offset_lod_and_move_between_files(scene, tmp_path):
    ctx, objs = scene
    text = SA_TEXT.replace('101, LODhouse, 0, 10.000000', '101, LODhouse, 0, 12.500000')
    a, b, house = _moving_house(tmp_path, objs, text)
    before = a.read_bytes()
    rep = ml.ipl_write(ctx, [house])
    assert a.read_bytes() == before and rep.counts.get('unchanged') == 1
    house.pos = (40, 0, 0)
    rep = ml.ipl_write(ctx, [house], picked=str(b), move=True)
    assert not rep.problems()
    rows = IplDoc.load(str(b)).rows
    assert rows[1].inst.pos_x - rows[0].inst.pos_x == 2.5
    assert IplDoc.load(str(a)).rows == []
