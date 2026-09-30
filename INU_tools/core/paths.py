"""
GTA SA path file readers/writers.

Supported formats:
  - paths.ipl   — path definitions for gta.dat (text, groups of 12 nodes)
  - tracks.dat  — train rail paths (text)
  - nodes*.dat  — compiled ped/vehicle navigation nodes (binary)

No Blender dependency — pure Python.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import struct


# ═══════════════════════════════════════════════════════════════════════
# FLIGHT PATHS (flight.dat)
# ═══════════════════════════════════════════════════════════════════════
#
# Text file format:
#   Each line: X, Y, Z  (comma-separated floats)
#   Empty line = end of current path, start of next
#   Planes follow waypoints sequentially, then loop.

@dataclass
class FlightPoint:
    """One waypoint in a flight path."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class FlightPath:
    """One complete flight route."""
    points: List[FlightPoint] = field(default_factory=list)


@dataclass
class FlightFile:
    """Collection of flight paths."""
    paths: List[FlightPath] = field(default_factory=list)


def read_flight(filepath: str) -> FlightFile:
    """Parse flight.dat and return structured data."""
    result = FlightFile()
    current = FlightPath()

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                # Empty line = end of current path
                if current.points:
                    result.paths.append(current)
                    current = FlightPath()
                continue

            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                try:
                    pt = FlightPoint(
                        x=float(parts[0]),
                        y=float(parts[1]),
                        z=float(parts[2]),
                    )
                    current.points.append(pt)
                except ValueError:
                    continue

    # Last path if file doesn't end with empty line
    if current.points:
        result.paths.append(current)

    return result


def write_flight(filepath: str, data: FlightFile) -> int:
    """Write flight paths to flight.dat. Returns path count."""
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        for i, path in enumerate(data.paths):
            for pt in path.points:
                f.write(f"{pt.x:.4f}, {pt.y:.4f}, {pt.z:.4f}\n")
            # Empty line between paths
            if i < len(data.paths) - 1:
                f.write('\n')

    return len(data.paths)


# ═══════════════════════════════════════════════════════════════════════
# PATHS.IPL (path definitions for gta.dat)
# ═══════════════════════════════════════════════════════════════════════
#
# Text file format (IPL with 'path' section):
#   path
#   GroupType, ExternalIndex     ← 0=ped, 1=vehicle
#   <tab>NodeType, LinkID, AreaID, X, Y, Z, Unknown, Width, LeftLanes, RightLanes, MedianWidth, Flags, SpawnRate
#   ...exactly 12 nodes per group...
#   end
#
# NodeType: 0=empty/unused, 1=external link, 2=internal node
# Groups always have 12 nodes; unused slots filled with NodeType=0

NODES_PER_GROUP = 12


@dataclass
class PathIPLNode:
    """One node in a paths.ipl group."""
    node_type: int = 0       # 0=empty, 1=external, 2=internal
    link_id: int = -1        # Next node index (-1 = none)
    area_id: int = 0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    unknown: float = 0.0
    width: int = 1
    left_lanes: int = 1
    right_lanes: int = 1
    median_width: int = 0
    flags: int = 1
    spawn_rate: int = 0


@dataclass
class PathIPLGroup:
    """One group of 12 nodes (vehicle or ped path)."""
    group_type: int = 1      # 0=ped, 1=vehicle
    external_index: int = -1
    nodes: List[PathIPLNode] = field(default_factory=list)


@dataclass
class PathIPLFile:
    """Collection of path groups from a paths.ipl file."""
    groups: List[PathIPLGroup] = field(default_factory=list)


# ── PathIPLNode.flags bit constants ─────────────────────────────────
#
# Based on SA path-node reverse-engineering (GTAMods wiki, Fastman92):
#   bits 0-3   : speed limit           (0 = slow, higher = faster)
#   bits 4-7   : special behaviour     (traffic lights encoded here)
#   bits 8-11  : traffic light kind    (0 none, 1 normal, 2 rail, 3 bus)
#   bit 12     : roadblock             (cops spawn barriers here)
#   bits 13-15 : reserved

PATH_FLAG_ROADBLOCK       = 1 << 12
PATH_FLAG_TRAFFIC_MASK    = 0xF << 8
PATH_FLAG_TRAFFIC_SHIFT   = 8
PATH_FLAG_SPEED_MASK      = 0xF
PATH_FLAG_BEHAVIOUR_MASK  = 0xF << 4
PATH_FLAG_BEHAVIOUR_SHIFT = 4

TRAFFIC_LIGHT_NONE   = 0
TRAFFIC_LIGHT_NORMAL = 1
TRAFFIC_LIGHT_RAIL   = 2
TRAFFIC_LIGHT_BUS    = 3


def decode_node_flags(flags: int) -> dict:
    """Expand the packed flags int into a readable dict."""
    return {
        'speed_limit': flags & PATH_FLAG_SPEED_MASK,
        'behaviour': (flags & PATH_FLAG_BEHAVIOUR_MASK) >> PATH_FLAG_BEHAVIOUR_SHIFT,
        'traffic_light': (flags & PATH_FLAG_TRAFFIC_MASK) >> PATH_FLAG_TRAFFIC_SHIFT,
        'roadblock': bool(flags & PATH_FLAG_ROADBLOCK),
    }


