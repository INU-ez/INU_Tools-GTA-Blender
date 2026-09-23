"""mapsync — reliable IDE / IPL synchronisation (no Blender dependency).

* :mod:`.ipl_doc` — ``inst`` rows found by content (:class:`Anchor`), LOD rows
  followed through ``lod_index``, every ``lod_index`` recomputed on commit.
* :mod:`.ide_doc` — ``objs``/``tobj`` rows keyed by id, guarded by name.
* :mod:`.textfile` — byte-exact line storage, atomic write, one ``.bak`` per
  file per session.

Typical use::

    doc = IplDoc.load(path)
    ed = doc.editor(game='SA')
    ed.reserve(anchor_of_other_object)          # rows other objects own
    res = ed.place(tag, dff_inst, anchor=old_anchor, lod=lod_inst)
    ed.remove(tag2, anchor2)
    new = ed.commit()                           # TextLines
    if not dry_run:
        new.write(path)
    res.index, res.inst, res.lod_index          # stamp these back
"""

from .textfile import TextLines, write_atomic, backup_path
from .ipl_doc import (Anchor, IplDoc, IplEditor, IplBinaryError, PlaceResult,
                      RemoveResult, Message, ANCHOR_TOL, RELINK_TOL, MATCH_TOL)
from .ide_doc import IdeDoc, IdeEditor, IdeResult

__all__ = [
    'TextLines', 'write_atomic', 'backup_path',
    'Anchor', 'IplDoc', 'IplEditor', 'IplBinaryError', 'PlaceResult',
    'RemoveResult', 'Message', 'ANCHOR_TOL', 'RELINK_TOL', 'MATCH_TOL',
    'IdeDoc', 'IdeEditor', 'IdeResult',
]
