# INU_tools.ops.col_import
# COL collision file → Blender mesh objects.
# Uses INU_tools.core.col for binary format reading.

import bpy
import os
from bpy.props import StringProperty, CollectionProperty

from .. import T
from ..core.col import read_col_file, ColModel


_COL_VERSION_TO_GAME = {1: 'III', 2: 'VC', 3: 'SA'}


def _get_or_make_col_material(surface, material_cache, source_game=''):
    """Return a reusable material datablock for the given COL surface.

    The cache key is the full surface tuple so different (mat,flags,
    brightness,light) combinations get separate datablocks. Without
    a cache, large-map import creates 10k+ duplicate `COL_N` materials
    (one per surface per model) — sharing collapses that to ~64.
    """
    s = surface
    key = (s.material, s.flags, s.brightness, s.light)
    if material_cache is not None:
        cached = material_cache.get(key)
        if cached is not None:
            return cached, key

    mat = bpy.data.materials.new(f"COL_{s.material}")
    mat.inu.col_mat_index = s.material
    mat.inu.col_flags = s.flags
    mat.inu.col_brightness = s.brightness
    # COL2/COL3 surface.light is one byte packed as
    #   day  = light & 0xF   (low 4 bits)
    #   night= light >> 4    (high 4 bits)
    # — matches the export side (col_export.py:71). The N-panel UI
    # reads `col_day_light` / `col_night_light` separately, so the
    # raw byte alone (`col_light = s.light`) leaves the UI sliders
    # at zero. Split here so что юзер сразу видит правильные значения
    # после импорта.
    mat.inu.col_light = s.light                          # raw byte (legacy)
    mat.inu.col_day_light   = s.light & 0xF
    mat.inu.col_night_light = (s.light >> 4) & 0xF
    # Source game stays on the material so a later COL export can
    # translate IDs across games. Empty string means "unknown" — the
    # writer's clamp-only safety net still applies.
    if source_game:
        mat.inu.col_source_game = source_game

    if material_cache is not None:
        material_cache[key] = mat
    return mat, key


def _create_mesh_from_col(model: ColModel, collection, obj_type: str,
                          material_cache=None):
    """Create a Blender mesh object from COL vertices + faces.

    Uses ``mesh.from_pydata`` + ``foreach_set('material_index', ...)``
    instead of bmesh — measured ~5× faster on a large-map import where
    `_create_mesh_from_col` accounted for 60% of total wall time.

    A shared ``material_cache`` dict (keyed by full surface tuple) lets
    the caller reuse material datablocks across many models, avoiding
    thousands of duplicate `bpy.data.materials.new("COL_N")` calls.
    """
    if obj_type == 'COL':
        vertices = model.vertices
        faces = model.faces
        suffix = '_COL'
    else:
        vertices = model.shadow_vertices
        faces = model.shadow_faces
        suffix = '_sha'

    if not vertices or not faces:
        return None

    name = (model.model_name or "col_model") + suffix

    # Build geometry buffers in pure Python — much cheaper than bmesh.
    # COL → Blender winding flip done by reordering tuple here, not
    # per-face inside bmesh.
    verts = [(v.x, v.y, v.z) for v in vertices]
    tris = [(f.c, f.b, f.a) for f in faces]

    # Per-face material index, computed alongside cache lookups so we
    # can foreach_set in one shot at the end. The model's version
    # (1/2/3) tags the source game so on later re-export we can
    # translate surface IDs across games instead of writing them
    # untranslated.
    source_game = _COL_VERSION_TO_GAME.get(model.version, '')
    local_slot = {}  # surface key -> local slot index (per-mesh)
    mat_indices = [0] * len(faces)
    materials_in_order = []

    for i, f in enumerate(faces):
        mat, key = _get_or_make_col_material(
            f.surface, material_cache, source_game=source_game)
        slot = local_slot.get(key)
        if slot is None:
            slot = len(local_slot)
            local_slot[key] = slot
            materials_in_order.append(mat)
        mat_indices[i] = slot

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], tris)

    for mat in materials_in_order:
        mesh.materials.append(mat)

    if mat_indices:
        mesh.polygons.foreach_set('material_index', mat_indices)

    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    obj.inu.type = obj_type

    collection.objects.link(obj)
    return obj


