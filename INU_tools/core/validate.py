"""Pure check functions for the pre-export Validate Scene sweep.

Lives in core/ (not ops/) so it stays bpy-free and unit-testable. The
operators and panel in ops/validate_scene.py wrap these with bpy.data
adapters, but the actual rules — when an issue is reported and what
message it carries — are defined here.

Strings are stored in Russian; translation happens at display time via
the panel's T() wrapper, so changing locale at runtime works as
expected (and so this module remains importable in pytest where T()
is unavailable).
"""

from __future__ import annotations


def _issue(severity, category, message,
           target_kind='', target_name='',
           fix_op_id='', fix_arg='',
           args=None):
    """Build a single issue dict.

    Severity is 'ERROR' | 'WARNING' | 'INFO'. target_kind labels the
    follow-up navigation: 'OBJECT' / 'MATERIAL' / 'ACTION' / ''. fix_op_id
    is the bpy operator idname that can fix the issue (empty if none),
    and fix_arg is the single string argument that operator takes.

    ``message`` may contain ``{key}`` placeholders. When ``args`` is
    provided, the message is treated as a translation template — the
    placeholders are kept verbatim in ``message_template`` (so the
    panel can look up a translated copy and format it at draw time)
    and a fully-rendered string is also written into ``message`` for
    legacy display paths and tests. Without ``args`` both
    ``message_template`` and ``message_args`` are empty and panels
    display ``message`` directly.
    """
    import json
    if args:
        message_template = message
        try:
            rendered = message.format(**args)
        except (KeyError, IndexError):
            rendered = message
        message_args = json.dumps(args, ensure_ascii=False)
    else:
        message_template = ''
        rendered = message
        message_args = ''
    return dict(
        severity=severity,
        category=category,
        message=rendered,
        message_template=message_template,
        message_args=message_args,
        target_kind=target_kind,
        target_name=target_name,
        fix_op_id=fix_op_id,
        fix_arg=fix_arg,
    )


def check_paintjobs(materials):
    """Half-filled paintjob slots and slots without a base texture.

    Args:
        materials: iterable of dicts with keys
            name (str), alt1 (bool), alt2 (bool), has_base (bool)
    """
    out = []
    for m in materials:
        if not (m['alt1'] or m['alt2']):
            continue
        if not m['alt1']:
            out.append(_issue(
                'WARNING', 'Paintjob',
                'заполнен только Paintjob 2 — нужны оба',
                'MATERIAL', m['name']))
        elif not m['alt2']:
            out.append(_issue(
                'WARNING', 'Paintjob',
                'заполнен только Paintjob 1 — нужны оба',
                'MATERIAL', m['name']))
        elif not m['has_base']:
            out.append(_issue(
                'WARNING', 'Paintjob',
                'нет основной текстуры — paintjob не к чему привязать',
                'MATERIAL', m['name']))
    return out


def check_quaternions(actions, eps=1e-3):
    """Find Actions with non-unit quaternion keyframes.

    Severity is INFO, not WARNING — the IFP exporter normalises every
    quat on the fly (ifp_export.py uses ``bl_quat.normalize()`` per
    keyframe), so dirty Action data does NOT corrupt the .ifp file.
    The check exists for two side-effects:

      • viewport preview between non-unit quats interpolates wonky
      • the source Action stays dirty if shared / saved / re-used

    Args:
        actions: iterable of dicts with keys
            name (str)
            quat_groups (list[list[float]]): each inner list is the
                4-tuple (w, x, y, z) values at one keyframe. Caller
                assembles these from fcurve data.
    """
    out = []
    for action in actions:
        bad = 0
        for mags in action.get('quat_groups', ()):
            if len(mags) != 4:
                continue
            w, x, y, z = mags
            length = (w * w + x * x + y * y + z * z) ** 0.5
            if abs(length - 1.0) > eps:
                bad += 1
        if bad:
            out.append(_issue(
                'INFO', 'Quaternions',
                "{count} ненормированных ключей (экспорт чинит сам, "
                "но preview прыгает)",
                'ACTION', action['name'],
                fix_op_id='gtatools.validate_fix_quaternions',
                fix_arg=action['name'],
                args={'count': bad}))
    return out


