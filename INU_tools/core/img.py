"""
GTA III / VC / SA IMG archive reader/writer.

Two on-disk formats:

* **VER1** (GTA III + Vice City) — split:
    - ``gta3.dir`` (directory only): num_entries × 32-byte records, no header
    - ``gta3.img`` (raw data): files at sector-aligned offsets, no header
  Reader auto-pairs by basename: a ``.img`` next to a same-named ``.dir``
  is treated as VER1.

* **VER2** (San Andreas) — single file:
    - Header: ``"VER2"`` (4 bytes) + num_entries (uint32 LE)
    - Directory: num_entries × 32 bytes (offset, size, name)
    - Data: files at sector-aligned offsets.

Directory record layout is identical between versions — only the
location of the directory differs (inline vs sibling file).

No Blender dependency — pure Python.
"""

from __future__ import annotations
import os
import struct
from dataclasses import dataclass

SECTOR = 2048
MAGIC = b'VER2'
DIR_ENTRY_SIZE = 32
NAME_SIZE = 24

# Img-archive version IDs (also used in core.game_versions.GameProfile.img_version).
IMG_VERSION_1 = 1   # III / VC: split .dir + .img
IMG_VERSION_2 = 2   # SA: single .img with embedded header + directory


def _sibling_dir_path(img_path: str) -> str:
    """Return the ``.dir`` path that pairs with the given ``.img``.
    Strips the trailing extension and replaces with ``.dir`` — case is
    preserved on the suffix so vanilla ``gta3.img`` ↔ ``gta3.dir``
    round-trips on case-sensitive filesystems."""
    base, _ext = os.path.splitext(img_path)
    return base + '.dir'


def detect_img_version(filepath: str) -> int:
    """Return ``IMG_VERSION_1`` or ``IMG_VERSION_2`` for the given path.

    Probe order:
      1. First 4 bytes == ``b'VER2'`` → VER2
      2. Sibling ``.dir`` file exists → VER1
      3. Otherwise → fall back to VER2 (most common; the caller's
         downstream ``read_directory`` will raise a clear error if the
         header turns out to be malformed)
    """
    try:
        with open(filepath, 'rb') as f:
            head = f.read(4)
    except OSError:
        return IMG_VERSION_2
    if head == MAGIC:
        return IMG_VERSION_2
    if os.path.isfile(_sibling_dir_path(filepath)):
        return IMG_VERSION_1
    return IMG_VERSION_2


# Filename sanitization for entry/texture names extracted from corrupt
# archives. Non-ASCII bytes get replaced with `?` during ascii-decode,
# and `?` is invalid on Windows; the rest of this set covers POSIX/NTFS
# reserved characters. Real GTA SA archives never need this — it only
# fires when a TXD/IMG was hand-edited with garbage bytes.
_FILENAME_INVALID = '<>:"/\\|?*\x00'


def safe_filename(name: str) -> str:
    """Replace filesystem-invalid characters with underscore."""
    return ''.join('_' if c in _FILENAME_INVALID else c for c in name).strip()


@dataclass
class ImgEntry:
    """One file entry in an IMG archive."""
    name: str
    offset: int   # sector offset
    size: int     # size in sectors


def _game_uses(cur, new) -> bool:
    """True → ``new`` replaces ``cur`` as the same-name record the game
    streams: the first one WITH data (``CStreaming::LoadCdDirectory`` skips
    a name already registered, and ``CStreamingInfo::GetCdPosnAndSize`` is
    false while size is 0, so an empty record doesn't register it)."""
    return cur is None or (not cur.size and bool(new.size))


def sectors_needed(byte_size: int) -> int:
    """Number of 2048-byte sectors needed to store *byte_size* bytes."""
    return (byte_size + SECTOR - 1) // SECTOR


# ── Reading ─────────────────────────────────────────────────────────

