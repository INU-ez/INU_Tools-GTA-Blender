# INU_tools.core.dff
# GTA SA DFF (RenderWare Clump) reader and writer.
# Pure Python, no Blender dependency.
#
# Written from scratch based on public RenderWare format specifications:
#   https://gtamods.com/wiki/RenderWare_binary_stream_file
#   https://gtamods.com/wiki/DFF
#
# RenderWare Binary Stream uses a chunked format:
#   Each chunk = 12-byte header (type:u32, size:u32, version:u32) + data

from __future__ import annotations

from struct import pack, unpack_from
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .rwbinary import BinaryReader


# ── RenderWare chunk type IDs (public constants) ─────────────────

CHUNK_STRUCT           = 1
CHUNK_STRING           = 2
CHUNK_EXTENSION        = 3
CHUNK_TEXTURE          = 6
CHUNK_MATERIAL         = 7
CHUNK_MATERIAL_LIST    = 8
CHUNK_FRAME_LIST       = 14
CHUNK_GEOMETRY         = 15
CHUNK_CLUMP            = 16
CHUNK_LIGHT            = 18
CHUNK_ATOMIC           = 20
CHUNK_GEOMETRY_LIST    = 26
CHUNK_ANIM_ANIMATION   = 27
CHUNK_UV_ANIM_DICT     = 43
CHUNK_SKIN_PLG         = 278
CHUNK_HANIM_PLG        = 286
CHUNK_USERDATA_PLG     = 287
CHUNK_MATFX_PLG        = 288
CHUNK_UV_ANIM_PLG      = 309
CHUNK_BIN_MESH_PLG     = 1294
CHUNK_NATIVE_DATA_PLG  = 0x0510   # 1296 — mobile (War Drum OpenGL) + PS2/Xbox native geom
CHUNK_PIPELINE_SET     = 0x0253F2F3

# ── Native Data PLG platform IDs (RW convention) ─────────────────
# Mobile GTA SA stores geometry via OGL (0x2). PS2/Xbox/PSP also have
# their own native data formats — we only support OGL for now.

NATIVE_PLATFORM_D3D7 = 0x1
NATIVE_PLATFORM_OGL  = 0x2   # War Drum / iOS / Android
NATIVE_PLATFORM_MAC  = 0x3
NATIVE_PLATFORM_PS2  = 0x4
NATIVE_PLATFORM_XBOX = 0x5
NATIVE_PLATFORM_GC   = 0x6
NATIVE_PLATFORM_PSP  = 0xA

# ── War Drum OpenGL attribute IDs / types ────────────────────────
# Each vertex in mobile geometry is described by 1-7 of these
# attributes, interleaved in a single buffer with explicit stride.

WDGL_ATTRIB_COORD       = 0   # vec3 position
WDGL_ATTRIB_TEX_COORD   = 1   # vec2 uv (scaled by 512 if integer)
WDGL_ATTRIB_NORMAL      = 2   # vec3 normal
WDGL_ATTRIB_PRELIT      = 3   # vec4 RGBA (normalised float)
WDGL_ATTRIB_BONE_WEIGHT = 4   # vec4 weights
WDGL_ATTRIB_BONE_INDEX  = 5   # vec4 bone indices
WDGL_ATTRIB_EXTRA_COLOR = 6   # vec4 RGBA night vertex colour (SA only)

WDGL_TYPE_FLOAT  = 0
WDGL_TYPE_BYTE   = 1
WDGL_TYPE_UBYTE  = 2
WDGL_TYPE_SHORT  = 3
WDGL_TYPE_USHORT = 4
CHUNK_SPECULAR_MAT     = 0x0253F2F6
CHUNK_2DFXPLG          = 0x0253F2F8
CHUNK_EXTRA_COLORS     = 0x0253F2F9
CHUNK_COLLISION_MODEL  = 0x0253F2FA
CHUNK_REFLECTION_MAT   = 0x0253F2FC
CHUNK_BREAKABLE        = 0x0253F2FD
CHUNK_FRAME_NAME       = 0x0253F2FE

# ── Geometry flags (public RenderWare constants) ─────────────────

GEOM_POSITIONS   = 0x02
GEOM_TEXTURED    = 0x04
GEOM_PRELIT      = 0x08
GEOM_NORMALS     = 0x10
GEOM_LIGHT       = 0x20
GEOM_MOD_COLOR   = 0x40
GEOM_TEXTURED2   = 0x80
GEOM_NATIVE      = 0x01000000

# ── GTA SA default version ───────────────────────────────────────

GTA_SA_VERSION = 0x36003
GTA_SA_BUILD   = 0xFFFF


# ── Library ID encoding (RenderWare spec) ────────────────────────

def make_library_id(version: int, build: int = 0xFFFF) -> int:
    """Encode RW version + build into a 32-bit library ID."""
    if version <= 0x31000:
        return version >> 8
    return (
        ((version - 0x30000 & 0x3FF00) << 14) |
        ((version & 0x3F) << 16) |
        (build & 0xFFFF)
    )


# ── Chunk builder ────────────────────────────────────────────────

def _chunk(chunk_type: int, data: bytes, lib_id: int) -> bytes:
    """Wrap data in a RenderWare chunk with 12-byte header."""
    return pack('<III', chunk_type, len(data), lib_id) + data


def _strip_root_chunk(blob: bytes, chunk_type: int) -> bytes:
    """Удалить из последовательности корневых чанков (raw bytes) все чанки
    данного типа. Для предотвращения дублей при повторной записи."""
    if not blob:
        return blob
    out = bytearray()
    off = 0
    n = len(blob)
    while off + 12 <= n:
        t, sz, _lib = unpack_from('<III', blob, off)
        seg = blob[off:off + 12 + sz]
        if t != chunk_type:
            out += seg
        off += 12 + sz
    return bytes(out)


def _pad_string(s: str) -> bytes:
    """Encode string with null terminator, padded to 4-byte boundary."""
    raw = s.encode('ascii', errors='replace') + b'\x00'
    pad_len = (4 - len(raw) % 4) % 4
    return raw + b'\x00' * pad_len


# ── Data structures ──────────────────────────────────────────────

@dataclass
class RGBA:
    r: int = 255
    g: int = 255
    b: int = 255
    a: int = 255


@dataclass
class TexCoords:
    u: float = 0.0
    v: float = 0.0


@dataclass
class DffTexture:
    """Material texture reference."""
    name: str = ""
    mask: str = ""
    filters: int = 0x1106  # default filter mode

    def to_bytes(self, lib_id: int) -> bytes:
        # Texture names must be ASCII. A non-ASCII char (a leftover U+FFFD from
        # a bad import, or one the user typed) gets written back as '?' by the
        # ascii encoder — a DIFFERENT name that won't link to the TXD in-game.
        # Warn at export so a name left unchanged since import is caught.
        if self.name and any(ord(c) > 127 for c in self.name):
            print(f"[INU] WARN: texture name '{self.name}' has a non-ASCII "
                  f"character — it will be written as '?' and won't link "
                  f"in-game. Rename it to ASCII (a-z, 0-9, _) before export.")
        # W8: RwTextureSetName keeps 31 chars, so the TXD side is always cut
        # to 31 while the DFF would carry the full name — the two can never
        # match and the material renders untextured (DFF-19). Refuse.
        if len(self.name.encode('ascii', errors='replace')) > TEXTURE_NAME_MAX:
            raise DffLimitError(_t(
                "имя текстуры «{0}» длиннее {1} символов — TXD хранит 31 символ, материал не найдёт свою текстуру. Переименуй текстуру."
            ).format(self.name, TEXTURE_NAME_MAX))
        # Write the FULL 32-bit filter/addressing word. The low 16 bits are
        # filter + U/V addressing; the high 16 bits are flags some textures set
        # (e.g. 0x0001) — writing them as `2x` padding dropped them, so a
        # re-export no longer matched the source byte-for-byte.
        struct_data = pack('<I', self.filters)
        body = _chunk(CHUNK_STRUCT, struct_data, lib_id)
        body += _chunk(CHUNK_STRING, _pad_string(self.name), lib_id)
        body += _chunk(CHUNK_STRING, _pad_string(self.mask), lib_id)
        body += _chunk(CHUNK_EXTENSION, b'', lib_id)
        return _chunk(CHUNK_TEXTURE, body, lib_id)


@dataclass
class SurfaceProperties:
    ambient: float = 1.0
    specular: float = 0.0
    diffuse: float = 1.0


@dataclass
class BumpMapEffect:
    intensity: float = 1.0
    bump_texture: Optional[DffTexture] = None
    height_texture: Optional[DffTexture] = None


@dataclass
class EnvMapEffect:
    coefficient: float = 0.5
    use_fb_alpha: bool = False
    texture: Optional[DffTexture] = None


@dataclass
class SpecularMaterial:
    level: float = 1.0
    name: str = ""


@dataclass
class ReflectionMaterial:
    scale_x: float = 0.0
    scale_y: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    intensity: float = 0.0


@dataclass
class DualTextureEffect:
    """Dual Texture (MatFX type 4) — src/dst blend modes."""
    src_blend: int = 5   # SRCALPHA
    dst_blend: int = 6   # INVSRCALPHA
    texture: Optional[DffTexture] = None


# ── UV Animation ─────────────────────────────────────────────────
#
# RenderWare UV anim format (written as CHUNK_UV_ANIM_DICT 0x2B at clump
# extension, referenced from materials via CHUNK_UV_ANIM_PLG 0x135).
# Keyframes are 36 bytes each: i32 prev_offset, f32 time, 6×f32 uv matrix
# (scale_u, scale_v, shear_u, shear_v, trans_u, trans_v).

UV_ANIM_KEYFRAME_SIZE = 32  # bytes — i32 prev_offset + f32 time + 6×f32 uv matrix


@dataclass
class UVAnimKeyframe:
    time: float = 0.0
    scale_u: float = 1.0
    scale_v: float = 1.0
    shear_u: float = 0.0
    shear_v: float = 0.0
    trans_u: float = 0.0
    trans_v: float = 0.0


@dataclass
class UVAnim:
    """One named UV animation. Формат 1-в-1 как Kam's UVanim_tool (рабочий
    в GTA SA)."""
    name: str = ""
    type_id: int = 0x1C1            # Kam: 449 = 0x1C1 (НЕ 0x1C0!)
    # nodeToUV: в стоке SA тут мусорные указатели (игра заполняет в рантайме) —
    # наши нули ОК, формат сверен байт-в-байт со стоковыми UV-аним моделями.
    # Пробовали (1,0,…) чтобы оживить анимацию в retail gtasa.exe — НЕ помогло
    # (там дело в движке/сетапе, не в DFF; euryopa/librw играет и с нулями).
    node_to_uv: tuple = (0, 0, 0, 0, 0, 0, 0, 0)
    duration: float = 1.0
    keyframes: list = field(default_factory=list)   # list[UVAnimKeyframe]

    def to_bytes(self, lib_id: int) -> bytes:
        n = len(self.keyframes)
        # STRUCT payload — точная раскладка Kam's UVanim_tool (88-байтный
        # заголовок + кадры по 32 байта):
        #   u32 version=0x100, u32 typeID=0x1C1, u32 numFrames,
        #   f32 0.0, f32 duration, u32 0, char name[32], i32 nodeToUV[8].
        data = pack('<III', 0x100, self.type_id, n)
        data += pack('<f', 0.0)
        data += pack('<f', self.duration)
        data += pack('<I', 0)
        raw = self.name.encode('ascii', errors='replace')[:31]
        data += raw + b'\x00' * (32 - len(raw))
        mapping = list(self.node_to_uv) + [0] * (8 - len(self.node_to_uv))
        data += pack('<8i', *mapping[:8])
        # Кадр (32 байта): f32 time, затем матрица 6×f32 в порядке Kam
        #   [0.0, scaleU, scaleV, 0.0, -transU, transV],
        # затем i32 prev (индекс пред. кадра, i-2 в 1-based ⇒ k-1 в 0-based).
        # Порядок именно такой — иначе матрица вырождается и альфа-листва
        # становится невидимой в игре.
        # Матрица uv[6] = [0, scaleU, scaleV, 0, transU, transV] (как DragonFF
        # get_uv_at: Location X→uv[4], Location Y→uv[5]). identity=[0,1,1,0,0,0].
        for k, kf in enumerate(self.keyframes):
            data += pack('<f', kf.time)
            data += pack('<6f', 0.0, kf.scale_u, kf.scale_v, 0.0,
                         kf.trans_u, kf.trans_v)
            data += pack('<i', k - 1)
        # ВАЖНО: данные кладутся ПРЯМО в чанк ANIM (0x1B), БЕЗ обёртки STRUCT.
        # DragonFF/Kam так и пишут. Лишний STRUCT внутри ANIM ломал чтение
        # анимации движком (version читался как заголовок STRUCT) → не играла.
        return _chunk(CHUNK_ANIM_ANIMATION, data, lib_id)


@dataclass
class UVAnimDict:
    """Clump-level dictionary of UV animations (chunk 0x2B)."""
    anims: list = field(default_factory=list)  # list[UVAnim]

    def to_bytes(self, lib_id: int) -> bytes:
        body = _chunk(CHUNK_STRUCT, pack('<I', len(self.anims)), lib_id)
        for a in self.anims:
            body += a.to_bytes(lib_id)
        return _chunk(CHUNK_UV_ANIM_DICT, body, lib_id)


def _uv_anim_plg_bytes(anim_names: list, lib_id: int) -> bytes:
    """Material UV-anim плагины в расширении материала — формат 1-в-1 как
    Kam's UVanim_tool (проверенно рабочий в GTA SA):

        chunk 0x120 (12 байт данных: 5, 5, 0)
        chunk 0x135 → STRUCT(0x01) { u32 mask; char name[32] на каждый бит }

    Раньше мы писали 0x135 без STRUCT-обёртки и с 8×32-байтными именами —
    движок читал мусор, позиция в потоке съезжала и весь клумп переставал
    грузиться (модель невидима)."""
    if not anim_names:
        return b''
    names = list(anim_names)[:8]
    mask = 0
    for i in range(len(names)):
        mask |= (1 << i)
    # 0x120 — материал-плагин UV-анимации (Kam пишет 5, 5, 0).
    out = _chunk(0x120, pack('<3I', 5, 5, 0), lib_id)
    # 0x135 — STRUCT { mask, name[32] на каждый установленный бит mask }.
    struct_data = pack('<I', mask)
    for name in names:
        raw = name.encode('ascii', errors='replace')[:31]
        struct_data += raw + b'\x00' * (32 - len(raw))
    out += _chunk(CHUNK_UV_ANIM_PLG,
                  _chunk(CHUNK_STRUCT, struct_data, lib_id), lib_id)
    return out


def _read_uv_anim(data: bytes, offset: int, size: int) -> 'UVAnim':
    """Parse one UVAnim (CHUNK_ANIM_ANIMATION 0x1B) → ``UVAnim``.

    The inverse of ``UVAnim.to_bytes``. Expects the outer 0x1B wrapper
    was already consumed — *offset* points at the inner STRUCT chunk.

    Layout (matches the writer):
        STRUCT:
            u32 version, u32 type_id, u32 num_keyframes, u32 flags,
            f32 duration,
            char name[32],
            i32 node_to_uv[8],
            keyframe[num_keyframes]  — 32 bytes each
    """
    import struct as _s
    end = offset + size
    anim = UVAnim()

    # Данные лежат ПРЯМО в чанке ANIM (0x1B), без STRUCT-обёртки.
    # 88-байтный заголовок: u32 version, u32 typeID, u32 numFrames,
    #   f32 0.0, f32 duration, u32 0, char name[32], i32 nodeToUV[8].
    if offset + 24 > end:
        return anim
    _version, type_id, num_kf = _s.unpack_from('<III', data, offset)
    duration = _s.unpack_from('<f', data, offset + 16)[0]
    anim.type_id = type_id
    anim.duration = duration
    offset += 24

    # Name (32 bytes, null-padded)
    if offset + 32 > end:
        return anim
    raw_name = data[offset:offset + 32]
    anim.name = raw_name.split(b'\x00', 1)[0].decode('ascii', errors='replace')
    offset += 32

    # node_to_uv[8]
    if offset + 32 > end:
        return anim
    anim.node_to_uv = tuple(_s.unpack_from('<8i', data, offset))
    offset += 32

    # Кадры — 32 байта: f32 time, матрица 6×f32, i32 prev.
    # Матрица uv = [0, scaleU, scaleV, 0, transU, transV].
    for _i in range(num_kf):
        if offset + UV_ANIM_KEYFRAME_SIZE > end:
            break
        t = _s.unpack_from('<f', data, offset)[0]
        m = _s.unpack_from('<6f', data, offset + 4)
        anim.keyframes.append(UVAnimKeyframe(
            time=t,
            scale_u=m[1], scale_v=m[2],
            shear_u=0.0, shear_v=0.0,
            trans_u=m[4], trans_v=m[5],
        ))
        offset += UV_ANIM_KEYFRAME_SIZE

    return anim


