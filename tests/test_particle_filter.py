import math
import os
import sys
import tempfile
import time
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfmap.localization.particle_filter import ParticleFilter, _path_loss_predicted, _wall_attenuation
from rfmap.models import APObservation
from rfmap.core.geometry import Obstacle

from tests import ring_samples


class TestParticleFilter(unittest.TestCase):

    def test_converges_to_truth(self):
        pf = ParticleFilter(n_particles=2000, sigma=4.0)
        true_x, true_y = 50.0, 50.0
        samples = ring_samples(true_x, true_y, 8, dist=15.0)

        pf.seed_around(50.0, 50.0, spread=20.0)
        for sample in samples:
            pf.update([sample])

        x, y, spread = pf.estimate()
        error = math.sqrt((x - true_x) ** 2 + (y - true_y) ** 2)
        self.assertLess(error, 10.0)

    def test_pf_with_wall_closer_than_ls(self):
        pf = ParticleFilter(n_particles=500, sigma=4.0)
        true_x, true_y = 50.0, 50.0
        wall = Obstacle(40, 30, 60, 70, "Brick")

        samples = []
        for i in range(6):
            angle = i * 2 * math.pi / 6
            dist = 12.0
            x = true_x + dist * math.cos(angle)
            y = true_y + dist * math.sin(angle)
            d = math.sqrt((x - true_x) ** 2 + (y - true_y) ** 2)
            rssi = -30.0 - 10.0 * 2.4 * math.log10(max(d, 1.0))
            rssi -= wall.attenuation_db  # simulate wall attenuation
            samples.append((x, y, rssi))

        pf.seed_around(50.0, 50.0, spread=20.0)
        for sample in samples:
            pf.update([sample], obstacles=[wall])

        x, y, spread = pf.estimate()
        self.assertGreaterEqual(x, 0)
        self.assertLessEqual(x, 100)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(y, 100)

    def test_performance(self):
        pf = ParticleFilter(n_particles=500, sigma=4.0)
        true_x, true_y = 50.0, 50.0
        samples = ring_samples(true_x, true_y, 12, dist=15.0)

        pf.seed_around(50.0, 50.0, spread=20.0)
        start = time.perf_counter()
        for sample in samples:
            pf.update([sample])
        elapsed = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed, 100, f"PF recompute took {elapsed:.1f} ms, expected < 100 ms")

    def test_systematic_resample(self):
        pf = ParticleFilter(n_particles=100, sigma=4.0)
        pf._init_uniform()
        pf._weights = np.ones(100) / 100
        indices = pf._systematic_resample()
        self.assertEqual(len(indices), 100)
        self.assertTrue(all(0 <= i < 100 for i in indices))

    def test_path_loss_predicted(self):
        rssi = _path_loss_predicted(-30.0, 10.0)
        expected = -30.0 - 10.0 * 2.4 * math.log10(10.0)
        self.assertAlmostEqual(rssi, expected, delta=0.01)

    def test_wall_attenuation(self):
        wall = Obstacle(0, 0, 10, 10, "Brick")
        att = _wall_attenuation(5.0, 5.0, 15.0, 15.0, [wall])
        self.assertGreater(att, 0)

        att_no_wall = _wall_attenuation(5.0, 5.0, 15.0, 15.0, [])
        self.assertEqual(att_no_wall, 0.0)


class TestAPLocalizerWithParticleFilter(unittest.TestCase):

    def test_pf_refines_ls_fix(self):
        from rfmap.localization.localizer import APLocalizer

        localizer = APLocalizer("aa:bb:cc:dd:ee:02")
        true_x, true_y = 40.0, 60.0
        for sample in ring_samples(true_x, true_y, 8, dist=15.0):
            localizer.add_sample(sample)

        fix = localizer.fix
        self.assertIsNotNone(fix)
        self.assertIsNotNone(fix.particle_centroid)


if __name__ == "__main__":
    unittest.main()