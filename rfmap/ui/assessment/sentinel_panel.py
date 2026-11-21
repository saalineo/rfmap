from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QComboBox,
    QLabel, QSpinBox, QCheckBox, QFrame, QListWidget,
    QListWidgetItem, QInputDialog, QMessageBox, QSplitter,
    QFileDialog,
)

from rfmap.sentinel.config import SentinelConfig
from rfmap.models import APObservation, RogueReport, SentryLogEntry
from rfmap.sentinel.allowlist import WhitelistStore
from rfmap.sentinel.engine import SentryEngine, calculate_trust_score
from rfmap.sentinel.deauth import DeauthDetector
from rfmap.ui.theme.tokens import BG_DARK, BG_SURFACE, BG_BORDER, FG, FG_MUTED, RED, YELLOW, GREEN


STATUS_GREEN = "#9ece6a"
STATUS_AMBER = "#e0af68"
STATUS_RED = "#f7768e"


class SentinelPanel(QWidget):
    scan_requested = pyqtSignal()
    survey_started = pyqtSignal(str)
    survey_ended = pyqtSignal()
    whitelist_changed = pyqtSignal()
    sentry_alert = pyqtSignal(object)
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = SentinelConfig.load()
        self._whitelist = WhitelistStore(self._config.whitelist_path)
        self._observations: list[APObservation] = []
        self._alerts: list[RogueReport] = []
        self._reports_dict: dict[str, RogueReport] = {}
        self._target_bssid: str | None = None
        self._survey_active = False
        self._sample_count = 0

        self._sentry_engine = SentryEngine(self._whitelist, alert_callback=self._on_sentry_log_entry)
        self._deauth_detector = DeauthDetector()
        self._simulated_deauth_active = False
        self._sentry_active = False

        self._build_ui()
        self._apply_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Trust Score Banner & Sentry Control Frame
        trust_frame = QFrame()
        trust_frame.setStyleSheet(
            f"background-color: {BG_SURFACE}; border: 1px solid {BG_BORDER}; border-radius: 6px; padding: 6px;"
        )
        trust_l = QVBoxLayout(trust_frame)
        trust_l.setContentsMargins(4, 4, 4, 4)
        trust_l.setSpacing(4)

        header_l = QHBoxLayout()
        self._trust_score_badge = QLabel("🛡 Trust Score: 100 / 100")
        self._trust_score_badge.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {STATUS_GREEN};"
        )
        header_l.addWidget(self._trust_score_badge)

        self._sentry_toggle = QPushButton("🛡 SENTRY: OFF")
        self._sentry_toggle.setCheckable(True)
        self._sentry_toggle.setStyleSheet(
            f"background-color: {BG_DARK}; color: {FG}; border: 1px solid {BG_BORDER}; font-weight: bold; padding: 4px 8px;"
        )
        self._sentry_toggle.toggled.connect(self._on_sentry_toggled)
        header_l.addWidget(self._sentry_toggle)

        trust_l.addLayout(header_l)

        self._trust_details_lbl = QLabel("Environment Status: Secure")
        self._trust_details_lbl.setStyleSheet(f"color: {FG_MUTED}; font-size: 11px;")
        trust_l.addWidget(self._trust_details_lbl)

        deauth_notice = QLabel(
            "Deauth monitoring is unavailable: RFMap does not capture monitor-mode frames."
        )
        deauth_notice.setWordWrap(True)
        deauth_notice.setToolTip(
            "Use a dedicated monitor-mode capture tool for deauthentication-frame analysis."
        )
        trust_l.addWidget(deauth_notice)
        layout.addWidget(trust_frame)

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
        self._export_btn.clicked.connect(self.export_requested.emit)
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
        self._wl_list.setMaximumHeight(80)
        layout.addWidget(self._wl_list)

        # Sentry Event Audit Log
        layout.addWidget(QLabel("Sentry Event Log:"))
        self._sentry_log_list = QListWidget()
        self._sentry_log_list.setMaximumHeight(100)
        layout.addWidget(self._sentry_log_list)

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
            rssi_item.setData(Qt.ItemDataRole.EditRole, obs.rssi)
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
        self._reports_dict = {a.bssid: a for a in alerts}
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
                dot_item.setBackground(QColor(RED))
                dot_item.setForeground(QColor(RED))
                dot_item.setText("●")
            elif is_suspicious:
                dot_item.setBackground(QColor(YELLOW))
                dot_item.setForeground(QColor(YELLOW))
                dot_item.setText("●")
            else:
                dot_item.setBackground(QColor(GREEN))
                dot_item.setForeground(QColor(GREEN))
                dot_item.setText("●")

        # Process Sentry Engine scans & recalculate trust score
        deauth_active = self._deauth_detector.poll_deauth_burst() or self._simulated_deauth_active
        if self._sentry_active:
            new_events = self._sentry_engine.process_scan(self._observations, self._reports_dict, deauth_burst=deauth_active)

        score, breakdown = calculate_trust_score(self._observations, self._reports_dict, deauth_burst_active=deauth_active)
        self._update_trust_score_ui(score, breakdown)

        # Show alert banner for rogue alerts
        rogue_alerts = [a for a in alerts if a.classification == "rogue"]
        if rogue_alerts or deauth_active:
            banner_msg = "⚠ SECURITY ALERT: "
            if deauth_active:
                banner_msg += "Deauth burst detected! "
            if rogue_alerts:
                banner_msg += f"{len(rogue_alerts)} Rogue AP(s) flagged ({rogue_alerts[0].ssid or '(hidden)'})"
            self._alert_banner.setText(banner_msg)
            self._alert_banner.show()
        else:
            self._alert_banner.hide()

    def _update_trust_score_ui(self, score: int, breakdown: list[str]):
        if score >= 80:
            color = STATUS_GREEN
        elif score >= 50:
            color = STATUS_AMBER
        else:
            color = STATUS_RED

        self._trust_score_badge.setText(f"🛡 Trust Score: {score} / 100")
        self._trust_score_badge.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")

        if breakdown:
            self._trust_details_lbl.setText("Issues: " + " | ".join(breakdown[:2]))
            self._trust_details_lbl.setToolTip("\n".join(breakdown))
        else:
            self._trust_details_lbl.setText("Environment Status: Secure (No threats detected)")
            self._trust_details_lbl.setToolTip("All APs trusted and encrypted")

    def _on_sentry_toggled(self, checked: bool):
        self._sentry_active = checked
        if checked:
            self._sentry_toggle.setText("🛡 SENTRY: ON")
            self._sentry_toggle.setStyleSheet(
                f"background-color: {RED}; color: {BG_DARK}; border: 1px solid {RED}; font-weight: bold; padding: 4px 8px;"
            )
            self._status_lbl.setText("Continuous Sentry Mode ACTIVE — Scanning every few seconds...")
        else:
            self._sentry_toggle.setText("🛡 SENTRY: OFF")
            self._sentry_toggle.setStyleSheet(
                f"background-color: {BG_DARK}; color: {FG}; border: 1px solid {BG_BORDER}; font-weight: bold; padding: 4px 8px;"
            )
            self._status_lbl.setText("Sentry Mode deactivated")

    def _on_deauth_toggled(self, checked: bool):
        if checked:
            self._deauth_detector.start_monitoring()
            self._status_lbl.setText("Monitor Mode Deauth Detection STARTED")
        else:
            self._deauth_detector.stop_monitoring()
            self._status_lbl.setText("Monitor Mode Deauth Detection STOPPED")

    def _on_sim_deauth(self):
        self._simulated_deauth_active = True
        self._deauth_detector.check_simulated(trigger=True)
        QMessageBox.warning(self, "Deauth Burst Simulated", "A 802.11 Deauthentication Packet Burst attack has been simulated!")
        QTimer.singleShot(5000, self._reset_sim_deauth)
        self.update_alerts(self._alerts)

    def _reset_sim_deauth(self):
        self._simulated_deauth_active = False
        self.update_alerts(self._alerts)

    def _on_sentry_log_entry(self, entry: SentryLogEntry):
        time_str = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M:%S")
        item_text = f"[{time_str}] [{entry.severity}] {entry.event_type}: {entry.details}"
        item = QListWidgetItem(item_text)
        if entry.severity == "HIGH":
            item.setForeground(QColor(RED))
        elif entry.severity == "MEDIUM":
            item.setForeground(QColor(YELLOW))
        self._sentry_log_list.insertItem(0, item)

        # Trigger System Audio/Visual Alarm
        try:
            from PyQt6.QtWidgets import QApplication
            QApplication.beep()
        except Exception:
            pass

    def get_target_bssid(self) -> str | None:
        return self._target_combo.currentData() or None

    def set_target_bssid(self, bssid: str | None):
        """Keep the scanner survey target aligned with the primary survey control."""
        index = self._target_combo.findData(bssid)
        if index >= 0:
            self._target_combo.setCurrentIndex(index)

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
        dialog.setText(
            f"Whitelist entries ({len(entries)}):\n\n" + "\n".join(items) +
            f"\n\nEdit {self._config.whitelist_path} to add or remove entries, then restart RFMap."
        )
        dialog.exec()

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
