"""core.ipl — the name of a LOD and how III/VC pair it with its model.

SA pairs a LOD with its model through the IPL lod_index, so any name works
(the addon's «LOD<name>»). III/VC have no such column: the game pairs them
by NAME from the 4th character on, case-sensitive — re3/reVC
CSimpleModelInfo::FindRelatedModel, faststrcmp(name + 3, …), the first
model by ID (VC: only in the LOD's own IDE file). A new LOD in III/VC gets
that name (house → LODse) unless another model has it or gets it (then the
unique LOD<base> as before); a name already in the files is never changed,
and a LOD without its model at hand never turns LODtower into LODer.
"""

from pathlib import Path
import glob
import os
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.ipl import (default_lod_name, lod_name_for,  # noqa: E402
                      lod_owner_by_tail, lod_pairs_by_name)


@pytest.mark.parametrize("model, game, want", [
    ("house", "VC", "LODse"),
    ("com_park3", "III", "LOD_park3"),        # vanilla III: LOD_park3
    ("ap_tower", "VC", "LODtower"),           # vanilla VC: LODtower
    ("Helipad0", "VC", "LODipad0"),           # case of the rest is kept
    ("house", "SA", "LODhouse"),
    ("abc", "VC", "LODabc"),                  # nothing to compare — see below
])
def test_default_lod_name(model, game, want):
    assert default_lod_name(model, game) == want


def test_pairs_by_name_is_the_games_rule():
    assert lod_pairs_by_name("LODtower", "ap_tower")
    assert lod_pairs_by_name("lodtower", "ap_tower")      # only name+3 counts
    assert not lod_pairs_by_name("LODTower", "ap_tower")  # case-sensitive
    assert not lod_pairs_by_name("LODhouse", "house")     # LOD<name> doesn't
    assert not lod_pairs_by_name("LOD", "abc")            # ≤ 3: nothing left
    for game in ("III", "VC"):
        assert lod_pairs_by_name(default_lod_name("house", game), "house")


def test_name_for_a_new_lod():
    # III/VC, model known: the game's name, whatever the object is called
    assert lod_name_for("LODhouse", "", "house", "house", "VC") == "LODse"
    assert lod_name_for("house_LOD", "", "house", "house", "III") == "LODse"
    assert lod_name_for("LODSE", "", "house", "SE", "VC") == "LODse"
    # … unless the object's own name already pairs
    assert lod_name_for("LODse", "", "house", "se", "VC") == "LODse"
    assert lod_name_for("lodse", "", "house", "se", "VC") == "lodse"
    # SA: unchanged
    assert lod_name_for("LODhouse", "", "house", "house", "SA") == "LODhouse"
    assert lod_name_for("house_LOD", "", "house", "house", "SA") == "LODhouse"


def test_name_in_the_files_is_kept():
    # vanilla / already written: never renamed
    assert lod_name_for("tower_LOD", "LODtower", "ap_tower", "tower", "VC") == "LODtower"
    assert lod_name_for("x_LOD", "tatar_str_1LOD", "tatar_str_1", "x", "SA") == "tatar_str_1LOD"
    # a name that doesn't pair stays too (Add to IDE warns about it)
    assert lod_name_for("LODhouse", "LODhouse", "house", "house", "VC") == "LODhouse"
    # a non-LOD stamp is ignored
    assert lod_name_for("LODhouse", "house", "house", "house", "VC") == "LODse"


def test_model_unknown_never_turns_lodtower_into_loder():
    # a LOD selected without its model: its own base, as before
    assert lod_name_for("LODtower", "", "", "tower", "VC") == "LODtower"
    assert lod_name_for("tower_LOD", "", "", "tower", "III") == "LODtower"


def test_a_taken_name_keeps_lod_base():
    # the game's name has another model (dt_house1 / ne_house1 → one
    # LODhouse1, the vanilla LODhotel): the unique LOD<base> as before
    taken = {"LODhotel", "LODhouse1"}.__contains__
    assert lod_name_for("LODmy_hotel", "", "my_hotel", "my_hotel", "VC",
                        taken) == "LODmy_hotel"
    assert lod_name_for("ne_house1_LOD", "", "ne_house1", "ne_house1", "III",
                        taken) == "LODne_house1"
    assert lod_name_for("LODmy_house", "", "my_house", "my_house", "VC",
                        taken) == "LODhouse"
    # … never the taken name itself (se_LOD of house: LODhouse, not LODse)
    assert lod_name_for("se_LOD", "", "house", "se", "VC", lambda n: True) == "LODhouse"


def test_taken_is_asked_only_for_a_new_name():
    def asked(_name):
        raise AssertionError("asked")
    assert lod_name_for("x", "LODtower", "ap_tower", "x", "VC", asked) == "LODtower"
    assert lod_name_for("LODse", "", "house", "se", "VC", asked) == "LODse"
    assert lod_name_for("LODhouse", "", "house", "house", "SA", asked) == "LODhouse"
    assert lod_name_for("LODtower", "", "", "tower", "VC", asked) == "LODtower"


def test_owner_by_tail_is_the_first_model_by_id():
    # vanilla VC: lodbackbit belongs to lhsbackbit (1410), not havbackbit
    models = [(1451, "havbackbit"), (1410, "lhsbackbit")]
    assert lod_owner_by_tail("lodbackbit", models) == "lhsbackbit"
    assert lod_owner_by_tail("lodbackbit", models[::-1]) == "lhsbackbit"
    # an ID not assigned yet (0) comes after the real ones
    assert lod_owner_by_tail("LODse", [(0, "house"), (700, "morse")]) == "morse"
    assert lod_owner_by_tail("LODse", [(0, "house")]) == "house"
    # the LOD itself and names of ≤ 3 characters never own it
    assert lod_owner_by_tail("LODse", [(5, "LODse"), (9, "abc")]) is None
    assert lod_owner_by_tail("LODse", [(5, "housE")]) is None


# ── vanilla data (skipped when the game is not installed) ──────────

def _ide_rows(root):
    from core.mapsync import IdeDoc
    per = {}
    for p in sorted(set(glob.glob(os.path.join(root, "data", "maps", "**", "*.ide"),
                                  recursive=True))):
        doc = IdeDoc.load(p)
        per[p] = [(r.model_id, r.name, float(getattr(r.obj, "draw_distance", 0) or 0))
                  for r in doc.rows if r.section in ("objs", "tobj")]
    return per


@pytest.mark.parametrize("root, game, at_least", [
    (r"D:\Grand Theft Auto Vice City", "VC", 1055),
    (r"D:\Grand Theft Auto III", "III", 1424),
])
def test_vanilla_lods_pair_by_the_rule(root, game, at_least):
    """Every vanilla LOD (distance > 300) the game pairs: its name is kept,
    and the rule's name for its model pairs too. VC looks in its own IDE."""
    if not os.path.isdir(os.path.join(root, "data", "maps")):
        pytest.skip("no " + game + " install")
    per = _ide_rows(root)
    everything = [(m, n) for rows in per.values() for m, n, _d in rows]
    linked = 0
    for rows in per.values():
        pool = [(m, n) for m, n, _d in rows] if game == "VC" else everything
        for _m, name, dist in rows:
            if not name.lower().startswith("lod") or dist <= 300:
                continue
            hd = lod_owner_by_tail(name, pool)
            if hd is None:
                continue
            linked += 1
            assert lod_name_for("", name, hd, "x", game) == name
            assert lod_pairs_by_name(default_lod_name(hd, game), hd)
    assert linked >= at_least
