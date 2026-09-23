"""Ariane → Blender bridge.

Ariane's "Export to Blender" button drops each selected model's ``.dff`` (and
its LOD ``.dff`` when one exists) into a shared inbox folder plus a small
``*.job`` file listing them. This watcher polls that folder and imports the
listed DFFs into the running Blender via :func:`import_dff` — so an already
open Blender picks up models on click, with no launching and no manual import.

Inbox (both sides compute it identically, no config):
    %LOCALAPPDATA%\\INU_ariane_bridge\\inbox
"""
from __future__ import annotations

import os

import bpy
from bpy.props import StringProperty, BoolProperty
from bpy.app.handlers import persistent as _persistent

from .. import T
from .dff_import import import_one_dff, _init_import_stats
from .dff_export import export_dff
from .col_export import export_col


# ── inbox / job processing ───────────────────────────────────────

def bridge_base() -> str:
    """Root of the bridge folders. Priority: the explicit "Ariane game" path set
    in the bridge panel → INU Game Root → %LOCALAPPDATA%. The first two point at
    the game folder, so the shared root is <game>\\ariane\\bridge (matches
    ariane's GetArianeDataPath), giving each install its own bridge."""
    try:
        import bpy
        s = bpy.context.scene.inu_settings
        for raw in (getattr(s, 'ariane_bridge_path', ''), getattr(s, 'gtatools_game_root', '')):
            p = (raw or '').strip()
            if p:
                p = bpy.path.abspath(p)
                if os.path.isdir(p):
                    return os.path.join(p, 'ariane', 'bridge')
    except Exception:                       # noqa: BLE001
        pass
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    return os.path.join(base, 'INU_ariane_bridge')


def inbox_dir() -> str:
    return os.path.join(bridge_base(), 'inbox')


# ── game of the bridge ───────────────────────────────────────────
# The job protocol carries no game (only "#v N"), so the addon decides the
# file formats itself: RW version of DFF/TXD, COL1 vs COL3, D3D8 vs D3D9
# textures, LOD naming. Source of truth = the scene's game (same as every
# other exporter); the exe in the game folder is only used to WARN when
# it disagrees, so a VC ariane never silently gets SA-format files.

_EXE_GAME = (('gta_sa.exe', 'SA'), ('gta-vc.exe', 'VC'), ('gta3.exe', 'III'))


def bridge_game() -> str:
    """Game the bridge exports for: ``scene.inu_settings.gtatools_game``."""
    try:
        import bpy
        from ..core import game_versions as gv
        return gv.game_of_scene(bpy.context.scene)
    except Exception:                       # noqa: BLE001
        return 'SA'


def bridge_game_from_exe():
    """Game of the ariane install the bridge points at, from the exe next to
    the ``ariane`` folder (``bridge_base()`` = <game>\\ariane\\bridge). None when
    the bridge lives in %LOCALAPPDATA% or no known exe is found."""
    try:
        game_dir = os.path.dirname(os.path.dirname(bridge_base()))
        for exe, game in _EXE_GAME:
            if os.path.isfile(os.path.join(game_dir, exe)):
                return game
    except Exception:                       # noqa: BLE001
        pass
    return None


def bridge_game_mismatch():
    """Warning text when the exe game differs from the scene game, else None."""
    exe_game = bridge_game_from_exe()
    game = bridge_game()
    if exe_game and exe_game != game:
        return T("В папке ariane найдена игра {0}, а сцена настроена на {1} — "
                 "файлы уйдут в формате {1}. Переключи игру во вкладке GTA Tools.").format(exe_game, game)
    return None


def _bridge_formats():
    """(game, rw_version, col_version) for this export — from the scene game."""
    from ..core import game_versions as gv
    game = bridge_game()
    return game, gv.rw_version_for_game(game), gv.profile_for(game).col_version


def _model_name_limit(game: str) -> int:
    """Longest model name the game accepts (buffer minus the NUL).
    SA: m_name[24] → 23. III: m_name[24] too, but the COL1 header stores
    name[22] and the loader memcpy's it together with the u16 model id, so
    the name must be NUL-terminated within 22 bytes → 21. VC: the model
    info itself is only MAX_MODEL_NAME=21 (reVC BaseModelInfo.h, strncpy
    without a forced NUL) → 20."""
    return {'SA': 23, 'VC': 20}.get(game, 21)


def _lod_model_name(name: str, game: str) -> str:
    """Name of the LOD model paired with ``name``.

    SA links HD↔LOD through the IPL ``lod`` column, so any name works and
    ariane's convention is ``LOD<name>``. III/VC have no such column: the
    engine pairs a big building with its LOD by NAME, comparing
    ``m_name+3`` (CSimpleModelInfo::FindRelatedModel) — the LOD is the HD
    name with its first three characters replaced by ``LOD``."""
    if game == 'SA':
        return ("LOD" + name)[:23]
    return "LOD" + name[3:]


def _rw_text(v: int) -> str:
    """0x36003 → '3.6.0.3'."""
    return f"{(v >> 16) & 0xF}.{(v >> 12) & 0xF}.{(v >> 8) & 0xF}.{v & 0xFF}"


# bridge job-format version — both sides write/parse "#v N" and warn on mismatch
_PROTO_VER = 2

# last-activity status shown in the panel (so the link isn't blind).
# 'ack' = (ok, err) reported back by ariane after a → Ariane send, or None.
_status = {'imported': 0, 'errors': 0, 'skipped': 0, 'sent': 0, 'ack': None}


def _parse_flags(line: str) -> dict:
    """Parse a ``#flags auto_txd=1 vanilla=1 ide=0 ipl=0`` header line."""
    flags = {'auto_txd': True, 'vanilla': True, 'ide': False, 'ipl': False}
    for tok in line.split()[1:]:
        if '=' in tok:
            k, v = tok.split('=', 1)
            flags[k.strip()] = (v.strip() == '1')
    return flags


def _apply_meta(objs, meta: dict, flags: dict) -> None:
    """Place (IPL) and tag (IDE) freshly imported objects from job metadata."""
    if flags.get('ipl'):
        try:
            from mathutils import Quaternion
            loc = (float(meta.get('x', 0.0)), float(meta.get('y', 0.0)),
                   float(meta.get('z', 0.0)))
            # INU IPL convention (ide_ipl.py): Quaternion(w, -x, -y, -z)
            q = Quaternion((float(meta.get('qw', 1.0)), -float(meta.get('qx', 0.0)),
                            -float(meta.get('qy', 0.0)), -float(meta.get('qz', 0.0))))
            for o in objs:
                if o.parent is None:          # move roots only; children follow
                    o.location = loc
                    o.rotation_mode = 'QUATERNION'
                    o.rotation_quaternion = q
        except Exception as exc:              # noqa: BLE001
            print(f"[ariane bridge] IPL place failed: {exc}")

    # IDE props (model id, draw distance, txd) are ALWAYS loaded — the meta line always
    # carries them, and the object needs its real draw distance so the IDE→ariane reverse
    # sends the actual value, not the 299 default. (No longer gated by the 'ide' flag.)
    try:
        mid = int(float(meta.get('id', 0)))
        dd = float(meta.get('dd', 299.0))
        txd = (meta.get('txd', '') or '').strip()
        for o in objs:
            inu = getattr(o, 'inu', None)
            if inu is None:
                continue
            for attr, val in (('model_id', mid), ('draw_distance', dd),
                              ('txd_name', txd if txd else None)):
                if val is None:
                    continue
                try:
                    setattr(inu, attr, val)
                except Exception:         # noqa: BLE001
                    pass
    except Exception as exc:              # noqa: BLE001
        print(f"[ariane bridge] IDE props failed: {exc}")


# Import work is QUEUED and processed a little per timer tick, so Blender stays
# responsive (with a progress bar) even for a big batch of models.
_import_queue = []       # list of (dff_path, meta, flags)
_import_total = 0        # models in the current batch (for the % bar)
_import_running = False
_import_cleanup = set()   # inbox files to delete once the WHOLE batch is done — a model
                          # reused by several instances is referenced by several entries,
                          # so we can't delete its dff after the first or the rest go missing


def _enqueue_job(inbox: str, lines) -> int:
    """Parse one job file into (dff, meta, flags) work items on _import_queue."""
    flags = {'auto_txd': True, 'vanilla': True, 'ide': False, 'ipl': False}
    added = 0
    for ln in lines:
        if not ln.strip():
            continue
        if ln.startswith('#'):                    # header lines (#v N, #flags ...)
            if ln.startswith('#v '):
                try:
                    v = int(ln[3:].strip())
                    if v != _PROTO_VER:
                        print(f"[ariane bridge] job protocol v{v} "
                              f"(addon expects {_PROTO_VER}) — update one side")
                except ValueError:
                    pass
            elif ln.startswith('#flags'):
                flags = _parse_flags(ln)
            continue
        parts = ln.split('\t')
        meta = {}
        for kv in parts[1:]:
            if '=' in kv:
                k, v = kv.split('=', 1)
                meta[k.strip()] = v.strip()
        dff = os.path.join(inbox, os.path.basename(parts[0].strip()))
        if os.path.isfile(dff):
            _import_queue.append((dff, meta, dict(flags)))
            added += 1
        else:
            print(f"[ariane bridge] missing {parts[0].strip()}")
    return added


def _already_in_scene(dff, meta) -> bool:
    """True if this placement is already imported — so a second Export-to-Blender
    doesn't stack a duplicate.

    Настоящий дубль = ТА ЖЕ модель в ТОЙ ЖЕ точке (имя + позиция ~0.5). По
    одному guid матчить НЕЛЬЗЯ: Ariane может слать один guid на МНОГО разных
    моделей (весь IPL, напр. «…LAw2#0») — тогда все, кроме первой, ложно
    скипались, а их LOD'ы (без guid) импортились → «только лоды».
    guid используется как дополнительная привязка, не как единственная."""
    import bpy
    name = os.path.splitext(os.path.basename(dff))[0]
    guid = (meta.get('guid') or '').strip()
    try:
        mx, my, mz = float(meta['x']), float(meta['y']), float(meta['z'])
    except (KeyError, ValueError, TypeError):
        # Нет позиции — матчим по guid + имя (guid+имя, не guid в одиночку).
        if guid:
            return any(o.get('ariane_guid') == guid
                       and o.get('ariane_name') == name
                       for o in bpy.data.objects)
        return False                              # нечего сравнивать → импортируем
    for o in bpy.data.objects:
        if o.get('ariane_name') != name:
            continue
        t = o.matrix_world.translation
        if abs(t.x - mx) < 0.5 and abs(t.y - my) < 0.5 and abs(t.z - mz) < 0.5:
            return True
    return False


