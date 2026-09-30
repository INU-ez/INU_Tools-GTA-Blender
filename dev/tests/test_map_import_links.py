"""Import Map (ops/map_ops.py) links placed models like the Import tab:
the IDE row's file (same «last wins» as the row itself), the archive the
cached DFF came from (Extract's index; a DFF it lacks → the game's winner
in the archive directories), a LOD row's distance in lod_draw_distance
(kept in draw_distance too), and a copy of an already placed model drops
the first placement's IPL link.

bpy is stubbed; only invoke runs (the geometry loop needs Blender)."""

from pathlib import Path
import importlib
import json
import os
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _is_ours(name):
    return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))


def _load():
    """Import the addon modules against our own bpy / INU_tools stubs and
    hand back those modules; sys.modules is restored for other tests."""
    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for key in saved:
        del sys.modules[key]
    try:
        bpy = types.ModuleType('bpy')
        base = type('Base', (), {})
        bpy.app = types.SimpleNamespace(
            version=(4, 2, 0),
            handlers=types.SimpleNamespace(persistent=lambda f: f))
        bpy.types = types.SimpleNamespace(**{
            n: type(n, (base,), {}) for n in (
                'Operator', 'Panel', 'PropertyGroup', 'Menu', 'UIList',
                'Object', 'Collection', 'Scene')})
        props = types.ModuleType('bpy.props')
        for n in ('StringProperty', 'BoolProperty', 'IntProperty',
                  'FloatProperty', 'EnumProperty', 'FloatVectorProperty',
                  'CollectionProperty', 'PointerProperty'):
            setattr(props, n, lambda **kw: None)
        bpy.props = props
        bpy.path = types.SimpleNamespace(abspath=lambda p: p)
        bpy.data = types.SimpleNamespace(filepath='', objects=[])
        sys.modules['bpy'] = bpy
        sys.modules['bpy.props'] = props
        pkg = types.ModuleType('INU_tools')
        pkg.__path__ = [str(ROOT / 'INU_tools')]
        pkg.T = lambda s: s
        sys.modules['INU_tools'] = pkg
        for name in ('ops.map_ops', 'ops.map_link', 'ops.ipl_sections',
                     'core.map_files', 'core.gta_dat', 'core.ide',
                     'core.ipl', 'core.img', 'tools.profiler'):
            importlib.import_module('INU_tools.' + name)
        return {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)


MODS = _load()
map_ops = MODS['INU_tools.ops.map_ops']
map_link = MODS['INU_tools.ops.map_link']
core_img = MODS['INU_tools.core.img']


def _key(p):
    return os.path.normcase(os.path.abspath(p))


@pytest.fixture
def game(tmp_path, monkeypatch):
    for key, mod in MODS.items():
        monkeypatch.setitem(sys.modules, key, mod)
    cache = tmp_path / 'blend' / '.inu_cache'
    cache.mkdir(parents=True)
    monkeypatch.setattr(MODS['INU_tools'], '_get_cache_dir',
                        lambda: str(cache), raising=False)

    root = tmp_path / 'game'
    (root / 'data' / 'maps').mkdir(parents=True)
    (root / 'models').mkdir()
    (root / 'data' / 'gta.dat').write_text(
        'IDE DATA\\MAPS\\one.ide\nIDE DATA\\MAPS\\two.ide\n'
        'IPL DATA\\MAPS\\one.ipl\n')
    # ID 100 is in both IDEs: the second one wins (ide_models too).
    (root / 'data' / 'maps' / 'one.ide').write_text(
        'objs\n100, modela, txda, 150, 0\nend\n')
    (root / 'data' / 'maps' / 'two.ide').write_text(
        'objs\n100, modela, txdb, 250, 4\n101, modelb, txdb, 99, 0\nend\n')
    (root / 'data' / 'maps' / 'one.ipl').write_text(
        'inst\n100, modela, 0, 1, 2, 3, 0, 0, 0, 1, -1\nend\n')
    gta3 = str(root / 'models' / 'gta3.img')
    core_img.create_img(gta3)
    with core_img.ImgWriter(gta3) as w:
        w.add('modela.dff', b'A' * 100)
    other = str(root / 'models' / 'zz_mod.img')
    core_img.create_img(other)
    with core_img.ImgWriter(other) as w:
        w.add('modela.dff', b'B' * 100)
        w.add('modelb.dff', b'C' * 100)
    return types.SimpleNamespace(root=str(root), cache=str(cache),
                                 gta3=gta3, other=other)


def _invoke(g):
    settings = types.SimpleNamespace(
        gtatools_game_root=g.root, gtatools_img_path='',
        gtatools_map_region='ALL', gtatools_img_skip_lod=False,
        gtatools_map_skip_2dfx=False, gtatools_map_skip_dupes=False,
        gtatools_map_group_by_ipl=True, gtatools_profile_enabled=False,
        gtatools_text_ipls=[], gtatools_binary_ipls=[])
    wm = types.SimpleNamespace(
        progress_begin=lambda a, b: None, modal_handler_add=lambda op: None,
        event_timer_add=lambda *a, **k: object())
    scene = types.SimpleNamespace(inu_settings=settings,
                                  get=lambda k, d=None: d)
    ctx = types.SimpleNamespace(
        scene=scene, window=None, window_manager=wm,
        workspace=types.SimpleNamespace(status_text_set=lambda t: None))
    op = map_ops.GTATOOLS_OT_import_map()
    op.report = lambda kind, msg: None
    assert op.invoke(ctx, None) == {'RUNNING_MODAL'}
    return op


