# INU_tools.tools.timecyc_prelight — прилайт Day↔Night и игровой вид.
#
# В SA ночные вершинные цвета лежат отдельной секцией DFF (Extra Vert
# Colour), а движок держит параметр dnParam и пишет в preLitLum смесь:
#
#     preLit = day * (1 - dnParam) + night * dnParam
#
# (CCustomBuildingDNPipeline::SetPrelitColors — переход день→ночь в
# игре приходится на 20:00 → 21:00). Здесь то же самое, но нодами:
# одна ОБЩАЯ группа «INU_Timecyc_DayNight» читает атрибуты "Day" и
# "Night" и микширует их по внутреннему Value-узлу.
#
# Дальше здание в игре считается ТАК (skygfx, shaders/vs/*BuildingVS):
#
#     prelight = day*dayparam + night*nightparam
#     color    = (prelight*surfDiff + ambient*surfAmb) * matCol
#     final    = color * texture
#
# ambient здесь — Amb из timecyc (CTimeCycle::GetAmbient* × LightsMult),
# и он ПРИБАВЛЯЕТСЯ, а не умножается: днём Amb почти чёрный (12 10 0),
# всю яркость даёт запечённый prelight. Никакого directional и никаких
# теней у зданий нет — directional и Amb_Obj достаются машинам, педам и
# объектам (mta-helper.fx, MTACalcGTAVehicleDiffuse).
#
# Поэтому «как в игре» = unlit: цвет уходит в Emission, мимо PBR. Иначе
# сцену красит небо (всё синеет) и солнце рисует тени, которых в игре
# не существует.
#
# Туман и PostFX здесь НЕ живут: и то и другое в игре — операции по
# готовому кадру, поэтому они переехали в tools/timecyc_screen.py, в
# композитор. Пока туман стоял в этом графе, он обходил стороной каждый
# объект, где превью прилайта не включено.
#
# Общая группа — не украшение, а способ не платить за карту: слайдер
# часа меняет ОДНО число внутри группы, и его видят все материалы
# сразу. Раскладывать баланс по сотням материалов на каждое движение
# ползунка означало бы столько же перекомпиляций шейдера.
#
# Врезка в граф превью прилайта — ровно в одну точку: источник цвета,
# который идёт в Prelight_ViewBC. Сам граф (ViewBC → ViewGamma →
# ViewSat → Prelight_Mix → Base Color) строит и держит prelight.py, мы
# его не трогаем.

import bpy

from . import compat
from ..core.timecyc import night_balance  # noqa: F401  (реэкспорт для ops)
from ..core.vc_layers import BASE_DAY_NAME, BASE_NIGHT_NAME

GROUP_NAME = "INU_Timecyc_DayNight"
# Имя инстанса группы внутри материала — по нему prelight.py узнаёт
# «источник цвета сейчас смешанный», а не одиночный Attribute.
NODE_NAME = "Prelight_DayNight"
# Ночной атрибут читается нодой В МАТЕРИАЛЕ, рядом с дневной.
NIGHT_NODE_NAME = "Prelight_NightColor"
DAY_NODE_NAME = "Prelight_DayColor"

# Свойства сцены, из которых группа читает значения.
SCENE_BALANCE_PROP = "inu_tc_night_balance"
SCENE_AMBIENT_PROP = "inu_tc_ambient"

_N_IN = "INU_DN_Input"
_N_MIX = "INU_DN_Mix"
_N_BALANCE = "INU_DN_Balance"
_N_AMBIENT = "INU_DN_Ambient"
_N_AMB_ADD = "INU_DN_AmbAdd"
_N_AMB_CLAMP = "INU_DN_AmbClamp"
_N_DAY_GATE = "INU_DN_DayGate"
_N_DAY_MIX = "INU_DN_DayMix"
_N_NIGHT_PRESENT = "INU_DN_NightPresent"
_N_FAC = "INU_DN_Fac"
_N_OUT = "INU_DN_Output"

# Бампать при правке внутренностей группы: группа сохраняется в .blend,
# и старый файл должен пересобраться сам, без «нажмите кнопку ещё раз».
_GROUP_VERSION = 9


