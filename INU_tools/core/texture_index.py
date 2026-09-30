# INU_tools.core.texture_index
# Fast TXD texture indexer for the Texture Browser panel.
# Walks RW chunks at byte level to extract texture name + dimensions
# + format without decoding any pixels — vanilla gta3.img (~14k
# textures across ~3000 TXDs) indexes in seconds rather than minutes
# that full DXT decompression would cost.
#
# Pixel decode happens lazily in the operator layer when a specific
# texture is selected for preview — see ops/texture_browser_ops.py.

from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import os
import struct


# ── RW chunk constants ───────────────────────────────────────────

_RW_CHUNK_STRUCT = 0x01
_RW_CHUNK_TEX_DICT = 0x16
_RW_CHUNK_TEX_NATIVE = 0x15


# ── Public dataclass ─────────────────────────────────────────────

@dataclass(frozen=True)
class TextureEntry:
    """One texture inside one TXD. Identity = (archive_path, txd_name,
    texture_name) so the same texture name appearing in multiple TXDs
    or archives is preserved as separate entries — exactly the
    overview a modder wants when hunting for "where is this texture
    actually defined".
    """
    archive_path: str   # 'F:/GTA SA/models/gta3.img' or .txd file path
    txd_name: str       # 'generic' (without .txd extension)
    texture_name: str   # 'tarmac'
    width: int
    height: int
    depth: int          # bits per pixel
    fourcc: int         # 0=raw, 0x31545844='DXT1', 0x35545844='DXT5'
    num_levels: int     # mipmap count incl. base level
    platform_id: int    # 8=D3D8, 9=D3D9 (PC); 5=Xbox; 6=PS2

    @property
    def format_label(self) -> str:
        """Human-readable format string: 'DXT1', 'DXT3', 'DXT5',
        'RAW8', 'RAW32', etc. Used by UIList display."""
        if self.fourcc == 0:
            return f"RAW{self.depth}"
        # FourCC is a little-endian 4-char ASCII code.
        try:
            return self.fourcc.to_bytes(4, 'little').decode('ascii').rstrip('\x00')
        except Exception:
            return f"0x{self.fourcc:08X}"


# ── Compression mark of a Texture Native ──────────────────────────
# The u32 after raster_format means different things per platform:
#   D3D9 (SA)     — D3DFORMAT: FourCC 'DXT1'..'DXT5' for compressed
#                   textures, a small D3DFMT_* number for raw ones;
#   D3D8 (III/VC) — has_alpha (0/1); compression lives in the last
#                   header byte instead (1..5 = DXT1..DXT5).
# Reading the D3D8 value as a FourCC showed format '\x01' in the texture
# browser and a false TXD_RASTER_PAL_AND_DXT on every palettized texture.
_DXT_BASE = 0x00545844          # 'DXT' + digit in the high byte


def dxt_fourcc(platform_id: int, format_field: int, compression: int) -> int:
    """FourCC of the texture compression (DXT1..DXT5), 0 if uncompressed."""
    if platform_id == 8:
        if 1 <= compression <= 5:
            return _DXT_BASE | ((0x30 + compression) << 24)
        return 0
    b = format_field.to_bytes(4, 'little')
    return format_field if all(0x20 <= c <= 0x7E for c in b) else 0


# ── Bytes-level TXD walker ────────────────────────────────────────

def scan_txd_bytes(raw: bytes, archive_path: str, txd_name: str
                   ) -> List[TextureEntry]:
    """Extract texture metadata from raw TXD bytes. Pure byte-level,
    no pixel decode — yields one TextureEntry per Texture Native
    chunk found.

    Returns ``[]`` for malformed / unrecognized data instead of
    raising — the scanner walks thousands of files and we'd rather
    skip a bad one than abort the whole pass.
    """
    out: List[TextureEntry] = []
    n = len(raw)
    if n < 12:
        return out

    ct, cs, _cl = struct.unpack_from('<III', raw, 0)
    if ct != _RW_CHUNK_TEX_DICT:
        return out

    pos = 12
    # Inner Struct chunk: tex_count u16, device_id u16
    if pos + 12 > n:
        return out
    ct_s, cs_s, _ = struct.unpack_from('<III', raw, pos)
    if ct_s != _RW_CHUNK_STRUCT:
        return out
    pos += 12
    if pos + 4 > n:
        return out
    tex_count = struct.unpack_from('<H', raw, pos)[0]
    # Skip rest of struct payload
    pos = 12 + 12 + cs_s

    for _ in range(tex_count):
        if pos + 12 > n:
            break
        ct_t, cs_t, _ = struct.unpack_from('<III', raw, pos)
        chunk_payload = pos + 12
        chunk_end = chunk_payload + cs_t
        if ct_t == _RW_CHUNK_TEX_NATIVE and chunk_payload + 12 <= n:
            ct_st, cs_st, _ = struct.unpack_from('<III', raw, chunk_payload)
            if ct_st == _RW_CHUNK_STRUCT and chunk_payload + 12 + 92 <= n:
                base = chunk_payload + 12
                # Layout (RW PC native texture struct):
                #   platform_id u32, filter_flags u32,
                #   name(32), mask(32), raster_format u32,
                #   d3d_format/has_alpha u32 (see dxt_fourcc),
                #   width u16, height u16, depth u8, num_levels u8,
                #   raster_type u8, compression_flag u8.
                platform_id = struct.unpack_from('<I', raw, base)[0]
                name_bytes = raw[base + 8 : base + 8 + 32]
                name = name_bytes.split(b'\x00', 1)[0].decode('ascii',
                    errors='replace')
                fourcc = dxt_fourcc(platform_id,
                                    struct.unpack_from('<I', raw, base + 76)[0],
                                    raw[base + 87])
                width  = struct.unpack_from('<H', raw, base + 80)[0]
                height = struct.unpack_from('<H', raw, base + 82)[0]
                depth  = raw[base + 84]
                num_levels = raw[base + 85]
                if name:
                    out.append(TextureEntry(
                        archive_path=archive_path,
                        txd_name=txd_name,
                        texture_name=name,
                        width=width, height=height,
                        depth=depth, fourcc=fourcc,
                        num_levels=num_levels,
                        platform_id=platform_id,
                    ))
        pos = chunk_end
    return out