def _parse_dir_records(raw: bytes) -> list[ImgEntry]:
    """Decode N × 32-byte directory records into ``ImgEntry`` objects.

    IMG VER2 entry layout (San Andreas docs / GTA wiki):
      offset       : u32 — sector offset (sectors of 2048 bytes)
      size_stream  : u16 — streaming size in sectors (THE actual size)
      size_archive : u16 — archive size in sectors (legacy, often 0
                          or equal to size_stream)
      name         : 24 bytes — zero-padded ASCII

    Earlier this used ``<II`` (two u32s) which folded the high u16 of
    the size field plus the low u16 of size_archive into a bogus huge
    sector count — e.g. for an entry with stream=2053, archive=2053 it
    produced size=0x08050805 ≈ 134M sectors ≈ 275 GB. ``self._f.read``
    with that count raised ``MemoryError`` on many systems; the outer
    operator's ``except Exception: pass`` swallowed it silently, so
    affected IMG archives appeared to extract zero files.

    Vanilla ``gta3.img`` worked by accident: the bogus size made
    ``file.read(N)`` return at most the file's actual remaining bytes,
    and downstream TXD/DFF parsers stopped at their own embedded
    length fields, ignoring the trailing junk. But large mod IMGs
    with high sector indices (Silent Hill TC etc.) tripped the
    MemoryError before parsing could happen."""
    entries = []
    n = len(raw) // DIR_ENTRY_SIZE
    for i in range(n):
        rec = raw[i * DIR_ENTRY_SIZE : (i + 1) * DIR_ENTRY_SIZE]
        off, size_stream, size_archive = struct.unpack_from('<IHH', rec, 0)
        # Use streaming size when present; some custom archives leave it
        # 0 and put the real size in `size_archive` (legacy VER1-like).
        sz = size_stream if size_stream > 0 else size_archive
        name_bytes = rec[8:8 + NAME_SIZE]
        name = name_bytes.split(b'\x00', 1)[0].decode('ascii', errors='replace')
        entries.append(ImgEntry(name=name, offset=off, size=sz))
    return entries


def read_directory(filepath: str) -> list[ImgEntry]:
    """Read the directory of an IMG archive — version auto-detected.

    For VER2, the directory is embedded at the top of the ``.img`` file.
    For VER1, it lives in a sibling ``.dir`` (same basename).
    """
    version = detect_img_version(filepath)
    if version == IMG_VERSION_1:
        dir_path = _sibling_dir_path(filepath)
        with open(dir_path, 'rb') as f:
            return _parse_dir_records(f.read())

    # VER2 — magic header + count + inline directory.
    entries = []
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != MAGIC:
            raise ValueError(f"Not a VER2 IMG archive (got {magic!r}). "
                             "No sibling .dir found either — file is "
                             "neither VER1 nor VER2.")
        num = struct.unpack('<I', f.read(4))[0]
        raw = f.read(num * DIR_ENTRY_SIZE)
        entries.extend(_parse_dir_records(raw))
    return entries


def extract_file(img_path: str, entry_name: str) -> bytes | None:
    """Extract a single file from an IMG archive by name — the same-name
    record the game streams (see ``_game_uses``)."""
    key = entry_name.lower()
    hit = None
    for e in read_directory(img_path):
        if e.name.lower() == key and _game_uses(hit, e):
            hit = e
    if hit is None:
        return None
    with open(img_path, 'rb') as f:
        f.seek(hit.offset * SECTOR)
        return f.read(hit.size * SECTOR)


