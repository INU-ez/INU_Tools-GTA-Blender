# Export to IMG: LOD / COL stubs are off by default.
#
# invoke() used to tick «LOD» and «COL» for every model, even when no LOD /
# COL was found in the scene. The default export then wrote a copy of the
# model as LOD<base>.dff and an empty <base>.col over the real ones already in
# the archive (walk-through house, LOD replaced by the HD model). Now found
# LOD / COL are ticked, stubs are written only on an explicit tick — like Max.
#
# ops/img_ops.py and __init__.py import bpy at module level — checked by AST.

import ast
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMG_OPS = os.path.join(ROOT, "INU_tools", "ops", "img_ops.py")
INIT = os.path.join(ROOT, "INU_tools", "__init__.py")


def _class(path, name):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def _method(cls, name):
    for fn in cls.body:
        if isinstance(fn, ast.FunctionDef) and fn.name == name:
            return fn
    raise AssertionError(f"{cls.name}.{name} not found")


def _assigns_to(fn, attr):
    return [n for n in ast.walk(fn) if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Attribute) and t.attr == attr for t in n.targets)]


def _names(node):
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def test_invoke_ticks_only_found_lod_and_col():
    # the rows are filled by fill_export_plan (All → IMG uses it too); the
    # dialog calls it with the stub switches at their defaults (off)
    inv = _method(_class(IMG_OPS, "GTATOOLS_OT_export_to_img"), "invoke")
    calls = [n for n in ast.walk(inv) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "fill_export_plan"]
    assert calls and all(not c.keywords for c in calls)
    tree = ast.parse(io.open(IMG_OPS, encoding="utf-8").read())
    fill = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "fill_export_plan")
    stubs = {a.arg: d.value for a, d in zip(fill.args.kwonlyargs,
                                            fill.args.kw_defaults)}
    assert stubs["lod_stub"] is False and stubs["col_stub"] is False
    for attr, found, obj in (("inc_lod", "lod_found", "lod_obj"),
                             ("inc_col", "col_found", "col_obj")):
        assigns = _assigns_to(fill, attr)
        assert assigns, f"fill_export_plan() no longer fills {attr}"
        for a in assigns:
            # never a blanket True (that is what ticked the stubs)
            assert not (isinstance(a.value, ast.Constant)
                        and a.value.value is True), attr
            # follows «found in the scene»
            assert _names(a.value) & {found, obj}, attr


def test_plan_entry_defaults_are_off():
    cls = _class(INIT, "GTATOOLS_TxdExportEntry")
    seen = set()
    for stmt in cls.body:
        if (isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.target.id in ("inc_lod", "inc_col")):
            kw = {k.arg: k.value for k in stmt.annotation.keywords}
            assert isinstance(kw.get("default"), ast.Constant)
            assert kw["default"].value is False, stmt.target.id
            seen.add(stmt.target.id)
    assert seen == {"inc_lod", "inc_col"}
