# INU_tools.data.id_manager — Model ID allocation and tracking
#
# Presets: IDs are stored as individual .txt files under `data/id_presets/`.
# The caller picks the active preset via `set_active_preset(name)`; all
# subsequent allocate/release/load/save operations run against that file.
# A legacy `data/model_ids.txt` (single-file layout from earlier versions)
# is auto-migrated into `id_presets/default.txt` on first access.
#
# File format (one ID per line):
#   Free IDs are plain numbers; used IDs carry a `-modelname` suffix.
#     3500
#     3501-tatar_str_2817_1
#     3502-LODtatar_str_2817_1
#     3503
#
# IDs of the game's own models («Из игры») are also listed in a sidecar
# `<preset>.game` (one ID per line — the same file the Max port writes, so
# preset folders stay interchangeable). «Освободить фантомы», «Очистить
# всё» and «Очистить выделенные» keep those IDs used: a freed vanilla ID
# would be handed out again, and a second IDE line with the same ID makes
# the engine overwrite the game's model info.
#
# Operators work through `Preset` — the preset is read and written once per
# operation, not once per handed-out ID.

import os
import re
import shutil

# Presets live in the addon's USER data directory — never inside the
# addon directory itself, which installs read-only and must not be
# written to (extensions.blender.org rule):
#     <user data>/id_presets/<name>.txt   (see tools/user_data.py)
#
# The legacy ``<addons>/INU_Preset/id_presets/`` layout is migrated into
# this location by ``tools/user_data.migrate_legacy_inu_preset()`` at
# register time — this module no longer reads or writes the addon folder.
from ..tools.user_data import get_user_data_dir


def _presets_dir() -> str:
    return get_user_data_dir('id_presets')

_DEFAULT_PRESET = 'default'
_active_preset = _DEFAULT_PRESET


# ── Presets ──────────────────────────────────────────────────────────

def _sanitize(name: str) -> str:
    """Return a filename-safe preset name (letters/digits/dash/underscore/dot/space)."""
    name = (name or '').strip()
    name = re.sub(r'[^\w.\- ]+', '_', name)
    return name or _DEFAULT_PRESET


def preset_name(name: str) -> str:
    """The name a new / renamed preset gets — exactly as list_presets()
    shows it (the preset selector only accepts listed names); '' if the
    name can't be one. A leading '_' is dropped (list_presets hides such
    files), a name of dots only is refused (no usable file name)."""
    s = _sanitize(name).lstrip('_ ')
    return s if s.strip('.') else ''


def _ensure_presets_dir():
    """Guarantee the user-data presets directory exists.

    The legacy ``<addons>/INU_Preset/id_presets/`` layout is migrated to
    this location by ``tools/user_data.migrate_legacy_inu_preset()`` at
    register time. This helper never touches the addon directory itself —
    extensions install read-only and writing there can break them.
    """
    _presets_dir()  # get_user_data_dir() creates the directory


def set_active_preset(name: str) -> None:
    """Select the preset used by subsequent load/save calls."""
    global _active_preset
    _active_preset = _sanitize(name) if name else _DEFAULT_PRESET


def get_active_preset() -> str:
    return _active_preset


def list_presets() -> list:
    """Return the sorted list of preset names (without .txt extension)."""
    _ensure_presets_dir()
    try:
        files = os.listdir(_presets_dir())
    except Exception:
        return []
    names = []
    for fn in files:
        low = fn.lower()
        if not low.endswith('.txt') or fn.startswith('_'):
            continue
        names.append(os.path.splitext(fn)[0])
    names.sort(key=lambda s: s.lower())
    if _DEFAULT_PRESET not in names:
        # Ensure a default preset always shows up so the dropdown isn't empty.
        names.insert(0, _DEFAULT_PRESET)
    return names


def _preset_path(name: str = None) -> str:
    _ensure_presets_dir()
    safe = _sanitize(name if name is not None else _active_preset)
    return os.path.join(_presets_dir(), safe + '.txt')


def _game_path(name: str = None) -> str:
    """`<preset>.game` — IDs used by the game («Из игры»), next to the .txt."""
    _ensure_presets_dir()
    safe = _sanitize(name if name is not None else _active_preset)
    return os.path.join(_presets_dir(), safe + '.game')


