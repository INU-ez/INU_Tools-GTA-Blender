# INU_tools.ops.id_manager_ops — ID manager (auto-assign / clear / extend / GC / sync) + ID preset CRUD.
#
# Phase 3 (2026-04-26): operators moved from __init__.py.

import os
import bpy
from bpy.props import (
    StringProperty, BoolProperty, IntProperty, EnumProperty,
)

from .. import T


class GTATOOLS_OT_id_manager_open_file(bpy.types.Operator):
    """Открыть файл активного ID пресета в текстовом редакторе"""
    bl_idname = "gtatools.id_manager_open_file"
    bl_label = "INU: Open ID File"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import get_file_path
        filepath = get_file_path()
        if not os.path.isfile(filepath):
            self.report({'ERROR'}, T("Файл ID не найден. Нажмите 'Создать файл ID'"))
            return {'CANCELLED'}
        # Штатный кроссплатформенный способ (без внешних процессов —
        # требование extensions.blender.org): открывает файл в приложении ОС.
        bpy.ops.wm.path_open(filepath=filepath)
        self.report({'INFO'}, f"{T('Открыт:')} {filepath}")
        return {'FINISHED'}


class GTATOOLS_OT_id_manager_release(bpy.types.Operator):
    """Освободить ID"""
    bl_idname = "gtatools.id_manager_release"
    bl_label = "INU: Release ID"
    bl_options = {'REGISTER'}

    model_id: IntProperty()
    _confirmed_game_id = None

    def invoke(self, context, event):
        from .. import _id_preset_sync
        from ..data.id_manager import game_ids
        _id_preset_sync(context)
        self._confirmed_game_id = None
        if self.model_id in game_ids():
            self._confirmed_game_id = self.model_id
            return context.window_manager.invoke_props_dialog(self, width=460)
        return self.execute(context)

    def draw(self, context):
        self.layout.label(text=T("Освободить ID игры {0}?").format(self.model_id))
        self.layout.label(text=T("ID будет удалён из .game и доступен для назначения."))
        self.layout.label(text=T("Новая модель с этим ID заменит модель игры в IDE."))

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import release_id, game_ids
        is_game = self.model_id in game_ids()
        if is_game and self._confirmed_game_id != self.model_id:
            self.report({'WARNING'}, T("Освобождение ID игры требует подтверждения."))
            return {'CANCELLED'}
        try:
            release_id(self.model_id, free_game=is_game)
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'CANCELLED'}
        # Clear scene IDs only after the preset and its sidecar were saved.
        for obj in bpy.data.objects:
            inu = getattr(obj, 'inu', None)
            if inu and inu.model_id == self.model_id:
                inu.model_id = 0
        self.report({'INFO'}, f"ID {self.model_id} {T('освобождён')}")
        return {'FINISHED'}


def _ide_name(obj, typed=None, hd_of=None):
    """Model name for the preset — as its IDE row (the IDE writer's rule:
    map_link.ide_entries). ``typed`` = get_model_type(obj) if already known;
    ``hd_of`` = map_link.lod_hd_names of the scene, built once by the caller
    (III/VC: a LOD's name follows its model's — house → LODse)."""
    from ..tools.model_utils import get_model_type
    from .. import _clean_model_name_ide
    from .map_link import lod_model_name
    mt, base = typed or get_model_type(obj)
    if mt == 'LOD':
        return lod_model_name(obj, base or _clean_model_name_ide(obj.name),
                              hd=(hd_of or {}).get(id(obj), ''))
    return _clean_model_name_ide(obj.name)


def _scene_hd_names(scene):
    """map_link.lod_hd_names of the whole scene ({} outside III/VC)."""
    from .map_link import lod_hd_names
    return lod_hd_names(scene.objects)


_IDE_IDS = {}       # IDE path → (mtime_ns, {ID: names lower}): re-read only when the file changed


