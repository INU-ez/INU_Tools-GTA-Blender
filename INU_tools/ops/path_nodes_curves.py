"""Persistent identities for Compiled NODES curves and the shared graph writer.

A hidden Empty stores one immutable region snapshot. Curve points store
occurrence tags, so junction copies resolve to the same physical node without
merging unrelated nearby nodes. No source mesh is required after conversion.
"""

import base64
import json
import math
import os
import tempfile
import uuid
from dataclasses import asdict, replace

from ..core.paths import (NodesFile, PathNode, NaviNode, PathLink, get_area_id,
                          decode_path_node_flags, decode_navi_flags, write_nodes)
from ..core.paths_graph import (graph_edges, rebuild_graph, validate_graph_batch,
                                remap_foreign_references, unpack_navi_address)
from .path_nodes_mesh import collect_compiled_nodes, complete_node_objects
from .path_ipl_props import _tag, _slot, _selected

SOURCE = 'inu_nodes_curve_source'
SNAPSHOT = 'inu_nodes_curve_snapshot'
VERSION = 1
LEGACY_ERROR = ('Curve has no Compiled NODES identities. Convert the original '
                'Compiled NODES mesh again with Mesh -> Curves before exporting.')


def _encode(nf):
    data = {key: [asdict(n) for n in getattr(nf, key)] for key in
            ('vehicle_nodes', 'ped_nodes', 'navi_nodes', 'links')}
    for key in ('navi_links', 'link_lengths', 'path_intersections', 'parsed_extras', 'fla4'):
        data[key] = getattr(nf, key)
    data['extra_data'] = base64.b64encode(nf.extra_data).decode('ascii')
    return json.dumps(data, separators=(',', ':'), sort_keys=True)


def _decode(value):
    data = json.loads(value)
    for key, cls in (('vehicle_nodes', PathNode), ('ped_nodes', PathNode),
                     ('navi_nodes', NaviNode), ('links', PathLink)):
        data[key] = [cls(**n) for n in data[key]]
    data['extra_data'] = base64.b64decode(data['extra_data'], validate=True)
    return NodesFile(**data)


def _carrier(source, objects):
    matches = [o for o in objects if o.get(SOURCE) == source and SNAPSHOT in o]
    if len(matches) != 1:
        raise ValueError('Compiled NODES curve source is missing or duplicated; reimport and reconvert')
    if matches[0].get('inu_nodes_curve_version') != VERSION:
        raise ValueError('Unsupported Compiled NODES curve metadata version')
    return matches[0]


def _chains(indices, edges):
    adjacency = {i: [] for i in indices}
    for a, b in sorted(edges):
        if a in adjacency and b in adjacency:
            adjacency[a].append(b)
            adjacency[b].append(a)
    visited, chains = set(), []

    def walk(start, step):
        chain = [start, step]
        visited.add(tuple(sorted((start, step))))
        while len(adjacency[step]) == 2:
            following = [n for n in adjacency[step] if tuple(sorted((step, n))) not in visited]
            if not following:
                break
            nxt = following[0]
            visited.add(tuple(sorted((step, nxt))))
            chain.append(nxt)
            step = nxt
        return chain

    for i, neighbors in adjacency.items():
        if not neighbors:
            chains.append([i])  # Isolated nodes still own IDs and properties.
        if len(neighbors) != 2:
            for n in neighbors:
                if tuple(sorted((i, n))) not in visited:
                    chains.append(walk(i, n))
    for i, neighbors in adjacency.items():
        for n in neighbors:
            if tuple(sorted((i, n))) not in visited:
                chains.append(walk(i, n))
    return chains


