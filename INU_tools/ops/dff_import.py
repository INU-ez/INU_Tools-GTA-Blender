# INU_tools.ops.dff_import
# DFF (RenderWare Clump) → Blender mesh objects.
# Uses INU_tools.core.dff for binary format reading.
#
# НЕ добавлять `from __future__ import annotations` — Blender читает
# `__annotations__` для регистрации `filepath: StringProperty(...)` и др.
# на Operator'ах. PEP 563 stringify ломает это → "property not found".

from typing import Optional

import math
import os
import bpy
import bmesh
import mathutils
import numpy as np

from .. import T
from ..tools import compat
from ..tools.compat import safe_icon, inu_icon
from bpy.props import (
    StringProperty, CollectionProperty,
)
from ..core.dff import (
    read_dff_file, DffClump, DffGeometry, DffMaterial, UserData,
    USERDATA_INT, USERDATA_FLOAT, USERDATA_STRING,
    Extension2dfx, Light2dfx, Particle2dfx, PedAttractor2dfx, SunGlare2dfx,
    EnterExit2dfx, RoadSign2dfx, Escalator2dfx, RawUnknown2dfx,
)


def _frame_name_usable(nm: str) -> bool:
    """True if a DFF frame name is a clean GTA-style name (keep it as-is).

    A ``?`` (literal byte 0x3F) or the Unicode replacement char means a
    previous tool/round-trip mangled the name — e.g.
    ``hedge_3_?_?_?_?_?_?_N__001``. In that case the caller falls back to the
    DFF *file* name instead of importing the junk into the outliner.

    We only reject those mangle markers (plus non-ASCII / control bytes) — NOT
    a strict alnum whitelist. GTA / VehFuncs frame names legitimately use ``:``
    and spaces (``f_extras:3``, ``extra_radio:1``, ``roof3:1``,
    ``Bip01 L Clavicle``); the old whitelist silently renamed them to
    ``<base>_frame_<idx>`` and broke VehFuncs / ped setups.
    """
    if not nm:
        return False
    if '?' in nm:
        return False
    return all(c.isascii() and c.isprintable() for c in nm)


def _is_light_frame_name(nm: str) -> bool:
    """True for an RW Light (RpLight) frame name — ``Omni###``.

    Kam's 3ds Max exporter (and our own DFF export) write one ``Omni<NNN>``
    frame per 2DFX light to carry the RW light source. These are light
    dummies, not real geometry frames, so map import skips them together
    with the 2DFX extension when «Без 2DFX» is on."""
    return (bool(nm) and len(nm) > 4
            and nm[:4].lower() == 'omni' and nm[4:].isdigit())


def _store_user_data(target, user_data: UserData):
    """Store UserData PLG into Blender custom properties.

    Saves as 'inu_user_data' — a list of dicts, each with
    'name', 'type' (int/float/str), and 'data' (list of values).
    """
    if not user_data or not user_data.sections:
        return

    type_names = {USERDATA_INT: 'int', USERDATA_FLOAT: 'float', USERDATA_STRING: 'str'}
    sections = []
    for sec in user_data.sections:
        sections.append({
            'name': sec.name,
            'type': type_names.get(sec.data_type, 'na'),
            'data': list(sec.data),
        })
    target['inu_user_data'] = sections


def _apply_uv_anim_to_material(mat, dff_mat: DffMaterial, uv_anim_dict):
    """Propagate clump UV anim (0x2B dict + 0x135 PLG names) into
    ``mat.inu.uv_anim_*`` so the writer's linear scroll can round-trip.

    Writer builds a 2-keyframe anim from ``speed_u/speed_v/duration`` —
    we invert that: first name wins, read ``duration`` from the anim,
    and derive speeds from ``kf1.trans / kf1.time``. More complex
    multi-keyframe anims flatten to the same speed/duration pair (we
    don't preserve intermediate keys yet; round-trip is lossy for
    hand-edited IFP but correct for addon-round-tripped files).
    """
    if not dff_mat.uv_anim_names or uv_anim_dict is None:
        return
    name = dff_mat.uv_anim_names[0]
    target = None
    for anim in uv_anim_dict.anims:
        if anim.name == name:
            target = anim
            break
    if target is None or not target.keyframes:
        return

    inu = getattr(mat, 'inu', None)
    if inu is None:
        return

    inu.uv_anim_write = True
    try:
        inu.animation_name = name
    except Exception:
        # animation_name may not exist on older addon builds —
        # fall back to material name matching implicitly.
        pass
    inu.uv_anim_duration = max(0.01, float(target.duration))

    # Linear-scroll inference: the writer encodes scroll speed as
    # (trans_u, trans_v) on the last keyframe at time = duration.
    last = target.keyframes[-1]
    dt = max(last.time, 1e-6)
    inu.uv_anim_speed_u = float(last.trans_u) / dt
    inu.uv_anim_speed_v = float(last.trans_v) / dt


# Кэш «есть ли у картинки прозрачные пиксели» — по имени картинки. При
# map-импорте одна текстура делится многими моделями, а чтение всех пикселей
# (1024²+) дорогое → проверяем каждую картинку один раз. Фильтр по каналу
# (depth==32) отсекает RGB-текстуры без чтения пикселей.
_IMG_ALPHA_CACHE = {}


def _image_has_transparency(image):
    """True, если у картинки есть реально прозрачные пиксели (вырезка листвы
    и т.п.). Кэшируется по имени; RGB-картинки без альфа-канала отсекаются."""
    if image is None:
        return False
    key = image.name
    cached = _IMG_ALPHA_CACHE.get(key)
    if cached is not None:
        return cached
    result = False
    try:
        if getattr(image, 'depth', 0) == 32:          # есть альфа-канал
            from ..tools.txd_export import check_image_has_transparent_pixels
            result = bool(check_image_has_transparent_pixels(image))
    except Exception:                                 # noqa: BLE001
        result = False
    _IMG_ALPHA_CACHE[key] = result
    return result


def _create_blender_material(dff_mat: DffMaterial, index: int,
                             material_cache: Optional[dict] = None,
                             uv_anim_dict=None) -> bpy.types.Material:
    """Создаём Blender материал из DFF материала.

    If ``material_cache`` (shared dict) is provided, materials without
    advanced effects (env_map / bump_map / specular / reflection /
    dual_texture / user_data) are deduplicated by (texture name, RGBA
    color) — massively cuts ``bpy.data.materials.new`` calls for a
    bulk map import where the same texture repeats across thousands
    of DFFs. Materials with advanced effects are always created fresh
    because each can carry per-model parameters.
    """
    tex_name = ""
    if dff_mat.texture and dff_mat.texture.name:
        tex_name = dff_mat.texture.name

    # Cache key combines everything that affects the material's
    # rendered appearance: texture, base RGBA, and a fingerprint of
    # each optional effect block. Two materials with the SAME texture +
    # SAME color + SAME effects collapse to one — that's the typical
    # vehicle case where 6 body panels all reference vehiclebody +
    # xvehicleenv128 with identical coefficients. Earlier code skipped
    # the cache whenever ANY effect was present, so vehicles ended up
    # with vehiclelights128.001/.002/.../.005 dupes.
    #
    # user_data is excluded from the key because it's metadata, not
    # appearance — two materials with same look but different user_data
    # should still dedupe (the user_data of the first wins).
    cache_key = None
    if material_cache is not None and tex_name:
        c = dff_mat.color
        em = dff_mat.env_map
        bm = dff_mat.bump_map
        sp = dff_mat.specular
        rf = dff_mat.reflection
        du = dff_mat.dual_texture
        cache_key = (
            tex_name, c.r, c.g, c.b, c.a,
            (em.coefficient, em.use_fb_alpha,
             em.texture.name if em.texture else "") if em else None,
            (bm.intensity,
             bm.bump_texture.name if bm.bump_texture else "",
             bm.height_texture.name if bm.height_texture else "")
            if bm else None,
            (sp.level, sp.name) if sp else None,
            (rf.scale_x, rf.scale_y, rf.offset_x, rf.offset_y,
             rf.intensity) if rf else None,
            (du.src_blend, du.dst_blend,
             du.texture.name if du.texture else "") if du else None,
        )
        cached = material_cache.get(cache_key)
        if cached is not None:
            return cached

    mat_name = tex_name if tex_name else f"Material_{index}"
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True

    # Сохраняем исходное имя текстуры в IDProp — Blender мог добавить .001/.002 к имени
    # материала при коллизии, а матчинг TXD→материал по имени в таком случае ломался.
    if tex_name:
        mat['dff_texture_name'] = tex_name

    tree = mat.node_tree
    nodes = tree.nodes

    # Получаем Principled BSDF
    bsdf = None
    for node in nodes:
        if node.type == 'BSDF_PRINCIPLED':
            bsdf = node
            break

    if bsdf is None:
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')

    # Устанавливаем цвет из DFF
    c = dff_mat.color
    bsdf.inputs['Base Color'].default_value = (c.r / 255.0, c.g / 255.0, c.b / 255.0, 1.0)

    # Solid-mode viewport colour (DragonFF-style). Base Color above only shows
    # in Material Preview / Rendered; Solid shading reads mat.diffuse_color, so
    # without this every part is the same default grey and the model "blends
    # together". Carry the DFF alpha too so glass shows through in Solid view
    # (Viewport Shading → Color → Material).
    mat.diffuse_color = (c.r / 255.0, c.g / 255.0, c.b / 255.0, c.a / 255.0)
    # Штамп импорта: с ним экспорт сравнивает diffuse_color и понимает, что
    # пользователь правил свотч «Цвет (RGBA)» в панели (см. _read_base_color
    # в dff_export). Точно те же float'ы, что ушли в diffuse_color.
    mat['inu_dff_color'] = (c.r / 255.0, c.g / 255.0, c.b / 255.0, c.a / 255.0)

    # Connect texture if available
    tex_node = None
    if tex_name:
        img = bpy.data.images.get(tex_name)
        if not img:
            # Try with common extensions
            for ext in ('.png', '.bmp', '.tga', '.dds', '.jpg'):
                img = bpy.data.images.get(tex_name + ext)
                if img:
                    break
        # Always create Image Texture node (for later cache loading)
        tex_node = nodes.new('ShaderNodeTexImage')
        tex_node.label = tex_name
        tex_node.location = (bsdf.location.x - 300, bsdf.location.y)
        tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
        if img:
            tex_node.image = img

    # Specular = 0 для GTA моделей
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.0
    elif 'Specular' in bsdf.inputs:
        bsdf.inputs['Specular'].default_value = 0.0

    # Альфа — подключать если материал прозрачный (альфа ЦВЕТА материала)
    # ИЛИ у ТЕКСТУРЫ есть реально прозрачные пиксели (вырезка: листва/забор/
    # стекло — цвет материала при этом обычно непрозрачный, c.a==255). Без
    # второго условия альфа-канал текстуры не подключался, и на экспорте
    # alpha_connected=False → вырезка терялась (TXD без альфы, модель сплошная).
    # Стандарт: Метод рендеринга Смешанный + Перекрытие прозрачности ВЫКЛ
    # (на 4.2+ blend_method сам по себе ничего не делает — см. compat).
    _tex_alpha = _image_has_transparency(tex_node.image) if tex_node else False
    if c.a < 255 or _tex_alpha:
        compat.make_material_alpha(mat)
        if c.a < 255:
            bsdf.inputs['Alpha'].default_value = c.a / 255.0
        # Connect texture alpha to shader alpha
        if tex_node:
            tree.links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])

    # Surface lighting coefficients (ambient/specular/diffuse) → INU свойства,
    # verbatim. ОБЯЗАТЕЛЬНО хранить specular+diffuse тоже: иначе экспорт берёт
    # их из Blender-входов (Roughness=0.5 → diffuse 0.5) и модель темнеет вдвое.
    if dff_mat.surface:
        mat.inu.ambient = dff_mat.surface.ambient
        mat.inu.surf_specular = dff_mat.surface.specular
        mat.inu.surf_diffuse = dff_mat.surface.diffuse
    else:
        mat.inu.ambient = 1.0

    # Texture filtering / addressing + mask → INU props (round-trip). Decode the
    # RW filterAddressing word: low byte = filter, nibbles 2-3 = U/V addressing,
    # high 16 bits kept verbatim. Guard out-of-range values to the defaults so a
    # malformed word can't raise on the enum assignment.
    if dff_mat.texture:
        _f = dff_mat.texture.filters
        mat.inu.tex_filter = str(_f & 0xFF) if (_f & 0xFF) <= 6 else '2'
        mat.inu.tex_addr_u = str((_f >> 8) & 0xF) if ((_f >> 8) & 0xF) <= 4 else '1'
        mat.inu.tex_addr_v = str((_f >> 12) & 0xF) if ((_f >> 12) & 0xF) <= 4 else '1'
        mat.inu.tex_filter_hi = (_f >> 16) & 0xFFFF
        mat.inu.mask_texture = dff_mat.texture.mask or ""
        mat.inu.texture_name = dff_mat.texture.name or ""

    # Material effects → INU свойства
    if dff_mat.env_map:
        mat.inu.export_env_map = True
        mat.inu.env_map_coef = dff_mat.env_map.coefficient
        mat.inu.env_map_fb_alpha = dff_mat.env_map.use_fb_alpha
        if dff_mat.env_map.texture:
            mat.inu.env_map_tex = dff_mat.env_map.texture.name

    if dff_mat.bump_map:
        mat.inu.export_bump_map = True
        if dff_mat.bump_map.bump_texture:
            mat.inu.bump_map_tex = dff_mat.bump_map.bump_texture.name

    if dff_mat.specular:
        mat.inu.export_specular = True
        mat.inu.specular_level = dff_mat.specular.level
        mat.inu.specular_texture = dff_mat.specular.name

    if dff_mat.reflection:
        mat.inu.export_reflection = True
        mat.inu.reflection_scale_x = dff_mat.reflection.scale_x
        mat.inu.reflection_scale_y = dff_mat.reflection.scale_y
        mat.inu.reflection_offset_x = dff_mat.reflection.offset_x
        mat.inu.reflection_offset_y = dff_mat.reflection.offset_y
        mat.inu.reflection_intensity = dff_mat.reflection.intensity

    if dff_mat.dual_texture:
        mat.inu.export_dual_tex = True
        mat.inu.dual_tex_src_blend = str(dff_mat.dual_texture.src_blend)
        mat.inu.dual_tex_dst_blend = str(dff_mat.dual_texture.dst_blend)
        if dff_mat.dual_texture.texture:
            mat.inu.dual_tex_texture = dff_mat.dual_texture.texture.name

    # User Data PLG
    if dff_mat.user_data:
        _store_user_data(mat, dff_mat.user_data)

    # UV animation — look up referenced anim names in the clump's dict
    # and populate mat.inu.uv_anim_* so the export writer round-trips.
    _apply_uv_anim_to_material(mat, dff_mat, uv_anim_dict)

    if cache_key is not None:
        material_cache[cache_key] = mat
    return mat


