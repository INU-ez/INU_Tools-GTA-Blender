# INU_tools.ops.map_watch — keeps the IDE/IPL link status honest.
#
# A persistent timer watches the IDE/IPL files that scene objects are linked
# to. When one of them changes on disk (a row deleted by hand, in MEd, by
# Del from another .blend …) the links are re-checked against it
# (map_link.refresh_links): a model whose row is gone loses its «В IPL» /
# «В IDE» status. Read-only — files are never written, objects never moved.
#
# Cheap by design: every tick only stat()s the known files; the scene is
# rescanned for linked files every few seconds; a file is parsed only when
# its mtime/size changed.

import os
import time
import bpy

_TICK = 2.0            # seconds between stat() passes
_RESCAN = 10.0         # seconds between rescans of which files are linked

_sig = {}              # normalized path → (mtime, size) last seen
_files = set()
_last_scan = 0.0
_scene_key = None      # (filepath, scene name) — rescan when it changes


def _stat(path):
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None                                   # gone


def reset():
    """Forget everything (file load): the next tick rescans + re-checks."""
    global _last_scan, _scene_key
    _sig.clear()
    _files.clear()
    _last_scan = 0.0
    _scene_key = None


def _tick():
    global _last_scan, _scene_key
    try:
        ctx = bpy.context
        scene = getattr(ctx, 'scene', None)
        if scene is None:
            return _TICK
        from . import map_link
        key = (bpy.data.filepath, scene.name)
        now = time.monotonic()
        first = key != _scene_key
        if first or now - _last_scan > _RESCAN:
            new = map_link.linked_files()
            for p in new - _files:
                _sig[p] = None        # unseen → checked once below
            for p in _files - new:
                _sig.pop(p, None)
            _files.clear()
            _files.update(new)
            _scene_key = key
            _last_scan = now
        changed = []
        for p in _files:
            cur = _stat(p)
            if _sig.get(p, 'x') != cur:
                _sig[p] = cur
                changed.append(p)
        if changed:
            lost_ipl, lost_ide = map_link.refresh_links(changed)
            if lost_ipl or lost_ide:
                print(f"[INU links] files changed: "
                      f"{', '.join(os.path.basename(p) for p in changed)} — "
                      f"IPL links dropped {lost_ipl}, IDE {lost_ide}")
                for win in getattr(bpy.context.window_manager, 'windows', []):
                    for area in win.screen.areas:
                        if area.type in ('VIEW_3D', 'PROPERTIES'):
                            area.tag_redraw()
    except Exception as e:                                  # noqa: BLE001
        print(f"[INU links] watch error: {e}")
    return _TICK


def start():
    reset()
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=_TICK, persistent=True)


def stop():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
