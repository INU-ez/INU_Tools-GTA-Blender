"""«Анализ карты» (ops/map_analyzer_ops.py) with «Проверять модели в IMG»:
_gather_img_files must read each archive's directory. ImgReader reads
it only in open(), so the bare ``ImgReader(path)`` gave every archive an
empty name set and every IDE model / TXD came out «not found in IMG».
An archive reached twice under different spellings (CUSTOM walks the IDE
folders and the game root) is read once, so it doesn't shadow itself.
DAT mode adds models/gta3.img and gta_int.img, which the game registers
itself — vanilla gta.dat lists only carrec/script/cutscene.

bpy is stubbed; the helper and core.map_lint are pure Python."""

from pathlib import Path
import importlib
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
        bpy.types = types.SimpleNamespace(**{
            n: type(n, (base,), {}) for n in ('Operator', 'Panel',
                                              'PropertyGroup', 'UIList')})
        props = types.ModuleType('bpy.props')
        for n in ('StringProperty', 'BoolProperty', 'IntProperty',
                  'FloatProperty', 'EnumProperty', 'CollectionProperty'):
            setattr(props, n, lambda **kw: None)
        bpy.props = props
        bpy.path = types.SimpleNamespace(abspath=lambda p: p)
        bpy.data = types.SimpleNamespace(filepath='')
        sys.modules['bpy'] = bpy
        sys.modules['bpy.props'] = props
        pkg = types.ModuleType('INU_tools')
        pkg.__path__ = [str(ROOT / 'INU_tools')]
        pkg.T = lambda s, *_a, **_kw: s
        sys.modules['INU_tools'] = pkg
        for name in ('ops.map_analyzer_ops', 'core.img', 'core.map_lint',
                     'core.ide', 'core.ipl', 'core.game_versions'):
            importlib.import_module('INU_tools.' + name)
        return {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)


MODS = _load()
analyzer = MODS['INU_tools.ops.map_analyzer_ops']
core_img = MODS['INU_tools.core.img']
map_lint = MODS['INU_tools.core.map_lint']


@pytest.fixture(autouse=True)
def _mods(monkeypatch):
    # _gather_img_files imports core.img lazily — resolve it to ours.
    for key, mod in MODS.items():
        monkeypatch.setitem(sys.modules, key, mod)


def _archive(path, names, version=core_img.IMG_VERSION_2):
    core_img.create_img(path, version=version)
    with core_img.ImgWriter(path) as w:
        for n in names:
            w.add(n, b'x' * 10)
    return path


def test_archive_directory_is_read(tmp_path):
    p = _archive(str(tmp_path / 'gta3.img'), ('A.dff', 'a.txd'))
    assert analyzer._gather_img_files([p]) == {p: {'a.dff', 'a.txd'}}


def test_ver1_archive_is_read_through_its_dir(tmp_path):
    p = _archive(str(tmp_path / 'gta3.img'), ('b.dff',),
                 version=core_img.IMG_VERSION_1)
    assert analyzer._gather_img_files([p]) == {p: {'b.dff'}}


def test_broken_archive_is_left_out(tmp_path):
    bad = tmp_path / 'junk.img'
    bad.write_bytes(b'junk')
    good = _archive(str(tmp_path / 'gta3.img'), ('a.dff',))
    assert analyzer._gather_img_files([str(bad), good]) == {good: {'a.dff'}}


def test_one_archive_under_two_spellings_is_read_once(tmp_path):
    (tmp_path / 'models').mkdir()
    p = _archive(str(tmp_path / 'models' / 'gta3.img'), ('a.dff',))
    other = os.path.join(str(tmp_path), 'models', '..', 'models', 'gta3.img')
    assert analyzer._gather_img_files([p, other]) == {p: {'a.dff'}}


