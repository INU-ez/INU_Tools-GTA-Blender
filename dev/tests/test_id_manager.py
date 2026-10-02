"""data/id_manager — ID presets: `Preset` (one read / one write per
operation), game IDs in `<preset>.game` (Free phantoms / Clear All / Clear
selected keep them) and «Из игры» reading default.dat + gta*.dat.

Runs without Blender: the addon is loaded as a synthetic package, and
tools/user_data (which imports bpy) is replaced — every test points
_presets_dir at tmp_path. The operator module gets its own bpy stub only
while it is imported; sys.modules is restored afterwards so sibling tests
that `importorskip('bpy')` still skip.
"""

from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib
import os
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
_PKG = "inu_idm_test_pkg"


def _package():
    pkg = sys.modules.get(_PKG)
    if pkg is None:
        pkg = ModuleType(_PKG)
        pkg.__path__ = [str(ROOT / "INU_tools")]
        pkg.T = lambda s: s
        pkg._id_preset_sync = lambda context: None
        sys.modules[_PKG] = pkg
        ud = ModuleType(f"{_PKG}.tools.user_data")
        ud.get_user_data_dir = lambda sub: str(ROOT / "_unused" / sub)
        sys.modules[f"{_PKG}.tools.user_data"] = ud
    return pkg


_package()
_im = importlib.import_module(f"{_PKG}.data.id_manager")


def _load_ops():
    class _Operator:
        pass

    def _prop(*_a, **_kw):
        return None

    bpy = ModuleType("bpy")
    bpy.types = SimpleNamespace(Operator=_Operator)
    bpy.props = SimpleNamespace(StringProperty=_prop, BoolProperty=_prop,
                                IntProperty=_prop, EnumProperty=_prop)
    bpy.app = SimpleNamespace(version=(4, 2, 0))
    bpy.path = SimpleNamespace(abspath=lambda p: p)
    bpy.data = SimpleNamespace(objects=[])
    saved = {n: sys.modules.get(n) for n in ("bpy", "bpy.types", "bpy.props")}
    sys.modules.update({"bpy": bpy, "bpy.types": bpy.types, "bpy.props": bpy.props})
    try:
        return importlib.import_module(f"{_PKG}.ops.id_manager_ops")
    finally:
        for n, m in saved.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m


_ops = _load_ops()


@pytest.fixture
def im(tmp_path, monkeypatch):
    monkeypatch.setattr(_im, "_presets_dir", lambda: str(tmp_path))
    _im.set_active_preset("t")
    yield _im
    _im.set_active_preset("default")


@pytest.fixture
def writes(im, monkeypatch):
    """Basenames of every file the module writes."""
    calls = []
    real = im._write_atomic

    def spy(path, text):
        calls.append(os.path.basename(path))
        real(path, text)

    monkeypatch.setattr(im, "_write_atomic", spy)
    return calls


