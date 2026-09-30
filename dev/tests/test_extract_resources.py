"""Extract Resources (ops/img_ops.py) end to end on a tiny game folder:
the logs hold only the last run, a name in two archives comes from the
first in the game's load order, the cache follows the archives through
.inu_cache/_extract_index.json (a model replaced in place is rewritten, an
unchanged archive is not re-extracted), GTA III palette textures get R↔B.

bpy is stubbed; the operator runs invoke → modal (TIMER) → _cleanup."""

from pathlib import Path
import importlib
import os
import struct
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
        bpy.app = types.SimpleNamespace(version=(4, 2, 0))
        bpy.types = types.SimpleNamespace(**{
            n: type(n, (base,), {}) for n in (
                'Operator', 'Panel', 'PropertyGroup', 'Menu', 'UIList')})
        props = types.ModuleType('bpy.props')
        for n in ('StringProperty', 'BoolProperty', 'IntProperty',
                  'FloatProperty', 'EnumProperty', 'FloatVectorProperty',
                  'CollectionProperty', 'PointerProperty'):
            setattr(props, n, lambda **kw: None)
        bpy.props = props
        bpy.path = types.SimpleNamespace(abspath=lambda p: p)
        bpy.data = types.SimpleNamespace(filepath='')
        sys.modules['bpy'] = bpy
        sys.modules['bpy.props'] = props
        pkg = types.ModuleType('INU_tools')
        pkg.__path__ = [str(ROOT / 'INU_tools')]
        pkg.T = lambda s: s
        sys.modules['INU_tools'] = pkg
        for name in ('ops.img_ops', 'core.map_files', 'core.txd',
                     'core.gta_dat', 'core.ide', 'core.ipl', 'core.img',
                     'tools.profiler'):
            importlib.import_module('INU_tools.' + name)
        return {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)


MODS = _load()
img_ops = MODS['INU_tools.ops.img_ops']
core_img = MODS['INU_tools.core.img']


# ── stand-ins: TXD decoder and PNG writer ────────────────────────

def _fake_read_txd(data):
    """b'PAL' → one GTA III palette texture, b'SA9' → one D3D9 texture,
    b'BAD' → a parse error."""
    kind = bytes(data[:3])
    if kind == b'BAD':
        raise ValueError('broken TXD')
    pid, fmt, name = {b'PAL': (8, 0x2000, 'pal'), b'SA9': (9, 0x0500, 'sa')}[kind]
    return [types.SimpleNamespace(name=name, width=1, height=1, platform_id=pid,
                                  raster_format=fmt, pixels=b'\x01\x02\x03\x04')]


def _png(w, h, pixels=b''):
    return (b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR'
            + struct.pack('>II', w, h) + bytes(pixels))


def _fake_write_png(path, pixels, w, h):
    with open(path, 'wb') as f:
        f.write(_png(w, h, pixels))


@pytest.fixture
def game(tmp_path, monkeypatch):
    for key, mod in MODS.items():
        monkeypatch.setitem(sys.modules, key, mod)
    pkg = MODS['INU_tools']
    cache = tmp_path / 'blend' / '.inu_cache'
    cache.mkdir(parents=True)
    monkeypatch.setattr(pkg, '_get_cache_dir', lambda: str(cache), raising=False)
    monkeypatch.setattr(pkg, '_write_png', _fake_write_png, raising=False)
    monkeypatch.setattr(MODS['INU_tools.core.txd'], 'read_txd', _fake_read_txd)
    monkeypatch.setattr(MODS['bpy'].data, 'filepath', str(tmp_path / 'blend' / 'a.blend'))

    root = tmp_path / 'game'
    (root / 'models').mkdir(parents=True)
    gta3 = str(root / 'models' / 'gta3.img')
    core_img.create_img(gta3)
    with core_img.ImgWriter(gta3) as w:
        w.add('a.dff', b'X' * 1000)
        w.add('pal.txd', b'PAL' + b'.' * 100)
        w.add('bad.txd', b'BAD' + b'.' * 100)
    return types.SimpleNamespace(root=str(root), gta3=gta3, cache=str(cache))


