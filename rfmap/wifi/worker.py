"""Background QThread that polls RSSI/SSID/clients and emits Qt signals."""
import logging
import time

from PyQt6.QtCore import QThread, pyqtSignal

from rfmap.wifi.constants import CONSECUTIVE_FAILURE_LIMIT, INFO_POLL_INTERVAL, POLL_INTERVAL_SECONDS
from rfmap.wifi.provider import RSSIProvider

logger = logging.getLogger(__name__)


class RSSIWorker(QThread):
    rssi_updated = pyqtSignal(float, str)
    source_changed = pyqtSignal(str)
    ssid_updated = pyqtSignal(str)
    devices_updated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._interval = POLL_INTERVAL_SECONDS
        self._running = False
        self._real_provider = RSSIProvider()
        self._current_provider = self._real_provider
        self._consecutive_failures = 0
        self._failure_limit = CONSECUTIVE_FAILURE_LIMIT
        self._last_good_value: float | None = None
        self._unavailable_reported = False
        self._info_counter = 0.0

    @property
    def is_simulated(self) -> bool:
        return False

    @property
    def last_good_value(self) -> float | None:
        return self._last_good_value

    def set_interface(self, interface: str | None):
        """Use a specific Wi-Fi adapter, or the system default when None."""
        self._real_provider.set_interface(interface)
        self._consecutive_failures = 0
        self._unavailable_reported = False
        self.source_changed.emit(self._real_provider.source_description())

    def run(self):
        self._running = True
        while self._running:
            try:
                rssi = self._current_provider.read()
            except Exception as exc:
                logger.debug("RSSI read failed: %s", exc)
                rssi = None

            if rssi is not None:
                self._consecutive_failures = 0
                self._last_good_value = rssi
                if self._unavailable_reported:
                    self._unavailable_reported = False
                    self.source_changed.emit(self._real_provider.source_description())
                self.rssi_updated.emit(rssi, "real")
            else:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_limit:
                    if not self._unavailable_reported:
                        self._unavailable_reported = True
                        self.source_changed.emit(
                            "No live Wi-Fi reading — choose an adapter or connect to Wi-Fi"
                        )
                else:
                    if self._last_good_value is not None:
                        self.rssi_updated.emit(
                            self._last_good_value, "real (held)"
                        )

            self._info_counter += self._interval
            if self._info_counter >= INFO_POLL_INTERVAL:
                self._info_counter = 0.0
                try:
                    ssid = self._current_provider.get_ssid()
                    if ssid is not None:
                        self.ssid_updated.emit(ssid)
                except Exception as exc:
                    logger.debug("SSID lookup failed: %s", exc)
                try:
                    devices = self._current_provider.get_connected_devices()
                    self.devices_updated.emit(devices)
                except Exception as exc:
                    logger.debug("Device lookup failed: %s", exc)

            for _ in range(int(self._interval / 0.1)):
                if not self._running:
                    return
                time.sleep(0.1)

    def stop(self):
        self._running = False