# ── Общая нод-группа ────────────────────────────────────────────────

def _attr_node(nodes, name, attr_name, location):
    """Читалка цветового атрибута (Attribute на 4.0+, Vertex Color ниже)."""
    node = nodes.get(name)
    wanted = ('ShaderNodeAttribute' if bpy.app.version >= (4, 0, 0)
              else 'ShaderNodeVertexColor')
    if node is not None and node.bl_idname != wanted:
        nodes.remove(node)
        node = None
    if node is None:
        node = nodes.new(wanted)
        node.name = name
        node.location = location
    if hasattr(node, 'attribute_type'):
        node.attribute_type = 'GEOMETRY'
        node.attribute_name = attr_name
    else:
        node.layer_name = attr_name
    node.label = attr_name
    return node


def _has_output(group):
    """Есть ли у группы хоть один выходной сокет. На 4.0+ интерфейс
    живёт в group.interface.items_tree, ниже — в group.outputs."""
    iface = getattr(group, 'interface', None)
    if iface is not None:
        return any(getattr(item, 'in_out', None) == 'OUTPUT'
                   for item in getattr(iface, 'items_tree', ()))
    return len(group.outputs) > 0


def scan_color_attributes(scene=None):
    """Какие цветовые атрибуты реально есть в сцене.

    Возвращает (day_attr, night_attr, материалы_с_прилайтом). Жёстко
    зашивать "Day"/"Night" нельзя: у чужих моделей слой может зваться
    иначе, а Attribute с несуществующим именем отдаёт нули — материал
    чернеет целиком. Поэтому имена выбираются по сцене, а «есть ли
    прилайт у этого материала» решается здесь же, в Python, а не
    гаданием по альфе в шейдере."""
    scene = scene or getattr(bpy.context, 'scene', None)
    counts = {}
    mats_with_prelight = set()
    if scene is None:
        return BASE_DAY_NAME, BASE_NIGHT_NAME, mats_with_prelight

    for obj in scene.objects:
        if obj.type != 'MESH' or obj.data is None:
            continue
        attrs = getattr(obj.data, 'color_attributes', None) or ()
        names = [a.name for a in attrs]
        if not names:
            continue
        for name in names:
            counts[name] = counts.get(name, 0) + 1
        for slot in obj.material_slots:
            if slot.material is not None:
                mats_with_prelight.add(slot.material.name)

    def _pick(preferred, exclude=()):
        if counts.get(preferred):
            return preferred
        best, best_n = None, 0
        for name, n in counts.items():
            if name in exclude or name.startswith(('VCL_D_', 'VCL_N_')):
                continue
            if n > best_n:
                best, best_n = name, n
        return best

    day = _pick(BASE_DAY_NAME, exclude=(BASE_NIGHT_NAME,)) or BASE_DAY_NAME
    night = BASE_NIGHT_NAME if counts.get(BASE_NIGHT_NAME) else ''
    return day, night, mats_with_prelight


