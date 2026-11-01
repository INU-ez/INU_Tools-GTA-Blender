"""Animated-object pivots must survive DFF frame and collision filtering.

Run without Blender: python dev/tests/test_animobj_frames_unit.py
"""

import ast
from pathlib import Path
import unittest


EXPORTER = Path(__file__).resolve().parents[2] / 'INU_tools/ops/dff_export.py'
HELPERS = {'_is_col_primitive_empty', '_collect_frame_objects'}
tree = ast.parse(EXPORTER.read_text(encoding='utf-8'))
namespace = {'is_collision_mesh': lambda obj: False}
exec(compile(ast.Module(body=[node for node in tree.body
                             if isinstance(node, ast.FunctionDef)
                             and node.name in HELPERS], type_ignores=[]),
             str(EXPORTER), 'exec'), namespace)
is_col_primitive = namespace['_is_col_primitive_empty']
collect_frames = namespace['_collect_frame_objects']


class Object:
    def __init__(self, name, kind='EMPTY', display='SPHERE', parent=None,
                 **props):
        self.name = name
        self.type = kind
        self.empty_display_type = display
        self.parent = parent
        self.children = []
        self.props = props
        if parent is not None:
            parent.children.append(self)

    def __contains__(self, key):
        return key in self.props

    def get(self, key, default=None):
        return self.props.get(key, default)


class AnimatedObjectFrameTests(unittest.TestCase):
    def test_rig_preserves_pivot_and_mesh_parent(self):
        for display in ('SPHERE', 'CUBE'):
            with self.subTest(display=display):
                root = Object('root', display='ARROWS',
                              inu_animobj_empty_root=True, inu_bone_id=0)
                pivot = Object('pivot', display=display, parent=root,
                               inu_animobj_empty_pivot=True, inu_bone_id=1,
                               dff_frame_write_name=True)
                mesh = Object('mesh', kind='MESH', parent=pivot)
                collision = Object('collision', parent=root)
                objects = [root, pivot, mesh, collision]
                self.assertEqual(collect_frames(objects),
                                 [(root, None), (pivot, root), (mesh, pivot)])
                # The same predicate also selects embedded COL primitives.
                self.assertEqual([o for o in objects if o.type == 'EMPTY'
                                  and is_col_primitive(o)], [collision])

    def test_each_rig_marker_identifies_a_frame(self):
        for props in ({'inu_bone_id': 0}, {'inu_bone_id': 1},
                      {'inu_animobj_empty_root': True},
                      {'inu_animobj_empty_pivot': True}):
            with self.subTest(props=props):
                self.assertFalse(is_col_primitive(Object('frame', **props)))

    def test_collision_and_imported_dummy_classification(self):
        for display in ('SPHERE', 'CUBE'):
            with self.subTest(display=display):
                self.assertTrue(is_col_primitive(Object('collision',
                                                        display=display)))
                for key in ('dff_frame_pos', 'dff_frame_rot', 'dff_frame_flags'):
                    self.assertFalse(is_col_primitive(Object(
                        'dummy', display=display, **{key: 0})))
        self.assertFalse(is_col_primitive(Object('axes', display='ARROWS')))


if __name__ == '__main__':
    unittest.main()