def _write(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")


def _lines(tmp_path, name):
    return (tmp_path / name).read_text(encoding="utf-8").splitlines()


# ── Preset ──────────────────────────────────────────────────────────

def test_allocate_ascending_skip_prefer(im, tmp_path):
    _write(tmp_path, "t.txt", "325\n321\n322-used\n323\n324\n")   # hand-edited, unsorted
    P = im.Preset()
    skip = {323}
    assert P.allocate("a", skip) == 321
    assert P.allocate("b", skip, prefer=325) == 325
    assert P.allocate("c", skip, prefer=322) == 324      # 322 taken → first free
    assert P.allocate("d", skip, prefer=323) is None     # prefer skipped, nothing free
    assert P.release(321)
    assert P.allocate("e", skip) == 321                  # freed → found again


def test_free_game_requires_explicit_release_and_removes_sidecar(im, tmp_path):
    _write(tmp_path, 't.txt', '500\n501\n')  # manually cleared .txt
    _write(tmp_path, 't.game', '500\n')
    p = im.Preset()
    assert not p.is_free(500)
    assert im.get_free_ids() == [501]
    assert p.allocate('house', (), prefer=500) == 501
    assert not p.release(500)
    assert p.release(500, free_game=True)
    p.save()
    assert im.game_ids() == set()
    assert im.Preset().allocate('new', (), prefer=500) == 500


def test_game_release_operator_requires_confirmation(im, tmp_path, monkeypatch):
    _write(tmp_path, 't.txt', '500-game_house\n')
    _write(tmp_path, 't.game', '500\n')
    obj = SimpleNamespace(inu=SimpleNamespace(model_id=500))
    monkeypatch.setattr(_ops.bpy, 'data', SimpleNamespace(objects=[obj]))
    op = _ops.GTATOOLS_OT_id_manager_release()
    op.model_id = 500
    _reports(op)
    ctx = SimpleNamespace(window_manager=SimpleNamespace(
        invoke_props_dialog=lambda *_a, **_kw: {'RUNNING_MODAL'}))
    assert op.execute(ctx) == {'CANCELLED'}
    assert obj.inu.model_id == 500 and im.game_ids() == {500}
    assert op.invoke(ctx, None) == {'RUNNING_MODAL'}
    assert obj.inu.model_id == 500 and im.game_ids() == {500}
    assert op.execute(ctx) == {'FINISHED'}
    assert obj.inu.model_id == 0 and im.game_ids() == set()
    assert im.get_free_ids() == [500]


def test_many_ids_one_write(im, tmp_path, writes):
    im.create_id_file()
    writes.clear()
    P = im.Preset()
    got = [P.allocate(f"m{k}", set()) for k in range(50)]
    P.save()
    assert got == list(range(321, 371))
    assert writes == ["t.txt"]
    assert im.get_used_ids()[370] == "m49"


def test_save_without_changes_writes_nothing(im, tmp_path, writes):
    _write(tmp_path, "t.txt", "321\n")
    im.Preset().save()
    assert im.gc_preset([]) == 0
    assert writes == []


def test_save_keeps_header_no_temp_left(im, tmp_path):
    _write(tmp_path, "t.txt", "# GTA SA model ID preset: t\n# note\n322\n321\n")
    assert im.allocate_id("house") == 321
    assert _lines(tmp_path, "t.txt") == ["# GTA SA model ID preset: t", "# note",
                                         "321-house", "322"]
    assert not list(tmp_path.glob("*.inu_tmp"))


def test_reserve_and_release(im, tmp_path, writes):
    _write(tmp_path, "t.txt", "321\n")
    assert im.reserve_id(321, "a") is True
    assert im.reserve_id(321, "a") is False          # same state — no write
    assert im.reserve_id(5000, "b") is True          # missing → appended
    assert im.get_used_ids() == {321: "a", 5000: "b"}
    assert im.release_id(321) is True
    assert im.release_id(321) is False
    assert writes == ["t.txt"] * 3


def test_extend_after_highest(im, tmp_path):
    _write(tmp_path, "t.txt", "321\n400-landstal\n")
    assert im.extend_ids(3) == (401, 403)
    assert im.get_free_ids() == [321, 401, 402, 403]


# ── game IDs (.game) ────────────────────────────────────────────────

GAME_TXT = "# hdr\n321-gun_dildo1\n400-landstal\n3500-mine\n3501-orphan\n"
GAME_IDS = "# INU: IDs used by the game (From Game)\n321\n400\n"


def test_gc_keeps_game_ids(im, tmp_path):
    _write(tmp_path, "t.txt", GAME_TXT)
    _write(tmp_path, "t.game", GAME_IDS)
    scene = [SimpleNamespace(inu=SimpleNamespace(model_id=3500))]
    assert im.gc_preset(scene) == 1
    assert im.get_used_ids() == {321: "gun_dildo1", 400: "landstal", 3500: "mine"}


def test_clear_all_keeps_game_ids(im, tmp_path):
    _write(tmp_path, "t.txt", GAME_TXT)
    _write(tmp_path, "t.game", GAME_IDS)
    assert im.clear_all() == 2
    assert im.get_used_ids() == {321: "gun_dildo1", 400: "landstal"}
    assert im.get_free_ids() == [3500, 3501]
    assert _lines(tmp_path, "t.txt")[0] == "# hdr"


def test_game_file_format_matches_max(im, tmp_path):
    P = im.Preset()
    P.mark_game({400: "landstal", 321: "gun_dildo1"})
    P.save()
    assert _lines(tmp_path, "t.game") == ["# INU: IDs used by the game (From Game)",
                                          "321", "400"]
    assert im.game_ids() == {321, 400}


def test_mark_game_clashes_and_added(im, tmp_path):
    _write(tmp_path, "t.txt", "321-my_obj\n322\n400-LANDSTAL\n")
    game = {0: "null", 321: "gun_dildo1", 400: "landstal"}
    P = im.Preset()
    clashes, added = P.mark_game(game)
    assert clashes == [(321, "my_obj", "gun_dildo1")]
    assert added == 1                    # only 0 was free / missing
    P.save()
    assert im.get_used_ids() == {0: "null", 321: "gun_dildo1", 400: "landstal"}
    assert im.Preset().mark_game(game) == ([], 0)


def test_create_id_file_keeps_used_and_game(im, tmp_path, writes):
    _write(tmp_path, "t.txt", "# hdr\n0-male01\n400-landstal\n500\n3500-mine\n25000-fla\n")
    _write(tmp_path, "t.game", "0\n400\n")
    assert im.create_id_file() == 19679 - 3
    assert im.get_used_ids() == {0: "male01", 400: "landstal", 3500: "mine", 25000: "fla"}
    assert set(range(321, 20000)) <= {i for i, _ in im._load()}
    assert _lines(tmp_path, "t.txt")[0] == "# hdr"
    writes.clear()
    assert im.create_id_file() == 0
    assert writes == []
    assert im.game_ids() == {0, 400}


def test_create_after_from_game_skips_game_ids(im, tmp_path):
    P = im.Preset()
    P.mark_game({321: "gun_dildo1", 400: "landstal", 401: "bravura"})
    P.save()
    im.create_id_file()
    P = im.Preset()
    got = [P.allocate(f"m{k}", set()) for k in range(100)]
    assert got[0] == 322
    assert not set(got) & {321, 400, 401}


def test_preset_crud_carries_game_file(im, tmp_path):
    _write(tmp_path, "t.txt", "321-gun_dildo1\n3500\n")
    _write(tmp_path, "t.game", GAME_IDS)
    assert im.create_preset("b", copy_from="t")
    assert im.game_ids("b") == {321, 400}
    assert im.create_preset("e")
    assert im.game_ids("e") == set()
    assert im.rename_preset("b", "c")
    assert im.game_ids("c") == {321, 400}
    assert not (tmp_path / "b.game").exists()
    assert im.delete_preset("c")
    assert not (tmp_path / "c.txt").exists() and not (tmp_path / "c.game").exists()
    assert im.game_ids("t") == {321, 400}            # the source is untouched


def test_stale_game_file_is_not_inherited(im, tmp_path):
    # n.txt deleted by hand, n.game left behind → a new «n» starts clean
    _write(tmp_path, "n.game", GAME_IDS)
    assert im.create_preset("n")
    assert im.game_ids("n") == set() and not (tmp_path / "n.game").exists()
    # same for a rename onto a name with a leftover .game
    _write(tmp_path, "z.game", GAME_IDS)
    assert im.rename_preset("n", "z")
    assert im.game_ids("z") == set()


# ── «Из игры» ───────────────────────────────────────────────────────

DEFAULT_IDE = (
    "weap\n321, gun_dildo1, gun_dildo1, null, 1, 50, 0\nend\n"
    "cars\n400, landstal, landstal, car, LANDSTAL, LANDSTAL, null, richfamily, "
    "10, 0, 0, -1, 0.768, 0.768, -1\nend\n"
    "peds\n0, null, generic, PLAYER1, STAT_PLAYER, player, 0, 0, null, 9, 9, "
    "PED_TYPE_PLAYER, VOICE_PLY_CR, VOICE_PLY_CR\nend\n"
)
MAP_IDE = "objs\n3000, my_house, my_txd, 299, 0\nend\n"


def _game(tmp_path, own_dat="gta.dat"):
    """Fake game folder: default.dat → default.ide, <own_dat> → maps/x.ide."""
    root = tmp_path / "game"
    (root / "data" / "maps").mkdir(parents=True, exist_ok=True)
    (root / "data" / "default.dat").write_text("IDE data\\default.ide\n", encoding="utf-8")
    (root / "data" / own_dat).write_text("IDE data\\maps\\x.ide\n", encoding="utf-8")
    (root / "data" / "default.ide").write_text(DEFAULT_IDE, encoding="utf-8")
    (root / "data" / "maps" / "x.ide").write_text(MAP_IDE, encoding="utf-8")
    return str(root)


def test_from_game_reads_default_dat_and_protects_ids(im, tmp_path):
    _write(tmp_path, "t.txt", "321-my_obj\n")
    im.create_id_file()
    root = _game(tmp_path)
    res = im.populate_from_game(root)
    assert res["dats"] == ["default.dat", "gta.dat"]
    assert (res["count"], res["n_ide"], res["bad"]) == (4, 2, [])
    assert res["clashes"] == [(321, "my_obj", "gun_dildo1")]
    assert res["added"] == 3             # 0, 400, 3000 were free or missing
    used = im.get_used_ids()
    assert {i: used[i] for i in (0, 321, 400, 3000)} == {
        0: "null", 321: "gun_dildo1", 400: "landstal", 3000: "my_house"}
    assert im.game_ids() == {0, 321, 400, 3000}
    # Free phantoms / Clear All leave the game's IDs taken
    assert im.gc_preset([]) == 0
    assert im.clear_all() == 0
    assert set(im.get_used_ids()) == {0, 321, 400, 3000}
    assert im.allocate_id("mine") == 322
    res2 = im.populate_from_game(root)
    assert (res2["added"], res2["clashes"]) == (0, [])


@pytest.mark.parametrize("own_dat", ["gta_vc.dat", "gta3.dat"])
def test_from_game_vc_iii_layout(im, tmp_path, own_dat):
    res = im.populate_from_game(_game(tmp_path, own_dat))
    assert res["dats"] == ["default.dat", own_dat]
    assert res["count"] == 4 and res["added"] == 4
    assert im.game_ids() == {0, 321, 400, 3000}


def test_from_game_without_dat(im, tmp_path, writes):
    (tmp_path / "empty" / "data").mkdir(parents=True)
    assert im.populate_from_game(str(tmp_path / "empty")) is None
    assert writes == []


def test_from_game_reports_missing_ide(im, tmp_path):
    root = _game(tmp_path)
    with open(os.path.join(root, "data", "gta.dat"), "a", encoding="utf-8") as f:
        f.write("IDE data\\maps\\gone.ide\n")
    res = im.populate_from_game(root)
    assert res["bad"] == ["gone.ide"] and res["n_ide"] == 2
    assert res["count"] == 4


def _lock_dats(monkeypatch, *names):
    """parse_gta_dat fails for these .dat files (locked / no rights)."""
    gd = importlib.import_module(f"{_PKG}.core.gta_dat")
    real = gd.parse_gta_dat

    def parse(p):
        if os.path.basename(p) in names:
            raise PermissionError(13, "locked", p)
        return real(p)

    monkeypatch.setattr(gd, "parse_gta_dat", parse)


def test_from_game_reports_unreadable_dat(im, tmp_path, monkeypatch):
    root = _game(tmp_path)
    _lock_dats(monkeypatch, "gta.dat")
    res = im.populate_from_game(root)
    assert res["dats"] == ["default.dat"]            # not «read» when it wasn't
    assert res["bad"] == ["gta.dat"] and res["n_ide"] == 1
    assert res["count"] == 3 and 3000 not in im.game_ids()
    _lock_dats(monkeypatch, "default.dat", "gta.dat")
    res = im.populate_from_game(root)                 # there, but none read: not «no .dat»
    assert (res["dats"], res["bad"], res["count"]) == ([], ["default.dat", "gta.dat"], 0)


# ── operators ───────────────────────────────────────────────────────

def _obj(mid):
    return SimpleNamespace(type="MESH", name=f"o{mid}", inu=SimpleNamespace(model_id=mid))


def _reports(op):
    out = []
    op.report = lambda level, msg: out.append((level, msg))
    return out


def test_clear_selected_keeps_game_ids(im, tmp_path, writes, monkeypatch):
    _write(tmp_path, "t.txt", "321-gun_dildo1\n3500-mine\n3501-other\n")
    _write(tmp_path, "t.game", "321\n")
    a, b, c, d = _obj(321), _obj(3500), _obj(3500), _obj(3501)   # c = copy of b
    monkeypatch.setattr(_ops.bpy, "data", SimpleNamespace(objects=[a, b, c, d]))
    op = _ops.GTATOOLS_OT_id_manager_clear_selected()
    reps = _reports(op)
    assert op.execute(SimpleNamespace(selected_objects=[a, b, c])) == {"FINISHED"}
    assert [o.inu.model_id for o in (a, b, c, d)] == [0, 0, 0, 3501]
    assert im.get_used_ids() == {321: "gun_dildo1", 3501: "other"}
    assert writes == ["t.txt"]
    assert reps == [({"INFO"}, "Очищено ID: 3 (освобождено в пресете: 1)")]


def test_gc_and_clear_report_kept_game_ids(im, tmp_path, monkeypatch):
    _write(tmp_path, "t.txt", "321-gun_dildo1\n3500-mine\n")
    _write(tmp_path, "t.game", "321\n")
    monkeypatch.setattr(_ops.bpy, "data", SimpleNamespace(objects=[]))
    op = _ops.GTATOOLS_OT_id_manager_gc()
    reps = _reports(op)
    assert op.execute(SimpleNamespace()) == {"FINISHED"}
    assert reps == [({"INFO"}, "Освобождено фантомных ID: 1 (ID игры сохранены: 1)")]
    op = _ops.GTATOOLS_OT_id_manager_clear()
    reps = _reports(op)
    assert op.execute(SimpleNamespace()) == {"FINISHED"}
    assert reps == [({"INFO"}, "Все ID очищены: 0 (ID игры сохранены: 1)")]
    assert im.get_used_ids() == {321: "gun_dildo1"}


def test_from_game_operator_report(im, tmp_path):
    def ctx(root):
        return SimpleNamespace(scene=SimpleNamespace(
            inu_settings=SimpleNamespace(gtatools_game_root=root)))

    op = _ops.GTATOOLS_OT_id_manager_from_game()
    reps = _reports(op)
    (tmp_path / "empty").mkdir()
    assert op.execute(ctx(str(tmp_path / "empty"))) == {"CANCELLED"}
    assert reps[-1] == ({"ERROR"}, "Нет data\\gta.dat / default.dat в папке игры")
    _write(tmp_path, "t.txt", "321-my_obj\n")
    assert op.execute(ctx(_game(tmp_path))) == {"FINISHED"}
    level, msg = reps[-1]
    assert level == {"WARNING"}
    assert msg == ("ID игры: 4 (IDE: 2, из default.dat, gta.dat), новых занято: 3; "
                   "Ваши записи на ID игры переименованы (1): 321 my_obj→gun_dildo1")
    assert op.execute(ctx(_game(tmp_path))) == {"FINISHED"}
    assert reps[-1] == ({"INFO"}, "ID игры: 4 (IDE: 2, из default.dat, gta.dat), новых занято: 0")


def test_from_game_operator_unreadable_dat(im, tmp_path, monkeypatch):
    op = _ops.GTATOOLS_OT_id_manager_from_game()
    reps = _reports(op)
    ctx = SimpleNamespace(scene=SimpleNamespace(
        inu_settings=SimpleNamespace(gtatools_game_root=_game(tmp_path))))
    _lock_dats(monkeypatch, "gta.dat")
    assert op.execute(ctx) == {"FINISHED"}
    assert reps[-1] == ({"WARNING"}, "ID игры: 3 (IDE: 1, из default.dat), "
                        "новых занято: 3; Не прочитаны: gta.dat")
    _lock_dats(monkeypatch, "default.dat", "gta.dat")
    assert op.execute(ctx) == {"FINISHED"}
    assert reps[-1] == ({"WARNING"}, "ID игры: 0 (IDE: 0, из —), новых занято: 0; "
                        "Не прочитаны: default.dat, gta.dat")


# ── Assign: copies share one ID, the LOD = model + 1, IDE IDs stepped over;
#    preset names = the model's IDE name (Assign / From ID / Sync) ─────

class _Mesh:
    """Scene mesh stub — hashable by identity, like bpy objects."""

    def __init__(self, name, mid=0, *, tex=True, stamp="", lod=None):
        self.name, self.type = name, "MESH"
        self.inu = SimpleNamespace(model_id=mid, type="OBJ", ide_last_name=stamp,
                                   lod_object=lod, ide_linked=False, ide_target_file="")
        mats = [SimpleNamespace(inu=SimpleNamespace(texture_name="t"))] if tex else []
        self.data = SimpleNamespace(materials=mats)


class _Objects(list):
    def __contains__(self, name):           # bpy.data.objects: `name in objects`
        return any(o.name == name for o in self)


def _clean_model_name_ide(name):
    """Copy of INU_tools.__init__._clean_model_name_ide (__init__ is too heavy)."""
    get_model_type = importlib.import_module(f"{_PKG}.tools.model_utils").get_model_type
    if '.' in name:
        b, s = name.rsplit('.', 1)
        if s.isdigit():
            name = b

    class _Mock:
        def __init__(self, n):
            self.name = n
    _, base = get_model_type(_Mock(name))
    return base


@pytest.fixture
def scene(im, monkeypatch):
    """bpy stub with a scene: the helpers classify models (tools.model_utils,
    map_link) at call time."""
    bpy = _ops.bpy
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(sys.modules, "bmesh", sys.modules.get("bmesh") or ModuleType("bmesh"))
    sc = SimpleNamespace(objects=_Objects(), inu_settings=SimpleNamespace(
        gtatools_ide_path="", gtatools_ide_sync_list=[]))
    monkeypatch.setattr(bpy, "context", SimpleNamespace(scene=sc), raising=False)
    monkeypatch.setattr(bpy, "data", SimpleNamespace(objects=sc.objects))
    monkeypatch.setattr(_package(), "_clean_model_name_ide", _clean_model_name_ide, raising=False)
    return sc


def _assign(sc, *selected):
    op = _ops.GTATOOLS_OT_id_manager_auto_assign()
    reps = _reports(op)
    assert op.execute(SimpleNamespace(selected_objects=list(selected), scene=sc)) == {"FINISHED"}
    return reps[-1]


def test_assign_groups_copies_share_one_id(im, tmp_path):
    _write(tmp_path, "t.txt", "321\n322\n323\n")
    a, b = _Mesh("house"), _Mesh("house.001")
    done, reused, left, warn = _ops.assign_groups(
        [("DFF", "house")], {("DFF", "house"): [a, b]}, im.Preset(), set(),
        lambda g: [], lambda o: "house")
    assert (a.inu.model_id, b.inu.model_id) == (321, 321)
    assert (done, reused, left, warn) == ([("house", 321)], 0, [], [])


def test_assign_groups_copy_with_id_gives_it_to_the_rest(im, tmp_path):
    _write(tmp_path, "t.txt", "321\n322\n")
    a, b, c = _Mesh("house", 500), _Mesh("house.001"), _Mesh("house.002")
    P = im.Preset()
    done, reused, left, warn = _ops.assign_groups(
        [("DFF", "house")], {("DFF", "house"): [a, b, c]}, P, set(), lambda g: [],
        lambda o: "house")
    assert [o.inu.model_id for o in (a, b, c)] == [500, 500, 500]
    assert (done, reused, warn) == ([], 2, [])
    assert not P.changed                     # nothing handed out
    d, e, f = _Mesh("tree", 7), _Mesh("tree.001", 5), _Mesh("tree.002")
    _d, _r, _l, warn = _ops.assign_groups(
        [("DFF", "tree")], {("DFF", "tree"): [d, e, f]}, P, set(), lambda g: [],
        lambda o: "tree")
    assert f.inu.model_id == 5 and warn == [("ids", "tree", [5, 7], 5)]


def test_assign_groups_lod_prefers_model_plus_one(im, tmp_path):
    _write(tmp_path, "t.txt", "321\n322\n401\n402\n")
    dff = _Mesh("house", 400)
    lods = [_Mesh("LODhouse.001", tex=False), _Mesh("LODhouse", tex=False)]  # group[0] = copy
    by_key = {("DFF", "house"): [dff], ("LOD", "lodhouse"): lods}
    done, _r, left, warn = _ops.assign_groups(
        [("DFF", "house"), ("LOD", "lodhouse")], by_key, im.Preset(), set(),
        lambda g: [dff.inu.model_id], lambda o: "LODhouse")
    assert [o.inu.model_id for o in lods] == [401, 401]
    assert (done, left, warn) == ([("LODhouse", 401)], [], [])


def test_assign_groups_lod_prefer_taken_warns(im, tmp_path):
    _write(tmp_path, "t.txt", "321\n322\n401\n")
    lod = _Mesh("LODhouse", tex=False)
    skip = {401, 321}                        # 401 in the scene / an IDE, 321 in an IDE
    done, _r, _l, warn = _ops.assign_groups(
        [("LOD", "lodhouse")], {("LOD", "lodhouse"): [lod]}, im.Preset(), skip,
        lambda g: [400], lambda o: "LODhouse")
    assert lod.inu.model_id == 322 and 322 in skip
    assert warn == [("taken", "LODhouse", 401, 322)]
    lod2 = _Mesh("LODtree", tex=False)       # model without ID → just the next free
    _d, _r, left, warn = _ops.assign_groups(
        [("LOD", "lodtree")], {("LOD", "lodtree"): [lod2]}, im.Preset(), set(),
        lambda g: [0], lambda o: "LODtree")
    assert lod2.inu.model_id == 321 and warn == [] and left == []


def test_assign_groups_no_free_ids_left_listed(im, tmp_path):
    _write(tmp_path, "t.txt", "321\n")
    a, b = _Mesh("house"), _Mesh("tree")
    by_key = {("DFF", "house"): [a], ("DFF", "tree"): [b]}
    done, _r, left, _w = _ops.assign_groups(
        [("DFF", "house"), ("DFF", "tree")], by_key, im.Preset(), set(), lambda g: [],
        lambda o: o.name)
    assert done == [("house", 321)] and left == ["tree"]
    assert (a.inu.model_id, b.inu.model_id) == (321, 0)


def test_ide_name_rules(scene):
    lm = importlib.import_module(f"{_PKG}.ops.map_link")
    mu = importlib.import_module(f"{_PKG}.tools.model_utils")
    cases = [
        (_Mesh("house.001"), "house"),
        (_Mesh("house_DFF"), "house"),
        (_Mesh("LODhouse.001", tex=False), "LODhouse"),
        (_Mesh("tatar_str_1LOD", tex=False, stamp="tatar_str_1LOD"), "tatar_str_1LOD"),
        (_Mesh("lodhouse", tex=False, stamp="lodhouse"), "lodhouse"),
        (_Mesh("xyz_lod", tex=False), "LODxyz"),
        (_Mesh("house_COL", tex=False), "house"),
    ]
    for o, want in cases:
        assert _ops._ide_name(o) == want, o.name
        mt, base = mu.get_model_type(o)
        if mt == "LOD":                      # = the name ide_entries writes to the IDE
            assert _ops._ide_name(o) == lm.lod_model_name(o, base)


def test_assign_operator_copies_col_and_unselected_lod(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "321\n322\n323\n324\n")
    house, copy = _Mesh("house"), _Mesh("house.001")
    lod, col, tree = _Mesh("LODhouse", tex=False), _Mesh("house_COL", tex=False), _Mesh("tree")
    scene.objects.extend([house, copy, lod, col, tree])
    assert _assign(scene, copy, col) == ({"INFO"}, "Назначено ID: 2 — house 321, LODhouse 322")
    assert [o.inu.model_id for o in (house, copy, lod, col, tree)] == [321, 321, 322, 0, 0]
    assert im.get_used_ids() == {321: "house", 322: "LODhouse"}
    extra = _Mesh("house.002")               # a new copy → the model's ID, no new one
    scene.objects.append(extra)
    assert _assign(scene, extra) == ({"INFO"}, "Назначено ID: 0 (копиям дан готовый ID: 1)")
    assert extra.inu.model_id == 321


def test_assign_operator_steps_over_ide_ids_lod_after_model(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "321\n322\n323\n324\n")
    ide = tmp_path / "my.ide"
    ide.write_text("objs\n321, foo, foo, 100, 0\nend\n", encoding="utf-8")
    scene.inu_settings.gtatools_ide_path = str(ide)
    house, lod = _Mesh("house"), _Mesh("LODhouse", tex=False)
    scene.objects.extend([house, lod])
    assert _assign(scene, lod, house)[0] == {"INFO"}      # LOD first in the selection
    assert (house.inu.model_id, lod.inu.model_id) == (322, 323)


def test_assign_operator_lod_by_stamp_and_taken_prefer(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "321\n5001\n")
    dff = _Mesh("tatar_str_1", 5000)
    lod = _Mesh("tatar_str_1LOD", tex=False, stamp="tatar_str_1LOD")
    scene.objects.extend([dff, lod])
    assert _assign(scene, dff) == ({"INFO"}, "Назначено ID: 1 — tatar_str_1LOD 5001")
    assert lod.inu.model_id == 5001 and im.get_used_ids()[5001] == "tatar_str_1LOD"
    _write(tmp_path, "t.txt", "321\n7001\n")
    d2, l2, other = _Mesh("barn", 7000), _Mesh("LODbarn", tex=False), _Mesh("x", 7001)
    scene.objects.extend([d2, l2, other])
    assert _assign(scene, l2) == ({"WARNING"}, "Назначено ID: 1 — LODbarn 321; "
                                  "«LODbarn»: ID 7001 занят — LOD получил 321")


def _linked(o, ide, mid):
    """As stamp_ide leaves a LOD that Add to IDE wrote at model + 1 (Model ID stays 0)."""
    o.inu.ide_linked, o.inu.ide_target_file = True, str(ide)
    o.inu.ide_last_model_id = mid
    return o


def test_assign_operator_lod_keeps_its_own_ide_row(im, tmp_path, scene):
    ide = tmp_path / "my.ide"
    ide.write_text("objs\n500, house, house, 100, 0\n501, LODhouse, house, 300, 0\n"
                   "600, barn, barn, 100, 0\n601, LODbarn, barn, 300, 0\nend\n",
                   encoding="utf-8")
    _write(tmp_path, "t.txt", "321\n322\n501\n")
    house, lod = _Mesh("house", 500), _linked(_Mesh("LODhouse", tex=False), ide, 501)
    barn, blod = _Mesh("barn", 600), _linked(_Mesh("LODbarn", tex=False), ide, 601)
    scene.objects.extend([house, lod, barn, blod])
    # 501 is only in the LOD's own row → N+1, no warning; 601 isn't in the
    # preset but the row holds it → kept and added to the preset.
    assert _assign(scene, house, barn) == ({"INFO"}, "Назначено ID: 2 — LODhouse 501, LODbarn 601")
    assert (lod.inu.model_id, blod.inu.model_id) == (501, 601)
    assert im.get_used_ids() == {501: "LODhouse", 601: "LODbarn"}


def test_assign_operator_lod_own_row_held_by_other_object(im, tmp_path, scene):
    ide = tmp_path / "my.ide"
    ide.write_text("objs\n500, house, house, 100, 0\n501, LODhouse, house, 300, 0\nend\n",
                   encoding="utf-8")
    _write(tmp_path, "t.txt", "321\n501\n")
    house, lod = _Mesh("house", 500), _linked(_Mesh("LODhouse", tex=False), ide, 501)
    scene.objects.extend([house, lod, _Mesh("x", 501)])      # 501 held in the scene
    assert _assign(scene, house) == ({"WARNING"}, "Назначено ID: 1 — LODhouse 321; "
                                     "«LODhouse»: ID 501 занят — LOD получил 321")


def test_assign_operator_lod_prefer_not_in_preset(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "321\n")
    dff, lod = _Mesh("house", 20000), _Mesh("LODhouse", tex=False)
    scene.objects.extend([dff, lod])
    assert _assign(scene, dff) == ({"WARNING"}, "Назначено ID: 1 — LODhouse 321; "
                                   "«LODhouse»: ID 20001 нет в пресете — LOD получил 321")


def test_assign_operator_no_free_ids(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "321\n")
    a, b = _Mesh("aaa"), _Mesh("bbb")
    scene.objects.extend([a, b])
    level, msg = _assign(scene, a, b)
    assert level == {"ERROR"}
    assert msg == ("Назначено ID: 1 — aaa 321; "
                   "Нет свободных ID в активном пресете — без ID: bbb")


def test_sync_scene_ide_names_skip_col(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "321\n322-mine\n")
    scene.objects.extend([_Mesh("house.001", 321), _Mesh("LODhouse", 900, tex=False),
                          _Mesh("house_COL", 901, tex=False), _Mesh("other", 322)])
    op = _ops.GTATOOLS_OT_id_manager_sync_scene()
    reps = _reports(op)
    assert op.execute(SimpleNamespace(scene=scene)) == {"FINISHED"}
    assert reps == [({"INFO"}, "Добавлено ID: 2")]
    assert im.get_used_ids() == {321: "house", 322: "mine", 900: "LODhouse"}


def test_assign_from_reserves_ide_name(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "321\n322\n")
    a, lod = _Mesh("house.001"), _Mesh("LODhouse.001", tex=False)
    scene.objects.extend([a, lod])
    op = _ops.GTATOOLS_OT_id_manager_assign_from()
    op.start_id, op.skip_occupied = 321, True
    _reports(op)
    assert op.execute(SimpleNamespace(selected_objects=[a, lod], scene=scene)) == {"FINISHED"}
    assert im.get_used_ids() == {321: "house", 322: "LODhouse"}


def test_vc_lod_name_follows_its_model_as_in_the_ide(im, tmp_path, scene):
    # VC: Export IDE wrote the unstamped LOD of house as «701, LODse» (the
    # game's pairing, final.g1) — the ID Manager names it the same: its own
    # row, not someone else's; the preset gets the game's name.
    scene.inu_settings.gtatools_game = "VC"
    ide = tmp_path / "my.ide"
    ide.write_text("objs\n700, house, house, 100, 0\n701, LODse, house, 300, 0\nend\n",
                   encoding="utf-8")
    scene.inu_settings.gtatools_ide_path = str(ide)
    _write(tmp_path, "t.txt", "700-800\n")
    house, lod = _Mesh("house", 700), _Mesh("LODhouse", 701, tex=False)
    scene.objects.extend([house, lod])
    assert _ops._ide_name(lod, hd_of=_ops._scene_hd_names(scene)) == "LODse"
    assert _assign_from(scene, 700, house, lod) == (
        {"FINISHED"}, ({"INFO"}, "Назначено ID: 2 (700–701) — house 700, LODse 701"))
    assert (house.inu.model_id, lod.inu.model_id) == (700, 701)
    assert im.get_used_ids() == {700: "house", 701: "LODse"}


# ── «С ID…»: one ID per model (copies share it), a LOD only when selected,
#    COL left alone, previous IDs freed; other models' IDE rows occupied ──

def _assign_from(sc, start, *selected, skip=True):
    op = _ops.GTATOOLS_OT_id_manager_assign_from()
    op.start_id, op.skip_occupied = start, skip
    reps = _reports(op)
    res = op.execute(SimpleNamespace(selected_objects=list(selected), scene=sc))
    return res, reps[-1]


def test_assign_from_skips_occupied_by_default():
    # the property stub drops the default — read it from the source
    import ast
    src = (ROOT / "INU_tools" / "ops" / "id_manager_ops.py").read_text(encoding="utf-8")
    cls = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ClassDef)
               and n.name == "GTATOOLS_OT_id_manager_assign_from")
    prop = next(n for n in cls.body if isinstance(n, ast.AnnAssign)
                and n.target.id == "skip_occupied")
    kw = {k.arg: k.value for k in prop.annotation.keywords}
    assert ast.literal_eval(kw["default"]) is True


