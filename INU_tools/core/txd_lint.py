# INU_tools.core.txd_lint
# Post-write audit of a TXD file image against what gta_sa.exe's
# CTxdStore::LoadTxd → RwTexDictionaryGtaStreamRead → _rwD3D9NativeTextureRead
# actually check (very little) and then dereference. Pure Python, no
# Blender dependency — runs on the assembled bytes right after
# tools.txd_export writes them (the encoder emits sections, not
# structures, so the file image is the natural unit to audit; it also
# covers the verbatim sections kept by the merge path).
#
# Every rule cites the engine finding it mirrors (TXD-* in
# E:\RE\addon_check\txd_path.md + its verification pass). Severity:
#   fatal   — the engine crashes, or the whole dictionary fails to load
#             (LOAD-FAIL: every model that needs it stays invisible and
#             the streamer re-requests it forever);
#   warning — it loads but a texture renders wrong or is unreachable.
#
# Calibrated against the 25 vanilla TXDs in E:\RE\addon_check\map\txd:
# zero fatals; the D3D8 misc.txd / PAL8 outro.txd (III/VC-era leftovers
# the SA engine cannot load either) are reported when checked for SA.

import math
import os
from struct import unpack_from, error as StructError

CHUNK_STRUCT = 1
CHUNK_EXTENSION = 3
CHUNK_TEX_NATIVE = 0x15
CHUNK_TEX_DICTIONARY = 0x16

PLATFORM_D3D8 = 8
PLATFORM_D3D9 = 9
# Stream versions each exe accepts (rwLIBRARYBASEVERSION..CURRENTVERSION of
# the RW build it links): SA 3.6.0.3, VC PC 3.4.0.3, III PC 3.3.0.2. A chunk
# newer than the engine is rejected — that's why an SA-versioned TXD never
# loads in VC.
RW_VERSION_RANGE = {
    'SA':  (0x34000, 0x36003),
    'VC':  (0x30000, 0x34003),
    'III': (0x30000, 0x33002),
}
RW_VERSION_MIN, RW_VERSION_MAX = RW_VERSION_RANGE['SA']   # kept for callers
RASTER_FORMAT_MASK = 0x0F00
RASTER_AUTOMIPMAP = 0x1000
RASTER_PAL8 = 0x2000
RASTER_PAL4 = 0x4000
RASTER_MIPMAP = 0x8000
FLAG_HAS_ALPHA = 0x1
FLAG_CUBE = 0x2
FLAG_AUTO_MIPMAP = 0x4
FLAG_COMPRESSED = 0x8
RASTER_TYPE_TEXTURE = 4
NAME_MAX = 31                 # TXD-NAME-LEN: name[31] forced to NUL
IMG_BASENAME_MAX = 20         # TXD-IMGNAME: '.' must sit at offset <= 20
MAX_SAFE_DIM = 2048           # TXD-DIMS: caps of older cards
DXT_FOURCC = {
    0x31545844: 8, 0x32545844: 16, 0x33545844: 16, 0x34545844: 16, 0x35545844: 16,
}
# rasterFormat nibble → (D3DFORMAT, bits per pixel) — table 0x85C670.
UNCOMPRESSED_TABLE = {
    0x1: (25, 16), 0x2: (23, 16), 0x3: (26, 16), 0x4: (50, 8),
    0x5: (21, 32), 0x6: (22, 32), 0xA: (24, 16),
}
FILTER_MIN, FILTER_MAX = 1, 6
ADDRESS_MIN, ADDRESS_MAX = 1, 4


def _t(s: str) -> str:
    """Lazy translation — falls back to the raw Russian string outside
    Blender (standalone unit tests)."""
    try:
        from .. import T
        return T(s)
    except Exception:
        return s


def _decode_version(lib_id: int) -> int:
    if lib_id & 0xFFFF0000:
        return (((lib_id >> 14) & 0x3FF00) + 0x30000) | ((lib_id >> 16) & 0x3F)
    return lib_id << 8


def _version_ok(lib_id: int, target: str = 'SA') -> bool:
    lo, hi = RW_VERSION_RANGE.get(target, RW_VERSION_RANGE['SA'])
    return lo <= _decode_version(lib_id) <= hi


def _rw_text(v: int) -> str:
    return f"{(v >> 16) & 0xF}.{(v >> 12) & 0xF}.{(v >> 8) & 0xF}.{v & 0xFF}"


def _version_range_text(target: str) -> str:
    lo, hi = RW_VERSION_RANGE.get(target, RW_VERSION_RANGE['SA'])
    return f"{_rw_text(lo)}..{_rw_text(hi)}"