def check_uv_anim_night_vcols(meshes):
    """MESH objects that carry BOTH a UV-animated material AND night
    vertex colors (Night flag on, or a Night colour attribute).

    Night vertex colors silently disable UV animation in retail
    gtasa.exe — confirmed in-game and documented in the ponz2009 SA
    tips. librw/euryopa ignore night vcols so the anim plays there,
    which makes it look like a DFF-format bug when it isn't. Dropping
    the night layer (or the Night flag) restores the animation.

    Args:
        meshes: iterable of dicts with keys
            name (str), has_uv_anim (bool),
            night_flag (bool), has_night_vcol (bool)
    """
    out = []
    for m in meshes:
        if not m.get('has_uv_anim'):
            continue
        if not (m.get('night_flag') or m.get('has_night_vcol')):
            continue
        out.append(_issue(
            'WARNING', 'UVAnimNightVcol',
            'Ночные vertex colors (Night) отключают UV-анимацию в '
            'retail SA — сними Night на этой модели',
            'OBJECT', m['name']))
    return out


def check_orphan_models(models):
    """Detect LOD/COL atomics whose base name has no main DFF in the
    scene. The engine pairs LOD/COL with a main mesh by base name —
    orphans are silently dropped at load.

    Args:
        models: iterable of dicts with keys
            name (str), type (str: 'DFF'|'LOD'|'COL'), base (str)
            The caller is responsible for stripping suffix/prefix
            via tools.model_utils.get_model_type — this check is
            naming-agnostic.
    """
    bases = {}
    for m in models:
        b = m['base'].lower()
        bases.setdefault(b, {})[m['type']] = m['name']

    out = []
    for base, by_type in bases.items():
        if 'LOD' in by_type and 'DFF' not in by_type:
            out.append(_issue(
                'WARNING', 'OrphanModel',
                'LOD без main DFF — engine не сможет переключиться '
                'между ближним и дальним LOD',
                'OBJECT', by_type['LOD']))
        if 'COL' in by_type and 'DFF' not in by_type:
            out.append(_issue(
                'WARNING', 'OrphanModel',
                'COL без main DFF — коллизия не привязана к модели',
                'OBJECT', by_type['COL']))
    return out


def check_untextured_col(models):
    """Warn about meshes classified COL ONLY by the no-texture heuristic
    (no ``inu.type`` tag, no name marker). Plain-coloured models are legal
    in GTA SA, but a heuristic-COL mesh silently skips DFF/IDE/IPL export —
    the model vanishes from the game with no error. The user should either
    add a texture (making it a DFF) or tag it COL explicitly.

    Args:
        models: iterable of dicts as in check_orphan_models, plus the
            optional key ``heuristic_col`` (bool) set by the gatherer.
    """
    out = []
    for m in models:
        if m.get('heuristic_col'):
            out.append(_issue(
                'WARNING', 'UntexturedModel',
                'Меш без текстур определён как COL — он не попадёт в '
                'DFF/IDE/IPL экспорт. Добавь текстуру или пометь тип '
                'COL явно',
                'OBJECT', m['name']))
    return out


def check_orphan_2dfx(fx_empties):
    """Detect 2DFX Empty objects that aren't parented to a MESH.
    The DFF exporter writes 2DFX entries as children of the parent
    mesh's atomic — without a MESH parent, the 2DFX never makes it
    into the .dff at all.

    Args:
        fx_empties: iterable of dicts with keys
            name (str), parent_kind (str: 'MESH'|'EMPTY'|'ARMATURE'|None)
    """
    out = []
    for fx in fx_empties:
        pk = fx.get('parent_kind')
        if pk == 'MESH':
            continue
        descr = pk if pk else 'нет родителя'
        out.append(_issue(
            'WARNING', 'Orphan2DFX',
            '2DFX не привязан к MESH (parent: {parent}) — не попадёт в DFF',
            'OBJECT', fx['name'],
            args={'parent': descr}))
    return out


def _strip_blender_dup_suffix(name):
    """Strip Blender's automatic ``.NNN`` (3-digit) duplicate suffix.

    ``body.001`` → ``body``; ``body`` → ``body``; ``foo.something`` →
    ``foo.something`` (not stripped — only the exact .NNN form is
    Blender's dup tag, longer/shorter tails belong to the user).
    """
    if len(name) < 4:
        return name
    if name[-4] != '.':
        return name
    if not name[-3:].isdigit():
        return name
    return name[:-4]


