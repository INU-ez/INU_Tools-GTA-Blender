# INU_tools.ops.col_surface_ops — COL Surface picker (material assignment) + batch set draw distance.
#
# Phase 3 (2026-04-26): operators moved from __init__.py.

import bpy
from bpy.props import (
    StringProperty, BoolProperty, FloatProperty, IntProperty,
)

from .. import T
from ..tools.compat import safe_icon, inu_icon, material_enable_nodes


def _set_material_base_color(mat, rgba):
    """Set the material's «Основной цвет» (Principled BSDF Base Color) so
    the surface colour shows in the material itself, not just the
    viewport. Falls back to any node exposing a colour input."""
    material_enable_nodes(mat)
    nt = getattr(mat, 'node_tree', None)
    if nt is None:
        return
    # Prefer the Principled BSDF (what the Surface panel shows).
    for node in nt.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            inp = node.inputs.get('Base Color')
            if inp is not None:
                inp.default_value = rgba
            return
    # No Principled node — set the first colour input we can find.
    for node in nt.nodes:
        inp = node.inputs.get('Base Color') or node.inputs.get('Color')
        if inp is not None:
            try:
                inp.default_value = rgba
            except Exception:
                pass
            return
from ..data.surface_materials import (
    GTA_SA_SURFACE_MATERIALS,
    COL_SURFACE_CATEGORIES,
    get_surface_name,
    get_surface_desc,
    get_surface_color,
    get_surface_material_name,
    get_colpoint_name,
    get_favorites,
    toggle_favorite,
)


class GTATOOLS_OT_toggle_col_surface_fav(bpy.types.Operator):
    """Добавить/убрать материал из избранного (★).

    Избранные показываются первыми в списке и отмечаются звёздочкой.
    Список хранится в пользовательских данных — сохраняется между
    файлами и перезапусками Blender."""
    bl_idname = "gtatools.toggle_col_surface_fav"
    bl_label = "INU: Toggle Surface Favorite"
    bl_options = {'INTERNAL'}

    surface_id: IntProperty(default=0, min=0, max=178)

    @classmethod
    def description(cls, context, properties):
        name = get_surface_name(properties.surface_id)
        if properties.surface_id in get_favorites():
            return f"{T('Убрать из избранного')}: {name}"
        return f"{T('В избранное')}: {name}"

    def execute(self, context):
        toggle_favorite(self.surface_id)
        # Redraw the popup so the star + favorites section update in place.
        if context.area is not None:
            context.area.tag_redraw()
        return {'FINISHED'}