# ── Source-specific scanners ──────────────────────────────────────

def scan_img(img_path: str, progress_cb=None) -> List[TextureEntry]:
    """Walk an IMG archive, find every .txd entry, return all
    textures inside. ``progress_cb(i, n)`` optional for UI bars.
    """
    from .img import ImgReader
    out: List[TextureEntry] = []
    try:
        with ImgReader(img_path) as img:
            txd_entries = [e for e in img.entries
                           if e.name.lower().endswith('.txd')]
            total = len(txd_entries)
            for i, e in enumerate(txd_entries):
                if progress_cb:
                    progress_cb(i, total)
                data = img.read(e.name)
                if not data:
                    continue
                txd_basename = e.name.rsplit('.', 1)[0]
                out.extend(scan_txd_bytes(data, img_path, txd_basename))
    except Exception:
        # Bad archive — return whatever we got. Caller decides what
        # to do with an empty result.
        return out
    return out


def scan_folder(folder: str, *, recursive: bool = True,
                progress_cb=None) -> List[TextureEntry]:
    """Walk a folder for .txd files, return all textures found.
    Standalone .txd files only — IMG archives in the same folder
    are NOT auto-opened, call scan_img() for those separately."""
    out: List[TextureEntry] = []
    if not os.path.isdir(folder):
        return out

    txd_paths: List[str] = []
    for root, dirs, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith('.txd'):
                txd_paths.append(os.path.join(root, fn))
        if not recursive:
            dirs.clear()

    total = len(txd_paths)
    for i, path in enumerate(txd_paths):
        if progress_cb:
            progress_cb(i, total)
        try:
            with open(path, 'rb') as f:
                raw = f.read()
        except OSError:
            continue
        txd_basename = os.path.basename(path).rsplit('.', 1)[0]
        out.extend(scan_txd_bytes(raw, path, txd_basename))
    return out


# ── Usage cross-reference (TXD-name → list of IDE entries) ───────

def build_usage_map(ide_paths: List[str]) -> Dict[str, List[str]]:
    """Walk a set of IDE files, return ``{txd_name_lower: [model_name, ...]}``.

    The map tells the Texture Browser «which models use this TXD»
    so it can show usage_count and a list-of-models on selection.
    """
    from .ide import read_ide
    usage: Dict[str, List[str]] = {}
    for path in ide_paths:
        try:
            ide = read_ide(path)
        except Exception:
            continue
        # All entry kinds that carry a txd_name field.
        for entry in (list(ide.objects) + list(ide.anims)
                      + list(ide.cars) + list(ide.peds)
                      + list(ide.weaps) + list(ide.hiers)):
            t = (getattr(entry, 'txd_name', '') or '').lower()
            if not t:
                continue
            name = getattr(entry, 'model_name', '')
            usage.setdefault(t, []).append(name)
    return usage


# ── Decode one texture for preview ────────────────────────────────

def decode_one_texture(archive_path: str, txd_name: str,
                       texture_name: str) -> Optional[object]:
    """Decode a specific texture's pixels for lazy preview. Returns
    a ``core.txd.TxdTexture`` instance with ``.pixels`` populated
    (RGBA bytes, top-to-bottom). Returns ``None`` on failure.

    Reuses the full TXD parser so DXT decompression / palette
    handling matches the import path exactly. Slower than scan_*
    (decompresses one TXD) but only called for the one currently
    selected row, not the 3000 indexed during scan.
    """
    from .txd import read_txd, read_txd_file
    try:
        # Two source flavours: archive entry vs standalone .txd
        if archive_path.lower().endswith('.img'):
            from .img import ImgReader
            with ImgReader(archive_path) as img:
                data = img.read(f"{txd_name}.txd")
                if not data:
                    return None
            textures = read_txd(data)
        else:
            textures = read_txd_file(archive_path)
        for t in textures:
            if t.name == texture_name:
                return t
    except Exception:
        return None
    return None
