# INU_tools.tools.build_library
#
# Core logic for the GTA SA Asset Library builder. The headless CLI script
# in ``dev/build_library.py`` is a thin wrapper over this module; the
# in-addon operator in ``INU_tools/ops/build_library_ops.py`` reuses the
# same generator pipeline so the UI version stays bit-identical to the CLI
# version.
#
# Key entry points:
#
#   build_classification(game_root) -> dict
#       Walks gta.dat + default.dat (+ optional gta_int.dat), reads every
#       IDE referenced, returns ``{model_name_lower: {category, txd_name,
#       model_id, draw_distance, ide_flags}}``.
#
#   scan_cache(cache_dir, classification) -> (by_category, unclassified)
#       Iterates ``<cache_dir>/*.dff``, groups by category using the
#       classification map.
#
#   build_library_iter(cache_dir, game_root, output_dir, status, **opts)
#       Main generator: yields ``None`` after each unit of work so a
#       caller (operator modal, CLI loop) can update progress. Pass a
#       mutable ``status`` dict — it's updated in-place with phase /
#       counters / current category / current asset name.
#
# All logic that reads/writes Blender data lives behind ``import bpy``
# inside the relevant function bodies — module-level imports stay
# bpy-free so the classification half can run without Blender if ever
# needed (e.g. unit tests).

from __future__ import annotations

import os
import shutil
import time
import uuid
from collections import defaultdict
from typing import Iterator, Optional


# ────────────────────────────────────────────────────────────────────
# Category routing
# ────────────────────────────────────────────────────────────────────

# Display names for vanilla SA region folders. Mods with custom regions
# fall through to the title-cased folder name automatically (see
# ``get_catalog_path`` below) — no hard-coded allow-list, so a modpack
# adding ``data/maps/BAYSIDE/`` lands cleanly under
# ``Map Objects/Bayside`` without us having to know about it.
_VANILLA_REGION_DISPLAY = {
    'LA':       'Los Santos',
    'SF':       'San Fierro',
    'VEGAS':    'Las Venturas',
    'COUNTRY':  'Country',
}

# Internal category code → Asset Browser catalog path. Only fixed-name
# categories live here; per-region catalog paths are computed dynamically
# in ``get_catalog_path`` because we don't know the region set up front
# (we don't even read gta.dat in this file — that's the addon's UI side).
CATEGORY_CATALOG = {
    'vehicles':              'Vehicles',
    'peds':                  'Peds',
    'weapons':               'Weapons',
    'cutscene':              'Cutscene',
    'lod':                   'LOD',
    'mapobjects_INTERIORS':  'Map Objects/Interiors',
    'mapobjects_GENERIC':    'Map Objects/Generic',
}


def get_catalog_path(category: str) -> str:
    """Resolve internal category code to the Asset Browser catalog path.

    Fixed categories come from ``CATEGORY_CATALOG``. Anything starting
    with ``mapobjects_<REGION>`` is mapped dynamically: vanilla SA
    regions get their pretty display name (``LA → Los Santos``), and
    custom mod regions get their folder name title-cased
    (``BAYSIDE → Bayside``). Result is always nested under
    ``Map Objects/`` so modpack-added regions sit alongside the
    vanilla ones in the Asset Browser tree.
    """
    if category in CATEGORY_CATALOG:
        return CATEGORY_CATALOG[category]
    if category.startswith('mapobjects_'):
        region = category[len('mapobjects_'):]
        display = _VANILLA_REGION_DISPLAY.get(region.upper())
        if display is None:
            # Custom region from a modpack — keep the folder name
            # readable (title case, replace underscores with spaces).
            display = region.replace('_', ' ').title()
        return f'Map Objects/{display}'
    return category

# Categories where we WANT armatures (skinned/rigged). Map objects skip
# armature build for speed since they're static.
SKINNED_CATEGORIES = {'vehicles', 'peds', 'weapons'}

# Stable namespace for asset-catalog UUIDs. uuid5(namespace, catalog_path)
# gives a deterministic UUID — the same path produces the same UUID across
# every run. This is what lets ``--skip-existing`` work: assets saved in a
# previous run reference UUIDs that match what a fresh ``cats.txt`` writes.
#
# This UUID is arbitrary but must NEVER change once any user has built a
# library with this script — bumping it would orphan every existing asset
# from its catalog.
_INU_CATALOG_NAMESPACE = uuid.UUID('5d92e3a4-3c1f-5b8b-9e2c-1f7a4d6e8b29')

