"""Корзины IDE/IPL (ops/map_link + ops/ide_ipl) — на подставном bpy.

* Корзины Unlink/Remove всегда показывают, что и из какого файла будет
  удалено, и спрашивают (ConfirmOnProblems._always_confirm + Report.plan).
  Корзина у имени модели (link_unlink) раньше звала вложенные операторы
  через EXEC_DEFAULT — окно пропускалось, строки удалялись молча.
* Unlink/Remove IDE: файл, который не открывается (занят, нет прав), даёт
  ERROR в отчёте, остальные файлы обрабатываются. Раньше исключение
  вылетало из оператора, и до следующих файлов дело не доходило.
"""

from pathlib import Path
from types import SimpleNamespace
import importlib
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]


# ── Изолированная загрузка ops/map_link и ops/ide_ipl ────────────────

def _is_ours(name):
    return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))


class _Operator:
    def report(self, level, text):
        self.__dict__.setdefault('reports', []).append((set(level), text))


def _install_stubs():
    bpy = types.ModuleType('bpy')
    bpy.app = SimpleNamespace(version=(4, 2, 0), translations=None)
    base = type('Base', (), {})
    bpy.types = SimpleNamespace(
        Operator=_Operator,
        OperatorFileListElement=type('OperatorFileListElement', (base,), {}),
        Panel=type('Panel', (base,), {}),
        PropertyGroup=type('PropertyGroup', (base,), {}),
    )
    props = types.ModuleType('bpy.props')
    for n in ('StringProperty', 'BoolProperty', 'IntProperty', 'FloatProperty',
              'EnumProperty', 'CollectionProperty', 'PointerProperty'):
        setattr(props, n, lambda **kw: None)
    bpy.props = props
    bpy.path = SimpleNamespace(abspath=lambda p: p)
    bpy.data = SimpleNamespace(objects=[])
    bpy.context = SimpleNamespace(scene=SimpleNamespace(objects=[]))
    sys.modules['bpy'] = bpy
    sys.modules['bpy.props'] = props
    pkg = types.ModuleType('INU_tools')
    pkg.__path__ = [str(ROOT / 'INU_tools')]
    pkg.T = lambda s: s
    sys.modules['INU_tools'] = pkg


def _load_isolated():
    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for k in saved:
        del sys.modules[k]
    try:
        _install_stubs()
        for name in ('INU_tools.ops.map_link', 'INU_tools.ops.ide_ipl',
                     'INU_tools.core.mapsync', 'INU_tools.core.ide',
                     'INU_tools.core.game_versions'):
            importlib.import_module(name)
        mods = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for k in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    return mods


_MODS = _load_isolated()
ml = _MODS['INU_tools.ops.map_link']
ii = _MODS['INU_tools.ops.ide_ipl']
ms = _MODS['INU_tools.core.mapsync']
core_ide = _MODS['INU_tools.core.ide']


@pytest.fixture(autouse=True)
def _our_modules():
    """Ленивые импорты в map_link (``from ..core.mapsync import IdeDoc``)
    ищут модуль по имени в sys.modules — на время теста там должны быть
    наши модули, а не заглушки соседних тестов."""
    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for k in saved:
        del sys.modules[k]
    sys.modules.update(_MODS)
    try:
        yield
    finally:
        for k in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)


# ── Подставные объекты, контекст, файлы ──────────────────────────────

IDE_TEXT = "objs\r\n100, house, house, 100, 0\r\nend\r\n"
IPL_TEXT = ("inst\r\n"
            "100, house, 0, 10.0, 0.0, 0.0, 0, 0, 0, 1, 1\r\n"
            "101, LODhouse, 0, 10.0, 0.0, 0.0, 0, 0, 0, 1, -1\r\n"
            "end\r\n")


