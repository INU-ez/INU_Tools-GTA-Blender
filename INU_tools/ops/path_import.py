# INU_tools.ops.path_import — Import GTA SA path files into Blender

import bpy
from ..core.paths import read_flight, read_track, read_nodes, read_paths_ipl, PathNode


def import_flight(filepath: str, context=None):
    """Import flight.dat as curve objects in Blender."""
    data = read_flight(filepath)
    if not data.paths:
        return []

    col = _get_or_create_collection("Flight Paths")
    created = []

    for i, path in enumerate(data.paths):
        if not path.points:
            continue

        curve = bpy.data.curves.new(f"FlightPath_{i}", type='CURVE')
        curve.dimensions = '3D'
        spline = curve.splines.new('POLY')
        spline.points.add(len(path.points) - 1)

        for j, pt in enumerate(path.points):
            spline.points[j].co = (pt.x, pt.y, pt.z, 1.0)

        obj = bpy.data.objects.new(f"FlightPath_{i}", curve)
        obj['path_type'] = 'flight'
        obj['path_index'] = i
        col.objects.link(obj)

        # Style
        _setup_path_curve(curve)
        _assign_path_material(obj, 'FlightPath_Mat', (1.0, 1.0, 0.0, 0.8))  # Yellow

        created.append(obj)

    return created


def import_track(filepath: str, context=None):
    """Import tracks*.dat as a curve object in Blender."""
    import os
    data = read_track(filepath)
    if not data.nodes:
        return []

    col = _get_or_create_collection("Train Tracks")
    name = os.path.splitext(os.path.basename(filepath))[0]

    curve = bpy.data.curves.new(name, type='CURVE')
    curve.dimensions = '3D'
    spline = curve.splines.new('POLY')
    spline.points.add(len(data.nodes) - 1)
    spline.use_cyclic_u = True  # Train tracks loop

    station_indices = []
    for j, node in enumerate(data.nodes):
        spline.points[j].co = (node.x, node.y, node.z, 1.0)
        if node.flag == 1:
            station_indices.append(j)

    obj = bpy.data.objects.new(name, curve)
    obj['path_type'] = 'track'
    obj['station_indices'] = str(station_indices)  # Store station stops
    col.objects.link(obj)

    # Style
    _setup_path_curve(curve)
    _assign_path_material(obj, 'TrainTrack_Mat', (0.6, 0.3, 0.0, 0.8))  # Brown

    return [obj]