def _import_one_entry(dff, meta, flags) -> None:
    """Import + place a single DFF, then drop its inbox transient."""
    import bpy
    ctx = bpy.context
    # Skip a re-import of something already in the scene (dedup, not duplicate). Still
    # queue the inbox file for cleanup so it doesn't leak when every entry is skipped.
    if _already_in_scene(dff, meta):
        base0 = os.path.splitext(dff)[0]
        _import_cleanup.update((dff, base0 + '.txd', base0 + '.col'))
        _status['skipped'] = _status.get('skipped', 0) + 1
        print(f"[ariane bridge] skip re-import (already in scene): "
              f"{os.path.basename(dff)} {meta.get('guid', '')}")
        return
    settings = getattr(ctx.scene, 'inu_settings', None)
    if settings is not None:
        try:
            settings.gtatools_txd_auto_import = bool(flags.get('auto_txd', True))
        except Exception:                     # noqa: BLE001
            pass
    is_vanilla = bool(flags.get('vanilla', True))
    link_alpha = not is_vanilla

    # R↔B своп теперь автоматический — по режиму игры (III/VC), см.
    # txd_import._textures_to_blender_images. Мосту ничего делать не нужно.
    before = set(bpy.data.objects)
    try:
        stats = _init_import_stats({})
        _txd_hint = (meta.get('txd', '') or '').strip() or None
        # Ariane's «Vanilla» flag drives the SAME weld path as the file-picker
        # «Стандартная модель GTA SA (vanilla)» toggle (weld_sharpen). Without it
        # the bridge always fell back to the addon pref (usually OFF = custom
        # path), which keeps GTA's reverse-wound double faces → red flipped
        # normals in Face Orientation. Vanilla map models need the weld+dedup.
        for _ in import_one_dff(dff, ctx, stats, import_game=None,
                                link_alpha=link_alpha, txd_hint=_txd_hint,
                                weld_sharpen=is_vanilla):
            pass
    except Exception as exc:                  # noqa: BLE001
        # Модель могла успеть импортироваться ДО ошибки (напр. на авто-TXD) —
        # не теряем её, разместим ниже вместе с успешными.
        print(f"[ariane bridge] import error for {os.path.basename(dff)}: {exc}")
        _status['errors'] += 1

    # Разместить/тегнуть ВСЁ, что реально появилось в сцене — даже если
    # import_one_dff упал позже. Иначе модель есть, но без размещения/тега, а
    # её LOD (отдельная запись) встаёт нормально → «только лоды».
    new_objs = [o for o in bpy.data.objects if o not in before]
    if new_objs:
        mdl_name = os.path.splitext(os.path.basename(dff))[0]
        guid = (meta.get('guid') or '').strip()
        for o in new_objs:
            o['ariane_name'] = mdl_name
            if 'iid' in meta:
                try:
                    o['ariane_iid'] = int(meta['iid'])
                except (TypeError, ValueError):
                    pass
            if guid:                              # stable cross-session instance id
                o['ariane_guid'] = guid
            else:
                # No guid = an imported LOD/HD display companion (ariane sent iid=-1). It's
                # not a real tracked instance, so it must NOT be treated as a "new model" on
                # Export (that spawned phantom instances) nor moved back.
                o['ariane_companion'] = True
        _apply_meta(new_objs, meta, flags)
        # optional collision alongside the model (present only if ariane sent one).
        # bulk_mode=True → no separate «Collision» collection and no sphere/box
        # empties; drop the COL mesh into the model's own collection and place it
        # at the same transform so it overlays the model.
        col_path = os.path.splitext(dff)[0] + '.col'
        if os.path.exists(col_path):
            try:
                from ..core.col import read_col_file
                from .col_import import import_col_from_models
                dest = (new_objs[0].users_collection[0]
                        if (new_objs and new_objs[0].users_collection)
                        else ctx.collection)
                col_objs = import_col_from_models(
                    read_col_file(col_path), bulk_mode=True,
                    target_collection=dest, material_cache={}) or []
                # Align COL to the VISIBLE mesh's world matrix, not just the IPL
                # root: import_one_dff bakes each frame's rotation into the mesh's
                # matrix_basis, so the model = root(IPL) × frame. Flat COL geometry
                # has no frame, so placing it only at the IPL root leaves it rotated
                # by that frame. Copy the mesh's full world matrix instead.
                ctx.view_layer.update()
                vis_mesh = max((o for o in new_objs if o.type == 'MESH'),
                               key=lambda o: len(o.data.vertices), default=None)
                if vis_mesh is not None:
                    mw = vis_mesh.matrix_world.copy()
                    for co in col_objs:
                        co.matrix_world = mw
                else:
                    _apply_meta(col_objs, meta, flags)
                for co in col_objs:
                    co['ariane_name'] = mdl_name
                    co['ariane_is_col'] = True
            except Exception as exc:                  # noqa: BLE001
                print(f"[ariane bridge] import COL skipped for {mdl_name}: {exc}")
        _status['imported'] += 1
    # Defer inbox cleanup to the end of the batch: the same dff may be referenced by
    # several instances (GTA3 land reuses one model), and deleting it now would make the
    # later entries fail to import. _finish_import() removes these once the queue drains.
    base = os.path.splitext(dff)[0]
    _import_cleanup.update((dff, base + '.txd', base + '.col'))


def _finish_import():
    global _import_running
    _import_running = False
    # now that the whole batch is imported, drop the inbox transients
    for pth in _import_cleanup:
        try:
            os.remove(pth)
        except OSError:
            pass
    _import_cleanup.clear()
    import bpy
    try:
        bpy.context.window_manager.progress_end()
    except Exception:                         # noqa: BLE001
        pass
    try:
        bpy.context.workspace.status_text_set(None)
    except Exception:                         # noqa: BLE001
        pass
    print(f"[ariane bridge] import done: {_status['imported']} ok, "
          f"{_status['errors']} err, {_status['skipped']} skipped (already in scene)")


def _import_driver():
    """Timer: import a slice of the queue per tick, yielding to keep the UI live."""
    import bpy
    import time as _time
    if not _import_queue:
        _finish_import()
        return None
    wm = bpy.context.window_manager
    deadline = _time.monotonic() + 0.05          # ~20 fps budget per tick
    while _import_queue and _time.monotonic() < deadline:
        dff, meta, flags = _import_queue.pop(0)
        _import_one_entry(dff, meta, flags)
    done = _import_total - len(_import_queue)
    try:
        wm.progress_update(int(100 * done / max(_import_total, 1)))
    except Exception:                         # noqa: BLE001
        pass
    try:
        bpy.context.workspace.status_text_set(f"Ariane импорт: {done}/{_import_total}")
    except Exception:                         # noqa: BLE001
        pass
    if not _import_queue:
        _finish_import()
        return None
    return 0.01


def _start_import_driver():
    global _import_running
    if _import_running:
        return
    _import_running = True
    import bpy
    try:
        bpy.context.window_manager.progress_begin(0, 100)
    except Exception:                         # noqa: BLE001
        pass
    if not bpy.app.timers.is_registered(_import_driver):
        bpy.app.timers.register(_import_driver, first_interval=0.0)


def process_jobs() -> int:
    """Enqueue every DFF listed in the inbox's ``*.job`` files and kick the
    background import driver (non-blocking). Returns how many were enqueued."""
    inbox = inbox_dir()
    if not os.path.isdir(inbox):
        return 0
    try:
        jobs = sorted(f for f in os.listdir(inbox) if f.lower().endswith('.job'))
    except OSError:
        return 0
    if not jobs:
        return 0

    global _import_total
    if not _import_queue:                     # fresh batch → reset counters/total
        _status['imported'] = 0
        _status['errors'] = 0
        _status['skipped'] = 0
        _import_total = 0
    before = len(_import_queue)
    for job in jobs:
        jpath = os.path.join(inbox, job)
        try:
            with open(jpath, 'r', encoding='utf-8', errors='replace') as fh:
                lines = [ln.rstrip('\n') for ln in fh]
        except OSError:
            continue
        try:
            _enqueue_job(inbox, lines)
        except Exception as exc:              # noqa: BLE001
            print(f"[ariane bridge] job {job} error: {exc}")
        try:
            os.remove(jpath)
        except OSError:
            pass
    added = len(_import_queue) - before
    _import_total += added
    if _import_queue:
        _start_import_driver()
    return added


# ── reverse: send edited model(s) back to ariane ────────────────

def outbox_dir() -> str:
    return os.path.join(bridge_base(), 'outbox')


def _ariane_name_of(obj) -> str:
    n = obj.get('ariane_name')
    if n:
        return str(n)
    base = obj.name
    if len(base) > 4 and base[-4] == '.' and base[-3:].isdigit():
        base = base[:-4]          # strip Blender's ".001" dedup suffix
    return base


def _find_col_object(name: str):
    """Find the collision mesh for model ``name`` — the bridge tags imported COL
    with ariane_is_col/ariane_name; otherwise fall back to a ``<name>_COL`` mesh."""
    import bpy
    for o in bpy.data.objects:
        if getattr(o, 'type', None) == 'MESH' \
                and o.get('ariane_is_col') and o.get('ariane_name') == name:
            return o
    want = (name + "_col").lower()
    for o in bpy.data.objects:
        if getattr(o, 'type', None) == 'MESH' and o.name.lower().startswith(want):
            return o
    return None


def _export_col_local(src_obj, name: str, outbox: str, version: int = 3) -> None:
    """Export ``src_obj``'s collision in LOCAL space. export_col bakes the object's
    matrix_world rotation into the verts, so we hand it a throwaway object at the
    identity transform sharing the same mesh data → ariane gets clean model-local
    collision (no display rotation baked in), mirroring how export_dff stays local.
    ``version``: 3 (SA) or 1 (III/VC — their loaders assert the 'COLL' ident)."""
    import bpy
    tmp = bpy.data.objects.new(name + "__col_tmp", src_obj.data)
    bpy.context.scene.collection.objects.link(tmp)
    try:
        export_col(os.path.join(outbox, name + '.col'), [tmp],
                   version=version, model_name=name)
    finally:
        bpy.data.objects.remove(tmp, do_unlink=True)


