"""core/gta_dat.game_ide_paths — every IDE the game loads, for all three
games: data/default.dat (vehicles, peds, weapons) first, then gta.dat /
gta_int.dat (SA), gta_vc.dat (VC) or gta3.dat (III). find_all_resources()
reads only gta.dat / gta_int.dat — «Из игры» missed IDs 321-372 / 400-611
in SA and everything in VC / III. Pure Python."""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

import core.gta_dat as gta_dat  # noqa: E402
from core.gta_dat import GAME_DATS, game_ide_paths  # noqa: E402


def _root(tmp_path, dats):
    """Fake game folder: {dat file name: text} under <root>/data."""
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    for name, text in dats.items():
        (tmp_path / "data" / name).write_text(text, encoding="utf-8")
    return str(tmp_path)


def _tail(paths, root):
    """Paths relative to the root, '/'-separated, for comparison."""
    return [os.path.relpath(p, root).replace("\\", "/") for p in paths]


def test_default_dat_is_read_first():
    assert GAME_DATS[0] == "default.dat"
    assert set(GAME_DATS) == {"default.dat", "gta.dat", "gta_int.dat",
                              "gta_vc.dat", "gta3.dat"}


def test_sa_reads_default_and_gta_dat(tmp_path):
    root = _root(tmp_path, {
        "default.dat": "# comment\nIDE data\\default.ide\nIDE data\\vehicles.ide\n"
                       "COLFILE 0 models\\coll\\weapons.col\n",
        "gta.dat": "IDE data\\maps\\x.ide\nIPL data\\maps\\x.ipl\n",
    })
    paths, dats = game_ide_paths(root)
    assert dats == ["default.dat", "gta.dat"]
    assert _tail(paths, root) == ["data/default.ide", "data/vehicles.ide",
                                  "data/maps/x.ide"]
    assert all(os.path.isabs(p) for p in paths)


def test_vc_and_iii_dat(tmp_path):
    vc = _root(tmp_path / "vc", {
        "default.dat": "IDE data\\default.ide\n",
        "gta_vc.dat": "IDE data\\maps\\haiti\\haiti.ide\n",
    })
    paths, dats = game_ide_paths(vc)
    assert dats == ["default.dat", "gta_vc.dat"]
    assert _tail(paths, vc) == ["data/default.ide", "data/maps/haiti/haiti.ide"]
    iii = _root(tmp_path / "iii", {
        "default.dat": "IDE data\\default.ide\n",
        "gta3.dat": "IDE data\\maps\\gta3.ide\n",
    })
    paths, dats = game_ide_paths(iii)
    assert dats == ["default.dat", "gta3.dat"]
    assert _tail(paths, iii) == ["data/default.ide", "data/maps/gta3.ide"]


def test_duplicate_ide_listed_once_any_case(tmp_path):
    root = _root(tmp_path, {
        "default.dat": "IDE data\\default.ide\n",
        "gta.dat": "IDE DATA\\DEFAULT.IDE\nIDE data/default.ide\nIDE data\\maps\\x.ide\n",
    })
    paths, _dats = game_ide_paths(root)
    assert _tail(paths, root) == ["data/default.ide", "data/maps/x.ide"]


def test_missing_ide_files_are_kept(tmp_path):
    # the caller reports them — a silently shorter list would hide it
    root = _root(tmp_path, {"gta.dat": "IDE data\\maps\\nope.ide\n"})
    paths, dats = game_ide_paths(root)
    assert _tail(paths, root) == ["data/maps/nope.ide"] and dats == ["gta.dat"]


def test_unreadable_dat_is_not_listed(tmp_path, monkeypatch):
    # gta.dat locked / no rights: skipped, and not reported as read
    root = _root(tmp_path, {"default.dat": "IDE data\\default.ide\n",
                            "gta.dat": "IDE data\\maps\\x.ide\n"})
    real = gta_dat.parse_gta_dat

    def parse(p):
        if os.path.basename(p) == "gta.dat":
            raise PermissionError(13, "locked", p)
        return real(p)

    monkeypatch.setattr(gta_dat, "parse_gta_dat", parse)
    paths, dats = game_ide_paths(root)
    assert dats == ["default.dat"]
    assert _tail(paths, root) == ["data/default.ide"]


def test_no_dat_files(tmp_path):
    assert game_ide_paths(str(tmp_path)) == ([], [])
    (tmp_path / "data").mkdir()
    assert game_ide_paths(str(tmp_path)) == ([], [])
