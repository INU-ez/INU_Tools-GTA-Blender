# INU_tools.ops.timecyc_ops — timecyc.dat: импорт, живое превью, экспорт.
#
# Разобранный файл живёт в модульном кэше, а не в сцене: 23 погоды × 8
# срезов × 52 значения — это ~9500 чисел, класть их в PropertyGroup
# накладно и незачем. В сцене хранится только путь; кэш поднимается
# лениво (в том числе после перезапуска Blender) при первом обращении.
#
# Правится ВСЕГДА конкретный срез (их 8 — как в файле), а слайдер часа
# лишь показывает интерполяцию между срезами, как это делает игра.
# Поэтому поля панели пишутся в срез из ``props.slot``, а сцена
# перестраивается по ``props.hour``.

import os

import bpy
from bpy.props import StringProperty, BoolProperty

from .. import T
from ..core import timecyc as tc
from ..tools import timecyc_screen, timecyc_world


# ── Кэш разобранного файла ──────────────────────────────────────────

# 'failed' — путь, на котором parse уже спотыкался. Без него битый файл
# печатал бы ошибку на КАЖДУЮ перерисовку панели: её draw() дёргает
# get_cyc().
_CACHE = {'path': '', 'cyc': None, 'failed': ''}

# Пока панель заливает свои поля из кэша, update-колбэки полей должны
# молчать — иначе каждая запись летит обратно в срез и метит его dirty.
_SYNCING = False


def get_cyc(context=None, load=True):
    """Разобранный timecyc для текущего пути. None, если нечего грузить."""
    context = context or bpy.context
    props = getattr(context.scene, 'inu_settings', None)
    if props is None:
        return None
    props = props.gtatools_timecyc
    path = bpy.path.abspath(props.path) if props.path else ''

    if _CACHE['cyc'] is not None and _CACHE['path'] == path:
        return _CACHE['cyc']
    if not load or not path or not os.path.isfile(path):
        return None
    if _CACHE['failed'] == path:
        return None
    try:
        cyc = tc.parse(path)
    except Exception as exc:
        _CACHE['failed'] = path
        print("[INU timecyc] не удалось разобрать %s: %s" % (path, exc))
        return None
    _CACHE['path'] = path
    _CACHE['cyc'] = cyc
    _CACHE['failed'] = ''
    return cyc


def drop_cache():
    _CACHE['path'] = ''
    _CACHE['cyc'] = None
    _CACHE['failed'] = ''


# ── Раскладка полей панели ↔ полей файла ────────────────────────────

# (ключ в файле, имя свойства). Цвета — три байта; у RGBA/ARGB альфа
# живёт отдельным свойством, потому что COLOR-свотч в Blender трёхканальный.
_COLOR_FIELDS = (
    ('amb',           'f_amb'),
    ('amb_obj',       'f_amb_obj'),
    ('amb_bl',        'f_amb_bl'),         # VC
    ('amb_obj_bl',    'f_amb_obj_bl'),     # VC
    ('dir',           'f_dir'),
    ('sky_top',       'f_sky_top'),
    ('sky_bot',       'f_sky_bot'),
    ('sun_core',      'f_sun_core'),
    ('sun_corona',    'f_sun_corona'),
    ('low_clouds',    'f_low_clouds'),
    ('top_clouds',    'f_top_clouds'),     # III / VC
    ('bottom_clouds', 'f_bottom_clouds'),
    ('blur',          'f_blur'),           # III (RGBA) / VC (RGB)
)

# (ключ, свойство цвета, свойство альфы, индекс альфы в значениях файла).
# Поле короче четырёх чисел (blur у VC) здесь пропускается — его RGB уже
# залил проход по _COLOR_FIELDS.
_ALPHA_FIELDS = (
    ('water',   'f_water',   'f_water_a',   3),   # RGBA — альфа последняя
    ('blur',    'f_blur',    'f_blur_a',    3),   # III: RGBA
    ('postfx1', 'f_postfx1', 'f_postfx1_a', 0),   # ARGB — альфа первая
    ('postfx2', 'f_postfx2', 'f_postfx2_a', 0),
)

# Поля, объявленные IntProperty: Blender 5.x отказывается принимать в
# них float ("expected an int type, not float"), так что округляем при
# заливке в панель. В файле все они и так целые.
_INT_PROPS = frozenset((
    'f_shadow', 'f_light_shad', 'f_pole_shad',
    'f_cloud_alpha', 'f_highlight_min', 'f_water_fog',
))

