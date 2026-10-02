# INU_tools.ops.ifp_import — Import GTA SA IFP animations into Blender

import ast
import bpy
import mathutils
from ..core.ifp import read_ifp, HAS_ROT, HAS_TRANS
from .. import T
from typing import List, Tuple

# Blender 5.x uses layered actions; 4.x uses action.fcurves directly
_USE_LAYERED = hasattr(bpy.types, 'ActionSlot')

# Cached IFP data (animations stored after import, applied on demand)
_ifp_cache = {}  # name → IFPFile


def _create_action_fcurves(action, armature):
    """Create action and return fcurves container."""
    if not _USE_LAYERED:
        return action.fcurves

    slot = action.slots.new(id_type='OBJECT', name=armature.name)
    layer = action.layers.new(name=action.name)
    strip = layer.strips.new(type='KEYFRAME')
    channelbag = strip.channelbag(slot, ensure=True)
    return channelbag.fcurves


def _reset_pose_bones(armature):
    """Снять позу со всех костей (вернуть в rest).

    При назначении новой анимации Blender НЕ трогает кости, у которых в
    новом экшене нет ключей — они остаются в позе от предыдущей анимации.
    Поэтому, например, применив crouchfire (ключи на нижней части тела), а
    потом standingfire (нижней части тела ключей нет), нижняя часть тела
    остаётся «присевшей». Сбрасываем локальный трансформ каждой pose-кости
    в rest перед применением — тогда не-заключённые кости встают в rest, а
    заключённые перезаписываются ключами нового экшена.
    """
    if not armature or armature.type != 'ARMATURE':
        return
    for pb in armature.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _action_has_fcurves(action):
    """True if ``action`` has any fcurves — works for both legacy and
    layered (4.4+/5.x) actions. Legacy: action.fcurves directly.
    Layered: drill into layers → strips → channelbags."""
    if not _USE_LAYERED:
        return bool(getattr(action, 'fcurves', None)) and len(action.fcurves) > 0
    if getattr(action, 'fcurves', None) and len(action.fcurves) > 0:
        return True
    for layer in getattr(action, 'layers', []):
        for strip in getattr(layer, 'strips', []):
            cbs = getattr(strip, 'channelbags', None)
            if cbs is None:
                cb_call = getattr(strip, 'channelbag', None)
                if callable(cb_call) and getattr(action, 'slots', None):
                    try:
                        cb = cb_call(action.slots[0])
                    except Exception:
                        cb = None
                    cbs = [cb] if cb else []
                else:
                    cbs = []
            for cb in cbs:
                if cb is None:
                    continue
                if len(getattr(cb, 'fcurves', [])) > 0:
                    return True
    return False


def import_ifp(filepath: str, context=None):
    """Import IFP file — parse and cache animations.

    Does NOT apply to armature. Use apply_ifp_action() to apply.
    """
    ifp = read_ifp(filepath)
    if not ifp.animations:
        return []

    # Cache for later application
    _ifp_cache[filepath] = ifp

    # Store animation names as empty actions (for UI listing)
    created = []
    for anim in ifp.animations:
        action = bpy.data.actions.new(name=anim.name)
        action['ifp_source'] = filepath
        action['ifp_package'] = ifp.name
        action['ifp_anim_index'] = ifp.animations.index(anim)
        created.append(action)

    return created


