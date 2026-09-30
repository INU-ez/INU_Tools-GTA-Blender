# Import IPL and «Replace Empty» found ONE object per model name and moved it
# onto every row of that model — with N rows only the last placement stayed,
# the other N−1 vanished without a placeholder or a message. Now the first
# row moves the object, every further row gets its own copy (shared mesh);
# on re-import an object already standing on a row (or linked to it) is
# reused instead of stacking another copy there. _row_target is that choice.
#
# Around it: a LOD row with no LOD mesh (only its model found) adds nothing
# when the model is placed by its own row or already stands there; another
# IPL's placements are never pulled off their rows; each copy pairs with the
# LOD placed by its own row (inu.lod_object).
#
# ops/ipl_import.py and ops/ide_ipl.py import bpy at module level, so pull
# the functions out by AST and run them against a small fake bpy.

import ast
import io
import os
import re
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IPL_IMPORT = os.path.join(ROOT, "INU_tools", "ops", "ipl_import.py")
IDE_IPL = os.path.join(ROOT, "INU_tools", "ops", "ide_ipl.py")
MAP_LINK = os.path.join(ROOT, "INU_tools", "ops", "map_link.py")

_pkg_root = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
if not hasattr(_pkg_root, '__path__'):
    _pkg_root.__path__ = [os.path.join(ROOT, "INU_tools")]
if not hasattr(_pkg_root, 'T'):
    _pkg_root.T = lambda s, *_a, **_kw: s

from INU_tools.core.ipl import read_ipl                    # noqa: E402
from INU_tools.core.model_classify import classify_model   # noqa: E402


def _extract(path, wanted, ns):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in keep} == set(wanted), path
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), ns)


NS = {}
_extract(IPL_IMPORT, {"_row_target"}, NS)
row_target = NS["_row_target"]


def _plan(found_per_row):
    used = set()
    return [row_target(f, (), used) for f in found_per_row]


def test_first_row_moves_repeats_copy():
    # None = place a copy of the found object on that row
    assert _plan(["a", "b", "a", "a", "b"]) == ["a", "b", None, None, None]


def test_single_rows_unchanged():
    assert _plan(["a", "b", "c"]) == ["a", "b", "c"]


def test_standing_object_is_reused():
    used = set()
    # re-import: the found object and its earlier copy already stand on rows
    assert row_target("a", ["a"], used) == "a"
    assert row_target("a", ["a.001"], used) == "a.001"
    assert row_target("a", [], used) is None


def test_standing_taken_falls_back():
    used = set()
    # two rows of one model on the same spot: one reuse, then a copy
    assert row_target("a", ["a"], used) == "a"
    assert row_target("a", ["a"], used) is None


def test_found_elsewhere_still_moves():
    used = set()
    # row 1 is taken by a copy standing there; the found object is free
    assert row_target("a", ["a.001"], used) == "a.001"
    assert row_target("a", [], used) == "a"
    assert row_target("a", [], used) is None


def _func_src(path, cls, name):
    src = io.open(path, encoding="utf-8").read()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ClassDef) and cls and node.name == cls:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    return ast.get_source_segment(src, f), f
        if not cls and isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node), node
    raise AssertionError(name)


def test_both_callers_use_it():
    imp = _func_src(IPL_IMPORT, None, "import_ipl")[0]
    assert "_row_target(obj, standing, used)" in imp
    assert "_linked_copy(obj)" in imp
    assert "fresh=fresh" in imp
    rep = _func_src(IDE_IPL, "GTATOOLS_OT_replace_ipl_placeholders", "execute")[0]
    assert "_row_target(mesh_obj, (), used)" in rep
    assert "_linked_copy(mesh_obj)" in rep


def test_copy_drops_ipl_link():
    cp = _func_src(IPL_IMPORT, None, "_linked_copy")[0]
    assert "clear_ipl(dup)" in cp
    assert "users_collection" in cp


# ── fake bpy: just what import_ipl / Replace Empty touch ─────────────────

