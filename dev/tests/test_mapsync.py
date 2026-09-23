"""Tests for core/mapsync — stateless IDE/IPL sync. Pure Python."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.ipl import IplInstance, read_ipl  # noqa: E402
from core.ide import IdeObject, read_ide  # noqa: E402
from core.mapsync import (  # noqa: E402
    Anchor, IplDoc, IdeDoc, TextLines, write_atomic,
)


def _inst(mid, name, x, y=0.0, z=0.0, lod=-1):
    return IplInstance(model_id=mid, model_name=name, pos_x=x, pos_y=y,
                       pos_z=z, lod_index=lod)


VANILLA = (
    "# my map\r\n"
    "inst\r\n"
    "100, house, 0, 10.0, 0.0, 0.0, 0, 0, 0, 1, 1\r\n"
    "101, LODhouse, 0, 10.0, 0.0, 0.0, 0, 0, 0, 1, -1\r\n"
    "# trees\r\n"
    "200, tree, 0, 50.0, 0.0, 0.0, 0, 0, 0, 1, -1\r\n"
    "end\r\n"
    "cull\r\n"
    "end\r\n"
    "path\r\n"
    "some, path, line\r\n"
    "end\r\n"
)


def _commit(ed):
    return IplDoc.from_text(ed.commit().to_text())


# ── IPL ───────────────────────────────────────────────────────────

def test_untouched_file_is_byte_exact():
    doc = IplDoc.from_text(VANILLA)
    assert doc.editor().commit().to_text() == VANILLA


def test_update_keeps_other_lines_and_comments():
    doc = IplDoc.from_text(VANILLA)
    ed = doc.editor()
    anchor = Anchor.of(doc.rows[2].inst)
    r = ed.place('tree', _inst(200, 'tree', 60.0), anchor=anchor)
    text = ed.commit().to_text()
    assert r.action == 'update'
    assert "# my map\r\n" in text and "# trees\r\n" in text
    assert "some, path, line\r\n" in text            # path section kept
    assert "100, house, 0, 10.0, 0.0, 0.0, 0, 0, 0, 1, 1\r\n" in text
    new = IplDoc.from_text(text)
    assert new.rows[2].inst.pos_x == 60.0


def test_duplicate_gets_its_own_lod_row():
    """The user's case: a Shift+D copy of a model must get ITS OWN LOD row at
    its own position — never borrow the original's."""
    doc = IplDoc.from_text(VANILLA)
    ed = doc.editor()
    ed.reserve(Anchor.of(doc.rows[0].inst))           # the original, not touched
    r = ed.place('copy', _inst(100, 'house', 500.0),
                 lod=_inst(101, 'LODhouse', 500.0))
    new = _commit(ed)
    assert r.action == 'add' and r.lod_action == 'add'
    assert len(new.rows) == 5
    copy_row = new.rows[r.index].inst
    lod_row = new.rows[copy_row.lod_index].inst
    assert lod_row.model_name == 'LODhouse' and lod_row.pos_x == 500.0
    # original still points at its own LOD
    assert new.rows[0].inst.lod_index == 1
    assert new.rows[1].inst.pos_x == 10.0


def test_place_never_overwrites_lod_with_model():
    """«Only the LOD got added»: a stale anchor must not land on the LOD row."""
    doc = IplDoc.from_text(VANILLA)
    ed = doc.editor()
    # stale anchor pointing where the LOD row lives, but with the MODEL's id
    stale = Anchor(100, 'house', (10.0, 0.0, 0.0))
    ed.place('house', _inst(100, 'house', 11.0), anchor=stale,
             lod=_inst(101, 'LODhouse', 11.0))
    new = _commit(ed)
    names = [r.inst.model_name for r in new.rows]
    assert names.count('house') == 1 and names.count('LODhouse') == 1
    assert new.rows[0].inst.lod_index == 1
    assert new.rows[1].inst.pos_x == 11.0


def test_remove_drops_lod_and_remaps_indices():
    text = (
        "inst\n"
        "100, house, 0, 10, 0, 0, 0, 0, 0, 1, 3\n"
        "300, shop, 0, 90, 0, 0, 0, 0, 0, 1, 4\n"
        "200, tree, 0, 50, 0, 0, 0, 0, 0, 1, -1\n"
        "101, LODhouse, 0, 10, 0, 0, 0, 0, 0, 1, -1\n"
        "301, LODshop, 0, 90, 0, 0, 0, 0, 0, 1, -1\n"
        "end\n"
    )
    doc = IplDoc.from_text(text)
    ed = doc.editor()
    rr = ed.remove('house', Anchor(100, 'house', (10.0, 0.0, 0.0)))
    out = ed.commit().to_text()
    new = IplDoc.from_text(out)
    assert rr.removed and rr.lod_removed
    names = [r.inst.model_name for r in new.rows]
    assert names == ['shop', 'tree', 'LODshop']
    assert new.rows[0].inst.lod_index == 2        # was 4, remapped
    assert '\r' not in out                        # LF endings kept


