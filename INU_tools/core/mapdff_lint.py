# INU_tools.core.mapdff_lint
# Pre-write audit of a non-skinned (map / object) DffClump against what
# gta_sa.exe dereferences when it streams an objs/tobj/anim model. Pure
# Python, no Blender dependency — runs on the core DffClump structures
# right before DffClump.to_bytes(), the same way core.skin_lint does for
# peds.
#
# Every rule cites the engine finding it mirrors (DFF-03..DFF-74 in
# E:\RE\addon_check\mapdff_path.md + its verification pass, W-items in
# E:\RE\addon_check\map\core_roundtrip_map.md). Severity:
#   fatal   — the model never loads (LOAD-FAIL: the streamer retries it
#             forever and it stays invisible) or the engine crashes;
#   warning — it loads but renders / behaves wrong, or the writer will
#             silently alter the data (drop / pad / truncate).
# Only what is decidable from the core structures is checked — chunk
# sizes and the RW version are the writer's job.
#
# Calibrated against the 70 vanilla map DFFs in E:\RE\addon_check\map\dff:
# zero fatals; the only warnings are the two `_dam` atomics (DFF-28,
# need the IDE flag), ammotrn_obj's black Modulate material (DFF-46) and
# visagesign04's dangling UV-anim reference (DFF-51).

import math

from .dff import (
    FRAME_NAME_MAX, TEXTURE_NAME_MAX, EFFECT_NAME_MAX,
    GEOM_MOD_COLOR, Light2dfx, Particle2dfx, PedAttractor2dfx, SunGlare2dfx,
    EnterExit2dfx, RoadSign2dfx, RawUnknown2dfx,
    _allowed_2dfx_ids,
)
from .skin_lint import _frames_of

MAX_VERTICES = 65535          # DFF-09: RpGeometryCreate fails at >= 0x10000
MAX_TEXCOORD_SETS = 8         # DFF-11: RpGeometry has 8 slots
USED_TEXCOORD_SETS = 2        # DFF-11: the SA pipelines read at most 2
MAX_2DFX_PER_MODEL = 255      # DFF-33: model-info count is a byte
MAX_CORONA_SHOW_MODE = 13     # DFF-35: switch default = never enabled
MAX_UV_ANIMS_PER_MATERIAL = 8 # DFF-54: slot mask bits 0..7
UV_ANIM_NAME_MAX = 31         # DFF-54: 32-byte fixed name
MODEL_NAME_MAX = 23           # DFF-70: IDE / IMG names, 24-byte buffers
BSPHERE_TOLERANCE = 1e-3      # DFF-25: allow float noise on the boundary
FX_POSITION_SLACK = 5.0       # DFF-39: metres past the sphere before "not on the model"
PIPELINE_IDS = frozenset({0x53F2009C, 0x53F20098, 0x53F2009A})  # DFF-08
LIGHT_AT_DAY = 0x20
LIGHT_AT_NIGHT = 0x40
_DAM_SUFFIX = '_dam'
_IDENTITY_ROT = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _t(s: str) -> str:
    """Lazy translation — falls back to the raw Russian string outside
    Blender (standalone unit tests)."""
    try:
        from .. import T
        return T(s)
    except Exception:
        return s


def _ascii_len(s: str) -> int:
    return len((s or '').encode('ascii', errors='replace'))


def _is_identity(frame) -> bool:
    for a, b in zip(frame.rotation, _IDENTITY_ROT):
        if abs(a - b) > 1e-5:
            return False
    return all(abs(v) <= 1e-5 for v in frame.position)


def _is_identity_rot(frame) -> bool:
    """True, если 3×3 фрейма — единичная (без поворота/масштаба).

    Позицию (смещение) НЕ проверяем намеренно: INU штатно кладёт мировое
    смещение objs-модели во фрейм ради round-trip одиночного DFF, а игра
    берёт позицию из IPL — это безвредно. Подозрителен (для DFF-29) только
    запечённый ПОВОРОТ/масштаб, который движок так же отбрасывает."""
    return all(abs(a - b) <= 1e-5 for a, b in zip(frame.rotation, _IDENTITY_ROT))