class _Vec:
    def __init__(self, t=(0.0, 0.0, 0.0)):
        self.v = tuple(float(x) for x in t)

    def __sub__(self, o):
        return _Vec(a - b for a, b in zip(self.v, o.v))

    @property
    def length(self):
        return sum(a * a for a in self.v) ** 0.5

    def copy(self):
        return _Vec(self.v)


class _Quat:
    def __init__(self, t=(1.0, 0.0, 0.0, 0.0)):
        self.v = tuple(t)

    def conjugated(self):
        w, x, y, z = self.v
        return _Quat((w, -x, -y, -z))

    def copy(self):
        return _Quat(self.v)


class _Coll:
    def __init__(self, name):
        self.name = name
        self.objects = _CollObjects(self)
        self.children = types.SimpleNamespace(link=lambda c: None)


class _CollObjects(list):
    def __init__(self, coll):
        super().__init__()
        self.coll = coll

    def link(self, o):
        assert o not in self
        self.append(o)
        o.users_collection.append(self.coll)


class _Obj:
    def __init__(self, objs, name, data, type_):
        self._objs, self.type, self.data = objs, type_, data
        self.location, self.rotation_quaternion = _Vec(), _Quat()
        self.rotation_mode = 'XYZ'
        self.inu = types.SimpleNamespace(
            model_id=0, interior_id=0, lod_index=-1, ipl_uuid='',
            ipl_target_file='', ipl_last_model_id=0, ipl_last_name='',
            ipl_last_pos=(0.0, 0.0, 0.0), ipl_last_rot=(0.0, 0.0, 0.0, 1.0),
            ipl_owner='', lod_object=None)
        self.users_collection, self.props = [], {}
        self.name = objs.unique(name)
        objs.all.append(self)

    def copy(self):
        dup = _Obj(self._objs, self.name, self.data, self.type)
        dup.location = self.location.copy()
        dup.rotation_mode = self.rotation_mode
        dup.rotation_quaternion = self.rotation_quaternion.copy()
        dup.inu = types.SimpleNamespace(**vars(self.inu))
        dup.props = dict(self.props)
        return dup

    def get(self, k, d=None):
        return self.props.get(k, d)

    def __setitem__(self, k, v):
        self.props[k] = v


class _Objects:
    def __init__(self):
        self.all = []

    def unique(self, name):
        taken = {o.name for o in self.all}
        if name not in taken:
            return name
        base, n = re.sub(r'\.\d{3}$', '', name), 1
        while "%s.%03d" % (base, n) in taken:
            n += 1
        return "%s.%03d" % (base, n)

    def __iter__(self):             # bpy.data lists are sorted by name
        return iter(sorted(self.all, key=lambda o: o.name))

    def new(self, name, data):
        return _Obj(self, name, data, 'EMPTY' if data is None else 'MESH')

    def remove(self, o, do_unlink=True):
        self.all.remove(o)
        for c in o.users_collection:
            c.objects.remove(o)


class _Collections(dict):
    def new(self, name):
        c = self[name] = _Coll(name)
        return c


def _model_type(obj):          # tools.model_utils.get_model_type, name only
    return classify_model(re.sub(r'\.\d{3}$', '', obj.name))


def _clean_name(name):         # __init__._clean_name_typed_ipl
    mt, base = _model_type(types.SimpleNamespace(name=name))
    return base, mt or 'OTHER'


