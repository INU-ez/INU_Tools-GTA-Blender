"""Export Blender objects → IPL file (object placements)."""

from __future__ import annotations
from ..core.ipl import IplFile, IplInstance, write_ipl


def _scene_game() -> str:
    """Read the active game (III/VC/SA) off the current Blender scene.
    Falls back to SA when bpy isn't available (unit tests)."""
    try:
        import bpy
        from ..core import game_versions as gv
        return gv.game_of_scene(bpy.context.scene)
    except Exception:
        return 'SA'


def export_ipl(filepath: str, objects: list, *, binary: bool = False,
               fla_extended: bool = False) -> None:
    """
    Generate an IPL file from selected Blender objects.

    Position and rotation are taken from the object's world transform.
    Blender quaternion is (W, X, Y, Z), GTA SA IPL stores (X, Y, Z, W).
    If ``binary=True`` the file is written in `bnry` format.

    ``fla_extended=True`` writes a 12th ``realInterior`` column in each
    inst row — Fastman92 Limit Adjuster reads it; vanilla SA ignores
    it. Off by default to keep diffs minimal against vanilla output.

    LOD pairing: each ``inst`` line ends with ``lod_index`` — a position
    pointer into the same IPL's instance list. We resolve it in two
    tiers: first ``obj.inu.lod_object`` (PointerProperty set by Map
    Import) — its pointee's index in *this* export is recomputed, so it
    survives reordering. If no pointer is set we fall back to the raw
    ``obj.inu.lod_index`` carried in from a plain IPL import or typed in
    the panel; without that fallback such links silently became -1 on
    export (the "LOD index doesn't work anymore" regression). Either way
    -1 means "no LOD".
    """
    ipl = IplFile()
    obj_per_inst: list = []

    from ..tools.model_utils import get_model_type
    hd_of = None
    for obj in objects:
        if obj.type != 'MESH':
            continue

        mt, base = get_model_type(obj)
        # Collision is never placed in the IPL — bound to its DFF by name.
        if mt == 'COL':
            continue

        inu = getattr(obj, 'inu', None)

        # LOD keeps its own model name (map_link.lod_model_name — as Export
        # IDE writes it) so its placement references the LOD model, not the DFF.
        if mt == 'LOD':
            from .map_link import lod_hd_names, lod_model_name
            if hd_of is None:
                hd_of = lod_hd_names(objects)
            model_name = lod_model_name(obj, base, hd=hd_of.get(id(obj), ''),
                                        game=_scene_game())
        else:
            model_name = _clean_model_name(obj.name)
        model_id = getattr(inu, 'model_id', 0) if inu else 0
        interior = getattr(inu, 'interior_id', 0) if inu else 0
        real_interior = getattr(inu, 'real_interior', 0) if inu else 0

        # World position
        loc = obj.matrix_world.translation

        # World rotation as quaternion — Blender: (W,X,Y,Z)
        # GTA SA uses conjugate quaternion (like Kam's scripts)
        rot = obj.matrix_world.to_quaternion().conjugated()

        ipl.instances.append(IplInstance(
            model_id=model_id,
            model_name=model_name,
            interior=interior,
            pos_x=loc.x,
            pos_y=loc.y,
            pos_z=loc.z,
            rot_x=rot.x,
            rot_y=rot.y,
            rot_z=rot.z,
            rot_w=rot.w,
            lod_index=-1,  # provisionally; resolved below
            real_interior=real_interior,
        ))
        obj_per_inst.append(obj)

    # ── Dedupe identical placements ──
    # SA crashes (0x534134 access violation in CClumpModelInfo::SetClump)
    # when two ``inst`` lines have the same ``(model_id, x, y, z)`` —
    # the streaming slot allocator gets confused trying to materialise
    # the same model twice at the exact same spot. Real-world cause:
    # a Blender duplicate (``.001``) inherited the same cleaned name
    # plus position from its source object, and after ID unification
    # both end up with the same model_id too. Drop duplicates by
    # rounded position (mm precision is enough to consider two
    # placements «the same», robust against float jitter from
    # successive imports).
    seen_keys: set = set()
    keep_idx: list = []
    for i, inst in enumerate(ipl.instances):
        key = (
            inst.model_id,
            round(inst.pos_x, 3),
            round(inst.pos_y, 3),
            round(inst.pos_z, 3),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        keep_idx.append(i)
    if len(keep_idx) != len(ipl.instances):
        ipl.instances = [ipl.instances[i] for i in keep_idx]
        obj_per_inst = [obj_per_inst[i] for i in keep_idx]

    # ── Resolve lod_index ──
    # Tier 1: the LOD partner PointerProperty. Recompute the pointee's
    #   position in THIS export so the pointer survives dedupe/reorder.
    #   A pointer to an object outside the export selection means the
    #   LOD genuinely isn't in this IPL → stays -1 (no fallback).
    # Tier 2 (only when no pointer): honour the raw ``inu.lod_index``
    #   preserved from a plain IPL import or set by hand. Bounds-checked
    #   so a stale pointer can't index past the instance list and
    #   corrupt the file.
    obj_to_idx = {id(obj): i for i, obj in enumerate(obj_per_inst)}
    n_inst = len(ipl.instances)
    for i, obj in enumerate(obj_per_inst):
        inu = getattr(obj, 'inu', None)
        if inu is None:
            continue
        lod_obj = getattr(inu, 'lod_object', None)
        if lod_obj is not None:
            lod_idx = obj_to_idx.get(id(lod_obj), -1)
            if lod_idx >= 0:
                ipl.instances[i].lod_index = lod_idx
            continue
        raw = getattr(inu, 'lod_index', -1)
        if raw is not None and 0 <= raw < n_inst:
            ipl.instances[i].lod_index = raw

    write_ipl(filepath, ipl, binary=binary, fla_extended=fla_extended,
              game=_scene_game())


def _clean_model_name(name: str) -> str:
    """Remove Blender duplicate suffixes (.001) and model suffixes/prefixes."""
    from ..tools.model_utils import get_model_type
    # Strip Blender duplicate suffix FIRST (before suffix matching)
    if '.' in name:
        b, s = name.rsplit('.', 1)
        if s.isdigit():
            name = b
    class _Mock:
        def __init__(self, n):
            self.name = n
    _, base = get_model_type(_Mock(name))
    return base
