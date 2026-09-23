"""
GTA IFP animation reader/writer.

Two on-disk formats are supported:

ANP3 (GTA SA):
  Flat int16-compressed format. Header is "ANP3" + size + pkg_name(24) +
  num_anims(uint32). Each animation: 36-byte header (name + bone_count +
  data_size + flag), followed by 36-byte bone headers (name + type +
  kf_count + bone_id), followed by per-keyframe int16 quat (×4096),
  16-bit time in 1/60 s units (×60 from seconds), and optional int16
  translation (×1024). Note: 60 units per second, not frames@30fps —
  vanilla SA anims are keyed at 30 fps, so their time values step by 2
  (e.g. ped.ifp WALK_player: 37 keys, times 0, 2, ... 72 = 1.2 s).

ANPK / ANP2 (GTA III, VC, SA-uncompressed):
  Chunked float32 format. Header is "ANPK" + size, then INFO chunk
  with num_anims + pkg_name. Each animation is NAME + DGAN, where
  DGAN contains INFO + CPAN(s). Each CPAN is ANIM (bone metadata) +
  KR00 / KRT0 / KRTS (rotation-only / rot+trans / rot+trans+scale).
  Time stored as float seconds.

Canonical in-memory unit for ``KeyFrame.time`` is **seconds**, regardless
of which format the file was loaded from. The reader normalises ANP3's
raw time by dividing by 60; the writer multiplies back. This
keeps preview / export math format-agnostic.

No Blender dependency — pure Python.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple
import struct

HAS_ROT = 1
HAS_TRANS = 2
HAS_SCALE = 4


@dataclass
class KeyFrame:
    """One keyframe for a bone."""
    rotation: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)  # XYZW quat
    translation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    time: float = 0.0


@dataclass
class AnimBone:
    """Animation data for one bone."""
    name: str = ""
    bone_id: int = -1
    key_type: int = HAS_ROT  # HAS_ROT, HAS_TRANS, HAS_SCALE flags
    keyframes: List[KeyFrame] = field(default_factory=list)


@dataclass
class Animation:
    """One animation clip."""
    name: str = ""
    bones: List[AnimBone] = field(default_factory=list)


@dataclass
class IFPFile:
    """Collection of animations from an IFP file."""
    name: str = ""  # Package name
    animations: List[Animation] = field(default_factory=list)
    # Format of the file this IFP was loaded from. ``write_ifp`` uses
    # this as the default so ``read → write`` round-trips preserve the
    # original on-disk encoding. Set by readers; ignored when building
    # an IFPFile from scratch (defaults to ANPK on write in that case).
    source_format: str = ""


def _roundsize(n: int) -> int:
    """Round up to 4-byte boundary."""
    if n & 3:
        n += 4 - (n & 3)
    return n


def _read_header(data: bytes, offset: int) -> Tuple[str, int, int]:
    """Read IFP chunk header (4-char ident + uint32 size). Returns (ident, size, new_offset)."""
    ident = data[offset:offset + 4].decode('ascii', errors='replace')
    size = struct.unpack_from('<I', data, offset + 4)[0]
    return ident, size, offset + 8


def _read_string(data: bytes, offset: int, length: int) -> str:
    """Read null-terminated string from buffer."""
    raw = data[offset:offset + length]
    null_pos = raw.find(b'\x00')
    if null_pos >= 0:
        raw = raw[:null_pos]
    return raw.decode('ascii', errors='replace')


def _read_anp3_animations(data: bytes, offset: int, num_anims: int) -> List[Animation]:
    """Parse ANP3 flat format — compressed int16 keyframes.

    Per animation:
      name(24) + numBones(4) + dataSize(4) + flag(4) = 36 bytes header
    Per bone:
      name(24) + type(4) + numKeyFrames(4) + boneId(4) = 36 bytes header
      Then keyframe data based on type:
        type 3 (rot only):    4*int16 rot + 1*uint16 time = 10 bytes per key
        type 4 (rot+trans):   4*int16 rot + 1*uint16 time + 3*int16 pos = 16 bytes per key
    Rotation: quaternion XYZW compressed as int16 / 4096.0
    Translation: XYZ compressed as int16 / 1024.0
    Time: 16-bit, 1/60 s units (convert with /60 for seconds)
    """
    animations = []

    for _a in range(num_anims):
        if offset + 36 > len(data):
            break

        try:
            anim = Animation()
            anim.name = _read_string(data, offset, 24)
            num_bones = struct.unpack_from('<I', data, offset + 24)[0]
            # offset+28: data_size (unused), offset+32: anim_flag (unused)
            offset += 36

            for _b in range(num_bones):
                if offset + 36 > len(data):
                    break

                bone = AnimBone()
                bone.name = _read_string(data, offset, 24)
                bone_type = struct.unpack_from('<I', data, offset + 24)[0]
                num_kf = struct.unpack_from('<I', data, offset + 28)[0]
                bone.bone_id = struct.unpack_from('<i', data, offset + 32)[0]
                offset += 36

                has_trans = (bone_type == 4)
                bone.key_type = (HAS_ROT | HAS_TRANS) if has_trans else HAS_ROT

                for _k in range(num_kf):
                    kf = KeyFrame()

                    # Rotation: 4 * int16, divide by 4096
                    rx, ry, rz, rw = struct.unpack_from('<4h', data, offset)
                    kf.rotation = (rx / 4096.0, ry / 4096.0, rz / 4096.0, rw / 4096.0)
                    offset += 8

                    # Time: 16-bit value in 1/60 s units (the game's
                    # compressed keyframe stores DeltaTime * 60). Normalise
                    # to seconds (canonical unit) so downstream code is
                    # format-agnostic.
                    t = struct.unpack_from('<H', data, offset)[0]
                    kf.time = float(t) / _ANP3_TIME_UNITS_PER_SEC
                    offset += 2

                    if has_trans:
                        # Translation: 3 * int16, divide by 1024
                        tx, ty, tz = struct.unpack_from('<3h', data, offset)
                        kf.translation = (tx / 1024.0, ty / 1024.0, tz / 1024.0)
                        offset += 6

                    bone.keyframes.append(kf)

                anim.bones.append(bone)

            animations.append(anim)

        except Exception as e:
            print(f"[IFP] Error at anim #{_a}: {e}")
            break

    return animations


def read_ifp(filepath: str) -> IFPFile:
    """Parse an IFP file and return structured animation data."""
    with open(filepath, 'rb') as f:
        data = f.read()

    result = IFPFile()
    offset = 0

    # Main header: ANP3 or ANLF/ANPK
    ident, size, offset = _read_header(data, offset)

    if ident == 'ANP3':
        # ANP3 format (SA) — flat compressed format (int16 keyframes)
        result.source_format = 'ANP3'
        result.name = _read_string(data, offset, 24)
        num_anims = struct.unpack_from('<I', data, offset + 24)[0]
        offset += 28
        print(f"[IFP] ANP3 package='{result.name}', anims={num_anims}")
        result.animations = _read_anp3_animations(data, offset, num_anims)
        print(f"[IFP] Parsed {len(result.animations)} animations")
        return result

    elif ident == 'ANLF':
        # ANLF container — skip to ANPK
        result.source_format = 'ANLF'
        rounded = _roundsize(size)
        # num_packages at offset (unused — caller iterates ANPK chunks)
        offset += rounded

        # Read first ANPK
        ident, size, offset = _read_header(data, offset)
        if ident != 'ANPK':
            return result

        # INFO inside ANPK
        info_ident, info_size, offset = _read_header(data, offset)
        info_rounded = _roundsize(info_size)
        num_anims = struct.unpack_from('<I', data, offset)[0]
        result.name = _read_string(data, offset + 4, 24)
        offset += info_rounded

    elif ident == 'ANPK':
        # Direct ANPK
        result.source_format = 'ANPK'
        info_ident, info_size, offset = _read_header(data, offset)
        info_rounded = _roundsize(info_size)
        num_anims = struct.unpack_from('<I', data, offset)[0]
        result.name = _read_string(data, offset + 4, 24)
        offset += info_rounded

    else:
        return result

    # Read animations
    for _a in range(num_anims):
        if offset + 8 >= len(data):
            break

        try:
            anim = Animation()

            # NAME chunk
            ch_ident, ch_size, offset = _read_header(data, offset)
            if ch_ident != 'NAME':
                print(f"[IFP] Expected NAME at {offset-8}, got '{ch_ident}', skipping rest")
                break
            ch_rounded = _roundsize(ch_size)
            anim.name = _read_string(data, offset, min(ch_size, 24))
            offset += ch_rounded

            # DGAN chunk
            ch_ident, ch_size, offset = _read_header(data, offset)
            if ch_ident != 'DGAN':
                print(f"[IFP] Expected DGAN for '{anim.name}', got '{ch_ident}', skipping")
                offset += _roundsize(ch_size)
                continue
            dgan_end = offset + _roundsize(ch_size)

            # INFO inside DGAN
            ch_ident, ch_size, offset = _read_header(data, offset)
            info_rounded = _roundsize(ch_size)
            num_bones = struct.unpack_from('<I', data, offset)[0]
            offset += info_rounded

            # Read bones (CPAN chunks)
            for _b in range(num_bones):
                if offset + 8 >= dgan_end:
                    break

                bone = AnimBone()

                # CPAN
                ch_ident, ch_size, offset = _read_header(data, offset)
                cpan_end = offset + _roundsize(ch_size)

                # ANIM inside CPAN
                ch_ident, ch_size, offset = _read_header(data, offset)
                anim_rounded = _roundsize(ch_size)
                anim_data = data[offset:offset + anim_rounded]
                offset += anim_rounded

                bone.name = _read_string(anim_data, 0, 24)
                num_kf = struct.unpack_from('<I', anim_data, 28)[0] if len(anim_data) > 28 else 0
                bone.bone_id = struct.unpack_from('<i', anim_data, 40)[0] if len(anim_data) > 40 else -1

                if num_kf == 0:
                    anim.bones.append(bone)
                    offset = cpan_end
                    continue

                # Key data chunk (KR00 / KRT0 / KRTS)
                ch_ident, ch_size, offset = _read_header(data, offset)

                if ch_ident == 'KR00':
                    bone.key_type = HAS_ROT
                elif ch_ident == 'KRT0':
                    bone.key_type = HAS_ROT | HAS_TRANS
                elif ch_ident == 'KRTS':
                    bone.key_type = HAS_ROT | HAS_TRANS | HAS_SCALE
                else:
                    # Unknown key type, skip this bone
                    anim.bones.append(bone)
                    offset = cpan_end
                    continue

                for _k in range(num_kf):
                    kf = KeyFrame()

                    if bone.key_type & HAS_ROT:
                        qx, qy, qz, qw = struct.unpack_from('<4f', data, offset)
                        kf.rotation = (-qx, -qy, -qz, qw)
                        offset += 16

                    if bone.key_type & HAS_TRANS:
                        tx, ty, tz = struct.unpack_from('<3f', data, offset)
                        kf.translation = (tx, ty, tz)
                        offset += 12

                    if bone.key_type & HAS_SCALE:
                        sx, sy, sz = struct.unpack_from('<3f', data, offset)
                        kf.scale = (sx, sy, sz)
                        offset += 12

                    t = struct.unpack_from('<f', data, offset)[0]
                    kf.time = t
                    offset += 4

                    bone.keyframes.append(kf)

                anim.bones.append(bone)
                offset = cpan_end  # Align after each bone

            offset = dgan_end  # Align after DGAN
            result.animations.append(anim)

        except Exception as e:
            print(f"[IFP] Error reading anim #{_a} '{anim.name if anim else '?'}': {e}")
            break

    print(f"[IFP] Parsed {len(result.animations)} animations")
    return result


# ANP3 keyframe time unit: 1/60 s. The game reads it as a fixed-point
# int16 with a 60.0 divisor (gta-reversed AnimSequenceFrames.h:
# KeyFrameCompressed::DeltaTime = FixedFloat<int16, 60.f, true>) and
# CAnimBlendHierarchy::CalcTotalTime takes the LAST key's time as the
# duration (times are absolute on disk, converted to deltas after load).
# Vanilla anims are sampled at 30 fps, i.e. their time values step by 2.
_ANP3_TIME_UNITS_PER_SEC = 60.0
_INT16_MAX = 32767
# The field is int16 in the engine (FixedFloat<int16>): 0x8000..0xFFFF read
# back negative, so the writable ceiling is 32767 ticks = 546.1 s.
_ANP3_TIME_CLAMP = _INT16_MAX
_ANP3_ROT_SCALE = 4096.0
_ANP3_TRANS_SCALE = 1024.0

# ANPK ``ANIM`` chunk body size per target game. GTA III's loader reads a
# 48-byte body; VC/SA read the bone id ONLY from a 44-byte body
# (``if (chunkSize == 0x2C) SetBoneTag(body+40)``) — with 48 bytes the id
# is ignored and sequences fall back to name matching, which drops the
# root track ("Normal" in the IFP vs "Root" in the DFF).
_ANPK_ANIM_CHUNK_SIZE = {'III': 48, 'VC': 44, 'SA': 44}


def _t(s: str) -> str:
    """Lazy translation for user-facing error text in this otherwise
    Blender-free core module. Falls back to the raw Russian string when
    bpy/T isn't available (standalone unit tests)."""
    try:
        from .. import T
        return T(s)
    except Exception:
        return s


