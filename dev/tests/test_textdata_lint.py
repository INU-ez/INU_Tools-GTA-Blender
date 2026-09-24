"""core.textdata_lint — pre-write audit of the text data files against what
gta_sa.exe does with them (DAT-* rules from E:\\RE\\addon_check\\textdata_path.md),
plus regressions for the writer fixes from the same engine read:

* W4  — water.dat floats keep vanilla precision (0.05100, 0.00528), X/Y one decimal;
* W5  — enex names are written in double quotes (LoadEntryExit strrchr '"');
* W9  — IDE objs 6-field mesh-count form parsed with LoadObject's re-parse rule;
* W10 — IDE / IPL parsers treat commas as whitespace like LoadLine;
* W18 — timecyc edited slots keep the vanilla column grouping; the short
        RAINY_COUNTRYSIDE line is read the way the engine's sscanf reads it.

Every lint rule gets a passing and a failing case built from synthetic core
structures. The vanilla round-trips run only when the game install is
present (D:\\Grand Theft Auto San Andreas). Pure Python — no Blender.
"""

import os
import shutil
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core import textdata_lint as L                       # noqa: E402
from core.water import (                                  # noqa: E402
    WaterFile, WaterPolygon, WaterVertex, read_water, write_water,
    format_water_line,
)
from core.ipl import (                                    # noqa: E402
    IplFile, IplInstance, IplZone, IplCull, IplGarage, IplEnex, IplAuzo,
    IplOccl, IplTcyc, IplCar, IplPickup, read_ipl, write_ipl,
    _format_enex_line, _parse_enex_line, _parse_inst_line, _format_zone_line,
    _parse_zone_line, _read_binary_ipl, _write_binary_ipl,
)
from core.ide import (                                    # noqa: E402
    IdeFile, IdeObject, IdeAnim, IdeHier, IdeCar, IdePed, IdeWeap, IdeTxdp,
    IdeFx2dfx, read_ide, write_ide, _parse_obj_line, _parse_car_line,
    _parse_ped_line, _format_obj_line,
)
from core import timecyc as tc                            # noqa: E402
from core.zon import Zone, parse_zone_line                # noqa: E402
from core.fxp import (                                    # noqa: E402
    FXFile, FXSystem, FXEmitter, FXInfoBlock, FXCurve, FXKeyframe,
    read_fxp, format_fxp,
)
from core.plants_dat import parse_plants_dat              # noqa: E402

GAME = Path(r"D:\Grand Theft Auto San Andreas")
DATA = GAME / "data"
needs_game = pytest.mark.skipif(not DATA.is_dir(), reason="vanilla SA install not present")


def _has(items, tag):
    return any(tag in s for s in items)


# ═══════════════════════════════════════════════════════════════════
# water.dat
# ═══════════════════════════════════════════════════════════════════

def _v(x, y, z=0.0, fx=0.0, fy=0.0, big=0.051, small=0.102):
    return WaterVertex(x=x, y=y, z=z, speed_x=fx, speed_y=fy, speed_z=big, wave_height=small)


def _quad(x0=0, y0=0, w=100, h=100, flag=1, **kw):
    return WaterPolygon(vertices=[_v(x0, y0, **kw), _v(x0 + w, y0, **kw),
                                  _v(x0, y0 + h, **kw), _v(x0 + w, y0 + h, **kw)], flag=flag)


def _tri(x0=0, y0=0, s=100, flag=1):
    return WaterPolygon(vertices=[_v(x0, y0), _v(x0 + s, y0), _v(x0, y0 + s)], flag=flag)


def test_water_clean_passes():
    assert L.check_water([_quad(), _tri(500, 500)]) == ([], [])


def test_water_vertex_count_fatal():
    bad = WaterPolygon(vertices=[_v(0, 0), _v(1, 0)], flag=1)
    fatal, _ = L.check_water([bad])
    assert _has(fatal, "DAT-43")


def test_water_out_of_world_fatal():
    fatal, _ = L.check_water([_quad(2950, 0, 100, 100)])
    assert _has(fatal, "DAT-45a")


def test_water_flow_range_fatal():
    ok, _ = L.check_water([_quad(fx=1.9)])
    bad, _ = L.check_water([_quad(fx=2.0)])
    assert ok == [] and _has(bad, "DAT-45a")


def test_water_non_integer_coordinate_warns():
    poly = _quad()
    poly.vertices[0].x = 0.5
    fatal, warn = L.check_water([poly])
    assert _has(warn, "DAT-45") and not _has(fatal, "DAT-45b")


def test_water_non_rectangular_quad_fatal():
    poly = _quad()
    poly.vertices[3].x = 150          # skewed corner
    fatal, _ = L.check_water([poly])
    assert _has(fatal, "DAT-45b")


def test_water_degenerate_warns():
    poly = WaterPolygon(vertices=[_v(0, 0), _v(100, 0), _v(0, 0), _v(100, 0)], flag=1)
    _, warn = L.check_water([poly])
    assert _has(warn, "DAT-45b")


def test_water_table_limits_fatal():
    quads = [_quad(i * 4 - 2000, 0, 4, 4) for i in range(302)]
    fatal, _ = L.check_water(quads)
    assert _has(fatal, "WaterQuads")
    tris = [_tri(i * 8 - 2000, 0, 4) for i in range(7)]
    fatal, _ = L.check_water(tris)
    assert _has(fatal, "WaterTriangles")


def test_water_block_grid_warns():
    _, warn = L.check_water([_quad(0, 0, 600, 100)])
    assert _has(warn, "500")


def test_water_flag_range_warns():
    _, warn = L.check_water([_quad(flag=7)])
    assert _has(warn, "DAT-45c")


# W4 — precision
def test_w4_water_line_keeps_vanilla_precision():
    line = format_water_line(_quad(-1584, -1826, 224, 184))
    assert line.startswith("-1584.0 -1826.0 0.00000 0.00000 0.00000 0.05100 0.10200    ")
    assert line.endswith("  1")
    poly = WaterPolygon(vertices=[_v(0, 0, big=0.98244, small=0.00528)] * 3, flag=1)
    assert "0.98244 0.00528" in format_water_line(poly)


