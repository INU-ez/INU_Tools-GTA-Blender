# INU_tools.core.game_versions
# Game-version constants and dispatch helpers for the III/VC/SA
# multi-game pipeline. Every format reader/writer consults this module
# instead of hardcoding 0x36003 / surface table sizes / etc — gives a
# single source of truth for "what does this game expect?"
#
# Scene exposes the active game via ``gtatools_game`` EnumProperty.
# This module only stores constants and pure helpers; it does NOT
# import bpy so it stays unit-testable.

from dataclasses import dataclass
from typing import Optional


# ── Game enum values ──────────────────────────────────────────────
# String IDs used by the Scene EnumProperty. Stable — do not rename.

GAME_III = 'III'    # Grand Theft Auto III (2001, RW3.3)
GAME_VC = 'VC'      # Grand Theft Auto: Vice City (2002, RW3.4.0.3 on PC)
GAME_SA = 'SA'      # Grand Theft Auto: San Andreas (2004, RW3.6)

ALL_GAMES = (GAME_III, GAME_VC, GAME_SA)


# ── RW version mapping ───────────────────────────────────────────
# Vanilla writes from each game's RenderWare build. Values are the
# 4-byte LE field at the end of every RW chunk header.

RW_VERSION_III = 0x33002    # RW 3.3.0.2 — vanilla III (also 0x31000 in early PS2 builds)
RW_VERSION_VC = 0x34003     # RW 3.4.0.3 — vanilla VC PC (3.5.0.0 is the Xbox build;
                            # the PC exe is linked against 3.4.0.3 and rejects newer streams)
RW_VERSION_SA = 0x36003     # RW 3.6.0.3 — vanilla SA

_RW_VERSION_BY_GAME = {
    GAME_III: RW_VERSION_III,
    GAME_VC:  RW_VERSION_VC,
    GAME_SA:  RW_VERSION_SA,
}

# Reverse mapping for game auto-detection from RW version bytes.
# Each version maps to a single game (the one that vanilla-writes it).
# Files with non-vanilla versions (mods cross-compiled etc) still pass
# through but detect_from_rw_version returns None → caller decides.
_GAME_BY_RW_VERSION = {v: g for g, v in _RW_VERSION_BY_GAME.items()}

# RW version float-pack constants for the IFP/older RW headers that
# use a single u16 (instead of the modern u32 1.6.0.3-style packing).
# Most users will never touch these but the parser layers need them.
RW_VERSION_LEGACY_III = 0x0310  # PS2 launch builds
RW_VERSION_LEGACY_VC = 0x0400


def rw_version_for_game(game: str) -> int:
    """Return the canonical RW version int for the given game enum.
    Fallback = SA for unknown values, so writers never crash."""
    return _RW_VERSION_BY_GAME.get(game, RW_VERSION_SA)


def detect_from_rw_version(version: int) -> Optional[str]:
    """Reverse lookup: which game wrote this RW version? Returns
    GAME_III/VC/SA, or None if the version isn't recognisable as an RW3
    build. Use for auto-detect on DFF/TXD/COL import.

    Exact vanilla versions match first; otherwise we fall back to the
    RW-version RANGE each game shipped, because real files use several
    builds (III: 3.1–3.3, VC: 3.4–3.5, SA: 3.6), not one fixed value —
    e.g. original III models are RW 3.2.0.0 (0x32000), which isn't the
    canonical 0x33002 but is unmistakably III.
    """
    exact = _GAME_BY_RW_VERSION.get(version)
    if exact is not None:
        return exact
    # Range fallback — only within the RW3 space (0x3xxxx). The three
    # games occupy non-overlapping minor-version bands, so the boundary
    # test never misclassifies one for another.
    if 0x30000 <= version < 0x34000:
        return GAME_III          # 3.0–3.3
    if 0x34000 <= version < 0x36000:
        return GAME_VC           # 3.4–3.5
    if 0x36000 <= version < 0x40000:
        return GAME_SA           # 3.6+
    return None


# ── Per-game limits & feature flags ──────────────────────────────
# Each field captures one engine quirk that diverges between games.
# Lint / export code reads these instead of branching on game string.

@dataclass(frozen=True)
class GameProfile:
    """Per-game limits and capability flags. One instance per game,
    looked up via ``profile_for(game)``."""

    name: str               # 'San Andreas' / 'Vice City' / 'III'
    rw_version: int         # canonical RW3 version int
    # ── COL format ─────────────────────────────────────────────
    col_version: int        # 1 (III, VC), 3 (SA). COL2 is an SA-era
                            # format too (weapons.col) — no game reads
                            # COL2/COL3 but SA; III/VC assert 'COLL'.
    col_supports_shadow_mesh: bool   # SA-only
    col_supports_face_groups: bool   # SA-only
    # ── DFF capabilities ──────────────────────────────────────
    dff_supports_skinning: bool      # peds skin in all 3, vehicles skin only in SA
    dff_supports_2dfx: bool          # all 3
    dff_supports_night_vertex_colors: bool   # Extra Vert Colours (VC+)
    # ── TXD / textures ────────────────────────────────────────
    txd_native_platform_default: int   # 8=D3D8 (SA), 9=D3D9 (VC PC), …
    # ── IDE sections (which kinds the parser must support) ───
    ide_sections: frozenset         # e.g. {'objs', 'tobj', 'cars'}
    # ── IPL inst column count ─────────────────────────────────
    ipl_inst_columns: int           # 12 (III), 13 (VC: +interior), 11 (SA)
    ipl_supports_binary: bool       # SA-only
    # ── IMG archive ───────────────────────────────────────────
    img_version: int                # 1 (III/VC, .dir external), 2 (SA, embedded)
    # ── Surface IDs (collision material) ─────────────────────
    surface_id_max: int             # 84 (III), 85 (VC), 178 (SA)
    # ── Model ID limits ──────────────────────────────────────
    model_id_max: int               # stock MODELINFOSIZE: 5500 (III), 6500 (VC), 19999 (SA)