def _obj(name, *, ide='', ipl='', mid=100, model='house'):
    inu = SimpleNamespace(
        model_id=mid, type='DFF', real_interior=0, lod_object=None,
        ide_linked=bool(ide), ide_target_file=ide,
        ide_last_model_id=mid if ide else 0, ide_last_name=model if ide else '',
        ide_last_draw_distance=0.0, ide_last_txd_name='', ide_last_flags=0,
        ipl_uuid=('u-' + name) if ipl else '', ipl_target_file=ipl,
        ipl_last_model_id=mid if ipl else 0, ipl_last_name=model if ipl else '',
        ipl_last_pos=(10.0, 0.0, 0.0), ipl_last_rot=(0.0, 0.0, 0.0, 1.0),
        ipl_owner=name if ipl else '', lod_index=-1)
    return SimpleNamespace(name=name, type='MESH', inu=inu)


class _WM:
    def __init__(self):
        self.dialogs = []
        self.status = []

    def invoke_props_dialog(self, op, width=300, **kw):
        self.dialogs.append((op, width))
        self.kwargs = kw
        return {'RUNNING_MODAL'}

    def status_text_set(self, text):
        self.status.append(text)


def _ctx(sel=(), ide='', ipl=''):
    return SimpleNamespace(
        scene=SimpleNamespace(inu_settings=SimpleNamespace(
            gtatools_ide_path=ide, gtatools_ipl_path=ipl, gtatools_game='SA')),
        selected_objects=list(sel),
        window_manager=_WM())


def _entry(mid=100, name='house'):
    return core_ide.IdeObject(model_id=mid, model_name=name, txd_name=name,
                              draw_distance=100.0, flags=0)


@pytest.fixture
def scene_stubs(monkeypatch):
    """model_type / ide_entries без bpy: каждый выделенный меш — модель
    «house» (ID 100), LOD-партнёров нет."""
    monkeypatch.setattr(ml, 'model_type', lambda o: ('DFF', 'house'))
    monkeypatch.setattr(ml, 'ide_entries',
                        lambda objs, rep: [(o, _entry(), None) for o in objs])


def _files(tmp_path):
    ide = tmp_path / 'map.ide'
    ipl = tmp_path / 'map.ipl'
    ide.write_bytes(IDE_TEXT.encode())
    ipl.write_bytes(IPL_TEXT.encode())
    return ide, ipl


class _Col:
    def __init__(self):
        self.rows = []

    def label(self, text='', icon='NONE'):
        self.rows.append(text)

    def separator(self):
        self.rows.append('---')


def _drawn(op):
    col = _Col()
    op.layout = SimpleNamespace(column=lambda align=False: col)
    op.draw(None)
    return col.rows


# ── Report.plan / merge ──────────────────────────────────────────────

def test_report_plan_and_merge_collect_touch():
    a = ml.Report()
    a.plan('x.ide', 'удалить определений: 2')
    b = ml.Report()
    b.plan('x.ide', 'ещё')
    b.plan('y.ipl', 'удалить расстановок: 1')
    b.msg('WARNING', 'w')
    b.add('removed')
    a.merge(b)
    assert a.touch == {'x.ide': ['удалить определений: 2', 'ещё'],
                       'y.ipl': ['удалить расстановок: 1']}
    assert a.counts == {'removed': 1}
    assert a.problems() == [('WARNING', 'w')]
    assert b.touch['x.ide'] == ['ещё']          # merge не трогает источник


# ── ConfirmOnProblems: ветки окна ────────────────────────────────────

def _op_class(always, rep=None, exc=None):
    class Op(ml.ConfirmOnProblems):
        _always_confirm = always

        def __init__(self):
            self.executed = 0
            self.reports = []

        def _run(self, context, dry_run):
            assert dry_run is True
            if exc is not None:
                raise exc
            return rep

        def execute(self, context):
            self.executed += 1
            return {'FINISHED'}

        def report(self, level, text):
            self.reports.append((set(level), text))
    return Op


def _rep(touch=None, probs=()):
    r = ml.Report()
    for p, whats in (touch or {}).items():
        for w in whats:
            r.plan(p, w)
    for t in probs:
        r.msg('WARNING', t)
    return r


