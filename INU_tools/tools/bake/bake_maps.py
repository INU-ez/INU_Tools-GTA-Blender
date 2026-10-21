# INU_tools.tools.bake.bake_maps — Слой 2 подсистемы запекания.
#
# Реестр карт (BAKE_MAPS) — единственный источник правды о том, какие
# карты бывают и как каждая печётся. Добавить карту = одна запись (+
# опционально один builder). Также владеет светозависимостью карт
# (риги, M3) и построением Bevel-материала в Python (light-free).
#
# Зависит ТОЛЬКО от bake_core (нижний слой) и compat. Не знает про
# операторы/UI/scene-настройки — параметры приходят словарём `params`.
#
# ВАЖНО: НЕ добавлять `from __future__ import annotations`.

import math
from collections import OrderedDict
from dataclasses import dataclass
from contextlib import ExitStack

import bpy
import mathutils

from . import bake_core


# Namespaced datablock-имена (get-or-reuse без `.001`, чистятся sweep'ом).
BEVEL_MAT_NAME = 'INU_Bevel_Mat'
BAKE_LIGHTS_COLL = 'INU_Bake_Lights'
BAKE_WORLD_NAME = 'INU_Bake_World'

# Hi→Low пары определяются по ФИКСИРОВАННЫМ суффиксам (не настраиваются).
HI_SUFFIX = '_hi'
LOW_SUFFIX = '_low'

# Дефолтные параметры запекания (перекрываются из scene-настроек на M5).
DEFAULT_PARAMS = {
    'bevel_size': 0.05,
    'bevel_samples': 8,
    'light_energy_scale': 1.0,
}


# ── Map definition ───────────────────────────────────────────────────

@dataclass(frozen=True)
class BakeMapDef:
    """Описание одной карты. Pure-data, не bpy-тип."""
    id: str                    # 'AO' | 'DIFFUSE' | 'BEVEL' | ...
    label_key: str             # сырой ключ для T() (перевод — в UI/proxy)
    bake_type: str             # тип для bpy.ops.object.bake: 'AO'|'DIFFUSE'|'EMIT'
    needs_light: bool          # True → нужен внутренний риг + изоляция (M3)
    rig_kind: str              # 'NONE' | 'SUN' | 'PRELIGHT_8'
    node_group_builder: object # callable(obj, params)->teardown | None
    samples: int               # cycles.samples для прохода
    default_blend: str         # режим смешивания свежего слоя в стеке
    default_opacity: float
    default_contrast: float    # FUTURE (1.0 = identity)
    default_gamma: float       # FUTURE (1.0 = identity)
    pass_direct: bool = False  # для DIFFUSE-семейства
    pass_indirect: bool = False
    pass_color: bool = True


# ── Bevel material (Python, light-free) ──────────────────────────────

def build_bevel_material(params):
    """Собрать/переиспользовать материал-маску кромок (Bevel).

    Идея: нормаль с Bevel-ноды совпадает с геометрической на плоскости
    и расходится у рёбер → их dot-product ≈1 на плоскости, <1 на кромке.
    Маска кромок = clamp(1 − dot): рёбра светлые, плоскости тёмные.
    Выход — Emission, поэтому печётся как EMIT и не зависит от света.

    Инверсию делаем ShaderNodeMath(SUBTRACT), а НЕ MapRange: у MapRange
    дублированные сокеты From/To Min/Max (FLOAT + VECTOR режимы), и
    inputs['From Min'] неоднозначен — попадает не в тот сокет, выход
    схлопывается в константу (тот же баг, что compat.py описывает для
    ShaderNodeMix). У ShaderNodeMath сокеты простые float — без ловушки.

    Сокеты материала строятся напрямую (без node-группы), поэтому
    interface-API 4.0 здесь не нужен; compat.node_group_* зарезервирован
    для будущих grouped-карт.
    """
    mat = bpy.data.materials.get(BEVEL_MAT_NAME)
    if mat is None:
        mat = bpy.data.materials.new(BEVEL_MAT_NAME)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emit = nt.nodes.new('ShaderNodeEmission')
    bevel = nt.nodes.new('ShaderNodeBevel')
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    dot = nt.nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.use_clamp = True

    bevel.samples = int(params.get('bevel_samples', 8))
    rad = bevel.inputs.get('Radius')
    if rad is not None:
        rad.default_value = float(params.get('bevel_size', 0.05))

    # bevel.Normal · geo.Normal → скаляр (output 'Value')
    nt.links.new(bevel.outputs['Normal'], dot.inputs[0])
    nt.links.new(geo.outputs['Normal'], dot.inputs[1])

    # mask = clamp(1 − dot): ребро (dot<1) → светлое, плоскость → тёмное
    inv.inputs[0].default_value = 1.0
    nt.links.new(dot.outputs['Value'], inv.inputs[1])

    # Distances interpolate per face corner, so shared vertices do not
    # accidentally enable neighbouring edges. Selected edges also work on
    # split game meshes where Cycles cannot find a connected bevel surface.
    edge_attrs = params.get('bevel_edge_mask_attrs')
    mask_out = inv.outputs['Value']
    if edge_attrs:
        distance = None
        for name in edge_attrs:
            attr = nt.nodes.new('ShaderNodeAttribute')
            attr.attribute_name = name
            value = attr.outputs['Fac']
            if distance is not None:
                minimum = _math_node(nt, 'MINIMUM')
                nt.links.new(distance, minimum.inputs[0])
                nt.links.new(value, minimum.inputs[1])
                value = minimum.outputs['Value']
            distance = value
        scale = _math_node(nt, 'DIVIDE', b=max(float(params.get('bevel_size', 0.05)), 1e-8))
        nt.links.new(distance, scale.inputs[0])
        fade = _math_node(nt, 'SUBTRACT', a=1.0, clamp=True)
        nt.links.new(scale.outputs['Value'], fade.inputs[1])
        mask_out = fade.outputs['Value']

    nt.links.new(mask_out, emit.inputs['Color'])
    nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])

    mat.use_fake_user = False
    return mat


_BEVEL_EDGE_ATTR = 'INU_BevelEdgeMask'


