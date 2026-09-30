"""X Radar tile layout per game (core.game_versions.radar_layout).

X Radar used to shoot every game as 8×8 tiles over ±3000 (750 m tiles,
radar00..63). The games differ:
  SA  — 12×12 tiles radar00..radar143, 500 m over ±3000 (gta_sa.exe
        CRadar::Initialise 0x587FB0, GetTextureCorners 0x584D90:
        x0=(x-6)*500, y0=(5-y)*500, row 0 = north).
  III/VC — 8×8 tiles, 500 m over ±2000 (re3/reVC Radar.cpp).
Pure Python — no Blender.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.game_versions import radar_layout, radar_tile_center  # noqa: E402


def _tile_bounds(idx, grid, half):
    cx, cy = radar_tile_center(idx, grid, half)
    s = half * 2 / grid
    return cx - s / 2, cx + s / 2, cy - s / 2, cy + s / 2


def test_sa_auto_is_12x12_over_3000():
    grid, half = radar_layout('SA')
    assert (grid, half) == (12, 3000.0)
    assert radar_tile_center(0, grid, half) == (-2750.0, 2750.0)
    assert radar_tile_center(143, grid, half) == (2750.0, -2750.0)


def test_sa_tile_matches_game_texture_corners():
    # GetTextureCorners(1, 1): x0=(1-6)*500=-2500, y0=(5-1)*500=2000,
    # the tile spans +500 on both axes. Tile index = x + y*12 = 13.
    grid, half = radar_layout('SA', 0)
    for tx in range(12):
        for ty in range(12):
            x0 = (tx - 6) * 500.0
            y0 = (5 - ty) * 500.0
            assert _tile_bounds(tx + ty * 12, grid, half) == (
                x0, x0 + 500.0, y0, y0 + 500.0)


def test_iii_vc_auto_is_8x8_over_2000():
    for game in ('III', 'VC'):
        grid, half = radar_layout(game)
        assert (grid, half) == (8, 2000.0)
        assert radar_tile_center(0, grid, half) == (-1750.0, 1750.0)
        assert radar_tile_center(63, grid, half) == (1750.0, -1750.0)
        # Every tile is 500 m like the game's RADAR_TILE_SIZE.
        x0, x1, y0, y1 = _tile_bounds(9, grid, half)
        assert (x1 - x0, y1 - y0) == (500.0, 500.0)


def test_manual_grid_is_respected_coverage_by_game():
    assert radar_layout('SA', 16) == (16, 3000.0)
    assert radar_layout('VC', 4) == (4, 2000.0)
    # Unknown game → SA, like profile_for.
    assert radar_layout('XX') == (12, 3000.0)
    assert radar_layout('XX', 8) == (8, 3000.0)


def test_radar_ops_uses_layout_everywhere():
    src = (ROOT / "INU_tools" / "ops" / "radar_ops.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    for cls in ("GTATOOLS_OT_radar_generate", "GTATOOLS_OT_radar_pack_txd"):
        node = next(n for n in tree.body
                    if isinstance(n, ast.ClassDef) and n.name == cls)
        body = ast.get_source_segment(src, node)
        assert "radar_layout(" in body, cls
        # The grid must come from radar_layout, not straight from the
        # setting (0 = auto would divide by zero).
        assert "grid = scn.inu_settings.gtatools_radar_grid" not in body
    assert "map_half = 3000.0" not in src
