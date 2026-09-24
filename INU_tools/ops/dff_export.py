# INU_tools.ops.dff_export
# Blender mesh objects → DFF file.
# Uses INU_tools.core.dff for binary format writing.

import os
import bpy
import bmesh
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper

from ..core.dff import (
    DffClump, DffFrame, DffGeometry, DffAtomic, DffLight,
    DffMaterial, DffTexture, SurfaceProperties,
    Triangle, BoundingSphere, TexCoords, RGBA,
    ExtraVertColors, SkinData, HAnimData, HAnimBone,
    BumpMapEffect, EnvMapEffect, DualTextureEffect, SpecularMaterial, ReflectionMaterial,
    UserData, UserDataSection,
    USERDATA_INT, USERDATA_FLOAT, USERDATA_STRING,
    Extension2dfx, Light2dfx, Particle2dfx, PedAttractor2dfx, SunGlare2dfx,
    EnterExit2dfx, RoadSign2dfx, Escalator2dfx, RawUnknown2dfx,
    UVAnim, UVAnimDict, UVAnimKeyframe,
    BreakableData,
    GTA_SA_VERSION, write_dff_file,
)
from ..core import game_versions
from ..tools.model_utils import is_collision_mesh


# ── Helpers ──────────────────────────────────────────────────────

def _resolve_export_version(context=None) -> int:
    """Pick the RW version for DFF export based on the scene's active
    game (gtatools_game). Falls back to GTA_SA_VERSION when context
    is None / scene has no inu_settings (e.g. unit-test paths).

    Centralised here so every DFF-write call-site uses the same logic
    — operators, IMG-export, INU Export, animated-map-object, etc.
    """
    if context is None:
        try:
            import bpy as _bpy
            context = _bpy.context
        except Exception:
            return GTA_SA_VERSION
    scene = getattr(context, 'scene', None)
    if scene is None:
        return GTA_SA_VERSION
    game = game_versions.game_of_scene(scene)
    return game_versions.rw_version_for_game(game)

def _load_user_data(target) -> UserData:
    """Load UserData from Blender custom property 'inu_user_data'.

    Returns UserData or None if not present.
    """
    raw = target.get('inu_user_data')
    if not raw:
        return None

    type_map = {'int': USERDATA_INT, 'float': USERDATA_FLOAT, 'str': USERDATA_STRING}
    ud = UserData()
    # IDProperty arrays come back as IDPropertyArray or list
    sections = list(raw) if hasattr(raw, '__iter__') else []
    for sec_raw in sections:
        sec = UserDataSection()
        sec.name = sec_raw.get('name', '')
        sec.data_type = type_map.get(sec_raw.get('type', 'na'), 0)
        data_raw = sec_raw.get('data', [])
        sec.data = list(data_raw)
        ud.sections.append(sec)

    return ud if ud.sections else None


def _strip_ext(name: str) -> str:
    """Game texture name: image extension and everything after it, plus a bare
    Blender .001 suffix, removed ('tex.png.001' → 'tex'). Same rule as the TXD
    exporter, so the DFF and TXD names always match."""
    from ..core.tex_name import clean_texture_name
    return clean_texture_name(name)


def _color_to_rgba(c, alpha=1.0) -> RGBA:
    """Convert Blender float color (0-1) to RGBA (0-255)."""
    return RGBA(
        max(0, min(255, int(c[0] * 255))),
        max(0, min(255, int(c[1] * 255))),
        max(0, min(255, int(c[2] * 255))),
        max(0, min(255, int(alpha * 255))),
    )


# ── Material reading ─────────────────────────────────────────────

def _get_principled(mat):
    """Find Principled BSDF node in material."""
    if not mat or not mat.use_nodes:
        return None
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node
    return None


# diffuse_color нового материала в Blender — эталон для материалов без
# импорт-штампа (созданных вручную): пока свотч равен ему, панель не трогали.
_BL_DEFAULT_DIFFUSE = (0.8, 0.8, 0.8, 1.0)


def _panel_color_override(mat):
    """RGBA из свотча «Цвет (RGBA)» панели (mat.diffuse_color), если его
    правил пользователь; иначе None.

    Панель редактирует diffuse_color, а не Base Color ноды, поэтому раньше
    ручной цвет/альфа «сбрасывались» при экспорте: _read_base_color читал
    только Principled. Слот цвета машины при этом работал — он пишет в оба
    места. Как с texture_name: свотч считается override'ом, только если он
    отличается от значения, записанного импортом (inu_dff_color), — иначе
    те, кто по привычке правит цвет в шейдере, ничего не потеряют.
    """
    dc = getattr(mat, 'diffuse_color', None)
    if dc is None:
        return None
    dc = tuple(dc)
    stamp = mat.get('inu_dff_color')
    try:
        ref = tuple(stamp) if stamp is not None and len(stamp) == 4 else None
    except TypeError:
        ref = None
    if ref is None:
        if mat.get('dff_texture_name') is not None:
            # Импорт старой версией — штампа цвета ещё не было. Оригинал
            # неизвестен, а diffuse_color = цвет DFF ≠ 0.8-серому: сочли бы
            # правкой и перебили бы цвет, выставленный в шейдере. Старое
            # поведение (Principled) до реимпорта.
            return None
        ref = _BL_DEFAULT_DIFFUSE
    # Полшага 8-битной шкалы: float32-шум не считается правкой.
    if all(abs(a - b) < 0.5 / 255.0 for a, b in zip(dc, ref)):
        return None
    return RGBA(*(max(0, min(255, int(round(v * 255)))) for v in dc))


def _read_base_color(mat) -> RGBA:
    """Read base color from Principled BSDF or fallback."""
    override = _panel_color_override(mat)
    if override is not None:
        return override
    principled = _get_principled(mat)
    if principled:
        bc = principled.inputs.get('Base Color')
        if bc:
            # Alpha берём из входа Alpha Principled BSDF (не зависит от цвета).
            alpha_input = principled.inputs.get('Alpha')

            # Base Color ПОДКЛЮЧЁН (текстура/ноды) → цвет материала в DFF должен
            # быть нейтральным БЕЛЫМ. У подключённого сокета default_value —
            # это остаточное значение из UI (по умолчанию 0.8,0.8,0.8 → 204), а
            # НЕ реальный цвет: с флагом MODULATE игра/Ariane умножают текстуру
            # на цвет материала (204/255 ≈ 0.8) → текстура темнеет на ~20%.
            # Поэтому default_value используем ТОЛЬКО для несвязанного сокета
            # (солид-цвет без текстуры).
            if getattr(bc, 'is_linked', False):
                alpha = (int(alpha_input.default_value * 255)
                         if alpha_input else 255)
                return RGBA(255, 255, 255, alpha)

            c = bc.default_value
            # Режим timecyc «игровой вид» уводит цвет в Emission и ОБНУЛЯЕТ
            # Base Color в чёрный. Читать его в этом состоянии нельзя: цвет
            # материала уйдёт в DFF как 0, и с флагом MODULATE игра считает
            # prelit × 0 = 0 → чёрная модель. Восстанавливаем исходный цвет:
            #   1) сохранённый game-look'ом inu_tc_prev_base;
            #   2) mat.diffuse_color — солид-цвет, его ставит импорт из цвета
            #      материала DFF, и ни превью, ни game-look, ни заливка его не
            #      трогают (страхует старые .blend, где режим уже выключали и
            #      флаг снят, а чёрный Base Color остался).
            # Работает при ЛЮБОМ пути экспорта, даже если превью не отключалось.
            _prev = mat.get('inu_tc_prev_base')
            if _prev is not None and mat.get('inu_tc_game_look'):
                c = tuple(_prev)
            elif tuple(c)[:3] == (0.0, 0.0, 0.0) and hasattr(mat, 'diffuse_color'):
                _dc = mat.diffuse_color
                if tuple(_dc)[:3] != (0.0, 0.0, 0.0):
                    c = (_dc[0], _dc[1], _dc[2], c[3])
            alpha = int(alpha_input.default_value * 255) if alpha_input else int(c[3] * 255)
            return RGBA(int(c[0]*255), int(c[1]*255), int(c[2]*255), alpha)
    if hasattr(mat, 'diffuse_color'):
        c = mat.diffuse_color
        return RGBA(int(c[0]*255), int(c[1]*255), int(c[2]*255), 255)
    return RGBA()


def _read_texture(mat) -> DffTexture:
    """Read texture name from Principled BSDF image node.

    Walks through preview nodes (Prelight_Mix, LM_Mix) to find the real texture.
    Falls back to IDProp `dff_texture_name` set at import time — это страхует
    от кейса, когда TXD не был загружен и image=None на Texture-ноде, но имя
    текстуры всё равно известно из DFF.
    """
    # Explicit GTA texture name from INU props overrides the node — BUT only
    # when the user actually changed it. At import we auto-fill inu.texture_name
    # with the DFF's name; if we always honoured it, swapping the image node
    # (e.g. replacing the stock "vehiclelights128" with a custom texture) would
    # be IGNORED and the original name re-exported. So treat it as an override
    # only when it differs from the value stashed at import (dff_texture_name);
    # otherwise fall through and let the image node drive the name, like
    # DragonFF. A material with no import stamp (dff_texture_name unset) still
    # honours a hand-typed name.
    _inu = getattr(mat, 'inu', None)
    _inu_name = (getattr(_inu, 'texture_name', '') or '').strip() if _inu else ''
    if _inu_name:
        _dff_stamp = (mat.get('dff_texture_name') or '').strip()
        if _strip_ext(_inu_name) != _strip_ext(_dff_stamp):
            _flt, _msk = _tex_filters_and_mask(mat)
            return DffTexture(name=_strip_ext(_inu_name),
                              mask=_msk, filters=_flt)

    # Как в DragonFF: имя текстуры берём из НОДЫ (её label), а НЕ из имени
    # картинки. Так пользователь задаёт имя текстуры в DFF через ноду, и
    # .001-суффиксы Blender / расширения файла не попадают в файл. Нода
    # авторитетнее: сначала её label, иначе имя картинки. IDProp
    # `dff_texture_name` (сохранённый при импорте) — только запасной вариант,
    # когда ноды/картинки нет (TXD не был загружен).
    principled = _get_principled(mat)
    if principled:
        bc_input = principled.inputs.get('Base Color')
        if bc_input and bc_input.is_linked:
            source_node = bc_input.links[0].from_node

            # Walk through preview mix nodes (Prelight_Mix, LM_Mix) to the
            # real texture — wrappers keep it on input 'A' / 'Color1'.
            max_depth = 5
            while (source_node and source_node.name in
                   ("Prelight_Mix", "LM_Mix", "Lightmap_Mix") and max_depth > 0):
                max_depth -= 1
                a_input = (source_node.inputs.get('A')
                           or source_node.inputs.get('Color1'))
                if not a_input or not a_input.is_linked:
                    source_node = None
                    break
                source_node = a_input.links[0].from_node

            # Skip lightmap texture nodes if they ended up here
            if source_node and source_node.name in ("LM_Texture",
                                                     "Lightmap_Texture"):
                source_node = None

            if source_node and source_node.type == 'TEX_IMAGE':
                # Точно как в DragonFF: берём label ноды, если он непустой И
                # является подстрокой имени картинки (т.е. «чистое» имя без
                # .001/расширения); иначе — имя картинки. Без картинки —
                # просто label.
                node_label = (source_node.label or "").strip()
                image_name = (source_node.image.name
                              if source_node.image else "")
                if node_label and node_label in image_name:
                    name = node_label
                elif image_name:
                    name = image_name
                else:
                    name = node_label
                name = _strip_ext(name)
                if name:
                    _flt, _msk = _tex_filters_and_mask(mat)
                    return DffTexture(name=name, mask=_msk, filters=_flt)

    # Запасной вариант: имя, сохранённое при импорте DFF
    dff_tex_name = mat.get('dff_texture_name')
    if dff_tex_name:
        _flt, _msk = _tex_filters_and_mask(mat)
        return DffTexture(name=_strip_ext(dff_tex_name), mask=_msk, filters=_flt)
    return None


def _tex_filters_and_mask(mat):
    """RW filterAddressing word + mask string from INU material props.

    Rebuilds the 32-bit word: filter mode | addrU<<8 | addrV<<12 | hi<<16, so
    the texture's filtering/addressing round-trips instead of falling back to a
    hard-coded default (which silently dropped the high bit on every export)."""
    inu = getattr(mat, 'inu', None)
    if not inu:
        return 0x11106, ""
    try:
        filt = (int(inu.tex_filter)
                | (int(inu.tex_addr_u) << 8)
                | (int(inu.tex_addr_v) << 12)
                | (int(inu.tex_filter_hi) << 16))
    except (ValueError, AttributeError):
        filt = 0x11106
    return filt, _strip_ext(getattr(inu, 'mask_texture', '') or "")


