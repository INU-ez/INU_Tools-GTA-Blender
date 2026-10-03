# INU_tools.ops.path_curves
# Curve-based authoring for GTA SA path nodes (Kams / ZZPuma style).
#
# Two complementary operators:
#   - GTATOOLS_OT_nodes_to_curves: split an imported nodes mesh into one
#     Blender Curve per lane chain. Path attributes (type/width/spawn/
#     highway/lane counts) live on the Curve object as `sapath_*`
#     IDProperties, mirroring how Kams' MaxScript stores them on the
#     SplineShape.
#   - GTATOOLS_OT_curves_to_nodes: export persistent point identities
#     through the same graph/navigation rebuild as the mesh exporter.

from __future__ import annotations

import bpy
from bpy.props import StringProperty, FloatProperty, BoolProperty
import struct

from .. import T
from ..tools.compat import safe_icon, inu_icon


# ── Curve ↔ flags property mapping ──────────────────────────────
# Same key names as ZZPuma's GetUserProp / SetUserProp so files
# round-trip between addons (a Curve authored in INU Tools can be
# opened in Max via ZZPuma if its props are mirrored to UserProps).
_SAPATH_PROPS = (
    'sapath_type',      # 1=Ped, 2=Vehicle
    'sapath_width',
    'sapath_pathid',
    'sapath_traffic',
    'sapath_spawn',
    'sapath_roadblock',
    'sapath_boats',
    'sapath_emergency',
    'sapath_highway',
    'sapath_parking',
    'sapath_laneright',
    'sapath_laneleft',
)


def _set_curve_wirecolor(curve_obj):
    """Auto-colour curve wireframe by sapath_type / flags so the user
    can identify path purpose at a glance — mirrors ZZPuma's
    `setShapeColors`. Priority order (ZZPuma's logic):
      type=1 (Ped)       → green
      type=2 (Vehicle)   → red
        + boats=1        → blue
        + parking=1      → orange (overrides everything else)
        + traffic=2      → darker (subtract 75 from RGB)
        + highway=1      → add 150 to blue channel
    Result is clamped to 0-255 and written to ``obj.color`` (RGBA).
    Object viewport display has to be set to "Object" colour for this
    to render — we leave that to the user (it's a one-time setting).
    """
    t = int(curve_obj.get('sapath_type', 1) or 1)
    boats = bool(int(curve_obj.get('sapath_boats', 0) or 0))
    parking = bool(int(curve_obj.get('sapath_parking', 0) or 0))
    traffic = int(curve_obj.get('sapath_traffic', 1) or 1)
    highway = bool(int(curve_obj.get('sapath_highway', 0) or 0))

    r = g = b = 0
    if t == 1:
        r, g, b = 0, 255, 0  # Ped — green
    elif t == 2:
        r, g, b = 255, 0, 0  # Vehicle — red
        if boats:
            r, g, b = 0, 0, 255  # Boat — blue
        if parking:
            r, g, b = 255, 150, 0  # Parking — orange (early exit)
            curve_obj.color = (r / 255, g / 255, b / 255, 1.0)
            return
    if traffic == 2:
        r = max(0, r - 75); g = max(0, g - 75); b = max(0, b - 75)
    if highway:
        b = min(255, b + 150)
    curve_obj.color = (r / 255, g / 255, b / 255, 1.0)


def _set_curve_defaults(curve_obj):
    """Seed sapath_* props with sane defaults — called when a fresh
    Curve has no props yet (user just added Curve→Bezier and ran the
    converter). Defaults match ZZPuma's `setDefault` block."""
    if curve_obj.get('sapath_type') is None:        curve_obj['sapath_type'] = 1
    if curve_obj.get('sapath_width') is None:       curve_obj['sapath_width'] = 0.0
    if curve_obj.get('sapath_pathid') is None:      curve_obj['sapath_pathid'] = 0
    if curve_obj.get('sapath_traffic') is None:     curve_obj['sapath_traffic'] = 1
    if curve_obj.get('sapath_spawn') is None:       curve_obj['sapath_spawn'] = 1.0
    if curve_obj.get('sapath_roadblock') is None:   curve_obj['sapath_roadblock'] = 0
    if curve_obj.get('sapath_boats') is None:       curve_obj['sapath_boats'] = 0
    if curve_obj.get('sapath_emergency') is None:   curve_obj['sapath_emergency'] = 0
    if curve_obj.get('sapath_highway') is None:     curve_obj['sapath_highway'] = 0
    if curve_obj.get('sapath_parking') is None:     curve_obj['sapath_parking'] = 0
    if curve_obj.get('sapath_laneright') is None:   curve_obj['sapath_laneright'] = 1
    if curve_obj.get('sapath_laneleft') is None:    curve_obj['sapath_laneleft'] = 1


