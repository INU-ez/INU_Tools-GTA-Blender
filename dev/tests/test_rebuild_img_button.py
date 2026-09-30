# Кнопка «Пересобрать IMG» в строке IMG (как в Max): цель — «В IMG» активной
# модели, иначе IMG из настроек; перед запуском вопрос с именем архива и
# числом записей; занятый игрой файл — понятная ошибка, а не трейсбек.
#
# img_ops импортирует bpy на уровне модуля — класс оператора вытаскиваем по
# AST и исполняем с заглушками (тот же приём, что в test_lightmap_folder).
# `from ..core.img import …` внутри методов резолвится в заглушечный пакет.

import ast
import importlib.util
import io
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADDON = os.path.join(ROOT, "INU_tools")
IMG_OPS = os.path.join(ADDON, "ops", "img_ops.py")
PANELS = os.path.join(ADDON, "ui", "panels.py")
sys.path.insert(0, ADDON)

import core.img as core_img  # noqa: E402

PKG = "_inu_rebuild_stub"


def _classes(path):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


def _load_op(refresh_calls):
    node = _classes(IMG_OPS)["GTATOOLS_OT_rebuild_img"]
    bpy = types.SimpleNamespace(
        types=types.SimpleNamespace(Operator=object),
        path=types.SimpleNamespace(abspath=lambda p: p))
    ns = {
        "__name__": PKG + ".ops.img_ops", "__package__": PKG + ".ops",
        "bpy": bpy, "os": os, "T": lambda s: s,
        "StringProperty": lambda **kw: ("StringProperty", kw),
        "_refresh_img_entries":
            lambda scn, p: refresh_calls.append(p),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), IMG_OPS, "exec"), ns)
    return ns["GTATOOLS_OT_rebuild_img"]


@pytest.fixture
def stub_core(monkeypatch):
    """Пакет-заглушка: ``..core.img`` → модуль с настоящими функциями ядра,
    которые тест может подменить."""
    img = types.ModuleType(PKG + ".core.img")
    img.read_directory = core_img.read_directory
    img.rebuild_img = core_img.rebuild_img
    for name, mod in ((PKG, types.ModuleType(PKG)),
                      (PKG + ".core", types.ModuleType(PKG + ".core")),
                      (PKG + ".core.img", img)):
        mod.__path__ = []
        monkeypatch.setitem(sys.modules, name, mod)
    return img


def _ctx(img_path="", model_img=""):
    ao = types.SimpleNamespace(inu=types.SimpleNamespace(img_target_file=model_img))
    return types.SimpleNamespace(
        scene=types.SimpleNamespace(
            inu_settings=types.SimpleNamespace(gtatools_img_path=img_path)),
        active_object=ao, window_manager=None)


def _op(cls, target=""):
    op = cls()
    op.target_img = target
    op.reports = []
    op.report = lambda kind, msg: op.reports.append((set(kind), msg))
    return op


def _archive(path, names):
    core_img.create_img(path, version=2)
    with core_img.ImgWriter(path, version=2) as w:
        for n in names:
            w.add(n, b"D" * 100)


def test_operator_has_target_and_confirmation():
    cls = _load_op([])
    assert "target_img" in cls.__annotations__
    assert callable(getattr(cls, "invoke", None))


def test_poll_accepts_model_img_without_settings_img():
    cls = _load_op([])
    assert cls.poll(_ctx(model_img="C:/g/models/gta3.img"))
    assert cls.poll(_ctx(img_path="C:/g/models/gta3.img"))
    assert not cls.poll(_ctx())


def test_execute_rebuilds_model_img_not_settings_img(tmp_path, stub_core):
    main = str(tmp_path / "gta3.img")
    mine = str(tmp_path / "mymod.img")
    _archive(main, ["a.dff"])
    _archive(mine, ["b.dff", "c.dff"])
    called = []
    stub_core.rebuild_img = lambda p: (called.append(p) or
                                       {"entries": 2, "saved": 0})
    refresh = []
    op = _op(_load_op(refresh), target=mine)
    assert op.execute(_ctx(img_path=main)) == {"FINISHED"}
    assert called == [mine]
    # Список записей в панели — про архив из настроек, его не трогаем.
    assert refresh == []


