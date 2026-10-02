# INU_tools.core.map_lint
# Cross-reference analysis for IDE / IPL files. Pure-Python, bpy-free.
#
# Phase 1 (this module):
# - Parse one or more IDE files → collect defined model definitions
# - Parse one or more IPL files → collect placed instances
# - Cross-reference: orphan placements (in IPL but no IDE), unused IDs
#   (in IDE but never placed), conflicts (same id in two IDEs).
# - Per-file structural checks (field count, name length, NaN coords,
#   interior range, drawdist sanity).
# - Optional IMG verification: if a list of files in the archive is
#   provided, also flag IDE entries that reference DFF/TXD that don't
#   exist there.
#
# Reuses the LintIssue structure from file_lint so the UIList and save-
# report code don't need to know about a different result format.

from dataclasses import dataclass, field
from math import isnan, isinf
from typing import Dict, List, Optional, Set, Tuple

from .file_lint import LintIssue
from . import lint_profile


# ── Limits / thresholds ──────────────────────────────────────────

# Vanilla SA model_id ceiling. Past this requires Fastman92 Limit
# Adjuster (FLA) — flagged as WARN, not ERROR.
_VANILLA_ID_MAX = 19999
_FLA_ID_MAX = 65535
# Vanilla SA interior count is 18 (1-18 + outside=0). FLA ramps to 255.
_VANILLA_INTERIOR_MAX = 18
# Map bounds. Real SA terrain spans about ±3000 m; anything outside is
# either a streaming bug or an off-grid prop loaded by a script.
_MAP_BOUND = 3500.0
# DrawDist sanity. Vanilla LODs commonly go 1000-1500m; threshold of 800
# would flag every LOD as "high". Bump to 2000 — past that either a
# 1-piece view-distance hack or accidental decimal point.
_DRAWDIST_HIGH = 2000.0
# IDE sections that ARE expected to be referenced by IPL placement.
# cars/peds/weaps/hiers are spawned at runtime by scripts (CLEO /
# main.scm), so the IDE_UNUSED check skips them — they're always
# "unused" in the IPL sense and would flood the report on vanilla.
_IDE_PLACEABLE_KINDS = frozenset({'objs', 'anim'})
# IDE OBJS file format: name ≤ 24 chars (game-side buffer), TXD ≤ 23.
_IDE_NAME_MAX = 24
_TXD_NAME_MAX = 23
# LOD detection: per gtamods.com/wiki/Item_Definition there is NO
# dedicated "is LOD" IDE-flag bit. VC bit 0x100 = IGNORE_DRAW_DISTANCE
# correlates with LOD models but the canonical marker across all three
# games is the model's NAME (``lod*`` prefix or ``*_lod`` suffix),
# resolved via ``core.ipl.is_lod_name``. We use that here too.
#
# (Earlier this module assumed ``_IDE_FLAG_LOD = 0x100`` which was
# wrong for SA — vanilla SA never sets that bit on LOD models.)


@dataclass
class MapStats:
    """Aggregate counters returned alongside the issue list."""
    ide_files: int = 0
    ipl_files: int = 0
    defined_models: int = 0
    placed_instances: int = 0
    unused_models: int = 0
    orphan_placements: int = 0
    duplicate_ids: int = 0
    interiors_used: int = 0
    lod_pairs: int = 0
    lod_chain_broken: int = 0
    by_section: Dict[str, int] = field(default_factory=dict)


def _bad_float(v) -> bool:
    try:
        return isnan(v) or isinf(v)
    except TypeError:
        return True


# ── Per-file IDE checks ──────────────────────────────────────────

