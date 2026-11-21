"""Off-thread heatmap computation with coalescing of pending requests."""
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from rfmap.core.constants import CELL_METERS
from rfmap.core.geometry import Obstacle
from rfmap.core.heatmap import gaussian_blob_heatmap


class HeatmapWorker(QThread):
    result_ready = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._router_xy: tuple[float, float] | None = None
        self._obstacles: list[Obstacle] = []
        self._measured_points: list[tuple[float, float, float]] = []
        self._pending = False
        self._running = False
        self._cell_meters = CELL_METERS

    def request(
        self,
        router_xy: tuple[float, float] | None,
        obstacles: list[Obstacle],
        measured_points: list[tuple[float, float, float]],
        cell_meters: float,
    ):
        self._router_xy = router_xy
        self._obstacles = list(obstacles)
        self._measured_points = list(measured_points)
        self._cell_meters = cell_meters
        if self._running:
            self._pending = True
        else:
            self.start()

    def run(self):
        self._running = True
        while True:
            router_xy = self._router_xy
            obstacles = self._obstacles
            measured = self._measured_points
            self._pending = False

            heatmap = gaussian_blob_heatmap(
                measured, router_xy, obstacles, cell_meters=self._cell_meters
            )
            self.result_ready.emit(heatmap)

            if not self._pending:
                break
        self._running = False
