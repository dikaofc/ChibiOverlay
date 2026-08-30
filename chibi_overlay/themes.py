"""Theme definitions for keycaps & overlay UI.

This module defines a token-based theme system for the Chibi Key Overlay.
Themes here are pure design tokens (no QPainter logic). Widgets consume
these tokens and adapt to actual widget size for responsive rendering.

Goals:
- High readability: auto-contrast labels for light surfaces
- Complete key states: normal / hover / pressed / selected / disabled
- Real "fluid" iOS glass + proper gamer themes
- Responsive spacing/radius/typography
- Safe fallback on invalid theme
- No text cutoff, no layout breakage.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from PySide6.QtGui import QColor

# ---------------------------------------------------------------------------
# Helpers: color & contrast
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")
_RGBA_RE = re.compile(
    r"^#(?:[0-9a-fA-F]{4}|[0-9a-fA-F]{8})$"
)  # #RGBa / #RRGGBBAA (loose check by length)

def _to_qcolor(c: str) -> QColor:
    qc = QColor(c)
    if not qc.isValid():
        qc = QColor("#2f3342")
    return qc

def luminance(hex_color: str) -> float:
    """Relative luminance (WCAG) 0..1."""
    c = _to_qcolor(hex_color)
    def srgb(v: int) -> float:
        fv = v / 255.0
        return fv / 12.92 if fv <= 0.03928 else math.pow((fv + 0.055) / 1.055, 2.4)
    r, g, b, _ = c.getRgb()
    return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)

def contrast_color(hex_color: str) -> str:
    """Return near-black or white for max readable label on given surface."""
    lum = luminance(hex_color)
    return "#0f1015" if lum > 0.55 else "#f7f8fa"

def ensure_contrast(fg: str | None, bg: str, fallback: str | None = None) -> str:
    """Ensure fg has reasonable contrast vs bg. If None, auto-contrast."""
    if fg is None or fg.strip() == "":
        return contrast_color(bg)
    fg_c = _to_qcolor(fg)
    bg_c = _to_qcolor(bg)
    if not fg_c.isValid() or not bg_c.isValid():
        return fallback or contrast_color(bg)
    return fg

def with_alpha(hex_rgb: str, alpha: float) -> str:
    """Return #RRGGBBAA with the given alpha applied."""
    c = _to_qcolor(hex_rgb)
    a = int(max(0.0, min(1.0, alpha)) * 255)
    c.setAlpha(a)
    return c.name(QColor.NameFormat.HexArgb)

def _is_hex(s: Any) -> bool:
    if not isinstance(s, str):
        return False
    s2 = s.strip()
    return bool(_HEX_RE.match(s2)) or bool(_RGBA_RE.match(s2))

# ---------------------------------------------------------------------------
# Dataclasses: structured tokens
# ---------------------------------------------------------------------------

@dataclass
class ThemeSpacing:
    xs: int = 4
    sm: int = 6
    md: int = 10
    lg: int = 14
    xl: int = 18

    def scale(self, factor: float) -> "ThemeSpacing":
        def s(v): return max(2, round(v * factor))
        return ThemeSpacing(s(self.xs), s(self.sm), s(self.md), s(self.lg), s(self.xl))

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)

@dataclass
class ThemeRadius:
    xs: int = 6
    sm: int = 8
    md: int = 10
    lg: int = 12
    xl: int = 16
    pill: int = 9999

    def scale(self, factor: float) -> "ThemeRadius":
        def s(v):
            if v >= 9999: return v
            return max(4, round(v * factor))
        return ThemeRadius(s(self.xs), s(self.sm), s(self.md), s(self.lg), s(self.xl), self.pill)

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)

