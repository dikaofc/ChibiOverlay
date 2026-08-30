"""Settings studio: a modern sidebar-navigated, live-preview settings UI.

Built on FramelessWindow (custom title bar with min/max/close + resize).
Layout is a sidebar + scrollable content panel with a persistent bottom save
bar — a small "character customization studio", not a default Python dialog.

Pages: General, Character, Keyboard, Mouse, Appearance, Profiles, Advanced.
Every control below is wired to a real behavior — there is no display-only
("pajangan") control. Changes apply live to the overlay; Save persists to the
profile. The content panel scrolls so nothing is ever clipped at small sizes.
"""
from __future__ import annotations

import os
from collections import deque
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLabel, QLineEdit,
    QCheckBox, QSlider, QListWidget, QListWidgetItem, QSpinBox, QWidget, QFrame,
    QStackedWidget, QAbstractButton, QButtonGroup, QGridLayout,
    QScrollArea, QMessageBox, QKeySequenceEdit, QFileDialog,
)

from .models import KeyConfig, SUGGESTED_KEYS
from . import config as cfg_mod
from .overlay_window import OverlayWindow
from .frameless import FramelessWindow
from .themes import get_key_theme, get_theme, theme_names, contrast_color
from .characters import CHARACTERS, character_names
from .key_widget import KeyWidget as kw
from .chibi_widget import ChibiWidget
from . import platform_win


# ---- design tokens ----
TOK = {
    "bg":       "#111318",
    "sidebar":  "#15171e",
    "card":     "#181a22",
    "card_alt": "#1c1e28",
    "text":     "#e2e4ea",
    "secondary": "#6b6f7e",
    "muted":    "#454856",
    "accent":   "#c084fc",
    "accent2":  "#a78bfa",
    "accent_soft": "#ddd6fe",
    "border":   "#252830",
    "danger":   "#f87171",
    "success":  "#4ade80",
}

def _q(size: int, s: float) -> int:
    """Scale a base font size by the responsive scale factor."""
    return max(8, int(size * s))


def _build_qss(s: float) -> str:
    """Build the settings QSS with font sizes scaled by `s` (responsive)."""
    return f"""
* {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
QWidget {{ color: {TOK['text']}; background: transparent; }}

/* ---- Labels ---- */
QLabel {{ background: transparent; color: {TOK['text']}; }}
QLabel[role="title"] {{ color: {TOK['text']}; font-size: {_q(18, s)}px; font-weight: 700; letter-spacing: -0.3px; }}
QLabel[role="page"] {{ color: {TOK['text']}; font-size: {_q(22, s)}px; font-weight: 800; letter-spacing: -0.5px; }}
QLabel[role="desc"] {{ color: {TOK['secondary']}; font-size: {_q(12, s)}px; font-weight: 400; }}
QLabel[role="section"] {{ color: {TOK['secondary']}; font-size: {_q(11, s)}px; font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase; }}
QLabel[role="hint"] {{ color: {TOK['muted']}; font-size: {_q(11, s)}px; font-style: italic; }}

/* ---- Sidebar ---- */
QWidget#Sidebar {{ background: {TOK['sidebar']}; border-right: 1px solid {TOK['border']}; }}

/* ---- Cards ---- */
QFrame[card="true"] {{
    background: {TOK['card']}; border: 1px solid {TOK['border']};
    border-radius: 8px;
}}

/* ---- Buttons ---- */
QPushButton {{
    background: {TOK['card']}; color: {TOK['text']};
    border: 1px solid {TOK['border']}; border-radius: 6px;
    padding: 7px 14px; font-weight: 500; font-size: {_q(13, s)}px;
}}
QPushButton:hover {{ background: {TOK['card_alt']}; border-color: {TOK['muted']}; }}
QPushButton:pressed {{ background: {TOK['border']}; }}
QPushButton:checked {{ background: {TOK['accent']}; border-color: {TOK['accent']}; color: #fff; font-weight: 600; }}
QPushButton[pill="true"] {{ border-radius: 20px; padding: 8px 20px; }}
QPushButton[accent="true"] {{
    background: {TOK['accent']}; border: none; color: #fff; font-weight: 600;
}}
QPushButton[accent="true"]:hover {{ background: {TOK['accent2']}; }}
QPushButton[ghost="true"] {{ background: transparent; border: 1px solid {TOK['border']}; color: {TOK['secondary']}; }}
QPushButton[ghost="true"]:hover {{ color: {TOK['text']}; border-color: {TOK['muted']}; }}

/* ---- Inputs ---- */
QLineEdit, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {{
    background: {TOK['bg']}; color: {TOK['text']};
    border: 1px solid {TOK['border']}; border-radius: 6px;
    padding: 6px 10px; selection-background-color: {TOK['accent']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {TOK['accent']}; }}
QKeySequenceEdit::clearButton {{ background: transparent; border: none; }}

/* ---- Checkbox ---- */
QCheckBox {{ color: {TOK['text']}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border-radius: 4px;
    border: 2px solid {TOK['border']}; background: {TOK['bg']};
}}
QCheckBox::indicator:checked {{ background: {TOK['accent']}; border-color: {TOK['accent']}; }}
QCheckBox::indicator:hover {{ border-color: {TOK['muted']}; }}

/* ---- Slider ---- */
QSlider::groove:horizontal {{
    height: 4px; background: {TOK['border']}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 16px; height: 16px; margin: -6px 0;
    border-radius: 8px; background: {TOK['accent']};
    border: 2px solid {TOK['bg']};
}}
QSlider::handle:horizontal:hover {{ background: {TOK['accent2']}; }}
QSlider::sub-page:horizontal {{ background: {TOK['accent']}; border-radius: 2px; }}

/* ---- List ---- */
QListWidget {{
    background: {TOK['bg']}; border: 1px solid {TOK['border']};
    border-radius: 6px; color: {TOK['text']}; padding: 4px;
    font-size: {_q(13, s)}px;
}}
QListWidget::item {{ padding: 6px 8px; border-radius: 4px; margin: 1px 2px; }}
QListWidget::item:selected {{ background: {TOK['accent']}; color: #fff; }}
QListWidget::item:hover {{ background: {TOK['card_alt']}; }}

/* ---- Scroll ---- */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {TOK['border']}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {TOK['muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

/* ---- Misc ---- */
QStackedWidget {{ background: {TOK['bg']}; }}
QWidget#BottomBar {{ background: {TOK['sidebar']}; border-top: 1px solid {TOK['border']}; }}
QWidget#Content {{ background: {TOK['bg']}; }}
QGroupBox {{ border: 1px solid {TOK['border']}; border-radius: 8px; margin-top: 14px; padding-top: 8px; }}
"""


