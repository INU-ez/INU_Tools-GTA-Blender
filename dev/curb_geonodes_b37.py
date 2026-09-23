# -*- coding: utf-8 -*-
#
# Процедурный бордюр на гео-нодах.
#
# ЗАПУСК
#   Text Editor -> Run Script. Создаёт нод-группу «INU_Curb» и вешает её
#   модификатором на выделенные меш-объекты.
#
# ДВЕ ВЕТКИ
#   Внешний контур — бордюр целиком с одной стороны линии, остаются верх
#   и наружная стенка. Внутренние рёбра — бордюр по центру ребра, остаётся
#   только верхняя грань: к ней вплотную встанут трава и тротуар, стенки
#   и низ всё равно не видно.
#   Посадка профиля у веток разная, одним свипом это не сделать, поэтому
#   строятся две одинаковые цепочки и склеиваются в конце.
#
# ПРО СУЖЕНИЕ В УГЛАХ
#   «Кривую в меш» ставит профиль перпендикулярно усреднённой касательной
#   и не масштабирует его, поэтому ширина в изломе падает как cos(угол/2).
#   Это её штатное поведение (issue #147946), в 5.3 для этого добавили
#   Miter Scale. Здесь то же самое делается руками: в каждой точке
#   считается 1/cos(угол/2) и подаётся во вход «Масштаб».
#   Косинус берётся без поиска соседних точек: у каждого ребра свой
#   единичный перпендикуляр, а среднее по рёбрам в вершине Blender
#   считает сам — длина полусуммы и есть cos(угол/2). Ради этого линия
#   переводится в рёбра и обратно в кривую.

import bpy

SCRIPT_BUILD = 37
GROUP_NAME = "INU_Curb"
MOD_NAME = "INU Curb"
EDGE_ATTR = "sharp_edge"
VGROUP = "curb_round"
UV_NAME = "UVMap"
PD_ATTR = "curb_pd"      # удаление точки сечения от линии
IS_IN_ATTR = "curb_isin"  # 1 у внутренней ветки, 0 у внешней
WDIR_ATTR = "curb_wdir"   # направление в сторону тротуара
UU_ATTR = "curb_uu"      # U до склейки
VV_ATTR = "curb_vv"      # V до склейки
MITER_EPS = 1e-3
CLIP_STEP = 0.02   # шаг деления линии перед обрезкой
WALK_SINK = 0.0005  # на сколько опущена лента тротуара

# Материалы по умолчанию: подставляются, если такие есть в файле.
MAT_CURB = "curb_1"
MAT_GRASS = "pf_Grass_01"
MAT_WALK = "KCG_trot01"

HELP_NAME = "INU_Curb — как пользоваться"

HELP_TEXT = """INU_Curb — процедурный бордюр

1. ЛИНИЯ БОРДЮРА
   Внешний край плоскости — галочка «Бордюр по контуру».
   Внутри участка: Edit Mode -> режим рёбер (клавиша 2) -> выдели
   рёбра -> Ctrl+E -> Mark Sharp. Снять: Ctrl+E -> Clear Sharp.
   Видеть пометки: Overlays -> Mesh Edit Mode -> Sharp.

   Внешний контур и внутренние рёбра строятся по-разному:
     внешний    — бордюр целиком внутрь от линии, остаются верх
                  и наружная стенка;
     внутренние — бордюр по центру ребра, остаётся только верх:
                  стенки и низ закроются травой и тротуаром.

2. КРУГЛЫЕ УГЛЫ — ТРИ ГРУППЫ
   Properties -> Object Data (зелёный треугольник) -> Vertex Groups
   -> «+» -> curb_round_1, curb_round_2, curb_round_3.
   Edit Mode -> выдели угловые точки -> внизу списка поставь Weight
   -> Assign.

   У каждой группы своё поле радиуса в метрах, а вес вершины
   масштабирует его от нуля до этого значения:
     радиус = Weight x «Радиус N»
   То есть группы задают порядок величины, а вес — точное
   значение внутри него, так что радиус может быть любой.
   Если точка в двух группах — берётся больший радиус,
   а не сумма. Точки вне всех групп остаются острыми.

3. СЕЧЕНИЕ
   «Ширина» и «Высота» — размеры камня.
   «Сдвиг по высоте» — поднять или опустить сечение относительно линии.
   «Сторона» — на какую сторону лечь бордюру внешнего контура.

4. UV
   Текстура делится на строки по горизонтали: «Строк в текстуре».
   «Строка бока» и «Строка верха» — в какую строку лечь каждому
   острову, счёт снизу.
   Масштаб берётся от высоты одной строки: при «Тайлинг вдоль» = 1
   боковая стенка занимает свою строку ровно по высоте, а вдоль и
   на верхней грани плотность та же — ничего не искажено.
   Строки в curb_1 при «Строк в текстуре» = 4:
     1  чёрно-белая разметка
     2  бордюр, грязный бетон с линией
     3  бордюр с зеленью по верхнему краю
     4  бордюр, чистый бетон с линией

5. ЗАТЕНЕНИЕ
   «Гладкое затенение» выкл — весь бордюр плоский.
   вкл — автосглаживание по «Углу автосглаживания».

6. ЗАЛИВКА ВНУТРИ
   Галочка «Заливка внутри» заполняет ячейки поверхностью вровень
   с верхом бордюра. Она отступает от бордюра, поэтому не лезет
   под него: у внешнего контура на всю ширину бордюра, у внутренних
   рёбер на половину — там бордюр стоит по центру ребра.

   Материал — поле «Материал травы».
   Развёртка заливки планарная, сверху; плотность — «Тайлинг заливки».

   ТРОТУАР. В Edit Mode выдели грани, которые должны стать тротуаром,
   и назначь им отдельный слот материала (Material Properties -> «+»
   -> Assign). Номер слота — поле «Слот тротуара», по умолчанию 1.
   На этих гранях заливка получает «Материал тротуара», а по всей
   границе помеченного участка встаёт бордюр — как между ячейками.

7. ЭКСПОРТ В GTA
   Включи «Триангулировать», затем Object -> Convert -> Mesh.
"""


# -- сокет-хелперы ----------------------------------------------------
# У Compare / Switch / Store Named Attribute несколько одноимённых
# сокетов (по одному на тип данных); актуален тот, у которого
# enabled=True. Плюс геометрические сокеты между версиями
# переименовывались.

_SOCKET_ALIASES = {
    'Target': ('Geometry', 'Mesh'),
    'Geometry': ('Mesh', 'Curve', 'Instances'),
    'Mesh': ('Geometry', 'Curve'),
    'Curve': ('Geometry', 'Mesh'),
}


def _pick(sockets, name, kind, bl_idname):
    for want in (name,) + _SOCKET_ALIASES.get(name, ()):
        for s in sockets:
            if s.name == want and s.enabled:
                return s
        for s in sockets:
            if s.name == want:
                return s
    raise KeyError("%s: нет %s '%s' (есть: %s)"
                   % (bl_idname, kind, name, [s.name for s in sockets]))


def _in(node, name):
    return _pick(node.inputs, name, "входа", node.bl_idname)


def _out(node, name):
    return _pick(node.outputs, name, "выхода", node.bl_idname)


def _find_in(node, name):
    """Как и _in, сначала ищет ВКЛЮЧЁННЫЙ сокет. У Compare сокеты «A» и
    «B» заведены для каждого типа данных, и в режиме INT включены только
    целочисленные. Если искать без учёта enabled, значение уляжется в
    вещественный сокет, который в этом режиме не участвует, — а сравнение
    останется с нулём."""
    for s in node.inputs:
        if s.name == name and s.enabled:
            return s
    for s in node.inputs:
        if s.name == name:
            return s
    return None


def _set_in(node, name, value):
    s = _find_in(node, name)
    if s is None:
        return False
    try:
        s.default_value = value
        return True
    except (TypeError, ValueError, AttributeError):
        return False


# В Blender 5.x часть выпадашек нод переехала в menu-сокеты входа, и
# старые enum-идентификаторы туда не пишутся. Перебираем написания, а при
# наличии проверочного входа — и индексы пунктов.
_ALIASES = {
    'POLY': ('Poly', 'Полилиния'),
    'EDGES': ('Edges', 'Edge'),
    'RECTANGLE': ('Rectangle',),
    'FACE': ('Face', 'Faces'),
    'EDGE': ('Edge', 'Edges'),
    'GEOMETRY': ('Geometry',),
    'FLOAT_VECTOR': ('Vector',),
}


def _set_prop(node, name, value, probe=None):
    if hasattr(node, name):
        try:
            setattr(node, name, value)
            return True
        except (TypeError, ValueError):
            pass

    for p in node.bl_rna.properties:
        if p.type != 'ENUM' or p.is_readonly or p.identifier == 'type':
            continue
        try:
            items = [i.identifier for i in p.enum_items]
        except (AttributeError, TypeError):
            continue
        if value in items:
            try:
                setattr(node, p.identifier, value)
                return True
            except (TypeError, ValueError):
                pass

    cands = [value, value.capitalize(), value.title(), value.lower()]
    cands += list(_ALIASES.get(value.upper(), ()))
    if probe is not None:
        cands += list(range(8))
    for s in node.inputs:
        if getattr(s, 'type', '') != 'MENU':
            continue
        for c in cands:
            try:
                s.default_value = c
            except (TypeError, ValueError, AttributeError):
                continue
            if probe is None or any(x.name == probe for x in node.inputs):
                return True
    return False


def ensure_help():
    txt = bpy.data.texts.get(HELP_NAME)
    if txt is None:
        txt = bpy.data.texts.new(HELP_NAME)
    txt.clear()
    txt.write(HELP_TEXT)
    return txt