def apply_ifp_action(action_name: str, armature, context=None):
    """Apply a cached IFP animation to an armature.

    Only works on ARMATURE objects. Finds the animation data from cache
    and creates fcurves on the action.
    """
    if not armature or armature.type != 'ARMATURE':
        return False, "Select an armature"

    # Снять остаточную позу от ранее применённой анимации, иначе кости без
    # ключей в новом экшене «залипают» в предыдущей позе (см. _reset_pose_bones).
    _reset_pose_bones(armature)

    # Find the action
    action = bpy.data.actions.get(action_name)
    if not action:
        return False, f"Action '{action_name}' not found"

    # If the action already carries keyframes (user-authored anim from
    # animobj_ops, or a previously-applied IFP action), there is nothing
    # to "import" — just bind it to the armature.
    #
    # IMPORTANT: animobj_ops tags actions with ``ifp_source = action_name``
    # purely as a marker so the IFP exporter picks them up; that value
    # is NOT a filepath. We must short-circuit on fcurves BEFORE trying
    # to read_ifp(), otherwise read_ifp('windmill') raises FileNotFoundError.
    if _action_has_fcurves(action):
        if not armature.animation_data:
            armature.animation_data_create()
        armature.animation_data.action = action
        if _USE_LAYERED and action.slots:
            try:
                armature.animation_data.action_slot = action.slots[0]
            except Exception:
                pass
        return True, f"Applied '{action_name}'"

    filepath = action.get('ifp_source')
    if not filepath:
        return False, "Not an IFP action"

    # The marker set by animobj_ops is the action name, not a path;
    # don't try to open it as a file.
    import os
    if not os.path.isfile(filepath):
        return False, (
            f"Action '{action_name}' has no keyframes and no IFP source "
            f"file to load from (ifp_source='{filepath}')")

    # Get cached IFP data
    ifp = _ifp_cache.get(filepath)
    if not ifp:
        # Try to reload
        ifp = read_ifp(filepath)
        if ifp:
            _ifp_cache[filepath] = ifp
        else:
            return False, f"Cannot read IFP: {filepath}"

    # Find animation by name
    anim = None
    for a in ifp.animations:
        if a.name == action_name:
            anim = a
            break
    if not anim:
        return False, f"Animation '{action_name}' not found in IFP"

    # Create fcurves
    try:
        fc_container = _create_action_fcurves(action, armature)
    except Exception as e:
        return False, f"Error creating fcurves: {e}"

    # IFP keyframe times are seconds. GTA/RenderWare animations run at a
    # FIXED 30 fps — convert time↔frame with 30, NOT the scene fps. Using
    # scene fps (default 24) made the round-trip 30→24→30 non-idempotent:
    # individual keyframes drifted by a frame (e.g. WALK_civi frame 62→63),
    # breaking the uniform 2-frame spacing → the root bone visibly jittered
    # on re-export. 30 keeps keyframes on their exact original frames.
    # (Preview plays at scene fps; set the scene to 30 fps for real-time
    # speed — the exported timing is correct either way.)
    fps = 30.0

    # Pre-build a bone_id → pose_bone map. Custom skins commonly rename
    # the root bone (vanilla 'Normal' becomes 'Root', 'Bip01', etc.) but
    # keep the canonical SA bone_id on each frame's HAnim entry. The
    # DFF importer stashes that id on the data bone as 'bone_id', so we
    # can fall back to id-matching whenever the IFP's bone name doesn't
    # match an armature bone — without this fallback, custom skins lose
    # their root-motion fcurves (id=0), the exported IFP comes out with
    # 31 bones instead of 32, and MTA tends to crash silently inside
    # engineLoadIFP.
    id_to_pose_bone = {}
    for pb in armature.pose.bones:
        db = armature.data.bones.get(pb.name)
        if db is not None and 'bone_id' in db:
            id_to_pose_bone[int(db['bone_id'])] = pb

    # Source-value cache for byte-exact round-trips. We stash the raw IFP
    # rotation/translation (exact int16/4096 & int16/1024) per bone+frame;
    # the exporter re-emits these verbatim for any keyframe the user did
    # NOT edit, so a vanilla-in → export-out is bit-identical instead of
    # drifting ±1 LSB through the float rest-transform round-trip.
    src_map = {}

    for abone in anim.bones:
        bone_name = abone.name
        pose_bone = armature.pose.bones.get(bone_name)
        if not pose_bone:
            for pb in armature.pose.bones:
                if pb.name.lower() == bone_name.lower():
                    pose_bone = pb
                    break
        if not pose_bone and abone.bone_id is not None:
            pose_bone = id_to_pose_bone.get(abone.bone_id)

        if not pose_bone:
            continue

        # Preserve the IFP's original bone name for a faithful round-trip.
        # Custom skins rename the root (vanilla 'Normal' → 'Root'/'Bip01'),
        # so the armature bone we matched by id carries a different name.
        # SA binds by bone_id, not name, so this is cosmetic in-game — but
        # storing the source name lets the exporter write it back verbatim
        # instead of leaking the Blender bone name into the IFP.
        db_orig = armature.data.bones.get(pose_bone.name)
        if db_orig is not None and abone.name and abone.name != pose_bone.name:
            db_orig['gta_ifp_name'] = abone.name

        # Stash the raw source keyframes for the exporter's byte-exact snap.
        sm_bone = src_map.setdefault(pose_bone.name, {})
        for _kf in abone.keyframes:
            _fr = round(_kf.time * fps)
            _rec = [_kf.rotation[0], _kf.rotation[1],
                    _kf.rotation[2], _kf.rotation[3]]
            if (abone.key_type & HAS_TRANS) and _kf.translation is not None:
                _rec.extend((_kf.translation[0], _kf.translation[1],
                             _kf.translation[2]))
            sm_bone[str(_fr)] = _rec

        data_path_rot = f'pose.bones["{pose_bone.name}"].rotation_quaternion'
        data_path_loc = f'pose.bones["{pose_bone.name}"].location'

        try:
            rest_bone = armature.data.bones.get(pose_bone.name)
            if rest_bone:
                rest_mat = rest_bone.matrix_local
                if rest_bone.parent:
                    rest_mat = rest_bone.parent.matrix_local.inverted() @ rest_mat
                rest_quat = rest_mat.to_quaternion()
                rest_inv = rest_quat.inverted()
            else:
                rest_inv = mathutils.Quaternion()

            # Round to integer Blender frames to avoid fractional-frame
            # collisions when scene fps != 30. Без round() ключи ложились
            # на 0.8, 1.6, 2.4 … (при fps=24) — навигация frame-by-frame
            # показывала пропуски а близкие fractional frames могли
            # схлопнуться через keyframe_points.insert overwrite.
            if abone.key_type & HAS_ROT:
                fc_rw = fc_container.new(data_path_rot, index=0)
                fc_rx = fc_container.new(data_path_rot, index=1)
                fc_ry = fc_container.new(data_path_rot, index=2)
                fc_rz = fc_container.new(data_path_rot, index=3)

                for kf in abone.keyframes:
                    frame = round(kf.time * fps)
                    qx, qy, qz, qw = kf.rotation
                    gta_quat = mathutils.Quaternion((qw, qx, qy, qz))
                    bl_quat = rest_inv @ gta_quat
                    fc_rw.keyframe_points.insert(frame, bl_quat.w, options={'FAST'})
                    fc_rx.keyframe_points.insert(frame, bl_quat.x, options={'FAST'})
                    fc_ry.keyframe_points.insert(frame, bl_quat.y, options={'FAST'})
                    fc_rz.keyframe_points.insert(frame, bl_quat.z, options={'FAST'})

                # FAST skipped sorting + handle recompute. GTA/RenderWare
                # interpolate keyframes LINEARLY between samples; Blender
                # inserts them as BEZIER by default, whose auto-handles
                # OVERSHOOT on the near-constant root-bone curves → the
                # animation visibly jitters ('подёргивание', «режет глаз»).
                # Force LINEAR so the preview matches the game and a
                # re-import round-trips cleanly. update() rebuilds handles.
                for _fc in (fc_rw, fc_rx, fc_ry, fc_rz):
                    _n = len(_fc.keyframe_points)
                    if _n:
                        _fc.keyframe_points.foreach_set('interpolation', [1] * _n)  # 1 = LINEAR
                    _fc.update()

            if abone.key_type & HAS_TRANS:
                fc_lx = fc_container.new(data_path_loc, index=0)
                fc_ly = fc_container.new(data_path_loc, index=1)
                fc_lz = fc_container.new(data_path_loc, index=2)

                for kf in abone.keyframes:
                    frame = round(kf.time * fps)
                    tx, ty, tz = kf.translation
                    gta_loc = mathutils.Vector((tx, ty, tz))
                    bl_loc = rest_inv.to_matrix() @ gta_loc
                    fc_lx.keyframe_points.insert(frame, bl_loc.x, options={'FAST'})
                    fc_ly.keyframe_points.insert(frame, bl_loc.y, options={'FAST'})
                    fc_lz.keyframe_points.insert(frame, bl_loc.z, options={'FAST'})

                # LINEAR — same reason as rotation above (no BEZIER jitter).
                for _fc in (fc_lx, fc_ly, fc_lz):
                    _n = len(_fc.keyframe_points)
                    if _n:
                        _fc.keyframe_points.foreach_set('interpolation', [1] * _n)  # 1 = LINEAR
                    _fc.update()
        except Exception:
            continue

    # Persist the source cache on the action for the byte-exact exporter.
    try:
        import json
        action['inu_ifp_src'] = json.dumps(src_map, separators=(',', ':'))
    except Exception:
        pass

    # Assign action to armature
    if not armature.animation_data:
        armature.animation_data_create()
    armature.animation_data.action = action
    if _USE_LAYERED and action.slots:
        try:
            armature.animation_data.action_slot = action.slots[0]
        except Exception:
            pass

    # Подогнать диапазон кадров сцены под этот блок, чтобы таймлайн показывал
    # ровно применённую анимацию (запрос ligabesar). Кадры = время(сек) × fps.
    try:
        frames = [round(kf.time * fps)
                  for b in anim.bones for kf in b.keyframes]
        if frames:
            scn = context.scene
            scn.frame_start = min(frames)
            scn.frame_end = max(frames)
            scn.frame_current = min(frames)
    except Exception:
        pass

    return True, f"Applied '{action_name}' ({len(anim.bones)} bones)"


