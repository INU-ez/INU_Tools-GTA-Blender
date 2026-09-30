"""
Import/export IPL sections (cull, grge, enex, pick, cars, auzo, jump, occl)
as Blender objects for visualization and editing.

Each section type creates objects in a dedicated collection with
custom properties for round-trip export.
"""

from __future__ import annotations
import bpy
import math

from ..core import ipl as _ipl


# ── Record identity (re-import dedup) ─────────────────────────────────
# Every imported record carries obj['ipl_row'] = its canonical file line
# (enex / jump: only on the entrance / start object). A second import of
# the same IPL skips records whose (kind, row) is already in the IPL_*
# collections — otherwise Export sections wrote every cull / enex twice
# and overflowed the game pools (400 enex, 72 mirror cull zones).

_ROW_FMT = {
    'cull': _ipl._format_cull_line,
    'grge': _ipl._format_grge_line,
    'enex': _ipl._format_enex_line,
    'pick': _ipl._format_pick_line,
    'cars': _ipl._format_cars_line,
    'auzo': _ipl._format_auzo_line,
    'jump': _ipl._format_jump_line,
    'occl': _ipl._format_occl_line,
    'zone': _ipl._format_zone_line,
}

# Default collection of each kind (import_* / export_* defaults) —
# the only place the dedup scan looks, same as Export sections reads.
_KIND_COLL = {
    'cull': 'IPL_Cull', 'grge': 'IPL_Garage', 'enex': 'IPL_Enex',
    'pick': 'IPL_Pickup', 'cars': 'IPL_Cars', 'auzo': 'IPL_Auzo',
    'jump': 'IPL_Jump', 'occl': 'IPL_Occl', 'zone': 'IPL_Zone',
}


def _existing_rows() -> set:
    """``{(ipl_type, ipl_row)}`` of the records already in the IPL_*
    collections. enex exits / jump targets / cameras carry no row."""
    rows = set()
    for name in _KIND_COLL.values():
        col = bpy.data.collections.get(name)
        if col is None:
            continue
        for obj in col.objects:
            row = obj.get('ipl_row')
            if row:
                rows.add((obj.get('ipl_type'), row))
    return rows


def _filter_new(kind: str, entries: list, existing: set):
    """``(kept, skipped_count)`` — drops the records whose line is already
    in the scene. Repeats inside one file are kept (the game loads them)."""
    fmt = _ROW_FMT[kind]
    kept = [e for e in entries if (kind, fmt(e)) not in existing]
    return kept, len(entries) - len(kept)


# ── Collection helpers ────────────────────────────────────────────────

def _get_or_create_collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _link_to_collection(obj: bpy.types.Object, col: bpy.types.Collection):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def _make_empty(name: str, display_type: str, size: float,
                location: tuple, collection: bpy.types.Collection) -> bpy.types.Object:
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = display_type
    empty.empty_display_size = size
    empty.location = location
    collection.objects.link(empty)
    return empty


def _make_cube_mesh(name: str, center: tuple, size: tuple,
                    collection: bpy.types.Collection) -> bpy.types.Object:
    """Create a wireframe cube mesh at center with given dimensions."""
    import bmesh
    bm = bmesh.new()
    sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
    verts = [
        bm.verts.new((-sx, -sy, -sz)), bm.verts.new((sx, -sy, -sz)),
        bm.verts.new((sx, sy, -sz)), bm.verts.new((-sx, sy, -sz)),
        bm.verts.new((-sx, -sy, sz)), bm.verts.new((sx, -sy, sz)),
        bm.verts.new((sx, sy, sz)), bm.verts.new((-sx, sy, sz)),
    ]
    faces = [
        (0, 1, 2, 3), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 3, 7, 4), (1, 2, 6, 5),
    ]
    for f in faces:
        bm.faces.new([verts[i] for i in f])

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = center
    obj.display_type = 'WIRE'
    collection.objects.link(obj)
    return obj


# ── CULL ZONES ────────────────────────────────────────────────────────

