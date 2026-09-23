# INU_tools.ui.geo_panels — вкладка «GTA Geo» в N-панели вьюпорта.
#
# Процедурная генерация окружения из готовых кусков: тротуар с бордюром
# и травой (ops/geo_curb_ops.py), дальше — дорога и модульные дома.
#
# Отдельная вкладка, а не подпанель GTA Tools: тут другой режим работы.
# GTA Tools — это импорт/экспорт готовых моделей, а здесь модель ещё
# только строится, и лезть сюда во время работы с DFF незачем.
#
# Корневые панели вкладок не входят в ui/registry.py — реестр раздаёт
# bl_order подпанелям внутри GTA Tools, а у корня своя вкладка (тот же
# приём, что в ui/library_panel.py).

import bpy

from .. import T
from ..tools import draw_cache
from ..tools.compat import safe_icon, inu_icon


class GTATOOLS_PT_geo_panel(bpy.types.Panel):
    """Корень вкладки «GTA Geo» — процедурная застройка."""
    bl_label = "GTA Geo"
    bl_idname = "GTATOOLS_PT_geo_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GTA Geo'

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text=T("Процедурная застройка"),
                  **inu_icon(safe_icon('MOD_BUILD')))
        col.label(text=T("из готовых кусков"))


class GTATOOLS_PT_geo_curb_panel(bpy.types.Panel):
    """Тротуар, бордюр и трава на гео-нодах: участок задаётся плоским
    мешем, трава — материалом на гранях, спуск к дороге — острыми
    рёбрами."""
    bl_label = "Тротуар и бордюр"
    bl_idname = "GTATOOLS_PT_geo_curb_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_geo_panel"

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('MOD_BEVEL')))

    def draw(self, context):
        from ..ops import geo_curb_ops as curb

        layout = self.layout
        ng = bpy.data.node_groups.get(curb.GROUP_NAME)

        # Главное действие — одной широкой кнопкой сверху. Рядом
        # пересборка: она нужна раз в год, поэтому только иконкой.
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("gtatools.geo_curb_apply",
                     text=T("Тротуар и бордюр"),
                     **inu_icon(safe_icon('MOD_BEVEL'))).force = False
        rebuild = row.row(align=True)
        rebuild.scale_y = 1.3
        rebuild.enabled = ng is not None
        rebuild.operator("gtatools.geo_curb_apply", text="",
                         **inu_icon(safe_icon('FILE_REFRESH'))).force = True

        if ng is None:
            layout.label(text=T("Выдели участок и нажми кнопку"),
                         **inu_icon(safe_icon('INFO')))
            return

        # Счёт по объектам файла — не бесплатный, поэтому через memo:
        # пересчитывается, только когда меняется число объектов.
        used = draw_cache.memo(
            ('curb_users', len(bpy.data.objects)),
            lambda: len(curb.group_users(ng)))
        layout.label(text=f"{T('Тротуаров в сцене:')} {used}",
                     **inu_icon(safe_icon('INFO')))

        obj = context.active_object
        if obj is not None and obj.type == 'MESH' and curb.has_modifier(obj, ng):
            box = layout.box()
            box.label(text=T("Настройки — в модификаторе «INU Curb»"),
                      **inu_icon(safe_icon('MODIFIER')))
            if not obj.data.polygons:
                box.label(text=T("У меша нет граней"),
                          **inu_icon(safe_icon('ERROR')))
            layout.operator("gtatools.geo_curb_remove",
                            text=T("Снять тротуар"),
                            **inu_icon(safe_icon('X')))