def send_to_ariane(objects) -> int:
    """Export selected meshes as DFF (+TXD) into the outbox and write a single
    ``reload.job`` so ariane hot-reloads geometry/textures and (via the tagged
    instance id) moves the instance to the object's current transform."""
    import bpy

    # Skip imported LOD/HD display companions (no real instance behind them, iid=-1): they
    # must not be hot-reloaded, moved, or turned into phantom new models in ariane.
    meshes = [o for o in objects
              if getattr(o, 'type', None) == 'MESH'
              and not o.get('ariane_companion') and o.get('ariane_iid') != -1]
    if not meshes:
        return 0
    send_pos = True
    want_col = False
    want_lod = True
    want_ide = False
    try:
        s = bpy.context.scene.inu_settings
        send_pos = bool(s.ariane_send_position)
        want_col = bool(s.ariane_send_col)
        want_lod = bool(s.ariane_send_lod)
        want_ide = bool(s.ariane_send_ide)
    except Exception:                                     # noqa: BLE001
        pass
    outbox = outbox_dir()
    os.makedirs(outbox, exist_ok=True)

    view = bpy.context.view_layer
    prev_active = view.objects.active
    prev_sel = list(bpy.context.selected_objects)

    # Instance authoring: a Blender duplicate (Shift+D) inherits the original's
    # ariane_guid → it points at the SAME ariane instance. Detect duplicates (a guid
    # shared by >1 object) and create fresh instances for the non-keepers, so simply
    # copying in Blender + Export = new instances (no separate button).
    guid_owners = {}
    for o in bpy.data.objects:
        g = o.get('ariane_guid')
        if g:
            guid_owners.setdefault(g, []).append(o)

    def _needs_new_instance(o):
        if not _ariane_name_of(o):
            return False
        if o.get('ariane_companion') or o.get('ariane_iid') == -1:
            return False                            # imported LOD/HD companion — not an instance
        g = o.get('ariane_guid')
        if not g:
            return True                              # references a model, no instance
        grp = guid_owners.get(g, [])
        return len(grp) > 1 and o is not min(grp, key=lambda x: x.name)  # duplicate

    _created = 0
    to_create = [o for o in meshes if _needs_new_instance(o)]
    if to_create:
        _created = create_in_ariane(to_create)       # async: places + tags new guids
        meshes = [o for o in meshes if o not in to_create]
    if not meshes:
        return _created

    _game, _rw_ver, _col_ver = _bridge_formats()
    _mm = bridge_game_mismatch()
    if _mm:
        print(f"[ariane bridge] {_mm}")

    def _export_one(obj, name, with_col, do_move):
        """DFF (+TXD always, +COL if asked) → outbox; returns the job line or None."""
        # Меш + прикреплённые 2DFX-пустышки (прямые дети) — ровно как в
        # основном экспорте (_export_model_group), тем же export_dff. Иначе в
        # Ariane улетит DFF без эффектов (короны/частицы/…).
        _fx = [c for c in obj.children
               if c.type == 'EMPTY'
               and getattr(getattr(c, 'inu', None), 'type', '') == '2DFX']
        try:
            export_dff(os.path.join(outbox, name + '.dff'), [obj] + _fx, version=_rw_ver)
        except Exception as exc:                          # noqa: BLE001
            print(f"[ariane bridge] export DFF failed for {name}: {exc}")
            return None
        txd_ok = 0
        try:
            for o in bpy.data.objects:
                o.select_set(False)
            obj.select_set(True)
            view.objects.active = obj
            bpy.ops.gtatools.export_txd(
                filepath=os.path.join(outbox, name + '.txd'), selected_only=True)
            txd_ok = 1
        except Exception as exc:                          # noqa: BLE001
            print(f"[ariane bridge] export TXD skipped for {name}: {exc}")
        col_ok = 0
        if with_col:
            col_src = _find_col_object(name)
            if col_src is not None:
                try:
                    _export_col_local(col_src, name, outbox, version=_col_ver)
                    col_ok = 1
                except Exception as exc:                  # noqa: BLE001
                    print(f"[ariane bridge] export COL failed for {name}: {exc}")
            else:
                print(f"[ariane bridge] no _COL mesh for {name}, collision not sent")
        parts = [name, "dff=1", f"txd={txd_ok}", f"col={col_ok}"]
        if want_ide:                                      # IDE draw distance back to ariane
            try:
                dd = float(obj.inu.draw_distance)
                if dd > 0.0:
                    parts.append(f"dd={dd:.3f}")
            except (AttributeError, TypeError, ValueError):
                pass
        if do_move:
            # world transform → GTA space (inverse of the import convention)
            loc, quat, _scale = obj.matrix_world.decompose()
            gx, gy, gz, gw = -quat.x, -quat.y, -quat.z, quat.w
            try:
                iid = int(obj.get('ariane_iid', -1))
            except (TypeError, ValueError):
                iid = -1
            parts.append(f"iid={iid}")
            g = (obj.get('ariane_guid') or '').strip()
            if g:                                         # stable id preferred by ariane
                parts.append(f"guid={g}")
            parts += [f"x={loc.x:.4f}", f"y={loc.y:.4f}", f"z={loc.z:.4f}",
                      f"qx={gx:.6f}", f"qy={gy:.6f}", f"qz={gz:.6f}", f"qw={gw:.6f}"]
        else:
            parts.append("iid=-1")                        # no move
        return "\t".join(parts)

    lines = []
    sent = set()
    for obj in meshes:
        name = _ariane_name_of(obj)
        if name in sent:
            continue
        ln = _export_one(obj, name, want_col, send_pos)
        if ln is None:
            continue
        lines.append(ln)
        sent.add(name)
        # LOD counterpart: object whose ariane name is the LOD name of <name>
        # (SA: "LOD<name>", III/VC: "LOD"+name[3:]) — geometry only
        if want_lod:
            lod_name = _lod_model_name(name, _game)
            if lod_name not in sent:
                lod_obj = next((o for o in bpy.data.objects
                                if getattr(o, 'type', None) == 'MESH'
                                and _ariane_name_of(o) == lod_name), None)
                if lod_obj is not None:
                    lln = _export_one(lod_obj, lod_name, False, False)
                    if lln:
                        lines.append(lln)
                        sent.add(lod_name)

    # restore the user's selection
    try:
        for o in bpy.data.objects:
            o.select_set(False)
        for o in prev_sel:
            try:
                o.select_set(True)
            except Exception:                             # noqa: BLE001
                pass
        view.objects.active = prev_active
    except Exception:                                     # noqa: BLE001
        pass

    if lines:
        tmp = os.path.join(outbox, 'reload.job.tmp')
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(f"#v {_PROTO_VER}\n")
            fh.write('\n'.join(lines) + '\n')
        os.replace(tmp, os.path.join(outbox, 'reload.job'))   # atomic
        _status['ack'] = None                     # cleared; ariane will report back
        _start_ack_waiter()
    _status['sent'] = len(lines)
    return len(lines) + _created


def send_positions_to_ariane(objects) -> int:
    """Position-only reverse: write a ``reload.job`` that moves each tagged
    instance to its current transform WITHOUT exporting any DFF/TXD. Lines carry
    ``pos=1`` so ariane skips the geometry reload and just relocates the instance
    (visual only — ariane persists to IPL on its own save). Objects without an
    ariane instance id (guid or iid) are skipped."""
    import bpy

    meshes = [o for o in objects if getattr(o, 'type', None) == 'MESH']
    if not meshes:
        return 0

    lines = []
    skipped = 0
    for obj in meshes:
        try:
            iid = int(obj.get('ariane_iid', -1))
        except (TypeError, ValueError):
            iid = -1
        guid = (obj.get('ariane_guid') or '').strip()
        if iid < 0 and not guid:          # no instance to move → nothing to send
            skipped += 1
            continue
        name = _ariane_name_of(obj)
        loc, quat, _scale = obj.matrix_world.decompose()
        gx, gy, gz, gw = -quat.x, -quat.y, -quat.z, quat.w
        toks = [name, f"iid={iid}", "pos=1"]
        if guid:
            toks.append(f"guid={guid}")
        toks += [f"x={loc.x:.4f}", f"y={loc.y:.4f}", f"z={loc.z:.4f}",
                 f"qx={gx:.6f}", f"qy={gy:.6f}", f"qz={gz:.6f}", f"qw={gw:.6f}"]
        lines.append("\t".join(toks))

    if lines:
        outbox = outbox_dir()
        os.makedirs(outbox, exist_ok=True)
        tmp = os.path.join(outbox, 'reload.job.tmp')
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(f"#v {_PROTO_VER}\n")
            fh.write('\n'.join(lines) + '\n')
        os.replace(tmp, os.path.join(outbox, 'reload.job'))   # atomic
        _status['ack'] = None
        _start_ack_waiter()
    _status['sent'] = len(lines)
    if skipped:
        print(f"[ariane bridge] position update: {skipped} object(s) without ariane_iid skipped")
    return len(lines)


# ── reverse ack: read ariane's <outbox>\reload.done after a send ─────

_ack_tries = 0


def _read_ack() -> bool:
    """Consume ariane's ack (reload.done) if present → _status['ack']=(ok,err)."""
    path = os.path.join(outbox_dir(), 'reload.done')
    if not os.path.isfile(path):
        return False
    ok = err = 0
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            for tok in fh.read().split():
                if tok.startswith('ok='):
                    ok = int(tok[3:])
                elif tok.startswith('err='):
                    err = int(tok[4:])
    except Exception:                             # noqa: BLE001
        pass
    _status['ack'] = (ok, err)
    try:
        os.remove(path)
    except OSError:
        pass
    return True


def _ack_waiter():
    global _ack_tries
    if _read_ack():
        return None
    _ack_tries += 1
    if _ack_tries > 30:                           # ~15 s, then give up
        return None
    return 0.5


def _start_ack_waiter():
    global _ack_tries
    _ack_tries = 0
    if not bpy.app.timers.is_registered(_ack_waiter):
        bpy.app.timers.register(_ack_waiter, first_interval=0.5)


# ── Phase E-1: create new instances of existing models ───────────

_create_tries = 0


def create_in_ariane(objects) -> int:
    """Ask ariane to create a NEW instance of each selected object's model at its
    current transform (added to ariane's open IPL, persisted on the user's save).
    ariane replies with a stable guid per object which we tag back on."""
    meshes = [o for o in objects if getattr(o, 'type', None) == 'MESH']
    if not meshes:
        return 0
    lines = []
    for obj in meshes:
        name = _ariane_name_of(obj)
        if not name:
            continue
        obj['ariane_name'] = name                 # remember the model for later sends
        loc, quat, _s = obj.matrix_world.decompose()
        gx, gy, gz, gw = -quat.x, -quat.y, -quat.z, quat.w
        lines.append(
            f"key={obj.name}\tname={name}\t"
            f"x={loc.x:.4f}\ty={loc.y:.4f}\tz={loc.z:.4f}\t"
            f"qx={gx:.6f}\tqy={gy:.6f}\tqz={gz:.6f}\tqw={gw:.6f}")
    if not lines:
        return 0
    outbox = outbox_dir()
    os.makedirs(outbox, exist_ok=True)
    tmp = os.path.join(outbox, 'create.job.tmp')
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(f"#v {_PROTO_VER}\n")
        fh.write('\n'.join(lines) + '\n')
    os.replace(tmp, os.path.join(outbox, 'create.job'))
    _start_create_waiter()
    return len(lines)


def _read_create_ack() -> bool:
    """Consume ariane's create.done → tag each object with its new guid."""
    path = os.path.join(outbox_dir(), 'create.done')
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding='utf-8') as fh:
            data = fh.read()
    except OSError:
        return False
    ok = 0
    for ln in data.splitlines():
        p = ln.split('\t')
        if len(p) < 2:
            continue
        obj = bpy.data.objects.get(p[0])
        if obj is None or not p[1] or p[1] == 'ERR':
            continue
        obj['ariane_guid'] = p[1]
        ok += 1
    try:
        os.remove(path)
    except OSError:
        pass
    _status['ack'] = (ok, 0)
    return True


def _create_waiter():
    global _create_tries
    if _read_create_ack():
        return None
    _create_tries += 1
    if _create_tries > 40:                        # ~10 s then give up
        return None
    return 0.25


def _start_create_waiter():
    global _create_tries
    _create_tries = 0
    if not bpy.app.timers.is_registered(_create_waiter):
        bpy.app.timers.register(_create_waiter, first_interval=0.25)


# ── Phase E-2: create BRAND-NEW models (new geometry) ────────────

_create_model_tries = 0


def _sanitize_model_name(raw: str, game: str = 'SA') -> str:
    """GTA model name: letters/digits/underscore, lowercase, ≤23 chars (SA),
    ≤21 (III), ≤20 (VC) — see ``_model_name_limit``. III/VC pair LOD↔HD on
    ``name[3:]``, so a name shorter than 4 chars would match every other
    short name — pad it."""
    import re
    s = re.sub(r'[^0-9A-Za-z_]', '_', raw or '').strip('_').lower()
    if not s:
        s = 'model'
    if s[0].isdigit():
        s = 'm' + s
    if game != 'SA':
        s = s.ljust(4, '0')
    return s[:_model_name_limit(game)]


def _spawn_scene_lod(main, base_name):
    """Создать <base>_LOD как редактируемую копию основной модели (если её ещё
    нет). Чтобы авто-LOD можно было потом поправить и переслать в ariane."""
    import bpy
    lname = base_name + "_LOD"
    if bpy.data.objects.get(lname) is not None:
        return None
    obj = bpy.data.objects.new(lname, main.data.copy())
    obj.matrix_world = main.matrix_world.copy()
    for c in (list(main.users_collection) or [bpy.context.scene.collection]):
        c.objects.link(obj)
    return obj


