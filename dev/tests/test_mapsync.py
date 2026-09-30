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


def test_interior_and_fla_kept_on_readd():
    # Вкладка Import кладёт interior/FLA строки в объект → Add без правок
    # оставляет файл как был; с 0 (старое поведение) строка теряла оба.
    text = "inst\n1, a, 3, 1, 0, 0, 0, 0, 0, 1, -1, 5\nend\n"
    doc = IplDoc.from_text(text)
    ed = doc.editor()
    res = ed.place('a', IplInstance(model_id=1, model_name='a', interior=3,
                                    pos_x=1.0, rot_w=1.0, lod_index=-1,
                                    real_interior=5),
                   anchor=Anchor.of(doc.rows[0].inst))
    assert ed.commit().to_text() == text
    assert res.action == 'unchanged'
    ed = IplDoc.from_text(text).editor()
    ed.place('a', IplInstance(model_id=1, model_name='a', pos_x=1.0,
                              rot_w=1.0, lod_index=-1),
             anchor=Anchor.of(doc.rows[0].inst))
    row = [p.strip() for p in ed.commit().to_text().splitlines()[1].split(',')]
    assert (row[2], len(row), row[11]) == ('0', 12, '0')


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


# ── VC / III: no lod_index column, LOD row found by content ──────

VC_TEXT = (
    "inst\r\n"
    "100, doc_shed01, 0, 10, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
    "300, doc_crane, 0, 90, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
    "101, LOD_shed01, 0, 10, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
    "301, LOD_crane, 0, 90, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
    "end\r\n"
)


def _add_three_times(game):
    text, anchor, res = "inst\nend\n", None, []
    for _ in range(3):
        ed = IplDoc.from_text(text).editor(game=game)
        r = ed.place('h', _inst(100, 'house', 10.0), anchor=anchor,
                     lod=_inst(101, 'LODhouse', 10.0))
        text = ed.commit().to_text()
        anchor = Anchor.of(r.inst)
        res.append(r)
    return text, anchor, res


def test_vc_repeated_add_reuses_lod_row():
    """Every repeated Add in a VC/III IPL appended one more LOD row: after a
    re-read the model row has no lod_index to follow."""
    for game in ('VC', 'III'):
        text, anchor, res = _add_three_times(game)
        new = IplDoc.from_text(text)
        assert [r.inst.model_name for r in new.rows] == ['house', 'LODhouse']
        assert all(r.style == game for r in new.rows)
        assert res[-1].action == 'unchanged' and res[-1].lod_action == 'unchanged'
        # moving the model moves its LOD row — still one of each
        ed = new.editor(game=game)
        r = ed.place('h', _inst(100, 'house', 30.0), anchor=anchor,
                     lod=_inst(101, 'LODhouse', 30.0))
        new = _commit(ed)
        assert r.action == 'update' and r.lod_action == 'update'
        assert [(x.inst.model_name, x.inst.pos_x) for x in new.rows] == [
            ('house', 30.0), ('LODhouse', 30.0)]
        # remove takes the LOD row along
        ed = new.editor(game=game)
        rr = ed.remove('h', Anchor.of(new.rows[0].inst))
        assert _commit(ed).rows == []
        assert rr.removed and rr.lod_removed


def test_vc_vanilla_lod_row_reused_and_removed():
    """Vanilla VC pairs model and LOD by name (equal after 3 characters)."""
    doc = IplDoc.from_text(VC_TEXT)
    ed = doc.editor(game='VC')
    r = ed.place('shed', _inst(100, 'doc_shed01', 10.0),
                 anchor=Anchor.of(doc.rows[0].inst),
                 lod=_inst(101, 'LOD_shed01', 10.0))
    assert ed.commit().to_text() == VC_TEXT
    assert r.action == 'unchanged' and r.lod_action == 'unchanged'
    ed = doc.editor(game='VC')
    rr = ed.remove('shed', Anchor(100, 'doc_shed01', (10.0, 0.0, 0.0)))
    assert ed.commit().to_text() == (
        "inst\r\n"
        "300, doc_crane, 0, 90, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
        "301, LOD_crane, 0, 90, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n"
        "end\r\n")
    assert rr.removed and rr.lod_removed