@pytest.fixture
def world(monkeypatch, tmp_path):
    """Fresh fake scene + import_ipl / Replace Empty bound to it."""
    scene_coll = _Coll('Scene Collection')
    bpy = types.SimpleNamespace(
        data=types.SimpleNamespace(objects=_Objects(), collections=_Collections()),
        context=types.SimpleNamespace(scene=types.SimpleNamespace(
            collection=scene_coll)),
        path=types.SimpleNamespace(abspath=lambda p: p),
        types=types.SimpleNamespace(Object=_Obj, Operator=object))

    imp = types.ModuleType('INU_tools.ops.ipl_import')
    imp.__package__ = 'INU_tools.ops'
    imp.__dict__.update(bpy=bpy, Vector=_Vec, Quaternion=_Quat, read_ipl=read_ipl)
    _extract(IPL_IMPORT, {"import_ipl", "_row_target", "_linked_copy",
                          "_clean_name_typed"}, imp.__dict__)
    link = types.ModuleType('INU_tools.ops.map_link')
    link.__dict__.update(bpy=bpy, os=os)
    _extract(MAP_LINK, {"norm", "ipl_linked_file", "stamp_ipl", "clear_ipl"},
             link.__dict__)
    mu = types.ModuleType('INU_tools.tools.model_utils')
    mu.get_model_type = _model_type
    monkeypatch.setitem(sys.modules, 'INU_tools.ops.ipl_import', imp)
    monkeypatch.setitem(sys.modules, 'INU_tools.ops.map_link', link)
    monkeypatch.setitem(sys.modules, 'INU_tools.tools.model_utils', mu)
    monkeypatch.setattr(sys.modules['INU_tools'], '_clean_name_typed_ipl',
                        _clean_name, raising=False)

    src, fn = _func_src(IDE_IPL, "GTATOOLS_OT_replace_ipl_placeholders", "execute")
    rns = {'__package__': 'INU_tools.ops', '__name__': 'INU_tools.ops.ide_ipl',
           'bpy': bpy, 'T': lambda s, *a, **k: s}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), IDE_IPL, 'exec'), rns)

    w = types.SimpleNamespace(bpy=bpy, tmp=tmp_path)

    def mesh(name, data=None):
        o = _Obj(bpy.data.objects, name, data or 'M_' + name, 'MESH')
        scene_coll.objects.link(o)
        return o

    def ipl(fname, rows):
        p = tmp_path / fname
        p.write_text("inst\n" + "\n".join(rows) + "\nend\n", encoding="utf-8")
        return imp.import_ipl(str(p))

    def placeholder(model, mid, pos):
        e = _Obj(bpy.data.objects, model + '_empty', None, 'EMPTY')
        e.location = _Vec(pos)
        e['ipl_placeholder'] = True
        e['ipl_model_name'] = model
        e.inu.model_id = mid

    def replace():
        rns['execute'](types.SimpleNamespace(report=lambda *a: None), None)

    def objs():
        return {o.name: o for o in bpy.data.objects}

    w.mesh, w.ipl, w.placeholder, w.replace, w.objs = (
        mesh, ipl, placeholder, replace, objs)
    return w


def _row(mid, name, x, lod=-1, y=0.0):
    return "%d, %s, 0, %g, %g, 0, 0, 0, 0, 1, %d" % (mid, name, x, y, lod)


def _where(w):
    """name → (x, model_id, linked IPL file name or '')."""
    return {n: (o.location.v[0], o.inu.model_id,
                os.path.basename(o.inu.ipl_target_file) if o.inu.ipl_uuid else '')
            for n, o in w.objs().items()}


def test_every_row_placed_and_reimport_adds_nothing(world):
    world.mesh("lamp")
    rows = [_row(200, "lamp", x) for x in (1, 2, 3)]
    world.ipl("a.ipl", rows)
    assert _where(world) == {"lamp": (1, 200, "a.ipl"),
                             "lamp.001": (2, 200, "a.ipl"),
                             "lamp.002": (3, 200, "a.ipl")}
    uuids = {o.inu.ipl_uuid for o in world.objs().values()}
    assert len(uuids) == 3                   # a link of its own per row
    world.ipl("a.ipl", rows)
    assert len(world.objs()) == 3


def test_moved_copy_goes_back_to_its_row(world):
    world.mesh("lamp")
    rows = [_row(200, "lamp", x) for x in (1, 2, 3)]
    world.ipl("a.ipl", rows)
    world.objs()["lamp.002"].location = _Vec((9, 9, 9))
    world.ipl("a.ipl", rows)
    assert sorted(v[0] for v in _where(world).values()) == [1, 2, 3]


def test_same_spot_rows_each_get_one(world):
    world.mesh("lamp")
    rows = [_row(200, "lamp", 1)] * 3
    world.ipl("a.ipl", rows)
    world.ipl("a.ipl", rows)
    assert len(world.objs()) == 3