def _spawn_scene_col(main, base_name, box=True):
    """Создать <base>_COL (заготовку коллизии, inu.type=COL), если её ещё нет.
    box=True → габаритный бокс (для пустой COL); box=False → копия геометрии
    основной модели (для COL, построенной из основной). Чтобы авто-COL можно
    было отредактировать и переслать."""
    import bpy
    from mathutils import Vector
    cname = base_name + "_COL"
    if bpy.data.objects.get(cname) is not None:
        return None
    if box:
        bb = [Vector(c) for c in main.bound_box]           # 8 углов, локальные коорд.
        mn = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
        mx = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
        verts = [(mn.x, mn.y, mn.z), (mx.x, mn.y, mn.z), (mx.x, mx.y, mn.z), (mn.x, mx.y, mn.z),
                 (mn.x, mn.y, mx.z), (mx.x, mn.y, mx.z), (mx.x, mx.y, mx.z), (mn.x, mx.y, mx.z)]
        faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        me = bpy.data.meshes.new(cname)
        me.from_pydata(verts, [], faces)
        me.update()
    else:
        me = main.data.copy()                              # копия геометрии основной
        me.name = cname
    obj = bpy.data.objects.new(cname, me)
    obj.matrix_world = main.matrix_world.copy()
    if hasattr(obj, 'inu'):
        obj.inu.type = 'COL'
    for c in (list(main.users_collection) or [bpy.context.scene.collection]):
        c.objects.link(obj)
    return obj


def create_model_in_ariane(objects, auto_lod=True, empty_col=True) -> int:
    """Register each selected mesh as a NEW model in ariane (DFF+TXD exported, COL
    auto-generated), placed at its transform. ariane allocates a free id, writes
    custom.ide + Mod Loader manifest, and replies with a stable guid we tag back.

    empty_col: when a group has no real _COL sibling, attach an EMPTY collision
    (no faces, but real bounds from the visual mesh so GTA doesn't cull it) instead
    of leaving col=0 (which makes ariane build solid collision from the geometry).
    A brand-new custom model usually wants a clean, non-solid COL it can shape later."""
    import bpy
    from ..tools.model_utils import find_all_selected_model_groups
    if not any(getattr(o, 'type', None) == 'MESH' for o in objects):
        return 0
    # Группируем выделенное по базовому имени: 123_DFF / 123_LOD / 123_COL →
    # ОДНА модель «123» (DFF=основной меш, LOD/COL — реальные соседи по группе).
    groups = find_all_selected_model_groups()
    if not groups:
        return 0
    outbox = outbox_dir()
    os.makedirs(outbox, exist_ok=True)
    view = bpy.context.view_layer
    prev_active = view.objects.active
    prev_sel = list(bpy.context.selected_objects)

    game, rw_ver, col_ver = _bridge_formats()
    _mm = bridge_game_mismatch()
    if _mm:
        print(f"[ariane bridge] {_mm}")
    _nlim = _model_name_limit(game)

    lines = []
    used = set()
    _spawn = []      # (main, base_name, make_lod, make_col) — создать в сцене
    for base_name, models in groups.items():
        main = models['DFF'] or models['LOD']       # основной меш модели
        if main is None:
            continue
        name = _sanitize_model_name(base_name, game)
        base, i = name, 1
        while name in used:
            name = f"{base[:_nlim - 3]}_{i}"; i += 1
        used.add(name)
        try:
            export_dff(os.path.join(outbox, name + '.dff'), [main], version=rw_ver)
        except Exception as exc:                          # noqa: BLE001
            print(f"[ariane bridge] export DFF failed for {name}: {exc}")
            continue
        try:
            for o in bpy.data.objects:
                o.select_set(False)
            main.select_set(True)
            view.objects.active = main
            bpy.ops.gtatools.export_txd(
                filepath=os.path.join(outbox, name + '.txd'), selected_only=True)
        except Exception as exc:                          # noqa: BLE001
            print(f"[ariane bridge] export TXD failed for {name}: {exc}")
            continue

        # COL, если у группы нет реального _COL — генерируем ВСЕГДА (col=1) и
        # создаём заготовку в сцене:
        #   empty_col ВКЛ → ПУСТАЯ (габаритная) COL  → в сцене _COL = бокс;
        #   empty_col ВЫКЛ → COL из ГЕОМЕТРИИ основной → в сцене _COL = копия основной.
        col = 0
        col_obj = models['COL']
        _col_mode = None      # что создать в сцене: 'box' | 'copy' | None
        try:
            if col_obj is not None:
                _export_col_local(col_obj, name, outbox, version=col_ver)   # реальный сосед _COL
                col = 1
            elif empty_col:
                # bounds от видимого меша (main), чтобы culling-сфера не была
                # нулевой; сама геометрия пропускается (empty=True).
                from .col_export import export_col as _export_col
                _export_col(os.path.join(outbox, name + '.col'), [main],
                            version=col_ver, model_name=name, empty=True,
                            bounds_ref=[main])
                col = 1
                _col_mode = 'box'
            else:
                _export_col_local(main, name, outbox, version=col_ver)      # COL из геометрии основной
                col = 1
                _col_mode = 'copy'
        except Exception as exc:                              # noqa: BLE001
            print(f"[ariane bridge] COL export failed for {name}: {exc}")
            col = 0
            _col_mode = None

        # LOD of the group → register a LOD model named LOD<name> (SA) or
        # LOD+name[3:] (III/VC pair by name, see _lod_model_name). When the DFF
        # is the main mesh: real _LOD sibling if present; else (auto_lod ON) a
        # copy of the main model as the LOD; else no LOD.
        lod = 0
        lod_name = ""
        lod_obj = None
        if models['DFF'] is not None:
            if models['LOD'] is not None:
                lod_obj = models['LOD']
            elif auto_lod:
                lod_obj = main            # авто-LOD из основной модели
        if lod_obj is not None:
            lod_name = _lod_model_name(name, game)
            try:
                export_dff(os.path.join(outbox, lod_name + '.dff'), [lod_obj], version=rw_ver)
                for o in bpy.data.objects:
                    o.select_set(False)
                lod_obj.select_set(True)
                view.objects.active = lod_obj
                bpy.ops.gtatools.export_txd(
                    filepath=os.path.join(outbox, lod_name + '.txd'), selected_only=True)
                lod = 1
            except Exception as exc:                      # noqa: BLE001
                print(f"[ariane bridge] export LOD failed for {lod_name}: {exc}")
                lod = 0

        # Авто-сгенерённые LOD/COL создаём и объектами в сцене (<base>_LOD /
        # <base>_COL) — чтобы их можно было отредактировать и переслать.
        _made_lod = (models['LOD'] is None and lod_obj is main and lod == 1)
        if _made_lod or _col_mode:
            _spawn.append((main, base_name, name, _made_lod, _col_mode))

        loc, quat, _s = main.matrix_world.decompose()
        gx, gy, gz, gw = -quat.x, -quat.y, -quat.z, quat.w
        lines.append(
            f"key={main.name}\tname={name}\tdd=300.0\tcol={col}\tlod={lod}\tlodname={lod_name}\t"
            f"x={loc.x:.4f}\ty={loc.y:.4f}\tz={loc.z:.4f}\t"
            f"qx={gx:.6f}\tqy={gy:.6f}\tqz={gz:.6f}\tqw={gw:.6f}")

    try:                                                  # restore selection
        for o in bpy.data.objects:
            o.select_set(False)
        for o in prev_sel:
            try:
                o.select_set(True)
            except Exception:                             # noqa: BLE001
                pass
        view.objects.active = prev_active
    except Exception:                                     # noqa: BLE001
        pass

    # Создать авто-LOD/COL объектами в сцене (после восстановления выделения).
    # Тегируем их ariane-именами, чтобы повторный «Экспорт → Ariane» находил и
    # ОБНОВЛЯЛ их (LOD ищется по ariane_name == "LOD"+имя, COL — по _COL/тегу).
    for _m, _bn, _nm, _dl, _cm in _spawn:
        try:
            if _dl:
                _o = _spawn_scene_lod(_m, _bn)
                if _o is not None:
                    _o['ariane_name'] = _lod_model_name(_nm, game)
                    _o['ariane_companion'] = True
            if _cm:
                _o = _spawn_scene_col(_m, _bn, box=(_cm == 'box'))
                if _o is not None:
                    _o['ariane_name'] = _nm
                    _o['ariane_is_col'] = True
        except Exception as exc:                          # noqa: BLE001
            print(f"[ariane bridge] scene LOD/COL create failed for {_bn}: {exc}")

    if not lines:
        return 0
    tmp = os.path.join(outbox, 'createmodel.job.tmp')
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(f"#v {_PROTO_VER}\n")
        fh.write('\n'.join(lines) + '\n')
    os.replace(tmp, os.path.join(outbox, 'createmodel.job'))
    _start_create_model_waiter()
    return len(lines)


def _read_create_model_ack() -> bool:
    path = os.path.join(outbox_dir(), 'createmodel.done')
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding='utf-8') as fh:
            data = fh.read()
    except OSError:
        return False
    ok, errs = 0, []
    for ln in data.splitlines():
        p = ln.split('\t')
        if len(p) < 2:
            continue
        obj = bpy.data.objects.get(p[0])
        if p[1].startswith('ERR:'):
            errs.append(p[1][4:])
            continue
        if obj is not None and p[1]:
            obj['ariane_guid'] = p[1]
            if len(p) >= 3:
                obj['ariane_name'] = p[2]
            # Model ID, выделенный Ariane созданной модели → в inu.model_id
            # (Ariane может слать «id=/mid=/objid=» или 4-м столбцом числом).
            _mid = None
            for _f in p[3:]:
                if _f.startswith(('id=', 'mid=', 'objid=')):
                    _mid = _f.split('=', 1)[1]
                    break
            if _mid is None and len(p) >= 4 and p[3].strip().lstrip('-').isdigit():
                _mid = p[3].strip()
            if _mid is not None and hasattr(obj, 'inu'):
                try:
                    obj.inu.model_id = int(_mid)
                except (TypeError, ValueError):
                    pass
            ok += 1
    try:
        os.remove(path)
    except OSError:
        pass
    _status['ack'] = (ok, len(errs))
    if errs:
        print("[ariane bridge] create-model errors:", errs)
    return True


def _create_model_waiter():
    global _create_model_tries
    if _read_create_model_ack():
        return None
    _create_model_tries += 1
    if _create_model_tries > 60:                          # ~15 s (model reg is slower)
        return None
    return 0.25


def _start_create_model_waiter():
    global _create_model_tries
    _create_model_tries = 0
    if not bpy.app.timers.is_registered(_create_model_waiter):
        bpy.app.timers.register(_create_model_waiter, first_interval=0.3)


def _find_companion(obj, suffix: str):
    """Mesh named ``<obj.name><suffix>`` (e.g. '_COL' / '_LOD'), case-insensitive."""
    import bpy
    want = (obj.name + suffix).lower()
    for o in bpy.data.objects:
        if getattr(o, 'type', None) == 'MESH' and o.name.lower() == want:
            return o
    return None


