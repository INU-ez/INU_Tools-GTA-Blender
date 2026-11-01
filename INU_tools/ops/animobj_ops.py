# INU_tools.ops.animobj_ops
# "Animated Map Object" workflow — windmills, cranes, wheels of fortune,
# advertising signs, any static map prop with one or more rotating parts.
#
# In GTA SA an animated map object needs three coordinated artefacts:
#   1. DFF with frame hierarchy + HAnim PLG marking each animated bone
#   2. IFP with an Animation track per bone (cyclic rotation, IDE-named)
#   3. IDE 'anim' entry: ID, modelname, txdname, animname, drawdist, flags
#
# Workflow (Kams 3ds Max style, single pivot pipette flow):
#   1. animobj_setup → creates an Empty root with one pivot child;
#      auto-parents active mesh to pivot, co-selected meshes go to root
#      as static parts.
#   2. Eyedropper on root → pick more meshes one by one, choosing target
#      (NEW pivot for another animated part / existing pivot / root).
#   3. animobj_export → writes <base>.dff + <base>.ifp + updates IDE.

import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, EnumProperty
import math
import mathutils
import os

from .. import T
from ..tools.compat import safe_icon, inu_icon


def _iter_action_fcurves(action):
    """Yield every fcurve in an Action across both Blender APIs.

    Pre-4.4 keeps fcurves on the Action root (``action.fcurves``).
    4.4+ moved them into the layered system: Action → slots × layers
    → strips → channelbag(slot) → fcurves. We unify both so callers
    don't have to branch on bpy.app.version every time they want to
    walk keyframes.

    Re-exported from this module because validate_scene.py imports it
    for character-anim quaternion normalisation checks (the IFP-IK
    pipeline keeps its own private copy in ifp_export.py).
    """
    legacy = getattr(action, 'fcurves', None)
    if legacy is not None:
        for fc in legacy:
            yield fc
        return
    slots = getattr(action, 'slots', None)
    layers = getattr(action, 'layers', None)
    if not slots or not layers:
        return
    for layer in layers:
        for strip in getattr(layer, 'strips', []):
            cbag_fn = getattr(strip, 'channelbag', None)
            if cbag_fn is None:
                continue
            for slot in slots:
                cb = cbag_fn(slot)
                if cb is None:
                    continue
                for fc in getattr(cb, 'fcurves', []):
                    yield fc


def _strip_fcurves_at_path(action, data_path):
    """Remove every fcurve in *action* whose data_path == *data_path*.
    Walks both legacy ``Action.fcurves`` (4.x) and the layered
    ``slots × layers → strips → channelbag → fcurves`` tree (4.4+/5.x)."""
    legacy = getattr(action, 'fcurves', None)
    if legacy is not None:
        for fc in list(legacy):
            if fc.data_path == data_path:
                try:
                    legacy.remove(fc)
                except Exception:
                    pass
        return

    slots = getattr(action, 'slots', None)
    layers = getattr(action, 'layers', None)
    if not slots or not layers:
        return
    for layer in layers:
        for strip in getattr(layer, 'strips', []):
            cbag_fn = getattr(strip, 'channelbag', None)
            if cbag_fn is None:
                continue
            for slot in slots:
                cb = cbag_fn(slot)
                if cb is None:
                    continue
                fcurves = getattr(cb, 'fcurves', None)
                if fcurves is None:
                    continue
                for fc in list(fcurves):
                    if fc.data_path == data_path:
                        try:
                            fcurves.remove(fc)
                        except Exception:
                            pass


# ── Combo export ──────────────────────────────────────────────────