def _edge_distance_buffers(me, positions, radius, selected_faces=False):
    """Per-corner distances to each selected edge line on the same face.

    Keep a separate field per edge: interpolating a minimum at vertices
    would fill a face when all its vertices belong to selected edges.
    positions are world-space coordinates; no Blender API is needed here.
    """
    selected = ({me.loops[i].edge_index for p in me.polygons if p.select for i in p.loop_indices}
                if selected_faces else {e.index for e in me.edges if e.select})
    face_edges = [[me.loops[i].edge_index for i in p.loop_indices
                   if me.loops[i].edge_index in selected] for p in me.polygons]
    buffers = [[max(radius, 1e-8)] * len(me.loops)
               for _ in range(max((len(es) for es in face_edges), default=0))]
    if not buffers:
        buffers = [[max(radius, 1e-8)] * len(me.loops)]
    for poly, edges in zip(me.polygons, face_edges):
        for slot, ei in enumerate(edges):
            va, vb = me.edges[ei].vertices
            a, b = positions[va], positions[vb]
            direction = [b[j] - a[j] for j in range(3)]
            length2 = sum(x * x for x in direction)
            if length2 <= 1e-20:
                continue
            for li in poly.loop_indices:
                point = positions[me.loops[li].vertex_index]
                delta = [point[j] - a[j] for j in range(3)]
                t = sum(delta[j] * direction[j] for j in range(3)) / length2
                buffers[slot][li] = math.sqrt(sum(
                    (delta[j] - t * direction[j]) ** 2 for j in range(3)))
    return buffers


def _make_edge_mask_attr(obj, radius, selected_faces=False):
    me = obj.data
    positions = [obj.matrix_world @ v.co for v in me.vertices]
    buffers = _edge_distance_buffers(me, positions, radius, selected_faces)
    names = []
    try:
        for i, values in enumerate(buffers):
            # Blender chooses a unique name if a user's attribute exists.
            attr = me.attributes.new(_BEVEL_EDGE_ATTR + str(i), 'FLOAT', 'CORNER')
            names.append(attr.name)
            attr.data.foreach_set('value', values)
    except Exception:
        _remove_edge_mask_attr(obj, names)
        raise
    return names


def _remove_edge_mask_attr(obj, names):
    ca = getattr(getattr(obj, 'data', None), 'attributes', None)
    if ca is None:
        return
    for name in names:
        a = ca.get(name)
        if a is not None:
            ca.remove(a)


def _prepare_bevel(obj, params):
    """Временно подменить материалы объекта на Bevel-материал. Возвращает
    teardown-замыкание, восстанавливающее исходные материалы."""
    _edge_attr = []
    if params.get('bevel_selected_edges') or params.get('bevel_selected_faces'):
        _edge_attr = _make_edge_mask_attr(obj, float(params.get('bevel_size', 0.05)),
                                        selected_faces=(params.get('bevel_selected_faces', False)
                                                        and not params.get('bevel_selected_edges')))
        if _edge_attr:
            params = dict(params)
            params['bevel_edge_mask_attrs'] = _edge_attr
    try:
        restore = _swap_materials(obj, build_bevel_material(params))
    except Exception:
        _remove_edge_mask_attr(obj, _edge_attr)
        raise

    def teardown():
        try:
            restore()
        finally:
            _remove_edge_mask_attr(obj, _edge_attr)
    return teardown


def _bake_selected_bevel_uv(context, obj, image, params, target_uv, margin):
    """Union UV masks instead of letting overlapping faces erase each other."""
    import numpy as np
    from .bake_edge_mask import rasterize_bevel_uv
    radius = float(params.get('bevel_size', 0.05))
    names = _make_edge_mask_attr(obj, radius,
        selected_faces=(params.get('bevel_selected_faces', False)
                        and not params.get('bevel_selected_edges')))
    evaluated = None
    try:
        obj.data.update()
        depsgraph = context.evaluated_depsgraph_get()
        depsgraph.update()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        mesh.calc_loop_triangles()
        uv_name = target_uv or (obj.data.uv_layers.active.name if obj.data.uv_layers.active else '')
        layer = mesh.uv_layers.get(uv_name)
        if layer is None:
            raise RuntimeError('Selected Bevel UV map is unavailable')
        uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        layer.data.foreach_get('uv', uv)
        fields = np.empty((len(names), len(mesh.loops)), dtype=np.float32)
        for i, name in enumerate(names):
            attribute = mesh.attributes.get(name)
            if attribute is None or attribute.domain != 'CORNER':
                raise RuntimeError('Evaluated mesh lost the selected-edge distance mask')
            attribute.data.foreach_get('value', fields[i])
        triangles = [tuple(t.loops) for t in mesh.loop_triangles]
        result = rasterize_bevel_uv(uv.reshape(-1, 2), triangles, fields, radius,
                                   int(image.size[0]), int(image.size[1]), margin)
        bake_core.write_numpy_to_image(image, result, pack=False)
    finally:
        if evaluated is not None:
            evaluated.to_mesh_clear()
        _remove_edge_mask_attr(obj, names)


# ── Процедурные EMIT-маски по геометрии (грязь/износ/кривизна/высота/
#    толщина/грандж). Все — light-free: подменяем материалы объекта на
#    построенный EMIT-материал и печём как EMIT (как Bevel). ──────────
DIRT_MAT_NAME = 'INU_Dirt_Mat'
EDGEWEAR_MAT_NAME = 'INU_EdgeWear_Mat'
CURVATURE_MAT_NAME = 'INU_Curvature_Mat'
HEIGHT_MAT_NAME = 'INU_Height_Mat'
THICKNESS_MAT_NAME = 'INU_Thickness_Mat'
GRUNGE_MAT_NAME = 'INU_Grunge_Mat'


def _swap_materials(obj, mat):
    """Подменить все материалы объекта на `mat`, вернуть teardown-замыкание
    (восстанавливает оригиналы и удаляет временный материал, если он остался
    без пользователей). Тот же приём, что у Bevel/Alpha."""
    slots = obj.material_slots
    if len(slots) > 0:
        original = [s.material for s in slots]
        for s in slots:
            s.material = mat

        def teardown():
            for s, m in zip(obj.material_slots, original):
                s.material = m
            if mat.users == 0:
                try:
                    bpy.data.materials.remove(mat)
                except Exception:
                    pass
        return teardown

    obj.data.materials.append(mat)

    def teardown_appended():
        try:
            obj.data.materials.pop()
        except Exception:
            pass
        if mat.users == 0:
            try:
                bpy.data.materials.remove(mat)
            except Exception:
                pass
    return teardown_appended