class GTATOOLS_OT_set_col_surface(bpy.types.Operator):
    """Назначить тип поверхности GTA SA для COL коллизии"""
    bl_idname = "gtatools.set_col_surface"
    bl_label = "INU: Set COL Surface"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: StringProperty()
    surface_id: IntProperty(default=0, min=0, max=178)
    # 'MATERIAL' (default) → assign to a COL material. 'GRASS' → set the
    # active plants.dat grass entry's surface name (reuses this picker).
    target: StringProperty(default='MATERIAL')
    # True → применить поверхность ко ВСЕМ выделенным COL-объектам (их
    # материалам), а не только к одному. Ставится по Alt / галкой в пикере.
    all_selected: BoolProperty(default=False)

    @classmethod
    def description(cls, context, properties):
        # Dynamic tooltip = human-readable surface description.
        name = get_surface_name(properties.surface_id)
        desc = get_surface_desc(properties.surface_id)
        return f"{properties.surface_id}: {name} — {desc}" if desc else f"{properties.surface_id}: {name}"

    def execute(self, context):
        if self.target == 'GRASS':
            s = context.scene.inu_settings
            entries = s.gtatools_grass_entries
            idx = s.gtatools_grass_index
            if 0 <= idx < len(entries):
                entries[idx].name = get_colpoint_name(self.surface_id)
                if context.area is not None:
                    context.area.tag_redraw()
                return {'FINISHED'}
            self.report({'ERROR'}, T("Нет выбранной записи травы"))
            return {'CANCELLED'}

        # Собираем целевые материалы. По умолчанию — один (по имени / активный).
        # По Alt / галке «Ко всем выделенным» — материалы всех выделенных
        # COL/SHA-объектов (не трогаем DFF/LOD, чтобы не переименовать их
        # материалы в поверхности). Исходный материал добавляем всегда.
        targets = []
        seen = set()

        def _add(m):
            if m is not None and m.name not in seen:
                seen.add(m.name)
                targets.append(m)

        if self.all_selected:
            from ..tools.model_utils import get_model_type
            for o in context.selected_objects:
                if o.type != 'MESH':
                    continue
                mtype, _ = get_model_type(o)
                if mtype not in ('COL', 'SHA'):
                    continue
                for sl in o.material_slots:
                    _add(sl.material)

        picked = bpy.data.materials.get(self.material_name)
        if picked is None:
            # material_name may be stale (auto-rename in an open popup) —
            # fall back to the active object's active material.
            obj = context.active_object
            picked = getattr(obj, 'active_material', None) if obj else None
        _add(picked)

        if not targets:
            self.report({'ERROR'}, f"Material not found: {self.material_name}")
            return {'CANCELLED'}

        name = get_surface_name(self.surface_id)
        col = get_surface_color(self.surface_id)
        # Auto-rename to <id>_<NAME> + colour by surface (Base Color +
        # viewport display). Best-effort — failure must not block assignment.
        for mat in targets:
            mat.inu.col_mat_index = self.surface_id
            try:
                mat.name = get_surface_material_name(self.surface_id)
            except Exception:
                pass
            try:
                _set_material_base_color(mat, col)
            except Exception:
                pass
            try:
                mat.diffuse_color = col
            except Exception:
                pass

        if len(targets) == 1:
            self.report({'INFO'}, f"{T('Surface ID назначен:')} "
                        f"{targets[0].name} = {self.surface_id} ({name})")
        else:
            self.report({'INFO'}, f"{T('Surface ID назначен материалам:')} "
                        f"{len(targets)} → {self.surface_id} ({name})")
        return {'FINISHED'}


