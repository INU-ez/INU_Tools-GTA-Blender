# INU_tools.ops.frame_hierarchy
# Frame Hierarchy Editor — focused tools for editing the DFF frame tree
# (the chain of dummy/mesh objects that gets serialised as the DFF Frame
# List). Critical for vehicle and ped workflows where the engine looks
# up frames by exact name (chassis_dummy, wheel_lf_dummy, R UpperArm, …).
#
# This module owns:
#   - operators: rename, set/clear parent, validate-against-template,
#     mirror left↔right
#   - vanilla-name templates for vehicles and peds
#
# The actual UI lives in ui/panels.py (panel that draws the descendant
# tree of the active object plus the operator buttons).

import re

import bpy
from bpy.props import StringProperty

from .. import T


# ── Vanilla SA name templates ──────────────────────────────────
# These names are not folklore: they were read out of gta_sa.exe 1.0 US, from
# the RwObjectNameIdAssocation tables that CClumpModelInfo::SetFrameIds walks
# at load time. That is the one moment the engine cares what a frame is
# called — it matches by name (with _stricmp, so casing is free), stamps a
# hierarchy id onto the frame, and from then on everything works by id.
#
# FATAL vs the rest is measured, not guessed: CVehicleModelInfo::GetWheelPosn
# dereferences whatever GetFrameFromId hands back with no null check on
# either of its branches, so a missing wheel dummy faults the game rather
# than degrading. Everything else merely goes missing.

VEHICLE_FATAL = {
    'wheel_lf_dummy':  "ось переднего левого колеса",
    'wheel_rf_dummy':  "ось переднего правого колеса",
    'wheel_lb_dummy':  "ось заднего левого колеса",
    'wheel_rb_dummy':  "ось заднего правого колеса",
}

VEHICLE_REQUIRED = {
    **VEHICLE_FATAL,
    'chassis_dummy': "верхний dummy всей машины",
}

VEHICLE_OPTIONAL = {
    # Rear doors are lr/rr in the engine's table, not lb/rb; bumpers are
    # front/rear rather than left/right; the exhaust entry is exhaust_ok.
    'chassis',
    'wheel_lm_dummy', 'wheel_rm_dummy',        # six-wheelers only
    'bonnet_dummy', 'boot_dummy', 'windscreen_dummy',
    'door_lf_dummy', 'door_rf_dummy', 'door_lr_dummy', 'door_rr_dummy',
    'bump_front_dummy', 'bump_rear_dummy',
    'wing_lf_dummy', 'wing_rf_dummy',
    'exhaust_ok',
    'misc_a', 'misc_b', 'misc_c', 'misc_d', 'misc_e',
}

# Bikes and BMX use a different table altogether and never reach
# GetWheelPosn — CBike has its own code — so none of this is fatal.
BIKE_REQUIRED = {
    'chassis_dummy': "верхний dummy байка",
    'wheel_front':   "переднее колесо",
    'wheel_rear':    "заднее колесо",
}

# Ped skeleton — these 31 names are matched verbatim by ped.ifp.
PED_REQUIRED = {
    'Root', 'Pelvis', 'Spine', 'Spine1', 'Neck', 'Head',
    'Bip01 L Clavicle', 'L UpperArm', 'L Forearm', 'L Hand', 'L Finger',
    'Bip01 R Clavicle', 'R UpperArm', 'R Forearm', 'R Hand', 'R Finger',
    'L Thigh', 'L Calf', 'L Foot', 'L Toe0',
    'R Thigh', 'R Calf', 'R Foot', 'R Toe0',
    'Bip01',
}


# Blender's duplicate suffix. Frame names are written to the DFF as-is, so
# "wheel_lf_dummy.001" reaches the engine with the suffix attached and never
# matches — the model looks fine in Blender and crashes in game.
_DUP_SUFFIX = re.compile(r"\.\d{3}$")


