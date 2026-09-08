# INU_tools.ui.panels — every Blender Panel and UIList class.
#
# Phase 4 (2026-04-26): all panels moved out of __init__.py into a
# single module. Material panel and its 3 draw helpers also recovered
# from ops/col_surface_ops.py where Phase 3 batch script wrongly
# moved them.
#
# Helpers used by draw() methods (e.g. _draw_label_with_info, surface
# name lookup, particle enum items) live in __init__.py — pulled in
# lazily inside each method. T() is top-level since panel class bodies
# use T(...) at class-definition time.

import ast
import bpy

from .. import T
from ..tools import compat
from ..tools import draw_cache
from ..tools.compat import safe_icon, inu_icon
from ..ui.registry import apply_order


def _draw_doc_help(layout, section):
    """Draw a HELP (?) button in a panel header that opens the docs at THIS
    panel's own section (``section`` is a key from _DOC_SECTIONS in
    ops/onboarding_ops — resolved to the right anchor for the UI language).
    Reused by every top-level panel so each tab links to its doc section."""
    row = layout.row(align=True)
    row.operator("gtatools.open_docs", text="",
                 **inu_icon(safe_icon('HELP')), emboss=False).section = section


# ── 2DFX custom-property tooltips ──
# These five Light-2DFX fields are stored as raw custom IDProperties on the
# Empty (not PropertyGroup fields), so their hover-tooltip comes from
# `id_properties_ui(...).description`, which is set per-object. We apply it
# lazily on first panel draw so EXISTING scenes also get the tooltips
# (a marker set keyed by object pointer keeps it one-shot per object).
_2DFX_PROP_TIPS = {
    '2dfx_corona_far_clip':
        "Дальность отрисовки короны (метры). Дальше этой дистанции от "
        "камеры корона перестаёт рисоваться. Больше — видна издалека",
    '2dfx_pointlight_range':
        "Радиус заливающего света лампы (метры) — на каком расстоянии "
        "лампа подсвечивает окружение в игре. 0 — не освещает геометрию",
    '2dfx_corona_enable_reflection':
        "1 — корона отражается на мокром асфальте/воде; 0 — без отражения",
    '2dfx_shadow_z_distance':
        "На сколько метров вниз проецируется световое пятно (тень) от "
        "лампы. 0 — пятно прямо на уровне лампы",
    '2dfx_shadow_color_multiplier':
        "Яркость/насыщенность светового пятна на земле (0–255). "
        "Больше — ярче и контрастнее пятно",
}
_2dfx_tips_done = set()


def _ensure_2dfx_tips(obj):
    """Set hover descriptions on the Light-2DFX custom properties (once)."""
    if obj is None or not hasattr(obj, 'id_properties_ui'):
        return
    key = obj.as_pointer()
    if key in _2dfx_tips_done:
        return
    for prop, tip in _2DFX_PROP_TIPS.items():
        if prop in obj:
            try:
                obj.id_properties_ui(prop).update(description=T(tip))
            except Exception:
                pass
    _2dfx_tips_done.add(key)


def _obj_has_uv_anim_material(obj):
    """True if any material slot on this mesh has UV animation enabled
    (``mat.inu.uv_anim_write``).

    Night vertex colors silently DISABLE UV animation in retail
    gtasa.exe — verified in-game and documented in the ponz2009 SA
    modding tips («補記»: «на dff с ночными вершинными цветами UV-аним
    в SA не работает»). librw/euryopa ignore night vcols, so the anim
    plays there — which is why it looked like a DFF bug. It isn't: the
    DFF Flags panel warns when Night + UV-anim coexist so the user
    drops the night layer instead of chasing a phantom format issue.
    """
    if obj is None or obj.type != 'MESH':
        return False
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None:
            continue
        m_inu = getattr(mat, 'inu', None)
        if m_inu is not None and getattr(m_inu, 'uv_anim_write', False):
            return True
    return False


def _draw_material_surface(layout, mat):
    """SURFACE tab — COL physical surface type + Day/Night light."""
    from .. import get_surface_name
    inu = mat.inu
    current_id = inu.col_mat_index
    current_name = get_surface_name(current_id)

    row = layout.row(align=True)
    row.prop(inu, "col_mat_index", text="ID")
    op = row.operator("gtatools.col_surface_menu", text="", **inu_icon(safe_icon('VIEWZOOM')))
    op.material_name = mat.name

    layout.label(text=f"{current_name}", **inu_icon(safe_icon('PHYSICS')))

    layout.separator()

    row = layout.row(align=True)
    row.prop(inu, "col_day_light", text=T("Дневной свет"))
    row.prop(inu, "col_night_light", text=T("Ночной свет"))

    layout.prop(inu, "col_brightness", text=T("Яркость"))



def _draw_material_effects(layout, mat):
    """EFFECTS tab — RW material effects (env map, bump, specular,
    reflection, dual texture, UV anim) + ambient + vehicle color slot."""
    inu = mat.inu

    # RW surface lighting coefficients (Ambient / Specular / Diffuse). They
    # scale how the material is lit — diffuse 0.5 instead of 1.0 renders the
    # model at half brightness — so they belong in the UI, not just silently
    # round-tripped. (DragonFF shows the same three under "Material settings".)
    col = layout.column(align=True)
    col.label(text=T("RW-затенение:"), **inu_icon(safe_icon('SHADING_RENDERED')))
    col.prop(inu, "ambient", text=T("Фоновое (ambient)"))
    col.prop(inu, "surf_specular", text=T("Зеркальное (specular)"))
    col.prop(inu, "surf_diffuse", text=T("Рассеянное (diffuse)"))

    # Цвет материала + прозрачность (нативный Blender — экспорт берёт цвет из
    # diffuse_color, а альфа из его 4-го канала). Свотч RGBA даёт и цвет, и альфу.
    col = layout.column(align=True)
    col.label(text=T("Цвет / прозрачность:"), **inu_icon(safe_icon('COLOR')))
    col.prop(mat, "diffuse_color", text=T("Цвет (RGBA)"))
    # На 4.2+ (EEVEE Next) прозрачностью управляет surface_render_method
    # («Метод рендеринга»: альфа = Смешанный) + use_transparency_overlap
    # («Перекрытие прозрачности»: у альфы должно быть ВЫКЛ). Legacy
    # blend_method там ни на что не влияет — рисуем только его замену.
    if hasattr(mat, "surface_render_method"):
        col.prop(mat, "surface_render_method", text=T("Метод рендеринга"))
        col.prop(mat, "use_transparency_overlap",
                 text=T("Перекрытие прозрачности"))
    elif hasattr(mat, "blend_method"):
        col.prop(mat, "blend_method", text=T("Режим прозрачности"))
        if hasattr(mat, "show_transparent_back"):
            col.prop(mat, "show_transparent_back",
                     text=T("Перекрытие прозрачности"))

    # Текстура: имя (только чтение) + фильтрация/адресация + маска. Фильтр и
    # адресация теперь round-trip'ятся (раньше экспорт писал дефолт и терял их).
    tbox = layout.box().column(align=True)
    tbox.label(text=T("Текстура:"), **inu_icon(safe_icon('TEXTURE')))
    # Превью + выбор картинки (первая Image-нода материала).
    _img_node = None
    if compat.material_uses_nodes(mat):
        for _n in mat.node_tree.nodes:
            if _n.type == 'TEX_IMAGE':
                _img_node = _n
                break
    if _img_node:
        tbox.template_ID_preview(_img_node, "image", rows=2, cols=4,
                                 open="image.open")
    # Имя текстуры — редактируемое (авторитетно для экспорта).
    tbox.prop(inu, "texture_name", text=T("Имя"))
    tbox.prop(inu, "tex_filter", text=T("Фильтрация"))
    row = tbox.row(align=True)
    row.prop(inu, "tex_addr_u", text=T("Адресация U"))
    row.prop(inu, "tex_addr_v", text="V")
    tbox.prop(inu, "mask_texture", text=T("Маска"))

    # Скопировать настройки этого материала на материалы выделенных объектов.
    layout.operator("gtatools.copy_material_settings",
                    text=T("Копировать на выделенные"),
                    **inu_icon(safe_icon('COPYDOWN')))

    # `s` — глобальное UI-состояние сворачиваемых секций (не пер-материал).
    s = getattr(bpy.context.scene, 'inu_settings', None)

    def _mat_section(prop, label):
        """Заголовок сворачиваемой секции. True — секция раскрыта."""
        if s is None:
            return True
        open_ = getattr(s, prop)
        hdr = layout.row(align=True)
        hdr.prop(s, prop, text=label, emboss=False,
                 **inu_icon(safe_icon('TRIA_DOWN') if open_ else 'TRIA_RIGHT'))
        return open_

    # ── Машина: пресеты + слот цвета + Paintjob (сворачиваемо) ──
    if _mat_section("gtatools_mat_show_vehicle", T("Машина")):
        # Быстрые пресеты материалов машин — один клик.
        layout.label(text=T("Быстрые пресеты:"), **inu_icon(safe_icon('PRESET')))
        qrow = layout.row(align=True)
        qrow.operator("gtatools.material_preset", text=T("Стекло")).preset = 'VEHICLE_GLASS'
        qrow.operator("gtatools.material_preset", text="Хром").preset = 'CHROME'
        qrow.operator("gtatools.material_preset", text=T("Краска")).preset = 'VEHICLE'
        qrow.operator("gtatools.material_preset", text=T("Сброс")).preset = 'GENERIC'

        box = layout.box()
        row = box.row()
        row.label(text=T("Слот цвета машины:"), **inu_icon(safe_icon('AUTO')))
        box.prop(inu, "vehicle_color_slot", text="")
        if inu.vehicle_color_slot != 'NONE':
            box.operator("gtatools.sa_vehicle_preset", text=T("Применить SA Vehicle defaults"), **inu_icon(safe_icon('SHADING_RENDERED')))

        # Vehicle Paintjob (Pay'n'Spray alt textures) — packed into the
        # vehicle TXD as <base>_paintjob1/2, swapped in-game at a spray shop.
        pj_box = layout.box()
        pj_row = pj_box.row()
        pj_row.label(text=T("Paintjob (Pay'n'Spray):"), **inu_icon(safe_icon('BRUSH_DATA')))
        has_pj = bool(inu.paintjob_alt_1 or inu.paintjob_alt_2)
        if has_pj:
            pj_row.operator("gtatools.validate_paintjobs",
                            text="", **inu_icon(compat.ICON_CHECK))
        pj_box.template_ID(inu, "paintjob_alt_1", open="image.open",
                           text=T("Раскраска 1"))
        pj_box.template_ID(inu, "paintjob_alt_2", open="image.open",
                           text=T("Раскраска 2"))
        if has_pj and not (inu.paintjob_alt_1 and inu.paintjob_alt_2):
            pj_box.label(
                text=T("Нужны обе альтернативы (1 и 2)"),
                **inu_icon(safe_icon('ERROR')))

    # ── GTA-эффекты: env map / bump / reflection / specular / dual / UV (сворачиваемо) ──
    if _mat_section("gtatools_mat_show_fx", T("GTA-эффекты")):
        # Все тумблеры эффектов склеены в один fused-блок.
        outer = layout.column(align=True)

        box = outer.box().column(align=True)
        box.prop(inu, "export_env_map", text=T("Карта окружения"))
        if inu.export_env_map:
            box.prop(inu, "env_map_tex", text=T("Текстура"))
            box.prop(inu, "env_map_coef", text=T("Коэффициент"))
            box.prop(inu, "env_map_fb_alpha", text=T("Использовать FB Alpha"))

        box = outer.box().column(align=True)
        box.prop(inu, "export_bump_map", text=T("Карта высот"))
        if inu.export_bump_map:
            box.prop(inu, "bump_map_tex", text=T("Текстура карты высот"))

        box = outer.box().column(align=True)
        box.prop(inu, "export_reflection", text=T("Отражение материала"))
        if inu.export_reflection:
            row = box.row(align=True)
            row.prop(inu, "reflection_scale_x", text=T("Масштаб X"))
            row.prop(inu, "reflection_scale_y", text="Y")
            row = box.row(align=True)
            row.prop(inu, "reflection_offset_x", text=T("Смещение X"))
            row.prop(inu, "reflection_offset_y", text="Y")
            box.prop(inu, "reflection_intensity", text=T("Интенсивность"))

        box = outer.box().column(align=True)
        box.prop(inu, "export_specular", text=T("Зеркальный материал"))
        if inu.export_specular:
            box.prop(inu, "specular_level", text=T("Уровень зеркальности"))
            box.prop(inu, "specular_texture", text=T("Текстура"))

        box = outer.box().column(align=True)
        box.prop(inu, "export_dual_tex", text="Blend Mode (Src/Dst)")
        if inu.export_dual_tex:
            box.prop(inu, "dual_tex_src_blend", text="Src")
            box.prop(inu, "dual_tex_dst_blend", text="Dst")
            box.prop(inu, "dual_tex_texture", text=T("Текстура"))

        # UV-анимация — тумблер пишет `uv_anim_write` (его проверяет экспортёр).
        box = outer.box().column(align=True)
        box.prop(inu, "uv_anim_write", text=T("UV Анимация"))
        if inu.uv_anim_write:
            box.prop(inu, "animation_name", text=T("Имя анимации"))
            box.prop(inu, "uv_anim_mode", expand=True)
            if inu.uv_anim_mode == 'SCROLL':
                row = box.row(align=True)
                row.prop(inu, "uv_anim_speed_u", text="Speed U")
                row.prop(inu, "uv_anim_speed_v", text="Speed V")
                box.prop(inu, "uv_anim_duration", text=T("Длительность"))
            else:  # KEYFRAME
                box.label(text=T("Ключи — в UV-редакторе:"),
                          **inu_icon(safe_icon('UV')))
                box.label(text=T("N-панель → GTA Tools → UV Анимация"),
                          **inu_icon(safe_icon('BLANK1')))
            box.label(text=T("▶ Пробел — предпросмотр (Material Preview / Rendered)"),
                      **inu_icon(safe_icon('PLAY')))



def _draw_sort_materials_menu(self, context):
    """Append sort button to material context menu"""
    self.layout.separator()
    self.layout.operator("gtatools.sort_materials", text=T("Сортировка материалов"), **inu_icon(safe_icon('SORTALPHA')))


# ── 2DFX Light flags1/flags2 — bit-by-bit named toggles ───────────
# Per-bit tooltips live on the operator (`description` classmethod in
# effects_ops._2DFX_BIT_TOOLTIPS) so hovering a flag button shows
# what the bit actually does.
#
# Bits are grouped *semantically* in the UI (visibility / corona-fx /
# blinking / advanced) instead of by raw byte (flags1/flags2). Users
# don't think in terms of "byte 1 vs byte 2" — they think "I want
# this thing to blink at night". Each tuple is (prop_name, bit, label).
# GTA SA flags1 (raw byte): bit5=AT_DAY(0x20), bit6=AT_NIGHT(0x40),
# bit7=Blinking1(0x80). Default 96=0x60=AT_DAY+AT_NIGHT подтверждает это.
# Раньше биты дня/ночи были сдвинуты на +1 (AT_DAY=6, AT_NIGHT=7) — из-за
# этого «ночной» свет на деле светился днём. «Corona Flare» был ошибочно
# на бите 5 (= AT_DAY); линзовый блик в SA задаётся полем «Тип бликов».
_2DFX_GROUP_VISIBILITY = (
    ("2dfx_flags1", 5, "AT_DAY"),
    ("2dfx_flags1", 6, "AT_NIGHT"),
    ("2dfx_flags1", 3, "Without Corona"),
    ("2dfx_flags1", 0, "Check Obstacles"),
)
_2DFX_GROUP_CORONA = (
    ("2dfx_flags1", 4, "Corona Reflects"),
)
_2DFX_GROUP_BLINK = (
    ("2dfx_flags2", 0, "Blink 1"),
    ("2dfx_flags2", 1, "Blink 2"),
    ("2dfx_flags2", 2, "Blink 3"),
    ("2dfx_flags2", 7, "Police Light"),
    ("2dfx_flags2", 3, "Traffic Light"),
    ("2dfx_flags2", 4, "Train Crossing"),
)
_2DFX_GROUP_ADVANCED = (
    ("2dfx_flags1", 1, "Fog Type 1"),
    ("2dfx_flags1", 2, "Fog Type 2"),
    ("2dfx_flags2", 5, "Update Height"),
    ("2dfx_flags2", 6, "Check Direction"),
)


def _draw_2dfx_flag_group(parent, obj, group, header):
    """Draw a labeled group of bit-toggle buttons in 2-column grid.
    Each button XOR-toggles its bit via gtatools.toggle_2dfx_flag_bit;
    the operator's `description` classmethod supplies per-bit tooltip."""
    parent.label(text=header, **inu_icon(safe_icon('LIGHT_DATA')))
    grid = parent.column(align=True)
    pairs = [group[i:i + 2] for i in range(0, len(group), 2)]
    for pair in pairs:
        row = grid.row(align=True)
        for prop_name, bit, label in pair:
            cur = int(obj.get(prop_name, 0))
            depressed = bool(cur & (1 << bit))
            op = row.operator(
                "gtatools.toggle_2dfx_flag_bit",
                text=label, depress=depressed,
            )
            op.prop_name = prop_name
            op.bit = bit
        # Pad with empty cell if odd count, so single button doesn't
        # stretch full-width.
        if len(pair) == 1:
            row.label(text="")


def _draw_2dfx_flag_box(parent, obj):
    """Render 4 semantic flag groups inside the parent box. Caller is
    responsible for the collapsible header — this just draws content.
    Groups stacked into one aligned column so Blender collapses the
    inter-row gap; the bold group label alone separates them visually."""
    col = parent.column(align=True)
    _draw_2dfx_flag_group(col, obj, _2DFX_GROUP_VISIBILITY,
                          T("Видимость:"))
    _draw_2dfx_flag_group(col, obj, _2DFX_GROUP_CORONA,
                          T("Эффекты короны:"))
    _draw_2dfx_flag_group(col, obj, _2DFX_GROUP_BLINK,
                          T("Мерцание:"))
    _draw_2dfx_flag_group(col, obj, _2DFX_GROUP_ADVANCED,
                          T("Доп.:"))



class GTATOOLS_PT_material_panel(bpy.types.Panel):
    """Unified GTA SA Material panel — SURFACE / EFFECTS / PIPELINE tabs."""
    bl_label = "GTA Material"
    bl_idname = "GTATOOLS_PT_material_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def draw(self, context):
        layout = self.layout
        mat = context.material

        # Tab row at the top — expand=True renders enum as a button row.
        layout.prop(mat.inu, "material_tab", expand=True)
        layout.separator()

        tab = mat.inu.material_tab
        if tab == 'SURFACE':
            _draw_material_surface(layout, mat)
        elif tab == 'ALPHA':
            from ..ops.alpha_tools import draw_alpha_tools
            draw_alpha_tools(layout, context)
        else:  # EFFECTS (вкладка Pipeline и пресеты материала удалены)
            _draw_material_effects(layout, mat)





class GTATOOLS_UL_txd_export_plan(bpy.types.UIList):
    """Per-model TXD name editor shown in the Export-to-IMG dialog."""
    bl_idname = "GTATOOLS_UL_txd_export_plan"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        row = layout.row(align=True)
        row.prop(item, "include", text="")
        sub = row.row(align=True)
        sub.active = item.include
        sub.label(text=item.model_name, **inu_icon(safe_icon('MESH_DATA')))
        sub.prop(item, "txd_name", text="", **inu_icon(safe_icon('TEXTURE')))



class GTATOOLS_UL_img_files(bpy.types.UIList):
    """Scrollable list of files in IMG archive."""
    bl_idname = "GTATOOLS_UL_img_files"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        ext = item.name.rsplit('.', 1)[-1].lower() if '.' in item.name else ''
        icons = {'dff': 'MESH_DATA', 'col': 'MESH_CUBE', 'txd': 'TEXTURE', 'ipl': 'EMPTY_AXIS'}
        layout.label(text=item.name, **inu_icon(icons.get(ext, 'FILE')))

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flt_flags = [self.bitflag_filter_item] * len(items)
        # Keep original order — no sorting
        flt_neworder = []

        if self.filter_name:
            search = self.filter_name.lower()
            for i, item in enumerate(items):
                if search not in item.name.lower():
                    flt_flags[i] = 0

        return flt_flags, flt_neworder


def _short_path(p, last=0):
    """Короткий путь для отображения. last>0 → только последние N компонент
    (папка+файл): 'D:\\…\\data\\maps\\Props_obj\\ali.ipl' → 'Props_obj\\ali.ipl'.
    last=0 → от папки 'data' (или последние 3). Полный путь в проперти как есть.
    """
    import os
    if not p:
        return ""
    parts = [x for x in p.replace('\\', '/').split('/') if x]
    if last and len(parts) > last:
        return os.sep.join(parts[-last:])
    low = [x.lower() for x in parts]
    if 'data' in low:
        parts = parts[low.index('data'):]
    elif len(parts) > 3:
        parts = parts[-3:]
    return os.sep.join(parts)


# Кэш счётчиков IDE/IPL по (path, mtime). Панель перерисовывается часто (в т.ч.
# при сворачивании списков), а парсить файл на 900+ записей в каждой
# перерисовке = лаг. Кэш сбрасывается при изменении файла (mtime), поэтому
# счётчики актуальны после Add/Export.
_IDE_COUNTS_CACHE = {}
_IPL_COUNTS_CACHE = {}


def _ide_counts_cached(path):
    import os
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return []
    hit = _IDE_COUNTS_CACHE.get(path)
    if hit is not None and hit[0] == mt:
        return hit[1]
    counts = []
    try:
        from ..core.ide import read_ide
        ide = read_ide(path)
        for attr, lbl in (('objects', 'objs'), ('anims', 'anim'),
                          ('cars', 'cars'), ('peds', 'peds'), ('txdps', 'txdp')):
            seq = getattr(ide, attr, None)
            if seq:
                counts.append(f"{lbl}: {len(seq)}")
    except Exception:
        counts = []
    _IDE_COUNTS_CACHE[path] = (mt, counts)
    return counts


def _ipl_counts_cached(path):
    import os
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return []
    hit = _IPL_COUNTS_CACHE.get(path)
    if hit is not None and hit[0] == mt:
        return hit[1]
    counts = []
    try:
        from ..core.ipl import read_ipl
        ipl = read_ipl(path)
        for attr, lbl in (('instances', 'inst'), ('culls', 'cull'),
                          ('garages', 'grge'), ('enexs', 'enex'),
                          ('pickups', 'pick'), ('cars', 'cars'),
                          ('jumps', 'jump'), ('auzos', 'auzo'),
                          ('occls', 'occl'), ('zones', 'zone')):
            seq = getattr(ipl, attr, None)
            if seq:
                counts.append(f"{lbl}: {len(seq)}")
    except Exception:
        counts = []
    _IPL_COUNTS_CACHE[path] = (mt, counts)
    return counts


class GTATOOLS_UL_ipl_sync_list(bpy.types.UIList):
    """Scrollable list of IPL files for batch Sync. Каждая строка —
    КЛИКАБЕЛЬНАЯ метка короткого пути (клик = выделение элемента списка) +
    кнопка удаления. Полный путь не редактируется инлайн; чтобы заменить —
    удали (X) и добавь заново через «Добавить»."""
    bl_idname = "GTATOOLS_UL_ipl_sync_list"

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # Иконка-«ручка» слева + короткий путь МЕТКОЙ: клик по строке
            # (по иконке/тексту) выделяет элемент — поле больше не перехватывает
            # клик. Полный путь хранится в item.path как есть.
            row.label(text=_short_path(item.path) or item.path,
                      **inu_icon(safe_icon('EMPTY_AXIS')))
            op = row.operator("gtatools.ipl_sync_remove", text="",
                              **inu_icon(safe_icon('X')))
            op.index = index
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", **inu_icon(safe_icon('EMPTY_AXIS')))


class GTATOOLS_PT_main_panel(bpy.types.Panel):
    """Главная панель GTA Tools — root of the N-sidebar tab. Not in
    PANELS registry: roots have no bl_order (they own the tab) and
    Phase 5 will need one root per tab, handled separately."""
    bl_label = "GTA Tools"
    bl_idname = "GTATOOLS_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GTA Tools'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # ── Game switcher + Profile (top of body) ──
        # SA/VC/III и Profile живут вверху body (а не в header), потому
        # что Blender фиксирует высоту header — там кнопки не следуют
        # общему row-scale. В body они масштабируются как любые другие
        # ряды, и юзер видит единую высоту по всему аддону.
        # Fused vertical cluster: platform row + games row + profile
        # row примыкают (одно column(align=True) — 1px overlap).
        top_col = layout.column(align=True)

        # Platform switcher: PC / Mobile.
        # Mobile = iOS/Android, DFF stored via Native Data PLG
        # (War Drum OpenGL geometry); TXD stored in 4-file container
        # (.txt/.toc/.dat/.tmb) с PVRTC/ETC1.
        #
        # `prop(..., expand=True)` is the standard idiom for full-width
        # enum-as-button-row — Blender renders it with the same height
        # as operator buttons, so heights stay uniform with siblings.
        platform_row = top_col.row(align=True)
        platform_row.prop(scene.inu_settings, "gtatools_platform", expand=True)

        games_row = top_col.row(align=True)
        games_row.prop(scene.inu_settings, "gtatools_game", expand=True)

        # ── Profile switcher ──
        # ALL = no filter, default order. User profiles are saved in
        # INU_Preset/profiles/ and govern both visibility and order.
        # +/- manage profiles; the gear button opens the layout editor
        # popup (where pick-and-place + eye-toggle live).
        row = top_col.row(align=True)
        row.prop(scene.inu_settings, "gtatools_profile", text="", **inu_icon(safe_icon('PRESET')))
        row.operator("gtatools.profile_save", text="", **inu_icon(safe_icon('ADD')))
        del_btn = row.row(align=True)
        del_btn.enabled = (scene.inu_settings.gtatools_profile != 'ALL')
        del_btn.operator("gtatools.profile_delete", text="", **inu_icon(safe_icon('REMOVE')))
        edit_btn = row.row(align=True)
        edit_btn.enabled = (scene.inu_settings.gtatools_profile != 'ALL')
        edit_btn.operator("gtatools.profile_edit", text="", **inu_icon(safe_icon('PREFERENCES')))
        # Кнопка плавающего окна убрана из UI (осталась только у «Проверки»).
        # Код флоатера 'info' на месте — можно вернуть кнопку при желании.

        # Docs / Issues / What's New живут в GTATOOLS_PT_footer_panel внизу.


@apply_order
class GTATOOLS_PT_ide_ipl_panel(bpy.types.Panel):
    """Панель IDE / IPL / IMG для работы с существующими файлами GTA SA"""
    bl_label = "IDE / IPL / IMG"
    bl_idname = "GTATOOLS_PT_ide_ipl_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('PACKAGE')))

    def draw_header_preset(self, context):
        # Кнопка плавающего окна 'iii' убрана из UI (код флоатера на месте).
        _draw_doc_help(self.layout, 'ide_ipl')

    def draw(self, context):
        # Пусто: тело + кнопки-табы рисуют под-панели (HIDE_HEADER), чтобы
        # кнопки были ВПРИТЫК к содержимому (одна колонка), без зазора.
        pass


def _draw_ide_ipl_tabs(layout, s):
    """Кнопки-переключатели Импорт/Экспорт/Карта (в верху активной под-панели)."""
    r = layout.row(align=True)
    r.scale_y = 1.2
    r.prop(s, "gtatools_ide_ipl_mode", expand=True)


def _draw_map_import(layout, context):
    """Полный импорт/экспорт карты: Game Root, фильтры LOD/2DFX/TXD/COL,
    бинарные/текстовые IPL, извлечение ресурсов, Import/Export Map, профайлер,
    BBox. Общий блок таба «Карта» (перенесён из Properties → Scene)."""
    import os as _os_panel
    from ..ops.map_ops import _bbox_mode_active
    scene = context.scene
    c = layout.column(align=True)
    # Источник — в боксе, как во вкладке «Импорт»: папка игры + тумблеры.
    # (тот же проп gtatools_game_root с инлайн-браузером; Auto-discover убран.)
    _src = c.box().column(align=True)
    _src.prop(scene.inu_settings, "gtatools_game_root", text=T("Папка игры"))
    # Тумблеры «что подгружать» одним рядом. ВКЛ = подгружать (skip_* инверт.).
    row = _src.row(align=True)
    row.prop(scene.inu_settings, "gtatools_img_skip_lod",
             text="LOD", toggle=True, invert_checkbox=True)
    row.prop(scene.inu_settings, "gtatools_map_skip_2dfx",
             text="2DFX", toggle=True, invert_checkbox=True)
    row.prop(scene.inu_settings, "gtatools_img_load_txd",
             text="TXD", toggle=True)
    row.prop(scene.inu_settings, "gtatools_map_load_col",
             text="COL", toggle=True)
    c.prop(scene.inu_settings, "gtatools_map_skip_dupes",
           text=T("Без дублей"), toggle=True,
           **inu_icon(safe_icon('DUPLICATE')))
    c.prop(scene.inu_settings, "gtatools_map_group_by_ipl",
           text=T("Группировать по IPL"), toggle=True,
           **inu_icon(safe_icon('OUTLINER_COLLECTION')))
    c.prop(scene.inu_settings, "gtatools_map_region", text="")

    # Binary IPL selector (collapsible)
    bi_box = c.box()
    bi_row = bi_box.row(align=True)
    bi_row.prop(
        scene.inu_settings, "gtatools_show_binary_ipls",
        **inu_icon(safe_icon('TRIA_DOWN') if scene.inu_settings.gtatools_show_binary_ipls else 'TRIA_RIGHT'),
        emboss=False,
        text=T("Бинарные IPL") + f": {len(scene.inu_settings.gtatools_binary_ipls)}",
    )
    bi_row.operator(
        "gtatools.scan_binary_ipls", text="", **inu_icon(safe_icon('FILE_REFRESH')),
    )
    if scene.inu_settings.gtatools_show_binary_ipls:
        cached_region = scene.get('gtatools_binary_ipls_region', '')
        if cached_region and cached_region != scene.inu_settings.gtatools_map_region:
            bi_box.label(
                text=T("Район изменился — пересканируйте"),
                **inu_icon(safe_icon('ERROR')),
            )
        if not scene.inu_settings.gtatools_binary_ipls:
            bi_box.label(
                text=T("Список пуст — нажмите Scan"),
                **inu_icon(safe_icon('INFO')),
            )
        else:
            bi_row2 = bi_box.row(align=True)
            op_all = bi_row2.operator(
                "gtatools.binary_ipl_toggle_all",
                text=T("Все"), **inu_icon(safe_icon('CHECKBOX_HLT')),
            )
            op_all.enable = True
            op_none = bi_row2.operator(
                "gtatools.binary_ipl_toggle_all",
                text=T("Никакие"), **inu_icon(safe_icon('CHECKBOX_DEHLT')),
            )
            op_none.enable = False
            bi_col = bi_box.column(align=True)
            for item in scene.inu_settings.gtatools_binary_ipls:
                bi_col.prop(item, "enabled", text=item.name)

    # Text IPL selector — тот же Scan сканирует оба формата.
    ti_box = c.box()
    ti_row = ti_box.row(align=True)
    ti_row.prop(
        scene.inu_settings, "gtatools_show_text_ipls",
        **inu_icon(safe_icon('TRIA_DOWN') if scene.inu_settings.gtatools_show_text_ipls else 'TRIA_RIGHT'),
        emboss=False,
        text=T("Текстовые IPL") + f": {len(scene.inu_settings.gtatools_text_ipls)}",
    )
    ti_row.operator(
        "gtatools.scan_binary_ipls", text="", **inu_icon(safe_icon('FILE_REFRESH')),
    )
    if scene.inu_settings.gtatools_show_text_ipls:
        if not scene.inu_settings.gtatools_text_ipls:
            ti_box.label(
                text=T("Список пуст — нажмите Scan"),
                **inu_icon(safe_icon('INFO')),
            )
        else:
            ti_row2 = ti_box.row(align=True)
            op_all = ti_row2.operator(
                "gtatools.text_ipl_toggle_all",
                text=T("Все"), **inu_icon(safe_icon('CHECKBOX_HLT')),
            )
            op_all.enable = True
            op_none = ti_row2.operator(
                "gtatools.text_ipl_toggle_all",
                text=T("Никакие"), **inu_icon(safe_icon('CHECKBOX_DEHLT')),
            )
            op_none.enable = False
            ti_col = ti_box.column(align=True)
            for item in scene.inu_settings.gtatools_text_ipls:
                src = "IMG" if item.img_source else "loose"
                ti_col.prop(item, "enabled",
                            text=f"{item.name}  [{src}]")

    # Извлечь ресурсы — требует сохранённый .blend (кеш рядом с ним).
    saved = bool(bpy.data.filepath)
    if saved:
        c.operator("gtatools.extract_textures",
                   text=T("Извлечь ресурсы"),
                   **inu_icon(safe_icon('PACKAGE')))
    else:
        warn = c.box()
        warn.alert = True
        warn_row = warn.row()
        warn_row.alignment = 'CENTER'
        warn_row.label(
            text=T("Сначала сохраните .blend"),
            **inu_icon(safe_icon('ERROR')))
        btn_row = warn.row(align=True)
        btn_row.enabled = False
        btn_row.operator("gtatools.extract_textures",
                         text=T("Извлечь ресурсы"),
                         **inu_icon(safe_icon('PACKAGE')))
    blend_path = bpy.data.filepath
    saved = bool(blend_path)
    cache_exists = saved and _os_panel.path.isdir(
        _os_panel.path.join(_os_panel.path.dirname(blend_path),
                            '.inu_cache'))
    _MAP_BTN_SCALE = 1.7
    if saved:
        if cache_exists:
            row = c.row(align=True)
            row.scale_y = _MAP_BTN_SCALE
            row.operator("gtatools.import_map",
                         text=T("Import Map"),
                         **inu_icon(safe_icon('IMPORT')))
            row.operator("gtatools.map_export",
                         text=T("Export Map"),
                         **inu_icon(safe_icon('EXPORT')))
        else:
            warn = c.box()
            warn.alert = True
            warn_row = warn.row()
            warn_row.alignment = 'CENTER'
            warn_row.label(
                text=T("Кеш пуст — карта без моделей"),
                **inu_icon(safe_icon('INFO')))
            btn_row = warn.row(align=True)
            btn_row.enabled = False
            btn_row.scale_y = _MAP_BTN_SCALE
            btn_row.operator("gtatools.import_map",
                             text=T("Import Map"),
                             **inu_icon(safe_icon('IMPORT')))
            exp_row = c.row(align=True)
            exp_row.scale_y = _MAP_BTN_SCALE
            exp_row.operator("gtatools.map_export",
                             text=T("Export Map"),
                             **inu_icon(safe_icon('EXPORT')))
    else:
        warn = c.box()
        warn.alert = True
        warn_row = warn.row()
        warn_row.alignment = 'CENTER'
        warn_row.label(
            text=T("Сначала сохраните .blend"),
            **inu_icon(safe_icon('ERROR')))
        btn_row = warn.row(align=True)
        btn_row.enabled = False
        btn_row.scale_y = _MAP_BTN_SCALE
        btn_row.operator("gtatools.import_map",
                         text=T("Import Map"),
                         **inu_icon(safe_icon('IMPORT')))
        btn_row.operator("gtatools.map_export",
                         text=T("Export Map"),
                         **inu_icon(safe_icon('EXPORT')))
    c.prop(scene.inu_settings, "gtatools_profile_enabled",
           text=T("Профайлер (тайминги в консоль)"), toggle=False)
    c.operator("gtatools.toggle_bbox",
               text=T("BBox: ON") if _bbox_mode_active else T("BBox: OFF"),
               **inu_icon(safe_icon('MESH_CUBE')),
               depress=_bbox_mode_active)


