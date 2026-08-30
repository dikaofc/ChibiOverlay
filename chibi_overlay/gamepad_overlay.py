"""Gamepad input overlay visualization.

Shows:
  - Face buttons (A/B/X/Y) with press glow
  - Bumpers (LB/RB) with press indicators
  - D-Pad with directional highlighting
  - Analog sticks as movable circles with deadzone
  - Triggers (LT/RT) as pressure bars

All drawn natively with QPainter — no external textures needed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Dict

from PySide6.QtCore import Qt, QPointF, QTimer, QRectF
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QRadialGradient, QPainterPath,
)
from PySide6.QtWidgets import QWidget


@dataclass
class GamepadConfig:
    """Configuration for the gamepad overlay."""
    enabled: bool = True
    x: int = 0
    y: int = 0
    size: int = 250
    opacity: float = 0.85
    # Colors
    bg_color: str = "#1a1d27"
    btn_color: str = "#2a2d3a"
    btn_active_color: str = "#7fd1ff"
    text_color: str = "#e2e4ea"
    # Face button colors
    a_color: str = "#4ade80"
    b_color: str = "#f87171"
    x_color: str = "#60a5fa"
    y_color: str = "#fbbf24"
    # Stick
    stick_color: str = "#ffffff"
    stick_active_color: str = "#7fd1ff"
    deadzone_radius: float = 0.15  # Normalized 0..1


class GamepadOverlay(QWidget):
    """Widget that visualizes gamepad input in real-time."""

    # Button states — True = pressed
    BUTTONS = [
        "gamepad_a", "gamepad_b", "gamepad_x", "gamepad_y",
        "gamepad_lb", "gamepad_rb", "gamepad_lt", "gamepad_rt",
        "gamepad_back", "gamepad_start",
        "gamepad_up", "gamepad_down", "gamepad_left", "gamepad_right",
        "gamepad_ls", "gamepad_rs",
    ]

    def __init__(self, config: Optional[GamepadConfig] = None, parent=None):
        super().__init__(parent)
        self.cfg = config or GamepadConfig()
        self.setFixedSize(self.cfg.size, self.cfg.size)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # State
        self._pressed: Dict[str, bool] = {b: False for b in self.BUTTONS}
        self._left_stick = QPointF(0, 0)   # Normalized -1..1
        self._right_stick = QPointF(0, 0)  # Normalized -1..1
        self._left_trigger = 0.0           # 0..1
        self._right_trigger = 0.0          # 0..1
        self._t = 0.0

        # Animation
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_button(self, name: str, pressed: bool):
        if name in self._pressed:
            self._pressed[name] = pressed
            self.update()

    def set_left_stick(self, x: float, y: float):
        """Set left analog stick position (normalized -1..1)."""
        self._left_stick = QPointF(max(-1, min(1, x)), max(-1, min(1, y)))
        self.update()

    def set_right_stick(self, x: float, y: float):
        """Set right analog stick position (normalized -1..1)."""
        self._right_stick = QPointF(max(-1, min(1, x)), max(-1, min(1, y)))
        self.update()

    def set_triggers(self, left: float, right: float):
        """Set trigger pressure (normalized 0..1)."""
        self._left_trigger = max(0, min(1, left))
        self._right_trigger = max(0, min(1, right))
        self.update()

    def _tick(self):
        self._t += 0.016
        # Slowly center sticks when no input
        decay = 0.92
        self._left_stick = QPointF(self._left_stick.x() * decay, self._left_stick.y() * decay)
        self._right_stick = QPointF(self._right_stick.x() * decay, self._right_stick.y() * decay)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.cfg.size
        cx, cy = s / 2, s / 2

        # ---- body outline ----
        body_r = s * 0.42
        body = QColor(self.cfg.bg_color)
        body.setAlpha(180)
        p.setBrush(QBrush(body))
        p.setPen(QPen(QColor("#333640"), 2))
        p.drawRoundedRect(QRectF(s * 0.08, s * 0.15, s * 0.84, s * 0.7), 30, 30)

        # ---- left analog stick ----
        self._draw_stick(p, s * 0.28, s * 0.5, self._left_stick, "LS")

        # ---- right analog stick ----
        self._draw_stick(p, s * 0.72, s * 0.5, self._right_stick, "RS")

        # ---- d-pad ----
        self._draw_dpad(p, s * 0.22, s * 0.38)

        # ---- face buttons ----
        self._draw_face_buttons(p, s * 0.78, s * 0.38)

        # ---- bumpers ----
        self._draw_bumper(p, s * 0.2, s * 0.18, "LB", "gamepad_lb")
        self._draw_bumper(p, s * 0.8, s * 0.18, "RB", "gamepad_rb")

        # ---- triggers ----
        self._draw_trigger(p, s * 0.1, s * 0.22, self._left_trigger, "LT", True)
        self._draw_trigger(p, s * 0.9, s * 0.22, self._right_trigger, "RT", False)

        # ---- center buttons ----
        self._draw_center_button(p, s * 0.43, s * 0.48, "≡", "gamepad_back")
        self._draw_center_button(p, s * 0.57, s * 0.48, "▶", "gamepad_start")

        p.end()

    def _draw_stick(self, p: QPainter, cx: float, cy: float, pos: QPointF, label: str):
        s = self.cfg.size
        stick_r = s * 0.08
        ring_r = s * 0.12

        # Ring
        p.setPen(QPen(QColor("#3a3d4a"), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        # Stick position
        sx = cx + pos.x() * ring_r * 0.8
        sy = cy + pos.y() * ring_r * 0.8
        active = abs(pos.x()) > 0.05 or abs(pos.y()) > 0.05
        col = QColor(self.cfg.stick_active_color if active else self.cfg.stick_color)
        p.setBrush(QBrush(col))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(sx, sy), stick_r, stick_r)

        # Label
        p.setPen(QPen(QColor("#666")))
        p.setFont(QFont("Segoe UI", max(7, int(s * 0.035)), QFont.Normal))
        p.drawText(QRectF(cx - stick_r, cy + ring_r + 2, stick_r * 2, 16), Qt.AlignCenter, label)

    def _draw_dpad(self, p: QPainter, cx: float, cy: float):
        s = self.cfg.size
        btn_r = s * 0.035
        gap = s * 0.05

        directions = {
            "gamepad_up": (0, -gap),
            "gamepad_down": (0, gap),
            "gamepad_left": (-gap, 0),
            "gamepad_right": (gap, 0),
        }
        for tok, (dx, dy) in directions.items():
            bx, by = cx + dx, cy + dy
            pressed = self._pressed.get(tok, False)
            col = QColor(self.cfg.btn_active_color if pressed else self.cfg.btn_color)
            p.setBrush(QBrush(col))
            p.setPen(QPen(QColor("#555"), 1))
            p.drawRoundedRect(QRectF(bx - btn_r, by - btn_r, btn_r * 2, btn_r * 2), 3, 3)

    def _draw_face_buttons(self, p: QPainter, cx: float, cy: float):
        s = self.cfg.size
        btn_r = s * 0.04
        gap = s * 0.065
        colors = {
            "gamepad_a": (self.cfg.a_color, "A", (0, gap)),
            "gamepad_b": (self.cfg.b_color, "B", (gap, 0)),
            "gamepad_x": (self.cfg.x_color, "X", (-gap, 0)),
            "gamepad_y": (self.cfg.y_color, "Y", (0, -gap)),
        }
        for tok, (col_str, lbl, (dx, dy)) in colors.items():
            bx, by = cx + dx, cy + dy
            pressed = self._pressed.get(tok, False)
            if pressed:
                # Glow
                glow = QColor(col_str)
                glow.setAlpha(60)
                p.setBrush(QBrush(glow))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(bx, by), btn_r * 1.8, btn_r * 1.8)
            col = QColor(col_str)
            if not pressed:
                col.setAlpha(120)
            p.setBrush(QBrush(col))
            p.setPen(QPen(QColor(col_str), 1.5))
            p.drawEllipse(QPointF(bx, by), btn_r, btn_r)
            # Label
            p.setPen(QPen(QColor("#fff")))
            p.setFont(QFont("Segoe UI", max(8, int(s * 0.04)), QFont.Bold))
            p.drawText(QRectF(bx - btn_r, by - btn_r, btn_r * 2, btn_r * 2), Qt.AlignCenter, lbl)

    def _draw_bumper(self, p: QPainter, cx: float, cy: float, label: str, token: str):
        s = self.cfg.size
        w, h = s * 0.16, s * 0.05
        pressed = self._pressed.get(token, False)
        col = QColor(self.cfg.btn_active_color if pressed else self.cfg.btn_color)
        p.setBrush(QBrush(col))
        p.setPen(QPen(QColor("#555"), 1))
        p.drawRoundedRect(QRectF(cx - w / 2, cy - h / 2, w, h), 4, 4)
        p.setPen(QPen(QColor("#aaa") if not pressed else QColor("#fff")))
        p.setFont(QFont("Segoe UI", max(7, int(s * 0.035)), QFont.Bold))
        p.drawText(QRectF(cx - w / 2, cy - h / 2, w, h), Qt.AlignCenter, label)

    def _draw_trigger(self, p: QPainter, cx: float, cy: float, value: float, label: str, is_left: bool):
        s = self.cfg.size
        w, h = s * 0.04, s * 0.18
        # Background
        p.setBrush(QBrush(QColor("#1a1d27")))
        p.setPen(QPen(QColor("#333"), 1))
        p.drawRoundedRect(QRectF(cx - w / 2, cy - h / 2, w, h), 3, 3)
        # Fill
        fill_h = h * value
        if is_left:
            fy = cy + h / 2 - fill_h
        else:
            fy = cy + h / 2 - fill_h
        fill_col = QColor(self.cfg.btn_active_color)
        fill_col.setAlpha(int(180 * value))
        p.setBrush(QBrush(fill_col))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(cx - w / 2 + 1, fy, w - 2, fill_h), 2, 2)
        # Label
        p.setPen(QPen(QColor("#888")))
        p.setFont(QFont("Segoe UI", max(6, int(s * 0.03)), QFont.Normal))
        p.drawText(QRectF(cx - w, cy + h / 2 + 2, w * 2, 14), Qt.AlignCenter, label)

    def _draw_center_button(self, p: QPainter, cx: float, cy: float, glyph: str, token: str):
        s = self.cfg.size
        r = s * 0.03
        pressed = self._pressed.get(token, False)
        col = QColor(self.cfg.btn_active_color if pressed else self.cfg.btn_color)
        p.setBrush(QBrush(col))
        p.setPen(QPen(QColor("#555"), 1))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(QPen(QColor("#aaa") if not pressed else QColor("#fff")))
        p.setFont(QFont("Segoe UI", max(6, int(s * 0.028)), QFont.Normal))
        p.drawText(QRectF(cx - r, cy - r, r * 2, r * 2), Qt.AlignCenter, glyph)
