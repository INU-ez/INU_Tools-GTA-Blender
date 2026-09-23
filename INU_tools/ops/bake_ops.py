# INU_tools.ops.bake_ops — Слой 4 подсистемы запекания: операторы.
#
# Оркестрируют bake_core + bake_maps + bake_composite по scene-настройкам
# (INUSceneSettings.gtatools_bake_*) и стеку слоёв (gtatools_bake_layers).
# Сами карты/композит живут в tools/bake/ — здесь только склейка, guard'ы
# валидации (Cycles, UV), report() и undo.
#
# ВАЖНО: НЕ добавлять `from __future__ import annotations` — модуль
# объявляет Operator-проперти (EnumProperty), их ломает PEP 563.

import json
import os
import re

import bpy
from bpy.props import EnumProperty, StringProperty, IntProperty

from .. import T
from ..tools import compat


# ── Память запечённых полигонов на слой (Bevel «только выделенные») ──
# Индексы граней хранятся на ОБЪЕКТЕ под ключом слоя → работает и для
# нескольких объектов; переключение слоя восстанавливает выделение.

def _lkey(L):
    """Ключ картинки слоя = uid | map_id. Каждый слой пишет в свою картинку
    <base>_<key> → несколько слоёв одной карты (напр. Bevel) не затирают друг
    друга. Совпадает с bake_composite.layer_image_key."""
    return getattr(L, 'uid', '') or L.map_id


def _bl_owner(context):
    """Владелец стека слоёв запекания = inu АКТИВНОЙ модели (стек теперь
    per-object, а не на сцене). None, если активной меш-модели нет. Возвращает
    объект с полями .gtatools_bake_layers / .gtatools_bake_layers_index — те же
    хелперы (_layer_specs/_composite_stack_image/…) принимают его вместо
    scene.inu_settings, т.к. используют аргумент только ради этой коллекции."""
    obj = getattr(context, 'active_object', None) or getattr(context, 'object', None)
    return obj.inu if (obj is not None and hasattr(obj, 'inu')) else None


def _alpha_src_img(s, base, src):
    """Картинка карты-источника альфы (alpha_source ссылается по map_id) — берём
    у ПЕРВОГО включённого слоя этой карты (его per-layer ключ); fallback —
    старое имя <base>_<map_id>."""
    for L in s.gtatools_bake_layers:
        if getattr(L, 'enabled', True) and L.map_id == src:
            im = bpy.data.images.get(f"{base}_{_lkey(L)}")
            if im is not None:
                return im
    return bpy.data.images.get(f"{base}_{src}")


def _map_image(obj, map_id):
    """Картинка запечённой карты `map_id` у объекта. Слой печёт в
    <base>_<uid> (см. _lkey), а не в <base>_<map_id> — искать надо по ключу
    слоя, иначе свежий бейк «не находится»: превью LightMap, «Применить» и
    «Пост-обработка» ругались «Нет запечённого результата — сначала
    запеките». Fallback — старое имя <base>_<map_id>."""
    base = obj.get("inu_bake_base", "") if obj is not None else ""
    if not base:
        return None
    blo = getattr(obj, 'inu', None)
    for L in getattr(blo, 'gtatools_bake_layers', []) or []:
        if L.map_id != map_id:
            continue
        im = bpy.data.images.get(f"{base}_{_lkey(L)}")
        if im is not None:
            return im
    return bpy.data.images.get(f"{base}_{map_id}")


def _lightmap_image(obj):
    """Запечённый LightMap объекта (или None)."""
    return _map_image(obj, 'LIGHTMAP')


def _layer_faces_key(uid):
    return f"inu_bake_faces_{uid}"


def _selected_face_indices(obj):
    me = getattr(obj, 'data', None)
    polys = getattr(me, 'polygons', None)
    if polys is None:
        return []
    return [p.index for p in polys if p.select]


def _save_layer_faces(obj, uid, indices):
    if obj is None or not uid:
        return
    try:
        obj[_layer_faces_key(uid)] = ",".join(str(i) for i in indices)
    except Exception:                             # noqa: BLE001
        pass


def _restore_layer_faces(obj, uid):
    """Выделить на obj грани, запечённые для слоя uid. Returns кол-во."""
    me = getattr(obj, 'data', None)
    polys = getattr(me, 'polygons', None)
    if polys is None or not uid:
        return 0
    raw = obj.get(_layer_faces_key(uid))
    if not raw:
        return 0
    try:
        want = {int(x) for x in str(raw).split(',') if x.strip().isdigit()}
    except Exception:                             # noqa: BLE001
        return 0
    n = 0
    for p in polys:
        sel = p.index in want
        if p.select != sel:
            p.select = sel
        if sel:
            n += 1
    me.update()
    return n


def _isolate_selected_faces(context, obj):
    """Временная копия obj только с ВЫДЕЛЕННЫМИ гранями (сохраняет UV +
    материалы) — чтобы запечь карту только по ним. Returns (tmp, teardown)
    или (None, None), если выделенных граней нет."""
    import bmesh
    me = getattr(obj, 'data', None)
    polys = getattr(me, 'polygons', None)
    if polys is None or not any(p.select for p in polys):
        return None, None
    tmp_mesh = me.copy()
    bm = bmesh.new()
    bm.from_mesh(tmp_mesh)
    bm.faces.ensure_lookup_table()
    doomed = [f for f in bm.faces if not f.select]
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context='FACES')
    bm.to_mesh(tmp_mesh)
    bm.free()
    tmp = obj.copy()
    tmp.data = tmp_mesh
    tmp.name = obj.name + "__bake_sel"
    context.scene.collection.objects.link(tmp)
    tmp.matrix_world = obj.matrix_world.copy()

    def teardown():
        try:
            d = tmp.data
            bpy.data.objects.remove(tmp, do_unlink=True)
            if d and getattr(d, 'users', 1) == 0:
                bpy.data.meshes.remove(d)
        except Exception:                         # noqa: BLE001
            pass
    return tmp, teardown


class GTATOOLS_OT_bake_select_layer(bpy.types.Operator):
    """Выбрать слой (его карта показывается в Image-редакторе)."""
    bl_idname = "gtatools.bake_select_layer"
    bl_label = "Выбрать слой"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=0)

    def execute(self, context):
        blo = _bl_owner(context)
        if blo and 0 <= self.index < len(blo.gtatools_bake_layers):
            blo.gtatools_bake_layers_index = self.index   # триггерит показ карты
        return {'FINISHED'}


def _derive_texture_name(obj, s):
    """Имя выходной текстуры из имени модели: срезаем .001-хвост, известные
    префиксы и суффиксы (_DFF/_LOD/_COL + фиксированные _hi/_low).
    Регистронезависимо."""
    from ..tools.bake import HI_SUFFIX, LOW_SUFFIX
    name = re.sub(r'\.\d+$', '', obj.name)
    low = name.lower()
    for pfx in (s.gtatools_prefix_dff, s.gtatools_prefix_lod,
                s.gtatools_prefix_col):
        if pfx and low.startswith(pfx.lower()):
            name = name[len(pfx):]
            low = name.lower()
    for sfx in (HI_SUFFIX, LOW_SUFFIX,
                s.gtatools_suffix_dff, s.gtatools_suffix_lod,
                s.gtatools_suffix_col):
        if sfx and low.endswith(sfx.lower()):
            name = name[:-len(sfx)]
            break
    name = name.strip(' _.')
    return name or "inu_bake"


# Имя INT-атрибута FACE-домена, куда прячем привязку «полигон → материал» на
# время превью. В отличие от JSON-снимка по номерам полигонов, атрибут
# ПЕРЕЖИВАЕТ правки топологии (экструд/разрез копируют значение на новые грани),
# поэтому материалы вернутся даже если ты редактировал сетку с включённым
# композитом (напр. выделял/добавлял полигоны для Bevel).
_MAT_IDX_ATTR = "inu_bake_mat_idx"


def _store_mat_idx_attr(me):
    """Сохранить material_index в FACE-атрибут (перезаписать, если был)."""
    try:
        n = len(me.polygons)
        if n == 0:
            return
        idx = [0] * n
        me.polygons.foreach_get('material_index', idx)
        attr = me.attributes.get(_MAT_IDX_ATTR)
        if attr is not None and (attr.domain != 'FACE'
                                 or attr.data_type != 'INT'):
            me.attributes.remove(attr)
            attr = None
        if attr is None:
            attr = me.attributes.new(_MAT_IDX_ATTR, 'INT', 'FACE')
        attr.data.foreach_set('value', idx)
    except Exception:                                 # noqa: BLE001
        pass


def _restore_mat_idx_attr(me):
    """Вернуть material_index из FACE-атрибута. True при успехе. Работает даже
    после правок топологии — у атрибута ровно столько значений, сколько граней
    сейчас (Blender ресайзит его вместе с сеткой)."""
    try:
        attr = me.attributes.get(_MAT_IDX_ATTR)
        if (attr is None or attr.domain != 'FACE'
                or attr.data_type != 'INT'):
            return False
        n = len(me.polygons)
        if n == 0 or len(attr.data) != n or len(me.materials) == 0:
            return False
        idx = [0] * n
        attr.data.foreach_get('value', idx)
        top = len(me.materials) - 1
        idx = [i if 0 <= i <= top else 0 for i in idx]
        me.polygons.foreach_set('material_index', idx)
        me.update()
        return True
    except Exception:                                 # noqa: BLE001
        return False


def _clear_mat_idx_attr(me):
    try:
        attr = me.attributes.get(_MAT_IDX_ATTR)
        if attr is not None:
            me.attributes.remove(attr)
    except Exception:                                 # noqa: BLE001
        pass


def _snapshot_materials(obj):
    """Сохранить исходные материалы + рендер-UV в custom-props (только если
    ещё не сохранены — не перезаписываем при повторном применении)."""
    if obj.get("inu_bake_preview_on", 0):
        return
    me = obj.data
    obj["inu_bake_prev_mats"] = json.dumps(
        [s.material.name if s.material else "" for s in obj.material_slots])
    obj["inu_bake_prev_render_uv"] = next(
        (u.name for u in me.uv_layers if u.active_render), "")
    # КРИТИЧНО: предпросмотр заменит слоты на preview-материал → у
    # оригиналов станет 0 пользователей, и при сохранении .blend Blender
    # их удалит (на повторном открытии восстанавливать нечего → «материалы
    # пропали»). Ставим fake user, чтобы оригиналы пережили сохранение.
    for sslot in obj.material_slots:
        if sslot.material is not None:
            try:
                sslot.material.use_fake_user = True
            except Exception:
                pass
    # Сохранить привязку материалов к полигонам (material_index). Превью
    # схлопывает все слоты в один материал → индексы полигонов сбрасываются
    # в 0; без этого снимка при возврате полигоны с других слотов «слетают»
    # на первый материал. Восстанавливаем в _restore_materials.
    try:
        n = len(me.polygons)
        idx = [0] * n
        me.polygons.foreach_get('material_index', idx)
        obj["inu_bake_prev_mat_idx"] = json.dumps(idx)
    except Exception:
        obj["inu_bake_prev_mat_idx"] = "[]"
    # Плюс тот же снимок в FACE-атрибут — он переживёт правку топологии и
    # восстановит материалы, когда JSON-снимок по номерам уже не совпадёт.
    _store_mat_idx_attr(me)


def _assign_material(obj, mat, uv_name):
    """Поставить единственный материал `mat`. active_render НЕ трогаем —
    превью/композит сэмплят через явные UV Map ноды, рабочая рендер-UV
    пользователя остаётся как есть."""
    me = obj.data
    me.materials.clear()
    me.materials.append(mat)
    obj["inu_bake_preview_on"] = 1