def import_cull_zones(culls: list, collection_name: str = "IPL_Cull",
                      game: str = 'SA') -> list:
    from ..core.ipl_geom import cull_row, cull_box_from_row
    col = _get_or_create_collection(collection_name)
    objects = []
    for i, c in enumerate(culls):
        # SA: rotated box 2|v2| x 2|v1| (see core/ipl_geom); III/VC: min..max.
        row = cull_row(c)
        center, size, rot_z = cull_box_from_row(row, game)
        name = f"Cull_{i:03d}"
        obj = _make_cube_mesh(name, center, size, col)
        obj.rotation_euler.z = rot_z
        obj['ipl_type'] = 'cull'
        obj['ipl_row'] = _ROW_FMT['cull'](c)
        # v2 = geometry as the game reads it. The original numbers are
        # written back while the box is untouched (exact, including the
        # non-rectangular vanilla ones); older objects keep old formulas.
        obj['ipl_geom_v'] = 2
        obj['cull_row'] = row
        obj['cull_game'] = game
        obj['cull_flag'] = c.flag
        obj['cull_unknown3'] = c.unknown3
        if c.has_mirror:
            obj['cull_mirror_vx'] = c.mirror_vx
            obj['cull_mirror_vy'] = c.mirror_vy
            obj['cull_mirror_vz'] = c.mirror_vz
            obj['cull_mirror_cm'] = c.mirror_cm
        objects.append(obj)
    return objects


def _world_aabb(obj):
    """World AABB of the object's bound box (rotation / scale / parent)."""
    mw = obj.matrix_world
    pts = [[sum(mw[r][k] * c[k] for k in range(3)) + mw[r][3]
            for r in range(3)] for c in obj.bound_box]
    return ([min(p[r] for p in pts) for r in range(3)],
            [max(p[r] for p in pts) for r in range(3)])


def _cull_geom_v2(obj, game: str) -> list:
    """The 9 geometric numbers of a v2 cull box for ``game``."""
    from ..core.ipl_geom import (cull_box_from_row, cull_box_equal,
                                 cull_row_from_box, cull_row_from_aabb)
    row = [float(v) for v in obj.get('cull_row', ())]
    src = obj.get('cull_game', 'SA')
    box = (tuple(obj.location), tuple(obj.dimensions),
           obj.rotation_euler.z)
    if (len(row) >= 9 and src == game
            and cull_box_equal(cull_box_from_row(row, src), box)):
        return row[:9]
    if game in ('III', 'VC'):
        lo, hi = _world_aabb(obj)
        return cull_row_from_aabb(
            lo, hi, row if src in ('III', 'VC') and len(row) >= 9 else None)
    return cull_row_from_box(*box)


def export_cull_zones(collection_name: str = "IPL_Cull",
                      game: str = 'SA') -> list:
    from ..core.ipl import IplCull
    from ..core.ipl_geom import apply_cull_row
    col = bpy.data.collections.get(collection_name)
    if not col:
        return []
    result = []
    for obj in col.objects:
        if obj.get('ipl_type') != 'cull':
            continue
        if obj.get('ipl_geom_v', 1) >= 2:
            c = apply_cull_row(IplCull(flag=obj.get('cull_flag', 0),
                                       unknown3=obj.get('cull_unknown3', 0)),
                               _cull_geom_v2(obj, game))
            if 'cull_mirror_vx' in obj:
                c.mirror_vx = obj['cull_mirror_vx']
                c.mirror_vy = obj['cull_mirror_vy']
                c.mirror_vz = obj['cull_mirror_vz']
                c.mirror_cm = obj['cull_mirror_cm']
            result.append(c)
            continue
        loc = obj.location
        dim = obj.dimensions
        bottom = loc.z - dim.z / 2
        top = loc.z + dim.z / 2
        c = IplCull(
            center_x=loc.x, center_y=loc.y, center_z=loc.z,
            unknown1=obj.get('cull_unknown1', 0),
            length=dim.y, bottom=bottom,
            width=dim.x, unknown2=obj.get('cull_unknown2', 0),
            top=top, flag=obj.get('cull_flag', 0),
            unknown3=obj.get('cull_unknown3', 0),
        )
        if 'cull_mirror_vx' in obj:
            c.mirror_vx = obj['cull_mirror_vx']
            c.mirror_vy = obj['cull_mirror_vy']
            c.mirror_vz = obj['cull_mirror_vz']
            c.mirror_cm = obj['cull_mirror_cm']
        result.append(c)
    return result


