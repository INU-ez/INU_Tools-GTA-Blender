# «В IMG» status (obj.inu.img_target_file): set after Export to IMG, cleared
# after Remove from IMG.
#
# Before, only Import from IMG and Verify touched the field: a model just
# exported showed «Не в IMG» (and the trash button stayed off), a model just
# removed kept «В IMG (x.img)». Export now stamps the DFF and the real LOD
# whose entries were written (a stub LOD — a copy of the model — does not),
# plus the selected copies of those models (house.001…, the LOD of every
# placement) — the same objects Remove clears; Remove clears the copies
# whose entries left THEIR archive only.
#
# ops/img_ops.py imports bpy at module level — the helpers are pulled out by
# AST (same trick as test_material_color_export), the wiring is checked on
# the AST of the operators.

import ast
import io
import os
import types

ROOT =os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "INU_tools", "ops", "img_ops.py")

WANTED = {"_same_img", "_stamp_img_status", "_copy_jobs"}


def _load():
    tree = ast.parse(io.open(MODULE, encoding="utf-8").read())
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name in WANTED]
    bpy = types.SimpleNamespace(path=types.SimpleNamespace(abspath=lambda p: p))
    ns = {"os": os, "bpy": bpy}
    exec(compile(ast.Module(body=keep, type_ignores=[]), MODULE, "exec"), ns)
    return ns, tree


NS, TREE = _load()
stamp = NS["_stamp_img_status"]
same_img = NS["_same_img"]
copy_jobs = NS["_copy_jobs"]


def _obj(tf="", name="", type="MESH"):
    return types.SimpleNamespace(
        name=name, type=type,
        inu=types.SimpleNamespace(img_target_file=tf))


# ── helpers ─────────────────────────────────────────────────────────────

def test_stamp_sets_only_written_entries():
    dff, lod, failed = _obj(), _obj("C:/g/gta3.img"), _obj()
    jobs = [("House.dff", dff), ("LODhouse.dff", lod), ("broken.dff", failed)]
    # writer.add succeeded for these (names kept lower-case by the operator)
    written = {"house.dff", "lodhouse.dff", "house.col", "house.txd"}
    stamp(jobs, written, "C:/g/custom.img")
    assert dff.inu.img_target_file == "C:/g/custom.img"
    assert lod.inu.img_target_file == "C:/g/custom.img"
    assert failed.inu.img_target_file == ""      # encode / add failed


def test_stamp_leaves_objects_without_a_job():
    # The stub LOD is the model itself written under the LOD name — it is not
    # a job, so nothing but the DFF entry stamps the model.
    model, not_selected = _obj(), _obj("C:/g/gta3.img")
    stamp([("house.dff", model)], {"house.dff", "lodhouse.dff"},
          "C:/g/custom.img")
    assert model.inu.img_target_file == "C:/g/custom.img"
    assert not_selected.inu.img_target_file == "C:/g/gta3.img"


def test_same_img_resolves_blend_relative_paths():
    old = NS["bpy"].path.abspath
    NS["bpy"].path.abspath = (
        lambda p: "/proj/" + p[2:] if p.startswith("//") else p)
    try:
        assert same_img("//models/gta3.img", "/proj/models/gta3.img")
        assert not same_img("//models/gta3.img", "/proj/gta3.img")
    finally:
        NS["bpy"].path.abspath = old
    assert not same_img("", "C:/g/gta3.img")
    assert not same_img("C:/g/gta3.img", "")


# Fake classifier / LOD namer for _copy_jobs: name → (type, base) as the
# addon's get_model_type would give for the name without its .001 suffix.
_TYPES = {"house": ("DFF", "house"), "house.001": ("DFF", "house"),
          "house_.002": ("DFF", "house_"), "lodhouse": ("LOD", "house"),
          "lodhouse.001": ("LOD", "house"), "house_col": ("COL", "house"),
          "barn": ("DFF", "barn"), "junk": (None, None)}


def _classify(o):
    return _TYPES.get(o.name, (None, None))


def _lod_name(o, base):
    return getattr(o, "ide_last_name", "") or "LOD" + base