def ensure_group(day_attr=None, night_attr=None):
    """Группа «INU_Timecyc_DayNight». Идемпотентна, пересобирается при
    смене _GROUP_VERSION; имена атрибутов обновляются без пересборки."""
    group = bpy.data.node_groups.get(GROUP_NAME)
    if group is not None and group.bl_idname != 'ShaderNodeTree':
        group = None
    if group is None:
        group = bpy.data.node_groups.new(GROUP_NAME, 'ShaderNodeTree')

    if group.get('inu_dn_version') == _GROUP_VERSION and group.nodes.get(_N_MIX):
        _set_attr_names(group, day_attr, night_attr)
        return group

    group.nodes.clear()
    # Цвета приходят СНАРУЖИ. Читать атрибуты внутри группы оказалось
    # нельзя: Attribute там не отдавал вершинные цвета объекта, и весь
    # материал уходил в чёрный. Снаружи это делает та самая нода
    # Prelight_VertexColor, которую собирает prelight.py и которая
    # работала до нас.
    if not _has_output(group):
        compat.node_group_new_output(group, "Color", 'NodeSocketColor')
    if not _has_inputs(group):
        compat.node_group_new_input(group, "Day", 'NodeSocketColor')
        compat.node_group_new_input(group, "Night", 'NodeSocketColor')

    nodes, links = group.nodes, group.links

    gin = nodes.new('NodeGroupInput')
    gin.name = _N_IN
    gin.location = (-560, 40)

    # Ночной вес и ambient читаются как СВОЙСТВА СЦЕНЫ, а не лежат
    # нодами внутри группы. Правка ноды метит дерево грязным, и EEVEE
    # пересобирает шейдеры всех материалов, которые эту группу видят —
    # на карте это тысяча с лишним перекомпиляций на каждое движение
    # слайдера. Attribute со scope VIEW_LAYER обновляется как uniform.
    balance = nodes.new('ShaderNodeAttribute')
    balance.name = _N_BALANCE
    balance.label = "Night balance (scene)"
    balance.location = (-560, -200)
    balance.attribute_type = 'VIEW_LAYER'
    balance.attribute_name = SCENE_BALANCE_PROP

    # Есть ли в сцене ночной слой — решает Python, а не шейдер.
    night_present = nodes.new('ShaderNodeValue')
    night_present.name = _N_NIGHT_PRESENT
    night_present.label = "Night present"
    night_present.location = (-560, -320)
    night_present.outputs[0].default_value = 0.0

    fac = nodes.new('ShaderNodeMath')
    fac.name = _N_FAC
    fac.label = "Balance × present"
    fac.operation = 'MULTIPLY'
    fac.use_clamp = True
    fac.location = (-340, -260)

    mix = compat.make_mix_rgba(nodes, blend='MIX', name=_N_MIX,
                               label="Day → Night")
    mix.node.location = (-120, 0)

    # Ambient из timecyc — прибавляется к prelight, как в движке.
    ambient = nodes.new('ShaderNodeAttribute')
    ambient.name = _N_AMBIENT
    ambient.label = "Ambient (scene)"
    ambient.location = (-340, 220)
    ambient.attribute_type = 'VIEW_LAYER'
    ambient.attribute_name = SCENE_AMBIENT_PROP

    amb_add = compat.make_mix_rgba(nodes, blend='ADD', name=_N_AMB_ADD,
                                   label="+ Ambient")
    amb_add.node.location = (80, 60)
    amb_add.factor.default_value = 1.0

    # saturate() из формулы движка — до умножения на текстуру.
    clamp = nodes.new('ShaderNodeVectorMath')
    clamp.name = _N_AMB_CLAMP
    clamp.label = "saturate"
    clamp.operation = 'MINIMUM'
    clamp.location = (280, 60)
    clamp.inputs[1].default_value = (1.0, 1.0, 1.0)

    out = nodes.new('NodeGroupOutput')
    out.name = _N_OUT
    out.location = (460, 60)

    links.new(balance.outputs['Fac'], fac.inputs[0])
    links.new(night_present.outputs[0], fac.inputs[1])

    links.new(gin.outputs[0], mix.a)
    links.new(gin.outputs[1], mix.b)
    links.new(fac.outputs[0], mix.factor)

    links.new(mix.result, amb_add.a)
    links.new(ambient.outputs['Color'], amb_add.b)
    links.new(amb_add.result, clamp.inputs[0])
    links.new(clamp.outputs[0], out.inputs[0])

    group['inu_dn_version'] = _GROUP_VERSION
    _set_attr_names(group, day_attr, night_attr)
    return group


def _set_attr_names(group, day_attr, night_attr):
    """Погасить ночную ветку, если ночного слоя в сцене нет."""
    if night_attr is None:
        return
    present = group.nodes.get(_N_NIGHT_PRESENT)
    if present is None:
        return
    value = 1.0 if night_attr else 0.0
    if present.outputs[0].default_value != value:
        present.outputs[0].default_value = value