_PREVIEW_CAMERA_NAME = '__INU_PreviewCamera__'


def classify_ide_path(ide_path: str) -> str:
    """Return the static-mapobject category for a given IDE file path.

    Vanilla SA regions and modpack-added regions both produce a category
    of the form ``mapobjects_<REGION>`` — no hard-coded region whitelist.
    Special-case folders (``GENERIC``, ``INTERIOR``, ``LEVELDES``) route
    to dedicated buckets so they don't clutter the regional catalogs.
    """
    p = ide_path.replace('\\', '/').lower()
    base = os.path.basename(p)

    if base == 'default.ide':
        return 'mapobjects_GENERIC'

    parts = p.split('/')
    if 'maps' in parts:
        idx = parts.index('maps')
        if idx + 1 < len(parts):
            region = parts[idx + 1].upper()
            if region in ('GENERIC',):
                return 'mapobjects_GENERIC'
            if region in ('INTERIOR', 'INTERIORS'):
                return 'mapobjects_INTERIORS'
            if region in ('LEVELDES', 'LEVELDESIGN'):
                # Level-design helpers: scaffolding, debug primitives.
                # Lump into GENERIC rather than getting their own bucket.
                return 'mapobjects_GENERIC'
            # Anything else — vanilla region (LA/SF/VEGAS/COUNTRY) or a
            # custom modpack region (BAYSIDE/LCSV/etc.) — gets its own
            # category. ``get_catalog_path`` then routes it under the
            # ``Map Objects/`` tree in the Asset Browser.
            return f'mapobjects_{region}'

    return 'mapobjects_GENERIC'


def is_lod_name(name: str) -> bool:
    """Vanilla SA names LOD twins three ways: prefix ``lodfoo``, infix
    ``foo_lod``, or bare in-name ``modeLODlaett``. Routing all three to
    a separate category keeps the main browse view clean."""
    n = name.lower()
    return n.startswith('lod') or '_lod' in n or 'lod' in n


