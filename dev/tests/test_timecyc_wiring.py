"""Врезки тайм-цикла — на подставном bpy.

Их две: в граф превью прилайта (материалы) и в композитор сцены
(экранные туман и PostFX).

Тут ловится ровно тот класс багов, который иначе виден только в
Blender: нода поставлена, но какой-то её сокет не подключён. Так у
группы тумана однажды остался висеть ВХОД — она отдавала свой дефолт
(чёрный) на всём, что ближе FogSt, и модели чернели.

Мок минимальный: узлы, сокеты с типами и связи — ровно столько, чтобы
tools/compat.py и tools/timecyc_prelight.py работали как в Blender.
"""

from pathlib import Path
import importlib.util
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]


# ── Мок bpy ─────────────────────────────────────────────────────────

class Socket:
    def __init__(self, name, sock_type='RGBA', node=None):
        self.name = name
        self.type = sock_type
        self.node = node
        self.links = []
        self.default_value = (0.0, 0.0, 0.0, 1.0) if sock_type == 'RGBA' else 0.0
        self.is_linked = False


class SocketList(list):
    def get(self, name, default=None):
        for s in self:
            if s.name == name:
                return s
        return default

    def __getitem__(self, key):
        if isinstance(key, str):
            found = self.get(key)
            if found is None:
                raise KeyError(key)
            return found
        return list.__getitem__(self, key)


# bl_idname → (inputs, outputs); сокет = (имя, тип)
_NODE_SPECS = {
    'ShaderNodeAttribute': ([], [('Color', 'RGBA'), ('Vector', 'VECTOR'),
                                 ('Fac', 'VALUE'), ('Alpha', 'VALUE')]),
    'ShaderNodeVertexColor': ([], [('Color', 'RGBA'), ('Alpha', 'VALUE')]),
    'ShaderNodeValue': ([], [('Value', 'VALUE')]),
    'ShaderNodeRGB': ([], [('Color', 'RGBA')]),
    'ShaderNodeMath': ([('Value', 'VALUE'), ('Value', 'VALUE')],
                       [('Value', 'VALUE')]),
    'ShaderNodeVectorMath': ([('Vector', 'VECTOR'), ('Vector', 'VECTOR')],
                             [('Vector', 'VECTOR')]),
    'ShaderNodeMix': ([('Factor', 'VALUE'), ('Factor', 'VECTOR'),
                       ('A', 'VALUE'), ('B', 'VALUE'),
                       ('A', 'VECTOR'), ('B', 'VECTOR'),
                       ('A', 'RGBA'), ('B', 'RGBA')],
                      [('Result', 'VALUE'), ('Result', 'VECTOR'),
                       ('Result', 'RGBA')]),
    'ShaderNodeMixRGB': ([('Fac', 'VALUE'), ('Color1', 'RGBA'),
                          ('Color2', 'RGBA')], [('Color', 'RGBA')]),
    'ShaderNodeMapRange': ([('Value', 'VALUE'), ('From Min', 'VALUE'),
                            ('From Max', 'VALUE'), ('To Min', 'VALUE'),
                            ('To Max', 'VALUE')], [('Result', 'VALUE')]),
    'ShaderNodeCameraData': ([], [('View Vector', 'VECTOR'),
                                  ('View Z Depth', 'VALUE'),
                                  ('View Distance', 'VALUE')]),
    'ShaderNodeBrightContrast': ([('Color', 'RGBA'), ('Bright', 'VALUE'),
                                  ('Contrast', 'VALUE')], [('Color', 'RGBA')]),
    'ShaderNodeGamma': ([('Color', 'RGBA'), ('Gamma', 'VALUE')],
                        [('Color', 'RGBA')]),
    'ShaderNodeHueSaturation': ([('Hue', 'VALUE'), ('Saturation', 'VALUE'),
                                 ('Value', 'VALUE'), ('Fac', 'VALUE'),
                                 ('Color', 'RGBA')], [('Color', 'RGBA')]),
    'ShaderNodeTexImage': ([], [('Color', 'RGBA'), ('Alpha', 'VALUE')]),
    'ShaderNodeBsdfPrincipled': ([('Base Color', 'RGBA'), ('Alpha', 'VALUE'),
                                  ('Emission Color', 'RGBA'),
                                  ('Emission Strength', 'VALUE')], []),
    # Композитор: ровно те ноды, из которых собрана экранная цепочка.
    # Depth появляется только при включённом пассе Z — см. ViewLayer.
    'CompositorNodeRLayers': ([], [('Image', 'RGBA'), ('Alpha', 'VALUE')]),
    # Три входа: в новых версиях у Math появляется лишний сокет, и
    # запись константы по индексу уезжает мимо.
    'CompositorNodeMath': ([('Value', 'VALUE'), ('Value', 'VALUE'),
                            ('Value', 'VALUE')], [('Value', 'VALUE')]),
    'CompositorNodeRGB': ([], [('RGBA', 'RGBA')]),
    'CompositorNodeMixRGB': ([('Fac', 'VALUE'), ('Image', 'RGBA'),
                              ('Image', 'RGBA')], [('Image', 'RGBA')]),
    # В 5.x у композиторной Gamma сокеты зовутся Color, а не Image —
    # ровно на этом падала сборка. Мок изображает новый вариант.
    'CompositorNodeGamma': ([('Color', 'RGBA'), ('Gamma', 'VALUE')],
                            [('Color', 'RGBA')]),
    'CompositorNodeComposite': ([('Image', 'RGBA'), ('Alpha', 'VALUE')], []),
    # Новая универсальная Mix (Blender 5.x): другие имена сокетов и по
    # три пары A/B на каждый тип данных.
    'CompositorNodeMix': ([('Factor', 'VALUE'), ('A', 'VALUE'), ('B', 'VALUE'),
                           ('A', 'VECTOR'), ('B', 'VECTOR'),
                           ('A', 'RGBA'), ('B', 'RGBA')],
                          [('Result', 'VALUE'), ('Result', 'VECTOR'),
                           ('Result', 'RGBA')]),
}

