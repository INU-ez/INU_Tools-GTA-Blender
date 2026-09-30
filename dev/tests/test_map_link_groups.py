"""ops/map_link — a model of several meshes at one spot is ONE placement.

The game draws every atomic of a map model with its IPL row's matrix
(core/mapsync/groups), so an imported breakable — bar_barrier10: the meshes
«bar_barrier10_L0_DFF» (linked to the row by the Import tab) and
«bar_barrier10_dam_DFF» — is one row, one IDE row, named bar_barrier10:

* IPL «Add» with the picked file writes no second row for the _dam mesh and
  leaves the file as it is (before: a row per mesh, renamed «…_L0»);
* IDE «Add» doesn't rename the row to «bar_barrier10_L0» (before: renamed,
  then a conflict for the _dam mesh);
* «Restore coords» moves the placement's meshes together — the _dam mesh
  doesn't take another free row of the model;
* the panel shows the placement's IPL state on the _dam mesh.

bpy is a private stub, objects are SimpleNamespaces, files are real; the
entry builders are the REAL ones cut out of INU_tools/__init__.py (as in
test_map_link_status.py).
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
    if n.upper().endswith('_DFF'):
        return 'DFF', n[:-4]
    if n.lower().startswith('lod'):
        return 'LOD', n[3:]
    return 'DFF', n


def _load():
    """map_link on a private bpy stub (see test_map_link_status._load)."""
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
                     'INU_tools.core.ide_flag_translate',
                     'INU_tools.tools.draw_cache'):
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
IplDoc = MODS['INU_tools.core.mapsync'].IplDoc
IdeDoc = MODS['INU_tools.core.mapsync'].IdeDoc

IDE_TEXT = "objs\r\n1461, bar_barrier10, bar_barrier, 100, 0\r\nend\r\n"
IPL_TEXT = ("inst\r\n"
            "1461, bar_barrier10, 0, 10.000000, 20.000000, 3.000000, "
            "0.000000, 0.000000, 0.000000, 1.000000, -1\r\n"
            "1461, bar_barrier10, 0, 50.000000, 0.000000, 0.000000, "
            "0.000000, 0.000000, 0.000000, 1.000000, -1\r\n"
            "end\r\n")


# ── fake scene ─────────────────────────────────────────────────────

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

    def pos(self):
        t = self.translation
        return (t.x, t.y, t.z)

    def __iter__(self):                 # rows (map_link.panel_main's key)
        return iter([self.pos(), self._q])

    def to_quaternion(self):
        return _Quat(*self._q)

    def to_scale(self):
        return (1.0, 1.0, 1.0)


class _Obj(NS):
    """A mesh; get() reads its custom props (inu_atomic_order)."""

    def get(self, key, default=None):
        return self.props.get(key, default)


class _Objects(list):
    """bpy.data.objects: get() by name."""

    def get(self, name, default=None):
        return next((o for o in self if o.name == name), default)


def _obj(name, *, sid, pos=(10.0, 20.0, 3.0), order=None, **kw):
    inu = dict(model_id=1461, txd_name='bar_barrier', draw_distance=100.0,
               lod_draw_distance=300.0, ide_flags=0, ide_flags_source_game='',
               type='OBJ', lod_object=None, ide_linked=False,
               ide_target_file='', ide_last_model_id=0, ide_last_name='',
               ide_last_draw_distance=0.0, ide_last_txd_name='',
               ide_last_flags=0, interior_id=0, real_interior=0, lod_index=-1,
               ipl_uuid='', ipl_target_file='', ipl_last_model_id=0,
               ipl_last_name='', ipl_last_pos=(0.0, 0.0, 0.0),
               ipl_last_rot=(0.0, 0.0, 0.0, 1.0), ipl_owner='')
    inu.update(kw)
    props = {} if order is None else {'inu_atomic_order': order}
    return _Obj(type='MESH', name=name, session_uid=sid, inu=NS(**inu),
                matrix_world=_Matrix(pos), parent=None, props=props)


def _stamp_ide(o, path):
    """What the Import tab leaves on every mesh of a model with an IDE row."""
    inu = o.inu
    inu.ide_linked, inu.ide_target_file = True, ml.norm(path)
    inu.ide_last_model_id, inu.ide_last_name = 1461, 'bar_barrier10'
    inu.ide_last_draw_distance, inu.ide_last_txd_name = 100.0, 'bar_barrier'
    inu.ide_last_flags = 0


def _copy(o, name, sid, pos):
    """Shift+D: the same custom props (so the same links)."""
    return _Obj(type='MESH', name=name, session_uid=sid, inu=NS(**vars(o.inu)),
                matrix_world=_Matrix(pos), parent=None, props=dict(o.props))


@pytest.fixture
def scene(monkeypatch):
    for k, v in MODS.items():
        monkeypatch.setitem(sys.modules, k, v)
    MODS['INU_tools.tools.draw_cache'].clear()
    objs = _Objects()
    ctx = NS(scene=NS(objects=objs, inu_settings=NS(
        gtatools_game='SA', gtatools_ide_path='', gtatools_ide_sync_list=[])))
    monkeypatch.setattr(BPY, 'data', NS(objects=objs))
    monkeypatch.setattr(BPY, 'context', ctx)
    monkeypatch.setattr(ml, 'apply_inst_transform', lambda o, inst: (
        o.matrix_world.set((inst.pos_x, inst.pos_y, inst.pos_z),
                           (inst.rot_x, inst.rot_y, inst.rot_z, inst.rot_w))))
    ml.reset_copies()
    return ctx, objs


@pytest.fixture
def barrier(scene, tmp_path):
    """bar_barrier10 as the Import tab leaves it: two meshes at the row of
    a.ipl, the intact one (first atomic) linked to it, both IDE-linked."""
    ctx, objs = scene
    ide, ipl = tmp_path / 'a.ide', tmp_path / 'a.ipl'
    ide.write_bytes(IDE_TEXT.encode())
    ipl.write_bytes(IPL_TEXT.encode())
    dam = _obj('bar_barrier10_dam_DFF', sid=1, order=1)
    whole = _obj('bar_barrier10_L0_DFF', sid=2, order=0)
    for o in (dam, whole):
        _stamp_ide(o, ide)
    row = IplDoc.load(str(ipl)).rows[0].inst
    ml.stamp_ipl(whole, ml.norm(str(ipl)), row, -1, fresh=True)
    objs += [dam, whole]
    return NS(ctx=ctx, objs=objs, ide=ide, ipl=ipl, whole=whole, dam=dam)


# ── one placement: main_of / ipl_expand ────────────────────────────

def test_expand_maps_the_damaged_part_to_the_main(barrier):
    b = barrier
    rep = ml.Report()
    assert ml.ipl_expand([b.dam], rep) == ([b.whole], [])
    ml.reset_copies()
    assert ml.ipl_expand([b.dam, b.whole], rep) == ([b.whole], [])
    ml.reset_copies()
    assert ml.main_of(b.whole) is b.whole
    assert ml.placement_name(b.dam) == 'bar_barrier10'


def test_moved_part_is_its_own_placement(barrier):
    b = barrier
    b.dam.matrix_world.set((12.0, 20.0, 3.0))
    assert ml.ipl_expand([b.dam], ml.Report()) == ([b.dam], [])
    assert ml.placement_name(b.dam) == ''          # its own name stands


def test_turned_part_is_its_own_placement(barrier):
    b = barrier
    b.dam.matrix_world.set((10.0, 20.0, 3.0), (0.0, 0.0, 0.7071068, 0.7071068))
    assert ml.main_of(b.dam) is b.dam


def test_old_import_linked_damaged_part_stays_main(barrier):
    """An import before the fix could stamp the row on the _dam mesh."""
    b = barrier
    row = IplDoc.load(str(b.ipl)).rows[0].inst
    ml.clear_ipl(b.whole)
    ml.stamp_ipl(b.dam, ml.norm(str(b.ipl)), row, -1, fresh=True)
    assert ml.main_of(b.whole) is b.dam
    assert ml.placement_name(b.whole) == 'bar_barrier10'


def test_two_linked_rows_at_one_spot_stay_two(scene, tmp_path):
    ctx, objs = scene
    ipl = tmp_path / 'dup.ipl'
    row = ("1461, bar_barrier10, 0, 10.000000, 20.000000, 3.000000, "
           "0.000000, 0.000000, 0.000000, 1.000000, -1\r\n")
    ipl.write_bytes(("inst\r\n" + row + row + "end\r\n").encode())
    rows = IplDoc.load(str(ipl)).rows
    a = _obj('bar_barrier10_L0_DFF', sid=1, order=0)
    c = _obj('bar_barrier10_L0_DFF.001', sid=2, order=0)
    ml.stamp_ipl(a, ml.norm(str(ipl)), rows[0].inst, -1, fresh=True)
    ml.stamp_ipl(c, ml.norm(str(ipl)), rows[1].inst, -1, fresh=True)
    objs += [a, c]
    assert ml.ipl_expand([a, c], ml.Report()) == ([a, c], [])
    before = ipl.read_bytes()
    rep = ml.ipl_write(ctx, [a, c], picked=str(ipl))
    assert not rep.problems() and rep.counts == {'unchanged': 2}
    assert ipl.read_bytes() == before


def test_main_rank_whole_part_first_atomic(scene):
    dam = _obj('x_dam_DFF', sid=1, order=0)
    whole = _obj('x_L0_DFF', sid=2, order=1)
    other = _obj('x_windows_DFF', sid=3, order=2)
    assert min([dam, other, whole], key=ml.main_rank) is whole
    assert min([dam, other], key=ml.main_rank) is other
    assert min([_obj('b_DFF', sid=4), _obj('a_DFF', sid=5)],
               key=ml.main_rank).name == 'a_DFF'


# ── IPL «Add» ──────────────────────────────────────────────────────

@pytest.mark.parametrize('pick', ['dam', 'both', 'whole'])
def test_ipl_add_leaves_the_row_alone(barrier, pick):
    b = barrier
    sel = {'dam': [b.dam], 'both': [b.dam, b.whole], 'whole': [b.whole]}[pick]
    before = b.ipl.read_bytes()
    rep = ml.ipl_write(b.ctx, sel, picked=str(b.ipl))
    assert not rep.problems()
    assert rep.counts == {'unchanged': 1}
    assert b.ipl.read_bytes() == before              # no 2nd row, no rename
    assert b.dam.inu.ipl_uuid == ''
    assert b.whole.inu.ipl_last_name == 'bar_barrier10'


def test_ipl_add_new_model_one_row_game_name(scene, tmp_path):
    """A model of two meshes never linked: one row, the game's name."""
    ctx, objs = scene
    whole = _obj('mybar_L0_DFF', sid=1, order=0, model_id=20000)
    dam = _obj('mybar_dam_DFF', sid=2, order=1, model_id=20000)
    objs += [dam, whole]
    ipl = tmp_path / 'new.ipl'
    rep = ml.ipl_write(ctx, [dam, whole], picked=str(ipl))
    assert not rep.problems() and rep.counts == {'add': 1}
    rows = IplDoc.load(str(ipl)).rows
    assert [(r.inst.model_id, r.inst.model_name) for r in rows] == [
        (20000, 'mybar')]
    assert whole.inu.ipl_uuid and not dam.inu.ipl_uuid