def _read_surface(mat) -> SurfaceProperties:
    """Read RW surface lighting coefficients (ambient, specular, diffuse).

    These are stored verbatim from the DFF on import — NOT derived from Blender
    shader inputs. The old code read diffuse from 'Roughness' (default 0.5) and
    specular from 'Specular' (default 0.0), which halved every material's
    brightness on round-trip (the "slightly darker after export" bug). Vanilla
    GTA uses specular=1.0, diffuse=1.0; our props default to 1.0 so materials
    authored from scratch in Blender also export at full brightness."""
    props = SurfaceProperties()
    inu = getattr(mat, 'inu', None)
    if inu:
        props.ambient = getattr(inu, 'ambient', 1.0)
        props.specular = getattr(inu, 'surf_specular', 1.0)
        props.diffuse = getattr(inu, 'surf_diffuse', 1.0)
    return props


def _read_material_plugins(mat) -> dict:
    """Read material effect plugins from INU properties."""
    plugins = {}
    inu = getattr(mat, 'inu', None)
    if not inu:
        return plugins

    # Bump map
    if getattr(inu, 'export_bump_map', False):
        bump = BumpMapEffect()
        bump_tex_name = getattr(inu, 'bump_map_tex', '')
        if bump_tex_name:
            bump.bump_texture = DffTexture(name=_strip_ext(bump_tex_name))
        plugins['bump_map'] = bump

    # Environment map
    if getattr(inu, 'export_env_map', False):
        env = EnvMapEffect()
        env.coefficient = getattr(inu, 'env_map_coef', 0.5)
        env.use_fb_alpha = getattr(inu, 'env_map_fb_alpha', False)
        tex_name = getattr(inu, 'env_map_tex', '')
        if tex_name:
            env.texture = DffTexture(name=_strip_ext(tex_name))
        plugins['env_map'] = env

    # Specular
    if getattr(inu, 'export_specular', False):
        spec = SpecularMaterial()
        spec.level = getattr(inu, 'specular_level', 1.0)
        spec.name = _strip_ext(getattr(inu, 'specular_texture', '') or '')
        plugins['specular'] = spec

    # Reflection
    if getattr(inu, 'export_reflection', False):
        refl = ReflectionMaterial()
        refl.scale_x = getattr(inu, 'reflection_scale_x', 0.0)
        refl.scale_y = getattr(inu, 'reflection_scale_y', 0.0)
        refl.offset_x = getattr(inu, 'reflection_offset_x', 0.0)
        refl.offset_y = getattr(inu, 'reflection_offset_y', 0.0)
        refl.intensity = getattr(inu, 'reflection_intensity', 0.0)
        plugins['reflection'] = refl

    # Dual Texture / Blend Mode
    if getattr(inu, 'export_dual_tex', False):
        dt = DualTextureEffect()
        dt.src_blend = int(getattr(inu, 'dual_tex_src_blend', '5'))
        dt.dst_blend = int(getattr(inu, 'dual_tex_dst_blend', '6'))
        tex_name = getattr(inu, 'dual_tex_texture', '')
        if tex_name:
            dt.texture = DffTexture(name=_strip_ext(tex_name))
        plugins['dual_texture'] = dt

    return plugins


def _build_material(mat) -> DffMaterial:
    """Convert a Blender material to DffMaterial."""
    dff_mat = DffMaterial()
    if mat is None:
        return dff_mat

    dff_mat.color = _read_base_color(mat)
    dff_mat.surface = _read_surface(mat)
    dff_mat.texture = _read_texture(mat)

    plugins = _read_material_plugins(mat)
    dff_mat.bump_map = plugins.get('bump_map')
    dff_mat.env_map = plugins.get('env_map')
    dff_mat.dual_texture = plugins.get('dual_texture')
    dff_mat.specular = plugins.get('specular')
    dff_mat.reflection = plugins.get('reflection')
    dff_mat.user_data = _load_user_data(mat)

    inu = getattr(mat, 'inu', None)
    if inu and getattr(inu, 'uv_anim_write', False):
        anim_name = (getattr(inu, 'animation_name', '') or mat.name)[:31]
        dff_mat.uv_anim_names = [anim_name]

    return dff_mat


def _collect_uv_anim_dict(materials) -> "UVAnimDict | None":
    """Scan Blender materials used in this clump and build a UVAnimDict
    containing one UVAnim per material that has `uv_anim_write` set.
    """
    anims = []
    seen = set()
    for mat in materials:
        if mat is None:
            continue
        inu = getattr(mat, 'inu', None)
        if not inu or not getattr(inu, 'uv_anim_write', False):
            continue
        anim_name = (getattr(inu, 'animation_name', '') or mat.name)[:31]
        if anim_name in seen:
            continue
        seen.add(anim_name)

        # Режим «Ключевые кадры»: читаем ключи ноды Mapping (Location/Scale)
        # и пишем их как кадры UVAnim. Если ключей нет — откат к прокрутке.
        mode = getattr(inu, 'uv_anim_mode', 'SCROLL')
        if mode == 'KEYFRAME':
            try:
                from ..tools import uv_anim_preview
                fps = float(bpy.context.scene.render.fps)
                res = uv_anim_preview.read_keyframes(mat, fps)
            except Exception as exc:
                import traceback
                print(f"[INU] UV anim read_keyframes failed for "
                      f"'{anim_name}': {exc}")
                traceback.print_exc()
                res = None
            if res and res[0]:
                print(f"[INU] UV anim '{anim_name}': прочитано "
                      f"{len(res[0])} ключей (keyframe mode)")
            else:
                print(f"[INU] UV anim '{anim_name}': ключей не найдено — "
                      f"откат к прокрутке (Speed U/V)")
            if res and res[0]:
                raw_kfs, duration = res
                duration = max(0.01, float(duration))
                kfs = [UVAnimKeyframe(time=t, scale_u=su, scale_v=sv,
                                      trans_u=tu, trans_v=tv)
                       for (t, su, sv, tu, tv) in raw_kfs]
                anims.append(UVAnim(name=anim_name, type_id=0x1C1,
                                    duration=duration, keyframes=kfs))
                continue
            # нет ключей → падаем в режим прокрутки ниже

        duration = max(0.01, float(getattr(inu, 'uv_anim_duration', 1.0)))
        su = float(getattr(inu, 'uv_anim_speed_u', 0.0))
        sv = float(getattr(inu, 'uv_anim_speed_v', 0.0))
        kf0 = UVAnimKeyframe(time=0.0, scale_u=1.0, scale_v=1.0,
                             trans_u=0.0, trans_v=0.0)
        kf1 = UVAnimKeyframe(time=duration, scale_u=1.0, scale_v=1.0,
                             trans_u=su * duration, trans_v=sv * duration)
        anims.append(UVAnim(
            name=anim_name, type_id=0x1C1,
            duration=duration, keyframes=[kf0, kf1],
        ))
    if not anims:
        return None
    return UVAnimDict(anims=anims)


# ── Export flags from DragonFF properties ────────────────────────

def _get_obj_export_flags(obj) -> dict:
    """Read export settings from obj.inu properties."""
    defaults = {
        'export_normals': True,
        'export_binsplit': True,
        'uv_map1': True,
        'uv_map2': True,
        'day_cols': True,
        'night_cols': True,
        'light': True,
        'modulate_color': True,
        'set_material_alpha': True,
        'light_beam_asi': False,
        'pipeline': 0,
    }
    inu = getattr(obj, 'inu', None)
    if not inu:
        return defaults

    result = {}
    # Detect scene-level «Ped» preset — applies ped-friendly overrides
    # on top of per-object DFF flags so the user can hit one button
    # and get a skinned character export without manually toggling
    # day_cols/night_cols/matfx off.
    import bpy as _bpy
    _scene_pipe = getattr(_bpy.context.scene, 'gtatools_export_pipeline', 'NONE')
    _is_ped_preset = (_scene_pipe == 'PED')
    # Ped-preset overrides for DFF flags. None = no override (keep
    # per-object value). False = force off, True = force on.
    # Must mirror the forbidden set used by the UI hint highlighter
    # (panels.py:_PIPE_FORBIDDEN['PED']).
    _PED_OVERRIDES = {
        # Core ped structure
        'has_skin':          True,    # SkinPLG обязателен
        'geom_native':       False,   # peds морфятся runtime, NOT native
        'matfx':             False,   # skinned не поддерживает reflection/spec
        'export_normals':    True,    # для in-game lighting/shading
        'export_binsplit':   True,    # vanilla peds имеют Bin Mesh PLG
        # Не нужны на ped'е (это map-object features):
        'day_cols':          False,
        'night_cols':        False,
        'modulate_color':    False,
        'set_material_alpha': False,
        'uv_map2':           False,   # ped только UV1
        'light_beam_asi':    False,   # SA_Light.asi — для зданий
    } if _is_ped_preset else {}

    for key, default in defaults.items():
        if key == 'pipeline':
            pipe_val = getattr(inu, 'pipeline', 'NONE')
            # If per-object pipeline is NONE, use scene-level setting
            if pipe_val == 'NONE' or pipe_val == '0':
                if _scene_pipe in ('NONE', 'PED'):
                    # Ped has no RenderWare pipeline ID — peds use the
                    # default RW pipeline (0); the «PED» enum value is
                    # only a preset trigger for the flag overrides above.
                    result['pipeline'] = 0
                else:
                    try:
                        result['pipeline'] = int(_scene_pipe, 0)
                    except ValueError:
                        result['pipeline'] = 0
            elif pipe_val == 'CUSTOM':
                custom = getattr(inu, 'custom_pipeline', '0')
                try:
                    result['pipeline'] = int(custom, 0)
                except ValueError:
                    result['pipeline'] = 0
            else:
                try:
                    result['pipeline'] = int(pipe_val, 0)
                except ValueError:
                    result['pipeline'] = 0
        else:
            # Ped-preset override wins over per-object inu.* defaults.
            if key in _PED_OVERRIDES:
                result[key] = _PED_OVERRIDES[key]
            else:
                result[key] = getattr(inu, key, default)

    return result


# ── Mesh processing ──────────────────────────────────────────────

def _needs_split(bm, vert, uv_layers, color_layers, nrm_layer=None):
    """
    Check if a vertex needs to be split because its loops
    have different UV, color, or NORMAL values.
    Returns list of loop groups that need separate vertices.

    Splitting by normal is what restores a GTA car's hard edges: the DFF
    stores one normal per vertex, so two faces meeting at a crease (same
    position, different normal) must each get their own output vertex —
    otherwise the crease collapses to one averaged normal (shading blotch).
    """
    loops = list(vert.link_loops)
    if len(loops) <= 1:
        return None

    groups = []
    used = [False] * len(loops)

    for i, loop_a in enumerate(loops):
        if used[i]:
            continue
        group = [loop_a]
        used[i] = True

        for j in range(i + 1, len(loops)):
            if used[j]:
                continue
            loop_b = loops[j]
            same = True

            for uv_layer in uv_layers:
                if loop_a[uv_layer].uv != loop_b[uv_layer].uv:
                    same = False
                    break

            if same:
                for cl in color_layers:
                    if loop_a[cl] != loop_b[cl]:
                        same = False
                        break

            if same and nrm_layer is not None:
                # dot < ~0.9997 ≈ >1.4° apart → distinct normal → separate vert.
                # Skip when either normal is ~zero: _loop_n hands both the SAME
                # geometric fallback, so splitting there only makes duplicate
                # verts (identical pos/uv/color/normal) — pure bloat.
                na = loop_a[nrm_layer]
                nb = loop_b[nrm_layer]
                if (na.length_squared > 1e-12 and nb.length_squared > 1e-12
                        and na.dot(nb) < 0.9997):
                    same = False

            if same:
                group.append(loop_b)
                used[j] = True

        groups.append(group)

    if len(groups) <= 1:
        return None
    return groups


