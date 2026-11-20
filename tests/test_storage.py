import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.sessions import SessionStore
from security.types import LocalizationFix, RogueReport, SurveySample


class TestSessionStore(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.store = SessionStore(self.tmp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir)

    def test_save_and_load_round_trip(self):
        samples = [
            SurveySample(
                bssid="aa:bb:cc:dd:ee:01",
                x=10.0,
                y=20.0,
                rssi=-55.0,
                channel=6,
            ),
        ]
        fixes = [
            LocalizationFix(
                bssid="aa:bb:cc:dd:ee:01",
                x=10.5,
                y=20.3,
                covariance=__import__("numpy").eye(2),
                gdop=1.5,
                n_samples=5,
                rssi_error_sigma=2.0,
            ),
        ]
        alerts = [
            RogueReport(
                bssid="aa:bb:cc:dd:ee:01",
                ssid="MyCorp",
                classification="rogue",
                rules_hit=["Open network with corporate SSID"],
                confidence=0.85,
                channel=6,
            ),
        ]

        session_dir = self.store.save_session(samples, fixes, alerts)

        self.assertTrue(os.path.isdir(session_dir))
        self.assertTrue(os.path.exists(os.path.join(session_dir, "samples.json")))
        self.assertTrue(os.path.exists(os.path.join(session_dir, "fixes.csv")))
        self.assertTrue(os.path.exists(os.path.join(session_dir, "alerts.json")))
        self.assertTrue(os.path.exists(os.path.join(session_dir, "scan_summary.json")))
        self.assertTrue(os.path.exists(os.path.join(session_dir, "report.html")))

        loaded_samples = self.store.load_samples(session_dir)
        self.assertEqual(len(loaded_samples), 1)
        self.assertEqual(loaded_samples[0]["bssid"], "aa:bb:cc:dd:ee:01")
        self.assertAlmostEqual(loaded_samples[0]["x"], 10.0, delta=0.1)

        loaded_fixes = self.store.load_fixes(session_dir)
        self.assertEqual(len(loaded_fixes), 1)

    def test_empty_session(self):
        session_dir = self.store.save_session([], [], [], {})
        self.assertTrue(os.path.isdir(session_dir))
        loaded = self.store.load_samples(session_dir)
        self.assertEqual(len(loaded), 0)

    def test_report_contains_disclaimer(self):
        session_dir = self.store.save_session([], [], [], {})
        report_path = os.path.join(session_dir, "report.html")
        with open(report_path) as f:
            content = f.read()
        self.assertIn("AUTHORIZED USE ONLY", content)

    def test_report_contains_tables(self):
        samples = [
            SurveySample(
                bssid="aa:bb:cc:dd:ee:01",
                x=10.0,
                y=20.0,
                rssi=-55.0,
                channel=6,
            ),
        ]
        session_dir = self.store.save_session(samples, [], [], {})
        report_path = os.path.join(session_dir, "report.html")
        with open(report_path) as f:
            content = f.read()
        self.assertIn("Survey Samples", content)
        self.assertIn("aa:bb:cc:dd:ee:01", content)

    def test_report_escapes_untrusted_ap_values(self):
        alert = RogueReport(
            bssid="<bssid>",
            ssid="<script>alert(1)</script>",
            classification="rogue",
            rules_hit=["<img src=x onerror=alert(1)>"],
        )
        session_dir = self.store.save_session([], [], [alert], {})
        with open(os.path.join(session_dir, "report.html")) as report:
            content = report.read()
        self.assertNotIn("<script>alert(1)</script>", content)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", content)


if __name__ == "__main__":
    unittest.main()
