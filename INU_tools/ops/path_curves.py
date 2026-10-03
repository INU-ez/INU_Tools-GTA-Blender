# INU_tools.ops.path_curves
# Curve-based authoring for GTA SA path nodes (Kams / ZZPuma style).
#
# Two complementary operators:
#   - GTATOOLS_OT_nodes_to_curves: split an imported nodes mesh into one
#     Blender Curve per lane chain. Path attributes (type/width/spawn/
#     highway/lane counts) live on the Curve object as `sapath_*`
#     IDProperties, mirroring how Kams' MaxScript stores them on the
#     SplineShape.
#   - GTATOOLS_OT_curves_to_nodes: retained to report a blocked export.
#     The legacy curve writer loses original IDs and foreign links,
#     then combines rebuilt links with unrelated navigation/tail data.
#     Use the Compiled NODES mesh exporter until this path is rebuilt.

from __future__ import annotations

import bpy
from bpy.props import StringProperty, FloatProperty, BoolProperty
import math

from .. import T
from ..tools.compat import safe_icon, inu_icon
from ..core.paths import (
    PathNode, NodesFile,
    decode_path_node_flags, encode_path_node_flags,
    get_area_id, PATHSET_VANILLA,
)


# Two knots are considered the same path node when their world-space
# distance is below this threshold. Mirrors ZZPuma's `nodeDistLimit`
# default of 0.25 — chosen because consecutive nodes in vanilla SA
# rarely sit closer than 1 m and a 25 cm fudge swallows authoring drift.
NODE_DIST_LIMIT = 0.25

_CURVES_EXPORT_BLOCKED = (
    "Экспорт NODES через Curves временно заблокирован: связи могут повреждаться. "
    "Используйте обычный экспорт Compiled NODES из исходных мешей."
)


# ── Curve ↔ flags property mapping ──────────────────────────────
# Same key names as ZZPuma's GetUserProp / SetUserProp so files
# round-trip between addons (a Curve authored in INU Tools can be
# opened in Max via ZZPuma if its props are mirrored to UserProps).
_SAPATH_PROPS = (
    'sapath_type',      # 1=Ped, 2=Vehicle
    'sapath_width',
    'sapath_pathid',
    'sapath_traffic',
    'sapath_spawn',
    'sapath_roadblock',
    'sapath_boats',
    'sapath_emergency',
    'sapath_highway',
    'sapath_parking',
    'sapath_laneright',
    'sapath_laneleft',
)


def _set_curve_wirecolor(curve_obj):
    """Auto-colour curve wireframe by sapath_type / flags so the user
    can identify path purpose at a glance — mirrors ZZPuma's
    `setShapeColors`. Priority order (ZZPuma's logic):
      type=1 (Ped)       → green
      type=2 (Vehicle)   → red
        + boats=1        → blue
        + parking=1      → orange (overrides everything else)
        + traffic=2      → darker (subtract 75 from RGB)
        + highway=1      → add 150 to blue channel
    Result is clamped to 0-255 and written to ``obj.color`` (RGBA).
    Object viewport display has to be set to "Object" colour for this
    to render — we leave that to the user (it's a one-time setting).
    """
    t = int(curve_obj.get('sapath_type', 1) or 1)
    boats = bool(int(curve_obj.get('sapath_boats', 0) or 0))
    parking = bool(int(curve_obj.get('sapath_parking', 0) or 0))
    traffic = int(curve_obj.get('sapath_traffic', 1) or 1)
    highway = bool(int(curve_obj.get('sapath_highway', 0) or 0))

    r = g = b = 0
    if t == 1:
        r, g, b = 0, 255, 0  # Ped — green
    elif t == 2:
        r, g, b = 255, 0, 0  # Vehicle — red
        if boats:
            r, g, b = 0, 0, 255  # Boat — blue
        if parking:
            r, g, b = 255, 150, 0  # Parking — orange (early exit)
            curve_obj.color = (r / 255, g / 255, b / 255, 1.0)
            return
    if traffic == 2:
        r = max(0, r - 75); g = max(0, g - 75); b = max(0, b - 75)
    if highway:
        b = min(255, b + 150)
    curve_obj.color = (r / 255, g / 255, b / 255, 1.0)


def _set_curve_defaults(curve_obj):
    """Seed sapath_* props with sane defaults — called when a fresh
    Curve has no props yet (user just added Curve→Bezier and ran the
    converter). Defaults match ZZPuma's `setDefault` block."""
    if curve_obj.get('sapath_type') is None:        curve_obj['sapath_type'] = 1
    if curve_obj.get('sapath_width') is None:       curve_obj['sapath_width'] = 0.0
    if curve_obj.get('sapath_pathid') is None:      curve_obj['sapath_pathid'] = 0
    if curve_obj.get('sapath_traffic') is None:     curve_obj['sapath_traffic'] = 1
    if curve_obj.get('sapath_spawn') is None:       curve_obj['sapath_spawn'] = 1.0
    if curve_obj.get('sapath_roadblock') is None:   curve_obj['sapath_roadblock'] = 0
    if curve_obj.get('sapath_boats') is None:       curve_obj['sapath_boats'] = 0
    if curve_obj.get('sapath_emergency') is None:   curve_obj['sapath_emergency'] = 0
    if curve_obj.get('sapath_highway') is None:     curve_obj['sapath_highway'] = 0
    if curve_obj.get('sapath_parking') is None:     curve_obj['sapath_parking'] = 0
    if curve_obj.get('sapath_laneright') is None:   curve_obj['sapath_laneright'] = 1
    if curve_obj.get('sapath_laneleft') is None:    curve_obj['sapath_laneleft'] = 1


