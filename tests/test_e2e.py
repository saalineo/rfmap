import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.ap_scanner import SimulatedScanner
from security.detection import RogueDetector
from security.localization import APLocalizer
from security.types import APObservation, SurveySample
from security.sessions import SessionStore
from security.allowlist import WhitelistStore

from tests import ring_samples


class TestE2E(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_full_chain(self):
        scanner = SimulatedScanner()
        observations = scanner.scan()
        self.assertGreater(len(observations), 0)

        whitelist_path = os.path.join(self.tmp, "allowlist.json")
        store = WhitelistStore(whitelist_path)
        store.add_entry(bssid="aabbccddee01", ssid="MyCorp-WPA")

        detector = RogueDetector(store)
        reports = detector.classify(observations)

        rogue_bssids = [b for b, r in reports.items() if r.classification == "rogue"]
        self.assertGreater(len(rogue_bssids), 0)

        target_bssid = rogue_bssids[0]
        localizer = APLocalizer(target_bssid)

        true_obs = next(o for o in observations if o.bssid == target_bssid)
        true_x, true_y = 30.0, 40.0

        for sample in ring_samples(true_x, true_y, 10, dist=12.0, bssid=target_bssid, channel=true_obs.channel):
            localizer.add_sample(sample)

        fix = localizer.fix
        self.assertIsNotNone(fix)
        error = math.sqrt((fix.x - true_x) ** 2 + (fix.y - true_y) ** 2)
        self.assertLess(error, 3.0)

        session_dir = os.path.join(self.tmp, "session")
        os.makedirs(session_dir, exist_ok=True)
        store = SessionStore(session_dir)
        saved_dir = store.save_session(
            localizer.samples,
            [fix] if fix else [],
            list(reports.values()),
            {"source": "simulated"},
        )
        self.assertTrue(os.path.isdir(saved_dir))
        self.assertTrue(os.path.exists(os.path.join(saved_dir, "report.html")))

        loaded = store.load_samples(saved_dir)
        self.assertEqual(len(loaded), n_samples)

    def test_evil_twin_detection_chain(self):
        whitelist_path = os.path.join(self.tmp, "allowlist.json")
        store = WhitelistStore(whitelist_path)
        store.add_entry(bssid="aabbccddee01", ssid="MyCorp-WPA")

        evil_twin = APObservation(
            bssid="aabbccddee02",
            ssid="MyCorp-WPA",
            channel=6,
            frequency_mhz=2437,
            rssi=-50.0,
            security="WPA2-Personal",
            source="test",
        )

        detector = RogueDetector(store)
        reports = detector.classify([evil_twin])
        self.assertEqual(reports["aabbccddee02"].classification, "rogue")

    def test_localization_round_trip(self):
        bssid = "aa:bb:cc:dd:ee:03"
        localizer = APLocalizer(bssid)

        samples = ring_samples(50.0, 50.0, 8, dist=10.0, bssid=bssid, channel=6)
        for sample in samples:
            localizer.add_sample(sample)

        fix = localizer.fix
        self.assertIsNotNone(fix)

        session_dir = os.path.join(self.tmp, "roundtrip")
        os.makedirs(session_dir, exist_ok=True)
        store = SessionStore(session_dir)
        saved_dir = store.save_session(samples, [fix], [])
        loaded_samples = store.load_samples(saved_dir)
        self.assertEqual(len(loaded_samples), 8)


if __name__ == "__main__":
    unittest.main()