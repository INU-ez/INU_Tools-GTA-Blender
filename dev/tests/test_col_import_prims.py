"""Import Map builds a model's collision once: mesh plus spheres/boxes.

Spheres and boxes are collision of their own in the game (reVC
Collision.cpp ProcessSphereSphere / ProcessSphereBox / TestLineSphere), not
a broad phase — 1319 vanilla SA models have no triangles at all — yet the
bulk path of ops/col_import.py dropped them, so after Import Map such models
had no collision at all.

col_import.import_col_from_models(bulk_mode=True, with_prims=True): the
spheres/boxes become children of the COL mesh (else the shadow mesh, else a
mesh WITHOUT geometry «<model>_COL», tagged COL, carrying the source
bounds), location/scale in model space. Without with_prims the bulk path
makes none (as before); single-file import keeps them loose.

ops/map_ops.py Import Map: the collision is built at the model's first
placement only and moved as a whole (its parentless objects), later
placements get no copy — as in Max. Driven through the real invoke on a
mini game folder with bpy and the DFF build stubbed.

col_import imports bpy at module level, so its functions are pulled out by
AST and run against a small bpy stand-in."""

from pathlib import Path
import ast
import importlib
import io
import os
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / 'INU_tools' / 'ops'


# ── bpy stand-in ─────────────────────────────────────────────────────────

class _V:
    """mathutils.Vector as far as the code reads it."""

    def __init__(self, v):
        self.x, self.y, self.z = (float(c) for c in v)

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __eq__(self, other):
        return tuple(self) == pytest.approx(tuple(other), abs=1e-6)

    def __repr__(self):
        return 'V%r' % (tuple(self),)


class _Obj:
    def __init__(self, name, data=None):
        self.props = {}
        self.name = name
        self.data = data
        self.type = 'EMPTY' if data is None else 'MESH'
        self.parent = None
        self.location = (0.0, 0.0, 0.0)
        self.scale = (1.0, 1.0, 1.0)
        self.rotation_mode = 'XYZ'
        self.rotation_quaternion = None
        self.empty_display_type = 'PLAIN_AXES'
        self.empty_display_size = 1.0
        self.inu = types.SimpleNamespace(type='OBJ', model_id=0,
                                         lod_object=None)

    def __setattr__(self, key, value):
        if key in ('location', 'scale'):
            value = _V(value)
        object.__setattr__(self, key, value)

    def __setitem__(self, key, value):
        self.props[key] = value

    def __contains__(self, key):
        return key in self.props

    def get(self, key, default=None):
        return self.props.get(key, default)

    def copy(self):
        dup = _Obj(self.name + '.001', self.data)
        dup.inu = types.SimpleNamespace(**vars(self.inu))
        return dup

    def select_set(self, state):
        pass


class _Mesh:
    def __init__(self, name):
        self.name = name
        self.vertices = []
        self.faces = []
        self.materials = []
        self.polygons = types.SimpleNamespace(
            foreach_set=lambda attr, seq: None)

    def from_pydata(self, verts, edges, faces):
        self.vertices, self.faces = list(verts), list(faces)

    def update(self):
        pass


class _Bag(list):
    """Collection.objects / .children: link() and get(name)."""

    def link(self, item):
        self.append(item)

    def get(self, name, default=None):
        return next((i for i in self if i.name == name), default)


class _Coll:
    def __init__(self, name):
        self.name = name
        self.objects = _Bag()
        self.children = _Bag()
        self.hide_viewport = False


class _Registry(_Bag):
    """bpy.data.objects / meshes / materials / collections."""

    def __init__(self, make):
        super().__init__()
        self._make = make

    def new(self, name, *args):
        item = self._make(name, *args)
        self.append(item)
        return item


def _material(name):
    return types.SimpleNamespace(name=name, inu=types.SimpleNamespace())


def _bpy_data():
    return types.SimpleNamespace(
        filepath='', objects=_Registry(_Obj), meshes=_Registry(_Mesh),
        materials=_Registry(_material), collections=_Registry(_Coll))


# ── modules: map_ops & co against the stand-in, col_import cut by AST ────

def _is_ours(name):
    return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))


