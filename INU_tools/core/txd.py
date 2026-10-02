# INU_tools.core.txd
# GTA SA TXD (RenderWare Texture Dictionary) reader.
# Uses numpy for fast DXT decompression.

from __future__ import annotations

import numpy as np
from .rwbinary import BinaryReader


# RW chunk types
CHUNK_STRUCT = 1
CHUNK_EXTENSION = 3
CHUNK_TEX_NATIVE = 0x15
CHUNK_TEX_DICTIONARY = 0x16

# Raster format flags
RASTER_1555 = 0x0100
RASTER_565 = 0x0200
RASTER_4444 = 0x0300
RASTER_LUM8 = 0x0400
RASTER_8888 = 0x0500
RASTER_888 = 0x0600
RASTER_FORMAT_MASK = 0x0F00
RASTER_MIPMAP = 0x8000
RASTER_AUTOMIPMAP = 0x1000
RASTER_PAL8 = 0x2000
RASTER_PAL4 = 0x4000

# DXT FourCC codes
DXT1 = 0x31545844  # 'DXT1'
DXT2 = 0x32545844  # 'DXT2' — DXT3 with pre-multiplied alpha (same byte layout)
DXT3 = 0x33545844  # 'DXT3'
DXT4 = 0x34545844  # 'DXT4' — DXT5 with pre-multiplied alpha (same byte layout)
DXT5 = 0x35545844  # 'DXT5'


class TxdTexture:
    """Single texture extracted from TXD."""
    __slots__ = ('name', 'mask', 'width', 'height', 'depth',
                 'raster_format', 'fourcc', 'num_levels',
                 'platform_id', 'pixels')  # pixels: bytes (RGBA, top-to-bottom)

    def __init__(self):
        self.name = ''
        self.mask = ''
        self.width = 0
        self.height = 0
        self.depth = 0
        self.raster_format = 0
        self.fourcc = 0
        self.num_levels = 1
        self.platform_id = 0   # RW platform: 8=D3D8 (III/VC), 9=D3D9 (SA)
        self.pixels = b''  # RGBA uint8 array


# ── Numpy DXT decompression ──────────────────────────────────────

def _rgb565_decode(c):
    """Vectorized RGB565 → (R, G, B) arrays, each uint8."""
    r = ((c >> 11) & 0x1F).astype(np.uint16) * 255 // 31
    g = ((c >> 5) & 0x3F).astype(np.uint16) * 255 // 63
    b = (c & 0x1F).astype(np.uint16) * 255 // 31
    return r.astype(np.uint8), g.astype(np.uint8), b.astype(np.uint8)