def test_custom_mode_mod_archive_inside_game_root(tmp_path):
    """IDE in a mod folder under the game root: both walks reach the
    mod's archive, the analysis must see it once — no self-shadowing."""
    root = tmp_path / 'game'
    mod = root / 'modloader' / 'mymod'
    mod.mkdir(parents=True)
    ide = mod / 'my.ide'
    ide.write_text('objs\n18000, a, a, 100, 0\nend\n')
    arch = _archive(str(mod / 'my.img'), ('a.dff', 'a.txd'))
    s = types.SimpleNamespace(
        gtatools_map_analyzer_mode='CUSTOM',
        gtatools_map_analyzer_custom_ides=[types.SimpleNamespace(path=str(ide))],
        gtatools_map_analyzer_custom_ipls=[],
        gtatools_map_analyzer_check_img=True,
        gtatools_game_root=os.path.join(str(root), 'modloader', '..'))
    ctx = types.SimpleNamespace(scene=types.SimpleNamespace(inu_settings=s))
    ides, _ipls, img_files, err = analyzer._collect_inputs(ctx)
    assert err is None and ides == [str(ide)]
    assert list(img_files.values()) == [{'a.dff', 'a.txd'}]
    assert os.path.samefile(next(iter(img_files)), arch)
    issues, _stats = map_lint.analyze_files(ides, [], img_files)
    assert not [i for i in issues if i.code.startswith('IMG_')]


def _dat_inputs(root, dat_text):
    """_collect_inputs in DAT mode on <root>/data/gta.dat, game root unset
    (taken from the .dat's folder)."""
    dat = root / 'data' / 'gta.dat'
    dat.write_text(dat_text)
    s = types.SimpleNamespace(
        gtatools_map_analyzer_mode='DAT',
        gtatools_map_analyzer_dat_path=str(dat),
        gtatools_map_analyzer_check_img=True,
        gtatools_game_root='')
    ctx = types.SimpleNamespace(scene=types.SimpleNamespace(inu_settings=s))
    return analyzer._collect_inputs(ctx)


def _game(tmp_path, ide_text):
    root = tmp_path / 'game'
    (root / 'data' / 'maps').mkdir(parents=True)
    (root / 'models').mkdir()
    (root / 'data' / 'maps' / 'my.ide').write_text(ide_text)
    return root


def _missing_or_shadowed(ides, img_files):
    issues, _stats = map_lint.analyze_files(ides, [], img_files)
    return [i.code for i in issues if i.code.startswith('IMG_')
            or i.code in ('IDE_DFF_MISSING', 'IDE_TXD_MISSING')]


def test_dat_mode_reads_the_archives_the_game_registers_itself(tmp_path):
    """Vanilla SA gta.dat: IMG lines only for carrec/script/cutscene, the
    map models live in gta3.img / gta_int.img the game adds on its own."""
    root = _game(tmp_path, 'objs\n18000, a, a, 100, 0\n'
                           '18001, b, b, 100, 0\nend\n')
    _archive(str(root / 'models' / 'gta3.img'), ('a.dff', 'a.txd'))
    _archive(str(root / 'models' / 'gta_int.img'), ('b.dff', 'b.txd'))
    _archive(str(root / 'models' / 'cutscene.img'), ('cs.dff',))
    ides, _ipls, img_files, err = _dat_inputs(
        root, 'IMG models\\cutscene.img\nIDE data\\maps\\my.ide\n')
    assert err is None and len(ides) == 1
    assert [os.path.basename(p) for p in img_files] == [
        'gta3.img', 'gta_int.img', 'cutscene.img']
    assert _missing_or_shadowed(ides, img_files) == []


def test_dat_mode_gta3_listed_in_the_dat_is_read_once(tmp_path):
    """A .dat that lists gta3.img itself, upper case as gta.dat writes
    paths (no gta_int.img, as in III/VC): one archive, no self-shadowing."""
    root = _game(tmp_path, 'objs\n18000, a, a, 100, 0\nend\n')
    _archive(str(root / 'models' / 'gta3.img'), ('a.dff', 'a.txd'))
    ides, _ipls, img_files, err = _dat_inputs(
        root, 'IMG MODELS\\GTA3.IMG\nIDE data\\maps\\my.ide\n')
    assert err is None and len(ides) == 1
    assert list(img_files.values()) == [{'a.dff', 'a.txd'}]
    assert _missing_or_shadowed(ides, img_files) == []


def test_models_in_the_archive_are_not_reported_missing(tmp_path):
    ide = tmp_path / 'my.ide'
    ide.write_text('objs\n18000, a, a, 100, 0\n18001, b, btxd, 100, 0\nend\n')
    p = _archive(str(tmp_path / 'gta3.img'), ('a.dff', 'a.txd'))
    img_files = analyzer._gather_img_files([p])
    issues, _stats = map_lint.analyze_files([str(ide)], [], img_files)
    missing = sorted((i.code, i.message.splitlines()[0]) for i in issues
                     if i.code in ('IDE_DFF_MISSING', 'IDE_TXD_MISSING'))
    # Only the model that really isn't there is flagged.
    assert missing == [('IDE_DFF_MISSING', "Имя модели = 'b'"),
                       ('IDE_TXD_MISSING', "Имя модели = 'b'")]