def _read_uv_anim_dict(data: bytes, offset: int, size: int) -> 'UVAnimDict':
    """Parse a CHUNK_UV_ANIM_DICT (0x2B) body → ``UVAnimDict``.

    Inverse of ``UVAnimDict.to_bytes``. Expects *offset* points at
    the inner STRUCT (count) chunk, *size* is the 0x2B body length.
    """
    import struct as _s
    end = offset + size
    result = UVAnimDict()

    if offset + 12 > end:
        return result
    struct_ident, struct_size = _s.unpack_from('<II', data, offset)[:2]
    if struct_ident != CHUNK_STRUCT:
        return result
    offset += 12
    if offset + 4 > end:
        return result
    count = _s.unpack_from('<I', data, offset)[0]
    offset += 4

    # Each animation is wrapped in a 0x1B chunk
    for _i in range(count):
        if offset + 12 > end:
            break
        ch_ident, ch_size = _s.unpack_from('<II', data, offset)[:2]
        inner_start = offset + 12
        if ch_ident == CHUNK_ANIM_ANIMATION:
            result.anims.append(
                _read_uv_anim(data, inner_start, ch_size))
        offset = inner_start + ch_size

    return result


def _read_uv_anim_plg(data: bytes, offset: int, size: int) -> list:
    """Parse a CHUNK_UV_ANIM_PLG (0x135) body → list[str] of referenced
    animation names.

    Layout (как в SA / UVanim_tool): STRUCT(0x01) { u32 mask; char name[32]
    на каждый установленный бит mask }.
    """
    import struct as _s
    end = offset + size
    # inner STRUCT
    if offset + 12 > end:
        return []
    struct_ident, struct_size = _s.unpack_from('<II', data, offset)[:2]
    if struct_ident != CHUNK_STRUCT:
        return []
    offset += 12
    if offset + 4 > end:
        return []
    mask = _s.unpack_from('<I', data, offset)[0]
    offset += 4

    names = []
    for i in range(8):
        if not (mask & (1 << i)):
            continue
        if offset + 32 > end:
            break
        raw = data[offset:offset + 32]
        name = raw.split(b'\x00', 1)[0].decode('ascii', errors='replace')
        offset += 32
        if name:
            names.append(name)
    return names


@dataclass
class DffMaterial:
    """Single material with optional plugins."""
    color: RGBA = field(default_factory=RGBA)
    surface: SurfaceProperties = field(default_factory=SurfaceProperties)
    texture: Optional[DffTexture] = None
    bump_map: Optional[BumpMapEffect] = None
    env_map: Optional[EnvMapEffect] = None
    dual_texture: Optional[DualTextureEffect] = None
    specular: Optional[SpecularMaterial] = None
    reflection: Optional[ReflectionMaterial] = None
    user_data: Optional[UserData] = None
    uv_anim_names: list = field(default_factory=list)  # names in clump UV anim dict

    def _matfx_bytes(self, lib_id: int) -> bytes:
        """Build Material Effects PLG content."""
        has_bump = self.bump_map is not None
        has_env = self.env_map is not None
        has_dual = self.dual_texture is not None

        if has_bump and has_env:
            effect_type = 3
        elif has_bump:
            effect_type = 1
        elif has_env:
            effect_type = 2
        elif has_dual:
            effect_type = 4
        else:
            return b''

        data = pack('<I', effect_type)

        if has_bump:
            bm = self.bump_map
            data += pack('<I', 1)  # bump effect marker
            data += pack('<f', bm.intensity)
            has_bump_tex = bm.bump_texture is not None
            data += pack('<I', 1 if has_bump_tex else 0)
            if has_bump_tex:
                data += bm.bump_texture.to_bytes(lib_id)
            has_height = bm.height_texture is not None
            data += pack('<I', 1 if has_height else 0)
            if has_height:
                data += bm.height_texture.to_bytes(lib_id)

        if has_env:
            em = self.env_map
            data += pack('<I', 2)  # env effect marker
            data += pack('<f', em.coefficient)
            data += pack('<I', 1 if em.use_fb_alpha else 0)
            has_tex = em.texture is not None
            data += pack('<I', 1 if has_tex else 0)
            if has_tex:
                data += em.texture.to_bytes(lib_id)

        if has_dual:
            dt = self.dual_texture
            data += pack('<I', 4)  # dual texture effect marker
            data += pack('<II', dt.src_blend, dt.dst_blend)
            has_tex = dt.texture is not None
            data += pack('<I', 1 if has_tex else 0)
            if has_tex:
                data += dt.texture.to_bytes(lib_id)

        if effect_type not in (3, 6):
            data += pack('<I', 0)  # terminator

        return _chunk(CHUNK_MATFX_PLG, data, lib_id)

    def to_bytes(self, lib_id: int, rw_version: int) -> bytes:
        """Serialize material to RenderWare binary."""
        # Struct header
        has_tex = 1 if self.texture else 0
        struct_data = pack('<4x')  # padding
        struct_data += pack('<4B', self.color.r, self.color.g, self.color.b, self.color.a)
        struct_data += pack('<II', 0, has_tex)  # unused=0 (as vanilla), textured flag
        if rw_version > 0x30400:
            struct_data += pack('<3f', self.surface.ambient, self.surface.specular, self.surface.diffuse)

        body = _chunk(CHUNK_STRUCT, struct_data, lib_id)

        # Texture
        if self.texture:
            body += self.texture.to_bytes(lib_id)

        # Extensions
        ext_data = b''
        ext_data += self._matfx_bytes(lib_id)

        if self.specular:
            spec_data = pack('<f', self.specular.level)
            spec_name = self.specular.name.encode('ascii', errors='replace')[:24]
            spec_data += spec_name + b'\x00' * (24 - len(spec_name))
            ext_data += _chunk(CHUNK_SPECULAR_MAT, spec_data, lib_id)

        # W7: Reflection Material (CHUNK 0x0253F2FC) — остаток 3ds Max-экспортёра.
        # Ваниль SA его НЕ пишет, движку он не нужен: env-map машин идёт через
        # MatFX (_matfx_bytes выше). Поэтому не сериализуем — так DFF совпадает
        # с ванильным. Данные (self.reflection) сохраняются в объекте на случай
        # анализа, но в файл не попадают.

        if self.user_data and self.user_data.sections:
            ext_data += self.user_data.to_bytes(lib_id)

        # UV Animation PLG (CHUNK_UV_ANIM_PLG = 0x135) references entries
        # in the clump-level UV Anim Dict (0x2B). Both are RW 3.5+ — skip
        # on III (rw_version < 0x35000) since the dict won't be emitted
        # there and a dangling reference would break the parser.
        if self.uv_anim_names and rw_version >= 0x35000:
            ext_data += _uv_anim_plg_bytes(self.uv_anim_names, lib_id)

        body += _chunk(CHUNK_EXTENSION, ext_data, lib_id)
        return _chunk(CHUNK_MATERIAL, body, lib_id)


@dataclass
class Triangle:
    """Face triangle with vertex indices and material index."""
    a: int = 0
    b: int = 0
    c: int = 0
    material: int = 0


@dataclass
class BoundingSphere:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    radius: float = 0.0


@dataclass
class UserDataSection:
    """Single named section of user data (int, float, or string array)."""
    name: str = ""
    data_type: int = 0   # 0=NA, 1=int, 2=float, 3=string
    data: list = field(default_factory=list)

USERDATA_NA     = 0
USERDATA_INT    = 1
USERDATA_FLOAT  = 2
USERDATA_STRING = 3


@dataclass
class UserData:
    """User Data PLG — arbitrary named data on geometry/frame/material."""
    sections: list = field(default_factory=list)  # list[UserDataSection]

    def to_bytes(self, lib_id: int) -> bytes:
        """Serialize to RenderWare User Data PLG chunk."""
        data = pack('<I', len(self.sections))
        for sec in self.sections:
            # Name
            name_bytes = sec.name.encode('ascii', errors='replace')
            data += pack('<I', len(name_bytes))
            data += name_bytes

            # Determine type from data if not set
            dtype = sec.data_type
            count = len(sec.data)
            data += pack('<II', dtype, count)

            if dtype == USERDATA_INT:
                for v in sec.data:
                    data += pack('<I', v)
            elif dtype == USERDATA_FLOAT:
                for v in sec.data:
                    data += pack('<f', v)
            elif dtype == USERDATA_STRING:
                for s in sec.data:
                    s_bytes = s.encode('ascii', errors='replace')
                    data += pack('<I', len(s_bytes))
                    data += s_bytes

        return _chunk(CHUNK_USERDATA_PLG, data, lib_id)


@dataclass
class ExtraVertColors:
    """Night vertex colors (second color layer)."""
    colors: list = field(default_factory=list)  # list[RGBA]


@dataclass
class BreakableData:
    """Breakable Objects extension (chunk 0x253F2FD) — the copy of the
    mesh the engine spawns as the broken pieces.

    Layout as ``BreakableStreamRead`` @ 0x59CEC0 parses it (verified on the
    vanilla ``bd_window`` / ``bussign1`` / ``barrierm`` chunks):
        u32 magic (0 = "not breakable", nothing follows; ≠ 0 = data)
        52-byte header: i32 posn_rule, u16 num_vertices, pad, 3 ptrs,
            u16 num_triangles, pad, 2 ptrs, u16 num_materials, pad, 4 ptrs
        num_vertices × {f32 x, y, z}, num_vertices × {f32 u, v},
        num_vertices × RGBA, num_triangles × {u16 a, b, c},
        num_triangles × u16 material, num_materials × char[32] texture,
        num_materials × char[32] mask, num_materials × {f32 r, g, b}
    The pointer words are heap garbage in vanilla; the engine overwrites
    them, so they are written as 0. Every material group is one piece;
    vanilla splits pieces by duplicating the material (same texture).
    """
    posn_rule: int = 1
    vertices: list = field(default_factory=list)       # list[(x, y, z)]
    uvs: list = field(default_factory=list)            # list[(u, v)]
    colors: list = field(default_factory=list)         # list[RGBA]
    triangles: list = field(default_factory=list)      # list[(a, b, c)]
    tri_materials: list = field(default_factory=list)  # list[int]
    tex_names: list = field(default_factory=list)      # list[str]
    mask_names: list = field(default_factory=list)     # list[str]
    ambient: list = field(default_factory=list)        # list[(r, g, b)]

    @classmethod
    def from_geometry(cls, geom: 'DffGeometry') -> 'BreakableData':
        """Build the break copy from the geometry itself (what Blender can
        supply): UV set 0 (or zeros), prelight (or white), the triangle
        list and one break material per DFF material."""
        nv = len(geom.vertices)
        uv0 = geom.uv_layers[0] if geom.uv_layers else []
        uvs = [(uv0[i].u, uv0[i].v) if i < len(uv0) else (0.0, 0.0)
               for i in range(nv)]
        cols = [geom.prelit_colors[i] if i < len(geom.prelit_colors)
                else RGBA() for i in range(nv)]
        tex, mask, amb = [], [], []
        for m in geom.materials:
            tex.append(m.texture.name if m.texture else '')
            mask.append(m.texture.mask if m.texture else '')
            amb.append((1.0, 1.0, 1.0))
        return cls(
            vertices=[tuple(v[:3]) for v in geom.vertices],
            uvs=uvs, colors=cols,
            triangles=[(t.a, t.b, t.c) for t in geom.triangles],
            tri_materials=[t.material for t in geom.triangles],
            tex_names=tex, mask_names=mask, ambient=amb,
        )

    def to_bytes(self, lib_id: int) -> bytes:
        nv, nt, nm = len(self.vertices), len(self.triangles), len(self.tex_names)
        data = bytearray(pack('<I', 1))  # magic ≠ 0: data follows
        data += pack('<iHH3IHH2IHH4I', self.posn_rule,
                     nv, 0, 0, 0, 0, nt, 0, 0, 0, nm, 0, 0, 0, 0, 0)
        for v in self.vertices:
            data += pack('<3f', v[0], v[1], v[2])
        for i in range(nv):
            u, v = self.uvs[i] if i < len(self.uvs) else (0.0, 0.0)
            data += pack('<2f', u, v)
        for i in range(nv):
            c = self.colors[i] if i < len(self.colors) else RGBA()
            data += pack('<4B', c.r, c.g, c.b, c.a)
        for t in self.triangles:
            data += pack('<3H', t[0], t[1], t[2])
        for i in range(nt):
            data += pack('<H', self.tri_materials[i] if i < len(self.tri_materials) else 0)
        for name in self.tex_names:
            data += _fixed_cstr(name, 32)
        for i in range(nm):
            data += _fixed_cstr(self.mask_names[i] if i < len(self.mask_names) else '', 32)
        for i in range(nm):
            a = self.ambient[i] if i < len(self.ambient) else (1.0, 1.0, 1.0)
            data += pack('<3f', a[0], a[1], a[2])
        return _chunk(CHUNK_BREAKABLE, bytes(data), lib_id)


def _fixed_cstr(s: str, size: int) -> bytes:
    """ASCII string in a fixed slot: at most ``size - 1`` chars + NUL,
    zero-padded — the engine reads these fields as C strings."""
    raw = s.encode('ascii', errors='replace')[:size - 1]
    return raw + b'\x00' * (size - len(raw))


def _read_breakable_plugin(r: BinaryReader, size: int) -> Optional[BreakableData]:
    """Decode the Breakable chunk the way the engine does. ``None`` for the
    4-byte "not breakable" marker (magic 0) — same state as no chunk."""
    end = r.pos + size
    magic = r.read_one('<I')
    if magic == 0 or size < 4 + 52:
        return None
    (posn_rule, nv, _p, _, _, _, nt, _p2, _, _, nm, _p3,
     _, _, _, _) = r.read('<iHH3IHH2IHH4I')
    need = nv * 24 + nt * 8 + nm * 76
    if r.pos + need > end:
        return None
    b = BreakableData(posn_rule=posn_rule)
    if nv:
        arr = np.frombuffer(r.data, dtype='<f4', count=nv * 3, offset=r.pos).reshape(nv, 3)
        r.skip(nv * 12)
        b.vertices = [tuple(v) for v in arr.tolist()]
        arr = np.frombuffer(r.data, dtype='<f4', count=nv * 2, offset=r.pos).reshape(nv, 2)
        r.skip(nv * 8)
        b.uvs = [tuple(v) for v in arr.tolist()]
        arr = np.frombuffer(r.data, dtype=np.uint8, count=nv * 4, offset=r.pos).reshape(nv, 4)
        r.skip(nv * 4)
        b.colors = [RGBA(*c) for c in arr.tolist()]
    if nt:
        arr = np.frombuffer(r.data, dtype='<u2', count=nt * 3, offset=r.pos).reshape(nt, 3)
        r.skip(nt * 6)
        b.triangles = [tuple(t) for t in arr.tolist()]
        arr = np.frombuffer(r.data, dtype='<u2', count=nt, offset=r.pos)
        r.skip(nt * 2)
        b.tri_materials = arr.tolist()
    for _ in range(nm):
        b.tex_names.append(r.read_str(32))
    for _ in range(nm):
        b.mask_names.append(r.read_str(32))
    for _ in range(nm):
        b.ambient.append(tuple(r.read('<3f')))
    return b


# ── 2DFX Effect structures ──────────────────────────────────────