class GTATOOLS_OT_col_surface_menu(bpy.types.Operator):
    """Выбрать тип поверхности для COL материала.

    Alt+клик — сразу «ко всем выделенным COL» (можно и галкой в пикере)."""
    bl_idname = "gtatools.col_surface_menu"
    bl_label = "INU: Surface Type"
    bl_options = {'REGISTER', 'UNDO'}

    material_name: StringProperty()
    # Passed straight through to gtatools.set_col_surface (MATERIAL/GRASS).
    target: StringProperty(default='MATERIAL')
    # Применять выбранную поверхность ко всем выделенным COL. Пред-ставится
    # по Alt при открытии пикера, плюс видимая галка в самом пикере.
    all_selected: BoolProperty(
        name=T("Ко всем выделенным COL"),
        description=T("Назначить поверхность материалам ВСЕХ выделенных "
                      "COL-объектов, а не только текущему"),
        default=False)

    # Search filter
    search: StringProperty(
        name="Search",
        description=T("Фильтр типов поверхности"),
        default="",
        options={'TEXTEDIT_UPDATE'},
    )

    # Category expand toggles (collapsed by default)
    cat_default: BoolProperty(default=False)
    cat_concrete: BoolProperty(default=False)
    cat_gravel: BoolProperty(default=False)
    cat_grass: BoolProperty(default=False)
    cat_dirt: BoolProperty(default=False)
    cat_sand: BoolProperty(default=False)
    cat_glass: BoolProperty(default=False)
    cat_wood: BoolProperty(default=False)
    cat_metal: BoolProperty(default=False)
    cat_stone: BoolProperty(default=False)
    cat_vegetation: BoolProperty(default=False)
    cat_water: BoolProperty(default=False)
    cat_misc: BoolProperty(default=False)

    _cat_props = {
        "Default": "cat_default", "Concrete": "cat_concrete", "Gravel": "cat_gravel",
        "Grass": "cat_grass", "Dirt": "cat_dirt", "Sand": "cat_sand",
        "Glass": "cat_glass", "Wood": "cat_wood", "Metal": "cat_metal",
        "Stone": "cat_stone", "Vegetation": "cat_vegetation", "Water": "cat_water",
        "Misc": "cat_misc",
    }

    def execute(self, context):
        return {'CANCELLED'}

    def invoke(self, context, event):
        self.search = ""
        # Alt при открытии пикера = сразу «ко всем выделенным» (блендеровское
        # соглашение). Галку в пикере тоже можно переключить вручную.
        self.all_selected = bool(getattr(event, 'alt', False))
        return context.window_manager.invoke_popup(self, width=360)

    def _draw_item(self, container, sid, name, favs):
        """One material row: [★ toggle][id: NAME]. Description is shown on
        hover via the select operator's dynamic tooltip."""
        row = container.row(align=True)
        is_fav = sid in favs
        star = 'SOLO_ON' if is_fav else 'SOLO_OFF'
        fav_op = row.operator("gtatools.toggle_col_surface_fav", text="",
                              **inu_icon(safe_icon(star)), emboss=False)
        fav_op.surface_id = sid
        op = row.operator("gtatools.set_col_surface", text=f"{sid}: {name}")
        op.material_name = self.material_name
        op.surface_id = sid
        op.target = self.target
        op.all_selected = self.all_selected

    def draw(self, context):
        layout = self.layout
        # Галка «ко всем выделенным» — только для COL-материалов (не для GRASS).
        if self.target == 'MATERIAL':
            layout.prop(self, "all_selected",
                        **inu_icon(safe_icon('RESTRICT_SELECT_OFF')))
        layout.prop(self, "search", text="", **inu_icon(safe_icon('VIEWZOOM')))

        search_lower = self.search.lower()
        name_lookup = {sid: name for sid, name, desc in GTA_SA_SURFACE_MATERIALS}
        favs = get_favorites()

        if search_lower:
            flow = layout.column_flow(columns=2, align=True)
            found = False
            for sid, name, desc in GTA_SA_SURFACE_MATERIALS:
                if (search_lower not in name.lower()
                        and search_lower not in str(sid)
                        and search_lower not in desc.lower()):
                    continue
                self._draw_item(flow, sid, name, favs)
                found = True
            if not found:
                layout.label(text=T("Ничего не найдено"), **inu_icon(safe_icon('INFO')))
            return

        # Favorites pinned to the top (starred = "important" materials).
        if favs:
            box = layout.box()
            box.label(text=T("Избранное"), **inu_icon(safe_icon('SOLO_ON')))
            flow = box.column_flow(columns=2, align=True)
            for sid in sorted(favs):
                self._draw_item(flow, sid, name_lookup.get(sid, f"UNKNOWN_{sid}"), favs)

        for cat_name, cat_ids in COL_SURFACE_CATEGORIES:
            prop_name = self._cat_props.get(cat_name, "")
            is_open = getattr(self, prop_name, False)

            box = layout.box()
            row = box.row()
            icon = safe_icon('DISCLOSURE_TRI_DOWN') if is_open else 'DISCLOSURE_TRI_RIGHT'
            row.prop(self, prop_name, text=f"{cat_name} ({len(cat_ids)})", **inu_icon(icon), emboss=False)

            if is_open:
                flow = box.column_flow(columns=2, align=True)
                for sid in cat_ids:
                    self._draw_item(flow, sid, name_lookup.get(sid, f"UNKNOWN_{sid}"), favs)


# =============================================================================

# ── Unified Material panel (Phase 1 of UI redesign) ──────────────────
#
# Replaces 3 separate Properties→Material panels (col_material_panel,
# material_effects_panel, gta_material_panel) with a single panel that
# shows one of three tab views — SURFACE / EFFECTS / PIPELINE.
#
# Tab state lives on the material itself (mat.inu.material_tab) so it
# survives switching between materials and reload. Default = SURFACE.
#
# Helpers below contain the original draw bodies verbatim — only the
# enclosing class/method wrapper is gone. Each takes (layout, mat) so
# they're testable and reusable from elsewhere.

