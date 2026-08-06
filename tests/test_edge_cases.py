import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.ap_scanner import _parse_iw_scan, _normalize_mac
from security.detection import RogueDetector, _is_locally_administered_mac
from security.localization import APLocalizer
from security.types import SurveySample


class TestEdgeCases(unittest.TestCase):

    def test_normalize_mac_various_formats(self):
        self.assertEqual(_normalize_mac("00:11:22:33:44:55"), "001122334455")
        self.assertEqual(_normalize_mac("00-11-22-33-44-55"), "001122334455")
        self.assertEqual(_normalize_mac("00.11.22.33.44.55"), "001122334455")
        self.assertEqual(_normalize_mac("001122334455"), "001122334455")

    def test_empty_iw_scan(self):
        results = _parse_iw_scan("", source="test")
        self.assertEqual(len(results), 0)

    def test_malformed_iw_scan(self):
        results = _parse_iw_scan(
            "BSS invalid_mac\n    garbage line\nBSS 00:11:22:33:44:55\n    SSID: Valid",
            source="test",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].bssid, "001122334455")

    def test_hidden_ssid_empty_string(self):
        results = _parse_iw_scan(
            "BSS aa:bb:cc:dd:ee:01\n    SSID: \n    signal: -50.00 dBm\n",
            source="test",
        )
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].ssid)

    def test_nan_rssi_skipped(self):
        results = _parse_iw_scan(
            "BSS aa:bb:cc:dd:ee:01\n    SSID: Test\n    signal: NaN dBm\n",
            source="test",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].rssi, -100.0)

    def test_empty_whitelist(self):
        store = type("obj", (), {"match": lambda self, b, s: None})()
        detector = RogueDetector(store)
        from security.types import APObservation
        import time
        obs = [APObservation(
            bssid="aa:bb:cc:dd:ee:01", ssid="Unknown",
            channel=6, frequency_mhz=2437, rssi=-50,
            security="WPA2-Personal", first_seen=time.time(), source="test",
        )]
        reports = detector.classify(obs)
        self.assertEqual(reports["aa:bb:cc:dd:ee:01"].classification, "suspicious")

    def test_survey_click_clamping(self):
        localizer = APLocalizer("test")
        sample = SurveySample(
            bssid="test",
            x=150.0,
            y=-10.0,
            rssi=-50.0,
            channel=6,
        )
        localizer.add_sample(sample)
        self.assertEqual(localizer.n_samples, 1)
        self.assertGreaterEqual(localizer.samples[0].x, 0)

    def test_locally_administered_mac_edge_cases(self):
        self.assertFalse(_is_locally_administered_mac(""))
        self.assertFalse(_is_locally_administered_mac("00:11"))
        self.assertTrue(_is_locally_administered_mac("02:00:00:00:00:01"))
        self.assertFalse(_is_locally_administered_mac("00:00:00:00:00:00"))

    def test_ap_disappears_mid_survey(self):
        localizer = APLocalizer("test")
        for i in range(5):
            sample = SurveySample(
                bssid="test",
                x=float(i * 5),
                y=float(i * 3),
                rssi=-50.0,
                channel=6,
            )
            localizer.add_sample(sample)
        self.assertEqual(localizer.n_samples, 5)

    def test_duplicate_bssid_in_scan(self):
        results = _parse_iw_scan(
            "BSS aa:bb:cc:dd:ee:01\n    SSID: Test1\n    signal: -50.00 dBm\n"
            "BSS aa:bb:cc:dd:ee:01\n    SSID: Test2\n    signal: -60.00 dBm\n",
            source="test",
        )
        self.assertEqual(len(results), 2)

    def test_rssi_floor_rejection(self):
        localizer = APLocalizer("test")
        sample = SurveySample(
            bssid="test",
            x=10.0,
            y=10.0,
            rssi=-100.0,
            channel=6,
        )
        localizer.add_sample(sample)
        self.assertEqual(localizer.n_samples, 0)

    def test_empty_scan_results(self):
        results = _parse_iw_scan("", source="test")
        self.assertEqual(len(results), 0)

    def test_very_short_ssid(self):
        results = _parse_iw_scan(
            "BSS aa:bb:cc:dd:ee:01\n    SSID: A\n    signal: -50.00 dBm\n",
            source="test",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].ssid, "A")


if __name__ == "__main__":
    unittest.main()