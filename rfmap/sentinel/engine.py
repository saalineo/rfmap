import time
from typing import Callable

from rfmap.models import APObservation, RogueReport, SentryLogEntry
from rfmap.sentinel.allowlist import WhitelistStore, mac_match


def calculate_trust_score(observations: list[APObservation], reports: dict[str, RogueReport], deauth_burst_active: bool = False) -> tuple[int, list[str]]:
    score = 100
    breakdown: list[str] = []

    if deauth_burst_active:
        score -= 25
        breakdown.append("Deauth packet burst detected (-25)")

    seen_ssids = set()
    for obs in observations:
        bssid = obs.bssid
        ssid = obs.ssid
        report = reports.get(bssid)

        if report and report.classification == "rogue":
            score -= 30
            breakdown.append(f"Rogue AP / Evil Twin detected ({ssid or bssid}) (-30)")
        elif obs.ssid is None:
            score -= 10
            breakdown.append(f"Hidden SSID detected ({bssid[:8]}...) (-10)")
        elif report and "Open network with corporate SSID" in " ".join(report.rules_hit):
            score -= 20
            breakdown.append(f"Open Corporate SSID ({ssid}) (-20)")
        elif obs.security == "open":
            score -= 5
            breakdown.append(f"Open network detected ({ssid or bssid}) (-5)")
        elif report and report.classification == "suspicious":
            score -= 5
            breakdown.append(f"Suspicious AP ({ssid or bssid}) (-5)")

    final_score = max(0, min(100, score))
    return final_score, breakdown


class SentryEngine:
    def __init__(self, whitelist: WhitelistStore, alert_callback: Callable[[SentryLogEntry], None] | None = None):
        self._whitelist = whitelist
        self._alert_callback = alert_callback
        self._known_ssids: set[str] = set()
        self._known_ssid_bssids: dict[str, set[str]] = {}  # ssid -> set of bssids
        self._seen_bssids: set[str] = set()
        self._reported_rogue_bssids: set[str] = set()
        self.logs: list[SentryLogEntry] = []
        self._initialized = False

    def process_scan(self, observations: list[APObservation], reports: dict[str, RogueReport], deauth_burst: bool = False) -> list[SentryLogEntry]:
        now = time.time()
        new_entries: list[SentryLogEntry] = []

        current_ssids = {obs.ssid for obs in observations if obs.ssid}
        current_bssids = {obs.bssid for obs in observations}

        if not self._initialized:
            # Seed baseline state on first run
            for obs in observations:
                self._seen_bssids.add(obs.bssid)
                if obs.ssid:
                    self._known_ssids.add(obs.ssid)
                    self._known_ssid_bssids.setdefault(obs.ssid, set()).add(obs.bssid)
            self._initialized = True
            return []

        for ssid in current_ssids:
            if ssid not in self._known_ssids:
                entry = SentryLogEntry(
                    timestamp=now,
                    event_type="NEW_SSID",
                    bssid="",
                    ssid=ssid,
                    details=f"New SSID '{ssid}' detected in RF environment",
                    severity="MEDIUM",
                )
                new_entries.append(entry)
                self._known_ssids.add(ssid)

        # Evil Twin Detection (Known SSID seen from a new BSSID)
        for obs in observations:
            bssid = obs.bssid
            ssid = obs.ssid

            if bssid not in self._seen_bssids:
                self._seen_bssids.add(bssid)
                if ssid and ssid in self._known_ssid_bssids:
                    known_bssids_for_ssid = self._known_ssid_bssids[ssid]
                    if bssid not in known_bssids_for_ssid:
                        wl_match = self._whitelist.match(bssid, ssid)
                        if not wl_match or (wl_match.bssid and not mac_match(bssid, wl_match.bssid)):
                            entry = SentryLogEntry(
                                timestamp=now,
                                event_type="EVIL_TWIN",
                                bssid=bssid,
                                ssid=ssid,
                                details=f"EVIL TWIN ALERT: Known SSID '{ssid}' broadcast from NEW unapproved BSSID {bssid}",
                                severity="HIGH",
                            )
                            new_entries.append(entry)

                if ssid:
                    self._known_ssid_bssids.setdefault(ssid, set()).add(bssid)

        #Deauth burst
        if deauth_burst:
            entry = SentryLogEntry(
                timestamp=now,
                event_type="DEAUTH_BURST",
                bssid="",
                ssid=None,
                details="DEAUTH BURST DETECTED: High frequency of IEEE 802.11 deauth frames intercepted",
                severity="HIGH",
            )
            new_entries.append(entry)

        # Rogue reports from RogueDetector
        for bssid, report in reports.items():
            if report.classification == "rogue" and bssid not in self._reported_rogue_bssids:
                self._reported_rogue_bssids.add(bssid)
                entry = SentryLogEntry(
                    timestamp=now,
                    event_type="ROGUE_AP",
                    bssid=bssid,
                    ssid=report.ssid,
                    details=f"Rogue AP Flagged: {'; '.join(report.rules_hit)}",
                    severity="HIGH",
                )
                new_entries.append(entry)
            elif report.classification != "rogue":
                self._reported_rogue_bssids.discard(bssid)

        for entry in new_entries:
            self.logs.append(entry)
            if self._alert_callback:
                self._alert_callback(entry)

        return new_entries