def _lint_ide_file(path: str, ide, drawdist_high: float = _DRAWDIST_HIGH,
                   vanilla_id_max: int = _VANILLA_ID_MAX) -> List[LintIssue]:
    """Structural checks on one parsed IdeFile.

    ``ide`` is the dataclass returned by core.ide.read_ide().
    ``drawdist_high`` — DRAWDIST_HIGH override (STRICT profile lowers
    this to 800m, default 2000m).
    ``vanilla_id_max`` — game-specific model_id ceiling above which
    Fastman92 Limit Adjuster is required. III=6500, VC=8500, SA=19999.
    Default matches SA for backward compatibility.
    """
    out: List[LintIssue] = []

    def _check_entry(kind: str, idx: int, model_id, name, txd):
        # ``loc`` is the issue summary shown as the header. It already
        # carries the ID — body lines below MUST NOT repeat ``ID = …``
        # or the panel ends up with the same number stacked twice with
        # uneven spacing between rows.
        loc = f"{kind}[{idx}] '{name}' (ID = {model_id})"

        if not isinstance(model_id, int) or model_id < 0:
            out.append(LintIssue('ERROR', 'IDE_BAD_ID', path, loc,
                "Причина = некорректный (отрицательный/non-int)"))
        elif model_id > _FLA_ID_MAX:
            out.append(LintIssue('WARN', 'IDE_ID_OUT_OF_RANGE', path, loc,
                f"Лимит FLA = {_FLA_ID_MAX}"))
        elif model_id > vanilla_id_max:
            out.append(LintIssue('WARN', 'IDE_ID_NEEDS_FLA', path, loc,
                f"Лимит vanilla = {vanilla_id_max}"))

        if not name:
            out.append(LintIssue('ERROR', 'IDE_NAME_EMPTY', path, loc,
                "Имя модели = пусто"))
        elif len(name) > _IDE_NAME_MAX:
            out.append(LintIssue('ERROR', 'IDE_NAME_TOO_LONG', path, loc,
                f"Имя = '{name}'\nДлина = {len(name)}\nЛимит engine = {_IDE_NAME_MAX}"))

        if txd and len(txd) > _TXD_NAME_MAX:
            out.append(LintIssue('ERROR', 'IDE_TXD_NAME_TOO_LONG', path, loc,
                f"Имя TXD = '{txd}'\nДлина = {len(txd)}\nЛимит engine = {_TXD_NAME_MAX}"))

    for i, o in enumerate(ide.objects):
        _check_entry('objs', i, o.model_id, o.model_name, o.txd_name)
        if _bad_float(o.draw_distance) or o.draw_distance < 0:
            out.append(LintIssue('ERROR', 'IDE_DRAWDIST_BAD', path,
                f"objs[{i}] '{o.model_name}'",
                f"draw_distance = {o.draw_distance!r}"))
        elif o.draw_distance > drawdist_high:
            out.append(LintIssue('INFO', 'IDE_DRAWDIST_HIGH', path,
                f"objs[{i}] '{o.model_name}'",
                f"draw_distance = {o.draw_distance:.0f}m\nПорог = {drawdist_high:.0f}m"))

    for i, a in enumerate(ide.anims):
        _check_entry('anim', i, a.model_id, a.model_name, a.txd_name)
    for i, c in enumerate(ide.cars):
        _check_entry('cars', i, c.model_id, c.model_name, c.txd_name)
    for i, p in enumerate(ide.peds):
        _check_entry('peds', i, p.model_id, p.model_name, p.txd_name)
    for i, w in enumerate(ide.weaps):
        _check_entry('weap', i, w.model_id, w.model_name, w.txd_name)
    for i, h in enumerate(ide.hiers):
        _check_entry('hier', i, h.model_id, h.model_name, h.txd_name)

    return out


# ── Per-file IPL checks ──────────────────────────────────────────

def _lint_ipl_file(path: str, ipl) -> List[LintIssue]:
    out: List[LintIssue] = []

    for i, inst in enumerate(ipl.instances):
        # ``loc`` summary carries the ID — body lines below must not
        # repeat ``ID = …``.
        loc = f"inst[{i}] '{inst.model_name}' (ID = {inst.model_id})"

        for axis_name, val in (('x', inst.pos_x), ('y', inst.pos_y), ('z', inst.pos_z)):
            if _bad_float(val):
                out.append(LintIssue('ERROR', 'IPL_COORD_NAN', path, loc,
                    f"Ось = {axis_name}\nЗначение = {val!r}"))
                break
            if abs(val) > _MAP_BOUND:
                out.append(LintIssue('WARN', 'IPL_COORD_OFF_MAP', path, loc,
                    f"Ось = {axis_name}\nЗначение = {val:.0f}\nГраница карты = ±{_MAP_BOUND:.0f}m"))

        if inst.interior < 0:
            out.append(LintIssue('WARN', 'IPL_INTERIOR_NEGATIVE', path, loc,
                f"Interior = {inst.interior}"))
        elif inst.interior > _VANILLA_INTERIOR_MAX:
            out.append(LintIssue('INFO', 'IPL_INTERIOR_NON_STANDARD', path, loc,
                f"Interior = {inst.interior}\nДиапазон vanilla = 0-{_VANILLA_INTERIOR_MAX}"))

        if inst.model_id < 0 or inst.model_id > _FLA_ID_MAX:
            out.append(LintIssue('ERROR', 'IPL_BAD_ID', path, loc,
                "Причина = вне допустимого диапазона"))

        if not inst.model_name:
            out.append(LintIssue('WARN', 'IPL_NAME_EMPTY', path, loc,
                "Имя модели = пусто"))

    return out


