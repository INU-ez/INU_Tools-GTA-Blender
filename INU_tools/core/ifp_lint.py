# INU_tools.core.ifp_lint
# Pre-write audit of IFP animation data against what gta_sa.exe's
# CAnimManager::LoadAnimFile and the CAnimBlend* playback code actually
# check (they check nothing). Pure Python, no Blender dependency — runs
# on the core IFPFile / Animation structures right before write_ifp().
#
# Every rule cites the engine finding it mirrors (IFP-01..IFP-22 in
# E:\RE\addon_check\ifp_path.md). Severity:
#   fatal   — the engine crashes / hangs, or the animation can never play;
#   warning — it plays with garbage (wrong blend, loop-seam hold, ...).
#
# Times: the core keeps ``KeyFrame.time`` in seconds; the ANP3 tick is
# 1/60 s (ANP3 tick = round(time * 60), see core.ifp). The engine stores
# the tick as int16, and for ANPK quantises ``time * 60 + 0.5`` on load,
# so both formats share the same 546.1 s absolute-time ceiling.
#
# Calibrated against vanilla ped.ifp + 7 anim.img IFPs: zero fatals.
# Vanilla does start some sequences past tick 0, animates translation on
# non-root bones and ships two non-unit quaternions — all warnings.

import math

from .ifp import HAS_ROT, HAS_TRANS, HAS_SCALE, IFPFile

MAX_ANIMATIONS_TOTAL = 2500   # ms_aAnimations[2500]
MAX_BLOCK_NAME = 15           # strncpy(name, 16), compared with _stricmp
MAX_NAME = 23                 # 24-byte fields, hashed up to the NUL
MAX_COUNT = 32767             # numFrames / numSequences stored as int16
MAX_TICK = 32767              # compressed time: int16 ticks
ANPK_TICKS_PER_SEC = 60.0     # engine: int16(time * 60 + 0.5)
ANP3_TICKS_PER_SEC = 60.0     # engine: FixedFloat<int16, 60.f>, see core.ifp
MAX_TRANSLATION = 32.0        # int16 / 1024
MAX_QUAT_COMPONENT = 8.0      # int16 / 4096
UNIT_QUAT_TOL = 5e-3

_ROOT_NAMES = ('root', 'normal')


def _t(s: str) -> str:
    """Lazy translation — falls back to the raw Russian string outside
    Blender (standalone unit tests)."""
    try:
        from .. import T
        return T(s)
    except Exception:
        return s


def _is_root(bone) -> bool:
    if bone.bone_id == 0:
        return True
    return bone.bone_id == -1 and bone.name.strip().lower() in _ROOT_NAMES


def _bone_key(bone):
    """Identity the engine binds a sequence by: the bone id, or the
    (case-insensitive) name when the id is -1."""
    if bone.bone_id != -1:
        return ('id', bone.bone_id)
    return ('name', bone.name.strip().lower())


def _check_times(anim, bone, compressed, fmt, fatal, warnings):
    """IFP-06/07/08/09 on one sequence."""
    kfs = bone.keyframes
    if fmt == 'ANP3':
        ticks = [int(round(k.time * ANP3_TICKS_PER_SEC)) for k in kfs]
    else:
        ticks = [k.time for k in kfs]

    if ticks[0] != 0:
        warnings.append(_t(
            "{0} / {1}: первый ключ на {2:.3f} с, а не на 0 — движок никогда не конвертирует нулевой кадр и добавляет его время на каждом витке цикла (IFP-06)."
        ).format(anim.name, bone.name, kfs[0].time))

    equal = 0
    for i in range(1, len(ticks)):
        if ticks[i] < ticks[i - 1]:
            fatal.append(_t(
                "{0} / {1}: время ключей убывает ({2:.3f} с после {3:.3f} с) — отрицательная дельта, зацикленная анимация повесит игру (IFP-07)."
            ).format(anim.name, bone.name, kfs[i].time, kfs[i - 1].time))
            return
        elif ticks[i] == ticks[i - 1]:
            equal += 1
    if len(ticks) >= 2 and ticks[-1] == ticks[0]:
        fatal.append(_t(
            "{0} / {1}: все {2} ключей на одном времени — нулевая длительность, зацикленная анимация повесит игру (IFP-07)."
        ).format(anim.name, bone.name, len(ticks)))
        return
    if equal:
        warnings.append(_t(
            "{0} / {1}: {2} пар ключей на одном тике — схлопнутся в скачок (IFP-08)."
        ).format(anim.name, bone.name, equal))

    if compressed:
        # IFP-09: the absolute time must fit an int16 tick.
        if fmt == 'ANP3':
            last_tick = ticks[-1]
            limit_s = MAX_TICK / ANP3_TICKS_PER_SEC
        else:
            last_tick = int(kfs[-1].time * ANPK_TICKS_PER_SEC + 0.5)
            limit_s = MAX_TICK / ANPK_TICKS_PER_SEC
        if last_tick > MAX_TICK:
            fatal.append(_t(
                "{0} / {1}: последний ключ на {2:.1f} с — больше {3:.1f} с, тик int16 переполнится и время станет отрицательным (IFP-09)."
            ).format(anim.name, bone.name, kfs[-1].time, limit_s))