def test_vc_copy_next_to_original_gets_its_own_lod():
    """A Shift+D copy 0.3 m off the original — or left right on it — must not
    take the original's LOD row; re-adding both keeps one LOD each."""
    for x in (10.3, 10.0):
        doc = IplDoc.from_text(VC_TEXT)
        ed = doc.editor(game='VC')
        ed.reserve(Anchor.of(doc.rows[0].inst))
        r = ed.place('copy', _inst(100, 'doc_shed01', x),
                     lod=_inst(101, 'LOD_shed01', x))
        assert r.action == 'add' and r.lod_action == 'add'
        doc = _commit(ed)
        ed = doc.editor(game='VC')
        for px in (x, 10.0):
            ed.place(px, _inst(100, 'doc_shed01', px),
                     anchor=Anchor(100, 'doc_shed01', (px, 0.0, 0.0)),
                     lod=_inst(101, 'LOD_shed01', px))
        new = _commit(ed)
        rows = sorted((r.inst.model_name, r.inst.pos_x) for r in new.rows)
        assert rows == sorted([('LOD_crane', 90.0), ('LOD_shed01', 10.0),
                               ('LOD_shed01', x), ('doc_crane', 90.0),
                               ('doc_shed01', 10.0), ('doc_shed01', x)])


def test_vc_remove_copy_and_original_together():
    """Original and a copy left on it, one LOD each: one Del of both takes
    both LOD rows (not the same one twice)."""
    text, anchors = "inst\nend\n", []
    for tag in ('orig', 'copy'):
        ed = IplDoc.from_text(text).editor(game='VC')
        for a in anchors:
            ed.reserve(a)
        r = ed.place(tag, _inst(100, 'house', 10.0),
                     lod=_inst(101, 'LODhouse', 10.0))
        text = ed.commit().to_text()
        anchors.append(Anchor.of(r.inst))
    assert len(IplDoc.from_text(text).rows) == 4
    ed = IplDoc.from_text(text).editor(game='VC')
    rs = [ed.remove(t, a) for t, a in zip(('orig', 'copy'), anchors)]
    assert _commit(ed).rows == []
    assert ed.counts()['lod_removed'] == 2
    assert all(r.removed and r.lod_removed for r in rs)


def _vc(mid, name, x):
    return "%d, %s, 0, %s, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n" % (mid, name, x)


def test_vc_neighbour_lod_is_not_taken():
    """B stands 0.3 m from A and has no LOD row: Add of B gets a new LOD,
    Del of B leaves A's LOD alone."""
    text = ("inst\r\n" + _vc(100, 'house', 10) + _vc(101, 'LODhouse', 10)
            + _vc(100, 'house', 10.3) + "end\r\n")
    doc = IplDoc.from_text(text)
    ed = doc.editor(game='VC')
    ed.reserve(Anchor.of(doc.rows[0].inst))
    r = ed.place('B', _inst(100, 'house', 10.3),
                 anchor=Anchor.of(doc.rows[2].inst),
                 lod=_inst(101, 'LODhouse', 10.3))
    rows = [(x.inst.model_name, x.inst.pos_x) for x in _commit(ed).rows]
    assert r.lod_action == 'add'
    assert rows == [('house', 10.0), ('LODhouse', 10.0), ('house', 10.3),
                    ('LODhouse', 10.3)]
    ed = doc.editor(game='VC')
    ed.reserve(Anchor.of(doc.rows[0].inst))
    rr = ed.remove('B', Anchor.of(doc.rows[2].inst))
    assert ed.commit().to_text() == text.replace(_vc(100, 'house', 10.3), '')
    assert rr.removed and not rr.lod_removed


def test_vc_shared_lod_of_stacked_pair_is_kept():
    """Two rows of one model on one spot sharing one LOD row (as in some
    shipped IPLs): deleting one keeps the LOD for the other."""
    text = ("inst\r\n" + _vc(100, 'house', 10) + _vc(100, 'house', 10)
            + _vc(101, 'LODhouse', 10) + "end\r\n")
    doc = IplDoc.from_text(text)
    ed = doc.editor(game='VC')
    ed.reserve(Anchor.of(doc.rows[0].inst))
    rr = ed.remove('B', Anchor.of(doc.rows[1].inst))
    assert ed.commit().to_text() == (
        "inst\r\n" + _vc(100, 'house', 10) + _vc(101, 'LODhouse', 10)
        + "end\r\n")
    assert rr.removed and not rr.lod_removed