def _ide_ids(context, names=False):
    """IDs of the IDE files the user works with: the IDE box, «IDE для
    экспорта», the IDE each scene model is linked to. Assign steps over
    them — a second row with the same ID overwrites the model in game.
    ``names`` → {ID: {model names lower}} instead of a set of IDs."""
    from .map_link import norm, ide_linked_file
    from ..core.ide import read_ide
    s = context.scene.inu_settings
    paths = [norm(p) for p in ([getattr(s, 'gtatools_ide_path', '')]
                               + [it.path for it in getattr(s, 'gtatools_ide_sync_list', [])])
             if p]
    paths += [ide_linked_file(o) for o in context.scene.objects
              if o.type == 'MESH' and hasattr(o, 'inu')]
    ids, seen = {}, set()
    for p in paths:
        if not p or p in seen or not os.path.isfile(p):
            continue
        seen.add(p)
        try:
            mt = os.stat(p).st_mtime_ns
        except OSError:
            continue
        hit = _IDE_IDS.get(p)
        if hit is None or hit[0] != mt:
            got = {}
            try:
                ide = read_ide(p)
                for sec in (ide.objects, ide.anims, ide.cars, ide.peds, ide.weaps, ide.hiers):
                    for e in sec:
                        got.setdefault(int(e.model_id), set()).add(str(e.model_name).lower())
            except Exception as e:
                print(f"[INU] IDE ids {os.path.basename(p)}: {e!r}")
            hit = _IDE_IDS[p] = (mt, got)
        for i, nms in hit[1].items():
            ids.setdefault(i, set()).update(nms)
    return ids if names else set(ids)


def _models_by_key(scene, hd_of=None):
    """(type, model name lower) → every mesh of the scene with that model
    (copies: house, house.001). COL has no IDE row — left out."""
    from ..tools.model_utils import get_model_type
    if hd_of is None:
        hd_of = _scene_hd_names(scene)
    out = {}
    for o in scene.objects:
        if o.type != 'MESH' or not hasattr(o, 'inu'):
            continue
        typed = get_model_type(o)
        if typed[0] == 'COL':
            continue
        out.setdefault((typed[0], _ide_name(o, typed, hd_of).lower()), []).append(o)
    return out


def _ordered_keys(objs, lodix, with_lods=True, hd_of=None):
    """Models of the selection in order: a model, then its LOD (also an
    unselected one; ``with_lods`` = False — only a selected one). Selected
    LODs whose model isn't selected go last, so a LOD never takes its
    number before its model."""
    from ..tools.model_utils import get_model_type
    if hd_of is None:
        hd_of = _scene_hd_names(bpy.context.scene)
    keys, lods, seen = [], [], set()

    def add(k):
        if k not in seen:
            seen.add(k)
            keys.append(k)

    for o in objs:
        typed = get_model_type(o)
        if typed[0] == 'COL':
            continue
        k = (typed[0], _ide_name(o, typed, hd_of).lower())
        if typed[0] == 'LOD':
            lods.append(k)
            continue
        add(k)
        lod = lodix.partner(o)
        if lod is not None:
            add(('LOD', _ide_name(lod, hd_of=hd_of).lower()))
    for k in lods:
        add(k)
    if not with_lods:
        sel = set(lods)
        keys = [k for k in keys if k[0] != 'LOD' or k in sel]
    return keys


def _own_col_ids(objects, hd_of=None):
    """Model key → IDs held only by that model's own COL copies.
    An unrelated model/COL holding the same ID still makes it occupied."""
    from ..tools.model_utils import get_model_type
    holders, collisions = {}, {}
    for o in objects:
        if o.type != 'MESH' or not getattr(o, 'inu', None):
            continue
        mid = o.inu.model_id
        if mid <= 0:
            continue
        typed = get_model_type(o)
        if typed[0] == 'COL':
            key = ('DFF', (typed[1] or '').lower())
            collisions.setdefault(key, set()).add(mid)
            owner = key
        else:
            owner = (typed[0], _ide_name(o, typed, hd_of).lower())
        holders.setdefault(mid, set()).add(owner)
    return {key: {i for i in ids if holders[i] == {key}}
            for key, ids in collisions.items()}


