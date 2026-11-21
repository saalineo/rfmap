"""Synthetic RSSI when no real Wi-Fi source exists."""
import math

import numpy as np

from rfmap.wifi.constants import POLL_INTERVAL_SECONDS, RSSI_MAX_DBM, RSSI_MIN_DBM


class SimulatedRSSIProvider:
    def __init__(self):
        self._t = 0.0
        self._walk = 0.0
        self._last_value = -55.0
        self._rng = np.random.default_rng()

    def read(self) -> float:
        self._t += POLL_INTERVAL_SECONDS
        drift = 15.0 * math.sin(2.0 * math.pi * self._t / 120.0)
        self._walk += self._rng.normal(0, 0.5)
        self._walk = max(-10.0, min(10.0, self._walk))
        noise = self._rng.normal(0, 1.0)
        value = -55.0 + drift + self._walk + noise
        value = max(RSSI_MIN_DBM, min(RSSI_MAX_DBM, value))
        self._last_value = value
        return value

    def get_ssid(self) -> str:
        return "SIMULATED_NETWORK"

    def get_connected_devices(self) -> list[str]:
        count = int(abs(np.random.default_rng().normal(3, 1.5))) + 1
        return [f"Device-{i + 1}" for i in range(count)]

    @staticmethod
    def source_description() -> str:
        return "Simulated (no Wi-Fi source available)"