def import_nodes(filepath: str, context=None):
    """Import nodes*.dat as mesh objects with integrated visualization.

    Round-trip preservation: `data.extra_data` (naviLinks, linkLengths,
    pathIntersections — everything after the links section) and
    `data.fla4` flag are stored on **every** created object. The export
    operator includes all category companions from the same import.

    Visualization is **integrated into the data mesh** so editing one
    thing updates the visual immediately (no separate viz curve to
    keep in sync):
      * Vehicle/ped meshes get edges (from link graph) + Skin modifier
        → vertices show as a network of square tubes; moving a vertex
        moves the tube, adding a vertex extends the geometry.
      * Navi mesh enables `instance_type='VERTS'` and parents a child
        Empty (Cube display) → every vertex draws a small wireframe
        cube at its position; the child empty is hidden from selection
        so the user can only manipulate the underlying vertex.
    """
    import os, base64, uuid
    from .path_nodes_mesh import initialize_node_identity
    data = read_nodes(filepath)

    col = _get_or_create_collection("Path Nodes")
    name = os.path.splitext(os.path.basename(filepath))[0]
    from collections import Counter
    area_counts = Counter(n.area_id for n in data.vehicle_nodes + data.ped_nodes)
    area = (int(name[5:]) if name.casefold().startswith('nodes') and name[5:].isdigit()
            else (area_counts.most_common(1)[0][0] if area_counts else 0))
    source_key = uuid.uuid4().hex
    created = []

    # Vehicle nodes — mesh + chain edges (NO Skin modifier; user
    # toggles tube geometry on via `gtatools.toggle_nodes_viz`)
    if data.vehicle_nodes:
        veh_edges = _compute_intra_category_edges(data, is_vehicle=True, area=area)
        obj = _create_nodes_mesh(f"{name}_vehicle", data.vehicle_nodes, col,
                                 edges=veh_edges)
        obj['path_type'] = 'nodes_vehicle'
        obj['nodes_filename'] = name + '.dat'
        _assign_path_material(obj, 'VehicleNode_Mat', (0.0, 0.5, 1.0, 0.8))  # Blue
        created.append(obj)

    # Ped nodes — mesh + chain edges (NO Skin modifier; same as above)
    if data.ped_nodes:
        ped_edges = _compute_intra_category_edges(data, is_vehicle=False, area=area)
        obj = _create_nodes_mesh(f"{name}_ped", data.ped_nodes, col,
                                 edges=ped_edges)
        obj['path_type'] = 'nodes_ped'
        obj['nodes_filename'] = name + '.dat'
        _assign_path_material(obj, 'PedNode_Mat', (0.0, 1.0, 0.3, 0.8))  # Green
        created.append(obj)

    # Navi nodes — mesh + cube-empty instanced at every vertex
    if data.navi_nodes:
        mesh = bpy.data.meshes.new(f"{name}_navi")
        verts = [(n.x, n.y, 0.0) for n in data.navi_nodes]  # NaviNodes are 2D (X,Y)
        mesh.from_pydata(verts, [], [])
        mesh.update()
        obj = bpy.data.objects.new(f"{name}_navi", mesh)
        obj['path_type'] = 'nodes_navi'
        obj['nodes_filename'] = name + '.dat'

        # Per-navi data as parallel arrays (same perf rationale as
        # `_create_nodes_mesh` — bulk write instead of per-index).
        obj['navi_areas'] = [n.area_id for n in data.navi_nodes]
        obj['navi_ids']   = [n.node_id for n in data.navi_nodes]
        obj['navi_dx']    = [n.dir_x   for n in data.navi_nodes]
        obj['navi_dy']    = [n.dir_y   for n in data.navi_nodes]
        obj['navi_flags'] = [n.flags   for n in data.navi_nodes]
        obj['navi_count'] = len(data.navi_nodes)
        initialize_node_identity(obj, [PathNode(x=n.x, y=n.y) for n in data.navi_nodes])

        _assign_path_material(obj, 'NaviNode_Mat', (1.0, 0.5, 0.0, 0.8))  # Orange
        col.objects.link(obj)
        # Navi rendered as bare mesh vertices (theme's vertex display) —
        # the cube-empty VERTS-instance approach was tried but the
        # instances inherited the parent's selection outline, making
        # every cube look "active" by default. Plain vertices are clearer.
        created.append(obj)

    # Keep empty regions selectable for a complete 64-region reindex export.
    if not created:
        obj = _create_nodes_mesh(f"{name}_vehicle", [], col, edges=[])
        obj['path_type'] = 'nodes_vehicle'
        obj['nodes_filename'] = name + '.dat'
        created.append(obj)

    # Store links + post-link tail + FLA4 flag on EVERY created object.
    # All as **bulk arrays** — see `_create_nodes_mesh` docstring for
    # why per-index IDProperties were O(n²) and froze full-map imports.
    # Storing on every object keeps the metadata reachable from any
    # one of them on re-export.
    link_areas = [l.area_id for l in data.links] if data.links else []
    link_nodes = [l.node_id for l in data.links] if data.links else []
    extra_b64 = ''
    if data.extra_data and not data.parsed_extras:
        extra_b64 = base64.b64encode(data.extra_data).decode('ascii')
    for obj in created:
        obj['nodes_area'] = area
        obj['nodes_source_key'] = source_key
        obj['nodes_vehicle_count'] = len(data.vehicle_nodes)
        obj['nodes_ped_count'] = len(data.ped_nodes)
        obj['nodes_navi_count'] = len(data.navi_nodes)
        if data.links:
            obj['link_areas'] = link_areas
            obj['link_nodes'] = link_nodes
            obj['num_links'] = len(data.links)
        obj['fla4'] = bool(data.fla4)
        if data.parsed_extras:
            obj['parsed_extras']      = True
            obj['navi_links']         = list(data.navi_links)
            obj['link_lengths']       = list(data.link_lengths)
            obj['path_intersections'] = list(data.path_intersections)
        elif extra_b64:
            obj['extra_data_b64'] = extra_b64

    # Visualization is built into the data meshes themselves (Skin
    # modifier on edged vehicle/ped meshes + VERTS-instanced cube
    # empty on navi mesh) — no separate viz objects needed.

    # The navi mesh's VERTS-instanced cube empties take their wireframe
    # colour from the parent's selection / active state. After a fresh
    # import the new objects can end up active in some Blender
    # versions, which makes every instanced cube glow orange even
    # though the user didn't click anything. Clear selection / active
    # on what we created so the cubes render in their neutral default
    # colour; user can pick the navi mesh later to highlight them.
    for o in created:
        try:
            o.select_set(False)
        except Exception:
            pass
    try:
        vl = bpy.context.view_layer
        if vl.objects.active in created:
            vl.objects.active = None
    except Exception:
        pass

    return created