class GTATOOLS_OT_auto_find_lod(bpy.types.Operator):
    """Найти LOD выделенных моделей в сцене по имени и подставить их в «LOD partner».

    Для каждой выделенной модели ищется её LOD-двойник среди объектов сцены
    (то же базовое имя, а имя несёт маркер lod — распознаётся тем же
    классификатором, что и весь аддон) и записывается в lod_object. Сами
    LOD-объекты в выделении пропускаются."""
    bl_idname = "gtatools.auto_find_lod"
    bl_label = "INU: Найти LOD автоматически"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..tools.model_utils import get_model_type
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        if not sel:
            self.report({'WARNING'}, T("Выдели модели"))
            return {'CANCELLED'}
        # Индекс всех LOD сцены по базовому имени (первый побеждает).
        lod_by_base = {}
        for o in context.scene.objects:
            if o.type != 'MESH':
                continue
            mt, base = get_model_type(o)
            if mt == 'LOD' and base:
                lod_by_base.setdefault(base.rstrip('_'), o)
        found = missing = 0
        for obj in sel:
            inu = getattr(obj, 'inu', None)
            if inu is None:
                continue
            mt, base = get_model_type(obj)
            if mt == 'LOD':
                continue                       # сам LOD — не ищем ему LOD
            lod = lod_by_base.get((base or '').rstrip('_'))
            if lod is not None and lod is not obj:
                inu.lod_object = lod
                found += 1
            else:
                missing += 1
        self.report({'INFO'},
                    T("LOD найден: {0}, не найдено: {1}").format(found, missing))
        return {'FINISHED'}


class GTATOOLS_OT_batch_set_distance(bpy.types.Operator):
    """Задать Draw Distance и/или LOD Distance всем выделенным MESH-объектам.

    По умолчанию поля заполняются значениями активного объекта — можно
    изменить и применить к выделению одним действием. Галочки слева
    выбирают какие именно поля переписывать (удобно менять только одно)"""
    bl_idname = "gtatools.batch_set_distance"
    bl_label = "INU: Apply distances to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    apply_draw: BoolProperty(
        name=T("Применить Draw Dist"),
        default=True,
    )
    draw_distance: FloatProperty(
        name="Draw Dist",
        default=299.0, min=0.0, max=10000.0,
    )
    apply_lod: BoolProperty(
        name=T("Применить LOD Dist"),
        default=False,
    )
    lod_draw_distance: FloatProperty(
        name="LOD Dist",
        default=999.0, min=0.0, max=10000.0,
    )

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        # Prefill from the active object so user can tweak from a known state.
        obj = context.active_object
        if obj and obj.type == 'MESH' and hasattr(obj, 'inu'):
            self.draw_distance = obj.inu.draw_distance
            self.lod_draw_distance = obj.inu.lod_draw_distance
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "apply_draw", text="")
        sub = row.row(align=True)
        sub.active = self.apply_draw
        sub.prop(self, "draw_distance")

        row = layout.row(align=True)
        row.prop(self, "apply_lod", text="")
        sub = row.row(align=True)
        sub.active = self.apply_lod
        sub.prop(self, "lod_draw_distance")

        n = sum(1 for o in context.selected_objects if o.type == 'MESH')
        layout.label(text=f"{n} {T('объектов будет изменено')}", **inu_icon(safe_icon('INFO')))

    def execute(self, context):
        if not self.apply_draw and not self.apply_lod:
            self.report({'WARNING'}, T("Включите хотя бы одну галочку"))
            return {'CANCELLED'}
        count = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH' or not hasattr(obj, 'inu'):
                continue
            if self.apply_draw:
                obj.inu.draw_distance = self.draw_distance
            if self.apply_lod:
                obj.inu.lod_draw_distance = self.lod_draw_distance
            count += 1
        self.report({'INFO'}, f"{T('Изменено:')} {count}")
        return {'FINISHED'}

