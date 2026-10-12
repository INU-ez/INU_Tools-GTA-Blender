"""Native model-folder import regression; generates its own assets.

blender --background --factory-startup --python-exit-code 1 --python <this file>
"""
from pathlib import Path
from types import SimpleNamespace
import json
import sys

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import addon_utils
addon_utils.enable('INU_tools', default_set=False,
                   handle_error=lambda error: (_ for _ in ()).throw(error))
from INU_tools.ops import dff_export, img_ops
from INU_tools.core import col, ipl
from INU_tools.tools import compat

OUTPUT = ROOT / 'dev/tests/.blender_model_folder_runtime'
MODELS = OUTPUT / 'models'
NESTED = MODELS / 'nested'
NESTED.mkdir(parents=True, exist_ok=True)

# Export a real mesh with UVs and a texture; no game assets are needed.
obj = bpy.context.active_object
obj.name = 'Gate'
material = bpy.data.materials.new('FolderCheckMaterial')
material.use_nodes = True
obj.data.materials.clear()
obj.data.materials.append(material)
image = bpy.data.images.new('gate_diffuse', width=4, height=4)
image.generated_color = (0.2, 0.5, 0.8, 1.0)
image.filepath_raw = str(NESTED / 'gate_diffuse.png')
image.file_format = 'PNG'
image.save()
texture = material.node_tree.nodes.new('ShaderNodeTexImage')
texture.image = image
material.node_tree.links.new(texture.outputs['Color'],
                            material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
dff_export.export_dff(str(NESTED / 'Gate.DFF'), [obj])
collision = col.ColModel(version=3, model_name='Gate', model_id=10,
    bounds=col.Bounds(center=col.Vec3(0, 0, 0), radius=2,
                      bb_min=col.Vec3(-1, -1, -1), bb_max=col.Vec3(1, 1, 1)),
    vertices=[col.Vec3(0, 0, 0), col.Vec3(1, 0, 0), col.Vec3(0, 1, 0)],
    faces=[col.ColFace(a=0, b=1, c=2, surface=col.Surface(material=4, light=78))])
(NESTED / 'library.COL').write_bytes(col.write_col([collision]))
ide_path = OUTPUT / 'selected.ide'
ide_path.write_text('objs\n10, Gate, shared, 100, 0\nend\n', encoding='ascii')
text_ipl = OUTPUT / 'text.ipl'
text_ipl.write_text('inst\n10, Gate, 0, 1, 2, 3, 0, 0, 0, 1, -1\nend\n', encoding='ascii')
binary_ipl = OUTPUT / 'binary.ipl'
binary_ipl.write_bytes(ipl._write_binary_ipl(ipl.IplFile(instances=[
    ipl.IplInstance(model_id=10, model_name='', pos_x=1, pos_y=2, pos_z=3,
                    lod_index=-1)])))


def clear_objects():
    for item in list(bpy.data.objects):
        bpy.data.objects.remove(item, do_unlink=True)
    for item in list(bpy.data.materials):
        bpy.data.materials.remove(item, do_unlink=True)
    for item in list(bpy.data.images):
        bpy.data.images.remove(item, do_unlink=True)


settings = bpy.context.scene.inu_settings
settings.gtatools_game_root = str(OUTPUT)
settings.gtatools_models_root = str(MODELS)
assert settings.gtatools_game_root == ''
settings.gtatools_img_path = str(OUTPUT / 'unused.img')
settings.gtatools_ide_path = ''
settings.gtatools_ide_sync_list.clear()
settings.gtatools_ide_sync_list.add().path = str(ide_path)
settings.gtatools_ipl_sync_list.clear()
settings.gtatools_img_use_gta_dat = True  # Folder import must ignore this.
settings.gtatools_img_load_txd = True
settings.gtatools_map_load_col = True
settings.gtatools_img_skip_lod = False
bpy.context.scene['gtatools_found_imgs'] = str(OUTPUT / 'unused.img')
cases = []
for label, source in [('text IPL', text_ipl), ('binary IPL', binary_ipl), ('IDE only', None)]:
    clear_objects()
    settings.gtatools_ipl_path = str(source) if source else ''
    reports = []
    operator = SimpleNamespace(_final=None, _total=0, _done=0,
                               report=lambda level, text: reports.append((str(level), text)))
    for _ in img_ops.GTATOOLS_OT_import_from_img._work(operator, bpy.context):
        pass
    assert operator._final[0] == 'INFO', operator._final
    meshes = [o for o in bpy.data.objects if o.type == 'MESH'
              and any(c.name == 'Map_DFF' for c in o.users_collection)]
    collisions = [o for o in bpy.data.objects if o.type == 'MESH'
                  and any(c.name == 'Map_COL' for c in o.users_collection)]
    assert len(meshes) == 1, (label, operator._final, len(meshes))
    assert meshes[0].data.polygons, label
    assert meshes[0].inu.model_id == 10, label
    assert collisions and collisions[0].data.polygons, label
    if source:
        assert (meshes[0].location - collisions[0].location).length < 1e-6
        assert all(abs(a - b) < 1e-5 for a, b in zip(meshes[0].location, (1, 2, 3)))
    images = [n.image for slot in meshes[0].material_slots if slot.material
              for n in slot.material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
    assert images, (label, 'Loose texture was not loaded')
    cases.append(dict(source=label, meshes=len(meshes), collisions=len(collisions),
                      textures=len(images), report=operator._final))

material = bpy.data.materials.new('DisabledNodesCheck')
material.use_nodes = True
assert compat.material_uses_nodes(material)
material.use_nodes = False
assert material.node_tree is not None
if bpy.app.version < (5, 0, 0):
    assert not compat.material_uses_nodes(material)

result = dict(status='passed', blender=bpy.app.version_string, cases=cases,
              disabled_node_material=True, independent_of_img=True)
(OUTPUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('MODEL_FOLDER_CHECKS_OK', json.dumps(result, ensure_ascii=False))
addon_utils.disable('INU_tools', default_set=False)