# ── Operator: build curves from a nodes mesh ──────────────────────

class GTATOOLS_OT_nodes_to_curves(bpy.types.Operator):
    """Split an imported nodes mesh into one Blender Curve per lane chain.

    Reads the mesh's edge graph (built by `path_import._create_nodes_mesh`),
    traces connected chains, and emits a Curve per chain with sapath_*
    properties seeded from the per-vertex flag IDProperties. The
    original mesh is left untouched so the user can compare side-by-side."""
    bl_idname = "gtatools.nodes_to_curves"
    bl_label = "INU: Nodes Mesh → Curves"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            return False
        return obj.get('path_type') in ('nodes_vehicle', 'nodes_ped')

    def execute(self, context):
        from .path_nodes_curves import convert_mesh
        try:
            curves = convert_mesh(context, context.active_object,
                                  _set_curve_defaults, _set_curve_wirecolor)
        except (ValueError, KeyError, TypeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        if curves and context.mode == 'OBJECT':
            for obj in context.selected_objects:
                obj.select_set(False)
            for obj in curves:
                obj.select_set(True)
            context.view_layer.objects.active = curves[0]
        self.report({'INFO'}, f"{len(curves)} {T('кривых построено')}")
        return {'FINISHED'}


# ── Operator: export curves to nodes.dat ──────────────────────────


class GTATOOLS_OT_curves_to_nodes(bpy.types.Operator):
    """Export converted Compiled NODES curves with persistent identities."""
    bl_idname = "gtatools.curves_to_nodes"
    bl_label = "INU: Curves → nodes*.dat"
    bl_description = T("Экспорт кривых с сохранением ID и связей Compiled NODES")
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH',
                              description="Куда сохранить nodes*.dat")
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})
    fla4: BoolProperty(
        name=T("FLA4"),
        description=T("Записать в расширенном FLA4 формате (для Fastman92 limit adjuster)"),
        default=False,
    )
    path_set: bpy.props.EnumProperty(
        name=T("Path set"),
        description=T(
            "Размер регионной сетки. 64 = vanilla SA. Большие значения "
            "требуют Fastman92 limit adjuster (FLA4)"),
        items=[
            ('64',    "64 (Vanilla)",  ""),
            ('256',   "256",            ""),
            ('1024',  "1024",           ""),
            ('4096',  "4096",           ""),
            ('16384', "16384",          ""),
            ('65536', "65536",          ""),
        ],
        default='64',
    )
    entire_map: BoolProperty(
        name=T("Записать всю карту"),
        description=T(
            "Включить все импортированные регионы и обновить межрегионные "
            "ссылки при изменении ID точек"),
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return any(o.type == 'CURVE' for o in context.selected_objects)

    def invoke(self, context, event):
        from .path_nodes_curves import prepare_curve_export, SOURCE, _carrier, _decode
        try:
            selected = [o for o in context.selected_objects if o.type == 'CURVE']
            if selected and selected[0].get(SOURCE):
                carrier = _carrier(selected[0][SOURCE], context.scene.objects)
                if not self.properties.is_property_set('fla4'):
                    self.fla4 = _decode(carrier['inu_nodes_curve_snapshot']).fla4
                if not self.filepath:
                    self.filepath = carrier['nodes_filename']
            # Reindexing needs neighbouring regions; include them automatically
            # when opening the file selector, then validate before it opens.
            from .path_nodes_curves import collect_curve_region
            if any(collect_curve_region(_carrier(source, context.scene.objects),
                                        context.scene.objects).node_remap
                   for source in {o[SOURCE] for o in selected if o.get(SOURCE)}):
                self.entire_map = True
            prepare_curve_export(selected, context.scene.objects, entire_map=self.entire_map,
                                 fla4=self.fla4, path_set=int(self.path_set))
        except (ValueError, KeyError, TypeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .path_nodes_curves import prepare_curve_export, write_curve_export
        try:
            regions = prepare_curve_export(context.selected_objects, context.scene.objects,
                                           entire_map=self.entire_map, fla4=self.fla4,
                                           path_set=int(self.path_set))
            write_curve_export(self.filepath, regions)
        except (ValueError, KeyError, TypeError, OSError, OverflowError, struct.error) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, f"{len(regions)} NODES {T('файлов экспортировано')}")
        return {'FINISHED'}


# ── Selection helpers (ZZPuma DEBUGPATH_ROL: bt_selPeds/Vehs/allp) ─

def _select_curves_by_type(context, target_type):
    """target_type: 0 = all path curves, 1 = ped only, 2 = vehicle only."""
    n = 0
    for o in bpy.data.objects:
        if o.type != 'CURVE':
            continue
        if o.get('sapath_type') is None:
            continue
        try:
            o.select_set(False)
        except Exception:
            continue
        t = int(o.get('sapath_type', 1))
        if target_type == 0 or t == target_type:
            try:
                o.select_set(True)
                n += 1
            except Exception:
                pass
    return n


class GTATOOLS_OT_select_path_peds(bpy.types.Operator):
    """Выделить все Curve-пути типа Ped (sapath_type=1)"""
    bl_idname = "gtatools.select_path_peds"
    bl_label = "INU: Select Ped Paths"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = _select_curves_by_type(context, 1)
        self.report({'INFO'}, f"{n} {T('ped Curve выделено')}")
        return {'FINISHED'}


class GTATOOLS_OT_select_path_vehs(bpy.types.Operator):
    """Выделить все Curve-пути типа Vehicle (sapath_type=2)"""
    bl_idname = "gtatools.select_path_vehs"
    bl_label = "INU: Select Vehicle Paths"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = _select_curves_by_type(context, 2)
        self.report({'INFO'}, f"{n} {T('vehicle Curve выделено')}")
        return {'FINISHED'}


class GTATOOLS_OT_select_path_all(bpy.types.Operator):
    """Выделить все Curve-пути с sapath_* свойствами"""
    bl_idname = "gtatools.select_path_all"
    bl_label = "INU: Select All Path Curves"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = _select_curves_by_type(context, 0)
        self.report({'INFO'}, f"{n} {T('Curve выделено')}")
        return {'FINISHED'}


# ── Refresh wireframe colour (ZZPuma setShapeColors button) ───────

class GTATOOLS_OT_refresh_path_colors(bpy.types.Operator):
    """Перекрасить wireframe выделенных Curve-путей по их типу/флагам"""
    bl_idname = "gtatools.refresh_path_colors"
    bl_label = "INU: Refresh Path Colours"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = 0
        for o in context.selected_objects:
            if o.type == 'CURVE' and o.get('sapath_type') is not None:
                _set_curve_wirecolor(o)
                n += 1
        self.report({'INFO'}, f"{n} {T('Curve перекрашено')}")
        return {'FINISHED'}


# ── Pick / Apply path properties (ZZPuma get_settg / set_settg) ───
# Module-level clipboard holding the last "picked" sapath_* dict.
# Lives only for the current Blender session — re-pick after restart.
_PATH_PROPS_CLIPBOARD: dict = {}


class GTATOOLS_OT_pick_path_props(bpy.types.Operator):
    """Скопировать sapath_* свойства активной Curve во внутренний буфер"""
    bl_idname = "gtatools.pick_path_props"
    bl_label = "INU: Pick Path Props"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return o is not None and o.type == 'CURVE' and o.get('sapath_type') is not None

    def execute(self, context):
        global _PATH_PROPS_CLIPBOARD
        o = context.active_object
        _PATH_PROPS_CLIPBOARD = {
            k: o.get(k) for k in _SAPATH_PROPS if o.get(k) is not None
        }
        self.report(
            {'INFO'},
            f"{T('Скопировано props:')} {len(_PATH_PROPS_CLIPBOARD)}")
        return {'FINISHED'}


class GTATOOLS_OT_apply_path_props(bpy.types.Operator):
    """Применить ранее скопированные sapath_* к выделенным Curve"""
    bl_idname = "gtatools.apply_path_props"
    bl_label = "INU: Apply Path Props"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_PATH_PROPS_CLIPBOARD)

    def execute(self, context):
        if not _PATH_PROPS_CLIPBOARD:
            self.report({'ERROR'}, T("Буфер пуст — сначала Pick на исходной Curve"))
            return {'CANCELLED'}
        n = 0
        for o in context.selected_objects:
            if o.type != 'CURVE':
                continue
            for k, v in _PATH_PROPS_CLIPBOARD.items():
                o[k] = v
            _set_curve_wirecolor(o)
            n += 1
        self.report({'INFO'}, f"{T('Props применены к')} {n} Curve")
        return {'FINISHED'}


