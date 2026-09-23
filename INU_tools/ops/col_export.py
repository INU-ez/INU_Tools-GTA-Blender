# INU_tools.ops.col_export
# Blender mesh objects → COL collision file.
# Uses INU_tools.core.col for binary format writing.

import math
import bpy
import bmesh
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper

from .. import T
from ..core.col import (
    ColModel, ColFace, ColSphere, ColBox, Bounds, Vec3, Surface,
    write_col_file, write_col,
)
from ..core import game_versions


def _resolve_col_version(context=None) -> int:
    """Pick the COL file version for export from the scene's active
    game (gtatools_game). Falls back to 3 (SA COL3) when context is
    unavailable. Centralised so every caller — operator, IMG bulk
    export, INU Export, map export — uses the same dispatch.
    """
    if context is None:
        try:
            import bpy as _bpy
            context = _bpy.context
        except Exception:
            return 3
    scene = getattr(context, 'scene', None)
    if scene is None:
        return 3
    game = game_versions.game_of_scene(scene)
    return game_versions.profile_for(game).col_version


# Findings of the last operator run (cleared by the operator, filled by
# ``audit_col`` for every record it writes) — the operator surfaces them
# after the files are on disk, like DFF_EXPORT_WARNINGS.
COL_EXPORT_FATAL = []
COL_EXPORT_WARNINGS = []


def _resolve_target_game(context=None) -> str:
    """The game the scene exports for ('III' / 'VC' / 'SA') — what the
    surface-ID clamp in ``write_col`` is keyed on (W3: the COL version
    cannot tell, SA ships COL2 archives with SA surface IDs)."""
    if context is None:
        try:
            import bpy as _bpy
            context = _bpy.context
        except Exception:
            return 'SA'
    scene = getattr(context, 'scene', None)
    if scene is None:
        return 'SA'
    try:
        return game_versions.game_of_scene(scene)
    except Exception:
        return 'SA'


def audit_col(models, filepath: str = '', target_game: str = ''):
    """Check ColModels against what the engine's collision loaders and
    CCollision assume without checking.

    ``core.col_lint.check_col_models`` mirrors LoadCollisionModel/Ver2/Ver3
    and the consumers: a face index past the vertex block, more than
    32767 faces, a surface id past the 179-row table, a coordinate past
    ±255.99 or a name without room for its NUL give garbage collision or
    crash the game instead of just looking wrong.

    ``target_game`` applies the same surface-ID clamp ``write_col`` will
    (in place, idempotent) *before* the lint, so a COL-18 id is reported
    as what the file gets — "clamped to 0" — rather than as a crash the
    writer then averts.

    Returns ``(fatal, warnings)`` — ready-to-show strings, also printed
    to the console the way the DFF audits are.
    """
    from ..core.col_lint import check_col_models
    warnings = []
    if target_game:
        from ..core.col import _clamp_surfaces_for_target
        for model in models:
            n = _clamp_surfaces_for_target(model, target_game)
            if n:
                warnings.append(T(
                    "COL «{0}»: {1} поверхностей с id вне таблицы {2} — в файл записан 0 (COL-18)."
                ).format(model.model_name, n, target_game))
    fatal, lint_warnings = check_col_models(models)
    warnings.extend(lint_warnings)
    COL_EXPORT_FATAL.extend(fatal)
    COL_EXPORT_WARNINGS.extend(warnings)
    tag = f" ({filepath})" if filepath else ""
    for item in fatal:
        print(f"[COL Export] ИГРА УПАДЁТ{tag}: {item}")
    for item in warnings:
        print(f"[COL Export]{tag} {item}")
    return fatal, warnings


