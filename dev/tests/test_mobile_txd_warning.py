# Platform MOBILE: every export that writes a TXD warns that it is PC-format.
#
# CHK-M8 (max_export:4). The addon writes no mobile TXD (PVRTC/ETC1 — only
# TxdGen does; core/txd_mobile only recognises the container on import), so
# with the MOBILE platform every TXD it writes is PC-format and the mobile
# game won't read it. Only the standalone Export TXD said so; Export All (to
# a folder), «Один DFF», INU Export, Export to IMG / All → IMG and Map Export
# wrote it silently. Now they all warn — one shared text,
# tools.txd_export.mobile_txd_warning (as Max's txd_data does on every path).
# The warning is the last report of the run (the status bar shows the latest
# one). All → IMG runs Export to IMG through bpy.ops, whose reports Blender
# keeps in the console (RPT_OP_HOLD) — Export All repeats its summary and
# the warning itself.
#
# Also: run_group_export returned 4 values on an empty selection while all
# three callers unpack 5 — Export All / Export DFF (по моделям) died with
# ValueError instead of «Выделите модели для экспорта!».

import ast
import io
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INU_EXPORT = ROOT / "INU_tools" / "ops" / "inu_export.py"
IMG_OPS = ROOT / "INU_tools" / "ops" / "img_ops.py"
MAP_EXPORT = ROOT / "INU_tools" / "tools" / "map_export.py"
sys.path.insert(0, str(ROOT / "INU_tools"))

KEY = "TXD сохранён в PC формате. Для mobile конвертируй через TxdGen (PVRTC/ETC1)."


def _ensure_bpy_stubs():
    # as in test_txd_platform — tools.txd_export imports bpy at module level
    bpy_mod = sys.modules.get('bpy')
    if bpy_mod is None:
        bpy_mod = types.ModuleType('bpy')
        sys.modules['bpy'] = bpy_mod
    if not hasattr(bpy_mod, 'types'):
        class _D:  # noqa: D401
            pass
        bpy_mod.types = types.SimpleNamespace(Operator=_D, Panel=_D, PropertyGroup=_D)
        sys.modules['bpy.types'] = bpy_mod.types
    if not hasattr(bpy_mod, 'props'):
        bpy_mod.props = types.SimpleNamespace(
            StringProperty=lambda **kw: None, IntProperty=lambda **kw: None,
            FloatProperty=lambda **kw: None, BoolProperty=lambda **kw: None,
            EnumProperty=lambda **kw: None)
        sys.modules['bpy.props'] = bpy_mod.props
    if not hasattr(bpy_mod, 'context'):
        bpy_mod.context = types.SimpleNamespace(scene=None)


_ensure_bpy_stubs()
_pkg_root = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
_pkg_root.__path__ = [str(ROOT / "INU_tools")]
_pkg_root.T = lambda s, *_a, **_kw: s

from INU_tools.tools import txd_export as tx           # noqa: E402

INU_TREE = ast.parse(io.open(INU_EXPORT, encoding="utf-8").read())


def _calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id == name)
        or (isinstance(n.func, ast.Attribute) and n.func.attr == name))]


