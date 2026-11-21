"""Windows: netsh wlan."""
import re

from rfmap.util.proc import run_subprocess


def rssi_windows() -> float | None:
    proc = run_subprocess(["netsh", "wlan", "show", "interfaces"])
    if proc:
        match = re.search(r"Signal\s*:\s*(\d+)%", proc.stdout)
        if match:
            percent = float(match.group(1))
            return (percent / 2.0) - 100.0
    return None


def ssid_windows() -> str | None:
    proc = run_subprocess(["netsh", "wlan", "show", "interfaces"])
    if proc:
        match = re.search(r"SSID\s*:\s*(.+)", proc.stdout)
        if match:
            return match.group(1).strip()
    return None


def connected_devices_windows() -> list[str]:
    proc = run_subprocess(["netsh", "wlan", "show", "hostednetwork"])
    if proc:
        match = re.search(r"Number of clients\s*:\s*(\d+)", proc.stdout)
        count = int(match.group(1)) if match else 0
        return [f"Device-{i + 1}" for i in range(count)]
    return []