def import_paths_ipl(filepath: str, context=None):
    """Import paths.ipl as curve objects in Blender.

    Each path group becomes a curve. Vehicle = blue, Ped = green.
    Only non-empty nodes (node_type > 0) are imported as curve points.
    """
    game = getattr(getattr(context, 'scene', None), 'gtatools_game', 'VC')
    data = read_paths_ipl(filepath, game=game)
    if not data.groups:
        return []

    col = _get_or_create_collection("Path IPL")
    created = []

    for i, group in enumerate(data.groups):
        # Filter out empty nodes
        real_nodes = [n for n in group.nodes if n.node_type > 0]
        if not real_nodes:
            continue

        is_vehicle = (group.group_type != 0)
        prefix = "VehPath" if is_vehicle else "PedPath"

        curve = bpy.data.curves.new(f"{prefix}_{i}", type='CURVE')
        curve.dimensions = '3D'
        spline = curve.splines.new('POLY')
        spline.points.add(len(real_nodes) - 1)

        for j, node in enumerate(real_nodes):
            spline.points[j].co = (node.x, node.y, node.z, 1.0)

        obj = bpy.data.objects.new(f"{prefix}_{i}", curve)
        obj['path_type'] = 'path_ipl'
        obj['group_type'] = group.group_type
        obj['group_index'] = i
        obj['external_index'] = group.external_index
        obj['pn_game'] = data.game
        obj['pn_model_name'] = group.model_name
        obj['pn_semantics_version'] = 2
        # Keep exact source groups, padding and link graph on untouched
        # export. Store only each object's group, not the whole map N times.
        obj['pn_original_group'] = (group._raw_header
                                    + ''.join(n._raw for n in group.nodes))
        obj['pn_source_prefix'] = data._prefix
        obj['pn_source_suffix'] = data._suffix

        # Store full node data for round-trip export
        for j, node in enumerate(group.nodes):
            obj[f'pn_{j}_type'] = node.node_type
            obj[f'pn_{j}_link'] = node.link_id
            obj[f'pn_{j}_cross'] = node.crossing
            obj[f'pn_{j}_width'] = node.width
            obj[f'pn_{j}_ll'] = node.left_lanes
            obj[f'pn_{j}_rl'] = node.right_lanes
            obj[f'pn_{j}_speed'] = node.speed_limit
            obj[f'pn_{j}_flags'] = node.flags
            obj[f'pn_{j}_spawn'] = node.spawn_rate
            obj[f'pn_{j}_extra'] = ', '.join(node.extra_columns)
        obj['pn_count'] = len(group.nodes)
        from .path_ipl_props import ensure_point_slots
        pairs = ensure_point_slots(obj)
        obj['pn_import_slots'] = [slot for _, slot in pairs]
        obj['pn_import_positions'] = [v for point, _ in pairs
                                      for v in point.co[:3]]

        # Style
        _setup_path_curve(curve)
        if is_vehicle:
            _assign_path_material(obj, 'VehiclePath_IPL_Mat', (0.0, 0.5, 1.0, 0.8))
        else:
            _assign_path_material(obj, 'PedPath_IPL_Mat', (0.0, 1.0, 0.3, 0.8))

        col.objects.link(obj)
        created.append(obj)

    return created


