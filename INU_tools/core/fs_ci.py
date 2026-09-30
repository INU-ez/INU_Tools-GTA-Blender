"""Case-insensitive lookup of game files on case-sensitive file systems.

GTA's .dat files spell paths the Windows way ("MODELS\\GTA3.IMG",
"DATA\\MAPS\\LA\\LAn.ide") while the folder on disk may be "models/gta3.img".
Windows doesn't care; on Linux / macOS the literal path is missing.
resolve() returns the existing file whatever its letter case — for an
exact (or Windows) hit it is just the normalized path.

No Blender dependency — pure Python.
"""

from __future__ import annotations
import os


def resolve(path: str) -> str:
    """``path`` with separators normalized; when it doesn't exist as written,
    the existing file / folder whose name matches it case-insensitively,
    component by component (first match in sorted order). A path nothing
    matches is returned normalized, as written."""
    if not path:
        return path
    p = os.path.normpath(str(path).replace('\\', '/'))
    if os.path.exists(p):
        return p
    head, tail = p, []
    while not os.path.exists(head):
        parent, name = os.path.split(head)
        if not name or parent == head:
            return p
        tail.append(name)
        head = parent or os.curdir
    cur = head
    for name in reversed(tail):
        try:
            names = os.listdir(cur)
        except OSError:
            return p
        if name not in names:
            low = name.lower()
            name = next((n for n in sorted(names) if n.lower() == low), None)
            if name is None:
                return p
        cur = os.path.join(cur, name)
    return os.path.normpath(cur)


def path_key(path: str) -> str:
    """Identity of a game file for de-duplication, case-insensitive on every
    OS like the game itself: "MODELS\\GTA3.IMG" and "models/gta3.img" of one
    game folder are one file even before it exists on disk."""
    return os.path.normcase(os.path.abspath(resolve(path))).lower()
