# INU_tools.ops.zon_ops — import / export GTA SA zone files (data/map.zon,
# data/info.zon) as editable wireframe boxes in the viewport.
#
# See core/zon.py for the file format and ui/panels.py for the «map.zon»
# panel. One imported file = one collection (ZON_map, ZON_info…), so two
# zone files can live in the same scene without mixing on export.

import os
import shutil

import bpy
from bpy.props import StringProperty
from mathutils import Vector

from .. import T
from ..core import zon as zon_core
from .ipl_sections import _get_or_create_collection, _make_cube_mesh


# Custom property that marks an object as a .zon zone box.
TAG = 'inu_zon'

# Viewport object colour per zone type — visible in Object-Color shading,
# enough to tell map / navigation / weather zones apart at a glance.
_TYPE_COLORS = {
    0: (0.25, 0.55, 1.00, 1.0),   # navigation / info zone (info.zon)
    1: (0.60, 0.60, 1.00, 1.0),
    2: (0.90, 0.75, 0.25, 1.0),
    3: (0.30, 0.85, 0.35, 1.0),   # map zone (map.zon)
    4: (1.00, 0.45, 0.15, 1.0),   # weather zone (mod extension)
}
_DEFAULT_COLOR = (0.70, 0.70, 0.70, 1.0)


def collection_name(filepath: str) -> str:
    """map.zon → ZON_map. Keeps each file's zones in their own collection."""
    base = os.path.splitext(os.path.basename(filepath))[0]
    return f"ZON_{base or 'zon'}"


def zone_objects(source=None):
    """All zone boxes in `source` (a collection or an iterable of objects),
    or in the whole file when omitted."""
    if source is None:
        source = bpy.data.objects
    elif isinstance(source, bpy.types.Collection):
        source = source.objects
    return [o for o in source if o.get(TAG)]


def _zon_collections():
    return [c for c in bpy.data.collections if c.name.startswith("ZON_")]


def _collection_of(obj):
    for c in obj.users_collection:
        if c.name.startswith("ZON_"):
            return c
    return None


def _split_lines(value) -> list:
    text = str(value or '')
    return text.split('\n') if text else []


# ── Import ────────────────────────────────────────────────────────────

def _clear_zones(col):
    """Drop the previous boxes of this file — re-import replaces, never
    stacks duplicates on top of the old ones."""
    for obj in zone_objects(col):
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def import_zon(filepath: str, context=None):
    """Read a .zon and build one wireframe box per zone.

    Returns (objects, ZonFile) — the caller reports the counts/warnings."""
    zf = zon_core.read_zon(filepath)

    col = _get_or_create_collection(collection_name(filepath))
    _clear_zones(col)
    # File scaffolding rides on the collection so the export can rebuild
    # the file with its original header, comments and line endings.
    col['zon_header'] = "\n".join(zf.header)
    col['zon_section_tail'] = "\n".join(zf.section_tail)
    col['zon_footer'] = "\n".join(zf.footer)
    col['zon_eol'] = zf.eol
    col['zon_source'] = filepath

    objects = []
    for i, z in enumerate(zf.zones):
        (mnx, mny, mnz), (mxx, mxy, mxz) = z.bounds
        center = ((mnx + mxx) / 2, (mny + mxy) / 2, (mnz + mxz) / 2)
        size = (max(mxx - mnx, 0.1), max(mxy - mny, 0.1), max(mxz - mnz, 0.1))
        obj = _make_cube_mesh(f"Zone_{z.name}" if z.name else f"Zone_{i:03d}",
                              center, size, col)
        obj[TAG] = 1
        obj['zon_name'] = z.name
        obj['zon_type'] = z.zone_type
        obj['zon_level'] = z.level
        obj['zon_gxt'] = z.gxt
        obj['zon_comment'] = "\n".join(z.comment)
        obj['zon_raw'] = z.raw
        obj['zon_index'] = i
        obj.color = _TYPE_COLORS.get(z.zone_type, _DEFAULT_COLOR)
        objects.append(obj)
    return objects, zf