# ── Bulk-edit props on multi-selection (#7) ───────────────────────
# Multi-select edit is implemented as a popup operator that prompts
# the user for each sapath_* override and propagates to every selected
# Curve. Lighter weight than a full PropertyGroup mirror; the popup is
# only opened when the user asks for it.

class GTATOOLS_OT_bulk_set_path_props(bpy.types.Operator):
    """Bulk-set sapath_* свойств для всех выделенных Curve.

    Опции с -1 / 0 значением «не менять». Полезно для разом установить
    type=Vehicle + traffic=enabled + spawn=1.0 на массу путей после
    импорта или ручной правки."""
    bl_idname = "gtatools.bulk_set_path_props"
    bl_label = "INU: Bulk Set Path Props"
    bl_options = {'REGISTER', 'UNDO'}

    set_type: bpy.props.EnumProperty(
        name=T("Тип"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('1', T("Ped"), ""),
            ('2', T("Vehicle"), ""),
        ],
        default='NONE')
    set_traffic: bpy.props.EnumProperty(
        name=T("Traffic"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('1', T("Включён"), ""),
            ('2', T("Выключен"), ""),
        ],
        default='NONE')
    set_spawn: FloatProperty(
        name=T("Spawn rate"),
        description=T("Spawn probability 0.0-1.0. Введи -1 чтобы не менять"),
        default=-1.0, min=-1.0, max=1.0)
    set_width: FloatProperty(
        name=T("Width"),
        description=T("Path width. Введи -1 чтобы не менять"),
        default=-1.0, min=-1.0, soft_max=100.0)
    set_highway: bpy.props.EnumProperty(
        name=T("Highway"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('0', T("Нет"), ""),
            ('1', T("Да"), ""),
        ],
        default='NONE')
    set_boats: bpy.props.EnumProperty(
        name=T("Boats"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('0', T("Нет"), ""),
            ('1', T("Да"), ""),
        ],
        default='NONE')
    set_parking: bpy.props.EnumProperty(
        name=T("Parking"),
        items=[
            ('NONE', T("Не менять"), ""),
            ('0', T("Нет"), ""),
            ('1', T("Да"), ""),
        ],
        default='NONE')

    @classmethod
    def poll(cls, context):
        return any(o.type == 'CURVE' for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, 'set_type')
        col.prop(self, 'set_traffic')
        col.prop(self, 'set_spawn')
        col.prop(self, 'set_width')
        col.prop(self, 'set_highway')
        col.prop(self, 'set_boats')
        col.prop(self, 'set_parking')

    def execute(self, context):
        n = 0
        for o in context.selected_objects:
            if o.type != 'CURVE':
                continue
            _set_curve_defaults(o)
            if self.set_type != 'NONE':
                o['sapath_type'] = int(self.set_type)
            if self.set_traffic != 'NONE':
                o['sapath_traffic'] = int(self.set_traffic)
            if self.set_spawn >= 0.0:
                o['sapath_spawn'] = float(self.set_spawn)
            if self.set_width >= 0.0:
                o['sapath_width'] = float(self.set_width)
            if self.set_highway != 'NONE':
                o['sapath_highway'] = int(self.set_highway)
            if self.set_boats != 'NONE':
                o['sapath_boats'] = int(self.set_boats)
            if self.set_parking != 'NONE':
                o['sapath_parking'] = int(self.set_parking)
            _set_curve_wirecolor(o)
            n += 1
        self.report({'INFO'}, f"{T('Bulk-set применён к')} {n} Curve")
        return {'FINISHED'}


