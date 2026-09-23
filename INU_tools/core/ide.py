"""
GTA SA IDE (Item Definition) file reader/writer.

IDE format — text file with sections:
  objs   — static objects
  tobj   — timed objects (appear/disappear by hour)
  anim   — animated objects
  cars   — vehicle definitions
  peds   — pedestrian definitions
  weap   — weapon model definitions
  hier   — hierarchy/cutscene objects
  txdp   — TXD parent references
  2dfx   — 2D effects (SA uses binary in DFF, IDE section usually empty)

No Blender dependency — pure Python.
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Optional


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class IdeObject:
    """Single object definition from IDE ``objs`` or ``tobj`` section.

    SA поддерживает три формы OBJS-строки (см. CFileLoader::LoadObject
    в gta-reversed-modern):
      • Type 1 (5 полей):  id, name, txd, drawDist, flags
      • Type 2 (7 полей):  id, name, txd, 2, dd1, dd2, flags  — 2 меша
      • Type 3 (9 полей):  id, name, txd, 3, dd1, dd2, dd3, flags  — 3 меша
    Multi-mesh используется в ваниле для LOD-цепочек крупных объектов
    (мост в SF и т.п.). ``extra_draw_distances`` пуст для type 1.
    """
    model_id: int
    model_name: str
    txd_name: str
    draw_distance: float = 300.0
    flags: int = 0
    # tobj-only
    time_on: Optional[int] = None   # hour 0-23
    time_off: Optional[int] = None  # hour 0-23
    # multi-mesh (type 2/3): дополнительные draw distances после первой
    extra_draw_distances: list = field(default_factory=list)

    @property
    def is_timed(self) -> bool:
        return self.time_on is not None and self.time_off is not None

    @property
    def mesh_count(self) -> int:
        return 1 + len(self.extra_draw_distances)


@dataclass
class IdeAnim:
    """Animated object from IDE ``anim`` section.
    Format: ID, ModelName, TXDName, AnimFile, DrawDist, Flags
    """
    model_id: int
    model_name: str
    txd_name: str
    anim_file: str = ""
    draw_distance: float = 300.0
    flags: int = 0


@dataclass
class IdeCar:
    """Vehicle definition from IDE ``cars`` section.
    Format: ID, ModelName, TxdName, Type, HandlingID, GameName, Anims,
            Class, Frequency, Flags, Comprules, WheelID,
            WheelScaleFront, WheelScaleRear, WheelUpgradeClass
    """
    model_id: int
    model_name: str
    txd_name: str
    veh_type: str = "car"
    handling_id: str = ""
    game_name: str = ""
    anims: str = "null"
    veh_class: str = "normal"
    frequency: int = 10
    flags: int = 0
    comprules: int = 0
    wheel_id: int = -1
    wheel_scale_front: float = 1.0
    wheel_scale_rear: float = 1.0
    wheel_upgrade_class: int = -1


@dataclass
class IdePed:
    """Pedestrian definition from IDE ``peds`` section.
    Format: ID, ModelName, TxdName, PedType, Behaviour, AnimGroup,
            CarsCanDriveMask, Flags, AnimFile, Radio1, Radio2,
            VoiceArchive, Voice1, Voice2
    """
    model_id: int
    model_name: str
    txd_name: str
    ped_type: str = "CIVMALE"
    behaviour: str = "CIVMALE"
    anim_group: str = "man"
    cars_can_drive: str = "0"
    flags: str = "0"
    anim_file: str = "null"
    radio1: int = 0
    radio2: int = 0
    voice_archive: str = "null"
    voice1: str = "null"
    voice2: str = "null"
    # Source game tag for cars_can_drive mask. Set when the entry was
    # imported from a known-format IDE file (parser stamps it on
    # read). The writer routes the mask through
    # ``core.ped_mask_translate.translate_mask_str`` when source_game
    # differs from the export target — keeps bit positions aligned to
    # each game's vehicle-class enum (III shifted vs VC/SA).
    source_game: str = ""


@dataclass
class IdeWeap:
    """Weapon model from IDE ``weap`` section.
    Format: ID, ModelName, TxdName, AnimName, MeshCount, DrawDistance
    """
    model_id: int
    model_name: str
    txd_name: str
    anim_name: str = "null"
    mesh_count: int = 1
    draw_distance: float = 100.0


@dataclass
class IdeHier:
    """Hierarchy/cutscene object from IDE ``hier`` section.
    Format: ID, ModelName, TxdName
    """
    model_id: int
    model_name: str
    txd_name: str


@dataclass
class IdeTxdp:
    """TXD parent reference from IDE ``txdp`` section.
    Format: TxdName, ParentTxdName
    """
    txd_name: str
    parent_txd_name: str


@dataclass
class IdeFx2dfx:
    """2DFX entry from IDE ``2dfx`` section. Used by GTA III + Vice
    City (SA stores the same effects inside DFF — see Phase 7).

    Common header (first 9 fields): ``model_id, pos_x, pos_y, pos_z,
    r, g, b, unknown, type_id``. Following fields depend on
    ``type_id`` and are stored verbatim in ``type_params`` (string
    list) to keep the data model game-agnostic — Phase 22 writes the
    list comma-joined after the header.

    Source: gtamods.com/wiki/2DFX + 2d_Effect_(RW_Section) (2026-05).
    """
    model_id: int
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    r: int = 255
    g: int = 255
    b: int = 255
    unknown: int = 200
    type_id: int = 0
    # Type-specific params (everything after type_id on the line) as
    # a list of strings — writer joins with ", ". This avoids
    # type-specific dataclass hierarchies for the IDE section while
    # still preserving exact field values across read→write.
    type_params: list = field(default_factory=list)


@dataclass
class IdeFile:
    """Collection of all IDE entries."""
    objects: list[IdeObject] = field(default_factory=list)
    anims: list[IdeAnim] = field(default_factory=list)
    cars: list[IdeCar] = field(default_factory=list)
    peds: list[IdePed] = field(default_factory=list)
    weaps: list[IdeWeap] = field(default_factory=list)
    hiers: list[IdeHier] = field(default_factory=list)
    txdps: list[IdeTxdp] = field(default_factory=list)
    # 2DFX section entries — populated for III/VC IDEs (where effects
    # live in IDE, not DFF). SA stores effects inline in DFF so this
    # list is typically empty for SA but the data model carries it.
    fx_2dfx: list[IdeFx2dfx] = field(default_factory=list)


# ── Parsing helpers ───────────────────────────────────────────────────

def _tokens(line: str) -> list:
    """Split a data line the way the engine does.

    ``CFileLoader::LoadLine`` (0x536F80) turns every ``,`` and every
    byte < 0x20 (TAB, CR) into a space before ``sscanf`` sees the line,
    so commas and whitespace are interchangeable and empty fields
    (trailing commas) vanish. The old comma-only split silently dropped
    vanilla lines: ``vehicles.ide`` 446/585/586/593 (tabs instead of
    commas, trailing comma) and ``peds.ide`` 51 (W10)."""
    return line.replace(',', ' ').split()


_INT_PREFIX_RE = re.compile(r'[-+]?\d+')


def _sscanf_int(tok: str):
    """``%d`` semantics: the leading integer of the token, or None when
    the token does not start with one. ``3.5`` → 3 (the ``.5`` makes the
    NEXT conversion fail, see ``_sscanf_seq``)."""
    m = _INT_PREFIX_RE.match(tok)
    return int(m.group(0)) if m else None


def _sscanf_seq(parts: list, start: int, kinds: str) -> list:
    """Emulate the numeric tail of an ``sscanf`` format from token
    ``start``: ``kinds`` is one char per conversion (``d`` / ``f``).
    Conversions run in order and stop at the first failure — like the
    CRT, which leaves the remaining targets untouched. A ``%d`` on
    ``3.5`` consumes ``3`` and the leftover ``.5`` fails the following
    conversion. Returns the list of successfully converted values."""
    out = []
    i = start
    for k in kinds:
        if i >= len(parts):
            break
        tok = parts[i]
        if k == 'd':
            v = _sscanf_int(tok)
            if v is None:
                break
            out.append(v)
            if _INT_PREFIX_RE.match(tok).end() != len(tok):
                # partial consumption — the next conversion sees ".5"
                break
        else:
            try:
                out.append(float(tok))
            except ValueError:
                break
        i += 1
    return out


def _parse_obj_line(line: str, timed: bool = False) -> Optional[IdeObject]:
    """Parse one OBJS/TOBJ line exactly the way ``CFileLoader::LoadObject``
    (0x5B3C60) / ``LoadTimeObject`` (0x5B3DE0) do (W9):

    1. ``"%d %s %s %f %d"`` (tobj: ``+ %d %d``). Accepted only when
       every conversion succeeded AND draw distance ≥ 4.0.
    2. Otherwise the legacy mesh-count form: ``"%d %s %s %d"`` gives
       ``count`` (sscanf ``%d`` reads the integer part of ``3.5``), then
       ``count == 1``: ``%f %d``, ``2``: ``%f %f %d``, ``3``: ``%f %f %f %d``
       (tobj: ``+ %d %d``). Any other count keeps whatever pass 1 left in
       dd / flags. Only the first draw distance is used by the game; the
       extra ones are kept for round-trips.
       A fractional count token is consumed only up to the dot: the
       following ``%f`` reads the leftover ``.5``, so ``3.5, 8`` gives
       dd = 0.5 (DAT-08, the object goes invisible) and ``1.5, 2000, 0``
       gives dd = 0.5, flags = 2000. The surplus distances read in that
       case are the flag column, not mesh distances — they are dropped.
    3. Fewer than 4 usable tokens → the engine drops the line (DAT-08b).

    So ``320, airtrain_vlo, generic, 1, 2000, 0`` (vanilla default.ide)
    reads as dd = 2000, flags = 0 — not dd = 1, flags = 2000.
    """
    parts = _tokens(line)
    if len(parts) < 4:
        return None
    model_id = _sscanf_int(parts[0])
    if model_id is None:
        return None
    model_name = parts[1]
    txd_name = parts[2]
    time_on = None
    time_off = None
    extras = []

    # Pass 1 — the SA single-mesh form.
    kinds = 'fd' + ('dd' if timed else '')
    vals = _sscanf_seq(parts, 3, kinds)
    draw_dist = vals[0] if len(vals) > 0 else 0.0
    flags = vals[1] if len(vals) > 1 else 0
    if timed and len(vals) > 2:
        time_on = vals[2]
    if timed and len(vals) > 3:
        time_off = vals[3]
    if len(vals) == len(kinds) and draw_dist >= 4.0:
        return IdeObject(
            model_id=model_id, model_name=model_name, txd_name=txd_name,
            draw_distance=draw_dist, flags=flags,
            time_on=time_on, time_off=time_off,
        )

    # Pass 2 — legacy mesh-count form.
    count = _sscanf_int(parts[3])
    if count is None:
        return None
    if count in (1, 2, 3):
        kinds = 'f' * count + 'd' + ('dd' if timed else '')
        # "%d" on "3.5" leaves ".5" for the next conversion.
        rest = parts[3][_INT_PREFIX_RE.match(parts[3]).end():]
        tail = ([rest] if rest else []) + parts[4:]
        vals = _sscanf_seq(tail, 0, kinds)
        dds = vals[:count]
        if dds:
            draw_dist = dds[0]
            extras = [] if rest else list(dds[1:])
        if len(vals) > count:
            flags = vals[count]
        if timed:
            if len(vals) > count + 1:
                time_on = vals[count + 1]
            if len(vals) > count + 2:
                time_off = vals[count + 2]
    if timed and (time_on is None or time_off is None):
        # LoadTimeObject stores the hours it got; unfilled ones are stack
        # garbage in-engine — treat the line as unusable.
        return None
    return IdeObject(
        model_id=model_id, model_name=model_name, txd_name=txd_name,
        draw_distance=draw_dist, flags=flags,
        time_on=time_on, time_off=time_off,
        extra_draw_distances=extras,
    )


def _parse_anim_line(line: str) -> Optional[IdeAnim]:
    """Parse anim section line: ID, ModelName, TXDName, AnimFile, DrawDist, Flags"""
    parts = _tokens(line)
    try:
        if len(parts) < 5:
            return None
        return IdeAnim(
            model_id=int(parts[0]),
            model_name=parts[1],
            txd_name=parts[2],
            anim_file=parts[3],
            draw_distance=float(parts[4]),
            flags=int(parts[5]) if len(parts) > 5 else 0,
        )
    except (ValueError, IndexError):
        return None


def _parse_car_line(line: str) -> Optional[IdeCar]:
    """Parse cars section line — auto-detect game by column count.

    * 12 cols → GTA III: id, name, txd, type, handling, gamename, class,
      frq, lvl, comprules, wheel_id, wheel_scale
    * 13 cols → GTA VC:  + ``anims`` between gamename and class
    * 15 cols → GTA SA:  + ``flags`` after frequency, split wheel scale,
      ``wheel_upgrade_class``

    Anything in between (10-14 not matching above) falls back to a
    best-effort SA-style parse — matches the legacy behaviour where
    short lines were tolerated.
    """
    parts = _tokens(line)
    n = len(parts)
    if n < 10:
        return None
    try:
        # ── III: 12 cols, no anims field ──────────────────────────
        # Token 7 is III's ``frq`` (a number); in an SA line with 12
        # tokens (boat/plane with a trailing column) it is the class
        # word — so only a numeric token 7 means III.
        if n == 12 and _sscanf_int(parts[7]) is not None:
            return IdeCar(
                model_id=int(parts[0]), model_name=parts[1],
                txd_name=parts[2], veh_type=parts[3],
                handling_id=parts[4], game_name=parts[5],
                anims='null',
                veh_class=parts[6],
                frequency=int(parts[7]),
                flags=0,
                comprules=int(parts[9], 16) if parts[9].strip() else 0,
                wheel_id=int(parts[10]),
                wheel_scale_front=float(parts[11]),
                wheel_scale_rear=float(parts[11]),
            )
        # ── VC: 13 cols, anims present, no flags ─────────────────
        if n == 13:
            return IdeCar(
                model_id=int(parts[0]), model_name=parts[1],
                txd_name=parts[2], veh_type=parts[3],
                handling_id=parts[4], game_name=parts[5],
                anims=parts[6],
                veh_class=parts[7],
                frequency=int(parts[8]),
                flags=0,
                comprules=int(parts[10], 16) if parts[10].strip() else 0,
                wheel_id=int(parts[11]),
                wheel_scale_front=float(parts[12]),
                wheel_scale_rear=float(parts[12]),
            )
        # ── SA: 15 cols (default), 10..14 cols fall through here ─
        car = IdeCar(
            model_id=int(parts[0]),
            model_name=parts[1],
            txd_name=parts[2],
            veh_type=parts[3],
            handling_id=parts[4],
            game_name=parts[5],
            anims=parts[6],
            veh_class=parts[7],
            frequency=int(parts[8]),
            flags=int(parts[9]),
        )
        if n > 10:
            car.comprules = int(parts[10], 16) if parts[10].strip() else 0
        if n > 11:
            car.wheel_id = int(parts[11])
        if n > 12:
            car.wheel_scale_front = float(parts[12])
        if n > 13:
            car.wheel_scale_rear = float(parts[13])
        if n > 14:
            car.wheel_upgrade_class = int(parts[14])
        return car
    except (ValueError, IndexError):
        return None


def _parse_ped_line(line: str) -> Optional[IdePed]:
    """Parse peds section line — auto-detect game by column count.

    * 7  cols → GTA III: id, name, txd, ped_type, behaviour, anim_group,
      cars_can_drive
    * 10 cols → GTA VC:  + anim_file, radio1, radio2
    * 14 cols → GTA SA:  + flags after cars_can_drive, +
      voice_archive, voice1, voice2

    Short / unrecognised line counts fall through to best-effort SA
    parse (matches legacy tolerance).
    """
    parts = _tokens(line)
    n = len(parts)
    if n < 7:
        return None
    try:
        # ── III: 7 cols ──────────────────────────────────────────
        if n == 7:
            return IdePed(
                model_id=int(parts[0]), model_name=parts[1],
                txd_name=parts[2], ped_type=parts[3],
                behaviour=parts[4], anim_group=parts[5],
                cars_can_drive=parts[6],
                source_game='III',
            )
        # ── VC: 10 cols ──────────────────────────────────────────
        if n == 10:
            return IdePed(
                model_id=int(parts[0]), model_name=parts[1],
                txd_name=parts[2], ped_type=parts[3],
                behaviour=parts[4], anim_group=parts[5],
                cars_can_drive=parts[6],
                anim_file=parts[7],
                radio1=int(parts[8]),
                radio2=int(parts[9]),
                source_game='VC',
            )
        # ── SA: 14 cols (default), 8/9/11..13 fall through here ──
        if n < 9:
            return None
        ped = IdePed(
            model_id=int(parts[0]),
            model_name=parts[1],
            txd_name=parts[2],
            ped_type=parts[3],
            behaviour=parts[4],
            anim_group=parts[5],
            cars_can_drive=parts[6],
            flags=parts[7],
            anim_file=parts[8],
            source_game='SA',
        )
        if n > 9:
            ped.radio1 = int(parts[9])
        if n > 10:
            ped.radio2 = int(parts[10])
        if n > 11:
            ped.voice_archive = parts[11]
        if n > 12:
            ped.voice1 = parts[12]
        if n > 13:
            ped.voice2 = parts[13]
        return ped
    except (ValueError, IndexError):
        return None


def _parse_weap_line(line: str) -> Optional[IdeWeap]:
    """Parse weap section line: ID, ModelName, TxdName, AnimName, MeshCount, DrawDist"""
    parts = _tokens(line)
    try:
        if len(parts) < 5:
            return None
        return IdeWeap(
            model_id=int(parts[0]),
            model_name=parts[1],
            txd_name=parts[2],
            anim_name=parts[3],
            mesh_count=int(parts[4]),
            draw_distance=float(parts[5]) if len(parts) > 5 else 100.0,
        )
    except (ValueError, IndexError):
        return None


def _parse_hier_line(line: str) -> Optional[IdeHier]:
    """Parse hier section line: ID, ModelName, TxdName"""
    parts = _tokens(line)
    try:
        if len(parts) < 3:
            return None
        return IdeHier(
            model_id=int(parts[0]),
            model_name=parts[1],
            txd_name=parts[2],
        )
    except (ValueError, IndexError):
        return None


def _parse_txdp_line(line: str) -> Optional[IdeTxdp]:
    """Parse txdp section line: TxdName, ParentTxdName"""
    parts = _tokens(line)
    try:
        if len(parts) < 2:
            return None
        return IdeTxdp(txd_name=parts[0], parent_txd_name=parts[1])
    except (ValueError, IndexError):
        return None


# ── Formatting helpers ────────────────────────────────────────────────

def _fmt_dd(val: float) -> str:
    """Format draw distance: integer if whole, float otherwise."""
    return str(int(val)) if val == int(val) else str(val)


def _format_obj_line(o: IdeObject, *, game: str = 'SA') -> str:
    """Format an ``objs`` line. SA supports the 7/9-field multi-mesh
    variants (mesh_count + 2/3 draw distances); III/VC only know the
    5-field single-mesh form and would mis-parse the longer variants.
    For III/VC we silently downgrade to single-mesh (first draw_dist
    only) — the alternative would be raising on export, which makes
    porting SA assets to VC harder than necessary.
    """
    if o.extra_draw_distances and game == 'SA':
        # SA multi-mesh: id, name, txd, meshCount, dd1, dd2[, dd3], flags
        dds = ', '.join(_fmt_dd(d) for d in (o.draw_distance, *o.extra_draw_distances))
        return f'{o.model_id}, {o.model_name}, {o.txd_name}, {o.mesh_count}, {dds}, {o.flags}'
    return f'{o.model_id}, {o.model_name}, {o.txd_name}, {_fmt_dd(o.draw_distance)}, {o.flags}'


def _format_tobj_line(o: IdeObject, *, game: str = 'SA') -> str:
    """Same multi-mesh / single-mesh distinction as ``_format_obj_line``,
    plus the trailing time_on / time_off columns that mark a timed
    object."""
    if o.extra_draw_distances and game == 'SA':
        dds = ', '.join(_fmt_dd(d) for d in (o.draw_distance, *o.extra_draw_distances))
        return (f'{o.model_id}, {o.model_name}, {o.txd_name}, {o.mesh_count}, '
                f'{dds}, {o.flags}, {o.time_on}, {o.time_off}')
    return f'{o.model_id}, {o.model_name}, {o.txd_name}, {_fmt_dd(o.draw_distance)}, {o.flags}, {o.time_on}, {o.time_off}'


def _format_anim_line(a: IdeAnim) -> str:
    return f'{a.model_id}, {a.model_name}, {a.txd_name}, {a.anim_file}, {_fmt_dd(a.draw_distance)}, {a.flags}'


def _format_car_line(c: IdeCar, *, game: str = 'SA') -> str:
    """Format a ``cars`` line for the target game's column layout.

    * III (12): id, name, txd, type, handling, gamename, class, frq,
      lvl, comprules, wheel_id, wheel_scale
    * VC  (13): + ``anims`` between gamename and class
    * SA  (15): adds ``flags`` after frequency, splits wheel_scale
      into front/rear, adds wheel_upgrade_class

    Source: gtamods.com/wiki/CARS (verified 2026-05).
    """
    comprules = format(c.comprules, 'x') if c.comprules else '0'
    if game == 'III':
        # 'lvl' field has no slot in our data model — emit 0 placeholder
        # (vanilla III files use 0/1 here, behaviour-irrelevant in vanilla).
        return (f'{c.model_id}, {c.model_name}, {c.txd_name}, {c.veh_type}, '
                f'{c.handling_id}, {c.game_name}, {c.veh_class}, '
                f'{c.frequency}, 0, {comprules}, {c.wheel_id}, '
                f'{c.wheel_scale_front:.4f}')
    if game == 'VC':
        return (f'{c.model_id}, {c.model_name}, {c.txd_name}, {c.veh_type}, '
                f'{c.handling_id}, {c.game_name}, {c.anims}, {c.veh_class}, '
                f'{c.frequency}, 0, {comprules}, {c.wheel_id}, '
                f'{c.wheel_scale_front:.4f}')
    # SA (default)
    return (f'{c.model_id}, {c.model_name}, {c.txd_name}, {c.veh_type}, '
            f'{c.handling_id}, {c.game_name}, {c.anims}, {c.veh_class}, '
            f'{c.frequency}, {c.flags}, {comprules}, {c.wheel_id}, '
            f'{c.wheel_scale_front:.4f}, {c.wheel_scale_rear:.4f}, {c.wheel_upgrade_class}')


def _format_ped_line(p: IdePed, *, game: str = 'SA',
                     source_game: str = '') -> str:
    """Format a ``peds`` line for the target game's column layout.

    * III (7):  id, name, txd, pedtype, behaviour, anim_group,
                cars_can_drive
    * VC  (10): + anim_file, radio1, radio2
    * SA  (14): adds ``flags`` after cars_can_drive, then voice_archive,
                voice1, voice2 at the tail

    ``source_game`` — when given and ≠ target ``game``, the
    cars_can_drive hex mask is routed through
    ``core.ped_mask_translate.translate_mask_str`` so vehicle classes
    map correctly across games. III's ``executive`` (bit 0x04) →
    VC's ``richfamily`` (also bit 0x04) without translation; with
    translation, III ``executive`` → VC ``executive`` (bit 0x08).

    Source: gtamods.com/wiki/PEDS (verified 2026-05).
    """
    ccd = p.cars_can_drive
    if source_game and source_game != game:
        from .ped_mask_translate import translate_mask_str
        ccd = translate_mask_str(ccd, source_game, game)

    base = (f'{p.model_id}, {p.model_name}, {p.txd_name}, {p.ped_type}, '
            f'{p.behaviour}, {p.anim_group}, {ccd}')
    if game == 'III':
        return base
    if game == 'VC':
        return f'{base}, {p.anim_file}, {p.radio1}, {p.radio2}'
    # SA (default)
    return (f'{base}, {p.flags}, '
            f'{p.anim_file}, {p.radio1}, {p.radio2}, '
            f'{p.voice_archive}, {p.voice1}, {p.voice2}')


def _format_weap_line(w: IdeWeap) -> str:
    return f'{w.model_id}, {w.model_name}, {w.txd_name}, {w.anim_name}, {w.mesh_count}, {_fmt_dd(w.draw_distance)}'


def _format_hier_line(h: IdeHier) -> str:
    return f'{h.model_id}, {h.model_name}, {h.txd_name}'


def _format_txdp_line(t: IdeTxdp) -> str:
    return f'{t.txd_name}, {t.parent_txd_name}'


def _format_2dfx_line(fx: IdeFx2dfx) -> str:
    """Format one ``2dfx`` IDE line. Common 9-field header + free
    type-specific tail joined from ``type_params``."""
    head = (f'{fx.model_id}, '
            f'{_ff(fx.pos_x)}, {_ff(fx.pos_y)}, {_ff(fx.pos_z)}, '
            f'{fx.r}, {fx.g}, {fx.b}, {fx.unknown}, {fx.type_id}')
    if fx.type_params:
        return head + ', ' + ', '.join(str(p) for p in fx.type_params)
    return head


def _ff(v: float) -> str:
    """Float formatter shared with IPL writer style — 6 decimals.
    Defined here too so 2DFX lines don't pull from ipl module."""
    return f'{v:.6f}'