def build_classification(game_root: str, game: str = 'SA') -> dict:
    """{ model_name_lower: {'category', 'txd_name', 'model_id',
                            'draw_distance', 'ide_flags'} }

    Reads every IDE referenced from the game's master .dat manifest.
    Vehicles / peds / weapons go to fixed categories; static objects
    are routed by IDE folder via ``classify_ide_path``.

    ``game`` (III / VC / SA, default SA) selects which .dat files to
    parse:
      * SA  → ``data/gta.dat`` + ``data/default.dat`` + optional
              ``data/gta_int.dat``
      * VC  → ``data/gta_vc.dat`` + ``data/default.dat``
      * III → ``data/gta3.dat`` + ``data/default.dat``

    The IDE parser itself is game-agnostic (per Phase 5 + 18 + 19);
    column counts auto-detect on read so III/VC cars/peds entries
    land in the right fields.
    """
    from ..core import ide as ide_module
    from ..core.gta_dat import parse_gta_dat, resolve_paths
    from ..core.fs_ci import resolve as _ci

    classification: dict = {}
    section_totals: dict = defaultdict(int)
    missing_paths: list = []

    state = {'current_cat': 'mapobjects_GENERIC'}

    def _absorb(ide):
        cat = state['current_cat']
        # objs / anim — static map objects, route by IDE path
        for obj in ide.objects:
            key = obj.model_name.lower()
            eff = 'lod' if is_lod_name(obj.model_name) else cat
            classification[key] = {
                'category': eff,
                'txd_name': obj.txd_name,
                'model_id': obj.model_id,
                'draw_distance': obj.draw_distance,
                'ide_flags': obj.flags,
            }
        for anim in ide.anims:
            key = anim.model_name.lower()
            eff = 'lod' if is_lod_name(anim.model_name) else cat
            classification[key] = {
                'category': eff,
                'txd_name': anim.txd_name,
                'model_id': anim.model_id,
                'draw_distance': anim.draw_distance,
                'ide_flags': anim.flags,
            }
        # cars/peds/weaps/hier — fixed categories
        for car in ide.cars:
            classification[car.model_name.lower()] = {
                'category': 'vehicles',
                'txd_name': car.txd_name,
                'model_id': car.model_id,
                'draw_distance': 0.0,
                'ide_flags': car.flags,
            }
        for ped in ide.peds:
            classification[ped.model_name.lower()] = {
                'category': 'peds',
                'txd_name': ped.txd_name,
                'model_id': ped.model_id,
                'draw_distance': 0.0,
                'ide_flags': 0,
            }
        for weap in ide.weaps:
            classification[weap.model_name.lower()] = {
                'category': 'weapons',
                'txd_name': weap.txd_name,
                'model_id': weap.model_id,
                'draw_distance': weap.draw_distance,
                'ide_flags': 0,
            }
        for hier in ide.hiers:
            classification[hier.model_name.lower()] = {
                'category': 'cutscene',
                'txd_name': hier.txd_name,
                'model_id': hier.model_id,
                'draw_distance': 0.0,
                'ide_flags': 0,
            }

    def _walk(dat_path, required: bool = True):
        if not os.path.isfile(dat_path):
            if required:
                print(f"      WARN: dat not found: {dat_path}")
            return
        info = resolve_paths(game_root, parse_gta_dat(dat_path))
        print(f"      {os.path.basename(dat_path)}: "
              f"{len(info.ide_paths)} IDE paths declared")
        for ide_path in info.ide_paths:
            if not os.path.isfile(ide_path):
                missing_paths.append(ide_path)
                continue
            try:
                ide = ide_module.read_ide(ide_path)
            except Exception as e:
                print(f"      ERROR parsing {ide_path}: {e}")
                continue
            section_totals['objs'] += len(ide.objects)
            section_totals['anim'] += len(ide.anims)
            section_totals['cars'] += len(ide.cars)
            section_totals['peds'] += len(ide.peds)
            section_totals['weap'] += len(ide.weaps)
            section_totals['hier'] += len(ide.hiers)
            state['current_cat'] = classify_ide_path(ide_path)
            _absorb(ide)

    # Per-game master .dat selection. Each game ships its IDE manifest
    # under a different name; default.dat is shared (vehicles/peds/
    # weapons across all three).
    if game == 'III':
        _walk(_ci(os.path.join(game_root, 'data', 'gta3.dat')), required=True)
        _walk(_ci(os.path.join(game_root, 'data', 'default.dat')), required=True)
    elif game == 'VC':
        _walk(_ci(os.path.join(game_root, 'data', 'gta_vc.dat')), required=True)
        _walk(_ci(os.path.join(game_root, 'data', 'default.dat')), required=True)
    else:
        # SA — three .dats; gta_int is only present on Steam Edition / mods.
        _walk(_ci(os.path.join(game_root, 'data', 'gta.dat')), required=True)
        _walk(_ci(os.path.join(game_root, 'data', 'default.dat')), required=True)
        _walk(_ci(os.path.join(game_root, 'data', 'gta_int.dat')), required=False)

    print(f"      sections: " + ", ".join(
        f"{k}={v}" for k, v in sorted(section_totals.items())))
    if missing_paths:
        print(f"      WARN: {len(missing_paths)} IDE paths declared in dat "
              f"but not found on disk; first 5:")
        for p in missing_paths[:5]:
            print(f"        {p}")

    return classification


def scan_cache(cache_dir: str, classification: dict):
    """Walk ``<cache_dir>/*.dff``, returning (by_category, unclassified).

    by_category: {category: [{filepath, name, txd_name, model_id,
                              draw_distance, ide_flags}, ...]}
    unclassified: [filename, ...] for DFFs not matching any IDE entry.
    """
    by_category: dict = defaultdict(list)
    unclassified: list = []
    for fn in sorted(os.listdir(cache_dir)):
        if not fn.lower().endswith('.dff'):
            continue
        name = os.path.splitext(fn)[0].lower()
        info = classification.get(name)
        if info is None:
            unclassified.append(fn)
            continue
        by_category[info['category']].append({
            'filepath': os.path.join(cache_dir, fn),
            'name': name,
            'txd_name': info['txd_name'],
            'model_id': info['model_id'],
            'draw_distance': info.get('draw_distance', 0.0),
            'ide_flags': info.get('ide_flags', 0),
        })
    return by_category, unclassified


# ────────────────────────────────────────────────────────────────────
# Asset catalog tree
# ────────────────────────────────────────────────────────────────────