def _curve_to_path_nodes(curve_obj, path_set: int = PATHSET_VANILLA,
                          starting_node_id: int = 0):
    """Walk every knot of every spline in a Curve and emit PathNode
    instances. Properties on the Curve object propagate to each node's
    flags. Returns ``(nodes, links)`` where ``links`` is a list of
    (from_idx, to_idx) tuples within the curve, suitable for feeding
    into a global cross-curve link reconciliation pass."""
    nodes = []
    links = []
    mw = curve_obj.matrix_world
    is_vehicle = int(curve_obj.get('sapath_type', 1)) == 2

    # Build flag value once — same flags apply to every node in this
    # curve since shape-level props are shape-level (Kams convention).
    flags = encode_path_node_flags(
        roadblock=bool(curve_obj.get('sapath_roadblock', 0)),
        boats=bool(curve_obj.get('sapath_boats', 0)),
        emergency=bool(curve_obj.get('sapath_emergency', 0)),
        highway=bool(curve_obj.get('sapath_highway', 0)),
        parking=bool(curve_obj.get('sapath_parking', 0)),
        spawn=int(round(float(curve_obj.get('sapath_spawn', 1.0)) * 15)),
    )
    width_byte = int(round(float(curve_obj.get('sapath_width', 0.0)) * 8))

    if curve_obj.type != 'CURVE':
        return nodes, links

    next_id = starting_node_id
    for spline in curve_obj.data.splines:
        first_in_spline = next_id
        points = (spline.bezier_points if spline.type == 'BEZIER'
                  else spline.points)
        for i, p in enumerate(points):
            co = p.co
            wpos = mw @ (co.xyz if hasattr(co, 'xyz') else co)
            area_id = get_area_id(wpos.x, wpos.y, path_set)
            node = PathNode(
                x=wpos.x, y=wpos.y, z=wpos.z,
                link_id=0,         # Filled in by reconciliation pass.
                area_id=area_id,
                node_id=next_id,
                path_width=width_byte,
                node_type=0,
                flags=flags,
                is_vehicle=is_vehicle,
            )
            nodes.append(node)
            if i > 0:
                # Consecutive knots in a spline are always linked.
                links.append((next_id - 1, next_id))
                links.append((next_id, next_id - 1))
            next_id += 1
        # Closed splines wrap the last knot to the first.
        if getattr(spline, 'use_cyclic_u', False) and next_id - first_in_spline > 1:
            links.append((next_id - 1, first_in_spline))
            links.append((first_in_spline, next_id - 1))

    return nodes, links


def _stitch_cross_curve_links(curves, all_nodes, all_links):
    """Deprecated — superseded by ``_dedup_coincident_nodes``.

    Previously: for each knot pair within ``NODE_DIST_LIMIT`` of each
    other, appended a bidirectional link between the two PathNode
    indices. This left both nodes in the output, producing 22-30 %
    duplicate path nodes per export pass (cumulative on multiple
    re-exports) and a denser-than-needed path graph in-game.

    Now: merging is done in ``_dedup_coincident_nodes`` which collapses
    coincident knots into a single canonical PathNode and remaps all
    link references. Kept as a no-op stub for backward compat with
    older call sites; can be removed once nothing references it.
    """
    return


def _dedup_coincident_nodes(all_nodes, all_links):
    """Merge nodes whose positions coincide within ``NODE_DIST_LIMIT``.

    When ``Mesh → Curves`` splits a path graph into chains by junctions,
    every chain that touches an intersection ends with a control point
    at the junction's position. Two adjacent chains → two duplicate
    PathNodes at the intersection. Without deduplication the round-trip
    grows the node count by ~20 % each pass and the game ends up with
    redundant path nodes that bloat memory and slow A*.

    Algorithm:
      1. Grid-bucket nodes by floor(pos / threshold) so we only compare
         neighbours within ±1 cell (O(N) instead of O(N²)).
      2. For each node, find any earlier-indexed node within
         ``NODE_DIST_LIMIT`` and same category (vehicle vs ped). Mark
         it as a duplicate of that canonical.
      3. Remap every link reference from duplicates to their canonical.
      4. Drop self-links and dedup link pairs while preserving order.
      5. Return the compacted node list and remapped link list.

    Note: only same-category (vehicle↔vehicle, ped↔ped) merges are
    performed — a vehicle knot and a ped knot sharing a coordinate are
    intentional (cross-category intersection points) and stay separate.
    """
    threshold2 = NODE_DIST_LIMIT * NODE_DIST_LIMIT
    # Bucket key: (cell_x, cell_y, cell_z, is_vehicle)
    buckets = {}

    def _cell(n):
        return (int(n.x / NODE_DIST_LIMIT),
                int(n.y / NODE_DIST_LIMIT),
                int(n.z / NODE_DIST_LIMIT),
                bool(n.is_vehicle))

    # canonical[i] = index of the kept node that i collapses into.
    # If canonical[i] == i, node i is kept.
    canonical = list(range(len(all_nodes)))
    for i, ni in enumerate(all_nodes):
        cell = _cell(ni)
        # Inspect this cell + 26 neighbours (±1 in x/y/z).
        merged = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    neighbour_cell = (cell[0] + dx, cell[1] + dy,
                                      cell[2] + dz, cell[3])
                    for j in buckets.get(neighbour_cell, ()):
                        nj = all_nodes[j]
                        ddx = ni.x - nj.x
                        ddy = ni.y - nj.y
                        ddz = ni.z - nj.z
                        if ddx * ddx + ddy * ddy + ddz * ddz <= threshold2:
                            canonical[i] = canonical[j]
                            merged = True
                            break
                    if merged:
                        break
                if merged:
                    break
            if merged:
                break
        if not merged:
            buckets.setdefault(cell, []).append(i)

    # Build compact node list (only canonicals, in original order) and
    # a remap old_idx → new_idx.
    remap = {}
    new_nodes = []
    for old_i, c in enumerate(canonical):
        if c == old_i:
            remap[old_i] = len(new_nodes)
            new_nodes.append(all_nodes[old_i])
    # Non-canonical old indices map to their canonical's NEW index.
    for old_i, c in enumerate(canonical):
        if c != old_i:
            remap[old_i] = remap[c]

    # Renumber node_id within each (area, category) so node_id field
    # stays consecutive 0..N-1 — the writer's link section uses these
    # values, downstream tools may rely on it.
    veh_counter = {}
    ped_counter = {}
    for n in new_nodes:
        if n.is_vehicle:
            n.node_id = veh_counter.get(n.area_id, 0)
            veh_counter[n.area_id] = n.node_id + 1
        else:
            n.node_id = ped_counter.get(n.area_id, 0)
            ped_counter[n.area_id] = n.node_id + 1

    # Remap link endpoints, drop self-links and duplicates.
    seen = set()
    new_links = []
    for from_i, to_i in all_links:
        a = remap.get(from_i)
        b = remap.get(to_i)
        if a is None or b is None or a == b:
            continue
        key = (a, b)
        if key in seen:
            continue
        seen.add(key)
        new_links.append(key)

    return new_nodes, new_links


