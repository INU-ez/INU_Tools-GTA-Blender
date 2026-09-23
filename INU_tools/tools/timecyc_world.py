# INU_tools.tools.timecyc_world — значения timecyc → освещение сцены.
#
# Строит и обновляет мир «INU Timecyc»: градиент неба зенит↔горизонт,
# ambient, солнце-Sun по времени суток, объёмный туман и цвет воды.
#
# Точного совпадения с игрой тут быть не может и не заявляется: SA не
# PBR — там `текстура × (prelight vcol × ambient + directional)`, свой
# fog и DITHERED-альфа. Задача — воспроизвести АТМОСФЕРУ среза, чтобы
# подбирать освещение и снимать скриншоты, глядя на те же цифры, что
# читает игра.
#
# Что где видно:
#   * градиент неба, ambient, солнце, вода — Material Preview и
#     Rendered (при use_scene_world/use_scene_lights, их включает
#     оператор «Показать в вьюпорте»);
#   * туман живёт НЕ здесь: игра гасит цвет по расстоянию фиксированной
#     функцией, и то же самое делает нодовая группа в
#     tools/timecyc_prelight.py. Мировой Volume Scatter, который стоял
#     тут раньше, без источников света давал чёрную кашу вместо дымки —
#     он убран;
#   * PostFX — композиторная цветокоррекция, во вьюпорте её нет вообще;
#     значения правятся и экспортируются, но в превью не участвуют.
#
# Солнца тут нет вовсе. В GTA оно не бросает теней, здания освещены
# запечённым prelight'ом, а «как в игре» вообще идёт мимо PBR — лампа
# только рисовала то, чего в игре не бывает. Оставшаяся от прошлых
# версий лампа удаляется при первом же применении (remove_sun).
#
# Ноды не пересоздаются на каждое движение слайдера: дерево строится
# один раз и помечается именами, дальше меняются только default_value.

import math

import bpy

from . import compat
from ..core.timecyc import srgb_to_linear

WORLD_NAME = "INU Timecyc"
SUN_NAME = "INU_Timecyc_Sun"
COLLECTION_NAME = "INU Timecyc"

# Кэш водных материалов (см. _apply_water).
_WATER_MATS = []
_WATER_MATS_STAMP = -1

# Имена нод — по ним же ищем их при обновлении значений.
_N_COORD = "INU_TC_Coord"
_N_SEP = "INU_TC_SepXYZ"
_N_RANGE = "INU_TC_Range"
_N_SKY_MIX = "INU_TC_SkyMix"
_N_SKY_BG = "INU_TC_SkyBG"
_N_AMB_BG = "INU_TC_AmbBG"
_N_PATH = "INU_TC_LightPath"
_N_SHADER_MIX = "INU_TC_ShaderMix"
_N_OUT = "INU_TC_Output"

# Бампать при любой правке структуры дерева: миры из старых .blend
# пересоберутся сами, без «нажмите кнопку ещё раз».
_TREE_VERSION = 3


# ── Цвет ────────────────────────────────────────────────────────────

def _color(values, key, fallback=(0.0, 0.0, 0.0)):
    """Три байта timecyc → linear-RGB для нод Blender."""
    v = values.get(key)
    if not v or len(v) < 3:
        return tuple(fallback)
    return tuple(srgb_to_linear(min(max(c, 0.0), 255.0) / 255.0) for c in v[:3])


def _num(values, key, fallback=0.0):
    v = values.get(key)
    if not v:
        return fallback
    return float(v[0])


# ── Мир ─────────────────────────────────────────────────────────────

def _node(tree, name, idname, location):
    """Нода по имени; создаётся, если её нет или тип не тот (дерево
    могли поправить руками)."""
    node = tree.nodes.get(name)
    if node is not None and node.bl_idname != idname:
        tree.nodes.remove(node)
        node = None
    if node is None:
        node = tree.nodes.new(idname)
        node.name = name
        node.label = name
        node.location = location
    return node