def check_duplicate_model_ids(objects):
    """Two DIFFERENT objects sharing the same non-zero ``inu.model_id``
    collide in the IDE — the second one overwrites the first at game
    load.

    Blender's ``Shift+D`` Shift+D copies inherit ``inu.model_id`` from the
    source by design (Map Export wants both instances pointing at the
    same DFF), and rename the copy to ``name.001``. We strip that exact
    suffix before comparing — so ``body`` + ``body.001`` are treated
    as one logical model, not as a collision.

    Args:
        objects: iterable of dicts with keys
            name (str), model_id (int)
            Objects with model_id == 0 are ignored (auto-assign).
    """
    by_id = {}
    for obj in objects:
        mid = obj.get('model_id') or 0
        if mid == 0:
            continue
        by_id.setdefault(mid, []).append(obj['name'])

    out = []
    for mid, names in by_id.items():
        if len(names) < 2:
            continue
        # Reduce each name to its dup-stripped base; one entry per
        # distinct base. ``body`` + ``body.001`` collapse to {body}.
        # Pick the shortest name as the representative so messages
        # show ``body`` rather than ``body.001`` if both exist.
        bases: "dict[str, str]" = {}
        for n in names:
            base = _strip_blender_dup_suffix(n).lower()
            existing = bases.get(base)
            if existing is None or len(n) < len(existing):
                bases[base] = n
        if len(bases) < 2:
            continue  # all duplicates of one logical object — not a collision
        reps = sorted(bases.values())
        out.append(_issue(
            'ERROR', 'DuplicateID',
            "model_id={mid} занят {count} разными моделями: {names}",
            'OBJECT', reps[0],
            args={'mid': mid,
                  'count': len(bases),
                  'names': ', '.join(reps)}))
    return out


def check_empty_meshes(meshes):
    """Meshes with 0 vertices — leftovers from Decimate / split / join,
    they still get listed in the export pipeline and produce empty
    atomics that the engine may or may not gracefully skip.

    Args:
        meshes: iterable of dicts with keys name (str), vert_count (int)
    """
    out = []
    for m in meshes:
        if m['vert_count'] == 0:
            out.append(_issue(
                'WARNING', 'EmptyMesh',
                'меш с 0 вершин — экспортируется как пустой атомик',
                'OBJECT', m['name']))
    return out


# Hard cap on a single DFF atomic is 65 535 vertices (uint16 indices).
# We warn at 32k as a soft signal that the user is approaching the
# limit — by the time you cross 65 535 the export will silently truncate
# or fail, and there's nothing to fix automatically.
LARGE_MESH_SOFT_LIMIT = 32000


def check_large_meshes(meshes, threshold=LARGE_MESH_SOFT_LIMIT):
    """Meshes approaching the 65 535-vert atomic limit.

    Args:
        meshes: iterable of dicts with keys name (str), vert_count (int)
        threshold: report meshes strictly above this count.
    """
    out = []
    for m in meshes:
        if m['vert_count'] > threshold:
            out.append(_issue(
                'INFO', 'LargeMesh',
                "{count} вершин — лимит атомика 65535, "
                "возможно стоит разрезать",
                'OBJECT', m['name'],
                args={'count': m['vert_count']}))
    return out


def check_materials_without_texture(materials):
    """Materials assigned to at least one MESH but without an image
    texture in their node tree. Most pipelines (default, vehicle,
    building DN) expect a base texture to multiply against vertex
    colors; without one the engine renders flat-coloured / white.

    COL surface materials are flag-only by design (surface type, sound,
    day/night light) and skip the texture requirement — the adapter
    sets ``is_col_surface=True`` and we short-circuit here.

    Args:
        materials: iterable of dicts with keys
            name (str), has_base (bool), used_on_mesh (bool),
            is_col_surface (bool, optional)
    """
    out = []
    for m in materials:
        if not m.get('used_on_mesh'):
            continue  # unused materials are someone else's problem
        if m.get('is_col_surface'):
            continue  # COL surface — never has texture, by design
        if not m['has_base']:
            out.append(_issue(
                'WARNING', 'NoTexture',
                'материал без image texture — pipeline скорее всего '
                'ожидает базовую',
                'MATERIAL', m['name']))
    return out