def _restore_materials(obj):
    """Вернуть исходные материалы + рендер-UV; снять флаг превью."""
    me = obj.data
    try:
        mats = json.loads(obj.get("inu_bake_prev_mats", "[]"))
    except Exception:
        mats = []
    me.materials.clear()
    _missing = []
    for nm in mats:
        m = bpy.data.materials.get(nm) if nm else None
        if nm and m is None:
            _missing.append(nm)
        me.materials.append(m)
    if _missing:
        # Материал не найден — был удалён (старые сцены без fake-user,
        # сохранённые с включённым превью). Восстановить нечего.
        print("[INU bake] восстановление материалов: не найдены "
              + ", ".join(_missing))
    # Вернуть привязку материалов к полигонам (см. _snapshot_materials).
    # Сначала пробуем FACE-атрибут — он верен даже после правки топологии
    # (добавил/удалил полигоны с включённым композитом). Если его нет или он
    # не совпал — падаем на старый JSON-снимок по номерам полигонов.
    if not _restore_mat_idx_attr(me):
        try:
            idx = json.loads(obj.get("inu_bake_prev_mat_idx", "[]"))
            if idx and len(idx) == len(me.polygons) and len(me.materials) > 0:
                # Зажать индексы в число слотов (если слотов стало меньше).
                top = len(me.materials) - 1
                idx = [i if 0 <= i <= top else 0 for i in idx]
                me.polygons.foreach_set('material_index', idx)
                me.update()
        except Exception:
            pass
    _clear_mat_idx_attr(me)
    ruv = obj.get("inu_bake_prev_render_uv", "")
    if ruv and ruv in me.uv_layers:
        for u in me.uv_layers:
            u.active_render = (u.name == ruv)
    obj["inu_bake_preview_on"] = 0
    obj["inu_bake_overbase_on"] = 0        # over-base снят (см. show_over_base)
    # Подчистить осиротевшие preview-материалы (в т.ч. per-слот overlay
    # INU_BakeOver_N от «Показать поверх базы»).
    dead = ["INU_BakePreview", "INU_BakeComposite"]
    dead += [m.name for m in bpy.data.materials
             if m.name.startswith("INU_BakeOver_")]
    for nm in dead:
        m = bpy.data.materials.get(nm)
        if m is not None and m.users == 0:
            try:
                bpy.data.materials.remove(m)
            except Exception:
                pass


def _prelight_attr_name(obj):
    """Имя вертекс-цветового атрибута прилайта, на который умножаем
    запечённую текстуру (слой «Day», иначе активный цветовой атрибут).
    None — если у меша нет вертекс-цветов (тогда материал = просто текстура,
    как раньше). Так прилайт переносится в запечённый материал и виден как
    в игре (texture × prelight), а не теряется визуально."""
    me = getattr(obj, 'data', None)
    cattrs = getattr(me, 'color_attributes', None)
    if not cattrs or len(cattrs) == 0:
        return None
    for nm in ('Day', 'day'):
        if cattrs.get(nm) is not None:
            return nm
    act = getattr(cattrs, 'active_color', None)
    if act is not None:
        return act.name
    return cattrs[0].name


def _new_vcol_node(nt, vcol_name):
    """Нода чтения вертекс-цвета (compat 2.83–5.1): ColorAttribute (3.3+)
    или VertexColor (старее). Возвращает ноду или None."""
    for tname in ('ShaderNodeColorAttribute', 'ShaderNodeVertexColor'):
        try:
            n = nt.nodes.new(tname)
        except RuntimeError:
            continue
        try:
            n.layer_name = vcol_name
        except Exception:
            pass
        return n
    return None


def _mul_by_vcol(nt, tex_color_out, vcol_name):
    """Вставить умножение texture-color × vertex-color (прилайт). Возвращает
    выходной сокет для дальнейшей привязки (или исходный, если не вышло).
    Использует версия-безопасный compat.make_mix_rgba (Mix-нода 5.1)."""
    if not vcol_name:
        return tex_color_out
    vc = _new_vcol_node(nt, vcol_name)
    if vc is None:
        return tex_color_out
    from ..tools import compat
    wrap = compat.make_mix_rgba(nt.nodes, blend='MULTIPLY', label='prelight')
    wrap.factor.default_value = 1.0
    nt.links.new(tex_color_out, wrap.a)
    nt.links.new(vc.outputs['Color'], wrap.b)
    return wrap.result


def _build_single_image_mat(img, uv_name, vcol_name=None):
    """Материал INU_BakePreview — flat-эмиссия одной картинки (per-map),
    опционально умноженной на вертекс-цвет прилайта (`vcol_name`)."""
    pm = (bpy.data.materials.get("INU_BakePreview")
          or bpy.data.materials.new("INU_BakePreview"))
    pm.use_nodes = True
    pm.use_fake_user = False
    nt = pm.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emit = nt.nodes.new('ShaderNodeEmission')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    if uv_name:
        uvm = nt.nodes.new('ShaderNodeUVMap')
        uvm.uv_map = uv_name
        nt.links.new(uvm.outputs['UV'], tex.inputs['Vector'])
    color_out = _mul_by_vcol(nt, tex.outputs['Color'], vcol_name)
    nt.links.new(color_out, emit.inputs['Color'])
    nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])
    return pm


def _build_standard_material(img, uv_name, vcol_name=None):
    """Финальный СТАНДАРТНЫЙ материал: Principled BSDF + запечённая текстура,
    опционально умноженная на вертекс-цвет прилайта (`vcol_name`). Base Color
    ← texture(× prelight); Alpha ← альфа текстуры (если RGBA) с alpha-clip."""
    mat = (bpy.data.materials.get("INU_BakeStandard")
           or bpy.data.materials.new("INU_BakeStandard"))
    mat.use_nodes = True
    mat.use_fake_user = False
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    if uv_name:
        uvm = nt.nodes.new('ShaderNodeUVMap')
        uvm.uv_map = uv_name
        nt.links.new(uvm.outputs['UV'], tex.inputs['Vector'])
    color_out = _mul_by_vcol(nt, tex.outputs['Color'], vcol_name)
    nt.links.new(color_out, bsdf.inputs['Base Color'])
    # Альфа — только если текстура RGBA (есть силуэт).
    has_alpha = (img is not None and img.channels == 4)
    if has_alpha:
        nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    # Specular 0 — как для GTA-материалов (см. dff_import).
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.0
    elif 'Specular' in bsdf.inputs:
        bsdf.inputs['Specular'].default_value = 0.0
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
    # Прозрачность billboard — стандарт проекта: Метод рендеринга Смешанный
    # + Перекрытие прозрачности ВЫКЛ (compat пишет оба поколения EEVEE;
    # на 4.2+ blend_method сам по себе — no-op).
    if has_alpha:
        compat.make_material_alpha(mat)
    else:
        compat.set_blend_method(mat, 'OPAQUE')   # датаблок переиспользуется
    return mat


def _apply_standard_material(obj, img, uv_name):
    """Применить финальный стандартный материал на obj (с сохранением
    исходных материалов для preview-toggle)."""
    _snapshot_materials(obj)
    mat = _build_standard_material(img, uv_name, _prelight_attr_name(obj))
    _assign_material(obj, mat, uv_name)
    obj["inu_bake_mode_live"] = 0
    return mat


def _layer_specs(s):
    return [{'map_id': L.map_id, 'uid': getattr(L, 'uid', ''),
             'blend_mode': L.blend_mode,
             'opacity': L.opacity, 'enabled': L.enabled,
             'contrast': L.contrast, 'gamma': L.gamma,
             'alpha_source': getattr(L, 'alpha_source', ''),
             'alpha_invert': getattr(L, 'alpha_invert', False),
             'as_decal': getattr(L, 'as_decal', False),
             'decal_threshold': getattr(L, 'decal_threshold', 0.5),
             'decal_softness': getattr(L, 'decal_softness', 0.25),
             'decal_invert': getattr(L, 'decal_invert', False)}
            for L in s.gtatools_bake_layers]


def _apply_result_material(obj):
    """Показать результат на модели: композит → живой нодовый стек, per-map →
    одиночная картинка. Возвращает материал (или None, если нечего показать).

    Учитывает inu_bake_preview_kind: если последним показывали ЛАЙТМАП
    (авто-превью), повторное «Показать текстуру» тоже показывает лайтмап БЕЗ
    ×prelight — иначе toggle делал его темнее (лайтмап × Day-vcol)."""
    if obj.get("inu_bake_preview_kind", "") == "lightmap":
        return _apply_lightmap_preview(obj)
    s = bpy.context.scene.inu_settings
    base = obj.get("inu_bake_base", "")
    uv = obj.get("inu_bake_uv", "")
    _snapshot_materials(obj)
    if obj.get("inu_bake_mode_live", 0):
        from ..tools.bake import bake_nodes
        # RAW — без ×prelight (как и single-превью ниже): «Показать текстуру»
        # показывает запечённое, а не in-game освещение. Иначе тёмный prelight
        # чернил стены. In-game вид даёт отдельная «Показать поверх базы».
        mat = bake_nodes.build_composite_material(
            _layer_specs(obj.inu), base, uv, None)
        obj["inu_bake_preview_kind"] = "composite"
    else:
        img = bpy.data.images.get(obj.get("inu_bake_image", ""))
        if img is None:
            return None
        # RAW запечённая карта — БЕЗ ×prelight. Иначе там, где prelight тёмный
        # (теневые стены зданий GTA), карта чернела, хотя запеклась нормально
        # (юзер: «стены чёрные, а „поверх базы“ — норм»). «Показать текстуру» =
        # показать ЧТО запёк, без освещения (как в TexTools).
        mat = _build_single_image_mat(img, uv, None)
        obj["inu_bake_preview_kind"] = "single"
    _assign_material(obj, mat, uv)
    return mat


def _apply_lightmap_preview(obj):
    """Превью LightMap на модели — ЖИВОЙ нодовый композит стека, но БЕЗ
    ×prelight (лайтмап уже и есть освещение; умножение на Day-vcol его бы
    затемнило). mode_live=1 → контраст/гамма/прозрачность слоёв правятся
    вживую (rebuild_live_composite). Сэмплится через UV запекания лайтмапа.
    Возвращает материал или None."""
    base = obj.get("inu_bake_base", "")
    if _lightmap_image(obj) is None:
        return None
    s = bpy.context.scene.inu_settings
    uv = obj.get("inu_bake_lm_uv", "") or obj.get("inu_bake_uv", "")
    _snapshot_materials(obj)
    from ..tools.bake import bake_nodes
    mat = bake_nodes.build_composite_material(_layer_specs(obj.inu), base, uv, None)
    _assign_material(obj, mat, uv)
    obj["inu_bake_mode_live"] = 1
    obj["inu_bake_image"] = ""
    obj["inu_bake_preview_kind"] = "lightmap"
    return mat


def _stack_has_bakeable(s, base):
    """Есть ли что сводить: включённый слой со своей запечённой картой ИЛИ
    ALPHA-слой, чей источник (напр. Shadow) запечён."""
    for L in s.gtatools_bake_layers:
        if not L.enabled:
            continue
        if bpy.data.images.get(f"{base}_{_lkey(L)}") is not None:
            return True
        if L.map_id == 'ALPHA':
            src = getattr(L, 'alpha_source', '')
            if (src and src != 'MATERIAL'
                    and _alpha_src_img(s, base, src) is not None):
                return True
    return False