# ── GARAGES ───────────────────────────────────────────────────────────

def import_garages(garages: list, collection_name: str = "IPL_Garage") -> list:
    col = _get_or_create_collection(collection_name)
    objects = []
    for i, g in enumerate(garages):
        name = f"Garage_{g.name}" if g.name else f"Garage_{i:03d}"
        loc = (g.pos_x, g.pos_y, g.pos_z)
        obj = _make_empty(name, 'CUBE', 2.0, loc, col)
        obj['ipl_type'] = 'grge'
        obj['ipl_row'] = _ROW_FMT['grge'](g)
        # v2: front point / far corner as offsets from the marker, so
        # moving (or turning) it moves the whole garage, not one corner.
        from ..core.ipl_geom import garage_offsets
        obj['ipl_geom_v'] = 2
        obj['grge_d_line'], obj['grge_d_cube'] = garage_offsets(g)
        obj['grge_flags'] = g.flags
        obj['grge_type'] = g.garage_type
        obj['grge_name'] = g.name
        objects.append(obj)
    return objects


def export_garages(collection_name: str = "IPL_Garage") -> list:
    from ..core.ipl import IplGarage
    col = bpy.data.collections.get(collection_name)
    if not col:
        return []
    result = []
    for obj in col.objects:
        if obj.get('ipl_type') != 'grge':
            continue
        loc = obj.location
        if obj.get('ipl_geom_v', 1) >= 2 and 'grge_d_line' in obj:
            from ..core.ipl_geom import garage_points
            (lx, ly), (cx, cy, cz) = garage_points(
                tuple(loc), list(obj['grge_d_line']),
                list(obj['grge_d_cube']), obj.rotation_euler.z)
            result.append(IplGarage(
                pos_x=loc.x, pos_y=loc.y, pos_z=loc.z,
                line_x=lx, line_y=ly, cube_x=cx, cube_y=cy, cube_z=cz,
                flags=obj.get('grge_flags', 0),
                garage_type=obj.get('grge_type', 0),
                name=obj.get('grge_name', ''),
            ))
            continue
        result.append(IplGarage(
            pos_x=loc.x, pos_y=loc.y, pos_z=loc.z,
            line_x=obj.get('grge_line_x', 0), line_y=obj.get('grge_line_y', 0),
            cube_x=obj.get('grge_cube_x', 0), cube_y=obj.get('grge_cube_y', 0),
            cube_z=obj.get('grge_cube_z', 0),
            flags=obj.get('grge_flags', 0), garage_type=obj.get('grge_type', 0),
            name=obj.get('grge_name', ''),
        ))
    return result


# ── ENEX (Entry/Exit) ────────────────────────────────────────────────

def import_enexs(enexs: list, collection_name: str = "IPL_Enex") -> list:
    col = _get_or_create_collection(collection_name)
    objects = []
    for i, e in enumerate(enexs):
        name = f"Enex_{e.name}" if e.name else f"Enex_{i:03d}"
        # Entrance marker
        enter = _make_empty(f"{name}_enter", 'PLAIN_AXES', 1.0,
                            (e.x1, e.y1, e.z1), col)
        enter.rotation_euler.z = math.radians(e.enter_angle)
        enter['ipl_type'] = 'enex'
        enter['ipl_row'] = _ROW_FMT['enex'](e)
        enter['enex_index'] = i
        enter['enex_is_exit'] = False
        enter['enex_size_x'] = e.size_x
        enter['enex_size_y'] = e.size_y
        enter['enex_size_z'] = e.size_z
        enter['enex_target_interior'] = e.target_interior
        enter['enex_flags'] = e.flags
        enter['enex_name'] = e.name
        enter['enex_sky'] = e.sky
        enter['enex_num_peds'] = e.num_peds
        enter['enex_time_on'] = e.time_on
        enter['enex_time_off'] = e.time_off
        # Exit position stored on entrance
        enter['enex_exit_x'] = e.x2
        enter['enex_exit_y'] = e.y2
        enter['enex_exit_z'] = e.z2
        enter['enex_exit_angle'] = e.exit_angle

        # Exit marker — linked from the entrance (enex_exit_obj); moving
        # or turning it changes the exported exit
        exit_obj = _make_empty(f"{name}_exit", 'PLAIN_AXES', 0.8,
                               (e.x2, e.y2, e.z2), col)
        exit_obj.rotation_euler.z = math.radians(e.exit_angle)
        exit_obj['ipl_type'] = 'enex_exit'
        exit_obj['enex_index'] = i
        enter['enex_exit_obj'] = exit_obj

        objects.extend([enter, exit_obj])
    return objects