def _build_mesh_bmesh(mesh: bpy.types.Mesh, geom: DffGeometry):
    """Legacy bmesh-based mesh builder — used only as a fallback when the
    fast foreach_set path fails on malformed DFF geometry."""
    bm = bmesh.new()
    for v in geom.vertices:
        bm.verts.new((v[0], v[1], v[2]))
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()

    uv_layers = []
    for i in range(len(geom.uv_layers)):
        uv_name = "UVMap" if i == 0 else f"UVMap.{i:03d}"
        uv_layers.append(bm.loops.layers.uv.new(uv_name))

    vc_layer = bm.loops.layers.color.new("Day") if geom.prelit_colors else None
    nc_layer = (bm.loops.layers.color.new("Night")
                if geom.extra_colors and geom.extra_colors.colors else None)

    for tri in geom.triangles:
        try:
            face = bm.faces.new([bm.verts[tri.a], bm.verts[tri.b], bm.verts[tri.c]])
            face.material_index = tri.material
            if hasattr(face, 'smooth'):
                face.smooth = True
            for loop in face.loops:
                vi = loop.vert.index
                for uv_idx, uv_bl_layer in enumerate(uv_layers):
                    uv_data = geom.uv_layers[uv_idx]
                    if vi < len(uv_data):
                        tc = uv_data[vi]
                        loop[uv_bl_layer].uv = (tc.u, 1.0 - tc.v)
                if vc_layer and vi < len(geom.prelit_colors):
                    c = geom.prelit_colors[vi]
                    loop[vc_layer] = (c.r / 255.0, c.g / 255.0, c.b / 255.0, c.a / 255.0)
                if nc_layer and vi < len(geom.extra_colors.colors):
                    c = geom.extra_colors.colors[vi]
                    loop[nc_layer] = (c.r / 255.0, c.g / 255.0, c.b / 255.0, c.a / 255.0)
        except Exception as e:
            print(f"[INU_tools] Face error (bmesh fallback): {e}")

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _align_winding_to_normals(tri_np, verts_np, norm_np):
    """Развернуть намотку треугольников по авторским нормалям.

    Некоторые модели карты GTA SA содержат грани с обратной намоткой
    (winding): их геометрическая нормаль (из порядка вершин) смотрит в
    противоположную сторону от авторской нормали вершин. В Blender это
    даёт «вывернутые» грани (красные в Face Orientation) и ломает
    шейдинг — грань освещается с изнанки. Считаем для каждого
    треугольника геометрическую нормаль и сравниваем с усреднённой
    авторской; где они смотрят врозь (dot < 0) — меняем местами 2-ю и
    3-ю вершины, разворачивая намотку под авторскую нормаль. Custom
    split normals при этом не трогаются, так что шейдинг остаётся
    авторским, а намотка перестаёт конфликтовать.

    Возвращает (tri_np, flipped_count). Делается полностью на numpy,
    так что даже на карте в 1.5 млн полигонов проход дешёвый.
    """
    if norm_np is None or len(norm_np) != len(verts_np):
        return tri_np, 0
    v0 = verts_np[tri_np[:, 0]]
    v1 = verts_np[tri_np[:, 1]]
    v2 = verts_np[tri_np[:, 2]]
    geo_n = np.cross(v1 - v0, v2 - v0)
    auth_n = norm_np[tri_np[:, 0]] + norm_np[tri_np[:, 1]] + norm_np[tri_np[:, 2]]
    dots = np.einsum('ij,ij->i', geo_n, auth_n)
    flip = dots < 0.0
    n_flip = int(np.count_nonzero(flip))
    if n_flip:
        tri_np[flip, 1], tri_np[flip, 2] = (
            tri_np[flip, 2].copy(), tri_np[flip, 1].copy())
    return tri_np, n_flip


def _weld_and_sharpen(obj):
    """Объединить совпадающие вершины и сохранить жёсткое затенение (по
    мотивам DragonFF ``remove_object_doubles``, но EdgeSplit применяется
    СРАЗУ в меш, без модификатора).

    GTA-меши хранят раздельные вершины на стыках/швах (по грани), из-за чего
    модель распадается на несвязные острова и держит наложенные дубли.
    Помечаем граничные рёбра (с одной гранью) острыми ДО сварки, свариваем
    все совпадающие вершины (``remove_doubles`` dist=1e-5 — попутно убирает
    и совпавшие дубли-грани), затем РАЗРЕЗАЕМ острые рёбра прямо в геометрии
    (``split_edges``). Так получается связная манифолд-топология с жёсткими
    исходными рёбрами и БЕЗ модификатора — на импорте карты не копятся
    тысячи модификаторов EdgeSplit (FPS не страдает).

    Это ВАНИЛЬНЫЙ путь (галочка «Авто-острые рёбра» ВКЛ) — НЕ трогаем, работает
    как раньше. Кастомный импорт (галочка ВЫКЛ) сюда не заходит вообще."""
    me = obj.data
    if me is None or not len(me.vertices):
        return
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        # Граничные рёбра (одна грань) → острые, ДО сварки.
        for edge in bm.edges:
            if len(edge.link_loops) == 1:
                edge.smooth = False
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00001)
        # Разрезать острые рёбра в самой геометрии (аналог EdgeSplit без угла).
        sharp_edges = [e for e in bm.edges if not e.smooth]
        if sharp_edges:
            bmesh.ops.split_edges(bm, edges=sharp_edges)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


# Custom-model weld crease angle: below this the two welded faces are treated as
# one flat surface (join); above it they stay hard. Only used on the CUSTOM
# import path — the vanilla path never sees it.
_CUSTOM_SHARP_ANGLE = math.radians(30.0)


def _weld_custom(obj):
    """Weld for CUSTOM (non-vanilla) models. Kept SEPARATE from
    ``_weld_and_sharpen`` so it can NEVER affect vanilla import.

    Some tools export a DFF fully split — every triangle isolated, no vertex
    sharing at all — so it imports as loose polygons (e.g. KRC_Mir01: 61341
    verts / 20447 tris, only 12850 unique positions). This CONNECTS it:
      • merge coincident verts (remove_doubles), but
      • PROTECT double-sided faces (fences/hedges: two coincident polys, opposite
        winding) from the merge so they stay two-sided, and
      • split hard edges by ANGLE (open boundaries + creases > _CUSTOM_SHARP_ANGLE)
        — a fully-split DFF carries no smoothing flag, so angle is the only cue.
    Per-loop vertex colors survive the weld, so baked lighting is kept."""
    me = obj.data
    if me is None or not len(me.vertices):
        return
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        # Protect double-sided faces (fences) from the merge.
        from collections import defaultdict
        by_pos = defaultdict(list)
        for f in bm.faces:
            by_pos[frozenset((round(v.co.x, 4), round(v.co.y, 4),
                              round(v.co.z, 4)) for v in f.verts)].append(f)
        protected = set()
        for faces in by_pos.values():
            if len(faces) >= 2:
                for f in faces:
                    protected.update(f.verts)
        weld_verts = ([v for v in bm.verts if v not in protected]
                      if protected else bm.verts)

        bmesh.ops.remove_doubles(bm, verts=weld_verts, dist=0.00001)

        # Do NOT split the geometry — keep the mesh fully WELDED and editable
        # (a 90° corner stays ONE vertex you can move as a whole). Just FLAG
        # creases as sharp so they still SHADE hard; Blender honours sharp edges
        # when computing normals (4.1+) / with auto-smooth (pre-4.1).
        for edge in bm.edges:
            if len(edge.link_faces) == 2:
                try:
                    edge.smooth = edge.calc_face_angle() <= _CUSTOM_SHARP_ANGLE
                except ValueError:
                    edge.smooth = True
        bm.to_mesh(me)
    finally:
        bm.free()
    if hasattr(me, 'use_auto_smooth'):     # pre-4.1: needed for sharp edges
        me.use_auto_smooth = True
        try:
            me.auto_smooth_angle = math.pi  # rely on explicit sharp flags only
        except Exception:
            pass
    me.update()


def _weld_keep_normals(obj):
    """Merge coincident verts so a vehicle mesh is editable (connected) and keep
    its hard-edge shading — a port of DragonFF's ``remove_object_doubles``.

    GTA cars are split at every crease/seam, so before welding those edges have
    a single linked face (boundaries). We mark every such edge sharp FIRST, then
    merge by distance, then add an EdgeSplit modifier (sharp edges only, no
    angle) so the marked edges shade hard while the body stays smooth.

    ``bmesh.remove_doubles`` AVERAGES the custom split normals (the
    ``has_custom_normals`` layer survives but its values are recomputed) — on a
    GTA car that wrecks the baked panel shading and the re-export writes the
    smoothed normals → visible stains. To keep them exactly, we stash each
    loop's authored normal in a bmesh loop custom-data layer BEFORE the merge;
    bmesh carries that layer verbatim through ``remove_doubles`` (loops keep
    their own data — only vertices merge), so we read it back afterwards and
    re-apply it as the mesh's custom split normals. No position matching, no
    averaging."""
    me = obj.data
    if not me or not len(me.vertices):
        return
    had_custom = getattr(me, 'has_custom_normals', False)
    lno = None
    if had_custom:
        try:
            me.calc_normals_split()   # pre-4.1; 4.1+ computes on access
        except Exception:
            pass
        nl = len(me.loops)
        lno = np.empty(nl * 3, dtype=np.float32)
        me.loops.foreach_get('normal', lno)
        lno = lno.reshape(-1, 3)

    restored = None
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        nlay = None
        if lno is not None:
            # bm.from_mesh keeps face/loop order identical to me.loops, so we
            # can push the authored normals in loop order into a custom layer.
            nlay = bm.loops.layers.float_vector.new('_inu_authored_n')
            i = 0
            n = len(lno)
            for f in bm.faces:
                for l in f.loops:
                    if i < n:
                        l[nlay] = (float(lno[i, 0]), float(lno[i, 1]),
                                   float(lno[i, 2]))
                    i += 1
        # Mark edges with 1 linked face (creases/seams/boundaries) sharp.
        for edge in bm.edges:
            if len(edge.link_loops) == 1:
                edge.smooth = False
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00001)
        # Read the authored normals back in the POST-weld loop order — that is
        # exactly the order bm.to_mesh will write, so it lines up with the new
        # me.loops 1:1.
        if nlay is not None:
            restored = []
            for f in bm.faces:
                for l in f.loops:
                    v = l[nlay]
                    restored.append((v[0], v[1], v[2]))
        bm.to_mesh(me)
    finally:
        bm.free()
    # Drop the temporary per-loop transfer layer — bm.to_mesh persists it as a
    # mesh attribute otherwise, leaving unused cruft on every welded vehicle.
    _tmp = me.attributes.get('_inu_authored_n')
    if _tmp is not None:
        try:
            me.attributes.remove(_tmp)
        except Exception:
            pass
    # Re-apply the authored normals the weld would otherwise have averaged.
    if restored is not None and len(restored) == len(me.loops):
        if hasattr(me, 'use_auto_smooth'):
            me.use_auto_smooth = True
        try:
            me.normals_split_custom_set(restored)
        except Exception:
            pass
        # NOTE: the RAW authored normals were already stashed in the
        # 'inu_authored_normal' corner attribute by _build_mesh (before Blender
        # could zero any); that attribute survives this weld, so we do NOT
        # overwrite it here with the mesh's (possibly zeroed) split normals.
    # EdgeSplit modifier (sharp-only): splits the marked edges at display so
    # they shade hard, while the base mesh stays connected/editable.
    if not me.shape_keys and not any(m.type == 'EDGE_SPLIT' for m in obj.modifiers):
        mod = obj.modifiers.new("EdgeSplit", 'EDGE_SPLIT')
        mod.use_edge_angle = False
    me.update()


def overlay_face_key(verts, a, b, c) -> str:
    """Stable position key for an overlay face (sorted, rounded to 0.1 mm).

    Used on BOTH sides of the round-trip — import records overlay faces by this
    key, export re-adds them by matching base triangles — so the exact format
    MUST match ``dff_export.overlay_face_key``."""
    pts = sorted(
        (round(verts[v][0], 4), round(verts[v][1], 4), round(verts[v][2], 4))
        for v in (a, b, c))
    return "|".join("%.4f,%.4f,%.4f" % p for p in pts)


def _detect_overlay_faces(geom: DffGeometry):
    """Record the reflective-overlay faces WITHOUT touching the mesh.

    GTA vehicles encode the glossy/reflective env-map layer as a SECOND (3rd,
    4th…) set of triangles sharing the SAME vertices as the body panel. Blender
    can't hold two faces on one vertex set — ``mesh.validate()`` drops the
    duplicate — so instead of splitting verts (bloats the file) or losing the
    layer (like DragonFF, which renders darker / less glossy) we just record
    each repeated face as ``(position-key, material)``. The exporter re-adds
    them on their base face's shared verts, keeping the mesh clean/compact in
    Blender while the round-trip preserves the reflection. Caller restricts
    this to authored-normal, non-skinned models (vehicles)."""
    tris = geom.triangles
    if not tris:
        return []
    verts = geom.vertices
    seen = set()
    overlay = []
    for tri in tris:
        ikey = tuple(sorted((tri.a, tri.b, tri.c)))
        if ikey in seen:
            overlay.append([overlay_face_key(verts, tri.a, tri.b, tri.c),
                            tri.material])
        else:
            seen.add(ikey)
    return overlay


