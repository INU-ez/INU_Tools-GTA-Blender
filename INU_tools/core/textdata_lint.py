# INU_tools.core.textdata_lint
# Pre-write audit of the text data files (water.dat, IPL text/binary,
# IDE, timecyc.dat, .zon, plants.dat, effects.fxp, gta.dat) against what
# gta_sa.exe 1.0 US actually does with them. Pure Python, no Blender
# dependency — runs on the core structures right before the writers.
#
# Every rule cites the engine finding it mirrors (DAT-nn in
# E:\RE\addon_check\textdata_path.md, corrections from its verification
# pass). Severity, same as skin_lint:
#   fatal   — the engine crashes at load, or the line / file is misread
#             so the data never reaches the game as written (overrun of
#             a fixed stack buffer, table overflow, dropped line);
#   warning — the engine loads it but silently changes / ignores it.
#
# Calibrated against the vanilla SA data: data\water.dat, timecyc.dat,
# timecycp.dat, plants.dat, info.zon, map.zon, effects.fxp and every IDE /
# IPL listed in gta.dat produce zero fatals.
#
# Limits are per FILE where the engine table is global (zones, cull,
# garages, enex, ...): the checker cannot see the other files the game
# loads, so a file within the limit can still overflow the table together
# with vanilla — the messages say "in this file" for that reason.

import math

# ── Engine limits (verified unless marked) ─────────────────────────

LINE_MAX = 511               # DAT-01: CFileMgr::ReadLine(buf, 512) → fgets
WORLD_HALF = 3000.0          # CEntity::Add / AddWaterLevelVertex clamp

# water (DAT-44/45)
WATER_MAX_VERTICES = 1021    # m_aVertices (vanilla count; room unverified)
WATER_MAX_QUADS = 301        # WaterQuads 0xC21C90..0xC22854 — FULL in vanilla
WATER_MAX_TRIANGLES = 6      # WaterTriangles 0xC22854..0xC22884 — FULL in vanilla
WATER_MAX_COMBOS = 700       # poly-combo list 0xC215F8 (accounting approximate)
WATER_BLOCK = 500.0
WATER_FLOW_MAX = 127.0 / 64.0   # int8(flow*64)

# IPL
IPL_MAX_MODEL_ID = 20000     # ms_modelInfoPtrs[20000]
IPL_INST_NAME_MAX = 23       # name[24]
IPL_MAX_INST_TEXT = 4096     # gCurrIplInstances (gta-reversed; plugin-sdk says 1000)
IPL_INST_TEXT_SAFE = 1000    # plugin-sdk figure; vanilla max is 718 (vegasE)
IPL_MAX_LOD_CHILDREN = 255   # m_nNumLodChildren uint8
ZONE_NAME_MAX = 7            # strncpy(dst, src, 7)
ZONE_INFO_MAX = 7
ZONE_INFO_CRASH = 12         # info[12] overrun
ZONE_MAX_NAV = 380
ZONE_MAX_MAP = 39
CULL_MAX_ATTR = 1300
CULL_MAX_TUNNEL = 40
CULL_MAX_MIRROR = 72
OCCL_MAX_MAP = 1000
OCCL_MAX_INTERIOR = 40
GRGE_NAME_MAX = 7            # name[8] sits under the return address
GRGE_MAX = 50
ENEX_NAME_MAX = 31           # name[32] on the stack
ENEX_NAME_STORED = 8         # AddOne strncpy(…, 8)
ENEX_MAX = 400
AUZO_NAME_MAX = 7            # 8-byte field; 8..15 lose the NUL, ≥16 smash the stack
AUZO_NAME_CRASH = 16
AUZO_MAX_BOX = 158
AUZO_MAX_SPHERE = 3          # FULL in vanilla
TCYC_MAX = 20                # gta-reversed, no exe bound
CARGEN_MAX = 500
CARGEN_MODEL_MIN, CARGEN_MODEL_MAX = 400, 630
PICKUP_IDS = frozenset(set(range(4, 7)) | (set(range(9, 0x38)) - {0x1E, 0x2A}))
BNRY_COUNT_MAX = 32767       # numInst / numCarGen read as int16
STREAMED_IPL_NAME_MAX = 17   # IplDef name[18]

# IDE
IDE_NAME_MAX = 23            # name[24] / txd[24]
IDE_ANIM_NAME_MAX = 15       # anim[16]
IDE_DD_MIN = 4.0             # DAT-08 legacy re-parse below this
IDE_DD_INVISIBLE = 2.0       # DAT-25b instances created invisible
IDE_STORE_ATOMIC = 14000
IDE_STORE_DAMAGE = 70
IDE_STORE_TIME = 169
IDE_STORE_CLUMP = 92
IDE_STORE_VEHICLE = 212
IDE_STORE_PED = 278
IDE_STORE_WEAPON = 51        # gta-reversed (51 or 52 by address arithmetic)
IDE_2DFX_MAX = 100
IDE_TXD_POOL = 5000
IDE_CAR_TYPE_MAX = 7         # type[8] — token ≥ 8 chars overwrites the parsed id
IDE_CAR_HANDLING_MAX = 15
IDE_CAR_GAMENAME_MAX = 31
IDE_CAR_ANIMS_MAX = 15
IDE_CAR_CLASS_MAX = 15
IDE_PED_FIELD_MAX = 23       # pedType / stats / animGroup [24]
IDE_PED_ANIMFILE_MAX = 15
IDE_PED_AUDIO_MAX = 19
IDE_PED_VOICE_MAX = 59
IDE_TXDP_NAME_MAX = 31
CAR_TYPES = frozenset({'car', 'mtruck', 'quad', 'heli', 'plane', 'boat',
                       'train', 'f_heli', 'f_plane', 'bike', 'bmx', 'trailer'})
CAR_CLASSES = frozenset({'normal', 'poorfamily', 'richfamily', 'executive',
                         'worker', 'big', 'taxi', 'moped', 'motorbike',
                         'leisureboat', 'workerboat', 'bicycle', 'ignore'})
# Bits SetBaseModelInfoFlags / SetAtomicModelInfoFlags read (DAT-14):
IDE_FLAG_MASK = 0x1 | 0x4 | 0x8 | 0x40 | 0x80 | 0x200 | 0x400 | 0x800 | \
    0x1000 | 0x2000 | 0x4000 | 0x8000 | 0x80000 | 0x100000 | 0x200000 | 0x400000
# Everything up to the highest documented flag (vanilla IDEs also carry
# 0x2 / 0x20 / 0x10000 / 0x20000 / 0x40000, all ignored by the engine).
IDE_FLAG_KNOWN_BITS = 0x7FFFFF

# timecyc (DAT-42)
TIMECYC_LINES = 184          # SA: 23 weathers × 8 samples
TIMECYC_WIDTHS = (51, 52)    # SA
# III / VC: CTimeCycle::Initialise reads NUMWEATHERS × NUMHOURS rows of a
# fixed width and stores them as int32/float — none of the SA byte-packing
# rules (DAT-42d) apply there, only the row count and the row width.
TIMECYC_GAME_SHAPE = {
    'III': (4, 24, 40),      # weathers, hours, numbers per row
    'VC':  (7, 24, 52),
}
TIMECYC_INT8_MAX = 12.7      # int8(v*10+0.5)
TIMECYC_LIGHTS_GROUND_MAX = 25.5   # uint8(v*10+0.5)
TIMECYC_POSTFX_ALPHA_MAX = 127     # uint8(a*2)

# plants (DAT-46)
PLANTS_TOKENS = 18
PLANTS_MAX_SURFACES = 57
PLANTS_SURFACE_ID_MAX = 177
PLANTS_SLOT_MAX = 3          # PC_PlantModelsTab[4][4]; only slots 0/1 are loaded
PLANTS_SLOT_LOADED = 1