# ──────────────────────────── live preview ───────────────────────────
#
# Preview an IFP animation on the armature WITHOUT creating/assigning
# a Blender Action. The frame_change_post handler pokes pose bones
# directly on every timeline scrub; when preview is turned off the
# previously-bound action (if any) is restored.
#
# Rationale: browsing 294 vanilla animations via `apply_ifp_action`
# creates 294 Action datablocks and burns the armature's animation_data.
# For a "just show me what this anim looks like" pass, preview is
# cheaper and leaves the Action editor untouched.

_preview_state = {
    'armature_name': None,
    'anim_name': None,
    'saved_action': None,
    'rest_cache': None,  # dict bone_name → (rest_quat_inv, rest_quat_inv_mat)
    'fps': 30.0,
}


def _build_rest_cache(armature):
    """Pre-compute rest-pose inverses per bone for the interpolator.

    Same math as apply_ifp_action: IFP rotations are stored absolute
    in bone-local (relative-to-parent) space, Blender's
    ``pose_bone.rotation_quaternion`` is a DELTA from rest. We subtract
    the rest by pre-multiplying with ``rest_quat.inverted()``.
    """
    cache = {}
    for pb in armature.pose.bones:
        rest_bone = armature.data.bones.get(pb.name)
        if not rest_bone:
            continue
        rest_mat = rest_bone.matrix_local
        if rest_bone.parent:
            rest_mat = rest_bone.parent.matrix_local.inverted() @ rest_mat
        rest_inv = rest_mat.to_quaternion().inverted()
        cache[pb.name] = (rest_inv, rest_inv.to_matrix())
    return cache