# Типы, наличие которых тест включает и выключает через bpy.types.
_GATED = ('CompositorNodeMixRGB', 'ShaderNodeMix', 'CompositorNodeComposite',
          'CompositorNodeMapRange')

# Ссылка на подставной bpy: sys.modules после изоляции его не хранит.
_BPY_STUB = None

_NODE_TYPE = {
    'ShaderNodeBsdfPrincipled': 'BSDF_PRINCIPLED',
    'ShaderNodeTexImage': 'TEX_IMAGE',
}


class Node:
    def __init__(self, bl_idname, tree):
        self.bl_idname = bl_idname
        self.type = _NODE_TYPE.get(bl_idname, bl_idname)
        self.name = bl_idname
        self.label = ''
        self.location = types.SimpleNamespace(x=0.0, y=0.0)
        self.node_tree = None
        self.data_type = 'RGBA'
        self.blend_type = 'MIX'
        self.operation = 'ADD'
        self.use_clamp = False
        self.clamp = False
        self.attribute_type = 'GEOMETRY'
        self.attribute_name = ''

        ins, outs = _NODE_SPECS.get(bl_idname, ([], []))
        self.inputs = SocketList(Socket(n, t, self) for n, t in ins)
        self.outputs = SocketList(Socket(n, t, self) for n, t in outs)

    def __setattr__(self, key, value):
        if key == 'location' and isinstance(value, tuple):
            value = types.SimpleNamespace(x=value[0], y=value[1])
        object.__setattr__(self, key, value)
        # Инстанс группы получает сокеты из её интерфейса — как в Blender.
        if key == 'node_tree' and isinstance(value, NodeTree):
            object.__setattr__(self, 'inputs', SocketList(
                Socket(i.name, 'RGBA', self) for i in value.iface_inputs))
            object.__setattr__(self, 'outputs', SocketList(
                Socket(o.name, 'RGBA', self) for o in value.iface_outputs))


class Nodes(list):
    def __init__(self, tree):
        list.__init__(self)
        self._tree = tree

    def new(self, bl_idname):
        # Типы из _GATED существуют только пока объявлены в bpy.types —
        # так тест изображает разные версии Blender (в 5.x, например,
        # нет CompositorNodeMapRange).
        if bl_idname in _GATED and not hasattr(_BPY_STUB.types, bl_idname):
            raise RuntimeError("Тип ноды %s не определён" % bl_idname)
        if bl_idname not in _NODE_SPECS and bl_idname not in (
                'NodeGroupInput', 'NodeGroupOutput', 'ShaderNodeGroup'):
            raise RuntimeError("Тип ноды %s не определён" % bl_idname)
        node = Node(bl_idname, self._tree)
        if bl_idname == 'CompositorNodeRLayers':
            scene = getattr(self._tree, 'scene', None)
            layers = getattr(scene, 'view_layers', ()) if scene else ()
            if any(getattr(vl, 'use_pass_z', False) for vl in layers):
                node.outputs.append(Socket('Depth', 'VALUE', node))
        if bl_idname == 'NodeGroupInput':
            node.outputs = SocketList(
                Socket(i.name, 'RGBA', node) for i in self._tree.iface_inputs)
        elif bl_idname == 'NodeGroupOutput':
            node.inputs = SocketList(
                Socket(o.name, 'RGBA', node) for o in self._tree.iface_outputs)
        self.append(node)
        return node

    def get(self, name, default=None):
        for n in self:
            if n.name == name:
                return n
        return default

    def remove(self, node):
        for sock in list(node.inputs) + list(node.outputs):
            for link in list(sock.links):
                self._tree.links.remove(link)
        if node in self:
            list.remove(self, node)

    def clear(self):
        for node in list(self):
            self.remove(node)


class Link:
    def __init__(self, from_socket, to_socket):
        self.from_socket = from_socket
        self.to_socket = to_socket
        self.from_node = from_socket.node
        self.to_node = to_socket.node


class Links(list):
    def new(self, from_socket, to_socket):
        for link in list(to_socket.links):
            self.remove(link)
        link = Link(from_socket, to_socket)
        self.append(link)
        from_socket.links.append(link)
        to_socket.links.append(link)
        from_socket.is_linked = True
        to_socket.is_linked = True
        return link

    def remove(self, link):
        if link in self:
            list.remove(self, link)
        for sock in (link.from_socket, link.to_socket):
            if link in sock.links:
                sock.links.remove(link)
            sock.is_linked = bool(sock.links)


class Interface:
    def __init__(self, tree):
        self._tree = tree

    @property
    def items_tree(self):
        return self._tree.iface_inputs + self._tree.iface_outputs

    def new_socket(self, name, in_out='OUTPUT', socket_type='NodeSocketColor'):
        item = types.SimpleNamespace(name=name, in_out=in_out,
                                     socket_type=socket_type)
        if in_out == 'INPUT':
            self._tree.iface_inputs.append(item)
        else:
            self._tree.iface_outputs.append(item)
        return item


class NodeTree:
    def __init__(self, name, bl_idname='ShaderNodeTree'):
        self.name = name
        self.bl_idname = bl_idname
        self.iface_inputs = []
        self.iface_outputs = []
        self.scene = None
        self.users = 0
        self.links = Links()
        self.nodes = Nodes(self)
        self.interface = Interface(self)
        self._props = {}

    def get(self, key, default=None):
        return self._props.get(key, default)

    def __setitem__(self, key, value):
        self._props[key] = value

    def __getitem__(self, key):
        return self._props[key]

    def __contains__(self, key):
        return key in self._props


class Collection(dict):
    def new(self, name, bl_idname=None):
        tree = NodeTree(name, bl_idname or 'ShaderNodeTree')
        self[name] = tree
        return tree

    def get(self, name, default=None):
        return dict.get(self, name, default)

    def remove(self, tree):
        self.pop(getattr(tree, 'name', None), None)


class Material:
    def __init__(self, name):
        self.name = name
        self.use_nodes = True
        self.node_tree = NodeTree(name)
        self._props = {}

    def get(self, key, default=None):
        return self._props.get(key, default)

    def __setitem__(self, key, value):
        self._props[key] = value

    def __getitem__(self, key):
        return self._props[key]

    def __contains__(self, key):
        return key in self._props

    def __delitem__(self, key):
        del self._props[key]


