import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfmap.localization.localizer import APLocalizer

from tests import ring_samples, make_sample


class TestLocalizationCore(unittest.TestCase):

    def test_ring_survey_fix_within_tolerance(self):
        localizer = APLocalizer("aa:bb:cc:dd:ee:02")
        true_x, true_y = 40.0, 60.0
        for sample in ring_samples(true_x, true_y, 8, dist=15.0):
            localizer.add_sample(sample)

        fix = localizer.fix
        self.assertIsNotNone(fix)
        error = math.sqrt((fix.x - true_x) ** 2 + (fix.y - true_y) ** 2)
        self.assertLess(error, 1.5)

    def test_collinear_samples_high_gdop(self):
        localizer = APLocalizer("aa:bb:cc:dd:ee:02")
        for i in range(5):
            x = float(i * 5)
            y = 10.0
            rssi = -50.0 - i
            localizer.add_sample(make_sample(x, y, rssi))

        fix = localizer.fix
        self.assertIsNotNone(fix)
        self.assertGreater(fix.gdop, 1.0)

    def test_fewer_than_3_samples_no_fix(self):
        localizer = APLocalizer("aa:bb:cc:dd:ee:02")
        localizer.add_sample(make_sample(10, 10, -50))
        localizer.add_sample(make_sample(20, 20, -55))
        self.assertIsNone(localizer.fix)

    def test_outlier_robustness(self):
        localizer = APLocalizer("aa:bb:cc:dd:ee:02")
        true_x, true_y = 40.0, 60.0
        for sample in ring_samples(true_x, true_y, 8, dist=15.0):
            localizer.add_sample(sample)

        localizer.add_sample(make_sample(40.0, 60.0, -30.0 + 15.0))

        fix = localizer.fix
        self.assertIsNotNone(fix)
        error = math.sqrt((fix.x - true_x) ** 2 + (fix.y - true_y) ** 2)
        self.assertLess(error, 3.0)

    def test_fix_has_ellipse_properties(self):
        localizer = APLocalizer("aa:bb:cc:dd:ee:02")
        true_x, true_y = 40.0, 60.0
        for sample in ring_samples(true_x, true_y, 6, dist=12.0):
            localizer.add_sample(sample)

        fix = localizer.fix
        self.assertIsNotNone(fix)
        self.assertGreater(fix.ellipse_major, 0)
        self.assertGreater(fix.ellipse_minor, 0)
        self.assertGreaterEqual(fix.confidence, 0.1)
        self.assertLessEqual(fix.confidence, 0.99)

    def test_fix_within_grid_bounds(self):
        localizer = APLocalizer("aa:bb:cc:dd:ee:02")
        for i in range(5):
            x = float(10 + i * 3)
            y = float(10 + i * 2)
            rssi = -50.0 - i
            localizer.add_sample(make_sample(x, y, rssi))

        fix = localizer.fix
        self.assertIsNotNone(fix)
        self.assertGreaterEqual(fix.x, 0)
        self.assertLessEqual(fix.x, 100)
        self.assertGreaterEqual(fix.y, 0)
        self.assertLessEqual(fix.y, 100)


if __name__ == "__main__":
    unittest.main()