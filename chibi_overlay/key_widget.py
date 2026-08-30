"""A single visual keycap that mirrors a physical key's press/release.

It renders with QPainter so it stays transparent outside the cap and can
be animated (press = cap sinks + glows; release = springs back). All colors
and metrics come from the token-based theme in ``themes.py`` — this widget
contains no hard-coded palette.

States (normal / hover / pressed / selected / disabled) are read from the
theme per the widget's current interaction state, so hover/press give real
visual feedback.

Right-click in edit mode opens a context menu:
  - Lock / Unlock position
  - Resize (cycle through presets)
  - Delete key
"""
from __future__ import annotations

import math
import time
from typing import Optional

from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QLinearGradient, QPainterPath
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QInputDialog

from .models import KeyConfig
from .themes import get_theme, theme_names

_SIZE_PRESETS = [48, 56, 64, 72, 80, 96]

# Responsive base: tokens use this as the "design size"; we scale by the
# actual widget size so caps never clip and proportions stay constant.
_BASE = 64


class KeyWidget(QWidget):
    def __init__(self, cfg: KeyConfig, parent: Optional[QWidget] = None, theme: str = "dark"):
        super().__init__(parent)
        self.cfg = cfg
        self._theme_name = theme
        # Pull the theme's own corner radius so themes differ at once; the
        # Appearance "Key corner radius" slider overrides it live via set_radius().
        try:
            self._radius_override = int(get_theme(theme).key.radius)
        except Exception:
            self._radius_override = 10
        self._pressed = 0.0       # 0..1 animated press amount (visual ease)
        self._target = 0.0
        self._t = 0.0             # time for sparkle/sheen animation
        # Interaction states.
        self._hover = False
        self._selected = False
        self._disabled = False
        self.draggable = False
        self._drag_pos = None
        # Real visual tuning driven from the profile.
        self._scale = 1.0         # drawn size relative to cfg.size
        self._cap_opacity = 1.0
        # Cached frosted-glass backdrop (see _frost) so glass themes don't
        # re-grab the compositor every paint frame.
        self._frost_cache = None
        self._frost_key = None
        self._frost_ts = 0.0
        self.setFixedSize(cfg.size, cfg.size)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._tick)
        self._anim.start(16)

    # ----------------------------------------------------------- config
    def set_config(self, cfg: KeyConfig):
        self.cfg = cfg
        self.setFixedSize(cfg.size, cfg.size)

    def set_theme(self, name: str):
        self._theme_name = name
        try:
            self._radius_override = int(get_theme(name).key.radius)
        except Exception:
            pass
        self.update()

    def set_scale(self, scale: float):
        """Scale the rendered cap inside its fixed widget box (real, live)."""
        self._scale = max(0.5, min(1.5, float(scale)))
        self.update()

    def set_opacity(self, opacity: float):
        """Cap opacity 0..1 (real, live)."""
        self._cap_opacity = max(0.1, min(1.0, float(opacity)))
        self.update()

    def set_radius(self, radius: int):
        """Corner radius override in px (real, live); 0 = use theme default."""
        self._radius_override = max(0, int(radius))
        self.update()

    # ----------------------------------------------------------- state
    def set_selected(self, on: bool):
        self._selected = on
        self.update()

    def set_disabled(self, on: bool):
        self._disabled = on
        self.update()

    def press(self):
        self._target = 1.0

    def release(self):
        self._target = 0.0

    def _tick(self):
        self._pressed += (self._target - self._pressed) * 0.35
        self._t += 0.016
        self.update()

    def _accent(self) -> QColor:
        return QColor(self.cfg.color)

    # ----------------------------------------------------------- paint
    def paintEvent(self, event):
        theme = get_theme(self._theme_name)
        kstyle = theme.key
        eff = theme.effects

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Scale the cap down inside its box so the user-visible size sliders work
        # without resizing the widget (which would break drag/position math).
        sc = self._scale
        if sc != 1.0:
            ox = (w * (1 - sc)) / 2.0
            oy = (h * (1 - sc)) / 2.0
            p.translate(ox, oy)
            w = int(w * sc)
            h = int(h * sc)
        p.setOpacity(self._cap_opacity)

        # Responsive factor: tokens are authored at a 64px design size.
        size = min(w, h)
        factor = size / _BASE if _BASE > 0 else 1.0

        # Pick the key state from interaction flags, highest precedence first.
        if self._disabled:
            st = kstyle.disabled
        elif self._pressed > 0.5 or self._target == 1.0:
            st = kstyle.pressed
        elif self._selected:
            st = kstyle.selected
        elif self._hover:
            st = kstyle.hover
        else:
            st = kstyle.normal

        radius = self._radius_override if self._radius_override > 0 else kstyle.radius
        # Scale radius to the actual widget, clamped so it never exceeds half.
        r = max(0, min(int(radius * factor), int(min(w, h) * 0.5)))
        height = max(0, int(kstyle.height * factor))
        bevel = max(0, int(kstyle.bevel * factor))
        bwidth = max(1, int(kstyle.border_width * factor))
        drop = int(self._pressed * max(2, int(size * 0.06)))  # visual sink on press

        cap_rect = QRectF(2, 2 + drop, w - 4, h - 4 - drop)
        face_rect = QRectF(4, 4 + drop, w - 8, h - 8 - drop)

        label_col = st.label
        glow_col = st.glow or eff.glow.color

        # ---- drop shadow (offset downwards) ----
        if eff.shadow.enabled and st.shadow_offset_y > 0:
            so = max(1, int(st.shadow_offset_y * factor))
            sh = QColor(eff.shadow.color)
            p.setBrush(QBrush(sh))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(
                QRectF(2, 2 + so + drop, w - 4, h - 4 - drop), r, r
            )

        # ---- glow bloom behind cap (glow color, only when glow enabled) ----
        if eff.glow.enabled and self._pressed > 0.01:
            g = QColor(glow_col)
            g.setAlpha(int(120 * self._pressed))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(g, max(2, int(w * 0.04))))
            p.drawRoundedRect(cap_rect, r, r)

        # ---- base cap (backing so transparent glass themes still read) ----
        bg = QColor(st.bg)
        if st.bg == "transparent":
            bg = QColor(theme.panel.surface)
            bg.setAlpha(60)
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(cap_rect, r, r)

        # ---- top surface (gradient for 3d/glass; flat otherwise) ----
        self._draw_surface(p, kstyle, st, face_rect, factor)

        # ---- top light strip (3D illusion) ----
        if kstyle.style == "3d":
            hi = QColor(st.top).lighter(118)
            p.setBrush(QBrush(hi))
            p.drawRoundedRect(
                QRectF(4, 4 + drop, w - 8, max(2, int(h * 0.12))),
                max(0, r - 2), max(0, r - 2),
            )

        # ---- border ----
        if kstyle.style == "flat":
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(st.border), bwidth + 1))
            p.drawRoundedRect(cap_rect, r, r)
        elif kstyle.style in ("3d", "glass"):
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(st.border), bwidth))
            p.drawRoundedRect(cap_rect, r, r)

        # ---- inner glow fill on press ----
        if self._pressed > 0.01:
            ig = QColor(glow_col)
            ig.setAlpha(int(30 * self._pressed))
            p.setBrush(QBrush(ig))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(face_rect, max(0, r - 2), max(0, r - 2))

        # ---- accent underline ----
        if kstyle.accent_bar:
            p.setBrush(QBrush(self._accent()))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(
                QRectF(6, h - 10 - drop, w - 12, max(2, int(h * 0.05))), 3, 3
            )

        # ---- animated glass sheen (diagonal highlight sweep) ----
        if eff.sheen:
            span = w + h
            x0 = self._t * span * 0.5 - span
            sheen = QLinearGradient(x0, 0, x0 + span * 0.8, h)
            scol = QColor(eff.sheen_color)
            sheen.setColorAt(0.0, QColor(scol.red(), scol.green(), scol.blue(), 0))
            sheen.setColorAt(0.5, scol)
            sheen.setColorAt(1.0, QColor(scol.red(), scol.green(), scol.blue(), 0))
            p.setBrush(QBrush(sheen))
            p.setPen(Qt.NoPen)
            p.save()
            p.setClipRect(face_rect)
            p.drawRect(QRectF(0, 0, w, h))
            p.restore()

        # ---- sparkles ----
        if eff.sparkles:
            for i in range(3):
                phase = self._t * 2.0 + i * 2.1
                alpha = int(80 * (0.5 + 0.5 * math.sin(phase)))
                sx = w * (0.2 + 0.6 * ((math.sin(phase * 0.7 + i) + 1) / 2))
                sy = h * (0.2 + 0.6 * ((math.cos(phase * 0.5 + i * 1.3) + 1) / 2))
                sz = max(1, int(w * 0.04))
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(QColor(255, 255, 255, alpha)))
                sparkle = QPainterPath()
                sparkle.moveTo(sx, sy - sz)
                sparkle.lineTo(sx + sz * 0.4, sy)
                sparkle.lineTo(sx, sy + sz)
                sparkle.lineTo(sx - sz * 0.4, sy)
                sparkle.closeSubpath()
                p.drawPath(sparkle)

        # ---- label (auto-contrast comes from the theme token) ----
        font_size = max(theme.min_key_font,
                        min(theme.max_key_font, int(size * 0.28 * factor)))
        font = QFont(theme.typography.font_family, font_size,
                     theme.typography.weight_bold)
        p.setPen(QPen(QColor(label_col)))
        p.setFont(font)
        # Draw text in the SCALED coordinate space, not self.rect().
        # After translate(ox,oy) + w/h resize, the visible area is (0,0,w,h).
        label_rect = QRectF(0, drop, w, h - drop)
        p.drawText(label_rect, Qt.AlignCenter, self.cfg.label)

        # ---- lock indicator (small icon top-right corner) ----
        if self.cfg.locked:
            p.setPen(QPen(QColor(255, 200, 80, 200), 2))
            p.setBrush(Qt.NoBrush)
            lx, ly = w - 14, 4
            p.drawRoundedRect(QRectF(lx, ly, 10, 8), 2, 2)
            p.drawArc(QRectF(lx + 2, ly - 2, 6, 6), 0, 180 * 16)

        p.end()

    # ---- surface fill (themed; genuine frost for glass blur_hint) ----
    def _draw_surface(self, p: QPainter, kstyle, st, rect: QRectF, factor: float):
        if kstyle.style in ("3d", "glass"):
            grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
            grad.setColorAt(0.0, QColor(st.top))
            grad.setColorAt(1.0, QColor(st.bottom))
            p.setBrush(QBrush(grad))
        else:
            sf = QColor(st.top)
            p.setBrush(QBrush(sf))
        p.setPen(Qt.NoPen)
        r = min(int(rect.width()), int(rect.height())) * 0.5
        p.drawRoundedRect(rect, r, r)
        # Frosted glass: blur the screen content behind the cap.
        if kstyle.style == "glass" and self._theme_blur_hint() > 0:
            self._frost(p, rect)

    def _theme_blur_hint(self) -> float:
        try:
            return float(get_theme(self._theme_name).effects.blur_hint)
        except Exception:
            return 0.0

    def _frost(self, p: QPainter, rect: QRectF):
        """Frosted-glass blur of the desktop content behind this cap.

        Grabs the screen pixels under the widget, downscales/upscales for a
        cheap blur, and composites at partial opacity so glass caps read as
        genuinely frosted (not a flat tint).

        The grab is throttled: grabbing (synchronous compositor readback +
        2 image rescales) on EVERY 60fps paint was the cause of glass themes
        stuttering. We keep a per-widget cache and only re-grab when the cap
        has moved/resized or ~200ms has passed, reusing the cached blur between
        frames.
        """
        screen = QApplication.instance().primaryScreen()
        if screen is None:
            return
        dpr = screen.devicePixelRatio()
        g = self.mapToGlobal(rect.topLeft().toPoint())
        sx = int(g.x() * dpr)
        sy = int(g.y() * dpr)
        pw = max(1, int(rect.width()))
        ph = max(1, int(rect.height()))
        now = time.monotonic()
        key = (sx, sy, pw, ph, self.width(), self.height(), dpr)
        if (
            self._frost_cache is not None
            and self._frost_key == key
            and now - self._frost_ts < 0.2
        ):
            blurred = self._frost_cache
        else:
            shot = screen.grabWindow(0, sx, sy, int(pw * dpr), int(ph * dpr))
            if shot.isNull():
                return
            img = shot.toImage()
            small = img.scaled(max(1, pw // 6), max(1, ph // 6),
                               Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            blurred = small.scaled(pw, ph, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self._frost_cache = blurred
            self._frost_key = key
            self._frost_ts = now
        # drawImage requires a QImage, NOT a QPixmap — passing a pixmap here
        # raised a TypeError on every glass-theme frame and segfaulted the app.
        p.save()
        p.setClipRect(rect)
        p.setOpacity(0.6)
        p.drawImage(rect.toRect(), blurred)
        p.restore()

    # ---- hover/press feedback ----
    def enterEvent(self, ev):
        self._hover = True
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hover = False
        self.update()
        super().leaveEvent(ev)

    # ---- drag ----
    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton and self.draggable:
            self._show_context_menu(ev)
            return
        if self.draggable and not self.cfg.locked:
            self._drag_pos = ev.globalPosition().toPoint()
            self._drag_origin = self.geometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self.draggable and not self.cfg.locked and self._drag_pos is not None:
            delta = ev.globalPosition().toPoint() - self._drag_pos
            self.move(self._drag_origin + delta)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None
        if self.draggable:
            ev.accept()

    # ---- context menu ----
    def _show_context_menu(self, ev):
        menu = QMenu(self)

        # lock / unlock
        if self.cfg.locked:
            act_lock = menu.addAction("Unlock")
        else:
            act_lock = menu.addAction("Lock")

        # resize
        act_resize = menu.addAction("Resize...")

        menu.addSeparator()

        # delete
        act_del = menu.addAction("Delete")

        action = menu.exec(ev.globalPos())
        if action is None:
            return

        if action == act_lock:
            self.cfg.locked = not self.cfg.locked
            self.update()
        elif action == act_resize:
            self._resize_dialog()
        elif action == act_del:
            # tell overlay to remove us
            self.parent()._remove_key(self.cfg.key)

    def _resize_dialog(self):
        sizes_str = " x ".join(str(s) for s in _SIZE_PRESETS)
        text, ok = QInputDialog.getInt(
            self, "Resize Key", f"Size (px): presets: {sizes_str}", self.cfg.size, 32, 200
        )
        if ok:
            self.cfg.size = text
            self.setFixedSize(text, text)
            self.update()
