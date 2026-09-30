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
  ``lod_index`` points at in the file. VC/III rows have no ``lod_index`` —
  there it is the LOD model's row standing at the model's spot.
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
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..ipl import (IplInstance, _format_inst_line, _parse_inst_line, _tokens,
                   is_lod_name, strip_lod_marker)
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


# Status «В IPL / координаты разошлись»: the scene placement against the
# anchor it last wrote. Anchors are parsed back from 6-decimal text and kept
# in float32 props, so the check needs a tolerance, not equality.
POS_EPS = 1e-4
ROT_EPS = 1e-5


def pos_close(a, b, eps: float = POS_EPS) -> bool:
    return all(abs(x - y) <= eps for x, y in zip(a, b))


def rot_close(q, ref, eps: float = ROT_EPS) -> bool:
    """Same rotation (x, y, z, w): both normalized (a file may hold 4-digit
    quaternions), q and −q are one rotation. A zero quaternion never is."""
    nq = sum(c * c for c in q) ** 0.5
    nr = sum(c * c for c in ref) ** 0.5
    if nq < 1e-9 or nr < 1e-9:
        return False
    q = [c / nq for c in q]
    ref = [c / nr for c in ref]
    if sum(x * y for x, y in zip(q, ref)) < 0.0:
        q = [-c for c in q]
    return all(abs(x - y) <= eps for x, y in zip(q, ref))


def inst_drifted(inst: IplInstance, anchor: 'Anchor') -> bool:
    """True when *inst* (what «Add» would write now) is not the row *anchor*
    last wrote: position, or rotation when the anchor has one."""
    if not pos_close((inst.pos_x, inst.pos_y, inst.pos_z), anchor.pos):
        return True
    return (anchor.rot is not None and not rot_close(
        (inst.rot_x, inst.rot_y, inst.rot_z, inst.rot_w), anchor.rot))