def ensure_world(split_ambient=False):
    """Мир «INU Timecyc» с готовым деревом нод.

    Два режима:
      * обычный — фон целиком градиент неба, он же и светит сцене. Это
        чистая связка Background → Output, работает в любом движке;
      * `split_ambient` — небо остаётся фоном для камеры, а освещение
        берётся из отдельного Background с цветом Amb. Разделение
        держится на Light Path «Is Camera Ray», который в EEVEE ведёт
        себя не так честно, как в Cycles, поэтому это тумблер, а не
        поведение по умолчанию.

    Дерево собирается ОДИН раз на режим: слайдер часа дёргает apply()
    десятки раз за секунду, а пересборка связей каждый раз заставляла
    депсграф перестраивать мир на каждый кадр."""
    world = bpy.data.worlds.get(WORLD_NAME)
    if world is None:
        world = bpy.data.worlds.new(WORLD_NAME)
    world.use_nodes = True
    tree = world.node_tree

    mode = 'SPLIT' if split_ambient else 'SKY'
    if (world.get('inu_tc_tree') == _TREE_VERSION
            and world.get('inu_tc_mode') == mode
            and tree.nodes.get(_N_OUT) is not None):
        return world

    coord = _node(tree, _N_COORD, 'ShaderNodeTexCoord', (-900, 240))
    sep = _node(tree, _N_SEP, 'ShaderNodeSeparateXYZ', (-700, 240))
    rng = _node(tree, _N_RANGE, 'ShaderNodeMapRange', (-520, 240))
    # Mix — через compat: на 3.4+ это ShaderNodeMix с тройными A/B
    # сокетами, брать их по имени напрямую нельзя (вернётся Float).
    mix_wrap = compat.find_mix_rgba(tree.nodes, _N_SKY_MIX)
    if mix_wrap is None:
        mix_wrap = compat.make_mix_rgba(tree.nodes, blend='MIX',
                                        name=_N_SKY_MIX, label=_N_SKY_MIX)
        mix_wrap.node.location = (-320, 240)
    mix = mix_wrap.node
    sky_bg = _node(tree, _N_SKY_BG, 'ShaderNodeBackground', (-120, 300))
    amb_bg = _node(tree, _N_AMB_BG, 'ShaderNodeBackground', (-120, 140))
    path = _node(tree, _N_PATH, 'ShaderNodeLightPath', (-320, 20))
    smix = _node(tree, _N_SHADER_MIX, 'ShaderNodeMixShader', (100, 220))
    out = _node(tree, _N_OUT, 'ShaderNodeOutputWorld', (320, 220))

    rng.clamp = True

    # Мусор от прежних правок дерева убираем, иначе второй Output может
    # перехватить рендер и мир останется чёрным.
    keep = {coord, sep, rng, mix, sky_bg, amb_bg, path, smix, out}
    for node in list(tree.nodes):
        if node not in keep:
            tree.nodes.remove(node)

    links = tree.links
    for link in list(links):
        links.remove(link)

    links.new(coord.outputs['Generated'], sep.inputs['Vector'])
    links.new(sep.outputs['Z'], rng.inputs['Value'])
    links.new(rng.outputs['Result'], mix_wrap.factor)
    links.new(mix_wrap.result, sky_bg.inputs['Color'])
    if split_ambient:
        # Fac = Is Camera Ray: 1 у луча из камеры → вход[2] (небо),
        # 0 у лучей освещения → вход[1] (ambient).
        links.new(sky_bg.outputs['Background'], smix.inputs[2])
        links.new(amb_bg.outputs['Background'], smix.inputs[1])
        links.new(path.outputs['Is Camera Ray'], smix.inputs['Fac'])
        links.new(smix.outputs['Shader'], out.inputs['Surface'])
    else:
        links.new(sky_bg.outputs['Background'], out.inputs['Surface'])

    world['inu_tc_tree'] = _TREE_VERSION
    world['inu_tc_mode'] = mode
    return world


def _apply_world(world, values, opts):
    tree = world.node_tree
    nodes = tree.nodes

    # Цвета неба идут в мир СЫРЫМИ, как в timecyc: цветофильтр кадра
    # накладывается позже, экранной стадией в композиторе — там же, где
    # его накладывает игра, и сразу на всё, включая небо.
    sky_top = _color(values, 'sky_top')
    sky_bot = _color(values, 'sky_bot')
    amb_key = 'amb_obj' if opts.get('ambient_from_objects') else 'amb'
    if amb_key not in values:          # III: одного ambient на всё
        amb_key = 'amb'
    amb = _color(values, amb_key)

    mix = compat.find_mix_rgba(nodes, _N_SKY_MIX)
    if mix:
        # Factor 0 → горизонт, 1 → зенит.
        mix.a.default_value = (*sky_bot, 1.0)
        mix.b.default_value = (*sky_top, 1.0)

    rng = nodes.get(_N_RANGE)
    if rng:
        sharp = max(float(opts.get('gradient', 0.35)), 0.01)
        rng.inputs['From Min'].default_value = 0.0
        rng.inputs['From Max'].default_value = sharp
        rng.inputs['To Min'].default_value = 0.0
        rng.inputs['To Max'].default_value = 1.0

    sky_bg = nodes.get(_N_SKY_BG)
    if sky_bg:
        sky_bg.inputs['Strength'].default_value = float(opts.get('sky_strength', 1.0))

    amb_bg = nodes.get(_N_AMB_BG)
    if amb_bg:
        amb_bg.inputs['Color'].default_value = (*amb, 1.0)
        amb_bg.inputs['Strength'].default_value = float(opts.get('ambient_strength', 1.0))