def test_vc_iii_detach_lod_removes_lod_row():
    """Del of a LOD selected alone in a VC/III IPL did nothing: the row has no
    lod_index. The LOD row goes, the model row stays byte for byte."""
    doc = IplDoc.from_text(VC_TEXT)
    ed = doc.editor(game='VC')
    rr = ed.detach_lod('shed', Anchor.of(doc.rows[0].inst))
    assert ed.commit().to_text() == VC_TEXT.replace(
        "101, LOD_shed01, 0, 10, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n", '')
    assert rr.lod_removed and not rr.removed and ed.messages == []
    iii = "%d, %s, %.1f, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0\r\n"
    text = ("inst\r\n" + iii % (100, 'house', 10) + iii % (300, 'shop', 90)
            + iii % (101, 'LODhouse', 10) + "end\r\n")
    doc = IplDoc.from_text(text)
    assert all(r.style == 'III' for r in doc.rows)
    ed = doc.editor(game='III')
    rr = ed.detach_lod('house', Anchor.of(doc.rows[0].inst))
    assert ed.commit().to_text() == text.replace(iii % (101, 'LODhouse', 10), '')
    assert rr.lod_removed and ed.messages == []


def test_detach_lod_without_lod_or_row_says_so():
    """Nothing to detach is no longer silent: INFO without a LOD row, WARNING
    when the row itself is gone; the file stays the same."""
    for text, game, row in ((VC_TEXT.replace(
            "301, LOD_crane, 0, 90, 0, 0, 1, 1, 1, 0, 0, 0, 1\r\n", ''), 'VC', 1),
            (VANILLA, 'SA', 2)):
        doc = IplDoc.from_text(text)
        ed = doc.editor(game=game)
        rr = ed.detach_lod('x', Anchor.of(doc.rows[row].inst))
        assert ed.commit().to_text() == text and not rr.lod_removed
        assert [m.level for m in ed.messages] == ['INFO']
    ed = IplDoc.from_text(VC_TEXT).editor(game='VC')
    rr = ed.detach_lod('x', Anchor(100, 'doc_shed01', (500.0, 0.0, 0.0)))
    assert ed.commit().to_text() == VC_TEXT and not rr.lod_removed
    assert [m.level for m in ed.messages] == ['WARNING']


def test_vc_detach_lod_of_copy_and_original():
    """Original and a copy on one spot, one LOD each: detaching both takes
    both LOD rows; detaching one (the other reserved) takes only one."""
    text = ("inst\r\n" + _vc(100, 'house', 10) + _vc(100, 'house', 10)
            + _vc(101, 'LODhouse', 10) + _vc(101, 'LODhouse', 10) + "end\r\n")
    doc = IplDoc.from_text(text)
    ed = doc.editor(game='VC')
    rs = [ed.detach_lod(t, Anchor.of(doc.rows[0].inst)) for t in ('a', 'b')]
    new = _commit(ed)
    assert sorted(r.inst.model_name for r in new.rows) == ['house', 'house']
    assert all(r.lod_removed for r in rs) and ed.messages == []
    ed = doc.editor(game='VC')
    ed.reserve(Anchor.of(doc.rows[1].inst))
    rr = ed.detach_lod('a', Anchor.of(doc.rows[0].inst))
    new = _commit(ed)
    assert sorted(r.inst.model_name for r in new.rows) == [
        'LODhouse', 'house', 'house']
    assert rr.lod_removed
    # B 0.3 m from A has no LOD row: A's LOD is not B's to detach
    text = ("inst\r\n" + _vc(100, 'house', 10) + _vc(101, 'LODhouse', 10)
            + _vc(100, 'house', 10.3) + "end\r\n")
    doc = IplDoc.from_text(text)
    ed = doc.editor(game='VC')
    ed.reserve(Anchor.of(doc.rows[0].inst))
    rr = ed.detach_lod('B', Anchor.of(doc.rows[2].inst))
    assert ed.commit().to_text() == text and not rr.lod_removed
    assert [m.level for m in ed.messages] == ['INFO']


