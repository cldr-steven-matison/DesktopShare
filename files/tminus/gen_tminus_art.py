#!/usr/bin/env python3
"""Launch art for tunastreet.tminus (#184).

The panel was a clock on black with a lot of empty middle. This is what fills
it: a rocket climbing out of a plume, drawn as a silhouette so the countdown
above it stays the loudest thing on the screen.

368x200, RGBA on a transparent ground -- it sits over the app's true black,
and an opaque backdrop would show as a box (the #205 sprite lesson).

Run: /home/tunas/tuna-starlink-app/backend/.venv/bin/python3 gen_tminus_art.py
"""
import math
import os
import random

from PIL import Image, ImageDraw

OUT = ("/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.tminus"
       "/res/images")
W, H = 368, 200

AMBER = (255, 176, 0, 255)
FLAME = (255, 120, 20, 255)
FLAME_HOT = (255, 232, 180, 255)
BODY = (214, 218, 226, 255)
BODY_DARK = (120, 126, 138, 255)
STAR = (150, 160, 180, 255)


def art():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Stars: fixed seed so the tile is identical on every regeneration --
    # a background that changes shape between builds is a diff nobody wants.
    rng = random.Random(2026)
    for _ in range(70):
        x, y = rng.randrange(W), rng.randrange(H - 40)
        r = rng.choice([0, 0, 0, 1])
        a = rng.randrange(40, 150)
        d.ellipse((x - r, y - r, x + r, y + r), fill=STAR[:3] + (a,))

    cx = W // 2
    top = 18            # nose tip
    body_w = 30
    body_bot = 128

    # Plume first, so the body paints over its top edge.
    for i, (spread, length, col, alpha) in enumerate([
        (34, 72, FLAME, 70), (22, 58, FLAME, 130), (12, 42, FLAME_HOT, 190),
    ]):
        d.polygon([(cx - spread, body_bot), (cx + spread, body_bot),
                   (cx + spread // 3, body_bot + length),
                   (cx, body_bot + length + 10),
                   (cx - spread // 3, body_bot + length)],
                  fill=col[:3] + (alpha,))

    # Fins.
    d.polygon([(cx - body_w // 2, body_bot - 34), (cx - body_w // 2 - 22, body_bot),
               (cx - body_w // 2, body_bot)], fill=BODY_DARK)
    d.polygon([(cx + body_w // 2, body_bot - 34), (cx + body_w // 2 + 22, body_bot),
               (cx + body_w // 2, body_bot)], fill=BODY_DARK)

    # Body + nose cone.
    d.rounded_rectangle((cx - body_w // 2, top + 34, cx + body_w // 2, body_bot),
                        radius=6, fill=BODY)
    d.polygon([(cx, top), (cx - body_w // 2, top + 40), (cx + body_w // 2, top + 40)],
              fill=BODY)
    d.ellipse((cx - 7, top + 48, cx + 7, top + 62), fill=(30, 34, 42, 255))
    d.rectangle((cx - body_w // 2, body_bot - 16, cx + body_w // 2, body_bot),
                fill=BODY_DARK)

    # Trajectory arc behind it -- the only thing here in the app's amber.
    for t in range(0, 100):
        a = t / 100.0
        x = cx - 150 + a * 300
        y = H - 6 - math.sin(a * math.pi) * 26
        if abs(x - cx) < 40:
            continue
        d.ellipse((x - 1, y - 1, x + 1, y + 1), fill=AMBER[:3] + (90,))

    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    img = art()
    path = os.path.join(OUT, "launch.png")
    img.save(path)
    print("wrote", path, img.size, img.mode)


if __name__ == "__main__":
    main()