def check_vehicle_names(names):
    """Audit the frame names a vehicle DFF will carry.

    *names* must be the names as they will be written to the file, not
    Blender object names, so that a ``.001`` suffix is judged the way the
    engine will see it.

    Returns ``(fatal, warnings)`` — two lists of ready-to-show strings.
    Empty *fatal* means the game will at least not crash on wheel lookup.
    """
    lower = {str(n).lower() for n in names}

    if 'wheel_front' in lower or 'wheel_rear' in lower:
        missing = [f"{name} — {T(desc)}"
                   for name, desc in BIKE_REQUIRED.items()
                   if name not in lower]
        return [], missing

    fatal, warnings = [], []

    for name, desc in VEHICLE_FATAL.items():
        if name in lower:
            continue
        near = next((k for k in lower if _DUP_SUFFIX.sub("", k) == name), None)
        if near:
            fatal.append(f"{name} — "
                         + T("есть как «{0}», суффикс уйдёт в DFF").format(near))
        else:
            fatal.append(f"{name} — {T(desc)}")

    if 'chassis_dummy' not in lower:
        warnings.append(
            f"chassis_dummy — {T(VEHICLE_REQUIRED['chassis_dummy'])}")

    for name in sorted(lower):
        # Ровно `wheel` — ванильный меш колеса (admiral, landstal, hydra,
        # linerun, monster…): игра клонирует его на wheel_*_dummy. Не дамми,
        # сторона ему не положена.
        if name == 'wheel':
            continue
        if 'wheel' in name and not any(s in name for s in
                                       ('_lf', '_rf', '_lb', '_rb', '_lm', '_rm')):
            warnings.append(f"{name} — {T('wheel без _lf/_rf/_lb/_rb')}")

    return fatal, warnings


# ── Helpers ────────────────────────────────────────────────────

def _all_descendants(root):
    """Depth-first list of root + all children, no ordering guarantees
    beyond depth-first."""
    out = [root]
    stack = list(root.children)
    while stack:
        cur = stack.pop()
        out.append(cur)
        stack.extend(cur.children)
    return out


def _restore_world_after_reparent(obj, parent):
    """Re-parent ``obj`` under ``parent`` while preserving its world
    transform. matrix_parent_inverse is reset to identity so the DFF
    exporter doesn't bake an offset into the frame matrix."""
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse.identity()
    # Restore the world transform for BOTH re-parent AND unparent (parent=None).
    # Skipping it on unparent left the object shifted by the old parent's
    # transform (matrix_basis stayed parent-relative but now reads as world).
    obj.matrix_world = world


# ── Operators ──────────────────────────────────────────────────

class GTATOOLS_OT_frame_select(bpy.types.Operator):
    """Сделать активным указанный фрейм (используется панелью при клике
    на строку дерева)."""
    bl_idname = "gtatools.frame_select"
    bl_label = "INU: Select Frame"
    bl_options = {'REGISTER', 'UNDO'}

    target_name: StringProperty()
    extend: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        target = bpy.data.objects.get(self.target_name)
        if target is None:
            return {'CANCELLED'}
        if not self.extend:
            for o in context.selected_objects:
                o.select_set(False)
        target.select_set(True)
        context.view_layer.objects.active = target
        return {'FINISHED'}


class GTATOOLS_OT_frame_rename(bpy.types.Operator):
    """Переименовать активный фрейм."""
    bl_idname = "gtatools.frame_rename"
    bl_label = "INU: Rename Frame"
    bl_options = {'REGISTER', 'UNDO'}

    new_name: StringProperty(
        name=T("Имя"),
        description=T("Новое имя фрейма (точное соответствие требуется для машин и педов)"),
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        self.new_name = context.active_object.name
        return context.window_manager.invoke_props_dialog(self, width=380)

    def execute(self, context):
        obj = context.active_object
        new = self.new_name.strip()
        if not new or obj is None:
            self.report({'ERROR'}, T("Имя не может быть пустым"))
            return {'CANCELLED'}
        if new == obj.name:
            return {'CANCELLED'}
        old = obj.name
        obj.name = new
        # Update DFF write-name flag so the new name actually survives export.
        if 'dff_frame_write_name' in obj:
            obj['dff_frame_write_name'] = True
        self.report({'INFO'}, f"{old} → {obj.name}")
        return {'FINISHED'}


class GTATOOLS_OT_frame_set_parent(bpy.types.Operator):
    """Назначить parent: активный объект становится родителем для остальных
    выделенных. Мировая позиция каждого ребёнка сохраняется, а
    matrix_parent_inverse сбрасывается в identity (DFF requirement)."""
    bl_idname = "gtatools.frame_set_parent"
    bl_label = "INU: Set Frame Parent"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None
                and len(context.selected_objects) >= 2)

    def execute(self, context):
        parent = context.active_object
        children = [o for o in context.selected_objects if o is not parent]
        for c in children:
            _restore_world_after_reparent(c, parent)
        self.report({'INFO'},
                    f"{T('parent')} {parent.name} → {len(children)}")
        return {'FINISHED'}