_PROFILE_III = GameProfile(
    name="Grand Theft Auto III",
    rw_version=RW_VERSION_III,
    col_version=1,
    col_supports_shadow_mesh=False,
    col_supports_face_groups=False,
    dff_supports_skinning=True,         # peds yes, vehicles no
    dff_supports_2dfx=True,
    dff_supports_night_vertex_colors=False,
    txd_native_platform_default=8,
    ide_sections=frozenset({'objs', 'tobj', 'hier',
                            'cars', 'peds', 'weap', 'anim',
                            'path'}),  # path was III-only experimental
    ipl_inst_columns=12,
    ipl_supports_binary=False,
    img_version=1,
    surface_id_max=84,
    model_id_max=5500,          # MODELINFOSIZE (re3 config.h); more needs a limit adjuster
)

_PROFILE_VC = GameProfile(
    name="Grand Theft Auto: Vice City",
    rw_version=RW_VERSION_VC,
    col_version=1,              # VC PC LoadCollisionFile asserts ident == 'COLL'
    col_supports_shadow_mesh=False,
    col_supports_face_groups=False,
    dff_supports_skinning=True,
    dff_supports_2dfx=True,
    dff_supports_night_vertex_colors=True,   # VC introduced Extra Vert Colours
    txd_native_platform_default=8,
    ide_sections=frozenset({'objs', 'tobj', 'hier',
                            'cars', 'peds', 'weap', 'anim',
                            'txdp'}),  # txdp was added in VC
    ipl_inst_columns=13,        # id name interior x y z sx sy sz rx ry rz rw
    ipl_supports_binary=False,
    img_version=1,
    surface_id_max=85,
    model_id_max=6500,          # MODELINFOSIZE (reVC config.h)
)

_PROFILE_SA = GameProfile(
    name="Grand Theft Auto: San Andreas",
    rw_version=RW_VERSION_SA,
    col_version=3,
    col_supports_shadow_mesh=True,
    col_supports_face_groups=True,
    dff_supports_skinning=True,
    dff_supports_2dfx=True,
    dff_supports_night_vertex_colors=True,
    txd_native_platform_default=8,
    ide_sections=frozenset({'objs', 'tobj', 'hier',
                            'cars', 'peds', 'weap', 'anim',
                            'txdp', '2dfx'}),  # 2dfx section is SA-only
    ipl_inst_columns=11,
    ipl_supports_binary=True,
    img_version=2,
    surface_id_max=178,
    model_id_max=19999,
)

_PROFILES = {
    GAME_III: _PROFILE_III,
    GAME_VC:  _PROFILE_VC,
    GAME_SA:  _PROFILE_SA,
}


def profile_for(game: str) -> GameProfile:
    """Return the GameProfile for the given game enum. Unknown
    values fall back to SA (safest default — SA writers are battle-
    tested and writing SA output for an unspecified game is the
    least surprising behaviour)."""
    return _PROFILES.get(game, _PROFILE_SA)


# ── Scene access helper ──────────────────────────────────────────
# Pull the active game from a bpy.types.Scene without forcing every
# caller to know the property name. Returns SA if the scene doesn't
# have the field yet (e.g. opened in a pre-multi-game build).

def game_of_scene(scene) -> str:
    """Read ``scene.inu_settings.gtatools_game`` with safe fallback
    to SA. Importable from anywhere without circular deps — no bpy
    type check, just a getattr chain."""
    inu = getattr(scene, 'inu_settings', None)
    if inu is None:
        return GAME_SA
    return getattr(inu, 'gtatools_game', GAME_SA)


# ── Import-side auto-detection ───────────────────────────────────
# Each detect_game_from_<format> reads just enough of the file to
# identify the game. Returns the GAME_* enum, or None when the
# format/version is unrecognised (caller decides whether to keep
# the scene's current setting or fall back to SA).