def _auto_light_settings():
    """Read the scene's auto collision-light setting.

    Returns ``(enabled, value)``. Kam's CST exporter hard-writes a face
    light byte of 78 (day≈15 / night 4) so collision is lit in-game;
    INU mirrors that by filling faces whose light byte is 0 (no COL
    material / unconfigured) with a configurable default. Returns
    ``(False, 0)`` when no scene is available (e.g. unit tests) so the
    behaviour is opt-in to a live Blender session only.
    """
    try:
        scn = bpy.context.scene
        st = scn.inu_settings
        return bool(getattr(st, 'gtatools_col_auto_light', False)), \
            int(getattr(st, 'gtatools_col_auto_light_value', 78))
    except Exception:
        return False, 0


def _draw_col_auto_light(layout, context):
    """Shared UI block for the auto collision-light setting — used by the
    COL and CST export dialogs and the N-panel so the control looks the
    same everywhere."""
    st = getattr(context.scene, 'inu_settings', None)
    if st is None:
        return
    box = layout.box()
    box.prop(st, 'gtatools_col_auto_light', text=T("Авто-свет коллизии"))
    row = box.row()
    row.enabled = st.gtatools_col_auto_light
    row.prop(st, 'gtatools_col_auto_light_value', text=T("Значение"))


def _vec3(v) -> Vec3:
    """Convert any (x,y,z) to Vec3."""
    return Vec3(v[0], v[1], v[2])


def _get_surface_from_material(mat, target_game: str = '') -> Surface:
    """Read collision surface properties from a Blender material.

    When ``target_game`` is set and the material was imported from a
    different game (``inu.col_source_game`` recorded the source),
    route the surface ID through ``core.surface_translate`` so the
    written byte points at the right material in the target game's
    surface table. Without translation a III asphalt (id=1) and an SA
    asphalt (id=1) happen to align but a III glass (id=7) would land
    as PEBBLES in SA — translation maps it to SA's glass (id=35).
    """
    surface = Surface()

    if mat is None:
        return surface

    inu = getattr(mat, 'inu', None)
    if inu is not None:
        sid = getattr(inu, 'col_mat_index', 0)
        source = getattr(inu, 'col_source_game', '') or ''
        if target_game and source and source != target_game:
            from ..core.surface_translate import translate_surface
            sid = translate_surface(sid, source, target_game)
        surface.material = sid
        surface.flags = getattr(inu, 'col_flags', 0)
        surface.brightness = getattr(inu, 'col_brightness', 0)
        day = getattr(inu, 'col_day_light', 0)
        night = getattr(inu, 'col_night_light', 0)
        surface.light = (day & 0xF) | ((night & 0xF) << 4)

    return surface


_COL_VERSION_TO_GAME = {1: 'III', 2: 'VC', 3: 'SA'}


def _drop_degenerate_faces(bm, compressed: bool):
    """Remove degenerate triangles that would produce broken collision.

    Runs after triangulation. Two failure modes are cleaned:

      * Zero-area / collinear triangles (area < 1e-4) — a sliver produced by
        triangulating a concave or non-planar quad/n-gon. These are invisible
        to the pre-flight "loose vertex" / "n-gon" checks (all 3 verts are
        attached and it is a triangle, not an n-gon), yet the game treats a
        zero-area face as a hole → "invisible walls" / missing collision.

      * On compressed formats (COL2+), triangles that stay non-degenerate at
        full precision but *collapse* once vertices snap to the int16/128 grid:
        if any two of the three snapped positions land on the same integer
        cell the face becomes zero-area in the written file. We reproduce the
        exact round(co*128) snap the writer uses so the check matches reality.

    Loose verts left behind by the face removal are dropped too, so the vertex
    count and file size don't carry dead geometry.
    """
    dead = []
    for face in bm.faces:
        if face.calc_area() < 1e-4:
            dead.append(face)
            continue
        if compressed:
            snapped = {(round(v.co.x * 128), round(v.co.y * 128),
                        round(v.co.z * 128)) for v in face.verts}
            if len(snapped) < 3:   # two verts fell into the same cell
                dead.append(face)
    if dead:
        bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
    return len(dead)


