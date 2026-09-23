# INU_tools.ops.ifp_export — Export Blender actions to GTA SA IFP

import bpy
import mathutils
from ..core.ifp import (
    IFPFile, Animation, AnimBone, KeyFrame,
    HAS_ROT, HAS_TRANS,
    write_ifp, merge_ifp, decimate_ifp, classify_bone_refs,
)


def _bone_rest_local(armature, bone_name):
    """Return ``(rest_quat, rest_mat3)`` — the bone's rest pose in
    parent space (or armature space for the root). Used to invert the
    import-time ``bl_quat = rest_inv @ gta_quat`` transform: on export
    we apply ``gta_quat = rest_quat @ bl_quat`` so the round-trip
    preserves bone-in-parent rotations exactly.
    """
    if not armature or armature.type != 'ARMATURE':
        return mathutils.Quaternion(), mathutils.Matrix.Identity(3)
    rest_bone = armature.data.bones.get(bone_name)
    if not rest_bone:
        return mathutils.Quaternion(), mathutils.Matrix.Identity(3)
    rest_mat = rest_bone.matrix_local
    if rest_bone.parent:
        rest_mat = rest_bone.parent.matrix_local.inverted() @ rest_mat
    rest_quat = rest_mat.to_quaternion()
    return rest_quat, rest_quat.to_matrix()


# Blender 5.x removed the flat ``Action.fcurves`` collection in favour
# of layered Actions (Slot → Layer → Strip → Channelbag → fcurves). This
# helper yields fcurves regardless of version so the export code stays
# linear.
_USE_LAYERED = hasattr(bpy.types, 'ActionSlot')


def _iter_action_fcurves(action):
    """Yield every fcurve attached to ``action`` (legacy or layered)."""
    if not _USE_LAYERED:
        for fc in action.fcurves:
            yield fc
        return
    for layer in getattr(action, 'layers', []):
        for strip in getattr(layer, 'strips', []):
            # Blender 5.x: strip.channelbags is a collection (per-slot).
            # Older alphas exposed ``channelbag()`` as a callable; keep
            # both paths so we don't break anyone who froze a beta.
            cbs = getattr(strip, 'channelbags', None)
            if cbs is None:
                cb_call = getattr(strip, 'channelbag', None)
                if callable(cb_call):
                    try:
                        cb = cb_call(action.slots[0]) if action.slots else None
                    except Exception:
                        cb = None
                    cbs = [cb] if cb else []
                else:
                    cbs = []
            for cb in cbs:
                if cb is None:
                    continue
                for fc in getattr(cb, 'fcurves', []):
                    yield fc


def validate_action_bones(action, armature):
    """Check which bone-name references in an Action's fcurves exist
    on the given armature.

    Silent in-game fails come from this exact mismatch: IFP stores
    ``bone_id`` as the armature index of the bone, so fcurve data on
    bones the target skeleton doesn't have produces ``bone_id = -1``
    entries the game silently skips. Calling this before export and
    surfacing the mismatch lets the user rename / retarget before the
    .ifp goes into an IMG.

    Args:
        action: bpy.types.Action whose fcurves we inspect.
        armature: bpy.types.Object (type='ARMATURE') — target skeleton.

    Returns:
        (unknown, known) — both sorted lists of bone names. ``unknown``
        are referenced by Action fcurves but absent from the armature;
        ``known`` are the ones that will map correctly.
    """
    if armature is None or armature.type != 'ARMATURE':
        return [], []

    return classify_bone_refs(
        (fc.data_path for fc in _iter_action_fcurves(action)),
        (pb.name for pb in armature.pose.bones),
    )


def _resolve_actions(actions, armature):
    """Fallback source when ``actions=None``: everything tagged with
    ifp_source plus whatever is currently assigned to ``armature``."""
    return [
        a for a in bpy.data.actions
        if a.get('ifp_source') or (
            armature and armature.animation_data
            and armature.animation_data.action == a
        )
    ]