def _build_mesh(geom: DffGeometry, name: str, materials: list,
                material_cache: Optional[dict] = None,
                uv_anim_dict=None, fix_winding: bool = False,
                preserve_doubles: bool = False) -> bpy.types.Mesh:
    """Build a Blender Mesh from DFF geometry via direct foreach_set.

    Avoids bmesh entirely — all attributes are pushed in bulk through
    ``foreach_set`` which is a C-level batch assignment. For a 10k-vert
    mesh this is ~40x faster than the old bmesh per-face loop.

    Falls back to the legacy bmesh path if a bulk assign fails — some
    malformed vanilla DFFs have duplicate faces / bad winding that
    ``mesh.validate()`` can't fully clean up.

    ``material_cache`` is threaded through to ``_create_blender_material``
    for cross-DFF dedup in bulk map import.

    ``uv_anim_dict`` (from the clump) is looked up by material's
    ``uv_anim_names`` so ``mat.inu.uv_anim_*`` is populated on import
    and the writer can round-trip the animation.
    """
    mesh = bpy.data.meshes.new(name)

    # Materials first — polygon material_index references these by slot.
    for mi, dff_mat in enumerate(materials):
        bl_mat = _create_blender_material(
            dff_mat, mi, material_cache, uv_anim_dict)
        mesh.materials.append(bl_mat)

    n_verts = len(geom.vertices)
    n_tris = len(geom.triangles)

    if n_verts == 0 or n_tris == 0:
        mesh.update()
        if geom.user_data:
            _store_user_data(mesh, geom.user_data)
        return mesh

    # Record the reflective-overlay faces (the env-map / glossy layer GTA stacks
    # on vehicle bodies as duplicate faces) and stash them on the mesh. They are
    # NOT added to Blender — it can't hold two faces on one vertex set — so the
    # mesh stays clean/compact like a DragonFF import; the exporter re-adds them
    # on the base faces' shared verts, preserving the reflection without bloating
    # the file. Gated to authored-normal, non-skinned geometry = vehicles.
    if bool(geom.normals) and len(geom.normals) == n_verts and not geom.skin:
        overlay = _detect_overlay_faces(geom)
        if overlay:
            import json
            mesh['inu_overlay_faces'] = json.dumps(overlay, separators=(',', ':'))

    try:
        # ── Vertices ────────────────────────────────────────────────────
        verts_np = np.asarray(geom.vertices, dtype=np.float32).reshape(-1, 3)
        mesh.vertices.add(n_verts)
        mesh.vertices.foreach_set('co', verts_np.ravel())

        # ── Triangles → loops + polygons ────────────────────────────────
        # Build flat index buffer [a0,b0,c0, a1,b1,c1, ...] from DFF tris.
        tri_np = np.empty((n_tris, 3), dtype=np.int32)
        mat_np = np.empty(n_tris, dtype=np.int32)
        for i, tri in enumerate(geom.triangles):
            tri_np[i, 0] = tri.a
            tri_np[i, 1] = tri.b
            tri_np[i, 2] = tri.c
            mat_np[i] = tri.material

        # ── Дедуп граней для моделей БЕЗ авторских нормалей (как DragonFF) ──
        # GTA-дороги/террейн со strip-флагом часто содержат вырожденные
        # треугольники (повтор индекса, от развёртки стрипа) и ДУБЛИКАТЫ
        # грани (один набор вершин дважды — 2-сторонняя геометрия с
        # противоположной намоткой). Наложенные «обратные» грани и дают
        # красные «через раз» + сломанный шейдинг. Отбрасываем вырожденные,
        # оставляем по одной грани на набор вершин; те, у кого был дубликат,
        # запоминаем (double_local) и ниже переориентируем по сваренному
        # эталону. Модели С нормалями (транспорт/педы) не трогаем.
        has_authored_normals = bool(geom.normals) and len(geom.normals) == n_verts
        double_local = None
        if preserve_doubles and not has_authored_normals and n_tris > 0:
            # RAW import (weld toggle OFF): keep every non-degenerate triangle,
            # INCLUDING coincident duplicates — double-sided fences/hedges. They
            # sit on separate verts (coincident positions), so validate() keeps
            # both, and the weld protection later keeps them apart. Only drop
            # genuinely degenerate tris (a repeated vertex, from strip flags).
            vkey = np.round(verts_np, 4)
            _, vclass = np.unique(vkey, axis=0, return_inverse=True)
            tcls = vclass[tri_np]
            valid = ((tcls[:, 0] != tcls[:, 1]) & (tcls[:, 1] != tcls[:, 2])
                     & (tcls[:, 0] != tcls[:, 2]))
            if not valid.all():
                keep = np.nonzero(valid)[0]
                tri_np = tri_np[keep]
                mat_np = mat_np[keep]
                n_tris = tri_np.shape[0]
        elif not has_authored_normals and n_tris > 0:
            # Дубли 2-сторонних граней в GTA часто сидят на ОТДЕЛЬНЫХ
            # вершинах с совпадающими координатами (одна точка — разные
            # индексы). Поэтому группируем по КЛАССАМ совпадающих позиций
            # (как remove_doubles dist=1e-4), а не по индексам вершин —
            # иначе такие дубли (тонкие бордюры) пропускаются. Исходные
            # индексы вершин при этом сохраняются.
            vkey = np.round(verts_np, 4)
            _, vclass = np.unique(vkey, axis=0, return_inverse=True)
            tcls = vclass[tri_np]
            pa, pb, pc = tcls[:, 0], tcls[:, 1], tcls[:, 2]
            valid = (pa != pb) & (pb != pc) & (pa != pc)
            vidx = np.nonzero(valid)[0]
            keys = np.sort(tcls[vidx], axis=1)
            ukeys, fi_loc, inv, counts = np.unique(
                keys, axis=0, return_index=True,
                return_inverse=True, return_counts=True)
            if len(ukeys) != n_tris:        # были вырожденные и/или дубликаты
                keep_loc = np.sort(fi_loc)
                keep = vidx[keep_loc]
                tri_np = tri_np[keep]
                mat_np = mat_np[keep]
                double_local = np.nonzero(counts[inv[keep_loc]] > 1)[0]
                n_tris = tri_np.shape[0]

        tri_flat = tri_np.ravel()

        n_loops = n_tris * 3
        mesh.loops.add(n_loops)
        mesh.polygons.add(n_tris)

        mesh.loops.foreach_set('vertex_index', tri_flat)
        mesh.polygons.foreach_set(
            'loop_start', np.arange(0, n_loops, 3, dtype=np.int32))
        mesh.polygons.foreach_set(
            'loop_total', np.full(n_tris, 3, dtype=np.int32))
        mesh.polygons.foreach_set('material_index', mat_np)

        # Smooth shading flag on EVERY face — required on all versions so
        # the DFF's per-vertex normals (applied below as custom split
        # normals) are honoured. A flat (use_smooth=False) face ignores
        # custom normals and shades hard, which read as "broken smoothing".
        # Previously this was gated to 4.1+, so on older Blender every mesh
        # came in flat-shaded.
        mesh.polygons.foreach_set('use_smooth', np.ones(n_tris, dtype=bool))

        # ── UV layers (per-vertex DFF → per-loop Blender) ───────────────
        for i, uv_layer_data in enumerate(geom.uv_layers):
            if not uv_layer_data:
                continue
            uv_name = "UVMap" if i == 0 else f"UVMap.{i:03d}"
            uv_layer = mesh.uv_layers.new(name=uv_name)
            # Build per-vertex UV array — flip V (GTA top-origin → Blender bot).
            uvs_np = np.array([(tc.u, 1.0 - tc.v) for tc in uv_layer_data],
                              dtype=np.float32)
            # Expand to per-loop via fancy indexing: loop[k] ← vertex[tri_flat[k]]
            loop_uvs = uvs_np[tri_flat]
            uv_layer.data.foreach_set('uv', loop_uvs.ravel())

        # ── Vertex color layers (Day / Night) ───────────────────────────
        from ..tools.compat import vcol_new
        def _add_color_layer(layer_name: str, dff_colors):
            if not dff_colors:
                return
            attr = vcol_new(mesh, layer_name)  # 2.80 vertex_colors / 3.2+ color_attributes
            cols_np = np.empty((len(dff_colors), 4), dtype=np.float32)
            for k, c in enumerate(dff_colors):
                cols_np[k, 0] = c.r / 255.0
                cols_np[k, 1] = c.g / 255.0
                cols_np[k, 2] = c.b / 255.0
                cols_np[k, 3] = c.a / 255.0
            loop_cols = cols_np[tri_flat]
            # 'color_srgb' пишет байт напрямую без gamma-encode (Blender
            # 4.x для BYTE_COLOR при 'color' трактует вход как LINEAR
            # и кодирует в sRGB при хранении → байт сдвигается, round-
            # trip ломается).
            attr.data.foreach_set('color_srgb', loop_cols.ravel())

        _add_color_layer('Day', geom.prelit_colors)
        if geom.extra_colors and getattr(geom.extra_colors, 'colors', None):
            _add_color_layer('Night', geom.extra_colors.colors)

        mesh.update(calc_edges=True)
        mesh.validate(verbose=False)  # clean duplicate/degenerate faces

        # ── Custom split normals from the DFF ───────────────────────────
        # GTA stores a per-vertex normal that encodes the authored shading
        # (hard vs soft edges). Without applying it, Blender recomputes
        # all-smooth normals and the model's smoothing looks wrong. Feed
        # the DFF normals back as custom split normals so the mesh shades
        # EXACTLY as exported. Cross-version: <4.1 also needs
        # use_auto_smooth=True for custom normals to take effect; 4.1+
        # dropped that flag and honours them whenever faces are smooth.
        if geom.normals and len(geom.normals) == n_verts:
            try:
                if hasattr(mesh, 'use_auto_smooth'):
                    mesh.use_auto_smooth = True
                mesh.normals_split_custom_set_from_vertices(
                    [(n[0], n[1], n[2]) for n in geom.normals])
            except Exception as ne:
                print(f"[INU_tools] custom split normals skipped: {ne}")

        # ── Переориентация ТОЛЬКО граней-дубликатов (как DragonFF) ──────
        # КЛЮЧЕВОЕ: трогаем лишь те грани, у которых БЫЛ дубликат
        # (double_local) — а НЕ всю модель. Иначе открытая оболочка
        # (здание без дна/стены) выворачивается целиком. DragonFF делает
        # ровно так: recalc нормалей у дублей, затем сверяет с эталоном
        # сваренной копии и разворачивает лишь несовпавшие дубли.
        if double_local is not None and len(double_local):
            try:
                bm = bmesh.new()
                bm.from_mesh(mesh)
                bm.faces.ensure_lookup_table()
                nfaces = len(bm.faces)
                dfaces = [bm.faces[int(i)] for i in double_local
                          if 0 <= int(i) < nfaces]
                if dfaces:
                    bmesh.ops.recalc_face_normals(bm, faces=dfaces)
                    bm_w = bm.copy()
                    bm_w.faces.ensure_lookup_table()
                    pairs = [(f, bm_w.faces[f.index]) for f in dfaces]
                    bmesh.ops.remove_doubles(bm_w, verts=bm_w.verts, dist=0.0001)
                    bmesh.ops.recalc_face_normals(bm_w, faces=bm_w.faces)
                    for f, wf in pairs:
                        if wf.is_valid and f.normal.dot(wf.normal) < 0.0:
                            f.normal_flip()
                    bm_w.free()
                    bm.to_mesh(mesh)
                    mesh.update()
                bm.free()
            except Exception as ne:
                print(f"[INU_tools] double-face reorient skipped: {ne}")

    except Exception as e:
        # Fallback to bmesh path on malformed geometry — rare but a few
        # vanilla DFFs have non-manifold data that foreach_set can't absorb.
        print(f"[INU_tools] foreach_set mesh build failed ({e}), falling back to bmesh")
        _build_mesh_bmesh(mesh, geom)

    # Stash the RAW DFF normals in a plain corner attribute — done LAST, after
    # every mesh rebuild (validate, double-face reorient) so it stays aligned
    # to the final loops. Blender ZEROES the split normal at a many-faces-one-
    # position corner (door hinges etc.); reading it back loses the value and
    # the re-export writes a black/geometric normal → shading blotch. A generic
    # attribute is never touched, so the exporter writes the authored normal
    # back verbatim. Zeros in geom.normals stay zero and the exporter ignores
    # them (falls back to the geometric normal).
    if geom.normals and len(geom.normals) == len(mesh.vertices):
        try:
            gn = np.asarray([(n[0], n[1], n[2]) for n in geom.normals],
                            dtype=np.float32)
            nl = len(mesh.loops)
            if nl:
                lvi = np.empty(nl, dtype=np.int32)
                mesh.loops.foreach_get('vertex_index', lvi)
                attr = mesh.attributes.new(
                    'inu_authored_normal', 'FLOAT_VECTOR', 'CORNER')
                attr.data.foreach_set('vector', gn[lvi].ravel())
        except Exception as ae:
            print(f"[INU_tools] authored-normal attr skipped: {ae}")

    # Store geometry user data on mesh
    if geom.user_data:
        _store_user_data(mesh, geom.user_data)

    return mesh


def _set_object_props(obj, geom: DffGeometry):
    """Записываем INU свойства объекта из DFF данных.

    Зеркалим то, что реально лежит в DFF: геометрические флаги
    (NORMALS / LIGHT / MODULATE / UV2) → одноимённые галки N-панели,
    пайплайн из CHUNK_PIPELINE_SET → enum ``inu.pipeline``. Если
    pipeline-чанка в файле нет — оставляем 'NONE'. Чтобы галки и
    пайплайн совпали с импортированной геометрией без ручной правки
    после Import DFF.
    """
    obj.inu.type = 'OBJ'
    # DFF geometry flag bits → per-object check-boxes (mirror N-panel)
    obj.inu.export_normals  = geom.export_normals
    obj.inu.light           = geom.export_light
    obj.inu.modulate_color  = geom.export_mod_color
    obj.inu.export_binsplit = geom.write_bin_mesh

    # Pipeline: значение CHUNK_PIPELINE_SET (если есть) или 'NONE'.
    # Так после Import DFF дропдаун пайплайна сразу показывает то, что
    # было в файле — не нужно угадывать вручную.
    if geom.pipeline:
        pipeline_hex = f"0x{geom.pipeline:08X}"
        known = {'0x53F20098', '0x53F2009A', '0x53F2009C'}
        if pipeline_hex in known:
            obj.inu.pipeline = pipeline_hex
        else:
            obj.inu.pipeline = 'CUSTOM'
            obj.inu.custom_pipeline = pipeline_hex
    else:
        obj.inu.pipeline = 'NONE'

    # UV maps
    obj.inu.uv_map1 = len(geom.uv_layers) >= 1
    obj.inu.uv_map2 = len(geom.uv_layers) >= 2

    # Color flags
    obj.inu.day_cols = bool(geom.prelit_colors)
    obj.inu.night_cols = bool(geom.extra_colors and geom.extra_colors.colors)


