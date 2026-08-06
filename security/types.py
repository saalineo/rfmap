from dataclasses import dataclass, field
import math
import time
from typing import Optional

import numpy as np


@dataclass
class APObservation:
    bssid: str
    ssid: str | None
    channel: int
    frequency_mhz: int
    rssi: float
    security: str
    first_seen: float = field(default_factory=time.time)
    source: str = "unknown"


@dataclass
class SurveySample:
    bssid: str
    x: float
    y: float
    rssi: float
    channel: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class RogueReport:
    bssid: str
    ssid: str | None
    classification: str
    rules_hit: list[str] = field(default_factory=list)
    confidence: float = 0.0
    channel: int = 0
    first_seen: float = 0.0


@dataclass
class LocalizationFix:
    bssid: str
    x: float
    y: float
    covariance: np.ndarray
    gdop: float
    n_samples: int
    rssi_error_sigma: float
    particle_centroid: tuple[float, float] | None = None

    @property
    def ellipse_major(self) -> float:
        eigenvalues = np.linalg.eigvalsh(self.covariance)
        return float(2.0 * np.sqrt(max(float(np.max(eigenvalues)), 0.0)))

    @property
    def ellipse_minor(self) -> float:
        eigenvalues = np.linalg.eigvalsh(self.covariance)
        return float(2.0 * np.sqrt(max(float(np.min(eigenvalues)), 0.0)))

    @property
    def ellipse_angle(self) -> float:
        eigenvalues, eigenvectors = np.linalg.eigh(self.covariance)
        major_idx = np.argmax(eigenvalues)
        return float(np.arctan2(eigenvectors[1, major_idx], eigenvectors[0, major_idx]))

    @property
    def confidence(self) -> float:
        if self.gdop <= 0:
            return 0.1
        norm = self.gdop / max(self.n_samples, 1)
        return float(max(0.1, min(0.99, 1.0 / (1.0 + norm))))