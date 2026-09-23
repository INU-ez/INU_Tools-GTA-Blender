# INU_tools.ops.plants_ops — import / edit / export data/plants.dat
# (procedural grass definitions for CPlantMgr). See core/plants_dat.py
# for the file format and ui/panels.py for the «Трава» panel.

import math
import os
import random
import shutil

import bpy
import bmesh
from bpy.props import IntProperty
from mathutils import Vector

from .. import T
from ..core import plants_dat
from ..data.surface_materials import (
    get_surface_name, resolve_surface_id, get_surface_color,
    get_surface_material_name,
)

_PREVIEW_TAG = "inu_grass_preview"
_PREVIEW_MAT = "INU_GrassPreview"
_PREVIEW_ATTR = "GrassCol"
# Permanent grass geometry (exported with the model), vs the temporary
# preview above.
_GEO_TAG = "inu_grass_geometry"
_GEO_MAT = "INU_GrassGeo"

# Internal safety cap — the preview uses the real plants.dat densities
# (no separate preview knobs), so this just stops a runaway terrain from
# freezing Blender. Not a user-facing setting.
_PREVIEW_CAP = 300000


def _engine_surface_names():
    """COLPOINT surface names ``SurfaceInfos_c::GetSurfaceIdFromName``
    resolves (ids 0..177): our table + the game's abbreviations. An entry
    with any other name makes LoadPlantsDat return false → no grass."""
    from ..data.surface_materials import (
        GTA_SA_SURFACE_MATERIALS, _COLPOINT_NAME_OVERRIDE)
    names = {name for _sid, name, _d in GTA_SA_SURFACE_MATERIALS}
    names.update(_COLPOINT_NAME_OVERRIDE.values())
    return names


def _resolve_path(context, *, must_exist):
    """Resolve the plants.dat path: explicit setting, else <GameRoot>/data.
    Returns an absolute path or '' if it can't be determined."""
    s = context.scene.inu_settings
    p = (s.gtatools_plants_dat_path or "").strip()
    if p:
        p = bpy.path.abspath(p)
        if must_exist and not os.path.isfile(p):
            return ''
        return p
    root = (getattr(s, 'gtatools_game_root', '') or "").strip()
    if root:
        cand = os.path.join(bpy.path.abspath(root), 'data', 'plants.dat')
        if not must_exist or os.path.isfile(cand):
            return cand
    return ''


def _entry_to_dict(item):
    return {key: getattr(item, key) for key, _kind in plants_dat.PLANTS_FIELDS}


def _dict_to_item(item, data):
    for key, _kind in plants_dat.PLANTS_FIELDS:
        if key in data:
            setattr(item, key, data[key])