class GTATOOLS_PT_ide_ipl_import(bpy.types.Panel):
    """Импорт моделей из игры: Game Root + IPL, авто-поиск IDE."""
    bl_label = "Импорт"
    bl_idname = "GTATOOLS_PT_ide_ipl_import"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_ide_ipl_panel"
    bl_options = {'HIDE_HEADER'}      # заголовок заменён кнопкой-переключателем

    @classmethod
    def poll(cls, context):
        return context.scene.inu_settings.gtatools_ide_ipl_mode == 'IMPORT'

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        s = scn.inu_settings
        col = layout.column(align=True)
        _draw_ide_ipl_tabs(col, s)      # кнопки-табы впритык к содержимому
        # Источник импорта — в одном боксе (как секции в Экспорте): папка игры,
        # выбранные IPL, целевой IMG и тумблеры.
        _src = col.box().column(align=True)
        # gtatools_game_root — КОРЕНЬ игры: по нему сканируют «Найти IDE/IMG» и
        # «Обновить из IDE/IPL» (не только IDE — отсюда подпись «Папка игры»).
        _src.prop(s, "gtatools_game_root", text=T("Папка игры"))
        # Отдельные строки IPL и IMG убраны: список IPL живёт в боксе «IPL для
        # импорта», а IMG подхватывается автоматически через «Найти IMG» (бокс
        # «IMG с моделями из IPL»). Значения читаем только для логики
        # кнопок/сканов.
        _ipl_list = s.gtatools_ipl_sync_list
        _ipl_pv = s.gtatools_ipl_path
        _has_ipl = bool(_ipl_list) or bool(_ipl_pv)
        _img_pv = s.gtatools_img_path
        # Тумблеры импорта.
        tr = _src.row(align=True)
        # ВКЛ = подгружать (skip_lod хранит «пропуск», поэтому invert_checkbox).
        tr.prop(s, "gtatools_img_skip_lod", text="LOD", toggle=True,
                invert_checkbox=True)
        tr.prop(s, "gtatools_img_load_txd", text="TXD", toggle=True)
        tr.prop(s, "gtatools_map_load_col", text="COL", toggle=True)
        # «Найти IDE/IMG» переехали значком 🔄 в шапки боксов «IMG/IDE с
        # моделями из IPL» ниже.
        # «IPL для импорта» — рядом с найденными IMG/IDE (одна группа списков).
        # Шапка с иконками: Добавить (один или несколько) / Папка / Корзина.
        _pexp = s.gtatools_show_import_ipl_list
        _plbox = col.box().column(align=True)
        _phdr = _plbox.row(align=True)
        _phdr.prop(s, "gtatools_show_import_ipl_list",
                   **inu_icon(safe_icon('TRIA_DOWN' if _pexp else 'TRIA_RIGHT')),
                   text=T("IPL для импорта ({0}):").format(len(_ipl_list)),
                   emboss=False)
        _phb = _phdr.row(align=True)
        _phb.alignment = 'RIGHT'
        _phb.operator("gtatools.ipl_sync_add", text="",
                      **inu_icon(safe_icon('ADD')))
        _phb.operator("gtatools.ipl_sync_add_folder", text="",
                      **inu_icon(safe_icon('FILE_FOLDER')))
        if _ipl_list:
            _phb.operator("gtatools.ipl_sync_remove", text="",
                          **inu_icon(safe_icon('TRASH'))).index = -1
        if _pexp and _ipl_list:
            for _pi, _pit in enumerate(_ipl_list):
                _pr = _plbox.row(align=True)
                _pr.label(text=_short_path(_pit.path) or _pit.path,
                          **inu_icon(safe_icon('EMPTY_AXIS')))
                _pr.operator("gtatools.open_text_file", text="",
                             **inu_icon(safe_icon('TEXT'))).filepath = _pit.path
                _pr.operator("gtatools.ipl_sync_remove", text="",
                             **inu_icon(safe_icon('X'))).index = _pi
        # Список найденных IMG — шапка видна всегда; значок 🔄 в ней = «Найти
        # IMG» (скан папки игры по моделям IPL). Импорт тянет модели из основного
        # IMG + всех этих архивов.
        found_img = [_p for _p in (scn.get('gtatools_found_imgs') or '').split('\n') if _p]
        _iexp = s.gtatools_show_found_imgs
        ibox = col.box().column(align=True)
        _ihdr = ibox.row(align=True)
        _ihdr.prop(s, "gtatools_show_found_imgs",
                   **inu_icon(safe_icon('TRIA_DOWN' if _iexp else 'TRIA_RIGHT')),
                   text=T("IMG с моделями из IPL ({0}):").format(len(found_img)),
                   emboss=False)
        _ihb = _ihdr.row(align=True)
        _ihb.alignment = 'RIGHT'
        _ihb.enabled = _has_ipl and bool(s.gtatools_game_root)
        _ihb.operator("gtatools.scan_img_for_ipl", text="",
                      **inu_icon(safe_icon('FILE_REFRESH')))
        if _iexp and found_img:
            _ilist = ibox.column(align=True)
            _ilist.scale_y = 0.85
            for _fp in found_img:
                _ilist.label(text=_short_path(_fp, last=2),
                             **inu_icon(safe_icon('FILE')))
        # Список найденных IDE — шапка видна всегда; значок 🔄 = «Найти IDE».
        # У каждого файла кнопка «открыть».
        found = [_p for _p in (scn.get('gtatools_found_ides') or '').split('\n') if _p]
        _dexp = s.gtatools_show_found_ides
        fbox = col.box().column(align=True)
        _fhdr = fbox.row(align=True)
        _fhdr.prop(s, "gtatools_show_found_ides",
                   **inu_icon(safe_icon('TRIA_DOWN' if _dexp else 'TRIA_RIGHT')),
                   text=T("IDE с моделями из IPL ({0}):").format(len(found)),
                   emboss=False)
        _fhb = _fhdr.row(align=True)
        _fhb.alignment = 'RIGHT'
        _fhb.enabled = _has_ipl and bool(s.gtatools_game_root)
        _fhb.operator("gtatools.scan_ide_for_ipl", text="",
                      **inu_icon(safe_icon('FILE_REFRESH')))
        if _dexp and found:
            for _fp in found:
                fr = fbox.row(align=True)
                fr.label(text=_short_path(_fp, last=2),
                         **inu_icon(safe_icon('TEXT')))
                fr.operator("gtatools.open_text_file", text="",
                            **inu_icon(safe_icon('TEXT'))).filepath = _fp
        # Главная кнопка импорта. Активна при выбранных IPL и хотя бы одном
        # источнике IMG: найденные («Найти IMG») ИЛИ вручную заданный путь.
        big = col.row(align=True)
        big.scale_y = 1.4
        big.enabled = _has_ipl and (bool(found_img) or bool(_img_pv))
        big.operator("gtatools.import_from_img", text=T("Импорт"),
                     **inu_icon(safe_icon('IMPORT')))
        # «Обновить из IDE/IPL» переехали значками в шапки «IDE для экспорта» /
        # «IPL для экспорта» (вкладка Экспорт).


class GTATOOLS_PT_ide_ipl_export(bpy.types.Panel):
    """Экспорт/запись: IDE + IPL + IMG (Add/Del/Export, синхронизация)."""
    bl_label = "Экспорт"
    bl_idname = "GTATOOLS_PT_ide_ipl_export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_ide_ipl_panel"
    bl_options = {'HIDE_HEADER'}      # заголовок заменён кнопкой-переключателем

    @classmethod
    def poll(cls, context):
        return context.scene.inu_settings.gtatools_ide_ipl_mode == 'EXPORT'

    def draw(self, context):
        import os
        layout = self.layout
        scn = context.scene
        # Контекстное затемнение: Add/Del работают с ВЫДЕЛЕНИЕМ, IMG-действия —
        # с выбранным архивом. Серые кнопки сами подсказывают, что нужно.
        has_sel = any(o.type == 'MESH' for o in context.selected_objects)

        # Wrap ВСЁ содержимое (IDE+IPL row, IPL utilities, IMG box) в
        # один outer `column(align=True)` — соседние боксы и кнопки
        # прижимаются друг к другу без дефолтного inter-row gap,
        # читается как один сплошной fused-блок.
        outer = layout.column(align=True)
        _draw_ide_ipl_tabs(outer, scn.inu_settings)   # кнопки-табы впритык

        # IDE + IPL side-by-side — narrow N-panel still fits since
        # both columns hold short button labels. Counts tooltip stays
        # in the header row of each box so the user can spot empty
        # files at a glance.
        cols_row = outer.row(align=True)
        col_ide = cols_row.column(align=True)
        col_ipl = cols_row.column(align=True)

        # IDE section — header + 4 кнопки в одном fused column,
        # так что Add/Del/Import/Export read as one connected group.
        box = col_ide.box()
        bc = box.column(align=True)
        row = bc.row(align=True)
        row.label(text="IDE", **inu_icon(safe_icon('TEXT')))
        # Выбор IDE-файла — кнопкой 📁 в шапке. Имя целевого файла модели
        # показывается в строке статуса «В IDE (…)» ниже — отдельной строкой
        # не дублируем.
        _hb_ide = row.row(align=True)
        _hb_ide.alignment = 'RIGHT'
        # Открыть выбранный IDE во внешнем редакторе (одиночный файл).
        _ide_pv0 = scn.inu_settings.gtatools_ide_path
        _oi = _hb_ide.row(align=True)
        _oi.enabled = bool(_ide_pv0)
        _oi.operator("gtatools.open_text_file", text="",
                     **inu_icon(safe_icon('TEXT'))).filepath = _ide_pv0 or ""
        _hb_ide.operator("gtatools.pick_setting_path", text="",
                         **inu_icon(safe_icon('FILEBROWSER'))).setting = "gtatools_ide_path"
        # Путь выбранного IDE-файла (короткий, от папки data).
        _ide_pv = scn.inu_settings.gtatools_ide_path
        _pr_ide = bc.row(align=True)
        _pr_ide.scale_y = 0.85
        _pr_ide.label(text=_short_path(_ide_pv, last=2) if _ide_pv else T("Файл не выбран"),
                      **inu_icon(safe_icon('FILE_FOLDER')))
        # Short un-translated labels — icons already carry the
        # meaning, and "Add/Del/Import/Export" are universally
        # readable across both Russian and English UIs. translate=
        # False is critical here.
        row = bc.row(align=True)
        row.enabled = has_sel        # Add/Del пишут выделенные модели
        row.operator("gtatools.upsert_ide", text="Add",
                     **inu_icon(safe_icon('ADD')), translate=False)
        row.operator("gtatools.remove_ide", text="Del",
                     **inu_icon(safe_icon('REMOVE')), translate=False)
        # Import убран: реальный импорт делает «Импорт из IMG» (тянет геометрию),
        # а import_ide только применял определения к уже загруженным моделям —
        # путало. Export (в новый .ide) остаётся.
        row = bc.row(align=True)
        row.operator("gtatools.export_ide", text="Export",
                     **inu_icon(safe_icon('EXPORT')), translate=False)

        # ── IDE file info + active object status (inside the box) ──
        ide_path = bpy.path.abspath(scn.inu_settings.gtatools_ide_path)
        if ide_path and os.path.isfile(ide_path):
            ide_counts = _ide_counts_cached(ide_path)   # кэш по mtime — без лага
            if ide_counts:
                info_row = bc.row(align=True)
                info_row.scale_y = 0.85
                info_row.label(text=", ".join(ide_counts),
                               **inu_icon(safe_icon('INFO')))
        # Статус активной модели вынесен в отдельный бокс «Выделенная модель»
        # ниже (под колонками) — здесь больше не дублируем.

        # IPL section
        box = col_ipl.box()
        bc = box.column(align=True)
        row = bc.row(align=True)
        row.label(text="IPL", **inu_icon(safe_icon('EMPTY_AXIS')))
        # Выбор IPL-файла — кнопкой 📁 в шапке. Имя целевого файла модели
        # показывается в строке статуса «В IPL (…)» ниже — не дублируем.
        _hb_ipl = row.row(align=True)
        _hb_ipl.alignment = 'RIGHT'
        # Открыть выбранный IPL во внешнем редакторе (одиночный файл).
        _ipl_pv0 = scn.inu_settings.gtatools_ipl_path
        _op = _hb_ipl.row(align=True)
        _op.enabled = bool(_ipl_pv0)
        _op.operator("gtatools.open_text_file", text="",
                     **inu_icon(safe_icon('TEXT'))).filepath = _ipl_pv0 or ""
        _hb_ipl.operator("gtatools.pick_setting_path", text="",
                         **inu_icon(safe_icon('FILEBROWSER'))).setting = "gtatools_ipl_path"
        # Путь выбранного IPL-файла (короткий, от папки data).
        _ipl_pv = scn.inu_settings.gtatools_ipl_path
        _pr_ipl = bc.row(align=True)
        _pr_ipl.scale_y = 0.85
        _pr_ipl.label(text=_short_path(_ipl_pv, last=2) if _ipl_pv else T("Файл не выбран"),
                      **inu_icon(safe_icon('EMPTY_AXIS')))
        row = bc.row(align=True)
        row.enabled = has_sel        # Add/Del пишут выделенные модели
        row.operator("gtatools.upsert_ipl", text="Add",
                     **inu_icon(safe_icon('ADD')), translate=False)
        row.operator("gtatools.remove_ipl", text="Del",
                     **inu_icon(safe_icon('REMOVE')), translate=False)
        # Import убран (как и в IDE): импорт делает «Импорт из IMG». Здесь
        # import_ipl только расставлял/ставил заглушки без геометрии — путало.
        row = bc.row(align=True)
        row.operator("gtatools.export_ipl", text="Export",
                     **inu_icon(safe_icon('EXPORT')), translate=False)

        # ── IPL file info + active object status (inside the box) ──
        ipl_path = bpy.path.abspath(scn.inu_settings.gtatools_ipl_path)
        if ipl_path and os.path.isfile(ipl_path):
            ipl_counts = _ipl_counts_cached(ipl_path)   # кэш по mtime — без лага
            if ipl_counts:
                info_row = bc.row(align=True)
                info_row.scale_y = 0.85
                info_row.label(text=", ".join(ipl_counts),
                               **inu_icon(safe_icon('INFO')))
        # Статус активной модели вынесен в отдельный бокс «Выделенная модель»
        # ниже (под колонками) — здесь больше не дублируем.

        # Below the two columns — two collapsible utility groups (collapsed by
        # default so the main view is just the IDE/IPL/IMG boxes) + IMG.
        bottom_col = outer.column(align=True)

        # ── Выделенная модель: имя + состояние (IDE/IPL) + действия. НАВЕРХУ,
        # над списками «… для экспорта» — это про активную модель, не про файлы.
        ao = context.active_object
        _selbox = bottom_col.box().column(align=True)
        # Модель + её состояние IDE/IPL — в отдельном ВЛОЖЕННОМ боксе, чтобы
        # визуально выделялось из блока действий ниже.
        _inner = _selbox.box().column(align=True)
        if ao is None or ao.type != 'MESH' or not hasattr(ao, 'inu'):
            _inner.label(text=T("Нет выделенной модели"),
                         **inu_icon(safe_icon('INFO')))
        else:
            _iao = ao.inu
            # Имя модели + справа значки: Проверить / Убрать из IDE+IPL
            # (корзина — последней справа).
            _nr = _inner.row(align=True)
            _nr.label(text=ao.name, **inu_icon(safe_icon('OBJECT_DATA')))
            _nab = _nr.row(align=True)
            _nab.alignment = 'RIGHT'
            # Два слота-заглушки под ведущие иконки строк ниже (открыть + ▶/🔄),
            # чтобы колонка «Check» стояла ровно над Add/Export.
            _nab.label(text="", icon='BLANK1')
            _nab.label(text="", icon='BLANK1')
            _nab_pv = _nab.row(align=True)
            _nab_pv.ui_units_x = 6.5   # общая ширина главных кнопок
            _nab_pv.operator("gtatools.link_verify", text="Check",
                             translate=False, **inu_icon(safe_icon('CHECKMARK')))
            _nab.operator("gtatools.link_unlink", text="",
                          **inu_icon(safe_icon('TRASH')))
            # IDE-состояние + кнопка «обновить параметры в своих IDE» (↑).
            _sr = _inner.row(align=True)
            _sr.scale_y = 0.85
            # Скопировал модель и сменил Model ID → привязка к старой строке
            # IDE неактуальна (новый ID в том IDE отсутствует).
            _ide_id_changed = (
                _iao.ide_linked and _iao.ide_last_model_id > 0
                and int(_iao.model_id) != int(_iao.ide_last_model_id))
            if _ide_id_changed:
                _sr.label(
                    text=T("Не в IDE — сменился ID (был {0})").format(
                        _iao.ide_last_model_id),
                    **inu_icon(safe_icon('DUPLICATE')))
            elif not _iao.ide_linked or _iao.model_id <= 0:
                _sr.label(text=T("Не в IDE"),
                          **inu_icon(safe_icon('RADIOBUT_OFF')))
            else:
                # Что именно разошлось с IDE — перечисляем в предупреждении.
                _ide_diff = []
                if abs(_iao.draw_distance - _iao.ide_last_draw_distance) > 1e-3:
                    _ide_diff.append("DrawDist")
                if (_iao.txd_name or '') != (_iao.ide_last_txd_name or ''):
                    _ide_diff.append("TXD")
                if int(_iao.ide_flags) != int(_iao.ide_last_flags):
                    _ide_diff.append("Flags")
                _drift_ide = bool(_ide_diff)
                if _drift_ide:
                    _sr.label(text=T("В IDE, изменено: {0}").format(
                        ", ".join(_ide_diff)),
                              **inu_icon(safe_icon('ERROR')))
                else:
                    _t = os.path.basename(_iao.ide_target_file or '') or '?'
                    _sr.label(text=T("В IDE ({0})").format(_t),
                              **inu_icon(safe_icon('CHECKMARK')))
            _sre = _sr.row(align=True)
            _sre.alignment = 'RIGHT'
            _sre.enabled = has_sel
            # 📄 открыть IDE-файл этой модели во внешнем редакторе.
            _oide = _sre.row(align=True)
            _oide.enabled = bool(_iao.ide_target_file)
            _oide.operator("gtatools.open_text_file", text="",
                           **inu_icon(safe_icon('TEXT'))).filepath = (
                               _iao.ide_target_file or "")
            # ▶ вернуть параметры модели ИЗ IDE (id, флаги, draw dist, TXD) —
            # парная кнопке «вернуть координаты из IPL» (тоже FORWARD).
            _rcide = _sre.row(align=True)
            _rcide.enabled = bool(_iao.ide_linked)
            _rcide.operator("gtatools.ide_sync_from_file", text="",
                            **inu_icon(safe_icon('FORWARD')))
            # ↑ обновить строку в IDE + 🗑 удалить (не активна, если ID сменился).
            _sre_ex = _sre.row(align=True)
            _sre_ex.ui_units_x = 6.5
            _sre_ex.operator("gtatools.ide_sync_export", text="Add",
                             translate=False, **inu_icon(safe_icon('EXPORT')))
            _dtide = _sre.row(align=True)
            _dtide.enabled = (bool(_iao.ide_target_file) and bool(_iao.ide_linked)
                              and not _ide_id_changed)
            _dtide.operator("gtatools.ide_remove_link", text="",
                            **inu_icon(safe_icon('TRASH'))
                            ).target_file = _iao.ide_target_file or ""
            # IPL-состояние + кнопка «обновить координаты в своих IPL» (↑).
            _sr2 = _inner.row(align=True)
            _sr2.scale_y = 0.85
            if not _iao.ipl_uuid:
                _sr2.label(text=T("Не в IPL"),
                           **inu_icon(safe_icon('RADIOBUT_OFF')))
            else:
                _uuid = _iao.ipl_uuid
                _sid = (getattr(ao, 'session_uid', None)
                        or getattr(ao, 'session_uuid', 0) or 0)
                _new_copy = False
                for _o in bpy.data.objects:
                    if _o is ao:
                        continue
                    if getattr(_o.inu, 'ipl_uuid', '') != _uuid:
                        continue
                    _os = (getattr(_o, 'session_uid', None)
                           or getattr(_o, 'session_uuid', 0) or 0)
                    if _os < _sid:
                        _new_copy = True
                        break
                _cp = ao.matrix_world.translation
                _lp = _iao.ipl_last_pos
                _drift_ipl = (abs(_cp.x - _lp[0]) > 1e-4
                              or abs(_cp.y - _lp[1]) > 1e-4
                              or abs(_cp.z - _lp[2]) > 1e-4)
                if _new_copy:
                    _sr2.label(text=T("Копия — добавится новым инстансом"),
                               **inu_icon(safe_icon('DUPLICATE')))
                elif _drift_ipl:
                    _sr2.label(text=T("В IPL, координаты разошлись"),
                               **inu_icon(safe_icon('ERROR')))
                else:
                    _t2 = os.path.basename(_iao.ipl_target_file or '') or '?'
                    _sr2.label(text=T("В IPL ({0})").format(_t2),
                               **inu_icon(safe_icon('CHECKMARK')))
            _sre2 = _sr2.row(align=True)
            _sre2.alignment = 'RIGHT'
            _sre2.enabled = has_sel
            # 📄 открыть IPL-файл этой модели во внешнем редакторе.
            _oipl = _sre2.row(align=True)
            _oipl.enabled = bool(_iao.ipl_target_file)
            _oipl.operator("gtatools.open_text_file", text="",
                           **inu_icon(safe_icon('TEXT'))).filepath = (
                               _iao.ipl_target_file or "")
            # ▶ вернуть координаты из IPL (в слот-иконку, как ▶ у IDE).
            _rc2 = _sre2.row(align=True)
            _rc2.enabled = bool(_iao.ipl_uuid)
            _rc2.operator("gtatools.ipl_restore_coords", text="",
                          **inu_icon(safe_icon('FORWARD')))
            # ↑ обновить координаты в IPL + 🗑 удалить инстанс.
            _sre2_ex = _sre2.row(align=True)
            _sre2_ex.ui_units_x = 6.5
            _sre2_ex.operator("gtatools.ipl_sync_export", text="Add",
                              translate=False, **inu_icon(safe_icon('EXPORT')))
            _dtipl = _sre2.row(align=True)
            _dtipl.enabled = bool(_iao.ipl_uuid)
            _dtipl.operator("gtatools.ipl_remove_link", text="",
                            **inu_icon(safe_icon('TRASH'))
                            ).target_file = _iao.ipl_target_file or ""
            # IMG-статус (по img_target_file) + кнопка ↑: экспорт модели в
            # выбранный IMG (по умолчанию — родной IMG модели, иначе выбранный
            # в дропдауне «Экспорт в IMG» ниже). Обновит или добавит модель.
            _sr3 = _inner.row(align=True)
            _sr3.scale_y = 0.85
            _img_tgt = _iao.img_target_file
            if _img_tgt:
                _sr3.label(
                    text=T("В IMG ({0})").format(
                        os.path.basename(bpy.path.abspath(_img_tgt)) or '?'),
                    **inu_icon(safe_icon('CHECKMARK')))
            else:
                _sr3.label(text=T("Не в IMG"),
                           **inu_icon(safe_icon('RADIOBUT_OFF')))
            _choice3 = scn.inu_settings.gtatools_export_img_target
            if _choice3 == 'SELF':
                _res3 = (bpy.path.abspath(_img_tgt) if _img_tgt
                         else bpy.path.abspath(scn.inu_settings.gtatools_img_path))
            else:
                _res3 = _choice3
            _sre3 = _sr3.row(align=True)
            _sre3.alignment = 'RIGHT'
            _sre3.enabled = has_sel
            # 📦 открыть .img этой модели ассоциированным приложением ОС.
            _oimg = _sre3.row(align=True)
            _oimg.enabled = bool(_img_tgt)
            _oimg.operator("gtatools.open_text_file", text="",
                           **inu_icon(safe_icon('FILE_ARCHIVE'))).filepath = (
                               bpy.path.abspath(_img_tgt) if _img_tgt else "")
            # 🔄 проверить, в каком IMG папки игры лежит DFF модели (слот-иконка).
            _sre3.operator("gtatools.verify_img_link", text="",
                           **inu_icon(safe_icon('FILE_REFRESH')))
            # ↑ экспорт в IMG.
            _upimg = _sre3.row(align=True)
            _upimg.ui_units_x = 6.5   # общая ширина главных кнопок
            _upimg.enabled = bool(_res3)
            _op3 = _upimg.operator("gtatools.export_to_img", text="Export",
                                   translate=False, **inu_icon(safe_icon('EXPORT')))
            _op3.target_img = _res3 or ""
            # 🗑 удалить DFF/TXD/COL модели из её IMG.
            _dtimg = _sre3.row(align=True)
            _dtimg.enabled = bool(_img_tgt)
            _dtimg.operator("gtatools.remove_from_img", text="",
                            **inu_icon(safe_icon('TRASH'))).target_img = _img_tgt or ""
        # «Вернуть координаты из IPL» — теперь значком 🔄 в строке «Не в IPL».
        # Убрать/Проверить — значками у имени модели выше.

        # IPL и IDE — отдельными боксами НАПРЯМУЮ (без общей обёртки
        # «Синхронизация с файлами»: не плодим вложенные сворачивашки).
        # ── IPL для экспорта — свой сворачиваемый бокс ──
        ipl_sync_list = scn.inu_settings.gtatools_ipl_sync_list
        count_suffix = f" ({len(ipl_sync_list)})" if ipl_sync_list else ""
        _ipl_exp = scn.inu_settings.gtatools_show_sync_ipl
        _iplbox = bottom_col.box().column(align=True)
        _hdr = _iplbox.row(align=True)
        _hdr.prop(scn.inu_settings, "gtatools_show_sync_ipl",
                  **inu_icon(safe_icon('TRIA_DOWN' if _ipl_exp
                                       else 'TRIA_RIGHT')),
                  text=T("IPL для экспорта") + count_suffix, emboss=False)
        # Иконки без подписей справа: Обновить из всех IPL / Добавить / Папка /
        # Очистить. («Экспорт в свои IPL» переехал в бокс «Выделенная модель».)
        _hb = _hdr.row(align=True)
        _hb.alignment = 'RIGHT'
        _hb.operator("gtatools.ipl_sync_from_file", text="",
                     **inu_icon(safe_icon('FILE_REFRESH')))
        _hb.operator("gtatools.ipl_sync_add", text="",
                     **inu_icon(safe_icon('ADD')))
        _hb.operator("gtatools.ipl_sync_add_folder", text="",
                     **inu_icon(safe_icon('FILE_FOLDER')))
        if ipl_sync_list:
            _hb.operator("gtatools.ipl_sync_remove", text="",
                         **inu_icon(safe_icon('TRASH'))).index = -1
        if _ipl_exp and ipl_sync_list:
            _lcol = _iplbox.column(align=True)
            for _si, _sit in enumerate(ipl_sync_list):
                _sr = _lcol.row(align=True)
                _sr.label(text=_short_path(_sit.path) or _sit.path,
                          **inu_icon(safe_icon('EMPTY_AXIS')))
                _sr.operator("gtatools.open_text_file", text="",
                             **inu_icon(safe_icon('TEXT'))).filepath = _sit.path
                _sr.operator("gtatools.ipl_sync_remove", text="",
                             **inu_icon(safe_icon('X'))).index = _si
        # ── IDE для экспорта — свой сворачиваемый бокс ──
        ide_sync_list = scn.inu_settings.gtatools_ide_sync_list
        ide_suffix = f" ({len(ide_sync_list)})" if ide_sync_list else ""
        _ide_exp = scn.inu_settings.gtatools_show_sync_ide
        _idebox = bottom_col.box().column(align=True)
        _dhdr = _idebox.row(align=True)
        _dhdr.prop(scn.inu_settings, "gtatools_show_sync_ide",
                   **inu_icon(safe_icon('TRIA_DOWN' if _ide_exp
                                        else 'TRIA_RIGHT')),
                   text=T("IDE для экспорта") + ide_suffix, emboss=False)
        # Иконки без подписей справа: Обновить из всех IDE / Добавить / Папка /
        # Очистить. («Экспорт в свои IDE» переехал в бокс «Выделенная модель».)
        _dhb = _dhdr.row(align=True)
        _dhb.alignment = 'RIGHT'
        _dhb.operator("gtatools.ide_sync_from_file", text="",
                      **inu_icon(safe_icon('FILE_REFRESH')))
        _dhb.operator("gtatools.ide_sync_add", text="",
                      **inu_icon(safe_icon('ADD')))
        _dhb.operator("gtatools.ide_sync_add_folder", text="",
                      **inu_icon(safe_icon('FILE_FOLDER')))
        if ide_sync_list:
            _dhb.operator("gtatools.ide_sync_remove", text="",
                          **inu_icon(safe_icon('TRASH'))).index = -1
        if _ide_exp and ide_sync_list:
            _dcol = _idebox.column(align=True)
            for _di, _dit in enumerate(ide_sync_list):
                _dr = _dcol.row(align=True)
                _dr.label(text=_short_path(_dit.path) or _dit.path,
                          **inu_icon(safe_icon('FILE_TEXT')))
                _dr.operator("gtatools.open_text_file", text="",
                             **inu_icon(safe_icon('TEXT'))).filepath = _dit.path
                _dr.operator("gtatools.ide_sync_remove", text="",
                             **inu_icon(safe_icon('X'))).index = _di
        # ── Флаги IDE активной модели — свой сворачиваемый бокс ──
        # Флаги пер-объектные (obj.inu.ide_flags), game-aware список тот же,
        # что в Object Properties. Здесь — чтобы не лезть в свойства объекта
        # ради пары галочек при работе с IDE/IPL/IMG.
        _fl_exp = scn.inu_settings.gtatools_show_ide_flags_box
        _flbox = bottom_col.box().column(align=True)
        _flbox.prop(scn.inu_settings, "gtatools_show_ide_flags_box",
                    **inu_icon(safe_icon('TRIA_DOWN' if _fl_exp
                                         else 'TRIA_RIGHT')),
                    text=T("Флаги IDE"), emboss=False)
        if _fl_exp:
            _fact = context.active_object
            _fainu = getattr(_fact, 'inu', None) if _fact else None
            if _fainu is None or getattr(_fact, 'type', '') != 'MESH':
                _flbox.label(text=T("Выдели модель"),
                             **inu_icon(safe_icon('INFO')))
            else:
                _flbox.prop(_fainu, "ide_flags", text="IDE Flags")
                from ..core.ide_flag_translate import flag_props_for_game
                from ..core import game_versions as _gv
                _flc = _flbox.column(align=True)
                for _flp in flag_props_for_game(_gv.game_of_scene(scn)):
                    _flc.prop(_fainu, _flp)
        # ── «Дополнительно (IPL)»: секции + замена Empty (collapsible) ──
        extra_expanded = scn.inu_settings.gtatools_show_ipl_extra
        extra_group = bottom_col.box().column(align=True)
        extra_group.prop(scn.inu_settings, "gtatools_show_ipl_extra",
                         **inu_icon(safe_icon('TRIA_DOWN' if extra_expanded
                                              else 'TRIA_RIGHT')),
                         text=T("Дополнительно (IPL)"), emboss=False)
        if extra_expanded:
            extra_group.label(text=T("Секции IPL (cull, пути, гаражи…):"),
                              **inu_icon(safe_icon('INFO')))
            _sec = extra_group.row(align=True)
            _sec.operator("gtatools.import_ipl_sections", text=T("Импорт"),
                          **inu_icon(safe_icon('IMPORT')))
            _sec.operator("gtatools.export_ipl_sections", text=T("Экспорт"),
                          **inu_icon(safe_icon('EXPORT')))
            extra_group.operator("gtatools.replace_ipl_placeholders",
                                 text=T("Заменить Empty на модели"),
                                 **inu_icon(safe_icon('MESH_DATA')))

        # IMG-секция убрана целиком: путь/выбор архива, экспорт, удаление и
        # пересборка живут в боксе «Выделенная модель» и диалоге «Export to
        # IMG» (выбор архива из папки игры + галочка «Пересобрать после
        # экспорта»). Отдельный путь IMG здесь больше не нужен.


# ── Menu: Create 2DFX effect ────────────────────────────────────
# Replaces 4 buttons (Light/Particle/Ped Attractor/Sun Glare) with one
# dropdown — each item just calls the same operator with a different
# effect_type. Clusters effect choice in one well-known UI pattern.
class GTATOOLS_MT_create_2dfx(bpy.types.Menu):
    bl_label = "INU: Создать 2DFX"
    bl_idname = "GTATOOLS_MT_create_2dfx"

    def draw(self, context):
        layout = self.layout
        op = layout.operator("gtatools.create_2dfx", text="2DFX",
                             **inu_icon(safe_icon('LIGHT_POINT')))
        op.effect_type = 'LIGHT'
        op = layout.operator("gtatools.create_2dfx", text=T("Частица"),
                             **inu_icon(safe_icon('PARTICLES')))
        op.effect_type = 'PARTICLE'
        op = layout.operator("gtatools.create_2dfx", text="Ped Attractor",
                             **inu_icon(safe_icon('COMMUNITY')))
        op.effect_type = 'PED_ATTRACTOR'
        op = layout.operator("gtatools.create_2dfx", text=T("Блик солнца"),
                             **inu_icon(safe_icon('LIGHT_SUN')))
        op.effect_type = 'SUN_GLARE'
        layout.separator()
        op = layout.operator("gtatools.create_2dfx", text=T("Вход/Выход"),
                             **inu_icon(safe_icon('EMPTY_ARROWS')))
        op.effect_type = 'ENTER_EXIT'
        op = layout.operator("gtatools.create_2dfx", text=T("Дорожный знак"),
                             **inu_icon(safe_icon('FONT_DATA')))
        op.effect_type = 'ROAD_SIGN'
        op = layout.operator("gtatools.create_2dfx", text=T("Эскалатор"),
                             **inu_icon(safe_icon('SORTSIZE')))
        op.effect_type = 'ESCALATOR'


# ── Menu: Radar generation modes ────────────────────────────────
# 5 separate mode buttons (ALL / MENU / FULL / FULL_MENU / SPECIFIC) →
# one dropdown. The "Specific" item still requires the user to fill
# the «Индексы» field on the panel — the menu just triggers, doesn't
# replace the parameter row.
class GTATOOLS_MT_radar_generate(bpy.types.Menu):
    bl_label = "INU: Генерировать радар"
    bl_idname = "GTATOOLS_MT_radar_generate"

    def draw(self, context):
        layout = self.layout
        op = layout.operator("gtatools.radar_generate",
                             text=T("Генерировать радар"),
                             **inu_icon(safe_icon('RENDER_RESULT')))
        op.mode = 'ALL'
        op = layout.operator("gtatools.radar_generate",
                             text=T("Меню радар (3x3)"),
                             **inu_icon(safe_icon('RENDER_RESULT')))
        op.mode = 'MENU'
        layout.separator()
        op = layout.operator("gtatools.radar_generate",
                             text=T("Полный радар"), **inu_icon(safe_icon('IMAGE')))
        op.mode = 'FULL'
        op = layout.operator("gtatools.radar_generate",
                             text=T("Полный меню"), **inu_icon(safe_icon('IMAGE')))
        op.mode = 'FULL_MENU'
        layout.separator()
        op = layout.operator("gtatools.radar_generate",
                             text=T("Указанные тайлы"),
                             **inu_icon(safe_icon('RENDER_RESULT')))
        op.mode = 'SPECIFIC'


# ── Menu: Path node traffic flags ───────────────────────────────
# 4 traffic-light buttons (None / Normal / Rail / Bus) → one dropdown.
# Roadblock toggle stays as a separate button (different operator
# semantics — it's a toggle, not an enum pick).
class GTATOOLS_MT_path_traffic(bpy.types.Menu):
    bl_label = "INU: Светофор"
    bl_idname = "GTATOOLS_MT_path_traffic"

    def draw(self, context):
        layout = self.layout
        op = layout.operator("gtatools.path_node_flag", text=T("Без светофора"))
        op.action = 'TRAFFIC_NONE'
        op = layout.operator("gtatools.path_node_flag", text=T("Обычный"))
        op.action = 'TRAFFIC_NORMAL'
        op = layout.operator("gtatools.path_node_flag", text=T("Железнодорожный"))
        op.action = 'TRAFFIC_RAIL'
        op = layout.operator("gtatools.path_node_flag", text=T("Автобусный"))
        op.action = 'TRAFFIC_BUS'


class GTATOOLS_PT_ide_ipl_map(bpy.types.Panel):
    """Полный импорт/экспорт карты (таб «Карта» в IDE/IPL/IMG)."""
    bl_label = "Карта"
    bl_idname = "GTATOOLS_PT_ide_ipl_map"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_ide_ipl_panel"
    bl_options = {'HIDE_HEADER'}      # заголовок заменён кнопкой-переключателем

    @classmethod
    def poll(cls, context):
        return context.scene.inu_settings.gtatools_ide_ipl_mode == 'MAP'

    def draw(self, context):
        outer = self.layout.column(align=True)
        _draw_ide_ipl_tabs(outer, context.scene.inu_settings)
        _draw_map_import(outer, context)