class GTATOOLS_OT_ariane_create_model(bpy.types.Operator):
    """Создать НОВУЮ модель в ariane из выделенной геометрии. Шлёт DFF+TXD, реальные
    COL/LOD если есть (<имя>_COL / <имя>_LOD), иначе авто-COL. Новый id, Mod Loader."""

    bl_idname = "gtatools.ariane_create_model"
    bl_label = "Ariane: создать модель"

    auto_lod: BoolProperty(
        name=T("Авто-LOD из основной модели"),
        description=T("Если LOD-меша (<имя>_LOD) в сцене нет — отправить копию "
                      "основной модели как дальний LOD. Выключи, если у модели "
                      "LOD не предусмотрен"),
        default=True,
    )

    empty_col: BoolProperty(
        name=T("Пустая COL если нет своей"),
        description=T("Если у группы нет реального _COL: ВКЛ — пустая "
                      "габаритная COL (без граней, bounds от меша); ВЫКЛ — COL "
                      "из геометрии основной модели. В обоих случаях в сцене "
                      "создаётся объект _COL для правки"),
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return any(getattr(o, 'type', None) == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        from ..tools.model_utils import find_all_selected_model_groups
        from ..core import game_versions as gv
        self._warn = []
        game = bridge_game()
        prof = gv.profile_for(game)
        self._game_line = T("Игра: {0} — DFF/TXD RW {1}, COL{2}, TXD {3}").format(
            game, _rw_text(prof.rw_version), prof.col_version,
            'D3D9' if game == 'SA' else 'D3D8')
        mm = bridge_game_mismatch()
        if mm:
            self._warn.append(mm)
        if game != 'SA':
            self._warn.append(T("{0}: id моделей до {1} (сток) — выше нужен limit adjuster; "
                                "имя модели ≤ {2} символов").format(
                                    game, prof.model_id_max, _model_name_limit(game)))
        # По группам (123_DFF/123_LOD/123_COL → одна модель «123»), а не по
        # каждому мешу: предупреждаем только если у группы реально нет COL/LOD.
        for base_name, models in find_all_selected_model_groups().items():
            if models['COL'] is None:
                self._warn.append(T("{0}: нет своей COL — будет создана автоматически").format(base_name))
            if models['LOD'] is None:
                self._warn.append(T("{0}: нет LOD — авто из основной модели").format(base_name))
        # Диалог показываем ВСЕГДА — в нём галочка «Авто-LOD» + предупреждения.
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=T("Продолжить создание модели?"), icon='QUESTION')
        gl = getattr(self, '_game_line', '')
        if gl:
            col.label(text=gl, icon='INFO')
        for w in getattr(self, '_warn', []):
            col.label(text=w, icon='ERROR')
        col.separator()
        col.prop(self, "auto_lod")
        col.prop(self, "empty_col")

    def execute(self, context):
        n = create_model_in_ariane(context.selected_objects,
                                   auto_lod=self.auto_lod,
                                   empty_col=self.empty_col)
        if n:
            self.report({'INFO'}, T("Отправлено моделей: {0}").format(n))
        else:
            self.report({'WARNING'}, T("Нет выделенных мешей"))
        return {'FINISHED'}


class GTATOOLS_OT_ariane_send(bpy.types.Operator):
    """Отправить выделенные модели обратно в ariane (DFF+TXD+позиция, live-reload)."""

    bl_idname = "gtatools.ariane_send"
    bl_label = "Ariane: отправить обратно"

    def execute(self, context):
        n = send_to_ariane(context.selected_objects)
        if n:
            self.report({'INFO'}, T("В ariane отправлено: {0} модель(ей)").format(n))
        else:
            self.report({'WARNING'}, T("Нет выделенных мешей"))
        return {'FINISHED'}


class GTATOOLS_OT_ariane_send_pos(bpy.types.Operator):
    """Обновить только позицию выделенных моделей в ariane (без экспорта DFF/TXD)."""

    bl_idname = "gtatools.ariane_send_pos"
    bl_label = "Ariane: обновить позицию"

    def execute(self, context):
        n = send_positions_to_ariane(context.selected_objects)
        if n:
            self.report({'INFO'}, T("Позиция обновлена: {0} модель(ей)").format(n))
        else:
            self.report({'WARNING'}, T("Нет моделей с ariane_iid (сначала импортируй из ariane)"))
        return {'FINISHED'}


def _norm_model_name(name: str) -> str:
    """Имя модели без суффиксов импорта карты (_DFF/_LOD/_COL) и .001."""
    n = name or ""
    if len(n) > 4 and n[-4] == '.' and n[-3:].isdigit():
        n = n[:-4]
    low = n.lower()
    for suf in ('_dff', '_lod', '_col'):
        if low.endswith(suf):
            return n[:-4]
    return n


class GTATOOLS_OT_ariane_bind(bpy.types.Operator):
    """Привязать модели к УЖЕ существующим инстансам Ariane — БЕЗ дублей.

    Для сцены, которая уже стоит в карте Ariane (импортировал из файлов игры,
    а не через мост): «Экспорт → Ariane» пытался бы СОЗДАТЬ дубли. Эта кнопка
    вместо создания МАТЧИТ объекты с инстансами Ariane по модель+позиция и
    вешает их guid/iid → после этого live-синк работает.

    Ariane выгружает свой список инстансов в <bridge>\\instances.txt, строка:
        guid <TAB> iid <TAB> model <TAB> x <TAB> y <TAB> z
    """
    bl_idname = "gtatools.ariane_bind"
    bl_label = "INU: Bind to Ariane instances"
    bl_options = {'REGISTER', 'UNDO'}

    only_selected: BoolProperty(
        name="Только выделенные", default=True,
        description="Привязывать только выделенные объекты (иначе всю сцену)")

    def execute(self, context):
        path = os.path.join(bridge_base(), 'instances.txt')
        if not os.path.isfile(path):
            alt = os.path.join(outbox_dir(), 'instances.txt')
            if os.path.isfile(alt):
                path = alt
        if not os.path.isfile(path):
            self.report({'ERROR'}, T("Нет instances.txt от Ariane. Ariane должна "
                        "выгрузить список инстансов: guid<TAB>iid<TAB>model<TAB>x<TAB>y<TAB>z"))
            return {'CANCELLED'}
        insts = []
        try:
            with open(path, encoding='utf-8', errors='replace') as fh:
                for ln in fh:
                    if not ln.strip() or ln.lstrip().startswith('#'):
                        continue
                    p = ln.rstrip('\n').split('\t')
                    if len(p) < 6:
                        continue
                    try:
                        insts.append((p[0], p[1],
                                      _norm_model_name(p[2]).lower(),
                                      float(p[3]), float(p[4]), float(p[5])))
                    except ValueError:
                        continue
        except OSError as e:                          # noqa: BLE001
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if not insts:
            self.report({'ERROR'}, T("instances.txt пуст или битый"))
            return {'CANCELLED'}
        objs = (context.selected_objects if self.only_selected
                else list(context.scene.objects))
        bound = 0
        for o in objs:
            if getattr(o, 'type', None) != 'MESH':
                continue
            nm = _norm_model_name(_ariane_name_of(o)).lower()
            t = o.matrix_world.translation
            for guid, iid, model, x, y, z in insts:
                if (model == nm and abs(t.x - x) < 0.6
                        and abs(t.y - y) < 0.6 and abs(t.z - z) < 0.6):
                    o['ariane_guid'] = guid
                    o['ariane_name'] = _ariane_name_of(o)
                    try:
                        o['ariane_iid'] = int(iid)
                    except (TypeError, ValueError):
                        pass
                    bound += 1
                    break
        self.report({'INFO'}, T("Привязано к Ariane: {0} из {1} инстансов").format(
            bound, len(insts)))
        return {'FINISHED'}


# ── background watcher (bpy.app.timers) ──────────────────────────

_watch_enabled = False
_last_poke_mtime = -1.0


def _poll_timer():
    """app-timer callback: returns seconds until next call, or None to stop.

    The tick itself is cheap: it only stats ariane's ``inbox/poke`` file and runs
    the actual import when that timestamp changed (ariane bumps it on every
    export). With no poke file (older ariane) it falls back to scanning each tick.
    """
    global _last_poke_mtime
    if not _watch_enabled:
        return None

    interval = 1.0
    try:
        interval = float(bpy.context.scene.inu_settings.ariane_poll_interval)
    except Exception:                                     # noqa: BLE001
        pass

    try:
        poke = os.path.join(inbox_dir(), 'poke')
        mt = os.path.getmtime(poke) if os.path.exists(poke) else None
    except Exception:                                     # noqa: BLE001
        mt = None

    do_scan = True
    if mt is not None:
        do_scan = (mt != _last_poke_mtime)
        _last_poke_mtime = mt

    if do_scan:
        try:
            n = process_jobs()
            if n:
                print(f"[ariane bridge] imported {n} model(s)")
        except Exception as exc:                          # noqa: BLE001
            print(f"[ariane bridge] poll error: {exc}")

    # ПОСТОЯННО ловим ответы Ariane (create.done → привязка guid; reload.done →
    # ack). Раньше их читал только временный ждун (10–15 с) — на больших
    # батчах (тысячи моделей) Ariane отвечает НАМНОГО позже, ждун уже сдавался,
    # и привязка терялась. Теперь подхватываем когда бы Ariane ни ответила.
    try:
        if _read_create_ack():
            print("[ariane bridge] create.done: guid'ы привязаны")
        _read_ack()
    except Exception as exc:                              # noqa: BLE001
        print(f"[ariane bridge] ack read error: {exc}")
    return max(0.1, interval)


# ── Phase D: live TWO-WAY position sync ──────────────────────────
# Whoever is actively moving wins. ariane streams its selected instances into
# from_ariane.txt; Blender streams user-moved objects into from_blender.txt. Each
# side ignores the other's stream for what it's currently driving — Blender via a
# short per-guid ownership timeout after it detects a user move, ariane via its
# gGizmoUsing drag flag. So drag in ariane → ariane wins; drag in Blender → Blender
# wins; neither fights the other.

_live_last_mtime = -1.0
_live_seen = {}          # guid -> last-known rounded transform tuple
_live_owned = {}         # guid -> monotonic time until which Blender drives it
_live_targets = {}       # guid -> (Vector loc, Quaternion) we glide the object toward
_live_sel_last = None    # last selection set applied from ariane (avoid thrash)
_ariane_sel = frozenset()  # latest selection guids reported by ariane
_sel_seen = None         # last-known Blender selection (bridge guids)
_guid_collide_seen = frozenset()  # DIAG: last-reported guid-collision set
_sel_owned_until = 0.0   # monotonic time until which Blender drives the selection
_sel_ariane_mtime = -1.0
_known_guids = set()     # guids present in the scene last tick (delete detection)
_bridge_deleted = set()  # guids soft-deleted in ariane because they vanished here


def _live_dir() -> str:
    return os.path.join(bridge_base(), 'live')


def _fresh(path, max_age=2.5) -> bool:
    """True only if a live process wrote the file within max_age seconds — guards
    against applying a stale file left over when the other side isn't running."""
    import time as _t
    try:
        return (_t.time() - os.path.getmtime(path)) <= max_age
    except OSError:
        return False


def _blender_focused() -> bool:
    """True if a Blender window is the OS foreground → we should DRIVE the sync. When
    it isn't (you're working in ariane), we stop writing so ariane isn't disturbed
    (its freshness gate then ignores our now-stale files). Fail-open on error."""
    import sys
    if sys.platform != 'win32':
        return True
    try:
        import ctypes
        u = ctypes.windll.user32
        fg = u.GetForegroundWindow()
        if not fg:
            return False
        pid = ctypes.c_ulong()
        u.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        return pid.value == os.getpid()
    except Exception:                                     # noqa: BLE001
        return True


def _obj_key(o):
    loc, quat, _s = o.matrix_world.decompose()
    return (round(loc.x, 4), round(loc.y, 4), round(loc.z, 4),
            round(quat.x, 5), round(quat.y, 5), round(quat.z, 5), round(quat.w, 5))


def _guid_map():
    """guid -> list of tagged objects (roots + children)."""
    m = {}
    for o in bpy.data.objects:
        g = o.get('ariane_guid')
        if g:
            m.setdefault(g, []).append(o)
    return m


def _root_of(objs):
    return next((o for o in objs if o.parent is None), objs[0])


def _live_push_blender_moves(gmap, now):
    """Detect Blender-side user moves, own them briefly, stream to from_blender."""
    moves = []
    for g, objs in gmap.items():
        o = _root_of(objs)
        cur = _obj_key(o)
        prev = _live_seen.get(g)
        if prev is not None and cur != prev:
            _live_owned[g] = now + 0.6            # Blender drives this guid for a moment
            loc, quat, _s = o.matrix_world.decompose()
            moves.append(f"mov\t{g}\t{loc.x:.4f}\t{loc.y:.4f}\t{loc.z:.4f}\t"
                         f"{-quat.x:.6f}\t{-quat.y:.6f}\t{-quat.z:.6f}\t{quat.w:.6f}")
        _live_seen[g] = cur
    if not moves:
        return
    d = _live_dir()
    try:
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, 'from_blender.tmp')
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write("#live 1\n" + "\n".join(moves) + "\n")
        os.replace(tmp, os.path.join(d, 'from_blender.txt'))
    except OSError:
        pass