# Per-game allowlist of 2DFX effect_id values. The 2DFX RW chunk
# (0x253F2F8) is shared across III / VC / SA, but each game's engine
# only recognises a subset of the type IDs that ship inside it. Types
# the engine doesn't understand are either silently ignored (best case)
# or parsed as a different type with garbage offsets (crash, worst
# case). Writer filters entries against the target game's allowlist
# before emitting to avoid both failure modes.
#
# IDs in the dict map to:
#   0 = Light (street lamps, neon signs) — III/VC/SA
#   1 = Particle effect                    — III/VC/SA
#   2 = Strobe/investigation               — III/VC (unused in VC, dropped in SA)
#   3 = Ped attractor (ATM, bench, bus stop) — VC + SA
#   4 = Sun reflection / sun glare         — VC + SA
#   6 = Enter-Exit, 7 = Street sign, 8 = Trigger point,
#   9 = Cover point, 10 = Escalator        — SA-specific extras
#       6/7/10 are now written by typed serializers below; 8/9 (and any
#       other type) round-trip byte-exact via RawUnknown2dfx.
#
# IMPORTANT — storage location differs across games:
#   * III / VC: 2DFX entries live in IDE files (``2dfx`` section).
#     Writing a DFF 0x253F2F8 chunk for those games is technically
#     valid bytes but the engine doesn't read them — effects appear
#     missing in-game until the IDE section is also populated.
#   * SA: 2DFX entries live in the DFF chunk (this writer's normal
#     path). The SA-only Type 5 ("special") still goes in IDE.
# Phase 7 currently only writes the DFF chunk; full III/VC 2DFX
# support requires extending the IDE writer to emit 2dfx entries
# from objects' attached effect Empties.
#
# Source: gtamods.com/wiki/2DFX (verified 2026-05).
_2DFX_ALLOWLIST_BY_RW_VERSION = {
    0x33000: frozenset({0, 1, 2}),          # III: + Strobe
    0x34000: frozenset({0, 1, 2, 3, 4}),    # VC (RW 3.4.0.3 on PC): + PedAttractor + SunGlare
    # SA: + PedAttractor, SunGlare, Enter/Exit, RoadSign, Trigger point (8),
    # Cover point (9), Escalator — the exact handler set of the SA 2dfx
    # reader @ 0x6F9FD0; 2 (III/VC strobe), 5 and ≥ 11 fall through unread.
    0x36000: frozenset({0, 1, 3, 4, 6, 7, 8, 9, 10}),
}


def _allowed_2dfx_ids(rw_version: int) -> frozenset:
    """Return the set of 2DFX effect_id values the target game accepts.
    Picks the closest floor ≤ rw_version so any future intermediate
    RW versions still resolve to a sensible allowlist."""
    best_floor = 0x33000
    for floor in _2DFX_ALLOWLIST_BY_RW_VERSION:
        if floor <= rw_version and floor >= best_floor:
            best_floor = floor
    return _2DFX_ALLOWLIST_BY_RW_VERSION[best_floor]




@dataclass
class Light2dfx:
    """Light effect (street lights, neon signs, etc.)."""
    effect_id: int = 0
    loc: tuple = (0.0, 0.0, 0.0)
    color: RGBA = field(default_factory=RGBA)
    corona_far_clip: float = 0.0
    pointlight_range: float = 0.0
    corona_size: float = 0.0
    shadow_size: float = 0.0
    corona_show_mode: int = 0
    corona_enable_reflection: int = 0
    corona_flare_type: int = 0
    shadow_color_multiplier: int = 0
    flags1: int = 0
    corona_tex_name: str = ""
    shadow_tex_name: str = ""
    shadow_z_distance: int = 0
    flags2: int = 0
    look_direction: Optional[tuple] = None  # (x, y, z) bytes or None


@dataclass
class Particle2dfx:
    """Particle effect (smoke, fire, etc.)."""
    effect_id: int = 1
    loc: tuple = (0.0, 0.0, 0.0)
    effect_name: str = ""


@dataclass
class PedAttractor2dfx:
    """Ped attractor (ATM, bench, bus stop, etc.).

    Payload = exactly 56 bytes — the SA reader (0x6F9FD0, type 3) skips
    any other size (W2): u32 type, 9f (queue / use / forward dirs),
    char[8] script, u32 probability, then ``flags`` (u8 @52, u8 pad,
    u8 @54, u8 pad) — vanilla carries 0x23 in byte 52 on 18 entries.
    """
    effect_id: int = 3
    loc: tuple = (0.0, 0.0, 0.0)
    attractor_type: int = 0
    rotation_matrix: tuple = (1,0,0, 0,1,0, 0,0,1)  # 3x3 as 9 floats
    external_script: str = ""
    ped_existing_probability: int = 0
    flags: int = 0          # byte 52 (→ C2dEffect +0x36)
    unknown: int = 0        # byte 54 (→ C2dEffect +0x37)


@dataclass
class SunGlare2dfx:
    """Sun glare effect on surfaces."""
    effect_id: int = 4
    loc: tuple = (0.0, 0.0, 0.0)


@dataclass
class EnterExit2dfx:
    """Enter/Exit marker (type 6) — interior teleport pairs.

    Payload = 44 bytes. Layout verified against gtamods 2d_Effect (RW
    Section) and DragonFF's parser (both agree on 44 bytes / field order):
        enter_angle f, radius_x f, radius_y f, exit_loc 3f, exit_angle f,
        interior u16, flags1 u8, sky_color u8, interior_name char[8],
        time_on u8, time_off u8, flags2 u8, unknown u8.
    """
    effect_id: int = 6
    loc: tuple = (0.0, 0.0, 0.0)
    enter_angle: float = 0.0
    approximation_radius_x: float = 0.0
    approximation_radius_y: float = 0.0
    exit_loc: tuple = (0.0, 0.0, 0.0)
    exit_angle: float = 0.0
    interior: int = 0
    flags1: int = 0
    sky_color: int = 0
    interior_name: str = ""
    time_on: int = 0
    time_off: int = 0
    flags2: int = 0
    unknown: int = 0


@dataclass
class RoadSign2dfx:
    """Road/street sign (type 7) — up to 4 lines of on-mesh text.

    Payload = 88 bytes: size 2f (w,h), rotation 3f, flags u16, then four
    16-byte text lines + 2 pad bytes. ``flags`` packs line count (bits 0-1),
    max symbols/line (bits 2-3) and text colour (bits 4-5).
    """
    effect_id: int = 7
    loc: tuple = (0.0, 0.0, 0.0)
    size: tuple = (1.0, 1.0)
    rotation: tuple = (0.0, 0.0, 0.0)
    flags: int = 0
    text_lines: list = field(default_factory=lambda: ["", "", "", ""])


@dataclass
class Escalator2dfx:
    """Escalator (type 10). Payload = 40 bytes: bottom 3f, top 3f, end 3f,
    direction u32 (0 = down, 1 = up). ``end`` Z matches top when going up,
    bottom when going down."""
    effect_id: int = 10
    loc: tuple = (0.0, 0.0, 0.0)
    bottom: tuple = (0.0, 0.0, 0.0)
    top: tuple = (0.0, 0.0, 0.0)
    end: tuple = (0.0, 0.0, 0.0)
    direction: int = 0


@dataclass
class RawUnknown2dfx:
    """Byte-exact passthrough for 2DFX entry types we don't decode into
    typed objects (e.g. 2/5 interior, 8 trigger point, 9 cover point, or any
    future type). Preserving the raw payload means round-tripping a DFF never
    silently drops effects the engine still reads — the previous reader
    skipped unknown entries entirely."""
    effect_id: int = 0
    loc: tuple = (0.0, 0.0, 0.0)
    raw: bytes = b""


@dataclass
class Extension2dfx:
    """Container for all 2DFX effect entries."""
    entries: list = field(default_factory=list)  # list of Light2dfx/Particle2dfx/etc.

    def to_bytes(self, lib_id: int, rw_version: int = 0x36003) -> bytes:
        """Serialize 2DFX plugin to RenderWare chunk.

        Entries whose ``effect_id`` is outside the target game's
        allowlist (per ``_2DFX_ALLOWLIST_BY_RW_VERSION``) are silently
        dropped — the engine wouldn't render them anyway and emitting
        them risks corrupt-stream crashes. Default rw_version is SA so
        existing callers that don't pass version keep current behaviour.
        """
        if not self.entries:
            return b''

        allowed = _allowed_2dfx_ids(rw_version)
        # W12: an entry of a type the target engine has no handler for is
        # neither read nor skipped by the SA reader (0x6F9FD0) — the stream
        # desyncs and the model never loads. Drop it and say so. Raw
        # passthrough entries of a KNOWN type (8 trigger, 9 cover) stay.
        kept = []
        for e in self.entries:
            if e.effect_id in allowed:
                kept.append(e)
                continue
            _w = _t(
                "2DFX: эффект типа {0} неизвестен целевой игре — движок не умеет его пропустить, запись убрана из экспорта."
            ).format(e.effect_id)
            DFF_EXPORT_WARNINGS.append(_w)
            print(f"[DFF Export WARNING] {_w}")
        if not kept:
            return b''

        data = pack('<I', len(kept))

        for entry in kept:
            # Location (3 floats) + entry_type (u32) + entry_size (u32)
            entry_data = _write_2dfx_entry(entry)
            data += pack('<3f', *entry.loc)
            data += pack('<II', entry.effect_id, len(entry_data))
            data += entry_data

        return _chunk(CHUNK_2DFXPLG, data, lib_id)


@dataclass
class SkinData:
    """Bone skinning data for a geometry."""
    num_bones: int = 0
    num_used: int = 0              # Number of used bones
    max_weights: int = 4           # Max weights per vertex
    bones_used: list = field(default_factory=list)  # List of used bone indices
    bone_indices: list = field(default_factory=list)   # per-vertex: list[(b0,b1,b2,b3)]
    bone_weights: list = field(default_factory=list)    # per-vertex: list[(w0,w1,w2,w3)]
    bone_matrices: list = field(default_factory=list)   # per-bone: list[4x4 floats]

    def to_bytes(self, lib_id: int, rw_version: int = GTA_SA_VERSION) -> bytes:
        # Layout is keyed on the RW version, NOT on num_used: the SA engine
        # picks the pre-3.5 layout only when the maxWeights byte is 0, and
        # vanilla SA never ships num_used == 0. Keying on num_used wrote a
        # RW 3.4 skin (4-byte pad before every matrix, no 12-byte trailer)
        # into a RW 3.6 file whenever a mesh was weighted to bone 0 only.
        oldver = rw_version < 0x35000
        if oldver:
            # RW < 3.5 (III/VC): a plain u32 numBones header — no used-bone
            # count, no maxWeights byte, no used-bone list.
            data = pack('<3Bx', self.num_bones, 0, 0)
        else:
            data = pack('<3Bx', self.num_bones, self.num_used, self.max_weights)
            # bones_used array
            for bu in self.bones_used:
                data += pack('<B', bu)

        for indices in self.bone_indices:
            data += pack('<4B', *indices)

        for weights in self.bone_weights:
            data += pack('<4f', *weights)

        for matrix in self.bone_matrices:
            if oldver:
                data += pack('<I', 0xDEADDEAD)  # RW < 3.5 marker before each matrix
            flat = matrix[0] + matrix[1] + matrix[2] + matrix[3]
            data += pack('<16f', *flat)

        # SA version: 3 trailing zero floats (skin bounds/padding)
        if not oldver:
            data += pack('<3f', 0.0, 0.0, 0.0)

        return _chunk(CHUNK_SKIN_PLG, data, lib_id)


@dataclass
class HAnimBone:
    bone_id: int = 0
    index: int = 0
    bone_type: int = 0


@dataclass
class HAnimData:
    """Hierarchical animation data for a frame."""
    version: int = 0x100
    bone_id: int = 0
    bones: list = field(default_factory=list)  # list[HAnimBone], only on root
    # Hierarchy flags and max interpolated keyframe size — only meaningful
    # on the frame that carries the node table. Vanilla SA: 0 / 36. The
    # engine crashes on flags bit 2 (no matrices) and on a size < 28.
    flags: int = 0
    keyframe_size: int = 36

    def to_bytes(self, lib_id: int) -> bytes:
        data = pack('<3i', self.version, self.bone_id, len(self.bones))
        if self.bones:
            data += pack('<II', self.flags, self.keyframe_size)
            for bone in self.bones:
                data += pack('<3i', bone.bone_id, bone.index, bone.bone_type)
        return _chunk(CHUNK_HANIM_PLG, data, lib_id)


@dataclass
class DffFrame:
    """Transform frame in the hierarchy."""
    name: str = ""
    rotation: tuple = (1,0,0, 0,1,0, 0,0,1)  # 3x3 matrix as 9 floats (row-major)
    position: tuple = (0.0, 0.0, 0.0)
    parent: int = -1
    flags: int = 0
    hanim: Optional[HAnimData] = None
    user_data: Optional[UserData] = None
    write_name: bool = False  # Only True if original DFF had Frame Name chunk

    def header_bytes(self) -> bytes:
        """56 bytes: rotation(36) + position(12) + parent(4) + flags(4)."""
        data = pack('<9f', *self.rotation)
        data += pack('<3f', *self.position)
        data += pack('<iI', self.parent, self.flags)
        return data

    def extension_bytes(self, lib_id: int) -> bytes:
        ext = b''
        if self.write_name and self.name and self.name != "unknown":
            # Vanilla writes exactly strlen(name) bytes — no NUL, no 4-byte
            # padding (NodeNameStreamGetSize = strlen). The engine reads the
            # chunk into a 24-byte slot and writes name[length] = 0, so a
            # padded chunk of 24 bytes (20..23-char name) overflows the
            # slot by one byte; anything longer overflows in vanilla too.
            raw = self.name.encode('ascii', errors='replace')
            if len(raw) > FRAME_NAME_MAX:
                raise DffLimitError(_t(
                    "имя фрейма «{0}» длиннее {1} символов — движок хранит имя в 24-байтовом слоте и упадёт при загрузке. Переименуй объект/кость."
                ).format(self.name, FRAME_NAME_MAX))
            ext += _chunk(CHUNK_FRAME_NAME, raw, lib_id)
        if self.hanim:
            ext += self.hanim.to_bytes(lib_id)
        if self.user_data and self.user_data.sections:
            ext += self.user_data.to_bytes(lib_id)
        return _chunk(CHUNK_EXTENSION, ext, lib_id)