def _parse_2dfx_line(line: str) -> Optional[IdeFx2dfx]:
    """Parse one ``2dfx`` IDE line: 9-field header + type-specific tail.
    Tail tokens are kept as strings so the writer round-trips them
    verbatim without losing exact float precision or string quoting."""
    parts = _tokens(line)
    if len(parts) < 9:
        return None
    try:
        return IdeFx2dfx(
            model_id=int(parts[0]),
            pos_x=float(parts[1]),
            pos_y=float(parts[2]),
            pos_z=float(parts[3]),
            r=int(parts[4]),
            g=int(parts[5]),
            b=int(parts[6]),
            unknown=int(parts[7]),
            type_id=int(parts[8]),
            type_params=parts[9:],
        )
    except (ValueError, IndexError):
        return None


# ── Reading ─────────────────────────────────────────────────────────

def read_ide(filepath: str) -> IdeFile:
    """Parse a text IDE file and return structured data with all sections."""
    ide = IdeFile()
    section = None

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue

            low = line.lower()

            if low == 'end':
                section = None
                continue

            if low in ('objs', 'tobj', 'anim', 'txdp', 'weap', 'hier',
                       'cars', 'peds', 'path', '2dfx'):
                section = low
                continue

            if section == 'objs':
                obj = _parse_obj_line(line)
                if obj:
                    ide.objects.append(obj)
            elif section == 'tobj':
                obj = _parse_obj_line(line, timed=True)
                if obj:
                    ide.objects.append(obj)
            elif section == 'anim':
                anim = _parse_anim_line(line)
                if anim:
                    ide.anims.append(anim)
            elif section == 'cars':
                car = _parse_car_line(line)
                if car:
                    ide.cars.append(car)
            elif section == 'peds':
                ped = _parse_ped_line(line)
                if ped:
                    ide.peds.append(ped)
            elif section == 'weap':
                weap = _parse_weap_line(line)
                if weap:
                    ide.weaps.append(weap)
            elif section == 'hier':
                hier = _parse_hier_line(line)
                if hier:
                    ide.hiers.append(hier)
            elif section == 'txdp':
                txdp = _parse_txdp_line(line)
                if txdp:
                    ide.txdps.append(txdp)
            elif section == '2dfx':
                fx = _parse_2dfx_line(line)
                if fx:
                    ide.fx_2dfx.append(fx)

    return ide


