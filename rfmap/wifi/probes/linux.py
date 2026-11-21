"""Linux: /proc/net/wireless, iw, iwconfig."""
import re

from rfmap.util.proc import run_subprocess


def read_proc_net_wireless(interface: str) -> float | None:
    try:
        with open("/proc/net/wireless") as f:
            for line in f:
                if interface not in line:
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    level_str = parts[3].replace(".", "")
                    return float(level_str)
    except (FileNotFoundError, PermissionError, OSError, ValueError):
        return None
    return None


def run_iw_dev_link(interface: str) -> float | None:
    proc = run_subprocess(["iw", "dev", interface, "link"])
    if proc:
        match = re.search(r"signal:\s*(-?\d+)\s*dBm", proc.stdout)
        if match:
            return float(match.group(1))
    return None


def run_iwconfig(interface: str) -> float | None:
    proc = run_subprocess(["iwconfig", interface])
    if proc:
        match = re.search(r"Signal level\s*=\s*(-?\d+)\s*dBm", proc.stdout)
        if match:
            return float(match.group(1))
    return None


def detect_linux_interfaces() -> list[str]:
    interfaces = []
    try:
        with open("/proc/net/wireless") as f:
            for i, line in enumerate(f):
                if i < 2:
                    continue
                iface = line.split(":")[0].strip()
                if iface:
                    interfaces.append(iface)
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return interfaces


def linux_interface(interface: str | None = None) -> str | None:
    interfaces = detect_linux_interfaces()
    if not interfaces:
        return None
    return interface if interface in interfaces else interfaces[0]


def rssi_linux(interface: str | None = None) -> float | None:
    iface = linux_interface(interface)
    if iface is None:
        return None

    rssi = read_proc_net_wireless(iface)
    if rssi is not None:
        return rssi
    rssi = run_iw_dev_link(iface)
    if rssi is not None:
        return rssi
    rssi = run_iwconfig(iface)
    if rssi is not None:
        return rssi
    return None


def ssid_from_iw(interface: str) -> str | None:
    proc = run_subprocess(["iw", "dev", interface, "link"])
    if proc:
        match = re.search(r"SSID:\s*(.+)", proc.stdout)
        if match:
            return match.group(1).strip()
    return None


def ssid_from_iwconfig(interface: str) -> str | None:
    proc = run_subprocess(["iwconfig", interface])
    if proc:
        match = re.search(r'ESSID:"(.+?)"', proc.stdout)
        if match:
            return match.group(1)
    return None


def connected_devices_linux(interface: str) -> list[str]:
    proc = run_subprocess(["iw", "dev", interface, "station", "dump"])
    if proc is None:
        return []
    macs = []
    for line in proc.stdout.splitlines():
        if line.startswith("Station "):
            mac = line.split()[1]
            macs.append(mac)
    # Reverse DNS has no portable timeout and can block the RSSI thread.
    return [mac[-8:] for mac in macs]