def assign_groups(keys, by_key, preset, skip, owner_ids_of, name_of,
                  own_ids_of=None, col_ids_of=None):
    """Assign's loop (bpy-free — tested without Blender). For each model key
    whose objects have Model ID = 0: a copy that already has an ID gives it
    to the rest; else a new ID from ``preset.allocate`` — a LOD prefers the
    ID of its model + 1. ``skip`` (IDs to step over) gets the new IDs;
    ``owner_ids_of(group)`` → Model IDs of the models whose LOD the group is;
    ``own_ids_of(group)`` → IDs of the group's own IDE rows: a LOD that Add
    to IDE already wrote at model + 1 keeps that ID (not someone else's).

    Returns (done [(name, ID)], reused — copies given an existing ID,
    left [names without ID], warn [('ids', name, IDs, ID) |
    ('taken' / 'absent' — not in the preset, name, preferred ID, ID)])."""
    done, reused, left, warn = [], 0, [], []
    new = set()
    for key in keys:
        group = by_key.get(key, [])
        zero = [o for o in group if o.inu.model_id <= 0]
        if not zero:
            continue
        have = sorted({o.inu.model_id for o in group if o.inu.model_id > 0})
        name = name_of(group[0])
        if have:
            if len(have) > 1:
                warn.append(('ids', name, have, have[0]))
            nid = have[0]
            reused += len(zero)
        else:
            prefer = None
            if key[0] == 'LOD':
                ids = [i for i in owner_ids_of(group) if i > 0]
                if ids:
                    prefer = min(ids) + 1
            own = (set(own_ids_of(group)) - new
                   if own_ids_of and prefer is not None else set())
            if prefer in own and prefer not in preset.ids():
                preset.reserve(prefer, name)     # its IDE row holds it — the preset learns it
                nid = prefer
            else:
                own_col = (set(col_ids_of(key)) - new if col_ids_of else set())
                free_skip = skip - own_col
                nid = preset.allocate(name, free_skip - own if prefer in own else free_skip,
                                      prefer, restart=bool(own_col))
            if nid is None:
                left.append(name)
                continue
            skip.add(nid)
            new.add(nid)
            if prefer is not None and nid != prefer:
                absent = prefer not in skip and prefer not in preset.ids()
                warn.append(('absent' if absent else 'taken', name, prefer, nid))
            done.append((name, nid))
        for o in zero:
            o.inu.model_id = nid
    return done, reused, left, warn


def _fmt_ids(pairs, n=6):
    s = ", ".join(f"{nm} {i}" for nm, i in pairs[:n])
    return s + (" …" if len(pairs) > n else "")


class GTATOOLS_OT_id_manager_auto_assign(bpy.types.Operator):
    """Назначить ID выделенным моделям с Model ID = 0. Копии модели получают один ID, её LOD (даже не выделенный) — ID модели + 1"""
    bl_idname = "gtatools.id_manager_auto_assign"
    bl_label = "INU: Auto Assign IDs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import Preset, get_active_preset
        from .map_link import LodIndex, ide_linked_file

        objs = [o for o in context.selected_objects
                if o.type == 'MESH' and hasattr(o, 'inu')]
        if not objs:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}

        # Collect every ID already claimed by a scene object so
        # allocation steps over them (no collision with map-imported or
        # hand-edited IDs). We pass these to allocate() as a *skip*
        # set rather than writing them into the preset: dragging the
        # whole scene into the preset used to flood the manager's
        # "used" list with IDs the user never assigned (the «shows
        # other ids I don't want» report). Newly allocated IDs still
        # land in the preset — those are the ones the user wants to see.
        # IDs of the user's IDE files are stepped over the same way.
        scene_ids = {
            o.inu.model_id for o in bpy.data.objects
            if o.type == 'MESH' and getattr(o, 'inu', None)
            and o.inu.model_id > 0
        }
        ide_ids = _ide_ids(context)
        skip = scene_ids | ide_ids

        # One model = one IDE row: all copies of a selected model get one
        # ID, its LOD (selected or not) — the model's ID + 1 if free.
        lodix = LodIndex()
        hd_of = _scene_hd_names(context.scene)
        by_key = _models_by_key(context.scene, hd_of)
        keys = _ordered_keys(objs, lodix, hd_of=hd_of)
        owners = None       # LOD → models it is the LOD of, built on first need

        def owner_ids_of(group):
            nonlocal owners
            if owners is None:
                owners = {}
                for (mt, _n), dffs in by_key.items():
                    if mt == 'DFF':
                        for d in dffs:
                            p = lodix.partner(d)
                            if p is not None:
                                owners.setdefault(p, []).append(d)
            return [d.inu.model_id for o in group for d in owners.get(o, ())]

        def own_ids_of(group):
            # The row Add to IDE wrote for a LOD still at Model ID 0 (its
            # ID = model + 1) — in its linked IDE and held by no scene object.
            out = set()
            for o in group:
                mid = int(getattr(o.inu, 'ide_last_model_id', 0) or 0)
                p = ide_linked_file(o) if mid in ide_ids else ''
                if p and mid in _IDE_IDS.get(p, (0, ()))[1]:
                    out.add(mid)
            return out - scene_ids

        # One read and one write of the preset for the whole run.
        P = Preset(get_active_preset())
        col_ids = _own_col_ids(bpy.data.objects, hd_of)
        done, reused, left, warn = assign_groups(
            keys, by_key, P, skip, owner_ids_of,
            lambda o: _ide_name(o, hd_of=hd_of), own_ids_of,
            lambda key: col_ids.get(key, set()) - ide_ids)

        # Saved also when IDs ran out midway — the objects above hold theirs.
        try:
            P.save()
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'FINISHED'}
        msg = f"{T('Назначено ID:')} {len(done)}"
        if reused:
            msg += " (" + T("копиям дан готовый ID: {0}").format(reused) + ")"
        if done:
            msg += " — " + _fmt_ids(done)
        parts = [msg]
        for kind, name, a, nid in warn:
            if kind == 'ids':
                parts.append(T("«{0}»: у копий разные ID ({1}) — взят {2}").format(
                    name, ", ".join(map(str, a)), nid))
            elif kind == 'absent':
                parts.append(T("«{0}»: ID {1} нет в пресете — LOD получил {2}").format(name, a, nid))
            else:
                parts.append(T("«{0}»: ID {1} занят — LOD получил {2}").format(name, a, nid))
        if left:
            parts.append(T("Нет свободных ID в активном пресете — без ID: {0}").format(
                ", ".join(left[:8]) + (" …" if len(left) > 8 else "")))
        self.report({'ERROR' if left else ('WARNING' if warn else 'INFO')}, "; ".join(parts))
        return {'FINISHED'}


