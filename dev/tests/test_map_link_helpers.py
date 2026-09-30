"""ops/map_link helpers that need no live Blender: snapping a placement
onto its own file row before Add (float32 noise, quaternion sign).

map_link imports bpy and ``from .. import T`` at module level, so it is
loaded against a stub bpy / INU_tools package, isolated: sys.modules is
put back afterwards (neighbour tests install their own stubs)."""

from pathlib import Path
import copy
import math
import struct
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.ipl import IplInstance  # noqa: E402
from core.mapsync import Anchor, IplDoc  # noqa: E402


def _load_map_link():
    def _is_ours(name):
        return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))

    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for key in saved:
        del sys.modules[key]
    try:
        sys.modules['bpy'] = types.ModuleType('bpy')
        pkg = types.ModuleType('INU_tools')
        pkg.__path__ = [str(ROOT / 'INU_tools')]
        pkg.T = lambda s, *_a, **_kw: s
        sys.modules['INU_tools'] = pkg
        import importlib
        return importlib.import_module('INU_tools.ops.map_link')
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)


ml = _load_map_link()


def _f32(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


SA = ("inst\n"
      "4002, LAn2_skyscrapr1, 0, 2233.8032, -1117.8828, 102.0391, "
      "0, 0, -0.7071068, -0.7071068, 1\n"
      "4003, LODn2_skyscrapr1, 0, 2233.8032, -1117.8828, 102.0391, "
      "0, 0, -0.7071068, -0.7071068, -1\n"
      "end\n")


def _anchor(row):
    """What the object holds: ipl_last_pos / _rot are float32 props."""
    a = Anchor.of(row)
    return Anchor(a.model_id, a.model_name, tuple(_f32(v) for v in a.pos),
                  tuple(_f32(v) for v in a.rot))


def _scene_inst(row, dx=0.0, rot=None):
    """_ipl_entry_from_obj of an untouched imported object: float32 position,
    quaternion from the matrix — w ≥ 0, float32 noise."""
    q = rot or (0.0, 0.0, _f32(0.7071068) + 3e-8, _f32(0.7071068) - 3e-8)
    return IplInstance(
        model_id=row.model_id, model_name=row.model_name,
        interior=row.interior,
        pos_x=_f32(_f32(row.pos_x) + dx), pos_y=_f32(row.pos_y),
        pos_z=_f32(row.pos_z),
        rot_x=q[0], rot_y=q[1], rot_z=q[2], rot_w=q[3],
        lod_index=1)


def _add(src, dinst, anchor, *, game='SA', lod_of=None):
    """ipl_write for one object, by hand (the call site in ops/map_link.py
    ipl_write needs live objects): snap to the anchor's row, LOD from the
    snapped values (as lod_inst_for / the IDE-LOD branch), place, commit."""
    doc = IplDoc.from_text(src)
    i = doc.find(anchor)
    if i >= 0 and doc.rows[i].inst is not None:
        ml._snap_to_row(dinst, doc.rows[i].inst)
    lod = None
    if lod_of is not None:
        lod = copy.copy(dinst)
        lod.model_id, lod.model_name = lod_of
        lod.lod_index = -1
    ed = doc.editor(game=game)
    res = ed.place('obj', dinst, anchor=anchor, lod=lod)
    text = ed.commit().to_text()
    return res, text


def test_untouched_object_leaves_file_byte_exact():
    row = IplDoc.from_text(SA).rows[0].inst
    dinst = _scene_inst(row)
    res, text = _add(SA, dinst, _anchor(row), lod_of=(4003, 'LODn2_skyscrapr1'))
    assert (res.action, res.lod_action) == ('unchanged', 'unchanged')
    assert text == SA
    # the row's own full-precision values, sign of the file quaternion
    assert (dinst.pos_x, dinst.pos_y, dinst.pos_z) == (2233.8032, -1117.8828,
                                                       102.0391)
    assert (dinst.rot_z, dinst.rot_w) == (-0.7071068, -0.7071068)


def test_small_move_is_written_and_anchor_follows():
    """0.5 mm: above the panel's drift threshold (1e-4) → written; the new
    anchor (float32 of the written row) is within 1e-4 of the object, so
    «координаты разошлись» doesn't stick."""
    row = IplDoc.from_text(SA).rows[0].inst
    dinst = _scene_inst(row, dx=5e-4)
    obj_x = dinst.pos_x
    res, text = _add(SA, dinst, _anchor(row), lod_of=(4003, 'LODn2_skyscrapr1'))
    assert res.action == 'update' and text != SA
    assert abs(_f32(res.inst.pos_x) - obj_x) <= ml.IPL_POS_EPS
    assert res.inst.rot_w < 0                   # rotation still snapped
    assert res.lod_inst.pos_x == res.inst.pos_x


def test_rotated_object_keeps_file_quaternion_sign():
    row = IplDoc.from_text(SA).rows[0].inst
    a = math.radians(50.0)                      # 100° about Z, w > 0
    dinst = _scene_inst(row, rot=(0.0, 0.0, math.sin(a), math.cos(a)))
    res, _text = _add(SA, dinst, _anchor(row))
    assert res.action == 'update'
    assert res.inst.rot_w < 0 and res.inst.rot_z < 0
    assert abs(res.inst.rot_w + math.cos(a)) < 1e-6
    # the position was still snapped onto the row
    assert res.inst.pos_x == 2233.8032


def test_vc_row_unchanged():
    src = ("inst\n"
           "100, house, 0, 2233.8032, -1117.8828, 102.0391, 1, 1, 1, "
           "0, 0, -0.7071068, -0.7071068\n"
           "end\n")
    row = IplDoc.from_text(src).rows[0].inst
    res, text = _add(src, _scene_inst(row), _anchor(row), game='VC')
    assert res.action == 'unchanged'
    assert text == src


def test_lod_inst_for_takes_the_snapped_model_row(monkeypatch):
    """The LOD row goes where the model's snapped row goes (full precision,
    the file's quaternion sign), not to a fresh float32 read of the object."""
    row = IplDoc.from_text(SA).rows[0].inst
    pkg = types.ModuleType('INU_tools')
    pkg._ipl_entry_from_obj = lambda _o: _scene_inst(row)
    monkeypatch.setitem(sys.modules, 'INU_tools', pkg)
    monkeypatch.setitem(sys.modules, 'INU_tools.core.ipl',
                        sys.modules['core.ipl'])
    ns = types.SimpleNamespace
    dff = ns(inu=ns(model_id=4002))
    lodo = ns(inu=ns(model_id=0, ide_last_name='LODn2_skyscrapr1'))
    dinst = _scene_inst(row)
    ml._snap_to_row(dinst, row)
    lod = ml.lod_inst_for(dff, lodo, 'n2_skyscrapr1', dinst)
    assert (lod.model_id, lod.model_name, lod.lod_index) == (
        4003, 'LODn2_skyscrapr1', -1)
    assert (lod.pos_x, lod.pos_y, lod.pos_z) == (2233.8032, -1117.8828,
                                                 102.0391)
    assert (lod.rot_z, lod.rot_w) == (-0.7071068, -0.7071068)


def test_out_of_float32_range_row_is_not_snapped():
    ref = IplInstance(model_id=1, model_name='a', pos_x=1e39, rot_w=-1.0)
    inst = IplInstance(model_id=1, model_name='a', pos_x=5.0, rot_w=1.0)
    ml._snap_to_row(inst, ref)                  # no exception
    assert inst.pos_x == 5.0
    assert inst.rot_w == -1.0                   # sign/rotation still snapped


# ── III/VC Del of a LOD: the row of the model standing on it ──────────

VC_TWO = ("inst\r\n"
          "100, house, 0, 10, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
          "100, house, 0, 500, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
          "101, LODhouse, 0, 10, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
          "101, LODhouse, 0, 500, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
          "end\r\n")


def _obj(name, x, base='house', *, row_x=None, lod_object=None):
    """Scene object as _lod_owner_at sees it; *row_x* — its linked row."""
    ns = types.SimpleNamespace
    return ns(name=name, base=base, matrix_world=ns(translation=(x, 0.0, 0.0)),
              inu=ns(lod_object=lod_object,
                     ipl_uuid='u' if row_x is not None else '',
                     ipl_last_pos=(row_x or 0.0, 0.0, 0.0)))


def _vc_scene(monkeypatch):
    """VC import: no lod_index → no inu.lod_object, and partner() gives both
    placements LODhouse (by name)."""
    monkeypatch.setattr(ml, 'model_type', lambda o: ('?', o.base))
    return (_obj('house', 10.0, row_x=10.0), _obj('house.001', 500.0, row_x=500.0),
            _obj('LODhouse', 10.0), _obj('LODhouse.001', 500.0))


def test_vc_lod_owner_is_the_model_on_it(monkeypatch):
    h1, h2, l1, l2 = _vc_scene(monkeypatch)
    linked = [h1, h2]
    assert ml._lod_owner_at(l1, linked, 0.5) is h1
    assert ml._lod_owner_at(l2, linked, 0.5) is h2
    # model selected with its LOD → the selected one (Del skips it)
    assert ml._lod_owner_at(l2, [h2] + linked, 0.5) is h2
    # moved in the scene, row still under the LOD
    moved = _obj('house', 13.0, row_x=10.0)
    assert ml._lod_owner_at(l1, [moved, h2], 0.5) is moved
    # nobody there / another model there → none
    assert ml._lod_owner_at(_obj('LODhouse.002', 200.0), linked, 0.5) is None
    assert ml._lod_owner_at(l1, [_obj('shed', 10.0, 'shed', row_x=10.0)],
                            0.5) is None
    # stacked twins: the earlier (the selection comes first)
    twin = _obj('house.002', 10.0, row_x=10.0)
    assert ml._lod_owner_at(l1, [twin, h1], 0.5) is twin
    # linked by hand: inu.lod_object wins, wherever it stands
    far = _obj('house.003', 900.0, row_x=900.0, lod_object=l1)
    assert ml._lod_owner_at(l1, [h1, far], 0.5) is far
    assert ml._lod_owner_at(l2, [far], 0.5) is None


def test_vc_del_one_lod_drops_only_its_row(monkeypatch):
    """ipl_remove, VC, LODhouse (at 10) selected alone: only house at 10 is
    detached (house.001 reserved as not in the batch) → one LOD row goes."""
    h1, h2, l1, _l2 = _vc_scene(monkeypatch)
    owner = ml._lod_owner_at(l1, [h1, h2], 0.5)
    doc = IplDoc.from_text(VC_TWO)
    ed = doc.editor(game='VC')
    ed.reserve(Anchor.of(doc.rows[1].inst))
    rr = ed.detach_lod(owner.name, Anchor.of(doc.rows[0].inst))
    new = IplDoc.from_text(ed.commit().to_text())
    assert rr.lod_removed and ed.messages == []
    assert [(r.inst.model_name, r.inst.pos_x) for r in new.rows] == [
        ('house', 10.0), ('house', 500.0), ('LODhouse', 500.0)]
