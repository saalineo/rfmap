from collections.abc import Callable

from rfmap.ui.chrome.section import section
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class SurveyCapture(QFrame):
    """Starts, finishes, and reports the state of measurement capture."""

    def __init__(self, on_start: Callable, on_finish: Callable, parent=None):
        super().__init__(parent)
        self.setProperty("rfmapRole", "card")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addWidget(section("Capture"))
        actions = QHBoxLayout()
        self.start_button = QPushButton("Start survey")
        self.start_button.setProperty("rfmapRole", "primary")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(on_start)
        actions.addWidget(self.start_button)
        self.finish_button = QPushButton("Finish && export")
        self.finish_button.setEnabled(False)
        self.finish_button.clicked.connect(on_finish)
        actions.addWidget(self.finish_button)
        layout.addLayout(actions)

        self.point_label = QLabel("Data points: 0")
        layout.addWidget(self.point_label)
        self.rssi_label = QLabel("Signal: waiting for adapter")
        layout.addWidget(self.rssi_label)
        self.source_label = QLabel("Source: ---")
        self.source_label.setProperty("rfmapRole", "muted")
        layout.addWidget(self.source_label)
