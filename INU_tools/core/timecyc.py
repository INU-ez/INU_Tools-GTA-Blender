# INU_tools.core.timecyc — чтение/запись timecyc.dat GTA SA / VC / III
# (и timecycp.dat).
#
# Формат: текстовый файл из блоков погоды. Каждый блок —
#
#     //////////// EXTRASUNNY_LA
#     //Amb  Amb_Obj  Dir  Sky top  Sky bot  ...           <- шапка колонок
#     //Midnight
#     22 22 22   220 212 130   ...                         <- строка данных
#     //5AM
#     ...
#     //
#
# SA: ровно 8 строк данных на блок — временны́е срезы 0/5/6/7/12/19/20/22 ч.
# III и VC: 24 строки на блок, по одной на каждый час (CTimeCycle::Initialise
# читает NUMWEATHERS × NUMHOURS строк подряд, пропуская всё, что начинается
# с «/»; III — 4 погоды × 40 чисел, VC — 7 погод × 52 числа, см. re3/reVC
# src/renderer/Timecycle.cpp). Игра линейно интерполирует между соседними
# срезами (последний → 0 через полночь), поэтому «час» — непрерывная
# величина, а правится всегда конкретный срез.
#
# Игра файла определяется по его форме: 24 строки на блок → III (≤ 46
# чисел) или VC (52), иначе SA. Ширина VC (52) совпадает с SA+DirMult, так
# что по одной ширине их не различить.
#
# Ширина строки (проверено на реальных файлах, не по вики):
#   51 — ванильный SA: Dir RGB есть, хвост из трёх (CloudAlpha,
#        HighLightMinIntensity, WaterFogAlpha);
#   52 — сборки с четвёртым хвостовым DirectionalMult (Project Eagle TC);
#   49 — без Dir RGB;
#   короче — попадается и в ванилле (одна строка), и в модах (в Project
#        Eagle весь блок UNDERWATER на значение короче).
# Поэтому схема выбирается по САМОЙ ШИРОКОЙ строке файла, недостающий
# хвост отдельной строки добивается дефолтами, а исходная ширина
# запоминается — при экспорте лишняя колонка не дописывается.
#
# Экспорт байт-в-байт для нетронутых строк: writer отдаёт оригинальную
# строку, если срез не помечен dirty. Дифф файла = только правки.

import os
import re


# ── Временны́е срезы ─────────────────────────────────────────────────

SLOT_HOURS = (0, 5, 6, 7, 12, 19, 20, 22)          # SA
SLOT_LABELS = ("Midnight", "5AM", "6AM", "7AM", "Midday", "7PM", "8PM", "10PM")
SLOTS = len(SLOT_HOURS)

# III / VC: почасовые срезы, подписи как в ванильных файлах.
SLOT_HOURS_24 = tuple(range(24))
SLOT_LABELS_24 = tuple(
    "Midnight" if h == 0 else "Midday" if h == 12
    else "%dAM" % h if h < 12 else "%dPM" % (h - 12)
    for h in SLOT_HOURS_24)

GAME_SLOT_HOURS = {
    'SA':  SLOT_HOURS,
    'VC':  SLOT_HOURS_24,
    'III': SLOT_HOURS_24,
}


def slot_hours_for(game):
    return GAME_SLOT_HOURS.get(game, SLOT_HOURS)


# ── Схема полей ─────────────────────────────────────────────────────
#
# (key, size, kind, fmt)
#   size — сколько чисел подряд;
#   kind — 'rgb' / 'rgba' / 'argb' (альфа ПЕРВОЙ — так лежат PostFX) / 'num';
#   fmt  — 'i' целое, 'f' с двумя знаками после точки.

