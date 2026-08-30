"""App icon generator — renders a cat-face icon at multiple sizes.

Used for:
  - Taskbar icon (16–48 px)
  - Title bar icon (18 px)
  - System tray icon (16–64 px)
  - Window icon (set on all top-level windows)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPixmap, QIcon, QPainterPath,
    QRadialGradient,
)


def _draw_cat(p: QPainter, size: int):
    """Draw the cat face at the given pixel size onto an active painter."""
    s = size
    cx, cy = s / 2, s / 2 + s * 0.04  # slight nudge down for ears
    p.setRenderHint(QPainter.Antialiasing)

    # ---- ears ----
    ear_color = QColor("#d4a056")
    ear_inner = QColor("#f5c88a")
    for sign in (-1, 1):
        ex = cx + sign * s * 0.26
        ey = cy - s * 0.22
        # outer ear triangle
        path = QPainterPath()
        path.moveTo(ex - s * 0.14, ey + s * 0.12)
        path.lineTo(ex, ey - s * 0.18)
        path.lineTo(ex + s * 0.14, ey + s * 0.12)
        path.closeSubpath()
        p.setBrush(QBrush(ear_color))
        p.setPen(Qt.NoPen)
        p.drawPath(path)
        # inner ear
        ip = QPainterPath()
        ip.moveTo(ex - s * 0.07, ey + s * 0.06)
        ip.lineTo(ex, ey - s * 0.08)
        ip.lineTo(ex + s * 0.07, ey + s * 0.06)
        ip.closeSubpath()
        p.setBrush(QBrush(ear_inner))
        p.drawPath(ip)

    # ---- head ----
    head_r = s * 0.32
    grad = QRadialGradient(cx - s * 0.04, cy - s * 0.04, head_r)
    grad.setColorAt(0, QColor("#f5d89a"))
    grad.setColorAt(1, QColor("#d4a056"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(cx, cy), head_r, head_r * 0.95)

    # ---- eyes ----
    eye_y = cy - s * 0.02
    for sign in (-1, 1):
        ex = cx + sign * s * 0.11
        # white
        p.setBrush(QBrush(QColor("#ffffff")))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(ex, eye_y), s * 0.065, s * 0.075)
        # pupil
        p.setBrush(QBrush(QColor("#1a1a2e")))
        p.drawEllipse(QPointF(ex + sign * s * 0.01, eye_y + s * 0.005), s * 0.035, s * 0.04)
        # glint
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(ex - s * 0.015, eye_y - s * 0.02), s * 0.015, s * 0.015)

    # ---- nose ----
    p.setBrush(QBrush(QColor("#ff8fa3")))
    p.setPen(Qt.NoPen)
    ny = cy + s * 0.08
    nose_path = QPainterPath()
    nose_path.moveTo(cx, ny - s * 0.015)
    nose_path.lineTo(cx - s * 0.025, ny + s * 0.02)
    nose_path.lineTo(cx + s * 0.025, ny + s * 0.02)
    nose_path.closeSubpath()
    p.drawPath(nose_path)

    # ---- mouth ----
    p.setPen(QPen(QColor("#8a6a42"), max(1, s * 0.015), Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    mouth_y = ny + s * 0.03
    # left curve
    p.drawArc(QRectF(cx - s * 0.06, mouth_y, s * 0.06, s * 0.04), 200 * 16, 140 * 16)
    # right curve
    p.drawArc(QRectF(cx, mouth_y, s * 0.06, s * 0.04), 200 * 16, 140 * 16)

    # ---- whiskers ----
    p.setPen(QPen(QColor("#b8976a"), max(1, s * 0.008), Qt.SolidLine, Qt.RoundCap))
    wy = cy + s * 0.06
    for sign in (-1, 1):
        wx = cx + sign * s * 0.14
        for k in (-1, 0, 1):
            p.drawLine(
                QPoint(int(wx), int(wy + k * s * 0.025)),
                QPoint(int(wx + sign * s * 0.16), int(wy + k * s * 0.04)),
            )


def generate_icon() -> QIcon:
    """Create a multi-size QIcon for the application."""
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(sz, sz)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        _draw_cat(p, sz)
        p.end()
        icon.addPixmap(pm)
    return icon


def generate_tray_pixmap(size: int = 64) -> QPixmap:
    """Create a single-size pixmap for the system tray."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    _draw_cat(p, size)
    p.end()
    return pm