def test_w4_water_round_trip_values(tmp_path):
    p = tmp_path / "water.dat"
    write_water(str(p), WaterFile(polygons=[_quad(big=0.19900, small=0.24100, fx=0.00528)]))
    v = read_water(str(p)).polygons[0].vertices[0]
    assert (v.speed_z, v.wave_height, v.speed_x) == (0.199, 0.241, 0.00528)


def test_water_reader_skips_engine_comment_lines(tmp_path):
    p = tmp_path / "water.dat"
    p.write_text("processed\n; comment\n* star\n"
                 "0.0 0.0 0.0 0.0 0.0 0.0 0.0, 4.0 0.0 0.0 0.0 0.0 0.0 0.0, "
                 "0.0 4.0 0.0 0.0 0.0 0.0 0.0  1\n")
    assert len(read_water(str(p)).polygons) == 1


def test_water_reader_accepts_28_token_quad(tmp_path):
    # engine: sscanf of 29 floats == 28 → quad, flags = 1 (vanilla water1.dat)
    p = tmp_path / "water.dat"
    p.write_text(" ".join(["0 0 0 0 0 0 0", "4 0 0 0 0 0 0", "0 4 0 0 0 0 0", "4 4 0 0 0 0 0"]) + "\n")
    polys = read_water(str(p)).polygons
    assert len(polys) == 1 and len(polys[0].vertices) == 4 and polys[0].flag == 1


@needs_game
def test_vanilla_water1_reads_as_quads():
    polys = read_water(str(DATA / "water1.dat")).polygons
    assert polys and all(len(q.vertices) == 4 and q.flag == 1 for q in polys)
    assert L.check_water(polys)[0] == []


@needs_game
def test_w4_vanilla_water_byte_exact(tmp_path):
    src = DATA / "water.dat"
    out = tmp_path / "water.dat"
    write_water(str(out), read_water(str(src)))
    assert out.read_bytes() == src.read_bytes()


@needs_game
def test_vanilla_water_zero_fatals():
    fatal, _ = L.check_water(read_water(str(DATA / "water.dat")))
    assert fatal == []


# ═══════════════════════════════════════════════════════════════════
# IPL
# ═══════════════════════════════════════════════════════════════════

def _inst(mid=1000, idx_lod=-1, **kw):
    d = dict(model_id=mid, model_name="m", interior=0, pos_x=1.0, pos_y=2.0, pos_z=3.0,
             rot_x=0.0, rot_y=0.0, rot_z=0.0, rot_w=1.0, lod_index=idx_lod)
    d.update(kw)
    return IplInstance(**d)


def test_ipl_clean_passes():
    ipl = IplFile(instances=[_inst(1000), _inst(1001, 0)])
    assert L.check_ipl(ipl, {1000, 1001}, filename="x.ipl") == ([], [])


def test_ipl_model_id_range_no_longer_fatal():
    # Ваниль-лимит id (0..19999) убран — у пользователей Fastman92, высокий
    # id сам по себе не фатал (проверка «не определён в IDE» — отдельная).
    fatal, _ = L.check_ipl(IplFile(instances=[_inst(20000)]))
    assert not _has(fatal, "DAT-21")


def test_ipl_undefined_model_fatal_only_with_known_ids():
    ipl = IplFile(instances=[_inst(1234)])
    assert L.check_ipl(ipl)[0] == []
    assert _has(L.check_ipl(ipl, {1})[0], "DAT-21")
    # a single picked IDE is not the whole game: any vanilla IPL mixes
    # instances from several IDEs, so an id outside it is only a warning
    fatal, warnings = L.check_ipl(ipl, {1}, known_complete=False, known_label="LAe2.IDE")
    assert fatal == [] and _has(warnings, "DAT-21") and _has(warnings, "LAe2.IDE")


def test_ipl_lod_index_range_fatal():
    fatal, _ = L.check_ipl(IplFile(instances=[_inst(1, 5)]))
    assert _has(fatal, "DAT-22")


def test_ipl_lod_self_reference_warns():
    _, warn = L.check_ipl(IplFile(instances=[_inst(1, 0)]))
    assert _has(warn, "DAT-22")


def test_ipl_binary_lod_uses_related_text_ipl():
    ipl = IplFile(instances=[_inst(1, 300)])
    assert L.check_ipl(ipl, binary=True, filename="lae_stream0.ipl")[0] == []
    fatal, _ = L.check_ipl(ipl, binary=True, filename="lae_stream0.ipl", related_inst_count=100)
    assert _has(fatal, "DAT-22")


def test_ipl_quaternion_fatal_and_warning():
    fatal, _ = L.check_ipl(IplFile(instances=[_inst(1, rot_w=1.2)]))
    assert _has(fatal, "DAT-23")
    _, warn = L.check_ipl(IplFile(instances=[_inst(1, rot_w=0.5)]))
    assert _has(warn, "DAT-23")


def test_ipl_position_and_interior_warn():
    _, warn = L.check_ipl(IplFile(instances=[_inst(1, pos_x=4000.0)]))
    assert _has(warn, "DAT-25")
    _, warn = L.check_ipl(IplFile(instances=[_inst(1, interior=0x4000)]))
    assert _has(warn, "DAT-24")


def test_ipl_inst_name_overrun_fatal():
    fatal, _ = L.check_ipl(IplFile(instances=[_inst(1, model_name="x" * 24)]))
    assert _has(fatal, "DAT-09")


def test_ipl_inst_count_limits():
    ipl = IplFile(instances=[_inst(1) for _ in range(1001)])
    fatal, warn = L.check_ipl(ipl)
    assert fatal == [] and _has(warn, "DAT-26")
    ipl = IplFile(instances=[_inst(1) for _ in range(4097)])
    assert _has(L.check_ipl(ipl)[0], "DAT-26")