def test_sa_repeated_add_is_byte_identical():
    """SA keeps following lod_index: repeated Add changes nothing."""
    text, _anchor, res = _add_three_times('SA')
    assert text == ("inst\n"
                    "100, house, 0, 10.000000, 0.000000, 0.000000, 0.000000, "
                    "0.000000, 0.000000, 1.000000, 1\n"
                    "101, LODhouse, 0, 10.000000, 0.000000, 0.000000, 0.000000, "
                    "0.000000, 0.000000, 1.000000, -1\n"
                    "end\n")
    assert [(r.action, r.lod_action) for r in res] == [
        ('add', 'add'), ('unchanged', 'unchanged'), ('unchanged', 'unchanged')]


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


# ── «same numbers»: float32 from Blender, the %.6f step ───────────

def _f32(v):
    import struct
    return struct.unpack('<f', struct.pack('<f', v))[0]


def test_ipl_float32_values_keep_row():
    """Blender hands float32 over; %.6f of float32 2796.9453125 is
    2796.945312 where R* wrote 2796.945313 — the same float for the game."""
    src = ("inst\n"
           "200, tree, 0, 2796.945313, 1015.664063, 117.0703125, "
           "0, 0, 0, 1, -1\n"
           "end\n")
    doc = IplDoc.from_text(src)
    row = doc.rows[0].inst
    ed = doc.editor()
    r = ed.place('t', _inst(200, 'tree', _f32(row.pos_x), _f32(row.pos_y),
                            _f32(row.pos_z)), anchor=Anchor.of(row))
    assert ed.commit().to_text() == src
    assert r.action == 'unchanged'


def test_ipl_seventh_decimal_keeps_row():
    """14.1015625 is written 14.101562: 5e-7 apart, within the %.6f step."""
    src = "inst\n1, a, 0, 14.1015625, 0, 0, 0, 0, 0, 1, -1\nend\n"
    doc = IplDoc.from_text(src)
    ed = doc.editor()
    r = ed.place('a', _inst(1, 'a', 14.1015625),
                 anchor=Anchor.of(doc.rows[0].inst))
    assert ed.commit().to_text() == src
    assert r.action == 'unchanged'


def test_ipl_real_move_is_written():
    src = "inst\n1, a, 0, 14.1015625, 0, 0, 0, 0, 0, 1, -1\nend\n"
    doc = IplDoc.from_text(src)
    ed = doc.editor()
    r = ed.place('a', _inst(1, 'a', 14.1015625 + 0.01),
                 anchor=Anchor.of(doc.rows[0].inst))
    new = _commit(ed)
    assert r.action == 'update'
    assert abs(new.rows[0].inst.pos_x - 14.1115625) < 1e-5


def test_ide_float32_draw_distance_keeps_row():
    src = "objs\n6062, Miami_atm, shops2_law, 100.01, 128\nend\n"
    ed = IdeDoc.from_text(src).editor(game='SA')
    r = ed.write('x', _obj(6062, 'Miami_atm', 'shops2_law', _f32(100.01), 128))
    assert r.action == 'unchanged'
    assert ed.commit().to_text() == src
    ed = IdeDoc.from_text(src).editor(game='SA')
    r = ed.write('x', _obj(6062, 'Miami_atm', 'shops2_law', 100.5, 128))
    assert r.action == 'update'
    assert "6062, Miami_atm, shops2_law, 100.5, 128\n" in ed.commit().to_text()


def test_ide_big_flags_compared_exactly():
    """16777216 and 16777217 are one float32 — flags still differ."""
    src = "objs\n1, a, b, 100, 16777216\nend\n"
    ed = IdeDoc.from_text(src).editor(game='SA')
    r = ed.write('x', _obj(1, 'a', 'b', 100.0, 16777217))
    assert r.action == 'update'
    assert "1, a, b, 100, 16777217\n" in ed.commit().to_text()


VC_IDE = "objs\n865, ap_tower, ap_buildings2, 1, 299, 0\nend\n"


