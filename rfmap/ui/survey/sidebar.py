from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget

from rfmap.ui.assessment.advanced_tools import AdvancedSurveyTools
from rfmap.ui.survey.floor_plan_setup import FloorPlanSetup
from rfmap.ui.survey.network_selector import NetworkSelector
from rfmap.ui.survey.survey_capture import SurveyCapture


class SurveySidebar(QScrollArea):
    """Composes the small controls required for a site-survey workflow."""

    def __init__(
        self,
        cell_meters: float,
        interfaces: list[str],
        on_import_floorplan: Callable,
        on_scale_changed: Callable,
        on_adapter_changed: Callable,
        on_ap_changed: Callable,
        on_scan_requested: Callable,
        on_start_survey: Callable,
        on_finish_survey: Callable,
        on_demo: Callable,
        on_reset: Callable,
        on_advanced_toggled: Callable,
        parent=None,
    ):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedWidth(340)

        content = QWidget()
        self.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.status_label = QLabel("1. Import a floor plan, then choose an access point.")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("rfmapRole", "muted")
        layout.addWidget(self.status_label)

        self.floor_plan_setup = FloorPlanSetup(cell_meters, on_import_floorplan, on_scale_changed)
        layout.addWidget(self.floor_plan_setup)

        self.network_selector = NetworkSelector(
            interfaces, on_adapter_changed, on_ap_changed, on_scan_requested
        )
        layout.addWidget(self.network_selector)

        self.survey_capture = SurveyCapture(on_start_survey, on_finish_survey)
        layout.addWidget(self.survey_capture)

        tools_toggle = QToolButton()
        tools_toggle.setText("Map and assessment tools")
        tools_toggle.setCheckable(True)
        tools_toggle.setArrowType(Qt.ArrowType.RightArrow)
        tools_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        layout.addWidget(tools_toggle)
        self.advanced_tools = AdvancedSurveyTools(on_demo, on_reset, on_advanced_toggled)
        self.advanced_tools.hide()
        tools_toggle.toggled.connect(self.advanced_tools.setVisible)
        tools_toggle.toggled.connect(
            lambda checked: tools_toggle.setArrowType(
                Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
            )
        )
        layout.addWidget(self.advanced_tools)
        layout.addStretch()
