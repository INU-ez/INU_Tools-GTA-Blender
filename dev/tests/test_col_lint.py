"""core.col_lint — pre-write audit of a ColModel against what the SA
collision loaders and CCollision assume without checking (COL-03..COL-25
in E:\\RE\\addon_check\\col_path.md), plus regressions for the COL writer /
reader fixes from the same read: W3 surface clamp keyed on the target
game (not the COL version), W6 face groups preserved, W11 a truncated
model stops the read instead of raising.

Every rule gets a passing and a failing case built from synthetic core
structures. Pure Python — no Blender required.
"""

from pathlib import Path
from struct import pack
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.col import (  # noqa: E402
    ColModel, ColFace, ColSphere, ColBox, Bounds, Vec3, Surface, FaceGroup,
    read_col, write_col, COL_READ_WARNINGS,
)
from core.col_lint import check_col, check_col_models  # noqa: E402


def _model(name="crate", version=3, nv=4):
    verts = [Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(1, 1, 1)][:nv]
    m = ColModel(
        version=version, model_name=name,
        bounds=Bounds(center=Vec3(0.5, 0.5, 0.5), radius=1.0,
                      bb_min=Vec3(0, 0, 0), bb_max=Vec3(1, 1, 1)),
        vertices=verts,
        faces=[ColFace(0, 1, 2, Surface(material=4)),
               ColFace(1, 3, 2, Surface(material=4))],
    )
    return m


def _has(items, tag):
    return any(tag in s for s in items)


def test_clean_model_passes():
    fatal, warn = check_col(_model())
    assert fatal == [] and warn == []


# ── names / counts ───────────────────────────────────────────────

def test_name_rules():
    fatal, _ = check_col(_model(name="a" * 22))
    assert _has(fatal, "COL-03")
    fatal, _ = check_col(_model(name="a" * 21))
    assert not _has(fatal, "COL-03")
    _, warn = check_col(_model(name=""))
    assert _has(warn, "COL-25")


def test_face_count_limit():
    m = _model()
    m.faces = [ColFace(0, 1, 2, Surface())] * 32768
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-11")
    m.faces = [ColFace(0, 1, 2, Surface())] * 32767
    fatal, _ = check_col(m)
    assert not _has(fatal, "COL-11")


def test_vertex_count_limit():
    m = _model()
    m.vertices = [Vec3(0, 0, 0)] * 65537
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-10")


def test_primitive_count_limit():
    m = _model()
    m.spheres = [ColSphere(Vec3(0.5, 0.5, 0.5), 0.1, Surface())] * 32768
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-12")


# ── faces ────────────────────────────────────────────────────────

def test_face_index_out_of_range_fatal():
    m = _model()
    m.faces[0] = ColFace(0, 1, 9, Surface())
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-09")


def test_coordinate_limit():
    m = _model()
    m.vertices[3] = Vec3(300.0, 0, 0)
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-13")
    m.vertices[3] = Vec3(255.5, 0, 0)
    fatal, warn = check_col(m)
    assert not _has(fatal, "COL-13") and _has(warn, "COL-13")
    # COL1 stores floats, but LoadCollisionModel converts to int16/128 too.
    m2 = _model(version=1)
    m2.vertices[3] = Vec3(300.0, 0, 0)
    fatal, _ = check_col(m2)
    assert _has(fatal, "COL-13")


def test_plane_distance_limit():
    # A face whose plane sits > 256 m from the origin although every
    # coordinate stays inside ±255.99: a diagonal face near a corner.
    m = ColModel(
        version=3, model_name="far",
        bounds=Bounds(center=Vec3(250, 250, 250), radius=10.0,
                      bb_min=Vec3(245, 245, 245), bb_max=Vec3(255, 255, 255)),
        vertices=[Vec3(255, 250, 250), Vec3(250, 255, 250), Vec3(250, 250, 255)],
        faces=[ColFace(0, 1, 2, Surface())],
    )
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-14")
    fatal, _ = check_col(_model())
    assert not _has(fatal, "COL-14")


def test_surface_id_limit():
    m = _model()
    m.faces[0].surface.material = 179
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-18")
    m.faces[0].surface.material = 178
    fatal, _ = check_col(m)
    assert not _has(fatal, "COL-18")
    m.boxes = [ColBox(Vec3(0, 0, 0), Vec3(1, 1, 1), Surface(material=200))]
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-18")


def test_shadow_mesh_rules():
    m = _model()
    m.shadow_vertices = [Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)]
    m.shadow_faces = [ColFace(0, 1, 2, Surface())]
    fatal, warn = check_col(m)
    assert fatal == [] and warn == []
    m.shadow_faces = [ColFace(0, 1, 5, Surface())]
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-22")
    m.shadow_vertices = []
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-22")
    m.shadow_faces = []
    m.shadow_vertices = [Vec3(0, 0, 0)]
    _, warn = check_col(m)
    assert _has(warn, "COL-21")


