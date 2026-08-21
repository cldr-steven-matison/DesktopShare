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
    img = Image.new("RGBA", (SZ, SZ), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Tile ground: near-black plate so the trace has something to sit on
    # without lighting up the whole launcher cell.
    rounded(d, (2, 2, SZ - 3, SZ - 3), 18, DARK)

    # The trace: flat line, one tall spike, flat line again. Coordinates are
    # hand-placed rather than computed -- the shape only has to read at 92px.
    mid = SZ // 2
    trace = [
        (10, mid), (26, mid), (32, mid - 6), (38, mid + 4),
        (44, mid - 26), (50, mid + 22), (56, mid), (66, mid), (82, mid),
    ]
    d.line(trace, fill=ORANGE, width=5, joint="curve")

    # The beat itself -- the one green thing on the tile.
    d.line([(44, mid - 26), (50, mid + 22)], fill=GREEN, width=5)
    d.ellipse((78, mid - 5, 88, mid + 5), fill=GREEN)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    img = icon()
    path = os.path.join(OUT, "launcher_icon.png")
    img.save(path)
    print("wrote", path, img.size, img.mode)


if __name__ == "__main__":
    main()
