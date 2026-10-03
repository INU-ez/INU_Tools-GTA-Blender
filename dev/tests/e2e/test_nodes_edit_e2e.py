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


@pytest.mark.parametrize('stay_in_edit_mode', [False, True])
def test_native_symmetric_duplicate_moves_export_distinct_points(tmp_path, stay_in_edit_mode):
    objects, vehicle = load_road(tmp_path)
    bm = enter_edit(vehicle, vertices=(1,))
    original = bm.verts[1]
    duplicate = bmesh.ops.duplicate(bm, geom=[original])['vert_map'][original]
    original.co.x -= 10
    duplicate.co.x += 10
    original.select_set(True)
    duplicate.select_set(True)
    bm.edges.new((original, duplicate))
    bmesh.update_edit_mesh(vehicle.data)
    if not stay_in_edit_mode:
        bpy.ops.object.mode_set(mode='OBJECT')
    back = assert_connected_export(tmp_path)
    assert [n.x for n in back.vehicle_nodes] == [800, 810, 830]


def test_native_coincident_duplicate_reports_object_and_vertices(tmp_path):
    objects, vehicle = load_road(tmp_path)
    bm = enter_edit(vehicle, vertices=(1,))
    original = bm.verts[1]
    duplicate = bmesh.ops.duplicate(bm, geom=[original])['vert_map'][original]
    original.select_set(True)
    duplicate.select_set(True)
    bmesh.update_edit_mesh(vehicle.data)
    with pytest.raises(ValueError, match='Coincident') as error:
        collect_compiled_nodes(objects)
    assert vehicle.name in str(error.value)
    assert 'vertex indices 1 and 2' in str(error.value)
    assert 'move the new point or merge' in str(error.value)


@pytest.mark.parametrize('call_context', ['EXEC_DEFAULT', 'INVOKE_DEFAULT'])
@pytest.mark.parametrize('keep_source_meshes', [False, True])
def test_native_legacy_curve_export_guard_leaves_all_files_unchanged(tmp_path, call_context, keep_source_meshes):
    objects, vehicle = load_road(tmp_path)
    assert bpy.ops.gtatools.nodes_to_curves() == {'FINISHED'}
    curve = next(o for o in bpy.context.scene.objects
                 if o.type == 'CURVE' and o.get('sapath_type') == 2)
    if not keep_source_meshes:
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    # Simulate a saved curve from the old converter, without recoverable IDs.
    del curve['inu_nodes_curve_source']
    activate(curve)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    # Exercise direct calls and the interactive invocation, both with an
    # existing destination and a new destination. Entire-map mode must
    # also leave every other region untouched and create no empty files.
    for destination in (tmp_path/'nodes37.dat', tmp_path/'nodes28.dat'):
        with pytest.raises(RuntimeError, match='Compiled NODES'):
            bpy.ops.gtatools.curves_to_nodes(call_context, filepath=str(destination), entire_map=True)
        assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    # Conversion remains available for viewing; normal mesh export is
    # still the supported route and must preserve the untouched DAT.
    if keep_source_meshes:
        activate(vehicle)
        assert bpy.ops.gtatools.export_nodes(directory=str(tmp_path)) == {'FINISHED'}
        assert (tmp_path/'nodes37.dat').read_bytes() == before['nodes37.dat']


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


def converted_curves(objects, categories=('nodes_vehicle', 'nodes_ped')):
    for obj in objects:
        if obj.get('path_type') in categories:
            activate(obj)
            assert bpy.ops.gtatools.nodes_to_curves() == {'FINISHED'}
    curves = [o for o in bpy.context.scene.objects if o.type == 'CURVE' and o.get('inu_nodes_curve_source')]
    activate(curves[0])
    return curves


def curve_extrude(curve):
    activate(curve)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.curve.select_all(action='DESELECT')
    curve.data.splines[0].points[-1].select = True
    assert bpy.ops.curve.extrude_move(TRANSFORM_OT_translate={'value': (20, 0, 0)}) == {'FINISHED'}


@pytest.mark.parametrize('convert_peds', [False, True])
def test_native_curves_roundtrip_survives_mesh_deletion_and_reload(tmp_path, convert_peds):
    objects, vehicle = load_road(tmp_path, peds=True)
    before = (tmp_path/'nodes37.dat').read_bytes()
    curves = converted_curves(objects, ('nodes_vehicle', 'nodes_ped') if convert_peds else ('nodes_vehicle',))
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    blend = tmp_path/'curves.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.wm.open_mainfile(filepath=str(blend), load_ui=False)
    curve = next(o for o in bpy.context.scene.objects if o.type == 'CURVE' and o.get('sapath_type') == 2)
    activate(curve)  # Selecting one chain includes all companion curves/category data.
    assert bpy.ops.gtatools.curves_to_nodes(filepath=str(tmp_path/'nodes37.dat')) == {'FINISHED'}
    assert (tmp_path/'nodes37.dat').read_bytes() == before