def _collect_mesh(obj, model: ColModel):
    """Triangulate a mesh object and add its vertices/faces to the model."""
    mesh = obj.data
    target_game = _COL_VERSION_TO_GAME.get(model.version, 'SA')
    auto_light, auto_light_val = _auto_light_settings()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        # Только масштаб объекта — БЕЗ поворота. Поворот объекта (во вьюпорте)
        # — это РАЗМЕЩЕНИЕ модели (уходит в IPL/frame), в геометрию коллизии
        # его запекать нельзя: иначе COL двоит поворот с размещением и уезжает
        # относительно модели. Геометрия остаётся в модель-локале, как в DFF.
        # Примитивы (сфера/бокс) поворот тоже не берут.
        import mathutils
        sx, sy, sz = obj.matrix_world.to_scale()
        if (sx, sy, sz) != (1.0, 1.0, 1.0):
            bm.transform(mathutils.Matrix.Diagonal((sx, sy, sz, 1.0)))
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        _drop_degenerate_faces(bm, compressed=model.version >= 2)
        bm.verts.index_update()

        vert_offset = len(model.vertices)

        # Vertices
        for vert in bm.verts:
            model.vertices.append(Vec3(vert.co.x, vert.co.y, vert.co.z))

        # Faces
        for face in bm.faces:
            # Get surface from material
            surface = Surface()
            if face.material_index < len(obj.data.materials):
                mat = obj.data.materials[face.material_index]
                surface = _get_surface_from_material(mat, target_game)

            # Auto collision light (Kam parity): fill faces whose light
            # byte is still 0 (no COL material / unconfigured day+night).
            if auto_light and surface.light == 0:
                surface.light = auto_light_val

            # Swap verts[1] and verts[2] for GTA winding order
            verts = list(face.verts)
            a = verts[0].index + vert_offset
            b = verts[2].index + vert_offset
            c = verts[1].index + vert_offset

            model.faces.append(ColFace(a, b, c, surface))
    finally:
        bm.free()


def _is_shadow_mesh(obj) -> bool:
    """Detect if a Blender object should be treated as shadow mesh.

    Two ways to mark a mesh as shadow-only (Kam's/Rockstar convention):
      1. obj.inu.type == 'SHA'  (INU_Tools dropdown)
      2. Object name ends with '_SHA' / '_sha'  (Kam's suffix convention)
    """
    # Explicit type on inu property
    inu = getattr(obj, 'inu', None)
    if inu is not None and getattr(inu, 'type', '') == 'SHA':
        return True
    # Name suffix
    name = obj.name.lower()
    if name.endswith('_sha') or '_sha.' in name:  # .001 suffix variants
        return True
    return False


def _collect_shadow_mesh(obj, model: ColModel):
    """Same as _collect_mesh but writes to shadow_vertices/shadow_faces."""
    mesh = obj.data
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        # Только масштаб, без поворота — как в _collect_mesh (см. коммент там):
        # поворот объекта = размещение (IPL), не геометрия COL.
        import mathutils
        sx, sy, sz = obj.matrix_world.to_scale()
        if (sx, sy, sz) != (1.0, 1.0, 1.0):
            bm.transform(mathutils.Matrix.Diagonal((sx, sy, sz, 1.0)))
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        _drop_degenerate_faces(bm, compressed=model.version >= 2)
        bm.verts.index_update()

        vert_offset = len(model.shadow_vertices)

        for vert in bm.verts:
            model.shadow_vertices.append(Vec3(vert.co.x, vert.co.y, vert.co.z))

        for face in bm.faces:
            surface = Surface()
            if face.material_index < len(obj.data.materials):
                mat = obj.data.materials[face.material_index]
                surface = _get_surface_from_material(mat)

            # Swap verts[1] and verts[2] for GTA winding order
            verts = list(face.verts)
            a = verts[0].index + vert_offset
            b = verts[2].index + vert_offset
            c = verts[1].index + vert_offset

            model.shadow_faces.append(ColFace(a, b, c, surface))
    finally:
        bm.free()