class ViewLayer:
    """Пасс Z управляет наличием сокета Depth у Render Layers — как в
    Blender. Именно на этом ломался экранный туман."""

    def __init__(self, scene):
        self._scene = scene
        self._use_pass_z = False

    @property
    def use_pass_z(self):
        return self._use_pass_z

    @use_pass_z.setter
    def use_pass_z(self, value):
        self._use_pass_z = bool(value)
        tree = self._scene.node_tree
        if tree is None:
            return
        for node in tree.nodes:
            if node.bl_idname != 'CompositorNodeRLayers':
                continue
            has = node.outputs.get('Depth') is not None
            if value and not has:
                node.outputs.append(Socket('Depth', 'VALUE', node))
            elif not value and has:
                node.outputs.remove(node.outputs.get('Depth'))


class Scene:
    """Минимальная сцена: custom-props, дерево композитора, view layer."""

    def __init__(self):
        self.use_nodes = False
        self.node_tree = None
        self.view_layers = [ViewLayer(self)]
        self._props = {}

    def get(self, key, default=None):
        return self._props.get(key, default)

    def __setitem__(self, key, value):
        self._props[key] = value

    def __getitem__(self, key):
        return self._props[key]

    def __contains__(self, key):
        return key in self._props

    def __delitem__(self, key):
        del self._props[key]

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)
        # Blender заводит дерево композитора при включении use_nodes.
        if key == 'use_nodes' and value and self.node_tree is None:
            tree = NodeTree("Compositing", 'CompositorNodeTree')
            tree.scene = self
            object.__setattr__(self, 'node_tree', tree)


class Scene5:
    """Сцена в стиле Blender 5.0: `node_tree` больше нет, композитор —
    отдельный датаблок `compositing_node_group`, `use_nodes` устарел."""

    def __init__(self, bpy_stub):
        self._bpy = bpy_stub
        self.compositing_node_group = None
        self.view_layers = [ViewLayer(self)]
        self._props = {}

    # у 5.x нет ни node_tree, ни рабочего use_nodes
    @property
    def node_tree(self):
        raise AttributeError("'Scene' object has no attribute 'node_tree'")

    def get(self, key, default=None):
        return self._props.get(key, default)

    def __setitem__(self, key, value):
        self._props[key] = value

    def __getitem__(self, key):
        return self._props[key]

    def __contains__(self, key):
        return key in self._props

    def __delitem__(self, key):
        del self._props[key]

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)
        if key == 'compositing_node_group' and value is not None:
            value.scene = self


def _install_bpy_stub():
    global _BPY_STUB
    """Подменить bpy и подгрузить наши модули ИЗОЛИРОВАННО.

    Соседние тесты в наборе ставят собственные заглушки bpy, и tools/
    compat.py запоминает версию Blender на импорте. Если модуль уже
    лежит в sys.modules с чужой версией, наш тест поедет на её ветке
    (например, на API нод-групп до 4.0). Поэтому: снимаем кэш, грузим
    своё, а затем возвращаем sys.modules как было — ссылки на уже
    загруженные модули у нас остаются.
    """
    bpy = types.ModuleType('bpy')
    bpy.app = types.SimpleNamespace(version=(4, 2, 0), translations=None)
    base = type('Base', (), {})
    bpy.types = types.SimpleNamespace(
        Operator=type('Operator', (base,), {}),
        Panel=type('Panel', (base,), {}),
        PropertyGroup=type('PropertyGroup', (base,), {}),
        Menu=type('Menu', (base,), {}),
        UIList=type('UIList', (base,), {}),
    )
    # Код проверяет наличие типов нод через hasattr(bpy.types, ...) —
    # для мока объявляем те, на которые он смотрит.
    for _name in ('CompositorNodeMixRGB', 'ShaderNodeMix',
                  'CompositorNodeComposite'):
        setattr(bpy.types, _name, type(_name, (base,), {}))
    bpy.props = types.SimpleNamespace(**{
        n: (lambda **kw: None) for n in (
            'StringProperty', 'BoolProperty', 'IntProperty', 'FloatProperty',
            'EnumProperty', 'FloatVectorProperty', 'CollectionProperty',
            'PointerProperty')})
    bpy.path = types.SimpleNamespace(abspath=lambda p: p)
    bpy.data = types.SimpleNamespace(node_groups=Collection(), materials=[],
                                     worlds=Collection(), objects={},
                                     lights={}, collections={})
    bpy.context = None
    sys.modules['bpy'] = bpy
    _BPY_STUB = bpy
    # ops-модуль пишет `from bpy.props import ...` — значит bpy должен
    # выглядеть пакетом с подмодулем.
    props_mod = types.ModuleType('bpy.props')
    for _n in ('StringProperty', 'BoolProperty', 'IntProperty',
               'FloatProperty', 'EnumProperty', 'FloatVectorProperty',
               'CollectionProperty', 'PointerProperty'):
        setattr(props_mod, _n, getattr(bpy.props, _n))
    sys.modules['bpy.props'] = props_mod

    pkg = types.ModuleType('INU_tools')
    pkg.__path__ = [str(ROOT / 'INU_tools')]
    pkg.T = lambda s: s
    sys.modules['INU_tools'] = pkg
    return bpy


def _load_isolated():
    def _is_ours(name):
        return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))

    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for key in saved:
        del sys.modules[key]
    try:
        bpy = _install_bpy_stub()
        import importlib
        prelight = importlib.import_module('INU_tools.tools.timecyc_prelight')
        screen = importlib.import_module('INU_tools.tools.timecyc_screen')
        compat_mod = importlib.import_module('INU_tools.tools.compat')
        ops_mod = importlib.import_module('INU_tools.ops.timecyc_ops')
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)
    return bpy, prelight, screen, compat_mod, ops_mod


BPY, tp, ts, compat, tops = _load_isolated()


# ── Подставной материал с собранным превью прилайта ──────────────────

