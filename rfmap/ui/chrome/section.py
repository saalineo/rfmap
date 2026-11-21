"""Small muted label that titles a sidebar card."""
from PyQt6.QtWidgets import QLabel


def section(text):
    """Small muted label that titles a sidebar card."""
    label = QLabel(text.upper())
    label.setProperty("rfmapRole", "section")
    return label
