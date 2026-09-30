# INU_tools.ops.path_export — Export Blender objects to GTA SA path files

import ast
import bpy
from ..core.paths import (
    FlightFile, FlightPath, FlightPoint, write_flight,
    TrackFile, TrackNode, write_track,
    NodesFile, PathNode, NaviNode, PathLink, write_nodes,
    PathIPLFile, PathIPLGroup, PathIPLNode, write_paths_ipl,
    PATH_FLAG_ROADBLOCK, PATH_FLAG_TRAFFIC_MASK,
)


def export_flight(filepath: str, objects=None):
    """Export curve objects as flight.dat."""
    if objects is None:
        objects = [o for o in bpy.context.selected_objects
                   if o.type == 'CURVE' and o.get('path_type') == 'flight']

    data = FlightFile()

    for obj in sorted(objects, key=lambda o: o.get('path_index', 0)):
        curve = obj.data
        mat_w = obj.matrix_world

        for spline in curve.splines:
            path = FlightPath()
            for point in spline.points:
                co = mat_w @ point.co.to_3d()
                path.points.append(FlightPoint(x=co.x, y=co.y, z=co.z))
            if path.points:
                data.paths.append(path)

    return write_flight(filepath, data)


def export_track(filepath: str, obj=None):
    """Export a curve object as tracks*.dat."""
    if obj is None:
        for o in bpy.context.selected_objects:
            if o.type == 'CURVE' and o.get('path_type') == 'track':
                obj = o
                break

    if not obj or obj.type != 'CURVE':
        return 0

    track = TrackFile()
    mat_w = obj.matrix_world

    # Restore station flags
    station_indices = set()
    raw = obj.get('station_indices', '[]')
    try:
        station_indices = set(ast.literal_eval(raw))
    except Exception:
        pass

    idx = 0
    for spline in obj.data.splines:
        for point in spline.points:
            co = mat_w @ point.co.to_3d()
            flag = 1 if idx in station_indices else 0
            track.nodes.append(TrackNode(x=co.x, y=co.y, z=co.z, flag=flag))
            idx += 1

    return write_track(filepath, track)


