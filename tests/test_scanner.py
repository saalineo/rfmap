import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.ap_scanner import IwScanner, SimulatedScanner, _parse_iw_scan
from security.types import APObservation


class TestIwScanParsing(unittest.TestCase):

    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tests", "fixtures", "iw_scan_sample.txt",
        )

    def test_fixture_parsing(self):
        with open(self.fixture_path) as f:
            output = f.read()
        results = _parse_iw_scan(output, source="fixture")
        self.assertEqual(len(results), 6)

    def test_fixture_has_trusted_wpa(self):
        with open(self.fixture_path) as f:
            output = f.read()
        results = _parse_iw_scan(output, source="fixture")
        trusted = [r for r in results if r.bssid == "001122334455"]
        self.assertEqual(len(trusted), 1)
        self.assertEqual(trusted[0].ssid, "MyCorp-WPA")
        self.assertEqual(trusted[0].security, "WPA2/WPA3")
        self.assertEqual(trusted[0].channel, 36)

    def test_fixture_has_hidden_bss(self):
        with open(self.fixture_path) as f:
            output = f.read()
        results = _parse_iw_scan(output, source="fixture")
        hidden = [r for r in results if r.ssid is None]
        self.assertGreaterEqual(len(hidden), 2)

    def test_fixture_has_open_bss(self):
        with open(self.fixture_path) as f:
            output = f.read()
        results = _parse_iw_scan(output, source="fixture")
        open_aps = [r for r in results if r.security == "open"]
        self.assertGreaterEqual(len(open_aps), 3)

    def test_fixture_rssi_values(self):
        with open(self.fixture_path) as f:
            output = f.read()
        results = _parse_iw_scan(output, source="fixture")
        for obs in results:
            self.assertGreaterEqual(obs.rssi, -100.0)
            self.assertLessEqual(obs.rssi, -25.0)

    def test_fixture_bssid_normalized(self):
        with open(self.fixture_path) as f:
            output = f.read()
        results = _parse_iw_scan(output, source="fixture")
        for obs in results:
            self.assertEqual(obs.bssid, obs.bssid.lower())
            self.assertNotIn(":", obs.bssid)
            self.assertNotIn("-", obs.bssid)

    def test_simulated_scanner(self):
        scanner = SimulatedScanner()
        results = scanner.scan()
        self.assertEqual(len(results), 5)
        for obs in results:
            self.assertIsInstance(obs, APObservation)
            self.assertIsNotNone(obs.bssid)
            self.assertGreaterEqual(obs.rssi, -95.0)
            self.assertLessEqual(obs.rssi, -25.0)

    def test_simulated_has_hidden_ap(self):
        scanner = SimulatedScanner()
        results = scanner.scan()
        hidden = [r for r in results if r.ssid is None]
        self.assertGreaterEqual(len(hidden), 1)

    def test_scanner_env_fixture_override(self):
        os.environ["SENTINEL_SCANNER"] = self.fixture_path
        try:
            scanner = IwScanner()
            results = scanner.scan()
            self.assertGreater(len(results), 0)
        finally:
            del os.environ["SENTINEL_SCANNER"]


class TestNetshScanner(unittest.TestCase):

    def test_netsh_parsing(self):
        output = (
            "SSID 1 : MyCorp\n"
            "    Network type            : Infrastructure\n"
            "    Authentication          : WPA2-Personal\n"
            "    Encryption              : CCMP\n"
            "    BSSID 1                 : 00:11:22:33:44:55\n"
            "         Signal             : 82%\n"
        )
        scanner = type("NetshScanner", (), {"scan": lambda self: []})()
        from security.ap_scanner import NetshScanner
        ns = NetshScanner()
        results = ns._parse_netsh(output)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].ssid, "MyCorp")
        self.assertEqual(results[0].bssid, "001122334455")
        self.assertAlmostEqual(results[0].rssi, -59.0, delta=0.1)
        self.assertEqual(results[0].security, "WPA2-Personal")


class TestAirportScanner(unittest.TestCase):

    def test_airport_parsing(self):
        output = (
            "             SSID BSSID             RSSI CHANNEL HT CC\n"
            "      MyCorp    00:11:22:33:44:55   -58   36     Y  US\n"
        )
        from security.ap_scanner import AirportScanner
        ap = AirportScanner()
        results = ap._parse_airport(output)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].ssid, "MyCorp")
        self.assertEqual(results[0].bssid, "001122334455")
        self.assertEqual(results[0].rssi, -58.0)
        self.assertEqual(results[0].channel, 36)


class TestNmcliScanner(unittest.TestCase):

    def test_nmcli_parsing(self):
        output = (
            "SSID              BSSID              CHAN  SECURITY  SIGNAL\n"
            "MyCorp            aa:bb:cc:dd:ee:01    6  WPA2      82\n"
            "OpenGuest         bb:cc:dd:ee:ff:01   11  --        45\n"
        )
        from security.ap_scanner import NmcliScanner
        nm = NmcliScanner()
        results = nm._parse_nmcli(output)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].ssid, "MyCorp")
        self.assertEqual(results[0].bssid, "aabbccddee01")
        self.assertAlmostEqual(results[0].rssi, -59.0, delta=0.1)
        self.assertEqual(results[1].security, "open")


if __name__ == "__main__":
    unittest.main()