@pytest.mark.parametrize('edit', ['extrude', 'subdivide', 'duplicate'])
def test_native_curve_point_edits_rebuild_navigation(tmp_path, edit):
    objects, _ = load_road(tmp_path)
    curve = converted_curves(objects)[0]
    if edit == 'extrude':
        curve_extrude(curve)
        expected = {(0, 1), (1, 2)}
    else:
        activate(curve)
        bpy.ops.object.mode_set(mode='EDIT')
        if edit == 'subdivide':
            bpy.ops.curve.select_all(action='SELECT')
            assert bpy.ops.curve.subdivide(number_cuts=1) == {'FINISHED'}
            expected = {(0, 2), (1, 2)}
        else:
            bpy.ops.curve.select_all(action='DESELECT')
            curve.data.splines[0].points[-1].select = True
            assert bpy.ops.curve.duplicate_move(TRANSFORM_OT_translate={'value': (20, 0, 0)}) == {'FINISHED'}
            expected = {(0, 1)}  # A duplicated isolated point has no invented edge.
    # Read the live Curve Edit Mode data, without forcing an Object Mode switch.
    assert bpy.ops.gtatools.curves_to_nodes(filepath=str(tmp_path/'nodes37.dat')) == {'FINISHED'}
    nf = read_nodes(str(tmp_path/'nodes37.dat'))
    assert len(nf.vehicle_nodes) == 3
    assert graph_edges(nf, 37) == expected
    assert [n.node_id for n in nf.vehicle_nodes] == [0, 1, 2]
    assert len(nf.links) == len(nf.navi_links) == len(nf.link_lengths)
    validate_graph_batch({37: nf})
    if edit == 'subdivide':
        assert len(nf.navi_nodes) == 3
        assert all(n.flags == road().navi_nodes[0].flags for n in nf.navi_nodes)


def test_native_curve_partial_reindex_leaves_files_unchanged(tmp_path):
    objects, _ = load_road(tmp_path, peds=True)
    curve = next(c for c in converted_curves(objects) if c.get('sapath_type') == 2)
    curve_extrude(curve)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(RuntimeError, match='all 64 regions'):
        bpy.ops.gtatools.curves_to_nodes(filepath=str(tmp_path/'nodes37.dat'))
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_native_curves_keep_distinct_coincident_originals_and_per_node_properties(tmp_path):
    nf = road(peds=True)
    nf.vehicle_nodes[1].path_width = 13
    nf.vehicle_nodes[1].flags |= 1 << 8
    nf.ped_nodes.append(PathNode(x=805, y=110, z=1, area_id=37, node_id=3, is_vehicle=False, node_type=3))
    path = tmp_path/'nodes37.dat'
    write_nodes(str(path), nf)
    before = path.read_bytes()
    objects = import_nodes(str(path), context=bpy.context)
    curves = converted_curves(objects)
    assert len(curves) == 3  # One road chain and two separate isolated pedestrian nodes.
    assert bpy.ops.gtatools.curves_to_nodes(filepath=str(path)) == {'FINISHED'}
    assert path.read_bytes() == before
    vehicle_curve = next(o for o in curves if o.get('sapath_type') == 2)
    vehicle_curve['sapath_width'] = 2.5
    activate(vehicle_curve)
    assert bpy.ops.gtatools.curves_to_nodes(filepath=str(path)) == {'FINISHED'}
    back = read_nodes(str(path))
    assert [n.path_width for n in back.vehicle_nodes] == [20, 20]
    assert back.vehicle_nodes[1].flags & (1 << 8)
    assert back.links == nf.links and back.navi_nodes == nf.navi_nodes


def test_native_curves_shared_junction_conflict_is_blocked(tmp_path):
    from INU_tools.core.paths_graph import rebuild_graph
    nodes = [PathNode(x=x, y=y, z=1, area_id=37, node_id=i, flags=0xF0000, path_width=8)
             for i, (x, y) in enumerate([(800, 100), (820, 100), (800, 120), (780, 100)])]
    nf, _, _ = rebuild_graph(NodesFile(parsed_extras=True), nodes, [None]*4,
                              {(0, 1), (0, 2), (0, 3)}, area=37, vehicle_count=4)
    path = tmp_path/'nodes37.dat'
    write_nodes(str(path), nf)
    before = path.read_bytes()
    curves = converted_curves(import_nodes(str(path), context=bpy.context))
    assert len(curves) == 3
    curves[0].data.splines[0].points[0].co.x += 2
    with pytest.raises(RuntimeError, match='Shared NODES junction'):
        bpy.ops.gtatools.curves_to_nodes(filepath=str(path))
    assert path.read_bytes() == before
    for curve in curves[1:]:
        curve.data.splines[0].points[0].co.x += 2
    assert bpy.ops.gtatools.curves_to_nodes(filepath=str(path)) == {'FINISHED'}
    assert read_nodes(str(path)).vehicle_nodes[0].x == 802