def _report_guid_collisions(gmap):
    """DIAG: guid'ы, висящие на НЕСКОЛЬКИХ РАЗНЫХ моделях — это и есть причина
    кривого синка (Ariane шлёт один guid → в блендере выделяется пачка/не тот).
    Печатается один раз на набор коллизий, чтобы не спамить."""
    global _guid_collide_seen
    bad = {}
    for g, objs in gmap.items():
        names = {o.get('ariane_name') for o in objs if o.get('ariane_name')}
        if len(names) > 1:
            bad[g] = sorted(names)
    key = frozenset(bad)
    if bad and key != _guid_collide_seen:
        _guid_collide_seen = key
        print(f"[ariane sel] ⚠ КОЛЛИЗИЯ guid: {len(bad)} guid'(ов) на РАЗНЫХ моделях:")
        for g, names in list(bad.items())[:10]:
            print(f"[ariane sel]     {g!r} → {len(names)} моделей: {names[:6]}")


def _apply_live_selection(gmap, sel_guids):
    """Mirror ariane's selection onto the matching Blender objects (bridge objects
    only — others are left alone)."""
    global _live_sel_last
    _report_guid_collisions(gmap)
    if sel_guids == _live_sel_last:
        return
    _live_sel_last = sel_guids
    if sel_guids:
        for g in sel_guids:
            objs = gmap.get(g, [])
            names = sorted({o.get('ariane_name', '?') for o in objs})
            print(f"[ariane sel] Ariane→Blender: guid {g!r} → {len(objs)} obj, "
                  f"models={names}")
    view = bpy.context.view_layer
    active = None
    for g, objs in gmap.items():
        on = g in sel_guids
        for o in objs:
            try:
                o.select_set(on)
            except Exception:                            # noqa: BLE001
                pass
        if on:
            active = _root_of(objs)
    if active is not None:
        try:
            view.objects.active = active
        except Exception:                                # noqa: BLE001
            pass


def _live_pull_ariane(gmap, now, want_moves):
    """Read ariane's live file (on mtime change): remember its selection, and set a
    glide target for each moved guid Blender isn't driving. The actual motion is a
    per-tick lerp in _live_lerp_targets (smooth, not a snap)."""
    global _live_last_mtime, _ariane_sel
    path = os.path.join(_live_dir(), 'from_ariane.txt')
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return
    if mt == _live_last_mtime:
        return
    _live_last_mtime = mt
    if not _fresh(path):                          # ariane not writing → stale, ignore
        return
    try:
        with open(path, encoding='utf-8') as fh:
            data = fh.read()
    except OSError:
        return

    from mathutils import Vector, Quaternion
    for ln in data.splitlines():
        if not ln or ln[0] == '#':
            continue
        f = ln.split('\t')
        if f[0] == 'sel':
            _ariane_sel = frozenset(f[1:])
            continue
        if not want_moves or len(f) < 9 or f[0] != 'mov':
            continue
        g = f[1]
        if _live_owned.get(g, 0.0) > now:         # Blender is driving it → skip
            continue
        if g not in gmap:
            continue
        try:
            x, y, z, qx, qy, qz, qw = (float(v) for v in f[2:9])
        except ValueError:
            continue
        # INU IPL convention (matches _apply_meta): Quaternion(w, -x, -y, -z)
        _live_targets[g] = (Vector((x, y, z)), Quaternion((qw, -qx, -qy, -qz)))


def _live_lerp_targets(gmap, now):
    """Glide objects toward their ariane targets each tick (smooth position sync)."""
    if not _live_targets:
        return
    done = []
    for g, (tloc, tquat) in _live_targets.items():
        if _live_owned.get(g, 0.0) > now:         # Blender took over → drop target
            done.append(g)
            continue
        objs = gmap.get(g)
        if not objs:
            done.append(g)
            continue
        o = _root_of(objs)
        a = 0.5
        o.location = o.location.lerp(tloc, a)
        if o.rotation_mode != 'QUATERNION':
            o.rotation_mode = 'QUATERNION'
        cq = o.rotation_quaternion
        tq = tquat
        if cq.dot(tq) < 0.0:                       # slerp the short way
            tq = tq.copy(); tq.negate()
        o.rotation_quaternion = cq.slerp(tq, a)
        if (o.location - tloc).length < 0.005:    # close enough → snap + finish
            o.location = tloc
            o.rotation_quaternion = tquat
            done.append(g)
        _live_seen[g] = _obj_key(o)               # our glide isn't a user move
    for g in done:
        _live_targets.pop(g, None)


# ── bidirectional selection sync ─────────────────────────────────

def _selected_bridge_guids():
    return frozenset(g for o in bpy.context.selected_objects
                     if (g := o.get('ariane_guid')))


def _write_sel_blender(guids):
    d = _live_dir()
    try:
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, 'sel_blender.tmp')
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write("sel\t" + "\t".join(sorted(guids)) + "\n")
        os.replace(tmp, os.path.join(d, 'sel_blender.txt'))
    except OSError:
        pass
    # DIAG: что реально выделено и с какими guid/iid — для отладки синка.
    try:
        detail = [(o.get('ariane_name', '?'),
                   o.get('ariane_guid'), o.get('ariane_iid'))
                  for o in bpy.context.selected_objects]
        print(f"[ariane sel] Blender→Ariane: guids={sorted(guids)} "
              f"selected(name,guid,iid)={detail}")
    except Exception:                                     # noqa: BLE001
        pass


def _live_selection(gmap, now, drive):
    """Two-way selection: whoever changed selection last wins. Blender→ariane writes
    sel_blender.txt on a selection change (only while Blender is the focused window);
    ariane→Blender applies ariane's selection when Blender isn't driving."""
    global _sel_seen, _sel_owned_until
    cur = _selected_bridge_guids()
    if drive and _sel_seen is not None and cur != _sel_seen:
        _sel_owned_until = now + 0.6              # user changed selection in Blender
        _write_sel_blender(cur)
    _sel_seen = cur
    if _sel_owned_until > now:
        return                                    # Blender is driving; ignore ariane
    if not _fresh(os.path.join(_live_dir(), 'from_ariane.txt')):
        return                                    # ariane not live → don't force selection
    _apply_live_selection(gmap, set(_ariane_sel))
    _sel_seen = _selected_bridge_guids()          # our apply isn't a user change


# ── soft-delete sync (Blender delete → ariane, with undo restore) ──

def _scene_guids():
    return frozenset(g for o in bpy.data.objects if (g := o.get('ariane_guid')))


def _write_del_blender():
    d = _live_dir()
    try:
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, 'del_blender.tmp')
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write("del\t" + "\t".join(sorted(_bridge_deleted)) + "\n")
        os.replace(tmp, os.path.join(d, 'del_blender.txt'))
    except OSError:
        pass


def _live_deletions():
    """Detect vanished/restored bridge objects. A guid that disappears → soft-delete
    in ariane; if it reappears (Ctrl+Z) → restore. Guards against a file reload wiping
    everything (mass-vanish + the load_post baseline reset)."""
    global _known_guids, _bridge_deleted
    current = _scene_guids()
    changed = False
    if _known_guids:                              # skip the very first tick (baseline)
        vanished = _known_guids - current - _bridge_deleted
        if vanished and len(vanished) <= 30:      # >30 at once = likely a reload → skip
            _bridge_deleted |= vanished
            changed = True
        reappeared = _bridge_deleted & current
        if reappeared:
            _bridge_deleted -= reappeared
            changed = True
    _known_guids = current
    if changed:
        _write_del_blender()


_ariane_del_mtime = -1.0


def _apply_ariane_deletions():
    """ariane → Blender soft-delete: HIDE objects whose instance was deleted in ariane, and
    un-hide when ariane restores it. We hide (reversible, no data loss / no re-import) to
    mirror ariane's soft-delete. Event-driven file (rewritten only on change), so we apply
    on mtime change — no freshness gate. Hiding keeps the object in the scene, so Blender's
    own delete detection never echoes it back → no loop."""
    global _ariane_del_mtime
    path = os.path.join(_live_dir(), 'del_ariane.txt')
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return
    if mt == _ariane_del_mtime:
        return
    _ariane_del_mtime = mt
    try:
        with open(path, encoding='utf-8') as fh:
            data = fh.read()
    except OSError:
        return
    deleted = set()
    for ln in data.splitlines():
        p = ln.split('\t')
        if p and p[0] == 'del':
            deleted.update(g for g in p[1:] if g)
    for o in bpy.data.objects:
        g = o.get('ariane_guid')
        if not g:
            continue
        if g in deleted:
            if not o.hide_viewport:
                o.hide_viewport = True
                o.hide_render = True
                o['ariane_hidden'] = True
        elif o.get('ariane_hidden'):
            o.hide_viewport = False
            o.hide_render = False
            try:
                del o['ariane_hidden']
            except KeyError:
                pass


@_persistent
def _ariane_on_load(*_a):
    """New/opened .blend → drop the delete baseline so a file switch never reads as a
    mass deletion."""
    global _known_guids, _bridge_deleted, _ariane_del_mtime
    _known_guids = set()
    _bridge_deleted = set()
    _ariane_del_mtime = -1.0


_live_cam_mtime = -1.0
_cam_seen = None            # last-known viewport (loc, rot, dist)
_cam_owned_until = 0.0      # monotonic time until which Blender drives the camera
_cam_target = None          # (loc, rot, dist) we glide the viewport toward

_time_last_push = None      # last "h m ow nw interp" string written to time_blender.txt
_time_ariane_mtime = -1.0   # mtime of time_ariane.txt we last applied
_timecyc_last_push = None    # last timecyc-slice body written to timecyc_blender.txt
_cam_draw_handle = None     # SpaceView3D draw handler (pushes camera during modal nav)