def _new_emit_mat(name):
    """Свежий EMIT-материал (переиспользуемый по имени): чистим ноды, ставим
    Emission→Output. Возвращает (mat, node_tree, emission_node)."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emit = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])
    mat.use_fake_user = False
    return mat, nt, emit


def _math_node(nt, op, a=None, b=None, clamp=False):
    """ShaderNodeMath с необязательными константами на входах (простые float
    сокеты — без ловушки дублированных сокетов Map Range)."""
    n = nt.nodes.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = clamp
    if a is not None:
        n.inputs[0].default_value = a
    if b is not None:
        n.inputs[1].default_value = b
    return n


def _cavity_node(nt, params, inside=False):
    """Local ray-based cavity detection also works across split vertices."""
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
    ao.inside = inside
    ao.only_local = True
    ao.samples = max(1, int(params.get('bevel_samples', 16)))
    ao.inputs['Distance'].default_value = float(params.get('cavity_distance', 0.05))
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    nt.links.new(geo.outputs['True Normal'], ao.inputs['Normal'])
    return ao


def build_dirt_material(params):
    """Darken locally occluded cavities; white is neutral for MULTIPLY."""
    mat, nt, emit = _new_emit_mat(DIRT_MAT_NAME)
    ao = _cavity_node(nt, params)
    k = float(params.get('cavity_gain', 4.0))
    conc = _math_node(nt, 'SUBTRACT', a=1.0)
    nt.links.new(ao.outputs['AO'], conc.inputs[1])
    mul = _math_node(nt, 'MULTIPLY', b=k)
    nt.links.new(conc.outputs['Value'], mul.inputs[0])
    inv = _math_node(nt, 'SUBTRACT', a=1.0, clamp=True)  # 1 − x
    nt.links.new(mul.outputs['Value'], inv.inputs[1])
    nt.links.new(inv.outputs['Value'], emit.inputs['Color'])
    return mat


def build_edgewear_material(params):
    """Inside AO detects convex edges; black is neutral for ADD."""
    mat, nt, emit = _new_emit_mat(EDGEWEAR_MAT_NAME)
    ao = _cavity_node(nt, params, inside=True)
    k = float(params.get('cavity_gain', 4.0))
    conv = _math_node(nt, 'SUBTRACT', a=1.0)
    nt.links.new(ao.outputs['AO'], conv.inputs[1])
    mul = _math_node(nt, 'MULTIPLY', b=k, clamp=True)
    nt.links.new(conv.outputs['Value'], mul.inputs[0])
    nt.links.new(mul.outputs['Value'], emit.inputs['Color'])
    return mat


def build_curvature_material(params):
    """Signed local cavity mask: concave dark, convex light, flat 0.5."""
    mat, nt, emit = _new_emit_mat(CURVATURE_MAT_NAME)
    outside = _cavity_node(nt, params)
    inside = _cavity_node(nt, params, inside=True)
    k = float(params.get('curvature_gain', 3.0))
    sub = _math_node(nt, 'SUBTRACT')
    nt.links.new(outside.outputs['AO'], sub.inputs[0])
    nt.links.new(inside.outputs['AO'], sub.inputs[1])
    mul = _math_node(nt, 'MULTIPLY', b=0.5 * k)
    nt.links.new(sub.outputs['Value'], mul.inputs[0])
    add = _math_node(nt, 'ADD', b=0.5, clamp=True)
    nt.links.new(mul.outputs['Value'], add.inputs[0])
    nt.links.new(add.outputs['Value'], emit.inputs['Color'])
    return mat


def build_height_material(params):
    """Высотный градиент: СНИЗУ светлое (маска грязи/влаги у земли).
    val = clamp(1 − (Zmir − Zmin)/(Zmax − Zmin)). Границы — мировой bbox."""
    mat, nt, emit = _new_emit_mat(HEIGHT_MAT_NAME)
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(geo.outputs['Position'], sep.inputs['Vector'])
    zmin = float(params.get('z_min', 0.0))
    zmax = float(params.get('z_max', 1.0))
    denom = max(zmax - zmin, 1e-6)
    sub = _math_node(nt, 'SUBTRACT', b=zmin)            # z − zmin
    nt.links.new(sep.outputs['Z'], sub.inputs[0])
    div = _math_node(nt, 'DIVIDE', b=denom)            # /(zmax−zmin) → 0..1
    nt.links.new(sub.outputs['Value'], div.inputs[0])
    inv = _math_node(nt, 'SUBTRACT', a=1.0, clamp=True)  # снизу 1, сверху 0
    nt.links.new(div.outputs['Value'], inv.inputs[1])
    nt.links.new(inv.outputs['Value'], emit.inputs['Color'])
    return mat


def build_thickness_material(params):
    """Толщина/просвет: inside-AO. Толстое тёмное, тонкое светлое (просвечивает)
    — стандартная thickness-маска. val = clamp(1 − AO_inside)."""
    mat, nt, emit = _new_emit_mat(THICKNESS_MAT_NAME)
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
    try:
        ao.inside = True
        ao.only_local = True
        ao.samples = max(1, int(params.get('bevel_samples', 16)))
    except Exception:
        pass
    dist = ao.inputs.get('Distance')
    if dist is not None:
        dist.default_value = float(params.get('thickness_dist', 0.2))
    inv = _math_node(nt, 'SUBTRACT', a=1.0, clamp=True)  # 1 − AO
    nt.links.new(ao.outputs['AO'], inv.inputs[1])
    nt.links.new(inv.outputs['Value'], emit.inputs['Color'])
    return mat


def _surface_pattern_output(nt, params):
    """3D object-space patterns; seed offsets do not move geometry or UVs."""
    kind = params.get('surface_pattern', 'NOISE')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    coords = tc.outputs['Object']
    seed = int(params.get('pattern_seed', 0))
    if seed:
        offset = nt.nodes.new('ShaderNodeVectorMath')
        offset.operation = 'ADD'
        offset.inputs[1].default_value = (seed * 0.754877, seed * 0.569841, seed * 0.438579)
        nt.links.new(coords, offset.inputs[0])
        coords = offset.outputs['Vector']
    if kind == 'VORONOI':
        node = nt.nodes.new('ShaderNodeTexVoronoi')
        node.voronoi_dimensions = '3D'
        node.feature = 'F1'
        output = node.outputs['Distance']
    elif kind == 'WAVE':
        node = nt.nodes.new('ShaderNodeTexWave')
        node.wave_type = 'BANDS'
        node.bands_direction = 'DIAGONAL'
        node.inputs['Distortion'].default_value = float(params.get('pattern_detail', 2.0))
        output = node.outputs['Fac']
    else:
        node = nt.nodes.new('ShaderNodeTexNoise')
        node.noise_dimensions = '3D'
        node.inputs['Detail'].default_value = float(params.get('pattern_detail', 2.0))
        output = node.outputs['Fac']
    node.inputs['Scale'].default_value = float(params.get('pattern_scale', 8.0))
    nt.links.new(coords, node.inputs['Vector'])
    sub = _math_node(nt, 'SUBTRACT', b=0.5)
    nt.links.new(output, sub.inputs[0])
    gain = _math_node(nt, 'MULTIPLY', b=float(params.get('pattern_contrast', 1.0)))
    nt.links.new(sub.outputs['Value'], gain.inputs[0])
    bias = _math_node(nt, 'ADD', b=0.5, clamp=True)
    nt.links.new(gain.outputs['Value'], bias.inputs[0])
    return bias.outputs['Value']


def _pattern_weight(nt, params):
    pattern = _surface_pattern_output(nt, params)
    strength = float(params.get('pattern_strength', 1.0))
    scale = _math_node(nt, 'MULTIPLY', b=strength)
    nt.links.new(pattern, scale.inputs[0])
    bias = _math_node(nt, 'ADD', b=1.0 - strength)
    nt.links.new(scale.outputs['Value'], bias.inputs[0])
    return bias.outputs['Value']


def _modulate_surface_output(nt, original, neutral, params):
    """Pattern only weakens the effect; unmarked geometry stays neutral."""
    sub = _math_node(nt, 'SUBTRACT', b=neutral)
    nt.links.new(original, sub.inputs[0])
    mul = _math_node(nt, 'MULTIPLY')
    nt.links.new(sub.outputs['Value'], mul.inputs[0])
    nt.links.new(_pattern_weight(nt, params), mul.inputs[1])
    add = _math_node(nt, 'ADD', b=neutral, clamp=True)
    nt.links.new(mul.outputs['Value'], add.inputs[0])
    return add.outputs['Value']


def build_grunge_material(params):
    """Bake coverage only; Grunge's procedural pattern lives in the compositor."""
    mat, nt, emit = _new_emit_mat(GRUNGE_MAT_NAME)
    emit.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    return mat