class GTATOOLS_OT_grass_import(bpy.types.Operator):
    """Загрузить строки из plants.dat в список для редактирования.
    Текущий список будет заменён."""
    bl_idname = "gtatools.grass_import"
    bl_label = "INU: Import plants.dat"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        path = _resolve_path(context, must_exist=True)
        if not path:
            self.report({'ERROR'}, T("plants.dat не найден — укажи путь или Game Root"))
            return {'CANCELLED'}
        try:
            with open(path, encoding='latin-1') as f:
                text = f.read()
        except OSError as e:
            self.report({'ERROR'}, f"{T('Ошибка чтения:')} {e}")
            return {'CANCELLED'}

        entries, skipped = plants_dat.parse_plants_dat(text)
        s = context.scene.inu_settings
        s.gtatools_grass_entries.clear()
        for e in entries:
            item = s.gtatools_grass_entries.add()
            _dict_to_item(item, e)
        s.gtatools_grass_index = 0
        msg = f"{T('Загружено записей:')} {len(entries)}"
        if skipped:
            msg += f"  ({T('пропущено строк:')} {len(skipped)})"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_grass_export(bpy.types.Operator):
    """Записать список обратно в plants.dat. Старый файл сохраняется
    рядом как plants.dat.bak."""
    bl_idname = "gtatools.grass_export"
    bl_label = "INU: Export plants.dat"
    bl_options = {'REGISTER'}

    def execute(self, context):
        s = context.scene.inu_settings
        entries = [_entry_to_dict(it) for it in s.gtatools_grass_entries]
        if not entries:
            self.report({'WARNING'}, T("Список пуст — нечего экспортировать"))
            return {'CANCELLED'}

        path = _resolve_path(context, must_exist=False)
        if not path:
            self.report({'ERROR'}, T("Укажи путь к plants.dat или Game Root"))
            return {'CANCELLED'}

        bak = path + '.bak'
        # Preserve the game's exact formatting: use the pristine original as
        # a template (the .bak holds it once made; else the current file).
        template = None
        for src in (bak, path):
            if os.path.isfile(src):
                try:
                    # newline='' preserves the original CRLF/LF exactly.
                    with open(src, encoding='latin-1', newline='') as f:
                        template = f.read()
                    break
                except OSError:
                    pass
        if template:
            text = plants_dat.rewrite_plants_dat(template, entries)
        else:
            text = plants_dat.format_plants_dat(entries)

        try:
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            # Back up the true original only once (don't clobber it with
            # our own later exports).
            if os.path.isfile(path) and not os.path.isfile(bak):
                shutil.copy2(path, bak)
            # newline='' → write our exact CRLF, no extra translation.
            with open(path, 'w', encoding='latin-1', newline='') as f:
                f.write(text)
        except OSError as e:
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'CANCELLED'}

        # DAT-46: known surface names, 18 tokens, ≤ 57 surfaces, slot /
        # model / uv ≤ 3 — an offending line silently disables ALL grass.
        try:
            from ..core.textdata_lint import check_plants
            from .textdata_audit import report_lint
            report_lint(self, os.path.basename(path),
                        *check_plants(entries, _engine_surface_names()))
        except Exception as e:                       # noqa: BLE001
            print(f"[INU lint] plants audit failed: {e}")
        self.report({'INFO'}, f"{T('Записано в')} {path} ({len(entries)})")
        return {'FINISHED'}


class GTATOOLS_OT_grass_add(bpy.types.Operator):
    """Добавить новую запись травы. Имя поверхности берётся из активного
    COL-материала, если он есть."""
    bl_idname = "gtatools.grass_add"
    bl_label = "INU: Add grass entry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.inu_settings
        item = s.gtatools_grass_entries.add()
        _dict_to_item(item, plants_dat.DEFAULT_ENTRY)
        # Prefill the surface name from the active material's COL surface.
        obj = context.active_object
        mat = getattr(obj, 'active_material', None) if obj else None
        inu = getattr(mat, 'inu', None) if mat else None
        if inu is not None:
            item.name = get_surface_name(getattr(inu, 'col_mat_index', 0))
        s.gtatools_grass_index = len(s.gtatools_grass_entries) - 1
        return {'FINISHED'}


class GTATOOLS_OT_grass_remove(bpy.types.Operator):
    """Удалить выбранную запись травы."""
    bl_idname = "gtatools.grass_remove"
    bl_label = "INU: Remove grass entry"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        s = context.scene.inu_settings
        idx = self.index if self.index >= 0 else s.gtatools_grass_index
        if not (0 <= idx < len(s.gtatools_grass_entries)):
            return {'CANCELLED'}
        s.gtatools_grass_entries.remove(idx)
        s.gtatools_grass_index = min(idx, len(s.gtatools_grass_entries) - 1)
        return {'FINISHED'}


# ── Scatter preview ──────────────────────────────────────────────────
# Build a real mesh of grass "cards" (crossed quads) on the selected COL
# mesh so the user can see where / how much / what colour grass will
# generate — driven by the plants.dat entries + face surface materials.

