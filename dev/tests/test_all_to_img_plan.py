# Export All → «All → IMG»: the toggles of the Export All window reach the IMG.
#
# IMG-15 (max_export:1). All → IMG cleared the plan of the Export to IMG
# window and ran gtatools.export_to_img without it: with no plan row LOD and
# COL are never written, DFF and TXD always (the DFF / TXD toggles were
# ignored), the TXD went out as <model>.txd and obj.inu.txd_name was then
# overwritten with the model name (a vanilla model of countn2_xxx pointed its
# IDE row at a wrong TXD). The window showed the IMG from settings, while the
# models went to their own archives. Now All → IMG fills the plan the same
# way the window does (fill_export_plan): LOD / COL only when found (as the
# folder export), «Пустая коллизия» = an empty COL for everyone, TXD name =
# the model's txd_name (the TXD is merged with the archive's, IMG-2); DFF /
# TXD toggles go as hidden SKIP_SAVE props; «Один DFF» + All → IMG is refused
# (the car's parts would go into the IMG as separate DFFs); the window shows
# the real target archives. «Общий TXD» of Export All now reaches the dialog
# (it was read from the Scene instead of scene.inu_settings).
#
# ops/img_ops.py / ops/inu_export.py import bpy at module level — the plan
# filler and the closures are pulled out by AST and run on stand-ins; the
# wiring is checked on the AST.

import ast
import io
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMG_OPS = ROOT / "INU_tools" / "ops" / "img_ops.py"
INU_EXPORT = ROOT / "INU_tools" / "ops" / "inu_export.py"

# `from ..tools.model_utils import …` inside fill_export_plan resolves through
# a minimal stub package (the addon __init__ needs Blender).
_pkg_root = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
_pkg_root.__path__ = [str(ROOT / "INU_tools")]

TREE = ast.parse(io.open(IMG_OPS, encoding="utf-8").read())
EXPORT = next(n for n in ast.walk(TREE)
              if isinstance(n, ast.ClassDef) and n.name == "GTATOOLS_OT_export_to_img")
EXECUTE = next(n for n in EXPORT.body
               if isinstance(n, ast.FunctionDef) and n.name == "execute")

INU_TREE = ast.parse(io.open(INU_EXPORT, encoding="utf-8").read())
EXPORT_ALL = next(n for n in ast.walk(INU_TREE)
                  if isinstance(n, ast.ClassDef) and n.name == "GTATOOLS_OT_export_all")

REFUSE = "All → IMG не работает с «Один DFF» — выключите одно из двух"
TO_IMG_DESC = ("Экспортировать прямо в .img: модель со своим IMG — в него, "
               "остальные — в архив, выбранный в «Экспорт в IMG» (иначе из "
               "настроек аддона). Выбор папки при этом игнорируется")
OLD_TO_IMG_DESC = ("Экспортировать прямо в .img архив, путь к которому задан в "
                   "настройках аддона. Выбор папки при этом игнорируется")


def _calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id == name)
        or (isinstance(n.func, ast.Attribute) and n.func.attr == name))]


def _method(cls, name):
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


# ── fill_export_plan on stand-ins ───────────────────────────────────────

class _Coll(list):
    """WindowManager collection: add() → a new row, clear()."""

    def add(self):
        row = types.SimpleNamespace()
        self.append(row)
        return row


def _obj(name, txd="", kind="MESH", display=""):
    return types.SimpleNamespace(name=name, type=kind, empty_display_type=display,
                                 inu=types.SimpleNamespace(txd_name=txd))


A_DFF = _obj("a", "tex_a")             # own TXD name, no LOD / COL
B_DFF, B_LOD, B_COL = _obj("b"), _obj("b_LOD", "b_lod"), _obj("b_COL")
C_DFF = _obj("c")                      # collision spheres only, no COL mesh
C_SPH = _obj("c_sphere_0", kind="EMPTY", display="SPHERE")
GROUPS = {
    "a": {"DFF": A_DFF, "LOD": None, "COL": None},
    # the LOD is not selected — found by name in the scene
    "b": {"DFF": B_DFF, "LOD": None, "COL": B_COL},
    "c": {"DFF": C_DFF, "LOD": None, "COL": None},
}


