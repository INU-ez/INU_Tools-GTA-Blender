"""UV diagnostics and portable bake preset validation, without Blender."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / 'INU_tools/tools/bake/bake_workflow.py'
spec = importlib.util.spec_from_file_location('bake_workflow', PATH)
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


class WorkflowTests(unittest.TestCase):
    def test_exact_stacks_and_touching_faces_are_not_partial_overlap(self):
        faces = {0: [(0, 0), (.5, 0), (.5, 1), (0, 1)],
                 1: [(.5, 0), (1, 0), (1, 1), (.5, 1)]}
        faces[2] = list(reversed(faces[0]))
        result = self.diagnose(faces)
        self.assertEqual(result['stacked'], [0, 2])
        self.assertEqual(result['overlap'], [])
        self.assertTrue(result['complete'])

    def test_partial_overlap_propagates_to_all_copies(self):
        faces = {0: [(0, 0), (1, 0), (0, 1)],
                 1: [(.1, .1), (.3, .1), (.1, .3)]}
        faces[2] = list(faces[0])
        self.assertEqual(self.diagnose(faces)['overlap'], [0, 1, 2])

    def test_invalid_and_tiled_uvs_are_separate(self):
        result = self.diagnose({0: [(0, 0), (1, 0), (2, 0)],
                               1: [(1.1, 0), (2, 0), (2, 1)]})
        self.assertEqual(result['degenerate'], [0])
        self.assertEqual(result['outside'], [1])

    def test_conflicts_compare_uv_edges_not_vertex_order(self):
        faces = {0: [(0, 0), (1, 0), (0, 1)], 1: [(0, 1), (1, 0), (0, 0)]}
        self.assertEqual(workflow.selection_uv_conflicts(faces, {0: [0], 1: [1]}), [])
        self.assertEqual(workflow.selection_uv_conflicts(faces, {0: [0], 1: [0]}), [0, 1])

    def test_provenance_handles_legacy_and_corruption(self):
        self.assertEqual(workflow.stamp_status(None, {}), 'MISSING')
        self.assertEqual(workflow.stamp_status({}, {}), 'UNKNOWN')
        self.assertEqual(workflow.stamp_status({workflow.STAMP: '{'}, {}), 'UNKNOWN')
        self.assertEqual(workflow.stamp_status({workflow.STAMP: '{"width": 1}'}, {'width': 1}), 'READY')
        self.assertEqual(workflow.stamp_status({workflow.STAMP: '{"width": 1}'}, {'width': 2}), 'STALE')

    def test_bad_presets_rejected_before_modification(self):
        for value in ([], {}, {'version': 2, 'layers': []}, {'version': 1, 'layers': [{}]},
                      {'version': 1, 'layers': [{'map_id': 'AO', 'paint_mask_index': 3}]}):
            with self.assertRaises(ValueError):
                workflow.validate_stack(value)
        rows = [{'map_id': 'DIRT', 'masks': [{'basis': 'DIRECTION', 'strength': .3}]}]
        self.assertEqual(workflow.validate_stack({'version': 1, 'layers': rows}), rows)

    def test_overlapping_uv_budget_is_explicit(self):
        faces = {i: [(i*.001, 0), (1+i*.001, 0), (i*.001, 1)] for i in range(20)}
        self.assertFalse(workflow.diagnose_uv(faces, [(i, p) for i, p in faces.items()], pair_limit=2)['complete'])

    def diagnose(self, faces):
        triangles = [(i, [uv[0], uv[j], uv[j+1]])
                     for i, uv in faces.items() for j in range(1, len(uv)-1)]
        return workflow.diagnose_uv(faces, triangles)


if __name__ == '__main__':
    unittest.main()
