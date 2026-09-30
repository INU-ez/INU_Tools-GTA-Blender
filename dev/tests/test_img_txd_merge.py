# Export to IMG: the TXD is merged with the archive's TXD, a LOD keeps its own
# TXD, obj.inu.txd_name is written back only after the archive was written.
#
# IMG-2 / BUG-7: <txd>.txd held only the textures of the selected models and
# writer.add replaced the archive entry — every other model of a shared TXD
# (district TXD; jester.txd = the car + its tuning parts) lost its textures.
# Now the archive's TXD is read first and merged (tools.txd_export.update_txd:
# same names replaced, the rest byte-for-byte, the base RW lib id kept) — as
# in Max.
# IMG-13 / CHK-B8: txd_name of the DFF AND the LOD was overwritten before
# anything was written (a refusal left it changed), and a vanilla LOD's own
# TXD (LODGSFreeway7_LAn → lanlod, the model → lanroad) became the model's.
# Now the LOD's textures go to its own TXD when it really is its own, and
# txd_name is written back only to objects whose TXD landed in the archive.
#
# ops/img_ops.py imports bpy at module level — the helpers AND the execute()
# closures are pulled out by AST and run on stand-in objects; the merge runs
# the real update_txd with bpy stubbed (as in test_txd_platform).

import ast
import io
import struct
import sys
import types
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMG_OPS = ROOT / "INU_tools" / "ops" / "img_ops.py"
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.model_classify import lod_has_own_txd  # noqa: E402

TREE = ast.parse(io.open(IMG_OPS, encoding="utf-8").read())
EXPORT = next(n for n in ast.walk(TREE)
              if isinstance(n, ast.ClassDef) and n.name == "GTATOOLS_OT_export_to_img")
EXECUTE = next(n for n in EXPORT.body
               if isinstance(n, ast.FunctionDef) and n.name == "execute")

HELPERS = {"_plan_txd_buckets", "_txd_writeback"}
CLOSURES = {"_plan_entry", "_inc_lod", "_lod_src", "_txd_for",
            "_lod_tex_src", "_lod_txd"}


def _env(entries=(), shared=False, objects=None, layer=None):
    """Namespace with the real helpers + execute() closures. Free names of the
    closures (self, plan_by_name, bpy, context…) become these globals."""
    objects = dict(objects or {})
    layer = objects if layer is None else {n: objects[n] for n in layer}
    ns = {
        "defaultdict": defaultdict,
        "lod_has_own_txd": lod_has_own_txd,
        "self": types.SimpleNamespace(shared_txd=shared,
                                      shared_txd_name="textures"),
        "plan_by_name": {e.model_name: e for e in entries},
        "bpy": types.SimpleNamespace(data=types.SimpleNamespace(objects=objects)),
        "context": types.SimpleNamespace(
            view_layer=types.SimpleNamespace(objects=layer)),
        "_lod_off_layer": [],
    }
    body = [n for n in TREE.body
            if isinstance(n, ast.FunctionDef) and n.name in HELPERS]
    body += [n for n in EXECUTE.body
             if isinstance(n, ast.FunctionDef) and n.name in CLOSURES]
    assert {n.name for n in body} == HELPERS | CLOSURES
    exec(compile(ast.Module(body=body, type_ignores=[]), str(IMG_OPS), "exec"), ns)
    return ns


def _plan(ns, groups):
    return ns["_plan_txd_buckets"](list(groups.items()), ns["_txd_for"],
                                   ns["_lod_tex_src"], ns["_lod_txd"])


def _obj(name, txd=""):
    return types.SimpleNamespace(name=name, inu=types.SimpleNamespace(txd_name=txd))


def _entry(model, txd, inc_lod=True, lod_name=""):
    return types.SimpleNamespace(model_name=model, txd_name=txd, include=True,
                                 inc_lod=inc_lod, lod_found=bool(lod_name),
                                 lod_name=lod_name)


def _apply(ns, buckets, written):
    for o, n in ns["_txd_writeback"](buckets, written):
        o.inu.txd_name = n


def _as_names(buckets):
    return {k: [o.name for o in v] for k, v in buckets.items()}


# ── lod_has_own_txd (core.model_classify) ───────────────────────────────