def _check_values(anim, bone, compressed, fatal, warnings):
    """IFP-09 (translation/quaternion range), IFP-16 (unit quaternions)."""
    non_unit = 0
    bad_trans = 0
    bad_quat = 0
    for k in bone.keyframes:
        q = k.rotation
        if any(not math.isfinite(c) for c in q):
            fatal.append(_t(
                "{0} / {1}: кватернион с NaN/inf — матрица кости станет NaN, меш исчезнет (IFP-16)."
            ).format(anim.name, bone.name))
            return
        mag = math.sqrt(sum(c * c for c in q))
        if abs(mag - 1.0) > UNIT_QUAT_TOL:
            non_unit += 1
        if compressed and any(abs(c) >= MAX_QUAT_COMPONENT for c in q):
            bad_quat += 1
        if bone.key_type & HAS_TRANS:
            t = k.translation
            if any(not math.isfinite(c) for c in t):
                fatal.append(_t(
                    "{0} / {1}: смещение с NaN/inf (IFP-16)."
                ).format(anim.name, bone.name))
                return
            if compressed and any(abs(c) >= MAX_TRANSLATION for c in t):
                bad_trans += 1
    if bad_quat:
        fatal.append(_t(
            "{0} / {1}: {2} ключей с компонентом кватерниона ≥ 8 — int16/4096 переполнится (IFP-09)."
        ).format(anim.name, bone.name, bad_quat))
    if bad_trans:
        fatal.append(_t(
            "{0} / {1}: {2} ключей со смещением ≥ 32 единиц — int16/1024 переполнится, кость прыгнет (IFP-09)."
        ).format(anim.name, bone.name, bad_trans))
    if non_unit:
        warnings.append(_t(
            "{0} / {1}: {2} ненормированных кватернионов (|q| ≠ 1 ± 0.005) — slerp смешает с неверными весами (IFP-16)."
        ).format(anim.name, bone.name, non_unit))


