# «Apply to selected» (gtatools.batch_set_distance) with «Sequential (+1)»
# used to number OBJECTS: copies of one model (tree, tree.001 — Shift+D,
# Import Map) got different IDs. Export IDE writes one row per model name,
# the IPL writes each copy's own ID → IPL rows with IDs no IDE defines, and
# SA crashes on load (LoadObjectInstance 0x538090 → NULL). The number is now
# per MODEL: the first object of a model takes the next ID, its copies the
# same one; a LOD is its own model (own IDE row), collision follows its model.
#
# col_surface_ops imports bpy at module level, so the helpers and the
# operator's methods are pulled out by AST; the `from ..tools.model_utils
# import …` inside them is answered by a stand-in package over the pure
# classifier.

import ast
import io
import os
import re
import runpy
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INU = os.path.join(ROOT, "INU_tools")
MODULE = os.path.join(INU, "ops", "col_surface_ops.py")
sys.path.insert(0, INU)

from core.model_classify import classify_model  # noqa: E402

_PKG = "_batchids_pkg"
_CLS = "GTATOOLS_OT_batch_set_distance"


def _load():
    tree = ast.parse(io.open(MODULE, encoding="utf-8").read())
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in ("_model_key", "_seq_ids")]
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == _CLS)
    meths = [n for n in cls.body if isinstance(n, ast.FunctionDef)
             and n.name in ("_targets", "_row", "draw", "execute")]
    assert len(funcs) == 2 and len(meths) == 4
    ns = {"T": lambda s: s, "safe_icon": lambda s: s,
          "inu_icon": lambda s: {},
          "__package__": _PKG + ".ops",
          "__name__": _PKG + ".ops.col_surface_ops"}
    exec(compile(ast.Module(body=funcs + meths, type_ignores=[]),
                 MODULE, "exec"), ns)
    return ns, cls


NS, CLS_NODE = _load()
model_key = NS["_model_key"]
seq_ids = NS["_seq_ids"]

_DUP3 = re.compile(r'\.\d{3}$')        # tools.model_utils._strip_dup_suffix


def _classify(o):
    """tools.model_utils.get_model_type over the pure classifier."""
    return classify_model(_DUP3.sub('', o.name), has_texture=True,
                          inu_type=o.inu.type)


@pytest.fixture
def fake_pkg(monkeypatch):
    mu = types.ModuleType(_PKG + ".tools.model_utils")
    mu.get_model_type = _classify
    mu.get_model_type_cached = _classify
    for name, mod in ((_PKG, types.ModuleType(_PKG)),
                      (_PKG + ".ops", types.ModuleType(_PKG + ".ops")),
                      (_PKG + ".tools", types.ModuleType(_PKG + ".tools")),
                      (_PKG + ".tools.model_utils", mu)):
        mod.__path__ = []
        monkeypatch.setitem(sys.modules, name, mod)


# ── stand-ins for Blender objects / the operator ────────────────────────

def _obj(name, inu_type='OBJ'):
    return types.SimpleNamespace(
        name=name, type='MESH',
        inu=types.SimpleNamespace(type=inu_type, model_id=0))


def _ctx(*names):
    return types.SimpleNamespace(selected_objects=[_obj(n) for n in names])


class _Layout:
    def __init__(self):
        self.labels = []
        self.active = True

    def row(self, **kw):
        return self

    def prop(self, *a, **kw):
        pass

    def separator(self, **kw):
        pass

    def label(self, text="", **kw):
        self.labels.append(text)


class _Op:
    _targets = NS["_targets"]
    _row = NS["_row"]
    draw = NS["draw"]
    execute = NS["execute"]

    def __init__(self, **kw):
        self.__dict__.update(dict(
            apply_draw=False, draw_distance=299.0, apply_lod=False,
            lod_draw_distance=999.0, apply_model_id=True, model_id=20000,
            model_id_sequential=True, apply_txd=False, txd_name="",
            apply_interior=False, interior_id=0, apply_flags=False,
            ide_flags=0, apply_col_name=False, col_name=""), **kw)
        self.layout = _Layout()
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((kind, msg))


# ── pure helpers ─────────────────────────────────────────────────────────

def test_seq_ids_one_number_per_model():
    assert seq_ids(['tree', 'tree', 'bush'], 20000) == {'tree': 20000,
                                                        'bush': 20001}
    assert seq_ids([], 5) == {}


def test_model_key_copies_share_lod_apart():
    def k(name, inu_type='OBJ'):
        return model_key(_obj(name, inu_type), _classify)
    # Blender copies (.001 … and .1000 past .999), any case — one model
    assert k('tree') == k('tree.001') == k('Tree.002') == k('tree.1000')
    # a LOD is its own model (own IDE row), keyed by its own name; its
    # copies share
    assert k('LODtree') != k('tree')
    assert k('LODtree') == k('LODtree.001') == k('lodtree') == k('LODtree.1000')
    assert k('lod_tree') != k('LODtree')
    # collision has no IDE row — goes with its model
    assert k('tree_col') == k('tree')
    assert k('bush') != k('tree')


# ── the operator ─────────────────────────────────────────────────────────

def test_execute_copies_get_one_id(fake_pkg):
    ctx = _ctx('tree.002', 'bush', 'tree', 'LODtree', 'rock', 'tree.001',
               'tree_col')
    op = _Op()
    assert op.execute(ctx) == {'FINISHED'}
    got = {o.name: o.inu.model_id for o in ctx.selected_objects}
    # by name: LODtree, bush, rock, tree, tree.001, tree.002, tree_col
    assert got == {'LODtree': 20000, 'bush': 20001, 'rock': 20002,
                   'tree': 20003, 'tree.001': 20003, 'tree.002': 20003,
                   'tree_col': 20003}
    assert op.reports[-1] == ({'INFO'}, "Изменено: 7")


def test_execute_unchecked_same_id_for_all(fake_pkg):
    ctx = _ctx('a', 'b', 'a.001')
    _Op(model_id_sequential=False, model_id=777).execute(ctx)
    assert [o.inu.model_id for o in ctx.selected_objects] == [777, 777, 777]


def test_draw_range_counts_models(fake_pkg):
    op = _Op()
    op.draw(_ctx('tree', 'tree.001', 'bush', 'LODtree'))
    assert op.layout.labels[0] == "4 объектов будет изменено"
    assert op.layout.labels[-1] == "ID: 20000 … 20002"   # 3 models
    op = _Op()
    op.draw(_ctx('tree', 'tree.001', 'tree.002'))        # one model, one ID
    assert not any(t.startswith("ID:") for t in op.layout.labels)


def test_sequential_tooltip_translated():
    # `model_id_sequential: BoolProperty(...)` — the call is the annotation
    text = next(kw.value.args[0].value
                for st in CLS_NODE.body
                if isinstance(st, ast.AnnAssign)
                and getattr(st.target, 'id', '') == 'model_id_sequential'
                for kw in st.annotation.keywords if kw.arg == 'description')
    assert "Копии одной модели" in text
    for lang in ("eng", "spa"):
        table = runpy.run_path(os.path.join(INU, "locale", lang + ".py"))
        assert table["LANG"].get(text), lang