def test_ipl_binary_rules():
    ipl = IplFile(instances=[_inst(1)], culls=[IplCull(flag=1)])
    fatal, warn = L.check_ipl(ipl, binary=True, filename="a_very_long_stream_name0.ipl")
    assert _has(fatal, "DAT-39") and _has(warn, "DAT-37")
    ipl = IplFile(cars=[IplCar(car_id=-1) for _ in range(32768)])
    assert _has(L.check_ipl(ipl, binary=True, filename="x.ipl")[0], "DAT-37")


def test_ipl_grge_rules():
    ipl = IplFile(garages=[IplGarage(name="12345678")])
    assert _has(L.check_ipl(ipl)[0], "DAT-31")
    ipl = IplFile(garages=[IplGarage(name="")])
    assert _has(L.check_ipl(ipl)[1], "DAT-31")
    ipl = IplFile(garages=[IplGarage(name=f"g{i}") for i in range(51)])
    assert _has(L.check_ipl(ipl)[0], "aGarages")
    assert L.check_ipl(IplFile(garages=[IplGarage(name="GARAGE1")]))[0] == []


def test_ipl_enex_rules():
    assert _has(L.check_ipl(IplFile(enexs=[IplEnex(name="x" * 32)]))[0], "DAT-30")
    assert _has(L.check_ipl(IplFile(enexs=[IplEnex(name="two words")]))[1], "DAT-30")
    assert _has(L.check_ipl(IplFile(enexs=[IplEnex(name="longername")]))[1], "strncpy")
    assert L.check_ipl(IplFile(enexs=[IplEnex(name="motel1")])) == ([], [])


def test_ipl_auzo_rules():
    assert _has(L.check_ipl(IplFile(auzos=[IplAuzo(name="x" * 16)]))[0], "DAT-36")
    assert _has(L.check_ipl(IplFile(auzos=[IplAuzo(name="x" * 8)]))[1], "DAT-36")
    spheres = [IplAuzo(name="s", radius=1.0) for _ in range(4)]
    assert _has(L.check_ipl(IplFile(auzos=spheres))[0], "DAT-36")


def test_ipl_cull_rules():
    ipl = IplFile(culls=[IplCull(flag=0)])
    assert _has(L.check_ipl(ipl)[1], "DAT-28")
    ipl = IplFile(culls=[IplCull(flag=0x80) for _ in range(41)])
    assert _has(L.check_ipl(ipl)[0], "DAT-28")


def test_ipl_occl_rules():
    ipl = IplFile(occls=[IplOccl(width_x=0.0, width_y=0.0, height=5.0)])
    assert _has(L.check_ipl(ipl)[1], "DAT-29")
    ipl = IplFile(occls=[IplOccl(width_x=1, width_y=1, height=1) for _ in range(41)])
    assert _has(L.check_ipl(ipl, filename="gen_int.ipl")[1], "DAT-29")
    assert L.check_ipl(ipl, filename="map.ipl")[1] == []


def test_ipl_tcyc_cars_pick_rules():
    assert _has(L.check_ipl(IplFile(tcycs=[IplTcyc() for _ in range(21)]))[0], "DAT-35")
    assert _has(L.check_ipl(IplFile(cars=[IplCar(car_id=2)]))[1], "DAT-34")
    assert L.check_ipl(IplFile(cars=[IplCar(car_id=411)]))[1] == []
    assert _has(L.check_ipl(IplFile(pickups=[IplPickup(pickup_id=30)]))[1], "DAT-33")
    assert L.check_ipl(IplFile(pickups=[IplPickup(pickup_id=9)]))[1] == []


def test_ipl_line_length_fatal():
    fatal, _ = L.check_ipl(IplFile(garages=[IplGarage(name="g", pos_x=1e300, pos_y=1e300)]))
    assert _has(fatal, "DAT-01")


# W5 — enex quoting
def test_w5_enex_written_with_quotes():
    line = _format_enex_line(IplEnex(name="motel1"))
    assert ', "motel1", ' in line
    assert _parse_enex_line(line).name == "motel1"
    # a name that arrives already quoted is not double-quoted
    assert '"motel1"' in _format_enex_line(IplEnex(name='"motel1"'))
    assert '""' not in _format_enex_line(IplEnex(name='"motel1"'))


# W10 — engine tokenizer (IPL)
def test_w10_ipl_accepts_tabs_and_trailing_commas():
    i = _parse_inst_line("1234\tmodel\t0\t1.0 2.0 3.0\t0 0 0 1\t-1,")
    assert i is not None and i.model_id == 1234 and i.lod_index == -1
    assert _parse_inst_line("1234, model, 0, 1.0, 2.0, 3.0, 0, 0, 0, 1, -1").pos_y == 2.0


# zone: 10 fields
def test_zone_line_has_ten_fields():
    line = _format_zone_line(IplZone(name="LA", zone_type=3, level=1))
    assert len(line.replace(',', ' ').split()) == 10
    assert line.endswith(", UNUSED")
    z = _parse_zone_line("LA, 3, 1, 2, 3, 4, 5, 6, 1, KEY1")
    assert z.info == "KEY1"
    assert _format_zone_line(z).endswith(", KEY1")


def test_ipl_zone_section_round_trip(tmp_path):
    p = tmp_path / "z.ipl"
    write_ipl(str(p), IplFile(zones=[IplZone(name="LA", zone_type=3, level=1, info="GXT1")]))
    assert read_ipl(str(p)).zones[0].info == "GXT1"


@needs_game
def test_w5_w10_vanilla_ipl_round_trip_semantic(tmp_path):
    for rel in ("maps/LA/LAe.ipl", "maps/interior/int_LA.ipl", "maps/country/countryS.ipl"):
        src = DATA / rel
        a = read_ipl(str(src))
        out = tmp_path / src.name
        write_ipl(str(out), a)
        b = read_ipl(str(out))
        assert len(b.instances) == len(a.instances)
        assert [e.name for e in b.enexs] == [e.name for e in a.enexs]
        assert all(n and '"' not in n for n in (e.name for e in b.enexs))
        # every written enex line carries the quotes the engine needs
        text = out.read_text()
        for e in b.enexs:
            assert f'"{e.name}"' in text
        for x, y in zip(a.instances, b.instances):
            assert (x.model_id, x.interior, x.lod_index) == (y.model_id, y.interior, y.lod_index)
            assert abs(x.pos_x - y.pos_x) < 1e-5 and abs(x.rot_w - y.rot_w) < 1e-5