def test_assign_from_groups_copies_share_one_id(im, tmp_path):
    _write(tmp_path, "t.txt", "500-house\n")
    a, b = _Mesh("house", 500), _Mesh("house.001", 600)     # copies with different IDs
    P = im.Preset()
    done, clashes, freed = _ops.assign_from_groups(
        [("DFF", "house")], {("DFF", "house"): [a, b]}, P, set(), {}, 700, True,
        lambda o: "house")
    assert (a.inu.model_id, b.inu.model_id) == (700, 700)
    assert (done, clashes, freed) == ([("house", 700)], 0, 1)   # 600 was never in the preset
    assert P.used() == {700: "house"}


def test_assign_from_copies_selected_lod_col_untouched(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "321\n")
    house, copy = _Mesh("house"), _Mesh("house.001")
    lod, col = _Mesh("LODhouse", tex=False), _Mesh("house_COL", 777, tex=False)
    tree, tlod = _Mesh("tree"), _Mesh("LODtree", tex=False)
    scene.objects.extend([house, copy, lod, col, tree, tlod])
    assert _assign_from(scene, 500, copy, col, tree, lod) == (
        {"FINISHED"}, ({"INFO"}, "Назначено ID: 3 (500–502) — house 500, LODhouse 501, tree 502"))
    # the selected LOD right after its model; the unselected LODtree and the COL untouched
    assert [o.inu.model_id for o in (house, copy, lod, col, tree, tlod)] == [
        500, 500, 501, 777, 502, 0]
    assert im.get_used_ids() == {500: "house", 501: "LODhouse", 502: "tree"}