class GTATOOLS_OT_animobj_export(bpy.types.Operator):
    """Экспортировать animated map object одним кликом: пишет
    <base>.dff + <base>.ifp в выбранную папку. Опционально дописывает
    или обновляет anim-запись в указанном IDE-файле."""
    bl_idname = "gtatools.animobj_export"
    bl_label = "INU: Export Animated Object"
    bl_options = {'REGISTER'}

    directory: StringProperty(
        name=T("Папка"), subtype='DIR_PATH',
        description=T("Куда положить .dff и .ifp"),
    )
    base_name: StringProperty(
        name=T("Базовое имя"),
        description=T("Имя файлов без расширения (например 'mill')"),
        default="mill",
    )
    txd_name: StringProperty(
        name=T("TXD"),
        description=T("Имя TXD для IDE entry (обычно совпадает с base_name)"),
        default="mill",
    )
    model_id: IntProperty(
        name=T("Model ID"),
        description=T(
            "ID модели для IDE — должен быть свободен в карте.\n"
            "0 = не задан (исправь в Object Properties → INU Tools → Model ID)"),
        default=18000, min=0, max=65535,
    )
    draw_distance: FloatProperty(
        name=T("Draw distance"),
        default=300.0, min=10.0, soft_max=2000.0,
    )
    write_ide: bpy.props.BoolProperty(
        name=T("Дописать IDE entry"),
        description=T("Добавить anim-запись в IDE-файл, заданный в Scene → INU Tools → IDE Path"),
        default=True,
    )
    ifp_name: StringProperty(
        name=T("Имя IFP"),
        description=T(
            "Базовое имя для .ifp (без расширения). Пусто = взять "
            "из «Базовое имя». Можно ввести общее имя типа "
            "'myhood_anims' чтобы складывать анимации мельницы, "
            "крана и флюгера в один файл"),
        default="",
    )
    existing_ifp_path: StringProperty(
        name=T("Существующий IFP (опционально)"),
        description=T(
            "Указать конкретный .ifp файл куда дополнить анимацию. "
            "Когда задан — игнорируется «Папка» и «Имя IFP», анимация "
            "пишется СЮДА. Удобно для merge'а в <game>/anim/myhood.ifp "
            "или подобных общих файлов вне папки экспорта DFF"),
        default="",
        subtype='FILE_PATH',
    )
    ifp_mode: EnumProperty(
        name=T("Режим IFP"),
        description=T(
            "Что делать если такой .ifp уже существует на диске"),
        items=[
            ('NEW',    T("Новый"),
             T("Перезаписать файл — старые анимации удаляются")),
            ('APPEND', T("Дополнить"),
             T("Подгрузить существующий, добавить новые анимации, "
               "заменить с тем же именем")),
            ('UPDATE', T("Обновить совпадения"),
             T("Подгрузить существующий, заменить ТОЛЬКО анимации "
               "с совпадающим именем, новые НЕ добавлять")),
        ],
        default='APPEND',
    )
    ifp_format: EnumProperty(
        name=T("Формат IFP"),
        items=[
            ('ANPK', "ANPK / ANP2 (III, VC, SA)", ""),
            ('ANP3', "ANP3 (SA compressed)", ""),
        ],
        default='ANPK',
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        # Resolve the rig the same way execute() does so invoke pre-fill
        # stays consistent with what gets used at write time.
        active = context.active_object
        root = _find_animobj_empty_root(active)
        if root is None:
            root = _animobj_find_first_rig()

        # Pre-fill names from the first pivot's Action — that becomes
        # the IFP animation name AND a sensible default base filename.
        first_mesh = None
        if root is not None:
            for emp in _collect_empty_rig_descendants(root):
                ad = emp.animation_data
                if ad and ad.action:
                    self.base_name = ad.action.name
                    self.txd_name = ad.action.name
                    break
            # First mesh found anywhere in the rig hierarchy provides
            # Model ID / Draw Distance / TXD Name defaults via inu props.
            stack = [root]
            while stack and first_mesh is None:
                n = stack.pop(0)
                for ch in n.children:
                    if ch.type == 'MESH':
                        first_mesh = ch
                        break
                    stack.append(ch)
            if first_mesh is not None:
                inu = getattr(first_mesh, 'inu', None)
                if inu is not None:
                    self.model_id = inu.model_id
                    self.draw_distance = inu.draw_distance
                    if inu.txd_name:
                        self.txd_name = inu.txd_name

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        col = self.layout.column()

        # Show which Action(s) will be exported. For Empty rigs every
        # animated pivot contributes one IFP bone track, all under a
        # single Animation named after the first pivot's Action.
        active = context.active_object
        root = _find_animobj_empty_root(active)
        if root is None:
            root = _animobj_find_first_rig()
        anim_name = None
        pivot_count = 0
        if root is not None:
            for emp in _collect_empty_rig_descendants(root):
                ad = emp.animation_data
                if ad and ad.action:
                    if anim_name is None:
                        anim_name = ad.action.name
                    pivot_count += 1
        if anim_name:
            label = (f"{T('Анимация')}: {anim_name}"
                     + (f"  ({pivot_count} pivots)" if pivot_count > 1 else ""))
            col.label(text=label, **inu_icon(safe_icon('ACTION')))
        else:
            col.label(
                text=T("Нет анимированных pivot'ов — IFP будет пустой"),
                **inu_icon(safe_icon('ERROR')))

        col.separator()
        col.prop(self, "directory")
        col.prop(self, "base_name")
        col.prop(self, "txd_name")
        col.prop(self, "model_id")
        if self.model_id == 0:
            col.label(
                text=T("Model ID = 0 — задай в Object Properties → "
                       "INU Tools → Model ID"),
                **inu_icon(safe_icon('ERROR')))
        col.prop(self, "draw_distance")

        # ── IFP file naming + write strategy ──
        # Most common pattern: artist exports several rigs (mill +
        # crane + flag) over time but wants them in a single shared
        # myhood_anims.ifp. Default mode APPEND lets every
        # subsequent export grow the file safely.
        ifp_box = col.box()
        ifp_box.label(text=T("IFP файл"), **inu_icon(safe_icon('ACTION')))

        # Explicit target file (file-picker) — overrides directory + ifp_name
        # when set. Lets user point at an existing .ifp outside the DFF
        # export folder (e.g. <game>/anim/myhood.ifp).
        ifp_box.prop(self, "existing_ifp_path", text=T("Дополнить файл"))

        explicit = bpy.path.abspath(self.existing_ifp_path).strip()
        if explicit:
            ifp_box.label(
                text=f"→ {os.path.basename(explicit)}",
                **inu_icon(safe_icon('FILE_BLANK')))
        else:
            # Standard path — directory + ifp_name (or base_name).
            resolved = (self.ifp_name.strip() or self.base_name.strip()
                        or "<пусто>")
            ifp_box.prop(self, "ifp_name", text=T("Имя"))
            ifp_box.label(
                text=f"→ {resolved}.ifp", **inu_icon(safe_icon('FILE_BLANK')))
        ifp_box.prop(self, "ifp_mode", text=T("Режим"))
        ifp_box.prop(self, "ifp_format")

        col.prop(self, "write_ide")
        if self.write_ide:
            ide_path = getattr(context.scene.inu_settings, 'gtatools_ide_path', '')
            if ide_path:
                col.label(text=f"IDE: {ide_path}", **inu_icon(safe_icon('TEXT')))
            else:
                col.label(text=T(
                    "Scene → INU Tools → IDE Path не задан — "
                    "anim-запись не будет дописана"),
                    **inu_icon(safe_icon('ERROR')))

    def execute(self, context):
        if not self.directory or not os.path.isdir(self.directory):
            self.report({'ERROR'}, T("Укажите существующую папку"))
            return {'CANCELLED'}
        base = self.base_name.strip()
        if not base:
            self.report({'ERROR'}, T("Базовое имя не может быть пустым"))
            return {'CANCELLED'}

        # Locate the Empty rig: prefer one in the active object's
        # ancestor chain, fall back to any rig present in the scene.
        active = context.active_object
        empty_root = _find_animobj_empty_root(active) if active else None
        if empty_root is None:
            empty_root = _animobj_find_first_rig()
        if empty_root is None:
            self.report({'ERROR'},
                        T("В сцене нет Empty-rig'а — сначала Setup"))
            return {'CANCELLED'}
        return self._execute_empty_rig(context, empty_root, base)

    def _execute_empty_rig(self, context, root_empty, base):
        """Export path for Kams-style Empty rig.

        Collects: root Empty + all descendant Empties + all mesh children.
        Writes DFF via gtatools.export_dff (the hierarchy path already
        handles Empty parents and our `_build_frame` change emits HAnim).
        Writes IFP via build_ifp_from_empty_rig.

        IFP destination resolution:
        * `existing_ifp_path` set → use it verbatim (lets the user point at
          `<game>/anim/myhood.ifp` outside the DFF export folder)
        * otherwise → `<directory>/<ifp_name or base>.ifp`
        """
        ifp_basename = self.ifp_name.strip() or base
        dff_path = os.path.join(self.directory, f"{base}.dff")
        explicit_ifp = bpy.path.abspath(self.existing_ifp_path).strip()
        if explicit_ifp:
            ifp_path = explicit_ifp
            # Use the existing file's basename for status messages and
            # internal package name fallback.
            ifp_basename = os.path.splitext(os.path.basename(ifp_path))[0]
        else:
            ifp_path = os.path.join(self.directory, f"{ifp_basename}.ifp")

        # Collect rig + meshes for the DFF selection.
        rig_objs = [root_empty]
        stack = [root_empty]
        while stack:
            n = stack.pop(0)
            for ch in n.children:
                rig_objs.append(ch)
                stack.append(ch)

        # Rebuild any auto-mode pivots so a slider drift doesn't ship
        # stale keys. Mirrors the armature path's _rebuild_animobj_action.
        for o in rig_objs:
            if o.type == 'EMPTY' and o.get('inu_animobj_empty_pivot'):
                try:
                    _rebuild_animobj_empty_action(o)
                except Exception as ex:
                    print(f"[INU] empty rig rebuild skipped on {o.name}: {ex}")

        # Backfill `dff_frame_write_name` flag on every Empty in the rig.
        # Earlier versions of `animobj_setup` didn't set this, so DFFs
        # exported then shipped with empty frame names — engine couldn't
        # match the IFP track to the pivot frame in some builds. Set the
        # flag now so re-exports from old rigs pick up named frames
        # without the user having to recreate the hierarchy.
        for o in rig_objs:
            if o.type in {'EMPTY', 'MESH'} and not o.get('dff_frame_write_name'):
                o['dff_frame_write_name'] = True

        # DFF export — select rig + meshes, reuse the file operator.
        for o in bpy.data.objects:
            o.select_set(False)
        for o in rig_objs:
            o.select_set(True)
        context.view_layer.objects.active = root_empty
        try:
            bpy.ops.gtatools.export_dff(
                'EXEC_DEFAULT', filepath=dff_path)
        except Exception as ex:
            self.report({'ERROR'}, f"DFF: {ex}")
            return {'CANCELLED'}

        # IFP export — build a single-Animation pack from the rig.
        ifp_msg = ""
        try:
            from .ifp_export import build_ifp_from_empty_rig
            from ..core.ifp import write_ifp, read_ifp, IFPFile
            # Animation name MUST equal the IDE entry's anim_file
            # (which is `base`, the model name) — that's how
            # CClumpAnimMgr finds the track inside the IFP pack.
            # Falling back to Action.name would break game lookup if the
            # user named the Action with non-ASCII chars (Cyrillic
            # action.name → 8 `?` in ANP3 header → game can't match).
            new_ifp = build_ifp_from_empty_rig(
                root_empty, action_name=base, package_name=ifp_basename)
            if not new_ifp.animations:
                self.report({'WARNING'},
                            T("Empty rig: ни один pivot не дал ключей — IFP не записан"))
            else:
                target_ifp = new_ifp
                file_exists = os.path.isfile(ifp_path)
                if file_exists and self.ifp_mode in ('APPEND', 'UPDATE'):
                    try:
                        existing = read_ifp(ifp_path)
                    except Exception as ex:
                        self.report({'WARNING'},
                                    f"IFP read failed, {T('перезаписываю')}: {ex}")
                        existing = IFPFile(name=ifp_basename)
                    by_name = {a.name: a for a in existing.animations}
                    if self.ifp_mode == 'APPEND':
                        for a in new_ifp.animations:
                            by_name[a.name] = a
                    else:
                        for a in new_ifp.animations:
                            if a.name in by_name:
                                by_name[a.name] = a
                    target_ifp = IFPFile(
                        name=existing.name or ifp_basename,
                        animations=list(by_name.values()),
                        source_format=existing.source_format,
                    )
                write_ifp(ifp_path, target_ifp, format=self.ifp_format)
                ifp_msg = f", IFP+{len(new_ifp.animations)}"
        except Exception as ex:
            self.report({'ERROR'}, f"IFP: {ex}")
            return {'CANCELLED'}

        # IDE entry — same logic as armature path.
        ide_msg = ""
        if self.write_ide and self.model_id == 0:
            self.report({'WARNING'},
                        T("Model ID = 0 — IDE entry пропущена"))
        elif self.write_ide:
            ide_path = getattr(context.scene.inu_settings, 'gtatools_ide_path', '')
            ide_path = bpy.path.abspath(ide_path) if ide_path else ""
            if ide_path and os.path.isfile(ide_path):
                try:
                    from ..core.ide import read_ide, write_ide, IdeAnim
                    ide = read_ide(ide_path)
                    anim_action_name = base
                    new_entry = IdeAnim(
                        model_id=self.model_id,
                        model_name=base,
                        txd_name=self.txd_name or base,
                        anim_file=anim_action_name,
                        draw_distance=self.draw_distance,
                        flags=0,
                    )
                    for i, a in enumerate(ide.anims):
                        if a.model_id == self.model_id:
                            ide.anims[i] = new_entry
                            break
                    else:
                        ide.anims.append(new_entry)
                    from ..core import game_versions as gv
                    write_ide(ide_path, ide,
                              game=gv.game_of_scene(context.scene))
                    ide_msg = ", IDE+1"
                except Exception as ex:
                    self.report({'WARNING'}, f"IDE: {ex}")
            else:
                self.report({'WARNING'},
                            T("IDE path не задан — anim-запись пропущена"))

        self.report({'INFO'},
                    f"[Empty rig] {base}.dff + {ifp_basename}.ifp{ifp_msg}{ide_msg}")
        return {'FINISHED'}


# ══════════════════════════════════════════════════════════════════
# ── Empty-based rig (Kams-style) ──────────────────────────────────
# Parallel workflow to the armature-based one above. Mirrors Kam's
# 3ds Max approach: dummies (Helper objects = Blender Empty) carry
# the animation, meshes are parented to them without any skin. The
# IFP exporter samples each animated Empty's transform directly,
# which sidesteps the rest_quat / pose-bone path that produced the
# stepping bug in the armature workflow.
#
# Scene layout after `animobj_setup_empty`:
#     <base>_root        Empty   inu_bone_id=0   (BoneID=0, no anim)
#     └── <base>_pivot   Empty   inu_bone_id=1   (BoneID=1, cyclic rotation)
# The user parents:
#   - the static mesh (base, frame) under <base>_root
#   - the moving mesh (blades, arm) under <base>_pivot
# IFP export walks selected rig, emits one ANP3 Object track per Empty
# with inu_bone_id ≠ 0 (root is RT-only — no rotation track needed).
# ══════════════════════════════════════════════════════════════════


def _rebuild_animobj_empty_action(empty_obj):
    """Idempotent rewrite of the pivot Empty's Action.

    Two keyframes only: 0° at frame 1, ``turns_per_cycle × 360°`` at
    duration_end. The IFP densifier handles the quaternion slerp
    between them on its side; in-Blender we rely on euler linear
    interpolation to actually traverse the full rotation.

    *Critically uses ``rotation_euler``, not ``rotation_quaternion``.*
    A full 360° turn keyed as quaternions has q_start = (1,0,0,0) and
    q_end = (-1,0,0,0), which Blender's shortest-arc slerp treats as
    the same orientation → ZERO rotation between the keys. Mirrors the
    armature-flow which has used euler since day one for the same
    reason.

    Uses ``Object.keyframe_insert()`` so it works on both legacy and
    layered (4.4+/5.x) Action storage.
    """
    if empty_obj is None or empty_obj.type != 'EMPTY':
        return
    props = empty_obj.inu_animobj_empty_props
    # Export calls this for every pivot, including hand-authored Actions.
    # Manual mode must preserve the user's curves and rotation order.
    if not props.auto_mode:
        return

    ad = empty_obj.animation_data
    if ad is None:
        ad = empty_obj.animation_data_create()
    if ad.action is None:
        action = bpy.data.actions.new(name=f"{empty_obj.name}_anim")
        ad.action = action
    else:
        action = ad.action

    # Use XYZ euler, identical to the armature path's choice. The IFP
    # exporter's empty-rig sampler handles euler tracks via its built-in
    # densifier (4 intermediate samples per segment) so the in-game
    # slerp can traverse the full 360° without snapping.
    empty_obj.rotation_mode = 'XYZ'

    _strip_fcurves_at_path(action, 'rotation_quaternion')
    _strip_fcurves_at_path(action, 'rotation_euler')

    sign = -1.0 if props.reverse else 1.0
    total_radians = sign * props.turns_per_cycle * 2.0 * math.pi
    axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[props.axis]

    duration = max(2, props.duration_frames)

    # Start key: 0° on every axis.
    empty_obj.rotation_euler = (0.0, 0.0, 0.0)
    empty_obj.keyframe_insert(
        data_path='rotation_euler', frame=1, group=empty_obj.name)

    # End key: full rotation on the chosen axis. Linear interp between
    # the two euler keyframes actually traverses the whole 0..2π range
    # (no shortest-arc collapse like quaternions).
    end_rot = [0.0, 0.0, 0.0]
    end_rot[axis_idx] = total_radians
    empty_obj.rotation_euler = tuple(end_rot)
    empty_obj.keyframe_insert(
        data_path='rotation_euler', frame=float(duration),
        group=empty_obj.name)

    # Reset viewport pose to start so the user doesn't see end-frame
    # rotation when stepping off the timeline.
    empty_obj.rotation_euler = (0.0, 0.0, 0.0)

    # Force LINEAR interpolation — default Bezier ease-in/out would
    # make the cycle stutter at boundaries.
    _set_keyframes_linear_at_path(action, 'rotation_euler')


def _set_keyframes_linear_at_path(action, data_path):
    """Set every keyframe on *data_path* fcurves to LINEAR.

    Walks legacy and layered Action storage — mirror of
    ``_strip_fcurves_at_path`` but instead of removing the fcurve it
    sets each keyframe_point's interpolation.
    """
    def _apply(fcurves):
        for fc in fcurves:
            if fc.data_path != data_path:
                continue
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
            fc.update()

    legacy = getattr(action, 'fcurves', None)
    if legacy is not None:
        _apply(legacy)
        return
    slots = getattr(action, 'slots', None)
    layers = getattr(action, 'layers', None)
    if not slots or not layers:
        return
    for layer in layers:
        for strip in getattr(layer, 'strips', []):
            cbag_fn = getattr(strip, 'channelbag', None)
            if cbag_fn is None:
                continue
            for slot in slots:
                cb = cbag_fn(slot)
                if cb is None:
                    continue
                fcurves = getattr(cb, 'fcurves', None)
                if fcurves is not None:
                    _apply(fcurves)


def _on_animobj_empty_prop_update(self, context):
    obj = self.id_data
    if obj is None or not obj.get('inu_animobj_empty_pivot'):
        return
    if not self.auto_mode:
        return
    _rebuild_animobj_empty_action(obj)
    scene = context.scene
    scene.frame_start = 1
    scene.frame_end = max(2, self.duration_frames)


def _on_animobj_empty_auto_mode_toggle(self, context):
    obj = self.id_data
    if obj is None or not obj.get('inu_animobj_empty_pivot'):
        return
    if self.auto_mode:
        _rebuild_animobj_empty_action(obj)
        scene = context.scene
        scene.frame_start = 1
        scene.frame_end = max(2, self.duration_frames)


class INUAnimObjEmptyProps(bpy.types.PropertyGroup):
    """Per-pivot Empty settings — mirrors INUAnimObjProps but lives on
    a pivot Empty instead of an armature Object. Same UX: slider-driven
    cyclic rotation, Auto/Manual toggle."""
    auto_mode: bpy.props.BoolProperty(
        name=T("Auto"),
        description=T(
            "Auto: ползунки сами пересчитывают keyframes цикла.\n"
            "Manual: ползунки заморожены, ты сам ставишь keyframes"),
        default=True,
        update=_on_animobj_empty_auto_mode_toggle,
    )
    axis: EnumProperty(
        name=T("Ось"),
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z',
        update=_on_animobj_empty_prop_update,
    )
    reverse: bpy.props.BoolProperty(
        name=T("В обратную сторону"),
        default=False,
        update=_on_animobj_empty_prop_update,
    )
    turns_per_cycle: IntProperty(
        name=T("Оборотов за цикл"),
        default=1, min=1, soft_max=20,
        update=_on_animobj_empty_prop_update,
    )
    duration_frames: IntProperty(
        name=T("Длительность (кадров)"),
        default=60, min=2, soft_max=600,
        update=_on_animobj_empty_prop_update,
    )


def _find_animobj_empty_root(obj):
    """Walk up from *obj* to find the rig's root Empty (the one with
    inu_animobj_empty_root flag). Returns the root or None.
    Used by validate / export to identify the rig regardless of which
    Empty / mesh inside it is currently selected."""
    while obj is not None:
        if obj.type == 'EMPTY' and obj.get('inu_animobj_empty_root'):
            return obj
        obj = obj.parent
    return None


def _animobj_frame_name(obj):
    """RW name, independent of Blender's automatic .001 import suffix."""
    source_name = obj.get('inu_animobj_frame_name')
    if source_name and obj.name == obj.get('inu_animobj_import_name'):
        return source_name
    return obj.name


def _collect_empty_rig_descendants(root):
    """Yield every descendant of *root* that has inu_bone_id set, in
    pre-order (root first). The IFP exporter walks this list to build
    AnimBone tracks; the DFF exporter to attach HAnim PLG."""
    if root is None:
        return
    stack = [root]
    while stack:
        node = stack.pop(0)
        if node.type == 'EMPTY' and 'inu_bone_id' in node:
            yield node
        stack.extend(list(node.children))


class GTATOOLS_OT_animobj_validate(bpy.types.Operator):
    """Проверить Empty-rig: есть ли root + pivot, корректные BoneID,
    Action на pivot, припарентенные меши. Сообщает первую ошибку."""
    bl_idname = "gtatools.animobj_validate"
    bl_label = "INU: Animated Object Validate (Empty rig)"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        root = _find_animobj_empty_root(context.active_object)
        if root is None:
            self.report({'ERROR'},
                        T("Не нашли root Empty — запустите Setup (Empty rig)"))
            return {'CANCELLED'}

        descendants = list(_collect_empty_rig_descendants(root))
        if len(descendants) < 2:
            self.report({'ERROR'},
                        T("Rig содержит только root — нужен хотя бы один pivot Empty"))
            return {'CANCELLED'}

        # Pivot must have an animation_data + action with keyframes.
        pivots_with_anim = []
        for emp in descendants:
            if emp is root:
                continue
            ad = emp.animation_data
            if ad and ad.action:
                pivots_with_anim.append(emp)

        if not pivots_with_anim:
            self.report({'ERROR'},
                        T("Ни один pivot не имеет Action с keyframes"))
            return {'CANCELLED'}

        # Meshes should be parented to one of the rig empties — at
        # least one direct mesh child somewhere is expected.
        mesh_children = []
        for emp in descendants:
            for ch in emp.children:
                if ch.type == 'MESH':
                    mesh_children.append((emp, ch))
        if not mesh_children:
            self.report({'WARNING'},
                        T("В rig нет меша — припарентите DFF меш к root или pivot"))
            return {'FINISHED'}

        self.report({'INFO'},
                    T("OK: {0} Empties, {1} с анимацией, {2} меш(а)").format(
                        len(descendants), len(pivots_with_anim), len(mesh_children)))
        return {'FINISHED'}


# ── Post-setup parenting helpers ──────────────────────────────────
# Solves the typical «animation doesn't work» symptom: rig was built
# but user's mesh sits next to it instead of inside it. These two
# operators move the selected mesh under root (static) or pivot
# (animated) of the nearest Empty-rig in the scene.

def _animobj_find_first_rig():
    """Return the first inu_animobj_empty_root Empty in bpy.data, or None.
    Used when the operator is run from a mesh that isn't already inside
    a rig — we pick whatever rig exists rather than asking the user."""
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.get('inu_animobj_empty_root'):
            return o
    return None


def _animobj_pivot_for_root(root):
    """Find the first pivot Empty under *root*. Returns None if none."""
    for ch in root.children:
        if ch.type == 'EMPTY' and ch.get('inu_animobj_empty_pivot'):
            return ch
    return None


def _parent_keep_transform(child, parent):
    """Parent *child* to *parent* preserving its current world transform.
    Skips re-parenting to the same target so undo history stays clean."""
    if child.parent is parent:
        return False
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = mw
    return True


class GTATOOLS_OT_animobj_parent_to_pivot(bpy.types.Operator):
    """Припарентить выделенные меши к pivot Empty-rig'а — меш будет
    крутиться вместе с rig'ом. Если rig'ов несколько, используется
    тот в иерархии которого уже находится активный объект."""
    bl_idname = "gtatools.animobj_parent_to_pivot"
    bl_label = "INU: Parent Selected Meshes to Rig Pivot"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        # Look for a rig in the active object's ancestor chain first
        # (lets the user disambiguate by picking a sibling Empty); fall
        # back to whatever rig exists in the scene.
        rig = _find_animobj_empty_root(context.active_object)
        if rig is None:
            rig = _animobj_find_first_rig()
        if rig is None:
            self.report({'ERROR'},
                        T("В сцене нет Empty-rig'а — сначала Setup (Empty)"))
            return {'CANCELLED'}
        pivot = _animobj_pivot_for_root(rig)
        if pivot is None:
            self.report({'ERROR'}, T("У rig'а нет pivot Empty"))
            return {'CANCELLED'}

        n = 0
        for o in context.selected_objects:
            if o.type == 'MESH' and _parent_keep_transform(o, pivot):
                n += 1
        self.report({'INFO'},
                    f"{n} {T('меш(а) припарентено к')} {pivot.name}")
        return {'FINISHED'}


def _create_pivot_under_root(root, axis: str = 'Z', turns: int = 1,
                              duration: int = 60, reverse: bool = False,
                              name_suffix: str = ''):
    """Spawn a new pivot Empty as a child of *root* and wire up its
    Action. Used by both the explicit Add Pivot operator and the
    eyedropper auto-attach when target mode is NEW_PIVOT.

    Returns the new pivot Empty. BoneID is auto-allocated (max existing
    + 1) so multiple pivots in the same rig never collide.
    """
    existing_ids = []
    for emp in _collect_empty_rig_descendants(root):
        existing_ids.append(int(emp.get('inu_bone_id', 0)))
    next_bone_id = max(existing_ids + [0]) + 1

    rig_base = root.name
    if rig_base.endswith('_root'):
        rig_base = rig_base[:-5]

    suffix = name_suffix or f"pivot{next_bone_id}"
    new_name = f"{rig_base}_{suffix}"
    if new_name in bpy.data.objects:
        counter = 2
        while f"{new_name}.{counter:03d}" in bpy.data.objects:
            counter += 1
        new_name = f"{new_name}.{counter:03d}"

    pivot = bpy.data.objects.new(new_name, None)
    pivot.empty_display_type = 'SPHERE'
    pivot.empty_display_size = 0.3
    pivot.parent = root
    pivot['inu_animobj_empty_pivot'] = True
    pivot['inu_bone_id'] = next_bone_id
    pivot['inu_animobj_action_name'] = suffix
    pivot['dff_frame_write_name'] = True
    for col in root.users_collection:
        col.objects.link(pivot)

    props = pivot.inu_animobj_empty_props
    props.axis = axis
    props.turns_per_cycle = turns
    props.duration_frames = duration
    props.reverse = reverse
    props.auto_mode = True

    ad = pivot.animation_data_create()
    action = bpy.data.actions.new(name=suffix)
    ad.action = action
    _rebuild_animobj_empty_action(pivot)

    return pivot


def _create_default_rig(context, base_name='animobj'):
    """Spawn a fresh root + pivot Empty pair at the world origin (or
    at the active object's location if any). Returns the root Empty.

    Used by the scene-level pipette: when the user picks the first
    mesh and no rig exists yet, we silently build one — so the user
    never has to click an explicit «Setup» button. Matches the «just
    works» philosophy of the whole pipette workflow.
    """
    active = context.active_object
    origin = (active.location.copy() if active
              else mathutils.Vector((0.0, 0.0, 0.0)))

    target_coll = context.collection
    if active and active.users_collection:
        target_coll = active.users_collection[0]

    root_name = f"{base_name}_root"
    if root_name in bpy.data.objects:
        counter = 2
        while f"{root_name}.{counter:03d}" in bpy.data.objects:
            counter += 1
        root_name = f"{root_name}.{counter:03d}"

    root = bpy.data.objects.new(root_name, None)
    root.empty_display_type = 'ARROWS'
    root.empty_display_size = 0.5
    root.location = origin
    root['inu_animobj_empty_root'] = True
    root['inu_bone_id'] = 0
    root['dff_frame_write_name'] = True
    target_coll.objects.link(root)
    return root


def attach_mesh_to_rig(context, mesh, target: str = 'NEW_PIVOT'):
    """Attach *mesh* to an animobj rig in the scene, creating the rig
    on the fly if none exists. Used by the scene-level pipette so the
    user never has to «set up» anything — every pick either grows the
    existing rig or starts a new one.

    *target* ∈ {'NEW_PIVOT', 'PIVOT', 'ROOT'}:
      * NEW_PIVOT — create a fresh pivot with its own Action, attach
        mesh under it.
      * PIVOT     — attach to the first existing pivot (or create one
        if there isn't any yet).
      * ROOT      — attach as a static part directly under root.

    **Static-base auto-adopt**: when this call CREATES the rig (none
    existed before), the context's active mesh — if any, and if it
    isn't the picked mesh itself — is treated as the static base and
    parented to the new root. Matches the user's mental model «у меня
    уже выделена статичная часть, пипеткой я указываю что будет
    крутиться» without an extra step.

    Returns a tuple (rig_root, target_empty, created_rig: bool).
    """
    rig = _animobj_find_first_rig()
    created_rig = False
    if rig is None:
        # Name the rig after the user's selected static base if there
        # is one — that's a more identifying name than the rotating
        # part. Falls back to picked_mesh.name then "animobj".
        active = context.active_object
        base = 'animobj'
        if (active is not None and active.type == 'MESH'
                and active is not mesh):
            base = active.name
        elif mesh is not None:
            base = mesh.name
        rig = _create_default_rig(context, base_name=base)
        created_rig = True
        # Adopt the active mesh as static base, but only if it's
        # currently a top-level object (no parent / no existing rig
        # ancestor). Avoids yanking it out of an unrelated hierarchy.
        if (active is not None and active.type == 'MESH'
                and active is not mesh
                and active.parent is None
                and _find_animobj_empty_root(active) is None):
            _parent_keep_transform(active, rig)

    if target == 'ROOT':
        attach_target = rig
    elif target == 'NEW_PIVOT':
        attach_target = _create_pivot_under_root(rig)
    else:  # 'PIVOT'
        attach_target = None
        for ch in rig.children:
            if ch.type == 'EMPTY' and ch.get('inu_animobj_empty_pivot'):
                attach_target = ch
                break
        if attach_target is None:
            # First-time pick with target=PIVOT and no pivots yet —
            # create one. Otherwise the mesh would silently go to root.
            attach_target = _create_pivot_under_root(rig)

    if mesh is not None:
        _parent_keep_transform(mesh, attach_target)
    return rig, attach_target, created_rig


def _on_attach_mesh_picked(self, context):
    """Update callback on the rig-root eyedropper PointerProperty.
    Fires when the user picks a mesh either via the dropdown or the
    viewport eyedropper. Auto-parents the mesh based on the sibling
    `attach_target` enum (ROOT / first PIVOT / brand-new pivot), then
    schedules a clear of the picker field so it's ready for the next
    mesh in a row.
    """
    root_obj = self.id_data  # the Object owning this PropertyGroup
    if root_obj is None or not root_obj.get('inu_animobj_empty_root'):
        return
    mesh = self.attach_mesh
    if mesh is None or mesh.type != 'MESH':
        return

    # Resolve the target Empty per mode.
    target = None
    if self.attach_target == 'ROOT':
        target = root_obj
    elif self.attach_target == 'NEW_PIVOT':
        try:
            target = _create_pivot_under_root(root_obj)
        except Exception as ex:
            print(f"[INU] eyedropper new-pivot failed: {ex}")
    else:  # 'PIVOT' — first existing pivot under root
        for ch in root_obj.children:
            if ch.type == 'EMPTY' and ch.get('inu_animobj_empty_pivot'):
                target = ch
                break
        if target is None:
            # No pivot yet — create one so the picked mesh has somewhere
            # to land. Avoids «nothing happens» when user picks before
            # building a pivot manually.
            try:
                target = _create_pivot_under_root(root_obj)
            except Exception as ex:
                print(f"[INU] eyedropper pivot-fallback failed: {ex}")

    if target is not None:
        _parent_keep_transform(mesh, target)

    # Clear the picker field via a deferred timer — update() callbacks
    # can't reliably mutate the property they fire from in the same
    # event cycle; a 10ms timer dodges the issue and is invisible.
    def _clear():
        try:
            self.attach_mesh = None
        except Exception:
            pass
        return None
    try:
        bpy.app.timers.register(_clear, first_interval=0.01)
    except Exception:
        pass


class INUAnimObjRigSettings(bpy.types.PropertyGroup):
    """Rig-level settings stored on the root Empty. Holds the
    eyedropper picker fields used by the «Add mesh» row in the panel.
    Separate from per-pivot INUAnimObjEmptyProps because these settings
    live on root, not on each pivot."""
    attach_target: EnumProperty(
        name=T("Куда добавить"),
        description=T(
            "Куда привесить выбранный меш:\n"
            "  К pivot — на первый pivot (анимация общая со всем pivot'ом)\n"
            "  Новый pivot — создать отдельный pivot с собственной анимацией\n"
            "  К root — статичная часть без анимации"),
        items=[
            ('NEW_PIVOT', T("Новый pivot"),
             T("Создать новый pivot и привесить меш к нему")),
            ('PIVOT', T("К существующему pivot"),
             T("Парентить к первому pivot'у (одна анимация на всех)")),
            ('ROOT', T("К root (статика)"),
             T("Статичная часть, не будет крутиться")),
        ],
        default='NEW_PIVOT',
    )
    attach_mesh: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name=T("Меш"),
        description=T(
            "Кликни на пипетку и выбери меш в сцене или 3D-окне. "
            "Он автоматически добавится в rig согласно выбору «Куда добавить»"),
        poll=lambda self, obj: obj is not None and obj.type == 'MESH',
        update=_on_attach_mesh_picked,
    )