def check_ifp(anims, block_name: str = '', target: str = 'SA',
              fmt: str = '', file_stem: str = '', total_anims=None):
    """Audit animations before they are written.

    ``anims`` — an ``IFPFile`` or a list of ``Animation``.
    ``block_name`` — internal package name (defaults to ``anims.name``).
    ``target`` — 'III' / 'VC' / 'SA'. SA compresses EVERY animation on
    load, so the int16 range rules apply there regardless of ``fmt``.
    ``fmt`` — 'ANP3' or 'ANPK' (what the writer will emit); '' means
    ANP3 for SA and ANPK otherwise.
    ``file_stem`` — output file name without extension; when given, the
    block name must match it (IFP-20).
    ``total_anims`` — animations already loaded by the game (ped.ifp +
    other blocks); when given, the 2500-slot ceiling is checked.

    Returns ``(fatal, warnings)`` — two lists of ready-to-show strings.
    """
    fatal, warnings = [], []
    if isinstance(anims, IFPFile):
        block_name = block_name or anims.name
        anims = anims.animations
    anims = list(anims)
    fmt = (fmt or ('ANP3' if target == 'SA' else 'ANPK')).upper()
    if fmt == 'ANP2':
        fmt = 'ANPK'
    compressed = fmt == 'ANP3' or target == 'SA'

    # IFP-11 / IFP-20: block name.
    if len(block_name) > MAX_BLOCK_NAME:
        fatal.append(_t(
            "имя пакета «{0}» длиннее {1} символов — strncpy(16) обрежет его, блок не совпадёт с записью в IMG (IFP-11)."
        ).format(block_name, MAX_BLOCK_NAME))
    if file_stem and block_name.lower() != file_stem.lower():
        fatal.append(_t(
            "имя пакета «{0}» не совпадает с именем файла «{1}» — игра заведёт второй блок, зарегистрированный по IMG останется пустым, AddAnimation упадёт (IFP-20)."
        ).format(block_name, file_stem))

    if total_anims is not None and total_anims + len(anims) > MAX_ANIMATIONS_TOTAL:
        fatal.append(_t(
            "всего анимаций {0} + {1} > {2} — ms_aAnimations переполнится, анимация №2500 затрёт заголовок блока ped (IFP-22)."
        ).format(total_anims, len(anims), MAX_ANIMATIONS_TOTAL))

    # IFP-18: duplicate animation names (case-insensitive hash).
    seen = {}
    for a in anims:
        key = a.name.lower()
        if key in seen:
            warnings.append(_t(
                "анимация «{0}» повторяет «{1}» (имена сравниваются без регистра) — вторая недостижима (IFP-18)."
            ).format(a.name, seen[key]))
        else:
            seen[key] = a.name

    for a in anims:
        if len(a.name) > MAX_NAME:
            fatal.append(_t(
                "анимация «{0}»: имя длиннее {1} символов — в файл уйдёт обрезанное, по своему имени она не найдётся (IFP-11)."
            ).format(a.name, MAX_NAME))
        if not a.bones:
            fatal.append(_t(
                "анимация «{0}» без единой кости — new[0] и чтение мимо массива при выгрузке (IFP-02)."
            ).format(a.name))
            continue
        if len(a.bones) > MAX_COUNT:
            fatal.append(_t(
                "анимация «{0}»: {1} костей — счётчик int16, максимум {2} (IFP-10)."
            ).format(a.name, len(a.bones), MAX_COUNT))

        # IFP-05: all sequences of one animation must be the same class.
        # The core writer emits one class per file, but honour an explicit
        # per-sequence ``compressed`` attribute if a caller sets one.
        classes = {bool(getattr(b, 'compressed', compressed)) for b in a.bones}
        if len(classes) > 1:
            fatal.append(_t(
                "анимация «{0}»: смешаны сжатые и несжатые кости — движок берёт класс по первой кости и читает остальные с неверным шагом (IFP-05)."
            ).format(a.name))

        # IFP-18: two sequences for the same bone — the last one wins.
        seen_bones = {}
        trans_nonroot = []
        scale_bones = []
        for b in a.bones:
            key = _bone_key(b)
            if key in seen_bones:
                warnings.append(_t(
                    "анимация «{0}»: кость «{1}» (id {2}) задана дважды — играть будет последняя (IFP-18)."
                ).format(a.name, b.name, b.bone_id))
            seen_bones[key] = b

            if len(b.name) > MAX_NAME:
                warnings.append(_t(
                    "анимация «{0}»: имя кости «{1}» длиннее {2} символов — в файл уйдёт обрезанное (IFP-11)."
                ).format(a.name, b.name, MAX_NAME))

            # IFP-04: the frame type must be one of the four rotation
            # classes; a sequence without rotation has no on-disk type.
            if not (b.key_type & HAS_ROT):
                fatal.append(_t(
                    "анимация «{0}» / «{1}»: тип ключей {2} без поворота — такого типа кадра нет, поток рассинхронизируется (IFP-04)."
                ).format(a.name, b.name, b.key_type))
                continue

            # IFP-01: empty sequence.
            if not b.keyframes:
                fatal.append(_t(
                    "анимация «{0}» / «{1}»: 0 ключей — CalcTotalTime читает кадр -1 (IFP-01)."
                ).format(a.name, b.name))
                continue
            if len(b.keyframes) > MAX_COUNT:
                fatal.append(_t(
                    "анимация «{0}» / «{1}»: {2} ключей — счётчик int16, максимум {3} (IFP-10)."
                ).format(a.name, b.name, len(b.keyframes), MAX_COUNT))

            _check_times(a, b, compressed, fmt, fatal, warnings)
            _check_values(a, b, compressed, fatal, warnings)

            if (b.key_type & HAS_TRANS) and not _is_root(b):
                trans_nonroot.append(b.name)
            if b.key_type & HAS_SCALE:
                scale_bones.append(b.name)

        if trans_nonroot:
            warnings.append(_t(
                "анимация «{0}»: ключи смещения на не-корневых костях ({1}) — наличие смещения заменяет bind-позицию кости (IFP-19)."
            ).format(a.name, ', '.join(trans_nonroot)))
        if scale_bones:
            warnings.append(_t(
                "анимация «{0}»: ключи масштаба ({1}) — движок их читает и выбрасывает; ANP3 их не хранит (IFP-21)."
            ).format(a.name, ', '.join(scale_bones)))

    return fatal, warnings