def test_assign_from_col_only_selection(im, tmp_path, scene):
    col = _Mesh("house_COL", 5, tex=False)
    scene.objects.append(col)
    assert _assign_from(scene, 500, col) == ({"CANCELLED"}, ({"ERROR"}, "Выделите меш объекты"))
    assert col.inu.model_id == 5


@pytest.mark.parametrize('mode', ['auto', 'from'])
def test_assign_own_collision_id_is_available(im, tmp_path, scene, mode):
    _write(tmp_path, 't.txt', '500\n501\n')
    house, col = _Mesh('house'), _Mesh('house_COL', 500, tex=False)
    scene.objects.extend([house, col])
    if mode == 'auto':
        _assign(scene, house)
    else:
        _assign_from(scene, 500, house)
    assert house.inu.model_id == 500
    assert col.inu.model_id == 500  # collision itself is untouched


@pytest.mark.parametrize('mode', ['auto', 'from'])
def test_assign_collision_id_held_by_other_model_still_occupied(im, tmp_path, scene, mode):
    _write(tmp_path, 't.txt', '500\n501\n')
    house, col = _Mesh('house'), _Mesh('house_COL', 500, tex=False)
    foreign = _Mesh('tree', 500)
    scene.objects.extend([house, col, foreign])
    if mode == 'auto':
        _assign(scene, house)
    else:
        _assign_from(scene, 500, house)
    assert house.inu.model_id == 501
    assert col.inu.model_id == foreign.inu.model_id == 500