def assign_from_groups(keys, by_key, preset, others, ide, start, skip_occupied, name_of,
                       col_ids_of=None):
    """«С ID…» loop (bpy-free — tested without Blender): IDs in a row from
    ``start``, one per model key — every copy of the model gets it.
    Occupied: the preset's used IDs, ``others`` (IDs of the objects not
    being renumbered) and ``ide`` ({ID: {model names lower}} of the user's
    IDE files) — except the model's own rows (under its own name, at its
    current ID or at the ID its IDE link remembers). ``skip_occupied``
    steps over them, else the ID is given anyway and counted as a clash.
    The models' previous IDs are freed in the preset unless still held or
    used by the game.

    Returns (done [(name, ID)], clashes, freed — IDs freed in the preset)."""
    groups = [(key, by_key.get(key) or []) for key in keys]
    old_ids, own = set(), set()
    for key, group in groups:
        for o in group:
            i = o.inu.model_id
            if i > 0:
                old_ids.add(i)
            # Its own IDE row — not a clash: at the current ID or at the one
            # its IDE link remembers (a LOD that Add to IDE wrote at model + 1
            # keeps Model ID 0; a model renumbered or cleared since the sync).
            for j in (i, int(getattr(o.inu, 'ide_last_model_id', 0) or 0)):
                if j > 0 and ide.get(j) == {key[1]}:
                    own.add(j)
    ide_f = set(ide) - own
    pre = preset.used()
    used = set(pre) | preset.game | others | ide_f
    used -= old_ids - preset.game - others - ide_f
    # A linked row's ID is free too, unless the preset gives it to another name.
    used -= {j for j in own - old_ids - preset.game - others
             if (pre.get(j) or '').lower() in ide[j] | {''}}
    cur, done, clashes = max(1, int(start)), [], 0
    for key, group in groups:
        if not group:
            continue
        own_col = set(col_ids_of(key)) if col_ids_of else set()
        available_col = {i for i in own_col - preset.game - ide_f
                         if not pre.get(i) or pre[i].lower() == key[1]}
        occupied = used - (available_col - {i for _n, i in done})
        if skip_occupied:
            while cur in occupied:
                cur += 1
        elif cur in occupied:
            # Honour the requested start exactly, but flag the overlap so
            # the user knows two models now share this ID.
            clashes += 1
        name = name_of(group[0])
        for o in group:
            o.inu.model_id = cur
        # Reserved in the preset too — otherwise it would keep showing the
        # ID as free and the next Assign would hand it out again.
        preset.reserve(cur, name)
        used.add(cur)
        done.append((name, cur))
        cur += 1
    still = others | {i for _n, i in done}
    freed = sum(1 for i in sorted(old_ids)
                if i not in still and i not in preset.game and preset.release(i))
    return done, clashes, freed


