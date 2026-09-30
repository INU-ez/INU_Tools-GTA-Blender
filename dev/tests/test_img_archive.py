"""Round-trip tests for core/img.py — IMG v2 archive create/add/replace/
remove/extract via batch ImgWriter and one-shot replace_or_add.

Pure Python."""

from pathlib import Path
import sys
import os


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.img import (  # noqa: E402
    SECTOR,
    create_img,
    list_files,
    read_directory,
    extract_file,
    replace_or_add,
    remove_file,
    sectors_needed,
    ImgReader,
    ImgWriter,
    rebuild_img,
    IMG_VERSION_1,
    _sibling_dir_path,
)
import core.img as img_module  # noqa: E402
import pytest  # noqa: E402


def _make_payload(size: int, fill: bytes = b'X') -> bytes:
    return (fill * size)[:size]


# ── sectors_needed math ──────────────────────────────────────────

def test_sectors_needed_round_up():
    assert sectors_needed(0) == 0
    assert sectors_needed(1) == 1
    assert sectors_needed(SECTOR) == 1
    assert sectors_needed(SECTOR + 1) == 2
    assert sectors_needed(2 * SECTOR) == 2


# ── Empty archive ────────────────────────────────────────────────

def test_create_empty(tmp_path):
    p = tmp_path / "empty.img"
    create_img(str(p))
    assert p.exists()
    assert read_directory(str(p)) == []
    assert list_files(str(p)) == []


# ── Single-file add via replace_or_add ───────────────────────────

def test_add_single_file(tmp_path):
    p = tmp_path / "one.img"
    create_img(str(p))
    payload = _make_payload(500, fill=b'A')
    status = replace_or_add(str(p), "test.dff", payload)
    assert status == 'added'

    files = list_files(str(p))
    assert len(files) == 1
    assert files[0].lower() == "test.dff"

    # Extract back, strip padding, compare
    extracted = extract_file(str(p), "test.dff")
    assert extracted is not None
    assert extracted[:500] == payload  # padding may follow


# ── Replace in place (fits in old slot) ──────────────────────────

def test_replace_in_place(tmp_path):
    p = tmp_path / "rep.img"
    create_img(str(p))
    replace_or_add(str(p), "data.col", _make_payload(SECTOR * 3, fill=b'A'))

    # New data fits — should reuse existing sectors
    new_data = _make_payload(SECTOR * 2, fill=b'B')
    status = replace_or_add(str(p), "data.col", new_data)
    assert status == 'replaced'

    extracted = extract_file(str(p), "data.col")
    assert extracted is not None
    assert extracted[:len(new_data)] == new_data


# ── Replace overflow (forces append) ─────────────────────────────

def test_replace_overflow_appends(tmp_path):
    p = tmp_path / "over.img"
    create_img(str(p))
    replace_or_add(str(p), "small.dff", _make_payload(100, fill=b'A'))

    # New data doesn't fit — must append
    bigger = _make_payload(SECTOR * 4, fill=b'B')
    status = replace_or_add(str(p), "small.dff", bigger)
    assert status == 'replaced'

    extracted = extract_file(str(p), "small.dff")
    assert extracted is not None
    assert extracted[:len(bigger)] == bigger


# ── Remove file ──────────────────────────────────────────────────

def test_remove_file(tmp_path):
    p = tmp_path / "rm.img"
    create_img(str(p))
    replace_or_add(str(p), "a.dff", _make_payload(100, fill=b'A'))
    replace_or_add(str(p), "b.dff", _make_payload(200, fill=b'B'))
    replace_or_add(str(p), "c.dff", _make_payload(300, fill=b'C'))

    assert remove_file(str(p), "b.dff") is True
    files = {n.lower() for n in list_files(str(p))}
    assert "a.dff" in files
    assert "b.dff" not in files
    assert "c.dff" in files


def test_remove_nonexistent_returns_false(tmp_path):
    p = tmp_path / "miss.img"
    create_img(str(p))
    assert remove_file(str(p), "nothing.dff") is False


# ── Case-insensitive lookup ──────────────────────────────────────

