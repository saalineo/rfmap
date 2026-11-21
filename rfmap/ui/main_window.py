import numpy as np
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFileDialog, QMessageBox,
)

from rfmap.core.constants import CELL_METERS, GRID_SIZE
from rfmap.core.geometry import Obstacle
from rfmap.core.history import SignalHistoryBuffer
from rfmap.core.propagation import estimate_router_position
from rfmap.ui.canvas.heatmap_canvas import HeatmapCanvas
from rfmap.ui.chrome.survey_header import SurveyHeader
from rfmap.ui.chrome.survey_status_bar import SurveyStatusBar
from rfmap.ui.survey.sidebar import SurveySidebar
from rfmap.scanning.worker import APScanner
from rfmap.storage.sessions import SessionStore
from rfmap.wifi.provider import RSSIProvider
from rfmap.localization.localizer import APLocalizer
from rfmap.ui.theme.stylesheet import QT_STYLESHEET
from rfmap.ui.workers.heatmap_worker import HeatmapWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RFMap — Wi-Fi Survey Mapper")
        self.setMinimumSize(1100, 700)

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

        self.setStyleSheet(QT_STYLESHEET)
        self._build_ui()

        empty = np.full((GRID_SIZE, GRID_SIZE), -90.0, dtype=np.float64)
        self._canvas.render(empty, [], None, device_positions=[], device_names=[])

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        self._canvas = HeatmapCanvas(parent=self)
        self._canvas.on_click = self._on_grid_click
        self._canvas.on_drag_start = self._on_drag_start
        self._canvas.on_drag_move = self._on_drag_move
        self._canvas.on_drag_end = self._on_drag_end
        self._canvas.canvas.events.key_press.connect(self._on_vispy_key)
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(8)

        self._sidebar = SurveySidebar(
            self._cell_meters,
            RSSIProvider().available_interfaces(),
            self._on_import_floorplan,
            self._on_scale_changed,
            self._on_adapter_changed,
            self._on_selected_ap_changed,
            self._on_scan_requested,
            self._on_start_survey_clicked,
            self._on_finish_survey_clicked,
            self._on_demo,
            self._on_reset,
            self._on_threat_toggled,
        )
        self._floorplan_lbl = self._sidebar.floor_plan_setup.file_label
        self._scale_spin = self._sidebar.floor_plan_setup.scale_spin
        self._scale_lbl = self._sidebar.floor_plan_setup.map_size_label
        self._adapter_combo = self._sidebar.network_selector.adapter_combo
        self._ap_combo = self._sidebar.network_selector.ap_combo
        self._start_survey_btn = self._sidebar.survey_capture.start_button
        self._finish_survey_btn = self._sidebar.survey_capture.finish_button
        self._point_lbl = self._sidebar.survey_capture.point_label
        self._rssi_lbl = self._sidebar.survey_capture.rssi_label
        self._source_lbl = self._sidebar.survey_capture.source_label
        self._mat_combo = self._sidebar.advanced_tools.material_combo
        self._threat_btn = self._sidebar.advanced_tools.assessment_toggle
        self._threat_panel = self._sidebar.advanced_tools.assessment_panel
        self._survey_status_lbl = self._sidebar.status_label
        self._demo_banner = QLabel(
            "DEMO DATA — this heatmap is simulated and must not be used for a real survey. Clear it before recording live measurements."
        )
        self._demo_banner.setWordWrap(True)
        self._demo_banner.setProperty("rfmapRole", "demoWarning")
        self._demo_banner.setAccessibleName("Demo data warning")
        self._demo_banner.hide()
        canvas_layout.addWidget(self._demo_banner)
        canvas_layout.addWidget(self._canvas.native)
        layout.addWidget(canvas_container, stretch=1)
        layout.addWidget(self._sidebar)

        self._threat_panel.scan_requested.connect(self._on_scan_requested)
        self._threat_panel.survey_started.connect(self._on_survey_started)
        self._threat_panel.survey_ended.connect(self._on_survey_ended)
        self._threat_panel.export_requested.connect(self._on_export_requested)
        self._update_scale_label()

        self.setMenuWidget(SurveyHeader())
        self._status = SurveyStatusBar()
        self.setStatusBar(self._status)
        self._status.show_hint(
            "Start a survey, click the map to record a sample, and drag to draw a wall."
        )

    def _on_threat_toggled(self, checked: bool):
        self._threat_btn.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
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
        from rfmap.sentinel.detection import RogueDetector
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
        self._ap_combo.addItem("Choose an access point…", None)
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
        self._start_survey_btn.setEnabled(bool(self._selected_ap_bssid) and not self._survey_mode)
        if self._selected_ap_bssid:
            self._status.showMessage(
                "Access point selected. Start the survey when you are ready to capture."
            )

    def _on_start_survey_clicked(self):
        if not self._selected_ap_bssid:
            self._status.showMessage("Choose an access point before starting a survey.")
            return
        self._on_survey_started(self._selected_ap_bssid)

    def _on_finish_survey_clicked(self):
        self._on_survey_ended()
        self._on_export_requested()

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
        if self._data_mode == "demo":
            self._status.showMessage("Clear demo data before starting a live survey.")
            return
        self._survey_mode = True
        self._survey_target_bssid = bssid
        self._survey_fix = None
        self._localizer = APLocalizer(bssid)
        self._ap_combo.setEnabled(False)
        self._start_survey_btn.setEnabled(False)
        self._finish_survey_btn.setEnabled(True)
        self._survey_status_lbl.setText("Survey active. Click the map at each measurement location.")
        self._status.showMessage(f"SURVEY MODE: {bssid} — click floor to record samples")

    def _on_survey_ended(self):
        self._survey_mode = False
        self._survey_target_bssid = None
        self._localizer = None
        self._ap_combo.setEnabled(True)
        self._start_survey_btn.setEnabled(bool(self._selected_ap_bssid))
        self._finish_survey_btn.setEnabled(False)
        self._survey_status_lbl.setText("Survey finished. Start another survey or export this session.")
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
        from rfmap.models import SurveySample
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
        self._measured_points.append((float(ix), float(iy), target.rssi))
        self._last_click_xy = (float(ix), float(iy))
        self._point_lbl.setText(f"Data points: {len(self._measured_points)}")
        self._update_router()
        self._compute_now()
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
        self._status.showMessage("Start a survey before recording measurements.")

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
        self._update_device_positions()


    def update_ssid(self, ssid: str):
        self._ssid = ssid

    def update_devices(self, device_names: list[str]):
        self._device_names = device_names
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

        self._canvas.render(
            heatmap, self._obstacles, self._router_xy,
            device_positions=self._device_positions,
            device_names=self._device_names,
        )

    def _on_demo(self):
        import random
        self._on_reset(confirm=False)
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


    def _on_reset(self, confirm: bool = True):
        if confirm and self._measured_points:
            answer = QMessageBox.question(
                self,
                "Clear survey data?",
                "This removes all recorded points and walls from the current survey.",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Discard,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                return
        self._router_xy = None
        self._data_mode = "live"
        self._demo_banner.hide()
        self._survey_mode = False
        self._survey_target_bssid = None
        self._survey_samples = []
        self._survey_fix = None
        self._localizer = None
        self._ap_combo.setEnabled(True)
        self._start_survey_btn.setEnabled(bool(self._selected_ap_bssid))
        self._finish_survey_btn.setEnabled(False)
        self._survey_status_lbl.setText("1. Import a floor plan, then choose an access point.")
        self._router_estimated = False
        self._obstacles.clear()
        self._measured_points.clear()
        self._last_render_key = ()
        self._history.clear()
        self._point_lbl.setText("Data points: 0")
        self._device_names = []
        self._device_positions = []
        empty = np.full((GRID_SIZE, GRID_SIZE), -90.0, dtype=np.float64)
        self._canvas.render(empty, [], None, device_positions=[], device_names=[])
        self._status.showMessage("All data cleared.")


    def closeEvent(self, event):
        self._worker.quit()
        self._worker.wait()
        self._scanner.stop()
        self._scanner.wait()
        super().closeEvent(event)