def _level_bytes(w: int, h: int, level: int, fourcc: int, bpp: int) -> int:
    lw = max(1, w >> level)
    lh = max(1, h >> level)
    if fourcc in DXT_FOURCC:
        return max(1, (lw + 3) // 4) * max(1, (lh + 3) // 4) * DXT_FOURCC[fourcc]
    return lw * bpp // 8 * lh


def _cstr(raw: bytes):
    """(text, has_nul) for a fixed 32-byte name field."""
    end = raw.find(b'\x00')
    if end < 0:
        return raw.decode('ascii', errors='replace'), False
    return raw[:end].decode('ascii', errors='replace'), True


def _check_texture(idx: int, data: bytes, off: int, end: int, target: str,
                   seen: dict, fatal, warnings):
    """One Texture Native chunk body (``off`` = start of its STRUCT header)."""
    label = f'#{idx}'
    try:
        st, slen, slib = unpack_from('<III', data, off)
        if st != CHUNK_STRUCT:
            fatal.append(_t(
                "TXD, текстура {0}: за заголовком Texture Native нет STRUCT — RwStreamFindChunk уйдёт в конец файла, словарь не загрузится (TXD-STRUCT-TRAILING)."
            ).format(label))
            return
        if not _version_ok(slib, target):
            fatal.append(_t(
                "TXD, текстура {0}: версия RW 0x{1:X} вне {2} — чанк отвергается, словарь не загрузится (TXD-VERSION)."
            ).format(label, _decode_version(slib), _version_range_text(target)))
        p = off + 12
        payload_end = p + slen
        if payload_end > end or slen < 0x58:
            fatal.append(_t(
                "TXD, текстура {0}: STRUCT длиной {1} байт короче заголовка растра — словарь не загрузится (TXD-STRUCT-TRAILING)."
            ).format(label, slen))
            return
        platform, filt = unpack_from('<II', data, p)
        name, name_nul = _cstr(data[p + 8:p + 40])
        mask, _ = _cstr(data[p + 40:p + 72])
        raster_format, d3d_format = unpack_from('<II', data, p + 72)
        width, height, depth, num_levels, raster_type, flags = unpack_from('<HHBBBB', data, p + 80)
        p += 0x58
    except StructError:
        fatal.append(_t(
            "TXD, текстура {0}: обрезанный заголовок Texture Native (TXD-STRUCT-TRAILING)."
        ).format(label))
        return
    label = f'«{name}»' if name else label

    # TXD-PLATFORM
    want = PLATFORM_D3D9 if target == 'SA' else PLATFORM_D3D8
    if platform != want:
        fatal.append(_t(
            "TXD, текстура {0}: platform {1} вместо {2} — _rwD3D9NativeTextureRead вернёт 0, словарь не загрузится (TXD-PLATFORM)."
        ).format(label, platform, want))

    # TXD-NAME-LEN / TXD-NAME-DUP
    if not name:
        warnings.append(_t(
            "TXD, текстура {0}: пустое имя — ни один материал её не найдёт (TXD-NAME-LEN)."
        ).format(f'#{idx}'))
    elif not name_nul or len(name) > NAME_MAX:
        # The dictionary still loads (name[31] is just forced to NUL) —
        # the texture is unreachable, not a crash → warning.
        warnings.append(_t(
            "TXD, текстура {0}: имя длиннее {1} символов — движок обрежет до 31, и материал DFF с полным именем её не найдёт (TXD-NAME-LEN)."
        ).format(label, NAME_MAX))
    if len(mask) > NAME_MAX:
        warnings.append(_t(
            "TXD, текстура {0}: имя маски длиннее {1} символов — обрежется (TXD-MASK)."
        ).format(label, NAME_MAX))
    key = name.lower()
    if key in seen:
        warnings.append(_t(
            "TXD, текстура {0}: имя повторяет текстуру #{1} — движок берёт последнюю в файле, обе остаются в памяти (TXD-NAME-DUP)."
        ).format(label, seen[key]))
    else:
        seen[key] = idx

    # TXD-FILTER
    f_mode = filt & 0xFF
    addr_u = (filt >> 8) & 0xF
    addr_v = (filt >> 12) & 0xF
    if not (FILTER_MIN <= f_mode <= FILTER_MAX):
        warnings.append(_t(
            "TXD, текстура {0}: фильтр {1} вне 1..6 — SetSamplerState получит мусор из таблицы (TXD-FILTER)."
        ).format(label, f_mode))
    if not (ADDRESS_MIN <= addr_u <= ADDRESS_MAX and ADDRESS_MIN <= addr_v <= ADDRESS_MAX):
        warnings.append(_t(
            "TXD, текстура {0}: адресация UV {1}/{2} вне 1..4 — SetSamplerState получит мусор из таблицы (TXD-FILTER)."
        ).format(label, addr_u, addr_v))

    # TXD-RASTERTYPE
    if raster_type != RASTER_TYPE_TEXTURE:
        if raster_type == 0:
            warnings.append(_t(
                "TXD, текстура {0}: rasterType 0 вместо 4 — грузится, но не как текстура по умолчанию (TXD-RASTERTYPE)."
            ).format(label))
        else:
            fatal.append(_t(
                "TXD, текстура {0}: rasterType {1} вместо 4 — создание растра или lock провалятся, словарь не загрузится или игра упадёт (TXD-RASTERTYPE)."
            ).format(label, raster_type))

    # TXD-ZERO-DIM / TXD-DIMS
    if width == 0 or height == 0:
        fatal.append(_t(
            "TXD, текстура {0}: размер {1}×{2} — растр без D3D-текстуры, RwRasterLock разыменует NULL (TXD-ZERO-DIM)."
        ).format(label, width, height))
    else:
        if (width & (width - 1)) or (height & (height - 1)):
            warnings.append(_t(
                "TXD, текстура {0}: размер {1}×{2} не степень двойки — на картах с POW2 словарь не загрузится (TXD-DIMS)."
            ).format(label, width, height))
        if width > MAX_SAFE_DIM or height > MAX_SAFE_DIM:
            warnings.append(_t(
                "TXD, текстура {0}: размер {1}×{2} больше {3} — превышает лимит старых карт (TXD-DIMS)."
            ).format(label, width, height, MAX_SAFE_DIM))

    # TXD-FORMAT-MISMATCH / TXD-PALETTE / TXD-AUTOMIP / TXD-CUBE
    nibble = (raster_format & RASTER_FORMAT_MASK) >> 8
    if platform == PLATFORM_D3D8:
        # D3D8 layout (III/VC): the d3dFormat word is ``hasAlpha`` and the
        # flags byte is the DXT number (0 = uncompressed). Normalise to
        # the D3D9 view so the size rules below apply unchanged.
        dxt_n = flags
        d3d_format = {1: 0x31545844, 2: 0x32545844, 3: 0x33545844,
                      4: 0x34545844, 5: 0x35545844}.get(dxt_n, 0)
        flags = FLAG_COMPRESSED if dxt_n else 0
        if d3d_format == 0 and nibble in UNCOMPRESSED_TABLE:
            d3d_format = UNCOMPRESSED_TABLE[nibble][0]
    compressed = bool(flags & FLAG_COMPRESSED)
    is_dxt = d3d_format in DXT_FOURCC
    bpp = 0
    if raster_format & (RASTER_PAL4 | RASTER_PAL8):
        fatal.append(_t(
            "TXD, текстура {0}: палитровый формат (PAL4/PAL8) — D3DFMT_P8 не поддерживает ни один современный драйвер, словарь не загрузится (TXD-PALETTE)."
        ).format(label))
    if raster_format & RASTER_AUTOMIPMAP or flags & FLAG_AUTO_MIPMAP:
        fatal.append(_t(
            "TXD, текстура {0}: автогенерация мипов (0x1000 / флаг 4) — читается один уровень, остальные байты ломают поток (TXD-AUTOMIP)."
        ).format(label))
    if flags & FLAG_CUBE:
        fatal.append(_t(
            "TXD, текстура {0}: флаг cube map — несжатые кубы не грузятся вовсе, сжатые ждут 6 граней (TXD-CUBE)."
        ).format(label))
    if raster_format & 0xFF or raster_format & ~0xFFFF:
        fatal.append(_t(
            "TXD, текстура {0}: rasterFormat 0x{1:X} содержит лишние биты — сравнение с растром не сойдётся, словарь не загрузится (TXD-FORMAT-MISMATCH)."
        ).format(label, raster_format))
    if compressed != is_dxt:
        fatal.append(_t(
            "TXD, текстура {0}: флаг compressed={1}, а d3dFormat 0x{2:X} {3} DXT — форматы противоречат, словарь не загрузится (TXD-FORMAT-MISMATCH)."
        ).format(label, int(compressed), d3d_format, 'это' if is_dxt else 'не'))
    if is_dxt:
        if nibble not in UNCOMPRESSED_TABLE:
            fatal.append(_t(
                "TXD, текстура {0}: nibble формата 0x{1:X}00 при DXT — допустимы 0x100..0x600/0xA00, иначе словарь не загрузится (TXD-FORMAT-MISMATCH)."
            ).format(label, nibble))
        if d3d_format != 0x31545844 and not (flags & FLAG_HAS_ALPHA):
            warnings.append(_t(
                "TXD, текстура {0}: DXT3/DXT5 без флага alpha — отрисуется непрозрачной (TXD-ALPHA-FLAG)."
            ).format(label))
        if width and height and (width < 4 or height < 4):
            warnings.append(_t(
                "TXD, текстура {0}: DXT при размере {1}×{2} меньше блока 4×4 (TXD-DIMS)."
            ).format(label, width, height))
    else:
        entry = UNCOMPRESSED_TABLE.get(nibble)
        if entry is None:
            fatal.append(_t(
                "TXD, текстура {0}: nibble формата 0x{1:X}00 вне таблицы растров — словарь не загрузится (TXD-FORMAT-MISMATCH)."
            ).format(label, nibble))
        else:
            bpp = entry[1]
            if d3d_format != entry[0]:
                fatal.append(_t(
                    "TXD, текстура {0}: несжатый формат 0x{1:X}00 требует D3DFORMAT {2}, в файле {3} — словарь не загрузится (TXD-FORMAT-MISMATCH)."
                ).format(label, nibble, entry[0], d3d_format))

    # TXD-NUMLEVELS-OVER / -UNDER
    chain = (int(math.floor(math.log2(max(width, height)))) + 1) if width and height else 1
    mipmapped = bool(raster_format & RASTER_MIPMAP)
    expected_levels = chain if mipmapped else 1
    if num_levels > expected_levels:
        fatal.append(_t(
            "TXD, текстура {0}: {1} мип-уровней при {2} у D3D-текстуры — RwRasterLock лишнего уровня вернёт NULL, RwStreamRead в 0 (TXD-NUMLEVELS-OVER)."
        ).format(label, num_levels, expected_levels))
    elif num_levels == 0:
        warnings.append(_t(
            "TXD, текстура {0}: 0 мип-уровней — ни один уровень не читается, текстура из мусора (TXD-NUMLEVELS-UNDER)."
        ).format(label))
    elif num_levels < expected_levels:
        if is_dxt and num_levels == 1:
            warnings.append(_t(
                "TXD, текстура {0}: флаг MIPMAP при одном уровне — мипов не будет (TXD-NUMLEVELS-UNDER)."
            ).format(label))
        else:
            warnings.append(_t(
                "TXD, текстура {0}: {1} мип-уровней из {2} — непрочитанные уровни остаются мусором (TXD-NUMLEVELS-UNDER)."
            ).format(label, num_levels, expected_levels))

    # palette block
    if raster_format & RASTER_PAL4:
        p += 0x80
    elif raster_format & RASTER_PAL8:
        p += 0x400

    # TXD-LEVEL-OVERSIZE / -SHORT / TXD-STRUCT-TRAILING
    faces = 6 if flags & FLAG_CUBE else 1
    short_levels = []
    for face in range(faces):
        for level in range(num_levels):
            if p + 4 > payload_end:
                fatal.append(_t(
                    "TXD, текстура {0}: STRUCT кончился до уровня {1} — поток рассинхронизируется, словарь не загрузится (TXD-STRUCT-TRAILING)."
                ).format(label, level))
                return
            size = unpack_from('<I', data, p)[0]
            p += 4
            if width and height and (is_dxt or bpp):
                expected = _level_bytes(width, height, level, d3d_format, bpp)
                lw, lh = max(1, width >> level), max(1, height >> level)
                if size > expected:
                    fatal.append(_t(
                        "TXD, текстура {0}: уровень {1} занимает {2} байт при поверхности {3} — запись за пределы D3D-текстуры, порча кучи (TXD-LEVEL-OVERSIZE)."
                    ).format(label, level, size, expected))
                elif size == 0:
                    if not (is_dxt and (lw < 4 or lh < 4)):
                        short_levels.append(level)
                elif size < expected:
                    short_levels.append(level)
            p += size
            if p > payload_end:
                fatal.append(_t(
                    "TXD, текстура {0}: уровень {1} выходит за STRUCT на {2} байт — поток рассинхронизируется (TXD-STRUCT-TRAILING)."
                ).format(label, level, p - payload_end))
                return
    if short_levels:
        warnings.append(_t(
            "TXD, текстура {0}: уровни {1} короче поверхности — хвост уровня остаётся мусором/чужой текстурой (TXD-LEVEL-SHORT)."
        ).format(label, ', '.join(str(l) for l in short_levels)))
    if p != payload_end:
        fatal.append(_t(
            "TXD, текстура {0}: после последнего уровня в STRUCT остаётся {1} байт — следующий FindChunk прочитает их как заголовок, словарь не загрузится (TXD-STRUCT-TRAILING)."
        ).format(label, payload_end - p))


def check_txd(txd, target: str = 'SA', file_name: str = ''):
    """Audit a TXD. ``txd`` is the file image (``bytes``) — the exporter
    hands over what it wrote; ``target`` picks the platform id the game
    expects; ``file_name`` (optional) feeds the IMG entry-name rule.

    Returns ``(fatal, warnings)`` — two lists of ready-to-show strings.
    """
    fatal, warnings = [], []
    data = bytes(txd)

    if file_name:
        base = os.path.splitext(os.path.basename(file_name))[0]
        if len(base) > IMG_BASENAME_MAX:
            fatal.append(_t(
                "TXD «{0}»: имя файла длиннее {1} символов — LoadCdDirectory молча пропустит запись в IMG, модели с этим TXD никогда не загрузятся (TXD-IMGNAME)."
            ).format(base, IMG_BASENAME_MAX))

    try:
        ct, clen, clib = unpack_from('<III', data, 0)
    except StructError:
        fatal.append(_t("TXD: файл короче заголовка чанка (TXD-STRUCTLEN)."))
        return fatal, warnings
    if ct != CHUNK_TEX_DICTIONARY:
        fatal.append(_t(
            "TXD: первый чанк 0x{0:X}, а не Texture Dictionary (0x16) — словарь не загрузится (TXD-VERSION)."
        ).format(ct))
        return fatal, warnings
    if not _version_ok(clib, target):
        fatal.append(_t(
            "TXD: версия RW 0x{0:X} вне {1} — чанк отвергается, словарь не загрузится (TXD-VERSION)."
        ).format(_decode_version(clib), _version_range_text(target)))
    try:
        st, slen, slib = unpack_from('<III', data, 12)
    except StructError:
        fatal.append(_t("TXD: нет STRUCT словаря (TXD-STRUCTLEN)."))
        return fatal, warnings
    if st != CHUNK_STRUCT:
        fatal.append(_t("TXD: за заголовком словаря нет STRUCT (TXD-STRUCTLEN)."))
        return fatal, warnings
    if slen != 4:
        if slen >= 13:
            fatal.append(_t(
                "TXD: STRUCT словаря длиной {0} байт — читается в 4-байтовый слот стека, от 13 байт затирает адрес возврата: краш (TXD-STRUCTLEN)."
            ).format(slen))
        else:
            fatal.append(_t(
                "TXD: STRUCT словаря длиной {0} байт вместо 4 — переполнение локальной переменной, словарь не загрузится (TXD-STRUCTLEN)."
            ).format(slen))
        return fatal, warnings
    if not _version_ok(slib, target):
        fatal.append(_t(
            "TXD: версия RW 0x{0:X} вне {1} — чанк отвергается, словарь не загрузится (TXD-VERSION)."
        ).format(_decode_version(slib), _version_range_text(target)))
    num_textures = unpack_from('<H', data, 24)[0]

    pos = 28
    end = min(len(data), 12 + clen)
    found = 0
    seen = {}
    while pos + 12 <= end:
        t, ln, lib = unpack_from('<III', data, pos)
        body = pos + 12
        if t == CHUNK_TEX_NATIVE:
            if not _version_ok(lib, target):
                fatal.append(_t(
                    "TXD, текстура #{0}: версия RW 0x{1:X} вне {2} — чанк отвергается, словарь не загрузится (TXD-VERSION)."
                ).format(found, _decode_version(lib), _version_range_text(target)))
            _check_texture(found, data, body, min(end, body + ln), target, seen, fatal, warnings)
            found += 1
        pos = body + ln

    # TXD-COUNT
    if num_textures > found:
        fatal.append(_t(
            "TXD: в заголовке {0} текстур, в файле {1} — FindChunk упрётся в конец файла, словарь не загрузится (TXD-COUNT)."
        ).format(num_textures, found))
    elif num_textures < found:
        warnings.append(_t(
            "TXD: в заголовке {0} текстур, в файле {1} — лишние никогда не загрузятся (TXD-COUNT)."
        ).format(num_textures, found))

    return fatal, warnings
