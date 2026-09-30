# Export to IMG: коллизия модели — в свою библиотеку архива, со сферами/боксами.
#
# IMG-3: a model whose COL record already lies in a .col of the archive
# (countn2.col, veh_mods.col, an old <base>.col) gets that record replaced IN
# PLACE — the library's other models stay byte for byte, the record keeps its
# model_id. Before, a second <base>.col was written next to it (both records
# are loaded, the last streamed slot wins — SA 0x5B5000 / 0x538440, reVC
# FileLoader.cpp), and the Export All library mode replaced the whole
# <name>.col with the selected models only. The sector padding after the
# records is dropped: VC refuses a library whose tail past the records is
# ≥ 2056 bytes (reVC CFileLoader::LoadCollisionFile), and a record appended
# after the padding is never read.
# IMG-4: <base>_sphere_N / <base>_box_N empties (the names col_import gives)
# go into the model's COL with its mesh — they were dropped. A Blender .NNN
# suffix counts only when it is the COL mesh's own (second import of a COL).
#
# ops/img_ops.py imports bpy at module level — the helpers are pulled out by
# AST and run on stand-ins; core.col / core.col_library are real.

import ast
import io
import struct
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMG_OPS = ROOT / "INU_tools" / "ops" / "img_ops.py"
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.col import Bounds, ColModel, ColSphere, Vec3, read_col, write_col  # noqa: E402
from core.col_library import col_chunks  # noqa: E402
from core.img import SECTOR  # noqa: E402

# `from ..core.col_library import col_splice` inside _col_lib_put resolves
# through a minimal stub package (the addon __init__ needs Blender).
_pkg_root = sys.modules.setdefault('INU_tools', types.ModuleType('INU_tools'))
_pkg_root.__path__ = [str(ROOT / "INU_tools")]

TREE = ast.parse(io.open(IMG_OPS, encoding="utf-8").read())
EXPORT = next(n for n in ast.walk(TREE)
              if isinstance(n, ast.ClassDef) and n.name == "GTATOOLS_OT_export_to_img")


def _method(name):
    return next(n for n in EXPORT.body
                if isinstance(n, ast.FunctionDef) and n.name == name)


EXECUTE = _method("execute")

_NS = {"__name__": "INU_tools.ops.img_ops", "__package__": "INU_tools.ops"}
_body = [n for n in TREE.body if isinstance(n, ast.FunctionDef)
         and n.name in {"_col_prim_index", "_col_prims_of", "_col_lib_put"}]
assert len(_body) == 3
exec(compile(ast.Module(body=_body, type_ignores=[]), str(IMG_OPS), "exec"), _NS)
_col_prim_index = _NS["_col_prim_index"]
_col_prims_of = _NS["_col_prims_of"]
_col_lib_put = _NS["_col_lib_put"]


def _calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id == name)
        or (isinstance(n.func, ast.Attribute) and n.func.attr == name))]


# ── сферы/боксы модели ──────────────────────────────────────────────────

def _o(name, kind="EMPTY", display="SPHERE"):
    return types.SimpleNamespace(name=name, type=kind, empty_display_type=display)


SCENE = [
    _o("x_sphere_0"), _o("X_BOX_1", display="CUBE"),     # import names, any case
    _o("x_sphere_0.001"),                                # second import
    _o("xy_sphere_0"),                                   # another model
    _o("x_sphere"), _o("x_sphere_2", display="ARROWS"),  # not a primitive
    _o("x_box_3", kind="MESH", display=None),
    _o("lamp_box_0", display="CUBE"),
]


def _names(objs):
    return sorted(o.name for o in objs)


def test_prims_of_the_model_are_found_by_import_names():
    idx = _col_prim_index(SCENE)
    assert _names(_col_prims_of(idx, "x", "x_COL")) == ["X_BOX_1", "x_sphere_0"]
    assert _names(_col_prims_of(idx, "X", "x_col")) == ["X_BOX_1", "x_sphere_0"]
    assert _names(_col_prims_of(idx, "xy", "")) == ["xy_sphere_0"]
    assert _col_prims_of(idx, "house", "house_COL") == []


def test_duplicate_suffix_only_with_the_same_col_mesh():
    idx = _col_prim_index(SCENE)
    # a second import of x.col: x_COL.001 + x_sphere_0.001 — not doubled
    assert _names(_col_prims_of(idx, "x", "x_COL.001")) == ["x_sphere_0.001"]
    # no COL mesh (spheres/boxes only): the unsuffixed ones
    assert _names(_col_prims_of(idx, "x", "")) == ["X_BOX_1", "x_sphere_0"]
    assert _names(_col_prims_of(idx, "lamp", "")) == ["lamp_box_0"]


# ── запись в библиотеку архива ─────────────────────────────────────────