# Габариты сцены для клипа вьюпорта. Обход объектов кэшируем: apply()
# зовётся на каждое движение слайдера часа.
_EXTENT = 0.0
_EXTENT_STAMP = -1


def scene_extent(scene):
    """Радиус сцены в метрах — по габаритам объектов.

    Клип вьюпорта должен покрывать карту целиком, иначе при отдалении
    её край честно обрезается плоскостью отсечения. Считать по FarClp
    среза мало: в timecyc это дальность прорисовки игры (800 м), а
    карта тянется на километры."""
    global _EXTENT, _EXTENT_STAMP
    stamp = len(scene.objects)
    if _EXTENT_STAMP == stamp and _EXTENT > 0.0:
        return _EXTENT

    radius = 0.0
    for obj in scene.objects:
        if obj.type not in ('MESH', 'CURVE', 'SURFACE', 'FONT'):
            continue
        try:
            mat = obj.matrix_world
            for corner in obj.bound_box:
                # Ручное умножение матрицы на точку: mathutils тянуть
                # незачем, а модуль должен грузиться и вне Blender.
                cx, cy, cz = corner[0], corner[1], corner[2]
                for row in range(3):
                    value = (mat[row][0] * cx + mat[row][1] * cy
                             + mat[row][2] * cz + mat[row][3])
                    radius = max(radius, abs(value))
        except (AttributeError, ValueError, IndexError, TypeError):
            continue
    _EXTENT = radius
    _EXTENT_STAMP = stamp
    return radius


def viewport_clip_end(context):
    """Наибольший clip end среди 3D-вьюпортов — это и есть глубина фона."""
    best = 0.0
    for area in getattr(context.screen, 'areas', ()) or ():
        if area.type != 'VIEW_3D':
            continue
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                best = max(best, float(space.clip_end))
    return best


def _timecyc_collection(scene):
    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION_NAME)
    if coll.name not in scene.collection.children:
        try:
            scene.collection.children.link(coll)
        except RuntimeError:
            pass
    return coll


def remove_sun(scene):
    """Убрать лампу-солнце, если она осталась от прошлых версий.

    В GTA солнце теней не бросает, а здания освещены запечённым
    prelight'ом — directional-лампа тут только вводила в заблуждение и
    рисовала то, чего в игре не бывает. Поэтому её больше нет, а старые
    сцены чистятся при первом же применении."""
    obj = bpy.data.objects.get(SUN_NAME)
    if obj is None:
        return False
    data = obj.data if obj.type == 'LIGHT' else None
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    try:
        bpy.data.objects.remove(obj)
        if data is not None and getattr(data, 'users', 0) == 0:
            bpy.data.lights.remove(data)
    except (RuntimeError, ReferenceError):
        pass

    coll = bpy.data.collections.get(COLLECTION_NAME)
    if coll is not None and not coll.objects and not coll.children:
        try:
            bpy.data.collections.remove(coll)
        except (RuntimeError, ReferenceError):
            pass
    return True


def _apply_water(values, opts):
    """Цвет импортированной воды. Материал заводит water_import —
    сами его не создаём, чтобы не плодить пустышку в сценах без воды."""
    if not opts.get('water'):
        return 0
    rgba = values.get('water')
    if not rgba or len(rgba) < 4:
        return 0
    color = _color(values, 'water')
    alpha = min(max(rgba[3] / 255.0, 0.0), 1.0)

    # Список водных материалов кэшируем: слайдер часа дёргает apply()
    # десятки раз в секунду, а обходить ВСЕ материалы сцены (их на карте
    # за тысячу) ради пары «waterclear» — верный способ подвесить UI.
    global _WATER_MATS, _WATER_MATS_STAMP
    stamp = len(bpy.data.materials)
    if _WATER_MATS_STAMP != stamp:
        _WATER_MATS = [m for m in bpy.data.materials
                       if m and m.name.startswith('waterclear')]
        _WATER_MATS_STAMP = stamp

    touched = 0
    for mat in _WATER_MATS:
        if not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type != 'BSDF_PRINCIPLED':
                continue
            base = node.inputs.get('Base Color')
            if base is not None and not base.is_linked:
                base.default_value = (*color, 1.0)
            alpha_in = node.inputs.get('Alpha')
            if alpha_in is not None and not alpha_in.is_linked:
                alpha_in.default_value = alpha
            touched += 1
    return touched