def encode_node_flags(*, speed_limit: int = 0, behaviour: int = 0,
                      traffic_light: int = 0, roadblock: bool = False,
                      keep_bits: int = 0) -> int:
    """Pack individual fields back into the flags int. `keep_bits` lets
    callers preserve unknown bits read from an existing file."""
    v = keep_bits & ~(PATH_FLAG_SPEED_MASK | PATH_FLAG_BEHAVIOUR_MASK
                      | PATH_FLAG_TRAFFIC_MASK | PATH_FLAG_ROADBLOCK)
    v |= speed_limit & PATH_FLAG_SPEED_MASK
    v |= (behaviour << PATH_FLAG_BEHAVIOUR_SHIFT) & PATH_FLAG_BEHAVIOUR_MASK
    v |= (traffic_light << PATH_FLAG_TRAFFIC_SHIFT) & PATH_FLAG_TRAFFIC_MASK
    if roadblock:
        v |= PATH_FLAG_ROADBLOCK
    return v


def read_paths_ipl(filepath: str) -> PathIPLFile:
    """Parse a paths.ipl file (path section only)."""
    result = PathIPLFile()

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    in_path = False
    current_group = None

    for raw_line in lines:
        line = raw_line.strip()

        if line == 'path':
            in_path = True
            continue
        if line == 'end' and in_path:
            if current_group and current_group.nodes:
                result.groups.append(current_group)
                current_group = None
            in_path = False
            continue
        if not in_path:
            continue

        # Tab-indented = node line, otherwise = group header
        if raw_line.startswith('\t') or raw_line.startswith('  '):
            # Node line
            if current_group is None:
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 13:
                try:
                    node = PathIPLNode(
                        node_type=int(parts[0]),
                        link_id=int(parts[1]),
                        area_id=int(parts[2]),
                        x=float(parts[3]),
                        y=float(parts[4]),
                        z=float(parts[5]),
                        unknown=float(parts[6]),
                        width=int(parts[7]),
                        left_lanes=int(parts[8]),
                        right_lanes=int(parts[9]),
                        median_width=int(parts[10]),
                        flags=int(parts[11]),
                        spawn_rate=int(parts[12]),
                    )
                    current_group.nodes.append(node)
                except ValueError:
                    continue
        else:
            # Group header: GroupType, ExternalIndex
            if current_group and current_group.nodes:
                result.groups.append(current_group)
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                try:
                    current_group = PathIPLGroup(
                        group_type=int(parts[0]),
                        external_index=int(parts[1]),
                    )
                except ValueError:
                    current_group = None

    if current_group and current_group.nodes:
        result.groups.append(current_group)

    return result


def write_paths_ipl(filepath: str, data: PathIPLFile) -> int:
    """Write path groups to a paths.ipl file. Returns group count."""
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# IPL generated by INU Tools\n')
        f.write('inst\nend\ncull\nend\npath\n')

        for group in data.groups:
            f.write(f"{group.group_type}, {group.external_index}\n")

            # Write nodes, pad to 12
            for i in range(NODES_PER_GROUP):
                if i < len(group.nodes):
                    n = group.nodes[i]
                    f.write(f"\t{n.node_type}, {n.link_id}, {n.area_id}, "
                            f"{n.x:.4g}, {n.y:.4g}, {n.z:.6g}, {n.unknown:.4g}, "
                            f"{n.width}, {n.left_lanes}, {n.right_lanes}, "
                            f"{n.median_width}, {n.flags}, {n.spawn_rate}\n")
                else:
                    # Empty node
                    f.write("\t0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0\n")

        f.write('end\n')

    return len(data.groups)


# ═══════════════════════════════════════════════════════════════════════
# TRAIN TRACKS (tracks.dat, tracks2.dat, tracks3.dat, tracks4.dat)
# ═══════════════════════════════════════════════════════════════════════
#
# Text file format:
#   Line 1: node count (integer)
#   Each subsequent line: X Y Z Flag
#     X, Y, Z = position (floats)
#     Flag = 0 or 1 (0 = normal, 1 = station/stop)
#
# tracks.dat  = track 1 (main LS-SF-LV loop)
# tracks2.dat = track 2 (secondary)
# tracks3.dat = track 3
# tracks4.dat = track 4


