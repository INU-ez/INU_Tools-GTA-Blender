"""Window/GPU companion to _fx_lifecycle_blender_entry.py; exits itself.

Run WITHOUT --background. No user scene or preferences are loaded/saved.
"""
from pathlib import Path
import importlib
import runpy
import traceback

import bpy

HERE = Path(__file__).resolve().parent
state = runpy.run_path(str(HERE / '_fx_lifecycle_blender_entry.py'))
state['enable']()
bpy.context.scene.inu_settings.gtatools_particle_sim = True
atlas = importlib.import_module(state['module'] + '.ops.floater.text_atlas')
result = {'drawn': False, 'error': None}


def draw():
    try:
        cached = atlas._get_atlas(16)
        assert cached is not None, 'GPU atlas bake failed'
        assert 'offscreen' not in cached, 'Offscreen retained until shutdown'
        assert atlas._get_text_shader() is not None
        atlas._text(50, 100, 'INU GPU atlas: English / Русский / Español', size=16)
        result['drawn'] = True
    except Exception:
        result['error'] = traceback.format_exc()


handler = bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')
attempts = 0


def finish():
    global attempts
    attempts += 1
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
    if not result['drawn'] and not result['error'] and attempts < 30:
        return 0.5
    if result['drawn'] and not result['error']:
        assert len(state['sim']._sim_state) == 4
        assert all(state['sim']._sim_state.values()), 'Live particle timer did not emit'
        bpy.ops.screen.screenshot(filepath=str(state['runtime'] / 'fx-gpu.png'))
        dimensions = [(window.width, window.height)
                      for window in bpy.context.window_manager.windows]
        print('GPU ATLAS PASSED / WINDOW DIMENSIONS:', dimensions, flush=True)
        print('PASS: live particle timer in a real viewport', flush=True)
    else:
        print('GPU ATLAS FAILED:', result['error'] or 'No draw callback', flush=True)
    bpy.types.SpaceView3D.draw_handler_remove(handler, 'WINDOW')
    # Exit with a LIVE cached GPU atlas: exercise the reported shutdown path.
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(finish, first_interval=3.0)
