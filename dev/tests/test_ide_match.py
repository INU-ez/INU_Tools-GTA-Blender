"""core/mapsync/ide_match — какую строку IDE берёт «Sync from IDE». Pure Python.

* Сначала своя связанная IDE модели (кроме устаревшей связи: Model ID
  сменили после связи — копия).
* Связь, записанная под именем ДРУГОЙ модели (III: импорт по ID через
  gta3.IDE), уступает строке с именем объекта и его Model ID.
* Имя в нескольких IDE с разными ID (или один ID с разными именами) —
  неоднозначно, если ни одна строка не совпала с Model ID объекта.
* LOD — только со строкой LOD, модель — только со строкой модели.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.ide import IdeObject  # noqa: E402
from core.mapsync.ide_match import (  # noqa: E402
    build_index, match_ide_row, unique,
)


def _e(mid, name, dd=100.0):
    return IdeObject(model_id=mid, model_name=name, txd_name=name,
                     draw_distance=dd)


def _match(files, cname, *, own=None, last_name='', last_id=0, mid=0,
           is_lod=False):
    """*files*: [(path, rows)]; *own*: path of the linked IDE (its rows are
    taken from *files*)."""
    rows = dict(files)
    own_ix = build_index([(own, rows[own])]) if own else None
    return match_ide_row(own_ix, build_index(files), cname, last_name,
                         last_id, mid, is_lod)


VANILLA = ('vanilla.ide', [_e(1280, 'bench'), _e(1281, 'LODbench')])
MOD = ('mod.ide', [_e(19000, 'bench'), _e(19001, 'tree1')])


def test_own_linked_ide_wins_over_earlier_file():
    hit, amb = _match([VANILLA, MOD], 'bench', own='mod.ide',
                      last_name='bench', last_id=19000, mid=19000)
    assert not amb and hit[1] == 'mod.ide' and hit[0].model_id == 19000


def test_different_ids_without_mid_match_ambiguous():
    hit, amb = _match([VANILLA, MOD], 'bench', mid=0)
    assert hit is None and amb == 'name'
    hit, amb = _match([VANILLA, MOD], 'bench', mid=555)
    assert hit is None and amb == 'name'


def test_different_ids_mid_picks_its_row():
    hit, amb = _match([VANILLA, MOD], 'bench', mid=19000)
    assert not amb and hit == (MOD[1][0], 'mod.ide')
    hit, amb = _match([VANILLA, MOD], 'bench', mid=1280)
    assert not amb and hit == (VANILLA[1][0], 'vanilla.ide')


def test_same_id_in_two_files_links_first():
    a = ('a.ide', [_e(700, 'house')])
    b = ('b.ide', [_e(700, 'HOUSE')])
    hit, amb = _match([a, b], 'house')
    assert not amb and hit[1] == 'a.ide'


def test_by_id_with_different_names_ambiguous():
    a = ('a.ide', [_e(700, 'house')])
    b = ('b.ide', [_e(700, 'shed')])
    hit, amb = _match([a, b], 'renamed', mid=700)
    assert hit is None and amb == 'id'
    # один файл — по ID связывается
    hit, amb = _match([a], 'renamed', mid=700)
    assert not amb and hit[0].model_name == 'house'


def test_lod_only_to_lod_row_and_model_only_to_model_row():
    hit, amb = _match([VANILLA], 'bench', is_lod=True, mid=0)
    assert not amb and hit[0].model_name == 'LODbench'
    # LOD с ID строки модели — не цепляется к ней
    f = ('x.ide', [_e(500, 'wall')])
    hit, amb = _match([f], 'wall', is_lod=True, mid=500)
    assert hit is None and not amb
    # модель с ID строки LOD — не цепляется к ней
    hit, amb = _match([VANILLA], 'renamed', mid=1281)
    assert hit is None and not amb


def test_lod_by_base_name():
    f = ('x.ide', [_e(301, 'house_lod')])
    hit, amb = _match([f], 'house', is_lod=True)
    assert not amb and hit[0].model_id == 301


def test_empty_last_name_does_not_hit_nameless_row():
    own = ('own.ide', [_e(42, ''), _e(43, 'shed')])
    hit, amb = _match([own], 'house', own='own.ide', last_name='', mid=0)
    assert hit is None and not amb


def test_own_ide_by_last_name_and_by_last_id():
    # переименованный объект: ищется по имени последней записи
    own = ('own.ide', [_e(42, 'house'), _e(43, 'shed')])
    hit, _ = _match([own], 'house_new', own='own.ide', last_name='house',
                    last_id=42, mid=42)
    assert hit[0].model_name == 'house'
    # имя в файле сменили — по ID последней записи
    own = ('own.ide', [_e(42, 'house_v2')])
    hit, _ = _match([own], 'house', own='own.ide', last_name='house',
                    last_id=42, mid=42)
    assert hit[0].model_name == 'house_v2'
    # текущее имя важнее имени последней записи, где бы оно ни стояло
    own = ('own.ide', [_e(42, 'house'), _e(44, 'house_new')])
    hit, _ = _match([own], 'house_new', own='own.ide', last_name='house',
                    last_id=42, mid=42)
    assert hit[0].model_name == 'house_new'


def test_own_ide_row_gone_falls_back_to_all_files():
    own = ('own.ide', [_e(43, 'shed')])
    hit, amb = _match([MOD, own], 'bench', own='own.ide', last_name='bench',
                      last_id=19000, mid=19000)
    assert not amb and hit[1] == 'mod.ide'


def test_stale_link_copy_not_snapped_back():
    """Копия «house2»: связь с own.ide (last 100/«house»), свой ID 300 —
    связь устарела, строка «house» ей не достаётся."""
    own = ('own.ide', [_e(100, 'house')])
    hit, amb = _match([own], 'house2', own='own.ide', last_name='house',
                      last_id=100, mid=300)
    assert hit is None and not amb


def test_link_to_another_models_row_iii_import():
    """Ванильный III: импорт связал по ID с неиспользуемым gta3.IDE, где под
    3004 другая модель. Строка с именем объекта И его Model ID важнее связи."""
    own = ('gta3.IDE', [_e(3004, 'Airportroad05'), _e(3005, 'Airportroad01')])
    other = ('landsw.ide', [_e(3004, 'Airportroad01')])
    for files in ([own, other], [other]):     # своя IDE в списке и вне его
        hit, amb = match_ide_row(build_index([own]), build_index(files),
                                 'airportroad01', 'Airportroad05', 3004, 3004,
                                 False)
        assert not amb and hit == (other[1][0], 'landsw.ide')


def test_lod_linked_to_model_row_takes_its_lod_row():
    """LOD, связанный импортом по ID со строкой МОДЕЛИ, получает LOD-строку
    со своим ID, а не LODhouse 501 из того же файла."""
    own = ('gta3.IDE', [_e(500, 'house'), _e(501, 'LODhouse')])
    other = ('area.ide', [_e(500, 'LODhouse')])
    hit, amb = _match([own, other], 'house', own='gta3.IDE',
                      last_name='house', last_id=500, mid=500, is_lod=True)
    assert not amb and hit == (other[1][0], 'area.ide')


def test_renamed_object_keeps_own_row_when_name_has_other_id():
    """Свою «house» (19002) переименовали в «bench»: ванильная bench 1280 —
    другой ID, связь не переезжает."""
    own = ('mod.ide', [_e(19002, 'house')])
    hit, amb = _match([VANILLA, own], 'bench', own='mod.ide',
                      last_name='house', last_id=19002, mid=19002)
    assert not amb and hit == (own[1][0], 'mod.ide')
    # под тем же ID в другом файле чужая модель — по ID связь не переезжает
    other = ('other.ide', [_e(19002, 'kiosk')])
    hit, amb = match_ide_row(build_index([own]), build_index([other]),
                             'house_new', 'house', 19002, 19002, False)
    assert not amb and hit == (own[1][0], 'mod.ide')


def test_unique_helper():
    a, b = _e(1, 'x'), _e(2, 'x')
    assert unique([], 0) == (None, False)
    assert unique([(a, 'p')], 0) == ((a, 'p'), False)
    assert unique([(a, 'p'), (b, 'q')], 0) == (None, True)
    assert unique([(a, 'p'), (b, 'q')], 2) == ((b, 'q'), False)


def test_unreadable_file_rows_none_ignored():
    idx = build_index([('bad.ide', None), MOD])
    assert [fp for _e_, fp in idx['by_name']['bench']] == ['mod.ide']
