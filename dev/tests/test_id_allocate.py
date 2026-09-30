"""data/id_manager.allocate_ids — Export Map hands out every missing Model
ID in one go: the preset is read once and written once, or not at all
when it runs out of free IDs (nothing half-assigned).

Runs without Blender: the addon is loaded as a synthetic package and
tools/user_data (which imports bpy) is replaced; every test points
_presets_dir at tmp_path.
"""

from pathlib import Path
from types import ModuleType
import importlib
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
_PKG = "inu_idalloc_test_pkg"


def _package():
    pkg = sys.modules.get(_PKG)
    if pkg is None:
        pkg = ModuleType(_PKG)
        pkg.__path__ = [str(ROOT / "INU_tools")]
        pkg.T = lambda s: s
        sys.modules[_PKG] = pkg
        ud = ModuleType(f"{_PKG}.tools.user_data")
        ud.get_user_data_dir = lambda sub: str(ROOT / "_unused" / sub)
        sys.modules[f"{_PKG}.tools.user_data"] = ud
    return pkg


_package()
_im = importlib.import_module(f"{_PKG}.data.id_manager")


@pytest.fixture
def im(tmp_path, monkeypatch):
    monkeypatch.setattr(_im, "_presets_dir", lambda: str(tmp_path))
    _im.set_active_preset("t")
    (tmp_path / "t.txt").write_text(
        "# GTA SA model ID preset: t\n321\n322-foo\n323\n324\n325\n", encoding="utf-8")
    yield _im
    _im.set_active_preset("default")


def test_ids_in_order_first_free_not_in_skip(im):
    assert im.allocate_ids([("a", None), ("b", None)], {323}) == [321, 324]
    used = im.get_used_ids()
    assert used == {321: "a", 322: "foo", 324: "b"}


def test_prefer_taken_when_free_else_first_free(im):
    # 325 is free → the LOD gets it; 322 is taken → first free.
    assert im.allocate_ids([("LODa", 325), ("LODb", 322)]) == [325, 321]
    # The caller checked prefer against its own skip — it is not re-checked.
    assert im.allocate_ids([("x", 323)], {323}) == [323]


def test_out_of_ids_writes_nothing(im, tmp_path):
    before = (tmp_path / "t.txt").read_bytes()
    assert im.allocate_ids([("a", None), ("b", None), ("c", None), ("d", None),
                            ("e", None)]) is None
    assert (tmp_path / "t.txt").read_bytes() == before


def test_header_kept_and_nothing_asked_nothing_written(im, tmp_path):
    before = (tmp_path / "t.txt").read_bytes()
    assert im.allocate_ids([]) == []
    assert (tmp_path / "t.txt").read_bytes() == before
    im.allocate_ids([("a", None)])
    assert (tmp_path / "t.txt").read_text(encoding="utf-8").startswith(
        "# GTA SA model ID preset: t")


def test_id_with_a_taken_duplicate_line_is_not_free(im, tmp_path):
    # Same rule as Preset.is_free (ID Manager): one taken line → taken.
    (tmp_path / "t.txt").write_text("321\n321-foo\n322\n", encoding="utf-8")
    assert im.allocate_ids([("a", None), ("b", 321)]) is None
    assert im.allocate_ids([("a", 321)]) == [322]
