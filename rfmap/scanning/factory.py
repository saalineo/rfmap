"""Pick the scanner for the current OS."""
import platform

from rfmap.scanning.backends.airport import AirportScanner
from rfmap.scanning.backends.iw import IwScanner
from rfmap.scanning.backends.linux import LinuxScanner
from rfmap.scanning.backends.netsh import NetshScanner


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


def create_scanner(interface: str | None = None):
    system = platform.system()
    if system == "Linux":
        return LinuxScanner(interface)
    if system == "Windows":
        return NetshScanner()
    if system == "Darwin":
        return AirportScanner()
    return IwScanner(interface)
