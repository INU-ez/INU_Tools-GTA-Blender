"""Which IDE row belongs to a scene model — the matching rule of «Sync from IDE».

* The model's own linked IDE first (the row with its name / the name it last
  wrote / ``lod`` + name, then its last Model ID). Skipped when the link is
  stale: the object's Model ID was changed after the link (a Shift+D copy
  renamed and given a new id must not snap back to the original's row).
  Also skipped when the link was recorded under ANOTHER model's name and a
  row with the object's own name AND its Model ID exists (vanilla III: the
  import links by id, and the unused data/maps/gta3.IDE shifts the ids —
  «Airportroad01» 3004 was linked to «3004, Airportroad05» of gta3.IDE).
* Otherwise every IDE of the game / list: by name, a LOD only to a LOD row,
  then by Model ID.
* One name under DIFFERENT ids in several IDEs (or one id under different
  names) is ambiguous — the game itself resolves such a clash by load order,
  so there is no «right» row. The row whose id equals the object's Model ID
  wins; otherwise nothing is linked and the caller reports it. The old rule
  «first file wins» silently gave the model another model's id (vanilla III:
  the unused data/maps/gta3.IDE re-numbered 591 models).

No Blender dependency.
"""

from __future__ import annotations

from ..ipl import is_lod_name, strip_lod_marker


def _name(e):
    return (getattr(e, 'model_name', '') or '').strip().lower()


def _base(nm):
    """Lower-case name without the LOD marker."""
    return strip_lod_marker(nm).lower() if is_lod_name(nm) else nm


def build_index(files):
    """*files*: iterable of ``(path, rows)`` (rows = IDE objs+tobj+anim
    entries; ``None`` for an unreadable file) → index for :func:`match_ide_row`.
    Every key keeps ALL ``(entry, path)`` pairs in file order."""
    by_id, by_name, lod_by_base = {}, {}, {}
    for fp, rows in files:
        for e in rows or ():
            by_id.setdefault(int(e.model_id), []).append((e, fp))
            nm = _name(e)
            if nm:
                by_name.setdefault(nm, []).append((e, fp))
                if is_lod_name(nm):
                    lod_by_base.setdefault(
                        strip_lod_marker(nm).lower(), []).append((e, fp))
    return {'by_id': by_id, 'by_name': by_name, 'lod_by_base': lod_by_base}


def unique(hits, mid):
    """``(hit, ambiguous)``. One model (one id AND one name) in any number of
    files → the first; otherwise the only model whose id is *mid*; otherwise
    ambiguous."""
    if not hits:
        return None, False
    if (len({int(e.model_id) for e, _fp in hits}) == 1
            and len({_name(e) for e, _fp in hits}) == 1):
        return hits[0], False
    if mid > 0:
        same = [h for h in hits if int(h[0].model_id) == mid]
        if same and len({_name(e) for e, _fp in same}) == 1:
            return same[0], False
    return None, True


def _search_all(index, cname, mid, is_lod):
    """Every IDE: by name (a LOD by its LOD row), then by *mid*."""
    by_name = index['by_name']
    if is_lod:
        hit, ambiguous = unique(by_name.get(cname, []) if is_lod_name(cname)
                                else by_name.get('lod' + cname, []), mid)
        if hit is None and not ambiguous:
            hit, ambiguous = unique(index['lod_by_base'].get(cname, []), mid)
    else:
        hit, ambiguous = unique(by_name.get(cname, []), mid)
    ambiguous = 'name' if ambiguous else False
    if hit is None and not ambiguous and mid > 0:
        hit, ambiguous = unique(index['by_id'].get(mid, []), mid)
        ambiguous = 'id' if ambiguous else False
    if hit is not None and is_lod_name(_name(hit[0])) != is_lod:
        hit = None                      # model ↔ LOD row: not a pair
    return hit, ambiguous


def match_ide_row(own, index, cname, last_name, last_id, mid, is_lod):
    """Row for one scene model → ``((entry, path) | None, ambiguous)``;
    *ambiguous*: ``False``, ``'name'`` (one name, different ids) or ``'id'``
    (one id, different names).

    *own* — :func:`build_index` of the model's linked IDE alone (``None`` =
    not linked / unreadable); *index* — of all IDEs; *cname* — model name
    without the LOD marker and the ``.001`` suffix; *last_name* / *last_id* —
    what the link last recorded; *mid* — the object's Model ID; *is_lod* —
    the object is a LOD."""
    cname = (cname or '').lower()
    last_name = (last_name or '').strip().lower()
    last_id = int(last_id or 0)
    mid = int(mid or 0)
    hit, ambiguous = _search_all(index, cname, mid, is_lod)
    stale = mid > 0 and last_id > 0 and mid != last_id
    if own is not None and not stale:
        if (last_name and mid > 0 and hit is not None
                and (_base(last_name) != cname
                     or is_lod_name(last_name) != is_lod)
                and int(hit[0].model_id) == mid
                and _base(_name(hit[0])) == cname):
            return hit, False           # the link is another model's row
        # current name, the name last written (a rename), LOD row of the name
        for nm in (cname, last_name, 'lod' + cname):
            if nm and nm != 'lod' and is_lod_name(nm) == is_lod:
                hits = own['by_name'].get(nm)
                if hits:
                    return hits[0], False
        want = last_id or mid
        for h in own['by_id'].get(want, []) if want > 0 else ():
            if is_lod_name(_name(h[0])) == is_lod:
                return h, False
    return hit, ambiguous
