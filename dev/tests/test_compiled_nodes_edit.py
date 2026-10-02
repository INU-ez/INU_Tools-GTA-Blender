"""Compiled SA graph editing, binary output and all-region reference safety."""

import ast
import copy
import importlib.util
import os
from pathlib import Path
import struct
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'INU_tools'))
from core.paths import (NodesFile, PathNode, NaviNode, PathLink, read_nodes,
                        write_nodes, encode_navi_flags)
from core.paths_graph import (rebuild_graph, graph_edges, navi_address,
                              remap_foreign_references, validate_graph_batch)


class Co:
    def __init__(self, x, y=100, z=1):
        self.x, self.y, self.z = x, y, z


class Identity:
    def __matmul__(self, value):
        return value


class AttributeData(list):
    def foreach_set(self, field, values):
        for item, value in zip(self, values):
            setattr(item, field, value)


class Attributes(dict):
    def __init__(self, mesh):
        super().__init__()
        self.mesh = mesh

    def new(self, name, data_type, domain):
        result = types.SimpleNamespace(data_type=data_type, domain=domain,
            data=AttributeData(types.SimpleNamespace(value=0) for _ in self.mesh.vertices))
        self[name] = result
        return result


class Mesh:
    def __init__(self, nodes, edges=()):
        self.vertices = [types.SimpleNamespace(co=Co(n.x, n.y, n.z), select=False) for n in nodes]
        self.edges = [types.SimpleNamespace(vertices=e) for e in edges]
        self.attributes = Attributes(self)


class Obj(dict):
    type = 'MESH'
    matrix_world = Identity()
    def __init__(self, nodes, edges=(), **props):
        super().__init__(props)
        self.data = Mesh(nodes, edges)
        self.flushed = 0

    def update_from_editmode(self):
        self.flushed += 1


