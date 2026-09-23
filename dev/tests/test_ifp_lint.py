"""core.ifp_lint — pre-write audit of IFP animations against what
CAnimManager::LoadAnimFile and the CAnimBlend* playback code do with bad
input, plus regressions for the IFP writer fixes from the same engine
read (W6 ANP3 header, W7 ANPK ANIM chunk size, W8 quantisation errors).

Every rule gets a passing and a failing case built from synthetic core
structures. Pure Python — no Blender required.
"""

from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.ifp import (  # noqa: E402
    IFPFile, Animation, AnimBone, KeyFrame, HAS_ROT, HAS_TRANS, HAS_SCALE,
    IfpLimitError, write_ifp, read_ifp,
)
from core.ifp_lint import check_ifp, MAX_COUNT  # noqa: E402


def _kf(t, q=(0.0, 0.0, 0.0, 1.0), pos=(0.0, 0.0, 0.0)):
    return KeyFrame(rotation=q, translation=pos, time=t)


def _bone(name="Pelvis", bone_id=1, key_type=HAS_ROT, times=(0.0, 0.5, 1.0)):
    return AnimBone(name=name, bone_id=bone_id, key_type=key_type,
                    keyframes=[_kf(t) for t in times])


def _anim(name="walk", bones=None):
    if bones is None:
        bones = [_bone("Root", 0, HAS_ROT | HAS_TRANS), _bone("Pelvis", 1)]
    return Animation(name=name, bones=bones)


def _ifp(name="custom", anims=None):
    return IFPFile(name=name, animations=anims if anims is not None else [_anim()])


def _has(items, tag):
    return any(tag in s for s in items)


def _check(ifp, **kw):
    kw.setdefault('target', 'SA')
    kw.setdefault('fmt', 'ANP3')
    return check_ifp(ifp, **kw)


# ── baseline ─────────────────────────────────────────────────────

def test_clean_pack_passes():
    assert _check(_ifp(), file_stem="custom") == ([], [])


def test_accepts_a_plain_animation_list():
    fatal, warn = check_ifp([_anim()], block_name="custom", target='SA')
    assert fatal == [] and warn == []


# ── IFP-01 / IFP-02 ──────────────────────────────────────────────

def test_ifp01_empty_sequence_is_fatal():
    ifp = _ifp(anims=[_anim(bones=[_bone(times=())])])
    assert _has(_check(ifp)[0], "IFP-01")


def test_ifp02_empty_animation_is_fatal():
    ifp = _ifp(anims=[_anim(bones=[])])
    assert _has(_check(ifp)[0], "IFP-02")


# ── IFP-04 / IFP-05 ──────────────────────────────────────────────

def test_ifp04_key_type_without_rotation_is_fatal():
    ifp = _ifp(anims=[_anim(bones=[_bone(key_type=HAS_TRANS)])])
    assert _has(_check(ifp)[0], "IFP-04")


def test_ifp05_mixed_compression_classes_are_fatal():
    a, b = _bone("Root", 0), _bone("Pelvis", 1)
    a.compressed = True
    b.compressed = False
    ifp = _ifp(anims=[_anim(bones=[a, b])])
    assert _has(_check(ifp)[0], "IFP-05")
    b.compressed = True
    assert not _has(_check(ifp)[0], "IFP-05")


# ── IFP-06 / IFP-07 / IFP-08 ─────────────────────────────────────

def test_ifp06_first_key_not_at_zero_is_a_warning():
    ifp = _ifp(anims=[_anim(bones=[_bone(times=(0.5, 1.0))])])
    fatal, warn = _check(ifp)
    assert fatal == []
    assert _has(warn, "IFP-06")


def test_ifp07_decreasing_times_are_fatal():
    ifp = _ifp(anims=[_anim(bones=[_bone(times=(0.0, 1.0, 0.5))])])
    assert _has(_check(ifp)[0], "IFP-07")


def test_ifp07_zero_duration_with_several_keys_is_fatal():
    ifp = _ifp(anims=[_anim(bones=[_bone(times=(0.0, 0.0, 0.0))])])
    assert _has(_check(ifp)[0], "IFP-07")
    # A single-pose sequence is fine.
    ifp = _ifp(anims=[_anim(bones=[_bone(times=(0.0,))])])
    assert _check(ifp) == ([], [])


def test_ifp08_equal_consecutive_ticks_warn():
    # 0.005 s apart → same ANP3 tick at 60 ticks/s.
    ifp = _ifp(anims=[_anim(bones=[_bone(times=(0.0, 0.5, 0.505, 1.0))])])
    fatal, warn = _check(ifp)
    assert fatal == []
    assert _has(warn, "IFP-08")


# ── IFP-09 ───────────────────────────────────────────────────────