@needs_game
def test_vanilla_text_ipls_zero_fatals():
    ipls = list((DATA / "maps").rglob("*.ipl")) + list((DATA / "maps").rglob("*.IPL"))
    assert ipls
    for p in ipls:
        ipl = read_ipl(str(p))
        fatal, _ = L.check_ipl(ipl, None, filename=str(p))
        assert fatal == [], (p.name, fatal)


@needs_game
def test_vanilla_binary_ipl_round_trip_and_lint():
    from core.img import extract_file
    img = GAME / "models" / "gta3.img"
    if not img.is_file():
        pytest.skip("gta3.img missing")
    data = extract_file(str(img), "countrys_stream0.ipl")
    ipl = _read_binary_ipl(data)
    out = _write_binary_ipl(ipl)
    assert out[76:] == data[76:len(out)]          # inst + cars blocks byte-identical
    related = len(read_ipl(str(DATA / "maps/country/countrys.IPL")).instances)
    fatal, _ = L.check_ipl(ipl, None, filename="countrys_stream0.ipl", binary=True,
                           related_inst_count=related)
    assert fatal == []


# ═══════════════════════════════════════════════════════════════════
# zones (.zon)
# ═══════════════════════════════════════════════════════════════════

def test_zones_clean_passes():
    z = parse_zone_line("LA01, 3, 480.0, -3000.0, -500.0, 3000.0, -850.0, 500.0, 1, UNUSED")
    assert L.check_zones([z]) == ([], [])


def test_zones_field_count_fatal():
    z = parse_zone_line("LA01, 3, 480.0, -3000.0, -500.0, 3000.0, -850.0, 500.0, 1")
    assert _has(L.check_zones([z])[0], "DAT-27")


def test_zones_name_rules():
    assert _has(L.check_zones([Zone(name="TOOLONGNAME", zone_type=0)])[1], "strncpy")
    assert _has(L.check_zones([Zone(name="A B", zone_type=0)])[0], "DAT-27")
    assert _has(L.check_zones([Zone(name="A", zone_type=0, gxt="x" * 12)])[0], "DAT-27b")
    assert _has(L.check_zones([Zone(name="A", zone_type=0, gxt="x" * 8)])[1], "DAT-27")


def test_zones_type_and_limits():
    assert _has(L.check_zones([Zone(name="A", zone_type=2)])[1], "DAT-27")
    nav = [Zone(name=f"Z{i}", zone_type=0) for i in range(381)]
    assert _has(L.check_zones(nav)[0], "NavigationZoneArray")
    mp = [Zone(name=f"Z{i}", zone_type=3) for i in range(40)]
    assert _has(L.check_zones(mp)[0], "MapZoneArray")
    assert _has(L.check_zones([Zone(name="A", zone_type=0, x1=40000.0)])[1], "int16")


@needs_game
def test_vanilla_zon_zero_fatals():
    from core.zon import read_zon
    for fn in ("info.zon", "map.zon"):
        assert L.check_zones(read_zon(str(DATA / fn)).zones) == ([], [])


# ═══════════════════════════════════════════════════════════════════
# IDE
# ═══════════════════════════════════════════════════════════════════

def _obj(mid=1000, name="m", txd="t", dd=300.0, flags=0, **kw):
    return IdeObject(model_id=mid, model_name=name, txd_name=txd, draw_distance=dd, flags=flags, **kw)


def test_ide_clean_passes():
    assert L.check_ide(IdeFile(objects=[_obj(1), _obj(2, time_on=7, time_off=20)])) == ([], [])


def test_ide_id_range_removed_duplicate_kept():
    # Ваниль-лимит id (DAT-06) убран (Fastman92) — высокий/отрицательный id
    # больше не фатал. Проверка дублей id в файле (DAT-07) осталась.
    assert not _has(L.check_ide(IdeFile(objects=[_obj(20000)]))[0], "DAT-06")
    assert not _has(L.check_ide(IdeFile(objects=[_obj(96955)]))[0], "DAT-06")
    assert _has(L.check_ide(IdeFile(objects=[_obj(5), _obj(5)]))[1], "DAT-07")


def test_ide_name_lengths():
    assert L.check_ide(IdeFile(objects=[_obj(1, name="x" * 23, txd="y" * 23)]))[0] == []
    assert _has(L.check_ide(IdeFile(objects=[_obj(1, name="x" * 24)]))[0], "DAT-09")
    assert _has(L.check_ide(IdeFile(objects=[_obj(1, txd="y" * 24)]))[0], "DAT-09")
    assert _has(L.check_ide(IdeFile(objects=[_obj(1, name="a b")]))[0], "DAT-08b")


def test_ide_draw_distance_rules():
    assert _has(L.check_ide(IdeFile(objects=[_obj(1, dd=3.9)]))[1], "DAT-08")
    assert _has(L.check_ide(IdeFile(objects=[_obj(1, dd=1.0)]))[1], "DAT-08")
    assert L.check_ide(IdeFile(objects=[_obj(1, dd=4.0)])) == ([], [])
    # fractional dd < 4 as the addon writes it: the engine re-parses the
    # line and reads dd = 0.5 — the post-write audit must not stay silent
    o = _parse_obj_line("1, m, t, 3.5, 8")
    assert (o.draw_distance, o.flags) == (0.5, 8)
    assert _has(L.check_ide(IdeFile(objects=[o]))[1], "DAT-08")
    # multi-mesh: count 2/3 fine, 4 meshes impossible
    assert L.check_ide(IdeFile(objects=[_obj(1, dd=1.0, extra_draw_distances=[2.0])]))[0] == []
    bad = _obj(1, extra_draw_distances=[1.0, 2.0, 3.0])
    assert _has(L.check_ide(IdeFile(objects=[bad]))[0], "DAT-08")