class GTATOOLS_OT_animobj_add_pivot(bpy.types.Operator):
    """Добавить ещё один pivot Empty в существующий Empty-rig — для
    моделей с несколькими анимированными частями (например мельница +
    противовес). Каждому pivot'у выдаётся свой BoneID и Action.

    Если выделен меш — он сразу парентится к новому pivot'у.
    Если выделена кость старого pivot'а или root — новый pivot
    создаётся как ребёнок root'а того же rig'а.
    """
    bl_idname = "gtatools.animobj_add_pivot"
    bl_label = "INU: Add Pivot to Empty Rig"
    bl_options = {'REGISTER', 'UNDO'}

    pivot_name: StringProperty(
        name=T("Имя pivot'а"),
        description=T(
            "Суффикс для нового Empty: <rig>_<name>. Имя action "
            "автоматически берётся таким же"),
        default="pivot2",
    )
    axis: EnumProperty(
        name=T("Ось вращения"),
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z',
    )
    turns_per_cycle: IntProperty(
        name=T("Оборотов за цикл"),
        default=1, min=1, soft_max=20,
    )
    duration_frames: IntProperty(
        name=T("Длительность (кадров)"),
        default=60, min=2, soft_max=600,
    )
    parent_active_mesh: bpy.props.BoolProperty(
        name=T("Припарентить активный меш"),
        description=T("Сразу подвесить активный меш под новый pivot"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        # Allow when there's a rig anywhere in the scene, or active
        # belongs to one. Setup wizard had no rig requirement; this op
        # requires at least one root.
        if _find_animobj_empty_root(context.active_object):
            return True
        return _animobj_find_first_rig() is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "pivot_name")
        col.prop(self, "axis")
        col.prop(self, "turns_per_cycle")
        col.prop(self, "duration_frames")
        col.prop(self, "parent_active_mesh")

    def execute(self, context):
        # Find target rig — prefer active object's ancestor chain.
        active = context.active_object
        rig = _find_animobj_empty_root(active)
        if rig is None:
            rig = _animobj_find_first_rig()
        if rig is None:
            self.report({'ERROR'},
                        T("В сцене нет Empty-rig'а — сначала Setup (Empty)"))
            return {'CANCELLED'}

        # Allocate next BoneID by scanning existing rig members.
        # Skip BoneID=0 (root) and pick max+1 of the rest.
        existing_ids = []
        for emp in _collect_empty_rig_descendants(rig):
            existing_ids.append(int(emp.get('inu_bone_id', 0)))
        next_bone_id = max(existing_ids + [0]) + 1

        # Strip base prefix off rig.name (<base>_root → <base>) so the
        # new pivot reads as a sibling of the existing pivot rather
        # than as a child of root.
        rig_base = rig.name
        if rig_base.endswith('_root'):
            rig_base = rig_base[:-5]

        suffix = self.pivot_name.strip() or f"pivot{next_bone_id}"
        new_name = f"{rig_base}_{suffix}"

        # Avoid name collision — bpy auto-suffixes anyway, but being
        # explicit keeps the user's BoneID and action name in sync.
        if new_name in bpy.data.objects:
            counter = 2
            while f"{new_name}.{counter:03d}" in bpy.data.objects:
                counter += 1
            new_name = f"{new_name}.{counter:03d}"

        # Create the new pivot, parented to the rig root. Same display
        # type as Setup (Empty) so all pivots in the rig look alike.
        pivot = bpy.data.objects.new(new_name, None)
        pivot.empty_display_type = 'SPHERE'
        pivot.empty_display_size = 0.3
        pivot.parent = rig
        pivot['inu_animobj_empty_pivot'] = True
        pivot['inu_bone_id'] = next_bone_id
        pivot['inu_animobj_action_name'] = suffix
        pivot['dff_frame_write_name'] = True
        for col in rig.users_collection:
            col.objects.link(pivot)

        # Seed props + build action.
        props = pivot.inu_animobj_empty_props
        props.axis = self.axis
        props.turns_per_cycle = self.turns_per_cycle
        props.duration_frames = self.duration_frames
        props.reverse = False
        props.auto_mode = True

        ad = pivot.animation_data_create()
        action = bpy.data.actions.new(name=suffix)
        ad.action = action
        _rebuild_animobj_empty_action(pivot)

        # Optionally pull the active mesh under the new pivot.
        parented_mesh = None
        if (self.parent_active_mesh and active is not None
                and active.type == 'MESH'):
            try:
                _parent_keep_transform(active, pivot)
                parented_mesh = active
            except Exception as ex:
                print(f"[INU] add_pivot parent failed: {ex}")

        # Activate the new pivot so panel sliders bind to it immediately.
        for o in bpy.data.objects:
            o.select_set(False)
        pivot.select_set(True)
        context.view_layer.objects.active = pivot

        suffix_msg = ""
        if parented_mesh:
            suffix_msg = f", {parented_mesh.name} → {pivot.name}"
        self.report({'INFO'},
                    f"Pivot {new_name} (BoneID={next_bone_id}){suffix_msg}")
        return {'FINISHED'}


class GTATOOLS_OT_animobj_parent_to_root(bpy.types.Operator):
    """Припарентить выделенные меши к root Empty-rig'а — они останутся
    статичными как 'основание' (как корпус мельницы без лопастей)."""
    bl_idname = "gtatools.animobj_parent_to_root"
    bl_label = "INU: Parent Selected Meshes to Rig Root"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        rig = _find_animobj_empty_root(context.active_object)
        if rig is None:
            rig = _animobj_find_first_rig()
        if rig is None:
            self.report({'ERROR'},
                        T("В сцене нет Empty-rig'а — сначала Setup (Empty)"))
            return {'CANCELLED'}

        n = 0
        for o in context.selected_objects:
            if o.type == 'MESH' and _parent_keep_transform(o, rig):
                n += 1
        self.report({'INFO'},
                    f"{n} {T('меш(а) припарентено к')} {rig.name}")
        return {'FINISHED'}