def _extract(g, region='ALL'):
    settings = types.SimpleNamespace(
        gtatools_game_root=g.root, gtatools_img_path='',
        gtatools_map_region=region, gtatools_profile_enabled=False)
    wm = types.SimpleNamespace(
        progress_begin=lambda a, b: None, progress_update=lambda v: None,
        progress_end=lambda: None, modal_handler_add=lambda op: None,
        event_timer_add=lambda *a, **k: object(),
        event_timer_remove=lambda t: None)
    ctx = types.SimpleNamespace(
        scene=types.SimpleNamespace(inu_settings=settings), window=None,
        window_manager=wm,
        workspace=types.SimpleNamespace(status_text_set=lambda t: None))
    op = img_ops.GTATOOLS_OT_extract_resources()
    reports = []
    op.report = lambda kind, msg: reports.append(msg)
    assert op.invoke(ctx, None) == {'RUNNING_MODAL'}
    timer = types.SimpleNamespace(type='TIMER')
    for _ in range(10000):
        if op.modal(ctx, timer) == {'FINISHED'}:
            break
    else:
        pytest.fail('Extract did not finish')
    return op, reports[-1]


def _read(path):
    with open(path, 'rb') as f:
        return f.read()


def test_extract_logs_hold_only_the_last_run(game):
    for name in ('_txd_errors.log', '_extract_skipped.log'):
        with open(os.path.join(game.cache, name), 'w', encoding='utf-8') as f:
            f.write('OLD RUN\n')
    _extract(game)
    errors = _read(os.path.join(game.cache, '_txd_errors.log')).decode()
    skipped = _read(os.path.join(game.cache, '_extract_skipped.log')).decode()
    assert 'OLD RUN' not in errors and 'OLD RUN' not in skipped
    assert errors.count('bad.txd') == 1
    _extract(game)                  # the broken TXD is checked again…
    errors = _read(os.path.join(game.cache, '_txd_errors.log')).decode()
    assert errors.count('bad.txd') == 1     # …but logged once, for this run


def test_first_run_extracts_and_swaps_palette_colours(game):
    op, msg = _extract(game)
    assert _read(os.path.join(game.cache, 'a.dff')).startswith(b'X')
    # GTA III palette (D3D8, PAL8): R and B back in place
    assert _read(os.path.join(game.cache, 'textures', 'pal.png')).endswith(
        b'\x03\x02\x01\x04')
    idx = MODS['INU_tools.core.map_files'].load_index(game.cache)
    assert len(idx['files']['a.dff']) == 4 and 'pal.txd' in idx['txd']
    assert 'bad.txd' not in idx['txd']
    assert idx['txd_png']['pal.txd'] == ['pal.png']
    assert idx['tex_ver'] == 2
    assert 'DFF: 1' in msg and op._tex_count == 1


def test_unchanged_archive_is_not_extracted_again(game):
    _extract(game)
    op, msg = _extract(game)
    assert op._plan['files'] == {}
    assert [k for k, _e in op._plan['txd'][game.gta3]] == ['bad.txd']
    assert op._same == 2 and op._dff_count == 0 and op._tex_count == 0
    assert 'без изменений: 2' in msg