def test_ifp09_translation_out_of_int16_range_is_fatal():
    b = _bone("Root", 0, HAS_ROT | HAS_TRANS, times=(0.0, 1.0))
    b.keyframes[1].translation = (32.0, 0.0, 0.0)
    assert _has(_check(_ifp(anims=[_anim(bones=[b])]))[0], "IFP-09")
    b.keyframes[1].translation = (31.9, 0.0, 0.0)
    assert not _has(_check(_ifp(anims=[_anim(bones=[b])]))[0], "IFP-09")


def test_ifp09_quaternion_component_out_of_range_is_fatal():
    b = _bone(times=(0.0, 1.0))
    b.keyframes[1].rotation = (8.0, 0.0, 0.0, 1.0)
    assert _has(_check(_ifp(anims=[_anim(bones=[b])]))[0], "IFP-09")


def test_ifp09_time_past_int16_ticks_is_fatal():
    # ANP3 tick = time * 60 → 32767 ticks = 546.1 s.
    b = _bone(times=(0.0, 550.0))
    assert _has(_check(_ifp(anims=[_anim(bones=[b])]))[0], "IFP-09")
    b = _bone(times=(0.0, 500.0))
    assert not _has(_check(_ifp(anims=[_anim(bones=[b])]))[0], "IFP-09")
    # ANPK on SA is quantised time * 60 on load → 546.1 s ceiling.
    b = _bone(times=(0.0, 600.0))
    assert _has(_check(_ifp(anims=[_anim(bones=[b])]), fmt='ANPK')[0], "IFP-09")
    # III/VC never compress: no ceiling.
    assert not _has(_check(_ifp(anims=[_anim(bones=[b])]), fmt='ANPK', target='VC')[0], "IFP-09")


# ── IFP-10 ───────────────────────────────────────────────────────

def test_ifp10_counts_above_int16_are_fatal():
    b = AnimBone(name="Pelvis", bone_id=1, key_type=HAS_ROT,
                 keyframes=[_kf(i / 60.0) for i in range(MAX_COUNT + 1)])
    assert _has(_check(_ifp(anims=[_anim(bones=[b])]))[0], "IFP-10")
    bones = [_bone(f"b{i}", i) for i in range(MAX_COUNT + 1)]
    fatal, _ = _check(_ifp(anims=[Animation(name="x", bones=bones)]))
    assert _has(fatal, "IFP-10")


# ── IFP-11 / IFP-20 ──────────────────────────────────────────────

def test_ifp11_block_name_longer_than_15_is_fatal():
    assert _has(_check(_ifp(name="a" * 16))[0], "IFP-11")
    assert not _has(_check(_ifp(name="a" * 15))[0], "IFP-11")


def test_ifp20_block_name_must_match_file_stem():
    assert _has(_check(_ifp(name="custom"), file_stem="myanims")[0], "IFP-20")
    assert not _has(_check(_ifp(name="custom"), file_stem="CUSTOM")[0], "IFP-20")
    # No stem given → not checked (merge into an existing pack).
    assert not _has(_check(_ifp(name="custom"))[0], "IFP-20")


def test_ifp11_animation_name_longer_than_23_is_fatal():
    assert _has(_check(_ifp(anims=[_anim(name="a" * 24)]))[0], "IFP-11")
    assert not _has(_check(_ifp(anims=[_anim(name="a" * 23)]))[0], "IFP-11")


def test_ifp11_bone_name_longer_than_23_warns():
    ifp = _ifp(anims=[_anim(bones=[_bone(name="b" * 24)])])
    fatal, warn = _check(ifp)
    assert not _has(fatal, "IFP-11")
    assert _has(warn, "IFP-11")


# ── IFP-16 ───────────────────────────────────────────────────────

def test_ifp16_non_unit_quaternion_warns_nan_is_fatal():
    b = _bone(times=(0.0, 1.0))
    b.keyframes[1].rotation = (0.0, 0.0, 0.0, 0.9)
    fatal, warn = _check(_ifp(anims=[_anim(bones=[b])]))
    assert fatal == []
    assert _has(warn, "IFP-16")
    b.keyframes[1].rotation = (float('nan'), 0.0, 0.0, 1.0)
    assert _has(_check(_ifp(anims=[_anim(bones=[b])]))[0], "IFP-16")


# ── IFP-18 ───────────────────────────────────────────────────────

def test_ifp18_duplicate_animation_names_are_case_insensitive():
    ifp = _ifp(anims=[_anim(name="Walk"), _anim(name="WALK")])
    assert _has(_check(ifp)[1], "IFP-18")


def test_ifp18_duplicate_bone_in_animation_warns():
    ifp = _ifp(anims=[_anim(bones=[_bone("Pelvis", 1), _bone("Pelvis2", 1)])])
    assert _has(_check(ifp)[1], "IFP-18")
    # id -1 sequences are matched by name: same name = duplicate,
    # different names are not (vanilla CAR_alignHI_LHS has 22 of them).
    ifp = _ifp(anims=[_anim(bones=[_bone("Root", -1), _bone("Pelvis", -1)])])
    assert not _has(_check(ifp)[1], "IFP-18")
    ifp = _ifp(anims=[_anim(bones=[_bone("Root", -1), _bone("root", -1)])])
    assert _has(_check(ifp)[1], "IFP-18")


