# INU_tools.ops.effects_ops — 2DFX presets + particle effects + emitter switch + attach/detach 2DFX + reload effects.fxp.
#
# Phase 3 (2026-04-26): operators moved from __init__.py.

import os
import bpy
from bpy.props import (
    StringProperty, BoolProperty, IntProperty, EnumProperty,
)

from .. import T
from ..tools.compat import safe_icon, inu_icon
class GTATOOLS_OT_apply_2dfx_preset(bpy.types.Operator):
    """Применить пресет 2DFX к активному объекту"""
    bl_idname = "gtatools.apply_2dfx_preset"
    bl_label = "INU: Apply 2DFX Preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'EMPTY':
            self.report({'WARNING'}, "No 2DFX object selected")
            return {'CANCELLED'}
        inu = obj.inu
        # _PRESET_MAP / _2DFX_PRESETS живут в пакете-родителе; импорт ленивый,
        # чтобы не ловить циклический импорт (effects_ops импортируется из
        # __init__.py).
        from .. import _PRESET_MAP, _2DFX_PRESETS
        preset_key = _PRESET_MAP.get(inu.preset_2dfx, 'Default')
        p = _2DFX_PRESETS[preset_key]

        inu.color_2dfx = (p['color'][0] / 255.0, p['color'][1] / 255.0,
                          p['color'][2] / 255.0, p['color'][3] / 255.0)
        inu.corona_size_2dfx = p['corona_size']
        inu.shadow_size_2dfx = p['shadow_size']
        obj['2dfx_corona_far_clip'] = p['corona_far_clip']
        obj['2dfx_pointlight_range'] = p['pointlight_range']
        obj['2dfx_corona_enable_reflection'] = p['corona_enable_reflection']
        obj['2dfx_shadow_z_distance'] = p['shadow_z_distance']
        obj['2dfx_shadow_color_multiplier'] = p['shadow_color_multiplier']
        obj['2dfx_flags1'] = p['flags1']
        obj['2dfx_flags2'] = p['flags2']
        # Set EnumProperty values
        inu.corona_tex_2dfx = p['corona_tex']
        inu.shadow_tex_2dfx = p['shadow_tex']
        inu.show_mode_2dfx = str(p['corona_show_mode'])
        inu.flare_type_2dfx = str(p['corona_flare_type'])

        self.report({'INFO'}, f"Preset '{preset_key}' applied")
        return {'FINISHED'}


class GTATOOLS_OT_create_2dfx(bpy.types.Operator):
    """Создать 2DFX эффект с настройками по умолчанию"""
    bl_idname = "gtatools.create_2dfx"
    bl_label = "INU: Create 2DFX Effect"
    bl_options = {'REGISTER', 'UNDO'}

    effect_type: EnumProperty(
        items=[
            ('LIGHT', 'Light', 'Street light / corona'),
            ('PARTICLE', 'Particle', 'Particle effect'),
            ('PED_ATTRACTOR', 'Ped Attractor', 'Ped attractor point'),
            ('SUN_GLARE', 'Sun Glare', 'Sun glare on surface'),
            ('ENTER_EXIT', 'Enter/Exit', 'Interior enter/exit marker'),
            ('ROAD_SIGN', 'Road Sign', 'On-mesh text sign'),
            ('ESCALATOR', 'Escalator', 'Escalator path'),
        ],
        default='LIGHT',
    )

    def execute(self, context):
        cursor_loc = context.scene.cursor.location

        display_map = {
            'LIGHT': ('PLAIN_AXES', 0.3),
            'PARTICLE': ('CIRCLE', 0.2),
            'PED_ATTRACTOR': ('CUBE', 0.15),
            'SUN_GLARE': ('SPHERE', 0.1),
            'ENTER_EXIT': ('ARROWS', 0.5),
            'ROAD_SIGN': ('PLAIN_AXES', 0.5),
            'ESCALATOR': ('SINGLE_ARROW', 0.5),
        }
        display_type, display_size = display_map[self.effect_type]

        name = f"2dfx_{self.effect_type.lower()}"
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = display_type
        obj.empty_display_size = display_size
        obj.location = cursor_loc

        obj.inu.type = '2DFX'
        obj.inu.effect_2dfx = self.effect_type

        # Создаём дефолтные custom properties
        if self.effect_type == 'LIGHT':
            obj.inu.color_2dfx = (1.0, 1.0, 1.0, 1.0)  # white
            obj.inu.corona_size_2dfx = 1.0
            obj.inu.shadow_size_2dfx = 8.0
            obj['2dfx_corona_far_clip'] = 100.0
            obj['2dfx_pointlight_range'] = 18.0
            obj['2dfx_corona_enable_reflection'] = 0
            obj['2dfx_shadow_color_multiplier'] = 40
            obj['2dfx_flags1'] = 96  # AT_DAY + AT_NIGHT
            obj['2dfx_shadow_z_distance'] = 0
            obj['2dfx_flags2'] = 0
            # Set display precision for float properties.
            # `id_properties_ui` added in Blender 3.0 — на 2.83–2.93 просто
            # пропускаем (precision дефолтный, в UI значит больше знаков).
            if hasattr(obj, 'id_properties_ui'):
                for key in ('2dfx_corona_far_clip', '2dfx_pointlight_range'):
                    obj.id_properties_ui(key).update(precision=1)
        elif self.effect_type == 'PARTICLE':
            obj['2dfx_effect_name'] = ""
        elif self.effect_type == 'PED_ATTRACTOR':
            obj['2dfx_attractor_type'] = 0
            obj['2dfx_rotation_matrix'] = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
            obj['2dfx_external_script'] = ""
            obj['2dfx_ped_probability'] = 0
        elif self.effect_type == 'ENTER_EXIT':
            obj.inu.ee_radius_x = 1.5
            obj.inu.ee_radius_y = 1.5
            obj.inu.ee_time_off = 24
        elif self.effect_type == 'ROAD_SIGN':
            obj.inu.sign_text0 = "TEXT"
            obj.inu.sign_size = (2.0, 1.0)
            obj.inu.sign_lines = 1
            obj.inu.sign_color = 'WHITE'
        elif self.effect_type == 'ESCALATOR':
            # Sample shape as offsets RELATIVE to the marker (Empty), so the
            # preview shows a ready escalator and moves with the Empty.
            obj.inu.esc_bottom = (0.0, 0.0, 0.0)
            obj.inu.esc_top = (0.0, 2.0, 3.0)
            obj.inu.esc_end = (0.0, 3.0, 3.0)
            obj.inu.esc_direction = '1'

        # Link to dedicated 2DFX collection (auto-create if missing)
        col_name = "2DFX"
        if col_name in bpy.data.collections:
            fx_col = bpy.data.collections[col_name]
        else:
            fx_col = bpy.data.collections.new(col_name)
            context.scene.collection.children.link(fx_col)
        fx_col.objects.link(obj)

        # Визуальный превью
        if self.effect_type == 'LIGHT':
            from .fx_preview import create_light_preview
            create_light_preview(obj)
        elif self.effect_type == 'PARTICLE':
            from .fx_preview import create_particle_preview
            create_particle_preview(obj)
        elif self.effect_type == 'ESCALATOR':
            from .fx_preview import create_escalator_preview
            create_escalator_preview(obj)
        elif self.effect_type == 'ROAD_SIGN':
            from .fx_preview import create_road_sign_preview
            create_road_sign_preview(obj)
        elif self.effect_type == 'ENTER_EXIT':
            from .fx_preview import create_enterexit_preview
            create_enterexit_preview(obj)

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj


        self.report({'INFO'}, f"2DFX {self.effect_type} created")
        return {'FINISHED'}


