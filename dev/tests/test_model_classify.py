"""Tests for the pure (bpy-free) DFF / LOD / COL classifier in
core/model_classify.py — the layered auto-detection that replaced the manual
suffix/prefix system. LOD detection for SCENE names is word-edge «lod» /
uppercase LOD (stricter than the importer's substring rule — English words
like «explode» must not classify as LODs), COL by tag or no-texture,
otherwise DFF; suffixes survive as a manual override."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.model_classify import classify_model, explicit_name_type, reuse_key  # noqa: E402
from core.ipl import strip_lod_marker  # noqa: E402


# ── LOD by name (case-insensitive, shared with the importer) ──

def test_lod_prefix_uppercase():
    assert classify_model("LODfunc_detail_47144") == ('LOD', 'func_detail_47144')


def test_lod_prefix_lowercase_vanilla():
    # Vanilla SA ships lowercase «lod» model names — must be caught too.
    assert classify_model("lodbush2b") == ('LOD', 'bush2b')


def test_lod_suffix():
    assert classify_model("bush1b_LOD") == ('LOD', 'bush1b')


def test_lod_token_at_end_no_separator():
    assert classify_model("detailLOD") == ('LOD', 'detail')


def test_name_without_lod_substring_stays_dff():
    # «bloodstain» has no «lod» substring at all → DFF.
    assert classify_model("bloodstain", has_texture=True) == ('DFF', 'bloodstain')


def test_lod_base_matches_dff_base_for_pairing():
    dff_t, dff_base = classify_model("worldspawn_1", has_texture=True)
    lod_t, lod_base = classify_model("LODworldspawn_1")
    assert (dff_t, lod_t) == ('DFF', 'LOD')
    assert dff_base == lod_base == 'worldspawn_1'


def test_lod_wins_over_texture():
    # A LOD is textured too — the LOD name must win over the DFF texture tier.
    assert classify_model("LODfunc", has_texture=True) == ('LOD', 'func')


def test_english_word_lod_midword_stays_dff():
    # «lod» buried between letters is an English word, not a LOD marker —
    # bare substring matching mangled these names on export (expe_box).
    assert classify_model("explode_box", has_texture=True) == ('DFF', 'explode_box')
    assert classify_model("melody_hall", has_texture=True) == ('DFF', 'melody_hall')
    # Known limitation: a leading «lod» (lodge_hotel) is indistinguishable
    # from the vanilla lod-prefix convention (lodbush2b) — stays LOD.
    assert classify_model("lodge_hotel", has_texture=True)[0] == 'LOD'


def test_lod_word_edge_forms_still_match():
    # Word-edge lowercase forms every SA convention uses must keep working.
    assert classify_model("nw_lodbit_26")[0] == 'LOD'          # _lod
    assert classify_model("oilderricklod01")[0] == 'LOD'       # lod + digit
    assert classify_model("bush_lod", has_texture=True)[0] == 'LOD'   # trailing


# ── DFF vs COL by texture (untagged external meshes) ──

def test_textured_untagged_is_dff():
    assert classify_model("func_detail_47144", has_texture=True) == ('DFF', 'func_detail_47144')


def test_untextured_untagged_is_col():
    assert classify_model("func_detail_47144", has_texture=False) == ('COL', 'func_detail_47144')


# ── Explicit name marker outranks a stale inu.type tag ──
# LODTerrain270 shipped as a geometry-less DFF: a `*_LOD` mesh carried a COL
# tag, export diverted it into embedded collision and the model never drew.

def test_lod_suffix_beats_col_tag():
    assert classify_model("terrain270_LOD", has_texture=True,
                          inu_type='COL') == ('LOD', 'terrain270')


def test_dff_suffix_beats_col_tag():
    assert classify_model("wall_DFF", has_texture=False,
                          inu_type='COL') == ('DFF', 'wall')


def test_explicit_name_type_reports_marker():
    assert explicit_name_type("terrain270_LOD") == ('LOD', 'terrain270')
    assert explicit_name_type("body_SHA") == ('COL', 'body')
    assert explicit_name_type("LODTerrain270") == (None, 'LODTerrain270')


# ── Explicit inu.type tag — checked BEFORE the LOD-name rule ──

def test_inu_type_col_forces_col_even_when_textured():
    assert classify_model("barrier", has_texture=True, inu_type='COL') == ('COL', 'barrier')


def test_inu_type_col_beats_accidental_lod_in_name():
    # A tagged collision whose name happens to contain «lod» must stay COL,
    # not be reclassified as a LOD.
    assert classify_model("lodwall", has_texture=True, inu_type='COL') == ('COL', 'lodwall')


def test_inu_type_sha_is_col():
    assert classify_model("shadow", has_texture=True, inu_type='SHA') == ('COL', 'shadow')


def test_inu_type_obj_defers_to_texture():
    assert classify_model("thing", has_texture=False, inu_type='OBJ') == ('COL', 'thing')


# ── Suffix / marker override beats the heuristic ──

def test_suffix_col_override_on_textured_mesh():
    assert classify_model("building_COL", has_texture=True) == ('COL', 'building')


def test_suffix_lod_override():
    assert classify_model("building_LOD", has_texture=True) == ('LOD', 'building')


def test_suffix_dff_override_on_untextured_mesh():
    assert classify_model("flat_DFF", has_texture=False) == ('DFF', 'flat')


def test_sha_suffix_is_col():
    assert classify_model("thing_SHA", has_texture=True) == ('COL', 'thing')


def test_bare_col_marker_uppercase_only():
    assert classify_model("buildingCOL", has_texture=True) == ('COL', 'building')


def test_protocol_lowercase_col_is_not_collision():
    # «protocol» ends with lowercase «col» — bare marker match is case-sensitive
    # so it stays a DFF, not collision.
    assert classify_model("protocol", has_texture=True) == ('DFF', 'protocol')


# ── has_texture lazy callable: only run when the texture tier is reached ──

def test_has_texture_callable_skipped_on_lod_hit():
    calls = []

    def ht():
        calls.append(1)
        return True

    classify_model("LODthing", has_texture=ht)
    assert calls == []


def test_has_texture_callable_used_when_needed():
    calls = []

    def ht():
        calls.append(1)
        return False

    assert classify_model("plain", has_texture=ht) == ('COL', 'plain')
    assert calls == [1]


# ── strip_lod_marker (reused from core.ipl) ──

def test_strip_lod_marker_unchanged_without_lod():
    assert strip_lod_marker("func_detail") == 'func_detail'


def test_strip_lod_marker_prefix():
    assert strip_lod_marker("LODbush2b") == 'bush2b'


# ── reuse_key (Import from IMG: модель из сцены по ID + имени) ──

def test_reuse_key_lod_forms():
    assert reuse_key('lodfoo') == reuse_key('foo_LOD') == 'foo'
    assert reuse_key('des_damlodbit04') == reuse_key('des_dambit04_LOD')
    assert reuse_key('tatar_str_1LOD') == 'tatar_str_1'


def test_reuse_key_dff_markers():
    assert reuse_key('Foo_DFF') == reuse_key('foo')
    # LOD, опознанный только по lod_index: импорт даёт «<имя>_DFF_LOD».
    assert reuse_key('xyz_far_DFF_LOD') == reuse_key('xyz_far')


def test_reuse_key_other_name_and_empty():
    assert reuse_key('mybox') != reuse_key('othername')
    assert reuse_key('') == ''