class IfpLimitError(ValueError):
    """Raised when a value does not fit the on-disk int16 quantisation of
    ANP3 (translation ±32 units, quaternion ±8, time ≤ 65535 ticks).

    Wraps the cryptic ``struct.error`` with a message naming the animation,
    bone and keyframe that broke the limit.
    """
    pass


def _build_anpk_cpan(bone: AnimBone, target: str = 'SA') -> bytes:
    """Serialise one bone as a CPAN chunk body (ANIM + key data)."""
    cpan_body = bytearray()

    # ANIM sub-chunk: name[24], unused[4], num_kf, unused[8], bone_id
    # (+ a -1 marker in the 48-byte GTA III layout only).
    anim_size = _ANPK_ANIM_CHUNK_SIZE.get(target, 44)
    anim_data = bytearray(anim_size)
    bone_name = bone.name.encode('ascii', errors='replace')[:23]
    anim_data[:len(bone_name)] = bone_name
    struct.pack_into('<I', anim_data, 28, len(bone.keyframes))
    struct.pack_into('<i', anim_data, 40, bone.bone_id)
    if anim_size >= 48:
        struct.pack_into('<i', anim_data, 44, -1)

    cpan_body.extend(b'ANIM')
    cpan_body.extend(struct.pack('<I', len(anim_data)))
    cpan_body.extend(anim_data)

    if not bone.keyframes:
        return bytes(cpan_body)

    if bone.key_type == HAS_ROT:
        key_ident = b'KR00'
    elif bone.key_type == (HAS_ROT | HAS_TRANS):
        key_ident = b'KRT0'
    else:
        key_ident = b'KRTS'

    key_data = bytearray()
    for kf in bone.keyframes:
        if bone.key_type & HAS_ROT:
            # ANPK convention: xyz negated on disk. Reader negates
            # again on load, so in-memory ``kf.rotation`` matches the
            # raw GTA quaternion the user thinks of.
            key_data.extend(struct.pack(
                '<4f',
                -kf.rotation[0], -kf.rotation[1],
                -kf.rotation[2], kf.rotation[3]))
        if bone.key_type & HAS_TRANS:
            key_data.extend(struct.pack('<3f', *kf.translation))
        if bone.key_type & HAS_SCALE:
            key_data.extend(struct.pack('<3f', *kf.scale))
        key_data.extend(struct.pack('<f', kf.time))

    cpan_body.extend(key_ident)
    cpan_body.extend(struct.pack('<I', len(key_data)))
    cpan_body.extend(key_data)
    return bytes(cpan_body)