def convert_mesh(context, mesh_obj, set_defaults, set_color):
    import bpy
    companions = complete_node_objects([mesh_obj], context.scene.objects)
    nf = collect_compiled_nodes(companions)
    if nf.node_remap:
        raise ValueError('Export all 64 Compiled NODES regions and reimport before converting reindexed meshes')
    area = int(mesh_obj['nodes_area'])
    encoded = _encode(nf)
    source_key = mesh_obj.get('nodes_source_key', '')
    matches = [o for o in context.scene.objects if SNAPSHOT in o and
               o.get('nodes_source_key') == source_key and o.get('nodes_area') == area]
    if len(matches) > 1:
        raise ValueError('Duplicate Compiled NODES curve snapshots')
    carrier = matches[0] if matches else None
    vehicle = mesh_obj.get('path_type') == 'nodes_vehicle'
    category = 2 if vehicle else 1
    if carrier is not None:
        if carrier[SNAPSHOT] != encoded:
            raise ValueError('Source mesh changed after curve conversion; reimport before converting again')
        if any(o.type == 'CURVE' and o.get(SOURCE) == carrier[SOURCE] and
               o.get('inu_nodes_curve_category') == category for o in context.scene.objects):
            raise ValueError('This NODES category already has curves; edit the existing curves')
    col = bpy.data.collections.get('Path Curves')
    if col is None:
        col = bpy.data.collections.new('Path Curves')
        context.scene.collection.children.link(col)
    elif col.name not in context.scene.collection.children:
        context.scene.collection.children.link(col)
    if carrier is None:
        carrier = bpy.data.objects.new(f'NODES{area} Curve Source', None)
        carrier[SOURCE] = uuid.uuid4().hex
        carrier[SNAPSHOT] = encoded
        carrier['inu_nodes_curve_version'] = VERSION
        carrier['nodes_area'] = area
        carrier['nodes_source_key'] = source_key
        carrier['nodes_filename'] = f'nodes{area}.dat'
        col.objects.link(carrier)
        carrier.hide_render = True
        carrier.hide_set(True)
    nodes = nf.vehicle_nodes + nf.ped_nodes
    start, end = (0, len(nf.vehicle_nodes)) if vehicle else (len(nf.vehicle_nodes), len(nodes))
    new_curves = []
    for chain in _chains(range(start, end), graph_edges(nf, area)):
        data = bpy.data.curves.new(mesh_obj.name + '_curve', 'CURVE')
        data.dimensions = '3D'
        spline = data.splines.new('POLY')
        spline.points.add(len(chain) - 1)
        for i, original in enumerate(chain):
            n = nodes[original]
            spline.points[i].co = (n.x, n.y, n.z, 1)
            spline.points[i].weight_softbody = _tag(i)
        obj = bpy.data.objects.new(data.name, data)
        obj[SOURCE] = carrier[SOURCE]
        obj['inu_nodes_curve_version'] = VERSION
        obj['inu_nodes_curve_category'] = category
        obj['inu_nodes_curve_id'] = uuid.uuid4().hex
        obj['inu_nodes_curve_origins'] = chain
        obj['inu_nodes_curve_positions'] = [v for i in chain for v in (nodes[i].x, nodes[i].y, nodes[i].z)]
        obj['sapath_type'] = category
        flags = decode_path_node_flags(nodes[chain[0]].flags)
        for name in ('roadblock', 'boats', 'emergency', 'highway', 'parking'):
            obj['sapath_' + name] = int(flags[name])
        obj['sapath_spawn'] = flags['spawn'] / 15
        obj['sapath_width'] = nodes[chain[0]].path_width / 8
        # Lane controls are in spline direction; navigation direction can be reversed.
        if vehicle and len(chain) > 1:
            first, second = chain[:2]
            for idx in range(nodes[first].link_id, nodes[first].link_id + (nodes[first].flags & 15)):
                link = nf.links[idx]
                if link.area_id != area or link.node_id != second:
                    continue
                nav_area, nav_index = unpack_navi_address(nf.navi_links[idx], nf.fla4)
                if nav_area == area and nav_index < len(nf.navi_nodes):
                    nav = nf.navi_nodes[nav_index]
                    forward = nav.dir_x*(nodes[second].x-nodes[first].x) + nav.dir_y*(nodes[second].y-nodes[first].y) >= 0
                    decoded = decode_navi_flags(nav.flags)
                    obj['sapath_laneright'] = decoded['right_lanes' if forward else 'left_lanes']
                    obj['sapath_laneleft'] = decoded['left_lanes' if forward else 'right_lanes']
                    obj['sapath_traffic'] = decoded['traffic_light']
                break
        set_defaults(obj)
        obj['inu_nodes_curve_props'] = json.dumps({k: obj[k] for k in obj.keys() if k.startswith('sapath_')})
        set_color(obj)
        col.objects.link(obj)
        new_curves.append(obj)
    carrier[f'inu_nodes_curve_category_{category}'] = True
    mesh_obj['path_curves_built'] = True
    return new_curves