def _collect_sphere(obj, model: ColModel):
    """Convert an Empty (sphere display) to ColSphere."""
    radius = max(s * obj.empty_display_size for s in obj.scale)
    center = Vec3(obj.location.x, obj.location.y, obj.location.z)

    surface = Surface()
    inu = getattr(obj, 'inu', None)
    if inu is not None:
        surface.material = getattr(inu, 'col_material', 0)
        surface.flags = getattr(inu, 'col_flags', 0)
        surface.brightness = getattr(inu, 'col_brightness', 0)
        surface.light = getattr(inu, 'col_light', 0)

    model.spheres.append(ColSphere(center=center, radius=radius, surface=surface))


def _collect_box(obj, model: ColModel):
    """Convert an Empty (cube display) to ColBox primitive.

    Inverse of `_create_box` in col_import: Blender's location is the
    box center, scale carries the half-extents per axis. AABB min/max
    fall out as `loc ± scale`. `abs()` on scale defends against the
    user mirroring an empty to a negative scale — the game stores an
    unordered AABB and a min > max box is silently dropped at load.
    """
    cx, cy, cz = obj.location
    sx, sy, sz = abs(obj.scale.x), abs(obj.scale.y), abs(obj.scale.z)

    surface = Surface()
    inu = getattr(obj, 'inu', None)
    if inu is not None:
        surface.material   = getattr(inu, 'col_material', 0)
        surface.flags      = getattr(inu, 'col_flags', 0)
        surface.brightness = getattr(inu, 'col_brightness', 0)
        surface.light      = getattr(inu, 'col_light', 0)

    model.boxes.append(ColBox(
        bb_min=Vec3(cx - sx, cy - sy, cz - sz),
        bb_max=Vec3(cx + sx, cy + sy, cz + sz),
        surface=surface,
    ))


def _collect_empty(obj, model: ColModel):
    """Dispatch an Empty to the right collector based on its display
    type. `'SPHERE'` → sphere primitive; `'CUBE'` → box primitive.
    Any other display type (`ARROWS`, `PLAIN_AXES`, …) is treated as
    sphere for backward compat with files imported by older versions
    that only knew about sphere empties."""
    if obj.empty_display_type == 'CUBE':
        _collect_box(obj, model)
    else:
        _collect_sphere(obj, model)