def _sample_post_ik_pose(armature, frames):
    """Walk ``frames`` and capture every non-control deform bone's
    visual basis (loc + rot quaternion) at each frame.

    Returns ``{bone_name: [(frame, basis_loc, basis_quat), ...]}``.

    Used when the armature has the IK rig active: the user keyframes
    only the IK control bones, so the deform bones have no fcurves
    of their own. Sampling at every IK-keyed frame gives us the
    post-IK pose without ever modifying the source Action — Bake &
    Clear's destructive flow is bypassed entirely.

    The visual-key math here mirrors ``ik_rig._visual_key_deform_bones``
    so the resulting basis values reproduce the IK-driven pose 1:1
    after the (now stripped) IK constraints are gone.
    """
    samples = {}
    if not frames:
        return samples
    scene = bpy.context.scene
    saved_frame = scene.frame_current
    try:
        for f in sorted(frames):
            f_int = int(round(f))
            scene.frame_set(f_int)
            bpy.context.view_layer.update()

            # Capture all visuals upfront so reading a child's matrix
            # isn't contaminated by parent-basis writes — pure read,
            # no writes here, but the same defensive pattern as in
            # ik_rig keeps things consistent if this is ever extended.
            visuals = {pb.name: pb.matrix.copy()
                       for pb in armature.pose.bones}

            for pb in armature.pose.bones:
                db = armature.data.bones.get(pb.name)
                if db is None:
                    continue
                if db.get('inu_ik_control'):
                    continue
                visual = visuals[pb.name]
                if pb.parent:
                    parent_visual = visuals.get(
                        pb.parent.name, pb.parent.matrix)
                    local_rest = (
                        pb.parent.bone.matrix_local.inverted()
                        @ pb.bone.matrix_local)
                    basis = (local_rest.inverted()
                             @ parent_visual.inverted() @ visual)
                else:
                    basis = pb.bone.matrix_local.inverted() @ visual
                loc, rot_q, _scl = basis.decompose()
                samples.setdefault(pb.name, []).append(
                    (f, loc, rot_q))
    finally:
        scene.frame_set(saved_frame)
        bpy.context.view_layer.update()
    return samples


def _build_animation_from_ik_samples(action, armature,
                                      fps, samples):
    """Build an Animation by sampling deform-bone poses (post-IK)
    at every keyed frame, instead of reading deform-bone fcurves.
    Mirrors the fcurve path's bone_id resolution + rest_quat /
    rest_mat math, so the resulting IFP is interchangeable with
    the post-Bake & Clear output."""
    anim = Animation(name=action.name)
    for bone_name, sample_list in samples.items():
        if not sample_list:
            continue
        # Skip bones that never actually move — sampling captures
        # every non-control deform bone, but most ped bones (fingers,
        # jaw, eyelids, etc.) sit at identity basis the whole time.
        # Including them would bloat the IFP with constant rotations
        # the engine could already read from the rest skeleton.
        rot_active = any(
            abs(q.w - 1.0) > 1e-4 or abs(q.x) > 1e-4
            or abs(q.y) > 1e-4 or abs(q.z) > 1e-4
            for _f, _l, q in sample_list
        )
        loc_active = any(
            abs(loc.x) > 1e-5 or abs(loc.y) > 1e-5
            or abs(loc.z) > 1e-5
            for _f, loc, _q in sample_list
        )
        # Same root-only translation rule as the fcurve path: SA peds animate
        # translation on the root frame only, so a non-root location channel
        # (e.g. a retarget leak) must be dropped or the engine snaps that joint
        # to the parent (arm into the torso). Animated map objects keep it.
        if loc_active:
            db = armature.data.bones.get(bone_name) if armature else None
            is_root = ((db is not None and db.parent is None)
                       or bone_name.strip() in ('Root', 'Normal', 'Bip01'))
            if not is_root and not bool(armature and armature.get('inu_animobj')):
                loc_active = False
        if not (rot_active or loc_active):
            continue

        rest_quat, rest_mat = _bone_rest_local(armature, bone_name)
        bone = AnimBone(name=bone_name)
        bone.key_type = (
            (HAS_ROT if rot_active else 0)
            | (HAS_TRANS if loc_active else 0)
        )

        if armature:
            data_bone = armature.data.bones.get(bone_name)
            if data_bone is not None and 'bone_id' in data_bone:
                bone.bone_id = int(data_bone['bone_id'])
            else:
                pb = armature.pose.bones.get(bone_name)
                if pb:
                    bone.bone_id = list(armature.pose.bones).index(pb)
            if data_bone is not None and 'gta_ifp_name' in data_bone:
                bone.name = str(data_bone['gta_ifp_name'])

        for frame, loc, rot_q in sample_list:
            kf = KeyFrame(time=frame / fps)
            if rot_active:
                gta_quat = rest_quat @ rot_q
                kf.rotation = (gta_quat.x, gta_quat.y,
                               gta_quat.z, gta_quat.w)
            if loc_active:
                gta_loc = rest_mat @ loc
                kf.translation = (gta_loc.x, gta_loc.y, gta_loc.z)
            bone.keyframes.append(kf)
        anim.bones.append(bone)
    return anim


