"""Bake provenance, UV diagnostics and portable stack data. No bpy imports."""
import hashlib
import json
import math
import time

import numpy as np

STAMP = 'inu_bake_stamp_v1'
_mesh_cache = {}


def layer_dict(layer):
    """Only writable RNA settings; never copy image identities or bake areas."""
    result = {}
    for prop in layer.bl_rna.properties:
        key = prop.identifier
        if key in {'rna_type', 'uid', 'paint_mask_uid', 'masks'} or prop.is_readonly:
            continue
        value = getattr(layer, key)
        if prop.type in {'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM'}:
            result[key] = list(value) if getattr(prop, 'is_array', False) else value
    if hasattr(layer, 'masks'):
        result['masks'] = [layer_dict(mask) for mask in layer.masks]
    return result


def stack_data(layers):
    rows = []
    indices = {layer.uid: i for i, layer in enumerate(layers)}
    for layer in layers:
        row = layer_dict(layer)
        row['paint_mask_index'] = indices.get(layer.paint_mask_uid, -1)
        rows.append(row)
    return {'version': 1, 'layers': rows}


def validate_stack(data):
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Unsupported bake preset version')
    rows = data.get('layers')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 128:
        raise ValueError('A bake preset must contain 1–128 layers')
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('map_id'), str):
            raise ValueError('Invalid bake layer')
        masks = row.get('masks', [])
        if not isinstance(masks, list) or len(masks) > 32 or any(not isinstance(m, dict) for m in masks):
            raise ValueError('Invalid masks')
        index = row.get('paint_mask_index', -1)
        if not isinstance(index, int) or index < -1 or index >= len(rows):
            raise ValueError('Invalid paint mask reference')
    return rows


def _array(collection, field, width, dtype):
    values = np.empty(len(collection) * width, dtype=dtype)
    collection.foreach_get(field, values)
    return values.tobytes()


def mesh_digest(obj, uv_name, *, cached=False):
    """UI caches expensive mesh reads briefly; actual bake always bypasses it."""
    me = obj.data
    key = (me.as_pointer(), uv_name, obj.mode)
    now = time.monotonic()
    if cached and key in _mesh_cache and now - _mesh_cache[key][0] < .75:
        return _mesh_cache[key][1]
    h = hashlib.sha256()
    if obj.mode == 'EDIT':
        import bmesh
        bm = bmesh.from_edit_mesh(me)
        uv = bm.loops.layers.uv.get(uv_name)
        h.update(np.asarray([v.co[:] for v in bm.verts], dtype=np.float32).tobytes())
        h.update(np.asarray([v.index for f in bm.faces for v in f.verts], dtype=np.int32).tobytes())
        h.update(np.asarray([len(f.verts) for f in bm.faces], dtype=np.int32).tobytes())
        h.update(np.asarray([f.smooth for f in bm.faces], dtype=np.bool_).tobytes())
        if uv:
            h.update(np.asarray([l[uv].uv[:] for f in bm.faces for l in f.loops], dtype=np.float32).tobytes())
    else:
        for coll, field, width, dtype in (
                (me.vertices, 'co', 3, np.float32), (me.loops, 'vertex_index', 1, np.int32),
                (me.polygons, 'loop_total', 1, np.int32), (me.polygons, 'use_smooth', 1, np.bool_)):
            h.update(_array(coll, field, width, dtype))
        uv = me.uv_layers.get(uv_name)
        if uv:
            h.update(_array(uv.data, 'uv', 2, np.float32))
    value = h.hexdigest()
    if len(_mesh_cache) > 128:
        _mesh_cache.clear()
    _mesh_cache[key] = now, value
    return value


def selection_digest(obj, domain):
    if obj.mode == 'EDIT':
        import bmesh
        bm = bmesh.from_edit_mesh(obj.data)
        items = bm.edges if domain == 'EDGE' else bm.faces
    else:
        items = obj.data.edges if domain == 'EDGE' else obj.data.polygons
    return hashlib.sha256(bytes(int(item.select) for item in items)).hexdigest()