class GTATOOLS_OT_apply_2dfx_to_selected(bpy.types.Operator):
    """Скопировать настройки активного 2DFX на все ОСТАЛЬНЫЕ выделенные пустышки.

    Мульти-редактирование: правишь один 2DFX (он — активный объект),
    выделяешь группу целевых пустышек и применяешь — все настройки (цвет,
    размеры короны/тени, текстуры, флаги) уходят на всех разом. Превью у
    целей обновляется автоматически.

    Дублирование (Shift+D) больше не требует этой кнопки: копия 2DFX уже
    несёт все настройки и сама получает превью."""
    bl_idname = "gtatools.apply_2dfx_to_selected"
    bl_label = "INU: Apply 2DFX to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Enabled whenever the active object is a configured 2DFX. We do NOT
        # gate on selection count here — a greyed button with no explanation
        # just reads as "broken". The target check lives in execute() with a
        # clear message instead.
        obj = context.active_object
        inu = getattr(obj, 'inu', None)
        return bool(obj and obj.type == 'EMPTY' and inu
                    and getattr(inu, 'type', '') == '2DFX')

    def execute(self, context):
        from .fx_preview import remove_preview_children
        src = context.active_object
        src_inu = src.inu
        targets = [o for o in context.selected_objects
                   if o != src and o.type == 'EMPTY']
        if not targets:
            self.report({'WARNING'},
                        T("Выдели целевые пустышки (Shift+клик), источник — активным"))
            return {'CANCELLED'}
        n = 0
        for tgt in targets:
            tgt.inu.type = '2DFX'
            # inu PropertyGroup fields (colour, corona/shadow sizes, show-mode…)
            for p in src_inu.bl_rna.properties:
                if p.is_readonly or p.identifier == 'rna_type':
                    continue
                try:
                    setattr(tgt.inu, p.identifier, getattr(src_inu, p.identifier))
                except Exception:
                    pass

            # 2dfx_* custom IDProps — clear stale, then copy the source's.
            for key in list(tgt.keys()):
                if key.startswith('2dfx_'):
                    del tgt[key]
            for key in list(src.keys()):
                if key.startswith('2dfx_'):
                    tgt[key] = src[key]
                    if hasattr(tgt, 'id_properties_ui') and isinstance(src[key], float):
                        try:
                            tgt.id_properties_ui(key).update(
                                **{k: v for k, v in
                                   src.id_properties_ui(key).as_dict().items()
                                   if k in ('precision', 'description')})
                        except Exception:
                            pass

            tgt.empty_display_type = src.empty_display_type
            tgt.empty_display_size = src.empty_display_size

            # Drop the target's stale preview; the auto-rebuild timer
            # recreates it from the freshly-copied settings within ~1s. The
            # operator no longer builds the preview rig itself — that's the
            # timer's job now. Position is left untouched (stays put).
            try:
                remove_preview_children(tgt)
            except Exception as e:
                print(f"[INU] apply-2dfx preview clear skipped: {e}")
            n += 1

        self.report({'INFO'}, T("Настройки 2DFX применены к {0}").format(n))
        return {'FINISHED'}


class GTATOOLS_OT_load_fx_textures(bpy.types.Operator):
    """Загрузить текстуры эффектов (короны/тени/вода) из указанного .txd.

    Текстуры эффектов GTA SA в аддон НЕ входят (это ассеты игры) — укажи путь
    к .txd (например particle.txd) в поле выше, либо задай Game Root, и они
    загрузятся из твоей игры для превью 2DFX."""
    bl_idname = "gtatools.load_fx_textures"
    bl_label = "INU: Load FX Textures"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from .fx_preview import _ensure_fx_txd_loaded, _ensure_particle_txd_loaded
        n = _ensure_fx_txd_loaded() + _ensure_particle_txd_loaded()
        if n > 0:
            self.report({'INFO'},
                        f"{n} {T('текстур эффектов загружено')}")
        else:
            self.report({'WARNING'},
                        T("Текстуры эффектов не найдены — укажи particle.txd "
                          "или путь к игре (Game Root)"))
        return {'FINISHED'}


class GTATOOLS_OT_pick_fx_txd(bpy.types.Operator):
    """Выбрать .txd с текстурами эффектов (particle.txd и т.п.).

    Открывает файловый браузер (фильтр *.txd) и записывает путь в
    scene.inu_settings.gtatools_fx_txd_path. Сама загрузка текстур —
    отдельной кнопкой «Загрузить текстуры эффектов»
    (gtatools.load_fx_textures). Кнопка-папка живёт в заголовке панели
    2DFX (GTATOOLS_PT_2dfx_panel.draw_header_preset)."""
    bl_idname = "gtatools.pick_fx_txd"
    bl_label = "INU: Pick FX TXD"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default="*.txd", options={'HIDDEN'})

    def invoke(self, context, event):
        # Стартуем браузер из уже указанного пути, если он есть.
        cur = getattr(context.scene.inu_settings, 'gtatools_fx_txd_path', '') or ''
        if cur:
            self.filepath = bpy.path.abspath(cur)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}
        # Присваивание дёргает update= свойства (_save_paths_proxy) само.
        context.scene.inu_settings.gtatools_fx_txd_path = self.filepath
        # Отдельной кнопки «Загрузить текстуры эффектов» больше нет — грузим
        # сразу при выборе .txd: явный TXD + (если задан Game Root) частицы.
        from .fx_preview import _ensure_fx_txd_loaded, _ensure_particle_txd_loaded
        n = _ensure_fx_txd_loaded() + _ensure_particle_txd_loaded()
        self.report({'INFO'},
                    f"{os.path.basename(self.filepath)}: "
                    f"{n} {T('текстур эффектов загружено')}")
        return {'FINISHED'}


class GTATOOLS_OT_refresh_2dfx_preview(bpy.types.Operator):
    """Обновить визуальный превью (свет + корона + тень) для выбранного 2DFX"""
    bl_idname = "gtatools.refresh_2dfx_preview"
    bl_label = "INU: Refresh Preview"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'EMPTY'
                and getattr(obj, 'inu', None)
                and obj.inu.type == '2DFX'
                and obj.inu.effect_2dfx in (
                    'LIGHT', 'PARTICLE', 'ESCALATOR', 'ROAD_SIGN', 'ENTER_EXIT'))

    def execute(self, context):
        obj = context.active_object
        if obj.inu.effect_2dfx == 'LIGHT':
            from .fx_preview import update_light_preview
            update_light_preview(obj)
        elif obj.inu.effect_2dfx == 'ESCALATOR':
            from .fx_preview import update_escalator_preview
            update_escalator_preview(obj)
        else:
            from .fx_preview import update_particle_preview
            update_particle_preview(obj)
        self.report({'INFO'}, "2DFX preview updated")
        return {'FINISHED'}


class GTATOOLS_OT_remove_2dfx_preview(bpy.types.Operator):
    """Удалить визуальный превью из выбранного 2DFX"""
    bl_idname = "gtatools.remove_2dfx_preview"
    bl_label = "INU: Remove Preview"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'EMPTY'
                and getattr(obj, 'inu', None)
                and obj.inu.type == '2DFX')

    def execute(self, context):
        from .fx_preview import remove_preview_children
        obj = context.active_object
        remove_preview_children(obj)
        # Пользователь явно убрал превью — подавить авто-таймер (иначе
        # rebuild_missing_previews воскресит риг за один тик). Явная
        # пересборка (create_*_preview) флаг снимает.
        obj["inu_2dfx_no_preview"] = 1
        self.report({'INFO'}, "2DFX preview removed")
        return {'FINISHED'}


def _get_current_emitter(obj):
    """Return (fxf, system, emitter) for the obj's current effect+emitter, or None."""
    effect_name = obj.get('2dfx_effect_name', '') or ''
    if not effect_name:
        return None
    game_root = bpy.path.abspath(
        getattr(bpy.context.scene.inu_settings, 'gtatools_game_root', '') or ''
    )
    if not game_root:
        return None
    fxp_path = os.path.join(game_root, 'models', 'effects.fxp')
    if not os.path.isfile(fxp_path):
        return None
    from ..core import fxp as _fxp
    fxf = _fxp.load_cached(fxp_path)
    system = fxf.find(effect_name)
    if not system or not system.emitters:
        return None
    idx = max(0, min(int(obj.inu.particle_emitter_index), len(system.emitters) - 1))
    return fxf, system, system.emitters[idx]


def _load_curve_into_buffer(obj, curve_key: str) -> bool:
    """Parse 'INFO.FIELD' and populate obj.inu.particle_curve_keys."""
    if '.' not in curve_key:
        return False
    info_type, field_name = curve_key.split('.', 1)

    result = _get_current_emitter(obj)
    if not result:
        return False
    _fxf, _system, em = result

    info = em.info(info_type)
    if not info:
        return False
    curve = info.curves.get(field_name)
    if not curve:
        return False

    obj.inu.particle_curve_keys.clear()
    for kf in curve.keys:
        item = obj.inu.particle_curve_keys.add()
        item.time = float(kf.time)
        item.val = float(kf.val)
    obj.inu.particle_curve_key_index = 0
    return True


# Curve picker — search popup of all curves in current emitter.
_particle_curve_items_cache = [('', '<none>', '')]


