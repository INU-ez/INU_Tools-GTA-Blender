# Remove from IMG: что удаляется из каждого архива (core/img_remove.py),
# записи COL-библиотек (core/col_library.py), IDE игры (core/gta_dat.py).
#
# Главное: TXD уходит, только если он больше никому не нужен (ванильный
# blade.txd нужен 10 деталям тюнинга); LOD — только выделенный сам (один LOD
# бывает у нескольких моделей); выделенный LOD не трогает DFF, TXD и COL своей
# модели; запись коллизии вырезается из библиотеки, опустевшая удаляется.
# Оператор (ops/img_ops.py) — по AST и целиком на заглушке bpy.

import ast
import importlib
import importlib.util
import io
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core import img_remove  # noqa: E402
from core.col import Bounds, ColModel, ColSphere, Vec3, read_col, write_col  # noqa: E402
from core.col_library import col_chunks, col_index, col_splice  # noqa: E402
from core.gta_dat import game_ide_paths  # noqa: E402
from core.img import (  # noqa: E402
    SECTOR, ImgReader, ImgWriter, create_img, read_directory)
from core.img_remove import (  # noqa: E402
    remove_entries, remove_plan, scene_txd_users, txd_users)

OPS = ROOT / "INU_tools" / "ops" / "img_ops.py"
A = "C:/g/models/gta3.img"          # only a key for the plan


def _col(name, mid, spheres=0):
    m = ColModel(version=3, model_name=name, model_id=mid, bounds=Bounds(
        center=Vec3(0.0, 0.0, 0.0), radius=2.0,
        bb_min=Vec3(-1.0, -1.0, 0.0), bb_max=Vec3(1.0, 1.0, 1.0)))
    for i in range(spheres):
        m.spheres.append(ColSphere(center=Vec3(float(i), 0.0, 0.0), radius=1.0))
    return write_col([m])


def _pad(data):
    return data + b"\x00" * (-len(data) % SECTOR)


def _archive(tmp_path, version, files):
    p = str(tmp_path / "test.img")
    create_img(p, version=version)
    with ImgWriter(p, version=version) as w:
        for name, data in files.items():
            w.add(name, data)
    return p


def _names(*entries):
    return {e.lower(): e for e in entries}


def _plan(parts, entries, col_idx=None, users=None):
    for p in parts:
        p.setdefault("arch", A)
    return remove_plan(parts, {A: _names(*entries)}, {A: col_idx or {}},
                       users or {})[A]


# ── план: LOD, TXD, COL ───────────────────────────────────────────

def test_dff_only_keeps_its_lod():
    t = _plan([dict(kind="dff", name="house", txd="house", lod="LODhouse")],
              ["house.dff", "house.txd", "lodhouse.dff", "houses.col"],
              col_idx={"house": ["houses.col"], "lodhouse": ["houses.col"]})
    assert t["entries"] == ["house.dff", "house.txd"]
    assert t["libs"] == {"houses.col": ["house"]}
    assert t["kept_lod"] == ["LODhouse"]


def test_lod_selected_with_its_model_is_removed_not_reported():
    t = _plan([dict(kind="dff", name="house", txd="house", lod="LODhouse"),
               dict(kind="lod", name="LODhouse", txd="house")],
              ["house.dff", "house.txd", "lodhouse.dff"])
    assert t["entries"] == ["house.dff", "house.txd", "lodhouse.dff"]
    assert t["kept_lod"] == []


def test_lod_only_leaves_its_model_alone():
    # Баг Max: выделен только LOD → уходили DFF и TXD основной модели.
    users = scene_txd_users([("house", "")], [("LODhouse", "", "house")])
    t = _plan([dict(kind="lod", name="LODhouse", txd="house")],
              ["house.dff", "house.txd", "lodhouse.dff", "house.col"],
              col_idx={"house": ["house.col"]}, users=users)
    assert t["entries"] == ["lodhouse.dff"]
    assert t["libs"] == {}
    assert [k[0] for k in t["kept_txd"]] == ["house.txd"]


def test_owner_with_empty_txd_name_in_scene_keeps_txd():
    # Модель в другом архиве и не в IDE — нужна ли её TXD, знает только сцена
    # (txd_name пуст → TXD = имя модели, как пишет Export to IMG).
    users = scene_txd_users([("house", "")], [("LODhouse", "", "house")])
    t = _plan([dict(kind="lod", name="LODhouse", txd="house")],
              ["lodhouse.dff", "house.txd"], users=users)
    assert t["entries"] == ["lodhouse.dff"]
    assert t["kept_txd"] == [("house.txd", "house", 1)]