_FIELDS_CORE = [
    ('amb',             3, 'rgb',  'i'),
    ('amb_obj',         3, 'rgb',  'i'),
    ('sky_top',         3, 'rgb',  'i'),
    ('sky_bot',         3, 'rgb',  'i'),
    ('sun_core',        3, 'rgb',  'i'),
    ('sun_corona',      3, 'rgb',  'i'),
    ('sun_size',        1, 'num',  'f'),
    ('spr_size',        1, 'num',  'f'),
    ('spr_bright',      1, 'num',  'f'),
    ('shadow',          1, 'num',  'i'),
    ('light_shad',      1, 'num',  'i'),
    ('pole_shad',       1, 'num',  'i'),
    ('far_clip',        1, 'num',  'f'),
    ('fog_start',       1, 'num',  'f'),
    ('light_on_ground', 1, 'num',  'f'),
    ('low_clouds',      3, 'rgb',  'i'),
    ('bottom_clouds',   3, 'rgb',  'i'),
    ('water',           4, 'rgba', 'i'),
    ('postfx1',         4, 'argb', 'i'),
    ('postfx2',         4, 'argb', 'i'),
    ('cloud_alpha',     1, 'num',  'i'),
    ('highlight_min',   1, 'num',  'i'),
    ('water_fog',       1, 'num',  'i'),
    ('dir_mult',        1, 'num',  'f'),
]

_DIR_FIELD = ('dir', 3, 'rgb', 'i')

# GTA III (re3 Timecycle.cpp, 40 чисел): Amb Dir SkyTop SkyBot SunCore
# SunCorona SunSz SprSz SprBght Shdw LightShd TreeShd FarClp FogSt
# LightOnGround LowClouds TopClouds BottomClouds BlurRGBA. Blur — цвет
# «трейлов» (CMBlur, на PC — опция Trails). TreeShd лежит под ключом
# pole_shad — та же позиция, что PoleShd у VC/SA.
_FIELDS_III = [
    ('amb',             3, 'rgb',  'i'),
    ('dir',             3, 'rgb',  'i'),
    ('sky_top',         3, 'rgb',  'i'),
    ('sky_bot',         3, 'rgb',  'i'),
    ('sun_core',        3, 'rgb',  'i'),
    ('sun_corona',      3, 'rgb',  'i'),
    ('sun_size',        1, 'num',  'f'),
    ('spr_size',        1, 'num',  'f'),
    ('spr_bright',      1, 'num',  'f'),
    ('shadow',          1, 'num',  'i'),
    ('light_shad',      1, 'num',  'i'),
    ('pole_shad',       1, 'num',  'i'),
    ('far_clip',        1, 'num',  'f'),
    ('fog_start',       1, 'num',  'f'),
    ('light_on_ground', 1, 'num',  'f'),
    ('low_clouds',      3, 'rgb',  'i'),
    ('top_clouds',      3, 'rgb',  'i'),
    ('bottom_clouds',   3, 'rgb',  'i'),
    ('blur',            4, 'rgba', 'i'),
]

# Vice City (reVC Timecycle.cpp, 52 числа): Amb Amb_Obj Amb_bl Amb_Obj_bl
# Dir SkyTop SkyBot SunCore SunCorona SunSz SprSz SprBght Shdw LightShd
# PoleShd FarClp FogSt LightOnGround LowClouds TopClouds BottomClouds
# BlurRGB WaterRGBA. *_bl — ambient, который игра берёт при включённых
# Trails (CMBlur::BlurOn, SetLightsWithTimeOfDayColour).
_FIELDS_VC = [
    ('amb',             3, 'rgb',  'i'),
    ('amb_obj',         3, 'rgb',  'i'),
    ('amb_bl',          3, 'rgb',  'i'),
    ('amb_obj_bl',      3, 'rgb',  'i'),
    ('dir',             3, 'rgb',  'i'),
    ('sky_top',         3, 'rgb',  'i'),
    ('sky_bot',         3, 'rgb',  'i'),
    ('sun_core',        3, 'rgb',  'i'),
    ('sun_corona',      3, 'rgb',  'i'),
    ('sun_size',        1, 'num',  'f'),
    ('spr_size',        1, 'num',  'f'),
    ('spr_bright',      1, 'num',  'f'),
    ('shadow',          1, 'num',  'i'),
    ('light_shad',      1, 'num',  'i'),
    ('pole_shad',       1, 'num',  'i'),
    ('far_clip',        1, 'num',  'f'),
    ('fog_start',       1, 'num',  'f'),
    ('light_on_ground', 1, 'num',  'f'),
    ('low_clouds',      3, 'rgb',  'i'),
    ('top_clouds',      3, 'rgb',  'i'),
    ('bottom_clouds',   3, 'rgb',  'i'),
    ('blur',            3, 'rgb',  'i'),
    ('water',           4, 'rgba', 'i'),
]