def _point_origins(obj):
    origins = list(obj['inu_nodes_curve_origins'])
    baseline = list(obj['inu_nodes_curve_positions'])
    if len(baseline) != len(origins)*3:
        raise ValueError('Compiled NODES curve identity positions are incomplete')
    points, spline_ranges = [], []
    for spline in obj.data.splines:
        start = len(points)
        points.extend(spline.bezier_points if spline.type == 'BEZIER' else spline.points)
        spline_ranges.append((start, len(points), spline.use_cyclic_u))
    positions = [tuple(obj.matrix_world @ p.co.xyz) for p in points]
    if any(not all(math.isfinite(v) for v in p) for p in positions):
        raise ValueError('NODES curve has a nonfinite coordinate')
    choices, slots = {}, [None]*len(points)
    for i, point in enumerate(points):
        slot = _slot(point)
        if slot is not None and slot < len(origins):
            choices.setdefault(slot, []).append(i)
    for slot, candidates in choices.items():
        old = baseline[slot*3:slot*3+3]
        candidates.sort(key=lambda i: (sum((a-b)**2 for a, b in zip(positions[i], old)), _selected(points[i]), i))
        if len(candidates) > 1 and positions[candidates[0]] == positions[candidates[1]]:
            raise ValueError(f'Coincident duplicated NODES identity in "{obj.name}": move or merge the new point')
        slots[candidates[0]] = origins[slot]
    return positions, slots, spline_ranges


def _overrides(obj):
    baseline = json.loads(obj['inu_nodes_curve_props'])
    if int(obj.get('sapath_type', baseline['sapath_type'])) != int(baseline['sapath_type']):
        raise ValueError('Changing a converted curve between vehicle and pedestrian is unsupported; use its original category')
    changes = {key: obj.get(key, value) for key, value in baseline.items()
               if obj.get(key, value) != value}
    # Path IDs are original physical identities; the legacy pathid field cannot replace them.
    if 'sapath_pathid' in changes:
        raise ValueError('Compiled NODES IDs are managed automatically; do not change sapath_pathid')
    return changes


def _apply_props(node, changes):
    from ..core import paths
    masks = dict(roadblock=paths.PNODE_ROADBLOCK_BIT, boats=paths.PNODE_BOATS_BIT,
                 emergency=paths.PNODE_EMERGENCY_BIT,
                 highway=paths.PNODE_HIGHWAY_BIT | paths.PNODE_NOT_HIGHWAY_BIT,
                 parking=paths.PNODE_PARKING_BIT, spawn=paths.PNODE_SPAWN_MASK)
    for name, mask in masks.items():
        key = 'sapath_' + name
        if key not in changes:
            continue
        value = changes[key]
        if name == 'spawn':
            if not 0 <= float(value) <= 1:
                raise ValueError('Spawn must be between 0 and 1')
            bits = round(float(value)*15) << paths.PNODE_SPAWN_SHIFT
        elif name == 'highway':
            bits = paths.PNODE_HIGHWAY_BIT if value else paths.PNODE_NOT_HIGHWAY_BIT
        else:
            bits = mask if value else 0
        node.flags = (node.flags & ~mask) | bits
    if 'sapath_width' in changes:
        value = round(float(changes['sapath_width'])*8)
        if not 0 <= value <= 255:
            raise ValueError('NODES width is outside the byte range')
        node.path_width = value


