# Export to IMG: each model goes into its own archive; the run report goes
# next to the .blend.
#
# idm_img:7 (IMG-7). The game takes a model from the FIRST archive that lists
# it (SA: CStreaming::LoadCdDirectory 0x5B82C0 walks gta3 → gta_int → the
# gta.dat IMGs and skips a name already registered; III/VC: the CDIMAGE
# archives come before gta3.img), so a model written into another archive is
# shadowed and the export «does nothing». Before, the whole selection went
# into ONE archive — the first model's. Now a model with its own IMG
# (img_target_file) always goes into it; the archive picked in the dialog gets
# only the models without one, else the IMG from settings (user decision, as
# in Max). A TXD / COL library shared by models of different archives goes
# whole into the archive(s) that already have it (else the first model's) —
# never two partial same-named files, also when one archive is skipped (busy /
# other game). A model left out of every archive → All → IMG writes no IDE/IPL.
#
# idm_img:18 (IMG-14). _export_report.txt is written next to the .blend, not
# into the game's models folder; an unsaved scene writes no file.
#
# core.img_routing is pure; the bpy-side glue of ops/img_ops.py
# (_export_routes, _img_report_path, the _targets closure of execute) is
# pulled out by AST and run on stand-ins; the wiring is checked on the AST.

import ast
import io
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMG_OPS = ROOT / "INU_tools" / "ops" / "img_ops.py"
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.img_routing import img_key, route_groups, shared_targets  # noqa: E402

# `from ..core.img_routing import …` inside _export_routes resolves through a
# minimal stub package (the addon __init__ needs Blender) — as in
# test_txd_platform / test_map_export_split.
_pkg_root = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
_pkg_root.__path__ = [str(ROOT / "INU_tools")]
_pkg_root.T = lambda s, *_a, **_kw: s

TREE = ast.parse(io.open(IMG_OPS, encoding="utf-8").read())
EXPORT = next(n for n in ast.walk(TREE)
              if isinstance(n, ast.ClassDef) and n.name == "GTATOOLS_OT_export_to_img")


def _method(name):
    return next(n for n in EXPORT.body
                if isinstance(n, ast.FunctionDef) and n.name == name)


EXECUTE = _method("execute")


def _module_funcs(names, ns):
    body = [n for n in TREE.body
            if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == set(names)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(IMG_OPS), "exec"), ns)
    return ns


def _img(tmp_path, name):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"VER2\0\0\0\0")
    return str(p)


def _calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id == name)
        or (isinstance(n.func, ast.Attribute) and n.func.attr == name))]


# ── core.img_routing ────────────────────────────────────────────────────

def test_each_model_goes_to_its_own_archive(tmp_path):
    a, b = _img(tmp_path, "a.img"), _img(tmp_path, "b.img")
    routes, none = route_groups({"house": a, "shop": b}, "")
    assert routes == {a: ["house"], b: ["shop"]} and none == []


def test_own_archive_wins_over_the_chosen_one(tmp_path):
    own, chosen = _img(tmp_path, "gta3.img"), _img(tmp_path, "mod.img")
    routes, none = route_groups({"house": own, "new": ""}, chosen)
    assert routes == {own: ["house"], chosen: ["new"]} and none == []


def test_missing_own_archive_counts_as_none(tmp_path):
    chosen = _img(tmp_path, "mod.img")
    routes, none = route_groups({"house": str(tmp_path / "deleted.img")}, chosen)
    assert routes == {chosen: ["house"]} and none == []


def test_no_archive_at_all_is_reported(tmp_path):
    assert route_groups({"house": "", "shop": ""}, "") == ({}, ["house", "shop"])
    assert route_groups({"house": ""}, str(tmp_path / "nope.img")) == ({}, ["house"])


def test_one_archive_in_different_spellings_is_one_route(tmp_path):
    a = _img(tmp_path, "models/gta3.img")
    (tmp_path / "models" / "sub").mkdir()
    alt = os.path.join(str(tmp_path), "models", "sub", "..", "gta3.img")
    own = {"house": a, "shop": alt}
    if os.name == "nt":
        own["barn"] = a.upper()
    routes, none = route_groups(own, "")
    assert routes == {os.path.normpath(a): list(own)} and none == []
    assert img_key(alt) == img_key(a)