# ── Path accessories (#6) ─────────────────────────────────────────
# TrafficLight / RoadBlock / Connector / SpecialNode are per-knot
# annotations on a path Curve. ZZPuma stores them as mesh-child
# objects parented to the spline with `knot` user-prop.
#
# We use the same pattern but with plain Empty objects instead of
# mesh blobs — easier to maintain, scales the same way, and the user
# can swap the display type if they want a custom icon. Each accessory
# carries:
#   inu_accessory_type  : 'TL' / 'RB' / 'CO' / 'SP'
#   inu_accessory_knot  : int — knot index on the parent Curve (0-based)
# For TrafficLight only:
#   inu_accessory_percent  : float 0..1 along the segment from knot N to N+1
#   inu_accessory_direction: int — TL orientation behaviour
#   inu_accessory_reversed : 0/1 — flip TL 180°

ACCESSORY_TYPES = {
    'TL': {'display': 'CUBE',   'size': 0.6, 'name': 'TrafficLight'},
    'RB': {'display': 'PLAIN_AXES', 'size': 0.8, 'name': 'RoadBlock'},
    'CO': {'display': 'CONE',   'size': 0.5, 'name': 'Connector'},
    'SP': {'display': 'SPHERE', 'size': 0.4, 'name': 'SpecialNode'},
}


