"""Native eyedropper → save/reopen → DFF/IFP hierarchy regression.

blender --background --factory-startup --python-exit-code 1 --python <file>
Pass an optional output directory after --. No external assets required.
"""

from pathlib import Path
import sys
import math
import os
import importlib
import copy

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
MODULE = os.environ.get('INU_ANIMOBJ_TEST_MODULE', 'INU_tools')
addon_utils.enable(MODULE, default_set=False,
                   handle_error=lambda error: (_ for _ in ()).throw(error))
dff = importlib.import_module(MODULE + '.core.dff')
ifp = importlib.import_module(MODULE + '.core.ifp')
animobj = importlib.import_module(MODULE + '.ops.animobj_ops')
_iter_action_fcurves = animobj._iter_action_fcurves
_strip_fcurves_at_path = animobj._strip_fcurves_at_path

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUTPUT = Path(args[0]) if args else ROOT / 'dev/tests/.blender_animobj_frames_runtime'
OUTPUT.mkdir(parents=True, exist_ok=True)

mesh = bpy.context.active_object
mesh.name = 'animpart_DFF'
settings = bpy.context.scene.inu_settings
settings.gtatools_animobj_picker_target = 'NEW_PIVOT'
# Exercise the actual scene-property update used by the UI pipette.
settings.gtatools_animobj_picker = mesh
bpy.context.view_layer.update()
pivot = mesh.parent
assert pivot is not None and pivot.get('inu_animobj_empty_pivot')
assert pivot.empty_display_type == 'SPHERE'
root = pivot.parent
assert root is not None and root.get('inu_animobj_empty_root')
names = root.name, pivot.name, mesh.name


def export_and_check(label, fmt):
    root_name, pivot_name, mesh_name = names
    bpy.context.view_layer.objects.active = bpy.data.objects[root_name]
    result = bpy.ops.gtatools.animobj_export(
        'EXEC_DEFAULT', directory=str(OUTPUT), base_name=label,
        txd_name=label, ifp_mode='NEW', ifp_format=fmt, write_ide=False)
    assert result == {'FINISHED'}, result
    clump = dff.read_dff_file(str(OUTPUT / f'{label}.dff'))
    frames = {frame.name: i for i, frame in enumerate(clump.frames)}
    assert len(clump.frames) == 3, frames
    root_index, pivot_index = frames[root_name], frames[pivot_name]
    mesh_index = clump.atomics[0].frame_index
    # Plain mesh frames may omit their name extension; the animated
    # pivot's name is required for IFP matching.
    assert clump.frames[mesh_index].name in ('', mesh_name)
    assert clump.frames[root_index].parent == -1
    assert clump.frames[pivot_index].parent == root_index
    assert clump.frames[mesh_index].parent == pivot_index
    assert clump.atomics[0].frame_index == mesh_index
    assert not clump.collision_data, 'Animated SPHERE pivot became embedded COL'
    assert len(clump.frames[root_index].hanim.bones) == 2
    pack = ifp.read_ifp(str(OUTPUT / f'{label}.ifp'))
    assert pack.source_format == fmt
    assert len(pack.animations) == 1
    tracks = pack.animations[0].bones
    assert len(tracks) == 1 and tracks[0].name == pivot_name
    assert len(tracks[0].keyframes) > 2
    assert tracks[0].keyframes[-1].time > 0
    print(f'PASS {label}: root -> pivot -> mesh, matching IFP, no pivot COL')
    return tracks[0]


def action_snapshot(obj):
    return (obj.rotation_mode, obj.animation_data.action.as_pointer(),
            [(fc.data_path, fc.array_index,
              [(tuple(k.co), tuple(k.handle_left), tuple(k.handle_right),
                k.interpolation) for k in fc.keyframe_points])
             for fc in _iter_action_fcurves(obj.animation_data.action)])


export_and_check('pipette_before_save', 'ANPK')
saved = OUTPUT / 'pipette.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(saved))
bpy.ops.wm.open_mainfile(filepath=str(saved), load_ui=False)
export_and_check('pipette_after_reopen', 'ANP3')

# A hand-authored rotation must survive export, even when its axis,
# duration and rotation order disagree with the automatic slider preset.
pivot = bpy.data.objects[names[1]]
pivot.inu_animobj_empty_props.auto_mode = False
for path in ('rotation_euler', 'rotation_quaternion', 'location'):
    _strip_fcurves_at_path(pivot.animation_data.action, path)
pivot.rotation_mode = 'ZYX'
for frame, angle, height in ((1, 0.25, 0.), (17, 1.2, 1.), (60, -0.4, 0.)):
    pivot.rotation_euler = (angle, 0., 0.)
    pivot.location.z = height
    pivot.keyframe_insert(data_path='rotation_euler', frame=frame)
    pivot.keyframe_insert(data_path='location', frame=frame)

