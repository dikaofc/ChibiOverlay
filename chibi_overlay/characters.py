"""Distinct chibi characters, not just color themes.

Each character is a dict: a color palette plus a draw(p, ctx) routine that
paints its own body, tail, ears, head and face. The shared parts (arms with
IK, paw, virtual mouse, emotion effects) are drawn by ChibiWidget.

`ctx` attributes used by draw routines:
  p            QPainter
  s            min dimension
  cx, cy       widget center
  hx, hy       head center (follows mouse)
  by           body center y
  breathe      idle breathing offset
  scale        pop scale
  blink        blink amount
  eye          QPoint pupil offsets
  emotion      name
  emo          current emotion dict
"""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, QPoint, QPointF
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPainterPath, QRadialGradient, QFont,
)


# ---------------------------------------------------------------------------
# Base helpers
# ---------------------------------------------------------------------------
def _g(p, cx: float, cy: float, r, light: QColor, dark: QColor):
    grad = QRadialGradient(cx, cy, r)
    grad.setColorAt(0, light)
    grad.setColorAt(1, dark)
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)


def _ear(p, hx: float, hy: float, s: float, sign: int, tilt: float,
         color: QColor, inner: QColor, kind: str = "tri"):
    ear = 0.18 * s
    ex = hx + sign * 0.22 * s + tilt * sign * 0.3
    ey = hy - 0.30 * s
    p.setBrush(QBrush(color))
    p.setPen(Qt.NoPen)
    if kind == "round":
        p.drawEllipse(QPointF(ex, ey - ear * 0.4), ear * 0.62, ear * 0.62)
        ir = ear * 0.32
        p.setBrush(QBrush(inner))
        p.drawEllipse(QPointF(ex, ey - ear * 0.42), ir, ir)
    elif kind == "long":  # rabbit
        p.drawEllipse(QPointF(ex, ey - ear * 0.9), ear * 0.4, ear * 1.7)
        p.setBrush(QBrush(inner))
        p.drawEllipse(QPointF(ex, ey - ear * 0.7), ear * 0.2, ear * 1.2)
    else:
        poly = [
            QPoint(int(ex - ear * 0.6), int(ey + ear)),
            QPoint(int(ex), int(ey - ear)),
            QPoint(int(ex + ear * 0.6), int(ey + ear)),
        ]
        p.drawPolygon(poly)
        p.setBrush(QBrush(inner))
        poly2 = [
            QPoint(int(ex - ear * 0.3), int(ey + ear * 0.6)),
            QPoint(int(ex), int(ey - ear * 0.2)),
            QPoint(int(ex + ear * 0.3), int(ey + ear * 0.6)),
        ]
        p.drawPolygon(poly2)


def _eyes(p, ctx, eye_dy=0.02, eye_dx=0.12, eye_r=0.10, pupil_r=0.055,
          white=True, glow_pupil=False):
    s = ctx.s; hx = ctx.hx; hy = ctx.hy
    emo = ctx.emo
    off = ctx.eye
    eyex = off.x() * 0.005 * s
    eyey = off.y() * 0.005 * s
    squint = emo.get("eye_squint", 0.0)
    eye_y = hy - eye_dy * s
    wh = eye_r * (1.0 - squint * 0.5)  # white ellipse vertical radius
    for sign in (-1, 1):
        ex = hx + sign * eye_dx * s
        # white of the eye
        if white:
            p.setBrush(QBrush(ctx.white))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPoint(int(ex), int(eye_y)), int(eye_r * s), max(1, int(wh * s)))
        # pupil center (follows the mouse)
        px = ex + eyex
        py = eye_y + eyey
        # iris — the colored disc that fills most of the eye
        iris_r = eye_r * (1.0 - squint * 0.4)
        p.setBrush(QBrush(ctx.pupil))
        p.drawEllipse(QPoint(int(px), int(py)), int(iris_r * s), int(iris_r * s))
        # dark core
        core = QColor(ctx.pupil).darker(180)
        p.setBrush(QBrush(core))
        p.drawEllipse(QPoint(int(px), int(py)), int(iris_r * 0.55 * s), int(iris_r * 0.55 * s))
        # white glint (anime highlight) — top-left of the iris
        gl = QColor(255, 255, 255, 230)
        p.setBrush(QBrush(gl))
        p.drawEllipse(QPoint(int(px - iris_r * s * 0.45), int(py - iris_r * s * 0.45)),
                      max(1, int(iris_r * s * 0.30)), max(1, int(iris_r * s * 0.30)))
        # small secondary glint
        gl2 = QColor(255, 255, 255, 160)
        p.setBrush(QBrush(gl2))
        p.drawEllipse(QPoint(int(px + iris_r * s * 0.35), int(py + iris_r * s * 0.15)),
                      max(1, int(iris_r * s * 0.14)), max(1, int(iris_r * s * 0.14)))
        # blink overlay
        if ctx.blink > 0.01:
            closed = int(eye_r * (1 - ctx.blink))
            p.setBrush(QBrush(ctx.dark))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPoint(int(ex), int(eye_y)), int(eye_r * s), max(1, closed))