class CatalogTree:
    """Backing store for ``blender_assets.cats.txt``."""

    def __init__(self):
        self._uuid_by_path: dict = {}
        self._all_paths: set = set()

    def get_uuid(self, catalog_path: str) -> str:
        key = catalog_path.lower()
        if key not in self._uuid_by_path:
            uid = str(uuid.uuid5(_INU_CATALOG_NAMESPACE, catalog_path))
            self._uuid_by_path[key] = (uid, catalog_path)
        parts = catalog_path.split('/')
        for i in range(1, len(parts) + 1):
            sub = '/'.join(parts[:i])
            sk = sub.lower()
            if sk not in self._uuid_by_path:
                uid = str(uuid.uuid5(_INU_CATALOG_NAMESPACE, sub))
                self._uuid_by_path[sk] = (uid, sub)
            self._all_paths.add(sk)
        return self._uuid_by_path[key][0]

    def write(self, path: str):
        lines = [
            "# This is an Asset Catalog Definition file for Blender.",
            "#",
            "# Empty lines and lines starting with `#` will be ignored.",
            "# The first non-ignored line should be the version indicator.",
            '# Other lines are of the format "UUID:catalog/path/for/assets:simple catalog name"',
            "",
            "VERSION 1",
            "",
        ]
        for sk in sorted(self._all_paths):
            u, p = self._uuid_by_path[sk]
            simple = p.replace('/', '-')
            lines.append(f"{u}:{p}:{simple}")
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')


# ────────────────────────────────────────────────────────────────────
# Preview rendering — Workbench, iso 3/4, transparent BG
# ────────────────────────────────────────────────────────────────────

def setup_preview_render(size: int):
    import bpy
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    shading = scene.display.shading
    shading.light = 'STUDIO'
    shading.color_type = 'TEXTURE'
    shading.show_specular_highlight = False
    shading.show_cavity = False


def ensure_preview_camera():
    import bpy
    cam_obj = bpy.data.objects.get(_PREVIEW_CAMERA_NAME)
    if cam_obj is None:
        cam_data = bpy.data.cameras.new(_PREVIEW_CAMERA_NAME)
        cam_data.lens = 50
        cam_obj = bpy.data.objects.new(_PREVIEW_CAMERA_NAME, cam_data)
        bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    return cam_obj


def frame_camera_on_collection(cam, coll) -> bool:
    """Place camera at iso 3/4 angle and distance such that the bbox
    diagonal exactly subtends the camera's FOV (plus 10% margin).
    Returns False on empty collections."""
    import math
    from mathutils import Vector

    bb_min = [float('inf')] * 3
    bb_max = [float('-inf')] * 3
    found = False

    for obj in coll.all_objects:
        if obj.type != 'MESH' or not obj.data or len(obj.data.vertices) == 0:
            continue
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            for i in range(3):
                if world[i] < bb_min[i]:
                    bb_min[i] = world[i]
                if world[i] > bb_max[i]:
                    bb_max[i] = world[i]
        found = True

    if not found:
        return False

    center = Vector(((bb_min[0] + bb_max[0]) / 2,
                     (bb_min[1] + bb_max[1]) / 2,
                     (bb_min[2] + bb_max[2]) / 2))
    extent_x = bb_max[0] - bb_min[0]
    extent_y = bb_max[1] - bb_min[1]
    extent_z = bb_max[2] - bb_min[2]
    diagonal = math.sqrt(extent_x * extent_x +
                         extent_y * extent_y +
                         extent_z * extent_z)
    if diagonal < 0.001:
        diagonal = 0.1

    fov = cam.data.angle
    margin = 1.10
    cam_distance = (diagonal / 2.0) / math.tan(fov / 2.0) * margin

    iso_dir = Vector((1.0, -1.0, 0.6)).normalized()
    cam.location = center + iso_dir * cam_distance
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return True


def render_and_load_preview(coll, png_path: str) -> bool:
    """Render `coll` to PNG, then load that PNG as the collection's asset
    preview. Caller must ensure only `coll` is currently linked to scene."""
    import bpy

    cam = bpy.context.scene.camera
    if cam is None or not frame_camera_on_collection(cam, coll):
        return False

    bpy.context.scene.render.filepath = png_path
    try:
        bpy.ops.render.render(write_still=True)
    except Exception as e:
        print(f"  render error ({coll.name}): {e}")
        return False

    if not os.path.isfile(png_path):
        return False

    try:
        with bpy.context.temp_override(id=coll):
            bpy.ops.ed.lib_id_load_custom_preview(filepath=png_path)
    except Exception as e:
        print(f"  preview load error ({coll.name}): {e}")
        return False

    try:
        os.remove(png_path)
    except OSError:
        pass
    return True


# ────────────────────────────────────────────────────────────────────
# Scene reset / texture wiring helpers
# ────────────────────────────────────────────────────────────────────