def _build_animation(action, armature, fps: float) -> Animation:
    """Build one Animation dataclass from a Blender Action.

    When the armature has an active IK rig (``inu_ik_rigged`` flag),
    we BYPASS the fcurve-based path and sample post-IK pose at every
    keyed frame instead. This lets the user animate purely on IK
    controls without first running Bake & Clear — the export
    captures the IK-driven deform pose on the fly."""
    if armature is not None and armature.get('inu_ik_rigged'):
        # Collect every keyed frame across the action — control
        # bones (where the user's keys live) AND any deform fcurves
        # they may have authored alongside.
        keyed_frames = set()
        for fc in _iter_action_fcurves(action):
            if not fc.data_path.startswith('pose.bones['):
                continue
            for kp in fc.keyframe_points:
                keyed_frames.add(int(round(kp.co[0])))
        if keyed_frames:
            samples = _sample_post_ik_pose(armature, keyed_frames)
            return _build_animation_from_ik_samples(
                action, armature, fps, samples)
        # Fall through to fcurve path if no keys at all (empty action).

    anim = Animation(name=action.name)

    # Byte-exact source cache (set by ifp_import): {bone_name: {frame: [rot4
    # (+trans3)]}}. When a keyframe was NOT edited, we re-emit the original
    # quantised values verbatim instead of the ±1 LSB the float rest-transform
    # round-trip would otherwise produce, so a vanilla-in→export-out is
    # bit-identical.
    src_map = {}
    _src_raw = action.get('inu_ifp_src')
    if _src_raw:
        try:
            import json
            src_map = json.loads(_src_raw)
        except Exception:
            src_map = {}

    # Group fcurves by bone name
    bone_curves = {}
    for fc in _iter_action_fcurves(action):
        if not fc.data_path.startswith('pose.bones['):
            continue
        parts = fc.data_path.split('"')
        if len(parts) < 2:
            continue
        bone_name = parts[1]
        prop = fc.data_path.rsplit('.', 1)[-1]
        bone_curves.setdefault(bone_name, {}).setdefault(prop, []).append(fc)

    for bone_name, props in bone_curves.items():
        # Skip IK control bones (created by ops.ik_rig). They live
        # inside the armature only for posing, are marked with the
        # ``inu_ik_control`` custom prop, and have no HAnim id —
        # without this guard their fcurves would fall through to
        # the pose-index id fallback and remap real ped rotations.
        if armature is not None:
            db = armature.data.bones.get(bone_name)
            if db is not None and db.get('inu_ik_control'):
                continue

        bone = AnimBone(name=bone_name)

        has_rot = 'rotation_quaternion' in props
        has_euler = 'rotation_euler' in props and not has_rot
        has_loc = 'location' in props

        # Strip the translation channel from every NON-root bone. SA ped IFPs
        # only ever animate translation on the root (Normal/Bip01); every other
        # bone takes its rest_head from the skeleton DFF. The engine reads a
        # non-root location channel as "put this bone at the offset relative to
        # its parent", so:
        #   • Blender's keying sets add an all-zero location to every selected
        #     bone → would collapse joints into the parent ("blob");
        #   • a retarget/transfer can LEAK a tiny (sub-cm) non-zero location
        #     onto a limb → the engine snaps that joint to the offset, e.g. an
        #     arm pulled into the torso (this is real — found in the wild).
        # The old `|v| > 1e-5` test only caught the all-zero case and let the
        # tiny-but-nonzero retarget leak through. So drop location on any
        # non-root bone outright. Armature-based animated map objects
        # (inu_animobj) DO translate a non-root bone, so they keep it.
        if has_loc:
            db = armature.data.bones.get(bone_name) if armature else None
            is_root = ((db is not None and db.parent is None)
                       or bone_name.strip() in ('Root', 'Normal', 'Bip01'))
            is_animobj = bool(armature and armature.get('inu_animobj'))
            loc_active = any(abs(kp.co[1]) > 1e-5
                             for fc in props['location']
                             for kp in fc.keyframe_points)
            if not loc_active:
                has_loc = False           # empty channel from a keying set
            elif not is_root and not is_animobj:
                has_loc = False           # retarget/transfer leak on a ped limb

        # Same logic for rotation: if every keyframe's bl_quat is
        # essentially identity (or its sign-flipped twin -identity),
        # the bone wasn't actually animated. Writing rotation keys
        # for such a bone would leak the bone's rest_quat into the
        # IFP — for Root with non-default Edit-Mode orientation
        # (e.g. head→tail along +X instead of +Y), rest_quat is
        # non-identity and the game would visibly rotate the
        # character even though the user never animated Root.
        # Mirrors the IK-aware path's rot_active check, so a Bake &
        # Clear'd action exports the same rotation set as one with
        # an active IK rig — without this, post-Bake Root suddenly
        # gets a rest_quat-derived rotation key the IK path would
        # have skipped. abs(|w|-1) treats q=identity and
        # q=-identity (same rotation, opposite hemisphere) both as
        # "no rotation".
        if has_rot:
            rot_active = False
            sample_frames = set()
            for fc in props['rotation_quaternion']:
                for kp in fc.keyframe_points:
                    sample_frames.add(kp.co[0])
            for sf in sample_frames:
                quat_w, quat_x, quat_y, quat_z = 1.0, 0.0, 0.0, 0.0
                for fc in props['rotation_quaternion']:
                    val = fc.evaluate(sf)
                    if fc.array_index == 0:
                        quat_w = val
                    elif fc.array_index == 1:
                        quat_x = val
                    elif fc.array_index == 2:
                        quat_y = val
                    elif fc.array_index == 3:
                        quat_z = val
                if (abs(abs(quat_w) - 1.0) > 1e-4
                        or abs(quat_x) > 1e-4
                        or abs(quat_y) > 1e-4
                        or abs(quat_z) > 1e-4):
                    rot_active = True
                    break
            if not rot_active:
                has_rot = False

        if has_euler:
            euler_active = False
            for fc in props['rotation_euler']:
                for kp in fc.keyframe_points:
                    if abs(kp.co[1]) > 1e-5:
                        euler_active = True
                        break
                if euler_active:
                    break
            if not euler_active:
                has_euler = False

        bone.key_type = 0
        if has_rot or has_euler:
            bone.key_type |= HAS_ROT
        if has_loc:
            bone.key_type |= HAS_TRANS
        if not bone.key_type:
            continue

        # SA bone_id is the HAnim hash from the DFF (e.g. L UpperArm=32,
        # Bip01 L Clavicle=31) — NOT a sequential pose-bone index. The
        # DFF importer stashes the original id on each edit_bone as the
        # 'bone_id' custom prop; read it back here. Falling back to the
        # pose index produced ids 1..32 for an animation whose vanilla
        # ids spread across 0..302, so the engine remapped rotations to
        # the wrong bones (twisted hands / broken face).
        if armature:
            data_bone = armature.data.bones.get(bone_name)
            if data_bone is not None and 'bone_id' in data_bone:
                bone.bone_id = int(data_bone['bone_id'])
            else:
                pb = armature.pose.bones.get(bone_name)
                if pb:
                    bone.bone_id = list(armature.pose.bones).index(pb)
            # Write the IFP's original bone name back (e.g. 'Normal' when the
            # armature renamed it to 'Root'), so a vanilla round-trip is
            # byte-faithful. Stashed by ifp_import when it matched by bone_id.
            if data_bone is not None and 'gta_ifp_name' in data_bone:
                bone.name = str(data_bone['gta_ifp_name'])

        # Mirrors the import-time formula: import did
        #   bl_quat = rest_inv @ gta_quat,  bl_loc = rest_inv_mat @ gta_loc
        # so export reverses it with
        #   gta_quat = rest_quat @ bl_quat, gta_loc = rest_mat @ bl_loc
        # to recover the absolute bone-in-parent rotation/translation
        # the IFP format expects. Skipping this step was producing
        # animations that played in MTA but with the character flat on
        # the ground — every bone was rotated by rest^-1.
        rest_quat, rest_mat = _bone_rest_local(armature, bone_name)

        # Collect all keyed timestamps across location/rotation channels.
        times = set()
        for prop_curves in props.values():
            for fc in prop_curves:
                for kp in fc.keyframe_points:
                    times.add(kp.co[0])

        # rotation_euler can store a full 0→2π turn between just two
        # keyframes (start + end). Quaternion conversion of those two
        # endpoints alone is identity → identity, so an IFP keyed only
        # at those frames would have the engine slerp between two
        # identities (no rotation in-game). Densify between every pair
        # of adjacent timestamps so the in-IFP shortest-arc slerp can
        # actually traverse the full turn. 4 splits per interval =
        # max 90° between adjacent IFP keys (slerp short-arc OK up to
        # 180°, picking 90° gives us safety margin).
        if has_euler and len(times) >= 2:
            sorted_times = sorted(times)
            for a, b in zip(sorted_times, sorted_times[1:]):
                step = (b - a) / 4.0
                for k in range(1, 4):
                    times.add(a + step * k)

        # Pose-bone rotation_mode determines how the euler triplet is
        # composed into a quaternion. Default XYZ works for animobj_setup
        # rigs; preserve whatever the user set if they tweaked it.
        euler_rotation_mode = 'XYZ'
        if has_euler and armature is not None:
            pb = armature.pose.bones.get(bone_name)
            if pb is not None and pb.rotation_mode in (
                    'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'):
                euler_rotation_mode = pb.rotation_mode

        src_bone = src_map.get(bone_name, {})
        _prev_rot = None   # previous frame's gta quaternion (hemisphere ref)

        for frame in sorted(times):
            kf = KeyFrame(time=frame / fps)

            if has_rot:
                rot_fcs = props['rotation_quaternion']
                quat = [0.0, 0.0, 0.0, 1.0]  # W, X, Y, Z
                for fc in rot_fcs:
                    quat[fc.array_index] = fc.evaluate(frame)
                bl_quat = mathutils.Quaternion(
                    (quat[0], quat[1], quat[2], quat[3]))
                # Only RE-normalize when the quaternion is genuinely off —
                # i.e. a between-keyframe sample on densified/euler curves
                # (magnitude drifts to 0.7-1.2). At a real keyframe the value
                # is the imported bl_quat, whose magnitude is already the
                # ORIGINAL non-unit ~0.9998 (raw int16/4096 quats aren't unit).
                # Forcing it to 1.0 there shifts it AWAY from the source → the
                # round-trip int16 comes out ±1 LSB wrong. Preserving the
                # native magnitude reproduces the original int16 exactly (the
                # byte-exact snap below also restores vanilla for untouched
                # frames). Hemisphere continuity is handled after the snap.
                _m = bl_quat.magnitude
                if _m > 0 and abs(_m - 1.0) > 5e-3:
                    bl_quat.normalize()
                gta_quat = rest_quat @ bl_quat
                kf.rotation = (
                    gta_quat.x, gta_quat.y, gta_quat.z, gta_quat.w)
            elif has_euler:
                # Sample the euler triplet at this frame, build a
                # quaternion, then apply the rest_quat the same way the
                # quaternion path does. Lets animobj_setup keep its
                # natural 2-keyframe euler representation (0° → 360°)
                # while still producing a valid IFP rotation track.
                euler_vals = [0.0, 0.0, 0.0]
                for fc in props['rotation_euler']:
                    euler_vals[fc.array_index] = fc.evaluate(frame)
                bl_quat = mathutils.Euler(
                    (euler_vals[0], euler_vals[1], euler_vals[2]),
                    euler_rotation_mode).to_quaternion()
                if bl_quat.magnitude > 0:
                    bl_quat.normalize()
                gta_quat = rest_quat @ bl_quat
                kf.rotation = (
                    gta_quat.x, gta_quat.y, gta_quat.z, gta_quat.w)

            if has_loc:
                loc_fcs = props['location']
                loc = [0.0, 0.0, 0.0]
                for fc in loc_fcs:
                    loc[fc.array_index] = fc.evaluate(frame)
                gta_loc = rest_mat @ mathutils.Vector(loc)
                kf.translation = (gta_loc.x, gta_loc.y, gta_loc.z)

            # Byte-exact snap: if this frame's recomputed value still matches
            # the original IFP source (i.e. the user never touched it), emit
            # the source verbatim so quantisation reproduces the original
            # int16 exactly — no ±1 LSB drift. A real edit moves the value
            # well past the tolerance and falls through to the computed one.
            rec = src_bone.get(str(int(round(frame))))
            if rec is not None:
                if (kf.rotation is not None) and len(rec) >= 4:
                    sx, sy, sz, sw = rec[0], rec[1], rec[2], rec[3]
                    cx, cy, cz, cw = kf.rotation
                    dot = cx * sx + cy * sy + cz * sz + cw * sw
                    # q and -q are the same rotation — align hemisphere
                    # before measuring the component distance.
                    if dot < 0.0:
                        sx, sy, sz, sw = -sx, -sy, -sz, -sw
                    if (abs(cx - sx) < 4.9e-4 and abs(cy - sy) < 4.9e-4
                            and abs(cz - sz) < 4.9e-4 and abs(cw - sw) < 4.9e-4):
                        # Write the ORIGINAL-sign source so the emitted int16
                        # bytes match vanilla exactly.
                        kf.rotation = (rec[0], rec[1], rec[2], rec[3])
                if (kf.translation is not None) and len(rec) >= 7:
                    tx, ty, tz = kf.translation
                    if (abs(tx - rec[4]) < 1.96e-3
                            and abs(ty - rec[5]) < 1.96e-3
                            and abs(tz - rec[6]) < 1.96e-3):
                        kf.translation = (rec[4], rec[5], rec[6])

            # Quaternion hemisphere continuity: keep consecutive keyframes on
            # the same side (dot >= 0 with the previous). GTA slerps between
            # keyframes and only takes the SHORT arc when they're same-
            # hemisphere; a sign that flips frame-to-frame — which editing a
            # pose easily introduces on a near-static bone like a clavicle —
            # makes the engine swing the long way → visible jitter. Flipping
            # the sign is free: q and -q are the same rotation. Vanilla anims
            # are already continuous so nothing flips there (byte-exact snap
            # above stays intact); only edit-induced flips get corrected.
            if kf.rotation is not None:
                if _prev_rot is not None:
                    d = (kf.rotation[0] * _prev_rot[0]
                         + kf.rotation[1] * _prev_rot[1]
                         + kf.rotation[2] * _prev_rot[2]
                         + kf.rotation[3] * _prev_rot[3])
                    if d < 0.0:
                        kf.rotation = (-kf.rotation[0], -kf.rotation[1],
                                       -kf.rotation[2], -kf.rotation[3])
                _prev_rot = kf.rotation

            bone.keyframes.append(kf)

        anim.bones.append(bone)

    return anim