def _find_cached_anim(anim_name):
    """Return the cached ``Animation`` object for *anim_name* across all
    previously-imported IFPs, or None."""
    for ifp in _ifp_cache.values():
        for a in ifp.animations:
            if a.name == anim_name:
                return a
    return None


def _sample_anim_keyframe(anim_bone, time_sec):
    """Linearly interpolate this bone's keyframes at ``time_sec``.

    Returns (rotation_xyzw, translation_xyz, has_trans) or None if the
    bone has no keyframes.
    """
    kfs = anim_bone.keyframes
    if not kfs:
        return None

    # ``kf.time`` is canonical seconds (both ANP3 and ANPK readers
    # normalise to seconds). The handler passes
    # ``scene.frame_current / fps`` which is also seconds, so we
    # compare directly with no conversion.
    t = time_sec

    # Find the pair surrounding t. Keyframes are already time-ordered.
    lo = kfs[0]
    hi = kfs[-1]
    for i in range(len(kfs) - 1):
        if kfs[i].time <= t <= kfs[i + 1].time:
            lo, hi = kfs[i], kfs[i + 1]
            break
    else:
        # Outside the range — clamp to endpoints for hold-behaviour.
        if t <= kfs[0].time:
            lo = hi = kfs[0]
        else:
            lo = hi = kfs[-1]

    span = hi.time - lo.time
    alpha = 0.0 if span <= 1e-6 else max(0.0, min(1.0, (t - lo.time) / span))

    rot = tuple(
        lo.rotation[i] + (hi.rotation[i] - lo.rotation[i]) * alpha
        for i in range(4)
    )
    trans = tuple(
        lo.translation[i] + (hi.translation[i] - lo.translation[i]) * alpha
        for i in range(3)
    )
    has_trans = bool(anim_bone.key_type & HAS_TRANS)
    return rot, trans, has_trans