# ── IFP-19 / IFP-21 ──────────────────────────────────────────────

def test_ifp19_translation_on_non_root_bone_warns():
    ifp = _ifp(anims=[_anim(bones=[_bone("Root", 0, HAS_ROT | HAS_TRANS),
                                   _bone("L Hand", 24, HAS_ROT | HAS_TRANS)])])
    fatal, warn = _check(ifp)
    assert fatal == []
    assert _has(warn, "IFP-19") and "L Hand" in ''.join(warn)
    # Root by id or by name ("Normal" in vanilla IFPs) is fine.
    ifp = _ifp(anims=[_anim(bones=[_bone("Normal", -1, HAS_ROT | HAS_TRANS)])])
    assert not _has(_check(ifp)[1], "IFP-19")


def test_ifp21_scale_keys_warn():
    ifp = _ifp(anims=[_anim(bones=[_bone("Root", 0, HAS_ROT | HAS_TRANS | HAS_SCALE)])])
    assert _has(_check(ifp)[1], "IFP-21")


# ── total animation budget ───────────────────────────────────────

def test_total_animation_budget():
    assert _has(_check(_ifp(), total_anims=2500)[0], "2500")
    assert not _has(_check(_ifp(), total_anims=2499)[0], "2500")


# ── writer regressions ───────────────────────────────────────────

def test_w6_anp3_header_flag_is_1_and_data_size_counts_keyframes_only(tmp_path):
    path = tmp_path / "custom.ifp"
    write_ifp(str(path), _ifp(), format='ANP3')
    data = path.read_bytes()
    # ANP3(4) size(4) name(24) num_anims(4) → first animation header.
    off = 36
    num_bones, data_size, flag = struct.unpack_from('<III', data, off + 24)
    assert num_bones == 2
    assert flag == 1
    # Root: 3 keys × 16 (rot+trans); Pelvis: 3 keys × 10 (rot only).
    assert data_size == 3 * 16 + 3 * 10
    parsed = read_ifp(str(path))
    assert len(parsed.animations[0].bones[0].keyframes) == 3


def test_w7_anpk_anim_chunk_is_44_bytes_for_sa_and_vc_48_for_iii(tmp_path):
    for target, expected in (('SA', 44), ('VC', 44), ('III', 48)):
        path = tmp_path / f"custom_{target}.ifp"
        write_ifp(str(path), _ifp(), format='ANPK', target=target)
        data = path.read_bytes()
        idx = data.find(b'ANIM')
        size = struct.unpack_from('<I', data, idx + 4)[0]
        assert size == expected, target
        # Bone id lives at +40 in both layouts and survives the round trip.
        assert struct.unpack_from('<i', data, idx + 8 + 40)[0] == 0
        parsed = read_ifp(str(path))
        assert [b.bone_id for b in parsed.animations[0].bones] == [0, 1]


def test_w7_default_target_is_sa(tmp_path):
    path = tmp_path / "custom.ifp"
    write_ifp(str(path), _ifp(), format='ANPK')
    data = path.read_bytes()
    idx = data.find(b'ANIM')
    assert struct.unpack_from('<I', data, idx + 4)[0] == 44


def test_w8_anp3_out_of_range_values_raise_a_named_error(tmp_path):
    path = tmp_path / "custom.ifp"
    b = _bone("Root", 0, HAS_ROT | HAS_TRANS, times=(0.0, 1.0))
    b.keyframes[1].translation = (40.0, 0.0, 0.0)
    with pytest.raises(IfpLimitError) as e:
        write_ifp(str(path), _ifp(anims=[_anim(bones=[b])]), format='ANP3')
    assert "Root" in str(e.value)

    b = _bone(times=(0.0, 1.0))
    b.keyframes[1].rotation = (9.0, 0.0, 0.0, 1.0)
    with pytest.raises(IfpLimitError):
        write_ifp(str(path), _ifp(anims=[_anim(bones=[b])]), format='ANP3')

    # The engine reads the tick as int16 → 32768 ticks already wraps negative.
    b = _bone(times=(0.0, 32768 / 60.0))
    with pytest.raises(IfpLimitError):
        write_ifp(str(path), _ifp(anims=[_anim(bones=[b])]), format='ANP3')

    # The limits themselves are still writable.
    b = _bone("Root", 0, HAS_ROT | HAS_TRANS, times=(0.0, 32767 / 60.0))
    b.keyframes[1].translation = (31.99, -31.99, 0.0)
    write_ifp(str(path), _ifp(anims=[_anim(bones=[b])]), format='ANP3')
    parsed = read_ifp(str(path))
    assert parsed.animations[0].bones[0].keyframes[1].translation[0] == pytest.approx(31.99, abs=1e-3)
