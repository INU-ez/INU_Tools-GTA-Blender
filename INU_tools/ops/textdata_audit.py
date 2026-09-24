# INU_tools.ops.textdata_audit — surface core.textdata_lint findings in
# the export operators, the same way the skin audit is surfaced in the
# DFF export: fatals go to the ERROR channel (red, named), warnings to
# the operator's WARNING channel, everything mirrored to the console.
#
# The file is written FIRST and audited afterwards from what actually
# landed on disk (re-read through the same core reader the game-side
# rules were calibrated on) — nothing is blocked, the user sees what the
# engine will do with the file and decides.

import bpy

from .. import T

# Blender shows every report in the Info log; keep the banner sane
# (the console always gets the full list).
_MAX_WARNINGS = 25
_MAX_FATALS = 25


def report_lint(op, label, fatal, warnings):
    """Report ``(fatal, warnings)`` from a ``core.textdata_lint`` check on
    behalf of operator ``op``. Returns True when there were fatals."""
    for item in fatal:
        print(f"[INU lint] {label}: {T('Игра не примет')}: {item}")
    for item in warnings:
        print(f"[INU lint] {label}: {item}")
    shown = warnings[:_MAX_WARNINGS]
    for item in shown:
        op.report({'WARNING'}, f"{label}: {item}")
    if len(warnings) > len(shown):
        op.report({'WARNING'}, T("{0}: ещё {1} предупреждений — см. консоль").format(
            label, len(warnings) - len(shown)))
    shown = fatal[:_MAX_FATALS]
    for item in shown:
        op.report({'ERROR'}, f"{T('Игра не примет')} {label}: {item}")
    if len(fatal) > len(shown):
        op.report({'ERROR'}, T("{0}: ещё {1} ошибок — см. консоль").format(
            label, len(fatal) - len(shown)))
    return bool(fatal)


def _ide_ids(path):
    """Model ids defined by one IDE file (None when unreadable)."""
    try:
        from ..core.ide import read_ide
        ide = read_ide(path)
    except Exception:
        return None
    ids = set()
    for lst in (ide.objects, ide.anims, ide.hiers, ide.cars, ide.peds, ide.weaps):
        for e in lst:
            ids.add(e.model_id)
    return ids


# game root → (signature of (path, mtime) pairs, ids) — the sweep over
# ~60 vanilla IDEs is not free, and every export re-audits.
_known_cache = {}


def _game_ide_ids(root):
    """Union of the ids of every IDE listed in default.dat / gta.dat
    (and gta_int.dat) under ``root`` — the set the game actually loads.
    None when the root has no data/gta.dat."""
    import os
    from ..core.gta_dat import parse_gta_dat, resolve_paths
    paths = []
    for dat in ('default.dat', 'gta.dat', 'gta_int.dat'):
        dat_path = os.path.join(root, 'data', dat)
        if not os.path.isfile(dat_path):
            continue
        try:
            info = resolve_paths(root, parse_gta_dat(dat_path))
        except Exception:
            continue
        paths.extend(p for p in info.ide_paths if os.path.isfile(p))
    if not os.path.isfile(os.path.join(root, 'data', 'gta.dat')) or not paths:
        return None
    sig = tuple((p, os.path.getmtime(p)) for p in paths)
    cached = _known_cache.get(root)
    if cached is not None and cached[0] == sig:
        return set(cached[1])
    ids = set()
    for p in paths:
        ids |= _ide_ids(p) or set()
    _known_cache[root] = (sig, frozenset(ids))
    return ids


def known_model_ids(context):
    """The «defined» half of the IPL id check. Returns
    ``(ids, complete, label)``: ``ids`` — model ids the game will have
    when it loads the IPL (None = unknown, only the range check runs);
    ``complete`` — True when the set covers every IDE in gta.dat /
    default.dat under the scene's game root (an id outside it IS a
    crash), False when only the picked IDE (``gtatools_ide_path``,
    ``label``) was available (an id outside it may live in another
    loaded IDE — a warning, not a fatal)."""
    import os
    try:
        s = context.scene.inu_settings
        picked = bpy.path.abspath(s.gtatools_ide_path or '')
        root = bpy.path.abspath(getattr(s, 'gtatools_game_root', '') or '')
    except Exception:
        return None, False, ''
    ids = None
    complete = False
    label = ''
    if root and os.path.isdir(root):
        ids = _game_ide_ids(root)
        complete = ids is not None
    if picked and os.path.isfile(picked):
        # A mod IDE not (yet) listed in gta.dat still defines its ids.
        picked_ids = _ide_ids(picked)
        if picked_ids is not None:
            ids = (ids or set()) | picked_ids
            label = os.path.basename(picked)
    return ids, complete, label


def audit_ide_file(op, path):
    """Re-read the IDE just written and report the DAT-* findings."""
    try:
        from ..core.ide import read_ide
        from ..core.textdata_lint import check_ide
        fatal, warnings = check_ide(read_ide(path))
    except Exception as e:                       # noqa: BLE001
        print(f"[INU lint] IDE audit failed: {e}")
        return False
    import os
    return report_lint(op, os.path.basename(path), fatal, warnings)


def audit_ipl_file(op, path, context=None, *, binary=False):
    """Re-read the IPL just written and report the DAT-* findings."""
    try:
        from ..core.ipl import read_ipl
        from ..core.textdata_lint import check_ipl
        ipl = read_ipl(path)
        known, complete, label = (known_model_ids(context) if context is not None
                                  else (None, False, ''))
        fatal, warnings = check_ipl(ipl, known, filename=path, binary=binary,
                                    known_complete=complete, known_label=label)
    except Exception as e:                       # noqa: BLE001
        print(f"[INU lint] IPL audit failed: {e}")
        return False
    import os
    return report_lint(op, os.path.basename(path), fatal, warnings)


def audit_water_file(op, path):
    try:
        from ..core.water import read_water
        from ..core.textdata_lint import check_water
        fatal, warnings = check_water(read_water(path))
    except Exception as e:                       # noqa: BLE001
        print(f"[INU lint] water audit failed: {e}")
        return False
    import os
    return report_lint(op, os.path.basename(path), fatal, warnings)
