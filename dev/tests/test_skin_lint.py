"""core.skin_lint — pre-write audit of a skinned (ped) clump against what
gta_sa.exe dereferences at load / spawn, plus regressions for the DFF
writer fixes that came out of the same engine read (W1 frame-name chunk,
W2 skin layout, W9 vertex limit).

Every rule gets a passing and a failing case built from synthetic core
structures. Pure Python — no Blender required.
"""

from pathlib import Path
from struct import unpack_from
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.dff import (  # noqa: E402
    DffClump, DffFrame, DffGeometry, DffAtomic, DffMaterial, Triangle,
    BoundingSphere, RGBA, SkinData, HAnimData, HAnimBone, DffLimitError,
    CHUNK_FRAME_NAME, FRAME_NAME_MAX, write_dff, read_dff,
)
from core.skin_lint import (  # noqa: E402
    check_skin_clump, ALWAYS_USED_BONE_IDS, CONDITIONAL_BONE_IDS,
    MAX_BONES, MAX_PUSH_DEPTH,
)

# The 32-node vanilla SA skeleton (army.dff) — id, push/pop flags in
# depth-first order. Pushes on 2,3,4,5,31,41; pops on 7,36,26,301,201,44,54
# (the last node pops an empty stack: normal R* layout).
VANILLA_NODES = [
    (0, 0), (1, 0), (2, 2), (3, 2), (4, 2), (5, 2), (6, 0), (7, 1),
    (8, 3), (31, 2), (32, 0), (33, 0), (34, 0), (35, 0), (36, 1),
    (21, 0), (22, 0), (23, 0), (24, 0), (25, 0), (26, 1),
    (302, 0), (301, 1), (201, 1),
    (41, 2), (42, 0), (43, 0), (44, 1),
    (51, 0), (52, 0), (53, 0), (54, 1),
]

IDENTITY = ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def _geom(num_verts=3):
    return DffGeometry(
        vertices=[(float(i), 0.0, 0.0) for i in range(num_verts)],
        normals=[(0.0, 0.0, 1.0)] * num_verts,
        triangles=[Triangle(a=0, b=1, c=2, material=0)],
        materials=[DffMaterial(color=RGBA(255, 255, 255, 255))],
        bounding_sphere=BoundingSphere(0.0, 0.0, 0.0, 2.0),
    )


def _skin(num_bones, num_verts=3, bone=1):
    """Every vertex fully weighted to ``bone`` (root moved to slot 3 the
    way the exporter does it)."""
    return SkinData(
        num_bones=num_bones, num_used=1, max_weights=4, bones_used=[bone],
        bone_indices=[(bone, 0, 0, 0)] * num_verts,
        bone_weights=[(1.0, 0.0, 0.0, 0.0)] * num_verts,
        bone_matrices=[IDENTITY] * num_bones,
    )


def _ped(nodes=VANILLA_NODES, num_verts=3):
    """Minimal vanilla-shaped ped: root frame, one bone frame per node
    (the first carries the table), one skinned atomic."""
    frames = [DffFrame(name="csplay", parent=-1, flags=0x20003, write_name=True)]
    for i, (bid, btype) in enumerate(nodes):
        f = DffFrame(name=f"b{bid}", parent=0 if i == 0 else 1,
                     flags=3, write_name=True)
        f.hanim = HAnimData(bone_id=bid)
        if i == 0:
            f.hanim.bones = [HAnimBone(bone_id=b, index=j, bone_type=t)
                             for j, (b, t) in enumerate(nodes)]
        frames.append(f)
    g = _geom(num_verts)
    g.skin = _skin(len(nodes), num_verts)
    return DffClump(frames=frames, geometries=[g],
                    atomics=[DffAtomic(frame_index=1, geometry_index=0)])


def _table(clump):
    return clump.frames[1].hanim


def _has(items, tag):
    return any(tag in s for s in items)


# ── baseline ─────────────────────────────────────────────────────

def test_vanilla_shaped_ped_is_clean():
    fatal, warn = check_skin_clump(_ped())
    assert fatal == [], fatal
    assert warn == [], warn


def test_unskinned_clump_is_ignored():
    g = _geom()
    clump = DffClump(frames=[DffFrame(name="x", parent=-1)], geometries=[g],
                     atomics=[DffAtomic(frame_index=0, geometry_index=0)])
    assert check_skin_clump(clump) == ([], [])


def test_written_and_reread_ped_is_still_clean():
    clump = _ped()
    parsed = read_dff(write_dff(clump))
    fatal, warn = check_skin_clump(parsed)
    assert fatal == [] and warn == []