for fmt in ('ANPK', 'ANP3'):
    before = action_snapshot(pivot)
    track = export_and_check(f'manual_{fmt.lower()}', fmt)
    assert action_snapshot(pivot) == before, 'Export overwrote manual keyframes/rotation order'
    # Inspect the actual IFP, not only the unchanged Blender Action.
    key = min(track.keyframes, key=lambda k: abs(k.time - 16. / 30.))
    assert abs(key.rotation[0] - math.sin(1.2 / 2.)) < 0.001
    assert abs(key.rotation[3] - math.cos(1.2 / 2.)) < 0.001
    assert abs(key.translation[2] - 1.) < 0.001

before = action_snapshot(pivot)
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / 'manual.blend'))
bpy.ops.wm.open_mainfile(filepath=str(OUTPUT / 'manual.blend'), load_ui=False)
pivot = bpy.data.objects[names[1]]
assert not pivot.inu_animobj_empty_props.auto_mode
# RNA pointers change on reopen; compare rotation order and curve content.
assert action_snapshot(pivot)[::2] == before[::2]
before = action_snapshot(pivot)
export_and_check('manual_reopened', 'ANP3')
assert action_snapshot(pivot) == before, 'Reopened manual Action changed on export'

def world_bounds(obj, frame):
    bpy.context.scene.frame_set(frame)
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    points = [evaluated.matrix_world @ v.co for v in evaluated.data.vertices]
    return tuple(value for axis in range(3)
                 for value in (min(p[axis] for p in points), max(p[axis] for p in points)))

source_bounds = {frame - 1: world_bounds(bpy.data.objects[names[2]], frame)
                 for frame in range(1, 61)}

# Import the actual exported pair and verify that IFP moves the mesh,
# while preserving the original Empty/object hierarchy exactly.
importer = importlib.import_module(MODULE + '.ops.dff_import')
ifp_importer = importlib.import_module(MODULE + '.ops.ifp_import')
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
imported = importer.import_dff(str(OUTPUT / 'manual_reopened.dff'),
                               context=bpy.context, weld_sharpen=False)
assert not any(obj.type == 'ARMATURE' for obj in bpy.context.scene.objects)
root = bpy.data.objects[names[0]]
pivot = bpy.data.objects[names[1]]
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
assert len(meshes) == 1
mesh = meshes[0]
assert mesh.name == names[2]
assert mesh.parent == pivot and pivot.parent == root and root.parent is None
assert root.type == pivot.type == 'EMPTY'
assert not mesh.modifiers
bpy.context.view_layer.objects.active = mesh
assert bpy.ops.gtatools.import_ifp('EXEC_DEFAULT',
    filepath=str(OUTPUT / 'manual_reopened.ifp')) == {'FINISHED'}
assert bpy.ops.gtatools.apply_ifp('EXEC_DEFAULT') == {'FINISHED'}
assert mesh.parent == pivot and pivot.parent == root

def evaluated_position(frame):
    bpy.context.scene.frame_set(frame)
    evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return evaluated.matrix_world @ evaluated.data.vertices[0].co

assert (evaluated_position(16) - evaluated_position(0)).length > 0.1, 'IFP did not move the mesh'
for frame, expected in source_bounds.items():
    actual = world_bounds(mesh, frame)
    assert max(abs(a - b) for a, b in zip(actual, expected)) < 0.003, (frame, actual, expected)
print('PASS reimport: identical Empty hierarchy and matching imported IFP motion')
saved_empty = OUTPUT / 'reimported_empty.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(saved_empty))
bpy.ops.wm.open_mainfile(filepath=str(saved_empty), load_ui=False)
root, pivot, mesh = (bpy.data.objects[name] for name in names)
assert mesh.parent == pivot and pivot.parent == root
assert not any(obj.type == 'ARMATURE' for obj in bpy.context.scene.objects)
export_and_check('empty_second_export', 'ANP3')

# Reimport into an occupied scene: Blender suffixes root/pivot names,
# while the IFP still names the original RW frames. Keep both rigs
# independent and retain canonical names on the second export.
original_action = action_snapshot(pivot)
second_objects = importer.import_dff(str(OUTPUT / 'manual_reopened.dff'),
                                     context=bpy.context, weld_sharpen=False)
second_root = next(obj for obj in second_objects if obj.get('inu_animobj_empty_root'))
second_mesh = next(obj for obj in second_objects if obj.type == 'MESH')
assert second_root != root and second_root.name != root.name
bpy.context.view_layer.objects.active = second_root
assert bpy.ops.gtatools.import_ifp('EXEC_DEFAULT',
    filepath=str(OUTPUT / 'manual_reopened.ifp')) == {'FINISHED'}