@pytest.mark.parametrize("lod, dff, own", [
    ("lanlod", "lanroad", True),
    ("", "myhouse", False),
    ("MyHouse", "myhouse", False),
    ("  lanlod ", "lanroad", True),
    ("lanlod", "", True),
    (None, "x", False),
])
def test_lod_has_own_txd(lod, dff, own):
    assert lod_has_own_txd(lod, dff) is own


# ── buckets + write-back (real closures of execute) ─────────────────────

def test_vanilla_lod_keeps_its_own_txd():
    dff = _obj("GSFreeway7_LAn", "lanroad")
    lod = _obj("LODGSFreeway7_LAn", "lanlod")
    ns = _env([_entry("GSFreeway7_LAn", "lanroad", lod_name=lod.name)],
              objects={dff.name: dff, lod.name: lod})
    b = _plan(ns, {"GSFreeway7_LAn": {"DFF": dff, "LOD": lod, "COL": None}})
    assert _as_names(b) == {"lanroad": [dff.name], "lanlod": [lod.name]}
    _apply(ns, b, {"lanroad.txd", "lanlod.txd"})
    assert (dff.inu.txd_name, lod.inu.txd_name) == ("lanroad", "lanlod")


def test_renamed_txd_follows_lod_that_shared_the_model_txd():
    dff, lod = _obj("myhouse", "myhouse"), _obj("LODmyhouse", "MyHouse")
    ns = _env([_entry("myhouse", "myhouse_tex", lod_name=lod.name)],
              objects={dff.name: dff, lod.name: lod})
    b = _plan(ns, {"myhouse": {"DFF": dff, "LOD": lod, "COL": None}})
    assert _as_names(b) == {"myhouse_tex": ["myhouse", "LODmyhouse"]}
    _apply(ns, b, {"myhouse_tex.txd"})
    assert dff.inu.txd_name == lod.inu.txd_name == "myhouse_tex"


def test_lod_without_txd_goes_to_model_txd():
    dff, lod = _obj("house", ""), _obj("LODhouse", "")
    ns = _env([_entry("house", "house", lod_name=lod.name)],
              objects={dff.name: dff, lod.name: lod})
    b = _plan(ns, {"house": {"DFF": dff, "LOD": lod, "COL": None}})
    assert _as_names(b) == {"house": ["house", "LODhouse"]}
    _apply(ns, b, {"house.txd"})
    assert dff.inu.txd_name == lod.inu.txd_name == "house"


def test_shared_mode_puts_everything_in_the_shared_txd():
    dff = _obj("GSFreeway7_LAn", "lanroad")
    lod = _obj("LODGSFreeway7_LAn", "lanlod")
    ns = _env([_entry("GSFreeway7_LAn", "lanroad", lod_name=lod.name)],
              shared=True, objects={dff.name: dff, lod.name: lod})
    b = _plan(ns, {"GSFreeway7_LAn": {"DFF": dff, "LOD": lod, "COL": None}})
    assert _as_names(b) == {"textures": [dff.name, lod.name]}
    _apply(ns, b, {"textures.txd"})
    assert dff.inu.txd_name == lod.inu.txd_name == "textures"


def test_stub_lod_is_not_a_second_source():
    dff = _obj("house", "house")
    ns = _env([_entry("house", "house", inc_lod=True)], objects={"house": dff})
    b = _plan(ns, {"house": {"DFF": dff, "LOD": None, "COL": None}})
    assert _as_names(b) == {"house": ["house"]}


def test_lod_only_group_takes_the_dialog_name():
    lod = _obj("LODGSFreeway7_LAn", "lanlod")
    ns = _env([_entry("GSFreeway7_LAn", "lanlod_new", lod_name=lod.name)],
              objects={lod.name: lod})
    b = _plan(ns, {"GSFreeway7_LAn": {"DFF": None, "LOD": lod, "COL": None}})
    assert _as_names(b) == {"lanlod_new": [lod.name]}
    _apply(ns, b, {"lanlod_new.txd"})
    assert lod.inu.txd_name == "lanlod_new"


def test_bucket_not_written_changes_nothing():
    dff, lod = _obj("myhouse", "myhouse"), _obj("LODmyhouse", "")
    ns = _env([_entry("myhouse", "myhouse_tex", lod_name=lod.name)],
              objects={dff.name: dff, lod.name: lod})
    b = _plan(ns, {"myhouse": {"DFF": dff, "LOD": lod, "COL": None}})
    _apply(ns, b, {"myhouse.dff"})          # TXD: no textures / error
    assert (dff.inu.txd_name, lod.inu.txd_name) == ("myhouse", "")