def build_group():
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, 'GeometryNodeTree')
    else:
        ng.nodes.clear()
        ng.interface.clear()

    link = ng.links.new
    warn = []

    def SI(node, name, value):
        if not _set_in(node, name, value):
            warn.append("%s: нет входа '%s' (есть: %s)"
                        % (node.bl_idname, name,
                           [x.name for x in node.inputs]))

    def N(idname, x, y, label=None, probe=None, **props):
        n = ng.nodes.new(idname)
        n.location = (x, y)
        for k, v in props.items():
            if not _set_prop(n, k, v, probe if k == 'mode' else None):
                warn.append("%s.%s = %r" % (idname, k, v))
        if label:
            n.label = label
        return n

    def fmath(op, x, y, label=None):
        return N('ShaderNodeMath', x, y, label, operation=op)

    def vmath(op, x, y, label=None):
        return N('ShaderNodeVectorMath', x, y, label, operation=op)

    # -- интерфейс ----------------------------------------------------
    it = ng.interface
    it.new_socket(name="Геометрия", in_out='OUTPUT',
                  socket_type='NodeSocketGeometry')

    def sock(name, stype, desc=None, **kw):
        s = it.new_socket(name=name, in_out='INPUT', socket_type=stype)
        for k in ('subtype', 'min_value', 'max_value', 'default_value'):
            if k in kw:
                try:
                    setattr(s, k, kw[k])
                except (AttributeError, TypeError):
                    pass
        if desc:
            try:
                s.description = desc
            except (AttributeError, TypeError):
                pass
        if 'mat' in kw:
            m = bpy.data.materials.get(kw['mat'])
            if m is None:
                warn.append("нет материала «%s» — поле оставлено пустым"
                            % kw['mat'])
            else:
                try:
                    s.default_value = m
                except (AttributeError, TypeError):
                    warn.append("не удалось подставить материал «%s»"
                                % kw['mat'])
        return s

    sock("Геометрия", 'NodeSocketGeometry')
    sock("Бордюр по контуру", 'NodeSocketBool', default_value=True,
         desc="Строить бордюр по внешнему краю плоскости")
    sock("Бордюр по внутренним", 'NodeSocketBool', default_value=True,
         desc="Строить бордюр по помеченным рёбрам внутри плоскости — "
              "по центру ребра и только верхней гранью")
    sock("Атрибут рёбер", 'NodeSocketString', default_value=EDGE_ATTR,
         desc="Рёбра с этим атрибутом. sharp_edge — пометка Mark Sharp")
    sock("Ширина", 'NodeSocketFloat', subtype='DISTANCE',
         min_value=0.0, max_value=10.0, default_value=0.15,
         desc="Ширина бордюрного камня, выдерживается и в острых углах")
    sock("Высота", 'NodeSocketFloat', subtype='DISTANCE',
         min_value=0.0, max_value=10.0, default_value=0.15,
         desc="Высота бордюрного камня")
    sock("Сторона", 'NodeSocketBool', default_value=False,
         desc="На какую сторону линии лечь бордюру внешнего контура")
    for i, (nm, rv) in enumerate(((VGROUP + "_1", 0.3),
                                  (VGROUP + "_2", 1.0),
                                  (VGROUP + "_3", 3.0)), 1):
        sock("Группа %d" % i, 'NodeSocketString', default_value=nm,
             desc="Object Data -> Vertex Groups -> «+», назови %s. "
                  "В Edit Mode выдели угловые точки, задай Weight, Assign"
                  % nm)
        sock("Радиус %d" % i, 'NodeSocketFloat', subtype='DISTANCE',
             min_value=0.0, max_value=100.0, default_value=rv,
             desc="Радиус в точке = вес вершины в группе %d x это "
                  "значение. Вес 1 даёт полный радиус, 0.5 половину, "
                  "точки вне группы остаются острыми" % i)
    sock("Сегментов скругления", 'NodeSocketInt',
         min_value=1, max_value=64, default_value=4,
         desc="Гладкость дуги. Для GTA хватает 3-8")
    sock("Строк в текстуре", 'NodeSocketInt',
         min_value=1, max_value=64, default_value=8,
         desc="На сколько горизонтальных строк поделена текстура")
    sock("Строка бока", 'NodeSocketInt',
         min_value=1, max_value=64, default_value=3,
         desc="В какую строку лечь боковой стенке, счёт снизу")
    sock("Строка верха", 'NodeSocketInt',
         min_value=1, max_value=64, default_value=4,
         desc="В какую строку лечь верхней грани, счёт снизу")
    sock("Тайлинг вдоль", 'NodeSocketFloat',
         min_value=0.0, max_value=1000.0, default_value=1.0,
         desc="1 — текстура не искажена. Больше — растянуть вдоль")
    sock("Бок: отразить вдоль", 'NodeSocketBool', default_value=False,
         desc="Зеркально развернуть текстуру боковой стенки по длине")
    sock("Бок: отразить поперёк", 'NodeSocketBool', default_value=False,
         desc="Перевернуть текстуру боковой стенки вверх ногами, "
              "в пределах своей строки")
    sock("Верх: отразить вдоль", 'NodeSocketBool', default_value=False,
         desc="Зеркально развернуть текстуру верхней грани по длине")
    sock("Верх: отразить поперёк", 'NodeSocketBool', default_value=False,
         desc="Развернуть текстуру верхней грани от дальнего края к линии")
    sock("Убрать низ", 'NodeSocketBool', default_value=True,
         desc="Выбросить нижние грани у внешнего бордюра")
    sock("Убрать внутреннюю стенку", 'NodeSocketBool', default_value=True,
         desc="Выбросить у внешнего бордюра стенку, обращённую внутрь")
    sock("Гладкое затенение", 'NodeSocketBool', default_value=True,
         desc="Выключено — плоское затенение")
    sock("Угол автосглаживания", 'NodeSocketFloat', subtype='ANGLE',
         min_value=0.0, max_value=3.14159, default_value=0.523599,
         desc="Рёбра острее этого остаются острыми")
    sock("Триангулировать", 'NodeSocketBool', default_value=False,
         desc="Включи перед экспортом в GTA")
    sock("Материал", 'NodeSocketMaterial', desc="Материал бордюра",
         mat=MAT_CURB)
    sock("Заливка внутри", 'NodeSocketBool', default_value=True,
         desc="Заполнить ячейки поверхностью вровень с верхом бордюра")
    sock("Материал травы", 'NodeSocketMaterial',
         desc="Материал заливки внутри бордюра", mat=MAT_GRASS)
    sock("Слот тротуара", 'NodeSocketInt',
         min_value=0, max_value=32, default_value=1,
         desc="Грани с этим слотом материала считаются тротуаром. "
              "В Edit Mode выдели грани и нажми Assign на нужном слоте")
    sock("Материал тротуара", 'NodeSocketMaterial',
         desc="Материал заливки на помеченных гранях", mat=MAT_WALK)
    sock("Тайлинг заливки", 'NodeSocketFloat',
         min_value=0.0, max_value=1000.0, default_value=1.0,
         desc="Повторов текстуры на метр у заливки. Развёртка планарная, "
              "проекцией сверху")

    gi = N('NodeGroupInput', -2600, 0)
    go = N('NodeGroupOutput', 1200, 0)

    def G(name):
        return _out(gi, name)

    # Сдвиг сечения по высоте — константа, из интерфейса убран: при
    # высоте 0.15 значение 0.075 ставит низ бордюра ровно на плоскость,
    # а верх на 0.15 над ней.
    hoffn = N('ShaderNodeValue', -2400, 1060, "сдвиг по высоте")
    hoffn.outputs[0].default_value = 0.075

    def HOFF():
        return hoffn.outputs[0]

    # -- общее: масштаб текстуры от высоты строки ----------------------
    rows = fmath('MAXIMUM', -2400, 900, "строк, не ноль")
    link(G("Строк в текстуре"), rows.inputs[0])
    rows.inputs[1].default_value = 1.0
    rowh = fmath('DIVIDE', -2220, 900, "высота строки")
    rowh.inputs[0].default_value = 1.0
    link(rows.outputs[0], rowh.inputs[1])
    hsafe = fmath('MAXIMUM', -2400, 760, "высота, не ноль")
    link(G("Высота"), hsafe.inputs[0])
    hsafe.inputs[1].default_value = 1e-6
    kden = fmath('DIVIDE', -2040, 900, "единиц текстуры на метр")
    link(rowh.outputs[0], kden.inputs[0])
    link(hsafe.outputs[0], kden.inputs[1])

    def row_base(sock_name, x, y):
        m1 = fmath('SUBTRACT', x, y, "номер строки минус один")
        link(G(sock_name), m1.inputs[0])
        m1.inputs[1].default_value = 1.0
        b = fmath('MULTIPLY', x + 180, y, "низ строки")
        link(m1.outputs[0], b.inputs[0])
        link(rowh.outputs[0], b.inputs[1])
        return b

    # -- общее: вектор «внутрь плоскости» ------------------------------
    # Позиция на домене граней — центр грани. Прочитанная на домене
    # вершин, она усредняется по смежным граням, то есть смотрит внутрь
    # плоскости. Нужна только для разворота нормалей: у стенки правильная
    # нормаль смотрит прочь от участка. Работает и на внешнем контуре, и
    # на отверстии — грань всегда со стороны плиты.
    IN_ATTR = "curb_in"
    mpos = N('GeometryNodeInputPosition', -2400, 60)
    fcen = N('GeometryNodeFieldOnDomain', -2220, 60, "центр грани",
             data_type='FLOAT_VECTOR', domain='FACE')
    link(mpos.outputs[0], _in(fcen, "Value"))
    inw = vmath('SUBTRACT', -2040, 60, "внутрь плоскости")
    link(_out(fcen, "Value"), inw.inputs[0])
    link(mpos.outputs[0], inw.inputs[1])
    inflat = vmath('MULTIPLY', -1860, 60, "в плане")
    link(inw.outputs[0], inflat.inputs[0])
    inflat.inputs[1].default_value = (1.0, 1.0, 0.0)
    # Входящий UVMap исходного меша надо снять. Он едет вместе с заливкой
    # в склейку, и тогда мой слой поверх него не ложится — на бордюре
    # оказывается развёртка самой плоскости, то есть полосы. Без заливки
    # этого слоя в результате нет, поэтому и проблемы не было.
    drop = N('GeometryNodeRemoveAttribute', -2220, -100, "снять старый UV")
    link(G("Геометрия"), _in(drop, "Geometry"))
    SI(drop, "Name", UV_NAME)

    keep = N('GeometryNodeStoreNamedAttribute', -2040, -100,
             "запомнить вектор", data_type='FLOAT_VECTOR', domain='POINT')
    link(_out(drop, "Geometry"), _in(keep, "Geometry"))
    SI(keep, "Name", IN_ATTR)
    link(inflat.outputs[0], _in(keep, "Value"))
    src_geo = _out(keep, "Geometry")

    # -- общее: радиус скругления в точке ------------------------------
    # Три группы вершин, у каждой свой радиус в метрах; вес вершины
    # масштабирует его от нуля до этого значения. В точке берётся
    # максимум по группам — попадание в две даёт больший радиус, а не
    # сумму. Поле одно на всё: им пользуются обе ветки бордюра и заливка.
    _rads = []
    for i in (1, 2, 3):
        w = N('GeometryNodeInputNamedAttribute', -2400, 300 + i * 140,
              "вес в группе %d" % i, data_type='FLOAT')
        link(G("Группа %d" % i), _in(w, "Name"))
        r = fmath('MULTIPLY', -2220, 300 + i * 140, "радиус %d" % i)
        link(_out(w, "Attribute"), r.inputs[0])
        link(G("Радиус %d" % i), r.inputs[1])
        _rads.append(r)
    _rmax = fmath('MAXIMUM', -2040, 580, "больший из 1 и 2")
    link(_rads[0].outputs[0], _rmax.inputs[0])
    link(_rads[1].outputs[0], _rmax.inputs[1])
    rad_node = fmath('MAXIMUM', -1860, 580, "радиус в точке")
    link(_rmax.outputs[0], rad_node.inputs[0])
    link(_rads[2].outputs[0], rad_node.inputs[1])
    rad_out = rad_node.outputs[0]

    # -- общее: выбор рёбер -------------------------------------------
    marked = N('GeometryNodeInputNamedAttribute', -2400, 520,
               "помеченные рёбра", data_type='BOOLEAN')
    link(G("Атрибут рёбер"), _in(marked, "Name"))
    en = N('GeometryNodeInputMeshEdgeNeighbors', -2400, 380)
    isrim = N('FunctionNodeCompare', -2220, 380, "ребро контура",
              data_type='INT', operation='LESS_EQUAL')
    link(_out(en, "Face Count"), _in(isrim, "A"))
    SI(isrim, "B", 1)
    isinner = N('FunctionNodeBooleanMath', -2220, 240, "ребро внутри",
                operation='NOT')
    link(_out(isrim, "Result"), isinner.inputs[0])

    # -- грани тротуара, помеченные слотом материала -------------------
    # Ребро на границе участка: с одной стороны тротуар, с другой нет.
    # Доля тротуара, прочитанная на домене рёбер, усредняется по двум
    # смежным граням — на границе она даёт ровно половину.
    wmat = N('GeometryNodeInputMaterialIndex', -2400, 100)
    wis = N('FunctionNodeCompare', -2220, 100, "грань тротуара",
            data_type='INT', operation='EQUAL')
    link(_out(wmat, "Material Index"), _in(wis, "A"))
    link(G("Слот тротуара"), _in(wis, "B"))
    wf = N('GeometryNodeSwitch', -2040, 100, "тротуар как число",
           input_type='FLOAT')
    link(_out(wis, "Result"), _in(wf, "Switch"))
    SI(wf, "False", 0.0)
    SI(wf, "True", 1.0)
    # Обязательный шаг: сравнение вычисляется на домене ГРАНЕЙ. Без него
    # Blender усреднит сам индекс материала по двум смежным граням, и на
    # границе выйдет 0.5 — не равно ни одному слоту, границы не будет.
    wface = N('GeometryNodeFieldOnDomain', -1950, 100, "на гранях",
              data_type='FLOAT', domain='FACE')
    link(_out(wf, "Output"), _in(wface, "Value"))
    wedge = N('GeometryNodeFieldOnDomain', -1860, 100, "доля по ребру",
              data_type='FLOAT', domain='EDGE')
    link(_out(wface, "Value"), _in(wedge, "Value"))
    wdif = fmath('SUBTRACT', -1680, 100, "отклонение от половины")
    link(_out(wedge, "Value"), wdif.inputs[0])
    wdif.inputs[1].default_value = 0.5
    wabs = fmath('ABSOLUTE', -1500, 100)
    link(wdif.outputs[0], wabs.inputs[0])
    wbord = N('FunctionNodeCompare', -1320, 100, "граница тротуара",
              data_type='FLOAT', operation='LESS_THAN')
    link(wabs.outputs[0], _in(wbord, "A"))
    SI(wbord, "B", 0.25)

    # Куда смещать тротуарную ленту: к центру помеченной грани. Средние
    # берутся с весом «грань тротуара», поэтому в числителе оказывается
    # центр только помеченной грани, а деление на долю его нормирует.
    wpos = N('GeometryNodeInputPosition', -1320, -100)
    wnumv = vmath('SCALE', -1140, -100, "центр с весом")
    link(wpos.outputs[0], wnumv.inputs[0])
    link(_out(wface, "Value"), _in(wnumv, "Scale"))
    wnum = N('GeometryNodeFieldOnDomain', -960, -100, "сумма центров",
             data_type='FLOAT_VECTOR', domain='FACE')
    link(wnumv.outputs[0], _in(wnum, "Value"))
    wden = N('GeometryNodeFieldOnDomain', -960, -240, "доля тротуара",
             data_type='FLOAT', domain='FACE')
    link(_out(wface, "Value"), _in(wden, "Value"))
    wdcl = fmath('MAXIMUM', -780, -240, "не ноль")
    link(_out(wden, "Value"), wdcl.inputs[0])
    wdcl.inputs[1].default_value = 1e-4
    winv = fmath('DIVIDE', -600, -240, "нормировка")
    winv.inputs[0].default_value = 1.0
    link(wdcl.outputs[0], winv.inputs[1])
    wcen = vmath('SCALE', -600, -100, "центр грани тротуара")
    link(_out(wnum, "Value"), wcen.inputs[0])
    link(winv.outputs[0], _in(wcen, "Scale"))
    wsub = vmath('SUBTRACT', -420, -100, "в сторону тротуара")
    link(wcen.outputs[0], wsub.inputs[0])
    link(wpos.outputs[0], wsub.inputs[1])
    wflat = vmath('MULTIPLY', -240, -100, "в плане")
    link(wsub.outputs[0], wflat.inputs[0])
    wflat.inputs[1].default_value = (1.0, 1.0, 0.0)
    wstore = N('GeometryNodeStoreNamedAttribute', -1860, -100,
               "запомнить направление", data_type='FLOAT_VECTOR',
               domain='POINT')
    link(src_geo, _in(wstore, "Geometry"))
    SI(wstore, "Name", WDIR_ATTR)
    link(wflat.outputs[0], _in(wstore, "Value"))
    src_geo = _out(wstore, "Geometry")

    # Внешний контур: край плоскости, если включён, плюс помеченные
    # рёбра, которые лежат на краю.
    rim_or = N('FunctionNodeBooleanMath', -2040, 520, "контур или пометка",
               operation='OR')
    link(G("Бордюр по контуру"), rim_or.inputs[0])
    link(_out(marked, "Attribute"), rim_or.inputs[1])
    sel_out = N('FunctionNodeBooleanMath', -1860, 520, "внешние рёбра",
                operation='AND')
    link(rim_or.outputs[0], sel_out.inputs[0])
    link(_out(isrim, "Result"), sel_out.inputs[1])

    # Внутренние: только помеченные, и только те, что не на краю.
    inner_on = N('FunctionNodeBooleanMath', -2040, 240, "внутренние включены",
                 operation='AND')
    link(G("Бордюр по внутренним"), inner_on.inputs[0])
    link(_out(marked, "Attribute"), inner_on.inputs[1])
    sel_in = N('FunctionNodeBooleanMath', -1860, 240, "внутренние рёбра",
               operation='AND')
    link(inner_on.outputs[0], sel_in.inputs[0])
    link(_out(isinner, "Boolean"), sel_in.inputs[1])

    # Граница тротуара — своя ветка: бордюр лежит внутри тротуара,
    # со стенкой и верхом, а не серединной лентой.
    sel_walk = N('FunctionNodeBooleanMath', -1860, 100, "рёбра тротуара",
                 operation='AND')
    link(_out(wbord, "Result"), sel_walk.inputs[0])
    link(_out(isinner, "Boolean"), sel_walk.inputs[1])

    # Проволочный контур участка — цель для замера расстояния при
    # обрезке ленты тротуара.
    rimc = N('GeometryNodeMeshToCurve', -1680, -100, "контур участка",
             mode='EDGES')
    link(src_geo, _in(rimc, "Mesh"))
    link(_out(sel_out, "Boolean"), _in(rimc, "Selection"))
    rimw = N('GeometryNodeCurveToMesh', -1500, -100, "контур в рёбра")
    link(_out(rimc, "Curve"), _in(rimw, "Curve"))

    # -- одна ветка бордюра --------------------------------------------

    def branch(tag, sel_socket, centered, only_top, y0,
               side_socket="Сторона", shift_attr=None, trim_ends=False,
               clip_rim=False):
        """Строит бордюр по выбранным рёбрам.

        centered — профиль по центру линии (внутренние рёбра) или целиком
        с одной стороны (внешний контур).
        only_top — оставить одну верхнюю грань.
        """
        ua_n = "%s_u" % tag          # длина вдоль линии
        za_n = "%s_z" % tag          # уровень линии
        la_n = "%s_lvl" % tag        # высота точки профиля
        da_n = PD_ATTR               # удаление точки профиля от линии
        ma_n = "%s_miter" % tag      # масштаб профиля в изломе
        pa_n = "%s_p0" % tag         # позиция точки линии
        sa_n = "%s_len" % tag        # длина сплайна
        ta_n = "%s_tan" % tag        # касательная линии

        def A(name, x, y, dtype='FLOAT', label=None):
            n = N('GeometryNodeInputNamedAttribute', x, y, label,
                  data_type=dtype)
            SI(n, "Name", name)
            return n

        def ST(geo, name, value, x, y, dtype='FLOAT', label=None):
            s = N('GeometryNodeStoreNamedAttribute', x, y, label,
                  data_type=dtype, domain='POINT')
            link(geo, _in(s, "Geometry"))
            SI(s, "Name", name)
            link(value, _in(s, "Value"))
            return _out(s, "Geometry")

        # линия
        m2c = N('GeometryNodeMeshToCurve', -1660, y0, "%s: линия" % tag,
                mode='EDGES')
        link(src_geo, _in(m2c, "Mesh"))
        link(sel_socket, _in(m2c, "Selection"))

        # скругление по весам группы вершин
        # Три группы вершин, у каждой свой радиус в метрах; вес вершины
        # масштабирует его от нуля до этого значения. В точке берётся
        # максимум по группам — попадание в две даёт больший радиус,
        # а не сумму.
        fil = N('GeometryNodeFilletCurve', -1480, y0, "%s: скругление" % tag,
                probe='Count', mode='POLY')
        link(_out(m2c, "Curve"), _in(fil, "Curve"))
        link(rad_out, _in(fil, "Radius"))
        SI(fil, "Limit Radius", True)
        if _set_in(fil, "Count", 4):
            link(G("Сегментов скругления"), _in(fil, "Count"))
        else:
            warn.append("Fillet Curve: нет входа 'Count'")

        # атрибуты линии
        # Обрезка концов на ширину бордюра: у незамкнутой линии концы
        # упираются в край участка, где стоит основной бордюр. У
        # замкнутых контуров обрезать нечего, и Trim Curve их разомкнул
        # бы — поэтому там оба конца остаются на месте.
        curve_geo = _out(fil, "Curve")
        if clip_rim:
            # Мелко делим: у прямой границы всего две точки, удалять
            # нечего. Шаг задаёт и точность обрезки, и порог сварки.
            rs = N('GeometryNodeResampleCurve', -1540, y0, "%s: дробление"
                   % tag, mode='LENGTH')
            link(curve_geo, _in(rs, "Curve"))
            SI(rs, "Length", CLIP_STEP)
            prox = N('GeometryNodeProximity', -1540, y0 + 560,
                     "до контура участка", target_element='EDGES')
            link(_out(rimw, "Mesh"), _in(prox, "Target"))
            near = N('FunctionNodeCompare', -1360, y0 + 560,
                     "внутри полосы бордюра", data_type='FLOAT',
                     operation='LESS_THAN')
            link(_out(prox, "Distance"), _in(near, "A"))
            link(G("Ширина"), _in(near, "B"))
            cut = N('GeometryNodeDeleteGeometry', -1360, y0,
                    "%s: убрать нахлёст" % tag, domain='POINT', mode='ALL')
            link(_out(rs, "Curve"), _in(cut, "Geometry"))
            link(_out(near, "Result"), _in(cut, "Selection"))
            curve_geo = _out(cut, "Geometry")
        if trim_ends:
            tlen = N('GeometryNodeSplineLength', -1360, y0 + 560)
            tcyc = N('GeometryNodeInputSplineCyclic', -1360, y0 + 700)
            tst = N('GeometryNodeSwitch', -1180, y0 + 700, "начало",
                    input_type='FLOAT')
            link(_out(tcyc, "Cyclic"), _in(tst, "Switch"))
            link(G("Ширина"), _in(tst, "False"))
            SI(tst, "True", 0.0)
            tsub = fmath('SUBTRACT', -1180, y0 + 560, "конец без ширины")
            link(_out(tlen, "Length"), tsub.inputs[0])
            link(G("Ширина"), tsub.inputs[1])
            ten = N('GeometryNodeSwitch', -1000, y0 + 560, "конец",
                    input_type='FLOAT')
            link(_out(tcyc, "Cyclic"), _in(ten, "Switch"))
            link(tsub.outputs[0], _in(ten, "False"))
            link(_out(tlen, "Length"), _in(ten, "True"))
            trim = N('GeometryNodeTrimCurve', -1360, y0, "%s: обрезка" % tag,
                     mode='LENGTH')
            link(curve_geo, _in(trim, "Curve"))
            link(_out(tst, "Output"), _in(trim, "Start"))
            link(_out(ten, "Output"), _in(trim, "End"))
            curve_geo = _out(trim, "Curve")

        sp = N('GeometryNodeSplineParameter', -1300, y0 + 300)
        geo = ST(curve_geo, ua_n, _out(sp, "Length"),
                 -1300, y0, 'FLOAT', "U вдоль линии")
        sl = N('GeometryNodeSplineLength', -1120, y0 + 300)
        geo = ST(geo, sa_n, _out(sl, "Length"),
                 -1120, y0, 'FLOAT', "длина сплайна")
        tn = N('GeometryNodeInputTangent', -940, y0 + 300)
        geo = ST(geo, ta_n, tn.outputs[0],
                 -940, y0, 'FLOAT_VECTOR', "касательная")
        pp = N('GeometryNodeInputPosition', -760, y0 + 300)
        geo = ST(geo, pa_n, pp.outputs[0],
                 -760, y0, 'FLOAT_VECTOR', "позиция линии")
        zp = N('ShaderNodeSeparateXYZ', -580, y0 + 300)
        link(pp.outputs[0], zp.inputs[0])
        geo = ST(geo, za_n, zp.outputs['Z'],
                 -580, y0, 'FLOAT', "уровень линии")

        # митра: линия в рёбра, счёт, обратно в кривую
        wire = N('GeometryNodeCurveToMesh', -400, y0, "%s: в рёбра" % tag)
        link(geo, _in(wire, "Curve"))
        ev = N('GeometryNodeInputMeshEdgeVertices', -1660, y0 - 400)
        ed = vmath('SUBTRACT', -1480, y0 - 400, "направление ребра")
        link(_out(ev, "Position 2"), ed.inputs[0])
        link(_out(ev, "Position 1"), ed.inputs[1])
        edf = vmath('MULTIPLY', -1300, y0 - 400, "в плане")
        link(ed.outputs[0], edf.inputs[0])
        edf.inputs[1].default_value = (1.0, 1.0, 0.0)
        ep = vmath('CROSS_PRODUCT', -1120, y0 - 400, "перпендикуляр ребра")
        link(edf.outputs[0], ep.inputs[0])
        ep.inputs[1].default_value = (0.0, 0.0, 1.0)
        epn = vmath('NORMALIZE', -940, y0 - 400)
        link(ep.outputs[0], epn.inputs[0])
        avg = N('GeometryNodeFieldOnDomain', -760, y0 - 400,
                "среднее по рёбрам", data_type='FLOAT_VECTOR', domain='EDGE')
        link(epn.outputs[0], _in(avg, "Value"))
        alen = vmath('LENGTH', -580, y0 - 400, "cos(угол/2)")
        link(_out(avg, "Value"), alen.inputs[0])
        acl = fmath('MAXIMUM', -400, y0 - 400, "не ноль")
        link(_out(alen, "Value"), acl.inputs[0])
        acl.inputs[1].default_value = MITER_EPS
        mit = fmath('DIVIDE', -220, y0 - 400, "масштаб профиля")
        mit.inputs[0].default_value = 1.0
        link(acl.outputs[0], mit.inputs[1])
        wgeo = ST(_out(wire, "Mesh"), ma_n, mit.outputs[0],
                  -220, y0, 'FLOAT', "митра")
        # Смещение линии вбок на половину ширины — тем же митровым
        # расчётом, что и сама митра: перпендикуляры рёбер уже усреднены
        # в avg, длина сдвига = половина ширины / |avg|^2. Знак берётся
        # из направления к помеченной грани, поэтому сторона получается
        # автоматически на каждом контуре, а не одной галочкой на все.
        if shift_attr is not None:
            wda = A(shift_attr, -220, y0 - 700, 'FLOAT_VECTOR',
                    "в сторону тротуара")
            sdt = vmath('DOT_PRODUCT', -40, y0 - 700, "куда смещать")
            link(_out(avg, "Value"), sdt.inputs[0])
            link(_out(wda, "Attribute"), sdt.inputs[1])
            ssg = fmath('SIGN', 140, y0 - 700, "знак")
            link(_out(sdt, "Value"), ssg.inputs[0])
            shw = fmath('MULTIPLY', -220, y0 - 840, "половина ширины")
            link(G("Ширина"), shw.inputs[0])
            shw.inputs[1].default_value = 0.5
            shs = fmath('MULTIPLY', 320, y0 - 840, "со знаком")
            link(shw.outputs[0], shs.inputs[0])
            link(ssg.outputs[0], shs.inputs[1])
            sl2 = vmath('DOT_PRODUCT', 140, y0 - 980, "|avg| в квадрате")
            link(_out(avg, "Value"), sl2.inputs[0])
            link(_out(avg, "Value"), sl2.inputs[1])
            slc = fmath('MAXIMUM', 320, y0 - 980, "не ноль")
            link(_out(sl2, "Value"), slc.inputs[0])
            slc.inputs[1].default_value = MITER_EPS
            ssc = fmath('DIVIDE', 500, y0 - 840, "длина сдвига")
            link(shs.outputs[0], ssc.inputs[0])
            link(slc.outputs[0], ssc.inputs[1])
            sof = vmath('SCALE', 680, y0 - 840, "сдвиг вбок")
            link(_out(avg, "Value"), sof.inputs[0])
            link(ssc.outputs[0], _in(sof, "Scale"))
            smv = N('GeometryNodeSetPosition', -120, y0, "%s: вбок" % tag)
            link(wgeo, _in(smv, "Geometry"))
            link(sof.outputs[0], _in(smv, "Offset"))
            wgeo = _out(smv, "Geometry")

        back = N('GeometryNodeMeshToCurve', -40, y0, "%s: в кривую" % tag,
                 mode='EDGES')
        link(wgeo, _in(back, "Mesh"))

        # профиль
        quad = N('GeometryNodeCurvePrimitiveQuadrilateral', -1660, y0 - 800,
                 "%s: профиль" % tag, mode='RECTANGLE')
        link(G("Ширина"), _in(quad, "Width"))
        link(G("Высота"), _in(quad, "Height"))
        if centered:
            dx = fmath('MULTIPLY', -1480, y0 - 960, "по центру ребра")
            link(G("Ширина"), dx.inputs[0])
            dx.inputs[1].default_value = 0.0
        else:
            # Явный переключатель вместо арифметики на булевом входе:
            # не полагаемся на неявное превращение галочки в 0/1.
            sf = N('GeometryNodeSwitch', -1660, y0 - 960, "сторона +-1",
                   input_type='FLOAT')
            link(G(side_socket), _in(sf, "Switch"))
            SI(sf, "False", 1.0)
            SI(sf, "True", -1.0)
            hw = fmath('MULTIPLY', -1480, y0 - 1100, "половина ширины")
            link(G("Ширина"), hw.inputs[0])
            hw.inputs[1].default_value = 0.5
            dx = fmath('MULTIPLY', -1300, y0 - 960, "сдвиг вбок")
            link(hw.outputs[0], dx.inputs[0])
            link(_out(sf, "Output"), dx.inputs[1])
        shift = N('ShaderNodeCombineXYZ', -1120, y0 - 960)
        link(dx.outputs[0], shift.inputs['X'])
        link(HOFF(), shift.inputs['Y'])
        lift = N('GeometryNodeSetPosition', -1120, y0 - 800, "посадка")
        link(_out(quad, "Curve"), _in(lift, "Geometry"))
        link(shift.outputs[0], _in(lift, "Offset"))

        # уровень точки профиля и её удаление от ближнего края сечения
        lp = N('GeometryNodeInputPosition', -940, y0 - 640)
        ls = N('ShaderNodeSeparateXYZ', -760, y0 - 640)
        link(lp.outputs[0], ls.inputs[0])
        pgeo = ST(_out(lift, "Geometry"), la_n, ls.outputs['Y'],
                  -940, y0 - 800, 'FLOAT', "уровень профиля")
        if centered:
            # Профиль стоит по центру линии, X идёт от -W/2 до +W/2.
            # Сдвигаем на половину ширины, чтобы поперёк верхней грани
            # величина росла монотонно от края до края — иначе развёртка
            # зеркалилась бы по середине.
            hw2 = fmath('MULTIPLY', -760, y0 - 1100, "половина ширины")
            link(G("Ширина"), hw2.inputs[0])
            hw2.inputs[1].default_value = 0.5
            pdv = fmath('ADD', -580, y0 - 960, "поперёк сечения")
            link(ls.outputs['X'], pdv.inputs[0])
            link(hw2.outputs[0], pdv.inputs[1])
        else:
            # Удаление от САМОЙ ЛИНИИ: у неё X ровно ноль, поэтому модуль
            # даёт расстояние независимо от того, в какую сторону лёг
            # профиль. Раньше я мерил от вычисленного края сечения, а он
            # зависит от знака сдвига — при одном знаке «дальней» стенкой
            # оказывалась та, что стоит на линии, и удалялась именно она.
            pdv = fmath('ABSOLUTE', -580, y0 - 960, "удаление от линии")
            link(ls.outputs['X'], pdv.inputs[0])
        pgeo = ST(pgeo, da_n, pdv.outputs[0],
                  -400, y0 - 800, 'FLOAT', "удаление от линии")

        # протяжка
        c2m = N('GeometryNodeCurveToMesh', 140, y0, "%s: бордюр" % tag)
        link(_out(back, "Curve"), _in(c2m, "Curve"))
        link(pgeo, _in(c2m, "Profile Curve"))
        ma = A(ma_n, -40, y0 - 260, 'FLOAT', "митра")
        sc = _find_in(c2m, "Scale")
        if sc is not None:
            link(_out(ma, "Attribute"), sc)
        else:
            setr = N('GeometryNodeSetCurveRadius', -40, y0 + 200, "митра")
            link(_out(back, "Curve"), _in(setr, "Curve"))
            link(_out(ma, "Attribute"), _in(setr, "Radius"))
            link(_out(setr, "Curve"), _in(c2m, "Curve"))

        # вернуть высоту, растянутую масштабом
        za = A(za_n, 140, y0 - 400, 'FLOAT')
        la = A(la_n, 140, y0 - 540, 'FLOAT')
        zsum = fmath('ADD', 320, y0 - 470, "верная высота")
        link(_out(za, "Attribute"), zsum.inputs[0])
        link(_out(la, "Attribute"), zsum.inputs[1])
        mp = N('GeometryNodeInputPosition', 140, y0 - 680)
        ms = N('ShaderNodeSeparateXYZ', 320, y0 - 680)
        link(mp.outputs[0], ms.inputs[0])
        mx = N('ShaderNodeCombineXYZ', 500, y0 - 560)
        link(ms.outputs['X'], mx.inputs['X'])
        link(ms.outputs['Y'], mx.inputs['Y'])
        link(zsum.outputs[0], mx.inputs['Z'])
        fixz = N('GeometryNodeSetPosition', 320, y0, "высота на место")
        link(_out(c2m, "Mesh"), _in(fixz, "Geometry"))
        link(mx.outputs[0], _in(fixz, "Position"))

        # какая грань верхняя: по средней высоте её вершин, именно по
        # средней — вершина верхнего ребра принадлежит и стенке тоже
        flvl = N('GeometryNodeFieldOnDomain', 140, y0 - 820, "высота грани",
                 data_type='FLOAT', domain='FACE')
        link(_out(la, "Attribute"), _in(flvl, "Value"))
        hq = fmath('MULTIPLY', 140, y0 - 960, "четверть высоты")
        link(G("Высота"), hq.inputs[0])
        hq.inputs[1].default_value = 0.25
        tthr = fmath('ADD', 320, y0 - 960, "порог верха")
        link(HOFF(), tthr.inputs[0])
        link(hq.outputs[0], tthr.inputs[1])
        istop = N('FunctionNodeCompare', 500, y0 - 880, "это верх",
                  data_type='FLOAT', operation='GREATER_THAN')
        link(_out(flvl, "Value"), _in(istop, "A"))
        link(tthr.outputs[0], _in(istop, "B"))

        pda = A(da_n, 140, y0 - 1100, 'FLOAT')
        if only_top:
            # всё, кроме верха: стенки и низ закроются травой и тротуаром
            dsel = N('FunctionNodeBooleanMath', 680, y0 - 880, "всё кроме верха",
                     operation='NOT')
            link(_out(istop, "Result"), dsel.inputs[0])
            dsel_out = _out(dsel, "Boolean")
        else:
            wthr = fmath('MULTIPLY', 320, y0 - 1100, "3/4 ширины")
            link(G("Ширина"), wthr.inputs[0])
            wthr.inputs[1].default_value = 0.75
            isfar = N('FunctionNodeCompare', 500, y0 - 1100, "дальняя стенка",
                      data_type='FLOAT', operation='GREATER_THAN')
            link(_out(pda, "Attribute"), _in(isfar, "A"))
            link(wthr.outputs[0], _in(isfar, "B"))
            hq2b = fmath('SUBTRACT', 320, y0 - 1240, "порог низа")
            link(HOFF(), hq2b.inputs[0])
            link(hq.outputs[0], hq2b.inputs[1])
            isbot = N('FunctionNodeCompare', 500, y0 - 1240, "низ",
                      data_type='FLOAT', operation='LESS_THAN')
            link(_out(flvl, "Value"), _in(isbot, "A"))
            link(hq2b.outputs[0], _in(isbot, "B"))
            dfar = N('FunctionNodeBooleanMath', 680, y0 - 1100, "стенку убрать",
                     operation='AND')
            link(G("Убрать внутреннюю стенку"), dfar.inputs[0])
            link(_out(isfar, "Result"), dfar.inputs[1])
            dbot = N('FunctionNodeBooleanMath', 680, y0 - 1240, "низ убрать",
                     operation='AND')
            link(G("Убрать низ"), dbot.inputs[0])
            link(_out(isbot, "Result"), dbot.inputs[1])
            dor = N('FunctionNodeBooleanMath', 860, y0 - 1170, "что убрать",
                    operation='OR')
            link(_out(dfar, "Boolean"), dor.inputs[0])
            link(_out(dbot, "Boolean"), dor.inputs[1])
            dsel_out = _out(dor, "Boolean")

        dele = N('GeometryNodeDeleteGeometry', 500, y0, "%s: лишние грани" % tag,
                 domain='FACE', mode='ALL')
        link(_out(fixz, "Geometry"), _in(dele, "Geometry"))
        link(dsel_out, _in(dele, "Selection"))

        # Нормали. У трубы из «Кривую в меш» ориентация зависит от
        # направления обхода линии, а у внешнего контура и у отверстия оно
        # противоположное — глобальным разворотом не обойтись. Считаем по
        # геометрии: у верхней грани нормаль смотрит вверх, у стенки —
        # прочь от плоскости участка. Уже правильные грани не трогаются.
        ina = A(IN_ATTR, 680, y0 - 400, 'FLOAT_VECTOR', "внутрь плоскости")
        inn = vmath('NORMALIZE', 860, y0 - 400)
        link(_out(ina, "Attribute"), inn.inputs[0])
        outw = vmath('SCALE', 1040, y0 - 400, "прочь от участка")
        link(inn.outputs[0], outw.inputs[0])
        SI(outw, "Scale", -1.0)
        upv = N('ShaderNodeCombineXYZ', 1040, y0 - 540)
        upv.inputs['Z'].default_value = 1.0
        nref = N('GeometryNodeSwitch', 1220, y0 - 460, "куда смотреть",
                 input_type='VECTOR')
        link(_out(istop, "Result"), _in(nref, "Switch"))
        link(outw.outputs[0], _in(nref, "False"))
        link(upv.outputs[0], _in(nref, "True"))
        fnrm = N('GeometryNodeInputNormal', 1220, y0 - 620)
        ndot = vmath('DOT_PRODUCT', 1400, y0 - 460, "смотрит внутрь")
        link(fnrm.outputs[0], ndot.inputs[0])
        link(_out(nref, "Output"), ndot.inputs[1])
        nbad = N('FunctionNodeCompare', 1580, y0 - 460, "развернуть",
                 data_type='FLOAT', operation='LESS_THAN')
        link(_out(ndot, "Value"), _in(nbad, "A"))
        SI(nbad, "B", 0.0)
        flip = N('GeometryNodeFlipFaces', 680, y0, "%s: нормали" % tag)
        link(_out(dele, "Geometry"), _in(flip, "Mesh"))
        link(_out(nbad, "Result"), _in(flip, "Selection"))

        # -- UV --------------------------------------------------------
        ua = A(ua_n, 140, y0 - 1400, 'FLOAT')
        sla = A(sa_n, 140, y0 - 1540, 'FLOAT')
        p0a = A(pa_n, 140, y0 - 1680, 'FLOAT_VECTOR')
        tana = A(ta_n, 140, y0 - 1820, 'FLOAT_VECTOR')

        # шов замкнутого контура: длина скачет с периметра обратно в ноль
        uavg = N('GeometryNodeFieldOnDomain', 320, y0 - 1400,
                 "среднее U по грани", data_type='FLOAT', domain='FACE')
        link(_out(ua, "Attribute"), _in(uavg, "Value"))
        udif = fmath('SUBTRACT', 500, y0 - 1400, "ниже среднего")
        link(_out(uavg, "Value"), udif.inputs[0])
        link(_out(ua, "Attribute"), udif.inputs[1])
        uq = fmath('MULTIPLY', 500, y0 - 1540, "четверть периметра")
        link(_out(sla, "Attribute"), uq.inputs[0])
        uq.inputs[1].default_value = 0.25
        uwr = N('FunctionNodeCompare', 680, y0 - 1470, "угол за швом",
                data_type='FLOAT', operation='GREATER_THAN')
        link(udif.outputs[0], _in(uwr, "A"))
        link(uq.outputs[0], _in(uwr, "B"))
        uad = fmath('MULTIPLY', 860, y0 - 1470, "прибавка периметра")
        link(_out(uwr, "Result"), uad.inputs[0])
        link(_out(sla, "Attribute"), uad.inputs[1])
        useam = fmath('ADD', 1040, y0 - 1470, "U без шва")
        link(_out(ua, "Attribute"), useam.inputs[0])
        link(uad.outputs[0], useam.inputs[1])

        # скос на концах островов
        npos = N('GeometryNodeInputPosition', 320, y0 - 1680)
        away = vmath('SUBTRACT', 500, y0 - 1680, "отъезд вбок")
        link(npos.outputs[0], away.inputs[0])
        link(_out(p0a, "Attribute"), away.inputs[1])
        awayf = vmath('MULTIPLY', 680, y0 - 1680, "в плане")
        link(away.outputs[0], awayf.inputs[0])
        awayf.inputs[1].default_value = (1.0, 1.0, 0.0)
        fp0 = N('GeometryNodeFieldOnDomain', 320, y0 - 1820,
                "линия по грани", data_type='FLOAT_VECTOR', domain='FACE')
        link(_out(p0a, "Attribute"), _in(fp0, "Value"))
        fdir = vmath('SUBTRACT', 500, y0 - 1820, "к середине грани")
        link(_out(fp0, "Value"), fdir.inputs[0])
        link(_out(p0a, "Attribute"), fdir.inputs[1])
        fdirf = vmath('MULTIPLY', 680, y0 - 1820, "в плане")
        link(fdir.outputs[0], fdirf.inputs[0])
        fdirf.inputs[1].default_value = (1.0, 1.0, 0.0)
        fdirn = vmath('NORMALIZE', 860, y0 - 1820)
        link(fdirf.outputs[0], fdirn.inputs[0])
        tanf = vmath('MULTIPLY', 680, y0 - 1960, "касательная в плане")
        link(_out(tana, "Attribute"), tanf.inputs[0])
        tanf.inputs[1].default_value = (1.0, 1.0, 0.0)
        fdot = vmath('DOT_PRODUCT', 860, y0 - 1960, "вперёд или назад")
        link(fdirf.outputs[0], fdot.inputs[0])
        link(tanf.outputs[0], fdot.inputs[1])
        fsgn = fmath('SIGN', 1040, y0 - 1960, "знак")
        link(_out(fdot, "Value"), fsgn.inputs[0])
        fwd = vmath('SCALE', 1040, y0 - 1820, "вперёд")
        link(fdirn.outputs[0], fwd.inputs[0])
        link(fsgn.outputs[0], _in(fwd, "Scale"))
        ush = vmath('DOT_PRODUCT', 1220, y0 - 1680, "скос")
        link(awayf.outputs[0], ush.inputs[0])
        link(fwd.outputs[0], ush.inputs[1])
        umet = fmath('ADD', 1400, y0 - 1680, "U в метрах")
        link(useam.outputs[0], umet.inputs[0])
        link(_out(ush, "Value"), umet.inputs[1])
        ufit = fmath('MULTIPLY', 1580, y0 - 1680, "U без искажений")
        link(umet.outputs[0], ufit.inputs[0])
        link(kden.outputs[0], ufit.inputs[1])
        us = fmath('MULTIPLY', 1760, y0 - 1680)
        link(ufit.outputs[0], us.inputs[0])
        link(G("Тайлинг вдоль"), us.inputs[1])

        # Отражение вдоль — просто смена знака: текстура тайлится,
        # поэтому зеркалить в пределах повтора не нужно. У бока и у верха
        # свои галочки, поэтому знак выбирается уже после того, как
        # определено, верхняя это грань или стенка.
        usn = fmath('MULTIPLY', 1940, y0 - 1680, "вдоль наоборот")
        link(us.outputs[0], usn.inputs[0])
        usn.inputs[1].default_value = -1.0
        us_side = N('GeometryNodeSwitch', 2120, y0 - 1620, "бок вдоль",
                    input_type='FLOAT')
        link(G("Бок: отразить вдоль"), _in(us_side, "Switch"))
        link(us.outputs[0], _in(us_side, "False"))
        link(usn.outputs[0], _in(us_side, "True"))
        us_top = N('GeometryNodeSwitch', 2120, y0 - 1780, "верх вдоль",
                   input_type='FLOAT')
        link(G("Верх: отразить вдоль"), _in(us_top, "Switch"))
        link(us.outputs[0], _in(us_top, "False"))
        link(usn.outputs[0], _in(us_top, "True"))
        ufin = N('GeometryNodeSwitch', 2300, y0 - 1700, "U: бок или верх",
                 input_type='FLOAT')
        link(_out(istop, "Result"), _in(ufin, "Switch"))
        link(_out(us_side, "Output"), _in(ufin, "False"))
        link(_out(us_top, "Output"), _in(ufin, "True"))

        # V: бок по высоте от низа своей строки, верх по удалению от края
        hh = fmath('MULTIPLY', 1220, y0 - 2100, "половина высоты")
        link(G("Высота"), hh.inputs[0])
        hh.inputs[1].default_value = 0.5
        vbot = fmath('SUBTRACT', 1400, y0 - 2100, "низ сечения")
        link(HOFF(), vbot.inputs[0])
        link(hh.outputs[0], vbot.inputs[1])
        vup = fmath('SUBTRACT', 1580, y0 - 2100, "высота над низом")
        link(_out(la, "Attribute"), vup.inputs[0])
        link(vbot.outputs[0], vup.inputs[1])
        vmul = fmath('MULTIPLY', 1760, y0 - 2100, "в текстуре")
        link(vup.outputs[0], vmul.inputs[0])
        link(kden.outputs[0], vmul.inputs[1])
        # Отражение поперёк — в пределах собственного размаха острова,
        # чтобы он остался в своей строке текстуры.
        vmir = fmath('SUBTRACT', 1940, y0 - 2240, "бок наоборот")
        link(rowh.outputs[0], vmir.inputs[0])
        link(vmul.outputs[0], vmir.inputs[1])
        vloc = N('GeometryNodeSwitch', 2120, y0 - 2100, "бок поперёк",
                 input_type='FLOAT')
        link(G("Бок: отразить поперёк"), _in(vloc, "Switch"))
        link(vmul.outputs[0], _in(vloc, "False"))
        link(vmir.outputs[0], _in(vloc, "True"))
        vb = row_base("Строка бока", 1940, y0 - 2000)
        v_side = fmath('ADD', 2300, y0 - 2100, "V бока")
        link(vb.outputs[0], v_side.inputs[0])
        link(_out(vloc, "Output"), v_side.inputs[1])

        tmul = fmath('MULTIPLY', 1760, y0 - 2380, "ширина в текстуре")
        link(_out(pda, "Attribute"), tmul.inputs[0])
        link(kden.outputs[0], tmul.inputs[1])
        twk = fmath('MULTIPLY', 1760, y0 - 2520, "ширина в единицах")
        link(G("Ширина"), twk.inputs[0])
        link(kden.outputs[0], twk.inputs[1])
        tmir = fmath('SUBTRACT', 1940, y0 - 2520, "верх наоборот")
        link(twk.outputs[0], tmir.inputs[0])
        link(tmul.outputs[0], tmir.inputs[1])
        tloc = N('GeometryNodeSwitch', 2120, y0 - 2380, "верх поперёк",
                 input_type='FLOAT')
        link(G("Верх: отразить поперёк"), _in(tloc, "Switch"))
        link(tmul.outputs[0], _in(tloc, "False"))
        link(tmir.outputs[0], _in(tloc, "True"))
        tb = row_base("Строка верха", 1940, y0 - 2660)
        v_top = fmath('ADD', 2300, y0 - 2380, "V верха")
        link(tb.outputs[0], v_top.inputs[0])
        link(_out(tloc, "Output"), v_top.inputs[1])

        vsw = N('GeometryNodeSwitch', 2120, y0 - 2240, "бок или верх",
                input_type='FLOAT')
        link(_out(istop, "Result"), _in(vsw, "Switch"))
        link(v_side.outputs[0], _in(vsw, "False"))
        link(v_top.outputs[0], _in(vsw, "True"))

        # Развёртка кладётся обычными числами, а слой UVMap собирается
        # один раз после склейки: если каждая часть создаёт свой UVMap,
        # Join Geometry сводит слои и острова разъезжаются.
        # Признак ветки: у внутренней лента стоит по центру ребра, и
        # кромок у неё две — это учитывает отбор кромки для заливки.
        stin = N('GeometryNodeStoreNamedAttribute', 780, y0,
                 "%s: признак ветки" % tag, data_type='FLOAT',
                 domain='POINT')
        link(_out(flip, "Mesh"), _in(stin, "Geometry"))
        SI(stin, "Name", IS_IN_ATTR)
        SI(stin, "Value", 1.0 if only_top else 0.0)

        stu2 = N('GeometryNodeStoreNamedAttribute', 860, y0, "%s: U" % tag,
                 data_type='FLOAT', domain='CORNER')
        link(_out(stin, "Geometry"), _in(stu2, "Geometry"))
        SI(stu2, "Name", UU_ATTR)
        link(_out(ufin, "Output"), _in(stu2, "Value"))
        stv2 = N('GeometryNodeStoreNamedAttribute', 1040, y0, "%s: V" % tag,
                 data_type='FLOAT', domain='CORNER')
        link(_out(stu2, "Geometry"), _in(stv2, "Geometry"))
        SI(stv2, "Name", VV_ATTR)
        link(_out(vsw, "Output"), _in(stv2, "Value"))
        return _out(stv2, "Geometry")

    geo_out = branch("cout", _out(sel_out, "Boolean"),
                     centered=False, only_top=False, y0=0)
    geo_in = branch("cinn", _out(sel_in, "Boolean"),
                    centered=True, only_top=True, y0=-2800)
    # Смещён внутрь тротуара, но без стенок: только верхняя грань.
    # Тогда у ленты обе кромки — границы заливки, и контуры ячеек
    # замыкаются с обеих сторон.
    geo_walk = branch("cwlk", _out(sel_walk, "Boolean"),
                      centered=True, only_top=True, y0=-5600,
                      shift_attr=WDIR_ATTR, clip_rim=False)

    # Лента тротуара опускается на полмиллиметра. Там, где она заходит на
    # основной бордюр, две грани лежали на одной высоте и мерцали друг
    # сквозь друга; теперь перекрытие уходит под верх основного бордюра.
    # На заливку это не влияет: её высота ставится присвоением, а не
    # наследуется от ленты.
    wsink = N('ShaderNodeCombineXYZ', 700, -5600)
    wsink.inputs['Z'].default_value = -WALK_SINK
    wdrop = N('GeometryNodeSetPosition', 880, -5600, "лента чуть ниже")
    link(geo_walk, _in(wdrop, "Geometry"))
    link(wsink.outputs[0], _in(wdrop, "Offset"))
    geo_walk = _out(wdrop, "Geometry")

    # -- заливка ячеек -------------------------------------------------
    # Строится по ВНУТРЕННЕЙ КРОМКЕ самого бордюра: она уже посчитана
    # свипом, со всеми скруглениями и митрой. Своего отступа у заливки
    # нет, поэтому расходиться с бордюром нечему по построению.
    #
    # Кромка опознаётся по «удалению точки сечения от линии»: у ближней
    # стенки оно ноль, у дальней — ширина бордюра. Прочитанное на домене
    # рёбер, оно усредняется по двум концам ребра, поэтому у кромочных
    # рёбер даёт ширину, у наружных ноль, а у поперечных на торцах —
    # половину, и они не попадают.
    fjoin = N('GeometryNodeJoinGeometry', -1680, -700, "бордюры вместе")
    link(geo_out, _in(fjoin, "Geometry"))
    link(geo_in, _in(fjoin, "Geometry"))
    link(geo_walk, _in(fjoin, "Geometry"))

    # Сварка нужна, чтобы кромки соседних кусков сомкнулись в замкнутые
    # контуры ячеек: до неё это отдельные разомкнутые куски.
    fweld = N('GeometryNodeMergeByDistance', -1500, -700, "сварить стыки")
    link(_out(fjoin, "Geometry"), _in(fweld, "Geometry"))
    SI(fweld, "Distance", 1e-4)

    fpda = N('GeometryNodeInputNamedAttribute', -1680, -900,
             "удаление от линии", data_type='FLOAT')
    SI(fpda, "Name", PD_ATTR)
    fpde = N('GeometryNodeFieldOnDomain', -1500, -900, "по ребру",
             data_type='FLOAT', domain='EDGE')
    link(_out(fpda, "Attribute"), _in(fpde, "Value"))
    fwthr = fmath('MULTIPLY', -1500, -1040, "3/4 ширины")
    link(G("Ширина"), fwthr.inputs[0])
    fwthr.inputs[1].default_value = 0.75
    fisin = N('FunctionNodeCompare', -1320, -900, "это кромка",
              data_type='FLOAT', operation='GREATER_THAN')
    link(_out(fpde, "Value"), _in(fisin, "A"))
    link(fwthr.outputs[0], _in(fisin, "B"))

    fben = N('GeometryNodeInputMeshEdgeNeighbors', -1680, -1180)
    fbcmp = N('FunctionNodeCompare', -1500, -1180, "край меша",
              data_type='INT', operation='LESS_EQUAL')
    link(_out(fben, "Face Count"), _in(fbcmp, "A"))
    SI(fbcmp, "B", 1)
    # У внутренней ветки годятся обе кромки, у внешней — только дальняя
    # от линии: ближняя стоит на самой линии и заливке не граница.
    fina = N('GeometryNodeInputNamedAttribute', -1680, -1320,
             "признак ветки", data_type='FLOAT')
    SI(fina, "Name", IS_IN_ATTR)
    fined = N('GeometryNodeFieldOnDomain', -1500, -1320, "по ребру",
             data_type='FLOAT', domain='EDGE')
    link(_out(fina, "Attribute"), _in(fined, "Value"))
    fincmp = N('FunctionNodeCompare', -1320, -1320, "внутренняя ветка",
               data_type='FLOAT', operation='GREATER_THAN')
    link(_out(fined, "Value"), _in(fincmp, "A"))
    SI(fincmp, "B", 0.5)
    fany = N('FunctionNodeBooleanMath', -1140, -1320, "годная кромка",
             operation='OR')
    link(_out(fisin, "Result"), fany.inputs[0])
    link(_out(fincmp, "Result"), fany.inputs[1])

    fsel = N('FunctionNodeBooleanMath', -1320, -1040, "кромка и край",
             operation='AND')
    link(_out(fany, "Boolean"), fsel.inputs[0])
    link(_out(fbcmp, "Result"), fsel.inputs[1])

    fm2c = N('GeometryNodeMeshToCurve', -1320, -700, "кромка в контур",
             mode='EDGES')
    link(_out(fweld, "Geometry"), _in(fm2c, "Mesh"))
    link(_out(fsel, "Boolean"), _in(fm2c, "Selection"))

    ffill = N('GeometryNodeFillCurve', -1140, -700, "залить ячейку")
    link(_out(fm2c, "Curve"), _in(ffill, "Curve"))

    # Высота ставится присвоением: Fill Curve строит меш в плоскости XY.
    ftop = fmath('MULTIPLY', -1500, -1400, "половина высоты")
    link(G("Высота"), ftop.inputs[0])
    ftop.inputs[1].default_value = 0.5
    flev = fmath('ADD', -1320, -1400, "верх бордюра")
    link(HOFF(), flev.inputs[0])
    link(ftop.outputs[0], flev.inputs[1])
    fzp = N('GeometryNodeInputPosition', -1140, -1400)
    fzs = N('ShaderNodeSeparateXYZ', -960, -1400)
    link(fzp.outputs[0], fzs.inputs[0])
    fzxyz = N('ShaderNodeCombineXYZ', -780, -1400)
    link(fzs.outputs['X'], fzxyz.inputs['X'])
    link(fzs.outputs['Y'], fzxyz.inputs['Y'])
    link(flev.outputs[0], fzxyz.inputs['Z'])
    fzfix = N('GeometryNodeSetPosition', -960, -700, "уровень на место")
    link(_out(ffill, "Mesh"), _in(fzfix, "Geometry"))
    link(fzxyz.outputs[0], _in(fzfix, "Position"))

    fmat2 = N('GeometryNodeSetMaterial', -780, -700, "материал травы")
    link(_out(fzfix, "Geometry"), _in(fmat2, "Geometry"))
    link(G("Материал травы"), _in(fmat2, "Material"))

    # Материал тротуара там, где под заливкой лежит помеченная грань.
    # Заливка построена по кромке бордюра и про исходные грани ничего не
    # знает, поэтому принадлежность берётся выборкой с исходного меша.
    wsamp = N('GeometryNodeSampleNearestSurface', -780, -1900,
              "что под заливкой", data_type='FLOAT')
    link(src_geo, _in(wsamp, "Mesh"))
    link(_out(wface, "Value"), _in(wsamp, "Value"))
    wfac = N('GeometryNodeFieldOnDomain', -600, -1900, "по грани заливки",
             data_type='FLOAT', domain='FACE')
    link(_out(wsamp, "Value"), _in(wfac, "Value"))
    wsel = N('FunctionNodeCompare', -420, -1900, "это тротуар",
             data_type='FLOAT', operation='GREATER_THAN')
    link(_out(wfac, "Value"), _in(wsel, "A"))
    SI(wsel, "B", 0.5)
    fmat3 = N('GeometryNodeSetMaterial', -700, -700, "материал тротуара")
    link(_out(fmat2, "Geometry"), _in(fmat3, "Geometry"))
    link(_out(wsel, "Result"), _in(fmat3, "Selection"))
    link(G("Материал тротуара"), _in(fmat3, "Material"))

    # UV заливки — планарная проекция сверху
    fpos = N('GeometryNodeInputPosition', -780, -1600)
    fsep = N('ShaderNodeSeparateXYZ', -600, -1600)
    link(fpos.outputs[0], fsep.inputs[0])
    fux = fmath('MULTIPLY', -420, -1600)
    link(fsep.outputs['X'], fux.inputs[0])
    link(G("Тайлинг заливки"), fux.inputs[1])
    fuy = fmath('MULTIPLY', -420, -1740)
    link(fsep.outputs['Y'], fuy.inputs[0])
    link(G("Тайлинг заливки"), fuy.inputs[1])
    fsu = N('GeometryNodeStoreNamedAttribute', -600, -700, "U заливки",
            data_type='FLOAT', domain='CORNER')
    link(_out(fmat3, "Geometry"), _in(fsu, "Geometry"))
    SI(fsu, "Name", UU_ATTR)
    link(fux.outputs[0], _in(fsu, "Value"))
    fstuv = N('GeometryNodeStoreNamedAttribute', -420, -700, "V заливки",
              data_type='FLOAT', domain='CORNER')
    link(_out(fsu, "Geometry"), _in(fstuv, "Geometry"))
    SI(fstuv, "Name", VV_ATTR)
    link(fuy.outputs[0], _in(fstuv, "Value"))

    fsw = N('GeometryNodeSwitch', -240, -700, "заливка вкл",
            input_type='GEOMETRY')
    link(G("Заливка внутри"), _in(fsw, "Switch"))
    link(_out(fstuv, "Geometry"), _in(fsw, "True"))


    jcurb = N('GeometryNodeJoinGeometry', 860, 0, "оба бордюра")
    link(geo_out, _in(jcurb, "Geometry"))
    link(geo_in, _in(jcurb, "Geometry"))
    link(geo_walk, _in(jcurb, "Geometry"))
    mat = N('GeometryNodeSetMaterial', 1040, 0, "материал бордюра")
    link(_out(jcurb, "Geometry"), _in(mat, "Geometry"))
    link(G("Материал"), _in(mat, "Material"))

    join = N('GeometryNodeJoinGeometry', 1220, 0, "бордюры и заливка")
    link(_out(mat, "Geometry"), _in(join, "Geometry"))
    link(_out(fsw, "Output"), _in(join, "Geometry"))

    # -- один слой UVMap на всё, уже после склейки ----------------------
    uua = N('GeometryNodeInputNamedAttribute', 1220, -400, data_type='FLOAT')
    SI(uua, "Name", UU_ATTR)
    vva = N('GeometryNodeInputNamedAttribute', 1220, -540, data_type='FLOAT')
    SI(vva, "Name", VV_ATTR)
    uvxy = N('ShaderNodeCombineXYZ', 1400, -470)
    link(_out(uua, "Attribute"), uvxy.inputs['X'])
    link(_out(vva, "Attribute"), uvxy.inputs['Y'])
    uvall = N('GeometryNodeStoreNamedAttribute', 1400, 0, "UVMap",
              data_type='FLOAT2', domain='CORNER')
    link(_out(join, "Geometry"), _in(uvall, "Geometry"))
    SI(uvall, "Name", UV_NAME)
    link(uvxy.outputs[0], _in(uvall, "Value"))

    # -- триангуляция, затенение ---------------------------------------
    tri = N('GeometryNodeTriangulate', 1220, -200)
    link(_out(uvall, "Geometry"), _in(tri, "Mesh"))
    swt = N('GeometryNodeSwitch', 1400, -100, "триангуляция",
            input_type='GEOMETRY')
    link(G("Триангулировать"), _in(swt, "Switch"))
    link(_out(uvall, "Geometry"), _in(swt, "False"))
    link(_out(tri, "Mesh"), _in(swt, "True"))

    ssf = N('GeometryNodeSetShadeSmooth', 1400, -100, "гладкие грани",
            domain='FACE')
    link(_out(swt, "Output"), _in(ssf, "Geometry"))
    link(G("Гладкое затенение"), _in(ssf, "Shade Smooth"))
    eang = N('GeometryNodeInputMeshEdgeAngle', 1400, -300)
    esh = N('FunctionNodeCompare', 1580, -300, "угол больше порога",
            data_type='FLOAT', operation='GREATER_THAN')
    link(_out(eang, "Unsigned Angle"), _in(esh, "A"))
    link(G("Угол автосглаживания"), _in(esh, "B"))
    sse = N('GeometryNodeSetShadeSmooth', 1760, -100, "острые рёбра",
            domain='EDGE')
    link(_out(ssf, "Geometry"), _in(sse, "Geometry"))
    link(_out(esh, "Result"), _in(sse, "Selection"))
    SI(sse, "Shade Smooth", False)
    link(_out(sse, "Geometry"), go.inputs[0])

    frame = ng.nodes.new('NodeFrame')
    frame.label = "Как пользоваться"
    frame.shrink = False
    frame.location = (-2600, 1100)
    frame.width = 620
    frame.height = 700
    try:
        frame.label_size = 16
        frame.text = ensure_help()
    except (AttributeError, TypeError) as e:
        warn.append("справка в рамке: %s" % e)

    return ng, warn