def _make_material(name="building"):
    """Материал в том виде, в каком его оставляет setup_prelight_preview:
    Attribute → ViewBC → ViewGamma → ViewSat → Mix(×текстура) → Base Color."""
    mat = Material(name)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links

    principled = nodes.new('ShaderNodeBsdfPrincipled')
    principled.name = "Principled BSDF"
    tex = nodes.new('ShaderNodeTexImage')
    tex.name = "Texture"

    vc = nodes.new('ShaderNodeAttribute')
    vc.name = "Prelight_VertexColor"
    vc.attribute_name = "Day"

    bc = nodes.new('ShaderNodeBrightContrast')
    bc.name = "Prelight_ViewBC"
    gm = nodes.new('ShaderNodeGamma')
    gm.name = "Prelight_ViewGamma"
    sat = nodes.new('ShaderNodeHueSaturation')
    sat.name = "Prelight_ViewSat"

    mix = compat.make_mix_rgba(nodes, blend='MULTIPLY', name="Prelight_Mix")

    links.new(vc.outputs['Color'], bc.inputs['Color'])
    links.new(bc.outputs['Color'], gm.inputs['Color'])
    links.new(gm.outputs['Color'], sat.inputs['Color'])
    links.new(sat.outputs['Color'], mix.b)
    links.new(tex.outputs['Color'], mix.a)
    links.new(mix.result, principled.inputs['Base Color'])

    mat['prelight_preview_active'] = True
    return mat


def _principled(mat):
    return mat.node_tree.nodes.get("Principled BSDF")


def _src_node(socket):
    return socket.links[0].from_node if socket.links else None


@pytest.fixture(autouse=True)
def _clean_groups():
    BPY.data.node_groups.clear()
    yield
    BPY.data.node_groups.clear()


# ── Тесты ────────────────────────────────────────────────────────────

def test_no_dangling_inputs_inside_groups():
    """Цветовые входы внутри общих групп обязаны быть подключены.

    Числовые сокеты (Gamma, From Min, второй операнд Math) — это
    константы, их ставим мы сами. А вот висящий Color означает, что
    стадия отдаёт свой дефолт: ровно так туман однажды чернил модели.
    """
    tp.ensure_group()
    for gname in (tp.GROUP_NAME,):
        group = BPY.data.node_groups.get(gname)
        assert group is not None
        for node in group.nodes:
            if node.bl_idname in ('NodeGroupInput', 'NodeGroupOutput'):
                continue
            for sock in node.inputs:
                if sock.is_linked or sock.type != 'RGBA':
                    continue
                # Несвязанный цветовой вход допустим, если он намеренно
                # константа с осмысленным значением (белый фолбэк, когда
                # прилайта нет). А вот ЧЁРНАЯ константа — это ровно тот
                # баг, что чернил кадр и модели.
                if tuple(sock.default_value)[:3] == (0.0, 0.0, 0.0):
                    raise AssertionError(
                        "%s.%s (цвет) не подключён и чёрный"
                        % (node.name, sock.name))


def test_game_look_routes_to_emission():
    mat = _make_material()
    tp.wire_material(mat, daynight=False, game_look=True)

    p = _principled(mat)
    emit = p.inputs['Emission Color']
    assert emit.is_linked, "игровой вид должен светиться через Emission"
    assert _src_node(emit).name == "Prelight_Mix"
    assert not p.inputs['Base Color'].is_linked
    assert p.inputs['Emission Strength'].default_value == 1.0
    assert mat.get('inu_tc_game_look')


def test_game_look_is_reversible():
    mat = _make_material()
    tp.wire_material(mat, daynight=False, game_look=True)
    tp.wire_material(mat, daynight=False, game_look=False)

    p = _principled(mat)
    assert p.inputs['Base Color'].is_linked
    assert _src_node(p.inputs['Base Color']).name == "Prelight_Mix"
    assert not p.inputs['Emission Color'].is_linked
    assert not mat.get('inu_tc_game_look')


def test_daynight_group_feeds_the_correction_chain():
    mat = _make_material()
    tp.wire_material(mat, daynight=True, game_look=True)

    bc_in = mat.node_tree.nodes.get("Prelight_ViewBC").inputs['Color']
    assert _src_node(bc_in).name == tp.NODE_NAME

    # Выключили — источник снова одиночный Attribute, группа убрана.
    tp.wire_material(mat, daynight=False, game_look=True)
    assert _src_node(bc_in).name == "Prelight_VertexColor"
    assert mat.node_tree.nodes.get(tp.NODE_NAME) is None


def test_daynight_with_night_selected_keeps_both_colour_sources(monkeypatch):
    mat = _make_material()
    vc = mat.node_tree.nodes.get('Prelight_VertexColor')
    vc.attribute_name = 'Night'
    monkeypatch.setattr(tp, 'scan_color_attributes', lambda scene=None: ('Day', 'Night', {mat.name}))
    tp.wire_material(mat, daynight=True, game_look=True)
    group = mat.node_tree.nodes.get(tp.NODE_NAME)
    assert _src_node(group.inputs['Day']).attribute_name == 'Day'
    assert _src_node(group.inputs['Night']).attribute_name == 'Night'
    assert vc.attribute_name == 'Night', 'Keep the selected single-layer source'
    links = list(mat.node_tree.links)
    tp.wire_material(mat, daynight=True, game_look=True)
    assert list(mat.node_tree.links) == links
    tp.wire_material(mat, daynight=False, game_look=True)
    assert _src_node(mat.node_tree.nodes.get('Prelight_ViewBC').inputs['Color']) is vc


def test_wiring_is_idempotent():
    """Повтор не должен плодить ноды и связи: материал в GTA-сцене общий
    на сотни объектов, каждая правка — перекомпиляция шейдера."""
    mat = _make_material()
    for _ in range(3):
        tp.wire_material(mat, daynight=True, game_look=True)
    n_nodes = len(mat.node_tree.nodes)
    n_links = len(mat.node_tree.links)

    changed = tp.wire_material(mat, daynight=True, game_look=True)
    assert not changed
    assert len(mat.node_tree.nodes) == n_nodes
    assert len(mat.node_tree.links) == n_links


