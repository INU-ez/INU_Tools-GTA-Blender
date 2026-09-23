# The GTA Material panel edits mat.diffuse_color (its "Цвет (RGBA)" swatch),
# but the DFF exporter used to read only the Principled Base Color / Alpha —
# so a hand-picked colour "reset" on export while the vehicle colour slot
# (which writes both places) kept working. _read_base_color now prefers the
# swatch whenever it differs from the import stamp `inu_dff_color`.
#
# dff_export imports bpy at module level, so pull the functions out by AST.

import ast
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "INU_tools", "ops", "dff_export.py")
sys.path.insert(0, os.path.join(ROOT, "INU_tools"))

from core.dff import RGBA  # noqa: E402

WANTED = {"_BL_DEFAULT_DIFFUSE", "_panel_color_override",
          "_read_base_color", "_get_principled"}


def _load():
    tree = ast.parse(io.open(MODULE, encoding="utf-8").read())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in WANTED:
            keep.append(node)
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(t in WANTED for t in targets):
                keep.append(node)
    ns = {"RGBA": RGBA}
    exec(compile(ast.Module(body=keep, type_ignores=[]), MODULE, "exec"), ns)
    return ns


NS = _load()
read_base_color = NS["_read_base_color"]


# ── minimal stand-ins for bpy material / node tree ──────────────────────

class _Socket:
    def __init__(self, value, is_linked=False):
        self.default_value = value
        self.is_linked = is_linked


class _Principled:
    type = 'BSDF_PRINCIPLED'

    def __init__(self, base=(1.0, 1.0, 1.0, 1.0), alpha=1.0):
        self.inputs = {'Base Color': _Socket(list(base)),
                       'Alpha': _Socket(alpha)}


class _Tree:
    def __init__(self, nodes):
        self.nodes = nodes


class _Mat:
    """Material as the importer leaves it: Base Color + diffuse_color +
    stamp all carry the DFF colour."""

    def __init__(self, dff=(255, 255, 255, 255), nodes=True):
        f = tuple(v / 255.0 for v in dff)
        self._props = {'inu_dff_color': f} if nodes else {}
        self.diffuse_color = list(f)
        self.use_nodes = nodes
        self.node_tree = _Tree([_Principled(base=f[:3] + (1.0,),
                                            alpha=f[3])]) if nodes else None

    def get(self, key):
        return self._props.get(key)

    def __setitem__(self, key, value):
        self._props[key] = value

    @property
    def principled(self):
        return self.node_tree.nodes[0]


def test_untouched_import_roundtrips_via_principled():
    mat = _Mat(dff=(200, 100, 50, 255))
    assert read_base_color(mat) == RGBA(200, 100, 50, 255)


def test_panel_swatch_wins_over_principled():
    # The Discord case: white decal texture, user picks black + alpha 0.949
    # in the panel; Base Color stays white (1,1,1) with Alpha 1.0.
    mat = _Mat(dff=(255, 255, 255, 255))
    mat.diffuse_color = [0.0, 0.0, 0.0, 0.949]
    assert read_base_color(mat) == RGBA(0, 0, 0, 242)


def test_shader_edit_still_honoured_when_swatch_untouched():
    mat = _Mat(dff=(255, 255, 255, 255))
    mat.principled.inputs['Base Color'].default_value = [0.5, 0.25, 0.125, 1.0]
    mat.principled.inputs['Alpha'].default_value = 0.5
    c = read_base_color(mat)
    assert (c.r, c.g, c.b) == (127, 63, 31)
    assert c.a == 127


def test_float32_noise_is_not_an_edit():
    mat = _Mat(dff=(242, 17, 90, 128))
    # diffuse_color comes back from RNA as float32
    mat.diffuse_color = [float.fromhex('0x1.e5e5e6p-1'), 17 / 255.0 + 1e-7,
                         90 / 255.0 - 1e-7, 128 / 255.0]
    mat.principled.inputs['Base Color'].default_value = [0.0, 1.0, 0.0, 1.0]
    # swatch equals stamp → shader route (green), not the swatch
    assert read_base_color(mat) == RGBA(0, 255, 0, 128)


def test_vehicle_slot_magic_colour_survives():
    # _on_vehicle_color_slot_update writes the marker into both places.
    mat = _Mat(dff=(255, 255, 255, 255))
    mat.diffuse_color = [60 / 255.0, 1.0, 0.0, 1.0]
    mat.principled.inputs['Base Color'].default_value = [60 / 255.0, 1.0, 0.0, 1.0]
    assert read_base_color(mat) == RGBA(60, 255, 0, 255)


def test_black_via_panel_is_reachable():
    # Pure black in the shader is treated as the game-look wipe and replaced
    # by diffuse_color; through the panel it must come out as 0,0,0.
    mat = _Mat(dff=(255, 255, 255, 255))
    mat.diffuse_color = [0.0, 0.0, 0.0, 1.0]
    assert read_base_color(mat) == RGBA(0, 0, 0, 255)


def test_no_stamp_uses_blender_default_as_reference():
    # Hand-made material, swatch never touched (0.8 grey) → shader route.
    mat = _Mat(dff=(0, 0, 255, 255))
    mat._props.clear()
    mat.diffuse_color = [0.8, 0.8, 0.8, 1.0]
    assert read_base_color(mat) == RGBA(0, 0, 255, 255)
    # …but a picked colour on the same material is honoured.
    mat.diffuse_color = [1.0, 0.0, 0.0, 0.5]
    assert read_base_color(mat) == RGBA(255, 0, 0, 128)


def test_old_import_without_colour_stamp_keeps_shader_route():
    # .blend from a version that stamped dff_texture_name but not
    # inu_dff_color: diffuse_color is the DFF colour (≠ 0.8 grey), which must
    # NOT be mistaken for a panel edit over a shader-side colour change.
    mat = _Mat(dff=(255, 255, 255, 255))
    mat._props.clear()
    mat['dff_texture_name'] = 'ambulbwdecal128'
    mat.principled.inputs['Base Color'].default_value = [0.5, 0.5, 0.5, 1.0]
    assert read_base_color(mat) == RGBA(127, 127, 127, 255)


def test_material_without_nodes_uses_swatch():
    mat = _Mat(dff=(10, 20, 30, 255), nodes=False)
    mat.diffuse_color = [0.2, 0.4, 0.6, 0.25]
    assert read_base_color(mat) == RGBA(51, 102, 153, 64)


def test_linked_base_color_exports_white():
    # Base Color connected to a texture: the socket's default_value (0.8 grey
    # → 204) is UI residue, not the real colour. With the MODULATE flag it
    # would darken the texture ~20% in-game / Ariane, so the material colour
    # must be neutral white. Alpha still comes from the Alpha input.
    mat = _Mat(dff=(255, 255, 255, 255))
    bc = mat.principled.inputs['Base Color']
    bc.default_value = [0.8, 0.8, 0.8, 1.0]
    bc.is_linked = True
    mat.principled.inputs['Alpha'].default_value = 0.5
    assert read_base_color(mat) == RGBA(255, 255, 255, 127)


def test_linked_base_color_swatch_still_wins():
    # An explicit panel swatch (differs from the import stamp) must still
    # override even when Base Color is linked — user intent wins.
    mat = _Mat(dff=(255, 255, 255, 255))
    mat.diffuse_color = [1.0, 0.0, 0.0, 1.0]
    bc = mat.principled.inputs['Base Color']
    bc.is_linked = True
    assert read_base_color(mat) == RGBA(255, 0, 0, 255)
