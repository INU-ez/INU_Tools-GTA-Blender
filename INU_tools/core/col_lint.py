# INU_tools.core.col_lint
# Pre-write audit of a ColModel against what gta_sa.exe's collision
# loaders (CFileLoader::LoadCollisionModel / Ver2 / Ver3) and the
# CCollision consumers assume without checking. Pure Python, no Blender
# dependency — runs on the core ColModel right before write_col().
#
# Every rule cites the engine finding it mirrors (COL-06..COL-31 in
# E:\RE\addon_check\col_path.md + its verification pass). Severity:
#   fatal   — the engine crashes, or the model's collision is garbage
#             (faces / planes read from the wrong memory);
#   warning — it loads but part of the collision is silently ignored, or
#             the exporter will quantise / alter the data.
# Sizes and offsets are the writer's job (COL-05..COL-08); the rules here
# are about counts, indices, coordinates, bounds and names.
#
# Calibrated against the 216 vanilla .col archives (8 255 models) in
# E:\RE\addon_check\map\col: zero fatals; 34 COL-23 warnings (vanilla
# bounds that miss a primitive by up to 0.26 m — pickups, barriers —
# and veg_largefurs02's box by 17 m) plus one COL-13 warning
# (sbedsfn1_SFN at |v| = 255.02).

import math

from .col import MODEL_NAME_MAX

MAX_FACES = 32767             # COL-11: count is signed int16 everywhere
MAX_VERTICES = 65536          # COL-10: u16 indices
MAX_PRIMITIVES = 32767        # COL-12: COL1 parser compares as int16
MAX_SURFACE_ID = 178          # COL-18: SurfaceInfos table has 179 rows
COORD_LIMIT = 255.99          # COL-13: int16 / 128
PLANE_DIST_LIMIT = 256.0      # COL-14: n·v0 × 128 → int16
BOUNDS_TOLERANCE = 0.02       # COL-17/23: vanilla boxes are built from float
                              # vertices, the file stores int16/128 (≤ 0.0115 off)
COL1_LINES_MAX = 127          # COL-12 (lines are never written)


def _t(s: str) -> str:
    """Lazy translation — falls back to the raw Russian string outside
    Blender (standalone unit tests)."""
    try:
        from .. import T
        return T(s)
    except Exception:
        return s


def _q(v: float) -> float:
    """Engine quantisation of a COL2/3 coordinate (int16 / 128)."""
    return round(v * 128.0) / 128.0


def _face_plane_distance(model, f):
    """|n·v0| with the normal quantised to int16/4096 the way
    CColTrianglePlane::Set does — the verification pass insists on the
    quantised normal, not the float one (COL-14)."""
    va, vb, vc = model.vertices[f.a], model.vertices[f.b], model.vertices[f.c]
    ax, ay, az = _q(va.x), _q(va.y), _q(va.z)
    e1 = (_q(vb.x) - ax, _q(vb.y) - ay, _q(vb.z) - az)
    e2 = (_q(vc.x) - ax, _q(vc.y) - ay, _q(vc.z) - az)
    n = (e1[1] * e2[2] - e1[2] * e2[1],
         e1[2] * e2[0] - e1[0] * e2[2],
         e1[0] * e2[1] - e1[1] * e2[0])
    length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    if length == 0.0:
        return 0.0
    n = tuple(round(c / length * 4096.0) / 4096.0 for c in n)
    return abs(n[0] * ax + n[1] * ay + n[2] * az)


def _check_counts(model, name, fatal, warnings):
    """COL-03 / COL-10 / COL-11 / COL-12."""
    if len(name.encode('ascii', errors='replace')) > MODEL_NAME_MAX:
        fatal.append(_t(
            "COL «{0}»: имя длиннее {1} символов — в 22-байтовом поле не остаётся NUL, движок хэширует мусор и модель не находит свою коллизию (COL-03)."
        ).format(name, MODEL_NAME_MAX))
    if not name:
        warnings.append(_t(
            "COL без имени — запись не сопоставится ни с одной моделью из IDE (COL-25)."
        ))
    nf = len(model.faces)
    if nf > MAX_FACES:
        fatal.append(_t(
            "COL «{0}»: {1} треугольников — движок хранит счётчик как int16, от 32768 все треугольники игнорируются, а с face-группами игра падает (COL-11)."
        ).format(name, nf))
    nv = len(model.vertices)
    if nv > MAX_VERTICES:
        fatal.append(_t(
            "COL «{0}»: {1} вершин — индексы u16, геометрия за 65536-й вершиной недостижима (COL-10)."
        ).format(name, nv))
    for what, n in (('сфер', len(model.spheres)), ('боксов', len(model.boxes))):
        if n > MAX_PRIMITIVES:
            fatal.append(_t(
                "COL «{0}»: {1} {2} — счётчик читается как int16, примитивы пропадут или парсер собьётся (COL-12)."
            ).format(name, n, what))