def test_execute_settings_img_refreshes_entry_list(tmp_path, stub_core):
    main = str(tmp_path / "gta3.img")
    _archive(main, ["a.dff", "b.dff"])
    refresh = []
    cls = _load_op(refresh)
    op = _op(cls)                               # пусто → IMG из настроек
    assert op.execute(_ctx(img_path=main)) == {"FINISHED"}
    op = _op(cls, target=main)                  # «В IMG» = тот же архив
    assert op.execute(_ctx(img_path=main)) == {"FINISHED"}
    assert refresh == [main, main]
    assert len(core_img.read_directory(main)) == 2


def test_execute_locked_file_reports_close_game(tmp_path, stub_core):
    main = str(tmp_path / "gta3.img")
    _archive(main, ["a.dff"])

    def locked(p):
        raise PermissionError(13, "in use", p)
    stub_core.rebuild_img = locked
    op = _op(_load_op([]), target=main)
    assert op.execute(_ctx()) == {"CANCELLED"}
    assert op.reports == [({"ERROR"},
                           "Файл .img занят — закрой игру: gta3.img")]


def test_invoke_asks_with_archive_name_and_entry_count(tmp_path, stub_core):
    mine = str(tmp_path / "mymod.img")
    _archive(mine, ["a.dff", "b.dff", "c.txd"])
    seen = []

    class WM:
        def invoke_confirm(self, op, event, **kw):
            seen.append(kw)
            return {"RUNNING_MODAL"}
    ctx = _ctx()
    ctx.window_manager = WM()
    op = _op(_load_op([]), target=mine)
    assert op.invoke(ctx, None) == {"RUNNING_MODAL"}
    kw = seen[0]
    assert kw["title"] == "Пересобрать IMG (компакт)"
    assert "mymod.img" in kw["message"] and "записей: 3" in kw["message"]


def test_invoke_old_blender_falls_back_to_plain_confirm(tmp_path, stub_core):
    mine = str(tmp_path / "mymod.img")
    _archive(mine, ["a.dff"])
    seen = []

    class OldWM:
        def invoke_confirm(self, op, event):
            seen.append("plain")
            return {"RUNNING_MODAL"}
    ctx = _ctx()
    ctx.window_manager = OldWM()
    assert _op(_load_op([]), target=mine).invoke(ctx, None) == {"RUNNING_MODAL"}
    assert seen == ["plain"]


def test_invoke_missing_archive_reports_error_without_asking(tmp_path,
                                                             stub_core):
    op = _op(_load_op([]), target=str(tmp_path / "nope.img"))
    assert op.invoke(_ctx(), None) == {"CANCELLED"}
    assert op.reports[0][0] == {"ERROR"}


def test_img_row_has_rebuild_between_export_and_trash():
    src = io.open(PANELS, encoding="utf-8").read()
    i_exp = src.index('"gtatools.export_to_img", text="Export"')
    i_rb = src.index('"gtatools.rebuild_img"', i_exp)
    i_del = src.index('"gtatools.remove_from_img"', i_exp)
    assert i_exp < i_rb < i_del
    assert ".target_img = _rbt" in src[i_rb:i_del]


def test_export_no_longer_sends_users_to_external_img_tool():
    node = _classes(IMG_OPS)["GTATOOLS_OT_export_to_img"]
    src = ast.get_source_segment(io.open(IMG_OPS, encoding="utf-8").read(), node)
    assert "Rebuild Archive в IMG-туле" not in src


def _lang(name):
    spec = importlib.util.spec_from_file_location(
        "_inu_locale_" + name, os.path.join(ADDON, "locale", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LANG


def test_rebuild_strings_are_translated():
    node = _classes(IMG_OPS)["GTATOOLS_OT_rebuild_img"]
    keys = {c.args[0].value for c in ast.walk(node)
            if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "T"
            and c.args and isinstance(c.args[0], ast.Constant)}
    assert "Файл .img занят — закрой игру: {0}" in keys
    for name in ("eng", "spa"):
        missing = keys - set(_lang(name))
        assert not missing, (name, missing)
