"""Format-aware writer tests for ANP3 / ANPK / ANP2.

Exercises the new ``write_ifp(format=...)`` dispatcher and the per-format
writers added for III/VC modding support. Each format gets a proper
round-trip test plus a check that the file's magic bytes are correct
on disk (the previous buggy writer emitted ANP3 magic with ANPK chunk
content, unloadable by either game's IFP reader).
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.ifp import (  # noqa: E402
    IFPFile,
    Animation,
    AnimBone,
    KeyFrame,
    HAS_ROT,
    HAS_TRANS,
    write_ifp,
    write_anpk,
    write_anp2,
    write_anp3,
    read_ifp,
)


def _sample_ifp(pkg="custom") -> IFPFile:
    """Two anims, two bones each, mixed key types — enough to exercise
    NAME/DGAN/CPAN structure and rot+trans encoding in both formats."""
    walk = Animation(name="WALK", bones=[
        AnimBone(
            name="Bip01 Pelvis", bone_id=0,
            key_type=HAS_ROT | HAS_TRANS,
            keyframes=[
                KeyFrame(rotation=(0.0, 0.0, 0.0, 1.0),
                         translation=(0.0, 0.0, 0.0), time=0.0),
                KeyFrame(rotation=(0.0, 0.1, 0.0, 0.995),
                         translation=(0.1, 0.0, 0.0), time=0.5),
            ],
        ),
        AnimBone(
            name="Bip01 Spine", bone_id=1, key_type=HAS_ROT,
            keyframes=[
                KeyFrame(rotation=(0.0, 0.0, 0.0, 1.0), time=0.0),
                KeyFrame(rotation=(0.05, 0.0, 0.0, 0.999), time=0.5),
            ],
        ),
    ])
    idle = Animation(name="IDLE", bones=[
        AnimBone(
            name="Bip01 Head", bone_id=2, key_type=HAS_ROT,
            keyframes=[
                KeyFrame(rotation=(0.0, 0.0, 0.0, 1.0), time=0.0),
                KeyFrame(rotation=(0.0, 0.0, 0.05, 0.999), time=1.0),
            ],
        ),
    ])
    return IFPFile(name=pkg, animations=[walk, idle])


# ─────────────────────────────── ANPK ────────────────────────────────

def test_write_anpk_emits_correct_magic_bytes(tmp_path):
    path = tmp_path / "out.ifp"
    write_anpk(str(path), _sample_ifp())
    with open(path, 'rb') as f:
        magic = f.read(4)
    assert magic == b'ANPK'


def test_write_anpk_round_trip_preserves_structure(tmp_path):
    src = _sample_ifp(pkg="custom")
    path = tmp_path / "anpk.ifp"
    count = write_anpk(str(path), src)
    assert count == 2

    parsed = read_ifp(str(path))
    assert parsed.source_format == 'ANPK'
    assert parsed.name == "custom"
    assert [a.name for a in parsed.animations] == ["WALK", "IDLE"]
    assert [b.name for b in parsed.animations[0].bones] == \
           ["Bip01 Pelvis", "Bip01 Spine"]
    assert len(parsed.animations[0].bones[0].keyframes) == 2


def test_write_anpk_round_trip_preserves_keyframe_values(tmp_path):
    """ANPK uses float32 — round-trip should be byte-faithful within
    float precision (rotation sign convention applied twice cancels)."""
    src = _sample_ifp()
    path = tmp_path / "anpk.ifp"
    write_anpk(str(path), src)
    parsed = read_ifp(str(path))

    bone_in = src.animations[0].bones[0]
    bone_out = parsed.animations[0].bones[0]
    for kf_in, kf_out in zip(bone_in.keyframes, bone_out.keyframes):
        for i in range(4):
            assert abs(kf_in.rotation[i] - kf_out.rotation[i]) < 1e-6
        for i in range(3):
            assert abs(kf_in.translation[i] - kf_out.translation[i]) < 1e-6
        assert abs(kf_in.time - kf_out.time) < 1e-6


def test_write_anp2_alias_matches_anpk_output(tmp_path):
    """ANP2 is an alias for ANPK — same wire format, both names exist
    because different docs call the III/VC chunked encoding different
    things. Emitted bytes should be identical."""
    src = _sample_ifp()
    p_anpk = tmp_path / "x.ifp"
    p_anp2 = tmp_path / "y.ifp"
    write_anpk(str(p_anpk), src)
    write_anp2(str(p_anp2), src)
    assert p_anpk.read_bytes() == p_anp2.read_bytes()


# ─────────────────────────────── ANP3 ────────────────────────────────

def test_write_anp3_emits_correct_magic_bytes(tmp_path):
    path = tmp_path / "out.ifp"
    write_anp3(str(path), _sample_ifp())
    with open(path, 'rb') as f:
        magic = f.read(4)
    assert magic == b'ANP3'


def test_write_anp3_round_trip_within_quantisation_tolerance(tmp_path):
    """ANP3 quantises rotation to int16 (×4096) and translation to int16
    (×1024), so round-trip is lossy. Tolerance must be ≥ 1/4096 ≈ 2.4e-4
    for rot, ≥ 1/1024 ≈ 9.8e-4 for trans."""
    src = _sample_ifp()
    path = tmp_path / "anp3.ifp"
    write_anp3(str(path), src)
    parsed = read_ifp(str(path))
    assert parsed.source_format == 'ANP3'
    assert [a.name for a in parsed.animations] == ["WALK", "IDLE"]

    bone_in = src.animations[0].bones[0]
    bone_out = parsed.animations[0].bones[0]
    for kf_in, kf_out in zip(bone_in.keyframes, bone_out.keyframes):
        for i in range(4):
            assert abs(kf_in.rotation[i] - kf_out.rotation[i]) < 3e-4
        for i in range(3):
            assert abs(kf_in.translation[i] - kf_out.translation[i]) < 1e-3


def test_write_anp3_time_round_trips_via_60_units_quantisation(tmp_path):
    """ANP3 stores time as a 16-bit value in 1/60 s units. Time 0.5s →
    raw 30 → 0.5s on read."""
    src = IFPFile(name="t", animations=[
        Animation(name="A", bones=[
            AnimBone(name="B", bone_id=0, key_type=HAS_ROT, keyframes=[
                KeyFrame(rotation=(0.0, 0.0, 0.0, 1.0), time=0.0),
                KeyFrame(rotation=(0.0, 0.0, 0.0, 1.0), time=1.0),
                KeyFrame(rotation=(0.0, 0.0, 0.0, 1.0), time=2.0),
            ]),
        ]),
    ])
    path = tmp_path / "anp3.ifp"
    write_anp3(str(path), src)
    parsed = read_ifp(str(path))
    times = [kf.time for kf in parsed.animations[0].bones[0].keyframes]
    assert abs(times[0] - 0.0) < 1e-6
    assert abs(times[1] - 1.0) < 1e-6
    assert abs(times[2] - 2.0) < 1e-6


def _anp3_single_bone_bytes(raw_times, bone_type=3):
    """Hand-built ANP3 file: one animation, one bone, identity rotations,
    the given raw 16-bit time values."""
    import struct
    kf = b"".join(struct.pack("<4hH", 0, 0, 0, 4096, t)
                  + (struct.pack("<3h", 0, 0, 0) if bone_type == 4 else b"")
                  for t in raw_times)
    bone = (b"Root".ljust(24, b"\0") + struct.pack("<IIi", bone_type, len(raw_times), 0) + kf)
    anim = b"WALK".ljust(24, b"\0") + struct.pack("<III", 1, len(bone), 0) + bone
    body = b"pkg".ljust(24, b"\0") + struct.pack("<I", 1) + anim
    return b"ANP3" + struct.pack("<I", len(body)) + body


def test_read_anp3_time_is_sixtieths_of_a_second(tmp_path):
    """The game reads ANP3 keyframe time as fixed-point with a 60.0 divisor
    (gta-reversed KeyFrameCompressed::DeltaTime = FixedFloat<int16, 60>).
    Vanilla SA anims are keyed at 30 fps, so raw times step by 2: ped.ifp
    WALK_player has 37 keys with times 0, 2, ..., 72 and lasts 1.2 s.
    Reading raw 72 as frame@30fps would give 2.4 s — double length."""
    path = tmp_path / "vanilla_like.ifp"
    path.write_bytes(_anp3_single_bone_bytes(list(range(0, 73, 2)), bone_type=4))
    parsed = read_ifp(str(path))
    times = [kf.time for kf in parsed.animations[0].bones[0].keyframes]
    assert len(times) == 37
    assert abs(times[1] - 1.0 / 30.0) < 1e-6
    assert abs(times[-1] - 1.2) < 1e-6


def test_write_anp3_emits_sixtieths_of_a_second_on_disk(tmp_path):
    """1.2 s must be written as raw 72 (not 36), otherwise the exported anim
    plays twice as fast in game."""
    import struct
    src = IFPFile(name="t", animations=[
        Animation(name="A", bones=[
            AnimBone(name="B", bone_id=0, key_type=HAS_ROT, keyframes=[
                KeyFrame(rotation=(0.0, 0.0, 0.0, 1.0), time=0.0),
                KeyFrame(rotation=(0.0, 0.0, 0.0, 1.0), time=1.0 / 30.0),
                KeyFrame(rotation=(0.0, 0.0, 0.0, 1.0), time=1.2),
            ]),
        ]),
    ])
    path = tmp_path / "out.ifp"
    write_anp3(str(path), src)
    data = path.read_bytes()
    # header 8 + pkg 24 + count 4 + anim hdr 36 + bone hdr 36 → first key
    first_key = 8 + 24 + 4 + 36 + 36
    raw = [struct.unpack_from("<H", data, first_key + 10 * i + 8)[0] for i in range(3)]
    assert raw == [0, 2, 72]


# ────────────────────────── dispatch / default ──────────────────────────

def test_write_ifp_default_emits_anpk(tmp_path):
    """No format param + no source_format → must default to ANPK,
    not the previous buggy 'ANP3 magic + ANPK content' hybrid."""
    path = tmp_path / "default.ifp"
    write_ifp(str(path), _sample_ifp())
    with open(path, 'rb') as f:
        assert f.read(4) == b'ANPK'


def test_write_ifp_format_param_overrides_default(tmp_path):
    src = _sample_ifp()
    p3 = tmp_path / "anp3.ifp"
    pk = tmp_path / "anpk.ifp"
    write_ifp(str(p3), src, format='ANP3')
    write_ifp(str(pk), src, format='ANPK')
    assert p3.read_bytes()[:4] == b'ANP3'
    assert pk.read_bytes()[:4] == b'ANPK'


def test_write_ifp_preserves_source_format_round_trip(tmp_path):
    """Read ANP3 → modify → write_ifp() with empty format → must write
    ANP3 again, not silently switch to ANPK. This is the merge_ifp
    invariant: editing one anim in vanilla peds.ifp keeps the file's
    on-disk format intact."""
    src = _sample_ifp()
    path = tmp_path / "x.ifp"
    write_anp3(str(path), src)

    loaded = read_ifp(str(path))
    assert loaded.source_format == 'ANP3'

    out_path = tmp_path / "y.ifp"
    write_ifp(str(out_path), loaded)  # no format → use source_format
    with open(out_path, 'rb') as f:
        assert f.read(4) == b'ANP3'


def test_write_ifp_rejects_unknown_format(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        write_ifp(str(tmp_path / "x.ifp"), _sample_ifp(), format='WXYZ')


# ────────────────────── cross-format conversion ──────────────────────

def test_anpk_to_anp3_conversion_round_trip(tmp_path):
    """Read an ANPK file, save as ANP3 — should produce a valid SA file
    whose anims/bones/keyframe-counts match (values within int16 quant)."""
    src = _sample_ifp()
    p_anpk = tmp_path / "in.ifp"
    p_anp3 = tmp_path / "out.ifp"
    write_anpk(str(p_anpk), src)

    loaded = read_ifp(str(p_anpk))
    write_ifp(str(p_anp3), loaded, format='ANP3')

    converted = read_ifp(str(p_anp3))
    assert converted.source_format == 'ANP3'
    assert len(converted.animations) == len(src.animations)
    for a_in, a_out in zip(src.animations, converted.animations):
        assert a_in.name == a_out.name
        assert len(a_in.bones) == len(a_out.bones)
        for b_in, b_out in zip(a_in.bones, a_out.bones):
            assert b_in.name == b_out.name
            assert len(b_in.keyframes) == len(b_out.keyframes)