def _check_frames(frames, fatal, warnings):
    """DFF-03 / DFF-06 / DFF-30."""
    if not frames:
        fatal.append(_t(
            "в клампе нет фреймов — RpClumpStreamRead возьмёт кадр из пустого массива, краш при загрузке (DFF-03)."
        ))
        return
    for i, f in enumerate(frames):
        # DFF-06: parent slots are filled in file order, so a forward or
        # self reference dereferences uninitialised memory.
        if f.parent >= i:
            fatal.append(_t(
                "фрейм {0} «{1}»: родитель {2} идёт не раньше него — RwFrameAddChild получит мусорный указатель, краш при загрузке (DFF-06)."
            ).format(i, f.name or '?', f.parent))
        # DFF-30: NodeName lives in a 24-byte slot.
        if (f.write_name and f.name and f.name != 'unknown'
                and _ascii_len(f.name) > FRAME_NAME_MAX):
            fatal.append(_t(
                "имя фрейма «{0}» длиннее {1} символов — движок хранит имя в 24-байтовом слоте и упадёт при загрузке. Переименуй объект/кость."
            ).format(f.name, FRAME_NAME_MAX))


def _check_atomics(clump, frames, fatal, warnings, objs_rules=True):
    """DFF-03 / DFF-05 / DFF-07 / DFF-27 / DFF-28 / DFF-29 / DFF-41.

    ``objs_rules=False`` (vehicle / weapon clump) skips DFF-27/28/29 —
    CVehicleModelInfo / CWeaponModelInfo keep every atomic, own the
    ``_dam`` slot and honour the frame transforms."""
    atomics = clump.atomics
    ngeom = len(clump.geometries)
    if not atomics:
        fatal.append(_t(
            "в клампе нет атомиков — модель objs никогда не загрузится, а anim-модель уронит игру при первом размещении (DFF-03/DFF-40)."
        ))
        return
    plain = []
    for ai, a in enumerate(atomics):
        if not (0 <= a.frame_index < len(frames)):
            fatal.append(_t(
                "атомик {0}: индекс фрейма {1} вне 0..{2} — движок читает указатель за массивом фреймов, краш при загрузке (DFF-05)."
            ).format(ai, a.frame_index, len(frames) - 1))
            continue
        if not (0 <= a.geometry_index < ngeom):
            fatal.append(_t(
                "атомик {0}: индекс геометрии {1} вне 0..{2} — RpGeometryAddRef по мусорному указателю, краш при загрузке (DFF-07)."
            ).format(ai, a.geometry_index, ngeom - 1))
            continue
        if not (a.flags & 0x4):
            warnings.append(_t(
                "атомик {0}: нет флага rpATOMICRENDER (4) — в anim-модели такой атомик не рисуется (DFF-41)."
            ).format(ai))
        name = frames[a.frame_index].name or ''
        if name.endswith(_DAM_SUFFIX) and objs_rules:
            # DFF-28: only a damage model info (IDE flag 0x1000) has the
            # damaged-atomic slot; on a plain one SetDamagedAtomic writes
            # through NULL. Decidable only with the IDE line → warn.
            warnings.append(_t(
                "атомик «{0}» с суффиксом _dam — у модели в IDE обязан стоять флаг 0x1000 (damageable), иначе SetDamagedAtomic пишет по NULL и игра падает (DFF-28)."
            ).format(name))
        else:
            plain.append(name or f'#{ai}')
    # DFF-27: an animated clump (HAnim on a frame) keeps every atomic —
    # the "first wins" rule is for objs/tobj.
    animated = any(f.hanim is not None for f in frames)
    if len(plain) > 1 and not animated and objs_rules:
        warnings.append(_t(
            "{0} обычных атомиков ({1}) — для objs/tobj движок берёт только первый в файле, остальные не рисуются и их 2DFX теряются; это нормально лишь для anim-моделей (DFF-27)."
        ).format(len(plain), ', '.join(plain[:6])))
    if len(atomics) == 1 and objs_rules:
        # DFF-29: objs atomics get a fresh identity frame at load, so a
        # transform baked into the DFF frame is silently discarded. Мы ругаемся
        # ТОЛЬКО на запечённый поворот/масштаб — чистое смещение INU кладёт во
        # фрейм штатно (round-trip), а позицию в игре несёт IPL → безвредно.
        f = frames[atomics[0].frame_index] if 0 <= atomics[0].frame_index < len(frames) else None
        if f is not None and not _is_identity_rot(f):
            warnings.append(_t(
                "фрейм атомика «{0}» несёт запечённый поворот/масштаб — для objs-модели движок его отбрасывает (ориентация берётся из IPL) (DFF-29)."
            ).format(f.name or '?'))


