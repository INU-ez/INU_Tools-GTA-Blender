"""
GTA SA gta.dat / gta_int.dat parser (also III gta3.dat, VC gta_vc.dat).

These files list all IDE, IPL, IMG and other resources the game loads.
Lines starting with IDE, IPL, IMG, SPLASH, COLFILE, TEXDICTION, MODELFILE
specify resource paths relative to the game root. III/VC name archives
with CDIMAGE instead of IMG — both go to img_paths.

Usage:
    info = parse_gta_dat("C:/Games/GTA SA/data/gta.dat")
    # info.ide_paths  → ["DATA\\MAPS\\generic\\vegepart.ide", ...]
    # info.ipl_paths  → ["DATA\\MAPS\\LA\\LAn.ipl", ...]
    # info.img_paths  → ["MODELS\\gta3.img", ...]

No Blender dependency — pure Python.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field


@dataclass
class GtaDatInfo:
    """Parsed gta.dat / gta_int.dat contents."""
    ide_paths: list[str] = field(default_factory=list)
    ipl_paths: list[str] = field(default_factory=list)
    img_paths: list[str] = field(default_factory=list)
    colfile_paths: list[str] = field(default_factory=list)
    texdiction_paths: list[str] = field(default_factory=list)
    modelfile_paths: list[str] = field(default_factory=list)
    splash_paths: list[str] = field(default_factory=list)


def parse_gta_dat(filepath: str) -> GtaDatInfo:
    """Parse a gta.dat or gta_int.dat file."""
    info = GtaDatInfo()

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split(None, 1)
            if len(parts) < 2:
                continue

            keyword = parts[0].upper()
            path = parts[1].strip()

            if keyword == 'IDE':
                info.ide_paths.append(path)
            elif keyword == 'IPL':
                info.ipl_paths.append(path)
            elif keyword in ('IMG', 'CDIMAGE'):
                info.img_paths.append(path)
            elif keyword == 'COLFILE':
                # Format: COLFILE <level> <path>
                col_parts = path.split(None, 1)
                if len(col_parts) >= 2:
                    info.colfile_paths.append(col_parts[1].strip())
                else:
                    info.colfile_paths.append(path)
            elif keyword == 'TEXDICTION':
                info.texdiction_paths.append(path)
            elif keyword == 'MODELFILE':
                info.modelfile_paths.append(path)
            elif keyword == 'SPLASH':
                info.splash_paths.append(path)

    return info


def resolve_paths(game_root: str, dat_info: GtaDatInfo) -> GtaDatInfo:
    """Convert relative paths to absolute using game root directory.
    Backslashes are normalized to forward slashes."""
    def _resolve(p: str) -> str:
        # Normalize separators
        p = p.replace('\\', '/')
        full = os.path.join(game_root, p)
        return os.path.normpath(full)

    return GtaDatInfo(
        ide_paths=[_resolve(p) for p in dat_info.ide_paths],
        ipl_paths=[_resolve(p) for p in dat_info.ipl_paths],
        img_paths=[_resolve(p) for p in dat_info.img_paths],
        colfile_paths=[_resolve(p) for p in dat_info.colfile_paths],
        texdiction_paths=[_resolve(p) for p in dat_info.texdiction_paths],
        modelfile_paths=[_resolve(p) for p in dat_info.modelfile_paths],
        splash_paths=[_resolve(p) for p in dat_info.splash_paths],
    )


def find_all_resources(game_root: str) -> GtaDatInfo:
    """Parse both gta.dat and gta_int.dat, merge and resolve all paths."""
    merged = GtaDatInfo()

    for dat_name in ('gta.dat', 'gta_int.dat'):
        dat_path = os.path.join(game_root, 'data', dat_name)
        if not os.path.isfile(dat_path):
            continue
        info = parse_gta_dat(dat_path)
        merged.ide_paths.extend(info.ide_paths)
        merged.ipl_paths.extend(info.ipl_paths)
        merged.img_paths.extend(info.img_paths)
        merged.colfile_paths.extend(info.colfile_paths)
        merged.texdiction_paths.extend(info.texdiction_paths)
        merged.modelfile_paths.extend(info.modelfile_paths)
        merged.splash_paths.extend(info.splash_paths)

    return resolve_paths(game_root, merged)


# Every .dat the game loads at start: default.dat (vehicles, peds, weapons)
# then its own — SA gta.dat + gta_int.dat, VC gta_vc.dat, III gta3.dat.
GAME_DATS = ('default.dat', 'gta.dat', 'gta_int.dat', 'gta_vc.dat', 'gta3.dat')


def game_ide_paths(game_root: str) -> tuple[list[str], list[str]]:
    """IDE files the game loads: the IDE lines of every ``data/<dat>`` of
    GAME_DATS that exists, resolved, de-duplicated case-insensitively, in
    load order. Returns ``(ide_paths, dats_found)``; a dat that fails to
    parse is skipped and not listed."""
    paths, dats, seen = [], [], set()
    for dat in GAME_DATS:
        dat_path = os.path.join(game_root, 'data', dat)
        if not os.path.isfile(dat_path):
            continue
        try:
            ides = resolve_paths(game_root, parse_gta_dat(dat_path)).ide_paths
        except Exception as e:
            print(f"[INU] {dat}: {e!r}")
            continue
        dats.append(dat)
        for p in ides:
            key = os.path.normcase(os.path.normpath(p))
            if key not in seen:
                seen.add(key)
                paths.append(p)
    return paths, dats


def _dat_archive_lines(game_root: str, dat_names, keyword: str,
                       cut_at_ipl: bool) -> list[str]:
    """``keyword`` lines (IMG / CDIMAGE) of data/<dat_names>, in file order,
    resolved like resolve_paths. EXIT ends a file (CFileLoader::LoadLevel).
    ``cut_at_ipl``: the game reads the archive directories at the first IPL
    line of each file (SA CStreaming::Init2, VC CStreaming::Init) — lines
    after the last such point are registered but never read, so dropped."""
    regs, cut = [], None
    for name in dat_names:
        dat_path = os.path.join(game_root, 'data', name)
        if not os.path.isfile(dat_path):
            continue
        seen_ipl = False
        with open(dat_path, 'r', encoding='utf-8', errors='replace') as f:
            for raw_line in f:
                parts = raw_line.strip().split(None, 1)
                if not parts or parts[0].startswith('#'):
                    continue
                word = parts[0].upper()
                if word == 'EXIT':
                    break
                if word == 'IPL' and cut_at_ipl and not seen_ipl:
                    seen_ipl, cut = True, len(regs)
                elif word == keyword and len(parts) == 2:
                    regs.append(os.path.normpath(os.path.join(
                        game_root, parts[1].strip().replace('\\', '/'))))
    return regs if cut is None else regs[:cut]


def img_load_order(game_root: str) -> list[str]:
    """IMG archives the game streams from, highest priority first: a name
    found in several archives is taken from the first one listed. Paths are
    resolved like resolve_paths (the file may be missing), one per file.
    The game is told by data/: gta.dat → SA, gta_vc.dat → VC, gta3.dat → III,
    none of them → [].

    SA: models/gta3.img, models/gta_int.img (CStreaming::InitImageList
    0x4083C0), then IMG lines of default.dat and gta.dat (CGame::Initialise
    0x53BC80 loads only these two). CStreaming::LoadCdDirectory 0x5B82C0
    walks them forward and keeps the first registration of a name.
    III/VC: models/gta3.img (Game.cpp), then CDIMAGE lines of default.dat
    and gta3.dat / gta_vc.dat. re3/reVC LoadCdDirectory walks them backwards
    (`while(i-- >= 1)`): the LAST registered archive wins, gta3.img loses.
    SA and VC read the directories at the first IPL line (LoadLevel
    0x5B9030, reVC FileLoader.cpp) — archive lines below it are never read;
    III reads them after both .dat files (re3 Game.cpp), all lines count.
    Not modelled: VC/III MODELS\\TXD.IMG (added only for cards without DXT).
    """
    data = os.path.join(game_root, 'data')
    if os.path.isfile(os.path.join(data, 'gta.dat')):
        regs = [os.path.normpath(os.path.join(game_root, 'models', n))
                for n in ('gta3.img', 'gta_int.img')]
        regs += _dat_archive_lines(game_root, ('default.dat', 'gta.dat'),
                                   'IMG', cut_at_ipl=True)
    else:
        main = next((n for n in ('gta_vc.dat', 'gta3.dat')
                     if os.path.isfile(os.path.join(data, n))), None)
        if main is None:
            return []
        regs = [os.path.normpath(os.path.join(game_root, 'models', 'gta3.img'))]
        regs += _dat_archive_lines(game_root, ('default.dat', main), 'CDIMAGE',
                                   cut_at_ipl=(main == 'gta_vc.dat'))
        regs.reverse()
    out, seen = [], set()
    for p in regs:
        key = os.path.normcase(p)
        if key not in seen:          # a second registration of the same file
            seen.add(key)
            out.append(p)
    return out


def order_archives(paths, game_root: str) -> list[str]:
    """``paths`` (IMG archives, repeats of one file dropped) sorted in the
    game's load order (img_load_order) — take a name found in several from
    the first archive. Archives the game doesn't read (not in its .dat
    files), and all of them when ``game_root`` isn't a folder, go last,
    alphabetically."""
    def key(p):
        return os.path.normcase(os.path.abspath(p))
    order = []
    if game_root and os.path.isdir(game_root):
        try:
            order = img_load_order(game_root)
        except OSError:
            order = []
    rank = {}
    for i, p in enumerate(order):
        rank.setdefault(key(p), i)
    out, seen = [], set()
    for p in paths:
        k = key(p)
        if k not in seen:
            seen.add(k)
            out.append(p)
    return sorted(out, key=lambda p: (rank.get(key(p), len(order)), p.lower()))


def dat_game(game_root: str):
    """'SA' / 'VC' / 'III' by the main .dat in <game_root>/data — gta.dat,
    gta_vc.dat, gta3.dat, checked like img_load_order; None when there is
    none (img_load_order is then [], order_archives alphabetical). Tells
    III from VC, whose IMG archives are alike (VER1 + .dir)."""
    if not game_root:
        return None
    data = os.path.join(game_root, 'data')
    for name, game in (('gta.dat', 'SA'), ('gta_vc.dat', 'VC'),
                       ('gta3.dat', 'III')):
        if os.path.isfile(os.path.join(data, name)):
            return game
    return None


def list_ide_files(folder: str) -> list[str]:
    """Return .ide file paths to scan under ``folder``.

    If ``folder`` looks like a game root (has ``data/gta.dat`` or
    ``data/gta_int.dat``) → use the canonical gta.dat list (fast, only the
    IDEs the game actually loads). Otherwise → recursively scan the folder
    for ``*.ide``. This lets the user point at the whole game OR at a tighter
    folder (fewer files = faster search)."""
    has_dat = (os.path.isfile(os.path.join(folder, 'data', 'gta.dat'))
               or os.path.isfile(os.path.join(folder, 'data', 'gta_int.dat')))
    if has_dat:
        try:
            return [p for p in find_all_resources(folder).ide_paths
                    if os.path.isfile(p)]
        except Exception:
            pass
    out = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith('.ide'):
                out.append(os.path.join(root, f))
    return out


def extract_regions(info: GtaDatInfo) -> list[str]:
    """Extract unique region folder names from IPL paths.
    E.g. 'DATA\\MAPS\\LA\\LAe.IPL' → 'LA'
    Returns sorted list of region names."""
    regions = set()
    for p in info.ipl_paths:
        # Normalize and split path
        parts = p.replace('\\', '/').upper().split('/')
        # Look for MAPS/<region>/<file> pattern
        for i, part in enumerate(parts):
            if part == 'MAPS' and i + 2 < len(parts):
                region = parts[i + 1]
                if region not in ('GENERIC',):  # skip generic
                    regions.add(region)
                break
    return sorted(regions)