_NUM_FIELDS = (
    ('sun_size',        'f_sun_size'),
    ('spr_size',        'f_spr_size'),
    ('spr_bright',      'f_spr_bright'),
    ('shadow',          'f_shadow'),
    ('light_shad',      'f_light_shad'),
    ('pole_shad',       'f_pole_shad'),
    ('far_clip',        'f_far_clip'),
    ('fog_start',       'f_fog_start'),
    ('light_on_ground', 'f_light_on_ground'),
    ('cloud_alpha',     'f_cloud_alpha'),
    ('highlight_min',   'f_highlight_min'),
    ('water_fog',       'f_water_fog'),
    ('dir_mult',        'f_dir_mult'),
)


def _rgb_offset(alpha_index):
    """С какого индекса в значениях файла начинается RGB: у ARGB альфа
    занимает нулевую позицию, у RGBA — последнюю."""
    return 1 if alpha_index == 0 else 0


def props_of(context):
    return context.scene.inu_settings.gtatools_timecyc


def weather_index(props, cyc=None):
    """Индекс выбранной погоды — по её имени.

    Имя лежит обычной строкой в сцене, поэтому «невыбранного» состояния
    тут просто не бывает: не нашли — берём первую погоду, ровно ту, что
    показывает панель."""
    if cyc is None or not cyc.weathers:
        return 0
    name = (props.weather_name or "").strip()
    if name:
        for i, weather in enumerate(cyc.weathers):
            if weather.name == name:
                return i
    return 0


def sync_weather_list(props, cyc):
    """Перезалить список погод в сцену — он и есть источник выпадашки."""
    props.weathers.clear()
    if cyc is None:
        return
    for weather in cyc.weathers:
        props.weathers.add().name = weather.name
    names = [w.name for w in cyc.weathers]
    if props.weather_name not in names:
        props.weather_name = names[0] if names else ""


def slot_prop_name(cyc):
    """Какое из двух свойств-срезов относится к файлу: 8 срезов SA живут
    в ``slot``, 24 почасовых III/VC — в ``slot_hourly``."""
    return 'slot_hourly' if cyc is not None and len(cyc.slot_hours) == 24 else 'slot'


def slot_index(props, cyc):
    try:
        return int(getattr(props, slot_prop_name(cyc)))
    except (ValueError, TypeError):
        return 0


def set_slot_index(props, cyc, idx):
    setattr(props, slot_prop_name(cyc), str(int(idx)))


def slot_hours(cyc):
    return cyc.slot_hours if cyc is not None else tc.SLOT_HOURS


def current_slot(context=None, cyc=None):
    context = context or bpy.context
    cyc = cyc or get_cyc(context)
    if cyc is None:
        return None
    props = context.scene.inu_settings.gtatools_timecyc
    return cyc.slot(weather_index(props, cyc), slot_index(props, cyc))


def sync_props_from_slot(context=None):
    """Кэш → поля панели. Молча ничего не делает, если файл не загружен."""
    global _SYNCING
    context = context or bpy.context
    slot = current_slot(context)
    if slot is None:
        return False
    props = context.scene.inu_settings.gtatools_timecyc

    _SYNCING = True
    try:
        for key, prop_name in _COLOR_FIELDS:
            vals = slot.values.get(key)
            if vals is None:
                continue
            setattr(props, prop_name,
                    tuple(tc.byte_to_linear(v) for v in vals[:3]))

        for key, color_prop, alpha_prop, alpha_idx in _ALPHA_FIELDS:
            vals = slot.values.get(key)
            if vals is None or len(vals) < 4:
                continue
            off = _rgb_offset(alpha_idx)
            setattr(props, color_prop,
                    tuple(tc.byte_to_linear(v) for v in vals[off:off + 3]))
            setattr(props, alpha_prop, min(max(vals[alpha_idx] / 255.0, 0.0), 1.0))

        for key, prop_name in _NUM_FIELDS:
            vals = slot.values.get(key)
            if vals is None:
                continue
            if prop_name in _INT_PROPS:
                setattr(props, prop_name, int(round(vals[0])))
            else:
                setattr(props, prop_name, float(vals[0]))
    finally:
        _SYNCING = False
    return True


def push_props_to_slot(context=None):
    """Поля панели → кэш. Возвращает True, если срез действительно
    изменился (dirty ставит сам TimecycSlot.set)."""
    context = context or bpy.context
    slot = current_slot(context)
    if slot is None:
        return False
    props = context.scene.inu_settings.gtatools_timecyc
    was_dirty = slot.dirty

    for key, prop_name in _COLOR_FIELDS:
        if key not in slot.values:
            continue
        slot.set(key, [tc.linear_to_byte(c) for c in getattr(props, prop_name)])

    for key, color_prop, alpha_prop, alpha_idx in _ALPHA_FIELDS:
        vals = slot.values.get(key)
        if vals is None or len(vals) < 4:
            continue
        off = _rgb_offset(alpha_idx)
        new = list(vals)
        rgb = [tc.linear_to_byte(c) for c in getattr(props, color_prop)]
        new[off:off + 3] = rgb
        new[alpha_idx] = round(min(max(getattr(props, alpha_prop), 0.0), 1.0) * 255.0)
        slot.set(key, new)

    for key, prop_name in _NUM_FIELDS:
        if key not in slot.values:
            continue
        slot.set(key, float(getattr(props, prop_name)))

    return slot.dirty and not was_dirty