def test_always_lists_rows_per_file_and_asks():
    rep = _rep({'C:/m/b.ipl': ['удалить расстановок: 1'],
                'C:/m/a.ide': ['удалить определений: 2']})
    op = _op_class(True, rep)()
    ctx = _ctx()
    assert op.invoke(ctx, None) == {'RUNNING_MODAL'}
    assert op.executed == 0 and len(ctx.window_manager.dialogs) == 1
    assert _drawn(op) == ["Строки будут УДАЛЕНЫ из файлов:",
                          "a.ide: удалить определений: 2",
                          "b.ipl: удалить расстановок: 1",
                          '---',
                          "Удалить эти строки?"]
    # Удаление: по умолчанию «Отмена» (Enter не удаляет), кнопка «Удалить».
    assert ctx.window_manager.kwargs == {'confirm_text': "Удалить",
                                         'cancel_default': True}


def test_delete_dialog_before_blender_4_2_plain_call(monkeypatch):
    """confirm_text / cancel_default есть только с 4.x — на старом Blender
    (legacy-аддон с 2.83) вызов без них, иначе TypeError."""
    monkeypatch.setattr(ml.bpy.app, 'version', (3, 6, 0))
    op = _op_class(True, _rep({'m.ide': ['удалить определений: 1']}))()
    ctx = _ctx()
    assert op.invoke(ctx, None) == {'RUNNING_MODAL'}
    assert ctx.window_manager.kwargs == {}
    assert _drawn(op)[-1] == "Удалить эти строки?"


def test_always_many_files_list_truncated():
    touch = {f"f{i:02}.ipl": ['удалить расстановок: 1'] for i in range(15)}
    op = _op_class(True, _rep(touch))()
    op.invoke(_ctx(), None)
    rows = _drawn(op)
    assert rows[1:13] == [f"f{i:02}.ipl: удалить расстановок: 1"
                          for i in range(12)]
    assert rows[13] == "… ещё 3"
    assert rows[14:] == ['---', "Удалить эти строки?"]


def test_always_rows_and_problems_problems_truncated():
    probs = [f"p{i}" for i in range(14)]
    op = _op_class(True, _rep({'m.ide': ['удалить определений: 1']}, probs))()
    op.invoke(_ctx(), None)
    rows = _drawn(op)
    assert rows[:4] == ["Строки будут УДАЛЕНЫ из файлов:",
                        "m.ide: удалить определений: 1", '', "Проблемы:"]
    assert rows[4:16] == probs[:12]
    assert rows[16] == "… ещё 2"
    assert rows[-1] == "Удалить эти строки?"


def test_always_nothing_to_delete_no_problems_runs_at_once():
    op = _op_class(True, _rep())()
    ctx = _ctx()
    assert op.invoke(ctx, None) == {'FINISHED'}
    assert op.executed == 1 and not ctx.window_manager.dialogs


def test_always_nothing_to_delete_with_problems_is_problem_dialog():
    cls = _op_class(True, _rep(probs=["«x»: нет IDE-файла"]))
    op = cls()
    ctx = _ctx()
    op.invoke(ctx, None)
    assert op.executed == 0
    assert ctx.window_manager.kwargs == {}             # окно проблем: OK как раньше
    assert _drawn(op) == ["Перед записью найдены проблемы:",
                          "«x»: нет IDE-файла", '---',
                          "Остальное будет записано. Продолжить?"]


def test_header_and_question_follow_the_branch():
    """Один и тот же класс: сначала окно удаления, потом окно проблем —
    вопрос не должен остаться от прошлого раза."""
    cls = _op_class(True, _rep({'m.ide': ['удалить определений: 1']}))
    op = cls()
    op.invoke(_ctx(), None)
    assert cls._question == "Удалить эти строки?"
    cls._run = lambda self, context, dry_run: _rep(probs=["w"])
    op.invoke(_ctx(), None)
    assert cls._header == "Перед записью найдены проблемы:"
    assert cls._question == "Остальное будет записано. Продолжить?"
    assert cls._problem_lines == ["w"]