def _check_materials(gi, geom, uv_dict_names, fatal, warnings, objs_rules=True):
    """DFF-14 / DFF-18 / DFF-19 / DFF-46 / DFF-51 / DFF-54 / W8.

    ``objs_rules=False`` skips DFF-46 — vehicles go through the car
    pipeline, where a black material is a legitimate body colour."""
    mats = geom.materials
    if not mats and geom.triangles:
        fatal.append(_t(
            "геометрия #{0}: нет материалов при {1} треугольниках — _rpMaterialListGetMaterial разыменует NULL, краш при загрузке (DFF-14)."
        ).format(gi, len(geom.triangles)))
    flags = geom._build_flags()
    for mi, m in enumerate(mats):
        tex = m.texture
        if tex is not None:
            n = _ascii_len(tex.name)
            if n > TEXTURE_NAME_MAX:
                fatal.append(_t(
                    "геометрия #{0}, материал {1}: имя текстуры «{2}» длиннее {3} символов — TXD хранит 31, текстура никогда не найдётся (DFF-19/W8)."
                ).format(gi, mi, tex.name, TEXTURE_NAME_MAX))
            elif n == 0:
                warnings.append(_t(
                    "геометрия #{0}, материал {1}: текстура с пустым именем — RwTextureRead вернёт NULL, материал отрисуется без текстуры (DFF-19)."
                ).format(gi, mi))
            if tex.name and any(ord(c) > 127 for c in tex.name):
                warnings.append(_t(
                    "геометрия #{0}, материал {1}: имя текстуры «{2}» не ASCII — запишется с «?» и не совпадёт с TXD (DFF-19)."
                ).format(gi, mi, tex.name))
            if _ascii_len(tex.mask) > TEXTURE_NAME_MAX:
                warnings.append(_t(
                    "геометрия #{0}, материал {1}: имя маски «{2}» длиннее {3} символов — будет обрезано движком (DFF-19)."
                ).format(gi, mi, tex.mask, TEXTURE_NAME_MAX))
        # DFF-46: MODULATEMATERIALCOLOR × black = black model.
        if (objs_rules and (flags & GEOM_MOD_COLOR)
                and m.color.r == 0 and m.color.g == 0 and m.color.b == 0):
            warnings.append(_t(
                "геометрия #{0}, материал {1}: чёрный цвет материала при флаге Modulate — prelight × 0, модель будет чёрной (DFF-46)."
            ).format(gi, mi))
        names = list(getattr(m, 'uv_anim_names', None) or [])
        if names:
            if len(names) > MAX_UV_ANIMS_PER_MATERIAL:
                fatal.append(_t(
                    "геометрия #{0}, материал {1}: {2} UV-анимаций — движок читает не больше {3}, лишние имена рассинхронизируют поток, модель не загрузится (DFF-54)."
                ).format(gi, mi, len(names), MAX_UV_ANIMS_PER_MATERIAL))
            for nm in names:
                if _ascii_len(nm) > UV_ANIM_NAME_MAX:
                    fatal.append(_t(
                        "геометрия #{0}, материал {1}: имя UV-анимации «{2}» длиннее {3} символов — 32-байтовое поле без NUL (DFF-54)."
                    ).format(gi, mi, nm, UV_ANIM_NAME_MAX))
                elif uv_dict_names is not None and nm not in uv_dict_names:
                    warnings.append(_t(
                        "геометрия #{0}, материал {1}: UV-анимация «{2}» отсутствует в словаре — движок подставит статичную (DFF-51)."
                    ).format(gi, mi, nm))