def _has_inputs(group):
    iface = getattr(group, 'interface', None)
    if iface is not None:
        return any(getattr(item, 'in_out', None) == 'INPUT'
                   for item in getattr(iface, 'items_tree', ()))
    return len(group.inputs) > 0


def set_balance(scene, value):
    """Ночной вес 0..1 — свойством сцены. Ни одна нода не трогается,
    поэтому перекомпиляции шейдеров не происходит."""
    if scene is None:
        return False
    value = min(max(float(value), 0.0), 1.0)
    if abs(float(scene.get(SCENE_BALANCE_PROP, -1.0)) - value) > 1e-5:
        scene[SCENE_BALANCE_PROP] = value
    return True


def set_ambient(scene, color):
    """Цвет Amb (linear RGB) — свойством сцены, см. set_balance."""
    if scene is None:
        return False
    value = [float(color[0]), float(color[1]), float(color[2])]
    old = scene.get(SCENE_AMBIENT_PROP)
    if old is None or any(abs(a - b) > 1e-5 for a, b in zip(old, value)):
        scene[SCENE_AMBIENT_PROP] = value
    return True


# ── Врезка в материалы ──────────────────────────────────────────────

def _colour_node(mat, name, attribute, label, offset):
    """Read a named colour layer outside the shared shader group."""
    nodes = mat.node_tree.nodes
    node = nodes.get(name)
    wanted = ('ShaderNodeAttribute' if bpy.app.version >= (4, 0, 0)
              else 'ShaderNodeVertexColor')
    if node is not None and node.bl_idname != wanted:
        nodes.remove(node)
        node = None
    if node is None:
        node = nodes.new(wanted)
        node.name = name
        node.label = label
        vc = nodes.get("Prelight_VertexColor")
        node.location = ((vc.location.x, vc.location.y + offset) if vc
                         else (-800, offset))
    if hasattr(node, 'attribute_type'):
        node.attribute_type = 'GEOMETRY'
        if node.attribute_name != attribute:
            node.attribute_name = attribute
    elif node.layer_name != attribute:
        node.layer_name = attribute
    return node


def _night_node(mat, night_attr):
    return _colour_node(mat, NIGHT_NODE_NAME, night_attr, "Night", -180)


def group_node(mat, vc_node, links, day_attr=None, night_attr=None):
    """Инстанс общей группы в материале, подключённый к читалкам слоёв.

    The single-layer reader may currently show Night. Keep that selection
    and use a separate Day reader when needed."""
    nodes = mat.node_tree.nodes
    node = nodes.get(NODE_NAME)
    if node is not None and node.bl_idname != 'ShaderNodeGroup':
        nodes.remove(node)
        node = None
    if node is None:
        node = nodes.new('ShaderNodeGroup')
        node.name = NODE_NAME
        node.label = "Day/Night (timecyc)"
        node.location = ((vc_node.location.x + 180, vc_node.location.y - 260)
                         if vc_node else (-620, -200))
    group = ensure_group(day_attr, night_attr)
    if node.node_tree is not group:
        node.node_tree = group

    day_in = node.inputs.get('Day')
    night_in = node.inputs.get('Night')
    if vc_node is not None and day_in is not None:
        current = getattr(vc_node, 'attribute_name', getattr(vc_node, 'layer_name', ''))
        day_node = vc_node
        if day_attr and current != day_attr:
            day_node = _colour_node(mat, DAY_NODE_NAME, day_attr, "Day", -360)
        else:
            stale = nodes.get(DAY_NODE_NAME)
            if stale is not None:
                nodes.remove(stale)
        _link_if_needed(links, day_node.outputs['Color'], day_in)
    if night_in is not None:
        if night_attr:
            _link_if_needed(links, _night_node(mat, night_attr).outputs['Color'],
                            night_in)
        else:
            _unlink_if_needed(links, night_in)
            stale = nodes.get(NIGHT_NODE_NAME)
            if stale is not None:
                nodes.remove(stale)
    return node