def _col(name, mid, spheres=0, version=3):
    m = ColModel(version=version, model_name=name, model_id=mid, bounds=Bounds(
        center=Vec3(0.0, 0.0, 0.0), radius=2.0,
        bb_min=Vec3(-1.0, -1.0, 0.0), bb_max=Vec3(1.0, 1.0, 1.0)))
    for i in range(spheres):
        m.spheres.append(ColSphere(center=Vec3(float(i), 0.0, 0.0), radius=1.0))
    return m


def _make(name, spheres, version=3):
    def make(mid):
        return write_col([_col(name, mid, spheres, version)])
    return make


def _pad(data):   # ImgReader.read / ImgWriter.add: whole sectors
    return data + b"\x00" * (-len(data) % SECTOR)


def _vc_loads(entry):
    """reVC CFileLoader::LoadCollisionFile over a streamed (sector-padded)
    entry: records up to the first non-'COLL' header, then size-8 < 2048."""
    size, pos = len(entry), 0
    while size > 8:
        if entry[pos:pos + 4] != b"COLL":
            return size - 8 < SECTOR
        rest = struct.unpack_from("<I", entry, pos + 4)[0]
        size -= 8 + rest
        pos += 8 + rest
    return True


def test_record_replaced_in_place_others_byte_for_byte():
    a, b, c = (write_col([_col(n, i)]) for n, i in (("a", 11), ("b", 12), ("c", 13)))
    out, n = _col_lib_put(_pad(a + b + c), "B", _make("b", 1))
    assert n == 1
    assert out.startswith(a) and out.endswith(c)
    assert [(m.model_name, m.model_id, len(m.spheres)) for m in read_col(out)] == [
        ("a", 11, 0), ("b", 12, 1), ("c", 13, 0)]          # model_id kept
    assert len(out) == col_chunks(out)[-1][1]             # no padding tail


def test_vc_still_loads_a_grown_library():
    recs = [write_col([_col(n, i, version=1)]) for n, i in (("a", 1), ("b", 2), ("c", 3))]
    lib = _pad(b"".join(recs))
    out, _n = _col_lib_put(lib, "b", _make("b", 1, version=1))   # +20 bytes
    assert _vc_loads(_pad(out))
    # keeping the old padding (Max col_splice) → tail ≥ 2056 → VC drops it all
    assert not _vc_loads(_pad(out + lib[len(b"".join(recs)):]))


def test_new_model_is_appended_after_the_records_not_the_padding():
    a, b = write_col([_col("a", 1)]), write_col([_col("b", 2)])
    out, n = _col_lib_put(_pad(a + b), "d", _make("d", 0))
    assert n == 0
    assert out.startswith(a + b)
    assert [ch[2] for ch in col_chunks(out)] == ["a", "b", "d"]
    assert [m.model_id for m in read_col(out)] == [1, 2, 0]


def test_new_library_from_nothing():
    out, n = _col_lib_put(b"", "d", _make("d", 1))
    assert (out, n) == (_make("d", 1)(0), 0)


# ── разводка в операторе ────────────────────────────────────────────────

def test_col_libraries_are_read_before_anything_is_written():
    idx = _calls(EXECUTE, "col_index")
    assert idx
    readers = [w for w in ast.walk(EXECUTE) if isinstance(w, ast.With)
               and any(_calls(i.context_expr, "ImgReader") for i in w.items)]
    assert all(any(w.lineno <= c.lineno <= w.end_lineno for w in readers) for c in idx)
    first_write = min(c.lineno for c in _calls(EXECUTE, "ImgWriter"))
    assert all(c.lineno < first_write for c in idx)


def test_library_is_edited_not_replaced():
    # the old library branch: export_col_library of the selected models only,
    # with the COL meshes moved to (0,0,0) meanwhile
    assert _calls(EXECUTE, "export_col_library") == []
    assert not [n for n in ast.walk(EXECUTE) if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Attribute) and t.attr == "location" for t in n.targets)]
    # own library of the model + the Export All library
    assert len(_calls(EXECUTE, "_col_lib_put")) >= 2


def test_lod_name_only_for_an_exported_lod():
    # III/VC: _lod_file walks the scene (map_link.lod_name_taken) — every
    # call sits under an _inc_lod check, and the name is kept per model.
    parent = {}
    for node in ast.walk(EXECUTE):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    calls = [c for c in _calls(EXECUTE, "_lod_file")
             if isinstance(c.func, ast.Name)]
    assert len(calls) >= 3
    for c in calls:
        node, guarded = c, False
        while node in parent and not guarded:
            node = parent[node]
            guarded = (isinstance(node, (ast.If, ast.IfExp))
                       and bool(_calls(node.test, "_inc_lod")))
        assert guarded, c.lineno
    lod_file = next(n for n in ast.walk(EXECUTE) if isinstance(n, ast.FunctionDef)
                    and n.name == "_lod_file")
    src = ast.unparse(lod_file)
    assert "_lod_names[base]" in src and "if base in _lod_names" in src


