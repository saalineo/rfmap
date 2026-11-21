"""Design tokens + one stylesheet. Graphite neutrals, a single indigo accent, hairline borders.

Names are kept (BG_DARK, BLUE, ...) because other modules import them; BLUE is the accent.
"""
BG_DARK = "#0b0c0f"      # window + map canvas (deepest layer)
BG = "#111317"           # sidebar / chrome
BG_SURFACE = "#16181d"   # cards, inputs
BG_BORDER = "#23262d"    # hairlines
BG_HOVER = "#1d2026"
FG = "#e6e8ec"           # 14:1 on BG
FG_MUTED = "#8b909a"     # 5.4:1 on BG
FG_DIM = "#5b606b"       # disabled only

ACCENT = BLUE = "#7c83ff"
ACCENT_HOVER = "#939aff"
CYAN = "#6cc4e0"
PURPLE = "#b79cf5"
GREEN = "#5fd38d"
YELLOW = "#e5b567"
ORANGE = "#f0925c"
RED = PINK = "#f06a6a"

FONT = '"Inter", "SF Pro Text", "Segoe UI", "Noto Sans", sans-serif'