def test_ipl_add_new_model_lod_from_ide_by_model_name(scene, tmp_path):
    """The LOD row of a model of two meshes is looked up by the model's name
    (LODmybar), not by the main mesh's (mybar_L0)."""
    ctx, objs = scene
    ide = tmp_path / 'my.ide'
    ide.write_bytes(b"objs\r\n20000, mybar, mybar, 100, 0\r\n"
                    b"20001, LODmybar, mybar, 1000, 0\r\nend\r\n")
    ctx.scene.inu_settings.gtatools_ide_path = str(ide)
    whole = _obj('mybar_L0_DFF', sid=1, order=0, model_id=20000)
    dam = _obj('mybar_dam_DFF', sid=2, order=1, model_id=20000)
    objs += [dam, whole]
    ipl = tmp_path / 'new.ipl'
    rep = ml.ipl_write(ctx, [whole], picked=str(ipl))
    assert not rep.problems() and rep.counts.get('add') == 1
    rows = [r.inst for r in IplDoc.load(str(ipl)).rows]
    assert [(r.model_id, r.model_name) for r in rows] == [
        (20000, 'mybar'), (20001, 'LODmybar')]
    assert rows[0].lod_index == 1


def test_ipl_add_moved_copy_of_both_meshes(barrier):
    """Shift+D of both meshes, moved: one new row in the original's IPL —
    before, the _dam copy had «нет своего IPL»."""
    b = barrier
    cw = _copy(b.whole, 'bar_barrier10_L0_DFF.001', 3, (30.0, 0.0, 0.0))
    cd = _copy(b.dam, 'bar_barrier10_dam_DFF.001', 4, (30.0, 0.0, 0.0))
    b.objs += [cw, cd]
    rep = ml.ipl_write(b.ctx, [cd, cw])
    assert not rep.problems()
    assert rep.counts == {'add': 1}
    rows = IplDoc.load(str(b.ipl)).rows
    assert [(r.inst.model_name, r.inst.pos_x) for r in rows] == [
        ('bar_barrier10', 10.0), ('bar_barrier10', 50.0),
        ('bar_barrier10', 30.0)]
    assert cw.inu.ipl_uuid and cw.inu.ipl_uuid != b.whole.inu.ipl_uuid
    assert cd.inu.ipl_uuid == ''


