# Chibi Overlay

A transparent, always-on-top desktop companion overlay for Windows, written
in Python. It shows a little chibi cat that looks at your mouse, blinks, and
reacts when you press keys or click — plus a visual keyboard that lights up
in real time with your physical keyboard/mouse.

Built with **PySide6** (transparent overlay), **pynput** (global input
hooks), and **Pillow**.

## Features

- Transparent, always-on-top overlay (click-through so it never blocks your game).
- Procedural chibi cat drawn with QPainter: eyes + head follow the mouse,
  periodic blinking, click/press "pop" reaction, idle breathing + tail sway.
- Optional GIF / image mode: drop in your own `idle.gif` / `my_chibi.png`.
- Visual key overlay: pick any keys (WASD, Space, Shift, Ctrl, LMB, RMB, …),
  each keycap animates on press/release.
- Edit mode: drag the chibi and keycaps anywhere, then it remembers positions.
- Mouse-follow sliders: follow strength, movement smoothing, eye movement.
- System tray icon + hotkeys: `Ctrl+Alt+S` settings, `Ctrl+Alt+C` edit toggle.
- Profile saved as JSON (`profiles/default.json`).

## Run (from source)

```bat
cd ChibiOverlay
.venv\Scripts\activate
python -m chibi_overlay
```

First run creates `profiles/default.json`. Right-click the tray paw icon for
Settings, or double-click it to open Settings fast.

## Add your own chibi

1. Open Settings → Character → "Import GIF / Image…"
2. Pick a `.gif` / `.png` / `.apng`. The procedural cat is replaced by your
   looping animation. Clear the path to go back to the drawn cat.
3. Save Profile.

## Add / remove keys

Settings → Key Overlay → pick a key from the dropdown → "+ Add Key".
Remove with "− Remove". In Edit Mode you can drag keycaps to position them.

## Package as .exe (PyInstaller)

```bat
pip install pyinstaller
pyinstaller chibi_overlay\spec\chibi_overlay.spec
```

Output lands in `dist/ChibiOverlay/`. On the target machine no Python install
is needed. Note: pynput registers global hooks, so Windows may show a
smartscreen prompt on first run — that's expected for any global hotkey app.

## Project layout

```
chibi_overlay/
├── __init__.py        public API (run, Profile, load_profile, …)
├── __main__.py        `python -m chibi_overlay`
├── app.py             QApplication + system tray + hotkeys
├── models.py          Profile / ChibiConfig / KeyConfig dataclasses
├── config.py          load/save/default profile (JSON)
├── input_listener.py  pynput keyboard+mouse, threaded, token matching
├── platform_win.py     Win32 click-through (WS_EX_TRANSPARENT) helper
├── chibi_widget.py    the cat (procedural + GIF mode)
├── key_widget.py      a single animated keycap
├── overlay_window.py  transparent window tying it all together
└── settings_dialog.py character/keys/sliders UI
profiles/              saved profiles (JSON)
```

## Notes / limitations

- Click-through uses `WS_EX_TRANSPARENT`; in Edit Mode it's disabled so you can
  drag widgets. Leave Edit Mode to re-enable pass-through.
- Multi-monitor positioning follows the primary screen; chibi/keycoords are
  absolute screen pixels stored in the profile.
- This is a working base, not a finished product — tweak the cat art, add
  sprite-part animation, sound reactions, per-key GIFs, etc.