def _is_lod_of(lod_name: str, name: str) -> bool:
    """III/VC pair a model with its LOD by name (FindRelatedModel: equal
    after the first 3 characters); «LOD<name>» is the addon's own spelling."""
    lo, nm = lod_name.lower(), name.lower()
    if lo == nm or not is_lod_name(lod_name):
        return False
    return ((len(lo) > 3 and lo[3:] == nm[3:])
            or strip_lod_marker(lod_name).lower() == nm)


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
        self._lod_grid = None             # 1 m cell -> LOD-named file rows
        self._detached: set = set()       # ids of rows detach_lod() unlinked
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

    def _lod_rows_near(self, pos):
        """File rows with a LOD name in the 1 m cells around *pos*."""
        if self._lod_grid is None:
            self._lod_grid = {}
            for r in self.rows:
                if (r.line is None or r.inst is None
                        or not is_lod_name(r.inst.model_name)):
                    continue
                try:
                    key = (int(r.inst.pos_x // 1), int(r.inst.pos_y // 1))
                except (ValueError, OverflowError):
                    continue
                self._lod_grid.setdefault(key, []).append(r)
        try:
            cx, cy = int(pos[0] // 1), int(pos[1] // 1)
        except (ValueError, OverflowError):
            return
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                yield from self._lod_grid.get((cx + dx, cy + dy), ())

    def _lod_taken(self, row: Row, r: Row, d2: float) -> bool:
        """LOD row *r* belongs to other placements of *row*'s model: as many
        of them (still without a LOD) stand as close to it as *row* (*d2*)
        as there are free rows of that LOD at its spot."""
        p = (r.inst.pos_x, r.inst.pos_y, r.inst.pos_z)
        lim = max(d2, ANCHOR_TOL * ANCHOR_TOL)
        others = sum(1 for o in self._by_mid.get(int(row.cur.model_id), ())
                     if o is not row and not o.deleted and o.lod is None
                     and id(o) not in self._detached
                     and _dist2(o.cur, p) <= lim)
        if not others:
            return False
        free = sum(1 for o in self._by_mid.get(int(r.inst.model_id), ())
                   if not o.deleted and id(o) not in self.claimed
                   and id(o) not in self.reserved
                   and _dist2(o.inst, p) <= ANCHOR_TOL * ANCHOR_TOL)
        return others >= free

    def _lod_by_content(self, row: Row,
                        lod: Optional[IplInstance] = None) -> Optional[Row]:
        """VC/III rows have no lod_index, so their LOD row is found by content:
        a free row of *lod*'s model where *row* stands in the file (a new row:
        where *lod* goes), else a row the game pairs with *row* by name.
        A row nearer to another placement of the same model is left to it."""
        spot = row.inst if row.line is not None else None
        if lod is not None:
            for s, tol in ((spot, MATCH_TOL), (lod, ANCHOR_TOL)):
                if s is None:
                    continue
                r = self._find(Anchor(int(lod.model_id), lod.model_name,
                                      (s.pos_x, s.pos_y, s.pos_z)), tol)
                if r is not None and s is spot and self._lod_taken(
                        row, r, _dist2(r.inst, (s.pos_x, s.pos_y, s.pos_z))):
                    r = None    # a nearer placement of the model owns it
                if r is not None and s is lod and any(
                        o is not row and not o.deleted and _dist2(
                            o.cur, (r.inst.pos_x, r.inst.pos_y, r.inst.pos_z))
                        <= ANCHOR_TOL * ANCHOR_TOL
                        for o in self._by_mid.get(int(row.cur.model_id), ())):
                    r = None    # another placement stands there: its LOD
                if r is not None:
                    return r
        if spot is None:
            return None
        p = (spot.pos_x, spot.pos_y, spot.pos_z)
        best, best_d = None, MATCH_TOL * MATCH_TOL
        for r in self._lod_rows_near(p):
            if (r.deleted or id(r) in self.claimed or id(r) in self.reserved
                    or int(r.inst.model_id) == int(spot.model_id)
                    or not _is_lod_of(r.inst.model_name, spot.model_name)):
                continue
            d2 = _dist2(r.inst, p)
            if d2 <= best_d and not self._lod_taken(row, r, d2):
                best, best_d = r, d2
        return best

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

        *lod* None keeps whatever LOD link the row already has. An existing
        III/VC row keeps its own scale — the game doesn't apply it (re3/reVC
        LoadObjectInstance); a new row gets *dff*'s."""
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
            # III/VC scale: the row's own (SA rows parse as 1.0, not written).
            if row.inst is not None:
                new.scale_x, new.scale_y, new.scale_z = (
                    row.inst.scale_x, row.inst.scale_y, row.inst.scale_z)
            row.new_inst = new
            res.action = 'update'
        self.claimed.add(id(row))
        res._row = row

        if lod is not None:
            lod_new = copy.copy(lod)
            lod_new.lod_index = -1
            cur = row.lod
            if cur is None and row.style != 'SA':
                cur = self._lod_by_content(row, lod_new)
            if (cur is not None and not cur.deleted and cur.inst is not None
                    and id(cur) not in self.claimed
                    and id(cur) not in self.reserved
                    and self._refcount(cur, excluding=row) == 0):
                # Same LOD model already there: keep its own spelling of the
                # name (vanilla LODs aren't always «LOD<base>»).
                if int(cur.inst.model_id) == int(lod_new.model_id):
                    lod_new.model_name = cur.inst.model_name
                # q and −q are one rotation: keep the row's own sign.
                n, c = lod_new, cur.inst
                if (n.rot_x * c.rot_x + n.rot_y * c.rot_y
                        + n.rot_z * c.rot_z + n.rot_w * c.rot_w) < 0:
                    n.rot_x, n.rot_y, n.rot_z, n.rot_w = (
                        -n.rot_x, -n.rot_y, -n.rot_z, -n.rot_w)
                # III/VC scale: the row's own (the game doesn't apply it).
                lod_new.scale_x, lod_new.scale_y, lod_new.scale_z = (
                    cur.inst.scale_x, cur.inst.scale_y, cur.inst.scale_z)
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
        lod = row.lod
        if with_lod and lod is None and row.style != 'SA':
            lod = self._lod_by_content(row)
            if lod is not None:
                self.claimed.add(id(lod))   # not the LOD of the next removal
        if with_lod and lod is not None:
            self._lod_candidates.append((res, lod))
        res.removed = True
        res._row = row
        self.removes.append(res)
        return res

    def detach_lod(self, tag, anchor: Anchor) -> RemoveResult:
        """Unlink a placement from its LOD and drop the LOD row if unused."""
        res = RemoveResult(tag)
        row = self._find(anchor, ANCHOR_TOL)
        if row is None:
            self.messages.append(Message(
                'WARNING', "«{0}»: строка не найдена в файле — удалять нечего",
                anchor.model_name or anchor.model_id, tag=tag))
            self.removes.append(res)
            return res
        self.claimed.add(id(row))      # a stacked twin's anchor takes the other row
        self._detached.add(id(row))    # its LOD isn't left to it (_lod_taken)
        lod = row.lod
        if lod is None and row.style != 'SA':
            lod = self._lod_by_content(row)     # VC/III: no lod_index column
        if lod is None or lod.deleted:
            self.messages.append(Message(
                'INFO', "«{0}»: у строки нет LOD — отвязывать нечего",
                anchor.model_name or anchor.model_id, tag=tag))
            self.removes.append(res)
            return res
        self._lod_candidates.append((res, lod))
        self.claimed.add(id(lod))
        if row.lod is not None:        # SA: the model row loses its lod_index
            row.new_inst = copy.copy(row.cur)
            row.lod = None
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


_F32 = struct.Struct('<f')


def _same_number(x: float, y: float) -> bool:
    """Numbers the game can't tell apart: within the %.6f step of
    _format_inst_line (1e-6: 14.1015625 is written 14.101562; float32
    2796.9453125 is written 2796.945312 where R* wrote 2796.945313), or the
    same float32 — CFileLoader reads inst/objs with sscanf("%f"). Whole
    numbers (id, interior, lod_index, flags) must match exactly: past 2^24
    two of them share a float32."""
    if abs(x - y) <= 1e-6:
        return True
    if x.is_integer() and y.is_integer():
        return False
    try:
        return _F32.unpack(_F32.pack(x)) == _F32.unpack(_F32.pack(y))
    except (OverflowError, struct.error):
        return False


def _same_values(a: str, b: str) -> bool:
    """True when two inst lines carry the same numbers (formatting aside)."""
    pa, pb = _tokens(a), _tokens(b)
    if len(pa) != len(pb):
        return False
    for x, y in zip(pa, pb):
        if x == y:
            continue
        try:
            fx, fy = float(x), float(y)
        except ValueError:
            if x.lower() != y.lower():
                return False
            continue
        if not _same_number(fx, fy):
            return False
    return True