@dataclass
class DffGeometry:
    """Mesh geometry with vertices, normals, UVs, colors, materials."""
    vertices: list = field(default_factory=list)        # list[(x,y,z)]
    normals: list = field(default_factory=list)          # list[(x,y,z)]
    triangles: list = field(default_factory=list)        # list[Triangle]
    uv_layers: list = field(default_factory=list)        # list[list[TexCoords]]
    prelit_colors: list = field(default_factory=list)    # list[RGBA]
    materials: list = field(default_factory=list)         # list[DffMaterial]
    bounding_sphere: BoundingSphere = field(default_factory=BoundingSphere)

    export_normals: bool = True
    write_bin_mesh: bool = True
    pipeline: int = 0
    export_light: bool = True
    export_mod_color: bool = True

    original_flags: int = 0  # original geometry flags from import (for round-trip)

    skin: Optional[SkinData] = None
    extra_colors: Optional[ExtraVertColors] = None
    user_data: Optional[UserData] = None
    ext_2dfx: Optional[Extension2dfx] = None
    breakable: Optional[BreakableData] = None
    # Mobile (War Drum OpenGL) native geometry marker. Set by the
    # reader when CHUNK_NATIVE_DATA_PLG with platform=OGL is parsed —
    # tells the rest of the pipeline that vertex data came from a
    # mobile DFF (iOS/Android), so subsequent processing knows the
    # provenance even though vertices/uvs/normals/triangles look
    # identical to a PC geom by the time we're done.
    is_native_ogl: bool = False
    # Per-vertex bone data carved out of the WDGL buffer — kept in
    # private fields so SKIN_PLG processing can grab them. Pre-parser
    # geom has no skin, post-parser they bubble into geom.skin.
    _wdgl_bone_weights: Optional[list] = None
    _wdgl_bone_indices: Optional[list] = None
    # Round-trip raw bytes for Native Data PLG variants we don't decode
    # (PS2/Xbox/PSP/GC). When present, the writer emits these bytes
    # verbatim in the geometry extension instead of building our own.
    raw_native_data_plg: bytes = b''
    is_native_other_platform: int = 0   # platform ID we captured raw

    def _build_flags(self) -> int:
        num_uv = len(self.uv_layers)

        if self.original_flags:
            # Start from original flags, but update data-dependent bits
            flags = self.original_flags & 0xFFFF

            # Update UV flags based on actual data
            flags &= ~(GEOM_TEXTURED | GEOM_TEXTURED2)
            if num_uv == 1:
                flags |= GEOM_TEXTURED
            elif num_uv >= 2:
                # Vanilla GTA SA sets BOTH TEXTURED + TEXTURED2 on multi-UV
                # geometry. Clearing TEXTURED (the old Kam's convention) makes
                # the engine treat the geometry as non-textured on some render
                # paths — the remap car-paint texture isn't applied and the
                # body renders with its (darker) base colour. Match vanilla.
                flags |= GEOM_TEXTURED | GEOM_TEXTURED2

            # Update prelit based on actual data
            if self.prelit_colors:
                flags |= GEOM_PRELIT
            else:
                flags &= ~GEOM_PRELIT

            # Update normals
            if self.export_normals and self.normals:
                flags |= GEOM_NORMALS
            else:
                flags &= ~GEOM_NORMALS

            # Light / Modulate Color — user-toggleable on the N-panel,
            # honor the current value over what was in original_flags.
            # Без этого пользовательский inu.light = False игнорируется
            # на ре-экспорте импортированной модели (original_flags
            # перезаписывает галку из UI).
            if self.export_light:
                flags |= GEOM_LIGHT
            else:
                flags &= ~GEOM_LIGHT
            if self.export_mod_color:
                flags |= GEOM_MOD_COLOR
            else:
                flags &= ~GEOM_MOD_COLOR

            flags = (flags & 0xFFFF) | ((num_uv & 0xFF) << 16)
            return flags

        flags = GEOM_POSITIONS
        if num_uv == 1:
            flags |= GEOM_TEXTURED
        elif num_uv >= 2:
            # Vanilla GTA SA sets BOTH TEXTURED + TEXTURED2 on multi-UV
            # geometry (not Kam's TEXTURED2-only) — see the original_flags
            # path above for why (remap paint renders untextured/dark).
            flags |= GEOM_TEXTURED | GEOM_TEXTURED2
        if self.prelit_colors:
            flags |= GEOM_PRELIT
        if self.export_normals and self.normals:
            flags |= GEOM_NORMALS
        if self.export_light:
            flags |= GEOM_LIGHT
        if self.export_mod_color:
            flags |= GEOM_MOD_COLOR

        # UV layer count in bits 16-23
        flags |= (num_uv & 0xFF) << 16

        return flags

    def _write_bin_mesh_plg(self, lib_id: int) -> bytes:
        """Group triangles by material index for Binary Mesh PLG."""
        # Group triangles by material
        mat_groups = {}
        for tri in self.triangles:
            mat_groups.setdefault(tri.material, []).append(tri)

        total_indices = len(self.triangles) * 3

        # bytearray — see DffGeometry.to_bytes: per-triangle `bytes +=` is
        # O(N²); in-place bytearray extend is O(N).
        data = bytearray(pack('<III', 0, len(mat_groups), total_indices))

        for mat_idx in sorted(mat_groups.keys()):
            tris = mat_groups[mat_idx]
            indices_count = len(tris) * 3
            data += pack('<II', indices_count, mat_idx)
            for tri in tris:
                data += pack('<III', tri.a, tri.b, tri.c)

        return _chunk(CHUNK_BIN_MESH_PLG, bytes(data), lib_id)

    def _build_wdgl_native_buffer(self, rw_version: int = GTA_SA_VERSION) -> tuple:
        """Pack our geom into War Drum OpenGL interleaved buffer.

        Returns (descriptors_bytes, vertex_buffer_bytes). The caller wraps
        them inside CHUNK_NATIVE_DATA_PLG > CHUNK_STRUCT alongside the
        platform u32. Layout chosen for simplicity + safety:
          - position : 3×FLOAT   (12B)
          - normal   : 3×FLOAT   (12B, if present)
          - uv0      : 2×FLOAT   ( 8B, scaled by 512 to match reader)
          - prelit   : 4×UBYTE   ( 4B, normalised)
          - extra    : 4×UBYTE   ( 4B, normalised, SA night colours)
          - bone_idx : 4×UBYTE   ( 4B, not normalised — raw bone IDs)
          - bone_wt  : 4×FLOAT   (16B)
        Skipping a layer (no normals/UVs/etc) skips the whole attribute,
        keeping stride compact. Real mobile DFFs use SHORT/UBYTE for
        many of these to save space; we use FLOAT for safety since War
        Drum's reader honours the descriptor regardless.
        """
        num_verts = len(self.vertices)
        attribs = []  # (id, type, size, normalized, per_vert_bytes)

        attribs.append((WDGL_ATTRIB_COORD,     WDGL_TYPE_FLOAT, 3, False, 12))
        if self.export_normals and self.normals:
            attribs.append((WDGL_ATTRIB_NORMAL, WDGL_TYPE_FLOAT, 3, False, 12))
        if self.uv_layers:
            attribs.append((WDGL_ATTRIB_TEX_COORD, WDGL_TYPE_FLOAT, 2, False, 8))
        if self.prelit_colors:
            attribs.append((WDGL_ATTRIB_PRELIT, WDGL_TYPE_UBYTE, 4, True, 4))
        # Night vertex colors — SA-only extension (RW 3.6+). III/VC's
        # mobile engines ignore the chunk on PC and lack the WDGL slot
        # on mobile, so we drop the attribute for older RW versions.
        if (self.extra_colors and self.extra_colors.colors
                and rw_version >= 0x36000):
            attribs.append((WDGL_ATTRIB_EXTRA_COLOR, WDGL_TYPE_UBYTE, 4, True, 4))
        has_skin = bool(self.skin and self.skin.bone_indices and self.skin.bone_weights)
        if has_skin:
            attribs.append((WDGL_ATTRIB_BONE_INDEX, WDGL_TYPE_UBYTE, 4, False, 4))
            attribs.append((WDGL_ATTRIB_BONE_WEIGHT, WDGL_TYPE_FLOAT, 4, False, 16))

        stride = sum(a[4] for a in attribs)

        # Build descriptor block (24 B each) with cumulative offsets.
        offsets = []
        running = 0
        for a in attribs:
            offsets.append(running)
            running += a[4]
        descs_bytes = b''
        for (aid, atype, asize, anorm, _per), off in zip(attribs, offsets):
            descs_bytes += pack('<IiIiII',
                                aid, atype, 1 if anorm else 0, asize, stride, off)

        # Build interleaved vertex buffer.
        buf = bytearray(num_verts * stride)
        uv0 = self.uv_layers[0] if self.uv_layers else None
        bidx = self.skin.bone_indices if has_skin else None
        bwts = self.skin.bone_weights if has_skin else None
        ec = self.extra_colors.colors if (self.extra_colors and self.extra_colors.colors) else None

        for vi in range(num_verts):
            base = vi * stride
            cur = base
            for (aid, atype, asize, anorm, per) in attribs:
                if aid == WDGL_ATTRIB_COORD:
                    v = self.vertices[vi]
                    pack_into = pack('<3f', v[0], v[1], v[2])
                    buf[cur:cur+12] = pack_into
                elif aid == WDGL_ATTRIB_NORMAL:
                    n = self.normals[vi]
                    buf[cur:cur+12] = pack('<3f', n[0], n[1], n[2])
                elif aid == WDGL_ATTRIB_TEX_COORD:
                    tc = uv0[vi] if uv0 and vi < len(uv0) else None
                    if tc is None:
                        buf[cur:cur+8] = pack('<2f', 0.0, 0.0)
                    else:
                        # Reader divides by 512 — pre-scale to keep round-trip stable.
                        buf[cur:cur+8] = pack('<2f', tc.u * 512.0, tc.v * 512.0)
                elif aid == WDGL_ATTRIB_PRELIT:
                    c = self.prelit_colors[vi] if vi < len(self.prelit_colors) else None
                    if c is None:
                        buf[cur:cur+4] = pack('<4B', 255, 255, 255, 255)
                    else:
                        buf[cur:cur+4] = pack('<4B', c.r & 0xFF, c.g & 0xFF,
                                              c.b & 0xFF, c.a & 0xFF)
                elif aid == WDGL_ATTRIB_EXTRA_COLOR:
                    c = ec[vi] if ec and vi < len(ec) else None
                    if c is None:
                        buf[cur:cur+4] = pack('<4B', 255, 255, 255, 255)
                    else:
                        buf[cur:cur+4] = pack('<4B', c.r & 0xFF, c.g & 0xFF,
                                              c.b & 0xFF, c.a & 0xFF)
                elif aid == WDGL_ATTRIB_BONE_INDEX:
                    bi = bidx[vi] if bidx and vi < len(bidx) else (0, 0, 0, 0)
                    buf[cur:cur+4] = pack('<4B',
                                          bi[0] & 0xFF, bi[1] & 0xFF,
                                          bi[2] & 0xFF, bi[3] & 0xFF)
                elif aid == WDGL_ATTRIB_BONE_WEIGHT:
                    bw = bwts[vi] if bwts and vi < len(bwts) else (0.0, 0.0, 0.0, 0.0)
                    buf[cur:cur+16] = pack('<4f', *bw)
                cur += per

        # Header inside WDGL block: just numAttribs u32 + descriptors + buffer.
        return (pack('<I', len(attribs)) + descs_bytes, bytes(buf))

    def _write_native_data_plg(self, lib_id: int,
                                rw_version: int = GTA_SA_VERSION) -> bytes:
        """Wrap WDGL geometry in CHUNK_NATIVE_DATA_PLG with platform=OGL."""
        descs_and_header, vertex_buf = self._build_wdgl_native_buffer(rw_version)
        # platform u32 + numAttribs + descriptors + vertex buffer
        struct_body = pack('<I', NATIVE_PLATFORM_OGL) + descs_and_header + vertex_buf
        body = _chunk(CHUNK_STRUCT, struct_body, lib_id)
        return _chunk(CHUNK_NATIVE_DATA_PLG, body, lib_id)

    def to_bytes(self, lib_id: int, rw_version: int) -> bytes:
        flags = self._build_flags()
        # Native export (mobile OGL OR round-tripped PS2/Xbox/PSP/GC) —
        # flip GEOM_NATIVE so the engine looks in Native Data PLG
        # instead of the main Struct.
        if self.is_native_ogl or self.raw_native_data_plg:
            flags |= GEOM_NATIVE
        num_verts = len(self.vertices)
        num_tris = len(self.triangles)

        # Struct: header.
        # bytearray, NOT bytes: every section below appends per-vertex /
        # per-tri. `bytes += pack(...)` reallocates and copies the WHOLE
        # accumulated buffer each time → O(N²) for an N-vertex mesh and the
        # dominant cost of a large export. bytearray extends in place →
        # amortized O(N).
        struct_data = bytearray(pack('<IIII', flags, num_tris, num_verts, 1))

        # Surface properties (for older versions)
        if rw_version < 0x34000:
            struct_data += pack('<3f', 1.0, 1.0, 1.0)

        is_native = self.is_native_ogl or bool(self.raw_native_data_plg)
        if not is_native:
            # ── PC / classic path ──
            # Prelit colors
            if flags & GEOM_PRELIT:
                for c in self.prelit_colors:
                    struct_data += pack('<4B', c.r, c.g, c.b, c.a)

            # UV layers
            for uv_layer in self.uv_layers:
                for tc in uv_layer:
                    struct_data += pack('<2f', tc.u, tc.v)

            # Triangles (RenderWare format: b, a, material, c)
            # Indices are u16; vertex counts above 65535 are rejected by
            # _validate_geometry_writable before we get here.
            for tri in self.triangles:
                struct_data += pack('<4H', tri.b, tri.a, tri.material, tri.c)

        # Bounding sphere — emitted on both paths.
        bs = self.bounding_sphere
        struct_data += pack('<4f', bs.x, bs.y, bs.z, bs.radius)

        if is_native:
            # Native path: vertex/normal/uv data lives in Native Data PLG.
            # Struct still needs the morph trailer, but has_pos/has_norm = 0.
            struct_data += pack('<II', 0, 0)
        else:
            # Has vertices / has normals flags
            struct_data += pack('<II', 1 if self.vertices else 0,
                                       1 if (self.export_normals and self.normals) else 0)

            # Vertices
            if self.vertices:
                for v in self.vertices:
                    struct_data += pack('<3f', v[0], v[1], v[2])

            # Normals
            if self.export_normals and self.normals:
                for n in self.normals:
                    struct_data += pack('<3f', n[0], n[1], n[2])

        body = _chunk(CHUNK_STRUCT, struct_data, lib_id)

        # Material list
        mat_struct = pack('<I', len(self.materials))
        for _ in self.materials:
            mat_struct += pack('<i', -1)
        mat_body = _chunk(CHUNK_STRUCT, mat_struct, lib_id)
        for mat in self.materials:
            mat_body += mat.to_bytes(lib_id, rw_version)
        body += _chunk(CHUNK_MATERIAL_LIST, mat_body, lib_id)

        # Extensions
        ext_data = b''

        # Native Data PLG comes first in extension on mobile DFFs —
        # carries the actual vertex buffer that the engine's WDGL
        # uploader expects. BIN_MESH_PLG that follows carries the
        # triangle index list (same as PC). For non-OGL native
        # platforms (PS2/Xbox/PSP/GC) we round-trip raw bytes instead
        # of building from scratch — we don't decode those formats.
        if self.raw_native_data_plg:
            ext_data += self.raw_native_data_plg
        elif self.is_native_ogl:
            ext_data += self._write_native_data_plg(lib_id, rw_version)

        if self.write_bin_mesh:
            ext_data += self._write_bin_mesh_plg(lib_id)

        if self.skin:
            if self.is_native_ogl:
                # NativeOGLSkin = u32 num_bones + 16f matrices. Per-vertex
                # weights/indices are already inside the WDGL buffer.
                sk_data = pack('<I', self.skin.num_bones)
                for matrix in self.skin.bone_matrices:
                    flat = matrix[0] + matrix[1] + matrix[2] + matrix[3]
                    sk_data += pack('<16f', *flat)
                ext_data += _chunk(CHUNK_SKIN_PLG, sk_data, lib_id)
            else:
                ext_data += self.skin.to_bytes(lib_id, rw_version)

        # Night Vertex Colors (CHUNK_EXTRA_COLORS = 0x253F2F9) — SA-only
        # extension. III/VC engines don't read it; emitting on those
        # versions just bloats the file. Gate on rw_version ≥ SA (0x36003).
        if (self.extra_colors and self.extra_colors.colors
                and rw_version >= 0x36000):
            # W14: the engine reads exactly numVertices × 4 bytes here,
            # ignoring the chunk length — a shorter or longer list
            # desynchronises the stream. Pad with white / truncate, warn.
            colors = list(self.extra_colors.colors)
            nv = len(self.vertices)
            if len(colors) != nv:
                _w = _t(
                    "ночных цветов {0}, а вершин {1} — список выровнен по числу вершин (движок читает ровно numVertices×4 байта)."
                ).format(len(colors), nv)
                DFF_EXPORT_WARNINGS.append(_w)
                print(f"[DFF Export WARNING] {_w}")
                colors = (colors + [RGBA()] * nv)[:nv]
            ec_data = bytearray(pack('<I', 1))  # magic; bytearray → O(N)
            for c in colors:
                ec_data += pack('<4B', c.r, c.g, c.b, c.a)
            ext_data += _chunk(CHUNK_EXTRA_COLORS, bytes(ec_data), lib_id)

        # Pipeline chunk пишем на уровне atomic extension (см. DffClump.to_bytes).
        # Раньше писался здесь, в geometry extension, но librwgta/Seggaeman/Kam
        # хранят его в atomic — для полной совместимости делаем как они.

        if self.user_data and self.user_data.sections:
            ext_data += self.user_data.to_bytes(lib_id)

        # NOTE: NO MatFX (0x120) chunk on the GEOMETRY extension. MatFX is a
        # material/atomic RW plugin — vanilla GTA SA vehicle geometries do NOT
        # carry a 0x120 here (they carry Breakable instead). Writing 0x120 on
        # the geometry made the engine misread the geometry extension and the
        # env-map reflections stopped drawing → the car rendered dull/dark.
        # The MatFX flag lives on the ATOMIC (see DffClump.to_bytes) where the
        # engine expects it, plus the per-material effect data — that's all the
        # game needs.

        # 2DFX effects (usually on last geometry only). Pass through
        # rw_version so types not supported by the target engine
        # (e.g. SunGlare on III/VC) are dropped before emit.
        if self.ext_2dfx and self.ext_2dfx.entries:
            ext_data += self.ext_2dfx.to_bytes(lib_id, rw_version)

        # Breakable Objects extension (0x253F2FD)
        if self.breakable:
            ext_data += self.breakable.to_bytes(lib_id)

        body += _chunk(CHUNK_EXTENSION, ext_data, lib_id)
        return _chunk(CHUNK_GEOMETRY, body, lib_id)


