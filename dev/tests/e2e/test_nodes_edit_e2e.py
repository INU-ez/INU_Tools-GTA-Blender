"""Native mesh Edit Mode, node operators and reload tests inside Blender."""

from pathlib import Path
import struct

import bpy
import bmesh
import pytest
from mathutils import Vector

from INU_tools.core.paths import (NodesFile, PathNode, NaviNode, PathLink,
                                 read_nodes, write_nodes, encode_navi_flags)
from INU_tools.core.paths_graph import graph_edges, navi_address, validate_graph_batch
from INU_tools.ops.path_import import import_nodes
from INU_tools.ops.path_export import export_nodes
from INU_tools.ops.path_nodes_mesh import collect_compiled_nodes, complete_node_objects


def road(peds=False):
    return NodesFile(vehicle_nodes=[
        PathNode(x=800, y=100, z=1, area_id=37, node_id=0, flags=0xF0001, node_type=1, path_width=8),
        PathNode(x=820, y=100, z=1, area_id=37, node_id=1, flags=0xF0001, node_type=1, path_width=8, link_id=1)],
        ped_nodes=[PathNode(x=805, y=110, z=1, area_id=37, node_id=2, is_vehicle=False, node_type=4)] if peds else [],
        navi_nodes=[NaviNode(x=810, y=100, area_id=37, node_id=0, dir_x=-100,
                             flags=encode_navi_flags(left_lanes=0, right_lanes=2))],
        links=[PathLink(37, 1), PathLink(37, 0)],
        navi_links=[navi_address(37, 0)]*2, link_lengths=[20, 20],
        path_intersections=[3, 1]+[7]*192, parsed_extras=True)


def load_road(tmp_path, peds=False):
    path = tmp_path/'nodes37.dat'
    write_nodes(str(path), road(peds))
    objects = import_nodes(str(path), context=bpy.context)
    vehicle = next(o for o in objects if o.get('path_type') == 'nodes_vehicle')
    activate(vehicle)
    return objects, vehicle


def activate(obj):
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for existing in bpy.context.selected_objects:
        existing.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def enter_edit(obj, vertices=(), edges=()):
    activate(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    for index in vertices:
        bm.verts[index].select_set(True)
    for index in edges:
        bm.edges[index].select_set(True)
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data)
    return bm


def extrude(obj, vertex=1, delta=(20, 0, 0)):
    bm = enter_edit(obj, vertices=(vertex,))
    original = bm.verts[vertex]
    created = bmesh.ops.extrude_vert_indiv(bm, verts=[original])['verts']
    assert len(created) == 1
    created[0].co += Vector(delta)
    created[0].select_set(True)
    bmesh.update_edit_mesh(obj.data)


def assert_connected_export(tmp_path, expected_nodes=3):
    result = bpy.ops.gtatools.export_nodes(directory=str(tmp_path))
    assert result == {'FINISHED'}
    back = read_nodes(str(tmp_path/'nodes37.dat'))
    assert len(back.vehicle_nodes) == expected_nodes
    assert len(back.links) == len(back.navi_links) == len(back.link_lengths) == 4
    assert graph_edges(back, 37) == {(0, 1), (1, 2)}
    assert len(back.path_intersections) == 196
    validate_graph_batch({37: back})
    return back


def test_native_import_stores_identity_and_roundtrips(tmp_path):
    objects, vehicle = load_road(tmp_path, peds=True)
    identities = vehicle.data.attributes.get('inu_node_identity')
    assert identities and identities.domain == 'POINT' and identities.data_type == 'INT'
    companions = complete_node_objects([vehicle], bpy.context.scene.objects)
    assert len(companions) == 3
    collected = collect_compiled_nodes(companions)
    assert not collected.topology_changed and not collected.node_remap
    source = (tmp_path/'nodes37.dat').read_bytes()
    export_nodes(str(tmp_path/'roundtrip.dat'), objects=companions, emit_roadblox=False)
    assert (tmp_path/'roundtrip.dat').read_bytes() == source


def test_native_extrude_export_while_still_in_edit_mode(tmp_path):
    objects, vehicle = load_road(tmp_path)
    extrude(vehicle)
    assert bpy.context.mode == 'EDIT_MESH'
    back = assert_connected_export(tmp_path)
    assert back.vehicle_nodes[2].x == 840
    assert len(back.navi_nodes) == 2
    assert bpy.context.mode == 'EDIT_MESH'


