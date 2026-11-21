"""Background QThread that polls the scanner and emits observations."""
import logging
import time

from PyQt6.QtCore import QThread, pyqtSignal

from rfmap.scanning.factory import create_scanner, scan_setup_guidance

logger = logging.getLogger(__name__)

SCAN_INTERVAL = 5.0


CONSECUTIVE_FAILURE_LIMIT = 2


class APScanner(QThread):
    scan_ready = pyqtSignal(list)
    source_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._interval = SCAN_INTERVAL
        self._running = False
        self._interface: str | None = None
        self._real_scanner = create_scanner()
        self._current_scanner = self._real_scanner
        self._consecutive_failures = 0
        self._failure_limit = CONSECUTIVE_FAILURE_LIMIT
        self._scan_unavailable_reported = False
        self._scan_now_requested = False

    @property
    def is_simulated(self) -> bool:
        return False

    def set_interface(self, interface: str | None):
        self._interface = interface
        self._real_scanner = create_scanner(interface)
        self._current_scanner = self._real_scanner
        self._consecutive_failures = 0
        self._scan_unavailable_reported = False

    def run(self):
        self._running = True
        while self._running:
            try:
                if self._scan_now_requested:
                    self._scan_now_requested = False
                    observations = self._current_scanner.scan()
                else:
                    observations = self._current_scanner.scan()
            except Exception as exc:
                logger.debug("Scan failed: %s", exc)
                observations = []

            if observations:
                self._consecutive_failures = 0
                self._scan_unavailable_reported = False
                source = getattr(self._current_scanner, "source", observations[0].source)
                adapter = f" ({self._interface})" if self._interface else ""
                self.source_changed.emit(f"AP scanner: {source}{adapter}")
                self.scan_ready.emit(observations)
            else:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_limit:
                    if not self._scan_unavailable_reported:
                        self._scan_unavailable_reported = True
                        self.source_changed.emit(scan_setup_guidance())
                else:
                    time.sleep(0.5)

            if self._scan_now_requested:
                continue

            for _ in range(int(self._interval / 0.1)):
                if not self._running:
                    return
                time.sleep(0.1)

    def scan_now(self):
        self._scan_now_requested = True

    def stop(self):
        self._running = False