def _alive(o, ipl_type: str) -> bool:
    """A linked marker (ID property) that still exists in the scene —
    deleted in the viewport it stays in bpy.data with no collections."""
    return (o is not None and o.get('ipl_type') == ipl_type
            and len(o.users_collection) > 0)


def export_enexs(collection_name: str = "IPL_Enex") -> list:
    from ..core.ipl import IplEnex
    col = bpy.data.collections.get(collection_name)
    if not col:
        return []
    result = []
    for obj in col.objects:
        if obj.get('ipl_type') != 'enex':
            continue
        loc = obj.location
        x2, y2, z2 = (obj.get('enex_exit_x', 0), obj.get('enex_exit_y', 0),
                      obj.get('enex_exit_z', 0))
        exit_angle = obj.get('enex_exit_angle', 0)
        ex = obj.get('enex_exit_obj')
        if _alive(ex, 'enex_exit'):
            # Untouched marker keeps the file's exact numbers
            el, ea = ex.location, math.degrees(ex.rotation_euler.z)
            if (max(abs(el.x - x2), abs(el.y - y2), abs(el.z - z2)) > 1e-3
                    or abs(ea - exit_angle) > 1e-2):
                x2, y2, z2, exit_angle = el.x, el.y, el.z, ea
        result.append(IplEnex(
            x1=loc.x, y1=loc.y, z1=loc.z,
            enter_angle=math.degrees(obj.rotation_euler.z),
            size_x=obj.get('enex_size_x', 0), size_y=obj.get('enex_size_y', 0),
            size_z=obj.get('enex_size_z', 0),
            x2=x2, y2=y2, z2=z2,
            exit_angle=exit_angle,
            target_interior=obj.get('enex_target_interior', 0),
            flags=obj.get('enex_flags', 0), name=obj.get('enex_name', ''),
            sky=obj.get('enex_sky', 0), num_peds=obj.get('enex_num_peds', 0),
            time_on=obj.get('enex_time_on', 0), time_off=obj.get('enex_time_off', 0),
        ))
    return result


# ── PICKUPS ───────────────────────────────────────────────────────────

def import_pickups(pickups: list, collection_name: str = "IPL_Pickup") -> list:
    col = _get_or_create_collection(collection_name)
    objects = []
    for i, p in enumerate(pickups):
        name = f"Pickup_{p.pickup_id}_{i:03d}"
        obj = _make_empty(name, 'SPHERE', 0.5, (p.pos_x, p.pos_y, p.pos_z), col)
        obj['ipl_type'] = 'pick'
        obj['ipl_row'] = _ROW_FMT['pick'](p)
        obj['pickup_id'] = p.pickup_id
        objects.append(obj)
    return objects


def export_pickups(collection_name: str = "IPL_Pickup") -> list:
    from ..core.ipl import IplPickup
    col = bpy.data.collections.get(collection_name)
    if not col:
        return []
    result = []
    for obj in col.objects:
        if obj.get('ipl_type') != 'pick':
            continue
        loc = obj.location
        result.append(IplPickup(
            pickup_id=obj.get('pickup_id', 0),
            pos_x=loc.x, pos_y=loc.y, pos_z=loc.z,
        ))
    return result


# ── PARKED CARS ───────────────────────────────────────────────────────