# ── Применение к сцене ──────────────────────────────────────────────

def preview_opts(props):
    return {
        'sky_strength':         props.sky_strength,
        'ambient_strength':     props.ambient_strength,
        'ambient_split':        props.ambient_split,
        'ambient_from_objects': props.ambient_from_objects,
        'gradient':             props.gradient,
        'game_look':            props.game_look,
        'water':                props.use_water,
        'far_clip':             props.use_far_clip,
    }


def apply_to_scene(context=None, force=False):
    """Пересобрать освещение под текущие погоду/час.

    Живое превью привязано к мастер-состоянию: пока тайм-цикл ВКЛючён
    (props.enabled), любое изменение часа/погоды/опций пересобирает сцену
    автоматически. Выключен — молчим (если не force). Отдельного тумблера
    «Живое превью» больше нет — оно всегда работает при активном цикле."""
    context = context or bpy.context
    props = context.scene.inu_settings.gtatools_timecyc
    # Live bridge: mirror the edited slice into ariane. Done BEFORE the preview gate so
    # timecycle edits still reach ariane even when Blender's own preview is off. The push
    # itself no-ops unless the watcher + ariane_sync_time are on and Blender is focused.
    try:
        from . import ariane_bridge as _ab
        _ab.push_timecyc_if_live(context)
    except Exception:                                      # noqa: BLE001
        pass
    if not (props.enabled or force):
        return False
    cyc = get_cyc(context)
    if cyc is None:
        return False
    values = cyc.interpolate(weather_index(props, cyc), props.hour)
    if not values:
        return False
    # Каждая стадия превью — отдельно и под защитой: сломавшийся мир,
    # материал или композитор не должен утаскивать за собой ни импорт
    # файла, ни остальные стадии. Ошибку печатаем в системную консоль.
    for stage, fn in (
            ('world', lambda: timecyc_world.apply(
                context, values, props.hour, _world_opts(props, values))),
            ('materials', lambda: apply_material_values(
                props, values, context.scene)),
            ('screen', lambda: apply_screen_values(context, props, values))):
        try:
            fn()
        except Exception as exc:                       # noqa: BLE001
            print("[INU timecyc] стадия %s: %s" % (stage, exc))
            import traceback
            traceback.print_exc()
    return True


def apply_screen_values(context, props, values):
    """Туман и цветофильтр — экранные стадии в композиторе.

    В игре обе операции идут по готовому кадру, поэтому и здесь они
    считаются один раз на кадр, а не размазаны по материалам: так под
    них попадают и объекты, где превью прилайта не включено."""
    scene = context.scene
    if not (props.use_fog or props.use_postfx):
        if scene.get('inu_tc_comp_version') is not None:
            timecyc_screen.teardown(scene, context)
        return False

    timecyc_screen.ensure_tree(scene)

    fog = None
    if props.use_fog:
        sky_bot = values.get('sky_bot') or [0.0, 0.0, 0.0]
        start = max(float((values.get('fog_start') or [0.0])[0]), 0.0)
        end = max(float((values.get('far_clip') or [800.0])[0]), 1.0)
        scale = props.fog_distance
        fog = ([tc.byte_to_linear(c) for c in sky_bot[:3]],
               start * scale, end * scale, props.fog_curve)

    gain = tc.postfx_gain(values) if props.use_postfx else (1.0, 1.0, 1.0)
    # Порог неба — вплотную к клипу: всё, что ближе, ещё геометрия и
    # обязано получить туман; глубина фона равна клипу и отсекается.
    # Глубина фона равна clip end вьюпорта, поэтому порог берём от
    # ФАКТИЧЕСКОГО клипа (мир его уже выставил), а не от расчётного:
    # пользователь мог поставить свой, и тогда небо снова заливалось бы.
    timecyc_screen.apply_values(
        scene, fog=fog, postfx_gain=gain,
        sky_threshold=sky_threshold(context, props, values))
    return True


def fog_end_distance(props, values):
    """Конец тумана в метрах."""
    end = max(float((values.get('far_clip') or [800.0])[0]), 1.0)
    return end * props.fog_distance


def viewport_clip(props, values):
    """Дальность отсечения вьюпорта, которую ставит превью.

    От неё же считается порог «дальше этого — небо»: небо — это не
    «далеко», а «геометрии тут нет вовсе», то есть глубина фона. Пока
    порог стоял на дальности ТУМАНА, дальняя геометрия за ним теряла
    туман и торчала чёткой — ровно как обрезанный край карты."""
    far = max(float((values.get('far_clip') or [800.0])[0]), 10.0)
    if props.use_fog:
        far = max(far, fog_end_distance(props, values) * 1.6)
    return far * 1.5