def test_all_to_img_empty_plan():
    # No plan row for the model (All → IMG now fills the plan, see
    # test_all_to_img_plan): model TXD = base name, the selected LOD with its
    # own TXD keeps it.
    dff = _obj("GSFreeway7_LAn", "lanroad")
    lod = _obj("LODGSFreeway7_LAn", "lanlod")
    ns = _env([], objects={dff.name: dff, lod.name: lod})
    b = _plan(ns, {"GSFreeway7_LAn": {"DFF": dff, "LOD": lod, "COL": None}})
    assert _as_names(b) == {"GSFreeway7_LAn": [dff.name], "lanlod": [lod.name]}
    _apply(ns, b, {"gsfreeway7_lan.txd", "lanlod.txd"})
    assert (dff.inu.txd_name, lod.inu.txd_name) == ("GSFreeway7_LAn", "lanlod")


def test_scene_lod_not_selected_gets_its_textures_written():
    # The LOD found by name (not selected) is written as .dff — before, its
    # textures went to no TXD at all.
    dff = _obj("GSFreeway7_LAn", "lanroad")
    lod = _obj("LODGSFreeway7_LAn", "lanlod")
    ns = _env([_entry("GSFreeway7_LAn", "lanroad", lod_name=lod.name)],
              objects={dff.name: dff, lod.name: lod})
    b = _plan(ns, {"GSFreeway7_LAn": {"DFF": dff, "LOD": None, "COL": None}})
    assert _as_names(b) == {"lanroad": [dff.name], "lanlod": [lod.name]}


def test_lod_outside_the_view_layer_is_skipped_and_reported():
    dff = _obj("GSFreeway7_LAn", "lanroad")
    lod = _obj("LODGSFreeway7_LAn", "lanlod")
    ns = _env([_entry("GSFreeway7_LAn", "lanroad", lod_name=lod.name)],
              objects={dff.name: dff, lod.name: lod}, layer=[dff.name])
    b = _plan(ns, {"GSFreeway7_LAn": {"DFF": dff, "LOD": None, "COL": None}})
    assert _as_names(b) == {"lanroad": [dff.name]}
    assert ns["_lod_off_layer"] == [lod.name]


def test_lod_unticked_but_selected_still_feeds_its_txd():
    dff = _obj("GSFreeway7_LAn", "lanroad")
    lod = _obj("LODGSFreeway7_LAn", "lanlod")
    ns = _env([_entry("GSFreeway7_LAn", "lanroad", inc_lod=False,
                      lod_name=lod.name)],
              objects={dff.name: dff, lod.name: lod})
    b = _plan(ns, {"GSFreeway7_LAn": {"DFF": dff, "LOD": lod, "COL": None}})
    assert _as_names(b) == {"lanroad": [dff.name], "lanlod": [lod.name]}


def test_bucket_names_are_case_insensitive():
    a, b_ = _obj("house_a", "House"), _obj("house_b", "house")
    ns = _env([_entry("house_a", "House"), _entry("house_b", "house")],
              objects={"house_a": a, "house_b": b_})
    b = _plan(ns, {"house_a": {"DFF": a, "LOD": None, "COL": None},
                   "house_b": {"DFF": b_, "LOD": None, "COL": None}})
    assert _as_names(b) == {"House": ["house_a", "house_b"]}


# ── wiring in execute() ─────────────────────────────────────────────────

def _img_writer_try():
    for n in ast.walk(EXECUTE):
        if isinstance(n, ast.Try) and any(
                isinstance(w, ast.With) and "ImgWriter" in ast.unparse(w.items[-1])
                for w in n.body):
            return n
    raise AssertionError("try/with ImgWriter not found")


def test_txd_name_written_only_after_the_archive():
    tr = _img_writer_try()
    assigns = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Attribute) and t.attr == "txd_name"
                       for t in n.targets)]
    assert assigns, "txd_name write-back vanished"
    for a in assigns:
        assert a.lineno > tr.end_lineno, (
            "txd_name must not change before the archive is written "
            f"(line {a.lineno})")
    calls = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "_txd_writeback"]
    assert calls and all(c.lineno > tr.end_lineno for c in calls)