def test_auto_assign_own_collision_id_after_earlier_model(im, tmp_path, scene):
    _write(tmp_path, 't.txt', '500\n501\n502\n')
    tree, house = _Mesh('tree'), _Mesh('house')
    col = _Mesh('house_COL', 500, tex=False)
    scene.objects.extend([tree, house, col])
    _assign(scene, tree, house)
    assert tree.inu.model_id == 501 and house.inu.model_id == col.inu.model_id == 500


def test_assign_from_rerun_keeps_start_and_frees_previous(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "700-barn\n")
    house, copy, lod = _Mesh("house"), _Mesh("house.001"), _Mesh("LODhouse", tex=False)
    barn = _Mesh("barn", 700)                                  # another model, not selected
    scene.objects.extend([house, copy, lod, barn])
    first = ({"FINISHED"}, ({"INFO"}, "Назначено ID: 2 (500–501) — house 500, LODhouse 501"))
    assert _assign_from(scene, 500, house, lod) == first
    assert _assign_from(scene, 500, house, lod) == first      # its own IDs — no drift
    assert _assign_from(scene, 600, lod, copy) == (
        {"FINISHED"}, ({"INFO"}, "Назначено ID: 2 (600–601) — house 600, LODhouse 601; "
                                 "прежние ID освобождены в пресете: 2"))
    assert [o.inu.model_id for o in (house, copy, lod, barn)] == [600, 600, 601, 700]
    assert im.get_used_ids() == {600: "house", 601: "LODhouse", 700: "barn"}
    assert {500, 501} <= set(im.get_free_ids())