def _empty_action_keyframes(action) -> set:
    """All keyframe timestamps in an Empty's Action across all fcurves.

    Empty Actions key ``rotation_quaternion``/``location``/``scale``
    directly on the object — fcurve.data_path is bare (no
    ``pose.bones[...]`` prefix), so we just iterate fcurves and
    collect keyframe X coords.
    """
    times = set()
    for fc in _iter_action_fcurves(action):
        for kp in fc.keyframe_points:
            times.add(kp.co[0])
    return times


def _build_animation_from_empty_rig(action_name: str, root_empty, fps: float,
                                     frame_start: float = 0.0) -> Animation:
    """Build one IFP Animation from a Kams-style Empty rig hierarchy.

    Walks every descendant Empty of *root_empty* that has ``inu_bone_id``
    set, samples its own action's rotation_quaternion + location at
    every keyed frame, and emits an AnimBone track per Empty.

    Unlike the armature path we DON'T apply ``rest_quat @ bl_quat`` —
    Empty's rotation_quaternion is already absolute in parent space,
    which is what IFP encodes natively. This is the main reason the
    Empty flow sidesteps the stepping bug.

    Animated map objects use bone_id=-1 (game matches by frame.name, not
    HAnim ID — verified against vanilla counxref.ifp). Keyframe times
    are shifted so the first key lands at t=0.0 by subtracting
    *frame_start* before dividing by *fps* (vanilla IFPs always start
    at exactly t=0.000000).
    """
    from .animobj_ops import _collect_empty_rig_descendants

    anim = Animation(name=action_name)
    if root_empty is None:
        return anim

    for emp in _collect_empty_rig_descendants(root_empty):
        # Skip the rig root — vanilla animated map objects (verified
        # against derrick01.ifp / counxref.ifp) only put CHILD frames
        # into the IFP bone list. The root is a transform anchor; if
        # it's also animated the whole clump rotates, including any
        # static sibling frames, which is virtually never desired.
        if emp.get('inu_animobj_empty_root'):
            continue
        ad = emp.animation_data
        if ad is None or ad.action is None:
            # Static frame (root with BoneID=0, no animation) — no track needed.
            continue
        action = ad.action

        # Collect timed samples from this Empty's own action.
        times = _empty_action_keyframes(action)
        if not times:
            continue

        # Group fcurves by property — Empty's data_paths are bare.
        prop_fcs = {}
        for fc in _iter_action_fcurves(action):
            prop = fc.data_path.rsplit('.', 1)[-1] if '.' in fc.data_path else fc.data_path
            prop_fcs.setdefault(prop, []).append(fc)

        has_rot = 'rotation_quaternion' in prop_fcs
        has_euler = 'rotation_euler' in prop_fcs and not has_rot
        has_loc = 'location' in prop_fcs

        # Drop dead tracks (all zero/identity) — same logic as armature path.
        if has_loc:
            loc_active = False
            for fc in prop_fcs['location']:
                for kp in fc.keyframe_points:
                    if abs(kp.co[1]) > 1e-5:
                        loc_active = True
                        break
                if loc_active:
                    break
            if not loc_active:
                has_loc = False

        if has_rot:
            rot_active = False
            sample_frames = set()
            for fc in prop_fcs['rotation_quaternion']:
                for kp in fc.keyframe_points:
                    sample_frames.add(kp.co[0])
            for sf in sample_frames:
                q_w, q_x, q_y, q_z = 1.0, 0.0, 0.0, 0.0
                for fc in prop_fcs['rotation_quaternion']:
                    val = fc.evaluate(sf)
                    if fc.array_index == 0: q_w = val
                    elif fc.array_index == 1: q_x = val
                    elif fc.array_index == 2: q_y = val
                    elif fc.array_index == 3: q_z = val
                if (abs(abs(q_w) - 1.0) > 1e-4
                        or abs(q_x) > 1e-4 or abs(q_y) > 1e-4 or abs(q_z) > 1e-4):
                    rot_active = True
                    break
            if not rot_active:
                has_rot = False

        bone = AnimBone(name=emp.name)
        # Animated map objects: bone_id=-1, game matches by frame.name.
        # Verified vs. vanilla counxref.ifp (derrick01, nt_windmill,
        # nt_noddonkbase, oilplodbitbase) — all use bone_id=-1.
        bone.bone_id = -1
        bone.key_type = 0
        if has_rot or has_euler:
            bone.key_type |= HAS_ROT
        if has_loc:
            bone.key_type |= HAS_TRANS
        if not bone.key_type:
            continue

        # Densify euler intervals — same as armature path.
        if has_euler and len(times) >= 2:
            sorted_times = sorted(times)
            for a, b in zip(sorted_times, sorted_times[1:]):
                step = (b - a) / 4.0
                for k in range(1, 4):
                    times.add(a + step * k)

        euler_rotation_mode = emp.rotation_mode if emp.rotation_mode in (
            'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX') else 'XYZ'

        for frame in sorted(times):
            kf = KeyFrame(time=(frame - frame_start) / fps)

            if has_rot:
                quat = [0.0, 0.0, 0.0, 1.0]  # W, X, Y, Z indices
                for fc in prop_fcs['rotation_quaternion']:
                    quat[fc.array_index] = fc.evaluate(frame)
                bl_quat = mathutils.Quaternion(
                    (quat[0], quat[1], quat[2], quat[3]))
                if bl_quat.magnitude > 0:
                    bl_quat.normalize()
                # NO rest_quat composition — Empty's transform is
                # already in parent space, exactly what IFP wants.
                kf.rotation = (bl_quat.x, bl_quat.y, bl_quat.z, bl_quat.w)
            elif has_euler:
                euler_vals = [0.0, 0.0, 0.0]
                for fc in prop_fcs['rotation_euler']:
                    euler_vals[fc.array_index] = fc.evaluate(frame)
                bl_quat = mathutils.Euler(
                    tuple(euler_vals), euler_rotation_mode).to_quaternion()
                if bl_quat.magnitude > 0:
                    bl_quat.normalize()
                kf.rotation = (bl_quat.x, bl_quat.y, bl_quat.z, bl_quat.w)

            if has_loc:
                loc = [0.0, 0.0, 0.0]
                for fc in prop_fcs['location']:
                    loc[fc.array_index] = fc.evaluate(frame)
                kf.translation = (loc[0], loc[1], loc[2])

            bone.keyframes.append(kf)

        anim.bones.append(bone)

    return anim