def test_set_values_reach_the_groups():
    tp.ensure_group()

    scene = Scene()
    assert tp.set_balance(scene, 0.25)
    assert tp.set_ambient(scene, (0.1, 0.2, 0.3))

    # Значения живут в СЦЕНЕ: правка ноды внутри общей группы метила бы
    # дерево грязным, и EEVEE пересобирал шейдеры всех материалов —
    # слайдер часа подвисал на карте.
    assert scene[tp.SCENE_BALANCE_PROP] == 0.25
    assert list(scene[tp.SCENE_AMBIENT_PROP]) == [0.1, 0.2, 0.3]

    dn = BPY.data.node_groups.get(tp.GROUP_NAME)
    assert dn.nodes.get("INU_DN_Balance").attribute_type == 'VIEW_LAYER'
    assert dn.nodes.get("INU_DN_Ambient").attribute_name == tp.SCENE_AMBIENT_PROP


def test_ambient_is_added_and_clamped():
    """Движок считает saturate(prelight + ambient) ДО умножения на
    текстуру: сложение, потом обрезка по 1.0, и только потом выход."""
    tp.ensure_group()
    group = BPY.data.node_groups.get(tp.GROUP_NAME)

    add = group.nodes.get("INU_DN_AmbAdd")
    assert add.blend_type == 'ADD'
    add_srcs = {s.links[0].from_node.name
                for s in add.inputs if s.is_linked}
    assert "INU_DN_Ambient" in add_srcs
    assert "INU_DN_Mix" in add_srcs

    clamp = group.nodes.get("INU_DN_AmbClamp")
    assert clamp is not None, "нет saturate после сложения с ambient"
    assert clamp.operation == 'MINIMUM'
    assert tuple(clamp.inputs[1].default_value) == (1.0, 1.0, 1.0)
    assert clamp.inputs[0].links[0].from_node.name == "INU_DN_AmbAdd"
    assert clamp.outputs[0].links[0].to_node.bl_idname == 'NodeGroupOutput'


# ── Экранные стадии: композитор ──────────────────────────────────────

def _src(socket):
    return socket.links[0].from_node.name if socket.links else None


def test_screen_chain_is_fully_connected():
    """Кадр → туман → PostFX → Composite, без единого висящего звена.

    Именно здесь ловится класс багов «нода стоит, а вход не подключён»:
    в материальной версии тумана такой обрыв красил всю ближнюю
    геометрию чёрным."""
    scene = Scene()
    ts.ensure_tree(scene)
    nodes = scene.node_tree.nodes

    sub = nodes.get("INU_TC_FogRange")
    assert _src(sub.inputs[0]) == "INU_TC_RenderLayers"
    div = nodes.get("INU_TC_FogDiv")
    assert _src(div.inputs[0]) == "INU_TC_FogRange"

    curve = nodes.get("INU_TC_FogCurve")
    assert _src(curve.inputs[0]) == "INU_TC_FogDiv"

    fog_mix = nodes.get("INU_TC_FogMix")
    assert _src(fog_mix.inputs['Fac']) == "INU_TC_FogFac"
    fog_srcs = {_src(sock) for sock in fog_mix.inputs if sock.links}
    assert {"INU_TC_RenderLayers", "INU_TC_FogColor"} <= fog_srcs

    enc = nodes.get("INU_TC_PostEnc")
    assert _src(enc.inputs['Color']) == "INU_TC_FogMix"
    assert abs(enc.inputs['Gamma'].default_value - 1.0 / 2.2) < 1e-6

    mul = nodes.get("INU_TC_PostMul")
    mul_srcs = {_src(sock) for sock in mul.inputs if sock.links}
    assert {"INU_TC_PostEnc", "INU_TC_PostGain"} <= mul_srcs

    dec = nodes.get("INU_TC_PostDec")
    assert _src(dec.inputs['Color']) == "INU_TC_PostMul"
    assert dec.inputs['Gamma'].default_value == 2.2

    comp = next(n for n in nodes
                if n.bl_idname in ('CompositorNodeComposite', 'NodeGroupOutput'))
    assert _src(comp.inputs['Image']) == "INU_TC_PostDec"


def test_screen_values_reach_the_nodes():
    scene = Scene()
    ts.ensure_tree(scene)
    ts.apply_values(scene, fog=((0.1, 0.2, 0.3), 120.0, 900.0, 2.5),
                    postfx_gain=(1.9, 1.76, 1.42))

    nodes = scene.node_tree.nodes
    assert _const_value(nodes.get("INU_TC_FogRange")) == 120.0
    assert _const_value(nodes.get("INU_TC_FogDiv")) == 780.0
    assert _const_value(nodes.get("INU_TC_FogCurve")) == 2.5
    assert tuple(nodes.get("INU_TC_FogColor").outputs[0].default_value)[:3]         == (0.1, 0.2, 0.3)
    assert tuple(nodes.get("INU_TC_PostGain").outputs[0].default_value)[:3]         == (1.9, 1.76, 1.42)


def test_screen_fog_off_pushes_range_past_the_horizon():
    """Выключенный туман не удаляет стадию, а уводит порог за горизонт —
    так цепочка остаётся собранной и ничего не красит."""
    scene = Scene()
    ts.ensure_tree(scene)
    ts.apply_values(scene, fog=None, postfx_gain=(1.0, 1.0, 1.0))
    assert _const_value(scene.node_tree.nodes.get("INU_TC_FogRange")) > 100000.0


def test_screen_reuses_existing_render_layers():
    """Если в сцене уже есть Render Layers — берём её, а не заводим
    второй источник кадра."""
    scene = Scene()
    scene.use_nodes = True
    existing = scene.node_tree.nodes.new('CompositorNodeRLayers')
    existing.name = "Мой рендер-слой"

    ts.ensure_tree(scene)
    rl_nodes = [n for n in scene.node_tree.nodes
                if n.bl_idname == 'CompositorNodeRLayers']
    assert len(rl_nodes) == 1
    assert rl_nodes[0].name == "Мой рендер-слой"