# ── Export ────────────────────────────────────────────────────────────

def _strip_dup_suffix(name: str) -> str:
    """`Zone_LA01.001` → `LA01` — Blender's duplicate suffix isn't part of
    the zone name."""
    if len(name) > 4 and name[-4] == '.' and name[-3:].isdigit():
        name = name[:-4]
    return name


def _zone_name(obj) -> str:
    """Renaming the object in the outliner renames the zone; otherwise the
    stored name wins (so a Blender name clash can't corrupt the file)."""
    stored = str(obj.get('zon_name') or '')
    base = obj.name[5:] if obj.name.startswith('Zone_') else obj.name
    base = _strip_dup_suffix(base)
    if stored and base == stored:
        return stored
    return base or stored


def _world_bounds(obj):
    """World-space AABB — correct even when the box is rotated or scaled."""
    mw = obj.matrix_world
    corners = [mw @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(c.x for c in corners),
                 min(c.y for c in corners),
                 min(c.z for c in corners)))
    mx = Vector((max(c.x for c in corners),
                 max(c.y for c in corners),
                 max(c.z for c in corners)))
    return mn, mx


def _order_key(obj):
    # Zones keep their file order: the engine returns the FIRST zone that
    # matches a point, so reordering silently changes behaviour.
    return (int(obj.get('zon_index', 10 ** 6)), obj.name)


def object_to_zone(obj) -> zon_core.Zone:
    mn, mx = _world_bounds(obj)
    return zon_core.Zone(
        name=_zone_name(obj),
        zone_type=int(obj.get('zon_type', 0)),
        x1=mn.x, y1=mn.y, z1=mn.z,
        x2=mx.x, y2=mx.y, z2=mx.z,
        level=int(obj.get('zon_level', 0)),
        gxt=str(obj.get('zon_gxt') or zon_core.DEFAULT_GXT),
        comment=_split_lines(obj.get('zon_comment')),
        raw=str(obj.get('zon_raw') or ''),
    )


def _clean_zone_name(name: str) -> str:
    """Object name → zone name: no duplicate suffix, no spaces (the engine
    splits lines on whitespace, so a space would shift every column)."""
    return _strip_dup_suffix(name).replace(' ', '_')


def zone_from_bbox(obj) -> zon_core.Zone:
    """Zone covering any object's world bounding box. Lets the user select
    a building / a piece of terrain and get a ready zone line for it."""
    mn, mx = _world_bounds(obj)
    return zon_core.Zone(
        name=_clean_zone_name(obj.name),
        zone_type=3,          # map zone — what map.zon is made of
        x1=mn.x, y1=mn.y, z1=mn.z,
        x2=mx.x, y2=mx.y, z2=mx.z,
    )


def lines_for_objects(objects) -> list:
    """The .zon text lines for these objects — zone boxes keep everything
    they were imported with, any other object is measured by its bbox."""
    lines = []
    for obj in sorted(objects, key=_order_key):
        z = object_to_zone(obj) if obj.get(TAG) else zone_from_bbox(obj)
        lines.append(zon_core.zone_line(z))
    return lines


def collect_for_export(context, filepath):
    """Which boxes go into `filepath`, in priority order:
    selection → the collection named after the file → the only ZON_*
    collection in the scene → every zone box. Returns (objects, note)."""
    selected = zone_objects(context.selected_objects)
    if selected:
        return selected, ''

    col = bpy.data.collections.get(collection_name(filepath))
    if col:
        return zone_objects(col), ''

    cols = _zon_collections()
    if len(cols) == 1:
        return zone_objects(cols[0]), cols[0].name
    if len(cols) > 1:
        return [], 'ambiguous'
    return zone_objects(), ''


