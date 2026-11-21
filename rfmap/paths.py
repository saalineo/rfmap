"""Filesystem locations. Everything that touches disk resolves through here."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"
SESSIONS_DIR = PROJECT_ROOT / "sessions"