def reset_blend_state():
    """Wipe all scene data WITHOUT touching Blender preferences. Uses
    ``bpy.data.batch_remove`` so the depsgraph update fires once."""
    import bpy
    to_remove = []
    for db_attr in ('objects', 'meshes', 'materials', 'images',
                    'collections', 'armatures', 'actions', 'curves',
                    'lights', 'cameras', 'node_groups', 'textures',
                    'lattices', 'particles'):
        coll = getattr(bpy.data, db_attr, None)
        if coll is None:
            continue
        to_remove.extend(coll)
    if to_remove:
        bpy.data.batch_remove(to_remove)
    bpy.ops.outliner.orphans_purge(do_local_ids=True,
                                   do_linked_ids=True,
                                   do_recursive=True)


def link_textures_for_objects(objects, tex_dir: str) -> int:
    """For each TEX_IMAGE node lacking an image, look up <label>.png in
    ``tex_dir`` and load it. Re-uses already-loaded images."""
    import bpy
    loaded = 0
    for obj in objects:
        if obj.type != 'MESH' or not obj.data:
            continue
        for slot in obj.material_slots:
            mat = slot.material
            if not mat or not mat.use_nodes or not mat.node_tree:
                continue
            for node in mat.node_tree.nodes:
                if node.type != 'TEX_IMAGE':
                    continue
                if node.image is not None:
                    continue
                tex_name = node.label
                if not tex_name:
                    continue
                png_path = os.path.join(tex_dir, tex_name + '.png')
                if not os.path.isfile(png_path):
                    continue
                img = bpy.data.images.load(png_path, check_existing=True)
                node.image = img
                loaded += 1
    return loaded


def remap_image_paths_to_library(library_tex_dirname: str = 'textures'):
    """Rewrite every loaded image's filepath to ``//<dir>/<basename>``."""
    import bpy
    for img in bpy.data.images:
        if img.source != 'FILE':
            continue
        src = img.filepath_raw or img.filepath
        if not src:
            continue
        base = os.path.basename(src)
        new_path = f"//{library_tex_dirname}/{base}"
        img.filepath_raw = new_path
        img.filepath = new_path


# ────────────────────────────────────────────────────────────────────
# Per-category build — generator yielding after each asset
# ────────────────────────────────────────────────────────────────────

