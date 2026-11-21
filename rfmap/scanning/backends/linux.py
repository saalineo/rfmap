"""Linux: prefer nmcli, fall back to an unprivileged iw scan."""
from rfmap.models import APObservation
from rfmap.scanning.backends.iw import IwScanner
from rfmap.scanning.backends.nmcli import NmcliScanner


class LinuxScanner:
    """Prefer NetworkManager and fall back to an unprivileged iw scan."""

    def __init__(self, interface: str | None = None):
        self.interface = interface
        self._nmcli = NmcliScanner(interface)
        self._iw = IwScanner(interface)
        self.source = "nmcli"

    def scan(self) -> list[APObservation]:
        observations = self._nmcli.scan()
        if observations:
            self.source = "nmcli"
            return observations
        observations = self._iw.scan()
        if observations:
            self.source = "iw"
        return observations