def _find_view3d():
    """First VIEW_3D (area, region_3d) across all windows, or (None, None)."""
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                sp = a.spaces.active
                r3d = getattr(sp, 'region_3d', None)
                if r3d is not None:
                    return a, r3d
    return None, None


def _view_key(r3d):
    return (tuple(round(c, 3) for c in r3d.view_location),
            tuple(round(c, 4) for c in r3d.view_rotation),
            round(r3d.view_distance, 3))


def _rot_from_forward_up(direction, up):
    """View rotation whose camera-local -Z aligns to `direction` and local +Y to `up`
    (both world space). region_3d.view_rotation maps camera-local axes to world; the
    camera looks down local -Z with local +Y as screen-up. Building the basis directly
    from a known up avoids to_track_quat's roll ambiguity, which re-picks an up and
    flips the view on a sideways / over-the-top orbit."""
    from mathutils import Matrix
    f = direction.normalized()
    if up is None or up.length < 1e-5:
        return f.to_track_quat('-Z', 'Y')                # legacy fallback (6-field line)
    right = f.cross(up.normalized())                     # world dir of camera-local +X
    if right.length < 1e-5:                              # up ∥ forward → degenerate
        return f.to_track_quat('-Z', 'Y')
    right.normalize()
    true_up = right.cross(f)                             # re-orthonormalized local +Y
    z = -f                                               # local +Z opposes the view dir
    m = Matrix(((right.x, true_up.x, z.x),               # columns = world dirs of X,Y,Z
                (right.y, true_up.y, z.y),
                (right.z, true_up.z, z.z)))
    return m.to_quaternion()


def _write_cam_blender(eye, tgt, up):
    d = _live_dir()
    try:
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, 'cam_blender.tmp')
        with open(tmp, 'w', encoding='utf-8') as fh:
            # 4 dp: with mm rounding the tiny horizontal part of a near-vertical view
            # direction is mostly noise, which ariane's roll-free camera turns into roll
            fh.write(f"cam\t{eye.x:.4f}\t{eye.y:.4f}\t{eye.z:.4f}\t"
                     f"{tgt.x:.4f}\t{tgt.y:.4f}\t{tgt.z:.4f}\t"
                     # up vector so ariane rebuilds the exact orientation (no roll guessing)
                     f"{up.x:.4f}\t{up.y:.4f}\t{up.z:.4f}\n")
        os.replace(tmp, os.path.join(d, 'cam_blender.txt'))
    except OSError:
        pass


def _cam_push(now, drive):
    """Blender→ariane camera PUSH: on a viewport change (while Blender is focused), own the
    camera briefly and write eye/target/up to cam_blender.txt. Kept separate so it can run
    from the VIEW_3D draw handler too — app timers are PAUSED during a modal operator like
    Walk/Fly, so without this the camera wouldn't stream while you walk."""
    global _cam_seen, _cam_owned_until, _cam_target
    if not drive:
        return
    from mathutils import Vector
    area, r3d = _find_view3d()
    if r3d is None or r3d.view_perspective == 'CAMERA':
        return
    cur = _view_key(r3d)
    if _cam_seen is not None and cur != _cam_seen:
        _cam_owned_until = now + 0.6
        _cam_target = None                        # cancel any inbound glide
        eye = r3d.view_location + (r3d.view_rotation @ Vector((0.0, 0.0, r3d.view_distance)))
        forward = r3d.view_rotation @ Vector((0.0, 0.0, -1.0))   # camera looks down local -Z
        up = r3d.view_rotation @ Vector((0.0, 1.0, 0.0))
        # target ALONG the view direction, not view_location: in Walk/Fly view_distance
        # collapses to ~0 so view_location == eye → zero direction → ariane's camera
        # degenerates. For orbit (distance >= min) this equals the pivot exactly.
        d = r3d.view_distance if r3d.view_distance > 2.0 else 2.0
        target = eye + forward * d
        _write_cam_blender(eye, target, up)
    _cam_seen = cur


def _live_camera(now, drive):
    """ariane→Blender camera PULL (apply cam_ariane to the viewport). The Blender→ariane
    push is _cam_push — driven both here and by the viewport draw handler (so it also fires
    during Walk/Fly, when timers are paused)."""
    global _live_cam_mtime, _cam_seen, _cam_owned_until, _cam_target
    _cam_push(now, drive)
    area, r3d = _find_view3d()
    if r3d is None or r3d.view_perspective == 'CAMERA':
        return
    from mathutils import Vector

    if _cam_owned_until > now:
        return                                    # Blender is driving; ignore ariane

    # refresh the target pose from ariane's file (only when it changed) …
    path = os.path.join(_live_dir(), 'cam_ariane.txt')
    try:
        mt = os.path.getmtime(path)
    except OSError:
        mt = None
    if mt is not None and mt != _live_cam_mtime:
        _live_cam_mtime = mt
        if _fresh(path):                          # ariane not live → don't grab the view
            try:
                with open(path, encoding='utf-8') as fh:
                    data = fh.read()
            except OSError:
                data = ''
            for ln in data.splitlines():
                p = ln.split('\t')
                if len(p) < 7 or p[0] != 'cam':
                    continue
                try:
                    px, py, pz, tx, ty, tz = (float(v) for v in p[1:7])
                except ValueError:
                    break
                direction = Vector((tx, ty, tz)) - Vector((px, py, pz))
                if direction.length < 1e-5:
                    break
                # Build the view rotation from forward + ariane's actual up vector, so a
                # sideways/over-the-top orbit reproduces exactly instead of to_track_quat
                # re-picking an up and flipping the view. Fall back to the old guess only
                # for a legacy 6-field line.
                up = None
                if len(p) >= 10:
                    try:
                        up = Vector((float(p[7]), float(p[8]), float(p[9])))
                    except ValueError:
                        up = None
                rot = _rot_from_forward_up(direction, up)
                _cam_target = (Vector((tx, ty, tz)), rot, direction.length)
                break

    # … and SNAP the viewport to it. A lerp interpolates the orbit quaternion, which
    # swings through a 180° flip near the vertical poles ("camera swings to the other
    # side") and lags a fast rotation — matching ariane exactly avoids both.
    if _cam_target is not None:
        tl, tr, td = _cam_target
        r3d.view_location = tl
        r3d.view_rotation = tr
        r3d.view_distance = td
        _cam_seen = _view_key(r3d)                # our own apply isn't a user nav
        if area is not None:
            area.tag_redraw()
        _cam_target = None


def _timecyc_props():
    try:
        return bpy.context.scene.inu_settings.gtatools_timecyc
    except Exception:                                     # noqa: BLE001
        return None


def _weather_names():
    """Ordered weather names from the PARSED timecyc — same order ariane indexes its
    weathers by (both read the one timecyc.dat), so this list is the index↔name map.
    Empty when no timecyc is loaded → weather sync is skipped, time still syncs."""
    try:
        from . import timecyc_ops as tc
        cyc = tc.get_cyc(bpy.context)
        if cyc and cyc.weathers:
            return [w.name for w in cyc.weathers]
    except Exception:                                     # noqa: BLE001
        pass
    return []


def _write_time_blender(hh, mm, ow, nw, interp):
    d = _live_dir()
    try:
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, 'time_blender.tmp')
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(f"time\t{hh}\t{mm}\t{ow}\t{nw}\t{interp:.4f}\n")
        os.replace(tmp, os.path.join(d, 'time_blender.txt'))
    except OSError:
        pass


def _apply_time_from_ariane(props, names, hh, mm, ow, nw, interp):
    """ariane → Blender: move the timecycle hour slider + weather to match. Set hour
    under timecyc's _SYNCING guard so its callback doesn't rebuild the world twice;
    let the (unguarded) weather callback apply once, else apply manually."""
    from . import timecyc_ops as tc
    hour = (hh % 24) + max(0, min(59, mm)) / 60.0
    widx = nw if interp >= 0.5 else ow            # dominant weather of the two-slot blend

    applied = False
    tc._SYNCING = True
    try:
        if abs(float(getattr(props, 'hour', -1.0)) - hour) > 1e-4:
            props.hour = hour
    finally:
        tc._SYNCING = False
    if names and 0 <= widx < len(names):
        if (props.weather_name or '') != names[widx]:
            props.weather_name = names[widx]      # fires on_weather_changed → applies once
            applied = True
    if not applied:
        try:
            tc.apply_to_scene(bpy.context)
        except Exception:                                 # noqa: BLE001
            pass


def _live_time(now, drive):
    """Two-way time-of-day + weather sync, mirroring the camera channel. drive → Blender
    is the active window and PUSHES its timecycle hour/weather to ariane; otherwise it
    PULLS ariane's time_ariane.txt onto the slider. Gated by ariane_sync_time."""
    global _time_last_push, _time_ariane_mtime
    props = _timecyc_props()
    if props is None:
        return
    names = _weather_names()

    if drive:
        hour = float(getattr(props, 'hour', 12.0))
        hh = int(hour) % 24
        mm = max(0, min(59, int((hour - int(hour)) * 60.0)))
        widx = 0
        if names:
            wname = (getattr(props, 'weather_name', '') or '').strip()
            if wname in names:
                widx = names.index(wname)
        # Blender's timecycle has ONE weather → send it in both slots (interp irrelevant).
        line = f"{hh}\t{mm}\t{widx}"
        if line != _time_last_push:
            _time_last_push = line
            _write_time_blender(hh, mm, widx, widx, 0.0)
        return

    # follow ariane
    path = os.path.join(_live_dir(), 'time_ariane.txt')
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return
    if mt == _time_ariane_mtime:
        return
    _time_ariane_mtime = mt
    if not _fresh(path):                                  # ariane not live → ignore stale file
        return
    try:
        with open(path, encoding='utf-8') as fh:
            data = fh.read()
    except OSError:
        return
    p = data.strip().split('\t')
    if len(p) < 3 or p[0] != 'time':
        return
    try:
        hh = int(p[1]); mm = int(p[2])
    except ValueError:
        return
    ow = nw = 0
    interp = 0.0
    if len(p) >= 6:
        try:
            ow = int(p[3]); nw = int(p[4]); interp = float(p[5])
        except ValueError:
            ow = nw = 0; interp = 0.0
    _apply_time_from_ariane(props, names, hh, mm, ow, nw, interp)


def push_timecyc_if_live(context=None):
    """Blender → ariane LIVE timecycle editing: when the watcher runs, ariane_sync_time is
    on and Blender is focused, write the currently-edited slice's fields into
    timecyc_blender.txt. ariane patches the matching (slot,weather) ColourSet cell in
    memory → the sky changes the same frame. Called from timecyc_ops.apply_to_scene, so it
    fires on any slice/field/slot/weather edit; content-diffed so an hour drag (values
    unchanged) writes nothing. slot index maps 1:1 to ariane's SA hour-row."""
    global _timecyc_last_push
    if not _watch_enabled:
        return
    context = context or bpy.context
    try:
        s = context.scene.inu_settings
    except Exception:                                     # noqa: BLE001
        return
    if not getattr(s, 'ariane_sync_time', False) or not _blender_focused():
        return
    props = _timecyc_props()
    if props is None:
        return
    try:
        from . import timecyc_ops as tc
        cyc = tc.get_cyc(context)
        if cyc is None or not cyc.weathers:
            return
        w = tc.weather_index(props, cyc)
        slot_idx = tc.slot_index(props, cyc)
        slot = cyc.weathers[w].slots[slot_idx]
        vals = getattr(slot, 'values', None)
    except Exception:                                     # noqa: BLE001
        return
    if not vals:
        return

    lines = []
    for key, arr in vals.items():
        if not arr:
            continue
        parts = "\t".join(f"{float(x):.3f}" for x in arr)
        lines.append(f"tccyc\t{w}\t{slot_idx}\t{key}\t{parts}")
    if not lines:
        return
    body = "\n".join(lines) + "\n"
    if body == _timecyc_last_push:
        return
    _timecyc_last_push = body

    d = _live_dir()
    try:
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, 'timecyc_blender.tmp')
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(body)
        os.replace(tmp, os.path.join(d, 'timecyc_blender.txt'))
    except OSError:
        pass