@dataclass
class TrackNode:
    """One node on a train track."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    flag: int = 0  # 0 = normal, 1 = station stop


@dataclass
class TrackFile:
    """One train track (one file)."""
    nodes: List[TrackNode] = field(default_factory=list)


def read_track(filepath: str) -> TrackFile:
    """Parse a tracks*.dat text file."""
    result = TrackFile()

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    if not lines:
        return result

    # First line is node count
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 3:
            try:
                node = TrackNode(
                    x=float(parts[0]),
                    y=float(parts[1]),
                    z=float(parts[2]),
                    flag=int(float(parts[3])) if len(parts) >= 4 else 0,
                )
                result.nodes.append(node)
            except ValueError:
                continue

    return result


def write_track(filepath: str, track: TrackFile) -> int:
    """Write train track to text file. Returns node count."""
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(f"{len(track.nodes)}\n")
        for node in track.nodes:
            f.write(f"{node.x:.2f} {node.y:.2f} {node.z:.5f} {node.flag}\n")

    return len(track.nodes)


# ═══════════════════════════════════════════════════════════════════════
# VEHICLE/PED NODES (nodes0.dat — nodes63.dat)
# ═══════════════════════════════════════════════════════════════════════
#
# Binary format — header + path nodes + navi nodes + links
#
# Header (20 bytes):
#   uint32 numNodes
#   uint32 numVehicleNodes
#   uint32 numPedNodes
#   uint32 numNaviNodes
#   uint32 numLinks
#
# Each PathNode (28 bytes):
#   int16  memAddress (unused, 0)
#   int16  unknown1 (0)
#   int16  posX      (compressed: real = value / 8.0)
#   int16  posY
#   int16  posZ
#   int16  heuristic (path distance, usually 0x7FFE)
#   uint16 linkID    (index of first link)
#   uint16 areaID    (zone area ID, 0-63)
#   uint16 nodeID    (node index within area)
#   uint8  pathWidth
#   uint8  nodeType  (flags: ped/vehicle, etc.)
#   uint32 flags
#
# Each NaviNode (14 bytes):
#   int16  posX (compressed / 8.0)
#   int16  posY
#   uint16 areaID
#   uint16 nodeID
#   int8   dirX  (direction vector, -100..100)
#   int8   dirY
#   uint32 flags
#
# Each Link (4 bytes):
#   uint16 areaID
#   uint16 nodeID

PATH_NODE_SIZE = 28
NAVI_NODE_SIZE = 14
LINK_SIZE = 4


# ── Binary PathNode flag bit layout (u32) ────────────────────────
# Reverse-engineered from ZZPuma Path Tools writer + game disasm.
# bits 0..3   — link count for this node (4 bits, max 15)
# bit  4      — onDeadEnd       (vehicle parks / ends route here)
# bit  5      — switchedOff     (traffic disabled by default)
# bit  6      — roadblock       (cops can spawn barriers)
# bit  7      — boats           (vehicle type = boat)
# bit  8      — emergency       (only emergency vehicles use it)
# bit 12      — NotHighway flag (inverse of bit 13)
# bit 13      — IsHighway flag  (traffic flows freely, no stops)
# bits 16..19 — spawn probability × 15 (4 bits, scale 0-15 → 0.0-1.0)
# bits 20..23 — specialFlag (4 bits, game-internal node behaviour)
# bit  21     — parking (also inside specialFlag range — historical naming)

PNODE_LINK_COUNT_MASK   = 0x0000000F
PNODE_DEAD_END_BIT      = 1 << 4
PNODE_SWITCHED_OFF_BIT  = 1 << 5
PNODE_ROADBLOCK_BIT     = 1 << 6
PNODE_BOATS_BIT         = 1 << 7
PNODE_EMERGENCY_BIT     = 1 << 8
PNODE_NOT_HIGHWAY_BIT   = 1 << 12
PNODE_HIGHWAY_BIT       = 1 << 13
PNODE_SPAWN_MASK        = 0x000F0000  # bits 16..19
PNODE_SPAWN_SHIFT       = 16
PNODE_SPECIAL_MASK      = 0x00F00000  # bits 20..23
PNODE_SPECIAL_SHIFT     = 20
PNODE_PARKING_BIT       = 1 << 21


def decode_path_node_flags(flags: int) -> dict:
    """Expand a PathNode.flags u32 into named fields. Inverse of
    ``encode_path_node_flags``. Returned dict carries booleans + ints
    matching ZZPuma's nomenclature so users can edit individual bits
    without manual masking."""
    return {
        'link_count':   flags & PNODE_LINK_COUNT_MASK,
        'on_dead_end':  bool(flags & PNODE_DEAD_END_BIT),
        'switched_off': bool(flags & PNODE_SWITCHED_OFF_BIT),
        'roadblock':    bool(flags & PNODE_ROADBLOCK_BIT),
        'boats':        bool(flags & PNODE_BOATS_BIT),
        'emergency':    bool(flags & PNODE_EMERGENCY_BIT),
        'not_highway':  bool(flags & PNODE_NOT_HIGHWAY_BIT),
        'highway':      bool(flags & PNODE_HIGHWAY_BIT),
        'spawn':        (flags & PNODE_SPAWN_MASK) >> PNODE_SPAWN_SHIFT,
        'special_flag': (flags & PNODE_SPECIAL_MASK) >> PNODE_SPECIAL_SHIFT,
        'parking':      bool(flags & PNODE_PARKING_BIT),
    }


def encode_path_node_flags(*, link_count: int = 0, on_dead_end: bool = False,
                            switched_off: bool = False, roadblock: bool = False,
                            boats: bool = False, emergency: bool = False,
                            highway: bool = False, spawn: int = 0,
                            special_flag: int = 0, parking: bool = False,
                            keep_bits: int = 0) -> int:
    """Pack named fields into a PathNode.flags u32.

    ``keep_bits`` is bitwise-ORed last — use it to preserve undocumented
    bits found on import without forcing the caller to enumerate them.
    """
    flags = keep_bits
    flags |= (link_count & 0x0F)
    if on_dead_end:  flags |= PNODE_DEAD_END_BIT
    if switched_off: flags |= PNODE_SWITCHED_OFF_BIT
    if roadblock:    flags |= PNODE_ROADBLOCK_BIT
    if boats:        flags |= PNODE_BOATS_BIT
    if emergency:    flags |= PNODE_EMERGENCY_BIT
    # NotHighway is the inverse of Highway; ZZPuma writes both bits
    # explicitly so the game always sees one of them set.
    if highway:
        flags |= PNODE_HIGHWAY_BIT
    else:
        flags |= PNODE_NOT_HIGHWAY_BIT
    flags |= (spawn & 0x0F) << PNODE_SPAWN_SHIFT
    flags |= (special_flag & 0x0F) << PNODE_SPECIAL_SHIFT
    if parking:      flags |= PNODE_PARKING_BIT
    return flags


# ── Binary NaviNode flag bit layout (u32) ────────────────────────
# bits 0..7   — reserved (game-internal)
# bits 8..10  — leftLanes (3 bits, 0-7)
# bits 11..13 — rightLanes (3 bits, 0-7)
# bit  14     — reverse_TrafficLight (180° orientation of TL geometry)
# bits 16..17 — trafficLight (0=none, 1=standard cycle, 2=strict)

NAVI_LEFT_LANES_MASK   = 0x00000700  # bits 8..10
NAVI_LEFT_LANES_SHIFT  = 8
NAVI_RIGHT_LANES_MASK  = 0x00003800  # bits 11..13
NAVI_RIGHT_LANES_SHIFT = 11
NAVI_REVERSE_TL_BIT    = 1 << 14
NAVI_TL_MASK           = 0x00030000  # bits 16..17
NAVI_TL_SHIFT          = 16


def decode_navi_flags(flags: int) -> dict:
    """Expand a NaviNode.flags u32. Inverse of ``encode_navi_flags``."""
    return {
        'left_lanes':         (flags & NAVI_LEFT_LANES_MASK) >> NAVI_LEFT_LANES_SHIFT,
        'right_lanes':        (flags & NAVI_RIGHT_LANES_MASK) >> NAVI_RIGHT_LANES_SHIFT,
        'reverse_tl':         bool(flags & NAVI_REVERSE_TL_BIT),
        'traffic_light':      (flags & NAVI_TL_MASK) >> NAVI_TL_SHIFT,
    }


def encode_navi_flags(*, left_lanes: int = 1, right_lanes: int = 1,
                       reverse_tl: bool = False, traffic_light: int = 0,
                       keep_bits: int = 0) -> int:
    """Pack named NaviNode fields into a u32 flags value."""
    flags = keep_bits
    flags |= (left_lanes & 0x07) << NAVI_LEFT_LANES_SHIFT
    flags |= (right_lanes & 0x07) << NAVI_RIGHT_LANES_SHIFT
    if reverse_tl:
        flags |= NAVI_REVERSE_TL_BIT
    flags |= (traffic_light & 0x03) << NAVI_TL_SHIFT
    return flags


# ── ROADBLOX.DAT ─────────────────────────────────────────────────
# Aux file emitted alongside nodes*.dat. Lists every PathNode that
# has the `roadblock` flag bit set, as (area_id, node_id) u16 pairs.
# Game uses this to spawn cop barriers during chases. Fastman92's
# vanilla layout pads the file to 325 entries (1300 bytes payload
# + 4-byte count header = 1304 bytes total).
ROADBLOX_VANILLA_CAPACITY = 325


def write_roadblox(filepath: str, nodes_files) -> int:
    """Emit ROADBLOX.DAT from a list of NodesFile objects.

    Scans every node across all files; entries are written in
    encounter order. Returns the number of roadblock nodes found.
    Pads to ``ROADBLOX_VANILLA_CAPACITY`` × 4 zero bytes if the count
    is below — vanilla SA expects a fixed-size file.
    """
    entries = []  # list of (area_id, node_id)
    for nf in nodes_files:
        for node in nf.vehicle_nodes + nf.ped_nodes:
            if node.flags & PNODE_ROADBLOCK_BIT:
                entries.append((node.area_id, node.node_id))

    with open(filepath, 'wb') as f:
        f.write(struct.pack('<I', len(entries)))
        for area_id, node_id in entries:
            f.write(struct.pack('<2H', area_id, node_id))
        # Pad to vanilla capacity for game compatibility.
        if len(entries) < ROADBLOX_VANILLA_CAPACITY:
            pad_count = ROADBLOX_VANILLA_CAPACITY - len(entries)
            f.write(b'\x00' * (pad_count * 4))
    return len(entries)


def read_roadblox(filepath: str):
    """Parse ROADBLOX.DAT into a list of (area_id, node_id) pairs.
    Ignores padding past the declared count. Returns empty list on
    missing file or short data."""
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except OSError:
        return []
    if len(data) < 4:
        return []
    count = struct.unpack_from('<I', data, 0)[0]
    entries = []
    offset = 4
    for _ in range(count):
        if offset + 4 > len(data):
            break
        area_id, node_id = struct.unpack_from('<2H', data, offset)
        entries.append((area_id, node_id))
        offset += 4
    return entries


# ── connectors.txt ───────────────────────────────────────────────
# Meta file pairing connector-flagged nodes to their (areaID, nodeID).
# Used by some mods (Fastman92 limit adjuster) to set up extra path
# bridges between regions. Format is plain CSV with a leading comment.

def write_connectors(filepath: str, connectors: list) -> int:
    """Write a connectors.txt file. ``connectors`` is a list of
    (area_id, node_id) tuples. Returns the number of entries.
    Leading ``;AreaID -- NodeID`` comment matches ZZPuma's output."""
    with open(filepath, 'w', encoding='ascii', newline='\n') as f:
        f.write(';AreaID -- NodeID\n')
        for area_id, node_id in connectors:
            f.write(f"{area_id}, {node_id}\n")
    return len(connectors)


