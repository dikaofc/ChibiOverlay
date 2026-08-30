"""Master overlay configuration.

Defines which overlay layers are active and their positions:
  - Chibi character
  - Key overlay (sprite-sheet or keycap-widget based)
  - Mouse movement overlay
  - Gamepad overlay

Each layer has independent x/y/size/opacity/scale settings.
Configs are saved as JSON and can be loaded as presets.

This is the equivalent of input-overlay's preset system but for
our multi-layer overlay architecture.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .models import Profile


# Where overlay presets live
if getattr(sys, "frozen", False):
    _PRESETS_DIR = os.path.join(os.path.dirname(sys.executable), "presets")
else:
    _PRESETS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "presets"
    )


@dataclass
class OverlayLayer:
    """A single overlay layer (chibi, keys, mouse, gamepad)."""
    enabled: bool = True
    x: int = 0
    y: int = 0
    size: int = 100
    opacity: float = 1.0
    scale: float = 1.0
    always_on_top: bool = True
    click_through: bool = True


@dataclass
class MouseOverlaySettings(OverlayLayer):
    """Mouse movement overlay settings."""
    show_trail: bool = True
    trail_length: int = 20
    trail_color: str = "#7fd1ff"
    show_arrow: bool = True
    arrow_color: str = "#ff9ecb"
    show_deadzone: bool = True
    deadzone_radius: int = 50
    sensitivity: float = 1.0
    size: int = 200


@dataclass
class GamepadOverlaySettings(OverlayLayer):
    """Gamepad overlay settings."""
    gamepad_id: int = 0
    show_axes: bool = True
    show_triggers: bool = True
    bg_color: str = "#1a1d27"
    btn_active_color: str = "#7fd1ff"
    size: int = 250


@dataclass
class KeyOverlaySettings(OverlayLayer):
    """Key overlay settings."""
    render_mode: str = "widget"  # "widget" (current QPainter) or "sprite"
    sprite_config: str = ""      # Path to sprite JSON config
    theme: str = "dark"          # Theme name for widget mode
    size: int = 64


@dataclass
class WebSocketSettings:
    """WebSocket server settings."""
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 16899
    send_keyboard: bool = True
    send_mouse: bool = True
    send_gamepad: bool = False


@dataclass
class MasterOverlayConfig:
    """Full overlay configuration — all layers + global settings."""
    name: str = "default"
    # Global
    global_opacity: float = 1.0
    always_on_top: bool = True
    edit_mode: bool = False
    # Layers
    chibi: OverlayLayer = field(default_factory=lambda: OverlayLayer(
        enabled=True, x=1500, y=700, size=160,
    ))
    keys: KeyOverlaySettings = field(default_factory=lambda: KeyOverlaySettings(
        enabled=True, x=100, y=400, size=64,
    ))
    mouse: MouseOverlaySettings = field(default_factory=lambda: MouseOverlaySettings(
        enabled=False, x=1600, y=500, size=200,
    ))
    gamepad: GamepadOverlaySettings = field(default_factory=lambda: GamepadOverlaySettings(
        enabled=False, x=1400, y=600, size=250,
    ))
    websocket: WebSocketSettings = field(default_factory=WebSocketSettings)

    @staticmethod
    def from_profile(profile: Profile) -> "MasterOverlayConfig":
        """Create a MasterOverlayConfig from an existing Profile."""
        cfg = MasterOverlayConfig()
        cfg.global_opacity = profile.opacity
        cfg.always_on_top = profile.always_on_top
        cfg.edit_mode = profile.edit_mode
        # Chibi
        cfg.chibi.x = profile.chibi.x
        cfg.chibi.y = profile.chibi.y
        cfg.chibi.size = profile.chibi.size
        # Keys
        cfg.keys.theme = profile.key_theme
        cfg.keys.size = int(profile.key_scale * 64)
        return cfg

    @staticmethod
    def from_json(path: str) -> "MasterOverlayConfig":
        """Load config from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = MasterOverlayConfig()
        cfg.name = data.get("name", "default")
        cfg.global_opacity = data.get("global_opacity", 1.0)
        cfg.always_on_top = data.get("always_on_top", True)
        cfg.edit_mode = data.get("edit_mode", False)
        for layer_name in ("chibi", "keys", "mouse", "gamepad"):
            if layer_name in data:
                layer_data = data[layer_name]
                layer = getattr(cfg, layer_name)
                for k, v in layer_data.items():
                    if hasattr(layer, k):
                        setattr(layer, k, v)
        if "websocket" in data:
            for k, v in data["websocket"].items():
                if hasattr(cfg.websocket, k):
                    setattr(cfg.websocket, k, v)
        return cfg

    def to_json(self, path: str) -> None:
        """Save config to JSON."""
        data = {
            "name": self.name,
            "global_opacity": self.global_opacity,
            "always_on_top": self.always_on_top,
            "edit_mode": self.edit_mode,
            "chibi": asdict(self.chibi),
            "keys": asdict(self.keys),
            "mouse": asdict(self.mouse),
            "gamepad": asdict(self.gamepad),
            "websocket": asdict(self.websocket),
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


# ===================================================================
# Built-in presets
# ===================================================================

BUILTIN_PRESETS: Dict[str, MasterOverlayConfig] = {}


def _register_preset(cfg: MasterOverlayConfig):
    BUILTIN_PRESETS[cfg.name] = cfg


def _default_overlay() -> MasterOverlayConfig:
    return MasterOverlayConfig(name="Default")


def _streaming_overlay() -> MasterOverlayConfig:
    cfg = MasterOverlayConfig(name="Streaming")
    cfg.mouse.enabled = True
    cfg.mouse.x = 1600
    cfg.mouse.y = 500
    cfg.gamepad.enabled = True
    cfg.gamepad.x = 1350
    cfg.gamepad.y = 550
    cfg.websocket.enabled = True
    cfg.websocket.send_keyboard = True
    cfg.websocket.send_mouse = True
    cfg.websocket.send_gamepad = True
    return cfg


def _minimal_overlay() -> MasterOverlayConfig:
    cfg = MasterOverlayConfig(name="Minimal")
    cfg.chibi.enabled = False
    cfg.mouse.enabled = False
    cfg.gamepad.enabled = False
    cfg.keys.size = 48
    return cfg


def _gaming_overlay() -> MasterOverlayConfig:
    cfg = MasterOverlayConfig(name="Gaming")
    cfg.chibi.x = 1600
    cfg.chibi.y = 600
    cfg.chibi.size = 120
    cfg.keys.x = 100
    cfg.keys.y = 500
    cfg.mouse.enabled = True
    cfg.mouse.x = 1500
    cfg.mouse.y = 500
    return cfg


_register_preset(_default_overlay())
_register_preset(_streaming_overlay())
_register_preset(_minimal_overlay())
_register_preset(_gaming_overlay())


def list_presets() -> List[str]:
    """List all available preset names."""
    presets = list(BUILTIN_PRESETS.keys())
    # Also scan custom presets directory
    if os.path.isdir(_PRESETS_DIR):
        for f in os.listdir(_PRESETS_DIR):
            if f.endswith(".json"):
                name = os.path.splitext(f)[0]
                if name not in presets:
                    presets.append(name)
    return presets


def load_preset(name: str) -> Optional[MasterOverlayConfig]:
    """Load a preset by name (built-in or custom file)."""
    if name in BUILTIN_PRESETS:
        return BUILTIN_PRESETS[name]
    path = os.path.join(_PRESETS_DIR, f"{name}.json")
    if os.path.exists(path):
        return MasterOverlayConfig.from_json(path)
    return None


def save_preset(config: MasterOverlayConfig, name: str = "") -> str:
    """Save a preset to the custom presets directory."""
    name = name or config.name
    path = os.path.join(_PRESETS_DIR, f"{name}.json")
    config.to_json(path)
    return path


def delete_preset(name: str) -> bool:
    """Delete a custom preset. Built-in presets cannot be deleted."""
    if name in BUILTIN_PRESETS:
        return False
    path = os.path.join(_PRESETS_DIR, f"{name}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