def _ifp_preview_frame_handler(scene, depsgraph=None):
    """Called on frame_change_post while preview is active. Writes
    interpolated pose to the cached armature's pose bones."""
    st = _preview_state
    arm_name = st['armature_name']
    anim_name = st['anim_name']
    if not arm_name or not anim_name:
        return

    armature = bpy.data.objects.get(arm_name)
    if not armature or armature.type != 'ARMATURE':
        return

    anim = _find_cached_anim(anim_name)
    if not anim:
        return

    rest_cache = st['rest_cache']
    if rest_cache is None:
        rest_cache = _build_rest_cache(armature)
        st['rest_cache'] = rest_cache

    fps = st.get('fps') or 30.0
    time_sec = scene.frame_current / fps

    # Same bone_id fallback as apply_ifp_action — keeps the live preview
    # in sync with custom-named root bones (e.g. army.dff calls it 'Root'
    # while vanilla IFP says 'Normal').
    id_to_pose_bone = st.get('id_map')
    if id_to_pose_bone is None:
        id_to_pose_bone = {}
        for pb in armature.pose.bones:
            db = armature.data.bones.get(pb.name)
            if db is not None and 'bone_id' in db:
                id_to_pose_bone[int(db['bone_id'])] = pb
        st['id_map'] = id_to_pose_bone

    for abone in anim.bones:
        pbone = armature.pose.bones.get(abone.name)
        if not pbone and abone.bone_id is not None:
            pbone = id_to_pose_bone.get(abone.bone_id)
        if not pbone:
            continue
        sample = _sample_anim_keyframe(abone, time_sec)
        if not sample:
            continue

        rot_xyzw, trans, has_trans = sample
        rest_inv, rest_inv_mat = rest_cache.get(
            pbone.name,
            (mathutils.Quaternion(), mathutils.Matrix.Identity(3)))

        gta_quat = mathutils.Quaternion(
            (rot_xyzw[3], rot_xyzw[0], rot_xyzw[1], rot_xyzw[2]))
        bl_quat = rest_inv @ gta_quat
        pbone.rotation_mode = 'QUATERNION'
        pbone.rotation_quaternion = bl_quat

        if has_trans:
            gta_loc = mathutils.Vector(trans)
            pbone.location = rest_inv_mat @ gta_loc


def preview_start(armature, anim_name) -> Tuple[bool, str]:
    """Enable live preview: register handler, stash the currently bound
    Action so we can restore it on stop."""
    if not armature or armature.type != 'ARMATURE':
        return False, "Select an armature"

    anim = _find_cached_anim(anim_name)
    if not anim:
        return False, f"Animation '{anim_name}' not in IFP cache"

    _preview_state['armature_name'] = armature.name
    _preview_state['anim_name'] = anim_name
    _preview_state['rest_cache'] = None  # rebuilt on first handler tick
    _preview_state['id_map'] = None      # bone_id → pose_bone, also rebuilt

    # Stash the current action only on first enable so a repeat-toggle
    # doesn't overwrite the saved baseline with None.
    if _preview_state.get('saved_action') is None:
        if armature.animation_data and armature.animation_data.action:
            _preview_state['saved_action'] = armature.animation_data.action
        if armature.animation_data:
            armature.animation_data.action = None

    if _ifp_preview_frame_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_ifp_preview_frame_handler)

    # Kick the handler once so the current frame updates immediately.
    try:
        _ifp_preview_frame_handler(bpy.context.scene)
    except Exception:
        pass

    return True, f"Preview: {anim_name}"