def _create_path_accessory(curve_obj, knot_index: int, accessory_type: str):
    """Spawn an Empty parented to *curve_obj* at the given knot. Type
    drives the Empty display style + IDProp tag. Returns the new object."""
    if accessory_type not in ACCESSORY_TYPES:
        raise ValueError(f"Unknown accessory type {accessory_type!r}")
    cfg = ACCESSORY_TYPES[accessory_type]

    name = f"{curve_obj.name}_{cfg['name']}"
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = cfg['display']
    empty.empty_display_size = cfg['size']
    empty['inu_accessory_type'] = accessory_type
    empty['inu_accessory_knot'] = int(knot_index)
    if accessory_type == 'TL':
        empty['inu_accessory_percent'] = 0.5
        empty['inu_accessory_direction'] = 1
        empty['inu_accessory_reversed'] = 0
    empty.parent = curve_obj

    # Place at the curve's knot world position. For Curves we read
    # spline 0's point N; for closed/multi-spline curves the user can
    # change `inu_accessory_knot` and the update tick will re-place it.
    try:
        spl = curve_obj.data.splines[0]
        pts = (spl.bezier_points if spl.type == 'BEZIER' else spl.points)
        if 0 <= knot_index < len(pts):
            local = pts[knot_index].co
            world = curve_obj.matrix_world @ (
                local.xyz if hasattr(local, 'xyz') else local)
            empty.matrix_world.translation = world
    except Exception:
        pass

    # Same collection as the parent.
    for col in curve_obj.users_collection:
        col.objects.link(empty)
    return empty


class GTATOOLS_OT_add_path_accessory(bpy.types.Operator):
    """Добавить TrafficLight / RoadBlock / Connector / SpecialNode на
    активный knot выделенной Curve."""
    bl_idname = "gtatools.add_path_accessory"
    bl_label = "INU: Add Path Accessory"
    bl_options = {'REGISTER', 'UNDO'}

    accessory_type: bpy.props.EnumProperty(
        name=T("Тип"),
        items=[
            ('TL', T("TrafficLight"), T("Светофор: spawn'ится на сегменте между knot и knot+1")),
            ('RB', T("RoadBlock"),    T("Дорожный блок копов на самом knot")),
            ('CO', T("Connector"),    T("Connector нода (для inter-region путей FLA4)")),
            ('SP', T("SpecialNode"),  T("Универсальный маркер для special-логики")),
        ],
        default='TL',
    )
    knot_index: bpy.props.IntProperty(
        name=T("Knot index"),
        description=T("Индекс knot'а на родительской Curve (0-based)"),
        default=0, min=0,
    )

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return o is not None and o.type == 'CURVE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def execute(self, context):
        curve_obj = context.active_object
        try:
            empty = _create_path_accessory(
                curve_obj, self.knot_index, self.accessory_type)
        except Exception as ex:
            self.report({'ERROR'}, f"Accessory: {ex}")
            return {'CANCELLED'}
        # Flag the parent Curve with corresponding sapath_* hint so the
        # export knows the node at this knot needs the matching bit set.
        if self.accessory_type == 'RB':
            curve_obj['sapath_roadblock'] = 1
            _set_curve_wirecolor(curve_obj)
        empty.select_set(True)
        context.view_layer.objects.active = empty
        self.report({'INFO'},
                    f"{T('Создан')} {ACCESSORY_TYPES[self.accessory_type]['name']}"
                    f" @ knot {self.knot_index}")
        return {'FINISHED'}