def test_ipl_remove_via_the_damaged_part(barrier):
    b = barrier
    rep = ml.ipl_remove(b.ctx, [b.dam])
    assert rep.counts == {'removed': 1}
    assert [r.inst.pos_x for r in IplDoc.load(str(b.ipl)).rows] == [50.0]
    assert b.whole.inu.ipl_uuid == ''


# ── IDE «Add» ──────────────────────────────────────────────────────

@pytest.mark.parametrize('pick', ['whole', 'dam', 'both'])
def test_ide_add_keeps_the_model_name(barrier, pick):
    b = barrier
    sel = {'dam': [b.dam], 'both': [b.dam, b.whole], 'whole': [b.whole]}[pick]
    before = b.ide.read_bytes()
    rep = ml.ide_write(b.ctx, sel, picked=str(b.ide))
    assert not rep.problems()
    assert rep.counts == {'unchanged': 1}
    assert b.ide.read_bytes() == before              # not «bar_barrier10_L0»


def test_ide_add_new_model_one_row_game_name(scene, tmp_path):
    ctx, objs = scene
    whole = _obj('mybar_L0_DFF', sid=1, order=0, model_id=20000,
                 txd_name='mybar')
    dam = _obj('mybar_dam_DFF', sid=2, order=1, model_id=20000,
               txd_name='mybar')
    objs += [dam, whole]
    ide = tmp_path / 'new.ide'
    rep = ml.ide_write(ctx, [dam, whole], picked=str(ide))
    assert not rep.problems() and rep.counts == {'add': 1}
    rows = [r for r in IdeDoc.load(str(ide)).rows if r.section == 'objs']
    assert [(r.model_id, r.name) for r in rows] == [(20000, 'mybar')]