def build_ifp_from_empty_rig(root_empty, action_name: str = "",
                              package_name: str = "anim",
                              decimate: bool = False,
                              decimate_tol_rot: float = 1e-3,
                              decimate_tol_trans: float = 1e-3) -> IFPFile:
    """Kams-style entry: build a single-Animation IFPFile from a root
    Empty's rig hierarchy.

    The animation name is taken from *action_name* if non-empty, else
    falls back to the pivot's action.name (first pivot in pre-order),
    else to *package_name*. One IFPFile per root rig — separate rigs
    each produce their own .ifp via separate calls.
    """
    fps = 30.0  # GTA/RenderWare IFP native rate — NOT scene fps, else the
    # frame→time→frame round-trip drifts keyframes (root-bone jitter).
    frame_start = float(bpy.context.scene.frame_start)
    # ANP3 is the SA-native compressed IFP format — vanilla map object
    # IFPs (counxref.ifp / airport.ifp / derrick01) all use ANP3.
    # Without this, write_ifp falls back to ANPK (text-chunked) which
    # may load but isn't the canonical SA encoding.
    ifp = IFPFile(name=package_name, source_format='ANP3')

    # Resolve animation name from the first animated pivot if not provided.
    if not action_name:
        from .animobj_ops import _collect_empty_rig_descendants
        for emp in _collect_empty_rig_descendants(root_empty):
            ad = emp.animation_data
            if ad and ad.action:
                action_name = ad.action.name
                break
        if not action_name:
            action_name = package_name

    anim = _build_animation_from_empty_rig(action_name, root_empty, fps, frame_start)
    if anim.bones:
        ifp.animations.append(anim)

    if decimate and ifp.animations:
        decimate_ifp(ifp, decimate_tol_rot, decimate_tol_trans)
    return ifp


