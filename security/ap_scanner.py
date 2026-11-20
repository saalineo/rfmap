import logging
import math
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from heatmap.math import GRID_SIZE
from security.types import APObservation

logger = logging.getLogger(__name__)

SCAN_INTERVAL = 5.0
CONSECUTIVE_FAILURE_LIMIT = 2
TX_POWER_DBM = -30.0
PATH_LOSS_EXPONENT = 2.4
D0 = 1.0


def _run_subprocess(cmd: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None

_FREQ_TO_CHANNEL = {
    2412: 1, 2417: 2, 2422: 3, 2427: 4, 2432: 5,
    2437: 6, 2442: 7, 2447: 8, 2452: 9, 2457: 10,
    2462: 11, 2467: 12, 2472: 13, 2484: 14,
    5180: 36, 5200: 40, 5220: 44, 5240: 48,
    5260: 52, 5280: 56, 5300: 60, 5320: 64,
    5500: 100, 5520: 104, 5540: 108, 5560: 112,
    5580: 116, 5600: 120, 5620: 124, 5640: 128,
    5660: 132, 5680: 136, 5700: 140, 5720: 144,
    5745: 149, 5765: 153, 5785: 157, 5805: 161,
    5825: 165,
}


def _freq_to_channel(freq: int) -> int:
    return _FREQ_TO_CHANNEL.get(freq, 0)


def _normalize_mac(mac: str) -> str:
    return mac.lower().replace(":", "").replace("-", "").replace(".", "")


def _mac_oui(mac: str) -> str:
    normalized = _normalize_mac(mac)
    return normalized[:6].upper()


def _is_locally_administered(mac: str) -> bool:
    normalized = _normalize_mac(mac)
    if len(normalized) < 12:
        return False
    second_byte = int(normalized[2:4], 16)
    return bool(second_byte & 0x02)


def _parse_iw_scan(output: str, source: str = "iw") -> list[APObservation]:
    observations: list[APObservation] = []
    current_bssid: str | None = None
    current_ssid: str | None = None
    current_channel: int = 0
    current_frequency: int = 0
    current_rssi: float = -100.0
    current_security: str = "open"
    in_bss = False

    for line in output.splitlines():
        bss_match = re.match(r"\s*BSS\s+([0-9a-f:]+)(?:\s+\(on\s+\S+\))?", line)
        if bss_match:
            if in_bss and current_bssid:
                observations.append(APObservation(
                    bssid=current_bssid,
                    ssid=current_ssid,
                    channel=current_channel,
                    frequency_mhz=current_frequency,
                    rssi=current_rssi,
                    security=current_security,
                    source=source,
                ))
            current_bssid = _normalize_mac(bss_match.group(1))
            current_ssid = None
            current_channel = 0
            current_frequency = 0
            current_rssi = -100.0
            current_security = "open"
            in_bss = True
            continue

        if not in_bss:
            continue

        ssid_match = re.match(r"\s+SSID:\s+(.*)", line)
        if ssid_match:
            ssid_val = ssid_match.group(1).strip()
            current_ssid = ssid_val if ssid_val else None
            continue

        freq_match = re.match(r"\s+freq:\s+(\d+)", line)
        if freq_match:
            current_frequency = int(freq_match.group(1))
            if current_channel == 0:
                current_channel = _freq_to_channel(current_frequency)
            continue

        chan_match = re.match(r"\s+channel:\s+(\d+)", line)
        if chan_match:
            current_channel = int(chan_match.group(1))
            continue

        signal_match = re.match(r"\s+signal:\s+([-\d.]+)\s*dBm", line)
        if signal_match:
            current_rssi = float(signal_match.group(1))
            continue

        if re.search(r"\s+WPA[23]?\b", line, re.IGNORECASE):
            current_security = "WPA2/WPA3"
        elif re.search(r"\s+WPA\b", line, re.IGNORECASE):
            current_security = "WPA"
        elif re.search(r"\s+RSN\b", line, re.IGNORECASE):
            current_security = "WPA2"

    if in_bss and current_bssid:
        observations.append(APObservation(
            bssid=current_bssid,
            ssid=current_ssid,
            channel=current_channel,
            frequency_mhz=current_frequency,
            rssi=current_rssi,
            security=current_security,
            source=source,
        ))

    return observations


def _detect_linux_interface() -> str | None:
    try:
        with open("/proc/net/wireless") as f:
            for i, line in enumerate(f):
                if i < 2:
                    continue
                iface = line.split(":")[0].strip()
                if iface:
                    return iface
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return None


class IwScanner:
    def __init__(self, interface: str | None = None):
        self.interface = interface or _detect_linux_interface() or "wlan0"

    def scan(self) -> list[APObservation]:
        scanner_env = os.environ.get("SENTINEL_SCANNER")
        if scanner_env:
            return self._scan_from_file(scanner_env)

        # Do not invoke sudo here: a GUI must never block on an invisible password
        # prompt.  Distributions that allow scans expose this command directly.
        proc = _run_subprocess(["iw", "dev", self.interface, "scan"])
        if proc is None or proc.returncode != 0:
            return []
        return _parse_iw_scan(proc.stdout, source="iw")

    def _scan_from_file(self, path: str) -> list[APObservation]:
        try:
            with open(path) as f:
                return _parse_iw_scan(f.read(), source="fixture")
        except (FileNotFoundError, OSError):
            return []


class NetshScanner:
    def scan(self) -> list[APObservation]:
        proc = _run_subprocess(["netsh", "wlan", "show", "networks", "mode=bssid"])
        if proc is None:
            return []
        return self._parse_netsh(proc.stdout)

    def _parse_netsh(self, output: str) -> list[APObservation]:
        observations: list[APObservation] = []
        current_ssid: str | None = None
        current_bssid: str | None = None
        current_channel: int = 0
        current_security: str = "open"
        current_rssi: float = -100.0

        for line in output.splitlines():
            ssid_match = re.match(r"SSID\s+\d+\s*:\s*(.*)", line)
            if ssid_match:
                if current_bssid:
                    observations.append(APObservation(
                        bssid=current_bssid,
                        ssid=current_ssid,
                        channel=current_channel,
                        frequency_mhz=0,
                        rssi=current_rssi,
                        security=current_security,
                        source="netsh",
                    ))
                current_ssid = ssid_match.group(1).strip() or None
                current_bssid = None
                current_channel = 0
                current_security = "open"
                current_rssi = -100.0
                continue

            bssid_match = re.match(r"\s+BSSID\s+\d+\s*:\s*([0-9a-f:]+)", line, re.IGNORECASE)
            if bssid_match:
                current_bssid = _normalize_mac(bssid_match.group(1))
                continue

            signal_match = re.match(r"\s+Signal\s*:\s*(\d+)%", line)
            if signal_match:
                percent = float(signal_match.group(1))
                current_rssi = (percent / 2.0) - 100.0
                continue

            sec_match = re.match(r"\s+Authentication\s*:\s*(.*)", line)
            if sec_match:
                auth = sec_match.group(1).strip().lower()
                if "wpa" in auth:
                    current_security = "WPA2-Personal"
                elif "open" in auth or "none" in auth:
                    current_security = "open"
                else:
                    current_security = auth

        if current_bssid:
            observations.append(APObservation(
                bssid=current_bssid,
                ssid=current_ssid,
                channel=current_channel,
                frequency_mhz=0,
                rssi=current_rssi,
                security=current_security,
                source="netsh",
            ))

        return observations


class AirportScanner:
    def scan(self) -> list[APObservation]:
        path = (
            "/System/Library/PrivateFrameworks/Apple80211.framework/"
            "Versions/Current/Resources/airport"
        )
        proc = _run_subprocess([path, "-s"])
        if proc is None:
            return []
        return self._parse_airport(proc.stdout)

    def _parse_airport(self, output: str) -> list[APObservation]:
        observations: list[APObservation] = []
        lines = output.strip().splitlines()
        if len(lines) < 2:
            return observations

        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 6:
                continue
            try:
                ssid = parts[0] if parts[0] != "(null)" else None
                bssid = _normalize_mac(parts[1])
                rssi = float(parts[2])
                channel = int(parts[3])
                security = "open"
                if len(parts) > 5:
                    sec_str = parts[5].upper()
                    if "WPA" in sec_str:
                        security = "WPA2-Personal"
                observations.append(APObservation(
                    bssid=bssid,
                    ssid=ssid,
                    channel=channel,
                    frequency_mhz=0,
                    rssi=rssi,
                    security=security,
                    source="airport",
                ))
            except (ValueError, IndexError):
                continue

        return observations


class NmcliScanner:
    def __init__(self, interface: str | None = None):
        self.interface = interface

    def scan(self) -> list[APObservation]:
        cmd = ["nmcli", "-t", "-e", "yes", "-f", "SSID,BSSID,CHAN,SECURITY,SIGNAL", "dev", "wifi", "list"]
        if self.interface:
            cmd.extend(["ifname", self.interface])
        proc = _run_subprocess(cmd)
        if proc is None:
            return []
        return self._parse_nmcli(proc.stdout)

    def _parse_nmcli(self, output: str) -> list[APObservation]:
        observations: list[APObservation] = []
        lines = output.strip().splitlines()
        if not lines:
            return observations

        if not lines[0].startswith("SSID"):
            return self._parse_nmcli_terse(lines)

        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                ssid = parts[0] if parts[0] != "--" else None
                bssid = _normalize_mac(parts[1]) if parts[1] != "--" else None
                if not bssid:
                    continue
                channel = int(parts[2]) if parts[2] != "--" else 0
                security = parts[3] if parts[3] != "--" else "open"
                if security.lower() in ("--", "none", "open"):
                    security = "open"
                elif "wpa" in security.lower():
                    security = "WPA2-Personal"
                signal_percent = float(parts[4]) if parts[4] != "--" else 0.0
                rssi = (signal_percent / 2.0) - 100.0
                observations.append(APObservation(
                    bssid=bssid,
                    ssid=ssid,
                    channel=channel,
                    frequency_mhz=0,
                    rssi=rssi,
                    security=security,
                    source="nmcli",
                ))
            except (ValueError, IndexError):
                continue

        return observations

    @staticmethod
    def _split_terse_fields(line: str) -> list[str]:
        fields: list[str] = []
        field: list[str] = []
        escaped = False
        for char in line:
            if escaped:
                field.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == ":":
                fields.append("".join(field))
                field = []
            else:
                field.append(char)
        if escaped:
            field.append("\\")
        fields.append("".join(field))
        return fields

    def _parse_nmcli_terse(self, lines: list[str]) -> list[APObservation]:
        observations: list[APObservation] = []
        for line in lines:
            fields = self._split_terse_fields(line)
            if len(fields) != 5:
                continue
            ssid, bssid, channel, security, signal = fields
            try:
                normalized_bssid = _normalize_mac(bssid) if bssid != "--" else ""
                if not normalized_bssid:
                    continue
                observations.append(APObservation(
                    bssid=normalized_bssid,
                    ssid=ssid or None,
                    channel=int(channel) if channel != "--" else 0,
                    frequency_mhz=0,
                    rssi=(float(signal) / 2.0) - 100.0 if signal != "--" else -100.0,
                    security="open" if security.lower() in ("--", "none", "open") else security,
                    source="nmcli",
                ))
            except ValueError:
                continue
        return observations


class LinuxScanner:
    """Prefer NetworkManager and fall back to an unprivileged iw scan."""

    def __init__(self, interface: str | None = None):
        self.interface = interface
        self._nmcli = NmcliScanner(interface)
        self._iw = IwScanner(interface)
        self.source = "nmcli"

    def scan(self) -> list[APObservation]:
        observations = self._nmcli.scan()
        if observations:
            self.source = "nmcli"
            return observations
        observations = self._iw.scan()
        if observations:
            self.source = "iw"
        return observations


def scan_setup_guidance() -> str:
    system = platform.system()
    if system == "Linux":
        return (
            "No AP scan — connect a Wi-Fi adapter and enable NetworkManager "
            "(nmcli); RFMap will not request sudo."
        )
    if system == "Windows":
        return "No AP scan — confirm Wi-Fi is enabled, then run RFMap normally."
    if system == "Darwin":
        return "No AP scan — allow Wi-Fi access and ensure the macOS airport utility is available."
    return "No AP scan — this platform has no supported Wi-Fi scanner."


def _create_scanner(interface: str | None = None):
    system = platform.system()
    if system == "Linux":
        return LinuxScanner(interface)
    if system == "Windows":
        return NetshScanner()
    if system == "Darwin":
        return AirportScanner()
    return IwScanner(interface)


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


class APScanner(QThread):
    scan_ready = pyqtSignal(list)
    source_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._interval = SCAN_INTERVAL
        self._running = False
        self._interface: str | None = None
        self._real_scanner = _create_scanner()
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
        self._real_scanner = _create_scanner(interface)
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