def build_nodes_file_from_curves(curves, path_set: int = PATHSET_VANILLA) -> NodesFile:
    """Convert a list of Curve objects into a single NodesFile."""
    nf = NodesFile()
    all_nodes = []
    all_links = []

    next_id = 0
    for c in curves:
        _set_curve_defaults(c)
        nodes, links = _curve_to_path_nodes(c, path_set, next_id)
        all_nodes.extend(nodes)
        all_links.extend(links)
        next_id += len(nodes)

    # Merge knots that coincide across curves (intersections) so the
    # exported graph has one PathNode per real-world position instead
    # of one per visiting curve. Replaces the legacy stitch-only path.
    all_nodes, all_links = _dedup_coincident_nodes(all_nodes, all_links)

    # Update each node's link_id (offset of its first outgoing link in
    # the global link list) and pack link_count into flags low nibble.
    by_from = {}
    for from_idx, to_idx in all_links:
        by_from.setdefault(from_idx, []).append(to_idx)

    # Build PathLink entries grouped by source node order.
    link_offset = 0
    for i, node in enumerate(all_nodes):
        outgoing = by_from.get(i, [])
        node.link_id = link_offset
        # Re-pack flags with updated link_count low nibble.
        decoded = decode_path_node_flags(node.flags)
        decoded['link_count'] = min(len(outgoing), 15)
        node.flags = encode_path_node_flags(**{
            k: v for k, v in decoded.items() if k != 'not_highway'
        })
        for to_idx in outgoing:
            target = all_nodes[to_idx]
            from ..core.paths import PathLink
            nf.links.append(PathLink(
                area_id=target.area_id, node_id=target.node_id))
            link_offset += 1

    # Split into vehicle vs ped pools.
    for node in all_nodes:
        if node.is_vehicle:
            nf.vehicle_nodes.append(node)
        else:
            nf.ped_nodes.append(node)

    # Initialise post-link arrays at link count length so write_nodes
    # emits a complete file (parsed_extras path). Zero defaults are
    # game-acceptable — user can tune later.
    n_links = len(nf.links)
    nf.navi_links = [0] * n_links
    nf.link_lengths = [0] * n_links
    nf.path_intersections = [0] * (n_links + 192)
    nf.parsed_extras = True

    return nf


# ── Operator: build curves from a nodes mesh ──────────────────────

