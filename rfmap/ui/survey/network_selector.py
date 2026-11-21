from collections.abc import Callable

from rfmap.ui.chrome.section import section
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class NetworkSelector(QFrame):
    """Chooses the adapter and access point that supply survey readings."""

    def __init__(
        self,
        interfaces: list[str],
        on_adapter_changed: Callable,
        on_ap_changed: Callable,
        on_scan_requested: Callable,
        parent=None,
    ):
        super().__init__(parent)
        self.setProperty("rfmapRole", "card")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addWidget(section("Survey network"))

        adapter_layout = QHBoxLayout()
        adapter_layout.addWidget(QLabel("Adapter"))
        self.adapter_combo = QComboBox()
        self.adapter_combo.setAccessibleName("Wi-Fi adapter")
        self.adapter_combo.addItem("Auto", None)
        for interface in interfaces:
            self.adapter_combo.addItem(interface, interface)
        self.adapter_combo.currentIndexChanged.connect(on_adapter_changed)
        adapter_layout.addWidget(self.adapter_combo)
        layout.addLayout(adapter_layout)

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Access point"))
        self.ap_combo = QComboBox()
        self.ap_combo.addItem("Choose an access point…", None)
        self.ap_combo.setAccessibleName("Access point used for survey measurements")
        self.ap_combo.currentIndexChanged.connect(on_ap_changed)
        target_layout.addWidget(self.ap_combo)
        layout.addLayout(target_layout)

        scan_btn = QPushButton("Find access points")
        scan_btn.clicked.connect(on_scan_requested)
        layout.addWidget(scan_btn)
