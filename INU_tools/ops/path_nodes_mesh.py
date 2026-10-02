"""Stable mesh identities and compiled NODES collection (no bpy import)."""

import base64
from dataclasses import replace

from ..core.paths import NodesFile, PathNode, NaviNode, PathLink, get_area_id
from ..core.paths_graph import graph_edges, rebuild_graph

_ATTRIBUTE = 'inu_node_identity'
_MULTIPLIER = 104729
_MASK = (1 << 31) - 1


def _token(slot):
    # A bijective, nonlinear permutation of 31-bit values. Interpolated
    # subdivision attributes should not look like consecutive old IDs.
    value = ((slot + 1) * _MULTIPLIER) & _MASK
    value ^= value >> 11
    value = (value * 0x45D9F3B) & _MASK
    return value ^ (value >> 16)


def _layer(mesh, create=False):
    attributes = getattr(mesh, 'attributes', None)
    if attributes is not None:
        layer = attributes.get(_ATTRIBUTE)
        if layer is None and create:
            layer = attributes.new(_ATTRIBUTE, 'INT', 'POINT')
        if layer is not None and (layer.data_type != 'INT' or layer.domain != 'POINT'):
            raise ValueError('Compiled NODES identity attribute must be INT / POINT')
        return layer
    # Blender 2.83-2.92 expose the same custom mesh data through this API.
    layers = getattr(mesh, 'vertex_layers_int', None)
    if layers is None:
        raise ValueError('Mesh does not support persistent NODES identities')
    layer = layers.get(_ATTRIBUTE)
    return layers.new(name=_ATTRIBUTE) if layer is None and create else layer


def _identity_values(mesh):
    # update_from_editmode flushes geometry but Mesh Attribute.data is
    # deliberately unavailable in Edit Mode. Read the live BMesh layer.
    if getattr(mesh, 'is_editmode', False):
        import bmesh
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.index_update()
        layer = bm.verts.layers.int.get(_ATTRIBUTE)
        return [vertex[layer] for vertex in bm.verts] if layer is not None else None
    layer = _layer(mesh)
    return [value.value for value in layer.data] if layer is not None else None


def initialize_node_identity(obj, nodes):
    values = [_token(i) for i in range(len(nodes))]
    if getattr(obj.data, 'is_editmode', False):
        import bmesh
        bm = bmesh.from_edit_mesh(obj.data)
        if len(bm.verts) != len(values):
            raise ValueError('Reimport NODES before editing topology in an older scene')
        layer = bm.verts.layers.int.get(_ATTRIBUTE) or bm.verts.layers.int.new(_ATTRIBUTE)
        for vertex, value in zip(bm.verts, values):
            vertex[layer] = value
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    else:
        layer = _layer(obj.data, create=True)
        layer.data.foreach_set('value', values)
    obj['node_positions'] = [v for n in nodes for v in (n.x, n.y, n.z)]
    obj['nodes_identity_version'] = 1
    for key in ('spawn_probability', 'speed_limit_kmh', 'lane_count_override'):
        obj['node_' + key] = [getattr(n, key) for n in nodes]


def complete_node_objects(selected, scene_objects):
    """Selecting a region's vehicle mesh also includes its ped/nav meshes."""
    objects = [o for o in selected if o.type == 'MESH' and
               o.get('path_type') in ('nodes_vehicle', 'nodes_ped', 'nodes_navi')]
    sources = {(o.get('nodes_filename', '').casefold(), o.get('nodes_source_key', ''))
               for o in objects if o.get('nodes_filename')}
    for obj in scene_objects:
        if (obj.type == 'MESH' and obj.get('path_type') in
                ('nodes_vehicle', 'nodes_ped', 'nodes_navi') and
                (obj.get('nodes_filename', '').casefold(), obj.get('nodes_source_key', '')) in sources and
                not any(obj is existing for existing in objects)):
            objects.append(obj)
    return objects


def _arr(obj, key):
    return list(obj.get(key, []))


def _at(obj, key, i, default=0):
    arr = obj.get(key, ())
    return int(arr[i]) if i < len(arr) else default


