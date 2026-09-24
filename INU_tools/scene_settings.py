# INU_tools.scene_settings
#
# Consolidated PropertyGroup for all Scene-level settings — registered
# in __init__.py as ``bpy.types.Scene.inu_settings``.
#
# Per Blender extensions ToS, the addon's ``register()`` should declare
# Scene properties via a single PropertyGroup, not 131 separate
# ``bpy.types.Scene.X = ...`` calls. All legacy field names keep the
# ``gtatools_`` prefix verbatim so the load_post migration handler in
# __init__.py can copy values from old scenes byte-for-byte.

import os

import bpy
from bpy.props import (
    StringProperty, BoolProperty, IntProperty, FloatProperty,
    EnumProperty, FloatVectorProperty, CollectionProperty,
    BoolVectorProperty,
    PointerProperty,
)
# T() = locale lookup (Russian source → active language). Safe to import
# here: __init__.py defines T before it imports this module (line ~351 vs
# ~486), so the name is already bound in the package when we load.
from . import T


# ── Update callbacks ────────────────────────────────────────────────
# All callbacks live at module level so they're picklable and can be
# referenced both from `update=` and `items=` parameters below. Most
# delegate to helpers defined in __init__.py via lazy imports — this
# breaks the circular dependency that would arise from importing the
# scene_settings module BEFORE __init__.py finishes loading.


def _save_paths_proxy(self, context):
    from . import _save_paths
    _save_paths(self, context)


def _map_region_changed_proxy(self, context):
    """Смена района карты → сбрасываем отсканированные списки IPL.

    Списки `gtatools_text_ipls` / `gtatools_binary_ipls` собираются Scan'ом
    под КОНКРЕТНЫЙ район и работают как allowlist. Если оставить их при
    переключении на другой район, ни один их пункт не совпадёт с новым
    набором → импорт молча отбросит ВСЁ («not in Scan selection», 0
    instances). Поэтому чистим: пустой список = грузить всё, что проходит
    фильтр района; при желании пользователь сканирует заново под новый."""
    try:
        self.gtatools_text_ipls.clear()
        self.gtatools_binary_ipls.clear()
        if hasattr(self, 'gtatools_text_ipls_index'):
            self.gtatools_text_ipls_index = 0
        if hasattr(self, 'gtatools_binary_ipls_index'):
            self.gtatools_binary_ipls_index = 0
    except Exception:
        pass


def _export_all_filter_update(self, context):
    """Диалог Export All: галочки форматов фильтруют список файлового
    браузера по расширениям (как в Import All).

    LOD пишется как .dff, поэтому и DFF, и LOD дают ``*.dff``. Пусто (все
    галочки сняты) → шаблон, который ничего не сопоставляет, иначе Blender
    при пустом filter_glob показал бы вообще все файлы. Blender копирует
    filter_glob в params браузера один раз при открытии — смена свойства
    туда потом не доходит, поэтому пишем прямо в ``sp.params`` по всем
    окнам и форсим file.refresh отложенно."""
    pairs = (
        ('gtatools_export_all_dff', '*.dff'),
        ('gtatools_export_all_lod', '*.dff'),
        ('gtatools_export_all_col', '*.col'),
        ('gtatools_export_all_txd', '*.txd'),
        ('gtatools_export_all_cst', '*.cst'),
    )
    parts = []
    for attr, glob in pairs:
        if getattr(self, attr, False) and glob not in parts:
            parts.append(glob)
    glob = ';'.join(parts) if parts else '*.__none__'
    wm = getattr(context, 'window_manager', None)
    for win in (wm.windows if wm else ()):
        scr = getattr(win, 'screen', None)
        if scr is None:
            continue
        for area in scr.areas:
            if area.type != 'FILE_BROWSER':
                continue
            for sp in area.spaces:
                if getattr(sp, 'type', '') == 'FILE_BROWSER' and sp.params:
                    try:
                        sp.params.use_filter = True
                        if hasattr(sp.params, 'use_filter_glob'):
                            sp.params.use_filter_glob = True
                        sp.params.filter_glob = glob
                    except Exception:
                        pass
            area.tag_redraw()

    def _refresh():
        _wm = bpy.context.window_manager
        for _win in (_wm.windows if _wm else ()):
            _scr = getattr(_win, 'screen', None)
            if _scr is None:
                continue
            for _area in _scr.areas:
                if _area.type != 'FILE_BROWSER':
                    continue
                _region = next((r for r in _area.regions
                                if r.type == 'WINDOW'), None)
                if _region is None:
                    continue
                try:
                    with bpy.context.temp_override(window=_win, area=_area,
                                                   region=_region):
                        bpy.ops.file.refresh()
                except Exception:
                    pass
        return None
    try:
        if not bpy.app.timers.is_registered(_refresh):
            bpy.app.timers.register(_refresh, first_interval=0.0)
    except Exception:
        pass


def _lightcut_rebuild_proxy(self, context):
    """Живое обновление вайр-резака света при смене типа/радиуса/сегментов/
    радиуса кольца — перестраивает INU_LightCutter, если он существует."""
    try:
        from .ops import light_ops
        light_ops.rebuild_lightcutter(context)
    except Exception:
        pass


def _col_light_invalidate_preview_proxy(self, context):
    from . import _col_light_invalidate_preview
    _col_light_invalidate_preview(self, context)


def _get_map_region_items_proxy(self, context):
    from . import _get_map_region_items
    return _get_map_region_items(self, context)


def _get_id_preset_items_proxy(self, context):
    from . import _get_id_preset_items
    return _get_id_preset_items(self, context)


def _id_preset_update_proxy(self, context):
    from . import _id_preset_update
    _id_preset_update(self, context)


def _upd_suffix_dff_proxy(self, context):
    from . import _upd_suffix_dff
    _upd_suffix_dff(self, context)


def _upd_suffix_lod_proxy(self, context):
    from . import _upd_suffix_lod
    _upd_suffix_lod(self, context)


def _upd_suffix_col_proxy(self, context):
    from . import _upd_suffix_col
    _upd_suffix_col(self, context)


def _upd_prefix_dff_proxy(self, context):
    from . import _upd_prefix_dff
    _upd_prefix_dff(self, context)


def _upd_prefix_lod_proxy(self, context):
    from . import _upd_prefix_lod
    _upd_prefix_lod(self, context)


def _upd_prefix_col_proxy(self, context):
    from . import _upd_prefix_col
    _upd_prefix_col(self, context)


def _get_preset_items_proxy(self, context):
    from . import _get_preset_items
    return _get_preset_items(self, context)


def _on_profile_changed_proxy(self, context):
    from .tools.profiles import _on_profile_changed
    _on_profile_changed(self, context)


def _profile_enum_items_proxy(self, context):
    from .tools.profiles import profile_enum_items
    return profile_enum_items(self, context)


# Texture-bake map enum: ДИНАМИЧЕСКИЙ (ведётся tools.bake.BAKE_MAPS,
# который растёт по этапам). Кэшируем построенный список в module-global,
# чтобы строки пережили GC enum-items Blender'а (иначе метки кракозябрятся)
# — тот же приём, что у _profile_enum_items_proxy.
_bake_map_enum_cache = []

# Контекст перевода для enum карт. Blender переводит пункты enum в контексте
# проперти; метки карт (AO/Diffuse/Shadow/Bevel) совпадают со встроенным
# словарём Blender и иначе становятся ОО/Диффузный/Тень/Фаска. Регистрация
# своего перевода НЕ перебивает встроенный словарь — поэтому уводим пункты в
# СВОЙ контекст, где переводов нет → Blender показывает исходный английский.
# (Любая непустая строка-контекст без записей в словаре подходит.)
_MAP_TR_CTX = 'INU_BAKE_MAP'


def _bake_map_enum_items_proxy(self, context):
    from .tools.bake import bake_map_enum_items
    global _bake_map_enum_cache
    # Английские имена карт как есть (без T) — карты не переводим.
    _bake_map_enum_cache = [(mid, label, desc)
                            for (mid, label, desc) in bake_map_enum_items()]
    return _bake_map_enum_cache


_bake_alpha_src_cache = []


def _bake_alpha_source_items_proxy(self, context):
    """Источник альфы для ALPHA-слоя: «Материал» (прозрачность материала)
    либо любая ДРУГАЯ карта стека (её яркость → альфа, напр. Shadow). Метки
    карт английские, как в дропдауне карт."""
    from .tools.bake import bake_map_enum_items
    global _bake_alpha_src_cache
    items = [('MATERIAL', 'Material', '')]
    items += [(mid, label, desc)
              for (mid, label, desc) in bake_map_enum_items() if mid != 'ALPHA']
    _bake_alpha_src_cache = items
    return _bake_alpha_src_cache


# Полный набор режимов наложения Blender (как в Mix-узле). Метки —
# английские (технические), описания — русские. id/порядок/набор зеркалят
# единый источник правды tools.bake.bake_composite.BLEND_DEFS; здесь только
# UI-метаданные. Статичный список GC-безопасен — proxy/кэш не нужны (в
# отличие от карт). Метки НЕ форсятся в английский (в отличие от карт):
# Blender сам переводит «Multiply→Умножение» и т.п. — как в своём Mix-узле.
_BAKE_BLEND_ITEMS = [
    ('NORMAL',       "Normal",       T("Заменяет нижний слой")),
    ('DARKEN',       "Darken",       T("Минимум из двух — затемнение")),
    ('MULTIPLY',     "Multiply",     T("Умножение (затемнение) — AO / Shadow")),
    ('BURN',         "Color Burn",   T("Затемнение основы — резкий контраст теней")),
    ('LIGHTEN',      "Lighten",      T("Максимум из двух — осветление")),
    ('SCREEN',       "Screen",       T("Экран (осветление)")),
    ('DODGE',        "Color Dodge",  T("Осветление основы — резкие блики")),
    ('ADD',          "Add",          T("Сложение (осветление)")),
    ('OVERLAY',      "Overlay",      T("Перекрытие — контраст / износ кромок")),
    ('SOFT_LIGHT',   "Soft Light",   T("Мягкий свет — деликатный контраст")),
    ('LINEAR_LIGHT', "Linear Light", T("Линейный свет — жёсткий контраст")),
    ('DIFFERENCE',   "Difference",   T("Модуль разности — инверсия пересечений")),
    ('SUBTRACT',     "Subtract",     T("Вычитание (затемнение)")),
    ('DIVIDE',       "Divide",       T("Деление (осветление)")),
    ('HUE',          "Hue",          T("Тон верхнего, насыщенность и яркость нижнего")),
    ('SATURATION',   "Saturation",   T("Насыщенность верхнего, тон и яркость нижнего")),
    ('COLOR',        "Color",        T("Тон и насыщенность верхнего, яркость нижнего")),
    ('VALUE',        "Value",        T("Яркость верхнего, тон и насыщенность нижнего")),
]

# Разрешения — степени двойки. X/Y привязаны к этому списку (enum), а
# «Размер» — квадратный пресет, синхронящий оба через _bake_res_update.
_BAKE_POT_VALUES = (32, 64, 128, 256, 512, 1024, 2048, 4096, 8192)
_BAKE_POT_ITEMS = [(str(v), str(v), "") for v in _BAKE_POT_VALUES]


def _nearest_pot(v):
    return min(_BAKE_POT_VALUES, key=lambda p: abs(p - int(v)))


def _bake_res_update(self, context):
    # «Размер» — квадратный пресет: синхронит X и Y (числовые поля).
    v = int(self.gtatools_bake_resolution)
    self.gtatools_bake_res_x = v
    self.gtatools_bake_res_y = v


def _bake_res_x_update(self, context):
    snapped = _nearest_pot(self.gtatools_bake_res_x)
    if snapped != self.gtatools_bake_res_x:        # привязка к степени двойки
        self.gtatools_bake_res_x = snapped


def _bake_res_y_update(self, context):
    snapped = _nearest_pot(self.gtatools_bake_res_y)
    if snapped != self.gtatools_bake_res_y:
        self.gtatools_bake_res_y = snapped


def _bake_live_update(self, context):
    # Правка слоя (opacity/blend/enabled/карта) → пересобрать живой нодовый
    # композит на активном объекте (если он показан) → мгновенное превью.
    obj = getattr(context, 'active_object', None)
    if obj is None:
        return
    try:
        from .ops.bake_ops import rebuild_live_composite
        rebuild_live_composite(obj)
    except Exception:
        pass


def _desaturate_image_inplace(img):
    """Свести изображение в серое по яркости (Rec.709) прямо в пикселях."""
    try:
        w, h = img.size
        if w == 0 or h == 0 or not len(img.pixels):
            return
        import numpy as np
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        lum = 0.2126 * px[:, 0] + 0.7152 * px[:, 1] + 0.0722 * px[:, 2]
        px[:, 0] = px[:, 1] = px[:, 2] = lum
        img.pixels.foreach_set(px.ravel())
        img.update()
    except Exception:
        pass


def _bake_desaturate_update(self, context):
    # При включении «Обесцветить» для Normal — сразу свести уже запечённую
    # карту в серое (визуально «перепечь обесцвеченной»), без полного
    # повторного запекания. Выключение вернёт цвет только после повторного
    # «Запечь» (обесцвечивание пикселей необратимо).
    if self.desaturate and self.map_id == 'NORMAL':
        obj = getattr(context, 'active_object', None)
        base = obj.get("inu_bake_base", "") if obj else ""
        img = bpy.data.images.get(f"{base}_{self.map_id}") if base else None
        if img is not None:
            _desaturate_image_inplace(img)
    _bake_live_update(self, context)


def _bake_layer_index_update(self, context):
    # Клик по слою → показать его запечённую карту в Image-редакторе.
    obj = getattr(context, 'active_object', None)
    if obj is None:
        return
    base = obj.get("inu_bake_base", "")
    i = self.gtatools_bake_layers_index
    layers = self.gtatools_bake_layers
    if not base or not (0 <= i < len(layers)):
        return
    _k = getattr(layers[i], 'uid', '') or layers[i].map_id
    img = bpy.data.images.get(f"{base}_{_k}")
    if img is None:
        return
    try:
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces.active.image = img
    except Exception:
        pass
    # Память полигонов: у слоя с сохранёнными гранями (Bevel «только
    # выделенные») — выделить их на объекте. Переключился на слой → его
    # полигоны выделены и готовы к перезапеканию.
    try:
        uid = getattr(layers[i], 'uid', '')
        if uid and obj.get(f"inu_bake_faces_{uid}"):
            from .ops.bake_ops import _restore_layer_faces
            _restore_layer_faces(obj, uid)
    except Exception:
        pass


def _ik_empty_types_proxy(self, context):
    from .ops.ik_rig import EMPTY_TYPES
    return EMPTY_TYPES


def _update_particle_sim(self, context):
    from .ops import particle_sim
    if self.gtatools_particle_sim:
        particle_sim.start_simulation()
    else:
        particle_sim.stop_simulation()


def _update_uv_grid(self, context):
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            area.tag_redraw()


def _on_modulate_preview_update(self, context):
    from .tools.prelight import apply_modulate_preview
    apply_modulate_preview(context.scene)


def _prelight_view_update(self, context):
    """Ползунок визуальной коррекции превью прилайта — live-применяем во все
    материалы с превью, без пересборки графа. Только вьюпорт."""
    try:
        from .tools.prelight import apply_prelight_view_correction
        apply_prelight_view_correction(getattr(context, 'scene', None))
    except Exception as e:                     # noqa: BLE001
        print(f"[INU] prelight view correction failed: {e!r}")


def _on_game_change(self, context):
    """Смена игры (SA/VC/III) → загрузить per-game дефолт коррекции превью
    прилайта в ползунки и применить."""
    try:
        from .tools.prelight import load_view_correction_for_game
        scene = getattr(context, 'scene', None)
        if scene is not None:
            load_view_correction_for_game(scene, self.gtatools_game)
    except Exception as e:                     # noqa: BLE001
        print(f"[INU] game-change prelight load failed: {e!r}")


def _inu_pipeline_changed_proxy(self, context):
    try:
        from . import _inu_pipeline_changed
        _inu_pipeline_changed(self, context)
    except Exception as e:
        # update-коллбэк не должен ронять остальной UI. Если что-то
        # пошло не так с per-pipeline snapshot logic — печатаем в
        # консоль и идём дальше, не мешая пайплайну сохраниться.
        print(f"[INU] pipeline-change snapshot failed: {e!r}")


def _ifp_action_changed(self, context):
    try:
        from .ops.ifp_import import preview_is_active, preview_start
    except Exception:
        return
    if not preview_is_active():
        return
    arm = context.active_object
    if not arm or arm.type != 'ARMATURE':
        return
    name = self.gtatools_ifp_action
    if not name:
        return
    preview_start(arm, name)


def _on_ik_color_change(self, context):
    rgb = tuple(self.gtatools_ik_color)[:3]
    for arm in bpy.data.objects:
        if arm.type != 'ARMATURE' or not arm.get('inu_ik_rigged'):
            continue
        for pb in arm.pose.bones:
            db = arm.data.bones.get(pb.name)
            if db is None or not db.get('inu_ik_control'):
                continue
            try:
                pb.color.palette = 'CUSTOM'
                pb.color.custom.normal = rgb
                pb.color.custom.select = rgb
                pb.color.custom.active = rgb
            except Exception:
                pass


def _on_floor_offset_change(self, context):
    for arm in bpy.data.objects:
        if arm.type != 'ARMATURE' or not arm.get('inu_ik_rigged'):
            continue
        for pb in arm.pose.bones:
            for c in pb.constraints:
                if (c.type == 'FLOOR'
                        and c.name.startswith('INU_IK_')):
                    c.offset = float(self.gtatools_floor_offset)


def _on_chain_offset_change(self, context):
    offset = tuple(self.gtatools_ik_chain_offset)
    for arm in bpy.data.objects:
        if arm.type != 'ARMATURE' or not arm.get('inu_ik_rigged'):
            continue
        for pb in arm.pose.bones:
            db = arm.data.bones.get(pb.name)
            if db is None or not db.get('inu_ik_control'):
                continue
            ct = db.get('inu_ik_ctrl_type')
            if ct != 'chain':
                continue
            try:
                pb.custom_shape_translation = offset
            except Exception:
                pass


