# INU_tools.tools.bake.bake_nodes — живой нодовый композит.
#
# Собирает материал-стек Mix-нод из per-map картинок (<base>_<map_id>):
# каждый слой = одна Mix-нода, blend_type = режим слоя, Fac = прозрачность.
# Результат показывается на модели в реальном времени (Material Preview) —
# blend/opacity крутятся без перезапекания. Финальное «сведение» в одну
# текстуру делает numpy-композит (bake_composite) отдельной кнопкой.

import bpy

from .. import compat
from .bake_composite import BLEND_NODE_TYPE, SURFACE_MAP_IDS, bevel_basis_key


COMPOSITE_MAT = 'INU_BakeComposite'


def uses_live_surface_patterns(specs):
    return any(L.get('enabled') and L['map_id'] == 'NORMAL'
               and (L.get('normal_lighting', True) or L.get('desaturate')) for L in specs) or any(
               L.get('enabled') and L['map_id'] in SURFACE_MAP_IDS
               and L['map_id'] != 'ALPHA'
               and (L['map_id'] == 'GRUNGE' or L.get('surface_pattern', 'NONE') != 'NONE'
                    or L.get('effect_basis', 'SELF') != 'SELF' or L.get('basis_invert')
                    or L.get('masks') or L.get('ramp_low', 0.) != 0.
                    or L.get('ramp_high', 1.) != 1. or L.get('ramp_smooth'))
               for L in specs)