def _load_grass_images(context):
    """Load the grass .txd once. Returns {lowercase_name: bpy.Image}."""
    path = (context.scene.inu_settings.gtatools_grass_txd_path or "").strip()
    if not path:
        return {}
    path = bpy.path.abspath(path)
    if not os.path.isfile(path):
        return {}
    try:
        from ..core.txd import read_txd_file
        from .txd_import import _textures_to_blender_images
        images = _textures_to_blender_images(read_txd_file(path))
    except Exception as e:
        print(f"[INU grass] txd load failed: {e}")
        return {}
    return {img.name.lower(): img for img in images}


def _slot_available_tex(images, slot_id):
    """Texture indices present for a slot: scans txgrass{slot}_N keys.

    The sprite is chosen by UVoff, NOT ModelID — ModelID is the geometry
    submodel. In plants.dat ModelID is almost always 0 while UVoff varies
    0..3, matching the 4 txgrass{slot}_0..3 textures."""
    out = []
    prefix = f"txgrass{slot_id}_"
    for k in images:
        if k.startswith(prefix) and k[len(prefix):].isdigit():
            out.append(int(k[len(prefix):]))
    return sorted(out)


def _grass_texture(images, slot_id, tex_id):
    """Exact sprite ``txgrass{SlotID}_{UVoff}`` or None (no arbitrary
    fallback — a wrong sprite is worse than a flat card)."""
    return images.get(f"txgrass{slot_id}_{tex_id}") if images else None


def _grass_preview_material(image, name):
    """Build a preview material named `name`. Flat vertex-colour card if
    `image` is None; otherwise textured (sprite × colour tint, alpha-clip)."""
    from ..tools.compat import material_enable_nodes, make_mix_rgba
    mat = bpy.data.materials.new(name)
    material_enable_nodes(mat)
    mat.diffuse_color = (0.30, 0.55, 0.18, 1.0)  # solid-view fallback
    nt = getattr(mat, 'node_tree', None)
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None) if nt else None
    if bsdf is None:
        return mat

    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = _PREVIEW_ATTR
    vc.location = (bsdf.location.x - 700, bsdf.location.y)

    if image is None:
        nt.links.new(vc.outputs['Color'], bsdf.inputs['Base Color'])
        return mat

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.location = (bsdf.location.x - 700, bsdf.location.y + 300)
    mix = make_mix_rgba(nt.nodes, blend='MULTIPLY')   # sprite × colour tint
    mix.node.location = (bsdf.location.x - 350, bsdf.location.y)
    mix.factor.default_value = 1.0
    nt.links.new(tex.outputs['Color'], mix.a)
    nt.links.new(vc.outputs['Color'], mix.b)
    nt.links.new(mix.result, bsdf.inputs['Base Color'])
    alpha_in = bsdf.inputs.get('Alpha')
    if alpha_in is not None:
        nt.links.new(tex.outputs['Alpha'], alpha_in)
    # Alpha cutout so grass silhouettes show (both legacy + EEVEE Next).
    try:
        mat.blend_method = 'CLIP'
    except (AttributeError, TypeError):
        pass
    try:
        mat.surface_render_method = 'DITHERED'
    except (AttributeError, TypeError):
        pass
    mat.use_backface_culling = False
    return mat


def _add_cross_card(verts, faces, cols, uvs, p, w, h, col, ang):
    """Append a crossed-quad grass card (8 verts, 2 faces) at world point
    p. Each quad is UV-mapped to the full sprite (0..1)."""
    base = len(verts)
    for dx, dy in ((math.cos(ang), math.sin(ang)),
                   (-math.sin(ang), math.cos(ang))):
        hx, hy = dx * w * 0.5, dy * w * 0.5
        verts.append((p.x - hx, p.y - hy, p.z))
        verts.append((p.x + hx, p.y + hy, p.z))
        verts.append((p.x + hx, p.y + hy, p.z + h))
        verts.append((p.x - hx, p.y - hy, p.z + h))
    faces.append((base, base + 1, base + 2, base + 3))
    faces.append((base + 4, base + 5, base + 6, base + 7))
    cols.extend([col] * 8)
    quad_uv = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    uvs.extend(quad_uv)   # face 1 loops
    uvs.extend(quad_uv)   # face 2 loops


