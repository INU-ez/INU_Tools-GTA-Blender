"""core/gta_dat.py — порядок IMG-архивов, как их читает игра
(img_load_order / order_archives) и CDIMAGE III/VC в parse_gta_dat.

SA (exe 0x4083C0 / 0x53BC80 / 0x5B9030 / 0x5B82C0): models/gta3.img,
models/gta_int.img, IMG-строки default.dat и gta.dat до первой IPL —
побеждает первый. III/VC (re3/reVC LoadCdDirectory `while(i-- >= 1)`):
gta3.img, CDIMAGE default.dat, CDIMAGE gta3.dat/gta_vc.dat — побеждает
последний; VC читает каталоги на первой IPL, III — после обоих .dat.

Pure Python."""

from pathlib import Path
import os
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.gta_dat import (  # noqa: E402
    dat_game,
    img_load_order,
    order_archives,
    parse_gta_dat,
)


def _game(tmp_path, **dats):
    """Папка игры: data/<имя>.dat из kwargs (gta_vc='...' → data/gta_vc.dat)."""
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    for name, text in dats.items():
        (data / (name + ".dat")).write_text(text, encoding="utf-8")
    return str(tmp_path)


def _p(root, *parts):
    return os.path.join(root, *parts)


def _norm(paths):
    return [os.path.normcase(os.path.normpath(p)) for p in paths]


# ── parse_gta_dat ────────────────────────────────────────────────

def test_parse_gta_dat_takes_cdimage(tmp_path):
    root = _game(tmp_path, gta_vc="CDIMAGE MODELS\\A.IMG\nIMG MODELS\\B.IMG\n"
                                  "IPL DATA\\X.IPL\n")
    info = parse_gta_dat(_p(root, "data", "gta_vc.dat"))
    assert info.img_paths == ["MODELS\\A.IMG", "MODELS\\B.IMG"]
    assert info.ipl_paths == ["DATA\\X.IPL"]


# ── SA: вперёд, первый выигрывает ───────────────────────────────

def test_sa_order_forward(tmp_path):
    root = _game(tmp_path, gta="IMG MODELS\\X.IMG\n")
    assert _norm(img_load_order(root)) == _norm([
        _p(root, "models", "gta3.img"), _p(root, "models", "gta_int.img"),
        _p(root, "MODELS", "X.IMG")])


def test_sa_img_after_first_ipl_is_never_read(tmp_path):
    root = _game(tmp_path, gta=(
        "IMG MODELS\\CUSTOM.IMG\n"
        "IMG MODELS\\GTA_INT.IMG\n"      # в exe пропускается — уже слот 1
        "IPL DATA\\X.IPL\n"
        "IMG MODELS\\LATE.IMG\n"))
    assert _norm(img_load_order(root)) == _norm([
        _p(root, "models", "gta3.img"), _p(root, "models", "gta_int.img"),
        _p(root, "MODELS", "CUSTOM.IMG")])


def test_sa_default_dat_first_and_exit_stops(tmp_path):
    root = _game(tmp_path,
                 default="# comment\nIMG MODELS\\D.IMG\n",
                 gta="img models\\a.img\nEXIT\nIMG MODELS\\B.IMG\n")
    assert _norm(img_load_order(root)) == _norm([
        _p(root, "models", "gta3.img"), _p(root, "models", "gta_int.img"),
        _p(root, "MODELS", "D.IMG"), _p(root, "models", "a.img")])


def test_sa_last_directory_read_counts(tmp_path):
    # IPL в default.dat читает каталоги раньше, но на первой IPL gta.dat
    # игра читает их снова — всё зарегистрированное до неё.
    root = _game(tmp_path,
                 default="IMG MODELS\\D1.IMG\nIPL DATA\\Z.IPL\nIMG MODELS\\D2.IMG\n",
                 gta="IMG MODELS\\G1.IMG\nIPL DATA\\X.IPL\nIMG MODELS\\G2.IMG\n")
    assert _norm(img_load_order(root)) == _norm([
        _p(root, "models", "gta3.img"), _p(root, "models", "gta_int.img"),
        _p(root, "MODELS", "D1.IMG"), _p(root, "MODELS", "D2.IMG"),
        _p(root, "MODELS", "G1.IMG")])


# ── III/VC: назад, последний CDIMAGE выигрывает ─────────────────

_ABC = ("CDIMAGE MODELS\\A.IMG\n"
        "CDIMAGE MODELS\\B.IMG\n"
        "IPL DATA\\X.IPL\n"
        "CDIMAGE MODELS\\C.IMG\n")


def test_vc_last_cdimage_wins_and_stops_at_ipl(tmp_path):
    root = _game(tmp_path, gta_vc=_ABC)
    assert _norm(img_load_order(root)) == _norm([
        _p(root, "MODELS", "B.IMG"), _p(root, "MODELS", "A.IMG"),
        _p(root, "models", "gta3.img")])