def _check_geometry(gi, geom, is_mobile, fatal, warnings):
    """DFF-09 / DFF-11 / DFF-12 / DFF-13 / DFF-20..23 / DFF-25 / DFF-26 /
    DFF-43 / DFF-45."""
    nv = len(geom.vertices)
    nt = len(geom.triangles)
    nm = len(geom.materials)

    if nv > MAX_VERTICES:
        fatal.append(_t(
            "геометрия #{0}: {1} вершин — RpGeometryCreate отказывает от 65536, модель не загрузится (DFF-09). Разбей меш."
        ).format(gi, nv))
    if nv == 0 or nt == 0:
        warnings.append(_t(
            "геометрия #{0}: {1} вершин / {2} треугольников — пустая геометрия ничего не рисует, поведение DN-пайплайна на ней не проверено (DFF-26)."
        ).format(gi, nv, nt))

    n_uv = len(geom.uv_layers)
    if n_uv > MAX_TEXCOORD_SETS:
        fatal.append(_t(
            "геометрия #{0}: {1} UV-слоёв — больше 8 затирают указатели RpGeometry, краш при загрузке (DFF-11)."
        ).format(gi, n_uv))
    elif n_uv > USED_TEXCOORD_SETS:
        warnings.append(_t(
            "геометрия #{0}: {1} UV-слоёв — пайплайны SA используют не больше 2, остальные балласт (DFF-11)."
        ).format(gi, n_uv))

    # DFF-12: the writer sets NATIVE (0x01000000) for a mobile / console
    # geometry; the PC engine then reads the vertices into NULL.
    if (geom.is_native_ogl or geom.raw_native_data_plg) and not is_mobile:
        fatal.append(_t(
            "геометрия #{0}: флаг NATIVE (0x01000000) на PC-геометрии — вершины читаются в NULL, краш при загрузке (DFF-12)."
        ).format(gi))

    # DFF-13: the struct is sized by numVertices — every per-vertex array
    # must be exactly that long or the reader desyncs.
    if geom.prelit_colors and len(geom.prelit_colors) != nv:
        fatal.append(_t(
            "геометрия #{0}: prelight-цветов {1}, а вершин {2} — поток рассинхронизируется, модель не загрузится (DFF-13)."
        ).format(gi, len(geom.prelit_colors), nv))
    if geom.export_normals and geom.normals and len(geom.normals) != nv:
        fatal.append(_t(
            "геометрия #{0}: нормалей {1}, а вершин {2} — поток рассинхронизируется, модель не загрузится (DFF-13)."
        ).format(gi, len(geom.normals), nv))
    for li, layer in enumerate(geom.uv_layers):
        if len(layer) != nv:
            fatal.append(_t(
                "геометрия #{0}: UV-слой {1} содержит {2} координат при {3} вершинах — поток рассинхронизируется, модель не загрузится (DFF-13)."
            ).format(gi, li, len(layer), nv))
            break

    # DFF-20..23: indices are never range-checked by the engine.
    bad_idx = 0
    bad_mat = 0
    for tri in geom.triangles:
        if tri.a >= nv or tri.b >= nv or tri.c >= nv or tri.a < 0 or tri.b < 0 or tri.c < 0:
            bad_idx += 1
        if tri.material >= nm or tri.material < 0:
            bad_mat += 1
    if bad_idx:
        fatal.append(_t(
            "геометрия #{0}: {1} треугольников ссылаются на вершины вне 0..{2} — индексы выходят за вершинный буфер (DFF-23)."
        ).format(gi, bad_idx, nv - 1))
    if bad_mat:
        fatal.append(_t(
            "геометрия #{0}: {1} треугольников ссылаются на материал вне 0..{2} — мусорный указатель материала, краш при загрузке/отрисовке (DFF-20/DFF-21)."
        ).format(gi, bad_mat, nm - 1))

    # DFF-25: the sphere gates D3D clipping — must enclose every vertex.
    bs = geom.bounding_sphere
    if nv:
        if bs.radius <= 0:
            warnings.append(_t(
                "геометрия #{0}: радиус ограничивающей сферы {1} — движок считает её «всегда в кадре» и отключает клиппинг, треугольники у камеры порвёт (DFF-25)."
            ).format(gi, bs.radius))
        else:
            r2 = (bs.radius + BSPHERE_TOLERANCE) ** 2
            worst = 0.0
            for v in geom.vertices:
                d = (v[0] - bs.x) ** 2 + (v[1] - bs.y) ** 2 + (v[2] - bs.z) ** 2
                if d > r2 and d > worst:
                    worst = d
            if worst:
                warnings.append(_t(
                    "геометрия #{0}: ограничивающая сфера (r={1:.3f}) не накрывает вершины (самая дальняя на {2:.3f}) — клиппинг у камеры отключится раньше времени (DFF-25)."
                ).format(gi, bs.radius, math.sqrt(worst)))

    # DFF-43 / DFF-45: night colours need PRELIT and exactly numVertices.
    ec = geom.extra_colors
    if ec is not None and ec.colors:
        if not geom.prelit_colors:
            warnings.append(_t(
                "геометрия #{0}: ночные цвета без дневных (prelight) — дневной буфер остаётся неинициализированным, днём модель будет случайного цвета (DFF-43)."
            ).format(gi))
        if len(ec.colors) != nv:
            warnings.append(_t(
                "геометрия #{0}: ночных цветов {1}, а вершин {2} — при экспорте список выровняют по числу вершин (DFF-45/W14)."
            ).format(gi, len(ec.colors), nv))

    # DFF-08: pipeline id the engine knows, or nothing.
    if geom.pipeline and geom.pipeline not in PIPELINE_IDS:
        warnings.append(_t(
            "геометрия #{0}: pipeline 0x{1:X} неизвестен движку — атомик останется на стандартном RW-пайплайне без шейдера зданий (DFF-08)."
        ).format(gi, geom.pipeline))