def find_ides_for_model_ids(ide_paths, model_ids):
    """Given IDE file paths and a set of model ids, return which IDE files
    define at least one of those ids: ``{ide_path: [model_id, ...]}``.

    Powers the Import sub-panel's auto-discovery — «which .ide do this IPL's
    models come from?». Matching is by Model ID (works for both text and
    binary IPL, since binary carries only the id). Unreadable IDEs are
    skipped silently."""
    wanted = set(model_ids)
    if not wanted:
        return {}
    result = {}
    for p in ide_paths:
        try:
            ide = read_ide(p)
        except Exception:
            continue
        hits = set()
        for obj in ide.objects:
            if obj.model_id in wanted:
                hits.add(obj.model_id)
        for anim in ide.anims:
            if anim.model_id in wanted:
                hits.add(anim.model_id)
        if hits:
            result[p] = sorted(hits)
    return result


# ── Writing ─────────────────────────────────────────────────────────

def write_ide(filepath: str, ide: IdeFile, *, game: str = 'SA') -> None:
    """Write a full IDE file.

    Standard map sections (objs, tobj, anim) are ALWAYS emitted with a
    terminating ``end`` — even when empty — to match vanilla layout.
    Specialised sections (cars, peds, weap, hier) are only emitted when
    populated. Game-specific sections:

    * ``txdp`` (texture-parent table) — VC + SA only; III predates it
      and would reject the unknown section header.
    * ``2dfx`` — SA-only IDE section (placeholder; effects live in DFF).

    ``game`` (III/VC/SA) — controls section gating + ``objs``/``tobj``
    multi-mesh dispatch (III/VC always single-mesh).
    """
    objs = [o for o in ide.objects if not o.is_timed]
    tobjs = [o for o in ide.objects if o.is_timed]

    with open(filepath, 'w', encoding='utf-8', newline='\r\n') as f:
        # objs — always emitted
        f.write('objs\n')
        for o in objs:
            f.write(_format_obj_line(o, game=game) + '\n')
        f.write('end\n')

        # tobj — always emitted
        f.write('tobj\n')
        for o in tobjs:
            f.write(_format_tobj_line(o, game=game) + '\n')
        f.write('end\n')

        # anim — always emitted
        f.write('anim\n')
        for a in ide.anims:
            f.write(_format_anim_line(a) + '\n')
        f.write('end\n')

        # cars — only when populated (veh.ide style). Per-game column
        # layout (III=12, VC=13, SA=15) handled by the line formatter.
        if ide.cars:
            f.write('cars\n')
            for c in ide.cars:
                f.write(_format_car_line(c, game=game) + '\n')
            f.write('end\n')

        # peds — only when populated (peds.ide style). Per-game layout
        # (III=7, VC=10, SA=14 columns). cars_can_drive mask is
        # translated through ped_mask_translate when the per-entry
        # source_game differs from the export target.
        if ide.peds:
            f.write('peds\n')
            for p in ide.peds:
                f.write(_format_ped_line(p, game=game,
                                          source_game=p.source_game) + '\n')
            f.write('end\n')

        # weap — only when populated
        if ide.weaps:
            f.write('weap\n')
            for w in ide.weaps:
                f.write(_format_weap_line(w) + '\n')
            f.write('end\n')

        # hier — only when populated
        if ide.hiers:
            f.write('hier\n')
            for h in ide.hiers:
                f.write(_format_hier_line(h) + '\n')
            f.write('end\n')

        # txdp — VC + SA (III IDE parser rejects unknown sections).
        if game != 'III':
            f.write('txdp\n')
            for t in ide.txdps:
                f.write(_format_txdp_line(t) + '\n')
            f.write('end\n')

        # 2dfx section — III/VC store effects HERE (not in DFF), SA
        # stores in DFF but vanilla SA still emits an empty 2dfx
        # block. Writing entries from ``ide.fx_2dfx`` lets III/VC mods
        # carry Light/Particle/PedAttractor/SunGlare data correctly;
        # SA users get the SA-only Type 5 (special) into IDE too via
        # this path. Emit when populated for any game; emit empty for
        # SA to match vanilla layout.
        if ide.fx_2dfx or game == 'SA':
            f.write('2dfx\n')
            for fx in ide.fx_2dfx:
                f.write(_format_2dfx_line(fx) + '\n')
            f.write('end\n')