def test_shared_txd_kept_own_txd_removed():
    # Ваниль SA: blade.txd — у blade и деталей тюнинга из veh_mods.ide.
    users = {"blade": {"blade", "rf_lr_bl2", "exh_lr_bl1"}, "mycar": {"mycar"}}
    t = _plan([dict(kind="dff", name="blade", txd="blade"),
               dict(kind="dff", name="mycar", txd="mycar")],
              ["blade.dff", "blade.txd", "mycar.dff", "mycar.txd"], users=users)
    assert t["entries"] == ["blade.dff", "mycar.dff", "mycar.txd"]
    assert t["kept_txd"] == [("blade.txd", "exh_lr_bl1", 2)]


def test_txd_of_models_removed_together_goes_once():
    users = {"common": {"a", "b"}}
    t = _plan([dict(kind="dff", name="a", txd="common"),
               dict(kind="dff", name="b", txd="common")],
              ["a.dff", "b.dff", "common.txd"], users=users)
    assert t["entries"] == ["a.dff", "common.txd", "b.dff"]
    assert t["kept_txd"] == []


def test_same_named_model_left_in_archive_keeps_txd():
    # Никто в IDE/сцене не знает про house, но house.dff остаётся в архиве.
    t = _plan([dict(kind="lod", name="LODhouse", txd="house")],
              ["house.dff", "house.txd", "lodhouse.dff"])
    assert t["entries"] == ["lodhouse.dff"]
    assert t["kept_txd"] == [("house.txd", "house", 1)]


def test_col_mesh_alone_takes_only_its_records():
    t = _plan([dict(kind="col", name="house")],
              ["house.dff", "house.txd", "lib.col"], col_idx={"house": ["lib.col"]})
    assert t["entries"] == []
    assert t["libs"] == {"lib.col": ["house"]}


def test_entry_names_keep_archive_spelling():
    t = _plan([dict(kind="dff", name="house", txd="house")],
              ["HOUSE.DFF", "House.txd"])
    assert t["entries"] == ["HOUSE.DFF", "House.txd"]


def test_unread_archive_is_skipped():
    plan = remove_plan([dict(kind="dff", arch="B.img", name="x", txd="x")],
                       {A: _names("x.dff")}, {}, {})
    assert plan == {}


def test_model_not_in_its_archive_is_left_whole():
    # Статус «В IMG» устарел: DFF в архиве нет — его TXD и коллизия могут
    # служить модели там, где она лежит на самом деле.
    users = {"shared": {"ghost", "real"}}
    t = _plan([dict(kind="dff", name="ghost", txd="shared", lod="LODghost"),
               dict(kind="dff", name="real", txd="shared")],
              ["real.dff", "shared.txd", "lodghost.dff", "lib.col"],
              col_idx={"ghost": ["lib.col"]}, users=users)
    assert t["missing"] == ["ghost"]
    assert t["entries"] == ["real.dff"]
    assert t["libs"] == {}
    assert t["kept_txd"] == [("shared.txd", "ghost", 1)]
    assert t["kept_lod"] == []


def test_col_mesh_selected_with_missing_model_is_left_too():
    # Рамкой выделены модель с устаревшим статусом и её COL-меш: коллизию
    # игра ищет по имени во всех архивах — она нужна модели там, где та лежит.
    t = _plan([dict(kind="dff", name="house", txd="house"),
               dict(kind="col", name="house")],
              ["shed.dff", "houses.col"], col_idx={"house": ["houses.col"]})
    assert t["missing"] == ["house"]
    assert t["entries"] == [] and t["libs"] == {}


# ── кто использует TXD ────────────────────────────────────────────

IDE = """\
# comment
objs
100, house, house, 299, 0
101, LODhouse, lod_tex, 1000, 0
1103, rf_lr_bl2, blade, 50, 0
end
anim
3100, animmodel, anim_tex, animfile, 100, 0
end
cars
536, blade, blade, car, BLADE, BLADE, null, executive, 10, 0, 0, -1, 0.7, 0.7, 1
end
peds
7, male01, male01, CIVMALE, STAT_STREET_GUY, man, 1983, 1, null, 9, 9, PED_TYPE_GEN, VOICE_GEN_MBDYRIC, VOICE_GEN_MBDYRIC
end
weap
321, gun_dildo1, gun_dildo1, null, 1, 50, 0
end
hier
3000, cutobj01, cut_tex
end
txdp
child_tex, parent_tex
end
"""