class GTATOOLS_OT_id_manager_assign_from(bpy.types.Operator):
    """Назначить ID подряд выделенным моделям, начиная с указанного. Копии модели получают один ID; LOD — только если выделен; COL не трогается. Прежние ID освобождаются в пресете"""
    bl_idname = "gtatools.id_manager_assign_from"
    bl_label = "INU: Assign IDs from..."
    bl_options = {'REGISTER', 'UNDO'}

    start_id: IntProperty(
        name="Start ID",
        default=321,
        min=1,
        description=T("Начальный ID для назначения"),
    )
    skip_occupied: BoolProperty(
        name=T("Пропускать занятые ID"),
        default=True,
        description=T("Вкл — пропускать уже занятые ID (как авто-назначение). "
                      "Выкл — строго по порядку от стартового, даже если занято"),
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import Preset, get_active_preset
        from .map_link import LodIndex

        objs = [o for o in context.selected_objects
                if o.type == 'MESH' and hasattr(o, 'inu')]
        # One model = one IDE row: all copies of a selected model get one
        # ID, a LOD only when selected. COL has no IDE row — left alone.
        hd_of = _scene_hd_names(context.scene) if objs else {}
        keys = (_ordered_keys(objs, LodIndex(), with_lods=False, hd_of=hd_of)
                if objs else [])
        if not keys:
            self.report({'ERROR'}, T("Выделите меш объекты"))
            return {'CANCELLED'}
        by_key = _models_by_key(context.scene, hd_of)

        # We deliberately do NOT pull the whole scene into the preset here —
        # doing so flooded the manager's "used" list with map-imported IDs the
        # user never assigned (the «From ID 80000 shows other ids I don't want»
        # report). Only the IDs we hand out below get reserved in the preset.
        # IDs on OTHER scene objects (not the models being re-numbered) are
        # occupied; the models' own current IDs are not, or re-running
        # «from X» on the same group would drift off the requested start.
        affected = {o for k in keys for o in by_key.get(k, ())}
        others = {o.inu.model_id for o in bpy.data.objects
                  if o.type == 'MESH' and o not in affected
                  and hasattr(o, 'inu') and o.inu.model_id > 0}
        P = Preset(get_active_preset())     # one read, one write per run
        col_ids = _own_col_ids(bpy.data.objects, hd_of)
        done, clashes, freed = assign_from_groups(
            keys, by_key, P, others, _ide_ids(context, names=True),
            self.start_id, self.skip_occupied,
            lambda o: _ide_name(o, hd_of=hd_of),
            lambda key: col_ids.get(key, ()))
        try:
            P.save()
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'FINISHED'}

        # The real range: skipping may start past the requested ID.
        msg = f"{T('Назначено ID:')} {len(done)}"
        if len(done) > 1:
            msg += f" ({done[0][1]}–{done[-1][1]})"
        if done:
            msg += " — " + _fmt_ids(done)
        parts = [msg]
        if clashes:
            parts.append(f"{T('конфликтов с занятыми:')} {clashes}")
        if freed:
            parts.append(T("прежние ID освобождены в пресете: {0}").format(freed))
        self.report({'WARNING' if clashes else 'INFO'}, "; ".join(parts))
        return {'FINISHED'}