def build_ifp_from_actions(actions=None, armature=None,
                            package_name: str = "ped",
                            decimate: bool = False,
                            decimate_tol_rot: float = 1e-3,
                            decimate_tol_trans: float = 1e-3) -> IFPFile:
    """Convert Blender Actions into an IFPFile ready for write_ifp /
    merge_ifp. Separated from the file-writing wrapper so the same
    build step can feed both single-file export and merge-into-pack.

    When ``decimate=True`` is passed, keyframes that lie on a linear
    interpolation between their neighbours within the given tolerance
    are dropped from each bone (see ``core.ifp.decimate_ifp``). First
    and last keyframe of every bone are always preserved.
    """
    if armature is None:
        if bpy.context.active_object and bpy.context.active_object.type == 'ARMATURE':
            armature = bpy.context.active_object

    if actions is None:
        actions = _resolve_actions(actions, armature)

    ifp = IFPFile(name=package_name)
    fps = 30.0  # GTA/RenderWare IFP native rate — NOT scene fps, else the
    # frame→time→frame round-trip drifts keyframes (root-bone jitter).

    for action in actions:
        ifp.animations.append(_build_animation(action, armature, fps))

    if decimate and ifp.animations:
        decimate_ifp(ifp, decimate_tol_rot, decimate_tol_trans)

    return ifp