@apply_order
class GTATOOLS_PT_export_panel(bpy.types.Panel):
    """Панель экспорта/импорта GTA моделей"""
    bl_label = "Экспорт / Импорт"
    bl_idname = "GTATOOLS_PT_export_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", **inu_icon(safe_icon('EXPORT')))

    def draw_header_preset(self, context):
        # Icon-only toggle for the floating-window version of this
        # panel — sits next to the panel title in the header so it's
        # one click away without taking up a full row of body space.
        # Иконка-планета ПЕРВОЙ (левее всех) → наш форк/релиз Ariane
        # (временная ссылка на GitHub до официального релиза Ariane).
        _u = self.layout.operator("gtatools.open_url", text="",
                                  **inu_icon(safe_icon('WORLD')), emboss=False)
        _u.url = "https://github.com/INU-ez/ariane-support-INU-Tools-and-DragonFF-"
        _u.tip = T("Открыть наш форк Ariane (GitHub) — редактор карт для "
                   "round-trip с аддоном (временно, до релиза Ariane)")
        # Кнопка плавающего окна 'ie' убрана из UI (код флоатера на месте).
        # «?» рисуем ПОСЛЕДНЕЙ → крайняя справа, единообразно со всеми панелями.
        _draw_doc_help(self.layout, 'export')

    def draw(self, context):
        from ..tools.model_utils import (
            find_selected_models, find_all_selected_model_groups,
            get_model_type_cached,
        )
        layout = self.layout
        s = context.scene.inu_settings

        # ── Selection diagnostic (top of panel, always visible) ──
        # Кэш-классификатор: draw() гоняется каждый redraw, а на большой сцене
        # (тем более с пустым выделением → скан всей коллекции) свежий скан
        # материалов подвешивал UI. Экспорт-операторы классифицируют свежо.
        models = find_selected_models(classify=get_model_type_cached)
        groups = find_all_selected_model_groups(classify=get_model_type_cached)
        selected_count = len([o for o in context.selected_objects if o.type == 'MESH'])

        # Per-type counts across ALL selected groups — single mesh shows
        # only the first DFF/LOD/COL, but a multi-select like 5 cars
        # should reveal the batch size instead of hiding it behind one
        # name. Format: "name +N" when >1.
        counts = {'DFF': 0, 'LOD': 0, 'COL': 0}
        for g in groups.values():
            for k in counts:
                if g[k] is not None:
                    counts[k] += 1

        def _line(kind):
            obj = models[kind]
            if obj is None:
                return f"{kind}: -"
            n = counts[kind]
            return f"{kind}: {obj.name}" if n <= 1 else f"{kind}: {obj.name} +{n - 1}"

        # Wrap diag box + IE buttons in a single aligned column so the
        # box и кнопки прижались друг к другу как один блок (без
        # дефолтного `inter_row_gap` который Blender вставляет между
        # сиблингами разных типов).
        top_col = layout.column(align=True)

        # Tabs fused with the diagnostic box below (one align column → no gap).
        tabs = top_col.row(align=True)
        tabs.scale_y = 1.2
        tabs.prop(s, "ariane_panel_mode", expand=True)

        box = top_col.box()
        box.label(text=f"{T('Выделено')}: {selected_count} {T('меш(ей)')}", **inu_icon(safe_icon('OBJECT_DATA')))
        col = box.column()
        for kind in ('DFF', 'LOD', 'COL'):
            col.label(text=_line(kind),
                      **inu_icon(compat.ICON_CHECK if models[kind] else 'X'))

        # Ariane tab: the shared diagnostic above, then the bridge body IN PLACE of
        # the normal import/export block (Ручной импорт / Экспорт → Ariane sit where
        # Импорт / Экспорт are). The normal IE body below is skipped entirely.
        if s.ariane_panel_mode == 'ARIANE':
            from ..ops.ariane_bridge import draw_ariane_body
            draw_ariane_body(top_col, context)
            return

        # Import/Export menus + Auto TXD + Pipeline — один fused
        # vertical block через `column(align=True)`. Раньше между ними
        # был `layout.separator()`, который рисует пустую row высотой
        # с обычную (~18px) — это создавало ощущение «дыры». Теперь
        # ряды примыкают друг к другу без 1px-разрывов, как Blender
        # делает в своих native fused property groups.
        io_col = top_col.column(align=True)

        # ── Импорт / Экспорт: две кнопки, формат выбирается галочками
        # в самом окне (Импорт → выбор файлов + фильтр расширений;
        # Экспорт → выбор папки + галочки DFF/COL/LOD/TXD/CST). ──
        row = io_col.row(align=True)
        row.operator("gtatools.inu_import", text=T("Импорт"), **inu_icon(safe_icon('IMPORT')))
        row.operator("gtatools.export_all", text=T("Экспорт"), **inu_icon(safe_icon('EXPORT')))

        # ── Auto TXD + DXT backend selector ──
        row = io_col.row(align=True)
        row.prop(context.scene.inu_settings, "gtatools_txd_auto_import", text=T("Авто TXD"))
        row.prop(context.scene.inu_settings, "gtatools_dxt_backend", text="")

        # ── Pipeline (one row, no info-label clutter — tooltip on each btn) ──
        # «Ped» — это preset для скиннутых персонажей: применяет
        # has_skin=True, отключает day/night vcols + MatFX. На pipeline
        # ID = 0 (peds в GTA SA не используют специальный RW pipeline).
        row = io_col.row(align=True)
        row.prop(context.scene.inu_settings, "gtatools_export_pipeline", expand=True)
        # ── Авто-генерация коллизии: выдели модель → кнопка (Выпуклая / Бокс).
        # Создаёт редактируемый <имя>_COL, который дальше идёт в COL-экспорт.
        io_col.operator_menu_enum("gtatools.auto_col", "mode",
                                  text=T("Сгенерировать COL"), icon='MESH_CUBE')
        # Suffix/Prefix customisation UI removed — model type is now detected
        # automatically (LOD by «LOD» in the name, COL by an import tag or the
        # absence of textured materials, otherwise DFF). The _DFF/_LOD/_COL
        # suffixes still work as a manual override via their default values.

        obj = context.active_object
        if obj and obj.type == 'MESH' and hasattr(obj, 'inu'):
            inu = obj.inu
            row = layout.row(align=True)
            row.prop(context.scene.inu_settings, "gtatools_show_dff_flags",
                     **inu_icon(safe_icon('TRIA_DOWN') if context.scene.inu_settings.gtatools_show_dff_flags else 'TRIA_RIGHT'),
                     text="DFF Flags", emboss=False)
            if context.scene.inu_settings.gtatools_show_dff_flags:
                fbox = layout.box()
                fc = fbox.column(align=True)
                from ..core import game_versions as _gv
                _game = _gv.game_of_scene(context.scene)
                _is_sa = (_game == 'SA')
                pipeline = context.scene.inu_settings.gtatools_export_pipeline

                # Pipeline-specific recommended flag states. Keys here
                # name properties on `obj.inu.*` (the per-mesh DFF flag
                # props). Когда юзер выбрал пайплайн, флаги отличные от
                # рекомендации подсвечиваются `row.alert = True`
                # (красным) — мгновенный визуальный sanity-check на
                # «этот флаг сейчас неправильный для пайплайна».
                # Blacklist of flags that DON'T BELONG on the chosen
                # pipeline — for these the row is painted red regardless
                # of current on/off value. Логика: «этот флаг вообще не
                # для этого пайплайна, лучше выключи». Юзер сам решает
                # включать flags которые «обязательные», но видит явное
                # предупреждение для несовместимых.
                _PIPE_FORBIDDEN = {
                    '0x53F2009A': {  # Vehicle — кузов машины
                        'day_cols', 'night_cols',
                        'light_beam_asi',  # Vehicle pipeline drops Light Beam
                    },
                    '0x53F20098': {  # D/N Building
                        # D/N светится через prelit day+night vcols:
                        # ни свет, ни нормали, ни mat-alpha, ни light beam.
                        'uv_map2',
                        'light',               # dynamic light не нужен
                        'export_normals',      # нормали => мерцание
                        'set_material_alpha',  # не для D/N building
                        'light_beam_asi',      # building feature, не D/N
                    },
                    '0x53F2009C': {  # Building (без D/N)
                        'night_cols',     # plain building, не D/N
                        'uv_map2',
                        'light_beam_asi',
                    },
                    'PED': {
                        # Peds НЕ используют:
                        'day_cols', 'night_cols',     # vcols — map-object feature
                        'modulate_color',             # map-object feature
                        'set_material_alpha',         # ped не использует
                        'light_beam_asi',             # building feature
                        'uv_map2',                    # ped только UV1
                    },
                }.get(pipeline, set())

                def _prop_hinted(prop_key, label):
                    r = fc.row(align=True)
                    if prop_key in _PIPE_FORBIDDEN:
                        r.alert = True
                    r.prop(inu, prop_key, text=label)

                _prop_hinted("export_normals",    "Normals")
                _prop_hinted("light",             "Light")
                _prop_hinted("modulate_color",    "Modulate Color")
                _prop_hinted("set_material_alpha", "Set Material Alpha")
                if _is_sa:
                    _prop_hinted("light_beam_asi", "Light Beam (SA_Light.asi)")
                # 'export_binsplit' (Bin Mesh PLG) намеренно скрыт из UI —
                # см. коммент у его BoolProperty в __init__.py. Дефолт True;
                # отключение делало модель невидимой в игре.
                _prop_hinted("uv_map1", "UV1")
                _prop_hinted("uv_map2", "UV2")
                _prop_hinted("day_cols", "Day")
                if _is_sa:
                    # Night vertex colors kill UV animation in retail SA.
                    # Paint the Night row red and spell out why when the
                    # active mesh carries a UV-anim material.
                    _uv_anim = _obj_has_uv_anim_material(obj)
                    r = fc.row(align=True)
                    if 'night_cols' in _PIPE_FORBIDDEN or (_uv_anim and inu.night_cols):
                        r.alert = True
                    r.prop(inu, "night_cols", text="Night")
                    if _uv_anim and inu.night_cols:
                        warn = fc.column(align=True)
                        warn.alert = True
                        warn.label(text=T("Night ломает UV-анимацию в retail SA"),
                                   **inu_icon(safe_icon('ERROR')))
                        warn.label(text=T("Сними Night (ночные vcol) на UV-аним модели"),
                                   **inu_icon(safe_icon('BLANK1')))




class GTATOOLS_PT_validate_scene(bpy.types.Panel):
    """Pre-export sweep: paintjob slots, quaternion normalisation,
    Modulate Color на прилайтах, парность _ok/_dam.

    Sub-panel живёт внутри Export panel — pre-flight check рядом с
    кнопкой экспорта, без отдельного слота в registry."""
    bl_label = "Проверка перед экспортом"
    bl_idname = "GTATOOLS_PT_validate_scene"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_export_panel"
    bl_options = {'DEFAULT_CLOSED'}

    _SEVERITY_ICON = {
        'ERROR':   'ERROR',
        'WARNING': 'ERROR',  # Blender has no separate WARN icon; ERROR is closest
        'INFO':    'INFO',
    }

    # Human-readable category labels — mirror the (raw) category tag
    # written by core/validate.py. Keep in sync if a new check is added.
    _CATEGORY_LABEL = {
        'Paintjob':       "Paintjob",
        'Quaternions':    "Кватернионы",
        'UVAnimNightVcol': "UV-аним × Night",
        'DamagePair':     "Пары _ok / _dam",
        'OrphanModel':    "Сирые LOD / COL",
        'Orphan2DFX':     "Непривязанный 2DFX",
        'DuplicateID':    "Дубликаты model_id",
        'EmptyMesh':      "Пустые меши",
        'LargeMesh':      "Большие меши",
        'NoTexture':      "Материал без текстуры",
        'SuffixMismatch': "Суффиксы / префиксы",
        'BadScale':       "Scale объектов",
        'LightBeamASI':   "Light Beam ASI",
    }

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(compat.ICON_CHECK))

    def draw(self, context):
        layout = self.layout
        issues = context.scene.inu_settings.inu_validate_issues

        row = layout.row(align=True)
        row.operator("gtatools.validate_run",
                     text=T("Проверить сцену"), **inu_icon(safe_icon('VIEWZOOM')))
        if len(issues):
            row.operator("gtatools.validate_clear",
                         text="", **inu_icon('X'))

        if not len(issues):
            return

        # Summary banner
        errors = sum(1 for i in issues if i.severity == 'ERROR')
        warns = sum(1 for i in issues if i.severity == 'WARNING')
        infos = sum(1 for i in issues if i.severity == 'INFO')
        box = layout.box()
        srow = box.row(align=True)
        if errors:
            srow.label(text=f"{errors} ✗", **inu_icon(safe_icon('CANCEL')))
        if warns:
            srow.label(text=f"{warns} ⚠", **inu_icon(safe_icon('ERROR')))
        if infos:
            srow.label(text=f"{infos} i", **inu_icon(safe_icon('INFO')))
        if not (errors or warns or infos):
            srow.label(text=T("OK"), **inu_icon(compat.ICON_CHECK))

        # ── Group issues by category, preserving first-seen order ──
        # Each category becomes a collapsible-feeling section: a small
        # header with severity colour + count, followed by per-issue
        # rows. A flat list with 6 categories was hard to scan when
        # one category had many entries.
        grouped: "dict[str, list]" = {}
        for issue in issues:
            grouped.setdefault(issue.category, []).append(issue)

        import json as _json
        for cat, group in grouped.items():
            # Worst severity in the group drives the header icon.
            worst = 'INFO'
            for it in group:
                if it.severity == 'ERROR':
                    worst = 'ERROR'
                    break
                if it.severity == 'WARNING' and worst != 'ERROR':
                    worst = 'WARNING'
            cat_box = layout.box()
            header = cat_box.row(align=True)
            # Category label is stored as raw Russian in _CATEGORY_LABEL
            # — wrap with T() so the active locale picks up its
            # eng.py translation at draw time.
            header.label(
                text=f"{T(self._CATEGORY_LABEL.get(cat, cat))}  ({len(group)})",
                **inu_icon(self._SEVERITY_ICON.get(worst, 'INFO')))

            for issue in group:
                ibox = cat_box.box()
                if issue.target_name:
                    ibox.label(text=issue.target_name,
                               **inu_icon(safe_icon('OBJECT_DATA') if issue.target_kind == 'OBJECT'
                                    else 'MATERIAL' if issue.target_kind == 'MATERIAL'
                                    else 'ACTION' if issue.target_kind == 'ACTION'
                                    else 'BLANK1'))
                # Render the message:
                #   • If the check function emitted a translation
                #     template + JSON args, look up the template's
                #     localised form and format the args into it. That
                #     way interpolated messages (e.g. «.DFF vs _DFF»)
                #     follow the active locale.
                #   • Otherwise the message is static — pass it
                #     through T() directly.
                shown = ""
                if issue.message_template:
                    template = T(issue.message_template)
                    args = {}
                    if issue.message_args:
                        try:
                            args = _json.loads(issue.message_args)
                        except Exception:
                            args = {}
                    try:
                        shown = template.format(**args)
                    except (KeyError, IndexError, ValueError):
                        shown = T(issue.message)
                else:
                    shown = T(issue.message)
                ibox.label(text=shown)

                actions = ibox.row(align=True)
                if issue.target_name:
                    op = actions.operator("gtatools.validate_goto",
                                          text=T("Перейти"),
                                          **inu_icon(safe_icon('RESTRICT_SELECT_OFF')))
                    op.target_kind = issue.target_kind
                    op.target_name = issue.target_name
                if issue.fix_op_id:
                    # Each fixer takes a single StringProperty arg.
                    # Dispatch by idname so we pass the correct arg name
                    # (action_name / object_name).
                    if issue.fix_op_id == 'gtatools.validate_fix_quaternions':
                        fix = actions.operator(issue.fix_op_id,
                                               text=T("Нормализовать"),
                                               **inu_icon(safe_icon('FILE_REFRESH')))
                        fix.action_name = issue.fix_arg
                    elif issue.fix_op_id == 'gtatools.validate_fix_suffix':
                        fix = actions.operator(issue.fix_op_id,
                                               text=T("Исправить"),
                                               **inu_icon(safe_icon('OUTLINER_DATA_FONT')))
                        fix.object_name = issue.fix_arg




@apply_order
class GTATOOLS_PT_check_panel(bpy.types.Panel):
    """Панель проверки геометрии и материалов"""
    bl_label = "Проверка"
    bl_idname = "GTATOOLS_PT_check_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(compat.ICON_CHECK))

    def draw_header_preset(self, context):
        on = context.scene.inu_settings.inu_floater_val_visible
        op = self.layout.operator(
            "gtatools.floater_toggle",
            text="", **inu_icon(safe_icon('WINDOW')),
            depress=on, emboss=False,
        )
        op.floater_name = 'val'
        _draw_doc_help(self.layout, 'check')

    def draw(self, context):
        # Read toggle state from scene properties — these persist with
        # the .blend across Blender restarts. Module-level globals would
        # reset to False on every addon reload and de-press the buttons
        # visually even when objects were still hidden in the scene.
        s = context.scene.inu_settings
        _hide_dff = s.gtatools_hide_dff
        _hide_lod = s.gtatools_hide_lod
        _hide_col = s.gtatools_hide_col
        _hide_sha = s.gtatools_hide_sha
        _links_active = s.gtatools_links_active
        layout = self.layout

        # Whole panel as one fused `column(align=True)` — adjacent rows
        # share a 1-px edge with no gap, mirroring the floater's
        # vertical-fusion layout. The actions are different categories
        # but together form the "Проверка" toolkit — visual stack reads
        # as one logical block.
        col = layout.column(align=True)

        # Геометрия (2-col)
        row = col.row(align=True)
        row.operator("gtatools.check_geometry", text=T("Проверка вершин"), **inu_icon(safe_icon('VIEWZOOM')))
        row.operator("gtatools.check_ngons", text=T("Проверка N-gon"), **inu_icon(safe_icon('MESH_DATA')))
        col.operator("gtatools.reset_transform", text=T("Сброс трансформ"), **inu_icon(safe_icon('EMPTY_AXIS')))
        col.operator("gtatools.snap_to_dff", text=T("LOD/COL → DFF"), **inu_icon(safe_icon('SNAP_ON')))
        col.operator("gtatools.fragment_mesh", text=T("Фрагментация меша"), **inu_icon(safe_icon('MOD_EXPLODE')))

        # «Материалы» (Проверка/Очистка/Сортировка) переехали в
        # «Менеджер текстур» — там же где Find/Remove Unused и Find
        # Duplicates, чтобы все операции по чистке ассетов жили в
        # одном месте.

        # Видимость (4-col)
        row = col.row(align=True)
        op = row.operator("gtatools.toggle_visibility", text="DFF",
                          **inu_icon(safe_icon('HIDE_ON') if _hide_dff else 'HIDE_OFF'), depress=_hide_dff)
        op.model_type = 'DFF'
        op = row.operator("gtatools.toggle_visibility", text="LOD",
                          **inu_icon(safe_icon('HIDE_ON') if _hide_lod else 'HIDE_OFF'), depress=_hide_lod)
        op.model_type = 'LOD'
        op = row.operator("gtatools.toggle_visibility", text="COL",
                          **inu_icon(safe_icon('HIDE_ON') if _hide_col else 'HIDE_OFF'), depress=_hide_col)
        op.model_type = 'COL'
        op = row.operator("gtatools.toggle_visibility", text="SHA",
                          **inu_icon(safe_icon('HIDE_ON') if _hide_sha else 'HIDE_OFF'), depress=_hide_sha)
        op.model_type = 'SHA'

        # Visual links between matching DFF/LOD/COL groups — colored
        # dashed lines drawn in the viewport so the user can spot
        # orphaned LODs / unpaired COLs without opening the outliner.
        # Lives here (not in Map/IMG) because it's a check-style
        # overlay, not part of map import workflow.
        col.operator("gtatools.toggle_links",
                     text=T("Связи: ON") if _links_active
                          else T("Связи: OFF"),
                     **inu_icon(safe_icon('LINKED')),
                     depress=_links_active)

        # Batch set type
        row = col.row(align=True)
        row.label(text=T("Тип:"))
        for _t in ('OBJ', 'COL', 'SHA', 'NON'):
            op = row.operator("gtatools.batch_set_type", text=_t)
            op.obj_type = _t



class GTATOOLS_UL_lint_issues(bpy.types.UIList):
    """Scrollable list of binary file lint issues. Filters by severity
    («Только ERROR» toggle) and free-text search via the standard
    UIList search field."""
    bl_idname = "GTATOOLS_UL_lint_issues"

    _SEV_ICON = {'ERROR': 'ERROR', 'WARN': 'ERROR', 'INFO': 'INFO'}

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        ic = self._SEV_ICON.get(item.severity, 'BLANK1')
        row = layout.row(align=True)
        row.label(text="", **inu_icon(safe_icon(ic)))
        # Show filename (basename) + first line of message — multi-line
        # details are shown in the detail-block below the list.
        import os as _os
        fn = _os.path.basename(item.file) if item.file else "?"
        first_line = item.message.split('\n', 1)[0]
        row.label(text=f"{fn} · {first_line}")

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        n = len(items)
        flt_flags = [self.bitflag_filter_item] * n
        flt_neworder = []

        s = context.scene.inu_settings
        only_err = s.gtatools_scan_only_errors
        search = (self.filter_name or "").lower()

        for i, it in enumerate(items):
            if only_err and it.severity != 'ERROR':
                flt_flags[i] = 0
                continue
            if search:
                hay = f"{it.code} {it.file} {it.where} {it.message}".lower()
                if search not in hay:
                    flt_flags[i] = 0

        return flt_flags, flt_neworder


class GTATOOLS_PT_file_scanner(bpy.types.Panel):
    """Combined sub-panel внутри «Проверка»: переключатель сверху между
    двумя режимами анализа — DFF/COL/TXD файлы или IDE/IPL карта.

    Историческое имя ``GTATOOLS_PT_file_scanner`` оставлено, чтобы
    layouts с ``bl_parent_id`` не сломались — содержание расширено
    на два подрежима.
    """
    bl_label = "Анализ карты/файлов"
    bl_idname = "GTATOOLS_PT_file_scanner"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_check_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('VIEWZOOM')))

    def draw(self, context):
        layout = self.layout
        s = context.scene.inu_settings

        # Mode switcher — radio toggle на 2 кнопки сверху панели.
        layout.prop(s, "gtatools_analysis_mode", expand=True)

        if s.gtatools_analysis_mode == 'FILES':
            self._draw_files_mode(context, layout)
        else:
            self._draw_map_mode(context, layout)

    # ── FILES mode (DFF/COL/TXD scanner) ────────────────────────

    def _draw_files_mode(self, context, layout):
        s = context.scene.inu_settings
        wm = context.window_manager

        # Папка
        row = layout.row(align=True)
        row.prop(s, "gtatools_scan_dir", text="")
        layout.prop(s, "gtatools_scan_recursive")

        # Type checkboxes
        row = layout.row(align=True)
        row.prop(s, "gtatools_scan_dff", toggle=True)
        row.prop(s, "gtatools_scan_col", toggle=True)
        row.prop(s, "gtatools_scan_txd", toggle=True)

        # Lint profile + ERROR-only toggle on one row — both are
        # filter axes, keep them visually grouped.
        prof_row = layout.row(align=True)
        prof_row.prop(s, "gtatools_lint_profile", text="")
        prof_row.prop(s, "gtatools_scan_only_errors", text="ERR")

        # Action row
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("gtatools.scan_files", text=T("Сканировать"), **inu_icon(safe_icon('VIEWZOOM')))

        # Results
        n_total = len(wm.gtatools_scan_results)
        if n_total:
            n_err = sum(1 for x in wm.gtatools_scan_results if x.severity == 'ERROR')
            n_warn = sum(1 for x in wm.gtatools_scan_results if x.severity == 'WARN')
            box = layout.box()
            head = box.row(align=True)
            head.label(text=f"ERROR: {n_err}", **inu_icon(safe_icon('ERROR')))
            head.label(text=f"WARN: {n_warn}")
            head.label(text=f"всего: {n_total}")
            head.operator("gtatools.scan_clear", text="", **inu_icon(safe_icon('X')))

            box.template_list("GTATOOLS_UL_lint_issues", "",
                              wm, "gtatools_scan_results",
                              wm, "gtatools_scan_results_index",
                              rows=8)

            # Selected row details + long-form explanation
            idx = wm.gtatools_scan_results_index
            if 0 <= idx < n_total:
                cur = wm.gtatools_scan_results[idx]
                detail = box.box()
                head = detail.row(align=True)
                head.label(text=f"[{cur.severity}] {cur.code}",
                           **inu_icon(safe_icon('INFO')))
                head.operator("gtatools.scan_reveal_file",
                              text="", **inu_icon(safe_icon('FILE_FOLDER')))

                # File path + where
                import os as _os
                detail.label(text=_os.path.basename(cur.file) if cur.file else "?",
                             **inu_icon(safe_icon('FILE')))
                if cur.where:
                    detail.label(text=cur.where, **inu_icon(safe_icon('VIEWZOOM')))
                # Message может содержать "\n" — рендерим построчно.
                msg_col = detail.column(align=True)
                msg_col.scale_y = 0.85
                for ln in cur.message.split('\n'):
                    msg_col.label(text=ln)

                # Long-form explanation: pulled from EXPLANATIONS
                # registry. Auto-wraps via splitting on whitespace —
                # Blender's label() doesn't wrap text by itself.
                from ..core.file_lint import explain
                explanation = explain(cur.code)
                detail.separator()
                detail.label(text=T("Что это значит:"), **inu_icon(safe_icon('QUESTION')))
                # Naive word-wrap at ~42 chars (panel width-dependent —
                # rough fit for default 250px N-panel width).
                words = explanation.split()
                line, lines = [], []
                for w in words:
                    if sum(len(x) for x in line) + len(line) + len(w) > 42:
                        lines.append(' '.join(line))
                        line = [w]
                    else:
                        line.append(w)
                if line:
                    lines.append(' '.join(line))
                # column(align=True) + scale_y<1 ужимает межстрочный gap.
                wrap_col = detail.column(align=True)
                wrap_col.scale_y = 0.7
                for ln in lines:
                    wrap_col.label(text=ln)

            # Save report block
            box2 = layout.box()
            box2.label(text=T("Сохранить отчёт:"))
            box2.prop(s, "gtatools_scan_report_target", text="")
            if s.gtatools_scan_report_target == 'CUSTOM':
                box2.prop(s, "gtatools_scan_report_custom_path", text="")
            elif s.gtatools_scan_report_target == 'BLEND' and not bpy.data.filepath:
                box2.label(text=T("Сцена не сохранена!"), **inu_icon(safe_icon('ERROR')))
            box2.operator("gtatools.scan_save_report",
                          text=T("Сохранить .txt"), **inu_icon(safe_icon('FILE_TEXT')))
        else:
            layout.label(text=T("Список пуст — запустите скан"), **inu_icon(safe_icon('INFO')))

    # ── MAP mode (cross-reference IDE/IPL) ─────────────────────

    def _draw_map_mode(self, context, layout):
        s = context.scene.inu_settings
        wm = context.window_manager

        # Mode picker — dropdown, не expand'нутый radio (3 кнопки в ряд
        # съедают высоту панели).
        mode = s.gtatools_map_analyzer_mode
        layout.prop(s, "gtatools_map_analyzer_mode", text="")

        if mode == 'DAT':
            layout.prop(s, "gtatools_map_analyzer_dat_path", text="")
        elif mode == 'FOLDER':
            row = layout.row(align=True)
            row.prop(s, "gtatools_map_analyzer_folder", text="")
            row.prop(s, "gtatools_map_analyzer_recursive",
                     text="", **inu_icon(safe_icon('FILE_FOLDER')),
                     toggle=True)
        else:  # CUSTOM
            box = layout.box()
            head = box.row(align=True)
            head.label(text=T("IDE файлы:"), **inu_icon(safe_icon('FILE_TEXT')))
            head.operator("gtatools.map_analyzer_add_ide",
                          text="", **inu_icon(safe_icon('ADD')))
            for idx, item in enumerate(s.gtatools_map_analyzer_custom_ides):
                row = box.row(align=True)
                row.prop(item, "path", text="")
                op = row.operator("gtatools.map_analyzer_remove_ide",
                                  text="", **inu_icon(safe_icon('X')))
                op.index = idx

            box = layout.box()
            head = box.row(align=True)
            head.label(text=T("IPL файлы:"), **inu_icon(safe_icon('FILE_VOLUME')))
            head.operator("gtatools.map_analyzer_add_ipl",
                          text="", **inu_icon(safe_icon('ADD')))
            for idx, item in enumerate(s.gtatools_map_analyzer_custom_ipls):
                row = box.row(align=True)
                row.prop(item, "path", text="")
                op = row.operator("gtatools.map_analyzer_remove_ipl",
                                  text="", **inu_icon(safe_icon('X')))
                op.index = idx

        layout.prop(s, "gtatools_map_analyzer_check_img",
                    text=T("Проверять модели в IMG"), toggle=False)

        # Lint profile (shared with File Scanner). Inline label-less
        # to keep one-row compactness.
        layout.prop(s, "gtatools_lint_profile", text=T("Профиль"))

        action = layout.row(align=True)
        action.scale_y = 1.3
        action.prop(s, "gtatools_map_analyzer_only_errors",
                    text="", **inu_icon(safe_icon('ERROR')), toggle=True)
        action.operator("gtatools.analyze_map",
                        text=T("Проанализировать"), **inu_icon(safe_icon('VIEWZOOM')))

        n_total = len(wm.gtatools_map_analyzer_results)
        if not n_total:
            return

        n_err = sum(1 for x in wm.gtatools_map_analyzer_results if x.severity == 'ERROR')
        n_warn = sum(1 for x in wm.gtatools_map_analyzer_results if x.severity == 'WARN')
        summary = getattr(wm, 'gtatools_map_analyzer_stats_summary', '')

        box = layout.box()
        head = box.row(align=True)
        head.label(text=f"E:{n_err}  W:{n_warn}  Σ:{n_total}",
                   **inu_icon(safe_icon('ERROR')))
        save_disabled = not bpy.data.filepath
        save_row = head.row(align=True)
        save_row.enabled = not save_disabled
        save_row.operator("gtatools.map_analyzer_save_report",
                          text="", **inu_icon(safe_icon('FILE_TEXT')))
        head.operator("gtatools.map_analyzer_clear",
                      text="", **inu_icon(safe_icon('X')))

        if summary:
            stats_col = box.column(align=True)
            stats_col.scale_y = 0.85
            for ln in summary.split('\n'):
                stats_col.label(text=ln)

        box.template_list("GTATOOLS_UL_map_lint_issues", "",
                          wm, "gtatools_map_analyzer_results",
                          wm, "gtatools_map_analyzer_results_index",
                          rows=8)

        idx = wm.gtatools_map_analyzer_results_index
        if 0 <= idx < n_total:
            cur = wm.gtatools_map_analyzer_results[idx]
            detail = box.box()
            import os as _os
            fn = _os.path.basename(cur.file) if cur.file else ''
            detail.label(text=f"[{cur.severity}] {cur.code}",
                         **inu_icon(safe_icon('INFO')))
            if fn:
                detail.label(text=fn, **inu_icon(safe_icon('FILE')))
            if cur.where:
                detail.label(text=cur.where)
            msg_col = detail.column(align=True)
            msg_col.scale_y = 0.85
            for ln in cur.message.split('\n'):
                msg_col.label(text=ln)

            from ..core.map_lint import explain
            explanation = explain(cur.code)
            words = explanation.split()
            line, lines = [], []
            for w in words:
                if sum(len(x) for x in line) + len(line) + len(w) > 42:
                    lines.append(' '.join(line))
                    line = [w]
                else:
                    line.append(w)
            if line:
                lines.append(' '.join(line))
            if lines:
                detail.separator()
                wrap_col = detail.column(align=True)
                wrap_col.scale_y = 0.7
                for ln in lines:
                    wrap_col.label(text=ln)


class GTATOOLS_UL_map_lint_issues(bpy.types.UIList):
    """Result list for the Map Analyzer panel. Same shape as the file
    scanner list but reads its own «Только ERROR» toggle from
    ``gtatools_map_analyzer_only_errors`` so the two panels filter
    independently."""
    bl_idname = "GTATOOLS_UL_map_lint_issues"
    _SEV_ICON = {'ERROR': 'ERROR', 'WARN': 'ERROR', 'INFO': 'INFO'}

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        ic = self._SEV_ICON.get(item.severity, 'BLANK1')
        row = layout.row(align=True)
        row.label(text="", **inu_icon(safe_icon(ic)))
        import os as _os
        fn = _os.path.basename(item.file) if item.file else "?"
        # Message может быть multi-line (key=value по строкам). В UIList
        # row показываем только ПЕРВУЮ строку — самую идентифицирующую
        # (обычно ID или имя). Полный текст виден в detail-блоке ниже.
        first_line = item.message.split('\n', 1)[0]
        row.label(text=f"{fn} · {first_line}")

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        n = len(items)
        flt_flags = [self.bitflag_filter_item] * n
        flt_neworder = []
        s = context.scene.inu_settings
        only_err = s.gtatools_map_analyzer_only_errors
        search = (self.filter_name or "").lower()
        for i, it in enumerate(items):
            if only_err and it.severity != 'ERROR':
                flt_flags[i] = 0
                continue
            if search:
                hay = f"{it.code} {it.file} {it.where} {it.message}".lower()
                if search not in hay:
                    flt_flags[i] = 0
        return flt_flags, flt_neworder


@apply_order
class GTATOOLS_PT_texture_browser(bpy.types.Panel):
    """Texture Browser — indexes every texture from every TXD in the
    chosen source (game folder via DAT, arbitrary folder, or hand-
    picked .img/.txd files), with optional IDE cross-reference
    showing how many models use each TXD. Selecting a row triggers
    lazy DXT decode for the in-panel preview, so the index stays
    fast even when scoping 14k+ vanilla textures.
    """
    bl_label = "Текстуры (TXD)"
    bl_idname = "GTATOOLS_PT_texture_browser"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_check_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('TEXTURE')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'texture_browser')

    def draw(self, context):
        import os
        layout = self.layout
        s = context.scene.inu_settings
        wm = context.window_manager

        # Source mode
        layout.prop(s, "gtatools_texture_browser_source", expand=True)

        if s.gtatools_texture_browser_source == 'DAT':
            row = layout.row(align=True)
            row.label(text=T("Использует gta.dat"), **inu_icon(safe_icon('INFO')))
        elif s.gtatools_texture_browser_source == 'FOLDER':
            layout.prop(s, "gtatools_texture_browser_folder", text="")
        elif s.gtatools_texture_browser_source == 'CUSTOM':
            row = layout.row(align=True)
            row.label(text=T("Файлы (.img / .txd):"))
            row.operator("gtatools.texture_browser_add_file",
                         text="", **inu_icon(safe_icon('ADD')))
            for idx, item in enumerate(s.gtatools_texture_browser_custom):
                row = layout.row(align=True)
                row.prop(item, "path", text="")
                op = row.operator("gtatools.texture_browser_remove_file",
                                  text="", **inu_icon(safe_icon('X')))
                op.index = idx

        layout.prop(s, "gtatools_texture_browser_check_ide",
                    text=T("Cross-ref с IDE (used by)"))

        action = layout.row(align=True)
        action.scale_y = 1.3
        action.operator("gtatools.scan_textures",
                        text=T("Сканировать"), **inu_icon(safe_icon('VIEWZOOM')))
        action.operator("gtatools.clear_texture_browser",
                        text="", **inu_icon(safe_icon('X')))

        # Results
        n_total = len(wm.gtatools_texture_browser_results)
        if not n_total:
            return

        # Search field
        layout.prop(s, "gtatools_texture_browser_search",
                    text="", **inu_icon(safe_icon('VIEWZOOM')))

        box = layout.box()
        box.label(text=f"{T('Найдено')}: {n_total}",
                  **inu_icon(safe_icon('TEXTURE')))
        box.template_list("GTATOOLS_UL_texture_browser", "",
                          wm, "gtatools_texture_browser_results",
                          wm, "gtatools_texture_browser_results_index",
                          rows=8)

        idx = wm.gtatools_texture_browser_results_index
        if 0 <= idx < n_total:
            cur = wm.gtatools_texture_browser_results[idx]
            detail = box.box()
            detail.label(
                text=f"{cur.txd_name} → {cur.texture_name}",
                **inu_icon(safe_icon('TEXTURE')))
            info = detail.column(align=True)
            info.scale_y = 0.85
            info.label(text=f"{cur.width} × {cur.height} · "
                            f"{cur.format_label} · "
                            f"depth {cur.depth} · "
                            f"mip {cur.num_levels}")
            info.label(text=f"{T('Архив')}: "
                            f"{os.path.basename(cur.archive_path)}")
            if s.gtatools_texture_browser_check_ide:
                info.label(text=f"{T('Used by')}: {cur.usage_count} "
                                f"{T('моделей')}")

            # Preview image. template_ID can show the Image with
            # a thumbnail; users can hit X to clear without
            # affecting the rest of the panel state.
            preview_img = bpy.data.images.get('INU_TextureBrowser_Preview')
            if preview_img is not None:
                detail.template_preview(preview_img, show_buttons=False)


