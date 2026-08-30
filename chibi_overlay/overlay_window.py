"""The overlay window: transparent, always-on-top, click-through.

Holds the ChibiWidget and a set of KeyWidgets. Wires up the global input
listener so physical key presses / mouse moves light up the widgets. In
edit mode the window becomes interactive and widgets become draggable;
leaving edit mode saves positions back to the profile.

All toggles (enabled, always-on-top, mouse tracking, key size/opacity, key
corner radius) are applied here for real — there is no "display-only" state.
"""
from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtWidgets import QApplication, QWidget

from .models import Profile
from . import platform_win
from .input_listener import KeyListener, key_matches
from .chibi_widget import ChibiWidget
from .key_widget import KeyWidget


# Map key tokens -> cat emotion reactions (Bongo's Cat style)
_KEY_EMOTIONS = {
    "w": "happy", "a": "happy", "s": "surprised", "d": "happy",
    "e": "love", "q": "angry", "r": "happy",
    "space": "surprised", "shift": "angry", "ctrl": "angry",
    "mouse_left": "happy", "mouse_right": "love",
}


class OverlayWindow(QWidget):
    def __init__(self, profile: Profile):
        super().__init__()
        self.profile = profile
        self._key_widgets: Dict[str, KeyWidget] = {}

        self._setup_window()
        self._build_widgets()
        self._apply_profile()
        self._start_listener()

    # ----------------------------------------------------------- window
    def _setup_window(self):
        flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # Use actual screen geometry instead of hardcoded 1920x1080
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
        else:
            geo = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)
        self.setWindowTitle("Chibi Overlay")

    def _build_widgets(self):
        self.chibi = ChibiWidget(self.profile.chibi, self, self.profile.chibi_theme)
        self.chibi.move(self.profile.chibi.x, self.profile.chibi.y)
        self.chibi.resize(self.profile.chibi.size, self.profile.chibi.size)

        for kc in self.profile.keys:
            w = KeyWidget(kc, self, self.profile.key_theme)
            w.move(kc.x, kc.y)
            self._key_widgets[kc.key] = w

    def _apply_profile(self):
        self.set_enabled(self.profile.enabled)
        self.set_always_on_top(self.profile.always_on_top)
        self.setWindowOpacity(self.profile.opacity)
        self.set_key_visuals(
            self.profile.key_scale, self.profile.key_opacity, self.profile.key_radius
        )
        self._set_click_through(self.profile.click_through and not self.profile.edit_mode)
        self.chibi.move(self.profile.chibi.x, self.profile.chibi.y)

    # ----------------------------------------------------------- listener
    def _start_listener(self):
        self._listener = KeyListener(
            on_press=self._on_press,
            on_release=self._on_release,
            on_click=self._on_click,
            on_move=self._on_move,
        )
        self._listener.start()

    def _on_press(self, key):
        token = getattr(key, "name", None) or getattr(key, "char", None)
        if token is None:
            return
        token = token.lower()
        QApplication.instance().postEvent(self, _PressEvent(token))

    def _on_release(self, key):
        token = getattr(key, "name", None) or getattr(key, "char", None)
        if token is None:
            return
        token = token.lower()
        QApplication.instance().postEvent(self, _ReleaseEvent(token))

    def _on_click(self, name):
        QApplication.instance().postEvent(self, _ClickEvent(name))

    def _on_move(self, x, y):
        # Route through Qt event system for thread safety (input thread -> GUI thread)
        QApplication.instance().postEvent(self, _MoveEvent(x, y))

    # ----------------------------------------------------------- event handlers
    def handle_press(self, token: str):
        for kc in self.profile.keys:
            if key_matches(kc.key, _token_to_pynput_key(token)):
                w = self._key_widgets.get(kc.key)
                if w:
                    w.press()
                emotion = _KEY_EMOTIONS.get(kc.key)
                if emotion:
                    self.chibi.set_emotion(emotion, 2.5)
        self.chibi.pulse()

    def handle_release(self, token: str):
        for kc in self.profile.keys:
            if key_matches(kc.key, _token_to_pynput_key(token)):
                w = self._key_widgets.get(kc.key)
                if w:
                    w.release()

    def handle_click(self, name: str):
        pressed = not name.endswith("_release")
        base = name[:-8] if name.endswith("_release") else name
        for kc in self.profile.keys:
            if kc.key == base:
                w = self._key_widgets.get(kc.key)
                if w:
                    (w.press() if pressed else w.release())
        self.chibi.set_click(base, pressed)
        if pressed:
            self.chibi.pulse()
            emotion = _KEY_EMOTIONS.get(base)
            if emotion:
                self.chibi.set_emotion(emotion, 2.0)

    def handle_move(self, x: int, y: int):
        # Mouse tracking is a real toggle: when off, the chibi never reacts
        # to cursor movement (eyes/head/body stay centered).
        if self.profile.chibi.mouse_follow:
            self.chibi.set_mouse_global(x, y)

    # ----------------------------------------------------------- click-through
    def _set_click_through(self, enabled: bool):
        if platform_win.is_windows():
            hwnd = int(self.winId())
            platform_win.set_click_through(hwnd, enabled)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        self.chibi.draggable = not enabled
        for w in self._key_widgets.values():
            w.draggable = not enabled

    # ----------------------------------------------------------- real toggles
    def set_enabled(self, on: bool):
        """Hide / show the whole overlay (tray stays alive)."""
        self.profile.enabled = on
        self.setVisible(on)

    def set_always_on_top(self, on: bool):
        """Toggle the always-on-top (WindowStaysOnTopHint) flag live.

        Idempotent: when the window flag already matches the requested state we
        skip setWindowFlags(). Calling setWindowFlags() unconditionally (e.g. on
        every Save) destroys and recreates the native xy window each time, which
        on some GPUs/window-managers intermittently aborts the process. Only a
        real change should touch the flags.
        """
        self.profile.always_on_top = on
        has = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        if has == on:
            return
        flags = self.windowFlags()
        if on:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        # Re-applying window flags hides the widget (and recreates the native
        # handle -> winId() changes). Restore visibility and re-apply the Win32
        # click-through style, which is keyed on the (now stale) hwnd.
        if self.profile.enabled:
            self.show()
            self._set_click_through(self.profile.click_through and not self.profile.edit_mode)

    def set_key_visuals(self, scale: float, opacity: float, radius: int) -> None:
        """Apply size/opacity/corner-radius to every keycap for real."""
        self.profile.key_scale = scale
        self.profile.key_opacity = opacity
        self.profile.key_radius = radius
        for kc in self.profile.keys:
            w = self._key_widgets.get(kc.key)
            if w is None:
                continue
            w.set_scale(scale)
            w.set_opacity(opacity)
            w.set_radius(radius)

    def set_animation_fps(self, fps: int) -> None:
        """Change the chibi animation rate live."""
        interval = max(8, 1000 // max(1, fps))
        self.chibi._anim_timer.setInterval(interval)

    def rebuild_keys(self) -> None:
        """Rebuild every key widget from the current profile (after load/reset)."""
        for k, w in list(self._key_widgets.items()):
            w.setParent(None)
            w.deleteLater()
        self._key_widgets.clear()
        for kc in self.profile.keys:
            w = KeyWidget(kc, self, self.profile.key_theme)
            w.move(kc.x, kc.y)
            w.draggable = not self.profile.click_through
            w.show()  # parent already shown at runtime => must re-show
            self._key_widgets[kc.key] = w
        self.set_key_visuals(
            self.profile.key_scale, self.profile.key_opacity, self.profile.key_radius
        )

    # ----------------------------------------------------------- edit mode
    def set_edit_mode(self, on: bool):
        self.profile.edit_mode = on
        self._set_click_through(self.profile.click_through and not on)
        if not on:
            self._save_positions()

    def _remove_key(self, key: str):
        w = self._key_widgets.pop(key, None)
        if w:
            w.setParent(None)
            w.deleteLater()
        self.profile.keys = [kc for kc in self.profile.keys if kc.key != key]

    def _save_positions(self):
        if not self.profile.enabled:
            return
        self.profile.chibi.x = self.chibi.x()
        self.profile.chibi.y = self.chibi.y()
        for kc in self.profile.keys:
            w = self._key_widgets.get(kc.key)
            if w:
                kc.x = w.x()
                kc.y = w.y()

    # ----------------------------------------------------------- misc
    def closeEvent(self, event):
        self._listener.stop()
        super().closeEvent(event)

    # ---- dispatch input-thread events onto the GUI thread ----
    def customEvent(self, event):
        if isinstance(event, _PressEvent):
            self.handle_press(event.token)
        elif isinstance(event, _ReleaseEvent):
            self.handle_release(event.token)
        elif isinstance(event, _ClickEvent):
            self.handle_click(event.name)
        elif isinstance(event, _MoveEvent):
            self.handle_move(event.x, event.y)
        else:
            super().customEvent(event)


# ---- Tiny custom events so input thread -> GUI thread handoff is clean ----
class _PressEvent(QEvent):
    Type = QEvent.Type(QEvent.registerEventType())
    def __init__(self, token): self.token = token; super().__init__(self.Type)

class _ReleaseEvent(QEvent):
    Type = QEvent.Type(QEvent.registerEventType())
    def __init__(self, token): self.token = token; super().__init__(self.Type)

class _ClickEvent(QEvent):
    Type = QEvent.Type(QEvent.registerEventType())
    def __init__(self, name): self.name = name; super().__init__(self.Type)

class _MoveEvent(QEvent):
    Type = QEvent.Type(QEvent.registerEventType())
    def __init__(self, x, y): self.x = x; self.y = y; super().__init__(self.Type)

def _token_to_pynput_key(token: str):
    """Build a pynput-like object so key_matches() can test against it."""
    from pynput.keyboard import Key, KeyCode
    class _K:
        pass
    t = token.lower()
    named = {
        "space": Key.space, "shift": Key.shift, "ctrl": Key.ctrl,
        "alt": Key.alt, "tab": Key.tab, "enter": Key.enter,
        "esc": Key.esc, "backspace": Key.backspace,
    }
    if t in named:
        return named[t]
    if len(t) == 1:
        return KeyCode.from_char(t)
    return _K()