def test_assign_from_keeps_game_ids(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "400-landstal\n")
    _write(tmp_path, "t.game", "400\n")
    car = _Mesh("landstal", 400)                               # a vanilla model re-numbered
    scene.objects.append(car)
    assert _assign_from(scene, 400, car)[1] == ({"INFO"}, "Назначено ID: 1 — landstal 401")
    assert _assign_from(scene, 900, car)[1] == ({"INFO"}, "Назначено ID: 1 — landstal 900; "
                                                         "прежние ID освобождены в пресете: 1")
    assert im.get_used_ids() == {400: "landstal", 900: "landstal"}     # 401 freed, 400 the game's


def test_assign_from_skip_or_clash_on_occupied(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "500-mine\n501-landstal\n")
    _write(tmp_path, "t.game", "501\n")
    ide = tmp_path / "my.ide"
    ide.write_text("objs\n502, foo, foo, 100, 0\nend\n", encoding="utf-8")
    scene.inu_settings.gtatools_ide_path = str(ide)
    house, other = _Mesh("house"), _Mesh("other", 503)
    scene.objects.extend([house, other])
    # preset 500, game 501, IDE 502, scene 503 — stepped over
    assert _assign_from(scene, 500, house)[1] == ({"INFO"}, "Назначено ID: 1 — house 504")
    tree = _Mesh("tree")
    scene.objects.append(tree)
    assert _assign_from(scene, 500, tree, skip=False)[1] == (
        {"WARNING"}, "Назначено ID: 1 — tree 500; конфликтов с занятыми: 1")
    assert tree.inu.model_id == 500 and im.get_used_ids()[500] == "tree"


