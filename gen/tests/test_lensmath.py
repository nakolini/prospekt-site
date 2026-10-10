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

    def test_coverage_on_full_frame(self):
        # 50 mm at 10 m: 36/50 x 10 = 7.2 m wide, 24/50 x 10 = 4.8 m tall.
        w, h = lm.coverage(50, 1.0, 10)
        self.assertAlmostEqual(w, 7.2)
        self.assertAlmostEqual(h, 4.8)
        w, h = lm.coverage(24, 1.0, 1)
        self.assertAlmostEqual(w, 1.5)
        self.assertAlmostEqual(h, 1.0)

    def test_coverage_scales_with_distance_and_crop(self):
        w1, _ = lm.coverage(35, 1.0, 2)
        w2, _ = lm.coverage(35, 1.0, 4)
        self.assertAlmostEqual(w2, 2 * w1)
        # 33.3 mm on APS-C covers what 50 mm covers on full frame.
        self.assertAlmostEqual(lm.coverage(50 / 1.5, 1.5, 3)[0], lm.coverage(50, 1.0, 3)[0])
        # Feet in, feet out.
        self.assertAlmostEqual(lm.coverage(50, 1.0, 10 / lm.FOOT_M)[0] * lm.FOOT_M, 7.2)

    def test_four_thirds_coverage_is_4_by_3(self):
        w, h = lm.coverage(25, 2.0, 5)
        self.assertAlmostEqual(w / h, 4 / 3)

    def test_distance_to_fit_full_body(self):
        # 1.8 m filling 90% of a vertical full-frame frame: 2 m of frame height
        # over the 36 mm side. 85 mm: 2 x 85 / 36 = 4.72 m.
        self.assertAlmostEqual(lm.distance_to_fit(1.8, 85, 1.0), 2 * 85 / 36)
        self.assertAlmostEqual(lm.distance_to_fit(0.5, 85, 1.0), 0.5 / 0.9 * 85 / 36)
        # Horizontal framing uses the 24 mm side, so you stand 1.5x further away.
        self.assertAlmostEqual(lm.distance_to_fit(1.8, 85, 1.0, vertical=False),
                               1.5 * lm.distance_to_fit(1.8, 85, 1.0))
        self.assertAlmostEqual(lm.distance_to_fit(1.8, 50, 1.0, fill=1.0), 2.5)

    def test_distance_to_fit_inverts_coverage(self):
        for crop in [0.79, 1.0, 1.5, 1.6, 2.0]:
            d = lm.distance_to_fit(1.8, 85, crop, vertical=False, fill=1.0)
            self.assertAlmostEqual(lm.coverage(85, crop, d)[1], 1.8)
            d = lm.distance_to_fit(1.8, 85, crop, vertical=True, fill=1.0)
            self.assertAlmostEqual(lm.coverage(85, crop, d)[0], 1.8)

    def test_crop_body_stands_further_back(self):
        # Same lens, smaller sensor: tighter frame, so step back by the crop factor.
        self.assertAlmostEqual(lm.distance_to_fit(1.8, 85, 1.5), 1.5 * lm.distance_to_fit(1.8, 85, 1.0))


if __name__ == "__main__":
    unittest.main()
