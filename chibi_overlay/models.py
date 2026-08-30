"""Data models for the Chibi Overlay profile.

A profile fully describes how the overlay looks and behaves: the chibi
character, which keys are shown, mouse-follow parameters, and global
toggles. Everything is a plain dataclass so it serializes cleanly to JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


# Keys we suggest in the "add key" picker. `match` is the token the input
# layer compares against (see input_listener.key_matches).
SUGGESTED_KEYS: List[dict] = [
    {"match": "w", "label": "W"},
    {"match": "a", "label": "A"},
    {"match": "s", "label": "S"},
    {"match": "d", "label": "D"},
    {"match": "space", "label": "SPACE"},
    {"match": "shift", "label": "SHIFT"},
    {"match": "ctrl", "label": "CTRL"},
    {"match": "alt", "label": "ALT"},
    {"match": "e", "label": "E"},
    {"match": "q", "label": "Q"},
    {"match": "r", "label": "R"},
    {"match": "f", "label": "F"},
    {"match": "mouse_left", "label": "LMB"},
    {"match": "mouse_right", "label": "RMB"},
]


@dataclass
class ChibiConfig:
    x: int = 1500
    y: int = 700
    size: int = 160
    # Master toggle: the whole body reaches toward the physical mouse.
    mouse_follow: bool = True
    follow_strength: float = 0.6
    smoothing: float = 0.6
    eye_movement: float = 0.6
    # Independent follow granularity (all real, applied in ChibiWidget).
    head_follow: bool = True
    eye_follow: bool = True
    arm_follow: bool = True
    # Below this many pixels of cursor movement, the head/eyes stop tracking.
    dead_zone: int = 5
    gif_path: Optional[str] = None


@dataclass
class KeyConfig:
    key: str
    label: str
    x: int = 0
    y: int = 0
    size: int = 64
    color: str = "#7fd1ff"
    locked: bool = False


@dataclass
class Profile:
    version: int = 1
    name: str = "default"
    # Overlay master switch (hide/show the whole overlay).
    enabled: bool = True
    opacity: float = 1.0
    click_through: bool = True
    edit_mode: bool = False
    always_on_top: bool = True
    start_with_windows: bool = False
    minimize_to_tray: bool = True
    toggle_hotkey: str = "Ctrl+Alt+S"
    key_theme: str = "midnight"
    chibi_theme: str = "cat"
    # Visual tuning that applies to every keycap.
    key_scale: float = 1.0
    key_opacity: float = 1.0
    key_radius: int = 18
    chibi: ChibiConfig = field(default_factory=ChibiConfig)
    keys: List[KeyConfig] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Profile":
        data = dict(data)
        chibi = data.pop("chibi", {}) or {}
        keys_raw = data.pop("keys", []) or []
        keys = [KeyConfig(**k) for k in keys_raw]
        # Only forward fields this Profile version actually knows about, so a
        # profile saved by an older build (with extra/renamed keys) still loads.
        p_known = {f.name for f in Profile.__dataclass_fields__.values()}
        c_known = {f.name for f in ChibiConfig.__dataclass_fields__.values()}
        extra = {k: v for k, v in data.items() if k in p_known}
        chibi = {k: v for k, v in chibi.items() if k in c_known}
        return Profile(chibi=ChibiConfig(**chibi), keys=keys, **extra)