def test_assign_from_own_ide_row_is_not_occupied(im, tmp_path, scene):
    _write(tmp_path, "t.txt", "500-foo\n")
    own = tmp_path / "own.ide"
    own.write_text("objs\n500, foo, foo, 100, 0\nend\n", encoding="utf-8")
    scene.inu_settings.gtatools_ide_path = str(own)
    foo = _Mesh("foo", 500)
    scene.objects.append(foo)
    assert _assign_from(scene, 500, foo)[1] == ({"INFO"}, "Назначено ID: 1 — foo 500")
    other = tmp_path / "other.ide"                             # 500 is another model's row
    other.write_text("objs\n500, bar, bar, 100, 0\nend\n", encoding="utf-8")
    scene.inu_settings.gtatools_ide_path = str(other)
    assert _assign_from(scene, 500, foo)[1] == (
        {"INFO"}, "Назначено ID: 1 — foo 501; прежние ID освобождены в пресете: 1")
    assert im.get_used_ids() == {501: "foo"}


def test_assign_from_old_id_held_by_another_model(im, tmp_path, scene, writes):
    _write(tmp_path, "t.txt", "500-house\n")
    house, barn = _Mesh("house", 500), _Mesh("barn", 500)     # barn (not selected) holds 500 too
    scene.objects.extend([house, barn])
    assert _assign_from(scene, 500, house)[1] == ({"INFO"}, "Назначено ID: 1 — house 501")
    assert barn.inu.model_id == 500
    assert im.get_used_ids() == {500: "house", 501: "house"}     # still held by barn — not freed
    assert writes == ["t.txt"]                                   # one write per run


def test_assign_from_lod_keeps_its_linked_ide_row(im, tmp_path, scene):
    ide = tmp_path / "my.ide"
    ide.write_text("objs\n500, house, house, 100, 0\n501, LODhouse, house, 300, 0\nend\n",
                   encoding="utf-8")
    _write(tmp_path, "t.txt", "500-house\n")
    house = _linked(_Mesh("house", 500), ide, 500)
    lod = _linked(_Mesh("LODhouse", tex=False), ide, 501)     # Add to IDE wrote it at 501, Model ID 0
    scene.objects.extend([house, lod])
    for skip in (True, False):                                 # its own row: no skip, no clash
        lod.inu.model_id = 0
        assert _assign_from(scene, 500, house, lod, skip=skip)[1] == (
            {"INFO"}, "Назначено ID: 2 (500–501) — house 500, LODhouse 501")
        assert (house.inu.model_id, lod.inu.model_id) == (500, 501)
    assert im.get_used_ids() == {500: "house", 501: "LODhouse"}