def test_case_insensitive_lookup(tmp_path):
    p = tmp_path / "case.img"
    create_img(str(p))
    replace_or_add(str(p), "House01.DFF", _make_payload(100, fill=b'X'))

    assert extract_file(str(p), "house01.dff") is not None
    assert extract_file(str(p), "HOUSE01.DFF") is not None


# ── ImgReader context manager ────────────────────────────────────

def test_reader_keeps_archive_open(tmp_path):
    p = tmp_path / "reader.img"
    create_img(str(p))
    replace_or_add(str(p), "a.dff", _make_payload(100, fill=b'A'))
    replace_or_add(str(p), "b.dff", _make_payload(200, fill=b'B'))

    with ImgReader(str(p)) as r:
        assert len(r.entries) == 2
        a = r.read("a.dff")
        b = r.read("b.dff")
        assert a is not None and a[:100] == b'A' * 100
        assert b is not None and b[:200] == b'B' * 200
        # Missing returns None, not exception
        assert r.read("ghost.dff") is None


def test_reader_extract_all_to_dir(tmp_path):
    p = tmp_path / "batch.img"
    create_img(str(p))
    replace_or_add(str(p), "a.dff", _make_payload(100, fill=b'A'))
    replace_or_add(str(p), "b.col", _make_payload(200, fill=b'B'))
    replace_or_add(str(p), "c.txd", _make_payload(300, fill=b'C'))
    replace_or_add(str(p), "d.bin", _make_payload(50, fill=b'D'))

    out = tmp_path / "extracted"
    with ImgReader(str(p)) as r:
        counts = r.extract_all_to(str(out))

    assert counts['dff'] == 1
    assert counts['col'] == 1
    assert counts['txd'] == 1
    assert counts['other'] == 1
    assert (out / "a.dff").exists()
    assert (out / "b.col").exists()


def test_reader_extract_filtered_by_extension(tmp_path):
    p = tmp_path / "filt.img"
    create_img(str(p))
    replace_or_add(str(p), "a.dff", _make_payload(100, fill=b'A'))
    replace_or_add(str(p), "b.col", _make_payload(200, fill=b'B'))
    replace_or_add(str(p), "c.txd", _make_payload(300, fill=b'C'))

    out = tmp_path / "dffonly"
    with ImgReader(str(p)) as r:
        counts = r.extract_all_to(str(out), extensions={'.dff'})

    assert counts['dff'] == 1
    assert counts['col'] == 0
    assert counts['txd'] == 0
    assert (out / "a.dff").exists()
    assert not (out / "b.col").exists()


# ── ImgWriter batch mode ─────────────────────────────────────────

def test_writer_batch_add(tmp_path):
    """Writer should write directory exactly once at __exit__, not per-add."""
    p = tmp_path / "batch.img"
    create_img(str(p))

    with ImgWriter(str(p)) as w:
        for i in range(20):
            w.add(f"file{i:02d}.dff", _make_payload(100 + i, fill=bytes([0x40 + i])))

    files = list_files(str(p))
    assert len(files) == 20
    # Verify a few survived intact
    assert extract_file(str(p), "file00.dff")[:100] == b'@' * 100
    assert extract_file(str(p), "file19.dff")[:119] == bytes([0x40 + 19]) * 119


def test_writer_replace_and_add_mixed(tmp_path):
    """First populate, then re-open with writer to replace some + add new."""
    p = tmp_path / "mixed.img"
    create_img(str(p))
    replace_or_add(str(p), "old1.dff", _make_payload(SECTOR * 3, fill=b'A'))
    replace_or_add(str(p), "old2.dff", _make_payload(SECTOR * 3, fill=b'B'))

    with ImgWriter(str(p)) as w:
        # Replace fits in slot
        w.add("old1.dff", _make_payload(SECTOR, fill=b'X'))
        # Replace overflows
        w.add("old2.dff", _make_payload(SECTOR * 5, fill=b'Y'))
        # Net new
        w.add("new1.dff", _make_payload(100, fill=b'Z'))

    files = {n.lower() for n in list_files(str(p))}
    assert files == {"old1.dff", "old2.dff", "new1.dff"}

    assert extract_file(str(p), "old1.dff")[:SECTOR] == b'X' * SECTOR
    assert extract_file(str(p), "old2.dff")[:SECTOR * 5] == b'Y' * (SECTOR * 5)
    assert extract_file(str(p), "new1.dff")[:100] == b'Z' * 100