_IK_BASE_SIZES = {
    'chain': 0.08, 'head': 0.08, 'rot': 0.08,
    'pole':  0.04, 'root': 0.16,
}


def _derive_ik_type(name):
    if not name.startswith('INU_IK_'):
        return None
    if name.endswith('_pole'):
        return 'pole'
    suffix = name[len('INU_IK_'):]
    if suffix in {'R_arm', 'L_arm', 'R_leg', 'L_leg'}:
        return 'chain'
    if suffix == 'root':
        return 'root'
    return 'rot'


def _ctrl_type_of(db):
    return db.get('inu_ik_ctrl_type') or _derive_ik_type(db.name)


def _on_ik_size_change(self, context):
    mult = float(self.gtatools_ik_size)
    for arm in bpy.data.objects:
        if arm.type != 'ARMATURE' or not arm.get('inu_ik_rigged'):
            continue
        for pb in arm.pose.bones:
            db = arm.data.bones.get(pb.name)
            if db is None or not db.get('inu_ik_control'):
                continue
            ct = _ctrl_type_of(db) or 'chain'
            base = _IK_BASE_SIZES.get(ct, 0.08)
            size = base * mult
            try:
                pb.custom_shape_scale_xyz = (size, size, size)
            except Exception:
                pass


_IK_TYPE_TO_COLL = {
    'chain': 'INU_IK_Chain',
    'pole':  'INU_IK_Pole',
    'rot':   'INU_IK_Rot',
    'head':  'INU_IK_Rot',
    'root':  'INU_IK_Root',
}


def _make_ik_visibility_setter(ctrl_types):
    def _setter(self, context):
        attr = ctrl_types[1]
        visible = bool(getattr(self, attr))
        type_set = ctrl_types[0]
        coll_names = {_IK_TYPE_TO_COLL[t] for t in type_set
                      if t in _IK_TYPE_TO_COLL}

        for arm in bpy.data.objects:
            if (arm.type != 'ARMATURE'
                    or not arm.get('inu_ik_rigged')):
                continue

            bone_colls = getattr(arm.data, 'collections', None)
            touched_via_collection = set()
            if bone_colls is not None:
                for cname in coll_names:
                    coll = bone_colls.get(cname)
                    if coll is None:
                        continue
                    coll.is_visible = visible
                    try:
                        for bone in coll.bones:
                            touched_via_collection.add(bone.name)
                    except Exception:
                        pass

            for db in arm.data.bones:
                if db.name in touched_via_collection:
                    continue
                if not db.get('inu_ik_control'):
                    continue
                if _ctrl_type_of(db) in type_set:
                    db.hide = not visible

            arm.data.update_tag()

        if context.area is not None:
            context.area.tag_redraw()
    return _setter


# ── CollectionProperty item types ─────────────────────────────────
#
# Defined here (not in their feature modules) so they can be referenced
# by ``CollectionProperty(type=...)`` fields inside INUSceneSettings
# without circular imports. Each remains a standalone PropertyGroup
# registered through the addon's classes-to-register list.


class INUValidateIssue(bpy.types.PropertyGroup):
    """One line in the Validate Scene panel. Backed by a Scene
    CollectionProperty so it survives between draws and across the
    Run → Goto/Fix interaction."""
    severity: StringProperty(default='WARNING')
    category: StringProperty(default='')
    message: StringProperty(default='')
    # Translation template + JSON-encoded args for interpolated
    # messages. When non-empty the panel does
    # ``T(template).format(**json.loads(args))`` so the user-facing
    # text follows the active locale. Empty when the message is
    # static and ``message`` itself is the displayed string.
    message_template: StringProperty(default='')
    message_args: StringProperty(default='')
    target_kind: StringProperty(default='')
    target_name: StringProperty(default='')
    fix_op_id: StringProperty(default='')
    fix_arg: StringProperty(default='')


class GTATOOLS_ImgFileEntry(bpy.types.PropertyGroup):
    """One file entry in IMG archive list."""
    name: StringProperty()


# Shared 4-way blend-mode items for the alpha-materials tool (per-row +
# bulk). Labels mirror Blender's native blend_method so it feels familiar.
# Applied via ops.alpha_tools._apply_blend, which ALSO sets
# surface_render_method — on EEVEE Next (4.2+) blend_method alone no
# longer takes effect, so a plain blend_method dropdown "does nothing".
_ALPHA_BLEND_ITEMS = [
    ('OPAQUE', T("Непрозрачность"),   ""),
    ('CLIP',   T("Альфа-усечение"),   ""),
    ('HASHED', T("Альфа-хеш"),        ""),
    ('BLEND',  T("Альфа-смешивание"), ""),
]


def _alpha_item_blend_update(self, context):
    """Editing a row's mode applies it to the real material (both
    blend_method and surface_render_method). Suppressed during scan
    (see ops.alpha_tools._SUPPRESS_ITEM_UPDATE) so populating the list
    doesn't mutate materials."""
    from .ops import alpha_tools
    if getattr(alpha_tools, '_SUPPRESS_ITEM_UPDATE', False):
        return
    mat = bpy.data.materials.get(self.name)
    if mat is not None:
        alpha_tools._apply_blend(mat, self.blend)


class GTATOOLS_AlphaMatEntry(bpy.types.PropertyGroup):
    """One scanned alpha material in the bulk blend-mode editor.
    ``blend`` mirrors the material's transparency mode; editing it in the
    list applies to the real material via _apply_blend."""
    name: StringProperty()
    blend: EnumProperty(items=_ALPHA_BLEND_ITEMS, default='BLEND',
                        update=_alpha_item_blend_update)


class GTATOOLS_BinaryIplEntry(bpy.types.PropertyGroup):
    """One binary IPL file found inside an IMG archive — user-selectable
    for inclusion in Build Map / Import Map."""
    name: StringProperty()
    enabled: BoolProperty(name="", default=True)
    img_source: StringProperty()


class GTATOOLS_TextIplEntry(bpy.types.PropertyGroup):
    """One text IPL file (loose on disk via gta.dat, or inside an IMG)
    — parallel to GTATOOLS_BinaryIplEntry but for human-readable IPLs.

    ``name`` is the display label.  ``path`` holds either an absolute
    loose-file path (when ``img_source`` is empty) or the entry name
    within ``img_source`` IMG.
    """
    name: StringProperty()
    enabled: BoolProperty(name="", default=True)
    path: StringProperty()
    img_source: StringProperty()


class GTATOOLS_LintIssueItem(bpy.types.PropertyGroup):
    """One row in the binary file scanner UIList. Mirrors core/file_lint.LintIssue.

    Lives on WindowManager (transient — results don't pollute .blend).
    """
    severity: StringProperty(default='ERROR')   # ERROR / WARN / INFO
    code: StringProperty(default='')            # stable key
    file: StringProperty(default='')            # absolute path
    where: StringProperty(default='')           # 'model[1].sphere[7]'
    message: StringProperty(default='')


class GTATOOLS_PathItem(bpy.types.PropertyGroup):
    """Single file-path entry — used by map analyzer's custom IDE/IPL
    lists. CollectionProperty of these gives the user an add/remove UI."""
    path: StringProperty(name="Path", subtype='FILE_PATH', default='')


class INUGrassEntry(bpy.types.PropertyGroup):
    """One line of data/plants.dat — a procedural-grass cover definition
    bound to a COLPOINT surface name. Fields mirror the file columns 1:1
    (see core/plants_dat.PLANTS_FIELDS). Editable in the «Трава» panel;
    written back out by the plants.dat exporter."""
    # Surface name — must match a COLPOINT_SURFACETYPE_* name (e.g.
    # GRASS_SHORT_LUSH). Kept as free text so imported names round-trip
    # verbatim and users can target names our surface table abbreviates.
    name: StringProperty(name=T("Поверхность"), default="GRASS_SHORT_LUSH")
    pcd_id: IntProperty(name="PCDid", default=0, min=0, max=2,
        description=T("Индекс определения покрова для поверхности (0-2). "
                    "На одну поверхность можно до 3 определений"))
    slot_id: IntProperty(name="SlotID", default=0, min=0, max=3,
        description=T("Слот: набор геометрии + «большая» текстура в plant1.txd. "
                    "Должен быть одинаковым для всех PCDid одной поверхности"))
    model_id: IntProperty(name="ModelID", default=0, min=0, max=3,
        description=T("Субмодель (0-3)"))
    uv_off: IntProperty(name="UVoff", default=1, min=0, max=15,
        description=T("Какой из 16 тайлов «большой» текстуры 64x1024 (0-15)"))
    r: IntProperty(name="R", default=220, min=0, max=255)
    g: IntProperty(name="G", default=210, min=0, max=255)
    b: IntProperty(name="B", default=165, min=0, max=255)
    intensity: IntProperty(name="I", default=160, min=0, max=255,
        description=T("Интенсивность цвета (0-255)"))
    var_i: IntProperty(name="VarI", default=22, min=0, max=255,
        description=T("Разброс интенсивности (работает при I<255)"))
    alpha: IntProperty(name="A", default=40, min=0, max=255,
        description=T("Альфа (129-255; ниже — полупрозрачнее)"))
    scl_xy: FloatProperty(name="SclXY", default=0.5, min=0.0, soft_max=5.0,
        description=T("Размер травинки по ширине"))
    scl_z: FloatProperty(name="SclZ", default=0.51, min=0.0, soft_max=5.0,
        description=T("Высота травинки"))
    scl_var_xy: FloatProperty(name="SclVarXY", default=1.5, min=0.0, soft_max=5.0,
        description=T("Разброс размера по ширине"))
    scl_var_z: FloatProperty(name="SclVarZ", default=0.65, min=0.0, soft_max=5.0,
        description=T("Разброс высоты"))
    wbend_scl: FloatProperty(name="WBendScl", default=1.0, soft_min=-5.0, soft_max=5.0,
        description=T("Сила качания на ветру (отрицательная = против ветра)"))
    wbend_var: FloatProperty(name="WBendVar", default=3.0, min=0.0, max=10.0,
        description=T("Разброс качания между травинками (0-10)"))
    density: FloatProperty(name="Density", default=0.1, min=0.0, soft_max=1.0,
        description=T("Плотность: травинок на 1 м² (1.0 густо, 0.1 редко, 0 — нет)"))


class GTATOOLS_TextureBrowserItem(bpy.types.PropertyGroup):
    """One row in the Texture Browser UIList. Mirrors
    core/texture_index.TextureEntry. Lives on WindowManager
    (transient — index isn't saved with the .blend, user re-scans
    each session)."""
    archive_path: StringProperty(default='')
    txd_name: StringProperty(default='')
    texture_name: StringProperty(default='')
    width: IntProperty(default=0)
    height: IntProperty(default=0)
    depth: IntProperty(default=0)
    fourcc: IntProperty(default=0)
    num_levels: IntProperty(default=1)
    platform_id: IntProperty(default=8)
    format_label: StringProperty(default='')
    usage_count: IntProperty(default=0)    # IDE models referencing this TXD


class INUBakeLayer(bpy.types.PropertyGroup):
    """Один слой в стеке запекания текстур (tools/bake/). Поля
    contrast/gamma/influence_* объявлены сейчас с identity-дефолтами —
    композитор их УЖЕ читает, включение = только UI, без смены схемы.
    См. docs/BAKE_FEATURE_PLAN.md."""
    map_id: EnumProperty(
        name=T("Карта"), description=T("Какую карту печь в этом слое"),
        items=_bake_map_enum_items_proxy, update=_bake_live_update,
        translation_context=_MAP_TR_CTX)        # пункты — английскими, без авто-перевода
    enabled: BoolProperty(name="", default=True, update=_bake_live_update)
    # Развёрнута ли строка слоя в списке (показывать настройки инлайн).
    expanded: BoolProperty(name="", default=False)
    # Стабильный уникальный id слоя — ключ памяти запечённых полигонов:
    # obj["inu_bake_faces_<uid>"] = "1,5,17,…". Ставится при добавлении слоя.
    uid: StringProperty(name="", default="")
    blend_mode: EnumProperty(
        name=T("Режим"), description=T("Как смешивать с нижними слоями"),
        items=_BAKE_BLEND_ITEMS, default='MULTIPLY', update=_bake_live_update)
    opacity: FloatProperty(
        name=T("Прозрачность"), default=1.0, min=0.0, max=1.0, subtype='FACTOR',
        update=_bake_live_update)
    # Обесцветить слой перед композитом (в оттенки серого по яркости).
    # Нужно для Normal Map: при объединении её синий tangent-space оттенок
    # проступает на итоговой текстуре; обесцвечивание оставляет только
    # деталь рельефа (как при сведении нормал-мапы в Фотошопе). Кнопка в
    # UI показывается только для слоёв с картой Normal.
    desaturate: BoolProperty(
        name=T("Обесцветить"), default=False,
        description=T("Обесцветить слой (в серое по яркости) — убирает синий "
                    "оттенок Normal Map. Для Normal сразу сводит уже "
                    "запечённую карту в серое"),
        update=_bake_desaturate_update)
    # Контраст/гамма слоя — real-time: применяются и в numpy-сведении, и в
    # живом нодовом превью (update пересобирает материал → видно сразу).
    contrast: FloatProperty(name=T("Контраст"), default=1.0, min=0.0, max=4.0,
                            update=_bake_live_update)
    gamma: FloatProperty(name=T("Гамма"), default=1.0, min=0.05, max=4.0,
                         update=_bake_live_update)
    # ── ALPHA-слой: откуда брать альфа-канал ──
    # 'MATERIAL' — прозрачность материала (как печётся сама карта ALPHA);
    # любой другой map_id — яркость этой карты (напр. Shadow) как альфа.
    # Так делается шэдоу-декаль: источник Shadow + инверсия → видно тёмное
    # (тень), скрыто светлое (свет).
    alpha_source: EnumProperty(
        name=T("Источник альфы"),
        description=T("Откуда брать альфу: прозрачность материала или яркость "
                    "другой карты стека (напр. Shadow)"),
        items=_bake_alpha_source_items_proxy, update=_bake_live_update,
        translation_context=_MAP_TR_CTX)
    alpha_invert: BoolProperty(
        name=T("Инвертировать"), default=False,
        description=T("Инвертировать альфу: показывать ТЁМНЫЕ участки, скрывать "
                    "светлые (для тени — включи)"),
        update=_bake_live_update)
    # ── Любой слой (напр. Shadow) → прозрачный декаль ──
    # Уводит ЯРКОСТЬ этой карты в альфа-канал: тёмное видно, светлое — дыра
    # (шэдоу-декаль). Порог/мягкость отсекают светлое/серое (затухание света),
    # чтобы осталась только тень. В RGB-стек такой слой не идёт.
    as_decal: BoolProperty(
        name=T("Декаль"), default=False,
        description=T("Увести яркость карты в прозрачность: тёмное (тень) видно, "
                    "светлое убирается. Порог/Мягкость отсекают серое"),
        update=_bake_live_update)
    decal_threshold: FloatProperty(
        name=T("Порог"), default=0.5, min=0.0, max=1.0, subtype='FACTOR',
        description=T("Яркость, выше которой пиксель скрывается (прозрачный). "
                    "Ниже порога — видно. Опусти, чтобы убрать серый пол"),
        update=_bake_live_update)
    decal_softness: FloatProperty(
        name=T("Мягкость"), default=0.25, min=0.0, max=1.0, subtype='FACTOR',
        description=T("Ширина мягкого перехода у порога (0 — резкая граница)"),
        update=_bake_live_update)
    decal_invert: BoolProperty(
        name=T("Инверсия цвета"), default=False,
        description=T("Инвертировать: показывать СВЕТЛОЕ вместо тёмного"),
        update=_bake_live_update)
    # ── FUTURE (identity сейчас; композитор уже читает) ──
    influence_target: StringProperty(name=T("Влияние на"), default='')
    influence_amount: FloatProperty(
        name=T("Сила влияния"), default=1.0, min=0.0, max=1.0, subtype='FACTOR')


def _on_scene_animobj_pick(self, context):
    """Fires when the user picks a mesh via the scene-level animobj
    pipette. Delegates to ``attach_mesh_to_rig`` which auto-creates a
    rig on the first pick, then routes subsequent picks per the
    sibling ``gtatools_animobj_picker_target`` enum. Imports the
    helper lazily — scene_settings is imported very early and the
    operators module isn't ready yet at top-level."""
    mesh = self.gtatools_animobj_picker
    if mesh is None or mesh.type != 'MESH':
        return
    target = self.gtatools_animobj_picker_target
    try:
        from .ops.animobj_ops import attach_mesh_to_rig
        attach_mesh_to_rig(context, mesh, target=target)
    except Exception as ex:
        print(f"[INU] animobj pipette failed: {ex}")

    # Clear the picker via a deferred timer — update callbacks can't
    # safely mutate their own property in the same event cycle.
    settings = self
    def _clear():
        try:
            settings.gtatools_animobj_picker = None
        except Exception:
            pass
        return None
    try:
        bpy.app.timers.register(_clear, first_interval=0.01)
    except Exception:
        pass


class INULightCutRing(bpy.types.PropertyGroup):
    """Одно кольцо резака света — радиус 0..1 (доля от общего радиуса,
    от центра к краю)."""
    radius: FloatProperty(name=T("Радиус"), default=0.5, min=0.0, max=1.0,
                          subtype='FACTOR', update=_lightcut_rebuild_proxy)


# ── PropertyGroup ─────────────────────────────────────────────────


_export_img_items_cache = []
_export_img_items_root = None


