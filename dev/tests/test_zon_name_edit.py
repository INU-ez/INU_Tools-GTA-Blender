# The map.zon panel showed «Имя» as a raw ID property (obj["zon_name"]), but
# the exporter (_zone_name) prefers the object-name base whenever it differs
# from the stored name — so typing a new name in the field was silently lost
# (Add Zone → Zone_NEW, type «LA99» → the file still got «NEW»). The field is
# now obj.inu.zon_name_edit, whose setter stores zon_name AND renames the box
# «Zone_<name>», the way Max's adapter/zon.rename does.
#
# __init__.py and ops/zon_ops.py import bpy at module level, so pull the
# functions out by AST.

import ast
import io
import os
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INIT = os.path.join(ROOT, "INU_tools", "__init__.py")
ZON_OPS = os.path.join(ROOT, "INU_tools", "ops", "zon_ops.py")


def _extract(path, wanted, ns):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in keep} == set(wanted), path
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, "exec"), ns)


NS = {}
_extract(INIT, {"_zon_name_get", "_zon_name_set"}, NS)
_extract(ZON_OPS, {"_strip_dup_suffix", "_zone_name"}, NS)
zon_get = NS["_zon_name_get"]
zon_set = NS["_zon_name_set"]
zone_name = NS["_zone_name"]


class _Obj(dict):
    """Object stand-in: ID properties via the dict, `.name` as an attribute."""

    def __init__(self, name, **props):
        super().__init__(props)
        self.name = name


def _inu(obj):
    # obj.inu — the PropertyGroup; its id_data is the object itself.
    return types.SimpleNamespace(id_data=obj)


def _zone(name, zon_name):
    # A zone box as import_zon / Add Zone build it: tagged 'inu_zon'.
    return _Obj(name, inu_zon=1, zon_name=zon_name)


def test_edit_renames_box_and_replaces_spaces():
    ob = _zone("Zone_LA01", "LA01")
    zon_set(_inu(ob), "LA 02")
    assert ob["zon_name"] == "LA_02"
    assert ob.name == "Zone_LA_02"
    assert zone_name(ob) == "LA_02"


def test_new_zone_edit_reaches_the_file():
    # The bug: Add Zone → Zone_NEW / «NEW», user types «LA99» in «Имя».
    ob = _zone("Zone_NEW", "NEW")
    zon_set(_inu(ob), "LA99")
    assert zone_name(ob) == "LA99"


def test_old_raw_edit_was_lost():
    # What editing obj["zon_name"] directly used to do: object name wins.
    ob = _Obj("Zone_NEW", zon_name="LA99")
    assert zone_name(ob) == "NEW"


def test_empty_value_changes_nothing():
    # apply_2dfx_to_selected copies every writable obj.inu property; a 2DFX
    # source has no zon_name, so '' arrives here and must be a no-op.
    for value in ("", "   ", " , "):
        ob = _Obj("Empty.002")
        zon_set(_inu(ob), value)
        assert "zon_name" not in ob
        assert ob.name == "Empty.002"

        zb = _zone("Zone_LA01", "LA01")
        zon_set(_inu(zb), value)
        assert zb["zon_name"] == "LA01"
        assert zb.name == "Zone_LA01"


def test_non_zone_object_is_untouched():
    # Alt+Enter / «Copy to Selected» apply inu.zon_name_edit to every selected
    # object — a building mesh in the selection must keep its model name.
    ob = _Obj("lae_building01")
    zon_set(_inu(ob), "LA99")
    assert "zon_name" not in ob
    assert ob.name == "lae_building01"


def test_getter_without_key_is_empty():
    assert zon_get(_inu(_Obj("Empty"))) == ""
    assert zon_get(_inu(_Obj("Zone_X", zon_name="X"))) == "X"


def test_commas_and_whitespace_collapse_to_one_underscore():
    # The engine turns ',' into a space and splits on any whitespace.
    ob = _zone("Zone_A", "A")
    zon_set(_inu(ob), "  SF,DOCKS \t 2 ")
    assert ob["zon_name"] == "SF_DOCKS_2"
    assert ob.name == "Zone_SF_DOCKS_2"


def test_name_clash_suffix_is_stripped_on_export():
    # Blender appends .001 when «Zone_LA99» is already taken.
    ob = _Obj("Zone_LA99.001", zon_name="LA99")
    assert zone_name(ob) == "LA99"