def _compute_bounds(model: ColModel) -> Bounds:
    """Bounding sphere + AABB over the COLLISION geometry.

    Covers mesh vertices and sphere/box primitives — but deliberately NOT the
    shadow mesh, and the sphere radius is the distance to the farthest real
    collision point, not half the AABB diagonal. Both of the latter inflate
    the sphere:
      • the shadow mesh often extends past the collision hull, and
      • the AABB diagonal measures to an empty box corner.
    An inflated collision bounding sphere makes GTA SA pull the vehicle
    follow-camera too far back — R* writes a tight sphere. Verified against a
    stock vehicle: this matches the R* radius far more closely than the old
    shadow-inclusive AABB-diagonal value.

    A shadow-only model (e.g. a light beam with no real collision) falls back
    to the shadow verts so it still gets non-empty bounds.
    """
    col_verts = model.vertices
    has_col = bool(col_verts) or bool(model.spheres) or bool(model.boxes)
    verts = col_verts if has_col else model.shadow_vertices
    if not (verts or model.spheres or model.boxes):
        return Bounds()

    INF = float('inf')
    bb_min = Vec3(INF, INF, INF)
    bb_max = Vec3(-INF, -INF, -INF)

    def _grow(x, y, z):
        if x < bb_min.x: bb_min.x = x
        if y < bb_min.y: bb_min.y = y
        if z < bb_min.z: bb_min.z = z
        if x > bb_max.x: bb_max.x = x
        if y > bb_max.y: bb_max.y = y
        if z > bb_max.z: bb_max.z = z

    for v in verts:
        _grow(v.x, v.y, v.z)
    for s in model.spheres:
        _grow(s.center.x - s.radius, s.center.y - s.radius, s.center.z - s.radius)
        _grow(s.center.x + s.radius, s.center.y + s.radius, s.center.z + s.radius)
    for b in model.boxes:
        _grow(b.bb_min.x, b.bb_min.y, b.bb_min.z)
        _grow(b.bb_max.x, b.bb_max.y, b.bb_max.z)

    center = Vec3(
        (bb_min.x + bb_max.x) / 2,
        (bb_min.y + bb_max.y) / 2,
        (bb_min.z + bb_max.z) / 2,
    )

    # Tight radius: distance to the farthest real collision point — vertices,
    # sphere surfaces, box corners — NOT the AABB corner.
    radius = 0.0
    for v in verts:
        dx, dy, dz = v.x - center.x, v.y - center.y, v.z - center.z
        radius = max(radius, math.sqrt(dx * dx + dy * dy + dz * dz))
    for s in model.spheres:
        dx, dy, dz = s.center.x - center.x, s.center.y - center.y, s.center.z - center.z
        radius = max(radius, math.sqrt(dx * dx + dy * dy + dz * dz) + s.radius)
    for b in model.boxes:
        for cx in (b.bb_min.x, b.bb_max.x):
            for cy in (b.bb_min.y, b.bb_max.y):
                for cz in (b.bb_min.z, b.bb_max.z):
                    dx, dy, dz = cx - center.x, cy - center.y, cz - center.z
                    radius = max(radius, math.sqrt(dx * dx + dy * dy + dz * dz))

    return Bounds(center=center, radius=radius, bb_min=bb_min, bb_max=bb_max)


def _stored_bounds(objects):
    """Return the SOURCE COL's saved Bounds if an imported object carries the
    ``inu_col_bounds`` custom property, else ``None``.

    Set by col_import on the COL mesh. Reusing it makes a round-trip export
    reproduce the original camera distance + shadow length exactly — R* builds
    vehicle bounds from the broad-phase spheres (not the mesh), which we can't
    recompute identically. Models built from scratch have no property → the
    freshly computed bounds are used."""
    for obj in objects:
        s = obj.get('inu_col_bounds') if hasattr(obj, 'get') else None
        if s is not None and len(s) == 10:
            return Bounds(center=Vec3(s[1], s[2], s[3]), radius=float(s[0]),
                          bb_min=Vec3(s[4], s[5], s[6]),
                          bb_max=Vec3(s[7], s[8], s[9]))
    return None


def _empty_col_bounds(ref, version: int, model_name: str) -> Bounds:
    """Bounds for a geometry-less (EMPTY) COL, measured from the visual model
    (``ref``) instead of left at zero.

    GTA streams / culls a model by its COL's bounding sphere. A zero-radius
    sphere at the origin makes the game never bring the model in — so it
    «disappears». We reuse the normal collect+measure path (a throwaway model)
    so the bounds land in exactly the same coordinate space a real COL would."""
    tmp = ColModel(version=version, model_name=model_name)
    for obj in (ref or []):
        if getattr(obj, 'type', None) == 'MESH' and not _is_shadow_mesh(obj):
            _collect_mesh(obj, tmp)
    return _compute_bounds(tmp)