# effects.fxp (DAT-47)
FXP_MAX_PRIMS = 8
FXP_MAX_KEYS = 127           # NUM_KEYS int8
FXP_TIME_MAX = 128.0         # int16(t*256)
FXP_TEXTURE_NAME_MAX = 31    # names[prim][32]
# FX_INFO_<TYPE>_DATA keyword → number of curves the engine reads
FXP_INFO_CURVES = {
    'EMRATE': 1, 'EMSIZE': 7, 'EMSPEED': 2, 'EMDIR': 3, 'EMANGLE': 2,
    'EMLIFE': 2, 'EMPOS': 3, 'EMWEATHER': 4, 'EMROTATION': 2,
    'NOISE': 1, 'FORCE': 3, 'FRICTION': 1, 'ATTRACTPT': 4, 'ATTRACTLINE': 7,
    'GROUNDCOLLIDE': 3, 'WIND': 1, 'JITTER': 1, 'ROTSPEED': 4, 'FLOAT': 0,
    'UNDERWATER': 0, 'COLOUR': 4, 'SIZE': 4, 'SPRITERECT': 4, 'HEATHAZE': 0,
    'TRAIL': 2, 'FLAT': 9, 'DIR': 3, 'ANIMTEX': 1, 'COLOURRANGE': 7,
    'SELFLIT': 0, 'COLOURBRIGHT': 5, 'SMOKE': 8,
}

# gta.dat (DAT-05)
GTADAT_SHORT_PATH_MAX = 63   # TEXDICTION / IPL → local_40[64]
GTADAT_IDE_PATH_MAX = 255    # IDE → local_100[256]


def _t(s: str) -> str:
    """Lazy translation — falls back to the raw Russian string outside
    Blender (standalone unit tests)."""
    try:
        from .. import T
        return T(s)
    except Exception:
        return s