def test_ide_file_game_from_rows():
    """III/VC read the 4th field as the mesh count: a VC file keeps the
    count form even when the scene is SA."""
    assert IdeDoc.from_text(VC_IDE).file_game('SA') == 'VC'
    assert IdeDoc.from_text(VC_IDE).file_game('III') == 'III'
    assert IdeDoc.from_text(IDE_TEXT).file_game('VC') == 'SA'
    tobj = "tobj\n300, lamp, lamp_txd, 150, 0, 20, 6\nend\n"
    assert IdeDoc.from_text(tobj).file_game('VC') == 'SA'
    assert IdeDoc.from_text("objs\nend\n").file_game('III') == 'III'
    assert IdeDoc.new().file_game('SA') == 'SA'


def test_ide_sa_scene_writes_count_form_into_vc_file():
    doc = IdeDoc.from_text(VC_IDE)
    ed = doc.editor(game=doc.file_game('SA'))
    assert ed.write('t', _obj(865, 'ap_tower', 'ap_buildings2')).action \
        == 'unchanged'
    ed.write('n', _obj(866, 'newmodel', 'nm', 200.0, 4))
    out = ed.commit().to_text()
    assert out.startswith(VC_IDE[:-4])
    assert "866, newmodel, nm, 1, 200, 4\n" in out


def test_ide_file_game_stray_sa_rows():
    """SA-form rows an SA scene wrote into a VC file don't switch the file
    to the SA form: the next Add writes the count form and fixes them."""
    tie = VC_IDE[:-4] + "900, mymodel, mytxd, 300, 0\nend\n"
    assert IdeDoc.from_text(tie).file_game('VC') == 'VC'
    assert IdeDoc.from_text(tie).file_game('SA') == 'VC'
    bad = (VC_IDE[:-4] + "866, ap_radar, ap_buildings2, 1, 299, 0\n"
           "900, mymodel, mytxd, 300, 0\nend\n")
    assert IdeDoc.from_text(bad).file_game('VC') == 'VC'
    assert IdeDoc.from_text(bad).file_game('SA') == 'VC'
    doc = IdeDoc.from_text(bad)
    ed = doc.editor(game=doc.file_game('VC'))
    assert ed.write('b', _obj(900, 'mymodel', 'mytxd', 300.0, 0)).action \
        == 'update'
    ed.write('n', _obj(901, 'newmodel', 'nm', 200.0, 4))
    out = ed.commit().to_text()
    assert "900, mymodel, mytxd, 1, 300, 0\n" in out
    assert "901, newmodel, nm, 1, 200, 4\n" in out
    # Mostly SA-form rows: SA for an SA scene; a III/VC scene keeps the
    # count form and leaves a good count row as it is.
    mixed = IdeDoc.from_text(IDE_TEXT + VC_IDE)
    assert mixed.file_game('SA') == 'SA'
    assert mixed.file_game('VC') == 'VC'
    ed = mixed.editor(game=mixed.file_game('III'))
    assert ed.write('t', _obj(865, 'ap_tower', 'ap_buildings2')).action \
        == 'unchanged'
    assert ed.commit().to_text() == IDE_TEXT + VC_IDE


def test_same_number_rule():
    from core.mapsync.ipl_doc import _same_number
    assert _same_number(2796.945313, 2796.945312)        # one float32
    assert _same_number(14.1015625, 14.101562)           # %.6f step
    assert not _same_number(14.1015625, 14.1015625 + 0.01)
    assert not _same_number(16777216.0, 16777217.0)      # whole numbers
    assert not _same_number(1e39, 1.5)                   # past float32