def _check_2dfx(gi, geom, rw_version, fatal, warnings) -> int:
    """DFF-31..DFF-39 / W12 / W13. Returns the number of entries kept."""
    ext = geom.ext_2dfx
    if ext is None or not ext.entries:
        return 0
    allowed = _allowed_2dfx_ids(rw_version)
    bs = geom.bounding_sphere
    kept = 0
    for ei, e in enumerate(ext.entries):
        if e.effect_id not in allowed:
            warnings.append(_t(
                "геометрия #{0}, 2DFX #{1}: тип {2} неизвестен целевой игре — движок не умеет его пропустить, при экспорте запись убирается (DFF-32/W12)."
            ).format(gi, ei, e.effect_id))
            continue
        kept += 1
        if isinstance(e, SunGlare2dfx):
            pass
        elif isinstance(e, Light2dfx):
            if e.shadow_size and not e.shadow_tex_name:
                fatal.append(_t(
                    "геометрия #{0}, 2DFX #{1}: у света есть тень (shadow_size={2}), но нет текстуры тени — RenderStaticShadows разыменует NULL, краш при отрисовке (DFF-34)."
                ).format(gi, ei, e.shadow_size))
            if e.corona_size and not e.corona_tex_name:
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: у света нет текстуры короны — корона не отрисуется (DFF-34)."
                ).format(gi, ei))
            for what, nm in (('corona', e.corona_tex_name), ('shadow', e.shadow_tex_name)):
                if _ascii_len(nm) > EFFECT_NAME_MAX:
                    warnings.append(_t(
                        "геометрия #{0}, 2DFX #{1}: имя {2} «{3}» длиннее {4} символов — при экспорте обрежется (DFF-34/W13)."
                    ).format(gi, ei, what, nm, EFFECT_NAME_MAX))
            if not (e.flags1 & (LIGHT_AT_DAY | LIGHT_AT_NIGHT)):
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: у света не стоит ни «днём», ни «ночью» — он никогда не включится (DFF-35)."
                ).format(gi, ei))
            if e.corona_show_mode > MAX_CORONA_SHOW_MODE:
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: режим короны {2} > {3} — свет никогда не включится (DFF-35)."
                ).format(gi, ei, e.corona_show_mode, MAX_CORONA_SHOW_MODE))
            if min(e.corona_far_clip, e.pointlight_range, e.corona_size, e.shadow_size) < 0:
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: отрицательный размер/дальность света — движок не проверяет, будет мусор (DFF-35)."
                ).format(gi, ei))
        elif isinstance(e, Particle2dfx):
            if not e.effect_name:
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: у частиц пустое имя системы — эффект не создастся (DFF-36)."
                ).format(gi, ei))
            elif _ascii_len(e.effect_name) > EFFECT_NAME_MAX:
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: имя {2} «{3}» длиннее {4} символов — при экспорте обрежется (DFF-34/W13)."
                ).format(gi, ei, 'particle', e.effect_name, EFFECT_NAME_MAX))
        elif isinstance(e, PedAttractor2dfx):
            if _ascii_len(e.external_script) > 8:
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: имя скрипта аттрактора «{2}» длиннее 8 символов — обрежется (DFF-38)."
                ).format(gi, ei, e.external_script))
        elif isinstance(e, EnterExit2dfx):
            if _ascii_len(e.interior_name) > 8:
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: имя интерьера «{2}» длиннее 8 символов — обрежется (DFF-38)."
                ).format(gi, ei, e.interior_name))
        elif isinstance(e, RoadSign2dfx):
            if len(e.text_lines) > 4 or any(_ascii_len(l) > 16 for l in e.text_lines):
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: у знака больше 4 строк или строка длиннее 16 символов — обрежется (DFF-38)."
                ).format(gi, ei))
        elif isinstance(e, RawUnknown2dfx):
            expected = {8: 4, 9: 12}.get(e.effect_id)
            if expected is not None and len(e.raw) != expected:
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: запись типа {2} занимает {3} байт вместо {4} — движок её пропустит (DFF-32)."
                ).format(gi, ei, e.effect_id, len(e.raw), expected))
        # DFF-39: position outside the model — nothing checks it, it is
        # just culled with the entity. Only for effects that sit on the
        # mesh; vanilla road signs / trigger points legitimately sit far,
        # and lights hang off tiny models (trimainlite: 1.5 m from r=0.2),
        # so the slack is absolute, not a multiple of the radius.
        if bs.radius > 0 and isinstance(e, (Light2dfx, Particle2dfx, PedAttractor2dfx)):
            d = math.sqrt((e.loc[0] - bs.x) ** 2 + (e.loc[1] - bs.y) ** 2 + (e.loc[2] - bs.z) ** 2)
            if d > bs.radius + FX_POSITION_SLACK:
                warnings.append(_t(
                    "геометрия #{0}, 2DFX #{1}: эффект в {2:.1f} м от центра модели (сфера r={3:.1f}) — вероятно, не то положение; отсечётся вместе с моделью (DFF-39)."
                ).format(gi, ei, d, bs.radius))
    return kept