def _actual_clip(scene, props, values):
    """Реальный клип вьюпорта, который ставит превью: не только дальность
    тумана (viewport_clip), но и габариты сцены. Должен 1:1 совпадать с тем,
    что пишет timecyc_world.apply() (max(clip, scene_extent*2.5)) — иначе
    порог неба и клип разъезжаются и туман «обрезается» на большой карте."""
    from ..tools.timecyc_world import scene_extent
    return max(viewport_clip(props, values), scene_extent(scene) * 2.5)


def sky_threshold(context, props, values):
    """Глубина, дальше которой начинается небо (туман туда не кладём).

    Ключ: глубина ФОНА в композиторе = clip end вьюпорта, а у любой
    геометрии глубина МЕНЬШЕ clip end. Поэтому порог = 0.98·clip_end:
      • небо (на clip_end) чуть ДАЛЬШЕ порога → без тумана → градиент
        зенит↔горизонт цел;
      • ВСЯ геометрия (ближе clip_end) → в тумане → ничего не «обрезается».
    Так порог и клип не разъезжаются при любом значении клипа (хоть 2000,
    хоть 80 000 — юзер мог задать сам). Клип мир уже выставил под габариты
    сцены (max(clip, scene_extent*2.5)) ДО экранной стадии, так что читаем
    фактический. Нет вьюпорта — фолбэк на расчётный клип.
    """
    clip = 0.0
    for area in getattr(getattr(context, 'screen', None), 'areas', ()) or ():
        if area.type != 'VIEW_3D':
            continue
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                clip = max(clip, float(getattr(space, 'clip_end', 0.0) or 0.0))
    if clip <= 0.0:
        clip = _actual_clip(context.scene, props, values)
    # Доля клипа настраивается: глубина фона в композиторе не ровно clip_end,
    # а чуть ближе (зависит от движка/сцены), поэтому фиксированный 0.98 небо
    # накрывал. Ползунок «Небо с (× клип)» ловит точку между «дальний край без
    # тумана» и «градиент пропал».
    return clip * float(getattr(props, 'fog_sky_factor', 0.819))


def _world_opts(props, values):
    """Опции мира + докуда клипать вьюпорт.

    Клип ставим ЗА порогом неба: иначе фон окажется ближе порога, и
    туман снова зальёт небо целиком — ровно то, из-за чего градиент
    зенит↔горизонт превращался в один цвет."""
    opts = preview_opts(props)
    opts['clip_end'] = viewport_clip(props, values)
    return opts


def apply_material_values(props, values, scene=None):
    """Ambient и ночной вес — в общую нод-группу прилайта.

    Оба значения одиночные на всю сцену, поэтому слайдер часа стоит две
    записи, а не проход по материалам."""
    from ..tools import timecyc_prelight

    scene = scene or getattr(bpy.context, 'scene', None)
    if props.prelight_daynight:
        timecyc_prelight.set_balance(scene, tc.night_balance(
            props.hour,
            dusk_start=props.dn_dusk_start, dusk_end=props.dn_dusk_end,
            dawn_start=props.dn_dawn_start, dawn_end=props.dn_dawn_end))

    # Ambient зданий — именно Amb, а не Amb_Obj: в игре к prelight
    # прибавляется он (Amb_Obj достаётся машинам, педам и объектам).
    amb = values.get('amb') or [0.0, 0.0, 0.0]
    timecyc_prelight.set_ambient(
        scene, [tc.byte_to_linear(c) for c in amb[:3]])

    return True


# ── Колбэки свойств (вызываются из scene_settings) ──────────────────

def on_weather_changed(self, context):
    sync_props_from_slot(context)
    apply_to_scene(context)


def _slot_for_hour(hour, cyc=None):
    """Индекс ближайшего среза к заданному часу (часы срезов игры файла)."""
    hours = slot_hours(cyc)
    return min(range(len(hours)), key=lambda i: abs(hours[i] - float(hour)))


def on_slot_changed(self, context):
    """Выбор среза ведёт за собой час — иначе правишь Midday, а в
    вьюпорте стоит полночь и правок не видно."""
    global _SYNCING
    # Программная смена среза (из on_hour_changed) идёт под _SYNCING: там час
    # НЕ снапаем и синк делаем сами — иначе таскание часа дёргало бы его назад.
    if _SYNCING:
        return
    cyc = get_cyc(context)
    idx = slot_index(self, cyc)
    hours = slot_hours(cyc)
    sync_props_from_slot(context)
    if 0 <= idx < len(hours):
        _SYNCING = True
        try:
            self.hour = float(hours[idx])
        finally:
            _SYNCING = False
    apply_to_scene(context)