# Сколько строк данных в блоке погоды ждёт движок.
GAME_ROWS = {'SA': 8, 'VC': 24, 'III': 24}

# Чем добивается хвост, которого в строке не оказалось. Ноль подходит
# почти всем, но белый Dir и dir_mult=1 — нейтральные значения, при
# которых отсутствующая колонка не гасит освещение.
_DEFAULTS = {
    'dir':      [255.0, 255.0, 255.0],
    'dir_mult': [1.0],
}

# Человекочитаемые подписи — их же показывает панель.
FIELD_LABELS = {
    'amb':             "Ambient (мир)",
    'amb_obj':         "Ambient (объекты)",
    'dir':             "Directional",
    'sky_top':         "Небо: зенит",
    'sky_bot':         "Небо: горизонт",
    'sun_core':        "Солнце: ядро",
    'sun_corona':      "Солнце: корона",
    'sun_size':        "Размер солнца",
    'spr_size':        "Размер блика",
    'spr_bright':      "Яркость блика",
    'shadow':          "Тени",
    'light_shad':      "Тени от света",
    'pole_shad':       "Тени столбов",
    'far_clip':        "Дальность прорисовки",
    'fog_start':       "Начало тумана",
    'light_on_ground': "Свет на земле",
    'low_clouds':      "Нижние облака",
    'bottom_clouds':   "Облака у горизонта",
    'water':           "Вода (RGBA)",
    'postfx1':         "PostFX 1 (ARGB)",
    'postfx2':         "PostFX 2 (ARGB)",
    'cloud_alpha':     "Прозрачность облаков",
    'highlight_min':   "Мин. яркость бликов",
    'water_fog':       "Туман под водой",
    'dir_mult':        "Множитель directional",
    'amb_bl':          "Ambient (мир, Trails)",
    'amb_obj_bl':      "Ambient (объекты, Trails)",
    'top_clouds':      "Верхние облака",
    'blur':            "Trails / blur",
}


def schema_for(width, game='SA'):
    """Список полей под файл, самая широкая строка которого — `width`
    чисел. SA: 50+ → есть Dir RGB (ваниль SA и всё, что от неё пошло),
    иначе ванильная схема без Dir. III и VC — фиксированные схемы."""
    if game == 'III':
        return list(_FIELDS_III)
    if game == 'VC':
        return list(_FIELDS_VC)
    fields = list(_FIELDS_CORE)
    if width >= 50:
        fields.insert(2, _DIR_FIELD)
    return fields


def detect_game(rows_per_block, width):
    """Игра по форме файла: 24 строки на блок → III/VC (VC шире: 52
    против 40), иначе SA."""
    if rows_per_block >= 24:
        return 'VC' if width >= 46 else 'III'
    return 'SA'


def schema_width(fields):
    return sum(f[1] for f in fields)


# ── Цвет ────────────────────────────────────────────────────────────

def srgb_to_linear(c):
    """0..1 sRGB → scene-linear. Blender рисует color-свотчи и считает
    шейдеры в линейном пространстве, а в timecyc лежат sRGB-байты —
    без конверсии цвет в панели светлее игрового."""
    c = min(max(float(c), 0.0), 1.0)
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    c = min(max(float(c), 0.0), 1.0)
    if c <= 0.0031308:
        return c * 12.92
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def byte_to_linear(b):
    return srgb_to_linear(float(b) / 255.0)


def linear_to_byte(c):
    return int(round(min(max(linear_to_srgb(c), 0.0), 1.0) * 255.0))


# ── Модель данных ───────────────────────────────────────────────────