def test_raw_frame_list_is_decoded_for_the_audit():
    # The Blender exporter replays the import-time frame list and clears
    # clump.frames; the audit must still see the hierarchy.
    clump = _ped()
    parsed = read_dff(write_dff(clump))
    raw = parsed.frames[0]._raw_frame_list
    parsed.raw_frame_list = raw
    parsed.frames.clear()
    fatal, warn = check_skin_clump(parsed)
    assert fatal == [] and warn == []
    # ...and a broken hierarchy inside the raw bytes is still caught.
    parsed.raw_frame_list = b''
    assert _has(check_skin_clump(parsed)[0], "C01")


# ── hierarchy rules ──────────────────────────────────────────────

def test_c01_no_node_table_is_fatal():
    clump = _ped()
    _table(clump).bones = []
    assert _has(check_skin_clump(clump)[0], "C01")


def test_c02_last_atomic_must_be_skinned():
    clump = _ped()
    extra = _geom()
    clump.geometries.append(extra)
    clump.atomics.append(DffAtomic(frame_index=0, geometry_index=1))
    assert _has(check_skin_clump(clump)[0], "C02")
    # Skinned atomic last → fine again.
    clump.atomics.reverse()
    assert not _has(check_skin_clump(clump)[0], "C02")


def test_c02_no_atomics_is_fatal():
    clump = _ped()
    clump.atomics = []
    assert _has(check_skin_clump(clump)[0], "C02")


def test_c03_no_matrices_flag_is_fatal():
    clump = _ped()
    _table(clump).flags = 0x36
    assert _has(check_skin_clump(clump)[0], "C03")


def test_c04_keyframe_size_below_28_is_fatal():
    clump = _ped()
    _table(clump).keyframe_size = 20
    assert _has(check_skin_clump(clump)[0], "C04")
    _table(clump).keyframe_size = 28
    assert not _has(check_skin_clump(clump)[0], "C04")


def test_c05_more_than_64_bones_is_fatal():
    nodes = VANILLA_NODES + [(1000 + i, 0) for i in range(MAX_BONES + 1 - len(VANILLA_NODES))]
    clump = _ped(nodes)
    assert len(nodes) == MAX_BONES + 1
    assert _has(check_skin_clump(clump)[0], "C05")


def test_c06_bone_count_must_equal_node_count():
    clump = _ped()
    skin = clump.geometries[0].skin
    skin.num_bones = 31
    skin.bone_matrices = skin.bone_matrices[:31]
    assert _has(check_skin_clump(clump)[0], "C06")


def test_c07_zero_bones_is_fatal():
    clump = _ped()
    skin = clump.geometries[0].skin
    skin.num_bones = 0
    skin.bone_matrices = []
    assert _has(check_skin_clump(clump)[0], "C07")


def test_c08_all_zero_weights_on_last_atomic_warns():
    clump = _ped()
    skin = clump.geometries[0].skin
    skin.bone_weights[0] = (0.0, 0.0, 0.0, 0.0)
    fatal, warn = check_skin_clump(clump)
    assert fatal == []
    assert _has(warn, "C08")


def test_c09_weight_sum_negative_and_nan_warn():
    clump = _ped()
    skin = clump.geometries[0].skin
    skin.bone_weights[0] = (0.7, 0.0, 0.0, 0.0)
    skin.bone_weights[1] = (1.2, -0.2, 0.0, 0.0)
    skin.bone_weights[2] = (float('nan'), 0.0, 0.0, 0.0)
    fatal, warn = check_skin_clump(clump)
    assert fatal == []
    assert sum(1 for w in warn if "C09" in w) == 3


def test_c10_bone_index_past_num_bones_warns():
    clump = _ped()
    skin = clump.geometries[0].skin
    skin.bone_indices[0] = (40, 0, 0, 0)
    assert _has(check_skin_clump(clump)[1], "C10")


def test_c11_c13_max_weights_range():
    for bad in (0, 5):
        clump = _ped()
        clump.geometries[0].skin.max_weights = bad
        assert _has(check_skin_clump(clump)[0], "C11/C13"), bad
    for ok in (1, 4):
        clump = _ped()
        clump.geometries[0].skin.max_weights = ok
        assert not _has(check_skin_clump(clump)[0], "C11/C13"), ok


def test_c11_empty_used_list_is_fatal():
    clump = _ped()
    skin = clump.geometries[0].skin
    skin.bones_used = []
    skin.num_used = 0
    assert _has(check_skin_clump(clump)[0], "C11")