def build_composite_material(specs, base_name, uv_name, vcol_name=None, *,
                             material_name=COMPOSITE_MAT, opaque_for_bake=False,
                             base_image=None, base_uv='', alpha_only_for_bake=False):
    """Собрать/пересобрать материал INU_BakeComposite по списку слоёв.

    specs: list[dict(map_id, blend_mode, opacity, enabled)] СНИЗУ ВВЕРХ
           (index 0 = база). Картинки берутся как <base_name>_<map_id>.
    `vcol_name` — если задан, итоговый композит умножается на вертекс-цвет
    прилайта (texture × prelight), чтобы прилайт не пропадал визуально после
    запекания. Возвращает материал. Если материал уже на объекте —
    пересборка его нод обновляет живое превью мгновенно.
    """
    mat = (bpy.data.materials.get(material_name)
           or bpy.data.materials.new(material_name))
    mat.use_nodes = True
    mat.use_fake_user = False
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (500, 0)
    emit = nt.nodes.new('ShaderNodeEmission')
    emit.location = (300, 0)
    nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])

    def _has_img(name):
        return bpy.data.images.get(f"{base_name}_{name}") is not None

    # Ключ картинки слоя = uid | map_id (совпадает с bake_ops._lkey): каждый
    # слой печётся в свою <base>_<key>, поэтому картинку в нодах ищем по ключу,
    # а не по map_id — иначе слои с uid (напр. AO/Bevel) «не показываются».
    def _key(L):
        return L.get('uid') or L['map_id']

    def _key_for_mapid(mid):
        """Ключ картинки для карты mid (первый слой этой карты со своей
        запечённой картинкой); fallback — сам mid (старое имя <base>_<mid>)."""
        for L in specs:
            if L['map_id'] == mid and _has_img(_key(L)):
                return _key(L)
        return mid

    # Провайдер альфы (ALPHA-карта или as_decal-слой, напр. Shadow) в RGB-стек
    # не идёт — задаёт прозрачность превью (Mix с Transparent BSDF по маске).
    def _is_provider(L):
        return L['map_id'] == 'ALPHA' or L.get('as_decal')
    alpha_spec = next((L for L in specs
                       if L.get('enabled') and _is_provider(L)), None)
    mask_keys = {L.get('paint_mask_uid') for L in specs if L.get('paint_mask_uid')}
    enabled = [L for L in specs
               if L.get('enabled') and not _is_provider(L)
               and _key(L) not in mask_keys
               and _has_img(_key(L))]
    # Список идёт СВЕРХУ ВНИЗ (как в фотошопе): верхний слой накладывается
    # последним. База = НИЖНИЙ слой списка → разворачиваем.
    enabled.reverse()
    if not enabled and alpha_spec is None:
        emit.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
        return mat

    def _img_node(name, y, label=None):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.get(f"{base_name}_{name}")
        n.location = (-900, y)
        n.label = label or name
        sample_uv = n.image.get('inu_bake_uv', uv_name) if n.image else uv_name
        if sample_uv:
            uvm = nt.nodes.new('ShaderNodeUVMap')
            uvm.uv_map = sample_uv
            uvm.location = (-1100, y)
            nt.links.new(uvm.outputs['UV'], n.inputs['Vector'])
        return n

    def _cg(color_out, contrast, gamma, y):
        """Контраст/гамма слоя нодами (если не identity). Формулы 1:1 с
        bake_composite.apply_contrast_gamma → живой превью = numpy-сведение:
          contrast (c−0.5)·k+0.5  → BrightContrast, Contrast = k−1;
          gamma c**(1/g)          → Gamma, Gamma = 1/g.
        Возвращает итоговый Color-сокет."""
        out = color_out
        if contrast != 1.0:
            bc = nt.nodes.new('ShaderNodeBrightContrast')
            bc.location = (-680, y)
            bc.inputs['Bright'].default_value = 0.0
            bc.inputs['Contrast'].default_value = float(contrast) - 1.0
            nt.links.new(out, bc.inputs['Color'])
            out = bc.outputs['Color']
        if gamma != 1.0 and gamma > 0.0:
            g = nt.nodes.new('ShaderNodeGamma')
            g.location = (-680, y - 160)
            g.inputs['Gamma'].default_value = 1.0 / float(gamma)
            nt.links.new(out, g.inputs['Color'])
            out = g.outputs['Color']
        return out

    def _paint_mask(color, L, y):
        mask = next((M for M in specs if _key(M) == L.get('paint_mask_uid')
                     and M.get('enabled') and _has_img(_key(M))), None)
        if mask is None:
            return color
        mask_color = _cg(_img_node(_key(mask), y - 160, 'Маска').outputs['Color'],
                         mask.get('contrast', 1.0), mask.get('gamma', 1.0), y - 160)
        wrap = compat.make_mix_rgba(nt.nodes, blend='MULTIPLY', label='Маска')
        wrap.factor.default_value = float(mask['opacity'])
        nt.links.new(color, wrap.a)
        nt.links.new(mask_color, wrap.b)
        return wrap.result

    def _colorize(color, layer):
        if not layer.get('use_color') or layer['map_id'] not in SURFACE_MAP_IDS:
            return color
        bw = nt.nodes.new('ShaderNodeRGBToBW')
        nt.links.new(color, bw.inputs['Color'])
        ramp = compat.make_mix_rgba(nt.nodes, blend='MIX', label='Цвет эффекта')
        ramp.a.default_value = tuple(layer.get('color_dark', (0, 0, 0))) + (1.0,)
        ramp.b.default_value = tuple(layer.get('color_light', (1, 1, 1))) + (1.0,)
        from .bake_surface import levels
        fac = levels(nt, bw.outputs['Val'], layer.get('ramp_low', 0.),
                     layer.get('ramp_high', 1.), layer.get('ramp_smooth', False))
        nt.links.new(fac, ramp.factor)
        return ramp.result

    normal_outputs = {}

    def _surface(color, layer):
        if layer['map_id'] == 'NORMAL':
            if layer.get('normal_lighting', True):
                from .bake_normal import normal_lighting_nodes
                image = bpy.data.images.get(f'{base_name}_{_key(layer)}')
                normal_settings = dict(layer,
                    normal_space=image.get('inu_normal_space', 'OBJECT'),
                    normal_uv=image.get('inu_bake_uv', uv_name))
                normal_outputs[_key(layer)] = normal_lighting_nodes(nt, color, normal_settings)
                return normal_outputs[_key(layer)][0]
            if layer.get('desaturate'):
                bw = nt.nodes.new('ShaderNodeRGBToBW')
                nt.links.new(color, bw.inputs['Color'])
                return bw.outputs['Val']
        if layer['map_id'] not in SURFACE_MAP_IDS:
            return color
        from .bake_maps import _pattern_weight, _modulate_surface_output, _math_node
        from .bake_surface import directional_mask, combine_masks, math_node
        basis = layer.get('effect_basis', 'SELF')
        neutral = 1.0 if layer['map_id'] in ('DIRT', 'GRUNGE') else (0.5 if layer['map_id'] == 'CURVATURE' else 0.0)
        def source(basis):
            if basis == 'PATTERN':
                return _pattern_weight(nt, layer)
            if basis == 'DIRECTION':
                return directional_mask(nt, layer)
            basis_key = _key_for_mapid(basis)
            if basis == 'BEVEL':
                own_key = (_key(layer) if layer['map_id'] == 'BEVEL' else bevel_basis_key(_key(layer)))
                if _has_img(own_key):
                    basis_key = own_key
            if not _has_img(basis_key):
                return math_node(nt, 'ADD', 0., 0.)
            value = _img_node(basis_key, -200).outputs['Color']
            if basis == 'AO':
                value = math_node(nt, 'SUBTRACT', 1., value, True)
            elif basis == 'CURVATURE':
                value = math_node(nt, 'MULTIPLY', math_node(nt, 'ABSOLUTE',
                    math_node(nt, 'SUBTRACT', value, .5)), 2., True)
            return value
        if layer['map_id'] == 'GRUNGE' and basis == 'SELF':
            color = _pattern_weight(nt, layer)
        elif basis != 'SELF':
            # Legacy PATTERN basis leaves strength modulation to the next stage.
            weight = (math_node(nt, 'ADD', 1., 0.) if basis == 'PATTERN' else source(basis))
            if neutral == 1.:
                color = math_node(nt, 'SUBTRACT', 1., weight, True)
            elif neutral == .5:
                color = math_node(nt, 'ADD', math_node(nt, 'MULTIPLY', weight, .5), .5)
            else:
                color = weight
        color = combine_masks(nt, color, layer, source)
        if layer.get('basis_invert'):
            inverse = _math_node(nt, 'SUBTRACT', a=1.0, clamp=True)
            nt.links.new(color, inverse.inputs[1])
            color = inverse.outputs['Value']
        if (layer.get('surface_pattern', 'NONE') == 'NONE'
                or (layer['map_id'] == 'GRUNGE' and basis == 'SELF')):
            return color
        return _modulate_surface_output(nt, color, neutral, layer)

    def _normal_highlight(layer, y):
        return normal_outputs[_key(layer)][1]

    def _add_highlight(color, layer, y):
        highlight = _paint_mask(_normal_highlight(layer, y), layer, y)
        wrap = compat.make_mix_rgba(nt.nodes, blend='ADD', label='Normal highlights')
        wrap.factor.default_value = float(layer['opacity'])
        nt.links.new(color, wrap.a)
        nt.links.new(highlight, wrap.b)
        return wrap.result

    y = 0
    if enabled:
        base = enabled[0]
        acc = _surface(_img_node(_key(base), y, base['map_id']).outputs['Color'], base)
        acc = _cg(acc, base.get('contrast', 1.0), base.get('gamma', 1.0), y)
        acc = _colorize(acc, base)
        acc = _paint_mask(acc, base, y)
        if base['map_id'] == 'NORMAL' and base.get('normal_lighting', True):
            acc = _add_highlight(acc, base, y)
        x = -460
        for L in enabled[1:]:
            y -= 320
            top_col = _surface(_img_node(_key(L), y, L['map_id']).outputs['Color'], L)
            top_col = _cg(top_col, L.get('contrast', 1.0), L.get('gamma', 1.0), y)
            top_col = _colorize(top_col, L)
            normal_lit = L['map_id'] == 'NORMAL' and L.get('normal_lighting', True)
            if normal_lit:
                # Masking a multiplier must tend to white outside the mask.
                from .bake_maps import _math_node
                delta = _math_node(nt, 'SUBTRACT', a=1.0)
                nt.links.new(top_col, delta.inputs[1])
                inverse = _math_node(nt, 'SUBTRACT', a=1.0)
                nt.links.new(_paint_mask(delta.outputs['Value'], L, y), inverse.inputs[1])
                top_col = inverse.outputs['Value']
            else:
                top_col = _paint_mask(top_col, L, y)
            wrap = compat.make_mix_rgba(
                nt.nodes,
                blend=('MULTIPLY' if normal_lit else BLEND_NODE_TYPE.get(L['blend_mode'], 'MIX')),
                label=L['map_id'])
            wrap.node.location = (x, y // 2)
            wrap.factor.default_value = float(L['opacity'])
            nt.links.new(acc, wrap.a)
            nt.links.new(top_col, wrap.b)
            acc = wrap.result
            if normal_lit:
                acc = _add_highlight(acc, L, y)
            x += 220
        # Прилайт: умножаем итоговый композит на вертекс-цвет (texture ×
        # prelight), чтобы прилайт оставался виден после запекания. Только
        # превью — на сохранённую/экспортируемую текстуру не влияет.
        if vcol_name:
            vc = None
            for tname in ('ShaderNodeColorAttribute', 'ShaderNodeVertexColor'):
                try:
                    vc = nt.nodes.new(tname)
                    break
                except RuntimeError:
                    vc = None
            if vc is not None:
                try:
                    vc.layer_name = vcol_name
                except Exception:
                    pass
                vc.location = (50, -250)
                wrap = compat.make_mix_rgba(nt.nodes, blend='MULTIPLY',
                                            label='prelight')
                wrap.node.location = (150, 0)
                wrap.factor.default_value = 1.0
                nt.links.new(acc, wrap.a)
                nt.links.new(vc.outputs['Color'], wrap.b)
                acc = wrap.result
        if base_image is not None:
            tex = nt.nodes.new('ShaderNodeTexImage')
            tex.name = 'INU_OverlayBase'
            tex.image = base_image
            if base_uv:
                uv = nt.nodes.new('ShaderNodeUVMap')
                uv.name = 'INU_OverlayBaseUV'
                uv.uv_map = base_uv
                nt.links.new(uv.outputs['UV'], tex.inputs['Vector'])
            overlay = compat.make_mix_rgba(nt.nodes, blend='MULTIPLY', label='bake_over')
            overlay.factor.default_value = 1.0
            nt.links.new(tex.outputs['Color'], overlay.a)
            nt.links.new(acc, overlay.b)
            acc = overlay.result
        nt.links.new(acc, emit.inputs['Color'])
    else:
        # Только ALPHA-слой — RGB чёрный, значима лишь прозрачность.
        emit.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)

    # Провайдер альфы → прозрачность превью: Mix(Transparent, Emission) по маске.
    if alpha_only_for_bake and alpha_spec is None:
        if enabled:
            tex = _img_node(_key(enabled[0]), -520)
            nt.links.new(tex.outputs['Alpha'], emit.inputs['Color'])
        else:
            emit.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    if alpha_spec is not None and (not opaque_for_bake or alpha_only_for_bake):
        decal = bool(alpha_spec.get('as_decal'))
        # Источник яркости: сама карта (декаль) / др. карта / прозрачность мат-ла.
        # Имя картинки — по ключу слоя (uid|map_id), не по «сырому» map_id.
        if decal:
            src_name = _key(alpha_spec)
        else:
            src_ref = alpha_spec.get('alpha_source') or 'MATERIAL'
            src_name = _key_for_mapid(src_ref) if src_ref != 'MATERIAL' else 'MATERIAL'
        alpha_name = _key_for_mapid('ALPHA')
        fac_img = (src_name if (src_name != 'MATERIAL' and _has_img(src_name))
                   else (alpha_name if _has_img(alpha_name) else None))
        if fac_img is not None:
            atex = _img_node(fac_img, y - 320)
            fac_out = atex.outputs['Color']
            if decal:
                fac_out = _surface(fac_out, alpha_spec)
                # Порог/мягкость: clamp((b−lo)/(hi−lo)) двумя Math-нодами.
                thr = float(alpha_spec.get('decal_threshold', 0.5))
                soft = float(alpha_spec.get('decal_softness', 0.25))
                lo, hi = thr - soft, thr + soft
                if hi > lo:
                    sub = nt.nodes.new('ShaderNodeMath')
                    sub.operation = 'SUBTRACT'
                    sub.location = (150, -400)
                    sub.inputs[1].default_value = lo
                    nt.links.new(fac_out, sub.inputs[0])
                    div = nt.nodes.new('ShaderNodeMath')
                    div.operation = 'DIVIDE'
                    div.use_clamp = True
                    div.location = (320, -400)
                    div.inputs[1].default_value = (hi - lo)
                    nt.links.new(sub.outputs[0], div.inputs[0])
                    fac_out = div.outputs[0]
                else:
                    # Мягкость 0 → жёсткая граница (яркость > порога → 1).
                    gt = nt.nodes.new('ShaderNodeMath')
                    gt.operation = 'GREATER_THAN'
                    gt.location = (200, -400)
                    gt.inputs[1].default_value = thr
                    nt.links.new(fac_out, gt.inputs[0])
                    fac_out = gt.outputs[0]
                invert_dir = not alpha_spec.get('decal_invert')   # деф.: видно тёмное
            else:
                # Обычная маска читается из R. Alpha используем только если
                # весь R пуст (покрытие Hi→Low), как при numpy-сведении.
                if (alpha_spec.get('map_id') == 'ALPHA'
                        and (alpha_spec.get('alpha_source') or 'MATERIAL') == 'MATERIAL'):
                    from .bake_core import read_image_to_numpy
                    from .bake_composite import material_alpha_uses_coverage
                    if material_alpha_uses_coverage(read_image_to_numpy(atex.image)):
                        fac_out = atex.outputs['Alpha']
                    else:
                        try:
                            separate = nt.nodes.new('ShaderNodeSeparateColor')
                            separate.mode = 'RGB'
                        except RuntimeError:
                            # Blender до появления Separate Color.
                            separate = nt.nodes.new('ShaderNodeSeparateRGB')
                        nt.links.new(atex.outputs['Color'], separate.inputs[0])
                        fac_out = separate.outputs[0]
                    gt = nt.nodes.new('ShaderNodeMath')
                    gt.operation = 'LESS_THAN'
                    gt.location = (470, -520)
                    gt.inputs[1].default_value = 0.5
                    nt.links.new(fac_out, gt.inputs[0])
                    solid = nt.nodes.new('ShaderNodeMath')
                    solid.operation = 'SUBTRACT'
                    solid.inputs[0].default_value = 1.0
                    nt.links.new(gt.outputs[0], solid.inputs[1])
                    fac_out = solid.outputs[0]
                invert_dir = bool(alpha_spec.get('alpha_invert'))
            if invert_dir:
                m = nt.nodes.new('ShaderNodeMath')
                m.operation = 'SUBTRACT'
                m.location = (470, -400)
                m.inputs[0].default_value = 1.0
                nt.links.new(fac_out, m.inputs[1])
                fac_out = m.outputs[0]
            strength = nt.nodes.new('ShaderNodeMath')
            strength.operation = 'MULTIPLY'
            strength.use_clamp = True
            strength.inputs[1].default_value = float(alpha_spec.get('opacity', 1.0))
            nt.links.new(fac_out, strength.inputs[0])
            fac_out = strength.outputs[0]
            if alpha_only_for_bake:
                nt.links.new(fac_out, emit.inputs['Color'])
                return mat
            trans = nt.nodes.new('ShaderNodeBsdfTransparent')
            trans.location = (300, -260)
            mixsh = nt.nodes.new('ShaderNodeMixShader')
            mixsh.location = (650, -60)
            # Fac 0 → Transparent (дыра), 1 → Emission (видно).
            nt.links.new(fac_out, mixsh.inputs['Fac'])
            nt.links.new(trans.outputs[0], mixsh.inputs[1])
            nt.links.new(emit.outputs['Emission'], mixsh.inputs[2])
            nt.links.new(mixsh.outputs[0], out.inputs['Surface'])
            # Стандарт для альфы: Метод рендеринга Смешанный + Перекрытие
            # прозрачности ВЫКЛ. Через compat — на 4.2+ (EEVEE Next) один
            # blend_method ничего не делает, и превью ALPHA-слоя / «как
            # прозрачный декаль» рисовалось непрозрачным.
            compat.make_material_alpha(mat)
        else:
            # Датаблок переиспользуется между сборками — если в прошлый раз
            # был альфа-слой, вернуть непрозрачность явно.
            compat.set_blend_method(mat, 'OPAQUE')
    else:
        compat.set_blend_method(mat, 'OPAQUE')
    return mat