class GTATOOLS_UL_texture_browser(bpy.types.UIList):
    """Result list for the Texture Browser. Row format:
    [TXD]    [texture]    [WxH]    [fmt]    [used×N]
    """
    bl_idname = "GTATOOLS_UL_texture_browser"

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_property, index):
        row = layout.row(align=True)
        # TXD name (gives the most identifying context first)
        row.label(text=item.txd_name, **inu_icon(safe_icon('TEXTURE')))
        # Texture name
        row.label(text=item.texture_name)
        # Dimensions + format
        row.label(text=f"{item.width}×{item.height}")
        row.label(text=item.format_label)
        # Usage count (only if cross-ref active)
        if item.usage_count > 0:
            row.label(text=f"×{item.usage_count}")

    def filter_items(self, context, data, propname):
        """Substring filter over txd_name + texture_name."""
        items = getattr(data, propname)
        flt_flags = [self.bitflag_filter_item] * len(items)
        flt_neworder = []

        s = context.scene.inu_settings
        search = (getattr(s, 'gtatools_texture_browser_search', '') or '').lower().strip()
        if search:
            for i, it in enumerate(items):
                hay = f"{it.txd_name} {it.texture_name} {it.format_label}".lower()
                if search not in hay:
                    flt_flags[i] = 0
        return flt_flags, flt_neworder


@apply_order
class GTATOOLS_PT_vehicle_panel(bpy.types.Panel):
    """Dedicated panel for vehicle-specific operators — body scale,
    damage variants (_ok / _dam pairs). Moved out of Check so the
    vehicle workflow has a stable home, and so non-vehicle modders
    don't see it during regular map work."""
    bl_label = "Машины"
    bl_idname = "GTATOOLS_PT_vehicle_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    # poll() removed — panel is always visible. Visibility filtering
    # is now handled by the profile system; users who don't want
    # vehicle tools can hide this panel via their profile.

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('AUTO')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'vehicles')

    def draw(self, context):
        layout = self.layout

        # One fused column for the whole panel — Hierarchy-scale +
        # Damage-variants block read as a single Vehicle toolkit без
        # 18-px gap'ов между button-боксами.
        col = layout.column(align=True)
        # Быстрый экспорт машины в один .dff (с встроенной коллизией) —
        # чтобы не лезть в общий диалог экспорта.
        col.operator("gtatools.quick_single_export",
                     text=T("Экспорт машины (один DFF)…"),
                     **inu_icon(safe_icon('EXPORT')))
        col.operator("gtatools.vehicle_scale",
                     text=T("Масштаб машины…"),
                     **inu_icon(safe_icon('FULLSCREEN_ENTER')))

        # Damage variants — header label + fused buttons. Без box, чтобы
        # вся секция была единым визуальным блоком с верхней кнопкой.
        col.label(text=T("Damage variants:"), **inu_icon(safe_icon('AUTO')))
        col.operator("gtatools.vehicle_add_damage_variant",
                     text=T("Создать _dam"), **inu_icon(safe_icon('DUPLICATE')))
        row = col.row(align=True)
        row.label(text=T("Показать:"))
        op = row.operator("gtatools.vehicle_show_damage", text=T("OK"))
        op.state = 'OK'
        op = row.operator("gtatools.vehicle_show_damage", text=T("Dam"))
        op.state = 'DAM'
        op = row.operator("gtatools.vehicle_show_damage", text=T("Оба"))
        op.state = 'BOTH'
        col.operator("gtatools.vehicle_pair_report",
                     text=T("Проверить пары"), **inu_icon(compat.ICON_CHECK))


def _draw_frame_hierarchy(layout, context, validate_template):
    """Shared body for both Frame-Hierarchy sub-panels — the one under
    «Машины» (validate_template='VEHICLE') and the one under «Анимации»
    (='PED'). Rename lives on F2; Set Parent / Unparent are per-row buttons
    in the tree (⤴ = make this frame the parent of the selected one, ⛓ = make
    this frame a root), so the top only carries Validate + Mirror."""
    active = context.active_object

    ops_col = layout.column(align=True)
    row = ops_col.row(align=True)
    if validate_template == 'PED':
        op = row.operator("gtatools.frame_validate",
                          text=T("Validate Ped"),
                          **inu_icon(safe_icon('ARMATURE_DATA')))
        op.template = 'PED'
    else:
        op = row.operator("gtatools.frame_validate",
                          text=T("Validate Vehicle"),
                          **inu_icon(safe_icon('AUTO')))
        op.template = 'VEHICLE'
    row.operator("gtatools.frame_mirror_lr",
                 text=T("Зеркало L↔R"), **inu_icon(safe_icon('MOD_MIRROR')))

    layout.separator()

    if active is None:
        layout.label(text=T("Выдели объект чтобы увидеть иерархию"),
                     **inu_icon(safe_icon('INFO')))
        return

    # Tree is rooted at the TOP of the active object's hierarchy — NOT at the
    # active object — so clicking a frame just highlights it; the whole tree
    # stays visible (it used to re-root to the click and hide everything else).
    root = active
    while root.parent is not None:
        root = root.parent

    layout.label(text=f"{T('Корень')}: {root.name}",
                 **inu_icon(safe_icon('OBJECT_DATA')))
    layout.label(
        text=T("Клик — выделить · ⤴ — родитель выделенного · ⛓ — снять родителя · F2 — переименовать"),
        **inu_icon(safe_icon('INFO')))

    from ..ops.frame_hierarchy import _all_descendants
    items = _all_descendants(root)

    depth_of = {root: 0}
    for it in items[1:]:  # skip root
        d = depth_of.get(it.parent, 0) + 1
        depth_of[it] = d

    box = layout.box()
    col = box.column(align=True)
    max_visible = 80
    shown = 0
    for it in items:
        if shown >= max_visible:
            col.label(text=f"… +{len(items) - max_visible} more")
            break
        row = col.row(align=True)
        depth = depth_of.get(it, 0)
        for _ in range(depth):
            spc = row.column()
            spc.scale_x = 0.5
            spc.label(text="")
        icon = ('MESH_DATA' if it.type == 'MESH'
                else 'ARMATURE_DATA' if it.type == 'ARMATURE'
                else 'EMPTY_AXIS')
        is_active = (it == active)
        name_row = row.row(align=True)
        sel_op = name_row.operator("gtatools.frame_select",
                                   text=it.name, **inu_icon(icon),
                                   emboss=is_active, depress=is_active)
        sel_op.target_name = it.name
        sel_op.extend = False
        # ⤴ make THIS frame the parent of the selected one (current parent
        # of the active is shown depressed). Skipped on the active row.
        if it is not active:
            is_cur_parent = (active.parent is it)
            rp = row.operator("gtatools.frame_reparent", text="",
                              **inu_icon(safe_icon('FILE_PARENT')),
                              depress=is_cur_parent)
            rp.parent_name = it.name
            rp.child_name = ""
        # ⛓ unparent THIS frame (make it a root). Only when it has a parent.
        if it.parent is not None:
            up = row.operator("gtatools.frame_reparent", text="",
                              **inu_icon(safe_icon('UNLINKED')))
            up.parent_name = ""
            up.child_name = it.name
        shown += 1


class GTATOOLS_PT_frame_hierarchy(bpy.types.Panel):
    """Frame Hierarchy Editor — компактное дерево фреймов + per-row кнопки
    смены родителя. DFF-frame-list пишется точно по этим именам, так что
    любая опечатка ломает поведение в игре.

    Vehicle-версия: раскрывающаяся ПОДпанель внутри «Машины», Validate
    Vehicle. Ped-версия — GTATOOLS_PT_frame_hierarchy_anim под «Анимации»."""
    bl_label = "Иерархия фреймов"
    bl_idname = "GTATOOLS_PT_frame_hierarchy"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_vehicle_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('OUTLINER')))

    def draw(self, context):
        _draw_frame_hierarchy(self.layout, context, 'VEHICLE')


class GTATOOLS_PT_frame_hierarchy_anim(bpy.types.Panel):
    """Ped/character copy of the Frame Hierarchy editor — a collapsible
    sub-panel under «Анимации», identical tree + per-row reparent, but with
    the PED validator instead of the VEHICLE one."""
    bl_label = "Иерархия фреймов"
    bl_idname = "GTATOOLS_PT_frame_hierarchy_anim"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_anim_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('OUTLINER')))

    def draw(self, context):
        _draw_frame_hierarchy(self.layout, context, 'PED')


@apply_order
class GTATOOLS_PT_2dfx_panel(bpy.types.Panel):
    """2DFX Effects — the full editor lives in the N-panel: create, attached
    list, per-effect settings, attach/detach, apply-to-selected, and the
    relationship-line toggle. Nothing is shown in the empty's Object data."""
    bl_label = "Эффекты"
    bl_idname = "GTATOOLS_PT_2dfx_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def _is_2dfx(self, context):
        obj = context.active_object
        return (obj and obj.type == 'EMPTY'
                and getattr(obj, 'inu', None)
                and obj.inu.type == '2DFX')

    def draw_header(self, context):
        # Always show the panel icon; append a checkmark when the
        # active object is actually a 2DFX empty, so the header hints
        # whether the panel's content applies to the current selection.
        self.layout.label(text="", **inu_icon(safe_icon('SHADERFX')))
        if self._is_2dfx(context):
            self.layout.label(text="", **inu_icon(compat.ICON_CHECK))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, '2dfx')

    def draw(self, context):
        from .. import _get_effect_emitter_count
        from .. import _draw_label_with_info
        layout = self.layout
        obj = context.active_object
        # bool(): _is_2dfx может вернуть объект/None — а UILayout.enabled
        # принимает только True/False, иначе TypeError обрывает отрисовку.
        is_active = bool(self._is_2dfx(context))

        # Toggle the dashed parent→child relationship lines (drawn across the
        # viewport once 2DFX are attached to a model) — uncheck to hide them.
        _ov = getattr(context.space_data, 'overlay', None)
        if _ov is not None:
            layout.prop(_ov, "show_relationship_lines",
                        text=T("Связи (пунктир)"))

        # Источник текстур эффектов: явный .txd, либо particle.txd/gta3.img из
        # Game Root (resolve_fx_txd_display). «Не выбран» — если нет ни того,
        # ни другого. Справа — папка выбора .txd (gtatools.pick_fx_txd).
        from ..ops.fx_preview import resolve_fx_txd_display
        status = resolve_fx_txd_display() or T("Не выбран")

        # ── Единая компоновка (всегда видна) ──
        # Раскладка не меняется при выборе/создании 2DFX: кнопки действий
        # всегда на месте и просто гаснут серым, когда нет активного эффекта.
        # Слева — источник .txd, «Создать эффект», имя/подсказка. Справа —
        # крупная «Применить настройки» и ряд иконок: привязать / отвязать /
        # обновить превью. Детальные настройки эффекта — в отдельной панели
        # (Object Data Properties → GTA SA: 2DFX).
        settings = obj.inu if is_active else None
        _effect = settings.effect_2dfx if settings else ''
        _type_icon = {
            'LIGHT': 'LIGHT_POINT',
            'PARTICLE': 'PARTICLES',
            'PED_ATTRACTOR': 'COMMUNITY',
            'SUN_GLARE': 'LIGHT_SUN',
        }.get(_effect, compat.ICON_CHECK)
        _attached = bool(is_active and obj.parent and obj.parent.type == 'MESH')

        box = layout.box()

        # Один column(align=True) — все ряды вплотную, без вертикальных
        # зазоров между строками.
        col = box.column(align=True)

        # Источник .txd + выбор папки.
        trow = col.row(align=True)
        trow.label(text=status, **inu_icon(safe_icon('IMAGE_DATA')))
        trow.operator("gtatools.pick_fx_txd", text="",
                      **inu_icon(safe_icon('FILE_FOLDER')))

        # Создать эффект.
        crb = col.row(align=True)
        crb.scale_y = 1.5
        crb.menu("GTATOOLS_MT_create_2dfx",
                 text=T("Создать эффект"), **inu_icon(safe_icon('ADD')))

        # «Применить настройки» + 3 иконки (привязать / отвязать / обновить
        # превью) — ОДНОЙ строкой под «Создать эффект», иконки справа вплотную.
        # «Применить» тянется на всё место, иконки — своей естественной
        # (узкой) шириной. Неактуальные гаснут серым: «применить» без
        # активного 2DFX; «привязать» / «отвязать» — по тому, привязан ли
        # эффект к мешу; превью — только LIGHT/PARTICLE.
        # ВСЕ кнопки — ПРЯМЫЕ дети одного row(align=True). Прямые дети
        # align-ряда сливаются рамками (нет зазоров) и вместе заполняют строку
        # до правого края: текстовая «Применить настройки» тянется, три иконки
        # идут вплотную за ней своей естественной шириной. Никаких вложенных
        # под-рядов / scale_x / ui_units_x — они и ломали то ширину, то край.
        # Вся строка гаснет серой, когда нет активного 2DFX.
        act = col.row(align=True)
        act.scale_y = 1.5
        act.enabled = is_active
        act.operator("gtatools.apply_2dfx_to_selected",
                     text=T("Применить настройки"),
                     **inu_icon(safe_icon('PASTEDOWN')))
        act.operator("gtatools.attach_2dfx", text="",
                     **inu_icon(safe_icon('LINK_BLEND')))
        act.operator("gtatools.detach_2dfx", text="",
                     **inu_icon(safe_icon('UNLINKED')))
        act.operator("gtatools.refresh_2dfx_preview", text="",
                     **inu_icon(safe_icon('FILE_REFRESH')))

        # Имя активного эффекта + подсказка/статус — во всю ширину box.
        if is_active:
            box.label(text=obj.name, **inu_icon(_type_icon))
            if _attached:
                box.label(text=f"Model: {obj.parent.name}",
                          **inu_icon(safe_icon('LINKED')))
            box.label(text=T("Настройки — в свойствах пустышки"),
                      **inu_icon(safe_icon('INFO')))
        else:
            box.label(text=T("Выберите 2DFX Empty для редактирования"),
                      **inu_icon(safe_icon('RESTRICT_SELECT_ON')))

        # Если выделен меш с привязанными эффектами — счётчик + «Отвязать все».
        if not is_active and obj and obj.type == 'MESH':
            # obj.children would still walk every object internally, so the
            # scan is memoised either way — parenting changes bump the
            # generation, so the count can't go stale.
            n_attached = draw_cache.memo(
                ('2dfx_attached', obj.name, len(bpy.data.objects)),
                lambda: sum(1 for c in bpy.data.objects
                            if c.parent == obj and c.type == 'EMPTY'
                            and getattr(c, 'inu', None)
                            and c.inu.type == '2DFX'))
            if n_attached:
                mb = layout.box()
                mb.label(text=f"{T('Привязанные 2DFX:')} {n_attached}",
                         **inu_icon(safe_icon('LINKED')))
                mb.operator("gtatools.detach_all_2dfx",
                            text=T("Отвязать все"),
                            **inu_icon(safe_icon('UNLINKED')))



# Short per-effect titles for the "GTA SA: <тип>" panel header.
_2DFX_TITLE = {
    'LIGHT': "Свет",
    'PARTICLE': "Частица",
    'PED_ATTRACTOR': "Ped Attractor",
    'SUN_GLARE': "Блик солнца",
    'ENTER_EXIT': "Вход/Выход",
    'ROAD_SIGN': "Дорожный знак",
    'ESCALATOR': "Эскалатор",
    'RAW_2DFX': "Raw",
}


class GTATOOLS_PT_2dfx_settings(bpy.types.Panel):
    """2DFX per-effect SETTINGS on the empty itself (Object Data
    Properties) — presets + light / particle / behaviour / shadow / flags.
    The action buttons (create, attach, apply, preview, relationship-line
    toggle) stay in the N-panel 2DFX panel."""
    # Empty bl_label — the full title ("GTA SA: <тип>") is drawn dynamically
    # in draw_header so it reflects the selected effect type.
    bl_label = ""
    bl_idname = "GTATOOLS_PT_2dfx_settings"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == 'EMPTY'
                    and getattr(obj, 'inu', None)
                    and obj.inu.type == '2DFX')

    def draw_header(self, context):
        obj = context.active_object
        eff = getattr(obj.inu, 'effect_2dfx', '') if obj and getattr(obj, 'inu', None) else ''
        title = _2DFX_TITLE.get(eff, "2DFX")
        self.layout.label(text="GTA SA: " + T(title))

    def draw(self, context):
        from .. import _get_effect_emitter_count
        layout = self.layout
        obj = context.active_object
        settings = obj.inu
        effect = settings.effect_2dfx
        main_box = layout
        if effect == 'LIGHT':
            _ensure_2dfx_tips(obj)
            # Presets
            box_p = main_box.box()
            box_p.label(text=T("Пресеты:"), **inu_icon(safe_icon('PRESET')))
            row_p = box_p.row(align=True)
            row_p.prop(settings, "preset_2dfx", text="")
            row_p.operator("gtatools.apply_2dfx_preset", text=T("Применить"), **inu_icon(compat.ICON_CHECK))

            # Each Light section is a collapsible box. Default-open
            # state lives on the scene so it persists across selection
            # changes and undo. «Свойства» starts open (most-used
            # fields), the rest start closed to keep the panel compact.
            scn = context.scene

            def _section(parent, prop, label, icon='NONE'):
                """Header row + content box. Returns the content box if
                expanded, else None so caller can skip drawing fields."""
                row = parent.row(align=True)
                row.prop(scn.inu_settings, prop,
                         **inu_icon(safe_icon('TRIA_DOWN') if getattr(scn.inu_settings, prop) else 'TRIA_RIGHT'),
                         text=label, emboss=False, toggle=True)
                if getattr(scn.inu_settings, prop):
                    return parent.box()
                return None

            # ── Свойства света (color, corona, range, texture) ──
            sec = _section(main_box, "gtatools_2dfx_show_props",
                           T("Свойства света"))
            if sec is not None:
                sec.prop(settings, "color_2dfx", text=T("Цвет"))
                col = sec.column(align=True)
                col.prop(settings, "corona_size_2dfx", text=T("Размер короны"))
                col.prop(obj, '["2dfx_corona_far_clip"]', text=T("Дальность отрисовки"))
                col.prop(obj, '["2dfx_pointlight_range"]', text=T("Радиус света"))
                sec.label(text=T("Имя короны:"))
                sec.prop(settings, "corona_tex_2dfx", text="")

            # ── Поведение (показ + блики + отражение) ──
            sec = _section(main_box, "gtatools_2dfx_show_behavior",
                           T("Поведение"))
            if sec is not None:
                col = sec.column(align=True)
                col.label(text=T("Режим показа:"))
                col.prop(settings, "show_mode_2dfx", text="")
                col.label(text=T("Тип бликов:"))
                col.prop(settings, "flare_type_2dfx", text="")
                sec.prop(obj, '["2dfx_corona_enable_reflection"]',
                         text=T("Отражение короны"))

            # ── Тень ──
            sec = _section(main_box, "gtatools_2dfx_show_shadow",
                           T("Тень"))
            if sec is not None:
                col = sec.column(align=True)
                col.prop(settings, "shadow_size_2dfx", text=T("Размер пятна"))
                col.prop(obj, '["2dfx_shadow_z_distance"]', text=T("Дистанция"))
                col.prop(obj, '["2dfx_shadow_color_multiplier"]', text=T("Множитель"))
                sec.label(text=T("Имя тени:"))
                sec.prop(settings, "shadow_tex_2dfx", text="")
                sec.label(text=T("Размер = 0 → только корона, без пятна"),
                          **inu_icon(safe_icon('INFO')))

            # ── Флаги (semantic groups, per-bit tooltip on hover) ──
            sec = _section(main_box, "gtatools_2dfx_show_flags",
                           T("Флаги"))
            if sec is not None:
                _draw_2dfx_flag_box(sec, obj)

            # View Vector — always-visible, only present on imported
            # lights with explicit direction (rare, so OK as plain box).
            if '2dfx_look_direction' in obj:
                box5 = main_box.box()
                box5.label(text=T("Вектор направления:"), **inu_icon(safe_icon('EMPTY_ARROWS')))
                box5.prop(obj, '["2dfx_look_direction"]', text="")


        elif effect == 'PARTICLE':
            box = main_box.box()
            box.label(text=T("Свойства частицы:"), **inu_icon(safe_icon('PARTICLES')))
            row = box.row(align=True)
            row.prop(obj.inu, 'particle_effect_2dfx', text=T("Эффект"))
            row.operator("gtatools.particle_effect_new", text="", **inu_icon(safe_icon('ADD')))
            row.operator("gtatools.particle_effect_delete", text="", **inu_icon(safe_icon('REMOVE')))
            row.operator("gtatools.reload_effects_fxp", text="", **inu_icon(safe_icon('FILE_REFRESH')))

            # Emitter switcher (only if system has > 1 emitter)
            eff_name = obj.get('2dfx_effect_name', '') or ''
            if eff_name:
                em_total = _get_effect_emitter_count(eff_name)
                if em_total > 1:
                    em_row = box.row(align=True)
                    op = em_row.operator("gtatools.particle_emitter_switch", text="", **inu_icon(safe_icon('TRIA_LEFT')))
                    op.direction = -1
                    em_row.label(text=f"Emitter {obj.inu.particle_emitter_index + 1} / {em_total}")
                    op = em_row.operator("gtatools.particle_emitter_switch", text="", **inu_icon(safe_icon('TRIA_RIGHT')))
                    op.direction = 1
                    box.label(text=T("Переключение сбросит правки — сохраняйте первыми"), **inu_icon(safe_icon('INFO')))

            # Live simulation toggle (scene-global)
            sim_row = box.row(align=True)
            sim_row.prop(
                context.scene.inu_settings, 'gtatools_particle_sim',
                text=T("Симуляция"),
                **inu_icon(safe_icon('PLAY') if context.scene.inu_settings.gtatools_particle_sim else 'PAUSE'),
                toggle=True,
            )

            inu = obj.inu
            scene = context.scene

            def _section(parent, prop_name: str, label: str, icon: str):
                """Collapsible section helper. Returns the content box or None."""
                expanded = getattr(scene.inu_settings, prop_name)
                header = parent.row(align=True)
                header.prop(
                    scene.inu_settings, prop_name,
                    **inu_icon(safe_icon('TRIA_DOWN') if expanded else 'TRIA_RIGHT'),
                    text="", emboss=False,
                )
                header.label(text=label, **inu_icon(icon))
                if expanded:
                    return parent.box()
                return None

            # ── Texture / blend ── #
            tex_box = _section(box, 'gtatools_pfx_exp_texture', T("Спрайт и смешивание"), 'TEXTURE')
            if tex_box:
                # Searchable list of loaded sprites instead of blind typing.
                # particle.txd textures auto-load into bpy.data.images; the
                # button next to it loads them if the list is still empty.
                trow = tex_box.row(align=True)
                trow.prop_search(inu, 'particle_texture', bpy.data, 'images',
                                 text=T("Текстура"))
                trow.operator('gtatools.load_fx_textures', text='',
                              **inu_icon(safe_icon('FILE_REFRESH')))
                row = tex_box.row(align=True)
                row.prop(inu, 'particle_src_blend', text="SRC")
                row.prop(inu, 'particle_dst_blend', text="DST")

            # ── Colour ── #
            col_box = _section(box, 'gtatools_pfx_exp_color', T("Цвет (start → end)"), 'COLOR')
            if col_box:
                col_box.prop(inu, 'particle_color_start', text=T("Начало"))
                col_box.prop(inu, 'particle_color_mid_enabled', text=T("Средний"), toggle=True)
                if inu.particle_color_mid_enabled:
                    col_box.prop(inu, 'particle_color_mid', text=T("Middle"))
                    col_box.prop(inu, 'particle_color_mid_time', text=T("Mid time"), slider=True)
                col_box.prop(inu, 'particle_color_end', text=T("Конец"))

            # ── Size ── #
            size_box = _section(box, 'gtatools_pfx_exp_size', T("Размер"), 'FULLSCREEN_ENTER')
            if size_box:
                row = size_box.row(align=True)
                row.prop(inu, 'particle_size_start', text=T("Начало"))
                row.prop(inu, 'particle_size_end', text=T("Конец"))

            # ── Emission ── #
            em_box = _section(box, 'gtatools_pfx_exp_emission', T("Эмиссия"), 'OUTLINER_OB_FORCE_FIELD')
            if em_box:
                em_box.prop(inu, 'particle_life', text=T("Жизнь"))
                em_box.prop(inu, 'particle_life_bias', text=T("Life bias"))
                em_box.prop(inu, 'particle_rate', text=T("Rate"))
                em_box.prop(inu, 'particle_speed', text=T("Скорость"))
                em_box.prop(inu, 'particle_speed_bias', text=T("Speed bias"))
                em_box.prop(inu, 'particle_direction', text=T("Направление"))
                row = em_box.row(align=True)
                row.prop(inu, 'particle_angle_min', text=T("Angle min"))
                row.prop(inu, 'particle_angle_max', text=T("Angle max"))
                em_box.prop(inu, 'particle_volume', text=T("Box"))
                em_box.prop(inu, 'particle_offset', text=T("Offset"))
                row = em_box.row(align=True)
                row.prop(inu, 'particle_rotation_min', text=T("Rot min"))
                row.prop(inu, 'particle_rotation_max', text=T("Rot max"))

            # ── Physics ── #
            ph_box = _section(box, 'gtatools_pfx_exp_physics', T("Физика"), 'PHYSICS')
            if ph_box:
                ph_box.prop(inu, 'particle_force', text=T("Force"))
                row = ph_box.row(align=True)
                row.prop(inu, 'particle_friction', text=T("Friction"))
                row.prop(inu, 'particle_wind', text=T("Wind"))
                row = ph_box.row(align=True)
                row.prop(inu, 'particle_noise', text=T("Noise"))
                row.prop(inu, 'particle_jitter', text=T("Jitter"))
                row = ph_box.row(align=True)
                row.prop(inu, 'particle_rotspeed_min', text=T("RotSpd min"))
                row.prop(inu, 'particle_rotspeed_max', text=T("RotSpd max"))
                row = ph_box.row(align=True)
                row.prop(inu, 'particle_ground_bounce', text=T("Bounce"))
                row.prop(inu, 'particle_ground_speedmult', text=T("SpeedMult"))

            # ── System-level (FX_SYSTEM_DATA header) ── #
            sys_box = _section(box, 'gtatools_pfx_exp_system', T("Система"), 'WORLD')
            if sys_box:
                sys_box.prop(inu, 'particle_sys_length', text=T("Length"))
                sys_box.prop(inu, 'particle_sys_playmode', text=T("Play mode"))
                sys_box.prop(inu, 'particle_sys_culldist', text=T("Cull dist"))

            # ── Curve editor (B1) ── #
            cv_box = _section(box, 'gtatools_pfx_exp_curves', T("Кривые (keyframes)"), 'FCURVE')
            if cv_box:
                # Curve picker row
                pick_row = cv_box.row(align=True)
                pick_row.operator(
                    "gtatools.particle_curve_select",
                    text=inu.particle_curve_name or T("Выбрать кривую..."),
                    **inu_icon(safe_icon('VIEWZOOM')),
                )

                if inu.particle_curve_name:
                    keys = inu.particle_curve_keys
                    # Header
                    hdr = cv_box.row(align=True)
                    hdr.label(text=T(f"Ключи ({len(keys)}):"))
                    hdr.operator("gtatools.particle_curve_key_add", text="", **inu_icon(safe_icon('ADD')))
                    hdr.operator("gtatools.particle_curve_key_remove", text="", **inu_icon(safe_icon('REMOVE')))

                    # Keyframe rows (time, val)
                    if len(keys) == 0:
                        cv_box.label(text=T("Нет ключей"), **inu_icon(safe_icon('INFO')))
                    else:
                        for i, kf in enumerate(keys):
                            r = cv_box.row(align=True)
                            # Active-row indicator (click selects for deletion)
                            is_active = (i == inu.particle_curve_key_index)
                            op = r.operator(
                                "gtatools.particle_curve_key_select_row",
                                text="", depress=is_active,
                                **inu_icon(safe_icon('RADIOBUT_ON') if is_active else 'RADIOBUT_OFF'),
                            )
                            op.index = i
                            r.prop(kf, 'time', text="t")
                            r.prop(kf, 'val', text="v")

                    # Write to FXP button
                    write_row = cv_box.row(align=True)
                    write_row.scale_y = 1.2
                    write_row.operator(
                        "gtatools.particle_curve_write",
                        text=T("Записать кривую в effects.fxp"),
                        **inu_icon(safe_icon('FILE_TICK')),
                    )

            # Save to effects.fxp
            save_row = box.row(align=True)
            save_row.scale_y = 1.3
            save_row.operator(
                "gtatools.save_particle_effect",
                text=T("Сохранить в effects.fxp"),
                **inu_icon(safe_icon('FILE_TICK')),
            )

        elif effect == 'PED_ATTRACTOR':
            box = main_box.box()
            box.label(text=T("Точка притяжения:"), **inu_icon(safe_icon('COMMUNITY')))
            if '2dfx_attractor_type' in obj:
                box.prop(obj, '["2dfx_attractor_type"]', text=T("Тип аттрактора"))
            if '2dfx_rotation_matrix' in obj:
                box.prop(obj, '["2dfx_rotation_matrix"]', text=T("Матрица поворота"))
            if '2dfx_external_script' in obj:
                box.prop(obj, '["2dfx_external_script"]', text=T("Внешний скрипт"))
            if '2dfx_ped_probability' in obj:
                box.prop(obj, '["2dfx_ped_probability"]', text=T("Вероятность NPC"))

        elif effect == 'SUN_GLARE':
            box = main_box.box()
            box.label(text=T("Солнечный блик"), **inu_icon(safe_icon('LIGHT_SUN')))
            box.label(text=T("Только позиция (без доп. данных)"))

        elif effect == 'ENTER_EXIT':
            box = main_box.box()
            box.label(text=T("Вход/Выход (интерьер):"), **inu_icon(safe_icon('EMPTY_ARROWS')))
            col = box.column(align=True)
            col.prop(settings, "ee_interior", text=T("Интерьер #"))
            col.prop(settings, "ee_interior_name", text=T("Имя интерьера"))
            col = box.column(align=True)
            col.prop(settings, "ee_enter_angle", text=T("Угол входа"))
            col.prop(settings, "ee_exit_angle", text=T("Угол выхода"))
            col.prop(settings, "ee_exit_loc", text=T("Позиция выхода"))
            row = box.row(align=True)
            row.prop(settings, "ee_radius_x", text=T("Радиус X"))
            row.prop(settings, "ee_radius_y", text=T("Радиус Y"))
            row = box.row(align=True)
            row.prop(settings, "ee_time_on", text=T("Вкл"))
            row.prop(settings, "ee_time_off", text=T("Выкл"))
            box.prop(settings, "ee_sky_color", text=T("Цвет неба"))

        elif effect == 'ROAD_SIGN':
            box = main_box.box()
            box.label(text=T("Дорожный знак (текст):"), **inu_icon(safe_icon('FONT_DATA')))
            col = box.column(align=True)
            n = max(1, min(4, settings.sign_lines))
            for li in range(n):
                col.prop(settings, "sign_text%d" % li, text=T("Строка %d") % (li + 1))
            box.prop(settings, "sign_lines", text=T("Строк"))
            box.prop(settings, "sign_maxchars", text=T("Символов/строку"))
            box.prop(settings, "sign_color", text=T("Цвет"))
            box.prop(settings, "sign_size", text=T("Размер"))
            box.prop(settings, "sign_rotation", text=T("Поворот"))

        elif effect == 'ESCALATOR':
            box = main_box.box()
            box.label(text=T("Эскалатор:"), **inu_icon(safe_icon('SORTSIZE')))
            col = box.column(align=True)
            col.prop(settings, "esc_bottom", text=T("Низ"))
            col.prop(settings, "esc_top", text=T("Верх"))
            col.prop(settings, "esc_end", text=T("Конец"))
            box.prop(settings, "esc_direction", text=T("Направление"), expand=True)

        elif effect == 'RAW_2DFX':
            box = main_box.box()
            box.label(text=T("Сохранённый эффект"), **inu_icon(safe_icon('LOCKED')))
            box.label(text=f"type {obj.get('2dfx_raw_effect_id', '?')}, "
                           f"{len(obj.get('2dfx_raw_bytes', []))} B")
            box.label(text=T("Байт-в-байт round-trip, не редактируется"),
                      **inu_icon(safe_icon('INFO')))


def _strip_dup_suffix(name: str) -> str:
    """Drop Blender's ``.001`` / ``.002`` duplicate suffix."""
    if '.' in name:
        head, tail = name.rsplit('.', 1)
        if tail.isdigit():
            return head
    return name


def _find_id_conflicts(obj, model_id):
    """Names of other meshes claiming the same IDE model_id.

    Duplicates of the SAME model (``foo``/``foo.001``) legitimately share
    an id — those are extra placements, not a conflict. Only a different
    base name counts. Called through ``draw_cache.memo`` — see the call
    site; this walks every object in the file.
    """
    self_base = _strip_dup_suffix(obj.name)
    return [o.name for o in bpy.data.objects
            if o.type == 'MESH' and o != obj
            and hasattr(o, 'inu') and o.inu.model_id == model_id
            and _strip_dup_suffix(o.name) != self_base]


@apply_order
class GTATOOLS_PT_object_ide_ipl_panel(bpy.types.Panel):
    """Per-object IDE/IPL properties (N-sidebar, DATA zone)"""
    bl_label = "Object IDE / IPL"
    bl_idname = "GTATOOLS_PT_object_ide_ipl_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('COPY_ID')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'ide_ipl')

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        scn = context.scene
        obj = context.active_object
        inu = obj.inu

        col = layout.column(align=True)
        col.prop(inu, "model_id", text="Model ID")
        # Дистанции по смыслу: LOD-модель → только LOD Dist; основная модель →
        # Draw Dist, а LOD Dist — лишь если есть LOD-партнёр.
        _detected = get_model_type_cached(obj)[0]
        _has_lod = bool(getattr(inu, 'lod_object', None))
        if _detected == 'LOD':
            col.prop(inu, "lod_draw_distance", text="LOD Dist")
        else:
            col.prop(inu, "draw_distance", text="Draw Dist")
            if _has_lod:
                col.prop(inu, "lod_draw_distance", text="LOD Dist")

        # Batch: apply distances to all selected MESH objects
        n_sel = sum(1 for o in context.selected_objects if o.type == 'MESH')
        if n_sel > 1:
            layout.operator(
                "gtatools.batch_set_distance",
                text=f"{T('Применить к выделенным')} ({n_sel})",
                **inu_icon(safe_icon('STICKY_UVS_LOC')),
            )

        # Flags with expandable checkboxes
        row = layout.row(align=True)
        row.prop(inu, "ide_flags", text="Flags")
        row.prop(scn.inu_settings, "gtatools_show_ide_flags",
                 **inu_icon(safe_icon('TRIA_DOWN') if scn.inu_settings.gtatools_show_ide_flags else 'TRIA_RIGHT'),
                 text="", emboss=False)
        if scn.inu_settings.gtatools_show_ide_flags:
            fbox = layout.box()
            fc = fbox.column(align=True)
            # Show only the checkboxes valid for the scene's active
            # game — III/VC/SA each support a different subset of the
            # 32-bit objs.flags column. Source: gtamods.com/wiki/
            # Item_Definition (verified 2026-05).
            from ..core.ide_flag_translate import flag_props_for_game
            from ..core import game_versions as _gv
            _game = _gv.game_of_scene(scn)
            for prop in flag_props_for_game(_game):
                fc.prop(inu, prop)

        row = layout.row(align=True)
        row.prop(inu, "interior_id", text="Interior")
        row.prop(inu, "lod_index", text="LOD")

        # Breakable object (DFF chunk 0x253F2FD)
        box = layout.box()
        row = box.row(align=True)
        row.prop(inu, "breakable", text=T("Разрушаемый (Breakable)"))
        if inu.breakable:
            box.prop(inu, "breakable_force", text=T("Break Force"))
            box.prop(inu, "breakable_offset", text=T("Смещение силы"))
            box.prop(inu, "breakable_alloc_auto",
                     text=T("Авто-буферы осколков"))
            if not inu.breakable_alloc_auto:
                col = box.column(align=True)
                col.prop(inu, "breakable_verts_alloc", text=T("Вершины"))
                col.prop(inu, "breakable_faces_alloc", text=T("Грани"))
                col.prop(inu, "breakable_mats_alloc", text=T("Материалы"))
                col.prop(inu, "breakable_uvs_alloc", text=T("UV"))

        # Check for ID conflicts — ignore Blender duplicate suffixes (.001,
        # .002, ...). Multiple placements of the same model legitimately
        # share a model_id; only a different base name counts as a real
        # conflict (two distinct meshes claiming the same IDE entry).
        # Memoised: this walks EVERY object in the file and touches an RNA
        # property on each, which on a map scene is far too much to repeat
        # per redraw. The key carries everything the answer depends on.
        if inu.model_id > 0:
            conflicts = draw_cache.memo(
                ('id_conflicts', obj.name, inu.model_id, len(bpy.data.objects)),
                lambda: _find_id_conflicts(obj, inu.model_id))
            if conflicts:
                layout.label(text=f"ID {inu.model_id}: {T('конфликт с')} {', '.join(conflicts[:3])}", **inu_icon(safe_icon('ERROR')))



