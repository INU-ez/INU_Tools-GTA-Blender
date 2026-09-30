"""The LOD name everywhere it is written, and the III/VC pair by name — run
without Blender.

bpy is a private stub, scene objects are SimpleNamespaces; tools.model_utils
is a stub over the REAL core.model_classify (no material scan); the entry
builders (_ide_entry_from_obj / _ipl_entry_from_obj / _clean_model_name_ide)
are the REAL ones cut out of INU_tools/__init__.py, as are «Поиск LOD»
(col_surface_ops) and Export All's _lod_file_base (inu_export); files go
through the real core.

* one name for a LOD in Add to IDE / IPL, Export IDE / IPL, Export All — the
  name it was imported with (tatar_str_1LOD), else LOD<base>; in III/VC the
  game's rule for its model (house → LODse) when that name is free — not
  another model's first by ID (dt_house1 / ne_house1), an object's, a row's
  of a known IDE or of the game folder (the vanilla LODhotel) — else
  LOD<base> and a warning;
* III/VC: a vanilla LOD is found by the game's rule (LODtower ↔ ap_tower,
  the model first by ID: lodbackbit → lhsbackbit) — only one standing on
  its model: a LOD placed apart (VC: ~1 in 8) would be moved / turned by a
  LOD row at the model's spot; Del of such a LOD alone finds it the same way;
* «Поиск LOD»: case-insensitive, LODhouse before LODhouse.001.
"""

from pathlib import Path
import ast
import importlib
import importlib.util
import io
import re
import sys
import types
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[2]
WANTED = {'_ide_entry_from_obj', '_ipl_entry_from_obj', '_clean_model_name_ide'}


def _plain(name):
    return re.sub(r'\.\d{3}$', '', name)


def _cut(path, pick, ns):
    """Exec the top-level functions / class methods *pick* of *path* in *ns*."""
    tree = ast.parse(io.open(path, encoding='utf-8').read())
    body = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in pick:
            body.append(n)
        elif isinstance(n, ast.ClassDef) and n.name in pick:
            body += [f for f in n.body if isinstance(f, ast.FunctionDef)
                     and f.name == pick[n.name]]
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), ns)
    return ns


