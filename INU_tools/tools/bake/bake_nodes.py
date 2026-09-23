# INU_tools.tools.bake.bake_nodes — живой нодовый композит.
#
# Собирает материал-стек Mix-нод из per-map картинок (<base>_<map_id>):
# каждый слой = одна Mix-нода, blend_type = режим слоя, Fac = прозрачность.
# Результат показывается на модели в реальном времени (Material Preview) —
# blend/opacity крутятся без перезапекания. Финальное «сведение» в одну
# текстуру делает numpy-композит (bake_composite) отдельной кнопкой.

import bpy

from .. import compat
from .bake_composite import BLEND_NODE_TYPE


COMPOSITE_MAT = 'INU_BakeComposite'


def build_composite_material(specs, base_name, uv_name, vcol_name=None):
    """Собрать/пересобрать материал INU_BakeComposite по списку слоёв.

    specs: list[dict(map_id, blend_mode, opacity, enabled)] СНИЗУ ВВЕРХ
           (index 0 = база). Картинки берутся как <base_name>_<map_id>.
    `vcol_name` — если задан, итоговый композит умножается на вертекс-цвет
    прилайта (texture × prelight), чтобы прилайт не пропадал визуально после
    запекания. Возвращает материал. Если материал уже на объекте —
    пересборка его нод обновляет живое превью мгновенно.
    """
    mat = (bpy.data.materials.get(COMPOSITE_MAT)
           or bpy.data.materials.new(COMPOSITE_MAT))
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
    enabled = [L for L in specs
               if L.get('enabled') and not _is_provider(L)
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
        if uv_name:
            uvm = nt.nodes.new('ShaderNodeUVMap')
            uvm.uv_map = uv_name
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

    y = 0
    if enabled:
        base = enabled[0]
        acc = _cg(_img_node(_key(base), y, base['map_id']).outputs['Color'],
                  base.get('contrast', 1.0), base.get('gamma', 1.0), y)
        x = -460
        for L in enabled[1:]:
            y -= 320
            top_col = _cg(_img_node(_key(L), y, L['map_id']).outputs['Color'],
                          L.get('contrast', 1.0), L.get('gamma', 1.0), y)
            wrap = compat.make_mix_rgba(
                nt.nodes,
                blend=BLEND_NODE_TYPE.get(L['blend_mode'], 'MIX'),
                label=L['map_id'])
            wrap.node.location = (x, y // 2)
            wrap.factor.default_value = float(L['opacity'])
            nt.links.new(acc, wrap.a)
            nt.links.new(top_col, wrap.b)
            acc = wrap.result
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
        nt.links.new(acc, emit.inputs['Color'])
    else:
        # Только ALPHA-слой — RGB чёрный, значима лишь прозрачность.
        emit.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)

    # Провайдер альфы → прозрачность превью: Mix(Transparent, Emission) по маске.
    if alpha_spec is not None:
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
                # CUTOUT для альфы из прозрачности материала. Значение может
                # быть в RGB (обычный EMIT) ИЛИ в АЛЬФА-канале карты (покрытие
                # Hi→Low, RGB пустой): берём max(Color, Alpha), затем порог 0.5
                # → 1/0. Совпадает с numpy-сведением в bake_composite.
                if (alpha_spec.get('map_id') == 'ALPHA'
                        and (alpha_spec.get('alpha_source') or 'MATERIAL') == 'MATERIAL'):
                    mx = nt.nodes.new('ShaderNodeMath')
                    mx.operation = 'MAXIMUM'
                    mx.location = (300, -520)
                    nt.links.new(fac_out, mx.inputs[0])
                    nt.links.new(atex.outputs['Alpha'], mx.inputs[1])
                    gt = nt.nodes.new('ShaderNodeMath')
                    gt.operation = 'GREATER_THAN'
                    gt.location = (470, -520)
                    gt.inputs[1].default_value = 0.5
                    nt.links.new(mx.outputs[0], gt.inputs[0])
                    fac_out = gt.outputs[0]
                invert_dir = bool(alpha_spec.get('alpha_invert'))
            if invert_dir:
                m = nt.nodes.new('ShaderNodeMath')
                m.operation = 'SUBTRACT'
                m.location = (470, -400)
                m.inputs[0].default_value = 1.0
                nt.links.new(fac_out, m.inputs[1])
                fac_out = m.outputs[0]
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
