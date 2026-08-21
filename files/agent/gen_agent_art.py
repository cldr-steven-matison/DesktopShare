#!/usr/bin/env python3
"""Launcher icon for tunastreet.agent (#197).

The Agent tile used to be the native status app, whose tile was text. A runtime
package gets a real icon, so this draws one: an ECG trace in Cloudera orange
across a true-black tile, with the beat spike picked out in live-green -- the
same heartbeat idea the app screen uses, readable at 92px on the launcher grid.

RGBA with a transparent ground: an opaque backdrop shows as a visible box on
the launcher's black (the sprite lesson from #205).

Run: /home/tunas/tuna-starlink-app/backend/.venv/bin/python3 gen_agent_art.py
"""
import os

from PIL import Image, ImageDraw

OUT = "/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.agent/res/images"
SZ = 92
ORANGE = (249, 103, 2, 255)
GREEN = (34, 197, 94, 255)
DARK = (26, 26, 26, 255)


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def icon():
    """A monitor trace, not a line drawing.

    The first pass used a 5px stroke on a small inset plate; at 92px next to
    RACING's full-bleed flag and T-MINUS's slab "T-" it read as a scratch.
    This one is full-bleed, 9px strokes, and the spike runs most of the tile's
    height so the shape is legible before you've focused on it.
    """
    img = Image.new("RGBA", (SZ, SZ), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Full-bleed plate, matching the weight of the other launcher tiles.
    rounded(d, (0, 0, SZ - 1, SZ - 1), 20, DARK)

    mid = SZ // 2
    # Baseline in, tall spike, baseline out. Hand-placed -- it only has to
    # read at 92px.
    d.line([(6, mid), (28, mid)], fill=ORANGE, width=9, joint="curve")
    d.line([(28, mid), (36, mid - 12)], fill=ORANGE, width=9, joint="curve")
    d.line([(36, mid - 12), (44, mid + 10)], fill=ORANGE, width=9, joint="curve")
    # The beat itself, in live-green: up hard, down hard, back to baseline.
    d.line([(44, mid + 10), (52, mid - 34)], fill=GREEN, width=9, joint="curve")
    d.line([(52, mid - 34), (60, mid + 30)], fill=GREEN, width=9, joint="curve")
    d.line([(60, mid + 30), (68, mid)], fill=GREEN, width=9, joint="curve")
    d.line([(68, mid), (86, mid)], fill=ORANGE, width=9, joint="curve")

    # Terminal pip -- the "still beating" dot the app's sweep also uses.
    d.ellipse((76, mid - 9, 92 - 2, mid + 7), fill=GREEN)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    img = icon()
    path = os.path.join(OUT, "launcher_icon.png")
    img.save(path)
    print("wrote", path, img.size, img.mode)


if __name__ == "__main__":
    main()