def read_connectors(filepath: str):
    """Parse connectors.txt into a list of (area_id, node_id) tuples."""
    entries = []
    try:
        with open(filepath, 'r', encoding='ascii', errors='replace') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith(';') or line.startswith('#'):
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    try:
                        entries.append((int(parts[0]), int(parts[1])))
                    except ValueError:
                        continue
    except OSError:
        return []
    return entries


# ── Region grid (PathSet) ────────────────────────────────────────
# Vanilla SA splits the world into 8×8 = 64 cells of 750×750 m each.
# Fastman92 limit adjuster supports larger grids (256/1024/4096/...)
# by changing the pathSet count. Each PathNode's area_id is the cell
# index computed from its XY coordinate.
PATHSET_VANILLA = 64
PATHSET_VARIANTS = (64, 256, 1024, 4096, 16384, 65536)
PATH_CELL_SIZE_M = 750.0


def get_area_id(x: float, y: float, path_set: int = PATHSET_VANILLA) -> int:
    """Compute the 0-based region index for a world-space (x, y).

    Mirrors ZZPuma's `getArea`: the path grid is a square of
    ``sqrt(path_set)`` cells per axis, centred on the origin with cells
    of ``PATH_CELL_SIZE_M``. The returned value is 0..(path_set - 1).
    """
    import math
    grid = int(math.isqrt(path_set))
    if grid <= 0:
        return 0
    half = grid * PATH_CELL_SIZE_M * 0.5
    cx = int((x + half) // PATH_CELL_SIZE_M)
    cy = int((y + half) // PATH_CELL_SIZE_M)
    if cx < 0:        cx = 0
    if cy < 0:        cy = 0
    if cx >= grid:    cx = grid - 1
    if cy >= grid:    cy = grid - 1
    return cx + cy * grid


def split_nodes_by_area(points, fla4: bool = False) -> dict:
    """Bin bare path nodes into one NodesFile per vanilla area (nodes<N>.dat).

    ``points`` yields ``(path_type, x, y, z)`` in world space; path_type is
    'nodes_vehicle' or 'nodes_ped', anything else is skipped (no area file
    is opened for it). The area is `get_area_id` — the game's
    CPathFind::FindX/YRegionForCoors (0x44D890 / 0x44D8C0) use the same
    (v + 3000) / 750 on both axes, Y is NOT flipped. node_id is the running
    index inside the file, vehicle nodes first, as in vanilla nodes*.dat;
    the empty post-link tail is marked parsed so `write_nodes` still emits
    the 768-byte filler and the section-7 padding.
    """
    zones = {}  # area_id → NodesFile
    for path_type, x, y, z in points:
        if path_type not in ('nodes_vehicle', 'nodes_ped'):
            continue
        # Area of the position as the game will see it: write_nodes stores
        # int(v * 8) (truncates toward zero), so a node at y = -750.05 is
        # read back as -750.0 and belongs to the next row up.
        area = get_area_id(int(x * 8.0) / 8.0, int(y * 8.0) / 8.0)
        nf = zones.get(area)
        if nf is None:
            nf = zones[area] = NodesFile(fla4=fla4, parsed_extras=True)
        is_vehicle = path_type == 'nodes_vehicle'
        node = PathNode(x=x, y=y, z=z, area_id=area, is_vehicle=is_vehicle)
        (nf.vehicle_nodes if is_vehicle else nf.ped_nodes).append(node)
    for nf in zones.values():
        for i, node in enumerate(nf.vehicle_nodes + nf.ped_nodes):
            node.node_id = i
    return zones

# FLA4 (Fastman Limit Adjuster 4) extension — unofficial format that
# inflates each PathNode by 12 bytes to store per-node speed limit,
# spawn probability and a lane override. File is tagged with the
# magic "FLA4" at offset 0 and the original 5-uint32 count header
# shifts to offset 4.
FLA4_MAGIC = b'FLA4'
# FLA4 node extension (16 bytes after the 28-byte standard node):
#   int32 ext_x, int32 ext_y, int32 ext_z  — extended position
#   u16 ext_width                          — extended path width/floodID
#   u16 alignment                          — always 0
FLA4_NODE_EXTRA = 16
FLA4_PATH_NODE_SIZE = PATH_NODE_SIZE + FLA4_NODE_EXTRA  # 44
# FLA4 navi extension (10 bytes after the 14-byte standard navi):
#   u16 alignment, int32 ext_x, int32 ext_y
FLA4_NAVI_SIZE = 24

# Fixed layout constants verified against ZZPuma Path Tools reference
# implementation. See docs comparing the two formats — these magic
# numbers appear identically in their reader and writer.
NODELINK_FILLER_BYTES = 768           # Section 4: 192 × (u16 0xFFFF + u16 0x0000) between NodeLinks and NaviLinks
PATH_INTERSECTION_TRAILING = 192      # Section 7 length = num_links + 192
FLA4_SECTION8_PAD = 192               # Section 8: 192 zero bytes before EOF
FLA4_EOF_MARKER = 0x00464F45          # u32 b'EOF\0' — written at the very end of FLA4 files
FLA4_NAVI_LINK_SIZE_VANILLA = 2       # u16 per nodelink in vanilla
FLA4_NAVI_LINK_SIZE_FLA4 = 4          # 2× u16 per nodelink in FLA4


@dataclass
class PathNode:
    """Vehicle or pedestrian path node."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    link_id: int = 0
    area_id: int = 0
    node_id: int = 0
    path_width: int = 0
    node_type: int = 0
    flags: int = 0
    is_vehicle: bool = True  # True = vehicle, False = ped
    # FLA4 extension fields (unused in vanilla SA format)
    spawn_probability: int = 0
    speed_limit_kmh: int = 0
    lane_count_override: int = 0


@dataclass
class NaviNode:
    """Navigation node (intermediate point between path nodes)."""
    x: float = 0.0
    y: float = 0.0
    area_id: int = 0
    node_id: int = 0
    dir_x: int = 0
    dir_y: int = 0
    flags: int = 0


@dataclass
class PathLink:
    """Link between two path nodes."""
    area_id: int = 0
    node_id: int = 0


@dataclass
class NodesFile:
    """One nodes*.dat file (one zone area).

    The post-link tail (naviLinks, linkLengths, pathIntersections) is
    parsed into structured lists when its size matches the expected
    `4 * num_links` layout (2-byte naviLink + 1-byte linkLength +
    1-byte pathIntersection per link). When the size doesn't fit —
    files with extra trailing data, or older / modded variants — the
    raw bytes are kept in `extra_data` instead, and `parsed_extras`
    stays False so the writer just blits them back.
    """
    vehicle_nodes: List[PathNode] = field(default_factory=list)
    ped_nodes: List[PathNode] = field(default_factory=list)
    navi_nodes: List[NaviNode] = field(default_factory=list)
    links: List[PathLink] = field(default_factory=list)
    # Parsed post-link arrays (each indexed by link index). Only valid
    # when `parsed_extras` is True.
    navi_links: List[int] = field(default_factory=list)         # uint16 each
    link_lengths: List[int] = field(default_factory=list)       # uint8 each
    path_intersections: List[int] = field(default_factory=list) # uint8 each
    parsed_extras: bool = False
    # Raw fallback when post-link layout doesn't match expectations.
    extra_data: bytes = b''
    fla4: bool = False       # True when loaded from / meant to write a FLA4 file


def read_nodes(filepath: str) -> NodesFile:
    """Parse a nodes*.dat binary file. Detects FLA4 extended format."""
    result = NodesFile()

    with open(filepath, 'rb') as f:
        data = f.read()

    if len(data) < 20:
        return result

    # FLA4 marker — skip the 4-byte magic and read the normal header after
    header_offset = 0
    if data[:4] == FLA4_MAGIC:
        result.fla4 = True
        header_offset = 4
        if len(data) < 24:
            return result

    num_nodes, num_vehicle, num_ped, num_navi, num_links = struct.unpack_from(
        '<5I', data, header_offset)
    offset = header_offset + 20

    node_size = FLA4_PATH_NODE_SIZE if result.fla4 else PATH_NODE_SIZE

    # Read all path nodes
    for i in range(num_nodes):
        if offset + node_size > len(data):
            break
        # PathNode: uint32 mem, uint32 unk, int16 x/y/z, int16 heuristic,
        #           uint16 linkID/areaID/nodeID, uint8 width/type, uint32 flags
        (mem, unk1, px, py, pz, heuristic,
         link_id, area_id, node_id,
         path_width, node_type, flags) = struct.unpack_from(
             '<II4h3HBBi', data, offset)

        extra_spawn = extra_speed = extra_lanes = 0
        if result.fla4:
            # FLA4 trailer: 3× int32 extended pos + u16 ext_width + u16
            # alignment. We re-use spawn/speed/lanes fields as storage
            # for ext_x/ext_y/ext_z respectively (3× int32). The u16
            # ext_width overlays our high 16 bits of `path_width` so
            # the FLA4 wider value can be reconstructed on write.
            (ex_x, ex_y, ex_z) = struct.unpack_from(
                '<iii', data, offset + PATH_NODE_SIZE)
            (ex_w, _align) = struct.unpack_from(
                '<HH', data, offset + PATH_NODE_SIZE + 12)
            extra_spawn = ex_x
            extra_speed = ex_y
            extra_lanes = ex_z
            # Promote ex_width to path_width if it's larger — FLA4 lets
            # paths exceed the 255 cap of the u8 vanilla field.
            if ex_w > path_width:
                path_width = ex_w

        offset += node_size

        node = PathNode(
            x=px / 8.0,
            y=py / 8.0,
            z=pz / 8.0,
            link_id=link_id,
            area_id=area_id,
            node_id=node_id,
            path_width=path_width,
            node_type=node_type,
            flags=flags,
            is_vehicle=(i < num_vehicle),
            spawn_probability=extra_spawn,
            speed_limit_kmh=extra_speed,
            lane_count_override=extra_lanes,
        )
        if i < num_vehicle:
            result.vehicle_nodes.append(node)
        else:
            result.ped_nodes.append(node)

    # Read navi nodes. FLA4 widens the structure to 16 bytes (2-byte
    # alignment + 8 bytes of extended position appended); vanilla stays 14.
    navi_size = FLA4_NAVI_SIZE if result.fla4 else NAVI_NODE_SIZE
    for i in range(num_navi):
        if offset + navi_size > len(data):
            break
        (nx, ny, area_id, node_id, dir_x, dir_y, nflags) = struct.unpack_from('<2h2H2bi', data, offset)
        if result.fla4:
            # 2-byte alignment + 2× int32 extended pos. We re-use the
            # extended pos (more precision) when it's present.
            try:
                ex_x = struct.unpack_from('<i', data, offset + 14 + 2)[0]
                ex_y = struct.unpack_from('<i', data, offset + 14 + 6)[0]
                nx = ex_x
                ny = ex_y
            except struct.error:
                pass
        offset += navi_size

        result.navi_nodes.append(NaviNode(
            x=nx / 8.0,
            y=ny / 8.0,
            area_id=area_id,
            node_id=node_id,
            dir_x=dir_x,
            dir_y=dir_y,
            flags=nflags,
        ))

    # Read links (Section 3)
    for i in range(num_links):
        if offset + LINK_SIZE > len(data):
            break
        area_id, node_id = struct.unpack_from('<2H', data, offset)
        offset += LINK_SIZE

        result.links.append(PathLink(area_id=area_id, node_id=node_id))

    # ── Section 4: 768-byte filler ──
    # ZZPuma Path Tools reference confirms vanilla SA always emits
    # 192 × (u16 0xFFFF + u16 0x0000) = 768 bytes between Section 3
    # (NodeLinks) and Section 5 (NaviLinks). Files without it are
    # corrupt or non-standard. Skip it; we don't store the filler
    # because it's a constant (regenerated on write).
    if offset + NODELINK_FILLER_BYTES <= len(data):
        offset += NODELINK_FILLER_BYTES
    else:
        # Truncated file — bail with raw tail fallback for round-trip safety.
        result.extra_data = data[offset:]
        return result

    # ── Sections 5-7: NaviLinks + LinkLengths + PathIntersections ──
    # Section 5: NaviLinks — 2 bytes per link (vanilla) or 4 bytes (FLA4).
    # Section 6: LinkLengths — 1 byte per link.
    # Section 7: PathIntersections — (num_links + 192) bytes.
    navi_link_unit = FLA4_NAVI_LINK_SIZE_FLA4 if result.fla4 else FLA4_NAVI_LINK_SIZE_VANILLA
    expected_sections567 = (
        num_links * navi_link_unit  # Section 5
        + num_links                 # Section 6
        + num_links + PATH_INTERSECTION_TRAILING  # Section 7
    )
    fla4_section8 = (FLA4_SECTION8_PAD + 4) if result.fla4 else 0
    expected_tail = expected_sections567 + fla4_section8
    remaining = len(data) - offset

    if num_links > 0 and remaining == expected_tail:
        try:
            base = offset
            # Section 5 — NaviLinks
            if result.fla4:
                # 2× u16 per link (naviID, region)
                fla4_nl = struct.unpack_from(
                    f'<{num_links * 2}H', data, base)
                # Re-pack into u32 each so we keep a single integer per
                # link in our public storage (low 16 bits = naviID, high
                # 16 bits = region) — keeps the dataclass shape stable.
                result.navi_links = [
                    (fla4_nl[i * 2] | (fla4_nl[i * 2 + 1] << 16))
                    for i in range(num_links)
                ]
            else:
                result.navi_links = list(
                    struct.unpack_from(f'<{num_links}H', data, base))
            base += num_links * navi_link_unit
            # Section 6 — LinkLengths
            result.link_lengths = list(
                struct.unpack_from(f'<{num_links}B', data, base))
            base += num_links
            # Section 7 — PathIntersections (note: linkCount + 192 bytes!)
            pi_total = num_links + PATH_INTERSECTION_TRAILING
            result.path_intersections = list(
                struct.unpack_from(f'<{pi_total}B', data, base))
            base += pi_total
            # Section 8 (FLA4 only) — skip 192 zero bytes + EOF marker.
            # We don't store them; writer regenerates from the fla4 flag.
            result.parsed_extras = True
        except struct.error:
            # Defensive fallback — shouldn't trigger with size match
            result.extra_data = data[offset:]
    elif remaining > 0:
        # Layout doesn't match expectations (truncated file, modded
        # variant). Keep raw bytes including the 768B filler we already
        # walked past — re-write them on save for byte-identical round-trip.
        result.extra_data = data[offset - NODELINK_FILLER_BYTES:]

    return result


def write_nodes(filepath: str, nodes_file: NodesFile) -> int:
    """Write nodes*.dat binary file. Returns total node count.

    If ``nodes_file.fla4`` is set, the output is written in FLA4 extended
    format (FLA4 magic + 40-byte path nodes with spawn/speed/lane fields).
    """
    num_vehicle = len(nodes_file.vehicle_nodes)
    num_ped = len(nodes_file.ped_nodes)
    num_nodes = num_vehicle + num_ped
    num_navi = len(nodes_file.navi_nodes)
    num_links = len(nodes_file.links)

    with open(filepath, 'wb') as f:
        if nodes_file.fla4:
            f.write(FLA4_MAGIC)

        # Header
        f.write(struct.pack('<5I', num_nodes, num_vehicle, num_ped, num_navi, num_links))

        # Path nodes (vehicle first, then ped)
        for node in (nodes_file.vehicle_nodes + nodes_file.ped_nodes):
            px = int(node.x * 8.0)
            py = int(node.y * 8.0)
            pz = int(node.z * 8.0)
            f.write(struct.pack('<II4h3HBBi',
                                0, 0,  # memAddress, unknown
                                px, py, pz,
                                0x7FFE,  # heuristic
                                node.link_id, node.area_id, node.node_id,
                                node.path_width, node.node_type, node.flags))
            if nodes_file.fla4:
                # 3× int32 extended position (re-using spawn/speed/lanes
                # slots as storage) + u16 ext_width + u16 alignment.
                # Matches ZZPuma's writer + gtamods FLA4 spec.
                f.write(struct.pack('<iii',
                                    node.spawn_probability,
                                    node.speed_limit_kmh,
                                    node.lane_count_override))
                # ext_width is the wider equivalent of u8 path_width.
                # On round-trip we just write back path_width (already
                # promoted on read if FLA4 had a larger value).
                f.write(struct.pack('<HH',
                                    node.path_width & 0xFFFF, 0))

        # Navi nodes
        for navi in nodes_file.navi_nodes:
            nx = int(navi.x * 8.0)
            ny = int(navi.y * 8.0)
            f.write(struct.pack('<2h2H2bi',
                                nx, ny,
                                navi.area_id, navi.node_id,
                                navi.dir_x, navi.dir_y,
                                navi.flags))
            if nodes_file.fla4:
                # 2-byte alignment + 2× int32 extended pos. Mirrors the
                # vanilla pos but with full int32 precision (avoid the
                # ±32767 short range cap on FLA4-only large maps).
                f.write(struct.pack('<HII', 0, nx, ny))

        # Section 3 — NodeLinks
        for link in nodes_file.links:
            f.write(struct.pack('<2H', link.area_id, link.node_id))

        # Post-link tail. Prefer the parsed structures when available
        # so user edits round-trip; fall back to the raw `extra_data`
        # blob (which already includes its own 768B filler) for files
        # where the on-read layout check didn't match.
        if nodes_file.parsed_extras:
            n = num_links

            # ── Section 4: 768-byte filler ──
            # 192 × (u16 0xFFFF + u16 0x0000). The game checks this
            # section for the literal 0xFFFF marker; emitting zeros
            # has been seen to cause stuttering on some PC builds.
            filler_block = struct.pack(
                f'<{192 * 2}H',
                *([0xFFFF, 0x0000] * 192))
            f.write(filler_block)

            nl = nodes_file.navi_links
            ll = nodes_file.link_lengths
            pi = nodes_file.path_intersections

            # If user edits made counts mismatch num_links, pad / truncate.
            # Section 7 has +192 bytes of trailing padding on top of
            # num_links, so its target length is num_links + 192.
            def _fit(arr, n_target, fill=0):
                if len(arr) >= n_target:
                    return arr[:n_target]
                return list(arr) + [fill] * (n_target - len(arr))

            # ── Section 5: NaviLinks ──
            fitted_nl = _fit(nl, n)
            if nodes_file.fla4:
                # u32 each, packed as 2× u16 (naviID, region) — naviID
                # in the low 16 bits, region in the high 16.
                for v in fitted_nl:
                    navi_id = v & 0xFFFF
                    region = (v >> 16) & 0xFFFF
                    f.write(struct.pack('<2H', navi_id, region))
            else:
                for v in fitted_nl:
                    f.write(struct.pack('<H', v & 0xFFFF))

            # ── Section 6: LinkLengths ──
            for v in _fit(ll, n):
                f.write(struct.pack('<B', v & 0xFF))

            # ── Section 7: PathIntersections (num_links + 192 bytes) ──
            pi_total = n + PATH_INTERSECTION_TRAILING
            for v in _fit(pi, pi_total):
                f.write(struct.pack('<B', v & 0xFF))

            # ── Section 8 (FLA4 only): 192 zero bytes + EOF marker ──
            if nodes_file.fla4:
                f.write(b'\x00' * FLA4_SECTION8_PAD)
                f.write(struct.pack('<I', FLA4_EOF_MARKER))
        elif nodes_file.extra_data:
            # Raw fallback — extra_data was captured from offset of the
            # 768B filler onwards on read, so it's a verbatim slice.
            f.write(nodes_file.extra_data)

    return num_nodes