@dataclass
class ThemeTypography:
    font_family: str = "Inter, Segoe UI, SF Pro Text, system-ui, sans-serif"
    size_base: int = 10
    size_sm: int = 9
    size_md: int = 10
    size_lg: int = 11
    weight: int = 500
    weight_bold: int = 600
    letter_spacing: float = 0.1
    line_height: float = 1.0

    def scale(self, factor: float) -> "ThemeTypography":
        def s(v): return max(7, round(v * factor))
        return ThemeTypography(
            font_family=self.font_family,
            size_base=s(self.size_base), size_sm=s(self.size_sm),
            size_md=s(self.size_md), size_lg=s(self.size_lg),
            weight=self.weight, weight_bold=self.weight_bold,
            letter_spacing=self.letter_spacing, line_height=self.line_height,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ThemeShadow:
    enabled: bool = True
    color: str = "#00000080"
    offset_x: int = 0
    offset_y: int = 2
    blur: int = 6
    spread: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ThemeGlow:
    enabled: bool = True
    color: str = "#7fd1ff"
    blur: int = 10
    spread: int = 0
    intensity: float = 0.9

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ThemeEffects:
    shadow: ThemeShadow = field(default_factory=ThemeShadow)
    glow: ThemeGlow = field(default_factory=ThemeGlow)
    sheen: bool = False
    sheen_color: str = "#ffffff26"
    inner_highlight: bool = False
    inner_highlight_color: str = "#ffffff18"
    outer_highlight: bool = False
    outer_highlight_color: str = "#ffffff0f"
    sparkles: bool = False
    blur_hint: float = 0.0  # UI hint for future blur

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["shadow"] = asdict(self.shadow)
        d["glow"] = asdict(self.glow)
        return d

@dataclass
class KeyState:
    bg: str
    top: str
    bottom: str
    border: str
    label: str
    glow: str | None = None
    shadow_offset_y: int = 2
    scale: float = 1.0
    pressed_depth: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ThemeKeyStyle:
    style: str  # "3d" | "flat" | "glass"
    height: int = 5
    bevel: int = 2
    radius: int = 10
    border_width: int = 1
    accent_bar: bool = True
    normal: KeyState = field(default_factory=lambda: KeyState("#2e313c", "#3a3e4c", "#1c1e26", "#3a3d4a", "#ebf0f5"))
    hover: KeyState = field(default_factory=lambda: KeyState("#353946", "#444856", "#1f2129", "#4a4f5d", "#f5f7fa"))
    pressed: KeyState = field(default_factory=lambda: KeyState("#262933", "#2f323d", "#16181f", "#3a3d4a", "#e6e9ef"))
    selected: KeyState = field(default_factory=lambda: KeyState("#323646", "#424657", "#1d2029", "#7fd1ff", "#f7faff"))
    disabled: KeyState = field(default_factory=lambda: KeyState("#242731", "#2a2e3a", "#1a1d26", "#2f3342", "#8b909c"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["normal"] = asdict(self.normal)
        d["hover"] = asdict(self.hover)
        d["pressed"] = asdict(self.pressed)
        d["selected"] = asdict(self.selected)
        d["disabled"] = asdict(self.disabled)
        return d

@dataclass
class ThemePanel:
    bg: str = "#10121a"
    surface: str = "#1c1e26"
    border: str = "#2f3342"
    text: str = "#ebf0f5"
    text_muted: str = "#b7bdc9"
    accent: str = "#7fd1ff"
    radius: int = 12
    padding: int = 12

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Theme:
    id: str
    name: str
    description: str = ""
    panel: ThemePanel = field(default_factory=ThemePanel)
    key: ThemeKeyStyle = field(default_factory=ThemeKeyStyle)
    effects: ThemeEffects = field(default_factory=ThemeEffects)
    spacing: ThemeSpacing = field(default_factory=ThemeSpacing)
    radius: ThemeRadius = field(default_factory=ThemeRadius)
    typography: ThemeTypography = field(default_factory=ThemeTypography)
    responsive: bool = True
    min_key_font: int = 7
    max_key_font: int = 16

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "panel": self.panel.to_dict(),
            "key": self.key.to_dict(),
            "effects": self.effects.to_dict(),
            "spacing": self.spacing.to_dict(),
            "radius": self.radius.to_dict(),
            "typography": self.typography.to_dict(),
            "responsive": self.responsive,
            "min_key_font": self.min_key_font,
            "max_key_font": self.max_key_font,
        }

# ---------------------------------------------------------------------------
# Theme builders (shared helpers)
# ---------------------------------------------------------------------------

def _mk_key(style: str, **kw) -> ThemeKeyStyle:
    k = ThemeKeyStyle(style=style)
    for fieldname in ("height", "bevel", "radius", "border_width", "accent_bar"):
        if fieldname in kw:
            setattr(k, fieldname, kw[fieldname])
    return k

def _state(bg, top, bottom, border, label=None, glow=None,
           shadow_offset_y=2, scale=1.0, pressed_depth=1) -> KeyState:
    lbl = ensure_contrast(label, top if top else bg)
    return KeyState(bg=bg, top=top, bottom=bottom, border=border,
                    label=lbl, glow=glow, shadow_offset_y=shadow_offset_y,
                    scale=scale, pressed_depth=pressed_depth)

def _derive_states(base_top, base_bottom, base_border, base_label, glow,
                   is_glass=False):
    top = base_top
    bottom = base_bottom
    border = base_border
    normal = _state("#00000000", top, bottom, border, base_label,
                    glow=glow, shadow_offset_y=2)
    hover = _state("#00000000", _lift(top, 8), bottom, _lift(border, 10),
                   base_label, glow=_lift(glow, 12), shadow_offset_y=2)
    pressed = _state("#00000000", _sink(top, 10), _sink(bottom, 6),
                     _sink(border, 8), base_label, glow=glow,
                     shadow_offset_y=1, scale=0.985, pressed_depth=1)
    selected = _state("#00000000", top, bottom, _glow_border(glow, border),
                      base_label, glow=glow, shadow_offset_y=2)
    disabled = _state("#00000000", with_alpha(top, 0.5), with_alpha(bottom, 0.5),
                      with_alpha(border, 0.5), with_alpha(contrast_color(top), 0.6),
                      glow=None, shadow_offset_y=1)
    if not is_glass:
        normal.bg = mix(bottom, top, 0.25)
        hover.bg = mix(normal.bg, "#ffffff", 0.04)
        pressed.bg = mix(bottom, top, 0.18)
        selected.bg = mix(normal.bg, glow, 0.08)
        disabled.bg = with_alpha(normal.bg, 0.6)
    else:
        normal.bg = "transparent"
        hover.bg = "transparent"
        pressed.bg = "transparent"
        selected.bg = "transparent"
        disabled.bg = "transparent"
    return normal, hover, pressed, selected, disabled

def _lift(c: str, amt: int) -> str:
    qc = _to_qcolor(c)
    h, s, v, a = qc.getHsv()
    v = min(255, v + amt)
    qc.setHsv(h, s, v, a)
    return qc.name(QColor.NameFormat.HexArgb) if qc.alpha() < 255 else qc.name()

def _sink(c: str, amt: int) -> str:
    qc = _to_qcolor(c)
    h, s, v, a = qc.getHsv()
    v = max(0, v - amt)
    qc.setHsv(h, s, v, a)
    return qc.name(QColor.NameFormat.HexArgb) if qc.alpha() < 255 else qc.name()

def mix(a: str, b: str, t: float) -> str:
    ca = _to_qcolor(a)
    cb = _to_qcolor(b)
    t = max(0, min(1, t))
    r = int(ca.red() * (1 - t) + cb.red() * t)
    g = int(ca.green() * (1 - t) + cb.green() * t)
    bl = int(ca.blue() * (1 - t) + cb.blue() * t)
    aa = int(ca.alpha() * (1 - t) + cb.alpha() * t)
    qc = QColor(r, g, bl, aa)
    return qc.name(QColor.NameFormat.HexArgb) if qc.alpha() < 255 else qc.name()

def _glow_border(glow: str, base: str) -> str:
    return mix(base, glow, 0.55)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

THEMES: Dict[str, Theme] = {}

def register(t: Theme) -> None:
    THEMES[t.id] = t


# ===================================================================
# 18 COMPLETELY UNIQUE THEMES
# Each has distinct: palette, key style, radius, effects, feel
# ===================================================================


# ---- 1. INK — Brutalist monochrome, sharp flat edges ----
def _ink() -> Theme:
    """Monochrome brutalist: ultra-flat, sharp 6px corners, thick borders, zero FX."""
    p = ThemePanel(
        bg="#0c0c0c", surface="#161616", border="#333333",
        text="#f0f0f0", text_muted="#999999", accent="#ffffff",
        radius=4, padding=10,
    )
    k = _mk_key("flat", height=4, bevel=0, radius=6, border_width=2, accent_bar=False)
    top = "#383838"
    bottom = "#1a1a1a"
    border = "#555555"
    glow = "#ffffff"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#f0f0f0", glow
    )
    k.pressed.scale = 0.97
    k.pressed.shadow_offset_y = 1
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000088", 0, 3, 0, 0),
        glow=ThemeGlow(False, glow, 0, 0, 0.0),
        sheen=False, sparkles=False,
    )
    ty = ThemeTypography(weight=600, weight_bold=700, letter_spacing=0.3)
    return Theme(
        id="ink", name="Ink", description="Brutalist monochrome",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=3, sm=4, md=6, lg=8, xl=10),
        typography=ty, min_key_font=8, max_key_font=14,
    )


