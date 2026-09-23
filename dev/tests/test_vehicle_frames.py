# check_vehicle_names must agree with what gta_sa.exe actually does.
#
# The reference behaviour was read out of the binary and then confirmed by
# running a reimplementation in the live game: the engine matches vehicle
# dummies by name once, at load, with _stricmp; GetWheelPosn then dereferences
# the frame it found with no null check, so a missing wheel dummy faults.
#
# frame_hierarchy imports bpy at module level, so pull just the function out
# by AST rather than importing the module.

import ast
import io
import os

MODULE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "INU_tools", "ops", "frame_hierarchy.py")

WANTED = {"VEHICLE_FATAL", "VEHICLE_REQUIRED", "VEHICLE_OPTIONAL",
          "BIKE_REQUIRED", "_DUP_SUFFIX", "check_vehicle_names"}


def _load():
    """Exec only the constants and the audit function, with no bpy."""
    tree = ast.parse(io.open(MODULE, encoding="utf-8").read())
    keep = [n for n in tree.body if isinstance(n, ast.Import)
            and any(a.name == "re" for a in n.names)]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in WANTED:
            keep.append(node)
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(t in WANTED for t in targets):
                keep.append(node)

    ns = {"T": lambda s: s}   # the module's T() is not in the AST cut
    exec(compile(ast.Module(body=keep, type_ignores=[]), MODULE, "exec"), ns)
    return ns


NS = _load()
check = NS["check_vehicle_names"]

CAR_OK = ["chassis", "chassis_dummy",
          "wheel_lf_dummy", "wheel_rf_dummy", "wheel_lb_dummy", "wheel_rb_dummy",
          "door_lf_dummy", "bonnet_dummy"]


def test_healthy_car_passes():
    fatal, warn = check(CAR_OK)
    assert fatal == [], fatal
    assert warn == [], warn


def test_vanilla_wheel_mesh_frame_is_not_flagged():
    # Every stock SA car carries a frame named exactly "wheel" — the wheel
    # geometry the engine clones onto wheel_*_dummy. Flagging it made the
    # validator warn on untouched vanilla exports.
    fatal, warn = check(CAR_OK + ["wheel"])
    assert fatal == [], fatal
    assert warn == [], warn


def test_wheel_without_side_is_still_flagged():
    _, warn = check(CAR_OK + ["wheel_spare"])
    assert len(warn) == 1 and warn[0].startswith("wheel_spare")


def test_missing_wheel_is_fatal():
    names = [n for n in CAR_OK if n != "wheel_lb_dummy"]
    fatal, _ = check(names)
    assert len(fatal) == 1
    assert fatal[0].startswith("wheel_lb_dummy")


def test_casing_is_irrelevant():
    # The engine compares with _stricmp.
    fatal, warn = check([n.upper() for n in CAR_OK])
    assert fatal == []
    assert warn == []


def test_blender_duplicate_suffix_is_fatal_and_explained():
    names = [n for n in CAR_OK if n != "wheel_rf_dummy"] + ["wheel_rf_dummy.001"]
    fatal, _ = check(names)
    assert len(fatal) == 1
    assert "wheel_rf_dummy" in fatal[0]
    assert "суффикс" in fatal[0], fatal[0]


def test_missing_chassis_dummy_is_only_a_warning():
    names = [n for n in CAR_OK if n != "chassis_dummy"]
    fatal, warn = check(names)
    assert fatal == []
    assert any(w.startswith("chassis_dummy") for w in warn), warn


def test_bike_uses_its_own_table_and_is_never_fatal():
    # Bikes never reach GetWheelPosn -- CBike has its own code -- and their
    # table is chassis_dummy / wheel_front / wheel_rear.
    fatal, warn = check(["chassis_dummy", "wheel_front", "wheel_rear"])
    assert fatal == []
    assert warn == []

    fatal, warn = check(["chassis_dummy", "wheel_front"])
    assert fatal == []
    assert any(w.startswith("wheel_rear") for w in warn), warn


def test_six_wheeler_middle_wheels_are_not_flagged():
    fatal, warn = check(CAR_OK + ["wheel_lm_dummy", "wheel_rm_dummy"])
    assert fatal == []
    assert warn == []


def test_optional_table_matches_the_engine_names():
    # These four were wrong before the binary was read: rear doors are lr/rr
    # not lb/rb, bumpers are front/rear, and the exhaust entry is exhaust_ok.
    opt = NS["VEHICLE_OPTIONAL"]
    for name in ("door_lr_dummy", "door_rr_dummy",
                 "bump_front_dummy", "bump_rear_dummy", "exhaust_ok"):
        assert name in opt, name
    for gone in ("door_lb_dummy", "door_rb_dummy",
                 "bumper_lf_dummy", "bumper_rf_dummy", "exhaust_dummy"):
        assert gone not in opt, gone


def test_fatal_set_is_exactly_the_four_wheels_getwheelposn_reads():
    # ms_wheelFrameIDs @ 0x8A7770 = {5, 7, 2, 4} -> lf, lb, rf, rb.
    assert set(NS["VEHICLE_FATAL"]) == {
        "wheel_lf_dummy", "wheel_lb_dummy", "wheel_rf_dummy", "wheel_rb_dummy"}


# ---------------------------------------------------------------------------
# Night colours without day prelight (DFF-43). The rule moved from
# dff_export._audit_night_colours into core.mapdff_lint.check_map_clump,
# which the exporter runs on every non-skinned clump.

import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(MODULE))))

from core.dff import (  # noqa: E402
    DffClump, DffFrame, DffGeometry, DffAtomic, DffMaterial, Triangle,
    BoundingSphere, RGBA, ExtraVertColors,
)
from core.mapdff_lint import check_map_clump  # noqa: E402


def _geom(prelit, extra):
    g = DffGeometry(
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        triangles=[Triangle(0, 1, 2, 0)],
        materials=[DffMaterial()],
        bounding_sphere=BoundingSphere(0.0, 0.0, 0.0, 2.0),
    )
    if prelit:
        g.prelit_colors = [RGBA()] * 3
    if extra:
        g.extra_colors = ExtraVertColors(colors=[RGBA()] * 3)
    return g


def _clump(*geoms):
    frames = [DffFrame(name="root", parent=-1)] + [
        DffFrame(name=f"g{i}", parent=0) for i in range(len(geoms))]
    return DffClump(frames=frames, geometries=list(geoms),
                    atomics=[DffAtomic(i + 1, i) for i in range(len(geoms))])


def _night_warnings(clump):
    _fatal, warn = check_map_clump(clump)
    return [w for w in warn if "DFF-43" in w]


def test_night_without_day_is_warned():
    warn = _night_warnings(_clump(_geom(prelit=False, extra=True)))
    assert len(warn) == 1 and "prelight" in warn[0], warn


def test_night_with_day_is_fine():
    assert _night_warnings(_clump(_geom(prelit=True, extra=True))) == []


def test_day_only_and_no_colours_are_fine():
    assert _night_warnings(_clump(_geom(prelit=True, extra=False),
                                  _geom(prelit=False, extra=False))) == []


def test_reports_the_geometry_index():
    warn = _night_warnings(_clump(_geom(True, False), _geom(False, True)))
    assert len(warn) == 1 and warn[0].startswith("геометрия #1"), warn