def _load():
    """map_link, ide_export, ipl_export against a private bpy stub and a
    minimal INU_tools package; sys.modules is put back afterwards."""
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
        mc = importlib.import_module('INU_tools.core.model_classify')

        def model_type(obj):
            inu = getattr(obj, 'inu', None)
            return mc.classify_model(_plain(obj.name), has_texture=True,
                                     inu_type=getattr(inu, 'type', 'OBJ'))

        tools = types.ModuleType('INU_tools.tools')
        tools.__path__ = [str(ROOT / 'INU_tools' / 'tools')]
        mu = types.ModuleType('INU_tools.tools.model_utils')
        mu.get_model_type = mu.get_model_type_cached = model_type
        mu._strip_dup_suffix = _plain
        sys.modules['INU_tools.tools'] = tools
        sys.modules['INU_tools.tools.model_utils'] = mu
        mods = {}
        for name in ('ops.map_link', 'ops.ide_export', 'ops.ipl_export',
                     'core.ipl', 'core.ide', 'core.mapsync',
                     'core.game_versions', 'core.ide_flag_translate',
                     'core.gta_dat'):
            mods[name] = importlib.import_module('INU_tools.' + name)
        ns = {'__name__': 'INU_tools', '__package__': 'INU_tools',
              'bpy': bpy, 'get_model_type': model_type}
        _cut(ROOT / 'INU_tools' / '__init__.py', WANTED, ns)
        for name in WANTED:
            setattr(pkg, name, ns[name])
        ops_ns = {'__name__': 'INU_tools.ops.x', '__package__': 'INU_tools.ops',
                  'bpy': bpy, 'T': pkg.T}
        _cut(ROOT / 'INU_tools' / 'ops' / 'col_surface_ops.py',
             {'GTATOOLS_OT_auto_find_lod': 'execute'}, ops_ns)
        _cut(ROOT / 'INU_tools' / 'ops' / 'inu_export.py', {'_lod_file_base'}, ops_ns)
        all_mods = {k: v for k, v in sys.modules.items() if ours(k)}
    finally:
        for k in [k for k in sys.modules if ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    return bpy, mods, all_mods, ops_ns


BPY, M, MODS, OPS = _load()
ml = M['ops.map_link']
IdeDoc = M['core.mapsync'].IdeDoc
IplDoc = M['core.mapsync'].IplDoc


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


class _Vec(tuple):
    x, y, z = (property(lambda v, i=i: v[i]) for i in range(3))


class _Matrix:
    def __init__(self, pos, quat):
        self.translation = _Vec(pos)
        self._q = quat

    def to_quaternion(self):
        return _Quat(*self._q)

    def to_scale(self):
        return (1.0, 1.0, 1.0)


TURN = (0.7071068, 0.0, 0.0, 0.7071068)      # 90° about Z (w, x, y, z)


def _obj(name, mid=0, pos=(0.0, 0.0, 0.0), quat=(1.0, 0.0, 0.0, 0.0), **kw):
    inu = dict(model_id=mid, txd_name='', draw_distance=299.0,
               lod_draw_distance=999.0, ide_flags=0, ide_flags_source_game='',
               type='OBJ', lod_object=None, ide_linked=False,
               ide_target_file='', ide_last_model_id=0, ide_last_name='',
               ide_last_draw_distance=0.0, ide_last_txd_name='',
               ide_last_flags=0, interior_id=0, real_interior=0, lod_index=-1,
               ipl_uuid='', ipl_target_file='', ipl_last_model_id=0,
               ipl_last_name='', ipl_last_pos=(0.0, 0.0, 0.0),
               ipl_last_rot=(0.0, 0.0, 0.0, 1.0), ipl_owner='',
               lod_ide_id=0, lod_ide_name='', lod_ide_file='')
    inu.update(kw)
    return NS(type='MESH', name=name, inu=NS(**inu),
              matrix_world=_Matrix(pos, quat), material_slots=[])


@pytest.fixture
def scene(monkeypatch):
    for k, v in MODS.items():
        monkeypatch.setitem(sys.modules, k, v)
    objs = _Objects()
    settings = NS(gtatools_game='VC', gtatools_ide_path='',
                  gtatools_ide_sync_list=[])
    ctx = NS(scene=NS(objects=objs, inu_settings=settings),
             selected_objects=[])
    monkeypatch.setattr(BPY, 'data', NS(objects=objs))
    monkeypatch.setattr(BPY, 'context', ctx)
    ml.reset_copies()
    return ctx, objs, settings


def _names(path):
    doc = IdeDoc.load(str(path))
    return [r.name for r in doc.rows]


def _entry(sel, who):
    for o, e, _p in ml.ide_entries(sel, ml.Report()):
        if o is who:
            return e
    raise AssertionError(who.name)


# ── one name: Add to IDE / IPL ─────────────────────────────────────

@pytest.mark.parametrize('game, want', [('VC', 'LODse'), ('III', 'LODse'),
                                        ('SA', 'LODhouse')])
def test_add_names_a_new_lod_by_the_games_rule(scene, tmp_path, game, want):
    ctx, objs, settings = scene
    settings.gtatools_game = game
    lod = _obj('LODhouse', 101, (10.0, 0.0, 0.0))
    house = _obj('house', 100, (10.0, 0.0, 0.0))
    objs += [house, lod]
    ide, ipl = tmp_path / 'my.ide', tmp_path / 'my.ipl'
    ide.write_text('objs\nend\n')
    ipl.write_text('inst\nend\n')
    ml.ide_write(ctx, [house], picked=str(ide))
    assert _names(ide) == ['house', want]
    assert lod.inu.ide_last_name == want          # stamped: from now on kept
    ml.ipl_write(ctx, [house], picked=str(ipl))
    assert [r.inst.model_name for r in IplDoc.load(str(ipl)).rows] == ['house', want]


def test_lod_selected_alone_gets_its_models_name(scene):
    _ctx, objs, _s = scene
    lod = _obj('LODhouse', 101)
    objs += [_obj('house', 100), lod]
    assert _entry([lod], lod).model_name == 'LODse'


def test_lod_copy_gets_the_same_name(scene, tmp_path):
    _ctx, objs, _s = scene
    house, lod, copy = _obj('house', 100), _obj('LODhouse', 101), _obj('LODhouse.001', 101)
    objs += [house, lod, copy]
    assert _entry([copy], copy).model_name == 'LODse'
    assert ml.lod_hd_names([copy]) == {id(lod): 'house', id(copy): 'house'}
    ide = tmp_path / 'a.ide'
    M['ops.ide_export'].export_ide(str(ide), [house, lod, copy])
    assert _names(ide) == ['house', 'LODse']          # one row, one ID


def test_lod_without_its_model_keeps_its_base(scene):
    _ctx, objs, _s = scene
    lod = _obj('LODtower', 101)            # never LODer
    objs.append(lod)
    assert _entry([lod], lod).model_name == 'LODtower'


def test_warnings_when_the_game_wont_pair(scene):
    _ctx, objs, settings = scene
    lod = _obj('LODhouse', 101, ide_last_name='LODhouse', lod_draw_distance=300.0)
    objs += [_obj('house', 100), lod]
    rep = ml.Report()
    ml.ide_entries([lod], rep)
    texts = [t for lvl, t in rep.messages if lvl == 'WARNING']
    assert any('LODse' in t for t in texts)          # kept name + what's needed
    assert any('300' in t for t in texts)            # distance ≤ 300: no pair
    short = _obj('LODabc', 201)
    objs += [_obj('abc', 200), short]
    rep = ml.Report()
    ml.ide_entries([short], rep)
    assert any('4' in t for _l, t in rep.messages)
    settings.gtatools_game = 'SA'
    rep = ml.Report()
    ml.ide_entries([lod, short], rep)
    assert not rep.problems()


# ── III/VC: the game's name of a new LOD must be free ──────────────

def _houses(objs, dt_id=100, ne_id=200):
    dt, dtl = _obj('dt_house1', dt_id), _obj('LODdt_house1', dt_id + 1)
    ne, nel = _obj('ne_house1', ne_id), _obj('LODne_house1', ne_id + 1)
    objs += [dt, dtl, ne, nel]
    return dt, dtl, ne, nel


def test_one_tail_two_models_one_name(scene, tmp_path):
    """dt_house1 / ne_house1: one LODhouse1 — the game gives it the first by
    ID, one IMG holds one file of it; the other keeps LOD<base> on every
    path and says why."""
    _ctx, objs, _s = scene
    dt, dtl, ne, nel = _houses(objs)
    assert _entry([dt], dtl).model_name == 'LODhouse1'
    assert _entry([ne], nel).model_name == 'LODne_house1'
    ide = tmp_path / 'a.ide'
    M['ops.ide_export'].export_ide(str(ide), [dt, dtl, ne, nel])
    assert _names(ide) == ['dt_house1', 'LODhouse1', 'ne_house1', 'LODne_house1']
    fb, notes = OPS['_lod_file_base'], []
    assert fb({'DFF': dt, 'LOD': dtl, 'COL': None}, 'dt_house1', False, None,
              notes) == 'LODhouse1'
    assert fb({'DFF': ne, 'LOD': nel, 'COL': None}, 'ne_house1', False, None,
              notes) == 'LODne_house1'
    assert len(notes) == 1 and 'LODhouse1' in notes[0] and 'dt_house1' in notes[0]
    assert ml.lod_name_notes([dtl, nel]) == notes
    # renamed in the file browser / Export to IMG's copy of the model: same
    assert fb({'DFF': ne, 'LOD': nel, 'COL': None}, 'ne_house1', True) == 'LODne_house1'
    assert ml.new_lod_name('ne_house1', 'ne_house1') == 'LODne_house1'
    rep = ml.Report()
    ml.ide_entries([ne], rep)
    assert notes[0] in [t for lvl, t in rep.messages if lvl == 'WARNING']


def test_the_first_by_id_gets_the_name(scene):
    _ctx, objs, _s = scene
    dt, dtl, ne, nel = _houses(objs, dt_id=300, ne_id=200)
    assert _entry([ne], nel).model_name == 'LODhouse1'
    assert _entry([dt], dtl).model_name == 'LODdt_house1'
    ne.inu.model_id = nel.inu.model_id = 0      # no ID yet: after the real ones
    assert _entry([dt], dtl).model_name == 'LODhouse1'


def test_an_object_called_so_takes_the_name(scene):
    _ctx, objs, _s = scene
    house, lod = _obj('house', 100), _obj('LODhouse', 101)
    objs += [house, lod, _obj('se_LOD', 900, ide_last_name='LODse')]
    assert _entry([house], lod).model_name == 'LODhouse'


def _game(root, game, ide_text):
    maps = root / 'data' / 'maps'
    maps.mkdir(parents=True)
    (root / 'data' / {'VC': 'gta_vc.dat', 'III': 'gta3.dat'}[game]).write_text(
        'IDE data\\maps\\x.ide\n')
    (maps / 'x.ide').write_text(ide_text)
    return str(root)


def test_a_vanilla_name_of_the_game_folder_is_taken(scene, tmp_path):
    """my_hotel in VC: LODhotel is havhotel's — Export to IMG would replace
    the vanilla file, and the game gives the file to one ID of that name."""
    _ctx, objs, settings = scene
    my, lod = _obj('my_hotel', 7000), _obj('LODmy_hotel', 7001)
    objs += [my, lod]
    assert _entry([my], lod).model_name == 'LODhotel'          # no game folder
    settings.gtatools_game_root = _game(tmp_path / 'vc', 'VC',
                                        "objs\n1277, havhotel, lhhotelbg, 1, 149.5, 128\n"
                                        "1308, LODhotel, lodhavbig, 1, 2000, 0\nend\n")
    assert _entry([my], lod).model_name == 'LODmy_hotel'
    rep = ml.Report()
    ml.ide_entries([my], rep)
    assert any('LODhotel' in t and 'x.ide' in t for _l, t in rep.messages)
    settings.gtatools_game = 'III'          # a VC folder says nothing of III
    assert _entry([my], lod).model_name == 'LODhotel'


def test_iii_gives_the_name_to_the_first_model_anywhere(scene, tmp_path):
    """III looks through every model: morse (50) of the game takes LODse from
    house (700). VC — only in the IDE of the model."""
    _ctx, objs, settings = scene
    house, lod = _obj('house', 700), _obj('LODhouse', 701)
    objs += [house, lod]
    text = "objs\n50, morse, generic, 1, 150, 0\nend\n"
    settings.gtatools_game = 'III'
    settings.gtatools_game_root = _game(tmp_path / 'iii', 'III', text)
    assert _entry([house], lod).model_name == 'LODhouse'
    settings.gtatools_game = 'VC'
    settings.gtatools_game_root = _game(tmp_path / 'vc', 'VC', text)
    assert _entry([house], lod).model_name == 'LODse'


def test_the_lods_own_row_is_not_taken(scene, tmp_path):
    """A row of that name with the LOD's ID (an earlier Export IDE) is its
    own; with another ID — another model's."""
    _ctx, objs, settings = scene
    house, lod = _obj('house', 100), _obj('LODhouse', 0)
    objs += [house, lod]
    ide = tmp_path / 'my.ide'
    settings.gtatools_ide_path = str(ide)
    ide.write_text("objs\n100, house, house, 1, 150, 0\n101, LODse, house, 1, 1500, 0\nend\n")
    assert _entry([house], lod).model_name == 'LODse'
    ide.write_text("objs\n100, house, house, 1, 150, 0\n5555, LODse, x, 1, 1500, 0\nend\n")
    assert _entry([house], lod).model_name == 'LODhouse'


# ── III/VC: the pair by the game's rule ────────────────────────────

def _tower(objs, lod_quat=(1.0, 0.0, 0.0, 0.0), lod_pos=(5.0, 5.0, 0.0)):
    model = _obj('ap_tower_DFF', 1000, (5.0, 5.0, 0.0))
    lod = _obj('tower_LOD', 1001, lod_pos, lod_quat, ide_last_name='LODtower')
    objs += [model, lod]
    return model, lod


def test_vanilla_lod_found_by_the_rule(scene):
    _ctx, objs, _s = scene
    model, lod = _tower(objs)
    assert ml.LodIndex().partner(model) is lod
    assert _entry([model], lod).model_name == 'LODtower'


def test_vanilla_lod_placed_apart_is_left_alone(scene):
    _ctx, objs, _s = scene
    model, _lod = _tower(objs, lod_quat=TURN)            # turned
    assert ml.LodIndex().partner(model) is None
    objs.clear()
    model, _lod = _tower(objs, lod_pos=(30.0, 5.0, 0.0))  # moved
    assert ml.LodIndex().partner(model) is None


def test_moved_model_keeps_its_lod_by_its_ipl_row(scene):
    _ctx, objs, _s = scene
    model, lod = _tower(objs)
    model.inu.ipl_uuid = 'u'
    model.inu.ipl_last_pos = (5.0, 5.0, 0.0)
    model.matrix_world = _Matrix((50.0, 5.0, 0.0), (1.0, 0.0, 0.0, 0.0))
    assert ml.LodIndex().partner(model) is lod


def test_sa_does_not_pair_by_the_rule(scene):
    _ctx, objs, settings = scene
    settings.gtatools_game = 'SA'
    model, _lod = _tower(objs)
    assert ml.LodIndex().partner(model) is None


def test_lod_goes_to_the_first_model_by_id(scene):
    _ctx, objs, _s = scene
    lhs = _obj('lhsbackbit', 1410, (0.0, 0.0, 0.0))
    hav = _obj('havbackbit', 1451, (300.0, 0.0, 0.0))
    lod = _obj('backbit_LOD', 1500, (300.0, 0.0, 0.0), ide_last_name='lodbackbit')
    objs += [lhs, hav, lod]
    ix = ml.LodIndex()
    assert ix.partner(hav) is None          # the game gives it lhsbackbit
    assert ix.partner(lhs) is None          # … which it doesn't stand on
    lod.matrix_world = _Matrix((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))
    assert ml.LodIndex().partner(lhs) is lod


# ── III/VC: a LOD from the IDE by the game's rule ──────────────────

VC_IDE = ("objs\n"
          "1000, ap_tower, generic, 1, 150, 0\n"
          "1001, LODtower, generic, 1, 1500, 0\n"
          "1410, lhsbackbit, generic, 1, 150, 0\n"
          "1451, havbackbit, generic, 1, 150, 0\n"
          "1500, lodbackbit, generic, 1, 1500, 0\n"
          "end\n")


def _linked(o, ide):
    o.inu.ide_linked = True
    o.inu.ide_target_file = str(ide)


def test_ide_lod_found_by_the_rule(scene, tmp_path):
    ctx, objs, _s = scene
    ide = tmp_path / 'airport.ide'
    ide.write_text(VC_IDE)
    tower, lhs, hav = (_obj('ap_tower', 1000), _obj('lhsbackbit', 1410),
                       _obj('havbackbit', 1451))
    for o in (tower, lhs, hav):
        _linked(o, ide)
    objs += [tower, lhs, hav]
    lods = ml.IdeLods(ctx)
    assert lods.find(tower, 'ap_tower')[:2] == (1001, 'LODtower')
    assert lods.find(lhs, 'lhsbackbit')[:2] == (1500, 'lodbackbit')
    assert lods.find(hav, 'havbackbit') is None
    ctx.scene.inu_settings.gtatools_game = 'SA'
    assert ml.IdeLods(ctx).find(tower, 'ap_tower') is None


def _ipl_case(tmp_path, objs, lod_rot):
    ide = tmp_path / 'airport.ide'
    ide.write_text(VC_IDE)
    ipl = tmp_path / 'airport.ipl'
    text = ("inst\n"
            "1000, ap_tower, 0, 5, 5, 0, 1, 1, 1, 0, 0, 0, 1\n"
            + ("1001, LODtower, 0, 5, 5, 0, 1, 1, 1, %s\n" % lod_rot if lod_rot else "")
            + "end\n")
    ipl.write_text(text)
    tower = _obj('ap_tower', 1000, (5.0, 5.0, 0.0))
    _linked(tower, ide)
    row = IplDoc.load(str(ipl)).rows[0].inst
    ml.stamp_ipl(tower, str(ipl), row)
    objs.append(tower)
    return ipl, text, tower


def test_ipl_lod_row_on_the_model_follows_it(scene, tmp_path):
    ctx, objs, _s = scene
    ipl, text, tower = _ipl_case(tmp_path, objs, '0, 0, 0, 1')
    rep = ml.ipl_write(ctx, [tower])
    assert not rep.problems()
    assert ipl.read_text() == text                    # unchanged
    tower.matrix_world = _Matrix((8.0, 5.0, 0.0), (1.0, 0.0, 0.0, 0.0))
    ml.ipl_write(ctx, [tower])
    rows = [r.inst for r in IplDoc.load(str(ipl)).rows]
    assert [(r.model_name, r.pos_x) for r in rows] == [('ap_tower', 8.0), ('LODtower', 8.0)]


def test_ipl_lod_row_turned_apart_is_kept(scene, tmp_path):
    ctx, objs, _s = scene
    ipl, text, tower = _ipl_case(tmp_path, objs, '0, 0, -0.7071068, 0.7071068')
    rep = ml.ipl_write(ctx, [tower])
    assert ipl.read_text() == text                    # not turned, no second LOD
    assert any('LODtower' in t for lvl, t in rep.messages if lvl == 'INFO')


def test_ipl_new_lod_row_by_the_rule(scene, tmp_path):
    ctx, objs, _s = scene
    ipl, _text, tower = _ipl_case(tmp_path, objs, None)
    ml.ipl_write(ctx, [tower])
    rows = [r.inst.model_name for r in IplDoc.load(str(ipl)).rows]
    assert rows == ['ap_tower', 'LODtower']


def test_del_lod_alone_finds_its_model_by_the_rule(scene, tmp_path):
    """Del with only the vanilla LODtower selected: its model ap_tower is
    found as Add finds it (the game's rule) — the LOD row goes."""
    ctx, objs, _s = scene
    ipl, _text, _tower = _ipl_case(tmp_path, objs, '0, 0, 0, 1')
    lod = _obj('tower_LOD', 1001, (5.0, 5.0, 0.0), ide_last_name='LODtower')
    objs.append(lod)
    rep = ml.ipl_remove(ctx, [lod])
    assert not rep.problems()
    assert [r.inst.model_name for r in IplDoc.load(str(ipl)).rows] == ['ap_tower']


# ── Export IDE / IPL, Export All ───────────────────────────────────

def _tatar(objs, stamp):
    dff = _obj('tatar_str_1', 5000, (1.0, 2.0, 3.0))
    lod = _obj('tatar_str_1_LOD', 5001, (1.0, 2.0, 3.0), ide_last_name=stamp)
    objs += [dff, lod]
    return dff, lod


@pytest.mark.parametrize('stamp, want', [('tatar_str_1LOD', 'tatar_str_1LOD'),
                                         ('', 'LODtatar_str_1')])
def test_export_ide_ipl_use_the_lods_own_name(scene, tmp_path, stamp, want):
    _ctx, objs, settings = scene
    settings.gtatools_game = 'SA'
    dff, lod = _tatar(objs, stamp)
    ide, ipl = tmp_path / 'a.ide', tmp_path / 'a.ipl'
    M['ops.ide_export'].export_ide(str(ide), [dff, lod])
    M['ops.ipl_export'].export_ipl(str(ipl), [dff, lod])
    for path in (ide, ipl):
        text = path.read_text()
        assert want in text, path.name
        if stamp:
            assert 'LODtatar_str_1' not in text, path.name


def test_export_ide_ipl_vc_rule(scene, tmp_path):
    _ctx, objs, _s = scene
    house, lod = _obj('house', 100), _obj('LODhouse', 101)
    objs += [house, lod]
    ide, ipl = tmp_path / 'a.ide', tmp_path / 'a.ipl'
    M['ops.ide_export'].export_ide(str(ide), [house, lod])
    M['ops.ipl_export'].export_ipl(str(ipl), [lod])       # LOD alone: its model's
    assert 'LODse' in ide.read_text() and 'LODhouse' not in ide.read_text()
    assert 'LODse' in ipl.read_text()


def test_export_all_lod_file_name(scene):
    _ctx, objs, settings = scene
    settings.gtatools_game = 'SA'
    dff, lod = _tatar(objs, 'tatar_str_1LOD')
    fb = OPS['_lod_file_base']
    group = {'DFF': dff, 'LOD': lod, 'COL': None}
    assert fb(group, 'tatar_str_1', False) == 'tatar_str_1LOD'
    assert fb(group, 'x', True) == 'LODx'          # renamed in the browser
    lod.inu.ide_last_name = ''
    assert fb(group, 'tatar_str_1', False) == 'LODtatar_str_1'
    settings.gtatools_game = 'VC'
    house = {'DFF': _obj('house'), 'LOD': _obj('LODhouse'), 'COL': None}
    assert fb(house, 'house', False) == 'LODse'
    assert fb(house, 'house', True) == 'LODse'
    assert fb({'DFF': None, 'LOD': _obj('LODtower'), 'COL': None},
              'tower', False) == 'LODtower'
    # the LOD alone in the selection: for its model in the scene
    alone = {'DFF': None, 'LOD': house['LOD'], 'COL': None}
    assert fb(alone, 'house', False, {id(house['LOD']): 'house'}) == 'LODse'


# ── «Поиск LOD» ────────────────────────────────────────────────────

def _find_lod(ctx, sel):
    reps = []
    op = NS(report=lambda lvl, msg: reps.append(msg))
    ctx.selected_objects = list(sel)
    assert OPS['execute'](op, ctx) == {'FINISHED'}
    return reps[-1]


def test_find_lod_ignores_case_and_prefers_the_plain_name(scene):
    ctx, objs, settings = scene
    settings.gtatools_game = 'SA'
    landy, toll = _obj('landy', 11106), _obj('toll_SFW')     # vanilla SA pairs
    copy, lod = _obj('LODhouse.001'), _obj('LODhouse')
    house = _obj('house')
    objs += [landy, _obj('lodLANDY', 11336), toll, _obj('LOD_toll_sfw'),
             copy, lod, house]
    assert _find_lod(ctx, [landy, toll, house]) == "LOD найден: 3, не найдено: 0"
    assert landy.inu.lod_object is objs[1]
    assert toll.inu.lod_object is objs[3]
    assert house.inu.lod_object is lod


def test_find_lod_by_the_games_rule(scene):
    ctx, objs, _s = scene
    model, lod = _tower(objs)
    _find_lod(ctx, [model])
    assert model.inu.lod_object is lod


def _lang(name):
    spec = importlib.util.spec_from_file_location(
        "inu_locale_" + name, ROOT / "INU_tools" / "locale" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LANG


def test_new_messages_are_translated():
    tree = ast.parse(io.open(ROOT / 'INU_tools' / 'ops' / 'map_link.py',
                             encoding='utf-8').read())
    keys = set()
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name in ('_lod_link_notes',
                                                           'lod_name_note',
                                                           'ipl_write'):
            for n in ast.walk(fn):
                if (isinstance(n, ast.Call) and getattr(n.func, 'id', '') == 'T'
                        and n.args and isinstance(n.args[0], ast.Constant)):
                    keys.add(n.args[0].value)
    assert len(keys) > 8
    for lang in ('eng', 'spa'):
        missing = sorted(k for k in keys if k not in _lang(lang))
        assert missing == [], (lang, missing)