class GTATOOLS_OT_batch_set_type(bpy.types.Operator):
    """Массовое переключение типа объектов (OBJ/COL/SHA/2DFX/NON)"""
    bl_idname = "gtatools.batch_set_type"
    bl_label = "INU: Batch Set Type"
    bl_options = {'REGISTER', 'UNDO'}

    obj_type: EnumProperty(
        items=[
            ('OBJ', 'Object', ''),
            ('COL', 'Collision', ''),
            ('SHA', 'Shadow', ''),
            ('NON', "Don't export", ''),
        ],
        name="Type",
    )

    def execute(self, context):
        from ..tools.model_utils import get_model_type, _get_suffixes, _get_prefixes

        suffixes = _get_suffixes()
        prefixes = _get_prefixes()

        count = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH' or not hasattr(obj, 'inu'):
                continue

            # Get current base name
            _, base = get_model_type(obj)
            if not base:
                base = obj.name

            # Set internal type
            obj.inu.type = self.obj_type

            # Rename: base + new suffix/prefix
            new_sfx = suffixes.get(self.obj_type, '')
            new_pfx = prefixes.get(self.obj_type, '')
            if new_sfx:
                obj.name = base + new_sfx
            elif new_pfx:
                obj.name = new_pfx + base
            else:
                obj.name = base

            count += 1
        self.report({'INFO'}, f"{self.obj_type}: {count}")
        return {'FINISHED'}


class GTATOOLS_OT_id_manager_clear_selected(bpy.types.Operator):
    """Очистить Model ID у выделенных объектов"""
    bl_idname = "gtatools.id_manager_clear_selected"
    bl_label = "INU: Clear Selected IDs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import Preset, get_active_preset

        # Snapshot which (obj, id) pairs we're clearing — then wipe
        # their scene IDs and finally release from the preset only
        # those IDs no other scene object still claims. Without this
        # check, clearing a duplicate (Shift+D gives copies the same
        # inu.model_id as the original) would free the preset slot
        # while the original is still visually using it.
        to_clear = []
        for obj in context.selected_objects:
            if obj.type == 'MESH' and hasattr(obj, 'inu'):
                mid = obj.inu.model_id
                if mid > 0:
                    to_clear.append((obj, mid))

        for obj, _mid in to_clear:
            obj.inu.model_id = 0

        remaining = {
            o.inu.model_id for o in bpy.data.objects
            if o.type == 'MESH' and hasattr(o, 'inu') and o.inu.model_id > 0
        }

        # IDs used by the game («Из игры») stay taken: freed, a vanilla ID
        # would be handed out again and duplicate the game's model.
        P = Preset(get_active_preset())
        released = 0
        for _obj, mid in to_clear:
            if mid not in remaining and mid not in P.game and P.release(mid):
                released += 1
        try:
            P.save()
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'FINISHED'}

        count = len(to_clear)
        self.report(
            {'INFO'},
            f"{T('Очищено ID:')} {count} "
            f"({T('освобождено в пресете:')} {released})",
        )
        return {'FINISHED'}


class GTATOOLS_OT_id_manager_clear(bpy.types.Operator):
    """Очистить все занятые ID"""
    bl_idname = "gtatools.id_manager_clear"
    bl_label = "INU: Clear All IDs"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        wm = context.window_manager
        if bpy.app.version >= (4, 1, 0):      # title/message: Blender 4.1+
            return wm.invoke_confirm(
                self, event, title=T("Очистить всё"),
                message=T("Освободить все занятые ID пресета. ID игры («Из игры») остаются."))
        return wm.invoke_confirm(self, event)

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import clear_all, game_ids
        try:
            n = clear_all()
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'CANCELLED'}
        msg = f"{T('Все ID очищены')}: {n}"
        kept = len(game_ids())
        if kept:
            msg += " (" + T("ID игры сохранены: {0}").format(kept) + ")"
        self.report({'INFO'}, msg)
        return {'FINISHED'}



class GTATOOLS_OT_id_manager_create(bpy.types.Operator):
    """Заполнить пресет ID 321-19999: недостающие — свободными, занятые остаются"""
    bl_idname = "gtatools.id_manager_create"
    bl_label = "INU: Create ID File"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        wm = context.window_manager
        if bpy.app.version >= (4, 1, 0):      # title/message: Blender 4.1+
            from .. import _id_preset_sync
            _id_preset_sync(context)
            from ..data.id_manager import get_active_preset
            return wm.invoke_confirm(
                self, event, title=T("Создать ID"),
                message=T("Пресет «{0}»: недостающие ID 321-19999 будут добавлены "
                          "свободными, занятые останутся").format(get_active_preset()))
        return wm.invoke_confirm(self, event)

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import create_id_file
        try:
            count = create_id_file()        # only the missing IDs are added
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, T("ID: 321-19999 (+{0} свободных)").format(count))
        return {'FINISHED'}