class _ResponsiveGrid(QWidget):
    """A grid that reflows columns based on available width."""

    def __init__(self, item_w: int = 120, item_h: int = 108, spacing: int = 10, parent=None):
        super().__init__(parent)
        self._item_w = item_w
        self._item_h = item_h
        self._spacing = spacing
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(spacing)
        self._items: list[QWidget] = []

    def add_widget(self, w: QWidget):
        self._items.append(w)
        self._reflow()

    def clear_widgets(self):
        for w in self._items:
            w.setParent(None)
            w.deleteLater()
        self._items.clear()
        # Clear grid layout
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def _reflow(self):
        avail = self.width() - self._grid.contentsMargins().left() - self._grid.contentsMargins().right()
        if avail < 1:
            p = self.parent()
            avail = (p.width() - 60) if p else 600
        cols = max(1, (avail + self._spacing) // (self._item_w + self._spacing))
        # Remove all from grid, re-add
        for i in range(self._grid.count()):
            item = self._grid.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        for i, w in enumerate(self._items):
            self._grid.addWidget(w, i // cols, i % cols)
        rows = (len(self._items) + cols - 1) // cols if self._items else 1
        self.setMinimumHeight(rows * (self._item_h + self._spacing))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reflow()


class _KeyListWidgetItem(QListWidgetItem):
    """A list item with a color swatch and key label."""

    def __init__(self, label: str, key: str, color: str):
        super().__init__()
        self.key = key
        self.color = color
        self.setData(Qt.UserRole, key)
        # Display: colored indicator + label
        self.setText(f"●  {label}   [{key}]")
        self.setForeground(QBrush(QColor(color)))


# Key colors for the add-key palette
_KEY_COLORS = {
    "w": "#7fd1ff", "a": "#7fd1ff", "s": "#7fd1ff", "d": "#7fd1ff",
    "space": "#ffd27f", "shift": "#c8a6ff", "ctrl": "#c8a6ff", "alt": "#c8a6ff",
    "e": "#9ee57f", "q": "#9ee57f", "r": "#9ee57f", "f": "#9ee57f",
    "mouse_left": "#ff9ecb", "mouse_right": "#ff9ecb",
}


class _AddKeyCard(QAbstractButton):
    """A clickable card to add a key to the overlay."""

    def __init__(self, token: str, label: str, color: str):
        super().__init__()
        self.token = token
        self.label_text = label
        self.color = color
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(80, 52)
        self._hover = False
        self._added = False  # True if already in profile

    def set_added(self, added: bool):
        self._added = added
        self.setEnabled(not added)
        self.update()

    def enterEvent(self, e):
        self._hover = True; self.update()
    def leaveEvent(self, e):
        self._hover = False; self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        # Background
        bg = QColor(TOK["card"])
        if self._added:
            bg = QColor(TOK["bg"])
        elif self._hover:
            bg = QColor("#1e2130")
        p.setBrush(QBrush(bg))
        border = QColor(self.color) if self.isChecked() else (
            QColor(TOK["border"]) if not self._hover else QColor(TOK["secondary"])
        )
        p.setPen(QPen(border, 2 if self.isChecked() else 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)
        # Color dot
        dot = QColor(self.color)
        if self._added:
            dot.setAlpha(60)
        p.setBrush(QBrush(dot))
        p.setPen(Qt.NoPen)
        p.drawEllipse(10, h // 2 - 5, 10, 10)
        # Label
        fg = QColor(TOK["secondary"]) if self._added else QColor(TOK["text"])
        p.setPen(QPen(fg))
        s = getattr(SettingsWindow, "_scale", 1.0)
        p.setFont(QFont("Segoe UI", max(9, int(12 * s)), QFont.Bold))
        p.drawText(QRectF(26, 0, w - 30, h), Qt.AlignVCenter | Qt.AlignLeft, self.label_text)
        p.end()


class _NavButton(QAbstractButton):
    """Sidebar nav: left accent bar + label. Clean, not pill-shaped."""

    def __init__(self, label: str, page: str):
        super().__init__()
        self.label = label
        self.page = page
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        self._hover = False

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        sel = self.isChecked()

        # Subtle hover/selected background
        if sel:
            p.setBrush(QBrush(QColor(TOK["accent"] + "18")))  # 10% opacity accent
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(4, 2, w - 8, h - 4, 6, 6)
        elif self._hover:
            p.setBrush(QBrush(QColor("#ffffff08")))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(4, 2, w - 8, h - 4, 6, 6)

        # Left accent bar
        if sel:
            p.setBrush(QBrush(QColor(TOK["accent"])))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 6, 3, h - 12, 2, 2)

        # Label
        fg = QColor(TOK["accent"] if sel else (TOK["text"] if self._hover else TOK["secondary"]))
        p.setPen(QPen(fg))
        s = getattr(SettingsWindow, "_scale", 1.0)
        weight = QFont.DemiBold if sel else QFont.Normal
        p.setFont(QFont("Segoe UI", max(9, int(12.5 * s)), weight))
        p.drawText(QRectF(14, 0, w - 20, h), Qt.AlignVCenter | Qt.AlignLeft, self.label)
        p.end()

    def enterEvent(self, e):
        self._hover = True; self.update()
    def leaveEvent(self, e):
        self._hover = False; self.update()


class _PickCard(QAbstractButton):
    """Clickable preview card for a keycap theme or chibi character."""

    def __init__(self, kind: str, name: str):
        super().__init__()
        self.kind = kind
        self.name = name
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(120, 108)
        self._hover = False

    def enterEvent(self, e):
        self._hover = True; self.update()
    def leaveEvent(self, e):
        self._hover = False; self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        sel = self.isChecked()
        if self.kind == "key":
            data = get_key_theme(self.name); title = data.get("name", self.name)
        else:
            data = CHARACTERS[self.name]; title = data["name"]
        p.setBrush(QBrush(QColor(TOK["card"])))
        p.setPen(QPen(QColor(TOK["accent"] if sel else (TOK["border"] if not self._hover else TOK["secondary"])), 2 if sel else 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)
        if self.kind == "key":
            self._draw_key(p, w, h, data)
        else:
            self._draw_char(p, data)
        p.setPen(QPen(QColor(TOK["text"])))
        s = getattr(SettingsWindow, "_scale", 1.0)
        p.setFont(QFont("Segoe UI", max(8, int(10 * s)), QFont.Bold))
        p.drawText(QRectF(0, h - 22, w, 18), Qt.AlignCenter, title)

    def _draw_key(self, p, w, h, d):
        x, y, s = 14, 12, 40
        theme = get_theme(self.name)
        st = theme.key.normal
        # backdrop so even translucent glass caps stay visible on the dark card
        p.setBrush(QBrush(QColor("#2a2d3a")))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(x - 3, y - 3, s + 6, s + 6, 10, 10)
        bg = QColor(st.bg if st.bg != "transparent" else theme.panel.surface)
        bg.setAlpha(255 if st.bg != "transparent" else 200)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(QColor(st.border).lighter(140), 2))
        p.drawRoundedRect(x, y, s, s, min(12, theme.key.radius), min(12, theme.key.radius))
        p.setBrush(QBrush(QColor(st.top)))
        p.setPen(QPen(QColor(st.border).lighter(160), 1))
        p.drawRoundedRect(x + 4, y + 4, s - 8, s - 8, 6, 6)
        p.setPen(QPen(QColor(st.label)))
        p.setFont(QFont("Segoe UI", 12, QFont.Bold))
        p.drawText(QRectF(x, y, s, s), Qt.AlignCenter, "A")

    def _draw_char(self, p, d):
        cx, cy = self.width() / 2, 38
        light = QColor(d["light"]); dark = QColor(d["dark"])
        p.setBrush(QBrush(QColor("#2a2d3a"))); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy + 6), 26, 24)
        p.setBrush(QBrush(dark)); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx - 16, cy - 18), 8, 8)
        p.drawEllipse(QPointF(cx + 16, cy - 18), 8, 8)
        p.setBrush(QBrush(light))
        p.drawEllipse(QPointF(cx, cy + 6), 21, 19)
        p.setBrush(QBrush(QColor(d["pupil"])))
        p.drawEllipse(QPointF(cx - 8, cy + 4), 3, 3)
        p.drawEllipse(QPointF(cx + 8, cy + 4), 3, 3)


