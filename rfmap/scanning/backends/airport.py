"""macOS `airport -s`."""

from rfmap.models import APObservation
from rfmap.util.proc import run_subprocess
from rfmap.scanning.parsing import normalize_mac


class AirportScanner:
    def scan(self) -> list[APObservation]:
        path = (
            "/System/Library/PrivateFrameworks/Apple80211.framework/"
            "Versions/Current/Resources/airport"
        )
        proc = run_subprocess([path, "-s"], timeout=10)
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
                bssid = normalize_mac(parts[1])
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