def _create_sphere(sphere, collection, model_name: str, index: int):
    """Create an Empty with sphere display from ColSphere."""
    name = f"{model_name}_sphere_{index}"
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = 'SPHERE'
    empty.empty_display_size = sphere.radius
    empty.location = (sphere.center.x, sphere.center.y, sphere.center.z)

    empty.inu.col_material = sphere.surface.material
    empty.inu.col_flags = sphere.surface.flags
    empty.inu.col_brightness = sphere.surface.brightness
    empty.inu.col_light = sphere.surface.light

    collection.objects.link(empty)
    return empty


def _create_box(box, collection, model_name: str, index: int):
    """Create an Empty with cube display from ColBox primitive.

    GTA SA collision files store axis-aligned box primitives (TBox)
    alongside spheres for fast broad-phase collision. Each box has
    `min`/`max` corners + a surface (material/flags/brightness/light).
    DragonFF convention: location = (min+max)/2, scale = (max-min)/2
    — so Blender's scale directly carries the box's half-extents on
    each axis. Re-export mirrors this: `min = loc - scale`,
    `max = loc + scale`.
    """
    name = f"{model_name}_box_{index}"
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = 'CUBE'
    empty.empty_display_size = 1.0     # constant — scale carries the size
    half_x = (box.bb_max.x - box.bb_min.x) * 0.5
    half_y = (box.bb_max.y - box.bb_min.y) * 0.5
    half_z = (box.bb_max.z - box.bb_min.z) * 0.5
    cx = box.bb_min.x + half_x
    cy = box.bb_min.y + half_y
    cz = box.bb_min.z + half_z
    empty.location = (cx, cy, cz)
    empty.scale    = (half_x, half_y, half_z)

    empty.inu.col_material   = box.surface.material
    empty.inu.col_flags      = box.surface.flags
    empty.inu.col_brightness = box.surface.brightness
    empty.inu.col_light      = box.surface.light

    collection.objects.link(empty)
    return empty


def _create_prim_holder(model: ColModel, collection):
    """Map import, a model with spheres/boxes but no mesh at all: a mesh
    object WITHOUT geometry, «<name>_COL» tagged COL, holds them as its
    children (and the bounds) — col_export measures primitives from the
    COL mesh. Not an empty: COL export would write an empty as a sphere
    and DFF export would take it for a frame."""
    name = (model.model_name or "col_model") + '_COL'
    obj = bpy.data.objects.new(name, bpy.data.meshes.new(name))
    obj.inu.type = 'COL'
    collection.objects.link(obj)
    return obj


def import_col(filepath: str, context=None, material_cache=None):
    """
    Import a COL file into Blender.

    Args:
        filepath: Path to .col file.
        context: Blender context (optional).
        material_cache: optional dict shared across calls so duplicate COL
            surfaces reuse one material datablock. CRITICAL: without it,
            ``_get_or_make_col_material`` creates a brand-new material for
            EVERY face — a COL mesh has thousands of faces, so a few models
            spawn tens of thousands of ``bpy.data.materials.new("COL_N")``
            calls whose name-disambiguation (``COL_N.001/.002/…``) is
            O(existing), turning the import into an O(N²) freeze. Vanilla
            COL only uses ~64 distinct surfaces, so the cache collapses
            that to a handful of datablocks.
    """
    models = read_col_file(filepath)
    if material_cache is None:
        material_cache = {}
    return import_col_from_models(models, bulk_mode=False,
                                  material_cache=material_cache)


def _get_or_make_collision_collection(parent):
    """Return a «Collision» sub-collection under ``parent``, reusing an
    existing one if present so repeated imports don't spawn Collision.001,
    .002…. Falls back to ``parent`` itself if the link fails."""
    for child in parent.children:
        if child.name == "Collision" or child.name.startswith("Collision."):
            return child
    try:
        col = bpy.data.collections.new("Collision")
        parent.children.link(col)
        return col
    except Exception:
        return parent