def _prepare_dirt(obj, params):
    return _swap_materials(obj, build_dirt_material(params))


def _prepare_edgewear(obj, params):
    return _swap_materials(obj, build_edgewear_material(params))


def _prepare_curvature(obj, params):
    return _swap_materials(obj, build_curvature_material(params))


def _prepare_thickness(obj, params):
    return _swap_materials(obj, build_thickness_material(params))


def _prepare_grunge(obj, params):
    return _swap_materials(obj, build_grunge_material(params))


def build_highlight_material(params):
    """Fixed world-space artificial specular lobe, independent of lights."""
    mat, nt, emit = _new_emit_mat('INU_Highlight_Mat')
    azimuth = math.radians(float(params.get('highlight_azimuth', -45.0)))
    elevation = math.radians(float(params.get('highlight_elevation', 45.0)))
    direction = (math.cos(elevation) * math.cos(azimuth),
                 math.cos(elevation) * math.sin(azimuth), math.sin(elevation))
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    dot = nt.nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    nt.links.new(geo.outputs['Normal'], dot.inputs[0])
    dot.inputs[1].default_value = direction
    positive = _math_node(nt, 'MAXIMUM', b=0.0)
    nt.links.new(dot.outputs['Value'], positive.inputs[0])
    power = _math_node(nt, 'POWER', b=float(params.get('highlight_sharpness', 16.0)), clamp=True)
    nt.links.new(positive.outputs['Value'], power.inputs[0])
    nt.links.new(power.outputs['Value'], emit.inputs['Color'])
    return mat


def _prepare_highlight(obj, params):
    return _swap_materials(obj, build_highlight_material(params))


def _prepare_height(obj, params):
    """Height: вычисляем мировой bbox по Z и кладём границы в params."""
    from mathutils import Vector
    p = dict(params)
    try:
        mw = obj.matrix_world
        zs = [(mw @ Vector(c)).z for c in obj.bound_box]
        p['z_min'], p['z_max'] = min(zs), max(zs)
    except Exception:
        p.setdefault('z_min', 0.0)
        p.setdefault('z_max', 1.0)
    return _swap_materials(obj, build_height_material(p))


# ── Alpha material (прозрачность материала → серая эмиссия) ──────────
# Cycles не умеет печь «альфу» нативным пассом, поэтому подменяем материалы
# на эмиссию альфа-канала (как Bevel подменяет на эмиссию маски кромок) и
# печём EMIT. Белый = непрозрачно, чёрный = дыра. Печём в Non-Color картинку
# (см. bake_ops), чтобы значение не искажалось sRGB-гаммой — тогда оно 1:1
# ложится в альфа-канал итоговой текстуры при «Сохранить как».
ALPHA_MAT_PREFIX = 'INU_Alpha_Mat_'


def _tex_uv_name(tex_node):
    """UV-map, к которой привязана Image Texture (или '')."""
    try:
        lnk = tex_node.inputs['Vector'].links
        if lnk and lnk[0].from_node.type == 'UVMAP':
            return lnk[0].from_node.uv_map
    except Exception:
        pass
    return ''


def _find_alpha_source(mat):
    """Откуда берётся прозрачность материала.

    Возвращает (image, uv_name, const): при image != None эмитим её альфа-
    канал; при image is None — сплошной серый `const` (0..1). Покрывает
    типовые случаи GTA/Blender: альфа в Principled.Alpha (константа или
    текстура) либо альфа основной Image Texture из Base Color.
    """
    if not mat or not getattr(mat, 'use_nodes', False) or mat.node_tree is None:
        return (None, '', 1.0)
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    # 1. Principled → Alpha (linked-текстура или константа).
    if bsdf is not None:
        ai = bsdf.inputs.get('Alpha')
        if ai is not None and ai.is_linked:
            src = ai.links[0].from_node
            if (src is not None and src.type == 'TEX_IMAGE'
                    and getattr(src, 'image', None)):
                return (src.image, _tex_uv_name(src), 1.0)
        elif ai is not None:
            return (None, '', float(ai.default_value))
    # 2. Основная Image Texture (из Base Color, иначе первая) → её альфа-канал.
    tex = None
    if bsdf is not None and bsdf.inputs['Base Color'].links:
        c = bsdf.inputs['Base Color'].links[0].from_node
        if c is not None and c.type == 'TEX_IMAGE' and getattr(c, 'image', None):
            tex = c
    if tex is None:
        tex = next((n for n in nodes
                    if n.type == 'TEX_IMAGE' and getattr(n, 'image', None)), None)
    if tex is not None:
        return (tex.image, _tex_uv_name(tex), 1.0)
    return (None, '', 1.0)