def test_lod_row_keeps_its_quaternion_sign():
    """q and −q are one rotation: a LOD row stored with the other sign than
    its model's row is left as is (SA by lod_index, VC by content); a real
    move rewrites it with the row's own sign."""
    import copy
    for game, src in (
            ('SA', "inst\n"
                   "4002, LAn2_x, 0, 10, 0, 0, 0, 0, -0.7071068, -0.7071068, 1\n"
                   "4003, LODn2_x, 0, 10, 0, 0, 0, 0, 0.7071068, 0.7071068, -1\n"
                   "end\n"),
            ('VC', "inst\n"
                   "100, house, 0, 10, 0, 0, 1, 1, 1, 0, 0, -0.7071068, -0.7071068\n"
                   "101, LODhouse, 0, 10, 0, 0, 1, 1, 1, 0, 0, 0.7071068, 0.7071068\n"
                   "end\n")):
        for dx in (0.0, 1.0):
            doc = IplDoc.from_text(src)
            row, lrow = doc.rows[0].inst, doc.rows[1].inst
            dinst = copy.copy(row)
            dinst.pos_x += dx
            lod = copy.copy(dinst)
            lod.model_id, lod.model_name = lrow.model_id, lrow.model_name
            lod.lod_index = -1
            ed = doc.editor(game=game)
            r = ed.place('x', dinst, anchor=Anchor.of(row), lod=lod)
            text = ed.commit().to_text()
            if not dx:
                assert (r.action, r.lod_action) == ('unchanged', 'unchanged')
                assert text == src
            else:
                assert r.lod_action == 'update'
                assert r.lod_inst.pos_x == 11.0
                assert r.lod_inst.rot_z > 0 and r.lod_inst.rot_w > 0


def test_vc_iii_update_keeps_file_scale():
    """III/VC read the row's scale but don't apply it (re3/reVC
    LoadObjectInstance): Blender objects stay unscaled and hand over 1.0.
    An existing model/LOD row keeps its own scale; a new row gets 1.0."""
    import copy
    for game, src, lod_id, scales in (
            ('VC', "inst\r\n"
                   "455, veg_palmkb8, 0, -988.378296, -1189.2052, 14.674223, "
                   "0.5, 0.5, 0.5, 0, 0, 0, 1\r\n"
                   "1020, LODdockwall1, 0, -988.378296, -1189.2052, 14.674223, "
                   "0.980392158, 1, 1, 0, 0, 0, 1\r\n"
                   "end\r\n",
             (1020, 'LODdockwall1'),
             ("0.500000, 0.500000, 0.500000", "0.980392, 1.000000, 1.000000")),
            ('III', "inst\r\n"
                    "1467, treepatchkb4, 358.6, -1567.28, 40.9143, "
                    "1.31, 1.31, 1.31, 0, 0, -1, 4.37114e-008\r\n"
                    "1493, LODepatchkb4, 358.6, -1567.28, 40.9143, "
                    "1.31, 1.31, 1.31, 0, 0, -1, 4.37114e-008\r\n"
                    "end\r\n",
             (1493, 'LODepatchkb4'),
             ("1.310000, 1.310000, 1.310000",) * 2)):
        for dx in (0.0, 1.0):
            doc = IplDoc.from_text(src)
            a = doc.rows[0].inst
            dinst = IplInstance(
                model_id=a.model_id, model_name=a.model_name,
                interior=a.interior, pos_x=a.pos_x + dx, pos_y=a.pos_y,
                pos_z=a.pos_z, rot_x=a.rot_x, rot_y=a.rot_y, rot_z=a.rot_z,
                rot_w=a.rot_w)
            lod = copy.copy(dinst)
            lod.model_id, lod.model_name = lod_id
            ed = doc.editor(game=game)
            r = ed.place('x', dinst, anchor=Anchor.of(a), lod=lod)
            text = ed.commit().to_text()
            assert dinst.scale_x == 1.0             # caller's object untouched
            if not dx:
                assert text == src
                assert (r.action, r.lod_action) == ('unchanged', 'unchanged')
            else:
                assert (r.action, r.lod_action) == ('update', 'update')
                lines = text.split("\r\n")
                assert scales[0] in lines[1] and scales[1] in lines[2]
                assert abs(r.inst.pos_x - (a.pos_x + 1.0)) < 1e-5
                assert abs(r.lod_inst.pos_x - (a.pos_x + 1.0)) < 1e-5
        # a new row: 1.0
        ed = IplDoc.from_text(src).editor(game=game)
        r = ed.place('n', _inst(lod_id[0] - 1, 'newthing', 500.0))
        text = ed.commit().to_text()
        assert r.action == 'add'
        new_line = [ln for ln in text.split("\r\n") if 'newthing' in ln][0]
        assert "1.000000, 1.000000, 1.000000" in new_line


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