def test_txd_users_reads_every_txd_section(tmp_path):
    p = tmp_path / "x.ide"
    p.write_text(IDE, encoding="utf-8")
    users, bad = txd_users([str(p), str(p), str(tmp_path / "missing.ide"), ""])
    assert bad == []
    assert users["blade"] == {"blade", "rf_lr_bl2"}
    assert users["lod_tex"] == {"lodhouse"}
    assert users["anim_tex"] == {"animmodel"}
    assert users["male01"] == {"male01"}
    assert users["gun_dildo1"] == {"gun_dildo1"}
    assert users["cut_tex"] == {"cutobj01"}
    assert users["parent_tex"] == {"txdp child_tex"}   # ребёнок грузит родителя


def test_txd_users_reports_unreadable_ide(tmp_path, monkeypatch):
    good, broken = tmp_path / "a.ide", tmp_path / "b.ide"
    good.write_text("objs\n1, a, a_tex, 100, 0\nend\n", encoding="utf-8")
    broken.write_text("", encoding="utf-8")
    real = img_remove.read_ide

    def fake(path):
        if path == str(broken):
            raise OSError("locked")
        return real(path)

    monkeypatch.setattr(img_remove, "read_ide", fake)
    users, bad = txd_users([str(good), str(broken)])
    assert users == {"a_tex": {"a"}}
    assert bad == [str(broken)]


def test_scene_txd_users_rule():
    users = scene_txd_users(
        [("house", ""), ("shop", "shops"), ("house", "other")],
        [("LODhouse", "", "house"), ("LODshop", "lod_tex", "shop"),
         ("LODlost", "", "")])
    assert users == {"house": {"house", "lodhouse"}, "shops": {"shop"},
                     "other": {"house"}, "lod_tex": {"lodshop"}}


# ── COL-библиотеки ────────────────────────────────────────────────

def test_col_splice_cuts_record_others_byte_for_byte():
    a, b, c = _col("a", 11), _col("b", 12, spheres=1), _col("c", 13)
    out, n, left = col_splice(_pad(a + b + c), "B", lambda _mid: None)
    assert (n, left) == (1, 2)
    assert out == a + c                       # хвост паддинга не остаётся
    assert [ch[2] for ch in col_chunks(out)] == ["a", "c"]


def test_col_splice_replacement_keeps_model_id():
    a, b = _col("a", 11), _col("b", 12)
    out, n, left = col_splice(_pad(a + b), "b",
                              lambda mid: _col("b", mid, spheres=2))
    assert (n, left) == (1, 2)
    assert out[:len(a)] == a
    models = read_col(out)
    assert [(m.model_name, m.model_id, len(m.spheres)) for m in models] == [
        ("a", 11, 0), ("b", 12, 2)]


def test_col_splice_absent_name_changes_nothing():
    a, b = _col("a", 1), _col("b", 2)
    out, n, left = col_splice(_pad(a + b), "zzz", lambda _mid: None)
    assert (out, n, left) == (a + b, 0, 2)


@pytest.mark.parametrize("version", [1, 2])
def test_col_index_finds_every_library(tmp_path, version):
    arch = _archive(tmp_path, version, {
        "lib.col": _col("a", 1) + _col("B", 2), "x.col": _col("x", 3),
        "a.dff": b"D" * 100})
    with ImgReader(arch) as rd:
        assert col_index(rd) == {"a": ["lib.col"], "b": ["lib.col"],
                                 "x": ["x.col"]}


# ── удаление из архива (VER2 SA, VER1 III/VC) ─────────────────────