def test_assign_from_linked_row_after_renumber_or_clear(im, tmp_path, scene):
    ide = tmp_path / "my.ide"
    ide.write_text("objs\n500, foo, foo, 100, 0\nend\n", encoding="utf-8")
    _write(tmp_path, "t.txt", "500-foo\n")
    foo = _linked(_Mesh("foo", 500), ide, 500)
    scene.objects.append(foo)
    assert _assign_from(scene, 600, foo)[1] == (
        {"INFO"}, "Назначено ID: 1 — foo 600; прежние ID освобождены в пресете: 1")
    # the IDE isn't synced yet — its row «500, foo» is still foo's own
    assert _assign_from(scene, 500, foo, skip=False)[1] == (
        {"INFO"}, "Назначено ID: 1 — foo 500; прежние ID освобождены в пресете: 1")
    op = _ops.GTATOOLS_OT_id_manager_clear_selected()          # Model ID 0, 500 freed
    _reports(op)
    assert op.execute(SimpleNamespace(selected_objects=[foo])) == {"FINISHED"}
    assert foo.inu.model_id == 0 and 500 not in im.get_used_ids()
    assert _assign_from(scene, 500, foo)[1] == ({"INFO"}, "Назначено ID: 1 — foo 500")
    assert im.get_used_ids() == {500: "foo"}


def test_assign_from_groups_linked_row_held_elsewhere(im, tmp_path):
    lod = _Mesh("LODhouse", tex=False)
    lod.inu.ide_last_model_id = 501                            # its IDE link remembers row 501
    key = ("LOD", "lodhouse")

    def run(preset, ide, others=()):
        _write(tmp_path, "t.txt", preset)
        lod.inu.model_id = 0
        return _ops.assign_from_groups([key], {key: [lod]}, im.Preset(), set(others), ide,
                                       501, True, lambda o: "LODhouse")[0]

    assert run("501\n", {501: {"lodhouse"}}) == [("LODhouse", 501)]
    assert run("501-LODhouse\n", {501: {"lodhouse"}}) == [("LODhouse", 501)]
    assert run("501-bar\n", {501: {"lodhouse"}}) == [("LODhouse", 502)]      # the preset's bar
    assert run("501\n", {501: {"bar"}}) == [("LODhouse", 502)]               # bar's row
    assert run("501\n", {501: {"lodhouse"}}, others={501}) == [("LODhouse", 502)]
    _write(tmp_path, "t.game", "501\n")
    assert run("501-LODhouse\n", {501: {"lodhouse"}}) == [("LODhouse", 502)]  # a game ID stays


# ── «Создать ID»: asks first; missing IDs added as free, used ones stay ──

def test_create_operator_asks_first_and_reports(im, tmp_path, monkeypatch):
    _write(tmp_path, "t.txt", "400-landstal\n")
    calls = []
    ctx = SimpleNamespace(window_manager=SimpleNamespace(
        invoke_confirm=lambda *a, **kw: calls.append(kw) or {"RUNNING_MODAL"}))
    op = _ops.GTATOOLS_OT_id_manager_create()
    assert op.invoke(ctx, None) == {"RUNNING_MODAL"}
    assert calls[-1] == {"title": "Создать ID", "message": (
        "Пресет «t»: недостающие ID 321-19999 будут добавлены свободными, занятые останутся")}
    monkeypatch.setattr(_ops.bpy.app, "version", (4, 0, 0))   # no title/message before 4.1
    op.invoke(ctx, None)
    assert calls[-1] == {}
    reps = _reports(op)
    assert op.execute(ctx) == {"FINISHED"}
    assert reps == [({"INFO"}, "ID: 321-19999 (+19678 свободных)")]
    assert im.get_used_ids() == {400: "landstal"}


def test_create_id_file_fresh_preset(im, tmp_path):
    im.set_active_preset("fresh")                   # no file yet — same result as before
    assert im.create_id_file() == 19679
    assert len(im.get_free_ids()) == 19679 and im.get_used_ids() == {}


# ── new / renamed preset: the selector gets the name the list shows ────

def test_preset_name_is_the_listed_name(im, tmp_path):
    for raw, want in (("a/b:c", "a_b_c"), ("my preset!", "my preset_"),
                      ("Пресет 1", "Пресет 1"), ("/foo", "foo"), ("_x", "x")):
        assert im.preset_name(raw) == want
        assert im.create_preset(want) and want in im.list_presets()
    assert im.preset_name("/") == im.preset_name(".") == im.preset_name("..") == ""
    assert im.rename_preset("a_b_c", im.preset_name("x:y"))
    names = im.list_presets()
    assert "x_y" in names and "a_b_c" not in names


class _PresetEnum:
    """scene.inu_settings whose gtatools_id_preset acts as Blender's dynamic
    enum: a name missing from list_presets() raises TypeError."""

    def __init__(self, value):
        self._value = value

    @property
    def gtatools_id_preset(self):
        return self._value

    @gtatools_id_preset.setter
    def gtatools_id_preset(self, value):
        if value not in _im.list_presets():
            raise TypeError(f"enum {value!r} not found")
        self._value = value


def test_preset_new_and_rename_select_the_clean_name(im, tmp_path):
    s = _PresetEnum("t")
    ctx = SimpleNamespace(scene=SimpleNamespace(inu_settings=s))
    op = _ops.GTATOOLS_OT_id_preset_new()
    op.name, op.copy_from_active = " a/b:c ", False
    reps = _reports(op)
    assert op.execute(ctx) == {"FINISHED"}
    assert s.gtatools_id_preset == "a_b_c"
    assert reps == [({"INFO"}, "Создан пресет: a_b_c")]
    op.name = "/"
    assert op.execute(ctx) == {"CANCELLED"}
    assert reps[-1] == ({"ERROR"}, "Введите название пресета")
    op = _ops.GTATOOLS_OT_id_preset_rename()
    op.new_name = "_x:y"
    reps = _reports(op)
    assert op.execute(ctx) == {"FINISHED"}
    assert s.gtatools_id_preset == "x_y"
    assert reps == [({"INFO"}, "Переименован: a_b_c → x_y")]
    assert "x_y" in im.list_presets() and "a_b_c" not in im.list_presets()