# ── Helpers ────────────────────────────────────────────────────────

def _setup_path_curve(curve):
    """Apply standard path curve display settings."""
    curve.dimensions = '3D'
    curve.bevel_depth = 0.1
    curve.bevel_resolution = 0
    curve.use_fill_caps = True
    curve.extrude = 0.5
    curve.offset = 0.0


def _get_or_create_collection(name: str):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _create_nodes_mesh(name, nodes, collection, edges=None):
    """Create a mesh object with a vertex per node + optional edges
    (link graph), storing per-node data as **array** custom props.

    Why arrays vs. per-index props (e.g. `node_0_link`, `node_1_link`,
    `node_2_link`, ...): the per-index approach was setting one
    IDProperty per node per attribute. For a full-map import (64 zones
    × hundreds of nodes × 6 attributes) that's hundreds of thousands
    of property writes, each O(n) because IDProperty insertion
    rehashes the dict-like backing collection. Total cost was O(n²)
    and froze Blender for tens of seconds.

    Switching to bulk arrays — one property write per attribute per
    mesh — collapses that to ~6 writes per object regardless of node
    count, restoring linear-time import.

    Edges are still passed as `(i, j)` tuples for `from_pydata()`; the
    Skin modifier added by the caller renders them as 3D tubes.
    """
    mesh = bpy.data.meshes.new(name)
    verts = [(n.x, n.y, n.z) for n in nodes]
    mesh.from_pydata(verts, edges or [], [])
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)

    # Per-node data as parallel arrays indexed by vertex index.
    if nodes:
        obj['node_links']  = [n.link_id    for n in nodes]
        obj['node_areas']  = [n.area_id    for n in nodes]
        obj['node_ids']    = [n.node_id    for n in nodes]
        obj['node_widths'] = [n.path_width for n in nodes]
        obj['node_types']  = [n.node_type  for n in nodes]
        obj['node_flags']  = [n.flags      for n in nodes]
    obj['node_count'] = len(nodes)
    from .path_nodes_mesh import initialize_node_identity
    initialize_node_identity(obj, nodes)

    collection.objects.link(obj)
    return obj


def _compute_intra_category_edges(data, is_vehicle, area=None):
    """Walk the link graph and return edges (pairs of local indices)
    that stay within one category (vehicle-vehicle OR ped-ped).

    Cross-category links (vehicle ↔ ped) and cross-area links are
    skipped — they'd need their own viz pass since the local indexing
    is per-category. Caller uses the returned edges directly with
    `mesh.from_pydata()`, and a Skin modifier turns them into tubes.

    SA GetPathNode addresses the physical vehicle-then-ped array.
    Foreign stub identity fields do not change this addressing rule.
    """
    num_vehicle = len(data.vehicle_nodes)
    all_nodes = data.vehicle_nodes + data.ped_nodes
    if not all_nodes or not data.links:
        return []
    # Legacy callers without the file name use the most common area.
    area_counts = {}
    for node in all_nodes:
        area_counts[node.area_id] = area_counts.get(node.area_id, 0) + 1
    our_area = area if area is not None else max(area_counts.items(), key=lambda x: x[1])[0]

    edges = set()
    for i, node in enumerate(all_nodes):
        src_is_veh = (i < num_vehicle)
        if src_is_veh != is_vehicle:
            continue                            # not our category
        link_count = node.flags & 0x0F
        src_local = i if is_vehicle else i - num_vehicle
        for j in range(link_count):
            link_idx = node.link_id + j
            if link_idx >= len(data.links):
                break
            link = data.links[link_idx]
            if link.area_id != our_area:
                continue                        # cross-area
            tgt_idx = link.node_id
            if not 0 <= tgt_idx < len(all_nodes):
                continue
            tgt_is_veh = (tgt_idx < num_vehicle)
            if tgt_is_veh != is_vehicle:
                continue                        # cross-category
            tgt_local = tgt_idx if is_vehicle else tgt_idx - num_vehicle
            if src_local != tgt_local:
                edges.add((min(src_local, tgt_local),
                           max(src_local, tgt_local)))
    return list(edges)