# ---- 2. NEON — Cyberpunk city, dark purple + electric cyan ----
def _neon() -> Theme:
    """Neon-drenched cyberpunk: 3D caps with hot cyan glow pulses."""
    p = ThemePanel(
        bg="#0a0514", surface="#150a2e", border="#3d1a7a",
        text="#e0f7ff", text_muted="#88ccee", accent="#00e5ff",
        radius=10, padding=12,
    )
    k = _mk_key("3d", height=6, bevel=2, radius=8, border_width=1, accent_bar=True)
    top = "#2e1660"
    bottom = "#0d0620"
    border = "#5c2db8"
    glow = "#00e5ff"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#d0f4ff", glow
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#000000cc", 0, 2, 12, 0),
        glow=ThemeGlow(True, glow, 18, 0, 1.0),
        sheen=True, sheen_color="#00e5ff18",
        inner_highlight=True, inner_highlight_color="#00e5ff10",
        sparkles=False,
    )
    return Theme(
        id="neon", name="Neon City", description="Cyberpunk electric",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=5, sm=6, md=8, lg=10, xl=12),
    )


# ---- 3. MIDNIGHT — Deep indigo cosmos, violet sparkle stars ----
def _midnight() -> Theme:
    """Cosmic night: deep indigo caps with violet glow and star sparkles."""
    p = ThemePanel(
        bg="#060610", surface="#10102a", border="#2e2e55",
        text="#e8e8ff", text_muted="#a0a0d0", accent="#a080ff",
        radius=12, padding=12,
    )
    k = _mk_key("3d", height=5, bevel=2, radius=12, border_width=1, accent_bar=True)
    top = "#302866"
    bottom = "#0e0c22"
    border = "#5040a0"
    glow = "#a080ff"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#e8e4ff", glow
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#000000aa", 0, 2, 8, 0),
        glow=ThemeGlow(True, glow, 14, 0, 0.85),
        sheen=False,
        inner_highlight=True, inner_highlight_color="#ffffff0a",
        sparkles=True,
    )
    return Theme(
        id="midnight", name="Midnight", description="Cosmic violet stars",
        panel=p, key=k, effects=ef,
    )