def test_teardown_restores_previous_composite_source():
    """Чужую цепочку не ломаем: что питало Composite до нас — вернётся."""
    scene = Scene()
    scene.use_nodes = True
    tree = scene.node_tree
    blur = tree.nodes.new('CompositorNodeGamma')
    blur.name = "Чужая нода"
    comp = tree.nodes.new('CompositorNodeComposite')
    comp.name = "Composite"
    tree.links.new(blur.outputs['Color'], comp.inputs['Image'])

    ts.ensure_tree(scene)
    assert _src(comp.inputs['Image']) == "INU_TC_PostDec"

    ts.teardown(scene)
    assert _src(comp.inputs['Image']) == "Чужая нода"
    assert all(n.name not in ("INU_TC_PostDec", "INU_TC_FogMix")
               for n in tree.nodes)


def test_ensure_tree_is_idempotent():
    scene = Scene()
    ts.ensure_tree(scene)
    n_nodes = len(scene.node_tree.nodes)
    n_links = len(scene.node_tree.links)
    ts.ensure_tree(scene)
    assert len(scene.node_tree.nodes) == n_nodes
    assert len(scene.node_tree.links) == n_links


def test_depth_pass_is_requested():
    """Туман считается по глубине — пасс должен быть включён."""
    scene = Scene()
    ts.ensure_tree(scene)
    assert scene.view_layers[0].use_pass_z is True


def test_screen_chain_on_new_mix_node():
    """Сборка не должна зависеть от того, жива ли старая MixRGB.

    В новых Blender композиторный микс — общая нода Mix: сокеты зовутся
    Factor/A/B/Result, а пар A/B там три. Ищем их по имени И по типу,
    иначе цепочка тумана просто не собиралась бы."""
    saved = BPY.types.CompositorNodeMixRGB
    del BPY.types.CompositorNodeMixRGB
    try:
        scene = Scene()
        ts.ensure_tree(scene)
        nodes = scene.node_tree.nodes

        fog_mix = nodes.get("INU_TC_FogMix")
        assert fog_mix.bl_idname == 'CompositorNodeMix'
        assert fog_mix.data_type == 'RGBA'
        assert _src(fog_mix.inputs['Factor']) == "INU_TC_FogFac"

        # Цветовые A/B заняты кадром и цветом тумана, а Float-пара — нет.
        colour_srcs = {_src(s) for s in fog_mix.inputs
                       if s.type == 'RGBA' and s.links}
        assert colour_srcs == {"INU_TC_RenderLayers", "INU_TC_FogColor"}

        comp = next(n for n in nodes
                    if n.bl_idname in ('CompositorNodeComposite',
                                       'NodeGroupOutput'))
        assert _src(comp.inputs['Image']) == "INU_TC_PostDec"
    finally:
        BPY.types.CompositorNodeMixRGB = saved


def test_fresh_screen_chain_is_neutral():
    """Свежесобранная цепочка не должна ничего менять в кадре.

    Регрессия: композиторная нода RGB рождается ЧЁРНОЙ, и пока значения
    не приехали, весь кадр умножался на ноль — вьюпорт становился
    чёрным."""
    scene = Scene()
    ts.ensure_tree(scene)
    nodes = scene.node_tree.nodes

    gain = nodes.get("INU_TC_PostGain")
    assert tuple(gain.outputs[0].default_value)[:3] == (1.0, 1.0, 1.0),         "множитель кадра по умолчанию гасит картинку"

    assert _const_value(nodes.get("INU_TC_FogRange")) > 100000.0,         "туман по умолчанию начинается в кадре"
    assert _const_value(nodes.get("INU_TC_FogCurve")) == 1.0


# ── Выбор погоды ─────────────────────────────────────────────────────

class _WeatherCollection(list):
    """CollectionProperty-заглушка: clear() + add()."""

    def add(self):
        item = types.SimpleNamespace(name="")
        self.append(item)
        return item


class _TimecycProps:
    def __init__(self):
        self.weathers = _WeatherCollection()
        self.weather_name = ""


def _fake_cyc(*names):
    return types.SimpleNamespace(
        weathers=[types.SimpleNamespace(name=n) for n in names])


def test_weather_list_syncs_and_keeps_valid_choice():
    props = _TimecycProps()
    cyc = _fake_cyc("EXTRASUNNY_LA", "RAINY_SF", "UNDERWATER")

    tops.sync_weather_list(props, cyc)
    assert [w.name for w in props.weathers] == [
        "EXTRASUNNY_LA", "RAINY_SF", "UNDERWATER"]
    assert props.weather_name == "EXTRASUNNY_LA"

    props.weather_name = "RAINY_SF"
    tops.sync_weather_list(props, cyc)
    assert props.weather_name == "RAINY_SF", "выбор сбросился на ровном месте"
    assert tops.weather_index(props, cyc) == 1


def test_weather_index_never_fails_on_bad_name():
    """Регрессия: пустое значение раньше валило применение с TypeError,
    а enum к тому же не давал записать в себя '0'."""
    props = _TimecycProps()
    cyc = _fake_cyc("EXTRASUNNY_LA", "RAINY_SF")

    props.weather_name = ""
    assert tops.weather_index(props, cyc) == 0
    props.weather_name = "НЕТ ТАКОЙ ПОГОДЫ"
    assert tops.weather_index(props, cyc) == 0
    assert tops.weather_index(props, None) == 0


def test_weather_list_drops_stale_names():
    """Загрузили другой файл — старый выбор не должен пережить смену."""
    props = _TimecycProps()
    tops.sync_weather_list(props, _fake_cyc("A", "B"))
    props.weather_name = "B"

    tops.sync_weather_list(props, _fake_cyc("X", "Y"))
    assert [w.name for w in props.weathers] == ["X", "Y"]
    assert props.weather_name == "X"


def _mix_socket(node, which):
    """Сокет микса через тот же compat, которым его собирает код."""
    if which == 'factor':
        return compat.mix_input_factor(node)
    if which == 'a':
        return compat.mix_input_a(node)
    return compat.mix_input_b(node)