def _clear_preview():
    """Remove any existing preview objects, orphan mesh data and the
    preview materials (txd images are shared → left in place)."""
    for obj in [o for o in bpy.data.objects if o.get(_PREVIEW_TAG)]:
        me = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    for mat in [m for m in bpy.data.materials if m.name.startswith(_PREVIEW_MAT)]:
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def _build_grass(context, name, tag, mat_prefix, hide_select):
    """Scatter grass cards onto selected COL meshes and build a mesh
    object named `name` (tagged `tag`, materials prefixed `mat_prefix`).

    Returns (status, obj, total, truncated); status is 'ok',
    'no_entries' or 'no_faces'. Shared by the temporary preview and the
    permanent (exported) geometry generators."""
    s = context.scene.inu_settings

    # Group grass entries by the surface ID they target.
    entries_by_id = {}
    for e in s.gtatools_grass_entries:
        if e.density <= 0.0:
            continue
        sid = resolve_surface_id(e.name)
        if sid is None:
            continue
        entries_by_id.setdefault(sid, []).append(e)
    if not entries_by_id:
        return ('no_entries', None, 0, False)

    images = _load_grass_images(context)
    if images:
        print(f"[INU grass] txd textures: {sorted(images.keys())}")

    slot_avail = {}

    def _avail(slot):
        if slot not in slot_avail:
            slot_avail[slot] = _slot_available_tex(images, slot)
        return slot_avail[slot]

    mat_slot_of = {}
    slot_images = []

    def _mat_slot(img):
        key = img.name if img is not None else ''
        if key not in mat_slot_of:
            mat_slot_of[key] = len(slot_images)
            slot_images.append(img)
        return mat_slot_of[key]

    warned = set()
    gen_map = {}
    rng = random.Random(20240722)
    verts, faces, cols, uvs, card_mat = [], [], [], [], []
    total = 0
    truncated = False

    for obj in context.selected_objects:
        # Never scatter onto our own generated grass objects.
        if obj.type != 'MESH' or obj.get(_PREVIEW_TAG) or obj.get(_GEO_TAG):
            continue
        me = obj.data
        mw = obj.matrix_world
        slot_sid = {}
        for i, slot in enumerate(obj.material_slots):
            inu = getattr(slot.material, 'inu', None) if slot.material else None
            slot_sid[i] = getattr(inu, 'col_mat_index', None) if inu else None

        for poly in me.polygons:
            ents = entries_by_id.get(slot_sid.get(poly.material_index))
            if not ents:
                continue
            pv = [mw @ me.vertices[vi].co for vi in poly.vertices]
            if len(pv) < 3:
                continue
            tris = [(pv[0], pv[k], pv[k + 1]) for k in range(1, len(pv) - 1)]
            areas = [(b - a).cross(c - a).length * 0.5 for a, b, c in tris]
            face_area = sum(areas)
            if face_area <= 0.0:
                continue
            for e in ents:
                n = face_area * e.density   # real plants.dat density (per m²)
                count = int(n) + (1 if rng.random() < (n - int(n)) else 0)
                if count <= 0:
                    continue
                w = max(e.scl_xy, 0.01)
                h = max(e.scl_z, 0.01)
                k_i = e.intensity / 255.0
                col = (e.r / 255.0 * k_i, e.g / 255.0 * k_i, e.b / 255.0 * k_i, 1.0)
                if images:
                    avail = _avail(e.slot_id)
                    if e.uv_off in avail:
                        tex_ids = [e.uv_off]
                    else:
                        tex_ids = avail
                        key = (e.slot_id, e.uv_off)
                        if key not in warned:
                            warned.add(key)
                            want = f"txgrass{e.slot_id}_{e.uv_off}"
                            print(f"[INU grass] {e.name}: {want} not in txd; "
                                  f"using slot {e.slot_id} tex {avail or 'NONE→flat'}")
                else:
                    tex_ids = []
                for _ in range(count):
                    if total >= _PREVIEW_CAP:
                        truncated = True
                        break
                    t = rng.random() * face_area
                    acc = 0.0
                    tri = tris[0]
                    for j, ar in enumerate(areas):
                        acc += ar
                        if t <= acc:
                            tri = tris[j]
                            break
                    a, b, c = tri
                    uu, vv = rng.random(), rng.random()
                    if uu + vv > 1.0:
                        uu, vv = 1.0 - uu, 1.0 - vv
                    p = a + (b - a) * uu + (c - a) * vv
                    tex_id = rng.choice(tex_ids) if tex_ids else e.uv_off
                    img = _grass_texture(images, e.slot_id, tex_id)
                    mslot = _mat_slot(img)
                    _add_cross_card(verts, faces, cols, uvs, p, w, h, col,
                                    rng.random() * math.pi)
                    card_mat.append(mslot)
                    total += 1
                    sid_key = slot_sid.get(poly.material_index)
                    g = gen_map.setdefault(sid_key, {
                        'name': e.name, 'slot': e.slot_id,
                        'uv': set(), 'tex': set()})
                    g['uv'].add(tex_id)
                    g['tex'].add(img.name if img is not None else 'flat')
                if truncated:
                    break
            if truncated:
                break
        if truncated:
            break

    if total == 0:
        return ('no_faces', None, 0, False)

    print("[INU grass] surface -> texture mapping:")
    for sid_key, g in sorted(gen_map.items(), key=lambda kv: (kv[0] is None, kv[0])):
        cp = get_surface_name(sid_key) if sid_key is not None else '?'
        print(f"    surface {sid_key} ({cp}) : {g['name']} "
              f"slot={g['slot']} uvoff={sorted(g['uv'])} -> {sorted(g['tex'])}")

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    cattr = mesh.color_attributes.new(name=_PREVIEW_ATTR, type='FLOAT_COLOR', domain='POINT')
    cattr.data.foreach_set("color", [ch for c in cols for ch in c])
    uvlayer = mesh.uv_layers.new(name="UVMap")
    uvlayer.data.foreach_set("uv", [c for uv in uvs for c in uv])
    for i, img in enumerate(slot_images):
        mesh.materials.append(_grass_preview_material(img, f"{mat_prefix}_{i}"))
    mesh.polygons.foreach_set("material_index", [m for m in card_mat for _ in (0, 1)])
    mesh.update()

    ob = bpy.data.objects.new(name, mesh)
    ob[tag] = True
    ob.color = (0.30, 0.55, 0.18, 1.0)
    if hide_select:
        ob.hide_select = True
    context.collection.objects.link(ob)
    return ('ok', ob, total, truncated)