def test_always_dry_run_exception_cancels_without_writing():
    op = _op_class(True, exc=RuntimeError("boom"))()
    ctx = _ctx()
    assert op.invoke(ctx, None) == {'CANCELLED'}
    assert op.executed == 0 and not ctx.window_manager.dialogs
    assert op.reports == [({'ERROR'}, "boom")]


def test_not_always_keeps_old_behaviour():
    # Исключение пробного прогона → запись как раньше.
    op = _op_class(False, exc=RuntimeError("boom"))()
    assert op.invoke(_ctx(), None) == {'FINISHED'} and op.executed == 1
    # Список удаляемого без проблем → сразу запись (Del в боксах).
    op = _op_class(False, _rep({'m.ide': ['удалить определений: 1']}))()
    assert op.invoke(_ctx(), None) == {'FINISHED'} and op.executed == 1
    # Проблемы → прежнее окно, строк удаления в нём нет.
    op = _op_class(False, _rep({'m.ide': ['удалить определений: 1']}, ["w"]))()
    op.invoke(_ctx(), None)
    assert op.executed == 0
    assert _drawn(op) == ["Перед записью найдены проблемы:", "w", '---',
                          "Остальное будет записано. Продолжить?"]


def test_which_operators_always_ask():
    assert ii.GTATOOLS_OT_link_unlink._always_confirm is True
    assert ii.GTATOOLS_OT_ide_remove_link._always_confirm is True
    assert ii.GTATOOLS_OT_ipl_remove_link._always_confirm is True
    # Del в боксах IDE / IPL — как раньше, только при проблемах.
    assert ii.GTATOOLS_OT_remove_ide._always_confirm is False
    assert ii.GTATOOLS_OT_remove_ipl._always_confirm is False
    assert issubclass(ii.GTATOOLS_OT_link_unlink, ml.ConfirmOnProblems)


# ── map_link: что попадает в план ────────────────────────────────────

def test_ipl_remove_plans_placements_dry_run_writes_nothing(tmp_path, scene_stubs):
    _ide, ipl = _files(tmp_path)
    o = _obj('house', ipl=str(ipl))
    rep = ml.ipl_remove(_ctx(), [o], dry_run=True)
    # Строка LOD уходит вместе с моделью — в списке тоже.
    assert rep.touch == {ml.norm(str(ipl)): ["удалить расстановок: 1",
                                             "удалить LOD: 1"]}
    assert ipl.read_bytes() == IPL_TEXT.encode()
    assert o.inu.ipl_uuid                              # связь не снята


def test_ide_remove_plans_definitions(tmp_path, scene_stubs):
    ide, _ipl = _files(tmp_path)
    o = _obj('house', ide=str(ide))
    rep = ml.ide_remove(_ctx(), [o], dry_run=True)
    assert rep.touch == {ml.norm(str(ide)): ["удалить определений: 1"]}
    assert ide.read_bytes() == IDE_TEXT.encode()


def test_ide_remove_other_model_under_id_is_not_planned(tmp_path, scene_stubs):
    ide, _ipl = _files(tmp_path)
    ide.write_bytes(b"objs\r\n100, barn, barn, 100, 0\r\nend\r\n")
    o = _obj('house', ide=str(ide))
    rep = ml.ide_remove(_ctx(), [o], dry_run=True)
    assert rep.touch == {}
    assert rep.problems()                              # «ID 100 … «barn»»


# ── IDE: файл не читается ────────────────────────────────────────────

def _deny_load(monkeypatch, bad):
    orig = ms.IdeDoc.__dict__['load'].__func__

    def load(cls, path):
        if ml.norm(path) == ml.norm(str(bad)):
            raise PermissionError(13, "Permission denied", str(bad))
        return orig(cls, path)
    monkeypatch.setattr(ms.IdeDoc, 'load', classmethod(load))


