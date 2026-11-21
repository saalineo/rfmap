from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from rfmap.ui.theme.tokens import ACCENT


class SurveyHeader(QFrame):
    """Persistent identity and context for the survey workspace."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("rfmapRole", "header")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {ACCENT}; font-size: 10px;")
        dot.setAccessibleName("RFMap")
        layout.addWidget(dot)
        title = QLabel("RFMap")
        title.setProperty("rfmapRole", "title")
        layout.addWidget(title)
        subtitle = QLabel("Wi-Fi coverage survey")
        subtitle.setProperty("rfmapRole", "muted")
        layout.addWidget(subtitle)
        layout.addStretch()