# ── Live preview (auto-refresh while active) ─────────────────────────
_live_last_key = None


def _grass_live_key(context):
    """A cheap signature of everything the preview depends on — used to
    detect changes and rebuild only when something actually changed."""
    s = context.scene.inu_settings
    sel = tuple(sorted(
        o.name for o in context.selected_objects
        if o.type == 'MESH' and not o.get(_PREVIEW_TAG) and not o.get(_GEO_TAG)))
    ents = tuple((
        e.name, round(e.density, 4), e.slot_id, e.model_id, e.uv_off,
        e.r, e.g, e.b, e.intensity, e.var_i, e.alpha,
        round(e.scl_xy, 3), round(e.scl_z, 3),
        round(e.scl_var_xy, 3), round(e.scl_var_z, 3),
        round(e.wbend_scl, 3), round(e.wbend_var, 3),
    ) for e in s.gtatools_grass_entries)
    return (s.gtatools_grass_txd_path, sel, ents)


def _grass_live_timer():
    """Runs while live mode is on; rebuilds the preview when the key
    changes. Returns the next interval, or None to stop the timer."""
    global _live_last_key
    try:
        ctx = bpy.context
        s = ctx.scene.inu_settings
    except Exception:
        return None
    if not getattr(s, 'gtatools_grass_live', False):
        return None
    try:
        key = _grass_live_key(ctx)
    except Exception:
        return 0.3
    if key != _live_last_key:
        _live_last_key = key
        try:
            _clear_preview()
            _build_grass(ctx, _PREVIEW_MAT, _PREVIEW_TAG, _PREVIEW_MAT, hide_select=True)
        except Exception as e:
            print("[INU grass] live rebuild failed:", e)
    return 0.3


