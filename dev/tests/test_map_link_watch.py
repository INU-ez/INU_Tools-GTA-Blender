"""Слежение за IDE/IPL и «Проверить IPL» (ops/map_link, ops/map_watch) — на
подставном bpy.

* Слежение (map_watch._tick → map_link.refresh_links): файл, которого сейчас
  нет (редактор пересохраняет через удаление, переименовали папку, отвалился
  диск), связи НЕ снимает. Раньше пропажа считалась «изменением», и все
  «В IPL / В IDE» файла снимались безвозвратно.
* «Проверить IPL» (ipl_pull far='unique', clear_lost=True):
  - единственная свободная строка модели привязывается только в пределах
    2 м — копия за 3 км не забирает чужую расстановку;
  - пропавший / нечитаемый файл связь оставляет (одно предупреждение на
    файл); снятая связь даёт предупреждение.
"""

from pathlib import Path
from types import SimpleNamespace
import importlib
import os
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]


# ── Изолированная загрузка ops/map_link и ops/map_watch ──────────────

def _is_ours(name):
    return name == 'bpy' or name.startswith(('bpy.', 'INU_tools'))


def _install_stubs():
    bpy = types.ModuleType('bpy')
    bpy.app = SimpleNamespace(
        version=(4, 2, 0), translations=None,
        timers=SimpleNamespace(is_registered=lambda f: False,
                               register=lambda f, **kw: None,
                               unregister=lambda f: None))
    bpy.path = SimpleNamespace(abspath=lambda p: p)
    bpy.data = SimpleNamespace(objects=[], filepath='x.blend')
    bpy.context = SimpleNamespace(
        scene=SimpleNamespace(name='S'),
        window_manager=SimpleNamespace(windows=[]))
    sys.modules['bpy'] = bpy
    pkg = types.ModuleType('INU_tools')
    pkg.__path__ = [str(ROOT / 'INU_tools')]
    pkg.T = lambda s, *a, **k: s
    sys.modules['INU_tools'] = pkg


def _load_isolated():
    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for k in saved:
        del sys.modules[k]
    try:
        _install_stubs()
        for name in ('INU_tools.ops.map_link', 'INU_tools.ops.map_watch',
                     'INU_tools.core.mapsync'):
            importlib.import_module(name)
        mods = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    finally:
        for k in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)
    return mods


_MODS = _load_isolated()
ml = _MODS['INU_tools.ops.map_link']
mw = _MODS['INU_tools.ops.map_watch']


@pytest.fixture(autouse=True)
def _our_modules(monkeypatch):
    """Ленивые импорты (``from ..core.mapsync import …``, ``from . import
    map_link``) ищут модуль в sys.modules — на время теста там наши модули.
    Каждый меш — модель «house» (ID 100)."""
    saved = {k: v for k, v in sys.modules.items() if _is_ours(k)}
    for k in saved:
        del sys.modules[k]
    sys.modules.update(_MODS)
    monkeypatch.setattr(ml, 'model_type', lambda o: ('DFF', 'house'))
    try:
        yield
    finally:
        ml.bpy.data.objects = []
        for k in [k for k in sys.modules if _is_ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)


# ── Подставные объекты и файлы ───────────────────────────────────────

IDE_TEXT = "objs\r\n100, house, house, 100, 0\r\nend\r\n"
IPL_TEXT = ("inst\r\n"
            "100, house, 0, 10.0, 0.0, 0.0, 0, 0, 0, 1, -1\r\n"
            "end\r\n")
IPL_OTHER = ("inst\r\n"
             "200, shed, 0, 10.0, 0.0, 0.0, 0, 0, 0, 1, -1\r\n"
             "end\r\n")
IDE_OTHER = "objs\r\n200, shed, shed, 100, 0\r\nend\r\n"


def _obj(name, *, ipl='', ide='', pos=(10.0, 0.0, 0.0), sid=1):
    """Меш модели house (ID 100); *ipl* / *ide* — файлы, к которым он
    привязан (пусто — не привязан)."""
    inu = SimpleNamespace(
        model_id=100, type='DFF', lod_object=None,
        ipl_uuid=('u-' + name) if ipl else '',
        ipl_target_file=ml.norm(ipl) if ipl else '',
        ipl_last_model_id=100 if ipl else 0,
        ipl_last_name='house' if ipl else '',
        ipl_last_pos=tuple(pos), ipl_last_rot=(0.0, 0.0, 0.0, 1.0),
        ipl_owner=name if ipl else '', lod_index=-1,
        ide_linked=bool(ide), ide_target_file=ide,
        ide_last_model_id=100 if ide else 0,
        ide_last_name='house' if ide else '',
        ide_last_draw_distance=0.0, ide_last_txd_name='', ide_last_flags=0)
    wp = SimpleNamespace(x=pos[0], y=pos[1], z=pos[2])
    o = SimpleNamespace(name=name, type='MESH', session_uid=sid, inu=inu,
                        parent=None, matrix_world=SimpleNamespace(translation=wp))
    return o


def _scene(*objs):
    ml.bpy.data.objects = list(objs)
    return list(objs)


