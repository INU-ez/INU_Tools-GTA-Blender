"""core/timecyc.py — timecyc.dat GTA III и Vice City.

Формат по re3/reVC ``src/renderer/Timecycle.cpp``: CTimeCycle::Initialise
читает NUMWEATHERS × NUMHOURS (III 4 × 24, VC 7 × 24) строк подряд,
пропуская всё, что начинается с «/». III — 40 чисел (… TopClouds
BottomClouds BlurRGBA), VC — 52 (Amb Amb_Obj Amb_bl Amb_Obj_bl … BlurRGB
WaterRGBA). Ширина VC совпадает с SA+DirMult, так что игра берётся по
числу строк в блоке, а не по ширине.

Синтетика повторяет вёрстку ванильных файлов (заголовок «//// NAME»,
«// 1AM», CRLF); если рядом лежат сами игры, их timecyc.dat гоняются
тоже (см. ``_REAL``)."""

from pathlib import Path
import os
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core import timecyc as tc  # noqa: E402

_REAL = {
    'VC':  r"D:\Grand Theft Auto Vice City\data\timecyc.dat",
    'III': r"D:\Grand Theft Auto III\data\timecyc.dat",
}


# ── Синтетика ────────────────────────────────────────────────────────

def _row_iii(h, w):
    return "\t".join([
        "%d %d %d" % (74 + w, 74, 46),          # amb
        "100 100 105",                          # dir
        "%d %d %d" % (h, 0, 5),                 # sky top — час в R
        "5 5 5", "255 255 0", "5 0 0",          # sky bot, sun core, corona
        "1.0 1.0 1.0", "200 100 0",             # sunsz sprsz sprbght / shdw lightshd treeshd
        "2000.0 100.0 1.0",                     # farclp fogst lightgnd
        "30 20 0", "23 32 33", "3 3 3",         # low / top / bottom clouds
        "152 086 005 80",                       # blur RGBA
    ])


def _row_vc(h, w):
    return "\t".join([
        "%d %d %d" % (55 + w, 55, 45),          # amb
        "95 95 95", "55 55 45", "55 55 45",     # amb_obj, amb_bl, amb_obj_bl
        "255 255 255",                          # dir
        "%d %d %d" % (h, 0, 5),                 # sky top — час в R
        "05 05 05", "255 255 0", "5 0 0",       # sky bot, sun core, corona
        "1.0 1.0 1.0", "200 100 0",
        "2000.0 100.0 1.0",
        "30 20 0", "23 32 33", "3 3 3",
        "056 038 000",                          # blur RGB
        "85 85 65 192",                         # water RGBA
    ])


def _make(tmp_path, game, name="timecyc.dat"):
    weathers = (("SUNNY", "CLOUDY", "RAINY", "FOGGY") if game == 'III' else
                ("SUNNY", "CLOUDY", "RAINY", "FOGGY", "EXTRASUNNY", "RAINY", "EXTRACOLOURS"))
    row = _row_iii if game == 'III' else _row_vc
    lines = []
    for w, wn in enumerate(weathers):
        lines.append("//////////////////////////////////////////////// " + wn)
        lines.append("// Amb     Dir          Sky top")
        for h in range(24):
            lines.append("// " + tc.SLOT_LABELS_24[h])
            lines.append(row(h, w))
        lines.append("//")
    path = tmp_path / name
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode())
    return path


@pytest.mark.parametrize('game', ['III', 'VC'])
def test_detect_and_shape(tmp_path, game):
    cyc = tc.parse(str(_make(tmp_path, game)))
    assert cyc.game == game
    assert cyc.width == (40 if game == 'III' else 52)
    assert len(cyc.weathers) == (4 if game == 'III' else 7)
    assert all(len(w.slots) == 24 for w in cyc.weathers)
    assert cyc.slot_hours == tuple(range(24))
    assert tc.schema_width(cyc.fields) == cyc.width
    assert not any(s.malformed for w in cyc.weathers for s in w.slots)


def test_iii_fields(tmp_path):
    cyc = tc.parse(str(_make(tmp_path, 'III')))
    s = cyc.weathers[1].slots[3]
    assert s.values['amb'] == [75.0, 74.0, 46.0]
    assert s.values['sky_top'] == [3.0, 0.0, 5.0]
    assert s.values['top_clouds'] == [23.0, 32.0, 33.0]
    assert s.values['blur'] == [152.0, 86.0, 5.0, 80.0]
    assert not cyc.has_field('amb_obj') and not cyc.has_field('water')
    assert not cyc.has_field('postfx1')


def test_vc_fields(tmp_path):
    cyc = tc.parse(str(_make(tmp_path, 'VC')))
    s = cyc.weathers[6].slots[23]
    assert s.values['amb'] == [61.0, 55.0, 45.0]
    assert s.values['amb_obj_bl'] == [55.0, 55.0, 45.0]
    assert s.values['sky_top'] == [23.0, 0.0, 5.0]
    assert s.values['blur'] == [56.0, 38.0, 0.0]
    assert s.values['water'] == [85.0, 85.0, 65.0, 192.0]
    assert not cyc.has_field('postfx1') and not cyc.has_field('dir_mult')


def test_vc_width_equals_sa_dirmult_but_rows_decide(tmp_path):
    """52 колонки — и у VC, и у SA с DirectionalMult; отличает число строк."""
    assert tc.detect_game(24, 52) == 'VC'
    assert tc.detect_game(8, 52) == 'SA'
    assert tc.detect_game(24, 40) == 'III'
    assert tc.detect_game(8, 51) == 'SA'