@pytest.fixture
def fill(monkeypatch):
    related = {"b": B_LOD}
    mu = types.ModuleType("INU_tools.tools.model_utils")
    mu.find_related_models = lambda base: {"DFF": None, "LOD": related.get(base),
                                           "COL": None}
    monkeypatch.setitem(sys.modules, "INU_tools.tools.model_utils", mu)
    ns = {"__name__": "INU_tools.ops.img_ops", "__package__": "INU_tools.ops"}
    names = {"fill_export_plan", "_col_prim_index", "_col_prims_of"}
    body = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == names
    exec(compile(ast.Module(body=body, type_ignores=[]), str(IMG_OPS), "exec"), ns)

    def run(**kw):
        plan = _Coll([types.SimpleNamespace(model_name="stale")])
        wm = types.SimpleNamespace(gtatools_txd_export_plan=plan,
                                   gtatools_txd_export_plan_index=7)
        ctx = types.SimpleNamespace(
            window_manager=wm,
            scene=types.SimpleNamespace(objects=[A_DFF, B_DFF, B_LOD, B_COL,
                                                 C_DFF, C_SPH]))
        ns["fill_export_plan"](ctx, GROUPS, **kw)
        assert wm.gtatools_txd_export_plan_index == 0
        return {e.model_name: e for e in plan}

    return run


def _ticks(plan):
    return {b: (e.inc_lod, e.inc_col) for b, e in plan.items()}


def test_dialog_rows_are_the_same_as_before(fill):
    plan = fill()
    assert list(plan) == ["a", "b", "c"]            # stale row dropped
    assert all(e.include for e in plan.values())
    assert {b: e.txd_name for b, e in plan.items()} == {"a": "tex_a", "b": "b", "c": "c"}
    b = plan["b"]
    assert (b.lod_found, b.lod_name, b.col_found, b.col_name) == (
        True, "b_LOD", True, "b_COL")
    c = plan["c"]
    assert (c.col_found, c.col_name, c.col_prims) == (True, "", 1)
    # found LOD / COL ticked; stubs and spheres-only — not (IMG-5 / IMG-4)
    assert _ticks(plan) == {"a": (False, False), "b": (True, True), "c": (False, False)}


def test_all_to_img_writes_found_lod_and_col():
    # what Export All passes with LOD and COL on, «Пустая коллизия» off
    calls = _calls(_method(EXPORT_ALL, "execute"), "fill_export_plan")
    assert len(calls) == 1
    kw = {k.arg: ast.unparse(k.value) for k in calls[0].keywords}
    assert kw == {"want_lod": "bool(s.gtatools_export_all_lod)",
                  "want_col": "bool(s.gtatools_export_all_col)",
                  "col_stub": "empty_col"}   # never a LOD stub from All → IMG


def test_all_to_img_toggles(fill):
    on = fill(want_lod=True, want_col=True, col_stub=False)
    assert _ticks(on) == {"a": (False, False), "b": (True, True), "c": (False, False)}
    # TXD name — the model's txd_name (the archive's TXD is merged, IMG-2)
    assert on["a"].txd_name == "tex_a" and on["b"].txd_name == "b"
    off = fill(want_lod=False, want_col=False, col_stub=True)
    assert _ticks(off) == {"a": (False, False), "b": (False, False), "c": (False, False)}
    assert off["b"].lod_found and off["b"].col_found   # still shown as found


def test_empty_collision_ticks_every_model(fill):
    plan = fill(want_lod=True, want_col=True, col_stub=True)
    assert _ticks(plan) == {"a": (False, True), "b": (True, True), "c": (False, True)}


def test_lod_stub_only_on_request(fill):
    assert fill(lod_stub=True)["a"].inc_lod is True
    assert fill()["a"].inc_lod is False


# ── export_to_img: hidden props of All → IMG ────────────────────────────

