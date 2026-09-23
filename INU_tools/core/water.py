"""
GTA SA water.dat reader/writer.

Format — text file:
  Line 1: "processed"
  Each subsequent line = one water polygon (3 or 4 vertices):
    For each vertex: X Y Z SpeedX SpeedY SpeedZ WaveHeight
    Last value on line: Flag (0-3)
      0 = Default/Invisible
      1 = Default/Visible
      2 = Shallow/Invisible
      3 = Shallow/Visible

  3 vertices = triangle (21 floats + 1 int = 22 values)
  4 vertices = quad (28 floats + 1 int = 29 values)

No Blender dependency — pure Python.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import math


# ── GTA SA engine limits ────────────────────────────────────────────
# The game renders water on a fixed grid of 500-unit blocks
# (CWaterLevel: WATER_BLOCK_SIZE = 500, a 12x12 grid over the ±3000
# world). Water is registered/looked-up per block, so a single quad
# must fit inside one block: bigger than 500, or straddling a block
# boundary, and the surface renders without a texture in-game.
WATER_BLOCK_SIZE = 500.0
WORLD_HALF = 3000.0          # water is only definable within ±3000
GRID_STEP = 4.0              # side lengths must be multiples of 4


def block_bounds(coord: float) -> tuple[float, float]:
    """Return (min, max) world edges of the 500-block containing ``coord``."""
    b = math.floor(coord / WATER_BLOCK_SIZE)
    return b * WATER_BLOCK_SIZE, (b + 1) * WATER_BLOCK_SIZE


def check_quad_fit(min_x, min_y, max_x, max_y, eps=0.01):
    """Classify a water polygon's XY footprint against the 500-block grid.

    Returns one of:
      'ok'       — ≤500 on both sides AND inside a single block (renders).
      'cross'    — ≤500 but straddles a block boundary (snap to fix).
      'oversize' — wider than 500 on some side (must be split into a grid).
    """
    w = max_x - min_x
    h = max_y - min_y
    if w > WATER_BLOCK_SIZE + eps or h > WATER_BLOCK_SIZE + eps:
        return 'oversize'
    same_block_x = math.floor(min_x / WATER_BLOCK_SIZE) == math.floor((max_x - eps) / WATER_BLOCK_SIZE)
    same_block_y = math.floor(min_y / WATER_BLOCK_SIZE) == math.floor((max_y - eps) / WATER_BLOCK_SIZE)
    if same_block_x and same_block_y:
        return 'ok'
    return 'cross'


@dataclass
class WaterVertex:
    """One vertex of a water polygon."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    speed_x: float = 0.0
    speed_y: float = 0.0
    speed_z: float = 0.0
    wave_height: float = 0.0


@dataclass
class WaterPolygon:
    """One water polygon (3 or 4 vertices)."""
    vertices: List[WaterVertex] = field(default_factory=list)
    flag: int = 1  # 0-3, default visible


@dataclass
class WaterFile:
    """Collection of water polygons."""
    polygons: List[WaterPolygon] = field(default_factory=list)


# ── Reading ─────────────────────────────────────────────────────────

def read_water(filepath: str) -> WaterFile:
    """Parse a water.dat file and return structured data."""
    water = WaterFile()

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for raw_line in f:
            line = raw_line.strip()
            # Engine (0x6EAE80): empty lines and lines whose first
            # non-blank char is ';', '*' or 'p' ("processed") are skipped;
            # '#' kept for files written by other tools.
            if not line or line[0] in ';*p#':
                continue

            # LoadLine turns every ',' into a space before sscanf.
            parts = line.replace(',', ' ').split()
            try:
                values = [float(p) for p in parts]
            except ValueError:
                continue

            poly = WaterPolygon()

            if len(parts) == 22:
                # Triangle (3 vertices + flag)
                for i in range(3):
                    base = i * 7
                    v = WaterVertex(
                        x=values[base], y=values[base + 1], z=values[base + 2],
                        speed_x=values[base + 3], speed_y=values[base + 4],
                        speed_z=values[base + 5], wave_height=values[base + 6],
                    )
                    poly.vertices.append(v)
                poly.flag = int(values[21])

            elif len(parts) in (28, 29):
                # Quad (4 vertices + flag). Engine (0x6EAE80): sscanf of
                # 29 floats == 28 is also a quad, with flag 1 — the whole
                # vanilla water1.dat is written that way.
                for i in range(4):
                    base = i * 7
                    v = WaterVertex(
                        x=values[base], y=values[base + 1], z=values[base + 2],
                        speed_x=values[base + 3], speed_y=values[base + 4],
                        speed_z=values[base + 5], wave_height=values[base + 6],
                    )
                    poly.vertices.append(v)
                poly.flag = int(values[28]) if len(parts) == 29 else 1

            else:
                continue

            water.polygons.append(poly)

    return water


# ── Writing ─────────────────────────────────────────────────────────

def format_water_line(poly: WaterPolygon) -> str:
    """One water.dat record in the vanilla layout.

    X/Y are written with one decimal — the engine ``_ftol``s them to
    integers (AddWaterLevelVertex 0x6E5A40), so nothing past the point
    survives anyway. The five per-vertex parameters (z, flow x/y, big /
    small waves) are written with FIVE decimals exactly like vanilla
    ``data/water.dat`` (``0.05100``, ``0.98244``, ``0.00528``): the old
    ``%.1f`` doubled wave heights (0.051 → 0.1) and zeroed flow speeds
    (0.00528 → 0.0) on every re-export (W4). Vertices are separated by
    four spaces, the flag by two — byte-identical to vanilla.
    """
    parts = []
    for v in poly.vertices:
        parts.append(
            f"{v.x:.1f} {v.y:.1f} {v.z:.5f} "
            f"{v.speed_x:.5f} {v.speed_y:.5f} "
            f"{v.speed_z:.5f} {v.wave_height:.5f}")
    return '    '.join(parts) + f"  {poly.flag}"


def write_water(filepath: str, water: WaterFile) -> int:
    """Write water polygons to a water.dat file. Returns polygon count."""
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write('processed\n')
        for poly in water.polygons:
            f.write(format_water_line(poly) + '\n')
    return len(water.polygons)