def on_hour_changed(self, context):
    # При выборе среза час выставляется программно под флагом _SYNCING —
    # тогда apply_to_scene сделает сам on_slot_changed один раз. Без этой
    # проверки один клик по срезу гонит полную пересборку мира+композитора
    # дважды.
    global _SYNCING
    if _SYNCING:
        return
    # Таскание часа подтягивает «Правку среза» под текущее время: выбираем
    # ближайший срез и синкаем его значения вниз (час НЕ снапаем). Дропдаун
    # среза ставим под _SYNCING, чтобы on_slot_changed не дёрнул час назад.
    cyc = get_cyc(context)
    idx = _slot_for_hour(self.hour, cyc)
    if slot_index(self, cyc) != idx:
        _SYNCING = True
        try:
            set_slot_index(self, cyc, idx)
            sync_props_from_slot(context)
        finally:
            _SYNCING = False
    apply_to_scene(context)


def on_field_changed(self, context):
    if _SYNCING:
        return
    push_props_to_slot(context)
    apply_to_scene(context)


def on_preview_opt_changed(self, context):
    apply_to_scene(context)


def on_path_changed(self, context):
    drop_cache()


def on_prelight_daynight_changed(self, context):
    """Переключение режима перевязывает материалы — один проход по
    сцене, а не работа на каждый кадр."""
    from ..tools import timecyc_prelight
    _touched, total, report = timecyc_prelight.refresh_materials(
        context.scene, enabled=self.prelight_daynight)
    print("[INU timecyc] %s" % report)
    self.dn_material_count = total
    apply_to_scene(context, force=True)


def on_material_mode_changed(self, context):
    """«Как в игре» меняет сам ГРАФ материалов — один проход по материалам
    на переключение, дальше меняются только значения."""
    from ..tools import timecyc_prelight
    _touched, total, _report = timecyc_prelight.refresh_materials(context.scene)
    self.dn_material_count = total
    apply_to_scene(context, force=True)


def on_screen_mode_changed(self, context):
    """Туман/PostFX — это ТОЛЬКО композитор сцены (см. модульный докстринг
    timecyc_prelight). Материалы не трогаем — раньше их зря перевязывали
    полным проходом по bpy.data.materials на каждый тумблер тумана."""
    apply_to_scene(context, force=True)
    if self.use_fog or self.use_postfx:
        timecyc_screen.enable_viewport_compositor(context, True)


# ── Операторы ───────────────────────────────────────────────────────

class GTATOOLS_OT_import_timecyc(bpy.types.Operator):
    """Загрузить timecyc.dat и показать его освещение в сцене"""
    bl_idname = "gtatools.import_timecyc"
    bl_label = "INU: Import timecyc.dat"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})

    def invoke(self, context, event):
        props = context.scene.inu_settings.gtatools_timecyc
        if not self.filepath:
            self.filepath = props.path or "timecyc.dat"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        props = context.scene.inu_settings.gtatools_timecyc
        path = bpy.path.abspath(self.filepath)
        if not os.path.isfile(path):
            self.report({'ERROR'}, T("Файл не найден: ") + path)
            return {'CANCELLED'}
        try:
            cyc = tc.parse(path)
        except Exception as exc:
            self.report({'ERROR'}, T("Ошибка чтения timecyc: ") + str(exc))
            return {'CANCELLED'}

        # Путь ставим ПЕРВЫМ: его update-колбэк чистит кэш, так что
        # заполнять кэш до этого бессмысленно.
        props.path = path
        _CACHE['path'] = path
        _CACHE['cyc'] = cyc
        _CACHE['failed'] = ''
        sync_weather_list(props, cyc)

        sync_props_from_slot(context)
        # Неотключаемые режимы форсим ДО refresh_materials, чтобы он сразу
        # развёл Day↔Night (PostFX/Прилайт по времени суток всегда True).
        props.use_postfx = True
        props.prelight_daynight = True
        try:
            from ..tools import timecyc_prelight
            # Импорт приводит сцену к ТЕКУЩИМ тумблерам: если игровой
            # вид выключен, материалы возвращаются в PBR, а наши ноды из
            # композитора убираются. Так остатки прошлых сессий не
            # переживают загрузку файла и не красят кадр.
            touched, total, report = timecyc_prelight.refresh_materials(
                context.scene,
                enabled=props.prelight_daynight,
                game_look=props.game_look)
            props.dn_material_count = total
            if not (props.use_fog or props.use_postfx):
                timecyc_screen.teardown(context.scene, context)
            if touched:
                print("[INU timecyc] материалов приведено: %d из %d (%s)"
                      % (touched, total, report))
        except Exception as exc:                       # noqa: BLE001
            print("[INU timecyc] материалы: %s" % exc)
        # Загрузили и показали превью → тайм-цикл активен: держим мастер-
        # состояние включённым, чтобы живое превью сразу реагировало на
        # час/погоду (гейт apply_to_scene теперь на props.enabled).
        props.enabled = True
        apply_to_scene(context, force=True)
        timecyc_world.show_in_viewport(context)
        self.report({'INFO'}, T("timecyc: %s, погод %d, срезов %d, ширина строки %d")
                    % (cyc.game, len(cyc.weathers), len(cyc.slot_hours), cyc.width))
        # Файл другой игры, чем выбрана в сцене — предупредить, как делают
        # остальные импортёры (формат экспорта берётся из файла, а не из
        # сцены, так что это только подсказка).
        try:
            from ..core import game_versions as gv
            if gv.game_of_scene(context.scene) != cyc.game:
                self.report({'WARNING'},
                            T("timecyc.dat из {0}, а игра сцены — {1}").format(
                                cyc.game, gv.game_of_scene(context.scene)))
        except Exception:                                  # noqa: BLE001
            pass
        return {'FINISHED'}