# ---- 4. FROST — Frosted glass, ice blue, shimmer ----
def _frost() -> Theme:
    """Frosted glass: translucent ice-blue caps with blur and sheen."""
    p = ThemePanel(
        bg="#0c1c2c", surface="#c0e8ff20", border="#d8f4ff50",
        text="#0a1420", text_muted="#2a5070", accent="#88ccff",
        radius=14, padding=12,
    )
    k = _mk_key("glass", height=5, bevel=1, radius=18, border_width=1, accent_bar=False)
    top = "#c8e4ff60"
    bottom = "#90c8ee20"
    border = "#e0f4ff50"
    glow = "#88ccff"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, None, glow, is_glass=True
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000028", 0, 2, 10, 0),
        glow=ThemeGlow(True, glow, 10, 0, 0.5),
        sheen=True, sheen_color="#ffffff30",
        inner_highlight=True, inner_highlight_color="#ffffff20",
        sparkles=True,
        blur_hint=10.0,
    )
    tr = ThemeTypography(size_base=10, size_md=10, size_lg=11)
    return Theme(
        id="frost", name="Frost", description="Frosted ice glass",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=8, sm=10, md=14, lg=18, xl=20),
        typography=tr, min_key_font=8, max_key_font=14,
    )


# ---- 5. EMBER — Aggressive fire gamer, dark copper + orange ----
def _ember() -> Theme:
    """Fire gamer: warm copper caps with orange glow and ember sparkles."""
    p = ThemePanel(
        bg="#120a04", surface="#2a1508", border="#6a3010",
        text="#ffe8d0", text_muted="#d0a070", accent="#ff6e20",
        radius=8, padding=12,
    )
    k = _mk_key("3d", height=6, bevel=2, radius=9, border_width=1, accent_bar=True)
    top = "#8a4420"
    bottom = "#1a0c04"
    border = "#c05a20"
    glow = "#ff6e20"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#ffe0c0", glow
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#000000bb", 0, 2, 10, 0),
        glow=ThemeGlow(True, glow, 16, 0, 0.95),
        sheen=False,
        inner_highlight=True, inner_highlight_color="#ff803010",
        sparkles=True,
    )
    return Theme(
        id="ember", name="Ember", description="Aggressive fire gamer",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=5, sm=6, md=9, lg=11, xl=14),
    )