def import_cars(cars: list, collection_name: str = "IPL_Cars") -> list:
    col = _get_or_create_collection(collection_name)
    objects = []
    for i, c in enumerate(cars):
        name = f"Car_{c.car_id}_{i:03d}"
        obj = _make_empty(name, 'SINGLE_ARROW', 1.5,
                          (c.pos_x, c.pos_y, c.pos_z), col)
        obj.rotation_euler.z = math.radians(c.angle)
        obj['ipl_type'] = 'cars'
        obj['ipl_row'] = _ROW_FMT['cars'](c)
        obj['car_id'] = c.car_id
        obj['car_primary_color'] = c.primary_color
        obj['car_secondary_color'] = c.secondary_color
        obj['car_force_spawn'] = c.force_spawn
        obj['car_alarm'] = c.alarm
        obj['car_door_lock'] = c.door_lock
        obj['car_unknown1'] = c.unknown1
        obj['car_unknown2'] = c.unknown2
        objects.append(obj)
    return objects


def export_cars(collection_name: str = "IPL_Cars") -> list:
    from ..core.ipl import IplCar
    col = bpy.data.collections.get(collection_name)
    if not col:
        return []
    result = []
    for obj in col.objects:
        if obj.get('ipl_type') != 'cars':
            continue
        loc = obj.location
        result.append(IplCar(
            pos_x=loc.x, pos_y=loc.y, pos_z=loc.z,
            angle=math.degrees(obj.rotation_euler.z),
            car_id=obj.get('car_id', -1),
            primary_color=obj.get('car_primary_color', -1),
            secondary_color=obj.get('car_secondary_color', -1),
            force_spawn=obj.get('car_force_spawn', 0),
            alarm=obj.get('car_alarm', 0),
            door_lock=obj.get('car_door_lock', 0),
            unknown1=obj.get('car_unknown1', 0),
            unknown2=obj.get('car_unknown2', 0),
        ))
    return result


# ── AUDIO ZONES ───────────────────────────────────────────────────────

def import_auzos(auzos: list, collection_name: str = "IPL_Auzo") -> list:
    col = _get_or_create_collection(collection_name)
    objects = []
    for i, a in enumerate(auzos):
        name = f"Auzo_{a.name}_{i:03d}" if a.name else f"Auzo_{i:03d}"
        if a.is_sphere:
            obj = _make_empty(name, 'SPHERE', a.radius or 1.0,
                              (a.x1, a.y1, a.z1), col)
            obj['auzo_is_sphere'] = True
            obj['auzo_radius'] = a.radius
        else:
            center = ((a.x1 + a.x2) / 2, (a.y1 + a.y2) / 2, (a.z1 + a.z2) / 2)
            size = (abs(a.x2 - a.x1), abs(a.y2 - a.y1), abs(a.z2 - a.z1))
            obj = _make_cube_mesh(name, center, size, col)
            obj['auzo_is_sphere'] = False
        obj['ipl_type'] = 'auzo'
        obj['ipl_row'] = _ROW_FMT['auzo'](a)
        obj['auzo_name'] = a.name
        obj['auzo_audio_id'] = a.audio_id
        obj['auzo_switch'] = a.switch
        objects.append(obj)
    return objects


def export_auzos(collection_name: str = "IPL_Auzo") -> list:
    from ..core.ipl import IplAuzo
    col = bpy.data.collections.get(collection_name)
    if not col:
        return []
    result = []
    for obj in col.objects:
        if obj.get('ipl_type') != 'auzo':
            continue
        a = IplAuzo(
            name=obj.get('auzo_name', ''),
            audio_id=obj.get('auzo_audio_id', 0),
            switch=obj.get('auzo_switch', 0),
        )
        if obj.get('auzo_is_sphere', False):
            loc = obj.location
            a.x1 = loc.x
            a.y1 = loc.y
            a.z1 = loc.z
            a.radius = obj.get('auzo_radius', 1.0)
        else:
            loc = obj.location
            dim = obj.dimensions
            a.x1 = loc.x - dim.x / 2
            a.y1 = loc.y - dim.y / 2
            a.z1 = loc.z - dim.z / 2
            a.x2 = loc.x + dim.x / 2
            a.y2 = loc.y + dim.y / 2
            a.z2 = loc.z + dim.z / 2
        result.append(a)
    return result


