"""IPL ``inst`` synchronisation — stateless, line-preserving.

Why this exists
---------------
The old «Add to IPL» remembered *line numbers* (a JSON sidecar next to the
.blend). Any delete, external edit or copied object made those numbers stale:
a model could be written over its own LOD row («only the LOD got added»), a
Shift+D copy borrowed the original's LOD row, and deleting rows shifted every
``lod_index`` below them.

How it works now
----------------
* Nothing positional is stored. An object remembers WHAT it last wrote — an
  :class:`Anchor` (model id, name, position, rotation). Before every write the
  row is found again by that content.
* A LOD row is never tracked on its own: it is whatever row the model row's
  ``lod_index`` points at in the file.
* While editing, ``lod_index`` values are held as references between row
  objects, not numbers. Deleting, appending, reordering can't break them; the
  final numbers are computed once, at :meth:`IplEditor.commit`.
* Rows nobody touched keep their original text byte-for-byte (comments,
  formatting, other sections too — see :mod:`.textfile`).

No Blender dependency.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..ipl import IplInstance, _format_inst_line, _parse_inst_line, _tokens
from .textfile import TextLines

IPL_SECTIONS = ('inst', 'cull', 'path', 'grge', 'enex', 'pick', 'jump',
                'tcyc', 'auzo', 'mult', 'cars', 'occl', 'zone')

# Anchors are stored from values parsed back from the written line, so a
# genuine match is exact; the tolerance only absorbs float round-trips.
ANCHOR_TOL = 0.01
# Fallback when the exact row is gone (file edited by hand / in MEd): the
# nearest free row of the same model within this distance is taken over.
RELINK_TOL = 2.0
# Linking a scene object that was never written by us (imported, dragged in).
MATCH_TOL = 0.5


class IplBinaryError(Exception):
    """Binary (``bnry``) IPL — streamed from an IMG, not editable as text."""


@dataclass
class Anchor:
    """What an object last wrote to / read from its IPL row."""
    model_id: int
    model_name: str = ''
    pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rot: Optional[Tuple[float, float, float, float]] = None   # x, y, z, w

    @classmethod
    def of(cls, inst: IplInstance) -> 'Anchor':
        return cls(int(inst.model_id), inst.model_name,
                   (inst.pos_x, inst.pos_y, inst.pos_z),
                   (inst.rot_x, inst.rot_y, inst.rot_z, inst.rot_w))


# ── row / document ─────────────────────────────────────────────────────

def _row_style(text: str) -> Tuple[str, bool]:
    """(game layout, has FLA 12th column) of an existing inst line."""
    parts = _tokens(text)
    n = len(parts)
    if n == 13:
        return 'VC', False
    if n == 12:
        if '.' in parts[2]:
            return 'III', False
        return 'SA', True
    return 'SA', False


class Row:
    """One data line of an ``inst`` section (comments/blank lines excluded).

    ``line`` — index in the file's line list (None for a row appended in this
    edit). ``lod`` — the row this one's lod_index points at (object ref)."""

    __slots__ = ('line', 'inst', 'text', 'style', 'fla', 'lod',
                 'orig_lod', 'new_inst', 'deleted')

    def __init__(self, line, inst, text, style='SA', fla=False):
        self.line = line
        self.inst = inst            # IplInstance | None (unparseable line)
        self.text = text            # original content (no ending)
        self.style = style
        self.fla = fla
        self.lod: Optional['Row'] = None
        self.orig_lod = -1
        self.new_inst: Optional[IplInstance] = None
        self.deleted = False

    @property
    def cur(self) -> Optional[IplInstance]:
        return self.new_inst if self.new_inst is not None else self.inst


def _dist2(inst: IplInstance, pos) -> float:
    return ((inst.pos_x - pos[0]) ** 2 + (inst.pos_y - pos[1]) ** 2
            + (inst.pos_z - pos[2]) ** 2)


def _rot_diff(inst: IplInstance, rot) -> float:
    if rot is None:
        return 0.0
    d = abs(inst.rot_x * rot[0] + inst.rot_y * rot[1]
            + inst.rot_z * rot[2] + inst.rot_w * rot[3])
    return 1.0 - min(d, 1.0)