def _import_2dfx(ext_2dfx: Extension2dfx, collection, base_name: str) -> list:
    """Создаём Empty-объекты для каждого 2DFX эффекта.

    Каждый эффект хранится как Empty с типом '2DFX' и custom properties.
    """
    objects = []
    if not ext_2dfx or not ext_2dfx.entries:
        return objects

    for i, entry in enumerate(ext_2dfx.entries):
        if isinstance(entry, Light2dfx):
            name = f"{base_name}.2dfx_light.{i}"
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = 'PLAIN_AXES'
            obj.empty_display_size = 0.3
            obj.location = entry.loc

            obj.inu.type = '2DFX'
            obj.inu.effect_2dfx = 'LIGHT'

            obj.inu.color_2dfx = (entry.color.r / 255.0, entry.color.g / 255.0,
                                   entry.color.b / 255.0, entry.color.a / 255.0)
            obj['2dfx_corona_far_clip'] = entry.corona_far_clip
            obj['2dfx_pointlight_range'] = entry.pointlight_range
            obj.inu.corona_size_2dfx = entry.corona_size
            obj.inu.shadow_size_2dfx = entry.shadow_size
            obj['2dfx_corona_enable_reflection'] = entry.corona_enable_reflection
            obj['2dfx_shadow_color_multiplier'] = entry.shadow_color_multiplier
            obj['2dfx_flags1'] = entry.flags1
            # Set EnumProperty values for dropdowns
            try:
                obj.inu.corona_tex_2dfx = entry.corona_tex_name
            except TypeError:
                obj['2dfx_corona_tex'] = entry.corona_tex_name
            try:
                obj.inu.shadow_tex_2dfx = entry.shadow_tex_name
            except TypeError:
                obj['2dfx_shadow_tex'] = entry.shadow_tex_name
            try:
                obj.inu.show_mode_2dfx = str(entry.corona_show_mode)
            except TypeError:
                pass
            try:
                obj.inu.flare_type_2dfx = str(entry.corona_flare_type)
            except TypeError:
                pass
            obj['2dfx_shadow_z_distance'] = entry.shadow_z_distance
            obj['2dfx_flags2'] = entry.flags2
            if entry.look_direction is not None:
                obj['2dfx_look_direction'] = list(entry.look_direction)
            # Display precision — `id_properties_ui` added in Blender 3.0,
            # на 2.83–2.93 пропускаем (косметика).
            if hasattr(obj, 'id_properties_ui'):
                for key in ('2dfx_corona_far_clip', '2dfx_pointlight_range'):
                    obj.id_properties_ui(key).update(precision=1)

        elif isinstance(entry, Particle2dfx):
            name = f"{base_name}.2dfx_particle.{i}"
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = 'CIRCLE'
            obj.empty_display_size = 0.2
            obj.location = entry.loc

            obj.inu.type = '2DFX'
            obj.inu.effect_2dfx = 'PARTICLE'

            obj['2dfx_effect_name'] = entry.effect_name

        elif isinstance(entry, PedAttractor2dfx):
            name = f"{base_name}.2dfx_ped.{i}"
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = 'CUBE'
            obj.empty_display_size = 0.15
            obj.location = entry.loc

            obj.inu.type = '2DFX'
            obj.inu.effect_2dfx = 'PED_ATTRACTOR'

            obj['2dfx_attractor_type'] = entry.attractor_type
            obj['2dfx_rotation_matrix'] = list(entry.rotation_matrix)
            obj['2dfx_external_script'] = entry.external_script
            obj['2dfx_ped_probability'] = entry.ped_existing_probability
            # Tail bytes 52/54 (W2) — vanilla carries 0x23 on 18 entries;
            # kept so a Blender round-trip re-writes the record verbatim.
            obj['2dfx_ped_flags'] = entry.flags
            obj['2dfx_ped_unknown'] = entry.unknown

        elif isinstance(entry, SunGlare2dfx):
            name = f"{base_name}.2dfx_sunglare.{i}"
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = 'SPHERE'
            obj.empty_display_size = 0.1
            obj.location = entry.loc

            obj.inu.type = '2DFX'
            obj.inu.effect_2dfx = 'SUN_GLARE'

        elif isinstance(entry, EnterExit2dfx):
            name = f"{base_name}.2dfx_enex.{i}"
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = 'ARROWS'
            obj.empty_display_size = 0.5
            obj.location = entry.loc
            obj.inu.type = '2DFX'
            obj.inu.effect_2dfx = 'ENTER_EXIT'
            obj.inu.ee_enter_angle = entry.enter_angle
            obj.inu.ee_radius_x = entry.approximation_radius_x
            obj.inu.ee_radius_y = entry.approximation_radius_y
            obj.inu.ee_exit_loc = tuple(entry.exit_loc)
            obj.inu.ee_exit_angle = entry.exit_angle
            obj.inu.ee_interior = entry.interior
            obj.inu.ee_flags1 = entry.flags1
            obj.inu.ee_sky_color = entry.sky_color
            obj.inu.ee_interior_name = entry.interior_name
            obj.inu.ee_time_on = entry.time_on
            obj.inu.ee_time_off = entry.time_off
            obj.inu.ee_flags2 = entry.flags2
            obj.inu.ee_unknown = entry.unknown

        elif isinstance(entry, RoadSign2dfx):
            name = f"{base_name}.2dfx_sign.{i}"
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = 'PLAIN_AXES'
            obj.empty_display_size = 0.5
            obj.location = entry.loc
            obj.inu.type = '2DFX'
            obj.inu.effect_2dfx = 'ROAD_SIGN'
            obj.inu.sign_size = tuple(entry.size)
            obj.inu.sign_rotation = tuple(entry.rotation)
            lines = list(entry.text_lines) + ["", "", "", ""]
            obj.inu.sign_text0 = lines[0]
            obj.inu.sign_text1 = lines[1]
            obj.inu.sign_text2 = lines[2]
            obj.inu.sign_text3 = lines[3]
            # Unpack the flags byte into friendly fields (bits 0-1 lines,
            # 2-3 max chars, 4-5 colour) — see _pack_sign_flags for the map.
            f = entry.flags
            obj.inu.sign_lines = (f & 0x3) + 1
            obj.inu.sign_maxchars = ('16', '2', '4', '8')[(f >> 2) & 0x3]
            obj.inu.sign_color = ('WHITE', 'BLACK', 'GREY', 'RED')[(f >> 4) & 0x3]

        elif isinstance(entry, Escalator2dfx):
            name = f"{base_name}.2dfx_escalator.{i}"
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = 'SINGLE_ARROW'
            obj.empty_display_size = 0.5
            obj.location = entry.loc
            obj.inu.type = '2DFX'
            obj.inu.effect_2dfx = 'ESCALATOR'
            # Store points RELATIVE to the marker (entry.loc) so the Empty is
            # the anchor: moving it in Blender carries the whole escalator.
            lx, ly, lz = entry.loc
            obj.inu.esc_bottom = (entry.bottom[0] - lx, entry.bottom[1] - ly, entry.bottom[2] - lz)
            obj.inu.esc_top = (entry.top[0] - lx, entry.top[1] - ly, entry.top[2] - lz)
            obj.inu.esc_end = (entry.end[0] - lx, entry.end[1] - ly, entry.end[2] - lz)
            obj.inu.esc_direction = '1' if entry.direction else '0'

        elif isinstance(entry, RawUnknown2dfx):
            name = f"{base_name}.2dfx_raw{entry.effect_id}.{i}"
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = 'CUBE'
            obj.empty_display_size = 0.1
            obj.location = entry.loc
            obj.inu.type = '2DFX'
            obj.inu.effect_2dfx = 'RAW_2DFX'
            obj['2dfx_raw_effect_id'] = entry.effect_id
            obj['2dfx_raw_bytes'] = list(entry.raw)

        else:
            continue

        collection.objects.link(obj)
        objects.append(obj)

        # Визуальный превью для Light2dfx
        if isinstance(entry, Light2dfx):
            try:
                from .fx_preview import create_light_preview
                create_light_preview(obj)
            except Exception as e:
                print(f"[INU_tools] 2DFX import preview error: {e}")
        elif isinstance(entry, Escalator2dfx):
            try:
                from .fx_preview import create_escalator_preview
                create_escalator_preview(obj)
            except Exception as e:
                print(f"[INU_tools] 2DFX escalator preview error: {e}")
        elif isinstance(entry, RoadSign2dfx):
            try:
                from .fx_preview import create_road_sign_preview
                create_road_sign_preview(obj)
            except Exception as e:
                print(f"[INU_tools] 2DFX road sign preview error: {e}")
        elif isinstance(entry, EnterExit2dfx):
            try:
                from .fx_preview import create_enterexit_preview
                create_enterexit_preview(obj)
            except Exception as e:
                print(f"[INU_tools] 2DFX enter/exit preview error: {e}")

    return objects


def _has_skeleton(clump: DffClump) -> bool:
    """Check if DFF has skeleton (HAnimData on any frame)."""
    return any(f.hanim and f.hanim.bones for f in clump.frames)


def _get_skinned_data(clump: DffClump):
    """Find the first geometry with SkinData."""
    for geom in clump.geometries:
        if geom.skin:
            return geom.skin
    return None


def _align_roll(vec, vecz, tarz):
    """Calculate bone roll to align Z axis (from DragonFF)."""
    import math
    sine_roll = vec.normalized().dot(vecz.normalized().cross(tarz.normalized()))
    if 1 < abs(sine_roll):
        sine_roll /= abs(sine_roll)
    if 0 < vecz.dot(tarz):
        return math.asin(sine_roll)
    elif 0 < sine_roll:
        return -math.asin(sine_roll) + math.pi
    else:
        return -math.asin(sine_roll) - math.pi


def _build_armature(clump: DffClump, name: str):
    """Create Blender Armature from DFF frame hierarchy + HAnimData + SkinData.

    Follows DragonFF approach: bone_matrices from SkinData → transposed → inverted → transform.
    Returns (armature_object, bone_names_list).
    """
    arm_data = bpy.data.armatures.new(f"{name}_Armature")
    arm_obj = bpy.data.objects.new(f"{name}_Armature", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)

    # Find root hanim frame (the one with the bone list)
    hanim_root_frame = None
    hanim_root_idx = 0
    for i, frame in enumerate(clump.frames):
        if frame.hanim and frame.hanim.bones:
            hanim_root_frame = frame
            hanim_root_idx = i
            break

    if not hanim_root_frame:
        print(f"[INU] No HAnimData root found in {name}")
        return arm_obj, []

    # Build bone_id → frame_index mapping
    bone_id_to_frame_idx = {}
    for i, frame in enumerate(clump.frames):
        if frame.hanim:
            bone_id_to_frame_idx[frame.hanim.bone_id] = i

    # Get skin data for bone matrices
    skin = _get_skinned_data(clump)

    print(f"[INU] Building armature: {len(hanim_root_frame.hanim.bones)} bones, "
          f"skin={'yes' if skin else 'no'}, "
          f"bone_matrices={len(skin.bone_matrices) if skin else 0}")

    # Enter edit mode
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = arm_data.edit_bones

    bone_names = []
    bone_list = {}  # frame_index → (edit_bone, has_connected_child)

    for bone_idx, hbone in enumerate(hanim_root_frame.hanim.bones):
        frame_idx = bone_id_to_frame_idx.get(hbone.bone_id)
        if frame_idx is None:
            print(f"[INU] Bone id={hbone.bone_id} has no matching frame, skipping")
            bone_names.append(f"Bone_{hbone.bone_id}")
            continue

        frame = clump.frames[frame_idx]
        bone_name = frame.name if frame.name else f"Bone_{hbone.bone_id}"

        e_bone = edit_bones.new(bone_name)
        e_bone.tail = (0, 0.05, 0)  # Prevent auto-deletion
        e_bone['bone_id'] = hbone.bone_id
        e_bone['bone_type'] = hbone.bone_type
        e_bone['bone_index'] = hbone.index
        e_bone['dff_frame_flags'] = frame.flags
        bone_names.append(bone_name)

        print(f"[INU]   Bone[{bone_idx}] '{bone_name}' id={hbone.bone_id} "
              f"index={hbone.index} frame={frame_idx} parent={frame.parent}")

        # Apply bone matrix from SkinData (exactly like DragonFF)
        if skin and hbone.index < len(skin.bone_matrices):
            matrix = mathutils.Matrix(skin.bone_matrices[hbone.index]).transposed()
            if abs(matrix.determinant()) > 1e-8:
                matrix.invert()
            else:
                matrix.identity()

            e_bone.transform(matrix, scale=True, roll=False)
            e_bone.roll = _align_roll(
                e_bone.vector, e_bone.z_axis,
                matrix.to_3x3() @ mathutils.Vector((0, 0, 1))
            )
        else:
            # Fallback: frame rotation/position (animated map objects —
            # rigs without SkinPLG). DFF stores frame.rotation row-major
            # with rows = axis vectors (RW convention), so the Matrix
            # constructor below — which takes ROW tuples — must read
            # (rot[0],rot[1],rot[2]) as row 0, NOT a column.
            #
            # The earlier "build as columns, then .transposed()" path
            # was equivalent in pure linear algebra (transpose twice =
            # identity) BUT for a bone authored with tail=(0,0,1) it
            # flipped the head→tail vector to -Z, because the export
            # side writes matrix_local.transposed() and we have to read
            # it back row-major to get matrix_local — not its transpose.
            # Symptoms before the fix: animated mesh imported lying on
            # its side (X+90°) and IFP application rotated 180° around Y.
            rot = frame.rotation
            pos = frame.position
            matrix = mathutils.Matrix((
                (rot[0], rot[1], rot[2]),
                (rot[3], rot[4], rot[5]),
                (rot[6], rot[7], rot[8]),
            ))
            e_bone.matrix = (
                mathutils.Matrix.Translation(pos) @ matrix.to_4x4()
            )

        # Parent relationship (like DragonFF: frame.parent >= root frame_index and in bone_list)
        if frame.parent >= hanim_root_idx and frame.parent in bone_list:
            e_bone.parent = bone_list[frame.parent][0]
            if skin is None:
                e_bone.matrix = bone_list[frame.parent][0].matrix @ e_bone.matrix

        # Key by frame_index (like DragonFF: bone_list[self.bones[bone.id]['index']])
        bone_list[frame_idx] = (e_bone, False)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Store ALL original frame data on armature object as JSON for round-trip export
    import json
    frame_data = {}
    for hbone in hanim_root_frame.hanim.bones:
        fi = bone_id_to_frame_idx.get(hbone.bone_id)
        if fi is None:
            continue
        f = clump.frames[fi]
        frame_data[str(hbone.bone_id)] = {
            'rot': list(f.rotation),
            'pos': list(f.position),
            'flags': f.flags,
            'parent': f.parent,
            'index': hbone.index,
            'write_name': f.write_name,
        }
        print(f"[INU]   save bone_id={hbone.bone_id} frame={fi} name='{f.name}' write_name={f.write_name}")
    arm_obj['dff_frame_data'] = json.dumps(frame_data)

    # Save raw DFF section bytes for perfect round-trip
    import base64
    if hasattr(clump.frames[0], '_raw_frame_list'):
        arm_obj['dff_raw_frame_list'] = base64.b64encode(clump.frames[0]._raw_frame_list).decode('ascii')
    if clump.raw_geometry_list:
        arm_obj['dff_raw_geometry_list'] = base64.b64encode(clump.raw_geometry_list).decode('ascii')
    if clump.raw_atomics:
        arm_obj['dff_raw_atomics'] = base64.b64encode(clump.raw_atomics).decode('ascii')

    print(f"[INU] Armature created: {len(bone_names)} bones")
    return arm_obj, bone_names


def _apply_skin_weights(obj, geom, arm_obj, bone_names):
    """Apply SkinData vertex weights to mesh object and parent to armature.

    DragonFF approach: create numbered vertex groups first, then rename to bone names.
    """
    skin = geom.skin
    if not skin:
        return

    print(f"[INU] Applying skin weights to '{obj.name}': "
          f"{skin.num_bones} bones, {len(skin.bone_indices)} verts")

    # Create vertex groups (one per bone, in order)
    for _ in range(skin.num_bones):
        obj.vertex_groups.new()

    # Assign weights via the bmesh deform layer — a direct C-backed write.
    # The old path called ``obj.vertex_groups[b].add([vi], w)`` once PER
    # vertex PER bone: on a 30k-vert mesh that's ~120k individual bpy
    # operator calls, and across a batch of skinned models it froze Blender
    # for minutes. bmesh writes every weight in one pass, no per-vertex cost.
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    dvert_lay = bm.verts.layers.deform.verify()
    n_skin_verts = min(len(bm.verts), len(skin.bone_indices))
    for vi in range(n_skin_verts):
        indices = skin.bone_indices[vi]
        weights = skin.bone_weights[vi]
        dv = bm.verts[vi][dvert_lay]
        for bi in range(4):
            bone_idx = indices[bi]
            weight = weights[bi]
            if weight > 0.0 and bone_idx < skin.num_bones:
                # 'ADD' semantics — accumulate if a bone repeats in the 4 slots.
                dv[bone_idx] = dv.get(bone_idx, 0.0) + weight
    bm.to_mesh(me)
    bm.free()

    # bmesh.to_mesh can drop custom split normals — re-apply from the DFF
    # so skinned meshes keep their authored shading (mirrors _build_mesh).
    if geom.normals and len(geom.normals) == len(me.vertices):
        try:
            if hasattr(me, 'use_auto_smooth'):
                me.use_auto_smooth = True
            me.normals_split_custom_set_from_vertices(
                [(nn[0], nn[1], nn[2]) for nn in geom.normals])
        except Exception:
            pass

    # Rename vertex groups to bone names
    for i, bname in enumerate(bone_names):
        if i < len(obj.vertex_groups):
            obj.vertex_groups[i].name = bname

    # Store original bone_matrices for round-trip export
    import json
    obj['dff_bone_matrices'] = json.dumps(skin.bone_matrices)
    obj['dff_skin_num_used'] = skin.num_used
    obj['dff_skin_max_weights'] = skin.max_weights
    obj['dff_skin_bones_used'] = json.dumps(skin.bones_used)

    # Parent mesh to armature with Armature modifier
    obj.parent = arm_obj
    mod = obj.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = arm_obj

    print(f"[INU] Skin weights applied, {len(obj.vertex_groups)} vertex groups")