def _nose(p, ctx, y=0.10, rx=0.03, s2=0.025, color=None):
    p.setBrush(QBrush(color or ctx.nose))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPoint(int(ctx.hx), int(ctx.hy + y * ctx.s)),
                  int(rx * ctx.s), int(s2 * ctx.s))


def _mouth(p, ctx, y=0.11):
    curve = ctx.emo.get("mouth_curve", 180)
    p.setPen(QPen(ctx.mouth, max(2, ctx.s * 0.02), Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(ctx.hx - 0.06 * ctx.s, ctx.hy + y * ctx.s,
                     0.12 * ctx.s, 0.06 * ctx.s), 0, curve * 16)


def _whiskers(p, ctx):
    p.setPen(QPen(ctx.whisker, max(1, ctx.s * 0.012), Qt.SolidLine, Qt.RoundCap))
    for sign in (-1, 1):
        wx = ctx.hx + sign * 0.10 * ctx.s
        wy = ctx.hy + 0.10 * ctx.s
        for k in (-1, 0, 1):
            p.drawLine(QPoint(int(wx), int(wy)),
                       QPoint(int(wx + sign * 0.22 * ctx.s), int(wy + k * 0.04 * ctx.s)))


def _cheeks(p, ctx):
    alpha = ctx.emo.get("cheek_alpha", 0)
    if alpha <= 0:
        return
    p.setBrush(QBrush(QColor(255, 150, 180, alpha)))
    p.setPen(Qt.NoPen)
    for sign in (-1, 1):
        cx2 = ctx.hx + sign * 0.18 * ctx.s
        cy2 = ctx.hy + 0.08 * ctx.s
        p.drawEllipse(QPoint(int(cx2), int(cy2)), int(0.06 * ctx.s), int(0.04 * ctx.s))


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------
def draw_cat(p, ctx):
    s, hx, hy, by = ctx.s, ctx.hx, ctx.hy, ctx.by
    cx, cy = ctx.cx, ctx.cy
    light, dark = ctx.light, ctx.dark
    _g(p, cx, by, 0.42 * s, light, dark)
    p.drawEllipse(QPoint(int(cx), int(by)), int(0.42 * s), int(0.42 * s * 1.05))
    # tail
    t = math.sin(ctx.t * (2.2 if ctx.emotion != "angry" else 5.0)) * (0.08 if ctx.emotion != "angry" else 0.15) * s
    tp = QPainterPath()
    tp.moveTo(cx + 0.29 * s, by + 0.08 * s)
    tp.quadTo(cx + 0.59 * s + t, by - 0.08 * s, cx + 0.50 * s + t, by - 0.38 * s)
    p.setPen(QPen(dark, max(4, s * 0.05), Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawPath(tp)
    for sign in (-1, 1):
        _ear(p, hx, hy, s, sign, ctx.emo.get("ear_tilt", 0), dark, ctx.ear_inner, "tri")
    _g(p, hx, hy, 0.30 * s * ctx.scale, light, dark)
    p.drawEllipse(QPoint(int(hx), int(hy)), int(0.30 * s * ctx.scale), int(0.30 * s * ctx.scale))
    _eyes(p, ctx)
    _nose(p, ctx)
    _mouth(p, ctx)
    _whiskers(p, ctx)
    _cheeks(p, ctx)


def draw_fox(p, ctx):
    s, hx, hy, by, cx = ctx.s, ctx.hx, ctx.hy, ctx.by, ctx.cx
    light, dark = ctx.light, ctx.dark
    _g(p, cx, by, 0.42 * s, light, dark)
    p.drawEllipse(QPoint(int(cx), int(by)), int(0.42 * s), int(0.42 * s * 1.05))
    # big fox tail with white tip
    t = math.sin(ctx.t * 2.4) * 0.1 * s
    tp = QPainterPath()
    tp.moveTo(cx - 0.3 * s, by + 0.1 * s)
    tp.quadTo(cx - 0.6 * s + t * 0.5, by - 0.1 * s, cx - 0.52 * s + t, by - 0.45 * s)
    p.setPen(QPen(dark, max(5, s * 0.08), Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawPath(tp)
    p.setPen(QPen(QColor("#ffffff"), max(5, s * 0.08), Qt.SolidLine, Qt.RoundCap))
    p.drawPoint(QPoint(int(cx - 0.52 * s + t), int(by - 0.45 * s)))
    # pointy tall ears
    for sign in (-1, 1):
        _ear(p, hx, hy, s, sign, ctx.emo.get("ear_tilt", 0), dark, ctx.ear_inner, "tri")
    _g(p, hx, hy, 0.30 * s * ctx.scale, light, dark)
    p.drawEllipse(QPoint(int(hx), int(hy)), int(0.30 * s * ctx.scale), int(0.30 * s * ctx.scale))
    # white muzzle
    p.setBrush(QBrush(QColor("#ffffff")))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPoint(int(hx), int(hy + 0.09 * s)), int(0.10 * s), int(0.08 * s))
    _eyes(p, ctx, eye_dy=0.02, eye_dx=0.10, pupil_r=0.045)
    _nose(p, ctx, y=0.10, rx=0.024, s2=0.02)
    _mouth(p, ctx)
    _whiskers(p, ctx)


def draw_rabbit(p, ctx):
    s, hx, hy, by, cx = ctx.s, ctx.hx, ctx.hy, ctx.by, ctx.cx
    light, dark = ctx.light, ctx.dark
    _g(p, cx, by, 0.42 * s, light, dark)
    p.drawEllipse(QPoint(int(cx), int(by)), int(0.42 * s), int(0.42 * s * 1.05))
    # tiny round tail
    p.setBrush(QBrush(QColor("#ffffff")))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPoint(int(cx + 0.36 * s), int(by + 0.05 * s)), int(0.07 * s), int(0.07 * s))
    # long rabbit ears
    for sign in (-1, 1):
        _ear(p, hx, hy, s, sign, ctx.emo.get("ear_tilt", 0), dark, ctx.ear_inner, "long")
    _g(p, hx, hy, 0.30 * s * ctx.scale, light, dark)
    p.drawEllipse(QPoint(int(hx), int(hy)), int(0.30 * s * ctx.scale), int(0.30 * s * ctx.scale))
    # pink inner muzzle + nose
    p.setBrush(QBrush(QColor("#fff0f3")))
    p.drawEllipse(QPoint(int(hx), int(hy + 0.10 * s)), int(0.09 * s), int(0.07 * s))
    # buck teeth
    p.setBrush(QBrush(QColor("#ffffff")))
    p.setPen(QPen(QColor("#cccccc"), 1))
    p.drawRect(QRectF(hx - 0.018 * s, hy + 0.14 * s, 0.016 * s, 0.03 * s))
    p.drawRect(QRectF(hx + 0.003 * s, hy + 0.14 * s, 0.016 * s, 0.03 * s))
    _nose(p, ctx, y=0.075, rx=0.03, s2=0.028, color=QColor(255, 160, 190, 255))
    _eyes(p, ctx, eye_dy=0.02, eye_dx=0.11, pupil_r=0.05)
    _whiskers(p, ctx)


def draw_dog(p, ctx):
    s, hx, hy, by, cx = ctx.s, ctx.hx, ctx.hy, ctx.by, ctx.cx
    light, dark = ctx.light, ctx.dark
    _g(p, cx, by, 0.42 * s, light, dark)
    p.drawEllipse(QPoint(int(cx), int(by)), int(0.42 * s), int(0.42 * s * 1.05))
    # floppy ears
    for sign in (-1, 1):
        ex = hx + sign * 0.22 * s
        ey = hy - 0.22 * s
        p.setBrush(QBrush(dark))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(ex, ey), 0.10 * s, 0.18 * s)
    # muzzle patch
    p.setBrush(QBrush(QColor("#ffffff")))
    p.drawEllipse(QPoint(int(hx), int(hy + 0.09 * s)), int(0.11 * s), int(0.09 * s))
    # snout bump
    p.setBrush(QBrush(ctx.nose))
    p.drawEllipse(QPoint(int(hx), int(hy + 0.09 * s)), int(0.035 * s), int(0.028 * s))
    _g(p, hx, hy, 0.30 * s * ctx.scale, light, dark)
    p.drawEllipse(QPoint(int(hx), int(hy)), int(0.30 * s * ctx.scale), int(0.30 * s * ctx.scale))
    # tongue on happy
    if ctx.emotion in ("happy", "love"):
        p.setBrush(QBrush(QColor("#ff8fa3")))
        p.drawEllipse(QPoint(int(hx), int(hy + 0.16 * s)), int(0.035 * s), int(0.05 * s))
    _eyes(p, ctx, eye_dy=0.02, eye_dx=0.11, pupil_r=0.05)
    _mouth(p, ctx, y=0.15)
    _whiskers(p, ctx)


def draw_bear(p, ctx):
    s, hx, hy, by, cx = ctx.s, ctx.hx, ctx.hy, ctx.by, ctx.cx
    light, dark = ctx.light, ctx.dark
    _g(p, cx, by, 0.44 * s, light, dark)
    p.drawEllipse(QPoint(int(cx), int(by)), int(0.44 * s), int(0.44 * s * 1.05))
    # round ears
    for sign in (-1, 1):
        _ear(p, hx, hy, s, sign, ctx.emo.get("ear_tilt", 0), dark, ctx.ear_inner, "round")
    _g(p, hx, hy, 0.32 * s * ctx.scale, light, dark)
    p.drawEllipse(QPoint(int(hx), int(hy)), int(0.32 * s * ctx.scale), int(0.32 * s * ctx.scale))
    # lighter muzzle
    p.setBrush(QBrush(QColor("#fff3e0")))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPoint(int(hx), int(hy + 0.10 * s)), int(0.09 * s), int(0.07 * s))
    _nose(p, ctx, y=0.09, rx=0.028, s2=0.024, color=QColor("#4a3418"))
    _mouth(p, ctx)
    _eyes(p, ctx, eye_dy=0.02, eye_dx=0.11, pupil_r=0.048)


CHARACTERS: dict[str, dict] = {
    "cat": {
        "name": "Cat", "draw": draw_cat,
        "light": "#ffe7c2", "dark": "#f7c98b", "ear_inner": "#ff9ecb",
        "nose": "#ff7aa2", "mouth": "#7a5230", "whisker": "#caa37a",
        "white": "#ffffff", "pupil": "#2b2b2b",
    },
    "fox": {
        "name": "Fox", "draw": draw_fox,
        "light": "#ffcf8f", "dark": "#e8823a", "ear_inner": "#ffe8c9",
        "nose": "#4a3418", "mouth": "#4a3418", "whisker": "#caa37a",
        "white": "#ffffff", "pupil": "#30a030",
    },
    "rabbit": {
        "name": "Rabbit", "draw": draw_rabbit,
        "light": "#f2efe9", "dark": "#d8d2c4", "ear_inner": "#ffb8cc",
        "nose": "#ff9ecb", "mouth": "#8a8578", "whisker": "#b0ab9f",
        "white": "#ffffff", "pupil": "#3a4a6a",
    },
    "dog": {
        "name": "Dog", "draw": draw_dog,
        "light": "#eaceb0", "dark": "#c89a67", "ear_inner": "#a8784a",
        "nose": "#5a3a20", "mouth": "#5a3a20", "whisker": "#a89078",
        "white": "#ffffff", "pupil": "#2a2a2a",
    },
    "bear": {
        "name": "Bear", "draw": draw_bear,
        "light": "#c89a6b", "dark": "#9a6a3a", "ear_inner": "#e8c9a0",
        "nose": "#6a4a2a", "mouth": "#6a4a2a", "whisker": "#8a6a4a",
        "white": "#fff3e8", "pupil": "#2a2a2a",
    },
}


def get_character(name: str) -> dict:
    return CHARACTERS.get(name, CHARACTERS["cat"])


def character_names() -> list[str]:
    return list(CHARACTERS.keys())