def test_vc_ide_lines_between_cdimage(tmp_path):
    root = _game(tmp_path,
                 default="IDE DATA\\X.IDE\n",
                 gta_vc=("CDIMAGE MODELS\\A.IMG\nIDE DATA\\MAPS\\Y.IDE\n"
                         "CDIMAGE MODELS\\B.IMG\nIPL DATA\\Y.IPL\n"
                         "CDIMAGE MODELS\\C.IMG\n"))
    assert _norm(img_load_order(root)) == _norm([
        _p(root, "MODELS", "B.IMG"), _p(root, "MODELS", "A.IMG"),
        _p(root, "models", "gta3.img")])


def test_iii_reads_all_cdimage(tmp_path):
    root = _game(tmp_path, gta3=_ABC)
    assert _norm(img_load_order(root)) == _norm([
        _p(root, "MODELS", "C.IMG"), _p(root, "MODELS", "B.IMG"),
        _p(root, "MODELS", "A.IMG"), _p(root, "models", "gta3.img")])


def test_vc_default_dat_cdimage_below_main_dat(tmp_path):
    root = _game(tmp_path, default="CDIMAGE MODELS\\D.IMG\n",
                 gta_vc="CDIMAGE MODELS\\A.IMG\n")
    assert _norm(img_load_order(root)) == _norm([
        _p(root, "MODELS", "A.IMG"), _p(root, "MODELS", "D.IMG"),
        _p(root, "models", "gta3.img")])


def test_vc_repeat_counts_by_later_registration(tmp_path):
    root = _game(tmp_path, gta_vc="CDIMAGE MODELS\\A.IMG\nCDIMAGE models\\gta3.img\n")
    assert _norm(img_load_order(root)) == _norm([
        _p(root, "models", "gta3.img"), _p(root, "MODELS", "A.IMG")])


def test_no_game_dat(tmp_path):
    assert img_load_order(_game(tmp_path)) == []


# ── order_archives ───────────────────────────────────────────────

def test_order_archives_vc(tmp_path):
    root = _game(tmp_path, gta_vc=_ABC)
    gta3 = _p(root, "models", "gta3.img")
    a, b, c = (_p(root, "MODELS", n) for n in ("A.IMG", "B.IMG", "C.IMG"))
    # C после IPL игра не читает — в хвост, как незаявленный.
    assert _norm(order_archives([gta3, a, b, c], root)) == _norm([b, a, gta3, c])


def test_order_archives_sa_unknown_last_alphabetical(tmp_path):
    root = _game(tmp_path, gta="IMG MODELS\\CUSTOM.IMG\nIPL DATA\\X.IPL\n")
    gta3 = _p(root, "models", "gta3.img")
    gta_int = _p(root, "models", "gta_int.img")
    custom = _p(root, "MODELS", "CUSTOM.IMG")
    backup = _p(root, "backup", "gta3.img")
    zzz = _p(root, "zzz", "other.img")
    got = order_archives([zzz, custom, backup, gta_int, gta3, custom], root)
    assert _norm(got) == _norm([gta3, gta_int, custom, backup, zzz])


def test_order_archives_without_game_root(tmp_path):
    a = str(tmp_path / "b" / "x.img")
    b = str(tmp_path / "a" / "y.img")
    assert order_archives([a, b, a], "") == [b, a]
    assert order_archives([a, b], str(tmp_path / "missing")) == [b, a]


# ── dat_game: III отличается от VC только папкой игры ───────────

def test_dat_game(tmp_path):
    assert dat_game("") is None
    assert dat_game(_game(tmp_path / "none")) is None
    assert dat_game(_game(tmp_path / "iii", default="", gta3="")) == "III"
    assert dat_game(_game(tmp_path / "vc", default="", gta_vc="")) == "VC"
    assert dat_game(_game(tmp_path / "sa", default="", gta="")) == "SA"
    # тот же выбор, что у img_load_order: gta.dat старше gta_vc/gta3
    assert dat_game(_game(tmp_path / "mix", gta="", gta3="")) == "SA"
    assert dat_game(_game(tmp_path / "vc3", gta_vc="", gta3="")) == "VC"


# ── ванильная SA (если установлена) ─────────────────────────────

GAME = Path(r"D:\Grand Theft Auto San Andreas")
needs_game = pytest.mark.skipif(not (GAME / "data" / "gta.dat").is_file(),
                                reason="vanilla SA install not present")


@needs_game
def test_vanilla_sa_shared_txd_taken_from_gta3():
    """barrier.txd и ещё 3 TXD лежат и в gta3.img, и в gta_int.img —
    игра (и импорт) берёт копию из gta3.img."""
    from core.img import read_directory
    root = str(GAME)
    order = order_archives([_p(root, "models", "gta_int.img"),
                            _p(root, "models", "gta3.img")], root)
    index = {}
    for arch in order:
        for e in read_directory(arch):
            index.setdefault(e.name.lower(), arch)
    assert os.path.basename(index["barrier.txd"]).lower() == "gta3.img"