class GTATOOLS_PT_geo_curb_help(bpy.types.Panel):
    """Короткая памятка по тротуару. Полный текст лежит рамкой в самой
    нод-группе и текстовым блоком в Text Editor — здесь только шаги,
    без которых ничего не появится."""
    bl_label = "Как пользоваться"
    bl_idname = "GTATOOLS_PT_geo_curb_help"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_geo_curb_panel"
    bl_options = {'DEFAULT_CLOSED'}

    # Короткие строки: Blender не переносит текст в label, а N-панель
    # узкая — длинная строка просто обрежется.
    _STEPS = (
        ('MESH_GRID', "1. Участок — плоский меш с гранями"),
        ('MATERIAL', "2. Трава — грани с материалом травы"),
        ('EDGESEL', "3. Спуск к дороге — Mark Sharp"),
        ('GROUP_VERTEX', "4. Круглые углы — curb_round_1..3"),
        ('EXPORT', "5. Экспорт — Триангулировать + Convert"),
    )

    def draw(self, context):
        col = self.layout.column(align=True)
        for icon, text in self._STEPS:
            col.label(text=T(text), **inu_icon(safe_icon(icon)))
        col.separator()
        col.label(text=T("Весь участок — тротуар по умолчанию"),
                  **inu_icon(safe_icon('INFO')))
        col.label(text=T("Бордюр встаёт только вокруг травы"),
                  **inu_icon(safe_icon('INFO')))


# ── Здания (Auto-Building) ───────────────────────────────────────
#
# Настройки берутся из карты в data/autobuilding_ui.py — она собрана
# разбором исходника Auto-Building, поэтому идентификаторы сокетов там
# заведомо верные. Панель просто рисует эту карту по активному объекту.

def _draw_rows(layout, mod, rows):
    """Нарисовать строки карты по модификатору.

    Поля, которых в модификаторе нет, пропускаем молча: у другой версии
    Auto-Building набор сокетов свой, а исключение внутри draw() убивает
    отрисовку всей панели, а не одной строки."""
    for kind, ident, data, label in rows:
        if ident not in mod:
            continue
        if kind == 'search':
            layout.prop_search(mod, '["%s"]' % ident, bpy.data, data,
                               text=label, translate=False)
        else:
            layout.prop(mod, '["%s"]' % ident, text=label, translate=False)


def _section(layout, settings, index, title, mod, rows):
    """Сворачиваемый блок: заголовок-переключатель и поля под ним."""
    box = layout.box()
    head = box.row(align=True)
    opened = settings.gtatools_ab_open[index]
    head.prop(settings, "gtatools_ab_open", index=index, text="",
              icon='DISCLOSURE_TRI_DOWN' if opened else 'DISCLOSURE_TRI_RIGHT',
              emboss=False)
    head.label(text=title, translate=False)
    if opened:
        _draw_rows(box.column(align=True), mod, rows)


def _building_modifier(context):
    from ..data.autobuilding_ui import MODIFIER
    obj = context.active_object
    if obj is None or obj.type != 'MESH':
        return None
    return obj.modifiers.get(MODIFIER)


