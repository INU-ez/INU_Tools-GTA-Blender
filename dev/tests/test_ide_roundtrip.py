"""Round-trip tests for core/ide.py — IDE text-format read/write covering
all sections: objs, tobj, anim, cars, peds, weap, hier, txdp.

Pure Python."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.ide import (  # noqa: E402
    IdeFile,
    IdeObject,
    IdeAnim,
    IdeCar,
    IdePed,
    IdeWeap,
    IdeHier,
    IdeTxdp,
    read_ide,
    write_ide,
    upsert_ide,
    remove_ide,
    _parse_ped_line,
    _parse_car_line,
)


# ── objs (most common section) ───────────────────────────────────

def test_objs_basic_round_trip(tmp_path):
    p = tmp_path / "objects.ide"
    ide = IdeFile(objects=[
        IdeObject(model_id=1700, model_name="cj_house",
                  txd_name="cj_house", draw_distance=299.0, flags=0),
        IdeObject(model_id=1701, model_name="cj_garage",
                  txd_name="cj_house", draw_distance=200.0, flags=4),
    ])
    write_ide(str(p), ide)
    parsed = read_ide(str(p))
    assert len(parsed.objects) == 2
    assert parsed.objects[0].model_id == 1700
    assert parsed.objects[0].model_name == "cj_house"
    assert parsed.objects[0].txd_name == "cj_house"
    assert abs(parsed.objects[0].draw_distance - 299.0) < 1e-3
    assert parsed.objects[1].flags == 4


def test_objs_flags_preserved(tmp_path):
    """Some flag values are bit-significant (alpha, day/night, etc.)."""
    p = tmp_path / "objs.ide"
    write_ide(str(p), IdeFile(objects=[
        IdeObject(model_id=100, model_name="m", txd_name="t",
                  draw_distance=100.0, flags=0x8000_0001),
    ]))
    parsed = read_ide(str(p))
    assert parsed.objects[0].flags == 0x8000_0001


# ── tobj (timed objects — day/night switch) ──────────────────────

def test_tobj_round_trip(tmp_path):
    p = tmp_path / "timed.ide"
    write_ide(str(p), IdeFile(objects=[
        IdeObject(model_id=2000, model_name="lampday", txd_name="lamps",
                  draw_distance=300.0, flags=0,
                  time_on=6, time_off=20),  # daytime
        IdeObject(model_id=2001, model_name="lampnight", txd_name="lamps",
                  draw_distance=300.0, flags=0,
                  time_on=20, time_off=6),  # nighttime
    ]))
    parsed = read_ide(str(p))
    assert len(parsed.objects) == 2
    a, b = parsed.objects[0], parsed.objects[1]
    assert a.is_timed and b.is_timed
    assert a.time_on == 6 and a.time_off == 20
    assert b.time_on == 20 and b.time_off == 6


# ── anim section ─────────────────────────────────────────────────

def test_anim_round_trip(tmp_path):
    p = tmp_path / "anim.ide"
    write_ide(str(p), IdeFile(anims=[
        IdeAnim(model_id=3000, model_name="brokenelevator",
                txd_name="elevator", anim_file="elevator",
                draw_distance=120.0, flags=0),
    ]))
    parsed = read_ide(str(p))
    assert len(parsed.anims) == 1
    a = parsed.anims[0]
    assert a.model_id == 3000
    assert a.anim_file == "elevator"


# ── cars section ─────────────────────────────────────────────────

def test_cars_round_trip(tmp_path):
    p = tmp_path / "vehicles.ide"
    write_ide(str(p), IdeFile(cars=[
        IdeCar(model_id=400, model_name="landstal", txd_name="landstal",
               veh_type="car", handling_id="LANDSTAL", game_name="LANDSTK",
               anims="null", veh_class="ignore",
               frequency=10, flags=0, comprules=0,
               wheel_id=174, wheel_scale_front=0.83, wheel_scale_rear=0.83,
               wheel_upgrade_class=0),
        IdeCar(model_id=476, model_name="rustler", txd_name="rustler",
               veh_type="plane", handling_id="RUSTLER",
               game_name="RUSTLER", anims="null", veh_class="ignore",
               frequency=10, flags=0, comprules=0,
               wheel_id=-1, wheel_scale_front=1.0, wheel_scale_rear=1.0,
               wheel_upgrade_class=-1),
    ]))
    parsed = read_ide(str(p))
    assert len(parsed.cars) == 2
    landstal, rustler = parsed.cars
    assert landstal.model_id == 400
    assert landstal.handling_id == "LANDSTAL"
    assert landstal.veh_type == "car"
    assert abs(landstal.wheel_scale_front - 0.83) < 1e-3
    assert rustler.veh_type == "plane"
    assert rustler.wheel_id == -1


# ── peds section ─────────────────────────────────────────────────

def test_peds_round_trip(tmp_path):
    p = tmp_path / "peds.ide"
    write_ide(str(p), IdeFile(peds=[
        IdePed(model_id=0, model_name="cj", txd_name="player",
               ped_type="PLAYER1", behaviour="PLAYER1",
               anim_group="man", cars_can_drive="7fffffff",
               flags="0", anim_file="null",
               radio1=4, radio2=4,
               voice_archive="null", voice1="null", voice2="null"),
    ]))
    parsed = read_ide(str(p))
    p0 = parsed.peds[0]
    assert p0.model_name == "cj"
    assert p0.ped_type == "PLAYER1"
    assert p0.cars_can_drive == "7fffffff"


# ── trailing "# comment" on peds/cars lines (III default.ide 39/40) ──

def test_ped_line_trailing_comment_iii():
    """The game's sscanf ignores the tail; the comment words must not
    push the 7-column III line into the SA branch (and fail)."""
    ped = _parse_ped_line("39, prostitute, prostitute, PROSTITUTE, "
                          "STAT_PROSTITUTE, sexywoman, 0\t# dont move this")
    assert ped is not None
    assert ped.model_id == 39
    assert ped.txd_name == "prostitute"
    assert ped.source_game == "III"
    assert ped.cars_can_drive == "0"


def test_car_line_trailing_comment_iii():
    car = _parse_car_line("90, landstal, landstal, car, LANDSTAL, LANDSTK, "
                          "poorfamily, 10, 7, 0, 250, 0.8\t# x")
    assert car is not None
    assert car.model_id == 90
    assert car.anims == "null"
    assert car.wheel_id == 250
    assert abs(car.wheel_scale_front - 0.8) < 1e-6


def test_read_ide_peds_with_trailing_comment(tmp_path):
    p = tmp_path / "default.ide"
    p.write_text(
        "peds\n"
        "38, male01, male01, CIVMALE, STAT_STREET_GUY, man, 0\n"
        "39, prostitute, prostitute, PROSTITUTE, STAT_PROSTITUTE, "
        "sexywoman, 0\t# dont move this\n"
        "40, prostitute2, prostitute2, PROSTITUTE, STAT_PROSTITUTE, "
        "sexywoman, 0\t# dont move this\n"
        "end\n", encoding="utf-8")
    parsed = read_ide(str(p))
    assert [pd.model_id for pd in parsed.peds] == [38, 39, 40]
    assert parsed.peds[2].txd_name == "prostitute2"


def test_read_ide_vanilla_iii_default_peds():
    import pytest
    p = Path(r"D:\Grand Theft Auto III\data\default.ide")
    if not p.is_file():
        pytest.skip("vanilla III install not present")
    ids = {pd.model_id for pd in read_ide(str(p)).peds}
    assert len(ids) == 83
    assert {39, 40} <= ids


# ── weap section ─────────────────────────────────────────────────

def test_weap_round_trip(tmp_path):
    p = tmp_path / "weap.ide"
    write_ide(str(p), IdeFile(weaps=[
        IdeWeap(model_id=321, model_name="ak47", txd_name="ak47",
                anim_name="null", mesh_count=1, draw_distance=100.0),
    ]))
    parsed = read_ide(str(p))
    assert parsed.weaps[0].model_id == 321
    assert parsed.weaps[0].model_name == "ak47"


# ── hier section ─────────────────────────────────────────────────

def test_hier_round_trip(tmp_path):
    p = tmp_path / "hier.ide"
    write_ide(str(p), IdeFile(hiers=[
        IdeHier(model_id=2000, model_name="hi_truth",
                txd_name="hi_truth"),
    ]))
    parsed = read_ide(str(p))
    assert len(parsed.hiers) == 1
    assert parsed.hiers[0].model_name == "hi_truth"


# ── txdp section (TXD parent chain) ──────────────────────────────

def test_txdp_round_trip(tmp_path):
    p = tmp_path / "txdp.ide"
    write_ide(str(p), IdeFile(txdps=[
        IdeTxdp(txd_name="generic", parent_txd_name="genericparent"),
        IdeTxdp(txd_name="vehicle", parent_txd_name="vehicleparent"),
    ]))
    parsed = read_ide(str(p))
    assert len(parsed.txdps) == 2
    assert parsed.txdps[0].txd_name == "generic"
    assert parsed.txdps[1].parent_txd_name == "vehicleparent"


# ── Multi-section file ───────────────────────────────────────────

def test_all_sections_in_one_file(tmp_path):
    """Realistic vehicles.ide with cars + tobj for damage variants."""
    p = tmp_path / "mixed.ide"
    ide = IdeFile(
        objects=[
            IdeObject(model_id=1000, model_name="tree", txd_name="trees",
                      draw_distance=300.0),
        ],
        anims=[
            IdeAnim(model_id=3000, model_name="elev", txd_name="elev",
                    anim_file="elev", draw_distance=100.0),
        ],
        cars=[
            IdeCar(model_id=400, model_name="landstal", txd_name="landstal",
                   handling_id="LANDSTAL", game_name="LANDSTK",
                   wheel_id=174),
        ],
        txdps=[IdeTxdp(txd_name="generic", parent_txd_name="genericparent")],
    )
    write_ide(str(p), ide)
    parsed = read_ide(str(p))
    assert len(parsed.objects) == 1
    assert len(parsed.anims) == 1
    assert len(parsed.cars) == 1
    assert len(parsed.txdps) == 1


# ── upsert / remove operators ────────────────────────────────────

def test_upsert_inserts_and_updates(tmp_path):
    p = tmp_path / "u.ide"
    write_ide(str(p), IdeFile(objects=[
        IdeObject(model_id=100, model_name="old", txd_name="old",
                  draw_distance=100.0),
    ]))

    # Update existing + add new
    inserted, updated = upsert_ide(str(p), [
        IdeObject(model_id=100, model_name="renamed", txd_name="newt",
                  draw_distance=200.0),
        IdeObject(model_id=101, model_name="fresh", txd_name="fresht",
                  draw_distance=150.0),
    ])
    assert inserted == 1
    assert updated == 1

    parsed = read_ide(str(p))
    by_id = {o.model_id: o for o in parsed.objects}
    assert by_id[100].model_name == "renamed"
    assert abs(by_id[100].draw_distance - 200.0) < 1e-3
    assert by_id[101].model_name == "fresh"


def test_remove_drops_entries(tmp_path):
    p = tmp_path / "r.ide"
    write_ide(str(p), IdeFile(objects=[
        IdeObject(model_id=100, model_name="a", txd_name="a",
                  draw_distance=100.0),
        IdeObject(model_id=101, model_name="b", txd_name="b",
                  draw_distance=100.0),
        IdeObject(model_id=102, model_name="c", txd_name="c",
                  draw_distance=100.0),
    ]))
    removed = remove_ide(str(p), {101})
    assert removed == 1
    parsed = read_ide(str(p))
    ids = {o.model_id for o in parsed.objects}
    assert ids == {100, 102}
