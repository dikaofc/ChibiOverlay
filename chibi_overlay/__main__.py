"""Allow `python -m chibi_overlay` to launch the overlay."""
from __future__ import annotations

try:
    from .app import main
except ImportError:
    from app import main

if __name__ == "__main__":
    raise SystemExit(main())
