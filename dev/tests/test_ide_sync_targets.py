"""ops/sync_files.merge_targets — файлы для «Sync from IDE»: список «IDE для
экспорта» → IDE игры → выбранный файл (всегда, последним), без дублей.

Модуль грузится по пути файла: пакет ops (ide_ipl.py) без Blender не
импортируется."""

from pathlib import Path
import importlib.util
import os

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    'inu_sync_files', ROOT / 'INU_tools' / 'ops' / 'sync_files.py')
sf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sf)


def _f(tmp_path, name):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("objs\nend\n")
    return str(p)


def test_order_front_game_picked(tmp_path):
    a, b, c = (_f(tmp_path, n) for n in ('my.ide', 'data/gta.ide', 'pick.ide'))
    valid, missing = sf.merge_targets([a], [b], c)
    assert valid == [a, b, c] and missing == []


def test_duplicates_case_and_slashes_collapse(tmp_path):
    a = _f(tmp_path, 'data/maps/Mod.ide')
    b = _f(tmp_path, 'other.ide')
    alt = a.replace(os.sep, '/')
    if os.path.normcase('A') == os.path.normcase('a'):
        alt = alt.upper()                   # Windows: регистр не важен
    valid, missing = sf.merge_targets([b, a], [alt], alt)
    assert valid == [b, a] and missing == []


def test_picked_already_in_game_not_duplicated(tmp_path):
    a = _f(tmp_path, 'gta.ide')
    valid, _ = sf.merge_targets([], [a], a)
    assert valid == [a]


def test_missing_and_empty(tmp_path):
    a = _f(tmp_path, 'ok.ide')
    gone = str(tmp_path / 'gone.ide')
    valid, missing = sf.merge_targets(['', gone, a], [''], '')
    assert valid == [a] and missing == [gone]


def test_picked_used_without_game_and_with_list(tmp_path):
    """Без папки игры и с непустым списком выбранный файл всё равно читается
    (в Max — только когда больше ничего нет)."""
    a, c = _f(tmp_path, 'list.ide'), _f(tmp_path, 'picked.ide')
    valid, _ = sf.merge_targets([a], [], c)
    assert valid == [a, c]
