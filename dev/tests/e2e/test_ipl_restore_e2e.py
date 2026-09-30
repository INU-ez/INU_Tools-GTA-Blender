"""E2E: Restore coords / Sync from IPL put the object on the row in WORLD space.

The IPL row is written from ``matrix_world`` (``_ipl_entry_from_obj``), but
``map_link.apply_inst_transform`` used to set the LOCAL ``location`` /
``rotation_quaternion`` (and force rotation_mode = QUATERNION): a model under
a moved / rotated parent landed at ``parent @ row``, not on the row.

No external assets needed.
"""

from __future__ import annotations

import importlib
import math
from types import SimpleNamespace

import bpy
import pytest
from mathutils import Quaternion


@pytest.fixture
def ml(inu):
    return importlib.import_module(f"{inu.__name__}.ops.map_link")


def _mesh(name):
    o = bpy.data.objects.new(name, bpy.data.meshes.new(name))
    bpy.context.scene.collection.objects.link(o)
    return o


def _empty(name):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    return o


def _row(pos, obj_quat):
    """Row values for an object that should end up at *pos* with world
    rotation *obj_quat* (the IPL stores the conjugate)."""
    q = Quaternion(obj_quat)
    return SimpleNamespace(pos_x=pos[0], pos_y=pos[1], pos_z=pos[2],
                           rot_x=-q.x, rot_y=-q.y, rot_z=-q.z, rot_w=q.w)


def _rz(deg):
    return Quaternion((0.0, 0.0, 1.0), math.radians(deg))


def _assert_on_row(inu, obj, row, eps=1e-4):
    bpy.context.view_layer.update()
    t = obj.matrix_world.translation
    assert abs(t.x - row.pos_x) < eps and abs(t.y - row.pos_y) < eps \
        and abs(t.z - row.pos_z) < eps, (tuple(t), row)
    e = inu._ipl_entry_from_obj(obj)
    dot = (e.rot_x * row.rot_x + e.rot_y * row.rot_y + e.rot_z * row.rot_z
           + e.rot_w * row.rot_w)
    assert abs(abs(dot) - 1.0) < 1e-5, (e, row)


def test_child_under_moved_rotated_empty(inu, ml):
    e = _empty("parent")
    e.location = (100.0, 50.0, 0.0)
    e.rotation_euler = (0.0, 0.0, math.radians(30.0))
    bpy.context.view_layer.update()
    c = _mesh("child")
    c.parent = e
    c.matrix_parent_inverse = e.matrix_world.inverted()   # as Ctrl+P
    e.location = (120.0, 40.0, 5.0)
    e.rotation_euler = (0.0, 0.0, math.radians(75.0))
    bpy.context.view_layer.update()
    row = _row((10.0, -20.0, 3.0), _rz(90.0))
    ml.apply_inst_transform(c, row)
    _assert_on_row(inu, c, row)


def test_rotation_mode_and_scale_kept(inu, ml):
    o = _mesh("house")
    o.rotation_mode = 'XYZ'
    o.scale = (2.0, 2.0, 2.0)
    bpy.context.view_layer.update()
    row = _row((1.0, 2.0, 3.0), _rz(45.0))
    ml.apply_inst_transform(o, row)
    _assert_on_row(inu, o, row)
    assert o.rotation_mode == 'XYZ'
    assert all(abs(s - 2.0) < 1e-5 for s in o.matrix_world.to_scale())


def test_mirrored_object_stays_mirrored(inu, ml):
    o = _mesh("mirror")
    o.scale = (-1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    row = _row((5.0, 0.0, 0.0), _rz(60.0))
    ml.apply_inst_transform(o, row)
    _assert_on_row(inu, o, row)
    assert o.matrix_world.is_negative


def test_unnormalized_row_quat_keeps_unit_scale(inu, ml):
    o = _mesh("lamp")
    row = SimpleNamespace(pos_x=0.0, pos_y=0.0, pos_z=0.0,
                          rot_x=0.0, rot_y=0.0, rot_z=0.7071, rot_w=0.7071)
    ml.apply_inst_transform(o, row)
    bpy.context.view_layer.update()
    assert all(abs(s - 1.0) < 1e-6 for s in o.scale), tuple(o.scale)


@pytest.mark.parametrize("order", ["child_first", "parent_first"])
def test_pull_moves_parent_and_child_onto_rows(inu, ml, tmp_path,
                                               monkeypatch, order):
    """Both linked: the child is placed after its parent, whatever the order
    of the list — otherwise it would move along with the parent."""
    mapsync = importlib.import_module(f"{inu.__name__}.core.mapsync")
    p = tmp_path / "map.ipl"
    p.write_bytes((
        "inst\r\n"
        "100, house, 0, 100.0, 50.0, 0.0, 0, 0, -0.258819, 0.965926, -1\r\n"
        "101, porch, 0, 103.0, 52.0, 1.0, 0, 0, -0.707107, 0.707107, -1\r\n"
        "end\r\n").encode())
    doc = mapsync.IplDoc.load(str(p))
    par = _mesh("house")
    ch = _mesh("porch")
    ch.parent = par
    ch.location = (1.0, 0.0, 0.0)
    for o, i, mid in ((par, 0, 100), (ch, 1, 101)):
        o.inu.model_id = mid
        ml.stamp_ipl(o, ml.norm(str(p)), doc.rows[i].inst, -1, fresh=True)
    bpy.context.view_layer.update()
    monkeypatch.setattr(ml, "model_type", lambda o: ("DFF", o.name))
    objs = [ch, par] if order == "child_first" else [par, ch]
    rep = ml.ipl_pull(bpy.context, objs, [], move=True)
    assert rep.counts.get("synced") == 2, rep.counts
    for o, i in ((par, 0), (ch, 1)):
        _assert_on_row(inu, o, doc.rows[i].inst)