def test_ide_source_follows_the_row_that_wins(game):
    op = _invoke(game)
    assert op._ide_models[100].txd_name == 'txdb'
    two = os.path.join(game.root, 'data', 'maps', 'two.ide')
    assert op._ide_source[100] == _key(two)
    assert op._ide_source[101] == _key(two)


def test_archive_without_index_is_the_game_winner(game):
    op = _invoke(game)
    assert _key(op._src_arch['modela.dff']) == _key(game.gta3)
    assert _key(op._src_arch['modelb.dff']) == _key(game.other)


def test_archive_from_the_extract_index(game):
    # The index names the archive the cached file came from (not the
    # winner); a DFF it lacks (ESC'd Extract over an older cache) → winner.
    with open(os.path.join(game.cache, '_extract_index.json'), 'w') as f:
        json.dump({'files': {'modela.dff': [game.other, 0, 1, 2],
                             'modela.col': [game.gta3, 0, 1, 2],
                             'broken.dff': 'x'}}, f)
    op = _invoke(game)
    assert op._src_arch['modela.dff'] == game.other
    assert _key(op._src_arch['modelb.dff']) == _key(game.other)
    assert set(op._src_arch) == {'modela.dff', 'modelb.dff'}


# ── map_link.stamp_map_import / clear_ipl on plain objects ──────────────

def _obj(**kw):
    inu = types.SimpleNamespace(
        img_target_file='', draw_distance=299.0, lod_draw_distance=999.0,
        ide_flags=0, txd_name='', ide_target_file='', ide_linked=False,
        ide_last_model_id=0, ide_last_name='', ide_last_draw_distance=0.0,
        ide_last_txd_name='', ide_last_flags=0,
        ipl_uuid='u1', ipl_target_file='C:/x.ipl', ipl_last_model_id=100,
        ipl_last_name='modela', ipl_last_pos=(1.0, 2.0, 3.0),
        ipl_last_rot=(0.0, 0.0, 0.0, 1.0), ipl_owner='modela', lod_index=5)
    for k, v in kw.items():
        setattr(inu, k, v)
    return types.SimpleNamespace(name='modela', inu=inu)


def _ide_row(dd=150.0):
    return types.SimpleNamespace(model_id=100, model_name='modela',
                                 txd_name='txda', draw_distance=dd, flags=4)


def test_lod_row_distance_goes_to_lod_draw_distance():
    o = _obj()
    map_link.stamp_map_import(o, True, _ide_row(400.0), 'c:/maps/one.ide',
                              'c:/models/gta3.img', 'lodmodela')
    assert o.inu.lod_draw_distance == 400.0
    # Export IDE / Ariane read draw_distance on a LOD too — not 299.
    assert o.inu.draw_distance == 400.0
    assert o.inu.ide_last_draw_distance == 400.0
    assert o.inu.ide_linked and o.inu.ide_target_file == 'c:/maps/one.ide'
    assert o.inu.img_target_file == 'c:/models/gta3.img'
    assert (o.inu.ide_flags, o.inu.txd_name) == (4, 'txda')


def test_model_row_distance_and_link():
    o = _obj()
    map_link.stamp_map_import(o, False, _ide_row(), 'c:/maps/one.ide', '',
                              'modela')
    assert o.inu.draw_distance == 150.0
    assert o.inu.lod_draw_distance == 999.0
    assert (o.inu.ide_last_model_id, o.inu.ide_last_name) == (100, 'modela')
    assert o.inu.img_target_file == ''


def test_no_ide_row_unlinks_and_names_the_txd():
    o = _obj(ide_linked=True, ide_target_file='c:/old.ide',
             ide_last_model_id=7)
    map_link.stamp_map_import(o, False, None, '', '', 'modela')
    assert not o.inu.ide_linked and o.inu.ide_target_file == ''
    assert o.inu.ide_last_model_id == 0
    assert o.inu.txd_name == 'modela'
    o = _obj(txd_name='own')
    map_link.stamp_map_import(o, False, None, '', '', 'modela')
    assert o.inu.txd_name == 'own'


def test_row_without_ide_file_is_not_linked():
    o = _obj(ide_linked=True, ide_target_file='c:/old.ide')
    map_link.stamp_map_import(o, False, _ide_row(), '', '', 'modela')
    assert o.inu.draw_distance == 150.0
    assert not o.inu.ide_linked and o.inu.ide_target_file == ''


def test_copy_drops_the_first_placements_ipl_link():
    o = _obj()
    map_link.clear_ipl(o)
    assert o.inu.ipl_uuid == '' and o.inu.ipl_target_file == ''
    assert o.inu.lod_index == -1 and o.inu.ipl_last_model_id == 0