@pytest.fixture
def adapter(monkeypatch):
    import core.paths, core.paths_graph
    for name in ('compiled_test', 'compiled_test.ops', 'compiled_test.core'):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, 'compiled_test.core.paths', core.paths)
    monkeypatch.setitem(sys.modules, 'compiled_test.core.paths_graph', core.paths_graph)
    name = 'compiled_test.ops.path_nodes_mesh'
    spec = importlib.util.spec_from_file_location(name, ROOT / 'INU_tools/ops/path_nodes_mesh.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def road(area=37, peds=True):
    return NodesFile(
        vehicle_nodes=[PathNode(x=800, y=100, z=1, area_id=area, node_id=0,
                               link_id=0, flags=0xF0001, path_width=8, node_type=1),
                       PathNode(x=820, y=100, z=1, area_id=area, node_id=1,
                               link_id=1, flags=0xF0001, path_width=8, node_type=1)],
        ped_nodes=[PathNode(x=805, y=110, z=1, area_id=area, node_id=2,
                            is_vehicle=False, node_type=4)] if peds else [],
        navi_nodes=[NaviNode(x=810, y=100, area_id=area, node_id=0,
                            dir_x=-100, flags=encode_navi_flags(left_lanes=0, right_lanes=2))],
        links=[PathLink(area, 1), PathLink(area, 0)],
        navi_links=[navi_address(area, 0)] * 2, link_lengths=[20, 20],
        path_intersections=[3, 1] + [7] * 192, parsed_extras=True)


def objects(adapter, nf, area=37):
    created = []
    visible = graph_edges(nf, area)
    offset = 0
    for category, nodes in (('nodes_vehicle', nf.vehicle_nodes), ('nodes_ped', nf.ped_nodes)):
        if not nodes and (created or nf.navi_nodes):
            offset += len(nodes)
            continue
        edges = [(a-offset, b-offset) for a, b in visible if offset <= a < b < offset+len(nodes)]
        obj = Obj(nodes, edges, path_type=category, nodes_filename=f'nodes{area}.dat',
                  node_count=len(nodes))
        for key, field in (('links', 'link_id'), ('areas', 'area_id'), ('ids', 'node_id'),
                           ('widths', 'path_width'), ('types', 'node_type'), ('flags', 'flags')):
            obj['node_' + key] = [getattr(n, field) for n in nodes]
        adapter.initialize_node_identity(obj, nodes)
        created.append(obj)
        offset += len(nodes)
    if nf.navi_nodes:
        nav = Obj([PathNode(x=n.x, y=n.y) for n in nf.navi_nodes], path_type='nodes_navi',
                  nodes_filename=f'nodes{area}.dat', navi_count=len(nf.navi_nodes))
        for key, field in (('areas', 'area_id'), ('ids', 'node_id'), ('dx', 'dir_x'),
                           ('dy', 'dir_y'), ('flags', 'flags')):
            nav['navi_' + key] = [getattr(n, field) for n in nf.navi_nodes]
        adapter.initialize_node_identity(nav, [PathNode(x=n.x, y=n.y) for n in nf.navi_nodes])
        created.append(nav)
    import base64
    for obj in created:
        obj.update(nodes_area=area, nodes_source_key=str(area), fla4=nf.fla4,
                   nodes_vehicle_count=len(nf.vehicle_nodes), nodes_ped_count=len(nf.ped_nodes),
                   nodes_navi_count=len(nf.navi_nodes), num_links=len(nf.links),
                   link_areas=[l.area_id for l in nf.links], link_nodes=[l.node_id for l in nf.links],
                   parsed_extras=nf.parsed_extras, navi_links=nf.navi_links,
                   link_lengths=nf.link_lengths, path_intersections=nf.path_intersections)
        if nf.extra_data:
            obj['extra_data_b64'] = base64.b64encode(nf.extra_data).decode()
    return created


def add_vertex(obj, x, *, copied_from=None):
    obj.data.vertices.append(types.SimpleNamespace(co=Co(x), select=True))
    layer = obj.data.attributes['inu_node_identity']
    layer.data.append(types.SimpleNamespace(value=layer.data[copied_from].value if copied_from is not None else 0))


def edge(obj, *pairs):
    obj.data.edges = [types.SimpleNamespace(vertices=p) for p in pairs]


def test_unedited_roundtrip_preserves_binary_and_flushes_edit_mode(adapter, tmp_path):
    nf = road()
    meshes = objects(adapter, nf)
    result = adapter.collect_compiled_nodes(meshes)
    assert not result.topology_changed and result.node_remap == {}
    assert all(o.flushed == 1 for o in meshes)
    old, new = tmp_path/'old.dat', tmp_path/'new.dat'
    write_nodes(str(old), nf)
    write_nodes(str(new), result)
    assert new.read_bytes() == old.read_bytes()


@pytest.mark.parametrize('copied', [None, 1])
def test_extrude_adds_connected_vehicle_and_real_navigation(adapter, tmp_path, copied):
    meshes = objects(adapter, road())
    veh = meshes[0]
    add_vertex(veh, 840, copied_from=copied)
    edge(veh, (0, 1), (1, 2))
    result = adapter.collect_compiled_nodes(meshes)
    assert result.node_remap == {(37, 2): 3}
    assert graph_edges(result, 37) == {(0, 1), (1, 2)}
    assert [n.node_id for n in result.vehicle_nodes + result.ped_nodes] == list(range(4))
    assert len(result.navi_nodes) == 2
    assert result.navi_links[-1] == navi_address(37, 1)
    nav = result.navi_nodes[1]
    assert (nav.x, nav.y, nav.area_id, nav.node_id, nav.dir_x) == (830, 100, 37, 1, -100)
    assert nav.flags & 0x3F00 == encode_navi_flags(left_lanes=1, right_lanes=1)
    validate_graph_batch({37: result})
    path = tmp_path/'nodes37.dat'
    write_nodes(str(path), result)
    back = read_nodes(str(path))
    assert graph_edges(back, 37) == {(0, 1), (1, 2)}
    assert len(back.links) == len(back.navi_links) == len(back.link_lengths) == 4
    assert len(back.path_intersections) == 4 + 192
    assert back.path_intersections[-192:] == [7]*192
    assert back.vehicle_nodes[2].node_type == 1


def test_reordered_vertices_keep_properties_and_game_ids(adapter):
    meshes = objects(adapter, road())
    veh = meshes[0]
    veh.data.vertices.reverse()
    veh.data.attributes['inu_node_identity'].data.reverse()
    result = adapter.collect_compiled_nodes(meshes)
    assert not result.topology_changed
    assert [(n.x, n.node_id) for n in result.vehicle_nodes] == [(800, 0), (820, 1)]


def test_subdivision_preserves_one_way_lanes_and_navigation_orientation(adapter):
    meshes = objects(adapter, road(peds=False))
    add_vertex(meshes[0], 810, copied_from=0)
    edge(meshes[0], (0, 2), (2, 1))
    nf = adapter.collect_compiled_nodes(meshes)
    assert nf.node_remap == {}
    assert graph_edges(nf, 37) == {(0, 2), (1, 2)}
    assert len(nf.navi_nodes) == 3
    assert all(n.flags == encode_navi_flags(left_lanes=0, right_lanes=2) for n in nf.navi_nodes)
    assert (nf.navi_nodes[1].node_id, nf.navi_nodes[1].dir_x) == (0, -100)
    assert (nf.navi_nodes[2].node_id, nf.navi_nodes[2].dir_x) == (2, -100)
    validate_graph_batch({37: nf})


def test_subdivision_keeps_original_one_direction_graph(adapter):
    original = road(peds=False)
    original.vehicle_nodes[1].flags &= ~15
    original.links.pop(); original.navi_links.pop(); original.link_lengths.pop()
    original.path_intersections = [3]+[7]*192
    meshes = objects(adapter, original)
    add_vertex(meshes[0], 810)
    edge(meshes[0], (0, 2), (2, 1))
    nf = adapter.collect_compiled_nodes(meshes)
    assert nf.links == [PathLink(37, 2), PathLink(37, 1)]
    assert [n.flags & 15 for n in nf.vehicle_nodes] == [1, 0, 1]
    validate_graph_batch({37: nf})


def test_ped_new_edge_does_not_shift_old_ids_or_generate_car_navigation(adapter):
    meshes = objects(adapter, road())
    ped = meshes[1]
    add_vertex(ped, 815)
    edge(ped, (0, 1))
    result = adapter.collect_compiled_nodes(meshes)
    assert result.node_remap == {}
    assert graph_edges(result, 37) == {(0, 1), (2, 3)}
    assert len(result.navi_nodes) == 1
    assert not result.ped_nodes[-1].is_vehicle


def test_delete_first_vertex_keeps_survivor_metadata_and_drops_incoming_link(adapter):
    nf = road()
    meshes = objects(adapter, nf)
    veh = meshes[0]
    veh.data.vertices.pop(0)
    veh.data.attributes['inu_node_identity'].data.pop(0)
    edge(veh)
    result = adapter.collect_compiled_nodes(meshes)
    assert result.node_remap == {(37, 0): None, (37, 1): 0, (37, 2): 1}
    assert [(n.x, n.node_id) for n in result.vehicle_nodes] == [(820, 0)]
    assert result.links == []
    neighbor = NodesFile(ped_nodes=[PathNode(area_id=38, node_id=0, flags=2)],
                         links=[PathLink(37, 0), PathLink(37, 1)], navi_links=[0, 0],
                         link_lengths=[12, 13], path_intersections=[2, 3] + [8]*192,
                         parsed_extras=True)
    remap_foreign_references(neighbor, result.node_remap, area=38)
    assert neighbor.links == [PathLink(37, 0)]
    assert neighbor.link_lengths == [13] and neighbor.path_intersections[:1] == [3]
    assert neighbor.ped_nodes[0].flags & 15 == 1
    validate_graph_batch({37: result, 38: neighbor})


def test_delete_edge_preserves_foreign_and_cross_category_links():
    nf = road()
    nf.vehicle_nodes[0].flags += 2
    nf.vehicle_nodes[1].link_id = 3
    nf.links = [PathLink(37, 1), PathLink(38, 10), PathLink(37, 2), PathLink(37, 0)]
    nf.navi_links = [navi_address(37, 0)]*4
    nf.link_lengths = [20, 30, 4, 20]
    nf.path_intersections = [1, 2, 3, 4]+[0]*192
    edited, _, changed = rebuild_graph(nf, copy.deepcopy(nf.vehicle_nodes+nf.ped_nodes),
                                       [0, 1, 2], set(), area=37, vehicle_count=2)
    assert changed and edited.links == [PathLink(38, 10), PathLink(37, 2)]
    assert edited.link_lengths == [30, 4]


def test_unchanged_one_direction_edge_keeps_direction_and_tail():
    nf = road(peds=False)
    nf.vehicle_nodes[1].flags &= ~15
    nf.links.pop(); nf.navi_links.pop(); nf.link_lengths.pop()
    nf.path_intersections = [3]+[7]*192
    result, _, _ = rebuild_graph(nf, copy.deepcopy(nf.vehicle_nodes), [0, 1],
                                 {(0, 1)}, area=37, vehicle_count=2)
    assert result.links == [PathLink(37, 1)]


@pytest.mark.parametrize('delta', [-10, 10])
@pytest.mark.parametrize('selected', [False, True])
def test_equidistant_distinct_duplicates_export_connected_graph(adapter, tmp_path, delta, selected):
    meshes = objects(adapter, road(peds=False))
    veh = meshes[0]
    veh.data.vertices[1].co.x += delta
    add_vertex(veh, 820-delta, copied_from=1)
    veh.data.vertices[1].select = selected
    veh.data.vertices[2].select = selected
    edge(veh, (0, 1), (1, 2))
    result = adapter.collect_compiled_nodes(meshes)
    assert not result.node_remap
    assert [(n.x, n.node_id) for n in result.vehicle_nodes] == [(800, 0), (820+delta, 1), (820-delta, 2)]
    path = tmp_path/'nodes37.dat'
    write_nodes(str(path), result)
    back = read_nodes(str(path))
    assert graph_edges(back, 37) == {(0, 1), (1, 2)}
    validate_graph_batch({37: back})


def test_reject_ambiguous_coincident_duplicates(adapter):
    meshes = objects(adapter, road())
    meshes[0].name = 'NODES37_Vehicle'
    add_vertex(meshes[0], 820, copied_from=1)
    meshes[0].data.vertices[1].select = True
    with pytest.raises(ValueError, match='Coincident') as error:
        adapter.collect_compiled_nodes(meshes)
    assert 'NODES37_Vehicle' in str(error.value)
    assert 'vertex indices 1 and 2' in str(error.value)
    assert 'move the new point or merge' in str(error.value)


def test_legacy_scene_requires_reimport_if_already_changed(adapter):
    meshes = objects(adapter, road())
    del meshes[0]['nodes_identity_version']
    add_vertex(meshes[0], 840)
    with pytest.raises(ValueError, match='Reimport'):
        adapter.collect_compiled_nodes(meshes)


def test_old_unchanged_scene_can_migrate_once(adapter):
    meshes = objects(adapter, road())
    del meshes[0]['nodes_identity_version']
    del meshes[0].data.attributes['inu_node_identity']
    nf = adapter.collect_compiled_nodes(meshes)
    assert not nf.topology_changed and meshes[0]['nodes_identity_version'] == 1


def test_raw_tail_refuses_topology_edit(adapter):
    nf = road(); nf.parsed_extras = False; nf.extra_data = b'unknown'
    meshes = objects(adapter, nf)
    edge(meshes[0])
    with pytest.raises(ValueError, match='parsed link sections'):
        adapter.collect_compiled_nodes(meshes)


def test_new_point_outside_region_is_rejected(adapter):
    meshes = objects(adapter, road())
    add_vertex(meshes[0], 100)
    with pytest.raises(ValueError, match='outside its region'):
        adapter.collect_compiled_nodes(meshes)


def test_navigation_topology_cannot_silently_corrupt_arrays(adapter):
    meshes = objects(adapter, road())
    add_vertex(meshes[-1], 800)
    with pytest.raises(ValueError, match='navigation vertices'):
        adapter.collect_compiled_nodes(meshes)


def test_auto_collects_region_companions_but_excludes_other_imports(adapter):
    meshes = objects(adapter, road())
    duplicate = objects(adapter, road())
    for o in duplicate:
        o['nodes_source_key'] = 'different-import'
    result = adapter.complete_node_objects([meshes[0]], meshes+duplicate)
    assert len(result) == 3 and all(a is b for a, b in zip(result, meshes))
    with pytest.raises(ValueError, match='every vehicle and pedestrian'):
        adapter.collect_compiled_nodes([meshes[0]])


def test_capacity_limits_refuse_unrepresentable_graph():
    nf = NodesFile(parsed_extras=True)
    nodes = [PathNode(x=800+i, y=100, area_id=37, node_id=i) for i in range(17)]
    with pytest.raises(ValueError, match='15 outgoing'):
        rebuild_graph(nf, nodes, [None]*17, {(0, i) for i in range(1, 17)},
                      area=37, vehicle_count=0)
    nf.navi_nodes = [NaviNode() for _ in range(1024)]
    with pytest.raises(ValueError, match='capacity'):
        rebuild_graph(nf, nodes[:2], [None, None], {(0, 1)}, area=37, vehicle_count=2)


def test_quantized_coincident_vehicle_points_are_rejected():
    nf = NodesFile(parsed_extras=True)
    nodes = [PathNode(x=-0.1, y=100), PathNode(x=0.1, y=100)]
    with pytest.raises(ValueError, match='distinct XY'):
        rebuild_graph(nf, nodes, [None, None], {(0, 1)}, area=36, vehicle_count=2)


def test_navigation_address_does_not_silently_wrap():
    nf = road()
    nf.navi_links[0] = 1 << 16
    with pytest.raises(ValueError, match='Invalid navigation'):
        validate_graph_batch({37: nf})


@pytest.mark.parametrize('empty', [False, True])
def test_read_nodes_parses_sector_padding_and_zero_link_tail(tmp_path, empty):
    nf = NodesFile(parsed_extras=True) if empty else road()
    path = tmp_path/'nodes37.dat'
    write_nodes(str(path), nf)
    original = path.read_bytes()
    path.write_bytes(original + b'\0' * ((-len(original)) % 2048))
    back = read_nodes(str(path))
    assert back.parsed_extras and not back.extra_data
    write_nodes(str(path), back)
    assert path.read_bytes() == original


def test_unknown_nonzero_tail_remains_raw(tmp_path):
    path = tmp_path/'nodes37.dat'
    write_nodes(str(path), road())
    path.write_bytes(path.read_bytes()+b'\x01')
    result = read_nodes(str(path))
    assert not result.parsed_extras and result.extra_data


def _load_function(filename, function, *, cls=None, **namespace):
    path = ROOT / 'INU_tools/ops' / filename
    tree = ast.parse(path.read_text(encoding='utf-8'))
    body = next(n.body for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls) if cls else tree.body
    target = next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == function)
    namespace['__package__'] = 'compiled_test.ops'
    exec(compile(ast.Module(body=[target], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[function]


def test_import_visualization_resolves_physical_indices_for_foreign_stubs():
    compute = _load_function('path_import.py', '_compute_intra_category_edges')
    nf = NodesFile(vehicle_nodes=[PathNode(area_id=52, node_id=9, flags=1),
                                  PathNode(area_id=37, node_id=2),
                                  PathNode(area_id=37, node_id=1)], links=[PathLink(37, 1)])
    assert compute(nf, True, area=37) == [(0, 1)]


def test_noncanonical_unedited_file_keeps_original_identity_fields(adapter):
    nf = road(peds=False)
    nf.vehicle_nodes[0].node_id = 17
    meshes = objects(adapter, nf)
    assert adapter.collect_compiled_nodes(meshes).vehicle_nodes[0].node_id == 17
    edge(meshes[0])
    with pytest.raises(ValueError, match='noncanonical'):
        adapter.collect_compiled_nodes(meshes)


def test_direct_export_collects_companions_from_context(adapter, tmp_path):
    meshes = objects(adapter, road())
    bpy = types.SimpleNamespace(context=types.SimpleNamespace(selected_objects=[meshes[0]],
                                 scene=types.SimpleNamespace(objects=meshes)))
    export = _load_function('path_export.py', 'export_nodes', write_nodes=write_nodes, bpy=bpy)
    path = tmp_path/'nodes37.dat'
    assert export(str(path), emit_roadblox=False, emit_connectors=False) == 3
    back = read_nodes(str(path))
    assert len(back.ped_nodes) == len(back.navi_nodes) == 1
    assert graph_edges(back, 37) == {(0, 1)}


@pytest.fixture
def operator(adapter, monkeypatch, tmp_path):
    export = _load_function('path_export.py', 'export_nodes', write_nodes=write_nodes)
    module = types.ModuleType('compiled_test.ops.path_export')
    module.export_nodes = export
    monkeypatch.setitem(sys.modules, module.__name__, module)
    execute = _load_function('world_ops.py', 'execute', cls='GTATOOLS_OT_export_nodes',
                             os=os, T=lambda text: text)
    reports = []
    instance = types.SimpleNamespace(directory=str(tmp_path), fla4=False,
                                     report=lambda levels, text: reports.append((levels, text)))
    def run(selected, scene=None):
        return execute(instance, types.SimpleNamespace(selected_objects=selected,
                       scene=types.SimpleNamespace(objects=scene or selected)))
    return run, reports


def test_operator_blocks_partial_reindex_without_touching_destination(adapter, operator, tmp_path):
    meshes = objects(adapter, road())
    add_vertex(meshes[0], 840, copied_from=1)
    edge(meshes[0], (0, 1), (1, 2))
    path = tmp_path/'nodes37.dat'
    path.write_bytes(b'original-file')
    run, reports = operator
    assert run([meshes[0]], meshes) == {'CANCELLED'}
    assert path.read_bytes() == b'original-file'
    assert list(tmp_path.iterdir()) == [path]
    assert any('64' in message for _, message in reports)


def test_operator_exports_new_edge_without_selecting_nav_companion(adapter, operator, tmp_path):
    meshes = objects(adapter, road(peds=False))
    add_vertex(meshes[0], 840)
    edge(meshes[0], (0, 1), (1, 2))
    run, reports = operator
    assert run([meshes[0]], meshes) == {'FINISHED'}
    back = read_nodes(str(tmp_path/'nodes37.dat'))
    assert graph_edges(back, 37) == {(0, 1), (1, 2)}
    validate_graph_batch({37: back})


def test_operator_binary_preflight_leaves_original_file_on_coordinate_error(adapter, operator, tmp_path):
    meshes = objects(adapter, road(peds=False))
    add_vertex(meshes[0], 840)
    meshes[0].data.vertices[-1].co.z = 5000
    edge(meshes[0], (0, 1), (1, 2))
    path = tmp_path/'nodes37.dat'
    path.write_bytes(b'original-file')
    run, reports = operator
    assert run(meshes) == {'CANCELLED'}
    assert path.read_bytes() == b'original-file'
    assert list(tmp_path.iterdir()) == [path]


def test_operator_full_batch_remaps_neighbor_and_preserves_local_navigation(adapter, operator, tmp_path):
    neighbors = NodesFile(ped_nodes=[PathNode(area_id=38, node_id=0, flags=1, is_vehicle=False)],
                          links=[PathLink(37, 2)], navi_links=[0], link_lengths=[40],
                          path_intersections=[2]+[0]*192, parsed_extras=True)
    meshes = []
    for area in range(64):
        meshes.extend(objects(adapter, road() if area == 37 else neighbors if area == 38
                              else NodesFile(parsed_extras=True), area))
    veh = next(o for o in meshes if o.get('nodes_area') == 37 and o.get('path_type') == 'nodes_vehicle')
    add_vertex(veh, 840)
    edge(veh, (0, 1), (1, 2))
    run, reports = operator
    assert run(meshes) == {'FINISHED'}, reports
    exported = {area: read_nodes(str(tmp_path/f'nodes{area}.dat')) for area in range(64)}
    assert exported[38].links == [PathLink(37, 3)]
    assert exported[37].ped_nodes[0].node_id == 3
    assert graph_edges(exported[37], 37) == {(0, 1), (1, 2)}
    validate_graph_batch(exported)


def test_edge_edit_plus_bare_merge_still_remaps_incoming_ped_ids(adapter, operator, tmp_path):
    neighbor = NodesFile(ped_nodes=[PathNode(area_id=38, node_id=0, flags=1, is_vehicle=False)],
                          links=[PathLink(37, 2)], navi_links=[0], link_lengths=[40],
                          path_intersections=[2]+[0]*192, parsed_extras=True)
    meshes = []
    for area in range(64):
        meshes.extend(objects(adapter, road() if area == 37 else neighbor if area == 38
                              else NodesFile(parsed_extras=True), area))
    veh = next(o for o in meshes if o.get('nodes_area') == 37 and o.get('path_type') == 'nodes_vehicle')
    edge(veh)
    meshes.append(Obj([PathNode(x=840, y=100)], path_type='nodes_vehicle'))
    run, reports = operator
    assert run(meshes) == {'FINISHED'}, reports
    result = read_nodes(str(tmp_path/'nodes38.dat'))
    assert result.links == [PathLink(37, 3)]


def test_new_connected_road_in_previously_empty_region(adapter, operator, tmp_path):
    meshes = objects(adapter, NodesFile(parsed_extras=True))
    add_vertex(meshes[0], 800)
    add_vertex(meshes[0], 820)
    edge(meshes[0], (0, 1))
    run, reports = operator
    assert run(meshes) == {'FINISHED'}, reports
    result = read_nodes(str(tmp_path/'nodes37.dat'))
    assert graph_edges(result, 37) == {(0, 1)}
    assert len(result.navi_nodes) == 1
    validate_graph_batch({37: result})


@pytest.fixture(scope='module')
def vanilla_regions(tmp_path_factory):
    archive = Path(r'D:\Grand Theft Auto San Andreas\models\gta3.img')
    if not archive.exists():
        pytest.skip('Optional vanilla SA nodes archive is unavailable')
    directory = tmp_path_factory.mktemp('vanilla_nodes')
    regions = {}
    with archive.open('rb') as stream:
        magic, count = struct.unpack('<4sI', stream.read(8))
        assert magic == b'VER2'
        entries = stream.read(count*32)
        for offset in range(0, len(entries), 32):
            sector, size, _, name = struct.unpack_from('<IHH24s', entries, offset)
            name = name.split(b'\0')[0].decode().lower()
            stem = name.rsplit('.', 1)[0]
            if not (name.endswith('.dat') and stem.startswith('nodes') and stem[5:].isdigit()):
                continue
            area = int(stem[5:])
            stream.seek(sector*2048)
            path = directory/name
            path.write_bytes(stream.read(size*2048))
            regions[area] = (read_nodes(str(path)), path.read_bytes())
    assert set(regions) == set(range(64))
    return regions


def test_vanilla_all_regions_roundtrip_matches_original_binary(adapter, vanilla_regions, tmp_path):
    exported = {}
    for area, (nf, original) in vanilla_regions.items():
        assert nf.parsed_extras and not nf.extra_data
        result = adapter.collect_compiled_nodes(objects(adapter, nf, area))
        assert not result.topology_changed and not result.node_remap
        path = tmp_path/f'nodes{area}.dat'
        write_nodes(str(path), result)
        binary = path.read_bytes()
        normalized = bytearray(original[:len(binary)])
        # Runtime pointer words are ignored by SA and already zeroed by
        # the existing writer. All actual graph bytes must remain exact.
        for index in range(len(nf.vehicle_nodes)+len(nf.ped_nodes)):
            normalized[20+index*28:28+index*28] = b'\0'*8
        assert binary == bytes(normalized), f'vanilla area {area} changed'
        assert not any(original[len(binary):])
        exported[area] = result
    validate_graph_batch(exported)


def test_vanilla_full_export_adds_vehicle_and_updates_neighbor_addresses(adapter, vanilla_regions, operator, tmp_path):
    meshes = []
    for area, (nf, _) in vanilla_regions.items():
        meshes.extend(objects(adapter, nf, area))
    veh = next(o for o in meshes if o.get('nodes_area') == 37 and o.get('path_type') == 'nodes_vehicle')
    add_vertex(veh, veh.data.vertices[0].co.x + 5, copied_from=0)
    veh.data.vertices[-1].co.y = veh.data.vertices[0].co.y
    edge(veh, *(e.vertices for e in veh.data.edges), (0, len(veh.data.vertices)-1))
    run, reports = operator
    assert run(meshes) == {'FINISHED'}, reports
    result = {area: read_nodes(str(tmp_path/f'nodes{area}.dat')) for area in range(64)}
    validate_graph_batch(result)
    assert len(result[37].vehicle_nodes) == len(vanilla_regions[37][0].vehicle_nodes)+1
    assert len(result[37].navi_nodes) == len(vanilla_regions[37][0].navi_nodes)+1
    assert all(n.node_id == i for i, n in enumerate(result[37].vehicle_nodes+result[37].ped_nodes))
    old_vehicle_count = len(vanilla_regions[37][0].vehicle_nodes)
    before = [(area, l.node_id) for area, (nf, _) in vanilla_regions.items() if area != 37
              for l in nf.links if l.area_id == 37 and l.node_id >= old_vehicle_count]
    after = [(area, l.node_id) for area, nf in result.items() if area != 37
             for l in nf.links if l.area_id == 37 and l.node_id >= old_vehicle_count+1]
    assert before and after == [(area, index+1) for area, index in before]


def test_vanilla_full_export_deletes_vehicle_without_dangling_addresses(adapter, vanilla_regions, operator, tmp_path):
    meshes = []
    for area, (nf, _) in vanilla_regions.items():
        meshes.extend(objects(adapter, nf, area))
    veh = next(o for o in meshes if o.get('nodes_area') == 37 and o.get('path_type') == 'nodes_vehicle')
    veh.data.vertices.pop(0)
    veh.data.attributes['inu_node_identity'].data.pop(0)
    edge(veh, *((a-1, b-1) for a, b in (e.vertices for e in veh.data.edges) if a and b))
    run, reports = operator
    assert run(meshes) == {'FINISHED'}, reports
    result = {area: read_nodes(str(tmp_path/f'nodes{area}.dat')) for area in range(64)}
    validate_graph_batch(result)
    assert len(result[37].vehicle_nodes) == len(vanilla_regions[37][0].vehicle_nodes)-1
    assert result[37].vehicle_nodes[0].x == vanilla_regions[37][0].vehicle_nodes[1].x
    assert all(n.node_id == i for i, n in enumerate(result[37].vehicle_nodes+result[37].ped_nodes))
