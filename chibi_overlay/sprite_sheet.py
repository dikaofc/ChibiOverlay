"""Sprite-sheet based keycap renderer.

Loads a PNG texture atlas and renders individual keys by sampling
rectangular regions (U, V, W, H) for each key state (normal, pressed).

This follows the input-overlay CCT paradigm:
  - A single texture file contains all keycap artwork
  - Each key is defined by its UV region in the texture
  - Pressed state uses a separate UV region offset by a configurable amount

Usage:
    sheet = SpriteSheet("keyboard.png")
    config = SpriteConfig.from_json("keyboard.json")
    # In paintEvent:
    sheet.draw_key(painter, config.get_key("w"), x=100, y=200, pressed=False)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QRect, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPixmap, QPen, QBrush, QFont
from PySide6.QtWidgets import QApplication


@dataclass
class SpriteKey:
    """A single key definition in the sprite sheet."""
    id: str                    # Key token: "w", "space", "mouse_left", etc.
    u: int = 0                 # X position in texture (normal state)
    v: int = 0                 # Y position in texture (normal state)
    w: int = 50                # Width of key region
    h: int = 50                # Height of key region
    z: int = 0                 # Z-index (draw order)
    # Pressed state offset (relative to normal UV)
    pressed_u: Optional[int] = None  # If None, uses u + pressed_offset_u
    pressed_v: Optional[int] = None  # If None, uses v + pressed_offset_v
    # Hit-test position (where the key is placed on screen)
    x: int = 0                 # Screen X
    y: int = 0                 # Screen Y
    keycode: str = ""          # Matching token for input system
    # Visual modifiers
    label: str = ""            # Text label drawn on key
    label_color: str = "#ffffff"
    label_size: int = 12
    scale: float = 1.0         # Render scale
    opacity: float = 1.0       # 0..1

    def normal_rect(self) -> QRect:
        return QRect(self.u, self.v, self.w, self.h)

    def pressed_rect(self, offset_u: int = 0, offset_v: int = 0) -> QRect:
        pu = self.pressed_u if self.pressed_u is not None else self.u + offset_u
        pv = self.pressed_v if self.pressed_v is not None else self.v + offset_v
        return QRect(pu, pv, self.w, self.h)

    def screen_rect(self) -> QRectF:
        sw = self.w * self.scale
        sh = self.h * self.scale
        return QRectF(self.x, self.y, sw, sh)


@dataclass
class SpriteConfig:
    """Full configuration for a sprite-sheet overlay."""
    name: str = "default"
    texture: str = ""          # Path to PNG texture
    default_w: int = 50        # Default key width
    default_h: int = 50        # Default key height
    h_offset: int = 0          # Horizontal offset for all keys
    v_offset: int = 0          # Vertical offset for all keys
    # Pressed-state offset in the texture (default: key height below)
    pressed_offset_u: int = 0
    pressed_offset_v: int = 50  # Typically pressed keys are below normal
    keys: List[SpriteKey] = field(default_factory=list)

    @staticmethod
    def from_json(path: str) -> "SpriteConfig":
        """Load a config from a JSON file (input-overlay CCT format compatible)."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = SpriteConfig()
        cfg.name = data.get("name", os.path.splitext(os.path.basename(path))[0])
        cfg.texture = data.get("texture", "")
        cfg.default_w = data.get("default_w", 50)
        cfg.default_h = data.get("default_h", 50)
        cfg.h_offset = data.get("h_offset", 0)
        cfg.v_offset = data.get("v_offset", 0)
        cfg.pressed_offset_u = data.get("pressed_offset_u", 0)
        cfg.pressed_offset_v = data.get("pressed_offset_v", cfg.default_h)
        for kd in data.get("keys", []):
            cfg.keys.append(SpriteKey(
                id=kd.get("id", ""),
                u=kd.get("u", 0), v=kd.get("v", 0),
                w=kd.get("w", cfg.default_w), h=kd.get("h", cfg.default_h),
                z=kd.get("z", 0),
                pressed_u=kd.get("pressed_u"),
                pressed_v=kd.get("pressed_v"),
                x=kd.get("x", 0), y=kd.get("y", 0),
                keycode=kd.get("keycode", kd.get("id", "")),
                label=kd.get("label", ""),
                label_color=kd.get("label_color", "#ffffff"),
                label_size=kd.get("label_size", 12),
                scale=kd.get("scale", 1.0),
                opacity=kd.get("opacity", 1.0),
            ))
        return cfg

    def to_json(self, path: str) -> None:
        """Save config to JSON."""
        data = {
            "name": self.name,
            "texture": self.texture,
            "default_w": self.default_w,
            "default_h": self.default_h,
            "h_offset": self.h_offset,
            "v_offset": self.v_offset,
            "pressed_offset_u": self.pressed_offset_u,
            "pressed_offset_v": self.pressed_offset_v,
            "keys": [
                {
                    "id": k.id, "u": k.u, "v": k.v, "w": k.w, "h": k.h,
                    "z": k.z, "x": k.x, "y": k.y, "keycode": k.keycode,
                    "label": k.label, "label_color": k.label_color,
                    "label_size": k.label_size, "scale": k.scale, "opacity": k.opacity,
                    **(({"pressed_u": k.pressed_u} if k.pressed_u is not None else {}) |
                       ({"pressed_v": k.pressed_v} if k.pressed_v is not None else {})),
                }
                for k in self.keys
            ],
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_key(self, key_id: str) -> Optional[SpriteKey]:
        for k in self.keys:
            if k.id == key_id:
                return k
        return None


class SpriteSheet:
    """Loads and renders from a sprite-sheet texture atlas."""

    def __init__(self, texture_path: str = ""):
        self._path = texture_path
        self._pixmap: Optional[QPixmap] = None
        self._image: Optional[QImage] = None  # For frost/blur backing
        if texture_path and os.path.exists(texture_path):
            self.load(texture_path)

    def load(self, path: str) -> bool:
        """Load a PNG/JPG texture. Returns True on success."""
        self._path = path
        if not path or not os.path.exists(path):
            self._pixmap = None
            self._image = None
            return False
        pm = QPixmap(path)
        if pm.isNull():
            self._pixmap = None
            self._image = None
            return False
        self._pixmap = pm
        self._image = pm.toImage()
        return True

    @property
    def is_loaded(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    @property
    def size(self) -> Tuple[int, int]:
        if self._pixmap:
            return (self._pixmap.width(), self._pixmap.height())
        return (0, 0)

    def draw_key(
        self,
        p: QPainter,
        key: SpriteKey,
        pressed: bool = False,
        config: Optional[SpriteConfig] = None,
    ) -> None:
        """Draw a single key from the sprite sheet."""
        if not self.is_loaded:
            # Fallback: draw a colored rectangle
            self._draw_fallback(p, key, pressed)
            return

        offset_u = config.pressed_offset_u if config else 0
        offset_v = config.pressed_offset_v if config else key.h
        rect = key.pressed_rect(offset_u, offset_v) if pressed else key.normal_rect()

        # Clip to texture bounds
        tex_w, tex_h = self.size
        rect = rect.intersected(QRect(0, 0, tex_w, tex_h))
        if rect.isNull():
            self._draw_fallback(p, key, pressed)
            return

        # Draw the sprite region at screen position
        dest = key.screen_rect()
        p.setOpacity(key.opacity)
        p.drawPixmap(dest, self._pixmap, QRectF(rect))

        # Draw label on top if present
        if key.label:
            p.setOpacity(1.0)
            p.setPen(QPen(QColor(key.label_color)))
            font = QFont("Segoe UI", max(8, int(key.label_size * key.scale)), QFont.Bold)
            p.setFont(font)
            p.drawText(dest, Qt.AlignCenter, key.label)

    def draw_all(
        self,
        p: QPainter,
        config: SpriteConfig,
        pressed_keys: set[str],
    ) -> None:
        """Draw all keys from a config, highlighting pressed ones."""
        # Sort by z-index for proper layering
        sorted_keys = sorted(config.keys, key=lambda k: k.z)
        for key in sorted_keys:
            is_pressed = key.id in pressed_keys or key.keycode in pressed_keys
            self.draw_key(p, key, pressed=is_pressed, config=config)

    def _draw_fallback(self, p: QPainter, key: SpriteKey, pressed: bool) -> None:
        """Fallback when no texture is loaded — draw a simple rounded rect."""
        dest = key.screen_rect()
        r = min(dest.width(), dest.height()) * 0.15

        # Background
        if pressed:
            bg = QColor("#4a4e5a")
        elif key.scale > 0:
            bg = QColor("#2a2d3a")
        else:
            bg = QColor("#1e2028")
        p.setBrush(QBrush(bg))
        border = QColor("#555555") if pressed else QColor("#3a3d4a")
        p.setPen(QPen(border, 1.5))
        p.drawRoundedRect(dest, r, r)

        # Top highlight (3D effect)
        if not pressed:
            hi = dest.adjusted(2, 2, -2, -dest.height() * 0.5)
            p.setBrush(QBrush(QColor(255, 255, 255, 15)))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(hi, max(0, r - 1), max(0, r - 1))

        # Pressed depth
        if pressed:
            depth = dest.adjusted(1, 2, -1, -1)
            p.setBrush(QBrush(QColor(255, 255, 255, 8)))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(depth, r, r)

        # Label
        if key.label:
            p.setOpacity(1.0)
            p.setPen(QPen(QColor(key.label_color)))
            font = QFont("Segoe UI", max(8, int(key.label_size * key.scale)), QFont.Bold)
            p.setFont(font)
            p.drawText(dest, Qt.AlignCenter, key.label)


# ===================================================================
# Built-in preset generators (no external PNG needed)
# ===================================================================

def generate_wasd_preset() -> SpriteConfig:
    """Generate a WASD + modifiers layout (no texture, pure drawn)."""
    cfg = SpriteConfig(name="WASD", default_w=50, default_h=50)
    # Row 0: W
    cfg.keys.append(SpriteKey(
        id="w", u=0, v=0, w=50, h=50, x=60, y=0,
        keycode="w", label="W", label_size=14,
    ))
    # Row 1: A S D
    for i, (tok, lbl) in enumerate([("a", "A"), ("s", "S"), ("d", "D")]):
        cfg.keys.append(SpriteKey(
            id=tok, u=0, v=0, w=50, h=50, x=i * 60, y=60,
            keycode=tok, label=lbl, label_size=14,
        ))
    # Row 2: SPACE
    cfg.keys.append(SpriteKey(
        id="space", u=0, v=0, w=170, h=50, x=0, y=120,
        keycode="space", label="SPACE", label_size=10,
        label_color="#ffd27f",
    ))
    return cfg


def generate_full_keyboard_preset() -> SpriteConfig:
    """Generate a full keyboard layout with common gaming keys."""
    cfg = SpriteConfig(name="Full Keyboard", default_w=40, default_h=40)
    # Number row
    row_y = 0
    for i, tok in enumerate(["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]):
        cfg.keys.append(SpriteKey(
            id=tok, u=0, v=0, w=40, h=40, x=i * 44, y=row_y,
            keycode=tok, label=tok.upper(), label_size=10,
        ))
    # QWERTY row
    row_y = 44
    for i, tok in enumerate(["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"]):
        cfg.keys.append(SpriteKey(
            id=tok, u=0, v=0, w=40, h=40, x=i * 44, y=row_y,
            keycode=tok, label=tok.upper(), label_size=10,
        ))
    # ASDF row
    row_y = 88
    for i, tok in enumerate(["a", "s", "d", "f", "g", "h", "j", "k", "l"]):
        cfg.keys.append(SpriteKey(
            id=tok, u=0, v=0, w=40, h=40, x=i * 44, y=row_y,
            keycode=tok, label=tok.upper(), label_size=10,
        ))
    # ZXCV row
    row_y = 132
    for i, tok in enumerate(["z", "x", "c", "v", "b", "n", "m"]):
        cfg.keys.append(SpriteKey(
            id=tok, u=0, v=0, w=40, h=40, x=i * 44, y=row_y,
            keycode=tok, label=tok.upper(), label_size=10,
        ))
    # Space bar
    cfg.keys.append(SpriteKey(
        id="space", u=0, v=0, w=220, h=40, x=88, y=176,
        keycode="space", label="SPACE", label_size=10,
        label_color="#ffd27f",
    ))
    # Modifiers
    cfg.keys.append(SpriteKey(
        id="shift", u=0, v=0, w=60, h=40, x=0, y=176,
        keycode="shift", label="SHIFT", label_size=8,
        label_color="#c8a6ff",
    ))
    cfg.keys.append(SpriteKey(
        id="ctrl", u=0, v=0, w=55, h=40, x=0, y=220,
        keycode="ctrl", label="CTRL", label_size=8,
        label_color="#c8a6ff",
    ))
    cfg.keys.append(SpriteKey(
        id="alt", u=0, v=0, w=55, h=40, x=60, y=220,
        keycode="alt", label="ALT", label_size=8,
        label_color="#c8a6ff",
    ))
    return cfg


def generate_gamepad_preset() -> SpriteConfig:
    """Generate a basic gamepad layout (face buttons + bumpers + sticks)."""
    cfg = SpriteConfig(name="Gamepad", default_w=44, h_offset=20, v_offset=20)
    # Face buttons (right side)
    btn_labels = {
        "gamepad_a": ("A", "#4ade80"),
        "gamepad_b": ("B", "#f87171"),
        "gamepad_x": ("X", "#60a5fa"),
        "gamepad_y": ("Y", "#fbbf24"),
    }
    cx, cy = 240, 80  # center of face buttons
    for i, (tok, (lbl, col)) in enumerate(btn_labels.items()):
        angle = i * 90 - 90  # top, right, bottom, left
        import math
        bx = cx + int(35 * math.cos(math.radians(angle)))
        by = cy + int(35 * math.sin(math.radians(angle)))
        cfg.keys.append(SpriteKey(
            id=tok, u=0, v=0, w=44, h=44, x=bx - 22, y=by - 22,
            keycode=tok, label=lbl, label_color=col, label_size=16,
        ))
    # Bumpers
    cfg.keys.append(SpriteKey(
        id="gamepad_lb", u=0, v=0, w=60, h=30, x=20, y=10,
        keycode="gamepad_lb", label="LB", label_size=10, label_color="#a0b8ff",
    ))
    cfg.keys.append(SpriteKey(
        id="gamepad_rb", u=0, v=0, w=60, h=30, x=260, y=10,
        keycode="gamepad_rb", label="RB", label_size=10, label_color="#a0b8ff",
    ))
    # D-Pad (left side)
    dpad_cx, dpad_cy = 80, 100
    dpad_items = [
        ("gamepad_up", "▲", 0, -30),
        ("gamepad_down", "▼", 0, 30),
        ("gamepad_left", "◄", -30, 0),
        ("gamepad_right", "►", 30, 0),
    ]
    for tok, lbl, dx, dy in dpad_items:
        cfg.keys.append(SpriteKey(
            id=tok, u=0, v=0, w=30, h=30,
            x=dpad_cx + dx - 15, y=dpad_cy + dy - 15,
            keycode=tok, label=lbl, label_size=12,
        ))
    # Analog sticks (as visual indicators, not buttons)
    cfg.keys.append(SpriteKey(
        id="gamepad_ls", u=0, v=0, w=50, h=50, x=50, y=140,
        keycode="gamepad_ls", label="LS", label_size=9, label_color="#888",
    ))
    cfg.keys.append(SpriteKey(
        id="gamepad_rs", u=0, v=0, w=50, h=50, x=230, y=140,
        keycode="gamepad_rs", label="RS", label_size=9, label_color="#888",
    ))
    return cfg