def _classify_skin(obj, arm_obj):
    """Identify whether ``obj`` is rigidly attached to a single armature
    bone (animated map object pattern) or truly multi-bone skinned (ped).

    Returns the bone INDEX when rigid (or 0 = root when there are no
    weights at all but an armature is still present), or ``None`` when
    the mesh is truly skinned across multiple bones.

    Used by build_dff_clump to decide:
      * rigid → atomic.frame_index = that bone's frame, skip SkinPLG
      * real  → atomic.frame_index = mesh's own frame, emit SkinPLG
    """
    if arm_obj is None or not obj.vertex_groups:
        # No armature data — caller treats as "no skin info available",
        # which downstream handles as rigid attach to root.
        return 0 if (arm_obj and arm_obj.data.bones) else None
    bone_list = list(arm_obj.data.bones)
    if not bone_list:
        return None
    bone_name_to_idx = {b.name: i for i, b in enumerate(bone_list)}
    unique_bones = set()
    for v in obj.data.vertices:
        for g in v.groups:
            vg = obj.vertex_groups[g.group]
            if vg.name in bone_name_to_idx and g.weight > 0.0001:
                unique_bones.add(bone_name_to_idx[vg.name])
        if len(unique_bones) > 1:
            return None    # truly skinned
    if len(unique_bones) == 1:
        return next(iter(unique_bones))
    # No real weights → still rigid, default to root bone.
    return 0


def overlay_face_key(verts, a, b, c) -> str:
    """Stable position key for an overlay face (sorted, rounded to 0.1 mm).

    MUST produce the exact same string as ``dff_import.overlay_face_key`` — the
    importer records overlay faces by this key and the exporter matches base
    triangles against it to re-add the reflection layer on shared verts."""
    pts = sorted(
        (round(verts[v][0], 4), round(verts[v][1], 4), round(verts[v][2], 4))
        for v in (a, b, c))
    return "|".join("%.4f,%.4f,%.4f" % p for p in pts)