class GTATOOLS_OT_nodes_to_curves(bpy.types.Operator):
    """Split an imported nodes mesh into one Blender Curve per lane chain.

    Reads the mesh's edge graph (built by `path_import._create_nodes_mesh`),
    traces connected chains, and emits a Curve per chain with sapath_*
    properties seeded from the per-vertex flag IDProperties. The
    original mesh is left untouched so the user can compare side-by-side."""
    bl_idname = "gtatools.nodes_to_curves"
    bl_label = "INU: Nodes Mesh → Curves"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            return False
        return obj.get('path_type') in ('nodes_vehicle', 'nodes_ped')

    def execute(self, context):
        mesh_obj = context.active_object
        mesh = mesh_obj.data
        if not mesh.edges:
            self.report({'ERROR'},
                        T("Меш не содержит рёбер — путь не построен"))
            return {'CANCELLED'}

        is_vehicle = mesh_obj.get('path_type') == 'nodes_vehicle'

        # Adjacency list from edges (undirected).
        adj = {i: [] for i in range(len(mesh.vertices))}
        for e in mesh.edges:
            adj[e.vertices[0]].append(e.vertices[1])
            adj[e.vertices[1]].append(e.vertices[0])

        # Trace chains: start from any vertex with degree != 2 (junction
        # or endpoint), walk until hitting another such vertex. Fall back
        # to closed-loop tracing for graphs that are pure cycles.
        visited_edges = set()
        chains = []

        def _edge_key(a, b):
            return (a, b) if a < b else (b, a)

        def _walk(start, first_step):
            chain = [start, first_step]
            visited_edges.add(_edge_key(start, first_step))
            cursor = first_step
            prev = start
            while True:
                nexts = [n for n in adj[cursor]
                         if n != prev and _edge_key(cursor, n) not in visited_edges]
                if not nexts or len(adj[cursor]) != 2:
                    break
                nxt = nexts[0]
                visited_edges.add(_edge_key(cursor, nxt))
                chain.append(nxt)
                prev = cursor
                cursor = nxt
            return chain

        for v in range(len(mesh.vertices)):
            if len(adj[v]) == 2:
                continue
            for nb in adj[v]:
                ek = _edge_key(v, nb)
                if ek in visited_edges:
                    continue
                chains.append(_walk(v, nb))

        # Sweep remaining cycles (pure loops with all-degree-2 vertices).
        for v in range(len(mesh.vertices)):
            for nb in adj[v]:
                ek = _edge_key(v, nb)
                if ek not in visited_edges:
                    chains.append(_walk(v, nb))

        if not chains:
            self.report({'ERROR'},
                        T("Не нашли цепочек путей в меше"))
            return {'CANCELLED'}

        # Build curves.
        col_name = "Path Curves"
        if col_name not in bpy.data.collections:
            bpy.data.collections.new(col_name)
            context.scene.collection.children.link(bpy.data.collections[col_name])
        col = bpy.data.collections[col_name]

        mw = mesh_obj.matrix_world
        # Bulk-read per-vertex flags + width if present on the source mesh.
        flags_arr = list(mesh_obj.get('node_flags', []))
        width_arr = list(mesh_obj.get('node_widths', []))

        base_name = mesh_obj.name + "_curves"
        new_curves = []
        for ci, chain in enumerate(chains):
            curve_data = bpy.data.curves.new(
                name=f"{base_name}_{ci:03d}", type='CURVE')
            curve_data.dimensions = '3D'
            spline = curve_data.splines.new('POLY')
            spline.points.add(len(chain) - 1)
            for pi, vi in enumerate(chain):
                wco = mw @ mesh.vertices[vi].co
                spline.points[pi].co = (wco.x, wco.y, wco.z, 1.0)

            curve_obj = bpy.data.objects.new(curve_data.name, curve_data)
            curve_obj['sapath_type'] = 2 if is_vehicle else 1
            # Seed sapath_* from the first node's flags / width.
            if flags_arr and chain[0] < len(flags_arr):
                decoded = decode_path_node_flags(int(flags_arr[chain[0]]))
                curve_obj['sapath_roadblock'] = int(decoded['roadblock'])
                curve_obj['sapath_boats']     = int(decoded['boats'])
                curve_obj['sapath_emergency'] = int(decoded['emergency'])
                curve_obj['sapath_highway']   = int(decoded['highway'])
                curve_obj['sapath_parking']   = int(decoded['parking'])
                curve_obj['sapath_spawn']     = decoded['spawn'] / 15.0
            else:
                _set_curve_defaults(curve_obj)
            if width_arr and chain[0] < len(width_arr):
                curve_obj['sapath_width'] = float(width_arr[chain[0]]) / 8.0
            _set_curve_wirecolor(curve_obj)
            col.objects.link(curve_obj)
            new_curves.append(curve_obj)

        # Tag the source mesh as "consumed" so a follow-up export knows
        # to read from curves instead. The mesh stays around for visual
        # reference — user can delete it manually.
        mesh_obj['path_curves_built'] = True

        self.report({'INFO'},
                    f"{len(new_curves)} {T('кривых построено')}")
        return {'FINISHED'}


# ── Operator: export curves to nodes.dat ──────────────────────────


def _merge_imported_extras(nf):
    """Pull NaviNodes + post-link tail from imported scene objects into
    ``nf`` so a Curve-only export still produces a complete file
    equivalent to the full export path.

    Background: ``build_nodes_file_from_curves`` only knows about path
    nodes and links — it has no curve representation for NaviNodes
    (those are sub-graph intersections, not lane-followable paths) nor
    for the post-link tail (naviLinks / linkLengths / pathIntersections).
    Without merging, exporting a vanilla region (which has 300+
    NaviNodes) silently drops them and breaks in-game vehicle traffic.

    Strategy: walk ``bpy.data.objects`` and pull:
      * ``path_type='nodes_navi'`` — NaviNode coordinates + per-vert
        parallel arrays (areas, ids, dx, dy, flags).
      * ``parsed_extras=True`` or ``extra_data_b64`` on any ``nodes_*``
        object — the post-link tail. Importer stores these on every
        created mesh, picking any one is fine.

    Returns a short summary (e.g. ``"369 navi, extras"``) for the UX
    report so the user sees what was preserved.
    """
    import base64
    from ..core.paths import NaviNode
    pulled = []

    def _at(arr, i, default=0):
        return int(arr[i]) if 0 <= i < len(arr) else default

    # 1. NaviNodes
    navi_obj = next(
        (o for o in bpy.data.objects
         if o.get('path_type') == 'nodes_navi' and o.type == 'MESH'),
        None,
    )
    if navi_obj is not None:
        mat_w = navi_obj.matrix_world
        navi_areas = list(navi_obj.get('navi_areas', []) or [])
        navi_ids   = list(navi_obj.get('navi_ids',   []) or [])
        navi_dx    = list(navi_obj.get('navi_dx',    []) or [])
        navi_dy    = list(navi_obj.get('navi_dy',    []) or [])
        navi_flags = list(navi_obj.get('navi_flags', []) or [])
        nf.navi_nodes = []
        for i, vert in enumerate(navi_obj.data.vertices):
            co = mat_w @ vert.co
            nf.navi_nodes.append(NaviNode(
                x=co.x, y=co.y,
                area_id=_at(navi_areas, i),
                node_id=_at(navi_ids,   i),
                dir_x  =_at(navi_dx,    i),
                dir_y  =_at(navi_dy,    i),
                flags  =_at(navi_flags, i),
            ))
        if nf.navi_nodes:
            pulled.append(f"{len(nf.navi_nodes)} navi")

    # 2. Post-link tail — first match wins (every imported obj carries
    #    an identical copy of the file-level metadata).
    for obj in bpy.data.objects:
        ptype = obj.get('path_type', '')
        if not ptype.startswith('nodes_') or ptype == 'nodes_viz':
            continue
        if obj.get('parsed_extras', False):
            nl = list(obj.get('navi_links',         []) or [])
            ll = list(obj.get('link_lengths',       []) or [])
            pi = list(obj.get('path_intersections', []) or [])
            if nl:
                nf.navi_links = [int(v) for v in nl]
            if ll:
                nf.link_lengths = [int(v) for v in ll]
            if pi:
                nf.path_intersections = [int(v) for v in pi]
            if nl or ll or pi:
                nf.parsed_extras = True
                pulled.append("extras")
            break
        b64 = obj.get('extra_data_b64', '')
        if b64:
            try:
                nf.extra_data = base64.b64decode(b64)
                nf.parsed_extras = False
                pulled.append("extra_data")
            except Exception as e:
                print(f"[INU] extra_data decode failed: {e}")
            break

    return ", ".join(pulled)


