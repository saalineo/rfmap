import numpy as np
from vispy.scene import visuals

from rfmap.models import LocalizationFix
from rfmap.ui.canvas.constants import CEILING_Z, FLOOR_Z

ROGUE_COLOR = "#f7768e"
ROGUE_COLOR_LOW = (0.97, 0.47, 0.56, 0.3)
ROGUE_COLOR_HIGH = (0.97, 0.47, 0.56, 0.9)


class RogueOverlay:
    def __init__(self, view):
        self._view = view
        self._marker = visuals.Markers()
        self._marker.visible = False
        self._marker.parent = view.scene

        self._ellipse_lines = visuals.Line()
        self._ellipse_lines.visible = False
        self._ellipse_lines.parent = view.scene

        self._ellipse_fill = visuals.Mesh()
        self._ellipse_fill.visible = False
        self._ellipse_fill.parent = view.scene

        self._drop_line = visuals.Line()
        self._drop_line.visible = False
        self._drop_line.parent = view.scene

        self._label = visuals.Text(
            "",
            pos=(0, 0, CEILING_Z),
            color=ROGUE_COLOR,
            font_size=10,
            bold=True,
            parent=view.scene,
            anchor_x="center",
            anchor_y="bottom",
        )
        self._label.visible = False

        self._visible = True
        self._blink_timer = None
        self._blink_state = False
        self._fix = None

    def set_fix(self, fix: LocalizationFix | None):
        self._fix = fix
        if fix is None:
            self._marker.visible = False
            self._ellipse_lines.visible = False
            self._ellipse_fill.visible = False
            self._drop_line.visible = False
            self._label.visible = False
            return

        x, y = fix.x, fix.y
        z = CEILING_Z

        # Ceiling marker
        size = max(8, min(25, 25 * fix.confidence))
        self._marker.set_data(
            pos=np.array([[x, y, z]], dtype=np.float32),
            face_color=ROGUE_COLOR,
            edge_color="#0b0c0f",
            size=size,
            symbol="diamond",
        )
        self._marker.visible = True

        # Floor ellipse
        major = max(1.0, fix.ellipse_major)
        minor = max(1.0, fix.ellipse_minor)
        angle = fix.ellipse_angle
        n_pts = 36
        phi = np.linspace(0, 2 * np.pi, n_pts)
        ex = x + major * np.cos(phi) * np.cos(angle) - minor * np.sin(phi) * np.sin(angle)
        ey = y + major * np.cos(phi) * np.sin(angle) + minor * np.sin(phi) * np.cos(angle)
        ez = np.full(n_pts, FLOOR_Z, dtype=np.float32)

        ellipse_pos = np.column_stack([ex, ey, ez]).astype(np.float32)
        self._ellipse_lines.set_data(
            pos=ellipse_pos,
            color=ROGUE_COLOR_LOW,
            width=1.5,
            connect="loop",
        )
        self._ellipse_lines.visible = True

        # Ellipse fill
        fill_verts = np.column_stack([
            np.concatenate([[x], ex]),
            np.concatenate([[y], ey]),
            np.concatenate([[FLOOR_Z + 1], ez]),
        ]).astype(np.float32)
        n = len(fill_verts)
        faces = np.column_stack([
            np.zeros(n - 2, dtype=np.uint32),
            np.arange(1, n - 1, dtype=np.uint32),
            np.arange(2, n, dtype=np.uint32),
        ])
        fill_colors = np.zeros((n, 4), dtype=np.float32)
        fill_colors[:, :3] = [0.97, 0.47, 0.56]
        fill_colors[:, 3] = 0.15
        self._ellipse_fill.set_data(
            vertices=fill_verts,
            faces=faces,
            color=fill_colors,
        )
        self._ellipse_fill.visible = True

        # Drop line
        self._drop_line.set_data(
            pos=np.array(
                [[x, y, FLOOR_Z], [x, y, CEILING_Z]],
                dtype=np.float32,
            ),
            color=ROGUE_COLOR_LOW,
            width=1.0,
        )
        self._drop_line.visible = True

        # Label
        self._label.text = f"ROGUE {fix.bssid[:8]}"
        self._label.pos = (x, y, CEILING_Z + 3)
        self._label.visible = True

        # Blink for low confidence
        if fix.confidence < 0.5:
            self._start_blink()
        else:
            self._stop_blink()

    def set_visible(self, visible: bool):
        self._visible = visible
        self._marker.visible = visible and self._marker.visible
        self._ellipse_lines.visible = visible and self._ellipse_lines.visible
        self._ellipse_fill.visible = visible and self._ellipse_fill.visible
        self._drop_line.visible = visible and self._drop_line.visible
        self._label.visible = visible and self._label.visible

    def _start_blink(self):
        if self._blink_timer is not None:
            return
        self._blink_state = False
        from PyQt6.QtCore import QTimer
        self._blink_timer = QTimer()
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_timer.start()

    def _stop_blink(self):
        if self._blink_timer is not None:
            self._blink_timer.stop()
            self._blink_timer = None
        self._marker.color = ROGUE_COLOR_HIGH

    def _toggle_blink(self):
        if self._fix is None or self._fix.confidence >= 0.5:
            self._stop_blink()
            return
        self._blink_state = not self._blink_state
        if self._blink_state:
            self._marker.color = ROGUE_COLOR_HIGH
        else:
            self._marker.color = (0.97, 0.47, 0.56, 0.1)

    def cleanup(self):
        self._stop_blink()
        for node in [self._marker, self._ellipse_lines, self._ellipse_fill, self._drop_line, self._label]:
            node.parent = None
