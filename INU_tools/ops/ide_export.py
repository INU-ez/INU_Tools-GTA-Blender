"""Export Blender objects → IDE file (object definitions)."""

from __future__ import annotations
from ..core.ide import IdeFile, IdeObject, IdeFx2dfx, write_ide


def _scene_game() -> str:
    """Read the active game (III/VC/SA) off the current Blender scene.
    Falls back to SA when bpy isn't available (unit tests)."""
    try:
        import bpy
        from ..core import game_versions as gv
        return gv.game_of_scene(bpy.context.scene)
    except Exception:
        return 'SA'


def _collect_2dfx_for_ide(objects, model_id_by_obj):
    """Walk scene 2DFX Empties and convert them to IdeFx2dfx entries
    for III/VC IDEs (where effects live in IDE, not DFF).

    For each Empty marked ``inu.type == '2DFX'``:
      * The parent mesh object's ``inu.model_id`` becomes the entry's
        target ID — engine attaches the effect to that model.
      * Position is taken in world space (relative to mesh origin
        would conflict with IDE-driven placement; IDE 2DFX positions
        are absolute on the model's local origin).
      * Type-specific fields collapse into ``type_params`` strings
        matching the verified per-type column layout from
        gtamods.com/wiki/2DFX.

    SA flow uses ``_collect_2dfx`` in dff_export.py to write the same
    data into the DFF chunk; III/VC use this function to put it in
    IDE instead. SA can also have Type 5 (special) in IDE but we
    don't emit those yet.
    """
    out = []
    for obj in objects:
        if obj.type != 'EMPTY':
            continue
        inu = getattr(obj, 'inu', None)
        if not inu or getattr(inu, 'type', '') != '2DFX':
            continue

        # Resolve target model_id from the parent (mesh) object — IDE
        # 2DFX entries are keyed by the DFF they attach to.
        parent = obj.parent
        if parent is None:
            continue
        target_mid = model_id_by_obj.get(id(parent), 0)
        if not target_mid:
            continue

        effect_type = getattr(inu, 'effect_2dfx', '')

        # Position: 2DFX is local to the mesh's origin per RW
        # convention. obj.location already encodes that when the
        # Empty is parented to the mesh.
        px, py, pz = obj.location.x, obj.location.y, obj.location.z

        # RGBA color → r/g/b ints (alpha goes into the "unknown"
        # slot which is read as opacity-ish in vanilla parsers).
        c = getattr(inu, 'color_2dfx', (1.0, 1.0, 1.0, 1.0))
        r, g, b, a = (int(c[0] * 255), int(c[1] * 255),
                       int(c[2] * 255), int(c[3] * 255))

        # If this Empty was materialised from an imported IDE 2dfx
        # entry, it carries the original ``type_params`` verbatim —
        # re-emit those for byte-identical round-trip instead of
        # re-deriving from per-prop Blender values (which may be
        # lossy for type-specific fields the UI doesn't expose).
        stashed_params = obj.get('ide_2dfx_params')
        stashed_type_id = obj.get('ide_2dfx_type_id')
        stashed_unknown = obj.get('ide_2dfx_unknown')
        if stashed_params is not None and stashed_type_id is not None:
            out.append(IdeFx2dfx(
                model_id=target_mid,
                pos_x=px, pos_y=py, pos_z=pz,
                r=r, g=g, b=b,
                unknown=int(stashed_unknown) if stashed_unknown is not None else a,
                type_id=int(stashed_type_id),
                type_params=[str(p) for p in stashed_params],
            ))
            continue

        if effect_type == 'LIGHT':
            # Type 0 Light. 11 type_params per gtamods spec:
            # corona_tex, shadow_tex, distance, outer_range, size,
            # inner_range, shadow_intensity, flash, wet, flare, flags.
            params = [
                f'"{inu.corona_tex_2dfx or "coronastar"}"',
                f'"{inu.shadow_tex_2dfx or "shad_exp"}"',
                str(obj.get('2dfx_corona_far_clip', 100.0)),
                str(obj.get('2dfx_pointlight_range', 200.0)),
                str(getattr(inu, 'corona_size_2dfx', 0.5)),
                str(getattr(inu, 'shadow_size_2dfx', 50.0)),
                str(obj.get('2dfx_shadow_color_multiplier', 255)),
                str(int(getattr(inu, 'show_mode_2dfx', '0') or 0)),
                str(obj.get('2dfx_wet', 0)),
                str(int(getattr(inu, 'flare_type_2dfx', '0') or 0)),
                str(obj.get('2dfx_flags1', 0)),
            ]
            out.append(IdeFx2dfx(
                model_id=target_mid,
                pos_x=px, pos_y=py, pos_z=pz,
                r=r, g=g, b=b, unknown=a,
                type_id=0,
                type_params=params,
            ))

        elif effect_type == 'PARTICLE':
            # Type 1 Particle. 5 type_params: particle, strX, strY,
            # strZ, scale. Lots of vanilla entries use 0s except for
            # particle name + scale.
            params = [
                f'"{obj.get("2dfx_effect_name", "smoke")}"',
                str(obj.get('2dfx_strength_x', 0.0)),
                str(obj.get('2dfx_strength_y', 0.0)),
                str(obj.get('2dfx_strength_z', 0.0)),
                str(obj.get('2dfx_particle_scale', 1.0)),
            ]
            out.append(IdeFx2dfx(
                model_id=target_mid,
                pos_x=px, pos_y=py, pos_z=pz,
                r=r, g=g, b=b, unknown=a,
                type_id=1,
                type_params=params,
            ))

        # Other types (PedAttractor=3, SunGlare=4, etc.) — VC adds 3
        # and 4 but their type_params layout differs and few users
        # mod them. Skipped for now; revisit if asked.

    return out