def _build_alpha_emit_material(name, src_mat):
    """Материал-эмиссия: серый = альфа исходного материала (белый =
    непрозрачно). Печётся как EMIT (свет не нужен). tex.Alpha — сырые данные
    (не цвет), поэтому colorspace исходной картинки не трогаем."""
    # Each Hi source/slot needs its own temporary shader until projection ends.
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_fake_user = False
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emit = nt.nodes.new('ShaderNodeEmission')
    img, uv, const = _find_alpha_source(src_mat)
    if img is not None:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        if uv:
            uvm = nt.nodes.new('ShaderNodeUVMap')
            uvm.uv_map = uv
            nt.links.new(uvm.outputs['UV'], tex.inputs['Vector'])
        nt.links.new(tex.outputs['Alpha'], emit.inputs['Color'])
    else:
        emit.inputs['Color'].default_value = (const, const, const, 1.0)
    nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])
    return m


def _prepare_alpha(obj, params):
    """Подменить материалы объекта на альфа-эмиссию (по слоту — своя, т.к.
    альфа зависит от материала). Возвращает teardown, восстанавливающий
    исходные материалы и удаляющий временные."""
    original = [s.material for s in obj.material_slots]
    temp, appended = [], False

    def teardown():
        if appended:
            obj.data.materials.pop()
        else:
            for slot, material in zip(obj.material_slots, original):
                slot.material = material
        for material in temp:
            try:
                if material.users == 0:
                    bpy.data.materials.remove(material)
            except Exception:
                pass
    try:
        for index, material in enumerate(original or [None]):
            temp.append(_build_alpha_emit_material(f'{ALPHA_MAT_PREFIX}{index}', material))
        if original:
            for slot, material in zip(obj.material_slots, temp):
                slot.material = material
        else:
            obj.data.materials.append(temp[0])
            appended = True
    except Exception:
        teardown()
        raise
    return teardown


# ── Self-contained light rig (Shadow / Diffuse-Lit) ──────────────────
# Свет генерирует сама подсистема — внешние источники сцены не нужны и НЕ
# должны влиять на результат. SUN-лампы (без inverse-square falloff →
# экспозиция инвариантна к размеру объекта, C5) в собственной коллекции
# INU_Bake_Lights (НЕ 'Prelight_Lights' — C3). На время прохода прячем
# (hide_render) все прочие объекты и ставим нейтральный мир (изоляция
# чужого света и эмиссии, C2); всё восстанавливаем в teardown.

# kind → список (euler_градусы_xyz, множитель_энергии).
# Энергии откалиброваны так, чтобы полностью освещённая поверхность давала
# ≈1.0 (учёт ламбертовского 1/π): иначе SHADOW как MULTIPLY-слой давит всю
# текстуру, а не только тени, а Diffuse-Lit выходит тёмным (C5). Точная
# подстройка — через gtatools_bake_light_energy_scale.
_RIG_SPECS = {
    'SUN':  [((50.0, 0.0, 40.0), 4.0)],                 # Shadow: один key-SUN (lit≈1)
    'DOME': [((0.0, 0.0, 0.0), 3.0),                    # Diffuse-Lit: верх + 4 бока
             ((60.0, 0.0, 0.0), 1.2),
             ((60.0, 0.0, 90.0), 1.2),
             ((60.0, 0.0, 180.0), 1.2),
             ((60.0, 0.0, 270.0), 1.2)],
}
# kind → (strength, color) нейтрального мира (ambient-fill, чтобы тени
# не были абсолютно чёрными).
_RIG_WORLD = {
    'SUN':  (0.05, (1.0, 1.0, 1.0)),
    'DOME': (0.15, (1.0, 1.0, 1.0)),
}


def _world_bbox(obj):
    """world-space центр + радиус (полудиагональ) bbox объекта."""
    mw = obj.matrix_world
    cs = [mw @ mathutils.Vector((c[0], c[1], c[2])) for c in obj.bound_box]
    xs = [c.x for c in cs]
    ys = [c.y for c in cs]
    zs = [c.z for c in cs]
    mn = mathutils.Vector((min(xs), min(ys), min(zs)))
    mx = mathutils.Vector((max(xs), max(ys), max(zs)))
    return (mn + mx) * 0.5, max((mx - mn).length * 0.5, 0.001)


def _make_bake_world(strength, color):
    w = bpy.data.worlds.get(BAKE_WORLD_NAME) or bpy.data.worlds.new(BAKE_WORLD_NAME)
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    if bg is not None:
        bg.inputs['Color'].default_value = (color[0], color[1], color[2], 1.0)
        bg.inputs['Strength'].default_value = strength
    return w


def _find_layer_collection(layer_coll, name):
    if layer_coll.collection.name == name:
        return layer_coll
    for ch in layer_coll.children:
        r = _find_layer_collection(ch, name)
        if r is not None:
            return r
    return None


def _build_light_rig(context, obj, kind, params, keep_visible=()):
    """Построить самодостаточный свет-риг под светозависимую карту и
    изолировать сцену от чужого света. keep_visible — объекты, которые НЕ
    прятать (для hi→low: хайполи-источник). Возвращает teardown (finally)."""
    scene = context.scene
    center, _radius = _world_bbox(obj)
    scale = float(params.get('light_energy_scale', 1.0))

    # 1. Снапшот + изоляция: прячем из рендера всё кроме целевого объекта
    #    (и keep_visible) — убирает чужие лампы И эмиссивные материалы (C2).
    keep = {obj}
    keep.update(keep_visible or ())
    hidden = []
    for o in scene.objects:
        hidden.append((o, o.hide_render))
        o.hide_render = (o not in keep)

    # 2. Снапшот + нейтральный мир.
    orig_world = scene.world
    strength, color = _RIG_WORLD.get(kind, (0.1, (1.0, 1.0, 1.0)))
    scene.world = _make_bake_world(strength, color)

    # 3. Собственная коллекция рига (очищаем от прошлых прогонов).
    coll = bpy.data.collections.get(BAKE_LIGHTS_COLL)
    if coll is None:
        coll = bpy.data.collections.new(BAKE_LIGHTS_COLL)
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    for o in list(coll.objects):
        ld = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if ld and getattr(ld, 'users', 1) == 0:
            bpy.data.lights.remove(ld)

    # 4. SUN-лампы (без falloff → инвариантны к размеру объекта).
    lamps = []
    for euler_deg, energy_f in _RIG_SPECS.get(kind, _RIG_SPECS['DOME']):
        ld = bpy.data.lights.new(name='INU_Bake_Sun', type='SUN')
        ld.energy = energy_f * scale
        lo = bpy.data.objects.new('INU_Bake_Sun', ld)
        lo.location = center
        lo.rotation_euler = (math.radians(euler_deg[0]),
                             math.radians(euler_deg[1]),
                             math.radians(euler_deg[2]))
        coll.objects.link(lo)
        lamps.append(lo)

    # 5. Коллекция рига не должна быть excluded из активного view layer (C10).
    lc = _find_layer_collection(context.view_layer.layer_collection, BAKE_LIGHTS_COLL)
    if lc is not None:
        lc.exclude = False
        lc.hide_viewport = False

    def teardown():
        for o, val in hidden:
            try:
                o.hide_render = val
            except Exception:
                pass
        try:
            scene.world = orig_world
        except Exception:
            pass
        for lo in lamps:
            ld = lo.data
            try:
                bpy.data.objects.remove(lo, do_unlink=True)
            except Exception:
                pass
            try:
                if ld and getattr(ld, 'users', 1) == 0:
                    bpy.data.lights.remove(ld)
            except Exception:
                pass
        c = bpy.data.collections.get(BAKE_LIGHTS_COLL)
        if c is not None:
            try:
                if scene.collection.children.get(BAKE_LIGHTS_COLL) is not None:
                    scene.collection.children.unlink(c)
            except Exception:
                pass
            try:
                if len(c.objects) == 0:
                    bpy.data.collections.remove(c)
            except Exception:
                pass
        w = bpy.data.worlds.get(BAKE_WORLD_NAME)
        if w is not None and w.users == 0:
            try:
                bpy.data.worlds.remove(w)
            except Exception:
                pass

    return teardown


