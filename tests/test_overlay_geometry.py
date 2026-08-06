import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from security.types import LocalizationFix


class TestOverlayGeometry(unittest.TestCase):

    def test_ellipse_vertices_at_floor_z(self):
        fix = LocalizationFix(
            bssid="aa:bb:cc:dd:ee:01",
            x=50.0,
            y=50.0,
            covariance=np.eye(2) * 25.0,
            gdop=2.0,
            n_samples=8,
            rssi_error_sigma=3.0,
        )
        major = fix.ellipse_major
        minor = fix.ellipse_minor
        self.assertGreater(major, 0)
        self.assertGreater(minor, 0)

    def test_drop_line_endpoints(self):
        fix = LocalizationFix(
            bssid="aa:bb:cc:dd:ee:02",
            x=30.0,
            y=70.0,
            covariance=np.eye(2) * 9.0,
            gdop=1.5,
            n_samples=6,
            rssi_error_sigma=2.0,
        )
        self.assertEqual(fix.x, 30.0)
        self.assertEqual(fix.y, 70.0)
        self.assertGreaterEqual(fix.x, 0)
        self.assertLessEqual(fix.x, 100)
        self.assertGreaterEqual(fix.y, 0)
        self.assertLessEqual(fix.y, 100)

    def test_confidence_in_range(self):
        fix = LocalizationFix(
            bssid="aa:bb:cc:dd:ee:03",
            x=50.0,
            y=50.0,
            covariance=np.eye(2) * 1.0,
            gdop=1.0,
            n_samples=10,
            rssi_error_sigma=1.0,
        )
        self.assertGreaterEqual(fix.confidence, 0.1)
        self.assertLessEqual(fix.confidence, 0.99)

    def test_ellipse_major_greater_than_minor(self):
        fix = LocalizationFix(
            bssid="aa:bb:cc:dd:ee:04",
            x=50.0,
            y=50.0,
            covariance=np.array([[25.0, 0.0], [0.0, 4.0]]),
            gdop=2.0,
            n_samples=8,
            rssi_error_sigma=3.0,
        )
        self.assertGreater(fix.ellipse_major, fix.ellipse_minor)

    def test_zero_covariance_ellipse(self):
        fix = LocalizationFix(
            bssid="aa:bb:cc:dd:ee:05",
            x=50.0,
            y=50.0,
            covariance=np.zeros((2, 2)),
            gdop=0.0,
            n_samples=1,
            rssi_error_sigma=0.0,
        )
        self.assertEqual(fix.ellipse_major, 0.0)
        self.assertEqual(fix.ellipse_minor, 0.0)


if __name__ == "__main__":
    unittest.main()