def _check_faces(model, name, fatal, warnings):
    """COL-09 / COL-13 / COL-14 / COL-18 / COL-22."""
    nv = len(model.vertices)
    bad = 0
    for f in model.faces:
        if f.a >= nv or f.b >= nv or f.c >= nv or f.a < 0 or f.b < 0 or f.c < 0:
            bad += 1
    if bad:
        fatal.append(_t(
            "COL «{0}»: {1} треугольников ссылаются на вершины вне 0..{2} — плоскости читаются из чужой памяти (COL-09)."
        ).format(name, bad, nv - 1))

    # COL-13 holds for every version: COL1 stores floats, but
    # LoadCollisionModel (0x53774A) converts them to int16/128 too.
    worst = 0.0
    for v in model.vertices:
        m = max(abs(v.x), abs(v.y), abs(v.z))
        if m > worst:
            worst = m
    if worst > COORD_LIMIT:
        fatal.append(_t(
            "COL «{0}»: координата вершины {1:.2f} за пределом ±{2} — int16/128 переполняется, грань уедет на 512 м (COL-13). Держи коллизию в 255 м от начала модели."
        ).format(name, worst, COORD_LIMIT))
    elif worst > COORD_LIMIT - 1.0:
        warnings.append(_t(
            "COL «{0}»: координата вершины {1:.2f} — у самой границы ±{2} (COL-13)."
        ).format(name, worst, COORD_LIMIT))

    if not bad and nv:
        far = 0.0
        for f in model.faces:
            d = _face_plane_distance(model, f)
            if d > far:
                far = d
        if far >= PLANE_DIST_LIMIT:
            fatal.append(_t(
                "COL «{0}»: расстояние плоскости грани {1:.1f} ≥ {2} — int16 переполняется, тесты линий/сфер промахнутся (COL-14). Сдвинь коллизию ближе к началу модели."
            ).format(name, far, PLANE_DIST_LIMIT))

    over = set()
    for s in model.spheres:
        if s.surface.material > MAX_SURFACE_ID:
            over.add(s.surface.material)
    for b in model.boxes:
        if b.surface.material > MAX_SURFACE_ID:
            over.add(b.surface.material)
    for f in model.faces:
        if f.surface.material > MAX_SURFACE_ID:
            over.add(f.surface.material)
    if over:
        fatal.append(_t(
            "COL «{0}»: surface id {1} > {2} — таблица поверхностей на 179 строк, трение/звук/частицы прочитаются из чужой памяти (COL-18)."
        ).format(name, ', '.join(str(i) for i in sorted(over)), MAX_SURFACE_ID))

    # COL-22: shadow indices are only bounded by max index + 1.
    nsv = len(model.shadow_vertices)
    if model.shadow_faces:
        if nsv == 0:
            fatal.append(_t(
                "COL «{0}»: {1} shadow-треугольников без shadow-вершин (COL-22)."
            ).format(name, len(model.shadow_faces)))
        else:
            sbad = sum(1 for f in model.shadow_faces
                       if f.a >= nsv or f.b >= nsv or f.c >= nsv)
            if sbad:
                fatal.append(_t(
                    "COL «{0}»: {1} shadow-треугольников ссылаются на вершины вне 0..{2} (COL-22)."
                ).format(name, sbad, nsv - 1))
    elif nsv:
        warnings.append(_t(
            "COL «{0}»: {1} shadow-вершин без shadow-треугольников — тень не запишется (COL-21)."
        ).format(name, nsv))


