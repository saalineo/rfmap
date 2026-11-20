# `ui/` — desktop interface and visualization

| File | Responsibility |
|---|---|
| `main_window.py` | Survey state, user controls, worker wiring, and main workflow |
| `canvas.py` | VisPy 3D heat surface, floor-plan image, walls, markers, waterfall |
| `scanner_panel.py` | AP table, target selection, assessment and export controls |
| `rogue_overlay.py` | Localization uncertainty overlay |
| `theme.py` | Application-wide semantic colours and Qt stylesheet |

Use Qt layouts and standard controls for new interaction. Add shared styling to `theme.py`; avoid per-widget stylesheet fragments. Any icon-only or custom control needs an accessible name and keyboard-reachable behavior.

The UI must distinguish live, held, unavailable, and demo data in text, not only by colour. `MainWindow` owns survey data and receives worker output through signals.