def preview_stop() -> Tuple[bool, str]:
    """Disable preview: unregister handler, restore stashed Action."""
    if _ifp_preview_frame_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_ifp_preview_frame_handler)

    arm = bpy.data.objects.get(_preview_state['armature_name'] or '')
    saved = _preview_state.get('saved_action')
    if arm and saved is not None and arm.animation_data:
        try:
            arm.animation_data.action = saved
        except Exception:
            pass

    _preview_state['armature_name'] = None
    _preview_state['anim_name'] = None
    _preview_state['saved_action'] = None
    _preview_state['rest_cache'] = None
    return True, "Preview stopped"


def preview_is_active() -> bool:
    return bool(_preview_state.get('anim_name'))


# ──────────────────────────── batch import ────────────────────────────

def enumerate_animations(folder: str, name_filter: str = "") -> List[Tuple[str, str]]:
    """Walk `folder` (non-recursive) for *.ifp files and return a flat list
    of (filepath, animation_name) tuples, optionally filtered by prefix
    (case-insensitive, empty = no filter).
    """
    import os
    from ..core.ifp import read_ifp as _read_ifp

    out: List[Tuple[str, str]] = []
    if not folder or not os.path.isdir(folder):
        return out
    flt = (name_filter or "").strip().lower()
    for entry in sorted(os.listdir(folder)):
        if not entry.lower().endswith('.ifp'):
            continue
        path = os.path.join(folder, entry)
        try:
            ifp = _read_ifp(path)
        except Exception as e:
            print(f"[IFP Batch] failed to read {entry}: {e}")
            continue
        for anim in ifp.animations:
            if flt and not anim.name.lower().startswith(flt):
                continue
            out.append((path, anim.name))
    return out


def _action_frame_range(action) -> Tuple[float, float]:
    """Return (start, end) in frames for an action regardless of Blender 4/5."""
    try:
        rng = action.frame_range
        return (float(rng[0]), float(rng[1]))
    except Exception:
        pass
    # Layered actions (Blender 5) — scan fcurves inside channelbags
    start, end = 0.0, 0.0
    if hasattr(action, 'layers'):
        for layer in action.layers:
            for strip in layer.strips:
                for cb in getattr(strip, 'channelbags', []):
                    for fc in cb.fcurves:
                        for kp in fc.keyframe_points:
                            start = min(start, kp.co.x)
                            end = max(end, kp.co.x)
    return start, end


def batch_apply_sequential(armature, anims: List[Tuple[str, str]],
                           *, mode: str = 'NLA',
                           offset_frames: float = 10.0) -> Tuple[int, str]:
    """Apply a list of (file, anim_name) pairs to `armature`.

    mode:
      'ACTIONS' — just create Actions, no NLA arrangement
      'NLA'     — stack sequentially on one NLA track with `offset_frames`
                  between clips (lets you scrub through the whole batch)

    Returns (applied_count, message).
    """
    import bpy

    if not armature or armature.type != 'ARMATURE':
        return 0, "Select an armature"

    applied = 0
    nla_track = None
    cursor = float(bpy.context.scene.frame_start or 0)

    if mode == 'NLA':
        if not armature.animation_data:
            armature.animation_data_create()
        nla_track = armature.animation_data.nla_tracks.new()
        nla_track.name = "IFP Batch"

    for path, anim_name in anims:
        # Ensure the action exists (import_ifp creates empty stubs per anim)
        action = bpy.data.actions.get(anim_name)
        if not action:
            import_ifp(path)
            action = bpy.data.actions.get(anim_name)
            if not action:
                continue

        ok, _msg = apply_ifp_action(anim_name, armature)
        if not ok:
            continue
        applied += 1

        if mode == 'NLA' and nla_track is not None:
            start_f, end_f = _action_frame_range(action)
            length = max(1.0, end_f - start_f)
            try:
                strip = nla_track.strips.new(anim_name, int(cursor), action)
                strip.frame_end = cursor + length
            except Exception as e:
                print(f"[IFP Batch] NLA strip failed for {anim_name}: {e}")
            cursor += length + offset_frames

    if mode == 'NLA' and applied > 0:
        # Clear the direct action so the NLA takes over
        armature.animation_data.action = None
        bpy.context.scene.frame_end = int(cursor)

    return applied, f"Applied {applied} animation(s)"


