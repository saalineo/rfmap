import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from security.types import LocalizationFix, RogueReport, SurveySample


def _iso_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class SessionStore:
    def __init__(self, base_dir: str = "sessions"):
        self.base_dir = base_dir

    def save_session(
        self,
        samples: list[SurveySample],
        fixes: list[LocalizationFix],
        alerts: list[RogueReport],
        scan_summary: dict | None = None,
    ) -> str:
        ts = _iso_timestamp()
        session_dir = os.path.join(self.base_dir, ts)
        os.makedirs(session_dir, exist_ok=True)

        self._save_samples(session_dir, samples)
        self._save_fixes(session_dir, fixes)
        self._save_alerts(session_dir, alerts)
        self._save_scan_summary(session_dir, scan_summary or {})
        self._save_report(session_dir, samples, fixes, alerts)

        return session_dir

    def _save_samples(self, session_dir: str, samples: list[SurveySample]):
        path = os.path.join(session_dir, "samples.json")
        data = [
            {
                "bssid": s.bssid,
                "x": s.x,
                "y": s.y,
                "rssi": s.rssi,
                "channel": s.channel,
                "timestamp": s.timestamp,
            }
            for s in samples
        ]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _save_fixes(self, session_dir: str, fixes: list[LocalizationFix]):
        path = os.path.join(session_dir, "fixes.csv")
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["bssid", "x", "y", "gdop", "confidence", "n_samples", "rssi_error_sigma", "timestamp"])
            for fix in fixes:
                writer.writerow([
                    fix.bssid,
                    f"{fix.x:.4f}",
                    f"{fix.y:.4f}",
                    f"{fix.gdop:.4f}",
                    f"{fix.confidence:.4f}",
                    fix.n_samples,
                    f"{fix.rssi_error_sigma:.4f}",
                    datetime.now(timezone.utc).isoformat(),
                ])

    def _save_alerts(self, session_dir: str, alerts: list[RogueReport]):
        path = os.path.join(session_dir, "alerts.json")
        data = [
            {
                "bssid": a.bssid,
                "ssid": a.ssid,
                "classification": a.classification,
                "rules_hit": a.rules_hit,
                "confidence": a.confidence,
                "channel": a.channel,
                "first_seen": a.first_seen,
            }
            for a in alerts
        ]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _save_scan_summary(self, session_dir: str, summary: dict):
        path = os.path.join(session_dir, "scan_summary.json")
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)

    def _save_report(self, session_dir: str, samples: list[SurveySample], fixes: list[LocalizationFix], alerts: list[RogueReport]):
        path = os.path.join(session_dir, "report.html")
        html = self._generate_html(samples, fixes, alerts)
        with open(path, "w") as f:
            f.write(html)

    def _generate_html(self, samples: list[SurveySample], fixes: list[LocalizationFix], alerts: list[RogueReport]) -> str:
        sample_rows = ""
        for s in samples:
            sample_rows += (
                f"<tr><td>{s.bssid}</td><td>{s.x:.1f}</td><td>{s.y:.1f}</td>"
                f"<td>{s.rssi:.1f}</td><td>{s.channel}</td></tr>\n"
            )

        fix_rows = ""
        for f in fixes:
            fix_rows += (
                f"<tr><td>{f.bssid}</td><td>{f.x:.2f}</td><td>{f.y:.2f}</td>"
                f"<td>{f.gdop:.2f}</td><td>{f.confidence:.2f}</td><td>{f.n_samples}</td></tr>\n"
            )

        alert_rows = ""
        for a in alerts:
            alert_rows += (
                f"<tr><td>{a.bssid}</td><td>{a.ssid or '(hidden)'}</td>"
                f"<td>{a.classification}</td><td>{'; '.join(a.rules_hit)}</td></tr>\n"
            )

        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Wavey Report</title>
<style>body{{font-family:sans-serif;margin:2em;}}table{{border-collapse:collapse;}}th,td{{border:1px solid #ccc;padding:4px 8px;}}</style>
</head>
<body>
<h1>Wavey — Site Survey Report</h1>
<p>Generated: {datetime.now(timezone.utc).isoformat()}</p>

<h2>Survey Samples</h2>
<table><tr><th>BSSID</th><th>X</th><th>Y</th><th>RSSI</th><th>Ch</th></tr>
{sample_rows}</table>

<h2>Localization Fixes</h2>
<table><tr><th>BSSID</th><th>X</th><th>Y</th><th>GDOP</th><th>Confidence</th><th>N</th></tr>
{fix_rows}</table>

<h2>Rogue Alerts</h2>
<table><tr><th>BSSID</th><th>SSID</th><th>Classification</th><th>Rules Hit</th></tr>
{alert_rows}</table>

<footer><p><strong>AUTHORIZED USE ONLY</strong> — This tool is intended for authorized security assessments only.</p></footer>
</body>
</html>"""

    def load_samples(self, session_dir: str) -> list[dict]:
        path = os.path.join(session_dir, "samples.json")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return json.load(f)

    def load_fixes(self, session_dir: str) -> list[dict]:
        path = os.path.join(session_dir, "fixes.csv")
        if not os.path.exists(path):
            return []
        fixes = []
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                fixes.append(row)
        return fixes