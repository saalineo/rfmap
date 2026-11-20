import re
import time
from dataclasses import dataclass
from typing import Optional

from security.types import APObservation, RogueReport
from security.allowlist import WhitelistStore, _mac_match, _oui_match, _ssid_match


CORPORATE_SSID_PATTERNS = [
    r"mycorp",
    r"my.?corp",
    r"corp.?wifi",
    r"company.?wifi",
    r"office.?wifi",
    r"enterprise.?wifi",
]


def _is_corporate_ssid(ssid: str) -> bool:
    if not ssid:
        return False
    for pattern in CORPORATE_SSID_PATTERNS:
        if re.search(pattern, ssid, re.IGNORECASE):
            return True
    return False


def _is_hidden_ssid(obs: APObservation) -> bool:
    return obs.ssid is None


def _is_locally_administered_mac(bssid: str) -> bool:
    normalized = bssid.lower().replace(":", "").replace("-", "").replace(".", "")
    if len(normalized) < 12:
        return False
    first_byte = int(normalized[0:2], 16)
    return bool(first_byte & 0x02)


def _is_new_recent(first_seen: float, max_age_hours: float = 24.0) -> bool:
    age_hours = (time.time() - first_seen) / 3600.0
    return age_hours < max_age_hours


class RogueDetector:
    rogue_detected = None
    classification_changed = None

    def __init__(self, whitelist: WhitelistStore):
        self._whitelist = whitelist
        self._first_seen: dict[str, float] = {}
        self._alerted_bssids: set[str] = set()
        self._reports: dict[str, RogueReport] = {}

    def classify(self, observations: list[APObservation]) -> dict[str, RogueReport]:
        reports: dict[str, RogueReport] = {}

        for obs in observations:
            bssid = obs.bssid
            ssid = obs.ssid
            first_seen = self._first_seen.get(bssid, obs.first_seen)
            self._first_seen[bssid] = first_seen

            rules_hit: list[str] = []
            classification = "trusted"
            confidence = 0.0

            whitelist_entry = self._whitelist.match(bssid, ssid)

            if whitelist_entry is not None:
                if whitelist_entry.bssid and _mac_match(bssid, whitelist_entry.bssid):
                    if whitelist_entry.ssid and ssid and not _ssid_match(ssid, whitelist_entry.ssid):
                        classification = "rogue"
                        rules_hit.append(
                            f"BSSID {bssid} is whitelisted but SSID '{ssid}' "
                            f"differs from whitelisted '{whitelist_entry.ssid}'"
                        )
                        confidence = 0.9
                    else:
                        classification = "trusted"
                        confidence = 1.0
                elif whitelist_entry.ssid and ssid and _ssid_match(ssid, whitelist_entry.ssid):
                    if whitelist_entry.bssid:
                        classification = "rogue"
                        rules_hit.append(
                            f"SSID '{ssid}' is bound to a different BSSID than {bssid}"
                        )
                        confidence = 0.9
                    else:
                        # An SSID-only entry intentionally trusts all APs using that name.
                        classification = "trusted"
                        confidence = 0.8
                elif whitelist_entry.oui and _oui_match(bssid, whitelist_entry.oui):
                    classification = "trusted"
                    confidence = 0.7
                else:
                    classification = "trusted"
                    confidence = 0.5
            else:
                if _is_hidden_ssid(obs):
                    classification = "suspicious"
                    rules_hit.append("Hidden SSID — stealth AP possible")
                    confidence = 0.5

                if _is_locally_administered_mac(bssid):
                    classification = "suspicious" if classification != "rogue" else classification
                    rules_hit.append(
                        "Locally-administered MAC bit set — possible spoofing"
                    )
                    confidence = max(confidence, 0.6)

                if _is_corporate_ssid(ssid or ""):
                    if obs.security == "open":
                        classification = "rogue"
                        rules_hit.append(
                            f"Open network with corporate SSID '{ssid}'"
                        )
                        confidence = 0.85
                    else:
                        classification = "suspicious"
                        rules_hit.append(
                            f"Corporate-named SSID '{ssid}' with encryption"
                        )
                        confidence = max(confidence, 0.5)

                if _is_new_recent(first_seen):
                    classification = "suspicious" if classification == "trusted" else classification
                    rules_hit.append("AP appeared recently (<24h) — new or roaming equipment")
                    confidence = max(confidence, 0.4)

                if classification == "trusted":
                    classification = "suspicious"
                    rules_hit.append("Unknown AP not in whitelist")
                    confidence = 0.4

            if not rules_hit and classification == "trusted":
                confidence = 1.0

            report = RogueReport(
                bssid=bssid,
                ssid=ssid,
                classification=classification,
                rules_hit=rules_hit,
                confidence=confidence,
                channel=obs.channel,
                first_seen=first_seen,
            )
            reports[bssid] = report
            self._reports[bssid] = report

            is_rogue = classification == "rogue"
            was_alerted = bssid in self._alerted_bssids

            if is_rogue and not was_alerted:
                self._alerted_bssids.add(bssid)
                if self.rogue_detected is not None:
                    self.rogue_detected(report)
            elif classification != "rogue" and was_alerted:
                self._alerted_bssids.discard(bssid)
                if self.classification_changed is not None:
                    self.classification_changed(bssid)

        return reports