def detect_game_from_dff(path: str) -> Optional[str]:
    """Read the RW version from a DFF's outer chunk header (first 12
    bytes — type, size, library_id) and map it back to a game."""
    try:
        with open(path, 'rb') as f:
            head = f.read(12)
        if len(head) < 12:
            return None
        import struct
        _ctype, _csize, lib_id = struct.unpack('<III', head)
        # Decode library ID → RW version (mirrors dff._decode_library_id)
        if lib_id & 0xFFFF0000 == 0:
            rw_version = lib_id << 8
        else:
            rw_version = (((lib_id >> 14) & 0x3FF00) + 0x30000) | ((lib_id >> 16) & 0x3F)
        return detect_from_rw_version(rw_version)
    except OSError:
        return None


def detect_game_from_col(path: str) -> Optional[str]:
    """Detect game from a COL file's first-model magic header.
    COL2/COL3 → SA (only SA reads them). COLL is shared by III and VC
    (both engines accept nothing else), so it can't pick one — return
    None and let the caller keep the scene's game."""
    try:
        with open(path, 'rb') as f:
            magic = f.read(4)
        if magic in (b'COL2', b'COL3'):
            return GAME_SA
    except OSError:
        pass
    return None


def detect_game_from_ipl(path: str) -> Optional[str]:
    """Detect game from the first ``inst`` line's column count.
    11 cols → SA, 12 cols → III (no interior), 13 cols → VC.
    For 12-col SA+FLA variant the parser would already accept it as
    SA via the realInterior fallback; here we lean toward III when
    token[2] looks like a float coord rather than an integer interior.
    """
    try:
        in_inst = False
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                low = line.lower()
                if low == 'inst':
                    in_inst = True
                    continue
                if low == 'end':
                    in_inst = False
                    continue
                if in_inst:
                    parts = [p.strip() for p in line.split(',')]
                    n = len(parts)
                    if n == 13:
                        return GAME_VC
                    if n == 12 and len(parts) > 2 and '.' in parts[2]:
                        return GAME_III
                    if n in (11, 12):
                        return GAME_SA
                    return None  # malformed line
    except OSError:
        pass
    return None


def detect_game_from_img(path: str) -> Optional[str]:
    """Detect game from an IMG archive: VER2 magic → SA, sibling
    ``.dir`` present (and no VER2 magic) → III/VC (can't tell apart
    from IMG alone — return VC as the more common case; user can
    flip to III via the panel switcher if needed)."""
    try:
        with open(path, 'rb') as f:
            head = f.read(4)
        if head == b'VER2':
            return GAME_SA
    except OSError:
        return None
    import os as _os
    sibling = _os.path.splitext(path)[0] + '.dir'
    if _os.path.isfile(sibling):
        return GAME_VC  # VC is more common; III is older and rarer
    return None


def detect_game_from_txd(path: str) -> Optional[str]:
    """Detect game from a TXD's outer chunk library_id. Same
    encoding scheme as DFF — RW version field at offset 8."""
    return detect_game_from_dff(path)   # same chunk-header layout


# ── Scene auto-update helper ─────────────────────────────────────

def maybe_set_game_from_import(scene, detected_game: Optional[str]) -> bool:
    """Auto-update ``scene.inu_settings.gtatools_game`` to the detected
    game when the scene looks "fresh" (default SA + no INU objects yet).
    Otherwise leave the user's choice alone. Returns True when the
    scene was updated, False when no change was made.

    Defensive: ``detected_game`` may be None when detection failed.
    """
    if detected_game is None:
        return False
    inu = getattr(scene, 'inu_settings', None)
    if inu is None:
        return False
    current = getattr(inu, 'gtatools_game', GAME_SA)
    if current == detected_game:
        return False
    # Only auto-flip when the scene is still at its default SA AND no
    # mesh objects have an `obj.inu.model_id` set yet — that signals
    # "this is a fresh import session, not a mixed-game project".
    if current != GAME_SA:
        return False
    try:
        scene_objs = getattr(scene, 'objects', None) or []
        for obj in scene_objs:
            obj_inu = getattr(obj, 'inu', None)
            if obj_inu is None:
                continue
            mid = getattr(obj_inu, 'model_id', 0)
            if mid:
                # Already-populated scene — respect the user's choice.
                return False
    except Exception:
        return False
    try:
        inu.gtatools_game = detected_game
        return True
    except Exception:
        return False


def check_game_mismatch_warning(scene, detected_game: Optional[str]
                                ) -> Optional[str]:
    """Return a human-readable warning string when the imported file's
    detected game differs from the scene's active game AND
    ``maybe_set_game_from_import`` didn't auto-flip (e.g. scene already
    has populated INU objects).

    The warning tells the user to switch the GTA Tools panel tab to
    avoid stale per-game formats. Returns ``None`` when there's no
    mismatch or detection failed. Importers route the result via
    ``self.report({'WARNING'}, msg)``.
    """
    if detected_game is None:
        return None
    inu = getattr(scene, 'inu_settings', None)
    if inu is None:
        return None
    current = getattr(inu, 'gtatools_game', GAME_SA)
    if current == detected_game:
        return None
    return (f"Импортированный файл = {detected_game}, "
            f"но активная игра сцены = {current}. "
            f"Переключи вкладку GTA Tools на «{detected_game}» — "
            f"иначе экспорт пойдёт в неправильном формате.")