def test_used_list_must_cover_referenced_bones():
    clump = _ped()
    skin = clump.geometries[0].skin
    skin.bone_indices[0] = (5, 0, 0, 0)  # bone 5 weighted but not listed
    fatal, warn = check_skin_clump(clump)
    assert fatal == []
    assert _has(warn, "не входят в список")
    skin.bones_used = [1, 5]
    skin.num_used = 2
    assert check_skin_clump(clump) == ([], [])


def test_c15_more_than_256_nodes_is_fatal():
    nodes = VANILLA_NODES + [(1000 + i, 0) for i in range(257 - len(VANILLA_NODES))]
    assert _has(check_skin_clump(_ped(nodes))[0], "C15")


def test_c16_table_on_clump_root_is_fatal():
    clump = _ped()
    clump.frames[0].hanim = _table(clump)
    clump.frames[1].hanim = HAnimData(bone_id=0)
    assert _has(check_skin_clump(clump)[0], "C16")


def test_c17_trailing_pop_is_allowed_but_early_underflow_is_fatal():
    # Vanilla layout: last node pops an empty stack → clean.
    assert not _has(check_skin_clump(_ped())[0], "C17")
    # Pop on the second node with nodes to follow → fatal.
    nodes = list(VANILLA_NODES)
    nodes[1] = (1, 1)
    assert _has(check_skin_clump(_ped(nodes))[0], "C17")


def test_c17_push_depth_limit():
    nodes = list(VANILLA_NODES)
    pushes = [(500 + i, 2) for i in range(MAX_PUSH_DEPTH + 1)]
    nodes = nodes[:1] + pushes + nodes[1:]
    assert _has(check_skin_clump(_ped(nodes))[0], "C17")


def test_c18_duplicate_node_ids_warn():
    nodes = list(VANILLA_NODES)
    nodes[6] = (5, 0)  # second node with id 5; id 6 is only conditional
    fatal, warn = check_skin_clump(_ped(nodes))
    assert _has(warn, "C18")


def test_c19_node_index_must_match_position():
    clump = _ped()
    _table(clump).bones[3].index = 7
    assert _has(check_skin_clump(clump)[1], "C19")


def test_c20_always_used_bone_missing_is_fatal():
    nodes = [n for n in VANILLA_NODES if n[0] != 24]  # L Hand
    assert _has(check_skin_clump(_ped(nodes))[0], "C20")


def test_c20_conditional_bone_missing_is_warning_only():
    # Vanilla cutscene skins ship without the facial bones 6/7/8.
    nodes = [n for n in VANILLA_NODES if n[0] not in (6, 7, 8)]
    nodes = [(b, 0 if b == 5 else t) for b, t in nodes]  # keep push/pop balanced
    fatal, warn = check_skin_clump(_ped(nodes))
    assert not _has(fatal, "C20")
    assert _has(warn, "C20")


def test_always_and_conditional_sets_are_disjoint_and_complete():
    assert not (ALWAYS_USED_BONE_IDS & CONDITIONAL_BONE_IDS)
    assert ALWAYS_USED_BONE_IDS | CONDITIONAL_BONE_IDS == {b for b, _ in VANILLA_NODES}


def test_c21_hanim_version_is_fatal():
    clump = _ped()
    clump.frames[3].hanim.version = 0x101
    assert _has(check_skin_clump(clump)[0], "C21")


def test_c23_size_mismatches_are_fatal():
    clump = _ped()
    clump.geometries[0].skin.bone_indices.pop()
    assert _has(check_skin_clump(clump)[0], "C23")
    clump = _ped()
    clump.geometries[0].skin.num_used = 3
    assert _has(check_skin_clump(clump)[0], "C23")


def test_c25_singular_or_nan_matrix_warns():
    clump = _ped()
    skin = clump.geometries[0].skin
    skin.bone_matrices[2] = ((0.0,) * 4,) * 4
    skin.bone_matrices[3] = ((float('nan'), 0.0, 0.0, 0.0),) + IDENTITY[1:]
    fatal, warn = check_skin_clump(clump)
    assert fatal == []
    assert sum(1 for w in warn if "C25" in w) == 2


def test_c26_two_node_tables_warn():
    clump = _ped()
    clump.frames[2].hanim.bones = list(_table(clump).bones)
    assert _has(check_skin_clump(clump)[1], "C26")


def test_w1_long_frame_name_is_fatal_in_lint():
    clump = _ped()
    clump.frames[5].name = "x" * (FRAME_NAME_MAX + 1)
    assert _has(check_skin_clump(clump)[0], "24-байт")


def test_w1_long_frame_name_without_name_chunk_is_not_flagged():
    # write_name=False → writer emits no FRAME_NAME chunk, so nothing to overflow.
    clump = _ped()
    clump.frames[5].name = "x" * (FRAME_NAME_MAX + 1)
    clump.frames[5].write_name = False
    assert not _has(check_skin_clump(clump)[0], "24-байт")


