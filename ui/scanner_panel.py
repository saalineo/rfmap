import os
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QComboBox,
    QLabel, QSpinBox, QCheckBox, QFrame, QListWidget,
    QListWidgetItem, QInputDialog, QMessageBox, QSplitter,
    QFileDialog,
)

from security.config import SentinelConfig
from security.types import APObservation, RogueReport
from security.allowlist import WhitelistStore
from security.sessions import SessionStore
from ui.theme import BG_DARK, BG_SURFACE, BG_BORDER, FG, FG_MUTED, RED, YELLOW, GREEN, BLUE


STATUS_GREEN = "#9ece6a"
STATUS_AMBER = "#e0af68"
STATUS_RED = "#f7768e"


class SentinelPanel(QWidget):
    scan_requested = pyqtSignal()
    survey_started = pyqtSignal(str)
    survey_ended = pyqtSignal()
    whitelist_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = SentinelConfig.load()
        self._whitelist = WhitelistStore(self._config.whitelist_path)
        self._observations: list[APObservation] = []
        self._alerts: list[RogueReport] = []
        self._target_bssid: str | None = None
        self._survey_active = False
        self._sample_count = 0

        self._build_ui()
        self._apply_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Alert banner 
        self._alert_banner = QLabel("")
        self._alert_banner.setStyleSheet(
            f"background-color: {RED}; color: {BG_DARK}; padding: 4px 8px; "
            f"border-radius: 4px; font-weight: bold;"
        )
        self._alert_banner.hide()
        layout.addWidget(self._alert_banner)

        # AP Table 
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["●", "SSID", "BSSID", "Ch", "Sec", "RSSI"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(5, Qt.SortOrder.DescendingOrder)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(
            f"QTableWidget {{ background-color: {BG_SURFACE}; color: {FG}; "
            f"border: 1px solid {BG_BORDER}; border-radius: 4px; gridline-color: {BG_BORDER}; }}"
            f"QHeaderView::section {{ background-color: {BG_DARK}; color: {FG}; "
            f"padding: 4px; border: 1px solid {BG_BORDER}; }}"
        )
        layout.addWidget(self._table)

        # Target selector
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target:"))
        self._target_combo = QComboBox()
        self._target_combo.addItem("(none)", "")
        target_layout.addWidget(self._target_combo)
        layout.addLayout(target_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self._scan_btn = QPushButton("Scan Now")
        self._scan_btn.clicked.connect(lambda: self.scan_requested.emit())
        btn_layout.addWidget(self._scan_btn)

        self._survey_btn = QPushButton("Begin Survey")
        self._survey_btn.clicked.connect(self._on_begin_survey)
        btn_layout.addWidget(self._survey_btn)

        self._end_survey_btn = QPushButton("End Survey")
        self._end_survey_btn.clicked.connect(self._on_end_survey)
        self._end_survey_btn.setEnabled(False)
        btn_layout.addWidget(self._end_survey_btn)

        self._export_btn = QPushButton("Export Session")
        self._export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(self._export_btn)

        self._wl_btn = QPushButton("Whitelist…")
        self._wl_btn.clicked.connect(self._on_whitelist)
        btn_layout.addWidget(self._wl_btn)

        layout.addLayout(btn_layout)

        #Scan interval 
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval (s):"))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 60)
        self._interval_spin.setValue(self._config.scan_interval_s)
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        interval_layout.addWidget(self._interval_spin)

        self._auto_cb = QCheckBox("Auto-scan")
        self._auto_cb.setChecked(True)
        self._auto_cb.toggled.connect(self._on_auto_toggled)
        interval_layout.addWidget(self._auto_cb)

        layout.addLayout(interval_layout)

        # Sample counter
        self._sample_lbl = QLabel("Samples: 0")
        layout.addWidget(self._sample_lbl)

        # Whitelist list
        layout.addWidget(QLabel("Whitelist:"))
        self._wl_list = QListWidget()
        self._wl_list.setMaximumHeight(120)
        layout.addWidget(self._wl_list)

        #Status
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color: {FG_MUTED};")
        layout.addWidget(self._status_lbl)

        # Auto-scan timer 
        self._auto_timer = QTimer()
        self._auto_timer.setInterval(self._config.scan_interval_s * 1000)
        self._auto_timer.timeout.connect(lambda: self.scan_requested.emit())

    def _apply_config(self):
        self._auto_timer.setInterval(self._config.scan_interval_s * 1000)
        self._interval_spin.setValue(self._config.scan_interval_s)
        self._refresh_whitelist()

    def _on_interval_changed(self, value: int):
        self._config.scan_interval_s = value
        self._auto_timer.setInterval(value * 1000)
        self._config.save()

    def _on_auto_toggled(self, checked: bool):
        if checked:
            self._auto_timer.start()
        else:
            self._auto_timer.stop()

    def update_from_scan(self, observations: list[APObservation]):
        self._observations = observations
        self._table.setRowCount(0)
        for obs in observations:
            row = self._table.rowCount()
            self._table.insertRow(row)

            status_dot = QTableWidgetItem("●")
            status_dot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, status_dot)

            ssid_item = QTableWidgetItem(obs.ssid if obs.ssid else "(hidden)")
            self._table.setItem(row, 1, ssid_item)

            bssid_item = QTableWidgetItem(obs.bssid)
            self._table.setItem(row, 2, bssid_item)

            ch_item = QTableWidgetItem(str(obs.channel))
            self._table.setItem(row, 3, ch_item)

            sec_item = QTableWidgetItem(obs.security)
            self._table.setItem(row, 4, sec_item)

            rssi_item = QTableWidgetItem(f"{obs.rssi:.1f}")
            self._table.setItem(row, 5, rssi_item)

        # Update target combo
        self._target_combo.clear()
        self._target_combo.addItem("(none)", "")
        for obs in observations:
            label = obs.ssid if obs.ssid else f"(hidden) {obs.bssid[:8]}"
            self._target_combo.addItem(label, obs.bssid)

        # Sort by RSSI descending
        self._table.sortByColumn(5, Qt.SortOrder.DescendingOrder)

    def update_alerts(self, alerts: list[RogueReport]):
        self._alerts = alerts
        # Update status dots
        for row in range(self._table.rowCount()):
            bssid_item = self._table.item(row, 2)
            if bssid_item is None:
                continue
            bssid = bssid_item.text()
            dot_item = self._table.item(row, 0)
            if dot_item is None:
                continue

            is_rogue = any(a.bssid == bssid and a.classification == "rogue" for a in alerts)
            is_suspicious = any(a.bssid == bssid and a.classification == "suspicious" for a in alerts)

            if is_rogue:
                dot_item.setBackground(RED)
                dot_item.setForeground(RED)
                dot_item.setText("●")
            elif is_suspicious:
                dot_item.setBackground(YELLOW)
                dot_item.setForeground(YELLOW)
                dot_item.setText("●")
            else:
                dot_item.setBackground(GREEN)
                dot_item.setForeground(GREEN)
                dot_item.setText("●")

        # Show alert banner for rogue alerts
        rogue_alerts = [a for a in alerts if a.classification == "rogue"]
        if rogue_alerts:
            self._alert_banner.setText(
                f"⚠ ROGUE DETECTED: {len(rogue_alerts)} network(s) flagged — "
                f"{rogue_alerts[0].ssid or '(hidden)'}"
            )
            self._alert_banner.show()
        else:
            self._alert_banner.hide()

    def get_target_bssid(self) -> str | None:
        return self._target_combo.currentData() or None

    def _on_begin_survey(self):
        target = self.get_target_bssid()
        if not target:
            self._status_lbl.setText("Select a target AP first")
            return
        self._survey_active = True
        self._sample_count = 0
        self._survey_btn.setEnabled(False)
        self._end_survey_btn.setEnabled(True)
        self._status_lbl.setText(f"SURVEY: {target} — 0 samples")
        self.survey_started.emit(target)

    def _on_end_survey(self):
        self._survey_active = False
        self._survey_btn.setEnabled(True)
        self._end_survey_btn.setEnabled(False)
        self._status_lbl.setText(f"Survey ended — {self._sample_count} samples recorded")
        self.survey_ended.emit()

    def _on_whitelist(self):
        entries = self._whitelist.list_entries()
        items = [
            f"{e.ssid or '(any)'} | {e.bssid or '(any)'} | {e.note or ''}"
            for e in entries
        ]

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Whitelist")
        dialog.setText(f"Whitelist entries ({len(entries)}):\n\n" + "\n".join(items) +
                       "\n\nUse the main window's Whitelist dialog to add/remove entries.")
        dialog.exec()

    def _on_export(self):
        if not self._observations:
            self._status_lbl.setText("No scan data to export")
            return
        dir_path = QFileDialog.getExistingDirectory(self, "Export Session To")
        if not dir_path:
            return
        store = SessionStore(dir_path)
        store.save_session(
            [], [], [],
            {"scanner_source": "simulated" if self._observations and self._observations[0].source == "simulated" else "real"},
        )
        self._status_lbl.setText(f"Session exported to {dir_path}")

    def _refresh_whitelist(self):
        self._wl_list.clear()
        for entry in self._whitelist.list_entries():
            label = f"{entry.ssid or '(any)'} | {entry.bssid or '(any)'}"
            if entry.note:
                label += f" — {entry.note}"
            item = QListWidgetItem(label)
            self._wl_list.addItem(item)

    def set_survey_sample_count(self, count: int):
        self._sample_count = count
        target = self.get_target_bssid() or "?"
        self._sample_lbl.setText(f"Samples: {count}")
        self._status_lbl.setText(f"SURVEY: {target} — {count} samples")

    def set_status(self, text: str):
        self._status_lbl.setText(text)

    def closeEvent(self, event):
        self._auto_timer.stop()
        super().closeEvent(event)