def _particle_curve_items(self, context):
    global _particle_curve_items_cache
    obj = context.active_object
    if not obj:
        _particle_curve_items_cache = [('', '<no object>', '')]
        return _particle_curve_items_cache
    result = _get_current_emitter(obj)
    if not result:
        _particle_curve_items_cache = [('', '<no emitter>', '')]
        return _particle_curve_items_cache
    _fxf, _system, em = result
    items = []
    for info in em.infos:
        for field_name in info.curves.keys():
            key = f"{info.type}.{field_name}"
            items.append((key, key, ""))
    if not items:
        items = [('', '<no curves>', '')]
    _particle_curve_items_cache = items
    return _particle_curve_items_cache


def _audit_fxp(op, fxp_path, fxf):
    """DAT-47/48 audit after every effects.fxp write: NUM_PRIMS ≤ 8, known
    FX_INFO keywords with the right curve count, NUM_KEYS ≤ 127 and equal
    across an info's curves, |t| < 128, texture names ≤ 31 and present in
    ``<project>PC.txd`` (the engine derives the TXD from the fxp name)."""
    try:
        from ..core.textdata_lint import check_fxp
        from .textdata_audit import report_lint
        textures = None
        txd_path = fxp_path[:-4] + 'PC.txd' if fxp_path.lower().endswith('.fxp') else ''
        if txd_path and os.path.isfile(txd_path):
            try:
                from ..core.txd import read_txd_texture_names
                textures = set(read_txd_texture_names(txd_path))
            except Exception as e:                   # noqa: BLE001
                print(f"[INU lint] effectsPC.txd not readable: {e}")
        report_lint(op, os.path.basename(fxp_path), *check_fxp(fxf, textures))
    except Exception as e:                           # noqa: BLE001
        print(f"[INU lint] fxp audit failed: {e}")


def _create_blank_particle_system(name: str):
    """Return a brand-new FXSystem with sensible defaults — single emitter,
    a 'sphere' texture, basic emission/colour/size info blocks set to neutral
    values. Everything is plain Python objects from core.fxp; no Blender state.
    """
    from ..core.fxp import (
        FXSystem, FXEmitter, FXInfoBlock, FXCurve, FXKeyframe,
    )

    system = FXSystem()
    system.version = "109"
    system.header = [
        ('FILENAME', f'effects/particles/{name}.fxs'),
        ('NAME', name),
        ('LENGTH', '1.000'),
        ('LOOPINTERVALMIN', '0.000'),
        ('LENGTH', '0.000'),
        ('PLAYMODE', '2'),
        ('CULLDIST', '50.000'),
        ('BOUNDINGSPHERE', '0.0 0.0 0.0 0.0'),
    ]
    system.footer = [
        ('OMITTEXTURES', '0'),
        ('TXDNAME', 'NOTXDSET'),
    ]

    em = FXEmitter()
    em.base = [
        ('NAME', 'ParticleEmitter'),
        ('MATRIX', '1.000 0.000 0.000 0.000 1.000 0.000 0.000 0.000 1.000 0.000 0.000 0.000 '),
        ('TEXTURE', 'sphere'),
        ('TEXTURE2', 'NULL'),
        ('TEXTURE3', 'NULL'),
        ('TEXTURE4', 'NULL'),
        ('ALPHAON', '1'),
        ('SRCBLENDID', '4'),
        ('DSTBLENDID', '5'),
    ]
    em.footer = [
        ('LODSTART', '30.000'),
        ('LODEND', '50.000'),
    ]

    def _single(val):
        return FXCurve(looped=0, keys=[FXKeyframe(time=0.0, val=float(val))])

    def _start_end(a, b):
        return FXCurve(looped=0, keys=[
            FXKeyframe(time=0.0, val=float(a)),
            FXKeyframe(time=1.0, val=float(b)),
        ])

    # Emission: EMLIFE, EMRATE, EMSPEED, EMDIR
    em.infos.append(FXInfoBlock(
        type='EMLIFE',
        curves={'LIFE': _single(1.0), 'BIAS': _single(0.0)},
    ))
    em.infos.append(FXInfoBlock(
        type='EMRATE',
        curves={'RATE': _single(10.0)},
    ))
    em.infos.append(FXInfoBlock(
        type='EMSPEED',
        curves={'SPEED': _single(1.0), 'BIAS': _single(0.0)},
    ))
    em.infos.append(FXInfoBlock(
        type='EMDIR',
        curves={'DIRX': _single(0.0), 'DIRY': _single(0.0), 'DIRZ': _single(1.0)},
    ))

    # Rendering: SIZE, COLOUR (white, full alpha → white, zero alpha for fade-out)
    em.infos.append(FXInfoBlock(
        type='SIZE',
        scalars=[('TIMEMODEPRT', '1')],
        curves={
            'SIZEX': _start_end(0.3, 0.5),
            'SIZEY': _start_end(0.3, 0.5),
            # Same key count as SIZEX/SIZEY: the engine allocates one
            # time array per info from the FIRST curve's NUM_KEYS and
            # shares it across the block (DAT-47c).
            'SIZEXBIAS': _start_end(0.0, 0.0),
            'SIZEYBIAS': _start_end(0.0, 0.0),
        },
    ))
    em.infos.append(FXInfoBlock(
        type='COLOUR',
        scalars=[('TIMEMODEPRT', '1')],
        curves={
            'RED': _start_end(255.0, 255.0),
            'GREEN': _start_end(255.0, 255.0),
            'BLUE': _start_end(255.0, 255.0),
            'ALPHA': _start_end(255.0, 0.0),
        },
    ))

    system.emitters.append(em)
    return system


class GTATOOLS_OT_particle_effect_new(bpy.types.Operator):
    """Создать новый пустой эффект в effects.fxp"""
    bl_idname = "gtatools.particle_effect_new"
    bl_label = "INU: New Particle Effect"
    bl_options = {'REGISTER'}

    effect_name: StringProperty(
        name="Name",
        description=T("Имя нового эффекта (должно быть уникальным)"),
        default="prt_custom",
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'EMPTY'
                and getattr(obj, 'inu', None)
                and obj.inu.type == '2DFX'
                and obj.inu.effect_2dfx == 'PARTICLE')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'effect_name')
        layout.label(text=T("Создастся пустая система с одним эмиттером"), **inu_icon(safe_icon('INFO')))
        layout.label(text=T("Текстура: sphere. Жизнь 1с, rate 10/с, цвет белый"))

    def execute(self, context):
        obj = context.active_object
        name = self.effect_name.strip()
        if not name:
            self.report({'ERROR'}, T("Имя пустое"))
            return {'CANCELLED'}

        game_root = bpy.path.abspath(context.scene.inu_settings.gtatools_game_root or '')
        if not game_root:
            self.report({'ERROR'}, T("Game Root не задан"))
            return {'CANCELLED'}
        fxp_path = os.path.join(game_root, 'models', 'effects.fxp')
        if not os.path.isfile(fxp_path):
            self.report({'ERROR'}, f"{T('effects.fxp не найден: ')}{fxp_path}")
            return {'CANCELLED'}

        # Auto-backup on first write
        backup_path = fxp_path + '.bak'
        if not os.path.isfile(backup_path):
            import shutil
            try:
                shutil.copy2(fxp_path, backup_path)
                print(f"[FXP] backed up to {backup_path}")
            except Exception as e:
                self.report({'ERROR'}, f"{T('Не удалось создать бэкап: ')}{e}")
                return {'CANCELLED'}

        from ..core import fxp as _fxp
        try:
            fxf = _fxp.read_fxp(fxp_path)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка парсинга: ')}{e}")
            return {'CANCELLED'}

        if fxf.find(name) is not None:
            self.report({'ERROR'}, T("Эффект '") + name + T("' уже существует"))
            return {'CANCELLED'}

        new_system = _create_blank_particle_system(name)
        fxf.systems.append(new_system)

        try:
            _fxp.write_fxp(fxp_path, fxf)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка записи: ')}{e}")
            return {'CANCELLED'}
        _audit_fxp(self, fxp_path, fxf)

        _fxp.clear_cache()
        # Force the enum to rebuild its cached item list on next draw
        global _particle_enum_cache_key
        _particle_enum_cache_key = None

        # Switch the object to the newly created effect
        obj['2dfx_effect_name'] = name
        obj.inu.particle_emitter_index = 0
        try:
            # Lazy import — defined in package __init__; module-level import
            # would be circular (effects_ops is imported from __init__).
            from .. import _populate_particle_props_from_fxp
            _populate_particle_props_from_fxp(obj, name, 0)
        except Exception as e:
            print(f"[2DFX Particle] populate failed: {e}")
        try:
            from .fx_preview import update_particle_preview
            update_particle_preview(obj)
        except Exception:
            pass

        self.report({'INFO'}, f"{T('Создан эффект: ')}{name}")
        return {'FINISHED'}


