#!/usr/bin/env python3
"""Media tiles for tunastreet.xviewer (#198).

Most posts in the feed carry no media, and the panel's 368x220 card is the
biggest thing on the screen -- leaving it black for a text post throws away
half the glass. These are the tiles that fill it instead: a dark card with a
Tuna Street mark, in the three accent colours the app already uses, picked
per post so consecutive text posts don't look identical.

Sized 368x220 exactly, matching the backend's CARD_W x CARD_H contract, so a
tile and a real photo occupy the identical slot.

Run: /home/tunas/tuna-starlink-app/backend/.venv/bin/python3 gen_xviewer_art.py
"""
import os

from PIL import Image, ImageDraw

OUT = ("/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.xviewer"
       "/res/images")
W, H = 368, 220

INK = (240, 240, 240, 255)
DIM = (58, 58, 64, 255)
PLATE = (18, 18, 20, 255)

# One tile per accent: Cloudera orange, X-like blue-grey, live green.
ACCENTS = [
    ("tile_a", (249, 103, 2, 255)),
    ("tile_b", (110, 140, 170, 255)),
    ("tile_c", (34, 197, 94, 255)),
]


def tile(accent):
    img = Image.new("RGBA", (W, H), PLATE)
    d = ImageDraw.Draw(img)

    # A quiet diagonal weave so the card has texture instead of flat black --
    # kept far darker than the text that sits under it.
    for x in range(-H, W, 26):
        d.line([(x, H), (x + H, 0)], fill=DIM, width=1)

    # The mark: two bars crossing, the Tuna Street "street" cut. Hand-placed
    # coordinates -- it only has to read at 368x220 on a small panel.
    cx, cy = W // 2, H // 2 - 6
    d.line([(cx - 46, cy - 34), (cx + 46, cy + 34)], fill=accent, width=10)
    d.line([(cx + 46, cy - 34), (cx - 46, cy + 34)], fill=INK, width=10)
    d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=PLATE)
    d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=accent)

    # Baseline rule + wordmark, well inside the card's own edges.
    d.line([(cx - 74, cy + 62), (cx + 74, cy + 62)], fill=accent, width=3)
    d.text((cx - 52, cy + 70), "TUNA STREET", fill=DIM)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, accent in ACCENTS:
        img = tile(accent)
        path = os.path.join(OUT, name + ".png")
        img.save(path)
        print("wrote", path, img.size, img.mode)


if __name__ == "__main__":
    main()