@pytest.mark.parametrize("prop", ["skip_dff", "skip_txd", "empty_col"])
def test_hidden_props_are_not_remembered(prop):
    # without SKIP_SAVE Blender keeps the last value: the panel's Export to
    # IMG button and the dialog would silently stop writing DFF / TXD
    ann = next(s for s in EXPORT.body if isinstance(s, ast.AnnAssign)
               and isinstance(s.target, ast.Name) and s.target.id == prop)
    assert ast.unparse(ann.annotation.func) == "BoolProperty"
    kw = {k.arg: k.value for k in ann.annotation.keywords}
    assert kw["default"].value is False
    opts = {e.value for e in kw["options"].elts}
    assert {"HIDDEN", "SKIP_SAVE"} <= opts


def test_dff_toggle_gates_every_dff_step():
    # name check, progress and the write itself
    tests = [n.test for n in ast.walk(EXECUTE) if isinstance(n, ast.If)
             and _calls(n.test, "_is_included") and "['DFF']" in ast.unparse(n.test)]
    assert len(tests) == 3
    assert all("not self.skip_dff" in ast.unparse(t) for t in tests)


def test_txd_toggle_empties_the_buckets():
    # no bucket → no TXD name check, no archive read, no write, no txd_name
    # written back
    plan = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.Assign)
            and ast.unparse(n.targets[0]) == "txd_buckets"
            and _calls(n.value, "_plan_txd_buckets")]
    assert len(plan) == 1
    comp = plan[0].value.args[0]
    assert isinstance(comp, ast.ListComp)
    assert "not self.skip_txd" in ast.unparse(comp.generators[0].ifs[0])


def _closures(names, **ns):
    body = [n for n in EXECUTE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == set(names)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(IMG_OPS), "exec"), ns)
    return ns


@pytest.mark.parametrize("empty", [False, True])
def test_empty_collision_drops_the_col_mesh_and_spheres(empty):
    col = _obj("b_COL")
    entry = types.SimpleNamespace(model_name="b", col_found=True, col_name="b_COL")
    ns = _closures({"_plan_entry", "_col_src"},
                   self=types.SimpleNamespace(empty_col=empty),
                   plan_by_name={"b": entry},
                   bpy=types.SimpleNamespace(data=types.SimpleNamespace(
                       objects={"b_COL": col})))
    got = ns["_col_src"]("b", {"DFF": None, "LOD": None, "COL": col})
    assert got is (None if empty else col)
    # spheres/boxes are not collected either (build_col_model gets nothing)
    idx = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.Assign)
           and ast.unparse(n.targets[0]) == "prim_idx"]
    assert idx and all("not self.empty_col" in ast.unparse(n.value) for n in idx)


def test_empty_collision_library_keeps_a_lone_col_model():
    # «Пустая коллизия» + library: _col_src gives None, and a selected lone
    # COL mesh has neither DFF nor LOD — the model still needs an object for
    # its archive (arch_of_obj[o.name]; None → AttributeError)
    lib = next(n for n in EXECUTE.body if isinstance(n, ast.If)
               and ast.unparse(n.test) == "col_library"
               and "library_col_objects.append" in ast.unparse(n))
    col, dff = _obj("k_COL"), _obj("m")
    ns = {"col_library": True, "_all_routes": {"x.img": ["k", "m"]},
          "_all_groups": {"k": {"DFF": None, "LOD": None, "COL": col},
                          "m": {"DFF": dff, "LOD": None, "COL": None}},
          "_inc_col": lambda b: True, "_col_src": lambda b, m: None,
          "col_idx": {"x.img": {"m": ["x.col"]}},
          "library_col_objects": [], "_lib_in": []}
    exec(compile(ast.Module(body=[lib], type_ignores=[]), str(IMG_OPS), "exec"), ns)
    assert ns["library_col_objects"] == [col] and ns["_lib_in"] == [dff]