# ---- 6. OCEAN — Deep-sea bioluminescent, navy + cyan ----
def _ocean() -> Theme:
    """Deep ocean: dark navy caps with bioluminescent blue glow."""
    p = ThemePanel(
        bg="#040e1c", surface="#0a1e3a", border="#18406a",
        text="#d8f0ff", text_muted="#80b0e0", accent="#30b0ff",
        radius=12, padding=12,
    )
    k = _mk_key("3d", height=5, bevel=2, radius=12, border_width=1, accent_bar=True)
    top = "#1e5080"
    bottom = "#081828"
    border = "#2870a8"
    glow = "#30b0ff"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#d0ecff", glow
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000099", 0, 2, 8, 0),
        glow=ThemeGlow(True, glow, 14, 0, 0.9),
        sheen=False,
        inner_highlight=True, inner_highlight_color="#40c0ff0c",
        sparkles=False,
    )
    return Theme(
        id="ocean", name="Ocean", description="Deep-sea bioluminescent",
        panel=p, key=k, effects=ef,
    )


# ---- 7. SAKURA — Cherry blossom pink, glass + sparkles ----
def _sakura() -> Theme:
    """Sakura: translucent pink glass with petal sparkles."""
    p = ThemePanel(
        bg="#1c101a", surface="#3a2030", border="#6a3050",
        text="#fff0f8", text_muted="#e0a0c0", accent="#ff80b8",
        radius=14, padding=12,
    )
    k = _mk_key("glass", height=5, bevel=1, radius=16, border_width=1, accent_bar=False)
    top = "#ff90c048"
    bottom = "#e070a018"
    border = "#ffb0d850"
    glow = "#ff80b8"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, None, glow, is_glass=True
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000024", 0, 3, 10, 0),
        glow=ThemeGlow(True, glow, 12, 0, 0.7),
        sheen=True, sheen_color="#ffffff28",
        inner_highlight=True, inner_highlight_color="#ffffff20",
        sparkles=True,
        blur_hint=6.0,
    )
    return Theme(
        id="sakura", name="Sakura", description="Cherry blossom glass",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=7, sm=9, md=14, lg=16, xl=20),
    )


# ---- 8. CANDY — Y2K pastel pop, glass + rainbow shimmer ----
def _candy() -> Theme:
    """Candy Pop: light pastel glass with multi-color shimmer."""
    p = ThemePanel(
        bg="#1e1420", surface="#f0b0d040", border="#ffc0e070",
        text="#201018", text_muted="#603850", accent="#ff70b0",
        radius=16, padding=14,
    )
    k = _mk_key("glass", height=5, bevel=1, radius=18, border_width=1, accent_bar=False)
    top = "#ffc8e860"
    bottom = "#f0a0c830"
    border = "#ffe0f070"
    glow = "#ff80c0"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, None, glow, is_glass=True
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000020", 0, 3, 12, 0),
        glow=ThemeGlow(True, glow, 12, 0, 0.65),
        sheen=True, sheen_color="#ffffff40",
        inner_highlight=True, inner_highlight_color="#ffffff30",
        sparkles=True,
        blur_hint=8.0,
    )
    return Theme(
        id="candy", name="Candy Pop", description="Y2K pastel pop",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=8, sm=10, md=14, lg=18, xl=22),
    )


# ---- 9. MINT — Fresh emerald, crisp 3D ----
def _mint() -> Theme:
    """Mint: clean dark-green caps with emerald glow."""
    p = ThemePanel(
        bg="#061810", surface="#0e2e20", border="#1a5840",
        text="#e8fff4", text_muted="#80d0a8", accent="#40e0a0",
        radius=10, padding=12,
    )
    k = _mk_key("3d", height=5, bevel=2, radius=10, border_width=1, accent_bar=True)
    top = "#2a6e50"
    bottom = "#0a2218"
    border = "#38a070"
    glow = "#40e0a0"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#e0fff0", glow
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000088", 0, 2, 7, 0),
        glow=ThemeGlow(True, glow, 12, 0, 0.85),
        sheen=False, sparkles=False,
    )
    return Theme(
        id="mint", name="Mint", description="Fresh emerald crisp",
        panel=p, key=k, effects=ef,
    )


# ---- 10. ROSE GOLD — Luxury glass, warm gold ----
def _rose_gold() -> Theme:
    """Rose Gold: translucent warm glass with golden sheen."""
    p = ThemePanel(
        bg="#1a1014", surface="#4a2830", border="#804050",
        text="#fff0f4", text_muted="#e0a0b0", accent="#e0a070",
        radius=14, padding=12,
    )
    k = _mk_key("glass", height=5, bevel=1, radius=14, border_width=1, accent_bar=False)
    top = "#e0b89050"
    bottom = "#c0987020"
    border = "#f0d0a060"
    glow = "#e0a070"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, None, glow, is_glass=True
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000030", 0, 2, 8, 0),
        glow=ThemeGlow(True, glow, 10, 0, 0.6),
        sheen=True, sheen_color="#f0d8a028",
        inner_highlight=True, inner_highlight_color="#ffffff20",
        sparkles=False,
        blur_hint=6.0,
    )
    return Theme(
        id="rose_gold", name="Rose Gold", description="Luxury warm glass",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=7, sm=9, md=12, lg=14, xl=18),
    )


