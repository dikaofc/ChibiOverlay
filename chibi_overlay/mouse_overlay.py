"""Mouse movement overlay visualization.

Shows cursor movement as:
  - A trailing dot that follows the cursor with smoothing
  - A direction arrow that rotates to point toward movement
  - Optional deadzone circle around the center
  - Click indicators (left/right mouse flash)

This mirrors input-overlay's mouse movement feature but implemented
natively in QPainter for the PySide6 overlay.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QPointF, QTimer
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QLinearGradient,
    QPainterPath, QRadialGradient,
)
from PySide6.QtWidgets import QWidget


@dataclass
class MouseOverlayConfig:
    """Configuration for the mouse overlay visualization."""
    enabled: bool = True
    # Movement visualization
    show_trail: bool = True
    trail_length: int = 20        # Number of trail points
    trail_dot_size: int = 6       # Size of trail dots
    trail_color: str = "#7fd1ff"  # Trail color
    # Direction arrow
    show_arrow: bool = True
    arrow_length: int = 40        # Length of direction indicator
    arrow_color: str = "#ff9ecb"
    # Deadzone
    show_deadzone: bool = True
    deadzone_radius: int = 50     # Pixels from center
    deadzone_color: str = "#ffffff20"
    # Click indicators
    show_clicks: bool = True
    left_click_color: str = "#4ade80"
    right_click_color: str = "#f87171"
    click_flash_duration: float = 0.3  # seconds
    # Sensitivity (how much cursor movement affects the visualization)
    sensitivity: float = 1.0
    # Position on screen
    x: int = 0
    y: int = 0
    size: int = 200               # Widget size


class MouseOverlay(QWidget):
    """Widget that visualizes mouse movement in real-time."""

    def __init__(self, config: Optional[MouseOverlayConfig] = None, parent=None):
        super().__init__(parent)
        self.cfg = config or MouseOverlayConfig()
        self.setFixedSize(self.cfg.size, self.cfg.size)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        # Internal state
        self._trail: deque[QPointF] = deque(maxlen=self.cfg.trail_length)
        self._mouse_pos = QPointF(0, 0)
        self._prev_mouse = QPointF(0, 0)
        self._velocity = QPointF(0, 0)
        self._angle = 0.0          # Direction angle in radians
        self._speed = 0.0          # Cursor speed (pixels/frame)

        # Click flash state
        self._left_flash = 0.0     # 0..1 decay
        self._right_flash = 0.0
        self._t = 0.0

        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60fps

    def set_config(self, config: MouseOverlayConfig):
        self.cfg = config
        self.setFixedSize(config.size, config.size)
        self._trail = deque(maxlen=config.trail_length)
        self.update()

    def set_mouse_global(self, x: int, y: int):
        """Called from the input thread via event system."""
        self._prev_mouse = self._mouse_pos
        self._mouse_pos = QPointF(x, y)

        # Calculate velocity and direction
        dx = x - self._prev_mouse.x()
        dy = y - self._prev_mouse.y()
        self._speed = math.hypot(dx, dy) * self.cfg.sensitivity
        if self._speed > 1.0:
            self._angle = math.atan2(dy, dx)
        self._velocity = QPointF(dx * self.cfg.sensitivity, dy * self.cfg.sensitivity)

        # Add to trail (mapped to widget center)
        cx = self.cfg.size / 2
        cy = self.cfg.size / 2
        # Clamp movement to deadzone visualization area
        max_r = self.cfg.size * 0.4
        tx = cx + self._velocity.x() * 0.3
        ty = cy + self._velocity.y() * 0.3
        # Keep within bounds
        dist = math.hypot(tx - cx, ty - cy)
        if dist > max_r:
            tx = cx + (tx - cx) / dist * max_r
            ty = cy + (ty - cy) / dist * max_r
        self._trail.append(QPointF(tx, ty))

        self.update()

    def flash_left_click(self):
        self._left_flash = 1.0

    def flash_right_click(self):
        self._right_flash = 1.0

    def _tick(self):
        dt = 0.016
        self._t += dt
        needs_update = False

        # Decay click flashes
        if self._left_flash > 0:
            self._left_flash = max(0, self._left_flash - dt / self.cfg.click_flash_duration)
            needs_update = True
        if self._right_flash > 0:
            self._right_flash = max(0, self._right_flash - dt / self.cfg.click_flash_duration)
            needs_update = True

        # Decay speed for arrow
        if self._speed > 0.5:
            self._speed *= 0.95
            needs_update = True

        if needs_update:
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.cfg.size, self.cfg.size
        cx, cy = w / 2, h / 2

        # ---- deadzone circle ----
        if self.cfg.show_deadzone and self.cfg.deadzone_radius > 0:
            r = self.cfg.deadzone_radius * self.cfg.sensitivity
            dz = QColor(self.cfg.deadzone_color)
            p.setPen(QPen(dz, 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)
            # Center dot
            p.setBrush(QBrush(QColor(255, 255, 255, 60)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), 3, 3)

        # ---- trail ----
        if self.cfg.show_trail and len(self._trail) > 1:
            trail_col = QColor(self.cfg.trail_color)
            n = len(self._trail)
            points = list(self._trail)
            for i in range(1, n):
                # Fade from old to new
                alpha = int(255 * (i / n) * 0.8)
                width = max(1, int(self.cfg.trail_dot_size * (i / n)))
                p.setPen(QPen(QColor(trail_col.red(), trail_col.green(),
                                     trail_col.blue(), alpha), width,
                              Qt.SolidLine, Qt.RoundCap))
                p.drawLine(points[i - 1], points[i])

            # Current position dot
            if n > 0:
                last = points[-1]
                p.setBrush(QBrush(trail_col))
                p.setPen(Qt.NoPen)
                p.drawEllipse(last, self.cfg.trail_dot_size, self.cfg.trail_dot_size)

        # ---- direction arrow ----
        if self.cfg.show_arrow and self._speed > 2.0:
            arrow_len = min(self.cfg.arrow_length, self._speed * 0.5)
            ax = cx + math.cos(self._angle) * arrow_len
            ay = cy + math.sin(self._angle) * arrow_len
            arrow_col = QColor(self.cfg.arrow_color)
            p.setPen(QPen(arrow_col, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            # Arrow shaft
            p.drawLine(QPointF(cx, cy), QPointF(ax, ay))
            # Arrowhead
            head_len = 8
            head_angle = 0.5
            for sign in (-1, 1):
                hx = ax - head_len * math.cos(self._angle + sign * head_angle)
                hy = ay - head_len * math.sin(self._angle + sign * head_angle)
                p.drawLine(QPointF(ax, ay), QPointF(hx, hy))

        # ---- click flashes ----
        if self.cfg.show_clicks:
            # Left click (green circle)
            if self._left_flash > 0:
                alpha = int(200 * self._left_flash)
                r = int(20 + (1 - self._left_flash) * 15)
                p.setPen(QPen(QColor(self.cfg.left_click_color), 2))
                p.setBrush(QBrush(QColor(QColor(self.cfg.left_click_color).red(),
                                         QColor(self.cfg.left_click_color).green(),
                                         QColor(self.cfg.left_click_color).blue(),
                                         alpha)))
                p.drawEllipse(QPointF(cx - 30, cy + 30), r, r)

            # Right click (red circle)
            if self._right_flash > 0:
                alpha = int(200 * self._right_flash)
                r = int(20 + (1 - self._right_flash) * 15)
                p.setPen(QPen(QColor(self.cfg.right_click_color), 2))
                p.setBrush(QBrush(QColor(QColor(self.cfg.right_click_color).red(),
                                         QColor(self.cfg.right_click_color).green(),
                                         QColor(self.cfg.right_click_color).blue(),
                                         alpha)))
                p.drawEllipse(QPointF(cx + 30, cy + 30), r, r)

        p.end()

    def set_position(self, x: int, y: int):
        """Position the overlay on screen."""
        self.cfg.x = x
        self.cfg.y = y
        super().move(x, y)
