"""Global keyboard + mouse listener built on pynput.

Runs in a background thread and reports events through callbacks so the
Qt GUI thread never blocks. We expose a small abstraction:

    KeyListener(on_press, on_release, on_click, on_move)

The callbacks receive normalized tokens:
  * keyboard key  -> the pynput Key/KeyCode, matched via key_matches()
  * mouse button  -> "mouse_left" / "mouse_right" / "mouse_middle"
  * mouse move    -> (x, y) screen coordinates

`key_matches(token, event_key)` turns a pynput key into a stable string we
can compare against a KeyConfig.key:
    "w", "space", "shift", "ctrl", "alt", "mouse_left", ...
"""
from __future__ import annotations

from typing import Callable, Optional

from pynput import keyboard, mouse


MouseButtonName = str  # "mouse_left" | "mouse_right" | "mouse_middle"
PressCb = Callable[[str], None]
ReleaseCb = Callable[[str], None]
ClickCb = Callable[[MouseButtonName], None]
MoveCb = Callable[[int, int], None]

_BUTTON_MAP = {
    mouse.Button.left: "mouse_left",
    mouse.Button.right: "mouse_right",
    mouse.Button.middle: "mouse_middle",
}


def key_matches(token: str, event_key) -> bool:
    """Return True if a pynput key event corresponds to `token`."""
    token = token.lower()
    if token.startswith("mouse_"):
        return False  # handled by the mouse listener

    # Special / named keys
    named = {
        "space": "space",
        "shift": "shift",
        "ctrl": "ctrl",
        "control": "ctrl",
        "alt": "alt",
        "tab": "tab",
        "enter": "enter",
        "return": "enter",
        "esc": "esc",
        "escape": "esc",
        "backspace": "backspace",
        "caps_lock": "caps_lock",
    }
    if token in named:
        target = named[token]
        return getattr(event_key, "name", None) == target

    # Single character / letter keys
    if len(token) == 1:
        # event_key.char is lowercase already
        return getattr(event_key, "char", None) == token
    return False


class KeyListener:
    def __init__(
        self,
        on_press: Optional[PressCb] = None,
        on_release: Optional[ReleaseCb] = None,
        on_click: Optional[ClickCb] = None,
        on_move: Optional[MoveCb] = None,
    ):
        self.on_press = on_press
        self.on_release = on_release
        self.on_click = on_click
        self.on_move = on_move
        self._kb = keyboard.Listener(
            on_press=self._kb_press, on_release=self._kb_release
        )
        self._ms = mouse.Listener(on_click=self._ms_click, on_move=self._ms_move)

    # --- keyboard ---
    def _kb_press(self, key):
        if self.on_press:
            self.on_press(key)

    def _kb_release(self, key):
        if self.on_release:
            self.on_release(key)

    # --- mouse ---
    def _ms_click(self, x, y, button, pressed):
        name = _BUTTON_MAP.get(button)
        if name is None:
            return
        if pressed and self.on_click:
            self.on_click(name)
        elif (not pressed) and self.on_click:
            # treat release as a (name + "_release")? We keep it simple:
            # emit the same token; widgets decide. Here we emit release token.
            self.on_click(name + "_release")

    def _ms_move(self, x, y):
        if self.on_move:
            self.on_move(int(x), int(y))

    def start(self):
        self._kb.start()
        self._ms.start()

    def stop(self):
        self._kb.stop()
        self._ms.stop()