def test_ide_anim_name_rules():
    a = IdeAnim(model_id=1, model_name="m", txd_name="t", anim_file="x" * 16)
    assert _has(L.check_ide(IdeFile(anims=[a]))[0], "DAT-10")
    a.anim_file = "x" * 15
    assert L.check_ide(IdeFile(anims=[a]))[0] == []


def test_ide_store_capacities():
    ide = IdeFile(objects=[_obj(i, time_on=0, time_off=24) for i in range(170)])
    assert _has(L.check_ide(ide)[0], "DAT-07")
    ide = IdeFile(objects=[_obj(i, flags=0x1000) for i in range(71)])
    assert _has(L.check_ide(ide)[0], "damage")
    ide = IdeFile(hiers=[IdeHier(model_id=i, model_name="m", txd_name="t") for i in range(93)])
    assert _has(L.check_ide(ide)[0], "clump")
    ide = IdeFile(weaps=[IdeWeap(model_id=i, model_name="m", txd_name="t") for i in range(52)])
    assert _has(L.check_ide(ide)[0], "weapon")


def test_ide_cars_rules():
    c = IdeCar(model_id=400, model_name="landstal", txd_name="landstal", veh_type="car",
               handling_id="LANDSTAL", game_name="LANDSTAL", anims="null", veh_class="normal")
    assert L.check_ide(IdeFile(cars=[c])) == ([], [])
    c.veh_type = "spaceship"
    assert _has(L.check_ide(IdeFile(cars=[c]))[0], "DAT-13")     # ≥ 8 chars overwrites id
    c.veh_type = "rocket"
    assert _has(L.check_ide(IdeFile(cars=[c]))[1], "DAT-13")     # unknown, ctor default
    c.veh_type = "car"
    c.veh_class = "weird"
    assert _has(L.check_ide(IdeFile(cars=[c]))[1], "DAT-13")
    c.veh_class = "normal"
    c.handling_id = "x" * 16
    assert _has(L.check_ide(IdeFile(cars=[c]))[0], "DAT-09")
    cars = [IdeCar(model_id=i, model_name="m", txd_name="t") for i in range(213)]
    assert _has(L.check_ide(IdeFile(cars=cars))[0], "vehicle")


def test_ide_peds_rules():
    p = IdePed(model_id=7, model_name="male01", txd_name="male01")
    assert L.check_ide(IdeFile(peds=[p])) == ([], [])
    p.txd_name = "x" * 24
    fatal, warn = L.check_ide(IdeFile(peds=[p]))
    assert fatal == [] and _has(warn, "voice1")
    p.txd_name = "t"
    p.voice1 = "x" * 60
    assert _has(L.check_ide(IdeFile(peds=[p]))[0], "DAT-09")
    p.voice1 = "v"
    assert L.check_ide(IdeFile(peds=[p]), anim_groups={"man"})[0] == []
    p.anim_group = "nosuchgroup"
    assert _has(L.check_ide(IdeFile(peds=[p]), anim_groups={"man"})[0], "DAT-12")


def test_ide_txdp_and_2dfx_rules():
    t = IdeTxdp(txd_name="x" * 32, parent_txd_name="p")
    assert _has(L.check_ide(IdeFile(txdps=[t]))[0], "DAT-09")
    fx = [IdeFx2dfx(model_id=1, type_id=0) for _ in range(101)]
    assert _has(L.check_ide(IdeFile(objects=[_obj(1)], fx_2dfx=fx))[0], "DAT-16")
    fx = [IdeFx2dfx(model_id=1), IdeFx2dfx(model_id=2), IdeFx2dfx(model_id=1)]
    fatal, warn = L.check_ide(IdeFile(objects=[_obj(1)], fx_2dfx=fx))
    assert _has(fatal, "DAT-16") and _has(warn, "DAT-16")


def test_ide_line_length_fatal():
    fatal, _ = L.check_ide(IdeFile(objects=[_obj(1, dd=1e300, extra_draw_distances=[1e300])]))
    assert _has(fatal, "DAT-01")


# W9 — LoadObject re-parse rule
def test_w9_six_field_mesh_count_form():
    o = _parse_obj_line("320, airtrain_vlo, generic, 1, 2000, 0")
    assert (o.draw_distance, o.flags, o.extra_draw_distances) == (2000.0, 0, [])
    o = _parse_obj_line("1, m, t, 2, 300, 100, 4")
    assert (o.draw_distance, o.extra_draw_distances, o.flags) == (300.0, [100.0], 4)
    o = _parse_obj_line("1, m, t, 3, 300, 200, 100, 8")
    assert (o.draw_distance, o.extra_draw_distances, o.flags) == (300.0, [200.0, 100.0], 8)
    # dd 3.5 → count 3 → third form: "%d" left ".5", so dd = 0.5,
    # flags kept from pass 1 (the "0" read as a second dd is not a mesh dd)
    o = _parse_obj_line("1, m, t, 3.5, 0")
    assert (o.draw_distance, o.flags, o.extra_draw_distances) == (0.5, 0, [])
    o = _parse_obj_line("100, foo, bar, 3.5, 8")
    assert (o.draw_distance, o.flags) == (0.5, 8)
    o = _parse_obj_line("100, foo, bar, 1.5, 2000, 0")
    assert (o.draw_distance, o.flags) == (0.5, 2000)
    o = _parse_obj_line("1, m, t, 2.5, 4")
    assert (o.draw_distance, o.flags) == (0.5, 4)
    assert _parse_obj_line("1, m, t") is None
    # tobj variants
    o = _parse_obj_line("1, m, t, 1, 2000, 0, 7, 20", timed=True)
    assert (o.draw_distance, o.flags, o.time_on, o.time_off) == (2000.0, 0, 7, 20)
    o = _parse_obj_line("1, m, t, 300, 0, 20, 7", timed=True)
    assert (o.draw_distance, o.time_on, o.time_off) == (300.0, 20, 7)


