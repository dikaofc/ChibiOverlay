"""Tiny Win32 helpers for the overlay.

On Windows a window is click-through when it carries WS_EX_TRANSPARENT, and
we flip that extended style at runtime so the overlay can be interactive in
edit mode and passive (mouse passes through to the game) otherwise.

Start-with-Windows is implemented through the HKCU "Run" registry key, so the
overlay (tray + settings) relaunches automatically after a reboot/logon.
"""
from __future__ import annotations

import ctypes
import os
import sys

try:  # winreg is only available on Windows
    import winreg
except ImportError:  # pragma: no cover - non-Windows
    winreg = None

user32 = ctypes.windll.user32 if sys.platform.startswith("win") else None

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

_REG_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_windows() -> bool:
    return sys.platform.startswith("win")


def set_click_through(hwnd: int, enabled: bool) -> None:
    """Enable/disable mouse pass-through for the given window handle."""
    if user32 is None or not hwnd:
        return
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    if ex == 0:
        return
    if enabled:
        ex |= WS_EX_TRANSPARENT | WS_EX_LAYERED
    else:
        ex &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)


def _exe_path() -> str:
    """Path to the running executable (PyInstaller bundle or python)."""
    return os.path.realpath(sys.executable)


def set_start_with_windows(enabled: bool, app_name: str = "ChibiOverlay") -> bool:
    """Add/remove the app from HKCU\\Run. Returns True on success."""
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_RUN, 0, winreg.KEY_SET_VALUE
        )
        if enabled:
            exe = _exe_path()
            # Quote the path so spaces in "Program Files" don't break it.
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe}"')
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def get_start_with_windows(app_name: str = "ChibiOverlay") -> bool:
    """True if the app is currently registered to run at logon."""
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN, 0, winreg.KEY_QUERY_VALUE)
        try:
            winreg.QueryValueEx(key, app_name)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False