def _write(p, text):
    p.write_bytes(text.encode() if isinstance(text, str) else text)
    return str(p)


# ── refresh_links: пропавший файл связи не снимает ───────────────────

def test_refresh_missing_files_keep_links(tmp_path):
    ipl = str(tmp_path / 'gone.ipl')
    ide = str(tmp_path / 'gone.ide')
    o = _obj('house', ipl=ipl, ide=ide)
    _scene(o)
    assert ml.refresh_links() == (0, 0)
    assert o.inu.ipl_uuid == 'u-house'
    assert o.inu.ipl_target_file == ml.norm(ipl)
    assert o.inu.ide_linked is True


def test_refresh_existing_files_still_checked(tmp_path):
    """Контроль: у существующего файла пропавшая строка / ID связь снимает,
    найденная строка — оставляет."""
    ipl = _write(tmp_path / 'map.ipl', IPL_OTHER)
    ide = _write(tmp_path / 'map.ide', IDE_OTHER)
    o = _obj('house', ipl=ipl, ide=ide)
    _scene(o)
    assert ml.refresh_links() == (1, 1)
    assert o.inu.ipl_uuid == ''
    assert o.inu.ide_linked is False

    ok = _write(tmp_path / 'ok.ipl', IPL_TEXT)
    o2 = _obj('house2', ipl=ok)
    _scene(o2)
    assert ml.refresh_links() == (0, 0)
    assert o2.inu.ipl_uuid == 'u-house2'


def test_watch_tick_skips_missing_file(tmp_path, monkeypatch):
    """Файл есть → проверка; удалён → проверки нет, связи и старая подпись
    целы; записан заново (другое содержимое) → снова проверка."""
    p = tmp_path / 'map.ipl'
    _write(p, IPL_TEXT)
    o = _obj('house', ipl=str(p))
    _scene(o)
    calls = []
    orig = ml.refresh_links

    def rec(files=None):
        calls.append(list(files or ()))
        return orig(files)

    monkeypatch.setattr(ml, 'refresh_links', rec)
    mw.reset()
    try:
        key = ml.norm(str(p))
        mw._tick()
        assert calls == [[key]]
        sig = mw._sig[key]
        assert sig is not None

        os.remove(p)
        mw._tick()
        assert len(calls) == 1
        assert mw._sig[key] == sig
        assert o.inu.ipl_uuid == 'u-house'

        _write(p, IPL_TEXT + "# re-saved\r\n")
        mw._tick()
        assert len(calls) == 2
        assert o.inu.ipl_uuid == 'u-house'
    finally:
        mw.reset()


# ── «Проверить IPL»: единственная свободная строка — только в 2 м ─────

def _verify(objs, files):
    return ml.ipl_pull(None, objs, files, move=False, far='unique',
                       clear_lost=True)


@pytest.mark.parametrize('x, linked', [(11.5, True), (12.5, False),
                                       (60.0, False)])
def test_verify_unique_row_only_within_2m(tmp_path, x, linked):
    ipl = _write(tmp_path / 'map.ipl', IPL_TEXT)
    o = _obj('house', pos=(x, 0.0, 0.0))
    _scene(o)
    before = Path(ipl).read_bytes()
    rep = _verify([o], [ipl])
    if linked:
        assert rep.counts == {'linked': 1}
        assert o.inu.ipl_target_file == ml.norm(ipl)
    else:
        assert rep.counts == {'skipped': 1}
        assert o.inu.ipl_uuid == ''
    assert rep.messages == []
    assert Path(ipl).read_bytes() == before


def test_verify_missing_file_keeps_links_one_warning(tmp_path):
    gone = str(tmp_path / 'gone.ipl')
    a = _obj('house', ipl=gone, sid=1)
    b = _obj('house2', ipl=gone, pos=(20.0, 0.0, 0.0), sid=2)
    _scene(a, b)
    rep = _verify([a, b], [])
    assert rep.counts == {'lost': 2}
    assert a.inu.ipl_uuid == 'u-house' and b.inu.ipl_uuid == 'u-house2'
    assert len(rep.messages) == 1
    lvl, text = rep.messages[0]
    assert lvl == 'WARNING' and 'gone.ipl' in text and '2' in text


def test_verify_binary_file_keeps_link(tmp_path):
    ipl = _write(tmp_path / 'map.ipl', b'bnry' + b'\0' * 60)
    o = _obj('house', ipl=ipl)
    _scene(o)
    rep = _verify([o], [])
    assert o.inu.ipl_uuid == 'u-house'
    assert rep.counts == {'lost': 1}
    levels = [lvl for lvl, _t in rep.messages]
    assert levels == ['ERROR', 'WARNING']


def test_verify_row_gone_clears_link_with_warning(tmp_path):
    ipl = _write(tmp_path / 'map.ipl', IPL_OTHER)
    o = _obj('house', ipl=ipl)
    _scene(o)
    rep = _verify([o], [])
    assert o.inu.ipl_uuid == '' and o.inu.ipl_target_file == ''
    assert rep.counts == {'lost': 1}
    assert rep.messages == [
        ('WARNING', "«house»: строки нет в map.ipl (и в 2 м) — связь снята")]