def _build_anpk_anim(anim: Animation, target: str = 'SA') -> bytes:
    """Serialise one animation as NAME + DGAN chunks (concatenated)."""
    out = bytearray()

    # NAME — 28-byte body (24 chars + 4 padding).
    name_data = bytearray(28)
    name_bytes = anim.name.encode('ascii', errors='replace')[:23]
    name_data[:len(name_bytes)] = name_bytes
    out.extend(b'NAME')
    out.extend(struct.pack('<I', 28))
    out.extend(name_data)

    # DGAN — INFO(num_bones, flags) + CPAN(s).
    dgan_body = bytearray()
    info_body = struct.pack('<II', len(anim.bones), 0)
    dgan_body.extend(b'INFO')
    dgan_body.extend(struct.pack('<I', len(info_body)))
    dgan_body.extend(info_body)

    for bone in anim.bones:
        cpan_body = _build_anpk_cpan(bone, target)
        dgan_body.extend(b'CPAN')
        dgan_body.extend(struct.pack('<I', len(cpan_body)))
        dgan_body.extend(cpan_body)

    out.extend(b'DGAN')
    out.extend(struct.pack('<I', len(dgan_body)))
    out.extend(dgan_body)
    return bytes(out)


def write_anpk(filepath: str, ifp: IFPFile, target: str = 'SA') -> int:
    """Write a chunked ANPK IFP file (GTA III, VC, SA-uncompressed).

    ``target`` ('III' / 'VC' / 'SA') selects the ``ANIM`` chunk layout:
    48 bytes for GTA III, 44 bytes for VC/SA (the only size those two
    engines read the bone id from).

    Layout:
        ANPK + size
            INFO + size
                num_anims (uint32) + pkg_name (24 bytes)
            <NAME + DGAN> per animation

    KeyFrame.time is written as float32 seconds. KeyFrame.rotation is
    stored with xyz negated on disk (GTA's quaternion sign convention).
    Suitable for III/VC/SA — SA reads ANPK as well as ANP3.
    """
    content = bytearray()

    # INFO chunk: num_anims(4) + pkg_name(24).
    info_body = bytearray()
    info_body.extend(struct.pack('<I', len(ifp.animations)))
    pkg_name = bytearray(24)
    pkg_bytes = ifp.name.encode('ascii', errors='replace')[:23]
    pkg_name[:len(pkg_bytes)] = pkg_bytes
    info_body.extend(pkg_name)

    content.extend(b'INFO')
    content.extend(struct.pack('<I', len(info_body)))
    content.extend(info_body)

    for anim in ifp.animations:
        content.extend(_build_anpk_anim(anim, target))

    buf = bytearray()
    buf.extend(b'ANPK')
    buf.extend(struct.pack('<I', len(content)))
    buf.extend(content)

    with open(filepath, 'wb') as f:
        f.write(buf)
    return len(ifp.animations)