@pytest.mark.parametrize("has, want", [
    ({"B"}, ["B"]),             # only the second model's archive has it
    (set(), ["A"]),             # nowhere yet → the first model's archive
    ({"A", "B"}, ["A", "B"]),   # in both → both, each merged with its own
])
def test_shared_entry_targets(has, want):
    assert shared_targets(["A", "B", "A"], lambda a: a in has) == want


# ── _export_routes (ops/img_ops.py) ─────────────────────────────────────

def _routes_env(settings_path="", choice="SELF", abspath=lambda p: p):
    ns = {"__name__": "INU_tools.ops.img_ops", "__package__": "INU_tools.ops",
          "os": os,
          "bpy": types.SimpleNamespace(path=types.SimpleNamespace(abspath=abspath))}
    _module_funcs({"_export_routes"}, ns)
    ctx = types.SimpleNamespace(scene=types.SimpleNamespace(
        inu_settings=types.SimpleNamespace(gtatools_img_path=settings_path,
                                           gtatools_export_img_target=choice)))
    return ns["_export_routes"], ctx


def _grp(tf=""):
    o = types.SimpleNamespace(inu=types.SimpleNamespace(img_target_file=tf))
    return {"DFF": o, "LOD": None, "COL": None}


def test_chosen_archive_gets_only_models_without_their_own(tmp_path):
    own, settings, chosen = (_img(tmp_path, n) for n in ("gta3.img", "s.img", "mod.img"))
    fn, ctx = _routes_env(settings, chosen)
    assert fn(ctx, {"house": _grp(own), "new": _grp()}) == (
        {own: ["house"], chosen: ["new"]}, [])


def test_self_means_settings_then_the_row_button_target(tmp_path):
    settings, active = _img(tmp_path, "s.img"), _img(tmp_path, "a.img")
    fn, ctx = _routes_env(settings)
    assert fn(ctx, {"new": _grp()}, target_img=active) == ({settings: ["new"]}, [])
    fn, ctx = _routes_env("")
    assert fn(ctx, {"new": _grp()}, target_img=active) == ({active: ["new"]}, [])
    assert fn(ctx, {"new": _grp()}) == ({}, ["new"])


def test_lod_only_group_and_the_want_filter(tmp_path):
    own = _img(tmp_path, "gta3.img")
    lod = types.SimpleNamespace(inu=types.SimpleNamespace(img_target_file=own))
    fn, ctx = _routes_env("")
    groups = {"x": {"DFF": None, "LOD": lod, "COL": None}, "off": _grp(own)}
    assert fn(ctx, groups, want=lambda b: b != "off") == ({own: ["x"]}, [])


def test_blend_relative_own_path_is_the_same_archive(tmp_path):
    own = _img(tmp_path, "models/gta3.img")
    rel = lambda p: str(tmp_path / p[2:]) if p.startswith("//") else p  # noqa: E731
    fn, ctx = _routes_env("", abspath=rel)
    routes, _ = fn(ctx, {"a": _grp("//models/gta3.img"), "b": _grp(own)})
    assert routes == {os.path.normpath(own): ["a", "b"]}


# ── _targets closure of execute: TXD / library shared by two archives ───

def _targets_env(arch_of_obj, arch_names, routes=None):
    # routes — the archives still written (a skipped one is dropped from it,
    # but its models stay in arch_of_obj); default: all of them.
    fn = next(n for n in EXECUTE.body
              if isinstance(n, ast.FunctionDef) and n.name == "_targets")
    ns = {"os": os, "T": lambda s: s, "shared_targets": shared_targets,
          "arch_of_obj": arch_of_obj, "arch_names": arch_names, "results": [],
          "routes": set(arch_of_obj.values()) if routes is None else routes,
          "_mixed": {}}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(IMG_OPS), "exec"), ns)
    return ns


def _o(name):
    return types.SimpleNamespace(name=name)


def test_shared_txd_goes_whole_where_it_already_is():
    g3, mod = os.path.join("g", "gta3.img"), os.path.join("g", "mod.img")
    ns = _targets_env({"a": g3, "b": mod}, {g3: {"a.dff"}, mod: {"shared.txd"}})
    assert ns["_targets"]("shared.txd", [_o("a"), _o("b")]) == [mod]
    # the «different archives» row is added after the write, for the
    # archives that really took it
    assert ns["_mixed"] == {"shared.txd": [mod]} and ns["results"] == []