def _original_nodes(obj):
    count = int(obj.get('node_count', len(obj.data.vertices)))
    positions = _arr(obj, 'node_positions')
    if len(positions) != count * 3:
        if len(obj.data.vertices) != count:
            raise ValueError('Reimport NODES before editing topology in an older scene')
        positions = [v for point in obj.data.vertices for v in
                     (point.co.x, point.co.y, point.co.z)]
    result = []
    for i in range(count):
        result.append(PathNode(
            x=positions[i * 3], y=positions[i * 3 + 1], z=positions[i * 3 + 2],
            link_id=_at(obj, 'node_links', i), area_id=_at(obj, 'node_areas', i),
            node_id=_at(obj, 'node_ids', i, i), path_width=_at(obj, 'node_widths', i),
            node_type=_at(obj, 'node_types', i), flags=_at(obj, 'node_flags', i),
            is_vehicle=obj.get('path_type') == 'nodes_vehicle',
            spawn_probability=_at(obj, 'node_spawn_probability', i),
            speed_limit_kmh=_at(obj, 'node_speed_limit_kmh', i),
            lane_count_override=_at(obj, 'node_lane_count_override', i)))
    return result


def _mesh_origins(obj, original, baseline_edges):
    mesh = obj.data
    if not obj.get('nodes_identity_version'):
        current_edges = {tuple(sorted(e.vertices)) for e in mesh.edges}
        if len(mesh.vertices) != len(original) or current_edges != baseline_edges:
            raise ValueError('Reimport NODES before editing topology in an older scene')
        initialize_node_identity(obj, original)
    values = _identity_values(mesh)
    if values is None or len(values) != len(mesh.vertices):
        raise ValueError('NODES identity attribute is missing; reimport the source file')
    by_token = {_token(slot): slot for slot in range(len(original))}
    candidates = {}
    origins = [None] * len(mesh.vertices)
    for i, value in enumerate(values):
        slot = by_token.get(value)
        if slot is not None:
            candidates.setdefault(slot, []).append(i)
    for slot, choices in candidates.items():
        old = original[slot]
        def rank(i):
            point = mesh.vertices[i]
            co = point.co
            return ((co.x-old.x)**2 + (co.y-old.y)**2 + (co.z-old.z)**2,
                    bool(getattr(point, 'select', False)))
        choices.sort(key=lambda i: (*rank(i), i))
        if len(choices) > 1 and rank(choices[0]) == rank(choices[1]):
            raise ValueError('Coincident duplicated NODES identity: move the new point before exporting')
        origins[choices[0]] = slot
    return origins


