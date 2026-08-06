import json
import os
from dataclasses import dataclass, field
from typing import Optional


DEFAULT_CONFIG = {
    "scan_interval_s": 5,
    "whitelist_path": "security/allowlist.json",
    "min_points": 3,
    "report_dir": "sessions",
    "logs_dir": "logs",
}


@dataclass
class SentinelConfig:
    scan_interval_s: int = 5
    whitelist_path: str = "security/allowlist.json"
    min_points: int = 3
    report_dir: str = "sessions"
    logs_dir: str = "logs"

    @classmethod
    def load(cls, path: str = "security/config.json") -> "SentinelConfig":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path) as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, OSError):
            return cls()

    def save(self, path: str = "security/config.json"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = {
            "scan_interval_s": self.scan_interval_s,
            "whitelist_path": self.whitelist_path,
            "min_points": self.min_points,
            "report_dir": self.report_dir,
            "logs_dir": self.logs_dir,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)