class GTATOOLS_OT_curves_to_nodes(bpy.types.Operator):
    """Block the legacy Curve writer before opening or changing files.

    Keep the operator ID for old layouts/scripts and saved scenes. All
    curves are blocked, including new curves and old converted curves
    whose original meshes have been deleted. Bounds checks cannot catch
    incorrect connections that still address existing nodes.
    """
    bl_idname = "gtatools.curves_to_nodes"
    bl_label = "INU: Curves → nodes*.dat"
    bl_description = T(_CURVES_EXPORT_BLOCKED)
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH',
                              description="Куда сохранить nodes*.dat")
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})
    fla4: BoolProperty(
        name=T("FLA4"),
        description=T("Записать в расширенном FLA4 формате (для Fastman92 limit adjuster)"),
        default=False,
    )
    path_set: bpy.props.EnumProperty(
        name=T("Path set"),
        description=T(
            "Размер регионной сетки. 64 = vanilla SA. Большие значения "
            "требуют Fastman92 limit adjuster (FLA4)"),
        items=[
            ('64',    "64 (Vanilla)",  ""),
            ('256',   "256",            ""),
            ('1024',  "1024",           ""),
            ('4096',  "4096",           ""),
            ('16384', "16384",          ""),
            ('65536', "65536",          ""),
        ],
        default='64',
    )
    entire_map: BoolProperty(
        name=T("Записать всю карту"),
        description=T(
            "Создать пустые nodes*.dat для всех регионов pathSet'а, "
            "не только для тех где есть Curve'ы. Vanilla SA требует "
            "наличия всех 64 файлов"),
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return any(o.type == 'CURVE' for o in context.selected_objects)

    def invoke(self, context, event):
        self.report({'ERROR'}, T(_CURVES_EXPORT_BLOCKED))
        return {'CANCELLED'}

    def execute(self, context):
        self.report({'ERROR'}, T(_CURVES_EXPORT_BLOCKED))
        return {'CANCELLED'}


# ── Selection helpers (ZZPuma DEBUGPATH_ROL: bt_selPeds/Vehs/allp) ─

def _select_curves_by_type(context, target_type):
    """target_type: 0 = all path curves, 1 = ped only, 2 = vehicle only."""
    n = 0
    for o in bpy.data.objects:
        if o.type != 'CURVE':
            continue
        if o.get('sapath_type') is None:
            continue
        try:
            o.select_set(False)
        except Exception:
            continue
        t = int(o.get('sapath_type', 1))
        if target_type == 0 or t == target_type:
            try:
                o.select_set(True)
                n += 1
            except Exception:
                pass
    return n


class GTATOOLS_OT_select_path_peds(bpy.types.Operator):
    """Выделить все Curve-пути типа Ped (sapath_type=1)"""
    bl_idname = "gtatools.select_path_peds"
    bl_label = "INU: Select Ped Paths"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = _select_curves_by_type(context, 1)
        self.report({'INFO'}, f"{n} {T('ped Curve выделено')}")
        return {'FINISHED'}


class GTATOOLS_OT_select_path_vehs(bpy.types.Operator):
    """Выделить все Curve-пути типа Vehicle (sapath_type=2)"""
    bl_idname = "gtatools.select_path_vehs"
    bl_label = "INU: Select Vehicle Paths"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = _select_curves_by_type(context, 2)
        self.report({'INFO'}, f"{n} {T('vehicle Curve выделено')}")
        return {'FINISHED'}


class GTATOOLS_OT_select_path_all(bpy.types.Operator):
    """Выделить все Curve-пути с sapath_* свойствами"""
    bl_idname = "gtatools.select_path_all"
    bl_label = "INU: Select All Path Curves"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = _select_curves_by_type(context, 0)
        self.report({'INFO'}, f"{n} {T('Curve выделено')}")
        return {'FINISHED'}


# ── Refresh wireframe colour (ZZPuma setShapeColors button) ───────

class GTATOOLS_OT_refresh_path_colors(bpy.types.Operator):
    """Перекрасить wireframe выделенных Curve-путей по их типу/флагам"""
    bl_idname = "gtatools.refresh_path_colors"
    bl_label = "INU: Refresh Path Colours"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = 0
        for o in context.selected_objects:
            if o.type == 'CURVE' and o.get('sapath_type') is not None:
                _set_curve_wirecolor(o)
                n += 1
        self.report({'INFO'}, f"{n} {T('Curve перекрашено')}")
        return {'FINISHED'}


# ── Pick / Apply path properties (ZZPuma get_settg / set_settg) ───
# Module-level clipboard holding the last "picked" sapath_* dict.
# Lives only for the current Blender session — re-pick after restart.
_PATH_PROPS_CLIPBOARD: dict = {}


class GTATOOLS_OT_pick_path_props(bpy.types.Operator):
    """Скопировать sapath_* свойства активной Curve во внутренний буфер"""
    bl_idname = "gtatools.pick_path_props"
    bl_label = "INU: Pick Path Props"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return o is not None and o.type == 'CURVE' and o.get('sapath_type') is not None

    def execute(self, context):
        global _PATH_PROPS_CLIPBOARD
        o = context.active_object
        _PATH_PROPS_CLIPBOARD = {
            k: o.get(k) for k in _SAPATH_PROPS if o.get(k) is not None
        }
        self.report(
            {'INFO'},
            f"{T('Скопировано props:')} {len(_PATH_PROPS_CLIPBOARD)}")
        return {'FINISHED'}


class GTATOOLS_OT_apply_path_props(bpy.types.Operator):
    """Применить ранее скопированные sapath_* к выделенным Curve"""
    bl_idname = "gtatools.apply_path_props"
    bl_label = "INU: Apply Path Props"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_PATH_PROPS_CLIPBOARD)

    def execute(self, context):
        if not _PATH_PROPS_CLIPBOARD:
            self.report({'ERROR'}, T("Буфер пуст — сначала Pick на исходной Curve"))
            return {'CANCELLED'}
        n = 0
        for o in context.selected_objects:
            if o.type != 'CURVE':
                continue
            for k, v in _PATH_PROPS_CLIPBOARD.items():
                o[k] = v
            _set_curve_wirecolor(o)
            n += 1
        self.report({'INFO'}, f"{T('Props применены к')} {n} Curve")
        return {'FINISHED'}


