"""core/map_files.py — the IPL set of a map region (Scan / Import Map /
Extract), LOD links of streamed IPLs, archive load order and the extract
cache index (which archive record the cached file came from).

Pure Python."""

from pathlib import Path
import os
import struct
import sys
import types


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core import map_files as mf  # noqa: E402
from core.img import (  # noqa: E402
    SECTOR, ImgWriter, create_img, read_directory,
)
from core.ipl import (  # noqa: E402
    IplFile, IplInstance, _write_binary_ipl, lod_instance_indices,
)


def _e(name, offset=0, size=1):
    return types.SimpleNamespace(name=name, offset=offset, size=size)


def _raw_img(path, records):
    """VER2 archive written by hand — ImgWriter never repeats a name.
    records: [(name, bytes)], each padded to whole sectors."""
    n = len(records)
    first = -(-(8 + n * 32) // SECTOR)
    head, body, off = b'VER2' + struct.pack('<I', n), b'', first
    for name, data in records:
        sz = -(-len(data) // SECTOR)
        head += struct.pack('<IHH', off, sz, 0) + name.encode().ljust(24, b'\0')
        body += data.ljust(sz * SECTOR, b'\0')
        off += sz
    with open(path, 'wb') as f:
        f.write(head.ljust(first * SECTOR, b'\0') + body)


# ── region of an IPL ─────────────────────────────────────────────

def test_region_match_folder_and_name():
    assert mf.region_match(r'DATA\MAPS\COUNTRY\countn2.ipl', 'COUNTRY')
    assert not mf.region_match(r'DATA\MAPS\LA\LAn2.ipl', 'COUNTRY')
    assert mf.region_match(r'DATA\MAPS\vegas\vegasN.IPL', 'VEGAS')
    # no region folder after maps → the file name decides
    assert mf.region_match(r'data\maps\LAx.ipl', 'LA')
    assert not mf.region_match(r'data\maps\x.ipl', 'LA')
    assert mf.region_match(r'DATA\MAPS\LA\LAn.ipl', 'ALL')


def _maps(*parts):
    return os.path.join('g', 'DATA', 'MAPS', *parts)


def _dirs(**names):
    return {a: [_e(n, i) for i, n in enumerate(ns)] for a, ns in names.items()}


def _na(binary):
    return [(n, a) for n, a, _e in binary]


def test_region_files_country_takes_streams_of_its_text_ipls():
    text = [_maps('COUNTRY', 'countn2.ipl'), _maps('LA', 'LAn2.ipl')]
    dirs = _dirs(
        gta3=['countn2_stream0.ipl', 'countn2_stream1.ipl',
              'lan2_stream0.ipl', 'barriers1.ipl'],
        mod=['countn2_stream0.ipl'],
    )
    t, b = mf.region_files(text, ['gta3', 'mod'], 'COUNTRY', dirs.__getitem__)
    assert t == [text[0]]
    # the second copy (mod) is skipped, the mission IPL is not linked
    assert _na(b) == [('countn2_stream0.ipl', 'gta3'),
                      ('countn2_stream1.ipl', 'gta3')]
    assert b[0][2] is dirs['gta3'][0]


def test_region_files_interior_streams_from_gta_int():
    text = [_maps('interior', 'int_LA.ipl'), _maps('LA', 'LAn.ipl')]
    dirs = _dirs(gta3=['lan_stream0.ipl'], gta_int=['int_la_stream0.ipl'])
    t, b = mf.region_files(text, ['gta3', 'gta_int'], 'INTERIOR',
                           dirs.__getitem__)
    assert t == [text[0]]
    assert _na(b) == [('int_la_stream0.ipl', 'gta_int')]


def test_region_files_all_and_duplicate_text():
    text = [_maps('LA', 'LAn.ipl'), _maps('LA', 'LAn.ipl')]
    t, b = mf.region_files(text, ['a'], 'ALL',
                           lambda a: [_e('LAn_stream0.ipl')])
    assert t == [text[0]]
    assert _na(b) == [('LAn_stream0.ipl', 'a')]


def test_region_files_stream_record_the_game_takes():
    """First record inside an archive; an emptied record (size 0) does not
    hold the name — the next one with data does (GetCdPosnAndSize)."""
    text = [_maps('COUNTRY', 'countn2.ipl')]
    dirs = {
        'gta3': [_e('countn2_stream0.ipl', 10, size=0),
                 _e('countn2_stream1.ipl', 11), _e('countn2_stream1.ipl', 12)],
        'mod': [_e('countn2_stream0.ipl', 20)],
    }
    _t, b = mf.region_files(text, ['gta3', 'mod'], 'COUNTRY', dirs.__getitem__)
    assert [(n, a, e.offset) for n, a, e in b] == [
        ('countn2_stream0.ipl', 'mod', 20), ('countn2_stream1.ipl', 'gta3', 11)]


def test_repeated_stream_ipl_is_read_by_its_first_record(tmp_path):
    # An IMG tool appended a second lan_stream0.ipl and left the old one:
    # Import Map / Extract read the record the game streams (the first).
    def blob(mid):
        return _write_binary_ipl(IplFile(instances=[
            IplInstance(model_id=mid, model_name='', lod_index=-1)]))
    p = str(tmp_path / 'gta3.img')
    _raw_img(p, [('lan_stream0.ipl', blob(7)), ('lan_stream0.ipl', blob(9))])
    _t, b = mf.region_files([_maps('LA', 'LAn.ipl')], [p], 'LA', read_directory)
    with open(p, 'rb') as fh:
        ipl = mf.read_ipl_bytes(mf.read_entry(fh, b[0][2]))
    assert [i.model_id for i in ipl.instances] == [7]


def test_region_relative_to_game_root(tmp_path):
    # The install lives in a folder named «Maps»: only the path inside the
    # game folder may decide the region.
    root = os.path.join(str(tmp_path), 'Maps', 'GTA SA')
    p = os.path.join(root, 'DATA', 'MAPS', 'LA', 'LAn.IPL')
    assert mf.region_files([p], [], 'LA', lambda a: [], root)[0] == [p]
    assert mf.region_files([p], [], 'LA', lambda a: [])[0] == []


# ── LOD of streamed IPLs ─────────────────────────────────────────

def test_binary_stem():
    assert mf.binary_stem('LAe_stream3.ipl') == 'lae'
    assert mf.binary_stem('countn2_stream0.ipl') == 'countn2'
    assert mf.binary_stem('COUNTN2_STREAM12.IPL') == 'countn2'
    assert mf.binary_stem('foo.ipl') is None
    assert mf.binary_stem('barriers1.ipl') is None


def test_rebase_binary_lod():
    assert mf.rebase_binary_lod(5, (100, 10)) == 105
    assert mf.rebase_binary_lod(12, (100, 10)) == -1
    assert mf.rebase_binary_lod(-1, (100, 10)) == -1
    assert mf.rebase_binary_lod(3, None) == -1


def test_streamed_lod_points_into_text_ipl():
    """lod_index of a streamed row → the row of its text IPL (the game takes
    the LOD from the related text IPL), not a row of the stream itself."""
    instances = [IplInstance(model_id=100 + i, model_name='m%d' % i, lod_index=-1)
                 for i in range(3)]
    text_base = {'lan2': (0, 3)}
    blob = _write_binary_ipl(IplFile(instances=[
        IplInstance(model_id=7, model_name='', lod_index=-1),
        IplInstance(model_id=8, model_name='', lod_index=1),
        IplInstance(model_id=9, model_name='', lod_index=5),  # past the text IPL
    ]))
    parsed = mf.read_ipl_bytes(blob)
    tb = text_base.get(mf.binary_stem('lan2_stream0.ipl'))
    for inst in parsed.instances:
        inst.lod_index = mf.rebase_binary_lod(inst.lod_index, tb)
        instances.append(inst)
    assert [i.lod_index for i in instances[3:]] == [-1, 1, -1]
    assert lod_instance_indices(instances) == {1}     # m1 of the text IPL


def test_read_ipl_bytes_text_record():
    data = b'inst\n100, foo, 0, 1, 2, 3, 0, 0, 0, 1, -1\nend\n'
    ipl = mf.read_ipl_bytes(data.ljust(SECTOR, b'\0'))
    assert [(i.model_id, i.model_name) for i in ipl.instances] == [(100, 'foo')]


# ── archives ─────────────────────────────────────────────────────

def test_order_archives_game_order_first():
    root = os.path.join('C:' + os.sep, 'g')
    j = lambda *p: os.path.join(root, *p)  # noqa: E731
    paths = [j('mods', 'zz.img'), j('models', 'gta_int.img'), j('mods', 'aa.img'),
             j('models', 'cutscene.img'), j('models', 'gta3.img'),
             j('MODELS', 'GTA3.IMG') if os.name == 'nt' else j('models', 'gta3.img')]
    out = mf.order_archives(paths, root, [j('models', 'cutscene.img')])
    assert out == [j('models', 'gta3.img'), j('models', 'gta_int.img'),
                   j('models', 'cutscene.img'), j('mods', 'aa.img'),
                   j('mods', 'zz.img')]


def test_game_archives_on_disk(tmp_path):
    root = str(tmp_path / 'game')
    for rel in ('models/gta3.img', 'models/gta_int.img', 'models/cutscene.img',
                'mods/aa.img', 'mods/zz.img', '.inu_cache/junk.img'):
        p = os.path.join(root, *rel.split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').close()
    j = lambda *p: os.path.join(root, *p)  # noqa: E731
    out = mf.game_archives(root, [j('models', 'cutscene.img')], j('mods', 'zz.img'))
    # gta3, gta_int, IMG of gta.dat, the panel's IMG, the rest alphabetically
    assert out == [j('models', 'gta3.img'), j('models', 'gta_int.img'),
                   j('models', 'cutscene.img'), j('mods', 'zz.img'),
                   j('mods', 'aa.img')]
    # an empty panel path adds nothing (os.path.abspath('') would be cwd)
    assert len(mf.game_archives(root, [], '')) == 5


def _game_dir(tmp_path, dat, text, rels):
    root = str(tmp_path / 'game')
    os.makedirs(os.path.join(root, 'data'))
    with open(os.path.join(root, 'data', dat), 'w') as f:
        f.write(text)
    for rel in rels:
        p = os.path.join(root, *rel.split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').close()
    return root, (lambda *p: os.path.join(root, *p))


def _nc(paths):
    return [os.path.normcase(os.path.normpath(p)) for p in paths]


def test_game_archives_vc_last_cdimage_wins(tmp_path):
    # The Import tab's order (gta_dat.img_load_order): VC walks CDIMAGE
    # backwards — mod.img above gta3.img; a line below the first IPL is
    # never read; the panel's IMG right after the .dat ones.
    root, j = _game_dir(tmp_path, 'gta_vc.dat',
                        'CDIMAGE models\\mod.img\nIPL data\\x.ipl\n'
                        'CDIMAGE models\\late.img\n',
                        ('models/gta3.img', 'models/mod.img',
                         'models/late.img', 'mods/aa.img', 'mods/zz.img'))
    out = mf.game_archives(root, [], j('mods', 'zz.img'))
    assert _nc(out) == _nc([j('models', 'mod.img'), j('models', 'gta3.img'),
                            j('mods', 'zz.img'), j('models', 'late.img'),
                            j('mods', 'aa.img')])


def test_game_archives_sa_unread_dat_lines_not_ranked(tmp_path):
    # SA: IMG lines of gta.dat below the first IPL and of gta_int.dat are
    # not read by the game — no rank of their own, the panel's IMG first.
    root, j = _game_dir(tmp_path, 'gta.dat',
                        'IMG models\\a.img\nIPL data\\x.ipl\nIMG models\\b.img\n',
                        ('models/gta3.img', 'models/gta_int.img',
                         'models/a.img', 'models/b.img', 'models/c.img',
                         'mods/zz.img'))
    out = mf.game_archives(root, [j('models', 'a.img'), j('models', 'b.img'),
                                  j('models', 'c.img')], j('mods', 'zz.img'))
    assert _nc(out) == _nc([j('models', 'gta3.img'), j('models', 'gta_int.img'),
                            j('models', 'a.img'), j('mods', 'zz.img'),
                            j('models', 'b.img'), j('models', 'c.img')])


# ── which record the game streams ────────────────────────────────

def test_extract_winners_first_archive_and_non_empty():
    dirs = {
        'a': [_e('x.dff', 10), _e('e.dff', 11, size=0), _e('x.DFF', 12),
              _e('t.txd', 13), _e('n.ifp', 14)],
        'b': [_e('x.dff', 20), _e('e.dff', 21), _e('y.col', 22)],
    }
    multi = set()
    win = mf.extract_winners(['a', 'b'], dirs.__getitem__, multi=multi)
    assert sorted(win) == ['e.dff', 't.txd', 'x.dff', 'y.col']
    assert win['x.dff'][0] == 'a' and win['x.dff'][1].offset == 10
    # an empty record holds its name only while nothing has data
    assert win['e.dff'][0] == 'b'
    assert multi == {'x.dff', 'e.dff'}


def test_duplicate_inside_archive_reads_first_record(tmp_path):
    p = str(tmp_path / 'dup.img')
    _raw_img(p, [('a.dff', b'A' * 100), ('a.dff', b'B' * 100)])
    win = mf.extract_winners([p], read_directory)
    with open(p, 'rb') as fh:
        data = mf.read_entry(fh, win['a.dff'][1])
    assert data.startswith(b'A')


# ── extract cache index ──────────────────────────────────────────

def _game(tmp_path):
    img = str(tmp_path / 'gta3.img')
    create_img(img)
    with ImgWriter(img) as w:
        w.add('a.dff', b'X' * 1000)
        w.add('b.col', b'C' * 3000)
        w.add('t.txd', b'T' * 500)
    cdir = tmp_path / 'cache'
    cdir.mkdir()
    return img, str(cdir)


def _run(img, cdir, idx, want_txd=None):
    """One Extract pass the way the operator does it (DFF/COL only);
    returns (plan, files written)."""
    win = mf.extract_winners([img], read_directory)
    have = {n.lower() for n in os.listdir(cdir)}
    states = {img: mf.archive_state(img)}
    plan = mf.plan_extract(win, idx, states, have, set(), want_txd)
    written = []
    with open(img, 'rb') as fh:
        for k, e in plan['files'].get(img, []):
            if mf.refresh_file(fh, img, k, e, os.path.join(cdir, e.name),
                               idx.setdefault('files', {})):
                written.append(k)
    mf.finish_archive(idx, img, states[img],
                      [k for k, _e in plan['filtered'].get(img, [])])
    return plan, written


def test_plan_first_run_writes_everything(tmp_path):
    img, cdir = _game(tmp_path)
    idx = {}
    plan, written = _run(img, cdir, idx)
    assert sorted(written) == ['a.dff', 'b.col']
    assert [k for k, _e in plan['txd'][img]] == ['t.txd']
    assert open(os.path.join(cdir, 'a.dff'), 'rb').read().startswith(b'X')
    assert idx['files']['a.dff'][0] == os.path.abspath(img)


def test_plan_unchanged_archive_reads_nothing(tmp_path):
    img, cdir = _game(tmp_path)
    idx = {}
    _run(img, cdir, idx)
    idx['txd'] = {'t.txd': mf.entry_stamp(img, mf.extract_winners(
        [img], read_directory)['t.txd'][1], 0)}
    idx['txd_png'] = {'t.txd': []}
    plan, written = _run(img, cdir, idx)
    assert plan['files'] == {} and plan['txd'] == {} and written == []
    assert plan['same'] == 3


def test_replace_in_place_same_length_is_rewritten(tmp_path):
    img, cdir = _game(tmp_path)
    idx = {}
    _run(img, cdir, idx)
    before = {e.name: (e.offset, e.size) for e in read_directory(img)}
    st = os.stat(img)
    with ImgWriter(img) as w:                 # vertex-only edit: same size
        w.add('a.dff', b'Y' * 1000)
    os.utime(img, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    assert {e.name: (e.offset, e.size) for e in read_directory(img)} == before
    plan, written = _run(img, cdir, idx)
    # the changed archive is checked record by record; only a.dff differs
    assert sorted(k for k, _e in plan['files'][img]) == ['a.dff', 'b.col']
    assert written == ['a.dff']
    assert open(os.path.join(cdir, 'a.dff'), 'rb').read().startswith(b'Y')


def test_deleted_cache_file_comes_back(tmp_path):
    img, cdir = _game(tmp_path)
    idx = {}
    _run(img, cdir, idx)
    os.remove(os.path.join(cdir, 'b.col'))
    plan, written = _run(img, cdir, idx)
    assert written == ['b.col']


def test_foreign_stamp_is_not_trusted(tmp_path):
    img, cdir = _game(tmp_path)
    idx = {}
    _run(img, cdir, idx)
    e = mf.extract_winners([img], read_directory)['a.dff'][1]
    # INU Max 0.28 stamps: [archive, offset, size] — no CRC
    idx['files']['a.dff'] = [img, e.offset, e.size]
    plan, written = _run(img, cdir, idx)
    assert written == ['a.dff']
    assert len(idx['files']['a.dff']) == 4


def test_cached_ok_rules():
    e = _e('a.dff', 5, 2)
    s = mf.entry_stamp('A.img', e, 77)
    assert mf.cached_ok(s, 'A.img', e, archive_same=True)
    assert not mf.cached_ok(s, 'A.img', e, archive_same=False)
    assert mf.cached_ok(s, 'A.img', e, crc=77)
    assert not mf.cached_ok(s, 'A.img', e, crc=78)
    assert not mf.cached_ok(s, 'B.img', e, crc=77)
    assert not mf.cached_ok(s, 'A.img', _e('a.dff', 6, 2), crc=77)
    assert not mf.cached_ok(s, 'A.img', e, crc=77, have_output=False)
    assert not mf.cached_ok(None, 'A.img', e, archive_same=True)


def test_region_run_on_changed_archive_drops_filtered_txd_stamps(tmp_path):
    idx = {'txd': {'t.txd': ['x', 0, 1, 2], 'u.txd': ['x', 0, 1, 2]},
           'archives': {mf.archive_key('A.img'): [1, 1]}}
    mf.finish_archive(idx, 'A.img', [1, 1], ['t.txd'])     # unchanged
    assert 't.txd' in idx['txd']
    mf.finish_archive(idx, 'A.img', [2, 2], ['t.txd'])     # changed
    assert 't.txd' not in idx['txd'] and 'u.txd' in idx['txd']
    assert idx['archives'][mf.archive_key('A.img')] == [2, 2]


def test_region_filter_keeps_txd_out_of_the_plan(tmp_path):
    img, cdir = _game(tmp_path)
    plan, _w = _run(img, cdir, {}, want_txd={'other'})
    assert plan['txd'] == {}
    assert [k for k, _e in plan['filtered'][img]] == ['t.txd']


# ── texture part of the index ────────────────────────────────────

def test_reset_tex_index_new_decode_version():
    idx = {'txd': {'t.txd': [1]}, 'txd_png': {'t.txd': ['a.png']}}
    stale = mf.reset_tex_index(idx, {'a.png', 'b.png'})
    assert idx['txd'] == {} and idx['txd_png'] == {}
    assert stale == {'a.png', 'b.png'} and idx['tex_ver'] == mf.TEX_VER


def test_reset_tex_index_empty_textures_folder():
    idx = {'tex_ver': mf.TEX_VER, 'txd': {'t.txd': [1]}, 'tex_stale': []}
    mf.reset_tex_index(idx, set())
    assert idx['txd'] == {}
    idx = {'tex_ver': mf.TEX_VER, 'txd': {'t.txd': [1]}}
    mf.reset_tex_index(idx, {'a.png'})
    assert idx['txd'] == {'t.txd': [1]}


def test_txd_outputs_present():
    idx = {'txd_png': {'t.txd': ['a.png', 'b.png'], 'e.txd': []}}
    assert mf.txd_outputs_present(idx, 't.txd', {'a.png', 'b.png'})
    assert not mf.txd_outputs_present(idx, 't.txd', {'a.png'})
    assert mf.txd_outputs_present(idx, 'e.txd', set())
    assert not mf.txd_outputs_present(idx, 'x.txd', {'a.png'})


def test_index_round_trip_keeps_max_keys(tmp_path):
    cdir = str(tmp_path)
    assert mf.load_index(cdir) == {}
    idx = {'files': {'a.dff': ['A.img', 1, 2, 3]}, 'txd': {},
           'tex_ver': 2, 'tex_stale': ['x.png']}
    mf.save_index(cdir, idx)
    back = mf.load_index(cdir)
    assert back == idx
    back['files']['b.col'] = ['A.img', 4, 5, 6]
    mf.save_index(cdir, back)
    again = mf.load_index(cdir)
    assert again['tex_stale'] == ['x.png'] and again['tex_ver'] == 2
    assert not os.path.exists(os.path.join(cdir, mf.INDEX_NAME + '.tmp'))


def test_load_index_survives_damage(tmp_path):
    p = tmp_path / mf.INDEX_NAME
    p.write_text('{broken', encoding='utf-8')
    assert mf.load_index(str(tmp_path)) == {}
    p.write_text('{"files": [1, 2]}', encoding='utf-8')
    assert mf.load_index(str(tmp_path))['files'] == {}
