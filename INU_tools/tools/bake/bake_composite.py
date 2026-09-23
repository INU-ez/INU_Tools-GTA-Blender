# INU_tools.tools.bake.bake_composite — Слой 3 подсистемы запекания.
#
# Композитор «N карт → одна текстура». ЧИСТЫЙ numpy, БЕЗ bpy и без
# относительных импортов — поэтому юнит-тестируется headless (и его
# инвариант «нет bpy» не нарушается: на вход подаются простые LayerSpec,
# не PropertyGroup — извлечение делает оператор, слой 4).
#
# Порядок пикселей — нативный Blender (снизу вверх, RGBA float). Композит
# идёт в linear, на выходе RGB кодируется в sRGB (карты GTA SA — sRGB
# 8-bit), alpha берётся из базового слоя без изменений (cutout/листва).

from dataclasses import dataclass

import numpy as np


# ── HSV-хелперы (векторные, для Hue/Saturation/Color/Value) ──────────
# numpy не имеет встроенного RGB↔HSV; повторяем точные формулы Blender
# (rgb_to_hsv / hsv_to_rgb из math_color.c), чтобы HSV-режимы совпадали
# с живым нодовым превью. Вход/выход (… ,3) float в [0,1].

def _rgb_to_hsv(rgb):
    """(… ,3) RGB → (h, s, v), каждый (…) в [0,1]. Серый (d==0) → h=0."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    d = mx - mn
    d_safe = np.where(d == 0.0, 1.0, d)
    # Порядок where обратный (b→g→r): при равенстве максимумов «победитель» —
    # r, как в if/elif Blender (последний where перетирает предыдущие).
    h = np.zeros_like(mx)
    h = np.where(mx == b, 4.0 + (r - g) / d_safe, h)
    h = np.where(mx == g, 2.0 + (b - r) / d_safe, h)
    h = np.where(mx == r, (g - b) / d_safe, h)
    h = (h / 6.0) % 1.0
    h = np.where(d == 0.0, 0.0, h)
    s = np.where(mx == 0.0, 0.0, d / np.where(mx == 0.0, 1.0, mx))
    return h, s, mx


def _hsv_to_rgb(h, s, v):
    """(h, s, v) каждый (…) → (… ,3) RGB float."""
    h6 = (h % 1.0) * 6.0
    i = np.floor(h6).astype(np.int64)
    f = h6 - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    i = i % 6
    r = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5],
                  [v, q, p, p, t, v])
    g = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5],
                  [t, v, v, q, p, p])
    b = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5],
                  [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


# ── Гауссово размытие (сепарабельное, чистый numpy) ──────────────────
# Пост-обработка LightMap: смягчает блочность/остаточный шум на низком
# разрешении (аналог OpenCV-фильтра The_Lightmapper), без внешних
# зависимостей (cv2/scipy) — согласуется с политикой «single in-process
# path». Сепарабельный проход по строкам и столбцам, края — clamp (edge).

def _gauss_kernel_1d(radius):
    """Нормированное 1D-гауссово ядро для радиуса `radius` (px). Полуширина
    ≈3σ; σ=radius. Возвращает (2r+1,) float32."""
    sigma = max(float(radius), 1e-3)
    r = max(1, int(round(sigma * 3.0)))
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-(x * x) / (2.0 * sigma * sigma))
    k /= k.sum()
    return k


def _convolve1d_edge(a, k, axis):
    """Свёртка `a` ядром `k` вдоль `axis` с edge-clamp по краям."""
    r = len(k) // 2
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r, r)
    padded = np.pad(a, pad, mode='edge')
    out = np.zeros_like(a)
    n = a.shape[axis]
    for i, w in enumerate(k):
        sl = [slice(None)] * a.ndim
        sl[axis] = slice(i, i + n)
        out += w * padded[tuple(sl)]
    return out


def gaussian_blur(arr, radius):
    """Гауссово размытие (h,w,ch) float-массива радиусом `radius` px. Размывает
    только RGB (первые 3 канала); alpha (если есть) остаётся как есть —
    силуэт/маска не должны замыливаться. radius<=0 → массив без изменений.
    Возвращает НОВЫЙ массив (вход не мутируется)."""
    if radius is None or radius <= 0:
        return arr
    k = _gauss_kernel_1d(radius)
    ch = arr.shape[2]
    n = min(3, ch)
    rgb = arr[:, :, :n].astype(np.float32, copy=False)
    rgb = _convolve1d_edge(rgb, k, 0)
    rgb = _convolve1d_edge(rgb, k, 1)
    out = arr.copy()
    out[:, :, :n] = rgb
    return out


# ── Bilateral denoise (краесохраняющий, чистый numpy) ────────────────
# Шумоподавление LightMap без зависимостей и без компоузера (в Blender 5.x
# компоузер стал node-группой, и OIDN-нода через рендер-readback недоступна).
# Bilateral сглаживает шум, сохраняя края: вес соседа = пространственный
# гаусс × дальностный гаусс по разнице RGB. Alpha не трогаем.

def _shift_clamp(a, dy, dx):
    """a[clamp(y+dy), clamp(x+dx)] — сдвиг с edge-clamp по краям."""
    h, w = a.shape[:2]
    ys = np.clip(np.arange(h) + dy, 0, h - 1)
    xs = np.clip(np.arange(w) + dx, 0, w - 1)
    return a[ys][:, xs]


def bilateral_denoise(arr, radius=3, sigma_space=3.0, sigma_range=0.12):
    """Bilateral-денойз (h,w,ch) float-массива. Сглаживает шум, сохраняя
    края. Размывает только RGB (первые 3 канала); alpha остаётся. radius=0
    → без изменений. Возвращает НОВЫЙ массив (вход не мутируется)."""
    if radius is None or radius <= 0:
        return arr
    ch = arr.shape[2]
    n = min(3, ch)
    rgb = arr[:, :, :n].astype(np.float32, copy=False)
    inv_s2 = 1.0 / (2.0 * sigma_space * sigma_space)
    inv_r2 = 1.0 / (2.0 * sigma_range * sigma_range)
    acc = np.zeros_like(rgb)
    wsum = np.zeros(rgb.shape[:2] + (1,), np.float32)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            shifted = _shift_clamp(rgb, dy, dx)
            spatial = float(np.exp(-(dx * dx + dy * dy) * inv_s2))
            diff = shifted - rgb
            rng = np.exp(-np.sum(diff * diff, axis=2, keepdims=True) * inv_r2)
            wgt = spatial * rng
            acc += shifted * wgt
            wsum += wgt
    out = arr.copy()
    out[:, :, :n] = acc / np.maximum(wsum, 1e-8)
    return out


# ── Blend-функции ────────────────────────────────────────────────────
# Каждая: (acc_rgb=низ, top_rgb=верх) -> blended_rgb, всё (h,w,3).
# Это значение режима при полной непрозрачности (fac=1) — смешивание по
# opacity делает вызывающий (composite_layers), ровно как Blender: outcol =
# facm*col1 + fac*<blend>. Формулы — 1:1 с ramp_blend() ядра Blender, поэтому
# numpy-«сведение» совпадает с живым превью на нодах ShaderNodeMix.

def _b_normal(a, b):   return b
def _b_darken(a, b):   return np.minimum(a, b)
def _b_multiply(a, b): return a * b
def _b_lighten(a, b):  return np.maximum(a, b)
def _b_screen(a, b):   return 1.0 - (1.0 - a) * (1.0 - b)
def _b_add(a, b):      return np.clip(a + b, 0.0, 1.0)
def _b_subtract(a, b): return np.clip(a - b, 0.0, 1.0)
def _b_difference(a, b): return np.abs(a - b)


def _b_burn(a, b):     # Color Burn: 1 − (1−a)/b
    out = 1.0 - (1.0 - a) / np.where(b <= 0.0, 1.0, b)
    return np.clip(np.where(b <= 0.0, 0.0, out), 0.0, 1.0)


def _b_dodge(a, b):    # Color Dodge: a / (1−b)
    denom = 1.0 - b
    out = a / np.where(denom <= 0.0, 1.0, denom)
    out = np.where(denom <= 0.0, 1.0, out)   # 1−b ≤ 0 → белый
    out = np.where(a <= 0.0, 0.0, out)        # a == 0 → чёрный (приоритет)
    return np.clip(out, 0.0, 1.0)


def _b_overlay(a, b):
    return np.where(a < 0.5, 2.0 * a * b,
                    1.0 - 2.0 * (1.0 - a) * (1.0 - b))


def _b_soft_light(a, b):
    scr = 1.0 - (1.0 - b) * (1.0 - a)
    return np.clip((1.0 - a) * b * a + a * scr, 0.0, 1.0)


def _b_linear_light(a, b):
    return np.clip(a + 2.0 * b - 1.0, 0.0, 1.0)


def _b_divide(a, b):   # где b==0 — слой не влияет (остаётся низ), как в Blender
    out = a / np.where(b == 0.0, 1.0, b)
    return np.clip(np.where(b == 0.0, a, out), 0.0, 1.0)


def _b_hue(a, b):          # тон ← верх; насыщ./яркость ← низ
    _ha, sa, va = _rgb_to_hsv(a)
    hb, sb, _vb = _rgb_to_hsv(b)
    out = _hsv_to_rgb(hb, sa, va)
    return np.where((sb == 0.0)[..., None], a, out)


def _b_saturation(a, b):   # насыщенность ← верх; тон/яркость ← низ
    ha, sa, va = _rgb_to_hsv(a)
    _hb, sb, _vb = _rgb_to_hsv(b)
    out = _hsv_to_rgb(ha, sb, va)
    return np.where((sa == 0.0)[..., None], a, out)


def _b_value(a, b):        # яркость ← верх; тон/насыщ. ← низ
    ha, sa, _va = _rgb_to_hsv(a)
    _hb, _sb, vb = _rgb_to_hsv(b)
    return _hsv_to_rgb(ha, sa, vb)


def _b_color(a, b):        # тон+насыщ. ← верх; яркость ← низ
    _ha, _sa, va = _rgb_to_hsv(a)
    hb, sb, _vb = _rgb_to_hsv(b)
    out = _hsv_to_rgb(hb, sb, va)
    return np.where((sb == 0.0)[..., None], a, out)


# ── Реестр режимов — ЕДИНЫЙ источник правды ──────────────────────────
# (id, blend_type ноды ShaderNodeMix, английская метка). Порядок = порядок
# в выпадашке. id NORMAL/MULTIPLY/ADD/SCREEN/OVERLAY сохранены ради старых
# .blend. Набор и порядок — как в Mix-узле Blender (версионно-безопасный
# поднабор без EXCLUSION: его нет в ShaderNodeMixRGB на ≤3.3).
#   bake_composite (этот файл) — формулы (_BLEND);
#   bake_nodes      — blend_type ноды (BLEND_NODE_TYPE);
#   scene_settings  — EnumProperty-метки (BLEND_LABEL).
BLEND_DEFS = (
    ('NORMAL',       'MIX',          'Normal',       _b_normal),
    ('DARKEN',       'DARKEN',       'Darken',       _b_darken),
    ('MULTIPLY',     'MULTIPLY',     'Multiply',     _b_multiply),
    ('BURN',         'BURN',         'Color Burn',   _b_burn),
    ('LIGHTEN',      'LIGHTEN',      'Lighten',      _b_lighten),
    ('SCREEN',       'SCREEN',       'Screen',       _b_screen),
    ('DODGE',        'DODGE',        'Color Dodge',  _b_dodge),
    ('ADD',          'ADD',          'Add',          _b_add),
    ('OVERLAY',      'OVERLAY',      'Overlay',      _b_overlay),
    ('SOFT_LIGHT',   'SOFT_LIGHT',   'Soft Light',   _b_soft_light),
    ('LINEAR_LIGHT', 'LINEAR_LIGHT', 'Linear Light', _b_linear_light),
    ('DIFFERENCE',   'DIFFERENCE',   'Difference',   _b_difference),
    ('SUBTRACT',     'SUBTRACT',     'Subtract',     _b_subtract),
    ('DIVIDE',       'DIVIDE',       'Divide',       _b_divide),
    ('HUE',          'HUE',          'Hue',          _b_hue),
    ('SATURATION',   'SATURATION',   'Saturation',   _b_saturation),
    ('COLOR',        'COLOR',        'Color',        _b_color),
    ('VALUE',        'VALUE',        'Value',        _b_value),
)

BLEND_MODES = tuple(d[0] for d in BLEND_DEFS)
BLEND_NODE_TYPE = {d[0]: d[1] for d in BLEND_DEFS}
BLEND_LABEL = {d[0]: d[2] for d in BLEND_DEFS}
_BLEND = {d[0]: d[3] for d in BLEND_DEFS}


@dataclass
class LayerSpec:
    """Плоское (bpy-free) описание слоя для композитора. Оператор
    извлекает его из INUBakeLayer (PropertyGroup) перед вызовом."""
    map_id: str
    uid: str = ''                  # per-layer id → своя картинка (layer_image_key)
    enabled: bool = True
    blend_mode: str = 'NORMAL'
    opacity: float = 1.0
    contrast: float = 1.0          # FUTURE (1.0 = identity)
    gamma: float = 1.0             # FUTURE (1.0 = identity)
    influence_target: str = ''     # FUTURE (masking by another map)
    influence_amount: float = 1.0
    alpha_source: str = ''         # ALPHA-слой: '' / 'MATERIAL' | map_id-источник
    alpha_invert: bool = False     # ALPHA-слой: инвертировать (тёмное = видно)
    as_decal: bool = False         # любой слой → альфа по своей яркости (декаль)
    decal_threshold: float = 0.5   # порог яркости (выше — прозрачно)
    decal_softness: float = 0.25   # мягкость перехода у порога
    decal_invert: bool = False     # декаль: показывать светлое вместо тёмного


def linear_to_srgb(c):
    """scene-linear → sRGB (C1). Вход/выход (… ,3) float в [0,1]."""
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308,
                    c * 12.92,
                    1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def srgb_to_linear(c):
    """sRGB → scene-linear (обратно linear_to_srgb). Нужно, чтобы numpy-
    композит считался в ЛИНЕЙНОМ пространстве — как нодовый превью (там
    Image Texture sRGB→linear, cg/blend в линейном). Иначе контраст/гамма и
    блендинг в over-base/«Сохранить как» расходились с живым превью."""
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045,
                    c / 12.92,
                    np.power((c + 0.055) / 1.055, 2.4))


def apply_contrast_gamma(rgb, contrast=1.0, gamma=1.0):
    """Per-layer контраст/гамма. При (1.0, 1.0) — тождество (FUTURE-хук:
    движок уже зовёт это каждый прогон, включение = только UI)."""
    if contrast == 1.0 and gamma == 1.0:
        return rgb
    out = rgb
    if contrast != 1.0:
        out = np.clip((out - 0.5) * contrast + 0.5, 0.0, 1.0)
    if gamma != 1.0 and gamma > 0.0:
        out = np.power(np.clip(out, 0.0, 1.0), 1.0 / gamma)
    return out


def _resample_to(arr, w, h):
    """Nearest-resample (h0,w0,C) → (h,w,C). Подстраховка на случай карт
    разного размера (C-mixed-resolution); в норме все слои печём в одно
    разрешение и это no-op."""
    ah, aw = arr.shape[0], arr.shape[1]
    if aw == w and ah == h:
        return arr
    yi = np.linspace(0, ah - 1, h).astype(np.int64)
    xi = np.linspace(0, aw - 1, w).astype(np.int64)
    return arr[yi][:, xi]


ALPHA_MAP_ID = 'ALPHA'


def layer_image_key(L):
    """Ключ картинки слоя. Раньше все слои одной карты ключевались по map_id и
    ДЕЛИЛИ одну картинку (второй Bevel затирал первый). Теперь у каждого слоя
    свой uid → своя картинка `<base>_<uid>`. Старые слои (без uid) — по map_id,
    как было (обратная совместимость)."""
    return getattr(L, 'uid', '') or L.map_id


def _is_alpha_provider(L):
    """Слой задаёт альфа-канал результата: карта ALPHA (прозрачность материала)
    ИЛИ любой слой с as_decal (яркость → прозрачность, напр. Shadow)."""
    return L.map_id == ALPHA_MAP_ID or getattr(L, 'as_decal', False)


def _layer_alpha_array(L, layer_pixels, fallback, w, h):
    """Посчитать альфа-канал (h,w) float для слоя-провайдера L.

    Источник яркости:
      * as_decal → сама карта слоя (L.map_id);
      * ALPHA    → alpha_source (др. карта) или прозрачность материала (Non-Color).
    Для as_decal применяем порог/мягкость (levels) и инверсию направления
    (по умолчанию видно ТЁМНОЕ). Возвращает значения в [0,1] (без ×opacity)."""
    decal = getattr(L, 'as_decal', False)
    # decal → своя картинка слоя (per-layer key); alpha_source ссылается на
    # ДРУГУЮ карту по map_id — она в layer_pixels продублирована под map_id.
    src_id = layer_image_key(L) if decal else (getattr(L, 'alpha_source', '') or 'MATERIAL')
    if src_id != 'MATERIAL' and src_id in layer_pixels:
        px = _resample_to(layer_pixels[src_id], w, h)
        a = (0.2126 * px[..., 0] + 0.7152 * px[..., 1]
             + 0.0722 * px[..., 2]).astype(np.float32)          # яркость
    elif ALPHA_MAP_ID in layer_pixels:
        px = _resample_to(layer_pixels[ALPHA_MAP_ID], w, h)
        a = px[..., 0].astype(np.float32)
        # Значение альфы обычно эмитится в RGB. Но в Hi→Low «покрытие» (где
        # геометрия) пишется в АЛЬФА-канал карты, а RGB остаётся пустым —
        # тогда берём альфа-канал (иначе читался бы чёрный R → всё прозрачно).
        if px.shape[2] >= 4 and float(a.max()) < 1e-4:
            a = px[..., 3].astype(np.float32)
        # CUTOUT: маска покрытия, а не полупрозрачность. Порог 0.5 → есть
        # геометрия → 1 (непрозрачно), дыра → 0. Стандарт GTA cutout.
        a = (a >= 0.5).astype(np.float32)
    else:
        return np.clip(fallback, 0.0, 1.0).astype(np.float32)
    if decal:
        thr = float(getattr(L, 'decal_threshold', 0.5))
        soft = float(getattr(L, 'decal_softness', 0.25))
        lo, hi = thr - soft, thr + soft
        if hi > lo:
            a = np.clip((a - lo) / (hi - lo), 0.0, 1.0)          # levels
        else:
            a = (a >= thr).astype(np.float32)                    # резкая граница
        # Декаль: по умолчанию видно ТЁМНОЕ → инверсия яркости.
        if not getattr(L, 'decal_invert', False):
            a = 1.0 - a
    else:
        if getattr(L, 'alpha_invert', False):
            a = 1.0 - a
    return np.clip(a, 0.0, 1.0)


def composite_layers(layer_pixels, layers, w, h, *, srgb=True):
    """Сложить включённые слои снизу вверх в одну текстуру.

    layer_pixels : dict {map_id: (h,w,4) float32} — запечённые карты
                   (scene-linear).
    layers       : упорядоченный list[LayerSpec]; index 0 = ВЕРХ (как в UI).
    w, h         : целевое разрешение.
    srgb         : кодировать ли RGB результата в sRGB (для записи в
                   8-bit текстуру GTA SA — да; для отладки blend-математики
                   удобно False).

    Возвращает (h,w,4) float32.

    Слои карты ALPHA в RGB-стек НЕ идут — они задают альфа-канал результата
    (верхний ALPHA-слой × его opacity). Так любую карту (тень, диффуз, …)
    можно сделать прозрачным декалем. Если ALPHA-слоя нет — альфа берётся из
    базового слоя без изменений (как раньше: cutout/листва SA).

    Выключенные слои и слои без запечённых пикселей пропускаются — отсюда
    «скомбинировать любой поднабор».
    """
    # UI-порядок (сверху вниз): index 0 = верх.
    present = [L for L in layers if L.enabled and layer_image_key(L) in layer_pixels]
    # Провайдер альфы — верхний включённый слой ALPHA или as_decal (не требуя
    # <base>_ALPHA: источником может быть другая карта, напр. Shadow).
    alpha_layer = next((L for L in layers
                        if L.enabled and _is_alpha_provider(L)), None)
    # RGB-стек без ALPHA и без as_decal-слоёв; база = НИЖНИЙ слой → разворот.
    enabled = list(reversed([L for L in present if not _is_alpha_provider(L)]))
    if not enabled and alpha_layer is None:
        return np.zeros((h, w, 4), dtype=np.float32)

    def _desat(rgb):
        # Обесцветить в серое по яркости (Rec.709, scene-linear) — убирает
        # синий оттенок Normal Map при объединении, оставляя только рельеф.
        lum = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1]
               + 0.0722 * rgb[..., 2])
        return np.repeat(lum[..., None], 3, axis=-1)

    if enabled:
        # Композитим в ЛИНЕЙНОМ пространстве (как нодовый превью): картинки —
        # sRGB-байт, переводим srgb→linear на входе, linear→srgb на выходе.
        # Так контраст/гамма и блендинг совпадают с живым превью и с игрой.
        base = _resample_to(layer_pixels[layer_image_key(enabled[0])], w, h)
        acc = srgb_to_linear(base[..., :3].astype(np.float32))
        if getattr(enabled[0], 'desaturate', False):
            acc = _desat(acc)
        acc = apply_contrast_gamma(acc, enabled[0].contrast, enabled[0].gamma)
        base_alpha = base[..., 3].astype(np.float32)

        for L in enabled[1:]:
            top = srgb_to_linear(
                _resample_to(layer_pixels[layer_image_key(L)], w, h)[..., :3].astype(np.float32))
            if getattr(L, 'desaturate', False):
                top = _desat(top)
            top = apply_contrast_gamma(top, L.contrast, L.gamma)
            blended = _BLEND.get(L.blend_mode, _BLEND['NORMAL'])(acc, top)
            # FUTURE: mask = mask_lookup[L.influence_target]; сейчас 1.0
            fac = float(L.opacity) * float(L.influence_amount) * 1.0
            acc = acc * (1.0 - fac) + blended * fac

        acc = np.clip(acc, 0.0, 1.0)
        if srgb:
            acc = linear_to_srgb(acc)
    else:
        # Только ALPHA-карта (например тень-декаль без базовой текстуры):
        # RGB чёрный, значимая только прозрачность.
        acc = np.zeros((h, w, 3), dtype=np.float32)
        base_alpha = np.ones((h, w), dtype=np.float32)

    # Альфа-канал результата.
    if alpha_layer is not None:
        a = _layer_alpha_array(alpha_layer, layer_pixels, base_alpha, w, h)
        a = a * float(alpha_layer.opacity) * float(alpha_layer.influence_amount)
        out_alpha = np.clip(a, 0.0, 1.0)
    else:
        out_alpha = np.clip(base_alpha, 0.0, 1.0)

    out = np.empty((h, w, 4), dtype=np.float32)
    out[..., :3] = acc
    out[..., 3] = out_alpha
    return out