def _build_anp3_anim(anim: Animation) -> bytes:
    """Serialise one animation as flat ANP3 (compressed int16) bytes.

    Layout:
        anim header (36 bytes): name[24] + num_bones + data_size + flag
        per bone:
            bone header (36 bytes): name[24] + type + num_kf + bone_id
            per keyframe:
                int16 × 4 rotation (qx, qy, qz, qw) × 4096
                16-bit time in 1/60 s units
                [if rot+trans] int16 × 3 translation × 1024
    """
    out = bytearray()

    # 36-byte header. data_size patched after the bones are emitted.
    name_data = bytearray(24)
    name_bytes = anim.name.encode('ascii', errors='replace')[:23]
    name_data[:len(name_bytes)] = name_bytes
    out.extend(name_data)
    out.extend(struct.pack('<I', len(anim.bones)))
    data_size_offset = len(out)
    out.extend(struct.pack('<I', 0))      # placeholder: keyframe bytes
    # flag bit 0 = compressed keyframes. Vanilla writes 1 on every ANP3
    # animation; retail gta_sa.exe re-derives it from the first sequence,
    # but engines that trust the header would walk int16 data with float
    # strides and corrupt it if this were 0.
    out.extend(struct.pack('<I', 1))      # flag

    # data_size counts KEYFRAME bytes only (vanilla), not the 36-byte
    # bone headers — the loader mallocs exactly this many bytes and
    # copies kf_size × count per sequence into it.
    keyframe_bytes = 0

    for bone in anim.bones:
        bone_name_data = bytearray(24)
        bn = bone.name.encode('ascii', errors='replace')[:23]
        bone_name_data[:len(bn)] = bn
        out.extend(bone_name_data)

        # Type 3 = rotation only, 4 = rotation + translation. ANP3 has
        # no scale support; HAS_SCALE silently downgrades to 4.
        has_trans = bool(bone.key_type & HAS_TRANS)
        bone_type = 4 if has_trans else 3
        out.extend(struct.pack('<I', bone_type))
        out.extend(struct.pack('<I', len(bone.keyframes)))
        out.extend(struct.pack('<i', bone.bone_id))

        keyframe_bytes += len(bone.keyframes) * (16 if has_trans else 10)

        for ki, kf in enumerate(bone.keyframes):
            q = [int(round(c * _ANP3_ROT_SCALE)) for c in kf.rotation]
            if any(abs(c) > _INT16_MAX for c in q):
                raise IfpLimitError(_t(
                    "{0} / {1}, ключ {2}: компонент кватерниона {3} не влезает в int16 (|c| < 8.0). Нормализуй поворот."
                ).format(anim.name, bone.name, ki, kf.rotation))
            out.extend(struct.pack('<4h', *q))

            # Seconds → 1/60 s units. Negative times clamp to 0; anything
            # past the int16 field is an error, not a silent clamp.
            frame_num = int(round(kf.time * _ANP3_TIME_UNITS_PER_SEC))
            if frame_num < 0:
                frame_num = 0
            elif frame_num > _ANP3_TIME_CLAMP:
                raise IfpLimitError(_t(
                    "{0} / {1}, ключ {2}: время {3:.2f} с = {4} тиков — больше {5} (int16). Укороти анимацию."
                ).format(anim.name, bone.name, ki, kf.time, frame_num,
                         _ANP3_TIME_CLAMP))
            out.extend(struct.pack('<H', frame_num))

            if has_trans:
                t = [int(round(c * _ANP3_TRANS_SCALE)) for c in kf.translation]
                if any(abs(c) > _INT16_MAX for c in t):
                    raise IfpLimitError(_t(
                        "{0} / {1}, ключ {2}: смещение {3} не влезает в int16 (|v| < 32.0 единиц). Кость уехала слишком далеко."
                    ).format(anim.name, bone.name, ki, kf.translation))
                out.extend(struct.pack('<3h', *t))

    struct.pack_into('<I', out, data_size_offset, keyframe_bytes)
    return bytes(out)