def _load():
    """Import the addon modules against our own bpy / INU_tools stubs and
    hand back those modules; sys.modules is restored for other tests."""
    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for key in saved:
        del sys.modules[key]
    try:
        bpy = types.ModuleType('bpy')
        base = type('Base', (), {})
        bpy.app = types.SimpleNamespace(
            version=(4, 2, 0),
            handlers=types.SimpleNamespace(persistent=lambda f: f))
        bpy.types = types.SimpleNamespace(**{
            n: type(n, (base,), {}) for n in (
                'Operator', 'Panel', 'PropertyGroup', 'Menu', 'UIList',
                'Object', 'Collection', 'Scene')})
        props = types.ModuleType('bpy.props')
        for n in ('StringProperty', 'BoolProperty', 'IntProperty',
                  'FloatProperty', 'EnumProperty', 'FloatVectorProperty',
                  'CollectionProperty', 'PointerProperty'):
            setattr(props, n, lambda **kw: None)
        bpy.props = props
        bpy.path = types.SimpleNamespace(abspath=lambda p: p)
        bpy.data = _bpy_data()
        sys.modules['bpy'] = bpy
        sys.modules['bpy.props'] = props
        pkg = types.ModuleType('INU_tools')
        pkg.__path__ = [str(ROOT / 'INU_tools')]
        pkg.T = lambda s: s
        sys.modules['INU_tools'] = pkg
        for name in ('ops.map_ops', 'ops.map_link', 'ops.ipl_sections',
                     'core.map_files', 'core.gta_dat', 'core.ide',
                     'core.ipl', 'core.img', 'core.col', 'tools.profiler'):
            importlib.import_module('INU_tools.' + name)
        return {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for key in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[key]
        sys.modules.update(saved)


def _cut(path, wanted, ns):
    """Exec the named functions of ``path`` — with the functions and module
    constants they use — into ``ns``."""
    tree = ast.parse(io.open(path, encoding='utf-8').read())
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    consts = {t.id for n in tree.body if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name)}
    need, used, todo = set(), set(), list(wanted)
    while todo:
        name = todo.pop()
        if name in need:
            continue
        need.add(name)
        for sub in ast.walk(defs[name]):
            if isinstance(sub, ast.Name):
                if sub.id in defs:
                    todo.append(sub.id)
                elif sub.id in consts:
                    used.add(sub.id)
    keep = [n for n in tree.body
            if (isinstance(n, ast.FunctionDef) and n.name in need)
            or (isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in used
                for t in n.targets))]
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(path), 'exec'),
         ns)
    return ns


MODS = _load()
BPY = MODS['bpy']
col = MODS['INU_tools.core.col']
map_ops = MODS['INU_tools.ops.map_ops']
map_link = MODS['INU_tools.ops.map_link']
core_img = MODS['INU_tools.core.img']

IMP = _cut(OPS / 'col_import.py', {'import_col_from_models'},
           {'bpy': BPY, 'ColModel': col.ColModel, 'T': lambda s: s, 'os': os})
import_col_from_models = IMP['import_col_from_models']

# The pre-existing collectors, anchor-free (raw location/scale — the space a
# child of the COL mesh keeps): what the file gets back for these empties.
EXP = _cut(OPS / 'col_export.py',
           {'_collect_empty', '_stored_bounds'},
           dict({k: getattr(col, k) for k in dir(col)
                 if not k.startswith('__')}, T=lambda s: s))


@pytest.fixture(autouse=True)
def fresh_data(monkeypatch):
    monkeypatch.setattr(BPY, 'data', _bpy_data())


def _surf(n):
    return col.Surface(material=n, flags=1, brightness=2, light=0x4E)


def _v(x, y, z):
    return col.Vec3(x, y, z)


def _bounds():
    return col.Bounds(center=_v(0.0, 0.0, 1.0), radius=2.5,
                      bb_min=_v(-1.0, -1.0, 0.0), bb_max=_v(1.0, 1.0, 2.0))


def _boxes_only(name='lampx'):
    return col.ColModel(
        version=3, model_name=name, bounds=_bounds(),
        boxes=[col.ColBox(_v(-1.0, -1.0, 0.0), _v(1.0, 1.0, 2.0), _surf(5)),
               col.ColBox(_v(0.5, 0.25, 0.5), _v(1.0, 1.0, 1.5), _surf(6))])


def _tri():
    return ([_v(0.0, 0.0, 0.0), _v(1.0, 0.0, 0.0), _v(0.0, 1.0, 0.0)],
            [col.ColFace(0, 1, 2, _surf(3))])


def _mesh_and_prims(name='rock'):
    verts, faces = _tri()
    return col.ColModel(
        version=3, model_name=name, bounds=_bounds(),
        vertices=verts, faces=faces,
        spheres=[col.ColSphere(_v(0.5, -0.5, 1.0), 0.75, _surf(7))],
        boxes=[col.ColBox(_v(-1.0, -1.0, 0.0), _v(0.0, 0.0, 1.0), _surf(8))])