class GTATOOLS_OT_id_manager_extend(bpy.types.Operator):
    """Добавить ID (Fastman Limit Adjuster)"""
    bl_idname = "gtatools.id_manager_extend"
    bl_label = "INU: Extend IDs"
    bl_options = {'REGISTER'}

    count: IntProperty(
        name="Count",
        default=1000,
        min=100, max=50000,
        description=T("Количество ID для добавления"),
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import extend_ids
        try:
            new_start, new_end = extend_ids(self.count)
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"ID: +{self.count} ({new_start}-{new_end})")
        return {'FINISHED'}


class GTATOOLS_OT_id_manager_from_game(bpy.types.Operator):
    """Загрузить занятые ID из IDE файлов игры (SA, VC, III)"""
    bl_idname = "gtatools.id_manager_from_game"
    bl_label = "INU: Load IDs from Game"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import populate_from_game
        game_root = bpy.path.abspath(context.scene.inu_settings.gtatools_game_root)
        if not game_root or not os.path.isdir(game_root):
            self.report({'ERROR'}, T("Укажите корневую папку GTA SA"))
            return {'CANCELLED'}
        try:
            res = populate_from_game(game_root)
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'CANCELLED'}
        if res is None:
            self.report({'ERROR'}, T("Нет data\\gta.dat / default.dat в папке игры"))
            return {'CANCELLED'}
        parts = [T("ID игры: {0} (IDE: {1}, из {2}), новых занято: {3}").format(
            res['count'], res['n_ide'], ", ".join(res['dats']) or "—", res['added'])]
        clashes, bad = res['clashes'], res['bad']
        if clashes:
            parts.append(T("Ваши записи на ID игры переименованы ({0}): {1}").format(
                len(clashes),
                ", ".join(f"{i} {old}→{new}" for i, old, new in clashes[:5])
                + (" …" if len(clashes) > 5 else "")))
        if bad:
            parts.append(T("Не прочитаны: {0}").format(
                ", ".join(bad[:5]) + (" …" if len(bad) > 5 else "")))
        self.report({'WARNING' if clashes or bad else 'INFO'}, "; ".join(parts))
        return {'FINISHED'}