def test_shared_lod_is_kept_when_still_used():
    text = (
        "inst\n"
        "100, house, 0, 10, 0, 0, 0, 0, 0, 1, 2\n"
        "100, house, 0, 20, 0, 0, 0, 0, 0, 1, 2\n"
        "101, LODhouse, 0, 15, 0, 0, 0, 0, 0, 1, -1\n"
        "end\n"
    )
    doc = IplDoc.from_text(text)
    ed = doc.editor()
    rr = ed.remove('a', Anchor(100, 'house', (10.0, 0.0, 0.0)))
    new = _commit(ed)
    assert rr.removed and not rr.lod_removed
    assert [r.inst.model_name for r in new.rows] == ['house', 'LODhouse']
    assert new.rows[0].inst.lod_index == 1


def test_moving_model_updates_its_lod_in_place():
    doc = IplDoc.from_text(VANILLA)
    ed = doc.editor()
    r = ed.place('house', _inst(100, 'house', 30.0),
                 anchor=Anchor.of(doc.rows[0].inst),
                 lod=_inst(101, 'LODhouse', 30.0))
    new = _commit(ed)
    assert r.action == 'update' and r.lod_action == 'update'
    assert len(new.rows) == 3
    assert new.rows[1].inst.pos_x == 30.0 and new.rows[0].inst.lod_index == 1


def test_second_write_is_unchanged():
    doc = IplDoc.from_text(VANILLA)
    ed = doc.editor()
    r = ed.place('tree', _inst(200, 'tree', 50.0),
                 anchor=Anchor.of(doc.rows[2].inst))
    assert ed.commit().to_text() == VANILLA
    assert r.action == 'unchanged'


def test_lost_anchor_relinks_nearby_or_appends():
    doc = IplDoc.from_text(VANILLA)
    ed = doc.editor()
    # row was nudged by 1 m in another editor → relinked, not duplicated
    r = ed.place('tree', _inst(200, 'tree', 70.0),
                 anchor=Anchor(200, 'tree', (49.0, 0.0, 0.0)))
    assert r.relinked and r.action == 'update'
    new = _commit(ed)
    assert len(new.rows) == 3


def test_reserved_row_is_never_taken():
    text = "inst\n200, tree, 0, 50, 0, 0, 0, 0, 0, 1, -1\nend\n"
    doc = IplDoc.from_text(text)
    ed = doc.editor()
    ed.reserve(Anchor(200, 'tree', (50.0, 0.0, 0.0)))
    r = ed.place('t2', _inst(200, 'tree', 50.5),
                 anchor=Anchor(200, 'tree', (50.4, 0.0, 0.0)))
    assert r.action == 'add'
    assert len(_commit(ed).rows) == 2


def test_no_inst_section_is_created():
    doc = IplDoc.from_text("cull\nend\n")
    ed = doc.editor()
    ed.place('a', _inst(1, 'a', 1.0))
    new = _commit(ed)
    assert len(new.rows) == 1 and new.rows[0].inst.model_name == 'a'


def test_new_file_and_atomic_write(tmp_path):
    p = tmp_path / "new.ipl"
    doc = IplDoc.load(str(p))
    ed = doc.editor()
    ed.place('a', _inst(1, 'a', 1.0), lod=_inst(2, 'LODa', 1.0))
    ed.commit().write(str(p))
    ipl = read_ipl(str(p))
    assert [i.model_name for i in ipl.instances] == ['a', 'LODa']
    assert ipl.instances[0].lod_index == 1
    # second write keeps a .bak of the first state
    doc2 = IplDoc.load(str(p))
    ed2 = doc2.editor()
    ed2.remove('a', Anchor(1, 'a', (1.0, 0.0, 0.0)))
    ed2.commit().write(str(p))
    assert (tmp_path / "new.ipl.bak").is_file()
    assert read_ipl(str(p)).instances == []