def build_category_blend_iter(category: str,
                              items: list,
                              output_dir: str,
                              catalog: CatalogTree,
                              tex_dir: str,
                              status: dict,
                              *,
                              generate_preview: bool = True,
                              preview_size: int = 128,
                              skip_existing: bool = False,
                              quiet_alpha: bool = True) -> Iterator[None]:
    """Build one .blend with N assets. Yields ``None`` after each asset
    so the caller can update progress / let UI tick. Updates ``status``
    in-place with current asset counters."""
    import bpy
    import contextlib
    import io
    import tempfile

    out_path = os.path.join(output_dir, f"{category}.blend")
    if skip_existing and os.path.isfile(out_path):
        print(f"[{category}] skipped (already exists: {out_path})")
        status['skipped_categories'] = status.get('skipped_categories', 0) + 1
        return

    print(f"[{category}] building {len(items)} assets → {out_path}")

    reset_blend_state()

    if generate_preview:
        setup_preview_render(preview_size)
        ensure_preview_camera()
        preview_tmp = tempfile.mkdtemp(prefix=f"inu_preview_{category}_")
    else:
        preview_tmp = None

    catalog_uuid = catalog.get_uuid(get_catalog_path(category))
    material_cache: dict = {}
    use_bulk = category not in SKINNED_CATEGORIES

    from ..ops.dff_import import import_dff
    from ..ops.texture_ops import link_material_alpha_if_textured

    imported_count = 0
    failed_count = 0
    preview_ok = 0
    preview_fail = 0
    t0 = time.perf_counter()

    status['category'] = category
    status['cat_total'] = len(items)
    status['cat_done'] = 0
    status['cat_ok'] = 0
    status['cat_fail'] = 0
    status['cat_preview_ok'] = 0
    status['cat_preview_fail'] = 0

    for i, item in enumerate(items):
        status['current_asset'] = item['name']
        try:
            objects = import_dff(
                item['filepath'],
                bulk_mode=use_bulk,
                material_cache=material_cache,
                skip_2dfx=True,
            )
            if not objects:
                continue

            coll = bpy.data.collections.new(item['name'])
            bpy.context.scene.collection.children.link(coll)
            for obj in objects:
                for c in list(obj.users_collection):
                    c.objects.unlink(obj)
                coll.objects.link(obj)

            link_textures_for_objects(objects, tex_dir)

            if quiet_alpha:
                _stdout_ctx = contextlib.redirect_stdout(io.StringIO())
            else:
                _stdout_ctx = contextlib.nullcontext()
            with _stdout_ctx:
                for obj in objects:
                    if obj.type != 'MESH':
                        continue
                    for slot in obj.material_slots:
                        if slot.material:
                            link_material_alpha_if_textured(slot.material)

            # Stamp INU metadata so a dragged-and-dropped asset
            # round-trips through Map Export back to game format.
            for obj in objects:
                inu = getattr(obj, 'inu', None)
                if inu is None:
                    continue
                inu.model_id = int(item['model_id'])
                inu.txd_name = item['txd_name']
                inu.draw_distance = float(item['draw_distance'])
                inu.ide_flags = int(item['ide_flags'])

            coll.asset_mark()
            ad = coll.asset_data
            ad.catalog_id = catalog_uuid
            ad.description = (
                f"GTA SA model_id={item['model_id']}, "
                f"txd={item['txd_name']}, "
                f"draw_dist={item['draw_distance']:.0f}, "
                f"flags=0x{item['ide_flags']:X}"
            )
            ad.tags.new(category, skip_if_exists=True)
            coll.use_fake_user = True

            if generate_preview:
                png = os.path.join(preview_tmp, f"{item['name']}.png")
                if render_and_load_preview(coll, png):
                    preview_ok += 1
                else:
                    preview_fail += 1

            try:
                bpy.context.scene.collection.children.unlink(coll)
            except RuntimeError:
                pass

            imported_count += 1

        except Exception as e:
            failed_count += 1
            print(f"  ERROR [{item['name']}]: {e}")

        status['cat_done'] = i + 1
        status['cat_ok'] = imported_count
        status['cat_fail'] = failed_count
        status['cat_preview_ok'] = preview_ok
        status['cat_preview_fail'] = preview_fail
        yield  # let modal tick / log progress between assets

    bpy.context.view_layer.update()

    if generate_preview:
        cam_obj = bpy.data.objects.get(_PREVIEW_CAMERA_NAME)
        if cam_obj is not None:
            cam_data = cam_obj.data
            bpy.data.objects.remove(cam_obj)
            if cam_data is not None and cam_data.users == 0:
                bpy.data.cameras.remove(cam_data)
        if preview_tmp and os.path.isdir(preview_tmp):
            shutil.rmtree(preview_tmp, ignore_errors=True)

    remap_image_paths_to_library('textures')

    bpy.ops.wm.save_as_mainfile(
        filepath=out_path,
        relative_remap=True,
        compress=True,
    )
    elapsed = time.perf_counter() - t0
    extra_msg = ""
    if generate_preview:
        extra_msg = f", previews {preview_ok}/{preview_ok + preview_fail}"
    print(f"[{category}] saved in {elapsed:.1f}s "
          f"({imported_count} ok, {failed_count} fail{extra_msg})")


# ────────────────────────────────────────────────────────────────────
# Texture folder mirroring
# ────────────────────────────────────────────────────────────────────