class GTATOOLS_PT_object_inu_tools(bpy.types.Panel):
    """INU Tools — full per-object model settings in Object Properties"""
    bl_label = "INU Tools: Model"
    bl_idname = "GTATOOLS_PT_object_inu_tools"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('COPY_ID')))

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type in ('MESH', 'EMPTY')

    def draw(self, context):
        from ..tools.model_utils import get_model_type_cached
        layout = self.layout
        scn = context.scene
        obj = context.active_object
        inu = obj.inu

        # ── Тип (по имени + manual) ──
        box = layout.box()
        box.label(text=T("Тип:"), **inu_icon(safe_icon('OBJECT_DATA')))
        detected, _ = get_model_type_cached(obj)   # draw hot path — кэш
        name_row = box.row(align=True)
        name_row.enabled = False
        name_row.label(text=f"{T('По имени:')} {detected or '—'}")
        box.prop(inu, "type", text=T("Экспортировать как"))
        # Явный маркер в имени (_DFF/_LOD) сильнее тега inu.type — так же, как
        # в classify_model. Тег COL/SHA, унаследованный Shift+D с коллизии или
        # оставшийся от Batch Set Type, раньше молча уводил меш в встроенную
        # коллизию: .dff уходил с пустым GeometryList и в игре не рисовался.
        # Экспорт это игнорирует, но противоречие в панели надо показать.
        if detected in ('DFF', 'LOD') and inu.type in ('COL', 'SHA'):
            warn = box.row(align=True)
            warn.label(text=f"{T('Маркер в имени важнее — экспорт как')} {detected}",
                       **inu_icon(safe_icon('INFO')))

        # ── IDE / Placement ──
        box = layout.box()
        box.label(text="IDE / Placement", **inu_icon(safe_icon('COPY_ID')))
        col = box.column(align=True)
        col.prop(inu, "model_id", text="Model ID")
        col.prop(inu, "txd_name", text="TXD")
        # Дистанции по смыслу: LOD-модель → только LOD Dist; основная модель →
        # Draw Dist, а LOD Dist — лишь если есть LOD-партнёр (`detected` выше).
        _has_lod = bool(getattr(inu, 'lod_object', None))
        if detected == 'LOD':
            col.prop(inu, "lod_draw_distance", text="LOD Dist")
        else:
            col.prop(inu, "draw_distance", text="Draw Dist")
            if _has_lod:
                col.prop(inu, "lod_draw_distance", text="LOD Dist")
        col.prop(inu, "interior_id", text="Interior")
        # LOD partner — clickable object picker. Auto-filled on Map
        # Import (preserves the IPL lod_index relationship even when
        # vanilla LOD names don't follow the lod* convention), but
        # the user can re-target it if naming heuristics get it wrong.
        # Map Export converts the pointer back into IPL lod_index.
        # LOD partner + короткая кнопка авто-поиска LOD в сцене по имени.
        _lodrow = col.row(align=True)
        _lodrow.prop(inu, "lod_object", text="LOD partner")
        _lodbtn = _lodrow.row(align=True)
        _lodbtn.ui_units_x = 4.5
        _lodbtn.operator("gtatools.auto_find_lod", text=T("Поиск LOD"),
                         **inu_icon(safe_icon('VIEWZOOM')))
        # Model ID самого LOD-объекта — виден и правится тут же. По нему
        # «Add в IPL» пишет LOD-инстанс (id=0 → авто DFF+1 при добавлении).
        _lodo = getattr(inu, 'lod_object', None)
        _lodinu = getattr(_lodo, 'inu', None) if _lodo is not None else None
        if _lodinu is not None:
            col.prop(_lodinu, "model_id", text="LOD ID")

        # Batch distance button
        n_sel = sum(1 for o in context.selected_objects if o.type == 'MESH')
        if n_sel > 1:
            box.operator(
                "gtatools.batch_set_distance",
                text=f"{T('Применить к выделенным')} ({n_sel})",
                **inu_icon(safe_icon('STICKY_UVS_LOC')),
            )

        # Clear Model ID on selection — quick path to re-run Auto Assign
        # on objects that already have IDs (duplicated with Shift+D,
        # imported from map, etc. — their inu.model_id carries over).
        clear_row = box.row(align=True)
        clear_row.operator(
            "gtatools.id_manager_clear_selected",
            text=f"{T('Очистить ID выделенных')} ({n_sel})" if n_sel > 1
                 else T("Очистить ID"),
            **inu_icon('X'),
        )

        # IDE Flags (collapsible)
        row = box.row(align=True)
        row.prop(inu, "ide_flags", text="IDE Flags")
        row.prop(scn.inu_settings, "gtatools_show_ide_flags",
                 **inu_icon(safe_icon('TRIA_DOWN') if scn.inu_settings.gtatools_show_ide_flags else 'TRIA_RIGHT'),
                 text="", emboss=False)
        if scn.inu_settings.gtatools_show_ide_flags:
            fbox = box.box()
            fc = fbox.column(align=True)
            # Game-aware list: see N-sidebar twin above. Keeping both
            # locations in sync so the Object Properties panel and the
            # 3D-view sidebar always show the same set of checkboxes.
            from ..core.ide_flag_translate import flag_props_for_game
            from ..core import game_versions as _gv
            _game = _gv.game_of_scene(scn)
            for prop in flag_props_for_game(_game):
                fc.prop(inu, prop)

        # ── DFF Flags (collapsible, only for mesh) ──
        if obj.type == 'MESH':
            box = layout.box()
            row = box.row(align=True)
            row.prop(scn.inu_settings, "gtatools_show_dff_flags",
                     **inu_icon(safe_icon('TRIA_DOWN') if scn.inu_settings.gtatools_show_dff_flags else 'TRIA_RIGHT'),
                     text="DFF Flags", emboss=False)
            if scn.inu_settings.gtatools_show_dff_flags:
                fc = box.column(align=True)
                from ..core import game_versions as _gv
                _is_sa = (_gv.game_of_scene(scn) == 'SA')
                pipeline = scn.inu_settings.gtatools_export_pipeline

                # Mirror the N-sidebar twin above — same pipeline-flag
                # mismatch hinting so Object Properties и N-sidebar
                # showing inconsistent advice не получается.
                # Blacklist of flags that DON'T BELONG on the chosen
                # pipeline — for these the row is painted red regardless
                # of current on/off value. Логика: «этот флаг вообще не
                # для этого пайплайна, лучше выключи». Юзер сам решает
                # включать flags которые «обязательные», но видит явное
                # предупреждение для несовместимых.
                _PIPE_FORBIDDEN = {
                    '0x53F2009A': {  # Vehicle — кузов машины
                        'day_cols', 'night_cols',
                        'light_beam_asi',  # Vehicle pipeline drops Light Beam
                    },
                    '0x53F20098': {  # D/N Building
                        # D/N светится через prelit day+night vcols:
                        # ни свет, ни нормали, ни mat-alpha, ни light beam.
                        'uv_map2',
                        'light',               # dynamic light не нужен
                        'export_normals',      # нормали => мерцание
                        'set_material_alpha',  # не для D/N building
                        'light_beam_asi',      # building feature, не D/N
                    },
                    '0x53F2009C': {  # Building (без D/N)
                        'night_cols',     # plain building, не D/N
                        'uv_map2',
                        'light_beam_asi',
                    },
                    'PED': {
                        # Peds НЕ используют:
                        'day_cols', 'night_cols',     # vcols — map-object feature
                        'modulate_color',             # map-object feature
                        'set_material_alpha',         # ped не использует
                        'light_beam_asi',             # building feature
                        'uv_map2',                    # ped только UV1
                    },
                }.get(pipeline, set())

                def _prop_hinted(prop_key, label):
                    r = fc.row(align=True)
                    if prop_key in _PIPE_FORBIDDEN:
                        r.alert = True
                    r.prop(inu, prop_key, text=label)

                _prop_hinted("export_normals",    "Normals")
                _prop_hinted("light",             "Light")
                _prop_hinted("modulate_color",    "Modulate Color")
                _prop_hinted("set_material_alpha", "Set Material Alpha")
                if _is_sa:
                    _prop_hinted("light_beam_asi", "Light Beam (SA_Light.asi)")
                # 'export_binsplit' (Bin Mesh PLG) намеренно скрыт из UI —
                # см. коммент у его BoolProperty в __init__.py. Дефолт True;
                # отключение делало модель невидимой в игре.
                _prop_hinted("uv_map1", "UV1")
                _prop_hinted("uv_map2", "UV2")
                _prop_hinted("day_cols", "Day")
                if _is_sa:
                    # Mirror the N-sidebar: Night vertex colors disable
                    # UV animation in retail SA — warn when both are on.
                    _uv_anim = _obj_has_uv_anim_material(obj)
                    r = fc.row(align=True)
                    if 'night_cols' in _PIPE_FORBIDDEN or (_uv_anim and inu.night_cols):
                        r.alert = True
                    r.prop(inu, "night_cols", text="Night")
                    if _uv_anim and inu.night_cols:
                        warn = fc.column(align=True)
                        warn.alert = True
                        warn.label(text=T("Night ломает UV-анимацию в retail SA"),
                                   **inu_icon(safe_icon('ERROR')))
                        warn.label(text=T("Сними Night (ночные vcol) на UV-аним модели"),
                                   **inu_icon(safe_icon('BLANK1')))

        # ── Pipeline ──
        if obj.type == 'MESH':
            box = layout.box()
            box.label(text="Pipeline", **inu_icon(safe_icon('NODETREE')))
            box.prop(inu, "pipeline", text="")
            if inu.pipeline == 'CUSTOM':
                box.prop(inu, "custom_pipeline", text="")

        # ── Breakable ──
        if obj.type == 'MESH':
            box = layout.box()
            box.prop(inu, "breakable", text=T("Разрушаемый (Breakable)"))
            if inu.breakable:
                box.prop(inu, "breakable_force", text=T("Break Force"))

        # ── 2DFX (only for EMPTY with type='2DFX') ──
        if obj.type == 'EMPTY' and inu.type == '2DFX':
            box = layout.box()
            box.label(text="2DFX", **inu_icon(safe_icon('LIGHT')))
            box.prop(inu, "effect_2dfx", text=T("Тип эффекта"))
            if inu.effect_2dfx == 'LIGHT':
                box.prop(inu, "color_2dfx", text=T("Цвет"))
                row = box.row(align=True)
                row.prop(inu, "preset_2dfx", text=T("Пресет"))
                row.operator("gtatools.apply_2dfx_preset", text="", **inu_icon(compat.ICON_CHECK))



class GTATOOLS_PT_inu_tools_panel(bpy.types.Panel):
    """Панель INU Tools в Properties > Scene"""
    bl_label = "INU Tools"
    bl_idname = "GTATOOLS_PT_inu_tools_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'

    def draw(self, context):
        from ..ops.map_ops import _bbox_mode_active
        layout = self.layout
        scene = context.scene

        # Секции вплотную друг к другу — один align-столбец (зазор 1px).
        sec_col = layout.column(align=True)
        # «Import Map» переехал в N-панель: GTA Tools → IDE / IPL / IMG →
        # вкладка «Карта». Здесь секцию убрали, чтобы не дублировать.

        # Textures (collapsible)
        box = sec_col.box()
        row = box.row()
        row.prop(scene.inu_settings, "gtatools_show_texture_settings",
                 **inu_icon(safe_icon('TRIA_DOWN') if scene.inu_settings.gtatools_show_texture_settings else 'TRIA_RIGHT'),
                 text=T("Текстуры"), emboss=False)
        if scene.inu_settings.gtatools_show_texture_settings:
            box.label(text=T("Системные текстуры:"), **inu_icon(safe_icon('TEXTURE')))
            box.prop(scene.inu_settings, "gtatools_texture_path1", text="")
            row = box.row()
            row.label(text=T("Папка .blend:"), **inu_icon(safe_icon('FILE_FOLDER')))
            row.operator("gtatools.set_blend_folder", text="", **inu_icon(safe_icon('FILE_REFRESH')))
            box.prop(scene.inu_settings, "gtatools_texture_path2", text="")
            box.operator("gtatools.load_textures", text=T("Загрузить текстуры"), **inu_icon(safe_icon('IMPORT')))
            _alpha_on = getattr(scene.inu_settings, 'gtatools_scene_alpha_on', True)
            box.operator("gtatools.toggle_scene_alpha",
                         text=(T("Альфа сцены: ВКЛ") if _alpha_on else T("Альфа сцены: ВЫКЛ")),
                         depress=_alpha_on,
                         **inu_icon(safe_icon('IMAGE_RGB_ALPHA')))

        # IMG file list (collapsible)
        box = sec_col.box()
        row = box.row()
        row.prop(scene.inu_settings, "gtatools_show_img_list",
                 **inu_icon(safe_icon('TRIA_DOWN') if scene.inu_settings.gtatools_show_img_list else 'TRIA_RIGHT'),
                 text=T("Файлы IMG"), emboss=False)
        if scene.inu_settings.gtatools_show_img_list:
            if len(scene.inu_settings.gtatools_img_entries) > 0:
                box.template_list("GTATOOLS_UL_img_files", "",
                                  scene.inu_settings, "gtatools_img_entries",
                                  scene.inu_settings, "gtatools_img_entries_index", rows=8)
                entries = scene.inu_settings.gtatools_img_entries
                dff_c = sum(1 for e in entries if e.name.lower().endswith('.dff'))
                col_c = sum(1 for e in entries if e.name.lower().endswith('.col'))
                txd_c = sum(1 for e in entries if e.name.lower().endswith('.txd'))
                box.label(text=f"DFF: {dff_c}  COL: {col_c}  TXD: {txd_c}  Total: {len(entries)}", **inu_icon(safe_icon('INFO')))
            box.operator("gtatools.refresh_img_list", text=T("Обновить список"), **inu_icon(safe_icon('FILE_REFRESH')))

        # Preset folder (collapsible) — where all INU Tools presets/data live
        box = sec_col.box()
        row = box.row()
        row.prop(scene.inu_settings, "gtatools_show_preset_dir",
                 **inu_icon(safe_icon('TRIA_DOWN') if scene.inu_settings.gtatools_show_preset_dir else 'TRIA_RIGHT'),
                 text=T("Папка пресетов"), emboss=False)
        if scene.inu_settings.gtatools_show_preset_dir:
            from ..tools import user_data
            cur = user_data.get_user_data_dir()
            is_custom = user_data.get_preset_root_override() is not None
            box.label(
                text=(T("Своя папка") if is_custom else T("По умолчанию")),
                **inu_icon(safe_icon('FILE_FOLDER')))
            sub = box.box()
            sub.scale_y = 0.85
            for chunk in (cur[i:i + 48] for i in range(0, len(cur), 48)):
                sub.label(text=chunk)
            r = box.row(align=True)
            r.operator("gtatools.set_preset_dir", text=T("Изменить"),
                       **inu_icon(safe_icon('FILE_FOLDER')))
            r.operator("gtatools.open_preset_dir", text="",
                       **inu_icon(safe_icon('FILEBROWSER')))
            if is_custom:
                box.operator("gtatools.reset_preset_dir",
                             text=T("Сбросить на стандартную"),
                             **inu_icon(safe_icon('LOOP_BACK')))



@apply_order
class GTATOOLS_PT_id_manager_panel(bpy.types.Panel):
    """Менеджер ID моделей GTA SA"""
    bl_label = "ID Manager"
    bl_idname = "GTATOOLS_PT_id_manager_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('COPY_ID')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'id_manager')

    def draw(self, context):
        from .. import _draw_id_manager
        layout = self.layout
        scene = context.scene
        _draw_id_manager(layout, scene, context)



@apply_order
class GTATOOLS_PT_light_master(bpy.types.Panel):
    """Lighting — общий контейнер для всех инструментов по работе со светом
    и vertex colors. Объединяет 5 подпанелей (Prelight, Prelight COL,
    Vertex Paint, LightMap, Itera Tools 3) под одним заголовком, чтобы не
    раздувать N-sidebar пятью отдельными top-level панелями. Все дети
    свёрнуты по умолчанию — юзер раскрывает только нужный."""
    bl_label = "Lighting"
    bl_idname = "GTATOOLS_PT_light_master"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('LIGHT')))

    def draw_header_preset(self, context):
        # Иконка-планета ПЕРВОЙ (левее всех) → сайт Itera Tools 3.
        _u = self.layout.operator("gtatools.open_url", text="",
                                  **inu_icon(safe_icon('WORLD')), emboss=False)
        _u.url = "https://itera.gumroad.com/l/IteraTools3"
        _u.tip = T("Открыть сайт Itera Tools 3 — материалы освещения (companion)")
        # Кнопка плавающего окна 'light' убрана из UI (код флоатера на месте).
        _draw_doc_help(self.layout, 'lighting')

    def draw(self, context):
        # Пусто: тело + кнопки-табы рисуют под-панели (HIDE_HEADER), впритык.
        pass


def _draw_light_tabs(layout, s):
    """Кнопки-переключатели PreLight / PreLight COL / Itera (в верху панели)."""
    r = layout.row(align=True)
    r.scale_y = 1.2
    r.prop(s, "gtatools_light_mode", expand=True)



class GTATOOLS_PT_prelight_panel(bpy.types.Panel):
    """Панель Prelight"""
    bl_label = "Prelight"
    bl_idname = "GTATOOLS_PT_prelight_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_light_master"
    bl_order = 0
    bl_options = {'HIDE_HEADER'}       # заголовок заменён кнопкой-переключателем

    @classmethod
    def poll(cls, context):
        return context.scene.inu_settings.gtatools_light_mode == 'PRELIGHT'

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('COLOR')))

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        scene = context.scene

        # Пресеты охватывают всю панель Prelight и её подпанели.
        # «Применить» (load) — primary action, в конце ряда с текстом.
        # Поскольку у load text=«Применить», scale_x на load_cell реально
        # тянет ВИДИМУЮ ширину кнопки (текст ужимается/растягивается),
        # в отличие от icon-only кнопок где cell разбухает пустым местом.
        # ВАЖНО: оператор `prelight_preset_LOAD` импортирует значения из
        # выбранного пресета в сцену. `prelight_preset_APPLY` несмотря
        # на имя — overwrite выбранного пресета текущими настройками,
        # для него мелкая ✓ слева.
        # Preset row + «Свет (8 ламп)» = fused vertical cluster. Both
        # live inside one `column(align=True)` so they render как одна
        # «пачка» без 1px-gap между ними (Blender auto-gap у соседних
        # независимых rows). Same fused-block treatment that Blender's
        # own checkbox/Enum-row pairs use.
        preset_col = layout.column(align=True)
        _draw_light_tabs(preset_col, scene.inu_settings)   # табы впритык сверху

        preset_row = preset_col.row(align=True)
        # Жёсткий split 1/3 : 2/3 — «Применить» ровно под столбиком PreLight
        # (табы сверху = 3 равные части через expand). Так кнопка НЕ растёт и
        # НЕ ужимает текст на узкой панели, а дропдаун с иконками живёт справа.
        # Три трети под табами: «Применить» (PreLight) | дропдаун пресета
        # (PreLight COL) | иконки ✎ + − ↑ (Itera).
        # Верхний split 2/3 : 1/3 — иконки уходят на ПОСЛЕДНЮЮ треть (под
        # столбик Itera) и тянутся на неё целиком. Левые 2/3 делим пополам:
        # «Применить» (PreLight) | дропдаун пресета (PreLight COL).
        _lr = preset_row.split(factor=2.0 / 3.0, align=True)
        _left = _lr.split(factor=0.5, align=True)
        _left.operator("gtatools.prelight_preset_load",
                       text=T("Применить"),
                       **inu_icon(compat.ICON_CHECK))
        _left.prop(scene.inu_settings, "gtatools_prelight_preset", text="")
        # icon-only кнопки в общем row НЕ растягиваются (остаются узкими).
        # Даём каждой свою равную ячейку через цепочку split → 4 кнопки
        # заполняют всю треть под Itera.
        _icons = _lr.row(align=True)
        _s = _icons.split(factor=0.25, align=True)
        _s.operator("gtatools.prelight_preset_rename", text="", **inu_icon(safe_icon('GREASEPENCIL')))
        _s = _s.split(factor=1.0 / 3.0, align=True)
        _s.operator("gtatools.prelight_preset_save", text="", **inu_icon(safe_icon('ADD')))
        _s = _s.split(factor=0.5, align=True)
        _s.operator("gtatools.prelight_preset_delete", text="", **inu_icon(safe_icon('REMOVE')))
        # Overwrite (export-up arrow): сохранить текущие настройки в пресет.
        _s.operator("gtatools.prelight_preset_apply", text="", **inu_icon(safe_icon('EXPORT')))

        # Lights toggle under presets — создаёт/удаляет 8 ламп вокруг
        # активного объекта одним кликом. depress показывает, есть ли
        # уже лампы в сцене (collection «Prelight_Lights»).
        _coll = bpy.data.collections.get("Prelight_Lights")
        _lights_on = bool(_coll and len(_coll.objects) > 0)
        preset_col.operator("gtatools.toggle_prelight_lights",
                            text=T("Свет (8 ламп)"),
                            **inu_icon(safe_icon('LIGHT')),
                            depress=_lights_on)
        # Солнце — направленный источник, включается независимо от 8 ламп.
        _sun_on = bpy.data.objects.get("Prelight_Sun") is not None
        preset_col.operator("gtatools.toggle_prelight_sun",
                            text=T("Солнце"),
                            **inu_icon(safe_icon('LIGHT_SUN')),
                            depress=_sun_on)

        # Блок ниже виден ВСЕГДА; без выделенного меша — затемнён (disabled),
        # раскладка сохраняется и активируется по выделению модели.
        _has_mesh = bool(obj and obj.type == 'MESH')
        mesh = obj.data if _has_mesh else None
        active_attr = compat.vcol_active(mesh) if mesh else None
        obj_col = preset_col.column(align=True)
        obj_col.enabled = _has_mesh
        if True:      # noqa: тело рисуется всегда (было `if obj ... MESH`)

            # Preview state computed up-front — кнопка теперь внутри box'а
            # слева от Day/Night рядов как высокий вертикальный rect.
            # Preview state — check the `prelight_preview_active`
            # material flag, not `Prelight_Mix` node existence. The
            # node now persists even while preview is OFF (we keep
            # it to avoid recreate-lag on toggle), so node existence
            # is no longer a reliable on/off signal.
            _preview_on = False
            for _ms in (obj.material_slots if _has_mesh else []):
                _m = _ms.material
                if _m and _m.get('prelight_preview_active', False):
                    _preview_on = True
                    break
            _pv_icon = safe_icon('HIDE_OFF') if _preview_on else 'HIDE_ON'

            # Day/Night rows inside a box, but the box itself sits in
            # the fused preset_col cluster — so it has its own subtle
            # frame yet still butts up against the «Свет (8 ламп)»
            # button above and «Запечь» below with no extra 18-px gap.
            box = obj_col.box()
            body = box.row(align=True)
            preview_col = body.column(align=True)
            preview_col.ui_units_x = 1.4
            preview_col.scale_y = 2.0
            op_pv = preview_col.operator("gtatools.prelight_preview",
                                         text="", **inu_icon(_pv_icon),
                                         depress=_preview_on)
            op_pv.enable = not _preview_on
            box_col = body.column(align=True)

            # Day / Night rows: [select btn][V offset prop][— remove].
            # Кнопка-селектор слева, V-offset справа от неё, кнопка
            # удаления в самом конце. Значение V применяется
            # автоматически при изменении (callback на per-object
            # FloatProperty).
            for _attr_name, _v_prop in (("Day", "gtatools_v_offset_day"),
                                        ("Night", "gtatools_v_offset_night")):
                # 3-cell layout: [name 60%][V slot 40%][action btn 18 px].
                # The +/- action button sits OUTSIDE the inner split so
                # it holds a fixed 0.9-ui-unit (~18 px) width. The
                # split's children (name + V) absorb panel narrowing
                # first — when the user drags the sidebar narrower the
                # name and V cells shrink while the +/- button stays
                # at its natural icon-button width. Same column geometry
                # whether the vcol attribute exists or not, so the «+»
                # (create) lands in the same slot as «—» (remove).
                row = box_col.row(align=True)
                inner = row.split(factor=0.6, align=True)
                left = inner.row(align=True)
                v_cell = inner.row(align=True)
                btn_cell = row.row(align=True)
                btn_cell.ui_units_x = 0.9
                if mesh is not None and compat.vcol_get(mesh, _attr_name) is not None:
                    is_active = bool(active_attr and active_attr.name == _attr_name)
                    icon = safe_icon('RADIOBUT_ON') if is_active else 'RADIOBUT_OFF'
                    op = left.operator("gtatools.select_color_attribute",
                                       text=_attr_name, **inu_icon(icon), depress=is_active)
                    op.attribute_name = _attr_name
                    v_cell.prop(obj, _v_prop, text="V")
                    op = btn_cell.operator("gtatools.remove_color_attr", text="", **inu_icon(safe_icon('REMOVE')))
                    op.attr_name = _attr_name
                else:
                    # «Phantom» selector — same operator-button shape as
                    # the «attribute exists» branch (so split-factor 0.6
                    # measures the same width in both states), but the
                    # whole left cell is `enabled=False`. Reads as «no
                    # attribute yet» — greyed out like the V phantom on
                    # the right. Action moves to the [+] button which
                    # stays enabled and creates the attribute.
                    left.enabled = False
                    op = left.operator("gtatools.create_color_attr",
                                       text=_attr_name,
                                       **inu_icon(safe_icon('RADIOBUT_OFF')))
                    op.attr_name = _attr_name
                    # Disabled-prop как «фантом» V — занимает ту же ширину,
                    # что и активный prop в [—]-state. Иначе label("") был
                    # 0-ширины, split-proportions уезжали, и btn ([+])
                    # становился визуально уже чем [—] после создания attr.
                    v_sub = v_cell.row(align=True)
                    v_sub.enabled = False
                    if obj is not None:
                        v_sub.prop(obj, _v_prop, text="V")
                    else:
                        v_sub.label(text="V")     # без объекта — фантом-заглушка
                    op = btn_cell.operator("gtatools.create_color_attr", text="", **inu_icon(safe_icon('ADD')))
                    op.attr_name = _attr_name

            # Scene-wide vertex-alpha preview — independent of the RGB
            # Prelight preview (eye on the left). One toggle scans the
            # whole scene, finds every model that actually has vertex
            # alpha (Day/Night layer < 255) and shows its transparency;
            # solid geometry (alpha 255) is skipped so the map can't go
            # black. State is the scene flag set by gtatools.alpha_preview.
            _alpha_on = bool(context.scene.get('inu_alpha_preview_on', False))
            _alpha_icon = safe_icon('HIDE_OFF') if _alpha_on else 'HIDE_ON'
            arow = box_col.row(align=True)
            op_a = arow.operator("gtatools.alpha_preview",
                                 text=T("Альфа вершины (сцена)"),
                                 **inu_icon(_alpha_icon),
                                 depress=_alpha_on)
            # operator() returns None if the op isn't registered yet
            # (e.g. mid-reload) — guard so a stale draw never crashes
            # the whole N-panel.
            if op_a is not None:
                op_a.enable = not _alpha_on
            # Справа — под столбцом «—» строк Day/Night: перенос альфы
            # вершин с активного атрибута (Day/Night) на второй (RGB
            # приёмника сохраняется; направление задаёт радиокнопка
            # выбора активного атрибута выше). ui_units_x резервирует
            # ширину — иначе растянутая текстовая кнопка выше съедает
            # место и иконка схлопывается в 0 (её не видно и не нажать).
            a_btns = arow.row(align=True)
            a_btns.ui_units_x = 0.9
            a_btns.operator("gtatools.copy_vertex_alpha", text="",
                            **inu_icon(safe_icon('COPYDOWN')))

            # Визуальная коррекция превью (яркость/контраст/гамма/насыщенность)
            # СПРЯТАНА из UI по просьбе. Значения живут в свойствах сцены и
            # применяются авто per-game (см. prelight._current_view_correction).

            # Other attributes are NOT shown here — they live in the
            # «Слои Vertex Color» collapsible section below LightMap.
            #
            # REMOVED: combined Preview / Day-Night-create / Add / Remove row.
            # • Preview-глаз перенесён внутрь box'а как высокая левая ячейка.
            # • «Day/Night» (создавал сразу оба) и bulk +/- убраны —
            #   каждая строка уже имеет свой персональный + / — для своего
            #   attr-name, чтобы юзеру было понятнее что именно создаётся.

            # Bake + Copy + LightMap всё ещё в preset_col — продолжаем
            # тот же fused кластер, что начался с preset row и Дня/Ночи.
            # Юзер хочет «1px между всеми кнопками без скругления по
            # краям» — это и есть `column(align=True)`.

            # «Запечь поверх» — additive bake: кладёт свет сцены ПОВЕРХ
            # текущего прилайта (Add), не перезаписывая. Над обычным рядом.
            row_o = obj_col.row(align=True)
            _op_o = row_o.operator("gtatools.bake_vertex_colors_simple",
                                   text=T("Запечь поверх"),
                                   **inu_icon(safe_icon('ADD')))
            _op_o.over = True
            _op_os = row_o.operator("gtatools.bake_vertex_colors",
                                    text=T("Запечь поверх с тенями"),
                                    **inu_icon(safe_icon('ADD')))
            _op_os.over = True
            _op_os.use_shadows = True

            # Bake row сразу под Day/Night атрибутами — это primary action
            # после настройки V-offset'ов, держим близко к атрибутам чтобы
            # workflow читался сверху-вниз: pick attr → tune V → bake.
            row = obj_col.row(align=True)
            row.scale_y = 1.6   # основные кнопки запекания — выше (были узкими)
            # over=False ставим ЯВНО: свойства оператора в Blender «липкие» —
            # без этого over=True от соседней «Запечь поверх» утекает сюда и
            # обычное «Запечь» начинает складывать вместо перезаписи.
            op_b = row.operator("gtatools.bake_vertex_colors_simple", text=T("Запечь"), **inu_icon(safe_icon('RENDER_STILL')))
            op_b.over = False
            op_bs = row.operator("gtatools.bake_vertex_colors", text=T("Запечь с тенями"), **inu_icon(safe_icon('RENDER_RESULT')))
            op_bs.use_shadows = True
            op_bs.over = False

            # Источники запекания: тумблеры Point/Sun/Spot/Area + HDRI(World)
            # одной строкой, впритык к кнопкам «Запечь» сверху. Кнопки
            # «Запечь» / «Запечь с тенями» учитывают только включённые
            # источники; HDRI сэмплит цвет мира по нормали и складывается с лампами.
            src_row = obj_col.row(align=True)
            src_row.prop(scene.inu_settings, "gtatools_prelight_use_point", toggle=True)
            src_row.prop(scene.inu_settings, "gtatools_prelight_use_sun", toggle=True)
            src_row.prop(scene.inu_settings, "gtatools_prelight_use_spot", toggle=True)
            src_row.prop(scene.inu_settings, "gtatools_prelight_use_area", toggle=True)
            src_row.prop(scene.inu_settings, "gtatools_prelight_use_hdri",
                         toggle=True, **inu_icon(safe_icon('WORLD')))

            # Copy Day ↔ Night — text-only buttons. Earlier the
            # FORWARD/BACK icons looked like media-player play/back
            # buttons and competed visually with the `→` glyph in the
            # label. Removing the icons leaves one unambiguous arrow
            # per button, which is what the user reads anyway.
            row = obj_col.row(align=True)
            op = row.operator("gtatools.copy_color_attr", text="Day → Night")
            op.source = "Day"
            op.target = "Night"
            op = row.operator("gtatools.copy_color_attr", text="Night → Day")
            op.source = "Night"
            op.target = "Day"

            # LightMap UV2 row
            row = obj_col.row(align=True)
            _lm_on = False
            _lm_exists = False
            for _ms in (obj.material_slots if _has_mesh else []):
                _m = _ms.material
                if compat.material_uses_nodes(_m):
                    _lm_mix = _m.node_tree.nodes.get("LM_Mix")
                    if _lm_mix:
                        _lm_exists = True
                        if not _lm_mix.mute:
                            _lm_on = True
                        break
            _lm_icon=safe_icon('HIDE_OFF') if _lm_on else 'HIDE_ON'
            if _lm_exists:
                op_lm = row.operator("gtatools.toggle_lightmap_uv2", text="", **inu_icon(_lm_icon), depress=_lm_on)
                op_lm.enable = not _lm_on
            else:
                row.label(text="", **inu_icon(safe_icon('HIDE_ON')))
            row.operator("gtatools.apply_lightmap_uv2", text=T("Добавить LightMap"))
            row.operator("gtatools.remove_lightmap_uv2", text="", **inu_icon(safe_icon('REMOVE')))

            # ─── Коррекция превью прилайта ─────────────────────────────
            # Только вьюпорт: ноды коррекции — постоянная часть графа
            # превью, нейтраль (0, 0, 1, 1) = pass-through. На экспорт не
            # влияет вообще — dff_export читает реальные vertex colors
            # мимо этих нод.
            view_box = obj_col.box().column(align=True)
            header = view_box.row(align=True)
            header.prop(
                scene.inu_settings, "gtatools_show_prelight_view",
                text=T("Коррекция превью"),
                icon='TRIA_DOWN' if scene.inu_settings.gtatools_show_prelight_view else 'TRIA_RIGHT',
                emboss=False)
            if scene.inu_settings.gtatools_show_prelight_view:
                view_col = view_box.column(align=True)
                view_col.prop(scene.inu_settings, "prelight_view_bright", text=T("Яркость"), slider=True)
                view_col.prop(scene.inu_settings, "prelight_view_contrast", text=T("Контраст"), slider=True)
                view_col.prop(scene.inu_settings, "prelight_view_gamma", text=T("Гамма"), slider=True)
                view_col.prop(scene.inu_settings, "prelight_view_saturation", text=T("Насыщенность"), slider=True)
                view_box.operator("gtatools.prelight_view_reset",
                                  text=T("Нейтрально"),
                                  **inu_icon(safe_icon('LOOP_BACK')))
                view_box.label(text=T("Только вьюпорт, на экспорт не влияет"),
                               **inu_icon(safe_icon('INFO')))

            # ─── Слои Vertex Color (collapsible, inline) ──────────────
            # Sits below LightMap so the user sees it in the natural
            # flow of vertex-color editing — pick base → tweak with
            # layers. Bake row уже выведен выше (рядом с Day/Night).
            # Collapsed by default until the user adds their first VCL.
            if mesh is not None:
                from ..tools.vc_layers import draw_vc_layers_section
                draw_vc_layers_section(obj_col, context, mesh)

        # Bake row перенесён внутрь `if obj and obj.type == 'MESH'`
        # сразу под Day/Night атрибутами — без активного меша запекать
        # всё равно нечего, операторы сами выдают error в том случае.

        # V-offset переехал инлайн в Day/Night-строки выше — каждый
        # атрибут хранит свой V и применяется автоматически.

        # Modulate Color убран: превью прилайта теперь минимальный граф
        # (VertexColor × текстура), без ambient/post-fx нод — переключение
        # моделей не тормозит компиляцией шейдеров.




class GTATOOLS_PT_bake_settings_subpanel(bpy.types.Panel):
    """Расширенные настройки запекания"""
    bl_label = "Advanced Settings"
    bl_idname = "GTATOOLS_PT_bake_settings_subpanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_prelight_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Fused vertical cluster — three sliders + Reset button as one
        # block, без 18px gap'ов между ними.
        col = layout.column(align=True)
        col.prop(scene.inu_settings, "gtatools_bake_ambient", text=T("Окружающий"), slider=True)
        col.prop(scene.inu_settings, "gtatools_bake_intensity", text=T("Интенсивность"), slider=True)
        col.prop(scene.inu_settings, "gtatools_bake_gamma", text=T("Гамма"), slider=True)
        col.operator("gtatools.reset_bake_settings", **inu_icon(safe_icon('LOOP_BACK')))

        # Presets перенесены в шапку Prelight (рядом с «Цветовые атрибуты:»)
        # — теперь они охватывают всю панель и её подпанели.