def _empties(objs):
    return [o for o in objs if o.type == 'EMPTY']


BOUNDS10 = [2.5, 0.0, 0.0, 1.0, -1.0, -1.0, 0.0, 1.0, 1.0, 2.0]


# ── col_import ───────────────────────────────────────────────────────────

def test_boxes_only_model_gets_a_mesh_holder():
    coll = _Coll('one_COL')
    objs = import_col_from_models([_boxes_only()], bulk_mode=True,
                                  target_collection=coll, material_cache={},
                                  with_prims=True)
    holder = objs[0]
    assert holder.type == 'MESH' and holder.name == 'lampx_COL'
    assert holder.inu.type == 'COL'
    assert holder.data.vertices == [] and holder.data.faces == []
    assert list(holder.get('inu_col_bounds')) == BOUNDS10
    boxes = _empties(objs)
    assert [b.name for b in boxes] == ['lampx_box_0', 'lampx_box_1']
    for b in boxes:
        assert b.parent is holder and b.empty_display_type == 'CUBE'
    # location = centre, scale = half sizes — in the model's space
    assert boxes[0].location == (0.0, 0.0, 1.0)
    assert boxes[0].scale == (1.0, 1.0, 1.0)
    assert boxes[1].location == (0.75, 0.625, 1.0)
    assert boxes[1].scale == (0.25, 0.375, 0.5)
    assert boxes[1].inu.col_material == 6
    assert list(coll.objects) == objs


def test_spheres_and_boxes_are_children_of_the_col_mesh():
    objs = import_col_from_models([_mesh_and_prims()], bulk_mode=True,
                                  target_collection=_Coll('c'),
                                  material_cache={}, with_prims=True)
    mesh = objs[0]
    assert mesh.name == 'rock_COL' and len(mesh.data.vertices) == 3
    assert [o.name for o in objs[1:]] == ['rock_sphere_0', 'rock_box_0']
    assert all(o.parent is mesh for o in objs[1:])
    assert len(BPY.data.meshes) == 1      # no holder next to a real mesh
    sphere = objs[1]
    assert sphere.empty_display_type == 'SPHERE'
    assert sphere.location == (0.5, -0.5, 1.0)
    assert sphere.empty_display_size == 0.75
    assert list(mesh.get('inu_col_bounds')) == BOUNDS10


def test_shadow_only_model_hangs_them_on_the_shadow_mesh():
    verts, faces = _tri()
    m = col.ColModel(version=3, model_name='fence', bounds=_bounds(),
                     shadow_vertices=verts, shadow_faces=faces,
                     spheres=[col.ColSphere(_v(0.0, 0.0, 0.0), 1.0,
                                            _surf(1))])
    objs = import_col_from_models([m], bulk_mode=True,
                                  target_collection=_Coll('c'),
                                  material_cache={}, with_prims=True)
    sha = objs[0]
    assert sha.name == 'fence_sha' and objs[1].parent is sha
    assert len(objs) == 2
    assert list(sha.get('inu_col_bounds')) == BOUNDS10


def test_bulk_without_with_prims_makes_no_primitives():
    # ariane_bridge / embedded DFF collision keep the old bulk behaviour.
    objs = import_col_from_models([_boxes_only(), _mesh_and_prims()],
                                  bulk_mode=True,
                                  target_collection=_Coll('c'),
                                  material_cache={})
    assert [o.name for o in objs] == ['rock_COL']
    assert not _empties(BPY.data.objects)


def test_single_file_import_keeps_them_loose(monkeypatch):
    scene_coll = _Coll('Scene')
    monkeypatch.setattr(BPY, 'context', types.SimpleNamespace(
        collection=scene_coll,
        view_layer=types.SimpleNamespace(
            objects=types.SimpleNamespace(active=None),
            update=lambda: None)), raising=False)
    monkeypatch.setattr(BPY, 'ops', types.SimpleNamespace(
        object=types.SimpleNamespace(select_all=lambda **kw: None)),
        raising=False)
    objs = import_col_from_models([_boxes_only()], material_cache={},
                                  skip_position_match=True)
    assert [o.name for o in objs] == ['lampx_box_0', 'lampx_box_1']
    assert all(o.parent is None for o in objs)
    assert not BPY.data.meshes