class GTATOOLS_OT_export_timecyc(bpy.types.Operator):
    """Записать timecyc.dat. Нетронутые строки сохраняются как есть, рядом кладётся .bak"""
    bl_idname = "gtatools.export_timecyc"
    bl_label = "INU: Export timecyc.dat"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.dat", options={'HIDDEN'})
    make_backup: BoolProperty(
        name="Сохранить .bak",
        description="Положить рядом копию прежнего файла",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return get_cyc(context, load=False) is not None

    def invoke(self, context, event):
        cyc = get_cyc(context)
        if not self.filepath:
            self.filepath = (cyc.path if cyc else '') or "timecyc.dat"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        cyc = get_cyc(context)
        if cyc is None:
            self.report({'ERROR'}, T("timecyc не загружен"))
            return {'CANCELLED'}
        # НЕ пушим поля панели в срез здесь: правки уже сохранены вживую
        # (on_field_changed пушит на каждое изменение поля). Слепой push
        # текущего среза затирал его полями панели, если они не соответствовали
        # этому срезу (пользователь его не открывал/не правил) — так портился,
        # например, CLOUDY_LA Midday. Пишем только реально изменённые (dirty).
        changed = cyc.dirty_count()
        try:
            path = tc.write(cyc, bpy.path.abspath(self.filepath),
                            backup=self.make_backup)
        except Exception as exc:
            self.report({'ERROR'}, T("Ошибка записи timecyc: ") + str(exc))
            return {'CANCELLED'}
        # DAT-42: 184 data lines, only «//» comments, 51/52 columns,
        # byte / int8 / int16 ranges — what CTimeCycle::Initialise does.
        try:
            from ..core.textdata_lint import check_timecyc
            from .textdata_audit import report_lint
            report_lint(self, os.path.basename(path), *check_timecyc(cyc))
        except Exception as exc:                     # noqa: BLE001
            print(f"[INU lint] timecyc audit failed: {exc}")

        context.scene.inu_settings.gtatools_timecyc.path = path
        _CACHE['path'] = path
        _CACHE['cyc'] = cyc
        _CACHE['failed'] = ''
        self.report({'INFO'}, T("timecyc записан, изменённых срезов: %d") % changed)
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_apply(bpy.types.Operator):
    """Пересобрать освещение сцены по текущим погоде и часу"""
    bl_idname = "gtatools.timecyc_apply"
    bl_label = "Применить к сцене"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_cyc(context, load=False) is not None

    def execute(self, context):
        # Сцены, сохранённые до перехода на коллекцию, приходят с
        # пустым списком погод — заполняем его здесь же.
        cyc = get_cyc(context)
        props = props_of(context)
        if cyc is not None and len(props.weathers) != len(cyc.weathers):
            sync_weather_list(props, cyc)

        from ..tools import timecyc_prelight
        _touched, total, _report = timecyc_prelight.refresh_materials(context.scene)
        props.dn_material_count = total
        if not apply_to_scene(context, force=True):
            cyc = get_cyc(context)
            if cyc is None:
                self.report({'ERROR'}, T("timecyc не загружен"))
            else:
                self.report({'ERROR'}, T("Не удалось применить срез — "
                                         "смотрите системную консоль"))
            return {'CANCELLED'}
        timecyc_world.show_in_viewport(context)
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_viewport(bpy.types.Operator):
    """Перевести вьюпорт в Material Preview со сценическим миром и светом"""
    bl_idname = "gtatools.timecyc_viewport"
    bl_label = "Показать в вьюпорте"
    bl_options = {'REGISTER'}

    def execute(self, context):
        n = timecyc_world.show_in_viewport(context)
        if not n:
            self.report({'WARNING'}, T("Не найден 3D-вьюпорт"))
            return {'CANCELLED'}
        # Туман и PostFX считаются композитором — без него их видно
        # только на F12.
        props = context.scene.inu_settings.gtatools_timecyc
        if props.use_fog or props.use_postfx:
            timecyc_screen.enable_viewport_compositor(context, True)
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_setup_materials(bpy.types.Operator):
    """Включить превью прилайта на всех мешах с вершинными цветами и привести их к игровому виду"""
    bl_idname = "gtatools.timecyc_setup_materials"
    bl_label = "Применить к моделям сцены"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..tools import prelight, timecyc_prelight
        from ..tools import compat

        # Неотключаемые режимы — гарантируем True (тумблеров в UI нет, старые
        # .blend могли сохранить False): PostFX и Прилайт по времени суток.
        props0 = props_of(context)
        props0.use_postfx = True
        props0.prelight_daynight = True

        done = 0
        for obj in context.scene.objects:
            if obj.type != 'MESH' or obj.data is None:
                continue
            # Без вершинных цветов превью прилайта нечего показывать —
            # такие модели (и вся служебная мелочь) пропускаются.
            if not compat.vcol_list(obj.data):
                continue
            ok, _msg = prelight.setup_prelight_preview(obj, enable=True)
            if ok:
                done += 1

        # Чистый цикл game-look off→on, как ручной тумблер «Как в игре»: без
        # него первая разводка иногда НЕ доводила материал до игрового вида
        # (модель чёрная, прилайт не виден до ручного off/on). Прогон в PBR и
        # обратно приводит материал в заведомо корректное состояние.
        props = props0
        gl = bool(props.game_look)
        if gl:
            timecyc_prelight.refresh_materials(context.scene, game_look=False)
        _touched, total, report = timecyc_prelight.refresh_materials(
            context.scene, game_look=gl)
        props.dn_material_count = total
        apply_to_scene(context, force=True)
        timecyc_world.show_in_viewport(context)
        print("[INU timecyc] %s" % report)

        if not done:
            self.report({'WARNING'}, T("Не найдено мешей с вершинными цветами"))
            return {'CANCELLED'}
        # Тайм-цикл применён к сцене — держим мастер-состояние в согласии,
        # чтобы кнопка-тумблер не врала (эту же кнопку можно нажать отдельно).
        props.enabled = True
        self.report({'INFO'}, T("Игровой вид: моделей %d, материалов %d — %s")
                    % (done, total, report))
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_compositor(bpy.types.Operator):
    """Включить композитор в вьюпорте — без него экранные туман и PostFX не считаются"""
    bl_idname = "gtatools.timecyc_compositor"
    bl_label = "Включить композитор"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = props_of(context)
        cyc = get_cyc(context)
        if cyc is not None:
            values = cyc.interpolate(weather_index(props, cyc), props.hour)
            apply_screen_values(context, props, values)

        n = timecyc_screen.enable_viewport_compositor(context, True)
        if not n:
            self.report({'WARNING'},
                        T("Не удалось включить — сделайте это в шейдинге "
                          "вьюпорта (Compositor)"))
            return {'CANCELLED'}
        self.report({'INFO'}, T("Композитор включён в вьюпортах: %d") % n)
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_diagnose(bpy.types.Operator):
    """Напечатать в системную консоль полное состояние превью: цепочка композитора, значения, клип, пассы"""
    bl_idname = "gtatools.timecyc_diagnose"
    bl_label = "Диагностика превью"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = props_of(context)
        cyc = get_cyc(context)

        print("=" * 60)
        print("[INU timecyc] диагностика")
        print("тумблеры: game_look=%s daynight=%s fog=%s postfx=%s"
              % (props.game_look, props.prelight_daynight,
                 props.use_fog, props.use_postfx))
        if cyc is not None:
            values = cyc.interpolate(weather_index(props, cyc), props.hour)
            print("срез: %s %.2f ч | FogSt=%.1f FarClp=%.1f | кривая=%.2f "
                  "×дальность=%.2f"
                  % (props.weather_name, props.hour,
                     (values.get('fog_start') or [0])[0],
                     (values.get('far_clip') or [0])[0],
                     props.fog_curve, props.fog_distance))
            print("клип превью: %.1f | порог неба: %.1f (%s)"
                  % (viewport_clip(props, values),
                     sky_threshold(context, props, values), "авто"))
        print(timecyc_screen.describe(context.scene, context))
        print("=" * 60)

        self.report({'INFO'}, T("Диагностика напечатана в системную консоль"))
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_reset_preview(bpy.types.Operator):
    """Убрать всё, что тайм-цикл добавил в сцену: вернуть материалы в PBR, снять игровой вид, вычистить ноды из композитора"""
    bl_idname = "gtatools.timecyc_reset_preview"
    bl_label = "Сбросить превью"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..tools import timecyc_prelight
        props = props_of(context)

        # Мастер-состояние согласуем сразу, чтобы кнопка-тумблер не осталась
        # «включённой» после ручного сброса.
        props.enabled = False
        props.live = False

        # Сначала гасим тумблеры — их update-колбэки сами ничего лишнего
        # не сделают, потому что дальше мы всё равно проходим по сцене.
        # prelight_daynight и use_postfx НЕ трогаем: они всегда True
        # (неотключаемы), а композитор/ноды всё равно снимает явный
        # refresh_materials(enabled=False) + timecyc_screen.teardown ниже.
        for flag in ('game_look', 'use_fog'):
            setattr(props, flag, False)

        touched, total, report = timecyc_prelight.refresh_materials(
            context.scene, enabled=False, game_look=False)
        timecyc_screen.teardown(context.scene, context)
        # Вернуть прежний мир и цветокоррекцию (apply() назначал INU-мир).
        timecyc_world.teardown(context.scene)

        self.report({'INFO'}, T("Превью сброшено: материалов %d из %d")
                    % (touched, total))
        print("[INU timecyc] сброс превью, %s" % report)
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_toggle(bpy.types.Operator):
    """Включить или выключить тайм-цикл целиком: ВКЛ — применить к сцене (свет, туман, игровой вид прилайта), ВЫКЛ — вернуть сцену как было (материалы в PBR, мир и композитор чистые)"""
    bl_idname = "gtatools.timecyc_toggle"
    bl_label = "Тайм-цикл вкл/выкл"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = props_of(context)
        if props.enabled:
            # ── Выключить: полный сброс превью (как «Сбросить превью») ──
            props.enabled = False
            props.live = False
            bpy.ops.gtatools.timecyc_reset_preview()
            self.report({'INFO'}, T("Тайм-цикл выключен"))
            return {'FINISHED'}

        # ── Включить ──
        # Если ни один под-режим не выбран (например, после сброса) —
        # включаем игровой вид, иначе показывать нечего.
        if not props.game_look and not props.prelight_daynight:
            props.game_look = True
        props.live = True
        # setup_materials сам ставит props.enabled=True при успехе. Если в
        # сцене нет мешей с вершинными цветами — он отменяется, тогда
        # включать нечего: держим состояние выключенным, не врём кнопкой.
        res = bpy.ops.gtatools.timecyc_setup_materials()
        if 'CANCELLED' in res:
            props.enabled = False
            self.report({'WARNING'},
                        T("Нет мешей с вершинными цветами — включать нечего"))
            return {'CANCELLED'}
        self.report({'INFO'}, T("Тайм-цикл включён"))
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_revert_slot(bpy.types.Operator):
    """Вернуть текущий срез к значениям из файла"""
    bl_idname = "gtatools.timecyc_revert_slot"
    bl_label = "Откатить срез"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        slot = current_slot(context)
        return slot is not None and slot.dirty

    def execute(self, context):
        cyc = get_cyc(context)
        slot = current_slot(context, cyc)
        if cyc is None or slot is None:
            return {'CANCELLED'}
        tc.revert_slot(cyc, slot)
        sync_props_from_slot(context)
        apply_to_scene(context)
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_reload(bpy.types.Operator):
    """Перечитать файл с диска — все несохранённые правки пропадут"""
    bl_idname = "gtatools.timecyc_reload"
    bl_label = "Перечитать файл"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return get_cyc(context, load=False) is not None

    def execute(self, context):
        cyc = get_cyc(context)
        dirty = cyc.dirty_count() if cyc else 0
        drop_cache()
        cyc = get_cyc(context)
        if cyc is None:
            self.report({'ERROR'}, T("Не удалось перечитать файл"))
            return {'CANCELLED'}
        sync_weather_list(props_of(context), cyc)
        sync_props_from_slot(context)
        apply_to_scene(context)
        if dirty:
            self.report({'WARNING'}, T("Отброшено изменённых срезов: %d") % dirty)
        return {'FINISHED'}


class GTATOOLS_OT_timecyc_copy_to_all_slots(bpy.types.Operator):
    """Скопировать текущий срез во все срезы этой погоды (8 у SA, 24 у III/VC)"""
    bl_idname = "gtatools.timecyc_copy_to_all_slots"
    bl_label = "Во все срезы погоды"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return current_slot(context) is not None

    def execute(self, context):
        cyc = get_cyc(context)
        props = context.scene.inu_settings.gtatools_timecyc
        push_props_to_slot(context)
        src = current_slot(context, cyc)
        if src is None:
            return {'CANCELLED'}
        weather = cyc.weathers[weather_index(props, cyc)]
        for slot in weather.slots:
            if slot is not src:
                slot.copy_from(src)
        apply_to_scene(context)
        self.report({'INFO'}, T("Срез размножен на всю погоду"))
        return {'FINISHED'}
