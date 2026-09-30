"""
Geometry of IPL section records that become boxes / markers in the
scene (cull zones, garages). Pure Python, no bpy — unit-tested.

cull, SA (11 or 14 fields). ``CFileLoader::LoadCullZone`` (0x5B4B40)
passes fields 3..8 to ``CCullZones::AddCullZone`` (0x72DF70), which
stores

    corner = (cx - f3 - f6, cy - f4 - f7)
    edge1  = 2 * (f3, f4)        # IplCull.unknown1, .length
    edge2  = 2 * (f6, f7)        # IplCull.width,    .unknown2
    z      = f5 .. f8            # IplCull.bottom .. .top

— a box centred on (cx, cy) with half-axes v1 = (f3, f4) and
v2 = (f6, f7), tested by ``IsPointWithin`` (0x72D850) as two strips.
So it is 2|v2| x 2|v1| and rotated by atan2(v2); 702 of the 1230
vanilla cull.ipl lines are rotated. f2 (center z) is not read.

cull, III/VC (11 fields, re3/reVC ``CFileLoader::LoadCullZone``):
    pos.xyz, min.xyz, max.xyz, flags, wantedLevelDrop
— an axis-aligned box plus a reference point (III clamps it into the
box).

A "row" below is the 9 geometric numbers of a cull line in file order
(fields 0..8); flag / unknown3 / mirror are kept as-is by the caller.
"""

from __future__ import annotations
import math


EPS = 0.01          # metres — same tolerance as core/zon.EPS
ANG_EPS = 1e-3      # radians — float32 rotation noise is ~1e-7
MIN_HEIGHT = 0.1    # a flat zone still gets a visible box

_AABB_GAMES = ('III', 'VC')


def cull_row(c) -> list:
    """The 9 geometric numbers of an ``IplCull`` in file order."""
    return [float(c.center_x), float(c.center_y), float(c.center_z),
            float(c.unknown1), float(c.length), float(c.bottom),
            float(c.width), float(c.unknown2), float(c.top)]


def apply_cull_row(c, row):
    """Write the 9 geometric numbers back into an ``IplCull``."""
    (c.center_x, c.center_y, c.center_z, c.unknown1, c.length,
     c.bottom, c.width, c.unknown2, c.top) = (float(v) for v in row[:9])
    return c


def cull_box_from_row(row, game: str = 'SA'):
    """Scene box of a cull row → ``(center, size, rot_z)``.

    ``size`` is (x, y, z) in the box's own axes, ``rot_z`` in radians."""
    if game in _AABB_GAMES:
        lo = [min(row[3 + k], row[6 + k]) for k in range(3)]
        hi = [max(row[3 + k], row[6 + k]) for k in range(3)]
        center = tuple((lo[k] + hi[k]) / 2 for k in range(3))
        size = (hi[0] - lo[0], hi[1] - lo[1],
                max(hi[2] - lo[2], MIN_HEIGHT))
        return center, size, 0.0
    cx, cy = row[0], row[1]
    v1x, v1y, bottom = row[3], row[4], row[5]
    v2x, v2y, top = row[6], row[7], row[8]
    l1 = math.hypot(v1x, v1y)
    l2 = math.hypot(v2x, v2y)
    if l2 > 1e-9:
        rot = math.atan2(v2y, v2x)
    elif l1 > 1e-9:
        rot = math.atan2(v1y, v1x) - math.pi / 2
    else:
        rot = 0.0
    center = (cx, cy, (bottom + top) / 2)
    size = (2 * l2, 2 * l1, max(top - bottom, MIN_HEIGHT))
    return center, size, rot


def cull_row_from_box(loc, dims, rot_z: float) -> list:
    """SA cull row of a box: centre ``loc``, size ``dims`` (own axes),
    rotated by ``rot_z`` about Z. Always a rectangle; center z = bottom
    (what most vanilla lines carry, the game ignores it)."""
    w, l, h = dims[0], dims[1], dims[2]
    c, s = math.cos(rot_z), math.sin(rot_z)
    bottom = loc[2] - h / 2
    top = loc[2] + h / 2
    row = [loc[0], loc[1], bottom,
           -l / 2 * s, l / 2 * c, bottom,
           w / 2 * c, w / 2 * s, top]
    return [v + 0.0 for v in row]   # no "-0.0" in the file


def cull_row_from_aabb(lo, hi, row=None) -> list:
    """III/VC cull row of a world AABB. ``row`` — the imported III/VC
    row: its reference point keeps its place relative to the box (moved
    with the box centre); without it the point is the box centre."""
    lo, hi = ([min(a, b) for a, b in zip(lo, hi)],
              [max(a, b) for a, b in zip(lo, hi)])
    center = [(lo[k] + hi[k]) / 2 for k in range(3)]
    if row is not None and len(row) >= 9:
        old = [(row[3 + k] + row[6 + k]) / 2 for k in range(3)]
        pos = [row[k] + center[k] - old[k] for k in range(3)]
    else:
        pos = center
    return [float(v) + 0.0 for v in (*pos, *lo, *hi)]


def cull_box_equal(a, b, eps: float = EPS, ang_eps: float = ANG_EPS) -> bool:
    """Same scene box ``(center, size, rot_z)`` up to float32 noise."""
    (ca, sa, ra), (cb, sb, rb) = a, b
    for x, y in zip((*ca, *sa), (*cb, *sb)):
        if abs(x - y) > eps:
            return False
    d = (ra - rb) % (2 * math.pi)
    return min(d, 2 * math.pi - d) <= ang_eps


# ── Garages ───────────────────────────────────────────────────────────
# CGarages::AddOne (0x4471E0) takes the front point (f3, f4) and the
# far corner (f5, f6, f7) as ABSOLUTE coordinates, so the scene marker
# (at the base point f0..f2) keeps them as offsets and carries them
# along when it is moved / rotated about Z.

def garage_offsets(g):
    """(line − pos, cube − pos) of an ``IplGarage``."""
    d_line = [g.line_x - g.pos_x, g.line_y - g.pos_y]
    d_cube = [g.cube_x - g.pos_x, g.cube_y - g.pos_y, g.cube_z - g.pos_z]
    return d_line, d_cube


def garage_points(pos, d_line, d_cube, rot_z: float = 0.0):
    """Absolute front point (x, y) and far corner (x, y, z) of a garage
    whose marker sits at ``pos`` rotated by ``rot_z``."""
    c, s = math.cos(rot_z), math.sin(rot_z)

    def _rot(dx, dy):
        return dx * c - dy * s, dx * s + dy * c

    lx, ly = _rot(d_line[0], d_line[1])
    cx, cy = _rot(d_cube[0], d_cube[1])
    return ((pos[0] + lx, pos[1] + ly),
            (pos[0] + cx, pos[1] + cy, pos[2] + d_cube[2]))