@pytest.mark.parametrize('dry_run', [False, True])
def test_ide_remove_unreadable_file_is_reported(tmp_path, monkeypatch,
                                                scene_stubs, dry_run):
    bad = tmp_path / 'bad.ide'
    good = tmp_path / 'good.ide'
    bad.write_bytes(IDE_TEXT.encode())
    good.write_bytes(IDE_TEXT.encode())
    _deny_load(monkeypatch, bad)
    o_bad = _obj('house', ide=str(bad))
    o_good = _obj('house.001', ide=str(good))

    rep = ml.ide_remove(SimpleNamespace(scene=None), [o_bad, o_good],
                        dry_run=dry_run)

    errs = [t for lvl, t in rep.messages if lvl == 'ERROR']
    assert len(errs) == 1 and errs[0].startswith('bad.ide: ')
    assert rep.counts.get('removed') == 1
    assert list(rep.touch) == [ml.norm(str(good))]
    assert bad.read_bytes() == IDE_TEXT.encode()
    assert o_bad.inu.ide_linked is True
    if dry_run:
        assert good.read_bytes() == IDE_TEXT.encode()
        assert o_good.inu.ide_linked is True
    else:
        assert b"house" not in good.read_bytes()
        assert o_good.inu.ide_linked is False


def test_unlink_ide_unreadable_file_shows_in_dialog(tmp_path, monkeypatch,
                                                   scene_stubs):
    """Корзина IDE: занятый файл — строка «Проблемы», остальное в списке."""
    bad = tmp_path / 'bad.ide'
    good = tmp_path / 'good.ide'
    bad.write_bytes(IDE_TEXT.encode())
    good.write_bytes(IDE_TEXT.encode())
    _deny_load(monkeypatch, bad)
    ctx = _ctx([_obj('house', ide=str(bad)), _obj('house.001', ide=str(good))])
    op = ii.GTATOOLS_OT_ide_remove_link()
    assert op.invoke(ctx, None) == {'RUNNING_MODAL'}
    rows = _drawn(op)
    assert rows[:4] == ["Строки будут УДАЛЕНЫ из файлов:",
                        "good.ide: удалить определений: 1", '', "Проблемы:"]
    assert rows[4].startswith("bad.ide: ")
    assert good.read_bytes() == IDE_TEXT.encode()      # до OK ничего не пишем


# ── Корзина у имени модели: link_unlink ──────────────────────────────

def test_link_unlink_run_merges_both_plans(monkeypatch):
    calls = []

    def fake(kind, path):
        def run(context, sel, *, picked='', dry_run=False):
            calls.append((kind, [o.name for o in sel], picked, dry_run))
            r = ml.Report()
            r.plan(path, kind)
            r.msg('WARNING', kind + ' w')
            return r
        return run
    monkeypatch.setattr(ml, 'ide_remove', fake('ide', 'a.ide'))
    monkeypatch.setattr(ml, 'ipl_remove', fake('ipl', 'a.ipl'))
    ctx = _ctx([_obj('house')], ide='pick.ide', ipl='pick.ipl')
    rep = ii.GTATOOLS_OT_link_unlink()._run(ctx, True)
    assert calls == [('ide', ['house'], 'pick.ide', True),
                     ('ipl', ['house'], 'pick.ipl', True)]
    assert rep.touch == {'a.ide': ['ide'], 'a.ipl': ['ipl']}
    assert [t for _l, t in rep.problems()] == ['ide w', 'ipl w']


