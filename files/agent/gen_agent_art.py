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
    """One bold pulse, one colour.

    Third pass. The first was a 5px stroke on an inset plate (a scratch at
    92px); the second went full-bleed at 9px but kept two colours and a stray
    green pip, so it still read as scribble next to its neighbours. Looking at
    the four tiles together is what settled it: RACING is diagonal stripes,
    T-MINUS is a "T-" letterform, X VIEWER is a big X -- every one of them a
    single dominant shape you recognise before you focus. The agent tile was
    the only one without a silhouette.

    So: one spike, one colour, 14px strokes, running nearly the full height,
    on a flat baseline that anchors it. Live-green rather than Cloudera orange
    because two of the other three tiles are already orange and green is the
    agent's own ONLINE colour -- the tile should be findable by colour alone in
    a grid.
    """
    img = Image.new("RGBA", (SZ, SZ), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    rounded(d, (0, 0, SZ - 1, SZ - 1), 20, DARK)

    mid = SZ // 2
    w = 14
    # Flat baseline in, one tall spike, flat baseline out. The spike is
    # deliberately asymmetric (fast up, faster down, small overshoot) so it
    # reads as a beat and not as a chevron.
    d.line([(8, mid), (30, mid)], fill=GREEN, width=w, joint="curve")
    d.line([(30, mid), (42, 16)], fill=GREEN, width=w, joint="curve")
    d.line([(42, 16), (54, SZ - 18)], fill=GREEN, width=w, joint="curve")
    d.line([(54, SZ - 18), (62, mid)], fill=GREEN, width=w, joint="curve")
    d.line([(62, mid), (84, mid)], fill=GREEN, width=w, joint="curve")
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    img = icon()
    path = os.path.join(OUT, "launcher_icon.png")
    img.save(path)
    print("wrote", path, img.size, img.mode)


if __name__ == "__main__":
    main()