def test_night_branch_is_not_gated_by_alpha():
    """Регрессия: «ворота» по альфе отсутствующего атрибута открывались,
    и в микс шёл чёрный. Ночной вес теперь множится на явный флаг."""
    tp.ensure_group(day_attr="Day", night_attr="Night")
    group = BPY.data.node_groups.get(tp.GROUP_NAME)
    fac = group.nodes.get("INU_DN_Fac")
    srcs = {s.links[0].from_node.name for s in fac.inputs if s.links}
    assert srcs == {"INU_DN_Balance", "INU_DN_NightPresent"}


def test_material_without_vertex_colours_shows_plain_texture():
    """У материала, которым не пользуется ни один меш с вершинными
    цветами, ветка прилайта даёт чёрный — в unlit отдаём текстуру."""
    mat = _make_material()
    tp.wire_material(mat, daynight=False, game_look=True, has_prelight=False)

    p = _principled(mat)
    emit = p.inputs['Emission Color']
    assert emit.is_linked
    assert _src_node(emit).name == "Texture",         "без прилайта в Emission должна идти текстура, а не чёрный микс"


def test_group_reads_colours_from_material_nodes():
    """Регрессия: Attribute ВНУТРИ группы не отдавал вершинные цвета —
    материал уходил в чёрный, а рабочая нода Prelight висела отключённой.
    Теперь цвет приходит в группу снаружи, из неё же."""
    mat = _make_material()
    tp.wire_material(mat, daynight=True, game_look=True,
                     day_attr="Day", night_attr="Night")

    nodes = mat.node_tree.nodes
    grp = nodes.get(tp.NODE_NAME)
    assert grp is not None
    assert _src(grp.inputs['Day']) == "Prelight_VertexColor",         "дневной цвет должен идти из ноды материала"
    assert _src(grp.inputs['Night']) == tp.NIGHT_NODE_NAME

    night = nodes.get(tp.NIGHT_NODE_NAME)
    assert night.attribute_name == "Night"

    # Внутри группы не должно быть читалок ГЕОМЕТРИИ: вершинные цвета
    # приходят снаружи. Attribute со scope VIEW_LAYER — это наши
    # значения из сцены, им там место.
    group = BPY.data.node_groups.get(tp.GROUP_NAME)
    geometry_readers = [n for n in group.nodes
                        if n.bl_idname == 'ShaderNodeVertexColor'
                        or (n.bl_idname == 'ShaderNodeAttribute'
                            and n.attribute_type == 'GEOMETRY')]
    assert not geometry_readers


def test_group_without_night_layer_drops_the_night_reader():
    mat = _make_material()
    tp.wire_material(mat, daynight=True, game_look=True,
                     day_attr="Day", night_attr="")

    nodes = mat.node_tree.nodes
    assert nodes.get(tp.NIGHT_NODE_NAME) is None
    group = BPY.data.node_groups.get(tp.GROUP_NAME)
    assert group.nodes.get("INU_DN_NightPresent").outputs[0].default_value == 0.0


def test_turning_daynight_off_restores_direct_link():
    """Выключили режим — нода Prelight снова питает цепочку напрямую,
    а наши ноды из материала уходят."""
    mat = _make_material()
    tp.wire_material(mat, daynight=True, game_look=True,
                     day_attr="Day", night_attr="Night")
    tp.wire_material(mat, daynight=False, game_look=True)

    nodes = mat.node_tree.nodes
    bc_in = nodes.get("Prelight_ViewBC").inputs['Color']
    assert _src(bc_in) == "Prelight_VertexColor"
    assert nodes.get(tp.NODE_NAME) is None
    assert nodes.get(tp.NIGHT_NODE_NAME) is None


def test_depth_pass_is_enabled_before_wiring():
    """Регрессия: сокет Depth есть у Render Layers только вместе с
    пассом Z. Пасс включался в КОНЦЕ сборки — на первом проходе связи
    тумана не создавались, а второй выходил раньше по версии, и туман
    молча не работал."""
    scene = Scene()
    ts.ensure_tree(scene)

    assert scene.view_layers[0].use_pass_z is True
    sub = scene.node_tree.nodes.get("INU_TC_FogRange")
    assert sub.inputs[0].is_linked, "глубина не подключена к туману"
    assert sub.inputs[0].links[0].from_socket.name == 'Depth'
    # Версия помечается только при успешной сборке.
    assert scene.get('inu_tc_comp_version') is not None


def test_version_not_marked_without_depth():
    """Не удалось подключить глубину — версию не метим, чтобы следующий
    вызов попробовал снова, а не вышел раньше."""
    scene = Scene()
    scene.use_nodes = True
    # Слой без пасса Z и без возможности его включить.
    scene.view_layers = [types.SimpleNamespace()]
    ts.ensure_tree(scene)
    assert scene.get('inu_tc_comp_version') is None


def test_blender5_compositing_node_group():
    """Регрессия: в Blender 5.0 `scene.node_tree` удалён, и сборка падала
    с AttributeError прямо в первой строке — туман не работал вовсе."""
    scene = Scene5(BPY)
    ts.ensure_tree(scene)

    tree = scene.compositing_node_group
    assert tree is not None, "группа композитора не создана"
    assert tree.bl_idname == 'CompositorNodeTree'

    sub = tree.nodes.get("INU_TC_FogRange")
    assert sub.inputs[0].is_linked
    assert sub.inputs[0].links[0].from_socket.name == 'Depth'
    assert scene.view_layers[0].use_pass_z is True
    assert scene.get('inu_tc_comp_version') is not None

    ts.apply_values(scene, fog=((0.1, 0.2, 0.3), 120.0, 900.0, 2.0),
                    postfx_gain=(1.5, 1.5, 1.5))
    assert _const_value(tree.nodes.get("INU_TC_FogRange")) == 120.0


def test_blender5_teardown_detaches_our_group():
    """Группу заводили мы — её же и отцепляем, чужую не трогаем."""
    scene = Scene5(BPY)
    ts.ensure_tree(scene)
    assert scene.compositing_node_group is not None

    ts.teardown(scene)
    assert scene.compositing_node_group is None
    assert scene.get('inu_tc_comp_version') is None