# ── Directory layout invariants ──────────────────────────────────

def test_directory_offsets_are_sector_aligned(tmp_path):
    p = tmp_path / "align.img"
    create_img(str(p))
    for i in range(5):
        replace_or_add(str(p), f"f{i}.dff", _make_payload(SECTOR + 17 + i,
                                                          fill=bytes([0x60 + i])))

    entries = read_directory(str(p))
    assert len(entries) == 5
    # No entry overlaps the next entry's start
    sorted_e = sorted(entries, key=lambda e: e.offset)
    for prev, nxt in zip(sorted_e, sorted_e[1:]):
        assert prev.offset + prev.size <= nxt.offset, (
            f"{prev.name} overlaps {nxt.name}: "
            f"{prev.offset}+{prev.size} > {nxt.offset}")


# ── Same-name records: the one the game streams wins ─────────────

def _make_archive(p: str, records, version: int = 2) -> None:
    """Archive with ``records`` [(name, data)] written as is — duplicate
    names and empty entries kept."""
    create_img(p, version=version)
    with ImgWriter(p, version=version) as w:
        for name, data in records:
            w.append_entry(name, data)


@pytest.mark.parametrize("version", [2, 1])
def test_duplicate_name_first_record_wins(tmp_path, version):
    """The game skips a name already registered (LoadCdDirectory) — read,
    extract, add and extract_all_to all use the FIRST record."""
    p = str(tmp_path / "dup.img")
    _make_archive(p, [("a.dff", b'A' * SECTOR), ("a.dff", b'B' * SECTOR)],
                  version)
    with ImgReader(p) as r:
        assert r.read("a.dff")[:1] == b'A'
    assert extract_file(p, "a.dff")[:1] == b'A'

    # Grows past its slot → appended after the second record.
    with ImgWriter(p) as w:
        assert w.add("a.dff", b'Z' * (2 * SECTOR)) == 'replaced'
    d = read_directory(p)
    assert [e.name for e in d] == ["a.dff", "a.dff"]
    assert d[0].size == 2
    with ImgReader(p) as r:
        assert r.read_entry(d[0]) == b'Z' * (2 * SECTOR)
        assert r.read_entry(d[1]) == b'B' * SECTOR

    out = tmp_path / "out"
    with ImgReader(p) as r:
        counts = r.extract_all_to(str(out), skip_existing=True)
    assert counts['dff'] == 1
    assert (out / "a.dff").read_bytes()[:1] == b'Z'


@pytest.mark.parametrize("version", [2, 1])
def test_empty_record_does_not_take_the_name(tmp_path, version):
    """A size-0 record doesn't register the name (GetCdPosnAndSize is false
    while size is 0) — the game streams the next same-name record."""
    p = str(tmp_path / "empty_first.img")
    _make_archive(p, [("a.dff", b''), ("a.dff", b'X' * SECTOR),
                      ("c.dff", b'C' * 100), ("e.dff", b''), ("e.dff", b'')],
                  version)
    with ImgReader(p) as r:
        assert r.read("a.dff")[:1] == b'X'
        assert r.read("e.dff") == b''
    assert extract_file(p, "a.dff")[:1] == b'X'
    assert extract_file(p, "e.dff") == b''

    with ImgWriter(p) as w:
        w.add("a.dff", b'Y' * 10)
    d = read_directory(p)
    assert d[0].size == 0
    with ImgReader(p) as r:
        assert r.read_entry(d[1])[:10] == b'Y' * 10

    out = tmp_path / "out"
    with ImgReader(p) as r:
        r.extract_all_to(str(out))
    assert (out / "a.dff").read_bytes()[:10] == b'Y' * 10


# ── rebuild_img ──────────────────────────────────────────────────

