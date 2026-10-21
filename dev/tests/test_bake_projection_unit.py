"""Alpha-aware pixel projection math, without Blender."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

PATH = Path(__file__).resolve().parents[2] / 'INU_tools/tools/bake/bake_projection.py'
spec = importlib.util.spec_from_file_location('bake_projection', PATH)
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)


class ProjectionTests(unittest.TestCase):
    def test_transparent_card_does_not_cover_bar(self):
        pixel = np.zeros(4)
        projection.over_sample(pixel, (0., 1., 0.), 0.)
        projection.over_sample(pixel, (.8, .1, .05), 1.)
        np.testing.assert_allclose(projection.straight_sample(pixel), (.8, .1, .05, 1.))

    def test_opaque_card_stays_in_front(self):
        pixel = np.zeros(4)
        projection.over_sample(pixel, (0., 1., 0.), 1.)
        projection.over_sample(pixel, (.8, .1, .05), 1.)
        np.testing.assert_allclose(projection.straight_sample(pixel), (0., 1., 0., 1.))

    def test_partial_alpha_composites_in_ray_order(self):
        pixel = np.zeros(4)
        projection.over_sample(pixel, (0., 1., 0.), .25)
        projection.over_sample(pixel, (.8, .1, .05), 1.)
        np.testing.assert_allclose(projection.straight_sample(pixel), (.6, .325, .0375, 1.))
        empty = np.zeros(4)
        projection.over_sample(empty, (0., 1., 0.), .25)
        np.testing.assert_allclose(projection.straight_sample(empty), (0., 1., 0., .25))

    def test_image_addressing_and_alpha_filter(self):
        image = np.array([[[1., 0., 0., 0.], [0., 1., 0., 1.]]])
        np.testing.assert_allclose(projection.sample_image(image, (.5, .5)), (.5, .5, 0., .5))
        np.testing.assert_allclose(projection.sample_image(image, (1.25, .5), nearest=True), image[0, 0])
        np.testing.assert_allclose(projection.sample_image(image, (1.25, .5), 'EXTEND'), image[0, 1])
        np.testing.assert_allclose(projection.sample_image(image, (1.25, .5), 'CLIP'), 0.)

    def test_batched_texture_samples_match_individual_samples(self):
        pixels = np.random.default_rng(31).random((8, 16, 4))
        points = np.random.default_rng(42).uniform(-2., 3., (100, 2))
        for extension in ('REPEAT', 'EXTEND', 'CLIP', 'MIRROR'):
            for nearest in (True, False):
                actual = projection.sample_image_batch(pixels, points, extension, nearest)
                expected = [projection.sample_image(pixels, point, extension, nearest) for point in points]
                np.testing.assert_allclose(actual, expected)

    def test_uv_raster_has_barycentric_weights_and_no_outside_writes(self):
        count = 0
        for rows, cols, weights in projection.uv_fragments([(0., 0.), (1., 0.), (0., 1.)], 16, 16):
            self.assertTrue(np.all(rows+cols <= 15))
            np.testing.assert_allclose(weights.sum(axis=1), 1.)
            count += len(rows)
        self.assertEqual(count, 136)

    def test_margin_does_not_fill_a_hole_inside_low_uv(self):
        pixels = np.ones((5, 5, 4))
        pixels[2, 2] = 0.
        coverage = np.zeros((5, 5), bool)
        coverage[1:4, 1:4] = True
        pixels[~coverage] = 0.
        result = projection.extend_margin(pixels, coverage, 1)
        np.testing.assert_array_equal(result[2, 2], 0.)
        np.testing.assert_array_equal(result[0, 0], 1.)


if __name__ == '__main__':
    unittest.main()
