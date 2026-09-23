# INU_tools.core.skin_lint
# Pre-write audit of a skinned (ped) DffClump against what gta_sa.exe
# actually dereferences when it loads a ped model. Pure Python, no
# Blender dependency — runs on the core DffClump structures right before
# DffClump.to_bytes().
#
# Every rule cites the engine finding it mirrors (C01..C28 in
# E:\RE\addon_check\ped_skin_path.md + ped_skin_path_verify.md, W1 in
# core_roundtrip.md). Severity:
#   fatal   — the engine crashes at load / spawn, or the ped is unusable
#             (load fails, renders at the origin, stale bone palette);
#   warning — the model loads but renders / animates with garbage.
#
# Calibrated against the 29 vanilla SA skins in E:\RE\addon_check\ped:
# they produce zero fatals (cutscene skeletons lack the facial bones
# 6/7/8, so those are conditional, not always-used).

import math

from .dff import FRAME_NAME_MAX

# Bone IDs every ped dereferences on load / spawn / every frame with no
# gameplay condition (hit-col spheres, FillFrameArray, shadows) —
# missing one means writes to matrix[-1] / frames[-1] (C20).
ALWAYS_USED_BONE_IDS = frozenset({
    0, 1, 2, 3, 4, 5, 21, 22, 23, 24, 31, 32, 33, 34, 41, 42, 43,
    51, 52, 53,
})
# Dereferenced only under a gameplay condition (rain / open-top / bike /
# finger IK / facial). Vanilla cutscene skins ship without 6, 7, 8.
CONDITIONAL_BONE_IDS = frozenset({
    6, 7, 8, 25, 26, 35, 36, 44, 54, 201, 301, 302,
})

MAX_BONES = 64            # C05: 64-entry CVector table on the spawn stack
MAX_NODES = 256           # C15: 0x4000-byte matrix scratch buffer
MIN_KEYFRAME_SIZE = 28    # C04: the game's interpolator stride
HANIM_VERSION = 0x100     # C21: any other value fails the clump read
MAX_PUSH_DEPTH = 31       # C17: SkinGetBonePositionsToTable stack
WEIGHT_SUM_TOL = 1e-3     # C09
HANIM_FLAG_NO_MATRICES = 0x2  # C03


def _t(s: str) -> str:
    """Lazy translation — falls back to the raw Russian string outside
    Blender (standalone unit tests)."""
    try:
        from .. import T
        return T(s)
    except Exception:
        return s


def _frames_of(clump):
    """Frames as they will be written: the structured list, or the raw
    import-time frame list decoded (the Blender exporter clears
    ``clump.frames`` when it replays ``raw_frame_list``)."""
    if clump.frames:
        return clump.frames
    raw = getattr(clump, 'raw_frame_list', b'')
    if raw:
        from .dff import _read_frame_list
        from .rwbinary import BinaryReader
        try:
            return _read_frame_list(BinaryReader(raw), len(raw))
        except Exception:
            return []
    return []


def _is_finite_matrix(m) -> bool:
    for row in m:
        for v in row:
            if not math.isfinite(v):
                return False
    return True