def _build_dxt_color_palettes(c0, c1):
    """Build 4-entry RGBA palettes for all blocks. Returns (N, 4, 4) uint8 array."""
    r0, g0, b0 = _rgb565_decode(c0)
    r1, g1, b1 = _rgb565_decode(c1)
    n = len(c0)

    # Palette shape: (N, 4, 4) = N blocks, 4 entries, 4 channels (RGBA)
    pal = np.zeros((n, 4, 4), dtype=np.uint8)

    # Entry 0
    pal[:, 0, 0] = r0; pal[:, 0, 1] = g0; pal[:, 0, 2] = b0; pal[:, 0, 3] = 255
    # Entry 1
    pal[:, 1, 0] = r1; pal[:, 1, 1] = g1; pal[:, 1, 2] = b1; pal[:, 1, 3] = 255

    # Promote to uint16 for interpolation
    R0 = r0.astype(np.uint16); G0 = g0.astype(np.uint16); B0 = b0.astype(np.uint16)
    R1 = r1.astype(np.uint16); G1 = g1.astype(np.uint16); B1 = b1.astype(np.uint16)

    opaque = c0 > c1  # DXT1 opaque mode

    # Entry 2 (opaque: 2/3 + 1/3, transparent: 1/2 + 1/2)
    pal[:, 2, 0] = np.where(opaque, (2*R0 + R1) // 3, (R0 + R1) // 2).astype(np.uint8)
    pal[:, 2, 1] = np.where(opaque, (2*G0 + G1) // 3, (G0 + G1) // 2).astype(np.uint8)
    pal[:, 2, 2] = np.where(opaque, (2*B0 + B1) // 3, (B0 + B1) // 2).astype(np.uint8)
    pal[:, 2, 3] = 255

    # Entry 3 (opaque: 1/3 + 2/3, transparent: 0,0,0,0)
    pal[:, 3, 0] = np.where(opaque, (R0 + 2*R1) // 3, 0).astype(np.uint8)
    pal[:, 3, 1] = np.where(opaque, (G0 + 2*G1) // 3, 0).astype(np.uint8)
    pal[:, 3, 2] = np.where(opaque, (B0 + 2*B1) // 3, 0).astype(np.uint8)
    pal[:, 3, 3] = np.where(opaque, 255, 0).astype(np.uint8)

    return pal


def _decode_color_indices(indices_u32):
    """Decode 32-bit index word → (N, 16) array of 2-bit indices."""
    n = len(indices_u32)
    # 16 pixels per block, each 2 bits
    idx = np.zeros((n, 16), dtype=np.uint8)
    for i in range(16):
        idx[:, i] = (indices_u32 >> (i * 2)) & 3
    return idx


def _scatter_blocks(block_colors, bw, bh, width, height):
    """Scatter block pixel data into (height, width, 4) image.
    block_colors: (N, 16, 4) where N = bw*bh, 16 pixels in row-major 4x4.
    """
    # Reshape to (bh, bw, 4rows, 4cols, 4rgba)
    blocks = block_colors.reshape(bh, bw, 4, 4, 4)
    # Transpose to (bh, 4rows, bw, 4cols, 4rgba) then merge
    # → (bh*4, bw*4, 4)
    img = blocks.transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    # Crop to actual size (in case width/height not multiple of 4)
    return img[:height, :width].copy()


def _decompress_dxt1(data, width, height):
    """Decompress DXT1 data to RGBA bytes using numpy."""
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    n_blocks = bw * bh
    expected = n_blocks * 8

    arr = np.frombuffer(data[:expected], dtype=np.uint8)
    if len(arr) < expected:
        arr = np.pad(arr, (0, expected - len(arr)))

    # Reshape: each block = 8 bytes
    blocks = arr.reshape(n_blocks, 8)

    # Parse c0, c1, indices
    c0 = blocks[:, 0].astype(np.uint16) | (blocks[:, 1].astype(np.uint16) << 8)
    c1 = blocks[:, 2].astype(np.uint16) | (blocks[:, 3].astype(np.uint16) << 8)
    idx_u32 = (blocks[:, 4].astype(np.uint32) |
               (blocks[:, 5].astype(np.uint32) << 8) |
               (blocks[:, 6].astype(np.uint32) << 16) |
               (blocks[:, 7].astype(np.uint32) << 24))

    pal = _build_dxt_color_palettes(c0, c1)  # (N, 4, 4)
    indices = _decode_color_indices(idx_u32)  # (N, 16)

    # Lookup: for each block and each pixel, pick palette entry
    # pal[block_i, indices[block_i, pixel_i]] → (N, 16, 4)
    block_i = np.arange(n_blocks)[:, None]  # (N, 1)
    colors = pal[block_i, indices]  # (N, 16, 4)

    # Reshape 16 pixels → 4x4
    colors = colors.reshape(n_blocks, 4, 4, 4)

    out = _scatter_blocks(colors.reshape(n_blocks, 16, 4), bw, bh, width, height)
    return out.tobytes()


def _decompress_dxt3(data, width, height):
    """Decompress DXT3 data to RGBA bytes using numpy."""
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    n_blocks = bw * bh
    expected = n_blocks * 16

    arr = np.frombuffer(data[:expected], dtype=np.uint8)
    if len(arr) < expected:
        arr = np.pad(arr, (0, expected - len(arr)))

    blocks = arr.reshape(n_blocks, 16)

    # Alpha block: first 8 bytes (64 bits, 4 bits per pixel, 16 pixels)
    alpha_bytes = blocks[:, :8]  # (N, 8)
    # Each byte has 2 x 4-bit alpha values
    alpha_lo = alpha_bytes & 0x0F
    alpha_hi = (alpha_bytes >> 4) & 0x0F
    # Interleave: byte0_lo, byte0_hi, byte1_lo, byte1_hi, ...
    alpha_4bit = np.zeros((n_blocks, 16), dtype=np.uint8)
    for i in range(8):
        alpha_4bit[:, i*2] = alpha_lo[:, i]
        alpha_4bit[:, i*2+1] = alpha_hi[:, i]
    alpha_8bit = (alpha_4bit << 4) | alpha_4bit  # 4-bit → 8-bit

    # Color block: bytes 8-15
    color_block = blocks[:, 8:16]
    c0 = color_block[:, 0].astype(np.uint16) | (color_block[:, 1].astype(np.uint16) << 8)
    c1 = color_block[:, 2].astype(np.uint16) | (color_block[:, 3].astype(np.uint16) << 8)
    idx_u32 = (color_block[:, 4].astype(np.uint32) |
               (color_block[:, 5].astype(np.uint32) << 8) |
               (color_block[:, 6].astype(np.uint32) << 16) |
               (color_block[:, 7].astype(np.uint32) << 24))

    pal = _build_dxt_color_palettes(c0, c1)
    indices = _decode_color_indices(idx_u32)

    block_i = np.arange(n_blocks)[:, None]
    colors = pal[block_i, indices]  # (N, 16, 4)

    # Override alpha channel
    colors[:, :, 3] = alpha_8bit

    colors = colors.reshape(n_blocks, 4, 4, 4)
    out = _scatter_blocks(colors.reshape(n_blocks, 16, 4), bw, bh, width, height)
    return out.tobytes()


def _decompress_dxt5(data, width, height):
    """Decompress DXT5 data to RGBA bytes using numpy."""
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    n_blocks = bw * bh
    expected = n_blocks * 16

    arr = np.frombuffer(data[:expected], dtype=np.uint8)
    if len(arr) < expected:
        arr = np.pad(arr, (0, expected - len(arr)))

    blocks = arr.reshape(n_blocks, 16)

    # Alpha block: bytes 0-7
    a0 = blocks[:, 0].astype(np.uint16)
    a1 = blocks[:, 1].astype(np.uint16)

    # 48-bit alpha index data (bytes 2-7)
    abits = (blocks[:, 2].astype(np.uint64) |
             (blocks[:, 3].astype(np.uint64) << 8) |
             (blocks[:, 4].astype(np.uint64) << 16) |
             (blocks[:, 5].astype(np.uint64) << 24) |
             (blocks[:, 6].astype(np.uint64) << 32) |
             (blocks[:, 7].astype(np.uint64) << 40))

    # Build 8-entry alpha LUT per block: (N, 8)
    alut = np.zeros((n_blocks, 8), dtype=np.uint8)
    alut[:, 0] = a0.astype(np.uint8)
    alut[:, 1] = a1.astype(np.uint8)

    hi = a0 > a1
    # High mode (a0 > a1): 6 interpolated values
    alut[:, 2] = np.where(hi, (6*a0 + 1*a1) // 7, (4*a0 + 1*a1) // 5).astype(np.uint8)
    alut[:, 3] = np.where(hi, (5*a0 + 2*a1) // 7, (3*a0 + 2*a1) // 5).astype(np.uint8)
    alut[:, 4] = np.where(hi, (4*a0 + 3*a1) // 7, (2*a0 + 3*a1) // 5).astype(np.uint8)
    alut[:, 5] = np.where(hi, (3*a0 + 4*a1) // 7, (1*a0 + 4*a1) // 5).astype(np.uint8)
    alut[:, 6] = np.where(hi, (2*a0 + 5*a1) // 7, 0).astype(np.uint8)
    alut[:, 7] = np.where(hi, (1*a0 + 6*a1) // 7, 255).astype(np.uint8)

    # Decode 16 x 3-bit alpha indices
    alpha_idx = np.zeros((n_blocks, 16), dtype=np.uint8)
    for i in range(16):
        alpha_idx[:, i] = ((abits >> (i * 3)) & 7).astype(np.uint8)

    # Lookup alpha values
    bi = np.arange(n_blocks)[:, None]
    alpha_vals = alut[bi, alpha_idx]  # (N, 16)

    # Color block: bytes 8-15
    color_block = blocks[:, 8:16]
    c0 = color_block[:, 0].astype(np.uint16) | (color_block[:, 1].astype(np.uint16) << 8)
    c1 = color_block[:, 2].astype(np.uint16) | (color_block[:, 3].astype(np.uint16) << 8)
    idx_u32 = (color_block[:, 4].astype(np.uint32) |
               (color_block[:, 5].astype(np.uint32) << 8) |
               (color_block[:, 6].astype(np.uint32) << 16) |
               (color_block[:, 7].astype(np.uint32) << 24))

    pal = _build_dxt_color_palettes(c0, c1)
    indices = _decode_color_indices(idx_u32)

    colors = pal[bi, indices]  # (N, 16, 4)
    colors[:, :, 3] = alpha_vals

    colors = colors.reshape(n_blocks, 4, 4, 4)
    out = _scatter_blocks(colors.reshape(n_blocks, 16, 4), bw, bh, width, height)
    return out.tobytes()


def _decode_uncompressed(data, width, height, raster_fmt, depth):
    """Decode uncompressed raster data to RGBA using numpy."""
    fmt = raster_fmt & RASTER_FORMAT_MASK
    n_pixels = width * height

    if fmt == RASTER_8888:
        arr = np.frombuffer(data[:n_pixels*4], dtype=np.uint8).reshape(-1, 4).copy()
        # BGRA → RGBA: swap R and B
        arr[:, [0, 2]] = arr[:, [2, 0]]
        return arr.tobytes()
    elif fmt == RASTER_888:
        if depth == 32 or len(data) >= n_pixels * 4:
            # 888 stored as 32-bit BGRX (4 bytes per pixel, X=padding)
            arr = np.frombuffer(data[:n_pixels*4], dtype=np.uint8).reshape(-1, 4).copy()
            arr[:, [0, 2]] = arr[:, [2, 0]]  # BGRA → RGBA
            arr[:, 3] = 255  # force opaque
            return arr.tobytes()
        else:
            # True 24-bit (3 bytes per pixel)
            arr = np.frombuffer(data[:n_pixels*3], dtype=np.uint8).reshape(-1, 3)
            out = np.empty((n_pixels, 4), dtype=np.uint8)
            out[:, 0] = arr[:, 2]  # B→R
            out[:, 1] = arr[:, 1]  # G
            out[:, 2] = arr[:, 0]  # R→B
            out[:, 3] = 255
            return out.tobytes()
    elif fmt == RASTER_565:
        raw = np.frombuffer(data[:n_pixels*2], dtype=np.uint16)
        out = np.empty((n_pixels, 4), dtype=np.uint8)
        out[:, 0] = (((raw >> 11) & 0x1F).astype(np.uint16) * 255 // 31).astype(np.uint8)
        out[:, 1] = (((raw >> 5) & 0x3F).astype(np.uint16) * 255 // 63).astype(np.uint8)
        out[:, 2] = ((raw & 0x1F).astype(np.uint16) * 255 // 31).astype(np.uint8)
        out[:, 3] = 255
        return out.tobytes()
    elif fmt == RASTER_1555:
        raw = np.frombuffer(data[:n_pixels*2], dtype=np.uint16)
        out = np.empty((n_pixels, 4), dtype=np.uint8)
        out[:, 0] = (((raw >> 10) & 0x1F).astype(np.uint16) * 255 // 31).astype(np.uint8)
        out[:, 1] = (((raw >> 5) & 0x1F).astype(np.uint16) * 255 // 31).astype(np.uint8)
        out[:, 2] = ((raw & 0x1F).astype(np.uint16) * 255 // 31).astype(np.uint8)
        out[:, 3] = np.where(raw >> 15, 255, 0).astype(np.uint8)
        return out.tobytes()
    elif fmt == RASTER_4444:
        raw = np.frombuffer(data[:n_pixels*2], dtype=np.uint16)
        out = np.empty((n_pixels, 4), dtype=np.uint8)
        out[:, 0] = (((raw >> 8) & 0x0F).astype(np.uint16) * 255 // 15).astype(np.uint8)
        out[:, 1] = (((raw >> 4) & 0x0F).astype(np.uint16) * 255 // 15).astype(np.uint8)
        out[:, 2] = ((raw & 0x0F).astype(np.uint16) * 255 // 15).astype(np.uint8)
        out[:, 3] = (((raw >> 12) & 0x0F).astype(np.uint16) * 255 // 15).astype(np.uint8)
        return out.tobytes()
    else:
        # Fallback: try 32-bit BGRA
        if len(data) >= n_pixels * 4:
            arr = np.frombuffer(data[:n_pixels*4], dtype=np.uint8).reshape(-1, 4).copy()
            arr[:, [0, 2]] = arr[:, [2, 0]]
            return arr.tobytes()
        return b'\x00' * (n_pixels * 4)


# ── TXD Reader ──────────────────────────────────────────────────

def _read_chunk_header(r):
    """Read 12-byte RW chunk header."""
    ct, cs, cl = r.read('<III')
    return ct, cs, cl


def _read_str32(r):
    """Read 32-byte null-terminated string."""
    raw = r.read_bytes(32)
    end = raw.find(b'\x00')
    if end == -1:
        end = 32
    return raw[:end].decode('ascii', errors='replace')


def _read_texture_native(r, size):
    """Read a single Texture Native chunk's Struct data."""
    tex = TxdTexture()

    # Struct header
    ct, cs, cl = _read_chunk_header(r)
    struct_end = r.pos + cs

    # Platform header — platform_id (8=D3D8 III/VC, 9=D3D9 SA) + filter flags.
    # platform_id drives the R↔B swap on import (D3D8 textures come in with
    # swapped channels through our decoder). filter_flags unused.
    tex.platform_id = r.read_one('<I')
    r.read_one('<I')

    tex.name = _read_str32(r)
    tex.mask = _read_str32(r)

    # Raster format
    tex.raster_format = r.read_one('<I')
    tex.fourcc = r.read_one('<I')  # D3D FourCC or has_alpha
    tex.width = r.read_one('<H')
    tex.height = r.read_one('<H')
    tex.depth = r.read_one('<B')
    tex.num_levels = r.read_one('<B')
    r.read_one('<B')                 # raster_type (unused)
    compression_flag = r.read_one('<B')

    # D3D native streams: PAL8 = 256 entries, PAL4 = 32 entries (16 used).
    # librw d3d8.cpp / d3d9.cpp read 4*32 for PAL4; indices are still bytes.
    has_pal8 = bool(tex.raster_format & RASTER_PAL8)
    has_pal4 = bool(tex.raster_format & RASTER_PAL4)
    has_palette = has_pal8 or has_pal4
    palette = None
    if has_palette:
        count = 32 if has_pal4 else 256
        pal_data = r.read_bytes(count * 4)
        palette = np.frombuffer(pal_data, dtype=np.uint8).reshape(count, 4).copy()
        # Both platforms store RGBA. Keep the historical D3D8 core result:
        # ops/txd_import applies its compensating swap for paletted D3D8.
        # D3D9 has no compensating swap and must already be RGBA here.
        if tex.platform_id == 8:
            palette[:, [0, 2]] = palette[:, [2, 0]]

    # Mip level 0 (we only need the largest)
    data_size = r.read_one('<I')
    raw_data = r.read_bytes(data_size)

    # Decompress / decode pixel data
    w, h = tex.width, tex.height

    # Detect real compression: if data matches uncompressed size, it's not DXT
    expected_uncompressed = w * h * max(tex.depth, 8) // 8
    really_compressed = (data_size < expected_uncompressed) if expected_uncompressed > 0 else False

    # DXT compression takes priority over palette flags. FOURCC is the
    # reliable signal: GTA SA fence/foliage textures (a_fence_*) are
    # DXT4 with depth=8, where the size-heuristic ``really_compressed``
    # is False (data_size matches the depth-implied uncompressed size),
    # and the texture would otherwise mis-route into _decode_uncompressed.
    # When fourcc says DXT, trust it — that's a true compression mark
    # written by the encoder. DXT2/DXT4 share byte layouts with DXT3/DXT5.
    if tex.fourcc == DXT1 or (compression_flag == 1 and really_compressed):
        tex.pixels = _decompress_dxt1(raw_data, w, h)
    elif tex.fourcc in (DXT2, DXT3) or (compression_flag in (2, 3) and really_compressed):
        tex.pixels = _decompress_dxt3(raw_data, w, h)
    elif tex.fourcc in (DXT4, DXT5) or (compression_flag in (4, 5) and really_compressed):
        tex.pixels = _decompress_dxt5(raw_data, w, h)
    elif has_palette and palette is not None:
        indices = np.frombuffer(raw_data[:w*h], dtype=np.uint8)
        tex.pixels = palette[indices].tobytes()
    else:
        # Check if data looks compressed (too small for uncompressed)
        expected = w * h * max(tex.depth, 8) // 8
        if data_size < expected and not has_palette and w >= 4 and h >= 4:
            # Likely compressed but not detected — try DXT by data size
            bw = max(1, (w + 3) // 4)
            bh = max(1, (h + 3) // 4)
            if data_size <= bw * bh * 8:
                tex.pixels = _decompress_dxt1(raw_data, w, h)
            else:
                tex.pixels = _decompress_dxt5(raw_data, w, h)
        else:
            tex.pixels = _decode_uncompressed(raw_data, w, h, tex.raster_format, tex.depth)

    r.seek(struct_end)

    # Skip extension
    if r.pos < size:
        ct2, cs2, cl2 = _read_chunk_header(r)
        r.skip(cs2)

    return tex


def read_txd(data: bytes) -> list:
    """
    Parse TXD binary data.
    Returns list of TxdTexture objects.
    """
    r = BinaryReader(data)
    textures = []

    # TXD Dictionary header
    ct, cs, cl = _read_chunk_header(r)
    if ct != CHUNK_TEX_DICTIONARY:
        raise ValueError(f"Expected Texture Dictionary (0x16), got 0x{ct:X}")

    # Struct: texture count
    ct, cs, cl = _read_chunk_header(r)
    tex_count = r.read_one('<H')
    r.read_one('<H')                  # device_id (unused)
    r.seek(r.pos + cs - 4)  # skip rest of struct

    # Read textures
    for _ in range(tex_count):
        ct, cs, cl = _read_chunk_header(r)
        chunk_end = r.pos + cs

        if ct == CHUNK_TEX_NATIVE:
            # Snapshot position for fallback diagnostics — if the texture
            # crashed early we can still pull format details out of the
            # raw chunk to figure out which decoder branch went wrong.
            chunk_start = r.pos
            try:
                tex = _read_texture_native(r, chunk_end)
                textures.append(tex)
            except Exception as e:
                # Best-effort header decode so the user can match the
                # failing texture to a specific asset AND we see enough
                # to diagnose the decoder bug remotely.
                tex_name = "<unknown>"
                fmt_info = "?"
                try:
                    r.seek(chunk_start)
                    _read_chunk_header(r)            # struct header
                    r.read_one('<I'); r.read_one('<I')  # platform / filter
                    name_bytes = r.read_bytes(32)
                    tex_name = (name_bytes.split(b'\x00', 1)[0]
                                .decode('ascii', errors='replace'))
                    r.read_bytes(32)                  # mask
                    raster_format = r.read_one('<I')
                    fourcc = r.read_one('<I')
                    w = r.read_one('<H'); h = r.read_one('<H')
                    depth = r.read_one('<B')
                    num_levels = r.read_one('<B')
                    r.read_one('<B')                  # raster_type
                    compression_flag = r.read_one('<B')
                    fmt_info = (
                        f"{w}x{h} depth={depth} "
                        f"raster_format=0x{raster_format:X} "
                        f"fourcc=0x{fourcc:X} "
                        f"compr={compression_flag} "
                        f"levels={num_levels}"
                    )
                except Exception:
                    pass
                # Non-fatal: this texture is skipped, the rest of the TXD
                # continues to load. The error stays in the console for
                # the user to investigate / report.
                print(f"[INU_tools TXD] Error reading texture "
                      f"{tex_name!r} ({fmt_info}): {e}")

        r.seek(chunk_end)

    return textures


def read_txd_file(filepath: str) -> list:
    """Read a TXD file and return list of TxdTexture."""
    with open(filepath, 'rb') as f:
        return read_txd(f.read())


def read_txd_texture_names(filepath: str) -> list[str]:
    """Return only the texture names from a TXD — no pixel decoding,
    no palette parsing. ~50× faster than ``read_txd_file`` and used by
    auto-TXD selection in DFF import to score candidate .txd files
    against the just-imported material set without paying the full
    decompression cost.

    Returns ``[]`` on parse failure (caller can treat as zero matches).
    """
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except OSError:
        return []

    try:
        r = BinaryReader(data)
        ct, cs, cl = _read_chunk_header(r)
        if ct != CHUNK_TEX_DICTIONARY:
            return []
        # struct: texture count + device_id (skip rest of struct)
        ct, cs, cl = _read_chunk_header(r)
        tex_count = r.read_one('<H')
        r.read_one('<H')  # device_id
        r.seek(r.pos + cs - 4)

        names = []
        for _ in range(tex_count):
            ct, cs, cl = _read_chunk_header(r)
            chunk_end = r.pos + cs
            if ct == CHUNK_TEX_NATIVE:
                # Inside the Texture Native: another Struct chunk header,
                # then platform_id(u32) + filter_flags(u32) + name(32B).
                _ = _read_chunk_header(r)  # struct header
                r.read('<II')  # platform + filter flags
                names.append(_read_str32(r))
            r.seek(chunk_end)
        return names
    except Exception:
        return []


def split_txd_sections(data: bytes):
    """Split a TXD container into its Texture-Native chunks WITHOUT decoding
    pixel data.

    Returns ``(lib_id, [(name, section_bytes), …])`` where ``section_bytes``
    is the COMPLETE 0x15 chunk (12-byte header + body), copied verbatim — so
    existing textures round-trip byte-for-byte. This is what lets us MERGE
    new textures into a TXD while leaving every other model's textures
    untouched (see ``tools.txd_export.update_txd``).

    Returns ``(None, [])`` if ``data`` is not a Texture Dictionary or on any
    parse error (caller falls back to a plain full export)."""
    try:
        r = BinaryReader(data)
        ct, cs, lib_id = _read_chunk_header(r)
        if ct != CHUNK_TEX_DICTIONARY:
            return None, []
        # Struct: texture count + device_id (skip rest of struct).
        sct, scs, scl = _read_chunk_header(r)
        tex_count = r.read_one('<H')
        r.read_one('<H')  # device_id
        r.seek(r.pos + scs - 4)

        out = []
        for _ in range(tex_count):
            start = r.pos
            tct, tcs, tcl = _read_chunk_header(r)
            section_end = r.pos + tcs
            if tct == CHUNK_TEX_NATIVE:
                # Read name: nested Struct header, then platform + filter,
                # then the 32-byte name. Then rewind and grab the chunk
                # verbatim (header included) so it re-emits unchanged.
                _ = _read_chunk_header(r)        # struct header
                r.read('<II')                    # platform + filter flags
                name = _read_str32(r)
                out.append((name, bytes(data[start:section_end])))
            r.seek(section_end)
        return lib_id, out
    except Exception:
        return None, []