class GTATOOLS_OT_frame_unparent(bpy.types.Operator):
    """Снять parent с выделенных объектов (parent → None). Мировая
    позиция сохраняется."""
    bl_idname = "gtatools.frame_unparent"
    bl_label = "INU: Clear Frame Parent"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.parent for o in context.selected_objects)

    def execute(self, context):
        count = 0
        for o in context.selected_objects:
            if o.parent:
                _restore_world_after_reparent(o, None)
                count += 1
        self.report({'INFO'}, f"{T('сняли parent с')}: {count}")
        return {'FINISHED'}


class GTATOOLS_OT_frame_reparent(bpy.types.Operator):
    """Сделать указанный фрейм РОДИТЕЛЕМ активного — клик прямо в дереве
    панели: сначала выдели дочерний фрейм, потом жми эту кнопку на строке
    будущего родителя. Мировая позиция сохраняется, matrix_parent_inverse
    сбрасывается в identity (требование DFF)."""
    bl_idname = "gtatools.frame_reparent"
    bl_label = "INU: Reparent Frame"
    bl_options = {'REGISTER', 'UNDO'}

    parent_name: StringProperty()
    # Which frame to move. Empty = the active object (the ⤴ «make this the
    # parent of the selected» button). Set = that exact frame (the per-row
    # unparent button passes its own name + empty parent → make it a root).
    child_name: StringProperty()

    @classmethod
    def description(cls, context, properties):
        cn = getattr(properties, 'child_name', '')
        pn = getattr(properties, 'parent_name', '')
        if not pn:
            who = f"«{cn}»" if cn else T('выделенный фрейм')
            return f"{T('Снять родителя — сделать')} {who} {T('корневым')}"
        return f"{T('Сделать')} «{pn}» {T('родителем выделенного фрейма')}"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        child = (bpy.data.objects.get(self.child_name)
                 if self.child_name else context.active_object)
        parent = (bpy.data.objects.get(self.parent_name)
                  if self.parent_name else None)
        if child is None:
            return {'CANCELLED'}
        if parent is child:
            self.report({'WARNING'},
                        T("Нельзя назначить объект родителем самого себя"))
            return {'CANCELLED'}
        # Reject a cycle: the chosen parent must not already be a descendant
        # of the child (that would make an unexportable loop).
        p = parent
        while p is not None:
            if p is child:
                self.report({'WARNING'}, T("Циклическая иерархия недопустима"))
                return {'CANCELLED'}
            p = p.parent
        _restore_world_after_reparent(child, parent)
        self.report({'INFO'},
                    f"{child.name} → {parent.name if parent else T('корень')}")
        return {'FINISHED'}


