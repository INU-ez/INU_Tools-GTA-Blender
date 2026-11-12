"""Real drag/drop operator + timer regression. Run in a window; auto exits.

Optional -- <sample.dff> tests a local model without modifying it.
"""
from pathlib import Path
import runpy
import sys
import traceback

import bpy

state = runpy.run_path(str(Path(__file__).with_name('_fx_lifecycle_blender_entry.py')))
state['enable']()
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
if '--' in sys.argv:
    sample = Path(sys.argv[sys.argv.index('--') + 1])
else:
    sample = state['runtime'] / 'drop_lamp.dff'
    sample.write_bytes(state['dff'].write_dff(state['clump']))
bpy.context.scene.inu_settings.gtatools_txd_auto_import = False
assert bpy.ops.gtatools.drop_dff(directory=str(sample.parent),
    files=[{'name': sample.name}], import_2dfx=True) == {'FINISHED'}
attempts = 0


def verify():
    global attempts
    attempts += 1
    effects = [obj for obj in bpy.context.scene.objects
               if getattr(obj.inu, 'type', '') == '2DFX']
    if not effects and attempts < 20:
        return 0.5
    try:
        assert effects, 'Drop did not import effects'
        duplicates = [obj.name for obj in bpy.context.scene.objects
                      if obj.type == 'EMPTY' and
                      state['imp']._is_light_frame_name(obj.name)]
        assert not duplicates, duplicates
        assert all(obj.parent is not None and obj.parent.type == 'MESH'
                   for obj in effects)
        print('DROP PASSED:', sample.name, 'effects:', len(effects),
              'extra Omni empties:', len(duplicates), flush=True)
    except Exception:
        print('DROP FAILED:', traceback.format_exc(), flush=True)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(verify, first_interval=1.0)