def _process_mesh(obj, clump: DffClump, frame_index: int, *,
                  force_no_skin: bool = False):
    """
    Convert a Blender mesh object into DffGeometry + DffAtomic.

    ``force_no_skin`` skips the SkinPLG emission path even when the
    mesh has an armature modifier — used by the animated-map-object
    flow where mesh is rigidly attached to one bone (atomic links
    directly to that bone's frame; no per-vertex skin data).
    """
    import mathutils

    flags = _get_obj_export_flags(obj)

    # Convert FLOAT_COLOR attributes to BYTE_COLOR before export (Itera Tools compatibility).
    # На 2.80-3.1 mesh.vertex_colors всегда BYTE_COLOR — конверсия не нужна, цикл no-op.
    import bpy
    import numpy as np
    from ..tools.compat import (HAS_COLOR_ATTRIBUTES, vcol_list, vcol_remove,
                                 vcol_new, vcol_get, vcol_data_type)
    orig_mesh = obj.data
    if HAS_COLOR_ATTRIBUTES:
        for ca in vcol_list(orig_mesh):
            if vcol_data_type(ca) in ('FLOAT_COLOR', 'COLOR'):
                name = ca.name
                domain = getattr(ca, 'domain', 'CORNER')
                n = len(ca.data)
                # Bulk read float colors → bulk write byte colors. Поэлементный
                # доступ через .data[i] медленный (RNA per-call), foreach_*
                # для тысяч loops/vertices даёт ×50-100 ускорение.
                flat = np.empty(n * 4, dtype=np.float32)
                ca.data.foreach_get('color', flat)
                vcol_remove(orig_mesh, ca)
                new_attr = vcol_new(orig_mesh, name, domain=domain)
                new_attr.data.foreach_set('color', flat)

    # Get evaluated mesh with modifiers applied (disable ARMATURE first)
    arm_mods = []
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.show_viewport:
            mod.show_viewport = False
            arm_mods.append(mod)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)

    # Re-enable ARMATURE modifiers
    for mod in arm_mods:
        mod.show_viewport = True

    # Resolve Day/Night color attributes by NAME, not by index.
    # У пользователей могут быть промежуточные слои (vertex_lights_both
    # из VC Layer System и т.п.) между Day и Night — индексный доступ
    # [0]/[1] прихватит не тот слой. Fallback на индексы — для старых
    # мешей без именованных атрибутов.
    #
    # КРИТИЧНО: берём атрибуты и лупы из ТОГО ЖЕ evaluated-меша (`mesh`),
    # из которого строится bmesh — НЕ из obj.data. При топологическом
    # модификаторе (Decimate у LOD, Mirror, Weld) индексы вершин
    # оригинала и evaluated НЕ совпадают: таблица альфы по orig-индексам
    # промахивалась, вершины уходили в ненадёжный bmesh-фолбэк и получали
    # alpha=0 (баг «на LOD появляется вертекс-альфа, которой не было»).
    # Данные меша (в отличие от bmesh) читают байтовую альфу надёжно и в 5.x.
    day_attr = vcol_get(mesh, "Day")
    night_attr = vcol_get(mesh, "Night")
    all_attrs = vcol_list(mesh)
    if day_attr is None and len(all_attrs) >= 1:
        day_attr = all_attrs[0]
    if night_attr is None and len(all_attrs) >= 2 and all_attrs[1] is not day_attr:
        night_attr = all_attrs[1]

    # Read alpha per vertex from named Day/Night attributes
    # (workaround: bmesh doesn't read alpha from byte color attrs in Blender 5.x).
    # Bulk read через foreach_get + numpy — ×30-50 быстрее старого
    # Python-цикла на каждый loop. Ключи — индексы вершин evaluated-меша,
    # они же у bmesh loop.vert.index → попадание 1:1.
    _mesh_alpha = [{}, {}]
    n_loops = len(mesh.loops)
    if n_loops > 0:
        loop_vidx = np.empty(n_loops, dtype=np.int32)
        mesh.loops.foreach_get('vertex_index', loop_vidx)
        for ci, ca in enumerate([day_attr, night_attr]):
            if ca is None or len(ca.data) != n_loops:
                continue  # missing or POINT-domain — skip
            flat = np.empty(n_loops * 4, dtype=np.float32)
            ca.data.foreach_get('color', flat)
            alphas = (flat[3::4] * 255.0).astype(np.int32)
            _mesh_alpha[ci] = dict(zip(loop_vidx.tolist(), alphas.tolist()))
        # ONE vertex alpha for both layers. The engine LERPs prelit RGBA
        # between Day and Night by time of day (alpha included,
        # CCustomBuildingDNPipeline), so alpha painted in only one layer
        # fades in/out with the clock. Kam's writes Max's single
        # vertex-alpha channel into both layers — do the same: per vertex
        # take the lower (more transparent) of Day/Night alpha, so it
        # doesn't matter which layer the user painted in.
        if _mesh_alpha[0] and _mesh_alpha[1]:
            _shared = {vi: min(a, _mesh_alpha[1].get(vi, a))
                       for vi, a in _mesh_alpha[0].items()}
            _mesh_alpha[0] = _mesh_alpha[1] = _shared
        elif _mesh_alpha[0] or _mesh_alpha[1]:
            _mesh_alpha[0] = _mesh_alpha[1] = _mesh_alpha[0] or _mesh_alpha[1]

    # Per-loop custom normals — read BEFORE triangulate so the vertex-split
    # logic below can give a SEPARATE output vertex to every distinct loop
    # normal. The DFF is per-vertex: two loops sharing one vertex but with
    # different normals (a hard edge) MUST become two verts, else the export
    # collapses them to a single averaged normal → a shading blotch on
    # re-import. Recover the authored normal where Blender zeroed the split
    # normal at a degenerate hinge corner (from the importer's attribute).
    _cn = None
    if getattr(orig_mesh, 'has_custom_normals', False):
        try:
            mesh.calc_normals_split()  # pre-4.1; 4.1+ auto-computes
        except (AttributeError, RuntimeError):
            pass
        _nl = len(mesh.loops)
        if _nl:
            _cn = np.empty(_nl * 3, dtype=np.float32)
            mesh.loops.foreach_get('normal', _cn)
            _cn = _cn.reshape(-1, 3)
            try:
                _an_attr = mesh.attributes.get('inu_authored_normal')
                if _an_attr is not None and len(_an_attr.data) == _nl:
                    _an = np.empty(_nl * 3, dtype=np.float32)
                    _an_attr.data.foreach_get('vector', _an)
                    _an = _an.reshape(-1, 3)
                    _zero = np.abs(_cn).sum(axis=1) < 1e-6
                    _anz = np.abs(_an).sum(axis=1) > 1e-6
                    _cn[_zero & _anz] = _an[_zero & _anz]
            except Exception:
                pass

    # Triangulate with bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    # Stash per-loop normals in a bmesh layer (bm.from_mesh keeps loop order =
    # mesh loop order) BEFORE triangulate so the split can read them per loop.
    nrm_layer = None
    if _cn is not None:
        try:
            nrm_layer = bm.loops.layers.float_vector.new('_inu_n')
            _i = 0
            _n = len(_cn)
            for _f in bm.faces:
                for _l in _f.loops:
                    if _i < _n:
                        _l[nrm_layer] = (float(_cn[_i, 0]), float(_cn[_i, 1]),
                                         float(_cn[_i, 2]))
                    _i += 1
        except Exception:
            nrm_layer = None
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.faces.index_update()

    # Collect UV and color layers
    max_uv = 0
    if flags['uv_map1']:
        max_uv = 1
        if flags['uv_map2'] and len(bm.loops.layers.uv) > 1:
            # Only use 2nd UV if it actually has different data (not auto-generated)
            max_uv = 2
    max_uv = min(max_uv, len(bm.loops.layers.uv))
    # For skinned meshes: respect original UV count stored on object
    orig_uv_count = obj.get('dff_num_uv_layers', 0)
    if orig_uv_count > 0:
        max_uv = min(max_uv, orig_uv_count)

    uv_layers_bm = [bm.loops.layers.uv[i] for i in range(max_uv)]

    # Pull bmesh color layers by NAME (Day/Night) — иначе при наличии
    # промежуточных слоёв (vertex_lights_both и т.п.) индекс сместится
    # и в night_colors уйдёт не то что надо.
    color_layers_bm = []
    if bm.loops.layers.color:
        if day_attr is not None:
            cl = bm.loops.layers.color.get(day_attr.name)
            if cl is not None:
                color_layers_bm.append(cl)
        if night_attr is not None and night_attr is not day_attr:
            cl = bm.loops.layers.color.get(night_attr.name)
            if cl is not None:
                color_layers_bm.append(cl)

    has_day = len(color_layers_bm) > 0 and flags['day_cols']
    has_night = len(color_layers_bm) > 1 and flags['night_cols']

    # Global "write vertex alpha" toggle. Default OFF → force fully-opaque
    # alpha (255) so stray/unpainted vertex alpha never leaks into the DFF
    # (the LOD alpha=0 pitfall). Turn on for glass/foliage/fences.
    _write_valpha = bool(getattr(
        getattr(bpy.context.scene, 'inu_settings', None),
        'gtatools_export_vertex_alpha', False))

    # ── Vertex splitting ──
    # Each vertex may need multiple copies if loops have different UV/color
    # We build a mapping: (vert_index, loop_group) → new_index

    num_original = len(bm.verts)

    # ── Per-loop custom normals ──
    # Vehicles/peds carry authored normals (set on import as custom split
    # normals). `_loop_n` returns a loop's normal from the bmesh layer stashed
    # above (falls back to the geometric vert normal for plain/map meshes with
    # no custom normals). A zero layer value (Blender couldn't represent it)
    # also falls back — never export (0,0,0), which renders black.
    def _loop_n(loop):
        if nrm_layer is not None:
            n = loop[nrm_layer]
            if abs(n[0]) + abs(n[1]) + abs(n[2]) > 1e-6:
                return (float(n[0]), float(n[1]), float(n[2]))
        bn = loop.vert.normal
        return (bn.x, bn.y, bn.z)

    # Vertex data lists (will grow as we split)
    positions = []
    normals_list = []
    # Track original bmesh vertex index for each output vertex (for skin data)
    split_origin = []

    for v in bm.verts:
        positions.append((v.co.x, v.co.y, v.co.z))
        ll = v.link_loops
        if ll:
            normals_list.append(_loop_n(ll[0]))
        else:
            normals_list.append((v.normal.x, v.normal.y, v.normal.z))
        split_origin.append(v.index)

    # Maps: BMLoop object → vertex index in output
    # Use loop objects (not loop.index) to avoid stale/duplicate index issues
    # after bmesh.ops.triangulate()
    loop_vert_map = {}

    for vert in bm.verts:
        groups = _needs_split(bm, vert, uv_layers_bm, color_layers_bm, nrm_layer)
        if groups is None:
            # No split needed — set the vert's normal from its first loop.
            ll = vert.link_loops
            if ll:
                normals_list[vert.index] = _loop_n(ll[0])
            for loop in ll:
                loop_vert_map[loop] = vert.index
        else:
            # First group keeps original index; each group gets its own normal.
            normals_list[vert.index] = _loop_n(groups[0][0])
            for loop in groups[0]:
                loop_vert_map[loop] = vert.index

            # Additional groups get new vertices (different UV / color / NORMAL)
            for group in groups[1:]:
                new_idx = len(positions)
                positions.append((vert.co.x, vert.co.y, vert.co.z))
                normals_list.append(_loop_n(group[0]))
                split_origin.append(vert.index)
                for loop in group:
                    loop_vert_map[loop] = new_idx

    num_verts = len(positions)

    # ── UV layers ──
    uv_data = []
    for _ in range(max_uv):
        uv_data.append([TexCoords() for _ in range(num_verts)])

    # ── Vertex colors ──
    day_colors = [RGBA(255, 255, 255, 255)] * num_verts if has_day else []
    night_colors = [RGBA(0, 0, 0, 255)] * num_verts if has_night else []

    # ── Triangles ──
    triangles = []

    for face in bm.faces:
        face_loops = list(face.loops)
        # Get mapped vertex indices
        vi = [loop_vert_map[loop] for loop in face_loops]

        # Triangle (RenderWare winding order)
        triangles.append(Triangle(
            a=vi[0],
            b=vi[1],
            c=vi[2],
            material=face.material_index,
        ))

        # Fill UV and color data from loops
        for loop in face_loops:
            out_idx = loop_vert_map[loop]

            for layer_i, uv_layer in enumerate(uv_layers_bm):
                uv = loop[uv_layer].uv
                uv_data[layer_i][out_idx] = TexCoords(uv.x, 1.0 - uv.y)  # V flipped

            if has_day:
                c = loop[color_layers_bm[0]]
                alpha = (_mesh_alpha[0].get(loop.vert.index, int(c[3]*255))
                         if _write_valpha else 255)
                day_colors[out_idx] = RGBA(
                    int(c[0]*255), int(c[1]*255), int(c[2]*255), alpha)

            if has_night:
                c = loop[color_layers_bm[1]]
                alpha = (_mesh_alpha[1].get(loop.vert.index, int(c[3]*255))
                         if _write_valpha else 255)
                night_colors[out_idx] = RGBA(
                    int(c[0]*255), int(c[1]*255), int(c[2]*255), alpha)

    # ── Restore the reflective-overlay faces recorded on import ─────────────
    # Vehicles stack the env-map gloss as duplicate faces on the SAME verts. The
    # importer kept them OFF the Blender mesh (which can't hold two faces on one
    # vertex set) and stashed them as position-keyed entries. Re-add each on its
    # base face's existing output verts — no new verts, so the mesh stays
    # vanilla-compact while the reflection layer survives the round-trip.
    overlay_json = obj.data.get('inu_overlay_faces')
    if overlay_json and triangles:
        import json
        try:
            overlay = json.loads(overlay_json)
        except Exception:
            overlay = []
        if overlay:
            num_mats = len(obj.data.materials) or 1
            pos_to_tri = {}
            for t in triangles:
                k = overlay_face_key(positions, t.a, t.b, t.c)
                if k not in pos_to_tri:
                    pos_to_tri[k] = (t.a, t.b, t.c)
            restored = missed = 0
            for pkey, mat in overlay:
                tv = pos_to_tri.get(pkey)
                if tv is None:
                    missed += 1
                    continue
                triangles.append(Triangle(
                    a=tv[0], b=tv[1], c=tv[2],
                    material=mat if 0 <= mat < num_mats else 0))
                restored += 1
            if restored or missed:
                print(f"[INU] overlay restore: +{restored} faces"
                      + (f", {missed} unmatched" if missed else ""))

    # ── Bounding sphere (from actual vertex positions, local space) ──
    if positions:
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        zs = [p[2] for p in positions]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        cz = (min(zs) + max(zs)) / 2.0
        radius = 0.0
        for p in positions:
            d = ((p[0] - cx)**2 + (p[1] - cy)**2 + (p[2] - cz)**2) ** 0.5
            if d > radius:
                radius = d
        center = mathutils.Vector((cx, cy, cz))
    else:
        center = mathutils.Vector((0, 0, 0))
        radius = 0.0

    # ── Materials ──
    # В DFF пишутся только материалы, на которые ссылается хотя бы одна грань:
    # пустые слоты (остатки от правок меша) тянули за собой лишние TEXTURE-чанки,
    # ели лимит движка (MATERIAL ≤ 28 на geometry) и требовали текстур в TXD.
    # Индексы граней перенумеровываются под новый список.
    materials = []
    if obj.data.materials:
        slots = list(obj.data.materials)
        used = sorted({t.material for t in triangles}) if triangles else []
        used = [i for i in used if 0 <= i < len(slots)]
        if used and len(used) < len(slots):
            remap = {old_i: new_i for new_i, old_i in enumerate(used)}
            for t in triangles:
                t.material = remap.get(t.material, 0)
            dropped = len(slots) - len(used)
            print(f"[INU] {obj.name}: материалов без граней не записано: {dropped}")
            slots = [slots[i] for i in used]
        for mat in slots:
            materials.append(_build_material(mat))
    else:
        materials.append(DffMaterial())

    # ── Build geometry ──
    geom = DffGeometry()
    geom.original_flags = obj.get('dff_geom_flags', 0)
    geom.vertices = positions
    geom.normals = normals_list
    geom.triangles = triangles
    geom.uv_layers = uv_data
    geom.prelit_colors = day_colors

    # Auto-detect vertex alpha: if any vertex has alpha < 255,
    # set material color alpha to 254 to enable alpha blending in GTA SA.
    # Can be disabled (Rockstar-style) via "Set Material Alpha" flag —
    # vanilla SA volumetric light beams (e.g. vgsecnstrct11.dff) use
    # material alpha 255 with only vertex alpha to drive transparency.
    if day_colors and flags.get('set_material_alpha', True):
        has_vertex_alpha = any(c.a < 255 for c in day_colors)
        if has_vertex_alpha:
            for m in materials:
                if m.color.a == 255:
                    m.color = RGBA(m.color.r, m.color.g, m.color.b, 254)

    # Light Beam marker for SA_Light.asi plugin.
    # When enabled, overrides the first material's color to the magic
    # marker RGBA(254,254,254,254). The plugin detects this at render
    # time and applies volumetric-beam render states (alpha test off,
    # proper alpha blend). Without the plugin, mesh renders as a plain
    # near-opaque object.
    #
    # Also: expand the bounding sphere to prevent frustum culling when
    # the player turns the camera. SA culls geometry whose bounding
    # sphere doesn't intersect the camera frustum — with a small offset
    # sphere, the mesh can disappear on slight camera rotation.
    # Light beams need to stay visible from any angle within range.
    if flags.get('light_beam_asi', False):
        if materials:
            materials[0].color = RGBA(254, 254, 254, 254)
        # Expand bounding sphere: center at origin + radius x5
        center = mathutils.Vector((0, 0, 0))
        radius = max(radius, 1.0) * 5.0

    geom.materials = materials
    geom.bounding_sphere = BoundingSphere(center.x, center.y, center.z, radius)
    geom.export_normals = flags['export_normals']
    geom.write_bin_mesh = flags['export_binsplit']
    geom.pipeline = flags['pipeline']
    geom.export_light = flags.get('light', True)
    geom.export_mod_color = flags.get('modulate_color', True)

    if has_night:
        geom.extra_colors = ExtraVertColors(colors=night_colors)

    # ── User Data PLG (from mesh custom property) ──
    geom.user_data = _load_user_data(obj.data)

    # ── Skin data (armature) ──
    armature_mod = None
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            armature_mod = mod
            break

    # An armature modifier alone doesn't imply skinning — animated map
    # objects (windmills, cranes, doors) carry an armature solely to
    # hold the frame hierarchy for IFP, with the mesh rigidly attached
    # to one frame. They have no vertex groups with real weights. Emit
    # SkinPLG only when there are bone-weighted vertex groups; otherwise
    # the mesh is exported as a rigid attachment to its frame.
    has_skin_weights = False
    if armature_mod and obj.vertex_groups:
        arm_obj_probe = armature_mod.object
        bone_names_probe = {b.name for b in arm_obj_probe.data.bones}
        # Any non-zero weight in a vertex group that matches a bone
        # name is enough — the full skin pass below builds the
        # per-vertex table.
        for v in obj.data.vertices:
            for g in v.groups:
                vg = obj.vertex_groups[g.group]
                if vg.name in bone_names_probe and g.weight > 0.0:
                    has_skin_weights = True
                    break
            if has_skin_weights:
                break

    if armature_mod and has_skin_weights and not force_no_skin:
        arm_obj = armature_mod.object
        bones = arm_obj.data.bones
        bone_names = [b.name for b in bones]

        skin = SkinData(num_bones=len(bones))

        # Inverse-bind matrices: ALWAYS compute from the CURRENT armature so
        # bone edits (Edit-Mode rest-pose changes) are reflected. Reusing the
        # stored import-time matrices kept the OLD bind pose → the skeleton/
        # skin reverted on export (same root cause as the frame positions
        # above). Vertex weights are already recomputed from groups below.
        import json
        for bone in bones:
            inv_mat = bone.matrix_local.inverted().transposed()
            skin.bone_matrices.append(
                [[inv_mat[row][col] for col in range(4)] for row in range(4)])

        # Skin header (num_used / max_weights / bones_used) is weights-related,
        # NOT bone-position — replay it from the import ONLY when the bone COUNT
        # still matches. If the user added/deleted a bone, the stored bones_used
        # would reference indices that no longer exist (or omit a new bone), so
        # fall through to the fresh weight-derived computation below.
        raw_bm = obj.get('dff_bone_matrices')
        raw_bu = obj.get('dff_skin_bones_used')
        if raw_bm and raw_bu:
            try:
                _stored_bones = (json.loads(raw_bm)
                                 if isinstance(raw_bm, str) else raw_bm)
                _stored_count = len(_stored_bones)
            except Exception:
                _stored_count = -1
            if _stored_count == len(bones):
                skin.num_used = obj.get('dff_skin_num_used', 0)
                skin.max_weights = obj.get('dff_skin_max_weights', 4)
                try:
                    skin.bones_used = (json.loads(raw_bu)
                                       if isinstance(raw_bu, str)
                                       else list(raw_bu))
                except Exception:
                    pass

        # Vertex weights — build per-original-vertex first, then expand for splits
        bone_name_to_idx = {name: i for i, name in enumerate(bone_names)}
        orig_skin = []  # per original bmesh vertex: (indices, weights)
        for v_idx in range(num_original):
            vert = mesh.vertices[v_idx]
            bone_idx = [0, 0, 0, 0]
            bone_wgt = [0.0, 0.0, 0.0, 0.0]

            entries = []
            for g in vert.groups:
                vg = obj.vertex_groups[g.group]
                bi = bone_name_to_idx.get(vg.name)
                if bi is not None:
                    entries.append((bi, g.weight))

            entries.sort(key=lambda x: -x[1])
            for i, (bi, w) in enumerate(entries[:4]):
                bone_idx[i] = bi
                bone_wgt[i] = w

            # Normalize weights
            total = sum(bone_wgt)
            if total > 0:
                bone_wgt = [w / total for w in bone_wgt]

            # Kams: root bone (index 0) must be last in the 4-slot array
            for i in range(3):  # check slots 0,1,2
                if bone_idx[i] == 0 and bone_wgt[i] > 0:
                    bone_idx[i], bone_idx[3] = bone_idx[3], bone_idx[i]
                    bone_wgt[i], bone_wgt[3] = bone_wgt[3], bone_wgt[i]
                    break

            orig_skin.append((tuple(bone_idx), tuple(bone_wgt)))

        # Map to output vertices using split_origin (O(n))
        for v_idx in range(num_verts):
            orig_idx = split_origin[v_idx]
            if orig_idx < len(orig_skin):
                skin.bone_indices.append(orig_skin[orig_idx][0])
                skin.bone_weights.append(orig_skin[orig_idx][1])
            else:
                skin.bone_indices.append((0, 0, 0, 0))
                skin.bone_weights.append((0.0, 0.0, 0.0, 0.0))

        # Used-bone list = every bone referenced with a non-zero weight,
        # bone 0 INCLUDED (vanilla ryder.dff / wfycrk.dff list it). The
        # engine uploads the bone palette only for the bones in this list
        # when it is shorter than the hierarchy, so a referenced bone that
        # is missing here keeps a stale matrix from the previous model;
        # and num_used == 0 skips the palette upload altogether. A stored
        # import-time list is kept (round-trip fidelity) but widened by
        # anything the current weights reference.
        used_set = set()
        for vi in range(len(skin.bone_indices)):
            indices = skin.bone_indices[vi]
            weights = skin.bone_weights[vi]
            for slot in range(4):
                if weights[slot] > 0:
                    used_set.add(indices[slot])
        if skin.bones_used:
            used_set.update(skin.bones_used)
        else:
            skin.max_weights = 4
        skin.bones_used = sorted(used_set)
        skin.num_used = len(skin.bones_used)

        geom.skin = skin

    # ── Breakable extension (chunk 0x253F2FD) ──
    # W1: the engine (BreakableStreamRead @ 0x59CEC0) expects a full copy
    # of the mesh after the magic word, not an allocation record — write
    # the geometry itself as the break copy (one piece per material).
    inu_props = getattr(obj, 'inu', None)
    if inu_props and getattr(inu_props, 'breakable', False):
        geom.breakable = BreakableData.from_geometry(geom)

    # ── Add to clump ──
    geom_idx = len(clump.geometries)
    clump.geometries.append(geom)
    clump.atomics.append(DffAtomic(
        frame_index=frame_index,
        geometry_index=geom_idx,
    ))

    # Debug summary
    print(f"[DFF Export] _process_mesh: verts={num_verts} tris={len(triangles)} "
          f"uv_layers={max_uv} has_skin={geom.skin is not None} "
          f"frame_index={frame_index} geom_flags=0x{geom._build_flags():X}")
    if geom.skin:
        skin = geom.skin
        print(f"[DFF Export]   SkinPLG: bones={skin.num_bones} used={skin.num_used} "
              f"max_w={skin.max_weights} bones_used={skin.bones_used[:10]} "
              f"vert_count={len(skin.bone_indices)} matrices={len(skin.bone_matrices)}")

    bm.free()
    eval_obj.to_mesh_clear()