def test_native_legacy_identity_migration_without_leaving_edit_mode(tmp_path):
    objects, vehicle = load_road(tmp_path)
    del vehicle['nodes_identity_version']
    vehicle.data.attributes.remove(vehicle.data.attributes['inu_node_identity'])
    enter_edit(vehicle)
    nf = collect_compiled_nodes(objects)
    assert not nf.topology_changed and vehicle['nodes_identity_version'] == 1
    assert bpy.context.mode == 'EDIT_MESH'
    assert bmesh.from_edit_mesh(vehicle.data).verts.layers.int.get('inu_node_identity') is not None


def test_native_navigation_position_edit_reads_live_identity_layer(tmp_path):
    objects, _ = load_road(tmp_path)
    nav = next(o for o in objects if o.get('path_type') == 'nodes_navi')
    bm = enter_edit(nav, vertices=(0,))
    bm.verts[0].co.x += 4
    bmesh.update_edit_mesh(nav.data)
    nf = collect_compiled_nodes(objects)
    assert nf.navi_nodes[0].x == 814
    assert not nf.topology_changed and bpy.context.mode == 'EDIT_MESH'


def test_native_mesh_operator_extrude_creates_connected_point(tmp_path):
    objects, vehicle = load_road(tmp_path)
    enter_edit(vehicle, vertices=(1,))
    result = bpy.ops.mesh.extrude_vertices_move(TRANSFORM_OT_translate={'value': (20, 0, 0)})
    assert result == {'FINISHED'}
    bpy.ops.object.mode_set(mode='OBJECT')
    back = assert_connected_export(tmp_path)
    assert back.vehicle_nodes[-1].x == 840