# ── STUNT JUMPS ───────────────────────────────────────────────────────

def import_jumps(jumps: list, collection_name: str = "IPL_Jump") -> list:
    col = _get_or_create_collection(collection_name)
    objects = []
    for i, j in enumerate(jumps):
        name = f"Jump_{i:03d}"
        # Start zone — midpoint of the two corners
        start_center = (
            (j.start_lower_x + j.start_upper_x) / 2,
            (j.start_lower_y + j.start_upper_y) / 2,
            (j.start_lower_z + j.start_upper_z) / 2,
        )
        start_size = (
            abs(j.start_upper_x - j.start_lower_x),
            abs(j.start_upper_y - j.start_lower_y),
            max(abs(j.start_upper_z - j.start_lower_z), 0.1),
        )
        start_obj = _make_cube_mesh(f"{name}_start", start_center, start_size, col)
        start_obj['ipl_type'] = 'jump'
        start_obj['ipl_row'] = _ROW_FMT['jump'](j)
        start_obj['jump_index'] = i
        start_obj['jump_reward'] = j.reward
        start_obj['jump_camera_x'] = j.camera_x
        start_obj['jump_camera_y'] = j.camera_y
        start_obj['jump_camera_z'] = j.camera_z

        # Target zone
        target_center = (
            (j.target_lower_x + j.target_upper_x) / 2,
            (j.target_lower_y + j.target_upper_y) / 2,
            (j.target_lower_z + j.target_upper_z) / 2,
        )
        target_size = (
            abs(j.target_upper_x - j.target_lower_x),
            abs(j.target_upper_y - j.target_lower_y),
            max(abs(j.target_upper_z - j.target_lower_z), 0.1),
        )
        target_obj = _make_cube_mesh(f"{name}_target", target_center, target_size, col)
        target_obj['ipl_type'] = 'jump_target'
        target_obj['jump_index'] = i

        # Camera point
        cam = _make_empty(f"{name}_camera", 'PLAIN_AXES', 1.0,
                          (j.camera_x, j.camera_y, j.camera_z), col)
        cam['ipl_type'] = 'jump_camera'
        cam['jump_index'] = i
        # jump_index restarts at 0 on every import — the pair is linked
        # from the start object, the index is only a fallback for old scenes
        start_obj['jump_target_obj'] = target_obj
        start_obj['jump_camera_obj'] = cam

        objects.extend([start_obj, target_obj, cam])
    return objects


def export_jumps(collection_name: str = "IPL_Jump") -> list:
    from ..core.ipl import IplJump
    col = bpy.data.collections.get(collection_name)
    if not col:
        return []

    # Every start object is a jump; its target / camera come from the
    # links set at import. Old scenes (no links) pair by jump_index,
    # only among the targets / cameras no link has claimed.
    starts = []
    targets = {}
    cameras = {}
    claimed = set()
    for obj in col.objects:
        t = obj.get('ipl_type', '')
        if t == 'jump':
            starts.append(obj)
            for key, kind in (('jump_target_obj', 'jump_target'),
                              ('jump_camera_obj', 'jump_camera')):
                o = obj.get(key)
                if _alive(o, kind):
                    claimed.add(o.name)
        elif t in ('jump_target', 'jump_camera'):
            idx = obj.get('jump_index', -1)
            if idx >= 0:
                (targets if t == 'jump_target' else cameras).setdefault(
                    idx, []).append(obj)

    def _pair(s, key, kind, pool):
        o = s.get(key)
        if _alive(o, kind):
            return o
        if o is not None:           # linked, but the marker was deleted
            return None
        for o in pool.get(s.get('jump_index', -1), ()):
            if o.name not in claimed:
                claimed.add(o.name)
                return o
        return None

    result = []
    starts.sort(key=lambda o: (o.get('jump_index', -1), o.name))
    for s in starts:
        t = _pair(s, 'jump_target_obj', 'jump_target', targets)
        c = _pair(s, 'jump_camera_obj', 'jump_camera', cameras)
        sl, sd = s.location, s.dimensions
        j = IplJump(
            start_lower_x=sl.x - sd.x / 2, start_lower_y=sl.y - sd.y / 2,
            start_lower_z=sl.z - sd.z / 2,
            start_upper_x=sl.x + sd.x / 2, start_upper_y=sl.y + sd.y / 2,
            start_upper_z=sl.z + sd.z / 2,
            reward=s.get('jump_reward', 0),
        )
        if t:
            tl, td = t.location, t.dimensions
            j.target_lower_x = tl.x - td.x / 2
            j.target_lower_y = tl.y - td.y / 2
            j.target_lower_z = tl.z - td.z / 2
            j.target_upper_x = tl.x + td.x / 2
            j.target_upper_y = tl.y + td.y / 2
            j.target_upper_z = tl.z + td.z / 2
        if c:
            j.camera_x = c.location.x
            j.camera_y = c.location.y
            j.camera_z = c.location.z
        result.append(j)
    return result