_KNOWN_PIPELINES = {'0x53F20098', '0x53F2009A', '0x53F2009C'}


def _autoset_scene_pipeline(clump):
    """Mirror the imported DFF's pipeline onto the scene's pipeline enum.

    Picks the most common ``CHUNK_PIPELINE_SET`` value across all
    geometries; if no geometry carries a Pipeline chunk, selects
    ``'NONE'`` (the standard RW render path). Unknown IDs route to
    ``'CUSTOM'`` with ``scn.inu_settings.gtatools_custom_pipeline`` set
    to the hex string. Silently no-ops when no scene is reachable
    (e.g. tests, background import).
    """
    try:
        import bpy as _bpy
        scn = _bpy.context.scene
        st = scn.inu_settings
    except Exception:
        return
    geoms = getattr(clump, 'geometry_list', None) or getattr(clump, 'geometries', [])
    if not geoms:
        return
    from collections import Counter
    counts = Counter(int(getattr(g, 'pipeline', 0)) for g in geoms)
    counts.pop(0, None)  # ignore "no chunk" entries — they don't dictate scene choice
    if not counts:
        target = 'NONE'
        custom_hex = ''
    else:
        pid = counts.most_common(1)[0][0]
        pipeline_hex = f"0x{pid:08X}"
        if pipeline_hex in _KNOWN_PIPELINES:
            target = pipeline_hex
            custom_hex = ''
        else:
            target = 'CUSTOM'
            custom_hex = pipeline_hex
    try:
        if getattr(st, 'gtatools_export_pipeline', None) != target:
            st.gtatools_export_pipeline = target
        if target == 'CUSTOM' and hasattr(st, 'gtatools_custom_pipeline'):
            st.gtatools_custom_pipeline = custom_hex
    except Exception:
        pass


def import_dff(filepath: str, context=None, *, skip_2dfx=None,
               bulk_mode: bool = False, target_collection=None,
               material_cache: Optional[dict] = None, profiler=None,
               weld_sharpen=None):
    """
    Импорт DFF файла в Blender.

    Args:
        filepath: Путь к .dff файлу.
        context: Blender context (опционально).
        skip_2dfx: пропустить импорт 2DFX-эффектов (лампы, частицы, ped attractors).
                   None → читать scene.inu_settings.gtatools_map_skip_2dfx.
        bulk_mode: при True пропускаются тяжёлые per-model операции —
                   ``view_layer.update()`` и ``select_all(DESELECT)``.
                   Для bulk-импорта карты их достаточно сделать один раз
                   в конце; в одиночном импорте эти вызовы нужны.
        target_collection: если указана — линковать созданные объекты
                   сразу в неё (избегает лишнего unlink+relink при
                   импорте карты).
        material_cache: общий dict для переиспользования материалов
                   между DFF (ключ — имя текстуры + RGBA). Сильно режет
                   время bulk-импорта карты.
        profiler: опциональный ``Profiler`` (см. ``INU_tools.tools.profiler``)
                   для замера под-стадий parse/build/link.
    """
    clump = read_dff_file(filepath)
    # Mobile DFFs use Native Data PLG (War Drum OpenGL) for vertex
    # storage — flip the scene's platform switch so the user sees that
    # the loaded file is mobile, not PC. Best-effort: don't break import
    # if the scene isn't reachable for any reason.
    if getattr(clump, 'is_mobile', False):
        try:
            import bpy as _bpy
            _bpy.context.scene.inu_settings.gtatools_platform = 'MOBILE'
        except Exception:
            pass

    # Auto-set scene pipeline to match the imported DFF, so the N-panel
    # pipeline button row immediately reflects what was actually in the
    # file. Skipped for bulk Map Import — flipping the scene pipeline per
    # geometry across thousands of buildings would thrash the per-object
    # flag-snapshot system (_inu_pipeline_changed iterates all meshes on
    # every change). Done BEFORE objects are built so the snapshot
    # callback only sees pre-existing objects, leaving the freshly
    # imported flags exactly as the file specifies.
    if not bulk_mode:
        _autoset_scene_pipeline(clump)
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    # Always thread a material cache through — even single-DFF imports
    # benefit. A vehicle.dff has 30+ parts but typically only ~5 unique
    # textures; without the cache that's ~30 bpy.data.materials.new
    # calls and we'd see vehiclelights128.001/.002/.../.005 copies for
    # every part that re-uses the same texture. Bulk imports already
    # pass their shared cache to dedupe across files; for a single
    # import we just want intra-file deduplication.
    if material_cache is None:
        material_cache = {}
    return import_dff_from_clump(
        clump, base_name, skip_2dfx=skip_2dfx, bulk_mode=bulk_mode,
        target_collection=target_collection, material_cache=material_cache,
        profiler=profiler, weld_sharpen=weld_sharpen,
    )


def import_dff_from_clump(clump, base_name: str, *, skip_2dfx=None,
                          bulk_mode: bool = False, target_collection=None,
                          material_cache: Optional[dict] = None, profiler=None,
                          fix_winding: bool = False, weld_sharpen=None):
    """Build Blender objects from an already-parsed DffClump.

    Separates the Blender-only work from the binary parse so the
    parse step can run in a worker thread (numpy releases the GIL)
    while the main thread stays busy creating bpy objects for the
    previous model.
    """
    # Resolve 2DFX skip flag from scene when not passed explicitly.
    # Свойство живёт на scene.inu_settings, не на scene напрямую —
    # без этого префикса getattr всегда возвращал False, и тогл
    # «Без 2DFX» в Import Map игнорировался.
    if skip_2dfx is None:
        try:
            settings = getattr(bpy.context.scene, 'inu_settings', None)
            skip_2dfx = bool(getattr(settings, 'gtatools_map_skip_2dfx', False))
        except Exception:
            skip_2dfx = False

    # Auto-weld + sharp edges (and the vehicle keep-normals weld) is right for
    # STANDARD GTA models but rewrites the topology of CUSTOM ones — gate both
    # on the user's toggle (scene setting when not passed explicitly).
    if weld_sharpen is None:
        try:
            from ..tools.user_data import get_addon_prefs
            prefs = get_addon_prefs()
            weld_sharpen = bool(getattr(prefs, 'import_weld_sharpen', False))
        except Exception:
            weld_sharpen = False

    # Null-object context manager so `with _stage(...)` works without
    # an `if profiler:` ladder every time. When profiler is None we
    # get effectively zero overhead.
    def _stage(name):
        if profiler is not None:
            return profiler.stage(name)
        class _Null:
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _Null()

    collection = target_collection if target_collection is not None else bpy.context.collection
    imported_objects = []
    # Объекты из геометрии БЕЗ авторских нормалей (карты/дороги/террейн) —
    # их автоматически сшиваем (сварка + острые рёбра, как DragonFF) в конце.
    # Модели с нормалями (транспорт/педы) сюда не попадают.
    weld_targets = []
    editable_targets = []  # authored-normal, non-skinned meshes (vehicles)
    frame_to_obj = {}  # frame_index → Blender object (MESH or EMPTY dummy)

    is_skinned = _has_skeleton(clump)

    # Suffix used for the fallback object name when the DFF frame
    # carries no name of its own. Reads the user-configured suffix from
    # scene settings (default ``_DFF``), so importing ``1.dff`` lands
    # ``1_DFF`` in the outliner rather than the previous ``1_0`` —
    # matches the convention model_utils.get_model_type() expects when
    # later inferring DFF / LOD / COL roles by name.
    try:
        _dff_suffix = getattr(bpy.context.scene.inu_settings,
                              'gtatools_suffix_dff', '_DFF')
    except Exception:
        _dff_suffix = '_DFF'
    try:
        _lod_suffix = getattr(bpy.context.scene.inu_settings,
                              'gtatools_suffix_lod', '_LOD') or '_LOD'
    except Exception:
        _lod_suffix = '_LOD'
    _n_geoms = len(clump.geometries)

    # LOD-модели именуем как ``<stem>_LOD`` (сняв маркер "lod" из имени)
    # вместо ``LOD…_DFF``. Централизовано здесь, поэтому работает для ВСЕХ
    # импортов, идущих через этот движок: одиночный DFF, drag-drop,
    # «Import All», импорт карты. Напр. LODham_orz_str_18 → ham_orz_str_18_LOD.
    from ..core.ipl import is_lod_name, strip_lod_marker
    _is_lod_base = is_lod_name(base_name)
    _name_stem = strip_lod_marker(base_name) if _is_lod_base else base_name
    _name_suffix = _lod_suffix if _is_lod_base else _dff_suffix

    def _fallback_name(gi: int) -> str:
        """Object name when the DFF frame has no name. Single-geom DFFs
        get ``<stem><suffix>``; multi-geom DFFs append the index so each
        part stays unique. LOD-имена получают суффикс ``_LOD``."""
        if _n_geoms <= 1:
            return f"{_name_stem}{_name_suffix}"
        return f"{_name_stem}{_name_suffix}_{gi}"

    # Создаём объекты из Atomic связей (frame → geometry)
    for atom_idx, atomic in enumerate(clump.atomics):
        gi = atomic.geometry_index
        fi = atomic.frame_index

        if gi >= len(clump.geometries):
            continue

        geom = clump.geometries[gi]
        frame = clump.frames[fi] if fi < len(clump.frames) else None

        # Имя объекта.
        # Одногеометрийный DFF (террейн, проп, LOD — одна модель): имя
        # берётся ИЗ ИМЕНИ ФАЙЛА. В GTA модель адресуется по имени .dff /
        # записи в IMG, а внутреннее имя фрейма у таких моделей — обычно
        # мусор моделлера («Line004», «Box001») или битое прошлым
        # экспортом («hedge_3_?_?_?_?_?_?_N__001»). Имя файла надёжнее.
        # Многосоставный DFF (транспорт, оружие): имена деталей важны для
        # иерархии и round-trip — берём имя фрейма, если оно «чистое»
        # (иначе fallback на имя файла).
        if _n_geoms <= 1:
            obj_name = _fallback_name(gi)
        elif frame and frame.name and _frame_name_usable(frame.name):
            obj_name = frame.name
        else:
            obj_name = _fallback_name(gi)

        with _stage('build_mesh'):
            mesh = _build_mesh(geom, obj_name, geom.materials,
                               material_cache, clump.uv_anim_dict,
                               fix_winding=fix_winding,
                               preserve_doubles=not weld_sharpen)

        # Создаём объект
        obj = bpy.data.objects.new(obj_name, mesh)

        # Трансформация применяется позже в hierarchy-проходе через matrix_world

        # INU свойства
        _set_object_props(obj, geom)
        # Store original UV layer count for round-trip
        obj['dff_num_uv_layers'] = len(geom.uv_layers)
        # Preserve the ATOMIC render order. GTA renders atomics in DFF-list
        # order; for alpha-blended parts (glossy car paint / glass) this order
        # decides the blend result. Re-export must keep it — otherwise Blender's
        # alphabetical child order scrambles it and the car renders dull/dark.
        obj['inu_atomic_order'] = atom_idx
        obj['dff_orig_vert_count'] = len(obj.data.vertices)
        # Store original geometry flags for round-trip
        obj['dff_geom_flags'] = geom._import_flags if hasattr(geom, '_import_flags') else 0
        # Store mesh frame index from atomic (needed for skinned export with edited geometry)
        obj['dff_mesh_frame_index'] = fi

        # Store original frame data for round-trip export
        if frame:
            obj['dff_frame_flags'] = frame.flags
            obj['dff_frame_rot'] = list(frame.rotation)
            obj['dff_frame_pos'] = list(frame.position)
            obj['dff_frame_write_name'] = frame.write_name

        # Frame user data → object custom property
        if frame and frame.user_data:
            _store_user_data(obj, frame.user_data)

        collection.objects.link(obj)
        imported_objects.append(obj)
        if not (geom.normals and len(geom.normals) == len(geom.vertices)):
            weld_targets.append(obj)
        elif not geom.skin:
            editable_targets.append(obj)
        if frame is not None:
            frame_to_obj[fi] = obj

    # Если нет Atomic, но есть геометрии — создаём напрямую
    if not clump.atomics and clump.geometries:
        for gi, geom in enumerate(clump.geometries):
            obj_name = _fallback_name(gi)
            with _stage('build_mesh'):
                mesh = _build_mesh(geom, obj_name, geom.materials,
                               material_cache, clump.uv_anim_dict,
                               fix_winding=fix_winding,
                               preserve_doubles=not weld_sharpen)
            obj = bpy.data.objects.new(obj_name, mesh)
            _set_object_props(obj, geom)
            collection.objects.link(obj)
            imported_objects.append(obj)
            if not (geom.normals and len(geom.normals) == len(geom.vertices)):
                weld_targets.append(obj)
            elif not geom.skin:
                editable_targets.append(obj)

    # Создаём Empty для каждого фрейма БЕЗ atomic'а (это dummy вроде wheel_lf_dummy)
    # Пропускаем если в DFF есть скелет — там фреймы представлены костями армутуры
    if not is_skinned:
        for fi, frame in enumerate(clump.frames):
            if fi in frame_to_obj:
                continue
            # RW-Light frames (``Omni###``) belong to the 2DFX lighting
            # system — drop them when 2DFX import is off, otherwise a map
            # imported «Без 2DFX» is still littered with Omni light dummies.
            if skip_2dfx and _is_light_frame_name(frame.name):
                continue
            dummy_name = (frame.name
                          if (frame.name and _frame_name_usable(frame.name))
                          else f"{base_name}_frame_{fi}")
            dummy = bpy.data.objects.new(dummy_name, None)
            # CUBE (like DragonFF) — a small box is far easier to see and
            # click in the viewport than the thin PLAIN_AXES cross.
            dummy.empty_display_type = 'CUBE'
            dummy.empty_display_size = 0.1

            dummy['dff_frame_flags'] = frame.flags
            dummy['dff_frame_rot'] = list(frame.rotation)
            dummy['dff_frame_pos'] = list(frame.position)
            dummy['dff_frame_write_name'] = frame.write_name

            if frame.user_data:
                _store_user_data(dummy, frame.user_data)

            collection.objects.link(dummy)
            imported_objects.append(dummy)
            frame_to_obj[fi] = dummy

        # Выставляем parent БЕЗ сохранения transform (matrix_parent_inverse=identity).
        for fi, frame in enumerate(clump.frames):
            child_obj = frame_to_obj.get(fi)
            if child_obj is None:
                continue
            parent_idx = frame.parent
            if 0 <= parent_idx < len(clump.frames):
                parent_obj = frame_to_obj.get(parent_idx)
                if parent_obj is not None and parent_obj is not child_obj:
                    child_obj.parent = parent_obj
                    child_obj.matrix_parent_inverse.identity()

        # Пишем matrix_basis прямо из DFF frame (rotation + position).
        # matrix_basis — внутреннее хранилище trans/rot/scale объекта, обходит
        # любые «умные» пересчёты Blender'а. При matrix_parent_inverse=identity
        # matrix_local == matrix_basis, а matrix_world = parent.matrix_world @ matrix_basis.
        #
        # ВАЖНО: для animated map objects atomic.frame_index указывает на
        # bone frame (HAnim), и frame.rotation там — это matrix_local
        # кости (например 90°X для bone с tail=+Z). Если этот transform
        # применить к самому MESH-объекту, меш визуально ляжет на бок
        # ровно на bone rest-pose поворот, потому что armature modifier
        # ещё раз развернёт меш на тот же угол при rest pose. Меш живёт
        # в armature-local space с identity transform, а ориентация
        # прихватывается через vertex group → armature modifier.
        for fi, frame in enumerate(clump.frames):
            obj = frame_to_obj.get(fi)
            if obj is None:
                continue
            if obj.type == 'MESH' and frame.hanim is not None:
                # rigid-attached to bone — transform приходит через
                # armature modifier, не через matrix_basis объекта.
                continue
            rot = frame.rotation
            pos = frame.position
            # DFF stores the frame rotation as ROWS = axis vectors (RW
            # convention), so it must be TRANSPOSED to get the actual local
            # matrix — exactly what DragonFF and our own exporter do
            # (dff_export.py: `mat.to_3x3().transposed()`). Reading the 9
            # floats straight as matrix rows (the old code) yielded the
            # transpose = inverse rotation, so original CS/rigid-attached
            # models came in rotated wrong (mesh lying on its side). Verified
            # on vanilla fam3.dff: transposed → skeleton↔bind consistent to
            # 0.0000, un-transposed → 2.0 error. (animobj meshes are skipped
            # above and don't reach this path.)
            obj.matrix_basis = mathutils.Matrix((
                (rot[0], rot[3], rot[6], pos[0]),
                (rot[1], rot[4], rot[7], pos[1]),
                (rot[2], rot[5], rot[8], pos[2]),
                (0, 0, 0, 1),
            ))

        if not bulk_mode:
            bpy.context.view_layer.update()

    # Skeleton: create Armature + apply skin weights / rigid-attach
    # if DFF has bones. Single guard:
    #   bulk_mode (map import) — skip armatures entirely. Vanilla map
    #   DFFs occasionally carry HAnim chunks with skin=no, and we don't
    #   want a ``<name>_Armature`` object per such model cluttering the
    #   outliner and bloating depsgraph.
    # Animated map objects (windmills, cranes, doors) have HAnim WITHOUT
    # skin and DO need an armature for IFP playback in Blender — so we
    # don't gate on ``has_skin`` here.
    if not bulk_mode and _has_skeleton(clump):
        try:
            arm_obj, bone_names = _build_armature(clump, base_name)
            imported_objects.append(arm_obj)

            for atomic in clump.atomics:
                gi = atomic.geometry_index
                if gi >= len(clump.geometries):
                    continue
                geom = clump.geometries[gi]
                fi = atomic.frame_index
                frame = clump.frames[fi] if fi < len(clump.frames) else None
                obj = frame_to_obj.get(fi)
                if not (obj and obj.type == 'MESH'):
                    continue

                if geom.skin:
                    # Skinned mesh (peds, skinned vehicles) — per-vertex
                    # bone weights wire the mesh to the armature.
                    _apply_skin_weights(obj, geom, arm_obj, bone_names)
                elif frame and frame.hanim:
                    # Animated map object — mesh rigidly follows ONE
                    # bone via Armature modifier + all-weight vertex
                    # group (NOT parent_type='BONE', which would
                    # re-align the mesh under the bone's tail and tip
                    # it 90° around X for a tail=+Z bone).
                    target_bone = frame.name
                    if target_bone and target_bone in bone_names:
                        obj.parent = arm_obj
                        obj.parent_type = 'OBJECT'
                        obj.matrix_parent_inverse.identity()
                        # Reset the mesh's own transform — the matrix_basis
                        # loop above skipped writing here, but be defensive
                        # in case a future code path wires it differently.
                        obj.matrix_basis = mathutils.Matrix.Identity(4)

                        vg = obj.vertex_groups.get(target_bone)
                        if vg is None:
                            vg = obj.vertex_groups.new(name=target_bone)
                        vg.add(
                            list(range(len(obj.data.vertices))),
                            1.0, 'REPLACE')

                        mod = next(
                            (m for m in obj.modifiers
                             if m.type == 'ARMATURE'), None)
                        if mod is None:
                            mod = obj.modifiers.new("Armature", 'ARMATURE')
                        mod.object = arm_obj

                        # Tag the rig so panels/animobj_export pick it
                        # up exactly like a freshly-built one from
                        # animobj_setup. Без маркера live-edit sliders
                        # и auto-rebuild-before-export молча no-op на
                        # импортированных рiгaх.
                        arm_obj['inu_animobj'] = True

                        print(f"[INU] mesh '{obj.name}' rigidly attached to "
                              f"bone '{target_bone}' via armature modifier "
                              f"(frame_idx={fi})")
                    else:
                        print(f"[INU] WARN: cannot parent mesh '{obj.name}' to "
                              f"bone '{target_bone}' — not in bone_names={bone_names}")
        except Exception as e:
            import traceback
            print(f"[INU_tools] Skeleton import error: {e}")
            traceback.print_exc()

    # Импорт 2DFX эффектов (собираем из всех геометрий) → коллекция "2DFX"
    if not skip_2dfx:
        fx_col = None
        for geom in clump.geometries:
            if geom.ext_2dfx and geom.ext_2dfx.entries:
                if fx_col is None:
                    col_name = "2DFX"
                    if col_name in bpy.data.collections:
                        fx_col = bpy.data.collections[col_name]
                    else:
                        fx_col = bpy.data.collections.new(col_name)
                        bpy.context.scene.collection.children.link(fx_col)
                fx_objects = _import_2dfx(geom.ext_2dfx, fx_col, base_name)
                imported_objects.extend(fx_objects)

    # Embedded collision — vehicles and skinned characters store COL
    # primitives (spheres + boxes + meshes) INSIDE the .dff as a
    # CHUNK_COLLISION_MODEL bytes blob, not as a separate .col file.
    # `read_dff_file` already preserved those bytes on
    # `clump.collision_data`. Parse them here and feed through the
    # normal COL importer so the user sees the same sphere empties /
    # col mesh objects that DragonFF creates — without this step
    # the col data was bit-perfect preserved for round-trip but
    # entirely invisible in viewport.
    if clump.collision_data:
        try:
            from ..core.col import read_col
            from .col_import import import_col_from_models
            col_models = read_col(clump.collision_data)
            if col_models:
                col_objs = import_col_from_models(
                    col_models,
                    bulk_mode=bulk_mode,
                    target_collection=target_collection,
                    skip_position_match=True,
                )
                imported_objects.extend(col_objs)
        except Exception as e:
            print(f"[INU] embedded COL parse failed for "
                  f"{base_name}: {e}")

    # Сварка моделей без авторских нормалей (карты/дороги/террейн). ВКЛ =
    # ванильный путь `_weld_and_sharpen` (как DragonFF, НЕ трогаем). ВЫКЛ =
    # кастомный путь `_weld_custom`: тоже СВЯЗЫВАЕТ рассыпанную геометрию, но
    # защищает двусторонние заборы и метит острые рёбра по углу.
    _weld_fn = _weld_and_sharpen if weld_sharpen else _weld_custom
    for obj in weld_targets:
        if getattr(obj, 'type', None) == 'MESH':
            try:
                _weld_fn(obj)
            except Exception as we:
                print(f"[INU] weld failed for {obj.name}: {we}")

    # Транспорт (авторские нормали, без скина): всегда свариваем совпадающие
    # вершины, чтобы меш был СВЯЗНЫМ и редактируемым (custom split normals
    # сохраняются) — независимо от галочки.
    for obj in editable_targets:
        if getattr(obj, 'type', None) == 'MESH':
            try:
                _weld_keep_normals(obj)
            except Exception as we:
                print(f"[INU] vehicle weld failed for {obj.name}: {we}")

    # Выделяем импортированные объекты. При bulk_mode пропускаем
    # select_all — это O(scene_size) операция, которая для импорта
    # карты (тысячи моделей) в сумме даёт O(N²). Для bulk достаточно
    # вернуть список и дать вызывающему коду самому решить.
    if not bulk_mode:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in imported_objects:
            obj.select_set(True)
        if imported_objects:
            bpy.context.view_layer.objects.active = imported_objects[0]

    return imported_objects


