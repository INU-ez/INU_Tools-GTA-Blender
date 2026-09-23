"""Line-preserving text file I/O for IDE / IPL sync.

Everything the sync layer doesn't deliberately change must survive a write
byte-for-byte: comments, blank lines, unknown sections (``path``, ``mult``…),
the file's own float formatting and line endings. So files are kept as a list
of raw lines (each with its own ending) and only the touched lines are
replaced.

Encoding: game text files are mostly ASCII, sometimes cp1251/latin-1 comments.
Decoding with ``surrogateescape`` round-trips any byte sequence exactly. A
UTF-8 BOM is kept aside and re-emitted, so the first section header is still
recognised.

Writes are atomic (temp file in the same folder + ``os.replace``) and the
first write of a file in a session leaves ``<file>.bak`` next to it.

No Blender dependency.
"""

from __future__ import annotations

import os
import tempfile
from typing import List, Optional

_BOM = '﻿'

# Files already backed up in this process (normcased abs paths) — the .bak is
# the state BEFORE the first sync write of the session, not before the last.
_backed_up: set = set()


class TextLines:
    """Raw lines of a text file, each keeping its own line ending."""

    def __init__(self, lines: Optional[List[str]] = None, *,
                 newline: str = '\r\n', bom: bool = False):
        self.lines: List[str] = list(lines or [])
        self.newline = newline
        self.bom = bom

    # ── construction ──
    @classmethod
    def from_text(cls, text: str) -> 'TextLines':
        bom = text.startswith(_BOM)
        if bom:
            text = text[1:]
        parts = text.split('\n')
        lines = [p + '\n' for p in parts[:-1]]
        if parts[-1]:
            lines.append(parts[-1])          # last line without a newline
        crlf = sum(1 for ln in lines if ln.endswith('\r\n'))
        lf = sum(1 for ln in lines if ln.endswith('\n')) - crlf
        newline = '\n' if lf > crlf else '\r\n'
        return cls(lines, newline=newline, bom=bom)

    @classmethod
    def read(cls, path: str) -> 'TextLines':
        with open(path, 'rb') as f:
            data = f.read()
        return cls.from_text(data.decode('utf-8', errors='surrogateescape'))

    # ── helpers ──
    @staticmethod
    def content(line: str) -> str:
        """Line text without its ending, stripped."""
        return line.rstrip('\r\n').strip()

    def ending(self, line: str) -> str:
        if line.endswith('\r\n'):
            return '\r\n'
        if line.endswith('\n'):
            return '\n'
        return ''

    def make(self, text: str) -> str:
        """A new line in the file's newline style."""
        return text + self.newline

    def to_text(self) -> str:
        out = list(self.lines)
        # A last line without an ending would glue onto nothing — fine as is,
        # but make sure every line except the last has one.
        for k in range(len(out) - 1):
            if not out[k].endswith('\n'):
                out[k] += self.newline
        return (_BOM if self.bom else '') + ''.join(out)

    def write(self, path: str, *, backup: bool = True) -> None:
        write_atomic(path, self.to_text(), backup=backup)


def _key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def write_atomic(path: str, text: str, *, backup: bool = True) -> None:
    """Write *text* to *path* atomically; first write per session keeps .bak."""
    data = text.encode('utf-8', errors='surrogateescape')
    folder = os.path.dirname(os.path.abspath(path)) or '.'
    if backup and os.path.isfile(path) and _key(path) not in _backed_up:
        try:
            with open(path, 'rb') as src, open(path + '.bak', 'wb') as dst:
                dst.write(src.read())
            _backed_up.add(_key(path))
        except OSError:
            pass                      # a failed backup must not block the save
    fd, tmp = tempfile.mkstemp(prefix='.inu_', suffix='.tmp', dir=folder)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def backup_path(path: str) -> str:
    return path + '.bak'
