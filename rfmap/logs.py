import logging
import os
from rfmap.paths import LOGS_DIR


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logs_dir = LOGS_DIR
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, "rfmap.log")
        handler = logging.FileHandler(log_path)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_fallback(logger: logging.Logger, source: str, reason: str):
    logger.info(f"Fallback to {source}: {reason}")


def log_alert(logger: logging.Logger, bssid: str, classification: str, rules: list[str]):
    logger.info(f"Alert: {bssid} -> {classification}: {'; '.join(rules)}")


def log_fix(logger: logging.Logger, bssid: str, x: float, y: float, gdop: float, confidence: float):
    logger.info(f"Fix: {bssid} at ({x:.2f}, {y:.2f}) gdop={gdop:.2f} conf={confidence:.2f}")