# ──────────────────── Auto-TXD picker ────────────────────────────────
#
# When a user imports a DFF, we want to auto-pull the matching TXD so
# materials get textured. The naïve heuristic ("same name first, else
# any .txd in the folder") fails on common cases like
#   BillBd2.dff  ←→  billbrd.txd
# where the artist used different shorthand names. So instead we score
# every .txd in the search dirs by how many of its texture names show
# up as `mat['dff_texture_name']` on a freshly-imported material, and
# pick the highest-scoring file. Same-name still wins ties for free
# (it scores ≥0 like everything else, and the loop preserves order).
#
# The probe uses ``read_txd_texture_names`` which only reads texture
# headers (no pixel decode) — sub-millisecond per file even on big TXDs.

def _collect_recent_dff_texture_names() -> set:
    """Names recorded as ``mat['dff_texture_name']`` across **all**
    materials in scene. After a DFF import this includes every texture
    the just-imported model references — but ALSO every previously
    imported one. Use `_collect_new_dff_texture_names(mats_before)`
    instead during batch import to keep the set scoped to the current
    DFF only; otherwise the auto-TXD picker drifts (sees more "needed"
    names with every import) and `name_filter` to `import_txd` over-
    decodes shared textures."""
    out = set()
    for mat in bpy.data.materials:
        n = mat.get('dff_texture_name')
        if n:
            out.add(n.lower())
    return out


def _collect_dff_scope(objs):
    """Материалы, реально используемые объектами ``objs`` (по слотам), плюс
    набор имён текстур, на которые они ссылаются (``dff_texture_name``).

    Надёжнее, чем диф по «новым» материалам: если DFF дропнут в сцену, где
    уже загружена карта с такими же именами материалов, импортёр
    ПЕРЕИСПОЛЬЗУЕТ существующие датаблоки — они не «новые», но текстуры им
    всё равно нужны. Сбор по слотам ловит и такие. Возвращает
    ``(scope_mats, needed_names)``."""
    scope_mats = []
    seen = set()
    needed = set()
    for o in (objs or []):
        if getattr(o, 'type', None) != 'MESH':
            continue
        for sl in o.material_slots:
            m = sl.material
            if m is None or m.name in seen:
                continue
            seen.add(m.name)
            scope_mats.append(m)
            n = m.get('dff_texture_name')
            if n:
                needed.add(n.lower())
    return scope_mats, needed


def _collect_new_dff_texture_names(mat_names_before: set) -> set:
    """Texture names from materials that did NOT exist before the
    snapshot. Pass the set captured from `{m.name for m in
    bpy.data.materials}` BEFORE calling `import_dff` — we diff after
    and return only the brand-new materials' texture refs."""
    out = set()
    for mat in bpy.data.materials:
        if mat.name in mat_names_before:
            continue
        n = mat.get('dff_texture_name')
        if n:
            out.add(n.lower())
    return out


# Module-level cache for `read_txd_texture_names` results. Batch
# character/ped import walks the same folder of .txd files for every
# DFF and re-parses each header set from disk every time — O(N×M).
# Caching by (path, mtime) collapses that to O(M) per session;
# mtime check keeps the cache safe if the user re-saves a .txd
# between imports.
_TXD_NAMES_CACHE: dict = {}


def _read_txd_names_cached(path: str) -> set:
    """Return lowercase texture names for `path`, reading the file
    once per session and reusing the result on subsequent calls."""
    from ..core.txd import read_txd_texture_names
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    cached = _TXD_NAMES_CACHE.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    try:
        names = {n.lower() for n in read_txd_texture_names(path)}
    except Exception:
        names = set()
    _TXD_NAMES_CACHE[path] = (mtime, names)
    return names


_PICK_BEST_TXD_MIN_COVERAGE = 0.5  # 50% of DFF textures must be in TXD


def _txd_affinity(txd_path: str, dff_basename: str) -> int:
    """Грубая «похожесть» имени TXD на имя DFF — задаёт порядок сканирования,
    чтобы вероятный «свой» TXD прочитать первым (billbrd.txd для BillBd2.dff).
    Больше = вероятнее. Дешёвая (только строки, без чтения файла)."""
    t = os.path.splitext(os.path.basename(txd_path))[0].lower()
    d = (dff_basename or "").lower()
    if not t or not d:
        return 0
    score = 0
    if t == d:
        score += 1000                 # точное совпадение (Pass 1 его уже ловит)
    if d in t or t in d:
        score += 100                  # одно имя содержит другое
    n = 0                             # длина общего префикса
    for a, b in zip(t, d):
        if a != b:
            break
        n += 1
    return score + n


