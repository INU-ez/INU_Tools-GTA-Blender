# INU_tools.tools.model_utils — Model detection utilities and geometry checks

import bpy
import re

# Blender appends `.001`, `.002`, … when a name collides on import or
# duplicate. Strip the suffix before any suffix/prefix-based type
# detection so `ali_road_sign_1_col.007` is still recognised as COL.
_BLENDER_DUP_SUFFIX = re.compile(r'\.\d{3}$')


def remap_copied_parents(sources, copies):
    """Keep copied model parts and 2DFX attached to their own instance."""
    mapping = dict(zip(sources, copies))
    for source, copy in mapping.items():
        if source.parent in mapping:
            copy.parent = mapping[source.parent]


def _strip_dup_suffix(name: str) -> str:
    return _BLENDER_DUP_SUFFIX.sub('', name)



def _get_suffixes():
    """Get custom suffixes from scene settings or use defaults."""
    scene = bpy.context.scene
    return {
        'DFF': getattr(scene.inu_settings, 'gtatools_suffix_dff', '_DFF'),
        'LOD': getattr(scene.inu_settings, 'gtatools_suffix_lod', '_LOD'),
        'COL': getattr(scene.inu_settings, 'gtatools_suffix_col', '_COL'),
    }


def _get_prefixes():
    """Get custom prefixes from scene settings or use defaults."""
    scene = bpy.context.scene
    return {
        'DFF': getattr(scene.inu_settings, 'gtatools_prefix_dff', ''),
        'LOD': getattr(scene.inu_settings, 'gtatools_prefix_lod', 'LOD'),
        'COL': getattr(scene.inu_settings, 'gtatools_prefix_col', ''),
    }


def _mesh_has_textured_material(obj):
    """True if any of OBJ's materials references an image texture.

    The signal that tells a visible DFF (textured) from collision (no texture)
    when nothing else does. Errs toward DFF — a non-mesh, or a material setup
    we can't read, returns True so a real model is never shoved into collision.
    No materials at all, or materials with no image, → False (collision)."""
    if getattr(obj, 'type', None) != 'MESH':
        return True
    data = getattr(obj, 'data', None)
    mats = [m for m in (getattr(data, 'materials', None) or []) if m is not None]
    if not mats:
        return False
    for mat in mats:
        # Round-trip texture name stamped by the DFF importer / material panel.
        inu = getattr(mat, 'inu', None)
        if inu is not None and (getattr(inu, 'texture_name', '') or '').strip():
            return True
        if getattr(mat, 'use_nodes', False) and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and getattr(node, 'image', None):
                    return True
    return False


def get_model_type(obj):
    """Determine a mesh's model type — ``LOD`` / ``COL`` / ``DFF`` — plus its
    base name (the name with the type marker stripped, for DFF↔LOD↔COL
    pairing).

    Detection is automatic and layered; the _DFF/_LOD/_COL suffixes survive
    only as a manual OVERRIDE (their customisation UI was removed). The
    authoritative tier order lives in core.model_classify.classify_model:

      1. explicit ``_SHA`` / suffix / prefix marker on the name → that type;
      2. ``inu.type`` of COL/SHA (stamped by the COL importer or Batch Set
         Type) → COL — checked BEFORE the LOD rule, so a tagged collision
         with an accidental «lod» in its name stays COL;
      3. a «lod» token at a word edge or an uppercase ``LOD`` marker
         (см. model_classify._is_scene_lod_name) → LOD;
      4. otherwise textured material → DFF, no texture → COL.

    Returns ``(model_type, base_name)``."""
    if obj is None:
        return None, None
    from ..core.model_classify import classify_model
    # Strip Blender's `.001`/`.002`/… duplicate suffix before classification.
    name = _strip_dup_suffix(obj.name)
    inu = getattr(obj, 'inu', None)
    inu_type = getattr(inu, 'type', 'OBJ') if inu is not None else 'OBJ'
    # has_texture is a lambda — the material scan only runs if classification
    # actually falls through to the texture tier.
    return classify_model(
        name,
        has_texture=lambda: _mesh_has_textured_material(obj),
        inu_type=inu_type,
        suffixes=_get_suffixes(),
        prefixes=_get_prefixes(),
    )