def regenerate_previews_iter(library_dir: str,
                             status: dict,
                             *,
                             preview_size: int = 128) -> Iterator[None]:
    """Refresh the asset thumbnail of every asset in an existing library.

    Walks ``<library_dir>/*.blend``, opens each one, re-renders the
    Workbench thumbnail for every asset-marked collection, then writes
    the .blend back. Useful when you want to bump preview size from
    128 to 256 or fix a batch of broken previews without paying for a
    full asset re-import.

    Yields between every asset so a modal operator can update progress.
    """
    import bpy
    import shutil
    import tempfile

    if not os.path.isdir(library_dir):
        raise FileNotFoundError(f"library dir not found: {library_dir}")

    blends = sorted(f for f in os.listdir(library_dir)
                    if f.lower().endswith('.blend'))
    if not blends:
        status['phase'] = 'done'
        return

    status['phase'] = 'regen'
    status['blend_total'] = len(blends)
    status['blend_done'] = 0
    yield

    for bi, blend_name in enumerate(blends):
        blend_path = os.path.join(library_dir, blend_name)
        category = blend_name[:-len('.blend')]
        status['category'] = category
        status['blend_done'] = bi
        yield

        # Open the .blend in this Blender instance. Replaces bpy.data
        # but keeps the addon registration (open_mainfile does not
        # reset preferences). The user's current work must be saved
        # before invoking — the caller is responsible for that check.
        bpy.ops.wm.open_mainfile(filepath=blend_path)
        yield

        # Configure scene render + preview camera. The library .blend
        # has neither — we strip the camera before save in the build
        # path, and the saved scene is otherwise the empty scene state
        # left after _reset_blend_state.
        setup_preview_render(preview_size)
        ensure_preview_camera()

        # Find every asset-marked collection. ``asset_data`` is the
        # presence indicator: not-None ⇒ collection is an asset.
        asset_colls = [c for c in bpy.data.collections
                       if c.asset_data is not None]
        status['cat_total'] = len(asset_colls)
        status['cat_done'] = 0

        if not asset_colls:
            yield
            continue

        scene_coll = bpy.context.scene.collection
        tmpdir = tempfile.mkdtemp(prefix=f'inu_regen_{category}_')
        try:
            for ai, coll in enumerate(asset_colls):
                status['current_asset'] = coll.name
                # Link briefly so the renderer sees this collection's
                # geometry; unlink right after to keep the render
                # context O(1) for the next asset (same trick as the
                # original build).
                try:
                    scene_coll.children.link(coll)
                except RuntimeError:
                    pass

                png = os.path.join(tmpdir, f'{coll.name}.png')
                render_and_load_preview(coll, png)

                try:
                    scene_coll.children.unlink(coll)
                except RuntimeError:
                    pass

                status['cat_done'] = ai + 1
                yield
        finally:
            # Drop the preview camera before save — it was internal-
            # use only and shouldn't ship inside the asset library.
            cam_obj = bpy.data.objects.get(_PREVIEW_CAMERA_NAME)
            if cam_obj is not None:
                cam_data = cam_obj.data
                bpy.data.objects.remove(cam_obj)
                if cam_data is not None and cam_data.users == 0:
                    bpy.data.cameras.remove(cam_data)
            shutil.rmtree(tmpdir, ignore_errors=True)

        # Save back over the original.
        bpy.ops.wm.save_as_mainfile(
            filepath=blend_path, compress=True)
        yield

    status['blend_done'] = len(blends)
    status['phase'] = 'done'


def link_or_copy_textures(src: str, dst: str, prefer_copy: bool = False):
    """Make ``dst`` point at ``src``'s contents.

    Default behaviour: try symlink first (zero-cost, no duplication);
    fall back to a real copy if Windows refuses (no dev-mode/admin).

    ``prefer_copy=True`` skips the symlink attempt entirely. Used when
    the caller intends to delete ``src`` afterwards — a symlink into
    a folder we're about to wipe would leave the library with broken
    texture references.
    """
    if not os.path.isdir(src):
        print(f"[Build Library] WARN: textures source not found: {src}")
        return
    if os.path.exists(dst):
        # If existing dst is a symlink and prefer_copy is requested,
        # replace the symlink with a real copy. Otherwise leave alone.
        if prefer_copy and os.path.islink(dst):
            print(f"[Build Library] replacing symlink {dst} with real copy")
            os.unlink(dst)
        else:
            print(f"[Build Library] textures dir already exists: {dst}")
            return
    if not prefer_copy:
        try:
            os.symlink(src, dst, target_is_directory=True)
            print(f"[Build Library] symlinked {dst} → {src}")
            return
        except (OSError, NotImplementedError) as e:
            print(f"[Build Library] symlink failed ({e}), falling back to copy")

    print(f"[Build Library] copying {src} → {dst} (this may take a while)")
    shutil.copytree(src, dst, dirs_exist_ok=False)
    print(f"[Build Library] copy done")


# ────────────────────────────────────────────────────────────────────
# Top-level orchestrator — generator
# ────────────────────────────────────────────────────────────────────