def test_shared_txd_nowhere_goes_to_the_first_model_archive():
    ns = _targets_env({"a": "A.img", "b": "B.img"}, {"A.img": set(), "B.img": set()})
    assert ns["_targets"]("Shared.TXD", [_o("a"), _o("b")]) == ["A.img"]
    assert ns["_mixed"] == {"Shared.TXD": ["A.img"]}


def test_txd_of_one_archive_needs_no_warning():
    ns = _targets_env({"a": "A.img", "b": "A.img"}, {"A.img": {"x.txd"}})
    assert ns["_targets"]("x.txd", [_o("a"), _o("b")]) == ["A.img"]
    assert ns["results"] == [] and ns["_mixed"] == {}


def test_skipped_unread_archive_blocks_a_new_partial_copy():
    # b.img failed the pre-check before its directory was read: it may hold
    # shared.txd — a new one-model shared.txd in a.img would shadow it (SA:
    # a.img first) and leave b's models without textures
    ns = _targets_env({"a": "A.img", "b": "B.img"}, {"A.img": set()}, routes={"A.img"})
    assert ns["_targets"]("shared.txd", [_o("a"), _o("b")]) == []
    assert ns["results"] == ["shared.txd: не записан — пропущен архив B.img"]


def test_skipped_archive_known_without_the_entry_does_not_block():
    # b.img was read (then refused: other game) and has no shared.txd; the
    # «first model's archive» is taken among the written ones
    ns = _targets_env({"a": "A.img", "b": "B.img"}, {"A.img": set(), "B.img": set()},
                      routes={"A.img"})
    assert ns["_targets"]("shared.txd", [_o("b"), _o("a")]) == ["A.img"]
    assert ns["results"] == []


def test_entry_in_a_written_and_a_skipped_archive_goes_to_the_written():
    ns = _targets_env({"a": "A.img", "b": "B.img"}, {"A.img": {"shared.txd"}},
                      routes={"A.img"})
    assert ns["_targets"]("shared.txd", [_o("b"), _o("a")]) == ["A.img"]
    assert ns["_mixed"] == {"shared.txd": ["A.img"]}


# ── _img_report_path ────────────────────────────────────────────────────

def test_report_goes_next_to_the_blend():
    f = _module_funcs({"_img_report_path"}, {"os": os})["_img_report_path"]
    assert f("") is None and f(None) is None          # unsaved scene: no file
    assert f("X:/proj/scene.blend") == os.path.join("X:/proj", "_export_report.txt")


# ── wiring ──────────────────────────────────────────────────────────────

def test_one_writer_session_per_archive():
    loops = [f for f in ast.walk(EXECUTE) if isinstance(f, ast.For)
             and "arch_files" in ast.unparse(f.iter) and _calls(f, "ImgWriter")]
    assert loops, "ImgWriter must be opened per archive (for … in arch_files)"
    for w in _calls(EXECUTE, "ImgWriter"):
        assert any(lp.lineno <= w.lineno <= lp.end_lineno for lp in loops)
    # a busy / broken archive becomes a row, the next archive is still written
    for lp in loops:
        tries = [t for t in ast.walk(lp) if isinstance(t, ast.Try) and _calls(
            ast.Module(body=t.body, type_ignores=[]), "ImgWriter")]
        assert tries
        for t in tries:
            kinds = [ast.unparse(h.type) for h in t.handlers]
            assert kinds[0] == "PermissionError" and "OSError" in kinds[1]
            assert all(any(isinstance(s, ast.Continue) for s in h.body)
                       for h in t.handlers)


def test_routes_drive_invoke_draw_and_execute():
    for name in ("invoke", "draw", "execute"):
        assert _calls(_method(name), "_export_routes"), name


def test_invoke_keeps_the_remembered_choice():
    # the old invoke pre-selected the first model's archive in the list
    assigns = [n for n in ast.walk(_method("invoke")) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Attribute)
                       and t.attr == "gtatools_export_img_target" for t in n.targets)]
    assert assigns == []


def test_report_path_comes_from_the_blend():
    calls = _calls(EXECUTE, "_img_report_path")
    assert calls and all(ast.unparse(c.args[0]) == "bpy.data.filepath" for c in calls)
    assert "_export_report.txt" not in ast.unparse(EXECUTE)


