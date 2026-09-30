"""
Map files of a GTA SA game folder: which IPLs make up a map region and
which archive record of a model the game streams. One module for Scan
IPLs, Import Map and Extract Resources, so all three see the same files.

What the game does (gta_sa.exe 1.0 US):

* ``CIplStore::SetupRelatedIpls`` (0x404DE0) takes the stem of every text
  IPL of gta.dat (``DATA\\MAPS\\LA\\LAn2.IPL`` → ``LAn2``), appends
  ``_stream`` and links every IPL slot of the archives whose name starts
  with that (strnicmp). Only linked slots stream in by position; the rest
  load from a script only (mission IPLs such as ``barriers1``).
  ``STREAM_RE`` also wants digits after ``_stream`` (as INU Max) — no
  difference for the vanilla files and usual mods.
* ``CIplStore::LoadIpl`` (0x406080) resolves the ``lod_index`` of a linked
  slot in the instance list of its text IPL, not in the slot itself.
* ``CStreaming::InitImageList`` (0x4083C0) registers ``GTA3.IMG`` (slot 0)
  and ``GTA_INT.IMG`` (slot 1), ``CFileLoader::LoadLevel`` (0x5B9030) the
  IMG lines of gta.dat. ``CStreaming::LoadCdDirectory`` (0x5B82C0) walks
  them in that order and skips a name that is already registered — the
  first archive wins; a record of size 0 does not hold its name
  (``GetCdPosnAndSize`` 0x4075A0 is false for it). III/VC walk their
  CDIMAGE archives the other way round (re3 ``LoadCdDirectory``), but
  only models/gta3.img streams there in the vanilla games. The order
  itself is ``gta_dat.img_load_order`` (one for every tab).

Extract cache index — ``.inu_cache/_extract_index.json``, shared with INU
Max (a .blend and a .max in one folder share the cache)::

    files    {name.lower(): [archive, offset, size, crc32]}   DFF / COL
    txd      {name.lower(): [archive, offset, size, crc32]}   decoded TXD
    txd_png  {txd name.lower(): [png file name.lower(), ...]}
    archives {normcase(abspath(archive)): [size, mtime_ns]}   state checked
    tex_ver, tex_stale                                        PNG decode version

An unchanged archive is not read at all; in a changed one every planned
record is read and compared by CRC, so a model replaced in place (same
offset and size, e.g. Export to IMG) still reaches the cache.

No Blender dependency — pure Python.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import zlib

from .gta_dat import img_load_order
from .img import SECTOR, safe_filename
from .ipl import _read_binary_ipl, read_ipl

STREAM_RE = re.compile(r'^(.+)_stream\d+\.ipl$', re.I)

# Folders that never hold game archives — skipped by find_game_imgs.
SKIP_DIRS = {'.git', '.svn', '__pycache__', '.inu_cache', 'node_modules'}


# ── IPL files of a region ──────────────────────────────────────────

def region_match(path: str, region: str) -> bool:
    """True when the IPL ``path`` (an IPL line of gta.dat, best relative to
    the game root) belongs to ``region``: the folder after ``maps`` names
    it (``DATA\\MAPS\\COUNTRY\\countn2.ipl``), otherwise the file name
    starts with it. ``ALL`` / empty region → always True."""
    if not region or region == 'ALL':
        return True
    parts = [x for x in path.replace('/', '\\').split('\\') if x]
    low = [x.lower() for x in parts]
    if 'maps' in low:
        i = low.index('maps')
        if i + 1 < len(parts) - 1:
            return parts[i + 1].upper() == region.upper()
    name = parts[-1] if parts else ''
    return name.upper().startswith(region.upper())


def binary_stem(name: str):
    """Stem of the text IPL a streamed IPL belongs to, lower case:
    ``countn2_stream3.ipl`` → ``countn2``; None for any other name."""
    m = STREAM_RE.match(os.path.basename(name or ''))
    return m.group(1).lower() if m else None


def rebase_binary_lod(li: int, tb) -> int:
    """``lod_index`` of a streamed IPL row → index in the merged instance
    list. ``tb`` = (first index, row count) of its text IPL there; None
    when that text IPL is not loaded. Anything else → -1 (no LOD)."""
    if tb is not None and 0 <= li < tb[1]:
        return tb[0] + li
    return -1


def region_files(text_paths, archives, region, list_entries, root=''):
    """IPL files of a map region — one set for Scan, Import Map and Extract.

    text_paths — IPL lines of gta.dat (existing files); the region is
    matched on the path relative to ``root`` (an install under a folder
    named «Maps» must not decide it). archives — in load order
    (``order_archives``); list_entries(archive) → its directory records
    (``.name``, ``.offset``, ``.size``).

    Returns (text [path], binary [(record name, archive, record)]): binary
    are the ``<stem>_stream<N>.ipl`` records of the region's text IPLs,
    the record the game streams for each name (``extract_winners``: first
    archive, first record, one of size 0 only while no other has data).
    Read them by record (``read_entry``) — a name can repeat."""
    text, seen = [], set()
    for p in text_paths:
        k = os.path.normcase(os.path.abspath(p))
        if k in seen:
            continue
        rel = p
        if root:
            try:
                rel = os.path.relpath(p, root)
            except ValueError:          # another drive
                rel = p
        if not region_match(rel, region):
            continue
        seen.add(k)
        text.append(p)
    stems = {os.path.splitext(os.path.basename(p))[0].lower() for p in text}
    win = extract_winners(archives, list_entries, exts=('.ipl',))
    binary = [(e.name, a, e) for k, (a, e) in win.items()
              if binary_stem(k) in stems]
    return text, binary


def read_ipl_bytes(data: bytes):
    """IplFile of an archive record — binary (``bnry``) or text."""
    if data[:4] == b'bnry':
        return _read_binary_ipl(data)
    fd, tmp = tempfile.mkstemp(suffix='.ipl')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        return read_ipl(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ── Archives ───────────────────────────────────────────────────────

def find_game_imgs(root: str) -> list:
    """Every .img under the game folder (housekeeping folders skipped)."""
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d.lower() not in SKIP_DIRS]
        out += [os.path.join(dp, f) for f in fn if f.lower().endswith('.img')]
    return out


def order_archives(paths, root, dat_imgs=(), extra=()) -> list:
    """Archives in the game's load order — the one of the Import tab
    (core/gta_dat.img_load_order: SA gta3.img, gta_int.img, IMG lines of
    default.dat/gta.dat above the first IPL; III/VC the last CDIMAGE first,
    gta3.img last), then ``extra`` (the IMG picked in the panel), the rest
    alphabetically. Only when <root>/data has no game .dat: models/gta3.img,
    models/gta_int.img, ``dat_imgs`` (IMG lines of gta.dat), ``extra``.
    The same file twice (another spelling) is kept once."""
    def key(p):
        return os.path.normcase(os.path.abspath(p))
    order = []
    if root and os.path.isdir(root):
        try:
            order = img_load_order(root)
        except OSError:
            order = []
    if not order and root:
        order = [os.path.join(root, 'models', 'gta3.img'),
                 os.path.join(root, 'models', 'gta_int.img')] + list(dat_imgs)
    order += list(extra)
    rank = {}
    for i, p in enumerate(order):
        rank.setdefault(key(p), i)
    out, seen = [], set()
    for p in paths:
        k = key(p)
        if k not in seen:
            seen.add(k)
            out.append(p)
    return sorted(out, key=lambda p: (rank.get(key(p), len(order)), p.lower()))


def game_archives(root, dat_imgs=(), extra='') -> list:
    """All archives of the game folder in load order. ``extra`` (the IMG
    picked in the panel, may lie outside the folder) goes right after the
    .dat ones, unless the game ranks it already (gta3.img)."""
    found = find_game_imgs(root) if root and os.path.isdir(root) else []
    ext = []
    if extra and os.path.isfile(extra):
        found.append(extra)
        ext.append(extra)
    return order_archives(found, root, dat_imgs, ext)


# ── Extract cache index ────────────────────────────────────────────

INDEX_NAME = '_extract_index.json'
# PNG decode version, same numbers as INU Max: 2 = palette textures of
# D3D8 (GTA III) with R and B in place.
TEX_VER = 2


def load_index(cdir: str) -> dict:
    """The extract index of a cache folder ({} when missing or unreadable)."""
    try:
        with open(os.path.join(cdir, INDEX_NAME), 'r', encoding='utf-8') as f:
            idx = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(idx, dict):
        return {}
    for k in ('files', 'txd', 'txd_png', 'archives'):
        if not isinstance(idx.get(k, {}), dict):
            idx[k] = {}
    return idx


def save_index(cdir: str, idx: dict) -> None:
    """Write the index through .tmp + replace (never half a file). Keys
    this module does not use are written back as they were."""
    p = os.path.join(cdir, INDEX_NAME)
    with open(p + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(idx, f)
    os.replace(p + '.tmp', p)


def archive_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def archive_state(path: str):
    """[size, mtime in ns] of an archive — any write to it changes this.
    None when the file cannot be read."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return [st.st_size, st.st_mtime_ns]