@pytest.mark.parametrize("version", [1, 2])
def test_remove_model_from_archive(tmp_path, version):
    house, shed = _col("house", 11), _col("shed", 12, spheres=1)
    arch = _archive(tmp_path, version, {
        "house.dff": b"H" * 3000, "house.txd": b"T" * 500,
        "lodhouse.dff": b"L" * 700, "shed.dff": b"S" * 100,
        "houses.col": house + shed, "house.col": _col("house", 11),
        "solo.col": _col("solo", 20)})
    names = {e.name.lower(): e.name for e in read_directory(arch)}
    with ImgReader(arch) as rd:
        idx = col_index(rd)
    plan = remove_plan([dict(kind="dff", arch=arch, name="house", txd="house",
                             lod="LODhouse"),
                        dict(kind="col", arch=arch, name="solo")],
                       {arch: names}, {arch: idx}, {})[arch]
    assert plan["entries"] == ["house.dff", "house.txd"]
    assert plan["libs"] == {"houses.col": ["house"], "house.col": ["house"],
                            "solo.col": ["solo"]}
    assert plan["kept_lod"] == ["LODhouse"]

    done = []
    remove_entries(arch, plan["entries"], plan["libs"], done)
    assert done[:2] == ["house.dff", "house.txd"]
    assert sorted(d for d in done[2:]) == [
        ("house.col", ["house"]), ("houses.col", ["house"]), ("solo.col", ["solo"])]
    assert {e.name for e in read_directory(arch)} == {
        "lodhouse.dff", "shed.dff", "houses.col"}
    with ImgReader(arch) as rd:
        data = rd.read("houses.col")
    assert data.startswith(shed)                   # чужая запись байт в байт
    assert [(m.model_name, m.model_id) for m in read_col(data)] == [("shed", 12)]
    # VC роняет библиотеку, если за записями ≥ 2056 байт.
    assert len(data) - col_chunks(data)[-1][1] < 2056


def test_remove_entries_reports_progress_before_failure(tmp_path, monkeypatch):
    arch = _archive(tmp_path, 2, {"a.dff": b"A" * 10, "b.dff": b"B" * 10})
    real, calls = img_remove.remove_file, []

    def flaky(path, name):
        calls.append(name)
        if len(calls) > 1:
            raise PermissionError("game holds the archive")
        return real(path, name)

    monkeypatch.setattr(img_remove, "remove_file", flaky)
    done = []
    with pytest.raises(PermissionError):
        remove_entries(arch, ["a.dff", "b.dff"], {}, done)
    assert done == ["a.dff"]


# ── IDE игры ──────────────────────────────────────────────────────

def test_game_ide_paths_reads_default_dat_first(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "default.dat").write_text(
        "IDE DATA\\DEFAULT.IDE\nIDE DATA\\VEHICLES.IDE\n", encoding="utf-8")
    (data / "gta.dat").write_text(
        "# c\nIDE DATA\\MAPS\\X.IDE\nIDE DATA\\VEHICLES.IDE\n", encoding="utf-8")
    paths, dats = game_ide_paths(str(tmp_path))
    assert dats == ["default.dat", "gta.dat"]
    assert [os.path.basename(p) for p in paths] == [
        "DEFAULT.IDE", "VEHICLES.IDE", "X.IDE"]


def test_game_ide_paths_vc_and_empty(tmp_path):
    data = tmp_path / "vc" / "data"
    data.mkdir(parents=True)
    (data / "default.dat").write_text("IDE DATA\\DEFAULT.IDE\n", encoding="utf-8")
    (data / "gta_vc.dat").write_text("IDE DATA\\MAPS\\HAITI\\HAITI.IDE\n",
                                     encoding="utf-8")
    paths, dats = game_ide_paths(str(tmp_path / "vc"))
    assert dats == ["default.dat", "gta_vc.dat"]
    assert len(paths) == 2
    assert game_ide_paths(str(tmp_path)) == ([], [])


# ── окно оператора и переводы ─────────────────────────────────────

def _ops_tree():
    return ast.parse(io.open(OPS, encoding="utf-8").read())


def _remove_nodes(tree):
    return [n for n in tree.body
            if getattr(n, "name", "") in ("_remove_plan", "_remove_lines",
                                          "GTATOOLS_OT_remove_from_img")]


def test_remove_lines_lists_archive_then_kept():
    fn = [n for n in _remove_nodes(_ops_tree()) if n.name == "_remove_lines"]
    ns = {"os": os, "T": lambda s: s}
    exec(compile(ast.Module(body=fn, type_ignores=[]), str(OPS), "exec"), ns)
    todo = {A: {"entries": ["a.dff", "a.txd", "b.dff", "c.dff"],
                "libs": {"lib.col": ["a", "b"]},
                "kept_txd": [("blade.txd", "exh_lr_bl1", 3)],
                "kept_lod": ["LODa"]}}
    assert ns["_remove_lines"](todo) == [
        "gta3.img:",
        "    a.dff, a.txd, b.dff",
        "    c.dff, a, b (из lib.col)",
        "    blade.txd оставлен — нужен exh_lr_bl1 +2",
        "    LOD «LODa» оставлен — выделите LOD, чтобы удалить",
    ]
    assert ns["_remove_lines"]({A: {"entries": [], "libs": {}, "kept_txd": [],
                                    "kept_lod": []}}) == []