def create_preset(name: str, copy_from: str = None) -> bool:
    """Create a new empty preset, optionally duplicating another preset's IDs."""
    _ensure_presets_dir()
    safe = _sanitize(name)
    if not safe:
        return False
    dst = os.path.join(_presets_dir(), safe + '.txt')
    if os.path.isfile(dst):
        return False
    try:        # a .game left by a .txt deleted by hand is not this preset's
        os.remove(_game_path(safe))
    except OSError:
        pass
    try:
        if copy_from:
            src = os.path.join(_presets_dir(), _sanitize(copy_from) + '.txt')
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                # the copy keeps the source's game IDs protected too
                if os.path.isfile(_game_path(copy_from)):
                    try:
                        shutil.copy2(_game_path(copy_from), _game_path(safe))
                    except OSError as e:
                        print(f"[INU] ID preset copy, {safe}.game: {e!r}")
                return True
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(f'# GTA SA model ID preset: {safe}\n')
        return True
    except Exception:
        return False


def delete_preset(name: str) -> bool:
    """Delete a preset file. The `default` preset cannot be removed."""
    safe = _sanitize(name)
    if safe == _DEFAULT_PRESET:
        return False
    path = os.path.join(_presets_dir(), safe + '.txt')
    if not os.path.isfile(path):
        return False
    try:
        os.remove(path)
    except Exception:
        return False
    try:
        os.remove(_game_path(safe))
    except OSError:
        pass
    return True


def rename_preset(old: str, new: str) -> bool:
    old_safe = _sanitize(old)
    new_safe = _sanitize(new)
    if old_safe == new_safe:
        return False
    src = os.path.join(_presets_dir(), old_safe + '.txt')
    dst = os.path.join(_presets_dir(), new_safe + '.txt')
    if not os.path.isfile(src) or os.path.isfile(dst):
        return False
    try:
        os.rename(src, dst)
    except Exception:
        return False
    try:
        if os.path.isfile(_game_path(old_safe)):
            os.replace(_game_path(old_safe), _game_path(new_safe))
        else:       # a stale .game under the new name is not this preset's
            os.remove(_game_path(new_safe))
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"[INU] ID preset rename, {old_safe}.game: {e!r}")
    return True


# ── Storage (current active preset) ──────────────────────────────────

def _load(name=None):
    """Load ID list from the active preset (or preset ``name``). Returns list of (id, model_name_or_None)."""
    entries = []
    path = _preset_path(name)
    if not os.path.isfile(path):
        return entries
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '-' in line:
                    parts = line.split('-', 1)
                    try:
                        id_num = int(parts[0].strip())
                        model = parts[1].strip()
                        entries.append((id_num, model if model else None))
                    except ValueError:
                        continue
                else:
                    try:
                        id_num = int(line)
                        entries.append((id_num, None))
                    except ValueError:
                        continue
    except Exception:
        pass
    return entries


def _write_atomic(path, text):
    """Write through a temp file + os.replace: a crash or a full disk
    mid-write can't leave a half-written preset behind."""
    tmp = path + '.inu_tmp'
    try:
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _save(entries, name=None):
    """Save ID list to the active preset (or preset ``name``), preserving any header comment lines."""
    path = _preset_path(name)
    header_lines = []
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped[0].isdigit():
                    break
                header_lines.append(line.rstrip('\n'))

    out = [h + '\n' for h in header_lines]
    for id_num, model in sorted(entries, key=lambda x: x[0]):
        if model:
            out.append(f"{id_num}-{model}\n")
        else:
            out.append(f"{id_num}\n")
    _write_atomic(path, ''.join(out))