def _place_on_models(groups, name_index, own):
    """Single-file import: every object of a COL model (mesh, shadow,
    spheres, boxes) moves by the world position of the scene model with the
    same name (or <name>_dff) — the primitives follow the mesh, so they stay
    where they are relative to it (col_export measures them from the mesh).

    ``groups`` = [(model_name, [objects])], created unparented at COL-local
    positions; ``own`` = the objects of this import (never a match).
    A model without a mesh (only spheres/boxes) stays put: export has no
    mesh to measure it from and writes its obj.location as is.
    The caller refreshes the view layer so matrix_world is current."""
    placed = 0
    for base, objs in groups:
        if not any(getattr(o, 'type', None) == 'MESH' for o in objs):
            continue
        low = base.lower()
        match = name_index.get(low) or name_index.get(low + '_dff')
        if match is None or match in own:
            continue
        off = match.matrix_world.translation.copy()
        for o in objs:
            if getattr(o, 'parent', None) is None:   # children follow
                o.location = o.location + off
        placed += 1
    return placed


def import_col_from_models(models, *, bulk_mode: bool = False,
                           target_collection=None,
                           skip_position_match: bool = False,
                           material_cache=None,
                           with_prims=None):
    """Build Blender objects from already-parsed ColModel list.

    Mirrors ``import_dff_from_clump``: the binary parse (``read_col``)
    can run in a worker thread, then the main thread calls this to
    materialise the objects. Used by Import Map for bulk-loading map
    collisions without going through the one-file-at-a-time flow.

    Args:
        models: list of parsed ``ColModel`` instances.
        bulk_mode: when True, skip ``bpy.ops.object.select_all`` and
                   position-match to DFF — caller handles placement
                   itself (this is the map-import case: the collision
                   goes to the model's first IPL instance).
        target_collection: destination collection; falls back to the
                   active one.
        skip_position_match: force-skip the «find DFF with same name
                   and copy its location» pass even without bulk_mode.
        material_cache: optional dict shared across calls so duplicate
                   surfaces reuse a single material datablock. Pass
                   the same dict for the entire map import.
        with_prims: create the spheres/boxes; default ``not bulk_mode``.
                   In bulk mode they become children of the model's COL
                   mesh (Import Map places the collision once per model).
    """
    if with_prims is None:
        with_prims = not bulk_mode
    if not models:
        raise ValueError("No collision models found in file")

    imported_objects = []
    collection = target_collection if target_collection is not None else bpy.context.collection
    # Single-model / vehicle import: drop the collision objects into a
    # dedicated «Collision» sub-collection so they're grouped and can be
    # hidden with one click instead of covering the model in the viewport.
    # Map (bulk) import keeps its own collection structure untouched.
    if not bulk_mode:
        collection = _get_or_make_collision_collection(collection)

    groups = []   # (model name, its objects) for the position match below
    for model in models:
        start = len(imported_objects)
        # Collision mesh
        obj = _create_mesh_from_col(model, collection, 'COL',
                                    material_cache=material_cache)
        if obj:
            imported_objects.append(obj)

        # Shadow mesh
        sha_obj = _create_mesh_from_col(model, collection, 'SHA',
                                        material_cache=material_cache)
        if sha_obj:
            imported_objects.append(sha_obj)

        # Spheres + boxes are collision of their own, not a broad phase:
        # the game tests them next to the triangles (reVC Collision.cpp
        # :513-525 lines, :1760-1782 ProcessSphereSphere/SphereBox); 1319
        # vanilla SA models have no triangles at all. Single-file import
        # makes them loose; bulk (map) import only with ``with_prims`` —
        # as children of the COL mesh (else the shadow mesh, else a mesh
        # holder without geometry), so they follow its placement.
        holder = None
        if with_prims and bulk_mode and (model.spheres or model.boxes):
            holder = obj or sha_obj
            if holder is None:
                holder = _create_prim_holder(model, collection)
                imported_objects.append(holder)
        if with_prims:
            for i, sphere in enumerate(model.spheres):
                emp = _create_sphere(sphere, collection,
                                     model.model_name or "col", i)
                if holder is not None:
                    emp.parent = holder
                imported_objects.append(emp)
            for i, box in enumerate(model.boxes):
                emp = _create_box(box, collection,
                                  model.model_name or "col", i)
                if holder is not None:
                    emp.parent = holder
                imported_objects.append(emp)

        # Preserve the source COL's bounds (sphere radius/center + AABB) on the
        # COL mesh so a round-trip export reproduces them EXACTLY. R* computes
        # vehicle bounds from the broad-phase spheres (NOT the mesh) — and they
        # drive the in-game camera distance AND shadow length — so recomputing
        # from the longer mesh inflates both. build_col_model reuses this on
        # export; models built from scratch (no property) fall back to compute.
        anchor = obj or sha_obj or holder
        if anchor is not None:
            b = model.bounds
            anchor['inu_col_bounds'] = [
                float(b.radius),
                float(b.center.x), float(b.center.y), float(b.center.z),
                float(b.bb_min.x), float(b.bb_min.y), float(b.bb_min.z),
                float(b.bb_max.x), float(b.bb_max.y), float(b.bb_max.z),
            ]

        if model.model_name:
            groups.append((model.model_name, imported_objects[start:]))

    # Single-file-import UX: place COL at the matching DFF's origin
    # so the user sees them aligned. Map import skips this — it sets
    # position directly from the IPL instance.
    if not bulk_mode and not skip_position_match:
        # Build a name→object index ONCE (O(N)). The previous code scanned
        # the ENTIRE scene for every imported COL mesh — O(N²) with RNA
        # `.name`/`.type` reads per inner step — which froze Blender for
        # minutes on a COL library holding thousands of models.
        name_index = {}
        for candidate in bpy.data.objects:
            if candidate.type == 'MESH':
                name_index.setdefault(candidate.name.lower(), candidate)

        try:
            bpy.context.view_layer.update()   # current matrix_world
        except Exception:
            pass
        _place_on_models(groups, name_index, set(imported_objects))

    # Select only on single-file import. Bulk map import needs no
    # selection side-effects.
    if not bulk_mode:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in imported_objects:
            obj.select_set(True)
        if imported_objects:
            bpy.context.view_layer.objects.active = imported_objects[0]

    return imported_objects