def test_fla_column_preserved():
    text = "inst\n1, a, 0, 1, 0, 0, 0, 0, 0, 1, -1, 5\nend\n"
    doc = IplDoc.from_text(text)
    ed = doc.editor()
    ed.place('b', _inst(2, 'b', 3.0))
    out = ed.commit().to_text()
    assert "1, a, 0, 1, 0, 0, 0, 0, 0, 1, -1, 5\n" in out
    assert len(out.splitlines()[2].split(',')) == 12


def test_bom_and_crlf_roundtrip():
    text = "﻿inst\r\n1, a, 0, 1, 0, 0, 0, 0, 0, 1, -1\r\nend\r\n"
    doc = IplDoc.from_text(text)
    assert len(doc.rows) == 1
    ed = doc.editor()
    ed.place('b', _inst(2, 'b', 3.0))
    out = ed.commit().to_text()
    assert out.startswith("﻿inst\r\n") and out.endswith("end\r\n")
    assert "\r\n2, b," in out


def test_detach_lod():
    doc = IplDoc.from_text(VANILLA)
    ed = doc.editor()
    rr = ed.detach_lod('house', Anchor.of(doc.rows[0].inst))
    new = _commit(ed)
    assert rr.lod_removed
    assert [r.inst.model_name for r in new.rows] == ['house', 'tree']
    assert new.rows[0].inst.lod_index == -1


# ── IDE ───────────────────────────────────────────────────────────

IDE_TEXT = (
    "# defs\n"
    "objs\n"
    "100, house, house_txd, 299, 0\n"
    "101, LODhouse, house_txd, 999, 0\n"
    "end\n"
    "tobj\n"
    "300, lamp, lamp_txd, 150, 0, 20, 6\n"
    "end\n"
    "anim\n"
    "400, door, door_txd, door_anim, 100, 0\n"
    "end\n"
)


def _obj(mid, name, txd='t', dd=299.0, flags=0):
    return IdeObject(model_id=mid, model_name=name, txd_name=txd,
                     draw_distance=dd, flags=flags)


def test_ide_update_add_and_preserve():
    doc = IdeDoc.from_text(IDE_TEXT)
    ed = doc.editor()
    r1 = ed.write('h', _obj(100, 'house', 'house_txd', 350.0))
    r2 = ed.write('n', _obj(500, 'newmodel', 'nm', 200.0))
    out = ed.commit().to_text()
    assert r1.action == 'update' and r2.action == 'add'
    assert "# defs\n" in out and "101, LODhouse, house_txd, 999, 0\n" in out
    ide = read_ide_text(out)
    ids = [o.model_id for o in ide.objects]
    assert ids.index(500) == ids.index(101) + 1      # appended inside objs


def test_ide_conflict_other_model_same_id():
    doc = IdeDoc.from_text(IDE_TEXT)
    ed = doc.editor()
    r = ed.write('x', _obj(100, 'garage'))
    assert r.action == 'conflict'
    assert ed.commit().to_text() == IDE_TEXT


def test_ide_conflict_id_in_anim_section():
    ed = IdeDoc.from_text(IDE_TEXT).editor()
    assert ed.write('x', _obj(400, 'door')).action == 'conflict'


def test_ide_name_exists_with_other_id():
    ed = IdeDoc.from_text(IDE_TEXT).editor()
    assert ed.write('x', _obj(900, 'house')).action == 'conflict'
    # ...unless the object was linked to that row under the old id
    ed2 = IdeDoc.from_text(IDE_TEXT).editor()
    r = ed2.write('x', _obj(900, 'house'), anchor_id=100, anchor_name='house')
    assert r.action == 'update'
    assert "900, house, t, 299, 0\n" in ed2.commit().to_text()


def test_ide_rename_via_anchor():
    ed = IdeDoc.from_text(IDE_TEXT).editor()
    r = ed.write('x', _obj(100, 'villa'), anchor_id=100, anchor_name='house')
    assert r.action == 'update'


def test_ide_tobj_times_kept():
    ed = IdeDoc.from_text(IDE_TEXT).editor()
    ed.write('l', _obj(300, 'lamp', 'lamp_txd', 180.0))
    assert "300, lamp, lamp_txd, 180, 0, 20, 6\n" in ed.commit().to_text()


def test_ide_copies_write_one_row():
    ed = IdeDoc.from_text(IDE_TEXT).editor()
    ed.write('a', _obj(600, 'bench'))
    r = ed.write('b', _obj(600, 'bench'))
    assert r.action == 'same'
    assert ed.commit().to_text().count('600, bench') == 1