def write_anp3(filepath: str, ifp: IFPFile, target: str = 'SA') -> int:
    """Write a flat int16-compressed ANP3 IFP file (GTA SA native).

    ``target`` is accepted for a uniform writer signature; ANP3 is SA-only.

    Layout:
        ANP3 + size
        pkg_name (24) + num_anims (uint32)
        per animation: flat 36-byte header + bones (no chunk wrappers)

    Rotations quantised to int16 with /4096 scale, translations to
    int16 with /1024 scale, time stored as 16-bit value in 1/60 s units.
    Use this for byte-faithful matching of vanilla peds.ifp.
    """
    body = bytearray()
    pkg_name = bytearray(24)
    pkg_bytes = ifp.name.encode('ascii', errors='replace')[:23]
    pkg_name[:len(pkg_bytes)] = pkg_bytes
    body.extend(pkg_name)
    body.extend(struct.pack('<I', len(ifp.animations)))

    for anim in ifp.animations:
        body.extend(_build_anp3_anim(anim))

    buf = bytearray()
    buf.extend(b'ANP3')
    buf.extend(struct.pack('<I', len(body)))
    buf.extend(body)

    with open(filepath, 'wb') as f:
        f.write(buf)
    return len(ifp.animations)


# Aliases — some modders refer to the III/VC chunked format as ANP2.
# Same wire format as ANPK, just a different name people search for.
write_anp2 = write_anpk


