#!/usr/bin/env python3
"""Generate the sprite PNGs for tunastreet.racing (#205, #221).

The sprites are the browser game's own inline SVGs, rasterised at panel scale --
not redrawn by hand. `extract()` lifts the `<svg>` literals straight out of the
upstream game's single-file source (`services/game/index.html` in the
`cloudera-racing-standalone` checkout) and vendors them into
`upstream_sprites.json` next to this script, so the generator still runs on a
device that has no upstream checkout. Point RACING_UPSTREAM at the checkout, or
pass --refresh, to re-vendor after upstream changes.

Each sprite is rasterised at 6x, cropped to its ink bounds and scaled to fill
its declared slot (44x44 obstacles, 56x74 cars). The crop matters: upstream's
viewBoxes carry generous whitespace, which at 44px would leave the drawn shape
much smaller than the 44px hit box the game tests against. PNG with a fully
transparent ground -- an opaque backdrop renders as a visible black box around
every sprite on the panel's true-black road.

Run: ~/venv/bin/python3 gen_racing_art.py   (needs cairosvg + PIL)
"""
import io
import json
import os
import re
import sys

import cairosvg
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
VENDORED = os.path.join(HERE, "upstream_sprites.json")
UPSTREAM = os.environ.get(
    "RACING_UPSTREAM",
    os.path.expanduser("~/cloudera-racing-standalone"),
)
OUT = "/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.racing/res/images"

OBS = 44
CAR_W, CAR_H = 56, 74
SUPERSAMPLE = 6

# panel sprite name -> key in upstream_sprites.json. The upstream obstacle
# array has seven entries; the panel carries five of them plus the two
# villains and the power-up. obs0 (warning triangle) and obs6 (wrench) are
# upstream types this app does not spawn.
SPRITES = {
    "obs_cone.png": ("obs2", OBS, OBS),
    "obs_barrier.png": ("obs1", OBS, OBS),
    "obs_drum.png": ("obs5", OBS, OBS),
    "obs_rock.png": ("obs4", OBS, OBS),
    "obs_hazard.png": ("obs3", OBS, OBS),
    "obs_databricks.png": ("databricks", OBS, OBS),
    "obs_snowflake.png": ("snowflake", OBS, OBS),
    "obs_iceberg.png": ("iceberg", OBS, OBS),
    "car_corolla.png": ("car_corolla", CAR_W, CAR_H),
    "car_porsche.png": ("car_porsche", CAR_W, CAR_H),
}


def extract():
    """Lift the inline <svg> literals out of the upstream game's index.html."""
    path = os.path.join(UPSTREAM, "services", "game", "index.html")
    src = open(path).read()

    def after(fn, count):
        m = re.search(r"function\s+%s\s*\(" % fn, src)
        if not m:
            raise SystemExit("upstream changed: no %s() in %s" % (fn, path))
        return re.findall(r"<svg[\s\S]*?</svg>", src[m.start():m.start() + 6000])[:count]

    out = {
        "databricks": after("dbSVG", 1)[0],
        "snowflake": after("bearSVG", 1)[0],
        "iceberg": after("icebergSVG", 1)[0],
    }
    out["car_corolla"], out["car_porsche"] = after("carSVG", 2)
    for i, svg in enumerate(after("obsSVG", 7)):
        out["obs%d" % i] = svg
    if len(out) != 12:
        raise SystemExit("upstream changed: extracted %d sprites, expected 12" % len(out))
    return out


def load(refresh):
    if refresh or not os.path.exists(VENDORED):
        sprites = extract()
        with open(VENDORED, "w") as fh:
            json.dump(sprites, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("vendored %d upstream SVGs -> %s" % (len(sprites), VENDORED))
        return sprites
    return json.load(open(VENDORED))


def render(svg, w, h):
    """Rasterise, crop to ink, scale to fill w x h, centred on transparent."""
    png = cairosvg.svg2png(
        bytestring=svg.encode(), output_width=w * SUPERSAMPLE, output_height=h * SUPERSAMPLE
    )
    big = Image.open(io.BytesIO(png)).convert("RGBA")
    box = big.getbbox()
    if box:
        big = big.crop(box)
    scale = min(w / big.width, h / big.height)
    size = (max(1, round(big.width * scale)), max(1, round(big.height * scale)))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.alpha_composite(big.resize(size, Image.LANCZOS), ((w - size[0]) // 2, (h - size[1]) // 2))
    return img


if __name__ == "__main__":
    sprites = load("--refresh" in sys.argv)
    for name, (key, w, h) in SPRITES.items():
        img = render(sprites[key], w, h)
        img.save(os.path.join(OUT, name))
        print("wrote", name, img.size)