# ── OCCLUSION ZONES ──────────────────────────────────────────────────

def import_occls(occls: list, collection_name: str = "IPL_Occl") -> list:
    col = _get_or_create_collection(collection_name)
    objects = []
    for i, o in enumerate(occls):
        name = f"Occl_{i:03d}"
        center = (o.mid_x, o.mid_y, o.bottom_z + o.height / 2)
        size = (o.width_x, o.width_y, max(o.height, 0.1))
        obj = _make_cube_mesh(name, center, size, col)
        obj.rotation_euler.z = math.radians(o.rot_x)
        obj['ipl_type'] = 'occl'
        obj['ipl_row'] = _ROW_FMT['occl'](o)
        # rot_x хранится в obj.rotation_euler.z (Blender transform);
        # rot_y, rot_z, flags — в custom props (нет места в transform).
        # Старые имена occl_unknown1/2/3 читаются как fallback в export.
        obj['occl_rot_y'] = o.rot_y
        obj['occl_rot_z'] = o.rot_z
        obj['occl_flags'] = o.flags
        objects.append(obj)
    return objects


def export_occls(collection_name: str = "IPL_Occl") -> list:
    from ..core.ipl import IplOccl
    col = bpy.data.collections.get(collection_name)
    if not col:
        return []
    result = []
    for obj in col.objects:
        if obj.get('ipl_type') != 'occl':
            continue
        loc = obj.location
        dim = obj.dimensions
        # Семантика как в старом коде, только имена custom-props:
        #   rot_x — первичная Z-rotation объекта в Blender'е
        #   rot_y, rot_z, flags — из custom props
        # Backward compat: старые сцены имеют occl_unknown1/2/3.
        rot_x = math.degrees(obj.rotation_euler.z)
        rot_y = float(obj.get('occl_rot_y',
                              obj.get('occl_unknown1', 0.0)))
        rot_z = float(obj.get('occl_rot_z',
                              obj.get('occl_unknown2', 0.0)))
        flags = int(obj.get('occl_flags',
                            obj.get('occl_unknown3', 0)))
        result.append(IplOccl(
            mid_x=loc.x, mid_y=loc.y,
            bottom_z=loc.z - dim.z / 2,
            width_x=dim.x, width_y=dim.y, height=dim.z,
            rot_x=rot_x, rot_y=rot_y, rot_z=rot_z,
            flags=flags,
        ))
    return result


# ── ZONES ────────────────────────────────────────────────────────────

def import_zones(zones: list, collection_name: str = "IPL_Zone") -> list:
    col = _get_or_create_collection(collection_name)
    objects = []
    for i, z in enumerate(zones):
        name = f"Zone_{z.name}" if z.name else f"Zone_{i:03d}"
        center = ((z.x1 + z.x2) / 2, (z.y1 + z.y2) / 2, (z.z1 + z.z2) / 2)
        size = (abs(z.x2 - z.x1), abs(z.y2 - z.y1), max(abs(z.z2 - z.z1), 0.1))
        obj = _make_cube_mesh(name, center, size, col)
        obj['ipl_type'] = 'zone'
        obj['ipl_row'] = _ROW_FMT['zone'](z)
        obj['zone_name'] = z.name
        obj['zone_type'] = z.zone_type
        obj['zone_level'] = z.level
        obj['zone_info'] = z.info       # 10th column (GXT key)
        objects.append(obj)
    return objects