_FORMAT_DISPATCH = {
    'ANPK': write_anpk,
    'ANP2': write_anp2,
    'ANP3': write_anp3,
    'ANLF': write_anpk,  # ANLF wraps an ANPK; we strip the wrapper for now
}


def write_ifp(filepath: str, ifp: IFPFile, format: str = "",
              target: str = 'SA') -> int:
    """Write *ifp* to *filepath* in the requested format.

    ``format`` selects the on-disk encoding:
        - 'ANP3' — GTA SA flat compressed (int16 keyframes)
        - 'ANPK' / 'ANP2' — GTA III/VC/SA chunked (float32 keyframes)
        - '' (default) — fall back to ``ifp.source_format`` if it was
          set by the reader, otherwise 'ANPK' (round-trips cleanly,
          loadable in all three games).

    ``target`` ('III' / 'VC' / 'SA') picks the ANPK ``ANIM`` chunk size
    (48 bytes for III, 44 for VC/SA — see ``_ANPK_ANIM_CHUNK_SIZE``).

    Returns the number of animations written.
    """
    fmt = (format or ifp.source_format or 'ANPK').upper()
    writer = _FORMAT_DISPATCH.get(fmt)
    if writer is None:
        raise ValueError(f"Unsupported IFP format: {format!r}")
    return writer(filepath, ifp, target)


def _sample_linear_kf(kf_a: KeyFrame, kf_b: KeyFrame, t: float):
    """Return (rotation_xyzw, translation_xyz) sampled linearly between
    two keyframes at time *t*. Clamped to endpoints if t falls outside."""
    span = kf_b.time - kf_a.time
    if span <= 1e-9:
        alpha = 0.0
    else:
        alpha = (t - kf_a.time) / span
    if alpha < 0.0:
        alpha = 0.0
    elif alpha > 1.0:
        alpha = 1.0
    rot = tuple(
        kf_a.rotation[i] + (kf_b.rotation[i] - kf_a.rotation[i]) * alpha
        for i in range(4)
    )
    trans = tuple(
        kf_a.translation[i] + (kf_b.translation[i] - kf_a.translation[i]) * alpha
        for i in range(3)
    )
    return rot, trans


