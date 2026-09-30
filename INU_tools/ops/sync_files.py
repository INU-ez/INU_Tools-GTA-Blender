# INU_tools.ops.sync_files — which files a «Sync from …» run reads.
#
# No Blender dependency (tested with plain pytest).

import os


def merge_targets(front, game, picked):
    """*front* (the panel list «… для экспорта») + *game* (the game's files)
    + *picked* (the file chosen in the box, always last). Duplicates (case /
    slashes) collapse onto the first occurrence; empty entries are ignored.
    Returns ``(valid, missing)``: existing files / paths that are gone."""
    raw = [p for p in list(front) + list(game) + ([picked] if picked else [])
           if p]
    valid, missing, seen = [], [], set()
    for p in raw:
        k = os.path.normcase(os.path.normpath(p))
        if k in seen:
            continue
        seen.add(k)
        (valid if os.path.isfile(p) else missing).append(p)
    return valid, missing
