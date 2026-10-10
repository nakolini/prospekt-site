import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import lensmath as lm  # noqa: E402


class LensMathTest(unittest.TestCase):
    def test_full_frame_sensor_is_36_by_24(self):
        w, h = lm.sensor_size(1.0)
        self.assertAlmostEqual(w, 36.0, places=6)
        self.assertAlmostEqual(h, 24.0, places=6)

    def test_micro_four_thirds_is_4_by_3(self):
        w, h = lm.sensor_size(2.0)
        self.assertAlmostEqual(w, 17.31, places=2)
        self.assertAlmostEqual(h, 12.98, places=2)

    def test_medium_format_is_44_by_33(self):
        w, h = lm.sensor_size(0.79)
        self.assertAlmostEqual(w, 43.8, places=1)
        self.assertAlmostEqual(h, 32.9, places=1)

    def test_known_angles_of_view(self):
        h, v, d = lm.angles(50, 1.0)
        self.assertAlmostEqual(h, 39.6, places=1)
        self.assertAlmostEqual(v, 27.0, places=1)
        self.assertAlmostEqual(d, 46.8, places=1)
        self.assertAlmostEqual(lm.angles(24, 1.0)[0], 73.7, places=1)

    def test_equivalent_matches_full_frame_angle(self):
        # 35 mm on 1.5x frames like 52.5 mm on full frame (3:2 sensors).
        self.assertAlmostEqual(lm.angles(35, 1.5)[0], lm.angles(52.5, 1.0)[0], places=6)

    def test_frame_of_the_photo_focal_fills_the_photo(self):
        fw, fh = lm.frame_in_photo(14, 1.0, 14, 1.5)
        self.assertAlmostEqual(fw, 1.0)
        self.assertAlmostEqual(fh, 1.0)

    def test_frame_scales_inversely_with_focal(self):
        fw, fh = lm.frame_in_photo(28, 1.0, 14, 1.5)
        self.assertAlmostEqual(fw, 0.5)
        self.assertAlmostEqual(fh, 0.5)
        fw, _ = lm.frame_in_photo(35, 1.5, 14, 1.5)
        self.assertAlmostEqual(fw, 14 / 52.5)

    def test_four_thirds_frame_is_taller_than_three_two(self):
        fw, fh = lm.frame_in_photo(50, 2.0, 14, 1.5)
        self.assertAlmostEqual(fw / fh * 1.5, 4 / 3)

    def test_focal_for_equivalent(self):
        self.assertAlmostEqual(lm.focal_for_equivalent(50, 1.5), 33.333, places=3)
        self.assertEqual(lm.mm(33.333), "33 mm")


if __name__ == "__main__":
    unittest.main()
