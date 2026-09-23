# -*- coding: utf-8 -*-
#
# Процедурный бордюр, трава и тротуар на гео-нодах.
#
# ЗАПУСК
#   Text Editor -> Run Script. Создаёт нод-группу «INU_Curb» и вешает её
#   модификатором на выделенные меш-объекты.
#
# СХЕМА: ДВА НЕЗАВИСИМЫХ ПРОХОДА
#   По умолчанию весь участок — тротуар. Помечаются только пятна травы,
#   слотом материала. Дальше строятся два прохода, у каждого СВОЙ
#   РАВНОМЕРНЫЙ отступ по всему контуру:
#       контур участка   -> внешний бордюр;
#       контур пятна травы -> бордюр вокруг травы, лежит внутри травы.
#   Тротуар — заливка контура участка с дырами по контурам травы;
#   собственного отступа ему не нужно, он занимает всё остальное.
#
#   Почему именно так. Все прежние поломки шли от РАЗНЫХ отступов у
#   соседних рёбер одной ячейки: в такой вершине точку надо сдвигать в
#   пересечение двух отступлённых линий, а посчитать это можно только до
#   скругления — тогда как сам сдвиг обязан считаться после скругления,
#   иначе дуги перекашивает. Требования противоречат друг другу. Когда
#   отступ один на весь контур, противоречия нет вовсе.
#
# ПРО СУЖЕНИЕ В УГЛАХ
#   «Кривую в меш» ставит профиль перпендикулярно усреднённой касательной
#   и не масштабирует его, поэтому ширина в изломе падала бы как
#   cos(угол/2). Это её штатное поведение (issue #147946), в Blender 5.3
#   для этого добавили Miter Scale. Здесь то же самое делается руками:
#   в каждой точке считается 1/cos(угол/2) и идёт во вход «Масштаб».
#   Косинус берётся без поиска соседних точек: у каждого ребра свой
#   единичный перпендикуляр, а среднее по рёбрам в вершине Blender
#   считает сам — длина полусуммы и есть cos(угол/2).

import bpy

SCRIPT_BUILD = 128
GROUP_NAME = "INU_Curb"
MOD_NAME = "INU Curb"
VGROUP = "curb_round"

# Группы скругления: (имя группы вершин, радиус по умолчанию, сегментов).
# Сколько строк — столько наборов полей в модификаторе. Добавляй свои и
# запускай скрипт заново: набор входов гео-нод фиксируется при сборке
# группы, на лету он не растёт.
ROUND_GROUPS = (
    ("curb_round_1", 0.3, 4),
    ("curb_round_2", 1.0, 6),
    ("curb_round_3", 3.0, 8),
)
UV_NAME = "UVMap"
MITER_EPS = 1e-3
EDGE_LIP = 0.01    # высота внутренней кромки каменной полосы

# Материалы по умолчанию: подставляются, если такие есть в файле.
MAT_CURB = "curb_1"
MAT_GRASS = "pf_Grass_01"
MAT_WALK = "KCG_trot01"

IN_ATTR = "curb_in"      # направление внутрь области
U_ATTR = "curb_u"        # длина вдоль линии
S_ATTR = "curb_len"      # полная длина сплайна
T_ATTR = "curb_tan"      # касательная линии
P_ATTR = "curb_p0"       # позиция точки линии
Z_ATTR = "curb_z"        # уровень линии
L_ATTR = "curb_lvl"      # высота точки профиля
M_ATTR = "curb_miter"    # масштаб профиля в изломе
UU_ATTR = "curb_uu"      # U до склейки
VV_ATTR = "curb_vv"      # V до склейки
R_ATTR = "curb_rimpt"    # точка лежит на краю участка
D_ATTR = "curb_downpt"   # точка на помеченном краевом ребре
OFF_ATTR = "curb_off"    # сдвиг точки контура внутрь

HELP_NAME = "INU_Curb — как пользоваться"

HELP_TEXT = """INU_Curb — бордюр, трава и тротуар

ПО УМОЛЧАНИЮ ВЕСЬ УЧАСТОК — ТРОТУАР.
Помечаются только пятна травы.

1. ПЛОСКОСТЬ
   Меш с гранями. Форма любая, дели как удобно — Ctrl+R, Knife.
   Работают только те грани, которым назначен материал тротуара или
   травы; остальные модификатор не трогает.

2. ТРАВА
   В Edit Mode выдели грани, которые должны стать травой, и назначь
   им материал травы: Material Properties -> выбрать слот -> Assign.
   Какой именно материал считается травой — поле «Материал травы»
   во вкладке «Материалы». Вокруг каждого пятна встанет бордюр.

3. СПУСК К ДОРОГЕ
   Помечай краевые рёбра острыми: Edge Mode -> выдели рёбра ->
   Edge -> Mark Sharp. По ним тротуар сойдёт на землю, и вдоль них
   ляжет каменная полоса шириной «Ширина». Непомеченный край
   остаётся на своём уровне.

4. БОРДЮР
   Строится ТОЛЬКО вокруг травы и стоит ВНУТРИ травы: ширину камня
   забирает она, тротуар не трогается совсем. По краю тротуара
   бордюра нет — он просто кончается на краю участка.

5. КРУГЛЫЕ УГЛЫ — ГРУППЫ ВЕРШИН
   Object Data -> Vertex Groups -> «+» -> curb_round_1, _2, _3.
   Edit Mode -> выдели угловые точки -> Weight -> Assign.
   Радиус = Weight x «Радиус N», сегменты свои у каждой группы.
   Точки вне групп остаются острыми. Если точка в двух группах,
   берётся больший радиус и сегменты ЕГО группы.
   Групп может быть сколько угодно: список ROUND_GROUPS в начале
   скрипта, добавь строку и запусти скрипт заново.

6. СЕЧЕНИЕ
   «Ширина» и «Высота» — размеры камня. Низ стоит на плоскости.
   Трава и тротуар лежат вровень с верхом камня. У помеченного края
   плита наклонена вниз, а последние «Ширина» перед ним — каменная
   полоса, сходящая на нет.

7. UV
   Текстура делится на строки: «Строк в текстуре».
   «Строка бока» и «Строка верха» — куда лечь каждому острову,
   под каждой её галочки отражения X и Y.
   Масштаб от высоты строки: при «Тайлинг вдоль» = 1 стенка занимает
   строку ровно по высоте, вдоль и на верху плотность та же.
   Развёртка заливки планарная, сверху; плотность — «Тайлинг заливки».

8. ЭКСПОРТ В GTA
   Включи «Триангулировать», затем Object -> Convert -> Mesh.
"""


# -- сокет-хелперы ----------------------------------------------------
# У Compare / Switch / Store Named Attribute несколько одноимённых
# сокетов (по одному на тип данных); актуален тот, у которого
# enabled=True. Плюс геометрические сокеты между версиями
# переименовывались.