class IplDoc:
    """A parsed text IPL that remembers its raw lines."""

    def __init__(self, path: str = '', tl: Optional[TextLines] = None,
                 exists: bool = True):
        self.path = path
        self.exists = exists
        self.tl = tl or TextLines()
        self.rows: List[Row] = []
        self.inst_end: Optional[int] = None     # line idx of last inst 'end'
        self._parse()

    # ── loading ──
    @classmethod
    def load(cls, path: str) -> 'IplDoc':
        if not os.path.isfile(path):
            return cls.new(path)
        with open(path, 'rb') as f:
            head = f.read(4)
        if head == b'bnry':
            raise IplBinaryError(path)
        return cls(path, TextLines.read(path), exists=True)

    @classmethod
    def from_text(cls, text: str, path: str = '') -> 'IplDoc':
        return cls(path, TextLines.from_text(text), exists=True)

    @classmethod
    def new(cls, path: str = '') -> 'IplDoc':
        """Empty IPL with the standard section skeleton (as write_ipl)."""
        tl = TextLines(newline='\r\n')
        for sec in ('inst', 'cull', 'path', 'grge', 'enex', 'pick', 'cars',
                    'jump', 'tcyc', 'auzo', 'mult', 'occl'):
            tl.lines += [tl.make(sec), tl.make('end')]
        return cls(path, tl, exists=False)

    def _parse(self):
        section = None
        for k, raw in enumerate(self.tl.lines):
            s = TextLines.content(raw)
            low = s.lower()
            if section is None:
                if low in IPL_SECTIONS:
                    section = low
                continue
            if low == 'end':
                if section == 'inst':
                    self.inst_end = k
                section = None
                continue
            if section != 'inst' or not s or s.startswith('#'):
                continue
            inst = _parse_inst_line(s)
            style, fla = _row_style(s)
            row = Row(k, inst, s, style, fla)
            if inst is not None:
                row.orig_lod = int(inst.lod_index)
            self.rows.append(row)
        n = len(self.rows)
        self._by_mid = {}
        for i, row in enumerate(self.rows):
            if row.inst is not None:
                self._by_mid.setdefault(int(row.inst.model_id), []).append(i)
                if 0 <= row.orig_lod < n:
                    row.lod = self.rows[row.orig_lod]

    # ── queries (index-based, on the file as loaded) ──
    @property
    def instances(self) -> List[Optional[IplInstance]]:
        return [r.inst for r in self.rows]

    def rows_of(self, model_id: int) -> List[int]:
        """Indices of the rows of one model."""
        return list(self._by_mid.get(int(model_id), ()))

    def has_fla(self) -> bool:
        return any(r.fla for r in self.rows)

    def find(self, anchor: Anchor, exclude=(), tol: float = ANCHOR_TOL) -> int:
        """Row index whose content matches *anchor*, or -1."""
        best, best_key = -1, None
        t2 = tol * tol
        for i in self._by_mid.get(int(anchor.model_id), ()):
            r = self.rows[i]
            if i in exclude:
                continue
            d2 = _dist2(r.inst, anchor.pos)
            if d2 > t2:
                continue
            name_miss = bool(anchor.model_name) and (
                r.inst.model_name.lower() != anchor.model_name.lower())
            key = (name_miss, _rot_diff(r.inst, anchor.rot) > 1e-4, d2)
            if best_key is None or key < best_key:
                best, best_key = i, key
        return best

    def nearest(self, model_id: int, pos, exclude=(), max_dist: float = MATCH_TOL,
                name: str = '') -> int:
        """Nearest row of *model_id* within *max_dist*, or -1."""
        best, best_d = -1, max_dist * max_dist
        for i in self._by_mid.get(int(model_id), ()):
            r = self.rows[i]
            if i in exclude:
                continue
            if name and r.inst.model_name.lower() != name.lower():
                continue
            d2 = _dist2(r.inst, pos)
            if d2 <= best_d:
                best, best_d = i, d2
        return best

    def editor(self, *, game: str = 'SA', fla: Optional[bool] = None) -> 'IplEditor':
        return IplEditor(self, game=game, fla=fla)