class GTATOOLS_OT_remove_path_accessory(bpy.types.Operator):
    """Удалить выделенные path accessory объекты"""
    bl_idname = "gtatools.remove_path_accessory"
    bl_label = "INU: Remove Path Accessory"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.get('inu_accessory_type') is not None
                   for o in context.selected_objects)

    def execute(self, context):
        n = 0
        for o in list(context.selected_objects):
            if o.get('inu_accessory_type') is not None:
                bpy.data.objects.remove(o, do_unlink=True)
                n += 1
        self.report({'INFO'}, f"{T('Удалено accessory:')} {n}")
        return {'FINISHED'}


# ── #8 Auto-tick service ──────────────────────────────────────────
# Keep accessory positions in sync with their parent Curve when the
# user drags knots. ZZPuma runs this every 30 frames via MaxScript
# upTick; we use bpy.app.timers (lightweight, native Blender API).

def _accessory_sync_tick():
    """Re-place every accessory on its parent Curve knot. Called every
    ~0.5s while there are accessories in the scene; auto-stops when
    none are left to save CPU."""
    if bpy is None or not hasattr(bpy, 'data'):
        return None
    accessories = [o for o in bpy.data.objects
                   if o.get('inu_accessory_type') is not None]
    if not accessories:
        # Unregister — nothing to sync. Will re-register on next add.
        return None

    for empty in accessories:
        parent = empty.parent
        if parent is None or parent.type != 'CURVE':
            continue
        kn = int(empty.get('inu_accessory_knot', 0))
        atype = empty.get('inu_accessory_type', '')
        try:
            spl = parent.data.splines[0]
        except IndexError:
            continue
        pts = spl.bezier_points if spl.type == 'BEZIER' else spl.points
        if not pts or kn < 0 or kn >= len(pts):
            continue
        p1 = pts[kn].co
        p1 = p1.xyz if hasattr(p1, 'xyz') else p1
        if atype == 'TL' and kn + 1 < len(pts):
            # TrafficLight floats along the segment based on `percent`.
            p2 = pts[kn + 1].co
            p2 = p2.xyz if hasattr(p2, 'xyz') else p2
            perc = float(empty.get('inu_accessory_percent', 0.5))
            local = p1 + perc * (p2 - p1)
        else:
            local = p1
        try:
            empty.matrix_world.translation = parent.matrix_world @ local
        except Exception:
            pass

    return 0.5  # next tick in 0.5 s


def _start_accessory_sync_timer():
    try:
        if not bpy.app.timers.is_registered(_accessory_sync_tick):
            bpy.app.timers.register(_accessory_sync_tick)
    except Exception:
        pass


class GTATOOLS_OT_start_accessory_sync(bpy.types.Operator):
    """Включить фоновую синхронизацию позиций path accessory'ев
    с их родительскими Curve'ами"""
    bl_idname = "gtatools.start_accessory_sync"
    bl_label = "INU: Start Accessory Sync"
    bl_options = {'REGISTER'}

    def execute(self, context):
        _start_accessory_sync_timer()
        self.report({'INFO'}, T("Auto-sync включён"))
        return {'FINISHED'}


# ── #9 Debug overlay (NodeID / LinkID / NaviID in viewport) ───────
# Uses gpu+blf draw handler on SpaceView3D — same technique as our
# floater framework. Only renders when toggled on; off by default
# so heavy maps don't lag.

_DEBUG_OVERLAY_STATE = {'handler': None, 'show_node_info': False,
                        'show_navi': False}


