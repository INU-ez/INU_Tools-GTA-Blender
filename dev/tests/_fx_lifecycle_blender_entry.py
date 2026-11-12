"""2DFX lifecycle regression, isolated installed extension; no game assets.

blender --background --factory-startup --python-exit-code 1 --python <file>
"""
from pathlib import Path
import importlib
import shutil
import sys
import tempfile

import addon_utils
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
runtime = Path(tempfile.mkdtemp(prefix='inu-fx-'))
repository = runtime / 'repository'
package = repository / 'inu_tools_gta_sa'
shutil.copytree(ROOT / 'INU_tools', package,
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
repo = bpy.context.preferences.extensions.repos.new(
    name='INU FX regression', module='inu_fx_test',
    custom_directory=str(repository), remote_url='', source='USER')
repo.enabled = True
module = f'bl_ext.{repo.module}.inu_tools_gta_sa'


def enable():
    addon_utils.enable(module, default_set=False,
        handle_error=lambda error: (_ for _ in ()).throw(error))
    assert hasattr(importlib.import_module(module + '.ops.bake_ops'), 'BakeJobDriver')


enable()
fx = importlib.import_module(module + '.ops.fx_preview')
sim = importlib.import_module(module + '.ops.particle_sim')
imp = importlib.import_module(module + '.ops.dff_import')
exp = importlib.import_module(module + '.ops.dff_export')
dff = importlib.import_module(module + '.core.dff')
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
corona_image = bpy.data.images.new('coronastar', width=2, height=2)
corona_image.pixels[:] = [1.0] * 16

geom = dff.DffGeometry(vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
    triangles=[dff.Triangle(a=0, b=1, c=2)], materials=[dff.DffMaterial()],
    ext_2dfx=dff.Extension2dfx(entries=[dff.Light2dfx(loc=(1, 2, 3),
        corona_size=1, shadow_size=2, corona_tex_name='coronastar')]))
clump = dff.DffClump(frames=[
    dff.DffFrame(name='lamp', position=(10, 0, 0), write_name=True),
    dff.DffFrame(name='Omni01d', parent=0, position=(1, 2, 3), write_name=True),
    dff.DffFrame(name='attachment', parent=0, write_name=True),
    dff.DffFrame(parent=0, position=(1, 2, 3))],
    geometries=[geom], atomics=[dff.DffAtomic(frame_index=0, geometry_index=0)],
    lights=[dff.DffLight(frame_index=1), dff.DffLight(frame_index=3)])
objects = imp.import_dff_from_clump(dff.read_dff(dff.write_dff(clump)),
                                    'lamp', skip_2dfx=False)
owner = next(obj for obj in objects if obj.type == 'MESH')
effect = next(obj for obj in objects if obj.inu.type == '2DFX')
bpy.context.view_layer.update()
assert effect.parent == owner
assert tuple(effect.location) == (1, 2, 3)
assert (effect.matrix_world.translation - Vector((11, 2, 3))).length < 1e-5
assert effect.show_in_front and not effect.hide_select
assert effect.empty_display_type == 'SPHERE'
assert len(effect.children) == 2  # one light + one corona, including RNA callbacks
for _ in range(2):
    fx.create_light_preview(effect)
    assert len(effect.children) == 2
corona = next(child for child in effect.children if child.type == 'MESH')
assert len(corona.data.materials) == 1 and corona.data.materials[0] is not None
assert any(node.type == 'TEX_IMAGE' and node.image == corona_image
           for node in corona.data.materials[0].node_tree.nodes)
print('PASS: repeated light preview creation keeps one textured corona')
settings = bpy.context.scene.inu_settings
lamp = next(child for child in effect.children if child.type == 'LIGHT')
lamp.hide_viewport = True
render_flags = {child.name: child.hide_render for child in effect.children}
settings.gtatools_fx_preview_hidden = True
assert all(child.hide_viewport for child in effect.children)
assert not effect.hide_viewport and not owner.hide_viewport
fx._show_mode_tick()
assert all(child.hide_viewport for child in effect.children)
assert render_flags == {child.name: child.hide_render for child in effect.children}
settings.gtatools_fx_preview_hidden = False
assert lamp.hide_viewport and not corona.hide_viewport
lamp.hide_viewport = False
settings.gtatools_fx_preview_hidden = True
fx.create_light_preview(effect)
assert all(child.hide_viewport for child in effect.children)
settings.gtatools_fx_preview_hidden = False
assert all(not child.hide_viewport for child in effect.children)
print('PASS: Empty-only toggle hides previews, keeps markers, restores visibility')
assert not any(obj.name == 'Omni01d' for obj in objects)
assert any(obj.name == 'attachment' for obj in objects)
assert sum(obj.type == 'EMPTY' for obj in objects) == 2  # effect + attachment
assert sum(obj.type == 'EMPTY' and obj.inu.type == '2DFX' for obj in objects) == 1
assert set(effect.users_collection) == set(owner.users_collection)
assert all(set(child.users_collection) == set(owner.users_collection)
           for child in effect.children)
assert '2DFX' not in bpy.data.collections
assert exp._collect_2dfx([owner, effect]).entries[0].loc == (1, 2, 3)
effect_collection = bpy.data.collections.new('MovedEffects')
bpy.context.scene.collection.children.link(effect_collection)
original_collections = list(effect.users_collection)
effect_collection.objects.link(effect)
for collection in original_collections:
    collection.objects.unlink(effect)
fx._preview_autobuild_tick()
assert all(set(child.users_collection) == {effect_collection}
           for child in effect.children)
assert not any(child in collection.objects.values()
               for child in effect.children for collection in original_collections)
effect_collection.hide_viewport = True
bpy.context.view_layer.update()
assert all(not child.visible_get() for child in effect.children)
effect_collection.hide_viewport = False
bpy.context.view_layer.update()
print('PASS: moved effect carries preview collection membership')
model_utils = importlib.import_module(module + '.tools.model_utils')
sources = [owner, effect, *effect.children]
copies = []
for source in sources:
    copy = source.copy()
    bpy.context.collection.objects.link(copy)
    copies.append(copy)
model_utils.remap_copied_parents(sources, copies)
assert copies[1].parent == copies[0]
assert all(child.parent == copies[1] for child in copies[2:])
copies[0].location = (20, 0, 0)
bpy.context.view_layer.update()
assert (copies[1].matrix_world.translation - Vector((21, 2, 3))).length < 1e-5
assert (effect.matrix_world.translation - Vector((11, 2, 3))).length < 1e-5
copy_corona = next(child for child in copies[1].children if child.type == 'MESH')
copy_material = copy_corona.data.materials[0]
fx.create_light_preview(effect)
assert copy_corona.data.materials[0] == copy_material
assert any(node.type == 'TEX_IMAGE' and node.image == corona_image
           for node in copy_material.node_tree.nodes)
for copy in reversed(copies):
    bpy.data.objects.remove(copy, do_unlink=True)
previews = [child.name for child in effect.children]
bpy.data.objects.remove(effect, do_unlink=True)
fx._preview_autobuild_tick()
assert all(name not in bpy.data.objects for name in previews)
print('PASS: light ownership, local coordinates, selectable marker, orphan cleanup')
print('PASS: copied model keeps its own 2DFX and preview hierarchy')

emitters = []
for i in range(5):
    emitter = bpy.data.objects.new(f'fountain_{i}', None)
    bpy.context.collection.objects.link(emitter)
    emitter.inu.type = '2DFX'
    emitter.inu.effect_2dfx = 'PARTICLE'
    emitter.inu.particle_rate = 100
    emitter.inu.particle_life = 2
    emitter.inu.particle_speed = 3
    fx.create_particle_preview(emitter)
    fx.create_particle_preview(emitter)
    assert len(emitter.children) == 1
    assert all(child.data.materials[0] is not None for child in emitter.children)
    emitters.append(emitter)
for emitter in emitters:
    for display in ('SPHERE', 'CUBE'):
        emitter.empty_display_type = display
        exported = exp.build_dff_clump([owner, emitter])
        assert not exported.collision_data
        assert sum(len(geom.ext_2dfx.entries) if geom.ext_2dfx else 0
                   for geom in exported.geometries) == 1
print('PASS: particle preview stays single; effect markers never export as COL')
bpy.context.scene.inu_settings.gtatools_particle_sim = True
for _ in range(150):
    sim._tick()
assert len(sim._sim_state) == 5
assert all(len(state) > 0 for state in sim._sim_state.values())
assert all(len(state) <= sim.MAX_PARTICLES_PER_EMITTER
           for state in sim._sim_state.values())
for emitter in emitters:
    pool = sim._get_or_create_sim_mesh(emitter)
    assert len(pool.data.vertices) == sim.MAX_PARTICLES_PER_EMITTER * 4
    assert pool.parent == emitter and pool.hide_select
    assert any(vertex.co.length > 0 for vertex in pool.data.vertices)

ages = [[particle.age for particle in values] for values in sim._sim_state.values()]
settings.gtatools_fx_preview_hidden = True
assert all(child.hide_viewport for emitter in emitters for child in emitter.children)
sim._tick()
assert ages == [[particle.age for particle in values] for values in sim._sim_state.values()]
assert all(not emitter.hide_viewport for emitter in emitters)
settings.gtatools_fx_preview_hidden = False
assert all(not child.hide_viewport for emitter in emitters for child in emitter.children)
print('PASS: Empty-only toggle hides particle pools and pauses hidden simulation')

victim = emitters.pop()
previews = [child.name for child in victim.children]
bpy.data.objects.remove(victim, do_unlink=True)
sim._tick()
fx._preview_autobuild_tick()
assert len(sim._sim_state) == 4
assert all(name not in bpy.data.objects for name in previews)
bpy.context.scene.inu_settings.gtatools_particle_sim = False
assert not sim._sim_state and not sim._sim_timer_running
assert not any('_psim' in child.name for obj in emitters for child in obj.children)
print('PASS: 5 particle emitters / 150 ticks, ordinary Delete, stop cleanup')

addon_utils.disable(module, default_set=False)
assert not bpy.app.timers.is_registered(fx._preview_autobuild_tick)
assert not bpy.app.timers.is_registered(sim._tick)
enable()
addon_utils.disable(module, default_set=False)
print('PASS: installed extension enable / disable / enable / disable')
print('FX LIFECYCLE PASSED:', bpy.app.version_string)
