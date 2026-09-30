"""core/fs_ci: game paths spelled the Windows way ("MODELS\\GTA3.IMG") are
found on a case-sensitive file system (CI runs on Linux). Pure Python."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.fs_ci import path_key, resolve  # noqa: E402
from core.gta_dat import img_load_order, resolve_paths, parse_gta_dat  # noqa: E402


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return p


def test_resolve_finds_any_letter_case(tmp_path):
    real = _touch(tmp_path / "models" / "gta3.img")
    got = resolve(os.path.join(str(tmp_path), "MODELS\\GTA3.IMG"))
    assert os.path.isfile(got)
    assert path_key(got) == path_key(str(real))


def test_resolve_keeps_a_missing_path(tmp_path):
    got = resolve(os.path.join(str(tmp_path), "models", "nope.img"))
    assert got == os.path.normpath(os.path.join(str(tmp_path), "models", "nope.img"))
    assert resolve("") == ""


def test_path_key_ignores_case_even_for_missing_files(tmp_path):
    a = os.path.join(str(tmp_path), "MODELS", "GTA_INT.IMG")
    b = os.path.join(str(tmp_path), "models", "gta_int.img")
    assert path_key(a) == path_key(b)


def test_dat_lines_resolve_to_the_real_files(tmp_path):
    _touch(tmp_path / "data" / "maps" / "one.ide")
    img = _touch(tmp_path / "models" / "custom.img")
    _touch(tmp_path / "models" / "gta3.img")
    dat = tmp_path / "data" / "gta.dat"
    dat.write_text("IDE DATA\\MAPS\\ONE.IDE\nIMG MODELS\\CUSTOM.IMG\nIPL DATA\\X.IPL\n")
    info = resolve_paths(str(tmp_path), parse_gta_dat(str(dat)))
    assert all(os.path.isfile(p) for p in info.ide_paths + info.img_paths)
    order = img_load_order(str(tmp_path))
    assert path_key(str(img)) in {path_key(p) for p in order}
    assert os.path.isfile(order[0])          # models/gta3.img, found as spelled on disk