def extract_winners(archives, list_entries, exts=('.dff', '.col', '.txd'),
                    multi=None) -> dict:
    """{name.lower(): (archive, entry)} — the record the game streams for
    each name: first archive in ``archives`` order, first record inside an
    archive; a record of size 0 only while no other one has data.
    ``multi`` (a set) collects the names found in more than one archive."""
    win, first = {}, {}
    for a in archives:
        for e in list_entries(a):
            k = e.name.lower()
            if not k.endswith(exts):
                continue
            cur = win.get(k)
            if cur is None:
                win[k] = (a, e)
                first[k] = a
                continue
            if multi is not None and first[k] != a:
                multi.add(k)
            if not cur[1].size and e.size:
                win[k] = (a, e)
    return win


def entry_stamp(archive, entry, crc) -> list:
    """Index stamp of a cached record: [archive, offset, size, CRC-32]."""
    return [os.path.abspath(archive), int(entry.offset), int(entry.size),
            int(crc) & 0xFFFFFFFF]


def cached_ok(old, archive, entry, crc=None, archive_same=False,
              have_output=True) -> bool:
    """True → the cache already holds this record. Before reading (no
    ``crc``) only the stamp of an unchanged archive is trusted; with the
    record's CRC the stamp must carry the same one. A stamp of another
    shape (older INU Max, damaged index) never matches."""
    if not have_output or not isinstance(old, list) or len(old) != 4:
        return False
    try:
        if (archive_key(old[0]) != archive_key(archive)
                or old[1] != entry.offset or old[2] != entry.size):
            return False
    except (TypeError, ValueError):
        return False
    if crc is not None:
        return old[3] == crc
    return archive_same


