#!/usr/bin/env python3
"""Generate the sprite PNGs for tunastreet.racing (#205).

The panel draws real vehicles and villains, not coloured blocks. Each sprite is
a redraw of the browser game's inline SVG (services/game/index.html) at panel
scale: 44x44 obstacles, 56x74 cars. PNG (not JPEG) because the S3 ROM decoder
is baseline-only and these need clean flat colour plus hard edges.

Run: python3 gen_racing_art.py   (needs PIL; the tuna-starlink venv has it)
"""
import os

from PIL import Image, ImageDraw

OUT = "/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.racing/res/images"
OBS = 44
CAR_W, CAR_H = 56, 74
BG = (15, 15, 15)


def new(w, h):
    img = Image.new("RGB", (w, h), BG)
    return img, ImageDraw.Draw(img)


def save(img, name):
    img.save(os.path.join(OUT, name))
    print("wrote", name, img.size)


# ---------------------------------------------------------------- the villains
def cone():
    img, d = new(OBS, OBS)
    d.polygon([(22, 5), (38, 39), (6, 39)], fill=(245, 166, 35))
    d.rectangle([4, 38, 40, 43], fill=(200, 130, 20))
    d.rectangle([14, 22, 30, 27], fill=(255, 255, 255))
    return img


def barrier():
    img, d = new(OBS, OBS)
    d.polygon([(22, 4), (37, 13), (37, 31), (22, 40), (7, 31), (7, 13)],
              fill=(229, 72, 77))
    d.rectangle([12, 20, 32, 25], fill=(255, 255, 255))
    return img


def drum():
    img, d = new(OBS, OBS)
    d.rounded_rectangle([12, 6, 32, 38], radius=3, fill=(192, 197, 204))
    d.rectangle([15, 3, 29, 8], fill=(138, 143, 152))
    d.rectangle([13, 16, 31, 20], fill=(107, 112, 121))
    d.rectangle([13, 26, 31, 30], fill=(107, 112, 121))
    return img


def rock():
    img, d = new(OBS, OBS)
    d.ellipse([8, 10, 36, 36], fill=(138, 143, 152))
    d.ellipse([13, 15, 21, 23], fill=(107, 112, 121))
    d.ellipse([23, 22, 32, 31], fill=(107, 112, 121))
    return img


def hazard():
    img, d = new(OBS, OBS)
    d.rounded_rectangle([5, 14, 39, 30], radius=2, fill=(245, 166, 35))
    for x in (6, 16, 26):
        d.line([(x, 30), (x + 9, 14)], fill=(28, 28, 28), width=4)
    return img


def databricks():
    """The red villain — stacked chevrons, from the game's dbSVG()."""
    img, d = new(OBS, OBS)
    d.rounded_rectangle([2, 2, 42, 42], radius=6, fill=(255, 54, 33))
    for i, y in enumerate((12, 19, 26, 33)):
        d.line([(9, y), (22, y - 6), (35, y)], fill=(255, 255, 255), width=3, joint="curve")
    return img


def snowflake():
    """The blue villain — the bear, from the game's bearSVG()."""
    img, d = new(OBS, OBS)
    d.ellipse([2, 2, 42, 42], fill=(41, 181, 232))
    d.ellipse([7, 6, 17, 16], fill=(232, 232, 238))
    d.ellipse([27, 6, 37, 16], fill=(232, 232, 238))
    d.ellipse([9, 12, 35, 36], fill=(240, 240, 246))
    d.ellipse([15, 18, 20, 24], fill=(41, 181, 232))
    d.ellipse([24, 18, 29, 24], fill=(41, 181, 232))
    d.ellipse([17, 25, 27, 32], fill=(212, 184, 150))
    d.ellipse([20, 25, 25, 29], fill=(34, 34, 34))
    return img


def iceberg():
    """The power-up — white peak over blue water, from icebergSVG()."""
    img, d = new(OBS, OBS)
    d.ellipse([2, 2, 42, 42], fill=(26, 107, 181))
    d.rectangle([2, 24, 42, 42], fill=(21, 87, 160))
    d.polygon([(22, 6), (34, 24), (10, 24)], fill=(232, 244, 248))
    d.polygon([(22, 6), (28, 17), (22, 20), (16, 17)], fill=(204, 232, 244))
    d.polygon([(10, 24), (34, 24), (30, 37), (14, 37)], fill=(122, 184, 216))
    return img


# -------------------------------------------------------------------- the cars
def car(kind):
    """Top-down car, from the game's carSVG() — Corolla white, 911 silver/red."""
    img, d = new(CAR_W, CAR_H)
    cx = CAR_W // 2
    if kind == "corolla":
        body, trim, glass = (242, 242, 242), (204, 34, 0), (42, 58, 90)
        d.ellipse([4, 3, CAR_W - 4, CAR_H - 3], fill=body)
        d.rounded_rectangle([14, 8, 42, 24], radius=4, fill=(17, 17, 17))
        d.rounded_rectangle([14, 50, 42, 66], radius=4, fill=(17, 17, 17))
        d.rounded_rectangle([17, 20, 39, 33], radius=3, fill=glass)
        d.rounded_rectangle([17, 44, 39, 55], radius=3, fill=(26, 42, 58))
        d.rounded_rectangle([20, 33, 36, 44], radius=2, fill=(232, 232, 232))
        d.rectangle([5, 30, 9, 44], fill=trim)
        d.rectangle([47, 30, 51, 44], fill=trim)
    else:
        body, hood, cabin = (200, 200, 204), (180, 180, 184), (176, 48, 16)
        d.ellipse([3, 4, CAR_W - 3, CAR_H - 4], fill=body)
        d.ellipse([12, 6, 44, 24], fill=(212, 212, 216))
        d.rounded_rectangle([15, 26, 41, 52], radius=5, fill=cabin)
        d.rounded_rectangle([17, 29, 26, 39], radius=2, fill=(200, 64, 32))
        d.rounded_rectangle([30, 29, 39, 39], radius=2, fill=(200, 64, 32))
        d.rounded_rectangle([17, 41, 26, 49], radius=2, fill=(200, 64, 32))
        d.rounded_rectangle([30, 41, 39, 49], radius=2, fill=(200, 64, 32))
        d.rounded_rectangle([18, 18, 38, 26], radius=3, fill=(42, 58, 90))
        d.rounded_rectangle([15, 56, 41, 62], radius=2, fill=hood)
    for wx, wy in ((2, 14), (CAR_W - 12, 14), (1, CAR_H - 26), (CAR_W - 11, CAR_H - 26)):
        d.ellipse([wx, wy, wx + 10, wy + 16], fill=(34, 34, 34))
        d.ellipse([wx + 3, wy + 4, wx + 7, wy + 12], fill=(150, 150, 150))
    return img


SPRITES = {
    "obs_cone.png": cone, "obs_barrier.png": barrier, "obs_drum.png": drum,
    "obs_rock.png": rock, "obs_hazard.png": hazard,
    "obs_databricks.png": databricks, "obs_snowflake.png": snowflake,
    "obs_iceberg.png": iceberg,
}

if __name__ == "__main__":
    for name, fn in SPRITES.items():
        save(fn(), name)
    save(car("corolla"), "car_corolla.png")
    save(car("porsche"), "car_porsche.png")