# ── Bulk-edit props on multi-selection (#7) ───────────────────────
# Multi-select edit is implemented as a popup operator that prompts
# the user for each sapath_* override and propagates to every selected
# Curve. Lighter weight than a full PropertyGroup mirror; the popup is
# only opened when the user asks for it.

class GTATOOLS_OT_bulk_set_path_props(bpy.types.Operator):
    """Bulk-set sapath_* свойств для всех выделенных Curve.

    Опции с -1 / 0 значением «не менять». Полезно для разом установить
    type=Vehicle + traffic=enabled + spawn=1.0 на массу путей после
    импорта или ручной правки."""
    bl_idname = "gtatools.bulk_set_path_props"
    bl_label = "INU: Bulk Set Path Props"
    bl_options = {'REGISTER', 'UNDO'}

    set_type: bpy.props.EnumProperty(
        name=T("Тип"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('1', T("Ped"), ""),
            ('2', T("Vehicle"), ""),
        ],
        default='NONE')
    set_traffic: bpy.props.EnumProperty(
        name=T("Traffic"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('1', T("Включён"), ""),
            ('2', T("Выключен"), ""),
        ],
        default='NONE')
    set_spawn: FloatProperty(
        name=T("Spawn rate"),
        description=T("Spawn probability 0.0-1.0. Введи -1 чтобы не менять"),
        default=-1.0, min=-1.0, max=1.0)
    set_width: FloatProperty(
        name=T("Width"),
        description=T("Path width. Введи -1 чтобы не менять"),
        default=-1.0, min=-1.0, soft_max=100.0)
    set_highway: bpy.props.EnumProperty(
        name=T("Highway"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('0', T("Нет"), ""),
            ('1', T("Да"), ""),
        ],
        default='NONE')
    set_boats: bpy.props.EnumProperty(
        name=T("Boats"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('0', T("Нет"), ""),
            ('1', T("Да"), ""),
        ],
        default='NONE')
    set_parking: bpy.props.EnumProperty(
        name=T("Parking"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('0', T("Нет"), ""),
            ('1', T("Да"), ""),
        ],
        default='NONE')

    @classmethod
    def poll(cls, context):
        return any(o.type == 'CURVE' for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, 'set_type')
        col.prop(self, 'set_traffic')
        col.prop(self, 'set_spawn')
        col.prop(self, 'set_width')
        col.prop(self, 'set_highway')
        col.prop(self, 'set_boats')
        col.prop(self, 'set_parking')

    def execute(self, context):
        n = 0
        for o in context.selected_objects:
            if o.type != 'CURVE':
                continue
            _set_curve_defaults(o)
            if self.set_type != 'NONE':
                o['sapath_type'] = int(self.set_type)
            if self.set_traffic != 'NONE':
                o['sapath_traffic'] = int(self.set_traffic)
            if self.set_spawn >= 0.0:
                o['sapath_spawn'] = float(self.set_spawn)
            if self.set_width >= 0.0:
                o['sapath_width'] = float(self.set_width)
            if self.set_highway != 'NONE':
                o['sapath_highway'] = int(self.set_highway)
            if self.set_boats != 'NONE':
                o['sapath_boats'] = int(self.set_boats)
            if self.set_parking != 'NONE':
                o['sapath_parking'] = int(self.set_parking)
            _set_curve_wirecolor(o)
            n += 1
        self.report({'INFO'}, f"{T('Bulk-set применён к')} {n} Curve")
        return {'FINISHED'}


# ── Path accessories (#6) ─────────────────────────────────────────
# TrafficLight / RoadBlock / Connector / SpecialNode are per-knot
# annotations on a path Curve. ZZPuma stores them as mesh-child
# objects parented to the spline with `knot` user-prop.
#
# We use the same pattern but with plain Empty objects instead of
# mesh blobs — easier to maintain, scales the same way, and the user
# can swap the display type if they want a custom icon. Each accessory
# carries:
#   inu_accessory_type  : 'TL' / 'RB' / 'CO' / 'SP'
#   inu_accessory_knot  : int — knot index on the parent Curve (0-based)
# For TrafficLight only:
#   inu_accessory_percent  : float 0..1 along the segment from knot N to N+1
#   inu_accessory_direction: int — TL orientation behaviour
#   inu_accessory_reversed : 0/1 — flip TL 180°

ACCESSORY_TYPES = {
    'TL': {'display': 'CUBE',   'size': 0.6, 'name': 'TrafficLight'},
    'RB': {'display': 'PLAIN_AXES', 'size': 0.8, 'name': 'RoadBlock'},
    'CO': {'display': 'CONE',   'size': 0.5, 'name': 'Connector'},
    'SP': {'display': 'SPHERE', 'size': 0.4, 'name': 'SpecialNode'},
}