def _lang(name):
    spec = importlib.util.spec_from_file_location(
        "inu_locale_" + name, ROOT / "INU_tools" / "locale" / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LANG


def test_remove_strings_are_translated():
    keys = set()
    for node in _remove_nodes(_ops_tree()):
        if isinstance(node, ast.ClassDef):
            keys.add(ast.get_docstring(node, clean=False).strip())
        for n in ast.walk(node):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "T"
                    and n.args and isinstance(n.args[0], ast.Constant)):
                keys.add(n.args[0].value)
    assert len(keys) > 10
    for lang in ("eng", "spa"):
        missing = sorted(k for k in keys if k not in _lang(lang))
        assert missing == [], (lang, missing)


# ── оператор целиком: bpy — заглушка (приём test_timecyc_wiring) ──

def _ours(name):
    return name in ("bpy", "bmesh") or name.startswith(("bpy.", "INU_tools"))


def _load_ops():
    """ops/img_ops.py + map_link + model_utils + core под пакетом INU_tools на
    заглушке bpy. В sys.modules не остаются: соседние тесты ставят свои
    заглушки; на время теста их возвращает фикстура `ops`."""
    saved = {k: v for k, v in sys.modules.items() if _ours(k)}
    for k in saved:
        del sys.modules[k]
    try:
        bpy = types.ModuleType("bpy")
        bpy.app = types.SimpleNamespace(version=(4, 2, 0))
        bpy.types = types.SimpleNamespace(Operator=type("Operator", (), {}))
        props = types.ModuleType("bpy.props")
        for n in ("BoolProperty", "StringProperty", "IntProperty",
                  "FloatProperty", "EnumProperty", "CollectionProperty",
                  "PointerProperty"):
            setattr(props, n, lambda **kw: None)
        bpy.props = props
        bpy.path = types.SimpleNamespace(abspath=lambda p: p)
        bpy.data = types.SimpleNamespace(objects={})
        bpy.context = types.SimpleNamespace(scene=None)
        sys.modules.update({"bpy": bpy, "bpy.props": props,
                            "bmesh": types.ModuleType("bmesh")})
        pkg = types.ModuleType("INU_tools")
        pkg.__path__ = [str(ROOT / "INU_tools")]
        pkg.T = lambda s: s
        sys.modules["INU_tools"] = pkg
        for m in ("ops.img_ops", "ops.map_link", "tools.model_utils",
                  "core.img_remove", "core.col_library", "core.gta_dat",
                  "core.img", "core.ipl", "core.model_classify"):
            importlib.import_module("INU_tools." + m)
        return bpy, {k: v for k, v in sys.modules.items() if _ours(k)}
    finally:
        for k in [k for k in sys.modules if _ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)


BPY, OPS_MODULES = _load_ops()


@pytest.fixture
def ops(monkeypatch):
    before = set(sys.modules)
    for k, v in OPS_MODULES.items():
        monkeypatch.setitem(sys.modules, k, v)
    yield OPS_MODULES["INU_tools.ops.img_ops"]
    for k in set(sys.modules) - before - set(OPS_MODULES):
        if _ours(k):
            del sys.modules[k]


class _Obj:
    """Меш сцены: имя, obj.inu, текстура в материале (→ DFF, не COL)."""

    def __init__(self, name, **inu):
        self.name, self.type = name, "MESH"
        d = dict(type="OBJ", txd_name="", img_target_file="", lod_object=None,
                 ide_linked=False, ide_target_file="", ide_last_name="")
        d.update(inu)
        self.inu = types.SimpleNamespace(**d)
        mat = types.SimpleNamespace(inu=types.SimpleNamespace(texture_name="t"),
                                    use_nodes=False, node_tree=None)
        self.data = types.SimpleNamespace(materials=[mat])


class _Entries(list):
    def add(self):
        self.append(types.SimpleNamespace(name=""))
        return self[-1]