class GTATOOLS_OT_particle_effect_delete(bpy.types.Operator):
    """Удалить текущий эффект из effects.fxp (с автобэкапом)"""
    bl_idname = "gtatools.particle_effect_delete"
    bl_label = "INU: Delete Particle Effect"
    bl_options = {'REGISTER'}

    confirm: BoolProperty(
        name=T("Я понимаю что это перезапишет effects.fxp"),
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'EMPTY'
                and getattr(obj, 'inu', None)
                and obj.inu.type == '2DFX'
                and obj.inu.effect_2dfx == 'PARTICLE'
                and (obj.get('2dfx_effect_name', '') or ''))

    def invoke(self, context, event):
        self.confirm = False
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        name = obj.get('2dfx_effect_name', '') or ''
        layout.label(text=T(f"Удалить '{name}' из effects.fxp?"), **inu_icon(safe_icon('ERROR')))
        layout.label(text=T("Действие необратимо (хотя есть .bak)"), **inu_icon(safe_icon('INFO')))

        # Warn if other scene objects reference the same effect
        count = 0
        for o in bpy.data.objects:
            if o.type != 'EMPTY':
                continue
            inu = getattr(o, 'inu', None)
            if not inu or inu.type != '2DFX' or inu.effect_2dfx != 'PARTICLE':
                continue
            if (o.get('2dfx_effect_name', '') or '') == name:
                count += 1
        if count > 1:
            layout.label(
                text=T(f"⚠ {count} объектов в сцене используют этот эффект"),
                **inu_icon(safe_icon('ERROR')),
            )

        layout.prop(self, 'confirm')

    def execute(self, context):
        if not self.confirm:
            self.report({'WARNING'}, T("Подтверждение не получено"))
            return {'CANCELLED'}

        obj = context.active_object
        name = (obj.get('2dfx_effect_name', '') or '').strip()
        if not name:
            self.report({'ERROR'}, T("Имя эффекта пустое"))
            return {'CANCELLED'}

        game_root = bpy.path.abspath(context.scene.inu_settings.gtatools_game_root or '')
        if not game_root:
            self.report({'ERROR'}, T("Game Root не задан"))
            return {'CANCELLED'}
        fxp_path = os.path.join(game_root, 'models', 'effects.fxp')
        if not os.path.isfile(fxp_path):
            self.report({'ERROR'}, f"{T('effects.fxp не найден: ')}{fxp_path}")
            return {'CANCELLED'}

        backup_path = fxp_path + '.bak'
        if not os.path.isfile(backup_path):
            import shutil
            try:
                shutil.copy2(fxp_path, backup_path)
                print(f"[FXP] backed up to {backup_path}")
            except Exception as e:
                self.report({'ERROR'}, f"{T('Не удалось создать бэкап: ')}{e}")
                return {'CANCELLED'}

        from ..core import fxp as _fxp
        try:
            fxf = _fxp.read_fxp(fxp_path)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка парсинга: ')}{e}")
            return {'CANCELLED'}

        before = len(fxf.systems)
        fxf.systems = [s for s in fxf.systems if s.name != name]
        removed = before - len(fxf.systems)
        if removed == 0:
            self.report({'WARNING'}, T("Эффект '") + name + T("' не найден в effects.fxp"))
            return {'CANCELLED'}

        try:
            _fxp.write_fxp(fxp_path, fxf)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка записи: ')}{e}")
            return {'CANCELLED'}
        _audit_fxp(self, fxp_path, fxf)

        _fxp.clear_cache()
        global _particle_enum_cache_key
        _particle_enum_cache_key = None

        # Clear the object's effect name so it doesn't point at a missing entry
        obj['2dfx_effect_name'] = ""
        obj.inu.particle_emitter_index = 0

        try:
            from .fx_preview import update_particle_preview
            update_particle_preview(obj)
        except Exception:
            pass

        self.report({'INFO'}, f"{T('Удалено: ')}{name}")
        return {'FINISHED'}


class GTATOOLS_OT_particle_curve_select(bpy.types.Operator):
    """Выбрать кривую для редактирования"""
    bl_idname = "gtatools.particle_curve_select"
    bl_label = "INU: Select Curve"
    bl_property = "curve_name"
    bl_options = {'REGISTER'}

    curve_name: EnumProperty(name="Curve", items=_particle_curve_items)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'EMPTY'
                and getattr(obj, 'inu', None)
                and obj.inu.type == '2DFX'
                and obj.inu.effect_2dfx == 'PARTICLE')

    def execute(self, context):
        obj = context.active_object
        if obj is None or not self.curve_name:
            return {'CANCELLED'}
        obj.inu.particle_curve_name = self.curve_name
        if _load_curve_into_buffer(obj, self.curve_name):
            n = len(obj.inu.particle_curve_keys)
            self.report({'INFO'}, f"{self.curve_name}: {n}{T(' ключей')}")
        else:
            self.report({'WARNING'}, f"{T('Не удалось загрузить ')}{self.curve_name}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}


class GTATOOLS_OT_particle_curve_key_add(bpy.types.Operator):
    """Добавить ключевой кадр в конец кривой"""
    bl_idname = "gtatools.particle_curve_key_add"
    bl_label = "INU: Add Keyframe"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and getattr(obj, 'inu', None) and obj.inu.particle_curve_name

    def execute(self, context):
        obj = context.active_object
        keys = obj.inu.particle_curve_keys
        item = keys.add()
        # Default new key to t=1 and the last val, or fallback
        if len(keys) >= 2:
            prev = keys[-2]
            item.time = min(prev.time + 0.1, 1.0)
            item.val = prev.val
        else:
            item.time = 0.0
            item.val = 0.0
        obj.inu.particle_curve_key_index = len(keys) - 1
        return {'FINISHED'}


class GTATOOLS_OT_particle_curve_key_select_row(bpy.types.Operator):
    """Выбрать активный ключ для удаления"""
    bl_idname = "gtatools.particle_curve_key_select_row"
    bl_label = "INU: Select Keyframe Row"
    bl_options = {'REGISTER'}

    index: IntProperty(default=0)

    def execute(self, context):
        obj = context.active_object
        if obj and getattr(obj, 'inu', None):
            obj.inu.particle_curve_key_index = self.index
        return {'FINISHED'}


class GTATOOLS_OT_particle_curve_key_remove(bpy.types.Operator):
    """Удалить активный ключевой кадр"""
    bl_idname = "gtatools.particle_curve_key_remove"
    bl_label = "INU: Remove Keyframe"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and getattr(obj, 'inu', None)
                and len(obj.inu.particle_curve_keys) > 0)

    def execute(self, context):
        obj = context.active_object
        keys = obj.inu.particle_curve_keys
        idx = max(0, min(obj.inu.particle_curve_key_index, len(keys) - 1))
        keys.remove(idx)
        if obj.inu.particle_curve_key_index >= len(keys):
            obj.inu.particle_curve_key_index = max(0, len(keys) - 1)
        return {'FINISHED'}