def _pick_best_txd(search_dirs: list, dff_basename: str,
                   needed_names: set = None, txd_hint: str = None) -> Optional[str]:
    """Pick the most relevant .txd file for the just-imported DFF.

    Strategy:
      0. ``txd_hint`` (the TXD name declared in the IDE/bridge meta, e.g.
         «generic») wins if a ``<hint>.txd`` in the search dirs actually
         covers the model's textures. Shared TXDs (generic.txd) aren't
         named after the model, so coverage-scoring alone can miss them;
         the declared name resolves them deterministically. Coverage is
         still checked so the RIGHT generic.txd is chosen when several
         games (III + VC) each ship one.
      1. Same-named ``<dff_basename>.txd`` wins immediately (cheap path).
      2. Otherwise, score every .txd in the search dirs by **coverage**:
         what fraction of the DFF's referenced textures live in that
         TXD. We pick the highest-coverage file as long as it clears
         ``_PICK_BEST_TXD_MIN_COVERAGE`` (default 50%). Tie-break:
         prefer the *smaller* TXD (fewer extras = more model-specific,
         less likely to be a generic catch-all).
      3. If only ONE .txd exists in the folder we still take it as a
         last resort — the user wouldn't have put it there if it was
         unrelated.

    Returns absolute path or ``None`` if no plausible .txd was found.
    A None return is a real "I refuse to guess" — the caller should
    warn the user so they can pick manually.
    """
    from ..core.txd import read_txd_texture_names

    needed = (needed_names if needed_names is not None
              else _collect_recent_dff_texture_names())

    # Pass 0: объявленное имя TXD (IDE/мета, напр. «generic»). Ищем
    # <hint>.txd, что РЕАЛЬНО покрывает нужные текстуры — важно при
    # нескольких играх (III и VC оба имеют generic.txd: берём тот, где есть
    # текстуры модели). Приоритет над basename: у shared-моделей рядом может
    # лежать пустой <model>.txd от моста, а правильный txd — общий.
    if txd_hint:
        hint = os.path.splitext(str(txd_hint).strip())[0]
        if hint:
            hits = [os.path.join(d, hint + ".txd")
                    for d in search_dirs if os.path.isdir(d)
                    if os.path.isfile(os.path.join(d, hint + ".txd"))]
            if hits and not needed:
                return hits[0]
            best_h = None
            for c in hits:
                names = _read_txd_names_cached(c)
                cov = (len(needed & names) / len(needed)) if needed else 0.0
                if best_h is None or cov > best_h[0]:
                    best_h = (cov, c)
            if best_h is not None and best_h[0] >= _PICK_BEST_TXD_MIN_COVERAGE:
                return best_h[1]
            # ни один <hint>.txd не покрывает нужное — идём к обычному подбору.

    # Pass 1: same-name shortcut
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        cand = os.path.join(d, dff_basename + ".txd")
        if os.path.isfile(cand):
            return cand

    # Gather every .txd we could pick from
    candidates = []
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if name.lower().endswith('.txd'):
                candidates.append(os.path.join(d, name))
    if not candidates:
        return None

    # Pass 2: coverage-based scoring. `needed` (computed above) is the
    # JUST-imported DFF's referenced texture set; falling back to the
    # full scene-wide collection works for one-shot import but
    # drifts badly across a batch.
    if needed:
        # Умный порядок: TXD с именем, похожим на DFF — первыми (его «свой»
        # TXD обычно там). coverage = доля текстур DFF, что есть в TXD;
        # tie-break — меньший TXD (более специфичный).
        candidates.sort(key=lambda c: -_txd_affinity(c, dff_basename))

        best = None  # (coverage, txd_size, path)

        def _consider(path):
            nonlocal best
            names = _read_txd_names_cached(path)
            cov = len(needed & names) / len(needed)
            if best is None or (cov, -len(names)) > (best[0], -best[1]):
                best = (cov, len(names), path)
            return cov

        # Сначала читаем PROBE самых похожих ПОСЛЕДОВАТЕЛЬНО и выходим на
        # 100% покрытии — «свой» TXD обычно находится за 1–2 чтения, и вся
        # папка не сканируется.
        PROBE = 6
        full_hit = False
        for c in candidates[:PROBE]:
            if _consider(c) >= 0.9999:
                full_hit = True
                break

        # Полного покрытия в топе нет — добиваем остаток. Чтение заголовков
        # I/O-bound → читаем ПАРАЛЛЕЛЬНО (запись в _TXD_NAMES_CACHE идёт по
        # разным ключам, GIL делает это безопасным), затем доскорим из кэша.
        if not full_hit and len(candidates) > PROBE:
            rest = candidates[PROBE:]
            if len(rest) > 8:
                try:
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(
                            max_workers=min(16, len(rest))) as ex:
                        list(ex.map(_read_txd_names_cached, rest))
                except Exception:
                    pass
            for c in rest:
                _consider(c)

        if best is not None and best[0] >= _PICK_BEST_TXD_MIN_COVERAGE:
            return best[2]
        # Best candidate covered less than the threshold — too risky to
        # guess, especially when shared textures (asphalt, glass…) leak
        # across many TXDs. Better to load nothing and surface a warning.

    # Pass 3: solo .txd in the folder — user clearly meant this one.
    if len(candidates) == 1:
        return candidates[0]

    return None


# ──────────────────── Modal import (progress, no freeze) ──────────────
#
# Both the file-picker (`import_dff`) and drag-drop (`drop_dff`) operators
# used to run the whole import synchronously in `execute()`, which froze
# Blender ("Not Responding") for the entire parse + build + TXD-decode of
# every file — exactly the hang the Map / COL importers already avoid.
#
# `_iter_import_dff_files` turns the work into a generator yielding
# ``(current, total, label)`` after each stage, and `_DFFImportModalMixin`
# drives it from a timer-based modal loop with a window progress bar and
# ESC cancel — the same scaffolding the COL importer uses.


def _init_import_stats(stats: dict) -> dict:
    """Seed the shared import-stats schema used by EVERY entry point
    (drag-drop, file-picker, «Import All»). One schema → one set of
    counters → identical reporting everywhere.

    Counters are ints; ``errors`` is ``[(name, err)]``; ``warnings`` /
    ``infos`` are ``[str]``; the ``*_paths`` sets dedupe a file that gets
    reached twice (e.g. a .col both selected AND pulled as a DFF sibling).
    """
    stats.setdefault('imported', 0)
    stats.setdefault('txd_loaded', 0)
    stats.setdefault('col_loaded', 0)
    stats.setdefault('errors', [])
    stats.setdefault('warnings', [])
    stats.setdefault('infos', [])
    stats.setdefault('txd_paths', set())
    stats.setdefault('col_paths', set())
    stats.setdefault('lod_paths', set())
    return stats


# Обычные форматы текстур (НЕ в .txd) — для fallback-поиска на диске.
_LOOSE_IMG_EXTS = ('.png', '.tga', '.dds', '.bmp', '.jpg', '.jpeg',
                   '.tif', '.tiff')


def _pull_loose_textures(loose_dirs, scope_mats, *, recursive=True,
                         _cap=40000):
    """Подтянуть ОБЫЧНЫЕ картинки (png/tga/dds/…) для текстур DFF, которых
    нет в .txd: ищем ``<имя_текстуры>.<ext>`` в папках модели и подпапках,
    грузим и назначаем материалам. Имя текстуры — из label Image-ноды (его
    ставит импорт DFF). Возвращает число назначенных нод."""
    # 1) какие Image-ноды scope остались без картинки (+ их имя текстуры)
    pending = []          # (node, texname)
    wanted = set()        # texname.lower()
    for mat in scope_mats:
        nt = mat.node_tree if (mat and getattr(mat, 'use_nodes', False)) else None
        if nt is None:
            continue
        for n in nt.nodes:
            if getattr(n, 'type', '') == 'TEX_IMAGE' and n.image is None:
                nm = (getattr(n, 'label', '') or '').strip()
                if nm:
                    pending.append((n, nm))
                    wanted.add(nm.lower())
    if not wanted:
        return 0
    # 2) индекс файлов картинок в папках модели (рекурсивно по подпапкам)
    index = {}            # basename_без_ext.lower() -> полный путь
    seen = 0
    for d in loose_dirs:
        if not d or not os.path.isdir(d):
            continue
        if recursive:
            for root, _dirs, files in os.walk(d):
                for f in files:
                    stem, ext = os.path.splitext(f)
                    if ext.lower() in _LOOSE_IMG_EXTS:
                        index.setdefault(stem.lower(), os.path.join(root, f))
                    seen += 1
                    if seen > _cap:
                        break
                if seen > _cap:
                    break
        else:
            try:
                for f in os.listdir(d):
                    stem, ext = os.path.splitext(f)
                    if ext.lower() in _LOOSE_IMG_EXTS:
                        index.setdefault(stem.lower(), os.path.join(d, f))
            except Exception:                          # noqa: BLE001
                pass
    if not index:
        return 0
    # 3) назначить найденные файлы материалам
    assigned = 0
    cache = {}            # texname.lower() -> image
    for node, nm in pending:
        key = nm.lower()
        img = cache.get(key)
        if img is None:
            path = index.get(key)
            if not path:
                continue
            img = bpy.data.images.get(nm)
            if img is None:
                try:
                    img = bpy.data.images.load(path, check_existing=True)
                    try:
                        img.name = nm
                    except Exception:                  # noqa: BLE001
                        pass
                except Exception:                      # noqa: BLE001
                    continue
            cache[key] = img
        node.image = img
        assigned += 1
    return assigned


def import_one_dff(path, context, stats, *, import_game=None,
                   link_alpha=False, txd_hint=None, weld_sharpen=None,
                   skip_2dfx=None):
    """THE canonical interactive single-DFF import: a .dff plus its
    auto-matched TXD. Shared by drag-drop and the file-picker «Import DFF»
    so both behave identically.

    Steps:
      1. import the .dff,
      2. optional source-game resolution (file-picker passes a game),
      3. auto-pull the best-matching .txd, decoding ONLY the textures the
         DFF references (``name_filter``),
      4. optional legacy alpha-link after the TXD.

    NOTE: «Import All» does NOT use this — it is a pure multi-format
    dispatcher that imports exactly the files the user selected (each via
    its own raw importer), with no name-based auto-pull of siblings/TXD.

    A generator yielding short status **labels** (strings); the outer
    driver wraps them with ``(current, total, label)`` for the progress
    bar. ``stats`` must be pre-seeded via ``_init_import_stats``.
    """
    from .txd_import import import_txd as inu_import_txd
    import time as _time

    name = os.path.basename(path)
    directory = os.path.dirname(path)
    dff_name = os.path.splitext(name)[0]

    settings = getattr(context.scene, 'inu_settings', None)
    auto_txd = bool(getattr(settings, 'gtatools_txd_auto_import', True))
    custom_dir = getattr(settings, 'gtatools_txd_import_path', '') or ''
    if custom_dir:
        custom_dir = bpy.path.abspath(custom_dir)

    yield f"DFF: {name}"

    # Snapshot existing materials BEFORE the import so we can tell which
    # materials THIS DFF adds — keeps the auto-TXD picker and name_filter
    # scoped to the current file during a batch.
    mats_before = {m.name for m in bpy.data.materials}
    _t0 = _time.perf_counter()
    try:
        new_objs = import_dff(filepath=path, context=context,
                              weld_sharpen=weld_sharpen, skip_2dfx=skip_2dfx)
        stats['imported'] += 1
    except Exception as e:
        stats['errors'].append((name, str(e)))
        return
    print(f"[TXD timing] {name}: import_dff = {(_time.perf_counter()-_t0)*1000:.0f} ms")

    # Определяем игру модели по RW-версии из заголовка DFF (12 байт) — дёшево
    # и работает на ВСЕХ путях импорта (файл, drag-drop, мост). Нужно и для
    # авто-режима сцены, и для свопа R↔B текстур (III/VC = движок D3D8 →
    # своп, SA = D3D9 → без свопа).
    detected = None
    txd_swap_rb = None          # None → txd-слой сам решит по режиму сцены
    try:
        from ..core import game_versions as gv
        if import_game and import_game != 'AUTO':
            detected = import_game          # игра задана вызвавшим явно
        else:
            detected = gv.detect_game_from_dff(path)
        # Авто-режим сцены: переключается ТОЛЬКО на «свежей» сцене (пустой,
        # дефолт SA); готовый проект не трогаем (защита внутри самой функции).
        switched = gv.maybe_set_game_from_import(context.scene, detected)
        if switched:
            stats['infos'].append(f"{name} → game={detected}")
        elif import_game is not None:
            # Предупреждение о несовпадении — только при файловом импорте,
            # чтобы не спамить на drag-drop / мосте.
            warn = gv.check_game_mismatch_warning(context.scene, detected)
            if warn:
                stats['warnings'].append(warn)
        # Per-model решение по свопу — по игре самой модели, а не по режиму.
        if detected in (gv.GAME_III, gv.GAME_VC):
            txd_swap_rb = True
        elif detected == gv.GAME_SA:
            txd_swap_rb = False
    except Exception:
        detected = None
        txd_swap_rb = None

    if auto_txd:
        # Auto-pull a matching TXD: same-name → content-coverage → solo.
        yield f"TXD: {name}"
        search_dirs = []
        if custom_dir and os.path.isdir(custom_dir):
            search_dirs.append(custom_dir)
        search_dirs.append(directory)

        # Общие (shared) TXD не лежат рядом с моделью: дорога rd_Road2B50
        # ссылается на «generic», а generic.txd находится в <игра>\models.
        # Добавляем папку игры в поиск, чтобы такие txd подхватывались сами.
        # Источник пути: сначала папка моста (ariane_bridge_path), затем
        # общий Game Root — что из них задано.
        for _root_key in ('ariane_bridge_path', 'gtatools_game_root'):
            _root = getattr(settings, _root_key, '') or ''
            if not _root:
                continue
            _root = bpy.path.abspath(_root)
            for _sub in (os.path.join(_root, 'models'), _root):
                if os.path.isdir(_sub) and _sub not in search_dirs:
                    search_dirs.append(_sub)

        # Область = материалы по слотам объектов этого DFF (и нужные им
        # имена текстур). Покрывает и переиспользованные материалы, когда
        # модель дропнута в сцену с уже загруженной картой — иначе они
        # выпадали из назначения и оставались чёрными.
        # Авто-TXD — НЕ-фатальный: любая ошибка подбора/области не должна
        # ронять импорт модели (иначе в мосте модель импортится, но остаётся
        # без размещения/тега — а её LOD встаёт → «только лоды»).
        try:
            _scope_mats, needed = _collect_dff_scope(new_objs)
            _t1 = _time.perf_counter()
            txd_file = _pick_best_txd(search_dirs, dff_name, needed_names=needed,
                                      txd_hint=txd_hint)
            print(f"[TXD timing] {name}: _pick_best_txd = "
                  f"{(_time.perf_counter()-_t1)*1000:.0f} ms "
                  f"(found={os.path.basename(txd_file) if txd_file else None})")
        except Exception as _e:                    # noqa: BLE001
            print(f"[TXD] auto-TXD pick failed for {name}: {_e!r}")
            stats.setdefault('warnings', []).append(
                f"{name}: {T('авто-TXD пропущен')} ({_e})")
            _scope_mats, needed, txd_file = [], set(), None
        # NB: НЕ пропускаем уже виденный txd-путь. Раньше дедуп по пути ломал
        # пару LOD+основная модель, делящих один .txd: LOD обрабатывался
        # первым, грузил txd с name_filter всего на свою 1 текстуру и «застолбя»
        # путь — основная модель потом пропускалась целиком и оставалась без
        # текстур. Теперь каждый DFF грузит из общего txd ИМЕННО свои текстуры
        # (name_filter) на свои материалы (material_scope); повторный декод
        # дёшев — image-датаблоки переиспользуются по имени.
        if txd_file:
            try:
                # Only decode textures the just-imported DFF references —
                # avoids spawning dozens of orphan images (and a long DXT
                # decode freeze) from shared archives like vehicle.txd.
                _t2 = _time.perf_counter()
                # material_scope ограничивает assign материалами этого DFF —
                # иначе он перебирал бы все тысячи материалов сцены (12.5с).
                images = inu_import_txd(
                    filepath=txd_file,
                    name_filter=needed if needed else None,
                    material_scope=_scope_mats,
                    swap_rb=txd_swap_rb)
                print(f"[TXD timing] {name}: import_txd decode = "
                      f"{(_time.perf_counter()-_t2)*1000:.0f} ms "
                      f"({len(images)} tex)")
                stats['txd_paths'].add(txd_file)
                stats['txd_loaded'] += 1
                stats['infos'].append(
                    f"TXD: {len(images)} ({os.path.basename(txd_file)})")
                if link_alpha:
                    # Legacy "Connect Textures": per-pixel alpha test so
                    # foliage/fences/windows pick up alpha-test transparency
                    # automatically. Idempotent.
                    #
                    # ВАЖНО для скорости: проходим ТОЛЬКО по материалам этого
                    # DFF (_scope_mats — по слотам объектов), а не по всем
                    # bpy.data.materials. Раньше на загруженной карте это
                    # перебирало тысячи чужих материалов и читало буфер
                    # пикселей каждой текстуры заново. Кэш в texture_ops
                    # сканирует каждую картинку один раз.
                    from .texture_ops import (
                        link_material_alpha_if_textured, clear_alpha_cache)
                    clear_alpha_cache()
                    _t3 = _time.perf_counter()
                    for material in _scope_mats:
                        link_material_alpha_if_textured(material)
                    print(f"[TXD timing] {name}: alpha-link = "
                          f"{(_time.perf_counter()-_t3)*1000:.0f} ms "
                          f"({len(_scope_mats)} mats)")
            except Exception as e:
                stats['warnings'].append(
                    f"{name}: TXD {os.path.basename(txd_file)}: {e}")
        elif not txd_file:
            dirs_str = " | ".join(search_dirs)
            stats['warnings'].append(
                f"{name}: {T('TXD не найден')} '{dff_name}.txd' "
                f"({T('и нет .txd с покрытием ≥50% в')} {dirs_str})")

        # Fallback: текстуры НЕ из TXD — обычные картинки (png/tga/dds/…) в
        # папке модели и подпапках. Тянем то, что TXD не покрыл (или всё, если
        # TXD не найден). Работает и в drag-drop (общий путь import_one_dff).
        try:
            _loose_dirs = [d for d in (custom_dir, directory) if d]
            _n_loose = _pull_loose_textures(_loose_dirs, _scope_mats)
            if _n_loose:
                stats['infos'].append(
                    f"{T('текстуры из файлов')}: {_n_loose}")
        except Exception as _e:                        # noqa: BLE001
            print(f"[loose-tex] {name}: {_e!r}")