# ── Frame building ───────────────────────────────────────────────

def _live_frame_transform(obj):
    """Read the object's current ``matrix_local`` as DFF (rotation, position).

    ``matrix_local`` is parent-relative — exactly the space a DFF frame
    stores — so for a top-level object it equals its global placement and
    for a parented part it equals the offset under its parent frame.

    A DFF frame stores its rotation as three ROW vectors ``right``, ``up``,
    ``at`` (RenderWare ``RwMatrix``: ``out = in.x*right + in.y*up + in.z*at
    + pos``), i.e. the axes of the local space — which are the COLUMNS of
    ``matrix_local.to_3x3()``. The Blender matrix therefore has to be
    transposed before its rows are written, exactly like the bone exporter
    below (``mat.to_3x3().transposed()``), the object importer
    (``dff_import.py`` builds ``matrix_basis`` from the columns
    ``rot[0], rot[3], rot[6]``) and DragonFF do.

    Writing ``to_3x3()`` untransposed (previous behaviour) stored the
    inverse rotation: every frame with a non-symmetric rotation came out
    rotated the wrong way both in game and on re-import (a door frame
    authored as Rz(+90) landed as Rz(-90), 180° off around its hinge).
    """
    ml = obj.matrix_local
    loc = ml.to_translation()
    m = ml.to_3x3().transposed()
    rotation = (
        m[0][0], m[0][1], m[0][2],
        m[1][0], m[1][1], m[1][2],
        m[2][0], m[2][1], m[2][2],
    )
    return rotation, (loc.x, loc.y, loc.z)


def _frame_transform_moved(obj, orig_rot, orig_pos, eps: float = 1e-5) -> bool:
    """True if the object's live transform diverges from the cached
    import-time frame transform — i.e. the user moved/rotated/scaled it.

    The cache (``dff_frame_rot``/``dff_frame_pos``) is an import-time
    snapshot that is **not** updated when the object moves. So trusting it
    blindly writes the stale (often (0,0,0)) placement back into the DFF
    and every re-imported part snaps to the origin. We compare against the
    live ``matrix_local`` and fall back to it the moment they differ."""
    live_rot, live_pos = _live_frame_transform(obj)
    if any(abs(live_pos[i] - orig_pos[i]) > eps for i in range(3)):
        return True
    return any(abs(live_rot[i] - orig_rot[i]) > eps for i in range(9))


def _build_frame(obj, parent_index: int = -1,
                 allow_live: bool = False) -> DffFrame:
    """Create a DffFrame from a Blender object.

    Uses stored original frame data for round-trip fidelity if available.

    ``allow_live`` (static-hierarchy export only): when the object carries
    a cached import-time transform but the user has since moved/rotated it,
    write the LIVE ``matrix_local`` instead of the stale cache. Kept OFF
    for the skinned/animated path, where the mesh frame is deliberately
    pinned to identity and its real placement lives in the bone matrices —
    there the cached snapshot is authoritative and must not be overridden.
    """
    frame = DffFrame()
    frame.name = _strip_ext(obj.name)
    frame.parent = parent_index

    # Use original frame data if available (round-trip)
    orig_rot = obj.get('dff_frame_rot')
    orig_pos = obj.get('dff_frame_pos')
    orig_flags = obj.get('dff_frame_flags', 0)
    frame.write_name = obj.get('dff_frame_write_name', False)

    if orig_rot and orig_pos and not (
            allow_live and _frame_transform_moved(obj, orig_rot, orig_pos)):
        # Untouched imported object (or skinned path) — replay the exact
        # import-time bytes so a pure round-trip stays bit-perfect.
        frame.rotation = tuple(orig_rot)
        frame.position = tuple(orig_pos)
        frame.flags = orig_flags
    else:
        # New object, OR an imported one the user has since moved/rotated:
        # the cached snapshot is stale, so write the LIVE transform. This
        # is what carries the part's global placement into frame.position
        # (mesh verts stay in local/origin space) — without it, moved
        # parts re-import stacked at the world origin.
        frame.rotation, frame.position = _live_frame_transform(obj)
        frame.flags = orig_flags

    # User Data PLG (from object custom property)
    frame.user_data = _load_user_data(obj)

    # HAnim PLG for Empty-based animobj rigs (Kams-style). Each Empty
    # with inu_bone_id gets a minimal HAnim entry; the rig ROOT
    # additionally carries the full bone tree (collected by the
    # caller after all frames are built). Verified against vanilla
    # derrick01.dff — all 5 frames carry HAnim PLG.
    if obj.type == 'EMPTY' and 'inu_bone_id' in obj:
        bone_id_int = int(obj['inu_bone_id'])
        frame.hanim = HAnimData(bone_id=bone_id_int)
        # Animobj rig root: frame.flags = 0x20003 — matches vanilla
        # SA animated map objects (nt_windmill, derrick01, etc.).
        # Without this flag the engine treats the clump root as a
        # plain static frame and the HAnim hierarchy walker bails
        # before it ever applies the IFP track.
        if obj.get('inu_animobj_empty_root') and not orig_flags:
            frame.flags = 0x20003

    return frame


# ── Armature export ──────────────────────────────────────────────

def _export_armature(arm_obj, clump: DffClump, parent_frame: int):
    """Export armature bones as frames with HAnimPLG.

    Uses stored original frame data from armature['dff_frame_data'] for round-trip fidelity.
    """
    import json
    bones = arm_obj.data.bones

    # Load original frame data if available
    orig_data = {}
    raw_json = arm_obj.get('dff_frame_data')
    if raw_json:
        try:
            orig_data = json.loads(raw_json)
            print(f"[DFF Export] Loaded dff_frame_data: {len(orig_data)} bones")
        except Exception as e:
            print(f"[DFF Export] Failed to load dff_frame_data: {e}")
    else:
        print(f"[DFF Export] No dff_frame_data on armature")

    for i, bone in enumerate(bones):
        frame = DffFrame()
        frame.name = bone.name

        # Use original frame data if available (round-trip)
        bone_id = str(bone.get('bone_id', 0))
        orig = orig_data.get(bone_id)

        # Position/rotation: ALWAYS compute from the CURRENT armature so a
        # user's bone edits (Edit-Mode repositioning of the rest pose) take
        # effect. The stored import-time rot/pos was reused before, silently
        # discarding every edit — the "skeleton/bones revert to their
        # original position on export, ignoring transforms" bug.
        #
        # The transform must live in the space of the frame we point at. For
        # i == 0 frame.parent is forced to the clump root (below), so the root
        # bone stays ABSOLUTE. If that bone happens to carry an armature
        # parent, going parent-relative wrote position (0,0,0) while the skin
        # bind matrix — built from the absolute matrix_local — still said
        # (3.197, 0.595, 0.817): skeleton and skin disagreed by that offset
        # and the ped collapsed / lay on its side in game. No-op for rigs whose
        # root is unparented (verified: re-exporting DragonFF's fam3 stays
        # bit-consistent, max err 0.0000).
        if bone.parent and i != 0:
            mat = bone.parent.matrix_local.inverted() @ bone.matrix_local
        else:
            mat = bone.matrix_local
        loc = mat.to_translation()
        rot = mat.to_3x3().transposed()
        frame.position = (loc.x, loc.y, loc.z)
        frame.rotation = (
            rot[0][0], rot[0][1], rot[0][2],
            rot[1][0], rot[1][1], rot[1][2],
            rot[2][0], rot[2][1], rot[2][2],
        )
        # Flags / write_name are DFF metadata (not position) — keep them
        # from the import for round-trip fidelity, else sensible defaults.
        if orig:
            frame.flags = orig.get('flags', 0)
            frame.write_name = bool(orig.get('write_name', False))
        else:
            frame.write_name = True
            if i == 0:      # SA skinned root frame flags
                frame.flags = 0x20003
        # Parent frame — use original if available
        if orig and 'parent' in orig:
            frame.parent = orig['parent']
        elif i == 0:
            frame.parent = parent_frame
        else:
            parent_bone = bone.parent
            if parent_bone:
                parent_bone_idx = list(bones).index(parent_bone)
                frame.parent = parent_frame + 1 + parent_bone_idx
            else:
                frame.parent = parent_frame

        # HAnimPLG
        bone_id_int = bone.get('bone_id', 0)

        if i == 0:
            # Root bone gets full bone list
            hanim = HAnimData(bone_id=bone_id_int)
            for j, b in enumerate(bones):
                b_id = str(b.get('bone_id', 0))
                b_orig = orig_data.get(b_id)
                hanim.bones.append(HAnimBone(
                    bone_id=b.get('bone_id', 0),
                    index=b_orig.get('index', j) if b_orig else b.get('bone_index', j),
                    bone_type=b.get('bone_type', 0),
                ))
            frame.hanim = hanim
        else:
            frame.hanim = HAnimData(bone_id=bone_id_int)

        clump.frames.append(frame)


# ── 2DFX export ──────────────────────────────────────────────────

