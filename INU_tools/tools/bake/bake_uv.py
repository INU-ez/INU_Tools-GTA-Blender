# INU_tools.tools.bake.bake_uv — вспомогательный слой подсистемы запекания.
#
# Две независимые утилиты для LightMap-режимов:
#   * ensure_lightmap_uv — создать/переиспользовать непересекающийся
#     lightmap-UV-канал (для режимов «отдельная текстура + 2 UV» и как
#     чистая цель запекания без наложений исходной развёртки);
#   * sample_image_uv / sample_image_uv_batch — билинейный сэмпл картинки
#     по UV (для режима «в vertex prelight»: цвет каждого лупа берётся из
#     запечённого lightmap).
#
# Зависит только от numpy/bpy — верхних слоёв не знает.
#
# ВАЖНО: НЕ добавлять `from __future__ import annotations`.

import math

import numpy as np
import bpy


LIGHTMAP_UV_NAME = 'LightMap'

# Blender ограничивает меш 8 UV-слоями (MAX_MTFACE) — uv_layers.new()
# на лимите возвращает None, это надо обрабатывать, а не ронять оператор.
_UV_LAYER_CAP = 8


def uv_needs_unique_target(me, name, minimum_fill=0.0):
    """Repeated face footprints or tiled coordinates cannot hold unique masks."""
    uv = me.uv_layers.get(name)
    if uv is None:
        return False
    coordinates = np.empty(len(me.loops) * 2, dtype=np.float32)
    uv.data.foreach_get('uv', coordinates)
    coordinates = coordinates.reshape(-1, 2)
    if np.any(coordinates < -1e-6) or np.any(coordinates > 1.0 + 1e-6):
        return True
    seen = set()
    filled_area = 0.0
    for face in me.polygons:
        points = coordinates[list(face.loop_indices)]
        footprint = tuple(sorted(tuple(p) for p in np.round(points, 6)))
        if footprint in seen:
            return True
        seen.add(footprint)
        if minimum_fill > 0 and len(points) >= 3:
            following = np.roll(points, -1, axis=0)
            filled_area += abs(float(np.sum(points[:, 0] * following[:, 1]
                                             - points[:, 1] * following[:, 0]))) * 0.5
    return minimum_fill > 0 and filled_area < minimum_fill