@pytest.mark.parametrize("version", [2, 1])
def test_rebuild_keeps_duplicates_and_empty_records(tmp_path, version):
    p = str(tmp_path / "rb.img")
    _make_archive(p, [("a.dff", b'A' * SECTOR), ("a.dff", b'B' * (2 * SECTOR)),
                      ("e.dff", b''), ("c.dff", b'C' * 100)], version)
    with ImgWriter(p) as w:         # dead space: old c.dff slot stays behind
        w.add("c.dff", b'D' * (3 * SECTOR))
    before = [(e.name, e.size) for e in read_directory(p)]
    with ImgReader(p) as r:
        data_before = [r.read_entry(e) for e in r.entries]

    first = rebuild_img(p)
    assert first['entries'] == 4
    assert first['saved'] >= SECTOR
    second = rebuild_img(p)         # nothing left over from the first run
    assert second['entries'] == 4

    assert [(e.name, e.size) for e in read_directory(p)] == before
    with ImgReader(p) as r:
        assert r.version == version
        assert [r.read_entry(e) for e in r.entries] == data_before
    tmp = p + '.rebuild_tmp'
    assert not os.path.exists(tmp)
    assert not os.path.exists(_sibling_dir_path(tmp))


@pytest.mark.parametrize("version", [2, 1])
def test_rebuild_failure_leaves_original_intact(tmp_path, monkeypatch,
                                                version):
    p = str(tmp_path / "fail.img")
    _make_archive(p, [("a.dff", b'A' * 100), ("b.dff", b'B' * 100)], version)
    files = [p] + ([_sibling_dir_path(p)] if version == IMG_VERSION_1 else [])
    snapshot = {f: Path(f).read_bytes() for f in files}

    def boom(self, name, data):
        raise RuntimeError("disk full")

    monkeypatch.setattr(ImgWriter, 'append_entry', boom)
    with pytest.raises(RuntimeError):
        rebuild_img(p)
    tmp = p + '.rebuild_tmp'
    assert not os.path.exists(tmp)
    assert not os.path.exists(_sibling_dir_path(tmp))
    for f, raw in snapshot.items():
        assert Path(f).read_bytes() == raw


def test_rebuild_ver1_dir_swap_failure_keeps_new_directory(tmp_path,
                                                           monkeypatch):
    """VER1: .img already swapped, .dir swap failed (file locked) — the new
    directory (<name>.img.dir) is the only copy: keep it, say what to do,
    and refuse a second Rebuild instead of deleting it."""
    p = str(tmp_path / "gta3.img")
    _make_archive(p, [("a.dff", b'A' * 100), ("b.dff", b'B' * 100)],
                  IMG_VERSION_1)
    with ImgWriter(p) as w:         # moves a.dff → old/new layouts differ
        w.add("a.dff", b'Z' * (2 * SECTOR))
    tmp = p + '.rebuild_tmp'
    tmp_dir = _sibling_dir_path(tmp)
    real_replace = os.replace

    def locked_dir_replace(src, dst):
        if str(dst).lower().endswith('.dir'):
            raise PermissionError(13, "file is locked", str(dst))
        return real_replace(src, dst)

    monkeypatch.setattr(img_module.os, 'replace', locked_dir_replace)
    with pytest.raises(OSError) as ei:
        rebuild_img(p)
    assert tmp_dir in str(ei.value)
    assert os.path.exists(tmp_dir)
    assert not os.path.exists(tmp)

    with pytest.raises(OSError, match="interrupted rebuild"):
        rebuild_img(p)
    assert os.path.exists(tmp_dir)

    # Renaming by hand, as the message says, gives a consistent archive.
    monkeypatch.undo()
    os.replace(tmp_dir, _sibling_dir_path(p))
    assert extract_file(p, "a.dff") == b'Z' * (2 * SECTOR)
    assert extract_file(p, "b.dff")[:100] == b'B' * 100


def _lock(monkeypatch, fn_name, target):
    """os.<fn_name> fails with PermissionError when its path is ``target``."""
    real = getattr(os, fn_name)

    def locked(src, *a, **kw):
        paths = (src,) + a[:1] if fn_name == 'replace' else (src,)
        if any(os.path.normcase(str(x)) == os.path.normcase(target)
               for x in paths):
            raise PermissionError(13, "file is locked", str(target))
        return real(src, *a, **kw)

    monkeypatch.setattr(img_module.os, fn_name, locked)