def export_col(filepath: str, objects, version: int = 3, model_name: str = "",
               empty: bool = False, bounds_ref=None):
    """
    Export selected Blender objects as a COL file.

    Args:
        filepath: Output .col file path.
        objects: Iterable of Blender objects to export.
        version: COL version (1, 2, 3, or 4). Default 3 for GTA SA.
        model_name: Model name in COL header. If empty, derived from filename.
        empty: When True, write a geometry-less COL record (no faces/verts/
            spheres/boxes) that still carries ``model_name`` AND a real
            bounding sphere/box measured from the visual model — a zero sphere
            makes GTA cull the model so it disappears.
        bounds_ref: Objects to measure the empty-COL bounds from (the DFF/LOD).
            Falls back to ``objects`` when omitted.
    """
    import os

    if not model_name:
        model_name = os.path.splitext(os.path.basename(filepath))[0]

    model = ColModel(version=version, model_name=model_name)

    if not empty:
        for obj in objects:
            if obj.type == 'MESH':
                if _is_shadow_mesh(obj):
                    _collect_shadow_mesh(obj, model)
                else:
                    _collect_mesh(obj, model)

            elif obj.type == 'EMPTY':
                _collect_empty(obj, model)
        model.bounds = _compute_bounds(model)
        saved = _stored_bounds(objects)
        if saved is not None:
            model.bounds = saved
    else:
        # Empty COL still needs real bounds (from the visual model) or GTA
        # culls the model → it disappears.
        model.bounds = _empty_col_bounds(bounds_ref or objects, version, model_name)
    target_game = _resolve_target_game()
    audit_col([model], filepath, target_game=target_game)
    write_col_file(filepath, [model], target_game=target_game)
    return model


def build_col_model(objects, version: int = 3, model_name: str = "",
                    empty: bool = False, bounds_ref=None) -> ColModel:
    """Build a ``ColModel`` from Blender objects (main thread).

    Split out so batch exporters can build models on the main thread
    (bpy reads) and then hand them off to a worker pool for the CPU-
    bound ``write_col`` serialisation.

    ``empty=True`` skips geometry collection — the model carries only
    ``model_name`` plus a bounding sphere/box measured from ``bounds_ref``
    (the visual model), so GTA doesn't cull it (see ``export_col``).
    """
    model = ColModel(version=version, model_name=model_name)

    if not empty:
        for obj in objects:
            if obj.type == 'MESH':
                if _is_shadow_mesh(obj):
                    _collect_shadow_mesh(obj, model)
                else:
                    _collect_mesh(obj, model)

            elif obj.type == 'EMPTY':
                _collect_empty(obj, model)
        model.bounds = _compute_bounds(model)
        saved = _stored_bounds(objects)
        if saved is not None:
            model.bounds = saved
    else:
        # Empty COL: derive bounds from the visual model (bounds_ref, else the
        # passed objects) so GTA's culling sphere isn't zero.
        model.bounds = _empty_col_bounds(bounds_ref or objects, version, model_name)
    return model


def export_col_bytes(objects, version: int = 3, model_name: str = "") -> bytes:
    """
    Export selected Blender objects as COL bytes (for embedding in DFF, etc.).
    """
    model = build_col_model(objects, version=version, model_name=model_name)
    target_game = _resolve_target_game()
    audit_col([model], target_game=target_game)
    return write_col([model], target_game=target_game)


def _group_objects_by_base(objects) -> dict:
    """Group collidable objects by their model base name for library export.

    Grouping rules:
      - MESH objects use :func:`get_model_type` to extract ``base_name``
        (honours suffix/prefix settings — ``_COL``, ``_SHA``, etc.).
      - EMPTY objects (collision spheres/boxes) inherit the base name from
        their parent mesh when possible, otherwise use their own name with
        any Blender ``.001`` duplicate suffix stripped.
      - If an object exposes a non-empty ``inu.model_name``, that wins over
        the derived base so re-exported COLs keep their original library
        key even if the Blender object was renamed.

    Returns ``{base_name: [obj, ...]}`` preserving insertion order.
    """
    from ..tools.model_utils import get_model_type

    groups: dict = {}

    def _clean(name: str) -> str:
        if '.' in name:
            head, tail = name.rsplit('.', 1)
            if tail.isdigit():
                return head
        return name

    def _base_for(obj) -> str:
        inu = getattr(obj, 'inu', None)
        if inu is not None:
            mn = getattr(inu, 'model_name', '') or ''
            if mn:
                return mn
        if obj.type == 'MESH':
            _, base = get_model_type(obj)
            return base or _clean(obj.name)
        if obj.type == 'EMPTY' and obj.parent is not None:
            return _base_for(obj.parent)
        return _clean(obj.name)

    for obj in objects:
        if obj.type not in ('MESH', 'EMPTY'):
            continue
        base = _base_for(obj)
        if not base:
            continue
        groups.setdefault(base, []).append(obj)

    return groups