def test_prims_reach_build_col_model_and_the_dialog():
    # the dialog rows come from fill_export_plan (invoke and All → IMG)
    fill = next(n for n in TREE.body if isinstance(n, ast.FunctionDef)
                and n.name == "fill_export_plan")
    assert _calls(_method("invoke"), "fill_export_plan")
    for fn in (fill, EXECUTE):
        assert _calls(fn, "_col_prim_index") and _calls(fn, "_col_prims_of")
    srcs = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.Assign)
            and ast.unparse(n.targets[0]) == "col_src"]
    assert srcs and all(_calls(n.value, "_col_prims_of") for n in srcs)
    assert all(ast.unparse(c.args[0]) == "col_src"
               for c in _calls(EXECUTE, "build_col_model"))
    found = [n for n in ast.walk(fill) if isinstance(n, ast.Assign)
             and ast.unparse(n.targets[0]) == "entry.col_found"]
    assert found and all("prims" in ast.unparse(n.value) for n in found)
    # spheres/boxes alone: shown, but written only by an explicit tick — with
    # no COL mesh they go out by raw location, and Import from IMG puts them
    # at the model's place in the world (the library record would move away)
    tick = [n for n in ast.walk(fill) if isinstance(n, ast.Assign)
            and ast.unparse(n.targets[0]) == "entry.inc_col"]
    assert tick and all("bool(col_obj)" in ast.unparse(n.value)
                        and "col_found" not in ast.unparse(n.value)
                        and "prims" not in ast.unparse(n.value) for n in tick)


def test_library_targets_count_the_models_already_in_it():
    # The Export All library lands in the FIRST model's archive, so it holds
    # models of other archives too. Where it already lies is looked up over
    # the models found in their archive as well: counting only the models
    # missing there made the second export of such a model write a second,
    # partial <name>.col into its own archive (the game reads one of the two).
    # Nowhere yet — the archive of the first model that goes into it.
    calls = [c for c in _calls(EXECUTE, "_targets")
             if ast.unparse(c.args[0]) == "col_library_name + '.col'"]
    assert calls and all(ast.unparse(c.args[1]) == "_lib_users + _lib_in" for c in calls)
    found = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.If)
             and "col_idx" in ast.unparse(n.test)
             and any("_lib_in.append" in ast.unparse(s) for s in n.body)]
    assert found


def test_own_col_without_the_record_is_appended_not_replaced():
    # <model>.col already in the archive but holding other models only (a
    # library named after the model): the record is appended to it — a whole
    # file replace dropped the others, and with another exported model's
    # record in that file the two writes of it lost this model's collision.
    assert [n for n in ast.walk(EXECUTE) if isinstance(n, ast.Assign)
            and ast.unparse(n.targets[0]) == "_where"
            and ast.unparse(n.value) == "[base_name + '.col']"]
    # its bytes are read up front with the libraries (before any write)
    reads = [n for n in ast.walk(EXECUTE) if isinstance(n, ast.AugAssign)
             and ast.unparse(n.target) == "_need" and "arch_names" in ast.unparse(n.value)]
    assert reads
    first_write = min(c.lineno for c in _calls(EXECUTE, "ImgWriter"))
    assert all(n.lineno < first_write for n in reads)


def _lang(fname):
    tree = ast.parse((ROOT / "INU_tools" / "locale" / fname).read_text(encoding="utf-8"))
    d = next(n.value for n in tree.body if isinstance(n, ast.Assign))
    return {k.value for k in d.keys if isinstance(k, ast.Constant)}


def test_dialog_counts_spheres_and_boxes():
    key = "сферы/боксы ({0})"
    t_keys = {c.args[0].value for c in _calls(_method("draw"), "T")
              if c.args and isinstance(c.args[0], ast.Constant)}
    assert key in t_keys
    assert key in _lang("eng.py") and key in _lang("spa.py")
    init = ast.parse((ROOT / "INU_tools" / "__init__.py").read_text(encoding="utf-8"))
    entry = next(n for n in ast.walk(init)
                 if isinstance(n, ast.ClassDef) and n.name == "GTATOOLS_TxdExportEntry")
    assert "col_prims" in {s.target.id for s in entry.body
                           if isinstance(s, ast.AnnAssign)}


@pytest.mark.parametrize("name", ["x_sphere_0", "x_box_12.003"])
def test_prim_pattern_matches_the_importer(name):
    # col_import._create_sphere / _create_box: f"{model_name}_sphere_{i}"
    idx = _col_prim_index([_o(name, display="CUBE")])
    assert list(idx) == ["x"]
