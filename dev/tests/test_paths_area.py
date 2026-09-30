"""Auto-split of bare path nodes into nodes<N>.dat (Export Path Nodes, objects
without `nodes_filename`).

The operator used to compute the area as gy = (3000 - y) / 750, i.e. with Y
flipped, so a node in the south-west corner landed in nodes56.dat instead of
nodes0.dat. The game's CPathFind::FindX/YRegionForCoors (0x44D890 /
0x44D8C0) use (v + 3000) / 750 on both axes — core.paths.get_area_id — and
the split now goes through core.paths.split_nodes_by_area. Pure Python — no
Blender.
"""

import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.paths import (                                  # noqa: E402
    get_area_id, split_nodes_by_area, write_nodes, read_nodes,
    PATH_NODE_SIZE, NODELINK_FILLER_BYTES, PATH_INTERSECTION_TRAILING,
)


def test_area_id_corners_not_mirrored():
    # South-west → 0, south-east → 7, north-west → 56, north-east → 63.
    assert get_area_id(-2999, -2999) == 0
    assert get_area_id(2999, -2999) == 7
    assert get_area_id(-2999, 2999) == 56
    assert get_area_id(2999, 2999) == 63
    # Outside ±3000 clamps to the edge cell like the game's 0..7 clamp.
    assert get_area_id(-5000, 5000) == 56
    assert get_area_id(5000, -5000) == 7


def test_split_uses_game_area_and_fills_ids():
    pts = [
        ('nodes_ped', -2999.0, -2999.0, 1.0),       # area 0
        ('nodes_vehicle', -2990.0, -2990.0, 2.0),   # area 0
        ('nodes_vehicle', -2999.0, 2999.0, 3.0),    # area 56 (was 0)
        ('nodes_navi', 100.0, 100.0, 0.0),          # skipped, no file
    ]
    zones = split_nodes_by_area(pts)
    assert sorted(zones) == [0, 56]

    z0 = zones[0]
    assert [n.z for n in z0.vehicle_nodes] == [2.0]
    assert [n.z for n in z0.ped_nodes] == [1.0]
    # Running index, vehicle nodes first — as in vanilla nodes*.dat.
    assert [n.node_id for n in z0.vehicle_nodes + z0.ped_nodes] == [0, 1]
    assert all(n.area_id == 0 for n in z0.vehicle_nodes + z0.ped_nodes)
    assert z0.vehicle_nodes[0].is_vehicle and not z0.ped_nodes[0].is_vehicle
    assert z0.parsed_extras and not z0.fla4

    z56 = zones[56]
    assert [n.area_id for n in z56.vehicle_nodes] == [56]
    assert [n.node_id for n in z56.vehicle_nodes] == [0]


def test_split_area_follows_quantized_position(tmp_path):
    # write_nodes stores int(v * 8): -750.05 → -750.0 (row 3, not row 2),
    # -0.05 → 0.0 (column 4, not 3). The file must match the stored position.
    zones = split_nodes_by_area([('nodes_vehicle', -0.05, -750.05, 0.0)])
    assert sorted(zones) == [4 + 3 * 8]
    path = tmp_path / "nodes28.dat"
    write_nodes(str(path), zones[28])
    n, = read_nodes(str(path)).vehicle_nodes
    assert get_area_id(n.x, n.y) == n.area_id == 28


def test_split_navi_only_opens_no_file():
    assert split_nodes_by_area([('nodes_navi', 0.0, 0.0, 0.0)]) == {}


def test_split_fla4_flag_passes_through():
    zones = split_nodes_by_area([('nodes_ped', 0.0, 0.0, 0.0)], fla4=True)
    assert all(nf.fla4 for nf in zones.values())


def test_split_file_has_tail_and_reads_back(tmp_path):
    pts = [('nodes_vehicle', 10.0, 20.0, 5.0),
           ('nodes_vehicle', 12.0, 22.0, 5.0),
           ('nodes_ped', 11.0, 21.0, 5.0)]
    zones = split_nodes_by_area(pts)
    (area, nf), = zones.items()
    assert area == get_area_id(10.0, 20.0) == 36

    path = tmp_path / f"nodes{area}.dat"
    assert write_nodes(str(path), nf) == 3
    # Header + nodes + 768-byte filler + section-7 padding (0 links).
    assert os.path.getsize(path) == (
        20 + 3 * PATH_NODE_SIZE
        + NODELINK_FILLER_BYTES + PATH_INTERSECTION_TRAILING)
    data = path.read_bytes()
    assert struct.unpack_from('<5I', data, 0) == (3, 2, 1, 0, 0)

    back = read_nodes(str(path))
    nodes = back.vehicle_nodes + back.ped_nodes
    assert [n.area_id for n in nodes] == [36, 36, 36]
    assert [n.node_id for n in nodes] == [0, 1, 2]
    assert [(n.x, n.y) for n in back.ped_nodes] == [(11.0, 21.0)]
