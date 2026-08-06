import os
import sys
import tempfile
import unittest
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.detection import RogueDetector, _is_corporate_ssid, _is_locally_administered_mac
from security.types import APObservation
from security.allowlist import WhitelistStore, WhitelistEntry


def make_obs(bssid, ssid, channel=6, rssi=-50, security="WPA2-Personal", first_seen=None):
    return APObservation(
        bssid=bssid,
        ssid=ssid,
        channel=channel,
        frequency_mhz=2437,
        rssi=rssi,
        security=security,
        first_seen=first_seen or time.time(),
        source="test",
    )


class TestWhitelistMatching(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self.store = WhitelistStore(self._tmp.name)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_exact_bssid_match(self):
        self.store.add_entry(bssid="aa:bb:cc:dd:ee:01", ssid="MyCorp")
        result = self.store.match("aa:bb:cc:dd:ee:01", "MyCorp")
        self.assertIsNotNone(result)

    def test_exact_bssid_no_match(self):
        self.store.add_entry(bssid="aa:bb:cc:dd:ee:01", ssid="MyCorp")
        result = self.store.match("aa:bb:cc:dd:ee:02", "OtherNet")
        self.assertIsNone(result)

    def test_wildcard_ssid_match(self):
        self.store.add_entry(ssid="MyCorp*", bssid="")
        result = self.store.match("aa:bb:cc:dd:ee:01", "MyCorp-Guest")
        self.assertIsNotNone(result)

    def test_wildcard_ssid_no_match(self):
        self.store.add_entry(ssid="MyCorp*", bssid="")
        result = self.store.match("aa:bb:cc:dd:ee:01", "OtherNet")
        self.assertIsNone(result)

    def test_oui_wildcard_match(self):
        self.store.add_entry(oui="AA:BB:CC", ssid="")
        result = self.store.match("aa:bb:cc:dd:ee:01", "AnySSID")
        self.assertIsNotNone(result)


class TestRogueDetection(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self.store = WhitelistStore(self._tmp.name)
        self.detector = RogueDetector(self.store)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_trusted_exact_pair(self):
        self.store.add_entry(bssid="aa:bb:cc:dd:ee:01", ssid="MyCorp-WPA")
        obs = [make_obs("aa:bb:cc:dd:ee:01", "MyCorp-WPA")]
        reports = self.detector.classify(obs)
        self.assertEqual(reports["aa:bb:cc:dd:ee:01"].classification, "trusted")
        self.assertEqual(len(reports["aa:bb:cc:dd:ee:01"].rules_hit), 0)

    def test_evil_twin_whitelisted_ssid_new_bssid(self):
        self.store.add_entry(bssid="aa:bb:cc:dd:ee:01", ssid="MyCorp-WPA")
        obs = [make_obs("aa:bb:cc:dd:ee:02", "MyCorp-WPA")]
        reports = self.detector.classify(obs)
        self.assertEqual(reports["aa:bb:cc:dd:ee:02"].classification, "rogue")
        self.assertGreater(len(reports["aa:bb:cc:dd:ee:02"].rules_hit), 0)
        self.assertGreaterEqual(reports["aa:bb:cc:dd:ee:02"].confidence, 0.8)

    def test_whitelisted_bssid_wrong_ssid(self):
        self.store.add_entry(bssid="aa:bb:cc:dd:ee:01", ssid="MyCorp-WPA")
        obs = [make_obs("aa:bb:cc:dd:ee:01", "EvilTwin")]
        reports = self.detector.classify(obs)
        self.assertEqual(reports["aa:bb:cc:dd:ee:01"].classification, "rogue")

    def test_open_corporate_ssid(self):
        obs = [make_obs("aa:bb:cc:dd:ee:03", "MyCorp", security="open")]
        reports = self.detector.classify(obs)
        self.assertEqual(reports["aa:bb:cc:dd:ee:03"].classification, "rogue")
        self.assertGreaterEqual(reports["aa:bb:cc:dd:ee:03"].confidence, 0.8)

    def test_hidden_ssid_suspicious(self):
        obs = [make_obs("aa:bb:cc:dd:ee:04", None)]
        reports = self.detector.classify(obs)
        self.assertEqual(reports["aa:bb:cc:dd:ee:04"].classification, "suspicious")

    def test_locally_administered_mac_suspicious(self):
        obs = [make_obs("02:00:00:00:00:05", "SomeNet")]
        reports = self.detector.classify(obs)
        self.assertEqual(reports["02:00:00:00:00:05"].classification, "suspicious")

    def test_oui_wildcard_trusted(self):
        self.store.add_entry(oui="AA:BB:CC", ssid="")
        obs = [make_obs("aa:bb:cc:dd:ee:06", "UnknownSSID")]
        reports = self.detector.classify(obs)
        self.assertEqual(reports["aa:bb:cc:dd:ee:06"].classification, "trusted")

    def test_unknown_ap_suspicious(self):
        obs = [make_obs("aa:bb:cc:dd:ee:07", "UnknownNet")]
        reports = self.detector.classify(obs)
        self.assertEqual(reports["aa:bb:cc:dd:ee:07"].classification, "suspicious")

    def test_corporate_ssid_with_encryption_suspicious(self):
        obs = [make_obs("aa:bb:cc:dd:ee:08", "MyCorp-Secure", security="WPA2-Personal")]
        reports = self.detector.classify(obs)
        self.assertEqual(reports["aa:bb:cc:dd:ee:08"].classification, "suspicious")

    def test_debounce_rogue_alert(self):
        self.store.add_entry(bssid="aa:bb:cc:dd:ee:01", ssid="MyCorp-WPA")
        obs = [make_obs("aa:bb:cc:dd:ee:02", "MyCorp-WPA")]
        reports1 = self.detector.classify(obs)
        self.assertEqual(reports1["aa:bb:cc:dd:ee:02"].classification, "rogue")
        reports2 = self.detector.classify(obs)
        self.assertEqual(reports2["aa:bb:cc:dd:ee:02"].classification, "rogue")

    def test_rules_hit_non_empty_for_non_trusted(self):
        obs = [make_obs("aa:bb:cc:dd:ee:09", "MyCorp", security="open")]
        reports = self.detector.classify(obs)
        self.assertGreater(len(reports["aa:bb:cc:dd:ee:09"].rules_hit), 0)

    def test_confidence_range(self):
        obs = [make_obs("aa:bb:cc:dd:ee:10", "Unknown")]
        reports = self.detector.classify(obs)
        conf = reports["aa:bb:cc:dd:ee:10"].confidence
        self.assertGreaterEqual(conf, 0.4)
        self.assertLessEqual(conf, 0.99)


class TestCorporateSSIDDetection(unittest.TestCase):

    def test_mycorp_match(self):
        self.assertTrue(_is_corporate_ssid("MyCorp"))

    def test_mycorp_guest_match(self):
        self.assertTrue(_is_corporate_ssid("MyCorp-Guest"))

    def test_office_wifi_match(self):
        self.assertTrue(_is_corporate_ssid("Office-WiFi"))

    def test_no_match(self):
        self.assertFalse(_is_corporate_ssid("NeighborNet"))


class TestLocallyAdministeredMac(unittest.TestCase):

    def test_locally_administered(self):
        self.assertTrue(_is_locally_administered_mac("02:00:00:00:00:01"))

    def test_not_locally_administered(self):
        self.assertFalse(_is_locally_administered_mac("00:11:22:33:44:55"))

    def test_locally_administered_06(self):
        self.assertTrue(_is_locally_administered_mac("06:00:00:00:00:01"))


if __name__ == "__main__":
    unittest.main()