class SettingsWindow(FramelessWindow):
    _scale = 1.0  # responsive text scale, updated on resize

    # Predefined per-game key setups (real; loadable).
    GAME_PROFILES = {
        "Valorant": [
            ("w", "W", 120, 0, 64, "#7fd1ff"), ("a", "A", 40, 72, 64, "#7fd1ff"),
            ("s", "S", 120, 72, 64, "#7fd1ff"), ("d", "D", 200, 72, 64, "#7fd1ff"),
            ("space", "SPACE", 120, 152, 64, "#ffd27f"), ("shift", "SHIFT", 300, 72, 64, "#c8a6ff"),
            ("ctrl", "CTRL", 300, 152, 64, "#c8a6ff"),
        ],
        "Minecraft": [
            ("w", "W", 120, 0, 64, "#7fd1ff"), ("a", "A", 40, 72, 64, "#7fd1ff"),
            ("s", "S", 120, 72, 64, "#7fd1ff"), ("d", "D", 200, 72, 64, "#7fd1ff"),
            ("space", "SPACE", 120, 152, 64, "#ffd27f"), ("e", "E", 300, 72, 64, "#9ee57f"),
        ],
        "Genshin": [
            ("w", "W", 120, 0, 64, "#7fd1ff"), ("a", "A", 40, 72, 64, "#7fd1ff"),
            ("s", "S", 120, 72, 64, "#7fd1ff"), ("d", "D", 200, 72, 64, "#7fd1ff"),
            ("q", "Q", 300, 0, 64, "#9ee57f"), ("e", "E", 300, 72, 64, "#9ee57f"),
            ("r", "R", 300, 152, 64, "#9ee57f"), ("f", "F", 380, 72, 64, "#9ee57f"),
        ],
    }

    def __init__(self, overlay: OverlayWindow, parent: Optional = None):
        from .icon import generate_icon
        super().__init__("Chibi Overlay", icon=generate_icon())
        self.overlay = overlay
        self.profile = overlay.profile
        self.setMinimumSize(860, 620)
        self.resize(980, 720)
        self.setStyleSheet(_build_qss(1.0))
        self._build()

    def resizeEvent(self, e):
        s = max(0.85, min(1.35, self.width() / 980.0))
        SettingsWindow._scale = s
        self.setStyleSheet(_build_qss(s))
        super().resizeEvent(e)

    # ============================================================== build
    def _build(self):
        content = QWidget(); content.setObjectName("Content")
        root = QHBoxLayout(content); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ---- sidebar ----
        side = QWidget(); side.setObjectName("Sidebar"); side.setFixedWidth(180)
        sv = QVBoxLayout(side); sv.setContentsMargins(12, 16, 12, 16); sv.setSpacing(2)
        logo = QLabel("CHIBI OVERLAY")
        logo.setStyleSheet(f"color: {TOK['accent']}; font-size: 13px; font-weight: 800; letter-spacing: 2px; padding-bottom: 4px;")
        sv.addWidget(logo)
        # Separator line under logo
        sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet(f"background: {TOK['border']}; margin: 4px 0 8px 0;")
        sv.addWidget(sep)
        self._nav = QButtonGroup(self)
        self._nav.setExclusive(True)
        nav_items = ["general", "character", "keyboard", "mouse", "appearance", "mouse_overlay", "gamepad", "websocket", "profiles", "presets", "advanced"]
        for key in nav_items:
            b = _NavButton(key.capitalize(), key)
            self._nav.addButton(b)
            sv.addWidget(b)
            b.clicked.connect(lambda _=False, k=key: self._goto(k))
        sv.addStretch()
        root.addWidget(side)

        # ---- page stack (scrollable) ----
        self._stack = QStackedWidget()
        self._pages = {}
        for key in nav_items:
            page = self._make_page(key)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self._pages[key] = scroll
            self._stack.addWidget(scroll)
        root.addWidget(self._stack, 1)

        # ---- bottom bar ----
        bottom = QWidget(); bottom.setObjectName("BottomBar")
        bottom.setFixedHeight(52)
        bl = QHBoxLayout(bottom); bl.setContentsMargins(20, 0, 20, 0)
        self._status = QLabel("  overlay active")
        self._status.setStyleSheet(f"color:{TOK['success']}; font-size:{_q(11, SettingsWindow._scale)}px; font-weight:500;")
        bl.addWidget(self._status)
        bl.addStretch()
        discard = QPushButton("Discard"); discard.setProperty("ghost", True)
        discard.clicked.connect(self._discard)
        save = QPushButton("Save"); save.setProperty("accent", True)
        save.clicked.connect(self._save)
        bl.addWidget(discard)
        bl.addWidget(save)

        top_area = QWidget(); top_area.setObjectName("Content")
        top_area.setLayout(root)
        content_body = QWidget()
        outer = QVBoxLayout(content_body); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        outer.addWidget(top_area, 1)
        outer.addWidget(bottom)
        self.setContent(content_body)

        self._goto("character")
        self._nav.buttons()[1].setChecked(True)
        self._mark_dirty(False)

    def _goto(self, key):
        if key in self._pages:
            self._stack.setCurrentWidget(self._pages[key])
            for b in self._nav.buttons():
                if b.page == key:
                    b.setChecked(True)

    # ============================================================== pages
    def _make_page(self, key):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24); v.setSpacing(16)
        builders = {
            "general": self._build_general,
            "character": self._build_character,
            "keyboard": self._build_keyboard,
            "mouse": self._build_mouse,
            "appearance": self._build_appearance,
            "mouse_overlay": self._build_mouse_overlay,
            "gamepad": self._build_gamepad,
            "websocket": self._build_websocket,
            "profiles": self._build_profiles,
            "presets": self._build_presets,
            "advanced": self._build_advanced,
        }
        builder = builders.get(key)
        if builder:
            builder(v)
        v.addStretch()
        return page

    def _page_title(self, v, title, desc):
        t = QLabel(title); t.setProperty("role", "page")
        d = QLabel(desc); d.setProperty("role", "desc")
        v.addWidget(t); v.addSpacing(2); v.addWidget(d); v.addSpacing(12)

    # ---- general (every control real) ----
    def _build_general(self, v):
        self._page_title(v, "General", "Overlay behavior and startup")
        c = self._card()
        f = QFormLayout(c); f.setContentsMargins(20, 18, 20, 18); f.setSpacing(14)
        self.cb_enabled = self._check("Enable overlay", self.profile.enabled, self._toggle_enabled)
        f.addRow(self.cb_enabled)
        self.cb_aot = self._check("Always on top", self.profile.always_on_top, self._toggle_always_on_top)
        f.addRow(self.cb_aot)
        self.cb_startup = self._check(
            "Start with Windows", self.profile.start_with_windows, self._toggle_startup
        )
        f.addRow(self.cb_startup)
        self.cb_min = self._check("Minimize to tray", self.profile.minimize_to_tray)
        f.addRow(self.cb_min)
        v.addWidget(c)

        c2 = self._card()
        f2 = QFormLayout(c2); f2.setContentsMargins(20, 18, 20, 18); f2.setSpacing(14)
        self._hotkey_edit = QKeySequenceEdit()
        self._hotkey_edit.setKeySequence(self.profile.toggle_hotkey)
        self._hotkey_edit.keySequenceChanged.connect(self._on_hotkey)
        f2.addRow("Open settings", self._hotkey_edit)
        hint = QLabel("Tip: open Settings anytime with Ctrl+Alt+S, or right-click the tray icon.")
        hint.setProperty("role", "hint")
        f2.addRow(hint)
        v.addWidget(c2)

    # ---- character (real follow controls; no dup with Mouse) ----
    def _build_character(self, v):
        self._page_title(v, "Character", "Pick and customize your companion — live")
        top = QHBoxLayout(); top.setSpacing(16)

        prev_card = QFrame(); prev_card.setProperty("card", True)
        pl = QVBoxLayout(prev_card); pl.setContentsMargins(12, 12, 12, 8)
        self._preview = ChibiWidget(self.profile.chibi, prev_card, self.profile.chibi_theme)
        self._preview.setFixedSize(240, 240)
        self._preview.set_mouse_global(400, 200)
        pl.addWidget(self._preview, 0, Qt.AlignCenter)
        cap = QLabel("▸ live preview — moves with your mouse")
        cap.setProperty("role", "hint")
        pl.addWidget(cap, 0, Qt.AlignCenter)
        top.addWidget(prev_card, 0)

        rc = self._card()
        rf = QFormLayout(rc); rf.setContentsMargins(20, 18, 20, 18); rf.setSpacing(12)
        self.cb_follow = self._check("Reach for the mouse (master)", self.profile.chibi.mouse_follow, self._toggle_master_follow)
        rf.addRow(self.cb_follow)
        self.cb_head = self._check("Head follows mouse", self.profile.chibi.head_follow, self._toggle_head_follow)
        rf.addRow(self.cb_head)
        self.cb_eye = self._check("Eyes follow mouse", self.profile.chibi.eye_follow, self._toggle_eye_follow)
        rf.addRow(self.cb_eye)
        self.cb_arm = self._check("Body leans toward mouse", self.profile.chibi.arm_follow, self._toggle_arm_follow)
        rf.addRow(self.cb_arm)
        self.sl_follow = self._slider(int(self.profile.chibi.follow_strength * 100), conn=self._apply_follow)
        self.sl_smooth = self._slider(int(self.profile.chibi.smoothing * 100), conn=self._apply_smoothing)
        self.sl_eye = self._slider(int(self.profile.chibi.eye_movement * 100), conn=self._apply_eye_movement)
        self.sl_size = self._slider(int(self.profile.chibi.size / 600.0 * 100), conn=self._apply_chibi_size)
        rf.addRow("Reach strength", self.sl_follow)
        rf.addRow("Smoothing", self.sl_smooth)
        rf.addRow("Eye movement", self.sl_eye)
        rf.addRow("Size", self.sl_size)
        top.addWidget(rc, 1)
        v.addLayout(top)

        c = self._card()
        cl = QVBoxLayout(c); cl.setContentsMargins(18, 14, 18, 14); cl.setSpacing(8)
        cl.addWidget(self._section("Choose your companion"))
        grid = QGridLayout(); grid.setSpacing(10)
        self._char_cards: list[_PickCard] = []
        # Exclusive group -> only one companion selected at a time.
        self._char_group = QButtonGroup(self)
        self._char_group.setExclusive(True)
        for i, name in enumerate(character_names()):
            card = _PickCard("chibi", name)
            card.setChecked((self.profile.chibi_theme or "cat") == name)
            card.clicked.connect(lambda _=False, c=card: self._on_character(c))
            self._char_group.addButton(card)
            self._char_cards.append(card)
            grid.addWidget(card, i // 6, i % 6)
        cl.addLayout(grid)
        v.addWidget(c)

        mc = self._card()
        ml = QVBoxLayout(mc); ml.setContentsMargins(18, 14, 18, 14); ml.setSpacing(8)
        ml.addWidget(self._section("Custom media (gif / png / jpg / mp4)"))
        prow = QHBoxLayout(); prow.setSpacing(8)
        self._media_pick = QPushButton("Choose file…")
        self._media_pick.clicked.connect(self._on_pick_media)
        self._media_clear = QPushButton("Clear")
        self._media_clear.clicked.connect(self._on_clear_media)
        self._media_clear.setFixedWidth(70)
        self._media_label = QLabel()
        self._media_label.setProperty("role", "hint")
        self._media_label.setWordWrap(True)
        prow.addWidget(self._media_pick)
        prow.addWidget(self._media_clear)
        ml.addLayout(prow)
        ml.addWidget(self._media_label)
        self._update_media_label()
        v.addWidget(mc)

    # ---- keyboard (real key theme + add/remove) ----
    def _build_keyboard(self, v):
        self._page_title(v, "Keyboard", "Which keys light up on the overlay")

        # -- keycap theme --
        c = self._card()
        cl = QVBoxLayout(c); cl.setContentsMargins(18, 14, 18, 14); cl.setSpacing(10)
        cl.addWidget(self._section("Keycap theme"))
        self._key_theme_grid = _ResponsiveGrid(item_w=120, item_h=108, spacing=10)
        self._key_theme_cards: list[_PickCard] = []
        # Exclusive group so only ONE theme is ever selected (a checkable
        # QAbstractButton is NOT exclusive by itself -> otherwise multi-select).
        self._key_theme_group = QButtonGroup(self)
        self._key_theme_group.setExclusive(True)
        for i, name in enumerate(theme_names()):
            card = _PickCard("key", name)
            card.setChecked(self.profile.key_theme == name)
            card.clicked.connect(lambda _=False, c=card: self._on_key_theme(c))
            self._key_theme_group.addButton(card)
            self._key_theme_cards.append(card)
            self._key_theme_grid.add_widget(card)
        cl.addWidget(self._key_theme_grid)
        v.addWidget(c)

        # -- live preview (real KeyWidgets, not a drawing) --
        cp = self._card()
        pv = QVBoxLayout(cp); pv.setContentsMargins(18, 14, 18, 14); pv.setSpacing(8)
        pv.addWidget(self._section("Live preview — real keycaps using this theme"))
        prev_row = QHBoxLayout(); prev_row.setSpacing(18); prev_row.addStretch()
        self._live_previews = {}
        for label, state in (("Normal", "normal"), ("Hover", "hover"), ("Pressed", "pressed")):
            col = QVBoxLayout(); col.setSpacing(4)
            wk = kw(KeyConfig(key="w", label="W"), self, self.profile.key_theme)
            wk.setFixedSize(72, 72)
            if state == "hover":
                wk._hover = True
            elif state == "pressed":
                wk._target = 1.0; wk._pressed = 1.0
            col.addWidget(wk, 0, Qt.AlignCenter)
            cap = QLabel(label); cap.setProperty("role", "hint"); cap.setAlignment(Qt.AlignCenter)
            col.addWidget(cap, 0, Qt.AlignCenter)
            prev_row.addLayout(col)
            self._live_previews[state] = wk
        prev_row.addStretch()
        pv.addLayout(prev_row)
        v.addWidget(cp)

        # -- active keys --
        ce = self._card()
        ev = QVBoxLayout(ce); ev.setContentsMargins(18, 14, 18, 14); ev.setSpacing(10)

        # Header with count badge
        header_row = QHBoxLayout(); header_row.setSpacing(8)
        sec = self._section("Active keys")
        header_row.addWidget(sec)
        self._key_count_badge = QLabel(f"{len(self.profile.keys)}")
        self._key_count_badge.setAlignment(Qt.AlignCenter)
        self._key_count_badge.setFixedSize(24, 24)
        self._key_count_badge.setStyleSheet(
            f"background:{TOK['accent']}; color:#0f1015; border-radius:12px; font-weight:700; font-size:11px;"
        )
        header_row.addWidget(self._key_count_badge)
        header_row.addStretch()
        ev.addLayout(header_row)

        # Empty state hint (created before _refresh_keys so _update_empty_state
        # can reference it during the first build).
        self._empty_hint = QLabel("No keys added yet. Click a key below to add it.")
        self._empty_hint.setProperty("role", "hint")
        self._empty_hint.setAlignment(Qt.AlignCenter)

        # Key list (expands, no fixed height)
        self.key_list = QListWidget()
        self.key_list.setMinimumHeight(100)
        self.key_list.setMaximumHeight(220)
        ev.addWidget(self.key_list, 1)
        ev.addWidget(self._empty_hint)

        # Remove button
        row = QHBoxLayout(); row.setSpacing(8)
        delb = QPushButton("− Remove Selected")
        delb.clicked.connect(self._remove_key)
        delb.setFixedHeight(34)
        row.addWidget(delb)
        row.addStretch()
        ev.addLayout(row)

        ev.addWidget(self._section("Add keys"))

        # Search field
        self._key_search = QLineEdit()
        self._key_search.setPlaceholderText("Search keys...")
        self._key_search.setClearButtonEnabled(True)
        self._key_search.textChanged.connect(self._filter_keys)
        ev.addWidget(self._key_search)

        # Suggested keys in responsive grid (all 14, scrollable)
        key_scroll = QScrollArea()
        key_scroll.setWidgetResizable(True)
        key_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        key_scroll.setMaximumHeight(160)
        self._add_key_grid = _ResponsiveGrid(item_w=80, item_h=52, spacing=6)
        self._add_key_cards: dict[str, _AddKeyCard] = {}
        for s in SUGGESTED_KEYS:
            card = _AddKeyCard(s["match"], s["label"], _KEY_COLORS.get(s["match"], "#7fd1ff"))
            card.set_added(any(k.key == s["match"] for k in self.profile.keys))
            card.clicked.connect(lambda _=False, t=s["match"]: self._add_key(t))
            self._add_key_cards[s["match"]] = card
            self._add_key_grid.add_widget(card)
        key_scroll.setWidget(self._add_key_grid)
        ev.addWidget(key_scroll, 1)

        v.addWidget(ce)

        # Populate the list + cards now that every widget they read
        # (_key_count_badge, _empty_hint, _add_key_cards) is created.
        self._refresh_keys()

    # ---- mouse (real reactivity: master + dead zone + sensitivity) ----
    def _build_mouse(self, v):
        self._page_title(v, "Mouse", "How the companion reacts to your cursor")
        c = self._card()
        f = QFormLayout(c); f.setContentsMargins(20, 18, 20, 18); f.setSpacing(12)
        self.cb_mtrack = self._check("Mouse tracking", self.profile.chibi.mouse_follow, self._toggle_master_follow)
        f.addRow(self.cb_mtrack)
        self.sl_dead = self._slider(self.profile.chibi.dead_zone, lo=0, hi=40, conn=self._apply_dead_zone)
        self.sl_sens = self._slider(int(self.profile.chibi.follow_strength * 100), conn=self._apply_follow)
        f.addRow("Dead zone (px)", self.sl_dead)
        f.addRow("Reach sensitivity", self.sl_sens)
        hint = QLabel("Dead zone hides tiny cursor jitter; sensitivity scales how far the companion leans.")
        hint.setProperty("role", "hint")
        f.addRow(hint)
        v.addWidget(c)

    # ---- appearance (real: opacity + key visuals) ----
    def _build_appearance(self, v):
        self._page_title(v, "Appearance", "Global visual tuning")
        c = self._card()
        f = QFormLayout(c); f.setContentsMargins(20, 18, 20, 18); f.setSpacing(14)
        self.sl_opacity = self._slider(int(self.profile.opacity * 100), conn=self._apply_opacity)
        self.sl_kscale = self._slider(int(self.profile.key_scale * 100), conn=self._apply_key_scale)
        self.sl_kop = self._slider(int(self.profile.key_opacity * 100), conn=self._apply_key_opacity)
        self.sl_krad = self._slider(self.profile.key_radius, lo=0, hi=40, conn=self._apply_key_radius)
        f.addRow("Overlay opacity", self.sl_opacity)
        f.addRow("Key size", self.sl_kscale)
        f.addRow("Key opacity", self.sl_kop)
        f.addRow("Key corner radius", self.sl_krad)
        v.addWidget(c)

    # ---- profiles (real load + save-as + delete) ----
    def _build_profiles(self, v):
        self._page_title(v, "Profiles", "Per-game key setups")
        c = self._card()
        cl = QVBoxLayout(c); cl.setContentsMargins(18, 14, 18, 14); cl.setSpacing(8)
        cl.addWidget(self._section("Built-in layouts"))
        for name in self.GAME_PROFILES:
            row = QFrame(); row.setProperty("card", True)
            r = QHBoxLayout(row); r.setContentsMargins(16, 10, 16, 10)
            rl = QVBoxLayout(); rl.setSpacing(2)
            n = QLabel(name); n.setProperty("role", "section")
            d = QLabel(", ".join(tok.upper() for tok, *_ in self.GAME_PROFILES[name]))
            d.setProperty("role", "hint")
            rl.addWidget(n); rl.addWidget(d)
            r.addLayout(rl, 1)
            load = QPushButton("Load"); load.setProperty("accent", True)
            load.clicked.connect(lambda _=False, nm=name: self._load_game_profile(nm))
            r.addWidget(load)
            cl.addWidget(row)
        v.addWidget(c)

        ce = self._card()
        ev = QVBoxLayout(ce); ev.setContentsMargins(18, 14, 18, 14); ev.setSpacing(8)
        ev.addWidget(self._section("Current layout"))
        row = QHBoxLayout()
        save_new = QPushButton("+ Save Current As New"); save_new.setProperty("ghost", True)
        save_new.clicked.connect(self._save_new_profile)
        del_cur = QPushButton("Delete Saved Profile"); del_cur.setProperty("ghost", True)
        del_cur.clicked.connect(self._delete_profile)
        row.addWidget(save_new)
        row.addWidget(del_cur)
        ev.addLayout(row)
        v.addWidget(ce)

    # ---- advanced (real: fps + reset; debug removed as no-op) ----
    def _build_advanced(self, v):
        self._page_title(v, "Advanced", "Performance & diagnostics")
        c = self._card()
        f = QFormLayout(c); f.setContentsMargins(20, 18, 20, 18); f.setSpacing(14)
        self.sp_fps = QSpinBox(); self.sp_fps.setRange(20, 240); self.sp_fps.setValue(60)
        self.sp_fps.valueChanged.connect(self._apply_fps)
        f.addRow("Animation FPS", self.sp_fps)
        v.addWidget(c)
        c2 = self._card()
        f2 = QFormLayout(c2); f2.setContentsMargins(20, 18, 20, 18); f2.setSpacing(12)
        danger = QPushButton("Reset All Settings")
        danger.setStyleSheet(f"background:{TOK['card']}; color:{TOK['danger']}; border:1px solid {TOK['danger']}; border-radius:9px; padding:8px 14px;")
        danger.clicked.connect(self._reset_layout)
        f2.addRow("Danger zone", danger)
        v.addWidget(c2)

    # ---- mouse overlay (cursor movement visualization) ----
    def _build_mouse_overlay(self, v):
        self._page_title(v, "Mouse Overlay", "Cursor movement visualization — trail, direction, deadzone")

        # Enable toggle
        c = self._card()
        f = QFormLayout(c); f.setContentsMargins(20, 18, 20, 18); f.setSpacing(14)
        self.cb_mouse_ov = self._check("Show mouse overlay", False, self._toggle_mouse_overlay)
        f.addRow(self.cb_mouse_ov)
        v.addWidget(c)

        # Visual settings
        c2 = self._card()
        f2 = QFormLayout(c2); f2.setContentsMargins(20, 18, 20, 18); f2.setSpacing(12)
        self.sl_mo_sens = self._slider(100, lo=10, hi=300, conn=self._apply_mouse_sensitivity)
        self.sl_mo_trail = self._slider(20, lo=5, hi=50, conn=self._apply_mouse_trail)
        self.sl_mo_deadzone = self._slider(50, lo=10, hi=200, conn=self._apply_mouse_deadzone)
        f2.addRow("Sensitivity", self.sl_mo_sens)
        f2.addRow("Trail length", self.sl_mo_trail)
        f2.addRow("Deadzone radius", self.sl_mo_deadzone)

        self.cb_mo_trail = self._check("Show trail", True, self._apply_mouse_visual)
        self.cb_mo_arrow = self._check("Show direction arrow", True, self._apply_mouse_visual)
        self.cb_mo_deadzone_show = self._check("Show deadzone circle", True, self._apply_mouse_visual)
        f2.addRow(self.cb_mo_trail)
        f2.addRow(self.cb_mo_arrow)
        f2.addRow(self.cb_mo_deadzone_show)
        v.addWidget(c2)

        # Preview
        cp = self._card()
        pl = QVBoxLayout(cp); pl.setContentsMargins(18, 14, 18, 14); pl.setSpacing(8)
        pl.addWidget(self._section("Preview"))
        from .mouse_overlay import MouseOverlay as MO
        self._mouse_ov_preview = MO()
        self._mouse_ov_preview.setFixedSize(200, 200)
        self._mouse_ov_preview.show()
        pl.addWidget(self._mouse_ov_preview, 0, Qt.AlignCenter)
        v.addWidget(cp)

    # ---- gamepad overlay ----
    def _build_gamepad(self, v):
        self._page_title(v, "Gamepad", "Gamepad button + stick visualization")

        c = self._card()
        f = QFormLayout(c); f.setContentsMargins(20, 18, 20, 18); f.setSpacing(14)
        self.cb_gp_ov = self._check("Show gamepad overlay", False, self._toggle_gamepad_overlay)
        f.addRow(self.cb_gp_ov)
        v.addWidget(c)

        # Preview
        cp = self._card()
        pl = QVBoxLayout(cp); pl.setContentsMargins(18, 14, 18, 14); pl.setSpacing(8)
        pl.addWidget(self._section("Preview"))
        from .gamepad_overlay import GamepadOverlay as GO
        self._gp_preview = GO()
        self._gp_preview.setFixedSize(250, 250)
        self._gp_preview.show()
        pl.addWidget(self._gp_preview, 0, Qt.AlignCenter)
        v.addWidget(cp)

    # ---- websocket server ----
    def _build_websocket(self, v):
        self._page_title(v, "WebSocket", "Stream input data to browser sources / other apps")

        c = self._card()
        f = QFormLayout(c); f.setContentsMargins(20, 18, 20, 18); f.setSpacing(14)
        self.cb_ws = self._check("Enable WebSocket server", False, self._toggle_ws)
        f.addRow(self.cb_ws)

        self.le_ws_host = QLineEdit("0.0.0.0")
        self.sp_ws_port = QSpinBox(); self.sp_ws_port.setRange(1024, 65535); self.sp_ws_port.setValue(16899)
        f.addRow("Host", self.le_ws_host)
        f.addRow("Port", self.sp_ws_port)

        self.cb_ws_kb = self._check("Send keyboard events", True)
        self.cb_ws_ms = self._check("Send mouse events", True)
        self.cb_ws_gp = self._check("Send gamepad events", False)
        f.addRow(self.cb_ws_kb)
        f.addRow(self.cb_ws_ms)
        f.addRow(self.cb_ws_gp)
        v.addWidget(c)

        # Status
        cs = self._card()
        sl = QVBoxLayout(cs); sl.setContentsMargins(18, 14, 18, 14); sl.setSpacing(8)
        self._ws_status = QLabel("Server not running")
        self._ws_status.setProperty("role", "hint")
        sl.addWidget(self._ws_status)
        hint = QLabel("Connect from a browser source: ws://localhost:16899")
        hint.setProperty("role", "hint")
        sl.addWidget(hint)
        v.addWidget(cs)

    # ---- presets (overlay layout presets) ----
    def _build_presets(self, v):
        self._page_title(v, "Presets", "Quick overlay layout configurations")
        from .overlay_config import list_presets, load_preset, BUILTIN_PRESETS

        c = self._card()
        cl = QVBoxLayout(c); cl.setContentsMargins(18, 14, 18, 14); cl.setSpacing(8)
        cl.addWidget(self._section("Built-in presets"))
        for name in list_presets():
            row = QFrame(); row.setProperty("card", True)
            r = QHBoxLayout(row); r.setContentsMargins(16, 10, 16, 10)
            rl = QVBoxLayout(); rl.setSpacing(2)
            n = QLabel(name); n.setProperty("role", "section")
            is_builtin = name in BUILTIN_PRESETS
            d = QLabel("Built-in" if is_builtin else "Custom")
            d.setProperty("role", "hint")
            rl.addWidget(n); rl.addWidget(d)
            r.addLayout(rl, 1)
            load = QPushButton("Apply"); load.setProperty("accent", True)
            load.clicked.connect(lambda _=False, nm=name: self._apply_preset(nm))
            r.addWidget(load)
            if not is_builtin:
                delb = QPushButton("Delete"); delb.setProperty("ghost", True)
                delb.clicked.connect(lambda _=False, nm=name: self._delete_preset(nm))
                r.addWidget(delb)
            cl.addWidget(row)
        v.addWidget(c)

    # ============================================================== new overlay handlers
    def _toggle_mouse_overlay(self, checked: bool):
        self.overlay.set_mouse_overlay(checked)
        self._mark_dirty(True)

    def _apply_mouse_sensitivity(self, val: int):
        if self.overlay.mouse_overlay is not None:
            self.overlay.mouse_overlay.cfg.sensitivity = val / 100.0
        self._mark_dirty(True)

    def _apply_mouse_trail(self, val: int):
        if self.overlay.mouse_overlay is not None:
            self.overlay.mouse_overlay.cfg.trail_length = val
            self.overlay.mouse_overlay._trail = deque(maxlen=val)
        self._mark_dirty(True)

    def _apply_mouse_deadzone(self, val: int):
        if self.overlay.mouse_overlay is not None:
            self.overlay.mouse_overlay.cfg.deadzone_radius = val
        self._mark_dirty(True)

    def _apply_mouse_visual(self):
        if self.overlay.mouse_overlay is not None:
            self.overlay.mouse_overlay.cfg.show_trail = self.cb_mo_trail.isChecked()
            self.overlay.mouse_overlay.cfg.show_arrow = self.cb_mo_arrow.isChecked()
            self.overlay.mouse_overlay.cfg.show_deadzone = self.cb_mo_deadzone_show.isChecked()
            self.overlay.mouse_overlay.update()
        self._mark_dirty(True)

    def _toggle_gamepad_overlay(self, checked: bool):
        self.overlay.set_gamepad_overlay(checked)
        self._mark_dirty(True)

    def _toggle_ws(self, checked: bool):
        if checked:
            host = self.le_ws_host.text() or "0.0.0.0"
            port = self.sp_ws_port.value()
            ok = self.overlay.start_ws_server(host, port)
            if ok:
                self._ws_status.setText(f"Running on ws://{host}:{port}")
                self._ws_status.setStyleSheet(f"color:{TOK['success']}; font-weight:500;")
            else:
                self._ws_status.setText("Failed to start — install 'websockets' package")
                self._ws_status.setStyleSheet(f"color:{TOK['danger']}; font-weight:500;")
                self.cb_ws.blockSignals(True)
                self.cb_ws.setChecked(False)
                self.cb_ws.blockSignals(False)
        else:
            self.overlay.stop_ws_server()
            self._ws_status.setText("Server stopped")
            self._ws_status.setStyleSheet(f"color:{TOK['secondary']};")
        self._mark_dirty(True)

    def _apply_preset(self, name: str):
        from .overlay_config import load_preset
        preset = load_preset(name)
        if preset is None:
            QMessageBox.warning(self, "Presets", f"Could not load preset '{name}'.")
            return
        # Apply preset settings
        self.overlay.set_mouse_overlay(
            preset.mouse.enabled, preset.mouse.x, preset.mouse.y, preset.mouse.size
        )
        self.overlay.set_gamepad_overlay(
            preset.gamepad.enabled, preset.gamepad.x, preset.gamepad.y, preset.gamepad.size
        )
        if preset.websocket.enabled:
            self.overlay.start_ws_server(preset.websocket.host, preset.websocket.port)
        else:
            self.overlay.stop_ws_server()
        self._mark_dirty(True)
        QMessageBox.information(self, "Presets", f"Applied preset '{name}'.")

    def _delete_preset(self, name: str):
        from .overlay_config import delete_preset
        if delete_preset(name):
            self._mark_dirty(True)

    # ============================================================== helpers
    def _card(self) -> QFrame:
        c = QFrame(); c.setProperty("card", True); return c

    def _section(self, text) -> QLabel:
        l = QLabel(text); l.setProperty("role", "section"); return l

    def _check(self, label, checked, conn=None) -> QCheckBox:
        cb = QCheckBox(label); cb.setChecked(checked)
        if conn:
            cb.toggled.connect(conn)
        return cb

    def _slider(self, val_0_100: int, lo=0, hi=100, conn=None) -> QSlider:
        s = QSlider(Qt.Horizontal); s.setRange(lo, hi)
        s.setValue(int(val_0_100))
        if conn:
            s.valueChanged.connect(conn)
        return s

    def _spacer(self, h) -> QWidget:
        w = QWidget(); w.setFixedHeight(h); return w

    # ============================================================== toggles (live)
    def _toggle_enabled(self, checked: bool):
        self.overlay.set_enabled(checked)
        self._mark_dirty(True)

    def _toggle_always_on_top(self, checked: bool):
        self.overlay.set_always_on_top(checked)
        self._mark_dirty(True)

    def _toggle_startup(self, checked: bool):
        ok = platform_win.set_start_with_windows(checked)
        if not ok:
            QMessageBox.warning(self, "Autostart", "Could not set Start-with-Windows on this system.")
            self.cb_startup.setChecked(platform_win.get_start_with_windows())
        self._mark_dirty(True)

    def _toggle_master_follow(self, checked: bool):
        self.profile.chibi.mouse_follow = checked
        self.overlay.chibi.cfg.mouse_follow = checked
        # Keep both page checkboxes in sync (General/Mouse share this toggle).
        self.cb_follow.blockSignals(True); self.cb_follow.setChecked(checked); self.cb_follow.blockSignals(False)
        self.cb_mtrack.blockSignals(True); self.cb_mtrack.setChecked(checked); self.cb_mtrack.blockSignals(False)
        self._mark_dirty(True)

    def _toggle_head_follow(self, checked: bool):
        self.profile.chibi.head_follow = checked
        self.overlay.chibi.cfg.head_follow = checked
        self._mark_dirty(True)

    def _toggle_eye_follow(self, checked: bool):
        self.profile.chibi.eye_follow = checked
        self.overlay.chibi.cfg.eye_follow = checked
        self._mark_dirty(True)

    def _toggle_arm_follow(self, checked: bool):
        self.profile.chibi.arm_follow = checked
        self.overlay.chibi.cfg.arm_follow = checked
        self._mark_dirty(True)

    # ============================================================== sliders (live)
    def _apply_follow(self, val: int):
        self.profile.chibi.follow_strength = val / 100.0
        self.overlay.chibi.cfg.follow_strength = val / 100.0
        self.sl_sens.blockSignals(True); self.sl_sens.setValue(val); self.sl_sens.blockSignals(False)
        self._mark_dirty(True)

    def _apply_smoothing(self, val: int):
        self.profile.chibi.smoothing = val / 100.0
        self.overlay.chibi.cfg.smoothing = val / 100.0
        self._mark_dirty(True)

    def _apply_eye_movement(self, val: int):
        self.profile.chibi.eye_movement = val / 100.0
        self.overlay.chibi.cfg.eye_movement = val / 100.0
        self._mark_dirty(True)

    def _apply_chibi_size(self, val: int):
        size = max(40, int(val / 100.0 * 600))
        self.profile.chibi.size = size
        self.overlay.chibi.cfg.size = size
        self.overlay.chibi.set_config(self.profile.chibi)
        self.overlay.chibi.resize(size, size)
        self._mark_dirty(True)

    def _apply_dead_zone(self, val: int):
        self.profile.chibi.dead_zone = val
        self.overlay.chibi.cfg.dead_zone = val
        self._mark_dirty(True)

    def _apply_opacity(self, val: int):
        self.profile.opacity = val / 100.0
        self.overlay.setWindowOpacity(self.profile.opacity)
        self._mark_dirty(True)

    def _apply_key_scale(self, val: int):
        self.overlay.set_key_visuals(val / 100.0, self.profile.key_opacity, self.profile.key_radius)
        self._mark_dirty(True)

    def _apply_key_opacity(self, val: int):
        self.overlay.set_key_visuals(self.profile.key_scale, val / 100.0, self.profile.key_radius)
        self._mark_dirty(True)

    def _apply_key_radius(self, val: int):
        self.overlay.set_key_visuals(self.profile.key_scale, self.profile.key_opacity, val)
        self._mark_dirty(True)

    def _apply_fps(self, val: int):
        self.overlay.set_animation_fps(val)
        self._mark_dirty(True)

    def _on_hotkey(self, seq):
        self.profile.toggle_hotkey = seq.toString()
        self._mark_dirty(True)

    # ============================================================== pickers
    def _on_key_theme(self, btn):
        self.profile.key_theme = btn.name
        for w in self.overlay._key_widgets.values():
            w.set_theme(btn.name)
        for wk in getattr(self, "_live_previews", {}).values():
            wk.set_theme(btn.name)
        self._mark_dirty(True)

    def _on_character(self, btn):
        self.profile.chibi_theme = btn.name
        self.overlay.chibi.set_character(btn.name)
        self._preview.set_character(btn.name)
        self._mark_dirty(True)

    def _on_pick_media(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose custom companion",
            "", "Media (*.gif *.png *.jpg *.jpeg *.bmp *.webp *.mp4)")
        if path:
            self._apply_media_path(path)

    def _on_clear_media(self):
        self._apply_media_path("")

    def _apply_media_path(self, path: str):
        self.profile.chibi.gif_path = path or None
        # Push to both the live overlay and the settings preview.
        for w in (self.overlay.chibi, self._preview):
            w.cfg.gif_path = self.profile.chibi.gif_path
            w._apply_media()
        self._update_media_label()
        self._mark_dirty(True)

    def _update_media_label(self):
        cur = self.profile.chibi.gif_path
        self._media_label.setText(f"Current: {cur}" if cur else "No custom media — procedural character is shown.")
        self._media_clear.setEnabled(bool(cur))

    def _refresh_keys(self):
        self.key_list.clear()
        for kc in self.profile.keys:
            item = _KeyListWidgetItem(kc.label, kc.key, kc.color)
            self.key_list.addItem(item)
        # Update badge count
        count = len(self.profile.keys)
        self._key_count_badge.setText(str(count))
        self._key_count_badge.setVisible(count > 0)
        # Update empty state
        self._update_empty_state()
        # Update add-key cards (gray out already-added)
        for token, card in self._add_key_cards.items():
            card.set_added(any(k.key == token for k in self.profile.keys))

    def _update_empty_state(self):
        self._empty_hint.setVisible(len(self.profile.keys) == 0)

    def _filter_keys(self, text: str):
        text = text.lower().strip()
        for token, card in self._add_key_cards.items():
            if not text:
                card.setVisible(True)
            else:
                card.setVisible(text in token.lower() or text in card.label_text.lower())
        # Trigger reflow after visibility changes
        self._add_key_grid._reflow()

    def _add_key(self, token: str):
        if any(k.key == token for k in self.profile.keys):
            return
        label = next((s["label"] for s in SUGGESTED_KEYS if s["match"] == token), token.upper())
        color = _KEY_COLORS.get(token, "#7fd1ff")
        kc = KeyConfig(key=token, label=label, x=100, y=100, color=color)
        self.profile.keys.append(kc)
        from .key_widget import KeyWidget
        w = KeyWidget(kc, self.overlay, self.profile.key_theme)
        w.move(kc.x, kc.y); w.draggable = self.profile.edit_mode
        w.show()  # new child of a shown parent still needs explicit show
        self.overlay._key_widgets[kc.key] = w
        self._refresh_keys(); self._mark_dirty(True)

    def _remove_key(self):
        it = self.key_list.currentItem()
        if not it:
            return
        token = it.data(Qt.UserRole)
        self.profile.keys = [k for k in self.profile.keys if k.key != token]
        w = self.overlay._key_widgets.pop(token, None)
        if w:
            w.deleteLater()
        self._refresh_keys(); self._mark_dirty(True)

    # ============================================================== profiles
    def _load_game_profile(self, name: str):
        raw_keys = self.GAME_PROFILES[name]
        for k, w in list(self.overlay._key_widgets.items()):
            w.setParent(None)
            w.deleteLater()
        self.overlay._key_widgets.clear()
        self.profile.keys.clear()
        from .key_widget import KeyWidget
        for token, label, x, y, sz, color in raw_keys:
            kc = KeyConfig(key=token, label=label, x=x, y=y, size=sz, color=color)
            self.profile.keys.append(kc)
            w = KeyWidget(kc, self.overlay, self.profile.key_theme)
            w.move(x, y)
            w.draggable = self.profile.edit_mode
            w.show()
            self.overlay._key_widgets[kc.key] = w
        self._refresh_keys()
        self._mark_dirty(True)

    def _save_new_profile(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:", text="my_profile")
        if not (ok and name.strip()):
            return
        name = name.strip()
        # Windows-illegal filename chars would make open() raise (and leave the
        # dialog in a half-saved state) — reject them up front.
        if any(ch in name for ch in '<>:"/\\|?*') or name in (".", ".."):
            QMessageBox.warning(self, "New Profile",
                                "Profile name contains characters Windows can't use "
                                "(< > : \" / \\ | ? *). Pick a simpler name.")
            return
        self.profile.name = name
        self.overlay._save_positions()
        cfg_mod.save_profile(self.profile)
        self._mark_dirty(False)

    def _delete_profile(self):
        path = cfg_mod.profile_path(self.profile.name)
        if not os.path.exists(path):
            QMessageBox.information(self, "Profiles", f"No saved file for '{self.profile.name}'.")
            return
        os.remove(path)
        QMessageBox.information(self, "Profiles", f"Deleted profile '{self.profile.name}'.")

    # ============================================================== status
    def _mark_dirty(self, dirty: bool):
        if dirty:
            self._status.setText("  unsaved changes")
            self._status.setStyleSheet(f"color:#fbbf24; font-size:{_q(11, SettingsWindow._scale)}px; font-weight:500;")
        else:
            self._status.setText("  overlay active")
            self._status.setStyleSheet(f"color:{TOK['success']}; font-size:{_q(11, SettingsWindow._scale)}px; font-weight:500;")

    # ============================================================== save / load
    def _discard(self):
        self.profile = cfg_mod.load_profile()
        self.overlay.profile = self.profile
        self._apply_full_profile()
        self._mark_dirty(False)

    def _apply_full_profile(self):
        """Re-apply the full profile to the overlay (used after discard)."""
        self.overlay.set_enabled(self.profile.enabled)
        self.overlay.set_always_on_top(self.profile.always_on_top)
        self.overlay.setWindowOpacity(self.profile.opacity)
        self.overlay.set_key_visuals(
            self.profile.key_scale, self.profile.key_opacity, self.profile.key_radius
        )
        self.overlay.chibi.set_config(self.profile.chibi)
        self.overlay.chibi.set_character(self.profile.chibi_theme)
        self.overlay.chibi.resize(self.profile.chibi.size, self.profile.chibi.size)
        self.overlay.rebuild_keys()
        # Refresh UI controls to match the profile.
        self.cb_enabled.setChecked(self.profile.enabled)
        self.cb_aot.setChecked(self.profile.always_on_top)
        self.cb_startup.setChecked(self.profile.start_with_windows)
        self.cb_min.setChecked(self.profile.minimize_to_tray)
        self._hotkey_edit.setKeySequence(self.profile.toggle_hotkey)
        self.sl_opacity.setValue(int(self.profile.opacity * 100))
        self.sl_kscale.setValue(int(self.profile.key_scale * 100))
        self.sl_kop.setValue(int(self.profile.key_opacity * 100))
        self.sl_krad.setValue(self.profile.key_radius)
        c = self.profile.chibi
        self.cb_follow.setChecked(c.mouse_follow)
        self.cb_mtrack.setChecked(c.mouse_follow)
        self.cb_head.setChecked(c.head_follow)
        self.cb_eye.setChecked(c.eye_follow)
        self.cb_arm.setChecked(c.arm_follow)
        self.sl_follow.setValue(int(c.follow_strength * 100))
        self.sl_sens.setValue(int(c.follow_strength * 100))
        self.sl_smooth.setValue(int(c.smoothing * 100))
        self.sl_eye.setValue(int(c.eye_movement * 100))
        self.sl_size.setValue(int(c.size / 600.0 * 100))
        self.sl_dead.setValue(c.dead_zone)
        self._refresh_keys()

    def _save(self):
        # Pull every live control back into the profile, then persist.
        c = self.profile.chibi
        c.mouse_follow = self.cb_follow.isChecked()
        c.head_follow = self.cb_head.isChecked()
        c.eye_follow = self.cb_eye.isChecked()
        c.arm_follow = self.cb_arm.isChecked()
        c.follow_strength = self.sl_follow.value() / 100.0
        c.smoothing = self.sl_smooth.value() / 100.0
        c.eye_movement = self.sl_eye.value() / 100.0
        c.dead_zone = self.sl_dead.value()
        c.size = max(40, int(self.sl_size.value() / 100.0 * 600))
        self.profile.enabled = self.cb_enabled.isChecked()
        self.profile.always_on_top = self.cb_aot.isChecked()
        self.profile.start_with_windows = self.cb_startup.isChecked()
        self.profile.minimize_to_tray = self.cb_min.isChecked()
        self.profile.opacity = self.sl_opacity.value() / 100.0
        self.profile.key_scale = self.sl_kscale.value() / 100.0
        self.profile.key_opacity = self.sl_kop.value() / 100.0
        self.profile.key_radius = self.sl_krad.value()
        # Persist startup state to the OS.
        platform_win.set_start_with_windows(self.profile.start_with_windows)
        # Apply final geometry/visuals.
        self.overlay.set_enabled(self.profile.enabled)
        self.overlay.set_always_on_top(self.profile.always_on_top)
        self.overlay.setWindowOpacity(self.profile.opacity)
        self.overlay.set_key_visuals(
            self.profile.key_scale, self.profile.key_opacity, self.profile.key_radius
        )
        self.overlay.chibi.cfg = c
        self.overlay.chibi.resize(c.size, c.size)
        self.overlay._save_positions()
        cfg_mod.save_profile(self.profile)
        self._mark_dirty(False)

    def _reset_layout(self):
        reply = QMessageBox.question(
            self, "Reset All Settings",
            "This will reset all settings to defaults. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            default = cfg_mod.default_profile()
            cfg_mod.save_profile(default)
            self.profile = default
            self.overlay.profile = default
            self._apply_full_profile()
            self._mark_dirty(False)