def _start_live_timer():
    if not bpy.app.timers.is_registered(_grass_live_timer):
        bpy.app.timers.register(_grass_live_timer, first_interval=0.1)


class GTATOOLS_OT_grass_preview(bpy.types.Operator):
    """Показать траву — переключатель живого предпросмотра. Пока активна,
    трава автоматически обновляется при правке параметров. Нажми ещё раз,
    чтобы убрать."""
    bl_idname = "gtatools.grass_preview"
    bl_label = "INU: Grass live preview"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        s = context.scene.inu_settings
        # Active → turn off and remove.
        if s.gtatools_grass_live or any(o.get(_PREVIEW_TAG) for o in bpy.data.objects):
            s.gtatools_grass_live = False
            _clear_preview()
            return {'FINISHED'}

        # Off → build once and enter live mode (timer keeps it in sync).
        status, ob, total, truncated = _build_grass(
            context, _PREVIEW_MAT, _PREVIEW_TAG, _PREVIEW_MAT, hide_select=True)
        if status == 'no_entries':
            self.report({'WARNING'}, T("Нет grass-записей под материалы сцены — импортируй plants.dat"))
            return {'CANCELLED'}
        if status == 'no_faces':
            self.report({'WARNING'}, T("Нет граней с подходящим grass-материалом на выделении"))
            return {'CANCELLED'}
        global _live_last_key
        _live_last_key = _grass_live_key(context)
        s.gtatools_grass_live = True
        _start_live_timer()
        msg = f"{T('Травинок в предпросмотре:')} {total}"
        if truncated:
            msg += f"  ({T('достигнут лимит')} {_PREVIEW_CAP})"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_grass_preview_clear(bpy.types.Operator):
    """Убрать предпросмотр травы."""
    bl_idname = "gtatools.grass_preview_clear"
    bl_label = "INU: Clear grass preview"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.get(_PREVIEW_TAG) for o in bpy.data.objects)

    def execute(self, context):
        _clear_preview()
        return {'FINISHED'}


def _clear_geometry():
    """Remove previously generated grass-GEOMETRY objects (and orphan data)."""
    for obj in [o for o in bpy.data.objects if o.get(_GEO_TAG)]:
        me = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


class GTATOOLS_OT_grass_generate_geometry(bpy.types.Operator):
    """Сгенерировать траву РЕАЛЬНОЙ ГЕОМЕТРИЕЙ (постоянный меш-объект),
    который экспортируется вместе с моделью. В отличие от предпросмотра —
    объект остаётся в сцене и не удаляется."""
    bl_idname = "gtatools.grass_generate_geometry"
    bl_label = "INU: Generate grass geometry"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        _clear_geometry()
        # Anchor name to the active mesh so it's obvious what it belongs to.
        base = (context.active_object.name if context.active_object else "Grass")
        status, ob, total, truncated = _build_grass(
            context, f"{base}_grass", _GEO_TAG, _GEO_MAT, hide_select=False)
        if status == 'no_entries':
            self.report({'WARNING'}, T("Нет grass-записей под материалы сцены — импортируй plants.dat"))
            return {'CANCELLED'}
        if status == 'no_faces':
            self.report({'WARNING'}, T("Нет граней с подходящим grass-материалом на выделении"))
            return {'CANCELLED'}
        # Select the new object so it's ready to export / join.
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        msg = f"{T('Создана геометрия травы:')} {ob.name} ({total})"
        if truncated:
            msg += f"  ({T('достигнут лимит')} {_PREVIEW_CAP})"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_grass_geometry_clear(bpy.types.Operator):
    """Удалить сгенерированную геометрию травы."""
    bl_idname = "gtatools.grass_geometry_clear"
    bl_label = "INU: Clear grass geometry"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.get(_GEO_TAG) for o in bpy.data.objects)

    def execute(self, context):
        _clear_geometry()
        return {'FINISHED'}