class GTATOOLS_OT_particle_curve_write(bpy.types.Operator):
    """Записать буфер ключей обратно в effects.fxp для выбранной кривой"""
    bl_idname = "gtatools.particle_curve_write"
    bl_label = "INU: Write Curve to FXP"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and getattr(obj, 'inu', None)
                and obj.inu.particle_curve_name
                and len(obj.inu.particle_curve_keys) > 0)

    def execute(self, context):
        obj = context.active_object
        curve_key = obj.inu.particle_curve_name
        if '.' not in curve_key:
            self.report({'ERROR'}, f"{T('Неверный ключ кривой: ')}{curve_key}")
            return {'CANCELLED'}
        info_type, field_name = curve_key.split('.', 1)

        game_root = bpy.path.abspath(context.scene.inu_settings.gtatools_game_root or '')
        if not game_root:
            self.report({'ERROR'}, T("Game Root не задан"))
            return {'CANCELLED'}
        fxp_path = os.path.join(game_root, 'models', 'effects.fxp')
        if not os.path.isfile(fxp_path):
            self.report({'ERROR'}, f"{T('effects.fxp не найден: ')}{fxp_path}")
            return {'CANCELLED'}

        effect_name = obj.get('2dfx_effect_name', '') or ''
        if not effect_name:
            self.report({'ERROR'}, T("Эффект не выбран"))
            return {'CANCELLED'}

        # Auto-backup on first write
        backup_path = fxp_path + '.bak'
        if not os.path.isfile(backup_path):
            import shutil
            try:
                shutil.copy2(fxp_path, backup_path)
                print(f"[FXP] backed up to {backup_path}")
            except Exception as e:
                self.report({'ERROR'}, f"{T('Не удалось создать бэкап: ')}{e}")
                return {'CANCELLED'}

        from ..core import fxp as _fxp
        from ..core.fxp import FXCurve, FXKeyframe, FXInfoBlock
        try:
            fxf = _fxp.read_fxp(fxp_path)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка парсинга: ')}{e}")
            return {'CANCELLED'}

        system = fxf.find(effect_name)
        if not system or not system.emitters:
            self.report({'ERROR'}, T("Система '") + effect_name + T("' не найдена"))
            return {'CANCELLED'}

        em_idx = max(0, min(int(obj.inu.particle_emitter_index), len(system.emitters) - 1))
        em = system.emitters[em_idx]

        info = em.info(info_type)
        if info is None:
            info = FXInfoBlock(type=info_type, scalars=[('TIMEMODEPRT', '1')])
            em.infos.append(info)

        # Build the new curve from the buffer, sorted by time
        keys_sorted = sorted(
            ((float(k.time), float(k.val)) for k in obj.inu.particle_curve_keys),
            key=lambda kv: kv[0],
        )
        info.curves[field_name] = FXCurve(
            looped=0,
            keys=[FXKeyframe(time=t, val=v) for t, v in keys_sorted],
        )

        try:
            _fxp.write_fxp(fxp_path, fxf)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка записи: ')}{e}")
            return {'CANCELLED'}
        _audit_fxp(self, fxp_path, fxf)

        _fxp.clear_cache()

        # Refresh the scalar fields from the updated FXP and rebuild preview
        try:
            from .. import _populate_particle_props_from_fxp
            _populate_particle_props_from_fxp(obj, effect_name, em_idx)
        except Exception:
            pass
        try:
            from .fx_preview import update_particle_preview
            update_particle_preview(obj)
        except Exception:
            pass

        self.report({'INFO'}, f"{curve_key}: {len(keys_sorted)}{T(' ключей записано')}")
        return {'FINISHED'}


class GTATOOLS_OT_particle_emitter_switch(bpy.types.Operator):
    """Переключить редактируемый эмиттер в системе с несколькими"""
    bl_idname = "gtatools.particle_emitter_switch"
    bl_label = "INU: Switch Particle Emitter"
    bl_options = {'REGISTER', 'UNDO'}

    direction: IntProperty(default=1)  # +1 = next, -1 = prev

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'EMPTY'
                and getattr(obj, 'inu', None)
                and obj.inu.type == '2DFX'
                and obj.inu.effect_2dfx == 'PARTICLE')

    def execute(self, context):
        obj = context.active_object
        name = obj.get('2dfx_effect_name', '') or ''
        if not name:
            self.report({'WARNING'}, T("Эффект не выбран"))
            return {'CANCELLED'}
        # Lazy import — both helpers live in the package __init__.
        from .. import (_get_effect_emitter_count,
                        _populate_particle_props_from_fxp)
        total = _get_effect_emitter_count(name)
        if total <= 1:
            self.report({'INFO'}, T("У эффекта один эмиттер"))
            return {'CANCELLED'}

        cur = int(obj.inu.particle_emitter_index)
        new_idx = (cur + self.direction) % total
        obj.inu.particle_emitter_index = new_idx
        try:
            _populate_particle_props_from_fxp(obj, name, new_idx)
        except Exception as e:
            self.report({'ERROR'}, f"populate error: {e}")
            return {'CANCELLED'}
        try:
            from .fx_preview import update_particle_preview
            update_particle_preview(obj)
        except Exception as e:
            print(f"[2DFX Particle] preview update failed: {e}")

        self.report({'INFO'}, f"Emitter {new_idx + 1}/{total}")
        return {'FINISHED'}


class GTATOOLS_OT_reload_effects_fxp(bpy.types.Operator):
    """Перечитать effects.fxp с диска (сбросить кэш)"""
    bl_idname = "gtatools.reload_effects_fxp"
    bl_label = "INU: Reload effects.fxp"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..core import fxp as _fxp
        _fxp.clear_cache()
        self.report({'INFO'}, "effects.fxp cache cleared")
        return {'FINISHED'}


# Zone assignment per FX_INFO block type, matching GTA SA / FX Editor order.
# The native parser reads blocks sequentially and expects them grouped by
# zone: Emission(1) → Physics(2) → Rendering(3). Out-of-order blocks
# (e.g. EMANGLE after COLOUR) are silently ignored by the game engine.
_INFO_ZONES = {
    # Zone 1 — Emission / birth
    'EMLIFE': 1, 'EMRATE': 1, 'EMSPEED': 1, 'EMANGLE': 1, 'EMDIR': 1,
    'EMSIZE': 1, 'EMROTATION': 1, 'EMPOS': 1, 'EMWEATHER': 1,
    # Zone 2 — Physics / movement
    'FORCE': 2, 'FRICTION': 2, 'WIND': 2, 'ROTSPEED': 2, 'NOISE': 2,
    'JITTER': 2, 'GROUNDCOLLIDE': 2, 'ATTRACTPT': 2, 'FLOAT': 2,
    'UNDERWATER': 2,
    # Zone 3 — Rendering / visuals
    'SIZE': 3, 'COLOUR': 3, 'COLOURBRIGHT': 3, 'SPRITERECT': 3, 'DIR': 3,
    'ANIMTEX': 3, 'TRAIL': 3, 'FLAT': 3, 'HEATHAZE': 3, 'SELFLIT': 3,
}


def _info_zone(type_name: str) -> int:
    return _INFO_ZONES.get(type_name, 3)


def _sort_infos_by_zone(em) -> None:
    """Stable-sort an emitter's info blocks into canonical zone order."""
    em.infos.sort(key=lambda i: _info_zone(i.type))


# Mandatory curve fields per FX_INFO block type, with sensible defaults.
# When we create a new info block from scratch during save, the game crashes
# if any of these fields are missing — the native parser allocates a fixed
# struct per block and reads garbage for absent fields. These defaults come
# from analysing the pristine effects.fxp across all 161 emitters.
_INFO_TEMPLATES = {
    'COLOUR': (
        [('TIMEMODEPRT', '1')],
        {'RED': 255.0, 'GREEN': 255.0, 'BLUE': 255.0, 'ALPHA': 255.0},
    ),
    'COLOURBRIGHT': (
        [('TIMEMODEPRT', '1')],
        {'RED': 255.0, 'GREEN': 255.0, 'BLUE': 255.0, 'ALPHA': 255.0, 'BIAS': 0.0},
    ),
    'SIZE': (
        [('TIMEMODEPRT', '1')],
        {'SIZEX': 1.0, 'SIZEY': 1.0, 'SIZEXBIAS': 0.0, 'SIZEYBIAS': 0.0},
    ),
    'EMLIFE':     ([], {'LIFE': 1.0, 'BIAS': 0.0}),
    'EMRATE':     ([], {'RATE': 10.0}),
    'EMSPEED':    ([], {'SPEED': 1.0, 'BIAS': 0.0}),
    'EMDIR':      ([], {'DIRX': 0.0, 'DIRY': 0.0, 'DIRZ': 1.0}),
    'EMANGLE':    ([], {'MIN': 0.0, 'MAX': 0.0}),
    'EMSIZE': (
        # Zone 1 blocks never carry TIMEMODEPRT in original GTA SA data;
        # adding one here desynchronises the native field-order parser.
        [],
        # Interleaved axis order — GTA SA's native parser reads these
        # sequentially by position, not by name. Wrong order => particles
        # emit along a degenerate line/point instead of the intended volume.
        {
            'RADIUS': 0.0,
            'SIZEMINX': 0.0, 'SIZEMAXX': 0.0,
            'SIZEMINY': 0.0, 'SIZEMAXY': 0.0,
            'SIZEMINZ': 0.0, 'SIZEMAXZ': 0.0,
        },
    ),
    'EMPOS':      ([], {'X': 0.0, 'Y': 0.0, 'Z': 0.0}),
    'EMROTATION': ([], {'ANGLEMIN': 0.0, 'ANGLEMAX': 0.0}),
    'FORCE': (
        [('TIMEMODEPRT', '1')],
        {'FORCEX': 0.0, 'FORCEY': 0.0, 'FORCEZ': 0.0},
    ),
    'FRICTION':   ([('TIMEMODEPRT', '1')], {'FRICTION': 0.0}),
    'WIND':       ([('TIMEMODEPRT', '1')], {'WINDFACTOR': 0.0}),
    'NOISE':      ([('TIMEMODEPRT', '1')], {'NOISE': 0.0}),
    'JITTER':     ([('TIMEMODEPRT', '1')], {'JITTERFACTOR': 0.0}),
    'ROTSPEED': (
        [('TIMEMODEPRT', '1')],
        {'MINCW': 0.0, 'MAXCW': 0.0, 'MINCCW': 0.0, 'MAXCCW': 0.0},
    ),
    'GROUNDCOLLIDE': (
        [('TIMEMODEPRT', '1')],
        {'BOUNCE': 0.0, 'SPEEDMULT': 1.0, 'BOUNCEERROR': 0.0},
    ),
}