class GTATOOLS_PT_scatter_color_subpanel(bpy.types.Panel):
    """Sub-panel: инструменты для работы со светом / vertex colors."""
    bl_label = "Инструменты"
    bl_idname = "GTATOOLS_PT_scatter_color_subpanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_prelight_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = context.scene.inu_settings

        # Each tool sits in its OWN box, so it's obvious where one tool ends
        # and the next begins. `column(align=True)` fuses the controls
        # inside each box so it stays compact.
        def _tool(title, icon_name):
            col = layout.box().column(align=True)
            col.label(text=title, **inu_icon(safe_icon(icon_name)))
            return col

        # ── Залить одним цветом ──
        c = _tool(T("Залить одним цветом:"), 'COLOR')
        row = c.row(align=True)
        row.prop(s, "gtatools_fill_prelight_day", text=T("День"))
        row.prop(s, "gtatools_fill_prelight_night", text=T("Ночь"))
        c.prop(s, "gtatools_fill_prelight_selected_only",
               text=T("Только выделенные"))
        c.operator("gtatools.fill_prelight", text=T("Применить"),
                   **inu_icon(safe_icon('CHECKMARK')))

        # ── Рисовать по нескольким ──
        c = _tool(T("Рисовать по нескольким:"), 'BRUSH_DATA')
        row = c.row(align=True)
        row.operator("gtatools.prelight_merge_paint", text=T("Объединить"),
                     **inu_icon(safe_icon('OBJECT_DATA')))
        row.operator("gtatools.prelight_split_paint", text=T("Разъединить"),
                     **inu_icon(safe_icon('MOD_EXPLODE')))

        # ── Рассеять цвет ──
        c = _tool(T("Рассеять цвет:"), 'BRUSH_DATA')
        c.operator("gtatools.scatter_color", text=T("Применить"),
                   **inu_icon(safe_icon('CHECKMARK')))
        c.prop(s, "gtatools_scatter_color_strength", text=T("Сила"), slider=True)
        c.prop(s, "gtatools_scatter_color_distance", text=T("Дальность"),
               slider=True)
        # Цвет: из активной Vertex Paint brush, иначе scene prop.
        try:
            ts = context.tool_settings
            vp = getattr(ts, 'vertex_paint', None)
            brush = getattr(vp, 'brush', None) if vp else None
            if brush is not None and hasattr(brush, 'color'):
                c.prop(brush, "color", text=T("Цвет (из кисти)"))
            else:
                c.prop(s, "gtatools_scatter_color_color", text=T("Цвет"))
        except Exception:
            c.prop(s, "gtatools_scatter_color_color", text=T("Цвет"))

        # ── Между объектами ──
        c = _tool(T("Между объектами:"), 'MOD_SMOOTH')
        c.operator("gtatools.vc_smooth_between",
                   text=T("Сгладить между объектами"),
                   **inu_icon(safe_icon('MOD_SMOOTH')))

        # ── Свет → топология (резак света v2) ──
        c = _tool(T("Свет → топология:"), 'LIGHT')
        c.prop(s, "gtatools_lightcut_type", expand=True)
        c.prop(s, "gtatools_lightcut_radius", text=T("Радиус"))
        c.prop(s, "gtatools_lightcut_segments", text=T("Сегменты"))
        # Кольца (только для цилиндра) — список с радиусом каждого + удаление
        if s.gtatools_lightcut_type == 'CYLINDER':
            c.separator()
            c.label(text=T("Кольца (от центра к краю):"),
                    **inu_icon(safe_icon('MESH_CIRCLE')))
            for i, ring in enumerate(s.gtatools_lightcut_ringlist):
                row = c.row(align=True)
                row.prop(ring, "radius", text=f"{i + 1}", slider=True)
                op_rm = row.operator("gtatools.lightcut_ring_remove",
                                     text="", **inu_icon(safe_icon('X')))
                op_rm.index = i
            c.operator("gtatools.lightcut_ring_add", text=T("+ Кольцо"),
                       **inu_icon(safe_icon('ADD')))
        # Создать резак
        c.separator()
        c.operator("gtatools.lightcut_create", text=T("Создать резак"),
                   **inu_icon(safe_icon('MESH_CYLINDER')))
        # Куда: отдельный диск / в пол
        c.prop(s, "gtatools_lightcut_separate", text=T("Отдельным объектом"))
        if not s.gtatools_lightcut_separate:
            c.prop(s, "gtatools_lightcut_target", text=T("Геометрия (пол)"))
        cut = c.row()
        cut.scale_y = 1.4
        cut.operator("gtatools.light_topo_cut",
                     text=T("Нарезать по резаку"),
                     **inu_icon(safe_icon('MOD_MULTIRES')))



class GTATOOLS_PT_foliage_subpanel(bpy.types.Panel):
    """Прилайт листвы деревьев: радиальный градиент (темнее в центре
    кроны, светлее снаружи) + смена цвета листвы. Геометрический, без
    света сцены — для billboard-листвы."""
    bl_label = "Листва / Дерево"
    bl_idname = "GTATOOLS_PT_foliage_subpanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_prelight_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = context.scene.inu_settings
        obj = context.active_object

        if not (obj and obj.type == 'MESH'):
            layout.label(text=T("Выберите меш-дерево"),
                         **inu_icon(safe_icon('ERROR')))
            return
        has_mats = bool(obj.material_slots)

        # ── Общие настройки (применяются к обеим операциям) ──
        top = layout.box().column(align=True)
        top.prop(s, "gtatools_foliage_select_only", text=T("Только выделенные грани"))
        top.prop(s, "gtatools_foliage_both_sides", text=T("Обе стороны (дубли)"))
        top.prop(s, "gtatools_foliage_blend", expand=True)

        # ── Блок 1: Крона (затенение) — свой материал + своя кнопка ──
        cb = layout.box().column(align=True)
        cb.label(text=T("Крона (затенение):"), **inu_icon(safe_icon('LIGHT_SUN')))
        if has_mats:
            cb.prop_search(s, "gtatools_foliage_material_name",
                           obj, "material_slots", text=T("Материал"),
                           icon=safe_icon('MATERIAL'))
        cb.prop(s, "gtatools_foliage_metric", text=T("Форма"))
        row = cb.row(align=True)
        row.prop(s, "gtatools_foliage_inside", text=T("Внутри"), slider=True)
        row.prop(s, "gtatools_foliage_outside", text=T("Снаружи"), slider=True)
        cb.prop(s, "gtatools_foliage_gamma", text=T("Кривая"), slider=True)
        cb.prop(s, "gtatools_foliage_height_dark",
                text=T("Затемнить низ"), slider=True)
        op_s = cb.operator("gtatools.prelight_foliage",
                           text=T("Прилайтить крону"),
                           **inu_icon(safe_icon('BRUSH_DATA')))
        op_s.mode = 'SHADE'

        # ── Блок 2: Цвет листвы — свой материал + своя кнопка ──
        cc = layout.box().column(align=True)
        cc.label(text=T("Цвет листвы (свет / тень):"),
                 **inu_icon(safe_icon('COLOR')))
        if has_mats:
            cc.prop_search(s, "gtatools_foliage_color_material_name",
                           obj, "material_slots", text=T("Материал"),
                           icon=safe_icon('MATERIAL'))
        crow = cc.row(align=True)
        crow.prop(s, "gtatools_foliage_light_tint", text="")
        crow.prop(s, "gtatools_foliage_shadow_tint", text="")
        cc.prop(s, "gtatools_foliage_tint_strength",
                text=T("Сила цвета"), slider=True)
        cc.prop(s, "gtatools_foliage_top_bright",
                text=T("Подсветить верх"), slider=True)
        sub = cc.row(align=True)
        sub.enabled = s.gtatools_foliage_top_bright > 0.0
        sub.prop(s, "gtatools_foliage_top_height",
                 text=T("Высота подсветки"), slider=True)
        cc.prop(s, "gtatools_foliage_color_height_dark",
                text=T("Затемнить низ"), slider=True)
        cc.prop(s, "gtatools_foliage_variation", text=T("Разброс"), slider=True)
        brow = cc.row(align=True)
        op_c = brow.operator("gtatools.prelight_foliage",
                             text=T("Запечь цвет"),
                             **inu_icon(safe_icon('BRUSH_DATA')))
        op_c.mode = 'COLOR'
        brow.operator("gtatools.foliage_color_reset",
                      text=T("Сброс"),
                      **inu_icon(safe_icon('LOOP_BACK')))


class GTATOOLS_PT_vc_postprocess_panel(bpy.types.Panel):
    """Панель пост-обработки vertex colors"""
    bl_label = "Post-Processing"
    bl_idname = "GTATOOLS_PT_vc_postprocess_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_prelight_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # ОДИН внешний box со всеми операциями внутри. Каждая секция —
        # label-заголовок + параметры + Apply, всё в общем
        # `column(align=True)`. Только внешний box имеет скруглённую
        # рамку (одно скругление на всю Post-Processing панель), а
        # между секциями нет своих границ — только текст-заголовки
        # разделяют их визуально. Раньше каждая секция была в своём
        # `layout.box()`, и юзер видел 5 скруглённых углов подряд
        # вместо одной чистой группы.
        #
        # «Между объектами» убрана отсюда — операция переехала в
        # «Инструменты» (это не post-process текущего объекта, а
        # межобъектная операция).
        big_col = layout.box().column(align=True)

        # Smooth — единственная секция с заголовком (2 параметра в одном
        # row + отдельная кнопка «Сгладить» не помещаются на одной строке).
        big_col.label(text=T("Сглаживание:"), **inu_icon(safe_icon('MOD_SMOOTH')))
        row = big_col.row(align=True)
        row.prop(scene.inu_settings, "gtatools_vc_smooth_iterations", text=T("Проходы"))
        row.prop(scene.inu_settings, "gtatools_vc_smooth_factor", text=T("Сила"))
        big_col.operator("gtatools.vc_smooth", text=T("Сгладить"), **inu_icon(safe_icon('SMOOTHCURVE')))

        # Contrast / Brightness / Gamma — без заголовков. Label поля
        # (text="Контраст" и т.п.) сам по себе описывает что регулируется,
        # дублировать ещё одной строкой выше — лишний шум.
        row = big_col.row(align=True)
        row.prop(scene.inu_settings, "gtatools_vc_contrast", text=T("Контраст"))
        row.operator("gtatools.vc_contrast", text=T("Применить"), **inu_icon(compat.ICON_CHECK))

        row = big_col.row(align=True)
        row.prop(scene.inu_settings, "gtatools_vc_brightness", text=T("Яркость"))
        row.operator("gtatools.vc_brightness", text=T("Применить"), **inu_icon(compat.ICON_CHECK))

        row = big_col.row(align=True)
        row.prop(scene.inu_settings, "gtatools_vc_gamma", text=T("Гамма"))
        row.operator("gtatools.vc_gamma", text=T("Применить"), **inu_icon(compat.ICON_CHECK))

        # Lift Shadows — без отдельного заголовка, label слайдера
        # «Подтянуть тени» сам себя описывает.
        row = big_col.row(align=True)
        row.prop(scene.inu_settings, "gtatools_lift_shadows_strength", text=T("Подтянуть тени"), slider=True)
        row.operator("gtatools.lift_shadows", text=T("Применить"), **inu_icon(compat.ICON_CHECK))



_ITERA_COLLECTION_PREFIX = "Template Scene - Vertex Lights"


def _itera_collection_state(scene):
    """None when Itera isn't in the file, else True if it needs fixing.

    «Needs fixing» = at least one Itera collection is linked from a
    library or isn't a direct child of the scene collection. Called
    through ``draw_cache.memo``.
    """
    cols = [c for c in bpy.data.collections
            if c.name.startswith(_ITERA_COLLECTION_PREFIX)]
    if not cols:
        return None
    return any(c.library or c.name not in scene.collection.children
               for c in cols)


class GTATOOLS_PT_itera_panel(bpy.types.Panel):
    """Интеграция с Itera Tools 3 — материалы освещения"""
    bl_label = "Itera Tools 3"
    bl_idname = "GTATOOLS_PT_itera_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_light_master"
    bl_order = 4
    bl_options = {'HIDE_HEADER'}       # заголовок заменён кнопкой-переключателем

    @classmethod
    def poll(cls, context):
        return context.scene.inu_settings.gtatools_light_mode == 'ITERA'

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('LIGHT_SUN')))

    def draw(self, context):
        from ..ops.light_ops import _find_itera_blend_path
        layout = self.layout
        _draw_light_tabs(layout, context.scene.inu_settings)   # табы сверху

        itera_path = _find_itera_blend_path()
        if not itera_path:
            layout.label(text=T("Itera не найден в библиотеках ассетов"), **inu_icon(safe_icon('ERROR')))
            return

        # Apply presets + Remove + Fix collection — единый fused column.
        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("gtatools.apply_itera_material", text="Vertex Lit Linear", **inu_icon(safe_icon('MATERIAL')))
        row.operator("gtatools.apply_itera_quickstart", text="Quickstart", **inu_icon(safe_icon('NODE_MATERIAL')))
        col.operator("gtatools.remove_itera_material", text=T("Убрать Itera"), **inu_icon(safe_icon('LOOP_BACK')))

        # Fix Itera Collection. Memoised — the check walks every collection
        # and its linked-children list on each redraw otherwise.
        itera_state = draw_cache.memo(
            ('itera_cols', len(bpy.data.collections),
             len(context.scene.collection.children)),
            lambda: _itera_collection_state(context.scene))
        if itera_state is not None:
            if itera_state:   # needs fixing
                col.operator("gtatools.fix_itera_collection", text=T("Исправить коллекцию Itera"), **inu_icon(safe_icon('LIGHT')))
            else:
                disabled = col.row(align=True)
                disabled.enabled = False
                disabled.operator("gtatools.fix_itera_collection", text=T("Коллекция Itera исправлена"), **inu_icon(compat.ICON_CHECK))



class GTATOOLS_PT_prelight_col_panel(bpy.types.Panel):
    """Конвертировать vertex colors в COL Day/Night Light"""
    bl_label = "PreLight COL"
    bl_idname = "GTATOOLS_PT_prelight_col_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_light_master"
    bl_order = 1
    bl_options = {'HIDE_HEADER'}       # заголовок заменён кнопкой-переключателем

    @classmethod
    def poll(cls, context):
        return context.scene.inu_settings.gtatools_light_mode == 'COL'

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('COLOR')))

    def draw(self, context):
        from .. import _col_light_mod
        from .. import _draw_label_with_info
        layout = self.layout
        obj = context.active_object
        scene = context.scene
        _draw_light_tabs(layout, scene.inu_settings)      # табы сверху

        # Show source layers
        if obj and obj.type == 'MESH' and compat.vcol_list(obj.data):
            mesh = obj.data
            _act = compat.vcol_active(mesh)
            day_src = "Day" if compat.vcol_get(mesh, "Day") else (_act.name if _act else "—")
            night_src = "Night" if compat.vcol_get(mesh, "Night") else day_src
            layout.label(text=f"Day: {day_src} | Night: {night_src}", **inu_icon(safe_icon('COLOR')))
        else:
            layout.label(text=T("Нет vertex colors"), **inu_icon(safe_icon('INFO')))

        layout.separator()

        # Day range
        box = layout.box()
        _draw_label_with_info(box, T("Дневной свет:"),
            T("Диапазон дневного освещения для COL материалов\nMin/Max — значения от 0 до 15\nЯркость vertex colors конвертируется в этот диапазон"),
            **inu_icon(safe_icon('LIGHT_SUN')))
        row = box.row(align=True)
        row.prop(scene.inu_settings, "gtatools_col_day_min", text=T("Мин."))
        row.prop(scene.inu_settings, "gtatools_col_day_max", text=T("Макс."))

        # Night range
        box = layout.box()
        _draw_label_with_info(box, T("Ночной свет:"),
            T("Диапазон ночного освещения для COL материалов\nMin/Max — значения от 0 до 15\nИспользует Night color attribute если есть"),
            **inu_icon(safe_icon('SHADING_RENDERED')))
        row = box.row(align=True)
        row.prop(scene.inu_settings, "gtatools_col_night_min", text=T("Мин."))
        row.prop(scene.inu_settings, "gtatools_col_night_max", text=T("Макс."))

        layout.separator()

        # Preview + sliders + Bake — единый fused кластер. Раньше каждый
        # row/box отрисовывался отдельно с 18-px gap'ами; теперь они
        # сидят в одном column(align=True).
        actions_col = layout.column(align=True)

        # Preview button
        preview_icon=safe_icon('HIDE_OFF') if _col_light_mod._col_light_preview_active else 'HIDE_ON'
        preview_text = T("Скрыть превью") if _col_light_mod._col_light_preview_active else T("Превью COL Light")
        actions_col.operator("gtatools.preview_col_light", text=preview_text,
                             **inu_icon(preview_icon), depress=_col_light_mod._col_light_preview_active)

        if _col_light_mod._col_light_preview_active:
            actions_col.prop(scene.inu_settings, "gtatools_col_light_edge", text=T("Край"), slider=True)
            actions_col.prop(scene.inu_settings, "gtatools_col_light_threshold", text=T("Порог"), slider=True)
            actions_col.prop(scene.inu_settings, "gtatools_col_light_contrast", text=T("Контраст"), slider=True)
            row = actions_col.row(align=True)
            row.prop(scene.inu_settings, "gtatools_col_light_show_numbers", text=T("Цифры"), toggle=True)
            row.prop(scene.inu_settings, "gtatools_col_light_font_size", text=T("Размер"))

        row = actions_col.row(align=True)
        row.operator("gtatools.bake_col_light", text=T("Запечь COL Light"), **inu_icon(safe_icon('RENDER_STILL')))
        row.operator("gtatools.clear_col_light_mats", text="", **inu_icon('X'))

        # Show info about created COL materials
        if obj and obj.type == 'MESH':
            import json
            stored = json.loads(obj.get("gtatools_col_light_mats", "[]"))
            if stored:
                layout.label(text=f"{T('COL light материалов:')} {len(stored)}", **inu_icon(compat.ICON_CHECK))



class GTATOOLS_PT_lightmap_panel(bpy.types.Panel):
    """Панель генератора Lightmap"""
    bl_label = "LightMap (beta_MTA)"
    bl_idname = "GTATOOLS_PT_lightmap_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_light_master"
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return False  # Hidden — code kept for future use

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Load Lightmap texture
        layout.label(text=T("Текстура Lightmap:"))
        row = layout.row(align=True)
        row.operator("gtatools.load_lightmap", text=T("Загрузить (LP_)"), **inu_icon(safe_icon('IMAGE_DATA')))
        row.operator("gtatools.remove_lightmap", text=T("Удалить"), **inu_icon('X'))

        layout.separator()

        # Generate code
        layout.label(text=T("Генерация кода:"))
        layout.operator("gtatools.lightmap_generate", text=T("Генерировать"), **inu_icon(safe_icon('FILE_TEXT')))
        layout.prop(scene.inu_settings, "gtatools_lightmap_path", text=T("Путь"))
        layout.prop(scene.inu_settings, "gtatools_model_id", text=T("ID модели"))

        layout.separator()
        layout.label(text=T("Результат:"))

        box = layout.box()
        if scene.inu_settings.gtatools_lightmap_result:
            lines = scene.inu_settings.gtatools_lightmap_result.split('\n')
            for line in lines:
                box.label(text=line)
            row = layout.row(align=True)
            row.operator("gtatools.lightmap_copy", text=T("Копировать"), **inu_icon(safe_icon('COPYDOWN')))
            row.operator("gtatools.lightmap_clear", text=T("Очистить"), **inu_icon('X'))
        else:
            box.label(text=T("Нажмите кнопку для генерации"))



class GTATOOLS_UL_grass(bpy.types.UIList):
    """Список записей plants.dat. Строка = поверхность · PCDid · плотность."""
    bl_idname = "GTATOOLS_UL_grass"

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            from ..data.surface_materials import resolve_surface_id
            sid = resolve_surface_id(item.name)
            label = f"{sid}: {item.name}" if sid is not None else (item.name or "?")
            row = layout.row(align=True)
            row.label(text=label, translate=False,
                      **inu_icon(safe_icon('SEQ_HISTOGRAM')))
            sub = row.row(align=True)
            sub.alignment = 'RIGHT'
            sub.label(text=f"#{item.pcd_id}  ·  {item.density:g}", translate=False)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", **inu_icon(safe_icon('SEQ_HISTOGRAM')))


@apply_order
class GTATOOLS_PT_grass_panel(bpy.types.Panel):
    """Панель травы — два способа: plants.dat (процедурная) и геометрия."""
    bl_label = "Трава"
    bl_idname = "GTATOOLS_PT_grass_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('OUTLINER_DATA_CURVES')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'grass')

    def draw(self, context):
        layout = self.layout
        s = context.scene.inu_settings

        # Both path fields together on top (процедурная трава plants.dat).
        paths = layout.column(align=True)
        paths.prop(s, "gtatools_grass_txd_path", text=".txd", **inu_icon(safe_icon('TEXTURE')))
        paths.prop(s, "gtatools_plants_dat_path", text=".dat")

        # Action block below: tall action button on the left, Import/Export
        # stacked on the right (right column = height of two buttons).
        blk = layout.row(align=True)
        left = blk.column(align=True)
        left.scale_y = 2.0
        right = blk.column(align=True)
        left.operator("gtatools.grass_preview", text=T("Показать траву"),
                      depress=s.gtatools_grass_live,
                      **inu_icon(safe_icon('OUTLINER_DATA_GREASEPENCIL')))
        right.operator("gtatools.grass_import", text=T("Импорт"), **inu_icon(safe_icon('IMPORT')))
        right.operator("gtatools.grass_export", text=T("Экспорт"), **inu_icon(safe_icon('EXPORT')))

        n_entries = len(s.gtatools_grass_entries)
        n_surf = len({e.name for e in s.gtatools_grass_entries})
        layout.label(
            text=f"{T('Записей:')} {n_entries}  ·  {T('поверхностей:')} {n_surf}",
            **inu_icon(safe_icon('INFO')))

        # The list + side controls (add / remove / duplicate).
        list_row = layout.row()
        list_row.template_list("GTATOOLS_UL_grass", "", s, "gtatools_grass_entries",
                               s, "gtatools_grass_index", rows=5)
        side = list_row.column(align=True)
        side.operator("gtatools.grass_add", text="", **inu_icon(safe_icon('ADD')))
        side.operator("gtatools.grass_remove", text="", **inu_icon(safe_icon('REMOVE')))
        side.separator()
        side.operator("gtatools.grass_duplicate", text="", **inu_icon(safe_icon('DUPLICATE')))

        entries = s.gtatools_grass_entries
        idx = s.gtatools_grass_index
        has_sel = 0 <= idx < len(entries)

        # Under the list: assign the SELECTED entry's surface (its COL
        # material, auto-created) to the selected faces — pick a plants.dat
        # entry, then apply its collision material in one click.
        arow = layout.row()
        arow.enabled = has_sel
        arow.operator("gtatools.grass_apply_surface",
                      text=T("Назначить выделенным полигонам"),
                      **inu_icon(safe_icon('FACESEL')))

        if not has_sel:
            layout.label(text=T("Импортируй plants.dat или добавь запись"),
                         **inu_icon(safe_icon('INFO')))
            return
        item = entries[idx]

        # Selected entry — surface picker header + collapsible sections
        # (disclosure triangles), with Предпросмотр pinned at the top.
        from ..data.surface_materials import resolve_surface_id
        box = layout.box()
        nrow = box.row(align=True)
        sid = resolve_surface_id(item.name)
        nrow.label(text=f"{sid}: {item.name}" if sid is not None else item.name,
                   translate=False, **inu_icon(safe_icon('PHYSICS')))
        pick = nrow.operator("gtatools.col_surface_menu", text="", **inu_icon(safe_icon('VIEWZOOM')))
        pick.target = 'GRASS'
        pick.material_name = ""

        # align=True on the wrapper glues the section boxes together — no
        # empty gaps between them.
        sec_col = box.column(align=True)

        def _section(prop, title):
            b = sec_col.box()
            is_open = getattr(s, prop)
            tri = safe_icon('DISCLOSURE_TRI_DOWN' if is_open else 'DISCLOSURE_TRI_RIGHT')
            b.row(align=True).prop(s, prop, text=title, **inu_icon(tri), emboss=False)
            return b.column(align=True) if is_open else None

        c = _section("gtatools_grass_exp_main", T("Основа"))
        if c:
            c.prop(item, "pcd_id")
            c.prop(item, "density", slider=True)
        c = _section("gtatools_grass_exp_tex", T("Текстура"))
        if c:
            c.prop(item, "slot_id")
            c.prop(item, "model_id")
            c.prop(item, "uv_off")
            c.label(text=T("Спрайт: txgrass{Slot}_{UVoff} в .txd"),
                    **inu_icon(safe_icon('TEXTURE')))
        c = _section("gtatools_grass_exp_color", T("Цвет"))
        if c:
            rgb = c.row(align=True)
            rgb.prop(item, "r")
            rgb.prop(item, "g")
            rgb.prop(item, "b")
            c.prop(item, "intensity", slider=True)
            c.prop(item, "var_i", slider=True)
            c.prop(item, "alpha", slider=True)
        c = _section("gtatools_grass_exp_size", T("Размер"))
        if c:
            c.prop(item, "scl_xy")
            c.prop(item, "scl_z")
            c.prop(item, "scl_var_xy")
            c.prop(item, "scl_var_z")
        c = _section("gtatools_grass_exp_wind", T("Ветер"))
        if c:
            c.prop(item, "wbend_scl")
            c.prop(item, "wbend_var", slider=True)


def _water_quad_fit_counts(obj):
    """(over, cross, ok) face counts against the 500×500 water-block grid.

    Tris and quads only — anything else isn't exportable water geometry
    and is skipped rather than counted as a failure. Called through
    ``draw_cache.memo``; see the call site for the key.
    """
    from ..core.water import check_quad_fit
    mat_w = obj.matrix_world
    verts = obj.data.vertices
    n_ok = n_cross = n_over = 0
    for poly in obj.data.polygons:
        if len(poly.vertices) not in (3, 4):
            continue
        world = [mat_w @ verts[vi].co for vi in poly.vertices]
        xs = [v.x for v in world]
        ys = [v.y for v in world]
        st = check_quad_fit(min(xs), min(ys), max(xs), max(ys))
        if st == 'ok':
            n_ok += 1
        elif st == 'cross':
            n_cross += 1
        else:
            n_over += 1
    return n_over, n_cross, n_ok


@apply_order
class GTATOOLS_PT_water_panel(bpy.types.Panel):
    """Панель Water IO"""
    bl_label = "Water"
    bl_idname = "GTATOOLS_PT_water_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('MOD_FLUIDSIM')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'water')

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Top — Import/Export + Add water fused.
        top_col = layout.column(align=True)
        row = top_col.row(align=True)
        row.operator("gtatools.import_water", text=T("Импорт"), **inu_icon(safe_icon('IMPORT')))
        row.operator("gtatools.export_water", text=T("Экспорт"), **inu_icon(safe_icon('EXPORT')))
        top_col.operator("gtatools.add_water", text=T("Добавить воду"), **inu_icon(safe_icon('SHADING_RENDERED')))

        # Water parameters — fused inside box.
        params_col = layout.box().column(align=True)
        params_col.label(text=T("Параметры воды:"), **inu_icon(safe_icon('PREFERENCES')))
        flag_labels = {
            '0': T("Обычная / Невидимая"),
            '1': T("Обычная / Видимая"),
            '2': T("Мелкая / Невидимая"),
            '3': T("Мелкая / Видимая"),
        }
        params_col.prop_menu_enum(scene.inu_settings, "gtatools_water_flag", text=flag_labels.get(scene.inu_settings.gtatools_water_flag, "?"))
        params_col.label(text=T("Скорость течения:"))
        row = params_col.row(align=True)
        row.prop(scene.inu_settings, "gtatools_water_speed_x", text="X")
        row.prop(scene.inu_settings, "gtatools_water_speed_y", text="Y")
        row.prop(scene.inu_settings, "gtatools_water_speed_z", text="Z")
        params_col.prop(scene.inu_settings, "gtatools_water_wave_height", text=T("Волны"))
        params_col.operator("gtatools.water_set_params", text=T("Применить"), **inu_icon(compat.ICON_CHECK))

        # Tools — fused inside box.
        tools_col = layout.box().column(align=True)
        tools_col.label(text=T("Инструменты:"), **inu_icon(safe_icon('TOOL_SETTINGS')))
        tools_col.operator("gtatools.water_snap_grid", text=T("Привязка к сетке (x4)"), **inu_icon(safe_icon('SNAP_GRID')))
        tools_col.operator("gtatools.water_snap_block", text=T("Привязка к блоку (500)"), **inu_icon(safe_icon('SNAP_VERTEX')))
        tools_col.operator("gtatools.water_split_blocks", text=T("Порезать по блокам (500)"), **inu_icon(safe_icon('MOD_EDGESPLIT')))
        tools_col.operator("gtatools.water_stitch", text=T("Сшить края"), **inu_icon(safe_icon('AUTOMERGE_ON')))

        # Limits overlay toggle — depress reflects live state.
        from ..ops import water_geometry_ops as _wg
        tools_col.operator(
            "gtatools.toggle_water_limits",
            text=T("Показать лимиты (500)"),
            depress=_wg._water_limits_active,
            **inu_icon(safe_icon('GRID')))

        # Show active object water info + per-face fit summary.
        obj = context.active_object
        if obj and obj.type == 'MESH' and 'water_flag' in obj:
            layout.separator()
            box = layout.box()
            flag = obj.get('water_flag', -1)
            flag_names = {
                0: "Default / Invisible",
                1: "Default / Visible",
                2: "Shallow / Invisible",
                3: "Shallow / Visible",
            }
            box.label(text=f"{obj.name}: {flag_names.get(flag, '?')} (flag={flag})", **inu_icon(safe_icon('INFO')))

            # Per-face fit is a Python loop over the whole mesh with a
            # matrix multiply per vertex — memoised, or it would run on
            # every redraw just because a water object is active. The
            # matrix is part of the key: the verdict is world-space, so
            # moving or scaling the plane must recompute it (a pure
            # transform deliberately does NOT bump the scene generation).
            n_over, n_cross, n_ok = draw_cache.memo(
                ('water_fit', obj.name, len(obj.data.polygons),
                 tuple(obj.matrix_world[i][j] for i in range(4) for j in range(4))),
                lambda: _water_quad_fit_counts(obj))
            if n_over or n_cross:
                box.label(text=f"{T('Не влезает:')} {n_over}  {T('на границе:')} {n_cross}  OK: {n_ok}",
                          **inu_icon(safe_icon('ERROR')))
            else:
                box.label(text=f"{T('Все грани влезают')} ({n_ok})", **inu_icon(compat.ICON_CHECK))



@apply_order
class GTATOOLS_PT_timecyc_panel(bpy.types.Panel):
    """Панель тайм-циклов: timecyc.dat → освещение сцены и обратно."""
    bl_label = "Тайм-циклы"
    bl_idname = "GTATOOLS_PT_timecyc_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('WORLD')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'timecyc')

    def draw(self, context):
        layout = self.layout
        props = context.scene.inu_settings.gtatools_timecyc

        from ..ops import timecyc_ops as tco
        cyc = tco.get_cyc(context)

        if cyc is None:
            # Файла нет — Импорт/Экспорт сверху (Импортом его и грузят) +
            # подсказка. Комбинированный блок с погодой показывать нечему.
            io = layout.row(align=True)
            io.scale_y = 1.4
            io.operator("gtatools.import_timecyc", text=T("Импорт"),
                        **inu_icon(safe_icon('IMPORT')))
            io.operator("gtatools.export_timecyc", text=T("Экспорт"),
                        **inu_icon(safe_icon('EXPORT')))
            info = layout.box().column(align=True)
            info.label(text=T("Файл не загружен"), **inu_icon(safe_icon('INFO')))
            info.label(text=T("data/timecyc.dat из папки игры"))
            return

        # Файл есть: слева выбор погоды + «Погод в файле», справа высокие
        # (в 2 ряда) кнопки Импорт/Экспорт — как просил: [погода][Имп][Эксп].
        _top = layout.split(factor=0.5, align=True)
        _wl = _top.column(align=True)
        _wl.prop_search(props, "weather_name", props, "weathers",
                        text="", icon=safe_icon('WORLD'))
        _wl.label(text=T("Погод в файле: %d") % len(cyc.weathers))
        _wr = _top.row(align=True)
        _wr.scale_y = 2.0
        _wr.operator("gtatools.import_timecyc", text=T("Импорт"),
                     **inu_icon(safe_icon('IMPORT')))
        _wr.operator("gtatools.export_timecyc", text=T("Экспорт"),
                     **inu_icon(safe_icon('EXPORT')))

        # ── Мастер вкл/выкл всего тайм-цикла ──
        en = props.enabled
        tgl = layout.row(align=True)
        tgl.scale_y = 1.3
        tgl.operator("gtatools.timecyc_toggle",
                     text=T("Тайм-цикл включён") if en else T("Тайм-цикл выключен"),
                     depress=en,
                     **inu_icon(safe_icon('CHECKBOX_HLT' if en
                                          else 'CHECKBOX_DEHLT')))

        time_box = layout.box().column(align=True)
        time_box.prop(props, "hour", text=T("Время"), slider=True)
        time_box.label(text=_timecyc_between_label(props.hour))
        # «Живое превью», «Применить», «Показать в вьюпорте» убраны: превью
        # всегда живое пока цикл включён, а вьюпорт переводится в Material
        # Preview автоматически (show_in_viewport при импорте/включении).

        # Прилайт Day↔Night — заметная фича, живёт в теле панели.
        pre_box = layout.box().column(align=True)
        pre_box.prop(props, "game_look", **inu_icon(safe_icon('SHADING_SOLID')))
        # Тумблера «Прилайт по времени суток» нет — он всегда включён
        # (props.prelight_daynight форсится при активном тайм-цикле).
        row = pre_box.row(align=True)
        row.operator("gtatools.timecyc_setup_materials",
                     text=T("Применить к моделям сцены"),
                     **inu_icon(safe_icon('SHADERFX')))
        row.operator("gtatools.timecyc_reset_preview", text="",
                     **inu_icon(safe_icon('LOOP_BACK')))
        row.operator("gtatools.timecyc_diagnose", text="",
                     **inu_icon(safe_icon('CONSOLE')))
        pre_box.label(text=T("Ночной вес: %.2f") % _timecyc_night_balance(props),
                      **inu_icon(safe_icon('INFO')))


        if (props.game_look or props.prelight_daynight)                 and props.dn_material_count == 0:
            warn = pre_box.column(align=True)
            warn.alert = True
            warn.label(text=T("Нет материалов с превью прилайта"),
                       **inu_icon(safe_icon('ERROR')))
            warn.label(text=T("Включите его в панели PreLight"))

        dirty = cyc.dirty_count()
        if dirty:
            warn = layout.box().column(align=True)
            warn.alert = True
            warn.label(text=T("Не сохранено срезов: %d") % dirty,
                       **inu_icon(safe_icon('ERROR')))
            warn.operator("gtatools.timecyc_reload",
                          text=T("Перечитать файл"),
                          **inu_icon(safe_icon('FILE_REFRESH')))


def _timecyc_fog_label(context, props):
    """Фактические дистанции тумана — чтобы было с чем сверять игру."""
    from ..ops import timecyc_ops as tco
    cyc = tco.get_cyc(context, load=False)
    if cyc is None:
        return T("Туман: срез не загружен")
    values = cyc.interpolate(tco.weather_index(props, cyc), props.hour)
    start = max(float((values.get('fog_start') or [0.0])[0]), 0.0)
    end = max(float((values.get('far_clip') or [800.0])[0]), 1.0)
    scale = props.fog_distance
    return T("Туман: %d → %d м") % (round(start * scale), round(end * scale))


def _timecyc_postfx_label(context, props):
    """Текущий множитель кадра — видно, насколько фильтр тянет цвет."""
    from ..ops import timecyc_ops as tco
    from ..core import timecyc as _tc
    cyc = tco.get_cyc(context, load=False)
    if cyc is None or not props.use_postfx:
        return T("Множитель кадра: 1.00 / 1.00 / 1.00")
    values = cyc.interpolate(tco.weather_index(props, cyc), props.hour)
    gain = _tc.postfx_gain(values)
    return T("Множитель кадра: %.2f / %.2f / %.2f") % gain


def _timecyc_night_balance(props):
    """Тот же расчёт, что уходит в нод-группу — чтобы панель не врала."""
    from ..core import timecyc as _tc
    return _tc.night_balance(
        props.hour,
        dusk_start=props.dn_dusk_start, dusk_end=props.dn_dusk_end,
        dawn_start=props.dn_dawn_start, dawn_end=props.dn_dawn_end)


