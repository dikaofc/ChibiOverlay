"""The chibi companion widget.

A small character drawn with QPainter that reacts in real time:
  - head + eyes follow the physical mouse (gated by toggle + dead zone)
  - the whole body leans toward the cursor (arm_follow toggle)
  - periodic blinking
  - a "pop" reaction on key press / mouse click (plus an emotion flash)
  - a gentle idle breathing + tail sway
  - emotion states: happy, surprised, sleepy, angry, love

The widget is meant to live on a transparent, always-on-top overlay, so
it paints nothing outside its own shape (full transparency elsewhere).
"""
from __future__ import annotations

import math
import os
from typing import Optional

from PySide6.QtCore import (
    QRectF, QSize, Qt, QTimer, QPoint, QElapsedTimer, QUrl,
)
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QMovie, QPainterPath, QRadialGradient, QFont,
    QPixmap,
)
from PySide6.QtWidgets import QWidget, QLabel

try:  # mp4 playback (QtMultimedia optional — absent on minimal builds)
    from PySide6.QtMultimedia import QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    _HAS_VIDEO = True
except Exception:  # pragma: no cover
    _HAS_VIDEO = False

from .models import ChibiConfig
from .characters import get_character


class _Ctx:
    """Painter context shared with character draw routines."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


# Emotion states — each is a dict of visual overrides
EMOTIONS = {
    "idle":      {"mouth_curve": 180, "eye_squint": 0.0, "ear_tilt": 0.0, "cheek_alpha": 0,   "color_override": None},
    "happy":     {"mouth_curve": 200, "eye_squint": 0.3, "ear_tilt": 5,   "cheek_alpha": 120, "color_override": "#ffd700"},
    "surprised": {"mouth_curve": 90,  "eye_squint": 0.0, "ear_tilt": -8,  "cheek_alpha": 0,   "color_override": None},
    "sleepy":    {"mouth_curve": 160, "eye_squint": 0.7, "ear_tilt": -3,  "cheek_alpha": 0,   "color_override": None},
    "angry":     {"mouth_curve": 120, "eye_squint": 0.5, "ear_tilt": -10, "cheek_alpha": 0,   "color_override": "#ff6b6b"},
    "love":      {"mouth_curve": 200, "eye_squint": 0.4, "ear_tilt": 3,   "cheek_alpha": 160, "color_override": "#ff69b4"},
}


class ChibiWidget(QWidget):
    def __init__(self, config: ChibiConfig, parent: Optional[QWidget] = None, theme: str = "cat"):
        super().__init__(parent)
        self.cfg = config
        self._character = theme or "cat"
        self._movie: Optional[QMovie] = None
        self._movie_label: Optional[QLabel] = None
        self._video: object = None
        self._video_widget: object = None

        # Animation state
        self._t = 0.0
        self._timer = QElapsedTimer()
        self._timer.start()
        self._last_ns = self._timer.nsecsElapsed()

        # Where the head/eyes should look (smoothed). Set by set_mouse_global.
        self._look_target = QPoint(0, 0)
        self._head = QPoint(0, 0)
        self._eye = QPoint(0, 0)
        # Whole-body lean toward the cursor (arm_follow toggle).
        self._lean = QPoint(0, 0)

        self._pop = 0.0
        self._click = 0.0  # mouse-click poke impulse (see set_click)
        self._blink = 0.0
        self._next_blink = self._rand_blink()

        # Emotion
        self._emotion = "idle"
        self._emotion_timer = 0.0

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(16)

        self.draggable = False

        self.setMinimumSize(config.size, config.size)
        self._apply_media()

    # ---------------------------------------------------------------- config
    def set_config(self, cfg: ChibiConfig):
        self.cfg = cfg
        self.setMinimumSize(cfg.size, cfg.size)
        self.resize(cfg.size, cfg.size)
        self._apply_media()

    def set_character(self, name: str):
        self._character = name or "cat"
        self.update()

    def _apply_media(self):
        """Show custom chibi media (gif / png / jpg / mp4) or fall back to the
        procedural character when no path is set."""
        self._clear_media()
        path = self.cfg.gif_path
        if not (path and os.path.exists(path)):
            return
        ext = os.path.splitext(path)[1].lower()

        if ext == ".mp4" and _HAS_VIDEO:
            from PySide6.QtMultimedia import QMediaPlayer
            from PySide6.QtMultimediaWidgets import QVideoWidget
            vw = QVideoWidget(self)
            vw.setAttribute(Qt.WA_TranslucentBackground)
            vw.setGeometry(0, 0, self.width(), self.height())
            vw.show()
            player = QMediaPlayer()
            player.setVideoOutput(vw)
            player.setSource(QUrl.fromLocalFile(path))
            player.setLoops(QMediaPlayer.Infinite)
            player.play()
            self._video, self._video_widget = player, vw
            return

        if self._movie_label is None:
            self._movie_label = QLabel(self)
            self._movie_label.setAlignment(Qt.AlignCenter)
            self._movie_label.setAttribute(Qt.WA_TranslucentBackground)
        self._movie_label.setGeometry(0, 0, self.width(), self.height())

        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            pm = QPixmap(path)
            if not pm.isNull():
                self._movie_label.setPixmap(pm.scaled(
                    self.width(), self.height(),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self._movie_label.show()
            return

        # default: animated gif (also apng/webm depending on Qt build)
        if self._movie is None:
            self._movie = QMovie(path, parent=self)
            self._movie.setCacheMode(QMovie.CacheAll)
            self._movie_label.setMovie(self._movie)
        self._movie.setFileName(path)
        self._movie.start()
        self._movie_label.show()

    def _clear_media(self):
        if self._video is not None:
            try:
                self._video.stop()
                self._video.setVideoOutput(None)
            except Exception:
                pass
            self._video = self._video_widget = None
        if self._movie is not None:
            self._movie.stop()
        if self._movie_label is not None:
            self._movie_label.hide()
            self._movie_label.setPixmap(QPixmap())
        for w in self.findChildren(QVideoWidget) if _HAS_VIDEO else []:
            w.deleteLater()

    # ---------------------------------------------------------------- events
    def set_mouse_global(self, gx: int, gy: int):
        center = self.mapToGlobal(self.rect().center())
        dx = gx - center.x()
        dy = gy - center.y()
        dist = math.hypot(dx, dy) or 1.0
        # Dead zone: ignore tiny cursor movements so the character isn't jittery.
        if dist < self.cfg.dead_zone:
            self._look_target = QPoint(0, 0)
            return
        # Unit direction scaled to a stable magnitude (direction only, not distance).
        self._look_target = QPoint(int(dx / dist * 100), int(dy / dist * 100))

    def pulse(self):
        self._pop = 1.0

    def set_emotion(self, name: str, duration: float = 3.0):
        """Switch to an emotion state for `duration` seconds, then return to idle."""
        if name in EMOTIONS:
            self._emotion = name
            self._emotion_timer = duration

    def set_click(self, base: str, pressed: bool):
        """React to a real mouse click (called from OverlayWindow.handle_click).

        On a press we add a small "poke" scale impulse so the character visibly
        jabs toward the button; releases only stop the impulse. This is separate
        from pulse()/set_emotion() (also driven by handle_click) so a single
        click doesn't stack them into one giant pop.
        """
        self._click = 1.0 if pressed else 0.0

    def _rand_blink(self) -> float:
        return 2.0 + (self._timer.nsecsElapsed() % 3000) / 1000.0

    # ---------------------------------------------------------------- tick
    def _tick(self):
        now = self._timer.nsecsElapsed()
        dt = (now - self._last_ns) / 1e9
        self._last_ns = now
        self._t += dt

        cfg = self.cfg
        follows = cfg.mouse_follow

        # Head tracking.
        if follows and cfg.head_follow:
            k_head = 1.0 - cfg.smoothing
            k_head = max(0.05, min(0.6, k_head)) * cfg.follow_strength
            self._head.setX(self._lerp(self._head.x(), self._look_target.x(), k_head))
            self._head.setY(self._lerp(self._head.y(), self._look_target.y(), k_head))
        else:
            self._head.setX(self._lerp(self._head.x(), 0.0, 0.2))
            self._head.setY(self._lerp(self._head.y(), 0.0, 0.2))

        # Eye tracking (independent of head; eased by eye_movement).
        if follows and cfg.eye_follow:
            ex = int(self._look_target.x() * cfg.eye_movement * 0.6)
            ey = int(self._look_target.y() * cfg.eye_movement * 0.6)
            self._eye.setX(self._lerp(self._eye.x(), ex, 0.25))
            self._eye.setY(self._lerp(self._eye.y(), ey, 0.25))
        else:
            self._eye.setX(self._lerp(self._eye.x(), 0.0, 0.25))
            self._eye.setY(self._lerp(self._eye.y(), 0.0, 0.25))

        # Whole-body lean (arm_follow) — the character leans toward the cursor.
        if follows and cfg.arm_follow:
            lx = self._look_target.x() * 0.10
            ly = self._look_target.y() * 0.10
            self._lean.setX(self._lerp(self._lean.x(), lx, 0.08))
            self._lean.setY(self._lerp(self._lean.y(), ly, 0.08))
        else:
            self._lean.setX(self._lerp(self._lean.x(), 0.0, 0.12))
            self._lean.setY(self._lerp(self._lean.y(), 0.0, 0.12))

        self._pop = max(0.0, self._pop - dt * 3.0)

        # blink scheduling
        self._next_blink -= dt
        if self._next_blink <= 0:
            self._blink = 1.0
            self._next_blink = self._rand_blink()
        else:
            self._blink = max(0.0, self._blink - dt * 8.0)

        # emotion timer
        if self._emotion != "idle":
            self._emotion_timer -= dt
            if self._emotion_timer <= 0:
                self._emotion = "idle"
                self._emotion_timer = 0.0

        if self._movie_label is not None and self._movie_label.isVisible():
            self._movie_label.setGeometry(0, 0, self.width(), self.height())
        self.update()

    @staticmethod
    def _lerp(a, b, t):
        return a + (b - a) * t

    def _cur_emotion(self) -> dict:
        return EMOTIONS.get(self._emotion, EMOTIONS["idle"])

    # ---------------------------------------------------------------- paint
    def paintEvent(self, event):
        if self._movie_label is not None and self._movie_label.isVisible():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self._draw_cat(p)
        p.end()

    def _draw_cat(self, p: QPainter):
        w, h = self.width(), self.height()
        # Shrink the drawing so the character keeps transparent margin around
        # it. Without this, tails/ears that animate past the center get
        # clipped at the widget rectangle.
        s = min(w, h) * 0.78
        cx = w / 2 + self._lean.x()
        cy = h / 2 + self._lean.y()
        emo = self._cur_emotion()
        char = get_character(self._character)
        light = QColor(char["light"])
        dark = QColor(char["dark"])

        breathe = math.sin(self._t * 1.6) * 0.02 * s
        hx = cx + self._head.x() * 0.18
        hy = cy + self._head.y() * 0.18 - breathe
        pop = self._pop
        scale = 1.0 + pop * 0.06
        by = cy + 0.22 * s  # body center y

        # ---- context passed to the character draw routine ----
        ctx = _Ctx(
            p=p, s=s, cx=cx, cy=cy, hx=hx, hy=hy, by=by,
            breathe=breathe, scale=scale, t=self._t,
            blink=self._blink, eye=self._eye, emotion=self._emotion, emo=emo,
            light=light, dark=dark, ear_inner=QColor(char["ear_inner"]),
            nose=QColor(char["nose"]), mouth=QColor(char["mouth"]),
            whisker=QColor(char["whisker"]), white=QColor(char["white"]),
            pupil=QColor(char["pupil"]),
        )

        # Character body/head/face
        char["draw"](p, ctx)

        # ---- emotion effects (shared across characters) ----
        self._draw_effects(p, ctx, pop)

    def _draw_effects(self, p: QPainter, ctx, pop: float):
        """Emotion extras: pop ring, exclamation, ZZZ, steam. Shared by all chars."""
        s = ctx.s; hx = ctx.hx; hy = ctx.hy
        # Pop ring
        if pop > 0.01:
            p.setPen(QPen(QColor(255, 158, 203, int(180 * pop)), max(2, s * 0.03)))
            p.setBrush(Qt.NoBrush)
            rr = int(0.30 * s * ctx.scale + (1 - pop) * 0.4 * s)
            p.drawEllipse(QPoint(int(hx), int(hy)), rr, rr)
        # Surprised: exclamation marks
        if ctx.emotion == "surprised":
            p.setPen(QPen(QColor(255, 220, 100, 200), max(2, s * 0.025)))
            for dx in (-0.35, 0.35):
                ex = hx + dx * s
                ey = hy - 0.40 * s
                p.drawLine(QPoint(int(ex), int(ey)), QPoint(int(ex), int(ey + 0.08 * s)))
                p.drawEllipse(QPoint(int(ex), int(ey + 0.12 * s)), int(0.015 * s), int(0.015 * s))
        # Sleepy: ZZZ
        if ctx.emotion == "sleepy":
            p.setPen(QPen(QColor(180, 200, 255, 180), max(2, s * 0.02)))
            for i, (dx, dy, sz) in enumerate([(0.3, -0.3, 0.06), (0.4, -0.4, 0.05), (0.5, -0.5, 0.04)]):
                zx = hx + dx * s + math.sin(self._t * 2 + i) * 3
                zy = hy + dy * s + math.cos(self._t * 1.5 + i) * 2
                font = QFont("Segoe UI", int(sz * s), QFont.Bold)
                p.setFont(font)
                p.drawText(QPoint(int(zx), int(zy)), "Z")
        # Angry: steam puffs
        if ctx.emotion == "angry":
            puff_alpha = int(150 * (0.5 + 0.5 * math.sin(self._t * 6)))
            p.setBrush(QBrush(QColor(255, 100, 100, puff_alpha)))
            p.setPen(Qt.NoPen)
            for sign in (-1, 1):
                px = hx + sign * 0.25 * s
                py = hy - 0.38 * s + math.sin(self._t * 4) * 2
                p.drawEllipse(QPoint(int(px), int(py)), int(0.04 * s), int(0.03 * s))

    # ---------------------------------------------------------------- drag
    def mousePressEvent(self, ev):
        if self.draggable:
            self._drag_pos = ev.globalPosition().toPoint()
            self._drag_origin = self.geometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self.draggable and getattr(self, "_drag_pos", None) is not None:
            delta = ev.globalPosition().toPoint() - self._drag_pos
            self.move(self._drag_origin + delta)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None
        if self.draggable:
            ev.accept()