def test_modloader_loose_models_and_default_texdiction_found(tmp_path):
    root = _game(tmp_path, 'objs\n18000, house, vehicle, 100, 0\nend\n')
    mod = root / 'modloader' / 'my_map'
    mod.mkdir(parents=True)
    (mod / 'house.dff').write_bytes(b'dff')
    (root / 'models' / 'vehicle.txd').write_bytes(b'txd')
    (root / 'data' / 'default.dat').write_text('TEXDICTION models/vehicle.txd\n')
    ides, _ipls, assets, err = _dat_inputs(root, 'IDE data/maps/my.ide\n')
    assert err is None
    assert assets == {'<loose>': {'house.dff', 'vehicle.txd'}}
    assert _missing_or_shadowed(ides, assets) == []


def test_loose_override_does_not_report_archive_shadowing(tmp_path):
    ide = tmp_path / 'my.ide'
    ide.write_text('objs\n18000, a, a, 100, 0\nend\n')
    loose = tmp_path / 'a.dff'
    loose.write_bytes(b'x')
    arch = _archive(str(tmp_path / 'map.img'), ('a.dff', 'a.txd'))
    assets = analyzer._gather_img_files([arch], [str(loose)])
    assert _missing_or_shadowed([str(ide)], assets) == []


def test_dat_mode_reads_default_cdimage(tmp_path):
    root = _game(tmp_path, 'objs\n18000, a, a, 100, 0\nend\n')
    (root / 'data' / 'default.dat').write_text('CDIMAGE models/mod.img\n')
    _archive(str(root / 'models' / 'mod.img'), ('a.dff', 'a.txd'))
    ides, _ipls, assets, err = _dat_inputs(root, 'IDE data/maps/my.ide\n')
    assert err is None and _missing_or_shadowed(ides, assets) == []


def test_folder_mode_excludes_non_streaming_archives_and_other_game(tmp_path):
    for name in analyzer._NON_STREAMING_IMGS | {'gta3.img'}:
        _archive(str(tmp_path / name), ('a.dff',))
    other = tmp_path / 'other'
    (other / 'data').mkdir(parents=True)
    (other / 'data' / 'gta.dat').write_text('IMG other.img\n')
    _archive(str(other / 'other.img'), ('a.dff',))
    s = types.SimpleNamespace(gtatools_map_analyzer_mode='FOLDER',
        gtatools_map_analyzer_folder=str(tmp_path),
        gtatools_map_analyzer_recursive=False, gtatools_map_analyzer_check_img=True,
        gtatools_game_root=str(other))
    ctx = types.SimpleNamespace(scene=types.SimpleNamespace(inu_settings=s))
    _ides, _ipls, assets, err = analyzer._collect_inputs(ctx)
    assert err is None and list(assets) == [str(tmp_path / 'gta3.img')]


def test_disabled_img_check_does_not_scan_assets(tmp_path, monkeypatch):
    root = _game(tmp_path, 'objs\nend\n')
    (root / 'data' / 'gta.dat').write_text('IDE data/maps/my.ide\n')
    monkeypatch.setattr(analyzer, '_asset_inputs', lambda *_a, **_kw: pytest.fail('asset scan'))
    s = types.SimpleNamespace(gtatools_map_analyzer_mode='DAT',
        gtatools_map_analyzer_dat_path=str(root / 'data' / 'gta.dat'),
        gtatools_map_analyzer_check_img=False, gtatools_game_root='')
    ctx = types.SimpleNamespace(scene=types.SimpleNamespace(inu_settings=s))
    assert analyzer._collect_inputs(ctx)[2] is None


def test_txd_cannot_satisfy_dff_presence(tmp_path):
    ide = tmp_path / 'my.ide'
    ide.write_text('objs\n18000, a, a, 100, 0\nend\n')
    assert _missing_or_shadowed([str(ide)], {'<loose>': {'a.txd'}}) == ['IDE_DFF_MISSING']