def _func(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


# ── the shared text ─────────────────────────────────────────────────────

def test_mobile_with_txd_warns():
    assert tx.mobile_txd_warning('MOBILE', 1) == KEY


@pytest.mark.parametrize("platform, n", [('MOBILE', 0), ('PC', 3), (None, 1), ('', 2)])
def test_no_warning_otherwise(platform, n):
    assert tx.mobile_txd_warning(platform, n) is None


# ── Export All / Один DFF / INU Export reports ─────────────────────────

class _Op:
    def __init__(self):
        self.reports = []

    def report(self, level, text):
        self.reports.append((set(level), text))


def _reporters(platform):
    ns = {"__name__": "INU_tools.ops.inu_export", "__package__": "INU_tools.ops",
          "T": lambda s, *_a, **_kw: s,
          "bpy": types.SimpleNamespace(context=types.SimpleNamespace(
              scene=types.SimpleNamespace(inu_settings=types.SimpleNamespace(
                  gtatools_platform=platform))))}
    names = {"_report_group_export", "_warn_mobile_txd", "_report_single_dff"}
    body = [n for n in INU_TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == names
    exec(compile(ast.Module(body=body, type_ignores=[]), str(INU_EXPORT), "exec"), ns)
    return ns


@pytest.mark.parametrize("platform, exported, warn", [
    ('MOBILE', ['a.dff', 'a.txd'], True),
    ('MOBILE', ['a.dff', 'textures.txd (3 models)'], True),   # shared TXD
    ('MOBILE', ['a.dff', 'a.col'], False),                     # no TXD written
    ('PC', ['a.dff', 'a.txd'], False),
])
def test_group_export_report(platform, exported, warn):
    op = _Op()
    assert _reporters(platform)["_report_group_export"](
        op, exported, [], [], 1) == {'FINISHED'}
    assert (op.reports[-1] == ({'WARNING'}, KEY)) is warn
    assert sum(t == KEY for _l, t in op.reports) == int(warn)


def test_group_export_nothing_selected_does_not_warn():
    op = _Op()
    assert _reporters('MOBILE')["_report_group_export"](op, [], [], [], 0) == {'CANCELLED'}
    assert all(t != KEY for _l, t in op.reports)


@pytest.mark.parametrize("out, warn", [
    (['car.dff', 'car.txd', 'car.dff (+collision)'], True),
    (['car.dff', 'car.txd (обновлено 1)'], True),               # merged TXD
    (['car.dff'], False),
])
def test_single_dff_report(out, warn):
    op = _Op()
    root = types.SimpleNamespace(name="car")
    assert _reporters('MOBILE')["_report_single_dff"](op, out, [], root, 0) == {'FINISHED'}
    assert (op.reports[-1] == ({'WARNING'}, KEY)) is warn


def test_single_dff_nothing_written_does_not_warn():
    op = _Op()
    assert _reporters('MOBILE')["_report_single_dff"](op, [], ["x"], None, 0) == {'CANCELLED'}
    assert all(t != KEY for _l, t in op.reports)


# ── Export to IMG / All → IMG and Map Export ────────────────────────────

def test_export_to_img_warns_after_the_summary():
    tree = ast.parse(io.open(IMG_OPS, encoding="utf-8").read())
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "GTATOOLS_OT_export_to_img")
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
    calls = _calls(fn, "mobile_txd_warning")
    assert len(calls) == 1
    assert [ast.unparse(a) for a in calls[0].args] == ["dff_target_platform", "n_txd"]
    reps = [c for c in _calls(fn, "report") if len(c.args) == 2]
    mob = [c for c in reps if ast.unparse(c.args[1]) == "_mob"]
    summary = [c for c in reps if ast.unparse(c.args[1]).startswith("f'IMG: {summary}")]
    assert len(mob) == len(summary) == 1
    assert "WARNING" in ast.unparse(mob[0].args[0])
    # after the summary, the last report of the run (the status bar keeps
    # the latest one); on the function's own level, not in a branch
    assert summary[0].lineno < mob[0].lineno
    assert max(reps, key=lambda c: c.lineno) is mob[0]
    stmt = next(s for s in fn.body if _calls(s, "mobile_txd_warning"))
    assert isinstance(stmt, ast.Assign) and isinstance(fn.body[-1], ast.Return)


def test_map_export_warns_after_the_summary():
    tree = ast.parse(io.open(MAP_EXPORT, encoding="utf-8").read())
    calls = _calls(tree, "mobile_txd_warning")
    assert len(calls) == 1
    src = ast.unparse(calls[0])
    assert "gtatools_platform" in src and "stats.get('txd', 0)" in src
    # the finish branch of modal: the summary, then the warning — the last
    # report of the run (the status bar keeps the latest one). Whatever the
    # summary looks like (one INFO line or a loop over report lines).
    h = next(h for h in ast.walk(tree) if isinstance(h, ast.ExceptHandler)
             and h.type is not None and ast.unparse(h.type) == "StopIteration")
    reps = _calls(h, "report")
    mob = [c for c in reps if len(c.args) == 2 and ast.unparse(c.args[1]) == "_mob"]
    assert len(mob) == 1 and "WARNING" in ast.unparse(mob[0].args[0])
    assert max(reps, key=lambda c: c.lineno) is mob[0]
    assert any("'INFO'" in ast.unparse(c.args[0]) for c in reps if c is not mob[0])
    assert calls[0].lineno < mob[0].lineno
    # right before the final return, on the handler's own level (the error
    # run returned earlier — it wrote no TXD)
    assert isinstance(h.body[-1], ast.Return) and "FINISHED" in ast.unparse(h.body[-1])
    assert any(n is mob[0] for n in ast.walk(h.body[-2]))


def test_export_to_img_leaves_its_result_for_all_to_img():
    # All → IMG runs Export to IMG through bpy.ops: Blender keeps the nested
    # operator's reports out of the status bar / Info (console only) — the
    # summary and the Mobile warning go to _export_final for Export All
    tree = ast.parse(io.open(IMG_OPS, encoding="utf-8").read())
    assert any(isinstance(n, ast.Assign) and ast.unparse(n) == "_export_final = {}"
               for n in tree.body)
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "GTATOOLS_OT_export_to_img")
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
    ups = [c for c in _calls(fn, "update") if ast.unparse(c.func) == "_export_final.update"]
    assert len(ups) == 1
    kw = {k.arg: ast.unparse(k.value) for k in ups[0].keywords}
    assert kw["mobile"] == "_mob"
    # the same texts the operator reports itself
    reps = [ast.unparse(c.args[1]) for c in _calls(fn, "report") if len(c.args) == 2]
    assert "f'IMG: {summary}{preview}{more}'" in reps
    assert "f'IMG: {summary}{preview}{more}'" in kw["summary"]
    assert "T('IMG: нет результатов экспорта')" in kw["summary"]
    # set only by a run that finished (right before its return)
    assert isinstance(fn.body[-1], ast.Return) and "FINISHED" in ast.unparse(fn.body[-1])
    assert any(n is ups[0] for n in ast.walk(fn.body[-2]))