def _draw_path_debug_overlay():
    try:
        import bpy as _bpy
        import blf
        # Get the 3D viewport region — required to project world→screen.
        ctx = _bpy.context
        region = ctx.region
        rv3d = ctx.region_data
        if region is None or rv3d is None:
            return
    except Exception:
        return

    try:
        from bpy_extras import view3d_utils
    except Exception:
        return

    font_id = 0
    blf.size(font_id, 11)
    blf.color(font_id, 1.0, 1.0, 0.0, 1.0)

    shown = 0
    SHOW_LIMIT = 80  # cap labels to avoid 1000-text spam on full map

    if _DEBUG_OVERLAY_STATE.get('show_node_info'):
        for obj in _bpy.data.objects:
            if shown >= SHOW_LIMIT:
                break
            pt = obj.get('path_type', '')
            if not pt.startswith('nodes_') or obj.hide_get():
                continue
            mw = obj.matrix_world
            node_ids = obj.get('node_ids', [])
            node_areas = obj.get('node_areas', [])
            for i, v in enumerate(obj.data.vertices):
                if shown >= SHOW_LIMIT:
                    break
                world = mw @ v.co
                co_2d = view3d_utils.location_3d_to_region_2d(
                    region, rv3d, world)
                if co_2d is None:
                    continue
                nid = int(node_ids[i]) if i < len(node_ids) else i
                aid = int(node_areas[i]) if i < len(node_areas) else -1
                blf.position(font_id, co_2d.x + 4, co_2d.y + 4, 0)
                blf.draw(font_id, f"#{nid}@{aid}")
                shown += 1

    if _DEBUG_OVERLAY_STATE.get('show_navi'):
        blf.color(font_id, 1.0, 0.6, 0.0, 1.0)
        for obj in _bpy.data.objects:
            if shown >= SHOW_LIMIT:
                break
            if obj.get('path_type') != 'nodes_navi' or obj.hide_get():
                continue
            mw = obj.matrix_world
            navi_ids = obj.get('navi_ids', [])
            for i, v in enumerate(obj.data.vertices):
                if shown >= SHOW_LIMIT:
                    break
                world = mw @ v.co
                co_2d = view3d_utils.location_3d_to_region_2d(
                    region, rv3d, world)
                if co_2d is None:
                    continue
                nid = int(navi_ids[i]) if i < len(navi_ids) else i
                blf.position(font_id, co_2d.x + 4, co_2d.y + 4, 0)
                blf.draw(font_id, f"N{nid}")
                shown += 1


class GTATOOLS_OT_toggle_path_debug(bpy.types.Operator):
    """Включить/выключить debug overlay для путей (NodeID/AreaID на нодах)"""
    bl_idname = "gtatools.toggle_path_debug"
    bl_label = "INU: Toggle Path Debug Overlay"
    bl_options = {'REGISTER'}

    target: bpy.props.EnumProperty(
        name=T("Что показать"),
        items=[
            ('NODES', T("Node IDs"), ""),
            ('NAVI',  T("Navi IDs"), ""),
            ('OFF',   T("Выключить всё"), ""),
        ],
        default='NODES',
    )

    def execute(self, context):
        global _DEBUG_OVERLAY_STATE
        if self.target == 'NODES':
            _DEBUG_OVERLAY_STATE['show_node_info'] = not _DEBUG_OVERLAY_STATE['show_node_info']
        elif self.target == 'NAVI':
            _DEBUG_OVERLAY_STATE['show_navi'] = not _DEBUG_OVERLAY_STATE['show_navi']
        else:  # OFF
            _DEBUG_OVERLAY_STATE['show_node_info'] = False
            _DEBUG_OVERLAY_STATE['show_navi'] = False

        any_on = (_DEBUG_OVERLAY_STATE['show_node_info']
                  or _DEBUG_OVERLAY_STATE['show_navi'])

        if any_on and _DEBUG_OVERLAY_STATE['handler'] is None:
            _DEBUG_OVERLAY_STATE['handler'] = bpy.types.SpaceView3D.draw_handler_add(
                _draw_path_debug_overlay, (), 'WINDOW', 'POST_PIXEL')
        elif not any_on and _DEBUG_OVERLAY_STATE['handler'] is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(
                    _DEBUG_OVERLAY_STATE['handler'], 'WINDOW')
            except Exception:
                pass
            _DEBUG_OVERLAY_STATE['handler'] = None

        # Force redraw so the change is visible immediately.
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        return {'FINISHED'}

