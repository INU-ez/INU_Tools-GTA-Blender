"""core/mapsync/groups — the meshes of one placement. Pure Python.

The game draws every atomic of a map model with its IPL row's matrix, so the
meshes of one model at one spot (bar_barrier10_L0 + bar_barrier10_dam) are
one placement: one row, one model name.
"""

from pathlib import Path
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "INU_tools"))

from core.mapsync import (  # noqa: E402
    group_instances, game_model_name, is_damage_part,
)

Q0 = (1.0, 0.0, 0.0, 0.0)              # (w, x, y, z)


def _zrot(deg):
    h = math.radians(deg) / 2
    return (math.cos(h), 0.0, 0.0, math.sin(h))


def _groups(items):
    return sorted(sorted(g) for g in group_instances(items))


# ── group_instances ─────────────────────────────────────────────────

def test_same_id_same_spot_one_group():
    items = [('L0', 1461, (10.0, 20.0, 3.0), Q0),
             ('dam', 1461, (10.0, 20.0, 3.0), Q0)]
    assert _groups(items) == [['L0', 'dam']]


def test_one_metre_apart_two_groups():
    items = [('a', 1461, (10.0, 20.0, 3.0), Q0),
             ('b', 1461, (11.0, 20.0, 3.0), Q0)]
    assert _groups(items) == [['a'], ['b']]


def test_float32_noise_is_one_spot():
    items = [('a', 7, (2233.8032, -1117.8828, 102.0391), Q0),
             ('b', 7, (2233.80322265625, -1117.8828, 102.0391), Q0)]
    assert _groups(items) == [['a', 'b']]


def test_minus_q_is_one_rotation():
    q = _zrot(90)
    items = [('a', 5, (0.0, 0.0, 0.0), q),
             ('b', 5, (0.0, 0.0, 0.0), tuple(-c for c in q))]
    assert _groups(items) == [['a', 'b']]


def test_turned_is_another_placement():
    items = [('a', 5, (0.0, 0.0, 0.0), _zrot(0)),
             ('b', 5, (0.0, 0.0, 0.0), _zrot(10))]
    assert _groups(items) == [['a'], ['b']]


def test_unnormalized_quaternion_still_matches():
    """A 4-digit vanilla row (norm ≠ 1) against the matrix's own quaternion."""
    items = [('a', 5, (0.0, 0.0, 0.0), (0.7071, 0.0, 0.0, -0.7071)),
             ('b', 5, (0.0, 0.0, 0.0), _zrot(-90))]
    assert _groups(items) == [['a', 'b']]


def test_different_ids_two_groups():
    items = [('a', 100, (0.0, 0.0, 0.0), Q0),
             ('b', 101, (0.0, 0.0, 0.0), Q0)]
    assert _groups(items) == [['a'], ['b']]


def test_every_key_once_in_input_order():
    items = [('b1', 2, (5.0, 0.0, 0.0), Q0),
             ('a1', 1, (0.0, 0.0, 0.0), Q0),
             ('b2', 2, (5.0, 0.0, 0.0), Q0),
             ('a2', 1, (0.0, 0.0, 0.0), Q0),
             ('c', 3, (0.0, 0.0, 0.0), Q0)]
    assert group_instances(items) == [['b1', 'b2'], ['a1', 'a2'], ['c']]
    assert group_instances([]) == []


def test_many_placements_of_one_model():
    """A model placed along a line: only the pairs at one spot join."""
    items = []
    for k in range(200):
        items.append((('m', k), 9, (k * 0.5, 0.0, 0.0), Q0))
        if k % 50 == 0:
            items.append((('d', k), 9, (k * 0.5, 0.0, 0.0), Q0))
    groups = group_instances(items)
    assert len(groups) == 200
    pairs = [g for g in groups if len(g) == 2]
    assert sorted(g[0][1] for g in pairs) == [0, 50, 100, 150]


# ── game_model_name / is_damage_part ────────────────────────────────

def test_game_model_name():
    assert game_model_name('bar_barrier10_L0') == 'bar_barrier10'
    assert game_model_name('bar_barrier10_l1') == 'bar_barrier10'
    assert game_model_name('sand_josh1_dam') == 'sand_josh1'
    assert game_model_name('Sand_Josh1_DAM') == 'Sand_Josh1'
    for keep in ('lodfoo', 'road_l0x', 'bar_barrier10', 'hotel_damaged',
                 'house_L', '_dam', ''):
        assert game_model_name(keep) == keep


def test_is_damage_part():
    for dam in ('bar_barrier10_dam', 'bar_barrier10_dam_DFF',
                'bar_barrier10_dam_DFF.001', 'SAND_JOSH1_DAM'):
        assert is_damage_part(dam)
    for whole in ('bar_barrier10_L0_DFF', 'hotel_damaged', 'dam_house',
                  'amsterdam', ''):
        assert not is_damage_part(whole)