def _iter_import_dff_files(paths, context, stats, *,
                           import_game=None, link_alpha=False, skip_2dfx=None):
    """Drive ``import_one_dff`` over a list of .dff paths, yielding
    ``(current, total, label)`` for the progress bar. Thin wrapper — the
    real per-file work lives in the shared ``import_one_dff`` so drag-drop
    and the file-picker import run byte-for-byte the same path."""
    _init_import_stats(stats)
    total = max(len(paths), 1)
    for i, path in enumerate(paths):
        for label in import_one_dff(
                path, context, stats,
                import_game=import_game, link_alpha=link_alpha,
                skip_2dfx=skip_2dfx):
            yield (i, total, label)
    yield (total, total, T("готово"))


class _DFFImportModalMixin:
    """Shared modal-loop scaffolding for the two DFF import operators.

    Owns the timer / progress-bar / status-bar plumbing so the operators
    only provide ``_collect_paths()`` and the import options via
    ``_import_game`` / ``_link_alpha``. Mirrors ``_COLImportModalMixin``.
    """

    _timer = None
    _gen = None
    _stats: dict = None
    # Subclasses override these to tune per-source behaviour.
    _import_game = None   # None → skip game detection (drag-drop)
    _link_alpha = False   # True → run alpha-link after TXD (file-picker)
    _skip_2dfx = None     # None → import_dff reads the map setting; ops set it

    def _collect_paths(self) -> list:
        raise NotImplementedError

    def _start_modal(self, context):
        paths = self._collect_paths()
        if not paths:
            self.report({'WARNING'}, T("Не выбран ни один .dff файл"))
            return {'CANCELLED'}

        self._stats = {}
        self._gen = _iter_import_dff_files(
            paths, context, self._stats,
            import_game=self._import_game, link_alpha=self._link_alpha,
            skip_2dfx=self._skip_2dfx)

        wm = context.window_manager
        wm.progress_begin(0, 100)
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(T("DFF Import: подготовка..."))
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC':
            self._finish(context)
            self.report({'WARNING'}, T("DFF Import отменён"))
            return {'CANCELLED'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        import time
        wm = context.window_manager
        deadline = time.monotonic() + 0.05  # ~20 fps frame budget

        while time.monotonic() < deadline:
            try:
                current, total, label = next(self._gen)
            except StopIteration:
                self._finish(context)
                return self._report_done()
            except Exception as e:
                self._finish(context)
                self.report({'ERROR'}, f"{T('Ошибка импорта DFF')}: {e}")
                print(f"[dff_import] aborted: {e}")
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}

            pct = int(100 * current / max(total, 1))
            wm.progress_update(pct)
            context.workspace.status_text_set(
                f"DFF Import: {current}/{total} — {label}")

        return {'RUNNING_MODAL'}

    def _report_done(self):
        stats = self._stats or {}
        imported = stats.get('imported', 0)
        errors = stats.get('errors', [])
        if errors and not imported:
            err_msg = '; '.join(f"{n}: {e}" for n, e in errors[:3])
            self.report({'ERROR'}, f"DFF: {err_msg}")
            return {'CANCELLED'}
        # Surface accumulated warnings (TXD-not-found, game mismatch).
        for w in stats.get('warnings', []):
            self.report({'WARNING'}, w)
        msg = f"DFF: {imported}"
        txd = stats.get('txd_loaded', 0)
        if txd:
            msg += f", TXD: {txd}"
        if errors:
            msg += f" ({len(errors)} {T('с ошибкой')})"
        self.report({'INFO'}, msg)
        return {'FINISHED'}

    def _finish(self, context):
        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        try:
            context.window_manager.progress_end()
        except Exception:
            pass
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass
        self._gen = None


# ──────────────────── Blender operator wrapper ────────────────────────

class GTATOOLS_OT_import_dff(_DFFImportModalMixin, bpy.types.Operator):
    """Импорт DFF модели GTA SA с прогресс-баром.
    ESC прерывает импорт, уже созданные объекты остаются в сцене."""
    bl_idname = "gtatools.import_dff"
    bl_label = "INU: Import DFF (.dff)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    # Multi-select support: the file browser fills `files` (+ `directory`)
    # when the user shift/ctrl-picks several .dff. Without these props the
    # operator only ever saw `filepath` (the last-clicked file) and
    # imported a single model no matter how many were selected.
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(default="*.dff", options={'HIDDEN'})

    # User-overridable game source for this import. Default 'AUTO'
    # delegates to game_versions.detect_game_from_dff (RW-version
    # header read). Explicit III/VC/SA bypasses detection and tags
    # the imported objects with that source_game — useful when the
    # file's RW version was misset by the original packager and
    # detection would land on the wrong game.
    import_game: bpy.props.EnumProperty(
        name=T("Игра"),
        description=T("Из какой игры импортируем. Auto — определить по RW-версии файла"),
        items=[
            ('AUTO', T("Авто-определение"), T("Прочитать RW версию и угадать игру")),
            ('III',  "GTA III",  T("Принудительно III")),
            ('VC',   "Vice City", T("Принудительно VC")),
            ('SA',   "San Andreas", T("Принудительно SA")),
        ],
        default='AUTO')

    import_2dfx: bpy.props.BoolProperty(
        name=T("Импортировать 2DFX"),
        description=T("Создавать пустышки-эффекты 2DFX из DFF (лампы/короны, "
                      "частицы, ped attractor, sun glare, знаки и т.д.). "
                      "Выключи, чтобы импортировать модель без эффектов"),
        default=True)

    def invoke(self, context, event):
        # дефолт 2DFX из scene-настроек, можно переопределить в диалоге.
        # import_game здесь НЕ трогаем — у «Import DFF» свой AUTO по умолчанию
        # (gtatools_import_game из окна Import All — только SA/VC/III).
        s = getattr(context.scene, 'inu_settings', None)
        if s is not None:
            self.import_2dfx = bool(getattr(s, 'gtatools_import_2dfx', True))
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        """Help-panel that shows the user how Auto-TXD picks a .txd
        next to the chosen DFF — explains the same-name → score-by-
        content → first-fallback strategy and the toggle that disables
        the whole thing."""
        layout = self.layout
        scene = context.scene

        # Game-source override — sits at the top so user sees it
        # before the TXD-help block.
        layout.prop(self, "import_game")
        # Платформа (PC / Mobile). Mobile-DFF распознаётся по данным сам —
        # это выбор/дефолт (влияет на дальнейший экспорт и подсказки).
        layout.prop(scene.inu_settings, "gtatools_platform", text=T("Платформа"))
        layout.separator()

        # Auto-weld / sharp-edges toggle — turn OFF for custom models.
        # Хранится в AddonPreferences → запоминается глобально (дефолт OFF).
        from ..tools.user_data import get_addon_prefs
        _prefs = get_addon_prefs()
        if _prefs is not None:
            layout.prop(_prefs, "import_weld_sharpen",
                        text=T("Стандартная модель GTA SA (vanilla)"))
            if not _prefs.import_weld_sharpen:
                layout.label(text=T("Кастом: связать + сохранить заборы"),
                             **inu_icon(safe_icon('INFO')))
        layout.separator()

        layout.prop(self, "import_2dfx")
        layout.prop(scene.inu_settings, "gtatools_txd_auto_import", text=T("Авто TXD"))

        if not getattr(scene.inu_settings, 'gtatools_txd_auto_import', True):
            layout.label(text=T("TXD не будет загружаться автоматически"),
                         **inu_icon(safe_icon('INFO')))
            return

        box = layout.box()
        box.label(text=T("Как ищется TXD:"), **inu_icon(safe_icon('QUESTION')))
        col = box.column(align=True)
        col.scale_y = 0.85
        col.label(text=T("1. <имя_dff>.txd в той же папке"))
        col.label(text=T("2. .txd с покрытием ≥50% текстур DFF"))
        col.label(text=T("   (выбирается с макс. покрытием,"))
        col.label(text=T("    меньший по размеру при равенстве)"))
        col.label(text=T("3. Единственный .txd в папке"))
        col.label(text=T("Иначе — warning, ничего не грузится"))

        custom_dir = getattr(scene.inu_settings, 'gtatools_txd_import_path', '')
        if custom_dir:
            box.label(text=f"+ {T('доп. папка')}: {custom_dir}",
                      **inu_icon(safe_icon('FILE_FOLDER')))

    _link_alpha = True  # run legacy alpha-link after TXD loads

    def _collect_paths(self):
        # Prefer the multi-select list; fall back to the single filepath
        # (e.g. invoked programmatically with just `filepath`).
        out = []
        directory = self.directory or os.path.dirname(self.filepath)
        for f in self.files:
            if not f.name:
                continue
            path = os.path.join(directory, f.name)
            if os.path.isfile(path) and path.lower().endswith('.dff'):
                out.append(path)
        if not out and self.filepath:
            out.append(self.filepath)
        return out

    def execute(self, context):
        # Game-source detection runs per-file inside the generator;
        # thread the user's choice through so AUTO still falls back to
        # RW-version detection and explicit III/VC/SA bypasses it.
        self._import_game = self.import_game
        self._skip_2dfx = not self.import_2dfx
        return self._start_modal(context)


class GTATOOLS_OT_drop_dff(_DFFImportModalMixin, bpy.types.Operator):
    """Импорт DFF при перетаскивании во viewport (батч, прогресс + ESC).

    Принимает несколько файлов сразу (батч), каждый импортируется
    как отдельная модель. Та же логика автоматического подцепления
    одноимённого .txd, что и в обычном импорте.
    """
    bl_idname = "gtatools.drop_dff"
    bl_label = "INU: Import DFF (Drop)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')

    import_2dfx: bpy.props.BoolProperty(
        name=T("Импортировать 2DFX"),
        description=T("Создавать пустышки-эффекты 2DFX из DFF (лампы/короны, "
                      "частицы, ped attractor, sun glare, знаки и т.д.). "
                      "Выключи, чтобы импортировать модель без эффектов"),
        default=True)

    def _collect_paths(self):
        out = []
        for f in self.files:
            path = os.path.join(self.directory, f.name)
            if os.path.isfile(path) and path.lower().endswith('.dff'):
                out.append(path)
        return out

    def invoke(self, context, event):
        # Show a small chooser ON DROP so the user picks vanilla vs custom
        # import each time. The checkboxes edit the scene settings directly,
        # which the import step (execute → import_dff → import_dff_from_clump)
        # reads. Fall back to a silent import if the scene isn't reachable.
        if getattr(context.scene, 'inu_settings', None) is None:
            return self.execute(context)
        # дефолт «Импортировать 2DFX» из панели «Импорт»
        self.import_2dfx = bool(getattr(context.scene.inu_settings,
                                        'gtatools_import_2dfx', True))
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        st = context.scene.inu_settings
        layout.label(text=T("Как импортировать DFF?"),
                     **inu_icon(safe_icon('IMPORT')))
        # Галочка хранится в AddonPreferences → запоминается глобально (дефолт OFF).
        from ..tools.user_data import get_addon_prefs
        _prefs = get_addon_prefs()
        if _prefs is not None:
            layout.prop(_prefs, "import_weld_sharpen",
                        text=T("Стандартная модель GTA SA (vanilla)"))
            if not _prefs.import_weld_sharpen:
                layout.label(text=T("Кастом: связать + сохранить заборы"),
                             **inu_icon(safe_icon('INFO')))
        layout.prop(self, "import_2dfx")
        layout.prop(st, "gtatools_txd_auto_import", text=T("Авто TXD"))

    def execute(self, context):
        # FileHandler-drop оператор получает таймер-тики МОДАЛКИ ненадёжно
        # (обычно только первый), поэтому _start_modal тут не работает: шаг
        # загрузки TXD ждал следующего тика, который при drop не приходит →
        # DFF есть, TXD нет (регрессия v2.0.4). Раньше из-за этого импорт
        # гнался ПОЛНОСТЬЮ синхронно в execute() → Blender фризился без
        # прогресса на всё время парса/билда.
        #
        # Теперь генератор крутится из bpy.app.timers — это главный цикл
        # приложения, а не модальные тики оператора: между вызовами идёт
        # перерисовка (виден прогресс-бар, ESC не нужен — UI отзывчив), и
        # шаг TXD выполняется надёжно. execute() сразу возвращает FINISHED,
        # поэтому self.report из таймера уже не покажется — итог/варнинги
        # пишем в консоль.
        paths = self._collect_paths()
        if not paths:
            self.report({'WARNING'}, T("Не выбран ни один .dff файл"))
            return {'CANCELLED'}

        stats = {}
        self._stats = stats
        gen = _iter_import_dff_files(
            paths, context, stats,
            import_game=self._import_game, link_alpha=self._link_alpha,
            skip_2dfx=not self.import_2dfx)

        wm = context.window_manager
        workspace = context.workspace
        wm.progress_begin(0, 100)

        def _drive():
            import time
            deadline = time.monotonic() + 0.05  # ~20 fps frame budget
            while time.monotonic() < deadline:
                try:
                    current, total, label = next(gen)
                except StopIteration:
                    wm.progress_end()
                    try:
                        workspace.status_text_set(None)
                    except Exception:
                        pass
                    for w in stats.get('warnings', []):
                        print(f"[drop_dff] WARN: {w}")
                    print(f"[drop_dff] done: DFF {stats.get('imported', 0)}, "
                          f"TXD {stats.get('txd_loaded', 0)}")
                    return None  # stop the timer
                except Exception as e:
                    wm.progress_end()
                    try:
                        workspace.status_text_set(None)
                    except Exception:
                        pass
                    print(f"[drop_dff] aborted: {e}")
                    import traceback
                    traceback.print_exc()
                    return None
                wm.progress_update(int(100 * current / max(total, 1)))
                try:
                    workspace.status_text_set(
                        f"DFF Import: {current}/{total} — {label}")
                except Exception:
                    pass
            return 0.01  # yield to the UI for a redraw, then continue

        bpy.app.timers.register(_drive, first_interval=0.0)
        return {'FINISHED'}


if hasattr(bpy.types, 'FileHandler'):
    class GTATOOLS_FH_dff_drop(bpy.types.FileHandler):
        """File Handler для перетаскивания DFF во viewport"""
        bl_idname = "GTATOOLS_FH_dff_drop"
        bl_label = "GTA DFF Drop"
        bl_import_operator = "gtatools.drop_dff"
        bl_file_extensions = ".dff"

        @classmethod
        def poll_drop(cls, context):
            return context.area and context.area.type == 'VIEW_3D'