def _det3(m) -> float:
    """Determinant of the 3x3 rotation/scale part of a row-major 4x4."""
    a, b, c = m[0][0], m[0][1], m[0][2]
    d, e, f = m[1][0], m[1][1], m[1][2]
    g, h, i = m[2][0], m[2][1], m[2][2]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _check_node_table(frames, table_frame, fatal, warnings):
    """HAnim node table rules (C03/C04/C15/C16/C17/C18/C19/C20)."""
    hanim = table_frame.hanim
    nodes = hanim.bones
    label = table_frame.name or '?'

    if hanim.flags & HANIM_FLAG_NO_MATRICES:
        fatal.append(_t(
            "HAnim «{0}»: флаг 0x2 (без матриц) — движок упадёт при загрузке (C03)."
        ).format(label))
    if hanim.keyframe_size < MIN_KEYFRAME_SIZE:
        fatal.append(_t(
            "HAnim «{0}»: размер ключа {1} < {2} — переполнение кучи при каждом спавне (C04)."
        ).format(label, hanim.keyframe_size, MIN_KEYFRAME_SIZE))
    if len(nodes) > MAX_NODES:
        fatal.append(_t(
            "HAnim «{0}»: {1} узлов — больше {2}, переполнение буфера матриц (C15)."
        ).format(label, len(nodes), MAX_NODES))

    # C16: the table must sit on a bone frame under the clump root; on the
    # root itself the bones are computed in model space and the ped is
    # drawn at the world origin.
    if table_frame.parent < 0:
        fatal.append(_t(
            "HAnim: таблица узлов лежит на корневом фрейме «{0}» — пед отрисуется в начале координат. Таблицу несёт первая кость (потомок корня) (C16)."
        ).format(label))

    # C18: duplicate node ids — IDGetIndex takes the first, the animation
    # binder the last, so col/IK and IFP drive different copies.
    seen = {}
    for pos, n in enumerate(nodes):
        if n.bone_id in seen:
            warnings.append(_t(
                "HAnim: id кости {0} повторяется (узлы {1} и {2}) — коллизия и анимация будут крутить разные копии (C18)."
            ).format(n.bone_id, seen[n.bone_id], pos))
        else:
            seen[n.bone_id] = pos

    # C19: the palette pairs skinToBone[i] with matrixArray[i] by position;
    # the exporter keeps node order == matrix order by writing index == i.
    for pos, n in enumerate(nodes):
        if n.index != pos:
            warnings.append(_t(
                "HAnim: узел {0} (id {1}) несёт индекс {2} — порядок узлов не совпадает с порядком матриц скина (C19)."
            ).format(pos, n.bone_id, n.index))
            break

    # C17 (corrected): push/pop is a prefix condition. A pop that underflows
    # on the LAST node is the normal R* layout; an underflow with a node
    # still to follow hands that node an uninitialised parent matrix.
    depth = 0
    last = len(nodes) - 1
    for pos, n in enumerate(nodes):
        kind = n.bone_type & 3
        if kind == 2:
            depth += 1
            if depth > MAX_PUSH_DEPTH:
                fatal.append(_t(
                    "HAnim: глубина push {0} на узле {1} — больше {2}, стек костей затрёт адрес возврата (C17)."
                ).format(depth, pos, MAX_PUSH_DEPTH))
                break
        elif kind == 1:
            depth -= 1
            if depth < 0 and pos != last:
                fatal.append(_t(
                    "HAnim: узел {0} (id {1}) делает pop из пустого стека, а за ним ещё есть узлы — следующая кость получит мусорную родительскую матрицу (C17)."
                ).format(pos, n.bone_id))
                break

    # C20: hard-coded bone ids.
    ids = {n.bone_id for n in nodes}
    missing = sorted(ALWAYS_USED_BONE_IDS - ids)
    if missing:
        fatal.append(_t(
            "HAnim: нет костей с id {0} — движок обращается к ним на каждом педе (хит-сферы, тени, m_apBones) и пишет мимо массива матриц (C20)."
        ).format(', '.join(str(i) for i in missing)))
    cond = sorted(CONDITIONAL_BONE_IDS - ids)
    if cond:
        warnings.append(_t(
            "HAnim: нет костей с id {0} — используются по условию (дождь, открытая машина, байк, пальцы, лицо); без них там будет мусор (C20)."
        ).format(', '.join(str(i) for i in cond)))