def _collect_2dfx(objects) -> Extension2dfx:
    """Collect 2DFX effect entries from Empty objects with inu.type == '2DFX'."""
    ext = Extension2dfx()

    # 2DFX coords must be in the MESH's LOCAL space (= the DFF geometry space,
    # same space the verts are written in). We use the full world-matrix
    # transform below — NOT `obj.location - mesh.location`. That naive
    # subtraction ignores the mesh's rotation/scale and the parent relationship
    # (2DFX empties are children of the mesh), so it shifted every effect the
    # moment the model was rotated or placed off-origin in the scene.
    mesh_obj = next((o for o in objects if o.type == 'MESH'), None)
    mesh_inv = mesh_obj.matrix_world.inverted() if mesh_obj else None

    for obj in objects:
        if obj.type != 'EMPTY':
            continue
        inu = getattr(obj, 'inu', None)
        if not inu or getattr(inu, 'type', '') != '2DFX':
            continue

        effect_type = getattr(inu, 'effect_2dfx', '')
        # 2DFX position in the mesh's local space (proper world-matrix
        # transform — robust to model rotation/scale and to the empty being a
        # child of the mesh).
        _wp = obj.matrix_world.translation
        _lp = (mesh_inv @ _wp) if mesh_inv is not None else _wp
        loc = (_lp.x, _lp.y, _lp.z)

        if effect_type == 'LIGHT':
            light = Light2dfx(loc=loc)
            inu = getattr(obj, 'inu', None)
            if inu and hasattr(inu, 'color_2dfx'):
                c = inu.color_2dfx
                light.color = RGBA(int(c[0] * 255), int(c[1] * 255),
                                   int(c[2] * 255), int(c[3] * 255))
            else:
                color_raw = obj.get('2dfx_color', [255, 255, 255, 255])
                light.color = RGBA(int(color_raw[0]), int(color_raw[1]),
                                   int(color_raw[2]), int(color_raw[3]))
            light.corona_far_clip = obj.get('2dfx_corona_far_clip', 0.0)
            light.pointlight_range = obj.get('2dfx_pointlight_range', 0.0)
            inu = getattr(obj, 'inu', None)
            if inu:
                light.corona_size = inu.corona_size_2dfx
                light.shadow_size = inu.shadow_size_2dfx
            else:
                # Legacy fallback for objects without INUObjectProps
                light.corona_size = obj.get('2dfx_corona_size', 0.0)
                light.shadow_size = obj.get('2dfx_shadow_size', 0.0)
            light.corona_show_mode = int(inu.show_mode_2dfx) if inu else obj.get('2dfx_corona_show_mode', 0)
            light.corona_enable_reflection = obj.get('2dfx_corona_enable_reflection', 0)
            light.corona_flare_type = int(inu.flare_type_2dfx) if inu else obj.get('2dfx_corona_flare_type', 0)
            light.shadow_color_multiplier = obj.get('2dfx_shadow_color_multiplier', 0)
            light.flags1 = obj.get('2dfx_flags1', 0)
            light.corona_tex_name = inu.corona_tex_2dfx if inu else obj.get('2dfx_corona_tex', '')
            light.shadow_tex_name = inu.shadow_tex_2dfx if inu else obj.get('2dfx_shadow_tex', '')
            light.shadow_z_distance = obj.get('2dfx_shadow_z_distance', 0)
            light.flags2 = obj.get('2dfx_flags2', 0)
            look = obj.get('2dfx_look_direction')
            if look is not None:
                light.look_direction = (int(look[0]), int(look[1]), int(look[2]))
            ext.entries.append(light)

        elif effect_type == 'PARTICLE':
            particle = Particle2dfx(loc=loc)
            particle.effect_name = obj.get('2dfx_effect_name', '')
            ext.entries.append(particle)

        elif effect_type == 'PED_ATTRACTOR':
            ped = PedAttractor2dfx(loc=loc)
            ped.attractor_type = obj.get('2dfx_attractor_type', 0)
            rot = obj.get('2dfx_rotation_matrix', [1,0,0, 0,1,0, 0,0,1])
            ped.rotation_matrix = tuple(float(v) for v in rot)
            ped.external_script = obj.get('2dfx_external_script', '')
            ped.ped_existing_probability = obj.get('2dfx_ped_probability', 0)
            ped.flags = int(obj.get('2dfx_ped_flags', 0))
            ped.unknown = int(obj.get('2dfx_ped_unknown', 0))
            ext.entries.append(ped)

        elif effect_type == 'SUN_GLARE':
            ext.entries.append(SunGlare2dfx(loc=loc))

        elif effect_type == 'ENTER_EXIT':
            ee = EnterExit2dfx(loc=loc)
            ee.enter_angle = inu.ee_enter_angle
            ee.approximation_radius_x = inu.ee_radius_x
            ee.approximation_radius_y = inu.ee_radius_y
            ee.exit_loc = tuple(inu.ee_exit_loc)
            ee.exit_angle = inu.ee_exit_angle
            ee.interior = int(inu.ee_interior)
            ee.flags1 = int(inu.ee_flags1)
            ee.sky_color = int(inu.ee_sky_color)
            ee.interior_name = inu.ee_interior_name
            ee.time_on = int(inu.ee_time_on)
            ee.time_off = int(inu.ee_time_off)
            ee.flags2 = int(inu.ee_flags2)
            ee.unknown = int(inu.ee_unknown)
            ext.entries.append(ee)

        elif effect_type == 'ROAD_SIGN':
            rs = RoadSign2dfx(loc=loc)
            rs.size = tuple(inu.sign_size)
            rs.rotation = tuple(inu.sign_rotation)
            rs.text_lines = [inu.sign_text0, inu.sign_text1,
                             inu.sign_text2, inu.sign_text3]
            # Pack friendly fields → flags byte (bits 0-1 lines-1,
            # 2-3 max chars, 4-5 colour).
            mc = {'16': 0, '2': 1, '4': 2, '8': 3}.get(inu.sign_maxchars, 0)
            col = {'WHITE': 0, 'BLACK': 1, 'GREY': 2, 'RED': 3}.get(inu.sign_color, 0)
            rs.flags = ((max(1, inu.sign_lines) - 1) & 0x3) | ((mc & 0x3) << 2) | ((col & 0x3) << 4)
            ext.entries.append(rs)

        elif effect_type == 'ESCALATOR':
            # Points are stored relative to the marker (Empty local space).
            # Push each through the Empty's world matrix, then into mesh-local
            # space — so the exported points match exactly what the preview
            # shows, robust to the Empty being moved / rotated / scaled.
            import mathutils

            def _esc_pt(off):
                world = obj.matrix_world @ mathutils.Vector((off[0], off[1], off[2]))
                lp = (mesh_inv @ world) if mesh_inv is not None else world
                return (lp.x, lp.y, lp.z)

            es = Escalator2dfx(loc=loc)
            es.bottom = _esc_pt(inu.esc_bottom)
            es.top = _esc_pt(inu.esc_top)
            es.end = _esc_pt(inu.esc_end)
            es.direction = int(inu.esc_direction)
            ext.entries.append(es)

        elif effect_type == 'RAW_2DFX':
            raw = bytes(int(b) & 0xFF for b in obj.get('2dfx_raw_bytes', []))
            ext.entries.append(RawUnknown2dfx(
                effect_id=int(obj.get('2dfx_raw_effect_id', 0)),
                loc=loc, raw=raw))

    return ext if ext.entries else None


# ── Hierarchy traversal ──────────────────────────────────────────

def _is_col_primitive_empty(obj):
    """True если empty — коллизионный примитив (ColSphere/ColBox), который надо
    встраивать как COL, а НЕ выносить во FrameList.

    Тонкость: и col-примитивы (col_import), и дамми фреймов машины/педа
    (wheel_lf_dummy, chassis_dummy, … — dff_import) создаются как SPHERE/CUBE
    empty. Отличаем по маркерам: дамми фрейма несут dff_frame_* (позиция/поворот/
    флаги кадра), col-примитивы — нет. Если спутать, дамми колёс выпадут из
    FrameList → движок читает мусорные позиции в GetWheelPosn и краш на спавне.
    """
    if getattr(obj, 'empty_display_type', '') not in ('SPHERE', 'CUBE'):
        return False
    # Дамми DFF-фрейма (в т.ч. wheel_*_dummy/chassis_dummy) — это КАДР, не COL.
    if ('dff_frame_pos' in obj or 'dff_frame_rot' in obj
            or 'dff_frame_flags' in obj):
        return False
    return True


def _collect_frame_objects(objects):
    """Return list of (obj, parent_obj) in DFS order for DFF frame list.

    Includes MESH and EMPTY objects; excludes 2DFX Empties, Armatures, and
    NON-type objects. Roots are objects whose Blender parent is not in the set.
    """
    valid = []
    for obj in objects:
        inu = getattr(obj, 'inu', None)
        itype = getattr(inu, 'type', 'OBJ') if inu else 'OBJ'
        if itype == 'NON':
            continue
        if obj.type == 'MESH':
            # COL/SHA collision meshes are embedded separately as
            # CHUNK_COLLISION_MODEL — they must NOT also become visible frame
            # atomics (that would render the collision hull in-game and add a
            # stray frame). They still reach build_dff_clump via the objects
            # list, which picks them up for embedding.
            # is_collision_mesh, not the raw tag: an explicit `_DFF`/`_LOD`
            # name marker outranks a stale COL tag, otherwise the mesh drops
            # out here AND out of the geometry list → DFF with nothing to draw.
            if is_collision_mesh(obj):
                continue
            valid.append(obj)
        elif obj.type == 'EMPTY' and itype != '2DFX':
            # SPHERE/CUBE-display empties are collision sphere/box primitives
            # (embedded as COL), not frames — skip them. НО дамми фреймов
            # (wheel_*_dummy/chassis_dummy) тоже CUBE — их НЕ пропускаем (см.
            # _is_col_primitive_empty), иначе колёса теряются → краш GetWheelPosn.
            if _is_col_primitive_empty(obj):
                continue
            valid.append(obj)

    obj_set = set(valid)
    input_order = {o: i for i, o in enumerate(valid)}
    roots = sorted(
        (o for o in valid if o.parent is None or o.parent not in obj_set),
        key=lambda o: input_order[o],
    )

    ordered = []
    visited = set()

    def dfs(obj, parent_obj):
        if obj in visited:
            return
        visited.add(obj)
        ordered.append((obj, parent_obj))
        # For animated map objects (Empty-rig flow): Empties carrying
        # an inu_bone_id are the HAnim bones — they MUST come before
        # any static / non-bone sibling Empties in the FrameList, so
        # HAnim's bone_list `idx` field stays a small sequential
        # integer matching vanilla (root=0, pivot=1, …). When the
        # game's CClumpAnimMgr resolves an IFP track via the
        # FindFrameFromHierarchyId path it expects this ordering;
        # otherwise the animated frame ends up at a higher idx and
        # the matcher fails silently.
        children = sorted(
            (c for c in obj.children if c in obj_set),
            key=lambda c: (
                0 if ('inu_bone_id' in c) else 1,
                input_order[c],
            ),
        )
        for child in children:
            dfs(child, obj)

    for root in roots:
        dfs(root, None)

    return ordered


# ── Main export function ─────────────────────────────────────────

def build_dff_clump(objects, version: int = GTA_SA_VERSION,
                    col_model_name: str = "") -> DffClump:
    """Build a ``DffClump`` from Blender objects — main thread only.

    All bpy access (mesh geometry, materials, UV, armature, 2DFX,
    embedded collision) happens here. The returned clump is a plain
    dataclass tree with no Blender references, so serialisation via
    ``clump.to_bytes()`` can then run in a worker pool.

    ``col_model_name`` is used for the name field of embedded COL
    chunks (CHUNK_COLLISION_MODEL). Normally this is the DFF's base
    filename without extension; the single-file ``export_dff`` wrapper
    derives it from ``filepath``.

    VCL Layer System (Phase 3): when any mesh in *objects* has VCL
    layers, the layer stacks are composited into Day/Night BEFORE the
    exporter reads them, and restored AFTER. So exporting a model
    with edit layers produces a DFF whose vertex colors are the
    flattened end result, while the user's working .blend keeps its
    layers intact for further editing.
    """
    # Pre-collect mesh objects so we can wrap the entire build pass
    # inside the VCL flatten context. The list is rebuilt below from
    # ``objects`` again — duplicating it here is the price of not
    # re-architecting the function for a one-line change.
    _vcl_target_meshes = list({
        obj.data for obj in objects
        if obj.type == 'MESH' and obj.data is not None
    })

    from ..tools.vc_layers import flatten_for_export
    from ..tools.prelight import setup_prelight_preview

    # Снять превью прилайта (Prelight_Mix) с экспортируемых мешей НА ВРЕМЯ
    # чтения: иначе Base Color/текстура читаются через превью-ноды и DFF
    # выходит неверным (тёмным/не тем цветом). Тут — ОБЩИЙ путь сборки, значит
    # защищены ВСЕ экспорты (одиночный DFF, Export All, в IMG) без ручного
    # отключения опции. Одиночный оператор уже снимает превью до вызова — там
    # ноды нет, повторно не трогаем. Возврат гарантирован finally.
    _pl_off = []
    try:
        for obj in objects:
            if getattr(obj, 'type', None) != 'MESH':
                continue
            if any(ms.material and ms.material.use_nodes
                   and ms.material.node_tree.nodes.get("Prelight_Mix")
                   for ms in obj.material_slots):
                try:
                    setup_prelight_preview(obj, enable=False)
                    _pl_off.append(obj)
                except Exception:                     # noqa: BLE001
                    pass
        with flatten_for_export(_vcl_target_meshes):
            return _build_dff_clump_inner(objects, version, col_model_name)
    finally:
        for obj in _pl_off:
            try:
                setup_prelight_preview(obj, enable=True)
            except Exception:                         # noqa: BLE001
                pass


