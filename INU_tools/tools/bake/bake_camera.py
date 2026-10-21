# INU_tools.tools.bake.bake_camera — режим «Камера» подсистемы запекания.
#
# Рендерит объект ортокамерой в текстуру с прозрачностью — метод для
# billboard/impostor-деревьев. Камера видит весь силуэт целиком, альфа
# берётся из film_transparent, силуэт растягивается на весь кадр.
#
# ДВИЖОК EEVEE (тот же, что в Material Preview вьюпорта) — материалы
# листвы с alpha-картами выглядят так же, как их видит пользователь;
# Cycles интерпретировал их иначе и давал чёрное. Освещение —
# фронтальный SUN вдоль взгляда камеры + ambient world, поэтому видимая
# сторона всегда освещена (а не уходит в чёрный под одним ambient).
#
# Рендер идёт в ОТДЕЛЬНОЙ временной сцене: world/compositor/view-layer/
# исключённые коллекции/color-management пользователя НЕ влияют. После
# рендера временная сцена удаляется, исходная сцена не трогается.

import math
import os
import tempfile

import bpy
import mathutils
import numpy as np

from . import bake_maps
from .bake_maps import _make_bake_world, BAKE_WORLD_NAME


def _eval_aabb(obj):
    """world-space AABB по ВЫЧИСЛЕННОЙ геометрии (учитывает модификаторы).
    Возвращает (center, dim). Fallback на bound_box при ошибке."""
    mw = obj.matrix_world
    try:
        deps = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(deps)
        me = ev.to_mesh()
        if me is not None and len(me.vertices):
            co = np.empty(len(me.vertices) * 3, dtype=np.float32)
            me.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3)
            M = np.array(mw, dtype=np.float32)
            homo = np.concatenate([co, np.ones((len(co), 1), np.float32)], axis=1)
            wp = (homo @ M.T)[:, :3]
            mn = wp.min(axis=0)
            mx = wp.max(axis=0)
            ev.to_mesh_clear()
            center = mathutils.Vector(((mn + mx) * 0.5).tolist())
            dim = mathutils.Vector((mx - mn).tolist())
            return center, dim
    except Exception:
        pass
    cs = [mw @ mathutils.Vector((c[0], c[1], c[2])) for c in obj.bound_box]
    xs = [c.x for c in cs]; ys = [c.y for c in cs]; zs = [c.z for c in cs]
    mn = mathutils.Vector((min(xs), min(ys), min(zs)))
    mx = mathutils.Vector((max(xs), max(ys), max(zs)))
    return (mn + mx) * 0.5, (mx - mn)


def _albedo_override(mat):
    """Временно подменить выход материала на Emission(Base Color) — рендер
    отдаёт ЧИСТЫЙ базовый цвет (albedo) без света и теней. Альфа здесь НЕ
    важна (берётся отдельным проходом по оригинальному материалу).
    Возвращает restore-замыкание."""
    if not getattr(mat, 'use_nodes', False) or mat.node_tree is None:
        return lambda: None
    nt = mat.node_tree
    out = next((n for n in nt.nodes
                if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None) \
        or next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None:
        return lambda: None
    surf = out.inputs['Surface']
    orig_from = surf.links[0].from_socket if surf.is_linked else None

    base_src = None
    base_val = (0.8, 0.8, 0.8, 1.0)
    alpha_src = None
    alpha_val = 1.0
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is not None:
        bc = bsdf.inputs.get('Base Color')
        if bc is not None:
            base_val = tuple(bc.default_value)
            if bc.is_linked:
                base_src = bc.links[0].from_socket
        al = bsdf.inputs.get('Alpha')
        if al is not None:
            alpha_val = float(al.default_value)
            if al.is_linked:
                alpha_src = al.links[0].from_socket

    # Альфа материала — чтобы emission ПРОПУСКАЛ сквозь прозрачные части
    # карт (иначе чёрный фон передней карты перекроет задние листья).
    # Источники по приоритету: Mix-Shader(Transparent) fac → Principled.Alpha
    # → альфа той же текстуры, что Base Color.
    src_node = orig_from.node if orig_from is not None else None
    if src_node is not None and src_node.type == 'MIX_SHADER':
        fac = src_node.inputs['Fac']
        if fac.is_linked:
            alpha_src = fac.links[0].from_socket
        else:
            alpha_val = float(fac.default_value)
    if alpha_src is None and base_src is not None:
        bn = base_src.node
        if getattr(bn, 'type', '') == 'TEX_IMAGE':
            a_out = bn.outputs.get('Alpha')
            if a_out is not None:
                alpha_src = a_out

    made = []
    emit = nt.nodes.new('ShaderNodeEmission')
    emit.label = 'INU_albedo'
    made.append(emit)
    if base_src is not None:
        nt.links.new(base_src, emit.inputs['Color'])
    else:
        emit.inputs['Color'].default_value = base_val

    if alpha_src is not None or alpha_val < 0.999:
        trans = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        made += [trans, mix]
        if alpha_src is not None:
            nt.links.new(alpha_src, mix.inputs['Fac'])
        else:
            mix.inputs['Fac'].default_value = alpha_val
        nt.links.new(trans.outputs[0], mix.inputs[1])
        nt.links.new(emit.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], surf)
    else:
        nt.links.new(emit.outputs[0], surf)

    def restore():
        for n in made:
            try:
                nt.nodes.remove(n)
            except Exception:
                pass
        if orig_from is not None:
            try:
                nt.links.new(orig_from, surf)
            except Exception:
                pass
    return restore