def is_collision_mesh(obj):
    """True when OBJ must be exported as collision — embedded CHUNK_COLLISION_MODEL
    in the .dff, or a .col mesh — instead of visible geometry.

    The ``inu.type`` COL/SHA tag is the signal, EXCEPT when the object name
    carries an explicit ``_DFF``/``_LOD`` marker: a deliberate name marker
    outranks the tag, same tier order as classify_model. Without that guard a
    stale COL tag (inherited by Shift+D from a collision mesh, or left over
    from Batch Set Type) on a ``*_LOD`` mesh silently wrote a DFF with an EMPTY
    GeometryList — collision only, so the model never rendered in game.

    Empties are never collision here: sphere/box primitives are recognised
    separately by dff_export._is_col_primitive_empty."""
    if getattr(obj, 'type', None) != 'MESH':
        return False
    inu = getattr(obj, 'inu', None)
    if getattr(inu, 'type', 'OBJ') not in ('COL', 'SHA'):
        return False
    from ..core.model_classify import explicit_name_type
    marker, _ = explicit_name_type(
        _strip_dup_suffix(obj.name), _get_suffixes(), _get_prefixes())
    return marker not in ('DFF', 'LOD')


# ── UI-only classification cache ──────────────────────────────────────
# get_model_type falls through to _mesh_has_textured_material, which walks
# each material's node tree for untagged meshes. It's called from several
# panel draw() methods EVERY redraw — on a big scene (and worst of all when
# nothing is selected, so the export panel scans the whole active
# collection) that per-redraw scan is what makes the UI lag (e.g. a dropdown
# feels like it "hangs" because opening it forces a repaint).
#
# This cache is for DRAW code ONLY. Export / validate keep calling
# get_model_type directly so their routing is always freshly computed —
# never trust the cache for anything that writes files. The cache is cleared
# on every depsgraph update (any rename / retag / material edit fires one),
# so idle redraws are free while the result stays correct.
_MODEL_TYPE_CACHE = {}


def invalidate_model_type_cache(_scene=None, depsgraph=None):
    """Drop the UI classification cache (registered on depsgraph_update_post).

    Marked persistent (survives .blend loads) in __init__.register() rather
    than with a module-level @bpy.app.handlers.persistent decorator — the
    latter runs at import and would break bpy-less unit tests (their stub
    has no bpy.app).

    A transform-only update batch is skipped: dragging an object fires a
    depsgraph update EVERY frame, and clearing here meant the export
    panel re-classified its whole fallback set (the active collection,
    when nothing is selected) on every one of those frames. Moving a mesh
    can't change whether it's a DFF, a LOD or a COL, so the cache is left
    alone and the drag stays smooth.

    Точечная инвалидация: чистим кэш ТОЛЬКО у объектов, что реально изменились
    (``depsgraph.updates``), а не весь. Иначе выбор материала / генерация превью
    (оба сыплют depsgraph-апдейтами) сбрасывали кэш целиком, и N-панель
    переклассифицировала ВСЕ объекты каждый redraw → лаг при работе с
    материалами. Объект, которому меняют материал/данные, приходит в updates,
    так что его запись чистится; export всё равно классифицирует свежо."""
    from .draw_cache import is_transform_only
    if is_transform_only(depsgraph):
        return
    if depsgraph is None or not _MODEL_TYPE_CACHE:
        _MODEL_TYPE_CACHE.clear()
        return
    try:
        for upd in depsgraph.updates:
            nm = getattr(getattr(upd, 'id', None), 'name', None)
            if nm is not None:
                _MODEL_TYPE_CACHE.pop(nm, None)
    except Exception:                                   # noqa: BLE001
        _MODEL_TYPE_CACHE.clear()