def test_native_curves_cycle_and_reversed_direction_keep_original_ids(tmp_path):
    from INU_tools.core.paths_graph import rebuild_graph
    nodes = [PathNode(x=x, y=y, z=1, area_id=37, node_id=i, flags=0xF0000, path_width=8)
             for i, (x, y) in enumerate([(800, 100), (820, 100), (800, 120)])]
    nf, _, _ = rebuild_graph(NodesFile(parsed_extras=True), nodes, [None]*3,
                              {(0, 1), (1, 2), (0, 2)}, area=37, vehicle_count=3)
    path = tmp_path/'nodes37.dat'
    write_nodes(str(path), nf)
    before = path.read_bytes()
    curve = converted_curves(import_nodes(str(path), context=bpy.context))[0]
    assert len(curve.data.splines[0].points) == 4
    activate(curve)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.curve.select_all(action='SELECT')
    assert bpy.ops.curve.switch_direction() == {'FINISHED'}
    assert bpy.ops.gtatools.curves_to_nodes(filepath=str(path)) == {'FINISHED'}
    assert path.read_bytes() == before


def test_native_curves_lane_controls_use_spline_direction(tmp_path):
    from INU_tools.core.paths import decode_navi_flags
    objects, _ = load_road(tmp_path)
    curve = converted_curves(objects)[0]
    curve['sapath_laneleft'] = 1
    curve['sapath_laneright'] = 3
    curve['sapath_traffic'] = 2
    assert bpy.ops.gtatools.curves_to_nodes(filepath=str(tmp_path/'nodes37.dat')) == {'FINISHED'}
    nf = read_nodes(str(tmp_path/'nodes37.dat'))
    flags = decode_navi_flags(nf.navi_nodes[0].flags)
    assert (flags['left_lanes'], flags['right_lanes'], flags['traffic_light']) == (3, 1, 2)
    assert nf.links == road().links


def test_native_curves_missing_source_and_whole_object_duplicates_are_blocked(tmp_path):
    objects, _ = load_road(tmp_path)
    curve = converted_curves(objects)[0]
    path = tmp_path/'nodes37.dat'
    before = path.read_bytes()
    duplicate = curve.copy()
    duplicate.data = curve.data.copy()
    bpy.context.scene.collection.objects.link(duplicate)
    duplicate.location.y += 10
    with pytest.raises(RuntimeError, match='Duplicated NODES curve objects'):
        bpy.ops.gtatools.curves_to_nodes(filepath=str(path))
    assert path.read_bytes() == before
    bpy.data.objects.remove(duplicate, do_unlink=True)
    source = next(o for o in bpy.context.scene.objects if o.get('inu_nodes_curve_snapshot'))
    bpy.data.objects.remove(source, do_unlink=True)
    with pytest.raises(RuntimeError, match='source is missing'):
        bpy.ops.gtatools.curves_to_nodes(filepath=str(path))
    assert path.read_bytes() == before


def test_native_curves_binary_preflight_preserves_all_destinations(tmp_path):
    from INU_tools.ops.path_nodes_curves import write_curve_export
    valid, invalid = road(), road()
    invalid.vehicle_nodes[0].x = 10000  # Cannot fit the vanilla signed 16-bit coordinate.
    for area in (37, 42):
        (tmp_path/f'nodes{area}.dat').write_bytes(b'Keep existing region')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(struct.error):
        write_curve_export(str(tmp_path/'nodes37.dat'), {37: valid, 42: invalid})
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_native_curves_vanilla28_roundtrip_keeps_every_arc(vanilla_files, tmp_path):
    source = next(p for p in vanilla_files if p.stem.lower() == 'nodes28')
    original = read_nodes(str(source))
    path = tmp_path/'nodes28.dat'
    write_nodes(str(path), original)
    before = path.read_bytes()
    objects = import_nodes(str(source), context=bpy.context)
    curves = converted_curves(objects)
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    activate(curves[-1])
    assert bpy.ops.gtatools.curves_to_nodes(filepath=str(path)) == {'FINISHED'}
    assert path.read_bytes() == before  # IDs, directed/foreign arcs, navigation and all tail sections.


def test_native_curves_full_vanilla_reindex_updates_foreign_regions(vanilla_files, tmp_path):
    imported, originals = [], {}
    for path in vanilla_files:
        originals[int(path.stem[5:])] = read_nodes(str(path))
        imported.extend(import_nodes(str(path), context=bpy.context))
    region = [o for o in imported if o.get('nodes_area') == 37]
    curves = converted_curves(region)
    curve = next(o for o in curves if o.get('sapath_type') == 2 and len(o.data.splines[0].points) > 1)
    curve_extrude(curve)
    assert bpy.ops.gtatools.curves_to_nodes(filepath=str(tmp_path/'nodes37.dat'), entire_map=True) == {'FINISHED'}
    result = {area: read_nodes(str(tmp_path/f'nodes{area}.dat')) for area in range(64)}
    validate_graph_batch(result)
    old_vehicle_count = len(originals[37].vehicle_nodes)
    assert len(result[37].vehicle_nodes) == old_vehicle_count + 1
    assert result[37].ped_nodes[0].node_id == old_vehicle_count + 1
    for area, original in originals.items():
        if area == 37:
            continue
        expected = [(l.area_id, l.node_id+1 if l.area_id == 37 and l.node_id >= old_vehicle_count else l.node_id)
                    for l in original.links]
        assert [(l.area_id, l.node_id) for l in result[area].links] == expected


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