# ── «Restore coords» / «Verify» ────────────────────────────────────

def test_restore_moves_the_placement_together(barrier):
    """Both meshes dragged 2 m: the _dam mesh (selected alone) must not take
    the free row at x=50 — the placement goes back to its own row."""
    b = barrier
    for o in (b.whole, b.dam):
        o.matrix_world.set((12.0, 20.0, 3.0))
    rep = ml.ipl_pull(b.ctx, [b.dam], [str(b.ipl)], move=True, far='nearest')
    assert rep.counts == {'synced': 1}
    assert b.whole.matrix_world.pos() == (10.0, 20.0, 3.0)
    assert b.dam.matrix_world.pos() == (10.0, 20.0, 3.0)
    assert b.dam.inu.ipl_uuid == ''


def test_verify_links_only_the_main(barrier):
    b = barrier
    ml.clear_ipl(b.whole)
    rep = ml.ipl_pull(b.ctx, [b.dam, b.whole], [str(b.ipl)], move=False,
                      far='unique', clear_lost=True)
    assert rep.counts == {'linked': 1}
    assert b.whole.inu.ipl_uuid and not b.dam.inu.ipl_uuid
    assert b.whole.inu.ipl_last_pos == (10.0, 20.0, 3.0)


# ── panel: the _dam mesh shows its placement's row ─────────────────

def test_panel_main_of_uncached(barrier):
    b = barrier
    assert ml.main_of(b.dam, cached=False) is b.whole
    assert ml.panel_main(b.dam) is b.whole
    assert ml.panel_main(b.whole) is b.whole          # linked: its own
    assert ml.ipl_status(ml.panel_main(b.dam))[0] == "В IPL ({0})"
    b.dam.matrix_world.set((12.0, 20.0, 3.0))       # moved away: its own
    assert ml.main_of(b.dam, cached=False) is b.dam
    assert ml.panel_main(b.dam) is b.dam              # the memo key moved too