# Сокеты, чьё значение в модификатор не пишется (геометрия и ссылки на
# датаблоки — их пользователь выбирает сам).
# Материалы сюда не входят: у них есть значения по умолчанию, и они
# проставляются в модификатор наравне с числами.
_NO_RESET = {
    'NodeSocketGeometry', 'NodeSocketObject',
    'NodeSocketCollection', 'NodeSocketImage', 'NodeSocketTexture',
}


def reset_inputs(mod, ng):
    """Проставляет модификатору значения по умолчанию из группы: при
    пересборке интерфейса сокеты получают новые идентификаторы, и старые
    значения к ним не подходят — поля оказываются пустыми."""
    for item in ng.interface.items_tree:
        if getattr(item, 'item_type', 'SOCKET') != 'SOCKET':
            continue
        if item.in_out != 'INPUT' or item.socket_type in _NO_RESET:
            continue
        try:
            mod[item.identifier] = item.default_value
        except (KeyError, TypeError, AttributeError, ValueError):
            pass


def attach(obj, ng):
    mod = None
    for m in obj.modifiers:
        if m.type == 'NODES' and m.node_group is ng:
            mod = m
            break
    if mod is None:
        mod = obj.modifiers.new(MOD_NAME, 'NODES')
        mod.node_group = ng
    reset_inputs(mod, ng)
    obj.update_tag()
    return mod


if __name__ == "__main__":
    group, problems = build_group()
    targets = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    if not targets and bpy.context.object \
            and bpy.context.object.type == 'MESH':
        targets = [bpy.context.object]
    for ob in targets:
        attach(ob, group)

    print("[INU Curb] build %d; группа «%s» собрана; модификатор на: %s"
          % (SCRIPT_BUILD, GROUP_NAME,
             [o.name for o in targets] or "ничего не выделено"))
    print("[INU Curb] внешний контур — бордюр вбок; внутренние — по центру, только верх")
    for ob in targets:
        me = ob.data
        print("[INU Curb] %s: вершин %d, рёбер %d, ГРАНЕЙ %d%s"
              % (ob.name, len(me.vertices), len(me.edges), len(me.polygons),
                 "" if len(me.polygons) else
                 "  <- граней нет, заливать нечего"))
        vg = [g.name for g in ob.vertex_groups]
        print("[INU Curb] %s: группы вершин %s"
              % (ob.name, vg or "нет"))
    for p in problems:
        print("[INU Curb] не выставилось: %s" % p)