@dataclass
class DffAtomic:
    """Links a frame to a geometry."""
    frame_index: int = 0
    geometry_index: int = 0
    # bit 0 (1) = rpATOMICCOLLISIONTEST, bit 2 (4) = rpATOMICRENDER.
    # Vanilla SA atomics (verified vs. nt_windmill, derrick01, etc.)
    # all use 5 = render + collision; flags=4 produces atomics the
    # collision tester silently rejects, which can crash CClumpAnimMgr
    # when applying an IFP track to an animated map object.
    flags: int = 0x05
    unused: int = 0


@dataclass
class DffLight:
    """RenderWare light in the clump (Omni/Point light for 2DFX)."""
    frame_index: int = 0
    radius: float = 200.0
    color: tuple = (1.0, 1.0, 1.0)
    direction: float = 0.0
    light_type: int = 0x80  # rpLIGHTPOINT (128)
    flags: int = 3          # rpLIGHTLIGHTATOMICS | rpLIGHTLIGHTWORLD


_U16_MAX = 65535
_U8_MAX = 255
# NodeName frame plugin: 24-byte slot, NAME_LENGTH 23 + terminating NUL.
FRAME_NAME_MAX = 23
# RwTexture name: 32-byte field, RwTextureSetName forces name[31] = 0.
TEXTURE_NAME_MAX = 31

# Non-fatal warnings collected during the last DFF validation/export.
# Triangle-count "over limit" is NOT a hard format limit (count is u32),
# so it lands here instead of raising — the export operator reads this
# list after writing and surfaces it via self.report({'WARNING'}).
# Cleared at the start of every _validate_dff_writable().
DFF_EXPORT_WARNINGS = []


def _t(s: str) -> str:
    """Lazy translation for user-facing error/warning text in this
    otherwise Blender-free core module. Falls back to the raw Russian
    string when bpy/T isn't available (standalone unit tests), so the
    module stays import-safe outside Blender."""
    try:
        from .. import T
        return T(s)
    except Exception:
        return s


class DffLimitError(ValueError):
    """Raised when a DffClump exceeds the binary format's uint16/uint8 limits.

    Wraps the cryptic ``struct.pack('H'/'B', ...)`` overflow with a message
    that names the geometry index and the specific field that broke the limit.
    """
    pass


def _validate_geometry_writable(geom: 'DffGeometry', idx: int):
    """Reject geometries that would overflow RenderWare's u16/u8 fields.

    DffGeometry.to_bytes() packs triangles as ``<4H`` (b, a, material, c) — so
    material count is capped at 65 536 (indices 0..65 535) and the vertex
    count at 65 535: RpGeometryCreate refuses numVerts >= 0x10000 (DFF-09),
    so a 65 536-vertex geometry would be written and then never load.
    UV layer count is packed into 8 bits of the geometry flags. Skin data
    packs bone counts and per-vertex bone indices as u8 (max 255).
    """
    n_verts = len(geom.vertices)
    if n_verts > _U16_MAX:
        # RenderWare stores triangle indices as u16. Masking the indices
        # used to let the write "succeed" with wrapped, garbage triangles;
        # refuse instead so the user splits the mesh.
        raise DffLimitError(_t(
            "геометрия #{0}: {1} вершин — RenderWare хранит индексы треугольников в uint16 (максимум {2} вершин). Разбей меш на части или упрости (Decimate)."
        ).format(idx, n_verts, _U16_MAX))

    n_tris = len(geom.triangles)
    if n_tris > _U16_MAX + 1:
        # Triangle COUNT is stored as u32 — this is NOT a hard format
        # limit. Only the per-triangle vertex INDICES are u16, and those
        # are bounded by the vertex check above. So a mesh with many
        # triangles but ≤65536 vertices is perfectly valid. Warn (so the
        # user knows the mesh is heavy and some old tools/engine paths
        # may struggle) but DON'T block the export.
        _w = _t(
            "геометрия #{0}: {1} треугольников — много для одной геометрии. Экспорт продолжен (счётчик треугольников u32), но движок/инструменты могут тормозить. Рекомендуется разбить меш на части."
        ).format(idx, n_tris)
        DFF_EXPORT_WARNINGS.append(_w)
        print(f"[DFF Export WARNING] {_w}")

    n_mats = len(geom.materials)
    if n_mats > _U16_MAX + 1:
        raise DffLimitError(_t(
            "геометрия #{0}: {1} материалов — RenderWare хранит material-индекс в uint16 (максимум {2}). Используй меньше материалов."
        ).format(idx, n_mats, _U16_MAX + 1))

    n_uv = len(geom.uv_layers)
    if n_uv > _U8_MAX:
        raise DffLimitError(_t(
            "геометрия #{0}: {1} UV-слоёв — флаги геометрии хранят кол-во UV в uint8 (максимум {2}). GTA SA рендерит максимум 2."
        ).format(idx, n_uv, _U8_MAX))

    if geom.skin is not None:
        skin = geom.skin
        if skin.num_bones > _U8_MAX:
            raise DffLimitError(_t(
                "геометрия #{0}: skin.num_bones={1} — RenderWare skin хранит счётчики костей в uint8 (максимум {2})."
            ).format(idx, skin.num_bones, _U8_MAX))
        if skin.num_used > _U8_MAX:
            raise DffLimitError(_t(
                "геометрия #{0}: skin.num_used={1} > {2} (uint8)."
            ).format(idx, skin.num_used, _U8_MAX))
        if skin.max_weights > _U8_MAX:
            raise DffLimitError(_t(
                "геометрия #{0}: skin.max_weights={1} > {2} (uint8)."
            ).format(idx, skin.max_weights, _U8_MAX))
        for bu in skin.bones_used:
            if not (0 <= bu <= _U8_MAX):
                raise DffLimitError(_t(
                    "геометрия #{0}: skin.bones_used содержит индекс {1} вне 0..{2} (uint8)."
                ).format(idx, bu, _U8_MAX))
        for vi, indices in enumerate(skin.bone_indices):
            for bi in indices:
                if not (0 <= bi <= _U8_MAX):
                    raise DffLimitError(_t(
                        "геометрия #{0}: skin.bone_indices[{1}] содержит индекс {2} вне 0..{3} (uint8). Слишком много костей в арматуре."
                    ).format(idx, vi, bi, _U8_MAX))


def _validate_dff_writable(clump: 'DffClump'):
    """Validate everything that would be packed from Python objects.

    Skips geometries when ``raw_geometry_list`` is set (round-trip path —
    those bytes are reused as-is and don't go through ``geom.to_bytes``).
    """
    DFF_EXPORT_WARNINGS.clear()
    if clump.raw_geometry_list:
        return
    for idx, geom in enumerate(clump.geometries):
        _validate_geometry_writable(geom, idx)


@dataclass
class DffClump:
    """Root DFF structure containing frames, geometries, and atomics."""
    frames: list = field(default_factory=list)       # list[DffFrame]
    geometries: list = field(default_factory=list)    # list[DffGeometry]
    atomics: list = field(default_factory=list)       # list[DffAtomic]
    lights: list = field(default_factory=list)        # list[DffLight]
    version: int = GTA_SA_VERSION
    collision_data: bytes = b''
    raw_frame_list: bytes = b''  # Raw frame list bytes for round-trip
    raw_geometry_list: bytes = b''  # Raw geometry list bytes for round-trip
    raw_atomics: bytes = b''  # Raw atomic bytes for round-trip
    uv_anim_dict: Optional['UVAnimDict'] = None  # Clump-level UV anim dictionary
    # Top-level RW chunks that appear in the file BEFORE the Clump
    # chunk — vanilla SA ships some files like that (UV Animation Dict
    # at 0x2B, Animation at 0x1B). Stored verbatim and re-emitted on
    # export to preserve the file's binary identity.
    pre_clump_data: bytes = b''
    # True when at least one geometry was parsed from Native Data PLG
    # (OpenGL/War Drum). Set after read_dff(). The dff import operator
    # uses this to flip scene.gtatools_platform = MOBILE.
    is_mobile: bool = False

    def to_bytes(self) -> bytes:
        _validate_dff_writable(self)

        lib_id = make_library_id(self.version)
        rw_version = self.version

        # Clump struct
        num_atomics = len(self.atomics)
        if num_atomics == 0 and self.raw_atomics:
            num_atomics = 1  # At least 1 atomic in raw data
        num_lights = len(self.lights)
        clump_struct = pack('<III', num_atomics, num_lights, 0)
        body = _chunk(CHUNK_STRUCT, clump_struct, lib_id)

        # Frame list — use raw bytes for perfect round-trip if available
        if self.raw_frame_list:
            body += _chunk(CHUNK_FRAME_LIST, self.raw_frame_list, lib_id)
        else:
            frame_struct = pack('<I', len(self.frames))
            for frame in self.frames:
                frame_struct += frame.header_bytes()
            frame_body = _chunk(CHUNK_STRUCT, frame_struct, lib_id)
            for frame in self.frames:
                frame_body += frame.extension_bytes(lib_id)
            body += _chunk(CHUNK_FRAME_LIST, frame_body, lib_id)

        # Geometry list — use raw bytes for round-trip if available
        if self.raw_geometry_list:
            body += self.raw_geometry_list
        else:
            geom_struct = pack('<I', len(self.geometries))
            geom_body = _chunk(CHUNK_STRUCT, geom_struct, lib_id)
            for geom in self.geometries:
                geom_body += geom.to_bytes(lib_id, rw_version)
            body += _chunk(CHUNK_GEOMETRY_LIST, geom_body, lib_id)

        # Atomics — use raw for round-trip if available
        if self.raw_atomics:
            body += self.raw_atomics
        else:
            for atomic in self.atomics:
                atomic_struct = pack('<IIII',
                    atomic.frame_index, atomic.geometry_index,
                    atomic.flags, atomic.unused)
                atomic_body = _chunk(CHUNK_STRUCT, atomic_struct, lib_id)

                # Atomic extensions
                atomic_ext = b''
                geom = self.geometries[atomic.geometry_index]
                if geom.skin:
                    atomic_ext += _chunk(0x001F, pack('<II', 0x0116, 1), lib_id)  # Right to Render
                    atomic_ext += _chunk(0x0120, pack('<I', 0), lib_id)  # Node Name PLG (required for SA skinned)
                # MatFX flag (Material Effects PLG 0x120 = 1) — engine uses the
                # MatFX pipeline. Vanilla GTA SA vehicles carry it on EVERY
                # effect atomic (env / reflection / specular / bump / dual /
                # uv-anim). The narrower bump/env/dual/uv-anim test left
                # reflection/specular-only parts WITHOUT the flag, so they
                # skipped the effect pipeline and rendered slightly darker.
                # Match vanilla — same effect set as Right-to-Render below.
                # W7 (left as is, by design): a Reflection Material chunk on
                # a plain map building (Max-exporter leftover, e.g.
                # airport_03_sfse / cables) also lands here, so such
                # buildings get R2R + MatFX=1 that vanilla lacks. The engine
                # treats it as a NULL effect and renders identically.
                _matfx = any(
                    m.bump_map or m.env_map or m.dual_texture
                    or m.specular or m.reflection
                    or getattr(m, 'uv_anim_names', None)
                    for m in geom.materials)
                # Right to Render (0x1F) = (0x120, 0): bind the atomic to the
                # MatFX render pipeline. Vanilla VEHICLES carry this — and BEFORE
                # the MatFX flag — on every effect atomic. WITHOUT it the engine
                # sees the MatFX flag but never runs the MatFX render callback,
                # so env-map reflections / vehicle specular don't draw and the
                # car renders dull/dark. Gate on env/reflection/specular/bump
                # (SA vehicles), EXCLUDE uv-anim (0x1F breaks UV-anim playback)
                # and skinned (writes its own 0x1F above).
                _veh_fx = any(
                    m.env_map or m.reflection or m.specular or m.bump_map
                    for m in geom.materials)
                _uvanim = any(getattr(m, 'uv_anim_names', None)
                              for m in geom.materials)
                if (_veh_fx and not _uvanim and not geom.skin
                        and rw_version >= 0x36000):
                    atomic_ext += _chunk(0x001F, pack('<II', 0x0120, 0), lib_id)
                if _matfx:
                    atomic_ext += _chunk(CHUNK_MATFX_PLG, pack('<I', 1), lib_id)
                # Pipeline chunk (0x253F2F3) — SA-specific RW pipeline ID
                # used for the vehicle env-map pipeline (0x53F2009A).
                # III/VC engines don't read this chunk and the SA vehicle
                # pipeline values would be meaningless to those games
                # anyway. Gate on rw_version ≥ SA (0x36000).
                if geom.pipeline and rw_version >= 0x36000:
                    atomic_ext += _chunk(CHUNK_PIPELINE_SET, pack('<I', geom.pipeline), lib_id)

                atomic_body += _chunk(CHUNK_EXTENSION, atomic_ext, lib_id)
                body += _chunk(CHUNK_ATOMIC, atomic_body, lib_id)

        # Lights (RW Light objects for 2DFX)
        for light in self.lights:
            # Frame link struct (precedes the Light chunk in clump)
            body += _chunk(CHUNK_STRUCT, pack('<I', light.frame_index), lib_id)

            # Light struct: radius(f), color_rgb(3f), direction(f), flags_type(u32)
            flags_type = (light.light_type << 16) | light.flags
            light_struct = pack('<f3ffI',
                                light.radius,
                                *light.color,
                                light.direction,
                                flags_type)
            light_body = _chunk(CHUNK_STRUCT, light_struct, lib_id)
            # Light extension (empty)
            light_body += _chunk(CHUNK_EXTENSION, b'', lib_id)

            body += _chunk(CHUNK_LIGHT, light_body, lib_id)

        # Clump extension
        clump_ext = b''
        if self.collision_data:
            clump_ext += _chunk(CHUNK_COLLISION_MODEL, self.collision_data, lib_id)
        body += _chunk(CHUNK_EXTENSION, clump_ext, lib_id)

        # UV Animation Dictionary (CHUNK_UV_ANIM_DICT = 0x2B) ДОЛЖЕН быть
        # КОРНЕВЫМ чанком ПЕРЕД Clump: движок RW сначала читает словарь в
        # глобальный реестр, затем кламп резолвит ссылки материалов (UVAnim
        # PLG 0x135) по имени. Если положить его в расширение клампа — игра
        # словарь не находит, и загрузка модели падает (модель невидима).
        # Добавлено в RW 3.5 (VC); для III (RW 3.3) пропускаем.
        pre = self.pre_clump_data
        uv_dict_bytes = b''
        if (self.uv_anim_dict and self.uv_anim_dict.anims
                and rw_version >= 0x35000):
            uv_dict_bytes = self.uv_anim_dict.to_bytes(lib_id)
            # На случай round-trip: убрать уже имеющийся 0x2B из pre-clump,
            # чтобы не задвоить словарь.
            pre = _strip_root_chunk(pre, CHUNK_UV_ANIM_DICT)

        # Pre-Clump chunks (UV Animation Dictionary, etc.) preserved
        # from the original file. Re-emitted verbatim before the Clump
        # so round-trip stays byte-identical for files like
        # chinafurn1.dff that the engine reads via linear chunk walk.
        return pre + uv_dict_bytes + _chunk(CHUNK_CLUMP, body, lib_id)