def _check_skin(gi, geom, is_last, num_nodes, fatal, warnings):
    """Per-geometry Skin PLG rules (C05..C13, C23, C25, verify-report
    used-list rule)."""
    skin = geom.skin
    nb = skin.num_bones
    nverts = len(geom.vertices)

    if nb < 1:
        fatal.append(_t(
            "геометрия #{0}: skin.num_bones = 0 — таблица костей нулевого размера, порча кучи при спавне (C07)."
        ).format(gi))
    elif nb > MAX_BONES:
        fatal.append(_t(
            "геометрия #{0}: {1} костей — больше {2}, переполнение стека при спавне (C05)."
        ).format(gi, nb, MAX_BONES))
    if num_nodes is not None and nb != num_nodes:
        fatal.append(_t(
            "геометрия #{0}: костей в скине {1}, а узлов в HAnim {2} — палитра и ключи читаются мимо массивов (C06)."
        ).format(gi, nb, num_nodes))
    if len(skin.bone_matrices) != nb:
        fatal.append(_t(
            "геометрия #{0}: матриц скина {1}, а num_bones = {2} — размер чанка не сойдётся с заголовком, модель не загрузится (C23)."
        ).format(gi, len(skin.bone_matrices), nb))
    if len(skin.bone_indices) != nverts or len(skin.bone_weights) != nverts:
        fatal.append(_t(
            "геометрия #{0}: веса заданы для {1}/{2} вершин, а вершин {3} — размер чанка не сойдётся с заголовком (C23)."
        ).format(gi, len(skin.bone_indices), len(skin.bone_weights), nverts))

    # C11 / C13: the format itself is keyed on the maxWeights byte.
    if not (1 <= skin.max_weights <= 4):
        fatal.append(_t(
            "геометрия #{0}: max_weights = {1} — допустимо 1..4 (0 переключает движок на старый формат, >4 ломает шейдер) (C11/C13)."
        ).format(gi, skin.max_weights))
    if skin.num_used < 1 or not skin.bones_used:
        fatal.append(_t(
            "геометрия #{0}: список используемых костей пуст — палитра костей не загрузится, пед деформируется чужими матрицами (C11)."
        ).format(gi))
    if skin.num_used != len(skin.bones_used):
        fatal.append(_t(
            "геометрия #{0}: num_used = {1}, а в списке {2} костей — размер чанка не сойдётся (C23)."
        ).format(gi, skin.num_used, len(skin.bones_used)))

    referenced = set()
    zero_verts = 0
    bad_sum = 0
    negative = 0
    nan = 0
    oob = set()
    for vi, (idx, w) in enumerate(zip(skin.bone_indices, skin.bone_weights)):
        total = 0.0
        for b, ww in zip(idx, w):
            if not math.isfinite(ww):
                nan += 1
                continue
            if ww < 0:
                negative += 1
            if ww != 0:
                referenced.add(b)
                if b >= nb:
                    oob.add(b)
            total += ww
        if total == 0:
            zero_verts += 1
        elif abs(total - 1.0) > WEIGHT_SUM_TOL:
            bad_sum += 1

    if zero_verts and is_last:
        warnings.append(_t(
            "геометрия #{0}: {1} вершин без единого веса — движок делит 1/0 при нормализации, вершины станут NaN (C08)."
        ).format(gi, zero_verts))
    if bad_sum:
        warnings.append(_t(
            "геометрия #{0}: у {1} вершин сумма весов ≠ 1 — движок нормализует только последний атомик (C09)."
        ).format(gi, bad_sum))
    if negative:
        warnings.append(_t(
            "геометрия #{0}: {1} отрицательных весов — сортировка весов в движке сравнивает биты float (C09)."
        ).format(gi, negative))
    if nan:
        warnings.append(_t(
            "геометрия #{0}: {1} весов NaN/inf (C09)."
        ).format(gi, nan))
    if oob:
        warnings.append(_t(
            "геометрия #{0}: индексы костей {1} ≥ num_bones ({2}) — такие вершины прилипнут к кости 0 (C10)."
        ).format(gi, ', '.join(str(b) for b in sorted(oob)), nb))
    used = set(skin.bones_used)
    missing = sorted(referenced - used)
    if missing and skin.bones_used:
        warnings.append(_t(
            "геометрия #{0}: кости {1} имеют веса, но не входят в список используемых — их матрица не загрузится в палитру и останется от предыдущей модели."
        ).format(gi, ', '.join(str(b) for b in missing)))

    # C25: skinToBone matrices are inverted for the bone-offset table.
    for bi, m in enumerate(skin.bone_matrices):
        if not _is_finite_matrix(m):
            warnings.append(_t(
                "геометрия #{0}: матрица кости {1} содержит NaN/inf (C25)."
            ).format(gi, bi))
        elif abs(_det3(m)) < 1e-9:
            warnings.append(_t(
                "геометрия #{0}: матрица кости {1} вырождена (det ≈ 0) — обратная даст мусорные смещения костей (C25)."
            ).format(gi, bi))


