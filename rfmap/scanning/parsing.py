"""MAC / channel helpers and the `iw scan` output parser."""
import re

from rfmap.models import APObservation


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


def freq_to_channel(freq: int) -> int:
    return _FREQ_TO_CHANNEL.get(freq, 0)


def normalize_mac(mac: str) -> str:
    return mac.lower().replace(":", "").replace("-", "").replace(".", "")


def mac_oui(mac: str) -> str:
    normalized = normalize_mac(mac)
    return normalized[:6].upper()


def is_locally_administered(mac: str) -> bool:
    normalized = normalize_mac(mac)
    if len(normalized) < 12:
        return False
    second_byte = int(normalized[2:4], 16)
    return bool(second_byte & 0x02)


def parse_iw_scan(output: str, source: str = "iw") -> list[APObservation]:
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
            current_bssid = normalize_mac(bss_match.group(1))
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
                current_channel = freq_to_channel(current_frequency)
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
