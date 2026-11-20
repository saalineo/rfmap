import logging
import re
import subprocess
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def parse_iw_event_deauth(output: str) -> int:
    """
    Parses 'iw event' or 'tcpdump' output for deauthentication packet events.
    Returns count of deauth frames found.
    """
    deauth_count = 0
    for line in output.splitlines():
        if re.search(r"deauth|deauthentication|reason code|subtype deauth", line, re.IGNORECASE):
            deauth_count += 1
    return deauth_count


class DeauthDetector:
    """
    Optional Monitor Mode / Deauth Packet Burst Detector.
    Linux compatible: monitors raw 802.11 frames via iw event, tcpdump, or tshark
    if monitor mode interface is available.
    """

    def __init__(self, interface: str = "wlan0mon", threshold_per_sec: int = 5):
        self.interface = interface
        self.threshold = threshold_per_sec
        self._proc: Optional[subprocess.Popen] = None
        self._deauth_timestamps: list[float] = []
        self.is_monitoring = False

    def check_simulated(self, trigger: bool = False) -> bool:
        """Helper for simulation mode."""
        if trigger:
            now = time.time()
            self._deauth_timestamps.extend([now] * (self.threshold + 2))
            return True
        return False

    def start_monitoring(self):
        """Attempts to launch background 'iw event' or tcpdump to capture deauth frames."""
        try:
            # First try iw event
            self._proc = subprocess.Popen(
                ["iw", "event", "-t"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.is_monitoring = True
            logger.info("DeauthDetector: Monitoring started on iw event")
        except (FileNotFoundError, PermissionError, OSError) as exc:
            logger.debug("DeauthDetector monitor mode launch failed: %s", exc)
            self.is_monitoring = False

    def poll_deauth_burst(self) -> bool:
        """
        Polls process output or evaluates recent frame count.
        Returns True if a deauthentication burst is active (> threshold frames in past 3 seconds).
        """
        now = time.time()
        # Clean up timestamps older than 3 seconds
        self._deauth_timestamps = [t for t in self._deauth_timestamps if now - t <= 3.0]

        if self._proc and self._proc.stdout:
            try:
                # Non-blocking read line if available
                import select
                r, _, _ = select.select([self._proc.stdout], [], [], 0.01)
                if r:
                    line = self._proc.stdout.readline()
                    if parse_iw_event_deauth(line) > 0:
                        self._deauth_timestamps.append(now)
            except Exception:
                pass

        return len(self._deauth_timestamps) >= self.threshold

    def stop_monitoring(self):
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        self.is_monitoring = False