# ── Cross-reference (the actual value of this module) ────────────

def cross_reference(
    ide_paths_results: List[Tuple[str, object]],   # (path, IdeFile)
    ipl_paths_results: List[Tuple[str, object]],   # (path, IplFile)
    img_files: Optional[object] = None,
    profile: str = lint_profile.STANDARD,
    game: str = 'SA',
) -> Tuple[List[LintIssue], MapStats]:
    """Cross-check IDEs vs IPLs.

    Returns ``(issues, stats)``. ``issues`` is the combined list of
    structural + cross-ref issues; ``stats`` is the aggregated counter.

    ``img_files`` — optional, archive contents for asset-presence and
    shadow-collision checks. Accepts two forms:

    - ``Dict[str, Set[str]]`` (path → entry-name set). Enables both
      ``IDE_DFF_MISSING`` / ``IDE_TXD_MISSING`` (asset absent from EVERY
      archive) and ``IMG_TXD_SHADOWED`` (same TXD/DFF name in multiple
      archives — engine takes the one loaded first via gta.dat order
      and silently drops the rest).
      The reserved ``'<loose>'`` key contains loose modloader assets and
      TEXDICTION/MODELFILE names: presence only, no archive shadowing.
    - ``Set[str]`` (legacy, flat name set). Only the missing-asset check
      runs; no shadowing detection possible with a flat set.
    """
    issues: List[LintIssue] = []
    stats = MapStats()
    stats.ide_files = len(ide_paths_results)
    stats.ipl_files = len(ipl_paths_results)

    # Resolve profile thresholds once at top — STRICT lowers
    # drawdist_high from 2000m to 800m, others leave it default.
    _profile_cfg = lint_profile.get_profile(profile)
    _drawdist_high = (_profile_cfg.drawdist_high
                      if _profile_cfg.drawdist_high is not None
                      else _DRAWDIST_HIGH)
    # Per-game model_id ceiling: III=6500, VC=8500, SA=19999. Above
    # this, FLA is required (IDE_ID_NEEDS_FLA warning fires). Pulled
    # from GameProfile so the limit moves correctly with the scene's
    # gtatools_game without touching map_lint constants.
    from . import game_versions as _gv
    _vanilla_id_max = _gv.profile_for(game).model_id_max

    # Index defined models: id → list of (path, name, txd)
    defined: Dict[int, List[Tuple[str, str, str, str]]] = {}  # id → (path, kind, name, txd)
    name_by_id: Dict[int, str] = {}    # last-seen name for each id (for IPL mismatch)
    # Reverse lookup name → id, lets us catch the vanilla pattern
    # where IPL uses outdated id but the model exists in IDE under a
    # different id (vegaxref.ipl ⇄ vegaxref.ide is the canonical case).
    id_by_name: Dict[str, int] = {}
    section_count: Dict[str, int] = {}
    # Per-id "is this model a LOD by name convention" — set when the
    # model name has the lod* prefix or *_lod suffix (see
    # ``core.ipl.is_lod_name``). Works uniformly across III/VC/SA;
    # replaces the old "flags & 0x100" heuristic which was wrong for SA.
    lod_by_id: set = set()
    from .ipl import is_lod_name as _is_lod_name

    def _record(path, kind, mid, name, txd, flags=0):
        defined.setdefault(mid, []).append((path, kind, name, txd or ''))
        name_by_id[mid] = name
        if name:
            id_by_name[name.lower()] = mid
        section_count[kind] = section_count.get(kind, 0) + 1
        if kind in _IDE_PLACEABLE_KINDS and name and _is_lod_name(name):
            lod_by_id.add(mid)

    for path, ide in ide_paths_results:
        issues.extend(_lint_ide_file(path, ide,
                                     drawdist_high=_drawdist_high,
                                     vanilla_id_max=_vanilla_id_max))
        for o in ide.objects:
            _record(path, 'objs', o.model_id, o.model_name, o.txd_name,
                    getattr(o, 'flags', 0))
        for a in ide.anims:
            _record(path, 'anim', a.model_id, a.model_name, a.txd_name,
                    getattr(a, 'flags', 0))
        for c in ide.cars:
            _record(path, 'cars', c.model_id, c.model_name, c.txd_name)
        for p in ide.peds:
            _record(path, 'peds', p.model_id, p.model_name, p.txd_name)
        for w in ide.weaps:
            _record(path, 'weap', w.model_id, w.model_name, w.txd_name)
        for h in ide.hiers:
            _record(path, 'hier', h.model_id, h.model_name, h.txd_name)

    stats.by_section = section_count
    stats.defined_models = len(defined)

    # Duplicate model_id check. Engine takes the FIRST loaded entry
    # for that id and silently ignores the rest — game doesn't crash,
    # but the duplicate models can never be referenced. WARN, not ERROR.
    for mid, entries in defined.items():
        if len(entries) > 1:
            stats.duplicate_ids += 1
            paths = ', '.join(sorted(set(e[0] for e in entries)))
            kinds = '/'.join(sorted(set(e[1] for e in entries)))
            # Build "Имя 1 = X / Имя 2 = Y / ..." structured message.
            # Header (summary) already carries ``id={mid} ({kinds})`` —
            # don't repeat it in the body, just list the conflicting
            # definitions so the user can decide which one to keep.
            lines = [f"Определений = {len(entries)}"]
            for idx, (_p, _k, _name, _txd) in enumerate(entries, start=1):
                lines.append(f"Имя {idx} = {_name}")
            issues.append(LintIssue('WARN', 'IDE_DUPLICATE_ID', paths,
                f"ID = {mid} ({kinds})",
                '\n'.join(lines)))

    # IPL passes — placement + cross-check against defined IDs.
    placed_ids: Set[int] = set()
    interiors: Set[int] = set()
    lod_pair_count = 0
    placed_total = 0

    for path, ipl in ipl_paths_results:
        issues.extend(_lint_ipl_file(path, ipl))

        # Pre-scan: which instance indices are referenced as LOD by some
        # other instance in this same file. Used below to flag orphan
        # LOD-flagged models (defined as LOD in IDE, but no HD points
        # at them in this IPL).
        referenced_as_lod: Set[int] = set()
        for inst in ipl.instances:
            li = getattr(inst, 'lod_index', -1)
            if li is not None and 0 <= li < len(ipl.instances):
                referenced_as_lod.add(li)

        for i, inst in enumerate(ipl.instances):
            placed_total += 1
            placed_ids.add(inst.model_id)
            interiors.add(inst.interior)
            if inst.lod_index is not None and inst.lod_index >= 0:
                lod_pair_count += 1
                if inst.lod_index >= len(ipl.instances):
                    issues.append(LintIssue('ERROR', 'IPL_LOD_REF_OOR',
                        path, f"inst[{i}] '{inst.model_name}'",
                        f"lod_index = {inst.lod_index}\nВсего инстансов = {len(ipl.instances)}"))
                else:
                    # In-range LOD reference — run chain-validity checks.
                    partner = ipl.instances[inst.lod_index]
                    partner_is_lod = partner.model_id in lod_by_id
                    partner_li = getattr(partner, 'lod_index', -1)
                    # 1) Partner must look like a LOD (lod-name convention).
                    #    Engine will still render the model, but a misnamed
                    #    LOD partner usually means the IPL wired the wrong
                    #    target — verify by looking at the model name.
                    if not partner_is_lod:
                        stats.lod_chain_broken += 1
                        issues.append(LintIssue('WARN', 'IPL_LOD_PARTNER_NO_FLAG',
                            path, f"inst[{i}] '{inst.model_name}'",
                            f"HD = '{inst.model_name}' (ID = {inst.model_id})\n"
                            f"LOD = '{partner.model_name}' (ID = {partner.model_id})\n"
                            f"Имя не соответствует LOD-конвенции (нет lod*/«*_lod»)"))
                    # 2) Partner itself must NOT be a chain link —
                    #    its lod_index must be -1. Two-hop chains
                    #    (HD → LOD → LOD2) crash the streamer's
                    #    fade logic.
                    if partner_li is not None and partner_li >= 0:
                        stats.lod_chain_broken += 1
                        issues.append(LintIssue('ERROR', 'IPL_LOD_CHAIN',
                            path, f"inst[{i}] '{inst.model_name}'",
                            f"HD = '{inst.model_name}'\n"
                            f"LOD = '{partner.model_name}' (idx = {inst.lod_index})\n"
                            f"LOD.lod_index = {partner_li}\n"
                            f"Должно быть = -1"))
                    # 3) HD instance whose own model has a LOD-style name —
                    #    being used in two roles at once. Likely a copy/paste
                    #    bug in IPL or a wrongly-named base model.
                    if inst.model_id in lod_by_id:
                        stats.lod_chain_broken += 1
                        issues.append(LintIssue('WARN', 'IPL_HD_HAS_LOD_FLAG',
                            path, f"inst[{i}] '{inst.model_name}' (ID = {inst.model_id})",
                            f"Имя = '{inst.model_name}' (lod-style)\n"
                            f"Но в IPL используется как HD (имеет lod_index ≥ 0)"))

            # 4) Orphan LOD: model name looks like LOD but no IPL inst
            #    references it via lod_index. Streamer never shows it —
            #    the LOD is dead weight in the placement file.
            if (inst.model_id in lod_by_id) and i not in referenced_as_lod:
                stats.lod_chain_broken += 1
                issues.append(LintIssue('INFO', 'IPL_LOD_ORPHAN',
                    path, f"inst[{i}] '{inst.model_name}' (ID = {inst.model_id})",
                    f"Имя = '{inst.model_name}' (lod-style)\n"
                    f"Ссылок lod_index = нет"))

            if inst.model_id not in defined:
                stats.orphan_placements += 1
                key = (inst.model_name or '').lower()
                alt_id = id_by_name.get(key)
                if alt_id is not None:
                    issues.append(LintIssue('WARN', 'IPL_ID_OUTDATED',
                        path, f"inst[{i}] '{inst.model_name}'",
                        f"Имя = {inst.model_name}\n"
                        f"ID в IPL = {inst.model_id}\n"
                        f"ID в IDE = {alt_id}"))
                else:
                    issues.append(LintIssue('WARN', 'IPL_MODEL_NOT_IN_IDE',
                        path,
                        f"inst[{i}] '{inst.model_name}' (ID = {inst.model_id})",
                        f"Имя = '{inst.model_name}'\n"
                        f"Найдено в IDE = нет (ни по ID, ни по имени)"))
            else:
                # Sanity: name in IPL matches name in IDE for same id?
                ide_name = name_by_id.get(inst.model_id, '')
                if ide_name and inst.model_name and ide_name.lower() != inst.model_name.lower():
                    issues.append(LintIssue('WARN', 'IPL_NAME_MISMATCH',
                        path, f"inst[{i}] (ID = {inst.model_id})",
                        f"В IPL = '{inst.model_name}'\n"
                        f"В IDE = '{ide_name}'"))

    stats.placed_instances = placed_total
    stats.lod_pairs = lod_pair_count
    stats.interiors_used = len(interiors)
    # Count UNUSED only over IDE sections that ARE expected to be
    # placed via IPL (cars/peds/weaps/hiers are script-spawned).
    stats.unused_models = sum(
        1 for mid, entries in defined.items()
        if mid not in placed_ids and entries[0][1] in _IDE_PLACEABLE_KINDS)

    # Unused (defined but never placed). Only checks IDE sections that
    # SHOULD be IPL-placed: objs/anim. cars/peds/weaps/hiers are
    # spawned at runtime by scripts (CLEO, main.scm) and are always
    # "unused" from the IPL viewpoint — flagging them would dump
    # thousands of false positives on vanilla.
    for mid, entries in defined.items():
        if mid in placed_ids:
            continue
        path, kind, name, _txd = entries[0]
        if kind not in _IDE_PLACEABLE_KINDS:
            continue
        issues.append(LintIssue('INFO', 'IDE_UNUSED', path,
            f"{kind} '{name}' (ID = {mid})",
            f"Имя = '{name}'\nТип = {kind}"))

    # IMG verification (DFF/TXD presence in archive + cross-archive
    # shadowing). The img_files parameter accepts two shapes — a flat
    # set (legacy: one bundle, no shadowing detection) or a per-archive
    # dict keyed by archive path. Normalise to per-archive form so the
    # downstream code can both compute the union (for presence) AND
    # detect duplicates across archives (for shadowing).
    if img_files:
        if isinstance(img_files, dict):
            archives_raw = {k: v for k, v in img_files.items()}
        else:
            # Legacy flat set — wrap as a single anonymous archive.
            archives_raw = {'<img>': set(img_files)}

        # Normalise entry names: strip extension, lowercase. Keep a
        # parallel ``ext_map`` so we can tell DFF apart from TXD when
        # reporting shadowing (same base name with different extensions
        # is NOT a conflict).
        archives: Dict[str, Set[str]] = {}        # archive_path → {basename}
        ext_by_base: Dict[str, Dict[str, Set[str]]] = {}  # basename → ext → {archive_path}
        union_names: Set[str] = set()
        for arch_path, names in archives_raw.items():
            normed = set()
            for fn in names:
                low = fn.lower()
                if '.' in low:
                    base, ext = low.rsplit('.', 1)
                else:
                    base, ext = low, ''
                normed.add(base)
                # Loose modloader overrides / TEXDICTIONs satisfy presence,
                # but are not competing streaming archive registrations.
                if arch_path != '<loose>':
                    ext_by_base.setdefault(base, {}).setdefault(ext, set()).add(arch_path)
            archives[arch_path] = normed
            union_names.update(normed)

        present = {fn.lower() for names in archives_raw.values() for fn in names}
        # ── Per-asset missing check (asset must exist in at least one
        # archive). We dedupe by name so the same DFF used by 200
        # instances reports only once.
        reported_dff: Set[str] = set()
        reported_txd: Set[str] = set()
        for mid, entries in defined.items():
            for path, kind, name, txd in entries:
                key_dff = name.lower()
                if key_dff and key_dff + '.dff' not in present and key_dff not in present and key_dff not in reported_dff:
                    reported_dff.add(key_dff)
                    issues.append(LintIssue('WARN', 'IDE_DFF_MISSING',
                        path, f"{kind} '{name}' (ID = {mid})",
                        f"Имя модели = '{name}'\nИщется = {name}.dff\nВ IMG = не найдено"))
                key_txd = (txd or '').lower()
                if key_txd and key_txd + '.txd' not in present and key_txd not in present and key_txd not in reported_txd:
                    reported_txd.add(key_txd)
                    issues.append(LintIssue('WARN', 'IDE_TXD_MISSING',
                        path, f"{kind} '{name}' (ID = {mid})",
                        f"Имя модели = '{name}'\nИщется = {txd}.txd\nВ IMG = не найдено"))

        # ── Cross-archive shadowing: same DFF/TXD basename present in
        # ≥ 2 archives. Engine reads gta.dat entries top-to-bottom and
        # keeps the FIRST loader registration for each name; subsequent
        # archives' copies become unreachable. Modders hit this when
        # adding gta3_custom.img alongside the vanilla gta3.img and
        # wondering why their edits never appear in-game.
        if len(archives) >= 2:
            for base, ext_map in ext_by_base.items():
                for ext, arch_set in ext_map.items():
                    if len(arch_set) < 2:
                        continue
                    if ext not in ('dff', 'txd', 'col', 'ifp'):
                        continue
                    code = ('IMG_TXD_SHADOWED' if ext == 'txd'
                            else 'IMG_DFF_SHADOWED' if ext == 'dff'
                            else 'IMG_COL_SHADOWED' if ext == 'col'
                            else 'IMG_IFP_SHADOWED')
                    sev = 'WARN'
                    paths_sorted = sorted(arch_set)
                    body = [f"Имя = '{base}.{ext}'",
                            f"Найдено в = {len(paths_sorted)} архивах"]
                    for idx, ap in enumerate(paths_sorted, start=1):
                        body.append(f"Архив {idx} = {ap}")
                    issues.append(LintIssue(sev, code, paths_sorted[0],
                        f"'{base}.{ext}' shadowed",
                        '\n'.join(body)))

    # Profile post-filter: FLA silences specific codes (IDE_ID_NEEDS_FLA
    # etc.), LENIENT drops everything informational. Done as the last
    # step so the stats counts above stay accurate — they reflect raw
    # findings, not the filtered view.
    issues = lint_profile.apply_filter(issues, profile)

    return issues, stats