def _run(op_mod, arch, objs, selected, **settings):
    s = dict(gtatools_ide_sync_list=[], gtatools_game_root="",
             gtatools_ide_path="", gtatools_img_path=arch,
             gtatools_img_entries=_Entries(), gtatools_img_entries_index=0)
    s.update(settings)
    scene = types.SimpleNamespace(objects=list(objs),
                                  inu_settings=types.SimpleNamespace(**s))
    BPY.context.scene = scene
    BPY.data.objects = {o.name: o for o in objs}
    dialog = []
    ctx = types.SimpleNamespace(
        scene=scene, selected_objects=list(selected),
        window_manager=types.SimpleNamespace(
            invoke_props_dialog=lambda op, width=0: dialog.append(width)
            or {"RUNNING_MODAL"}))
    op = op_mod.GTATOOLS_OT_remove_from_img()
    reports = []
    op.report = lambda level, msg: reports.append((min(level), msg))
    first = op.invoke(ctx, None)
    lines = list(type(op)._lines) if dialog else []
    notes = list(type(op)._notes) if dialog else []
    return dict(op=op, ctx=ctx, invoke=first, lines=lines, notes=notes,
                reports=reports, dialog=bool(dialog))


def _house_archive(tmp_path):
    return _archive(tmp_path, 2, {
        "house.dff": b"H" * 3000, "house.txd": b"T" * 900,
        "lodhouse.dff": b"L" * 500, "shed.dff": b"S" * 100,
        "houses.col": _col("house", 11) + _col("shed", 12)})


def _house_scene(arch):
    house = _Obj("house", img_target_file=arch)
    lod = _Obj("LODhouse", img_target_file=arch)
    house.inu.lod_object = lod
    return house, lod, _Obj("shed", img_target_file=arch)


def test_operator_removes_model_keeps_lod_and_its_txd(tmp_path, ops):
    arch = _house_archive(tmp_path)
    house, lod, shed = _house_scene(arch)
    r = _run(ops, arch, [house, lod, shed], [house])
    assert r["invoke"] == {"RUNNING_MODAL"} and r["dialog"]
    assert r["lines"] == [
        "test.img:",
        "    house.dff, house (из houses.col)",
        # LOD остаётся, его txd_name пуст → TXD модели нужен ему.
        "    house.txd оставлен — нужен lodhouse",
        "    LOD «LODhouse» оставлен — выделите LOD, чтобы удалить",
    ]
    r["reports"].clear()
    assert r["op"].execute(r["ctx"]) == {"FINISHED"}
    assert r["reports"] == [("INFO", "IMG: удалено house.dff, house (из houses.col)")]
    assert {e.name for e in read_directory(arch)} == {
        "house.txd", "lodhouse.dff", "shed.dff", "houses.col"}
    with ImgReader(arch) as rd:
        assert [m.model_name for m in read_col(rd.read("houses.col"))] == ["shed"]
    assert house.inu.img_target_file == ""            # снят «В IMG»
    assert lod.inu.img_target_file == arch             # LOD в архиве
    entries = r["ctx"].scene.inu_settings.gtatools_img_entries
    assert sorted(e.name for e in entries) == [
        "house.txd", "houses.col", "lodhouse.dff", "shed.dff"]


def test_operator_clears_status_only_for_that_archive(tmp_path, ops):
    arch = _house_archive(tmp_path)
    other = str(tmp_path / "other.img")
    create_img(other)
    house, lod, shed = _house_scene(arch)
    copy = _Obj("house.001", img_target_file=other)    # копия со своим архивом
    r = _run(ops, arch, [house, copy, lod, shed], [house, copy])
    assert "«house»: нет в other.img — нажмите «Проверить IMG»" in r["notes"]
    assert r["op"].execute(r["ctx"]) == {"FINISHED"}
    assert house.inu.img_target_file == ""
    assert copy.inu.img_target_file == other          # из other.img не удалялась


def test_operator_lod_only_and_model_without_status(tmp_path, ops):
    arch = _house_archive(tmp_path)
    house, lod, shed = _house_scene(arch)
    lod.inu.img_target_file = ""                       # архив — у модели
    ghost = _Obj("ghost")
    r = _run(ops, arch, [house, lod, shed, ghost], [lod, ghost],
             gtatools_img_path="")
    assert r["lines"] == [
        "test.img:",
        "    lodhouse.dff",
        "    house.txd оставлен — нужен house",
    ]
    assert r["notes"] == ["«ghost»: не в IMG — нажмите «Проверить IMG»"]
    assert r["op"].execute(r["ctx"]) == {"FINISHED"}
    assert {e.name for e in read_directory(arch)} == {
        "house.dff", "house.txd", "shed.dff", "houses.col"}
    assert house.inu.img_target_file == arch           # модель не тронута