def check_loose_geom(meshes):
    """Висящие вершины/рёбра (как кнопка «Проверка вершин»). При экспорте
    такая геометрия даёт мусор/пропадает — GTA-модель должна быть чистой.

    Args:
        meshes: iterable of dicts with keys name (str), n_verts (int),
            n_edges (int) — счётчики висящих вершин/рёбер объекта.
    """
    out = []
    for m in meshes:
        nv = int(m.get('n_verts', 0) or 0)
        ne = int(m.get('n_edges', 0) or 0)
        if not (nv or ne):
            continue
        out.append(_issue(
            'WARNING', 'LooseGeometry',
            'Висящая геометрия: вершин {v}, рёбер {e} — почисти меш '
            '(«Проверка вершин» их выделит)',
            'OBJECT', m['name'], args={'v': nv, 'e': ne}))
    return out


def check_non_ascii_names(names):
    """Имена с не-ASCII символами (кириллица и т.п.). GTA SA принимает в
    именах моделей (DFF/IDE/IPL/TXD) только латиницу/цифры/подчёркивание —
    русское имя не запишется корректно и модель не найдётся в игре.

    Args:
        names: iterable of object names (str).
    """
    out = []
    for name in names:
        try:
            name.encode('ascii')
            continue
        except (UnicodeEncodeError, AttributeError):
            pass
        out.append(_issue(
            'WARNING', 'NonAsciiName',
            'Имя содержит не-латинские символы (напр. кириллицу) — GTA SA '
            'не примет. Переименуй латиницей (a-z, 0-9, _)',
            'OBJECT', name))
    return out


def check_extra_color_attrs(meshes):
    """Лишние цветовые атрибуты (не Day/Night) на мешах.

    GTA использует только два prelit-слоя вершинного цвета — Day и Night.
    Любой другой цветовой атрибут (col1, Attribute, Col и т.п.) в игру не
    идёт, зато сбивает превью альфы вершин (оно ищет альфу < 255 в ЛЮБОМ
    цветовом атрибуте) и путает экспорт. Такие атрибуты стоит удалить.

    Args:
        meshes: iterable of dict(name, extra=[имена лишних цв. атрибутов]).
    """
    out = []
    for m in meshes:
        extra = m.get('extra') or []
        if not extra:
            continue
        out.append(_issue(
            'WARNING', 'ExtraColorAttr',
            'Лишние цветовые атрибуты: {extra}. GTA использует только Day и '
            'Night — остальные не экспортируются и сбивают превью альфы '
            'вершин. Удали лишние цветовые атрибуты.',
            'OBJECT', m['name'],
            args={'extra': ', '.join(extra)}))
    return out