# ── face groups ──────────────────────────────────────────────────

def test_face_group_rules():
    m = _model()
    m.face_groups = [FaceGroup(Vec3(0, 0, 0), Vec3(1, 1, 1), 0, 1)]
    fatal, warn = check_col(m)
    assert fatal == [] and warn == []
    m.face_groups = [FaceGroup(Vec3(0, 0, 0), Vec3(1, 1, 1), 0, 5)]
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-16")
    m.face_groups = [FaceGroup(Vec3(0, 0, 0), Vec3(1, 1, 1), 0, 0)]
    _, warn = check_col(m)
    assert _has(warn, "COL-16")           # face 1 not covered
    m.face_groups = [FaceGroup(Vec3(0, 0, 0), Vec3(0.5, 0.5, 0.5), 0, 1)]
    _, warn = check_col(m)
    assert _has(warn, "COL-17")
    m.face_groups = [FaceGroup(Vec3(0, 0, 0), Vec3(1, 1, 1), 1, 0)]
    _, warn = check_col(m)
    assert _has(warn, "COL-16")           # first > last


# ── bounds ───────────────────────────────────────────────────────

def test_bounds_rules():
    m = _model()
    m.bounds.radius = 0.0
    fatal, _ = check_col(m)
    assert _has(fatal, "COL-23")
    m = _model()
    m.bounds.bb_max = Vec3(0.5, 1, 1)
    _, warn = check_col(m)
    assert _has(warn, "COL-23")
    m = _model()
    m.bounds.radius = 0.5
    _, warn = check_col(m)
    assert _has(warn, "COL-23")
    m = _model()
    m.spheres = [ColSphere(Vec3(0.5, 0.5, 0.5), 3.0, Surface())]
    _, warn = check_col(m)
    assert _has(warn, "COL-23")


def test_duplicate_names_warn():
    _, warn = check_col_models([_model("a"), _model("A")])
    assert _has(warn, "COL-24")
    _, warn = check_col_models([_model("a"), _model("b")])
    assert not _has(warn, "COL-24")


# ── writer / reader regressions ──────────────────────────────────

def test_w3_clamp_keyed_on_target_game_not_version():
    """SA ships COL2 archives with SA surface IDs (seabed, levelxre)."""
    m = _model(version=2)
    m.faces[0].surface.material = 99
    parsed = read_col(write_col([m]))[0]
    assert parsed.faces[0].surface.material == 99          # no target → untouched
    m = _model(version=2)
    m.faces[0].surface.material = 99
    parsed = read_col(write_col([m], target_game='SA'))[0]
    assert parsed.faces[0].surface.material == 99
    m = _model(version=2)
    m.faces[0].surface.material = 99
    parsed = read_col(write_col([m], target_game='VC'))[0]
    assert parsed.faces[0].surface.material == 0           # VC table ends at 85


def test_w6_face_groups_round_trip():
    m = _model()
    m.face_groups = [FaceGroup(Vec3(0, 0, 0), Vec3(1, 1, 1), 0, 0),
                     FaceGroup(Vec3(0, 0, 0), Vec3(1, 1, 1), 1, 1)]
    blob = write_col([m])
    parsed = read_col(blob)[0]
    assert parsed.flags & 8
    assert [(g.first, g.last) for g in parsed.face_groups] == [(0, 0), (1, 1)]
    assert abs(parsed.face_groups[1].bb_max.z - 1.0) < 1e-6
    assert [(f.a, f.b, f.c) for f in parsed.faces] == [(0, 1, 2), (1, 3, 2)]
    # no groups → flag clear, no table
    parsed = read_col(write_col([_model()]))[0]
    assert not (parsed.flags & 8) and parsed.face_groups == []


def test_w11_truncated_model_stops_read_with_warning():
    good = write_col([_model("ok")])
    bad = write_col([_model("broken")])
    blob = good + bad[:len(bad) - 20]            # cut the second model short
    models = read_col(blob)
    assert [m.model_name for m in models] == ["ok"]
    assert COL_READ_WARNINGS and "broken" in COL_READ_WARNINGS[0]


def test_w11_col1_garbage_count_stops_read():
    m = _model("v1", version=1)
    blob = bytearray(write_col([m]))
    # vertex count sits after spheres(4) + unknown(4) + boxes(4) in the body
    off = 32 + 40 + 4 + 4 + 4
    blob[off:off + 4] = pack('<I', 0x7FFFFFFF)
    models = read_col(bytes(blob))
    assert models == [] and COL_READ_WARNINGS
