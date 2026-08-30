"""Generate chibi_overlay.ico from the icon module.

Run once:  python generate_icon.py
Produces:  chibi_overlay.ico  (multi-size: 16, 24, 32, 48, 64, 128, 256)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
from chibi_overlay.icon import _draw_cat

app = QApplication(sys.argv)

sizes = [16, 24, 32, 48, 64, 128, 256]
pixmaps = []
for sz in sizes:
    pm = QPixmap(sz, sz)
    pm.fill(0)  # transparent
    from PySide6.QtGui import QPainter
    p = QPainter(pm)
    _draw_cat(p, sz)
    p.end()
    pixmaps.append(pm)

# PySide6 doesn't have a direct .ico writer, so write as .png first,
# then use Pillow to create the .ico.
try:
    from PIL import Image
    images = []
    for pm in pixmaps:
        # Convert QPixmap -> PIL Image via bytes
        ba = pm.toImage()
        # Write to buffer
        from PySide6.QtCore import QBuffer, QByteArray
        buf = QBuffer()
        buf.open(QBuffer.WriteOnly)
        ba.save(buf, "PNG")
        data = buf.data().data()
        buf.close()
        from io import BytesIO
        img = Image.open(BytesIO(data))
        images.append(img)

    out = os.path.join(os.path.dirname(__file__), "chibi_overlay.ico")
    images[0].save(out, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])
    print(f"Saved {out} ({len(images)} sizes)")
except ImportError:
    # Fallback: save largest as .png and note the user needs Pillow
    out = os.path.join(os.path.dirname(__file__), "chibi_overlay.png")
    pixmaps[-1].save(out)
    print(f"Pillow not installed — saved {out} (install Pillow: pip install Pillow)")
