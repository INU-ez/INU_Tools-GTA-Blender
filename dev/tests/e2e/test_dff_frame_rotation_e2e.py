"""E2E regression test: DFF frame rotation convention on export.

A RenderWare frame stores its rotation as three row vectors ``right``,
``up``, ``at`` — the axes of the frame's local space, i.e. the COLUMNS of
Blender's ``matrix_local.to_3x3()``. ``_live_frame_transform`` used to
write the Blender matrix untransposed, so every frame with a
non-symmetric rotation was stored as its inverse: a child authored as
Rz(+90) came back (in game and on re-import) as Rz(-90).

Two checks, no external assets needed:

1. Byte-level: export a parent + child rotated Rz(+90) and read the
   FrameList chunk directly — ``right`` must equal the child's local
   X axis (0, 1, 0), not (0, -1, 0).
2. Round-trip: re-import the file with ``import_dff`` and compare the
   child's ``matrix_local`` with the original.
"""

from __future__ import annotations

import math
import struct

import bpy
import mathutils
import pytest


CHUNK_FRAMELIST = 0x0E
CHUNK_STRUCT = 0x01
FRAME_SIZE = 9 * 4 + 3 * 4 + 4 + 4


def _read_frames(data: bytes):
    """Return [(rotation9, position3, parent), ...] from the first
    FrameList chunk. Minimal parser — mirrors the on-disk layout only."""
    i = 0
    while i + 12 <= len(data):
        cid, size, _ver = struct.unpack_from("<III", data, i)
        body = i + 12
        if cid == CHUNK_FRAMELIST:
            sid, _ssize, _ = struct.unpack_from("<III", data, body)
            assert sid == CHUNK_STRUCT
            count = struct.unpack_from("<I", data, body + 12)[0]
            off = body + 16
            frames = []
            for _ in range(count):
                rot = struct.unpack_from("<9f", data, off)
                pos = struct.unpack_from("<3f", data, off + 36)
                parent = struct.unpack_from("<i", data, off + 48)[0]
                frames.append((rot, pos, parent))
                off += FRAME_SIZE
            return frames
        # descend into containers (clump) / skip leaves
        if cid in (0x10,):
            i = body
        else:
            i = body + size
    raise AssertionError("no FrameList chunk found")


def _build_scene():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    root = bpy.context.active_object
    root.name = "root"
    bpy.ops.mesh.primitive_cube_add(size=0.5)
    child = bpy.context.active_object
    child.name = "child"
    child.parent = root
    child.matrix_parent_inverse.identity()
    child.location = (2.0, 0.0, 0.0)
    child.rotation_euler = (0.0, 0.0, math.radians(90.0))
    for o in (root, child):
        o["dff_frame_write_name"] = True
    bpy.context.view_layer.update()
    return root, child


def _close(a, b, eps=1e-5):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


def test_export_writes_frame_axes_as_rows(tmp_path, inu_ops):
    root, child = _build_scene()
    expected_right = tuple(child.matrix_local.to_3x3() @ mathutils.Vector((1, 0, 0)))
    expected_up = tuple(child.matrix_local.to_3x3() @ mathutils.Vector((0, 1, 0)))
    assert _close(expected_right, (0.0, 1.0, 0.0))  # sanity: Rz(+90) maps X -> +Y

    path = str(tmp_path / "frame_rot.dff")
    inu_ops.dff_export.export_dff(path, [root, child])

    frames = _read_frames(open(path, "rb").read())
    child_frames = [f for f in frames if f[2] == 0 and _close(f[1], (2.0, 0.0, 0.0))]
    assert child_frames, f"child frame not found in {frames!r}"
    rot, _pos, _parent = child_frames[0]
    right, up, at = rot[0:3], rot[3:6], rot[6:9]
    assert _close(right, expected_right), f"right={right} expected {expected_right} (transposed export?)"
    assert _close(up, expected_up), f"up={up} expected {expected_up}"
    assert _close(at, (0.0, 0.0, 1.0))


def test_export_import_round_trip_keeps_rotation(tmp_path, inu_ops):
    root, child = _build_scene()
    original = child.matrix_local.copy()
    path = str(tmp_path / "frame_rot_rt.dff")
    inu_ops.dff_export.export_dff(path, [root, child])

    bpy.ops.wm.read_homefile(use_empty=True)
    inu_ops.dff_import.import_dff(filepath=path, context=bpy.context)
    bpy.context.view_layer.update()

    imported = [o for o in bpy.data.objects if o.type == "MESH" and o.parent is not None]
    assert imported, "re-import produced no parented child object"
    got = imported[0].matrix_local
    for r in range(3):
        for c in range(3):
            assert abs(got[r][c] - original[r][c]) < 1e-4, (
                f"matrix_local[{r}][{c}] = {got[r][c]:.4f}, expected {original[r][c]:.4f}"
            )
