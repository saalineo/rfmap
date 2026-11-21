"""macOS: airport -I."""
import os
import re

from rfmap.util.proc import run_subprocess


def ssid_macos() -> str | None:
    path = (
        "/System/Library/PrivateFrameworks/Apple80211.framework/"
        "Versions/Current/Resources/airport"
    )
    if not os.path.exists(path):
        return None
    proc = run_subprocess([path, "-I"])
    if proc:
        match = re.search(r"\s+SSID:\s*(.+)", proc.stdout)
        if match:
            return match.group(1).strip()
    return None


def rssi_macos() -> float | None:
    path = (
        "/System/Library/PrivateFrameworks/Apple80211.framework/"
        "Versions/Current/Resources/airport"
    )
    if not os.path.exists(path):
        return None
    proc = run_subprocess([path, "-I"])
    if proc:
        match = re.search(r"agrCtlRSSI:\s*(-?\d+)", proc.stdout)
        if match:
            return float(match.group(1))
    return None