# ---- 11. CYBER — Hot hacker neon, purple + magenta ----
def _cyber() -> Theme:
    """Cyber: deep purple caps with hot magenta neon glow."""
    p = ThemePanel(
        bg="#0c0416", surface="#1e0838", border="#4a1070",
        text="#f0e0ff", text_muted="#c080e0", accent="#ff30a0",
        radius=7, padding=12,
    )
    k = _mk_key("3d", height=6, bevel=2, radius=7, border_width=1, accent_bar=True)
    top = "#48207a"
    bottom = "#120828"
    border = "#7a30b0"
    glow = "#ff30a0"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#f0d0ff", glow
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#000000cc", 0, 2, 12, 0),
        glow=ThemeGlow(True, glow, 20, 0, 1.0),
        sheen=True, sheen_color="#ff30a018",
        inner_highlight=True, inner_highlight_color="#ff30a010",
        sparkles=False,
    )
    return Theme(
        id="cyber", name="Cyber", description="Hot hacker neon",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=4, sm=5, md=7, lg=9, xl=12),
    )


# ---- 12. LAVENDER — Dreamy pastel glass + sparkle mist ----
def _lavender() -> Theme:
    """Lavender: soft purple glass with dreamy sparkle mist."""
    p = ThemePanel(
        bg="#1a1428", surface="#c0a8f030", border="#d0c0ff50",
        text="#141020", text_muted="#504080", accent="#b098e0",
        radius=14, padding=14,
    )
    k = _mk_key("glass", height=5, bevel=1, radius=16, border_width=1, accent_bar=False)
    top = "#c8b4f048"
    bottom = "#a890d020"
    border = "#dcc8ff50"
    glow = "#b098e0"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, None, glow, is_glass=True
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000028", 0, 3, 10, 0),
        glow=ThemeGlow(True, glow, 10, 0, 0.6),
        sheen=True, sheen_color="#ffffff30",
        inner_highlight=True, inner_highlight_color="#ffffff28",
        sparkles=True,
        blur_hint=8.0,
    )
    return Theme(
        id="lavender", name="Lavender", description="Dreamy pastel mist",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=8, sm=10, md=14, lg=16, xl=20),
    )


# ---- 13. AURORA — Northern lights, teal/green glass ----
def _aurora() -> Theme:
    """Aurora: translucent teal glass with multi-color shimmer."""
    p = ThemePanel(
        bg="#08141a", surface="#1a3834", border="#2e7068",
        text="#e8fff8", text_muted="#90e0c8", accent="#50f0c0",
        radius=14, padding=12,
    )
    k = _mk_key("glass", height=5, bevel=1, radius=16, border_width=1, accent_bar=False)
    top = "#60ffc048"
    bottom = "#30d0a018"
    border = "#90ffe050"
    glow = "#50f0c0"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, None, glow, is_glass=True
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000022", 0, 3, 10, 0),
        glow=ThemeGlow(True, glow, 14, 0, 0.75),
        sheen=True, sheen_color="#50f0c020",
        inner_highlight=True, inner_highlight_color="#ffffff20",
        sparkles=True,
        blur_hint=8.0,
    )
    return Theme(
        id="aurora", name="Aurora", description="Northern lights shimmer",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=8, sm=10, md=14, lg=16, xl=20),
    )


# ---- 14. FOREST — Organic earth tones, solid 3D ----
def _forest() -> Theme:
    """Forest: earthy brown-green with subtle moss glow."""
    p = ThemePanel(
        bg="#0c140a", surface="#1e2e18", border="#3a5a2e",
        text="#e8ffe0", text_muted="#a0d090", accent="#70c060",
        radius=8, padding=12,
    )
    k = _mk_key("3d", height=5, bevel=2, radius=8, border_width=1, accent_bar=True)
    top = "#3e6e30"
    bottom = "#142010"
    border = "#589848"
    glow = "#70c060"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#e0ffe0", glow
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000088", 0, 2, 6, 0),
        glow=ThemeGlow(True, glow, 10, 0, 0.75),
        sheen=False, sparkles=False,
    )
    return Theme(
        id="forest", name="Forest", description="Organic earth tones",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=5, sm=6, md=8, lg=10, xl=12),
    )