# ──────────────────── Modal-friendly generator ────────────────────────


def _iter_import_col_files(filepaths, target_collection, stats):
    """Yield ``(current, total, label)`` tuples while importing each
    .col file from ``filepaths`` and every model inside.

    Memory: the COL parsing step (``read_col_file``) is a single bulk
    decode per file — not chunked here. The slow part for COL libraries
    (vegasN.col with thousands of models) is the per-model object
    creation, which is what we yield-pace below.

    On completion, ``stats`` is filled with:
      - ``imported_objects`` — list of bpy.types.Object created
      - ``files_done`` — count of .col files successfully read
      - ``errors`` — list of (filename, error_str)
    """
    stats.setdefault('imported_objects', [])
    stats.setdefault('files_done', 0)
    stats.setdefault('errors', [])
    stats.setdefault('groups', [])   # (model name, its objects) — placement

    # Share the material cache across files so a multi-file drop with
    # repeating COL surface tuples (very common — vanilla COL only uses
    # ~64 distinct surfaces) doesn't create duplicate datablocks.
    material_cache: dict = {}

    # Pre-count total models for accurate progress. Read-twice would be
    # wasteful, so we count files first and refine inside the loop.
    file_count = len(filepaths)

    for file_idx, fpath in enumerate(filepaths):
        label = os.path.basename(fpath)
        yield (file_idx, max(file_count, 1), f"read: {label}")

        try:
            models = read_col_file(fpath)
        except Exception as e:
            stats['errors'].append((label, str(e)))
            continue

        if not models:
            stats['errors'].append((label, "no models"))
            continue

        for m_idx, model in enumerate(models):
            mname = model.model_name or f"model_{m_idx + 1}"
            yield (file_idx, max(file_count, 1),
                   f"{label} • {m_idx + 1}/{len(models)}: {mname}")

            start = len(stats['imported_objects'])
            obj = _create_mesh_from_col(
                model, target_collection, 'COL',
                material_cache=material_cache)
            if obj:
                stats['imported_objects'].append(obj)
            sha_obj = _create_mesh_from_col(
                model, target_collection, 'SHA',
                material_cache=material_cache)
            if sha_obj:
                stats['imported_objects'].append(sha_obj)
            for s_idx, sphere in enumerate(model.spheres):
                emp = _create_sphere(
                    sphere, target_collection,
                    model.model_name or "col", s_idx)
                stats['imported_objects'].append(emp)
            for b_idx, box in enumerate(model.boxes):
                emp = _create_box(
                    box, target_collection,
                    model.model_name or "col", b_idx)
                stats['imported_objects'].append(emp)
            if model.model_name:
                stats['groups'].append(
                    (model.model_name, stats['imported_objects'][start:]))

        stats['files_done'] += 1

    # Final position-match pass. Same logic as the synchronous
    # import_col_from_models but applied to ALL imported objects from
    # this batch (one match-DFF lookup per COL model).
    yield (file_count, max(file_count, 1), "matching DFF positions")
    # One-pass name→object index instead of a per-object whole-scene scan
    # (was O(N²) and froze on multi-model COL libraries — same fix as the
    # synchronous import_col_from_models path).
    name_index = {}
    for candidate in bpy.data.objects:
        if candidate.type == 'MESH':
            name_index.setdefault(candidate.name.lower(), candidate)

    try:
        bpy.context.view_layer.update()   # current matrix_world
    except Exception:
        pass
    _place_on_models(stats['groups'], name_index,
                     set(stats['imported_objects']))

    # Selection: deselect all, select all imported, set first as active.
    yield (file_count, max(file_count, 1), "selecting imported")
    bpy.ops.object.select_all(action='DESELECT')
    for obj in stats['imported_objects']:
        try:
            obj.select_set(True)
        except RuntimeError:
            pass  # not in active view layer; rare for fresh imports
    if stats['imported_objects']:
        try:
            bpy.context.view_layer.objects.active = stats['imported_objects'][0]
        except Exception:
            pass