def _add_skin_modifier(obj, edges, radius=0.4):
    """Add a Skin modifier to a mesh+edges object, set uniform per-
    vertex radii, and **mark one root per connected component**.

    Skin builds one tube tree per connected component of the edge
    graph and each tree REQUIRES a vertex flagged `use_root=True`.
    Blender auto-flags only vertex 0 — any other components stay
    un-rooted and produce no geometry. nodes*.dat graphs typically
    have many disconnected components (different road systems in
    one zone), so without per-component rooting most of the mesh
    renders as bare edges with no tubes.

    Strategy: BFS over the edge adjacency; the first vertex visited
    in each component becomes that component's root.
    """
    obj.modifiers.new("Path Skin", 'SKIN').use_smooth_shade = True
    if not obj.data.skin_vertices:
        return
    sv_data = obj.data.skin_vertices[0].data
    n = len(sv_data)

    # Uniform radius, clear all auto-flagged roots.
    for sv in sv_data:
        sv.radius = (radius, radius)
        sv.use_root = False

    # Build adjacency from edges, find components, one root each.
    adj = [set() for _ in range(n)]
    for a, b in edges:
        if 0 <= a < n and 0 <= b < n:
            adj[a].add(b)
            adj[b].add(a)
    visited = [False] * n
    for i in range(n):
        if visited[i]:
            continue
        sv_data[i].use_root = True
        stack = [i]
        while stack:
            v = stack.pop()
            if visited[v]:
                continue
            visited[v] = True
            for nb in adj[v]:
                if not visited[nb]:
                    stack.append(nb)


def _attach_vertex_cube_empty(parent_obj, collection, display_size=1.0):
    """Make `parent_obj`'s mesh instance a small cube-display Empty at
    every vertex. Lets the user see + edit data + viz as one mesh.

    The Empty is parented to the mesh and `hide_select` so the user
    can't accidentally pick it instead of the underlying mesh vertices.
    It also carries `path_type='nodes_viz'` so the exporter ignores it.
    """
    cube = bpy.data.objects.new(f"{parent_obj.name}_cube", None)
    cube.empty_display_type = 'CUBE'
    cube.empty_display_size = display_size
    cube.parent = parent_obj
    cube.hide_select = True
    cube['path_type'] = 'nodes_viz'
    collection.objects.link(cube)
    parent_obj.instance_type = 'VERTS'


def _assign_path_material(obj, mat_name, color):
    """Assign a colored material to a path object."""
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        for n in mat.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                n.inputs['Base Color'].default_value = color
                n.inputs['Alpha'].default_value = color[3]
                break
        mat.diffuse_color = color
        if hasattr(mat, 'blend_method'):
            mat.blend_method = 'BLEND'
    obj.data.materials.append(mat)


