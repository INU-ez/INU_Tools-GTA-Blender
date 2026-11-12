"""Light 2DFX size round-trip; scaled mesh and scaled effect, no game assets."""
from pathlib import Path
import runpy

import bpy

state = runpy.run_path(str(Path(__file__).with_name('_fx_lifecycle_blender_entry.py')))
state['enable']()
exp, imp, dff, fx = (state[name] for name in ('exp', 'imp', 'dff', 'fx'))

for effect_scale in (0.25, 2.0, -0.5):
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.mesh.primitive_cube_add()
    owner = bpy.context.active_object
    owner.name = 'ScaledModel'
    owner.scale = (2, 3, 4)
    effect = bpy.data.objects.new('ScaledEffect', None)
    bpy.context.collection.objects.link(effect)
    effect.parent = owner
    effect.location = (1, 2, 3)
    effect.scale = (effect_scale,) * 3
    effect.inu.type = '2DFX'
    effect.inu.effect_2dfx = 'LIGHT'
    effect.inu.corona_size_2dfx = 3
    effect.inu.shadow_size_2dfx = 2
    fx.create_light_preview(effect)
    bpy.context.view_layer.update()
    source = next(child for child in effect.children if child.type == 'MESH')
    dimensions = tuple(source.dimensions)
    position = effect.matrix_world.translation.copy()
    snapshot = (tuple(effect.scale), effect.inu.corona_size_2dfx,
                effect.inu.shadow_size_2dfx)
    clump = dff.read_dff(dff.write_dff(exp.build_dff_clump([owner, effect])))
    imported = imp.import_dff_from_clump(clump, 'RoundTrip', skip_2dfx=False)
    restored = next(obj for obj in imported if obj.inu.type == '2DFX')
    bpy.context.view_layer.update()
    corona = next(child for child in restored.children if child.type == 'MESH')
    assert all(abs(a-b) < 1e-4 for a,b in zip(dimensions, corona.dimensions)), (
        effect_scale, dimensions, tuple(corona.dimensions))
    assert (restored.matrix_world.translation-position).length < 1e-4
    assert abs(restored.inu.shadow_size_2dfx - 2*abs(effect_scale)) < 1e-5
    assert snapshot == (tuple(effect.scale), effect.inu.corona_size_2dfx,
                        effect.inu.shadow_size_2dfx)
    print('PASS: effect scale', effect_scale, 'corona dimensions', dimensions)
print('FX SCALE ROUNDTRIP PASSED')