def check_suffix_consistency(names, configured_suffixes):
    """Detect names that look like they're trying to be a typed model
    (DFF/LOD/COL) but use a different separator than scene config, or
    pile two type-suffixes onto one name.

    Args:
        names: iterable of object names (strings)
        configured_suffixes: dict {'DFF': '_DFF', 'LOD': '_LOD',
            'COL': '_COL'} — values come from
            scene.inu_settings.gtatools_suffix_dff / _lod / _col.

    Catches:
      • body_LOD_DFF — adjacent type-suffix pair
      • body.DFF when settings have _DFF — wrong separator at end
    """
    out = []
    cfg_upper = {k: v.upper() for k, v in configured_suffixes.items() if v}

    for name in names:
        upper = name.upper()

        # ── 1. Adjacent type-suffix pair ──
        flagged_double = False
        for kind_a, sfx_a in cfg_upper.items():
            for kind_b, sfx_b in cfg_upper.items():
                if kind_a == kind_b:
                    continue
                if (sfx_a + sfx_b) in upper:
                    out.append(_issue(
                        'WARNING', 'SuffixMismatch',
                        "имя содержит '{combo}' — "
                        "лишний суффикс рядом с {kind}",
                        'OBJECT', name,
                        args={'combo': f'{sfx_a}{sfx_b}',
                              'kind': kind_a}))
                    flagged_double = True
                    break
            if flagged_double:
                break

        if flagged_double:
            continue

        # ── 2. Wrong separator at end ──
        # If config says "_DFF" and name ends with ".DFF" — flag it.
        # We only consider single-character separators (_ . space).
        # Bare-suffix variant ("nameDFF") is already accepted by
        # tools.model_utils.get_model_type, so we skip it here.
        # The separator-mismatch case is fixable in one rename, so we
        # wire fix_op_id — the panel renders an «Исправить» button
        # that calls gtatools.validate_fix_suffix to do the rename.
        for kind, sfx in cfg_upper.items():
            if upper.endswith(sfx):
                continue  # name uses configured separator — fine
            if not sfx or len(sfx) < 2:
                continue
            sep = sfx[0]
            rest = sfx[1:]
            if sep not in '_.':
                continue
            alt_sep = '.' if sep == '_' else '_'
            alt = alt_sep + rest
            if upper.endswith(alt):
                out.append(_issue(
                    'WARNING', 'SuffixMismatch',
                    "имя оканчивается на '{alt}', "
                    "но настройка ожидает '{sfx}'",
                    'OBJECT', name,
                    fix_op_id='gtatools.validate_fix_suffix',
                    fix_arg=name,
                    args={'alt': alt, 'sfx': sfx}))
                break  # one mismatch per name is enough

    return out


def check_object_scale(objects, eps=1e-3):
    """Detect objects whose ``obj.scale`` will cause grief at export
    time:

      • negative scale (any axis < 0): the mesh ends up mirrored and
        normals point inward — invisible faces in-game, lighting wrong
      • non-uniform scale (axes differ): hierarchy children inherit a
        skewed transform, vehicle wheels rotate wrong, ped weights
        deform incorrectly

    Uniform-but-non-one (e.g. (2, 2, 2)) is intentionally not flagged
    — it's common during WIP and Apply Transforms is one Ctrl+A away.

    Args:
        objects: iterable of dicts with keys
            name (str), scale (3-tuple of floats)
    """
    out = []
    for obj in objects:
        sx, sy, sz = obj['scale']

        if sx < -eps or sy < -eps or sz < -eps:
            out.append(_issue(
                'WARNING', 'BadScale',
                "отрицательный scale ({sx:.2f}, {sy:.2f}, {sz:.2f}) — "
                "нормали вывернутся, faces могут стать невидимы",
                'OBJECT', obj['name'],
                args={'sx': sx, 'sy': sy, 'sz': sz}))
            continue

        # Non-uniform: largest pairwise diff above tolerance.
        if (abs(sx - sy) > eps
                or abs(sy - sz) > eps
                or abs(sx - sz) > eps):
            out.append(_issue(
                'INFO', 'BadScale',
                "non-uniform scale ({sx:.2f}, {sy:.2f}, {sz:.2f}) — "
                "перед экспортом сделай Ctrl+A → All Transforms",
                'OBJECT', obj['name'],
                args={'sx': sx, 'sy': sy, 'sz': sz}))
    return out


def check_light_beam_asi(meshes, sa_light_asi_present):
    """Meshes with the SA_Light.asi marker flag set, but plugin not
    installed in the game root — flag won't activate, render will
    fall back to opaque polygon with hard alpha cutoff.

    Args:
        meshes: iterable of dicts with keys
            name (str), light_beam_asi (bool)
        sa_light_asi_present: bool — SA_Light.asi present in game root.
    """
    if sa_light_asi_present:
        return []
    out = []
    for m in meshes:
        if m.get('light_beam_asi'):
            out.append(_issue(
                'INFO', 'LightBeamASI',
                'флаг Light Beam ASI включён, но SA_Light.asi не найден '
                'в game root — плагин не активируется',
                'OBJECT', m['name']))
    return out


# Детали, у которых по канону НЕТ повреждённого варианта (_dam), — их `_ok`
# без пары это норма, предупреждать не надо. Напр. exhaust никогда не ломается.
_NO_DAM_PARTS = frozenset({'exhaust'})