def test_round_trip_gives_back_the_source_primitives():
    src = _mesh_and_prims()
    src.boxes.append(col.ColBox(_v(2.0, 3.0, -1.0), _v(4.0, 3.5, 0.5),
                                _surf(9)))
    objs = import_col_from_models([src, _boxes_only()], bulk_mode=True,
                                  target_collection=_Coll('c'),
                                  material_cache={}, with_prims=True)
    for model_name, want in (('rock', src), ('lampx', _boxes_only())):
        anchor = next(o for o in objs if o.name == model_name + '_COL')
        kids = [o for o in objs if o.parent is anchor]
        got = col.ColModel(version=3, model_name=model_name)
        for o in kids:
            EXP['_collect_empty'](o, got)
        assert len(got.spheres) == len(want.spheres)
        assert len(got.boxes) == len(want.boxes)
        for a, b in zip(got.spheres, want.spheres):
            assert (a.center.x, a.center.y, a.center.z, a.radius) == \
                pytest.approx((b.center.x, b.center.y, b.center.z,
                               b.radius), abs=1e-6)
            assert a.surface.material == b.surface.material
        for a, b in zip(got.boxes, want.boxes):
            assert (a.bb_min.x, a.bb_min.y, a.bb_min.z,
                    a.bb_max.x, a.bb_max.y, a.bb_max.z) == pytest.approx(
                (b.bb_min.x, b.bb_min.y, b.bb_min.z,
                 b.bb_max.x, b.bb_max.y, b.bb_max.z), abs=1e-6)
            assert a.surface.material == b.surface.material
        bounds = EXP['_stored_bounds']([anchor] + kids)
        assert (bounds.radius, bounds.center.z, bounds.bb_max.z) == \
            (2.5, 1.0, 2.0)


# ── Import Map: once per model, at its first placement ───────────────────

class _Quat(tuple):
    def __new__(cls, wxyz):
        return tuple.__new__(cls, (float(c) for c in wxyz))

    def conjugated(self):
        w, x, y, z = self
        return _Quat((w, -x, -y, -z))


def _fake_dff_import(clump, model_name, target_collection=None, **kw):
    obj = BPY.data.objects.new(model_name + '_DFF',
                               BPY.data.meshes.new(model_name))
    target_collection.objects.link(obj)
    return [obj]


@pytest.fixture
def game(tmp_path, monkeypatch):
    for key, mod in MODS.items():
        monkeypatch.setitem(sys.modules, key, mod)
    monkeypatch.setitem(sys.modules, 'mathutils',
                        types.SimpleNamespace(Quaternion=_Quat))
    monkeypatch.setitem(sys.modules, 'INU_tools.core.dff',
                        types.SimpleNamespace(read_dff=lambda data: data))
    monkeypatch.setitem(sys.modules, 'INU_tools.ops.dff_import',
                        types.SimpleNamespace(
                            import_dff_from_clump=_fake_dff_import))
    monkeypatch.setitem(sys.modules, 'INU_tools.ops.col_import',
                        types.SimpleNamespace(
                            import_col_from_models=import_col_from_models))
    for fn in ('stamp_map_import', 'stamp_ipl', 'clear_ipl'):
        monkeypatch.setattr(map_link, fn, lambda *a, **k: None)
    cache = tmp_path / 'blend' / '.inu_cache'
    cache.mkdir(parents=True)
    monkeypatch.setattr(MODS['INU_tools'], '_get_cache_dir',
                        lambda: str(cache), raising=False)

    root = tmp_path / 'game'
    (root / 'data' / 'maps').mkdir(parents=True)
    (root / 'models').mkdir()
    (root / 'data' / 'gta.dat').write_text(
        'IDE DATA\\MAPS\\one.ide\n'
        'IPL DATA\\MAPS\\one.ipl\nIPL DATA\\MAPS\\two.ipl\n')
    (root / 'data' / 'maps' / 'one.ide').write_text(
        'objs\n100, rock, txda, 150, 0\n101, lampx, txda, 99, 0\n'
        '102, bush, txda, 99, 0\nend\n')
    # rock: twice in one.ipl (first one turned 90° about Z), once in two.ipl
    (root / 'data' / 'maps' / 'one.ipl').write_text(
        'inst\n'
        '100, rock, 0, 10, 20, 30, 0, 0, 0.7071068, 0.7071068, -1\n'
        '100, rock, 0, 50, 60, 70, 0, 0, 0, 1, -1\n'
        '101, lampx, 0, 1, 2, 3, 0, 0, 0, 1, -1\n'
        'end\n')
    (root / 'data' / 'maps' / 'two.ipl').write_text(
        'inst\n'
        '100, rock, 0, 90, 90, 9, 0, 0, 0, 1, -1\n'
        '102, bush, 0, 5, 5, 5, 0, 0, 0, 1, -1\n'
        'end\n')
    gta3 = str(root / 'models' / 'gta3.img')
    core_img.create_img(gta3)
    with core_img.ImgWriter(gta3) as w:
        for n in ('rock', 'lampx', 'bush'):
            w.add(n + '.dff', b'D' * 64)
    for n in ('rock', 'lampx', 'bush'):
        (cache / (n + '.dff')).write_bytes(b'D' * 64)
    # bush has no collision
    (cache / 'mapcol.col').write_bytes(
        col.write_col([_mesh_and_prims(), _boxes_only()]))
    return types.SimpleNamespace(root=str(root), cache=str(cache))


