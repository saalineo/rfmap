"""RSSIProvider: picks the right probe for the current OS."""
import platform

from rfmap.wifi.probes import linux, macos, windows


class RSSIProvider:
    def __init__(self, interface: str | None = None):
        self.system = platform.system()
        self.interface = interface

    def set_interface(self, interface: str | None):
        self.interface = interface

    def available_interfaces(self) -> list[str]:
        if self.system == "Linux":
            return linux.detect_linux_interfaces()
        return []

    def read(self) -> float | None:
        if self.system == "Linux":
            return linux.rssi_linux(self.interface)
        elif self.system == "Windows":
            return windows.rssi_windows()
        elif self.system == "Darwin":
            return macos.rssi_macos()
        return None

    def source_description(self) -> str:
        if self.system == "Linux":
            iface = linux.linux_interface(self.interface)
            if iface:
                if linux.read_proc_net_wireless(iface) is not None:
                    return f"Linux /proc/net/wireless ({iface})"
                if linux.run_iw_dev_link(iface) is not None:
                    return f"Linux iw dev ({iface})"
                if linux.run_iwconfig(iface) is not None:
                    return f"Linux iwconfig ({iface})"
            return "Linux (no interface found)"
        elif self.system == "Windows":
            return "Windows netsh wlan"
        elif self.system == "Darwin":
            return "macOS airport"
        return f"Unknown OS ({self.system})"

    def get_ssid(self) -> str | None:
        if self.system == "Linux":
            iface = linux.linux_interface(self.interface)
            if iface:
                ssid = linux.ssid_from_iw(iface)
                if ssid is not None:
                    return ssid
                ssid = linux.ssid_from_iwconfig(iface)
                if ssid is not None:
                    return ssid
        elif self.system == "Windows":
            return windows.ssid_windows()
        elif self.system == "Darwin":
            return macos.ssid_macos()
        return None

    def get_connected_devices(self) -> list[str]:
        if self.system == "Linux":
            iface = linux.linux_interface(self.interface)
            if iface:
                return linux.connected_devices_linux(iface)
        elif self.system == "Windows":
            return windows.connected_devices_windows()
        return []