# ──────────────────── Blender operator wrapper ────────────────────────


class _COLImportModalMixin:
    """Shared modal-loop scaffolding for the two COL import operators.

    Both ``import_col`` (file picker, single path) and ``drop_col``
    (drag-drop, multi path) drive the same per-model generator with
    progress + ESC cancel. The mixin owns timer / progress / status-bar
    plumbing so the operators only have to provide ``_collect_paths()``.
    """

    _timer = None
    _gen = None
    _stats: dict = None

    def _collect_paths(self) -> list:
        """Subclasses return the list of .col paths to import."""
        raise NotImplementedError

    def _start_modal(self, context):
        paths = self._collect_paths()
        if not paths:
            self.report({'WARNING'}, T("Не выбран ни один .col файл"))
            return {'CANCELLED'}

        self._stats = {}
        self._gen = _iter_import_col_files(
            paths, context.collection, self._stats)

        wm = context.window_manager
        wm.progress_begin(0, 100)
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(T("COL Import: подготовка..."))
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC':
            self._finish(context)
            self.report({'WARNING'}, T("COL Import отменён"))
            return {'CANCELLED'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        import time
        wm = context.window_manager
        deadline = time.monotonic() + 0.05  # ~20 fps frame budget

        while time.monotonic() < deadline:
            try:
                current, total, label = next(self._gen)
            except StopIteration:
                self._finish(context)
                stats = self._stats or {}
                imported = len(stats.get('imported_objects', []))
                files_done = stats.get('files_done', 0)
                errors = stats.get('errors', [])
                if errors and not imported:
                    err_msg = '; '.join(f"{n}: {e}" for n, e in errors[:3])
                    self.report({'ERROR'}, f"COL: {err_msg}")
                    return {'CANCELLED'}
                msg = (f"COL: {imported} {T('объект(ов)')} "
                       f"{T('из')} {files_done} {T('файлов')}")
                if errors:
                    msg += f" ({len(errors)} {T('с ошибкой')})"
                self.report({'INFO'}, msg)
                return {'FINISHED'}
            except Exception as e:
                self._finish(context)
                self.report({'ERROR'},
                            f"{T('Ошибка импорта COL')}: {e}")
                print(f"[col_import] aborted: {e}")
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}

            pct = int(100 * current / max(total, 1))
            wm.progress_update(pct)
            context.workspace.status_text_set(
                f"COL Import: {current}/{total} — {label}")

        return {'RUNNING_MODAL'}

    def _finish(self, context):
        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        try:
            context.window_manager.progress_end()
        except Exception:
            pass
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass
        self._gen = None