def _check_face_groups(model, name, fatal, warnings):
    """COL-15 / COL-16 / COL-17."""
    groups = model.face_groups
    if not groups:
        return
    nf = len(model.faces)
    if nf == 0:
        warnings.append(_t(
            "COL «{0}»: face-группы без треугольников — при экспорте не запишутся (COL-15)."
        ).format(name))
        return
    covered = [False] * nf
    for gi, g in enumerate(groups):
        if g.first < 0 or g.last >= nf or g.first > 32767:
            fatal.append(_t(
                "COL «{0}»: face-группа {1} охватывает {2}..{3} при {4} треугольниках — движок читает треугольники и плоскости за массивом (COL-16)."
            ).format(name, gi, g.first, g.last, nf))
            continue
        if g.first > g.last:
            warnings.append(_t(
                "COL «{0}»: face-группа {1}: first {2} > last {3} — группа пропускается (COL-16)."
            ).format(name, gi, g.first, g.last))
            continue
        outside = 0
        for fi in range(g.first, g.last + 1):
            covered[fi] = True
            f = model.faces[fi]
            for vi in (f.a, f.b, f.c):
                if vi >= len(model.vertices):
                    continue
                v = model.vertices[vi]
                if (v.x < g.bb_min.x - BOUNDS_TOLERANCE or v.x > g.bb_max.x + BOUNDS_TOLERANCE
                        or v.y < g.bb_min.y - BOUNDS_TOLERANCE or v.y > g.bb_max.y + BOUNDS_TOLERANCE
                        or v.z < g.bb_min.z - BOUNDS_TOLERANCE or v.z > g.bb_max.z + BOUNDS_TOLERANCE):
                    outside += 1
                    break
        if outside:
            warnings.append(_t(
                "COL «{0}»: face-группа {1}: {2} треугольников торчат из её бокса — с ними не столкнутся машины и педы (COL-17)."
            ).format(name, gi, outside))
    missing = covered.count(False)
    if missing:
        warnings.append(_t(
            "COL «{0}»: {1} треугольников не входят ни в одну face-группу — они не сталкиваются с движущимися объектами (COL-16)."
        ).format(name, missing))


def _check_bounds(model, name, fatal, warnings):
    """COL-19 / COL-23."""
    b = model.bounds
    has_prims = bool(model.spheres or model.boxes or model.faces)
    if not has_prims:
        return
    if not (b.radius > 0) or not math.isfinite(b.radius):
        fatal.append(_t(
            "COL «{0}»: радиус ограничивающей сферы {1} — движок отсекает по ней и модель, и коллизию: объект исчезнет (COL-23)."
        ).format(name, b.radius))
        return
    tol = BOUNDS_TOLERANCE
    out_box = 0
    out_sphere = 0
    r2 = (b.radius + tol) ** 2

    def _pt(x, y, z):
        nonlocal out_box, out_sphere
        if (x < b.bb_min.x - tol or x > b.bb_max.x + tol
                or y < b.bb_min.y - tol or y > b.bb_max.y + tol
                or z < b.bb_min.z - tol or z > b.bb_max.z + tol):
            out_box += 1
        if (x - b.center.x) ** 2 + (y - b.center.y) ** 2 + (z - b.center.z) ** 2 > r2:
            out_sphere += 1

    for v in model.vertices:
        _pt(v.x, v.y, v.z)
    for s in model.spheres:
        for dx, dy, dz in ((s.radius, 0, 0), (-s.radius, 0, 0), (0, s.radius, 0),
                           (0, -s.radius, 0), (0, 0, s.radius), (0, 0, -s.radius)):
            _pt(s.center.x + dx, s.center.y + dy, s.center.z + dz)
    for bx in model.boxes:
        _pt(bx.bb_min.x, bx.bb_min.y, bx.bb_min.z)
        _pt(bx.bb_max.x, bx.bb_max.y, bx.bb_max.z)
    if out_box:
        warnings.append(_t(
            "COL «{0}»: {1} точек коллизии вне ограничивающего бокса — объект попадёт не во все секторы мира, часть коллизии не сработает (COL-23)."
        ).format(name, out_box))
    if out_sphere:
        warnings.append(_t(
            "COL «{0}»: {1} точек коллизии вне ограничивающей сферы — по ней отсекается и видимая модель, и широкая фаза столкновений (COL-23)."
        ).format(name, out_sphere))


def check_col(model):
    """Audit one ColModel. Returns ``(fatal, warnings)`` — two lists of
    ready-to-show strings."""
    fatal, warnings = [], []
    name = model.model_name or ''
    _check_counts(model, name, fatal, warnings)
    _check_faces(model, name, fatal, warnings)
    _check_face_groups(model, name, fatal, warnings)
    _check_bounds(model, name, fatal, warnings)
    return fatal, warnings


def check_col_models(models):
    """Audit a whole archive: every model plus COL-24 (duplicate names —
    the engine leaks a CColModel per duplicate and unloads the wrong one).
    Returns ``(fatal, warnings)``."""
    fatal, warnings = [], []
    seen = {}
    for i, m in enumerate(models):
        f, w = check_col(m)
        fatal += f
        warnings += w
        key = (m.model_name or '').lower()
        if key in seen:
            warnings.append(_t(
                "COL «{0}»: имя повторяется (записи {1} и {2}) — движок выделит вторую CColModel и потеряет одну из коллизий при выгрузке (COL-24)."
            ).format(m.model_name, seen[key], i))
        else:
            seen[key] = i
    return fatal, warnings