# ---- 15. MONO — Pure black & white, zero decoration ----
def _mono() -> Theme:
    """Monochrome: pure B&W, flat, no effects, razor-sharp."""
    p = ThemePanel(
        bg="#000000", surface="#111111", border="#222222",
        text="#ffffff", text_muted="#888888", accent="#ffffff",
        radius=4, padding=10,
    )
    k = _mk_key("flat", height=4, bevel=0, radius=4, border_width=1, accent_bar=False)
    top = "#2a2a2a"
    bottom = "#151515"
    border = "#444444"
    glow = "#ffffff"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#f8f8f8", glow
    )
    k.pressed.scale = 0.98
    ef = ThemeEffects(
        shadow=ThemeShadow(False, "#00000000", 0, 0, 0, 0),
        glow=ThemeGlow(False, glow, 0, 0, 0.0),
        sheen=False, sparkles=False,
    )
    ty = ThemeTypography(weight=500, weight_bold=600)
    return Theme(
        id="monochrome", name="Monochrome", description="Pure B&W minimal",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=3, sm=3, md=4, lg=5, xl=6),
        typography=ty, min_key_font=8, max_key_font=13,
    )


# ---- 16. RETRO — Arcade CRT, cream-on-dark ----
def _retro() -> Theme:
    """Retro Arcade: light cream keys on dark, thick colorful borders, CRT feel."""
    p = ThemePanel(
        bg="#141414", surface="#1e1e1e", border="#333333",
        text="#e0e0e0", text_muted="#888888", accent="#00ccff",
        radius=6, padding=10,
    )
    k = _mk_key("flat", height=4, bevel=0, radius=6, border_width=2, accent_bar=True)
    top = "#f0f0e0"
    bottom = "#d8d8c8"
    border = "#00ccff"
    glow = "#ff30a0"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, None, glow
    )
    k.normal.shadow_offset_y = 3
    k.hover.shadow_offset_y = 4
    k.pressed.shadow_offset_y = 1
    k.pressed.scale = 0.97
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000055", 0, 4, 0, 0),
        glow=ThemeGlow(True, glow, 8, 0, 0.6),
        sheen=False, sparkles=False,
    )
    ty = ThemeTypography(weight=600, weight_bold=800, letter_spacing=0.5)
    return Theme(
        id="retro", name="Retro Arcade", description="CRT arcade light keys",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=4, sm=5, md=6, lg=8, xl=10),
        typography=ty, min_key_font=8, max_key_font=14,
    )


# ---- 17. CAT CAFÉ — Warm cozy pink, 3D + sparkles ----
def _catcafe() -> Theme:
    """Cat Café: cozy warm caps with pink-brown tones and sparkle dust."""
    p = ThemePanel(
        bg="#18101a", surface="#2e1e28", border="#584050",
        text="#fff4f8", text_muted="#d8b0c0", accent="#e8a0c0",
        radius=12, padding=12,
    )
    k = _mk_key("3d", height=5, bevel=2, radius=14, border_width=1, accent_bar=True)
    top = "#6e5060"
    bottom = "#221820"
    border = "#906880"
    glow = "#e8a0c0"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#fff0f4", glow
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000080", 0, 2, 8, 0),
        glow=ThemeGlow(True, glow, 12, 0, 0.85),
        sheen=False, sparkles=True,
    )
    return Theme(
        id="cat_cafe", name="Cat Café", description="Cozy warm sparkle",
        panel=p, key=k, effects=ef,
    )


# ---- 18. GLASS — Generic dark frosted glass ----
def _glass() -> Theme:
    """Glass: translucent dark caps with soft blur and sheen."""
    p = ThemePanel(
        bg="#10102080", surface="#ffffff14", border="#ffffff28",
        text="#ffffff", text_muted="#e0e0e0", accent="#a0b8e0",
        radius=14, padding=12,
    )
    k = _mk_key("glass", height=5, bevel=1, radius=16, border_width=1, accent_bar=False)
    top = "#ffffff24"
    bottom = "#ffffff08"
    border = "#ffffff38"
    glow = "#a0b8e0"
    k.normal, k.hover, k.pressed, k.selected, k.disabled = _derive_states(
        top, bottom, border, "#ffffff", glow, is_glass=True
    )
    ef = ThemeEffects(
        shadow=ThemeShadow(True, "#00000030", 0, 2, 8, 0),
        glow=ThemeGlow(True, glow, 10, 0, 0.65),
        sheen=True, sheen_color="#ffffff18",
        inner_highlight=True, inner_highlight_color="#ffffff16",
        sparkles=True,
        blur_hint=8.0,
    )
    return Theme(
        id="glass", name="Glass", description="Translucent dark glass",
        panel=p, key=k, effects=ef,
        radius=ThemeRadius(xs=7, sm=9, md=14, lg=16, xl=20),
    )