assert bpy.ops.gtatools.apply_ifp('EXEC_DEFAULT') == {'FINISHED'}
assert action_snapshot(pivot) == original_action, 'Applying IFP changed the other rig'
for key in ('inu_animobj_frame_name', 'inu_animobj_import_name'):
    del second_mesh.parent[key]
assert bpy.ops.gtatools.apply_ifp('EXEC_DEFAULT') == {'FINISHED'}, 'Older imported rig was not recognized'
assert mesh.parent == pivot and second_mesh.parent.parent == second_root
for frame, expected in source_bounds.items():
    actual = world_bounds(second_mesh, frame)
    assert max(abs(a-b) for a,b in zip(actual, expected)) < 0.003
second_name = second_root.name
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / 'same_names.blend'))
bpy.ops.wm.open_mainfile(filepath=str(OUTPUT / 'same_names.blend'), load_ui=False)
bpy.context.view_layer.objects.active = bpy.data.objects[second_name]
assert bpy.ops.gtatools.apply_ifp('EXEC_DEFAULT') == {'FINISHED'}
assert bpy.ops.gtatools.animobj_export('EXEC_DEFAULT', directory=str(OUTPUT),
    base_name='same_name_export', txd_name='same_name_export',
    ifp_mode='NEW', ifp_format='ANPK', write_ide=False) == {'FINISHED'}
second_dff = dff.read_dff_file(str(OUTPUT / 'same_name_export.dff'))
second_ifp = ifp.read_ifp(str(OUTPUT / 'same_name_export.ifp'))
assert {f.name for f in second_dff.frames} == set(names)
assert all(track.name in {f.name for f in second_dff.frames}
           for anim in second_ifp.animations for track in anim.bones)
print('PASS same-name import: IFP applies to .001 rig, survives reopen and reexport')

# The supplied scene has two distinct pivot frames sharing BoneID=1.
# Its HAnim frame indices must keep both bones instead of importing the
# final pivot twice and leaving the first mesh unbound.
clump = dff.read_dff_file(str(OUTPUT / 'manual_reopened.dff'))
pivot_index = next(i for i, f in enumerate(clump.frames) if f.name == names[1])
root_index = clump.frames[pivot_index].parent
second_pivot = copy.deepcopy(clump.frames[pivot_index])
second_pivot.name = 'second_pivot'
second_index = len(clump.frames)
clump.frames.append(second_pivot)
second_frame = copy.deepcopy(clump.frames[clump.atomics[0].frame_index])
second_frame.name = 'second_mesh'
second_frame.write_name = True
second_frame.parent = second_index
second_atomic = copy.deepcopy(clump.atomics[0])
second_atomic.frame_index = len(clump.frames)
clump.frames.append(second_frame)
clump.atomics.append(second_atomic)
clump.frames[root_index].hanim.bones.append(dff.HAnimBone(
    bone_id=second_pivot.hanim.bone_id, index=second_index, bone_type=1))
clump.raw_frame_list = b''
clump.raw_atomics = b''
dff.write_dff_file(str(OUTPUT / 'duplicate_ids.dff'), clump)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
importer.import_dff(str(OUTPUT / 'duplicate_ids.dff'), context=bpy.context,
                    weld_sharpen=False)
assert not any(obj.type == 'ARMATURE' for obj in bpy.context.scene.objects)
root = bpy.data.objects[names[0]]
assert bpy.data.objects[names[1]].parent == root
assert bpy.data.objects['second_pivot'].parent == root
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
assert len(meshes) == 2
assert {obj.parent.name for obj in meshes} == {names[1], 'second_pivot'}
print('PASS repeated BoneID: both pivot Empties and child meshes preserved')

# Legacy rigid models with an atomic directly on a HAnim frame keep the
# existing armature path; skinned/character import is not replaced.
legacy = dff.read_dff_file(str(OUTPUT / 'manual_reopened.dff'))
legacy.atomics[0].frame_index = next(i for i, f in enumerate(legacy.frames) if f.name == names[1])
legacy.raw_atomics = b''
dff.write_dff_file(str(OUTPUT / 'legacy_rigid.dff'), legacy)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
importer.import_dff(str(OUTPUT / 'legacy_rigid.dff'), context=bpy.context, weld_sharpen=False)
arm = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
mesh = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
assert mesh.parent == arm and names[1] in mesh.vertex_groups
print('PASS legacy rigid HAnim: armature import retained')
print(f'Animated-object frames regression passed in Blender {bpy.app.version_string}')