def _live_timer():
    """Fast timer (~0.15s): while the watcher runs and any live toggle is on, run
    the two-way position sync, selection sync and/or camera sync. Cheap when idle."""
    if not _watch_enabled:
        return None
    try:
        import time as _t
        s = bpy.context.scene.inu_settings
        live = getattr(s, 'ariane_live_sync', False)      # one master toggle: pos + sel + cam
        pos = sel = cam = live
        now = _t.monotonic()
        drive = _blender_focused()                        # only drive while focused here
        if pos or sel:
            gmap = _guid_map()
            if gmap:
                if pos and drive:
                    _live_push_blender_moves(gmap, now)
                _live_pull_ariane(gmap, now, want_moves=pos)   # targets + _ariane_sel
                if pos:
                    _live_lerp_targets(gmap, now)
                    for g in [k for k, t in _live_owned.items() if t <= now]:
                        _live_owned.pop(g, None)
                if sel:
                    _live_selection(gmap, now, drive)
        if cam:
            _live_camera(now, drive)
        if getattr(s, 'ariane_sync_deletions', False):
            if drive:
                _live_deletions()                         # Blender → ariane (while Blender drives)
            _apply_ariane_deletions()                     # ariane → Blender (hide/un-hide)
        if getattr(s, 'ariane_sync_time', False):
            _live_time(now, drive)                        # two-way time-of-day + weather
    except Exception as exc:                              # noqa: BLE001
        print(f"[ariane bridge] live sync error: {exc}")
    return 0.05                                           # ~20 Hz for smoother sync


def _on_view3d_draw():
    """VIEW_3D draw callback — fires on every viewport redraw, INCLUDING during a modal
    navigation operator (Walk/Fly), when bpy.app timers are paused. We only push the camera
    here (never modify the view mid-draw)."""
    try:
        if not _watch_enabled:
            return
        s = getattr(bpy.context.scene, 'inu_settings', None)
        if s is None or not getattr(s, 'ariane_live_sync', False):
            return
        import time as _t
        _cam_push(_t.monotonic(), _blender_focused())
    except Exception:                                     # noqa: BLE001
        pass


def _cam_draw_start():
    global _cam_draw_handle
    if _cam_draw_handle is None:
        try:
            _cam_draw_handle = bpy.types.SpaceView3D.draw_handler_add(
                _on_view3d_draw, (), 'WINDOW', 'POST_PIXEL')
        except Exception:                                 # noqa: BLE001
            _cam_draw_handle = None


def _cam_draw_stop():
    global _cam_draw_handle
    if _cam_draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_cam_draw_handle, 'WINDOW')
        except Exception:                                 # noqa: BLE001
            pass
        _cam_draw_handle = None


def start_watch():
    global _watch_enabled, _last_poke_mtime, _live_last_mtime, _known_guids
    _watch_enabled = True
    _last_poke_mtime = -1.0            # force a scan on the first tick after start
    _live_last_mtime = -1.0
    _known_guids = set()              # rebaseline delete detection
    if not bpy.app.timers.is_registered(_poll_timer):
        bpy.app.timers.register(_poll_timer, first_interval=0.5)
    if not bpy.app.timers.is_registered(_live_timer):
        bpy.app.timers.register(_live_timer, first_interval=0.3)
    _cam_draw_start()                 # camera push also from the viewport draw (Walk/Fly)
    if _ariane_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_ariane_on_load)


def stop_watch():
    global _watch_enabled
    _watch_enabled = False   # the timer unregisters itself on its next tick
    _cam_draw_stop()
    try:
        if _ariane_on_load in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_ariane_on_load)
    except Exception:                                     # noqa: BLE001
        pass


def is_watching() -> bool:
    return _watch_enabled


def _sweep_orphans(folder: str) -> int:
    """Delete leftover .dff/.txd payloads (historical pile / crash orphans),
    but never touch files still queued for import."""
    if not os.path.isdir(folder):
        return 0
    keep = set()
    for dff, _m, _f in _import_queue:
        b = os.path.basename(dff).lower()
        keep.add(b)
        keep.add(os.path.splitext(b)[0] + '.txd')
    n = 0
    for f in os.listdir(folder):
        low = f.lower()
        if low.endswith(('.dff', '.txd')) and low not in keep:
            try:
                os.remove(os.path.join(folder, f)); n += 1
            except OSError:
                pass
    return n


def clear_bridge_cache() -> int:
    """Wipe every bridge folder (inbox/outbox/overrides). Meant for between
    sessions — while ariane runs, its live edits live in 'overrides'."""
    base = bridge_base()
    n = 0
    for sub in ('inbox', 'outbox', 'overrides'):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            try:
                os.remove(os.path.join(d, f)); n += 1
            except OSError:
                pass
    return n


# ── operators ────────────────────────────────────────────────────

class GTATOOLS_OT_ariane_watch(bpy.types.Operator):
    """Вкл/выкл слежение за ariane: авто-импорт присланных моделей (DFF+LOD)."""

    bl_idname = "gtatools.ariane_watch"
    bl_label = "Ariane watcher (вкл/выкл)"

    def execute(self, context):
        if is_watching():
            stop_watch()
            self.report({'INFO'}, T("Ariane watcher выключен"))
        else:
            start_watch()
            process_jobs()               # import anything already waiting (self-cleans)
            _sweep_orphans(inbox_dir())  # clear the historical .dff/.txd pile
            self.report({'INFO'}, T("Ariane watcher включён · {0}").format(inbox_dir()))
        return {'FINISHED'}


class GTATOOLS_OT_ariane_clear(bpy.types.Operator):
    """Очистить папки моста (inbox/outbox/overrides). Делай между сессиями —
    во время работы ariane её живые правки лежат в overrides."""

    bl_idname = "gtatools.ariane_clear"
    bl_label = "Ariane: очистить кэш моста"

    def execute(self, context):
        n = clear_bridge_cache()
        self.report({'INFO'}, T("Ariane: удалено файлов из кэша: {0}").format(n))
        return {'FINISHED'}


class GTATOOLS_OT_ariane_pick_game(bpy.types.Operator):
    """Указать папку игры с ariane для моста (обмен через <папка>\\ariane\\bridge)."""

    bl_idname = "gtatools.ariane_pick_game"
    bl_label = "Папка игры (ariane)"

    directory: StringProperty(subtype='DIR_PATH')
    filter_folder: BoolProperty(default=True, options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        context.scene.inu_settings.ariane_bridge_path = self.directory
        return {'FINISHED'}


class GTATOOLS_OT_ariane_import_now(bpy.types.Operator):
    """Разово импортировать всё, что сейчас лежит в инбоксе ariane."""

    bl_idname = "gtatools.ariane_import_now"
    bl_label = "Ariane: импортировать сейчас"

    def execute(self, context):
        n = process_jobs()
        self.report({'INFO'}, T("Ariane: импортировано {0} модель(ей)").format(n))
        return {'FINISHED'}


# ── panel ────────────────────────────────────────────────────────

def draw_ariane_body(layout, context):
    """Ariane bridge controls, grouped by task (essential/common/advanced) per
    progressive-disclosure: setup → import → export → sync, rare/dangerous under
    a collapsed «Ещё». The selection block (Выделено / DFF/LOD/COL) is drawn
    ABOVE this by the shared panel, so it stays for both tabs."""
    s = context.scene.inu_settings

    # Один плотный столбец вплотную (без рамок/заголовков) — соседние кнопки
    # слиты в общие ряды. Группировка держится порядком, а не боксами.
    col = layout.column(align=True)

    # Папка игры (предусловие) — подсветка, если не задана.
    p = (s.ariane_bridge_path or '').strip()
    frow = col.row(align=True)
    frow.operator("gtatools.ariane_pick_game", text="", icon='FILE_FOLDER')
    if p:
        frow.label(text=p)
    else:
        frow.alert = True
        frow.label(text=T("укажи папку игры"), icon='ERROR')

    # Импорт: ручной + авто (⟳) в одном ряду.
    irow = col.row(align=True)
    irow.operator("gtatools.ariane_import_now", text=T("Ручной импорт"), icon='IMPORT')
    irow.operator("gtatools.ariane_watch", text=T("Sync импорт"), icon='FILE_REFRESH',
                  depress=is_watching())

    # Экспорт + опции «что включать» одним рядом (COL / LOD / позиция).
    col.operator("gtatools.ariane_send", text=T("Экспорт → Ariane"), icon='EXPORT')
    orow = col.row(align=True)
    orow.prop(s, "ariane_send_col", toggle=True)
    orow.prop(s, "ariane_send_lod", toggle=True)
    orow.prop(s, "ariane_send_ide", toggle=True)
    orow.prop(s, "ariane_send_position", toggle=True, text=T("Позиция"))

    # Синхронизация — все три тумблера одним рядом: Live + удаления + время.
    _sync = col.row(align=True)
    _sync.prop(s, "ariane_live_sync", toggle=True)
    _sync.prop(s, "ariane_sync_deletions", toggle=True)
    _sync.prop(s, "ariane_sync_time", toggle=True)
    if not getattr(s, 'ariane_live_sync', False):
        col.operator("gtatools.ariane_send_pos", text=T("Обновить позицию"),
                     icon='EMPTY_ARROWS')

    # Ещё (свёрнуто) — редкое/опасное. Заголовок повыше, чтобы не был тонким.
    _open = getattr(s, 'ariane_ui_more_open', False)
    _mrow = col.row(align=True)
    _mrow.scale_y = 1.3
    _mrow.prop(s, "ariane_ui_more_open", text=T("Ещё"), emboss=False,
               icon='TRIA_DOWN' if _open else 'TRIA_RIGHT')
    if _open:
        # Привязать существующую сцену к инстансам Ariane (без дублей) — для
        # моделей, что уже стоят в карте Ariane, но импортнуты из файлов игры.
        col.operator("gtatools.ariane_bind", text=T("Привязать к Ariane"),
                     icon='LINKED')
        col.operator("gtatools.ariane_create_model", text=T("Создать модель"), icon='MESH_DATA')
        col.operator("gtatools.ariane_clear", text=T("Очистить кэш"), icon='TRASH')

    st = layout.column(align=True)
    st.enabled = False
    if _import_queue:
        done = _import_total - len(_import_queue)
        st.label(text=T("импортирую… {0}/{1}").format(done, _import_total), icon='SORTTIME')
    st.label(text=T("импорт {0} (ош {1}) · отпр {2}").format(
                 _status['imported'], _status['errors'], _status['sent']),
             icon='INFO')
    ack = _status.get('ack')
    if ack is not None:
        st.label(text=T("Ariane принял: {0} (ош {1})").format(ack[0], ack[1]),
                 icon='CHECKMARK')