def export_col_library(filepath: str, objects, version: int = 3,
                       empty: bool = False) -> int:
    """Export a multi-entry COL "library" file.

    Selected objects are grouped by base name (via :func:`_group_objects_by_base`)
    and each group becomes its own COL record inside the single ``filepath``.
    This is how vanilla GTA SA ships ``<district>.col``, ``vehicles.col``,
    etc. — one ``.col`` file with many entries concatenated back-to-back.

    Returns the number of records written.
    """
    groups = _group_objects_by_base(objects)
    models = []
    for base_name, objs in groups.items():
        model = ColModel(version=version, model_name=base_name)
        if not empty:
            for obj in objs:
                if obj.type == 'MESH':
                    if _is_shadow_mesh(obj):
                        _collect_shadow_mesh(obj, model)
                    else:
                        _collect_mesh(obj, model)
                elif obj.type == 'EMPTY':
                    _collect_empty(obj, model)
            model.bounds = _compute_bounds(model)
        else:
            # Empty COL: bounds from the group's meshes so GTA doesn't cull it.
            model.bounds = _empty_col_bounds(objs, version, base_name)
        models.append(model)

    if models:
        from ..core.col import write_col_file
        target_game = _resolve_target_game()
        audit_col(models, filepath, target_game=target_game)
        write_col_file(filepath, models, target_game=target_game)
    return len(models)


# ──────────────────── Blender operator wrapper ────────────────────────