def test_native_subdivide_keeps_lane_metadata_and_graph(tmp_path):
    objects, vehicle = load_road(tmp_path)
    bm = enter_edit(vehicle, edges=(0,))
    bmesh.ops.subdivide_edges(bm, edges=[bm.edges[0]], cuts=1, use_grid_fill=False)
    bmesh.update_edit_mesh(vehicle.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert bpy.ops.gtatools.export_nodes(directory=str(tmp_path)) == {'FINISHED'}
    back = read_nodes(str(tmp_path/'nodes37.dat'))
    assert len(back.vehicle_nodes) == 3
    assert graph_edges(back, 37) == {(0, 2), (1, 2)}
    assert back.vehicle_nodes[-1].x == 810
    assert len(back.navi_nodes) == 3
    assert all(n.flags == road().navi_nodes[0].flags for n in back.navi_nodes)
    validate_graph_batch({37: back})


def test_native_delete_vertex_preserves_remaining_properties(tmp_path):
    objects, vehicle = load_road(tmp_path)
    bm = enter_edit(vehicle, vertices=(0,))
    bmesh.ops.delete(bm, geom=[bm.verts[0]], context='VERTS')
    bmesh.update_edit_mesh(vehicle.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    nf = collect_compiled_nodes(objects)
    assert nf.node_remap == {(37, 0): None, (37, 1): 0}
    assert nf.vehicle_nodes[0].x == 820
    assert nf.vehicle_nodes[0].node_type == 1 and nf.links == []
    # The real operator must refuse this partial reindex before overwriting.
    before = (tmp_path/'nodes37.dat').read_bytes()
    try:
        result = bpy.ops.gtatools.export_nodes(directory=str(tmp_path))
        assert result == {'CANCELLED'}
    except RuntimeError as exc:
        assert '64' in str(exc)
    assert (tmp_path/'nodes37.dat').read_bytes() == before


def test_native_duplicate_then_move_gets_a_fresh_node(tmp_path):
    objects, vehicle = load_road(tmp_path)
    bm = enter_edit(vehicle, vertices=(1,))
    original = bm.verts[1]
    duplicate = bmesh.ops.duplicate(bm, geom=[original])['vert_map'][original]
    duplicate.co += Vector((20, 0, 0))
    bm.edges.new((original, duplicate))
    bmesh.update_edit_mesh(vehicle.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert_connected_export(tmp_path)


def test_native_save_reload_preserves_ids_for_followup_edit(tmp_path):
    objects, vehicle = load_road(tmp_path)
    extrude(vehicle)
    bpy.ops.object.mode_set(mode='OBJECT')
    blend = tmp_path/'nodes_edit.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.wm.open_mainfile(filepath=str(blend), load_ui=False)
    vehicle = next(o for o in bpy.context.scene.objects if o.get('path_type') == 'nodes_vehicle')
    activate(vehicle)
    back = assert_connected_export(tmp_path)
    assert len(back.navi_nodes) == 2
    # Reimport the emitted DAT: viewport edges must reproduce the graph.
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    imported = import_nodes(str(tmp_path/'nodes37.dat'), context=bpy.context)
    veh = next(o for o in imported if o.get('path_type') == 'nodes_vehicle')
    assert {tuple(sorted(e.vertices)) for e in veh.data.edges} == {(0, 1), (1, 2)}


@pytest.fixture(scope='module')
def vanilla_files(tmp_path_factory):
    archive = Path(r'D:\Grand Theft Auto San Andreas\models\gta3.img')
    if not archive.exists():
        pytest.skip('Vanilla SA archive is unavailable')
    directory = tmp_path_factory.mktemp('vanilla_nodes_native')
    files = []
    with archive.open('rb') as stream:
        magic, count = struct.unpack('<4sI', stream.read(8))
        assert magic == b'VER2'
        entries = stream.read(count*32)
        for offset in range(0, len(entries), 32):
            sector, size, _, name = struct.unpack_from('<IHH24s', entries, offset)
            name = name.split(b'\0')[0].decode().lower()
            stem = name.rsplit('.', 1)[0]
            if name.endswith('.dat') and stem.startswith('nodes') and stem[5:].isdigit():
                stream.seek(sector*2048)
                path = directory/name
                path.write_bytes(stream.read(size*2048))
                files.append(path)
    assert len(files) == 64
    return files


@pytest.mark.parametrize('stay_in_edit_mode', [False, True])
def test_native_full_vanilla_import_extrude_and_export(vanilla_files, tmp_path, stay_in_edit_mode):
    imported = []
    originals = {}
    for path in vanilla_files:
        area = int(path.stem[5:])
        originals[area] = read_nodes(str(path))
        imported.extend(import_nodes(str(path), context=bpy.context))
    vehicle = next(o for o in imported if o.get('nodes_area') == 37 and o.get('path_type') == 'nodes_vehicle')
    if not stay_in_edit_mode:
        extrude(vehicle, vertex=0, delta=(5, 0, 0))
        bpy.ops.object.mode_set(mode='OBJECT')
    # Select just the vehicle meshes; companions must be included by the operator.
    for obj in imported:
        obj.select_set(obj.get('path_type') == 'nodes_vehicle')
    bpy.context.view_layer.objects.active = vehicle
    if stay_in_edit_mode:
        # Blender edits all selected vehicle meshes at once, including
        # empty region meshes. Their identities must stay readable too.
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(vehicle.data)
        bm.verts.ensure_lookup_table()
        created = bmesh.ops.extrude_vert_indiv(bm, verts=[bm.verts[0]])['verts']
        created[0].co += Vector((5, 0, 0))
        bmesh.update_edit_mesh(vehicle.data)
    assert bpy.ops.gtatools.export_nodes(directory=str(tmp_path)) == {'FINISHED'}
    result = {area: read_nodes(str(tmp_path/f'nodes{area}.dat')) for area in range(64)}
    validate_graph_batch(result)
    original = originals[37]
    new = result[37]
    assert len(new.vehicle_nodes) == len(original.vehicle_nodes)+1
    assert len(new.navi_nodes) == len(original.navi_nodes)+1
    assert len(new.links) == len(original.links)+2
    assert new.ped_nodes[0].node_id == len(new.vehicle_nodes)
    assert all(n.node_id == i for i, n in enumerate(new.vehicle_nodes+new.ped_nodes))
    before = [(area, l.node_id) for area, nf in originals.items() if area != 37
              for l in nf.links if l.area_id == 37 and l.node_id >= len(original.vehicle_nodes)]
    after = [(area, l.node_id) for area, nf in result.items() if area != 37
             for l in nf.links if l.area_id == 37 and l.node_id >= len(original.vehicle_nodes)+1]
    assert before and after == [(area, index+1) for area, index in before]
    assert bpy.context.mode == ('EDIT_MESH' if stay_in_edit_mode else 'OBJECT')