@pytest.mark.parametrize('game', ['III', 'VC'])
def test_untouched_write_is_byte_identical(tmp_path, game):
    path = _make(tmp_path, game)
    before = path.read_bytes()
    cyc = tc.parse(str(path))
    tc.write(cyc, backup=False)
    assert path.read_bytes() == before


@pytest.mark.parametrize('game', ['III', 'VC'])
def test_edit_touches_one_line_and_survives_reparse(tmp_path, game):
    path = _make(tmp_path, game)
    before = path.read_bytes().split(b"\r\n")
    cyc = tc.parse(str(path))
    cyc.weathers[0].slots[7].set('sky_top', [1, 2, 3])
    if game == 'III':
        cyc.weathers[0].slots[7].set('blur', [10, 20, 30, 40])
    tc.write(cyc, backup=False)
    after = path.read_bytes().split(b"\r\n")
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(changed) == 1
    again = tc.parse(str(path))
    assert again.game == game
    assert again.weathers[0].slots[7].values['sky_top'] == [1.0, 2.0, 3.0]
    if game == 'III':
        assert again.weathers[0].slots[7].values['blur'] == [10.0, 20.0, 30.0, 40.0]
    assert len(again.weathers[0].slots[7].raw.split()) == cyc.width


@pytest.mark.parametrize('game', ['III', 'VC'])
def test_hourly_interpolation(tmp_path, game):
    cyc = tc.parse(str(_make(tmp_path, game)))
    assert cyc.interpolate(0, 7.0)['sky_top'][0] == pytest.approx(7.0)
    assert cyc.interpolate(0, 7.5)['sky_top'][0] == pytest.approx(7.5)
    # 23 → 0 через полночь
    assert cyc.interpolate(0, 23.5)['sky_top'][0] == pytest.approx(11.5)


def test_iii_cloudy_header_with_garbage_inside_slashes(tmp_path):
    """Ванильный III: «///////0 0 5/////////// CLOUDY» — имя после
    последнего ряда слэшей, а сама строка данными не считается."""
    path = _make(tmp_path, 'III')
    text = path.read_bytes().decode()
    text = text.replace("//////////////////////////////////////////////// CLOUDY",
                        "///////////////////////0 0 5////////////////////////// CLOUDY")
    path.write_bytes(text.encode())
    cyc = tc.parse(str(path))
    assert cyc.weather_names == ["SUNNY", "CLOUDY", "RAINY", "FOGGY"]
    assert all(len(w.slots) == 24 for w in cyc.weathers)


def test_sa_file_still_sa(tmp_path):
    """8 строк на блок → SA, схема по ширине как раньше."""
    lines = ["//////////// EXTRASUNNY_LA"]
    for label in tc.SLOT_LABELS:
        lines.append("//" + label)
        lines.append(" ".join(["1"] * 51))
    path = tmp_path / "timecyc.dat"
    path.write_text("\r\n".join(lines) + "\r\n")
    cyc = tc.parse(str(path))
    assert cyc.game == 'SA' and cyc.has_field('dir') and cyc.slot_hours == tc.SLOT_HOURS


# ── Реальные файлы игр (если установлены) ─────────────────────────────

@pytest.mark.parametrize('game', ['III', 'VC'])
def test_real_game_file(tmp_path, game):
    src = _REAL[game]
    if not os.path.isfile(src):
        pytest.skip("нет " + src)
    path = tmp_path / "timecyc.dat"
    shutil.copy(src, path)
    before = path.read_bytes()
    cyc = tc.parse(str(path))
    assert cyc.game == game
    assert all(len(w.slots) == 24 for w in cyc.weathers)
    assert len(cyc.weathers) == (4 if game == 'III' else 7)
    assert not any(s.malformed or s.width != cyc.width
                   for w in cyc.weathers for s in w.slots)
    tc.write(cyc, backup=False)
    assert path.read_bytes() == before


# ── textdata_lint: DAT-42 под III/VC ─────────────────────────────────

def test_lint_iii_vc_shapes(tmp_path):
    from core import textdata_lint as L
    for game in ('III', 'VC'):
        cyc = tc.parse(str(_make(tmp_path, game)))
        assert L.check_timecyc(cyc) == ([], []), game
        # короткий файл — fatal, лишний блок — только предупреждение
        cyc.weathers.pop()
        fatal, _ = L.check_timecyc(cyc)
        assert any('DAT-42a' in f for f in fatal)
        cyc = tc.parse(str(_make(tmp_path, game)))
        cyc.weathers.append(cyc.weathers[0])
        fatal, warn = L.check_timecyc(cyc)
        assert fatal == [] and any('DAT-42a' in w for w in warn)


def test_lint_iii_vc_skip_sa_packing_rules(tmp_path):
    """int8/uint8-упаковка — только SA; у III/VC значения лежат int32/float."""
    from core import textdata_lint as L
    cyc = tc.parse(str(_make(tmp_path, 'VC')))
    s = cyc.weathers[0].slots[0]
    s.set('sun_size', 50.0)              # SA: «максимум 12.7»
    s.set('light_on_ground', 100.0)      # SA: «диапазон 0..25.5»
    s.set('far_clip', 100000.0)          # SA: «не влезает в int16»
    fatal, warn = L.check_timecyc(cyc)
    assert fatal == [] and warn == []
    s.set('sky_top', [300, 0, 0])        # цвет вне байта — предупреждение везде
    _, warn = L.check_timecyc(cyc)
    assert any('DAT-42d' in w for w in warn)