# ── Per-map orchestration ────────────────────────────────────────────

def prepare_map(map_def, obj, context, params, keep_visible=()):
    """Подготовить окружение под карту. Возвращает teardown-замыкание
    (всегда вызывать в finally).

    - Bevel → подмена материалов (node_group_builder).
    - Светозависимые (Shadow / Diffuse-Lit):
        * params['use_scene_light'] → печём от РЕАЛЬНОГО света сцены (твои
          лампы/солнце/world, как LightMap): ни рига, ни изоляции → no-op;
        * иначе → самодостаточный внутренний свет-риг + изоляция сцены
          (keep_visible не прячется — для hi→low хайполи остаётся виден).
    - Остальные light-free (AO / Diffuse-albedo) → no-op.
    """
    if map_def.node_group_builder is not None:
        return map_def.node_group_builder(obj, params)
    if map_def.needs_light:
        if params.get('use_scene_light'):
            return lambda: None
        return _build_light_rig(context, obj, map_def.rig_kind, params,
                                keep_visible)
    return lambda: None


def _prepare_map_for_bake(map_def, obj, context, params, *, selected_to_active=False,
                          keep_visible=()):
    if map_def.id != 'ALPHA' or not selected_to_active:
        return prepare_map(map_def, obj, context, params, keep_visible=keep_visible)
    # In selected-to-active Cycles samples Hi shaders, not the target Low shader.
    candidates = keep_visible or context.selected_objects
    sources = [source for source in candidates if source is not obj and source.type == 'MESH']
    if not sources:
        raise RuntimeError('Alpha Hi to Low requires a source mesh')
    stack = ExitStack()
    try:
        for source in sources:
            stack.callback(prepare_map(map_def, source, context, params, keep_visible=keep_visible))
    except Exception:
        stack.close()
        raise
    return stack.close


def _try_alpha_pixel_projection(context, map_def, obj, image, *, selected_to_active,
                                 sources, target_uv, cage_extrusion, max_ray, margin):
    if not selected_to_active or map_def.id not in {'DIFFUSE', 'ALPHA'}:
        return False
    from .bake_projection import bake_alpha_projection
    return bake_alpha_projection(context, obj, image, sources=sources,
        map_id=map_def.id, target_uv=target_uv, cage_extrusion=cage_extrusion,
        max_ray=max_ray, margin=margin)


def bake_one_map(context, map_def, obj, image, *, margin=8, params=None,
                 samples=None, target_uv=None, selected_to_active=False,
                 cage_extrusion=0.0, max_ray=0.0, keep_visible=(),
                 pass_overrides=None):
    """Запечь одну карту `map_def` объекта `obj` в `image`.

    Предполагается, что вызывающий уже внутри bake_core.BakeStateGuard,
    объект активен+выделен и в OBJECT mode.

    samples=None → берём map_def.samples; иначе override (оператор даёт
    его шумным картам — AO / свет).

    pass_overrides=(direct, indirect, color) → переопределить пассы карты
    (для LightMap: режим Combined / только Indirect / только Direct). None →
    брать из map_def.

    target_uv (имя UV-карты) → печь в указанную UV. None → активная UV.
    Bevel по выбранным рёбрам/граням объединяет маски наложенных UV
    по максимуму, сохраняя исходные координаты.

    Мульти-материал: один вызов bpy.ops.object.bake печёт все слоты в
    одну картинку (у всех активная image-нода указывает на неё) —
    отдельный per-slot цикл не нужен.
    """
    if params is None:
        params = DEFAULT_PARAMS
    if _try_alpha_pixel_projection(context, map_def, obj, image,
            selected_to_active=selected_to_active, sources=keep_visible,
            target_uv=target_uv, cage_extrusion=cage_extrusion, max_ray=max_ray, margin=margin):
        return
    if map_def.id == 'NORMAL':
        from .bake_uv import uv_needs_unique_target
        image.colorspace_settings.name = 'Non-Color'
        uv_name = target_uv or (obj.data.uv_layers.active.name if obj.data.uv_layers.active else '')
        image['inu_normal_space'] = ('TANGENT' if uv_needs_unique_target(obj.data, uv_name) else 'OBJECT')
        if params.get('normal_bevel') and not selected_to_active:
            import bpy
            from .bake_normal import make_normal_bevel_source, normal_bevel_cage
            selected = list(context.selected_objects)
            active = context.view_layer.objects.active
            source = make_normal_bevel_source(context, obj, params)
            try:
                for other in context.view_layer.objects:
                    other.select_set(other in (obj, source))
                context.view_layer.objects.active = obj
                return bake_one_map(context, map_def, obj, image, margin=margin,
                    params=dict(params, normal_bevel=False), samples=samples, target_uv=target_uv,
                    selected_to_active=True,
                    cage_extrusion=normal_bevel_cage(obj, params),
                    keep_visible=(source,))
            finally:
                mesh = source.data
                bpy.data.objects.remove(source, do_unlink=True)
                bpy.data.meshes.remove(mesh)
                for other in context.view_layer.objects:
                    other.select_set(other in selected)
                context.view_layer.objects.active = active
    if (map_def.id == 'BEVEL' and not selected_to_active
            and (params.get('bevel_selected_edges') or params.get('bevel_selected_faces'))):
        _bake_selected_bevel_uv(context, obj, image, params, target_uv, margin)
        return
    teardown = _prepare_map_for_bake(map_def, obj, context, params,
        selected_to_active=selected_to_active, keep_visible=keep_visible)

    # UV→UV: если печём в ДРУГУЮ UV, исходные текстуры надо приколоть к
    # исходной (текущей активной) UV — иначе они засэмплятся по целевой и
    # выйдет каша. Источник = активная UV на момент старта (твоя trim).
    pin_token = None
    uv_token = None
    if target_uv:
        uvs = getattr(obj.data, 'uv_layers', None)
        # Источник = UV, по которой материал РЕНДЕРИТ текстуры (active_render),
        # с fallback на active. Её пиним, чтобы текстуры не «съехали» на
        # целевую UV при переключении.
        src_name = None
        if uvs:
            src_name = next((u.name for u in uvs if u.active_render), None)
            if src_name is None and uvs.active:
                src_name = uvs.active.name
        if src_name and src_name != target_uv:
            pin_token = bake_core.pin_image_nodes_to_uv(obj, src_name)
        uv_token = bake_core.set_active_uv(obj, target_uv)
    if pass_overrides is not None:
        p_direct, p_indirect, p_color = pass_overrides
    else:
        p_direct, p_indirect, p_color = (
            map_def.pass_direct, map_def.pass_indirect, map_def.pass_color)
    try:
        rec = bake_core.prepare_bake_targets(obj, image)
        try:
            bake_core.run_cycles_bake(
                map_def.bake_type,
                margin=margin,
                use_clear=True,
                pass_direct=p_direct,
                pass_indirect=p_indirect,
                pass_color=p_color,
                samples=(samples if samples is not None else map_def.samples),
                selected_to_active=selected_to_active,
                cage_extrusion=cage_extrusion,
                max_ray_distance=max_ray,
                normal_space=image.get('inu_normal_space', 'OBJECT'),
                sources=keep_visible,
            )
        finally:
            bake_core.restore_bake_targets(rec)
    finally:
        bake_core.restore_active_uv(uv_token)
        bake_core.unpin_image_nodes(pin_token)
        teardown()