def export_zon(filepath: str, objects, context=None):
    """Write zone boxes to a .zon. Returns (ZonFile, duplicate_names)."""
    objects = sorted(objects, key=_order_key)

    zf = zon_core.ZonFile()
    # Reuse the source file's header / trailing lines when these boxes came
    # from an import; a scene-built file just gets the defaults.
    col = _collection_of(objects[0]) if objects else None
    if col is not None:
        zf.header = _split_lines(col.get('zon_header'))
        zf.section_tail = _split_lines(col.get('zon_section_tail'))
        zf.footer = _split_lines(col.get('zon_footer'))
        zf.eol = str(col.get('zon_eol') or "\r\n")

    seen = {}
    duplicates = []
    for obj in objects:
        z = object_to_zone(obj)
        if z.name in seen:
            duplicates.append(z.name)
        seen[z.name] = True
        zf.zones.append(z)

    zon_core.write_zon(filepath, zf)
    return zf, duplicates


# ── Operators ─────────────────────────────────────────────────────────

def _report_reversed(op, zones):
    """A zone whose min/max pair is swapped never matches in game — the
    engine tests `x >= x1 && x <= x2`. Worth saying out loud."""
    bad = [z.name for z in zones if z.is_reversed]
    if not bad:
        return
    print("[INU zon] reversed bbox (never matches in game): " + ", ".join(bad))
    shown = ", ".join(bad[:4]) + ("…" if len(bad) > 4 else "")
    op.report({'WARNING'},
              f"{T('Зон с перевёрнутым bbox (в игре не сработают):')} "
              f"{len(bad)} — {shown}")