_SOCKET_ALIASES = {
    'Target': ('Geometry', 'Mesh'),
    'Source Position': ('Sample Position',),
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
    """Как и _in, сначала ищет ВКЛЮЧЁННЫЙ сокет: у Compare сокеты «A» и
    «B» заведены для каждого типа данных, и в режиме INT включены только
    целочисленные."""
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
    """В Blender 5.x часть выпадашек нод переехала в menu-сокеты входа, и
    старые enum-идентификаторы туда не пишутся."""
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

    def attr(name, x, y, dtype='FLOAT', label=None):
        n = N('GeometryNodeInputNamedAttribute', x, y, label, data_type=dtype)
        SI(n, "Name", name)
        return n

    def store(geo, name, value, x, y, dtype='FLOAT', domain='POINT',
              label=None):
        s = N('GeometryNodeStoreNamedAttribute', x, y, label,
              data_type=dtype, domain=domain)
        link(geo, _in(s, "Geometry"))
        SI(s, "Name", name)
        link(value, _in(s, "Value"))
        return _out(s, "Geometry")

    def on_domain(value, dom, x, y, dtype='FLOAT', label=None):
        """Вычислить поле на нужном домене и только потом отдать дальше.
        Без этого Blender интерполирует ИСХОДНЫЕ величины на целевой
        домен и считает выражение уже из них — например усредняет индекс
        материала по двум граням ребра и получает 0.5."""
        n = N('GeometryNodeFieldOnDomain', x, y, label,
              data_type=dtype, domain=dom)
        link(value, _in(n, "Value"))
        return n

    def switchf(cond, false_val, true_val, x, y, label=None):
        n = N('GeometryNodeSwitch', x, y, label, input_type='FLOAT')
        link(cond, _in(n, "Switch"))
        if isinstance(false_val, float):
            SI(n, "False", false_val)
        else:
            link(false_val, _in(n, "False"))
        if isinstance(true_val, float):
            SI(n, "True", true_val)
        else:
            link(true_val, _in(n, "True"))
        return _out(n, "Output")

    def cmp(a, b, op, x, y, dtype='FLOAT', label=None):
        n = N('FunctionNodeCompare', x, y, label,
              data_type=dtype, operation=op)
        link(a, _in(n, "A"))
        if isinstance(b, (int, float)):
            SI(n, "B", b)
        else:
            link(b, _in(n, "B"))
        return _out(n, "Result")

    def boolean(op, a, b, x, y, label=None):
        n = N('FunctionNodeBooleanMath', x, y, label, operation=op)
        link(a, n.inputs[0])
        if b is not None:
            link(b, n.inputs[1])
        return _out(n, "Boolean")

    # -- интерфейс ----------------------------------------------------
    it = ng.interface
    it.new_socket(name="Геометрия", in_out='OUTPUT',
                  socket_type='NodeSocketGeometry')

    def panel(name, closed=True):
        """Сворачиваемая подвкладка. В старых версиях панелей в интерфейсе
        нод-группы нет — тогда поля просто идут подряд."""
        try:
            return it.new_panel(name, default_closed=closed)
        except TypeError:
            try:
                return it.new_panel(name)
            except (AttributeError, TypeError):
                return None
        except AttributeError:
            return None

    def sock(name, stype, desc=None, panel=None, **kw):
        try:
            s = it.new_socket(name=name, in_out='INPUT', socket_type=stype,
                              parent=panel) if panel is not None else \
                it.new_socket(name=name, in_out='INPUT', socket_type=stype)
        except TypeError:
            s = it.new_socket(name=name, in_out='INPUT', socket_type=stype)
            if panel is not None:
                try:
                    it.move_to_parent(s, panel, len(panel.interface_items))
                except (AttributeError, TypeError):
                    pass
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
                warn.append("нет материала «%s» — поле пустое" % kw['mat'])
            else:
                try:
                    s.default_value = m
                except (AttributeError, TypeError):
                    warn.append("не подставился материал «%s»" % kw['mat'])
        return s

    sock("Геометрия", 'NodeSocketGeometry')

    p_curb = panel("Бордюр", closed=False)
    sock("Ширина", 'NodeSocketFloat', subtype='DISTANCE', panel=p_curb,
         min_value=0.0, max_value=10.0, default_value=0.15,
         desc="Ширина бордюрного камня, выдерживается и в острых углах")
    sock("Высота", 'NodeSocketFloat', subtype='DISTANCE', panel=p_curb,
         min_value=0.0, max_value=10.0, default_value=0.15,
         desc="Высота бордюра над плоскостью")

    p_round = panel("Скругление")
    for i, (nm, rv, sv) in enumerate(ROUND_GROUPS, 1):
        sock("Группа %d" % i, 'NodeSocketString', default_value=nm,
             panel=p_round,
             desc="Object Data -> Vertex Groups -> «+», назови %s" % nm)
        sock("Радиус %d" % i, 'NodeSocketFloat', subtype='DISTANCE',
             min_value=0.0, max_value=100.0, default_value=rv,
             panel=p_round,
             desc="Радиус в точке = вес вершины в группе %d x это "
                  "значение" % i)
        sock("Сегментов %d" % i, 'NodeSocketInt', panel=p_round,
             min_value=1, max_value=64, default_value=sv,
             desc="Гладкость дуги у группы %d. Для GTA хватает 3-8" % i)

    p_uv = panel("UV")
    sock("Строк в текстуре", 'NodeSocketInt', panel=p_uv,
         min_value=1, max_value=64, default_value=8)
    sock("Строка бока", 'NodeSocketInt', panel=p_uv,
         min_value=1, max_value=64, default_value=3)
    sock("Бок X", 'NodeSocketBool', default_value=False, panel=p_uv,
         desc="Отразить текстуру бока вдоль")
    sock("Бок Y", 'NodeSocketBool', default_value=False, panel=p_uv,
         desc="Отразить текстуру бока поперёк")
    sock("Строка верха", 'NodeSocketInt', panel=p_uv,
         min_value=1, max_value=64, default_value=4)
    sock("Верх X", 'NodeSocketBool', default_value=False, panel=p_uv,
         desc="Отразить текстуру верха вдоль")
    sock("Верх Y", 'NodeSocketBool', default_value=False, panel=p_uv,
         desc="Отразить текстуру верха поперёк")
    sock("Тайлинг вдоль", 'NodeSocketFloat', panel=p_uv,
         min_value=0.0, max_value=1000.0, default_value=1.0,
         desc="1 — текстура не искажена")
    sock("Тайлинг заливки", 'NodeSocketFloat', panel=p_uv,
         min_value=0.0, max_value=1000.0, default_value=1.0,
         desc="Повторов текстуры на метр у заливки")

    p_mat = panel("Материалы", closed=False)
    sock("Материал бордюра", 'NodeSocketMaterial', panel=p_mat,
         mat=MAT_CURB, desc="Материал бордюрного камня")
    sock("Материал травы", 'NodeSocketMaterial', panel=p_mat, mat=MAT_GRASS,
         desc="Трава — это грани, которым назначен ЭТОТ материал. "
              "Назначаешь его в Edit Mode, и они становятся травой; "
              "всё остальное — тротуар")
    sock("Материал тротуара", 'NodeSocketMaterial', panel=p_mat,
         mat=MAT_WALK)

    p_exp = panel("Экспорт")
    sock("Гладкое затенение", 'NodeSocketBool', default_value=True,
         panel=p_exp)
    sock("Угол автосглаживания", 'NodeSocketFloat', subtype='ANGLE',
         panel=p_exp,
         min_value=0.0, max_value=3.14159, default_value=0.523599)
    sock("Триангулировать", 'NodeSocketBool', default_value=False,
         panel=p_exp, desc="Включи перед экспортом в GTA")

    gi = N('NodeGroupInput', -3200, 0)
    go = N('NodeGroupOutput', 3000, 0)

    def G(name):
        return _out(gi, name)

    half_h = fmath('MULTIPLY', -3000, 1000, "половина высоты")
    link(G("Высота"), half_h.inputs[0])
    half_h.inputs[1].default_value = 0.5
    hoff = half_h.outputs[0]
    half_w = fmath('MULTIPLY', -3000, 860, "половина ширины")
    link(G("Ширина"), half_w.inputs[0])
    half_w.inputs[1].default_value = 0.5

    # -- радиус и сегменты в точке -------------------------------------
    # Побеждает группа с наибольшим радиусом; её счётчик сегментов идёт с
    # ней. Fillet Curve принимает Count полем, поэтому у разных точек
    # одной кривой сегменты могут отличаться.
    rad_out = None
    seg_out = None
    for i in range(1, len(ROUND_GROUPS) + 1):
        y = 200 + i * 200
        w = attr(VGROUP, -3200, y, 'FLOAT', "вес в группе %d" % i)
        link(G("Группа %d" % i), _in(w, "Name"))
        r = fmath('MULTIPLY', -3020, y, "радиус %d" % i)
        link(_out(w, "Attribute"), r.inputs[0])
        link(G("Радиус %d" % i), r.inputs[1])
        if rad_out is None:
            rad_out = r.outputs[0]
            seg_out = G("Сегментов %d" % i)
            continue
        win = cmp(r.outputs[0], rad_out, 'GREATER_THAN', -2840, y,
                  'FLOAT', "группа %d больше" % i)
        rmax = fmath('MAXIMUM', -2660, y, "радиус после %d" % i)
        link(rad_out, rmax.inputs[0])
        link(r.outputs[0], rmax.inputs[1])
        ssw = N('GeometryNodeSwitch', -2660, y - 100,
                "сегменты после %d" % i, input_type='INT')
        link(win, _in(ssw, "Switch"))
        link(seg_out, _in(ssw, "False"))
        link(G("Сегментов %d" % i), _in(ssw, "True"))
        rad_out = rmax.outputs[0]
        seg_out = _out(ssw, "Output")

    # -- вход: снять чужой UV, выделить траву ---------------------------
    drop = N('GeometryNodeRemoveAttribute', -3000, -100, "снять старый UV")
    link(G("Геометрия"), _in(drop, "Geometry"))
    SI(drop, "Name", UV_NAME)
    src = _out(drop, "Geometry")

    # Край участка помечается на целом меше, до разделения: после него
    # край участка от границы с травой уже не отличить. Нужен он для
    # боковых граней бордюра — снаружи стенка видна только там.
    ren = N('GeometryNodeInputMeshEdgeNeighbors', -3000, -300)
    rimb = cmp(_out(ren, "Face Count"), 1, 'LESS_EQUAL', -2820, -300, 'INT',
               "ребро края участка")
    rimf = switchf(rimb, 0.0, 1.0, -2640, -300, "край как число")
    # Домен здесь — тот, на котором считается САМО выражение: число
    # смежных граней живёт у ребра. К точке результат приводит уже запись
    # атрибута, усреднением по её рёбрам.
    rimp = on_domain(rimf, 'EDGE', -2460, -300, 'FLOAT',
                     "край, посчитанный у ребра")
    rimy = cmp(_out(rimp, "Value"), 0.01, 'GREATER_THAN', -2280, -300,
               'FLOAT', "точка на краю")
    rimv = switchf(rimy, 0.0, 1.0, -2100, -300, "точка края как число")
    src = store(src, R_ATTR, rimv, -1920, -300, 'FLOAT', 'POINT',
                "точка на краю участка")

    # Спуск — только по краевым рёбрам, помеченным ОСТРЫМИ (Mark Sharp).
    # Пометка живёт у ребра в атрибуте sharp_edge, к точке приводится тем
    # же усреднением по её рёбрам.
    shp = attr("sharp_edge", -3000, -460, 'BOOLEAN', "ребро помечено")
    shf = switchf(_out(shp, "Attribute"), 0.0, 1.0, -2820, -460,
                  "пометка как число")
    rimn = switchf(rimb, 0.0, 1.0, -2820, -600, "край как число")
    dwe = fmath('MULTIPLY', -2640, -460, "край И помечено")
    link(shf, dwe.inputs[0])
    link(rimn, dwe.inputs[1])
    dwp = on_domain(dwe.outputs[0], 'EDGE', -2460, -460, 'FLOAT',
                    "посчитано у ребра")
    dwy = cmp(_out(dwp, "Value"), 0.01, 'GREATER_THAN', -2280, -460,
              'FLOAT', "точка на помеченном крае")
    dwv = switchf(dwy, 0.0, 1.0, -2100, -460, "0 или 1")
    src = store(src, D_ATTR, dwv, -1920, -460, 'FLOAT', 'POINT',
                "точка спуска")

    # Отбор по САМОМУ материалу, а не по номеру слота: номер зависит от
    # порядка слотов в объекте и путается, а материал виден глазами.
    gsel = N('GeometryNodeMaterialSelection', -2820, 60, "грань травы")
    link(G("Материал травы"), _in(gsel, "Material"))
    is_grass = _out(gsel, "Selection")
    gsep = N('GeometryNodeSeparateGeometry', -2640, -100, "пятна травы",
             domain='FACE')
    link(src, _in(gsep, "Geometry"))
    link(is_grass, _in(gsep, "Selection"))

    # Тротуар — тоже по своему материалу, а не «всё, что не трава». Грань,
    # которой не назначен ни тот ни другой, не даёт ничего: так на одном
    # меше можно держать и куски, к которым модификатор не относится.
    wsel = N('GeometryNodeMaterialSelection', -2820, -260, "грань тротуара")
    link(G("Материал тротуара"), _in(wsel, "Material"))
    wsep = N('GeometryNodeSeparateGeometry', -2640, -260, "куски тротуара",
             domain='FACE')
    link(src, _in(wsep, "Geometry"))
    link(_out(wsel, "Selection"), _in(wsep, "Selection"))

    # Бордюр строится ТОЛЬКО вокруг травы и стоит ВНУТРИ травы: контур
    # пятна отступает внутрь на ширину камня, полоса между контуром и
    # отступом и есть бордюр. Тротуар при этом не трогается совсем —
    # ни отступа, ни полосы по его краю: он просто доходит до контура
    # травы с одной стороны и до края участка с другой. Поэтому и не
    # возникает разных отступов в одной вершине: у травы он всюду один,
    # у тротуара его нет вовсе.

    # -- контуры и бордюр ------------------------------------------------

    def contour(mesh, tag, y0):
        """Скруглённый контур области: рёбра, у которых смежная грань
        одна. У травы это её край, у тротуара — край участка вместе с
        краями пятен травы."""
        ben = N('GeometryNodeInputMeshEdgeNeighbors', -2280, y0 + 160)
        is_bnd = cmp(_out(ben, "Face Count"), 1, 'LESS_EQUAL', -2100,
                     y0 + 160, 'INT', "граница области")
        m2c = N('GeometryNodeMeshToCurve', -2280, y0, "%s: контур" % tag,
                mode='EDGES')
        link(mesh, _in(m2c, "Mesh"))
        link(is_bnd, _in(m2c, "Selection"))
        fil = N('GeometryNodeFilletCurve', -2100, y0,
                "%s: скругление" % tag, probe='Count', mode='POLY')
        link(_out(m2c, "Curve"), _in(fil, "Curve"))
        link(rad_out, _in(fil, "Radius"))
        SI(fil, "Limit Radius", True)
        if _find_in(fil, "Count") is not None:
            link(seg_out, _in(fil, "Count"))
        else:
            warn.append("Fillet Curve: нет входа 'Count'")
        # Уровень земли под этим контуром: Fill Curve строит в плоскости
        # XY и высоту теряет, а вернуть её надо разную — трава ложится на
        # землю, тротуар на верх камня.
        cz = N('GeometryNodeInputPosition', -2100, y0 + 300)
        czs = N('ShaderNodeSeparateXYZ', -1920, y0 + 300)
        link(cz.outputs[0], czs.inputs[0])
        geo = store(_out(fil, "Curve"), "%s_%s" % (tag, Z_ATTR),
                    czs.outputs['Z'], -1920, y0 + 160, 'FLOAT', 'POINT',
                    "уровень земли")
        # Длина вдоль линии и полная длина сплайна: по ним раскладывается
        # UV всего, что строится по этому контуру.
        csp = N('GeometryNodeSplineParameter', -2100, y0 + 460)
        geo = store(geo, "%s_%s" % (tag, U_ATTR), _out(csp, "Length"),
                    -1920, y0 + 460, 'FLOAT', 'POINT', "U вдоль линии")
        csl = N('GeometryNodeSplineLength', -2100, y0 + 620)
        geo = store(geo, "%s_%s" % (tag, S_ATTR), _out(csl, "Length"),
                    -1920, y0 + 620, 'FLOAT', 'POINT', "длина сплайна")
        # Касательная и позиция точки линии: по ним выправляется перекос
        # UV там, где точка отъехала вбок — на дуге и в изломе.
        ctn = N('GeometryNodeInputTangent', -2100, y0 + 780)
        geo = store(geo, "%s_%s" % (tag, T_ATTR), ctn.outputs[0],
                    -1920, y0 + 780, 'FLOAT_VECTOR', 'POINT', "касательная")
        cpp = N('GeometryNodeInputPosition', -2100, y0 + 940)
        return store(geo, "%s_%s" % (tag, P_ATTR), cpp.outputs[0],
                     -1920, y0 + 940, 'FLOAT_VECTOR', 'POINT',
                     "позиция линии")

    def _profile_box(tag, n, y0):
        """Профиль камня: прямоугольник по центру оси, низом на земле."""
        quad = N('GeometryNodeCurvePrimitiveQuadrilateral', -2460, y0 - 1100,
                 "%s: профиль" % tag, mode='RECTANGLE')
        link(G("Ширина"), _in(quad, "Width"))
        link(G("Высота"), _in(quad, "Height"))
        pshift = N('ShaderNodeCombineXYZ', -2460, y0 - 1240)
        link(hoff, pshift.inputs['Y'])
        lift = N('GeometryNodeSetPosition', -2280, y0 - 1100, "посадка")
        link(_out(quad, "Curve"), _in(lift, "Geometry"))
        link(pshift.outputs[0], _in(lift, "Offset"))
        lp = N('GeometryNodeInputPosition', -2280, y0 - 1240)
        lsx = N('ShaderNodeSeparateXYZ', -2100, y0 - 1240)
        link(lp.outputs[0], lsx.inputs[0])
        prof = store(_out(lift, "Geometry"), n(L_ATTR), lsx.outputs['Y'],
                     -2100, y0 - 1100, 'FLOAT', 'POINT', "уровень профиля")

        return prof

    def region(mesh, tag, y0, floor=False):
        """Строит полосу по контуру области. Отступ РАВНОМЕРНЫЙ по всему
        контуру — ширина камня, — поэтому смешанных величин в вершине не
        возникает и сдвиг считается после скругления, по радиусу дуги.

        Возвращает (полоса, отступлённый контур)."""
        n = lambda name: "%s_%s" % (tag, name)

        # направление внутрь области: центр смежной грани минус позиция
        pos = N('GeometryNodeInputPosition', -2460, y0 + 300)
        fcen = on_domain(pos.outputs[0], 'FACE', -2280, y0 + 300,
                         'FLOAT_VECTOR', "центр грани")
        inw = vmath('SUBTRACT', -2100, y0 + 300, "внутрь области")
        link(_out(fcen, "Value"), inw.inputs[0])
        link(pos.outputs[0], inw.inputs[1])
        inflat = vmath('MULTIPLY', -1920, y0 + 300, "в плане")
        link(inw.outputs[0], inflat.inputs[0])
        inflat.inputs[1].default_value = (1.0, 1.0, 0.0)
        geo = store(mesh, n(IN_ATTR), inflat.outputs[0], -2460, y0,
                    'FLOAT_VECTOR', 'POINT', "внутрь области")

        cont = contour(geo, tag, y0)
        sp = N('GeometryNodeSplineParameter', -1920, y0 + 160)
        cur = store(cont, n(U_ATTR), _out(sp, "Length"),
                    -1920, y0, 'FLOAT', 'POINT', "U вдоль линии")
        sl = N('GeometryNodeSplineLength', -1740, y0 + 160)
        cur = store(cur, n(S_ATTR), _out(sl, "Length"), -1740, y0, 'FLOAT',
                    'POINT', "длина сплайна")
        tn = N('GeometryNodeInputTangent', -1560, y0 + 160)
        cur = store(cur, n(T_ATTR), tn.outputs[0], -1560, y0,
                    'FLOAT_VECTOR', 'POINT', "касательная")
        pp = N('GeometryNodeInputPosition', -1380, y0 + 160)
        cur = store(cur, n(P_ATTR), pp.outputs[0], -1380, y0,
                    'FLOAT_VECTOR', 'POINT', "позиция линии")
        zsep = N('ShaderNodeSeparateXYZ', -1200, y0 + 160)
        link(pp.outputs[0], zsep.inputs[0])
        cur = store(cur, n(Z_ATTR), zsep.outputs['Z'], -1200, y0, 'FLOAT',
                    'POINT', "уровень линии")

        # митра и сдвиг: перпендикуляры рёбер уже скруглённого контура
        wire = N('GeometryNodeCurveToMesh', -1020, y0, "%s: в рёбра" % tag)
        link(cur, _in(wire, "Curve"))

        ev = N('GeometryNodeInputMeshEdgeVertices', -2460, y0 - 500)
        ed = vmath('SUBTRACT', -2280, y0 - 500, "направление ребра")
        link(_out(ev, "Position 2"), ed.inputs[0])
        link(_out(ev, "Position 1"), ed.inputs[1])
        edf = vmath('MULTIPLY', -2100, y0 - 500, "в плане")
        link(ed.outputs[0], edf.inputs[0])
        edf.inputs[1].default_value = (1.0, 1.0, 0.0)
        ep = vmath('CROSS_PRODUCT', -1920, y0 - 500, "перпендикуляр ребра")
        link(edf.outputs[0], ep.inputs[0])
        ep.inputs[1].default_value = (0.0, 0.0, 1.0)
        epn = vmath('NORMALIZE', -1740, y0 - 500)
        link(ep.outputs[0], epn.inputs[0])
        ina = attr(n(IN_ATTR), -1920, y0 - 640, 'FLOAT_VECTOR',
                   "внутрь области")
        sdot = vmath('DOT_PRODUCT', -1740, y0 - 640)
        link(epn.outputs[0], sdot.inputs[0])
        link(_out(ina, "Attribute"), sdot.inputs[1])
        ssg = fmath('SIGN', -1560, y0 - 640, "знак стороны")
        link(_out(sdot, "Value"), ssg.inputs[0])
        epin = vmath('SCALE', -1380, y0 - 500, "перпендикуляр внутрь")
        link(epn.outputs[0], epin.inputs[0])
        link(ssg.outputs[0], _in(epin, "Scale"))
        avg = on_domain(epin.outputs[0], 'EDGE', -1200, y0 - 500,
                        'FLOAT_VECTOR', "среднее по рёбрам")

        # |avg| = cos(угол/2) для масштаба профиля, |avg|^2 для сдвига
        alenl = vmath('LENGTH', -1020, y0 - 640, "|avg|")
        link(_out(avg, "Value"), alenl.inputs[0])
        acll = fmath('MAXIMUM', -840, y0 - 640, "не ноль")
        link(_out(alenl, "Value"), acll.inputs[0])
        acll.inputs[1].default_value = MITER_EPS
        mit = fmath('DIVIDE', -660, y0 - 640, "масштаб профиля")
        mit.inputs[0].default_value = 1.0
        link(acll.outputs[0], mit.inputs[1])
        alen = vmath('DOT_PRODUCT', -1020, y0 - 780, "|avg| в квадрате")
        link(_out(avg, "Value"), alen.inputs[0])
        link(_out(avg, "Value"), alen.inputs[1])
        acl = fmath('MAXIMUM', -840, y0 - 780, "не ноль")
        link(_out(alen, "Value"), acl.inputs[0])
        acl.inputs[1].default_value = MITER_EPS

        def offset_by(dist, x, y, label):
            sc = fmath('DIVIDE', x, y, "длина сдвига")
            link(dist, sc.inputs[0])
            link(acl.outputs[0], sc.inputs[1])
            v = vmath('SCALE', x + 180, y, label)
            link(_out(avg, "Value"), v.inputs[0])
            link(sc.outputs[0], _in(v, "Scale"))
            return v.outputs[0]

        d_axis, d_edge = half_w.outputs[0], G("Ширина")
        off_axis = offset_by(d_axis, -660, y0 - 780, "ось полосы")
        off_fill = offset_by(d_edge, -660, y0 - 920, "контур заливки")

        wgeo = store(_out(wire, "Mesh"), n(M_ATTR), mit.outputs[0],
                     -840, y0, 'FLOAT', 'POINT', "митра")
        axis = N('GeometryNodeSetPosition', -660, y0, "ось бордюра")
        link(wgeo, _in(axis, "Geometry"))
        link(off_axis, _in(axis, "Offset"))
        back = N('GeometryNodeMeshToCurve', -480, y0, "%s: ось" % tag,
                 mode='EDGES')
        link(_out(axis, "Geometry"), _in(back, "Mesh"))

        inm = N('GeometryNodeSetPosition', -660, y0 - 300, "контур заливки")
        link(wgeo, _in(inm, "Geometry"))
        link(off_fill, _in(inm, "Offset"))
        inner = N('GeometryNodeMeshToCurve', -480, y0 - 300,
                  "%s: отступ" % tag, mode='EDGES')
        link(_out(inm, "Geometry"), _in(inner, "Mesh"))

        prof = _profile_box(tag, n, y0)

        c2m = N('GeometryNodeCurveToMesh', -300, y0, "%s: бордюр" % tag)
        link(_out(back, "Curve"), _in(c2m, "Curve"))
        link(prof, _in(c2m, "Profile Curve"))
        ma = attr(n(M_ATTR), -480, y0 - 160, 'FLOAT', "митра")
        sc_sock = _find_in(c2m, "Scale")
        if sc_sock is not None:
            link(_out(ma, "Attribute"), sc_sock)
        else:
            setr = N('GeometryNodeSetCurveRadius', -480, y0 + 460, "митра")
            link(_out(back, "Curve"), _in(setr, "Curve"))
            link(_out(ma, "Attribute"), _in(setr, "Radius"))
            link(_out(setr, "Curve"), _in(c2m, "Curve"))

        # Расстояние точки до линии в плане. По нему различаются стенки
        # (сторону профиля задаёт нормаль кривой, а она зависит от
        # направления обхода контура) и по нему же строится спуск.
        p0a = attr(n(P_ATTR), 60, y0 - 700, 'FLOAT_VECTOR', "позиция линии")
        dpos = N('GeometryNodeInputPosition', 60, y0 - 840)
        dvec = vmath('SUBTRACT', 240, y0 - 700, "отъезд от линии")
        link(dpos.outputs[0], dvec.inputs[0])
        link(_out(p0a, "Attribute"), dvec.inputs[1])
        dflat = vmath('MULTIPLY', 420, y0 - 700, "в плане")
        link(dvec.outputs[0], dflat.inputs[0])
        dflat.inputs[1].default_value = (1.0, 1.0, 0.0)
        dlen = vmath('LENGTH', 600, y0 - 700, "расстояние до линии")
        link(dflat.outputs[0], dlen.inputs[0])

        # вернуть высоту, растянутую масштабом
        za = attr(n(Z_ATTR), -300, y0 - 300, 'FLOAT')
        la = attr(n(L_ATTR), -300, y0 - 440, 'FLOAT')
        lvl = _out(la, "Attribute")
        zsum0 = fmath('ADD', -120, y0 - 370, "высота по профилю")
        link(_out(za, "Attribute"), zsum0.inputs[0])
        link(lvl, zsum0.inputs[1])
        if floor:
            # Низ стенки поднимается на уровень плитки: там, где она уже
            # вровень с камнем, стенка вырождается в ничто и её грани
            # удаляются ниже. Ровно так же сделана заплатка в эталоне.
            zfl = fmath('ADD', -300, y0 - 660, "уровень плитки")
            link(_out(za, "Attribute"), zfl.inputs[0])
            link(plate_on, zfl.inputs[1])
            # Только внутри. На краю участка та же стенка смотрит наружу,
            # под ней нет никакой плитки, и поднимать её низ нельзя —
            # камень повиснет над землёй.
            zra = attr(R_ATTR, -480, y0 - 800, 'FLOAT', "край участка")
            zrim = cmp(_out(zra, "Attribute"), 0.5, 'GREATER_THAN', -300,
                       y0 - 800, 'FLOAT', "точка на краю")
            zfle = switchf(zrim, zfl.outputs[0], _out(za, "Attribute"),
                           -120, y0 - 800, "пол: плитка или земля")
            zsum = fmath('MAXIMUM', -60, y0 - 370, "не ниже плитки")
            link(zsum0.outputs[0], zsum.inputs[0])
            link(zfle, zsum.inputs[1])
        else:
            zsum = zsum0
        mp = N('GeometryNodeInputPosition', -300, y0 - 580)
        ms = N('ShaderNodeSeparateXYZ', -120, y0 - 580)
        link(mp.outputs[0], ms.inputs[0])
        mx = N('ShaderNodeCombineXYZ', 60, y0 - 470)
        link(ms.outputs['X'], mx.inputs['X'])
        link(ms.outputs['Y'], mx.inputs['Y'])
        link(zsum.outputs[0], mx.inputs['Z'])
        fixz = N('GeometryNodeSetPosition', -120, y0, "высота на место")
        link(_out(c2m, "Mesh"), _in(fixz, "Geometry"))
        link(mx.outputs[0], _in(fixz, "Position"))

        fdist = on_domain(_out(dlen, "Value"), 'FACE', 780, y0 - 700,
                          'FLOAT', "расстояние по грани")
        flvl = on_domain(_out(la, "Attribute"), 'FACE', 780, y0 - 840,
                         'FLOAT', "высота грани")
        hq = fmath('MULTIPLY', 600, y0 - 980, "четверть высоты")
        link(G("Высота"), hq.inputs[0])
        hq.inputs[1].default_value = 0.25
        top_thr = fmath('ADD', 780, y0 - 980, "порог верха")
        link(hoff, top_thr.inputs[0])
        link(hq.outputs[0], top_thr.inputs[1])
        bot_thr = fmath('SUBTRACT', 780, y0 - 1120, "порог низа")
        link(hoff, bot_thr.inputs[0])
        link(hq.outputs[0], bot_thr.inputs[1])
        is_top = cmp(_out(flvl, "Value"), top_thr.outputs[0],
                     'GREATER_THAN', 960, y0 - 840, 'FLOAT', "верх")
        is_bot = cmp(_out(flvl, "Value"), bot_thr.outputs[0], 'LESS_THAN',
                     960, y0 - 980, 'FLOAT', "низ")
        # Стенка, обращённая к тротуару, остаётся всегда. Раньше она
        # удалялась как невидимая — покрытие лежало на одном уровне с
        # верхом камня и её нечем было увидеть. Теперь плитка наклонена
        # вниз к краю участка, стенка открывается, и без неё на её месте
        # дыра. Дальняя стенка стоит под краем газона и не видна никогда:
        # её и низ по-прежнему вон.
        near_thr = fmath('MULTIPLY', 780, y0 - 1540, "четверть ширины")
        link(G("Ширина"), near_thr.inputs[0])
        near_thr.inputs[1].default_value = 0.25
        is_seamw = cmp(_out(fdist, "Value"), near_thr.outputs[0],
                       'LESS_THAN', 960, y0 - 1540, 'FLOAT',
                       "стенка к тротуару")
        not_top = boolean('NOT', is_top, None, 1680, y0 - 1540, "не верх")
        hid_w = boolean('AND', not_top, boolean('NOT', is_seamw, None,
                                                1860, y0 - 1400,
                                                "не к тротуару"),
                        2040, y0 - 1400, "стенка под газоном")
        del_sel = boolean('OR', is_bot, hid_w, 1140, y0 - 1120,
                          "низ и стенка под газоном")
        if floor:
            # Там, где плитка вровень с верхом камня, стенка к тротуару
            # схлопнулась в линию — такие грани вон.
            fhi = on_domain(plate_on, 'POINT', 1140, y0 - 1680, 'FLOAT',
                            "уровень плитки по грани")
            fthr = fmath('SUBTRACT', 1320, y0 - 1820, "почти вровень")
            link(G("Высота"), fthr.inputs[0])
            fthr.inputs[1].default_value = 1e-4
            fflat = cmp(_out(fhi, "Value"), fthr.outputs[0], 'GREATER_THAN',
                        1500, y0 - 1680, 'FLOAT', "плитка вровень")
            fra = attr(R_ATTR, 1140, y0 - 1960, 'FLOAT', "край участка")
            frf = on_domain(_out(fra, "Attribute"), 'FACE', 1320, y0 - 1960,
                            'FLOAT', "доля концов на краю")
            fon = cmp(_out(frf, "Value"), 0.75, 'GREATER_THAN', 1500,
                      y0 - 1960, 'FLOAT', "грань на краю участка")
            fin = boolean('NOT', fon, None, 1680, y0 - 1960, "не на краю")
            fgone = boolean('AND', boolean('AND', is_seamw, fflat, 1680,
                                           y0 - 1680, "стенка схлопнулась"),
                            fin, 1860, y0 - 1680, "и это не край")
            del_sel = boolean('OR', del_sel, fgone, 1860, y0 - 1120,
                              "и схлопнувшаяся стенка")
        dele = N('GeometryNodeDeleteGeometry', 60, y0, "%s: лишние" % tag,
                 domain='FACE', mode='ALL')
        link(_out(fixz, "Geometry"), _in(dele, "Geometry"))
        link(del_sel, _in(dele, "Selection"))
        cleaned = _out(dele, "Geometry")

        # Сторона стенки: ближняя к контуру смотрит на тротуар, дальняя —
        # вглубь травы. Нужно это только для нормалей.
        hw_thr = fmath('MULTIPLY', 780, y0 - 1680, "половина ширины")
        link(G("Ширина"), hw_thr.inputs[0])
        hw_thr.inputs[1].default_value = 0.5
        is_farw = cmp(_out(fdist, "Value"), hw_thr.outputs[0],
                      'GREATER_THAN', 960, y0 - 1680, 'FLOAT',
                      "дальняя стенка")

        # нормали: у верха вверх, у каждой стенки — от середины камня
        inn2 = attr(n(IN_ATTR), 1320, y0 - 700, 'FLOAT_VECTOR')
        innn = vmath('NORMALIZE', 1500, y0 - 700)
        link(_out(inn2, "Attribute"), innn.inputs[0])
        seamw = vmath('SCALE', 1680, y0 - 620, "на тротуар")
        link(innn.outputs[0], seamw.inputs[0])
        SI(seamw, "Scale", -1.0)
        wref = N('GeometryNodeSwitch', 1860, y0 - 620, "сторона стенки",
                 input_type='VECTOR')
        link(is_farw, _in(wref, "Switch"))
        link(seamw.outputs[0], _in(wref, "False"))
        link(innn.outputs[0], _in(wref, "True"))
        upv = N('ShaderNodeCombineXYZ', 1680, y0 - 840)
        upv.inputs['Z'].default_value = 1.0
        nref = N('GeometryNodeSwitch', 2040, y0 - 760, "куда смотреть",
                 input_type='VECTOR')
        link(is_top, _in(nref, "Switch"))
        link(_out(wref, "Output"), _in(nref, "False"))
        link(upv.outputs[0], _in(nref, "True"))
        fnrm = N('GeometryNodeInputNormal', 1860, y0 - 900)
        ndot = vmath('DOT_PRODUCT', 2040, y0 - 760, "смотрит внутрь")
        link(fnrm.outputs[0], ndot.inputs[0])
        link(_out(nref, "Output"), ndot.inputs[1])
        nbad = cmp(_out(ndot, "Value"), 0.0, 'LESS_THAN', 2220, y0 - 760,
                   'FLOAT', "развернуть")
        flip = N('GeometryNodeFlipFaces', 240, y0, "%s: нормали" % tag)
        link(cleaned, _in(flip, "Mesh"))
        link(nbad, _in(flip, "Selection"))

        # -- UV --------------------------------------------------------
        ua = attr(n(U_ATTR), 420, y0 + 700, 'FLOAT')
        sla = attr(n(S_ATTR), 420, y0 + 560, 'FLOAT')
        p0b = attr(n(P_ATTR), 420, y0 + 420, 'FLOAT_VECTOR')
        tana = attr(n(T_ATTR), 420, y0 + 280, 'FLOAT_VECTOR')

        uavg = on_domain(_out(ua, "Attribute"), 'FACE', 600, y0 + 700,
                         'FLOAT', "среднее U по грани")
        udif = fmath('SUBTRACT', 780, y0 + 700, "ниже среднего")
        link(_out(uavg, "Value"), udif.inputs[0])
        link(_out(ua, "Attribute"), udif.inputs[1])
        uq = fmath('MULTIPLY', 780, y0 + 560, "четверть периметра")
        link(_out(sla, "Attribute"), uq.inputs[0])
        uq.inputs[1].default_value = 0.25
        uwr = cmp(udif.outputs[0], uq.outputs[0], 'GREATER_THAN',
                  960, y0 + 630, 'FLOAT', "угол за швом")
        uad = fmath('MULTIPLY', 1140, y0 + 630, "прибавка периметра")
        link(uwr, uad.inputs[0])
        link(_out(sla, "Attribute"), uad.inputs[1])
        useam = fmath('ADD', 1320, y0 + 630, "U без шва")
        link(_out(ua, "Attribute"), useam.inputs[0])
        link(uad.outputs[0], useam.inputs[1])

        npos = N('GeometryNodeInputPosition', 600, y0 + 420)
        away = vmath('SUBTRACT', 780, y0 + 420, "отъезд вбок")
        link(npos.outputs[0], away.inputs[0])
        link(_out(p0b, "Attribute"), away.inputs[1])
        awayf = vmath('MULTIPLY', 960, y0 + 420, "в плане")
        link(away.outputs[0], awayf.inputs[0])
        awayf.inputs[1].default_value = (1.0, 1.0, 0.0)
        fp0 = on_domain(_out(p0b, "Attribute"), 'FACE', 600, y0 + 280,
                        'FLOAT_VECTOR', "линия по грани")
        fdir = vmath('SUBTRACT', 780, y0 + 280, "к середине грани")
        link(_out(fp0, "Value"), fdir.inputs[0])
        link(_out(p0b, "Attribute"), fdir.inputs[1])
        fdirf = vmath('MULTIPLY', 960, y0 + 280, "в плане")
        link(fdir.outputs[0], fdirf.inputs[0])
        fdirf.inputs[1].default_value = (1.0, 1.0, 0.0)
        fdirn = vmath('NORMALIZE', 1140, y0 + 280)
        link(fdirf.outputs[0], fdirn.inputs[0])
        tanf = vmath('MULTIPLY', 960, y0 + 140, "касательная в плане")
        link(_out(tana, "Attribute"), tanf.inputs[0])
        tanf.inputs[1].default_value = (1.0, 1.0, 0.0)
        fdot = vmath('DOT_PRODUCT', 1140, y0 + 140, "вперёд или назад")
        link(fdirf.outputs[0], fdot.inputs[0])
        link(tanf.outputs[0], fdot.inputs[1])
        fsgn = fmath('SIGN', 1320, y0 + 140, "знак")
        link(_out(fdot, "Value"), fsgn.inputs[0])
        fwd = vmath('SCALE', 1320, y0 + 280, "вперёд")
        link(fdirn.outputs[0], fwd.inputs[0])
        link(fsgn.outputs[0], _in(fwd, "Scale"))
        ush = vmath('DOT_PRODUCT', 1500, y0 + 420, "скос")
        link(awayf.outputs[0], ush.inputs[0])
        link(fwd.outputs[0], ush.inputs[1])
        umet = fmath('ADD', 1680, y0 + 420, "U в метрах")
        link(useam.outputs[0], umet.inputs[0])
        link(_out(ush, "Value"), umet.inputs[1])
        ufit = fmath('MULTIPLY', 1860, y0 + 420, "U без искажений")
        link(umet.outputs[0], ufit.inputs[0])
        link(kden.outputs[0], ufit.inputs[1])
        us = fmath('MULTIPLY', 2040, y0 + 420, "тайлинг")
        link(ufit.outputs[0], us.inputs[0])
        link(G("Тайлинг вдоль"), us.inputs[1])
        usn = fmath('MULTIPLY', 2220, y0 + 420, "вдоль наоборот")
        link(us.outputs[0], usn.inputs[0])
        usn.inputs[1].default_value = -1.0
        u_side = switchf(G("Бок X"), us.outputs[0],
                         usn.outputs[0], 2400, y0 + 480, "бок вдоль")
        u_top = switchf(G("Верх X"), us.outputs[0],
                        usn.outputs[0], 2400, y0 + 340, "верх вдоль")
        ufin = switchf(is_top, u_side, u_top, 2580, y0 + 420,
                       "U: бок или верх")

        vbot = fmath('SUBTRACT', 600, y0 + 20, "низ сечения")
        link(hoff, vbot.inputs[0])
        link(half_h.outputs[0], vbot.inputs[1])
        vup = fmath('SUBTRACT', 780, y0 + 20, "высота над низом")
        link(_out(la, "Attribute"), vup.inputs[0])
        link(vbot.outputs[0], vup.inputs[1])
        vmul = fmath('MULTIPLY', 960, y0 + 20, "в текстуре")
        link(vup.outputs[0], vmul.inputs[0])
        link(kden.outputs[0], vmul.inputs[1])
        vmir = fmath('SUBTRACT', 1140, y0 + 20, "бок наоборот")
        link(rowh.outputs[0], vmir.inputs[0])
        link(vmul.outputs[0], vmir.inputs[1])
        vloc = switchf(G("Бок Y"), vmul.outputs[0],
                       vmir.outputs[0], 1320, y0 + 20, "бок поперёк")
        vb = row_base("Строка бока", 1320, y0 + 160)
        v_side = fmath('ADD', 1680, y0 + 20, "V бока")
        link(vb.outputs[0], v_side.inputs[0])
        link(vloc, v_side.inputs[1])

        # По верху V берётся ПЕРПЕНДИКУЛЯРНОЕ расстояние: в изломе точка
        # отъезжает по биссектрисе дальше ширины полосы, и митра как раз
        # равна 1/cos(угол/2), поэтому делим на неё.
        mfv = attr(n(M_ATTR), 600, y0 - 120, 'FLOAT', "митра")
        mcv = fmath('MAXIMUM', 780, y0 - 120, "не ноль")
        link(_out(mfv, "Attribute"), mcv.inputs[0])
        mcv.inputs[1].default_value = MITER_EPS
        pdm = fmath('DIVIDE', 960, y0 - 120, "поперёк, перпендикулярно")
        link(_out(dlen, "Value"), pdm.inputs[0])
        link(mcv.outputs[0], pdm.inputs[1])
        tmul = fmath('MULTIPLY', 1140, y0 - 120, "ширина в текстуре")
        link(pdm.outputs[0], tmul.inputs[0])
        link(kden.outputs[0], tmul.inputs[1])
        twk = fmath('MULTIPLY', 1140, y0 - 260, "полная ширина")
        link(G("Ширина"), twk.inputs[0])
        link(kden.outputs[0], twk.inputs[1])
        tmir = fmath('SUBTRACT', 1320, y0 - 260, "верх наоборот")
        link(twk.outputs[0], tmir.inputs[0])
        link(tmul.outputs[0], tmir.inputs[1])
        tloc = switchf(G("Верх Y"), tmul.outputs[0],
                       tmir.outputs[0], 1500, y0 - 120, "верх поперёк")
        tb = row_base("Строка верха", 1320, y0 - 400)
        v_top = fmath('ADD', 1680, y0 - 120, "V верха")
        link(tb.outputs[0], v_top.inputs[0])
        link(tloc, v_top.inputs[1])
        vfin = switchf(is_top, v_side.outputs[0], v_top.outputs[0],
                       1860, y0 - 60, "V: бок или верх")

        curb = store(_out(flip, "Mesh"), UU_ATTR, ufin, 420, y0, 'FLOAT',
                     'CORNER', "U бордюра")
        curb = store(curb, VV_ATTR, vfin, 600, y0, 'FLOAT', 'CORNER',
                     "V бордюра")

        return curb, _out(inner, "Curve")

    # -- масштаб текстуры (нужен внутри region) --------------------------
    rows = fmath('MAXIMUM', -3000, 700, "строк, не ноль")
    link(G("Строк в текстуре"), rows.inputs[0])
    rows.inputs[1].default_value = 1.0
    rowh = fmath('DIVIDE', -2820, 700, "высота строки")
    rowh.inputs[0].default_value = 1.0
    link(rows.outputs[0], rowh.inputs[1])
    hsafe = fmath('MAXIMUM', -3000, 560, "высота, не ноль")
    link(G("Высота"), hsafe.inputs[0])
    hsafe.inputs[1].default_value = 1e-6
    kden = fmath('DIVIDE', -2640, 700, "единиц текстуры на метр")
    link(rowh.outputs[0], kden.inputs[0])
    link(hsafe.outputs[0], kden.inputs[1])

    def row_base(sock_name, x, y):
        m1 = fmath('SUBTRACT', x, y, "номер минус один")
        link(G(sock_name), m1.inputs[0])
        m1.inputs[1].default_value = 1.0
        b = fmath('MULTIPLY', x + 180, y, "низ строки")
        link(m1.outputs[0], b.inputs[0])
        link(rowh.outputs[0], b.inputs[1])
        return b

    walk_mesh = _out(wsep, "Selection")
    wpos = N('GeometryNodeInputPosition', -3000, -6500)
    wfc = on_domain(wpos.outputs[0], 'FACE', -2820, -6500, 'FLOAT_VECTOR',
                    "центр грани")
    win = vmath('SUBTRACT', -2640, -6500, "внутрь тротуара")
    link(_out(wfc, "Value"), win.inputs[0])
    link(wpos.outputs[0], win.inputs[1])
    winf = vmath('MULTIPLY', -2460, -6500, "в плане")
    link(win.outputs[0], winf.inputs[0])
    winf.inputs[1].default_value = (1.0, 1.0, 0.0)
    walk_mesh = store(walk_mesh, "walk_%s" % IN_ATTR, winf.outputs[0],
                      -2280, -6500, 'FLOAT_VECTOR', 'POINT',
                      "внутрь тротуара")
    walk_cont = contour(walk_mesh, "walk", -6800)

    # Внутренняя кромка каменной полосы: контур, отступлённый внутрь на
    # «Ширину» ТОЛЬКО на краю участка. У травы отступ нулевой, лишних
    # вершин там не появляется.
    wwire = N('GeometryNodeCurveToMesh', -1020, -6800, "контур в рёбра")
    link(walk_cont, _in(wwire, "Curve"))
    wev = N('GeometryNodeInputMeshEdgeVertices', -1020, -7000)
    wed = vmath('SUBTRACT', -840, -7000, "направление ребра")
    link(_out(wev, "Position 2"), wed.inputs[0])
    link(_out(wev, "Position 1"), wed.inputs[1])
    wedf = vmath('MULTIPLY', -660, -7000, "в плане")
    link(wed.outputs[0], wedf.inputs[0])
    wedf.inputs[1].default_value = (1.0, 1.0, 0.0)
    wep = vmath('CROSS_PRODUCT', -480, -7000, "перпендикуляр ребра")
    link(wedf.outputs[0], wep.inputs[0])
    wep.inputs[1].default_value = (0.0, 0.0, 1.0)
    wepn = vmath('NORMALIZE', -300, -7000)
    link(wep.outputs[0], wepn.inputs[0])
    wina = attr("walk_%s" % IN_ATTR, -480, -7160, 'FLOAT_VECTOR',
                "внутрь тротуара")
    wdot = vmath('DOT_PRODUCT', -300, -7160)
    link(wepn.outputs[0], wdot.inputs[0])
    link(_out(wina, "Attribute"), wdot.inputs[1])
    wsg = fmath('SIGN', -120, -7160, "знак стороны")
    link(_out(wdot, "Value"), wsg.inputs[0])
    wepin = vmath('SCALE', 60, -7000, "перпендикуляр внутрь")
    link(wepn.outputs[0], wepin.inputs[0])
    link(wsg.outputs[0], _in(wepin, "Scale"))
    # Ребро края участка — то, у которого ОБА конца на краю. По нему идёт
    # полоса камня. Помечено ли оно острым, полосу не решает: пометка
    # меняет только высоту — см. plate_on ниже.
    wrfa = attr(R_ATTR, 60, -7300, 'FLOAT', "край участка")
    wrha = cmp(_out(wrfa, "Attribute"), 0.99, 'GREATER_THAN', 240, -7300,
               'FLOAT', "точка точно на краю")
    wrna = switchf(wrha, 0.0, 1.0, 420, -7300, "точка края: 0 или 1")
    were = on_domain(wrna, 'POINT', 600, -7300, 'FLOAT', "по концам ребра")
    wreb = cmp(_out(were, "Value"), 0.99, 'GREATER_THAN', 780, -7300,
               'FLOAT', "ребро края участка")
    wren = switchf(wreb, 0.0, 1.0, 960, -7300, "ребро края: 0 или 1")

    # Ребро спуска — помеченное острым. Их проволока пойдёт целью замера
    # высоты: рядом с ней плита сходит на землю, вдали держит полную.
    wdfa = attr(D_ATTR, 60, -7620, 'FLOAT', "помеченный край")
    wdha = cmp(_out(wdfa, "Attribute"), 0.99, 'GREATER_THAN', 240, -7620,
               'FLOAT', "точка на помеченном крае")
    wdna = switchf(wdha, 0.0, 1.0, 420, -7620, "точка спуска: 0 или 1")
    wdee = on_domain(wdna, 'POINT', 600, -7620, 'FLOAT', "по концам ребра")
    wdeb = cmp(_out(wdee, "Value"), 0.99, 'GREATER_THAN', 780, -7620,
               'FLOAT', "ребро спуска")

    # Отступ РЕБРА: ширина у ребра края, ноль у бокового.
    wde = fmath('MULTIPLY', 420, -7000, "отступ ребра")
    link(G("Ширина"), wde.inputs[0])
    link(wren, wde.inputs[1])
    wndv = vmath('SCALE', 600, -7000, "n * d")
    link(wepin.outputs[0], wndv.inputs[0])
    link(wde.outputs[0], _in(wndv, "Scale"))

    # Средние по рёбрам точки: из них восстанавливается пересечение.
    wP = on_domain(wndv.outputs[0], 'EDGE', 780, -7000, 'FLOAT_VECTOR', "P")
    wQ = on_domain(wepin.outputs[0], 'EDGE', 780, -7160, 'FLOAT_VECTOR', "Q")
    wR = on_domain(wde.outputs[0], 'EDGE', 780, -7320, 'FLOAT', "R")
    wQ2 = vmath('DOT_PRODUCT', 960, -7160, "|Q| в квадрате")
    link(_out(wQ, "Value"), wQ2.inputs[0])
    link(_out(wQ, "Value"), wQ2.inputs[1])
    wcc = fmath('MULTIPLY_ADD', 1140, -7160, "c = 2|Q|^2 - 1")
    link(_out(wQ2, "Value"), wcc.inputs[0])
    wcc.inputs[1].default_value = 2.0
    wcc.inputs[2].default_value = -1.0

    wP2 = vmath('SCALE', 1140, -7000, "2P")
    link(_out(wP, "Value"), wP2.inputs[0])
    SI(wP2, "Scale", 2.0)
    wRQ = vmath('SCALE', 960, -7320, "RQ")
    link(_out(wQ, "Value"), wRQ.inputs[0])
    link(_out(wR, "Value"), _in(wRQ, "Scale"))
    wRQ4 = vmath('SCALE', 1140, -7320, "4RQ")
    link(wRQ.outputs[0], wRQ4.inputs[0])
    SI(wRQ4, "Scale", 4.0)
    wbr = vmath('SUBTRACT', 1320, -7320, "4RQ - 2P")
    link(wRQ4.outputs[0], wbr.inputs[0])
    link(wP2.outputs[0], wbr.inputs[1])
    wbrc = vmath('SCALE', 1500, -7320, "c(4RQ - 2P)")
    link(wbr.outputs[0], wbrc.inputs[0])
    link(wcc.outputs[0], _in(wbrc, "Scale"))
    wnum = vmath('SUBTRACT', 1680, -7000, "числитель")
    link(wP2.outputs[0], wnum.inputs[0])
    link(wbrc.outputs[0], wnum.inputs[1])
    wc2 = fmath('MULTIPLY', 1320, -7160, "c^2")
    link(wcc.outputs[0], wc2.inputs[0])
    link(wcc.outputs[0], wc2.inputs[1])
    wden = fmath('SUBTRACT', 1500, -7160, "1 - c^2")
    wden.inputs[0].default_value = 1.0
    link(wc2.outputs[0], wden.inputs[1])
    wdcl = fmath('MAXIMUM', 1680, -7160, "не ноль")
    link(wden.outputs[0], wdcl.inputs[0])
    wdcl.inputs[1].default_value = 1e-6
    wdinv = fmath('DIVIDE', 1860, -7160, "1 / (1 - c^2)")
    wdinv.inputs[0].default_value = 1.0
    link(wdcl.outputs[0], wdinv.inputs[1])
    wtgen = vmath('SCALE', 1860, -7000, "общий случай")
    link(wnum.outputs[0], wtgen.inputs[0])
    link(wdinv.outputs[0], _in(wtgen, "Scale"))

    # Прямой участок: рёбра сонаправлены, знаменатель вырожден.
    wQ2c = fmath('MAXIMUM', 1320, -7480, "не ноль")
    link(_out(wQ2, "Value"), wQ2c.inputs[0])
    wQ2c.inputs[1].default_value = MITER_EPS
    wflat = fmath('DIVIDE', 1500, -7480, "R / |Q|^2")
    link(_out(wR, "Value"), wflat.inputs[0])
    link(wQ2c.outputs[0], wflat.inputs[1])
    wtflat = vmath('SCALE', 1680, -7480, "прямой участок")
    link(_out(wQ, "Value"), wtflat.inputs[0])
    link(wflat.outputs[0], _in(wtflat, "Scale"))

    wnear = cmp(wden.outputs[0], 1e-4, 'LESS_THAN', 1860, -7480, 'FLOAT',
                "рёбра сонаправлены")
    wtsw = N('GeometryNodeSwitch', 2040, -7160, "сдвиг точки",
             input_type='VECTOR')
    link(wnear, _in(wtsw, "Switch"))
    link(wtgen.outputs[0], _in(wtsw, "False"))
    link(wtflat.outputs[0], _in(wtsw, "True"))
    wofs_out = _out(wtsw, "Output")

    # Тот же признак точки нужен для отбора граней полосы.
    won = wrna

    # Сдвиг кладётся атрибутом ТОЧКИ и дальше берётся только отсюда.
    # Считать его заново после выдавливания нельзя: Extrude Mesh берёт
    # поле смещения с домена рёбер, и в точке, где сходятся ребро края и
    # ребро не-края, получает их среднее — ровно половину нужного. Полоса
    # тогда выходит вдвое уже плиты, а между ними остаётся щель.
    wgeo = store(_out(wwire, "Mesh"), OFF_ATTR, wofs_out, 960, -6800,
                 'FLOAT_VECTOR', 'POINT', "сдвиг точки")

    # Цель для замера расстояния до края — рёбра края УЖЕ СКРУГЛЁННОГО
    # контура. По несглаженному краю из исходного меша мерить нельзя:
    # точка в середине дуги отстоит от острого угла дальше ширины полосы,
    # проверку «на краю» проваливает и вылезает на полную высоту.
    wnotrim = boolean('NOT', wreb, None, 1140, -7300, "не ребро края")
    rimw = N('GeometryNodeDeleteGeometry', 1140, -6640, "только край",
             domain='EDGE', mode='ALL')
    link(wgeo, _in(rimw, "Geometry"))
    link(wnotrim, _in(rimw, "Selection"))

    # Замер расстояния до края идёт В ПЛАНЕ: и цель, и источник кладутся
    # на нулевую высоту. Иначе полоса, поднятая на высоту камня, оказалась
    # бы «в 0.15 от края» просто из-за разницы высот — а по этому
    # расстоянию считается и V текстуры, и уровень плиты.
    def _flatten(geo, x, y, label):
        fp = N('GeometryNodeInputPosition', x, y - 140)
        fs = N('ShaderNodeSeparateXYZ', x + 180, y - 140)
        link(fp.outputs[0], fs.inputs[0])
        fc = N('ShaderNodeCombineXYZ', x + 360, y - 140)
        link(fs.outputs['X'], fc.inputs['X'])
        link(fs.outputs['Y'], fc.inputs['Y'])
        sp = N('GeometryNodeSetPosition', x + 360, y, label)
        link(geo, _in(sp, "Geometry"))
        link(fc.outputs[0], _in(sp, "Position"))
        return _out(sp, "Geometry")

    def _flat_pos(x, y):
        fp = N('GeometryNodeInputPosition', x, y)
        fs = N('ShaderNodeSeparateXYZ', x + 180, y)
        link(fp.outputs[0], fs.inputs[0])
        fc = N('ShaderNodeCombineXYZ', x + 360, y)
        link(fs.outputs['X'], fc.inputs['X'])
        link(fs.outputs['Y'], fc.inputs['Y'])
        return fc.outputs[0]

    wnotd = boolean('NOT', wdeb, None, 1140, -7620, "не ребро спуска")
    rimd = N('GeometryNodeDeleteGeometry', 1140, -6320, "только спуск",
             domain='EDGE', mode='ALL')
    link(wgeo, _in(rimd, "Geometry"))
    link(wnotd, _in(rimd, "Selection"))

    # Если не помечено ни одного ребра, цель замера окажется ПУСТОЙ, а
    # Geometry Proximity на пустой цели возвращает ноль — и вся плита
    # села бы на землю вместо того, чтобы остаться наверху. Поэтому в
    # цель всегда добавляется отрезок, унесённый за тридевять земель: он
    # никогда не окажется ближайшим, но пустой цели не бывает.
    farl = N('GeometryNodeCurvePrimitiveLine', 1140, -6480, "далёкий отрезок")
    SI(farl, "Start", (1e6, 1e6, 0.0))
    SI(farl, "End", (1e6 + 1.0, 1e6, 0.0))
    farw = N('GeometryNodeCurveToMesh', 1320, -6480, "он же в рёбра")
    link(_out(farl, "Curve"), _in(farw, "Curve"))
    rimj = N('GeometryNodeJoinGeometry', 1500, -6640, "цель замера высоты")
    link(_out(rimd, "Geometry"), _in(rimj, "Geometry"))
    link(_out(farw, "Mesh"), _in(rimj, "Geometry"))
    downw_flat = _flatten(_out(rimj, "Geometry"), 1680, -6640,
                          "спуск в плане")
    rimw_flat = _flatten(_out(rimw, "Geometry"), 1680, -6320,
                         "край в плане")

    woff = attr(OFF_ATTR, 960, -6960, 'FLOAT_VECTOR', "сдвиг точки")

    # Проволочный контур края участка. Он нужен как ЦЕЛЬ ЗАМЕРА: признак
    # «точка на краю» не доживает до заливки — Fill Curve именованные
    # атрибуты точек не переносит, — поэтому край определяется расстоянием
    # до этой проволоки, а не меткой.


    # Уровень плитки в точке — тем же правилом, что и у самой заливки:
    # у ПОМЕЧЕННОГО края кромка EDGE_LIP, дальше полная высота. Нужен и
    # бордюру: его стенка к тротуару начинается от плитки, а не от земли.
    ppx = N('GeometryNodeProximity', -1200, -7600, "до края участка",
            target_element='EDGES')
    link(downw_flat, _in(ppx, "Target"))
    link(_flat_pos(-1380, -7760), _in(ppx, "Source Position"))
    pws = fmath('MAXIMUM', -1020, -7740, "ширина, не ноль")
    link(G("Ширина"), pws.inputs[0])
    pws.inputs[1].default_value = 1e-6
    pfr = fmath('DIVIDE', -1020, -7600, "доля ширины")
    link(_out(ppx, "Distance"), pfr.inputs[0])
    link(pws.outputs[0], pfr.inputs[1])
    pcap = fmath('MINIMUM', -840, -7600, "не больше единицы")
    link(pfr.outputs[0], pcap.inputs[0])
    pcap.inputs[1].default_value = 1.0
    pedge = fmath('MULTIPLY', -660, -7600, "высота у края")
    link(pcap.outputs[0], pedge.inputs[0])
    pedge.inputs[1].default_value = EDGE_LIP
    pfar = fmath('MULTIPLY', -840, -7740, "полторы ширины")
    link(G("Ширина"), pfar.inputs[0])
    pfar.inputs[1].default_value = 1.5
    pout = cmp(_out(ppx, "Distance"), pfar.outputs[0], 'GREATER_THAN',
               -660, -7740, 'FLOAT', "за полосой")
    plate_h = switchf(pout, pedge.outputs[0], G("Высота"), -480, -7600,
                      "уровень плитки")
    plate_on = plate_h

    curb, inner_grass = region(_out(gsep, "Selection"), "grass", 0,
                               floor=True)

    # -- заливки ---------------------------------------------------------
    # Трава — её контур, отступлённый внутрь на ширину камня: эту полосу
    # занял бордюр. Тротуар — свой контур как есть, без отступа: бордюра
    # на его краю нет, он доходит до контура травы вплотную, а на краю
    # участка просто кончается. Пятна травы входят в его контур
    # внутренними петлями и становятся дырами сами.
    # Трава режется ПО СОБСТВЕННЫМ РЁБРАМ исходной плоскости: внутренние
    # рёбра пятна (те, у которых две смежные грани) идут в заливку вторым
    # контуром и работают ограничениями, поэтому разрез ложится туда, где
    # он проведён в меше, а не диагоналями от случайной вершины. Плиту
    # тротуара этим не трогаем — там от таких ограничений пропадали куски.
    grass_mesh = _out(gsep, "Selection")

    # Трава режется ПО СОБСТВЕННЫМ РЁБРАМ пятна: они идут в заливку вторым
    # контуром и работают ограничениями, поэтому разрез ложится туда, где
    # он проведён в меше. Плиту тротуара этим не трогаем — там от таких
    # ограничений пропадали куски.
    #
    # Граничные точки пятна перед этим сдвигаются тем же отступом, что и
    # контур: иначе на вогнутом углу контур уходит в сторону, конец линии
    # реза за ним не идёт, и между ними остаётся незакрытый треугольник.
    gpos = N('GeometryNodeInputPosition', 240, -1500)
    gfc = on_domain(gpos.outputs[0], 'FACE', 420, -1500, 'FLOAT_VECTOR',
                    "центр грани")
    gin = vmath('SUBTRACT', 600, -1500, "внутрь пятна")
    link(_out(gfc, "Value"), gin.inputs[0])
    link(gpos.outputs[0], gin.inputs[1])
    ginf = vmath('MULTIPLY', 780, -1500, "в плане")
    link(gin.outputs[0], ginf.inputs[0])
    ginf.inputs[1].default_value = (1.0, 1.0, 0.0)
    gmesh = store(grass_mesh, "gcut_in", ginf.outputs[0], 960, -1500,
                  'FLOAT_VECTOR', 'POINT', "внутрь пятна")

    gev = N('GeometryNodeInputMeshEdgeVertices', 240, -1660)
    ged = vmath('SUBTRACT', 420, -1660, "направление ребра")
    link(_out(gev, "Position 2"), ged.inputs[0])
    link(_out(gev, "Position 1"), ged.inputs[1])
    gedf = vmath('MULTIPLY', 600, -1660, "в плане")
    link(ged.outputs[0], gedf.inputs[0])
    gedf.inputs[1].default_value = (1.0, 1.0, 0.0)
    gep = vmath('CROSS_PRODUCT', 780, -1660, "перпендикуляр ребра")
    link(gedf.outputs[0], gep.inputs[0])
    gep.inputs[1].default_value = (0.0, 0.0, 1.0)
    gepn = vmath('NORMALIZE', 960, -1660)
    link(gep.outputs[0], gepn.inputs[0])
    gina = attr("gcut_in", 780, -1820, 'FLOAT_VECTOR', "внутрь пятна")
    gdot = vmath('DOT_PRODUCT', 960, -1820)
    link(gepn.outputs[0], gdot.inputs[0])
    link(_out(gina, "Attribute"), gdot.inputs[1])
    gsg = fmath('SIGN', 1140, -1820, "знак стороны")
    link(_out(gdot, "Value"), gsg.inputs[0])
    gnin = vmath('SCALE', 1320, -1660, "перпендикуляр внутрь")
    link(gepn.outputs[0], gnin.inputs[0])
    link(gsg.outputs[0], _in(gnin, "Scale"))

    gen = N('GeometryNodeInputMeshEdgeNeighbors', 240, -1980)
    gbnd = cmp(_out(gen, "Face Count"), 1, 'LESS_EQUAL', 420, -1980, 'INT',
               "граничное ребро")
    gbf = switchf(gbnd, 0.0, 1.0, 600, -1980, "граница: 0 или 1")
    gnb = vmath('SCALE', 780, -1980, "перпендикуляр только у границы")
    link(gnin.outputs[0], gnb.inputs[0])
    link(gbf, _in(gnb, "Scale"))
    gQ0 = on_domain(gnb.outputs[0], 'EDGE', 960, -1980, 'FLOAT_VECTOR',
                    "сумма перпендикуляров")
    gC0 = on_domain(gbf, 'EDGE', 960, -2140, 'FLOAT', "доля граничных")
    gCc = fmath('MAXIMUM', 1140, -2140, "не ноль")
    link(_out(gC0, "Value"), gCc.inputs[0])
    gCc.inputs[1].default_value = 1e-4
    gCi = fmath('DIVIDE', 1320, -2140, "нормировка")
    gCi.inputs[0].default_value = 1.0
    link(gCc.outputs[0], gCi.inputs[1])
    gQ = vmath('SCALE', 1140, -1980, "Q")
    link(_out(gQ0, "Value"), gQ.inputs[0])
    link(gCi.outputs[0], _in(gQ, "Scale"))
    gQ2 = vmath('DOT_PRODUCT', 1320, -1980, "|Q| в квадрате")
    link(gQ.outputs[0], gQ2.inputs[0])
    link(gQ.outputs[0], gQ2.inputs[1])
    gQ2c = fmath('MAXIMUM', 1500, -2140, "не ноль")
    link(_out(gQ2, "Value"), gQ2c.inputs[0])
    gQ2c.inputs[1].default_value = MITER_EPS
    gsc = fmath('DIVIDE', 1680, -2140, "длина сдвига")
    link(G("Ширина"), gsc.inputs[0])
    link(gQ2c.outputs[0], gsc.inputs[1])
    gofs = vmath('SCALE', 1500, -1980, "сдвиг точки")
    link(gQ.outputs[0], gofs.inputs[0])
    link(gsc.outputs[0], _in(gofs, "Scale"))
    gmoved = N('GeometryNodeSetPosition', 1680, -1660, "пятно с отступом")
    link(gmesh, _in(gmoved, "Geometry"))
    link(gofs.outputs[0], _in(gmoved, "Offset"))

    # Отступ даёт правильный ус, но на вогнутом углу он вылезает остриём,
    # а контур заливки там скруглён и это остриё срезает. Поэтому после
    # отступа граничные точки прижимаются к самому контуру — садятся на
    # ближайшую его точку, хоть на прямой, хоть на дуге.
    gcw = N('GeometryNodeCurveToMesh', 1680, -2300, "контур в рёбра")
    link(inner_grass, _in(gcw, "Curve"))
    gpx = N('GeometryNodeProximity', 1860, -2300, "до контура заливки",
            target_element='EDGES')
    link(_out(gcw, "Mesh"), _in(gpx, "Target"))
    gbp = on_domain(gbf, 'EDGE', 1860, -2140, 'FLOAT', "граница у точки")
    gbpt = cmp(_out(gbp, "Value"), 0.01, 'GREATER_THAN', 2040, -2140,
               'FLOAT', "точка на границе пятна")
    # Точка садится на контур и утапливается ещё на пару миллиметров
    # внутрь. Без этого ломаная пятна КАСАЕТСЯ дуги, заливка серпа не
    # может решить, что внутри, и заливает всю область — вторая трава
    # поверх нашей. Утопленная ломаная строго вложена в дугу, и вопрос
    # снимается; два миллиметра не видно.
    gqn = vmath('NORMALIZE', 2040, -1820)
    link(gQ.outputs[0], gqn.inputs[0])
    gtuck = vmath('SCALE', 2220, -1820, "утопить внутрь")
    link(gqn.outputs[0], gtuck.inputs[0])
    SI(gtuck, "Scale", 0.002)
    gsnp = vmath('ADD', 2220, -1980, "на контур и внутрь")
    link(_out(gpx, "Position"), gsnp.inputs[0])
    link(gtuck.outputs[0], gsnp.inputs[1])
    gsnap = N('GeometryNodeSetPosition', 2040, -1660, "прижать к контуру")
    link(_out(gmoved, "Geometry"), _in(gsnap, "Geometry"))
    link(gbpt, _in(gsnap, "Selection"))
    link(gsnp.outputs[0], _in(gsnap, "Position"))

    # Сама трава — это ГРАНИ пятна, а не заливка: нарезка тогда ровно та,
    # что в меше, и терять нечего. Заливка тут вообще не участвует, а
    # значит и не может потерять область, как это было со всеми
    # предыдущими попытками отдать ей линии реза.
    gcore = _out(gsnap, "Geometry")

    # У скруглённого угла граничное ребро пятна идёт хордой, а контур —
    # дугой; между ними серп, и без него трава не доходит до бордюра. Он
    # закрывается СТАРЫМ способом, заливкой: кольцо между двумя замкнутыми
    # контурами — дугой снаружи и утопленной ломаной пятна внутри. Там,
    # где скруглений нет, кольцо вырождается в ничто и граней не даёт.
    gben = N('GeometryNodeInputMeshEdgeNeighbors', 2220, -2460)
    gbe = cmp(_out(gben, "Face Count"), 1, 'LESS_EQUAL', 2400, -2460, 'INT',
              "граничное ребро пятна")
    glin = N('GeometryNodeMeshToCurve', 2220, -2300, "ломаная пятна",
             mode='EDGES')
    link(gcore, _in(glin, "Mesh"))
    link(gbe, _in(glin, "Selection"))
    gring = N('GeometryNodeJoinGeometry', 1140, -1800, "дуга и ломаная")
    link(inner_grass, _in(gring, "Geometry"))
    link(_out(glin, "Curve"), _in(gring, "Geometry"))
    gfillr = N('GeometryNodeFillCurve', 1320, -1800, "серпы у скруглений")
    link(_out(gring, "Geometry"), _in(gfillr, "Curve"))

    gjoin = N('GeometryNodeJoinGeometry', 1500, -1800, "трава целиком")
    link(gcore, _in(gjoin, "Geometry"))
    link(_out(gfillr, "Mesh"), _in(gjoin, "Geometry"))
    gfill = _out(gjoin, "Geometry")

    # Полоса — выдавливанием рёбер контура. Заливкой её строить нельзя:
    # там, где отступ обрывается, у контура появляется длинная диагональ,
    # и область под ней не закрывает никто. При выдавливании переходный
    # четырёхугольник получается сам и закрывает ровно её.
    # Выдавливаются ТОЛЬКО рёбра, у которых ОБА конца на краю участка.
    # Если брать все рёбра и гасить сдвиг в точках не-края, на боковом
    # ребре появляется четырёхугольник во всю его длину: один конец на
    # краю, другой нет. Полигонов там быть не должно.
    wfn = on_domain(won, 'POINT', 1140, -2380, 'FLOAT',
                    "край по концам ребра")
    wboth = cmp(_out(wfn, "Value"), 0.99, 'GREATER_THAN', 1320, -2380,
                'FLOAT', "оба конца на краю")
    wext = N('GeometryNodeExtrudeMesh', 1320, -2240, "полоса у края",
             mode='EDGES')
    link(wgeo, _in(wext, "Mesh"))
    link(wboth, _in(wext, "Selection"))
    SI(wext, "Offset Scale", 0.0)
    SI(wext, "Individual", False)
    # Верхние точки двигаются тем же атрибутом, что и кромка плиты, —
    # значит стыкуются они точно.
    wtopmv = N('GeometryNodeSetPosition', 1500, -2240, "верх полосы")
    link(_out(wext, "Mesh"), _in(wtopmv, "Geometry"))
    link(_out(wext, "Top"), _in(wtopmv, "Selection"))
    link(_out(woff, "Attribute"), _in(wtopmv, "Offset"))

    # Контур плиты: тот же контур со сдвинутыми точками края. В углу, где
    # край встречается с боковым ребром, точка съезжает ВДОЛЬ бокового —
    # оно остаётся прямым, и щели рядом не открывается.
    wringp = N('GeometryNodeSetPosition', 1500, -2520, "передний край внутрь")
    link(wgeo, _in(wringp, "Geometry"))
    link(_out(woff, "Attribute"), _in(wringp, "Offset"))
    pcont = N('GeometryNodeMeshToCurve', 1680, -2520, "контур плиты",
              mode='EDGES')
    link(_out(wringp, "Geometry"), _in(pcont, "Mesh"))


    # У полосы остаются только грани; висячие рёбра исходного контура вон.
    ben3 = N('GeometryNodeInputMeshEdgeNeighbors', 1860, -2660)
    bloose = cmp(_out(ben3, "Face Count"), 0, 'EQUAL', 2040, -2660, 'INT',
                 "ребро без граней")
    wcut = N('GeometryNodeDeleteGeometry', 1500, -2380, "только полоса",
             domain='EDGE', mode='ALL')
    link(_out(wtopmv, "Geometry"), _in(wcut, "Geometry"))
    link(bloose, _in(wcut, "Selection"))
    wplate = N('GeometryNodeFillCurve', 1860, -2100, "плита тротуара")
    link(_out(pcont, "Curve"), _in(wplate, "Curve"))

    # Стенка бордюра по краю участка: она нужна там, где ребро НЕ
    # помечено острым. На помеченном полоса и так уходит на землю, и
    # закрывать нечего.
    wallsel = boolean('AND', wreb, wnotd, 1140, -2900, "край без спуска")
    wallx = N('GeometryNodeExtrudeMesh', 1320, -2900, "стенка по краю",
              mode='EDGES')
    link(wgeo, _in(wallx, "Mesh"))
    link(wallsel, _in(wallx, "Selection"))
    SI(wallx, "Offset Scale", 0.0)
    SI(wallx, "Individual", False)
    # Верх стенки идёт по уровню плитки, а не по константе: там, где рядом
    # спуск, плитка опускается, и стенка вместе с ней сходит на нет.
    wallz0 = attr("walk_%s" % Z_ATTR, 1320, -3040, 'FLOAT', "земля")
    wallhi = fmath('ADD', 1500, -3040, "верх стенки")
    link(_out(wallz0, "Attribute"), wallhi.inputs[0])
    link(plate_on, wallhi.inputs[1])
    wallz = switchf(_out(wallx, "Top"), wallhi.outputs[0],
                    _out(wallz0, "Attribute"), 1680, -3040,
                    "верх или низ стенки")
    wallp = N('GeometryNodeInputPosition', 1860, -3180)
    walls = N('ShaderNodeSeparateXYZ', 2040, -3180)
    link(wallp.outputs[0], walls.inputs[0])
    wallc = N('ShaderNodeCombineXYZ', 2220, -3180)
    link(walls.outputs['X'], wallc.inputs['X'])
    link(walls.outputs['Y'], wallc.inputs['Y'])
    link(wallz, wallc.inputs['Z'])
    wallsp = N('GeometryNodeSetPosition', 1860, -2900, "стенка по высоте")
    link(_out(wallx, "Mesh"), _in(wallsp, "Geometry"))
    link(wallc.outputs[0], _in(wallsp, "Position"))
    walln = N('GeometryNodeInputMeshEdgeNeighbors', 2040, -3040)
    wallloose = cmp(_out(walln, "Face Count"), 0, 'EQUAL', 2220, -3040,
                    'INT', "ребро без граней")
    wallcut = N('GeometryNodeDeleteGeometry', 2040, -2900, "только стенка",
                domain='EDGE', mode='ALL')
    link(_out(wallsp, "Geometry"), _in(wallcut, "Geometry"))
    link(wallloose, _in(wallcut, "Selection"))

    # Схлопнувшиеся грани — там, где плитка уже на земле, — вон.
    wallhf = on_domain(plate_on, 'POINT', 2220, -3180, 'FLOAT',
                       "уровень плитки по грани")
    wallnil = cmp(_out(wallhf, "Value"), 1e-4, 'LESS_THAN', 2400, -3180,
                  'FLOAT', "стенка схлопнулась")
    wallcut2 = N('GeometryNodeDeleteGeometry', 2220, -2900,
                 "без вырожденных", domain='FACE', mode='ALL')
    link(_out(wallcut, "Geometry"), _in(wallcut2, "Geometry"))
    link(wallnil, _in(wallcut2, "Selection"))
    wallcut = wallcut2

    # Трава ложится на верх камня, плитка — по своей прямой: полная
    # высота у травы, ноль у края участка.
    def set_level(geo, zval, x, y, label):
        zp = N('GeometryNodeInputPosition', x, y - 140)
        zs = N('ShaderNodeSeparateXYZ', x + 180, y - 140)
        link(zp.outputs[0], zs.inputs[0])
        zc = N('ShaderNodeCombineXYZ', x + 360, y - 140)
        link(zs.outputs['X'], zc.inputs['X'])
        link(zs.outputs['Y'], zc.inputs['Y'])
        link(zval, zc.inputs['Z'])
        sp = N('GeometryNodeSetPosition', x + 360, y, label)
        link(geo, _in(sp, "Geometry"))
        link(zc.outputs[0], _in(sp, "Position"))
        return _out(sp, "Geometry")

    gz = attr("grass_%s" % Z_ATTR, 1680, -1660, 'FLOAT', "земля под травой")
    gtop = fmath('ADD', 1860, -1660, "верх камня")
    link(_out(gz, "Attribute"), gtop.inputs[0])
    link(G("Высота"), gtop.inputs[1])
    glvl = set_level(gfill, gtop.outputs[0], 1680, -1800,
                     "трава на верх камня")
    wz = attr("walk_%s" % Z_ATTR, 1680, -2380, 'FLOAT', "земля под плиткой")

    # Точки тротуара, лежащие на краю участка, садятся на землю,
    # остальные остаются наверху. Никаких добавленных вершин: работают
    # рёбра самой заливки — одно её ребро внизу, другое наверху.
    # Расстояние до края берётся геометрически, до проволочного контура:
    # признак «точка на краю» до заливки не доживает, Fill Curve
    # именованные атрибуты точек не переносит.
    wup = plate_on

    wtop = fmath('ADD', 1860, -2380, "уровень точки тротуара")
    link(_out(wz, "Attribute"), wtop.inputs[0])
    link(wup, wtop.inputs[1])
    wlvl = set_level(_out(wplate, "Mesh"), wtop.outputs[0], 1680, -2100,
                     "плита по высоте")

    gmatn = N('GeometryNodeSetMaterial', 2220, -1800, "материал травы")
    link(glvl, _in(gmatn, "Geometry"))
    link(G("Материал травы"), _in(gmatn, "Material"))
    # Полоса ровняется по высоте, стенка — уже нет: у неё низ на земле, а
    # верх на уровне покрытия, и общий уровень её бы сплющил.
    wblvl = set_level(_out(wcut, "Geometry"), wtop.outputs[0], 1680,
                      -2520, "полоса по высоте")
    wbmat = N('GeometryNodeSetMaterial', 2040, -2520, "камень по краю")
    link(wblvl, _in(wbmat, "Geometry"))
    link(G("Материал бордюра"), _in(wbmat, "Material"))
    wbmat_lvl = _out(wbmat, "Geometry")
    wmatn = N('GeometryNodeSetMaterial', 2220, -2100, "материал тротуара")
    link(wlvl, _in(wmatn, "Geometry"))
    link(G("Материал тротуара"), _in(wmatn, "Material"))

    fjoin = N('GeometryNodeJoinGeometry', 2400, -1950, "плитка и трава")
    link(_out(gmatn, "Geometry"), _in(fjoin, "Geometry"))
    link(_out(wmatn, "Geometry"), _in(fjoin, "Geometry"))

    fpos = N('GeometryNodeInputPosition', 2040, -2700)
    fsep = N('ShaderNodeSeparateXYZ', 2220, -2700)
    link(fpos.outputs[0], fsep.inputs[0])
    fux = fmath('MULTIPLY', 2400, -2700)
    link(fsep.outputs['X'], fux.inputs[0])
    link(G("Тайлинг заливки"), fux.inputs[1])
    fuy = fmath('MULTIPLY', 2400, -2840)
    link(fsep.outputs['Y'], fuy.inputs[0])
    link(G("Тайлинг заливки"), fuy.inputs[1])
    fill = store(_out(fjoin, "Geometry"), UU_ATTR, fux.outputs[0],
                 2220, -1950, 'FLOAT', 'CORNER', "U заливки")
    fill = store(fill, VV_ATTR, fuy.outputs[0], 2400, -1950, 'FLOAT',
                 'CORNER', "V заливки")
    # Полоса по краю разворачивается как верх бордюра: U вдоль линии, V
    # поперёк, обе в единицах строки текстуры. Планарная развёртка сверху
    # ей не годится — камень должен повторяться вдоль, как и весь бордюр.
    bu = attr("walk_%s" % U_ATTR, 2220, -3100, 'FLOAT', "U вдоль линии")
    bs = attr("walk_%s" % S_ATTR, 2220, -3240, 'FLOAT', "длина линии")
    bpx = N('GeometryNodeProximity', 2220, -3400, "поперёк, до края",
            target_element='EDGES')
    link(rimw_flat, _in(bpx, "Target"))
    link(_flat_pos(1860, -3560), _in(bpx, "Source Position"))

    buav = on_domain(_out(bu, "Attribute"), 'FACE', 2400, -3100, 'FLOAT',
                     "среднее U по грани")
    budif = fmath('SUBTRACT', 2580, -3100, "ниже среднего")
    link(_out(buav, "Value"), budif.inputs[0])
    link(_out(bu, "Attribute"), budif.inputs[1])
    buq = fmath('MULTIPLY', 2400, -3240, "четверть длины")
    link(_out(bs, "Attribute"), buq.inputs[0])
    buq.inputs[1].default_value = 0.25
    buwr = cmp(budif.outputs[0], buq.outputs[0], 'GREATER_THAN', 2760,
               -3170, 'FLOAT', "угол за швом")
    buad = fmath('MULTIPLY', 2940, -3170, "прибавка длины")
    link(buwr, buad.inputs[0])
    link(_out(bs, "Attribute"), buad.inputs[1])
    buse = fmath('ADD', 3120, -3170, "U без шва")
    link(_out(bu, "Attribute"), buse.inputs[0])
    link(buad.outputs[0], buse.inputs[1])
    # Внешняя дуга длиннее внутренней, а U у обеих одна — грань выходит
    # перекошенной. Правится сдвигом вдоль касательной ровно на то,
    # насколько точка отъехала вбок от своей линии.
    bp0 = attr("walk_%s" % P_ATTR, 2220, -3680, 'FLOAT_VECTOR',
               "позиция линии")
    btn = attr("walk_%s" % T_ATTR, 2220, -3820, 'FLOAT_VECTOR',
               "касательная")
    bpos = N('GeometryNodeInputPosition', 2400, -3820)
    baway = vmath('SUBTRACT', 2580, -3820, "отъезд вбок")
    link(bpos.outputs[0], baway.inputs[0])
    link(_out(bp0, "Attribute"), baway.inputs[1])
    bawf = vmath('MULTIPLY', 2760, -3820, "в плане")
    link(baway.outputs[0], bawf.inputs[0])
    bawf.inputs[1].default_value = (1.0, 1.0, 0.0)
    btf = vmath('MULTIPLY', 2760, -3960, "касательная в плане")
    link(_out(btn, "Attribute"), btf.inputs[0])
    btf.inputs[1].default_value = (1.0, 1.0, 0.0)
    # Направление к середине грани, со знаком от касательной, — ровно то
    # же, что у верхней грани бордюра вокруг травы.
    bfp0 = on_domain(_out(bp0, "Attribute"), 'FACE', 2400, -3680,
                     'FLOAT_VECTOR', "линия по грани")
    bfdir = vmath('SUBTRACT', 2580, -3680, "к середине грани")
    link(_out(bfp0, "Value"), bfdir.inputs[0])
    link(_out(bp0, "Attribute"), bfdir.inputs[1])
    bfdf = vmath('MULTIPLY', 2760, -3680, "в плане")
    link(bfdir.outputs[0], bfdf.inputs[0])
    bfdf.inputs[1].default_value = (1.0, 1.0, 0.0)
    bfdn = vmath('NORMALIZE', 2940, -3680)
    link(bfdf.outputs[0], bfdn.inputs[0])
    bfdot = vmath('DOT_PRODUCT', 2940, -3820, "вперёд или назад")
    link(bfdf.outputs[0], bfdot.inputs[0])
    link(btf.outputs[0], bfdot.inputs[1])
    bfsg = fmath('SIGN', 3120, -3960, "знак")
    link(_out(bfdot, "Value"), bfsg.inputs[0])
    bfwd = vmath('SCALE', 3120, -3680, "вперёд")
    link(bfdn.outputs[0], bfwd.inputs[0])
    link(bfsg.outputs[0], _in(bfwd, "Scale"))
    bsh = vmath('DOT_PRODUCT', 3300, -3960, "поправка вдоль")
    link(bawf.outputs[0], bsh.inputs[0])
    link(bfwd.outputs[0], bsh.inputs[1])
    bumet = fmath('ADD', 3300, -3820, "U в метрах")
    link(buse.outputs[0], bumet.inputs[0])
    link(_out(bsh, "Value"), bumet.inputs[1])
    bufit = fmath('MULTIPLY', 3300, -3170, "U в единицах строки")
    link(bumet.outputs[0], bufit.inputs[0])
    link(kden.outputs[0], bufit.inputs[1])
    bus = fmath('MULTIPLY', 3480, -3170, "тайлинг")
    link(bufit.outputs[0], bus.inputs[0])
    link(G("Тайлинг вдоль"), bus.inputs[1])
    busn = fmath('MULTIPLY', 3660, -3170, "вдоль наоборот")
    link(bus.outputs[0], busn.inputs[0])
    busn.inputs[1].default_value = -1.0
    bufin = switchf(G("Верх X"), bus.outputs[0],
                    busn.outputs[0], 3840, -3170, "верх вдоль")

    bvm = fmath('MULTIPLY', 2400, -3400, "поперёк в единицах строки")
    link(_out(bpx, "Distance"), bvm.inputs[0])
    link(kden.outputs[0], bvm.inputs[1])
    bwk = fmath('MULTIPLY', 2400, -3540, "полная ширина")
    link(G("Ширина"), bwk.inputs[0])
    link(kden.outputs[0], bwk.inputs[1])
    bvmir = fmath('SUBTRACT', 2580, -3540, "поперёк наоборот")
    link(bwk.outputs[0], bvmir.inputs[0])
    link(bvm.outputs[0], bvmir.inputs[1])
    bvloc = switchf(G("Верх Y"), bvm.outputs[0],
                    bvmir.outputs[0], 2760, -3400, "верх поперёк")
    bvb = row_base("Строка верха", 2580, -3680)
    bvfin = fmath('ADD', 2940, -3400, "V верха")
    link(bvb.outputs[0], bvfin.inputs[0])
    link(bvloc, bvfin.inputs[1])

    band = store(wbmat_lvl, UU_ATTR, bufin, 3120, -2800, 'FLOAT', 'CORNER',
                 "U полосы")
    band = store(band, VV_ATTR, bvfin.outputs[0], 3300, -2800, 'FLOAT',
                 'CORNER', "V полосы")

    # Стенка по краю разворачивается как БОКОВАЯ грань бордюра: U вдоль
    # линии, V по высоте, строка — «Строка бока». В развёртку полосы её
    # класть нельзя: там V берётся из расстояния до края, а у обеих кромок
    # стенки оно нулевое — текстура схлопывалась в линию.
    wusn = fmath('MULTIPLY', 3480, -4200, "вдоль наоборот")
    link(bus.outputs[0], wusn.inputs[0])
    wusn.inputs[1].default_value = -1.0
    wufin = switchf(G("Бок X"), bus.outputs[0], wusn.outputs[0],
                    3660, -4200, "бок вдоль")

    wvz = attr("walk_%s" % Z_ATTR, 2940, -4340, 'FLOAT', "земля")
    wvp = N('GeometryNodeInputPosition', 2940, -4480)
    wvs = N('ShaderNodeSeparateXYZ', 3120, -4480)
    link(wvp.outputs[0], wvs.inputs[0])
    wvup = fmath('SUBTRACT', 3300, -4480, "высота над землёй")
    link(wvs.outputs['Z'], wvup.inputs[0])
    link(_out(wvz, "Attribute"), wvup.inputs[1])
    wvm = fmath('MULTIPLY', 3480, -4480, "в единицах строки")
    link(wvup.outputs[0], wvm.inputs[0])
    link(kden.outputs[0], wvm.inputs[1])
    wvh = fmath('MULTIPLY', 3300, -4620, "полная высота в строке")
    link(G("Высота"), wvh.inputs[0])
    link(kden.outputs[0], wvh.inputs[1])
    wvmir = fmath('SUBTRACT', 3480, -4620, "поперёк наоборот")
    link(wvh.outputs[0], wvmir.inputs[0])
    link(wvm.outputs[0], wvmir.inputs[1])
    wvloc = switchf(G("Бок Y"), wvm.outputs[0], wvmir.outputs[0],
                    3660, -4480, "бок поперёк")
    wvb = row_base("Строка бока", 3300, -4760)
    wvfin = fmath('ADD', 3840, -4480, "V стенки")
    link(wvb.outputs[0], wvfin.inputs[0])
    link(wvloc, wvfin.inputs[1])

    wall = store(_out(wallcut, "Geometry"), UU_ATTR, wufin, 3120, -4200,
                 'FLOAT', 'CORNER', "U стенки")
    wall = store(wall, VV_ATTR, wvfin.outputs[0], 3300, -4200, 'FLOAT',
                 'CORNER', "V стенки")
    wallm = N('GeometryNodeSetMaterial', 3480, -4200, "камень у стенки")
    link(wall, _in(wallm, "Geometry"))
    link(G("Материал бордюра"), _in(wallm, "Material"))
    wall = _out(wallm, "Geometry")
    fall = N('GeometryNodeJoinGeometry', 3480, -2400, "вся заливка")
    link(fill, _in(fall, "Geometry"))
    link(band, _in(fall, "Geometry"))
    link(wall, _in(fall, "Geometry"))
    fill = _out(fall, "Geometry")



    # -- сборка -----------------------------------------------------------
    cmat = N('GeometryNodeSetMaterial', 1680, 0, "материал бордюра")
    link(curb, _in(cmat, "Geometry"))
    link(G("Материал бордюра"), _in(cmat, "Material"))

    join = N('GeometryNodeJoinGeometry', 2760, 0, "всё вместе")
    link(_out(cmat, "Geometry"), _in(join, "Geometry"))
    link(fill, _in(join, "Geometry"))

    # Куски (плита, полоса, стенка, бордюр, трава) строятся порознь и
    # стыкуются по общим кромкам, но Join Geometry их не сваривает — по
    # каждому шву остаются двойные вершины. Сварка по расстоянию их
    # схлопывает и заодно превращает вырожденные четырёхугольники (те, у
    # которых стенка сошла на нет и два угла слиплись) в треугольники.
    # UV при этом не страдает: она лежит на углах, а не на вершинах.
    weld = N('GeometryNodeMergeByDistance', 2760, -160, "сварить швы")
    link(_out(join, "Geometry"), _in(weld, "Geometry"))
    SI(weld, "Distance", 1e-4)

    # Слой UVMap собирается один раз после склейки: если бы каждая часть
    # заводила свой, Join Geometry сводил бы слои и острова разъезжались.
    uua = attr(UU_ATTR, 2760, -300, 'FLOAT')
    vva = attr(UU_ATTR, 2760, -440, 'FLOAT')
    SI(vva, "Name", VV_ATTR)
    uvxy = N('ShaderNodeCombineXYZ', 2940, -370)
    link(_out(uua, "Attribute"), uvxy.inputs['X'])
    link(_out(vva, "Attribute"), uvxy.inputs['Y'])
    uvall = store(_out(weld, "Geometry"), UV_NAME, uvxy.outputs[0],
                  2940, 0, 'FLOAT2', 'CORNER', "UVMap")

    tri = N('GeometryNodeTriangulate', 3120, -200)
    link(uvall, _in(tri, "Mesh"))
    swt = N('GeometryNodeSwitch', 3120, 0, "триангуляция",
            input_type='GEOMETRY')
    link(G("Триангулировать"), _in(swt, "Switch"))
    link(uvall, _in(swt, "False"))
    link(_out(tri, "Mesh"), _in(swt, "True"))

    ssf = N('GeometryNodeSetShadeSmooth', 3300, 0, "гладкие грани",
            domain='FACE')
    link(_out(swt, "Output"), _in(ssf, "Geometry"))
    link(G("Гладкое затенение"), _in(ssf, "Shade Smooth"))
    eang = N('GeometryNodeInputMeshEdgeAngle', 3300, -200)
    esh = cmp(_out(eang, "Unsigned Angle"), G("Угол автосглаживания"),
              'GREATER_THAN', 3480, -200, 'FLOAT', "угол больше порога")
    sse = N('GeometryNodeSetShadeSmooth', 3480, 0, "острые рёбра",
            domain='EDGE')
    link(_out(ssf, "Geometry"), _in(sse, "Geometry"))
    link(esh, _in(sse, "Selection"))
    SI(sse, "Shade Smooth", False)
    go.location = (3660, 0)
    link(_out(sse, "Geometry"), go.inputs[0])

    frame = ng.nodes.new('NodeFrame')
    frame.label = "Как пользоваться"
    frame.shrink = False
    frame.location = (-3200, 1300)
    frame.width = 640
    frame.height = 900
    try:
        frame.label_size = 16
        frame.text = ensure_help()
    except (AttributeError, TypeError) as e:
        warn.append("справка в рамке: %s" % e)

    return ng, warn


_NO_RESET = {
    'NodeSocketGeometry', 'NodeSocketObject',
    'NodeSocketCollection', 'NodeSocketImage', 'NodeSocketTexture',
}


def reset_inputs(mod, ng):
    """Проставляет модификатору значения по умолчанию: при пересборке
    интерфейса сокеты получают новые идентификаторы, и старые значения к
    ним не подходят — поля оказываются пустыми или, что хуже, съезжают на
    соседние. Так у бордюра и тротуара однажды обменялись материалы."""
    for item in ng.interface.items_tree:
        if getattr(item, 'item_type', 'SOCKET') != 'SOCKET':
            continue
        if item.in_out != 'INPUT' or item.socket_type in _NO_RESET:
            continue
        try:
            mod[item.identifier] = item.default_value
        except (KeyError, TypeError, AttributeError, ValueError):
            pass
        # Материал — не число: у ID-сокета значение в модификаторе живёт
        # отдельным полем «_attribute_name»/указателем, и присвоение выше
        # для него могло не сработать. Дожимаем через RNA.
        if item.socket_type == 'NodeSocketMaterial':
            try:
                mod[item.identifier] = item.default_value
            except Exception:
                pass


def _wipe_modifier(obj, ng):
    """Снести старый модификатор с этой группой.

    Значения в модификаторе привязаны к идентификаторам сокетов. Стоит
    переименовать поле или переставить его в другую вкладку — часть
    идентификаторов меняется, и остатки старых значений садятся не на свои
    поля. Проще пересоздать модификатор, чем угадывать, что уцелело."""
    for m in list(obj.modifiers):
        if m.type == 'NODES' and m.node_group is ng:
            obj.modifiers.remove(m)


def attach(obj, ng):
    _wipe_modifier(obj, ng)
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
    print("[INU Curb] по умолчанию весь участок тротуар; трава — это "
          "грани с материалом травы")
    print("[INU Curb] бордюр только вокруг травы и внутри неё; спуск к "
          "дороге — по краевым рёбрам, помеченным острыми (Mark Sharp)")
    for ob in targets:
        me = ob.data
        print("[INU Curb] %s: вершин %d, рёбер %d, ГРАНЕЙ %d%s"
              % (ob.name, len(me.vertices), len(me.edges), len(me.polygons),
                 "" if len(me.polygons) else
                 "  <- граней нет, заливать нечего"))
    for p in problems:
        print("[INU Curb] не выставилось: %s" % p)