def test_archive_txd_is_read_before_the_writer_and_merged():
    tr = _img_writer_try()
    readers = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.With)
               and "ImgReader" in ast.unparse(n.items[0])]
    assert readers and all(r.lineno < tr.lineno for r in readers)
    # merged before the writer session: all bytes first, then one ImgWriter
    # per archive (IMG-7)
    merge = {"update_txd", "export_txd", "split_txd_sections"}
    calls = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) in merge]
    assert {c.func.id for c in calls} == merge
    assert all(c.lineno < tr.lineno for c in calls)


# ── merge with the archive (real update_txd, bpy stubbed) ───────────────

def _ensure_bpy_stubs():
    bpy_mod = sys.modules.get('bpy')
    if bpy_mod is None:
        bpy_mod = types.ModuleType('bpy')
        sys.modules['bpy'] = bpy_mod
    if not hasattr(bpy_mod, 'types'):
        class _D:
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


@pytest.fixture(scope="module")
def tx():
    _ensure_bpy_stubs()
    pkg = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
    pkg.__path__ = [str(ROOT / "INU_tools")]
    pkg.T = lambda s, *_a, **_kw: s
    from INU_tools.tools import txd_export
    return txd_export


BASE_LIB, NEW_LIB = 0x1803FFFF, 0x1003FFFF


def _section(name, fill, lib=BASE_LIB):
    # Minimal 0x15 texture native: header + struct(platform, filter, name32).
    body = struct.pack('<II', 9, 0) + name.encode().ljust(32, b'\0') + bytes([fill]) * 40
    st = struct.pack('<III', 1, len(body), lib) + body
    return struct.pack('<III', 0x15, len(st), lib) + st


def _padded_archive_txd(tx, tmp_path):
    from INU_tools.core.img import ImgReader, ImgWriter, create_img, SECTOR
    src = tmp_path / "base.txd"
    tx._assemble_txd_file(str(src), BASE_LIB,
                          [('a', _section('a', 1)), ('b', _section('b', 2))])
    img = str(tmp_path / "x.img")
    create_img(img)
    with ImgWriter(img) as w:
        w.add('shared.txd', src.read_bytes())
    with ImgReader(img) as rd:
        raw = rd.read('SHARED.TXD')          # names are case-insensitive
    assert raw and len(raw) % SECTOR == 0     # sector padding comes along
    return raw


def test_archive_txd_with_padding_still_splits(tx, tmp_path):
    from INU_tools.core.txd import split_txd_sections
    lib, secs = split_txd_sections(_padded_archive_txd(tx, tmp_path))
    assert lib == BASE_LIB and [n for n, _ in secs] == ['a', 'b']


def test_update_txd_merges_into_the_archive_txd(tx, tmp_path, monkeypatch):
    from INU_tools.core.txd import split_txd_sections
    raw = _padded_archive_txd(tx, tmp_path)

    def fake_export(fp, ctx, sel, backend=None, **kw):
        tx._assemble_txd_file(fp, NEW_LIB, [('B', _section('B', 9, NEW_LIB)),
                                            ('c', _section('c', 3, NEW_LIB))])
        return {'FINISHED'}, 'ok', []

    monkeypatch.setattr(tx, 'export_txd', fake_export)
    p = tmp_path / "shared.txd"
    p.write_bytes(raw)
    res, msg, _ = tx.update_txd(str(p), types.SimpleNamespace(), True, backend='numpy')
    assert res == {'FINISHED'}
    lib, secs = split_txd_sections(p.read_bytes())
    assert lib == BASE_LIB                                   # archive lib id kept
    assert [n for n, _ in secs] == ['a', 'B', 'c']           # b replaced in place
    assert secs[0][1] == _section('a', 1)                    # untouched byte-for-byte
    assert secs[1][1] == _section('B', 9, NEW_LIB)


def test_update_txd_without_textures_leaves_the_file(tx, tmp_path, monkeypatch):
    raw = _padded_archive_txd(tx, tmp_path)
    monkeypatch.setattr(tx, 'export_txd', lambda *a, **k: (
        {'CANCELLED'}, "No textures found on selected objects", []))
    p = tmp_path / "shared.txd"
    p.write_bytes(raw)
    res, _msg, _ = tx.update_txd(str(p), types.SimpleNamespace(), True)
    assert res == {'CANCELLED'} and p.read_bytes() == raw


def test_not_a_txd_is_detected_up_front(tx):
    from INU_tools.core.txd import split_txd_sections
    assert split_txd_sections(b'')[0] is None
    assert split_txd_sections(b'\0' * 2048)[0] is None