def decimate_bone_keyframes(bone: AnimBone,
                            tol_rot: float = 1e-3,
                            tol_trans: float = 1e-3) -> int:
    """Drop keyframes that fall on a linear interpolation between the
    previously-kept keyframe and the next original keyframe within
    tolerance. Single-pass, O(N) per bone. Modifies ``bone.keyframes``
    in place. Returns the number of keyframes removed.

    Rotation tolerance compares component-wise on the raw quaternion
    (max-norm on (x, y, z, w)). Translation tolerance is also max-norm
    on (x, y, z) in DFF units (typically metres). Defaults of 1e-3 are
    conservative — with SA's 16-bit ANP3 rotation quantisation the
    original keyframes already have ~1/4096 ≈ 2.4e-4 precision, so
    1e-3 drops truly-redundant keys without touching meaningful detail.

    Endpoints (first and last keyframe) are always preserved so the
    overall loop boundaries stay stable.
    """
    kfs = bone.keyframes
    n = len(kfs)
    if n < 3:
        return 0

    kept = [kfs[0]]
    for i in range(1, n - 1):
        curr = kfs[i]
        nxt = kfs[i + 1]
        prev = kept[-1]

        rot_pred, trans_pred = _sample_linear_kf(prev, nxt, curr.time)
        rot_delta = max(abs(curr.rotation[k] - rot_pred[k]) for k in range(4))
        trans_delta = max(
            abs(curr.translation[k] - trans_pred[k]) for k in range(3)
        )

        if rot_delta <= tol_rot and trans_delta <= tol_trans:
            continue  # curr is redundant — drop it
        kept.append(curr)

    kept.append(kfs[-1])
    removed = n - len(kept)
    bone.keyframes = kept
    return removed


def decimate_animation(anim: Animation,
                       tol_rot: float = 1e-3,
                       tol_trans: float = 1e-3) -> int:
    """Run ``decimate_bone_keyframes`` across every bone of an animation.
    Returns total removed keyframes."""
    return sum(
        decimate_bone_keyframes(b, tol_rot, tol_trans)
        for b in anim.bones
    )


def decimate_ifp(ifp: IFPFile,
                 tol_rot: float = 1e-3,
                 tol_trans: float = 1e-3) -> Tuple[int, int]:
    """Decimate every animation in *ifp* in place.

    Returns ``(removed, total_before)`` — both counts aggregated across
    all bones of all animations. ``(removed / total_before) * 100`` is
    the compression ratio for the report line.
    """
    total_before = sum(
        len(b.keyframes) for a in ifp.animations for b in a.bones
    )
    removed = sum(
        decimate_animation(a, tol_rot, tol_trans) for a in ifp.animations
    )
    return removed, total_before


def roundtrip_test(filepath: str) -> dict:
    """Read an IFP → write to a temp file → read that → compare.

    Semantic round-trip check for debugging the IFP codec. Writer
    preserves ``ifp.source_format`` so the temp file uses the same
    on-disk encoding as the input — ANPK round-trips byte-faithfully
    via float32, ANP3 loses some precision to int16 quantisation.
    We compare at the animation/bone/keyframe level with floating-point
    tolerance.

    Catches classic regressions:
    * Animations silently dropped on export
    * Quaternion XYZW ↔ WXYZ mis-swap (rotation delta explodes)
    * Sign flips on any rotation component
    * Translation axis reordering
    * Keyframe time precision loss

    Returns a dict of metrics:
        {
            'anims_in', 'anims_out',
            'bones_in', 'bones_out',
            'keyframes_in', 'keyframes_out',
            'max_rot_delta', 'max_trans_delta', 'max_time_delta',
            'missing_anims': [name, ...],
            'missing_bones': {anim_name: [bone, ...], ...},
            'kf_mismatches': [(anim, bone, in_count, out_count), ...],
            'error': str | None,
        }
    """
    import os
    import tempfile

    result = {
        'anims_in': 0, 'anims_out': 0,
        'bones_in': 0, 'bones_out': 0,
        'keyframes_in': 0, 'keyframes_out': 0,
        'max_rot_delta': 0.0,
        'max_trans_delta': 0.0,
        'max_time_delta': 0.0,
        'missing_anims': [],
        'missing_bones': {},
        'kf_mismatches': [],
        'error': None,
    }

    try:
        original = read_ifp(filepath)
    except Exception as e:
        result['error'] = f"read failed: {e}"
        return result

    result['anims_in'] = len(original.animations)
    result['bones_in'] = sum(len(a.bones) for a in original.animations)
    result['keyframes_in'] = sum(
        len(b.keyframes) for a in original.animations for b in a.bones)

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix='.ifp', prefix='inu_rt_')
        os.close(fd)
        write_ifp(tmp_path, original)
        reread = read_ifp(tmp_path)
    except Exception as e:
        result['error'] = f"write/reread failed: {e}"
        return result
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    result['anims_out'] = len(reread.animations)
    result['bones_out'] = sum(len(a.bones) for a in reread.animations)
    result['keyframes_out'] = sum(
        len(b.keyframes) for a in reread.animations for b in a.bones)

    # Index re-read by animation name (case-insensitive) for diffing.
    out_by_name = {a.name.lower(): a for a in reread.animations}

    for anim_in in original.animations:
        anim_out = out_by_name.get(anim_in.name.lower())
        if anim_out is None:
            result['missing_anims'].append(anim_in.name)
            continue

        out_bones_by_name = {b.name: b for b in anim_out.bones}
        missing_for_anim = []

        for bone_in in anim_in.bones:
            bone_out = out_bones_by_name.get(bone_in.name)
            if bone_out is None:
                missing_for_anim.append(bone_in.name)
                continue

            if len(bone_in.keyframes) != len(bone_out.keyframes):
                result['kf_mismatches'].append((
                    anim_in.name, bone_in.name,
                    len(bone_in.keyframes), len(bone_out.keyframes),
                ))
                continue

            for kf_in, kf_out in zip(bone_in.keyframes, bone_out.keyframes):
                # Rotation — 4 components, chord distance
                r_delta = max(
                    abs(kf_in.rotation[i] - kf_out.rotation[i])
                    for i in range(4)
                )
                if r_delta > result['max_rot_delta']:
                    result['max_rot_delta'] = r_delta

                t_delta = max(
                    abs(kf_in.translation[i] - kf_out.translation[i])
                    for i in range(3)
                )
                if t_delta > result['max_trans_delta']:
                    result['max_trans_delta'] = t_delta

                time_delta = abs(kf_in.time - kf_out.time)
                if time_delta > result['max_time_delta']:
                    result['max_time_delta'] = time_delta

        if missing_for_anim:
            result['missing_bones'][anim_in.name] = missing_for_anim

    return result