def _ensure_surface_material(obj, sid):
    """Return the slot index of a material on `obj` whose COL surface ==
    sid, creating (and colouring) one if needed."""
    for i, sl in enumerate(obj.material_slots):
        m = sl.material
        inu = getattr(m, 'inu', None) if m else None
        if inu is not None and getattr(inu, 'col_mat_index', None) == sid:
            return i
    mat = bpy.data.materials.new(get_surface_material_name(sid))
    mat.inu.col_mat_index = sid
    col = get_surface_color(sid)
    try:
        from .col_surface_ops import _set_material_base_color
        _set_material_base_color(mat, col)
    except Exception:
        pass
    mat.diffuse_color = col
    obj.data.materials.append(mat)
    return len(obj.data.materials) - 1


class GTATOOLS_OT_grass_apply_surface(bpy.types.Operator):
    """Назначить поверхность выбранной grass-записи выделенным полигонам.
    Материал коллизии с нужным ID создаётся автоматически."""
    bl_idname = "gtatools.grass_apply_surface"
    bl_label = "INU: Apply grass surface to faces"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        s = context.scene.inu_settings
        idx = s.gtatools_grass_index
        entries = s.gtatools_grass_entries
        if not (0 <= idx < len(entries)):
            self.report({'ERROR'}, T("Нет выбранной записи травы"))
            return {'CANCELLED'}
        sid = resolve_surface_id(entries[idx].name)
        if sid is None:
            self.report({'ERROR'}, T("Неизвестная поверхность записи"))
            return {'CANCELLED'}

        obj = context.active_object
        slot_idx = _ensure_surface_material(obj, sid)

        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(obj.data)
            sel = [f for f in bm.faces if f.select]
            if not sel:
                self.report({'WARNING'}, T("Не выделено ни одного полигона"))
                return {'CANCELLED'}
            for f in sel:
                f.material_index = slot_idx
            bmesh.update_edit_mesh(obj.data)
            n = len(sel)
        else:
            polys = [p for p in obj.data.polygons if p.select]
            if not polys:
                self.report({'WARNING'}, T("Не выделено ни одного полигона"))
                return {'CANCELLED'}
            for p in polys:
                p.material_index = slot_idx
            obj.data.update()
            n = len(polys)

        name = get_surface_name(sid)
        self.report({'INFO'}, f"{T('Назначено полигонам:')} {n} — {sid} ({name})")
        return {'FINISHED'}


class GTATOOLS_OT_grass_duplicate(bpy.types.Operator):
    """Дублировать выбранную запись (удобно для второго PCDid одной
    поверхности)."""
    bl_idname = "gtatools.grass_duplicate"
    bl_label = "INU: Duplicate grass entry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.inu_settings
        idx = s.gtatools_grass_index
        if not (0 <= idx < len(s.gtatools_grass_entries)):
            return {'CANCELLED'}
        src = _entry_to_dict(s.gtatools_grass_entries[idx])
        item = s.gtatools_grass_entries.add()
        _dict_to_item(item, src)
        # Move the new item right after the source.
        new_idx = len(s.gtatools_grass_entries) - 1
        s.gtatools_grass_entries.move(new_idx, idx + 1)
        s.gtatools_grass_index = idx + 1
        return {'FINISHED'}