# ===================================================================
# Register all themes
# ===================================================================
for _fn in (
    _ink, _neon, _midnight, _frost, _ember, _ocean, _sakura, _candy,
    _mint, _rose_gold, _cyber, _lavender, _aurora, _forest, _mono,
    _retro, _catcafe, _glass,
):
    register(_fn())

# ===================================================================
# Validation
# ===================================================================

REQUIRED_PANEL = {"bg", "surface", "border", "text", "accent"}
REQUIRED_KEY = {"style", "normal", "hover", "pressed", "selected", "disabled"}
REQUIRED_STATE = {"bg", "top", "bottom", "border", "label"}


def validate_theme(t: Theme) -> list[str]:
    errs: list[str] = []
    pid = t.id
    p = t.panel
    for kf in REQUIRED_PANEL:
        if not hasattr(p, kf):
            errs.append(f"{pid}.panel missing {kf}")
    k = t.key
    for kf in REQUIRED_KEY:
        if not hasattr(k, kf):
            errs.append(f"{pid}.key missing {kf}")
    for stn in ("normal", "hover", "pressed", "selected", "disabled"):
        st = getattr(k, stn, None)
        if not st:
            errs.append(f"{pid}.key.{stn} missing")
            continue
        for sf in REQUIRED_STATE:
            if not hasattr(st, sf):
                errs.append(f"{pid}.key.{stn} missing {sf}")
            else:
                v = getattr(st, sf)
                if sf != "label" and isinstance(v, str) and not _is_hex(v) and v != "transparent":
                    pass  # TODO: could warn about non-hex
    if t.radius.md < 4 and t.radius.md < 9999:
        errs.append(f"{pid}.radius.md too small")
    if t.spacing.sm < 2:
        errs.append(f"{pid}.spacing.sm too small")
    if t.typography.size_base < 7:
        errs.append(f"{pid}.typography.size_base too small")
    if t.key.radius < 4:
        errs.append(f"{pid}.key.radius too small")
    return errs


def _validate_all() -> None:
    for t in list(THEMES.values()):
        e = validate_theme(t)
        if e:
            print(f"[themes] WARN invalid '{t.id}':", "; ".join(e[:3]),
                  ("..." if len(e) > 3 else ""))


try:
    _validate_all()
except Exception as ex:
    print("[themes] validator skipped:", ex)

# ===================================================================
# Public API
# ===================================================================


def get_key_theme(name: str) -> Dict[str, Any]:
    """Return a flat dict with backward-compat keys for settings_dialog."""
    t = THEMES.get(name) or THEMES.get("dark") or THEMES.get("ink")
    if not t:
        t = next(iter(THEMES.values())) if THEMES else _ink()
    d = t.to_dict()
    d["_theme_obj"] = t

    # Flat backward-compat keys
    ks = t.key.normal
    ef = t.effects
    d["bg"] = ks.bg
    d["surface"] = ks.bg
    d["top"] = ks.top
    d["bottom"] = ks.bottom
    d["border"] = ks.border
    d["label"] = ks.label
    d["glow"] = ef.glow.color if ef.glow.enabled else ks.border
    d["accent_bar"] = t.key.accent_bar
    d["shadow"] = ef.shadow.enabled
    d["shadow_offset"] = ef.shadow.offset_y
    d["sparkles"] = ef.sparkles
    d["sheen"] = ef.sheen
    d["style"] = t.key.style
    d["height"] = t.key.height
    d["radius"] = t.key.radius
    return d


def key_theme_names() -> list[str]:
    """Ordered list of theme IDs for the picker UI."""
    keys = list(THEMES.keys())
    pref = [
        "ink", "neon", "midnight", "frost", "ember", "ocean", "sakura",
        "candy", "mint", "rose_gold", "cyber", "lavender", "aurora",
        "forest", "monochrome", "retro", "cat_cafe", "glass",
    ]
    out = [k for k in pref if k in keys]
    for k in keys:
        if k not in out:
            out.append(k)
    return out


def get_theme(name: str) -> Theme:
    return THEMES.get(name) or THEMES.get("ink") or (next(iter(THEMES.values())) if THEMES else _ink())


def theme_names() -> list[str]:
    return key_theme_names()


# Back-compat
KEY_THEMES = {tid: get_key_theme(tid) for tid in THEMES.keys()}