def _timecyc_between_label(hour):
    """Подпись «между какими срезами сейчас интерполяция» — иначе
    непонятно, какой из восьми срезов правится под текущий час."""
    from ..core import timecyc as _tc
    hour = float(hour) % 24.0
    lo = len(_tc.SLOT_HOURS) - 1
    for i, h in enumerate(_tc.SLOT_HOURS):
        if hour < h:
            lo = i - 1
            break
    if lo < 0:
        lo = len(_tc.SLOT_HOURS) - 1
    hi = (lo + 1) % len(_tc.SLOT_HOURS)
    return "%s %02d:00 → %02d:00" % (T("Между срезами"),
                                     _tc.SLOT_HOURS[lo], _tc.SLOT_HOURS[hi])


class GTATOOLS_PT_timecyc_edit(bpy.types.Panel):
    """Правка одного временно́го среза выбранной погоды."""
    bl_label = "Правка среза"
    bl_idname = "GTATOOLS_PT_timecyc_edit"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_timecyc_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        from ..ops import timecyc_ops as tco
        return tco.get_cyc(context, load=False) is not None

    def draw(self, context):
        layout = self.layout
        props = context.scene.inu_settings.gtatools_timecyc

        from ..ops import timecyc_ops as tco
        from ..core import timecyc as _tc
        cyc = tco.get_cyc(context)
        slot = tco.current_slot(context, cyc)

        layout.prop(props, "slot", text=T("Срез"))
        if slot is None:
            layout.label(text=T("Срез недоступен"), **inu_icon(safe_icon('ERROR')))
            return

        if slot.width != _tc.schema_width(cyc.fields):
            note = layout.box().column(align=True)
            note.label(text=T("Строка короче схемы: %d из %d")
                       % (slot.width, _tc.schema_width(cyc.fields)),
                       **inu_icon(safe_icon('INFO')))
            note.label(text=T("Поля читаются со сдвигом — как их видит игра"))

        sky = layout.box().column(align=True)
        sky.label(text=T("Небо и солнце:"), **inu_icon(safe_icon('LIGHT_SUN')))
        sky.prop(props, "f_sky_top", text=T("Зенит"))
        sky.prop(props, "f_sky_bot", text=T("Горизонт"))
        sky.prop(props, "f_sun_size", text=T("Размер солнца"))
        sky.prop(props, "f_spr_size", text=T("Размер блика"))
        sky.prop(props, "f_spr_bright", text=T("Яркость блика"))

        light = layout.box().column(align=True)
        light.label(text=T("Свет и тени:"), **inu_icon(safe_icon('OUTLINER_OB_LIGHT')))
        light.prop(props, "f_amb", text=T("Ambient мира"))
        light.prop(props, "f_amb_obj", text=T("Ambient объектов"))
        if cyc.has_field('dir'):
            light.prop(props, "f_dir", text=T("Directional"))
            light.prop(props, "f_dir_mult", text=T("Множитель dir"))
        light.prop(props, "f_light_on_ground", text=T("Свет на земле"))
        light.prop(props, "f_shadow", text=T("Тени"))
        light.prop(props, "f_light_shad", text=T("Тени от света"))
        light.prop(props, "f_pole_shad", text=T("Тени столбов"))
        light.prop(props, "f_highlight_min", text=T("Мин. блики"))

        fog = layout.box().column(align=True)
        fog.label(text=T("Туман и дальность:"), **inu_icon(safe_icon('MOD_FLUIDSIM')))
        fog.prop(props, "f_far_clip", text=T("Дальность (FarClp)"))
        fog.prop(props, "f_fog_start", text=T("Начало тумана"))

        clouds = layout.box().column(align=True)
        clouds.label(text=T("Облака:"), **inu_icon(safe_icon('OUTLINER_OB_VOLUME')))
        clouds.prop(props, "f_low_clouds", text=T("Нижние"))
        clouds.prop(props, "f_bottom_clouds", text=T("У горизонта"))
        clouds.prop(props, "f_cloud_alpha", text=T("Прозрачность"))

        water = layout.box().column(align=True)
        water.label(text=T("Вода:"), **inu_icon(safe_icon('MATFLUID')))
        water.prop(props, "f_water", text=T("Цвет"))
        water.prop(props, "f_water_a", text=T("Альфа"))
        water.prop(props, "f_water_fog", text=T("Туман под водой"))

        post = layout.box().column(align=True)
        post.label(text=T("PostFX:"), **inu_icon(safe_icon('SEQ_PREVIEW')))
        post.prop(props, "f_postfx1", text=T("Слой 1"))
        post.prop(props, "f_postfx1_a", text=T("Альфа 1"))
        post.prop(props, "f_postfx2", text=T("Слой 2"))
        post.prop(props, "f_postfx2_a", text=T("Альфа 2"))
        post.label(text=T("В вьюпорте не показывается"),
                   **inu_icon(safe_icon('INFO')))

        tools = layout.column(align=True)
        tools.operator("gtatools.timecyc_revert_slot",
                       text=T("Откатить срез"),
                       **inu_icon(safe_icon('LOOP_BACK')))
        tools.operator("gtatools.timecyc_copy_to_all_slots",
                       text=T("Во все срезы погоды"),
                       **inu_icon(safe_icon('DUPLICATE')))


class GTATOOLS_PT_timecyc_preview(bpy.types.Panel):
    """Ручки превью: как значения среза ложатся на свет Blender."""
    bl_label = "Настройки превью"
    bl_idname = "GTATOOLS_PT_timecyc_preview"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_timecyc_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        from ..ops import timecyc_ops as tco
        return tco.get_cyc(context, load=False) is not None

    def draw(self, context):
        layout = self.layout
        props = context.scene.inu_settings.gtatools_timecyc

        sky = layout.box().column(align=True)
        sky.label(text=T("Небо и ambient:"), **inu_icon(safe_icon('WORLD')))
        sky.prop(props, "sky_strength")
        sky.prop(props, "gradient")
        sky.prop(props, "ambient_split")
        sub = sky.column(align=True)
        sub.enabled = props.ambient_split
        sub.prop(props, "ambient_strength")
        sub.prop(props, "ambient_from_objects")

        screen = layout.box().column(align=True)
        screen.label(text=T("Экранные эффекты (композитор):"),
                     **inu_icon(safe_icon('NODE_COMPOSITING')))
        screen.prop(props, "use_fog", **inu_icon(safe_icon('MOD_FLUIDSIM')))
        sub = screen.column(align=True)
        sub.enabled = props.use_fog
        sub.prop(props, "fog_curve")
        sub.prop(props, "fog_distance")
        sub.label(text=_timecyc_fog_label(context, props))

        # PostFX (цветофильтр) — всегда включён при активном тайм-цикле,
        # тумблера нет; показываем только текущие значения фильтра.
        screen.label(text=_timecyc_postfx_label(context, props),
                     **inu_icon(safe_icon('SEQ_PREVIEW')))
        if props.use_fog or props.use_postfx:
            from ..tools import timecyc_screen
            on, total = timecyc_screen.viewport_compositor_state(context)
            if on:
                screen.label(text=T("Композитор вьюпорта: вкл (%d из %d)")
                             % (on, total), **inu_icon(compat.ICON_CHECK))
            else:
                warn = screen.column(align=True)
                warn.alert = True
                warn.label(text=T("Композитор вьюпорта выключен — "
                                  "экранных эффектов не видно"),
                           **inu_icon(safe_icon('ERROR')))
                warn.operator("gtatools.timecyc_compositor",
                              text=T("Включить композитор"),
                              **inu_icon(safe_icon('NODE_COMPOSITING')))

        # Блок «Прилайт Day/Night» (пороги заката/рассвета) убран из UI —
        # значения фиксированные (dn_dusk_*/dn_dawn_* дефолты), Day↔Night
        # всегда включён.

        misc = layout.box().column(align=True)
        misc.prop(props, "use_water")
        misc.prop(props, "use_far_clip")


@apply_order
class GTATOOLS_PT_zon_panel(bpy.types.Panel):
    """Панель зон карты: импорт/экспорт map.zon (и info.zon) боксами."""
    bl_label = "map.zon"
    bl_idname = "GTATOOLS_PT_zon_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    # Тип зоны в файле — число; подписи, чтобы не лезть в вики.
    _TYPES = {
        0: "0 — навигация (info.zon)",
        1: "1 — navig",
        2: "2 — info",
        3: "3 — зона карты (map.zon)",
        4: "4 — погода (мод)",
    }

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('MESH_CUBE')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'zon')

    def draw(self, context):
        from ..ops.zon_ops import TAG as _ZON_TAG
        layout = self.layout
        s = context.scene.inu_settings

        # Файл + две главные кнопки — один сплошной блок сверху.
        top = layout.column(align=True)
        top.prop(s, "gtatools_zon_path", text="", **inu_icon(safe_icon('FILE_TEXT')))
        row = top.row(align=True)
        row.operator("gtatools.import_zon", text=T("Импорт"),
                     **inu_icon(safe_icon('IMPORT')))
        row.operator("gtatools.export_zon", text=T("Экспорт"),
                     **inu_icon(safe_icon('EXPORT')))
        top.operator("gtatools.add_zon_zone", text=T("Новая зона"),
                     **inu_icon(safe_icon('ADD')))
        # Генерация строк — то, что чаще всего и нужно: выделил боксы (или
        # обычные меши) и вставил готовые строки руками в map.zon.
        gen = top.row(align=True)
        gen.enabled = bool(context.selected_objects)
        gen.operator("gtatools.zon_copy_lines", text=T("Строки в буфер"),
                     **inu_icon(safe_icon('COPYDOWN')))

        # Считаем по ZON_-коллекциям, а не по всей сцене: на большой карте
        # это десятки объектов вместо десятков тысяч. Плюс memo — счёт
        # переживает и навигацию, и перетаскивание бокса.
        n_zones = draw_cache.memo(
            ('zon_count', len(bpy.data.collections)),
            lambda: sum(1 for c in bpy.data.collections
                        if c.name.startswith("ZON_")
                        for o in c.objects if o.get(_ZON_TAG)))
        layout.label(text=f"{T('Зон в сцене:')} {n_zones}",
                     **inu_icon(safe_icon('INFO')))

        # Параметры активного бокса — правятся прямо здесь, координаты
        # берутся из габаритов объекта при экспорте.
        obj = context.active_object
        if obj is None or not obj.get(_ZON_TAG):
            layout.label(text=T("Выдели бокс зоны, чтобы править параметры"),
                         **inu_icon(safe_icon('INFO')))
            return

        box = layout.box().column(align=True)
        box.label(text=obj.name, **inu_icon(safe_icon('MESH_CUBE')))
        for key, label in (('zon_name', T("Имя")), ('zon_type', T("Тип")),
                           ('zon_level', T("Уровень")), ('zon_gxt', "GXT")):
            if key in obj:
                box.prop(obj, f'["{key}"]', text=label)
            if key == 'zon_type':
                box.label(text=self._TYPES.get(int(obj.get('zon_type', 0)),
                                               T("свой тип")))

        # Схлопнутая по одной оси зона не поймает ни одной точки — движок
        # проверяет попадание в габарит включительно по всем трём осям.
        if min(obj.dimensions) <= 0.001:
            box.label(text=T("Нулевой размер по одной из осей"),
                      **inu_icon(safe_icon('ERROR')))


def _find_animobj_rig_name():
    """Name of the Animated-Map-Object rig root Empty, or ''.

    Whole-file scan behind ``draw_cache.memo`` — returns a NAME, never
    the object, so a stale memo can't hold a freed pointer.
    """
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.get('inu_animobj_empty_root'):
            return o.name
    return ''


@apply_order
class GTATOOLS_PT_anim_panel(bpy.types.Panel):
    """Панель анимаций IFP"""
    bl_label = "Анимации"
    bl_idname = "GTATOOLS_PT_anim_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('ARMATURE_DATA')))

    def draw_header_preset(self, context):
        # «?» ведёт в раздел по активной вкладке: Объект → Animated Map Objects,
        # иначе → Персонажи (Skinned DFF). Иконка справа, единообразно с др. панелями.
        tab = context.scene.inu_settings.gtatools_anim_tab
        _draw_doc_help(self.layout,
                       'anim_object' if tab == 'OBJ' else 'anim_character')

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # ── Internal tab switcher ──
        # Two distinct workflows ended up in this panel: ped/character
        # animation (IFP, IK Rig) and animated map props (windmills,
        # cranes). They have nothing in common UX-wise, so a tab row
        # at the top hides the irrelevant half. Tabs + первая action
        # row живут в общем `column(align=True)` — fused: между ними
        # нет 18-px gap. Остальной контент (boxes, sliders, labels)
        # переходит на обычный layout, чтобы box-рамки не превращались
        # в куски слипшейся стенки.
        top = layout.column(align=True)
        # Tabs side-by-side: expand=True inside a column places items
        # vertically (one per row), so wrap in row(align=True) for the
        # standard segmented-control look.
        tab_row = top.row(align=True)
        tab_row.prop(scene.inu_settings, "gtatools_anim_tab", expand=True)

        if scene.inu_settings.gtatools_anim_tab == 'OBJ':
            self._draw_object_tab(context, layout, top)
        else:
            self._draw_character_tab(context, layout, top)

    def _draw_object_tab(self, context, layout, top=None):
        """Animated Map Object — single-bone rotating prop workflow.

        ``top`` — общий fused column с tabs выше. Если передан, первая
        action row рисуется в нём, чтобы прилегать к табам без gap.
        """
        scene = context.scene
        obj = context.active_object

        # ── Top action row ──
        # In the Object tab the «Импорт» slot from the Character tab is
        # replaced by the combo «DFF+IFP+IDE»: importing an IFP rarely
        # makes sense when you're authoring a new animated prop from
        # scratch, but writing all three artefacts at once is the main
        # action for this workflow.
        row = (top or layout).row(align=True)
        row.operator("gtatools.animobj_export",
                     text=T("DFF+IFP+IDE"), **inu_icon(safe_icon('EXPORT')))
        row.operator("gtatools.export_ifp",
                     text=T("Экспорт"), **inu_icon(safe_icon('EXPORT')))
        row.operator("gtatools.merge_ifp",
                     text=T("Добавить"), **inu_icon(safe_icon('FILE_REFRESH')))

        # Actions live outside the depsgraph, so len(bpy.data.actions) goes
        # into the key — an IFP import bumps it and the count refreshes.
        n_ifp_actions = draw_cache.memo(
            ('ifp_action_count', len(bpy.data.actions)),
            lambda: sum(1 for a in bpy.data.actions if a.get('ifp_source')))
        if n_ifp_actions:
            layout.label(
                text=f"{n_ifp_actions} {T('анимаций загружено')}")

        layout.separator()

        amo_box = layout.box()
        amo_box.label(text=T("Animated Map Object"), **inu_icon(safe_icon('MOD_SCREW')))

        # State-driven UI: pipette is enabled only when there's a clear
        # «static base» to anchor the rig on. Three states:
        #   1. Rig exists                   → pipette + radio, target chosen.
        #   2. Mesh active outside any rig  → pipette enabled, hint
        #      «Статика: <name>». Pick attaches BOTH: active → root
        #      (static), picked → new pivot (animated).
        #   3. No mesh active and no rig    → pipette disabled, hint
        #      «Выдели меш-основание».
        # Memoised by NAME (a memo must never pin an Object reference —
        # it would dangle after undo/delete); the object is looked up
        # fresh each draw, which is a hash lookup.
        rig_name = draw_cache.memo(
            ('animobj_rig', len(bpy.data.objects)), _find_animobj_rig_name)
        scene_rig = bpy.data.objects.get(rig_name) if rig_name else None

        def _is_in_rig(o):
            c = o
            while c is not None:
                if (c.type == 'EMPTY'
                        and c.get('inu_animobj_empty_root')):
                    return True
                c = c.parent
            return False

        active_mesh = obj if (obj is not None and obj.type == 'MESH') else None
        active_in_rig = (active_mesh is not None
                         and _is_in_rig(active_mesh))
        rig_exists = scene_rig is not None

        # Context hint line so the user knows what the pipette will do.
        hint_col = amo_box.column(align=True)
        hint_col.scale_y = 0.85
        if rig_exists:
            hint_col.label(
                text=f"{T('Target rig:')} {scene_rig.name}",
                **inu_icon(safe_icon('OUTLINER')))
        elif active_mesh is not None and not active_in_rig:
            hint_col.label(
                text=f"{T('Статика:')} {active_mesh.name}",
                **inu_icon(safe_icon('OUTLINER_OB_MESH')))
            hint_col.label(
                text=T("Пипеткой выбери анимированную часть ↓"),
                **inu_icon(safe_icon('EYEDROPPER')))
        else:
            hint_col.label(
                text=T("Выдели меш-основание (станет статикой)"),
                **inu_icon(safe_icon('INFO')))

        # Pipette + radio — disabled when there's nothing to anchor on.
        pick_row = amo_box.column(align=True)
        pick_row.enabled = rig_exists or (active_mesh is not None
                                          and not active_in_rig)
        # Radio is only meaningful when a rig already exists. For the
        # first pick we always wire static→root and picked→new pivot,
        # so the radio would only confuse.
        if rig_exists:
            pick_row.prop(scene.inu_settings, "gtatools_animobj_picker_target",
                          expand=True)
        pick_row.prop(scene.inu_settings, "gtatools_animobj_picker", text="")

        val_row = amo_box.row(align=True)
        val_row.enabled = rig_exists
        val_row.operator("gtatools.animobj_validate",
                         text=T("Validate"),
                         **inu_icon(compat.ICON_CHECK))

        # Live-edit sliders bind to the active pivot Empty. Walk up
        # parents so selecting a mesh inside the rig still surfaces the
        # sliders — works equally for nested meshes via outliner click.
        empty_pivot = None
        if obj is not None:
            cursor = obj
            while cursor is not None and empty_pivot is None:
                if (cursor.type == 'EMPTY'
                        and cursor.get('inu_animobj_empty_pivot')):
                    empty_pivot = cursor
                cursor = cursor.parent

        if empty_pivot is not None:
            ed_box = amo_box.box()
            ed_box.label(text=f"{T('Настройки')}: {empty_pivot.name}",
                         **inu_icon(safe_icon('EMPTY_ARROWS')))

            # Show child meshes summary — the typical «animation doesn't
            # work» symptom is no mesh parented to the pivot, so we
            # surface it up front.
            pivot_meshes = [c for c in empty_pivot.children if c.type == 'MESH']
            root_obj = empty_pivot.parent
            root_meshes = []
            if root_obj is not None and root_obj.get('inu_animobj_empty_root'):
                root_meshes = [c for c in root_obj.children if c.type == 'MESH']
            kids_row = ed_box.column(align=True)
            kids_row.scale_y = 0.85
            kids_row.label(
                text=f"{T('Меш под pivot:')} {len(pivot_meshes)}"
                     f"  /  {T('под root:')} {len(root_meshes)}",
                **inu_icon(safe_icon('OUTLINER_OB_MESH')))
            if not pivot_meshes:
                kids_row.label(
                    text=T("Pivot пустой — анимация не будет видна. Выдели меш и нажми «К pivot»"),
                    **inu_icon(safe_icon('ERROR')))

            # Quick parenting buttons + "Add Pivot" for multi-part rigs.
            # The latter lets the user grow the rig (windmill + counter-
            # weight, sign + arrow, etc.) without manually wiring custom
            # IDProps via the outliner.
            pa_row = ed_box.row(align=True)
            pa_row.operator("gtatools.animobj_parent_to_pivot",
                            text=T("К pivot"),
                            **inu_icon(safe_icon('CON_CHILDOF')))
            pa_row.operator("gtatools.animobj_parent_to_root",
                            text=T("К root"),
                            **inu_icon(safe_icon('CON_CHILDOF')))
            pa_row.operator("gtatools.animobj_add_pivot",
                            text=T("+Pivot"),
                            **inu_icon(safe_icon('ADD')))

            # Eyedropper picker — click the pipette icon, then click on
            # a mesh in the viewport or pick from the dropdown. The mesh
            # is attached to the rig per the «Куда» radio button. Field
            # clears itself after each pick so the user can chain
            # multiple meshes without re-opening anything.
            if root_obj is not None:
                rig_settings = root_obj.inu_animobj_rig_settings
                pipette_box = ed_box.box().column(align=True)
                pipette_box.label(
                    text=T("Добавить меш в rig:"),
                    **inu_icon(safe_icon('EYEDROPPER')))
                pipette_box.prop(rig_settings, "attach_target", expand=True)
                pipette_box.prop(rig_settings, "attach_mesh", text="")

            # Show the rig tree so the user can see all pivots at once.
            # Particularly useful when the rig grew via Add Pivot and
            # each one needs different axis/turns settings.
            if root_obj is not None:
                tree_box = ed_box.box().column(align=True)
                tree_box.scale_y = 0.85
                tree_box.label(
                    text=T("Структура rig'а:"),
                    **inu_icon(safe_icon('OUTLINER')))
                # Walk root → children once and render as indented lines.
                # Skip non-rig empties to avoid clutter; meshes are shown
                # one-per-line under their parent.
                def _show_node(node, depth):
                    indent = "  " * depth
                    is_pivot = bool(node.get('inu_animobj_empty_pivot'))
                    is_root  = bool(node.get('inu_animobj_empty_root'))
                    if is_root:
                        icon = safe_icon('EMPTY_ARROWS')
                        tag = "[root]"
                    elif is_pivot:
                        icon = safe_icon('EMPTY_AXIS')
                        bid = int(node.get('inu_bone_id', 0))
                        tag = f"[pivot {bid}]"
                    elif node.type == 'MESH':
                        icon = safe_icon('OUTLINER_OB_MESH')
                        tag = "[mesh]"
                    else:
                        icon = safe_icon('EMPTY_DATA')
                        tag = ""
                    tree_box.label(
                        text=f"{indent}{node.name} {tag}",
                        **inu_icon(icon))

                _show_node(root_obj, 0)
                for ch in root_obj.children:
                    _show_node(ch, 1)
                    for gc in ch.children:
                        _show_node(gc, 2)

            eprops = empty_pivot.inu_animobj_empty_props
            mode_row = ed_box.row(align=True)
            mode_row.prop(
                eprops, "auto_mode",
                text=T("Авто"),
                **inu_icon(safe_icon('IPO_LINEAR')),
                toggle=True)
            mr = mode_row.row(align=True)
            mr.enabled = False
            mr.prop(
                eprops, "auto_mode",
                text=T("Вручную"),
                **inu_icon(safe_icon('HAND')),
                toggle=True, invert_checkbox=True)
            if eprops.auto_mode:
                ed_box.prop(eprops, "axis", expand=True)
                ed_box.prop(eprops, "reverse")
                ed_box.prop(eprops, "turns_per_cycle", slider=True)
                ed_box.prop(eprops, "duration_frames", slider=True)
                fps = max(1, scene.render.fps)
                sign = -1 if eprops.reverse else 1
                rpm = (sign * eprops.turns_per_cycle * fps
                       / max(1, eprops.duration_frames))
                ed_box.label(
                    text=f"≈ {rpm:+.2f} {T('об/сек при FPS')} {fps}",
                    **inu_icon(safe_icon('INFO')))
            else:
                col = ed_box.column(align=True)
                col.scale_y = 0.85
                col.label(
                    text=T("Manual режим — keyframes управляются вручную"),
                    **inu_icon(safe_icon('HAND')))
                col.label(text=T("Action Editor"))
                col.label(
                    text=T("Переключение в Auto перезапишет твои ключи"),
                    **inu_icon(safe_icon('ERROR')))
        elif rig_exists:
            # Rig in scene but active isn't a pivot — show its tree so
            # user knows what they'll be adding to via the top pipette.
            tree_box = amo_box.box().column(align=True)
            tree_box.scale_y = 0.85
            for ch in scene_rig.children:
                is_pivot = bool(ch.get('inu_animobj_empty_pivot'))
                icon = (safe_icon('EMPTY_AXIS') if is_pivot
                        else safe_icon('OUTLINER_OB_MESH')
                        if ch.type == 'MESH'
                        else safe_icon('EMPTY_DATA'))
                tag = (f"[pivot {int(ch.get('inu_bone_id', 0))}]"
                       if is_pivot else "[mesh]"
                       if ch.type == 'MESH' else "")
                tree_box.label(
                    text=f"  {ch.name} {tag}",
                    **inu_icon(icon))

    def _draw_character_tab(self, context, layout, top=None):
        """Character animations — IFP I/O, action apply, IK Rig.

        ``top`` — общий fused column с tabs выше. Если передан, первая
        action row рисуется в нём, чтобы прилегать к табам без gap.
        """
        scene = context.scene
        obj = context.active_object

        # ── Weight Paint helpers (только в WPAINT mode) ───────────
        # Появляется в начале панели когда юзер красит веса на скине
        # с split-вершинами (типичная ситуация после DFF импорта).
        # «Merge» временно сливает co-located вершины, штрихи ложатся
        # как на цельный меш — швы исчезают. «Apply» возвращает
        # split-геометрию с одинаковыми весами на cluster-mate'ах.
        if obj and obj.type == 'MESH' and obj.mode == 'WEIGHT_PAINT':
            wp_box = layout.box()
            wp_box.label(text=T("Weight Paint: швы"),
                         **inu_icon(safe_icon('GROUP_VERTEX')))
            in_merge = '_inu_weight_edit_backup' in obj
            if not in_merge:
                wp_box.label(
                    text=T("Слить co-located вершины для покраски:"),
                    **inu_icon(safe_icon('INFO')))
                row = wp_box.row(align=True)
                row.scale_y = 1.3
                row.operator("gtatools.weight_merge_start",
                             text=T("Объединить для покраски"),
                             **inu_icon(safe_icon('STICKY_UVS_LOC')))
            else:
                wp_box.label(
                    text=T("РЕЖИМ MERGE: не меняй геометрию!"),
                    **inu_icon(safe_icon('ERROR')))
                wp_box.label(
                    text=T("Не жми Ctrl+Z — Undo ломает backup-mesh!"),
                    **inu_icon(safe_icon('ERROR')))
                row = wp_box.row(align=True)
                row.scale_y = 1.3
                row.operator("gtatools.weight_merge_apply",
                             text=T("Применить и вернуть швы"),
                             **inu_icon(safe_icon('CHECKMARK')))
                row.operator("gtatools.weight_merge_cancel",
                             text=T("Откатить"),
                             **inu_icon(safe_icon('X')))
            layout.separator()

        # ── IFP main row ─────────────────────────────────────────
        # First action row рисуется в `top` (fused col c табами) если
        # его передали, иначе fallback на layout.
        row = (top or layout).row(align=True)
        row.operator("gtatools.import_ifp",
                     text=T("Импорт"), **inu_icon(safe_icon('IMPORT')))
        row.operator("gtatools.export_ifp",
                     text=T("Экспорт"), **inu_icon(safe_icon('EXPORT')))
        row.operator("gtatools.merge_ifp",
                     text=T("Добавить"), **inu_icon(safe_icon('FILE_REFRESH')))

        # Экспорт самой МОДЕЛИ скина/педа (скелетный DFF) в один .dff —
        # отдельно от IFP-анимаций выше. Кнопки IFP-ряда пишут анимацию, а
        # это пишет геометрию + скелет. Рисуем в fused-колонке `top`, чтобы
        # кнопка прилегала к ряду Импорт/Экспорт/Добавить без gap.
        (top or layout).operator("gtatools.quick_single_export",
                                 text=T("Экспорт скина (один DFF)…"),
                                 **inu_icon(safe_icon('EXPORT')))

        # ── Cutscene camera (.dat) ───────────────────────────────
        # Траектория катсцен-камеры GTA: FOV + позиция камеры + цель.
        # Отдельно от IFP-скелета — работает с обычной Camera + Empty.
        cam_box = layout.box()
        cam_box.label(text=T("Камера (катсцена .dat)"),
                      **inu_icon(safe_icon('CAMERA_DATA')))
        cam_row = cam_box.row(align=True)
        cam_row.operator("gtatools.import_camera_dat",
                         text=T("Импорт"), **inu_icon(safe_icon('IMPORT')))
        cam_row.operator("gtatools.export_camera_dat",
                         text=T("Экспорт"), **inu_icon(safe_icon('EXPORT')))

        # ── Loaded actions + apply / preview ─────────────────────
        # See the IFP count in GTATOOLS_PT_anim_panel for why len() is
        # part of the memo key.
        n_ifp_actions = draw_cache.memo(
            ('ifp_action_count', len(bpy.data.actions)),
            lambda: sum(1 for a in bpy.data.actions if a.get('ifp_source')))
        if n_ifp_actions:
            layout.label(
                text=f"{n_ifp_actions} {T('анимаций загружено')}")
            if obj and obj.type == 'ARMATURE':
                # NOTE: UILayout.prop_search() НЕ принимает `icon_value`,
                # только string `icon`. Поэтому используем safe_icon
                # напрямую, не через inu_icon (который может вернуть
                # icon_value для PNG-bake'нутых Lucide-иконок).
                layout.prop_search(scene.inu_settings, "gtatools_ifp_action",
                                   bpy.data, "actions",
                                   text=T("Анимация"), icon=safe_icon('ACTION'))
                ar = layout.row(align=True)
                ar.operator("gtatools.apply_ifp",
                            text=T("Применить"), **inu_icon(safe_icon('PLAY')))
                try:
                    from ..ops.ifp_import import preview_is_active as _pv
                    _pv_on = _pv()
                except Exception:
                    _pv_on = False
                ar.operator(
                    "gtatools.ifp_preview_toggle",
                    text=T("Preview") if not _pv_on else T("Preview ●"),
                    **inu_icon(('HIDE_OFF' if not _pv_on
                          else 'RESTRICT_VIEW_OFF')),
                    depress=_pv_on)
                if obj.animation_data and obj.animation_data.action:
                    cur_row = layout.row(align=True)
                    cur_row.label(
                        text=f"{T('Текущая')}: "
                             f"{obj.animation_data.action.name}",
                        **inu_icon(safe_icon('ARMATURE_DATA')))
                    cur_row.operator(
                        "gtatools.delete_active_action",
                        text="", **inu_icon(safe_icon('TRASH')))
            else:
                layout.label(text=T("Выделите скелет для применения"),
                             **inu_icon(safe_icon('INFO')))

        # ── IK Rig label (no separator — the label itself
        # gives enough visual break, factor=1.5 leaves a too-big
        # gap on Blender 5.x default UI scale)
        layout.label(text=T("IK Rig"), **inu_icon(safe_icon('CON_KINEMATIC')))

        if obj and obj.type == 'ARMATURE':
            if obj.get('inu_ik_rigged'):
                layout.operator("gtatools.bake_ik_rig",
                                text=T("Bake & Clear IK"), **inu_icon(safe_icon('REC')))
            else:
                # Root motion toggle — must be set BEFORE Add IK Rig,
                # determines whether INU_IK_root targets Pelvis (off,
                # default) or the topmost bone (on, for walk/run).
                layout.prop(scene.inu_settings, "gtatools_ik_root_motion",
                            text=T("Root motion (walk/run)"))
                layout.operator("gtatools.add_ik_rig",
                                text=T("Add IK Rig"),
                                **inu_icon(safe_icon('CON_KINEMATIC')))

        # ── Handsign Tools — авторинг жестов банды (ghands.ifp) ──
        # Кисти shandl/shandr — отдельные скелеты; кнопка цепляет их к
        # запястьям скелета игрока (Child Of), чтобы анимировать жест
        # синхронно. Экспорт жеста — штатным IFP-экспортом по каждой armature
        # (рука→gsignN, левые пальцы→lhgsignN, правые→rhgsignN).
        from ..ops.handsign_ops import classify_handsign_armatures
        hs_box = layout.box().column(align=True)
        hs_box.label(text="Handsign Tools", **inu_icon(safe_icon('VIEW_PAN')))
        _ped, _lh, _rh = classify_handsign_armatures(context)
        _sr = hs_box.row(align=True)
        _sr.scale_y = 0.85
        _sr.label(
            text="{0} · L:{1} · R:{2}".format(
                _ped.name if _ped else "—",
                "✓" if _lh else "—", "✓" if _rh else "—"),
            **inu_icon(safe_icon('ARMATURE_DATA')))
        _hr = hs_box.row(align=True)
        _hr.enabled = bool(_ped) and bool(_lh or _rh)
        _hr.operator("gtatools.handsign_attach", text=T("Прицепить кисти"),
                     **inu_icon(safe_icon('CONSTRAINT_BONE')))
        hs_box.operator("gtatools.handsign_detach", text=T("Отцепить"),
                        **inu_icon(safe_icon('X')))
        # Экспорт жеста в один заход — три активные Action (рука + обе кисти)
        # → ghands.ifp одним merge.
        hs_box.operator("gtatools.handsign_export",
                        text=T("Экспорт жеста → ghands.ifp"),
                        **inu_icon(safe_icon('EXPORT')))

        # ── Single "Дополнительно" — IK extras + IFP utilities ──
        # Combined collapsible holds all the niche tweakables: ground
        # plane spawning, floor collision tuning, IK control color,
        # plus the rare round-trip and batch-import utilities. One
        # toggle keeps the panel calm during normal animation work.
        extras_row = layout.row(align=True)
        extras_row.alignment = 'LEFT'
        extras_row.prop(
            scene.inu_settings, "gtatools_ik_extras_show",
            text=T("Дополнительно"),
            **inu_icon(('TRIA_DOWN' if scene.inu_settings.gtatools_ik_extras_show
                  else 'TRIA_RIGHT')),
            emboss=False,
        )
        if scene.inu_settings.gtatools_ik_extras_show:
            ebox = layout.box()
            # Single align'd column collapses the inter-row gaps
            # Blender adds between standalone ``box.prop`` calls —
            # the section now reads as one grouped block.
            col = ebox.column(align=True)
            col.operator("gtatools.add_ground_plane",
                         text=T("Пол"), **inu_icon(safe_icon('MESH_PLANE')))
            col.prop(scene.inu_settings, "gtatools_floor_offset",
                     text=T("Коллизия"))
            # Color swatch shrinks to half-width when paired with
            # the size slider on the same row — saves a row and
            # matches the user's "цвет помельче" request.
            row = col.row(align=True)
            row.prop(scene.inu_settings, "gtatools_ik_color", text="")
            row.prop(scene.inu_settings, "gtatools_ik_size", text=T("Размер"))

            # 2×2 eye-icon grid for control-type visibility. Each
            # toggle keeps its short label and flips between
            # HIDE_OFF / HIDE_ON so the icon mirrors the state.
            col.separator()
            grid = col.grid_flow(
                row_major=True, columns=2, align=True)
            grid.prop(
                scene.inu_settings, "gtatools_ik_show_chain",
                text=T("Руки/ноги"),
                **inu_icon(('HIDE_OFF' if scene.inu_settings.gtatools_ik_show_chain
                      else 'HIDE_ON')),
                toggle=True)
            grid.prop(
                scene.inu_settings, "gtatools_ik_show_pole",
                text=T("Локти/колени"),
                **inu_icon(('HIDE_OFF' if scene.inu_settings.gtatools_ik_show_pole
                      else 'HIDE_ON')),
                toggle=True)
            grid.prop(
                scene.inu_settings, "gtatools_ik_show_rot",
                text=T("Голова/торс"),
                **inu_icon(('HIDE_OFF' if scene.inu_settings.gtatools_ik_show_rot
                      else 'HIDE_ON')),
                toggle=True)
            grid.prop(
                scene.inu_settings, "gtatools_ik_show_root",
                text=T("Корень"),
                **inu_icon(('HIDE_OFF' if scene.inu_settings.gtatools_ik_show_root
                      else 'HIDE_ON')),
                toggle=True)

            col.separator()
            col.operator("gtatools.ifp_roundtrip",
                         text=T("Проверить round-trip"),
                         **inu_icon(compat.ICON_CHECK))
            col.operator("gtatools.ifp_batch_import",
                         text=T("Batch папка…"),
                         **inu_icon(safe_icon('FILE_FOLDER')))

        # ── Настройка анимации — sign-fix утилиты с диапазоном кадров
        anim_row = layout.row(align=True)
        anim_row.alignment = 'LEFT'
        anim_row.prop(
            scene.inu_settings, "gtatools_anim_tools_show",
            text=T("Настройка анимации"),
            **inu_icon(('TRIA_DOWN' if scene.inu_settings.gtatools_anim_tools_show
                  else 'TRIA_RIGHT')),
            emboss=False,
        )
        if scene.inu_settings.gtatools_anim_tools_show:
            abox = layout.box()
            acol = abox.column(align=True)
            range_row = acol.row(align=True)
            range_row.prop(scene.inu_settings, "gtatools_anim_fix_start", text=T("Старт"))
            range_row.prop(scene.inu_settings, "gtatools_anim_fix_end", text=T("Конец"))
            acol.operator(
                "gtatools.fix_quat_signs",
                text=T("Исправить кватернионы (sign-flip)"),
                **inu_icon(safe_icon('ORIENTATION_GIMBAL')))
            # Axis row + smooth button. The axis selector is persisted on
            # the scene so it survives panel redraw; the operator copies
            # it on invoke.
            axis_row = acol.row(align=True)
            axis_row.prop(scene.inu_settings, "gtatools_smooth_axis_mode",
                          expand=True)
            smooth_btn = acol.operator(
                "gtatools.smooth_between_anchors",
                text=T("Сгладить между выделенными ключами"),
                **inu_icon(safe_icon('SMOOTHCURVE')))
            smooth_btn.axis_mode = scene.inu_settings.gtatools_smooth_axis_mode

            # ── Зеркало анимации: rest-aware отражение L↔R ────────────
            acol.separator()
            acol.prop(scene.inu_settings, "gtatools_mirror_root_rotation",
                      text=T("Отражать поворот Root"))

            mbox = acol.box()
            mbox.label(text=T("Авто-доворот Root на 180°"),
                       **inu_icon(safe_icon('DRIVER_ROTATIONAL_DIFFERENCE')))
            mbox.prop(scene.inu_settings, "gtatools_mirror_flip_root_180",
                      text=T("Включить"))
            frow = mbox.row()
            frow.enabled = scene.inu_settings.gtatools_mirror_flip_root_180
            frow.prop(scene.inu_settings, "gtatools_mirror_flip_root_axis",
                      text=T("Ось"))
            frow2 = mbox.row()
            frow2.enabled = scene.inu_settings.gtatools_mirror_flip_root_180
            frow2.prop(scene.inu_settings, "gtatools_mirror_flip_root_space",
                       text=T("Пространство"))

            lbox = acol.box()
            lbox.label(text=T("Инверсия Root Location"),
                       **inu_icon(safe_icon('ARROW_LEFTRIGHT')))
            lbox.prop(scene.inu_settings, "gtatools_mirror_invert_root_loc",
                      text=T("Ось"))

            acol.operator(
                "gtatools.mirror_anim",
                text=T("Отзеркалить анимацию (L/R)"),
                **inu_icon(safe_icon('MOD_MIRROR')))