class GTATOOLS_OT_frame_validate(bpy.types.Operator):
    """Проверить иерархию активного объекта против vanilla SA шаблона.
    Тип шаблона выбирается атрибутом ``template`` оператора."""
    bl_idname = "gtatools.frame_validate"
    bl_label = "INU: Validate Frame Hierarchy"
    bl_options = {'REGISTER'}

    template: bpy.props.EnumProperty(
        name="Template",
        items=[
            ('VEHICLE', "Vehicle", "GTA SA vehicle dummy hierarchy"),
            ('PED',     "Ped",     "GTA SA ped 31-bone skeleton"),
        ],
        default='VEHICLE',
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        root = context.active_object
        descendants = _all_descendants(root)
        names = {o.name for o in descendants}
        names_lower = {n.lower() for n in names}

        fatal = []
        if self.template == 'VEHICLE':
            # Bikes, wheel typos and Blender's .001 suffix are all handled by
            # the shared audit, so the export path and this button agree.
            fatal, suspicious = check_vehicle_names(names_lower)
            missing = []
            label = "Vehicle"
        else:
            required = PED_REQUIRED
            # Peds use exact case-sensitive match
            missing = [
                f"{name}"
                for name in required
                if name not in names
            ]
            suspicious = []
            label = "Ped"

        # Always log — easier to copy-paste from console.
        print(f"[frame_validate {label}] root={root.name}, "
              f"descendants={len(descendants)}")
        if fatal:
            print(f"  ИГРА УПАДЁТ ({len(fatal)}) — GetWheelPosn разыменует "
                  f"фрейм без проверки на NULL:")
            for f in fatal:
                print(f"    ✗ {f}")
        if missing:
            print(f"  Missing required ({len(missing)}):")
            for m in missing:
                print(f"    ! {m}")
        if suspicious:
            print(f"  Suspicious ({len(suspicious)}):")
            for s in suspicious:
                print(f"    ? {s}")
        if not fatal and not missing and not suspicious:
            print("  OK — все обязательные имена на месте")

        if fatal:
            self.report({'ERROR'},
                        f"{label}: {T('игра упадёт')} — "
                        f"{', '.join(f.split(' — ')[0] for f in fatal)} "
                        f"({T('см. System Console')})")
        elif missing or suspicious:
            self.report({'WARNING'},
                        f"{label}: missing={len(missing)}, "
                        f"suspicious={len(suspicious)} "
                        f"({T('см. System Console')})")
        else:
            self.report({'INFO'}, f"{label} {T('иерархия OK')}")
        return {'FINISHED'}


class GTATOOLS_OT_frame_mirror_lr(bpy.types.Operator):
    """Создать зеркальную копию выделенных фреймов: ``_lf`` → ``_rf``,
    ``_lb`` → ``_rb`` (X отражается, остальные оси без изменений). Если
    зеркальный близнец уже существует — оператор его не трогает."""
    bl_idname = "gtatools.frame_mirror_lr"
    bl_label = "INU: Mirror Left↔Right"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(
            any(suf in o.name for suf in ('_lf', '_lb'))
            for o in context.selected_objects
        )

    _MAP = {'_lf': '_rf', '_lb': '_rb'}

    def execute(self, context):
        created = 0
        skipped = 0

        for src in list(context.selected_objects):
            mirror_suffix = None
            target_name = None
            for src_suf, dst_suf in self._MAP.items():
                if src_suf in src.name:
                    target_name = src.name.replace(src_suf, dst_suf, 1)
                    mirror_suffix = (src_suf, dst_suf)
                    break
            if mirror_suffix is None:
                continue
            if target_name in bpy.data.objects:
                skipped += 1
                continue

            # Duplicate: keep parent + flip X position
            if src.data is None:
                copy = bpy.data.objects.new(target_name, None)
                copy.empty_display_type = src.empty_display_type
                copy.empty_display_size = src.empty_display_size
            else:
                copy = bpy.data.objects.new(target_name, src.data.copy())

            copy.parent = src.parent
            copy.matrix_parent_inverse = src.matrix_parent_inverse.copy()
            # Mirror local X
            from mathutils import Matrix
            mirror_x = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
            copy.matrix_basis = src.matrix_basis @ mirror_x

            # Carry DFF frame metadata if present
            for k in ('dff_frame_flags', 'dff_frame_write_name'):
                if k in src:
                    copy[k] = src[k]

            # Link to same collections
            for col in src.users_collection:
                col.objects.link(copy)

            created += 1

        self.report({'INFO'},
                    f"{T('зеркально создано')}: {created}, "
                    f"{T('пропущено (уже есть)')}: {skipped}")
        return {'FINISHED'}