# ── Convenience: parse + lint in one call ────────────────────────

def analyze_files(
    ide_paths: List[str],
    ipl_paths: List[str],
    img_files: Optional[object] = None,
    profile: str = lint_profile.STANDARD,
    game: str = 'SA',
) -> Tuple[List[LintIssue], MapStats]:
    """Parse the given IDE/IPL files and run cross_reference. Files
    that fail to parse turn into a single ``IDE_PARSE_FAIL`` /
    ``IPL_PARSE_FAIL`` issue and are dropped from the analysis.

    ``img_files`` — see ``cross_reference`` for accepted shapes
    (flat set OR per-archive dict). The per-archive dict form is
    required to detect cross-archive shadowing.
    """
    from .ide import read_ide
    from .ipl import read_ipl

    issues: List[LintIssue] = []
    parsed_ides: List[Tuple[str, object]] = []
    parsed_ipls: List[Tuple[str, object]] = []

    for path in ide_paths:
        try:
            parsed_ides.append((path, read_ide(path)))
        except Exception as e:
            issues.append(LintIssue('ERROR', 'IDE_PARSE_FAIL', path, '',
                f"Ошибка = {e.__class__.__name__}\nДетали = {e}"))
    for path in ipl_paths:
        try:
            parsed_ipls.append((path, read_ipl(path)))
        except Exception as e:
            issues.append(LintIssue('ERROR', 'IPL_PARSE_FAIL', path, '',
                f"Ошибка = {e.__class__.__name__}\nДетали = {e}"))

    cross_issues, stats = cross_reference(
        parsed_ides, parsed_ipls, img_files, profile=profile, game=game)
    issues.extend(cross_issues)
    # Re-filter the pre-cross-reference parse-fail issues too — LENIENT
    # would still want PARSE_FAIL through (they're ERROR), but FLA's
    # silenced_codes don't intersect them so no-op there. apply_filter
    # is idempotent on already-filtered lists.
    issues = lint_profile.apply_filter(issues, profile)
    return issues, stats


