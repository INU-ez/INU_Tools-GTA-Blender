"""IDE ``objs`` / ``tobj`` synchronisation — line-preserving, conflict-safe.

The model id is the key, but it is never trusted blindly: a row is only
overwritten when it belongs to the same model (same name, or the name the
object had when it was last written — a rename). An id already used by a
DIFFERENT model, or a model name already present under another id, is a
conflict: nothing is written for that object and the caller gets a message.
The old upsert replaced whatever row had the id — a wrong Model ID silently
destroyed someone else's definition.

Untouched lines stay byte-exact; ``tobj`` time columns and multi-mesh draw
distances of an updated row are kept.

No Blender dependency.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from typing import List, Optional

from ..ide import (IdeObject, _format_obj_line, _format_tobj_line,
                   _parse_obj_line, _tokens)
from .ipl_doc import Message
from .textfile import TextLines

IDE_SECTIONS = ('objs', 'tobj', 'anim', 'weap', 'cars', 'peds', 'hier',
                'txdp', '2dfx', 'path', 'tanm')
# Sections whose first column is a model id (one shared id space).
ID_SECTIONS = ('objs', 'tobj', 'anim', 'weap', 'cars', 'peds', 'hier', 'tanm')
OBJ_SECTIONS = ('objs', 'tobj')


class IdeRow:
    __slots__ = ('line', 'section', 'model_id', 'name', 'obj', 'text',
                 'new_text', 'deleted')

    def __init__(self, line, section, model_id, name, obj, text):
        self.line = line
        self.section = section
        self.model_id = model_id
        self.name = name
        self.obj = obj                  # IdeObject for objs/tobj, else None
        self.text = text
        self.new_text: Optional[str] = None
        self.deleted = False


class IdeDoc:
    def __init__(self, path: str = '', tl: Optional[TextLines] = None,
                 exists: bool = True):
        self.path = path
        self.exists = exists
        self.tl = tl or TextLines()
        self.rows: List[IdeRow] = []
        self.objs_end: Optional[int] = None     # line idx of last objs 'end'
        self._parse()

    @classmethod
    def load(cls, path: str) -> 'IdeDoc':
        if not os.path.isfile(path):
            return cls.new(path)
        return cls(path, TextLines.read(path), exists=True)

    @classmethod
    def from_text(cls, text: str, path: str = '') -> 'IdeDoc':
        return cls(path, TextLines.from_text(text), exists=True)

    @classmethod
    def new(cls, path: str = '') -> 'IdeDoc':
        tl = TextLines(newline='\r\n')
        tl.lines = [tl.make('objs'), tl.make('end')]
        return cls(path, tl, exists=False)

    def _parse(self):
        section = None
        for k, raw in enumerate(self.tl.lines):
            s = TextLines.content(raw)
            low = s.lower()
            if low in IDE_SECTIONS:
                # A new header also closes a section left without 'end'.
                if section == 'objs':
                    self.objs_end = k
                section = low
                continue
            if section is None:
                continue
            if low == 'end':
                if section == 'objs':
                    self.objs_end = k
                section = None
                continue
            if section not in ID_SECTIONS or not s or s.startswith('#'):
                continue
            parts = _tokens(s)
            try:
                mid = int(parts[0])
            except (ValueError, IndexError):
                continue
            name = parts[1] if len(parts) > 1 else ''
            obj = (_parse_obj_line(s, timed=(section == 'tobj'))
                   if section in OBJ_SECTIONS else None)
            self.rows.append(IdeRow(k, section, mid, name, obj, s))

    # ── queries ──
    def by_id(self, model_id: int) -> Optional[IdeRow]:
        for r in self.rows:
            if r.model_id == model_id and not r.deleted:
                return r
        return None

    def by_name(self, name: str) -> Optional[IdeRow]:
        low = (name or '').lower()
        for r in self.rows:
            if r.section in OBJ_SECTIONS and r.name.lower() == low and not r.deleted:
                return r
        return None

    def ids(self) -> set:
        return {r.model_id for r in self.rows}

    def editor(self, *, game: str = 'SA') -> 'IdeEditor':
        return IdeEditor(self, game=game)


@dataclass
class IdeResult:
    tag: object
    action: str = ''          # 'add' | 'update' | 'unchanged' | 'conflict' | 'same'
    entry: Optional[IdeObject] = None       # what the file now holds
    _row: Optional[IdeRow] = field(default=None, repr=False)


class IdeEditor:
    def __init__(self, doc: IdeDoc, *, game: str = 'SA'):
        self.doc = doc
        self.game = game if game in ('SA', 'VC', 'III') else 'SA'
        self.rows: List[IdeRow] = []
        for r in doc.rows:
            c = IdeRow(r.line, r.section, r.model_id, r.name,
                       copy.copy(r.obj) if r.obj else None, r.text)
            self.rows.append(c)
        self.appended: List[IdeRow] = []
        self.results: List[IdeResult] = []
        self.removed: List[object] = []
        self.messages: List[Message] = []
        self._written = {}          # id(row) -> IdeObject written this batch
        self._ids = {}              # model id → [rows]
        self._names = {}            # lower name → [objs/tobj rows]
        for r in self.rows:
            self._index(r)

    def _index(self, r):
        self._ids.setdefault(r.model_id, []).append(r)
        if r.section in OBJ_SECTIONS:
            self._names.setdefault(r.name.lower(), []).append(r)

    def _unindex(self, r):
        for d, k in ((self._ids, r.model_id), (self._names, r.name.lower())):
            lst = d.get(k)
            if lst and r in lst:
                lst.remove(r)

    def _by_id(self, mid):
        for r in self._ids.get(mid, ()):
            if not r.deleted:
                return r
        return None

    def _by_name(self, name):
        for r in self._names.get(name.lower(), ()):
            if not r.deleted:
                return r
        return None

    def _format(self, e: IdeObject, section: str) -> str:
        if section == 'tobj' and e.is_timed:
            return _format_tobj_line(e, game=self.game)
        return _format_obj_line(e, game=self.game)

    def write(self, tag, entry: IdeObject, *, anchor_id: int = 0,
              anchor_name: str = '') -> IdeResult:
        res = IdeResult(tag)
        e = copy.copy(entry)
        name_l = e.model_name.lower()
        anchor_l = (anchor_name or '').lower()

        row = self._by_id(e.model_id)
        if row is not None:
            if row.section not in OBJ_SECTIONS:
                return self._conflict(
                    res, "ID {0} уже занят в секции {1} («{2}») — «{3}» не "
                    "записана", e.model_id, row.section, row.name, e.model_name)
            if row.name.lower() not in (name_l, anchor_l):
                return self._conflict(
                    res, "ID {0} в файле занят другой моделью «{1}» — «{2}» не "
                    "записана. Проверь Model ID", e.model_id, row.name,
                    e.model_name)
        else:
            by_name = self._by_name(e.model_name)
            if by_name is not None:
                if anchor_id and by_name.model_id == anchor_id:
                    row = by_name           # the object's Model ID was changed
                    self.messages.append(Message(
                        'INFO', "«{0}»: ID изменён {1} → {2}", e.model_name,
                        anchor_id, e.model_id, tag=tag))
                else:
                    return self._conflict(
                        res, "«{0}» уже есть в файле с ID {1} — не записана "
                        "(поставь модели этот ID или удали ту строку)",
                        e.model_name, by_name.model_id)

        if row is not None and id(row) in self._written:
            # Several objects of one model in the batch (copies): one row.
            prev = self._written[id(row)]
            if (abs(prev.draw_distance - e.draw_distance) > 1e-6
                    or prev.flags != e.flags or prev.txd_name != e.txd_name):
                self.messages.append(Message(
                    'WARNING', "«{0}»: у копий разные параметры IDE — записаны "
                    "параметры первой", e.model_name, tag=tag))
            res.action, res.entry, res._row = 'same', prev, row
            self.results.append(res)
            return res

        if row is None:
            text = _format_obj_line(e, game=self.game)
            row = IdeRow(None, 'objs', e.model_id, e.model_name, e, text)
            row.new_text = text
            self.appended.append(row)
            self._index(row)
            res.action = 'add'
        else:
            old = row.obj
            if old is not None:
                if row.section == 'tobj' and old.is_timed:
                    e.time_on, e.time_off = old.time_on, old.time_off
                if old.extra_draw_distances and not e.extra_draw_distances:
                    e.extra_draw_distances = list(old.extra_draw_distances)
            text = self._format(e, row.section)
            if _same_values(text, row.text):
                res.action = 'unchanged'
            else:
                row.new_text = text
                res.action = 'update'
            self._unindex(row)
            row.model_id, row.name, row.obj = e.model_id, e.model_name, e
            self._index(row)
        self._written[id(row)] = e
        res.entry, res._row = e, row
        self.results.append(res)
        return res

    def _conflict(self, res, fmt, *args):
        res.action = 'conflict'
        self.messages.append(Message('WARNING', fmt, *args, tag=res.tag))
        self.results.append(res)
        return res

    def remove(self, tag, model_id: int, model_name: str = '', *,
               anchor_name: str = '') -> bool:
        row = self._by_id(model_id)
        if row is None:
            return False
        names = {n.lower() for n in (model_name, anchor_name) if n}
        if names and row.name.lower() not in names:
            self.messages.append(Message(
                'WARNING', "ID {0} в файле принадлежит «{1}», а не «{2}» — не "
                "удалено", model_id, row.name, model_name, tag=tag))
            return False
        row.deleted = True
        self.removed.append(tag)
        return True

    def commit(self) -> TextLines:
        tl = self.doc.tl
        by_line = {r.line: r for r in self.rows}
        app = [tl.make(r.new_text) for r in self.appended if not r.deleted]
        out = []
        for k, raw in enumerate(tl.lines):
            if k == self.doc.objs_end and app:
                if out and not out[-1].endswith('\n'):
                    out[-1] += tl.newline
                out.extend(app)
                app = []
            r = by_line.get(k)
            if r is None:
                out.append(raw)
            elif r.deleted:
                continue
            elif r.new_text is not None:
                out.append(r.new_text + (tl.ending(raw) or tl.newline))
            else:
                out.append(raw)
        if app:
            if out and not out[-1].endswith('\n'):
                out[-1] += tl.newline
            out += [tl.make('objs')] + app + [tl.make('end')]
        return TextLines(out, newline=tl.newline, bom=tl.bom)

    def counts(self) -> dict:
        c = {'add': 0, 'update': 0, 'unchanged': 0, 'conflict': 0, 'same': 0,
             'removed': len(self.removed)}
        for r in self.results:
            c[r.action] = c.get(r.action, 0) + 1
        return c

    def problems(self) -> List[Message]:
        return [m for m in self.messages if m.level in ('WARNING', 'ERROR')]


def _same_values(a: str, b: str) -> bool:
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
            if x != y:
                return False
    return True
