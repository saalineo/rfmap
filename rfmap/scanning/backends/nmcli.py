"""Linux NetworkManager `nmcli`."""

from rfmap.models import APObservation
from rfmap.util.proc import run_subprocess
from rfmap.scanning.parsing import normalize_mac


class NmcliScanner:
    def __init__(self, interface: str | None = None):
        self.interface = interface

    def scan(self) -> list[APObservation]:
        cmd = ["nmcli", "-t", "-e", "yes", "-f", "SSID,BSSID,CHAN,SECURITY,SIGNAL", "dev", "wifi", "list"]
        if self.interface:
            cmd.extend(["ifname", self.interface])
        proc = run_subprocess(cmd)
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
                bssid = normalize_mac(parts[1]) if parts[1] != "--" else None
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
                normalized_bssid = normalize_mac(bssid) if bssid != "--" else ""
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