def check_damage_pairs(mesh_names):
    """Detect _ok meshes without a _dam twin (and vice versa).

    The engine only swaps in damaged variants when both halves of
    the pair exist; orphans are silently ignored.

    Args:
        mesh_names: iterable of strings (object .name values)
    """
    OK = '_ok'
    DAM = '_dam'
    oks = {}
    dams = {}
    for name in mesh_names:
        if name.endswith(OK):
            oks[name[:-len(OK)]] = name
        elif name.endswith(DAM):
            dams[name[:-len(DAM)]] = name

    out = []
    for base in sorted(set(oks) - set(dams)):
        # Детали без канонного _dam (exhaust и т.п.) не считаем «без пары».
        if base.lower() in _NO_DAM_PARTS:
            continue
        out.append(_issue(
            'WARNING', 'DamagePair',
            'нет парного _dam',
            'OBJECT', oks[base]))
    for base in sorted(set(dams) - set(oks)):
        out.append(_issue(
            'WARNING', 'DamagePair',
            'нет парного _ok',
            'OBJECT', dams[base]))
    return out


def check_cross_game_compat(scene_game, model_data):
    """Warn when the scene targets III/VC but objects rely on
    SA-only features that the writer would silently drop on export.

    The writers (Phase 1-7) already gate SA-specific extensions
    when ``rw_version < 0x36000`` — this check surfaces the same
    information to the user at validate time, so they can decide
    whether to remove the feature or switch the scene back to SA.

    Args:
        scene_game: 'III' / 'VC' / 'SA' (gtatools_game enum value).
        model_data: list of dicts with keys
            name (str), model_id (int), has_night_vcols (bool),
            has_multi_mesh_lod (bool), has_uv_anim_material (bool),
            fx_2dfx_ids (set of int)
        Built by ``_gather_cross_game_data`` in ops/validate_scene.py.
    """
    out = []
    if scene_game == 'SA' or not model_data:
        # SA target accepts everything — no cross-game friction.
        return out

    # Per-game model_id ceilings — SA-only IDs are written but the
    # target engine refuses to load model IDs past its vanilla cap
    # unless FLA is installed.
    _id_max = {'III': 6500, 'VC': 8500}.get(scene_game, 19999)

    for m in model_data:
        name = m.get('name', '?')
        mid = m.get('model_id') or 0

        if mid > _id_max:
            out.append(_issue(
                'WARNING', 'CrossGame',
                f'model_id {mid} > {scene_game} vanilla max {_id_max} '
                f'(нужен Fastman92 Limit Adjuster для {scene_game})',
                'OBJECT', name))

        # Night vertex colors (SA-only extension 0x253F2FB).
        if m.get('has_night_vcols'):
            out.append(_issue(
                'WARNING', 'CrossGame',
                f'Night vcols это SA-only — будут потеряны при экспорте в {scene_game}',
                'OBJECT', name))

        # Multi-mesh LOD (SA-only OBJS-line variant — III/VC IDE writer
        # downgrades to single-mesh and drops extra draw_distances).
        if m.get('has_multi_mesh_lod'):
            out.append(_issue(
                'WARNING', 'CrossGame',
                f'Multi-mesh LOD это SA-only — в {scene_game} останется только первый draw_distance',
                'OBJECT', name))

        # UV animation materials: the UV Anim Dict / PLG are RW 3.5+, so
        # only SA (3.6.0.3) gets them — VC PC is 3.4.0.3, III 3.3.0.2.
        if scene_game in ('III', 'VC') and m.get('has_uv_anim_material'):
            out.append(_issue(
                'WARNING', 'CrossGame',
                'UV anim material требует RW 3.5+ (SA) — в III/VC не запишется',
                'OBJECT', name))

        # 2DFX types — types beyond III/VC's allowlist are silently
        # dropped (see _allowed_2dfx_ids in core/dff.py).
        fx_ids = m.get('fx_2dfx_ids') or set()
        if scene_game == 'III':
            unsupported = fx_ids - {0, 1}
        else:  # VC
            unsupported = fx_ids - {0, 1, 3}
        if unsupported:
            ids_str = ', '.join(sorted(str(i) for i in unsupported))
            out.append(_issue(
                'WARNING', 'CrossGame',
                f'2DFX типы {ids_str} не поддерживаются в {scene_game}, будут пропущены',
                'OBJECT', name))

    return out
