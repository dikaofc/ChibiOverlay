"""A frameless, resizable window with a custom title bar.

Modern chromeless window with:
  - Thin title bar with app icon + title
  - Smooth window control buttons (min/max/close)
  - Edge/corner resize with proper cursor feedback
  - Subtle drop shadow for depth
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect,
)


# ---- Design tokens ----
_C = {
    "bg":       "#111318",
    "surface":  "#181a22",
    "border":   "#252830",
    "text":     "#e2e4ea",
    "muted":    "#6b6f7e",
    "accent":   "#c084fc",
    "close_bg": "#e81123",
    "hover":    "#1e2028",
}


class _WinButton(QPushButton):
    """Custom-drawn title-bar control button."""

    def __init__(self, glyph: str, close: bool = False):
        super().__init__()
        self._glyph = glyph
        self._close = close
        self.setFixedSize(36, 28)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.underMouse()
        w, ht = self.width(), self.height()

        # Background
        if h and self._close:
            p.setBrush(QBrush(QColor(_C["close_bg"])))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(self.rect(), 4, 4)
        elif h:
            p.setBrush(QBrush(QColor(_C["hover"])))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(self.rect(), 4, 4)

        # Glyph
        fg = QColor("#fff" if (h and self._close) else _C["muted"])
        if h and not self._close:
            fg = QColor(_C["text"])
        p.setPen(QPen(fg, 1.4))
        cx, cy = w // 2, ht // 2
        if self._glyph == "min":
            p.drawLine(QPoint(cx - 5, cy), QPoint(cx + 5, cy))
        elif self._glyph == "max":
            p.drawRoundedRect(QRect(cx - 5, cy - 4, 10, 8), 1, 1)
        elif self._glyph == "close":
            p.drawLine(QPoint(cx - 4, cy - 4), QPoint(cx + 4, cy + 4))
            p.drawLine(QPoint(cx + 4, cy - 4), QPoint(cx - 4, cy + 4))
        p.end()


class TitleBar(QWidget):
    """Thin title bar: icon + title on left, window controls on right."""

    def __init__(self, title: str, icon_pixmap: QPixmap | None, win: "FramelessWindow"):
        super().__init__()
        self.setObjectName("TitleBar")
        self.setFixedHeight(38)
        self._win = win

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 4, 0)
        lay.setSpacing(8)

        # App icon — accept QIcon or QPixmap
        if icon_pixmap is not None:
            if isinstance(icon_pixmap, QIcon):
                pm = icon_pixmap.pixmap(18, 18)
            else:
                pm = icon_pixmap
            if not pm.isNull():
                icon_label = QLabel()
                icon_label.setPixmap(pm.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                icon_label.setFixedSize(18, 18)
                lay.addWidget(icon_label)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {_C['muted']}; font-size: 12px; font-weight: 500; letter-spacing: 0.5px;")
        lay.addWidget(title_label)
        lay.addStretch()

        # Window controls
        self.btn_min = _WinButton("min")
        self.btn_max = _WinButton("max")
        self.btn_close = _WinButton("close", close=True)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

        self.btn_min.clicked.connect(self._win.showMinimized)
        self.btn_max.clicked.connect(self._win.toggle_max)
        self.btn_close.clicked.connect(self._win.close)

        self._drag_pos = None

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint()
            self._drag_origin = self._win.frameGeometry().topLeft() if not self._win._maximized else None
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self._drag_pos is not None and not self._win._maximized:
            delta = ev.globalPosition().toPoint() - self._drag_pos
            self._win.move(self._drag_origin + delta)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._win.toggle_max()


class FramelessWindow(QWidget):
    """Borderless, resizable window with modern chrome."""

    def __init__(self, title: str = "", icon: QPixmap | None = None):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._maximized = False
        self._normal_geo = None
        self.setMinimumSize(640, 480)
        self.setMouseTracking(True)

        # Outer layout — space for the shadow
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(10, 10, 10, 10)
        self._outer.setSpacing(0)

        # Main frame with rounded corners
        self._frame = QFrame()
        self._frame.setObjectName("MainFrame")
        self._frame.setStyleSheet(f"""
            QFrame#MainFrame {{
                background: {_C['surface']};
                border: 1px solid {_C['border']};
                border-radius: 10px;
            }}
        """)
        self._outer.addWidget(self._frame)

        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Title bar
        self.titlebar = TitleBar(title, icon, self)
        frame_layout.addWidget(self.titlebar)

        # Thin separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {_C['border']};")
        frame_layout.addWidget(sep)

        # Content host
        self.content_host = QWidget()
        self.content_host.setObjectName("ContentHost")
        frame_layout.addWidget(self.content_host, 1)
        self._content_layout = QVBoxLayout(self.content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self._frame.setGraphicsEffect(shadow)

        self._resize_edges = 6
        self._edge = None

    def setContent(self, widget: QWidget):
        self._content_layout.addWidget(widget)

    def toggle_max(self):
        if self._maximized:
            if self._normal_geo:
                self.setGeometry(self._normal_geo)
            self._maximized = False
        else:
            self._normal_geo = self.geometry()
            scr = self.screen().availableGeometry()
            self.setGeometry(scr)
            self._maximized = True
        self.setAttribute(Qt.WA_TranslucentBackground, not self._maximized)

    def _hit_edge(self, pos: QPoint):
        g = self.rect()
        x, y = pos.x(), pos.y()
        e = self._resize_edges
        l, r = x < e, x > g.width() - e
        t, b = y < e, y > g.height() - e
        if l and t: return (0, 0)
        if r and t: return (1, 0)
        if l and b: return (0, 1)
        if r and b: return (1, 1)
        if l: return (0, 0.5)
        if r: return (1, 0.5)
        if t: return (0.5, 0)
        if b: return (0.5, 1)
        return None

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._edge = self._hit_edge(ev.position().toPoint())
            if self._edge is not None:
                self._resize_start = ev.globalPosition().toPoint()
                self._resize_geo = self.geometry()
                ev.accept()

    def mouseMoveEvent(self, ev):
        if self._edge is not None:
            self._do_resize(ev.globalPosition().toPoint())
            ev.accept()
        elif not self._maximized:
            self._update_cursor()

    def mouseReleaseEvent(self, ev):
        self._edge = None

    def _do_resize(self, gp: QPoint):
        start = self._resize_start
        geo = self._resize_geo
        dx = gp.x() - start.x()
        dy = gp.y() - start.y()
        nx, ny, nw, nh = geo.getRect()
        ex, ey = self._edge
        if ex == 1: nw = max(self.minimumWidth(), geo.width() + dx)
        if ex == 0: nw = max(self.minimumWidth(), geo.width() - dx); nx = geo.right() - nw
        if ey == 1: nh = max(self.minimumHeight(), geo.height() + dy)
        if ey == 0: nh = max(self.minimumHeight(), geo.height() - dy); ny = geo.bottom() - nh
        self.setGeometry(nx, ny, nw, nh)

    def _update_cursor(self):
        pos = self.mapFromGlobal(self.cursor().pos())
        if self._maximized:
            return
        e = self._hit_edge(pos)
        cursors = {
            (0, 0): Qt.SizeFDiagCursor, (1, 0): Qt.SizeBDiagCursor,
            (0, 1): Qt.SizeBDiagCursor, (1, 1): Qt.SizeFDiagCursor,
            (0, 0.5): Qt.SizeHorCursor, (1, 0.5): Qt.SizeHorCursor,
            (0.5, 0): Qt.SizeVerCursor, (0.5, 1): Qt.SizeVerCursor,
        }
        self.setCursor(cursors.get(e, Qt.ArrowCursor))