def ensure_lightmap_uv(obj, name=LIGHTMAP_UV_NAME, margin=0.002,
                       angle_limit=66.0):
    """Получить-или-создать UV-канал `name` объекта с НЕПЕРЕСЕКАЮЩЕЙСЯ
    развёрткой. Если канал уже существует — переиспользуем как есть (не
    пере-разворачиваем: повторный lightmap_pack сдвинул бы острова и
    рассинхронизировал ранее запечённый lightmap с развёрткой).

    Новый канал разворачиваем Smart UV Project с сохранением пропорций,
    при провале — lightmap_pack. Margin — доля UV, без умножения на 1000.
    КРИТИЧНО: перед
    входом в EDIT изолируем выделение до одного `obj` — mode_set в 2.8+
    входит в мульти-объектный едит, и unwrap-операторы перепаковали бы
    активные UV ВСЕХ выделенных мешей (тихая порча чужих развёрток).
    Выделение/активный объект/режим восстанавливаются.

    Возвращает имя канала или None при неудаче (без исключений).
    """
    me = getattr(obj, 'data', None)
    uvs = getattr(me, 'uv_layers', None)
    if me is None or uvs is None:
        return None

    existing = uvs.get(name)
    if existing is not None:
        return name                      # уже развёрнут — переиспользуем

    view = bpy.context.view_layer
    prev_obj = view.objects.active
    prev_mode = getattr(obj, 'mode', 'OBJECT')
    prev_sel = [(o, o.select_get()) for o in view.objects]
    prev_active_name = uvs.active.name if uvs.active else None
    prev_render_name = next((u.name for u in uvs if u.active_render), None)
    if prev_mode == 'EDIT':
        obj.update_from_editmode()
    mesh_flags = []
    for elements in (me.vertices, me.edges, me.polygons):
        selected, hidden = [False] * len(elements), [False] * len(elements)
        elements.foreach_get('select', selected)
        elements.foreach_get('hide', hidden)
        mesh_flags.append((elements, selected, hidden))
    ok = False
    try:
        uv = uvs.new(name=name)
        if uv is None:                   # лимит 8 UV-слоёв — new() даёт None
            return None
        # Операторы разворачивают АКТИВНЫЙ UV — временно целевой активный.
        uvs.active = uv

        # Изоляция: только obj выделен и активен (см. докстринг).
        for o in view.objects:
            try:
                o.select_set(o is obj)
            except Exception:
                pass
        view.objects.active = obj
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.reveal(select=True)
        bpy.ops.mesh.select_all(action='SELECT')

        # Первый сработавший unwrap побеждает.
        for op, kwargs in (
                (bpy.ops.uv.smart_project,
                 dict(angle_limit=math.radians(angle_limit), margin_method='FRACTION',
                      island_margin=margin, correct_aspect=True)),
                (bpy.ops.uv.lightmap_pack,
                 dict(PREF_CONTEXT='ALL_FACES',
                      PREF_MARGIN_DIV=min(1.0, max(margin, 0.001)))),
        ):
            try:
                result = op(**kwargs)
                if result and 'FINISHED' in result:
                    ok = True
                    break
            except Exception:
                continue
    except Exception:
        ok = False
    finally:
        try:
            if obj.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            for elements, selected, hidden in mesh_flags:
                elements.foreach_set('select', selected)
                elements.foreach_set('hide', hidden)
            me.update()
            if prev_render_name:
                for layer in uvs:
                    layer.active_render = layer.name == prev_render_name
        except Exception:
            pass
        try:
            if obj.mode != prev_mode:
                bpy.ops.object.mode_set(mode=prev_mode)
        except Exception:
            pass
        # Вернуть исходный активный UV (рендер-UV пользователя не трогаем).
        try:
            if prev_active_name and uvs.get(prev_active_name):
                uvs.active = uvs.get(prev_active_name)
        except Exception:
            pass
        # Вернуть исходное выделение и активный объект.
        for o, sel in prev_sel:
            try:
                o.select_set(sel)
            except Exception:
                pass
        try:
            if prev_obj is not None:
                view.objects.active = prev_obj
        except Exception:
            pass
        # Неудачный unwrap — убрать пустой канал, чтобы повторный вызов
        # не «переиспользовал» неразвёрнутый слой.
        if not ok:
            try:
                lay = uvs.get(name)
                if lay is not None:
                    uvs.remove(lay)
            except Exception:
                pass
    return name if ok else None


def sample_image_uv(arr, u, v):
    """Билинейный сэмпл `arr` (H,W,C float32 из read_image_to_numpy) в точке
    UV (u,v). Порядок пикселей Blender — снизу-вверх, поэтому v отображается
    в строку напрямую (row = v*(H-1), без flip). UV зажимается в [0,1]
    (clamp/extend по краям — как GL_CLAMP). Возвращает вектор из C float.

    Тонкая обёртка над sample_image_uv_batch (одна реализация математики)."""
    return sample_image_uv_batch(arr, np.array([[u, v]], np.float32))[0]


def sample_image_uv_batch(arr, uvs):
    """Векторный билинейный сэмпл: `uvs` — (N,2) float массив UV-координат,
    результат — (N,C) float. Семантика как у sample_image_uv, один
    numpy-проход (для записи в per-loop vertex colors)."""
    h, w, c = arr.shape
    uvs = np.asarray(uvs, dtype=np.float32)
    x = np.clip(uvs[:, 0], 0.0, 1.0) * (w - 1)
    y = np.clip(uvs[:, 1], 0.0, 1.0) * (h - 1)
    x0 = np.floor(x).astype(np.intp)
    y0 = np.floor(y).astype(np.intp)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    fx = (x - x0)[:, None]
    fy = (y - y0)[:, None]
    c00 = arr[y0, x0]
    c10 = arr[y0, x1]
    c01 = arr[y1, x0]
    c11 = arr[y1, x1]
    top = c00 * (1.0 - fx) + c10 * fx
    bot = c01 * (1.0 - fx) + c11 * fx
    return top * (1.0 - fy) + bot * fy