def test_operator_stale_status_and_locked_archive(tmp_path, ops, monkeypatch):
    arch = _house_archive(tmp_path)
    house, lod, shed = _house_scene(arch)
    ghost = _Obj("ghost", img_target_file=arch)        # «В IMG», но .dff нет
    r = _run(ops, arch, [ghost], [ghost])
    assert r["invoke"] == {"CANCELLED"} and not r["dialog"]
    assert r["reports"] == [
        ("WARNING", "«ghost»: нет в test.img — нажмите «Проверить IMG»")]

    def locked(path, name):
        raise PermissionError(path)

    monkeypatch.setattr(OPS_MODULES["INU_tools.core.img_remove"],
                        "remove_file", locked)
    r = _run(ops, arch, [house, lod, shed], [shed])
    r["reports"].clear()
    assert r["op"].execute(r["ctx"]) == {"CANCELLED"}
    assert r["reports"][-1] == ("ERROR", "Файл .img занят — закрой игру: test.img")
    assert shed.inu.img_target_file == arch


def test_operator_clears_status_of_every_copy(tmp_path, ops):
    # Копии на карте — одна модель: её .dff ушёл → «В IMG» снят и у невыделенных.
    arch = _house_archive(tmp_path)
    house, lod, shed = _house_scene(arch)
    copy = _Obj("house.001", img_target_file=arch)
    r = _run(ops, arch, [house, copy, lod, shed], [house])
    assert r["op"].execute(r["ctx"]) == {"FINISHED"}
    assert house.inu.img_target_file == "" and copy.inu.img_target_file == ""
    assert lod.inu.img_target_file == arch and shed.inu.img_target_file == arch


def test_operator_lod_copies_find_model_archive_in_any_order(tmp_path, ops):
    # Первой выделена копия LOD — архив модели всё равно находится.
    arch = _house_archive(tmp_path)
    house, lod, shed = _house_scene(arch)
    lod.inu.img_target_file = ""
    lod2 = _Obj("LODhouse.001")
    r = _run(ops, arch, [house, lod, lod2, shed], [lod2, lod])
    assert r["lines"] == [
        "test.img:",
        "    lodhouse.dff",
        "    house.txd оставлен — нужен house",
    ]
    assert r["notes"] == []


def test_operator_untextured_model_still_uses_its_txd(tmp_path, ops):
    # b без текстурного материала (классификатор скажет COL), но с txd_name —
    # это модель, общий TXD ей нужен; настоящая коллизия (тег COL) — нет.
    arch = _archive(tmp_path, 2, {"a.dff": b"A" * 100, "b.dff": b"B" * 100,
                                  "shared.txd": b"T" * 100})
    a = _Obj("a", img_target_file=arch, txd_name="shared")
    b = _Obj("b", img_target_file=arch, txd_name="shared")
    b.data.materials = []
    r = _run(ops, arch, [a, b], [a])
    assert r["lines"] == ["test.img:", "    a.dff", "    shared.txd оставлен — нужен b"]
    b.inu.type = "COL"
    r = _run(ops, arch, [a, b], [a])
    assert r["lines"] == ["test.img:", "    a.dff, shared.txd"]


def test_operator_notes_not_cut_by_long_list(tmp_path, ops):
    # 30 моделей: режется перечень записей, предупреждение видно до «Удалить?».
    files = {f"m{i:02}.dff": b"D" * 10 for i in range(30)}
    files.update({f"m{i:02}.txd": b"T" * 10 for i in range(30)})
    arch = _archive(tmp_path, 2, files)
    objs = [_Obj(f"m{i:02}", img_target_file=arch) for i in range(30)]
    r = _run(ops, arch, objs, objs)
    assert r["notes"] == [
        "Папка игры не задана — TXD сверены только со сценой и списками IDE"]
    assert len(r["lines"]) == 20 and r["lines"][-1] == "… ещё 2"


# ── Verify IMG: LOD под своим именем, непрочитанный архив связь не снимает ──

def _verify(op_mod, objs, **settings):
    s = dict(gtatools_img_path="", gtatools_game_root="")
    s.update(settings)
    scene = types.SimpleNamespace(objects=list(objs),
                                  inu_settings=types.SimpleNamespace(**s))
    BPY.context.scene = scene
    op = op_mod.GTATOOLS_OT_verify_img_link()
    reports = []
    op.report = lambda level, msg: reports.append((min(level), msg))
    ctx = types.SimpleNamespace(scene=scene, selected_objects=list(objs))
    assert op.execute(ctx) == {"FINISHED"}
    return reports