def plane_normal_world(obj):
    """Усреднённая нормаль полигонов объекта в world space (нормализ.).
    Для billboard-плоскости — её «лицевое» направление."""
    me = obj.data
    mw3 = obj.matrix_world.to_3x3()
    nm = mathutils.Vector((0.0, 0.0, 0.0))
    for p in me.polygons:
        nm += (mw3 @ p.normal)
    if nm.length < 1e-6:
        return mathutils.Vector((0.0, -1.0, 0.0))
    return nm.normalized()


def _basis_from_normal(normal):
    """Базис камеры из нормали плоскости: возвращает (view_dir, quat,
    right, up). Камера смотрит ПРОТИВ нормали (на лицевую сторону),
    «вверх» тянется к мировому +Z. Один и тот же базис используют и
    камера, и перепроекция UV — поэтому текстура ложится точь-в-точь."""
    view_dir = (-normal).normalized()
    quat = view_dir.to_track_quat('-Z', 'Y')
    right = (quat @ mathutils.Vector((1.0, 0.0, 0.0))).normalized()
    up = (quat @ mathutils.Vector((0.0, 1.0, 0.0))).normalized()
    return view_dir, quat, right, up


def reproject_billboard_uv(low, normal, padding=0.0, uv_name=None):
    """Перепроецировать UV `low` из того же базиса И той же рамки, что камера
    (нормаль плоскости + padding, центрировано по bbox плоскости). Маппинг
    идентичен проекции камеры, поэтому текстура ложится на плоскость
    точь-в-точь, без сдвига/зеркала/поворота.

    ``uv_name`` — если задан (режим «Не сбрасывать мою UV»), проекция пишется в
    ОТДЕЛЬНЫЙ слой с этим именем (создаётся при отсутствии), а активная
    (пользовательская) UV не трогается и остаётся активной. Если None — как
    раньше: перезаписывается активная UV."""
    _vd, _q, right, up = _basis_from_normal(normal)
    me = low.data
    mw = low.matrix_world
    coords = [mw @ v.co for v in me.vertices]
    if not coords:
        return
    rs = [right.dot(c) for c in coords]
    us = [up.dot(c) for c in coords]
    cr = (min(rs) + max(rs)) * 0.5
    cu = (min(us) + max(us)) * 0.5
    k = 1.0 + padding * 2.0
    rspan = max((max(rs) - min(rs)) * k, 1e-9)
    uspan = max((max(us) - min(us)) * k, 1e-9)
    prev_active = me.uv_layers.active
    if uv_name:
        uv = me.uv_layers.get(uv_name) or me.uv_layers.new(name=uv_name)
    else:
        uv = me.uv_layers.active or me.uv_layers.new(name="BakeUV")
    for loop in me.loops:
        c = coords[loop.vertex_index]
        uv.data[loop.index].uv = ((right.dot(c) - cr) / rspan + 0.5,
                                  (up.dot(c) - cu) / uspan + 0.5)
    # Вернуть активной пользовательскую UV (создание слоя могло переключить).
    if uv_name and prev_active is not None:
        me.uv_layers.active = prev_active
    me.update()


