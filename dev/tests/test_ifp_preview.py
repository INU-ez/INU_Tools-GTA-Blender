"""Tests for the interpolation math behind IFP live preview.

The frame-change handler in ``ops.ifp_import`` requires bpy and can't run
in CI. The actual blend math, however, lives in pure
``core.ifp._sample_linear_kf`` — same code path the decimator uses to
detect redundant middle keys. We test that here so a regression in
linear interp shows up before it bites preview accuracy.

A bpy-gated smoke test of ``preview_start`` / ``preview_stop`` is also
included; it skips automatically when bpy is unavailable.
"""

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.ifp import (  # noqa: E402
    KeyFrame,
    _sample_linear_kf,
)


def _kf(time, rot=(0.0, 0.0, 0.0, 1.0), trans=(0.0, 0.0, 0.0)):
    return KeyFrame(rotation=rot, translation=trans, time=time)


def test_sample_at_start_returns_first_keyframe():
    a = _kf(0.0, rot=(0.1, 0.2, 0.3, 0.9), trans=(1.0, 2.0, 3.0))
    b = _kf(1.0, rot=(0.5, 0.5, 0.5, 0.5), trans=(5.0, 6.0, 7.0))
    rot, trans = _sample_linear_kf(a, b, 0.0)
    for i in range(4):
        assert abs(rot[i] - a.rotation[i]) < 1e-6
    for i in range(3):
        assert abs(trans[i] - a.translation[i]) < 1e-6


def test_sample_at_end_returns_last_keyframe():
    a = _kf(0.0, rot=(0.1, 0.2, 0.3, 0.9), trans=(1.0, 2.0, 3.0))
    b = _kf(1.0, rot=(0.5, 0.5, 0.5, 0.5), trans=(5.0, 6.0, 7.0))
    rot, trans = _sample_linear_kf(a, b, 1.0)
    for i in range(4):
        assert abs(rot[i] - b.rotation[i]) < 1e-6
    for i in range(3):
        assert abs(trans[i] - b.translation[i]) < 1e-6


def test_sample_at_midpoint_blends_evenly():
    a = _kf(0.0, trans=(0.0, 0.0, 0.0))
    b = _kf(2.0, trans=(2.0, 4.0, 6.0))
    _, trans = _sample_linear_kf(a, b, 1.0)
    assert abs(trans[0] - 1.0) < 1e-6
    assert abs(trans[1] - 2.0) < 1e-6
    assert abs(trans[2] - 3.0) < 1e-6


def test_sample_clamps_below_start_time():
    a = _kf(0.5, trans=(1.0, 0.0, 0.0))
    b = _kf(1.5, trans=(2.0, 0.0, 0.0))
    _, trans = _sample_linear_kf(a, b, 0.0)
    assert abs(trans[0] - 1.0) < 1e-6  # clamped to first key, not extrapolated


def test_sample_clamps_above_end_time():
    a = _kf(0.5, trans=(1.0, 0.0, 0.0))
    b = _kf(1.5, trans=(2.0, 0.0, 0.0))
    _, trans = _sample_linear_kf(a, b, 5.0)
    assert abs(trans[0] - 2.0) < 1e-6


def test_sample_with_zero_span_returns_first_keyframe():
    # Two keyframes at the same time (degenerate, but possible after
    # decimation) must not divide by zero.
    a = _kf(1.0, trans=(3.0, 0.0, 0.0))
    b = _kf(1.0, trans=(7.0, 0.0, 0.0))
    _, trans = _sample_linear_kf(a, b, 1.0)
    assert abs(trans[0] - 3.0) < 1e-6


# ─────────────────────── bpy-gated wrapper smoke test ───────────────────────
# preview_start / preview_stop wire bpy.app.handlers.frame_change_post
# and read armature data — requires a real Blender Python.

@pytest.fixture
def blender_api():
    # Gate only the Blender wrappers, not the pure interpolation tests.
    # Other test modules install bpy stubs; the native runtime is required.
    pytest.importorskip('_bpy', reason='IFP preview smoke tests require the native Blender runtime')
    return pytest.importorskip("bpy")


def test_preview_is_inactive_by_default(blender_api):
    from INU_tools.ops.ifp_import import preview_is_active
    # Fresh process or after preview_stop — must report inactive.
    # If a previous test left preview running, that's a leak we want
    # surfaced here.
    if preview_is_active():
        from INU_tools.ops.ifp_import import preview_stop
        preview_stop()
    assert preview_is_active() is False


def test_preview_start_rejects_non_armature(blender_api):
    from INU_tools.ops.ifp_import import preview_start
    ok, msg = preview_start(None, "WALK")
    assert ok is False
    assert "armature" in msg.lower()


def test_preview_start_rejects_unknown_anim(blender_api):
    from INU_tools.ops.ifp_import import preview_start
    bpy = blender_api
    arm = bpy.data.objects.new("PreviewArm", bpy.data.armatures.new("PreviewArmData"))
    try:
        ok, msg = preview_start(arm, "ANIM_THAT_DOES_NOT_EXIST")
        assert ok is False
        assert "not in ifp cache" in msg.lower()
    finally:
        bpy.data.objects.remove(arm, do_unlink=True)
