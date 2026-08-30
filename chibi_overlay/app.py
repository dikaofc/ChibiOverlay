"""Application entry point: builds the Qt app, overlay, and tray icon."""
from __future__ import annotations

import sys
import os

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import (
    QIcon, QKeySequence, QPalette, QColor, QShortcut,
)
from PySide6.QtCore import Qt, QTimer


def _apply_dark_palette(app: QApplication):
    """Force a dark palette with light text globally."""
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#0f1015"))
    p.setColor(QPalette.WindowText, QColor("#f4f4f5"))
    p.setColor(QPalette.Base, QColor("#1b1d27"))
    p.setColor(QPalette.AlternateBase, QColor("#151720"))
    p.setColor(QPalette.ToolTipBase, QColor("#1b1d27"))
    p.setColor(QPalette.ToolTipText, QColor("#f4f4f5"))
    p.setColor(QPalette.Text, QColor("#f4f4f5"))
    p.setColor(QPalette.Button, QColor("#1b1d27"))
    p.setColor(QPalette.ButtonText, QColor("#f4f4f5"))
    p.setColor(QPalette.BrightText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor("#ff8fc7"))
    p.setColor(QPalette.Highlight, QColor("#ff8fc7"))
    p.setColor(QPalette.HighlightedText, QColor("#0f1015"))
    p.setColor(QPalette.PlaceholderText, QColor("#9ca3af"))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor("#9ca3af"))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#9ca3af"))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#9ca3af"))
    app.setPalette(p)


def _base_dir() -> str:
    """Return the app root dir — works both in dev and PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    from .config import load_profile, save_profile
    from .overlay_window import OverlayWindow
    from .settings_dialog import SettingsWindow
    from .icon import generate_icon
    from . import platform_win

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _apply_dark_palette(app)

    # Generate icon AFTER QApplication exists
    app_icon = generate_icon()
    app.setWindowIcon(app_icon)

    profile = load_profile()
    overlay = OverlayWindow(profile)
    overlay.setWindowIcon(app_icon)

    # Apply startup toggles from saved profile
    overlay.set_always_on_top(profile.always_on_top)
    overlay.setWindowOpacity(profile.opacity)
    overlay._set_click_through(profile.click_through and not profile.edit_mode)
    if profile.start_with_windows and not platform_win.get_start_with_windows():
        platform_win.set_start_with_windows(True)
    overlay.set_enabled(profile.enabled)

    _first_run = not os.path.exists(
        os.path.join(_base_dir(), "profiles", "default.json")
    )

    # ---- settings dialog helper ----
    _dlg = [None]

    def open_settings():
        if _dlg[0] is not None:
            _dlg[0].showNormal()
            _dlg[0].raise_()
            _dlg[0].activateWindow()
            return
        try:
            dlg = SettingsWindow(overlay)
            _dlg[0] = dlg
            dlg.destroyed.connect(lambda: _set_dlg_none())
            dlg.show()
            QTimer.singleShot(80, lambda: _raise_dlg(dlg))
        except Exception:
            import traceback; traceback.print_exc()

    def _raise_dlg(dlg):
        if dlg is not None and not dlg.isHidden():
            dlg.raise_()
            dlg.activateWindow()

    def _set_dlg_none():
        _dlg[0] = None

    # ---- keyboard shortcut ----
    shortcut = QShortcut(QKeySequence("Ctrl+Alt+S"), overlay)
    shortcut.activated.connect(open_settings)

    # ---- system tray ----
    tray = QSystemTrayIcon(app_icon, app)
    tray.setToolTip("Chibi Overlay — Right-click for menu")

    menu = QMenu()
    menu.setStyleSheet(
        "QMenu { background: #1b1d27; color: #f4f4f5; border: 1px solid #262936; }"
        "QMenu::item { background: transparent; color: #f4f4f5; padding: 6px 18px; }"
        "QMenu::item:selected { background: #ff8fc7; color: #0f1015; }"
        "QMenu::item:disabled { color: #6b7280; }"
        "QMenu::separator { height: 1px; background: #262936; margin: 4px 8px; }"
    )

    act_settings = menu.addAction("Settings (Ctrl+Alt+S)")
    menu.addSeparator()

    act_enable = menu.addAction("Show Overlay")
    act_enable.setCheckable(True)
    act_enable.setChecked(profile.enabled)

    act_edit = menu.addAction("Edit Mode")
    act_edit.setCheckable(True)
    act_edit.setChecked(profile.edit_mode)

    act_click = menu.addAction("Click-Through")
    act_click.setCheckable(True)
    act_click.setChecked(profile.click_through)

    menu.addSeparator()
    act_quit = menu.addAction("Quit")

    tray.setContextMenu(menu)

    def toggle_enable(checked):
        overlay.set_enabled(checked)
        save_profile(profile)

    def toggle_edit(checked):
        overlay.set_edit_mode(checked)
        save_profile(profile)

    def toggle_click(checked):
        profile.click_through = checked
        overlay._set_click_through(checked and not profile.edit_mode)
        save_profile(profile)

    def do_quit():
        save_profile(profile)
        overlay.close()
        app.quit()

    act_settings.triggered.connect(open_settings)
    act_enable.triggered.connect(toggle_enable)
    act_edit.triggered.connect(toggle_edit)
    act_click.triggered.connect(toggle_click)
    act_quit.triggered.connect(do_quit)

    tray.activated.connect(
        lambda reason: open_settings() if reason == QSystemTrayIcon.DoubleClick else None
    )

    tray.show()

    # Open settings on first run
    if _first_run:
        QTimer.singleShot(500, open_settings)

    return app.exec()