def game_ids(name=None):
    """IDs used by the game («Из игры») — the `<preset>.game` sidecar."""
    out = set()
    try:
        with open(_game_path(name), 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if s.isascii() and s.isdigit():
                    out.add(int(s))
    except FileNotFoundError:
        pass
    return out


def save_game_ids(name, ids):
    """Write `<preset>.game` (same format as the Max port)."""
    _write_atomic(_game_path(name),
                  "# INU: IDs used by the game (From Game)\n"
                  + "".join(f"{i}\n" for i in sorted(ids)))


def get_free_ids():
    """Return list of free (unassigned) IDs."""
    protected = game_ids()
    return [id_num for id_num, name in _load()
            if name is None and id_num not in protected]


def get_used_ids():
    """Return dict of used IDs: {id_num: model_name}."""
    return {id_num: name for id_num, name in _load() if name is not None}


def get_all():
    """Return all entries as list of (id, name_or_None)."""
    return _load()


class Preset:
    """A preset held in memory for one operation: read once, written once
    by ``save()`` (the module functions below used to load and rewrite the
    whole ~20k-line file for every handed-out ID).

    Port of the Max ``id_presets.Preset`` — same files, same rules.
    ``game`` = IDs from `<preset>.game`: ``gc`` / ``clear_all`` keep them.
    """

    def __init__(self, name=None):
        self.name = _sanitize(name if name is not None else _active_preset)
        self.entries = _load(self.name)
        self._idx = {}                       # ID → positions in entries (duplicates — several)
        for k, (i, _n) in enumerate(self.entries):
            self._idx.setdefault(i, []).append(k)
        self.game = game_ids(self.name)
        self._game0 = set(self.game)
        self.changed = False

    # — queries —
    def used(self):
        return {i: n for i, n in self.entries if n}

    def ids(self):
        return set(self._idx)

    def is_free(self, i):
        """The ID is in the preset and none of its lines is taken."""
        pos = self._idx.get(i)
        return (i not in self.game and bool(pos)
                and not any(self.entries[k][1] for k in pos))

    # — changes —
    def _append(self, i, name):
        self._idx.setdefault(i, []).append(len(self.entries))
        self.entries.append((i, name))
        self._order = None
        self.changed = True

    def _set(self, i, name):
        pos = self._idx.get(i)
        if not pos:
            self._append(i, name)
            return
        for k in pos:
            self.entries[k] = (i, name)
        if name is None:
            self._order = None          # freed — search from the start again
        self.changed = True

    _order = None

    def allocate(self, name, skip, prefer=None, restart=False):
        """First free ID in ascending order (not in ``skip``) → taken by
        ``name``. ``prefer`` goes first if it is free. None — no free IDs.
        Searches with a cursor over the sorted IDs (within one operation
        ``skip`` only grows). Set ``restart`` when a caller exempts its
        own collision ID from skip, making an earlier slot available."""
        skip = skip or ()
        if prefer is not None and prefer not in skip and self.is_free(prefer):
            self._set(prefer, name)
            return prefer
        if self._order is None:
            self._order = sorted(self._idx)
            self._cur = 0
        k = 0 if restart else self._cur
        while k < len(self._order):
            i = self._order[k]
            if i not in skip and self.is_free(i):
                self._set(i, name)
                self._cur = k + 1
                return i
            k += 1
        self._cur = k
        return None

    def reserve(self, i, name):
        """The ID is taken by ``name`` (overwrites the name; appended if missing)."""
        pos = self._idx.get(i)
        if not pos or any(self.entries[k][1] != name for k in pos):
            self._set(i, name)

    def release(self, i, free_game=False):
        """Free a slot; game IDs require the explicit, confirmed action."""
        if i in self.game:
            if not free_game:
                return False
            self.game.remove(i)
            self._set(i, None)
            return True
        if any(self.entries[k][1] for k in self._idx.get(i, ())):
            self._set(i, None)
            return True
        return False

    def gc(self, scene_ids):
        """Free phantoms: used IDs no scene object holds → free (game IDs
        stay). Returns how many were freed."""
        n = 0
        for i in list(self.used()):
            if i not in scene_ids and i not in self.game:
                self._set(i, None)
                n += 1
        return n

    def clear_all(self):
        """Clear All: every used ID → free (game IDs stay). Returns the count."""
        n = 0
        for i in list(self.used()):
            if i not in self.game:
                self._set(i, None)
                n += 1
        return n

    def fill(self, first=321, last=19999):
        """Create ID: the missing IDs first..last are added as free; used
        ones stay. Returns how many were added."""
        have = self.ids()
        add = [i for i in range(first, last + 1) if i not in have]
        for i in add:
            self._append(i, None)
        return len(add)

    def extend(self, count):
        """``count`` free IDs after the highest one. Returns (first, last)."""
        top = max(self.ids()) if self.entries else 320
        start = top + 1
        for i in range(start, start + count):
            self._append(i, None)
        return start, start + count - 1

    def mark_game(self, game):
        """From Game: {ID: game model name} → used by those names and
        remembered as game IDs. Returns (clashes, added): clashes =
        [(ID, your name, game name)] for IDs the preset held under another
        name; added = game IDs that were free or missing before."""
        clashes, added = [], 0
        cur = self.used()
        have = self.ids()
        for i, gname in sorted(game.items()):
            old = cur.get(i)
            if old and old.lower() != gname.lower() and i not in self.game:
                clashes.append((i, old, gname))
            if not old:
                added += 1
            if old != gname or i not in have:
                self._set(i, gname)
        self.game |= set(game)
        return clashes, added

    def save(self):
        """Write the .txt / .game only if they changed."""
        if self.changed:
            _save(self.entries, self.name)
            self.changed = False
        if self.game != self._game0:
            save_game_ids(self.name, self.game)
            self._game0 = set(self.game)


def allocate_id(model_name, skip=None):
    """Take first free ID, assign model_name, save. Returns ID or None.

    ``skip`` is an optional iterable of IDs to treat as unavailable
    even though the preset still lists them as free. Callers pass the
    set of IDs already claimed by scene objects so allocation steps
    over them WITHOUT writing every scene ID into the preset — the
    latter floods the manager's "used" list with map-imported IDs the
    user never assigned (see id_manager_ops.auto_assign).
    Operators handing out many IDs use one ``Preset`` instead.
    """
    P = Preset()
    new_id = P.allocate(model_name, set(skip) if skip else ())
    if new_id is not None:
        P.save()
    return new_id


def reserve_id(model_id, model_name):
    """Mark ``model_id`` as used (with ``model_name``) in the active preset.

    If the ID isn't present in the preset, the entry is appended so the
    preset stays in sync with the scene. If the slot is already taken by
    a different name, the name is overwritten — the scene is the source
    of truth for what's currently placed on the map.

    Returns True if a write happened, False if the slot was already in
    that exact state.
    """
    P = Preset()
    P.reserve(model_id, model_name)
    if not P.changed:
        return False
    P.save()
    return True


def gc_preset(objects):
    """Release preset entries whose IDs no object in ``objects`` claims.

    Handles the "I cleared everything but the gaps won't go away" case:
    the preset is the source of truth for allocation, and when it keeps
    a name on a slot that no scene object actually uses (e.g. the
    corresponding mesh was deleted long ago, or the slot was leaked by
    a Shift+D duplicate that later got its ID reassigned), that slot
    stays "used" forever and ``allocate_id`` keeps skipping past it.
    IDs used by the game (`.game`, «Из игры») are kept: no scene object
    holds them, yet handing them out again duplicates a vanilla ID.

    Returns the number of slots that were freed.
    """
    scene_ids = set()
    for obj in objects:
        inu = getattr(obj, 'inu', None)
        if inu is None:
            continue
        mid = getattr(inu, 'model_id', 0) or 0
        if mid > 0:
            scene_ids.add(mid)

    P = Preset()
    released = P.gc(scene_ids)
    P.save()
    return released


def sync_scene_to_preset(objects):
    """Pull every ``obj.inu.model_id > 0`` into the active preset.

    Without this, objects imported from the map (or hand-edited) hold
    IDs that the preset has never heard of. The *Assign IDs from…*
    operator then silently skips around those IDs because it sees them
    used in the scene, while the preset keeps showing them as free —
    producing the mysterious gaps users see in the preset file.

    Returns the number of preset slots that were updated.
    """
    entries = _load()
    by_id = {id_num: i for i, (id_num, _name) in enumerate(entries)}

    updated = 0
    appended = []
    for obj in objects:
        inu = getattr(obj, 'inu', None)
        if inu is None:
            continue
        mid = getattr(inu, 'model_id', 0) or 0
        if mid <= 0:
            continue
        name = obj.name
        idx = by_id.get(mid)
        if idx is None:
            appended.append((mid, name))
            updated += 1
            continue
        cur_id, cur_name = entries[idx]
        if cur_name is None:
            entries[idx] = (cur_id, name)
            updated += 1

    if appended:
        entries.extend(appended)
    if updated:
        _save(entries)
    return updated


def allocate_ids(requests, skip=None):
    """Several IDs at once, all or nothing (Export Map). ``requests`` =
    [(model_name, prefer)] in order: ``prefer`` (an ID or None — the caller
    has checked it against its own skip) is taken when the preset lists it
    free, else the first free ID not in ``skip``. The preset is read once
    and written once — or not at all when it runs out of free IDs (then
    None). Returns the IDs in request order. One ``Preset``: free by its
    rules (an ID with a taken duplicate line is not free)."""
    skip = set(skip) if skip else set()
    P = Preset()
    out = []
    for model_name, prefer in requests:
        if prefer is not None and P.is_free(prefer):
            P.reserve(prefer, model_name)
            nid = prefer
        else:
            nid = P.allocate(model_name, skip)
            if nid is None:
                return None
        skip.add(nid)
        out.append(nid)
    P.save()
    return out


def release_id(model_id, free_game=False):
    """Release an ID (remove model name, keep ID as free)."""
    P = Preset()
    if not P.release(model_id, free_game=free_game):
        return False
    P.save()
    return True


def clear_all():
    """Clear all assignments in the active preset (IDs become free) —
    except IDs used by the game («Из игры», `.game`). Returns how many
    were freed."""
    P = Preset()
    n = P.clear_all()
    P.save()
    return n


def get_file_path():
    """Return path to the current active preset file."""
    return _preset_path()


def create_id_file(max_id=19999):
    """Fill the active preset with IDs 321..max_id: missing ones are added
    as free, used ones (yours and the game's) stay — wiping them would hand
    vanilla IDs out again. Returns how many IDs were added."""
    P = Preset()
    n = P.fill(321, max_id)
    P.save()
    return n


def extend_ids(count=1000):
    """Add more free IDs after the current maximum. Returns (new_start, new_end)."""
    P = Preset()
    new_start, new_end = P.extend(count)
    P.save()
    return new_start, new_end


def populate_from_game(game_root):
    """«Из игры»: read every IDE the game loads — data/default.dat
    (vehicles, peds, weapons) plus gta.dat / gta_int.dat (SA), gta_vc.dat
    (VC) or gta3.dat (III) — mark those IDs used by the game's model names
    in the active preset and remember them in `<preset>.game`.

    Returns None if ``game_root/data`` has none of those .dat files, else a
    dict: count (game IDs), added (of them, free or missing in the preset
    before), clashes [(ID, your name, game name)], n_ide (IDE files read),
    dats (the .dat files read), bad (.dat / IDE files missing or unreadable).
    """
    from ..core.gta_dat import GAME_DATS, game_ide_paths
    from ..core.ide import read_ide

    paths, dats = game_ide_paths(game_root)
    # a .dat that is there but failed to parse (locked, no rights) is not in
    # ``dats`` — its IDs stay unprotected, so the report must name it
    bad_dats = [d for d in GAME_DATS if d not in dats
                and os.path.isfile(os.path.join(game_root, 'data', d))]
    if not dats and not bad_dats:
        return None
    game, bad = {}, []  # id -> model_name, basenames not read
    for p in paths:
        if not os.path.isfile(p):
            bad.append(os.path.basename(p))
            continue
        try:
            ide = read_ide(p)
        except Exception:
            bad.append(os.path.basename(p))
            continue
        for sec in (ide.objects, ide.anims, ide.cars, ide.peds, ide.weaps, ide.hiers):
            for e in sec:
                game[int(e.model_id)] = str(e.model_name)

    P = Preset()
    clashes, added = P.mark_game(game)
    P.save()
    return dict(count=len(game), added=added, clashes=clashes,
                n_ide=len(paths) - len(bad), dats=dats, bad=bad_dats + bad)
