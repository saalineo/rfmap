"""Deterministic fake APs for demos and tests."""

import numpy as np

from rfmap.models import APObservation


class SimulatedScanner:
    def __init__(self):
        self._rng = np.random.default_rng(42)
        self._aps = self._build_aps()

    def _build_aps(self) -> list[APObservation]:
        aps = [
            APObservation(
                bssid="aa:bb:cc:dd:ee:01",
                ssid="MyCorp-WPA",
                channel=36,
                frequency_mhz=5180,
                rssi=-45.0,
                security="WPA2-Personal",
                source="simulated",
            ),
            APObservation(
                bssid="aa:bb:cc:dd:ee:02",
                ssid="MyCorp",
                channel=6,
                frequency_mhz=2437,
                rssi=-52.0,
                security="open",
                source="simulated",
            ),
            APObservation(
                bssid="aa:bb:cc:dd:ee:03",
                ssid=None,
                channel=11,
                frequency_mhz=2462,
                rssi=-78.0,
                security="open",
                source="simulated",
            ),
            APObservation(
                bssid="aa:bb:cc:dd:ee:04",
                ssid="GuestNet",
                channel=1,
                frequency_mhz=2412,
                rssi=-65.0,
                security="WPA2-Personal",
                source="simulated",
            ),
            APObservation(
                bssid="aa:bb:cc:dd:ee:05",
                ssid="Free_Admin",
                channel=6,
                frequency_mhz=2437,
                rssi=-60.0,
                security="open",
                source="simulated",
            ),
        ]
        return aps

    def scan(self) -> list[APObservation]:
        results = []
        for ap in self._aps:
            noise = self._rng.normal(0, 2.0)
            rssi = max(-95.0, min(-25.0, ap.rssi + noise))
            results.append(APObservation(
                bssid=ap.bssid,
                ssid=ap.ssid,
                channel=ap.channel,
                frequency_mhz=ap.frequency_mhz,
                rssi=rssi,
                security=ap.security,
                source="simulated",
            ))
        return results