def test_w9_written_form_is_what_the_engine_reads():
    o = _parse_obj_line("320, airtrain_vlo, generic, 1, 2000, 0")
    line = _format_obj_line(o)
    assert line == "320, airtrain_vlo, generic, 2000, 0"
    assert _parse_obj_line(line).draw_distance == 2000.0


# W10 — engine tokenizer (IDE)
def test_w10_ide_tabs_and_trailing_commas():
    c = _parse_car_line("446, \tsqualo, \tsqualo, \tboat,\t\tSQUALO,\t\tSQUALO, \tnull,\tignore,\t\t10,\t0, \t0,")
    assert c is not None and c.model_name == "squalo" and c.veh_class == "ignore"
    c = _parse_car_line("585,\temperor\t\temperor, \tcar, \t\tEMPEROR, \tEMPEROR, \tnull,\tnormal,\t\t10, \t0,\t0,\t\t-1, 0.74, 0.74,\t\t0")
    assert c is not None and c.txd_name == "emperor" and c.wheel_upgrade_class == 0
    p = _parse_ped_line("51, BMYMOUN, BMYMOUN, CIVMALE, STAT_SENSIBLE_GUY, man,0800,1, man,2,0 PED_TYPE_GEN,VOICE_GEN_BMYMOUN ,VOICE_GEN_BMYMOUN ")
    assert p is not None and p.anim_group == "man" and p.voice2 == "VOICE_GEN_BMYMOUN"
    # a III line (12 numeric-frq tokens) is still detected as III
    c = _parse_car_line("90, landstal, landstal, car, LANDSTAL, LANDSTK, richfamily, 10, 7, 0, 164, 0.8")
    assert c.veh_class == "richfamily" and c.frequency == 10


@needs_game
def test_w10_vanilla_vehicles_and_peds_complete(tmp_path):
    v = read_ide(str(DATA / "vehicles.ide"))
    assert len(v.cars) == 212
    p = read_ide(str(DATA / "peds.ide"))
    assert len(p.peds) == 276
    out = tmp_path / "vehicles.ide"
    write_ide(str(out), v)
    assert len(read_ide(str(out)).cars) == 212


@needs_game
def test_w9_vanilla_default_ide_airtrain():
    ide = read_ide(str(DATA / "default.ide"))
    o = [x for x in ide.objects if x.model_id == 320][0]
    assert (o.draw_distance, o.flags) == (2000.0, 0)


@needs_game
def test_vanilla_ides_zero_fatals():
    from core.gta_dat import parse_gta_dat
    info = parse_gta_dat(str(DATA / "gta.dat"))
    paths = [GAME / p for p in info.ide_paths] + [DATA / "default.ide", DATA / "vehicles.ide", DATA / "peds.ide"]
    for p in paths:
        if not p.is_file():
            continue
        fatal, _ = L.check_ide(read_ide(str(p)))
        assert fatal == [], (p.name, fatal)


# ═══════════════════════════════════════════════════════════════════
# timecyc
# ═══════════════════════════════════════════════════════════════════

_HDR = "//Amb\tAmb_Obj\tDir\tSky top\tSky bot\tSunCore\tSunCorona\t..."


def _tc_row(amb=(22, 22, 22), width=51):
    groups = [
        "%d %d %d" % amb, "220 212 130", "255 255 255", "0 23 24", "0 31 32",
        "255 128 0", "5 0 0", "1.00 1.00 0.30 200 100 0",
        "400.00 100.00 1.00 30 20 0", "3 3 3", "85 85 65 240",
        "255 87 87 87", "255 60 121 122", "0 90 0" + (" 1.00" if width == 52 else ""),
    ]
    return "\t".join(groups)


def _tc_file(tmp_path, weathers=23, rows=8, width=51, extra_lines=None, bad_row=None):
    lines = []
    for w in range(weathers):
        lines.append("//////////// WEATHER_%d" % w)
        lines.append(_HDR)
        for s in range(rows):
            lines.append("//" + tc.SLOT_LABELS[s % 8])
            if bad_row == (w, s):
                lines.append("255\t167 198 223\t255 255 255\t40 40 40\t70 70 70\t0 0 0\t0 0 0\t"
                             "2.00 1.90 0.80 80 80 0\t650.00 123.00 1.00 120 40 40\t0 0 0\t"
                             "132 176 189 240\t255 38 64 99\t255 0 55 20\t90 55 0")
            else:
                lines.append(_tc_row((22 + w, 22 + s, 22), width))
        if extra_lines and w == 0:
            lines.extend(extra_lines)
        lines.append("//")
    p = tmp_path / "timecyc.dat"
    p.write_bytes("\r\n".join(lines).encode())
    return p


def test_timecyc_clean_passes(tmp_path):
    cyc = tc.parse(str(_tc_file(tmp_path)))
    assert L.check_timecyc(cyc) == ([], [])
    cyc = tc.parse(str(_tc_file(tmp_path, width=52)))
    assert L.check_timecyc(cyc) == ([], [])


def test_timecyc_line_count_rules(tmp_path):
    assert _has(L.check_timecyc(tc.parse(str(_tc_file(tmp_path, weathers=22))))[0], "DAT-42a")
    assert _has(L.check_timecyc(tc.parse(str(_tc_file(tmp_path, rows=9))))[1], "DAT-42a")


def test_timecyc_foreign_line_fatal(tmp_path):
    cyc = tc.parse(str(_tc_file(tmp_path, extra_lines=["# a comment the engine will sscanf"])))
    assert _has(L.check_timecyc(cyc)[0], "DAT-42b")