def modifier_settings(obj):
    rows = []
    for modifier in obj.modifiers:
        row = {'type': modifier.type}
        for prop in modifier.bl_rna.properties:
            if prop.identifier in {'rna_type', 'name', 'execution_time'} or prop.is_readonly:
                continue
            if prop.type in {'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM'}:
                value = getattr(modifier, prop.identifier)
                row[prop.identifier] = (sorted(value) if isinstance(value, set) else
                    list(value) if getattr(prop, 'is_array', False) else value)
        rows.append(row)
    return rows


def bake_stamp(obj, scene_settings, layer, uv_name, *, cached=False):
    s = scene_settings
    mid = layer.map_id
    values = {key: getattr(s, 'gtatools_bake_' + key) for key in (
        'mode', 'res_x', 'res_y', 'margin', 'aa', 'samples', 'isolate', 'use_prelight')}
    fields = []
    if mid in {'DIFFUSE', 'ALPHA'} and s.gtatools_bake_mode == 'HILOW':
        values['alpha_projection_version'] = 1
    if mid == 'BEVEL' or layer.effect_basis == 'BEVEL' or any(
            m.enabled and m.basis == 'BEVEL' for m in getattr(layer, 'masks', ())):
        fields += ['bevel_size', 'bevel_samples', 'selected_edges', 'selected_faces']
        if s.gtatools_bake_selected_edges:
            values['edge_selection'] = selection_digest(obj, 'EDGE')
        if s.gtatools_bake_selected_faces:
            values['face_selection'] = selection_digest(obj, 'FACE')
    if mid == 'NORMAL':
        for key in ('normal_bevel', 'normal_bevel_selection', 'normal_bevel_width',
                    'normal_bevel_segments', 'normal_bevel_profile'):
            values[key] = getattr(layer, key)
        if layer.normal_bevel and s.gtatools_bake_mode == 'UV':
            values['selection'] = selection_digest(obj, layer.normal_bevel_selection)
        if s.gtatools_bake_mode != 'CAMERA':
            values.pop('aa', None)  # Native Normal intentionally doesn't supersample.
    if mid in {'AO', 'DIRT', 'EDGEWEAR', 'CURVATURE'}:
        fields += ['cavity_distance', 'cavity_gain']
    if mid == 'HIGHLIGHT':
        fields += ['highlight_azimuth', 'highlight_elevation', 'highlight_sharpness']
    if mid in {'LIGHTMAP', 'SHADOW', 'DIFFUSE_LIT', 'EMIT_GI'}:
        fields += ['use_scene_light', 'light_energy_scale', 'lightmap_samples', 'lightmap_light_mode']
    if s.gtatools_bake_mode == 'HILOW':
        fields += ['cage_extrusion', 'max_ray']
        from .bake_maps import find_hilow_pair, HI_SUFFIX, LOW_SUFFIX
        high, _ = find_hilow_pair(obj, HI_SUFFIX, LOW_SUFFIX)
        values['high'] = (dict(name=high.name_full,
            matrix=[list(row) for row in high.matrix_world],
            mesh=mesh_digest(high, '', cached=cached), modifiers=modifier_settings(high)) if high else None)
    if s.gtatools_bake_mode == 'CAMERA':
        fields += ['cam_axis', 'cam_padding', 'cam_keep_uv']
    values.update((key, getattr(s, 'gtatools_bake_' + key)) for key in fields)
    # Object transform changes ray distances, lighting and modifier evaluation.
    values['matrix'] = [list(row) for row in obj.matrix_world]
    values['modifiers'] = modifier_settings(obj)
    values['mesh'] = mesh_digest(obj, uv_name, cached=cached)
    values['uv'] = uv_name
    values['map_id'] = mid
    return values


def stamp_status(image, current):
    if image is None:
        return 'MISSING'
    saved = image.get(STAMP)
    if not saved:
        return 'UNKNOWN'
    try:
        return 'READY' if json.loads(saved) == current else 'STALE'
    except (TypeError, ValueError):
        return 'UNKNOWN'