def txd_outputs_present(idx, key, have_png) -> bool:
    """Every PNG the TXD gave last time is still in textures."""
    names = (idx.get('txd_png') or {}).get(key)
    return isinstance(names, list) and all(n in have_png for n in names)


def reset_tex_index(idx, png_names) -> set:
    """Texture part of the index before a run; ``png_names`` — lower-case
    PNG files now in .inu_cache/textures. Another decode version →
    every TXD is decoded again and the PNGs of the old decode are
    overwritten once whatever their size (``tex_stale``, as INU Max); no
    PNG at all → every TXD again. Returns the stale PNG names."""
    txds = idx.setdefault('txd', {})
    pngs = idx.setdefault('txd_png', {})
    if idx.get('tex_ver') != TEX_VER:
        txds.clear()
        pngs.clear()
        idx['tex_stale'] = sorted(png_names)
        idx['tex_ver'] = TEX_VER
    if not png_names:
        txds.clear()
    return set(idx.get('tex_stale') or ())


def plan_extract(win, idx, states, have_files, have_png, want_txd=None) -> dict:
    """What Extract has to read. win — ``extract_winners``; states —
    {archive: archive_state()} now; have_files / have_png — lower-case
    names in the cache folder / in textures; want_txd — TXD names without
    extension the region needs (None = all).

    Returns {'files': {archive: [(name, entry)]}, 'txd': {…}, 'filtered':
    {archive: [(name, entry)]}, 'same': n}: records sorted by offset (one
    pass through each archive); a record whose archive is unchanged and
    whose stamp and output are in place goes to 'same' and is not read."""
    files = idx.setdefault('files', {})
    txds = idx.setdefault('txd', {})
    seen = idx.get('archives') or {}
    plan = {'files': {}, 'txd': {}, 'filtered': {}, 'same': 0}
    for k, (a, e) in win.items():
        st = states.get(a)
        same = st is not None and seen.get(archive_key(a)) == st
        if k.endswith('.txd'):
            if want_txd is not None and k[:-4] not in want_txd:
                plan['filtered'].setdefault(a, []).append((k, e))
                continue
            ok = cached_ok(txds.get(k), a, e, archive_same=same,
                           have_output=txd_outputs_present(idx, k, have_png))
            bucket = plan['txd']
        else:
            ok = cached_ok(files.get(k), a, e, archive_same=same,
                           have_output=safe_filename(e.name).lower() in have_files)
            bucket = plan['files']
        if ok:
            plan['same'] += 1
        else:
            bucket.setdefault(a, []).append((k, e))
    for bucket in (plan['files'], plan['txd']):
        for todo in bucket.values():
            todo.sort(key=lambda ke: ke[1].offset)
    return plan


def read_entry(fh, entry) -> bytes:
    """Bytes of one directory record (``fh`` — the open .img; VER1 keeps
    its data there too). By record, not by name: a name can repeat."""
    if not entry.size:
        return b''
    fh.seek(entry.offset * SECTOR)
    return fh.read(entry.size * SECTOR)


def refresh_file(fh, archive, key, entry, out_path, stamps) -> bool:
    """Bring one cached file in line with its archive record (``stamps`` —
    the index's ``files``). True when the file was (re)written; a failed
    write leaves no stamp, so the next run tries again."""
    data = read_entry(fh, entry)
    stamp = entry_stamp(archive, entry, zlib.crc32(data))
    if cached_ok(stamps.get(key), archive, entry, crc=stamp[3],
                 have_output=os.path.isfile(out_path)):
        return False
    stamps.pop(key, None)
    with open(out_path, 'wb') as f:
        f.write(data)
    stamps[key] = stamp
    return True


def finish_archive(idx, archive, state, filtered=()) -> None:
    """Every planned record of ``archive`` went through: remember the state
    its stamps were checked against. If the archive changed, the TXDs the
    region filter left out were not checked — their stamps are dropped so
    they are decoded once a region needs them."""
    seen = idx.setdefault('archives', {})
    k = archive_key(archive)
    if state is None or seen.get(k) != state:
        txds = idx.setdefault('txd', {})
        for name in filtered:
            txds.pop(name, None)
    if state is None:
        seen.pop(k, None)
    else:
        seen[k] = state