# ── requests / results ─────────────────────────────────────────────────

@dataclass
class PlaceResult:
    tag: object
    action: str = ''          # 'add' | 'update' | 'unchanged'
    lod_action: str = ''      # '' | 'add' | 'update' | 'unchanged' | 'kept'
    relinked: bool = False    # found by proximity, not by exact anchor
    index: int = -1           # final row index (after commit)
    inst: Optional[IplInstance] = None       # final written values
    lod_index: int = -1
    lod_inst: Optional[IplInstance] = None
    _row: Optional[Row] = field(default=None, repr=False)
    _lod_row: Optional[Row] = field(default=None, repr=False)


@dataclass
class RemoveResult:
    tag: object
    removed: bool = False
    lod_removed: bool = False
    _row: Optional[Row] = field(default=None, repr=False)


class Message:
    """A note for the user. ``fmt`` is a Russian template with ``{0}``… slots
    (the addon's T() translates it), ``args`` fill them; ``text`` is the
    untranslated result."""

    __slots__ = ('level', 'fmt', 'args', 'tag')

    def __init__(self, level: str, fmt: str, *args, tag=None):
        self.level = level        # 'INFO' | 'WARNING' | 'ERROR'
        self.fmt = fmt
        self.args = args
        self.tag = tag

    @property
    def text(self) -> str:
        return self.fmt.format(*self.args)

    def __repr__(self):
        return f"Message({self.level!r}, {self.text!r})"


# ── editor ─────────────────────────────────────────────────────────────