def audit_ifp(ifp, filepath: str = "", fmt: str = "", target: str = 'SA',
              check_stem: bool = True):
    """Check an IFPFile against what the engine's loader / player does.

    ``core.ifp_lint.check_ifp`` mirrors CAnimManager::LoadAnimFile and the
    CAnimBlend* playback code: an empty sequence, a decreasing time, an
    int16 overflow or a block name that differs from the file name crash
    or hang the game instead of just playing wrong.

    Returns ``(fatal, warnings)`` — ready-to-show strings, also printed to
    the console the way the DFF audits are.
    """
    import os
    from ..core.ifp_lint import check_ifp
    stem = ''
    if check_stem and filepath:
        stem = os.path.splitext(os.path.basename(filepath))[0]
    fatal, warnings = check_ifp(ifp, target=target, fmt=fmt, file_stem=stem)
    for item in fatal:
        print(f"[IFP Export] ИГРА УПАДЁТ: {item}")
    for item in warnings:
        print(f"[IFP Export] {item}")
    return fatal, warnings


def export_ifp(filepath: str, actions=None, armature=None,
               package_name="ped",
               decimate: bool = False,
               decimate_tol_rot: float = 1e-3,
               decimate_tol_trans: float = 1e-3,
               format: str = "ANPK",
               target: str = 'SA'):
    """Export Blender Actions as a brand-new IFP file.

    Each Action becomes one animation in the IFP. Reads keyframes
    from fcurves on pose bones. Overwrites ``filepath`` completely —
    use ``merge_actions_into_ifp`` to edit a pack in-place.

    ``format`` selects the on-disk encoding (``ANPK`` / ``ANP2`` for
    III/VC/SA chunked float32, ``ANP3`` for SA flat int16-compressed);
    ``target`` ('III' / 'VC' / 'SA') the game the file is for.
    """
    ifp = build_ifp_from_actions(
        actions, armature, package_name,
        decimate=decimate,
        decimate_tol_rot=decimate_tol_rot,
        decimate_tol_trans=decimate_tol_trans,
    )
    if not ifp.animations:
        return 0
    audit_ifp(ifp, filepath, fmt=format, target=target)
    return write_ifp(filepath, ifp, format=format, target=target)