@pytest.mark.parametrize("parts, want", [
    (("", "", "k_COL"), "k_COL"),       # a lone COL mesh — its own bounds
    (("m", "m_LOD", "k_COL"), "m"),     # the visual model first
    (("", "m_LOD", "k_COL"), "m_LOD"),
    (("", "", ""), None),
])
def test_empty_collision_bounds_of_a_lone_col_model(parts, want):
    # «Пустая коллизия»: the empty record's bounds are measured off the DFF /
    # LOD, and with neither — off the COL mesh (as the folder export), not
    # left at zero (GTA culls the model by that sphere → it disappears)
    blk = next(n for n in ast.walk(EXECUTE) if isinstance(n, ast.If)
               and ast.unparse(n.test) == "is_empty")
    models = {k: (_obj(n) if n else None) for k, n in zip(("DFF", "LOD", "COL"), parts)}
    ns = {"models": models, "is_empty": True, "_bref": None}
    exec(compile(ast.Module(body=[blk], type_ignores=[]), str(IMG_OPS), "exec"), ns)
    assert (ns["_bref"] and [o.name for o in ns["_bref"]]) == ([want] if want else None)


def test_shared_txd_prefill_reads_inu_settings():
    src = ast.unparse(_method(EXPORT, "invoke"))
    assert "context.scene.inu_settings, 'gtatools_export_all_txd_shared'" in src
    assert "getattr(context.scene, 'gtatools_export_all" not in ast.unparse(TREE)


# ── Export All: the All → IMG branch ────────────────────────────────────

def _to_img_branch():
    fn = _method(EXPORT_ALL, "execute")
    return next(n for n in ast.walk(fn) if isinstance(n, ast.If)
                and ast.unparse(n.test) == "self.to_img")


def test_single_dff_with_all_to_img_is_refused():
    br = _to_img_branch()
    first = br.body[0]
    assert isinstance(first, ast.If) and "gtatools_export_all_single_dff" in ast.unparse(first.test)
    keys = {c.args[0].value for c in _calls(first, "T")}
    assert REFUSE in keys
    assert any(isinstance(s, ast.Return) and "CANCELLED" in ast.unparse(s) for s in first.body)
    # shown in the window too, before the click
    assert REFUSE in {c.args[0].value for c in _calls(_method(EXPORT_ALL, "draw"), "T")
                      if c.args and isinstance(c.args[0], ast.Constant)}


def test_plan_is_filled_not_cleared_and_toggles_passed():
    br = _to_img_branch()
    src = ast.unparse(br)
    assert "gtatools_txd_export_plan.clear" not in src
    fill_ln = _calls(br, "fill_export_plan")[0].lineno
    call = _calls(br, "export_to_img")[0]
    assert fill_ln < call.lineno
    kw = {k.arg: ast.unparse(k.value) for k in call.keywords}
    assert kw["skip_dff"] == "not s.gtatools_export_all_dff"
    assert kw["skip_txd"] == "not s.gtatools_export_all_txd"
    assert kw["empty_col"] == "empty_col"


def test_window_and_check_use_the_real_archives():
    # the label and the check followed gtatools_img_path while the models
    # went to their own archives (and a model with its own IMG was refused
    # when settings were empty)
    br = _to_img_branch()
    assert _calls(br, "_export_routes")
    assert "isfile" not in ast.unparse(br)
    assert _calls(_method(EXPORT_ALL, "invoke"), "_export_routes")
    assert "_img_routes" in ast.unparse(_method(EXPORT_ALL, "draw"))


def _t_keys(tree):
    return {n.args[0].value for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "T" and n.args and isinstance(n.args[0], ast.Constant)}


def _lang(fname):
    tree = ast.parse((ROOT / "INU_tools" / "locale" / fname).read_text(encoding="utf-8"))
    d = next(n.value for n in tree.body if isinstance(n, ast.Assign))
    return {k.value for k in d.keys if isinstance(k, ast.Constant)}


def test_strings_are_translated():
    used = _t_keys(INU_TREE)
    assert {REFUSE, TO_IMG_DESC} <= used and OLD_TO_IMG_DESC not in used
    for lang in ("eng.py", "spa.py"):
        keys = _lang(lang)
        assert {REFUSE, TO_IMG_DESC} <= keys and OLD_TO_IMG_DESC not in keys