def test_ide_remove_checks_name():
    ed = IdeDoc.from_text(IDE_TEXT).editor()
    assert not ed.remove('x', 100, 'garage')
    assert ed.remove('h', 101, 'LODhouse')
    out = ed.commit().to_text()
    assert 'LODhouse' not in out and '100, house' in out


def test_ide_unchanged_is_byte_exact():
    ed = IdeDoc.from_text(IDE_TEXT).editor()
    r = ed.write('h', _obj(100, 'house', 'house_txd', 299.0))
    assert r.action == 'unchanged'
    assert ed.commit().to_text() == IDE_TEXT


def read_ide_text(text):
    import tempfile
    import os
    fd, p = tempfile.mkstemp(suffix='.ide')
    os.close(fd)
    try:
        write_atomic(p, text, backup=False)
        return read_ide(p)
    finally:
        os.remove(p)


# ── randomized workflow: add / duplicate / move / delete ──────────

def test_random_workflow_keeps_file_consistent():
    """Simulate the Blender side (objects remember the anchor the editor
    returned) through hundreds of random Add / Shift+D / move / Del steps.
    Invariants after every step: each object has exactly one row, its
    lod_index points at ITS OWN LOD row (same position, LOD name), no orphan
    LOD rows, and a foreign row that was in the file stays untouched."""
    import random
    rnd = random.Random(1234)
    foreign = "999, bridge, 0, -500, -500, 0, 0, 0, 0, 1, -1"
    text = "inst\n" + foreign + "\nend\n"
    objs = []          # dict(mid, name, x, anchor)
    for step in range(400):
        doc = IplDoc.from_text(text)
        ed = doc.editor()
        op = rnd.choice(['add', 'add', 'dup', 'move', 'move', 'del'])
        if op == 'add' or not objs:
            o = {'mid': rnd.choice([100, 200, 300]), 'x': rnd.uniform(0, 1000),
                 'anchor': None}
            o['name'] = f"m{o['mid']}"
            objs.append(o)
            batch = [o]
        elif op == 'dup':
            src = rnd.choice(objs)
            o = dict(src, x=src['x'] + rnd.uniform(5, 50), anchor=None)
            objs.append(o)
            batch = [o]
        elif op == 'move':
            batch = rnd.sample(objs, min(len(objs), rnd.randint(1, 3)))
            for o in batch:
                o['x'] += rnd.uniform(-20, 20)
        else:
            o = rnd.choice(objs)
            others = [a for a in objs if a is not o and a['anchor']]
            for a in others:
                ed.reserve(a['anchor'])
            if o['anchor']:
                ed.remove(o, o['anchor'])
            text = ed.commit().to_text()
            objs.remove(o)
            _check(text, objs, foreign)
            continue
        ids = {id(b) for b in batch}
        for a in objs:
            if id(a) not in ids and a['anchor']:
                ed.reserve(a['anchor'])
        res = [ed.place(b, _inst(b['mid'], b['name'], b['x']), anchor=b['anchor'],
                        lod=_inst(b['mid'] + 1, 'LOD' + b['name'], b['x']))
               for b in batch]
        text = ed.commit().to_text()
        for r in res:
            r.tag['anchor'] = Anchor.of(r.inst)
        _check(text, objs, foreign)


def _check(text, objs, foreign):
    doc = IplDoc.from_text(text)
    rows = [r.inst for r in doc.rows]
    assert foreign in text
    models = [i for i in rows if not i.model_name.startswith('LOD')
              and i.model_name != 'bridge']
    lods = [k for k, i in enumerate(rows) if i.model_name.startswith('LOD')]
    assert len(models) == len(objs)
    used = []
    for o in objs:
        k = doc.find(o['anchor'])
        assert k >= 0, o
        m = rows[k]
        assert abs(m.pos_x - o['x']) < 1e-3
        li = m.lod_index
        assert 0 <= li < len(rows)
        lod = rows[li]
        assert lod.model_name == 'LOD' + o['name'] and abs(lod.pos_x - o['x']) < 1e-3
        used.append(li)
    assert sorted(used) == sorted(lods)          # one LOD per model, no orphans


# ── texture names ─────────────────────────────────────────────────

def test_clean_texture_name():
    from core.tex_name import clean_texture_name as c
    assert c('render_tex_1.png.001') == 'render_tex_1'
    assert c('render_tex_1.png001') == 'render_tex_1'
    assert c('tex.PNG') == 'tex'
    assert c('tex.dds.002') == 'tex'
    assert c('tex.001') == 'tex'
    assert c('door_big_white_3') == 'door_big_white_3'
    assert c('my.pngish') == 'my.pngish'
    assert c('') == ''
