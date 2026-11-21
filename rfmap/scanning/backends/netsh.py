"""Windows `netsh wlan show networks`."""
import re

from rfmap.models import APObservation
from rfmap.util.proc import run_subprocess
from rfmap.scanning.parsing import normalize_mac


class NetshScanner:
    def scan(self) -> list[APObservation]:
        proc = run_subprocess(["netsh", "wlan", "show", "networks", "mode=bssid"], timeout=10)
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
                current_bssid = normalize_mac(bssid_match.group(1))
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
