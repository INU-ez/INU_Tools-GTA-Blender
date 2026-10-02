"""Rebuild an edited SA node graph without treating vertex indices as IDs.

Navigation addresses use the game's 6-bit area / 10-bit index packing.
Existing navigation records retain their indices: neighbouring regions may
refer to them even when the corresponding local mesh edge was removed.
"""

import copy
import math
from dataclasses import replace

from .paths import (NaviNode, PathLink, PNODE_LINK_COUNT_MASK,
                    PATH_INTERSECTION_TRAILING, encode_navi_flags)


def navi_address(area, index, fla4=False):
    limit = 65536 if fla4 else 1024
    if not 0 <= index < limit or not 0 <= area < (65536 if fla4 else 64):
        raise ValueError('Navigation address capacity exceeded')
    return (area << (16 if fla4 else 10)) | index


def unpack_navi_address(value, fla4=False):
    bits = 16 if fla4 else 10
    return value >> bits, value & ((1 << bits) - 1)


def graph_edges(nf, area):
    """Visible edges address the physical vehicle-then-ped array."""
    nodes = nf.vehicle_nodes + nf.ped_nodes
    edges = set()
    for src, node in enumerate(nodes):
        if not 0 <= node.link_id <= 65535:
            raise ValueError('Invalid node link index')
        for idx in range(node.link_id, node.link_id + (node.flags & 15)):
            if idx >= len(nf.links):
                raise ValueError('Node link range is outside the links array')
            link = nf.links[idx]
            dst = link.node_id
            if link.area_id != area or not 0 <= dst < len(nodes):
                continue
            if (src < len(nf.vehicle_nodes)) != (dst < len(nf.vehicle_nodes)):
                continue
            if src != dst:
                edges.add(tuple(sorted((src, dst))))
    return edges


