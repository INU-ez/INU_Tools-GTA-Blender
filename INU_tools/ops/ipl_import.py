"""Import IPL file → Blender (place objects or create empties)."""

from __future__ import annotations
import bpy
from mathutils import Quaternion, Vector
from ..core.ipl import read_ipl


def import_ipl(filepath: str, context=None) -> list:
    """
    Read IPL file and position matching Blender objects.

    For each ``inst`` entry, searches for a mesh object whose name matches
    model_name. Tries exact match first, then with _DFF/_LOD suffixes.
    If not found, creates an Empty at that position.

    GTA SA IPL quaternion is (X, Y, Z, W) → Blender quaternion is (W, X, Y, Z).

    Returns list of placed objects.
    """
    ipl = read_ipl(filepath)
    placed = []

    # Build multiple lookups for flexible matching
    # exact name (lowercase) → obj
    exact_lookup: dict[str, bpy.types.Object] = {}
    # clean name without suffixes (lowercase) → {suffix_type: obj}
    clean_lookup: dict[str, dict[str, bpy.types.Object]] = {}
    # mesh → its objects: a placement already standing on a row (re-import)
    # is reused instead of stacking another copy there
    by_data: dict = {}
    used: set = set()
    # placements of other IPL files and their LODs: never pulled off their
    # rows (Import All / several IPLs sharing a model)
    from .map_link import ipl_linked_file, norm
    here = norm(filepath)
    elsewhere: set = set()
    row_obj: dict = {}      # row index → object placed on it

    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        by_data.setdefault(obj.data, []).append(obj)
        if ipl_linked_file(obj) not in ('', here):
            elsewhere.add(obj)
            if obj.inu.lod_object is not None:
                elsewhere.add(obj.inu.lod_object)
        low = obj.name.lower()
        if low not in exact_lookup:
            exact_lookup[low] = obj

        clean, suffix_type = _clean_name_typed(obj.name)
        clean_low = clean.lower()
        if clean_low not in clean_lookup:
            clean_lookup[clean_low] = {}
        if suffix_type not in clean_lookup[clean_low]:
            clean_lookup[clean_low][suffix_type] = obj

    from ..core.ipl import is_lod_name, strip_lod_marker, lod_instance_indices
    lod_refs = lod_instance_indices(ipl.instances)

    for idx, inst in enumerate(ipl.instances):
        key = inst.model_name.lower()
        is_lod = idx in lod_refs or is_lod_name(inst.model_name)

        # GTA SA quat (X,Y,Z,W) → Blender quat (W,X,Y,Z), conjugate back
        quat = Quaternion((inst.rot_w, inst.rot_x, inst.rot_y, inst.rot_z)).conjugated()
        loc = Vector((inst.pos_x, inst.pos_y, inst.pos_z))

        # Try to find matching object
        obj = None

        # 1. Exact name match
        obj = exact_lookup.get(key)

        # 2. Match by clean name + appropriate suffix
        if not obj:
            if is_lod:
                base = strip_lod_marker(inst.model_name).lower()
                variants = clean_lookup.get(base, {})
                obj = variants.get('LOD') or variants.get('DFF')
                # No LOD mesh, only its model: that model is placed by its own
                # row (one references this row) or already stands here — a
                # stand-in on top would be a duplicate under the LOD's ID.
                if (obj is not None and not variants.get('LOD') and base != key
                        and (idx in lod_refs or any(
                            (o.location - loc).length < 1e-3
                            for o in by_data.get(obj.data, ())))):
                    continue
            else:
                variants = clean_lookup.get(key, {})
                obj = variants.get('DFF') or variants.get('OTHER')

        if obj:
            mine = by_data.setdefault(obj.data, [])
            # The one linked to this very row first (it may have been moved
            # since), then whatever stands on the row.
            standing = [o for o in mine
                        if (Vector(o.inu.ipl_last_pos) - loc).length < 1e-3
                        and ipl_linked_file(o) == here]
            standing += [o for o in mine if (o.location - loc).length < 1e-3]
            if obj in elsewhere and obj not in standing:
                used.add(obj)
            target = _row_target(obj, standing, used)
            fresh = target is None
            if fresh:
                # Another row of the same model: its own copy, not a move
                # of the one object (that kept only the last placement).
                target = _linked_copy(obj)
                used.add(target)
                mine.append(target)
            target.location = loc
            target.rotation_mode = 'QUATERNION'
            target.rotation_quaternion = quat

            # Rename <LOD marker somewhere>model → model_LOD
            if is_lod and target is obj and is_lod_name(obj.name):
                obj.name = strip_lod_marker(obj.name) + '_LOD'

            inu = target.inu
            inu.model_id = inst.model_id
            inu.interior_id = inst.interior
            inu.real_interior = int(getattr(inst, 'real_interior', 0) or 0)
            inu.lod_index = inst.lod_index
            # Link the model to this row (Add/Del/Sync find it by content).
            if not is_lod:
                from .map_link import stamp_ipl, norm
                stamp_ipl(target, norm(filepath), inst, inst.lod_index,
                          fresh=fresh)

            # Move paired COL to same position (COL not listed in IPL)
            if not is_lod and target is obj:
                clean, _ = _clean_name_typed(obj.name)
                col_variants = clean_lookup.get(clean.lower(), {})
                col_obj = col_variants.get('COL')
                if col_obj:
                    col_obj.location = loc
                    col_obj.rotation_mode = 'QUATERNION'
                    col_obj.rotation_quaternion = quat

            placed.append(target)
            row_obj[idx] = target
        else:
            # Create empty as placeholder (model not in scene)
            empty_name = inst.model_name + '_empty'
            empty = bpy.data.objects.new(empty_name, None)
            empty.empty_display_type = 'CUBE'
            empty.empty_display_size = 1.0
            empty.location = loc
            empty.rotation_mode = 'QUATERNION'
            empty.rotation_quaternion = quat
            empty['ipl_placeholder'] = True
            empty['ipl_model_name'] = inst.model_name

            # Put in IPL_Empty collection
            empty_col = bpy.data.collections.get("IPL_Empty")
            if not empty_col:
                empty_col = bpy.data.collections.new("IPL_Empty")
                bpy.context.scene.collection.children.link(empty_col)
            empty_col.objects.link(empty)

            inu = empty.inu
            inu.model_id = inst.model_id
            inu.interior_id = inst.interior
            inu.real_interior = int(getattr(inst, 'real_interior', 0) or 0)
            inu.lod_index = inst.lod_index

            placed.append(empty)

    # Each placement's LOD partner = the LOD placed on its lod_index row —
    # copies too (as Map Import does), else they all pair with the first LOD.
    for idx, inst in enumerate(ipl.instances):
        main, lodo = row_obj.get(idx), row_obj.get(inst.lod_index)
        if (main is not None and lodo is not None and lodo.data != main.data
                and not (idx in lod_refs or is_lod_name(inst.model_name))):
            main.inu.lod_object = lodo

    return placed


def _row_target(found, standing, used):
    """Object that takes one IPL row, or None → place a copy of *found*.

    *standing*: objects sharing *found*'s mesh that are linked to the row or
    already stand on it (re-import reuses them); else *found* itself on its
    first row. *used* collects the taken ones across the rows."""
    for o in standing:
        if o not in used:
            used.add(o)
            return o
    if found in used:
        return None
    used.add(found)
    return found


def _linked_copy(obj):
    """Another placement of *obj*: shares its mesh, sits in its collections,
    drops its IPL link (a copy must not answer for the source's row)."""
    from .map_link import clear_ipl
    dup = obj.copy()
    for c in obj.users_collection or (bpy.context.scene.collection,):
        c.objects.link(dup)
    clear_ipl(dup)
    return dup


def _clean_name_typed(name: str) -> tuple[str, str]:
    """Remove Blender numeric suffix and detect type using scene settings."""
    from ..tools.model_utils import get_model_type
    class _Mock:
        def __init__(self, n):
            self.name = n
    mt, base = get_model_type(_Mock(name))
    return base, mt or 'OTHER'