def _import_map(g):
    settings = types.SimpleNamespace(
        gtatools_game_root=g.root, gtatools_img_path='',
        gtatools_map_region='ALL', gtatools_img_skip_lod=False,
        gtatools_map_skip_2dfx=False, gtatools_map_skip_dupes=False,
        gtatools_map_group_by_ipl=True, gtatools_profile_enabled=False,
        gtatools_text_ipls=[], gtatools_binary_ipls=[],
        gtatools_map_load_col=True, gtatools_img_load_txd=False)
    wm = types.SimpleNamespace(
        progress_begin=lambda a, b: None, modal_handler_add=lambda op: None,
        event_timer_add=lambda *a, **k: object())
    scene = types.SimpleNamespace(inu_settings=settings,
                                  collection=_Coll('Scene'),
                                  get=lambda k, d=None: d)
    ctx = types.SimpleNamespace(
        scene=scene, window=None, window_manager=wm,
        workspace=types.SimpleNamespace(status_text_set=lambda t: None))
    op = map_ops.GTATOOLS_OT_import_map()
    op.report = lambda kind, msg: None
    assert op.invoke(ctx, None) == {'RUNNING_MODAL'}
    for _ in op._gen:
        pass
    return op


def test_import_map_builds_the_collision_once_at_the_first_placement(game):
    op = _import_map(game)
    assert op._imported == 5
    colls = {c.name: c for c in BPY.data.collections}
    # rock's third placement (two.ipl) gets no copy; bush has no COL
    assert 'two_COL' not in colls
    objs = colls['one_COL'].objects
    assert sorted(o.name for o in objs) == [
        'lampx_COL', 'lampx_box_0', 'lampx_box_1',
        'rock_COL', 'rock_box_0', 'rock_sphere_0']
    assert sum(len(c.objects) for c in BPY.data.collections
               if c.name.endswith('_COL')) == 6

    rock, lamp = objs.get('rock_COL'), objs.get('lampx_COL')
    assert rock.location == (10.0, 20.0, 30.0)
    assert rock.rotation_mode == 'QUATERNION'
    assert tuple(rock.rotation_quaternion) == pytest.approx(
        (0.7071068, 0.0, 0.0, -0.7071068))
    assert lamp.location == (1.0, 2.0, 3.0)
    assert lamp.data.vertices == []
    assert list(lamp.get('inu_col_bounds')) == BOUNDS10
    # the primitives ride on their mesh: model-space values, no own placement
    for o in objs:
        if o.type == 'EMPTY':
            assert o.parent is (rock if o.name.startswith('rock') else lamp)
            assert o.rotation_quaternion is None
    assert objs.get('rock_sphere_0').location == (0.5, -0.5, 1.0)
    assert objs.get('lampx_box_1').location == (0.75, 0.625, 1.0)


# ── Import tab (img_ops): the same collision as Import Map ───────────────

def test_import_tab_builds_prims_through_the_core():
    # The tab made its own spheres/boxes and, for a model without a mesh,
    # put each one in the world (matrix_basis = placement @ basis) — COL
    # export then wrote world coordinates into the model's record. Now the
    # core builds them (a mesh holder for a spheres/boxes-only model) as
    # children of the COL mesh, which alone is placed.
    tree = ast.parse(io.open(OPS / 'img_ops.py', encoding='utf-8').read())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'GTATOOLS_OT_import_from_img')
    work = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == '_work')
    names = {getattr(n.func, 'id', getattr(n.func, 'attr', ''))
             for n in ast.walk(work) if isinstance(n, ast.Call)}
    assert '_create_sphere' not in names and '_create_box' not in names
    calls = [n for n in ast.walk(work) if isinstance(n, ast.Call)
             and getattr(n.func, 'id', '') == 'import_col_from_models']
    assert calls
    for c in calls:
        kw = {k.arg: k.value for k in c.keywords}
        assert ast.literal_eval(kw['bulk_mode']) is True
        assert ast.literal_eval(kw['with_prims']) is True
    assert not [n for n in ast.walk(work) if isinstance(n, ast.Attribute)
                and n.attr == 'matrix_basis']
