"""Path IPL columns, world scale, Edit Mode identities and round trips."""

import ast
import importlib.util
import pathlib
import os
import struct
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'INU_tools'))
from core.paths import (PathIPLFile, PathIPLGroup, PathIPLNode,
                        read_paths_ipl, parse_paths_ipl, write_paths_ipl,
                        PATH_FLAG_ROADBLOCK, decode_node_flags, encode_node_flags,
                        NodesFile, PathNode, NaviNode, PathLink, merge_bare_nodes,
                        remap_node_references,
                        split_nodes_by_area, read_nodes, write_nodes)

_spec = importlib.util.spec_from_file_location(
    'path_identity_test', ROOT / 'INU_tools/ops/path_ipl_props.py')
props = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(props)


class Co:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z

    def to_3d(self):
        return self

    def __truediv__(self, value):
        return Co(self.x / value, self.y / value, self.z / value)


class Identity:
    def __matmul__(self, co):
        return co


def point(x, *, weight=0, selected=False):
    return types.SimpleNamespace(co=Co(x, 5, 1), weight_softbody=weight,
                                 select=selected)


class Obj(dict):
    type = 'CURVE'

    def __init__(self, count=3, **values):
        super().__init__(path_type='path_ipl', pn_semantics_version=2,
                         group_type=1, pn_count=count, **values)
        self.data = types.SimpleNamespace(splines=[types.SimpleNamespace(
            type='POLY', points=[point(10 * k) for k in range(count)])])
        self.matrix_world = Identity()
        self.modifiers = []
        for slot in range(count):
            props.set_slot(self, slot, dict(link=slot + 1 if slot + 1 < count else -1))


def load_exporter():
    file = ROOT / 'INU_tools/ops/path_export.py'
    names = {'_path_ipl_node_props', 'export_paths_ipl'}
    tree = ast.parse(file.read_text(encoding='utf-8'))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = dict(PathIPLFile=PathIPLFile, PathIPLGroup=PathIPLGroup,
              PathIPLNode=PathIPLNode, write_paths_ipl=write_paths_ipl,
              parse_paths_ipl=parse_paths_ipl, slot_values=props.slot_values,
              ensure_point_slots=props.ensure_point_slots)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(file), 'exec'), ns)
    return ns['export_paths_ipl']


export = load_exporter()


def test_vc_column_semantics_and_sixteenths(tmp_path):
    source = b'path\n1, -1\n\t2, -1, 1, 2233.8, 19752, 161.083, 4.5, 2, 3, 1, 6, 0.75\nend\n'
    data = parse_paths_ipl(source)
    n = data.groups[0].nodes[0]
    assert (n.x, n.y, n.z) == (2233.8 / 16, 19752 / 16, 161.083 / 16)
    assert (n.crossing, n.width, n.left_lanes, n.right_lanes,
            n.speed_limit, n.flags, n.spawn_rate) == (1, 4.5, 2, 3, 1, 6, .75)
    dest = tmp_path / 'path.ipl'
    write_paths_ipl(str(dest), data)
    assert dest.read_bytes() == source
    n.x += .0625
    write_paths_ipl(str(dest), data)
    line = dest.read_text().splitlines()[2]
    assert '2234.8, 19752, 161.083, 4.5, 2, 3, 1, 6, 0.75' in line
    assert 'e+' not in line


def test_flags_are_vc_bits_not_sa_runtime_bits():
    assert PATH_FLAG_ROADBLOCK == 2
    assert decode_node_flags(7) == dict(disabled=True, between_levels=True, roadblock=True)
    assert encode_node_flags(disabled=True, roadblock=True, keep_bits=128) == 131


def test_iii_ide_columns_and_header(tmp_path):
    source = b'path\ncar, 33, road\n\t2, -1, 0, 160, 320, 16, 0, 2, 1\nend\n'
    data = parse_paths_ipl(source, game='III')
    n = data.groups[0].nodes[0]
    assert (n.x, n.y, n.z, n.left_lanes, n.right_lanes) == (10, 20, 1, 2, 1)
    n.x += 1
    dest = tmp_path / 'roads.ide'
    write_paths_ipl(str(dest), data)
    assert 'car, 33, road' in dest.read_text()
    assert '\t2, -1, 0, 176, 320, 16, 0, 2, 1' in dest.read_text()


def test_new_edit_points_get_defaults_and_flags_export(tmp_path):
    obj = Obj(2)
    props.ensure_point_slots(obj)
    obj.data.splines[0].points.insert(1, point(15, selected=True))
    pairs = props.ensure_point_slots(obj)
    slot = pairs[1][1]
    assert slot == 2
    assert props.slot_values(obj, slot) == props.FIELDS
    obj[f'pn_{slot}_flags'] = PATH_FLAG_ROADBLOCK
    dest = tmp_path / 'new.ipl'
    export(str(dest), [obj])
    nodes = read_paths_ipl(str(dest)).groups[0].nodes
    assert [n.flags for n in nodes[:3]] == [0, 2, 0]
    assert nodes[1].x == 15


def test_delete_insert_and_reorder_preserve_original_properties():
    obj = Obj(4)
    points = obj.data.splines[0].points
    props.ensure_point_slots(obj)
    obj['pn_2_flags'] = 2
    obj['pn_3_width'] = 7.5
    del points[0]
    points.insert(1, point(15))
    pairs = props.ensure_point_slots(obj)
    assert [s for _, s in pairs] == [1, 4, 2, 3]
    assert obj['pn_2_flags'] == 2 and obj['pn_4_flags'] == 0
    points.reverse()
    assert [s for _, s in props.ensure_point_slots(obj)] == [3, 2, 4, 1]


def test_bezier_and_multiple_splines_keep_identity_without_radius_changes():
    obj = Obj(1)
    obj.data.splines[0].points[0].radius = 2.5
    bezier = types.SimpleNamespace(co=Co(20, 5, 1), weight_softbody=0,
                                  radius=3.0, select_control_point=True)
    obj.data.splines.append(types.SimpleNamespace(type='BEZIER', bezier_points=[bezier]))
    pairs = props.ensure_point_slots(obj)
    assert [s for _, s in pairs] == [0, 1]
    assert props._selected(bezier)
    assert [p.radius for p, _ in pairs] == [2.5, 3.0]
    obj.data.splines.reverse()
    assert [s for _, s in props.ensure_point_slots(obj)] == [1, 0]


def test_extrude_duplicate_and_subdivision_do_not_copy_flags():
    obj = Obj(2)
    points = obj.data.splines[0].points
    props.ensure_point_slots(obj)
    obj['pn_0_flags'] = 2
    points.insert(0, point(-10, weight=points[0].weight_softbody, selected=True))
    pairs = props.ensure_point_slots(obj)
    assert [s for _, s in pairs] == [2, 0, 1]
    assert obj['pn_0_flags'] == 2 and obj['pn_2_flags'] == 0
    average = (points[1].weight_softbody + points[2].weight_softbody) / 2
    points.insert(2, point(5, weight=average))
    pairs = props.ensure_point_slots(obj)
    assert [s for _, s in pairs] == [2, 0, 3, 1]
    assert obj['pn_3_flags'] == 0


def test_goal_weight_edit_recovers_property_and_reports_warning():
    obj = Obj(2)
    props.ensure_point_slots(obj)
    obj['pn_1_flags'] = 2
    obj.data.splines[0].points[1].weight_softbody = 1.0
    assert [s for _, s in props.ensure_point_slots(obj)] == [0, 1]
    assert obj['pn_1_flags'] == 2
    assert obj['pn_identity_warning'] == 'WEIGHT_EDIT'


def test_identity_channel_float32_range_and_uniqueness():
    tags = [props._tag(n) for n in range(10000)]
    assert len(set(tags)) == len(tags)
    for slot in (0, 1, 10000, (1 << 20) - 1):
        value = props._tag(slot)
        assert 64 <= value < 96
        value32 = struct.unpack('<f', struct.pack('<f', value))[0]
        assert value32 == value
        assert props._slot(types.SimpleNamespace(weight_softbody=value32)) == slot


def test_saved_properties_keep_point_identity_after_reloading():
    import json
    obj = Obj(3)
    pairs = props.ensure_point_slots(obj)
    obj['pn_1_flags'] = 2
    saved_values = json.loads(json.dumps(dict(obj)))
    saved_weights = [p.weight_softbody for p, _ in pairs]
    restored = Obj(3)
    restored.clear()
    restored.update(saved_values)
    for p, weight in zip(restored.data.splines[0].points, saved_weights):
        p.weight_softbody = struct.unpack('<f', struct.pack('<f', weight))[0]
    restored.data.splines[0].points.pop(0)
    assert [s for _, s in props.ensure_point_slots(restored)] == [1, 2]
    assert restored['pn_1_flags'] == 2


def test_softbody_modifier_rejected_and_unrelated_curve_untouched():
    obj = Obj(2)
    obj.modifiers = [types.SimpleNamespace(type='SOFT_BODY')]
    with pytest.raises(ValueError, match='Softbody'):
        props.ensure_point_slots(obj)
    assert obj['pn_identity_warning'] == 'SOFT_BODY'
    unrelated = Obj(2)
    unrelated['path_type'] = 'track'
    before = dict(unrelated)
    assert props.ensure_point_slots(unrelated) == []
    assert dict(unrelated) == before


def _load_method(file, class_name, method, **ns):
    path = ROOT / 'INU_tools/ops' / file
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method)
    ns['__package__'] = 'path_lane.ops'
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), ns)
    return ns[method]


def _stub_relative_modules(monkeypatch):
    import core.paths
    monkeypatch.setitem(sys.modules, 'path_lane', types.ModuleType('path_lane'))
    monkeypatch.setitem(sys.modules, 'path_lane.ops', types.ModuleType('path_lane.ops'))
    monkeypatch.setitem(sys.modules, 'path_lane.core', types.ModuleType('path_lane.core'))
    monkeypatch.setitem(sys.modules, 'path_lane.core.paths', core.paths)
    import core.paths_graph
    monkeypatch.setitem(sys.modules, 'path_lane.core.paths_graph', core.paths_graph)
    mesh_spec = importlib.util.spec_from_file_location(
        'path_lane.ops.path_nodes_mesh', ROOT / 'INU_tools/ops/path_nodes_mesh.py')
    mesh_module = importlib.util.module_from_spec(mesh_spec)
    mesh_spec.loader.exec_module(mesh_module)
    monkeypatch.setitem(sys.modules, 'path_lane.ops.path_nodes_mesh', mesh_module)
    monkeypatch.setitem(sys.modules, 'path_lane.ops.path_ipl_props', props)


def test_selected_new_point_operator_creates_slot_and_real_bit(monkeypatch):
    _stub_relative_modules(monkeypatch)
    execute = _load_method('ifp_import.py', 'GTATOOLS_OT_path_node_flag', 'execute', T=lambda s: s)
    obj = Obj(2, pn_game='VC')
    props.ensure_point_slots(obj)
    obj.data.splines[0].points.insert(1, point(15, selected=True))
    reports = []
    operator = types.SimpleNamespace(action='TOGGLE_ROADBLOCK',
        report=lambda levels, text: reports.append((levels, text)))
    context = types.SimpleNamespace(active_object=obj,
        scene=types.SimpleNamespace(gtatools_game='VC'))
    assert execute(operator, context) == {'FINISHED'}
    assert obj['pn_2_flags'] == 2
    assert obj['pn_2_spawn'] == 1.0
    assert '1 point(s)' in reports[-1][1]
    operator.action = 'TRAFFIC_RAIL'
    before = dict(obj)
    assert execute(operator, context) == {'CANCELLED'}
    assert dict(obj) == before
    assert 'не хранится' in reports[-1][1]


def test_case_insensitive_node_groups_merge_bare_before_one_write(monkeypatch, tmp_path):
    _stub_relative_modules(monkeypatch)
    calls = []
    stub = types.ModuleType('path_lane.ops.path_export')
    def write_or_collect(**kw):
        if kw.get('collect_only'):
            return NodesFile(vehicle_nodes=[PathNode(node_id=0, area_id=37),
                                            PathNode(node_id=1, area_id=37)], parsed_extras=True)
        calls.append(kw)
        return 3
    stub.export_nodes = write_or_collect
    monkeypatch.setitem(sys.modules, 'path_lane.ops.path_export', stub)
    execute = _load_method('world_ops.py', 'GTATOOLS_OT_export_nodes', 'execute', os=os, T=lambda s: s)
    class Mesh(dict):
        type = 'MESH'
        matrix_world = Identity()
        def __init__(self, filename=''):
            super().__init__(path_type='nodes_vehicle', nodes_filename=filename)
            self.data = types.SimpleNamespace(vertices=[types.SimpleNamespace(co=Co(800, 0, 1))])
    objects = [Mesh('NODES37.dat'), Mesh('nodes37.DAT'), Mesh()]
    reports = []
    operator = types.SimpleNamespace(directory=str(tmp_path), fla4=False,
        report=lambda levels, text: reports.append((levels, text)))
    assert execute(operator, types.SimpleNamespace(selected_objects=objects)) == {'FINISHED'}
    assert len(calls) == 1
    assert pathlib.Path(calls[0]['filepath']).name == 'NODES37.dat'
    assert calls[0]['objects'] == objects[:2]
    assert len(calls[0]['prepared_nodes'].vehicle_nodes) == 3
    assert [n.node_id for n in calls[0]['prepared_nodes'].vehicle_nodes] == [0, 1, 2]
    assert any('WARNING' in levels and 'объединены' in text for levels, text in reports)


def test_legacy_column_migration_keeps_real_flags_spawn_and_authored_coordinates():
    obj = Obj(2)
    del obj['pn_semantics_version']
    obj.update(pn_0_area=1, pn_0_unk=4.5, pn_0_width=2,
               pn_0_ll=3, pn_0_rl=1, pn_0_mw=2, pn_0_flags=1,
               pn_0_spawn=99)
    props.ensure_point_slots(obj)
    assert props.slot_values(obj, 0) == dict(type=2, link=1, cross=1,
        width=4.5, ll=2, rl=3, speed=1, flags=2, spawn=1.0)
    assert not obj['pn_legacy_import_scale']
    assert obj.data.splines[0].points[1].co.x == 10


def test_old_import_export_keeps_original_file_scale(tmp_path):
    obj = Obj(12)
    del obj['pn_semantics_version']
    obj['pn_11_type'] = 0
    obj.data.splines[0].points.pop()
    dest = tmp_path / 'legacy.ipl'
    export(str(dest), [obj])
    assert obj['pn_legacy_import_scale']
    assert read_paths_ipl(str(dest)).groups[0].nodes[1].x == 10 / 16
    assert obj.data.splines[0].points[1].co.x == 10


def test_imported_graph_and_padding_roundtrip_without_chain_rebuild(tmp_path):
    rows = ['2, 2, 0, 2233.8, 19752, 161.083, 4, 2, 2, 0, 2, 1',
            '1, -1, 0, 2500, 19752, 161.083, 0, 1, 1, 0, 0, 0.5',
            '2, 0, 0, 2400, 19752, 161.083, 4, 2, 2, 0, 0, 1']
    rows += ['0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1'] * 9
    raw = '1, -1\r\n' + ''.join('\t' + row + '\r\n' for row in rows)
    obj = Obj(0, pn_game='VC', pn_original_group=raw,
              pn_source_prefix='# test\r\npath\r\n', pn_source_suffix='end\r\n')
    data = parse_paths_ipl(('path\n' + raw + 'end\n').encode())
    obj['pn_count'] = 12
    for slot, n in enumerate(data.groups[0].nodes):
        props.set_slot(obj, slot, dict(type=n.node_type, link=n.link_id,
            cross=n.crossing, width=n.width, ll=n.left_lanes, rl=n.right_lanes,
            speed=n.speed_limit, flags=n.flags, spawn=n.spawn_rate))
        if n.node_type:
            obj.data.splines[0].points.append(types.SimpleNamespace(
                co=Co(n.x, n.y, n.z), weight_softbody=0, select=False))
    pairs = props.ensure_point_slots(obj)
    obj['pn_import_slots'] = [s for _, s in pairs]
    obj['pn_import_positions'] = [v for p, _ in pairs for v in (p.co.x, p.co.y, p.co.z)]
    dest = tmp_path / 'graph.ipl'
    export(str(dest), [obj])
    assert dest.read_bytes() == ('# test\r\npath\r\n' + raw + 'end\r\n').encode()


def test_bare_merge_retains_imported_nodes_links_and_metadata(tmp_path):
    target = NodesFile(vehicle_nodes=[PathNode(node_id=0, area_id=37, flags=1)],
                       ped_nodes=[PathNode(node_id=1, area_id=37, is_vehicle=False)],
                       links=[PathLink(37, 1)],
                       navi_nodes=[NaviNode(area_id=37, node_id=1)], parsed_extras=True,
                       navi_links=[123], link_lengths=[5], path_intersections=[7] * 193)
    extra = split_nodes_by_area([('nodes_vehicle', 800, 0, 1)])
    assert 37 in extra
    remap = merge_bare_nodes(target, extra[37], allow_reindex=True)
    remap_node_references(target, remap, area_id=37)
    assert remap == {(37, 1): 2}
    assert [n.node_id for n in target.vehicle_nodes] == [0, 1]
    assert target.ped_nodes[0].node_id == 2
    assert target.links == [PathLink(37, 2)]
    assert target.navi_nodes[0].node_id == 2
    dest = tmp_path / 'NODES37.DAT'
    write_nodes(str(dest), target)
    result = read_nodes(str(dest))
    assert len(result.vehicle_nodes) == 2 and len(result.ped_nodes) == 1
    assert result.navi_links == [123] and result.link_lengths == [5]
    assert result.links[0].node_id == 2
    assert result.navi_nodes[0].node_id == 2


def test_vehicle_merge_rejects_partial_export_and_unknown_tail():
    target = NodesFile(vehicle_nodes=[PathNode(area_id=37, node_id=0)],
                       ped_nodes=[PathNode(area_id=37, node_id=1, is_vehicle=False)],
                       parsed_extras=True)
    extra = split_nodes_by_area([('nodes_vehicle', 800, 0, 1)])[37]
    with pytest.raises(ValueError, match='all 64'):
        merge_bare_nodes(target, extra)
    assert len(target.vehicle_nodes) == 1 and target.ped_nodes[0].node_id == 1
    target.extra_data = b'unknown tail'
    with pytest.raises(ValueError, match='unparsed'):
        merge_bare_nodes(target, extra, allow_reindex=True)
    assert len(target.vehicle_nodes) == 1 and target.ped_nodes[0].node_id == 1


def test_ped_only_merge_appends_without_shifting_original_references():
    target = NodesFile(vehicle_nodes=[PathNode(area_id=37, node_id=0)],
                       ped_nodes=[PathNode(area_id=37, node_id=1, is_vehicle=False)],
                       links=[PathLink(37, 1)], extra_data=b'keep raw tail')
    extra = split_nodes_by_area([('nodes_ped', 800, 0, 1)])[37]
    assert merge_bare_nodes(target, extra) == {}
    assert [n.node_id for n in target.ped_nodes] == [1, 2]
    assert target.links == [PathLink(37, 1)] and target.extra_data == b'keep raw tail'


def test_full_regions_vehicle_merge_updates_neighbour_links(monkeypatch, tmp_path):
    _stub_relative_modules(monkeypatch)
    stub = types.ModuleType('path_lane.ops.path_export')
    written = {}
    def write_or_collect(**kw):
        if kw.get('collect_only'):
            area = kw['objects'][0]['area']
            if area == 37:
                return NodesFile(vehicle_nodes=[PathNode(area_id=37, node_id=0)],
                    ped_nodes=[PathNode(area_id=37, node_id=1, is_vehicle=False, flags=1)],
                    links=[PathLink(37, 1)], navi_links=[0], link_lengths=[1],
                    path_intersections=[0]*193, parsed_extras=True)
            if area == 38:
                return NodesFile(ped_nodes=[PathNode(area_id=38, node_id=0, is_vehicle=False, flags=1)],
                    links=[PathLink(37, 1)], navi_links=[0], link_lengths=[1],
                    path_intersections=[0]*193, parsed_extras=True)
            return NodesFile(parsed_extras=True)
        written[pathlib.Path(kw['filepath']).name.casefold()] = kw['prepared_nodes']
        return len(kw['prepared_nodes'].vehicle_nodes) + len(kw['prepared_nodes'].ped_nodes)
    stub.export_nodes = write_or_collect
    monkeypatch.setitem(sys.modules, 'path_lane.ops.path_export', stub)
    execute = _load_method('world_ops.py', 'GTATOOLS_OT_export_nodes', 'execute', os=os, T=lambda s: s)
    class Mesh(dict):
        type = 'MESH'
        matrix_world = Identity()
        def __init__(self, area=None):
            super().__init__(path_type='nodes_vehicle', area=area,
                             nodes_filename=f'NODES{area}.dat' if area is not None else '')
            self.data = types.SimpleNamespace(vertices=[types.SimpleNamespace(co=Co(800, 0, 1))])
    reports = []
    operator = types.SimpleNamespace(directory=str(tmp_path), fla4=False,
        report=lambda levels, text: reports.append((levels, text)))
    objects = [Mesh(area) for area in range(64)] + [Mesh()]
    assert execute(operator, types.SimpleNamespace(selected_objects=objects)) == {'FINISHED'}
    assert len(written) == 64
    region = written['nodes37.dat']
    assert [n.node_id for n in region.vehicle_nodes] == [0, 1]
    assert region.ped_nodes[0].node_id == 2
    assert region.links[0].node_id == 2
    assert written['nodes38.dat'].links[0].node_id == 2
    # With only region 37 selected, skip that output entirely rather than
    # overwriting it with bare nodes or emitting a broken pedestrian graph.
    written.clear()
    assert execute(operator, types.SimpleNamespace(selected_objects=[Mesh(37), Mesh()])) == {'CANCELLED'}
    assert written == {}
    assert any('64 района' in text for _, text in reports)


def test_full_batch_later_merge_failure_cancels_before_any_writes(monkeypatch, tmp_path):
    _stub_relative_modules(monkeypatch)
    stub = types.ModuleType('path_lane.ops.path_export')
    writes = []
    def write_or_collect(**kw):
        if kw.get('collect_only'):
            area = kw['objects'][0]['area']
            if area in (37, 38):
                # 37 merges successfully first. 38 has invalid imported
                # identity and references the original ped37 physical ID.
                return NodesFile(vehicle_nodes=[PathNode(area_id=area, node_id=0, flags=1)],
                    ped_nodes=[PathNode(area_id=area, node_id=1 if area == 37 else 99,
                                        is_vehicle=False)],
                    links=[PathLink(37, 1)], parsed_extras=True)
            return NodesFile(parsed_extras=True)
        writes.append(kw)
        return 1
    stub.export_nodes = write_or_collect
    monkeypatch.setitem(sys.modules, 'path_lane.ops.path_export', stub)
    execute = _load_method('world_ops.py', 'GTATOOLS_OT_export_nodes', 'execute', os=os, T=lambda s: s)
    class Mesh(dict):
        type = 'MESH'
        matrix_world = Identity()
        def __init__(self, area, bare=False):
            super().__init__(path_type='nodes_vehicle', area=area,
                             nodes_filename='' if bare else f'NODES{area}.dat')
            x = 800 if area == 37 else 1600
            self.data = types.SimpleNamespace(vertices=[types.SimpleNamespace(co=Co(x, 0, 1))])
    objects = [Mesh(area) for area in range(64)] + [Mesh(37, True), Mesh(38, True)]
    reports = []
    operator = types.SimpleNamespace(directory=str(tmp_path), fla4=False,
        report=lambda levels, text: reports.append((levels, text)))
    assert execute(operator, types.SimpleNamespace(selected_objects=objects)) == {'CANCELLED'}
    assert writes == []
    assert any('файлы не записаны' in text for _, text in reports)