def _create_path_accessory(curve_obj, knot_index: int, accessory_type: str):
    """Spawn an Empty parented to *curve_obj* at the given knot. Type
    drives the Empty display style + IDProp tag. Returns the new object."""
    if accessory_type not in ACCESSORY_TYPES:
        raise ValueError(f"Unknown accessory type {accessory_type!r}")
    cfg = ACCESSORY_TYPES[accessory_type]

    name = f"{curve_obj.name}_{cfg['name']}"
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = cfg['display']
    empty.empty_display_size = cfg['size']
    empty['inu_accessory_type'] = accessory_type
    empty['inu_accessory_knot'] = int(knot_index)
    if accessory_type == 'TL':
        empty['inu_accessory_percent'] = 0.5
        empty['inu_accessory_direction'] = 1
        empty['inu_accessory_reversed'] = 0
    empty.parent = curve_obj

    # Place at the curve's knot world position. For Curves we read
    # spline 0's point N; for closed/multi-spline curves the user can
    # change `inu_accessory_knot` and the update tick will re-place it.
    try:
        spl = curve_obj.data.splines[0]
        pts = (spl.bezier_points if spl.type == 'BEZIER' else spl.points)
        if 0 <= knot_index < len(pts):
            local = pts[knot_index].co
            world = curve_obj.matrix_world @ (
                local.xyz if hasattr(local, 'xyz') else local)
            empty.matrix_world.translation = world
    except Exception:
        pass

    # Same collection as the parent.
    for col in curve_obj.users_collection:
        col.objects.link(empty)
    return empty


class GTATOOLS_OT_add_path_accessory(bpy.types.Operator):
    """Добавить TrafficLight / RoadBlock / Connector / SpecialNode на
    активный knot выделенной Curve."""
    bl_idname = "gtatools.add_path_accessory"
    bl_label = "INU: Add Path Accessory"
    bl_options = {'REGISTER', 'UNDO'}

    accessory_type: bpy.props.EnumProperty(
        name=T("Тип"),
        items=[
            ('TL', T("TrafficLight"), T("Светофор: spawn'ится на сегменте между knot и knot+1")),
            ('RB', T("RoadBlock"),    T("Дорожный блок копов на самом knot")),
            ('CO', T("Connector"),    T("Connector нода (для inter-region путей FLA4)")),
            ('SP', T("SpecialNode"),  T("Универсальный маркер для special-логики")),
        ],
        default='TL',
    )
    knot_index: bpy.props.IntProperty(
        name=T("Knot index"),
        description=T("Индекс knot'а на родительской Curve (0-based)"),
        default=0, min=0,
    )

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return o is not None and o.type == 'CURVE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def execute(self, context):
        curve_obj = context.active_object
        try:
            empty = _create_path_accessory(
                curve_obj, self.knot_index, self.accessory_type)
        except Exception as ex:
            self.report({'ERROR'}, f"Accessory: {ex}")
            return {'CANCELLED'}
        # Flag the parent Curve with corresponding sapath_* hint so the
        # export knows the node at this knot needs the matching bit set.
        if self.accessory_type == 'RB':
            curve_obj['sapath_roadblock'] = 1
            _set_curve_wirecolor(curve_obj)
        empty.select_set(True)
        context.view_layer.objects.active = empty
        self.report({'INFO'},
                    f"{T('Создан')} {ACCESSORY_TYPES[self.accessory_type]['name']}"
                    f" @ knot {self.knot_index}")
        return {'FINISHED'}


class GTATOOLS_OT_remove_path_accessory(bpy.types.Operator):
    """Удалить выделенные path accessory объекты"""
    bl_idname = "gtatools.remove_path_accessory"
    bl_label = "INU: Remove Path Accessory"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.get('inu_accessory_type') is not None
                   for o in context.selected_objects)

    def execute(self, context):
        n = 0
        for o in list(context.selected_objects):
            if o.get('inu_accessory_type') is not None:
                bpy.data.objects.remove(o, do_unlink=True)
                n += 1
        self.report({'INFO'}, f"{T('Удалено accessory:')} {n}")
        return {'FINISHED'}


# ── #8 Auto-tick service ──────────────────────────────────────────
# Keep accessory positions in sync with their parent Curve when the
# user drags knots. ZZPuma runs this every 30 frames via MaxScript
# upTick; we use bpy.app.timers (lightweight, native Blender API).

def _accessory_sync_tick():
    """Re-place every accessory on its parent Curve knot. Called every
    ~0.5s while there are accessories in the scene; auto-stops when
    none are left to save CPU."""
    if bpy is None or not hasattr(bpy, 'data'):
        return None
    accessories = [o for o in bpy.data.objects
                   if o.get('inu_accessory_type') is not None]
    if not accessories:
        # Unregister — nothing to sync. Will re-register on next add.
        return None

    for empty in accessories:
        parent = empty.parent
        if parent is None or parent.type != 'CURVE':
            continue
        kn = int(empty.get('inu_accessory_knot', 0))
        atype = empty.get('inu_accessory_type', '')
        try:
            spl = parent.data.splines[0]
        except IndexError:
            continue
        pts = spl.bezier_points if spl.type == 'BEZIER' else spl.points
        if not pts or kn < 0 or kn >= len(pts):
            continue
        p1 = pts[kn].co
        p1 = p1.xyz if hasattr(p1, 'xyz') else p1
        if atype == 'TL' and kn + 1 < len(pts):
            # TrafficLight floats along the segment based on `percent`.
            p2 = pts[kn + 1].co
            p2 = p2.xyz if hasattr(p2, 'xyz') else p2
            perc = float(empty.get('inu_accessory_percent', 0.5))
            local = p1 + perc * (p2 - p1)
        else:
            local = p1
        try:
            empty.matrix_world.translation = parent.matrix_world @ local
        except Exception:
            pass

    return 0.5  # next tick in 0.5 s