def test_copy_jobs_maps_copies_to_their_entry():
    objs = [_obj(name=n) for n in _TYPES] + [_obj(name="house", type="EMPTY")]
    jobs = [(fn, o.name) for fn, o in copy_jobs(objs, _classify, _lod_name)]
    assert jobs == [("house.dff", "house"), ("house.dff", "house.001"),
                    ("house.dff", "house_.002"),       # base as Export writes it
                    ("LODhouse.dff", "lodhouse"),
                    ("LODhouse.dff", "lodhouse.001"),
                    ("barn.dff", "barn")]              # COL / unknown / EMPTY: none


def test_copies_stamped_only_when_their_entry_was_written():
    objs = {n: _obj(name=n) for n in ("house", "house.001", "lodhouse",
                                      "lodhouse.001", "barn")}
    # house.dff and its real LOD written; barn excluded in the dialog
    stamp(copy_jobs(objs.values(), _classify, _lod_name),
          {"house.dff", "house.txd", "lodhouse.dff"}, "C:/g/custom.img")
    for n in ("house", "house.001", "lodhouse", "lodhouse.001"):
        assert objs[n].inu.img_target_file == "C:/g/custom.img", n
    assert objs["barn"].inu.img_target_file == ""


def test_copies_of_a_named_lod_follow_its_ide_name():
    lod = _obj(name="lodhouse")
    lod.ide_last_name = "house_lod"
    stamp(copy_jobs([lod], _classify, _lod_name), {"lodhouse.dff"},
          "C:/g/custom.img")
    assert lod.inu.img_target_file == ""               # its entry: house_lod.dff
    stamp(copy_jobs([lod], _classify, _lod_name), {"house_lod.dff"},
          "C:/g/custom.img")
    assert lod.inu.img_target_file == "C:/g/custom.img"


# ── wiring in the operators ─────────────────────────────────────────────

def _method(cls_name, name):
    for node in ast.walk(TREE):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return fn
    raise AssertionError(f"{cls_name}.{name} not found")


def _calls(fn, name):
    return [n for n in ast.walk(fn) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id == name)
        or (isinstance(n.func, ast.Attribute) and n.func.attr == name))]


def test_export_stamps_after_the_archive_is_closed():
    fn = _method("GTATOOLS_OT_export_to_img", "execute")
    stamps = _calls(fn, "_stamp_img_status")
    assert stamps
    # the try that holds `with ImgWriter(...)`: its __exit__ writes the
    # directory, and PermissionError / other errors return CANCELLED — the
    # status must be set only after it, never inside
    tries = [t for t in ast.walk(fn) if isinstance(t, ast.Try)
             and _calls(ast.Module(body=t.body, type_ignores=[]), "ImgWriter")]
    assert tries
    for s in stamps:
        assert any(s.lineno > t.end_lineno for t in tries)
        assert not any(t.lineno <= s.lineno <= t.end_lineno for t in tries)


def test_export_collects_written_names():
    fn = _method("GTATOOLS_OT_export_to_img", "execute")
    adds = [c for c in _calls(fn, "add")
            if isinstance(c.func.value, ast.Name) and c.func.value.id == "written"]
    assert adds


def test_export_stamps_selected_copies_too():
    # Remove clears every selected copy — Export must stamp them as well,
    # or the active house.001 shows «Не в IMG» right after its Export.
    fn = _method("GTATOOLS_OT_export_to_img", "execute")
    copies = _calls(fn, "_copy_jobs")
    stamps = _calls(fn, "_stamp_img_status")
    assert copies and stamps
    assert max(c.lineno for c in copies) < min(s.lineno for s in stamps)


def test_remove_clears_status():
    # Either through the helper or inline (`… .img_target_file = ''`).
    fn = _method("GTATOOLS_OT_remove_from_img", "execute")
    inline = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
              and isinstance(n.value, ast.Constant) and n.value.value == ''
              and any(isinstance(t, ast.Attribute)
                      and t.attr == "img_target_file" for t in n.targets)]
    assert _calls(fn, "_clear_img_status") or inline