def color_source(mat, nodes, links, vc_node, enabled, day_attr=None,
                 night_attr=None):
    """Socket, который должен питать Prelight_ViewBC.

    Единственная точка, где режим Day/Night вмешивается в граф превью
    прилайта: включён — выход общей группы, выключен — обычная нода
    Attribute, которую сделал prelight.py."""
    if vc_node is None:
        return None
    if not enabled:
        stale = nodes.get(NODE_NAME)
        if stale is not None:
            nodes.remove(stale)
        for name in (DAY_NODE_NAME, NIGHT_NODE_NAME):
            stale = nodes.get(name)
            if stale is not None:
                nodes.remove(stale)
        return vc_node.outputs['Color']
    return group_node(mat, vc_node, links, day_attr, night_attr).outputs[0]


def _link_if_needed(links, src, socket):
    """Связать, только если связи ещё нет. Материал в GTA-сцене общий на
    сотни объектов, а wire_material зовётся для каждого из них: лишняя
    перевязка = лишняя перекомпиляция шейдера на ровном месте."""
    if socket.is_linked and socket.links[0].from_socket == src:
        return False
    for lnk in list(socket.links):
        links.remove(lnk)
    links.new(src, socket)
    return True


def _unlink_if_needed(links, socket):
    if not socket.is_linked:
        return False
    for lnk in list(socket.links):
        links.remove(lnk)
    return True


def _wire_output(mat, nodes, links, principled, mix_node, game_look,
                 has_prelight=True):
    """Куда уходит цвет: PBR Base Color или Emission (как в игре).

    Игра рисует здания fixed-function'ом — ни теней, ни бликов, ни
    подсветки от неба. Ближайший эквивалент в Blender — Emission:
    материал отдаёт ровно посчитанный цвет и не участвует в освещении.
    Прежний вид возвращается один в один, поэтому переключаться можно
    сколько угодно."""
    base_color = principled.inputs.get('Base Color')
    emit_color = compat.principled_emission_input(principled)
    emit_strength = principled.inputs.get('Emission Strength')
    if base_color is None:
        return False

    changed = False
    src = compat.mix_output_result(mix_node)
    if not has_prelight:
        # Ни один меш с этим материалом не несёт вершинных цветов.
        # Тогда ветка прилайта даёт чёрный (Attribute на пустом месте),
        # и в unlit объект чернел целиком — отдаём чистую текстуру.
        tex = compat.mix_input_a(mix_node)
        if tex.is_linked:
            src = tex.links[0].from_socket

    if game_look and emit_color is not None:
        if not mat.get('inu_tc_game_look'):
            # Запоминаем, чтобы вернуть материал как было.
            mat['inu_tc_prev_emit'] = (
                float(emit_strength.default_value)
                if emit_strength is not None else 1.0)
            # И исходный Base Color: game-look обнуляет его в чёрный, а у
            # бестекстурного материала при экспорте вернуть его больше
            # неоткуда — без этого цвет материала уходил в DFF как 0, и с
            # флагом MODULATE прилайт умножался на ноль → чёрная модель.
            mat['inu_tc_prev_base'] = tuple(base_color.default_value)
            mat['inu_tc_game_look'] = True
            changed = True
        changed |= _unlink_if_needed(links, base_color)
        if tuple(base_color.default_value)[:3] != (0.0, 0.0, 0.0):
            base_color.default_value = (0.0, 0.0, 0.0, 1.0)
            changed = True
        changed |= _link_if_needed(links, src, emit_color)
        if (emit_strength is not None and not emit_strength.is_linked
                and emit_strength.default_value != 1.0):
            emit_strength.default_value = 1.0
            changed = True
        return changed

    if emit_color is not None and mat.get('inu_tc_game_look'):
        changed |= _unlink_if_needed(links, emit_color)
        emit_color.default_value = (0.0, 0.0, 0.0, 1.0)
        if emit_strength is not None and not emit_strength.is_linked:
            emit_strength.default_value = float(mat.get('inu_tc_prev_emit', 1.0))
        # Вернуть Base Color, который game-look обнулял в чёрный.
        prev_base = mat.get('inu_tc_prev_base')
        if prev_base is not None:
            base_color.default_value = tuple(prev_base)
        elif (not base_color.is_linked
                and tuple(base_color.default_value)[:3] == (0.0, 0.0, 0.0)):
            # Старый .blend без сохранённого цвета — не оставлять чёрным.
            base_color.default_value = (1.0, 1.0, 1.0, 1.0)
        for key in ('inu_tc_game_look', 'inu_tc_prev_emit', 'inu_tc_prev_base'):
            if key in mat:
                del mat[key]
        changed = True

    changed |= _link_if_needed(links, src, base_color)
    return changed


