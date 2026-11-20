import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from heatmap.math import GRID_SIZE, Obstacle, segments_intersect
from security.types import LocalizationFix, SurveySample
from security.particle_filter import ParticleFilter

logger = logging.getLogger(__name__)


class APLocalizer:
    fix_updated = None

    def __init__(self, target_bssid: str):
        self.target_bssid = target_bssid
        self.samples: list[SurveySample] = []
        self._fix: LocalizationFix | None = None
        self._obstacles: list[Obstacle] = []
        self._particle_filter = ParticleFilter(n_particles=2000, sigma=4.0)

    def set_obstacles(self, obstacles: list[Obstacle]) -> None:
        self._obstacles = list(obstacles)

    def add_sample(self, sample: SurveySample) -> None:
        if sample.bssid != self.target_bssid:
            return
        if sample.rssi < -95.0:
            return
        self.samples.append(sample)
        self._fix = self._solve()
        if self._fix is not None:
            self._particle_filter.seed_around(self._fix.x, self._fix.y, spread=max(self._fix.ellipse_major, 5.0))
            self._particle_filter.update(
                [(s.x, s.y, s.rssi) for s in self.samples],
                obstacles=self._obstacles,
            )
            pf_x, pf_y, pf_spread = self._particle_filter.estimate()
            if pf_spread < 2.0 * self._fix.ellipse_major:
                self._fix.particle_centroid = (pf_x, pf_y)

    @property
    def fix(self) -> LocalizationFix | None:
        return self._fix

    @property
    def n_samples(self) -> int:
        return len(self.samples)

    @property
    def sample_positions(self) -> list[tuple[float, float]]:
        return [(s.x, s.y) for s in self.samples]

    def _solve(self) -> LocalizationFix | None:
        if len(self.samples) < 3:
            return None

        xs = np.array([s.x for s in self.samples], dtype=np.float64)
        ys = np.array([s.y for s in self.samples], dtype=np.float64)
        rssi_vals = np.array([s.rssi for s in self.samples], dtype=np.float64)

        tx_est = float(np.max(rssi_vals))

        def _make_residuals(xs_arr, ys_arr, rssi_arr):
            def _residuals(params):
                x, y = params
                dists = np.sqrt((xs_arr - x) ** 2 + (ys_arr - y) ** 2)
                dists = np.maximum(dists, 1.0)
                predicted = tx_est - 10.0 * 2.4 * np.log10(dists)
                wall_loss = np.array([
                    sum(
                        obs.attenuation_db
                        for obs in self._obstacles
                        if segments_intersect(x, y, float(sx), float(sy), obs.x1, obs.y1, obs.x2, obs.y2)
                    )
                    for sx, sy in zip(xs_arr, ys_arr)
                ])
                return rssi_arr - (predicted - wall_loss)
            return _residuals

        residuals = _make_residuals(xs, ys, rssi_vals)

        try:
            from scipy.optimize import least_squares

            x0 = np.array([np.average(xs, weights=(rssi_vals + 100) ** 2),
                           np.average(ys, weights=(rssi_vals + 100) ** 2)])
            fit = least_squares(
                residuals, x0,
                bounds=([0, 0], [GRID_SIZE, GRID_SIZE]),
                loss="huber",
            )
            x_opt, y_opt = fit.x
            J = fit.jac
            residuals_vec = fit.fun
            sigma_hat = np.sqrt(np.sum(residuals_vec ** 2) / max(len(residuals_vec) - 2, 1))

            try:
                cov = sigma_hat ** 2 * np.linalg.inv(J.T @ J)
            except np.linalg.LinAlgError:
                cov = np.eye(2) * 1e6

            eigenvalues = np.real(np.linalg.eigvalsh(cov))
            gdop = float(np.linalg.cond(J.T @ J))

            outlier_mask = np.abs(residuals_vec) < 3 * sigma_hat
            if np.sum(outlier_mask) >= 3 and np.sum(~outlier_mask) > 0:
                filtered_xs = xs[outlier_mask]
                filtered_ys = ys[outlier_mask]
                filtered_rssi = rssi_vals[outlier_mask]
                filtered_residuals = _make_residuals(filtered_xs, filtered_ys, filtered_rssi)
                fit2 = least_squares(
                    filtered_residuals, fit.x,
                    bounds=([0, 0], [GRID_SIZE, GRID_SIZE]),
                    loss="huber",
                )
                x_opt, y_opt = fit2.x
                J = fit2.jac
                residuals_vec = fit2.fun
                sigma_hat = np.sqrt(np.sum(residuals_vec ** 2) / max(len(residuals_vec) - 2, 1))
                try:
                    cov = sigma_hat ** 2 * np.linalg.inv(J.T @ J)
                except np.linalg.LinAlgError:
                    cov = np.eye(2) * 1e6
                gdop = float(np.linalg.cond(J.T @ J))
        except Exception as exc:
            logger.debug("Localization solve failed: %s", exc)
            return None

        major = float(2.0 * np.sqrt(max(float(np.max(eigenvalues)), 0.0)))
        minor = float(2.0 * np.sqrt(max(float(np.min(eigenvalues)), 0.0)))
        _, eigenvectors = np.linalg.eig(cov)
        eigenvectors = np.real(eigenvectors)
        angle = float(np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0]))

        confidence = float(max(0.1, min(0.99, 1.0 / (1.0 + gdop / max(len(self.samples), 1)))))

        fix = LocalizationFix(
            bssid=self.target_bssid,
            x=float(x_opt),
            y=float(y_opt),
            covariance=cov,
            gdop=gdop,
            n_samples=len(self.samples),
            rssi_error_sigma=float(sigma_hat),
        )
        self._fix = fix
        return fix