def get_model_type_cached(obj):
    """Cached get_model_type for panel draw() — see _MODEL_TYPE_CACHE. Do NOT
    use in export/validate paths (they must classify fresh)."""
    if obj is None:
        return None, None
    key = obj.name
    hit = _MODEL_TYPE_CACHE.get(key)
    if hit is not None:
        return hit
    res = get_model_type(obj)
    _MODEL_TYPE_CACHE[key] = res
    return res


def find_related_models(base_name):
    """Найти связанные модели (DFF, LOD, COL) по базовому имени"""
    models = {
        'DFF': None,
        'LOD': None,
        'COL': None
    }

    base_upper = base_name.upper()

    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue

        name_upper = obj.name.upper()

        # Проверяем DFF (base, base_dff, baseDFF)
        if name_upper == base_upper:
            models['DFF'] = obj
        elif name_upper == base_upper + '_DFF' or name_upper == base_upper + 'DFF':
            models['DFF'] = obj

        # Проверяем LOD (base_lod, baseLOD)
        if name_upper == base_upper + '_LOD' or name_upper == base_upper + 'LOD':
            models['LOD'] = obj

        # Проверяем COL (base_col, baseCOL)
        if name_upper == base_upper + '_COL' or name_upper == base_upper + 'COL':
            models['COL'] = obj

    return models


def find_selected_models(classify=None):
    """Найти модели DFF, LOD, COL только среди выделенных объектов.

    `classify` — функция классификации (по умолчанию get_model_type). UI
    передаёт get_model_type_cached, чтобы не сканировать материалы каждый
    redraw; экспорт-операторы оставляют дефолт (всегда свежая классификация).
    """
    classify = classify or get_model_type
    models = {
        'DFF': None,
        'LOD': None,
        'COL': None
    }

    for obj in bpy.context.selected_objects:
        if obj.type != 'MESH':
            continue

        model_type, base_name = classify(obj)

        if model_type and models[model_type] is None:
            models[model_type] = obj

    return models


def _get_active_collection_objects():
    """Get mesh objects from active collection (including child collections)."""
    col = bpy.context.collection
    if col is None or col == bpy.context.scene.collection:
        return []
    objects = []
    def _collect(c):
        for obj in c.objects:
            if obj.type == 'MESH':
                objects.append(obj)
        for child in c.children:
            _collect(child)
    _collect(col)
    return objects


def find_all_selected_model_groups(classify=None):
    """Find all DFF/LOD/COL model groups among selected objects, grouped by base_name.
    Falls back to active collection if nothing is selected.

    `classify` — см. find_selected_models. UI передаёт кэш-версию (иначе на
    большой сцене с пустым выделением скан всей активной коллекции гонится
    каждый redraw → лаги); экспорт — дефолт (свежая классификация)."""
    classify = classify or get_model_type
    groups = {}  # {base_name: {'DFF': obj, 'LOD': obj, 'COL': obj}}

    source = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    if not source:
        source = _get_active_collection_objects()

    for obj in source:
        model_type, base_name = classify(obj)
        if not base_name:
            continue

        # Нормализуем base_name (убираем _ в конце если есть)
        base_name_clean = base_name.rstrip('_')

        if base_name_clean not in groups:
            groups[base_name_clean] = {'DFF': None, 'LOD': None, 'COL': None}

        if model_type and groups[base_name_clean][model_type] is None:
            groups[base_name_clean][model_type] = obj

    return groups


def get_base_name_from_selected():
    """Получить базовое имя из выделенных моделей"""
    models = find_selected_models()

    # Берём имя из первой найденной модели
    if models['DFF']:
        _, base_name = get_model_type(models['DFF'])
        return base_name
    elif models['LOD']:
        _, base_name = get_model_type(models['LOD'])
        return base_name
    elif models['COL']:
        _, base_name = get_model_type(models['COL'])
        return base_name

    return None