def _unwritten_updates(node):
    return [c for c in _calls(node, "update")
            if ast.unparse(c.func.value) == "_export_unwritten"]


def test_models_left_out_of_every_archive_are_tracked():
    # module-level set, refilled by every execute: no archive, an archive that
    # failed the pre-check, an archive the writer could not open
    assert any(isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "_export_unwritten"
               and ast.unparse(n.value) == "set()" for n in TREE.body)
    clear = [c for c in _calls(EXECUTE, "clear")
             if ast.unparse(c.func.value) == "_export_unwritten"]
    ups = _unwritten_updates(EXECUTE)
    assert len(clear) == 1 and ups and all(clear[0].lineno < u.lineno for u in ups)
    assert "no_arch" in {ast.unparse(u.args[0]) for u in ups}
    writer_tries = [t for t in ast.walk(EXECUTE) if isinstance(t, ast.Try)
                    and _calls(ast.Module(body=t.body, type_ignores=[]), "ImgWriter")]
    assert writer_tries and all(_unwritten_updates(h) for t in writer_tries
                                for h in t.handlers)
    dels = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.Delete)
            and ast.unparse(n.targets[0]) == "routes[img_path]"]
    assert dels and any(u.lineno < dels[0].lineno for u in ups)


def test_all_to_img_writes_ide_ipl_only_if_every_model_got_into_the_img():
    tree = ast.parse((ROOT / "INU_tools" / "ops" / "inu_export.py").read_text(encoding="utf-8"))
    guards = [n for n in ast.walk(tree) if isinstance(n, ast.If)
              and ast.unparse(n.test) == "_export_unwritten"]
    assert len(guards) == 1
    g = guards[0]
    assert not _calls(ast.Module(body=g.body, type_ignores=[]), "_also_upsert_ide_ipl")
    assert _calls(ast.Module(body=g.body, type_ignores=[]), "report")
    assert _calls(ast.Module(body=g.orelse, type_ignores=[]), "_also_upsert_ide_ipl")


def test_busy_archive_is_found_before_the_build():
    # a running game lets the file be read, not written: probe for writing in
    # the pre-check, not only when ImgWriter opens it after DFF/TXD encoding
    probes = [c for c in _calls(EXECUTE, "open") if len(c.args) > 1
              and isinstance(c.args[1], ast.Constant) and c.args[1].value == "r+b"]
    assert probes
    first_build = min(c.lineno for c in _calls(EXECUTE, "build_dff_clump"))
    assert all(p.lineno < first_build for p in probes)


NEW_KEYS = {
    "IMG из настроек",
    "Модели без своего IMG — в архив из настроек аддона",
    "Куда писать при «Экспорт в IMG» модели без своего IMG: архив из настроек "
    "или конкретный архив из папки игры. Модель со своим IMG (img_target_file) "
    "всегда пишется в него — игра берёт первую копию. Обновляет запись, если "
    "модель там есть, иначе добавляет",
    "IMG для моделей без своего",
    "Без IMG-архива: {0} — выберите архив выше",
    "Модель со своим IMG пишется в него: игра берёт первую копию",
    "нет архива",
    "«{0}»: нет IMG-архива — выберите архив в окне",
    "{0}: модели из разных архивов — записан в {1}",
    "{0}: не записан — пропущен архив {1}",
    "IDE/IPL не записаны: часть моделей не попала в IMG",
}


def _t_keys(path):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    return {n.args[0].value for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "T" and n.args and isinstance(n.args[0], ast.Constant)}


def _lang(fname):
    tree = ast.parse((ROOT / "INU_tools" / "locale" / fname).read_text(encoding="utf-8"))
    d = next(n.value for n in tree.body if isinstance(n, ast.Assign))
    return {k.value for k in d.keys if isinstance(k, ast.Constant)}


def test_new_strings_are_used_and_translated():
    used = (_t_keys(IMG_OPS) | _t_keys(ROOT / "INU_tools" / "scene_settings.py")
            | _t_keys(ROOT / "INU_tools" / "ops" / "inu_export.py"))
    assert NEW_KEYS <= used
    assert NEW_KEYS <= _lang("eng.py")
    assert NEW_KEYS <= _lang("spa.py")