# Ракурс → (направление от центра, rotation_euler, оси ширины/высоты).
_CAM_AXES = {
    'FRONT': ((0, -1, 0), (math.radians(90), 0, 0), ('x', 'z')),
    'BACK':  ((0, 1, 0), (math.radians(90), 0, math.radians(180)), ('x', 'z')),
    'RIGHT': ((1, 0, 0), (math.radians(90), 0, math.radians(90)), ('y', 'z')),
    'LEFT':  ((-1, 0, 0), (math.radians(90), 0, math.radians(-90)), ('y', 'z')),
    'TOP':   ((0, 0, 1), (0, 0, 0), ('x', 'y')),
}


def render_one_map_camera(context, map_def, obj, image, *, params=None,
                          samples=None, axis='FRONT', padding=0.05,
                          keep_visible=(), orient_normal=None, frame_obj=None):
    """Захватить карту `map_def` объекта `obj` в `image` рендером
    ортокамеры (EEVEE, прозрачный фон) во временной изолированной сцене.

    orient_normal (Vector или None) — если задан, камера ориентируется ПО
    НОРМАЛИ (billboard-плоскости): смотрит против неё, «вверх» к +Z. Иначе
    — по мировой оси `axis`.

    frame_obj (Object или None) — объект, по bbox которого КАДРИРУЕТСЯ
    камера (центр + габариты). Для billboard это low-плоскость: камера
    снимает ИМЕННО её область, а рендерит `obj` (дерево) в ней. UV
    плоскости перепроецируется той же рамкой → точное совпадение без
    сдвига. None → кадр по самому `obj`.
    """
    if params is None:
        params = bake_maps.DEFAULT_PARAMS

    # Bevel и пр. node-group-карты подменяют материал на datablock obj.
    map_teardown = (lambda: None)
    if map_def.node_group_builder is not None:
        map_teardown = bake_maps.prepare_map(map_def, obj, context, params)

    frame = frame_obj if frame_obj is not None else obj
    center, dim = _eval_aabb(frame)         # КАДР — по плоскости (frame)
    rcenter, rdim = _eval_aabb(obj)         # дерево — для дальности камеры
    diag = max(dim.length, rdim.length, 0.001)
    dist = diag * 2.0 + 1.0

    if orient_normal is not None:
        # Ракурс по нормали плоскости. vw/vh — габариты bbox РАМКИ (frame)
        # на right/up камеры (тот же базис и центр, что у перепроекции UV).
        view_dir, quat, right, up = _basis_from_normal(orient_normal)
        rot = quat.to_euler()
        cam_loc = center + orient_normal.normalized() * dist
        hd = dim * 0.5
        corners = [center + mathutils.Vector((sx * hd.x, sy * hd.y, sz * hd.z))
                   for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        rs = [right.dot(c) for c in corners]
        us = [up.dot(c) for c in corners]
        vw = max(max(rs) - min(rs), 1e-6)
        vh = max(max(us) - min(us), 1e-6)
    else:
        direction, rot, (wax, hax) = _CAM_AXES.get(axis, _CAM_AXES['FRONT'])
        vw = max(getattr(dim, wax), 1e-6)
        vh = max(getattr(dim, hax), 1e-6)
        cam_loc = center + mathutils.Vector(direction) * dist

    # Рендер идёт В ГЛАВНОЙ СЦЕНЕ (без создания временной — быстрее:
    # depsgraph уже готов, шейдеры не перекомпилируются). Все настройки
    # сцены снапшотятся и восстанавливаются в finally.
    scene = context.scene
    r = scene.render
    vs = scene.view_settings
    cam_obj = cam_data = None
    lights = []
    fpath = None

    scale = float(params.get('light_energy_scale', 1.0))
    eev = getattr(scene, 'eevee', None)
    cyc = getattr(scene, 'cycles', None)

    snap = {
        'engine': r.engine, 'film': r.film_transparent,
        'rx': r.resolution_x, 'ry': r.resolution_y, 'pct': r.resolution_percentage,
        'pax': r.pixel_aspect_x, 'pay': r.pixel_aspect_y,
        'fp': r.filepath, 'ff': r.image_settings.file_format,
        'cm': r.image_settings.color_mode,
        'vt': vs.view_transform, 'look': vs.look,
        'exp': vs.exposure, 'gamma': vs.gamma,
        'world': scene.world, 'cam': scene.camera, 'nodes': scene.use_nodes,
        'eevee_s': getattr(eev, 'taa_render_samples', None),
        'cycles_s': getattr(cyc, 'samples', None),
    }
    hidden = [(o, o.hide_render) for o in scene.objects]
    try:
        # ── изоляция: рендерим только obj (+ keep_visible) ──
        keep = {obj}
        keep.update(keep_visible or ())
        for o in scene.objects:
            try:
                o.hide_render = (o not in keep)
            except Exception:
                pass

        # ── движок EEVEE (как Material Preview) — ВЫБИРАЕМ ДИНАМИЧЕСКИ:
        # имя зависит от сборки ('BLENDER_EEVEE' или 'BLENDER_EEVEE_NEXT'),
        # пробуем реально присвоить. Иначе рендерили бы Cycles (≠ то, что
        # видно в Material Preview) — отсюда были чёрные/иные результаты.
        eevee_engine = None
        for _eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
            try:
                r.engine = _eng
                eevee_engine = _eng
                break
            except Exception:
                pass
        eev = getattr(scene, 'eevee', None)   # обновить после смены движка
        scene.use_nodes = False          # игнорируем compositor пользователя
        # Для flat-albedo сэмплов почти не надо (нет шума) — это и ускоряет.
        s_use = int(samples) if samples else 16
        try:
            if eev is not None:
                eev.taa_render_samples = s_use
            elif cyc is not None:
                cyc.samples = s_use
        except Exception:
            pass

        r.film_transparent = True
        r.resolution_x = image.size[0]
        r.resolution_y = image.size[1]
        r.resolution_percentage = 100
        r.image_settings.file_format = 'PNG'
        r.image_settings.color_mode = 'RGBA'
        try:
            vs.view_transform = 'Standard'
            vs.look = 'None'
            vs.exposure = 0.0
            vs.gamma = 1.0
        except Exception:
            pass

        # film_transparent — для альфы из силуэта.
        scene.world = _make_bake_world(0.6, (1.0, 1.0, 1.0))
        use_flat = (map_def.bake_type == 'DIFFUSE' and not map_def.needs_light)
        if map_def.needs_light:
            # Светозависимые карты (Shadow/Diffuse-Lit) — свой риг.
            for euler_deg, ef in bake_maps._RIG_SPECS.get(
                    map_def.rig_kind, bake_maps._RIG_SPECS['DOME']):
                ld = bpy.data.lights.new('INU_CamSun', type='SUN')
                ld.energy = ef * scale
                lo = bpy.data.objects.new('INU_CamSun', ld)
                lo.location = center
                lo.rotation_euler = (math.radians(euler_deg[0]),
                                     math.radians(euler_deg[1]),
                                     math.radians(euler_deg[2]))
                scene.collection.objects.link(lo)
                lights.append(lo)
        elif not use_flat:
            # Bevel и пр. — фронтальный SUN.
            ld = bpy.data.lights.new('INU_CamSun', type='SUN')
            ld.energy = 1.5 * scale
            lo = bpy.data.objects.new('INU_CamSun', ld)
            lo.location = center
            lo.rotation_euler = rot
            scene.collection.objects.link(lo)
            lights.append(lo)

        # ── камера (ortho, анаморфное растяжение на весь кадр) ──
        cam_data = bpy.data.cameras.new("INU_BakeCam")
        cam_data.type = 'ORTHO'
        cam_data.sensor_fit = 'HORIZONTAL'
        cam_data.ortho_scale = max(vw * (1.0 + padding * 2.0), 0.001)
        cam_data.clip_start = 0.0
        cam_data.clip_end = dist * 3.0
        cam_obj = bpy.data.objects.new("INU_BakeCam", cam_data)
        cam_obj.location = cam_loc
        cam_obj.rotation_euler = rot
        scene.collection.objects.link(cam_obj)
        scene.camera = cam_obj
        if vw >= vh:
            r.pixel_aspect_x = vw / vh
            r.pixel_aspect_y = 1.0
        else:
            r.pixel_aspect_x = 1.0
            r.pixel_aspect_y = vh / vw

        def _render_pixels():
            """Один проход рендера → numpy RGBA (или None при размере≠)."""
            fd2, fp2 = tempfile.mkstemp(suffix='.png', prefix='inu_cam_')
            os.close(fd2)
            r.filepath = fp2
            try:
                bpy.ops.render.render(write_still=True)
                ld2 = bpy.data.images.load(fp2)
                try:
                    if tuple(ld2.size) != tuple(image.size):
                        return None
                    b = np.empty(len(ld2.pixels), dtype=np.float32)
                    ld2.pixels.foreach_get(b)
                    return b
                finally:
                    try:
                        bpy.data.images.remove(ld2)
                    except Exception:
                        pass
            finally:
                if os.path.exists(fp2):
                    try:
                        os.remove(fp2)
                    except Exception:
                        pass

        if use_flat:
            # ДВА ПРОХОДА (план: albedo как в TexTools + альфа отдельно):
            #  1) RGB = чистый albedo — материалы как самосвечение
            #     (Emission=Base Color), без света/теней. Не зависит от
            #     движка/world-GI → детерминированно, не тёмное.
            #  2) Alpha = силуэт листвы — рендер ОРИГИНАЛЬНОГО материала
            #     (его прозрачность как есть). Оба прохода — одна камера →
            #     один layout, идеально совмещаются.
            restores = []
            for slot in obj.material_slots:
                if slot.material is not None:
                    restores.append(_albedo_override(slot.material))
            rgb_buf = _render_pixels()
            for rs in restores:
                try:
                    rs()
                except Exception:
                    pass
            a_buf = _render_pixels()
            if rgb_buf is not None:
                out = rgb_buf.reshape(-1, 4).copy()
                if a_buf is not None:
                    out[:, 3] = a_buf.reshape(-1, 4)[:, 3]   # альфа из 2-го прохода
                image.pixels.foreach_set(out.ravel())
                image.update()
        else:
            buf = _render_pixels()
            if buf is not None:
                image.pixels.foreach_set(buf)
                image.update()
    finally:
        # удалить временные камеру/свет
        for lo in lights:
            ld = lo.data
            try:
                bpy.data.objects.remove(lo, do_unlink=True)
            except Exception:
                pass
            try:
                if ld and ld.users == 0:
                    bpy.data.lights.remove(ld)
            except Exception:
                pass
        if cam_obj is not None:
            try:
                bpy.data.objects.remove(cam_obj, do_unlink=True)
            except Exception:
                pass
        if cam_data is not None and cam_data.users == 0:
            try:
                bpy.data.cameras.remove(cam_data)
            except Exception:
                pass
        # восстановить настройки сцены
        try:
            r.engine = snap['engine']
            r.film_transparent = snap['film']
            r.resolution_x = snap['rx']; r.resolution_y = snap['ry']
            r.resolution_percentage = snap['pct']
            r.pixel_aspect_x = snap['pax']; r.pixel_aspect_y = snap['pay']
            r.filepath = snap['fp']
            r.image_settings.file_format = snap['ff']
            r.image_settings.color_mode = snap['cm']
            vs.view_transform = snap['vt']; vs.look = snap['look']
            vs.exposure = snap['exp']; vs.gamma = snap['gamma']
            scene.world = snap['world']
            scene.camera = snap['cam']
            scene.use_nodes = snap['nodes']
            if snap['eevee_s'] is not None and eev is not None:
                eev.taa_render_samples = snap['eevee_s']
            if snap['cycles_s'] is not None and cyc is not None:
                cyc.samples = snap['cycles_s']
        except Exception:
            pass
        for o, v in hidden:
            try:
                o.hide_render = v
            except Exception:
                pass
        map_teardown()
        w = bpy.data.worlds.get(BAKE_WORLD_NAME)
        if w is not None and w.users == 0:
            try:
                bpy.data.worlds.remove(w)
            except Exception:
                pass
        if fpath and os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass
