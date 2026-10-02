"""User-answer regressions: real IPL/IMG IO, Blender replaced by small stand-ins."""

import ast
import copy
import io
import math
import os
import sys
import tempfile
import types
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'INU_tools'))
_pkg = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
_pkg.__path__ = [str(ROOT / 'INU_tools')]
from core.ipl import IplInstance
from core.mapsync import Anchor, IplDoc
from core.img import create_img, ImgReader
from core.img_routing import lod_routes


def _funcs(path, names, ns=None):
    ns = dict(ns or {})
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == set(names)
    exec(compile(ast.Module(body=body, type_ignores=[]), path, 'exec'), ns)
    return ns


OFFSET = ('inst\r\n'
          '100, house, 0, 10.0, 20.00, 30, 0, 0, 0, 1, 1\r\n'
          '101, LODhouse, 0, 12.5, 21, 30, 0, 0, 0.6000, 0.8000, -1\r\n'
          'end\r\n')


def test_sa_lod_offset_untouched_is_byte_identical():
    doc = IplDoc.from_text(OFFSET)
    model = copy.copy(doc.rows[0].inst)
    requested = copy.copy(model)
    requested.model_id, requested.model_name = 101, 'LODhouse'
    ed = doc.editor()
    result = ed.place('house', model, anchor=Anchor.of(model), lod=requested)
    assert ed.commit().to_text() == OFFSET
    assert result.action == result.lod_action == 'unchanged'


@pytest.mark.parametrize('with_mesh', [False, True])
def test_sa_lod_keeps_offset_and_rotation_when_model_moves(with_mesh):
    doc = IplDoc.from_text(OFFSET)
    model = copy.copy(doc.rows[0].inst)
    model.pos_x += 40
    model.pos_z += 3
    requested = copy.copy(model) if with_mesh else None
    if requested:
        requested.model_id, requested.model_name = 101, 'LODhouse'
    ed = doc.editor()
    ed.place('house', model, anchor=Anchor.of(doc.rows[0].inst), lod=requested)
    lod = IplDoc.from_text(ed.commit().to_text()).rows[1].inst
    assert (lod.pos_x, lod.pos_y, lod.pos_z) == (52.5, 21, 33)
    assert (lod.rot_x, lod.rot_y, lod.rot_z, lod.rot_w) == (0, 0, .6, .8)


def test_sa_lod_relative_transform_survives_model_rotation():
    doc = IplDoc.from_text(OFFSET)
    model = copy.copy(doc.rows[0].inst)
    # IPL is the conjugate: this is a +90-degree scene rotation.
    model.rot_z, model.rot_w = -math.sqrt(.5), math.sqrt(.5)
    ed = doc.editor()
    ed.place('house', model, anchor=Anchor.of(doc.rows[0].inst))
    lod = IplDoc.from_text(ed.commit().to_text()).rows[1].inst
    assert (lod.pos_x, lod.pos_y, lod.pos_z) == pytest.approx((9, 22.5, 30))
    assert (lod.rot_z, lod.rot_w) == pytest.approx(
        ((.6 - .8) * math.sqrt(.5), (.8 + .6) * math.sqrt(.5)), abs=1e-6)


def test_new_sa_lod_still_uses_requested_transform():
    ed = IplDoc.new().editor()
    model = IplInstance(100, 'house', pos_x=7)
    lod = IplInstance(101, 'LODhouse', pos_x=7)
    ed.place('house', model, lod=lod)
    assert IplDoc.from_text(ed.commit().to_text()).rows[1].inst.pos_x == 7


@pytest.mark.parametrize('game', ['SA', 'III', 'VC'])
def test_scaled_object_warning_for_every_game(game):
    ns = _funcs('INU_tools/ops/map_link.py', {'_scale_note'}, {'T': lambda s: s})
    messages = []
    obj = types.SimpleNamespace(name='house', matrix_world=types.SimpleNamespace(
        to_scale=lambda: (2, 1, 1)))
    rep = types.SimpleNamespace(msg=lambda *args: messages.append(args))
    ns['_scale_note'](obj, game, rep)
    assert len(messages) == 1 and messages[0][0] == 'WARNING'
    assert 'игра не применяет масштаб из IPL' in messages[0][1]


@pytest.mark.parametrize('is_lod,lod_distance,expected', [
    (True, 900, 900), (True, 0, 140), (True, -1, 140), (False, 900, 140),
])
def test_lod_draw_distance_and_old_scene_fallback(is_lod, lod_distance, expected):
    obj = types.SimpleNamespace(inu=types.SimpleNamespace(
        draw_distance=140, lod_draw_distance=lod_distance))
    ns = _funcs('INU_tools/ops/map_link.py', {'ide_draw_distance'})
    assert ns['ide_draw_distance'](obj, is_lod) == expected


def test_lod_archive_strict_and_model_fallback(tmp_path):
    hd, lod = (str(tmp_path / n) for n in ('mod.img', 'gta3.img'))
    create_img(hd)
    create_img(lod)
    assert lod_routes({'a': lod, 'b': '', 'c': str(tmp_path / 'missing.img')},
                      {'a': hd, 'b': hd, 'c': hd}) == ({'a': lod, 'b': hd}, ['c'])


def _stub_module(monkeypatch, name, **members):
    mod = types.ModuleType(name)
    mod.__dict__.update(members)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


@pytest.fixture
def export_img(monkeypatch, tmp_path):
    """Run the actual operator method with real archives and fake mesh/TXD builders."""
    pkg = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
    pkg.__path__ = [str(ROOT / 'INU_tools')]
    monkeypatch.setattr(pkg, '_append_export_report', lambda *_: None, raising=False)
    hd_path, lod_path = (str(tmp_path / n) for n in ('mod.img', 'gta3.img'))
    create_img(hd_path)
    create_img(lod_path)
    sources = []

    class Obj:
        type = 'MESH'
        children = []

        def __init__(self, name, arch, txd):
            self.name, self.selected = name, name == 'house'
            self.inu = types.SimpleNamespace(img_target_file=arch, txd_name=txd)
            sources.append(self)

        def select_set(self, value):
            self.selected = value

    hd, lod = Obj('house', hd_path, 'hdtex'), Obj('LODhouse', lod_path, 'lodtex')
    plan = [types.SimpleNamespace(model_name='house', include=True, inc_lod=True,
                                 inc_col=False, lod_found=True, lod_name=lod.name,
                                 col_found=False, col_name='', txd_name='hdtex')]
    settings = types.SimpleNamespace(gtatools_img_path=hd_path,
                                     gtatools_export_img_target='SELF', gtatools_game='SA',
                                     gtatools_platform='PC')
    objects = {o.name: o for o in sources}

    class Context:
        @property
        def selected_objects(self):
            return [o for o in sources if o.selected]

    ctx = Context()
    ctx.scene = types.SimpleNamespace(inu_settings=settings, objects=sources)
    ctx.window_manager = types.SimpleNamespace(gtatools_txd_export_plan=plan,
        progress_begin=lambda *_: None, progress_update=lambda *_: None,
        progress_end=lambda: None)
    ctx.view_layer = types.SimpleNamespace(objects=types.SimpleNamespace(
        get=objects.get, active=hd))
    ctx.workspace = types.SimpleNamespace(status_text_set=lambda *_: None)

    def deselect(**_):
        for obj in sources:
            obj.selected = False

    bpy = types.SimpleNamespace(data=types.SimpleNamespace(objects=objects, filepath=''),
        path=types.SimpleNamespace(abspath=lambda p: p),
        ops=types.SimpleNamespace(object=types.SimpleNamespace(select_all=deselect)))
    groups = {'house': {'DFF': hd, 'LOD': lod, 'COL': None}}
    _stub_module(monkeypatch, 'INU_tools.tools.model_utils',
                 find_all_selected_model_groups=lambda: groups,
                 find_related_models=lambda _: groups['house'], get_model_type=lambda _: ('DFF', 'house'))
    _stub_module(monkeypatch, 'INU_tools.ops.map_link', lod_hd_names=lambda _: {},
                 lod_model_name=lambda *_a, **_k: 'LODhouse', lod_name_note=lambda *_: '',
                 new_lod_name=lambda *_: 'LODhouse')
    _stub_module(monkeypatch, 'INU_tools.ops.dff_export',
        build_dff_clump=lambda objs, **_: types.SimpleNamespace(
            geometries=[], to_bytes=lambda: ('DFF:' + objs[0].name).encode()),
        _uv_anim_dropped_names=lambda *_: [], _resolve_export_version=lambda *_: 0x1803ffff)
    _stub_module(monkeypatch, 'INU_tools.ops.col_export', build_col_model=lambda *_a, **_k: None,
        export_col_library=lambda *_a, **_k: None, audit_col=lambda *_a, **_k: ([], []),
        _resolve_col_version=lambda *_: 3)

    def txd(path, context, *_a, **_k):
        Path(path).write_bytes(('TXD:' + ','.join(o.name for o in context.selected_objects)).encode())
        return {'FINISHED'}, 'ok', None

    _stub_module(monkeypatch, 'INU_tools.tools.txd_export', export_txd=txd,
                 update_txd=txd, mobile_txd_warning=lambda *_: None)
    ns = {'__package__': 'INU_tools.ops', 'T': lambda s: s, 'bpy': bpy, 'os': os,
          'tempfile': tempfile, 'defaultdict': defaultdict, 'ThreadPoolExecutor': ThreadPoolExecutor,
          '_export_unwritten': set(), '_export_final': {}, '_copy_jobs': lambda *_: [],
          '_stamp_img_status': lambda *_: None, '_same_img': lambda a, b: a == b,
          '_refresh_img_entries': lambda *_: None}
    helpers = {'_export_routes', '_export_lod_routes', '_plan_txd_buckets', '_txd_writeback',
               '_img_report_path', '_col_prim_index', '_col_prims_of'}
    ns = _funcs('INU_tools/ops/img_ops.py', helpers, ns)
    tree = ast.parse((ROOT / 'INU_tools/ops/img_ops.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'GTATOOLS_OT_export_to_img')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'img_ops.py', 'exec'), ns)
    reports = []
    op = types.SimpleNamespace(shared_txd=False, target_img='', skip_txd=False, skip_dff=False,
                               empty_col=False, rebuild_after=False,
                               report=lambda level, text: reports.append((level, text)))
    return types.SimpleNamespace(run=lambda: ns['execute'](op, ctx), ns=ns, hd=hd, lod=lod,
                                  hd_path=hd_path, lod_path=lod_path, reports=reports, op=op,
                                  ctx=ctx, groups=groups, objects=objects)


def _entries(path):
    with ImgReader(path) as reader:
        return {e.name: reader.read(e.name).rstrip(b'\0') for e in reader.entries}


def test_img_lod_and_its_txd_reach_own_archive(export_img):
    ex = export_img
    assert ex.run() == {'FINISHED'}
    assert _entries(ex.hd_path) == {'house.dff': b'DFF:house', 'hdtex.txd': b'TXD:house'}
    assert _entries(ex.lod_path) == {'LODhouse.dff': b'DFF:LODhouse', 'lodtex.txd': b'TXD:LODhouse'}
    assert ex.ns['_export_unwritten'] == set()


def test_img_missing_lod_archive_never_falls_back(export_img, tmp_path):
    ex = export_img
    ex.lod.inu.img_target_file = str(tmp_path / 'missing.img')
    assert ex.run() == {'FINISHED'}
    assert set(_entries(ex.hd_path)) == {'house.dff', 'hdtex.txd'}
    assert _entries(ex.lod_path) == {}
    assert ex.ns['_export_unwritten'] == {'house'}
    assert any('LOD пропущен' in message for _, message in ex.reports)


def test_img_lod_without_archive_follows_model(export_img):
    ex = export_img
    ex.lod.inu.img_target_file = ''
    assert ex.run() == {'FINISHED'}
    assert set(_entries(ex.hd_path)) == {'house.dff', 'LODhouse.dff', 'hdtex.txd', 'lodtex.txd'}
    assert _entries(ex.lod_path) == {}


def test_img_shared_txd_is_complete_in_lod_archive(export_img):
    ex = export_img
    ex.lod.inu.txd_name = 'hdtex'
    assert ex.run() == {'FINISHED'}
    assert _entries(ex.lod_path)['hdtex.txd'] == b'TXD:house,LODhouse'
    assert _entries(ex.hd_path)['hdtex.txd'] == b'TXD:house,LODhouse'


def test_shared_lod_without_archive_follows_each_model_archive(export_img):
    ex = export_img
    ex.lod.inu.img_target_file = ''
    barn = type(ex.hd)('barn', ex.lod_path, 'barntex')
    barn.selected = True
    ex.objects[barn.name] = barn
    ex.groups['barn'] = {'DFF': barn, 'LOD': ex.lod, 'COL': None}
    ex.ctx.window_manager.gtatools_txd_export_plan.append(types.SimpleNamespace(
        model_name='barn', include=True, inc_lod=True, inc_col=False, lod_found=True,
        lod_name=ex.lod.name, col_found=False, col_name='', txd_name='barntex'))
    assert ex.run() == {'FINISHED'}
    for arch in (ex.hd_path, ex.lod_path):
        entries = _entries(arch)
        assert entries['LODhouse.dff'] == b'DFF:LODhouse'
        assert entries['lodtex.txd'] == b'TXD:LODhouse'
    assert ex.ns['_export_unwritten'] == set()


def test_failed_lod_txd_prevents_dependent_ide_ipl(export_img, monkeypatch):
    ex = export_img
    txd = sys.modules['INU_tools.tools.txd_export']
    original = txd.export_txd

    def fail_lod(path, ctx, *args, **kw):
        if ctx.selected_objects == [ex.lod]:
            return {'CANCELLED'}, 'texture build failed', None
        return original(path, ctx, *args, **kw)

    monkeypatch.setattr(txd, 'export_txd', fail_lod)
    assert ex.run() == {'FINISHED'}
    assert set(_entries(ex.lod_path)) == {'LODhouse.dff'}
    assert ex.ns['_export_unwritten'] == {'house'}


def test_busy_lod_archive_does_not_receive_lod_in_model_archive(export_img, monkeypatch):
    ex = export_img
    real_open = open

    def busy(path, mode='r', *args, **kw):
        if str(path) == ex.lod_path and mode == 'r+b':
            raise PermissionError('locked')
        return real_open(path, mode, *args, **kw)

    ex.ns['open'] = busy
    assert ex.run() == {'FINISHED'}
    assert set(_entries(ex.hd_path)) == {'house.dff', 'hdtex.txd'}
    assert _entries(ex.lod_path) == {}
    assert ex.ns['_export_unwritten'] == {'house'}


def test_nested_img_error_returns_cancelled_without_traceback(monkeypatch):
    _stub_module(monkeypatch, 'INU_tools.tools.model_utils',
                 find_all_selected_model_groups=lambda: {})
    _stub_module(monkeypatch, 'INU_tools.ops.img_ops',
                 _export_routes=lambda *_: ({'a.img': ['house']}, []),
                 fill_export_plan=lambda *_a, **_k: None)
    tree = ast.parse((ROOT / 'INU_tools/ops/inu_export.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GTATOOLS_OT_export_all')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')

    def fail(*_a, **_k):
        raise RuntimeError('Error: IMG archive has an invalid format')

    ns = {'__package__': 'INU_tools.ops', 'T': lambda s: s,
          'bpy': types.SimpleNamespace(ops=types.SimpleNamespace(gtatools=types.SimpleNamespace(
              export_to_img=fail)))}
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'inu_export.py', 'exec'), ns)
    reports = []
    op = types.SimpleNamespace(to_img=True, report=lambda *args: reports.append(args))
    ctx = types.SimpleNamespace(scene=types.SimpleNamespace(inu_settings=types.SimpleNamespace(
        gtatools_export_all_lod=True, gtatools_export_all_col=True,
        gtatools_export_all_dff=True, gtatools_export_all_txd=True)))
    assert ns['execute'](op, ctx) == {'CANCELLED'}
    assert reports == [({'ERROR'}, 'Error: IMG archive has an invalid format')]


@pytest.mark.parametrize('lod_distance,expected', [(700, 700), (0, 140)])
def test_export_ide_writes_the_lod_panel_distance(monkeypatch, tmp_path, lod_distance, expected):
    from core.ide import IdeFile, IdeObject, read_ide, write_ide
    _stub_module(monkeypatch, 'INU_tools.tools.model_utils', get_model_type=lambda _: ('LOD', 'house'))
    distance = _funcs('INU_tools/ops/map_link.py', {'ide_draw_distance'})['ide_draw_distance']
    _stub_module(monkeypatch, 'INU_tools.ops.map_link', ide_draw_distance=distance,
                 lod_hd_names=lambda _: {}, lod_model_name=lambda *_a, **_k: 'LODhouse')
    ns = _funcs('INU_tools/ops/ide_export.py', {'export_ide'}, {
        '__package__': 'INU_tools.ops', 'IdeFile': IdeFile, 'IdeObject': IdeObject,
        'write_ide': write_ide, '_scene_game': lambda: 'SA'})
    obj = types.SimpleNamespace(type='MESH', name='LODhouse', inu=types.SimpleNamespace(
        model_id=101, txd_name='lodtex', draw_distance=140, lod_draw_distance=lod_distance))
    path = str(tmp_path / 'test.ide')
    ns['export_ide'](path, [obj])
    assert read_ide(path).objects[0].draw_distance == expected


@pytest.mark.parametrize('lod_distance,expected', [(700, 700), (0, 140)])
def test_add_builder_keeps_old_scene_draw_distance(monkeypatch, lod_distance, expected):
    _stub_module(monkeypatch, 'INU_tools.tools.model_utils', get_model_type=lambda _: ('LOD', 'house'))
    ns = _funcs('INU_tools/__init__.py', {'_ide_entry_from_obj'}, {
        '__package__': 'INU_tools', '_clean_model_name_ide': lambda n: n})
    obj = types.SimpleNamespace(name='LODhouse', inu=types.SimpleNamespace(
        model_id=101, txd_name='lodtex', draw_distance=140, lod_draw_distance=lod_distance))
    assert ns['_ide_entry_from_obj'](obj).draw_distance == expected


def test_map_library_keeps_ide_names_and_model_groups(monkeypatch, tmp_path):
    from core.col import ColModel, Bounds, ColSphere, Vec3, read_col_file
    # The ordinary builder is already covered by COL tests. This regression
    # checks the map's dispatch: IDE name, saved bounds, and mixed-case
    # primitives must stay in a single record instead of being regrouped.
    mesh = types.SimpleNamespace(name='wrong_COL', saved_bounds=Bounds(
        center=Vec3(1, 2, 3), radius=10, bb_min=Vec3(-5, -5, -5), bb_max=Vec3(5, 5, 5)))
    sphere = types.SimpleNamespace(name='HOUSE_sphere_0')
    model = types.SimpleNamespace(name='house', cols=[mesh, sphere])
    seen = []

    def build(objects, version, model_name):
        seen.append((objects, model_name))
        out = ColModel(version=version, model_name=model_name)
        out.bounds = objects[0].saved_bounds
        out.spheres = [ColSphere(center=Vec3(2, 3, 4), radius=1)]
        return out

    _stub_module(monkeypatch, 'INU_tools.ops.col_export',
                 _resolve_col_version=lambda: 3, export_col=lambda *_a, **_k: None,
                 build_col_model=build, audit_col=lambda *_a, **_k: ([], ['legacy import warning']))
    path = str(tmp_path / 'library.col')
    prep = types.SimpleNamespace(error='', models={'house': model}, placements=[], pair=False,
                                  split=False, notes=[], game='SA', plan={path: ('col_lib', [model])})
    ns = _funcs('INU_tools/tools/map_export.py', {'iter_export_map'}, {
        '__package__': 'INU_tools.tools', 'Optional': Optional,
        'MapExportPrep': type(prep),
        'os': os, 'T': lambda s: s})
    # Python <=3.13 resolves annotations during definition. Resolve them
    # explicitly on 3.14 too so a missing dependency cannot pass unnoticed.
    assert ns['iter_export_map'].__annotations__['prepared'] == Optional[type(prep)]
    stats = {}
    list(ns['iter_export_map'](types.SimpleNamespace(mode='OBJECT'), str(tmp_path),
                               prepared=prep, stats=stats))
    rows = read_col_file(path)
    assert len(rows) == stats['col'] == 1
    assert rows[0].model_name == 'house' and len(rows[0].spheres) == 1
    assert rows[0].bounds.radius == 10
    assert seen == [([mesh, sphere], 'house')]
    assert ('WARNING', 'library.col: legacy import warning') in stats['notes']