def _build_dff_clump_inner(objects, version: int, col_model_name: str) -> DffClump:
    clump = DffClump(version=version)

    # Separate objects by type
    mesh_objects = []
    armatures = set()

    for obj in objects:
        if obj.type == 'MESH':
            mesh_objects.append(obj)
            # Check for armature modifier
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    armatures.add(mod.object)

    has_skinned = bool(armatures)

    if has_skinned:
        # Skinned DFF (ped): flat one-mesh-one-frame, armature handles hierarchy
        for obj in mesh_objects:
            frame = _build_frame(obj)
            frame_idx = len(clump.frames)

            clump.frames.append(frame)

            arm_obj = None
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    arm_obj = mod.object
                    break

            if arm_obj:
                import base64
                raw_fl = arm_obj.get('dff_raw_frame_list')

                if raw_fl:
                    try:
                        clump.raw_frame_list = base64.b64decode(raw_fl)
                        clump.frames.clear()
                        print(f"[DFF Export] Using raw frame list ({len(clump.raw_frame_list)} bytes)")
                    except Exception:
                        _export_armature(arm_obj, clump, frame_idx)
                else:
                    _export_armature(arm_obj, clump, frame_idx)

            if clump.raw_frame_list:
                stored_fi = obj.get('dff_mesh_frame_index', -1)
                if stored_fi >= 0:
                    mesh_frame_idx = stored_fi
                else:
                    from struct import unpack_from
                    if len(clump.raw_frame_list) >= 16:
                        frame_count = unpack_from('<I', clump.raw_frame_list, 12)[0]
                        mesh_frame_idx = frame_count - 1
                        print(f"[DFF Export] Parsed frame_count={frame_count} from raw, mesh frame={mesh_frame_idx}")
                    else:
                        mesh_frame_idx = frame_idx
                print(f"[DFF Export] Skinned mesh: frame_index={mesh_frame_idx}")
            else:
                mesh_frame_idx = frame_idx

            # Animated map object detection: when every weighted vertex
            # group targets a single bone, the mesh is rigidly attached
            # to that bone (typical of windmill/crane/door pattern). We
            # route the atomic at the BONE's frame instead of the mesh
            # frame and skip SkinPLG — engine drives the mesh via the
            # bone frame's IFP-animated transform, not per-vertex skin.
            rigid_bone_idx = _classify_skin(obj, arm_obj)
            if rigid_bone_idx is not None and arm_obj and not clump.raw_frame_list:
                # Bones appear after the mesh frame: frame_idx is mesh,
                # bones start at frame_idx + 1.
                target_frame_idx = frame_idx + 1 + rigid_bone_idx
                if target_frame_idx < len(clump.frames):
                    print(f"[DFF Export] Rigid attach to bone[{rigid_bone_idx}] "
                          f"({clump.frames[target_frame_idx].name}) — "
                          f"atomic frame={target_frame_idx}, no SkinPLG")
                    _process_mesh(obj, clump, target_frame_idx,
                                  force_no_skin=True)
                    continue

            _process_mesh(obj, clump, mesh_frame_idx)
    else:
        # Static DFF: walk Blender hierarchy, write Empty→dummy frames
        ordered = _collect_frame_objects(objects)
        obj_to_frame_idx = {}

        # Pass 1: FRAME list in DFS/hierarchy order (parents before children —
        # required for the parentIndex references).
        for obj, parent_obj in ordered:
            parent_idx = obj_to_frame_idx[parent_obj] if parent_obj is not None else -1
            frame = _build_frame(obj, parent_index=parent_idx, allow_live=True)
            my_idx = len(clump.frames)
            clump.frames.append(frame)
            obj_to_frame_idx[obj] = my_idx

        # Pass 2: ATOMICS/geometries in the ORIGINAL render order. GTA renders
        # atomics in DFF-list order; for alpha-blended parts (glossy car paint,
        # glass) that order decides the blend, so a re-export MUST reproduce it
        # — Blender's alphabetical child order otherwise scrambles it and the
        # car renders dull/dark. `inu_atomic_order` is stamped on import;
        # objects without it (built from scratch) keep their DFS order via the
        # stable sort.
        mesh_objs = [o for o, _ in ordered if o.type == 'MESH']
        mesh_objs.sort(key=lambda o: o.get('inu_atomic_order', 1 << 30))
        for obj in mesh_objs:
            _process_mesh(obj, clump, obj_to_frame_idx[obj])

        print(f"[DFF Export] Static hierarchy: {len(clump.frames)} frames "
              f"({sum(1 for o, _ in ordered if o.type == 'EMPTY')} dummies)")

        # Empty-rig animobj (Kams-style): once all frames are built,
        # populate the root rig Empty's HAnim with the full bone tree —
        # verified against vanilla derrick01.dff (5 frames, all with
        # HAnim PLG, root carries full bone list).
        #
        # bone_type field follows RenderWare HAnim hierarchy markers
        # (bit 0 = PUSH; bit 1 = POP).
        for obj, _parent_obj in ordered:
            if obj.type != 'EMPTY' or not obj.get('inu_animobj_empty_root'):
                continue
            root_frame_idx = obj_to_frame_idx.get(obj)
            if root_frame_idx is None:
                continue
            root_frame = clump.frames[root_frame_idx]

            bone_nodes = []  # list of (node, depth)

            def _walk(node, depth):
                if 'inu_bone_id' in node:
                    bone_nodes.append((node, depth))
                for ch in node.children:
                    _walk(ch, depth + 1)

            _walk(obj, 0)

            # bone_type encoding matches vanilla SA animated map object
            # DFFs exactly (verified against nt_windmill, oilplodbitbase,
            # derrick01, nt_noddonkbase):
            #   * first bone (root): type=0
            #   * last bone: type=1
            #   * intermediate bones at the same depth as siblings
            #     alternate 3, 0, 3, 0, ... (per derrick01 pattern)
            # For the common single-pivot case (root + 1 pivot) this
            # produces [0, 1] — exact match with nt_windmill.
            rig_bones = []
            n = len(bone_nodes)
            for i, (node, depth) in enumerate(bone_nodes):
                fi = obj_to_frame_idx.get(node)
                if fi is None:
                    continue
                if i == 0:
                    bt = 0
                elif i == n - 1:
                    bt = 1
                else:
                    bt = 3 if (i % 2 == 1) else 0
                rig_bones.append(HAnimBone(
                    bone_id=int(node['inu_bone_id']),
                    index=fi,
                    bone_type=bt,
                ))

            if root_frame.hanim is None:
                root_frame.hanim = HAnimData(
                    bone_id=int(obj.get('inu_bone_id', 0)))
            root_frame.hanim.bones = rig_bones

    # If no frames were created, add a default one
    if not clump.frames:
        clump.frames.append(DffFrame(name="root"))

    # Collect 2DFX effects — from selected objects AND from children of selected meshes
    all_objects = list(objects)
    for obj in objects:
        if obj.type == 'MESH':
            for child in obj.children:
                if child not in all_objects:
                    all_objects.append(child)
    ext_2dfx = _collect_2dfx(all_objects)
    if ext_2dfx and clump.geometries:
        clump.geometries[-1].ext_2dfx = ext_2dfx

        # Create RW Light frames for each Light2dfx entry (like Kam's 3DS Max Omni)
        light_count = 0
        for entry in ext_2dfx.entries:
            if isinstance(entry, Light2dfx):
                light_count += 1
                # Add frame for the light (child of root frame 0)
                light_frame = DffFrame(
                    name=f"Omni{light_count:03d}",
                    position=entry.loc,
                    parent=0,
                    flags=3,
                )
                frame_idx = len(clump.frames)
                clump.frames.append(light_frame)

                # Add RW Light linked to this frame
                color_r = entry.color.r / 255.0
                color_g = entry.color.g / 255.0
                color_b = entry.color.b / 255.0
                rw_light = DffLight(
                    frame_index=frame_idx,
                    radius=entry.pointlight_range * 10.0,
                    color=(color_r, color_g, color_b),
                )
                clump.lights.append(rw_light)

    # Embed collision data in DFF (CHUNK_COLLISION_MODEL). COL version
    # is derived from the same RW version: SA (0x36xxx) writes COL3,
    # anything older writes COL1 — III and VC both accept only 'COLL'
    # (COL2 is an SA-era format). Inline rather than calling
    # _resolve_col_version() since build_dff_clump receives `version`
    # directly and we want the COL version to track the DFF version.
    # Collision = COL/SHA meshes (faces + shadow) AND sphere/box collision
    # primitives, which the importer creates as SPHERE/CUBE-display Empties.
    # Both must be embedded — otherwise the vehicle keeps its body-mesh
    # collision but loses the sphere primitives (wheels, bumpers) and drives
    # through other models. build_col_model already turns sphere/cube empties
    # into ColSphere/ColBox via _collect_empty.
    col_objects = [obj for obj in objects
                   if is_collision_mesh(obj)
                   or (obj.type == 'EMPTY'
                       and _is_col_primitive_empty(obj))]
    if col_objects:
        from .col_export import export_col_bytes
        col_ver = 3 if version >= 0x36000 else 1
        clump.collision_data = export_col_bytes(
            col_objects, version=col_ver, model_name=col_model_name)

    # Collect UV animations from materials used across all exported meshes
    uv_mats = []
    seen_mat_ids = set()
    for obj in objects:
        if obj.type != 'MESH':
            continue
        for slot in obj.data.materials:
            if slot is None or id(slot) in seen_mat_ids:
                continue
            seen_mat_ids.add(id(slot))
            uv_mats.append(slot)
    clump.uv_anim_dict = _collect_uv_anim_dict(uv_mats)

    return clump


def _audit_vehicle_frames(clump):
    """Check the frame names a vehicle DFF is about to carry.

    The engine matches vehicle dummies by name exactly once, at load time
    (CClumpModelInfo::SetFrameIds), and CVehicleModelInfo::GetWheelPosn then
    dereferences the frame it finds with no null check — so a wheel dummy
    that is absent, or carries Blender's ``.001`` suffix, crashes the game
    instead of just looking wrong.

    Returns ``(fatal, warnings)``; both empty for anything that is not a
    vehicle, so map models and peds pass straight through.
    """
    names = [f.name for f in clump.frames if f.name]
    if not any('wheel' in n.lower() for n in names):
        return [], []

    from .frame_hierarchy import check_vehicle_names
    return check_vehicle_names(names)


def _audit_skin(clump):
    """Check a skinned (ped) clump against what the engine dereferences.

    ``core.skin_lint.check_skin_clump`` mirrors CPedModelInfo::SetClump and
    the skin/HAnim readers: a missing node table, an unskinned last atomic,
    a bone count ≠ node count, a missing hard-coded bone id and so on crash
    the game at load or spawn instead of just looking wrong.

    Returns ``(fatal, warnings)``; both empty for anything without a skin,
    so map models and vehicles pass straight through.
    """
    if not any(g.skin is not None for g in clump.geometries):
        return [], []
    from ..core.skin_lint import check_skin_clump
    return check_skin_clump(clump)


def _audit_map(clump, model_name: str = ''):
    """Check a non-skinned (map / object) clump against what the engine
    dereferences when it streams it.

    ``core.mapdff_lint.check_map_clump`` mirrors RpClumpStreamRead, the
    geometry / material / 2dfx / night-colour / breakable plugin readers
    and CAtomicModelInfo::SetAtomic: a bad frame or material index, a
    texture name the TXD cannot hold, a 2dfx type the reader cannot skip,
    a light with a shadow but no texture and so on crash the game or
    leave the model invisible instead of just looking wrong.

    Returns ``(fatal, warnings)``; both empty for skinned clumps (peds),
    which ``_audit_skin`` covers. Vehicles and weapons go through the
    same checks minus the objs/tobj-only rules (DFF-27/28/29/46) —
    CVehicleModelInfo / CWeaponModelInfo keep every atomic and own the
    ``_dam`` slot, so those would be false alarms (vanilla infernus.dff:
    9, landstal.dff: 26).
    """
    if any(g.skin is not None for g in clump.geometries):
        return [], []
    from ..core.mapdff_lint import check_map_clump
    return check_map_clump(clump, model_name=model_name,
                           is_vehicle=_is_vehicle_or_weapon(clump))


def _is_vehicle_or_weapon(clump) -> bool:
    """Vehicle / weapon clump: an embedded COL (only vehicles carry one)
    or the frame names the engine looks up by name (wheel_*, chassis,
    gunflash)."""
    if clump.collision_data:
        return True
    names = [(f.name or '').lower() for f in clump.frames]
    return any(k in n for n in names for k in ('wheel', 'chassis', 'gunflash'))