class GTATOOLS_OT_id_manager_gc(bpy.types.Operator):
    """Освободить записи пресета, у которых нет соответствующего объекта в сцене"""
    bl_idname = "gtatools.id_manager_gc"
    bl_label = "INU: Free phantom IDs"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import gc_preset, game_ids
        try:
            released = gc_preset(bpy.data.objects)
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'CANCELLED'}
        msg = f"{T('Освобождено фантомных ID:')} {released}"
        kept = len(game_ids())
        if kept:
            msg += " (" + T("ID игры сохранены: {0}").format(kept) + ")"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class GTATOOLS_OT_id_manager_sync_scene(bpy.types.Operator):
    """Добавить ID из объектов сцены в менеджер"""
    bl_idname = "gtatools.id_manager_sync_scene"
    bl_label = "INU: Sync Scene IDs"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from .. import _id_preset_sync
        _id_preset_sync(context)
        from ..data.id_manager import Preset, get_active_preset
        from ..tools.model_utils import get_model_type

        # A missing ID is added, a free one is taken — by the model's IDE
        # name (a LOD by its own, not its model's). Taken names stay. COL
        # has no IDE row: its ID is the model's.
        P = Preset(get_active_preset())     # one read, one write
        used = P.used()
        added = 0
        hd_of = None        # built on the first LOD
        for obj in bpy.data.objects:
            if obj.type != 'MESH' or not hasattr(obj, 'inu'):
                continue
            mid = obj.inu.model_id
            if mid <= 0 or mid in used:
                continue
            typed = get_model_type(obj)
            if typed[0] == 'COL':
                continue
            if typed[0] == 'LOD' and hd_of is None:
                hd_of = _scene_hd_names(context.scene)
            P.reserve(mid, _ide_name(obj, typed, hd_of))
            used[mid] = True
            added += 1

        try:
            P.save()
        except OSError as e:        # preset file locked (antivirus, another program)
            self.report({'ERROR'}, f"{T('Ошибка записи:')} {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"{T('Добавлено ID:')} {added}")
        return {'FINISHED'}


class GTATOOLS_OT_id_preset_new(bpy.types.Operator):
    """Создать новый пресет ID.

    Пустой пресет создаётся готовым к `Создать файл ID` (Заполнить 321-19999).
    Опция «Скопировать с активного» дублирует текущий файл ID, чтобы не
    начинать с нуля, если часть ID уже назначена.
    """
    bl_idname = "gtatools.id_preset_new"
    bl_label = "INU: New ID Preset"
    bl_options = {'REGISTER'}

    name: StringProperty(
        name=T("Название"),
        description=T("Имя нового пресета. Будет сохранён как data/id_presets/<имя>.txt"),
        default="",
    )
    copy_from_active: BoolProperty(
        name=T("Скопировать с активного"),
        description=T("Создать пресет как копию текущего активного"),
        default=False,
    )

    def invoke(self, context, event):
        self.name = ""
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'name')
        layout.prop(self, 'copy_from_active')

    def execute(self, context):
        from ..data.id_manager import create_preset, get_active_preset, preset_name
        name = (self.name or '').strip()
        # The file name as the selector lists it («a/b» → «a_b»): the
        # selector only takes listed names — the raw one left it on the old
        # preset while the report said «created».
        name = preset_name(name) if name else ''
        if not name:
            self.report({'ERROR'}, T("Введите название пресета"))
            return {'CANCELLED'}
        src = get_active_preset() if self.copy_from_active else None
        if not create_preset(name, copy_from=src):
            self.report({'ERROR'}, T("Пресет уже существует или не удалось создать"))
            return {'CANCELLED'}
        # Switch to the newly created preset
        try:
            context.scene.inu_settings.gtatools_id_preset = name
        except Exception:
            pass
        self.report({'INFO'}, f"{T('Создан пресет:')} {name}")
        return {'FINISHED'}


class GTATOOLS_OT_id_preset_delete(bpy.types.Operator):
    """Удалить активный пресет ID. Пресет «default» удалить нельзя"""
    bl_idname = "gtatools.id_preset_delete"
    bl_label = "INU: Delete ID Preset"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from ..data.id_manager import delete_preset, list_presets
        current = getattr(context.scene.inu_settings, 'gtatools_id_preset', 'default')
        if current == 'default':
            self.report({'ERROR'}, T("Пресет 'default' удалить нельзя"))
            return {'CANCELLED'}
        if not delete_preset(current):
            self.report({'ERROR'}, T("Не удалось удалить пресет"))
            return {'CANCELLED'}
        # Fall back to the first remaining preset
        remaining = list_presets()
        try:
            context.scene.inu_settings.gtatools_id_preset = remaining[0] if remaining else 'default'
        except Exception:
            pass
        self.report({'INFO'}, f"{T('Удалён пресет:')} {current}")
        return {'FINISHED'}


class GTATOOLS_OT_id_preset_rename(bpy.types.Operator):
    """Переименовать активный пресет ID"""
    bl_idname = "gtatools.id_preset_rename"
    bl_label = "INU: Rename ID Preset"
    bl_options = {'REGISTER'}

    new_name: StringProperty(
        name=T("Новое название"),
        default="",
    )

    def invoke(self, context, event):
        self.new_name = getattr(context.scene.inu_settings, 'gtatools_id_preset', '') or ''
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        self.layout.prop(self, 'new_name')

    def execute(self, context):
        from ..data.id_manager import rename_preset, preset_name
        current = getattr(context.scene.inu_settings, 'gtatools_id_preset', 'default')
        new = (self.new_name or '').strip()
        new = preset_name(new) if new else ''       # as the selector lists it
        if not new or new == current:
            self.report({'ERROR'}, T("Введите новое название"))
            return {'CANCELLED'}
        if not rename_preset(current, new):
            self.report({'ERROR'}, T("Не удалось переименовать (имя занято или ошибка)"))
            return {'CANCELLED'}
        try:
            context.scene.inu_settings.gtatools_id_preset = new
        except Exception:
            pass
        self.report({'INFO'}, f"{T('Переименован:')} {current} → {new}")
        return {'FINISHED'}