def polygon_area(poly):
    return abs(sum(a[0]*b[1] - b[0]*a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) * .5


def triangle_intersection(a, b):
    """Convex clipping; touching boundaries do not count as UV overlap."""
    orientation = sum(p[0]*q[1] - q[0]*p[1] for p, q in zip(b, b[1:] + b[:1]))
    sign = 1 if orientation >= 0 else -1
    out = list(a)
    for p, q in zip(b, b[1:] + b[:1]):
        old, out = out, []
        if not old:
            break
        def distance(v):
            return sign*((q[0]-p[0])*(v[1]-p[1]) - (q[1]-p[1])*(v[0]-p[0]))
        last = old[-1]
        dl = distance(last)
        for point in old:
            dp = distance(point)
            if (dp >= 0) != (dl >= 0):
                t = dl/(dl-dp)
                out.append((last[0]+t*(point[0]-last[0]), last[1]+t*(point[1]-last[1])))
            if dp >= 0:
                out.append(point)
            last, dl = point, dp
    return polygon_area(out) if len(out) >= 3 else 0.0


def diagnose_uv(faces, triangles, *, pair_limit=200000):
    """Return selectable face sets. Exact stacks are informational, never errors.

    faces: {face_index: [(u,v), ...]}; triangles: [(face_index, [uv,uv,uv])].
    A bounded broad phase prevents accidental quadratic work on large assets.
    """
    result = {k: set() for k in ('degenerate', 'outside', 'stacked', 'overlap')}
    footprints, groups = {}, {}
    for index, uv in faces.items():
        if any(not math.isfinite(c) for p in uv for c in p) or polygon_area(uv) < 1e-12:
            result['degenerate'].add(index)
            continue
        if any(c < -1e-6 or c > 1+1e-6 for p in uv for c in p):
            result['outside'].add(index)
        footprint = tuple(sorted((round(p[0], 6), round(p[1], 6)) for p in uv))
        groups.setdefault(footprint, []).append(index)
        footprints[index] = footprint
    for indices in groups.values():
        if len(indices) > 1:
            result['stacked'].update(indices)
    # Collapse duplicate footprints before triangle comparisons (fences often
    # contain thousands of intentional copies). Retain group membership below.
    representatives = {indices[0] for indices in groups.values()}
    items = []
    for index, uv in triangles:
        if index in representatives:
            items.append((min(p[0] for p in uv), max(p[0] for p in uv),
                          min(p[1] for p in uv), max(p[1] for p in uv), index, uv))
    items.sort(key=lambda item: item[0])
    active, checked, complete = [], 0, True
    for item in items:
        active = [other for other in active if other[1] > item[0]+1e-10]
        for other in active:
            if item[4] == other[4] or other[3] <= item[2]+1e-10 or item[3] <= other[2]+1e-10:
                continue
            checked += 1
            if checked > pair_limit:
                complete = False
                break
            if triangle_intersection(item[5], other[5]) > 1e-10:
                for index in (item[4], other[4]):
                    result['overlap'].update(groups[footprints[index]])
        if not complete:
            break
        active.append(item)
    return {**{key: sorted(value) for key, value in result.items()}, 'complete': complete}


def selection_uv_conflicts(faces, edge_masks):
    """Different selected UV edges on exactly stacked faces need distinct pixels."""
    groups, conflicts = {}, set()
    for index, uv in faces.items():
        footprint = tuple(sorted((round(p[0], 6), round(p[1], 6)) for p in uv))
        mask = frozenset(tuple(sorted(((round(uv[i][0], 6), round(uv[i][1], 6)),
                                       (round(uv[(i+1)%len(uv)][0], 6), round(uv[(i+1)%len(uv)][1], 6)))))
                         for i in edge_masks.get(index, ()))
        groups.setdefault(footprint, []).append((index, mask))
    for rows in groups.values():
        if len({mask for _, mask in rows}) > 1:
            conflicts.update(index for index, _ in rows)
    return sorted(conflicts)