@pytest.mark.parametrize('game,path', [
    ('VC', pathlib.Path('D:/Grand Theft Auto Vice City/data/maps/paths.ipl')),
    ('III', pathlib.Path('D:/Grand Theft Auto III/data/maps/paths.ipl'))])
def test_vanilla_byte_roundtrip(tmp_path, game, path):
    if not path.is_file():
        pytest.skip('No vanilla paths.ipl for this install (III loads IDE paths)')
    data = read_paths_ipl(str(path), game=game)
    assert data.groups and any(n.node_type for g in data.groups for n in g.nodes)
    dest = tmp_path / 'roundtrip.ipl'
    write_paths_ipl(str(dest), data)
    assert dest.read_bytes() == path.read_bytes()


def test_vanilla_vc_blender_adapter_roundtrip_float32_points(tmp_path):
    source = pathlib.Path('D:/Grand Theft Auto Vice City/data/maps/paths.ipl')
    if not source.is_file():
        pytest.skip('Vanilla VC install absent')
    data = read_paths_ipl(str(source))
    objects = []
    for index, group in enumerate(data.groups):
        raw = group._raw_header + ''.join(n._raw for n in group.nodes)
        obj = Obj(0, pn_game='VC', pn_original_group=raw,
                  pn_source_prefix=data._prefix, pn_source_suffix=data._suffix,
                  group_index=index, external_index=group.external_index)
        obj['group_type'] = group.group_type
        obj['pn_count'] = len(group.nodes)
        for slot, n in enumerate(group.nodes):
            props.set_slot(obj, slot, dict(type=n.node_type, link=n.link_id,
                cross=n.crossing, width=n.width, ll=n.left_lanes, rl=n.right_lanes,
                speed=n.speed_limit, flags=n.flags, spawn=n.spawn_rate))
            obj[f'pn_{slot}_extra'] = ', '.join(n.extra_columns)
            if n.node_type:
                floats = [struct.unpack('<f', struct.pack('<f', v))[0] for v in (n.x, n.y, n.z)]
                obj.data.splines[0].points.append(types.SimpleNamespace(
                    co=Co(*floats), weight_softbody=0, select=False))
        pairs = props.ensure_point_slots(obj)
        obj['pn_import_slots'] = [s for _, s in pairs]
        obj['pn_import_positions'] = [v for p, _ in pairs for v in (p.co.x, p.co.y, p.co.z)]
        objects.append(obj)
    dest = tmp_path / 'adapter_roundtrip.ipl'
    export(str(dest), objects)
    assert dest.read_bytes() == source.read_bytes()


def test_vanilla_iii_ide_path_roundtrip(tmp_path):
    root = pathlib.Path('D:/Grand Theft Auto III/data/maps')
    if not root.is_dir():
        pytest.skip('Vanilla III install absent')
    paths = list(root.rglob('*.IDE')) + list(root.rglob('*.ide'))
    found = False
    for path in dict.fromkeys(paths):
        data = read_paths_ipl(str(path), game='III')
        if data.groups:
            assert any(n.node_type for g in data.groups for n in g.nodes)
            dest = tmp_path / 'iii.ide'
            write_paths_ipl(str(dest), data)
            assert dest.read_bytes() == path.read_bytes()
            found = True
    assert found, 'III vanilla contains model path sections in IDE files'