def _props(scene=None):
    scene = scene or getattr(bpy.context, 'scene', None)
    if scene is None:
        return None
    settings = getattr(scene, 'inu_settings', None)
    if settings is None:
        return None
    return getattr(settings, 'gtatools_timecyc', None)


def wire_material(mat, daynight=None, game_look=None, scene=None,
                  day_attr=None, night_attr=None, has_prelight=True):
    """Привести ОДИН материал с превью прилайта к текущему режиму.

    Вызывается и из refresh_materials, и из prelight.py сразу после
    сборки графа превью — иначе включение превью на объекте сбрасывало
    бы игровой вид обратно в PBR."""
    if not mat or not getattr(mat, 'use_nodes', False):
        return False
    nt = mat.node_tree
    if nt is None:
        return False
    props = _props(scene)
    if daynight is None:
        daynight = bool(props and props.prelight_daynight)
    if game_look is None:
        game_look = bool(props and props.game_look)
    if daynight and (day_attr is None or night_attr is None):
        detected_day, detected_night, _ = scan_color_attributes(scene)
        day_attr = detected_day if day_attr is None else day_attr
        night_attr = detected_night if night_attr is None else night_attr

    nodes, links = nt.nodes, nt.links
    bc = nodes.get("Prelight_ViewBC")
    mix_node = nodes.get("Prelight_Mix")
    if bc is None or mix_node is None:
        return False
    vc_node = nodes.get("Prelight_VertexColor")

    changed = False

    # 1. Источник цвета: смесь Day↔Night или одиночная читалка слоя.
    src = color_source(mat, nodes, links, vc_node,
                       daynight and has_prelight,
                       day_attr=day_attr, night_attr=night_attr)
    if src is not None:
        changed |= _link_if_needed(links, src, bc.inputs['Color'])

    # 2. Куда уходит результат: PBR или unlit.
    principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if principled is not None:
        changed |= bool(_wire_output(mat, nodes, links, principled,
                                     mix_node, game_look, has_prelight))
    return changed


def refresh_materials(scene=None, enabled=None, game_look=None):
    """Привести все материалы с превью прилайта к текущему режиму.

    Имена цветовых слоёв и признак «у этого материала есть прилайт»
    берутся из реальных мешей сцены — см. scan_color_attributes.

    Возвращает ``(перевязано, всего материалов с превью, отчёт)``, где
    отчёт — короткая строка о том, что нашлось в сцене: без неё «всё
    чёрное» диагностировать нечем."""
    props = _props(scene)
    if enabled is None:
        enabled = bool(props and props.prelight_daynight)
    if game_look is None:
        game_look = bool(props and props.game_look)

    day_attr, night_attr, mats_with_prelight = scan_color_attributes(scene)
    if enabled:
        ensure_group(day_attr, night_attr)

    touched = 0
    total = 0
    for mat in bpy.data.materials:
        if not mat or not getattr(mat, 'use_nodes', False):
            continue
        if not mat.get('prelight_preview_active') and not mat.get('inu_tc_game_look'):
            continue
        total += 1
        if wire_material(mat, daynight=enabled, game_look=game_look,
                         scene=scene, day_attr=day_attr, night_attr=night_attr,
                         has_prelight=mat.name in mats_with_prelight):
            touched += 1

    report = "прилайт: %s%s, материалов с цветами %d" % (
        day_attr or "—",
        (" + %s" % night_attr) if night_attr else " (ночного слоя нет)",
        len(mats_with_prelight))
    return touched, total, report