def _apply_particle_props_to_emitter(obj, em) -> int:
    """Write obj.inu.particle_* back into an FXEmitter, but ONLY for fields
    that differ from what a fresh sample of `em` would produce.

    This preserves multi-keyframe curves the user hasn't touched: if the
    user only edited `particle_size_start`, we rewrite just SIZE.SIZEX/SIZEY
    with a 2-keyframe curve and leave every other curve alone.

    Returns the number of fields actually applied.
    """
    from ..core.fxp import FXCurve, FXKeyframe, FXInfoBlock
    # `_sample_particle_from_emitter` живёт в __init__.py — lazy-импорт
    # внутри функции т.к. модульный from-import при загрузке вызывает
    # circular dependency (effects_ops регится из __init__.py).
    from .. import _sample_particle_from_emitter
    inu = obj.inu
    fresh = _sample_particle_from_emitter(em)

    applied = 0
    eps = 1e-4

    def _close_scalar(a, b):
        return abs(float(a) - float(b)) < eps

    def _close_vec(a, b):
        if len(a) != len(b):
            return False
        return all(abs(float(x) - float(y)) < eps for x, y in zip(a, b))

    def _set_base(key, value):
        sv = str(value)
        for i, (k, _) in enumerate(em.base):
            if k == key:
                em.base[i] = (k, sv)
                return
        em.base.append((key, sv))

    def _get_or_create_info(type_name):
        info = em.info(type_name)
        if info is not None:
            return info
        # Build fresh block populated with ALL mandatory fields at sensible
        # defaults. The subsequent per-field writes below will overwrite the
        # specific fields the user actually changed, while non-touched fields
        # remain as defaults — so the game sees a complete struct.
        tmpl = _INFO_TEMPLATES.get(type_name, ([], {}))
        scalars, default_curves = tmpl
        info = FXInfoBlock(type=type_name, scalars=list(scalars))
        for field, default_val in default_curves.items():
            info.curves[field] = FXCurve(
                looped=0,
                keys=[FXKeyframe(time=0.0, val=float(default_val))],
            )
        em.infos.append(info)
        return info

    def _set_start_end(info, field, start_val, end_val):
        info.curves[field] = FXCurve(looped=0, keys=[
            FXKeyframe(time=0.0, val=float(start_val)),
            FXKeyframe(time=1.0, val=float(end_val)),
        ])

    def _set_single(info, field, value):
        info.curves[field] = FXCurve(looped=0, keys=[
            FXKeyframe(time=0.0, val=float(value)),
        ])

    # ── Base scalars ── #
    cur_tex = inu.particle_texture.strip()
    cur_tex_to_write = cur_tex if cur_tex else 'NULL'
    if cur_tex != fresh['texture']:
        _set_base('TEXTURE', cur_tex_to_write)
        applied += 1

    if int(inu.particle_src_blend) != fresh['src_blend']:
        _set_base('SRCBLENDID', int(inu.particle_src_blend))
        applied += 1
    if int(inu.particle_dst_blend) != fresh['dst_blend']:
        _set_base('DSTBLENDID', int(inu.particle_dst_blend))
        applied += 1

    # ── COLOUR curves ── #
    c0 = tuple(inu.particle_color_start)
    c1 = tuple(inu.particle_color_end)
    cm = tuple(inu.particle_color_mid)
    mid_enabled = bool(inu.particle_color_mid_enabled)
    mid_time = float(inu.particle_color_mid_time)
    fresh_mid_enabled = bool(fresh.get('color_mid_enabled', False))
    fresh_mid = tuple(fresh.get('color_mid', (1.0, 1.0, 1.0, 1.0)))
    fresh_mid_time = float(fresh.get('color_mid_time', 0.5))

    colour_changed_start = not _close_vec(c0, fresh['color_start'])
    colour_changed_end = not _close_vec(c1, fresh['color_end'])
    mid_mode_changed = mid_enabled != fresh_mid_enabled
    mid_value_changed = mid_enabled and (
        not _close_vec(cm, fresh_mid)
        or abs(mid_time - fresh_mid_time) >= eps
    )

    def _set_3key(info, field, v0, vm, v1, tm):
        info.curves[field] = FXCurve(looped=0, keys=[
            FXKeyframe(time=0.0, val=float(v0)),
            FXKeyframe(time=float(tm), val=float(vm)),
            FXKeyframe(time=1.0, val=float(v1)),
        ])

    if colour_changed_start or colour_changed_end or mid_mode_changed or mid_value_changed:
        colour = _get_or_create_info('COLOUR')
        # Rewrite channels that changed; if middle is enabled, always use
        # 3-key curves for those channels to preserve the middle keyframe.
        for idx, name in enumerate(('RED', 'GREEN', 'BLUE', 'ALPHA')):
            ch_a_changed = abs(c0[idx] - fresh['color_start'][idx]) >= eps
            ch_b_changed = abs(c1[idx] - fresh['color_end'][idx]) >= eps
            ch_m_changed = mid_enabled and abs(cm[idx] - fresh_mid[idx]) >= eps
            if ch_a_changed or ch_b_changed or ch_m_changed or mid_mode_changed:
                if mid_enabled:
                    _set_3key(colour, name,
                              c0[idx] * 255.0, cm[idx] * 255.0, c1[idx] * 255.0,
                              mid_time)
                else:
                    _set_start_end(colour, name, c0[idx] * 255.0, c1[idx] * 255.0)
                applied += 1

    # ── SIZE curves (SIZEX/SIZEY) ── #
    sz_start_changed = not _close_scalar(inu.particle_size_start, fresh['size_start'])
    sz_end_changed = not _close_scalar(inu.particle_size_end, fresh['size_end'])
    if sz_start_changed or sz_end_changed:
        size_info = _get_or_create_info('SIZE')
        _set_start_end(size_info, 'SIZEX', inu.particle_size_start, inu.particle_size_end)
        _set_start_end(size_info, 'SIZEY', inu.particle_size_start, inu.particle_size_end)
        applied += 1

    # ── Scalar emission curves ── #
    if not _close_scalar(inu.particle_life, fresh['life']):
        _set_single(_get_or_create_info('EMLIFE'), 'LIFE', inu.particle_life)
        applied += 1
    if not _close_scalar(inu.particle_rate, fresh['rate']):
        _set_single(_get_or_create_info('EMRATE'), 'RATE', inu.particle_rate)
        applied += 1
    if not _close_scalar(inu.particle_speed, fresh['speed']):
        _set_single(_get_or_create_info('EMSPEED'), 'SPEED', inu.particle_speed)
        applied += 1

    # ── EMDIR ── #
    dir_cur = tuple(inu.particle_direction)
    if not _close_vec(dir_cur, fresh['direction']):
        emdir = _get_or_create_info('EMDIR')
        if abs(dir_cur[0] - fresh['direction'][0]) >= eps:
            _set_single(emdir, 'DIRX', dir_cur[0])
            applied += 1
        if abs(dir_cur[1] - fresh['direction'][1]) >= eps:
            _set_single(emdir, 'DIRY', dir_cur[1])
            applied += 1
        if abs(dir_cur[2] - fresh['direction'][2]) >= eps:
            _set_single(emdir, 'DIRZ', dir_cur[2])
            applied += 1

    # ── Biases (EMLIFE BIAS, EMSPEED BIAS) ── #
    if not _close_scalar(inu.particle_life_bias, fresh['life_bias']):
        _set_single(_get_or_create_info('EMLIFE'), 'BIAS', inu.particle_life_bias)
        applied += 1
    if not _close_scalar(inu.particle_speed_bias, fresh['speed_bias']):
        _set_single(_get_or_create_info('EMSPEED'), 'BIAS', inu.particle_speed_bias)
        applied += 1

    # ── EMANGLE ── #
    if not _close_scalar(inu.particle_angle_min, fresh['angle_min']):
        _set_single(_get_or_create_info('EMANGLE'), 'MIN', inu.particle_angle_min)
        applied += 1
    if not _close_scalar(inu.particle_angle_max, fresh['angle_max']):
        _set_single(_get_or_create_info('EMANGLE'), 'MAX', inu.particle_angle_max)
        applied += 1

    # ── EMSIZE (Box as symmetric half-extent around emitter) ── #
    # UI stores `particle_volume` as half-extent; FXP needs pairs of
    # SIZEMIN=-v SIZEMAX=+v. Writing both sides keeps the parser happy.
    vol_cur = tuple(inu.particle_volume)
    if not _close_vec(vol_cur, fresh['volume']):
        emsize = _get_or_create_info('EMSIZE')
        for idx, (fld_min, fld_max) in enumerate(
            (('SIZEMINX', 'SIZEMAXX'),
             ('SIZEMINY', 'SIZEMAXY'),
             ('SIZEMINZ', 'SIZEMAXZ'))
        ):
            half = float(vol_cur[idx])
            _set_single(emsize, fld_min, -half)
            _set_single(emsize, fld_max, half)
            applied += 2

    # ── EMPOS ── #
    off_cur = tuple(inu.particle_offset)
    if not _close_vec(off_cur, fresh['offset']):
        empos = _get_or_create_info('EMPOS')
        for idx, fld in enumerate(('X', 'Y', 'Z')):
            if abs(off_cur[idx] - fresh['offset'][idx]) >= eps:
                _set_single(empos, fld, off_cur[idx])
                applied += 1

    # ── EMROTATION ── #
    if not _close_scalar(inu.particle_rotation_min, fresh['rotation_min']):
        _set_single(_get_or_create_info('EMROTATION'), 'ANGLEMIN', inu.particle_rotation_min)
        applied += 1
    if not _close_scalar(inu.particle_rotation_max, fresh['rotation_max']):
        _set_single(_get_or_create_info('EMROTATION'), 'ANGLEMAX', inu.particle_rotation_max)
        applied += 1

    # ── FORCE ── #
    force_cur = tuple(inu.particle_force)
    if not _close_vec(force_cur, fresh['force']):
        finfo = _get_or_create_info('FORCE')
        for idx, fld in enumerate(('FORCEX', 'FORCEY', 'FORCEZ')):
            if abs(force_cur[idx] - fresh['force'][idx]) >= eps:
                _set_single(finfo, fld, force_cur[idx])
                applied += 1

    # ── FRICTION / WIND / NOISE / JITTER ── #
    if not _close_scalar(inu.particle_friction, fresh['friction']):
        _set_single(_get_or_create_info('FRICTION'), 'FRICTION', inu.particle_friction)
        applied += 1
    if not _close_scalar(inu.particle_wind, fresh['wind']):
        _set_single(_get_or_create_info('WIND'), 'WINDFACTOR', inu.particle_wind)
        applied += 1
    if not _close_scalar(inu.particle_noise, fresh['noise']):
        _set_single(_get_or_create_info('NOISE'), 'NOISE', inu.particle_noise)
        applied += 1
    if not _close_scalar(inu.particle_jitter, fresh['jitter']):
        _set_single(_get_or_create_info('JITTER'), 'JITTERFACTOR', inu.particle_jitter)
        applied += 1

    # ── ROTSPEED ── #
    if not _close_scalar(inu.particle_rotspeed_min, fresh['rotspeed_min']):
        _set_single(_get_or_create_info('ROTSPEED'), 'MINCW', inu.particle_rotspeed_min)
        applied += 1
    if not _close_scalar(inu.particle_rotspeed_max, fresh['rotspeed_max']):
        _set_single(_get_or_create_info('ROTSPEED'), 'MAXCW', inu.particle_rotspeed_max)
        applied += 1

    # ── GROUNDCOLLIDE ── #
    if not _close_scalar(inu.particle_ground_bounce, fresh['ground_bounce']):
        _set_single(_get_or_create_info('GROUNDCOLLIDE'), 'BOUNCE', inu.particle_ground_bounce)
        applied += 1
    if not _close_scalar(inu.particle_ground_speedmult, fresh['ground_speedmult']):
        _set_single(_get_or_create_info('GROUNDCOLLIDE'), 'SPEEDMULT', inu.particle_ground_speedmult)
        applied += 1

    # Enforce canonical zone order — the native GTA SA parser ignores
    # info blocks that appear out of Emission→Physics→Rendering sequence.
    if applied > 0:
        _sort_infos_by_zone(em)

    # Strip stray TIMEMODEPRT from Zone 1 blocks (the native parser never
    # expects it there; its presence desyncs the field-order reader and
    # crashes the game). Zone 2/3 blocks always keep TIMEMODEPRT: 1.
    for info in em.infos:
        if _info_zone(info.type) == 1:
            if any(k == 'TIMEMODEPRT' for k, _ in info.scalars):
                info.scalars = [(k, v) for k, v in info.scalars if k != 'TIMEMODEPRT']
                applied += 1

    return applied