@apply_order
class GTATOOLS_PT_radar_panel(bpy.types.Panel):
    """X Radar Maker — генерация тайлов мини-карты GTA SA"""
    bl_label = "X Radar Maker"
    bl_idname = "GTATOOLS_PT_radar_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('TRACKER')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'radar')

    def draw(self, context):
        layout = self.layout
        scn = context.scene

        layout.prop(scn.inu_settings, "gtatools_radar_output", text=T("Папка"))
        col = layout.column(align=True)
        col.prop(scn.inu_settings, "gtatools_radar_grid", text=T("Сетка"))
        col.prop(scn.inu_settings, "gtatools_radar_size", text=T("Размер"))
        col.prop(scn.inu_settings, "gtatools_radar_height", text=T("Высота"))

        layout.separator()

        # All 5 generation modes live in a single dropdown — the
        # «Индексы» field above stays visible because Specific mode
        # reads it as input.
        layout.prop(scn.inu_settings, "gtatools_radar_specific", text=T("Индексы"))
        layout.menu("GTATOOLS_MT_radar_generate",
                    text=T("Генерировать"), **inu_icon(safe_icon('RENDER_RESULT')))

        layout.separator()
        layout.operator("gtatools.radar_pack_txd", text=T("Упаковать в TXD"), **inu_icon(safe_icon('PACKAGE')))



@apply_order
class GTATOOLS_PT_paths_panel(bpy.types.Panel):
    """Панель Path IO"""
    bl_label = "Пути"
    bl_idname = "GTATOOLS_PT_paths_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('TRACKING')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'paths')

    def draw(self, context):
        layout = self.layout

        # Convert to path button (top)
        obj = context.active_object
        if obj and (obj.type == 'CURVE' or (obj.type == 'MESH' and len(obj.data.polygons) == 0)):
            if obj.get('path_type') != 'path_ipl':
                layout.operator("gtatools.convert_to_path", text=T("Конвертировать в путь"), **inu_icon(safe_icon('CURVE_PATH')))

        # Paths IPL (main — for gta.dat) — fused inside box.
        box1 = layout.box().column(align=True)
        box1.label(text=T("Пути (paths.ipl):"), **inu_icon(safe_icon('TRACKING')))
        row = box1.row(align=True)
        row.operator("gtatools.import_paths_ipl", text=T("Импорт"), **inu_icon(safe_icon('IMPORT')))
        row.operator("gtatools.export_paths_ipl", text=T("Экспорт"), **inu_icon(safe_icon('EXPORT')))
        box1.operator("gtatools.add_path_ipl", text=T("Создать путь"), **inu_icon(safe_icon('ADD')))
        # Roadblocks / Traffic Lights — visible only in Edit Curve on path_ipl
        if (obj and obj.type == 'CURVE' and obj.get('path_type') == 'path_ipl'
                and context.mode == 'EDIT_CURVE'):
            box1.label(text=T("Флаги выделенных точек:"), **inu_icon(safe_icon('CONSTRAINT')))
            op = box1.operator("gtatools.path_node_flag",
                               text=T("Переключить Roadblock"))
            op.action = 'TOGGLE_ROADBLOCK'
            box1.menu("GTATOOLS_MT_path_traffic",
                      text=T("Светофор"), **inu_icon(safe_icon('LIGHT')))

        # Train tracks — fused inside box.
        box2 = layout.box().column(align=True)
        box2.label(text=T("Ж/д пути:"), **inu_icon(safe_icon('CON_FOLLOWPATH')))
        row = box2.row(align=True)
        row.operator("gtatools.import_track", text=T("Импорт"), **inu_icon(safe_icon('IMPORT')))
        row.operator("gtatools.export_track", text=T("Экспорт"), **inu_icon(safe_icon('EXPORT')))
        box2.operator("gtatools.add_track", text=T("Создать ж/д путь"), **inu_icon(safe_icon('ADD')))
        obj = context.active_object
        if (obj and obj.type == 'CURVE' and obj.get('path_type') == 'track'
                and context.mode == 'EDIT_CURVE'):
            box2.operator("gtatools.mark_station", text=T("Станция (вкл/выкл)"), **inu_icon(safe_icon('DECORATE_KEYFRAME')))
        # Station markers refresh — works in object mode too
        if obj and obj.type == 'CURVE' and obj.get('path_type') == 'track':
            box2.operator("gtatools.refresh_station_markers",
                          text=T("Обновить маркеры станций"),
                          **inu_icon(safe_icon('EMPTY_SINGLE_ARROW')))

        # Compiled nodes (NODES*.DAT) — fused inside box.
        box3 = layout.box().column(align=True)
        box3.label(text=T("Скомпилированные (NODES):"), **inu_icon(safe_icon('FILE_CACHE')))
        row = box3.row(align=True)
        row.operator("gtatools.import_nodes", text=T("Импорт"), **inu_icon(safe_icon('IMPORT')))
        row.operator("gtatools.export_nodes", text=T("Экспорт"), **inu_icon(safe_icon('EXPORT')))
        # Visualization toggle — turns Skin modifier off on all path
        # meshes so heavy maps don't lag the viewport. Mesh data
        # (verts + link arrays) survives; only the generated tube
        # geometry is hidden.
        box3.operator("gtatools.toggle_nodes_viz",
                      text=T("Геометрия путей"),
                      **inu_icon(safe_icon('MODIFIER')))

        # ── Curve-based authoring (Kams / ZZPuma style) ──
        # Параллельный workflow к меш-пайплайну: один объект Blender
        # Curve = один lane chain с sapath_* user-props на всю кривую,
        # как в Max + Kams скриптах. Хорош для авторинга новых путей
        # с нуля или для миграции на формат совместимый с ZZPuma.
        box4 = layout.box().column(align=True)
        box4.label(text=T("Curve workflow (Kams / ZZPuma):"),
                   **inu_icon(safe_icon('CURVE_BEZCURVE')))
        cv_row = box4.row(align=True)
        cv_row.operator("gtatools.nodes_to_curves",
                        text=T("Меш → Curves"),
                        **inu_icon(safe_icon('OUTLINER_OB_CURVE')))
        cv_row.operator("gtatools.curves_to_nodes",
                        text=T("Curves → .dat"),
                        **inu_icon(safe_icon('EXPORT')))

        # Selection helpers — pick Ped / Vehicle / All path curves at once.
        sel_row = box4.row(align=True)
        op = sel_row.operator("gtatools.select_path_peds",
                              text=T("Peds"), **inu_icon(safe_icon('OUTLINER_OB_ARMATURE')))
        op = sel_row.operator("gtatools.select_path_vehs",
                              text=T("Vehs"), **inu_icon(safe_icon('AUTO')))
        op = sel_row.operator("gtatools.select_path_all",
                              text=T("Все"), **inu_icon(safe_icon('SELECT_SET')))

        # Quick-edit row: pick / apply / bulk / refresh colours.
        pa_row = box4.row(align=True)
        pa_row.operator("gtatools.pick_path_props",
                        text=T("Pick"), **inu_icon(safe_icon('EYEDROPPER')))
        pa_row.operator("gtatools.apply_path_props",
                        text=T("Apply"), **inu_icon(safe_icon('PASTEDOWN')))
        pa_row.operator("gtatools.bulk_set_path_props",
                        text=T("Bulk"), **inu_icon(safe_icon('MODIFIER')))
        pa_row.operator("gtatools.refresh_path_colors",
                        text=T("Colors"), **inu_icon(safe_icon('COLOR')))

        # Accessories: TrafficLight / RoadBlock / Connector + sync + debug.
        ac_row = box4.row(align=True)
        ac_row.operator("gtatools.add_path_accessory",
                        text=T("+TL/RB/CO"), **inu_icon(safe_icon('LIGHT')))
        ac_row.operator("gtatools.remove_path_accessory",
                        text=T("Удалить"), **inu_icon(safe_icon('REMOVE')))
        ac_row.operator("gtatools.start_accessory_sync",
                        text=T("Sync"), **inu_icon(safe_icon('FILE_REFRESH')))

        dbg_row = box4.row(align=True)
        dbg_row.operator("gtatools.toggle_path_debug",
                        text=T("Node IDs"), **inu_icon(safe_icon('HIDE_OFF'))).target = 'NODES'
        dbg_row.operator("gtatools.toggle_path_debug",
                        text=T("Navi IDs"), **inu_icon(safe_icon('HIDE_OFF'))).target = 'NAVI'
        dbg_row.operator("gtatools.toggle_path_debug",
                        text=T("Off"), **inu_icon(safe_icon('HIDE_ON'))).target = 'OFF'

        # Per-Curve sapath_* properties — surface them when the user
        # has a Curve selected so editing is right next to the op buttons.
        obj_act = context.active_object
        if obj_act is not None and obj_act.type == 'CURVE' and (
                obj_act.get('sapath_type') is not None
                or obj_act.get('sapath_pathid') is not None
                or obj_act.get('sapath_width') is not None):
            attr_box = box4.box().column(align=True)
            attr_box.label(text=f"{T('Атрибуты:')} {obj_act.name}",
                           **inu_icon(safe_icon('PROPERTIES')))
            # Use ID Property edit cells — they auto-sync with the
            # value the export operator reads, no PropertyGroup needed.
            for key in ('sapath_type', 'sapath_width', 'sapath_pathid',
                        'sapath_traffic', 'sapath_spawn', 'sapath_highway',
                        'sapath_roadblock', 'sapath_boats',
                        'sapath_emergency', 'sapath_parking',
                        'sapath_laneright', 'sapath_laneleft'):
                if obj_act.get(key) is not None:
                    attr_box.prop(obj_act, f'["{key}"]',
                                  text=key.replace('sapath_', ''))

        # Info about selected path object
        obj = context.active_object
        if obj and 'path_type' in obj:
            layout.separator()
            box = layout.box()
            pt = obj.get('path_type', '')
            type_names = {
                'track': T("Ж/д путь"),
                'path_ipl': T("Путь IPL"),
                'nodes_vehicle': T("Авто пути"),
                'nodes_ped': T("Пешеходные пути"),
                'nodes_navi': T("Навигационные точки"),
            }
            label = type_names.get(pt, pt)
            if pt == 'path_ipl':
                gt = obj.get('group_type', 1)
                gt_label = T("Авто") if gt == 1 else T("Пешеходный")
                count = sum(len(s.points) for s in obj.data.splines)
                box.label(text=f"{obj.name}: {gt_label} ({count}/12 pts)", **inu_icon(safe_icon('INFO')))
            elif obj.type == 'CURVE':
                count = sum(len(s.points) for s in obj.data.splines)
                stations = obj.get('station_indices', '[]')
                try:
                    num_st = len(ast.literal_eval(stations))
                except Exception:
                    num_st = 0
                box.label(text=f"{obj.name}: {label} ({count} pts, {num_st} stations)", **inu_icon(safe_icon('INFO')))
            elif obj.type == 'MESH':
                box.label(text=f"{obj.name}: {label} ({len(obj.data.vertices)} nodes)", **inu_icon(safe_icon('INFO')))


# ── Footer panel (Docs / Issues / Info) ────────────────────────────
# Sits at the very bottom of the N-sidebar — high bl_order pushes it
# below every tooling panel. Used to live in the main panel header
# (Info) + main body top (Docs/Issues/What's New) but the header was
# getting cluttered and the onboarding row above the actual tooling
# made the panel read "noisy at the top". Moving everything here
# keeps tooling primary on first scroll-position.

@apply_order
class GTATOOLS_PT_footer_panel(bpy.types.Panel):
    """Документация, баг-репорты и What's New — просто строкой внизу панели
    (без вкладки: HIDE_HEADER убирает заголовок, высокий bl_order держит
    внизу под всеми инструментами)."""
    bl_label = "Поддержка"
    bl_idname = "GTATOOLS_PT_footer_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout

        # Docs / Issues / What's New — плоская строка внизу, без вкладки.
        row = layout.column(align=True).row(align=True)
        row.operator("gtatools.open_docs",
                     text=T("Docs"), **inu_icon(safe_icon('HELP')))
        row.operator("gtatools.open_issues",
                     text=T("Issues"), **inu_icon(safe_icon('URL')))
        row.operator("gtatools.whats_new",
                     text="", **inu_icon(safe_icon('SOLO_ON')))


# ── Vertex Paint mode panel gating ─────────────────────────────────
# При входе в Vertex Paint mode от пользователя ожидается только
# работа с цветом — все панели кроме «Освещение» (и его sub-panel'ов)
# скрываются. Sub-panel'ы наследуют видимость от родителя автоматически
# (если parent.poll → False, sub-panel не показывается), поэтому гейтить
# нужно только top-level не-light панели.

def _gate_vertex_paint_panel(cls):
    """Wrap class's poll() to return False when context.mode == 'PAINT_VERTEX'."""
    existing_poll = cls.__dict__.get('poll')

    @classmethod
    def poll(klass, context):
        try:
            if context.mode == 'PAINT_VERTEX':
                return False
        except AttributeError:
            pass
        if existing_poll is not None:
            return existing_poll.__func__(klass, context)
        return True

    cls.poll = poll
    return cls


# ── Texture Bake (карты → текстура; tools/bake/) ───────────────────

class GTATOOLS_UL_bake_layers(bpy.types.UIList):
    """Стек слоёв запекания. Порядок = порядок смешивания (низ = база)."""
    bl_idname = "GTATOOLS_UL_bake_layers"

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_property, index):
        from ..tools.bake import get_map
        md = get_map(item.map_id)
        name = md.label_key if md else item.map_id

        # ОДНА строка: глазик (слева, переключатель) + имя + режим + размер.
        # UIList делает кликабельной только одну строку элемента, поэтому
        # держим всё в одной — тогда вся строка выделяет слой по клику.
        obj = context.active_object
        base = obj.get("inu_bake_base", "") if obj else ""
        _k = getattr(item, 'uid', '') or item.map_id
        img = bpy.data.images.get(f"{base}_{_k}") if base else None
        res = f"{img.size[0]}×{img.size[1]}" if img else "—"

        row = layout.row(align=True)
        row.prop(item, "enabled", text="",
                 **inu_icon(safe_icon('HIDE_OFF' if item.enabled else 'HIDE_ON')))
        # ОДИН «резиновый» блок (имя слева + режим·размер справа) — заполняет
        # всё место, прижимая bake/save к правому краю.
        mid = row.row(align=True)
        mid.active = item.enabled
        mid.label(text=name, translate=False)          # английское имя
        rmeta = mid.row(align=True)
        rmeta.alignment = 'RIGHT'
        rmeta.label(text=f"{item.blend_mode.title()}  ·  {res}", translate=False)
        # bake / Save — ПРЯМЫЕ дети строки с фикс. ui_units_x.
        bcell = row.row(align=True)
        bcell.ui_units_x = 3.0
        bk = bcell.operator("gtatools.bake_run", text="bake")
        bk.only_uid = getattr(item, 'uid', '') or item.map_id
        scell = row.row(align=True)
        scell.ui_units_x = 1.1
        scell.enabled = img is not None
        sop = scell.operator("gtatools.bake_save_map", text="",
                             **inu_icon(safe_icon('FILE_TICK')))
        sop.map_id = item.map_id
        sop.uid = getattr(item, 'uid', '') or item.map_id


class GTATOOLS_PT_uv_root(bpy.types.Panel):
    """Корень вкладки «GTA Tools» в N-панели UV/Image-редактора. Сам ничего
    не рисует — под ним подпанели UV-инструментов (tools/uv_tools.py) через
    bl_parent_id. Texture Bake переехала отсюда в 3D-вьюпорт.
    ВАЖНО: регистрировать РАНЬШЕ детей."""
    bl_label = "GTA Tools"
    bl_idname = "GTATOOLS_PT_uv_root"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "GTA Tools"

    def draw(self, context):
        pass                            # контейнер — содержимое в подпанелях


@apply_order
class GTATOOLS_PT_bake_panel(bpy.types.Panel):
    """Запекание текстур — AO / Diffuse / Bevel / Shadow / Alpha (и др.)
    через Cycles, с опциональным композитом нескольких карт в одну
    текстуру. Свет генерируется подсистемой или берётся со сцены.

    Подпанель главной панели «GTA Tools» в 3D-вьюпорте (bl_parent_id), в зоне
    MODEL между 2DFX и Анимациями. Порядок — через registry.PANELS
    (@apply_order). Запечённую текстуру Blender показывает в Image-редакторе
    автоматически."""
    bl_label = "Texture Bake"
    bl_idname = "GTATOOLS_PT_bake_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('RENDER_STILL')))

    def draw_header_preset(self, context):
        _draw_doc_help(self.layout, 'baking')

    def draw(self, context):
        layout = self.layout
        s = context.scene.inu_settings
        obj = context.active_object

        # ── Размер (плоско, серые числовые поля X/Y) ──
        col = layout.column(align=True)
        col.prop(s, "gtatools_bake_resolution", text=T("Размер"))
        xy = col.row(align=True)
        xy.prop(s, "gtatools_bake_res_x", text="X")
        xy.prop(s, "gtatools_bake_res_y", text="Y")
        col.prop(s, "gtatools_bake_margin", text="Padding")
        col.prop(s, "gtatools_bake_aa", text=T("АА"))
        # Имя текстуры берётся из имени модели — поле убрано намеренно.

        # ── Запекание: выбор режима 3 кнопками (сворачивашка убрана из UI) ──
        box = layout.box()

        # Инфо показываем ТОЛЬКО когда меш реально ВЫДЕЛЕН (active_object
        # сохраняется после снятия выделения — иначе подпись «висит»).
        sel = obj if (obj and obj.type == 'MESH' and obj.select_get()) else None

        mode_row = box.row(align=True)
        mode_row.prop(s, "gtatools_bake_mode", expand=True)

        if s.gtatools_bake_mode == 'UV':
            # UV→UV: источник = рендер-UV (📷), цель = выделенная UV.
            if sel is None:
                box.label(text=T("Выделите модель"), **inu_icon(safe_icon('INFO')))
            elif len(sel.data.uv_layers):
                me = sel.data
                src = next((u.name for u in me.uv_layers if u.active_render), None) or "—"
                tgt = me.uv_layers.active.name if me.uv_layers.active else "—"
                info = box.column(align=True)
                info.scale_y = 0.85
                info.label(text=T("Активная UV: ") + src,
                           **inu_icon(safe_icon('RESTRICT_RENDER_OFF')))
                info.label(text=T("Запекать в UV: ") + tgt,
                           **inu_icon(safe_icon('RENDER_STILL')))
            else:
                box.label(text=T("У объекта нет UV-развёртки"),
                          **inu_icon(safe_icon('ERROR')))
        elif s.gtatools_bake_mode == 'HILOW':  # пара по _hi/_low или DFF/LOD
            if sel is None:
                box.label(text=T("Выделите модель"), **inu_icon(safe_icon('INFO')))
            else:
                from ..tools.bake import find_hilow_pair, HI_SUFFIX, LOW_SUFFIX
                high, low = find_hilow_pair(sel, HI_SUFFIX, LOW_SUFFIX,
                                            dff_lod_fallback=True)
                info = box.column(align=True)
                info.scale_y = 0.85
                info.label(text="High:  " + (high.name if high else "—"),
                           **inu_icon(safe_icon('MOD_MULTIRES')))
                info.label(text="Low:  " + (low.name if low else "—"),
                           **inu_icon(safe_icon('MESH_DATA')))
                # Cage-настройка вынесена в «Дополнительно» (рядом с Max Ray).
        else:  # CAMERA — ортокамера спереди, для billboard/импостеров
            if sel is None:
                box.label(text=T("Выделите модель"), **inu_icon(safe_icon('INFO')))
            else:
                from ..tools.bake import find_hilow_pair, HI_SUFFIX, LOW_SUFFIX
                high, low = find_hilow_pair(sel, HI_SUFFIX, LOW_SUFFIX)
                info = box.column(align=True)
                info.scale_y = 0.85
                if high is not None and low is not None:
                    info.label(text=T("Рендер: ") + high.name,
                               **inu_icon(safe_icon('OUTLINER_OB_CAMERA')))
                    info.label(text=T("На модель: ") + low.name,
                               **inu_icon(safe_icon('MESH_DATA')))
                    # Ракурс берётся из нормали плоскости — выбор не нужен.
                    info.label(text=T("Ракурс: по нормали плоскости"),
                               **inu_icon(safe_icon('NORMALS_FACE')))
                else:
                    info.label(text=T("Рендер: ") + sel.name,
                               **inu_icon(safe_icon('OUTLINER_OB_CAMERA')))
                    info.label(text=T("На модель: ") + sel.name,
                               **inu_icon(safe_icon('MESH_DATA')))
                    # Пары нет — ракурс по мировой оси, выбираем вручную.
                    box.prop(s, "gtatools_bake_cam_axis", text=T("Ракурс"))
                box.prop(s, "gtatools_bake_cam_padding", text=T("Отступ"), slider=True)
                box.prop(s, "gtatools_bake_cam_keep_uv")

        from ..tools.bake import get_map
        # Стек слоёв запекания теперь per-model — берём у активной модели.
        _blo = obj.inu if obj else None
        layers = _blo.gtatools_bake_layers if _blo else []
        idx = _blo.gtatools_bake_layers_index if _blo else 0
        base = obj.get("inu_bake_base", "") if obj else ""

        # ── Создание слоя — ОТДЕЛЬНАЯ форма (не путать с редактором ниже) ──
        # Выбираешь карту → «Добавить». Карта слоя задаётся только тут, при
        # создании; в редакторе выбранного слоя её нет (другой слой = другая
        # карта). Это и убирает прежнюю «кашу», где дропдаун «Карта» в
        # параметрах выглядел как создание, хотя правил выбранный слой.
        addbox = box.box()
        addbox.label(text=T("Добавить слой"), **inu_icon(safe_icon('ADD')))
        arow = addbox.row(align=True)
        arow.prop(s, "gtatools_bake_new_map", text="")
        arow.operator("gtatools.bake_layer_add", text=T("Добавить"),
                      **inu_icon(safe_icon('ADD')))

        # ── Список слоёв ── НЕ UIList (у него свои отступы и нет контроля
        # ширины), а обычные строки: глаз | имя-выбор | режим·размер | bake |
        # save. В обычной строке глаз прижат влево, bake/save вправо,
        # ui_units_x фиксируется надёжно.
        # Рамка списка слева + колонка управления справа (вне рамки), вплотную
        # (align=True — без зазора). Кнопки X / ▲ / ▼ действуют на ВЫБРАННЫЙ
        # слой (index по умолчанию = выбранный).
        list_row = box.row(align=True)
        lbox = list_row.box()
        lcol = lbox.column(align=True)
        # ВАЖНО: ui_units_x на кнопках этого вложенного списка Blender ИГНОРИРУЕТ
        # (кнопка всё равно тянется под текст → колонки разъезжались). Поэтому
        # колонки строим через split() с фиксированными ДОЛЯМИ: доля одинакова в
        # каждой строке → имя/метка/кнопки выровнены, длинные имена ОБРЕЗАЮТСЯ
        # (а не растягивают строку). Доли тянутся с шириной панели, но строки
        # между собой всегда выровнены. Калибровка — factor'ы 0.40 / 0.55 ниже.
        for i, L in enumerate(layers):
            md = get_map(L.map_id)
            nm = md.label_key if md else L.map_id
            img = (bpy.data.images.get(f"{base}_{getattr(L, 'uid', '') or L.map_id}")
                   if base else None)
            r = lcol.row(align=True)
            # Треугольник разворота — показать настройки слоя инлайн под строкой.
            r.prop(L, "expanded", text="", emboss=False,
                   icon=safe_icon('TRIA_DOWN' if L.expanded else 'TRIA_RIGHT'))
            r.prop(L, "enabled", text="",
                   **inu_icon(safe_icon('HIDE_OFF' if L.enabled else 'HIDE_ON')))
            # [имя 60%] | [Bake + save].
            sp_name = r.split(factor=0.60, align=True)
            sp_name.operator("gtatools.bake_select_layer", text=nm,
                             translate=False, depress=(i == idx)).index = i
            acell = sp_name.row(align=True)
            acell.operator("gtatools.bake_run",
                           text="Bake").only_uid = getattr(L, 'uid', '') or L.map_id
            svcell = acell.row(align=True)
            svcell.enabled = img is not None    # сохранить можно только запечённое
            _sv = svcell.operator("gtatools.bake_save_map", text="",
                                  **inu_icon(safe_icon('FILE_TICK')))
            _sv.map_id = L.map_id
            _sv.uid = getattr(L, 'uid', '') or L.map_id
            # Развёрнутые настройки этого слоя (режим/прозрачность/контраст/
            # гамма/размер) — real-time, живой превью обновляется сразу.
            if L.expanded:
                sres = f"{img.size[0]}×{img.size[1]}" if img else "—"
                det = lcol.box().column(align=True)
                if L.map_id == 'ALPHA':
                    # Альфа в RGB-стек не смешивается — задаёт альфа-канал
                    # (прозрачность) результата. Режим/контраст/гамма к ней
                    # не применяются; opacity — множитель силы альфы.
                    det.label(text=T("Задаёт альфа-канал (прозрачность)"),
                              **inu_icon(safe_icon('IMAGE_ALPHA')))
                    # Источник: прозрачность материала или яркость др. карты
                    # (напр. Shadow) + инверсия → шэдоу-декаль (видно тёмное).
                    det.prop(L, "alpha_source", text=T("Источник"))
                    det.prop(L, "alpha_invert", toggle=True,
                             **inu_icon(safe_icon('MOD_MASK')))
                    det.prop(L, "opacity", slider=True, text=T("Сила альфы"))
                else:
                    det.prop(L, "blend_mode")
                    det.prop(L, "opacity", slider=True)
                    det.prop(L, "contrast")
                    det.prop(L, "gamma")
                    # «Обесцветить» — только для Normal Map (убирает синий
                    # tangent-space оттенок при сведении).
                    if L.map_id == 'NORMAL':
                        det.prop(L, "desaturate", toggle=True,
                                 **inu_icon(safe_icon('IMAGE_ALPHA')))
                    # «Декаль» — увести яркость карты (напр.
                    # Shadow) в прозрачность: тёмное видно, светлое убирается.
                    det.separator()
                    det.prop(L, "as_decal", toggle=True,
                             **inu_icon(safe_icon('IMAGE_ALPHA')))
                    if L.as_decal:
                        dc = det.box().column(align=True)
                        dc.prop(L, "decal_threshold", slider=True)
                        dc.prop(L, "decal_softness", slider=True)
                        dc.prop(L, "decal_invert", toggle=True,
                                **inu_icon(safe_icon('MOD_MASK')))
                det.label(text=T("Размер текстуры") + f":  {sres}",
                          **inu_icon(safe_icon('IMAGE_DATA')))
        if not layers:
            lcol.label(text=T("Нет слоёв — добавьте выше"),
                       **inu_icon(safe_icon('INFO')))

        # Колонка управления справа от рамки. Сверху — управление слоями
        # (удалить / ↑ / ↓), ниже — действия по запечённому результату (все
        # иконками, подписи в тултипах). Всё в одном правом столбике.
        side = list_row.column(align=True)
        side.operator("gtatools.bake_layer_remove", text="",
                      **inu_icon(safe_icon('X')))
        side.operator("gtatools.bake_layer_move", text="",
                      **inu_icon(safe_icon('TRIA_UP'))).direction = 'UP'
        side.operator("gtatools.bake_layer_move", text="",
                      **inu_icon(safe_icon('TRIA_DOWN'))).direction = 'DOWN'
        # «Объединить и сохранить» (весь стек; disabled пока не запечено).
        side.operator("gtatools.bake_flatten", text="",
                      **inu_icon(safe_icon('FILE_TICK')))
        if obj and obj.type == 'MESH' and obj.get("inu_bake_base"):
            on = bool(obj.get("inu_bake_preview_on", 0))
            over_on = on and bool(obj.get("inu_bake_overbase_on", 0))
            # Показать/Скрыть текстуру (тоггл, синяя когда включено).
            side.operator(
                "gtatools.bake_preview", text="", depress=on,
                **inu_icon(safe_icon('HIDE_OFF' if on else 'HIDE_ON')))
            # Показать поверх UV1 (тоггл): база(UV1) × запечённое(UV2).
            side.operator("gtatools.bake_show_over_base", text="",
                          depress=over_on, **inu_icon(safe_icon('UV')))
            # «Обновить лайтмап» (пост-обработка) переехала в «Дополнительно»
            # под Интенсивность/Смягчение.

        # (Настройки слоя теперь инлайн в развёрнутой строке списка выше —
        #  отдельный бокс «Выбранный слой» больше не нужен.)


class GTATOOLS_PT_bake_advanced(bpy.types.Panel):
    """Дополнительные настройки запекания текстур: сэмплы, параметры
    Bevel, и per-слой контраст/гамма. Дом для будущих настроек влияния."""
    bl_label = "Дополнительно"
    bl_idname = "GTATOOLS_PT_bake_advanced"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_bake_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = context.scene.inu_settings

        # Настройки фильтруются по ВЫБРАННОЙ карте: не ко всем картам
        # применяются одни и те же параметры (сэмплы — только шумным,
        # свет — светозависимым, Bevel — только Bevel, Cage/Max Ray —
        # только режиму Hi→Low). AA переехал наверх (к Padding).
        from ..tools.bake import get_map
        # Стек слоёв — per-model (у активной модели).
        _o = context.active_object
        _blo = _o.inu if _o else None
        layers = _blo.gtatools_bake_layers if _blo else []
        idx = _blo.gtatools_bake_layers_index if _blo else 0
        md = get_map(layers[idx].map_id) if 0 <= idx < len(layers) else None

        col = layout.column(align=True)
        shown = False
        if md is not None:
            noisy = (md.bake_type == 'AO' or md.needs_light
                     or getattr(md, 'pass_indirect', False))
            # Шумные карты: сэмплы (у LightMap свои пресеты — общий ползунок
            # не показываем) + общий Денойз (для AO / Shadow / Diffuse Lit /
            # Emission GI / LightMap).
            if noisy:
                if md.id != 'LIGHTMAP':
                    col.prop(s, "gtatools_bake_samples")
                col.prop(s, "gtatools_bake_denoise", toggle=True,
                         **inu_icon(safe_icon('SHADERFX')))
                if md.id == 'LIGHTMAP' and s.gtatools_bake_denoise:
                    col.prop(s, "gtatools_bake_lightmap_denoise_passes")
                shown = True
            if md.needs_light:              # Shadow / Diffuse-Lit
                # Свет от сцены (мои лампы) vs внутренний калиброванный SUN.
                col.prop(s, "gtatools_bake_use_scene_light", toggle=True,
                         **inu_icon(safe_icon('LIGHT')))
                # Экспозиция рига актуальна только для внутреннего света.
                if not s.gtatools_bake_use_scene_light:
                    col.prop(s, "gtatools_bake_light_energy_scale")
                shown = True
            if md.id == 'BEVEL':            # только Bevel
                col.prop(s, "gtatools_bake_bevel_size")
                col.prop(s, "gtatools_bake_bevel_samples")
                col.prop(s, "gtatools_bake_selected_faces")
                col.prop(s, "gtatools_bake_selected_edges")
                shown = True
            if md.id == 'LIGHTMAP':         # GI от реального света сцены
                col.prop(s, "gtatools_bake_lightmap_quality")
                if s.gtatools_bake_lightmap_quality == 'CUSTOM':
                    col.prop(s, "gtatools_bake_lightmap_samples")
                col.prop(s, "gtatools_bake_lightmap_light_mode")
                col.separator()
                # Яркость/смягчение + кнопка применить их без пере-запекания.
                col.prop(s, "gtatools_bake_lightmap_intensity", slider=True)
                col.prop(s, "gtatools_bake_lightmap_filter", slider=True)
                col.operator("gtatools.bake_lightmap_postprocess",
                             text=T("Обновить лайтмап"),
                             **inu_icon(safe_icon('SHADERFX')))
                col.separator()
                col.prop(s, "gtatools_bake_lightmap_apply")
                col.operator("gtatools.bake_lightmap_apply",
                             text=T("Применить"),
                             **inu_icon(safe_icon('CHECKMARK')))
                shown = True
        # Учитывать прилайт при запекании (vertex colors × текстура). Актуально
        # для Diffuse в любом режиме, поэтому показываем всегда.
        col.prop(s, "gtatools_bake_use_prelight")
        # Изоляция объекта от сцены: чинит чёрный AO среди карты + ускоряет.
        col.prop(s, "gtatools_bake_isolate")
        # Прозрачный / непрозрачный фон запечённых карт (общая настройка).
        col.prop(s, "gtatools_bake_transparent_bg")
        shown = True
        if s.gtatools_bake_mode == 'HILOW':  # перенос Hi→Low
            col.prop(s, "gtatools_bake_cage_extrusion")
            col.prop(s, "gtatools_bake_max_ray")
            shown = True
        if not shown:
            col.label(text=T("Для выбранной карты доп. настроек нет"),
                      **inu_icon(safe_icon('INFO')))
        # Контраст/гамма слоя живут в боксе «Выбранный слой» (real-time).


# NOTE: GTATOOLS_PT_main_panel — top-level container N-sidebar, у него
# bl_parent_id отсутствует. Все остальные панели (включая light_master)
# — его дети. Гейтить main_panel НЕЛЬЗЯ — спрячется вся вкладка
# аддона. Гейтим только конкретные top-level-в-логике дочерние панели,
# оставляя light_master невредимым.
_VPAINT_HIDDEN_PANELS = [
    GTATOOLS_PT_material_panel,
    GTATOOLS_PT_ide_ipl_panel,
    GTATOOLS_PT_export_panel,
    GTATOOLS_PT_validate_scene,
    GTATOOLS_PT_check_panel,
    GTATOOLS_PT_vehicle_panel,
    GTATOOLS_PT_frame_hierarchy,
    GTATOOLS_PT_2dfx_panel,
    GTATOOLS_PT_bake_panel,
    GTATOOLS_PT_object_ide_ipl_panel,
    GTATOOLS_PT_id_manager_panel,
    GTATOOLS_PT_water_panel,
    GTATOOLS_PT_timecyc_panel,
    GTATOOLS_PT_anim_panel,
    GTATOOLS_PT_frame_hierarchy_anim,
    GTATOOLS_PT_radar_panel,
    GTATOOLS_PT_paths_panel,
    GTATOOLS_PT_footer_panel,
]

# Панели в других модулях добавляем lazy чтобы не плодить
# циркулярные импорты на module-load.
try:
    from ..tools.bitmaps_manager import GTATOOLS_PT_bitmaps_panel as _bp
    _VPAINT_HIDDEN_PANELS.append(_bp)
except Exception:
    pass

for _cls in _VPAINT_HIDDEN_PANELS:
    _gate_vertex_paint_panel(_cls)


# NOTE: panels are registered from the master class list in __init__.py — NOT
# from this module. A local `classes` tuple used to live here but it was dead
# (nothing imported it) and drifted out of sync (missing grass_panel etc.), so
# it was removed to avoid the "edit this to register a panel" trap. Add new
# panels to the registration list in __init__.py.