def test_socket_names_may_differ_between_versions():
    """Регрессия: имена сокетов гуляют между версиями — у композиторной
    Gamma это то Image, то Color. Жёсткое обращение по имени роняло
    сборку с KeyError посреди цепочки."""
    scene = Scene()
    ts.ensure_tree(scene)
    nodes = scene.node_tree.nodes

    enc, dec = nodes.get("INU_TC_PostEnc"), nodes.get("INU_TC_PostDec")
    assert enc.inputs['Color'].is_linked, "вход gamma-кодирования не найден"
    assert dec.inputs['Color'].is_linked

    comp = next(n for n in nodes
                if n.bl_idname in ('CompositorNodeComposite', 'NodeGroupOutput'))
    assert _src(comp.inputs['Image']) == "INU_TC_PostDec"


def test_fog_does_not_touch_the_sky():
    """Регрессия: у фона глубина «бесконечная», фактор тумана выходил
    единицей, и небо целиком заливалось цветом тумана — градиент
    зенит↔горизонт пропадал. В игре fog на небо не действует."""
    scene = Scene()
    ts.ensure_tree(scene)
    nodes = scene.node_tree.nodes

    gate = nodes.get("INU_TC_FogSkyGate")
    assert gate is not None, "нет отсечки неба по глубине"
    assert gate.operation == 'LESS_THAN'
    assert _src(gate.inputs[0]) == "INU_TC_RenderLayers"

    fac = nodes.get("INU_TC_FogFac")
    assert fac.operation == 'MULTIPLY'
    srcs = {_src(s) for s in fac.inputs if s.links}
    assert srcs == {"INU_TC_FogCurve", "INU_TC_FogSkyGate"}
    assert _src(nodes.get("INU_TC_FogMix").inputs['Fac']) == "INU_TC_FogFac"


def test_sky_threshold_follows_fog_distance():
    """Регрессия: порог «дальше этого — небо» стоял константой 1e6, а
    глубина фона зависит от clip end вьюпорта и вполне может быть
    меньше. Небо тогда заливалось туманом целиком, и градиент
    зенит↔горизонт схлопывался в один цвет."""
    scene = Scene()
    ts.ensure_tree(scene)

    ts.apply_values(scene, fog=((0.1, 0.2, 0.3), 100.0, 800.0, 2.0),
                    postfx_gain=(1.0, 1.0, 1.0))
    gate = scene.node_tree.nodes.get("INU_TC_FogSkyGate")
    # Без явного порога берётся запасной — чуть дальше конца тумана.
    assert _const_value(gate) == 1000.0

    # Явный порог перекрывает расчётный.
    ts.apply_values(scene, fog=((0.1, 0.2, 0.3), 100.0, 800.0, 2.0),
                    postfx_gain=(1.0, 1.0, 1.0), sky_threshold=4321.0)
    assert _const_value(gate) == 4321.0


def test_sky_threshold_sits_next_to_the_clip():
    """Порог неба должен стоять вплотную к клипу вьюпорта, а не к концу
    тумана: иначе дальняя геометрия за порогом теряет туман и торчит
    чёткой — как обрезанный край карты при отдалении камеры."""
    scene = Scene()
    ts.ensure_tree(scene)

    clip = 2000.0
    ts.apply_values(scene, fog=((0.1, 0.2, 0.3), 100.0, 800.0, 2.0),
                    postfx_gain=(1.0, 1.0, 1.0),
                    sky_threshold=clip * 0.98)

    gate = scene.node_tree.nodes.get("INU_TC_FogSkyGate")
    assert _const_value(gate) == clip * 0.98
    # Геометрия у самой границы клипа ещё получает туман.
    assert _const_value(gate) > 800.0


def _const_value(node):
    """Константа ноды — из первого СВОБОДНОГО числового входа.

    Именно так её пишет код: у композиторных Math в разных версиях
    разное число сокетов, и обращение по индексу уезжает мимо — туман
    тогда считается с дефолтами и заливает весь кадр.
    """
    for sock in node.inputs:
        if sock.type == 'VALUE' and not sock.is_linked:
            return sock.default_value
    return None


def test_constants_go_into_free_sockets():
    """Регрессия: константы писались по индексу inputs[1]. Если у Math
    сокетов больше двух (или первый занят связью), значение уходит не
    туда, и туман заливает кадр целиком."""
    scene = Scene()
    ts.ensure_tree(scene)
    ts.apply_values(scene, fog=((0.1, 0.2, 0.3), 150.0, 950.0, 3.0),
                    postfx_gain=(1.0, 1.0, 1.0), sky_threshold=5000.0)
    nodes = scene.node_tree.nodes

    # Первый вход занят связью — константа обязана лечь в следующий.
    sub = nodes.get("INU_TC_FogRange")
    assert sub.inputs[0].is_linked
    assert _const_value(sub) == 150.0
    assert _const_value(nodes.get("INU_TC_FogDiv")) == 800.0
    assert _const_value(nodes.get("INU_TC_FogCurve")) == 3.0
    assert _const_value(nodes.get("INU_TC_FogSkyGate")) == 5000.0


def test_threshold_ignores_huge_user_clip():
    """Регрессия: порог брался от clip end ВЬЮПОРТА. Стоит там 80 000 —
    и порог уезжает за любую геометрию, небо считается поверхностью и
    заливается туманом целиком. Порог обязан считаться от габаритов
    сцены и дальности тумана."""
    scene = Scene()
    ts.ensure_tree(scene)

    # Наш расчёт клипа — около двух километров, а не восемьдесят.
    ts.apply_values(scene, fog=((0.1, 0.2, 0.3), 10.0, 800.0, 2.0),
                    postfx_gain=(1.0, 1.0, 1.0), sky_threshold=1920.0 * 0.98)

    gate = scene.node_tree.nodes.get("INU_TC_FogSkyGate")
    value = _const_value(gate)
    assert value < 5000.0, "порог ушёл за пределы сцены — небо зальётся"
    assert value > 800.0, "порог ближе тумана — дальняя геометрия его потеряет"
