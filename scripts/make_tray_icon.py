"""One-off generator for the menu bar glyph (run manually, not at runtime).

    python scripts/make_tray_icon.py

Separate from scripts/make_icon.py, which resizes the approved artwork into
icon.icns, because this glyph cannot be derived from that artwork: flatten
icon_source.png and what you get is the silhouette of its rounded-square tile,
not the book. The mark is redrawn here instead, which is also why the two
scripts share no code — one resamples a photograph of a thing, the other draws
the thing.

The menu bar needs Imprint's mark drawn differently from the app icon: solid
black on transparent, no tile, no gradient, no glow. macOS treats that as a
template image and recolours it for a light or dark menu bar and for the
highlighted state, which is why the colour chosen here is thrown away.

Three shapes and no more — the open book, and the spark coming off it. The app
icon's tapering page, trailing comet and loose star dust are what make it a
mark at 512px and mush at 18px; the spark is kept because book-plus-spark is
what distinguishes Imprint from every other book glyph in a menu bar.

Drawn with QPainter rather than PIL so icon generation needs nothing the app
does not already depend on. Each size is rendered natively instead of being
downsampled from one master, which keeps the edges crisp at 18px.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPainter, QPainterPath

ASSETS = Path(__file__).resolve().parent.parent / "assets"

BLACK = QColor("#000000")

# macOS menu bar art is ~18pt; @2x covers Retina. Qt picks the @2x file up on
# its own when the base name is the one that was loaded.
TRAY_SIZES = {"tray.png": 18, "tray@2x.png": 36}

# The mark in unit coordinates (x right, y down), scaled to whatever size is
# being rendered. Written out rather than computed so the shape can be nudged
# by reading it.
# The book fills the box: at 18px a mark with polite margins is just a smaller
# mark. Everything below is tuned at 18px, not scaled down from a drawing that
# looked right large.
SPINE_GAP = 0.035         # half the gap between the two pages
PAGE_TOP_SPINE = 0.55     # the pages meet low and rise outward: that V is the
PAGE_TOP_OUTER = 0.36     # whole reason an open book reads as open.
PAGE_BOTTOM_SPINE = 0.94
PAGE_BOTTOM_OUTER = 0.79
PAGE_OUTER_X = 0.05

# Tucked into the corner, and kept clear of the page below it — at 18px two
# shapes a pixel apart are one shape.
SPARK_CENTRE = QPointF(0.81, 0.15)
SPARK_REACH = 0.145       # tip to centre
SPARK_WAIST = 0.04        # how fat the four arms are at the middle


def _page(size: int, mirrored: bool) -> QPainterPath:
    """One half of the open book, drawn from the spine outwards."""
    def point(x: float, y: float) -> QPointF:
        return QPointF((1.0 - x if mirrored else x) * size, y * size)

    spine_x = 0.5 - SPINE_GAP
    path = QPainterPath()
    path.moveTo(point(spine_x, PAGE_TOP_SPINE))
    # Top edge, bowed up: a straight line here reads as a paper aeroplane.
    path.cubicTo(
        point(0.35, 0.44), point(0.20, 0.36), point(PAGE_OUTER_X, PAGE_TOP_OUTER)
    )
    path.lineTo(point(PAGE_OUTER_X, PAGE_BOTTOM_OUTER))
    # Bottom edge back to the spine, bowed the other way, so the page has a
    # thickness that varies instead of being a parallelogram.
    path.cubicTo(
        point(0.20, 0.85), point(0.34, 0.90), point(spine_x, PAGE_BOTTOM_SPINE)
    )
    path.closeSubpath()
    return path


def _spark(size: int) -> QPainterPath:
    """A four-pointed star with concave sides — the shape in the app icon."""
    cx, cy = SPARK_CENTRE.x() * size, SPARK_CENTRE.y() * size
    reach = SPARK_REACH * size
    waist = SPARK_WAIST * size

    path = QPainterPath()
    path.moveTo(cx, cy - reach)
    # Each arm is two quadratic curves pulled in towards the centre, which is
    # what makes it a spark rather than a diamond.
    path.quadTo(cx + waist, cy - waist, cx + reach, cy)
    path.quadTo(cx + waist, cy + waist, cx, cy + reach)
    path.quadTo(cx - waist, cy + waist, cx - reach, cy)
    path.quadTo(cx - waist, cy - waist, cx, cy - reach)
    path.closeSubpath()
    return path


def draw_tray(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    # One flat black everywhere: a template image is recoloured wholesale, so a
    # partial alpha reads as a smudge rather than as depth.
    brush = QBrush(BLACK)
    painter.fillPath(_page(size, mirrored=False), brush)
    painter.fillPath(_page(size, mirrored=True), brush)
    painter.fillPath(_spark(size), brush)
    painter.end()
    return image


def main() -> int:
    QGuiApplication([])  # QImage/QPainter need an application instance.

    for name, px in TRAY_SIZES.items():
        if not draw_tray(px).save(str(ASSETS / name)):
            print(f"Failed to write {name}", file=sys.stderr)
            return 1

    print(f"Wrote {len(TRAY_SIZES)} menu bar PNGs to {ASSETS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