class _ABPanel:
    """Общее для подпанелей Auto-Building: рисуются, только когда на
    активном объекте есть их модификатор."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_geo_building_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _building_modifier(context) is not None


class GTATOOLS_PT_geo_building_panel(bpy.types.Panel):
    """Здания на базе Auto-Building: генерацию делает их система, наша
    часть — куски из домов GTA SA и сборка результата в меш под экспорт."""
    bl_label = "Здания"
    bl_idname = "GTATOOLS_PT_geo_building_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "GTATOOLS_PT_geo_panel"

    def draw_header(self, context):
        self.layout.label(text="", **inu_icon(safe_icon('HOME')))

    def draw(self, context):
        from ..ops.geo_building_ops import start_file
        from ..data.autobuilding_ui import REALIZE

        settings = context.scene.inu_settings
        layout = self.layout
        ready = bool(start_file(settings))

        layout.prop(settings, "gtatools_building_assets", text="")
        if not ready:
            layout.label(text=T("Укажи папку assets Auto-Building"),
                         **inu_icon(safe_icon('ERROR')))
            return

        add = layout.column(align=True)
        add.scale_y = 1.2
        add.operator("gtatools.building_new", text=T("Новое здание"),
                     **inu_icon(safe_icon('HOME')))
        row = add.row(align=True)
        row.operator("gtatools.building_example", text=T("Примеры"),
                     **inu_icon(safe_icon('ASSET_MANAGER')))
        row.operator("gtatools.building_base", text=T("Auto-Base"),
                     **inu_icon(safe_icon('MESH_PLANE')))

        mod = _building_modifier(context)
        if mod is None:
            layout.label(text=T("Выдели здание"),
                         **inu_icon(safe_icon('INFO')))
            return

        if REALIZE in mod:
            layout.prop(mod, '["%s"]' % REALIZE, text=T("Реальная геометрия"))
        layout.operator("gtatools.building_to_mesh", text=T("Собрать в меш"),
                        **inu_icon(safe_icon('MESH_DATA')))


class GTATOOLS_PT_ab_walls(_ABPanel, bpy.types.Panel):
    """Стены A–H и материалы пустых стен."""
    bl_label = "Стены"
    bl_idname = "GTATOOLS_PT_ab_walls"

    def draw(self, context):
        from ..data import autobuilding_ui as ab

        settings = context.scene.inu_settings
        mod = _building_modifier(context)
        layout = self.layout

        for socket, rows in ((ab.EMPTY_A, ab.EMPTY_A_ROWS),
                             (ab.EMPTY_B, ab.EMPTY_B_ROWS)):
            ident, data, label = socket
            if ident not in mod:
                continue
            box = layout.box()
            box.prop_search(mod, '["%s"]' % ident, bpy.data, data,
                            text=label, translate=False)
            _draw_rows(box.column(align=True), mod, rows)

        for index, (letter, collection, rows) in enumerate(ab.WALLS):
            if collection not in mod:
                continue
            box = layout.box()
            head = box.row(align=True)
            opened = settings.gtatools_ab_wall_open[index]
            head.prop(settings, "gtatools_ab_wall_open", index=index, text="",
                      icon=('DISCLOSURE_TRI_DOWN' if opened
                            else 'DISCLOSURE_TRI_RIGHT'), emboss=False)
            head.prop_search(mod, '["%s"]' % collection, bpy.data,
                             'collections', text="Wall %s" % letter,
                             translate=False)
            if opened:
                _draw_rows(box.column(align=True), mod, rows)


class _ABGroupPanel(_ABPanel):
    """Подпанель, собранная из нескольких разделов карты."""
    _keys = ()

    def draw(self, context):
        from ..data import autobuilding_ui as ab

        settings = context.scene.inu_settings
        mod = _building_modifier(context)
        for index, (key, title, rows) in enumerate(ab.SECTIONS):
            if key in self._keys:
                _section(self.layout, settings, index, title, mod, rows)


class GTATOOLS_PT_ab_roof(_ABGroupPanel, bpy.types.Panel):
    """Крыша: материалы, плоская, скатная, модульная, украшения."""
    bl_label = "Крыша"
    bl_idname = "GTATOOLS_PT_ab_roof"
    _keys = ('roof_mat', 'flat', 'slope', 'modular', 'dressing')


class GTATOOLS_PT_ab_creases(_ABGroupPanel, bpy.types.Panel):
    """Заломы: карнизы и профили по горизонтальным, вертикальным и
    верхним рёбрам."""
    bl_label = "Заломы"
    bl_idname = "GTATOOLS_PT_ab_creases"
    _keys = ('hor_a', 'hor_b', 'ver_a', 'ver_b', 'top')


class GTATOOLS_PT_ab_extra(_ABGroupPanel, bpy.types.Panel):
    """Фундамент, опоры, украшения фасада и интерьер."""
    bl_label = "Дополнительно"
    bl_idname = "GTATOOLS_PT_ab_extra"
    _keys = ('foundation', 'supports', 'facade', 'interior')


class GTATOOLS_PT_ab_config(_ABGroupPanel, bpy.types.Panel):
    """Материалы разметки ID_* и общие настройки."""
    bl_label = "Разметка"
    bl_idname = "GTATOOLS_PT_ab_config"
    _keys = ('config',)