def build_library_iter(cache_dir: str,
                       game_root: str,
                       output_dir: str,
                       status: dict,
                       *,
                       no_preview: bool = False,
                       preview_size: int = 128,
                       limit: int = 0,
                       categories: Optional[set] = None,
                       skip_existing: bool = False,
                       quiet_alpha: bool = True,
                       dry_run: bool = False,
                       delete_cache_after: bool = False,
                       game: str = 'SA') -> Iterator[None]:
    """Drive the full build pipeline as a generator. Yields ``None`` at
    every meaningful checkpoint (per-asset, between phases). Updates
    ``status`` in-place — operator/CLI both read fields off it.

    ``status`` keys populated:
        'phase'   : 'classify' | 'scan' | 'build' | 'finalize' | 'done'
        'category': current category
        'cat_done', 'cat_total', 'cat_ok', 'cat_fail',
        'cat_preview_ok', 'cat_preview_fail'
        'current_asset': name of asset currently being processed
        'classified', 'unclassified': dict scan counts after phase 'scan'
    """
    if not os.path.isdir(cache_dir):
        raise FileNotFoundError(f"cache dir not found: {cache_dir}")
    if not os.path.isdir(game_root):
        raise FileNotFoundError(f"game root not found: {game_root}")
    os.makedirs(output_dir, exist_ok=True)

    # ── classify ──────────────────────────────────────────────
    status['phase'] = 'classify'
    yield
    print(f"[1/4] Reading IDE files (game={game})...")
    classification = build_classification(game_root, game=game)
    print(f"      {len(classification)} model names classified")
    yield

    # ── scan ──────────────────────────────────────────────────
    status['phase'] = 'scan'
    yield
    print("[2/4] Scanning cache for DFFs...")
    by_category, unclassified = scan_cache(cache_dir, classification)
    classified_count = sum(len(v) for v in by_category.values())
    print(f"      {classified_count} classified, {len(unclassified)} unclassified")
    for cat in sorted(by_category):
        print(f"        {cat:30s} {len(by_category[cat]):>5}")
    if unclassified:
        with open(os.path.join(output_dir, '_unclassified.txt'),
                  'w', encoding='utf-8') as f:
            for n in unclassified:
                f.write(n + '\n')
    status['classified'] = classified_count
    status['unclassified'] = len(unclassified)
    status['by_category'] = {k: len(v) for k, v in by_category.items()}
    yield

    if dry_run:
        status['phase'] = 'done'
        return

    # ── build per category ────────────────────────────────────
    status['phase'] = 'build'
    yield
    print("[3/4] Building .blend files...")
    catalog = CatalogTree()
    # Pre-populate catalog UUIDs for every category that the cache
    # actually has DFFs for — vanilla fixed buckets AND dynamic per-
    # region map categories (LA/SF/etc. + any custom modpack regions).
    # This way cats.txt is consistent even if the user runs
    # ``--categories X`` (only one category gets built but the tree
    # still shows all of them).
    for cat in by_category:
        catalog.get_uuid(get_catalog_path(cat))

    tex_dir = os.path.join(cache_dir, 'textures')
    cats_to_build = sorted(by_category)
    if categories is not None:
        cats_to_build = [c for c in cats_to_build if c in categories]

    for cat in cats_to_build:
        items = by_category[cat]
        if limit:
            items = items[:limit]
        if not items:
            continue
        for _ in build_category_blend_iter(
                cat, items, output_dir, catalog, tex_dir, status,
                generate_preview=not no_preview,
                preview_size=preview_size,
                skip_existing=skip_existing,
                quiet_alpha=quiet_alpha):
            yield

    # ── finalize ──────────────────────────────────────────────
    status['phase'] = 'finalize'
    yield
    print("[4/4] Finalizing...")
    catalog.write(os.path.join(output_dir, 'blender_assets.cats.txt'))

    # If the user asked to delete the cache afterwards, force-copy the
    # textures (don't symlink) so the library stays self-contained
    # after we wipe the source folder.
    library_tex = os.path.join(output_dir, 'textures')
    link_or_copy_textures(tex_dir, library_tex, prefer_copy=delete_cache_after)

    if delete_cache_after:
        # Sanity check before wiping: textures must actually be a real
        # copy in the library, not a symlink. If symlink replacement
        # failed for some reason, refuse to delete — better to leave
        # an extra few GB on disk than corrupt the user's library.
        safe = (os.path.isdir(library_tex)
                and not os.path.islink(library_tex))
        if safe:
            png_count = sum(1 for f in os.listdir(library_tex)
                            if f.lower().endswith('.png'))
            if png_count == 0:
                safe = False
                print("[Build Library] WARN: library textures empty, "
                      "cache NOT deleted")
        else:
            print("[Build Library] WARN: library textures missing or "
                  "still a symlink, cache NOT deleted")

        if safe:
            print(f"[Build Library] deleting cache: {cache_dir}")
            shutil.rmtree(cache_dir, ignore_errors=True)
            print("[Build Library] cache deleted")

    status['phase'] = 'done'
    print("[Build Library] DONE")