class GTATOOLS_OT_save_particle_effect(bpy.types.Operator):
    """Сохранить правки эффекта обратно в effects.fxp (с автобэкапом)"""
    bl_idname = "gtatools.save_particle_effect"
    bl_label = "INU: Save Particle Effect"
    bl_options = {'REGISTER'}

    effect_name: StringProperty(
        name="Effect Name",
        description=T("Имя системы в effects.fxp (можно новое — тогда клонируется из текущей)"),
        default="",
    )
    overwrite: BoolProperty(
        name="Overwrite existing",
        description=T("Перезаписать существующую систему с таким именем"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'EMPTY'
                and getattr(obj, 'inu', None)
                and obj.inu.type == '2DFX'
                and obj.inu.effect_2dfx == 'PARTICLE')

    def invoke(self, context, event):
        obj = context.active_object
        self.effect_name = obj.get('2dfx_effect_name', '') or ''
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'effect_name')
        layout.prop(self, 'overwrite')
        layout.label(text=T("При первой записи создастся effects.fxp.bak"), **inu_icon(safe_icon('INFO')))

    def execute(self, context):
        obj = context.active_object
        game_root = bpy.path.abspath(context.scene.inu_settings.gtatools_game_root or '')
        if not game_root:
            self.report({'ERROR'}, T("Game Root не задан"))
            return {'CANCELLED'}

        fxp_path = os.path.join(game_root, 'models', 'effects.fxp')
        if not os.path.isfile(fxp_path):
            self.report({'ERROR'}, f"{T('effects.fxp не найден: ')}{fxp_path}")
            return {'CANCELLED'}

        target_name = self.effect_name.strip()
        if not target_name:
            self.report({'ERROR'}, T("Имя эффекта пустое"))
            return {'CANCELLED'}

        # Read fresh (don't mutate cached object)
        from ..core import fxp as _fxp
        try:
            fxf = _fxp.read_fxp(fxp_path)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка парсинга effects.fxp: ')}{e}")
            return {'CANCELLED'}

        existing = fxf.find(target_name)

        if existing is None:
            # Clone current system under new name
            source_name = obj.get('2dfx_effect_name', '') or ''
            source = fxf.find(source_name)
            if source is None:
                self.report({'ERROR'}, T("Исходная система '") + source_name + T("' не найдена — нечего клонировать"))
                return {'CANCELLED'}
            import copy
            new_system = copy.deepcopy(source)
            renamed = False
            for i, (k, v) in enumerate(new_system.header):
                if k == 'NAME':
                    new_system.header[i] = (k, target_name)
                    renamed = True
                    break
            if not renamed:
                new_system.header.append(('NAME', target_name))
            fxf.systems.append(new_system)
            target_system = new_system
        else:
            if not self.overwrite:
                self.report({'ERROR'}, T("Система '") + target_name + T("' уже существует (снимите галку 'Overwrite' нельзя, включите её)"))
                return {'CANCELLED'}
            target_system = existing

        if not target_system.emitters:
            self.report({'ERROR'}, T("У системы '") + target_name + T("' нет эмиттеров"))
            return {'CANCELLED'}

        em_idx = max(0, min(int(obj.inu.particle_emitter_index), len(target_system.emitters) - 1))
        try:
            applied = _apply_particle_props_to_emitter(obj, target_system.emitters[em_idx])
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка применения правок: ')}{e}")
            return {'CANCELLED'}

        # System-level header fields (LENGTH/PLAYMODE/CULLDIST) — dirty check
        def _set_header(key, value):
            sv = str(value)
            for i, (k, _) in enumerate(target_system.header):
                if k == key:
                    target_system.header[i] = (k, sv)
                    return
            target_system.header.append((key, sv))

        def _header_float(key, default):
            try:
                return float(target_system.header_get(key) or default)
            except ValueError:
                return default

        def _header_int(key, default):
            try:
                return int(target_system.header_get(key) or default)
            except ValueError:
                return default

        inu = obj.inu
        if abs(float(inu.particle_sys_length) - _header_float('LENGTH', 1.0)) > 1e-4:
            _set_header('LENGTH', f"{float(inu.particle_sys_length):.3f}")
            applied += 1
        if int(inu.particle_sys_playmode) != _header_int('PLAYMODE', 2):
            _set_header('PLAYMODE', int(inu.particle_sys_playmode))
            applied += 1
        if abs(float(inu.particle_sys_culldist) - _header_float('CULLDIST', 50.0)) > 1e-4:
            _set_header('CULLDIST', f"{float(inu.particle_sys_culldist):.3f}")
            applied += 1

        # No-op early exit: if we didn't clone a new system and no fields
        # changed, don't touch the file (and don't create a pointless backup).
        is_clone = existing is None
        if not is_clone and applied == 0:
            self.report({'INFO'}, T("Нет изменений — файл не тронут"))
            return {'FINISHED'}

        # Auto-backup on first actual write
        backup_path = fxp_path + '.bak'
        if not os.path.isfile(backup_path):
            import shutil
            try:
                shutil.copy2(fxp_path, backup_path)
                print(f"[FXP] backed up to {backup_path}")
            except Exception as e:
                self.report({'ERROR'}, f"{T('Не удалось создать бэкап: ')}{e}")
                return {'CANCELLED'}

        try:
            _fxp.write_fxp(fxp_path, fxf)
        except Exception as e:
            self.report({'ERROR'}, f"{T('Ошибка записи: ')}{e}")
            return {'CANCELLED'}
        _audit_fxp(self, fxp_path, fxf)

        _fxp.clear_cache()

        if obj.get('2dfx_effect_name') != target_name:
            obj['2dfx_effect_name'] = target_name

        msg = f"Клон '{target_name}' сохранён" if is_clone else f"'{target_name}': применено полей — {applied}"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_attach_2dfx(bpy.types.Operator):
    """Привязать 2DFX к модели (сделать дочерним)"""
    bl_idname = "gtatools.attach_2dfx"
    bl_label = "INU: Attach to Model"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'EMPTY'
                and getattr(obj, 'inu', None)
                and obj.inu.type == '2DFX')

    def execute(self, context):
        # Attach EVERY selected 2DFX empty to the one selected mesh — not just
        # the active one, so a whole batch of lights parents in a single click.
        mesh_obj = next((o for o in context.selected_objects
                         if o.type == 'MESH'), None)
        if not mesh_obj:
            self.report({'WARNING'}, T("Выдели меш вместе с 2DFX"))
            return {'CANCELLED'}
        fx_objs = [o for o in context.selected_objects
                   if o.type == 'EMPTY' and getattr(o, 'inu', None)
                   and o.inu.type == '2DFX']
        if not fx_objs:
            self.report({'WARNING'}, T("Нет выделенных 2DFX"))
            return {'CANCELLED'}
        # Keep world position when parenting (same inverse for every child of
        # this mesh).
        inv = mesh_obj.matrix_world.inverted()
        for fx_obj in fx_objs:
            fx_obj.parent = mesh_obj
            fx_obj.matrix_parent_inverse = inv.copy()
        self.report({'INFO'},
                    T("Привязано 2DFX: {0} → '{1}'").format(
                        len(fx_objs), mesh_obj.name))
        return {'FINISHED'}