def _export_img_target_items(self, context):
    """Items для выбора целевого IMG при экспорте: «родной IMG модели» +
    все .img из папки игры. Кэш по корню (пересканит только при смене папки)
    — enum-callback зовётся на каждый draw дропдауна, os.walk каждый раз дорог.
    Список пиним в модульной переменной, иначе GC съедает строки (известный
    баг динамических EnumProperty)."""
    global _export_img_items_cache, _export_img_items_root
    try:
        root = bpy.path.abspath(context.scene.inu_settings.gtatools_game_root) \
            if (context and context.scene) else ''
    except Exception:
        root = ''
    if root == _export_img_items_root and _export_img_items_cache:
        return _export_img_items_cache
    items = [('SELF', T("Родной IMG модели"),
              T("IMG, откуда пришла модель (img_target_file)"))]
    if root and os.path.isdir(root):
        seen = set()
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.lower().endswith('.img'):
                    fp = os.path.join(dirpath, f)
                    k = os.path.normcase(fp)
                    if k not in seen:
                        seen.add(k)
                        items.append((fp, f, fp))
    _export_img_items_root = root
    _export_img_items_cache = items
    return _export_img_items_cache


# ── timecyc.dat ─────────────────────────────────────────────────────
#
# Сам разобранный файл в сцене НЕ живёт (23 погоды × 8 срезов × 52
# числа) — он в модульном кэше ops/timecyc_ops.py. Здесь только путь,
# выбор погоды/среза/часа, ручки превью и поля РЕДАКТИРУЕМОГО среза.
# Имена полей среза (f_*) сопоставлены ключам core/timecyc.py в
# таблицах _COLOR_FIELDS / _ALPHA_FIELDS / _NUM_FIELDS того же модуля.


def _tc_weather_changed(self, context):
    from .ops.timecyc_ops import on_weather_changed
    on_weather_changed(self, context)


def _tc_slot_changed(self, context):
    from .ops.timecyc_ops import on_slot_changed
    on_slot_changed(self, context)


def _tc_hour_changed(self, context):
    from .ops.timecyc_ops import on_hour_changed
    on_hour_changed(self, context)


def _tc_field_changed(self, context):
    from .ops.timecyc_ops import on_field_changed
    on_field_changed(self, context)


def _tc_opt_changed(self, context):
    from .ops.timecyc_ops import on_preview_opt_changed
    on_preview_opt_changed(self, context)


def _tc_path_changed(self, context):
    from .ops.timecyc_ops import on_path_changed
    on_path_changed(self, context)


def _tc_prelight_changed(self, context):
    from .ops.timecyc_ops import on_prelight_daynight_changed
    on_prelight_daynight_changed(self, context)


def _tc_material_mode_changed(self, context):
    """Тумблер, меняющий ГРАФ материалов (игровой вид) — один проход по
    материалам."""
    from .ops.timecyc_ops import on_material_mode_changed
    on_material_mode_changed(self, context)


def _tc_screen_mode_changed(self, context):
    """Туман/PostFX — только композитор, без прохода по материалам."""
    from .ops.timecyc_ops import on_screen_mode_changed
    on_screen_mode_changed(self, context)


_TC_SLOT_ITEMS = [
    ('0', "00:00", T("Полночь")),
    ('1', "05:00", T("Раннее утро")),
    ('2', "06:00", T("Рассвет")),
    ('3', "07:00", T("Утро")),
    ('4', "12:00", T("Полдень")),
    ('5', "19:00", T("Вечер")),
    ('6', "20:00", T("Закат")),
    ('7', "22:00", T("Ночь")),
]

# III / VC: почасовые срезы (24 строки на погоду). Отдельное статичное
# свойство, а не динамический enum — см. комментарий к weathers ниже:
# какой из двух показывать, решает панель по игре загруженного файла.
_TC_SLOT24_ITEMS = [(str(h), "%02d:00" % h, "") for h in range(24)]


def _tc_color(name, default=(0.0, 0.0, 0.0)):
    return FloatVectorProperty(
        name=name, subtype='COLOR', size=3, min=0.0, max=1.0,
        default=default, update=_tc_field_changed)


class INUTimecycWeather(bpy.types.PropertyGroup):
    """Имя одной погоды из timecyc — строка в списке для выбора."""
    name: StringProperty(default="")


class INUTimecycProps(bpy.types.PropertyGroup):
    """Состояние вкладки «Тайм-циклы»."""

    # ── Источник ────────────────────────────────────────────────
    path: StringProperty(
        name=T("Файл"), subtype='FILE_PATH', default="",
        update=_tc_path_changed)
    # Погоды — КОЛЛЕКЦИЯ, а не динамический enum. У enum'а с items-
    # колбэком есть скверная особенность: стоит колбэку один раз
    # оступиться (или списку пересобраться под сохранённым значением),
    # как свойство отдаёт пустую строку, выпадашка рисуется пустой, и в
    # него нельзя даже записать — «enum "0" not found in ()». Коллекция
    # живёт в сцене и такого не умеет.
    weathers: CollectionProperty(type=INUTimecycWeather)
    weather_name: StringProperty(
        name=T("Погода"), default="", update=_tc_weather_changed)
    slot: EnumProperty(
        name=T("Срез"), items=_TC_SLOT_ITEMS, default='4',
        update=_tc_slot_changed)
    slot_hourly: EnumProperty(
        name=T("Срез"), items=_TC_SLOT24_ITEMS, default='12',
        update=_tc_slot_changed)
    hour: FloatProperty(
        name=T("Время суток"), min=0.0, max=24.0, default=12.0, step=25,
        precision=2, update=_tc_hour_changed)
    live: BoolProperty(
        name=T("Живое превью"), default=True,
        description=T("Обновлять освещение сцены при каждом изменении"))
    # Мастер-состояние: применён ли тайм-цикл к сцене. Только индикатор для
    # кнопки-тумблера — саму работу делает оператор gtatools.timecyc_toggle.
    enabled: BoolProperty(default=False)

    # ── Ручки превью ────────────────────────────────────────────
    sky_strength: FloatProperty(
        name=T("Яркость неба"), min=0.0, max=20.0, default=1.0,
        update=_tc_opt_changed)
    ambient_strength: FloatProperty(
        name=T("Сила ambient"), min=0.0, max=20.0, default=1.0,
        update=_tc_opt_changed)
    ambient_split: BoolProperty(
        name=T("Ambient отдельно от неба"), default=True,
        description=T("Небо остаётся фоном для камеры, а сцену освещает "
                      "отдельный цвет Amb. Держится на Light Path — в "
                      "EEVEE может сработать не так, как в Cycles"),
        update=_tc_opt_changed)
    ambient_from_objects: BoolProperty(
        name=T("Ambient объектов"), default=True,
        description=T("Брать Amb_Obj вместо Amb — как в игре светятся "
                      "машины и педы, а не здания"),
        update=_tc_opt_changed)
    gradient: FloatProperty(
        name=T("Резкость горизонта"), min=0.02, max=1.0, default=0.35,
        description=T("На какой высоте небо доходит до цвета зенита. "
                      "1.0 растягивает переход на всю полусферу, и в "
                      "кадре виден только горизонтный цвет"),
        update=_tc_opt_changed)
    use_fog: BoolProperty(
        name=T("Туман"), default=True,
        description=T("Гасить цвет по расстоянию от FogSt до FarClp — "
                      "той же фиксированной функцией, что и игра. "
                      "Работает там же, где превью прилайта"),
        update=_tc_screen_mode_changed)
    use_postfx: BoolProperty(
        name=T("PostFX (цветофильтр)"), default=True,
        description=T("Цветофильтр кадра из PostFX1/PostFX2 среза: "
                      "out = in*(1 + rgb1*a1 + rgb2*a2). Именно он делает "
                      "картинку игры светлее и цветнее значений timecyc"),
        update=_tc_screen_mode_changed)
    fog_curve: FloatProperty(
        name=T("Кривая тумана"), min=0.5, max=6.0, default=2.0,
        description=T("1 — честная линейка FogSt→FarClp, как у RW. "
                      "Больше — дымка набирается ближе к горизонту, как "
                      "выглядит кадр игры"),
        update=_tc_opt_changed)
    fog_distance: FloatProperty(
        name=T("Дальность тумана ×"), min=0.1, max=8.0, default=1.0,
        description=T("Растянуть обе дистанции. В игре на кадр влияет ещё "
                      "и ползунок дальности прорисовки, которого в "
                      "timecyc нет"),
        update=_tc_opt_changed)
    # Доля клипа, дальше которой — небо (туман не кладём). Подобрано так,
    # чтобы небо не красилось (градиент цел), а вся геометрия попадала в
    # туман. Ползунок из UI убран — значение фиксированное.
    fog_sky_factor: FloatProperty(
        name=T("Небо с (× клип)"), min=0.1, max=1.0, default=0.819,
        subtype='FACTOR',
        description=T("Где начинается небо — как доля клипа вьюпорта. Всё "
                      "ближе получает туман, дальше — небо (туман не кладём, "
                      "градиент цел). Меньше — небо начинается раньше (если "
                      "градиент пропал), больше — туман тянется дальше (если "
                      "дальний край торчит без тумана)"),
        update=_tc_opt_changed)
    use_water: BoolProperty(
        name=T("Красить воду"), default=True,
        description=T("Подставлять WaterRGBA в материал импортированной воды"),
        update=_tc_opt_changed)
    use_far_clip: BoolProperty(
        name=T("Дальность вьюпорта"), default=True,
        description=T("Поднимать clip end вьюпорта до FarClp среза"),
        update=_tc_opt_changed)

    # ── Прилайт по времени суток ────────────────────────────────
    # Движок SA хранит ночные вершинные цвета отдельной секцией DFF и
    # пишет в prelight смесь day*(1-dn) + night*dn. Здесь то же самое
    # нодами: общая группа читает атрибуты Day и Night.
    game_look: BoolProperty(
        name=T("Как в игре (unlit)"), default=True,
        description=T("Отдавать цвет прилайта напрямую, мимо PBR: игра "
                      "рисует здания fixed-function'ом — без теней, "
                      "бликов и подсветки от неба"),
        update=_tc_material_mode_changed)
    # Всегда включён при активном тайм-цикле (тумблер из UI убран, значение
    # форсится в True при импорте/включении). default=True — для новых сцен.
    prelight_daynight: BoolProperty(
        name=T("Прилайт по времени суток"), default=True,
        description=T("Смешивать вершинные цвета Day и Night по часам — "
                      "как это делает игра. Работает на материалах, где "
                      "включено превью прилайта"),
        update=_tc_prelight_changed)
    # Сколько материалов подхватило режим — считается в момент
    # переключения, чтобы панель не обходила bpy.data.materials на
    # каждую перерисовку.
    dn_material_count: IntProperty(default=-1)
    dn_dusk_start: FloatProperty(
        name=T("Закат: начало"), min=0.0, max=24.0, default=20.0,
        description=T("С какого часа прилайт начинает уходить в ночной"),
        update=_tc_opt_changed)
    dn_dusk_end: FloatProperty(
        name=T("Закат: конец"), min=0.0, max=24.0, default=21.0,
        description=T("К какому часу прилайт становится полностью ночным"),
        update=_tc_opt_changed)
    dn_dawn_start: FloatProperty(
        name=T("Рассвет: начало"), min=0.0, max=24.0, default=5.0,
        description=T("С какого часа ночной прилайт начинает уходить"),
        update=_tc_opt_changed)
    dn_dawn_end: FloatProperty(
        name=T("Рассвет: конец"), min=0.0, max=24.0, default=6.0,
        description=T("К какому часу прилайт становится полностью дневным"),
        update=_tc_opt_changed)

    # ── Значения среза: цвета ───────────────────────────────────
    f_amb: _tc_color(T("Ambient (мир)"))
    f_amb_obj: _tc_color(T("Ambient (объекты)"))
    # VC: ambient при включённых Trails (CMBlur::BlurOn).
    f_amb_bl: _tc_color(T("Ambient (мир, Trails)"))
    f_amb_obj_bl: _tc_color(T("Ambient (объекты, Trails)"))
    f_dir: _tc_color(T("Directional"), (1.0, 1.0, 1.0))
    f_sky_top: _tc_color(T("Небо: зенит"))
    f_sky_bot: _tc_color(T("Небо: горизонт"))
    f_sun_core: _tc_color(T("Солнце: ядро"))
    f_sun_corona: _tc_color(T("Солнце: корона"))
    f_low_clouds: _tc_color(T("Нижние облака"))
    f_top_clouds: _tc_color(T("Верхние облака"))          # III / VC
    f_bottom_clouds: _tc_color(T("Облака у горизонта"))
    f_blur: _tc_color(T("Trails / blur"))                  # III / VC
    f_water: _tc_color(T("Вода"))
    f_postfx1: _tc_color(T("PostFX 1"))
    f_postfx2: _tc_color(T("PostFX 2"))

    f_water_a: FloatProperty(
        name=T("Вода: альфа"), min=0.0, max=1.0, default=0.94,
        update=_tc_field_changed)
    f_blur_a: FloatProperty(                               # III (RGBA)
        name=T("Trails: альфа"), min=0.0, max=1.0, default=0.3,
        update=_tc_field_changed)
    f_postfx1_a: FloatProperty(
        name=T("PostFX 1: альфа"), min=0.0, max=1.0, default=1.0,
        update=_tc_field_changed)
    f_postfx2_a: FloatProperty(
        name=T("PostFX 2: альфа"), min=0.0, max=1.0, default=1.0,
        update=_tc_field_changed)

    # ── Значения среза: числа ───────────────────────────────────
    f_sun_size: FloatProperty(
        name=T("Размер солнца"), min=0.0, max=20.0, default=1.0,
        update=_tc_field_changed)
    f_spr_size: FloatProperty(
        name=T("Размер блика"), min=0.0, max=20.0, default=1.0,
        update=_tc_field_changed)
    f_spr_bright: FloatProperty(
        name=T("Яркость блика"), min=-5.0, max=20.0, default=0.3,
        update=_tc_field_changed)
    f_shadow: IntProperty(
        name=T("Тени"), min=0, max=255, default=200,
        update=_tc_field_changed)
    f_light_shad: IntProperty(
        name=T("Тени от света"), min=0, max=255, default=100,
        update=_tc_field_changed)
    f_pole_shad: IntProperty(
        name=T("Тени столбов"), min=0, max=255, default=0,
        update=_tc_field_changed)
    f_far_clip: FloatProperty(
        name=T("Дальность прорисовки"), min=0.0, max=10000.0, default=800.0,
        update=_tc_field_changed)
    f_fog_start: FloatProperty(
        name=T("Начало тумана"), min=-2000.0, max=10000.0, default=100.0,
        update=_tc_field_changed)
    f_light_on_ground: FloatProperty(
        name=T("Свет на земле"), min=-5.0, max=5.0, default=1.0,
        update=_tc_field_changed)
    f_cloud_alpha: IntProperty(
        name=T("Прозрачность облаков"), min=0, max=255, default=0,
        update=_tc_field_changed)
    f_highlight_min: IntProperty(
        name=T("Мин. яркость бликов"), min=0, max=255, default=90,
        update=_tc_field_changed)
    f_water_fog: IntProperty(
        name=T("Туман под водой"), min=0, max=255, default=0,
        update=_tc_field_changed)
    f_dir_mult: FloatProperty(
        name=T("Множитель directional"), min=0.0, max=20.0, default=1.0,
        update=_tc_field_changed)


