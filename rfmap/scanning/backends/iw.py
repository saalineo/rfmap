"""Linux `iw dev <if> scan` (or a fixture file via SENTINEL_SCANNER)."""
import os

from rfmap.models import APObservation
from rfmap.util.proc import run_subprocess
from rfmap.scanning.parsing import parse_iw_scan


def detect_linux_interface() -> str | None:
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
        self.interface = interface or detect_linux_interface() or "wlan0"

    def scan(self) -> list[APObservation]:
        scanner_env = os.environ.get("SENTINEL_SCANNER")
        if scanner_env:
            return self._scan_from_file(scanner_env)

        # Do not invoke sudo here: a GUI must never block on an invisible password
        # prompt.  Distributions that allow scans expose this command directly.
        proc = run_subprocess(["iw", "dev", self.interface, "scan"], timeout=10)
        if proc is None or proc.returncode != 0:
            return []
        return parse_iw_scan(proc.stdout, source="iw")

    def _scan_from_file(self, path: str) -> list[APObservation]:
        try:
            with open(path) as f:
                return parse_iw_scan(f.read(), source="fixture")
        except (FileNotFoundError, OSError):
            return []