def test_verify_lod_found_under_its_own_name(tmp_path, ops):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = _archive(tmp_path / "a", 2, {"house.dff": b"H" * 10, "shed.dff": b"S" * 10})
    b = _archive(tmp_path / "b", 2, {"lodhouse.dff": b"L" * 10,
                                     "tatar_str_1lod.dff": b"T" * 10})
    house = _Obj("house")
    lod = _Obj("LODhouse", img_target_file=a)          # был «в архиве модели»
    lod_shed = _Obj("LODshed", img_target_file=a)      # lodshed.dff нигде нет
    tatar = _Obj("tatar_str_1LOD", ide_last_name="tatar_str_1LOD")
    reports = _verify(ops, [house, lod, lod_shed, tatar],
                      gtatools_img_path=a, gtatools_game_root=str(tmp_path))
    assert reports == [("INFO", "Проверка IMG: найдено 3, не в архивах 1")]
    assert house.inu.img_target_file == a
    assert lod.inu.img_target_file == b
    assert lod_shed.inu.img_target_file == ""
    assert tatar.inu.img_target_file == b


def test_verify_unreadable_archive_keeps_links(tmp_path, ops):
    arch = _archive(tmp_path, 2, {"house.dff": b"H" * 10})
    bad = tmp_path / "bad.img"
    bad.write_bytes(b"JUNK" * 8)                       # ни VER2, ни .dir
    house = _Obj("house")
    ghost = _Obj("ghost", img_target_file=str(bad))
    reports = _verify(ops, [house, ghost], gtatools_game_root=str(tmp_path))
    assert reports == [
        ("INFO", "Проверка IMG: найдено 1, не в архивах 1"),
        ("WARNING", "Не прочитаны (связи не сняты): bad.img")]
    assert house.inu.img_target_file == arch
    assert ghost.inu.img_target_file == str(bad)       # могла быть в bad.img
    bad.unlink()
    reports = _verify(ops, [house, ghost], gtatools_game_root=str(tmp_path))
    assert reports == [("INFO", "Проверка IMG: найдено 1, не в архивах 1")]
    assert ghost.inu.img_target_file == ""


@pytest.mark.parametrize("dat, line, version, winner", [
    # SA: первый зарегистрированный — gta3.img, хоть в панели mod.img
    ("gta.dat", "IMG models\\mod.img", 2, "gta3"),
    # VC: CDIMAGE обходится с конца — mod.img бьёт gta3.img
    ("gta_vc.dat", "CDIMAGE models\\mod.img", 1, "mod"),
])
def test_verify_stamps_the_archive_the_game_streams(tmp_path, ops, dat, line,
                                                    version, winner):
    root = tmp_path / "game"
    (root / "data").mkdir(parents=True)
    (root / "data" / dat).write_text(line + "\nIPL data\\x.ipl\n")
    paths = {}
    for stem in ("gta3", "mod"):
        (root / "tmp" / stem).mkdir(parents=True)
        src = _archive(root / "tmp" / stem, version, {"house.dff": b"H" * 10})
        dst = root / "models" / (stem + ".img")
        dst.parent.mkdir(exist_ok=True)
        os.replace(src, dst)
        if version == 1:
            os.replace(src[:-4] + ".dir", str(dst)[:-4] + ".dir")
        paths[stem] = str(dst)
    house = _Obj("house")
    # в панели — проигравший архив (раньше штамп получал именно он)
    loser = "mod" if winner == "gta3" else "gta3"
    _verify(ops, [house], gtatools_img_path=paths[loser],
            gtatools_game_root=str(root))
    assert os.path.normcase(house.inu.img_target_file) == \
        os.path.normcase(paths[winner])


def test_verify_strings_are_translated():
    keys = set()
    for node in _ops_tree().body:
        if getattr(node, "name", "") != "GTATOOLS_OT_verify_img_link":
            continue
        keys.add(ast.get_docstring(node, clean=False).strip())
        for n in ast.walk(node):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "T"
                    and n.args and isinstance(n.args[0], ast.Constant)):
                keys.add(n.args[0].value)
    assert "Не прочитаны (связи не сняты): {0}" in keys
    for lang in ("eng", "spa"):
        missing = sorted(k for k in keys if k not in _lang(lang))
        assert missing == [], (lang, missing)
