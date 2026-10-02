"""Persistent point identities for our legacy Blender Curve paths.

Legacy Curve/SplinePoint has no custom point attributes. Reserve the
otherwise unused softbody-goal weight on path_ipl points for an exact
float32 ID. This does not alter bevel radius, tilt or NURBS weights.
Softbody modifiers / manual goal-weight edits are incompatible with this
channel. Duplicated IDs keep the point nearest its last position; new
points get defaults. Exactly coincident duplicates remain ambiguous.
"""

import json
import math


FIELDS = dict(type=2, link=-1, cross=0, width=1.0, ll=1, rl=1,
              speed=0, flags=0, spawn=1.0)
_CAPACITY = 1 << 20
_BUSY = False


def curve_points(obj):
    for spline in obj.data.splines:
        points = (spline.bezier_points if getattr(spline, 'type', '') == 'BEZIER'
                  else spline.points)
        yield from points


def _co(point):
    co = point.co
    return [float(co.x), float(co.y), float(co.z)]


def _selected(point):
    return bool(getattr(point, 'select',
                        getattr(point, 'select_control_point', False)))


def _tag(slot):
    # 64..96 is within RNA's hard 0.01..100 goal-weight range. All tags
    # are multiples of 2^-15, exactly representable by Blender float32.
    # Permutation reduces interpolated subdivision tags matching old IDs.
    return 64.0 + ((slot * 104729 + 1) % _CAPACITY) / 32768.0


def _slot(point):
    value = float(getattr(point, 'weight_softbody', 0.0))
    scaled = (value - 64.0) * 32768.0
    if not math.isfinite(scaled) or not 0 <= scaled < _CAPACITY:
        return None
    code = round(scaled)
    if abs(scaled - code) > 0.01:
        return None
    return ((code - 1) * pow(104729, -1, _CAPACITY)) % _CAPACITY


def set_slot(obj, slot, values=None):
    for key, value in {**FIELDS, **(values or {})}.items():
        obj[f'pn_{slot}_{key}'] = value


def slot_values(obj, slot):
    return {key: obj.get(f'pn_{slot}_{key}', default)
            for key, default in FIELDS.items()}


def ensure_point_slots(obj):
    """Return (point, stable slot) pairs; migrate old index properties once.

    Called after topology updates and before every editor/export action.
    Existing geometry is never rescaled during legacy scene migration:
    old imported scenes need reimport to correct their /16 placement.
    """
    if getattr(obj, 'type', None) != 'CURVE' or obj.get('path_type') != 'path_ipl':
        return []
    if any(getattr(m, 'type', '') == 'SOFT_BODY'
           for m in getattr(obj, 'modifiers', ())):
        obj['pn_identity_warning'] = 'SOFT_BODY'
        raise ValueError('Path IPL point IDs reserve Softbody Weight; remove the Softbody modifier')
    points = list(curve_points(obj))
    count = int(obj.get('pn_count', 0))
    if count < 0 or count > _CAPACITY:
        raise ValueError('Path IPL point identity capacity exceeded')
    if int(obj.get('pn_semantics_version', 0)) < 2:
        # Import stored all 12 slots, including padding/external types.
        # Add/Convert authored only internal nodes. For identifiable old
        # imports retain their old file scale during export without moving
        # geometry. Ambiguous all-internal scenes keep world coordinates.
        imported = (count == 12 and any(int(obj.get(f'pn_{s}_type', 2)) != 2
                                        for s in range(count)))
        # The old fields were named one column too far to the right.
        # Preserve their actual parsed column values, not the labels.
        for slot in range(count):
            prefix = f'pn_{slot}_'
            values = dict(
                type=obj.get(prefix + 'type', 0), link=obj.get(prefix + 'link', -1),
                cross=obj.get(prefix + 'area', 0),
                width=float(obj.get(prefix + 'unk', 0.0)),
                ll=int(obj.get(prefix + 'width', 1)),
                rl=int(obj.get(prefix + 'll', 1)),
                speed=int(obj.get(prefix + 'rl', 0)),
                flags=int(obj.get(prefix + 'mw', 0)),
                spawn=float(obj.get(prefix + 'flags', 1)))
            obj[prefix + 'extra'] = str(obj.get(prefix + 'spawn', 0))
            set_slot(obj, slot, values)
        obj['pn_semantics_version'] = 2
        # Only 12-slot legacy curves can be imports. Other sizes came
        # from Add/Convert and do not need an import-scale warning.
        obj['pn_legacy_coordinates'] = count == 12
        obj['pn_legacy_import_scale'] = imported

    if not obj.get('pn_identity_version'):
        slots = [slot for slot in range(count)
                 if int(obj.get(f'pn_{slot}_type', 0)) > 0]
        for index, point in enumerate(points):
            if index >= len(slots):
                if count >= _CAPACITY:
                    raise ValueError('Path IPL point identity capacity exceeded')
                slots.append(count)
                set_slot(obj, count)
                count += 1
            point.weight_softbody = _tag(slots[index])
        obj['pn_identity_version'] = 1
        obj['pn_count'] = count
        obj['pn_identity_live'] = json.dumps(slots[:len(points)])

    positions = json.loads(obj.get('pn_identity_positions', '{}'))
    live = set(json.loads(obj.get('pn_identity_live', '[]')))
    candidates = {}
    fresh = []
    for index, point in enumerate(points):
        slot = _slot(point)
        if slot not in live:
            fresh.append((index, point))
        else:
            candidates.setdefault(slot, []).append((index, point))

    pairs = {}
    for slot, choices in candidates.items():
        previous = positions.get(str(slot))
        def rank(item):
            index, point = item
            distance = (sum((a - b) ** 2 for a, b in zip(_co(point), previous))
                        if previous is not None else 0.0)
            return distance, _selected(point), index
        choices.sort(key=rank)
        keeper = choices[0]
        pairs[keeper[0]] = (keeper[1], slot)
        fresh.extend(choices[1:])
        if len(choices) > 1 and rank(choices[0])[:2] == rank(choices[1])[:2]:
            obj['pn_identity_warning'] = 'COINCIDENT_DUPLICATE'

    # Manual goal-weight edits can erase a tag. Recover a uniquely
    # identifiable unchanged coordinate instead of dropping its properties.
    missing = live - set(candidates)
    recovered = []
    for index, point in fresh:
        matches = [slot for slot in missing if positions.get(str(slot)) == _co(point)]
        if len(matches) == 1:
            slot = matches[0]
            point.weight_softbody = _tag(slot)
            pairs[index] = (point, slot)
            missing.remove(slot)
            obj['pn_identity_warning'] = 'WEIGHT_EDIT'
        else:
            recovered.append((index, point))
    if missing and recovered:
        # A tag was lost and no unique position can recover it. Keep old
        # slots as orphans for recovery; expose the ambiguity in the UI.
        obj['pn_identity_warning'] = 'WEIGHT_EDIT'
    for index, point in sorted(recovered):
        if count >= _CAPACITY:
            raise ValueError('Path IPL point identity capacity exceeded')
        set_slot(obj, count)
        point.weight_softbody = _tag(count)
        pairs[index] = (point, count)
        count += 1

    ordered = [pairs[index] for index in range(len(points))]
    next_live = json.dumps([slot for _, slot in ordered])
    next_positions = json.dumps({str(slot): _co(point) for point, slot in ordered})
    if obj.get('pn_identity_live') != next_live:
        obj['pn_identity_live'] = next_live
    if obj.get('pn_identity_positions') != next_positions:
        obj['pn_identity_positions'] = next_positions
    if obj.get('pn_count') != count:
        obj['pn_count'] = count
    return ordered