def write_dff(clump: DffClump) -> bytes:
    """Serialize a DffClump to DFF binary format."""
    return clump.to_bytes()


def write_dff_file(filepath: str, clump: DffClump):
    """Write a DffClump to a .dff file."""
    with open(filepath, 'wb') as f:
        f.write(clump.to_bytes())


# ── Reader ──────────────────────────────────────────────────────

def _decode_library_id(lib_id: int):
    """Decode 32-bit library ID into (version, build)."""
    if lib_id & 0xFFFF0000 == 0:
        return (lib_id << 8, 0)
    version = (((lib_id >> 14) & 0x3FF00) + 0x30000) | ((lib_id >> 16) & 0x3F)
    build = lib_id & 0xFFFF
    return (version, build)


def _read_chunk_header(r: BinaryReader):
    """Read a 12-byte RW chunk header. Returns (type, size, lib_id)."""
    chunk_type, size, lib_id = r.read('<III')
    return chunk_type, size, lib_id


def _read_string_chunk(r: BinaryReader, size: int) -> str:
    """Read a RW String chunk payload."""
    raw = r.read_bytes(size)
    end = raw.find(b'\x00')
    if end == -1:
        end = len(raw)
    return raw[:end].decode('ascii', errors='replace')


def _read_texture_chunk(r: BinaryReader, size: int) -> DffTexture:
    """Read a Texture chunk (struct + name string + mask string + ext)."""
    end = r.pos + size
    tex = DffTexture()

    # Struct
    ct, cs, cl = _read_chunk_header(r)
    if ct == CHUNK_STRUCT:
        tex.filters = r.read_one('<I')  # full 32-bit filter/addressing word
        r.skip(cs - 4)  # skip remaining struct bytes

    # Name string
    ct, cs, cl = _read_chunk_header(r)
    if ct == CHUNK_STRING:
        tex.name = _read_string_chunk(r, cs)
        # GTA texture names must be ASCII. A non-ASCII byte (modder's locale,
        # e.g. Turkish 'ö') gets decoded to U+FFFD here and would be written
        # back as '?' on export — a different name that won't link in-game.
        # Warn so the user renames the texture at the source instead.
        if '�' in tex.name:  # U+FFFD = decode-replacement char
            print(f"[INU] WARN: texture name '{tex.name}' contains a non-ASCII "
                  f"character — GTA names must be ASCII (a-z, 0-9, _). Rename "
                  f"the texture in the TXD + material or it won't link in-game.")

    # Mask string
    if r.pos < end:
        ct, cs, cl = _read_chunk_header(r)
        if ct == CHUNK_STRING:
            tex.mask = _read_string_chunk(r, cs)
        else:
            r.skip(cs)

    # Skip extension
    r.seek(end)
    return tex


def _read_material_chunk(r: BinaryReader, size: int, rw_version: int) -> DffMaterial:
    """Read a Material chunk."""
    end = r.pos + size
    mat = DffMaterial()

    # Struct
    ct, cs, cl = _read_chunk_header(r)
    struct_end = r.pos + cs
    r.skip(4)  # padding
    mat.color = RGBA(*r.read('<4B'))
    _unused, has_tex = r.read('<II')
    if rw_version > 0x30400:
        mat.surface = SurfaceProperties(*r.read('<3f'))
    r.seek(struct_end)

    # Texture
    if has_tex:
        ct, cs, cl = _read_chunk_header(r)
        if ct == CHUNK_TEXTURE:
            mat.texture = _read_texture_chunk(r, cs)
        else:
            r.skip(cs)

    # Extension
    if r.pos < end:
        ct, cs, cl = _read_chunk_header(r)
        if ct == CHUNK_EXTENSION:
            ext_end = r.pos + cs
            while r.pos < ext_end:
                ect, ecs, ecl = _read_chunk_header(r)
                plugin_end = r.pos + ecs
                if ect == CHUNK_MATFX_PLG:
                    _read_matfx_plugin(r, ecs, mat)
                elif ect == CHUNK_SPECULAR_MAT:
                    level = r.read_one('<f')
                    name_raw = r.read_bytes(min(24, ecs - 4))
                    nm_end = name_raw.find(b'\x00')
                    spec_name = name_raw[:nm_end].decode('ascii', errors='replace') if nm_end >= 0 else name_raw.decode('ascii', errors='replace')
                    mat.specular = SpecularMaterial(level=level, name=spec_name)
                elif ect == CHUNK_REFLECTION_MAT:
                    vals = r.read('<5f')
                    mat.reflection = ReflectionMaterial(*vals)
                elif ect == CHUNK_USERDATA_PLG:
                    mat.user_data = _read_userdata_plugin(r, ecs)
                elif ect == CHUNK_UV_ANIM_PLG:
                    # Material-level UV anim reference — list of names
                    # pointing into the clump-level UV anim dict.
                    mat.uv_anim_names = _read_uv_anim_plg(
                        r.data, r.pos, ecs)
                else:
                    pass
                r.seek(plugin_end)
        else:
            r.skip(cs)

    r.seek(end)
    return mat


def _read_material_list(r: BinaryReader, matlist_size: int,
                        rw_version: int) -> list:
    """Read a Material List chunk body (its 12-byte header already consumed).

    The RW material-list index array has ONE entry PER SLOT:
      * ``< 0``  → a new MATERIAL chunk follows inline;
      * ``>= 0`` → REUSE the material at that earlier slot index (RW exporters
        deduplicate when one material is shared across slots).

    So the number of inline MATERIAL chunks equals the count of negative
    entries — NOT ``numMaterials``. The old reader read ``numMaterials``
    chunks unconditionally and ignored the index array, which over-read and
    mis-mapped materials for any DFF that reused a material (wrong textures
    on parts of the model). This mirrors ``RpMaterialListStreamRead``
    (RenderWare ``world/bamatlst.c``). Returns the per-slot material list."""
    matlist_end = r.pos + matlist_size
    materials = []

    _mct, _mcs, _mcl = _read_chunk_header(r)          # inner STRUCT
    mat_count = r.read_one('<I')
    indices = [r.read_one('<i') for _ in range(mat_count)]

    for idx in indices:
        if idx < 0:
            ct, cs, cl = _read_chunk_header(r)
            if ct == CHUNK_MATERIAL:
                materials.append(_read_material_chunk(r, cs, rw_version))
            else:
                # Malformed (a non-material chunk where one was promised) —
                # keep slot alignment so triangle material indices stay valid.
                r.skip(cs)
                materials.append(DffMaterial())
        else:
            # Reuse an earlier slot's material (same object, as RW shares the
            # pointer). Guard the index in case of a corrupt file.
            materials.append(materials[idx]
                             if 0 <= idx < len(materials) else DffMaterial())

    r.seek(matlist_end)
    return materials


def _read_matfx_plugin(r: BinaryReader, size: int, mat: DffMaterial):
    """Read Material Effects PLG content."""
    start = r.pos
    end = start + size
    effect_type = r.read_one('<I')

    if effect_type in (1, 3):
        # Bump map
        marker = r.read_one('<I')
        if marker == 1:
            intensity = r.read_one('<f')
            has_bump_tex = r.read_one('<I')
            bump_tex = None
            if has_bump_tex and r.pos < end:
                ct, cs, cl = _read_chunk_header(r)
                if ct == CHUNK_TEXTURE:
                    bump_tex = _read_texture_chunk(r, cs)
                else:
                    r.skip(cs)
            has_height = r.read_one('<I') if r.pos < end else 0
            height_tex = None
            if has_height and r.pos < end:
                ct, cs, cl = _read_chunk_header(r)
                if ct == CHUNK_TEXTURE:
                    height_tex = _read_texture_chunk(r, cs)
                else:
                    r.skip(cs)
            mat.bump_map = BumpMapEffect(intensity=intensity, bump_texture=bump_tex, height_texture=height_tex)

    if effect_type in (2, 3):
        # Env map
        if r.pos < end:
            marker = r.read_one('<I')
            if marker == 2:
                coeff = r.read_one('<f')
                use_fb = bool(r.read_one('<I'))
                has_tex = r.read_one('<I') if r.pos < end else 0
                env_tex = None
                if has_tex and r.pos < end:
                    ct, cs, cl = _read_chunk_header(r)
                    if ct == CHUNK_TEXTURE:
                        env_tex = _read_texture_chunk(r, cs)
                    else:
                        r.skip(cs)
                mat.env_map = EnvMapEffect(coefficient=coeff, use_fb_alpha=use_fb, texture=env_tex)

    if effect_type == 4:
        # Dual Texture
        if r.pos < end:
            marker = r.read_one('<I')
            if marker == 4:
                src_blend = r.read_one('<I')
                dst_blend = r.read_one('<I')
                has_tex = r.read_one('<I') if r.pos < end else 0
                dual_tex = None
                if has_tex and r.pos < end:
                    ct, cs, cl = _read_chunk_header(r)
                    if ct == CHUNK_TEXTURE:
                        dual_tex = _read_texture_chunk(r, cs)
                    else:
                        r.skip(cs)
                mat.dual_texture = DualTextureEffect(
                    src_blend=src_blend, dst_blend=dst_blend, texture=dual_tex)

    r.seek(end)