def test_timecyc_value_ranges(tmp_path):
    cyc = tc.parse(str(_tc_file(tmp_path)))
    s = cyc.slot(0, 0)
    s.set('amb', [300, 0, 0])
    s.set('sun_size', 13.0)
    s.set('postfx1', [200, 0, 0, 0])
    s.set('light_on_ground', 30.0)
    _, warn = L.check_timecyc(cyc)
    assert _has(warn, "amb") and _has(warn, "sun_size") and _has(warn, "postfx1") \
        and _has(warn, "light_on_ground")
    s.set('postfx1', [255, 0, 0, 0])      # vanilla value: 255 → 254, harmless
    s.set('amb', [22, 22, 22])
    s.set('sun_size', 1.0)
    s.set('light_on_ground', 1.0)
    assert L.check_timecyc(cyc)[1] == []


# W18 — short line handled like the engine, vanilla grouping kept
def test_w18_short_line_parsed_like_sscanf(tmp_path):
    cyc = tc.parse(str(_tc_file(tmp_path, bad_row=(1, 6))))
    prev = cyc.slot(1, 5)
    bad = cyc.slot(1, 6)
    assert bad.malformed and bad.width == 49
    # 19 ints read normally, the 20th %d takes "2" from "2.00", the 21st fails
    assert bad.get('amb') == [255.0, 167.0, 198.0]
    assert bad.get('sun_corona')[:2] == [0.0, 2.0]
    # everything after that keeps the previous line's values (stale stack)
    assert bad.get('sun_corona')[2] == prev.get('sun_corona')[2]
    assert bad.get('far_clip') == prev.get('far_clip')
    assert bad.get('water') == prev.get('water')
    _, warn = L.check_timecyc(cyc)
    assert _has(warn, "DAT-42c")


def test_w18_edited_slot_uses_vanilla_grouping(tmp_path):
    p = _tc_file(tmp_path)
    cyc = tc.parse(str(p))
    s = cyc.slot(0, 0)
    original = s.raw
    s.set('sky_top', [1, 2, 3])
    line = tc.format_slot(s, cyc.fields)
    assert line.count("\t") == original.count("\t") == 13
    assert line.split("\t")[3] == "1 2 3"
    # untouched values keep the exact vanilla text: every group but sky_top identical
    a, b = original.split("\t"), line.split("\t")
    assert [x for i, x in enumerate(a) if i != 3] == [x for i, x in enumerate(b) if i != 3]


def test_w18_malformed_slot_written_at_full_width(tmp_path):
    p = _tc_file(tmp_path, bad_row=(1, 6))
    cyc = tc.parse(str(p))
    s = cyc.slot(1, 6)
    s.set('sky_top', [7, 8, 9])
    tc.write(cyc, backup=False)
    again = tc.parse(str(p))
    fixed = again.slot(1, 6)
    assert fixed.width == 51 and not fixed.malformed
    assert fixed.get('sky_top') == [7.0, 8.0, 9.0]
    assert fixed.get('amb') == [255.0, 167.0, 198.0]


def test_w18_revert_slot_restores_stale_fill(tmp_path):
    cyc = tc.parse(str(_tc_file(tmp_path, bad_row=(1, 6))))
    s = cyc.slot(1, 6)
    before = dict(s.values)
    s.set('sky_top', [7, 8, 9])
    tc.revert_slot(cyc, s)
    assert s.values == before and s.malformed


def test_w18_partial_int_token_feeds_next_conversion():
    """«%d» on «2.00» leaves «.00»: a following «%d» fails (line stops),
    a following «%f» reads 0.0 and every later column shifts by one."""
    fields = tc.schema_for(52)
    keys = [f[0] for f in fields]
    # int → int boundary (amb.g → amb.b): stale fill from the defaults
    vals, bad = tc._parse_values(["22", "22.00", "22", "1", "2"], fields, None)
    assert bad and vals['amb'] == [22.0, 22.0, 0.0] and vals['amb_obj'] == [0.0, 0.0, 0.0]
    # int → float boundary (pole_shad → far_clip)
    n = sum(f[1] for f in fields[:keys.index('pole_shad')])
    toks = ["5"] * n + ["1.00", "800", "0.5"] + ["7"] * 40
    vals, bad = tc._parse_values(toks, fields, None)
    assert bad and vals['pole_shad'] == [1.0] and vals['far_clip'] == [0.0]
    assert vals[keys[keys.index('far_clip') + 1]] == [800.0]


@needs_game
def test_w18_vanilla_timecyc_all_dirty_byte_exact(tmp_path):
    """Forcing every slot dirty rewrites 183 vanilla lines byte-for-byte;
    only the malformed RAINY_COUNTRYSIDE 8PM line changes (to what the
    engine actually read from it)."""
    for fn in ("timecyc.dat", "timecycp.dat"):
        src = DATA / fn
        dst = tmp_path / fn
        shutil.copy(src, dst)
        cyc = tc.parse(str(dst))
        assert sum(len(w.slots) for w in cyc.weathers) == 184
        mal = []
        for w in cyc.weathers:
            for s in w.slots:
                s.dirty = True
                if s.malformed:
                    mal.append(s.width)
                else:
                    assert tc.format_slot(s, cyc.fields) == s.raw
        tc.write(cyc, backup=False)
        if fn == "timecycp.dat":
            assert dst.read_bytes() == src.read_bytes()
        else:
            assert mal == [49]
            a = src.read_bytes().split(b"\n")
            b = dst.read_bytes().split(b"\n")
            assert len(a) == len(b)
            diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
            assert len(diff) == 1
            assert b[diff[0]].startswith(b"255 167 198\t223 255 255\t255 40 40\t")


@needs_game
def test_vanilla_timecyc_zero_fatals():
    for fn in ("timecyc.dat", "timecycp.dat"):
        fatal, _ = L.check_timecyc(tc.parse(str(DATA / fn)))
        assert fatal == []


# ═══════════════════════════════════════════════════════════════════
# plants.dat
# ═══════════════════════════════════════════════════════════════════

def _plant(**kw):
    from core.plants_dat import DEFAULT_ENTRY
    e = dict(DEFAULT_ENTRY)
    e.update(kw)
    return e