class INUSceneSettings(bpy.types.PropertyGroup):
    """All Scene-level INU Tools settings.

    Registered as ``bpy.types.Scene.inu_settings``. Field names keep
    their legacy ``gtatools_`` prefix to make the load_post migration
    a 1:1 attribute copy.
    """

    # ── Lightmap & validation ───────────────────────────────────
    gtatools_lightmap_result: StringProperty(name="Result", default="")
    gtatools_lightmap_path: StringProperty(name="Lightmap Path", default="lightmaps/lightmap.png")

    # inu_validate_issues uses a separate registered class — registered
    # in __init__.py at the bpy.types.Scene level since it predates this
    # consolidation and CollectionProperty(type=...) needs the class
    # registered first. Kept on Scene directly for now.

    # ── Particle 2DFX panel collapsibles ────────────────────────
    gtatools_pfx_exp_texture: BoolProperty(default=False)
    gtatools_pfx_exp_color: BoolProperty(default=False)
    gtatools_pfx_exp_size: BoolProperty(default=False)
    gtatools_pfx_exp_emission: BoolProperty(default=False)
    gtatools_pfx_exp_physics: BoolProperty(default=False)
    gtatools_pfx_exp_system: BoolProperty(default=False)
    gtatools_pfx_exp_curves: BoolProperty(default=False)

    gtatools_particle_sim: BoolProperty(
        name="Particle Simulation",
        description=T("Анимировать 2DFX частицы в viewport"),
        default=False,
        update=_update_particle_sim,
    )
    gtatools_model_id: StringProperty(name="Model ID", default="0")
    gtatools_vc_analysis: StringProperty(name="VC Analysis", default="")

    # ── UV Grid Randomizer ──────────────────────────────────────
    gtatools_uv_grid_cols: IntProperty(
        name="Columns",
        description=T("Количество колонок в сетке текстуры"),
        default=3, min=1, max=16,
        update=_update_uv_grid,
    )
    gtatools_uv_grid_rows: IntProperty(
        name="Rows",
        description=T("Количество рядов в сетке текстуры"),
        default=2, min=1, max=16,
        update=_update_uv_grid,
    )
    gtatools_uv_grid_align: EnumProperty(
        name="Alignment",
        description=T("Позиция UV в ячейке"),
        items=[
            ('CENTER', "Center", "Center of cell"),
            ('TOP_LEFT', "Top Left", "Top left corner"),
            ('TOP_CENTER', "Top", "Top center"),
            ('TOP_RIGHT', "Top Right", "Top right corner"),
            ('LEFT_CENTER', "Left", "Left center"),
            ('RIGHT_CENTER', "Right", "Right center"),
            ('BOTTOM_LEFT', "Bottom Left", "Bottom left corner"),
            ('BOTTOM_CENTER', "Bottom", "Bottom center"),
            ('BOTTOM_RIGHT', "Bottom Right", "Bottom right corner"),
        ],
        default='CENTER',
    )
    gtatools_uv_link_islands: BoolProperty(
        name="Link Polygons",
        description=T("Полигоны с пересекающимися UV перемещаются вместе"),
        default=False,
    )
    # ── Масштаб островов по сетке / тексель ──────────────────────
    gtatools_uv_texture_size: EnumProperty(
        name=T("Размер текстуры"),
        description=T("Размер текстуры в пикселях (для расчёта масштаба/текселя)"),
        items=[('128', "128", ""), ('256', "256", ""), ('512', "512", ""),
               ('1024', "1024", ""), ('2048', "2048", ""), ('4096', "4096", "")],
        default='512',
    )
    gtatools_uv_texel_value: FloatProperty(
        name=T("Значение"),
        description=T("Целевой размер: для «В сетку» — сколько пикселей должна "
                      "занимать высота(ряды)/ширина(колонки) острова; для текселя "
                      "— плотность px на юнит"),
        default=256.0, min=0.0,
    )

    # ── COL Light ───────────────────────────────────────────────
    gtatools_col_day_min: IntProperty(
        name="Day Min", description=T("Минимальное значение дневного света (тень)"),
        default=10, min=0, max=15)
    gtatools_col_day_max: IntProperty(
        name="Day Max", description=T("Максимальное значение дневного света (свет)"),
        default=15, min=0, max=15)
    gtatools_col_night_min: IntProperty(
        name="Night Min", description=T("Минимальное значение ночного света (тень)"),
        default=0, min=0, max=15,
        update=_col_light_invalidate_preview_proxy)
    gtatools_col_night_max: IntProperty(
        name="Night Max", description=T("Максимальное значение ночного света (свет)"),
        default=5, min=0, max=15,
        update=_col_light_invalidate_preview_proxy)
    gtatools_col_light_edge: FloatProperty(
        name="Edge",
        description=T("Сдвиг границы COL освещения"),
        default=0.0, min=-5.0, max=5.0, soft_min=-1.0, soft_max=1.0, step=1,
        update=_col_light_invalidate_preview_proxy)
    gtatools_col_light_threshold: IntProperty(
        name="Threshold",
        description=T("Порог яркости"),
        default=0, min=0, max=100,
        update=_col_light_invalidate_preview_proxy)
    gtatools_col_light_contrast: FloatProperty(
        name="Contrast",
        description=T("Контраст"),
        default=0.0, min=0.0, max=5.0, soft_min=0.0, soft_max=1.0, step=1,
        update=_col_light_invalidate_preview_proxy)
    gtatools_col_light_font_size: IntProperty(
        name="Font Size",
        description=T("Размер цифр на полигонах"),
        default=13, min=6, max=36,
        update=_col_light_invalidate_preview_proxy)
    gtatools_col_light_show_numbers: BoolProperty(
        name="Show Numbers",
        description=T("Показать цифры на полигонах"),
        default=True)

    # ── Map / IMG / Paths ───────────────────────────────────────
    gtatools_img_path: StringProperty(
        name="IMG Archive",
        description=T("Путь к .img архиву GTA SA для экспорта моделей"),
        default="", subtype='FILE_PATH',
        update=_save_paths_proxy)
    gtatools_export_img_target: EnumProperty(
        name=T("IMG для экспорта"),
        description=T("В какой IMG писать при «Экспорт в IMG»: родной IMG "
                      "модели (img_target_file) или конкретный архив из папки "
                      "игры. Обновляет запись, если модель там есть, иначе "
                      "добавляет"),
        items=_export_img_target_items)
    gtatools_fx_txd_path: StringProperty(
        name=T("TXD эффектов"),
        description=T(
            "Путь к .txd с текстурами эффектов GTA SA (короны, тени, вода — "
            "например particle.txd). Эти текстуры НЕ входят в аддон (это "
            "ассеты игры) и грузятся отсюда для превью 2DFX. Если пусто — "
            "ищутся автоматически в папке игры (Game Root)."),
        default="", subtype='FILE_PATH',
        update=_save_paths_proxy)
    gtatools_map_region: EnumProperty(
        name="Region",
        description=T("Район карты для импорта"),
        items=_get_map_region_items_proxy,
        update=_map_region_changed_proxy)
    gtatools_profile_enabled: BoolProperty(
        name=T("Профайлер"),
        description=T("Замерять время операций импорта и выводить тайминги "
                    "по стадиям в системную консоль (Window → Toggle System "
                    "Console). Полезно для диагностики тормозов"),
        default=False)
    gtatools_show_binary_ipls: BoolProperty(
        name="Show binary IPLs",
        description=T("Развернуть список бинарных IPL для галочек"),
        default=False)
    gtatools_show_text_ipls: BoolProperty(
        name="Show text IPLs",
        description=T("Развернуть список текстовых IPL для галочек"),
        default=False)
    gtatools_map_skip_2dfx: BoolProperty(
        name="Skip 2DFX",
        description=T("Не импортировать 2DFX-эффекты при импорте"),
        default=True)
    gtatools_map_skip_dupes: BoolProperty(
        name="Skip duplicates",
        description=T("Пропускать размещения, которые в сцене уже есть: "
                      "совпал ID модели и позиция. Удобно доимпортировать "
                      "соседний кусок карты, не плодя копии"),
        default=False)
    gtatools_img_use_gta_dat: BoolProperty(
        name="Use gta.dat",
        description=T("Искать все IDE/IPL через gta.dat"),
        default=False)
    gtatools_scene_alpha_on: BoolProperty(
        name=T("Альфа сцены"),
        description=T("Текущее состояние альфы на материалах сцены (для кнопки-переключателя)"),
        default=True)
    gtatools_img_skip_lod: BoolProperty(
        name="Skip LOD",
        description=T("Пропустить LOD модели при импорте"),
        default=True)
    gtatools_img_load_txd: BoolProperty(
        name="Load TXD",
        description=T("Загружать TXD текстуры вместе с DFF"),
        default=False)
    gtatools_map_load_col: BoolProperty(
        name="Load COL",
        description=T("Загружать коллизии из кеша при импорте карты"),
        default=False)
    gtatools_map_group_by_ipl: BoolProperty(
        name="Group by IPL",
        description=T("Создавать отдельную коллекцию на каждый IPL-файл"),
        default=True)
    # Active game — drives version dispatch in DFF/COL/TXD/IDE/IPL/IMG
    # writers and lint thresholds. Default SA (the addon's historical
    # focus). III/VC are work-in-progress — readers/writers gradually
    # gaining version-aware code paths.
    gtatools_game: EnumProperty(
        name=T("Игра"),
        description=T("Целевая игра для экспорта / валидации. Импорт авто-детектит игру по RW-версии"),
        items=[
            ('SA',  "SA",  "GTA: San Andreas (RW 3.6, COL3, IMG VER2)"),
            ('VC',  "VC",  "GTA: Vice City (RW 3.4, COL1, IMG VER1)"),
            ('III', "III", "GTA III (RW 3.3, COL1, IMG VER1)"),
        ],
        default='SA',
        update=_on_game_change)
    # Target platform — PC (vanilla RW geometry, D3D textures) vs
    # Mobile (Native Data PLG / OpenGL geometry, PVRTC/ETC1 textures).
    # Affects DFF reader/writer dispatch and export options. Импорт
    # авто-детектит платформу по наличию Native Data PLG чанков.
    gtatools_platform: EnumProperty(
        name=T("Платформа"),
        description=T("Целевая платформа: PC (vanilla) или Mobile (iOS/Android, Native Data PLG)"),
        items=[
            ('PC',     "PC",     "PC / Xbox / PS2 (vanilla RW geometry)"),
            ('MOBILE', "Mobile", "iOS / Android (Native Data PLG, War Drum OpenGL)"),
        ],
        default='PC')
    gtatools_game_root: StringProperty(
        name="Game Root",
        description=T("Корневая папка GTA SA"),
        default="", subtype='DIR_PATH',
        update=_save_paths_proxy)
    ariane_bridge_path: StringProperty(
        name="Ariane game",
        description=T("Папка игры с ariane для моста (обмен через <папка>\\ariane\\bridge). "
                      "Пусто → берётся Game Root, иначе %LOCALAPPDATA%"),
        default="", subtype='DIR_PATH')
    ariane_send_position: BoolProperty(
        name="Переносить позицию",
        description=T("При «Экспорт → Ariane» переносить и позицию/поворот объекта "
                      "(двигает инстанс в ariane и авто-сохраняет IPL). Выкл = только геометрия/текстуры"),
        default=True)
    ariane_send_col: BoolProperty(
        name="COL",
        description=T("Слать коллизию (COL) при «Экспорт → Ariane» (live-перезагрузка коллизии в ariane). "
                      "DFF и TXD шлются всегда"),
        default=False)
    ariane_send_lod: BoolProperty(
        name="LOD",
        description=T("Слать и LOD-модель (LOD<имя>) при «Экспорт → Ariane»"),
        default=True)
    ariane_live_sync: BoolProperty(
        name="Live-синхронизация",
        description=T("Live: перемещение, выделение и камера синхронизируются между ariane "
                      "и Blender в реальном времени (по ariane_guid). Один переключатель на "
                      "всё; требует включённого watcher"),
        default=False)
    ariane_send_ide: BoolProperty(
        name="IDE",
        description=T("Слать назад IDE-свойства (draw distance) при Экспорт → Ariane. "
                      "Меняет модель в ariane целиком (все инстансы). Выключено по умолчанию, "
                      "чтобы случайно не переписать дальность у моделей без правок"),
        default=False)
    ariane_sync_deletions: BoolProperty(
        name="Синхр. удаления",
        description=T("Live: синхронизация удалений в обе стороны. Удалил в Blender → мягкое "
                      "удаление инстанса в ariane; удалил в ariane → объект СКРЫВАЕТСЯ в "
                      "Blender (обратимо — undelete в ariane его показывает). Выключено по "
                      "умолчанию, чтобы можно было удалять свободно, не трогая другую сторону"),
        default=False)
    ariane_sync_time: BoolProperty(
        name=T("Синхр. время/погоду"),
        description=T("Live: время суток (ползунок таймцикла) и погода синхронизируются с "
                      "ariane в обе стороны. Ведущий — активное окно (как у камеры): крутишь "
                      "в ariane → двигается ползунок в Blender, и наоборот. Погода по индексу "
                      "(обе стороны читают один timecyc.dat). Плюс живая правка таймцикла: "
                      "меняешь поля среза (небо/солнце/туман/цвета) — ariane применяет их в "
                      "тот же кадр. Требует включённого watcher"),
        default=False)
    ariane_ui_more_open: BoolProperty(
        name="Ещё",
        description=T("Показать редкие/продвинутые действия моста"),
        default=False)
    ariane_panel_mode: EnumProperty(
        name="Режим панели",
        description=T("Вкладка панели Экспорт/Импорт: обычный экспорт/импорт или мост Ariane"),
        items=[
            ('IE', "Экспорт / Импорт", "Обычный экспорт/импорт в файлы"),
            ('ARIANE', "Ariane", "Мост с запущенной ariane (live-обмен)"),
        ],
        default='IE')
    gtatools_ide_ipl_mode: EnumProperty(
        name=T("Режим"),
        description=T("Переключение Импорт / Экспорт в панели IDE/IPL/IMG"),
        items=[
            ('IMPORT', T("Импорт"), T("Импорт моделей из игры")),
            ('EXPORT', T("Экспорт"), T("Запись IDE/IPL/IMG")),
            ('MAP', T("Карта"), T("Полный импорт/экспорт карты (gta.dat, "
                                  "бинарные/текстовые IPL, регионы)")),
        ],
        default='IMPORT')
    gtatools_light_mode: EnumProperty(
        name=T("Режим света"),
        description=T("Переключение инструментов в панели Освещение"),
        items=[
            ('PRELIGHT', "PreLight", T("Прилайт вершинными цветами")),
            ('COL', "PreLight COL", T("Вершинные цвета → COL Day/Night")),
            ('ITERA', "Itera", T("Интеграция с Itera Tools 3")),
        ],
        default='PRELIGHT')
    ariane_poll_interval: FloatProperty(
        name="Интервал опроса",
        description=T("Как часто watcher проверяет инбокс ariane (сек). "
                      "Опрос дешёвый — реальный импорт запускается только по poke-файлу от ariane"),
        default=1.0, min=0.1, max=10.0, subtype='TIME')
    gtatools_ide_path: StringProperty(
        name="IDE File",
        description=T("Путь к IDE файлу GTA SA"),
        default="", subtype='FILE_PATH',
        update=_save_paths_proxy)
    gtatools_ipl_path: StringProperty(
        name="IPL File",
        description=T("Путь к IPL файлу GTA SA"),
        default="", subtype='FILE_PATH',
        update=_save_paths_proxy)
    # Optional multi-IPL sync list. When populated, the IPL Sync
    # operator iterates every entry here instead of the single
    # ``gtatools_ipl_path`` above — lets one click reconcile a map
    # split across several .ipl files. Empty → falls back to the
    # single path (unchanged legacy behaviour). GTATOOLS_PathItem is
    # already registered (shared with the map analyzer lists).
    gtatools_ipl_sync_list: CollectionProperty(type=GTATOOLS_PathItem)
    # Active row for the scrollable template_list, and the collapse
    # toggle for its panel section (the list can grow long, so it's
    # collapsed by default and lives behind a disclosure triangle).
    gtatools_ipl_sync_list_index: IntProperty(default=0)
    gtatools_show_ipl_sync_list: BoolProperty(
        name=T("Sync несколько IPL"),
        description=T("Показать список IPL для пакетной синхронизации"),
        default=False)
    # Симметричный список IDE (round-trip): наполняется импортом, экспорт пишет
    # каждую модель в её IDE. Рядом с gtatools_ipl_sync_list в «Синхронизации».
    gtatools_ide_sync_list: CollectionProperty(type=GTATOOLS_PathItem)
    gtatools_ide_sync_list_index: IntProperty(default=0)
    # Сворачивание списков в панели Импорта (заголовок остаётся, список прячется).
    gtatools_show_import_ipl_list: BoolProperty(
        name=T("IPL для импорта"), default=True)
    gtatools_show_found_imgs: BoolProperty(
        name=T("IMG с моделями из IPL"), default=True)
    gtatools_show_found_ides: BoolProperty(
        name=T("IDE с моделями из IPL"), default=True)
    gtatools_show_map_io: BoolProperty(
        name=T("Ещё"),
        description=T("Импорт/экспорт по отдельности, синхронизация, секции IPL"),
        default=False)
    gtatools_show_img: BoolProperty(
        name=T("Архив IMG"),
        description=T("Достать/впихнуть отдельную модель в .img"),
        default=False)
    gtatools_show_sync_group: BoolProperty(
        name=T("Синхронизация с файлами"),
        description=T("Обновление сцены из файлов, отвязка, проверка"),
        default=False)
    # Сворачивание списков IPL/IDE в «Синхронизации» Экспорта (изначально
    # закрыты — разворачиваются треугольником в заголовке).
    gtatools_show_sync_ipl: BoolProperty(
        name=T("IPL для экспорта"), default=False)
    gtatools_show_sync_ide: BoolProperty(
        name=T("IDE для экспорта"), default=False)
    gtatools_show_ipl_extra: BoolProperty(
        name=T("Дополнительно (IPL)"),
        description=T("Секции IPL (cull/пути/гаражи) и замена Empty-заглушек"),
        default=False)
    gtatools_show_id_service: BoolProperty(
        name=T("База ID и сервис"),
        description=T("Управление пресетом ID: sync, из игры, GC, лимит FLA"),
        default=False)

    # ── GTA Geo: здания ─────────────────────────────────────────
    # Генерацию домов делает Auto-Building; нам нужен только путь к его
    # папке assets, откуда берётся заготовка.
    # Раскрытые блоки настроек Auto-Building. Вектором, а не россыпью
    # булевых свойств: блоков два десятка, и каждому своё поле — это
    # двадцать записей в PropertyGroup ради галочки «развернуть».
    gtatools_ab_wall_open: BoolVectorProperty(size=8, default=[False] * 8)
    gtatools_ab_open: BoolVectorProperty(size=16, default=[False] * 16)
    gtatools_building_assets: StringProperty(
        name=T("Папка Auto-Building"), default="", subtype='DIR_PATH',
        description=T("Папка assets аддона Auto-Building — в ней лежит "
                      "Auto-Building_1.2.6_Start.blend с заготовкой"))

    # ── Grass / plants.dat ──────────────────────────────────────
    # Editable working set of procedural-grass definitions. Imported
    # from data/plants.dat, edited in the «Трава» panel, written back.
    gtatools_grass_entries: CollectionProperty(type=INUGrassEntry)
    gtatools_grass_index: IntProperty(default=0)
    gtatools_plants_dat_path: StringProperty(
        name=T("plants.dat"),
        description=T("Путь к data/plants.dat. Пусто → берётся из Game Root"),
        default="", subtype='FILE_PATH')
    # Texture dictionary (plant1.txd style) for the scatter preview — the
    # grass card texture is taken from here so the preview looks like the
    # real thing. Empty → flat coloured cards.
    gtatools_grass_txd_path: StringProperty(
        name=T("Текстура .txd"),
        description=T("Путь к .txd с текстурой травы (напр. plant1.txd). "
                    "Пусто — карточки просто цветные"),
        default="", subtype='FILE_PATH')
    gtatools_grass_tint: BoolProperty(
        name=T("Тонировать цветом"),
        description=T("Умножать спрайт на цвет из plants.dat (как в игре). "
                    "Выключено — показывать текстуру как есть (для проверки)"),
        default=False)
    # Two ways of making grass: procedural (plants.dat, engine-generated)
    # or real geometry baked into the model and exported with it.
    gtatools_grass_mode: EnumProperty(
        name=T("Способ"),
        items=[
            ('PLANTS', "plants.dat", T("Процедурная трава движка (data/plants.dat)")),
            ('GEOMETRY', T("Генерация геометрией"),
             T("Реальная геометрия травы, экспортируется вместе с мешем")),
        ],
        default='PLANTS')

    # Live preview toggle: while on, «Показать траву» stays active
    # (depressed) and the preview auto-rebuilds when parameters change.
    gtatools_grass_live: BoolProperty(default=False)

    # Collapsible sections for the selected entry's parameters (disclosure
    # triangles, several can be open at once — like the Papka presetov UI).
    gtatools_grass_exp_preview: BoolProperty(default=True)
    gtatools_grass_exp_main: BoolProperty(default=True)
    gtatools_grass_exp_tex: BoolProperty(default=False)
    gtatools_grass_exp_color: BoolProperty(default=False)
    gtatools_grass_exp_size: BoolProperty(default=False)
    gtatools_grass_exp_wind: BoolProperty(default=False)

    # ── Zones / map.zon ─────────────────────────────────────────
    # Last .zon touched by import/export — prefills the export dialog so
    # the usual «загрузил → подвинул → записал обратно» loop is two clicks.
    gtatools_zon_path: StringProperty(
        name="map.zon",
        description=T("Путь к файлу зон (data/map.zon или data/info.zon)"),
        default="", subtype='FILE_PATH')

    # ── TXD settings ────────────────────────────────────────────
    gtatools_txd_auto_import: BoolProperty(
        name="Import TXD",
        description=T("Автоимпорт TXD текстур при импорте DFF"),
        default=True)
    # Постоянные настройки одиночного импорта DFF (панель «Импорт»). Операторы
    # импорта/драг-дропа берут из них дефолты в invoke().
    gtatools_import_auto_game: BoolProperty(
        name="Auto",
        description=T("Определять игру автоматически по RW-версии файла"),
        default=True)
    gtatools_import_game: EnumProperty(
        name=T("Игра"),
        description=T("Из какой игры импортируем (когда Auto выключен)"),
        items=[
            ('SA',  "SA",  T("Принудительно SA")),
            ('VC',  "VC",  T("Принудительно VC")),
            ('III', "III", T("Принудительно III")),
        ],
        default='SA')
    gtatools_import_2dfx: BoolProperty(
        name=T("Импортировать 2DFX"),
        description=T("Создавать пустышки-эффекты 2DFX из DFF (лампы/короны, "
                      "частицы, ped attractor, sun glare, знаки и т.д.). "
                      "Выключи, чтобы импортировать модель без эффектов"),
        default=True)
    # gtatools_import_weld_sharpen переехал в AddonPreferences
    # (INUAddonPreferences.import_weld_sharpen) — запоминается глобально,
    # дефолт OFF. Читается через tools.user_data.get_addon_prefs().
    gtatools_shared_txd_name: StringProperty(
        name="Shared TXD Name",
        description=T("Имя общего TXD файла"),
        default="")
    gtatools_txd_import_path: StringProperty(
        name="TXD Import Folder",
        description=T("Папка для поиска TXD при импорте DFF"),
        default="", subtype='DIR_PATH')

    # ── Asset Library Builder ───────────────────────────────────
    # Settings for the operator that turns the .inu_cache contents into
    # a portable Blender Asset Library (one .blend per category, with
    # thumbnails + IDE metadata embedded on every asset).
    gtatools_library_output_path: StringProperty(
        name="Library Output",
        description=T("Папка куда писать собранную Asset Library "
                    "(13 .blend файлов + blender_assets.cats.txt + textures/)"),
        default="", subtype='DIR_PATH')
    gtatools_enable_asset_builder: BoolProperty(
        name=T("Разрешить сборку Asset Library"),
        description=T(
            "Сборка Asset Library запускает ФОНОВЫЙ процесс Blender "
            "(blender --background) на встроенном скрипте. Это безопасно "
            "(запускается сам Blender, не сторонняя программа), но по "
            "умолчанию выключено. Включи, если осознанно пользуешься этой "
            "функцией."),
        default=False)
    gtatools_library_no_preview: BoolProperty(
        name=T("Без превью"),
        description=T("Не рендерить превьюшки. В ~3× быстрее, но Asset Browser "
                    "показывает заглушки вместо миниатюр"),
        default=False)
    gtatools_library_preview_size: IntProperty(
        name=T("Размер превью"),
        description=T("Размер превьюшек в пикселях. 128 — стандарт Blender, "
                    "256 крупнее но в 4× медленнее на рендере"),
        default=128, min=64, max=512)
    gtatools_library_skip_existing: BoolProperty(
        name=T("Пропускать готовые"),
        description=T("Пропускать категории чьи .blend уже существуют в Output. "
                    "Удобно при инкрементальном добавлении новых моделей "
                    "после установки модов"),
        default=True)
    gtatools_library_delete_cache: BoolProperty(
        name=T("Удалить кеш после сборки"),
        description=T("После успешной сборки библиотеки удалить папку "
                    ".inu_cache/ (DFF, COL, исходные PNG). Освобождает "
                    "много места на диске. Текстуры в самой библиотеке "
                    "остаются — при включённой галочке они принудительно "
                    "копируются в библиотеку (не симлинком). Будь готов "
                    "что Import Map после этого потребует повторно "
                    "«Извлечь ресурсы»"),
        default=False)
    # Дополнительные категории при региональной сборке. Когда Map Region
    # ≠ ALL, по умолчанию строится только regional + GENERIC + LOD.
    # Чекбоксы ниже позволяют опционально докинуть универсальные группы.
    # При region == ALL — игнорируются (всё равно строится всё).
    gtatools_library_include_vehicles: BoolProperty(
        name="Vehicles",
        description=T("Включить в сборку машины/мотоциклы/лодки/самолёты. "
                    "Имеет смысл только при выбранном регионе — при ALL "
                    "категория всё равно строится"),
        default=False)
    gtatools_library_include_peds: BoolProperty(
        name="Peds",
        description=T("Включить в сборку модели NPC / игрока. "
                    "Имеет смысл только при выбранном регионе"),
        default=False)
    gtatools_library_include_weapons: BoolProperty(
        name="Weapons",
        description=T("Включить в сборку модели оружия. "
                    "Имеет смысл только при выбранном регионе"),
        default=False)
    gtatools_library_include_interiors: BoolProperty(
        name="Interiors",
        description=T("Включить в сборку Interior-объекты (data/maps/interior). "
                    "Имеет смысл только при выбранном регионе"),
        default=False)

    # ── «Проверка» panel toggle state ─────────────────────────────────
    # Persisted with the .blend so the panel reflects actual hidden /
    # links-active state after Blender restart. Previously lived as
    # module-level globals which reset on every addon (re)load.
    gtatools_hide_dff: BoolProperty(
        name="Hide DFF",
        description=T("Currently hiding DFF meshes via the «Проверка» toggle"),
        default=False)
    gtatools_hide_lod: BoolProperty(
        name="Hide LOD",
        description=T("Currently hiding LOD meshes via the «Проверка» toggle"),
        default=False)
    gtatools_hide_col: BoolProperty(
        name="Hide COL",
        description=T("Currently hiding COL meshes via the «Проверка» toggle"),
        default=False)
    gtatools_hide_sha: BoolProperty(
        name="Hide SHA",
        description=T("Currently hiding shadow meshes via the «Проверка» toggle"),
        default=False)
    gtatools_links_active: BoolProperty(
        name="Model links overlay",
        description="DFF↔LOD↔COL dashed-link viewport overlay enabled",
        default=False)

    gtatools_audit_on_export: BoolProperty(
        name=T("Проверять модели при экспорте"),
        description=T(
            "После записи каждого DFF прогонять проверку на краши/баги в игре\n"
            "(индексы вершин/материалов, dummy машин, скин, 2DFX, имена и т.д.),\n"
            "предупреждения — в консоль и панель.\n"
            "ОТКЛЮЧИ для МАССОВОГО экспорта тысяч уже проверенных моделей —\n"
            "аудит гоняется на каждую модель и заметно замедляет."),
        default=False,
    )
    gtatools_dxt_backend: EnumProperty(
        name="",
        description=(
            T("Бэкенд сжатия DXT-текстур.\n"
            "Pure numpy, без внешних бинарей — соответствует требованиям\n"
            "extensions.blender.org. Поверх любого бэкенда работает кэш по\n"
            "session_uid: повторный экспорт без правок текстур почти мгновенный.")
        ),
        items=[
            ('numpy', "Numpy",
             T("Рекомендуемый режим для финального экспорта в IMG.\n"
             "Range-fit на mip 0 (главный уровень детализации) + bbox-int\n"
             "на меньших мипах. Лучшее качество без внешних бинарей.\n"
             "Скорость: ~0.5с на 54 текстурах (1024²).\n"
             "Бери его, если не уверен какой выбрать")),
            ('numpy_fast', "Numpy fast",
             T("Для массовых тестовых прогонов и итеративной работы над\n"
             "геометрией, когда пиксельное качество не критично.\n"
             "Bbox-int на всех мипах, ~1.7× быстрее режима Numpy\n"
             "(~0.27с на тех же 54 текстурах).\n"
             "Качество: на типовых текстурах (бетон, кирпич, дороги) на глаз\n"
             "не отличается. На текстурах с резкими альфа-границами — заборы\n"
             "(a_fence_*), листва, проволока — могут быть видимые артефакты\n"
             "до −5 dB PSNR. Перед релизом переключи обратно на Numpy")),
            ('gpu', "GPU",
             T("Work-in-progress. bpy.gpu compute shader через RGBA32F image-\n"
             "слот (в Blender 5.1 ещё нет публичного SSBO API). На практике\n"
             "не даёт выигрыша: readback Buffer'а упирается в Python GIL и\n"
             "выходит медленнее обоих CPU-режимов. Оставлено как задел —\n"
             "оживёт когда в Blender добавят GPUStorageBuf. Сейчас используй\n"
             "Numpy или Numpy fast")),
        ],
        default='numpy')

    # ── UI section toggles ──────────────────────────────────────
    gtatools_show_texture_settings: BoolProperty(
        name="Show Texture Settings", default=False)
    gtatools_show_paths_settings: BoolProperty(
        name="Show Paths Settings", default=False)
    gtatools_show_suffix_settings: BoolProperty(
        name="Show Suffix Settings", default=False)
    gtatools_show_dff_flags: BoolProperty(
        name="Show DFF Flags", default=False)
    gtatools_2dfx_show_props: BoolProperty(
        name="Show 2DFX Light Props", default=False)
    gtatools_2dfx_show_behavior: BoolProperty(
        name="Show 2DFX Behavior", default=False)
    gtatools_2dfx_show_shadow: BoolProperty(
        name="Show 2DFX Shadow", default=False)
    gtatools_2dfx_show_flags: BoolProperty(
        name="Show 2DFX Flags", default=False)

    gtatools_anim_tab: EnumProperty(
        name="Animation Tab",
        description=T("Раздел панели Анимации"),
        items=[
            ('CHAR', T("Персонажи"), T("IFP импорт/экспорт, IK Rig")),
            ('OBJ',  T("Объекты"),   "Animated Map Object"),
        ],
        default='CHAR')

    # ── Animated Map Object — scene-level eyedropper ─────────────
    # Replaces the «Setup» button: user picks meshes one by one with
    # the pipette, and the rig is auto-created on the first pick.
    # update= lives in ops/animobj_ops.py (lazy-imported to dodge
    # the circular import that would happen at module load time).
    gtatools_animobj_picker_target: EnumProperty(
        name=T("Куда добавить"),
        description=(
            T("Куда привесить выбранный пипеткой меш:\n"
            "  Новый pivot — анимированная часть (своя ось/скорость)\n"
            "  К существующему pivot — на тот же pivot что и предыдущая\n"
            "  К root — статичная часть без анимации")),
        items=[
            ('NEW_PIVOT', T("Новый pivot"),
             T("Создать новый pivot и привесить меш к нему — он будет крутиться отдельно")),
            ('PIVOT', T("К существующему pivot"),
             T("На первый pivot — общая анимация с другими мешами под ним")),
            ('ROOT', T("К root (статика)"),
             T("Статичная часть, не крутится")),
        ],
        default='NEW_PIVOT')
    gtatools_animobj_picker: PointerProperty(
        type=bpy.types.Object,
        name=T("Меш"),
        description=(
            T("Кликни на пипетку и выбери меш в сцене или 3D-окне. "
            "Если rig'а ещё нет — он создастся автоматически. "
            "После пика поле очищается — можно сразу подбирать следующий")),
        poll=lambda self, obj: obj is not None and obj.type == 'MESH',
        update=lambda self, context: _on_scene_animobj_pick(self, context))

    # ── Profile ─────────────────────────────────────────────────
    gtatools_profile: EnumProperty(
        name=T("Профиль"),
        description=T("Какие панели показывать в N-sidebar"),
        items=_profile_enum_items_proxy,
        update=_on_profile_changed_proxy)
    gtatools_profile_picked: StringProperty(
        name="Profile Picked Panel",
        default="")

    # ── IDE flags / suffixes / prefixes ─────────────────────────
    gtatools_show_ide_flags: BoolProperty(
        name="Show IDE Flags",
        description=T("Показать флаги IDE"),
        default=False)
    # Отдельный тумблер сворачивания бокса «Флаги IDE» в N-панели IDE/IPL/IMG
    # (независимо от свёрнутости флагов в Object Properties).
    gtatools_show_ide_flags_box: BoolProperty(
        name="Show IDE Flags box",
        description=T("Показать флаги IDE"),
        default=False)
    gtatools_suffix_dff: StringProperty(
        name="DFF Suffix", default="_DFF",
        description=T("Суффикс для DFF моделей"),
        update=_upd_suffix_dff_proxy)
    gtatools_suffix_lod: StringProperty(
        name="LOD Suffix", default="_LOD",
        description=T("Суффикс для LOD моделей"),
        update=_upd_suffix_lod_proxy)
    gtatools_suffix_col: StringProperty(
        name="COL Suffix", default="_COL",
        description=T("Суффикс для COL моделей"),
        update=_upd_suffix_col_proxy)
    gtatools_prefix_dff: StringProperty(
        name="DFF Prefix", default="",
        description=T("Префикс для DFF моделей"),
        update=_upd_prefix_dff_proxy)
    gtatools_prefix_lod: StringProperty(
        name="LOD Prefix", default="",
        description=T("Префикс для LOD моделей"),
        update=_upd_prefix_lod_proxy)
    gtatools_prefix_col: StringProperty(
        name="COL Prefix", default="",
        description=T("Префикс для COL моделей"),
        update=_upd_prefix_col_proxy)

    # ── X Radar Maker ───────────────────────────────────────────
    gtatools_radar_output: StringProperty(
        name="Radar Output", subtype='DIR_PATH', default="",
        description=T("Папка для сохранения тайлов радара"))
    gtatools_radar_grid: IntProperty(
        name="Radar Grid", default=8, min=1, max=16,
        description=T("Размер сетки (8 = 64 тайла)"))
    gtatools_radar_size: IntProperty(
        name="Radar Tile Size", default=256, min=64, max=4096,
        description=T("Размер тайла в пикселях"))
    gtatools_radar_height: FloatProperty(
        name="Radar Height", default=3000.0, min=100.0,
        description=T("Высота камеры"))
    gtatools_radar_specific: StringProperty(
        name="Radar Specific", default="",
        description=T("Индексы тайлов через запятую (0,1,5,63)"))

    # ── IMG / ID Manager ───────────────────────────────────────
    gtatools_show_img_list: BoolProperty(
        name="Show IMG List", default=False)
    gtatools_show_preset_dir: BoolProperty(
        name="Show Preset Folder", default=False)
    gtatools_col_auto_light: BoolProperty(
        name="Auto COL Light",
        description=(T("Заполнять байт освещения коллизии у фейсов, где он "
                     "равен 0 (нет COL-материала / day+night не заданы). "
                     "Повторяет поведение Kam's CST-экспорта (light=78), "
                     "иначе коллизия в игре остаётся неосвещённой. "
                     "Заданные вручную и импортированные значения не "
                     "трогаются")),
        default=True)
    gtatools_col_auto_light_value: IntProperty(
        name="COL Light",
        description=(T("Значение байта освещения для незаполненных фейсов. "
                     "78 = день≈15 / ночь 4 (дефолт Kam). Упаковка: "
                     "день = младший ниббл, ночь = старший ниббл")),
        default=78, min=0, max=255)
    gtatools_img_entries_index: IntProperty(default=0)
    gtatools_id_search: StringProperty(
        name="ID Search",
        description=T("Поиск по ID или имени модели"),
        default="")
    gtatools_id_page: IntProperty(
        name="ID Page", default=0, min=0, soft_max=1000)
    gtatools_id_preset: EnumProperty(
        name=T("Пресет ID"),
        description=T("Активный файл со списком ID"),
        items=_get_id_preset_items_proxy,
        update=_id_preset_update_proxy)

    # ── Texture loader ──────────────────────────────────────────
    gtatools_texture_path1: StringProperty(
        name="System Textures Path",
        description=T("Путь к папке с системными текстурами GTA"),
        default="", subtype='DIR_PATH',
        update=_save_paths_proxy)
    gtatools_texture_path2: StringProperty(
        name="Blend Folder Path",
        description=T("Путь к папке где находится .blend файл"),
        default="", subtype='DIR_PATH',
        update=_save_paths_proxy)

    # ── IK Rig ──────────────────────────────────────────────────
    gtatools_ik_display: EnumProperty(
        name=T("Форма IK-эмпти"),
        description=T("Какой примитив рисовать на IK-target и pole"),
        items=_ik_empty_types_proxy,
        default=0)
    gtatools_ik_color: FloatVectorProperty(
        name=T("Цвет IK-контроллов"),
        description=T("Цвет всех IK-контрольных костей"),
        subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(0.2, 1.0, 0.2, 1.0),
        update=_on_ik_color_change)
    gtatools_floor_offset: FloatProperty(
        name=T("Коллизия"),
        description=T("Высота виртуальной коллизии над плоскостью-полом"),
        default=0.05, min=0.0, max=1.0, step=1, precision=3,
        subtype='DISTANCE',
        update=_on_floor_offset_change)
    gtatools_ik_extras_show: BoolProperty(
        name=T("Дополнительно"),
        description=T("Настройки пола, коллизии, цвета IK"),
        default=False)
    gtatools_ik_root_motion: BoolProperty(
        name="Root motion",
        description=T("Включить для анимаций которые двигают персонажа"),
        default=False)
    gtatools_anim_tools_show: BoolProperty(
        name=T("Настройка анимации"),
        description=T("Утилиты для исправления sign-discontinuities"),
        default=False)
    gtatools_anim_fix_start: IntProperty(
        name=T("Старт"),
        description=T("Первый кадр диапазона"),
        default=0, min=0)
    gtatools_anim_fix_end: IntProperty(
        name=T("Конец"),
        description=T("Последний кадр диапазона"),
        default=10000, min=0)
    gtatools_smooth_axis_mode: EnumProperty(
        name="Smooth axis",
        description=(T("Ось вдоль которой сглаживать ключи между опорными. "
                     "ALL — все каналы в локальных координатах кости; "
                     "WORLD_X/Y/Z — только translation, в мировых "
                     "координатах (медленнее, but учитывает поворот родителей)")),
        items=[
            ('ALL', "All", "All channels (local)"),
            ('WORLD_X', "X", "World X (translation only)"),
            ('WORLD_Y', "Y", "World Y (translation only)"),
            ('WORLD_Z', "Z", "World Z (translation only)"),
        ],
        default='ALL')
    gtatools_mirror_axis: EnumProperty(
        name=T("Ось зеркала"),
        description=T("Плоскость отражения анимации в armature-space: "
                      "X — лево↔право (сагиттальная), Y — вперёд↔назад, "
                      "Z — верх↔низ"),
        items=[
            ('X', "X", T("Лево ↔ право (обычное зеркало)")),
            ('Y', "Y", T("Вперёд ↔ назад")),
            ('Z', "Z", T("Верх ↔ низ")),
        ],
        default='X')
    gtatools_mirror_swap_lr: BoolProperty(
        name=T("Менять L/R кости"),
        description=T("Обменивать данные парных костей 'L …'↔'R …' "
                      "(настоящее зеркало гуманоида). Выключи для чистого "
                      "геометрического флипа без обмена"),
        default=True)
    gtatools_mirror_root_rotation: BoolProperty(
        name=T("Отражать поворот Root"),
        description=T("Отражать и поворот корневой кости. Если после зеркала "
                      "персонаж встаёт «на голову» — выключи: тогда поворот "
                      "Root останется как в оригинале, отразится только "
                      "смещение (движение вперёд/назад)"),
        default=True)
    gtatools_mirror_flip_root_180: BoolProperty(
        name=T("Довернуть Root на 180°"),
        description=T("Автоматически добавляет поворот 180° к Root на каждом "
                      "кадре (заменяет ручную правку после зеркала). Компенсирует "
                      "разницу между rest- и игровой ориентацией скелета GTA"),
        default=True)
    gtatools_mirror_flip_root_axis: EnumProperty(
        name=T("Ось доворота Root"),
        description=T("Ось, вокруг которой Root доворачивается на 180°"),
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='X')
    gtatools_mirror_flip_root_space: EnumProperty(
        name=T("Пространство доворота Root"),
        description=T("В каком пространстве применять доворот 180°. Если "
                      "результат неверный — переключи вариант"),
        items=[
            ('LOCAL', T("Локальное"),
             "rot = rot @ flip (относительно самой кости)"),
            ('GLOBAL', T("Глобальное"),
             "rot = flip @ rot (относительно арматуры)"),
        ],
        default='GLOBAL')
    gtatools_mirror_invert_root_loc: EnumProperty(
        name=T("Инверсия Root Location"),
        description=T("Негировать одну координату смещения Root (замена ручного "
                      "«By Values / Over Cursor Value» при курсоре на 0)"),
        items=[
            ('NONE', T("Не инвертировать"), ""),
            ('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", ""),
        ],
        default='Y')
    gtatools_ik_chain_offset: FloatVectorProperty(
        name=T("Смещение куба руки/ноги"),
        description=T("Визуальный сдвиг кубов IK для рук и ног"),
        size=3, subtype='TRANSLATION',
        default=(0.0, 0.0, 0.0), precision=3,
        update=_on_chain_offset_change)
    gtatools_ik_size: FloatProperty(
        name=T("Размер"),
        description=T("Множитель размера всех IK-контролов"),
        default=1.0, min=0.1, max=5.0, step=10, precision=2,
        update=_on_ik_size_change)
    gtatools_ik_show_chain: BoolProperty(
        name=T("Руки/ноги"),
        description=T("Показывать кубы запястий и ступней"),
        default=True,
        update=_make_ik_visibility_setter(
            (frozenset({'chain'}), 'gtatools_ik_show_chain')))
    gtatools_ik_show_pole: BoolProperty(
        name=T("Локти/колени"),
        description=T("Показывать кубы-маркеры на локтях и коленях"),
        default=True,
        update=_make_ik_visibility_setter(
            (frozenset({'pole'}), 'gtatools_ik_show_pole')))
    gtatools_ik_show_rot: BoolProperty(
        name=T("Голова/торс/плечи"),
        description=T("Показывать кубы головы, верхнего торса и ключиц"),
        default=True,
        update=_make_ik_visibility_setter(
            (frozenset({'rot', 'head'}), 'gtatools_ik_show_rot')))
    gtatools_ik_show_root: BoolProperty(
        name=T("Корень"),
        description=T("Показывать корневой куб"),
        default=True,
        update=_make_ik_visibility_setter(
            (frozenset({'root'}), 'gtatools_ik_show_root')))

    gtatools_ifp_action: StringProperty(
        name="IFP Action",
        description="Select IFP animation to apply",
        update=_ifp_action_changed)

    # ── Water ───────────────────────────────────────────────────
    gtatools_water_flag: EnumProperty(
        name="Water Type",
        description="Water polygon visibility and depth type",
        items=[
            ('0', T("Обычная / Невидимая"), T("Глубокая вода, не отображается")),
            ('1', T("Обычная / Видимая"),   T("Глубокая вода с волнами")),
            ('2', T("Мелкая / Невидимая"),  T("Мелкая вода, не отображается")),
            ('3', T("Мелкая / Видимая"),    T("Мелкая вода, отображается")),
        ],
        default='1')
    gtatools_water_speed_x: FloatProperty(
        name="Speed X", default=0.0, min=-5.0, max=5.0)
    gtatools_water_speed_y: FloatProperty(
        name="Speed Y", default=0.0, min=-5.0, max=5.0)
    gtatools_water_speed_z: FloatProperty(
        name="Speed Z", default=0.05, min=-5.0, max=5.0)
    gtatools_water_wave_height: FloatProperty(
        name="Wave Height", default=0.1, min=0.0, max=10.0)

    # ── Bake ────────────────────────────────────────────────────
    gtatools_bake_ambient: FloatProperty(
        name="Ambient",
        description=T("Базовый рассеянный свет"),
        default=0.10, min=0.0, max=0.5)
    gtatools_bake_intensity: FloatProperty(
        name="Intensity",
        description=T("Множитель интенсивности света"),
        default=0.05, min=0.0001, max=0.5)
    gtatools_bake_gamma: FloatProperty(
        name="Gamma",
        description=T("Гамма-коррекция"),
        default=0.50, min=0.1, max=3.0)
    gtatools_bake_shadows: BoolProperty(
        name="Shadows",
        description=T("Включить тени при запекании"),
        default=True)

    # ── Texture Bake (карты → текстура; tools/bake/) ────────────
    # Отдельная подсистема от vertex-prelight выше: печёт AO/Diffuse/
    # Shadow/Bevel через Cycles и опц. складывает в одну diffuse-текстуру.
    # Композит строится ВСЕГДА (живой нодовый стек) — тумблера нет.
    gtatools_bake_resolution: EnumProperty(
        name=T("Размер"), description=T("Квадратный пресет размера (синхронит X/Y)"),
        items=_BAKE_POT_ITEMS, default='1024', update=_bake_res_update)
    gtatools_bake_res_x: IntProperty(
        name="X", description=T("Ширина текстуры (привязка к степеням двойки)"),
        default=1024, min=32, max=8192, update=_bake_res_x_update)
    gtatools_bake_res_y: IntProperty(
        name="Y", description=T("Высота текстуры (привязка к степеням двойки)"),
        default=1024, min=32, max=8192, update=_bake_res_y_update)
    gtatools_bake_samples: IntProperty(
        name="Samples",
        description=T("Сэмплы Cycles для шумных карт (AO / свет)"),
        default=16, min=1, max=512)
    gtatools_bake_show_mode: BoolProperty(
        name=T("Запекание"),
        description=T("Свернуть/развернуть выбор режима запекания"),
        default=True)
    gtatools_bake_aa: EnumProperty(
        name=T("АА"),
        description=T("Суперсэмплинг: печь во внутреннем бóльшем разрешении и "
                    "ужимать до целевого — убирает лесенки/полосы на текстуре "
                    "(как в TexTools). Работает и на Diffuse, в отличие от "
                    "сэмплов. Дороже по времени/памяти"),
        items=[('1', T("Выкл"),  T("Без сглаживания (быстро)")),
               ('2', "2×",    T("Печь в 2× и ужать")),
               ('4', "4×",    T("Печь в 4× и ужать (чисто, медленнее)"))],
        default='2')
    gtatools_bake_margin: IntProperty(
        name="Margin", description=T("Залив за края UV-островов, px"),
        default=8, min=0, max=64)
    # Имя выходной текстуры НЕ задаётся вручную — берётся из имени модели
    # (без префиксов/суффиксов _DFF/_LOD/_COL/hi/low) в ops/bake_ops.py.
    # Цель запекания = ВЫДЕЛЕННАЯ UV (mesh.uv_layers.active), источник =
    # рендер-UV (active_render, иконка 📷). Читаются прямо с меша — поэтому
    # отдельного поля для целевой UV нет (TexTools-подход).
    gtatools_bake_mode: EnumProperty(
        name=T("Режим"),
        description=T("Что запекаем"),
        items=[
            ('UV', "UV → UV",
             T("Запечь сам объект: текстуры берутся с рендер-UV (источник), "
             "результат пишется в выделенную UV (цель). Для trim-развёрток")),
            ('HILOW', "Hi → Low",
             T("Перенести деталь с хайполи на выделенный лоуполи (в разработке)")),
            ('CAMERA', T("Камера"),
             T("Отрендерить объект ортокамерой в текстуру с прозрачностью. "
             "Для billboard-деревьев/импостеров: ничего не обрезается, "
             "альфа берётся из силуэта")),
        ],
        default='UV')
    gtatools_bake_cam_axis: EnumProperty(
        name=T("Ракурс"),
        description=T("С какой стороны смотрит ортокамера"),
        items=[
            ('FRONT', T("Спереди −Y"), T("Камера на −Y, смотрит вдоль +Y")),
            ('BACK', T("Сзади +Y"), T("Камера на +Y, смотрит вдоль −Y")),
            ('RIGHT', T("Справа +X"), T("Камера на +X, смотрит вдоль −X")),
            ('LEFT', T("Слева −X"), T("Камера на −X, смотрит вдоль +X")),
            ('TOP', T("Сверху +Z"), T("Камера сверху, смотрит вниз")),
        ],
        default='FRONT')
    gtatools_bake_cam_padding: FloatProperty(
        name=T("Отступ"),
        description=T("Запас вокруг силуэта (доля размера) — чтобы крона не "
                    "упиралась в края текстуры"),
        default=0.05, min=0.0, max=0.5, subtype='FACTOR')
    gtatools_bake_cam_keep_uv: BoolProperty(
        name=T("Не сбрасывать мою UV"),
        description=T("Режим Камера обычно ПЕРЕЗАПИСЫВАЕТ активную UV проекцией "
                    "камеры. С этой галкой проекция пишется в ОТДЕЛЬНЫЙ слой "
                    "«INU_BakeUV», а твоя активная UV остаётся целой — на модели "
                    "две UV: своя + под запечённую текстуру"),
        default=False)
    gtatools_bake_bevel_size: FloatProperty(
        name=T("Bevel радиус"),
        description=T("Радиус скругления для Bevel-карты (в единицах сцены)"),
        default=0.05, min=0.0, soft_max=1.0, precision=3)
    gtatools_bake_bevel_samples: IntProperty(
        name="Bevel samples", default=8, min=2, max=64)
    gtatools_bake_selected_faces: BoolProperty(
        name=T("Только выделенные полигоны"),
        description=T("Запекать Bevel (UV→UV) только по ВЫДЕЛЕННЫМ граням — "
                      "карта ляжет лишь на них, и на сложной модели это сильно "
                      "быстрее. Действует ТОЛЬКО на Bevel; Diffuse/AO/Normal/"
                      "LightMap всегда печатаются целиком. Выдели грани в Edit "
                      "Mode перед запеканием"),
        default=False)
    gtatools_bake_selected_edges: BoolProperty(
        name=T("Только выделенные рёбра"),
        description=T("Bevel только вдоль ВЫДЕЛЕННЫХ рёбер: маска по вершинам "
                      "выделенных рёбер домножается на маску кромок. Действует "
                      "ТОЛЬКО на Bevel. Переход у ребра мягкий (интерполяция по "
                      "граням). Выдели рёбра в Edit Mode перед запеканием"),
        default=False)
    gtatools_bake_transparent_bg: BoolProperty(
        name=T("Прозрачный фон"),
        description=T("Вкл — фон запечённых карт прозрачный (альфа 0 там, где нет "
                      "развёртки). Выкл (по умолчанию) — фон заливается СРЕДНИМ "
                      "цветом текстуры (альфа 1), чтобы на швах/мипах не лезла "
                      "чернота. Не влияет на карту ALPHA и слои-декали — у них "
                      "альфа значима"),
        default=False)
    # ── Prelight: какие источники учитывать при запекании в vertex colors ──
    gtatools_prelight_use_point: BoolProperty(
        name=T("Point"),
        description=T("Учитывать точечные лампы (Point) при запекании прилайта"),
        default=True)
    gtatools_prelight_use_sun: BoolProperty(
        name=T("Sun"),
        description=T("Учитывать солнце (Sun) при запекании прилайта"),
        default=True)
    gtatools_prelight_use_spot: BoolProperty(
        name=T("Spot"),
        description=T("Учитывать прожекторы (Spot, с конусом) при запекании "
                      "прилайта"),
        default=True)
    gtatools_prelight_use_area: BoolProperty(
        name=T("Area"),
        description=T("Учитывать площадные лампы (Area) при запекании прилайта "
                      "(считаются как точечный источник)"),
        default=True)
    gtatools_prelight_use_hdri: BoolProperty(
        name=T("HDRI"),
        description=T("Добавить освещение от мира/HDRI (World): цвет неба "
                      "сэмплится по направлению нормали. Можно комбинировать с "
                      "лампами через тумблеры Point/Sun/Spot/Area"),
        default=False)
    gtatools_bake_use_scene_light: BoolProperty(
        name=T("Свет от сцены"),
        description=T("Печь Shadow / Diffuse-Lit от реальных источников света "
                    "сцены (твои лампы/солнце/world), как LightMap. Выкл — "
                    "внутренний калиброванный SUN (работает даже без ламп)"),
        default=True)
    gtatools_bake_light_energy_scale: FloatProperty(
        name=T("Свет (экспозиция)"),
        description=T("Множитель энергии внутреннего свет-рига для карт "
                    "Shadow / Diffuse-Lit. Больше — ярче"),
        default=1.0, min=0.0, soft_max=4.0)
    # Hi→Low: суффиксы пар ФИКСИРОВАНЫ (_hi / _low, см. tools.bake.HI_SUFFIX)
    # — поля выбора убраны намеренно. Настраивается только cage.
    gtatools_bake_cage_extrusion: FloatProperty(
        name="Cage",
        description=T("Выдавливание cage (на сколько раздуть лоуполи наружу "
                      "перед пуском лучей к хайполи). 0 = как TexTools: лучи "
                      "идут от самой поверхности лоуполи. БОЛЬШЕ 0 раздувает "
                      "лоуполи и на близких параллельных стенах кидает лучи на "
                      "СОСЕДНЮЮ стену → стены «меняются местами». Поднимай "
                      "только если хайполи торчит наружу за лоуполи"),
        default=0.0, min=0.0, soft_max=1.0, precision=3)
    gtatools_bake_max_ray: FloatProperty(
        name="Max Ray",
        description=T("Макс. дистанция луча (0 = без лимита, как TexTools)"),
        default=0.0, min=0.0, soft_max=1.0, precision=3)
    gtatools_bake_use_prelight: BoolProperty(
        name=T("Учитывать PreLight"),
        description=T("Запекать хайполи ВМЕСТЕ с прилайтом (vertex colors × "
                      "текстура): включает превью прилайта на хайполи на время "
                      "бейка. Выкл = чистая текстура без освещения прилайта"),
        default=False)
    gtatools_bake_isolate: BoolProperty(
        name=T("Изолировать объект"),
        description=T("На время бейка прятать прочие МЕШ-объекты сцены (лампы "
                      "не трогаются). Чинит чёрный AO (соседи по сцене больше "
                      "не затеняют модель) и ускоряет бейк (Cycles строит BVH "
                      "только по цели). Выкл = запекать с тенями от соседей"),
        default=True)
    # ── LightMap (карта GI от реального света сцены) ──────────────
    # Денойз общий для всех ШУМНЫХ карт (AO / Shadow / Diffuse Lit /
    # Emission GI / LightMap): OIDN-нода компоузера на Blender 4.x, bilateral
    # (numpy) на 5.x. Чистые карты (Diffuse/Normal/Emission/Bevel) не шумят —
    # к ним не применяется.
    gtatools_bake_denoise: BoolProperty(
        name=T("Шумоподавление"),
        description=T("Шумоподавление шумных карт (AO / Shadow / Diffuse Lit / "
                    "Emission GI / LightMap). Их запечка светозависимая/GI и "
                    "шумит — денойз чистит. К плоским картам не применяется"),
        default=True)
    gtatools_bake_lightmap_samples: IntProperty(
        name=T("Сэмплы LightMap"),
        description=T("Сэмплы Cycles для карты LightMap. GI шумнее AO — "
                    "нужно больше. С денойзом можно ниже"),
        default=128, min=1, max=2048)
    gtatools_bake_lightmap_apply: EnumProperty(
        name=T("Применить как"),
        description=T("Как использовать запечённый LightMap в GTA SA"),
        items=[
            ('STACK', T("Слой в стеке"),
             T("Оставить MULTIPLY-слоем в стеке — сведёте/сохраните сами, "
             "как остальные карты")),
            ('DIFFUSE', T("Впечь в диффуз"),
             T("Умножить LightMap × диффуз-текстуру → одна готовая текстура. "
             "Работает в ванильной GTA SA без шейдеров")),
            ('PRELIGHT', T("В vertex prelight"),
             T("Сэмплировать LightMap по вершинам в prelight-цвета «Day» — "
             "нативное статическое освещение GTA SA")),
        ],
        default='PRELIGHT')
    gtatools_bake_lightmap_quality: EnumProperty(
        name=T("Качество"),
        description=T("Пресет сэмплов LightMap (как в The_Lightmapper). "
                    "«Своё» — использовать ползунок «Сэмплы LightMap»"),
        items=[
            ('CUSTOM', T("Своё"), T("Из ползунка «Сэмплы LightMap»")),
            ('PREVIEW', T("Черновик"), T("32 сэмпла — быстро, для превью")),
            ('MEDIUM', T("Средне"), T("128 сэмплов")),
            ('HIGH', T("Высоко"), T("512 сэмплов")),
            ('PRODUCTION', T("Продакшн"), T("1024 сэмпла — чисто, медленно")),
        ],
        default='CUSTOM')
    gtatools_bake_lightmap_light_mode: EnumProperty(
        name=T("Режим света"),
        description=T("Какой свет запекать в LightMap"),
        items=[
            ('COMBINED', T("Полный (прямой+отражённый)"),
             T("Прямой свет + глобальное освещение (GI). Обычный выбор")),
            ('INDIRECT', T("Только отражённый (GI)"),
             T("Только непрямой отскок света — прямой оставить динамическим/в prelight")),
            ('DIRECT', T("Только прямой"),
             T("Только прямой свет и тени, без отскока")),
        ],
        default='COMBINED')
    gtatools_bake_lightmap_denoise_passes: BoolProperty(
        name=T("Денойз по albedo/normal"),
        description=T("Скормить денойзеру запечённые Diffuse (albedo) и Normal "
                    "как доп-пассы — чище результат на краях. Работает, если "
                    "эти карты запечены в том же размере"),
        default=True)
    gtatools_bake_lightmap_intensity: FloatProperty(
        name=T("Интенсивность"),
        description=T("Яркость запечённого LightMap. Меняется без "
                    "пере-запекания — кнопкой «Обновить лайтмап» ниже"),
        default=1.0, min=0.0, soft_max=4.0)
    gtatools_bake_lightmap_filter: FloatProperty(
        name=T("Смягчение"),
        description=T("Размытие LightMap — сглаживает зерно/блочность. 0 = "
                    "выкл. Меняется без пере-запекания — кнопкой «Обновить "
                    "лайтмап» ниже"),
        default=0.0, min=0.0, soft_max=8.0)
    # gtatools_bake_layers(+_index) переехали на объект (obj.inu) — стек
    # слоёв запекания теперь per-model. См. INUObjectProps в __init__.py.
    # Карта для формы «Добавить слой» (создание отделено от списка слоёв):
    # выбираешь карту здесь → кнопка добавляет слой с ней. Сама карта слоя
    # после создания не меняется (другой слой = другая карта).
    gtatools_bake_new_map: EnumProperty(
        name=T("Карта"), description=T("Какую карту добавить новым слоем"),
        items=_bake_map_enum_items_proxy,
        translation_context=_MAP_TR_CTX)        # пункты — английскими, без авто-перевода

    # ── Modulate Color preview ──────────────────────────────────
    gtatools_modulate_mode: EnumProperty(
        name="Modulate Color",
        description=T("Preview-режим"),
        items=[
            ('OFF',   "Off",   T("Без ambient — только prelight")),
            ('DAY',   "Day",   "EXTRASUNNY_LA Midday"),
            ('NIGHT', "Night", "EXTRASUNNY_LA Midnight"),
        ],
        default='OFF',
        update=_on_modulate_preview_update)
    gtatools_modulate_mix: FloatProperty(
        name=T("Прозрачность"),
        description=T("Сколько ambient добавлять к prelight"),
        default=0.002, min=0.0, max=1.0, precision=3,
        subtype='FACTOR',
        update=_on_modulate_preview_update)
    gtatools_modulate_contrast: FloatProperty(
        name=T("Контраст"),
        description=T("Контраст финального изображения"),
        default=0.0, min=-1.0, max=1.0,
        subtype='FACTOR',
        update=_on_modulate_preview_update)
    gtatools_modulate_gamma: FloatProperty(
        name=T("Гамма"),
        description=T("Гамма финального изображения"),
        default=0.8, min=0.1, max=4.0,
        update=_on_modulate_preview_update)

    # ── Визуальная коррекция превью прилайта (ТОЛЬКО вьюпорт) ─────
    # Дефолты грузятся из prelight.PRELIGHT_VIEW_CORRECTION при смене игры;
    # ползунками можно крутить живьём. На экспорт НЕ влияют.
    prelight_view_bright: FloatProperty(
        name=T("Яркость (превью)"),
        description=T("Только вьюпорт: яркость прилайта в превью. На экспорт НЕ влияет"),
        default=0.004, min=-1.0, max=1.0, precision=3,
        update=_prelight_view_update)
    prelight_view_contrast: FloatProperty(
        name=T("Контраст (превью)"),
        description=T("Только вьюпорт: контраст прилайта в превью. На экспорт НЕ влияет"),
        default=0.0, min=-1.0, max=1.0, precision=3,
        update=_prelight_view_update)
    prelight_view_gamma: FloatProperty(
        name=T("Гамма (превью)"),
        description=T("Только вьюпорт: гамма прилайта в превью. <1 — светлее. На экспорт НЕ влияет"),
        default=1.0, min=0.1, max=4.0, precision=3,
        update=_prelight_view_update)
    prelight_view_saturation: FloatProperty(
        name=T("Насыщенность (превью)"),
        description=T("Только вьюпорт: насыщенность прилайта в превью. 1 — как есть, 0 — ч/б. На экспорт НЕ влияет"),
        default=1.0, min=0.0, max=2.0, precision=3,
        update=_prelight_view_update)
    gtatools_show_prelight_view: BoolProperty(
        name=T("Коррекция превью"),
        description=T("Показать ползунки визуальной коррекции превью прилайта "
                      "(яркость/контраст/гамма/насыщенность). Только вьюпорт — "
                      "на экспорт не влияет"),
        default=False)

    # ── Prelight / VC processing ────────────────────────────────
    gtatools_prelight_preset: EnumProperty(
        name="Prelight Preset",
        items=_get_preset_items_proxy,
        description=T("Выбрать пресет настроек прелайта"))
    gtatools_v_offset: FloatProperty(
        name="V Offset",
        description=T("Смещение яркости"),
        default=0.0, min=-100.0, max=100.0)
    gtatools_vc_smooth_iterations: IntProperty(
        name="Iterations",
        description=(
            T("Сглаживание vertex colors между соседними вершинами.\n"
            "Iterations — количество проходов.\n"
            "Больше проходов = плавнее переходы")),
        default=1, min=1, max=50)
    gtatools_vc_smooth_factor: FloatProperty(
        name="Factor",
        description=(
            T("Сила сглаживания за один проход (0-1).\n"
            "0 — без эффекта, 1 — vertex берёт полное среднее соседей")),
        default=0.5, min=0.0, max=1.0)
    gtatools_vc_contrast: FloatProperty(
        name="Contrast",
        description=(
            T("Контраст vertex colors.\n"
            "1.0 — без изменений\n"
            "< 1.0 — меньше контраст\n"
            "> 1.0 — больше контраст")),
        default=1.0, min=0.0, max=3.0)
    gtatools_vc_brightness: FloatProperty(
        name="Brightness",
        description=(
            T("Яркость vertex colors (additive offset).\n"
            "0.0 — без изменений\n"
            "> 0 — светлее\n"
            "< 0 — темнее")),
        default=0.0, min=-1.0, max=1.0)
    gtatools_lift_shadows_strength: FloatProperty(
        name=T("Подтянуть тени"),
        description=(
            T("Подтягивает тёмные участки к самой яркой точке, "
            "сохраняя шаг между гранями.\n"
            "0 — без изменений\n"
            "0.3-0.5 — рекомендуемый диапазон\n"
            "1 — все цвета доходят до max (теряется визуальный шаг)")),
        default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    gtatools_vc_gamma: FloatProperty(
        name="Gamma",
        description=(
            T("Гамма-коррекция vertex colors.\n"
            "1.0 — без изменений\n"
            "< 1.0 — светлее (lift тени)\n"
            "> 1.0 — темнее (deepen тени)")),
        default=1.0, min=0.1, max=3.0)
    gtatools_fill_color: FloatVectorProperty(
        name="Fill Color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0)
    gtatools_scatter_intensity: FloatProperty(
        name="Intensity",
        description=T("Интенсивность рассеивания света"),
        default=1.0, min=0.1, max=5.0)
    gtatools_scatter_falloff: FloatProperty(
        name="Falloff",
        description=T("Скорость затухания света"),
        default=1.5, min=0.5, max=5.0)
    gtatools_scatter_iterations: IntProperty(
        name="Iterations",
        description=T("Количество слоёв соседних граней"),
        default=3, min=1, max=10)
    gtatools_scatter_radius: FloatProperty(
        name="Radius",
        description=T("Радиус поиска соседних граней"),
        default=0.0)

    # Scatter Color — paints chosen color around selected polys with
    # linear distance falloff. Independent from Scatter Light (which
    # spreads existing prelight).
    gtatools_scatter_color_color: FloatVectorProperty(
        name=T("Цвет"),
        description=T("Цвет, которым заливаются вершины вокруг выделенных полигонов"),
        subtype='COLOR_GAMMA', size=3,
        default=(1.0, 1.0, 1.0), min=0.0, max=1.0)
    gtatools_scatter_color_strength: FloatProperty(
        name=T("Сила"),
        description=T("Сила вклада цвета в центре. 0 — ничего не делать, 1 — полностью заменить vcols в центре на выбранный цвет"),
        default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    gtatools_scatter_color_distance: FloatProperty(
        name=T("Дальность"),
        description=T("Радиус как доля половины bbox-диагонали меша. 0 — только выделенные вершины, 1 — расходится на половину диагонали"),
        default=0.3, min=0.0, max=1.0, subtype='FACTOR')

    # ── Fill prelight (плоская заливка Day/Night одним цветом) ──
    # Дефолты — доминирующие тона из test.dff: день 124/124/124, ночь
    # 83/83/83 (в 0-1: 124/255≈0.486, 83/255≈0.325). subtype COLOR_GAMMA
    # хранит значение прямо в sRGB-пространстве, поэтому оно пишется
    # один-в-один в `color_srgb` → байт ровно 124 / 83.
    gtatools_fill_prelight_day: FloatVectorProperty(
        name=T("День"),
        description=T("Цвет дневного прилайта (Day). По умолчанию 124,124,124 — доминирующий тон"),
        subtype='COLOR_GAMMA', size=3,
        default=(124 / 255, 124 / 255, 124 / 255), min=0.0, max=1.0)
    gtatools_fill_prelight_night: FloatVectorProperty(
        name=T("Ночь"),
        description=T("Цвет ночного прилайта (Night). По умолчанию 83,83,83 — доминирующий тон"),
        subtype='COLOR_GAMMA', size=3,
        default=(83 / 255, 83 / 255, 83 / 255), min=0.0, max=1.0)
    gtatools_fill_prelight_selected_only: BoolProperty(
        name=T("Только выделенные"),
        description=T("Залить только выделенные меши (иначе — все меши сцены)"),
        default=False)

    # ── Foliage prelight — радиальный градиент кроны + tint листвы ──
    # Темнее в центре кроны, светлее на периферии (геометрический, без
    # света сцены). Материал листвы выбирается через prop_search по
    # material_slots активного объекта — ствол не трогается.
    gtatools_foliage_material_name: StringProperty(
        name=T("Материал листвы"),
        description=T("Красить только грани с этим материалом (пусто = весь меш). Ствол с другим материалом не затрагивается"),
        default="")
    gtatools_foliage_color_material_name: StringProperty(
        name=T("Материал (цвет)"),
        description=T("Материал для операции «Цвет листвы» (своя независимая "
                    "цель; пусто = весь меш)"),
        default="")
    gtatools_foliage_select_only: BoolProperty(
        name=T("Только выделенное"),
        description=T("Красить только выделенные в Edit Mode грани"),
        default=False)
    gtatools_foliage_metric: EnumProperty(
        name=T("Форма"),
        description=T("Как считать «внутри/снаружи»"),
        items=[
            ('SPHERE', T("Сфера"), T("3D-расстояние от центра кроны — для округлых крон")),
            ('CYLINDER', T("Цилиндр"), T("Горизонтальное расстояние от оси ствола — для вытянутых/колонновидных")),
        ],
        default='SPHERE')
    gtatools_foliage_inside: FloatProperty(
        name=T("Внутри"),
        description=T("Яркость в центре кроны (темнее)"),
        default=0.25, min=0.0, max=1.0, subtype='FACTOR')
    gtatools_foliage_outside: FloatProperty(
        name=T("Снаружи"),
        description=T("Яркость на периферии кроны (светлее)"),
        default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    gtatools_foliage_gamma: FloatProperty(
        name=T("Кривая"),
        description=T("Кривизна градиента: >1 расширяет светлую зону, <1 — тёмную"),
        default=1.0, min=0.1, max=4.0)
    gtatools_foliage_height_dark: FloatProperty(
        name=T("Затемнить низ"),
        description=T("Доп. затемнение нижней части кроны (самозатенение сверху). 0 — выкл"),
        default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    gtatools_foliage_color_height_dark: FloatProperty(
        name=T("Затемнить низ"),
        description=T("Доп. затемнение нижней части кроны для операции «Цвет» "
                    "(отдельно от настройки кроны). 0 — выкл"),
        default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    # ── Нарезка топологии под светом (для плавного прилайта ламп) ──
    gtatools_lightcut_segments: IntProperty(
        name=T("Сегменты"),
        description=T("Количество полигонов по окружности кольца (стороны "
                    "круга). Больше — круглее, но больше геометрии"),
        default=16, min=3, max=64, update=_lightcut_rebuild_proxy)
    gtatools_lightcut_target: PointerProperty(
        type=bpy.types.Object,
        name=T("Геометрия"),
        description=T("Меш, в который резать (земля под лампой). Пусто — найти "
                    "автоматически лучом вниз от лампы"),
        poll=lambda self, obj: obj is not None and obj.type == 'MESH')
    # ── Резак света v2 ──
    gtatools_lightcut_type: EnumProperty(
        name=T("Тип резака"),
        items=[('CYLINDER', T("Цилиндр"), T("Концентрические кольца (для пола)")),
               ('SPHERE', T("Сфера"), T("Сфера (радиус + сегменты)"))],
        default='CYLINDER', update=_lightcut_rebuild_proxy)
    gtatools_lightcut_ringlist: CollectionProperty(type=INULightCutRing)
    gtatools_lightcut_ring_index: IntProperty(default=0)
    gtatools_lightcut_separate: BoolProperty(
        name=T("Отдельным объектом"),
        description=T("ВКЛ — создать чистый отдельный диск (пол не трогать). "
                      "ВЫКЛ — врезать кольца прямо в пол"),
        default=True)
    gtatools_lightcut_radius: FloatProperty(
        name=T("Радиус"),
        description=T("Радиус зоны света (метры) — задаёт размер круга. "
                    "0 — взять Custom Distance лампы, если включён"),
        default=3.0, min=0.0, soft_max=50.0, subtype='DISTANCE',
        update=_lightcut_rebuild_proxy)
    gtatools_foliage_top_bright: FloatProperty(
        name=T("Подсветить верх"),
        description=T("Доп. подсветка макушки кроны (имитация солнца сверху). 0 — выкл"),
        default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    gtatools_foliage_top_height: FloatProperty(
        name=T("Высота подсветки"),
        description=T("Как высоко по Z достаёт подсветка верха: 1 — вся крона, "
                    "0.3 — только верхние 30%. Ниже — подсветки нет"),
        default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    gtatools_foliage_both_sides: BoolProperty(
        name=T("Обе стороны (дубли)"),
        description=T("GTA-листья часто продублированы (две грани в одной точке). "
                    "Красить обе стороны одинаково — иначе лист закрашен только "
                    "с одной стороны"),
        default=True)
    gtatools_foliage_variation: FloatProperty(
        name=T("Разброс"),
        description=T("Случайная вариация яркости по вершинам — листва неоднородна. "
                    "0 — выкл; чем больше, тем сильнее темнеют отдельные листья"),
        default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    gtatools_foliage_light_tint: FloatVectorProperty(
        name=T("Цвет света"),
        description=T("Оттенок освещённых листьев (периферия/снаружи кроны)"),
        subtype='COLOR_GAMMA', size=3,
        default=(0.55, 0.8, 0.3), min=0.0, max=1.0)
    gtatools_foliage_shadow_tint: FloatVectorProperty(
        name=T("Цвет тени"),
        description=T("Оттенок затенённых листьев (центр кроны) — обычно темнее и холоднее"),
        subtype='COLOR_GAMMA', size=3,
        default=(0.2, 0.35, 0.12), min=0.0, max=1.0)
    gtatools_foliage_tint_strength: FloatProperty(
        name=T("Сила цвета"),
        description=T("Сила оттенка. 0 — цвет не меняется (только затенение), 1 — полный tint"),
        default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    gtatools_foliage_blend: EnumProperty(
        name=T("Режим"),
        description=T("Как наложить результат на текущие vertex colors"),
        items=[
            ('MULTIPLY', T("Поверх (×)"), T("Умножить на существующий прилайт — затенение и оттенок накладываются, запечённый свет сохраняется")),
            ('REPLACE', T("Заменить"), T("Полностью заменить vertex colors результатом")),
        ],
        default='MULTIPLY')

    # ── Pipeline / Material preset ──────────────────────────────
    gtatools_export_pipeline: EnumProperty(
        items=[
            ('NONE', 'None', T("Без pipeline")),
            ('0x53F2009A', 'Vehicle', T("Pipeline кузова машины")),
            ('0x53F20098', 'Day/Night', T("Pipeline здания с day/night vertex colors")),
            ('0x53F2009C', 'Building', T("Простой pipeline здания")),
            ('PED', 'Ped',
             T("Preset для персонажа: pipeline ID = 0, SkinPLG обязателен, "
             "MatFX/day-night vcols отключены. Используется для экспорта "
             "скиннутых ped-моделей. На самом экспорте автоматически "
             "выставляет ped-friendly defaults: has_skin=True, "
             "day_cols=False, night_cols=False, matfx=False")),
        ],
        name="Pipeline",
        description=T("Рендер-пайплайн для экспорта DFF"),
        default='NONE',
        update=_inu_pipeline_changed_proxy)
    # Last seen pipeline value — без этого update-коллбэк не знает
    # из какого слота сохранять. Hidden, не показывается юзеру.
    inu_prev_pipeline_internal: StringProperty(default='NONE', options={'HIDDEN'})

    # ── Graph editor: keyframe thinning ──
    gtatools_thin_keys_mode: EnumProperty(
        name=T("Режим прореживания"),
        items=[
            ('NTH',  T("Каждый N-ный"), T("Оставить каждый N-ный ключ")),
            ('AUTO', T("Авто"),          T("Удалить избыточные (колинеарные) ключи")),
        ],
        default='NTH')
    gtatools_thin_keys_stride: IntProperty(
        name="N",
        description=T("Оставить каждый N-ный из выделенных (2 = удалить каждый второй)"),
        default=2, min=2, max=20)
    gtatools_thin_keys_error: FloatProperty(
        name=T("Порог ошибки"),
        description=T("Чем выше — тем агрессивнее срез избыточных ключей"),
        default=0.01, min=0.0001, max=1.0, precision=4)
    gtatools_thin_keys_interp: EnumProperty(
        name=T("Интерполяция"),
        items=[
            ('BEZIER',   T("Безье"),     T("Плавная кривая между ключами")),
            ('LINEAR',   T("Линейная"),  T("Прямые линии между ключами")),
            ('CONSTANT', T("Постоянная"), T("Ступенька — без интерполяции")),
        ],
        default='BEZIER')

    # ── Alpha materials bulk blend-mode tool (ops/alpha_tools) ───
    inu_alpha_mats: CollectionProperty(type=GTATOOLS_AlphaMatEntry)
    inu_alpha_mat_idx: IntProperty(default=0)
    gtatools_alpha_scope: EnumProperty(
        name=T("Область"),
        items=[
            ('SCENE',    T("Вся сцена"),        T("Собирать по всей сцене")),
            ('SELECTED', T("Только выделенные"), T("Только материалы выделенных объектов")),
        ],
        default='SCENE')
    gtatools_alpha_filter_mode: EnumProperty(
        name=T("Режим"),
        items=[
            ('NODE',        T("По ноде альфы"),   T("Альфа текстуры подключена ко входу Alpha шейдера")),
            ('CHANNEL',     T("Есть альфа-канал"), T("У текстуры есть значимый альфа-канал")),
            ('TRANSPARENT', T("Уже прозрачные"),  T("blend_method уже не Opaque")),
            ('ALL',         T("Все"),             T("Любой из критериев выше")),
        ],
        default='NODE')
    gtatools_alpha_bulk_blend: EnumProperty(
        name=T("Режим для всех"),
        items=_ALPHA_BLEND_ITEMS,
        default='CLIP')   # стандарт проекта: Колебание/DITHERED (см. compat)

    # ── GTA Material EFFECTS collapsible sections ───────────────
    gtatools_mat_show_vehicle: BoolProperty(
        name=T("Машина"), default=False,
        description=T("Свернуть/развернуть блок машины (слот цвета + Paintjob)"))
    gtatools_mat_show_fx: BoolProperty(
        name=T("GTA-эффекты"), default=False,
        description=T("Свернуть/развернуть GTA-эффекты (env map, bump, reflection, specular, dual, UV-аним)"))

    # Global export toggle — write per-vertex alpha into the DFF.
    # Default OFF: rarely needed and prone to accidental alpha (LOD etc.).
    gtatools_export_vertex_alpha: BoolProperty(
        name=T("Vertex Alpha"), default=False,
        description=T("Записывать вершинную альфу (прозрачность vertex colors) в DFF. "
                      "По умолчанию ВЫКЛ — редко нужна и может дать случайную альфу "
                      "(напр. на LOD). Включай осознанно для стёкол/листвы/заборов; "
                      "при выключенной альфа всегда 255 (непрозрачно)"))

    # ── Export All ──────────────────────────────────────────────
    gtatools_export_all_dff: BoolProperty(
        name="Export DFF",
        description=T("Экспортировать DFF при Export All"),
        default=True, update=_export_all_filter_update)
    gtatools_export_all_col: BoolProperty(
        name="Export COL",
        description=T("Экспортировать COL при Export All"),
        default=True, update=_export_all_filter_update)
    gtatools_export_all_lod: BoolProperty(
        name="Export LOD",
        description=T("Экспортировать LOD при Export All"),
        default=True, update=_export_all_filter_update)
    gtatools_export_all_txd: BoolProperty(
        name="Export TXD",
        description=T("Экспортировать TXD при Export All"),
        default=True, update=_export_all_filter_update)
    gtatools_export_all_cst: BoolProperty(
        name="Export CST",
        description=T("Экспортировать коллизию в текстовый .cst (Collision File Editor II) при Export All"),
        default=False, update=_export_all_filter_update)
    gtatools_export_all_ide_ipl: BoolProperty(
        name="IDE/IPL",
        description=T("После экспорта также дописать модели в IDE и IPL, "
                      "выбранные в панели IDE / IPL / IMG (id, имя, TXD, "
                      "дальность + расстановка и lod_index). Пути берутся из "
                      "полей IDE / IPL панели"),
        default=False)
    gtatools_export_all_col_empty: BoolProperty(
        name="Empty COL",
        description=T("Писать COL/CST без геометрии (ноль faces/вершин/сфер/боксов, нулевой bounds), но с именем модели. Для моделей, которым коллизия не нужна, но запись COL должна существовать и быть привязана к модели"),
        default=False)
    gtatools_export_all_single_dff: BoolProperty(
        name=T("Один DFF (машина/пед)"),
        description=T(
            "Экспортировать ВСЮ выделенную иерархию в ОДИН .dff (машина, "
            "пед, любая многокомпонентная модель), а не разбивать по именам "
            "на отдельные файлы. TXD/COL при этом пишутся одним общим "
            "файлом. Имя берётся из поля имени внизу."),
        default=False)
    gtatools_export_all_col_library: BoolProperty(
        name="COL Library",
        description=T("Писать все коллизии в один .col файл"),
        default=False)
    gtatools_export_all_col_library_name: StringProperty(
        name=T("Имя library .col"),
        description=T("Имя общего .col файла без расширения"),
        default="collision")
    gtatools_export_all_txd_shared: BoolProperty(
        name="Shared TXD",
        description=T("Писать все текстуры в один общий .txd файл"),
        default=False)
    gtatools_export_all_txd_shared_name: StringProperty(
        name=T("Имя общего .txd"),
        description=T("Имя общего .txd файла без расширения"),
        default="textures")
    gtatools_export_all_txd_merge: BoolProperty(
        name=T("Дописать в существующий TXD"),
        description=T(
            "Если .txd уже существует — добавить/обновить в нём текстуры "
            "модели, сохранив остальные текстуры файла (от других моделей). "
            "Иначе .txd перезаписывается целиком."),
        default=False)

    # ── Misc ────────────────────────────────────────────────────
    gtatools_vc_layers_expanded: BoolProperty(
        name="VC Layers Section Expanded",
        default=False)


    # ── Binary file scanner (DFF / COL / TXD lint) ─────────────
    gtatools_scan_dir: StringProperty(
        name=T("Папка"),
        description=T("Папка с DFF/COL/TXD для сканирования"),
        subtype='DIR_PATH', default="")
    gtatools_scan_recursive: BoolProperty(
        name=T("Включая подпапки"),
        description=T("Рекурсивный обход подпапок. По умолчанию выключено, чтобы случайно не просканировать всю систему"),
        default=False)
    gtatools_scan_dff: BoolProperty(name="DFF", default=True)
    gtatools_scan_col: BoolProperty(name="COL", default=True)
    gtatools_scan_txd: BoolProperty(name="TXD", default=True)
    gtatools_scan_only_errors: BoolProperty(
        name=T("Только ERROR"),
        description=T("Скрыть WARN/INFO в списке (фильтр draw, коллекция не пересоздаётся)"),
        default=True)
    gtatools_scan_report_target: EnumProperty(
        name=T("Куда сохранять отчёт"),
        items=[
            ('BLEND', T("Рядом с .blend"), T("В папке текущей сцены (.blend должен быть сохранён)")),
            ('SCAN',  T("В папке скана"),   T("Туда же, откуда брались файлы")),
            ('CUSTOM',T("Своя папка"),      T("Указать вручную")),
        ],
        default='BLEND')
    gtatools_scan_report_custom_path: StringProperty(
        name=T("Папка для отчёта"),
        subtype='DIR_PATH', default="")

    # ── Analysis combined panel (file scanner + map analyzer) ──
    # Внутренний toggle между двумя режимами в одной sub-panel
    # «Анализ карты/файлов» внутри Check.
    gtatools_analysis_mode: EnumProperty(
        name=T("Режим"),
        items=[
            ('FILES', T("Файлы"),  T("Скан DFF/COL/TXD на диске")),
            ('MAP',   T("Карта"),  "Cross-reference IDE/IPL"),
        ],
        default='FILES')

    # ── Map Analyzer (cross-reference IDE/IPL) ──────────────────
    gtatools_map_analyzer_mode: EnumProperty(
        name=T("Источник"),
        items=[
            ('DAT',    T("DAT файл"),   T("gta.dat / default.dat / кастомный — следует за IDE/IPL/IMG строками")),
            ('FOLDER', T("Папка"),      T("Сканировать все *.ide / *.ipl в указанной папке")),
            ('CUSTOM', T("Свои пути"),  T("Ручной список IDE и IPL файлов")),
        ],
        default='FOLDER')
    gtatools_map_analyzer_dat_path: StringProperty(
        name=T(".dat файл"),
        subtype='FILE_PATH', default="")
    gtatools_map_analyzer_folder: StringProperty(
        name=T("Папка с IDE/IPL"),
        subtype='DIR_PATH', default="")
    gtatools_map_analyzer_recursive: BoolProperty(
        name=T("Включая подпапки"),
        description=T("Рекурсивный обход подпапок при FOLDER-режиме"),
        default=True)
    gtatools_map_analyzer_check_img: BoolProperty(
        name=T("Проверять модели в IMG"),
        description=T("Авто-поиск всех *.img в области скана (DAT-строки / FOLDER walk / CUSTOM parent dirs) и cross-check IDE entries — flag missing DFF/TXD"),
        default=False)
    gtatools_map_analyzer_custom_ides: CollectionProperty(type=GTATOOLS_PathItem)
    gtatools_map_analyzer_custom_ipls: CollectionProperty(type=GTATOOLS_PathItem)
    gtatools_map_analyzer_only_errors: BoolProperty(
        name=T("Только ERROR"),
        description=T("Скрыть WARN/INFO в списке (фильтр draw)"),
        default=True)
    # Shared profile for File Scanner + Map Analyzer. Single EnumProperty
    # rather than per-tool — modders typically have one stance on
    # what counts as a problem; splitting would force them to keep
    # both panels in sync manually.
    # Texture Browser inputs. Reuses the same source-mode pattern as
    # Map Analyzer (DAT / FOLDER / CUSTOM) but with its own paths so
    # the user can index a different scope.
    gtatools_texture_browser_source: EnumProperty(
        name=T("Источник"),
        description=T("Откуда брать TXD-файлы для индекса"),
        items=[
            ('DAT',    "DAT",    T("Из gta.dat по путям сцены — все *.img и *.txd")),
            ('FOLDER', T("Папка"), T("Просканировать одну папку рекурсивно")),
            ('CUSTOM', T("Файлы"), T("Вручную выбранные .img / .txd")),
        ],
        default='DAT')
    gtatools_texture_browser_folder: StringProperty(
        name=T("Папка"),
        description=T("Папка со стандалон-TXD для сканирования"),
        subtype='DIR_PATH', default='')
    gtatools_texture_browser_custom: CollectionProperty(type=GTATOOLS_PathItem)
    gtatools_texture_browser_check_ide: BoolProperty(
        name="Cross-ref c IDE",
        description=T("Подсчитать сколько IDE-моделей используют каждый TXD (используется тот же набор IDE что и у Map Analyzer)"),
        default=True)
    gtatools_texture_browser_search: StringProperty(
        name=T("Поиск"),
        description=T("Фильтр по имени текстуры или TXD"),
        default='')

    gtatools_lint_profile: EnumProperty(
        name=T("Профиль"),
        description=T("Стандарт (vanilla SA) / FLA / Строгий / Мягкий"),
        items=[
            ('STANDARD', T("Стандарт"), T("Калибровано под vanilla SA — поведение из коробки")),
            ('FLA',      "FLA",      T("Считаем что Fastman92 Limit Adjuster установлен: глушим warnings про ID > 19999, interior > 18, COL surface > 178")),
            ('STRICT',   T("Строгий"), T("Жёстче пороги: draw_distance > 800m, mat > 50, vert > 16k, 2DFX > 100, texture > 512px. Для QA сборки")),
            ('LENIENT',  T("Мягкий"),  T("Прячем все INFO-уровни. Для легаси-проектов где informational шум перевешивает сигнал")),
        ],
        default='STANDARD')

    # ── Viewport Floater ──────────────────────────────────────
    # Plавающее окно с инфо по активному объекту. State for the
    # gpu+blf-drawn panel in ops/viewport_floater.py. Default OFF so
    # opening Blender never shows the floater until user toggles it.
    inu_floater_visible: BoolProperty(default=False)
    inu_floater_collapsed: BoolProperty(default=False)
    inu_floater_locked: BoolProperty(default=False)
    inu_floater_workspace: StringProperty(default="")
    inu_floater_x: IntProperty(default=40, min=-9999, max=9999)
    inu_floater_y: IntProperty(default=200, min=-9999, max=9999)

    # Import/Export floater (second instance, framework-driven)
    inu_floater_ie_visible: BoolProperty(default=False)
    inu_floater_ie_collapsed: BoolProperty(default=False)
    inu_floater_ie_locked: BoolProperty(default=False)
    inu_floater_ie_workspace: StringProperty(default="")
    inu_floater_ie_x: IntProperty(default=340, min=-9999, max=9999)
    inu_floater_ie_y: IntProperty(default=200, min=-9999, max=9999)

    # Validation floater (Проверка перед экспортом)
    inu_floater_val_visible: BoolProperty(default=False)
    inu_floater_val_collapsed: BoolProperty(default=False)
    inu_floater_val_locked: BoolProperty(default=False)
    inu_floater_val_workspace: StringProperty(default="")
    inu_floater_val_x: IntProperty(default=640, min=-9999, max=9999)
    inu_floater_val_y: IntProperty(default=200, min=-9999, max=9999)

    # Lighting floater
    inu_floater_light_visible: BoolProperty(default=False)
    inu_floater_light_collapsed: BoolProperty(default=False)
    inu_floater_light_locked: BoolProperty(default=False)
    inu_floater_light_workspace: StringProperty(default="")
    inu_floater_light_x: IntProperty(default=340, min=-9999, max=9999)
    inu_floater_light_y: IntProperty(default=400, min=-9999, max=9999)

    # IDE / IPL / IMG floater
    inu_floater_iii_visible: BoolProperty(default=False)
    inu_floater_iii_collapsed: BoolProperty(default=False)
    inu_floater_iii_locked: BoolProperty(default=False)
    inu_floater_iii_workspace: StringProperty(default="")
    inu_floater_iii_x: IntProperty(default=640, min=-9999, max=9999)
    inu_floater_iii_y: IntProperty(default=400, min=-9999, max=9999)

    # ── timecyc.dat ───────────────────────────────────────────
    # Вложенная группа, а не плоские gtatools_* поля: их там под сорок,
    # и все живут одним экраном панели.
    gtatools_timecyc: PointerProperty(type=INUTimecycProps)

    # Развёрнутые группы в панели «Проверка перед экспортом» — JSON-список
    # ключей групп (модель/категория). Список сворачиваемый: пусто = всё
    # свёрнуто (обзор), клик по строке разворачивает проблемы модели.
    inu_validate_expanded: StringProperty(default="", options={'HIDDEN'})

    # ── CollectionProperty fields with custom item types ──────
    inu_validate_issues: CollectionProperty(type=INUValidateIssue)
    gtatools_binary_ipls: CollectionProperty(type=GTATOOLS_BinaryIplEntry)
    gtatools_text_ipls: CollectionProperty(type=GTATOOLS_TextIplEntry)
    gtatools_img_entries: CollectionProperty(type=GTATOOLS_ImgFileEntry)
    # gtatools_bake_layers переехал на объект (obj.inu) — per-model стек.