# ── Issue-code → human explanation ───────────────────────────────

EXPLANATIONS = {
    'IDE_PARSE_FAIL': "Парсер IDE упал. Файл повреждён или содержит неподдерживаемую секцию.",
    'IPL_PARSE_FAIL': "Парсер IPL упал. Файл повреждён или содержит секцию которую мы не умеем читать.",
    'IDE_BAD_ID':
        "model_id некорректный (отрицательный или non-int). Engine не загрузит эту модель.",
    'IDE_ID_OUT_OF_RANGE':
        "model_id превышает FLA-максимум 65535. Не работает даже с Fastman92 Limit Adjuster — "
        "engine читает u16 из item-таблицы.",
    'IDE_ID_NEEDS_FLA':
        "model_id > 19999 — vanilla SA не поддерживает, нужен Fastman92 Limit Adjuster. "
        "С FLA до 65535 работает.",
    'IDE_NAME_EMPTY':
        "Имя модели пустое — engine не сможет найти DFF в IMG.",
    'IDE_NAME_TOO_LONG':
        "Имя модели > 24 символов. Engine читает буфер 24 байта и обрезает имя — "
        "ссылка на DFF в IMG будет неверной → null model.",
    'IDE_TXD_NAME_TOO_LONG':
        "Имя TXD > 23 символов — обрезается. Material lookup не найдёт текстуры → "
        "модель отрисуется без текстур.",
    'IDE_DRAWDIST_BAD':
        "draw_distance NaN/Inf или отрицательный. Cull-расчёт сломается — модель либо "
        "не появится, либо никогда не выгрузится.",
    'IDE_DRAWDIST_HIGH':
        "draw_distance > 2000m. Vanilla LODs обычно 1000-1500m, обычные props 100-300m. "
        "Значение выше 2000 — почти всегда опечатка экспортёра или 1-piece view-distance "
        "хак (всю карту в одной модели). Стрим будет загружать модель далеко.",
    'IDE_UNUSED':
        "model_id определён в IDE (objs/anim секция), но нигде не размещён через IPL. "
        "Балласт — занимает слот ID, увеличивает время парсинга. cars/peds/weaps/hiers "
        "не проверяются на UNUSED — они спавнятся скриптами и в IPL никогда не лежат.",
    'IDE_DUPLICATE_ID':
        "Один model_id определён в нескольких IDE. Engine берёт ПЕРВЫЙ загруженный — "
        "остальные становятся unreachable. Игра не крашит, но модели с того же ID не появляются. "
        "В vanilla SA таких 7 (countn2.ide vs leveldes.ide пересекаются по 16700-16702).",
    'IDE_DFF_MISSING':
        "IDE ссылается на DFF которого нет в IMG-архиве. Engine получит null model → "
        "проп не появится; в местах с CullZone — возможный краш стримера.",
    'IDE_TXD_MISSING':
        "IDE ссылается на TXD которого нет в IMG. Модель загрузится но без текстур "
        "(чёрная / шахматка).",
    'IMG_TXD_SHADOWED':
        "Один и тот же TXD-name присутствует в нескольких IMG-архивах. Engine "
        "регистрирует FIRST loader для имени (по порядку gta.dat) и молча "
        "игнорирует копии в остальных архивах — твои правки в gta3_custom.img "
        "могут не появляться в игре, потому что vanilla gta3.img перебивает. "
        "Решение: или вытащи дубликат из лишнего архива, или подвинь порядок "
        "загрузки в gta.dat.",
    'IMG_DFF_SHADOWED':
        "DFF-name присутствует в нескольких IMG. Engine берёт первый зарегистрированный — "
        "правки в добавленном архиве не появляются в игре. Аналогично TXD-shadowing.",
    'IMG_COL_SHADOWED':
        "COL-name присутствует в нескольких IMG. Engine берёт первый зарегистрированный — "
        "столкновения из добавленного архива не применяются.",
    'IMG_IFP_SHADOWED':
        "IFP-name присутствует в нескольких IMG. Engine берёт первый — анимации из "
        "добавленного архива не применяются.",
    'IPL_PARSE_FAIL':
        "Парсер IPL упал.",
    'IPL_BAD_ID':
        "model_id в IPL некорректный.",
    'IPL_NAME_EMPTY':
        "IPL-инстанс без имени модели.",
    'IPL_COORD_NAN':
        "Координаты позиции содержат NaN/Inf. Engine разместит инстанс в космосе или "
        "упадёт при первом ray-cast.",
    'IPL_COORD_OFF_MAP':
        "Координаты вне карты (±3500m). Скорее всего опечатка/баг экспортёра — "
        "проп будет загружаться зря, никогда не виден.",
    'IPL_INTERIOR_NEGATIVE':
        "Interior id < 0. Engine читает как u8, отрицательное значение wrap'нется в "
        "большое число (например -1 → 255). Игра не крашит, но проп окажется в "
        "неожиданном interior — обычно невидимым.",
    'IPL_INTERIOR_NON_STANDARD':
        "Interior id вне диапазона 0-18 (vanilla SA range). Не обязательно баг — "
        "vanilla `countn2.ipl` шипает interior=1024 как «render anywhere» sentinel, "
        "engine просто читает значение verbatim. Если ты сам не ставил такие, "
        "проверь не съехала ли колонка в IPL-строке.",
    'IPL_LOD_REF_OOR':
        "lod_index указывает на entry за пределами IPL — LOD не будет работать. "
        "Engine отрисует только HD без переключения.",
    'IPL_LOD_PARTNER_NO_FLAG':
        "Инстанс ссылается на LOD-партнёр (lod_index), но у партнёра в IDE НЕ "
        "установлен LOD-бит (0x100 в objs.flags). Engine отрисует модель, но "
        "не будет переключаться между HD и LOD по дистанции — увидишь pop-in "
        "на границе draw_distance. Поставь LOD-флаг в IDE для модели-партнёра.",
    'IPL_LOD_CHAIN':
        "Двухзвенная LOD-цепочка: HD ссылается на LOD, а у LOD тоже lod_index ≠ -1. "
        "Engine SA ожидает один hop (HD → LOD → конец), цепочки длиннее ломают "
        "streamer fade logic. У LOD-инстанса lod_index должен быть -1.",
    'IPL_HD_HAS_LOD_FLAG':
        "Инстанс используется как HD (имеет lod_index ≥ 0 → ссылается на свой LOD), "
        "но его собственная модель в IDE помечена LOD-флагом (0x100). Модель играет "
        "сразу две роли — вероятно опечатка во флагах IDE или copy/paste бага в IPL.",
    'IPL_LOD_ORPHAN':
        "Модель в IDE помечена LOD-флагом (0x100), но ни один инстанс в этом IPL "
        "не ссылается на неё через lod_index. Engine никогда её не отрисует — "
        "balast в placement. Либо добавь lod_index у HD-партнёра, либо сними "
        "LOD-флаг и используй как обычную модель.",
    'IPL_MODEL_NOT_IN_IDE':
        "Инстанс размещает model_id, и ни одна IDE не определяет НИ этот ID, НИ модель "
        "с таким именем. Engine SA forgiving — просто скипает placement, проп не появляется. "
        "Игра НЕ крашит. Если в кастомной карте — модель реально потеряна, добавь в IDE.",
    'IPL_ID_OUTDATED':
        "IPL ссылается на model_id, который ни одна IDE не определяет, НО модель с таким "
        "ИМЕНЕМ существует в IDE под другим id. Engine SA матчит по имени и грузит модель "
        "корректно — игра работает. Это типичный паттерн vanilla vegaxref.ipl ⇄ vegaxref.ide "
        "(IPL не обновили после rev в IDE). Чисто косметический баг — обнови id в IPL "
        "чтобы cross-ref был чистый.",
    'IPL_NAME_MISMATCH':
        "В IPL имя модели не совпадает с именем в IDE для того же model_id. "
        "Engine использует ID, имя в IPL — справочное; но рассинхрон обычно означает "
        "что один из файлов был отредактирован руками неаккуратно.",
}


def explain(code: str) -> str:
    return EXPLANATIONS.get(code, "(нет описания для этого кода)")