class ImgReader:
    """Keeps IMG file open for fast sequential/random reads.
    Use as context manager for automatic cleanup.

    Usage:
        with ImgReader("gta3.img") as img:
            data = img.read("building01.dff")
            img.extract_all_to(output_dir)  # batch extract
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.version = IMG_VERSION_2
        self._f = None
        self._entries: list[ImgEntry] = []
        self._lookup: dict[str, ImgEntry] = {}

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def open(self):
        # Detect version BEFORE opening — for VER1 the directory lives
        # in a sibling .dir file, not inside the .img we'll be reading
        # data from.
        self.version = detect_img_version(self.filepath)
        self._entries = []
        self._lookup = {}

        if self.version == IMG_VERSION_1:
            # VER1: parse the sibling .dir first; keep the .img open
            # for random-access data reads.
            dir_path = _sibling_dir_path(self.filepath)
            with open(dir_path, 'rb') as df:
                raw = df.read()
            self._entries = _parse_dir_records(raw)
            self._f = open(self.filepath, 'rb')
        else:
            # VER2: magic + count + inline directory in one file.
            self._f = open(self.filepath, 'rb')
            magic = self._f.read(4)
            if magic != MAGIC:
                self._f.close()
                raise ValueError(f"Not a VER2 IMG archive (got {magic!r})")
            num = struct.unpack('<I', self._f.read(4))[0]
            raw = self._f.read(num * DIR_ENTRY_SIZE)
            self._entries = _parse_dir_records(raw)

        # Same-name records: the one the game streams wins (``_game_uses``).
        for entry in self._entries:
            k = entry.name.lower()
            if _game_uses(self._lookup.get(k), entry):
                self._lookup[k] = entry

    def close(self):
        if self._f:
            self._f.close()
            self._f = None

    @property
    def entries(self) -> list[ImgEntry]:
        return self._entries

    def read(self, entry_name: str) -> bytes | None:
        """Read a single file by name (fast — no directory re-read)."""
        e = self._lookup.get(entry_name.lower())
        if not e:
            return None
        self._f.seek(e.offset * SECTOR)
        return self._f.read(e.size * SECTOR)

    def read_entry(self, e: ImgEntry) -> bytes:
        """Data of one directory record (by its position, not by name —
        duplicates and empty entries included)."""
        if not e.size:
            return b''
        self._f.seek(e.offset * SECTOR)
        return self._f.read(e.size * SECTOR)

    def extract_all_to(self, output_dir: str,
                       extensions: set[str] | None = None,
                       skip_existing: bool = True,
                       name_filter=None) -> dict[str, int]:
        """Batch extract files to output_dir in one sequential pass.

        Args:
            output_dir: directory to write files to
            extensions: set of extensions to extract (e.g. {'.dff', '.col'}),
                       None = extract all
            skip_existing: skip files that already exist on disk
            name_filter: optional callable ``(lower_name: str) -> bool`` —
                       only entries where the filter returns True are
                       extracted. Lets callers narrow down by base name
                       (e.g. region-filtered TXD subsets) while still
                       benefiting from the sorted-by-offset pass.

        Returns dict with counts: {'dff': N, 'col': N, 'txd': N, 'other': N, 'skipped': N}
        """
        os.makedirs(output_dir, exist_ok=True)

        # Sort entries by offset for sequential disk read; of same-name
        # records only the one the game streams is extracted, and not an
        # empty one (holds no file — with skip_existing it would block the
        # same name from a later archive).
        sorted_entries = sorted(
            (e for e in self._entries
             if e.size and self._lookup.get(e.name.lower()) is e),
            key=lambda e: e.offset)

        counts = {'dff': 0, 'col': 0, 'txd': 0, 'other': 0, 'skipped': 0}

        for entry in sorted_entries:
            low = entry.name.lower()
            ext = '.' + low.rsplit('.', 1)[-1] if '.' in low else ''

            if extensions and ext not in extensions:
                continue
            if name_filter is not None and not name_filter(low):
                continue

            out_path = os.path.join(output_dir, safe_filename(entry.name))
            if skip_existing and os.path.isfile(out_path):
                counts['skipped'] += 1
                continue

            self._f.seek(entry.offset * SECTOR)
            data = self._f.read(entry.size * SECTOR)

            # Trim padding (sector-aligned, may have trailing zeros)
            with open(out_path, 'wb') as out:
                out.write(data)

            if ext == '.dff':
                counts['dff'] += 1
            elif ext == '.col':
                counts['col'] += 1
            elif ext == '.txd':
                counts['txd'] += 1
            else:
                counts['other'] += 1

        return counts


# ── Writing / Replacing ────────────────────────────────────────────

def replace_or_add(img_path: str, filename: str, data: bytes) -> str:
    """
    Replace or add one file in an IMG archive (VER1 or VER2).

    - If *filename* already exists and the new data fits in the old slot,
      overwrite in place.
    - If new data is larger or file doesn't exist, append at the end.
    - Directory is always rewritten (the sibling ``.dir`` for VER1).

    Thin wrapper over ``ImgWriter`` so both share one code path, including
    the VER2 directory-growth relocation. For many files use ``ImgWriter``
    directly.

    Returns status string: 'replaced' or 'added'.
    """
    with ImgWriter(img_path) as w:
        return w.add(filename, data)


def remove_file(img_path: str, filename: str) -> bool:
    """
    Remove a file entry from the directory (data stays, space is wasted).
    VER1 rewrites the sibling ``.dir``; VER2 rewrites the inline directory.
    Returns True if removed.
    """
    version = detect_img_version(img_path)
    entries = read_directory(img_path)
    new_entries = [e for e in entries if e.name.lower() != filename.lower()]
    removed = len(entries) - len(new_entries)
    if not removed:
        return False

    if version == IMG_VERSION_1:
        _write_dir_file(_sibling_dir_path(img_path), new_entries)
        return True
    with open(img_path, 'r+b') as f:
        _write_directory(f, new_entries)
        # The directory shrank: blank the stale tail records.
        f.write(b'\x00' * (removed * DIR_ENTRY_SIZE))
    return True


def _check_entry_name(filename: str) -> None:
    """Reject names the game can't load. The record holds 24 bytes and the
    engine forces ``name[23] = 0`` (``CStreaming::LoadCdDirectory``), so a
    24th character is lost and the entry no longer matches IDE/IPL."""
    try:
        raw = filename.encode('ascii')
    except UnicodeEncodeError:
        raise ValueError(f"IMG entry name must be ASCII: {filename!r}")
    if not raw or len(raw) > NAME_SIZE - 1:
        raise ValueError(f"IMG entry name must be 1..{NAME_SIZE - 1} "
                         f"characters: {filename!r}")


def _encode_directory_records(entries: list[ImgEntry]) -> bytes:
    """Serialise entries to the 32-bytes-per-record on-disk form. Used
    for both VER1 (full .dir contents) and VER2 (in-place at top of .img).

    Size is written as ``<HH`` (streaming size, archive size = 0), the
    layout ``_parse_dir_records`` reads. Names are cut to 23 bytes so the
    field always keeps its terminating zero."""
    out = bytearray()
    for e in entries:
        if e.size > 0xFFFF:
            raise ValueError(f"IMG entry {e.name!r} is {e.size} sectors, "
                             "the directory size field holds at most 65535")
        name_bytes = e.name.encode('ascii', errors='replace')[:NAME_SIZE - 1]
        name_bytes = name_bytes.ljust(NAME_SIZE, b'\x00')
        out += struct.pack('<IHH', e.offset, e.size, 0)
        out += name_bytes
    return bytes(out)


def _directory_end(num_entries: int) -> int:
    """Byte offset where the VER2 header + directory end."""
    return 8 + num_entries * DIR_ENTRY_SIZE


def _write_directory(f, entries: list[ImgEntry]) -> None:
    """Rewrite the VER2 header and directory in-place at the top of
    the IMG file. VER1 doesn't use this — its .dir is a separate file
    written by ImgWriter on close."""
    f.seek(0)
    f.write(MAGIC)
    f.write(struct.pack('<I', len(entries)))
    f.write(_encode_directory_records(entries))


def _write_dir_file(dir_path: str, entries: list[ImgEntry]) -> None:
    """Write VER1's sibling .dir file (just concatenated 32-byte
    records, no header)."""
    with open(dir_path, 'wb') as f:
        f.write(_encode_directory_records(entries))


class ImgWriter:
    """Batch-mode IMG archive writer — context manager.

    Opens the IMG once, loads the directory once, appends/replaces many
    files, then rewrites the directory ONCE at close. Cuts the cost of
    big exports from O(N × directory-size) writes to O(N + directory-size).

    Typical use:

        with ImgWriter("gta3.img") as w:
            for group in groups:
                w.add("house1.dff", dff_bytes)
                w.add("house1.col", col_bytes)
                w.add("house1.txd", txd_bytes)
        # Directory was rewritten exactly once on exit.

    Compatible semantics with ``replace_or_add``:
    - If the file exists and new data fits in the old slot → overwrite
      in place
    - If it doesn't fit or the file is new → append at the end
    - Directory entry is updated accordingly and flushed at close.

    VER2 keeps its directory at the top of the file, so every added entry
    grows it by 32 bytes towards the first file's data. On close, files
    the grown directory would overlap are moved to the end of the archive
    before the directory is written.
    """

    def __init__(self, filepath: str, *, version: int | None = None,
                 reserve_entries: int = 0):
        """Open or create an IMG archive for batch writes.

        ``version`` — 1 (VER1, III/VC: split .dir + .img) or 2 (VER2,
        SA: single .img). Default ``None`` means auto-detect from the
        existing file (or fall back to VER2 for new archives).

        ``reserve_entries`` — VER2 only: leave room for a directory of this
        many entries before the first appended file, so a fresh archive of
        known size (``rebuild_img``) needs no relocation at close.
        """
        self.filepath = filepath
        self.version = version
        self.reserve_entries = reserve_entries
        self._f = None
        self._entries: list[ImgEntry] = []
        self._lookup: dict[str, int] = {}
        self._end_pos: int = 0

    def _register(self, i: int) -> None:
        """Index record ``i`` by name — of same-name records the one the
        game streams wins (``_game_uses``), so ``add`` replaces that one."""
        e = self._entries[i]
        k = e.name.lower()
        j = self._lookup.get(k)
        if _game_uses(None if j is None else self._entries[j], e):
            self._lookup[k] = i

    def __enter__(self):
        # Auto-detect version when not pinned by caller. We do this BEFORE
        # opening so the right read path (embedded vs sibling .dir) is
        # taken.
        if self.version is None:
            if os.path.isfile(self.filepath):
                self.version = detect_img_version(self.filepath)
            else:
                self.version = IMG_VERSION_2

        if self.version == IMG_VERSION_1:
            # VER1: directory lives in sibling .dir. Data file (.img)
            # is plain raw — no header to consume. Append-pointer (
            # ``_end_pos``) starts at the file's current EOF, which is
            # 0 for a freshly created archive.
            dir_path = _sibling_dir_path(self.filepath)
            # Create the .img if missing, then open r+b.
            if not os.path.isfile(self.filepath):
                open(self.filepath, 'wb').close()
            self._f = open(self.filepath, 'r+b')
            if os.path.isfile(dir_path):
                with open(dir_path, 'rb') as df:
                    raw = df.read()
                for i, e in enumerate(_parse_dir_records(raw)):
                    self._entries.append(e)
                    self._register(i)
            self._f.seek(0, 2)
            self._end_pos = self._f.tell()
            return self

        # VER2 — single-file with embedded header + directory at top.
        # If the file doesn't exist we initialise an empty VER2 header
        # so the append path below has a valid file to work with.
        if not os.path.isfile(self.filepath):
            create_img(self.filepath)
        self._f = open(self.filepath, 'r+b')
        magic = self._f.read(4)
        if magic != MAGIC:
            self._f.close()
            self._f = None
            raise ValueError(f"Not a VER2 IMG archive (got {magic!r})")
        num = struct.unpack('<I', self._f.read(4))[0]
        # Same record decoder as the reader: size is two u16s.
        for i, e in enumerate(_parse_dir_records(
                self._f.read(num * DIR_ENTRY_SIZE))):
            self._entries.append(e)
            self._register(i)
        # Remember current EOF so append operations don't have to
        # seek-to-end every time (which costs a syscall).
        self._f.seek(0, 2)
        self._end_pos = max(self._f.tell(),
                            _directory_end(self.reserve_entries))
        return self

    def _append(self, padded: bytes) -> int:
        """Write sector-padded data at the sector-aligned end of the
        archive. Returns its sector offset."""
        aligned = sectors_needed(self._end_pos) * SECTOR
        if self._end_pos < aligned:
            self._f.seek(self._end_pos)
            self._f.write(b'\x00' * (aligned - self._end_pos))
            self._end_pos = aligned
        self._f.seek(self._end_pos)
        self._f.write(padded)
        new_offset = self._end_pos // SECTOR
        self._end_pos += len(padded)
        return new_offset

    def _relocate_under_directory(self) -> None:
        """VER2: move every file whose data starts inside the space the
        directory is about to occupy to the end of the archive. Moving
        doesn't change the entry count, so one pass is enough."""
        dir_end = _directory_end(len(self._entries))
        for e in self._entries:
            if e.size and e.offset * SECTOR < dir_end:
                self._f.seek(e.offset * SECTOR)
                data = self._f.read(e.size * SECTOR)
                data += b'\x00' * (e.size * SECTOR - len(data))
                e.offset = self._append(data)

    def add(self, filename: str, data: bytes) -> str:
        """Add or replace one file. Returns ``'added'`` or ``'replaced'``."""
        if self._f is None:
            raise RuntimeError("ImgWriter used outside its 'with' block")
        _check_entry_name(filename)

        new_sectors = sectors_needed(len(data))
        if new_sectors > 0xFFFF:
            raise ValueError(f"{filename}: {len(data)} bytes is too big for "
                             "one IMG entry (max 65535 sectors)")
        padded = data + b'\x00' * (new_sectors * SECTOR - len(data))

        idx = self._lookup.get(filename.lower())
        if idx is not None and new_sectors <= self._entries[idx].size:
            # In-place — cheapest path.
            e = self._entries[idx]
            self._f.seek(e.offset * SECTOR)
            self._f.write(padded)
            e.size = new_sectors
            return 'replaced'

        # Append path — align end to sector boundary.
        new_offset = self._append(padded)

        if idx is not None:
            self._entries[idx].offset = new_offset
            self._entries[idx].size = new_sectors
            return 'replaced'
        self._entries.append(ImgEntry(
            name=filename, offset=new_offset, size=new_sectors))
        self._lookup[filename.lower()] = len(self._entries) - 1
        return 'added'

    def append_entry(self, filename: str, data: bytes) -> None:
        """Append a NEW directory record as is — no lookup, no name check
        (rebuild_img: keeps duplicate names and empty entries of the source
        archive, which ``add`` would merge or drop)."""
        if self._f is None:
            raise RuntimeError("ImgWriter used outside its 'with' block")
        n = sectors_needed(len(data))
        offset = self._append(data + b'\x00' * (n * SECTOR - len(data)))
        self._entries.append(ImgEntry(name=filename, offset=offset, size=n))
        self._register(len(self._entries) - 1)

    def __exit__(self, *args):
        if self._f is not None:
            try:
                if self.version == IMG_VERSION_1:
                    # VER1: directory in sibling .dir, .img holds only data.
                    _write_dir_file(_sibling_dir_path(self.filepath),
                                    self._entries)
                else:
                    self._relocate_under_directory()
                    _write_directory(self._f, self._entries)
            finally:
                self._f.close()
                self._f = None