# ── All → IMG: Export All repeats the nested Export to IMG's result ─────

def _export_all_execute():
    cls = next(n for n in INU_TREE.body if isinstance(n, ast.ClassDef)
               and n.name == "GTATOOLS_OT_export_all")
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "execute")


@pytest.fixture
def all_to_img(monkeypatch):
    img = types.ModuleType("INU_tools.ops.img_ops")
    img._export_final, img._export_unwritten = {}, set()
    img._export_routes = lambda ctx, groups: ({"x.img": list(groups)}, [])
    img.fill_export_plan = lambda *_a, **_kw: None
    mu = types.ModuleType("INU_tools.tools.model_utils")
    mu.find_all_selected_model_groups = lambda: {"a": {}}
    monkeypatch.setitem(sys.modules, "INU_tools.ops.img_ops", img)
    monkeypatch.setitem(sys.modules, "INU_tools.tools.model_utils", mu)

    def run(res, final, ide_ipl=True):
        def export_to_img(*_a, **_kw):
            img._export_final.update(final)   # a stale one when cancelled
            return res
        ns = {"__name__": "INU_tools.ops.inu_export", "__package__": "INU_tools.ops",
              "T": lambda s, *_a, **_kw: s,
              "bpy": types.SimpleNamespace(ops=types.SimpleNamespace(
                  gtatools=types.SimpleNamespace(export_to_img=export_to_img)))}
        exec(compile(ast.Module(body=[_export_all_execute()], type_ignores=[]),
                     str(INU_EXPORT), "exec"), ns)
        op = _Op()
        op.to_img = True
        op._also_upsert_ide_ipl = lambda _ctx: op.report({'INFO'}, "IDE: добавлено 1")
        s = types.SimpleNamespace(
            gtatools_export_all_single_dff=False, gtatools_export_all_dff=True,
            gtatools_export_all_lod=True, gtatools_export_all_col=True,
            gtatools_export_all_txd=True, gtatools_export_all_col_empty=False,
            gtatools_export_all_txd_shared=False,
            gtatools_export_all_txd_shared_name="",
            gtatools_export_all_ide_ipl=ide_ipl)
        ctx = types.SimpleNamespace(scene=types.SimpleNamespace(inu_settings=s))
        assert ns["execute"](op, ctx) == res
        return op.reports

    return run