class GTATOOLS_OT_detach_2dfx(bpy.types.Operator):
    """Отвязать 2DFX от родительской модели"""
    bl_idname = "gtatools.detach_2dfx"
    bl_label = "INU: Detach from Model"
    bl_options = {'REGISTER', 'UNDO'}

    fx_name: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        # Если указано имя — отвязываем конкретный объект
        if self.fx_name:
            fx_obj = bpy.data.objects.get(self.fx_name)
        else:
            fx_obj = context.active_object

        if not fx_obj or not fx_obj.parent:
            self.report({'WARNING'}, "Nothing to detach")
            return {'CANCELLED'}

        parent_name = fx_obj.parent.name
        world_matrix = fx_obj.matrix_world.copy()
        fx_obj.parent = None
        fx_obj.matrix_world = world_matrix
        self.report({'INFO'}, f"'{fx_obj.name}' detached from '{parent_name}'")
        return {'FINISHED'}


class GTATOOLS_OT_detach_all_2dfx(bpy.types.Operator):
    """Отвязать все 2DFX/частицы от выделенного меша"""
    bl_idname = "gtatools.detach_all_2dfx"
    bl_label = "INU: Detach All from Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH'

    def execute(self, context):
        mesh_obj = context.active_object
        # Собрать всех дочерних 2DFX
        children = [c for c in bpy.data.objects
                    if c.parent == mesh_obj and c.type == 'EMPTY'
                    and getattr(c, 'inu', None) and c.inu.type == '2DFX']

        if not children:
            self.report({'WARNING'}, "No attached 2DFX found")
            return {'CANCELLED'}

        for fx in children:
            world_matrix = fx.matrix_world.copy()
            fx.parent = None
            fx.matrix_world = world_matrix

        self.report({'INFO'}, f"{len(children)} 2DFX detached from '{mesh_obj.name}'")
        return {'FINISHED'}


# ── 2DFX Light flag bit-toggle ────────────────────────────────
# Light2dfx.flags1 / flags2 are u8 bit-fields (8 boolean flags each
# packed into one byte). Blender ID-properties don't natively render
# as per-bit checkboxes, so we expose each bit through a tiny operator
# that XORs the corresponding bit on the active object's ID-prop.
# The panel draws 8 buttons per byte with depress=current-bit-state,
# giving the user named-flag toggles instead of a raw 0–255 spinner.

# Per-bit human descriptions for the 2DFX Light flag bytes. Lives
# here so the operator's `description` classmethod can look them up —
# Blender queries that classmethod per-button on hover, so it's the
# only way to attach distinct tooltips to bit-toggle buttons that all
# share one operator id.
_2DFX_BIT_TOOLTIPS = {
    ('2dfx_flags1', 0): "Check Obstacles — корона прячется за препятствиями (raycast от камеры). Реалистично, но дороже",
    ('2dfx_flags1', 1): "Fog Type 1 — бит 1 типа тумана (комбинируется с битом 2: 00=без, 01=type1, 10=type2, 11=type3)",
    ('2dfx_flags1', 2): "Fog Type 2 — бит 2 типа тумана (см. Fog Type 1)",
    ('2dfx_flags1', 3): "Without Corona — выключает корону, остаётся только point light. Полезно для невидимых источников",
    ('2dfx_flags1', 4): "Corona Reflects — корона отражается от кузова машин (как фары)",
    ('2dfx_flags1', 5): "AT_DAY — источник виден днём (06:00–20:00)",
    ('2dfx_flags1', 6): "AT_NIGHT — источник виден ночью (20:00–06:00)",
    ('2dfx_flags1', 7): "Blinking 1 — источник мигает (паттерн 1)",
    ('2dfx_flags2', 0): "Blink 1 — мерцает паттерном 1 (короткие вспышки)",
    ('2dfx_flags2', 1): "Blink 2 — мерцает паттерном 2 (равномерное)",
    ('2dfx_flags2', 2): "Blink 3 — мерцает паттерном 3 (длинные вспышки)",
    ('2dfx_flags2', 3): "Traffic Light — светофор (цвет управляется игровым скриптом)",
    ('2dfx_flags2', 4): "Train Crossing — мигает как ЖД-переезд",
    ('2dfx_flags2', 5): "Update Height — пересчитывает высоту над землёй каждый кадр (для движущихся источников)",
    ('2dfx_flags2', 6): "Check Direction — учитывает направление взгляда камеры (Look Vector)",
    ('2dfx_flags2', 7): "Police Light — полицейская мигалка (чередующиеся красный/синий)",
}


class GTATOOLS_OT_toggle_2dfx_flag_bit(bpy.types.Operator):
    """Переключить один бит в 2dfx_flags1 / 2dfx_flags2 на активном объекте."""
    bl_idname = "gtatools.toggle_2dfx_flag_bit"
    bl_label = "INU: Toggle 2DFX Flag Bit"
    bl_options = {'REGISTER', 'UNDO'}

    prop_name: StringProperty(default="2dfx_flags1")
    bit: IntProperty(default=0, min=0, max=7)

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    @classmethod
    def description(cls, context, properties):
        return _2DFX_BIT_TOOLTIPS.get(
            (properties.prop_name, properties.bit),
            "Toggle 2DFX flag bit"
        )

    def execute(self, context):
        obj = context.active_object
        cur = int(obj.get(self.prop_name, 0))
        mask = 1 << self.bit
        obj[self.prop_name] = (cur ^ mask) & 0xFF
        return {'FINISHED'}