def merge_ifp(filepath: str, new_animations: List[Animation],
              package_name: str = None,
              format: str = "",
              target: str = 'SA') -> Tuple[int, int]:
    """Merge ``new_animations`` into an existing IFP file at ``filepath``.

    Reads the existing pack, replaces animations whose name matches
    (case-insensitive) with the corresponding entry from
    ``new_animations``, appends the rest, then rewrites the file.
    Returns ``(replaced_count, added_count)``.

    If ``filepath`` doesn't exist yet, a fresh pack is written with
    ``package_name`` (falls back to ``'ped'``) and every new animation
    is counted as added.

    ``format`` overrides the on-disk encoding for the rewrite. Empty
    string (default) preserves whatever format the reader detected on
    the existing file — so merging into vanilla SA peds.ifp keeps it
    ANP3, merging into a III file keeps it ANPK.

    This is the «without external IFP Editor» path — edit one
    animation in Blender, merge back into ``ped.ifp``, the rest of the
    pack's 294 vanilla animations stay intact byte-for-byte (as long
    as ``read_ifp → write_ifp`` round-trips cleanly).
    """
    import os

    if os.path.isfile(filepath):
        existing = read_ifp(filepath)
    else:
        existing = IFPFile(name=package_name or 'ped', animations=[])

    if package_name:
        existing.name = package_name

    # Index existing animations by lowercase name → list-position.
    # Iteration order is preserved for untouched entries so merged
    # pack keeps its original lookup order (the game iterates in
    # pack order when resolving an animation by name).
    by_name = {}
    for i, anim in enumerate(existing.animations):
        by_name[anim.name.lower()] = i

    replaced = 0
    added = 0
    for new_anim in new_animations:
        key = new_anim.name.lower()
        idx = by_name.get(key)
        if idx is not None:
            existing.animations[idx] = new_anim
            replaced += 1
        else:
            existing.animations.append(new_anim)
            by_name[key] = len(existing.animations) - 1
            added += 1

    write_ifp(filepath, existing, format=format, target=target)
    return replaced, added


def classify_bone_refs(data_paths, arm_bone_names) -> Tuple[List[str], List[str]]:
    """Pure-logic core of ``ops.ifp_export.validate_action_bones``.

    Given an iterable of fcurve ``data_path`` strings and a set of
    available armature bone names, return ``(unknown, known)`` —
    sorted lists of bone names referenced via ``pose.bones["..."]``,
    split by membership.

    Lives here (not in ops.ifp_export) so it stays bpy-free and
    testable outside Blender. The bpy wrapper just feeds it the right
    iterables.
    """
    arm_set = set(arm_bone_names)
    referenced = set()
    for path in data_paths:
        if not path.startswith('pose.bones['):
            continue
        parts = path.split('"')
        if len(parts) < 2:
            continue
        referenced.add(parts[1])

    unknown = sorted(n for n in referenced if n not in arm_set)
    known = sorted(n for n in referenced if n in arm_set)
    return unknown, known