def _path_identity_update(scene, depsgraph):
    global _BUSY
    if _BUSY:
        return
    _BUSY = True
    try:
        import bpy
        # Edit Mode Curve changes report Curve data IDs, object changes
        # report objects. Ignore other geometry updates.
        curves = {u.id.original for u in depsgraph.updates
                  if isinstance(u.id, bpy.types.Curve)}
        objects = {u.id.original for u in depsgraph.updates
                   if isinstance(u.id, bpy.types.Object)
                   and u.id.get('path_type') == 'path_ipl'}
        if not curves and not objects:
            return
        targets = set(objects)
        if curves:
            targets.update(obj for obj in scene.objects
                           if obj.get('path_type') == 'path_ipl'
                           and getattr(obj, 'data', None) in curves)
        for obj in targets:
            if obj.get('path_type') == 'path_ipl':
                try:
                    ensure_point_slots(obj)
                except ValueError as exc:
                    print(f'[INU] Path IPL identity: {exc}')
    finally:
        _BUSY = False


def _path_identity_load(_dummy):
    import bpy
    for obj in bpy.data.objects:
        try:
            ensure_point_slots(obj)
        except ValueError as exc:
            print(f'[INU] Path IPL identity: {exc}')


def _path_identity_initialize():
    import bpy
    # addon_utils.enable registers under _RestrictContext: bpy.data has
    # no object collections until registration returns. Migrate later.
    if not hasattr(bpy.data, 'objects'):
        return 0.1
    _path_identity_load(None)
    return None


def register_path_identity_handlers():
    import bpy
    for handlers, callback in ((bpy.app.handlers.depsgraph_update_post, _path_identity_update),
                               (bpy.app.handlers.load_post, _path_identity_load)):
        bpy.app.handlers.persistent(callback)
        if callback not in handlers:
            handlers.append(callback)
    if not bpy.app.timers.is_registered(_path_identity_initialize):
        bpy.app.timers.register(_path_identity_initialize, first_interval=0.1)


def unregister_path_identity_handlers():
    import bpy
    if bpy.app.timers.is_registered(_path_identity_initialize):
        bpy.app.timers.unregister(_path_identity_initialize)
    for handlers, callback in ((bpy.app.handlers.depsgraph_update_post, _path_identity_update),
                               (bpy.app.handlers.load_post, _path_identity_load)):
        if callback in handlers:
            handlers.remove(callback)