class GTATOOLS_OT_import_zon(bpy.types.Operator):
    """Импорт зон из map.zon / info.zon — каждая зона становится
    рамкой-боксом в сцене. Повторный импорт того же файла заменяет
    старые боксы"""
    bl_idname = "gtatools.import_zon"
    bl_label = "INU: Import Zones (.zon)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.zon", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = context.scene.inu_settings.gtatools_zon_path
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath or not os.path.isfile(self.filepath):
            self.report({'ERROR'}, T("Файл не выбран"))
            return {'CANCELLED'}
        try:
            objects, zf = import_zon(self.filepath, context)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка чтения:')} {e}")
            return {'CANCELLED'}

        context.scene.inu_settings.gtatools_zon_path = self.filepath
        for w in zf.warnings:
            print(f"[INU zon] {os.path.basename(self.filepath)} — {w}")
        _report_reversed(self, zf.zones)
        msg = (f"{T('Зон импортировано:')} {len(objects)} → "
               f"{collection_name(self.filepath)}")
        if zf.warnings:
            msg += f"  ({T('замечаний:')} {len(zf.warnings)} — {T('см. консоль')})"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_export_zon(bpy.types.Operator):
    """Экспорт зон обратно в map.zon / info.zon. Пишутся выделенные боксы,
    а если ничего не выделено — вся коллекция ZON_<имя файла>.
    Незатронутые зоны сохраняются строка в строку, старый файл
    копируется рядом как .bak"""
    bl_idname = "gtatools.export_zon"
    bl_label = "INU: Export Zones (.zon)"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.zon", options={'HIDDEN'})

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = (context.scene.inu_settings.gtatools_zon_path
                             or "map.zon")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, T("Файл не выбран"))
            return {'CANCELLED'}
        if not self.filepath.lower().endswith('.zon'):
            self.filepath += '.zon'

        objects, note = collect_for_export(context, self.filepath)
        if note == 'ambiguous':
            self.report({'ERROR'},
                        T("В сцене несколько наборов зон — выдели нужные "
                          "боксы или назови файл как коллекцию ZON_*"))
            return {'CANCELLED'}
        if not objects:
            self.report({'WARNING'}, T("Нет зон для экспорта"))
            return {'CANCELLED'}

        # Back up the untouched original once, never our own re-exports.
        bak = self.filepath + '.bak'
        try:
            if os.path.isfile(self.filepath) and not os.path.isfile(bak):
                shutil.copy2(self.filepath, bak)
        except OSError as e:
            print(f"[INU zon] backup failed: {e}")

        try:
            zf, duplicates = export_zon(self.filepath, objects, context)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'CANCELLED'}

        context.scene.inu_settings.gtatools_zon_path = self.filepath
        # DAT-27: exactly 10 fields, names ≤ 7, types 0/1/3, 380/39 tables.
        try:
            from ..core.textdata_lint import check_zones
            from .textdata_audit import report_lint
            report_lint(self, os.path.basename(self.filepath),
                        *check_zones(zf.zones))
        except Exception as e:                       # noqa: BLE001
            print(f"[INU lint] zon audit failed: {e}")
        # No reversed-bbox check here: a box always has a normalised bbox,
        # so only the import (which reads the raw lines) can spot those.
        if duplicates:
            self.report({'WARNING'},
                        f"{T('Повторяющиеся имена зон:')} "
                        f"{', '.join(sorted(set(duplicates))[:4])}")
        msg = f"{T('Зон записано:')} {len(zf.zones)} → {os.path.basename(self.filepath)}"
        if note:
            msg += f"  ({note})"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_zon_copy_lines(bpy.types.Operator):
    """Сгенерировать строки зон для выделенных объектов и положить их в
    буфер обмена — можно сразу вставить в map.zon. Строки заодно кладутся
    в текстовый блок INU_map_zon (Text Editor). Для обычного меша зона
    считается по его габаритам"""
    bl_idname = "gtatools.zon_copy_lines"
    bl_label = "INU: Copy zone lines"
    bl_options = {'REGISTER'}

    # Текстовый блок с последним результатом — чтобы строки можно было
    # посмотреть/поправить, а не только вслепую вставить из буфера.
    TEXT_NAME = "INU_map_zon"

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def execute(self, context):
        objects = list(context.selected_objects)
        if not objects:
            self.report({'WARNING'}, T("Ничего не выделено"))
            return {'CANCELLED'}

        lines = lines_for_objects(objects)
        text = "\n".join(lines)
        context.window_manager.clipboard = text
        print("[INU zon] generated lines:\n" + text)

        txt = bpy.data.texts.get(self.TEXT_NAME)
        if txt is None:
            txt = bpy.data.texts.new(self.TEXT_NAME)
        txt.clear()
        txt.write(text + "\n")

        n_boxes = sum(1 for o in objects if o.get(TAG))
        msg = f"{T('Строк в буфере:')} {len(lines)}"
        if n_boxes < len(objects):
            msg += f"  ({T('по габаритам:')} {len(objects) - n_boxes})"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_add_zon_zone(bpy.types.Operator):
    """Создать новую зону — бокс 100×100×100 в позиции 3D-курсора.
    Имя, тип, уровень и GXT-ключ правятся ниже в панели"""
    bl_idname = "gtatools.add_zon_zone"
    bl_label = "INU: Add Zone (.zon)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.inu_settings
        path = s.gtatools_zon_path or "map.zon"
        col = _get_or_create_collection(collection_name(path))
        loc = context.scene.cursor.location
        obj = _make_cube_mesh("Zone_NEW", (loc.x, loc.y, loc.z),
                              (100.0, 100.0, 100.0), col)
        obj[TAG] = 1
        obj['zon_name'] = "NEW"
        # 3 = map zone: what map.zon is made of. info.zon zones use 0.
        obj['zon_type'] = 3
        obj['zon_level'] = 0
        obj['zon_gxt'] = zon_core.DEFAULT_GXT
        obj['zon_comment'] = ''
        obj['zon_raw'] = ''
        # New zones go last — the engine returns the first matching zone,
        # so appending can't shadow anything that already worked.
        existing = [int(o.get('zon_index', 0)) for o in zone_objects(col)
                    if o is not obj]
        obj['zon_index'] = (max(existing) + 1) if existing else 0
        obj.color = _TYPE_COLORS[3]

        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        self.report({'INFO'}, f"{T('Зона создана:')} {obj.name}")
        return {'FINISHED'}