def export_zones(collection_name: str = "IPL_Zone") -> list:
    from ..core.ipl import IplZone
    col = bpy.data.collections.get(collection_name)
    if not col:
        return []
    result = []
    for obj in col.objects:
        if obj.get('ipl_type') != 'zone':
            continue
        loc = obj.location
        dim = obj.dimensions
        result.append(IplZone(
            name=obj.get('zone_name', ''),
            zone_type=obj.get('zone_type', 0),
            x1=loc.x - dim.x / 2, y1=loc.y - dim.y / 2, z1=loc.z - dim.z / 2,
            x2=loc.x + dim.x / 2, y2=loc.y + dim.y / 2, z2=loc.z + dim.z / 2,
            level=obj.get('zone_level', 0),
            info=obj.get('zone_info', ''),
        ))
    return result


# ── MASTER IMPORT/EXPORT ─────────────────────────────────────────────

def import_ipl_sections(ipl, sections: set | None = None,
                        skip_existing: bool = True, existing: set | None = None,
                        game: str | None = None) -> dict:
    """Import selected IPL sections as Blender objects.
    Returns dict of section_name → list of created objects, plus
    ``'_skipped'`` (int) — records already in the scene (``existing``:
    a snapshot from ``_existing_rows()``, taken here when not given).
    ``game`` picks the cull layout (SA / III / VC); default = scene's."""
    all_sections = {'cull', 'grge', 'enex', 'pick', 'cars', 'auzo', 'jump', 'occl', 'zone'}
    if sections is None:
        sections = all_sections
    if game is None:
        from ..core import game_versions as gv
        game = gv.game_of_scene(bpy.context.scene)
    if existing is None and skip_existing:
        existing = _existing_rows()
    skipped = 0

    def _new(kind, entries):
        nonlocal skipped
        if not skip_existing:
            return entries
        kept, n = _filter_new(kind, entries, existing)
        skipped += n
        return kept

    result = {}
    if 'cull' in sections and ipl.culls:
        result['cull'] = import_cull_zones(_new('cull', ipl.culls), game=game)
    if 'grge' in sections and ipl.garages:
        result['grge'] = import_garages(_new('grge', ipl.garages))
    if 'enex' in sections and ipl.enexs:
        result['enex'] = import_enexs(_new('enex', ipl.enexs))
    if 'pick' in sections and ipl.pickups:
        result['pick'] = import_pickups(_new('pick', ipl.pickups))
    if 'cars' in sections and ipl.cars:
        result['cars'] = import_cars(_new('cars', ipl.cars))
    if 'auzo' in sections and ipl.auzos:
        result['auzo'] = import_auzos(_new('auzo', ipl.auzos))
    if 'jump' in sections and ipl.jumps:
        result['jump'] = import_jumps(_new('jump', ipl.jumps))
    if 'occl' in sections and ipl.occls:
        result['occl'] = import_occls(_new('occl', ipl.occls))
    if 'zone' in sections and ipl.zones:
        result['zone'] = import_zones(_new('zone', ipl.zones))
    result['_skipped'] = skipped
    return result


def export_ipl_sections(game: str | None = None) -> dict:
    """Export all IPL section objects back to dataclasses.
    Returns dict of section_name → list of dataclass instances.
    ``game`` — target format of the cull boxes; default = scene's."""
    if game is None:
        from ..core import game_versions as gv
        game = gv.game_of_scene(bpy.context.scene)
    return {
        'cull': export_cull_zones(game=game),
        'grge': export_garages(),
        'enex': export_enexs(),
        'pick': export_pickups(),
        'cars': export_cars(),
        'auzo': export_auzos(),
        'jump': export_jumps(),
        'occl': export_occls(),
        'zone': export_zones(),
    }
