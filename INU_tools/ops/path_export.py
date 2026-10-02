# INU_tools.ops.path_export — Export Blender objects to GTA SA path files

import ast
import bpy
from ..core.paths import (
    FlightFile, FlightPath, FlightPoint, write_flight,
    TrackFile, TrackNode, write_track,
    NodesFile, PathNode, NaviNode, PathLink, write_nodes,
    PathIPLFile, PathIPLGroup, PathIPLNode, write_paths_ipl, parse_paths_ipl,
)
from .path_ipl_props import ensure_point_slots, slot_values


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
                 emit_roadblox: bool = True, emit_connectors: bool = True,
                 bare_nodes=None, collect_only: bool = False,
                 prepared_nodes=None):
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
    from .path_nodes_mesh import collect_compiled_nodes, complete_node_objects
    if objects is None:
        objects = complete_node_objects(bpy.context.selected_objects,
                                        bpy.context.scene.objects)
    objects = list(objects)
    nodes_file = (prepared_nodes if prepared_nodes is not None else
                  collect_compiled_nodes(objects, fla4=fla4))

    def _arr(obj, name):
        return list(obj.get(name, []))

    if bare_nodes is not None:
        from ..core.paths import merge_bare_nodes
        merge_bare_nodes(nodes_file, bare_nodes)
    if collect_only:
        return nodes_file
    if prepared_nodes is None and getattr(nodes_file, 'node_remap', {}):
        raise ValueError('Node IDs changed: export all 64 regions with Export Path Nodes')
    if getattr(nodes_file, 'topology_changed', False):
        from ..core.paths_graph import validate_graph_batch
        area = next(iter({n.area_id for n in nodes_file.vehicle_nodes + nodes_file.ped_nodes}), None)
        validate_graph_batch({area: nodes_file})
    if getattr(nodes_file, 'topology_changed', False):
        # Serialize the complete binary before replacing this destination.
        # The batch operator has already validated all region binaries.
        import os
        import tempfile
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(os.path.abspath(filepath)),
                                         prefix='.inu_nodes_', delete=False) as stream:
            temporary = stream.name
        try:
            n_written = write_nodes(temporary, nodes_file)
            os.replace(temporary, filepath)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    else:
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


def _path_ipl_node_props(obj, slot):
    values = slot_values(obj, slot)
    return dict(crossing=int(values['cross']), width=float(values['width']),
                left_lanes=int(values['ll']), right_lanes=int(values['rl']),
                speed_limit=int(values['speed']), flags=int(values['flags']),
                spawn_rate=float(values['spawn']),
                extra_columns=tuple(v.strip() for v in
                                    obj.get(f'pn_{slot}_extra', '').split(',') if v.strip()))


def export_paths_ipl(filepath: str, objects=None):
    """Export curve objects as paths.ipl.

    Auto-splits long curves into groups of 12 nodes.
    Links between groups are set automatically.
    """
    if objects is None:
        objects = [o for o in bpy.context.selected_objects
                   if o.type == 'CURVE' and o.get('path_type') == 'path_ipl']

    games = {obj.get('pn_game', 'VC') for obj in objects}
    if len(games) > 1:
        raise ValueError('Cannot export mixed III/VC path formats to one file')
    data = PathIPLFile(game=next(iter(games), 'VC'))

    for obj in sorted(objects, key=lambda o: o.get('group_index', 0)):
        group_type = obj.get('group_type', 1)
        mat_w = obj.matrix_world

        pairs = ensure_point_slots(obj)
        all_points = [mat_w @ (point.co.to_3d() if hasattr(point.co, 'to_3d')
                              else point.co) for point, _ in pairs]
        if obj.get('pn_legacy_import_scale'):
            all_points = [co / 16.0 for co in all_points]

        if not all_points:
            continue

        all_nodes = [(co, _path_ipl_node_props(obj, slot))
                     for co, (_, slot) in zip(all_points, pairs)]

        # Keep the imported link graph, external nodes and padding when
        # topology is unchanged. The previous exporter rebuilt every
        # vanilla graph into a chain even for an untouched curve.
        raw = obj.get('pn_original_group', '')
        imported_slots = list(obj.get('pn_import_slots', []))
        if raw and imported_slots == [slot for _, slot in pairs]:
            original = parse_paths_ipl(('path\n' + raw + 'end\n').encode('utf-8'),
                                       game=data.game)
            group = original.groups[0]
            group.group_type = group_type
            group.external_index = int(obj.get('external_index', -1))
            group.model_name = obj.get('pn_model_name', '')
            imported_positions = list(obj.get('pn_import_positions', []))
            for index, (co, props) in enumerate(all_nodes):
                node = group.nodes[imported_slots[index]]
                base = imported_positions[index * 3:index * 3 + 3]
                if len(base) == 3:
                    for key, value, before in zip(('x', 'y', 'z'), (co.x, co.y, co.z), base):
                        delta = value - before
                        if abs(delta) > 1e-7:
                            setattr(node, key, getattr(node, key) + delta)
                for key, value in props.items():
                    setattr(node, key, value)
                values = slot_values(obj, imported_slots[index])
                node.node_type = int(values['type'])
                node.link_id = int(values['link'])
            data.groups.append(group)
            data._prefix = data._prefix or obj.get('pn_source_prefix', '')
            data._suffix = obj.get('pn_source_suffix', 'end\n')
            continue

        if data.game == 'III':
            raise ValueError('III paths belong to an IDE model and cannot be generated as detached IPL groups')

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
                    node_type=1, link_id=0,
                    x=next_co.x, y=next_co.y, z=next_co.z,
                ))

            # External link to previous group (type=1)
            if ci > 0:
                prev_co = chunks[ci - 1][-1][0]
                group.nodes.append(PathIPLNode(
                    node_type=1, link_id=len(chunk) - 1,
                    x=prev_co.x, y=prev_co.y, z=prev_co.z,
                ))

            data.groups.append(group)

    return write_paths_ipl(filepath, data)