def _fin(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _check_line_len(line: str, label: str, fatal: list) -> None:
    """DAT-01: ReadLine stops at 511 bytes; the tail becomes a second,
    garbage record."""
    if len(line.encode('utf-8', 'replace')) > LINE_MAX:
        fatal.append(_t(
            "{0}: строка длиннее {1} байт — движок прочтёт её как две записи (DAT-01)."
        ).format(label, LINE_MAX))


# ═══════════════════════════════════════════════════════════════════
# water.dat
# ═══════════════════════════════════════════════════════════════════

def check_water(polygons):
    """``polygons`` — list of ``core.water.WaterPolygon`` (or a
    ``WaterFile``). Returns ``(fatal, warnings)``."""
    from .water import format_water_line
    polys = getattr(polygons, 'polygons', polygons)
    fatal, warnings = [], []

    quads = tris = 0
    verts = set()
    bad_shape = []
    degenerate = []
    oversize = 0
    crossing = 0
    blocks = {}

    for idx, poly in enumerate(polys):
        n = len(poly.vertices)
        label = _t("Полигон {0}").format(idx + 1)
        if n == 4:
            quads += 1
        elif n == 3:
            tris += 1
        else:
            # DAT-43 — anything but 22 / 28 / 29 tokens is parsed as a
            # triangle with stale fields (28 = quad without the flag
            # column, the engine takes flags = 1; core.water reads it).
            fatal.append(_t(
                "{0}: {1} вершин — water.dat принимает только 3 или 4, строка прочтётся мусором (DAT-43)."
            ).format(label, n))
            continue

        xs, ys = [], []
        for v in poly.vertices:
            if not all(_fin(c) for c in (v.x, v.y, v.z, v.speed_x, v.speed_y,
                                          v.speed_z, v.wave_height)):
                fatal.append(_t(
                    "{0}: NaN/inf в вершине — sscanf сорвётся, строка прочтётся мусором (DAT-43)."
                ).format(label))
                break
            xi, yi = int(v.x), int(v.y)          # _ftol truncation
            if abs(v.x - round(v.x)) > 1e-4 or abs(v.y - round(v.y)) > 1e-4:
                warnings.append(_t(
                    "{0}: координата ({1:.3f}, {2:.3f}) не целая — движок отбросит дробную часть (DAT-45)."
                ).format(label, v.x, v.y))
            if abs(v.x) > WORLD_HALF or abs(v.y) > WORLD_HALF:
                # DAT-45a: clamp resets z / waves / flow.
                fatal.append(_t(
                    "{0}: вершина ({1:.0f}, {2:.0f}) за пределами ±3000 — движок прижмёт её к краю и обнулит высоту/волны (DAT-45a)."
                ).format(label, v.x, v.y))
            if abs(v.speed_x) > WATER_FLOW_MAX or abs(v.speed_y) > WATER_FLOW_MAX:
                fatal.append(_t(
                    "{0}: течение ({1:.3f}, {2:.3f}) — |flow|·64 не влезает в int8, нужно |flow| < 2 (DAT-45a)."
                ).format(label, v.speed_x, v.speed_y))
            verts.add((xi, yi, round(v.z, 5)))
            xs.append(xi)
            ys.append(yi)
        else:
            sx, sy = set(xs), set(ys)
            if len(sx) == 1 or len(sy) == 1:
                degenerate.append(idx + 1)                      # DAT-45b
            elif n == 4:
                # DAT-45b: sorted by (y, x) and used as the four corners
                # of an axis-aligned rectangle.
                corners = {(x, y) for x in sx for y in sy}
                if len(sx) != 2 or len(sy) != 2 or set(zip(xs, ys)) != corners:
                    bad_shape.append(idx + 1)
            else:
                # triangle: two vertices must share a Y (or an X) line
                if len(sx) == 3 and len(sy) == 3:
                    bad_shape.append(idx + 1)
            fit = _water_fit(min(xs), min(ys), max(xs), max(ys))
            if fit == 'oversize':
                oversize += 1
            elif fit == 'cross':
                crossing += 1
            for b in _water_blocks(min(xs), min(ys), max(xs), max(ys)):
                blocks[b] = blocks.get(b, 0) + 1

        if not 0 <= int(poly.flag) <= 3:
            warnings.append(_t(
                "{0}: флаг {1} вне 0..3 — движок читает только биты 0 (видимость) и 1 (мелководье) (DAT-45c)."
            ).format(label, poly.flag))
        _check_line_len(format_water_line(poly), label, fatal)

    if bad_shape:
        fatal.append(_t(
            "Квады должны быть прямоугольниками по осям, треугольники — с двумя вершинами на одной линии X или Y: движок сортирует вершины по (y, x) и рисует мусор ({0} шт.: {1}) (DAT-45b)."
        ).format(len(bad_shape), _short_list(bad_shape)))
    if degenerate:
        warnings.append(_t(
            "Вырожденные полигоны (все X или все Y равны) движок молча выбрасывает ({0} шт.: {1}) (DAT-45b)."
        ).format(len(degenerate), _short_list(degenerate)))
    if quads > WATER_MAX_QUADS:
        fatal.append(_t(
            "Квадов {0} — таблица WaterQuads вмещает {1} (ваниль заполняет её целиком); 302-й затирает треугольники (DAT-44)."
        ).format(quads, WATER_MAX_QUADS))
    if tris > WATER_MAX_TRIANGLES:
        fatal.append(_t(
            "Треугольников {0} — таблица WaterTriangles вмещает {1}; 7-й затирает свой же счётчик (DAT-44)."
        ).format(tris, WATER_MAX_TRIANGLES))
    if len(verts) > WATER_MAX_VERTICES:
        fatal.append(_t(
            "Уникальных вершин {0} — в ванильном water.dat их {1}, реальная ёмкость m_aVertices не проверена; лишние могут писаться поверх соседних глобалов (DAT-44)."
        ).format(len(verts), WATER_MAX_VERTICES))
    combos = sum(n + 1 for n in blocks.values() if n >= 2)
    if combos > WATER_MAX_COMBOS:
        warnings.append(_t(
            "Полигонов на блок слишком много: список комбинаций ≈{0} записей при лимите {1} (DAT-44)."
        ).format(combos, WATER_MAX_COMBOS))
    if oversize or crossing:
        warnings.append(_t(
            "Полигонов шире 500 по стороне: {0}, пересекающих границу 500-блока: {1} — в игре такие могут рисоваться без текстуры (наблюдение, не проверка парсера)."
        ).format(oversize, crossing))
    return fatal, warnings


def _short_list(items, limit=6):
    s = ', '.join(str(i) for i in items[:limit])
    return s + ('…' if len(items) > limit else '')


def _water_fit(min_x, min_y, max_x, max_y, eps=0.01):
    w = max_x - min_x
    h = max_y - min_y
    if w > WATER_BLOCK + eps or h > WATER_BLOCK + eps:
        return 'oversize'
    same_x = math.floor(min_x / WATER_BLOCK) == math.floor((max_x - eps) / WATER_BLOCK)
    same_y = math.floor(min_y / WATER_BLOCK) == math.floor((max_y - eps) / WATER_BLOCK)
    return 'ok' if (same_x and same_y) else 'cross'


def _water_blocks(min_x, min_y, max_x, max_y):
    """Block indices (0..11 each axis) a polygon overlaps — the engine's
    post-pass (0x6E7B30) registers it in every one of them."""
    def _rng(lo, hi):
        a = max(0, min(11, int(math.floor((lo + WORLD_HALF) / WATER_BLOCK))))
        b = max(0, min(11, int(math.ceil((hi + WORLD_HALF) / WATER_BLOCK)) - 1))
        return range(a, max(a, b) + 1)
    return [(i, j) for i in _rng(min_x, max_x) for j in _rng(min_y, max_y)]


# ═══════════════════════════════════════════════════════════════════
# IPL (text + binary)
# ═══════════════════════════════════════════════════════════════════

def check_ipl(ipl, known_ids=None, *, filename='', binary=False,
              related_inst_count=None, known_complete=True, known_label=''):
    """``ipl`` — ``core.ipl.IplFile``. ``known_ids`` — the set of model ids
    defined by the IDEs the game loads (None = skip the «defined» check;
    the range check always runs). ``known_complete=False`` says the set
    was built from a single picked IDE (``known_label``) rather than from
    every IDE in gta.dat / default.dat — an id outside it is then only a
    WARNING (it may live in another loaded IDE), not a fatal: any vanilla
    IPL mixes instances from several IDEs. ``filename`` — the file name the IPL
    will be written to (interior-ness of occluders, streamed basename).
    ``binary=True`` audits the ``bnry`` rules instead of the text ones;
    a streamed IPL's ``lod_index`` addresses the inst list of the gta.dat
    TEXT IPL with the same basename (DAT-22), so pass that list's length
    as ``related_inst_count`` (None = range unknown, only the sign is
    checked). Returns ``(fatal, warnings)``."""
    from . import ipl as _ipl
    fatal, warnings = [], []
    base = filename.replace('\\', '/').rsplit('/', 1)[-1]
    stem = base.rsplit('.', 1)[0] if '.' in base else base

    # ── inst ─────────────────────────────────────────────────────
    insts = ipl.instances
    n_inst = len(insts)
    lod_pool = related_inst_count if binary else n_inst
    children = {}
    for idx, i in enumerate(insts):
        label = _t("inst #{0} ({1}, id {2})").format(idx, i.model_name or '?', i.model_id)
        if not 0 <= i.model_id < IPL_MAX_MODEL_ID:
            fatal.append(_t(
                "{0}: id модели вне 0..19999 — чтение за пределами ms_modelInfoPtrs, краш (DAT-21)."
            ).format(label))
        elif known_ids is not None and i.model_id not in known_ids:
            if known_complete:
                fatal.append(_t(
                    "{0}: id модели не определён ни в одном IDE — NULL в LinkLods, краш при загрузке (DAT-21)."
                ).format(label))
            else:
                warnings.append(_t(
                    "{0}: id модели нет в {1} — он должен быть определён в другом загружаемом IDE, иначе NULL в LinkLods и краш (DAT-21)."
                ).format(label, known_label or 'IDE'))
        if len(i.model_name) > IPL_INST_NAME_MAX:
            fatal.append(_t(
                "{0}: имя модели длиннее {1} символов — переполнение буфера name[24] (DAT-09)."
            ).format(label, IPL_INST_NAME_MAX))
        if not all(_fin(v) for v in (i.pos_x, i.pos_y, i.pos_z,
                                      i.rot_x, i.rot_y, i.rot_z, i.rot_w)):
            fatal.append(_t(
                "{0}: NaN/inf в позиции или повороте — матрица объекта станет NaN (DAT-23)."
            ).format(label))
            continue
        # DAT-22: lod must be -1 or an index into the inst list of THIS
        # text IPL (streamed: of the same-name text IPL from gta.dat).
        li = i.lod_index
        if li != -1:
            if li < 0 or (lod_pool is not None and li >= lod_pool):
                fatal.append(_t(
                    "{0}: lod_index {1} вне списка inst ({2}: 0..{3}) — LinkLods разыменует мусор (DAT-22)."
                ).format(label, li,
                         _t("одноимённого текстового IPL") if binary else _t("этого файла"),
                         (lod_pool or 0) - 1))
            elif li == idx and not binary:
                warnings.append(_t(
                    "{0}: lod_index указывает на саму себя (DAT-22)."
                ).format(label))
            else:
                children[li] = children.get(li, 0) + 1
        # DAT-23: normalised quaternion; |rw| > 1 → acos → NaN heading.
        norm = math.sqrt(i.rot_x ** 2 + i.rot_y ** 2 + i.rot_z ** 2 + i.rot_w ** 2)
        if abs(i.rot_w) > 1.0 + 1e-4:
            fatal.append(_t(
                "{0}: |rot_w| = {1:.4f} > 1 — acos даёт NaN, объект невидим и без коллизии (DAT-23)."
            ).format(label, i.rot_w))
        elif abs(norm - 1.0) > 0.01:
            warnings.append(_t(
                "{0}: кватернион не нормирован (|q| = {1:.4f}) — SetRotate даст масштабированную матрицу (DAT-23)."
            ).format(label, norm))
        # DAT-24: interior byte + 5 flag bits.
        interior = int(i.interior)
        if interior < 0 or (interior & 0xFF) != interior and (interior & ~0x1FFF):
            warnings.append(_t(
                "{0}: поле interior {1} содержит биты вне 0..255 + 0x100..0x1000 — движок их игнорирует (DAT-24)."
            ).format(label, interior))
        if abs(i.pos_x) > WORLD_HALF or abs(i.pos_y) > WORLD_HALF:
            warnings.append(_t(
                "{0}: позиция ({1:.0f}, {2:.0f}) за пределами ±3000 — CEntity::Add прижмёт её к крайнему сектору (DAT-25)."
            ).format(label, i.pos_x, i.pos_y))
        if not binary:
            _check_line_len(_ipl._format_inst_line(i), label, fatal)
    for li, cnt in children.items():
        if cnt > IPL_MAX_LOD_CHILDREN:
            warnings.append(_t(
                "inst #{0}: {1} LOD-детей — счётчик m_nNumLodChildren восьмибитный, переполнится (DAT-22)."
            ).format(li, cnt))
    if binary:
        if n_inst > BNRY_COUNT_MAX or len(ipl.cars) > BNRY_COUNT_MAX:
            fatal.append(_t(
                "bnry: {0} inst / {1} cars — счётчики читаются как int16, секция ≥ 32768 пропускается (DAT-37)."
            ).format(n_inst, len(ipl.cars)))
        if len(stem) > STREAMED_IPL_NAME_MAX:
            fatal.append(_t(
                "bnry: имя файла «{0}» длиннее {1} символов — переполняет IplDef.name[18] при AddIplSlot (DAT-39)."
            ).format(stem, STREAMED_IPL_NAME_MAX))
        extra = [name for name, lst in (
            ('cull', ipl.culls), ('grge', ipl.garages), ('enex', ipl.enexs),
            ('pick', ipl.pickups), ('auzo', ipl.auzos), ('jump', ipl.jumps),
            ('occl', ipl.occls), ('tcyc', ipl.tcycs), ('zone', ipl.zones)) if lst]
        if extra:
            warnings.append(_t(
                "bnry: секции {0} в бинарном IPL не сохраняются — движок читает только inst и cars (DAT-37)."
            ).format(', '.join(extra)))
    else:
        if n_inst > IPL_MAX_INST_TEXT:
            fatal.append(_t(
                "{0} строк inst в одном текстовом IPL — gCurrIplInstances вмещает {1} (DAT-26)."
            ).format(n_inst, IPL_MAX_INST_TEXT))
        elif n_inst > IPL_INST_TEXT_SAFE:
            warnings.append(_t(
                "{0} строк inst в одном текстовом IPL — ёмкость gCurrIplInstances не подтверждена (1000 по plugin-sdk, ваниль ≤ 718) (DAT-26)."
            ).format(n_inst))

    # ── zone ─────────────────────────────────────────────────────
    zf, zw = check_zones(ipl.zones)
    fatal += zf
    warnings += zw

    # ── cull ─────────────────────────────────────────────────────
    attr = tunnel = mirror = 0
    dropped = []
    for idx, c in enumerate(ipl.culls):
        if c.has_mirror:
            mirror += 1
            continue
        flags = int(c.flag) & 0xFFFF
        if flags & 0x880:
            tunnel += 1
        if flags & 0xF77F:
            attr += 1
        elif not (flags & 0x880):
            dropped.append(idx)
    if dropped:
        warnings.append(_t(
            "cull: {0} зон с нулевыми флагами после маски — движок их отбрасывает ({1}) (DAT-28)."
        ).format(len(dropped), _short_list(dropped)))
    if attr > CULL_MAX_ATTR:
        fatal.append(_t(
            "cull: {0} атрибутных зон в файле — таблица вмещает {1} (ваниль уже 1180) (DAT-28)."
        ).format(attr, CULL_MAX_ATTR))
    if tunnel > CULL_MAX_TUNNEL:
        fatal.append(_t(
            "cull: {0} туннельных зон — таблица вмещает {1} (ваниль 36) (DAT-28)."
        ).format(tunnel, CULL_MAX_TUNNEL))
    if mirror > CULL_MAX_MIRROR:
        fatal.append(_t(
            "cull: {0} зеркальных зон — таблица вмещает {1} (ваниль 65) (DAT-28)."
        ).format(mirror, CULL_MAX_MIRROR))

    # ── occl ─────────────────────────────────────────────────────
    is_interior = stem.lower().endswith('int')
    zero_dims = []
    for idx, o in enumerate(ipl.occls):
        dims = (int(o.width_x), int(o.width_y), int(o.height))
        if sum(1 for d in dims if d == 0) >= 2:
            zero_dims.append(idx)
    if zero_dims:
        warnings.append(_t(
            "occl: {0} объёмов с двумя нулевыми размерами — COcclusion::AddOne их отбрасывает ({1}) (DAT-29)."
        ).format(len(zero_dims), _short_list(zero_dims)))
    n_occl = len(ipl.occls) - len(zero_dims)
    limit = OCCL_MAX_INTERIOR if is_interior else OCCL_MAX_MAP
    if n_occl > limit:
        warnings.append(_t(
            "occl: {0} окклюдеров в файле при лимите {1} ({2}) — лишние молча отбрасываются (DAT-29)."
        ).format(n_occl, limit,
                 _t("интерьер: имя файла кончается на int.ipl") if is_interior
                 else _t("карта")))

    # ── grge ─────────────────────────────────────────────────────
    for idx, g in enumerate(ipl.garages):
        name = g.name.strip()
        if len(name) > GRGE_NAME_MAX:
            fatal.append(_t(
                "grge #{0}: имя «{1}» длиннее {2} символов — name[8] лежит под адресом возврата, краш (DAT-31)."
            ).format(idx, name, GRGE_NAME_MAX))
        elif not name or ' ' in name:
            warnings.append(_t(
                "grge #{0}: имя «{1}» пустое или с пробелом — sscanf не наберёт 11 полей, гараж пропущен (DAT-31)."
            ).format(idx, name))
        _check_line_len(_ipl._format_grge_line(g), f"grge #{idx}", fatal)
    if len(ipl.garages) > GRGE_MAX:
        fatal.append(_t(
            "grge: {0} гаражей — aGarages вмещает {1} (ваниль заполняет все 50) (DAT-31)."
        ).format(len(ipl.garages), GRGE_MAX))

    # ── enex ─────────────────────────────────────────────────────
    for idx, e in enumerate(ipl.enexs):
        name = e.name.strip().strip('"')
        if len(name) > ENEX_NAME_MAX:
            fatal.append(_t(
                "enex #{0}: имя «{1}» длиннее {2} символов — переполнение name[32], краш (DAT-30)."
            ).format(idx, name, ENEX_NAME_MAX))
        elif any(ch.isspace() for ch in name):
            warnings.append(_t(
                "enex #{0}: имя «{1}» с пробелом — %s оборвёт его, остальные поля получат значения по умолчанию (DAT-30)."
            ).format(idx, name))
        elif len(name) > ENEX_NAME_STORED:
            warnings.append(_t(
                "enex #{0}: имя «{1}» длиннее {2} символов — AddOne хранит только {2} (strncpy), пара по имени может не совпасть (DAT-30)."
            ).format(idx, name, ENEX_NAME_STORED))
        _check_line_len(_ipl._format_enex_line(e), f"enex #{idx}", fatal)
    if len(ipl.enexs) > ENEX_MAX:
        warnings.append(_t(
            "enex: {0} маркеров в файле — пул на {1} (ваниль 376); лишние пишут флаги в запись 0 (DAT-30)."
        ).format(len(ipl.enexs), ENEX_MAX))

    # ── auzo ─────────────────────────────────────────────────────
    boxes = spheres = 0
    for idx, a in enumerate(ipl.auzos):
        name = a.name.strip().strip('"')
        if len(name) >= AUZO_NAME_CRASH:
            fatal.append(_t(
                "auzo #{0}: имя «{1}» длиннее 15 символов — переполнение name[16], краш (DAT-36)."
            ).format(idx, name))
        elif len(name) > AUZO_NAME_MAX:
            warnings.append(_t(
                "auzo #{0}: имя «{1}» длиннее {2} символов — в 8-байтовом поле теряется NUL, имя читается мусором (DAT-36)."
            ).format(idx, name, AUZO_NAME_MAX))
        if a.is_sphere:
            spheres += 1
        else:
            boxes += 1
    if boxes > AUZO_MAX_BOX:
        fatal.append(_t(
            "auzo: {0} боксов — таблица вмещает {1} (DAT-36)."
        ).format(boxes, AUZO_MAX_BOX))
    if spheres > AUZO_MAX_SPHERE:
        fatal.append(_t(
            "auzo: {0} сфер — таблица вмещает {1} и в ванили уже полна; 4-я затирает состояние камеры (DAT-36)."
        ).format(spheres, AUZO_MAX_SPHERE))

    # ── tcyc ─────────────────────────────────────────────────────
    if len(ipl.tcycs) > TCYC_MAX:
        fatal.append(_t(
            "tcyc: {0} боксов — m_aBoxes вмещает {1} (ваниль 8); лишние пишут поверх соседних глобалов (DAT-35)."
        ).format(len(ipl.tcycs), TCYC_MAX))

    # ── cars ─────────────────────────────────────────────────────
    bad_cars = [idx for idx, c in enumerate(ipl.cars)
                if c.car_id != -1 and not CARGEN_MODEL_MIN <= c.car_id <= CARGEN_MODEL_MAX]
    if bad_cars:
        warnings.append(_t(
            "cars: {0} генераторов с моделью вне -1 / 400..630 — CreateCarGenerator их отбрасывает ({1}) (DAT-34)."
        ).format(len(bad_cars), _short_list(bad_cars)))
    if len(ipl.cars) > CARGEN_MAX:
        warnings.append(_t(
            "cars: {0} генераторов — пул на {1}, лишние отбрасываются (DAT-34)."
        ).format(len(ipl.cars), CARGEN_MAX))

    # ── pick ─────────────────────────────────────────────────────
    bad_pick = [idx for idx, p in enumerate(ipl.pickups) if p.pickup_id not in PICKUP_IDS]
    if bad_pick:
        warnings.append(_t(
            "pick: {0} пикапов с id вне таблицы движка (4..6, 9..55 без 30 и 42) — отбрасываются ({1}) (DAT-33)."
        ).format(len(bad_pick), _short_list(bad_pick)))

    return fatal, warnings


# ═══════════════════════════════════════════════════════════════════
# zones (.zon and IPL «zone»)
# ═══════════════════════════════════════════════════════════════════

def check_zones(zones):
    """``zones`` — list of ``core.zon.Zone`` or ``core.ipl.IplZone``.
    Returns ``(fatal, warnings)``."""
    fatal, warnings = [], []
    nav = mp = 0
    for idx, z in enumerate(zones):
        name = (z.name or '').strip()
        info = (getattr(z, 'gxt', None) or getattr(z, 'info', None) or '').strip()
        label = _t("zone #{0} ({1})").format(idx, name or '?')
        raw = getattr(z, 'raw', '')
        if raw and hasattr(z, 'gxt'):
            # zon.Zone re-emits its original line only while unchanged;
            # an edited zone is reformatted (10 fields) — judge the text
            # that will actually be written.
            from .zon import zone_line
            if zone_line(z) != raw:
                raw = ''
        if raw:
            ntok = len(raw.replace(',', ' ').split())
            if ntok != 10:
                fatal.append(_t(
                    "{0}: в строке {1} полей вместо 10 — LoadZone вызывает CreateZone только при ровно 10 (DAT-27)."
                ).format(label, ntok))
        if not name or any(ch.isspace() for ch in name) or any(ch.isspace() for ch in info):
            fatal.append(_t(
                "{0}: имя или GXT-ключ пусты либо содержат пробел — sscanf не наберёт ровно 10 полей, зона выброшена (DAT-27)."
            ).format(label))
        if len(name) > ZONE_NAME_MAX:
            warnings.append(_t(
                "{0}: имя длиннее {1} символов — CreateZone хранит 7 (strncpy), остаток отрезается (DAT-27)."
            ).format(label, ZONE_NAME_MAX))
        if len(info) >= ZONE_INFO_CRASH:
            fatal.append(_t(
                "{0}: GXT-ключ «{1}» длиннее 11 символов — переполнение info[12], затирает границы зоны (DAT-27b)."
            ).format(label, info))
        elif len(info) > ZONE_INFO_MAX:
            warnings.append(_t(
                "{0}: GXT-ключ «{1}» длиннее {2} символов — хранится 7, остаток отрезается (DAT-27)."
            ).format(label, info, ZONE_INFO_MAX))
        zt = int(z.zone_type)
        if zt in (0, 1):
            nav += 1
        elif zt == 3:
            mp += 1
        else:
            warnings.append(_t(
                "{0}: тип {1} — ваниль принимает 0/1 (навигация) и 3 (карта), остальное молча отбрасывается (DAT-27)."
            ).format(label, zt))
        for v in (z.x1, z.y1, z.z1, z.x2, z.y2, z.z2):
            if not _fin(v) or abs(v) > 32767:
                warnings.append(_t(
                    "{0}: координата {1} не влезает в int16 (DAT-27)."
                ).format(label, v))
                break
        if not 0 <= int(z.level) <= 255:
            warnings.append(_t(
                "{0}: level {1} хранится байтом (DAT-27)."
            ).format(label, z.level))
    if nav > ZONE_MAX_NAV:
        fatal.append(_t(
            "zone: {0} навигационных зон в файле — NavigationZoneArray вмещает {1} (ваниль уже 378); 381-я затирает m_CurrLevel (DAT-27)."
        ).format(nav, ZONE_MAX_NAV))
    if mp > ZONE_MAX_MAP:
        fatal.append(_t(
            "zone: {0} зон карты в файле — MapZoneArray вмещает {1}; 40-я затирает счётчик zone-info (DAT-27)."
        ).format(mp, ZONE_MAX_MAP))
    return fatal, warnings


# ═══════════════════════════════════════════════════════════════════
# IDE
# ═══════════════════════════════════════════════════════════════════

def _name_check(label, name, txd, fatal, txd_fatal=True):
    if len(name) > IDE_NAME_MAX:
        fatal.append(_t(
            "{0}: имя модели «{1}» длиннее {2} символов — name[24] переполняется в буфер txd, хеш модели ломается, она никогда не загрузится (DAT-09)."
        ).format(label, name, IDE_NAME_MAX))
    if len(txd) > IDE_NAME_MAX:
        (fatal if txd_fatal else fatal).append(_t(
            "{0}: имя TXD «{1}» длиннее {2} символов — txd[24] лежит под адресом возврата, краш (DAT-09)."
        ).format(label, txd, IDE_NAME_MAX))
    if any(ch.isspace() for ch in name) or any(ch.isspace() for ch in txd):
        fatal.append(_t(
            "{0}: имя модели или TXD содержит пробел — сдвинет все поля строки (DAT-08b)."
        ).format(label))


def check_ide(ide, *, anim_groups=None):
    """``ide`` — ``core.ide.IdeFile``. ``anim_groups`` — optional set of
    group names from animgrp.dat for the peds check. Returns
    ``(fatal, warnings)``."""
    from . import ide as _ide
    fatal, warnings = [], []
    seen = {}
    defined = set()

    def _id_check(label, mid):
        if not 0 <= mid < IPL_MAX_MODEL_ID:
            fatal.append(_t(
                "{0}: id вне 0..19999 — запись за пределы ms_modelInfoPtrs (DAT-06)."
            ).format(label))
            return
        if mid in seen:
            warnings.append(_t(
                "{0}: id уже определён в этом файле ({1}) — вторая запись молча заменяет первую (DAT-07)."
            ).format(label, seen[mid]))
        else:
            seen[mid] = label
        defined.add(mid)

    n_atomic = n_damage = n_time = 0
    for o in ide.objects:
        label = _t("{0} {1} ({2})").format('tobj' if o.is_timed else 'objs', o.model_id, o.model_name)
        _id_check(label, o.model_id)
        _name_check(label, o.model_name, o.txd_name, fatal)
        if o.is_timed:
            n_time += 1
        elif int(o.flags) & 0x1000:
            n_damage += 1
        else:
            n_atomic += 1
        extras = list(o.extra_draw_distances)
        if len(extras) > 2:
            fatal.append(_t(
                "{0}: {1} дистанций — движок знает формы с 1..3 мешами, строка прочтётся мусором (DAT-08)."
            ).format(label, len(extras) + 1))
        if not extras and o.draw_distance < IDE_DD_MIN:
            # Silent garbage, not a crash: vanilla dynamic2.IDE ships
            # ``1489, DYN_SALE_POST, BREAK_STREET2, 1, 0`` (→ dd 0, invisible).
            warnings.append(_t(
                "{0}: дистанция {1} < 4.0 — LoadObject перечитает строку как legacy-форму со счётчиком мешей: дистанция возьмётся из колонки флагов, объект станет невидимым (DAT-08)."
            ).format(label, o.draw_distance))
        elif o.draw_distance < IDE_DD_INVISIBLE:
            warnings.append(_t(
                "{0}: дистанция {1} < 2.0 — экземпляры создаются невидимыми (DAT-25b)."
            ).format(label, o.draw_distance))
        if int(o.flags) & ~IDE_FLAG_KNOWN_BITS:
            # Vanilla itself uses 0x2 / 0x20 / 0x10000.. that the engine
            # ignores — only bits beyond every documented flag are odd.
            warnings.append(_t(
                "{0}: флаги 0x{1:X} содержат биты выше 0x400000, которых движок не знает (DAT-14)."
            ).format(label, int(o.flags)))
        if o.is_timed and not (0 <= int(o.time_on) <= 24 and 0 <= int(o.time_off) <= 24):
            warnings.append(_t(
                "{0}: часы {1}..{2} вне 0..24 — хранятся байтами (DAT-08)."
            ).format(label, o.time_on, o.time_off))
        line = (_ide._format_tobj_line(o) if o.is_timed else _ide._format_obj_line(o))
        _check_line_len(line, label, fatal)

    n_clump = 0
    for a in ide.anims:
        label = _t("anim {0} ({1})").format(a.model_id, a.model_name)
        _id_check(label, a.model_id)
        _name_check(label, a.model_name, a.txd_name, fatal)
        if len(a.anim_file) > IDE_ANIM_NAME_MAX:
            fatal.append(_t(
                "{0}: имя анимации «{1}» длиннее {2} символов — anim[16] лежит под буфером имени модели и затирает его (DAT-10)."
            ).format(label, a.anim_file, IDE_ANIM_NAME_MAX))
        n_clump += 1
        _check_line_len(_ide._format_anim_line(a), label, fatal)
    for h in ide.hiers:
        label = _t("hier {0} ({1})").format(h.model_id, h.model_name)
        _id_check(label, h.model_id)
        _name_check(label, h.model_name, h.txd_name, fatal)
        n_clump += 1

    for w in ide.weaps:
        label = _t("weap {0} ({1})").format(w.model_id, w.model_name)
        _id_check(label, w.model_id)
        _name_check(label, w.model_name, w.txd_name, fatal)
        if len(w.anim_name) > IDE_ANIM_NAME_MAX:
            fatal.append(_t(
                "{0}: имя анимации «{1}» длиннее {2} символов — переполнение anim[16] (DAT-09)."
            ).format(label, w.anim_name, IDE_ANIM_NAME_MAX))

    for c in ide.cars:
        label = _t("cars {0} ({1})").format(c.model_id, c.model_name)
        _id_check(label, c.model_id)
        _name_check(label, c.model_name, c.txd_name, fatal)
        if len(c.veh_type) > IDE_CAR_TYPE_MAX:
            fatal.append(_t(
                "{0}: тип «{1}» длиннее 7 символов — type[8] затирает уже прочитанный id (DAT-13)."
            ).format(label, c.veh_type))
        elif c.veh_type not in CAR_TYPES:
            warnings.append(_t(
                "{0}: тип «{1}» неизвестен движку — останется значение конструктора (DAT-13)."
            ).format(label, c.veh_type))
        if len(c.veh_class) > IDE_CAR_CLASS_MAX:
            fatal.append(_t(
                "{0}: класс «{1}» длиннее 15 символов — переполнение class[16] (DAT-09)."
            ).format(label, c.veh_class))
        elif c.veh_class not in CAR_CLASSES:
            warnings.append(_t(
                "{0}: класс «{1}» неизвестен движку — останется значение конструктора (DAT-13)."
            ).format(label, c.veh_class))
        for fname, val, lim in (('handling', c.handling_id, IDE_CAR_HANDLING_MAX),
                                ('game name', c.game_name, IDE_CAR_GAMENAME_MAX),
                                ('anims', c.anims, IDE_CAR_ANIMS_MAX)):
            if len(val) > lim:
                fatal.append(_t(
                    "{0}: поле {1} «{2}» длиннее {3} символов — переполнение стекового буфера (DAT-09)."
                ).format(label, fname, val, lim))
        _check_line_len(_ide._format_car_line(c), label, fatal)

    for p in ide.peds:
        label = _t("peds {0} ({1})").format(p.model_id, p.model_name)
        _id_check(label, p.model_id)
        if len(p.model_name) > IDE_NAME_MAX:
            fatal.append(_t(
                "{0}: имя модели «{1}» длиннее {2} символов — name[24] переполняется в буфер txd, хеш модели ломается, она никогда не загрузится (DAT-09)."
            ).format(label, p.model_name, IDE_NAME_MAX))
        if len(p.txd_name) > IDE_NAME_MAX:
            # peds: txd[24] overflows into voice1, which is parsed later —
            # the txd loses its NUL (textureless ped), no crash.
            warnings.append(_t(
                "{0}: имя TXD «{1}» длиннее {2} символов — теряет NUL и склеивается с voice1, пед без текстур (DAT-09)."
            ).format(label, p.txd_name, IDE_NAME_MAX))
        for fname, val, lim in (('ped type', p.ped_type, IDE_PED_FIELD_MAX),
                                ('stats', p.behaviour, IDE_PED_FIELD_MAX),
                                ('anim group', p.anim_group, IDE_PED_FIELD_MAX),
                                ('anim file', p.anim_file, IDE_PED_ANIMFILE_MAX),
                                ('audio type', p.voice_archive, IDE_PED_AUDIO_MAX),
                                ('voice1', p.voice1, IDE_PED_VOICE_MAX),
                                ('voice2', p.voice2, IDE_PED_VOICE_MAX)):
            if len(val) > lim:
                fatal.append(_t(
                    "{0}: поле {1} «{2}» длиннее {3} символов — переполнение стекового буфера (DAT-09)."
                ).format(label, fname, val, lim))
        if anim_groups is not None and p.anim_group not in anim_groups:
            fatal.append(_t(
                "{0}: группа анимаций «{1}» отсутствует в animgrp.dat — индекс за концом таблицы, краш при спавне (DAT-12)."
            ).format(label, p.anim_group))
        _check_line_len(_ide._format_ped_line(p), label, fatal)

    txds = set()
    for t in ide.txdps:
        for nm in (t.txd_name, t.parent_txd_name):
            if len(nm) > IDE_TXDP_NAME_MAX:
                fatal.append(_t(
                    "txdp {0}: имя «{1}» длиннее {2} символов — переполнение буфера [32] (DAT-09)."
                ).format(t.txd_name, nm, IDE_TXDP_NAME_MAX))
            txds.add(nm)
    for o in ide.objects:
        txds.add(o.txd_name)
    if len(txds) > IDE_TXD_POOL:
        fatal.append(_t(
            "{0} разных TXD в файле — пул TexDictionary на {1} записей, AddTxdSlot пишет в NULL (DAT-15)."
        ).format(len(txds), IDE_TXD_POOL))

    # store capacities (per file; the tables are global)
    for count, limit, store in ((n_atomic, IDE_STORE_ATOMIC, 'atomic (objs)'),
                                (n_damage, IDE_STORE_DAMAGE, 'damage-atomic (objs, флаг 0x1000)'),
                                (n_time, IDE_STORE_TIME, 'time (tobj)'),
                                (n_clump, IDE_STORE_CLUMP, 'clump (hier + anim)'),
                                (len(ide.cars), IDE_STORE_VEHICLE, 'vehicle (cars)'),
                                (len(ide.peds), IDE_STORE_PED, 'ped (peds)'),
                                (len(ide.weaps), IDE_STORE_WEAPON, 'weapon (weap)')):
        if count > limit:
            fatal.append(_t(
                "{0} записей в хранилище {1} — оно вмещает {2}; лишние затирают счётчик следующего хранилища (DAT-07)."
            ).format(count, store, limit))

    # 2dfx section: ≤ 100, consecutive per model, model defined
    fx = ide.fx_2dfx
    if len(fx) > IDE_2DFX_MAX:
        fatal.append(_t(
            "2dfx: {0} записей — хранилище на {1} (ваниль уже занимает 97) (DAT-16)."
        ).format(len(fx), IDE_2DFX_MAX))
    last = None
    seen_fx = set()
    for e in fx:
        if e.model_id != last and e.model_id in seen_fx:
            fatal.append(_t(
                "2dfx: записи модели {0} идут не подряд — Add2dEffect хранит первый индекс + счётчик, эффекты смешаются (DAT-16)."
            ).format(e.model_id))
        seen_fx.add(e.model_id)
        last = e.model_id
        if e.model_id not in defined:
            warnings.append(_t(
                "2dfx: модель {0} не определена в этом IDE — если её нет и в ранее загруженном IDE, ms_modelInfoPtrs даст NULL, краш (DAT-16)."
            ).format(e.model_id))
    return fatal, warnings


# ═══════════════════════════════════════════════════════════════════
# timecyc.dat
# ═══════════════════════════════════════════════════════════════════

_TC_COLOUR_KEYS = ('amb', 'amb_obj', 'dir', 'sky_top', 'sky_bot', 'sun_core',
                   'sun_corona', 'low_clouds', 'bottom_clouds', 'water',
                   'amb_bl', 'amb_obj_bl', 'top_clouds', 'blur')   # III/VC
_TC_BYTE_KEYS = ('shadow', 'light_shad', 'pole_shad', 'cloud_alpha',
                 'highlight_min', 'water_fog')


def check_timecyc(cyc):
    """``cyc`` — ``core.timecyc.TimecycFile`` (or a flat list of slots —
    then the file-level checks are skipped). Returns ``(fatal, warnings)``."""
    fatal, warnings = [], []
    game = getattr(cyc, 'game', 'SA')
    shape = TIMECYC_GAME_SHAPE.get(game)
    widths = (shape[2],) if shape else TIMECYC_WIDTHS
    weathers = getattr(cyc, 'weathers', None)
    if weathers is None:
        slots = [(None, i, s) for i, s in enumerate(cyc)]
    else:
        slots = [(w.name, i, s) for w in weathers for i, s in enumerate(w.slots)]
        # DAT-42a: exactly NUMWEATHERS × NUMHOURS data lines are consumed.
        n = len(slots)
        if shape:
            need = shape[0] * shape[1]
            if n < need:
                fatal.append(_t(
                    "Строк данных {0}, нужно ровно {1} ({2} погод × 24 часа) — движок читает строки подряд без проверки конца буфера (DAT-42a)."
                ).format(n, need, shape[0]))
            elif n > need:
                warnings.append(_t(
                    "Строк данных {0} при {1} читаемых — хвост файла игнорируется (DAT-42a)."
                ).format(n, need))
        elif n < TIMECYC_LINES:
            fatal.append(_t(
                "Строк данных {0}, нужно ровно {1} (23 погоды × 8 срезов) — на короткий файл движок вызывает sscanf(NULL), краш (DAT-42a)."
            ).format(n, TIMECYC_LINES))
        elif n > TIMECYC_LINES:
            warnings.append(_t(
                "Строк данных {0} при {1} читаемых — хвост файла игнорируется (DAT-42a)."
            ).format(n, TIMECYC_LINES))
        # DAT-42b: only '/'-prefixed and blank lines are skipped.
        lines = getattr(cyc, 'lines', [])
        line_map = getattr(cyc, 'line_map', {})
        for idx, line in enumerate(lines):
            st = line.strip()
            if not st or st.startswith('/') or idx in line_map:
                continue
            fatal.append(_t(
                "Строка {0} «{1}» — не данные и не комментарий на «//»: движок скормит её sscanf, все следующие срезы сдвинутся (DAT-42b)."
            ).format(idx + 1, st[:30]))

    for wname, i, s in slots:
        label = _t("{0} срез {1}").format(wname or '?', i)
        if s.width not in widths:
            warnings.append(_t(
                "{0}: {1} чисел в строке вместо {2} — недостающие колонки движок берёт с предыдущей строки (DAT-42c)."
            ).format(label, s.width, "/".join(str(w) for w in widths)))
        if getattr(s, 'malformed', False):
            warnings.append(_t(
                "{0}: sscanf споткнулся посреди строки (дробное число в целой колонке) — остаток колонок игра берёт с предыдущей строки; при правке срез запишется целиком (DAT-42c)."
            ).format(label))
        v = s.values
        for key in _TC_COLOUR_KEYS:
            vals = v.get(key, ())
            if any(not 0 <= x <= 255 for x in vals):
                warnings.append(_t(
                    "{0}: {1} = {2} вне 0..255 — хранится байтом, значение обернётся (DAT-42d)."
                ).format(label, key, [round(x) for x in vals]))
        if shape:
            continue          # III/VC keep int32/float — no packing rules
        for key in ('postfx1', 'postfx2'):
            vals = v.get(key, ())
            # uint8(a*2): 0..127 exact; vanilla's 255 wraps to 254
            # (harmless); anything in 128..254 or beyond wraps badly.
            if vals and not (0 <= vals[0] <= TIMECYC_POSTFX_ALPHA_MAX or vals[0] == 255):
                warnings.append(_t(
                    "{0}: альфа {1} = {2} — хранится как uint8(a·2): 0..127 точно, 255 → 254, остальное обернётся (DAT-42d)."
                ).format(label, key, vals[0]))
            if any(not 0 <= x <= 255 for x in vals[1:]):
                warnings.append(_t(
                    "{0}: {1} = {2} вне 0..255 — хранится байтом, значение обернётся (DAT-42d)."
                ).format(label, key, [round(x) for x in vals]))
        for key in ('sun_size', 'spr_size', 'spr_bright'):
            x = v.get(key, [0.0])[0]
            if not -12.8 <= x <= TIMECYC_INT8_MAX:
                warnings.append(_t(
                    "{0}: {1} = {2} — хранится как int8(v·10), максимум 12.7 (DAT-42d)."
                ).format(label, key, x))
        x = v.get('light_on_ground', [0.0])[0]
        if not 0 <= x <= TIMECYC_LIGHTS_GROUND_MAX:
            warnings.append(_t(
                "{0}: light_on_ground = {1} — хранится как uint8(v·10), диапазон 0..25.5 (DAT-42d)."
            ).format(label, x))
        for key in _TC_BYTE_KEYS:
            x = v.get(key, [0.0])[0]
            if not 0 <= x <= 255:
                warnings.append(_t(
                    "{0}: {1} = {2} вне 0..255 — хранится байтом (DAT-42d)."
                ).format(label, key, x))
        for key in ('far_clip', 'fog_start'):
            x = v.get(key, [0.0])[0]
            if not -32768 <= x <= 32767:
                warnings.append(_t(
                    "{0}: {1} = {2} не влезает в int16 (DAT-42d)."
                ).format(label, key, x))
        if s.width >= 52:
            x = v.get('dir_mult', [1.0])[0]
            if int(x) not in (0, 1, 2):
                warnings.append(_t(
                    "{0}: directional mult {1} — движок хранит uint8(int(v))·100, осмысленны только 0, 1, 2 (DAT-42d)."
                ).format(label, x))
    return fatal, warnings


# ═══════════════════════════════════════════════════════════════════
# plants.dat
# ═══════════════════════════════════════════════════════════════════

def check_plants(entries, surface_names=None):
    """``entries`` — list of dicts keyed like ``core.plants_dat.PLANTS_FIELDS``.
    ``surface_names`` — the COLPOINT surface names the engine knows
    (None = skip that check). Returns ``(fatal, warnings)``."""
    from .plants_dat import PLANTS_FIELDS, _format_line
    fatal, warnings = [], []
    surfaces = []
    for idx, e in enumerate(entries):
        name = str(e.get('name', ''))
        label = _t("plants #{0} ({1})").format(idx, name or '?')
        if not name or any(ch.isspace() for ch in name) or ',' in name:
            fatal.append(_t(
                "{0}: имя поверхности пустое или с пробелом — строка не даст ровно 18 токенов, LoadPlantsDat вернёт false, трава отключится целиком (DAT-46a)."
            ).format(label))
        missing = [k for k, _kind in PLANTS_FIELDS if k not in e]
        if missing:
            fatal.append(_t(
                "{0}: нет полей {1} — строка не даст 18 токенов, трава отключится целиком (DAT-46a)."
            ).format(label, ', '.join(missing)))
        if name.startswith(';'):
            fatal.append(_t(
                "{0}: имя начинается с «;» — движок примет строку за комментарий (DAT-46a)."
            ).format(label))
        if surface_names is not None and name not in surface_names:
            fatal.append(_t(
                "{0}: поверхность «{1}» неизвестна движку (GetSurfaceIdFromName) — LoadPlantsDat вернёт false, трава отключится целиком (DAT-46a)."
            ).format(label, name))
        if name not in surfaces:
            surfaces.append(name)
        try:
            pcd = int(e.get('pcd_id', 0))
            slot = int(e.get('slot_id', 0))
            model = int(e.get('model_id', 0))
            uv = int(e.get('uv_off', 0))
        except (TypeError, ValueError):
            fatal.append(_t(
                "{0}: нечисловые id — sscanf/atoi даст мусор (DAT-46b)."
            ).format(label))
            continue
        if not 0 <= pcd <= 2:
            warnings.append(_t(
                "{0}: PCDid {1} вне 0..2 — движок подставит 0 и затрёт первое определение (DAT-46b)."
            ).format(label, pcd))
        if not 0 <= slot <= PLANTS_SLOT_MAX:
            fatal.append(_t(
                "{0}: SlotID {1} вне 0..3 — индекс за пределами PC_PlantModelsTab, мусор/краш при отрисовке (DAT-46b)."
            ).format(label, slot))
        elif slot > PLANTS_SLOT_LOADED:
            warnings.append(_t(
                "{0}: SlotID {1} — из models\\grass загружаются только слоты 0 и 1 (DAT-46b)."
            ).format(label, slot))
        if not 0 <= model <= 3:
            fatal.append(_t(
                "{0}: ModelID {1} вне 0..3 — индекс за пределами таблицы моделей, мусор/краш (DAT-46b)."
            ).format(label, model))
        if not 0 <= uv <= 3:
            fatal.append(_t(
                "{0}: UVoff {1} вне 0..3 — четыре текстуры на слот (DAT-46b)."
            ).format(label, uv))
        for key in ('r', 'g', 'b', 'intensity', 'var_i', 'alpha'):
            try:
                x = int(e.get(key, 0))
            except (TypeError, ValueError):
                x = -1
            if not 0 <= x <= 255:
                warnings.append(_t(
                    "{0}: {1} = {2} вне 0..255 — хранится байтом (DAT-46b)."
                ).format(label, key, e.get(key)))
        for key in ('scl_xy', 'scl_z', 'scl_var_xy', 'scl_var_z',
                    'wbend_scl', 'wbend_var', 'density'):
            if not _fin(e.get(key, 0.0)):
                fatal.append(_t(
                    "{0}: {1} не число (DAT-46a)."
                ).format(label, key))
        _check_line_len(_format_line(e), label, fatal)
    if len(surfaces) > PLANTS_MAX_SURFACES:
        fatal.append(_t(
            "{0} разных поверхностей — таблица на {1}; LoadPlantsDat вернёт false, трава отключится целиком (DAT-46a)."
        ).format(len(surfaces), PLANTS_MAX_SURFACES))
    return fatal, warnings


# ═══════════════════════════════════════════════════════════════════
# effects.fxp
# ═══════════════════════════════════════════════════════════════════

def check_fxp(project, txd_textures=None):
    """``project`` — ``core.fxp.FXFile`` (or a single ``FXSystem``).
    ``txd_textures`` — texture names present in effectsPC.txd (None =
    skip). Returns ``(fatal, warnings)``."""
    fatal, warnings = [], []
    systems = getattr(project, 'systems', None)
    if systems is None:
        systems = [project]
    for sysm in systems:
        sname = sysm.name or '?'
        if len(sysm.emitters) > FXP_MAX_PRIMS:
            fatal.append(_t(
                "{0}: NUM_PRIMS = {1} — буфер имён текстур рассчитан на {2} эмиттеров, переполнение стека (DAT-47a)."
            ).format(sname, len(sysm.emitters), FXP_MAX_PRIMS))
        for ei, em in enumerate(sysm.emitters):
            elabel = _t("{0} / эмиттер {1}").format(sname, em.name)
            for tex in em.textures:
                if len(tex) > FXP_TEXTURE_NAME_MAX:
                    fatal.append(_t(
                        "{0}: имя текстуры «{1}» длиннее {2} символов — переполняет 32-байтовый слот (DAT-47a)."
                    ).format(elabel, tex, FXP_TEXTURE_NAME_MAX))
                elif (txd_textures is not None and tex != 'NULL'
                        and tex not in txd_textures):
                    warnings.append(_t(
                        "{0}: текстуры «{1}» нет в effectsPC.txd — частицы без текстуры (DAT-48)."
                    ).format(elabel, tex))
            for info in em.infos:
                ilabel = _t("{0} / {1}").format(elabel, info.type)
                expected = FXP_INFO_CURVES.get(info.type)
                if expected is None:
                    fatal.append(_t(
                        "{0}: неизвестное FX_INFO_{1}_DATA — движок пишет в NULL, краш (DAT-47b)."
                    ).format(ilabel, info.type))
                    continue
                if len(info.curves) != expected:
                    fatal.append(_t(
                        "{0}: {1} кривых вместо {2} — читатель сдвинется по строкам, все дальнейшие значения станут мусором (DAT-47c)."
                    ).format(ilabel, len(info.curves), expected))
                first_keys = None
                for cname, curve in info.curves.items():
                    nk = len(curve.keys)
                    if nk > FXP_MAX_KEYS:
                        fatal.append(_t(
                            "{0} / {1}: NUM_KEYS = {2} — хранится как int8, максимум {3} (DAT-47c)."
                        ).format(ilabel, cname, nk, FXP_MAX_KEYS))
                    if first_keys is None:
                        first_keys = nk
                    elif nk > first_keys:
                        fatal.append(_t(
                            "{0} / {1}: {2} ключей при {3} у первой кривой — массив времён выделен по первой кривой, запись за его пределы (DAT-47c)."
                        ).format(ilabel, cname, nk, first_keys))
                    elif nk < first_keys:
                        warnings.append(_t(
                            "{0} / {1}: {2} ключей при {3} у первой кривой — времена общие на все кривые info, хвост читается мусором (DAT-47c)."
                        ).format(ilabel, cname, nk, first_keys))
                    for k in curve.keys:
                        if not _fin(k.time) or abs(k.time) >= FXP_TIME_MAX:
                            fatal.append(_t(
                                "{0} / {1}: время ключа {2} — хранится как int16(t·256), нужно |t| < 128 (DAT-47c)."
                            ).format(ilabel, cname, k.time))
                            break
                    if not all(_fin(k.val) for k in curve.keys):
                        fatal.append(_t(
                            "{0} / {1}: NaN/inf в значении ключа (DAT-47c)."
                        ).format(ilabel, cname))
    return fatal, warnings


# ═══════════════════════════════════════════════════════════════════
# gta.dat
# ═══════════════════════════════════════════════════════════════════

def check_gta_dat(text):
    """``text`` — the gta.dat contents. Returns ``(fatal, warnings)``."""
    fatal, warnings = [], []
    seen_ipl = False
    for no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        _check_line_len(raw, _t("gta.dat строка {0}").format(no), fatal)
        if not line or line.startswith('#'):
            continue
        parts = line.split(None, 1)
        kw = parts[0]
        arg = parts[1].strip() if len(parts) > 1 else ''
        if kw == 'EXIT':
            break
        if kw in ('TEXDICTION', 'IPL') and len(arg) > GTADAT_SHORT_PATH_MAX:
            fatal.append(_t(
                "gta.dat строка {0}: путь {1} длиннее {2} символов — переполнение local_40[64], краш (DAT-05)."
            ).format(no, kw, GTADAT_SHORT_PATH_MAX))
        if kw == 'IDE' and len(arg) > GTADAT_IDE_PATH_MAX:
            fatal.append(_t(
                "gta.dat строка {0}: путь IDE длиннее {1} символов — переполнение local_100[256], краш (DAT-05)."
            ).format(no, GTADAT_IDE_PATH_MAX))
        if kw == 'IPL':
            seen_ipl = True
        elif kw in ('IDE', 'IMG') and seen_ipl:
            warnings.append(_t(
                "gta.dat строка {0}: {1} после первой строки IPL — Init2 уже отработал, эти модели никогда не подгрузятся (DAT-04)."
            ).format(no, kw))
        if kw in ('IDE', 'IPL', 'IMG', 'TEXDICTION', 'COLFILE', 'MODELFILE', 'HIERFILE'):
            # The argument is taken at a FIXED offset (exactly one
            # separator after the keyword; COLFILE: "COLFILE 0 path").
            tail = line[len(kw):]
            if kw == 'COLFILE':
                ok = len(tail) > 2 and tail[0] in ' 	' and tail[1].isdigit()
                tail = tail[2:] if ok else ''
            if not (len(tail) > 1 and tail[0] in ' 	' and tail[1] not in ' 	'):
                fatal.append(_t(
                    "gta.dat строка {0}: между {1} и путём должен быть ровно один пробел — иначе путь берётся со сдвигом, файл не откроется, fgets(NULL) (DAT-03)."
                ).format(no, kw))
    return fatal, warnings