def _composite_stack_image(s, base, out_name):
    """Свести включённые карты стека (<base>_<map>) numpy-композитом в одну
    картинку `out_name`. Возвращает image или None (нет запечённых карт).
    Единый движок сведения — используется и «Сохранить как», и overlay-превью."""
    from ..tools import bake as B
    pixels = {}
    for L in s.gtatools_bake_layers:
        key = _lkey(L)
        if not L.enabled or key in pixels:
            continue
        img = bpy.data.images.get(f"{base}_{key}")
        if img is not None:
            arr = B.read_image_to_numpy(img)
            pixels[key] = arr
            pixels.setdefault(L.map_id, arr)   # дубль по map_id для alpha_source
    # Дозагрузить карту-источник альфы (напр. Shadow), даже если её слой
    # выключен в RGB — она нужна только как альфа-канал.
    for L in s.gtatools_bake_layers:
        if not L.enabled or L.map_id != 'ALPHA':
            continue
        src = getattr(L, 'alpha_source', '')
        if src and src != 'MATERIAL' and src not in pixels:
            img = _alpha_src_img(s, base, src)
            if img is not None:
                pixels[src] = B.read_image_to_numpy(img)
    if not pixels:
        return None
    first = bpy.data.images.get(f"{base}_{next(iter(pixels))}")
    w, h = first.size
    specs = [B.LayerSpec(
        map_id=L.map_id, uid=getattr(L, 'uid', ''), enabled=L.enabled, blend_mode=L.blend_mode,
        opacity=L.opacity, contrast=L.contrast, gamma=L.gamma,
        influence_target=L.influence_target,
        influence_amount=L.influence_amount,
        alpha_source=getattr(L, 'alpha_source', ''),
        alpha_invert=getattr(L, 'alpha_invert', False),
        as_decal=getattr(L, 'as_decal', False),
        decal_threshold=getattr(L, 'decal_threshold', 0.5),
        decal_softness=getattr(L, 'decal_softness', 0.25),
        decal_invert=getattr(L, 'decal_invert', False))
        for L in s.gtatools_bake_layers]
    # srgb=True: композит считается в линейном, на выходе кодируется в sRGB
    # для sRGB-байтовой картинки (совпадает с нодовым превью и с игрой).
    arr = B.composite_layers(pixels, specs, w, h, srgb=True)
    out = B.setup_target_image(out_name, w, h, transient=False)
    # RGB и альфа независимы (без premultiply) — cutout-текстура не темнеет.
    # Ставим ТОЛЬКО при отличии: смена alpha_mode — colormanage-сигнал, Blender
    # сбрасывает буфер и перечитывает картинку из packed-данных, отменяя
    # ресайз из setup_target_image (старая 2048² при новом бейке 1024² →
    # foreach_set «expected 16777216, got 4194304»). На первый раз, когда
    # режим реально меняется, страхует проверка размера в write_numpy_to_image.
    try:
        if out.alpha_mode != 'CHANNEL_PACKED':
            out.alpha_mode = 'CHANNEL_PACKED'
    except Exception:                                 # noqa: BLE001
        pass
    B.write_numpy_to_image(out, arr, pack=True)
    return out


def _layer_to_spec(B, L):
    """LayerSpec из INUBakeLayer (все поля, включая alpha/decal)."""
    return B.LayerSpec(
        map_id=L.map_id, uid=getattr(L, 'uid', ''), enabled=True, blend_mode=L.blend_mode,
        opacity=L.opacity, contrast=L.contrast, gamma=L.gamma,
        influence_target=L.influence_target,
        influence_amount=L.influence_amount,
        alpha_source=getattr(L, 'alpha_source', ''),
        alpha_invert=getattr(L, 'alpha_invert', False),
        as_decal=getattr(L, 'as_decal', False),
        decal_threshold=getattr(L, 'decal_threshold', 0.5),
        decal_softness=getattr(L, 'decal_softness', 0.25),
        decal_invert=getattr(L, 'decal_invert', False))


def _single_layer_composite_image(s, base, layer, out_name):
    """Свести ОДИН слой-провайдер альфы (as_decal / ALPHA) в RGBA-картинку:
    RGB как при общем сведении (без др. слоёв = чёрный), alpha = декаль/маска.
    out_name — ВРЕМЕННОЕ имя (не перезаписывает сырую <base>_<map>).
    Возвращает временную image (transient) или None."""
    from ..tools import bake as B
    pixels = {}
    lk = _lkey(layer)
    own = bpy.data.images.get(f"{base}_{lk}")
    if own is not None:
        arr0 = B.read_image_to_numpy(own)
        pixels[lk] = arr0
        pixels.setdefault(layer.map_id, arr0)
    extra = set()
    src = getattr(layer, 'alpha_source', '')
    if src and src != 'MATERIAL':
        extra.add(src)
    if layer.map_id == 'ALPHA':
        extra.add('ALPHA')
    for mid in extra:
        if mid in pixels:
            continue
        img = _alpha_src_img(s, base, mid)
        if img is not None:
            pixels[mid] = B.read_image_to_numpy(img)
    if not pixels:
        return None
    first = own or bpy.data.images.get(f"{base}_{next(iter(pixels))}")
    w, h = first.size
    arr = B.composite_layers(pixels, [_layer_to_spec(B, layer)], w, h, srgb=True)
    out = B.setup_target_image(out_name, w, h, transient=True)
    B.write_numpy_to_image(out, arr, pack=True)
    return out


def _find_base_tex(mat):
    """(image, uv_name) базовой Image Texture материала — для показа
    «база × запечённое». Идёт от Base Color (через Prelight_Mix.A, если есть),
    иначе первая image-нода. uv_name — из связанной UVMap-ноды (иначе '')."""
    if not mat or not mat.use_nodes:
        return None, ''
    from ..tools import compat
    nodes = mat.node_tree.nodes
    tex = None
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is not None and bsdf.inputs['Base Color'].links:
        src = bsdf.inputs['Base Color'].links[0].from_node
        if src is not None and src.name == 'Prelight_Mix':
            a = compat.mix_input_a(src)
            if a is not None and a.is_linked:
                src = a.links[0].from_node
        if src is not None and src.type == 'TEX_IMAGE':
            tex = src
    if tex is None:
        tex = next((n for n in nodes
                    if n.type == 'TEX_IMAGE' and getattr(n, 'image', None)), None)
    if tex is None:
        return None, ''
    uv = ''
    if tex.inputs['Vector'].links:
        vn = tex.inputs['Vector'].links[0].from_node
        if vn is not None and vn.type == 'UVMAP':
            uv = vn.uv_map
    return tex.image, uv


def _build_overlay_preview_mat(base_img, base_uv, comp_img, over_uv, key):
    """Preview-материал: flat-эмиссия (базовая текстура через её UV) × (запечённый
    композит через UV2). Отдельный материал на слот (`key`) — у каждого своя
    база. Без базовой текстуры → показываем только композит."""
    from ..tools import compat
    name = f"INU_BakeOver_{key}"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_fake_user = False
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    emit = nt.nodes.new('ShaderNodeEmission')

    base_out = None
    if base_img is not None:
        bt = nt.nodes.new('ShaderNodeTexImage')
        bt.image = base_img
        if base_uv:
            bu = nt.nodes.new('ShaderNodeUVMap')
            bu.uv_map = base_uv
            nt.links.new(bu.outputs['UV'], bt.inputs['Vector'])
        base_out = bt.outputs['Color']

    ct = nt.nodes.new('ShaderNodeTexImage')
    ct.image = comp_img
    if over_uv:
        cu = nt.nodes.new('ShaderNodeUVMap')
        cu.uv_map = over_uv
        nt.links.new(cu.outputs['UV'], ct.inputs['Vector'])

    if base_out is not None:
        mix = compat.make_mix_rgba(nt.nodes, blend='MULTIPLY', label='bake_over')
        mix.factor.default_value = 1.0
        nt.links.new(base_out, mix.a)
        nt.links.new(ct.outputs['Color'], mix.b)
        color_out = mix.result
    else:
        color_out = ct.outputs['Color']
    nt.links.new(color_out, emit.inputs['Color'])
    nt.links.new(emit.outputs['Emission'], out.inputs['Surface'])
    return m


def rebuild_live_composite(obj):
    """Пересобрать живое превью при правке слоёв (контраст/гамма/opacity/
    blend) — мгновенное обновление. Работает для трёх видов превью:
      * over-base — пересчитываем композит-картинку <base>_OVER (per-слот
        overlay-материалы ссылаются на неё → обновляются сами);
      * lightmap — живой композит БЕЗ prelight, через lm-UV;
      * обычный композит — живой композит БЕЗ prelight (как и первичный показ
        _apply_result_material с vcol=None). In-game вид (×prelight) даёт
        отдельная «Показать поверх базы»."""
    if not (obj and obj.get("inu_bake_preview_on", 0)):
        return
    s = obj.inu           # стек слоёв теперь на объекте (per-model)
    base = obj.get("inu_bake_base", "")
    # over-base: пересчёт свёрнутого композита (numpy применяет cg/opacity).
    if obj.get("inu_bake_overbase_on", 0):
        _composite_stack_image(s, base, f"{base}_OVER")
        return
    if not obj.get("inu_bake_mode_live", 0):
        return
    from ..tools.bake import bake_nodes
    is_lm = obj.get("inu_bake_preview_kind", "") == "lightmap"
    # RAW: живой композит — БЕЗ ×prelight. Иначе переключение слоя добавляло бы
    # умножение на вертекс-цвет прилайта («Day») и модель темнела, хотя первичный
    # показ (_apply_result_material) строит композит без прилайта. Совпадаем с ним.
    vcol = None
    uv = ((obj.get("inu_bake_lm_uv", "") or obj.get("inu_bake_uv", ""))
          if is_lm else obj.get("inu_bake_uv", ""))
    bake_nodes.build_composite_material(_layer_specs(s), base, uv, vcol)


def _ensure_paint_image(name, w, h):
    """Картинка слоя «Рисование»: если её нет — создаём БЕЛУЮ RGBA (белый =
    no-op для blend MULTIPLY, пока не нарисуешь тёмное). Существующую не
    трогаем (неразрушающе к уже нарисованному)."""
    img = bpy.data.images.get(name)
    if img is not None:
        return img
    img = bpy.data.images.new(name, width=int(w), height=int(h), alpha=True)
    try:
        import numpy as np
        from ..tools import bake as B
        B.write_numpy_to_image(
            img, np.ones((int(h), int(w), 4), dtype='float32'), pack=True)
    except Exception:                                 # noqa: BLE001
        try:
            img.generated_color = (1.0, 1.0, 1.0, 1.0)
            img.pack()
        except Exception:                             # noqa: BLE001
            pass
    return img


class GTATOOLS_OT_bake_paint_layer(bpy.types.Operator):
    """Рисовать по картинке слоя кистью (Texture Paint, Material-mode) — WYSIWYG:
    живой композит обновляется по мазкам. Работает по любой запечённой карте
    ИЛИ по слою «Рисование». Выход — Tab (назад в Object Mode)."""
    bl_idname = "gtatools.bake_paint_layer"
    bl_label = "Рисовать"
    bl_options = {'REGISTER'}

    uid: StringProperty(default="")
    map_id: StringProperty(default="")

    def execute(self, context):
        from ..tools.bake import bake_nodes
        obj = context.active_object
        s = context.scene.inu_settings
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, T("Выделите меш-объект"))
            return {'CANCELLED'}
        blo = obj.inu
        base = obj.get("inu_bake_base", "") or _derive_texture_name(obj, s)
        uv = obj.get("inu_bake_uv", "") or (
            obj.data.uv_layers.active.name if obj.data.uv_layers.active else "")
        # найти слой по ключу (uid) или map_id
        L = None
        for _L in blo.gtatools_bake_layers:
            if ((self.uid and _lkey(_L) == self.uid)
                    or (not self.uid and _L.map_id == self.map_id)):
                L = _L
                break
        if L is None:
            self.report({'ERROR'}, T("Слой не найден"))
            return {'CANCELLED'}
        key = _lkey(L)
        img = bpy.data.images.get(f"{base}_{key}")
        if img is None:
            if L.map_id == 'PAINT':
                img = _ensure_paint_image(f"{base}_{key}",
                                          s.gtatools_bake_res_x,
                                          s.gtatools_bake_res_y)
                obj["inu_bake_base"] = base
                obj["inu_bake_uv"] = uv
            else:
                self.report({'ERROR'},
                            T("Слой ещё не запечён — сначала «Запечь»"))
                return {'CANCELLED'}
        # слой должен быть включён — иначе его нет в живом композите
        if not L.enabled:
            L.enabled = True
        # показать живой композит (mode_live), чтобы мазки были видны сразу
        obj["inu_bake_mode_live"] = 1
        _apply_result_material(obj)
        # активировать image-ноду этой картинки → она станет paint-слотом
        mat = bpy.data.materials.get(bake_nodes.COMPOSITE_MAT)
        if mat is not None and mat.use_nodes:
            for n in mat.node_tree.nodes:
                if getattr(n, 'type', '') == 'TEX_IMAGE' and n.image is img:
                    mat.node_tree.nodes.active = n
                    break
        # активная UV = UV запекания (проекция кисти)
        if uv:
            uvl = obj.data.uv_layers.get(uv)
            if uvl is not None:
                uvl.active = True
        try:
            for o in context.view_layer.objects:
                try:
                    o.select_set(o is obj)
                except Exception:                     # noqa: BLE001
                    pass
            context.view_layer.objects.active = obj
            if obj.mode != 'TEXTURE_PAINT':
                bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
            context.scene.tool_settings.image_paint.mode = 'MATERIAL'
        except Exception as e:                        # noqa: BLE001
            self.report({'ERROR'},
                        T("Не удалось войти в режим рисования: {0}").format(e))
            return {'CANCELLED'}
        # 2D: показать картинку в Image-редакторе, если он открыт
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                try:
                    area.spaces.active.image = img
                except Exception:                     # noqa: BLE001
                    pass
                break
        self.report({'INFO'},
                    T("Рисуй по слою «{0}». Выход — Tab").format(L.map_id))
        return {'FINISHED'}