def export_ide(filepath: str, objects: list) -> None:
    """
    Generate an IDE file from selected Blender objects.

    Each mesh object produces one ``objs`` entry.
    Properties are read from ``obj.inu`` (model_id, txd_name, draw_distance, ide_flags).
    Model name defaults to the object name (without _COL/_LOD suffixes).
    """
    ide = IdeFile()
    seen_models: set[str] = set()
    # Build lookup so the 2DFX collector below can resolve the target
    # model_id of each Empty's parent without re-walking the mesh list.
    _model_id_by_obj_id: dict[int, int] = {}

    from ..tools.model_utils import get_model_type
    hd_of = None
    for obj in objects:
        if obj.type != 'MESH':
            continue

        mt, base = get_model_type(obj)
        # Collision has NO objs entry — it's bound to its DFF by name.
        if mt == 'COL':
            continue

        inu = getattr(obj, 'inu', None)

        # Model name. A LOD gets its own name — the one it was imported /
        # written with (tatar_str_1LOD), else LOD<base>; in III/VC the game's
        # rule for its model (map_link.lod_model_name, as Add to IDE and the
        # exported .dff) — so it gets its own entry instead of deduping with
        # the DFF; everything else uses the clean base name.
        if mt == 'LOD':
            from .map_link import lod_hd_names, lod_model_name
            if hd_of is None:
                hd_of = lod_hd_names(objects)
            model_name = lod_model_name(obj, base, hd=hd_of.get(id(obj), ''),
                                        game=_scene_game())
        else:
            model_name = _clean_model_name(obj.name)

        # Skip duplicate model names (instances like gta_bench.001, .002)
        if model_name in seen_models:
            continue
        seen_models.add(model_name)

        model_id = getattr(inu, 'model_id', 0) if inu else 0
        txd_name = getattr(inu, 'txd_name', '') if inu else ''
        if not txd_name:
            if mt == 'LOD':
                # LOD делит TXD с основной моделью: аддон пишет {base}.txd и
                # никогда не создаёт LOD<base>.txd — fallback на имя модели
                # дал бы несуществующий архив (LOD без текстур в игре).
                # Add-to-IDE (ide_ipl.py) так же берёт TXD парного DFF.
                txd_name = base
            else:
                txd_name = model_name  # default: same as model name

        from .map_link import ide_draw_distance
        draw_distance = ide_draw_distance(obj, mt == 'LOD')
        flags = getattr(inu, 'ide_flags', 0) if inu else 0

        # Translate flags when the per-object source game differs from
        # the scene's target. Same-game (or unknown source) → pass
        # through. See core.ide_flag_translate for the bit↔category
        # table (verified against gtamods.com/wiki/Item_Definition).
        target_game = _scene_game()
        source_game = (getattr(inu, 'ide_flags_source_game', '')
                       if inu else '') or ''
        if source_game and source_game != target_game:
            from ..core.ide_flag_translate import translate_flags
            flags = translate_flags(flags, source_game, target_game)

        ide.objects.append(IdeObject(
            model_id=model_id,
            model_name=model_name,
            txd_name=txd_name,
            draw_distance=draw_distance,
            flags=flags,
        ))
        _model_id_by_obj_id[id(obj)] = model_id

    # 2DFX → IDE for III/VC. SA stores effects in DFF chunks via
    # _collect_2dfx in dff_export.py, so we skip IDE 2dfx population
    # for SA — vanilla SA IDEs have an empty 2dfx section, write_ide
    # already emits that.
    if _scene_game() in ('III', 'VC'):
        ide.fx_2dfx = _collect_2dfx_for_ide(objects, _model_id_by_obj_id)

    write_ide(filepath, ide, game=_scene_game())


def _clean_model_name(name: str) -> str:
    """Remove Blender duplicate suffixes (.001) and model suffixes/prefixes."""
    from ..tools.model_utils import get_model_type
    # Strip Blender duplicate suffix FIRST (before suffix matching)
    if '.' in name:
        b, s = name.rsplit('.', 1)
        if s.isdigit():
            name = b
    class _Mock:
        def __init__(self, n):
            self.name = n
    _, base = get_model_type(_Mock(name))
    return base