class IplEditor:
    """Batch of place / remove operations on one IPL, applied by commit()."""

    def __init__(self, doc: IplDoc, *, game: str = 'SA',
                 fla: Optional[bool] = None):
        self.doc = doc
        self.game = game if game in ('SA', 'VC', 'III') else 'SA'
        self.fla = doc.has_fla() if fla is None else bool(fla or doc.has_fla())
        # Work on copies so a discarded plan leaves the document untouched.
        self.rows: List[Row] = []
        remap = {}
        for r in doc.rows:
            c = Row(r.line, copy.copy(r.inst) if r.inst else None, r.text,
                    r.style, r.fla)
            c.orig_lod = r.orig_lod
            remap[id(r)] = c
            self.rows.append(c)
        for r, c in zip(doc.rows, self.rows):
            c.lod = remap.get(id(r.lod)) if r.lod is not None else None
        self._by_mid = {}
        for c in self.rows:
            if c.inst is not None:
                self._by_mid.setdefault(int(c.inst.model_id), []).append(c)
        self.claimed: set = set()      # ids of rows used by this batch
        self.reserved: set = set()     # ids of rows owned by other objects
        self.places: List[PlaceResult] = []
        self.removes: List[RemoveResult] = []
        self.messages: List[Message] = []
        self._lod_candidates: list = []   # (RemoveResult, Row)
        self._committed = False

    # ── lookup on the live (edited) rows ──
    def _live(self):
        return [r for r in self.rows if not r.deleted]

    def _find(self, anchor: Anchor, tol: float) -> Optional[Row]:
        best, best_key = None, None
        t2 = tol * tol
        for r in self._by_mid.get(int(anchor.model_id), ()):
            if (r.deleted or r.line is None
                    or id(r) in self.claimed or id(r) in self.reserved):
                continue
            d2 = _dist2(r.inst, anchor.pos)
            if d2 > t2:
                continue
            name_miss = bool(anchor.model_name) and (
                r.inst.model_name.lower() != anchor.model_name.lower())
            key = (name_miss, _rot_diff(r.inst, anchor.rot) > 1e-4, d2)
            if best_key is None or key < best_key:
                best, best_key = r, key
        return best

    def _refcount(self, target: Row, *, excluding: Optional[Row] = None) -> int:
        return sum(1 for r in self.rows
                   if not r.deleted and r is not excluding and r.lod is target)

    def _append(self, inst: IplInstance) -> Row:
        row = Row(None, inst, '', self.game, self.fla)
        self.rows.append(row)
        return row

    # ── public operations ──
    def reserve(self, anchor: Anchor) -> bool:
        """Mark the row of an object NOT in this batch as taken, so nothing
        in the batch can be matched onto it. Returns True if found."""
        r = self._find(anchor, ANCHOR_TOL)
        if r is None:
            return False
        self.reserved.add(id(r))
        return True

    def place(self, tag, dff: IplInstance, *, anchor: Optional[Anchor] = None,
              lod: Optional[IplInstance] = None) -> PlaceResult:
        """Add or update one placement (and its LOD row when *lod* is given).

        *lod* None keeps whatever LOD link the row already has."""
        res = PlaceResult(tag)
        row = None
        if anchor is not None:
            row = self._find(anchor, ANCHOR_TOL)
            if row is None:
                row = self._find(anchor, RELINK_TOL)
                if row is not None:
                    res.relinked = True
                    self.messages.append(Message(
                        'INFO', "«{0}»: строка в файле была изменена вручную — "
                        "найдена рядом и обновлена", dff.model_name, tag=tag))
                else:
                    self.messages.append(Message(
                        'WARNING', "«{0}»: прежняя строка в файле не найдена "
                        "(удалена или правилась вручную) — добавлена заново",
                        dff.model_name, tag=tag))
        new = copy.copy(dff)
        if row is None:
            row = self._append(new)
            res.action = 'add'
        else:
            row.new_inst = new
            res.action = 'update'
        self.claimed.add(id(row))
        res._row = row

        if lod is not None:
            lod_new = copy.copy(lod)
            lod_new.lod_index = -1
            cur = row.lod
            if (cur is not None and not cur.deleted and cur.inst is not None
                    and id(cur) not in self.claimed
                    and id(cur) not in self.reserved
                    and self._refcount(cur, excluding=row) == 0):
                # Same LOD model already there: keep its own spelling of the
                # name (vanilla LODs aren't always «LOD<base>»).
                if int(cur.inst.model_id) == int(lod_new.model_id):
                    lod_new.model_name = cur.inst.model_name
                cur.new_inst = lod_new
                res.lod_action = 'update'
            else:
                cur = self._append(lod_new)
                res.lod_action = 'add'
            row.lod = cur
            self.claimed.add(id(cur))
            res._lod_row = cur
        elif row.lod is not None and not row.lod.deleted:
            res.lod_action = 'kept'
            res._lod_row = row.lod
        self.places.append(res)
        return res

    def remove(self, tag, anchor: Anchor, *, tol: float = ANCHOR_TOL,
               with_lod: bool = True) -> RemoveResult:
        """Delete a placement row; its LOD row goes too unless still used."""
        res = RemoveResult(tag)
        row = self._find(anchor, tol)
        if row is None:
            self.messages.append(Message(
                'WARNING', "«{0}»: строка не найдена в файле — удалять нечего",
                anchor.model_name or anchor.model_id, tag=tag))
            self.removes.append(res)
            return res
        row.deleted = True
        self.claimed.add(id(row))
        if with_lod and row.lod is not None:
            self._lod_candidates.append((res, row.lod))
        res.removed = True
        res._row = row
        self.removes.append(res)
        return res

    def detach_lod(self, tag, anchor: Anchor) -> RemoveResult:
        """Unlink a placement from its LOD and drop the LOD row if unused."""
        res = RemoveResult(tag)
        row = self._find(anchor, ANCHOR_TOL)
        if row is None or row.lod is None:
            self.removes.append(res)
            return res
        self._lod_candidates.append((res, row.lod))
        row.new_inst = copy.copy(row.cur)
        row.lod = None
        self.claimed.add(id(row))
        res._row = row
        self.removes.append(res)
        return res

    # ── commit ──
    def commit(self) -> TextLines:
        """Resolve deletions and lod_index numbers; return the new file."""
        if self._committed:
            raise RuntimeError("IplEditor.commit() called twice")
        self._committed = True

        # 1) LOD rows of removed models — only when no surviving row still
        #    points at them and nothing in this batch re-used them.
        for owner, lod in self._lod_candidates:
            if lod.deleted:
                owner.lod_removed = True
                continue
            if self._refcount(lod) == 0 and not any(
                    p._lod_row is lod or p._row is lod for p in self.places):
                lod.deleted = True
                owner.lod_removed = True

        # 2) Surviving rows that pointed at a deleted row lose their LOD.
        orphaned = 0
        for r in self.rows:
            if not r.deleted and r.lod is not None and r.lod.deleted:
                r.lod = None
                orphaned += 1
        if orphaned:
            self.messages.append(Message(
                'WARNING', "{0} строк(и) ссылались на удалённый LOD — их "
                "lod_index сброшен в -1", orphaned))

        live = self._live()
        pos = {id(r): i for i, r in enumerate(live)}

        # 3) Final text of every row.
        new_text = {}
        for r in live:
            if r.inst is None and r.new_inst is None:
                continue                                    # unparseable: as is
            inst = copy.copy(r.cur)
            if r.style == 'SA':
                inst.lod_index = pos[id(r.lod)] if r.lod is not None else -1
            if r.line is not None and r.new_inst is None \
                    and inst.lod_index == r.orig_lod:
                continue                                    # untouched row
            text = _format_inst_line(inst, fla_extended=r.fla, game=r.style)
            if r.line is not None and _same_values(text, r.text):
                continue                                    # same numbers
            new_text[id(r)] = text

        # 4) Results.
        for p in self.places:
            r = p._row
            p.index = pos[id(r)]
            p.inst = _parse_inst_line(new_text.get(id(r), r.text)) or r.cur
            if r.line is not None and id(r) not in new_text and p.action == 'update':
                p.action = 'unchanged'
            lr = r.lod
            if lr is not None and not lr.deleted:
                p.lod_index = pos[id(lr)]
                p.lod_inst = _parse_inst_line(new_text.get(id(lr), lr.text)) or lr.cur
                if (p.lod_action == 'update' and lr.line is not None
                        and id(lr) not in new_text):
                    p.lod_action = 'unchanged'

        # 5) Emit lines.
        return self._emit(live, new_text)

    def _emit(self, live, new_text) -> TextLines:
        tl = self.doc.tl
        by_line = {r.line: r for r in self.rows if r.line is not None}
        out = []
        appended = [r for r in live if r.line is None]
        app_lines = [tl.make(new_text[id(r)]) for r in appended]
        for k, raw in enumerate(tl.lines):
            if k == self.doc.inst_end and app_lines:
                if out and not out[-1].endswith('\n'):
                    out[-1] += tl.newline
                out.extend(app_lines)
                app_lines = []
            r = by_line.get(k)
            if r is None:
                out.append(raw)
                continue
            if r.deleted:
                continue
            if id(r) in new_text:
                out.append(new_text[id(r)] + (tl.ending(raw) or tl.newline))
            else:
                out.append(raw)
        if app_lines:                               # file had no inst section
            head = [tl.make('inst')] + app_lines + [tl.make('end')]
            out = head + out
        return TextLines(out, newline=tl.newline, bom=tl.bom)

    # ── summary ──
    def counts(self) -> dict:
        c = {'add': 0, 'update': 0, 'unchanged': 0, 'lod_add': 0,
             'lod_update': 0, 'removed': 0, 'lod_removed': 0}
        for p in self.places:
            c[p.action] = c.get(p.action, 0) + 1
            if p.lod_action in ('add', 'update'):
                c['lod_' + p.lod_action] += 1
        for r in self.removes:
            c['removed'] += int(r.removed)
            c['lod_removed'] += int(r.lod_removed)
        return c

    def problems(self) -> List[Message]:
        return [m for m in self.messages if m.level in ('WARNING', 'ERROR')]


def _same_values(a: str, b: str) -> bool:
    """True when two inst lines carry the same numbers (formatting aside)."""
    pa, pb = _tokens(a), _tokens(b)
    if len(pa) != len(pb):
        return False
    for x, y in zip(pa, pb):
        if x == y:
            continue
        try:
            if abs(float(x) - float(y)) > 5e-7:
                return False
        except ValueError:
            if x.lower() != y.lower():
                return False
    return True