def collect_compiled_nodes(objects, *, fla4=False):
    """Collect all categories, rebuild edited graph, retain foreign IDs."""
    objects = list(objects)
    for obj in objects:
        update = getattr(obj, 'update_from_editmode', None)
        if callable(update):
            update()
    categories = {}
    for obj in objects:
        category = obj.get('path_type')
        if category in ('nodes_vehicle', 'nodes_ped', 'nodes_navi'):
            if category in categories:
                raise ValueError('Select one imported mesh per NODES category and region')
            categories[category] = obj
    original = NodesFile(fla4=fla4 or any(o.get('fla4') for o in objects))
    original_counts = []
    for category, target in (('nodes_vehicle', original.vehicle_nodes),
                             ('nodes_ped', original.ped_nodes)):
        obj = categories.get(category)
        if obj is not None:
            target.extend(_original_nodes(obj))
        original_counts.append(len(target))
    for obj in objects:
        for category, count in zip(('vehicle', 'ped'), original_counts):
            expected = obj.get('nodes_' + category + '_count')
            if expected is not None and count != int(expected):
                raise ValueError('Include every vehicle and pedestrian mesh from this NODES region')
    nav_obj = categories.get('nodes_navi')
    nav_count = int(nav_obj.get('navi_count', len(nav_obj.data.vertices))) if nav_obj is not None else 0
    if any(int(o.get('nodes_navi_count', nav_count)) != nav_count for o in objects):
        raise ValueError('Include the navigation mesh from this NODES region')
    if nav_obj is not None:
        if len(nav_obj.data.vertices) != nav_count:
            raise ValueError('Edit vehicle mesh edges to create navigation; do not add/delete navigation vertices')
        values = _identity_values(nav_obj.data)
        if nav_obj.get('nodes_identity_version') and values is None:
            raise ValueError('Navigation identity attribute is missing; reimport NODES')
        positions = {}
        for i, point in enumerate(nav_obj.data.vertices):
            token = values[i] if values is not None else _token(i)
            if token in positions:
                raise ValueError('Navigation vertices have duplicate identities')
            positions[token] = nav_obj.matrix_world @ point.co
        for i in range(nav_count):
            co = positions.get(_token(i))
            if co is None:
                raise ValueError('Navigation topology changed; reimport NODES')
            original.navi_nodes.append(NaviNode(
                x=co.x, y=co.y, area_id=_at(nav_obj, 'navi_areas', i),
                node_id=_at(nav_obj, 'navi_ids', i), dir_x=_at(nav_obj, 'navi_dx', i),
                dir_y=_at(nav_obj, 'navi_dy', i), flags=_at(nav_obj, 'navi_flags', i)))
    for obj in objects:
        if obj.get('parsed_extras'):
            original.parsed_extras = True
            original.navi_links = _arr(obj, 'navi_links')
            original.link_lengths = _arr(obj, 'link_lengths')
            original.path_intersections = _arr(obj, 'path_intersections')
            break
        if obj.get('extra_data_b64'):
            original.extra_data = base64.b64decode(obj['extra_data_b64'], validate=True)
            break
    for obj in objects:
        if obj.get('num_links', 0):
            original.links = [PathLink(_at(obj, 'link_areas', i), _at(obj, 'link_nodes', i))
                              for i in range(int(obj['num_links']))]
            break
    areas = {int(o['nodes_area']) for o in objects if 'nodes_area' in o}
    if not areas:
        for obj in objects:
            stem = obj.get('nodes_filename', '').casefold().rsplit('.', 1)[0]
            if stem.startswith('nodes') and stem[5:].isdigit():
                areas.add(int(stem[5:]))
    if len(areas) != 1:
        raise ValueError('Cannot identify a single NODES region')
    area = areas.pop()
    baseline = graph_edges(original, area)
    nodes, origins, edited_edges = [], [], set()
    old_offset = 0
    for category, old_nodes in (('nodes_vehicle', original.vehicle_nodes),
                                ('nodes_ped', original.ped_nodes)):
        obj = categories.get(category)
        if obj is None:
            old_offset += len(old_nodes)
            continue
        local_baseline = {(a-old_offset, b-old_offset) for a, b in baseline
                          if old_offset <= a < b < old_offset + len(old_nodes)}
        slots = _mesh_origins(obj, old_nodes, local_baseline)
        # Sort surviving originals by identity. Reordering mesh vertices
        # alone must not renumber the game node array.
        order = sorted(range(len(slots)), key=lambda i:
                       (slots[i] is None, slots[i] if slots[i] is not None else i))
        local_to_output = {local: len(nodes)+i for i, local in enumerate(order)}
        adjacency = [[] for _ in slots]
        for edge in obj.data.edges:
            a, b = edge.vertices
            adjacency[a].append(b)
            adjacency[b].append(a)
            edited_edges.add(tuple(sorted((local_to_output[a], local_to_output[b]))))
        templates = list(slots)
        queue = [i for i, slot in enumerate(slots) if slot is not None]
        for local in queue:
            for neighbor in adjacency[local]:
                if templates[neighbor] is None:
                    templates[neighbor] = templates[local]
                    queue.append(neighbor)
        for local in order:
            co = obj.matrix_world @ obj.data.vertices[local].co
            slot = slots[local]
            template = templates[local]
            if template is None and old_nodes:
                template = 0
            node = replace(old_nodes[template]) if template is not None else PathNode(
                flags=0x000F0000, node_type=1, path_width=8,
                is_vehicle=category == 'nodes_vehicle')
            if slot is None:
                if get_area_id(int(co.x*8)/8, int(co.y*8)/8) != area:
                    raise ValueError('New NODES point lies outside its region; add it to the correct region mesh')
                node.area_id = area
                node.flags &= ~(15 | (1 << 4) | (1 << 6) | 0x00F00000)
                node.is_vehicle = category == 'nodes_vehicle'
            node.x, node.y, node.z = co.x, co.y, co.z
            if original.fla4:
                node.spawn_probability, node.speed_limit_kmh, node.lane_count_override = (
                    int(co.x*8), int(co.y*8), int(co.z*8))
            nodes.append(node)
            origins.append(None if slot is None else old_offset + slot)
        old_offset += len(old_nodes)
    # Category objects were collected vehicle-first, so this is its mesh count.
    vehicle_count = len(categories['nodes_vehicle'].data.vertices) if 'nodes_vehicle' in categories else 0
    nf, remap, changed = rebuild_graph(original, nodes, origins, edited_edges,
                                      area=area, vehicle_count=vehicle_count)
    nf.node_remap, nf.topology_changed = remap, changed
    nf.original_node_indices = origins
    return nf
