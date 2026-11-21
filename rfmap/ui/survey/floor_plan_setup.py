from collections.abc import Callable

from rfmap.ui.chrome.section import section
from PyQt6.QtWidgets import QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class FloorPlanSetup(QFrame):
    """Imports and calibrates the floor plan used by a survey."""

    def __init__(self, cell_meters: float, on_import: Callable, on_scale_changed: Callable, parent=None):
        super().__init__(parent)
        self.setProperty("rfmapRole", "card")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addWidget(section("Floor plan"))
        import_btn = QPushButton("Import Floor Plan…")
        import_btn.clicked.connect(on_import)
        layout.addWidget(import_btn)
        self.file_label = QLabel("Floor plan: none")
        self.file_label.setWordWrap(True)
        self.file_label.setProperty("rfmapRole", "muted")
        layout.addWidget(self.file_label)

        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale:"))
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 100.0)
        self.scale_spin.setDecimals(2)
        self.scale_spin.setSuffix(" m/grid")
        self.scale_spin.setValue(cell_meters)
        self.scale_spin.setAccessibleName("Floor plan scale in metres per grid cell")
        self.scale_spin.valueChanged.connect(on_scale_changed)
        scale_layout.addWidget(self.scale_spin)
        layout.addLayout(scale_layout)

        self.map_size_label = QLabel()
        self.map_size_label.setProperty("rfmapRole", "muted")
        layout.addWidget(self.map_size_label)