def test_second_ipl_keeps_first_placements(world):
    world.mesh("lamp")
    a = [_row(200, "lamp", x) for x in (1, 2)]
    b = [_row(200, "lamp", x) for x in (5, 6)]
    world.ipl("area1.ipl", a)
    world.ipl("area2.ipl", b)
    world.ipl("area1.ipl", a)
    world.ipl("area2.ipl", b)
    got = sorted((v[0], v[2]) for v in _where(world).values())
    assert got == [(1, "area1.ipl"), (2, "area1.ipl"),
                   (5, "area2.ipl"), (6, "area2.ipl")]


@pytest.mark.parametrize("lod_first", [False, True])
def test_lod_row_without_lod_mesh_adds_nothing(world, lod_first):
    # scene: the model + its COL, no LOD mesh; the IPL: model row + its LOD row
    world.mesh("building")
    world.mesh("building_COL")
    rows = ([_row(101, "lodbuilding", 10), _row(100, "building", 10, lod=0)]
            if lod_first else
            [_row(100, "building", 10, lod=1), _row(101, "lodbuilding", 10)])
    world.ipl("s.ipl", rows)
    got = _where(world)
    assert got["building"] == (10, 100, "s.ipl")
    assert got["building_COL"][0] == 10
    assert len(got) == 2


def test_lod_only_rows_keep_stand_ins(world):
    # text IPL of LOD rows only, scene has just the model: stand-ins as before
    world.mesh("building")
    rows = [_row(101, "lodbuilding", x) for x in (10, 20)]
    world.ipl("t.ipl", rows)
    world.ipl("t.ipl", rows)
    assert sorted((v[0], v[1]) for v in _where(world).values()) == [
        (10, 101), (20, 101)]


def test_lod_row_over_placed_model_keeps_it(world):
    world.mesh("building")
    world.ipl("stream.ipl", [_row(100, "building", 10)])
    world.ipl("text.ipl", [_row(101, "lodbuilding", 10),
                           _row(101, "lodbuilding", 40)])
    got = _where(world)
    assert got["building"] == (10, 100, "stream.ipl")   # not taken over
    assert sorted(v[:2] for v in got.values()) == [(10, 100), (40, 101)]


def test_copies_pair_with_their_own_lod(world):
    world.mesh("house")
    world.mesh("lodhouse")
    world.ipl("a.ipl", [_row(300, "house", 10, lod=2), _row(300, "house", 20, lod=3),
                        _row(301, "lodhouse", 10), _row(301, "lodhouse", 20)])
    world.ipl("b.ipl", [_row(300, "house", 50, lod=1), _row(301, "lodhouse", 50)])
    got = world.objs()
    pairs = sorted((o.location.v[0], o.inu.lod_object.location.v[0])
                   for o in got.values() if o.inu.lod_object is not None)
    assert pairs == [(10, 10), (20, 20), (50, 50)]
    assert len({id(o.inu.lod_object) for o in got.values()
                if o.inu.lod_object is not None}) == 3
    assert len(got) == 6


def test_replace_empty_lod_placeholders_add_nothing_on_the_model(world):
    world.mesh("building")
    # LOD placeholders sort before the model's ones by name — must not matter
    for x in (10, 20):
        world.placeholder("LODbuilding", 101, (x, 0, 0))
        world.placeholder("building", 100, (x, 0, 0))
    world.replace()
    assert sorted(v[:2] for v in _where(world).values()) == [(10, 100), (20, 100)]


def test_replace_empty_keeps_linked_model(world):
    world.mesh("lamp")
    world.ipl("a.ipl", [_row(200, "lamp", 1)])
    world.placeholder("lamp", 200, (7, 0, 0))
    world.placeholder("lamp", 200, (8, 0, 0))
    world.replace()
    got = _where(world)
    assert got["lamp"] == (1, 200, "a.ipl")
    assert sorted(v[0] for v in got.values()) == [1, 7, 8]


def test_replace_empty_lod_only_stand_ins(world):
    world.mesh("building")
    world.placeholder("lodbuilding", 101, (10, 0, 0))
    world.placeholder("lodbuilding", 101, (20, 0, 0))
    world.replace()
    assert sorted(v[:2] for v in _where(world).values()) == [(10, 101), (20, 101)]