SUMMARY = ({'INFO'}, "IMG: DFF 1, TXD 1 — a.dff added, tex_a.txd added")


def test_all_to_img_repeats_summary_and_warns_last(all_to_img):
    got = all_to_img({'FINISHED'}, {"summary": SUMMARY, "mobile": KEY})
    assert got == [SUMMARY, ({'INFO'}, "IDE: добавлено 1"), ({'WARNING'}, KEY)]
    got = all_to_img({'FINISHED'}, {"summary": SUMMARY, "mobile": KEY}, ide_ipl=False)
    assert got == [SUMMARY, ({'WARNING'}, KEY)]


def test_all_to_img_without_mobile_shows_the_summary(all_to_img):
    got = all_to_img({'FINISHED'}, {"summary": SUMMARY, "mobile": None}, ide_ipl=False)
    assert got == [SUMMARY]


def test_all_to_img_cancelled_repeats_nothing(all_to_img):
    # the IMG refused — _export_final is a previous run's, not repeated
    assert all_to_img({'CANCELLED'}, {"summary": SUMMARY, "mobile": KEY}) == []


# ── INU Export: the warning after its IDE / IPL lines ───────────────────

def test_inu_export_warns_after_ide_ipl():
    cls = next(n for n in INU_TREE.body if isinstance(n, ast.ClassDef)
               and n.name == "GTATOOLS_OT_inu_export")
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
    # the shared reporters don't warn here…
    for name in ("_report_group_export", "_report_single_dff"):
        c = _calls(fn, name)
        assert len(c) == 1
        assert {k.arg: ast.unparse(k.value) for k in c[0].keywords} == {"mobile": "False"}
    # …the operator does, last: after the «objects.ide objects.ipl» line
    assert isinstance(fn.body[-1], ast.Return) and ast.unparse(fn.body[-1]) == "return result"
    warn = fn.body[-2]
    assert ast.unparse(warn) == "_warn_mobile_txd(self, written)"
    assert all(c.lineno < warn.lineno for c in _calls(fn, "report"))
    assigned = {ast.unparse(n.value) for n in ast.walk(fn) if isinstance(n, ast.Assign)
                and ast.unparse(n.targets[0]) == "written"}
    assert assigned == {"[]", "out", "exported"}


def test_reporters_can_leave_the_warning_to_the_caller():
    op = _Op()
    _reporters('MOBILE')["_report_group_export"](op, ['a.txd'], [], [], 1, mobile=False)
    root = types.SimpleNamespace(name="car")
    _reporters('MOBILE')["_report_single_dff"](op, ['car.txd'], [], root, 0, mobile=False)
    assert op.reports and all(t != KEY for _l, t in op.reports)


def _own_returns(fn):
    """Return statements of fn itself (not of its nested helpers)."""
    out, todo = [], list(fn.body)
    while todo:
        n = todo.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(n, ast.Return):
            out.append(n)
        todo.extend(ast.iter_child_nodes(n))
    return out


def test_run_group_export_always_returns_five_values():
    fn = _func(INU_TREE, "run_group_export")
    rets = _own_returns(fn)
    assert len(rets) == 2
    assert all(isinstance(r.value, ast.Tuple) and len(r.value.elts) == 5
               for r in rets)
    # and every caller unpacks five
    for c in _calls(INU_TREE, "run_group_export"):
        parent = next(n for n in ast.walk(INU_TREE) if isinstance(n, ast.Assign)
                      and n.value is c)
        assert len(parent.targets[0].elts) == 5