def export_nodes(filepath: str, objects=None, *, fla4: bool = False,
                 emit_roadblox: bool = True, emit_connectors: bool = True):
    """Export mesh objects as nodes*.dat. Set ``fla4=True`` to emit the
    extended Fastman Limit Adjuster 4 format.

    Round-trip preservation: reads `obj['extra_data_b64']` (set on
    import) and threads it back into `nodes_file.extra_data` so the
    post-link section (naviLinks, linkLengths, pathIntersections) is
    written out unchanged. Without this, exported files would be
    missing those tail bytes and the game would crash / paths would
    not work.

    Also auto-upgrades to FLA4 format if any source object carries the
    `fla4` flag from import — explicit `fla4=True` caller still wins
    (it's a fresh choice, not metadata).

    ``emit_roadblox`` — when True (default) writes ROADBLOX.DAT next
    to the nodes file with every node that has the roadblock flag bit
    set. The game uses it to spawn cop barriers during chases. Vanilla
    SA expects this file to exist (padded to 325 entries / 1304 bytes).

    ``emit_connectors`` — when True (default) writes connectors.txt
    listing every node tagged with the `connector` IDProperty. Used by
    FLA mods to bridge regions; harmless to write even without FLA.
    """
    import base64
    if objects is None:
        objects = [o for o in bpy.context.selected_objects
                   if o.type == 'MESH' and o.get('path_type', '').startswith('nodes_')
                   and o.get('path_type') != 'nodes_viz']

    nodes_file = NodesFile()
    nodes_file.fla4 = fla4

    # Reconstruct post-link tail from the first object that has it.
    # Every object from the same file carries an identical copy of
    # the file-level metadata, so picking any one is fine.
    #
    # Two paths depending on what the importer stored:
    #   * `parsed_extras=True` — naviLinks / linkLengths / pathIntersections
    #     are stored as per-index props (`navi_link_{i}`, etc). Read them
    #     back into lists. Editable round-trip.
    #   * `extra_data_b64` — raw bytes fallback. Decode to `extra_data`.
    def _arr(obj, name):
        """Read an array IDProperty as a plain Python list. Returns []
        if missing. Importer now stores per-node/link arrays in bulk."""
        v = obj.get(name)
        return list(v) if v is not None else []

    def _at(arr, i, default=0):
        return int(arr[i]) if 0 <= i < len(arr) else default

    for obj in objects:
        if obj.get('parsed_extras', False):
            nodes_file.navi_links         = [int(v) for v in _arr(obj, 'navi_links')]
            nodes_file.link_lengths       = [int(v) for v in _arr(obj, 'link_lengths')]
            nodes_file.path_intersections = [int(v) for v in _arr(obj, 'path_intersections')]
            nodes_file.parsed_extras = True
            break
        b64 = obj.get('extra_data_b64', '')
        if b64:
            try:
                nodes_file.extra_data = base64.b64decode(b64)
            except Exception as e:
                print(f"[INU] nodes extra_data decode failed: {e}")
            break

    # Auto-upgrade FLA4 if any object came from an FLA4 file. Explicit
    # caller `fla4=True` already on; only flip from False → True here.
    if not nodes_file.fla4:
        for obj in objects:
            if obj.get('fla4', False):
                nodes_file.fla4 = True
                break

    for obj in objects:
        path_type = obj.get('path_type', '')
        mat_w = obj.matrix_world
        mesh = obj.data

        # Bulk-read parallel arrays once per object — much faster than
        # `obj.get(f'node_{i}_link')` × num_nodes which was O(n²)
        # against the IDProperty dict.
        node_links  = _arr(obj, 'node_links')
        node_areas  = _arr(obj, 'node_areas')
        node_ids    = _arr(obj, 'node_ids')
        node_widths = _arr(obj, 'node_widths')
        node_types  = _arr(obj, 'node_types')
        node_flags  = _arr(obj, 'node_flags')

        for i, vert in enumerate(mesh.vertices):
            co = mat_w @ vert.co
            node = PathNode(
                x=co.x, y=co.y, z=co.z,
                link_id   = _at(node_links,  i),
                area_id   = _at(node_areas,  i),
                node_id   = _at(node_ids,    i, i),
                path_width= _at(node_widths, i),
                node_type = _at(node_types,  i),
                flags     = _at(node_flags,  i),
                # FLA4 extension fields — currently unused, default 0
                spawn_probability=0,
                speed_limit_kmh=0,
                lane_count_override=0,
            )

            if path_type == 'nodes_vehicle':
                nodes_file.vehicle_nodes.append(node)
            elif path_type == 'nodes_ped':
                nodes_file.ped_nodes.append(node)

        if path_type == 'nodes_navi':
            navi_areas = _arr(obj, 'navi_areas')
            navi_ids   = _arr(obj, 'navi_ids')
            navi_dx    = _arr(obj, 'navi_dx')
            navi_dy    = _arr(obj, 'navi_dy')
            navi_flags = _arr(obj, 'navi_flags')
            for i, vert in enumerate(mesh.vertices):
                co = mat_w @ vert.co
                nodes_file.navi_nodes.append(NaviNode(
                    x=co.x, y=co.y,
                    area_id = _at(navi_areas, i),
                    node_id = _at(navi_ids,   i),
                    dir_x   = _at(navi_dx,    i),
                    dir_y   = _at(navi_dy,    i),
                    flags   = _at(navi_flags, i),
                ))

    # Restore links from bulk arrays — ONCE, not per-object.
    # The importer mirrors `link_areas`/`link_nodes`/`num_links` to every
    # created object (vehicle / ped / navi) so any of them can re-emit
    # the post-link tail; doing the loop per-object here previously
    # duplicated the entire Links section 3× and produced corrupt files
    # (num_links=75249 on round-trip of a 25083-link source).
    for obj in objects:
        num_links = int(obj.get('num_links', 0))
        if num_links <= 0:
            continue
        link_areas = _arr(obj, 'link_areas')
        link_nodes = _arr(obj, 'link_nodes')
        for i in range(num_links):
            nodes_file.links.append(PathLink(
                area_id=_at(link_areas, i),
                node_id=_at(link_nodes, i),
            ))
        break  # one object is enough — they all carry the same data

    n_written = write_nodes(filepath, nodes_file)

    # Sibling files written next to the .dat — only if there's data
    # worth writing OR the file would already be expected by the game
    # (ROADBLOX.DAT must exist even when empty per vanilla SA layout).
    import os
    folder = os.path.dirname(filepath) or '.'

    if emit_roadblox:
        try:
            from ..core.paths import write_roadblox
            rb_path = os.path.join(folder, 'ROADBLOX.DAT')
            write_roadblox(rb_path, [nodes_file])
        except Exception as e:
            print(f"[INU] ROADBLOX.DAT emit failed: {e}")

    if emit_connectors:
        # Collect connector-flagged nodes from source objects' IDProps.
        # We store the flag as a per-vertex IDProp on import — if user
        # tagged extra nodes via the Curve workflow's `sapath_connector`
        # those get caught here too.
        connectors_list = []
        seen = set()
        for obj in objects:
            conn_arr = _arr(obj, 'node_connectors')
            for i, node in enumerate(nodes_file.vehicle_nodes
                                     + nodes_file.ped_nodes):
                if i < len(conn_arr) and int(conn_arr[i]) != 0:
                    key = (node.area_id, node.node_id)
                    if key not in seen:
                        connectors_list.append(key)
                        seen.add(key)
        if connectors_list:
            try:
                from ..core.paths import write_connectors
                conn_path = os.path.join(folder, 'connectors.txt')
                write_connectors(conn_path, connectors_list)
            except Exception as e:
                print(f"[INU] connectors.txt emit failed: {e}")

    return n_written