def apply(context, values, hour, opts=None):
    """Разлить значения среза по сцене. `values` — из
    TimecycFile.interpolate(); `opts` — ручки превью из панели."""
    opts = opts or {}
    scene = context.scene

    world = ensure_world(opts.get('ambient_split', False))
    _apply_world(world, values, opts)
    if scene.world is not world:
        # Запоминаем прежний мир ОДИН раз — иначе назначение INU-мира затирает
        # пользовательский безвозвратно, и «Сбросить превью» его не вернёт.
        if 'inu_tc_prev_world' not in scene:
            scene['inu_tc_prev_world'] = scene.world.name if scene.world else ''
        scene.world = world

    remove_sun(scene)
    _apply_water(values, opts)
    apply_color_management(scene, opts.get('game_look', False))

    # Дальность прорисовки среза — заодно и клип вьюпорта: с дефолтными
    # 100 м дальняя часть карты просто обрезается, и туман гасить нечего.
    if opts.get('far_clip'):
        # Клип и порог неба считаются в одном месте (ops.viewport_clip):
        # порог стоит чуть ближе клипа, чтобы фон гарантированно
        # отсекался, а вся геометрия оставалась в тумане.
        far = float(opts.get('clip_end') or 0.0)
        if far <= 0.0:
            far = max(_num(values, 'far_clip', 800.0), 10.0) * 1.5
        # Карта обязана помещаться целиком: иначе её край обрезается
        # плоскостью отсечения, стоит чуть отдалить камеру.
        far = max(far, scene_extent(scene) * 2.5)
        for area in getattr(context.screen, 'areas', ()) or ():
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.clip_end = max(space.clip_end, far)


def apply_color_management(scene, game_look):
    """Вид через Standard, пока включён игровой режим.

    Blender 4.x по умолчанию показывает сцену через AgX: он затемняет и
    десатурирует, и цвет неба на экране перестаёт быть тем sRGB-байтом,
    который записан в timecyc. Игра же выводит его напрямую, без
    тонемаппинга. Standard + нейтральные exposure/gamma возвращают
    ровно исходные значения.

    Прежние настройки запоминаются на сцене и возвращаются, когда
    игровой режим выключают — чужой воркфлоу мы не ломаем."""
    view = getattr(scene, 'view_settings', None)
    if view is None:
        return False

    if game_look:
        if 'inu_tc_prev_view' not in scene:
            scene['inu_tc_prev_view'] = [
                view.view_transform, view.look,
                float(view.exposure), float(view.gamma)]
        changed = False
        for attr, value in (('view_transform', 'Standard'), ('look', 'None'),
                            ('exposure', 0.0), ('gamma', 1.0)):
            try:
                if getattr(view, attr) != value:
                    setattr(view, attr, value)
                    changed = True
            except (TypeError, AttributeError):
                # 'None' у look в разных версиях зовётся по-разному —
                # не смогли поставить, и ладно: тонемап важнее look'а.
                pass
        return changed

    prev = scene.get('inu_tc_prev_view')
    if not prev:
        return False
    try:
        view.view_transform = prev[0]
        view.look = prev[1]
        view.exposure = float(prev[2])
        view.gamma = float(prev[3])
    except (TypeError, AttributeError, IndexError):
        pass
    del scene['inu_tc_prev_view']
    return True


def teardown(scene):
    """Вернуть сцену как было до тайм-цикла: восстановить прежний мир и снять
    игровую цветокоррекцию. Парная apply(); зовётся из reset_preview/toggle-off.
    Без неё сцена оставалась с миром «INU Timecyc», а исходный мир терялся."""
    apply_color_management(scene, False)          # снять игровой Standard
    prev = scene.get('inu_tc_prev_world')
    if prev is not None:
        scene.world = bpy.data.worlds.get(prev) if prev else None
        del scene['inu_tc_prev_world']


def show_in_viewport(context):
    """Перевести вьюпорты в Material Preview со сценическим миром и
    светом — иначе Blender светит студийным HDRI и правок не видно."""
    switched = 0
    for area in getattr(context.screen, 'areas', ()) or ():
        if area.type != 'VIEW_3D':
            continue
        for space in area.spaces:
            if space.type != 'VIEW_3D':
                continue
            shading = space.shading
            if shading.type not in ('MATERIAL', 'RENDERED'):
                shading.type = 'MATERIAL'
            shading.use_scene_world = True
            shading.use_scene_lights = True
            switched += 1
    return switched