def _build_nodes_viz_curves(data, base_name, collection):
    """Build curve objects tracing the link graph for visualization.

    nodes*.dat is a graph, not a single polyline — but with chain
    tracing we can decompose it into a set of long polylines that
    cleanly render through `bevel/extrude` curve chrome:

      1. Build per-category adjacency (vehicle↔vehicle, ped↔ped,
         vehicle↔ped). Cross-category links live in their own bucket.
      2. For each graph, find chains: a chain starts at a node with
         degree != 2 (endpoint or intersection) and walks through
         degree-2 nodes until hitting another endpoint/intersection.
      3. Each chain → ONE multi-point POLY spline. Adjacent links
         within a chain share interior points → no rounded-endcap
         gaps where they meet.
      4. Closed loops (all nodes degree 2) get a single closed-cycle
         spline starting anywhere on the loop.

    Built as separate curves per category so they can be coloured
    distinctly. Marked `hide_select=True` + `path_type='nodes_viz'` so
    the export filter skips them and the user can't accidentally pick
    them while editing data meshes.
    """
    if not data.links:
        return

    all_nodes = data.vehicle_nodes + data.ped_nodes
    num_vehicle = len(data.vehicle_nodes)
    if not all_nodes:
        return
    # See _compute_intra_category_edges for why we pick most-common
    # area_id and resolve links via (area_id, node_id) lookup.
    area_counts = {}
    for node in all_nodes:
        area_counts[node.area_id] = area_counts.get(node.area_id, 0) + 1
    our_area = max(area_counts.items(), key=lambda x: x[1])[0]
    by_aid_nid = {(n.area_id, n.node_id): i for i, n in enumerate(all_nodes)}

    # ── Build adjacency per category ──────────────────────────────
    # adj_veh / adj_ped: set of neighbour indices (within the same
    # category's local indexing). cross_segs: direct line segments.
    n_veh = num_vehicle
    n_ped = len(data.ped_nodes)
    adj_veh = [set() for _ in range(n_veh)]
    adj_ped = [set() for _ in range(n_ped)]
    cross_segs = []
    seen_cross = set()

    for i, node in enumerate(all_nodes):
        link_count = node.flags & 0x0F
        src_is_veh = (i < num_vehicle)
        src_local = i if src_is_veh else i - num_vehicle
        for j in range(link_count):
            link_idx = node.link_id + j
            if link_idx >= len(data.links):
                break
            link = data.links[link_idx]
            if link.area_id != our_area:
                continue
            tgt_idx = by_aid_nid.get((link.area_id, link.node_id))
            if tgt_idx is None:
                continue
            tgt_is_veh = (tgt_idx < num_vehicle)
            tgt_local = tgt_idx if tgt_is_veh else tgt_idx - num_vehicle
            if src_is_veh and tgt_is_veh and src_local != tgt_local:
                adj_veh[src_local].add(tgt_local)
                adj_veh[tgt_local].add(src_local)
            elif (not src_is_veh) and (not tgt_is_veh) and src_local != tgt_local:
                adj_ped[src_local].add(tgt_local)
                adj_ped[tgt_local].add(src_local)
            elif src_is_veh != tgt_is_veh:
                src_co = (all_nodes[i].x, all_nodes[i].y, all_nodes[i].z)
                tgt_co = (all_nodes[tgt_idx].x, all_nodes[tgt_idx].y, all_nodes[tgt_idx].z)
                key = frozenset({src_co, tgt_co})
                if key not in seen_cross:
                    seen_cross.add(key)
                    cross_segs.append((src_co, tgt_co))

    # ── Chain tracing ─────────────────────────────────────────────
    veh_chains = _trace_chains(adj_veh, data.vehicle_nodes)
    ped_chains = _trace_chains(adj_ped, data.ped_nodes)

    _create_viz_curve_from_chains(f"{base_name}_vehicle_viz", veh_chains, collection,
                                  'VehicleNode_Viz_Mat', (0.0, 0.5, 1.0, 0.9))
    _create_viz_curve_from_chains(f"{base_name}_ped_viz", ped_chains, collection,
                                  'PedNode_Viz_Mat', (0.0, 1.0, 0.3, 0.9))
    # Cross-links stay as 2-point segments — they're inherently
    # bridge edges between two distinct subgraphs.
    _create_viz_curve(f"{base_name}_cross_viz", cross_segs, collection,
                      'NodeCross_Viz_Mat', (1.0, 0.5, 0.0, 0.9))


