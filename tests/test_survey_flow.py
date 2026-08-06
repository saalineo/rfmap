import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.localization import APLocalizer
from security.types import SurveySample


class TestSurveyFlow(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp.close()
        self.localizer = APLocalizer("aa:bb:cc:dd:ee:02")

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_add_sample_stores_sample(self):
        sample = SurveySample(
            bssid="aa:bb:cc:dd:ee:02",
            x=10.0,
            y=20.0,
            rssi=-55.0,
            channel=6,
        )
        self.localizer.add_sample(sample)
        self.assertEqual(self.localizer.n_samples, 1)
        self.assertEqual(self.localizer.samples[0].x, 10.0)
        self.assertEqual(self.localizer.samples[0].y, 20.0)

    def test_wrong_bssid_ignored(self):
        sample = SurveySample(
            bssid="aa:bb:cc:dd:ee:99",
            x=10.0,
            y=20.0,
            rssi=-55.0,
            channel=6,
        )
        self.localizer.add_sample(sample)
        self.assertEqual(self.localizer.n_samples, 0)

    def test_rssi_floor_rejected(self):
        sample = SurveySample(
            bssid="aa:bb:cc:dd:ee:02",
            x=10.0,
            y=20.0,
            rssi=-100.0,
            channel=6,
        )
        self.localizer.add_sample(sample)
        self.assertEqual(self.localizer.n_samples, 0)

    def test_no_fix_with_fewer_than_3_samples(self):
        for i in range(2):
            sample = SurveySample(
                bssid="aa:bb:cc:dd:ee:02",
                x=float(i * 5),
                y=float(i * 3),
                rssi=-55.0,
                channel=6,
            )
            self.localizer.add_sample(sample)
        self.assertIsNone(self.localizer.fix)

    def test_fix_with_3_samples(self):
        import math
        for i in range(3):
            angle = i * 2 * math.pi / 3
            x = 50.0 + 10.0 * math.cos(angle)
            y = 50.0 + 10.0 * math.sin(angle)
            dist = math.sqrt((x - 50.0) ** 2 + (y - 50.0) ** 2)
            rssi = -30.0 - 10.0 * 2.4 * math.log10(max(dist, 1.0))
            sample = SurveySample(
                bssid="aa:bb:cc:dd:ee:02",
                x=x,
                y=y,
                rssi=rssi,
                channel=6,
            )
            self.localizer.add_sample(sample)
        fix = self.localizer.fix
        self.assertIsNotNone(fix)
        self.assertEqual(fix.n_samples, 3)

    def test_samples_persist_across_adds(self):
        for i in range(5):
            sample = SurveySample(
                bssid="aa:bb:cc:dd:ee:02",
                x=float(i * 2),
                y=float(i * 3),
                rssi=-55.0 - i,
                channel=6,
            )
            self.localizer.add_sample(sample)
        self.assertEqual(self.localizer.n_samples, 5)


if __name__ == "__main__":
    unittest.main()