def test_plants_clean_passes():
    assert L.check_plants([_plant()], {"GRASS_SHORT_LUSH"}) == ([], [])


def test_plants_rules():
    assert _has(L.check_plants([_plant(name="NOPE")], {"GRASS_SHORT_LUSH"})[0], "DAT-46a")
    assert L.check_plants([_plant(name="NOPE")])[0] == []          # no table → skipped
    assert _has(L.check_plants([_plant(name="A B")])[0], "DAT-46a")
    e = _plant()
    del e['density']
    assert _has(L.check_plants([e])[0], "18")
    assert _has(L.check_plants([_plant(slot_id=4)])[0], "DAT-46b")
    assert _has(L.check_plants([_plant(slot_id=2)])[1], "DAT-46b")
    assert _has(L.check_plants([_plant(model_id=4)])[0], "DAT-46b")
    assert _has(L.check_plants([_plant(uv_off=4)])[0], "DAT-46b")
    assert _has(L.check_plants([_plant(pcd_id=3)])[1], "DAT-46b")
    assert _has(L.check_plants([_plant(r=300)])[1], "DAT-46b")
    many = [_plant(name=f"S{i}") for i in range(58)]
    assert _has(L.check_plants(many)[0], "57")


@needs_game
def test_vanilla_plants_zero_fatals():
    entries, skipped = parse_plants_dat((DATA / "plants.dat").read_text(encoding="latin-1"))
    assert skipped == []
    assert L.check_plants(entries) == ([], [])


# ═══════════════════════════════════════════════════════════════════
# effects.fxp
# ═══════════════════════════════════════════════════════════════════

def _curve(n=2):
    return FXCurve(keys=[FXKeyframe(time=i / max(n - 1, 1), val=1.0) for i in range(n)])


def _system(name="fx", prims=1, infos=None):
    s = FXSystem(header=[('NAME', name)])
    for _ in range(prims):
        em = FXEmitter(base=[('NAME', 'E'), ('TEXTURE', 'sphere'), ('TEXTURE2', 'NULL')])
        em.infos = infos if infos is not None else [
            FXInfoBlock(type='EMRATE', curves={'RATE': _curve()}),
            FXInfoBlock(type='COLOUR', curves={k: _curve() for k in ('RED', 'GREEN', 'BLUE', 'ALPHA')}),
        ]
        s.emitters.append(em)
    return s


def test_fxp_clean_passes():
    assert L.check_fxp(FXFile(systems=[_system()])) == ([], [])
    assert L.check_fxp(_system(), {"sphere"}) == ([], [])


def test_fxp_rules():
    assert _has(L.check_fxp(_system(prims=9))[0], "DAT-47a")
    assert _has(L.check_fxp(_system(infos=[FXInfoBlock(type='BOGUS')]))[0], "DAT-47b")
    assert _has(L.check_fxp(_system(infos=[FXInfoBlock(type='EMRATE', curves={})]))[0], "DAT-47c")
    big = FXInfoBlock(type='EMRATE', curves={'RATE': _curve(128)})
    assert _has(L.check_fxp(_system(infos=[big]))[0], "NUM_KEYS")
    uneven = FXInfoBlock(type='EMSPEED', curves={'SPEED': _curve(2), 'BIAS': _curve(3)})
    assert _has(L.check_fxp(_system(infos=[uneven]))[0], "DAT-47c")
    uneven = FXInfoBlock(type='EMSPEED', curves={'SPEED': _curve(3), 'BIAS': _curve(2)})
    assert _has(L.check_fxp(_system(infos=[uneven]))[1], "DAT-47c")
    late = FXInfoBlock(type='EMRATE', curves={'RATE': FXCurve(keys=[FXKeyframe(time=128.0, val=1.0)])})
    assert _has(L.check_fxp(_system(infos=[late]))[0], "int16")
    s = _system()
    s.emitters[0].base[1] = ('TEXTURE', 'x' * 32)
    assert _has(L.check_fxp(s)[0], "DAT-47a")
    assert _has(L.check_fxp(_system(), {"other"})[1], "DAT-48")


@needs_game
def test_vanilla_fxp_zero_fatals_and_byte_exact(tmp_path):
    src = GAME / "models" / "effects.fxp"
    fxf = read_fxp(str(src))
    assert L.check_fxp(fxf)[0] == []
    txd = GAME / "models" / "effectsPC.txd"
    if txd.is_file():
        from core.txd import read_txd_texture_names
        assert L.check_fxp(fxf, set(read_txd_texture_names(str(txd)))) == ([], [])
    assert format_fxp(fxf).encode("ascii") == src.read_bytes()


# ═══════════════════════════════════════════════════════════════════
# gta.dat
# ═══════════════════════════════════════════════════════════════════

def test_gta_dat_rules():
    ok = "# c\nIMG MODELS\\GTA_INT.IMG\nIDE DATA\\MAPS\\a.IDE\nCOLFILE 0 MODELS\\COLL\\x.col\nIPL DATA\\MAPS\\a.IPL\n"
    assert L.check_gta_dat(ok) == ([], [])
    assert _has(L.check_gta_dat("IDE  DATA\\a.IDE\n")[0], "DAT-03")
    assert _has(L.check_gta_dat("IDE\tDATA\\a.IDE\n")[0] , "DAT-03") is False
    assert _has(L.check_gta_dat("IPL " + "x" * 64 + "\n")[0], "DAT-05")
    assert _has(L.check_gta_dat("IDE " + "x" * 256 + "\n")[0], "DAT-05")
    assert _has(L.check_gta_dat("IPL a.ipl\nIDE b.ide\n")[1], "DAT-04")
    assert _has(L.check_gta_dat("IDE " + "x" * 200 + "\nEXIT\nIDE  bad\n")[0], "DAT-03") is False


@needs_game
def test_vanilla_gta_dat_zero_fatals():
    text = (DATA / "gta.dat").read_text(encoding="latin-1")
    assert L.check_gta_dat(text)[0] == []