# ── writer regressions ───────────────────────────────────────────

def _find_chunk(blob, chunk_type):
    """Header of the first chunk of ``chunk_type`` (type, size, lib)."""
    off = 0
    while off + 12 <= len(blob):
        t, sz, _ = unpack_from('<III', blob, off)
        if t == chunk_type:
            return off, sz
        off += 4
    raise AssertionError("chunk not found")


def test_w1_frame_name_chunk_is_strlen_bytes_no_padding():
    blob = write_dff(_ped())
    off, size = _find_chunk(blob, CHUNK_FRAME_NAME)
    assert size == len("csplay")
    assert blob[off + 12:off + 12 + size] == b"csplay"
    # Names that used to pad to a 24-byte chunk stay exactly strlen.
    clump = _ped()
    clump.frames[0].name = "ws_roadwarning_01_L0"     # 20 chars
    blob = write_dff(clump)
    off, size = _find_chunk(blob, CHUNK_FRAME_NAME)
    assert size == 20
    assert read_dff(blob).frames[0].name == "ws_roadwarning_01_L0"


def test_w1_frame_name_longer_than_23_is_rejected():
    clump = _ped()
    clump.frames[0].name = "Para_Harness_SpineTrace_"  # 24 chars
    with pytest.raises(DffLimitError):
        write_dff(clump)
    clump.frames[0].name = "Para_Harness_SpineTrace"   # 23 chars — vanilla has this
    write_dff(clump)


def test_w2_root_only_weights_keep_sa_layout():
    # Mesh weighted 100 % to bone 0: used list = [0], num_used = 1, and the
    # Skin PLG is the RW ≥ 3.5 layout (no pad before matrices, 12-byte
    # trailer) — 164 bytes of payload for 2 bones / 3 vertices.
    clump = _ped()
    skin = clump.geometries[0].skin
    skin.num_bones = 2
    skin.bone_matrices = [IDENTITY, IDENTITY]
    skin.bone_indices = [(0, 0, 0, 0)] * 3
    skin.bone_weights = [(1.0, 0.0, 0.0, 0.0)] * 3
    skin.bones_used = [0]
    skin.num_used = 1
    payload = skin.to_bytes(0, 0x36003)
    assert len(payload) - 12 == 4 + 1 + 3 * 4 + 3 * 16 + 2 * 64 + 12
    # Even a (foreign) num_used == 0 skin must not flip to the 3.4 layout.
    skin.bones_used = []
    skin.num_used = 0
    payload = skin.to_bytes(0, 0x36003)
    assert len(payload) - 12 == 4 + 0 + 3 * 4 + 3 * 16 + 2 * 64 + 12
    # Pre-3.5 files (III/VC) get the RW 3.3 layout: u32 numBones header,
    # NO used-bone list even when one is populated, 0xDEADDEAD before
    # every matrix, no trailer.
    skin.bones_used = [0]
    skin.num_used = 1
    payload = skin.to_bytes(0, 0x33002)
    assert len(payload) - 12 == 4 + 0 + 3 * 4 + 3 * 16 + 2 * 68
    assert payload[12:16] == bytes([2, 0, 0, 0])
    assert unpack_from('<I', payload, 12 + 4 + 3 * 4 + 3 * 16)[0] == 0xDEADDEAD
    assert read_dff(write_dff(_iii_clump(skin))).geometries[0].skin.num_bones == 2


def _iii_clump(skin):
    g = _geom()
    g.skin = skin
    return DffClump(version=0x33002, frames=[DffFrame(name="r", parent=-1)],
                    geometries=[g],
                    atomics=[DffAtomic(frame_index=0, geometry_index=0)])


def test_w9_more_than_65536_vertices_is_an_error():
    n = 65537
    g = DffGeometry(
        vertices=[(0.0, 0.0, 0.0)] * n,
        triangles=[Triangle(a=0, b=1, c=n - 1, material=0)],
        materials=[DffMaterial()],
        bounding_sphere=BoundingSphere(0.0, 0.0, 0.0, 1.0),
    )
    clump = DffClump(frames=[DffFrame(name="big", parent=-1)], geometries=[g],
                     atomics=[DffAtomic(frame_index=0, geometry_index=0)])
    with pytest.raises(DffLimitError):
        write_dff(clump)


def test_hanim_flags_and_keyframe_size_round_trip():
    clump = _ped()
    _table(clump).flags = 0
    _table(clump).keyframe_size = 36
    parsed = read_dff(write_dff(clump))
    h = parsed.frames[1].hanim
    assert (h.flags, h.keyframe_size) == (0, 36)
