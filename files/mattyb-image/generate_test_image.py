#!/usr/bin/env python3
"""Generate the mattyB test image: 6 distinct-color shapes on a flat background.

Deterministic stand-in for an object-detection model's input — a flat neutral
background with six well-separated solid-color shapes laid out in a 3x2 grid.
Because the shapes are solid colors on a uniform background, `ShapeDetector`'s
contour detection finds exactly six boxes every run, with no ML dependency.

Standalone:  python3 generate_test_image.py [out.png]
Library:     from generate_test_image import make_test_image  # -> PNG bytes
"""
import sys
from PIL import Image, ImageDraw

BG = (245, 245, 245)          # flat, near-white background
W, H = 900, 600               # 3 cols x 2 rows of 300px cells
CELL = 300

# (name, RGB) — one solid color per shape, chosen to be far apart in RGB space
# so the detector's nearest-color labelling is unambiguous.
SHAPES = [
    ("red",    (220, 30, 30),   "circle"),
    ("green",  (30, 160, 30),   "square"),
    ("blue",   (30, 60, 200),   "triangle"),
    ("orange", (240, 140, 20),  "rectangle"),
    ("purple", (140, 30, 160),  "pentagon"),
    ("teal",   (20, 150, 150),  "ellipse"),
]


def _pentagon(cx, cy, r):
    import math
    return [
        (cx + r * math.sin(2 * math.pi * i / 5),
         cy - r * math.cos(2 * math.pi * i / 5))
        for i in range(5)
    ]


def make_test_image():
    """Render the test image and return it as PNG bytes."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for idx, (color_name, rgb, shape) in enumerate(SHAPES):
        col, row = idx % 3, idx // 3
        cx, cy = col * CELL + CELL // 2, row * CELL + CELL // 2
        pad = 60
        box = [col * CELL + pad, row * CELL + pad,
               col * CELL + CELL - pad, row * CELL + CELL - pad]
        if shape == "circle":
            d.ellipse(box, fill=rgb)
        elif shape == "ellipse":
            d.ellipse([box[0], box[1] + 25, box[2], box[3] - 25], fill=rgb)
        elif shape == "square":
            d.rectangle(box, fill=rgb)
        elif shape == "rectangle":
            d.rectangle([box[0] - 15, box[1] + 25, box[2] + 15, box[3] - 25], fill=rgb)
        elif shape == "triangle":
            d.polygon([(cx, box[1]), (box[0], box[3]), (box[2], box[3])], fill=rgb)
        elif shape == "pentagon":
            d.polygon(_pentagon(cx, cy, (CELL - 2 * pad) // 2), fill=rgb)
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "test-image.png"
    with open(out, "wb") as f:
        f.write(make_test_image())
    print(f"wrote {out}  ({W}x{H}, {len(SHAPES)} shapes)")