class GTATOOLS_OT_ifp_batch_import(bpy.types.Operator):
    """Импортировать все *.ifp из папки и уложить анимации на NLA-трек активного armature"""
    bl_idname = "gtatools.ifp_batch_import"
    bl_label = "INU: Batch Import IFP Folder"
    bl_options = {'REGISTER', 'UNDO'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    name_filter: bpy.props.StringProperty(
        name="Name Prefix",
        description=T("Применять только анимации, имя которых начинается с этого префикса (регистронезависимо)"),
        default="",
    )
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('NLA', "NLA Sequential", T("Уложить клипы на один NLA-трек с зазором")),
            ('ACTIONS', "Actions Only", T("Создать Actions, без NLA")),
        ],
        default='NLA',
    )
    offset_frames: bpy.props.FloatProperty(
        name="Gap Between Clips",
        default=10.0, min=0.0, soft_max=100.0,
    )
    start_index: bpy.props.IntProperty(
        name=T("Начальный индекс"),
        description=T("0-based индекс первой анимации в отфильтрованном списке. Удобно бить ped.ifp на порции: 0..49 проверил → 50..99 следующим проходом, не забивая сцену сразу всеми 294 клипами"),
        default=0, min=0,
    )
    count: bpy.props.IntProperty(
        name=T("Сколько применить"),
        description=T("Максимум анимаций для обработки в этом запуске. 0 = все оставшиеся после start_index"),
        default=0, min=0,
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Select an armature as the active object")
            return {'CANCELLED'}

        anims_all = enumerate_animations(self.directory, self.name_filter)
        if not anims_all:
            self.report({'WARNING'}, "No animations matched in folder")
            return {'CANCELLED'}

        # Range slice — enumerate_animations already honours name_filter,
        # so the indices below refer to positions in the FILTERED list.
        # This means the user's mental model is stable: "5..15 of the
        # WALK_* animations" stays consistent regardless of prefix.
        total = len(anims_all)
        start = min(self.start_index, total)
        anims = anims_all[start:]
        if self.count > 0:
            anims = anims[:self.count]

        if not anims:
            self.report({'WARNING'},
                f"Range empty: start={start}, count={self.count}, "
                f"total matched={total}")
            return {'CANCELLED'}

        applied, msg = batch_apply_sequential(
            armature, anims, mode=self.mode, offset_frames=self.offset_frames)
        if applied == 0:
            self.report({'WARNING'}, "No animations applied")
            return {'CANCELLED'}

        end = start + len(anims)
        self.report({'INFO'},
            f"{msg} — {T('диапазон')} {start}..{end} {T('из')} {total}")
        return {'FINISHED'}




# ──────────────────────────── train station markers ───────────────────
# (Lives in this module only for lack of a dedicated path_ui module.)

def _refresh_station_markers(track_obj):
    """Rebuild visible Empty markers for every station point on a track
    curve. The markers are parented to the curve so they follow any
    object-space moves.
    """
    import bpy as _bpy
    from mathutils import Vector
    if track_obj is None or track_obj.type != 'CURVE':
        return 0
    if track_obj.get('path_type') != 'track':
        return 0

    # Wipe old markers under this track
    for child in list(track_obj.children):
        if child.get('station_marker_of') == track_obj.name:
            try:
                _bpy.data.objects.remove(child, do_unlink=True)
            except Exception:
                pass

    try:
        stations = set(ast.literal_eval(track_obj.get('station_indices', '[]')))
    except Exception:
        return 0

    target_collection = (track_obj.users_collection[0]
                         if track_obj.users_collection
                         else _bpy.context.scene.collection)

    idx = 0
    placed = 0
    for spline in track_obj.data.splines:
        for pt in spline.points:
            if idx in stations:
                empty = _bpy.data.objects.new(
                    f"{track_obj.name}_station_{idx}", None)
                empty.empty_display_type = 'SPHERE'
                empty.empty_display_size = 3.0
                empty['station_marker_of'] = track_obj.name
                empty['station_index'] = idx
                target_collection.objects.link(empty)
                # Parent first, clear parent-inverse, THEN write position.
                # pt.co is in the curve's local space, which is exactly what
                # `location` on a child (with identity parent-inverse) wants.
                empty.parent = track_obj
                empty.matrix_parent_inverse.identity()
                empty.location = Vector((pt.co.x, pt.co.y, pt.co.z))
                placed += 1
            idx += 1
    return placed


class GTATOOLS_OT_refresh_station_markers(bpy.types.Operator):
    """Пересоздать видимые Empty-маркеры для каждой станции на активном ж/д пути"""
    bl_idname = "gtatools.refresh_station_markers"
    bl_label = "INU: Refresh Station Markers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'CURVE' and obj.get('path_type') == 'track'

    def execute(self, context):
        placed = _refresh_station_markers(context.active_object)
        self.report({'INFO'}, f"{placed} station marker(s)")
        return {'FINISHED'}




# ──────────────────────────── path-node flags ─────────────────────────

class GTATOOLS_OT_path_node_flag(bpy.types.Operator):
    """Флаги VC или переход на выделенных точках paths.ipl"""
    bl_idname = "gtatools.path_node_flag"
    bl_label = "INU: Set Path Node Flag"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        items=[
            ('TOGGLE_ROADBLOCK', "Toggle Roadblock",
             T("VC: бит 1 реальных флагов — барьер копов")),
            ('CROSSING_ON', T("Пешеходный переход"), T("Колонка Crossing для пешеходных узлов")),
            ('CROSSING_OFF', T("Без перехода"), T("Колонка Crossing для пешеходных узлов")),
            ('TRAFFIC_NONE',   "Clear Traffic Light",
             T("Тип светофора не хранится в paths.ipl")),
            ('TRAFFIC_NORMAL', "Normal Traffic Light",
             T("Тип светофора не хранится в paths.ipl")),
            ('TRAFFIC_RAIL',   "Rail Traffic Light",
             T("Тип светофора не хранится в paths.ipl")),
            ('TRAFFIC_BUS',    "Bus Traffic Light",
             T("Тип светофора не хранится в paths.ipl")),
        ],
        default='TOGGLE_ROADBLOCK',
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'CURVE'
                and obj.get('path_type') == 'path_ipl'
                and context.mode == 'EDIT_CURVE')

    def execute(self, context):
        from ..core.paths import PATH_FLAG_ROADBLOCK
        from .path_ipl_props import ensure_point_slots, _selected
        obj = context.active_object
        if self.action.startswith('TRAFFIC_'):
            self.report({'WARNING'}, T("Тип светофора не хранится в paths.ipl: III/VC определяют его по объектам светофоров"))
            return {'CANCELLED'}
        game = obj.get('pn_game', getattr(context.scene, 'gtatools_game', 'VC'))
        if game == 'SA':
            self.report({'WARNING'}, T("SA игнорирует секцию path в IPL"))
            return {'CANCELLED'}
        if self.action == 'TOGGLE_ROADBLOCK' and (game != 'VC' or obj.get('group_type', 1) == 0):
            self.report({'WARNING'}, T("Roadblock в paths.ipl поддерживается только для авто/лодок VC"))
            return {'CANCELLED'}
        if self.action == 'TOGGLE_ROADBLOCK' and obj.get('external_index', -1) != -1:
            self.report({'WARNING'}, T("VC: Roadblock действует только на отдельные группы с ID -1"))
            return {'CANCELLED'}
        if self.action.startswith('CROSSING_') and obj.get('group_type', 1) != 0:
            self.report({'WARNING'}, T("Crossing поддерживается только для пешеходных узлов"))
            return {'CANCELLED'}
        try:
            pairs = ensure_point_slots(obj)
        except ValueError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}
        touched = 0
        for point, slot in pairs:
            if not _selected(point):
                continue
            if self.action == 'TOGGLE_ROADBLOCK':
                key = f'pn_{slot}_flags'
                obj[key] = int(obj.get(key, 0)) ^ PATH_FLAG_ROADBLOCK
            else:
                obj[f'pn_{slot}_cross'] = int(self.action == 'CROSSING_ON')
            touched += 1
        self.report({'INFO'}, f"{touched} point(s) updated — {self.action}")
        return {'FINISHED'}
