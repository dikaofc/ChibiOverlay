"""Chibi Overlay — a transparent desktop companion overlay.

Public API for embedding / scripting:
    from chibi_overlay import run, OverlayWindow, Profile, load_profile
"""
from __future__ import annotations

from .models import Profile, KeyConfig, ChibiConfig, SUGGESTED_KEYS
from .config import load_profile, save_profile, default_profile, profile_path
from .overlay_window import OverlayWindow
from . import input_listener

__all__ = [
    "Profile", "KeyConfig", "ChibiConfig", "SUGGESTED_KEYS",
    "load_profile", "save_profile", "default_profile", "profile_path",
    "OverlayWindow", "input_listener", "run",
]

__version__ = "0.1.0"


def run() -> int:
    """Launch the overlay GUI. Returns a process exit code."""
    from .app import main
    return main()