class TimecycSlot:
    """Один временно́й срез одной погоды."""

    __slots__ = ('values', 'raw', 'width', 'dirty', 'malformed')

    def __init__(self, values, raw, width, malformed=False):
        self.values = values      # {key: [float, ...]}
        self.raw = raw            # исходная строка без перевода строки
        self.width = width        # сколько чисел было в файле
        self.dirty = False
        # True — sscanf движка споткнулся ПОСРЕДИ строки (например «2.00»
        # в целочисленной колонке): поля после сбоя игра берёт с прошлой
        # строки. Такой срез при записи выводится полной шириной файла
        # — теми значениями, которые игра реально использует.
        self.malformed = malformed

    def get(self, key, default=0.0):
        v = self.values.get(key)
        if not v:
            return default
        return v[0] if len(v) == 1 else list(v)

    def set(self, key, value):
        if key not in self.values:
            return
        seq = value if isinstance(value, (list, tuple)) else (value,)
        cur = self.values[key]
        new = [float(x) for x in seq][:len(cur)]
        while len(new) < len(cur):
            new.append(cur[len(new)])
        if new != cur:
            self.values[key] = new
            self.dirty = True

    def copy_from(self, other):
        for key, val in other.values.items():
            if key in self.values:
                self.set(key, list(val))


class TimecycWeather:
    __slots__ = ('name', 'slots')

    def __init__(self, name):
        self.name = name
        self.slots = []


class TimecycFile:
    """Разобранный timecyc.dat, помнящий исходные строки файла."""

    def __init__(self, path=''):
        self.path = path
        self.lines = []        # исходные строки, без перевода строки
        self.newline = '\r\n'  # как файл был свёрстан — так и запишем
        self.weathers = []
        self.game = 'SA'       # 'SA' | 'VC' | 'III' — по форме файла
        self.fields = list(_FIELDS_CORE)
        self.int_keys = _ENGINE_INT_KEYS
        self.width = 49
        # line_index → (weather_idx, slot_idx)
        self.line_map = {}

    @property
    def slot_hours(self):
        """Часы срезов этой игры: 8 у SA, 24 у III/VC."""
        return slot_hours_for(self.game)

    # -- запросы -----------------------------------------------------

    @property
    def weather_names(self):
        return [w.name for w in self.weathers]

    def has_field(self, key):
        return any(f[0] == key for f in self.fields)

    def slot(self, weather_idx, slot_idx):
        try:
            return self.weathers[weather_idx].slots[slot_idx]
        except IndexError:
            return None

    def is_dirty(self):
        return any(s.dirty for w in self.weathers for s in w.slots)

    def dirty_count(self):
        return sum(1 for w in self.weathers for s in w.slots if s.dirty)

    def interpolate(self, weather_idx, hour):
        """Значения погоды на произвольный час — как в игре: линейно
        между соседними срезами, 22 ч → 0 ч через полночь."""
        try:
            slots = self.weathers[weather_idx].slots
        except IndexError:
            return {}
        if not slots:
            return {}
        if len(slots) < 2:
            return {k: list(v) for k, v in slots[0].values.items()}

        hours = self.slot_hours
        n = min(len(slots), len(hours))
        hour = float(hour) % 24.0
        lo = n - 1
        for i in range(n):
            if hour < hours[i]:
                lo = i - 1
                break
        if lo < 0:
            lo = n - 1
        hi = (lo + 1) % n

        span = (hours[hi] - hours[lo]) % 24
        if span == 0:
            t = 0.0
        else:
            t = min(max(((hour - hours[lo]) % 24) / span, 0.0), 1.0)

        a, b = slots[lo].values, slots[hi].values
        out = {}
        for key, va in a.items():
            vb = b.get(key, va)
            out[key] = [x + (y - x) * t for x, y in zip(va, vb)]
        return out


# ── Парсинг ─────────────────────────────────────────────────────────

