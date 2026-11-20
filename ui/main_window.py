import numpy as np
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt, QElapsedTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QStatusBar, QFrame,
    QCheckBox, QSlider, QSplitter, QToolButton, QDoubleSpinBox,
    QFileDialog, QMessageBox,
)

from heatmap.math import CELL_METERS, GRID_SIZE, Obstacle, estimate_router_position
from heatmap.heatmap import gaussian_blob_heatmap
from ui.canvas import HeatmapCanvas
from ui.scanner_panel import SentinelPanel
from security.ap_scanner import APScanner
from security.sessions import SessionStore
from wifi.networking import RSSIProvider
from security.localization import APLocalizer
from ui.theme import QT_STYLESHEET


class AnimationEngine:
    def __init__(self, speed: float = 3.0):
        self._speed = speed
        self._current: np.ndarray | None = None
        self._target: np.ndarray | None = None

    def set_target(self, heatmap: np.ndarray):
        self._target = heatmap.copy()
        if self._current is None:
            self._current = heatmap.copy()

    @property
    def has_target(self) -> bool:
        return self._target is not None

    def update(self, delta: float):
        if self._current is None or self._target is None:
            return
        t = min(1.0, delta * self._speed)
        np.add(self._current, (self._target - self._current) * t, out=self._current)

    def current(self) -> np.ndarray:
        if self._current is None:
            return np.full((GRID_SIZE, GRID_SIZE), -90.0, dtype=np.float64)
        return self._current


class PerformanceMonitor:
    def __init__(self, window: int = 20):
        self._times: list[float] = []
        self._window = window

    def record(self, elapsed: float):
        self._times.append(elapsed)
        if len(self._times) > self._window:
            self._times.pop(0)

    @property
    def fps(self) -> float:
        if not self._times:
            return 60.0
        avg = sum(self._times) / len(self._times)
        return 1.0 / avg if avg > 0 else 60.0