class GTATOOLS_OT_export_col(bpy.types.Operator, ExportHelper):
    """Экспортировать COL модель коллизии"""
    bl_idname = "gtatools.export_col"
    bl_label = "INU: Export COL"
    bl_options = {'PRESET'}
    filename_ext = ".col"
    filter_glob: StringProperty(default="*.col", options={'HIDDEN'})

    library_mode: BoolProperty(
        name=T("Library (несколько коллизий)"),
        description=T("Сгруппировать выделение по базовому имени (house1_COL + house1_SHA → одна запись 'house1') и записать все группы в один .col файл подряд. Так vanilla SA хранит <district>.col и vehicles.col"),
        default=False,
    )

    empty_col: BoolProperty(
        name=T("Пустая коллизия"),
        description=T("Записать COL без геометрии (ноль faces/вершин/сфер/боксов, нулевой bounds), но с именем модели. Для моделей, у которых не должно быть коллизии, но запись COL обязана существовать и быть привязана к модели. Геометрия выделенных объектов игнорируется — берётся только имя"),
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'library_mode')
        layout.prop(self, 'empty_col')
        col = layout.column()
        col.enabled = not self.empty_col
        _draw_col_auto_light(col, context)

    def execute(self, context):
        from ..tools.prelight import setup_prelight_preview
        import os

        # Common COL-name suffixes the importer / Map Import may attach.
        # Stripped from object names to derive a per-mesh filename in
        # the multi-select branch.
        SUFFIXES = ('_col', '.col', '_dff', '.dff', '_lod', '_dam', '_ok')

        def _basename_for(obj):
            n = obj.name
            ln = n.lower()
            for s in SUFFIXES:
                if ln.endswith(s):
                    return n[:-len(s)]
            return n

        prelight_was_on = []
        COL_EXPORT_FATAL.clear()
        COL_EXPORT_WARNINGS.clear()
        try:
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    has_prelight = False
                    for mat_slot in obj.material_slots:
                        mat = mat_slot.material
                        if mat and mat.use_nodes and mat.node_tree.nodes.get("Prelight_Mix"):
                            has_prelight = True
                            break
                    if has_prelight:
                        prelight_was_on.append(obj)
                        setup_prelight_preview(obj, enable=False)

            # COL is always exported around (0,0,0) — temporarily move
            original_locations = {}
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    original_locations[obj.name] = obj.location.copy()
                    obj.location = (0, 0, 0)

            col_objects = [o for o in context.selected_objects
                           if o.type in ('MESH', 'EMPTY')]
            mesh_objects = [o for o in col_objects if o.type == 'MESH']

            col_ver = _resolve_col_version(context)

            # ── Per-mesh split ────────────────────────────────────────
            # `library_mode=False` + multiple selected meshes → one .col
            # per mesh, named after each mesh (suffix-stripped). Default
            # behaviour previously bundled them all into one file which
            # mismatched user expectation and the rest of the toolset
            # (TXD now does per-mesh too).
            if not self.library_mode and len(mesh_objects) > 1:
                out_dir = os.path.dirname(self.filepath) or '.'
                written = []
                errors = []
                for obj in mesh_objects:
                    base = _basename_for(obj)
                    col_path = os.path.join(out_dir, f"{base}.col")
                    try:
                        export_col(
                            filepath=col_path,
                            objects=[obj],
                            version=col_ver,
                            model_name=base,
                            empty=self.empty_col,
                        )
                        written.append(f"{base}.col")
                    except Exception as e:
                        errors.append(f"{base}.col: {e}")

                # Restore positions before reporting so user can re-export
                # without picking up zeroed transforms on failure paths.
                for obj in context.selected_objects:
                    if obj.name in original_locations:
                        obj.location = original_locations[obj.name]
                for obj in prelight_was_on:
                    setup_prelight_preview(obj, enable=True)

                if not written:
                    self.report({'ERROR'},
                                "COL export failed for every mesh: "
                                + "; ".join(errors[:3]))
                    return {'CANCELLED'}
                summary = (f"{len(written)} COL written to {out_dir}"
                           + (f" ({len(errors)} failed)" if errors else ""))
                self._report_audit()
                self.report({'WARNING'} if errors else {'INFO'}, summary)
                return {'FINISHED'}

            # ── Single-file paths (legacy behaviour) ──────────────────
            if self.library_mode:
                count = export_col_library(
                    filepath=self.filepath,
                    objects=col_objects,
                    version=col_ver,
                    empty=self.empty_col,
                )
                msg = f"Exported COL{col_ver} library: {self.filepath} ({count} records)"
            else:
                export_col(
                    filepath=self.filepath,
                    objects=col_objects,
                    version=col_ver,
                    empty=self.empty_col,
                )
                msg = f"Exported COL{col_ver}: {self.filepath}"

            # Restore original positions
            for obj in context.selected_objects:
                if obj.name in original_locations:
                    obj.location = original_locations[obj.name]

            for obj in prelight_was_on:
                setup_prelight_preview(obj, enable=True)

            self._report_audit()
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        except Exception as e:
            for obj in prelight_was_on:
                try:
                    setup_prelight_preview(obj, enable=True)
                except Exception:
                    # Cleanup runs inside the export's error handler — a
                    # failure here must not mask the real error below.
                    pass
            self.report({'ERROR'}, f"COL export error: {str(e)}")
            return {'CANCELLED'}

    def _report_audit(self):
        """Surface the collision audit: warnings as WARNING, engine-crash
        findings as ERROR — the file is already written, the user fixes
        the mesh and re-exports."""
        for w in COL_EXPORT_WARNINGS:
            self.report({'WARNING'}, w)
        for item in COL_EXPORT_FATAL:
            self.report({'ERROR'}, f"{T('Игра упадёт')}: {item}")