# Имя — текст после ПОСЛЕДНЕГО ряда слэшей: в ванильном III заголовок
# CLOUDY выглядит как «///////0 0 5/////////// CLOUDY» (обрывок строки
# внутри слэшей; игра такую строку пропускает целиком, т.к. она
# начинается с «/»).
_WEATHER_RE = re.compile(r'^\s*/{4,}(?:[^/]*/+)*\s*([^/\s][^/]*?)\s*$')
_NUM_RE = re.compile(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?')


# Колонки, которые CTimeCycle::Initialise (0x5BBAC0) читает через «%d»:
# 21 цветов в начале, три тени, два цвета облаков и два байта хвоста.
# Остальное — «%f» (в том числе water RGBA и PostFX, хотя в файле они
# целые). Нужно для точной эмуляции sscanf: «%d» на «2.00» читает 2 и
# отдаёт «.00» СЛЕДУЮЩЕЙ конверсии — «%d» на нём валится, «%f» читает
# 0.0 и сдвигает остаток строки на токен (границы int→float:
# sun_corona.b→sun_size, pole_shad→far_clip, bottom_clouds.b→water.r,
# water_fog→dir_mult).
_ENGINE_INT_KEYS = frozenset({
    'amb', 'amb_obj', 'dir', 'sky_top', 'sky_bot', 'sun_core', 'sun_corona',
    'shadow', 'light_shad', 'pole_shad', 'low_clouds', 'bottom_clouds',
    'highlight_min', 'water_fog',
})

# III / VC читают через «%d» все цвета, кроме blur/water (те — «%f», хотя
# в файле целые), и три тени.
_ENGINE_INT_KEYS_III = frozenset({
    'amb', 'dir', 'sky_top', 'sky_bot', 'sun_core', 'sun_corona',
    'shadow', 'light_shad', 'pole_shad', 'low_clouds', 'top_clouds',
    'bottom_clouds',
})
_ENGINE_INT_KEYS_VC = _ENGINE_INT_KEYS_III | frozenset({
    'amb_obj', 'amb_bl', 'amb_obj_bl'})


def int_keys_for(game):
    if game == 'III':
        return _ENGINE_INT_KEYS_III
    if game == 'VC':
        return _ENGINE_INT_KEYS_VC
    return _ENGINE_INT_KEYS


_INT_TOKEN_RE = re.compile(r'[-+]?\d+$')


def _parse_values(tokens, fields, prev=None, int_keys=None):
    """Строка → {key: [...]} ровно так, как её видит игра.

    ``CTimeCycle::Initialise`` читает каждую строку одним ``sscanf`` с 52
    конверсиями в фиксированные локальные переменные. sscanf заполняет их
    по порядку и останавливается на первой неудачной конверсии; всё, что
    после, остаётся нетронутым — а поскольку локальные живут в одном
    кадре стека на весь цикл, там лежат значения ПРЕДЫДУЩЕЙ строки
    данных (для самой первой строки — мусор). Так ведёт себя ванильная
    короткая строка RAINY_COUNTRYSIDE 8PM: 49 чисел, «2.00» в 20-й
    целочисленной колонке → SunCorona.g = 2, а SunCorona.b и все
    последующие 31 колонка приходят из 7PM (DAT-42c).

    Здесь то же самое: ``tokens`` — сырые строки чисел, ``prev`` — values
    предыдущего среза в порядке файла (или None). Хвост, до которого
    sscanf не дошёл, берётся из ``prev``, а без prev — из ``_DEFAULTS``
    (белый Dir, dir_mult = 1 — нейтральные значения).

    Возвращает ``(values, malformed)``: malformed = True, если конверсия
    сорвалась на непригодном токене (а не потому, что токены кончились).
    """
    values = {}
    tokens = list(tokens)
    if int_keys is None:
        int_keys = _ENGINE_INT_KEYS
    pos = 0
    stopped = False
    malformed = False
    for key, size, _kind, _fmt in fields:
        chunk = []
        for j in range(size):
            if stopped or pos + j >= len(tokens):
                stopped = True
                break
            tok = str(tokens[pos + j])
            if key in int_keys:
                if _INT_TOKEN_RE.match(tok):
                    chunk.append(float(int(tok)))
                else:
                    m = re.match(r'[-+]?\d+', tok)
                    if m is None:
                        # «%d» на «.5» — конверсия не удалась.
                        stopped = malformed = True
                        break
                    # «%d» на «2.00»: читается 2, остаток «.00» уходит
                    # следующей конверсии: «%d» на нём валится (строка
                    # обрывается), а «%f» читает 0.0 и все дальнейшие
                    # колонки съезжают на один токен.
                    chunk.append(float(int(m.group(0))))
                    tokens.insert(pos + j + 1, tok[m.end():])
                    malformed = True
                    continue
            else:
                try:
                    chunk.append(float(tok))
                except ValueError:
                    stopped = malformed = True
                    break
        if len(chunk) < size:
            if prev is not None and key in prev:
                fallback = list(prev[key])
            else:
                fallback = _DEFAULTS.get(key, [0.0] * size)
            while len(chunk) < size:
                chunk.append(fallback[len(chunk)] if len(chunk) < len(fallback) else 0.0)
        values[key] = chunk
        pos += size
    return values, malformed


def parse(path):
    """Читает timecyc.dat. Бросает ValueError, если блоков не нашлось."""
    # newline='' — переводы строк не трогаем, чтобы вернуть файл в
    # игровую папку ровно в том виде (CRLF в ванилле), в каком взяли.
    with open(path, 'r', encoding='utf-8', errors='replace', newline='') as fh:
        text = fh.read()

    cyc = TimecycFile(path)
    cyc.newline = '\r\n' if '\r\n' in text else '\n'
    cyc.lines = text.replace('\r\n', '\n').split('\n')

    # Ширину схемы берём по самой широкой строке данных: узкие блоки
    # (UNDERWATER, битая строка в ванилле) не должны переключить весь
    # файл на схему без Dir и сдвинуть все поля.
    width = 0
    block_rows = []           # строк данных в каждом блоке погоды
    rows = 0
    for line in cyc.lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('//'):
            if _WEATHER_RE.match(line):
                if rows:
                    block_rows.append(rows)
                rows = 0
            continue
        n = len(_NUM_RE.findall(line))
        if n:
            rows += 1
            width = max(width, n)
    if rows:
        block_rows.append(rows)
    if width == 0:
        raise ValueError("timecyc: строк с данными не найдено")

    # Игра — по типичному блоку (самая частая длина), чтобы битый или
    # укороченный блок не переключил схему всего файла.
    typical = max(set(block_rows), key=block_rows.count) if block_rows else 0
    cyc.game = detect_game(typical, width)
    cyc.width = width
    cyc.fields = schema_for(width, cyc.game)
    cyc.int_keys = int_keys_for(cyc.game)

    current = None
    prev_values = None
    for idx, line in enumerate(cyc.lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('//'):
            m = _WEATHER_RE.match(line)
            if m:
                current = TimecycWeather(m.group(1))
                cyc.weathers.append(current)
            continue

        tokens = _NUM_RE.findall(line)
        if not tokens:
            continue
        if current is None:
            # Данные до первого заголовка — заводим безымянный блок.
            current = TimecycWeather("WEATHER_%d" % len(cyc.weathers))
            cyc.weathers.append(current)
        values, malformed = _parse_values(tokens, cyc.fields, prev_values,
                                          cyc.int_keys)
        slot = TimecycSlot(values, line, len(tokens), malformed)
        prev_values = values
        current.slots.append(slot)
        cyc.line_map[idx] = (len(cyc.weathers) - 1, len(current.slots) - 1)

    if not cyc.weathers:
        raise ValueError("timecyc: блоков погоды не найдено")
    return cyc


# ── PostFX (цветофильтр кадра) ──────────────────────────────────────
#
# Два ARGB-слоя из timecyc — это полноэкранный фильтр, который игра
# накладывает на ГОТОВЫЙ кадр:
#
#     PC/Xbox: out = in + in*rgb1*alpha1 + in*rgb2*alpha2
#     PS2:     out = in*rgb1*2 + in*rgb2*2*alpha2*2
#
# То есть кадр умножается покомпонентно на (1 + rgb1*a1 + rgb2*a2). Для
# ванильного полдня это ≈ (1.58, 1.82, 1.82): картинка заметно светлеет
# и уходит в голубизну. Без него превью выглядит темнее и синее игры —
# особенно небо, где эффект виден чище всего.
#
# Умножение идёт по значениям кадра, то есть в gamma-пространстве, а не
# в linear — вызывающий обязан это учесть.


def postfx_gain(values, ps2=False):
    """Множитель кадра (kr, kg, kb) из PostFX1/PostFX2 среза."""
    def _layer(key):
        v = values.get(key)
        if not v or len(v) < 4:
            return 0.0, (0.0, 0.0, 0.0)
        # ARGB: альфа первой.
        alpha = min(max(v[0] / 255.0, 0.0), 1.0)
        rgb = tuple(min(max(c / 255.0, 0.0), 1.0) for c in v[1:4])
        return alpha, rgb

    a1, rgb1 = _layer('postfx1')
    a2, rgb2 = _layer('postfx2')

    if ps2:
        # PS2 blend: обе стадии удваиваются, вклад второй ещё и по альфе.
        return tuple(rgb1[i] * 2.0 + rgb2[i] * 2.0 * a2 * 2.0
                     for i in range(3))
    return tuple(1.0 + rgb1[i] * a1 + rgb2[i] * a2 for i in range(3))


def apply_gain_srgb(linear_rgb, gain):
    """Применить множитель кадра к linear-цвету.

    Фильтр работает по значениям кадра (gamma-пространство), поэтому
    цвет разворачивается в sRGB, множится и сворачивается обратно —
    иначе осветление выходит заметно грубее игрового."""
    out = []
    for c, k in zip(linear_rgb, gain):
        v = linear_to_srgb(c) * float(k)
        out.append(srgb_to_linear(min(max(v, 0.0), 1.0)))
    return tuple(out)


# ── Баланс дневного / ночного прилайта ──────────────────────────────
#
# В SA ночные вершинные цвета лежат отдельной секцией (Extra Vert
# Colour), а движок держит в геометрии параметр dnParam и пишет в
# preLitLum смесь:
#
#     preLit = day * (1 - dnParam) + night * dnParam
#
# (CCustomBuildingDNPipeline::SetPrelitColors). Сам dnParam качается по
# игровым суткам; смена дневного набора на ночной приходится на 20:00 →
# 21:00 — те же часы, когда зажигаются фонари и фары. Утренний порог
# берём по срезам timecyc (05:00 → 06:00, ночь → рассвет); границы
# вынесены в параметры, потому что в модах сутки перекраивают.

DUSK_START, DUSK_END = 20.0, 21.0
DAWN_START, DAWN_END = 5.0, 6.0


def night_balance(hour, dusk_start=DUSK_START, dusk_end=DUSK_END,
                  dawn_start=DAWN_START, dawn_end=DAWN_END):
    """dnParam для часа: 0.0 — чистый Day, 1.0 — чистый Night."""
    hour = float(hour) % 24.0

    def _ramp(h, start, end):
        span = end - start
        if span <= 0.0:
            return None if h < start else 1.0
        if h < start:
            return None
        if h >= end:
            return 1.0
        return (h - start) / span

    # Рассвет: ночь → день.
    if dawn_start <= hour < dawn_end:
        t = _ramp(hour, dawn_start, dawn_end)
        return 1.0 - (t if t is not None else 1.0)
    # Закат: день → ночь.
    if dusk_start <= hour < dusk_end:
        t = _ramp(hour, dusk_start, dusk_end)
        return t if t is not None else 1.0
    # День — между концом рассвета и началом заката.
    if dawn_end <= hour < dusk_start:
        return 0.0
    return 1.0


def _previous_slot(cyc, slot):
    """Срез, стоящий в файле прямо перед ``slot`` (для «stale»-хвоста)."""
    prev = None
    for idx in sorted(cyc.line_map):
        w, i = cyc.line_map[idx]
        cur = cyc.weathers[w].slots[i]
        if cur is slot:
            return prev
        prev = cur
    return None


def revert_slot(cyc, slot):
    """Вернуть срез к содержимому его исходной строки файла."""
    tokens = _NUM_RE.findall(slot.raw)
    prev = _previous_slot(cyc, slot)
    slot.values, slot.malformed = _parse_values(
        tokens, cyc.fields, prev.values if prev is not None else None,
        cyc.int_keys)
    slot.width = len(tokens) or slot.width
    slot.dirty = False
    return slot


# ── Запись ──────────────────────────────────────────────────────────

def _fmt_num(value, fmt):
    if fmt == 'i':
        return str(int(round(value)))
    return "%.2f" % value


# Поля, с которых в ванильном timecyc.dat начинается новая табом
# отделённая группа. Ванильная строка: Amb | Amb_Obj | Dir | SkyTop |
# SkyBot | SunCore | SunCorona | SunSz SprSz SprBght Shdw LightShd
# PoleShd | FarClp FogSt LightOnGround LowClouds | BottomClouds |
# WaterRGBA | PostFX1 | PostFX2 | CloudAlpha HighLight WaterFog [DirMult].
# Раньше каждое поле шло через свой таб (W18) — игре всё равно, но
# правленая строка выбивалась из вёрстки файла.
_GROUP_STARTS = frozenset({
    'amb', 'amb_obj', 'dir', 'sky_top', 'sky_bot', 'sun_core', 'sun_corona',
    'sun_size', 'far_clip', 'bottom_clouds', 'water', 'postfx1', 'postfx2',
    'cloud_alpha',
    # III / VC
    'amb_bl', 'amb_obj_bl', 'top_clouds', 'blur',
})


def format_slot(slot, fields, width=None):
    """Строка данных из значений среза в ванильной вёрстке: группы
    колонок через таб, числа внутри группы через пробел (см.
    ``_GROUP_STARTS``). Ширина обрезается до ``width`` — по умолчанию до
    исходной ширины среза, чтобы в укороченном блоке не появилась
    лишняя колонка. Для среза с ``malformed`` вызывающий передаёт ширину
    файла: битую строку записываем целиком теми значениями, которые
    игра для неё реально использовала."""
    limit = slot.width if width is None else width
    groups = []
    written = 0
    for key, size, _kind, fmt in fields:
        if written >= limit:
            break
        vals = slot.values.get(key, [0.0] * size)
        take = min(size, limit - written)
        nums = [_fmt_num(v, fmt) for v in vals[:take]]
        if key in _GROUP_STARTS or not groups:
            groups.append(nums)
        else:
            groups[-1].extend(nums)
        written += take
    return '\t'.join(' '.join(g) for g in groups)


def _slot_line(cyc, slot):
    """Текст среза для записи: битую строку — полной шириной файла."""
    return format_slot(slot, cyc.fields,
                       max(slot.width, cyc.width) if slot.malformed else None)


def write(cyc, path=None, backup=True):
    """Пишет файл. Нетронутые строки уходят байт-в-байт.

    Рядом кладётся `.bak` прошлой версии — правки timecyc делаются в
    живой игровой папке, и откатиться должно быть чем."""
    target = path or cyc.path
    if not target:
        raise ValueError("timecyc: не задан путь для записи")

    out = []
    for idx, line in enumerate(cyc.lines):
        ref = cyc.line_map.get(idx)
        if ref is None:
            out.append(line)
            continue
        weather_idx, slot_idx = ref
        slot = cyc.weathers[weather_idx].slots[slot_idx]
        out.append(_slot_line(cyc, slot) if slot.dirty else slot.raw)

    tmp = target + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(cyc.newline.join(out))

    if backup and os.path.exists(target):
        bak = target + '.bak'
        try:
            if os.path.exists(bak):
                os.remove(bak)
            os.replace(target, bak)
        except OSError:
            pass
    os.replace(tmp, target)

    # Файл на диске теперь совпадает с моделью — сбрасываем dirty и
    # переносим отформатированный текст в raw, чтобы следующая запись
    # снова была байт-в-байт для нетронутых строк.
    for weather in cyc.weathers:
        for slot in weather.slots:
            if slot.dirty:
                slot.raw = _slot_line(cyc, slot)
                if slot.malformed:
                    slot.width = max(slot.width, cyc.width)
                    slot.malformed = False
                slot.dirty = False
    cyc.path = target
    cyc.lines = out
    return target
