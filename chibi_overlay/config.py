"""Profile loading / saving and the built-in default profile."""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from .models import KeyConfig, Profile

# In PyInstaller bundle, profiles live next to the .exe.
# In dev mode, they live in the project root (parent of chibi_overlay/).
if getattr(sys, "frozen", False):
    _BASE = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROFILES_DIR = os.path.join(_BASE, "profiles")


def profile_path(name: str = "default") -> str:
    os.makedirs(_PROFILES_DIR, exist_ok=True)
    return os.path.join(_PROFILES_DIR, f"{name}.json")


def default_profile() -> Profile:
    """A sensible first-run layout: WASD + Space + LMB near the bottom."""
    keys = [
        KeyConfig("w", "W", x=120, y=0, size=64),
        KeyConfig("a", "A", x=40, y=72, size=64),
        KeyConfig("s", "S", x=120, y=72, size=64),
        KeyConfig("d", "D", x=200, y=72, size=64),
        KeyConfig("space", "SPACE", x=120, y=152, size=64, color="#ffd27f"),
        KeyConfig("mouse_left", "LMB", x=300, y=72, size=64, color="#ff9ecb"),
    ]
    p = Profile(keys=keys)
    # Place chibi a bit to the right of the keys.
    p.chibi.x = 520
    p.chibi.y = 40
    return p


def load_profile(path: Optional[str] = None) -> Profile:
    path = path or profile_path()
    if not os.path.exists(path):
        p = default_profile()
        save_profile(p, path)
        return p
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return Profile.from_dict(data)


def save_profile(profile: Profile, path: Optional[str] = None) -> str:
    path = path or profile_path(profile.name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(profile.to_dict(), fh, indent=2)
    return path
