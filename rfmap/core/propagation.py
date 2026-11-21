"""Physics baseline, router estimate, and combined heatmap computation."""
import logging

import numpy as np
from scipy.interpolate import RBFInterpolator

from rfmap.core.constants import CELL_METERS, D0, GRID_SIZE, PATH_LOSS_EXPONENT, TX_POWER_DBM
from rfmap.core.geometry import Obstacle, segments_intersect

logger = logging.getLogger(__name__)


def compute_physics_baseline(
    router_xy: tuple[float, float],
    obstacles: list[Obstacle] | None = None,
    cell_meters: float = CELL_METERS,
) -> np.ndarray:
    if obstacles is None:
        obstacles = []

    rx, ry = router_xy
    xs = np.arange(GRID_SIZE, dtype=np.float64)
    ys = np.arange(GRID_SIZE, dtype=np.float64)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    # RSSI path loss is measured in metres; the grid is only a display unit.
    cell_meters = max(float(cell_meters), 0.01)
    dists = np.sqrt((X - rx) ** 2 + (Y - ry) ** 2) * cell_meters
    dists = np.maximum(dists, D0)

    baseline = TX_POWER_DBM - 10.0 * PATH_LOSS_EXPONENT * np.log10(dists / D0)

    if obstacles:
        obs_data = [(o.x1, o.y1, o.x2, o.y2, o.attenuation_db) for o in obstacles]
        obs_data = [od for od in obs_data if od[4] != 0.0]
        if obs_data:
            for cy in range(GRID_SIZE):
                for cx in range(GRID_SIZE):
                    total_attenuation = 0.0
                    for x1, y1, x2, y2, att in obs_data:
                        if segments_intersect(rx, ry, float(cx), float(cy), x1, y1, x2, y2):
                            total_attenuation += att
                    if total_attenuation > 0.0:
                        baseline[cx, cy] -= total_attenuation

    return baseline


def estimate_router_position(
    measured_points: list[tuple[float, float, float]],
) -> tuple[float, float] | None:
    if not measured_points:
        return None

    if len(measured_points) == 1:
        return (measured_points[0][0], measured_points[0][1])

    total_weight = 0.0
    cx = 0.0
    cy = 0.0
    for x, y, rssi in measured_points:
        weight = (rssi + 100.0) ** 2
        cx += x * weight
        cy += y * weight
        total_weight += weight

    if total_weight == 0.0:
        return (measured_points[0][0], measured_points[0][1])

    ex = cx / total_weight
    ey = cy / total_weight
    ex = max(0.0, min(float(GRID_SIZE - 1), ex))
    ey = max(0.0, min(float(GRID_SIZE - 1), ey))
    return (ex, ey)


def compute_heatmap(
    router_xy: tuple[float, float],
    obstacles: list[Obstacle] | None = None,
    measured_points: list[tuple[float, float, float]] | None = None,
    cell_meters: float = CELL_METERS,
) -> np.ndarray:
    if measured_points is None:
        measured_points = []

    baseline = compute_physics_baseline(router_xy, obstacles, cell_meters)

    if len(measured_points) == 0:
        return np.clip(baseline, -90.0, -30.0)

    pts = np.array([(x, y) for x, y, _ in measured_points], dtype=np.float64)
    vals = np.array([rssi for _, _, rssi in measured_points], dtype=np.float64)

    unique_pts, inverse_indices = np.unique(pts, axis=0, return_inverse=True)
    if len(unique_pts) < len(pts):
        deduped_vals = np.zeros(len(unique_pts), dtype=np.float64)
        counts = np.zeros(len(unique_pts), dtype=np.int64)
        for i, idx in enumerate(inverse_indices):
            deduped_vals[idx] += vals[i]
            counts[idx] += 1
        vals = deduped_vals / counts
        pts = unique_pts

    residuals = np.zeros(len(pts), dtype=np.float64)
    for i, (x, y) in enumerate(pts):
        ix = int(round(x))
        iy = int(round(y))
        ix = max(0, min(GRID_SIZE - 1, ix))
        iy = max(0, min(GRID_SIZE - 1, iy))
        residuals[i] = vals[i] - baseline[ix, iy]

    if len(pts) == 1:
        residual_grid = np.full_like(baseline, residuals[0])
    else:
        xs = np.arange(GRID_SIZE, dtype=np.float64)
        ys = np.arange(GRID_SIZE, dtype=np.float64)
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        grid_points = np.column_stack((X.ravel(), Y.ravel()))

        try:
            rbf = RBFInterpolator(pts, residuals, kernel="multiquadric")
            residual_flat = rbf(grid_points)
            residual_grid = residual_flat.reshape(GRID_SIZE, GRID_SIZE)
        except Exception as exc:
            logger.debug("RBF interpolation failed: %s", exc)
            residual_grid = np.zeros_like(baseline)

    heatmap = baseline + residual_grid
    return np.clip(heatmap, -90.0, -30.0)