def merge_actions_into_ifp(filepath: str, actions=None, armature=None,
                            package_name: str = None,
                            decimate: bool = False,
                            decimate_tol_rot: float = 1e-3,
                            decimate_tol_trans: float = 1e-3,
                            format: str = "",
                            target: str = 'SA'):
    """Merge the given Blender Actions into an existing IFP pack.

    Animations whose name matches an existing entry (case-insensitive)
    overwrite that entry; unknown names are appended. The rest of the
    pack stays intact — this is the flow for patching
    ``ped.ifp`` / ``anim.ifp`` with a single edited animation without
    rewriting all 294 vanilla entries.

    ``format`` is forwarded to the underlying writer; pass empty string
    (default) to preserve the existing pack's on-disk format detected
    by the reader.

    Returns ``(replaced, added)``. When ``filepath`` doesn't exist
    yet, acts like ``export_ifp`` but with the merge-count semantics.
    """
    ifp = build_ifp_from_actions(
        actions, armature, package_name or 'ped',
        decimate=decimate,
        decimate_tol_rot=decimate_tol_rot,
        decimate_tol_trans=decimate_tol_trans,
    )
    if not ifp.animations:
        return 0, 0
    # The block name is only ours to check when the caller overrides it;
    # otherwise the existing pack keeps its own.
    audit_ifp(ifp, filepath, fmt=format, target=target,
              check_stem=bool(package_name))
    return merge_ifp(filepath, ifp.animations,
                     package_name=package_name, format=format,
                     target=target)