def _trace_chains(adj, nodes):
    """Decompose an undirected graph into chains (polylines).
    Returns list of [(x,y,z), (x,y,z), ...] — each one is a chain of
    coords ready to be turned into a POLY spline."""
    n = len(adj)
    visited = set()                            # frozenset({a,b}) per edge
    chains = []

    def walk(start, first_step):
        path = [start, first_step]
        visited.add(frozenset({start, first_step}))
        prev, curr = start, first_step
        while True:
            # Stop at non-degree-2 nodes (intersection/dead-end) — the
            # current node either has > 2 neighbours or only one, so
            # the chain terminates here.
            if len(adj[curr]) != 2:
                break
            nbrs = adj[curr] - {prev}
            if len(nbrs) != 1:
                break
            nxt = next(iter(nbrs))
            e = frozenset({curr, nxt})
            if e in visited:
                break
            visited.add(e)
            path.append(nxt)
            prev, curr = curr, nxt
        return path

    # Pass 1 — start from intersections and dead-ends. This covers
    # every chain except closed loops where every node has degree 2.
    for i in range(n):
        if len(adj[i]) == 2:
            continue
        for nb in list(adj[i]):
            e = frozenset({i, nb})
            if e in visited:
                continue
            chains.append(walk(i, nb))

    # Pass 2 — closed loops. Any unvisited edge belongs to one.
    for i in range(n):
        for nb in list(adj[i]):
            e = frozenset({i, nb})
            if e in visited:
                continue
            chains.append(walk(i, nb))

    return [[(nodes[k].x, nodes[k].y, nodes[k].z) for k in path] for path in chains]


def _create_viz_curve_from_chains(name, chains, collection, mat_name, color):
    """Build a curve object where each chain is one POLY spline.
    Same chrome as `_create_viz_curve` (bevel + extrude → 3-D tube).
    """
    if not chains:
        return None
    curve = bpy.data.curves.new(name, type='CURVE')
    curve.dimensions = '3D'
    for chain in chains:
        if len(chain) < 2:
            continue
        spline = curve.splines.new('POLY')
        spline.points.add(len(chain) - 1)      # POLY starts with 1 point
        for i, co in enumerate(chain):
            spline.points[i].co = (co[0], co[1], co[2], 1.0)
    obj = bpy.data.objects.new(name, curve)
    obj['path_type'] = 'nodes_viz'
    obj.hide_select = True
    _setup_path_curve(curve)
    _assign_path_material(obj, mat_name, color)
    collection.objects.link(obj)
    return obj


def _build_navi_direction_arrows(data, base_name, collection):
    """Draw a short directional segment at every navi node.

    Each navi node carries an int8 (dir_x, dir_y) which encodes the
    direction it "looks at" — used by the AI for next-hop choice. We
    normalise that to a unit vector and emit a fixed-length 3-m
    segment, so the arrow length is consistent regardless of the raw
    magnitude (which the parser leaves as the original signed-byte
    value — its real-world scale is not 100% documented).

    Nodes with a near-zero direction (dir_x == dir_y == 0) are
    skipped — no meaningful arrow to draw.
    """
    if not data.navi_nodes:
        return
    import math
    LENGTH = 3.0      # metres — comparable to a vehicle length
    segments = []
    for navi in data.navi_nodes:
        dx, dy = float(navi.dir_x), float(navi.dir_y)
        mag = math.hypot(dx, dy)
        if mag < 0.5:
            continue
        udx, udy = dx / mag, dy / mag
        src = (navi.x, navi.y, 0.0)
        dst = (navi.x + udx * LENGTH, navi.y + udy * LENGTH, 0.0)
        segments.append((src, dst))
    _create_viz_curve(f"{base_name}_navi_viz", segments, collection,
                      'NaviNode_Viz_Mat', (1.0, 0.5, 0.0, 0.9))


def _create_viz_curve(name, segments, collection, mat_name, color):
    """Build a multi-spline POLY curve from line segments and apply
    the standard path-curve chrome (bevel + extrude → 3D tube)."""
    if not segments:
        return None
    curve = bpy.data.curves.new(name, type='CURVE')
    curve.dimensions = '3D'
    for src, dst in segments:
        spline = curve.splines.new('POLY')
        spline.points.add(1)                   # POLY starts with 1 point
        spline.points[0].co = (src[0], src[1], src[2], 1.0)
        spline.points[1].co = (dst[0], dst[1], dst[2], 1.0)
    obj = bpy.data.objects.new(name, curve)
    # Tag so the export filter never picks this up — `nodes_filename`
    # absent + `path_type` doesn't start with `nodes_`.
    obj['path_type'] = 'nodes_viz'
    obj.hide_select = True                     # data lives on sibling meshes
    _setup_path_curve(curve)
    _assign_path_material(obj, mat_name, color)
    collection.objects.link(obj)
    return obj