class SignalHistoryBuffer:
    def __init__(self, maxlen: int = 100):
        self._buf: list[float | None] = [None] * maxlen
        self._max = maxlen
        self._pos = 0
        self._count = 0

    def push(self, value: float):
        self._buf[self._pos] = value
        self._pos = (self._pos + 1) % self._max
        self._count = min(self._count + 1, self._max)

    def get_all(self) -> list[float | None]:
        if self._count < self._max:
            return self._buf[: self._count]
        return self._buf[self._pos :] + self._buf[: self._pos]

    def clear(self):
        self._buf = [None] * self._max
        self._pos = 0
        self._count = 0


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RFMap — Wi-Fi Survey Mapper")
        self.setMinimumSize(1200, 800)

        self._router_xy: tuple[float, float] | None = None
        self._router_estimated = False
        self._obstacles: list[Obstacle] = []
        self._measured_points: list[tuple[float, float, float]] = []
        self._current_rssi: float | None = None
        self._drag_start: tuple[float, float] | None = None
        self._preview_xy: tuple[float, float] | None = None
        self._last_render_key: tuple = ()
        self._animating = False
        self._device_names: list[str] = []
        self._device_positions: list[tuple[float, float]] = []
        self._ssid: str = ""
        self._survey_mode: bool = False
        self._survey_target_bssid: str | None = None
        self._survey_samples: list = []
        self._survey_fix = None
        self._last_scan_observations: list = []
        self._localizer: APLocalizer | None = None
        self._rssi_worker = None
        self._cell_meters = CELL_METERS
        self._selected_ap_bssid: str | None = None
        self._data_mode = "live"

        self._animation = AnimationEngine(speed=3.0)
        self._perf = PerformanceMonitor()
        self._history = SignalHistoryBuffer(maxlen=80)

        self._scanner = APScanner()
        self._scanner.scan_ready.connect(self._on_scan_ready)
        self._scanner.source_changed.connect(self._on_source_changed)

        self._worker = HeatmapWorker()
        self._worker.result_ready.connect(self._on_heatmap_ready)

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._debounce.timeout.connect(self._compute_now)

        self._anim_timer = QTimer()
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._on_animation_tick)
        self._anim_elapsed = QElapsedTimer()

        self.setStyleSheet(QT_STYLESHEET)
        self._build_ui()

        empty = np.full((GRID_SIZE, GRID_SIZE), -90.0, dtype=np.float64)
        self._canvas.render(empty, [], None, device_positions=[], device_names=[])

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        canvas_container = QVBoxLayout()
        self._canvas = HeatmapCanvas(parent=self)
        canvas_container.addWidget(self._canvas.native)

        self._canvas.on_click = self._on_grid_click
        self._canvas.on_drag_start = self._on_drag_start
        self._canvas.on_drag_move = self._on_drag_move
        self._canvas.on_drag_end = self._on_drag_end

        layout.addLayout(canvas_container, stretch=1)

        self._canvas.canvas.events.key_press.connect(self._on_vispy_key)

        panel = QVBoxLayout()
        panel.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._threat_btn = QPushButton("⚡ Threat Scanner")
        self._threat_btn.setCheckable(True)
        self._threat_btn.toggled.connect(self._on_threat_toggled)
        panel.addWidget(self._threat_btn)
        panel.addSpacing(5)

        self._threat_panel = SentinelPanel()
        self._threat_panel.scan_requested.connect(self._on_scan_requested)
        self._threat_panel.survey_started.connect(self._on_survey_started)
        self._threat_panel.survey_ended.connect(self._on_survey_ended)
        self._threat_panel.export_requested.connect(self._on_export_requested)
        panel.addWidget(self._threat_panel)
        self._threat_panel.hide()

        panel.addWidget(QLabel("Wall material:"))
        self._mat_combo = QComboBox()
        self._mat_combo.addItems(["Drywall", "Brick", "Reinforced Concrete"])
        panel.addWidget(self._mat_combo)
        panel.addSpacing(15)

        floorplan_frame = QFrame()
        floorplan_layout = QVBoxLayout(floorplan_frame)
        floorplan_layout.addWidget(QLabel("Survey setup"))
        floorplan_btn = QPushButton("Import Floor Plan…")
        floorplan_btn.clicked.connect(self._on_import_floorplan)
        floorplan_layout.addWidget(floorplan_btn)
        self._floorplan_lbl = QLabel("Floor plan: none")
        self._floorplan_lbl.setWordWrap(True)
        floorplan_layout.addWidget(self._floorplan_lbl)
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale:"))
        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(0.01, 100.0)
        self._scale_spin.setDecimals(2)
        self._scale_spin.setSuffix(" m/grid")
        self._scale_spin.setValue(self._cell_meters)
        self._scale_spin.setAccessibleName("Floor plan scale in metres per grid cell")
        self._scale_spin.valueChanged.connect(self._on_scale_changed)
        scale_layout.addWidget(self._scale_spin)
        floorplan_layout.addLayout(scale_layout)
        self._scale_lbl = QLabel()
        floorplan_layout.addWidget(self._scale_lbl)
        self._update_scale_label()
        panel.addWidget(floorplan_frame)
        panel.addSpacing(10)

        adapter_layout = QHBoxLayout()
        adapter_layout.addWidget(QLabel("Adapter:"))
        self._adapter_combo = QComboBox()
        self._adapter_combo.setAccessibleName("Wi-Fi adapter")
        self._adapter_combo.addItem("Auto", None)
        for interface in RSSIProvider().available_interfaces():
            self._adapter_combo.addItem(interface, interface)
        self._adapter_combo.currentIndexChanged.connect(self._on_adapter_changed)
        adapter_layout.addWidget(self._adapter_combo)
        panel.addLayout(adapter_layout)

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Survey AP:"))
        self._ap_combo = QComboBox()
        self._ap_combo.addItem("Connected network", None)
        self._ap_combo.setAccessibleName("Access point used for survey measurements")
        self._ap_combo.currentIndexChanged.connect(self._on_selected_ap_changed)
        target_layout.addWidget(self._ap_combo)
        panel.addLayout(target_layout)
        refresh_aps_btn = QPushButton("Refresh Access Points")
        refresh_aps_btn.clicked.connect(self._on_scan_requested)
        panel.addWidget(refresh_aps_btn)
        panel.addSpacing(10)

        self._auto_cb = QCheckBox("Auto-sample")
        self._auto_cb.toggled.connect(self._on_auto_toggled)
        panel.addWidget(self._auto_cb)
        panel.addSpacing(15)

        self._point_lbl = QLabel("Data points: 0")
        panel.addWidget(self._point_lbl)
        self._fps_lbl = QLabel("FPS: --")
        panel.addWidget(self._fps_lbl)
        panel.addSpacing(10)

        self._ssid_lbl = QLabel("Network: ---")
        panel.addWidget(self._ssid_lbl)
        self._devices_lbl = QLabel("Connected: ---")
        panel.addWidget(self._devices_lbl)
        self._router_lbl = QLabel("Router: ---")
        panel.addWidget(self._router_lbl)
        panel.addSpacing(15)

        frame = QFrame()
        fl = QVBoxLayout(frame)
        fl.addWidget(QLabel("Status"))
        self._rssi_lbl = QLabel("RSSI: --- dBm")
        fl.addWidget(self._rssi_lbl)
        self._source_lbl = QLabel("Source: ---")
        fl.addWidget(self._source_lbl)
        panel.addWidget(frame)

        lerp_frame = QFrame()
        ll = QVBoxLayout(lerp_frame)
        ll.addWidget(QLabel("Smoothness"))
        self._lerp_slider = QSlider(Qt.Orientation.Horizontal)
        self._lerp_slider.setMinimum(1)
        self._lerp_slider.setMaximum(10)
        self._lerp_slider.setValue(4)
        self._lerp_slider.valueChanged.connect(
            lambda v: setattr(self._animation, "_speed", v * 0.8)
        )
        ll.addWidget(self._lerp_slider)
        panel.addWidget(lerp_frame)

        panel.addSpacing(10)
        demo_btn = QPushButton("Load DEMO Data (20 pts)")
        demo_btn.clicked.connect(self._on_demo)
        panel.addWidget(demo_btn)
        panel.addSpacing(5)
        reset_btn = QPushButton("Clear All Data")
        reset_btn.clicked.connect(self._on_reset)
        panel.addWidget(reset_btn)
        panel.addStretch()
        layout.addLayout(panel, stretch=0)

        self._demo_banner = QLabel(
            "DEMO DATA — this heatmap is simulated and must not be used for a real survey. Clear it before recording live measurements."
        )
        self._demo_banner.setWordWrap(True)
        self._demo_banner.setProperty("rfmapRole", "demoWarning")
        self._demo_banner.setAccessibleName("Demo data warning")
        self._demo_banner.hide()
        canvas_container.insertWidget(0, self._demo_banner)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage(
            "Click = record signal  |  Drag = draw wall  |  Arrows = rotate  |  RSSI updates live"
        )

    def _on_threat_toggled(self, checked: bool):
        if checked:
            self._threat_panel.show()
            self._on_scan_requested()
        else:
            self._threat_panel.hide()
            self._scanner.stop()
            self._scanner.wait()

    def _on_scan_requested(self):
        if not self._scanner.isRunning():
            self._scanner.start()
        self._scanner.scan_now()

    def _on_scan_ready(self, observations):
        self._last_scan_observations = observations
        self._threat_panel.update_from_scan(observations)
        self._refresh_ap_selector(observations)

        # Run RogueDetector classification
        from security.detection import RogueDetector
        if not hasattr(self, "_rogue_detector") or self._rogue_detector is None:
            self._rogue_detector = RogueDetector(self._threat_panel._whitelist)
        reports = self._rogue_detector.classify(observations)
        self._threat_panel.update_alerts(list(reports.values()))

        if self._survey_mode and self._survey_target_bssid:
            target_obs = next(
                (o for o in observations if o.bssid == self._survey_target_bssid),
                None,
            )
            if target_obs:
                self._threat_panel.set_status(
                    f"SURVEY: {self._survey_target_bssid} — RSSI {target_obs.rssi:.1f} dBm"
                )

    def _on_source_changed(self, desc: str):
        self._threat_panel.set_status(f"Scanner: {desc}")
        self._status.showMessage(desc)

    def attach_rssi_worker(self, worker):
        """Connect adapter selection after the application creates its RSSI worker."""
        self._rssi_worker = worker
        self._on_adapter_changed(self._adapter_combo.currentIndex())

    def _on_adapter_changed(self, _index: int):
        interface = self._adapter_combo.currentData()
        self._scanner.set_interface(interface)
        if self._rssi_worker is not None:
            self._rssi_worker.set_interface(interface)

    def _refresh_ap_selector(self, observations):
        selected = self._selected_ap_bssid
        self._ap_combo.blockSignals(True)
        self._ap_combo.clear()
        self._ap_combo.addItem("Connected network", None)
        for observation in observations:
            name = observation.ssid or "(hidden)"
            self._ap_combo.addItem(
                f"{name} · {observation.bssid} · {observation.rssi:.0f} dBm",
                observation.bssid,
            )
        index = self._ap_combo.findData(selected)
        self._ap_combo.setCurrentIndex(index if index >= 0 else 0)
        self._ap_combo.blockSignals(False)
        self._on_selected_ap_changed(self._ap_combo.currentIndex())

    def _on_selected_ap_changed(self, _index: int):
        self._selected_ap_bssid = self._ap_combo.currentData()
        self._threat_panel.set_target_bssid(self._selected_ap_bssid)
        if self._selected_ap_bssid:
            self._status.showMessage(
                "Selected AP readings update when access points are refreshed."
            )

    def _selected_ap_rssi(self) -> float | None:
        if not self._selected_ap_bssid:
            return self._current_rssi
        target = next(
            (obs for obs in self._last_scan_observations if obs.bssid == self._selected_ap_bssid),
            None,
        )
        if target is None:
            return None
        if target.source == "simulated":
            self._show_demo_warning("SIMULATED ACCESS-POINT DATA")
            return None
        return target.rssi

    def _on_import_floorplan(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Floor Plan",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All files (*)",
        )
        if not path:
            return
        if not self._canvas.set_floorplan(path):
            QMessageBox.warning(self, "RFMap", "RFMap could not open that floor-plan image.")
            return
        from pathlib import Path
        self._floorplan_lbl.setText(f"Floor plan: {Path(path).name}")
        self._status.showMessage("Floor plan imported. Set its scale before recording measurements.")

    def _update_scale_label(self):
        width_m = GRID_SIZE * self._cell_meters
        self._scale_lbl.setText(f"Map size: {width_m:.1f} × {width_m:.1f} m")

    def _on_scale_changed(self, value: float):
        self._cell_meters = value
        self._update_scale_label()
        self._request_compute()

    def _show_demo_warning(self, title: str = "DEMO DATA"):
        self._demo_banner.setText(
            f"{title} — this heatmap is simulated and must not be used for a real survey. "
            "Clear it before recording live measurements."
        )
        self._demo_banner.show()

    def _on_survey_started(self, bssid: str):
        self._survey_mode = True
        self._survey_target_bssid = bssid
        self._survey_samples = []
        self._survey_fix = None
        self._localizer = APLocalizer(bssid)
        self._status.showMessage(f"SURVEY MODE: {bssid} — click floor to record samples")

    def _on_survey_ended(self):
        self._survey_mode = False
        self._survey_target_bssid = None
        self._localizer = None
        self._status.showMessage("Survey mode ended.")

    def _on_survey_click(self, x: float, y: float):
        if not self._survey_mode or not self._survey_target_bssid:
            return
        target = next(
            (o for o in self._last_scan_observations if o.bssid == self._survey_target_bssid),
            None,
        )
        if target is None:
            self._status.showMessage("Target AP not visible in last scan — cannot record")
            return
        if target.rssi < -95.0:
            self._status.showMessage("RSSI too weak to record sample")
            return
        ix, iy = self._get_grid(x, y)
        from security.types import SurveySample
        sample = SurveySample(
            bssid=target.bssid,
            x=float(ix),
            y=float(iy),
            rssi=target.rssi,
            channel=target.channel,
        )
        if self._localizer is not None:
            self._localizer.add_sample(sample)
            self._survey_fix = self._localizer.fix
        self._survey_samples.append(sample)
        self._threat_panel.set_survey_sample_count(len(self._survey_samples))
        self._status.showMessage(
            f"SURVEY: ({ix:.0f}, {iy:.0f}) RSSI {target.rssi:.1f} dBm — {len(self._survey_samples)} samples"
        )

    def _on_export_requested(self):
        if not self._survey_samples and not self._last_scan_observations:
            self._threat_panel.set_status("No survey or scan data to export")
            return
        directory = QFileDialog.getExistingDirectory(self, "Export RFMap Session To")
        if not directory:
            return
        fixes = [self._survey_fix] if self._survey_fix is not None else []
        source = self._last_scan_observations[0].source if self._last_scan_observations else "none"
        session_dir = SessionStore(directory).save_session(
            self._survey_samples,
            fixes,
            self._threat_panel._alerts,
            {"scanner_source": source, "survey_samples": len(self._survey_samples)},
        )
        self._threat_panel.set_status(f"Session exported to {session_dir}")

    def _on_vispy_key(self, event):
        step = 5
        mapping = {
            "Up":    (step, 0),
            "Down":  (-step, 0),
            "Left":  (0, -step),
            "Right": (0, step),
        }
        if event.key in mapping:
            de, da = mapping[event.key]
            self._canvas.rotate(de, da)


    def _get_grid(self, x: float, y: float) -> tuple[int, int]:
        ix = max(0, min(GRID_SIZE - 1, int(round(x))))
        iy = max(0, min(GRID_SIZE - 1, int(round(y))))
        return ix, iy

    def _on_grid_click(self, x: float, y: float):
        if self._survey_mode:
            self._on_survey_click(x, y)
            return
        ix, iy = self._get_grid(x, y)
        self._add_point(float(ix), float(iy))

    def _on_drag_start(self, x: float, y: float):
        ix, iy = self._get_grid(x, y)
        self._drag_start = (float(ix), float(iy))

    def _on_drag_move(self, x: float, y: float):
        if self._drag_start is None:
            return
        self._preview_xy = (float(x), float(y))

    def _on_drag_end(self, x: float, y: float):
        if self._drag_start is None:
            return
        sx, sy = self._drag_start
        self._drag_start = None
        self._preview_xy = None
        ix, iy = self._get_grid(x, y)
        dx = abs(ix - sx)
        dy = abs(iy - sy)
        if dx > 1 or dy > 1:
            self._add_wall(sx, sy, float(ix), float(iy))


    def _add_point(self, x: float, y: float, quiet: bool = False):
        if self._data_mode == "demo":
            if not quiet:
                self._status.showMessage("Clear demo data before recording a live survey.")
            return
        rssi = self._selected_ap_rssi()
        if rssi is None:
            if not quiet:
                self._status.showMessage("No reading for the selected adapter or AP — refresh access points and try again.")
            return
        self._measured_points.append((x, y, rssi))
        self._last_click_xy = (x, y)
        self._point_lbl.setText(f"Data points: {len(self._measured_points)}")
        self._update_router()
        if not quiet:
            self._status.showMessage(
                f"Recorded at ({x:.0f}, {y:.0f}): {rssi:.1f} dBm"
            )
        self._compute_now()


    def _add_wall(self, x1: float, y1: float, x2: float, y2: float):
        mat = self._mat_combo.currentText()
        self._obstacles.append(Obstacle(x1, y1, x2, y2, mat))
        self._status.showMessage(
            f"Wall: ({x1:.0f},{y1:.0f}) → ({x2:.0f},{y2:.0f}) [{mat}]"
        )
        self._request_compute()

    def _update_router(self):
        if not self._measured_points:
            return
        est = estimate_router_position(self._measured_points)
        if est is not None:
            self._router_xy = est
            self._router_estimated = True
            self._router_lbl.setText(f"Router: ({est[0]:.0f}, {est[1]:.0f})")
        self._update_device_positions()


    def update_ssid(self, ssid: str):
        self._ssid = ssid
        self._ssid_lbl.setText(f"Network: {ssid}")

    def update_devices(self, device_names: list[str]):
        self._device_names = device_names
        count = len(device_names)
        self._devices_lbl.setText(
            f"Connected: {count} device{'s' if count != 1 else ''}"
        )
        if count > 0:
            names_text = ", ".join(device_names[:5])
            if count > 5:
                names_text += f" +{count - 5} more"
            self._devices_lbl.setToolTip(names_text)
        self._update_device_positions()

    def _update_device_positions(self):
        # The OS reports associated devices, not their physical locations.
        self._device_positions = []


    def update_rssi(self, rssi: float, source: str):
        self._current_rssi = rssi
        self._rssi_lbl.setText(f"RSSI: {rssi:.1f} dBm")
        self._history.push(rssi)
        self._canvas.update_waterfall(rssi)

    def update_source(self, desc: str):
        self._source_lbl.setText(f"Source: {desc}")


    def _request_compute(self):
        self._debounce.start()

    def _compute_now(self):
        if self._router_xy is None and not self._measured_points:
            return
        self._worker.request(
            self._router_xy, self._obstacles, self._measured_points, self._cell_meters
        )

    def _on_heatmap_ready(self, heatmap: np.ndarray):
        n = len(self._measured_points)
        key = (n, tuple(self._obstacles), self._router_xy, self._cell_meters)
        if key == self._last_render_key:
            return
        self._last_render_key = key

        self._animation.set_target(heatmap)

        self._canvas.render(
            heatmap, self._obstacles, self._router_xy,
            device_positions=self._device_positions,
            device_names=self._device_names,
        )

        if not self._animating:
            self._animating = True
            self._anim_elapsed.start()
            self._anim_timer.start()


    def _on_animation_tick(self):
        delta = self._anim_elapsed.elapsed() / 1000.0
        self._anim_elapsed.restart()
        self._animation.update(delta)

        fps = self._perf.fps
        self._fps_lbl.setText(f"FPS: {fps:.0f}")


    def _on_auto_toggled(self, checked: bool):
        if checked:
            self._auto_timer = QTimer()
            self._auto_timer.setInterval(1000)
            self._auto_timer.timeout.connect(self._record_auto)
            self._auto_timer.start()
        elif hasattr(self, "_auto_timer"):
            self._auto_timer.stop()
            del self._auto_timer

    def _record_auto(self):
        if hasattr(self, "_last_click_xy"):
            lx, ly = self._last_click_xy
        else:
            lx = ly = GRID_SIZE / 2.0
        self._add_point(lx, ly, quiet=True)

    def _on_demo(self):
        import random
        self._on_reset()
        self._data_mode = "demo"
        rx, ry = GRID_SIZE * 0.3, GRID_SIZE * 0.4
        for _ in range(20):
            angle = random.uniform(0, 2 * 3.14159)
            dist = random.uniform(1, 35)
            x = max(0, min(GRID_SIZE - 1, rx + dist * np.cos(angle)))
            y = max(0, min(GRID_SIZE - 1, ry + dist * np.sin(angle)))
            rssi = max(-85, min(-35, -30 - 10 * np.log10(max(1, dist * 0.5))))
            self._measured_points.append((float(x), float(y), rssi))
        self._point_lbl.setText(f"Data points: {len(self._measured_points)}")
        self._update_router()
        self._show_demo_warning()
        self._status.showMessage(
            f"Loaded {len(self._measured_points)} DEMO points → router auto-detected"
        )
        self._compute_now()


    def _on_reset(self):
        if hasattr(self, "_auto_timer"):
            self._auto_timer.stop()
            del self._auto_timer
            self._auto_cb.setChecked(False)
        self._router_xy = None
        self._data_mode = "live"
        self._demo_banner.hide()
        self._router_estimated = False
        self._obstacles.clear()
        self._measured_points.clear()
        self._last_render_key = ()
        self._history.clear()
        self._point_lbl.setText("Data points: 0")
        self._router_lbl.setText("Router: ---")
        self._device_names = []
        self._device_positions = []
        empty = np.full((GRID_SIZE, GRID_SIZE), -90.0, dtype=np.float64)
        self._canvas.render(empty, [], None, device_positions=[], device_names=[])
        self._status.showMessage("All data cleared.")


    def closeEvent(self, event):
        if hasattr(self, "_auto_timer"):
            self._auto_timer.stop()
        self._anim_timer.stop()
        self._worker.quit()
        self._worker.wait()
        self._scanner.stop()
        self._scanner.wait()
        super().closeEvent(event)