class GTATOOLS_OT_bake_run(bpy.types.Operator):
    """Запечь карты активного объекта в свои картинки и собрать живой
    нодовый композит. Свет для карт генерируется самой подсистемой —
    внешние источники сцены не нужны. only_map_id — запечь только одну
    карту (per-layer Bake)."""
    bl_idname = "gtatools.bake_run"
    bl_label = "Запечь"
    bl_options = {'REGISTER', 'UNDO'}

    only_map_id: StringProperty(
        name="", default="",
        description="Запечь только эту карту (пусто = все включённые слои)")
    only_uid: StringProperty(
        name="", default="",
        description="Запечь только слой с этим ключом (uid|map_id) — для "
                    "per-layer «Запечь», чтобы не затрагивать другие слои той "
                    "же карты")

    # Состояние модального прогона (создаётся в invoke).
    _timer = None
    _gen = None

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    # ── Драйверы генератора _bake_iter ──────────────────────────────────
    def execute(self, context):
        """Синхронный путь (скрипты / без окна): прокрутить генератор до конца.
        Итог операции лежит в StopIteration.value."""
        gen = self._bake_iter(context)
        try:
            while True:
                next(gen)
        except StopIteration as e:
            return e.value or {'FINISHED'}

    def invoke(self, context, event):
        """UI-путь: печём по карте за тик таймера — Blender не виснет на всю
        пачку, виден прогресс, работает ESC-отмена."""
        self._gen = self._bake_iter(context)
        wm = context.window_manager
        wm.progress_begin(0, 100)
        try:
            context.workspace.status_text_set(T("Запекание…"))
        except Exception:                             # noqa: BLE001
            pass
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC' and event.value == 'PRESS':
            self.report({'WARNING'}, T("Запекание отменено"))
            return self._end(context, {'CANCELLED'}, cancelled=True)
        if event.type != 'TIMER':
            # Захватываем ввод, чтобы во время бейка ничего не сломало
            # состояние (изоляция/материалы). Перерисовка при этом идёт.
            return {'RUNNING_MODAL'}
        wm = context.window_manager
        try:
            done, total, label = next(self._gen)
        except StopIteration as e:
            return self._end(context, e.value or {'FINISHED'})
        except Exception as e:                        # noqa: BLE001
            self.report({'ERROR'}, T("Ошибка запекания: ") + str(e))
            return self._end(context, {'CANCELLED'}, cancelled=True)
        try:
            wm.progress_update(int(100 * done / max(1, total)))
            context.workspace.status_text_set(
                T("Запекание {0}/{1}: {2}").format(done, total, label))
        except Exception:                             # noqa: BLE001
            pass
        return {'RUNNING_MODAL'}

    def _end(self, context, retval, cancelled=False):
        """Снять таймер/прогресс/статус; при отмене — закрыть генератор, что
        раскрутит его finally (изоляция/прилайт/временная копия вернутся)."""
        wm = context.window_manager
        if cancelled and self._gen is not None:
            try:
                self._gen.close()
            except Exception:                         # noqa: BLE001
                pass
        if self._timer is not None:
            try:
                wm.event_timer_remove(self._timer)
            except Exception:                         # noqa: BLE001
                pass
            self._timer = None
        try:
            wm.progress_end()
        except Exception:                             # noqa: BLE001
            pass
        try:
            context.workspace.status_text_set(None)
        except Exception:                             # noqa: BLE001
            pass
        self._gen = None
        return retval

    def _bake_iter(self, context):
        """ГЕНЕРАТОР запекания: печёт по одной карте за итерацию и `yield`-ит
        (готово, всего, имя_карты) — драйвер (модальный или синхронный)
        крутит его, показывая прогресс. Кадр генератора держит открытым
        `with BakeStateGuard`, изоляцию и `finally`, поэтому отмена через
        gen.close() корректно раскручивает всё восстановление. `return {…}`
        внутри уходит в StopIteration.value — итог операции."""
        from ..tools import bake as B

        scene = context.scene
        s = scene.inu_settings
        obj = context.active_object

        # ── Валидация ──
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, T("Выделите меш-объект"))
            return {'CANCELLED'}
        if not B.cycles_available(scene):
            self.report({'ERROR'}, T("Cycles недоступен — включите аддон Cycles"))
            return {'CANCELLED'}
        blo = obj.inu            # стек слоёв запекания — per-model, на объекте
        layers = [L for L in blo.gtatools_bake_layers if L.enabled]
        if not self.only_map_id and not self.only_uid and not layers:
            self.report({'ERROR'}, T("Добавьте хотя бы один слой карты"))
            return {'CANCELLED'}

        res_x = int(s.gtatools_bake_res_x)
        res_y = int(s.gtatools_bake_res_y)
        margin = int(s.gtatools_bake_margin)
        composite = True            # ноды строятся всегда
        scene_samples = int(s.gtatools_bake_samples)
        params = {
            'bevel_size': float(s.gtatools_bake_bevel_size),
            'bevel_samples': int(s.gtatools_bake_bevel_samples),
            # Bevel только по выделенным РЁБРАМ: маска-вертекс-атрибут по
            # вершинам выделенных рёбер, домножается на маску кромок.
            'bevel_selected_edges': bool(
                getattr(s, 'gtatools_bake_selected_edges', False)),
            'light_energy_scale': float(s.gtatools_bake_light_energy_scale),
            # ВКЛ → Shadow/Diffuse-Lit печём от реального света сцены (без
            # внутреннего рига и изоляции); ВЫКЛ → внутренний SUN/DOME.
            'use_scene_light': bool(s.gtatools_bake_use_scene_light),
        }

        if obj.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass

        # ── Режим: что и куда печём ──
        # bpy.ops.object.bake обрабатывает ВЫДЕЛЕННЫЕ объекты и падает, если
        # среди них скрытый из рендера — поэтому ниже аккуратно выставляем
        # выделение под каждый режим.
        s2a = False
        cage = 0.0
        mray = 0.0
        keep = ()
        is_camera = False
        render_obj = obj
        cam_axis = s.gtatools_bake_cam_axis
        cam_padding = float(s.gtatools_bake_cam_padding)
        cam_orient_normal = None
        cam_keep_uv = False
        if s.gtatools_bake_mode == 'CAMERA':
            # Рендерим детальный объект ортокамерой; результат кладём на
            # billboard-плоскость. Если есть пара _hi/_low — рендерим high,
            # а камеру ориентируем ПО НОРМАЛИ low-плоскости и потом
            # перепроецируем её UV из этой же камеры → текстура ложится
            # точь-в-точь. Иначе рендерим сам объект по мировой оси.
            high, low = B.find_hilow_pair(obj, B.HI_SUFFIX, B.LOW_SUFFIX)
            if high is not None and low is not None:
                render_obj = high
                bake_obj = low
                cam_orient_normal = B.plane_normal_world(low)
            else:
                render_obj = obj
                bake_obj = obj
            is_camera = True
            cam_keep_uv = bool(getattr(s, 'gtatools_bake_cam_keep_uv', False))
            if cam_keep_uv:
                # Проекция уйдёт в отдельный слой INU_BakeUV; активная (твоя)
                # UV не трогается. Результат сэмплится через INU_BakeUV.
                target_uv = "INU_BakeUV"
            else:
                target_uv = (bake_obj.data.uv_layers.active.name
                             if (bake_obj.data.uv_layers
                                 and bake_obj.data.uv_layers.active) else "")
            for o in context.view_layer.objects:
                try:
                    o.select_set(o is bake_obj)
                except Exception:
                    pass
            context.view_layer.objects.active = bake_obj
        elif s.gtatools_bake_mode == 'HILOW':
            high, low = B.find_hilow_pair(obj, B.HI_SUFFIX, B.LOW_SUFFIX,
                                          dff_lod_fallback=True)
            if high is None or low is None:
                self.report(
                    {'ERROR'},
                    T("У выделенной модели нет пары: "
                      "name_hi/name_low или GTA DFF/LOD (name_dff/name_lod)"))
                return {'CANCELLED'}
            if not low.data.uv_layers or not low.data.uv_layers.active:
                self.report({'ERROR'}, T("У лоуполи нет UV-развёртки"))
                return {'CANCELLED'}
            bake_obj = low
            target_uv = None              # печём в активную UV лоуполи
            s2a = True
            cage = float(s.gtatools_bake_cage_extrusion)
            mray = float(s.gtatools_bake_max_ray)
            keep = (high,)
            for o in context.view_layer.objects:
                try:
                    o.select_set(o is high or o is low)
                except Exception:
                    pass
            context.view_layer.objects.active = low
        else:  # UV → UV
            if not obj.data.uv_layers or len(obj.data.uv_layers) == 0:
                self.report({'ERROR'}, T("У объекта нет UV-развёртки для запекания"))
                return {'CANCELLED'}
            bake_obj = obj
            # Цель = ВЫДЕЛЕННАЯ UV (uv_layers.active); источник = рендер-UV
            # (active_render) — определяется автоматически в bake_one_map.
            # Все карты (вкл. LightMap) печём в эту одну UV.
            target_uv = (obj.data.uv_layers.active.name
                         if obj.data.uv_layers.active else None)
            for o in context.view_layer.objects:
                try:
                    o.select_set(o is obj)
                except Exception:
                    pass
            context.view_layer.objects.active = obj

        # Имя выходной текстуры — из имени модели (без префиксов/суффиксов).
        result_name = _derive_texture_name(bake_obj, s)

        # Если превью включено — печём по ИСХОДНЫМ материалам (иначе запеклась
        # бы превью-эмиссия / чёрный композит). КРИТИЧНО восстановить ДО изоляции
        # выделенных граней ниже: временная копия дублирует материалы объекта, и
        # если сделать её при активном INU_BakeComposite — она унесёт его с
        # собой, а _restore_materials починит только оригинал → Diffuse на копии
        # запечётся чёрным. Превью с новой текстурой вернём в конце.
        was_preview = bool(bake_obj.get("inu_bake_preview_on", 0))
        if was_preview:
            _restore_materials(bake_obj)

        # «Только выделенные полигоны» (UV→UV): сам бейк-пасс идёт по ВРЕМЕННОЙ
        # копии с одними выделенными гранями (карта ложится лишь на них, и это
        # быстрее), а метадата/результат-материал остаются на ОРИГИНАЛЕ. Плюс
        # запоминаем эти грани за АКТИВНЫМ слоем — переключение слоя их вернёт.
        # «Только выделенные полигоны» задумана под Bevel — на обычных картах
        # (Diffuse/AO/Normal/LightMap) она давала бы чёрное вне выделения.
        # Поэтому изоляцию делаем ТОЛЬКО если в этом прогоне печётся Bevel.
        if self.only_uid:
            _bevel_run = any(_lkey(L) == self.only_uid and L.map_id == 'BEVEL'
                             for L in blo.gtatools_bake_layers)
        elif self.only_map_id:
            _bevel_run = (self.only_map_id == 'BEVEL')
        else:
            _bevel_run = any(L.map_id == 'BEVEL' for L in layers)

        _bake_src = bake_obj
        _sel_teardown = None
        if (not is_camera and s.gtatools_bake_mode == 'UV' and _bevel_run
                and getattr(s, 'gtatools_bake_selected_faces', False)):
            _sel_idx = _selected_face_indices(bake_obj)
            if _sel_idx:
                _li = blo.gtatools_bake_layers_index
                if 0 <= _li < len(blo.gtatools_bake_layers):
                    _save_layer_faces(bake_obj,
                                      blo.gtatools_bake_layers[_li].uid, _sel_idx)
                _tmp, _sel_teardown = _isolate_selected_faces(context, bake_obj)
                if _tmp is not None:
                    _bake_src = _tmp
                    for _o in context.view_layer.objects:
                        try:
                            _o.select_set(_o is _tmp)
                        except Exception:         # noqa: BLE001
                            pass
                    context.view_layer.objects.active = _tmp

        # Список СЛОЁВ для запекания. Каждый слой печём в свою картинку
        # <base>_<key> (key = uid|map_id) → два слоя одной карты (напр. две
        # Bevel) НЕ затирают друг друга. Дедуп по ключу: один и тот же слой,
        # встречающийся в стеке несколько раз с разными blend, печём ОДИН раз.
        if self.only_uid:
            bake_targets = [L for L in blo.gtatools_bake_layers
                            if _lkey(L) == self.only_uid
                            and B.get_map(L.map_id) is not None]
        elif self.only_map_id:
            bake_targets = [L for L in blo.gtatools_bake_layers
                            if L.map_id == self.only_map_id
                            and B.get_map(L.map_id) is not None][:1]
        else:
            bake_targets, _seen_key = [], set()
            for L in layers:
                k = _lkey(L)
                if k not in _seen_key and B.get_map(L.map_id) is not None:
                    _seen_key.add(k)
                    bake_targets.append(L)
        if not bake_targets:
            self.report({'ERROR'}, T("Нет валидных карт"))
            return {'CANCELLED'}
        # Набор map_id среди запекаемых — для проверок «есть ли LIGHTMAP».
        baked_mids = {L.map_id for L in bake_targets}

        _LM_QUALITY_SAMPLES = {'PREVIEW': 32, 'MEDIUM': 128,
                               'HIGH': 512, 'PRODUCTION': 1024}

        def _samples_for(md):
            # LightMap — пресет качества (или свой ползунок при 'CUSTOM').
            if md.id == 'LIGHTMAP':
                q = s.gtatools_bake_lightmap_quality
                base = _LM_QUALITY_SAMPLES.get(
                    q, int(s.gtatools_bake_lightmap_samples))
                return max(1, base // (aa * aa))
            # Bevel — нода Bevel стохастическая (случайная нормаль на сэмпл),
            # поэтому EMIT-запёк шумит и его надо гасить сэмплами Cycles, а не
            # только лучами ноды. Берём max(ползунок Samples, «Bevel samples»),
            # БЕЗ деления на aa² — Bevel печётся без суперсэмплинга (map_aa=1).
            if md.id == 'BEVEL':
                return max(1, int(scene_samples),
                           int(s.gtatools_bake_bevel_samples))
            # Thickness — inside-AO, стохастична: сэмплы из настроек, с учётом
            # ускорения AA (суперсэмплинг усредняет шум), как у AO.
            if md.id == 'THICKNESS':
                base = max(int(scene_samples), md.samples)
                return max(1, base // (aa * aa))
            # AO / светозависимые / непрямой GI (свет излучения) — шумные,
            # берут сэмплы из настроек. Остальные (плоский color/normal) — 1.
            if (md.bake_type == 'AO' or md.needs_light
                    or getattr(md, 'pass_indirect', False)):
                base = max(int(scene_samples), md.samples)
                # УСКОРЕНИЕ AA: суперсэмплинг сам усредняет шум (aa² текселей
                # → 1 пиксель ≈ ×aa² сэмплов). Поэтому при AA снижаем сэмплы
                # Cycles в aa² раз — чистота та же, а лучей суммарно столько
                # же, что без AA (т.е. AA почти «бесплатно» по времени).
                return max(1, base // (aa * aa))
            return None

        # (was_preview + _restore_materials перенесены ВЫШЕ, до изоляции
        #  выделенных граней — см. комментарий там.)

        # Сглаживание (AA) суперсэмплингом — как в TexTools: печём во
        # внутреннем aa×размер и ужимаем до целевого через img.scale().
        # Работает и на Diffuse (в отличие от сэмплов Cycles, которые
        # плоский color-пасс не сглаживают). margin тоже масштабируем.
        try:
            aa = int(getattr(s, 'gtatools_bake_aa', '1') or '1')
        except Exception:
            aa = 1
        aa = max(1, aa)
        # Потолок внутреннего разрешения 4096 — чтобы AA не раздувал
        # большие запекания (2048×4 = 8192) до неподъёмного по памяти.
        _AA_CAP = 4096
        _m = max(res_x, res_y)
        while aa > 1 and _m * aa > _AA_CAP:
            aa //= 2
        bw, bh = res_x * aa, res_y * aa

        baked = 0
        result_img = None
        # «Учитывать PreLight»: на время бейка ставим превью прилайта на
        # ИСТОЧНИК цвета (hi→low: хайполи; камера: рендер-объект; UV: объект) —
        # Diffuse сэмплит его Base Color. Вьюпорт-коррекцию (яркость/контраст/
        # гамма/насыщенность) НЕЙТРАЛИЗУЕМ: она только для превью, в текстуру
        # попадать не должна. Галка выкл = чистая текстура без прилайта.
        _pl_restore = []
        _pl_touched = False
        try:
            from ..tools.prelight import (setup_prelight_preview as _spp,
                                          _set_view_correction_values)
            _use_pl = bool(getattr(s, 'gtatools_bake_use_prelight', False))
            if s.gtatools_bake_mode == 'HILOW':
                _pl_src = [o for o in keep if getattr(o, 'type', None) == 'MESH']
            elif is_camera:
                _pl_src = [render_obj] if render_obj else []
            else:
                _pl_src = [bake_obj]
            for _o in _pl_src:
                _on = any(ms.material and ms.material.use_nodes
                          and ms.material.node_tree.nodes.get("Prelight_Mix")
                          for ms in _o.material_slots)
                if _on != _use_pl:
                    _spp(_o, enable=_use_pl)
                    _pl_restore.append((_o, _on))
                if _use_pl:
                    for ms in _o.material_slots:
                        mat = ms.material
                        nt = mat.node_tree if (mat and mat.use_nodes) else None
                        if nt is None:
                            continue
                        bc = nt.nodes.get("Prelight_ViewBC")
                        gm = nt.nodes.get("Prelight_ViewGamma")
                        sat = nt.nodes.get("Prelight_ViewSat")
                        if bc and gm and sat:
                            _set_view_correction_values(bc, gm, sat, 0.0, 0.0, 1.0, 1.0)
                            _pl_touched = True
        except Exception:                     # noqa: BLE001
            pass
        # Диагностика (галка «Профайлер»): печатаем в системную консоль
        # состояние источника и статистику каждой запечённой картинки —
        # чтобы отличить «чёрная сама запечка» от «композит читает не то».
        _dbg = bool(getattr(s, 'gtatools_profile_enabled', False))

        def _img_stats(image):
            try:
                a = B.read_image_to_numpy(image)      # (h, w, ch) float32
                mn = [round(float(a[..., c].min()), 4) for c in range(a.shape[2])]
                mx = [round(float(a[..., c].max()), 4) for c in range(a.shape[2])]
                av = [round(float(a[..., c].mean()), 4) for c in range(a.shape[2])]
                return f"size={a.shape[1]}x{a.shape[0]} min={mn} max={mx} mean={av}"
            except Exception as _e:                   # noqa: BLE001
                return "stats-fail: " + str(_e)

        if _dbg:
            try:
                print("[INU bake] === старт ===")
                print("[INU bake] источник:", getattr(_bake_src, 'name', '?'),
                      "| режим:", s.gtatools_bake_mode,
                      "| камера:", is_camera)
                print("[INU bake] материалы источника:",
                      [ms.material.name if ms.material else "<пусто>"
                       for ms in _bake_src.material_slots])
                _uvs = [(u.name, u.active, u.active_render)
                        for u in _bake_src.data.uv_layers]
                print("[INU bake] UV (имя,active,active_render):", _uvs,
                      "| target_uv:", target_uv)
                print("[INU bake] слои-карты:", [_lkey(L) for L in layers])
            except Exception as _e:                   # noqa: BLE001
                print("[INU bake] дамп источника упал:", _e)

        # Изоляция объекта: на время бейка прячем прочие МЕШ-объекты сцены
        # (лампы/пустышки не трогаем — иначе сломается «Свет от сцены»),
        # кроме цели, hi-поли (keep) и временной копии выделенных граней.
        # Чинит чёрный AO (соседи по сцене больше не затеняют) и ускоряет
        # бейк (BVH только по цели). Камеру не трогаем — у неё свой рендер.
        _isolate = bool(getattr(s, 'gtatools_bake_isolate', True)) and not is_camera
        _iso_hidden = []
        try:
            with B.BakeStateGuard(context):
                if _isolate:
                    _keep_iso = {bake_obj, _bake_src} | set(keep)
                    for _o in context.scene.objects:
                        if (_o.type == 'MESH' and _o not in _keep_iso
                                and not _o.hide_render):
                            _iso_hidden.append(_o)
                            _o.hide_render = True
                # Каждую карту печём в свою картинку <base>_<map> — это
                # источники и для живого нодового стека, и для «Свести».
                for L in bake_targets:
                    mid = L.map_id
                    key = _lkey(L)
                    md = B.get_map(mid)
                    # Слой «Рисование» не печётся — только гарантируем его
                    # картинку (белую), уже нарисованное НЕ трогаем.
                    if mid == 'PAINT':
                        _ensure_paint_image(f"{result_name}_{key}", res_x, res_y)
                        baked += 1
                        yield (baked, len(bake_targets), mid)
                        continue
                    # AA (super-sampling) per-map. Bevel сэмплит лучи вокруг
                    # КАЖДОГО пикселя и уже сам сглаживает (bevel.samples), так
                    # что super-sampling ему не нужен — а он множит стоимость в
                    # aa² раз (при AA 4× это 16×) и вешает бейк на сложных
                    # моделях. Печём Bevel БЕЗ AA, в целевом разрешении.
                    map_aa = 1 if mid == 'BEVEL' else aa
                    mbw, mbh = res_x * map_aa, res_y * map_aa
                    # Печём в супер-разрешение mbw×mbh (при map_aa=1 = целевое).
                    img = B.setup_target_image(
                        f"{result_name}_{key}", mbw, mbh, transient=False)
                    if mid == 'ALPHA':
                        # Альфа — сырые данные: Non-Color, чтобы sRGB-гамма
                        # не искажала маску (значение 1:1 в альфа-канал).
                        try:
                            img.colorspace_settings.name = 'Non-Color'
                        except Exception:
                            pass
                    if is_camera:
                        # Камера: рендер ортокамерой. samples повышаем —
                        # нужны для сглаживания alpha-краёв листвы.
                        B.render_one_map_camera(
                            context, md, render_obj, img, params=params,
                            samples=max(scene_samples, 16),
                            axis=cam_axis, padding=cam_padding,
                            orient_normal=cam_orient_normal,
                            frame_obj=(bake_obj if cam_orient_normal is not None
                                       else None))
                    else:
                        # Режим света LightMap: Combined / только Indirect /
                        # только Direct → переопределяем пассы (color всегда
                        # off — карта это множитель освещения без альбедо).
                        _pass = None
                        if mid == 'LIGHTMAP':
                            _lm = s.gtatools_bake_lightmap_light_mode
                            _pass = {'INDIRECT': (False, True, False),
                                     'DIRECT': (True, False, False)}.get(
                                         _lm, (True, True, False))
                        B.bake_one_map(context, md, _bake_src, img, margin=margin * map_aa,
                                       params=params, samples=_samples_for(md),
                                       target_uv=target_uv, selected_to_active=s2a,
                                       cage_extrusion=cage, max_ray=mray,
                                       keep_visible=keep, pass_overrides=_pass)
                    # Ужать супер-разрешение до целевого (фильтрованное
                    # уменьшение Blender) — это и даёт сглаживание.
                    if map_aa > 1:
                        try:
                            img.scale(res_x, res_y)
                        except Exception:
                            pass
                    # Денойз ЛЮБОЙ шумной карты (AO / Shadow / Diffuse Lit /
                    # Emission GI / LightMap / Bevel) на финальном размере.
                    # denoise_image по контракту не бросает (graceful False).
                    # Feature-пассы (albedo/normal) — только для LightMap.
                    _noisy = (md.bake_type == 'AO' or md.needs_light
                              or getattr(md, 'pass_indirect', False)
                              or mid in ('BEVEL', 'THICKNESS'))
                    if _noisy and s.gtatools_bake_denoise:
                        _alb = _nrm = None
                        if (mid == 'LIGHTMAP'
                                and s.gtatools_bake_lightmap_denoise_passes):
                            _alb = _alpha_src_img(blo, result_name, 'DIFFUSE')
                            _nrm = _alpha_src_img(blo, result_name, 'NORMAL')
                        B.denoise_image(img, context, albedo=_alb, normal=_nrm)
                    # LightMap: сохранить сырой результат (post-denoise) в
                    # <base>_LIGHTMAP_raw и применить пост-обработку (интенсивность
                    # + смягчение) → <base>_LIGHTMAP. Raw нужен, чтобы менять
                    # интенсивность/фильтр БЕЗ пере-GI (кнопка «Пост-обработка»).
                    if mid == 'LIGHTMAP':
                        _stash_lightmap_raw(img)
                        _apply_lightmap_postprocess(s, img)
                    # Normal с включённым «Обесцветить» — сводим запечённую
                    # карту в серое сразу (как при сведении нормал-мапы в
                    # Фотошопе), убирая синий tangent-space оттенок.
                    if mid == 'NORMAL' and any(
                            L.enabled and L.map_id == 'NORMAL'
                            and getattr(L, 'desaturate', False)
                            for L in blo.gtatools_bake_layers):
                        from ..scene_settings import _desaturate_image_inplace
                        _desaturate_image_inplace(img)
                    # Непрозрачный фон (галка «Прозрачный фон» снята, дефолт):
                    # фон вне развёртки заливаем СРЕДНИМ цветом запечённых
                    # (покрытых) пикселей и ставим альфу 1 → текстура сплошная,
                    # без черноты на швах/мипах. Пропускаем ALPHA/декали (там
                    # альфа значима) и камеру-billboard (альфа = вырез листвы).
                    if (not getattr(s, 'gtatools_bake_transparent_bg', False)
                            and not is_camera and mid != 'ALPHA'
                            and not getattr(L, 'as_decal', False)):
                        try:
                            _a = B.read_image_to_numpy(img)
                            if _a.shape[2] >= 4:
                                _cov = _a[..., 3] > 0.5      # покрытые пиксели
                                if _cov.any():
                                    _avg = _a[..., :3][_cov].mean(axis=0)
                                    _a[..., :3][~_cov] = _avg
                                _a[..., 3] = 1.0
                                B.write_numpy_to_image(img, _a, pack=False)
                        except Exception:             # noqa: BLE001
                            pass
                    try:
                        img.pack()
                    except Exception:
                        pass
                    img.update()
                    if _dbg:
                        print(f"[INU bake] карта {mid}: {img.name} |",
                              _img_stats(img))
                    # ALPHA — не «результат» (это альфа-канал, не RGB-картинка).
                    if mid == 'DIFFUSE' or (result_img is None and mid != 'ALPHA'):
                        result_img = img
                    baked += 1
                    # Уступить управление драйверу: карта готова → обновить
                    # прогресс, дать Blender перерисоваться (модальный путь).
                    yield (baked, len(bake_targets), mid)
        except RuntimeError as e:
            self.report({'ERROR'}, T("Ошибка запекания: ") + str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, T("Ошибка: ") + str(e))
            return {'CANCELLED'}
        finally:
            # Снять изоляцию — вернуть спрятанным мешам render-видимость.
            for _o in _iso_hidden:
                try:
                    _o.hide_render = False
                except Exception:             # noqa: BLE001
                    pass
            # Вернуть прилайт-состояние источника и значения вьюпорт-коррекции.
            try:
                from ..tools.prelight import (setup_prelight_preview as _spp,
                                              apply_prelight_view_correction)
                for _o, _was in _pl_restore:
                    _spp(_o, enable=_was)
                if _pl_touched:
                    apply_prelight_view_correction(context.scene)
            except Exception:                 # noqa: BLE001
                pass
            # Убрать временную копию «только выделенные» и вернуть оригинал
            # активным/выделенным.
            if _sel_teardown is not None:
                _sel_teardown()
                try:
                    for _o in context.view_layer.objects:
                        _o.select_set(_o is bake_obj)
                    context.view_layer.objects.active = bake_obj
                except Exception:             # noqa: BLE001
                    pass

        # Камера + billboard: перепроецируем UV плоскости из того же
        # ракурса, что снимала камера — текстура ложится точь-в-точь
        # (0..1, без зеркала/поворота), независимо от исходной развёртки.
        if is_camera and cam_orient_normal is not None:
            try:
                B.reproject_billboard_uv(
                    bake_obj, cam_orient_normal, padding=cam_padding,
                    uv_name=("INU_BakeUV" if cam_keep_uv else None))
            except Exception:
                pass

        # Метаданные для нод / превью / сведения.
        baked_uv = target_uv or (bake_obj.data.uv_layers.active.name
                                 if bake_obj.data.uv_layers.active else "")
        bake_obj["inu_bake_base"] = result_name
        bake_obj["inu_bake_uv"] = baked_uv
        # UV, в которую запечён LIGHTMAP (= общая цель) — для «Применить»
        # (сэмплинг в prelight) и превью.
        if 'LIGHTMAP' in baked_mids:
            bake_obj["inu_bake_lm_uv"] = baked_uv

        # Сброс вида превью — иначе _apply_result_material после прошлой
        # lightmap-запечки ошибочно показал бы старый лайтмап. Нужный вид
        # выставит соответствующая ветка ниже.
        bake_obj["inu_bake_preview_kind"] = ""

        if is_camera:
            # Billboard: финальный СТАНДАРТНЫЙ материал — Principled +
            # запечённая текстура, альфа из неё (clip). Лишних
            # композит/эмиссия-нод нет.
            bake_obj["inu_bake_mode_live"] = 0
            bake_obj["inu_bake_image"] = result_img.name if result_img else ""
            _apply_standard_material(bake_obj, result_img, baked_uv)
            msg = T("Запечено камерой (стандартный материал)")
        elif 'LIGHTMAP' in baked_mids:
            # LightMap всегда сразу показываем на модели (живой композит без
            # prelight) — без кнопки. Не нужно — снять «Скрыть текстуру».
            _apply_lightmap_preview(bake_obj)
            msg = T("LightMap запечён — превью на модели")
        elif composite:
            bake_obj["inu_bake_mode_live"] = 1
            bake_obj["inu_bake_image"] = ""
            # Живой нодовый материал на модель — крутишь opacity/blend сразу.
            _apply_result_material(bake_obj)
            msg = T("Live-композит собран: ") + str(baked) + T(" карт")
        else:
            # Показать diffuse-карту в Image-редакторе.
            if result_img is not None:
                _show_image(context, result_img)
            if was_preview:           # вернуть превью с обновлённой картинкой
                _apply_result_material(bake_obj)
            msg = T("Запечено карт: ") + str(baked)

        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_bake_layer_add(bpy.types.Operator):
    """Добавить слой карты в стек запекания"""
    bl_idname = "gtatools.bake_layer_add"
    bl_label = "Добавить слой"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import uuid
        from ..tools.bake import BAKE_MAPS, get_map
        s = context.scene.inu_settings
        blo = _bl_owner(context)
        if blo is None:
            self.report({'ERROR'}, T("Выделите модель"))
            return {'CANCELLED'}
        layer = blo.gtatools_bake_layers.add()    # добавляется в конец
        layer.uid = uuid.uuid4().hex[:16]         # ключ памяти полигонов слоя
        # Карта берётся из формы «Добавить слой» (gtatools_bake_new_map);
        # fallback на первую карту реестра, если значение почему-то пустое.
        chosen = get_map(s.gtatools_bake_new_map) or next(iter(BAKE_MAPS.values()), None)
        if chosen is not None:
            layer.map_id = chosen.id
            layer.blend_mode = chosen.default_blend
            layer.opacity = chosen.default_opacity
            # Normal Map по умолчанию обесцвечиваем — иначе её синий
            # tangent-space оттенок проступает на итоговой текстуре.
            if chosen.id == 'NORMAL':
                layer.desaturate = True
        # Список сверху-вниз → новый слой должен быть СВЕРХУ (index 0).
        last = len(blo.gtatools_bake_layers) - 1
        if last > 0:
            blo.gtatools_bake_layers.move(last, 0)
        blo.gtatools_bake_layers_index = 0
        rebuild_live_composite(context.active_object)
        return {'FINISHED'}


class GTATOOLS_OT_bake_layer_remove(bpy.types.Operator):
    """Удалить слой из стека запекания"""
    bl_idname = "gtatools.bake_layer_remove"
    bl_label = "Удалить слой"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(
        default=-1, description="Индекс слоя (-1 = выбранный)")

    def execute(self, context):
        blo = _bl_owner(context)
        if blo is None:
            return {'CANCELLED'}
        n = len(blo.gtatools_bake_layers)
        i = self.index if self.index >= 0 else blo.gtatools_bake_layers_index
        if 0 <= i < n:
            blo.gtatools_bake_layers.remove(i)
            # Выбранный слой держим на том же логическом (сдвиг при удалении выше).
            ai = blo.gtatools_bake_layers_index
            if ai > i:
                ai -= 1
            blo.gtatools_bake_layers_index = max(
                0, min(ai, len(blo.gtatools_bake_layers) - 1))
        rebuild_live_composite(context.active_object)
        return {'FINISHED'}


class GTATOOLS_OT_bake_layer_move(bpy.types.Operator):
    """Переместить слой вверх/вниз в стеке (порядок = порядок смешивания)"""
    bl_idname = "gtatools.bake_layer_move"
    bl_label = "Переместить слой"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        items=[('UP', "Up", ""), ('DOWN', "Down", "")], default='UP')
    index: IntProperty(
        default=-1, description="Индекс слоя (-1 = выбранный)")

    def execute(self, context):
        blo = _bl_owner(context)
        if blo is None:
            return {'CANCELLED'}
        n = len(blo.gtatools_bake_layers)
        i = self.index if self.index >= 0 else blo.gtatools_bake_layers_index
        j = i - 1 if self.direction == 'UP' else i + 1
        if 0 <= i < n and 0 <= j < n:
            blo.gtatools_bake_layers.move(i, j)
            blo.gtatools_bake_layers_index = j
        rebuild_live_composite(context.active_object)
        return {'FINISHED'}


class GTATOOLS_OT_bake_preview(bpy.types.Operator):
    """Показать/скрыть запечённую текстуру прямо на модели (flat-эмиссия,
    видно при любом освещении). Для UV→UV переключает отображение на UV, в
    которую запекали; для hi→low просто показывает на лоуполи. Повторный
    клик возвращает исходные материалы и рендер-UV.

    Исходные материалы/UV хранятся в custom-props объекта (переживают
    перезагрузку аддона и сохранение .blend)."""
    bl_idname = "gtatools.bake_preview"
    bl_label = "Показать текстуру"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and bool(obj.get("inu_bake_base")))

    def execute(self, context):
        obj = context.active_object
        if bool(obj.get("inu_bake_preview_on", 0)):
            _restore_materials(obj)
            self.report({'INFO'}, T("Превью выключено"))
            return {'FINISHED'}
        if _apply_result_material(obj) is None:
            self.report({'ERROR'},
                        T("Нет запечённого результата — сначала запеките"))
            return {'CANCELLED'}
        self.report({'INFO'}, T("Превью включено"))
        return {'FINISHED'}


class GTATOOLS_OT_bake_flatten(bpy.types.Operator):
    """Свести стек слоёв (per-map картинки <base>_<map>) в ОДНУ текстуру
    <base> numpy-композитом и сохранить её в файл («Сохранить как»)."""
    bl_idname = "gtatools.bake_flatten"
    bl_label = "Сохранить как"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.png;*.tga;*.bmp", options={'HIDDEN'})
    # Размер при сохранении: печём в высоком (чисто), а в файл можно
    # сохранить уменьшенным — аккуратное усреднение соседних пикселей даёт
    # чистый результат без алиасинг-полос (лучше, чем печь сразу в мелкое).
    save_scale: EnumProperty(
        name="Размер",
        description="Во сколько раз уменьшить текстуру при сохранении",
        items=[('1', "Оригинал", "Полный запечённый размер"),
               ('2', "½",        "В 2 раза меньше"),
               ('4', "¼",        "В 4 раза меньше"),
               ('8', "⅛",        "В 8 раз меньше")],
        default='1')

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and bool(obj.get("inu_bake_base")))

    def _src_size(self, context):
        """Размер запечённой текстуры (первой включённой карты), или None."""
        obj = context.active_object
        base = obj.get("inu_bake_base", "") if obj else ""
        if not base:
            return None
        for L in obj.inu.gtatools_bake_layers:
            img = bpy.data.images.get(f"{base}_{_lkey(L)}") if L.enabled else None
            if img is not None:
                return tuple(img.size)
        return None

    def draw(self, context):
        layout = self.layout
        layout.label(text=T("Размер при сохранении:"))
        layout.prop(self, "save_scale", expand=True)
        sz = self._src_size(context)
        if sz:
            f = int(self.save_scale)
            layout.label(text=f"{sz[0] // f} × {sz[1] // f} px")

    def _flatten(self, context):
        """Свести стек в одну картинку <base>. Возвращает image или None."""
        obj = context.active_object
        base = obj.get("inu_bake_base", "")
        final = _composite_stack_image(obj.inu, base, base)
        if final is not None:
            _show_image(context, final)
        return final

    def invoke(self, context, event):
        # Сначала убедимся, что есть что сводить; путь по умолчанию = <base>.png.
        obj = context.active_object
        base = obj.get("inu_bake_base", "") if obj else ""
        if obj is None or not _stack_has_bakeable(obj.inu, base):
            self.report({'ERROR'}, T("Нет запечённых карт для сведения"))
            return {'CANCELLED'}
        if not self.filepath:
            self.filepath = (base or "inu_bake") + ".png"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def _downscaled_copy(self, img, f):
        """Вернуть временную копию `img`, уменьшенную в `f` раз box-усреднением
        (среднее блока f×f → чистое уменьшение без алиасинга). Кратность f
        обеспечиваем обрезкой до f·(размер//f); остаток (обычно 0 для
        степеней двойки) отбрасывается."""
        import numpy as np
        from ..tools import bake as B
        w, h = img.size
        nw, nh = max(1, w // f), max(1, h // f)
        arr = B.read_image_to_numpy(img)            # (h, w, ch) float32
        ch = arr.shape[2]
        arr = arr[:nh * f, :nw * f]
        small = arr.reshape(nh, f, nw, f, ch).mean(axis=(1, 3))
        tmp = bpy.data.images.new(img.name + f"__x{f}", nw, nh,
                                  alpha=(ch >= 4), float_buffer=False)
        tmp.use_fake_user = False
        B.write_numpy_to_image(tmp, small, pack=False)
        return tmp

    def execute(self, context):
        final = self._flatten(context)
        if final is None:
            self.report({'ERROR'}, T("Нет запечённых карт для сведения"))
            return {'CANCELLED'}
        f = int(self.save_scale)
        save_img = final
        tmp = None
        if f > 1:
            try:
                save_img = tmp = self._downscaled_copy(final, f)
            except Exception as e:
                self.report({'ERROR'}, T("Не удалось уменьшить: ") + str(e))
                return {'CANCELLED'}
        try:
            # CHANNEL_PACKED: RGB и альфа НЕЗАВИСИМЫ — Blender не домножает RGB
            # на альфу (premultiply) при сохранении. Иначе полупрозрачные зоны
            # (cutout-силуэт) темнели и вся текстура «уходила в полуальфу».
            try:
                save_img.alpha_mode = 'CHANNEL_PACKED'
            except Exception:                         # noqa: BLE001
                pass
            save_img.filepath_raw = self.filepath
            save_img.file_format = 'PNG'
            save_img.save()
        except Exception as e:
            self.report({'ERROR'}, T("Не удалось сохранить: ") + str(e))
            return {'CANCELLED'}
        finally:
            if tmp is not None:
                try:
                    bpy.data.images.remove(tmp)
                except Exception:
                    pass
        self.report({'INFO'}, T("Сохранено: ") + self.filepath)
        return {'FINISHED'}


class GTATOOLS_OT_bake_save_map(bpy.types.Operator):
    """Сохранить картинку выбранной карты (<base>_<map>) в файл. Для слоя с
    «Декаль» (или карты ALPHA) сохраняет RGBA с вычисленной
    альфой — как в общем сведении, но для одной карты."""
    bl_idname = "gtatools.bake_save_map"
    bl_label = "Сохранить карту"

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.png;*.tga;*.bmp", options={'HIDDEN'})
    # ВНУТРЕННЕЕ: какую запечённую карту брать (DIFFUSE/NORMAL/…). Скрыто из
    # диалога — проставляется автоматически от карты/слоя, юзеру не нужно.
    map_id: StringProperty(
        default="", description="Какую карту сохранить (пусто = выбранный слой)",
        options={'HIDDEN'})
    # ВНУТРЕННЕЕ: ключ конкретного слоя (uid|map_id) — чтобы при нескольких
    # слоях одной карты (напр. две Bevel) сохранить именно свой, а не первый.
    uid: StringProperty(default="", options={'HIDDEN'})
    # Суффикс имени файла — что дописать к имени модели. Правится вручную.
    name_suffix: StringProperty(
        name=T("Суффикс имени"),
        default="_DEFAULT",
        description=T("Что дописать к имени модели в имени файла. Например "
                      "'_DEFAULT' → grozdom97_DEFAULT.png. Меняй под свою "
                      "текстуру в TXD"))
    # Размер при сохранении — как в «Сохранить все»: печём в высоком, а в файл
    # можно уменьшить box-усреднением (чисто, без алиасинга).
    save_scale: EnumProperty(
        name="Размер",
        description=T("Во сколько раз уменьшить текстуру при сохранении"),
        items=[('1', "Оригинал", "Полный запечённый размер"),
               ('2', "½",        "В 2 раза меньше"),
               ('4', "¼",        "В 4 раза меньше"),
               ('8', "⅛",        "В 8 раз меньше")],
        default='1')

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and bool(obj.get("inu_bake_base")))

    def _downscaled_copy(self, img, f):
        """Временная копия img, уменьшенная в f раз box-усреднением (среднее
        блока f×f). Копия обычной save-all; см. её коммент."""
        import numpy as np
        from ..tools import bake as B
        w, h = img.size
        nw, nh = max(1, w // f), max(1, h // f)
        arr = B.read_image_to_numpy(img)
        ch = arr.shape[2]
        arr = arr[:nh * f, :nw * f]
        small = arr.reshape(nh, f, nw, f, ch).mean(axis=(1, 3))
        tmp = bpy.data.images.new(img.name + f"__x{f}", nw, nh,
                                  alpha=(ch >= 4), float_buffer=False)
        tmp.use_fake_user = False
        B.write_numpy_to_image(tmp, small, pack=False)
        return tmp

    def _write(self, img):
        """Сохранить img в self.filepath, уменьшив по save_scale. Возвращает
        True/False; временную уменьшенную копию убирает сам."""
        f = int(self.save_scale)
        save_img, tmp = img, None
        if f > 1:
            try:
                save_img = tmp = self._downscaled_copy(img, f)
            except Exception as e:                # noqa: BLE001
                self.report({'ERROR'}, T("Не удалось уменьшить: ") + str(e))
                return False
        ok = True
        try:
            # CHANNEL_PACKED — не премультиплаить RGB на альфу при сохранении
            # (иначе cutout-текстура выходит полупрозрачной/тёмной).
            try:
                save_img.alpha_mode = 'CHANNEL_PACKED'
            except Exception:                         # noqa: BLE001
                pass
            save_img.filepath_raw = self.filepath
            save_img.file_format = 'PNG'
            save_img.save()
        except Exception as e:                    # noqa: BLE001
            self.report({'ERROR'}, T("Не удалось сохранить: ") + str(e))
            ok = False
        finally:
            if tmp is not None:
                try:
                    bpy.data.images.remove(tmp)
                except Exception:                 # noqa: BLE001
                    pass
        return ok

    def _layer(self, context):
        """Слой, чью карту сохраняем: по uid (конкретный слой), иначе по map_id
        (первый включённый с этой картой), иначе выбранный в списке."""
        blo = _bl_owner(context)
        if blo is None:
            return None
        if self.uid:
            for L in blo.gtatools_bake_layers:
                if _lkey(L) == self.uid:
                    return L
        if self.map_id:
            cand = [L for L in blo.gtatools_bake_layers if L.map_id == self.map_id]
            for L in cand:
                if L.enabled:
                    return L
            return cand[0] if cand else None
        i = blo.gtatools_bake_layers_index
        if 0 <= i < len(blo.gtatools_bake_layers):
            return blo.gtatools_bake_layers[i]
        return None

    def _image(self, context):
        obj = context.active_object
        base = obj.get("inu_bake_base", "") if obj else ""
        if not base:
            return None
        L = self._layer(context)
        if L is not None:
            im = bpy.data.images.get(f"{base}_{_lkey(L)}")
            if im is not None:
                return im
        mid = self.map_id or (L.map_id if L else "")
        if not mid:
            return None
        return bpy.data.images.get(f"{base}_{mid}")

    @staticmethod
    def _is_provider(L):
        return L is not None and (getattr(L, 'as_decal', False)
                                  or L.map_id == 'ALPHA')

    def _provider_source_img(self, context, L):
        """Запечённая карта-источник для слоя-провайдера (as_decal → сама
        карта; ALPHA → alpha_source или <base>_ALPHA)."""
        obj = context.active_object
        base = obj.get("inu_bake_base", "") if obj else ""
        if not base or L is None:
            return None
        if getattr(L, 'as_decal', False):
            # Декаль: сама запечённая карта слоя (свой per-layer ключ).
            return bpy.data.images.get(f"{base}_{_lkey(L)}")
        src = getattr(L, 'alpha_source', '') or 'MATERIAL'
        if src == 'MATERIAL':
            src = 'ALPHA'
        return _alpha_src_img(obj.inu, base, src)

    def invoke(self, context, event):
        L = self._layer(context)
        img = self._image(context)
        provider = self._is_provider(L)
        if img is None and not (provider
                                and self._provider_source_img(context, L) is not None):
            self.report({'ERROR'}, T("Эта карта ещё не запечена"))
            return {'CANCELLED'}
        if not self.filepath:
            self.filepath = self._compose_name(context)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def _base_name(self, context):
        ao = context.active_object
        return (ao.get("inu_bake_base", "") if ao else "") or "texture"

    def _compose_name(self, context):
        """Имя файла = <модель><суффикс>.png в текущей папке диалога."""
        fname = f"{self._base_name(context)}{self.name_suffix or ''}.png"
        d = os.path.dirname(self.filepath) if self.filepath else ""
        return os.path.join(d, fname) if d else fname

    def check(self, context):
        # Живая синхронизация: меняешь суффикс в сайдбаре → имя файла обновляется.
        new = self._compose_name(context)
        if new != self.filepath:
            self.filepath = new
            return True
        return False

    def draw(self, context):
        layout = self.layout
        # В сайдбаре — поле суффикса (map_id скрыт) + размер при сохранении.
        layout.prop(self, "name_suffix")
        layout.separator()
        layout.label(text=T("Размер при сохранении:"))
        layout.prop(self, "save_scale", expand=True)
        img = self._image(context)
        if img is not None:
            f = int(self.save_scale)
            layout.label(text=f"{img.size[0] // f} × {img.size[1] // f} px")

    def execute(self, context):
        L = self._layer(context)
        base = context.active_object.get("inu_bake_base", "")
        # Слой-провайдер (декаль / ALPHA): сохраняем RGBA с вычисленной альфой.
        if self._is_provider(L):
            comp = _single_layer_composite_image(
                context.active_object.inu, base, L, f"{base}_{_lkey(L)}__save")
            if comp is not None:
                ok = self._write(comp)
                try:
                    bpy.data.images.remove(comp)
                except Exception:                 # noqa: BLE001
                    pass
                if not ok:
                    return {'CANCELLED'}
                self.report({'INFO'}, T("Сохранено: ") + self.filepath)
                return {'FINISHED'}
            # не собралось — падаем на сырое сохранение ниже
        img = self._image(context)
        if img is None:
            self.report({'ERROR'}, T("Нет картинки карты"))
            return {'CANCELLED'}
        if not self._write(img):
            return {'CANCELLED'}
        self.report({'INFO'}, T("Сохранено: ") + self.filepath)
        return {'FINISHED'}


def _show_image(context, img):
    """Показать `img` в Image-редакторе (если есть)."""
    try:
        sp = getattr(context, 'space_data', None)
        if sp is not None and getattr(sp, 'type', '') == 'IMAGE_EDITOR':
            sp.image = img
            return
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces.active.image = img
                return
    except Exception:
        pass


def _stash_lightmap_raw(img):
    """Сохранить сырой (post-denoise, ДО пост-обработки) LightMap в
    <картинка слоя>_raw — источник для пере-применения интенсивности/фильтра
    без пере-GI (кнопка «Пост-обработка»)."""
    from ..tools import bake as B
    w, h = img.size
    raw = B.setup_target_image(f"{img.name}_raw", w, h, transient=False)
    try:
        B.write_numpy_to_image(raw, B.read_image_to_numpy(img), pack=True)
    except Exception:
        pass


def _apply_lightmap_postprocess(s, target_img):
    """raw → смягчение (Gaussian) × интенсивность → target_img (картинка
    LightMap-слоя). Источник — <её имя>_raw (или сам target, если raw нет).
    Значения клампятся в [0,1] — GTA-текстуры LDR."""
    import numpy as np
    from ..tools import bake as B
    intensity = float(getattr(s, 'gtatools_bake_lightmap_intensity', 1.0))
    radius = float(getattr(s, 'gtatools_bake_lightmap_filter', 0.0))
    raw = bpy.data.images.get(f"{target_img.name}_raw")
    src = raw if raw is not None else target_img
    try:
        arr = B.read_image_to_numpy(src)     # приватный свежий буфер
    except Exception:
        return
    if radius > 0:
        arr = B.gaussian_blur(arr, radius)   # новый приватный массив
    if intensity != 1.0:
        ch = min(3, arr.shape[2])
        arr[..., :ch] = np.clip(arr[..., :ch] * intensity, 0.0, 1.0)
    if tuple(target_img.size) != (arr.shape[1], arr.shape[0]):
        try:
            target_img.scale(arr.shape[1], arr.shape[0])
        except Exception:
            pass
    B.write_numpy_to_image(target_img, arr, pack=True)
    target_img.update()


class GTATOOLS_OT_bake_lightmap_apply(bpy.types.Operator):
    """Применить запечённый LightMap выбранным способом
    (gtatools_bake_lightmap_apply): оставить слоем / впечь в диффуз /
    записать в vertex prelight «Day»."""
    bl_idname = "gtatools.bake_lightmap_apply"
    bl_label = "Применить LightMap"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            return False
        return _lightmap_image(obj) is not None

    def execute(self, context):
        s = context.scene.inu_settings
        obj = context.active_object
        base = obj.get("inu_bake_base", "")
        lm = _lightmap_image(obj)
        if lm is None:
            self.report({'ERROR'}, T("Сначала запеките слой LightMap"))
            return {'CANCELLED'}
        mode = s.gtatools_bake_lightmap_apply
        if mode == 'STACK':
            self.report({'INFO'},
                        T("LightMap — слой в стеке. Сведите «Сохранить как»"))
            return {'FINISHED'}
        if mode == 'DIFFUSE':
            return self._apply_diffuse(context, obj, base, lm)
        if mode == 'PRELIGHT':
            return self._apply_prelight(context, obj, base, lm)
        return {'CANCELLED'}

    # ── режим: впечь в diffuse ──
    def _apply_diffuse(self, context, obj, base, lm):
        from ..tools import bake as B
        diff = _map_image(obj, 'DIFFUSE')
        if diff is None:
            self.report({'ERROR'},
                        T("Нет запечённого Diffuse — добавьте слой Diffuse и запеките"))
            return {'CANCELLED'}
        d = B.read_image_to_numpy(diff)
        l = B.read_image_to_numpy(lm)
        if d.shape[:2] != l.shape[:2]:
            self.report({'ERROR'},
                        T("Размеры Diffuse и LightMap не совпадают — печатайте в одном размере"))
            return {'CANCELLED'}
        # In-place: d — приватный свежий буфер из read_image_to_numpy,
        # альфа не трогается (лишняя полная копия — до 256 МБ на 4096²).
        ch = min(3, d.shape[2], l.shape[2])
        d[..., :ch] *= l[..., :ch]                     # diffuse × освещение
        w, h = diff.size
        final = B.setup_target_image(base, w, h, transient=False)
        B.write_numpy_to_image(final, d, pack=True)
        _show_image(context, final)
        self.report({'INFO'}, T("LightMap впечён в диффуз: ") + final.name)
        return {'FINISHED'}

    # ── режим: в vertex prelight ──
    def _apply_prelight(self, context, obj, base, lm):
        import numpy as np
        from ..tools import bake as B
        from ..tools import vc_layers, compat
        me = obj.data
        # Сэмплим по UV, в которую запечён lightmap.
        uv_name = obj.get("inu_bake_lm_uv", "") or obj.get("inu_bake_uv", "")
        uvs = me.uv_layers
        uv = (uvs.get(uv_name) if uv_name else None) or uvs.active or (
            uvs[0] if len(uvs) else None)
        if uv is None:
            self.report({'ERROR'}, T("У объекта нет UV для сэмплинга LightMap"))
            return {'CANCELLED'}
        arr = B.read_image_to_numpy(lm)
        n = len(me.loops)
        uv_co = np.empty(n * 2, dtype=np.float32)
        uv.data.foreach_get('uv', uv_co)
        sampled = B.sample_image_uv_batch(arr, uv_co.reshape(n, 2))
        rgba = np.ones((n, 4), dtype=np.float32)
        c = min(3, sampled.shape[1])
        rgba[:, :c] = np.clip(sampled[:, :c], 0.0, 1.0)
        # Пишем в prelight-атрибут «Day» (CORNER / FLOAT_COLOR). Если он есть,
        # но не CORNER-домена — пересоздаём (наш массив пер-лупный).
        attr = me.color_attributes.get(vc_layers.BASE_DAY_NAME)
        if attr is not None and getattr(attr, 'domain', 'CORNER') != 'CORNER':
            try:
                me.color_attributes.remove(attr)
            except Exception:
                pass
            attr = None
        if attr is None:
            attr = compat.vcol_new(me, vc_layers.BASE_DAY_NAME,
                                   domain='CORNER', dtype='FLOAT_COLOR')
        if attr is None:
            self.report({'ERROR'}, T("Не удалось создать prelight-атрибут «Day»"))
            return {'CANCELLED'}
        vc_layers._write_array_to_color_attr(attr, rgba)
        # «Day» сделать активным цветовым атрибутом — чтобы превью прилайта и
        # экспорт брали именно его.
        try:
            me.color_attributes.active_color = attr
        except Exception:
            pass
        # VC-Layers: при включённом Live Preview «Day» — сводка стека
        # (backup + слои), и следующий recompose/экспорт затёр бы записанный
        # lightmap восстановлением из старого backup. Делаем lightmap НОВОЙ
        # базой: обновляем backup-снапшот и пересобираем стек (слои лягут
        # поверх). Без LP запись в Day — уже база, трогать нечего.
        try:
            if vc_layers._is_live_preview_on(me):
                vc_layers._backup_base_attr(
                    me, vc_layers.BASE_DAY_NAME,
                    vc_layers._backup_prop_for_scope('DAY'))
                vc_layers.recompose_stack(me, 'DAY')
        except Exception:
            pass
        me.update()
        # Показать результат: снять bake-эмиссия-превью (иначе оно перекрывает
        # модель) и включить превью прилайта — тогда записанный «Day» виден.
        if obj.get("inu_bake_preview_on", 0):
            _restore_materials(obj)
        try:
            from ..tools.prelight import setup_prelight_preview
            setup_prelight_preview(obj, enable=True)
        except Exception:
            pass
        self.report({'INFO'},
                    T("LightMap записан в prelight «Day» — превью прилайта включено"))
        return {'FINISHED'}

class GTATOOLS_OT_bake_lightmap_postprocess(bpy.types.Operator):
    """Применить Интенсивность и Смягчение к запечённому LightMap — быстро,
    без повторной запечки. Крутишь ползунки → жмёшь → результат обновился."""
    bl_idname = "gtatools.bake_lightmap_postprocess"
    bl_label = "Обновить лайтмап"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            return False
        return _lightmap_image(obj) is not None

    def execute(self, context):
        s = context.scene.inu_settings
        obj = context.active_object
        target = _lightmap_image(obj)
        if target is None:
            self.report({'ERROR'}, T("Сначала запеките слой LightMap"))
            return {'CANCELLED'}
        _apply_lightmap_postprocess(s, target)
        # Обновить активное превью: обычный/лайтмап-композит подхватит новую
        # картинку сам (тот же датаблок), а over-base показывает отдельную
        # свёрнутую <base>_OVER — её надо пересчитать.
        rebuild_live_composite(obj)
        self.report({'INFO'}, T("Лайтмап обновлён"))
        return {'FINISHED'}


class GTATOOLS_OT_bake_show_over_base(bpy.types.Operator):
    """Показать финальный вид на модели: базовая текстура (через свою UV1) ×
    запечённый композит стека (через UV запекания, UV2). Как в игре с двумя
    UV-каналами.

    Строит per-слот preview-материал: TexUV1 (база) × TexUV2 (композит) →
    эмиссия. Композит запечённых карт сводится в <base>_OVER. Базовая
    текстура и её UV берутся из ИСХОДНОГО материала каждого слота. Снять —
    кнопкой «Скрыть текстуру» (возврат исходных материалов)."""
    bl_idname = "gtatools.bake_show_over_base"
    bl_label = "Показать поверх базы (UV2)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and bool(obj.get("inu_bake_base")))

    def execute(self, context):
        s = context.scene.inu_settings
        obj = context.active_object
        base = obj.get("inu_bake_base", "")
        # ТОГГЛ: если over-base уже показан — выключаем, но возвращаемся к
        # ОБЫЧНОМУ превью (композит/лайтмап), а не к голым материалам —
        # «Показать текстуру» остаётся включённым.
        if (obj.get("inu_bake_preview_on", 0)
                and obj.get("inu_bake_overbase_on", 0)):
            obj["inu_bake_overbase_on"] = 0
            if _apply_result_material(obj) is None:
                _restore_materials(obj)          # нет результата — просто снять
            else:
                # подчистить осиротевшие per-слот over-base материалы
                for _m in [mm for mm in bpy.data.materials
                           if mm.name.startswith("INU_BakeOver_")
                           and mm.users == 0]:
                    try:
                        bpy.data.materials.remove(_m)
                    except Exception:
                        pass
            self.report({'INFO'}, T("Показ поверх UV1 выключен"))
            return {'FINISHED'}
        # UV2 = UV, в которую запечён стек (inu_bake_uv). fallback — 2-й/1-й слой.
        over_uv = obj.get("inu_bake_uv", "")
        uvs = getattr(obj.data, 'uv_layers', None)
        if not over_uv and uvs and len(uvs):
            over_uv = (uvs[1].name if len(uvs) >= 2 else uvs[0].name)
        # Свести стек в один композит (UV2-раскладка).
        comp = _composite_stack_image(obj.inu, base, f"{base}_OVER")
        if comp is None:
            self.report({'ERROR'}, T("Нет запечённых карт"))
            return {'CANCELLED'}
        # Исходные материалы должны быть в слотах (для чтения базовой текстуры):
        # если сейчас превью — сначала вернём оригиналы.
        if obj.get("inu_bake_preview_on", 0):
            _restore_materials(obj)
        slot_bases = [_find_base_tex(sl.material) for sl in obj.material_slots]
        _snapshot_materials(obj)
        uv1_fallback = uvs[0].name if (uvs and len(uvs)) else ''
        for i, sl in enumerate(obj.material_slots):
            b_img, b_uv = slot_bases[i] if i < len(slot_bases) else (None, '')
            if not b_uv:
                b_uv = uv1_fallback
            sl.material = _build_overlay_preview_mat(b_img, b_uv, comp, over_uv, i)
        # Отдельный флаг over-base: НЕ трогаем inu_bake_mode_live/preview_kind
        # (это состояние «обычного» результата) — иначе после выключения
        # over-base «Показать текстуру» терял бы, что показывать.
        obj["inu_bake_preview_on"] = 1
        obj["inu_bake_overbase_on"] = 1
        self.report({'INFO'},
                    T("Показано: база(UV1) × запечённое(UV2), UV2: ")
                    + (over_uv or "?"))
        return {'FINISHED'}