def _distance(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def rebuild_graph(original, nodes, origins, edges, *, area, vehicle_count):
    """Return an edited NodesFile and old physical-index -> new-index map.

    ``origins`` contains the original physical index or None for a new
    point. Mesh edges describe local connections; untouched directed links,
    cross-category links and outgoing links to other areas are preserved.
    New road segments get a real navigation record and one lane each way.
    """
    old = original.vehicle_nodes + original.ped_nodes
    if len(nodes) != len(origins) or len(nodes) > 65536:
        raise ValueError('Invalid edited node count')
    by_old = {origin: i for i, origin in enumerate(origins) if origin is not None}
    if len(by_old) != sum(o is not None for o in origins):
        raise ValueError('Ambiguous duplicate node identity')
    if any(o is not None and not 0 <= o < len(old) for o in origins):
        raise ValueError('Invalid original node identity')
    edges = {tuple(sorted(e)) for e in edges}
    if any(a == b or a < 0 or b >= len(nodes) or
           (a < vehicle_count) != (b < vehicle_count) for a, b in edges):
        raise ValueError('Invalid or cross-category mesh edge')
    remap = {(area, i): by_old.get(i) for i in range(len(old))
             if by_old.get(i) != i}
    surviving_old_edges = {tuple(sorted((by_old[a], by_old[b])))
                           for a, b in graph_edges(original, area)
                           if a in by_old and b in by_old}
    unchanged = (origins == list(range(len(old))) and
                 vehicle_count == len(original.vehicle_nodes) and
                 edges == surviving_old_edges)
    result = copy.deepcopy(original)
    result.vehicle_nodes = nodes[:vehicle_count]
    result.ped_nodes = nodes[vehicle_count:]
    if unchanged:
        return result, {}, False
    for index, node in enumerate(nodes):
        # Preserve foreign stub identities, but all own nodes use physical IDs.
        if origins[index] is None or node.area_id == area:
            node.area_id, node.node_id = area, index
    if original.extra_data or (original.links and not original.parsed_extras):
        raise ValueError('Reimport NODES with parsed link sections before editing topology')
    if any(n.area_id == area and n.node_id != i for i, n in enumerate(old)):
        raise ValueError('Cannot edit noncanonical node identities')
    if original.links and any(len(a) < len(original.links) for a in
                              (original.navi_links, original.link_lengths,
                               original.path_intersections)):
        raise ValueError('Incomplete navigation/link sections')

    # Collect original directed arcs with their per-link metadata.
    outgoing = [[] for _ in nodes]
    present = set()
    original_arcs = {}
    for old_src, source in enumerate(old):
        if old_src not in by_old:
            continue
        src = by_old[old_src]
        for idx in range(source.link_id, source.link_id + (source.flags & 15)):
            if idx >= len(original.links):
                raise ValueError('Node link range is outside the links array')
            link = original.links[idx]
            dst = None
            if link.area_id == area:
                dst = by_old.get(link.node_id)
                if dst is None:
                    continue
                same_category = ((src < vehicle_count) == (dst < vehicle_count))
                if src != dst and same_category and tuple(sorted((src, dst))) not in edges:
                    continue
                target = PathLink(area, dst)
            else:
                target = replace(link)
            outgoing[src].append((target, original.navi_links[idx],
                                  original.link_lengths[idx], original.path_intersections[idx]))
            if dst is not None:
                present.add((src, dst))
    # Also remember removed internal edges for subdivision lane data.
    for old_src, source in enumerate(old):
        for idx in range(source.link_id, source.link_id + (source.flags & 15)):
            link = original.links[idx]
            if link.area_id == area and old_src in by_old and link.node_id in by_old:
                original_arcs[(by_old[old_src], by_old[link.node_id])] = idx

    # Subdividing an existing segment preserves its lane counts/direction
    # and its original directed arcs. New branches default to one lane each
    # way. Only an unambiguous chain of degree-two new points inherits data.
    adjacency = [[] for _ in nodes]
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    subdivisions = {}
    for a, b in surviving_old_edges - edges:
        chains = []
        for neighbor in adjacency[a]:
            previous, current, chain = a, neighbor, [a]
            visited = {a}
            while current != b and origins[current] is None and len(adjacency[current]) == 2 and current not in visited:
                visited.add(current)
                chain.append(current)
                following = next(p for p in adjacency[current] if p != previous)
                previous, current = current, following
            if current == b:
                chains.append(chain + [b])
        if len(chains) != 1:
            continue
        chain = chains[0]
        forward, reverse = (a, b) in original_arcs, (b, a) in original_arcs
        index = original_arcs[(a, b) if forward else (b, a)]
        nav_area, nav_index = unpack_navi_address(original.navi_links[index], original.fla4)
        template = (original.navi_nodes[nav_index] if nav_area == area and
                    nav_index < len(original.navi_nodes) else None)
        attached_to_end = template is not None and template.node_id == origins[b]
        for left, right in zip(chain, chain[1:]):
            subdivisions[tuple(sorted((left, right)))] = (
                right if attached_to_end else left,
                template.flags if template is not None else None,
                {(left, right)} if forward and not reverse else
                {(right, left)} if reverse and not forward else {(left, right), (right, left)})

    # Reattach surviving local navigation records. Unused deleted records
    # keep their index but get an invalid address, never an unrelated node.
    for nav in result.navi_nodes:
        if nav.area_id == area:
            attached = by_old.get(nav.node_id)
            nav.area_id, nav.node_id = ((area, attached) if attached is not None
                                       else (0xFFFF, 0xFFFF))
    for a, b in sorted(edges):
        missing = [(src, dst) for src, dst in ((a, b), (b, a))
                   if (src, dst) not in present]
        # A surviving original one-direction edge must remain one-direction.
        if ((a, b) in present or (b, a) in present):
            continue
        nav_ref = 0
        subdivision = subdivisions.get((a, b))
        if subdivision is not None:
            missing = [arc for arc in missing if arc in subdivision[2]]
        if a < vehicle_count:
            attached = subdivision[0] if subdivision is not None else a
            other = b if attached == a else a
            first, second = nodes[attached], nodes[other]
            # Use the positions SA will actually read. Coordinates on
            # opposite sides of zero can quantize to the same position.
            fx, fy = int(first.x*8)/8, int(first.y*8)/8
            sx, sy = int(second.x*8)/8, int(second.y*8)/8
            dx, dy = fx - sx, fy - sy
            length = math.hypot(dx, dy)
            if length < 0.125:
                raise ValueError('Vehicle edge needs distinct XY positions')
            nav_ref = navi_address(area, len(result.navi_nodes), result.fla4)
            width = min(127, max(0, first.path_width))
            flags = (subdivision[1] if subdivision is not None else None)
            if flags is None:
                flags = encode_navi_flags(left_lanes=1, right_lanes=1, keep_bits=width)
            result.navi_nodes.append(NaviNode(
                x=(fx + sx) / 2, y=(fy + sy) / 2,
                area_id=area, node_id=attached,
                dir_x=round(100 * dx / length), dir_y=round(100 * dy / length),
                flags=flags))
        for src, dst in missing:
            outgoing[src].append((PathLink(area, dst), nav_ref,
                                  max(1, min(255, int(_distance(nodes[src], nodes[dst])))), 0))

    padding = original.path_intersections[len(original.links):]
    result.links, result.navi_links, result.link_lengths, result.path_intersections = [], [], [], []
    for node, links in zip(nodes, outgoing):
        if len(links) > 15:
            raise ValueError('A path node cannot have more than 15 outgoing links')
        node.link_id = len(result.links)
        if node.link_id > 65535:
            raise ValueError('Node link index capacity exceeded')
        node.flags = (node.flags & ~PNODE_LINK_COUNT_MASK) | len(links)
        for target, nav, length, intersection in links:
            result.links.append(target)
            result.navi_links.append(nav)
            result.link_lengths.append(length)
            result.path_intersections.append(intersection)
    result.path_intersections.extend((padding + [0] * PATH_INTERSECTION_TRAILING)[:PATH_INTERSECTION_TRAILING])
    result.parsed_extras, result.extra_data = True, b''
    return result, remap, True


def remap_foreign_references(nf, remap, *, area):
    """Drop links to deleted nodes and update incoming foreign addresses.

    Local references have already been rebuilt. Compact all four parallel
    link arrays together, preserving the section-7 trailing padding.
    """
    if not remap:
        return
    if nf.extra_data or (nf.links and not nf.parsed_extras):
        raise ValueError('Cannot remap an unparsed nodes tail')
    old_links = nf.links
    arrays = nf.navi_links, nf.link_lengths, nf.path_intersections
    if old_links and any(len(a) < len(old_links) for a in arrays):
        raise ValueError('Incomplete navigation/link sections')
    padding = nf.path_intersections[len(old_links):]
    rebuilt = [], [], [], []
    for node in nf.vehicle_nodes + nf.ped_nodes:
        start, count = node.link_id, node.flags & 15
        node.link_id = len(rebuilt[0])
        kept = 0
        for idx in range(start, start + count):
            if idx >= len(old_links):
                raise ValueError('Node link range is outside the links array')
            link = old_links[idx]
            mapped = remap.get((link.area_id, link.node_id), link.node_id) if link.area_id != area else link.node_id
            if mapped is None:
                continue
            rebuilt[0].append(PathLink(link.area_id, mapped))
            for dst, source in zip(rebuilt[1:], arrays):
                dst.append(source[idx])
            kept += 1
        node.flags = (node.flags & ~15) | kept
        if node.area_id != area:
            mapped = remap.get((node.area_id, node.node_id), node.node_id)
            if mapped is None:
                raise ValueError('Deleting a node referenced by a foreign stub is unsupported')
            node.node_id = mapped
    nf.links, nf.navi_links, nf.link_lengths, nf.path_intersections = rebuilt
    nf.path_intersections.extend(padding)
    for nav in nf.navi_nodes:
        if nav.area_id != area:
            mapped = remap.get((nav.area_id, nav.node_id), nav.node_id)
            if mapped is None:
                nav.area_id = nav.node_id = 0xFFFF
            else:
                nav.node_id = mapped


def validate_graph_batch(regions):
    """Validate every reachable node/navigation address before writing."""
    for area, nf in regions.items():
        nodes = nf.vehicle_nodes + nf.ped_nodes
        for index, node in enumerate(nodes):
            count = node.flags & 15
            if node.link_id < 0 or node.link_id + count > len(nf.links):
                raise ValueError('Node link range is outside the links array')
            for idx in range(node.link_id, node.link_id + count):
                link = nf.links[idx]
                if link.node_id < 0 or not 0 <= link.area_id < (65536 if nf.fla4 else 72):
                    raise ValueError('Invalid node link address')
                target = regions.get(link.area_id)
                if target is not None and link.node_id >= len(target.vehicle_nodes + target.ped_nodes):
                    raise ValueError('Node link points outside its target region')
                if index >= len(nf.vehicle_nodes):
                    continue
                if idx >= len(nf.navi_links):
                    raise ValueError('Vehicle link has no navigation address')
                address = nf.navi_links[idx]
                if not 0 <= address < (1 << (32 if nf.fla4 else 16)):
                    raise ValueError('Invalid navigation link address')
                nav_area, nav_index = unpack_navi_address(address, nf.fla4)
                nav_file = regions.get(nav_area)
                if nav_file is None:
                    continue  # unchanged neighbouring file is outside this export
                if nav_index >= len(nav_file.navi_nodes):
                    raise ValueError('Vehicle link points outside the navigation array')
                nav = nav_file.navi_nodes[nav_index]
                attached = regions.get(nav.area_id)
                if nav.area_id == 0xFFFF or (attached is not None and nav.node_id >= len(attached.vehicle_nodes)):
                    raise ValueError('Vehicle navigation points to a deleted or non-vehicle node')