def _check_breakable(gi, geom, fatal, warnings):
    """DFF-60 / W1: the break copy is parsed with no validation."""
    b = geom.breakable
    if b is None:
        return
    nv, nm = len(b.vertices), len(b.tex_names)
    if len(b.uvs) != nv or len(b.colors) != nv:
        fatal.append(_t(
            "геометрия #{0}: breakable — UV ({1}) / цветов ({2}) не по числу вершин ({3}), движок прочитает мусор (DFF-60)."
        ).format(gi, len(b.uvs), len(b.colors), nv))
    if len(b.tri_materials) != len(b.triangles):
        fatal.append(_t(
            "геометрия #{0}: breakable — материалов треугольников {1} при {2} треугольниках (DFF-60)."
        ).format(gi, len(b.tri_materials), len(b.triangles)))
    if any(i >= nv or i < 0 for t in b.triangles for i in t):
        fatal.append(_t(
            "геометрия #{0}: breakable — треугольник ссылается на вершину вне 0..{1}, краш при разрушении (DFF-60)."
        ).format(gi, nv - 1))
    if any(m >= nm or m < 0 for m in b.tri_materials):
        fatal.append(_t(
            "геометрия #{0}: breakable — треугольник ссылается на материал вне 0..{1}, краш при разрушении (DFF-60)."
        ).format(gi, nm - 1))
    if len(b.mask_names) != nm or len(b.ambient) != nm:
        warnings.append(_t(
            "геометрия #{0}: breakable — масок/цветов не по числу материалов ({1}), недостающие будут дописаны пустыми (DFF-60)."
        ).format(gi, nm))
    for nm_ in b.tex_names:
        if _ascii_len(nm_) > TEXTURE_NAME_MAX:
            fatal.append(_t(
                "геометрия #{0}: breakable — имя текстуры «{1}» длиннее {2} символов, не совпадёт с TXD (DFF-60/W8)."
            ).format(gi, nm_, TEXTURE_NAME_MAX))