def _path_ipl_real_to_full(obj):
    """Curve point index → pn_<slot>_* slot (same mapping as the
    path_node_flag operator): the curve holds only nodes with
    node_type > 0, import stores pn_<slot>_* for every slot incl. padding."""
    pn_count = int(obj.get('pn_count', 0) or 0)
    return [j for j in range(pn_count)
            if int(obj.get(f'pn_{j}_type', 0) or 0) > 0]


def _path_ipl_node_props(obj, slot, defaults):
    """PathIPLNode fields of one node from pn_<slot>_*; slot None → defaults."""
    if slot is None:
        return defaults
    p = f'pn_{slot}_'
    return dict(
        area_id=obj.get(p + 'area', defaults['area_id']),
        unknown=obj.get(p + 'unk', defaults['unknown']),
        width=obj.get(p + 'width', defaults['width']),
        left_lanes=obj.get(p + 'll', defaults['left_lanes']),
        right_lanes=obj.get(p + 'rl', defaults['right_lanes']),
        median_width=obj.get(p + 'mw', defaults['median_width']),
        flags=obj.get(p + 'flags', defaults['flags']),
        spawn_rate=obj.get(p + 'spawn', defaults['spawn_rate']),
    )


def export_paths_ipl(filepath: str, objects=None):
    """Export curve objects as paths.ipl.

    Auto-splits long curves into groups of 12 nodes.
    Links between groups are set automatically.
    """
    if objects is None:
        objects = [o for o in bpy.context.selected_objects
                   if o.type == 'CURVE' and o.get('path_type') == 'path_ipl']

    data = PathIPLFile()

    for obj in sorted(objects, key=lambda o: o.get('group_index', 0)):
        group_type = obj.get('group_type', 1)
        mat_w = obj.matrix_world

        # Collect all curve points
        all_points = []
        for spline in obj.data.splines:
            for point in spline.points:
                co = mat_w @ point.co.to_3d()
                all_points.append(co)

        if not all_points:
            continue

        # Get default node properties from object
        def_width = obj.get('pn_0_width', 1)
        def_ll = obj.get('pn_0_ll', 1)
        def_rl = obj.get('pn_0_rl', 1)
        def_mw = obj.get('pn_0_mw', 0)
        def_flags = obj.get('pn_0_flags', 1)
        def_spawn = obj.get('pn_0_spawn', 0)

        # Roadblock / traffic light are per-point toggles (path_node_flag):
        # points past the slots and synthesized link nodes don't inherit
        # them from node 0.
        fill_flags = int(def_flags) & ~(PATH_FLAG_ROADBLOCK
                                        | PATH_FLAG_TRAFFIC_MASK)

        # Each point keeps its own imported node (pn_<slot>_*); points past
        # the imported slots (added later) get node 0's values minus those
        # toggles.
        defaults = dict(area_id=0, unknown=0.0, width=def_width,
                        left_lanes=def_ll, right_lanes=def_rl,
                        median_width=def_mw, flags=fill_flags,
                        spawn_rate=def_spawn)
        real_to_full = _path_ipl_real_to_full(obj)
        all_nodes = [
            (co, _path_ipl_node_props(
                obj, real_to_full[k] if k < len(real_to_full) else None,
                defaults))
            for k, co in enumerate(all_points)]

        # Max internal nodes per group = 10 (slot 0-9 internal, 10-11 for external links)
        MAX_INTERNAL = 10
        chunks = []
        for i in range(0, len(all_nodes), MAX_INTERNAL):
            chunks.append(all_nodes[i:i + MAX_INTERNAL])

        for ci, chunk in enumerate(chunks):
            group = PathIPLGroup(group_type=group_type, external_index=-1)

            # Internal nodes (type=2)
            for pi, (co, props) in enumerate(chunk):
                next_link = pi + 1 if pi < len(chunk) - 1 else -1
                node = PathIPLNode(
                    node_type=2,
                    link_id=next_link,
                    x=co.x, y=co.y, z=co.z,
                    **props,
                )
                group.nodes.append(node)

            # External link to next group (type=1)
            if ci < len(chunks) - 1:
                next_co = chunks[ci + 1][0][0]
                group.nodes.append(PathIPLNode(
                    node_type=1, link_id=0, area_id=0,
                    x=next_co.x, y=next_co.y, z=next_co.z,
                    width=def_width, left_lanes=def_ll, right_lanes=def_rl,
                    flags=fill_flags,
                ))

            # External link to previous group (type=1)
            if ci > 0:
                prev_co = chunks[ci - 1][-1][0]
                group.nodes.append(PathIPLNode(
                    node_type=1, link_id=len(chunk) - 1, area_id=0,
                    x=prev_co.x, y=prev_co.y, z=prev_co.z,
                    width=def_width, left_lanes=def_ll, right_lanes=def_rl,
                    flags=fill_flags,
                ))

            data.groups.append(group)

    return write_paths_ipl(filepath, data)