def create_img(filepath: str, *, version: int = IMG_VERSION_2) -> None:
    """Create an empty IMG archive.

    VER2 (SA): single ``.img`` with ``VER2`` magic + zero count.
    VER1 (III/VC): empty ``.img`` data file plus empty ``.dir`` next
    to it — the data file has no header, the directory file is also
    initially empty.
    """
    if version == IMG_VERSION_1:
        # Empty .img (raw data, no header) + empty .dir (no records).
        open(filepath, 'wb').close()
        open(_sibling_dir_path(filepath), 'wb').close()
        return
    with open(filepath, 'wb') as f:
        f.write(MAGIC)
        f.write(struct.pack('<I', 0))


def list_files(img_path: str) -> list[str]:
    """Return list of filenames in the archive."""
    return [e.name for e in read_directory(img_path)]


def rebuild_img(filepath: str) -> dict:
    """Compact an IMG archive — drop the dead sectors left behind when an
    entry was replaced with larger data and appended instead of overwritten
    in place (``ImgWriter.add`` repoints the directory but never reclaims the
    old slot, so repeated re-exports bloat the file).

    Reads every directory record (duplicate names and empty entries
    included), writes a fresh archive with sequential offsets, then
    atomically replaces the original (and its sibling ``.dir`` for VER1).
    Returns ``{'entries', 'old_size', 'new_size', 'saved'}`` (bytes).
    """
    version = detect_img_version(filepath)
    old_size = os.path.getsize(filepath)
    tmp = filepath + '.rebuild_tmp'
    tmp_dir = _sibling_dir_path(tmp)
    dst_dir = _sibling_dir_path(filepath)
    # VER1: a lone tmp_dir means an earlier rebuild swapped the .img but not
    # the .dir — it is the only copy of the new directory, never delete it.
    if (version == IMG_VERSION_1 and os.path.exists(tmp_dir)
            and not os.path.exists(tmp)):
        raise OSError(f"{tmp_dir} is left from an interrupted rebuild; "
                      f"rename it to {dst_dir} by hand first")

    # 1. Read every directory record's (sector-aligned) data BY POSITION —
    #    reading by name returned one duplicate for both records and
    #    ``if data`` dropped empty ones, so the rebuilt directory lost entries.
    with ImgReader(filepath) as r:
        blobs = [(e.name, r.read_entry(e)) for e in r.entries]

    # 2. Write a fresh, compacted archive beside the original — same records
    #    in the same order. tmp_dir goes first: if it can't be removed, tmp
    #    stays beside it and the pair is never taken for a lone tmp_dir.
    for _p in (tmp_dir, tmp):
        if os.path.exists(_p):
            os.remove(_p)
    swapped = False
    try:
        create_img(tmp, version=version)
        with ImgWriter(tmp, version=version, reserve_entries=len(blobs)) as w:
            for name, data in blobs:
                w.append_entry(name, data)

        # 3. Atomically swap in the rebuilt archive (+ sibling .dir for VER1).
        os.replace(tmp, filepath)
        swapped = True
        if version == IMG_VERSION_1 and os.path.exists(tmp_dir):
            try:
                os.replace(tmp_dir, dst_dir)
            except OSError as e:
                raise OSError(f"{filepath} rebuilt, but {dst_dir} could not "
                              f"be replaced ({e}); rename {tmp_dir} to "
                              f"{dst_dir} by hand") from e
    finally:
        # Before the swap the original is untouched — drop the temp files
        # (tmp_dir first: a lone tmp_dir must only ever mean "swapped", so
        # if it can't be removed tmp is kept too — the next run clears both).
        if not swapped:
            for _p in (tmp_dir, tmp):
                if os.path.exists(_p):
                    try:
                        os.remove(_p)
                    except OSError:
                        break

    new_size = os.path.getsize(filepath)
    return {'entries': len(blobs), 'old_size': old_size,
            'new_size': new_size, 'saved': max(0, old_size - new_size)}