def check_map_clump(clump, model_name: str = '', is_vehicle: bool = False):
    """Audit a non-skinned clump (map object, LOD, animated object).

    Returns ``(fatal, warnings)`` — two lists of ready-to-show strings.
    Skinned clumps belong to ``core.skin_lint``; nothing here applies to
    them, so both lists come back empty. ``model_name`` (the file stem)
    is optional and only feeds the IDE/IMG name-length rule (DFF-70).
    ``is_vehicle`` (vehicle / weapon clump) turns off the objs/tobj-only
    rules DFF-27 / DFF-28 / DFF-29 / DFF-46 — vanilla infernus.dff would
    otherwise collect 9 false warnings, landstal.dff 26.
    """
    fatal, warnings = [], []
    geoms = clump.geometries
    if any(g.skin is not None for g in geoms):
        return fatal, warnings

    if model_name and _ascii_len(model_name) > MODEL_NAME_MAX:
        fatal.append(_t(
            "имя модели «{0}» длиннее {1} символов — IDE/IMG держат 23 + NUL, LoadObject переполнит стек (DFF-70)."
        ).format(model_name, MODEL_NAME_MAX))

    frames = _frames_of(clump)
    _check_frames(frames, fatal, warnings)
    _check_atomics(clump, frames, fatal, warnings, objs_rules=not is_vehicle)

    uv_dict_names = None
    if clump.uv_anim_dict is not None and clump.uv_anim_dict.anims:
        uv_dict_names = {a.name for a in clump.uv_anim_dict.anims}
    # Materials referencing anims with no dictionary at all fall back to
    # identity too (DFF-51) — treat "no dict" as "no names".
    if uv_dict_names is None and any(getattr(m, 'uv_anim_names', None)
                                     for g in geoms for m in g.materials):
        uv_dict_names = set()

    total_fx = 0
    for gi, g in enumerate(geoms):
        _check_geometry(gi, g, clump.is_mobile, fatal, warnings)
        _check_materials(gi, g, uv_dict_names, fatal, warnings,
                         objs_rules=not is_vehicle)
        total_fx += _check_2dfx(gi, g, clump.version, fatal, warnings)
        _check_breakable(gi, g, fatal, warnings)

    if total_fx > MAX_2DFX_PER_MODEL:
        warnings.append(_t(
            "{0} 2DFX-эффектов на модель — счётчик в model-info байтовый, лишние потеряются или прочитаются не из того слота (DFF-33)."
        ).format(total_fx))

    return fatal, warnings
