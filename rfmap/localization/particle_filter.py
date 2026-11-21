import numpy as np

from rfmap.core.constants import GRID_SIZE
from rfmap.core.geometry import Obstacle, segments_intersect


def _path_loss_predicted(tx_power: float, distance: float, n: float = 2.4, d0: float = 1.0) -> float:
    return tx_power - 10.0 * n * np.log10(max(distance, d0) / d0)


def _wall_attenuation(
    px: float, py: float,
    sx: float, sy: float,
    obstacles: list[Obstacle],
) -> float:
    total = 0.0
    for obs in obstacles:
        if segments_intersect(px, py, sx, sy, obs.x1, obs.y1, obs.x2, obs.y2):
            total += obs.attenuation_db
    return total


class ParticleFilter:
    def __init__(self, n_particles: int = 2000, sigma: float = 4.0):
        self.n_particles = n_particles
        self.sigma = sigma
        self._particles: np.ndarray | None = None
        self._weights: np.ndarray | None = None
        self._initialized = False

    def _init_uniform(self):
        rng = np.random.default_rng(0)
        self._particles = rng.uniform(0, GRID_SIZE, size=(self.n_particles, 2))
        self._weights = np.ones(self.n_particles, dtype=np.float64) / self.n_particles
        self._initialized = True

    def seed_around(self, x: float, y: float, spread: float = 10.0):
        rng = np.random.default_rng(0)
        self._particles = rng.normal([x, y], spread, size=(self.n_particles, 2))
        self._particles[:, 0] = np.clip(self._particles[:, 0], 0, GRID_SIZE)
        self._particles[:, 1] = np.clip(self._particles[:, 1], 0, GRID_SIZE)
        self._weights = np.ones(self.n_particles, dtype=np.float64) / self.n_particles
        self._initialized = True

    def update(
        self,
        samples: list[tuple[float, float, float]],
        obstacles: list[Obstacle] | None = None,
        tx_power: float = -30.0,
    ) -> None:
        if not self._initialized:
            self._init_uniform()

        if not samples:
            return

        if obstacles is None:
            obstacles = []

        xs = np.array([s[0] if isinstance(s, (tuple, list)) else s.x for s in samples], dtype=np.float64)
        ys = np.array([s[1] if isinstance(s, (tuple, list)) else s.y for s in samples], dtype=np.float64)
        rssi = np.array([s[2] if isinstance(s, (tuple, list)) else s.rssi for s in samples], dtype=np.float64)

        for i in range(self.n_particles):
            px, py = self._particles[i]
            predicted = np.array([
                _path_loss_predicted(tx_power, np.sqrt((px - sx) ** 2 + (py - sy) ** 2))
                - _wall_attenuation(px, py, sx, sy, obstacles)
                for sx, sy in zip(xs, ys)
            ])
            residuals = rssi - predicted
            self._weights[i] = np.exp(-0.5 * np.sum(residuals ** 2) / (self.sigma ** 2 * len(samples)))

        total_weight = np.sum(self._weights)
        if total_weight > 0:
            self._weights /= total_weight
        else:
            self._weights = np.ones(self.n_particles, dtype=np.float64) / self.n_particles

        ess = 1.0 / np.sum(self._weights ** 2)
        if ess < self.n_particles / 2:
            self._resample()

    def _resample(self):
        indices = self._systematic_resample()
        self._particles = self._particles[indices]
        self._weights = np.ones(self.n_particles, dtype=np.float64) / self.n_particles

    def _systematic_resample(self) -> np.ndarray:
        n = self.n_particles
        positions = (np.arange(n) + np.random.uniform(0, 1)) / n
        cumulative = np.cumsum(self._weights)
        cumulative[-1] = 1.0
        indices = np.searchsorted(cumulative, positions)
        return np.clip(indices, 0, n - 1)

    def estimate(self) -> tuple[float, float, float]:
        if not self._initialized or self._particles is None:
            return 0.0, 0.0, 0.0

        weights = self._weights
        x = float(np.sum(weights * self._particles[:, 0]))
        y = float(np.sum(weights * self._particles[:, 1]))

        spread = float(2.0 * np.sqrt(
            np.sum(weights * (self._particles[:, 0] - x) ** 2)
            + np.sum(weights * (self._particles[:, 1] - y) ** 2)
        ))

        return x, y, spread