def test_model_replaced_in_place_reaches_the_cache(game):
    _extract(game)
    st = os.stat(game.gta3)
    with core_img.ImgWriter(game.gta3) as w:     # same length: same slot
        w.add('a.dff', b'Y' * 1000)
    os.utime(game.gta3, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    op, _msg = _extract(game)
    assert _read(os.path.join(game.cache, 'a.dff')).startswith(b'Y')
    assert op._dff_count == 1
    assert op._tex_count == 0 and op._same == 1   # pal.txd: same CRC


def test_deleted_png_is_decoded_again(game):
    _extract(game)
    os.remove(os.path.join(game.cache, 'textures', 'pal.png'))
    op, _msg = _extract(game)
    assert os.path.isfile(os.path.join(game.cache, 'textures', 'pal.png'))
    assert op._tex_count == 1


def test_png_of_an_older_decode_is_rewritten_once(game):
    tex = os.path.join(game.cache, 'textures')
    os.makedirs(tex, exist_ok=True)
    with open(os.path.join(tex, 'pal.png'), 'wb') as f:     # bigger, old colours
        f.write(_png(64, 64))
    _extract(game)
    assert _read(os.path.join(tex, 'pal.png')).endswith(b'\x03\x02\x01\x04')
    idx = MODS['INU_tools.core.map_files'].load_index(game.cache)
    assert idx['tex_stale'] == []


def test_region_reads_the_stream_ipl_record_the_game_loads(game):
    """Region LA: TXDs of the models its stream IPL places. The archive
    repeats lan_stream0.ipl (an IMG tool appended a copy); the game loads
    the first record, so only pal.txd is needed, bad.txd is filtered."""
    maps = os.path.join(game.root, 'data', 'maps', 'LA')
    os.makedirs(maps)
    with open(os.path.join(game.root, 'data', 'gta.dat'), 'w') as f:
        f.write('IDE data\\maps\\LA\\LAn.ide\nIPL data\\maps\\LA\\LAn.ipl\n')
    with open(os.path.join(maps, 'LAn.ide'), 'w') as f:
        f.write('objs\n100, m_pal, pal, 100, 0\n101, m_bad, bad, 100, 0\nend\n')
    with open(os.path.join(maps, 'LAn.ipl'), 'w') as f:
        f.write('inst\nend\n')
    ipl = MODS['INU_tools.core.ipl']

    def stream(mid):
        return ipl._write_binary_ipl(ipl.IplFile(instances=[
            ipl.IplInstance(model_id=mid, model_name='', lod_index=-1)]))
    # VER2 by hand — ImgWriter never repeats a name.
    recs = [('a.dff', b'X' * 1000), ('pal.txd', b'PAL' + b'.' * 100),
            ('bad.txd', b'BAD' + b'.' * 100),
            ('lan_stream0.ipl', stream(100)), ('lan_stream0.ipl', stream(101))]
    first = -(-(8 + len(recs) * 32) // core_img.SECTOR)
    head, body, off = b'VER2' + struct.pack('<I', len(recs)), b'', first
    for name, data in recs:
        sz = -(-len(data) // core_img.SECTOR)
        head += struct.pack('<IHH', off, sz, 0) + name.encode().ljust(24, b'\0')
        body += data.ljust(sz * core_img.SECTOR, b'\0')
        off += sz
    with open(game.gta3, 'wb') as f:
        f.write(head.ljust(first * core_img.SECTOR, b'\0') + body)

    op, _msg = _extract(game, 'LA')
    assert op._tex_count == 1
    assert os.path.isfile(os.path.join(game.cache, 'textures', 'pal.png'))
    assert op._skip_reasons['archive_filtered'] == 1
    assert not os.path.isfile(os.path.join(game.cache, '_txd_errors.log'))


def test_smaller_texture_landing_last_is_redone_next_run(game, monkeypatch):
    """Two TXDs of one archive hold a texture of one name and decode side
    by side: both find no PNG and the smaller one lands last. The larger
    TXD loses its stamp, so the next run decodes it again and keeps the
    larger PNG (as before the index)."""
    import time
    if (os.cpu_count() or 4) < 2:
        pytest.skip('one worker thread: TXDs decode one after another')
    with core_img.ImgWriter(game.gta3) as w:
        w.add('big.txd', b'BIG' + b'.' * 100)
        w.add('small.txd', b'SML' + b'.' * 100)

    def read_txd(data):
        n = {b'BIG': 2, b'SML': 1}.get(bytes(data[:3]))
        if n is None:
            return _fake_read_txd(data)
        return [types.SimpleNamespace(name='dup', width=n, height=n, platform_id=9,
                                      raster_format=0x0500, pixels=b'\x01' * (4 * n * n))]

    def write_png(path, pixels, w, h):
        if os.path.basename(path) == 'dup.png':  # both checked, smaller last
            time.sleep(0.1 if w == 2 else 0.3)
        _fake_write_png(path, pixels, w, h)

    monkeypatch.setattr(MODS['INU_tools.core.txd'], 'read_txd', read_txd)
    monkeypatch.setattr(MODS['INU_tools'], '_write_png', write_png)
    load_index = MODS['INU_tools.core.map_files'].load_index
    png = os.path.join(game.cache, 'textures', 'dup.png')
    _extract(game)
    assert img_ops._read_png_dimensions(png) == (1, 1)
    txd = load_index(game.cache)['txd']
    assert 'big.txd' not in txd and 'small.txd' in txd
    op, _msg = _extract(game)
    assert img_ops._read_png_dimensions(png) == (2, 2) and op._tex_count == 1
    assert 'big.txd' in load_index(game.cache)['txd']
    op, _msg = _extract(game)
    assert op._tex_count == 0


def test_name_in_two_archives_comes_from_the_first(game):
    mods = os.path.join(game.root, 'mods')
    os.makedirs(mods)
    other = os.path.join(mods, 'aaa.img')        # alphabetically first, but
    core_img.create_img(other)                   # not an archive of the game
    with core_img.ImgWriter(other) as w:
        w.add('a.dff', b'Z' * 1000)
        w.add('b.dff', b'B' * 1000)
    op, msg = _extract(game)
    assert _read(os.path.join(game.cache, 'a.dff')).startswith(b'X')
    assert _read(os.path.join(game.cache, 'b.dff')).startswith(b'B')
    assert op._img_paths[0] == game.gta3 and op._multi == 1
    assert 'файлов в нескольких архивах' in msg