def upsert_ide(filepath: str, entries: list[IdeObject]) -> tuple[int, int]:
    """
    Insert or update entries in an existing IDE file.

    - If entry with same model_id exists → replace the line.
    - If no match → append to the ``objs`` section (or create it).

    Returns (updated_count, added_count).
    """
    if not os.path.isfile(filepath):
        # File doesn't exist — write fresh
        write_ide(filepath, IdeFile(objects=entries))
        return (0, len(entries))

    # Read original lines
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    # Build lookup of entries to upsert by model_id
    pending: dict[int, IdeObject] = {e.model_id: e for e in entries}
    updated = 0
    result_lines = []
    section = None
    objs_end_idx = -1  # index of 'end' line for objs section ONLY

    for line in lines:
        stripped = line.strip()
        low = stripped.lower()

        if low == 'end' and section is not None:
            if section == 'objs':
                objs_end_idx = len(result_lines)
            section = None
            result_lines.append(line)
            continue

        if low in ('objs', 'tobj', 'anim', 'txdp', 'weap', 'hier',
                   'cars', 'peds', 'path', '2dfx'):
            # Previous section ended implicitly (no 'end' before new section)
            if section == 'objs':
                objs_end_idx = len(result_lines)
            section = low
            result_lines.append(line)
            continue

        if section in ('objs', 'tobj') and stripped and not stripped.startswith('#'):
            parsed = _parse_obj_line(stripped, timed=(section == 'tobj'))
            if parsed and parsed.model_id in pending:
                # Replace this line with updated entry
                entry = pending.pop(parsed.model_id)
                if entry.is_timed:
                    result_lines.append(_format_tobj_line(entry) + '\n')
                else:
                    result_lines.append(_format_obj_line(entry) + '\n')
                updated += 1
                continue

        result_lines.append(line)

    # Remaining entries need to be appended
    added = len(pending)
    if added > 0:
        remaining = list(pending.values())
        if objs_end_idx >= 0:
            # Insert before the last 'end' of objs section
            insert_lines = [_format_obj_line(e) + '\n' for e in remaining]
            result_lines = (result_lines[:objs_end_idx]
                          + insert_lines
                          + result_lines[objs_end_idx:])
        else:
            # No objs section found — append one at the end
            result_lines.append('objs\n')
            for e in remaining:
                result_lines.append(_format_obj_line(e) + '\n')
            result_lines.append('end\n')

    with open(filepath, 'w', encoding='utf-8', newline='\r\n') as f:
        f.writelines(result_lines)

    return (updated, added)


def remove_ide(filepath: str, model_ids: set[int]) -> int:
    """Remove entries with given model_ids from IDE file. Returns count removed."""
    if not os.path.isfile(filepath):
        return 0

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    result_lines = []
    section = None
    removed = 0

    for line in lines:
        stripped = line.strip()
        low = stripped.lower()

        if low == 'end':
            section = None
            result_lines.append(line)
            continue

        if low in ('objs', 'tobj', 'anim', 'txdp', 'weap', 'hier',
                   'cars', 'peds', 'path', '2dfx'):
            section = low
            result_lines.append(line)
            continue

        if section in ('objs', 'tobj', 'anim', 'cars', 'peds', 'weap', 'hier'):
            if stripped and not stripped.startswith('#'):
                # Try to extract model_id (first field)
                try:
                    mid = int(_tokens(stripped)[0])
                    if mid in model_ids:
                        removed += 1
                        continue
                except (ValueError, IndexError):
                    pass

        result_lines.append(line)

    if removed > 0:
        with open(filepath, 'w', encoding='utf-8', newline='\r\n') as f:
            f.writelines(result_lines)

    return removed