def _start_accessory_sync_timer():
    try:
        if not bpy.app.timers.is_registered(_accessory_sync_tick):
            bpy.app.timers.register(_accessory_sync_tick)
    except Exception:
        pass


class GTATOOLS_OT_start_accessory_sync(bpy.types.Operator):
    """Включить фоновую синхронизацию позиций path accessory'ев
    с их родительскими Curve'ами"""
    bl_idname = "gtatools.start_accessory_sync"
    bl_label = "INU: Start Accessory Sync"
    bl_options = {'REGISTER'}

    def execute(self, context):
        _start_accessory_sync_timer()
        self.report({'INFO'}, T("Auto-sync включён"))
        return {'FINISHED'}


# ── #9 Debug overlay (NodeID / LinkID / NaviID in viewport) ───────
# Uses gpu+blf draw handler on SpaceView3D — same technique as our
# floater framework. Only renders when toggled on; off by default
# so heavy maps don't lag.

_DEBUG_OVERLAY_STATE = {'handler': None, 'show_node_info': False,
                        'show_navi': False}


def _draw_path_debug_overlay():
    try:
        import bpy as _bpy
        import blf
        # Get the 3D viewport region — required to project world→screen.
        ctx = _bpy.context
        region = ctx.region
        rv3d = ctx.region_data
        if region is None or rv3d is None:
            return
    except Exception:
        return

    try:
        from bpy_extras import view3d_utils
    except Exception:
        return

    font_id = 0
    blf.size(font_id, 11)
    blf.color(font_id, 1.0, 1.0, 0.0, 1.0)

    shown = 0
    SHOW_LIMIT = 80  # cap labels to avoid 1000-text spam on full map

    if _DEBUG_OVERLAY_STATE.get('show_node_info'):
        for obj in _bpy.data.objects:
            if shown >= SHOW_LIMIT:
                break
            pt = obj.get('path_type', '')
            if not pt.startswith('nodes_') or obj.hide_get():
                continue
            mw = obj.matrix_world
            node_ids = obj.get('node_ids', [])
            node_areas = obj.get('node_areas', [])
            for i, v in enumerate(obj.data.vertices):
                if shown >= SHOW_LIMIT:
                    break
                world = mw @ v.co
                co_2d = view3d_utils.location_3d_to_region_2d(
                    region, rv3d, world)
                if co_2d is None:
                    continue
                nid = int(node_ids[i]) if i < len(node_ids) else i
                aid = int(node_areas[i]) if i < len(node_areas) else -1
                blf.position(font_id, co_2d.x + 4, co_2d.y + 4, 0)
                blf.draw(font_id, f"#{nid}@{aid}")
                shown += 1

    if _DEBUG_OVERLAY_STATE.get('show_navi'):
        blf.color(font_id, 1.0, 0.6, 0.0, 1.0)
        for obj in _bpy.data.objects:
            if shown >= SHOW_LIMIT:
                break
            if obj.get('path_type') != 'nodes_navi' or obj.hide_get():
                continue
            mw = obj.matrix_world
            navi_ids = obj.get('navi_ids', [])
            for i, v in enumerate(obj.data.vertices):
                if shown >= SHOW_LIMIT:
                    break
                world = mw @ v.co
                co_2d = view3d_utils.location_3d_to_region_2d(
                    region, rv3d, world)
                if co_2d is None:
                    continue
                nid = int(navi_ids[i]) if i < len(navi_ids) else i
                blf.position(font_id, co_2d.x + 4, co_2d.y + 4, 0)
                blf.draw(font_id, f"N{nid}")
                shown += 1


class GTATOOLS_OT_toggle_path_debug(bpy.types.Operator):
    """Включить/выключить debug overlay для путей (NodeID/AreaID на нодах)"""
    bl_idname = "gtatools.toggle_path_debug"
    bl_label = "INU: Toggle Path Debug Overlay"
    bl_options = {'REGISTER'}

    target: bpy.props.EnumProperty(
        name=T("Что показать"),
        items=[
            ('NODES', T("Node IDs"), ""),
            ('NAVI',  T("Navi IDs"), ""),
            ('OFF',   T("Выключить всё"), ""),
        ],
        default='NODES',
    )

    def execute(self, context):
        global _DEBUG_OVERLAY_STATE
        if self.target == 'NODES':
            _DEBUG_OVERLAY_STATE['show_node_info'] = not _DEBUG_OVERLAY_STATE['show_node_info']
        elif self.target == 'NAVI':
            _DEBUG_OVERLAY_STATE['show_navi'] = not _DEBUG_OVERLAY_STATE['show_navi']
        else:  # OFF
            _DEBUG_OVERLAY_STATE['show_node_info'] = False
            _DEBUG_OVERLAY_STATE['show_navi'] = False

        any_on = (_DEBUG_OVERLAY_STATE['show_node_info']
                  or _DEBUG_OVERLAY_STATE['show_navi'])

        if any_on and _DEBUG_OVERLAY_STATE['handler'] is None:
            _DEBUG_OVERLAY_STATE['handler'] = bpy.types.SpaceView3D.draw_handler_add(
                _draw_path_debug_overlay, (), 'WINDOW', 'POST_PIXEL')
        elif not any_on and _DEBUG_OVERLAY_STATE['handler'] is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(
                    _DEBUG_OVERLAY_STATE['handler'], 'WINDOW')
            except Exception:
                pass
            _DEBUG_OVERLAY_STATE['handler'] = None

        # Force redraw so the change is visible immediately.
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        return {'FINISHED'}