def _read_geometry_chunk(r: BinaryReader, size: int, rw_version: int) -> DffGeometry:
    """Read a Geometry chunk.  *rw_version* comes from the parent Geometry List."""
    end = r.pos + size
    geom = DffGeometry()

    # ── Struct ──
    ct, cs, cl = _read_chunk_header(r)
    struct_end = r.pos + cs

    flags, num_tris, num_verts, morph_count = r.read('<IIII')
    geom._import_flags = flags  # store original flags for round-trip
    geom.original_flags = flags  # full flag word, exposed for importer round-trip
    geom.export_normals = bool(flags & GEOM_NORMALS)
    geom.export_light = bool(flags & GEOM_LIGHT)
    geom.export_mod_color = bool(flags & GEOM_MOD_COLOR)

    # Old RW versions store surface properties inline
    if rw_version < 0x34000:
        r.skip(12)  # ambient, specular, diffuse

    # Native geometry — data is in platform-specific extension, not here
    is_native = bool(flags & GEOM_NATIVE)

    # UV layer count from upper byte of flags
    num_uv = (flags >> 16) & 0xFF
    if num_uv == 0:
        if flags & GEOM_TEXTURED2:
            num_uv = 2
        elif flags & GEOM_TEXTURED:
            num_uv = 1

    if not is_native:
        # Prelit colors (4 bytes per vertex: RGBA) — numpy bulk read
        if flags & GEOM_PRELIT and num_verts > 0:
            arr = np.frombuffer(r.data, dtype=np.uint8,
                                count=num_verts * 4, offset=r.pos).reshape(num_verts, 4)
            r.skip(num_verts * 4)
            geom.prelit_colors = [RGBA(r_, g_, b_, a_) for r_, g_, b_, a_ in arr.tolist()]

        # UV layers (8 bytes per vertex per layer: u, v as float32)
        for _ in range(num_uv):
            if num_verts > 0:
                arr = np.frombuffer(r.data, dtype='<f4',
                                    count=num_verts * 2, offset=r.pos).reshape(num_verts, 2)
                r.skip(num_verts * 8)
                geom.uv_layers.append([TexCoords(u, v) for u, v in arr.tolist()])
            else:
                geom.uv_layers.append([])

        # Triangles (8 bytes each: b, a, material, c as uint16)
        if num_tris > 0:
            arr = np.frombuffer(r.data, dtype='<u2',
                                count=num_tris * 4, offset=r.pos).reshape(num_tris, 4)
            r.skip(num_tris * 8)
            # File order is (b, a, material, c) — remap into Triangle's ABC layout.
            geom.triangles = [Triangle(a=a, b=b, c=c, material=m)
                              for b, a, m, c in arr.tolist()]

    # ── Morph targets ──
    for _morph in range(morph_count):
        geom.bounding_sphere = BoundingSphere(*r.read('<4f'))
        has_pos, has_norms = r.read('<II')

        if has_pos and num_verts > 0:
            arr = np.frombuffer(r.data, dtype='<f4',
                                count=num_verts * 3, offset=r.pos).reshape(num_verts, 3)
            r.skip(num_verts * 12)
            # extend, not assign — DFFs with morph_count > 1 append per morph.
            # .tolist() yields list of [x, y, z] lists — indexable like the
            # old tuples so downstream `v[0], v[1], v[2]` access is unchanged.
            geom.vertices.extend(arr.tolist())

        if has_norms and num_verts > 0:
            arr = np.frombuffer(r.data, dtype='<f4',
                                count=num_verts * 3, offset=r.pos).reshape(num_verts, 3)
            r.skip(num_verts * 12)
            geom.normals.extend(arr.tolist())

    r.seek(struct_end)

    # ── Material list (honors RW reuse-index array; see _read_material_list) ──
    ct, cs, cl = _read_chunk_header(r)
    if ct == CHUNK_MATERIAL_LIST:
        geom.materials = _read_material_list(r, cs, rw_version)

    # ── Extension ──
    if r.pos < end:
        ct, cs, cl = _read_chunk_header(r)
        if ct == CHUNK_EXTENSION:
            ext_end = r.pos + cs
            while r.pos < ext_end:
                ect, ecs, ecl = _read_chunk_header(r)
                plugin_end = r.pos + ecs
                if ect == CHUNK_BIN_MESH_PLG:
                    _read_bin_mesh_plg(r, ecs, geom)
                elif ect == CHUNK_NATIVE_DATA_PLG:
                    # Mobile DFF (or PS2/Xbox native) — geometry data
                    # lives here, not in the main Struct. We only
                    # handle OGL/War Drum; other platforms are no-op.
                    _read_native_data_plg(r, ecs, geom, num_verts)
                elif ect == CHUNK_SKIN_PLG:
                    if geom.is_native_ogl:
                        # Mobile SKIN_PLG = NativeOGLSkin (matrices only;
                        # weights/indices live in WDGL buffer we already
                        # parsed). Different reader, different layout.
                        geom.skin = _read_native_skin_plg(r, ecs, geom)
                    else:
                        geom.skin = _read_skin_plugin(r, ecs, len(geom.vertices))
                elif ect == CHUNK_EXTRA_COLORS:
                    # Night Vertex Colors PLG:
                    #   magic u32 — 0 means "no night colors, chunk is only
                    #     the magic word". Non-zero → nv × RGBA follow.
                    # Some vanilla DFFs also trim the chunk short (fewer
                    # colors than verts) or the chunk size doesn't match
                    # `len(geom.vertices)*4` — we clamp to what's actually
                    # in the chunk instead of reading past the buffer.
                    _magic = r.read_one('<I')
                    ec = ExtraVertColors()
                    _nv = len(geom.vertices)
                    available = ecs - 4  # bytes left in this chunk after magic
                    # Cap nv to what the chunk can actually carry (4 B per colour).
                    safe_nv = min(_nv, available // 4) if _nv > 0 else 0
                    if _magic != 0 and safe_nv > 0:
                        _arr = np.frombuffer(r.data, dtype=np.uint8,
                                             count=safe_nv * 4, offset=r.pos).reshape(safe_nv, 4)
                        r.skip(safe_nv * 4)
                        ec.colors = [RGBA(r_, g_, b_, a_) for r_, g_, b_, a_ in _arr.tolist()]
                    geom.extra_colors = ec
                elif ect == CHUNK_PIPELINE_SET:
                    geom.pipeline = r.read_one('<I')
                elif ect == CHUNK_USERDATA_PLG:
                    geom.user_data = _read_userdata_plugin(r, ecs)
                elif ect == CHUNK_2DFXPLG:
                    geom.ext_2dfx = _read_2dfx_plugin(r, ecs)
                elif ect == CHUNK_BREAKABLE:
                    # W1: the full mesh copy the engine parses; the 4-byte
                    # "not breakable" marker (magic 0) leaves it None.
                    geom.breakable = _read_breakable_plugin(r, ecs)
                else:
                    pass
                r.seek(plugin_end)

    r.seek(end)
    return geom


def _read_userdata_plugin(r: BinaryReader, size: int) -> UserData:
    """Read User Data PLG."""
    start = r.pos
    ud = UserData()
    num_sections = r.read_one('<I')

    for _ in range(num_sections):
        sec = UserDataSection()
        # Name
        name_len = r.read_one('<I')
        if name_len > 0:
            sec.name = r.read_bytes(name_len).decode('ascii', errors='replace')
        # Type and count
        sec.data_type, num_elements = r.read('<II')
        sec.data = []

        if sec.data_type == USERDATA_INT:
            for _ in range(num_elements):
                sec.data.append(r.read_one('<I'))
        elif sec.data_type == USERDATA_FLOAT:
            for _ in range(num_elements):
                sec.data.append(r.read_one('<f'))
        elif sec.data_type == USERDATA_STRING:
            for _ in range(num_elements):
                str_len = r.read_one('<I')
                sec.data.append(r.read_bytes(str_len).decode('ascii', errors='replace'))

        ud.sections.append(sec)

    r.seek(start + size)
    return ud


def _wdgl_unpack_attrib(data: bytes, offset: int, attrib_type: int,
                        comp_size: int, is_normalized: bool):
    """Unpack one attribute value from War Drum OpenGL interleaved buffer.

    Mirrors DragonFF's reference implementation. Normalisation divisors
    follow DragonFF (USHORT uses 65435.0 — that matches War Drum runtime
    even though it looks like a typo of 65535, keep it for parity).
    """
    if attrib_type == WDGL_TYPE_FLOAT:
        return unpack_from('<%df' % comp_size, data, offset)
    if attrib_type == WDGL_TYPE_BYTE:
        vals = unpack_from('<%db' % comp_size, data, offset)
        if is_normalized:
            return tuple(v / 127.0 for v in vals)
        return vals
    if attrib_type == WDGL_TYPE_UBYTE:
        vals = unpack_from('<%dB' % comp_size, data, offset)
        if is_normalized:
            return tuple(v / 255.0 for v in vals)
        return vals
    if attrib_type == WDGL_TYPE_SHORT:
        vals = unpack_from('<%dh' % comp_size, data, offset)
        if is_normalized:
            return tuple(v / 32767.0 for v in vals)
        return vals
    if attrib_type == WDGL_TYPE_USHORT:
        vals = unpack_from('<%dH' % comp_size, data, offset)
        if is_normalized:
            return tuple(v / 65435.0 for v in vals)
        return vals
    raise ValueError(f"Unknown WDGL attrib type: {attrib_type}")


def _read_wdgl_geometry(r: BinaryReader, size: int, geom: 'DffGeometry',
                        num_verts: int):
    """Parse War Drum OpenGL native vertex block (mobile DFF).

    Layout (after the platform u32 already consumed by the caller):
        u32 numAttribs
        numAttribs × 24-byte descriptor (id, type, normalized, size, stride, offset)
        <interleaved vertex buffer>

    Each descriptor describes one attribute (position / uv / normal /
    color / weights / bone indices / extra color) and its byte offset
    inside the interleaved buffer. We iterate per-vertex per-attribute
    using descriptor.offset + i*descriptor.stride.
    """
    block_start = r.pos
    block_end = block_start + size

    if size < 4:
        r.seek(block_end)
        return

    num_attribs = r.read_one('<I')
    if num_attribs <= 0 or num_attribs > 8:
        # Out-of-range descriptor count — likely a non-OGL native data
        # variant or a corrupt chunk. Bail without trashing the geom.
        r.seek(block_end)
        return

    descs = []
    for _ in range(num_attribs):
        # <I i I i I I> matches DragonFF; signed fields keep War Drum's
        # original layout where 'type' and 'size' were declared as int32.
        aid, atype, normalized, comp_size, stride, voff = r.read('<IiIiII')
        descs.append((aid, atype, bool(normalized), comp_size, stride, voff))

    # All descriptor offsets are relative to the byte after the
    # descriptor array — i.e. the start of the interleaved buffer.
    attribs_base = r.pos

    coords = []
    uvs = []
    normals = []
    prelits = []
    extras = []
    bone_weights = []
    bone_indices = []

    data = r.data
    for (aid, atype, norm, csize, stride, voff) in descs:
        cursor = attribs_base + voff
        for _ in range(num_verts):
            vals = _wdgl_unpack_attrib(data, cursor, atype, csize, norm)
            if aid == WDGL_ATTRIB_COORD:
                coords.append([vals[0], vals[1], vals[2]])
            elif aid == WDGL_ATTRIB_TEX_COORD:
                # War Drum UVs come pre-scaled by 512 (fits in short).
                # Divide back to get standard 0..1 range.
                uvs.append(TexCoords(vals[0] / 512.0, vals[1] / 512.0))
            elif aid == WDGL_ATTRIB_NORMAL:
                normals.append([vals[0], vals[1], vals[2]])
            elif aid == WDGL_ATTRIB_PRELIT:
                r_, g_, b_, a_ = (int(v * 255.0) for v in vals)
                prelits.append(RGBA(r_, g_, b_, a_))
            elif aid == WDGL_ATTRIB_EXTRA_COLOR:
                r_, g_, b_, a_ = (int(v * 255.0) for v in vals)
                extras.append(RGBA(r_, g_, b_, a_))
            elif aid == WDGL_ATTRIB_BONE_WEIGHT:
                bone_weights.append(tuple(vals))
            elif aid == WDGL_ATTRIB_BONE_INDEX:
                bone_indices.append(tuple(int(v) for v in vals))
            cursor += stride

    if coords:
        geom.vertices = coords
    if uvs:
        geom.uv_layers = [uvs]
    if normals:
        geom.normals = normals
    if prelits:
        geom.prelit_colors = prelits
    if extras:
        ec = ExtraVertColors()
        ec.colors = extras
        geom.extra_colors = ec
    if bone_weights:
        geom._wdgl_bone_weights = bone_weights
    if bone_indices:
        geom._wdgl_bone_indices = bone_indices

    r.seek(block_end)


def _read_native_skin_plg(r: BinaryReader, size: int,
                          geom: 'DffGeometry') -> Optional['SkinData']:
    """Read SKIN_PLG for mobile (Native OGL) geometry.

    Mobile DFFs put per-vertex weights/indices inside the WDGL buffer
    of Native Data PLG, so the SKIN_PLG carries only header + bone
    matrices (NativeOGLSkin format):
        u32 num_bones
        num_bones × 16f matrix (4×4 column-major; last column zeroed
        and [15]=1 enforced for affine sanity)

    We pair the matrices with the bone weights/indices we cached in
    geom._wdgl_bone_weights / _wdgl_bone_indices during Native Data PLG
    read, and produce a regular SkinData so the rest of the pipeline
    (skin builder, write_skin) sees a uniform object.
    """
    start = r.pos
    skin = SkinData()

    skin.num_bones = r.read_one('<I')
    for _ in range(skin.num_bones):
        raw = list(r.read('<16f'))
        raw[3] = 0.0
        raw[7] = 0.0
        raw[11] = 0.0
        raw[15] = 1.0
        skin.bone_matrices.append([raw[0:4], raw[4:8], raw[8:12], raw[12:16]])

    # Stitch in per-vertex data that WDGL parsed earlier.
    bw = getattr(geom, '_wdgl_bone_weights', None) or []
    bi = getattr(geom, '_wdgl_bone_indices', None) or []
    if bw:
        skin.bone_weights = list(bw)
    if bi:
        skin.bone_indices = list(bi)

    # max_weights = highest non-zero weight count per vertex
    if skin.bone_weights:
        mw = 0
        for vw in skin.bone_weights:
            nz = sum(1 for x in vw if x > 0.0)
            if nz > mw:
                mw = nz
        skin.max_weights = mw
    skin.num_used = 0  # mobile skins ship without the bones_used list

    r.seek(start + size)
    return skin


def _read_native_data_plg(r: BinaryReader, size: int, geom: 'DffGeometry',
                          num_verts: int):
    """Read Native Data PLG (chunk 0x510).

    Mobile DFFs store geometry inside this plugin instead of the main
    Geometry Struct. The PLG itself wraps a single Struct that carries
    the platform ID followed by platform-native data. For OpenGL/War
    Drum (mobile) we dispatch to _read_wdgl_geometry; for other native
    platforms (PS2/Xbox/PSP/GC) we capture the entire chunk verbatim so
    the writer can round-trip the file without losing data we can't
    interpret yet.
    """
    # Chunk header was consumed by the caller (12 B before r.pos).
    chunk_header_start = r.pos - 12
    chunk_end_abs = chunk_header_start + 12 + size
    end = r.pos + size

    ct, cs, cl = _read_chunk_header(r)
    if ct != CHUNK_STRUCT:
        r.seek(end)
        return
    struct_end = r.pos + cs

    if cs < 4:
        r.seek(end)
        return

    platform = r.read_one('<I')
    if platform == NATIVE_PLATFORM_OGL:
        geom.is_native_ogl = True
        _read_wdgl_geometry(r, struct_end - r.pos, geom, num_verts)
    else:
        # Round-trip: capture the chunk bytes (header + body) so the
        # writer can emit them unchanged. Decoding PS2/Xbox/PSP/GC is
        # out of scope for now.
        geom.raw_native_data_plg = bytes(r.data[chunk_header_start:chunk_end_abs])
        geom.is_native_other_platform = platform

    r.seek(end)


def _read_bin_mesh_plg(r: BinaryReader, size: int, geom: 'DffGeometry'):
    """Read Binary Mesh PLG.

    For PC DFFs the main Geometry Struct already carries triangles
    (with material indices), and BIN_MESH_PLG just *re-assigns* the
    material via vertex-tuple lookup. For mobile DFFs (Native Data PLG)
    the Struct has no triangles at all — BIN_MESH_PLG IS the triangle
    list and we have to build geom.triangles from scratch.
    """
    # Capture position BEFORE reading anything — `r.seek(start + size)`
    # at the bottom of this function uses it to advance past any padding
    # the source DFF left after the indices. An autofixer once removed
    # this line as "unused" because the use site is far below; that
    # broke every DFF import. Don't re-trigger it: the variable IS used.
    start = r.pos
    flags = r.read_one('<I')       # 0 = trilist, 1 = tristrip
    num_splits = r.read_one('<I')
    r.read_one('<I')               # total_indices (unused)

    build_mode = (len(geom.triangles) == 0)

    # Build vertex→triangle lookup for material assignment (PC path).
    # In build_mode we skip this — geom.triangles is empty.
    tri_lookup = {}
    if not build_mode:
        for ti, tri in enumerate(geom.triangles):
            key = tuple(sorted((tri.a, tri.b, tri.c)))
            tri_lookup[key] = ti

    for _ in range(num_splits):
        num_indices = r.read_one('<I')
        mat_idx = r.read_one('<I')

        if flags == 0:
            # Triangle list: every 3 indices = one triangle — bulk read via numpy
            n_tris = num_indices // 3
            if n_tris > 0:
                tri_arr = np.frombuffer(r.data, dtype='<u4',
                                        count=n_tris * 3, offset=r.pos).reshape(n_tris, 3)
                r.skip(n_tris * 12)
                if build_mode:
                    for i0, i1, i2 in tri_arr.tolist():
                        geom.triangles.append(
                            Triangle(a=i0, b=i1, c=i2, material=mat_idx))
                else:
                    for i0, i1, i2 in tri_arr.tolist():
                        key = tuple(sorted((i0, i1, i2)))
                        ti = tri_lookup.get(key)
                        if ti is not None:
                            geom.triangles[ti].material = mat_idx
        else:
            # Triangle strip: read all indices at once, then walk in Python.
            if num_indices > 0:
                indices = np.frombuffer(r.data, dtype='<u4',
                                        count=num_indices, offset=r.pos).tolist()
                r.skip(num_indices * 4)
            else:
                indices = []
            for j in range(len(indices) - 2):
                if j % 2 == 0:
                    i0, i1, i2 = indices[j], indices[j+1], indices[j+2]
                else:
                    i0, i1, i2 = indices[j], indices[j+2], indices[j+1]
                if i0 == i1 or i1 == i2 or i0 == i2:
                    continue  # degenerate
                if build_mode:
                    geom.triangles.append(
                        Triangle(a=i0, b=i1, c=i2, material=mat_idx))
                else:
                    key = tuple(sorted((i0, i1, i2)))
                    ti = tri_lookup.get(key)
                    if ti is not None:
                        geom.triangles[ti].material = mat_idx

    r.seek(start + size)


def _read_skin_plugin(r: BinaryReader, size: int, num_verts: int) -> SkinData:
    """Read Skin PLG (matching DragonFF format)."""
    skin = SkinData()

    # Header: num_bones, num_used_bones, max_weights_per_vertex, padding
    skin.num_bones, skin.num_used, skin.max_weights = r.read('<3B')
    r.skip(1)  # padding byte

    # Read bones_used array
    oldver = (skin.num_used == 0)
    if skin.num_used > 0:
        for _ in range(skin.num_used):
            skin.bones_used.append(r.read_one('<B'))

    # Vertex bone indices (4 bytes per vertex) — bulk read via numpy
    if num_verts > 0:
        _bi = np.frombuffer(r.data, dtype=np.uint8,
                            count=num_verts * 4, offset=r.pos).reshape(num_verts, 4)
        r.skip(num_verts * 4)
        skin.bone_indices = [tuple(row) for row in _bi.tolist()]

    # Vertex bone weights (4 floats per vertex)
    if num_verts > 0:
        _bw = np.frombuffer(r.data, dtype='<f4',
                            count=num_verts * 4, offset=r.pos).reshape(num_verts, 4)
        r.skip(num_verts * 16)
        skin.bone_weights = [tuple(row) for row in _bw.tolist()]

    # Bone matrices (inverse bind pose)
    for _ in range(skin.num_bones):
        if oldver:
            r.skip(4)  # 0xDEADDEAD marker in old format
        raw = list(r.read('<16f'))
        # Clear last column, set [15]=1 (proper affine matrix)
        raw[3] = 0.0
        raw[7] = 0.0
        raw[11] = 0.0
        raw[15] = 1.0
        skin.bone_matrices.append([raw[0:4], raw[4:8], raw[8:12], raw[12:16]])

    return skin


# 24-byte 2DFX name fields (corona / shadow texture, particle system):
# 23 chars + terminating NUL.
EFFECT_NAME_MAX = 23


def _cut_2dfx_name(name: str, what: str) -> str:
    """Truncate a 24-byte-slot 2DFX name to 23 chars, warning once per
    export (W13) — consistent with the rest of the exporter, which cuts
    fixed-width strings instead of refusing."""
    if len(name.encode('ascii', errors='replace')) > EFFECT_NAME_MAX:
        cut = name[:EFFECT_NAME_MAX]
        _w = _t(
            "2DFX: имя {0} «{1}» длиннее {2} символов — обрезано до «{3}» (24-байтовое поле с NUL)."
        ).format(what, name, EFFECT_NAME_MAX, cut)
        DFF_EXPORT_WARNINGS.append(_w)
        print(f"[DFF Export WARNING] {_w}")
        return cut
    return name


def _write_2dfx_entry(entry) -> bytes:
    """Serialize a single 2DFX effect entry payload (without header)."""
    if isinstance(entry, Light2dfx):
        data = pack('<4B', entry.color.r, entry.color.g, entry.color.b, entry.color.a)
        data += pack('<ffffBBBBB',
                     entry.corona_far_clip, entry.pointlight_range,
                     entry.corona_size, entry.shadow_size,
                     entry.corona_show_mode, entry.corona_enable_reflection,
                     entry.corona_flare_type, entry.shadow_color_multiplier,
                     entry.flags1)
        # Corona and shadow texture names — 24-byte C strings, so at most
        # 23 chars + NUL (W13); longer names are cut with a warning.
        data += _fixed_cstr(_cut_2dfx_name(entry.corona_tex_name, 'corona'), 24)
        data += _fixed_cstr(_cut_2dfx_name(entry.shadow_tex_name, 'shadow'), 24)
        data += pack('<BB', entry.shadow_z_distance, entry.flags2)
        # Always write 80-byte variant (Kam's / GTA SA standard)
        if entry.look_direction is not None:
            data += pack('<BBB2x', *entry.look_direction)
        else:
            data += b'\x00' * 5  # 3 bytes look_dir + 2 padding = 80 bytes total
        return data

    elif isinstance(entry, Particle2dfx):
        # The engine copies the name until NUL (unbounded), so the NUL
        # must sit inside the 24-byte field (W13).
        return _fixed_cstr(_cut_2dfx_name(entry.effect_name, 'particle'), 24)

    elif isinstance(entry, PedAttractor2dfx):
        data = pack('<I', entry.attractor_type)
        data += pack('<9f', *entry.rotation_matrix)
        script = entry.external_script.encode('ascii', errors='replace')[:8]
        data += script + b'\x00' * (8 - len(script))
        data += pack('<I', entry.ped_existing_probability)
        # W2: bytes 52..55 — without them the entry is 52 bytes and the
        # engine drops it (size must be 0x38).
        data += pack('<BxBx', entry.flags & 0xFF, entry.unknown & 0xFF)
        return data   # 56 bytes

    elif isinstance(entry, SunGlare2dfx):
        return b''

    elif isinstance(entry, EnterExit2dfx):
        data = pack('<3f', entry.enter_angle,
                    entry.approximation_radius_x, entry.approximation_radius_y)
        data += pack('<3f', *entry.exit_loc)
        data += pack('<f', entry.exit_angle)
        data += pack('<H', entry.interior & 0xFFFF)
        data += pack('<BB', entry.flags1 & 0xFF, entry.sky_color & 0xFF)
        name = entry.interior_name.encode('ascii', errors='replace')[:8]
        data += name + b'\x00' * (8 - len(name))
        data += pack('<4B', entry.time_on & 0xFF, entry.time_off & 0xFF,
                     entry.flags2 & 0xFF, entry.unknown & 0xFF)
        return data   # 44 bytes

    elif isinstance(entry, RoadSign2dfx):
        data = pack('<2f', entry.size[0], entry.size[1])
        data += pack('<3f', *entry.rotation)
        data += pack('<H', entry.flags & 0xFFFF)
        lines = list(entry.text_lines) + ["", "", "", ""]
        for line in lines[:4]:
            b = line.encode('ascii', errors='replace')[:16]
            data += b + b'\x00' * (16 - len(b))
        data += b'\x00\x00'   # 2 pad bytes
        return data   # 88 bytes

    elif isinstance(entry, Escalator2dfx):
        data = pack('<3f', *entry.bottom)
        data += pack('<3f', *entry.top)
        data += pack('<3f', *entry.end)
        data += pack('<I', entry.direction & 0xFFFFFFFF)
        return data   # 40 bytes

    elif isinstance(entry, RawUnknown2dfx):
        return entry.raw

    return b''


def _read_2dfx_plugin(r: BinaryReader, size: int) -> Extension2dfx:
    """Read 2DFX Plugin (lights, particles, ped attractors, sun glare)."""
    start = r.pos
    ext = Extension2dfx()
    entries_count = r.read_one('<I')

    for _ in range(entries_count):
        loc = r.read('<3f')
        entry_type, entry_size = r.read('<II')
        entry_start = r.pos

        if entry_type == 0:  # Light
            light = Light2dfx(loc=loc)
            light.color = RGBA(*r.read('<4B'))
            (light.corona_far_clip, light.pointlight_range,
             light.corona_size, light.shadow_size,
             light.corona_show_mode, light.corona_enable_reflection,
             light.corona_flare_type, light.shadow_color_multiplier,
             light.flags1) = r.read('<ffffBBBBB')

            corona_raw = r.read_bytes(24)
            shadow_raw = r.read_bytes(24)
            end_c = corona_raw.find(b'\x00')
            end_s = shadow_raw.find(b'\x00')
            light.corona_tex_name = corona_raw[:end_c if end_c >= 0 else 24].decode('ascii', errors='replace')
            light.shadow_tex_name = shadow_raw[:end_s if end_s >= 0 else 24].decode('ascii', errors='replace')

            light.shadow_z_distance, light.flags2 = r.read('<BB')

            # 80-byte variant has look_direction
            if entry_size > 76:
                light.look_direction = r.read('<3B')

            ext.entries.append(light)

        elif entry_type == 1:  # Particle
            particle = Particle2dfx(loc=loc)
            raw = r.read_bytes(min(24, entry_size))
            end_p = raw.find(b'\x00')
            particle.effect_name = raw[:end_p if end_p >= 0 else len(raw)].decode('ascii', errors='replace')
            ext.entries.append(particle)

        elif entry_type == 3:  # Ped Attractor
            ped = PedAttractor2dfx(loc=loc)
            ped.attractor_type = r.read_one('<I')
            ped.rotation_matrix = r.read('<9f')
            script_raw = r.read_bytes(8)
            end_e = script_raw.find(b'\x00')
            ped.external_script = script_raw[:end_e if end_e >= 0 else 8].decode('ascii', errors='replace')
            ped.ped_existing_probability = r.read_one('<I')
            if entry_size >= 56:
                # W2: keep bytes 52 and 54 (the engine stores both).
                ped.flags, ped.unknown = r.read('<BxBx')
            ext.entries.append(ped)

        elif entry_type == 4:  # Sun Glare
            ext.entries.append(SunGlare2dfx(loc=loc))

        elif entry_type == 6:  # Enter/Exit
            ee = EnterExit2dfx(loc=loc)
            (ee.enter_angle, ee.approximation_radius_x,
             ee.approximation_radius_y) = r.read('<3f')
            ee.exit_loc = r.read('<3f')
            ee.exit_angle = r.read_one('<f')
            ee.interior = r.read_one('<H')
            ee.flags1, ee.sky_color = r.read('<BB')
            nm = r.read_bytes(8)
            end_n = nm.find(b'\x00')
            ee.interior_name = nm[:end_n if end_n >= 0 else 8].decode('ascii', errors='replace')
            ee.time_on, ee.time_off, ee.flags2, ee.unknown = r.read('<4B')
            ext.entries.append(ee)

        elif entry_type == 7:  # Road / street sign
            rs = RoadSign2dfx(loc=loc)
            rs.size = r.read('<2f')
            rs.rotation = r.read('<3f')
            rs.flags = r.read_one('<H')
            lines = []
            for _ in range(4):
                raw = r.read_bytes(16)
                end_l = raw.find(b'\x00')
                lines.append(raw[:end_l if end_l >= 0 else 16].decode('ascii', errors='replace'))
            rs.text_lines = lines
            ext.entries.append(rs)

        elif entry_type == 10:  # Escalator
            es = Escalator2dfx(loc=loc)
            es.bottom = r.read('<3f')
            es.top = r.read('<3f')
            es.end = r.read('<3f')
            es.direction = r.read_one('<I')
            ext.entries.append(es)

        else:
            # Types we don't decode (2/5 interior, 8 trigger, 9 cover, …):
            # keep the payload verbatim so re-export doesn't drop them.
            raw = r.read_bytes(entry_size)
            ext.entries.append(RawUnknown2dfx(effect_id=entry_type, loc=loc, raw=raw))

        r.seek(entry_start + entry_size)

    r.seek(start + size)
    return ext


def _read_frame_list(r: BinaryReader, size: int) -> list:
    """Read Frame List chunk. Returns list of DffFrame."""
    end = r.pos + size
    # Save raw bytes for round-trip export
    start_pos = r.pos
    r.seek(end)
    raw_bytes = r.data[start_pos:end]
    r.seek(start_pos)

    frames = []

    # Struct
    ct, cs, cl = _read_chunk_header(r)
    struct_end = r.pos + cs
    frame_count = r.read_one('<I')

    for _ in range(frame_count):
        rotation = r.read('<9f')
        position = r.read('<3f')
        parent, flags = r.read('<iI')
        frames.append(DffFrame(
            rotation=rotation,
            position=position,
            parent=parent,
            flags=flags,
        ))

    r.seek(struct_end)

    # Frame extensions (one per frame)
    for i in range(frame_count):
        if r.pos >= end:
            break
        ct, cs, cl = _read_chunk_header(r)
        if ct == CHUNK_EXTENSION:
            ext_end = r.pos + cs
            while r.pos < ext_end:
                ect, ecs, ecl = _read_chunk_header(r)
                plugin_end = r.pos + ecs
                if ect == CHUNK_FRAME_NAME:
                    raw = r.read_bytes(ecs)
                    nm_end = raw.find(b'\x00')
                    if nm_end == -1:
                        nm_end = len(raw)
                    frames[i].name = raw[:nm_end].decode('ascii', errors='replace')
                    frames[i].write_name = True
                elif ect == CHUNK_HANIM_PLG:
                    frames[i].hanim = _read_hanim_plugin(r, ecs)
                elif ect == CHUNK_USERDATA_PLG:
                    frames[i].user_data = _read_userdata_plugin(r, ecs)
                else:
                    pass
                r.seek(plugin_end)
            r.seek(ext_end)
        else:
            r.skip(cs)

    r.seek(end)
    # Attach raw bytes for round-trip
    for f in frames:
        f._raw_frame_list = raw_bytes
    return frames


def _read_hanim_plugin(r: BinaryReader, size: int) -> HAnimData:
    """Read HAnim PLG."""
    start = r.pos
    hanim = HAnimData()
    hanim.version, hanim.bone_id, bone_count = r.read('<3i')
    if bone_count > 0:
        hanim.flags, hanim.keyframe_size = r.read('<II')
        for _ in range(bone_count):
            bid, idx, btype = r.read('<3i')
            hanim.bones.append(HAnimBone(bone_id=bid, index=idx, bone_type=btype))
    r.seek(start + size)
    return hanim


def read_dff(data: bytes) -> DffClump:
    """
    Parse DFF binary data into a DffClump.
    Returns a DffClump with frames, geometries, and atomics.
    """
    r = BinaryReader(data)
    clump = DffClump()

    # Vanilla SA ships some DFFs (chinafurn1.dff, casinoblock2_nt.dff,
    # aptcanopynit_lvs01.dff, ...) where Clump (0x10) is preceded by
    # other top-level RW chunks — most commonly UV Animation Dictionary
    # (0x2B). The game's RW loader walks chunks linearly and processes
    # whichever one it finds. We do the same: any non-Clump chunks
    # before Clump are kept verbatim as raw bytes so write_dff() can
    # emit them again on export (round-trip preservation).
    pre_clump_start = r.pos
    while True:
        snap = r.pos
        ct, cs, cl = _read_chunk_header(r)
        if ct == CHUNK_CLUMP:
            break
        # Sanity: refuse to follow a wildly out-of-range chunk header
        # rather than skip past EOF on a truly broken file.
        if cs > len(data) - r.pos:
            r.seek(snap)
            raise ValueError(f"Expected Clump chunk (0x10), got 0x{ct:X}")
        # Vanilla layout: the UV-anim dictionary (0x2B) sits at root, BEFORE
        # the clump. Parse it into the clump so re-import exposes the
        # animations as objects (driving the UV-anim preview, not just raw
        # bytes). write_dff strips this raw copy from pre_clump_data and
        # re-emits it from clump.uv_anim_dict — so there's no duplication.
        if ct == CHUNK_UV_ANIM_DICT:
            try:
                clump.uv_anim_dict = _read_uv_anim_dict(data, r.pos, cs)
            except Exception:
                pass
        r.skip(cs)
        if r.pos >= len(data):
            r.seek(snap)
            raise ValueError(f"Expected Clump chunk (0x10), got 0x{ct:X}")
    if r.pos > pre_clump_start + 12:
        # We consumed at least one full pre-Clump chunk. Store its raw
        # bytes (header + body) for re-emission on export. r.pos is
        # currently at the start of the Clump *body*, i.e. 12 bytes
        # past the Clump header — back up to keep the slice exclusive
        # of the Clump header itself.
        clump.pre_clump_data = bytes(data[pre_clump_start:r.pos - 12])
        # Re-read the Clump header so the variables ct, cs, cl reflect
        # the Clump chunk and not whatever pre-chunk was last skipped.
        r.seek(r.pos - 12)
        ct, cs, cl = _read_chunk_header(r)

    clump.version = _decode_library_id(cl)[0]
    clump_end = r.pos + cs

    # Clump struct
    ct, cs, cl = _read_chunk_header(r)
    if ct == CHUNK_STRUCT:
        r.skip(cs)  # num_atomics + lights + cameras (unused)
    else:
        r.skip(cs)

    # Read child chunks
    while r.pos < clump_end:
        ct, cs, cl = _read_chunk_header(r)
        chunk_end = r.pos + cs

        if ct == CHUNK_FRAME_LIST:
            clump.frames = _read_frame_list(r, cs)

        elif ct == CHUNK_GEOMETRY_LIST:
            # Save raw geometry list for round-trip
            clump.raw_geometry_list = r.data[r.pos - 12:chunk_end]  # include chunk header

            # Struct: geometry count
            gct, gcs, gcl = _read_chunk_header(r)
            geom_list_ver = _decode_library_id(gcl)[0]
            geom_count = r.read_one('<I')
            r.seek(r.pos + gcs - 4)  # skip rest of struct if any extra

            for _ in range(geom_count):
                gct2, gcs2, gcl2 = _read_chunk_header(r)
                if gct2 == CHUNK_GEOMETRY:
                    # Use Geometry List version (like DragonFF's parent_chunk.version)
                    ver = geom_list_ver or clump.version
                    clump.geometries.append(_read_geometry_chunk(r, gcs2, ver))
                else:
                    r.skip(gcs2)

        elif ct == CHUNK_ATOMIC:
            # Save raw atomic for round-trip
            clump.raw_atomics += r.data[r.pos - 12:chunk_end]

            atom_end = r.pos + cs
            act, acs, acl = _read_chunk_header(r)
            if act == CHUNK_STRUCT:
                fi, gi, af, au = r.read('<IIII')
                clump.atomics.append(DffAtomic(
                    frame_index=fi,
                    geometry_index=gi,
                    flags=af,
                    unused=au,
                ))
                # Parse atomic extension — ищем Pipeline chunk (он может лежать
                # на уровне атомика, как у Kam's/Seggaeman/librwgta).
                if r.pos < atom_end:
                    ect, ecs, ecl = _read_chunk_header(r)
                    if ect == CHUNK_EXTENSION:
                        ext_end = r.pos + ecs
                        while r.pos < ext_end:
                            pct, pcs, pcl = _read_chunk_header(r)
                            plugin_end = r.pos + pcs
                            if pct == CHUNK_PIPELINE_SET and 0 <= gi < len(clump.geometries):
                                # Пишем на геометрию — у нас geom.pipeline единое поле
                                clump.geometries[gi].pipeline = r.read_one('<I')
                            r.seek(plugin_end)
            r.seek(atom_end)

        elif ct == CHUNK_EXTENSION:
            ext_end = r.pos + cs
            while r.pos < ext_end:
                ect, ecs, ecl = _read_chunk_header(r)
                if ect == CHUNK_COLLISION_MODEL:
                    clump.collision_data = r.read_bytes(ecs)
                elif ect == CHUNK_UV_ANIM_DICT:
                    # Parse the dict body off the BinaryReader's buffer
                    # without advancing the cursor mid-parse — seek back
                    # when done. _read_uv_anim_dict wants absolute
                    # offsets into the whole file.
                    body_start = r.pos
                    clump.uv_anim_dict = _read_uv_anim_dict(
                        r.data, body_start, ecs)
                    r.seek(body_start + ecs)
                else:
                    r.skip(ecs)
        else:
            r.skip(cs)

        r.seek(chunk_end)

    # Mobile DFF detection: any geometry parsed via Native Data PLG
    # (War Drum OpenGL) flips the clump's is_mobile flag. The import
    # operator reads this and switches scene.gtatools_platform=MOBILE
    # so the UI reflects what was actually loaded.
    if any(getattr(g, 'is_native_ogl', False) for g in clump.geometries):
        clump.is_mobile = True

    return clump


def read_dff_file(filepath: str) -> DffClump:
    """Read a DFF file and return a DffClump."""
    with open(filepath, 'rb') as f:
        return read_dff(f.read())