def test_rebuild_ver1_cleanup_failure_never_leaves_lone_tmp_dir(tmp_path,
                                                                monkeypatch):
    """.img swap failed (game holds it) and the fresh tmp_dir can't be
    removed either — tmp must stay beside it, or the next Rebuild would take
    tmp_dir for "swapped" and advise renaming it next to the OLD .img."""
    p = str(tmp_path / "gta3.img")
    _make_archive(p, [("a.dff", b'A' * 100), ("b.dff", b'B' * 100)],
                  IMG_VERSION_1)
    with ImgWriter(p) as w:         # moves a.dff → old/new layouts differ
        w.add("a.dff", b'Z' * (2 * SECTOR))
    files = [p, _sibling_dir_path(p)]
    snapshot = {f: Path(f).read_bytes() for f in files}
    tmp = p + '.rebuild_tmp'
    tmp_dir = _sibling_dir_path(tmp)

    _lock(monkeypatch, 'replace', p)
    _lock(monkeypatch, 'remove', tmp_dir)
    with pytest.raises(OSError):
        rebuild_img(p)
    assert os.path.exists(tmp_dir)
    assert os.path.exists(tmp)
    for f, raw in snapshot.items():
        assert Path(f).read_bytes() == raw

    monkeypatch.undo()
    rebuild_img(p)                  # the leftover pair is simply cleared
    assert not os.path.exists(tmp)
    assert not os.path.exists(tmp_dir)
    assert extract_file(p, "a.dff") == b'Z' * (2 * SECTOR)
    assert extract_file(p, "b.dff")[:100] == b'B' * 100


def test_rebuild_ver1_stale_pair_cleared_tmp_dir_first(tmp_path,
                                                       monkeypatch):
    """Leftover tmp + tmp_dir from an earlier failed run: tmp_dir is removed
    first, so a failure there keeps tmp and the pair stays recognisable."""
    p = str(tmp_path / "gta3.img")
    _make_archive(p, [("a.dff", b'A' * 100)], IMG_VERSION_1)
    tmp = p + '.rebuild_tmp'
    tmp_dir = _sibling_dir_path(tmp)
    Path(tmp).write_bytes(b'junk')
    Path(tmp_dir).write_bytes(b'junk')

    _lock(monkeypatch, 'remove', tmp_dir)
    with pytest.raises(OSError):
        rebuild_img(p)
    assert os.path.exists(tmp)
    assert os.path.exists(tmp_dir)

    monkeypatch.undo()
    assert rebuild_img(p)['entries'] == 1
    assert not os.path.exists(tmp)
    assert not os.path.exists(tmp_dir)


@pytest.mark.parametrize("version", [2, 1])
def test_extract_all_skips_empty_record_for_later_archive(tmp_path, version):
    """An empty record holds no file — with skip_existing it must not block
    the same name that a later archive has data for."""
    p1 = str(tmp_path / "one.img")
    p2 = str(tmp_path / "two.img")
    _make_archive(p1, [("a.dff", b''), ("c.dff", b'C' * 100)], version)
    _make_archive(p2, [("a.dff", b'X' * 100)], version)
    out = tmp_path / "out"
    for ip in (p1, p2):
        with ImgReader(ip) as r:
            r.extract_all_to(str(out), skip_existing=True)
    assert (out / "a.dff").read_bytes()[:100] == b'X' * 100
    assert (out / "c.dff").read_bytes()[:100] == b'C' * 100


# ── Export to IMG: archive format from the file, names checked up front ──
# The operator (ops/img_ops.py) imports bpy, so its wiring is checked on the
# source; the core behaviour it relies on is checked directly.

import ast  # noqa: E402

import pytest  # noqa: E402

from core.img import (  # noqa: E402
    IMG_VERSION_1,
    IMG_VERSION_2,
    _check_entry_name,
    detect_img_version,
)
from core import game_versions as gv  # noqa: E402

IMG_OPS = ROOT / "INU_tools" / "ops" / "img_ops.py"


def test_autodetected_ver1_writes_into_dir(tmp_path):
    """VER1 archive opened without a pinned version: the entry goes to the
    sibling .dir, the .img gets no VER2 header."""
    p = tmp_path / "gta3.img"
    create_img(str(p), version=IMG_VERSION_1)
    with ImgWriter(str(p)) as w:
        w.add("a.dff", _make_payload(100, fill=b'A'))
    assert detect_img_version(str(p)) == IMG_VERSION_1
    assert [n.lower() for n in list_files(str(p))] == ["a.dff"]
    assert p.read_bytes()[:4] != b'VER2'


