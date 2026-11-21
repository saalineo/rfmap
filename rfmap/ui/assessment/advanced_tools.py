from collections.abc import Callable

from rfmap.ui.chrome.section import section
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QFrame, QPushButton, QToolButton, QVBoxLayout

from rfmap.ui.assessment.sentinel_panel import SentinelPanel


class AdvancedSurveyTools(QFrame):
    """Explicitly optional map-editing, demo, and AP-assessment controls."""

    def __init__(self, on_demo: Callable, on_reset: Callable, on_assessment_toggled: Callable, parent=None):
        super().__init__(parent)
        self.setProperty("rfmapRole", "card")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addWidget(section("Wall material"))
        self.material_combo = QComboBox()
        self.material_combo.addItems(["Drywall", "Brick", "Reinforced Concrete"])
        layout.addWidget(self.material_combo)
        demo_btn = QPushButton("Load demo data")
        demo_btn.clicked.connect(on_demo)
        layout.addWidget(demo_btn)
        reset_btn = QPushButton("Clear survey data")
        reset_btn.setProperty("rfmapRole", "ghost")
        reset_btn.clicked.connect(on_reset)
        layout.addWidget(reset_btn)

        self.assessment_toggle = QToolButton()
        self.assessment_toggle.setText("Advanced assessment")
        self.assessment_toggle.setCheckable(True)
        self.assessment_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.assessment_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.assessment_toggle.toggled.connect(on_assessment_toggled)
        layout.addWidget(self.assessment_toggle)
        self.assessment_panel = SentinelPanel()
        self.assessment_panel.hide()
        layout.addWidget(self.assessment_panel)
