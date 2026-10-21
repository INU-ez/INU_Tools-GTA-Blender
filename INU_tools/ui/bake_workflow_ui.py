"""Shared compact controls for bake provenance, masks and stack reuse."""
import json
import bpy
from .. import T


def _foldout(layout, settings, field, label):
    expanded = getattr(settings, field)
    layout.prop(settings, field, text=T(label), toggle=True,
                icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT')
    return layout.box().column(align=True) if expanded else None


def draw_workflow(layout, context, obj):
    col = _foldout(layout, context.scene.inu_settings,
                   'gtatools_bake_workflow_expanded', 'Инструменты запекания')
    if col is None:
        return
    col.operator('gtatools.bake_diagnose', text=T('Проверить запекание'), icon='VIEWZOOM')
    if obj:
        try:
            report = json.loads(obj.get('inu_bake_diagnostics', '{}'))
        except ValueError:
            report = {}
        labels = [('degenerate', T('Вырожденные UV')), ('overlap', T('Частичные наложения')),
                  ('conflict', T('Конфликт выделения в общих UV')),
                  ('normal_pixels', T('Некорректные пиксели нормалей')),
                  ('outside', T('UV за пределами 0–1')), ('stacked', T('Совпадающие UV-копии'))]
        for key, label in labels:
            if report.get(key):
                row = col.row(align=True)
                row.alert = key in {'degenerate', 'conflict', 'normal_pixels'}
                row.operator('gtatools.bake_diagnostic_select', text=f'{label}: {len(report[key])}',
                             icon='RESTRICT_SELECT_OFF').category = key
        if report and not report.get('complete', True):
            col.label(text=T('Лимит проверки: проверены не все наложения'), icon='INFO')
    row = col.row(align=True)
    row.operator('gtatools.bake_preset_save', text=T('Сохранить пресет'), icon='EXPORT')
    row.operator('gtatools.bake_preset_load', text=T('Загрузить пресет'), icon='IMPORT')
    col.operator('gtatools.bake_stack_copy', text=T('Слои на выделенные'), icon='COPYDOWN')
    col.prop(context.scene.inu_settings, 'gtatools_bake_batch_only_stale')
    col.operator('gtatools.bake_batch', text=T('Запечь выделенные модели'),
                 icon='RENDER_STILL').only_stale = context.scene.inu_settings.gtatools_bake_batch_only_stale


def layer_status(context, obj, layer, image):
    from ..tools.bake.bake_workflow import bake_stamp, stamp_status
    if layer.map_id == 'PAINT':
        return 'READY'
    uv = obj.data.uv_layers.active
    return stamp_status(image, bake_stamp(obj, context.scene.inu_settings, layer,
                                         uv.name if uv else '', cached=True))


def draw_status(layout, context, obj, layer, image, state=None):
    state = state or layer_status(context, obj, layer, image)
    messages = {'STALE': T('Нужно перепечь: основа изменилась'),
                'MISSING': T('Слой ещё не запечён'),
                'UNKNOWN': T('Состояние старой запечки неизвестно')}
    if state in messages:
        row = layout.row()
        row.alert = state == 'STALE'
        row.label(text=messages[state], icon='ERROR' if state == 'STALE' else 'INFO')


def draw_surface_controls(layout, layer):
    for i, mask in enumerate(layer.masks):
        box = layout.box().column(align=True)
        row = box.row(align=True)
        row.prop(mask, 'enabled', text='')
        row.prop(mask, 'basis', text='')
        op = row.operator('gtatools.bake_mask_edit', text='', icon='X')
        op.uid, op.index = layer.uid or layer.map_id, i
        box.prop(mask, 'operation')
        box.prop(mask, 'strength', slider=True)
        box.prop(mask, 'invert')
    layout.operator('gtatools.bake_mask_edit', text=T('Добавить маску'), icon='ADD').uid = layer.uid or layer.map_id
    if layer.effect_basis == 'DIRECTION' or any(m.basis == 'DIRECTION' for m in layer.masks):
        col = layout.box().column(align=True)
        col.prop(layer, 'direction_mode')
        col.prop(layer, 'direction')
        col.prop(layer, 'direction_threshold', slider=True)
        col.prop(layer, 'direction_softness', slider=True)
        if layer.direction_mode == 'STREAK':
            col.prop(layer, 'streak_length')
        col.label(text=T('Направление в локальных осях модели'), icon='INFO')
    if layer.use_color:
        layout.prop(layer, 'ramp_low', slider=True)
        layout.prop(layer, 'ramp_high', slider=True)
        layout.prop(layer, 'ramp_smooth')
    # Additional mask inputs use the same raw images as the primary basis.
    required = {m.basis for m in layer.masks if m.enabled}
    obj = layer.id_data
    base = obj.get('inu_bake_base', '')
    layers = obj.inu.gtatools_bake_layers
    for mid in sorted(required - {'PATTERN', 'DIRECTION', 'BEVEL'}):
        if not any(l.map_id == mid and bpy.data.images.get(f'{base}_{l.uid or l.map_id}') for l in layers):
            layout.label(text=T('Не запечена основа: {0}').format(mid), icon='ERROR')


def draw_game_preview(layout, settings, obj):
    if not obj or not obj.get('inu_bake_base'):
        return
    col = _foldout(layout, settings, 'gtatools_bake_game_expanded', 'Проверка игровой текстуры')
    if col is None:
        return
    col.prop(settings, 'gtatools_bake_game_size')
    col.prop(settings, 'gtatools_bake_game_mip')
    col.prop(settings, 'gtatools_bake_game_alpha')
    col.operator('gtatools.bake_game_preview', text=T('Показать результат'), icon='IMAGE_DATA')
    col.operator('gtatools.bake_game_preview', text=T('Исходные материалы'), icon='MATERIAL').original = True
    col.label(text=T('Уменьшение для проверки; сжатие DXT не моделируется'), icon='INFO')