def fix_col_model_name(col_path, model_name):
    """
    Исправить имя модели внутри COL файла после экспорта.

    Структура COL заголовка:
    - Offset 0-3: Magic (COLL/COL2/COL3/COL4)
    - Offset 4-7: File size (uint32)
    - Offset 8-29: Model name (22 bytes, null-terminated)
    - Offset 30-31: Model ID (uint16)

    Args:
        col_path: Путь к COL файлу
        model_name: Имя модели для записи (без расширения .col)

    Returns:
        True если успешно, False если ошибка
    """
    try:
        # Читаем файл
        with open(col_path, 'rb') as f:
            data = bytearray(f.read())

        if len(data) < 32:
            return False

        # Проверяем что это COL файл
        magic = data[0:4]
        if magic not in (b'COLL', b'COL2', b'COL3', b'COL4'):
            return False

        # Убираем расширение .col если есть
        if model_name.lower().endswith('.col'):
            model_name = model_name[:-4]

        # Кодируем имя модели (макс 21 символ + null terminator)
        # Пробуем ASCII, если не получается - используем latin-1 с заменой
        try:
            name_bytes = model_name.encode('ascii')
        except UnicodeEncodeError:
            # Для кириллицы и других символов - транслитерация или замена
            name_bytes = model_name.encode('latin-1', errors='replace')

        # Обрезаем до 21 байта (22-й = null terminator)
        name_bytes = name_bytes[:21]

        # Дополняем нулями до 22 байт
        name_bytes = name_bytes.ljust(22, b'\x00')

        # Записываем имя модели в заголовок (offset 8)
        data[8:30] = name_bytes

        # Сохраняем файл
        with open(col_path, 'wb') as f:
            f.write(data)

        return True

    except Exception as e:
        print(f"fix_col_model_name error: {e}")
        return False


# =============================================================================
# GEOMETRY CHECK FUNCTIONS
# =============================================================================

def bmesh_from_object_safe(obj):
    """Вернуть (bmesh, None) или (None, error_str).

    Чинит случай, когда ``obj.data`` — не обычный ``bpy.types.Mesh`` (напр.
    'FastMesh' от стороннего аддона / спец-состояние Blender 5.x), из-за
    чего ``bmesh.from_mesh`` бросает TypeError. Тогда читаем вычисленную
    копию меша через ``to_mesh()``. Вызывающий обязан сделать ``bm.free()``."""
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        return bm, None
    except (TypeError, RuntimeError):
        try:
            bm.free()
        except Exception:
            pass
    bm = bmesh.new()
    ev = None
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        bm.from_mesh(ev.to_mesh())
        return bm, None
    except Exception:
        try:
            bm.free()
        except Exception:
            pass
        return None, "Неподдерживаемый тип меша (%s)" % type(obj.data).__name__
    finally:
        if ev is not None:
            try:
                ev.to_mesh_clear()
            except Exception:
                pass


def check_loose_geometry(obj):
    """Проверить объект на висящие вершины и рёбра (не присоединённые к полигонам)"""
    if obj is None or obj.type != 'MESH':
        return None, None, "Не меш объект"

    bm, err = bmesh_from_object_safe(obj)
    if err:
        return None, None, err

    # Находим висящие вершины (не принадлежат ни одному face)
    loose_verts = [v.index for v in bm.verts if not v.link_faces]

    # Находим висящие рёбра (не принадлежат ни одному face)
    loose_edges = [e.index for e in bm.edges if not e.link_faces]

    bm.free()

    return loose_verts, loose_edges, None


def get_model_textures(obj):
    """Get all textures used by object's materials"""
    textures = []

    if obj is None or obj.type != 'MESH':
        return textures

    for mat_slot in obj.material_slots:
        mat = mat_slot.material
        if not mat or not mat.use_nodes:
            continue

        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                if node.image not in textures:
                    textures.append(node.image)

    return textures