def test_link_unlink_asks_then_deletes_from_both(tmp_path, monkeypatch,
                                                 scene_stubs):
    ide, ipl = _files(tmp_path)
    o = _obj('house', ide=str(ide), ipl=str(ipl))
    ctx = _ctx([o])
    published = []
    monkeypatch.setattr(ii, '_pub', lambda op, level, msg: published.append(msg))
    op = ii.GTATOOLS_OT_link_unlink()

    # Клик по корзине: только окно, файлы и связи не тронуты.
    assert op.invoke(ctx, None) == {'RUNNING_MODAL'}
    assert _drawn(op) == ["Строки будут УДАЛЕНЫ из файлов:",
                          "map.ide: удалить определений: 1",
                          "map.ipl: удалить расстановок: 1; удалить LOD: 1",
                          '---',
                          "Удалить эти строки?"]
    assert ide.read_bytes() == IDE_TEXT.encode()
    assert ipl.read_bytes() == IPL_TEXT.encode()
    assert o.inu.ide_linked and o.inu.ipl_uuid

    # OK в окне → execute.
    assert op.execute(ctx) == {'FINISHED'}
    assert b"house" not in ide.read_bytes()
    assert b"house" not in ipl.read_bytes()            # и модель, и её LOD
    assert not o.inu.ide_linked and not o.inu.ipl_uuid
    # Итоги IDE и IPL раздельно, в статусе — оба через «|».
    line = "IDE: удалено 1  |  IPL: удалено 1, LOD удалено 1"
    assert published == ["IDE: удалено 1", "IPL: удалено 1, LOD удалено 1",
                         line]
    assert ctx.window_manager.status == [line]


def test_link_unlink_lod_alone_asks_before_detach(tmp_path, monkeypatch):
    """Выделен только LOD (корзина у имени активна и для него). В IDE
    удалять нечего, но в IPL модель теряет LOD, а строка LOD уходит —
    раньше это шло без окна."""
    ide = tmp_path / 'map.ide'
    ipl = tmp_path / 'map.ipl'
    ide.write_bytes(IDE_TEXT.encode())                 # строки 101 нет
    ipl.write_bytes(IPL_TEXT.encode())
    dff = _obj('house', ipl=str(ipl))
    lod = _obj('LODhouse', mid=101, model='LODhouse')
    lod.inu.type = 'LOD'
    bpy = ml.bpy
    monkeypatch.setattr(bpy.data, 'objects', [dff, lod])
    monkeypatch.setattr(bpy.context.scene, 'objects', [dff, lod])
    monkeypatch.setattr(ml, 'model_type', lambda o: (
        ('LOD', 'house') if o.name.startswith('LOD') else ('DFF', 'house')))
    monkeypatch.setattr(ml, 'ide_entries', lambda objs, rep: [
        (o, _entry(101, 'LODhouse'), None) for o in objs])
    monkeypatch.setattr(ml, 'plain_name', lambda o: o.name)
    published = []
    monkeypatch.setattr(ii, '_pub', lambda op, level, msg: published.append(msg))
    ctx = _ctx([lod], ide=str(ide))
    op = ii.GTATOOLS_OT_link_unlink()

    assert op.invoke(ctx, None) == {'RUNNING_MODAL'}
    assert _drawn(op) == ["Строки будут УДАЛЕНЫ из файлов:",
                          "map.ipl: отвязать LOD: 1; удалить LOD: 1",
                          '---',
                          "Удалить эти строки?"]
    assert ipl.read_bytes() == IPL_TEXT.encode()       # до OK ничего не пишем

    assert op.execute(ctx) == {'FINISHED'}
    assert b"LODhouse" not in ipl.read_bytes()
    assert b"house" in ipl.read_bytes()                # модель осталась
    assert dff.inu.lod_index == -1
    assert published[-1].endswith("IPL: LOD удалено 1")


def test_link_unlink_without_selection():
    op = ii.GTATOOLS_OT_link_unlink()
    ctx = _ctx([])
    assert op.execute(ctx) == {'CANCELLED'}
    assert op.reports == [({'ERROR'}, "Выделите меш объекты")]


def test_box_del_still_writes_without_dialog(tmp_path, monkeypatch,
                                            scene_stubs):
    """Del в боксе IDE: чистый прогон пишет сразу, как раньше."""
    ide, _ipl = _files(tmp_path)
    o = _obj('house', ide=str(ide))
    ctx = _ctx([o], ide=str(ide))
    published = []
    monkeypatch.setattr(ii, '_pub', lambda op, level, msg: published.append(msg))
    op = ii.GTATOOLS_OT_remove_ide()
    assert op.invoke(ctx, None) == {'FINISHED'}
    assert not ctx.window_manager.dialogs
    assert b"house" not in ide.read_bytes()
    assert published == ["IDE: удалено 1"]