def collect_curve_region(carrier, objects):
    original = _decode(carrier[SNAPSHOT])
    old = original.vehicle_nodes + original.ped_nodes
    area = int(carrier['nodes_area'])
    curves = sorted([o for o in objects if o.type == 'CURVE' and o.get(SOURCE) == carrier[SOURCE]],
                    key=lambda o: (o.get('inu_nodes_curve_id', ''), o.name))
    curve_ids = [o.get('inu_nodes_curve_id') for o in curves]
    if len(set(curve_ids)) != len(curve_ids):
        raise ValueError('Duplicated NODES curve objects share identities; duplicate points in Edit Mode instead')
    nodes, origins, edges, directed = [], [], set(), []
    by_key, properties = {}, {}
    for category in (2, 1):
        if not carrier.get(f'inu_nodes_curve_category_{category}'):
            start, end = (0, len(original.vehicle_nodes)) if category == 2 else (len(original.vehicle_nodes), len(old))
            for origin in range(start, end):
                by_key[('old', origin)] = len(nodes)
                nodes.append(replace(old[origin]))
                origins.append(origin)
            continue
        for obj in curves:
            if obj.get('inu_nodes_curve_version') != VERSION:
                raise ValueError(LEGACY_ERROR)
            if obj.get('inu_nodes_curve_category') != category:
                continue
            if any(m.type == 'SOFT_BODY' for m in obj.modifiers):
                raise ValueError('Remove Soft Body from NODES curves; it uses the point identity storage')
            positions, slots, splines = _point_origins(obj)
            changes = _overrides(obj)
            local = []
            for i, (position, origin) in enumerate(zip(positions, slots)):
                if origin is not None and (not 0 <= origin < len(old) or old[origin].is_vehicle != (category == 2)):
                    raise ValueError('Invalid Compiled NODES curve identity')
                key = ('old', origin) if origin is not None else (obj['inu_nodes_curve_id'], i)
                if key in by_key:
                    index = by_key[key]
                    node = nodes[index]
                    if max(abs(a-b) for a, b in zip((node.x, node.y, node.z), position)) > 1e-4:
                        raise ValueError(f'Shared NODES junction {origin} was moved differently on its curves; move all copies together')
                else:
                    index = by_key[key] = len(nodes)
                    template = origin
                    if template is None:
                        known = [(abs(i-j), j, slot) for j, slot in enumerate(slots) if slot is not None]
                        template = min(known)[2] if known else obj['inu_nodes_curve_origins'][0]
                    node = replace(old[template])
                    node.x, node.y, node.z = position
                    if origin is None:
                        if get_area_id(int(node.x*8)/8, int(node.y*8)/8) != area:
                            raise ValueError('New NODES point lies outside its region; add it to the correct region')
                        node.area_id = area
                        node.flags &= ~(15 | (1 << 4) | (1 << 6) | 0x00F00000)
                    if original.fla4:
                        node.spawn_probability, node.speed_limit_kmh, node.lane_count_override = (int(v*8) for v in position)
                    nodes.append(node)
                    origins.append(origin)
                for prop, value in changes.items():
                    prior = properties.setdefault(key, {})
                    if prop in prior and prior[prop] != value:
                        raise ValueError(f'Conflicting curve properties at shared NODES junction {origin}')
                    prior[prop] = value
                local.append(index)
            for start, end, cyclic in splines:
                pairs = list(zip(local[start:end], local[start+1:end]))
                if cyclic and end-start > 1:
                    pairs.append((local[end-1], local[start]))
                for a, b in pairs:
                    if a == b:
                        raise ValueError('NODES spline contains consecutive copies of the same node')
                    edges.add(tuple(sorted((a, b))))
                    directed.append((a, b, changes))
    # Original IDs keep their physical order; new vehicles precede pedestrians.
    order = sorted(range(len(nodes)), key=lambda i: (not nodes[i].is_vehicle,
                   origins[i] is None, origins[i] if origins[i] is not None else i))
    remap_indices = {old_i: new_i for new_i, old_i in enumerate(order)}
    for key, changes in properties.items():
        _apply_props(nodes[by_key[key]], changes)
    edges = {tuple(sorted((remap_indices[a], remap_indices[b]))) for a, b in edges}
    for a, b in graph_edges(original, area):
        category = 2 if a < len(original.vehicle_nodes) else 1
        if not carrier.get(f'inu_nodes_curve_category_{category}'):
            edges.add(tuple(sorted((remap_indices[by_key['old', a]], remap_indices[by_key['old', b]]))))
    nodes, origins = [nodes[i] for i in order], [origins[i] for i in order]
    nf, remap, changed = rebuild_graph(original, nodes, origins, edges, area=area,
                                       vehicle_count=sum(n.is_vehicle for n in nodes))
    # Explicit lane edits apply in spline direction; preserve untouched per-link data.
    nav_changes = {}
    for a, b, changes in directed:
        a, b = remap_indices[a], remap_indices[b]
        if not nodes[a].is_vehicle:
            continue
        changes = {k: v for k, v in changes.items() if k in ('sapath_laneleft', 'sapath_laneright', 'sapath_traffic')}
        if not changes:
            continue
        for src, dst in ((a, b), (b, a)):
            n = nodes[src]
            for idx in range(n.link_id, n.link_id + (n.flags & 15)):
                link = nf.links[idx]
                if (link.area_id, link.node_id) != (area, dst):
                    continue
                nav_area, nav_index = unpack_navi_address(nf.navi_links[idx], nf.fla4)
                if nav_area != area or nav_index >= len(nf.navi_nodes):
                    raise ValueError('Lane edits on navigation owned by another region require editing that region')
                nav = nf.navi_nodes[nav_index]
                forward = nav.dir_x*(nodes[b].x-nodes[a].x) + nav.dir_y*(nodes[b].y-nodes[a].y) >= 0
                for key, value in changes.items():
                    if not 0 <= int(value) <= (3 if key == 'sapath_traffic' else 7):
                        raise ValueError('Lane count or traffic light value is outside its format range')
                    field = ('traffic_light' if key == 'sapath_traffic' else
                             ('left_lanes' if (key == 'sapath_laneleft') == forward else 'right_lanes'))
                    entry = nav_changes.setdefault(nav_index, {})
                    if field in entry and entry[field] != int(value):
                        raise ValueError('Conflicting lane properties on shared navigation')
                    entry[field] = int(value)
    for index, changes in nav_changes.items():
        nav = nf.navi_nodes[index]
        for field, value in changes.items():
            shift = {'left_lanes': 8, 'right_lanes': 11, 'traffic_light': 16}[field]
            mask = (3 if field == 'traffic_light' else 7) << shift
            nav.flags = (nav.flags & ~mask) | (value << shift)
    nf.node_remap, nf.topology_changed, nf.original_node_indices = remap, changed, origins
    return nf


