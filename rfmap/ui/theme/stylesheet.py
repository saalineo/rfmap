"""The single Qt stylesheet. Per-widget styling is selected via the `rfmapRole` property."""
from rfmap.ui.theme.tokens import (
    ACCENT,
    ACCENT_HOVER,
    BG,
    BG_BORDER,
    BG_DARK,
    BG_HOVER,
    BG_SURFACE,
    FG,
    FG_DIM,
    FG_MUTED,
    FONT,
    RED,
    YELLOW,
)

QT_STYLESHEET = f"""
QMainWindow, QMenuBar {{ background-color: {BG_DARK}; }}
QWidget {{
    color: {FG};
    font-family: {FONT};
    font-size: 12px;
    selection-background-color: {ACCENT};
    selection-color: {BG_DARK};
}}
QToolTip {{
    background-color: {BG_SURFACE}; color: {FG};
    border: 1px solid {BG_BORDER}; padding: 4px 8px;
}}

/* ── Typography ───────────────────────── */
QLabel {{ background: transparent; padding: 0; }}
QLabel[rfmapRole="title"] {{ font-size: 15px; font-weight: 600; }}
QLabel[rfmapRole="section"] {{ font-size: 11px; font-weight: 600; color: {FG_MUTED}; padding-bottom: 2px; }}
QLabel[rfmapRole="muted"] {{ color: {FG_MUTED}; }}
QLabel[rfmapRole="demoWarning"] {{
    background-color: {YELLOW}; color: {BG_DARK};
    padding: 8px 12px; font-weight: 600; border-radius: 6px;
}}

/* ── Surfaces ─────────────────────────── */
QFrame {{ background: transparent; border: none; }}
QFrame[rfmapRole="card"] {{
    background-color: {BG_SURFACE};
    border: 1px solid {BG_BORDER};
    border-radius: 8px;
}}
QFrame[rfmapRole="header"] {{
    background-color: {BG};
    border-bottom: 1px solid {BG_BORDER};
}}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ── Buttons ──────────────────────────── */
QPushButton {{
    background-color: {BG_HOVER};
    border: 1px solid {BG_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
}}
QPushButton:hover {{ background-color: #262a32; border-color: #353a44; }}
QPushButton:pressed {{ background-color: {BG_SURFACE}; }}
QPushButton:disabled {{ color: {FG_DIM}; background-color: {BG}; border-color: {BG_BORDER}; }}
QPushButton:checked {{ background-color: {ACCENT}; border-color: {ACCENT}; color: {BG_DARK}; }}
QPushButton[rfmapRole="primary"] {{
    background-color: {ACCENT}; border-color: {ACCENT}; color: {BG_DARK}; font-weight: 600;
}}
QPushButton[rfmapRole="primary"]:hover {{ background-color: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton[rfmapRole="primary"]:pressed {{ background-color: {ACCENT}; }}
QPushButton[rfmapRole="primary"]:disabled {{ background-color: {BG_HOVER}; border-color: {BG_BORDER}; color: {FG_DIM}; }}
QPushButton[rfmapRole="ghost"] {{ background: transparent; border-color: transparent; color: {FG_MUTED}; }}
QPushButton[rfmapRole="ghost"]:hover {{ background-color: {BG_HOVER}; color: {RED}; }}
QPushButton:focus, QToolButton:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QToolButton {{
    background: transparent; border: 1px solid transparent; border-radius: 6px;
    padding: 6px 8px; font-weight: 600; color: {FG_MUTED}; text-align: left;
}}
QToolButton:hover {{ background-color: {BG_HOVER}; color: {FG}; }}
QToolButton:checked {{ color: {FG}; }}

/* ── Inputs ───────────────────────────── */
QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {BG_DARK};
    border: 1px solid {BG_BORDER};
    border-radius: 6px;
    padding: 5px 8px;
}}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: #353a44; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_SURFACE}; border: 1px solid {BG_BORDER};
    selection-background-color: {BG_HOVER}; selection-color: {FG};
    outline: none; padding: 4px;
}}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px; border: 1px solid #353a44; border-radius: 4px; background: {BG_DARK};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background-color: {ACCENT}; border-color: {ACCENT}; }}

/* ── Lists / tables ───────────────────── */
QTableWidget, QListWidget {{
    background-color: {BG_DARK};
    border: 1px solid {BG_BORDER};
    border-radius: 6px;
    gridline-color: transparent;
    alternate-background-color: {BG};
    outline: none;
}}
QTableWidget::item, QListWidget::item {{ padding: 4px 8px; border: none; }}
QTableWidget::item:hover, QListWidget::item:hover {{ background-color: {BG_HOVER}; }}
QTableWidget::item:selected, QListWidget::item:selected {{ background-color: #262a4d; color: {FG}; }}
QHeaderView::section {{
    background-color: {BG_DARK}; color: {FG_MUTED};
    padding: 6px 8px; border: none; border-bottom: 1px solid {BG_BORDER}; font-weight: 600;
}}
QTableCornerButton::section {{ background: {BG_DARK}; border: none; }}

/* ── Scrollbars: thin, no arrows ──────── */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2b2f38; border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:horizontal {{ background: #2b2f38; border-radius: 3px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: #434956; }}
QScrollBar::handle:pressed {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; background: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* ── Status bar ───────────────────────── */
QStatusBar {{
    background-color: {BG}; color: {FG_MUTED};
    border-top: 1px solid {BG_BORDER}; font-size: 11px; padding: 2px 8px;
}}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: {BG_BORDER}; }}
"""
