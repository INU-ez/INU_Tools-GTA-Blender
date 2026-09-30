"""core/ipl_geom — cull boxes and garage offsets as the game reads them.

SA ``CCullZones::AddCullZone`` (0x72DF70): corner = c − v1 − v2, edges
2·v1 / 2·v2 with v1 = (f3, f4), v2 = (f6, f7) — a box 2|v2| × 2|v1|
rotated by atan2(v2). The old import drew (f6, f4) unrotated: half the
size and no angle. III/VC read the same 11 columns as pos, min, max.
"""

from pathlib import Path
import math
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.ipl import IplCull, IplGarage, _parse_cull_line, _format_cull_line  # noqa: E402
from core.ipl_geom import (  # noqa: E402
    apply_cull_row, cull_box_equal, cull_box_from_row, cull_row,
    cull_row_from_aabb, cull_row_from_box, garage_offsets, garage_points,
)


AXIAL = '1.7363, 29.5882, 198.602, 0, 8.15653, 198.602, 2.4303, 0, 203.101, 1, 0'
ROTATED = ('1640.38, -1899.78, 11.3458, -11.3957, 44.6585, 11.0143, '
           '19.05, 4.81555, 22.1307, 8, 0')


def _row(line):
    return cull_row(_parse_cull_line(line))


def _corners_from_row(row):
    """The game's four XY corners of an SA cull row."""
    cx, cy = row[0], row[1]
    v1 = (row[3], row[4])
    v2 = (row[6], row[7])
    return [(cx + a * v1[0] + b * v2[0], cy + a * v1[1] + b * v2[1])
            for a in (-1, 1) for b in (-1, 1)]


def test_axial_vanilla_line():
    row = _row(AXIAL)
    (cx, cy, cz), size, rot = cull_box_from_row(row, 'SA')
    assert (cx, cy) == (1.7363, 29.5882)
    assert cz == pytest.approx((198.602 + 203.101) / 2)
    assert size == pytest.approx((4.8606, 16.31306, 4.499))
    assert rot == 0.0
    back = cull_row_from_box((cx, cy, cz), size, rot)
    assert back == pytest.approx(row, abs=1e-4)


def test_rotated_vanilla_line():
    row = _row(ROTATED)
    center, size, rot = cull_box_from_row(row, 'SA')
    assert size[0] == pytest.approx(39.298, abs=1e-3)
    assert size[1] == pytest.approx(92.179, abs=1e-3)
    assert math.degrees(rot) == pytest.approx(14.186, abs=1e-3)
    # untouched box is recognised (export then writes the original row)
    f32 = tuple(round(v, 4) for v in center)
    assert cull_box_equal((center, size, rot), (f32, size, rot + 1e-6))
    # edited → rectangle from the box; the line is not strictly
    # rectangular (cos ≈ −0.0022), so compare the corners
    new = cull_row_from_box(center, size, rot)
    for p, q in zip(sorted(_corners_from_row(row)),
                    sorted(_corners_from_row(new))):
        assert p == pytest.approx(q, abs=0.15)


def test_rectangular_rotated_round_trip():
    loc, dims, rot = (100.0, 200.0, 15.0), (10.0, 6.0, 8.0), 0.7
    row = cull_row_from_box(loc, dims, rot)
    c2, s2, r2 = cull_box_from_row(row, 'SA')
    assert c2 == pytest.approx(loc) and s2 == pytest.approx(dims)
    assert r2 == pytest.approx(rot)
    assert cull_row_from_box(c2, s2, r2) == pytest.approx(row, abs=1e-4)


def test_box_equal_wraps_angle_and_detects_edit():
    box = ((0.0, 0.0, 0.0), (2.0, 2.0, 2.0), 0.0)
    assert cull_box_equal(box, ((0, 0, 0), (2, 2, 2), 2 * math.pi - 1e-5))
    assert not cull_box_equal(box, ((0.5, 0, 0), (2, 2, 2), 0.0))
    assert not cull_box_equal(box, ((0, 0, 0), (2, 2, 2), 0.1))


def test_mirror_line_keeps_mirror_fields():
    line = AXIAL.rsplit(',', 1)[0] + ', 0.0, 0.0, -1.0, 10.5'
    c = _parse_cull_line(line)
    assert c.has_mirror
    row = cull_row(c)
    assert cull_box_from_row(row, 'SA')[1] == pytest.approx(
        (4.8606, 16.31306, 4.499))
    out = apply_cull_row(IplCull(flag=c.flag, mirror_vx=c.mirror_vx,
                                 mirror_vy=c.mirror_vy, mirror_vz=c.mirror_vz,
                                 mirror_cm=c.mirror_cm), row)
    assert _format_cull_line(out).split(', ')[-4:] == ['0.0', '0.0', '-1.0', '10.5']


def test_vc_aabb_and_reference_point():
    row = [5.0, 6.0, 7.0, 0.0, 0.0, 0.0, 10.0, 20.0, 4.0]   # pos, min, max
    center, size, rot = cull_box_from_row(row, 'VC')
    assert center == pytest.approx((5.0, 10.0, 2.0))
    assert size == pytest.approx((10.0, 20.0, 4.0)) and rot == 0.0
    # moved by (1, 2, 3), corners given in any order
    new = cull_row_from_aabb([11.0, 2.0, 3.0], [1.0, 22.0, 7.0], row)
    assert new == pytest.approx([6.0, 8.0, 10.0, 1.0, 2.0, 3.0,
                                 11.0, 22.0, 7.0])
    # no imported III/VC row → the point is the box centre
    assert cull_row_from_aabb([0, 0, 0], [2, 4, 6])[:3] == [1.0, 2.0, 3.0]


def test_garage_offsets_follow_the_marker():
    g = IplGarage(pos_x=10, pos_y=20, pos_z=5, line_x=14, line_y=20,
                  cube_x=14, cube_y=26, cube_z=9)
    d_line, d_cube = garage_offsets(g)
    assert d_line == [4, 0] and d_cube == [4, 6, 4]
    (lx, ly), (cx, cy, cz) = garage_points((10, 20, 5), d_line, d_cube)
    assert (lx, ly, cx, cy, cz) == (14, 20, 14, 26, 9)
    # moved marker moves the whole garage
    (lx, ly), (cx, cy, cz) = garage_points((110, 20, 6), d_line, d_cube)
    assert (lx, ly, cx, cy, cz) == (114, 20, 114, 26, 10)
    # turned 90° about Z
    (lx, ly), (cx, cy, cz) = garage_points((10, 20, 5), d_line, d_cube,
                                           math.pi / 2)
    assert (lx, ly) == pytest.approx((10, 24))
    assert (cx, cy, cz) == pytest.approx((4, 24, 9))