def check_skin_clump(clump):
    """Audit a clump that carries at least one skinned geometry.

    Returns ``(fatal, warnings)`` — two lists of ready-to-show strings.
    Both are empty when no geometry has a skin (map models, vehicles):
    nothing here applies to them.
    """
    fatal, warnings = [], []
    geoms = clump.geometries
    skinned = [gi for gi, g in enumerate(geoms) if g.skin is not None]
    if not skinned:
        return fatal, warnings

    frames = _frames_of(clump)

    # W1: frame names live in a 24-byte slot.
    for f in frames:
        # Same gate as DffFrame.extension_bytes: no name chunk is written
        # unless write_name is set, so only those names can overflow.
        if (f.write_name and f.name and f.name != 'unknown'
                and len(f.name.encode('ascii', errors='replace')) > FRAME_NAME_MAX):
            fatal.append(_t(
                "имя фрейма «{0}» длиннее {1} символов — движок хранит имя в 24-байтовом слоте и упадёт при загрузке. Переименуй объект/кость."
            ).format(f.name, FRAME_NAME_MAX))

    # C21: HAnim version on every frame that carries the plugin.
    for f in frames:
        if f.hanim is not None and f.hanim.version != HANIM_VERSION:
            fatal.append(_t(
                "HAnim «{0}»: версия 0x{1:X} вместо 0x100 — RpClumpStreamRead вернёт NULL, модель не загрузится (C21)."
            ).format(f.name or '?', f.hanim.version))

    # C01 / C22 / C26: exactly one node table, somewhere below the root.
    tables = [f for f in frames if f.hanim is not None and f.hanim.bones]
    num_nodes = None
    if not tables:
        fatal.append(_t(
            "нет таблицы узлов HAnim (numNodes > 0) ни на одном фрейме — движок пишет по нулевому указателю при загрузке (C01)."
        ))
    else:
        if len(tables) > 1:
            warnings.append(_t(
                "таблица узлов HAnim есть на {0} фреймах ({1}) — движок использует первую найденную, остальные утекут (C26)."
            ).format(len(tables), ', '.join(f.name or '?' for f in tables)))
        table = tables[0]
        num_nodes = len(table.hanim.bones)
        _check_node_table(frames, table, fatal, warnings)

    # C02: RpClumpAddAtomic inserts at the list head, so the engine's
    # "first" atomic is the LAST one in the file — it must be skinned.
    if not clump.atomics:
        fatal.append(_t(
            "в клампе нет атомиков — CreateHitColModelSkinned обратится к NULL-иерархии (C02)."
        ))
    else:
        last = clump.atomics[-1]
        gi_last = last.geometry_index
        g_last = geoms[gi_last] if 0 <= gi_last < len(geoms) else None
        if g_last is None or g_last.skin is None:
            fatal.append(_t(
                "последний атомик файла (геометрия #{0}) без скина — движок берёт его как первый, иерархия не назначится, краш при загрузке (C02)."
            ).format(gi_last))

    last_gi = clump.atomics[-1].geometry_index if clump.atomics else -1
    for gi in skinned:
        _check_skin(gi, geoms[gi], gi == last_gi, num_nodes, fatal, warnings)

    return fatal, warnings
