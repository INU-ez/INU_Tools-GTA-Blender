"""core.txd_lint — post-write audit of a TXD file image against what the SA
TXD reader dereferences (TXD-* in E:\\RE\\addon_check\\txd_path.md).

Every rule gets a passing and a failing case built from a hand-assembled
Texture Native (the same layout tools.txd_export emits). Pure Python — no
Blender required.
"""

from pathlib import Path
from struct import pack
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.txd_lint import check_txd  # noqa: E402

LIB = 0x1803FFFF
DXT1 = 0x31545844
DXT3 = 0x33545844


def _chunk(t, body, lib=LIB):
    return pack('<III', t, len(body), lib) + body


def _levels(w, h, fourcc, mip, bpp=0, sizes=None):
    """Level blobs the way the exporter writes them (full chain when mip)."""
    out = b''
    n = 1
    if mip:
        n = max(w, h).bit_length()
    for lvl in range(n):
        lw, lh = max(1, w >> lvl), max(1, h >> lvl)
        if fourcc:
            size = max(1, (lw + 3) // 4) * max(1, (lh + 3) // 4) * (8 if fourcc == DXT1 else 16)
        else:
            size = lw * bpp // 8 * lh
        if sizes and lvl in sizes:
            size = sizes[lvl]
        out += pack('<I', size) + b'\x11' * size
    return out, n


def _native(name="brick", w=16, h=16, fourcc=DXT1, mip=True, platform=9,
            raster_format=None, flags=None, raster_type=4, num_levels=None,
            filt=0x1106, mask="", depth=16, extra=b'', sizes=None, lib=LIB,
            struct_lib=LIB, bpp=0, d3d_format=None):
    if raster_format is None:
        raster_format = (0x0200 if fourcc == DXT1 else 0x0300) | (0x8000 if mip else 0)
    if flags is None:
        flags = 0x08 if fourcc == DXT1 else 0x09
    levels, n = _levels(w, h, fourcc, mip, bpp=bpp, sizes=sizes)
    if num_levels is None:
        num_levels = n
    if d3d_format is None:
        d3d_format = fourcc
    body = pack('<II', platform, filt)
    body += name.encode('ascii').ljust(32, b'\x00')[:32]
    body += mask.encode('ascii').ljust(32, b'\x00')[:32]
    body += pack('<II', raster_format, d3d_format)
    body += pack('<HHBBBB', w, h, depth, num_levels, raster_type, flags)
    body += levels + extra
    return _chunk(0x15, _chunk(1, body, struct_lib) + _chunk(3, b''), lib)


def _txd(natives, count=None, struct_len=4, lib=LIB):
    if count is None:
        count = len(natives)
    st = pack('<HH', count, 0)
    if struct_len != 4:
        st = st.ljust(struct_len, b'\x00')[:struct_len]
    body = _chunk(1, st, lib) + b''.join(natives) + _chunk(3, b'', lib)
    return _chunk(0x16, body, lib)


def _has(items, tag):
    return any(tag in s for s in items)


# ── baseline ─────────────────────────────────────────────────────

def test_clean_txd_passes():
    fatal, warn = check_txd(_txd([_native(), _native("wall", 64, 32, DXT3)]))
    assert fatal == [] and warn == []


def test_no_mip_single_level_passes():
    fatal, warn = check_txd(_txd([_native(mip=False)]))
    assert fatal == [] and warn == []


def test_uncompressed_8888_passes():
    n = _native("u", 8, 8, fourcc=0, mip=False, raster_format=0x0500, flags=0x01,
                depth=32, bpp=32, d3d_format=21)
    fatal, warn = check_txd(_txd([n]))
    assert fatal == [] and warn == []


def test_vanilla_zero_size_small_dxt_levels_accepted():
    # vanilla stores size 0 for DXT levels below 4×4 (2×2, 1×1)
    n = _native(w=8, h=8, sizes={2: 0, 3: 0})
    fatal, warn = check_txd(_txd([n]))
    assert fatal == [] and warn == []


# ── dictionary level ─────────────────────────────────────────────

def test_struct_len_rules():
    fatal, _ = check_txd(_txd([_native()], struct_len=8))
    assert _has(fatal, "TXD-STRUCTLEN")
    fatal, _ = check_txd(_txd([_native()], struct_len=16))
    assert _has(fatal, "TXD-STRUCTLEN") and _has(fatal, "13")


def test_version_rules():
    fatal, _ = check_txd(_txd([_native()], lib=0x0C02FFFF))          # VC 3.3.0.2
    assert _has(fatal, "TXD-VERSION")
    fatal, _ = check_txd(_txd([_native(lib=0x1C020065)]))            # RW 3.7
    assert _has(fatal, "TXD-VERSION")
    fatal, _ = check_txd(_txd([_native(struct_lib=0x0310)]))
    assert _has(fatal, "TXD-VERSION")


def test_count_rules():
    fatal, _ = check_txd(_txd([_native()], count=2))
    assert _has(fatal, "TXD-COUNT")
    _, warn = check_txd(_txd([_native(), _native("b")], count=1))
    assert _has(warn, "TXD-COUNT")


def test_img_name_rule():
    fatal, _ = check_txd(_txd([_native()]), file_name="x" * 21 + ".txd")
    assert _has(fatal, "TXD-IMGNAME")
    fatal, _ = check_txd(_txd([_native()]), file_name="x" * 20 + ".txd")
    assert not _has(fatal, "TXD-IMGNAME")


# ── texture level ────────────────────────────────────────────────

def test_platform_rule():
    fatal, _ = check_txd(_txd([_native(platform=8)]))
    assert _has(fatal, "TXD-PLATFORM")
    fatal, _ = check_txd(_txd([_native(platform=8, flags=1)]), target='VC')
    assert not _has(fatal, "TXD-PLATFORM")


def test_name_rules():
    # Over-long name: the TXD still loads, the texture is just unreachable.
    fatal, warn = check_txd(_txd([_native(name="n" * 32)]))
    assert not _has(fatal, "TXD-NAME-LEN") and _has(warn, "TXD-NAME-LEN")
    _, warn = check_txd(_txd([_native(name="n" * 31)]))
    assert not _has(warn, "TXD-NAME-LEN")
    _, warn = check_txd(_txd([_native(name="")]))
    assert _has(warn, "TXD-NAME-LEN")
    _, warn = check_txd(_txd([_native("Brick"), _native("brick")]))
    assert _has(warn, "TXD-NAME-DUP")
    _, warn = check_txd(_txd([_native(mask="m" * 32)]))
    assert _has(warn, "TXD-MASK")


def test_filter_rules():
    _, warn = check_txd(_txd([_native(filt=0x1109)]))
    assert _has(warn, "TXD-FILTER")
    _, warn = check_txd(_txd([_native(filt=0x0006)]))
    assert _has(warn, "TXD-FILTER")


def test_raster_type_rules():
    fatal, _ = check_txd(_txd([_native(raster_type=1)]))
    assert _has(fatal, "TXD-RASTERTYPE")
    _, warn = check_txd(_txd([_native(raster_type=0)]))
    assert _has(warn, "TXD-RASTERTYPE")


def test_dimension_rules():
    n = _native(w=0, h=16, sizes={})
    fatal, _ = check_txd(_txd([n]))
    assert _has(fatal, "TXD-ZERO-DIM")
    _, warn = check_txd(_txd([_native(w=12, h=16, mip=False)]))
    assert _has(warn, "TXD-DIMS")
    _, warn = check_txd(_txd([_native(w=4096, h=4, mip=False)]))
    assert _has(warn, "TXD-DIMS")
    _, warn = check_txd(_txd([_native(w=2, h=2, mip=False)]))
    assert _has(warn, "TXD-DIMS")


def test_format_rules():
    fatal, _ = check_txd(_txd([_native(raster_format=0x2200 | 0x8000)]))
    assert _has(fatal, "TXD-PALETTE")
    fatal, _ = check_txd(_txd([_native(raster_format=0x1200 | 0x8000)]))
    assert _has(fatal, "TXD-AUTOMIP")
    fatal, _ = check_txd(_txd([_native(flags=0x0C)]))
    assert _has(fatal, "TXD-AUTOMIP")
    fatal, _ = check_txd(_txd([_native(flags=0x0A, mip=False)]))
    assert _has(fatal, "TXD-CUBE")
    fatal, _ = check_txd(_txd([_native(raster_format=0x8201)]))
    assert _has(fatal, "TXD-FORMAT-MISMATCH")
    fatal, _ = check_txd(_txd([_native(flags=0x00)]))                 # DXT fourcc, no bit3
    assert _has(fatal, "TXD-FORMAT-MISMATCH")
    fatal, _ = check_txd(_txd([_native(raster_format=0x8000)]))       # nibble 0 with DXT
    assert _has(fatal, "TXD-FORMAT-MISMATCH")
    n = _native("u", 8, 8, fourcc=0, mip=False, raster_format=0x0500, flags=0x01,
                depth=32, bpp=32, d3d_format=22)                     # 8888 needs 21
    fatal, _ = check_txd(_txd([n]))
    assert _has(fatal, "TXD-FORMAT-MISMATCH")
    n = _native("u", 8, 8, fourcc=0, mip=False, raster_format=0x0B00, flags=0x00,
                depth=32, bpp=32, d3d_format=0)
    fatal, _ = check_txd(_txd([n]))
    assert _has(fatal, "TXD-FORMAT-MISMATCH")
    _, warn = check_txd(_txd([_native(fourcc=DXT3, flags=0x08)]))
    assert _has(warn, "TXD-ALPHA-FLAG")


def test_num_levels_rules():
    fatal, _ = check_txd(_txd([_native(w=16, h=16, num_levels=6, extra=pack('<I', 0))]))
    assert _has(fatal, "TXD-NUMLEVELS-OVER")
    fatal, _ = check_txd(_txd([_native(mip=False, num_levels=2, extra=pack('<I', 0))]))
    assert _has(fatal, "TXD-NUMLEVELS-OVER")
    _, warn = check_txd(_txd([_native(mip=True, num_levels=0)]))
    assert _has(warn, "TXD-NUMLEVELS-UNDER")
    # MIPMAP flag, one level written: lost mips (DXT) — warning
    body_one, _ = _levels(16, 16, DXT1, False)
    n = _native(mip=False, raster_format=0x8200, num_levels=1)
    _, warn = check_txd(_txd([n]))
    assert _has(warn, "TXD-NUMLEVELS-UNDER")


def test_level_size_rules():
    fatal, _ = check_txd(_txd([_native(sizes={0: 256})]))            # 16×16 DXT1 = 128
    assert _has(fatal, "TXD-LEVEL-OVERSIZE")
    _, warn = check_txd(_txd([_native(sizes={0: 64})]))
    assert _has(warn, "TXD-LEVEL-SHORT")
    _, warn = check_txd(_txd([_native(sizes={0: 0})]))
    assert _has(warn, "TXD-LEVEL-SHORT")


def test_trailing_bytes_rule():
    fatal, _ = check_txd(_txd([_native(extra=bytes(8))]))
    assert _has(fatal, "TXD-STRUCT-TRAILING")
    # a level running past the STRUCT: shrink the declared STRUCT length
    n = bytearray(_native())
    struct_len = int.from_bytes(n[16:20], 'little')
    n[16:20] = pack('<I', struct_len - 8)
    fatal, _ = check_txd(_txd([bytes(n)]))
    assert _has(fatal, "TXD-STRUCT-TRAILING")


def test_d3d8_layout_for_vc_target():
    # D3D8: d3dFormat word is hasAlpha, flags byte is the DXT number.
    # Every chunk carries the VC lib id (3.4.0.3) — the VC exe rejects
    # streams newer than the RW it links.
    VC = 0x1003FFFF
    n = _native("w", 16, 16, fourcc=DXT1, mip=False, platform=8, raster_format=0x0200,
                flags=1, d3d_format=0, lib=VC, struct_lib=VC)
    fatal, warn = check_txd(_txd([n], lib=VC), target='VC')
    assert fatal == [] and warn == []


def test_version_range_per_target():
    """SA-versioned chunks are fatal for VC/III; VC's own version is fine
    for VC but too new for III."""
    VC, III = 0x1003FFFF, 0x0C02FFFF
    fatal, _ = check_txd(_txd([_native()]), target='VC')             # 3.6.0.3 → VC
    assert _has(fatal, "TXD-VERSION")
    n = _native(platform=8, flags=1, d3d_format=0, lib=VC, struct_lib=VC)
    fatal, _ = check_txd(_txd([n], lib=VC), target='III')            # 3.4.0.3 → III
    assert _has(fatal, "TXD-VERSION")
    n = _native(platform=8, flags=1, d3d_format=0, lib=III, struct_lib=III)
    fatal, _ = check_txd(_txd([n], lib=III), target='III')           # 3.3.0.2 → III
    assert not _has(fatal, "TXD-VERSION")
