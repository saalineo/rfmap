import fnmatch
import json
import os
from dataclasses import dataclass
from typing import Optional

from rfmap.paths import CONFIG_DIR


@dataclass
class WhitelistEntry:
    ssid: str = ""
    bssid: str = ""
    oui: str = ""
    note: str = ""


class WhitelistStore:
    def __init__(self, path: str = str(CONFIG_DIR / "allowlist.json")):
        self.path = path
        self.entries: list[WhitelistEntry] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.entries = [WhitelistEntry(**e) for e in data if isinstance(e, dict)]
        except (json.JSONDecodeError, OSError):
            self.entries = []

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        data = [
            {"ssid": e.ssid, "bssid": e.bssid, "oui": e.oui, "note": e.note}
            for e in self.entries
        ]
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def add_entry(self, ssid: str = "", bssid: str = "", oui: str = "", note: str = ""):
        entry = WhitelistEntry(ssid=ssid, bssid=bssid.lower().replace(":", "").replace("-", ""), oui=oui, note=note)
        self.entries.append(entry)
        self.save()

    def remove_entry(self, index: int):
        if 0 <= index < len(self.entries):
            del self.entries[index]
            self.save()

    def list_entries(self) -> list[WhitelistEntry]:
        return list(self.entries)

    def match(self, bssid: str, ssid: str | None) -> Optional[WhitelistEntry]:
        normalized_bssid = bssid.lower().replace(":", "").replace("-", "").replace(".", "")
        for entry in self.entries:
            if entry.bssid and mac_match(normalized_bssid, entry.bssid):
                return entry
            if entry.ssid and ssid and ssid_match(ssid, entry.ssid):
                return entry
            if entry.oui and oui_match(normalized_bssid, entry.oui):
                return entry
        return None


def mac_match(raw: str, pattern: str) -> bool:
    raw_norm = raw.lower().replace(":", "").replace("-", "").replace(".", "")
    normalized_pattern = pattern.lower().replace(":", "").replace("-", "").replace(".", "")
    if "*" in normalized_pattern or "?" in normalized_pattern:
        return fnmatch.fnmatch(raw_norm, normalized_pattern)
    return raw_norm == normalized_pattern


def ssid_match(raw: str, pattern: str) -> bool:
    if "*" in pattern or "?" in pattern:
        return fnmatch.fnmatch(raw, pattern)
    return raw == pattern


def oui_match(raw_mac: str, oui_pattern: str) -> bool:
    raw_oui = raw_mac[:6].upper()
    pattern_oui = oui_pattern.upper().replace(":", "").replace("-", "").replace(".", "")
    if "*" in pattern_oui or "?" in pattern_oui:
        return fnmatch.fnmatch(raw_oui, pattern_oui)
    return raw_oui == pattern_oui