def test_autodetected_ver2_ignores_stray_dir(tmp_path):
    """A stray empty .dir next to a VER2 archive doesn't turn it into VER1:
    the entry lands in the VER2 header, the .dir stays empty."""
    p = tmp_path / "gta3.img"
    create_img(str(p))
    stray = tmp_path / "gta3.dir"
    stray.write_bytes(b"")
    assert detect_img_version(str(p)) == IMG_VERSION_2
    with ImgWriter(str(p)) as w:
        w.add("a.dff", _make_payload(100, fill=b'A'))
    head = p.read_bytes()[:8]
    assert head[:4] == b'VER2'
    assert int.from_bytes(head[4:8], 'little') == 1
    assert stray.stat().st_size == 0


def test_img_version_per_game():
    assert gv.profile_for('III').img_version == IMG_VERSION_1
    assert gv.profile_for('VC').img_version == IMG_VERSION_1
    assert gv.profile_for('SA').img_version == IMG_VERSION_2


def test_archive_of_another_game_is_refused(tmp_path):
    """The refusal condition of Export to IMG: file format != scene game."""
    sa = tmp_path / "sa.img"
    create_img(str(sa))
    vc = tmp_path / "vc.img"
    create_img(str(vc), version=IMG_VERSION_1)
    assert detect_img_version(str(sa)) != gv.profile_for('VC').img_version
    assert detect_img_version(str(vc)) != gv.profile_for('SA').img_version
    assert detect_img_version(str(sa)) == gv.profile_for('SA').img_version
    assert detect_img_version(str(vc)) == gv.profile_for('III').img_version


def test_file_without_header_or_dir_is_not_an_archive(tmp_path):
    """No VER2 header and no .dir (a VC archive copied without its .dir):
    auto-detect says VER2, so the operator validates the directory first and
    reports the file instead of a «VER2 (SA)» game mismatch."""
    p = tmp_path / "gta3.img"
    p.write_bytes(b"raw VER1 data without its .dir")
    assert detect_img_version(str(p)) == IMG_VERSION_2
    with pytest.raises(ValueError):
        read_directory(str(p))


@pytest.mark.parametrize("game", ['III', 'VC', 'SA'])
def test_empty_file_is_laid_out_for_the_scene_game(tmp_path, game):
    """An empty .img without .dir isn't an archive yet — the operator lays it
    out for the scene game, after which the format check passes."""
    p = tmp_path / "new.img"
    p.write_bytes(b"")
    want = gv.profile_for(game).img_version
    create_img(str(p), version=want)
    assert detect_img_version(str(p)) == want
    with ImgWriter(str(p)) as w:
        w.add("a.dff", b"x")
    assert [n.lower() for n in list_files(str(p))] == ["a.dff"]


@pytest.mark.parametrize("name", ["дом.dff", "", "a" * 20 + ".dff"])
def test_entry_name_rejected(name):
    with pytest.raises(ValueError):
        _check_entry_name(name)


def test_entry_name_23_chars_ok():
    _check_entry_name("a" * 19 + ".dff")


def test_writer_refuses_non_ascii_name(tmp_path):
    p = tmp_path / "ru.img"
    create_img(str(p))
    with pytest.raises(ValueError):
        with ImgWriter(str(p)) as w:
            w.add("дом.dff", b"x")
    assert list_files(str(p)) == []


def _export_execute():
    tree = ast.parse(IMG_OPS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.ClassDef)
                and node.name == "GTATOOLS_OT_export_to_img"):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "execute":
                    return fn
    raise AssertionError("GTATOOLS_OT_export_to_img.execute not found")


def _calls(fn, name):
    """Line numbers of calls to `name` (plain or attribute) inside fn."""
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            if ((isinstance(f, ast.Name) and f.id == name)
                    or (isinstance(f, ast.Attribute) and f.attr == name)):
                out.append(n.lineno)
    return sorted(out)


def _t_keys(fn):
    return {n.args[0].value for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == 'T' and n.args
            and isinstance(n.args[0], ast.Constant)}