class GTATOOLS_OT_import_col(_COLImportModalMixin, bpy.types.Operator):
    """Импорт COL коллизии GTA SA с прогресс-баром.
    ESC прерывает импорт, уже созданные объекты остаются в сцене."""
    bl_idname = "gtatools.import_col"
    bl_label = "INU: Import COL (.col)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.col", options={'HIDDEN'})

    # User-overridable game source — Auto reads the COL header magic
    # (COLL / COL2 / COL3) to detect the game. Explicit values bypass
    # detection and tag surface IDs with that source for later
    # cross-game translation on export.
    import_game: bpy.props.EnumProperty(
        name=T("Игра"),
        description=T("Из какой игры импортируем COL. Auto — по magic header"),
        items=[
            ('AUTO', T("Авто-определение"), ""),
            ('III',  "GTA III",  ""),
            ('VC',   "Vice City", ""),
            ('SA',   "San Andreas", ""),
        ],
        default='AUTO')

    def _collect_paths(self):
        return [self.filepath] if self.filepath else []

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        self.layout.prop(self, "import_game")

    def execute(self, context):
        # Source-game resolution: user choice wins, AUTO falls back to
        # COL-magic detection. Then auto-flip-or-warn the scene game.
        try:
            from ..core import game_versions as gv
            if self.import_game == 'AUTO':
                detected = gv.detect_game_from_col(self.filepath)
            else:
                detected = self.import_game
            switched = gv.maybe_set_game_from_import(context.scene, detected)
            if not switched:
                warn = gv.check_game_mismatch_warning(context.scene, detected)
                if warn:
                    self.report({'WARNING'}, warn)
        except Exception:
            pass
        return self._start_modal(context)


class GTATOOLS_OT_drop_col(_COLImportModalMixin, bpy.types.Operator):
    """Импорт COL при перетаскивании во viewport (батч, прогресс + ESC).

    Принимает несколько файлов сразу. Селекция игнорируется — COL
    создаёт собственные mesh-объекты, не цепляется к существующим.
    """
    bl_idname = "gtatools.drop_col"
    bl_label = "INU: Import COL (Drop)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')

    def _collect_paths(self):
        out = []
        for f in self.files:
            path = os.path.join(self.directory, f.name)
            if os.path.isfile(path) and path.lower().endswith('.col'):
                out.append(path)
        return out

    def execute(self, context):
        return self._start_modal(context)


if hasattr(bpy.types, 'FileHandler'):
    class GTATOOLS_FH_col_drop(bpy.types.FileHandler):
        """File Handler для перетаскивания COL во viewport"""
        bl_idname = "GTATOOLS_FH_col_drop"
        bl_label = "GTA COL Drop"
        bl_import_operator = "gtatools.drop_col"
        bl_file_extensions = ".col"

        @classmethod
        def poll_drop(cls, context):
            return context.area and context.area.type == 'VIEW_3D'