def prepare_curve_export(selected, scene_objects, *, entire_map=False, fla4=False, path_set=64):
    objects = list(scene_objects)
    selected = [o for o in selected if o.type == 'CURVE']
    if not selected or any(not o.get(SOURCE) for o in selected):
        raise ValueError(LEGACY_ERROR)
    if path_set != 64:
        raise ValueError('Converted Compiled NODES curves retain their imported region grid; use Path set 64')
    sources = {o[SOURCE] for o in selected}
    carriers = [_carrier(s, objects) for s in sorted(sources)]
    if entire_map:
        carriers = [o for o in objects if SNAPSHOT in o]
    regions, imports = {}, {}
    for carrier in carriers:
        area = int(carrier['nodes_area'])
        if area in regions:
            raise ValueError('Multiple imported curve sources for one NODES region')
        _carrier(carrier[SOURCE], objects)
        nf = collect_curve_region(carrier, objects)
        if not 0 <= area < 64:
            raise ValueError('Curve editing currently supports the imported 64-region grid; use the mesh exporter for extended grids')
        if fla4 != nf.fla4:
            raise ValueError('FLA4 setting must match the imported Compiled NODES format')
        regions[area] = nf
        imports[area] = carrier.get('nodes_source_key', '')
    if entire_map:
        grouped = {}
        for obj in objects:
            if obj.type != 'MESH' or obj.get('path_type') not in ('nodes_vehicle', 'nodes_ped', 'nodes_navi'):
                continue
            area = obj.get('nodes_area')
            source = obj.get('nodes_source_key', '')
            if area in imports:
                if source != imports[area]:
                    raise ValueError('Multiple imported sources for one NODES region')
                continue
            grouped.setdefault((area, source), []).append(obj)
        for (area, source), meshes in grouped.items():
            if area is None or area in regions:
                raise ValueError('Cannot identify a unique NODES region')
            nf = collect_compiled_nodes(meshes)
            if nf.fla4 != fla4:
                raise ValueError('All exported regions must use the same imported NODES format')
            regions[area] = nf
    remaps = {key: value for nf in regions.values() for key, value in nf.node_remap.items()}
    if remaps:
        if set(regions) != set(range(64)):
            raise ValueError('NODES IDs changed: import all 64 regions and enable Entire map before exporting')
        for area, nf in regions.items():
            remap_foreign_references(nf, remaps, area=area)
    validate_graph_batch(regions)
    return regions


def write_curve_export(filepath, regions):
    """Serialize every region before replacing any user file."""
    if not filepath:
        raise ValueError('Choose an output nodes*.dat file')
    filepath = os.path.abspath(filepath)
    folder = os.path.dirname(filepath)
    if not os.path.isdir(folder):
        raise ValueError('Choose an existing output directory')
    if len(regions) == 1:
        area = next(iter(regions))
        if os.path.basename(filepath).casefold() != f'nodes{area}.dat':
            raise ValueError(f'This region must be exported as nodes{area}.dat')
    with tempfile.TemporaryDirectory(prefix='.inu_nodes_', dir=folder) as staging:
        staged = []
        for area, nf in sorted(regions.items()):
            name = f'nodes{area}.dat'
            target = os.path.join(folder, name)
            if os.path.exists(target) and not os.access(target, os.W_OK):
                raise ValueError(f'Output file is not writable: {name}')
            path = os.path.join(staging, name)
            write_nodes(path, nf)
            staged.append((path, target))
        for path, target in staged:
            os.replace(path, target)
