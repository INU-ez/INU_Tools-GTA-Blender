# INU_tools.core.model_classify — pure (bpy-free) DFF / LOD / COL classifier.
#
# Kept Blender-free so the layered model-type detection rules can be unit
# tested without a Blender session. tools.model_utils.get_model_type is a thin
# wrapper that pulls name / inu.type / materials off the object and calls in.
#
# LOD detection: strip reuses strip_lod_marker from core.ipl; the MATCH rule
# here is deliberately STRICTER than core.ipl.is_lod_name («lod» anywhere).
# The importer's substring rule is right for game data (des_damlodbit04), but
# scene objects are USER-named — bare substring would classify «explode_box» /
# «melody_hall» as LODs and mangle their export names. See _is_scene_lod_name.

import re

from .ipl import strip_lod_marker

# Defaults mirror scene_settings; the customisation UI was removed, so these
# are effectively the fixed markers that still work as a manual override.
DEFAULT_SUFFIXES = {'DFF': '_DFF', 'LOD': '_LOD', 'COL': '_COL'}
DEFAULT_PREFIXES = {'DFF': '', 'LOD': 'LOD', 'COL': ''}

# «lod» at a word edge: start/end of the name, or a non-letter neighbour
# (digit / _ / - / .). Catches lodfoo, foo_lod, nw_lodbit_26, oilderricklod01.
_SCENE_LOD_RE = re.compile(r'(?:^|[^a-z])lod|lod(?:[^a-z]|$)')


def _is_scene_lod_name(name):
    """LOD-name test for SCENE objects — stricter than core.ipl.is_lod_name.

    Accepts:
      * an explicit uppercase ``LOD`` marker anywhere (LODfoo, fooLOD,
        modeLODlaett — deliberate user/addon marking);
      * lowercase ``lod`` at a word edge (start/end or next to a non-letter):
        lodbush2b, bush_lod, nw_lodbit_26, oilderricklod01.

    Rejects lowercase ``lod`` buried between letters — that's how English
    words look (explode, melody, lodge), not LOD markers. Trade-off: rare
    vanilla names with letters on BOTH sides (des_damlodbit04) classify as
    DFF here; the map importer still links those authoritatively via the
    IPL lod_index cross-reference, and ``_LOD`` suffix stays as an override.
    """
    if 'LOD' in name:
        return True
    return _SCENE_LOD_RE.search(name.lower()) is not None


def explicit_name_type(name, suffixes=None, prefixes=None):
    """Tier 1 of classify_model on its own — the EXPLICIT name marker.

    Returns ``(model_type, base_name)`` when NAME carries a deliberate
    ``_SHA`` / suffix / prefix marker, else ``(None, name)``.

    Split out because export routing has to know whether the marker was
    deliberate: an ``inu.type`` COL/SHA tag diverts a mesh into embedded
    collision, and a stale tag on a ``*_LOD`` mesh used to write a DFF with an
    empty GeometryList — collision only, nothing to render in game. Tier 1
    outranks the tag here exactly as it does inside classify_model.
    """
    suffixes = suffixes or DEFAULT_SUFFIXES
    prefixes = prefixes or DEFAULT_PREFIXES
    name_upper = name.upper()

    # Shadow mesh (_SHA) → COL bucket (non-blocking shadow mesh in the .col).
    if name_upper.endswith('_SHA'):
        return 'COL', name[:-4]

    for mt in ('LOD', 'COL', 'DFF'):
        sfx = suffixes.get(mt, '') or ''
        sfx_upper = sfx.upper()
        if sfx_upper and name_upper.endswith(sfx_upper):
            return mt, name[:-len(sfx)]
        # No-separator marker (e.g. "modelCOL") — case-SENSITIVE on the
        # uppercase convention so «protocol» / «exploded» don't trip COL/DFF.
        bare = sfx_upper.lstrip('_. ')
        if bare and sfx_upper != bare and name.endswith(bare):
            return mt, name[:-len(bare)]
    for mt in ('COL', 'DFF'):     # LOD prefix is handled by is_lod_name below
        pfx = prefixes.get(mt, '') or ''
        pfx_upper = pfx.upper()
        if pfx_upper and name_upper.startswith(pfx_upper):
            return mt, name[len(pfx):]

    return None, name


def reuse_key(name):
    """Нормализованное имя модели для сверки «модель уже в сцене» (Import from
    IMG): без маркеров _DFF/_LOD/LOD, в нижнем регистре. Тип в ключ не входит —
    DFF и его LOD различаются ID, коллизия отсекается отдельно."""
    if not name:
        return ''
    m, b = explicit_name_type(name)
    if m in ('DFF', 'LOD'):
        m2, b2 = explicit_name_type(b)   # «xyz_DFF_LOD» (LOD без маркера в имени)
        if m2 in ('DFF', 'LOD'):
            b = b2
    return strip_lod_marker(b).lower()


def classify_model(name, *, has_texture=True, inu_type='OBJ',
                   suffixes=None, prefixes=None):
    """Classify a model NAME into ``LOD`` / ``COL`` / ``DFF`` and return
    ``(model_type, base_name)``.

    Layered, automatic — suffixes/prefixes survive only as a manual override:

      1. explicit ``_SHA`` / suffix / prefix marker on the name → that type;
      2. ``inu_type`` of COL/SHA (stamped by the COL importer / Batch Set Type)
         → COL — checked before the LOD rule so a tagged collision with an
         accidental «lod» in its name isn't misread as a LOD;
      3. a «lod» token at a word edge / uppercase LOD marker (see
         _is_scene_lod_name — строже импортёрского is_lod_name) → LOD;
      4. otherwise textured → DFF, untextured → COL.

    ``has_texture`` may be a bool OR a 0-arg callable — the callable is only
    evaluated if classification actually reaches the texture tier, so the
    (potentially expensive) material scan is skipped on a name/tag hit."""
    # ── 1. Explicit suffix / prefix override (see explicit_name_type) ──
    marker, base = explicit_name_type(name, suffixes, prefixes)
    if marker is not None:
        return marker, base

    # ── 2. Explicit object type (import / Batch Set Type) ──
    if inu_type in ('COL', 'SHA'):
        return 'COL', name

    # ── 3. «lod» token at a word edge / uppercase marker → LOD ──
    if _is_scene_lod_name(name):
        return 'LOD', strip_lod_marker(name)

    # ── 4. Texture heuristic for untagged meshes ──
    ht = has_texture() if callable(has_texture) else has_texture
    if not ht:
        return 'COL', name

    return 'DFF', name


def lod_has_own_txd(lod_txd, dff_txd):
    """У LOD-а свой TXD, а не TXD модели: не пустой и не совпадает с TXD
    модели (регистр и пробелы не важны). У ванильных LOD почти всегда свой —
    LODGSFreeway7_LAn → lanlod при lanroad модели; Export to IMG такой TXD
    LOD-у оставляет и кладёт его текстуры туда же."""
    lod = (lod_txd or '').strip().lower()
    dff = (dff_txd or '').strip().lower()
    return bool(lod) and lod != dff