# ── Registry ─────────────────────────────────────────────────────────
# Светозависимые карты (SHADOW, DIFFUSE_LIT) добавляются на M3 — реестр
# data-driven, появление записи автоматически прокидывает их в enum/UI.

BAKE_MAPS = OrderedDict([
    ('AO', BakeMapDef(
        id='AO', label_key='AO', bake_type='AO',
        needs_light=False, rig_kind='NONE', node_group_builder=None,
        samples=16, default_blend='MULTIPLY', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    ('DIFFUSE', BakeMapDef(
        id='DIFFUSE', label_key='Diffuse', bake_type='DIFFUSE',
        needs_light=False, rig_kind='NONE', node_group_builder=None,
        samples=1, default_blend='NORMAL', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0,
        pass_direct=False, pass_indirect=False, pass_color=True)),
    ('DIFFUSE_LIT', BakeMapDef(
        id='DIFFUSE_LIT', label_key='Diffuse Lit', bake_type='DIFFUSE',
        needs_light=True, rig_kind='DOME', node_group_builder=None,
        samples=8, default_blend='NORMAL', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0,
        pass_direct=True, pass_indirect=False, pass_color=True)),
    ('SHADOW', BakeMapDef(
        id='SHADOW', label_key='Shadow', bake_type='DIFFUSE',
        needs_light=True, rig_kind='SUN', node_group_builder=None,
        samples=32, default_blend='MULTIPLY', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0,
        pass_direct=True, pass_indirect=False, pass_color=False)),
    ('BEVEL', BakeMapDef(
        id='BEVEL', label_key='Bevel', bake_type='EMIT',
        needs_light=False, rig_kind='NONE',
        node_group_builder=_prepare_bevel,
        samples=4, default_blend='ADD', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    # Ray-based cavity maps need sampling/denoising; Height/Grunge are deterministic.
    ('DIRT', BakeMapDef(
        id='DIRT', label_key='Dirt (Cavity)', bake_type='EMIT',
        needs_light=False, rig_kind='NONE',
        node_group_builder=_prepare_dirt,
        samples=16, default_blend='MULTIPLY', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    ('EDGEWEAR', BakeMapDef(
        id='EDGEWEAR', label_key='Edge Wear', bake_type='EMIT',
        needs_light=False, rig_kind='NONE',
        node_group_builder=_prepare_edgewear,
        samples=16, default_blend='ADD', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    ('CURVATURE', BakeMapDef(
        id='CURVATURE', label_key='Curvature', bake_type='EMIT',
        needs_light=False, rig_kind='NONE',
        node_group_builder=_prepare_curvature,
        samples=16, default_blend='NORMAL', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    ('HEIGHT', BakeMapDef(
        id='HEIGHT', label_key='Height', bake_type='EMIT',
        needs_light=False, rig_kind='NONE',
        node_group_builder=_prepare_height,
        samples=1, default_blend='NORMAL', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    ('THICKNESS', BakeMapDef(
        id='THICKNESS', label_key='Thickness', bake_type='EMIT',
        needs_light=False, rig_kind='NONE',
        node_group_builder=_prepare_thickness,
        samples=16, default_blend='NORMAL', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    ('GRUNGE', BakeMapDef(
        id='GRUNGE', label_key='Grunge', bake_type='EMIT',
        needs_light=False, rig_kind='NONE',
        node_group_builder=_prepare_grunge,
        samples=1, default_blend='MULTIPLY', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    # «Рисование» — НЕ печётся: пустой (белый) слой под ручную роспись кистью
    # (Texture Paint). blend MULTIPLY → белый пустой не влияет, рисуешь тёмным
    # → грязь/затемнение. bake_ops пропускает его в цикле и лишь создаёт
    # картинку; редактируется кнопкой «Рисовать».
    ('PAINT', BakeMapDef(
        id='PAINT', label_key='Paint', bake_type='EMIT',
        needs_light=False, rig_kind='NONE', node_group_builder=None,
        samples=1, default_blend='MULTIPLY', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    # Альфа/прозрачность материала → серая маска (EMIT). В стеке НЕ
    # смешивается в RGB — задаёт альфа-канал итоговой текстуры (при
    # «Сохранить как» выходит RGBA). Так любую карту (тень, диффуз, …) можно
    # сделать прозрачным декалем: RGB = карта, A = ALPHA. blend/контраст к
    # ней не применяются; opacity работает как множитель силы альфы.
    ('ALPHA', BakeMapDef(
        id='ALPHA', label_key='Alpha', bake_type='EMIT',
        needs_light=False, rig_kind='NONE',
        node_group_builder=_prepare_alpha,
        samples=1, default_blend='NORMAL', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),

    # ── PBR-карты (нативные пассы Cycles) ─────────────────────────────
    # Полноценные карты стека, как AO/Diffuse/Bevel. Печёт сам материал
    # объекта (свой normal/roughness/emission); для переноса детали — hi→low.
    ('NORMAL', BakeMapDef(
        id='NORMAL', label_key='Normal Map', bake_type='NORMAL',
        needs_light=False, rig_kind='NONE', node_group_builder=None,
        samples=1, default_blend='MULTIPLY', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    # ROUGHNESS убрана из списка карт по запросу — для GTA-текстур она не
    # нужна. Старые слои/пресеты со map_id='ROUGHNESS' безопасно
    # игнорируются (get_map вернёт None, bake_ops такие слои пропускает).
    ('EMISSION', BakeMapDef(
        id='EMISSION', label_key='Emission', bake_type='EMIT',
        needs_light=False, rig_kind='NONE', node_group_builder=None,
        samples=1, default_blend='NORMAL', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0)),
    # Свет ОТ излучающих граней на соседние поверхности (GI). В отличие от
    # карты Emission (она снимает только само свечение грани), здесь
    # светящийся материал работает как лампа: запекаем НЕпрямой diffuse-свет
    # (pass_indirect, без albedo) — зелёная грань «подсвечивает» кирпич
    # вокруг. Складываем поверх (ADD). GI шумный → сэмплы из настроек.
    ('EMIT_GI', BakeMapDef(
        id='EMIT_GI', label_key='Emission Light (GI)', bake_type='DIFFUSE',
        needs_light=False, rig_kind='NONE', node_group_builder=None,
        samples=64, default_blend='ADD', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0,
        pass_direct=False, pass_indirect=True, pass_color=False)),

    # ── LightMap — полный GI от РЕАЛЬНОГО света сцены (аналог The_Lightmapper).
    # В отличие от Shadow / Diffuse-Lit (внутренний свет-риг + изоляция сцены),
    # LightMap НЕ строит риг и НЕ изолирует (needs_light=False) → печёт
    # настоящие лампы/солнце/world сцены. Прямой + непрямой diffuse-свет БЕЗ
    # альбедо (pass_color=False) = чистый множитель освещения поверх текстуры
    # (тени, отражённый свет, небо). Складываем MULTIPLY. GI очень шумный →
    # высокие сэмплы (128) + опциональный OIDN-денойз в операторе. Способ
    # применения (в диффуз / в prelight / отдельная LP_-текстура+UV2 / слой)
    # выбирается пользователем в gtatools_bake_lightmap_apply.
    ('LIGHTMAP', BakeMapDef(
        id='LIGHTMAP', label_key='LightMap', bake_type='DIFFUSE',
        needs_light=False, rig_kind='NONE', node_group_builder=None,
        samples=128, default_blend='MULTIPLY', default_opacity=1.0,
        default_contrast=1.0, default_gamma=1.0,
        pass_direct=True, pass_indirect=True, pass_color=False)),
    # Append new maps to preserve Blender's saved enum indices.
    ('HIGHLIGHT', BakeMapDef(
        id='HIGHLIGHT', label_key='Highlights', bake_type='EMIT',
        needs_light=False, rig_kind='NONE', node_group_builder=_prepare_highlight,
        samples=1, default_blend='ADD', default_opacity=0.35,
        default_contrast=1.0, default_gamma=1.0)),
])


def get_map(map_id):
    """BakeMapDef по id (или None)."""
    return BAKE_MAPS.get(map_id)


def bake_map_enum_items():
    """Список (id, raw_label, description) для EnumProperty. Перевод
    (T()) применяется на стороне UI/proxy — bake_maps не зависит от T."""
    return [(m.id, m.label_key, '') for m in BAKE_MAPS.values()]


def _find_dff_lod_pair(obj):
    """GTA DFF↔LOD pair for `obj`: the main DFF acts as high-detail, the LOD
    as low-detail. Resolved through the addon's model-type detection, so any
    naming convention (suffix `_LOD`, prefix `LOD…`, or the user's configured
    suffixes) matches `base_dff` ↔ `base_lod` / `LODbase`. Returns
    (dff_obj, lod_obj); either may be None when no partner exists."""
    try:
        from ..model_utils import get_model_type
    except Exception:
        return (None, None)
    mt, base = get_model_type(obj)
    if mt not in ('DFF', 'LOD') or not base:
        return (None, None)
    base_u = base.upper()
    want = 'LOD' if mt == 'DFF' else 'DFF'
    dff = obj if mt == 'DFF' else None
    lod = obj if mt == 'LOD' else None
    for o in bpy.data.objects:
        if o.type != 'MESH' or o is obj:
            continue
        omt, obase = get_model_type(o)
        if omt == want and (obase or '').upper() == base_u:
            if want == 'DFF':
                dff = o
            else:
                lod = o
            break
    return (dff, lod)


def find_hilow_pair(obj, hi_suffix, low_suffix, dff_lod_fallback=False):
    """По объекту `obj` (хай- или лоуполи) найти пару.

    Сначала по явным суффиксам 'wheel_hi' ↔ 'wheel_low'. Если их нет и
    включён `dff_lod_fallback` — пробуем GTA-пару DFF↔LOD (DFF = high,
    LOD = low), например `base_dff` ↔ `base_lod`. Фолбэк опционален: в
    режиме «Камера» low — это плоский billboard, а LOD-меш им не является,
    поэтому там его не используем (только в режиме Hi→Low). Принимает любой
    из пары. Возвращает (high_obj, low_obj); любой может быть None.
    """
    if obj is None:
        return (None, None)
    name = obj.name
    if low_suffix and name.endswith(low_suffix):
        base = name[:-len(low_suffix)]
        return (bpy.data.objects.get(base + hi_suffix), obj)
    if hi_suffix and name.endswith(hi_suffix):
        base = name[:-len(hi_suffix)]
        return (obj, bpy.data.objects.get(base + low_suffix))
    # Fallback: GTA DFF/LOD pair (DFF acts as hi, LOD as low). Only when a
    # real pair exists — a lone object returns nothing usable.
    if dff_lod_fallback:
        dff, lod = _find_dff_lod_pair(obj)
        if dff is not None and lod is not None:
            return (dff, lod)
    return (None, None)