def export_dff(filepath: str, objects, version: int = GTA_SA_VERSION,
               target_platform: str = 'PC'):
    """
    Export Blender objects as a DFF file.

    Args:
        filepath: Output .dff file path.
        objects: Iterable of Blender objects (MESH, EMPTY, ARMATURE).
        version: RenderWare version. Default GTA SA (0x36003).
        target_platform: 'PC' (default) or 'MOBILE'. Mobile flips each
            geometry's is_native_ogl flag so the writer emits Native
            Data PLG (War Drum OpenGL) instead of inline Struct verts.
    """
    model_name = os.path.splitext(os.path.basename(filepath))[0]
    clump = build_dff_clump(objects, version=version, col_model_name=model_name)
    if target_platform == 'MOBILE':
        for g in clump.geometries:
            # Round-tripped non-OGL natives keep their own raw bytes —
            # don't overwrite those by setting is_native_ogl.
            if not g.raw_native_data_plg:
                g.is_native_ogl = True
        clump.is_mobile = True

    # Audit before writing, surface after: ``write_dff_file`` clears
    # DFF_EXPORT_WARNINGS on its way in, so anything appended earlier is lost.
    #
    # Пост-экспортный аудит модели (проверка на краши/баги в игре) гоняется
    # на КАЖДУЮ модель — при массовом экспорте (тысячи моделей) это заметно
    # замедляет. Настройка сцены gtatools_audit_on_export по умолчанию ВЫКЛ
    # (быстрый экспорт); включить галку в панели экспорта для разовой проверки.
    # Батч-скрипты без сцены → аудит тоже выключен.
    _do_audit = False
    try:
        import bpy as _bpy
        _do_audit = bool(getattr(_bpy.context.scene.inu_settings,
                                 'gtatools_audit_on_export', False))
    except Exception:                                  # noqa: BLE001
        _do_audit = False
    if _do_audit:
        veh_fatal, veh_warn = _audit_vehicle_frames(clump)
        skin_fatal, skin_warn = _audit_skin(clump)
        map_fatal, map_warn = _audit_map(clump, model_name)
    else:
        veh_fatal = veh_warn = skin_fatal = skin_warn = []
        map_fatal = map_warn = []
    for item in veh_fatal:
        print(f"[DFF Export] ИГРА УПАДЁТ: нет дамми {item}")
    for item in veh_warn:
        print(f"[DFF Export] дамми машины: {item}")
    for item in skin_fatal:
        print(f"[DFF Export] ИГРА УПАДЁТ: скин: {item}")
    for item in skin_warn:
        print(f"[DFF Export] скин: {item}")
    for item in map_fatal:
        print(f"[DFF Export] ИГРА УПАДЁТ: модель: {item}")
    for item in map_warn:
        print(f"[DFF Export] модель: {item}")

    write_dff_file(filepath, clump)

    if veh_fatal or veh_warn or skin_fatal or skin_warn or map_fatal or map_warn:
        from .. import T
        from ..core.dff import DFF_EXPORT_WARNINGS
        for item in veh_fatal:
            DFF_EXPORT_WARNINGS.append(f"{T('Игра упадёт — нет дамми')}: {item}")
        for item in veh_warn:
            DFF_EXPORT_WARNINGS.append(f"{T('Дамми машины')}: {item}")
        for item in skin_fatal:
            DFF_EXPORT_WARNINGS.append(f"{T('Игра упадёт — скин')}: {item}")
        for item in skin_warn:
            DFF_EXPORT_WARNINGS.append(f"{T('Скин')}: {item}")
        for item in map_fatal:
            DFF_EXPORT_WARNINGS.append(f"{T('Игра упадёт — модель')}: {item}")
        for item in map_warn:
            DFF_EXPORT_WARNINGS.append(f"{T('Модель')}: {item}")

    return veh_fatal, veh_warn + skin_warn + map_warn, skin_fatal + map_fatal


def draw_export_game_rows(layout, context):
    """Ряды выбора игры/платформы БЕЗ своего бокса — рисует прямо в
    переданный layout. Нужно, чтобы главный диалог мог положить их в
    один бокс вместе с форматами экспорта."""
    from .. import T
    scn = context.scene
    layout.label(text=T("Экспорт в игру:"))
    # Слитый блок: два ГОРИЗОНТАЛЬНЫХ ряда кнопок вплотную (row внутри
    # column(align) — иначе expand на enum раскрывает кнопки вертикально).
    col = layout.column(align=True)
    col.row(align=True).prop(scn.inu_settings, "gtatools_platform", expand=True)  # PC | Mobile
    col.row(align=True).prop(scn.inu_settings, "gtatools_game", expand=True)      # SA | VC | III


def draw_export_game_block(layout, context):
    """Целевая игра/платформа экспорта в отдельном боксе (для диалогов,
    где нет блока форматов). Пишет RW-версию (III 3.3 / VC 3.4 / SA 3.6)
    и колонки IPL/IDE. По умолчанию = игра проекта (её ставит авто-детект
    при импорте), здесь можно переопределить перед экспортом."""
    draw_export_game_rows(layout.box(), context)


def draw_dff_flags_block(layout, context):
    """Reusable Pipeline-buttons + DFF-flags-column block.

    Mirrors the N-panel DFF Flags section 1:1 (panels.py): pipeline as
    expanded scene-level buttons, then the active object's obj.inu.*
    flags in a single column with per-pipeline red-alert hinting on
    forbidden flags.  Shared by every DFF export dialog (single Export
    DFF, Export All, INU Export All) so the look + behaviour is
    identical everywhere.  Edits propagate to all selected + persist
    per-pipeline through the props' own update callbacks.
    """
    from .. import T
    scn = context.scene

    layout.label(text=T("Pipeline:"))
    row = layout.row(align=True)
    row.prop(scn.inu_settings, "gtatools_export_pipeline", expand=True)

    # Global toggle — write per-vertex alpha into the DFF. Off forces
    # fully-opaque (255) so stray/unpainted vertex alpha never leaks in.
    layout.prop(scn.inu_settings, "gtatools_export_vertex_alpha")

    # В контексте файлового браузера context.active_object бывает None —
    # берём активный объект из view_layer (работает во всех областях),
    # иначе блок DFF-флагов «пропадал» при открытом диалоге экспорта.
    ao = context.active_object
    if ao is None:
        vl = getattr(context, 'view_layer', None)
        ao = getattr(getattr(vl, 'objects', None), 'active', None)
    if ao is None or ao.type != 'MESH' or not hasattr(ao, 'inu'):
        layout.label(text=T("Выдели меш-объект для DFF-флагов"))
        return
    inu = ao.inu
    from ..core import game_versions as _gv
    _is_sa = (_gv.game_of_scene(scn) == 'SA')
    pipeline = scn.inu_settings.gtatools_export_pipeline
    _PIPE_FORBIDDEN = {
        '0x53F2009A': {'day_cols', 'night_cols', 'light_beam_asi'},
        '0x53F20098': {'uv_map2', 'light', 'export_normals',
                       'set_material_alpha', 'light_beam_asi'},
        '0x53F2009C': {'night_cols', 'uv_map2', 'light_beam_asi'},
        'PED': {'day_cols', 'night_cols', 'modulate_color',
                'set_material_alpha', 'light_beam_asi', 'uv_map2'},
    }.get(pipeline, set())

    box = layout.box()
    box.label(text=T("DFF Flags (активный объект, из N-панели):"))
    fc = box.column(align=True)

    def _flag(prop_key, label):
        r = fc.row(align=True)
        if prop_key in _PIPE_FORBIDDEN:
            r.alert = True
        r.prop(inu, prop_key, text=label)

    _flag("export_normals",    "Normals")
    _flag("light",             "Light")
    _flag("modulate_color",    "Modulate Color")
    _flag("set_material_alpha", "Set Material Alpha")
    if _is_sa:
        _flag("light_beam_asi", "Light Beam (SA_Light.asi)")
    # 'export_binsplit' (Bin Mesh PLG) намеренно скрыт из UI — см. коммент
    # у его BoolProperty в __init__.py. Дефолт True; отключение делало
    # модель невидимой в игре.
    _flag("uv_map1", "UV1")
    _flag("uv_map2", "UV2")
    _flag("day_cols", "Day")
    if _is_sa:
        # Night vertex colors kill UV animation in retail SA — mirror the
        # N-panel: red-alert the Night row and spell out why when the active
        # mesh carries a UV-anim material (this warning was missing from the
        # export dialog, only shown in the N-panel).
        from ..ui.panels import _obj_has_uv_anim_material
        _uv_anim = _obj_has_uv_anim_material(ao)
        r = fc.row(align=True)
        if 'night_cols' in _PIPE_FORBIDDEN or (_uv_anim and inu.night_cols):
            r.alert = True
        r.prop(inu, "night_cols", text="Night")
        if _uv_anim and inu.night_cols:
            warn = fc.column(align=True)
            warn.alert = True
            warn.label(text=T("Night ломает UV-анимацию в retail SA"),
                       icon='ERROR')
            warn.label(text=T("Сними Night (ночные vcol) на UV-аним модели"),
                       icon='BLANK1')


# ──────────────────── Blender operator wrapper ────────────────────────

class GTATOOLS_OT_export_dff(bpy.types.Operator, ExportHelper):
    """Экспортировать DFF модель"""
    bl_idname = "gtatools.export_dff"
    bl_label = "INU: Export DFF"
    bl_options = {'PRESET'}
    filename_ext = ".dff"
    filter_glob: StringProperty(default="*.dff", options={'HIDDEN'})

    def draw(self, context):
        # File-browser sidebar: target game/platform at the very top, then
        # the same Pipeline buttons + DFF flags column as the N-panel, so
        # everything can be tweaked at the moment of export.
        col = self.layout.column(align=True)   # вплотную, без зазоров браузера
        draw_export_game_block(col, context)
        draw_dff_flags_block(col, context)

    def execute(self, context):
        from ..tools.prelight import setup_prelight_preview
        try:
            # Remember which objects had prelight preview on (Prelight_Mix node)
            # so we can disable for export and restore the visual after.
            prelight_was_on = []
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

            # Auto-include hierarchy: walk parents and children of selection
            # so the DFF clump frame chain is preserved (dummies + meshes).
            def _inu_type(o):
                return getattr(getattr(o, 'inu', None), 'type', 'OBJ')

            def _is_exportable(o):
                if o.type == 'MESH':
                    return _inu_type(o) != 'NON'
                if o.type == 'EMPTY':
                    return _inu_type(o) in ('OBJ', '2DFX')
                return False

            selected = [o for o in context.selected_objects if _is_exportable(o)]
            dff_objects = list(selected)
            seen = set(dff_objects)

            for o in list(selected):
                p = o.parent
                while p is not None and p not in seen:
                    if p.type == 'EMPTY' and _inu_type(p) == 'OBJ':
                        dff_objects.append(p)
                        seen.add(p)
                    p = p.parent

            def _walk_children(o):
                for c in o.children:
                    if c in seen or not _is_exportable(c):
                        continue
                    dff_objects.append(c)
                    seen.add(c)
                    _walk_children(c)
            for o in list(selected):
                _walk_children(o)

            print(f"[DFF Export] selector: selected={len(selected)}, total={len(dff_objects)} objects → {self.filepath}")
            for o in dff_objects[:20]:
                print(f"  - {o.name} ({o.type})")
            target_platform = getattr(context.scene.inu_settings,
                                      'gtatools_platform', 'PC')
            veh_fatal, _veh_warn, model_fatal = export_dff(
                filepath=self.filepath, objects=dff_objects,
                version=_resolve_export_version(context),
                target_platform=target_platform)

            for obj in prelight_was_on:
                setup_prelight_preview(obj, enable=True)

            # Surface non-fatal validation warnings (e.g. very high
            # triangle count) — export already succeeded.
            from ..core.dff import DFF_EXPORT_WARNINGS
            if DFF_EXPORT_WARNINGS:
                for w in DFF_EXPORT_WARNINGS:
                    self.report({'WARNING'}, w)
            if veh_fatal:
                # A missing wheel dummy is not cosmetic: the game faults on
                # it. Red, and named, so it is not lost among the warnings.
                from .. import T
                self.report(
                    {'ERROR'},
                    f"{T('Игра упадёт — нет дамми')}: "
                    f"{', '.join(f.split(' — ')[0] for f in veh_fatal)}")
            if model_fatal:
                # Same weight as a missing wheel: the engine dereferences
                # these at load / spawn (skin audit for peds, map audit for
                # everything else). One line per finding — each names the
                # geometry, bone or effect to fix.
                from .. import T
                for item in model_fatal:
                    self.report({'ERROR'}, f"{T('Игра упадёт')}: {item}")
            self.report({'INFO'}, f"Exported DFF: {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            for obj in prelight_was_on:
                try:
                    setup_prelight_preview(obj, enable=True)
                except Exception:
                    # Cleanup runs inside the export's error handler — a
                    # failure here must not mask the real error below.
                    pass
            self.report({'ERROR'}, f"DFF export error: {str(e)}")
            return {'CANCELLED'}