def _lang(fname):
    tree = ast.parse((ROOT / "INU_tools" / "locale" / fname)
                     .read_text(encoding="utf-8"))
    d = next(n.value for n in tree.body if isinstance(n, ast.Assign))
    return {k.value for k in d.keys if isinstance(k, ast.Constant)}


def test_export_takes_format_from_the_archive():
    fn = _export_execute()
    writers = [n for n in ast.walk(fn)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "ImgWriter"]
    assert writers
    for w in writers:
        # no version pinned from the scene game — the writer auto-detects
        assert not any(k.arg == "version" for k in w.keywords)
        # and the format is checked before any writer opens the archive
        assert _calls(fn, "detect_img_version")[0] < w.lineno


def test_export_checks_names_before_touching_anything():
    fn = _export_execute()
    first_check = _calls(fn, "_check_entry_name")[0]
    format_check = _calls(fn, "detect_img_version")[0]
    assert first_check < _calls(fn, "progress_begin")[0]
    assert first_check < _calls(fn, "ImgWriter")[0]
    # txd_name of the models is not changed before either refusal point
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Attribute) and t.attr == 'txd_name'
                for t in n.targets):
            assert n.lineno > max(first_check, format_check)


def test_export_new_messages_are_translated():
    keys = _t_keys(_export_execute())
    new = {
        "Имя для IMG длиннее 23 символов или не ASCII — игра его не найдёт: "
        "{0}. Переименуй модель / TXD.",
        "Архив {0} — формат {1}, а игра сцены — {2}: игра не прочитает такие "
        "DFF/COL. Переключи игру во вкладке GTA Tools или выбери другой "
        "архив.",
        "IMG: не удалось записать {0}: {1}",
    }
    assert new <= keys
    eng, spa = _lang("eng.py"), _lang("spa.py")
    assert new <= eng
    assert new <= spa


def _handler_names(h):
    t = h.type
    elts = t.elts if isinstance(t, ast.Tuple) else [t]
    return {e.id for e in elts if isinstance(e, ast.Name)}


def test_format_check_keeps_the_busy_file_hint():
    """PermissionError is an OSError: in the format check (before the writer)
    a locked archive must still get «Файл .img занят…», not a bare
    «[Errno 13]» from the generic handler."""
    fn = _export_execute()
    tries = [t for t in ast.walk(fn) if isinstance(t, ast.Try)
             and _calls(ast.Module(body=t.body, type_ignores=[]),
                        "read_directory")]
    assert tries
    for t in tries:
        names = [_handler_names(h) for h in t.handlers]
        perm = next(i for i, n in enumerate(names) if "PermissionError" in n)
        oserr = next(i for i, n in enumerate(names) if "OSError" in n)
        assert perm < oserr
        keys = _t_keys(ast.Module(body=t.handlers[perm].body, type_ignores=[]))
        assert "Файл .img занят — закрой игру перед экспортом: {0}" in keys


def test_all_to_img_skips_ide_ipl_when_img_export_refused():
    """All → IMG: the IMG step can now refuse cleanly (format / names / busy)
    instead of raising — IDE/IPL rows must not be written for models that
    never reached the archive."""
    tree = ast.parse((ROOT / "INU_tools" / "ops" / "inu_export.py")
                     .read_text(encoding="utf-8"))
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
               and n.name == "GTATOOLS_OT_export_all")
    fn = next(f for f in cls.body if isinstance(f, ast.FunctionDef)
              and f.name == "execute")
    img_branch = next(n for n in ast.walk(fn) if isinstance(n, ast.If)
                      and _calls(ast.Module(body=n.body, type_ignores=[]),
                                 "export_to_img"))
    # every call sits inside an `if` that checks FINISHED (not just the
    # enclosing `if self.to_img:`); models left out of the IMG — see
    # test_img_routing
    guards = [n for n in ast.walk(img_branch) if isinstance(n, ast.If)
              and any(isinstance(c, ast.Constant) and c.value == 'FINISHED'
                      for c in ast.walk(n.test))]
    lines = _calls(img_branch, "_also_upsert_ide_ipl")
    assert guards and lines
    for ln in lines:
        assert any(g.lineno < ln <= g.end_lineno for g in guards)
