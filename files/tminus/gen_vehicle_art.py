#!/usr/bin/env python3
"""Per-vehicle rocket art for tunastreet.tminus (#222).

The panel is a T-minus countdown app on an AMOLED display, where a "black"
background is actually off pixels. Generic launch-art placeholders don't cut
it for a per-vehicle art library -- this generates a photoreal image of the
named vehicle standing against pure black, then crops it to the panel's art
band (368x168, see gen_tminus_screen.py's ART_H=168) as a baseline JPEG.

Mirrors the proven wrapper at
/home/tunas/tuna-starlink-app/backend/services/xai_imagine.py: same client
construction, same size+aspect_ratio forcing to avoid portrait comebacks,
same one-shot retry without those params, same url/b64_json duality. This
script does not invent a new API client -- it is a thin CLI around the same
pattern, pointed at a prompt table instead of the Planet Hack style YAML.

Costs real money per image (xAI Imagine). Only pass the vehicle names you
actually want generated -- there is no "generate everything" mode by design.

Usage:
    /home/tunas/tuna-starlink-app/backend/.venv/bin/python \\
        gen_vehicle_art.py "Falcon 9" "Starship"

    # Re-run a single vehicle that came out badly:
    /home/tunas/tuna-starlink-app/backend/.venv/bin/python \\
        gen_vehicle_art.py "Falcon 9"

    # List known vehicles without generating anything:
    gen_vehicle_art.py --list

Env:
    XAI_API_KEY must be set (e.g. `source /home/tunas/.env` beforehand, or
    exported by the shell). Never printed, logged, or written by this script.

Output:
    files/tminus/vehicles/raw/<slug>.png   -- raw Imagine response, unedited
    files/tminus/vehicles/<slug>.jpg       -- 368x168 baseline JPEG, panel-ready
    files/tminus/vehicles/contact-sheet.png -- all processed tiles, refreshed
                                                each run, for eyeball approval
"""
from __future__ import annotations

import argparse
import base64
import io
import math
import os
import re
import sys
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
VEHICLES_DIR = os.path.join(HERE, "vehicles")
RAW_DIR = os.path.join(VEHICLES_DIR, "raw")
CONTACT_SHEET = os.path.join(VEHICLES_DIR, "contact-sheet.png")

ART_W, ART_H = 368, 168  # the T-minus art band -- NOT 368x220 (different app)

XAI_BASE_URL = "https://api.x.ai/v1"
XAI_IMAGE_MODEL = "grok-imagine-image"
XAI_IMAGE_SIZE = "1792x1024"
XAI_IMAGE_ASPECT_RATIO = "16:9"

# Background/lighting language, kept last so it survives truncation/
# de-prioritization by the model. Strengthened for the second #222 haze round
# (Starship/Soyuz 2.1b/New Glenn measured 5.95/11.67/7.24 border luminance --
# real light in the render, confirmed by a uniform elevation across every
# edge, not just corner bleed from the diagonal vehicle) with explicit
# negative clauses against haze/fog/glow/bloom/volumetric light/vignette/
# gradient, and a rule that the rim light lands on the vehicle only.
_BG_LIGHTING = (
    "Dramatic rim and side lighting so the vehicle reads clearly against "
    "black -- strong specular highlights along one edge, deep shadow on the "
    "other; the rim light falls on the vehicle's surface only and must never "
    "spill into the air or background around it. Pure black background "
    "(#000000), uniform and perfectly flat out to every edge of the frame: "
    "no sky, no clouds, no ground, no horizon line, no launch tower, no "
    "gantry, no pad structures, no crowd, no text, no logos, no watermark, "
    "no atmospheric haze, no fog, no glow, no light bloom, no volumetric "
    "lighting, no vignette, no gradient. Photorealistic render, studio-"
    "product-shot lighting isolated on black, sharp focus, high detail."
)

# Standard composition, promoted from the #222 variant experiment below
# (falcon-9-varC won the A/B/C comparison: whole vehicle at 0.65 frame-width,
# 0.00 border luminance, judged the safest standard across very different
# silhouettes -- pushing wider would mean edge-clipping, which reads
# differently on a pencil-thin Electron than on a fat Starship cone). Every
# vehicle in PROMPTS shares this composition; only the descriptive sentence
# in front of it changes per vehicle.
_COMPOSITION = (
    "The complete vehicle shown at a dynamic diagonal angle, spanning nearly "
    "corner to corner across the wide frame: nose close to the top-right "
    "corner, engine/base close to the bottom-left corner, so the rocket's "
    "full length spans most of the frame's diagonal. The rocket is the "
    "dominant subject, shot close to the camera so it is large in frame -- "
    "not a small object floating in empty space. Vehicle static at rest, not "
    "launching, no exhaust plume."
)

# Shared tail glued onto every vehicle prompt: composition, then the
# background/lighting language (unchanged since the first #222 run -- this
# is what measured 0.00 / 2.06 border luminance, keep it last so it survives
# truncation/de-prioritization by the model).
_COMMON_TAIL = " " + _COMPOSITION + " " + _BG_LIGHTING

PROMPTS: dict[str, str] = {
    "Falcon 9": (
        "Photorealistic SpaceX Falcon 9 rocket, white cylindrical first-stage "
        "body with the distinctive black interstage band, four silver grid "
        "fins deployed near the top of the first stage, single Merlin nozzle "
        "visible at the base, tall and slender proportions."
        + _COMMON_TAIL
    ),
    "Starship": (
        "Photorealistic SpaceX Starship stack: bare unpainted stainless-steel "
        "upper stage with its curved silver flaps and blunt nose, stacked "
        "atop the wider Super Heavy booster with its ring of Raptor engines "
        "visible at the base, brushed-metal sheen catching the light, massive "
        "and imposing scale."
        + _COMMON_TAIL
    ),
    "Falcon Heavy": (
        "Photorealistic SpaceX Falcon Heavy rocket: three white Falcon-9-"
        "derived cores strapped side by side, black interstage bands on each, "
        "silver grid fins near the top of every core, a dense cluster of 27 "
        "Merlin nozzles visible across the base, noticeably wider and more "
        "massive than a single-core Falcon 9."
        + _COMMON_TAIL
    ),
    "Electron": (
        "Photorealistic Rocket Lab Electron rocket: the entire body from nose "
        "to base is deep matte black carbon-composite -- black, not white, "
        "not silver, not grey, a non-reflective black carbon-fiber weave "
        "texture over the whole airframe. Small and slender, narrow diameter, "
        "no grid fins, a small cluster of Rutherford engine nozzles visible "
        "at the base, noticeably more compact and pencil-thin than a "
        "Falcon 9. Because the body is black on a black background, a bright "
        "thin specular rim-light traces the entire silhouette edge of the "
        "vehicle -- nose, sides, fins, and base -- so its outline separates "
        "clearly from the background; the body surface itself stays a deep "
        "black, only the edge highlight is bright."
        + _COMMON_TAIL
    ),
    "Vulcan": (
        "Photorealistic ULA Vulcan Centaur rocket: white cylindrical core "
        "body, twin BE-4 engine nozzles at the base, two solid rocket "
        "boosters strapped to the sides of the core near the base, a large "
        "bulbous payload fairing at the top wider than the core body."
        + _COMMON_TAIL
    ),
    "Ariane 62": (
        "Photorealistic Ariane 62 rocket: white cylindrical core body, a "
        "single Vulcain engine nozzle at the base, two white solid rocket "
        "boosters strapped to the sides of the core, a large payload fairing "
        "at the top, clean European-launcher styling."
        + _COMMON_TAIL
    ),
    "Long March 6C": (
        "Photorealistic Chinese Long March 6C rocket: light grey-and-white "
        "single-core body, slim proportions, no strap-on boosters, a modest "
        "payload fairing at the top, simple utilitarian stack with visible "
        "stage separation bands."
        + _COMMON_TAIL
    ),
    "Long March 12A": (
        "Photorealistic Chinese Long March 12A rocket: a distinctly wide, "
        "stocky, fat core -- much thicker and stubbier in proportion than a "
        "slender rocket, closer to a squat cylinder than a pencil shape. "
        "Dark graphite-grey body colour, visibly darker than a white rocket. "
        "Blunt, rounded nose rather than a sharp point. A wide cluster of "
        "seven engine nozzles spread across the full width of the base. "
        "Short, squat overall silhouette -- deliberately NOT a long thin "
        "stack, and clearly a different width and colour from a slim "
        "light-grey single-core rocket."
        + _COMMON_TAIL
    ),
    "Soyuz 2.1b": (
        "Photorealistic Soyuz 2.1b rocket: the iconic Soyuz silhouette -- "
        "four tapered conical strap-on boosters flaring outward around the "
        "base of a slender white-and-grey central core, classic rounded "
        "nose fairing, engine nozzles clustered at the base of the core and "
        "each booster."
        + _COMMON_TAIL
    ),
    "Vega-C": (
        "Photorealistic Vega-C rocket: slim four-stage solid-fuel stack, "
        "dark grey-and-black body, narrow diameter tapering slightly toward "
        "the top, no strap-on boosters, small pointed nose fairing, visibly "
        "slimmer and more tapered than a liquid-fueled rocket. Despite the "
        "slim body, the camera is close in and the vehicle is shot large and "
        "dominant in frame, its length spanning nearly the full diagonal "
        "corner to corner -- not small, not distant, not a thin sliver lost "
        "in empty space."
        + _COMMON_TAIL
    ),
    "New Glenn": (
        "Photorealistic Blue Origin New Glenn rocket: very large diameter "
        "white body with dark blue accent color banding near the base, seven "
        "engine nozzles clustered at the base, folded landing legs visible "
        "near the base, massive and imposing scale, broader and heavier-"
        "looking than a Falcon 9 or Vulcan."
        + _COMMON_TAIL
    ),
}

# --- #222 composition experiment (historical) -------------------------------
# The A/B/C comparison that produced _COMPOSITION above. Kept only as a
# record of what was tried and a reusable harness (--variant) for testing a
# new composition idea on one vehicle before promoting it to PROMPTS again;
# not part of the normal vehicle CLI path.
VARIANTS: dict[str, tuple[str, str]] = {
    "falcon-9-varA": (
        "Falcon 9 (Variant A: tight crop, upper stage + fairing)",
        (
            "Photorealistic SpaceX Falcon 9 upper stage and payload fairing in "
            "extreme close-up, cinematic crop -- white fairing halves with the "
            "black interstage visible below, only the upper section of the "
            "vehicle. Not the whole rocket: the vehicle is deliberately cropped "
            "by the frame's left and right edges, its body filling the full "
            "width of the frame edge to edge, camera positioned slightly below "
            "the vehicle looking up along its length -- like SpaceX's own night "
            "pad photography of a Starlink fairing close-up. "
            + _BG_LIGHTING
        ),
    ),
    "falcon-9-varB": (
        "Falcon 9 (Variant B: diagonal, full vehicle)",
        (
            "Photorealistic SpaceX Falcon 9 rocket, white cylindrical "
            "first-stage body with the distinctive black interstage band, four "
            "silver grid fins deployed near the top of the first stage, single "
            "Merlin nozzle visible at the base. The complete vehicle shown at a "
            "dynamic diagonal angle crossing the wide frame corner to corner, "
            "nose toward the upper right and base toward the lower left, so its "
            "full length fills the frame's width. Vehicle static at rest, not "
            "launching, no exhaust plume. "
            + _BG_LIGHTING
        ),
    ),
    "falcon-9-varC": (
        "Falcon 9 (Variant C: diagonal, full vehicle, pushed to fill frame)",
        (
            "Photorealistic SpaceX Falcon 9 rocket, white cylindrical "
            "first-stage body with the distinctive black interstage band, four "
            "silver grid fins deployed near the top of the first stage, single "
            "Merlin nozzle visible at the base. The complete vehicle shown at a "
            "dynamic diagonal angle, spanning nearly corner to corner across the "
            "wide frame: nose close to the top-right corner, engine bell close "
            "to the bottom-left corner, so the rocket's full length spans the "
            "entire width of the frame corner to corner. The rocket is the "
            "dominant subject, shot close to the camera so it is large and "
            "fills nearly the whole frame -- not a small object floating in "
            "empty space. Vehicle static at rest, not launching, no exhaust "
            "plume. "
            + _BG_LIGHTING
        ),
    ),
}


def slug(name: str) -> str:
    """'Falcon 9' -> 'falcon-9'. Stable -- the backend keys on this later."""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _client():
    from openai import OpenAI  # local import: keep --list usable with no deps issue

    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "XAI_API_KEY is not set in the environment. `source /home/tunas/.env` "
            "(or otherwise export it) before running this script."
        )
    return OpenAI(base_url=XAI_BASE_URL.rstrip("/"), api_key=api_key)


def generate_raw_image(prompt: str) -> bytes:
    """Call xAI Imagine, return raw image bytes. Mirrors xai_imagine.py's
    landscape-forcing + one-shot-retry-without-params behavior."""
    c = _client()
    kwargs: dict[str, Any] = {
        "model": XAI_IMAGE_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": XAI_IMAGE_SIZE,
        "extra_body": {"aspect_ratio": XAI_IMAGE_ASPECT_RATIO},
    }
    try:
        resp = c.images.generate(**kwargs)
    except Exception as e:
        print(
            f"  [warn] first Imagine call failed ({type(e).__name__}); "
            "retrying once without size/aspect_ratio",
            file=sys.stderr,
        )
        resp = c.images.generate(
            model=XAI_IMAGE_MODEL,
            prompt=prompt
            + "\n\nAspect: wide cinematic 16:9 landscape, full-frame horizontal composition.",
            n=1,
        )

    item = resp.data[0]
    url = getattr(item, "url", None)
    b64 = getattr(item, "b64_json", None)

    if b64:
        return base64.b64decode(b64)

    if not url:
        raise RuntimeError("Imagine response had neither url nor b64_json")

    with httpx.Client(timeout=120.0, follow_redirects=True) as http:
        r = http.get(url)
        r.raise_for_status()
        return r.content


def cover_fit_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    """Cover-fit + centre-crop to exactly w x h."""
    img = img.convert("RGB")
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    dst_ratio = w / h

    if src_ratio > dst_ratio:
        # source is wider than target -- scale by height, crop width
        new_h = h
        new_w = int(round(new_h * src_ratio))
    else:
        # source is taller/narrower than target -- scale by width, crop height
        new_w = w
        new_h = int(round(new_w / src_ratio))

    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return resized.crop((left, top, left + w, top + h))


def border_luminance(img: Image.Image, margin: int = 6) -> float:
    """Mean luminance of the outer `margin`-pixel border ring. Near 0 means a
    genuinely black background; anything else flags a bad generation."""
    gray = img.convert("L")
    w, h = gray.size
    px = gray.load()
    total = 0
    count = 0
    for x in range(w):
        for y in list(range(0, margin)) + list(range(h - margin, h)):
            total += px[x, y]
            count += 1
    for y in range(margin, h - margin):
        for x in list(range(0, margin)) + list(range(w - margin, w)):
            total += px[x, y]
            count += 1
    return total / count if count else 0.0


# Above this measured border luminance, treat the background as a raised
# black point rather than a real light source in the scene (confirmed on
# Soyuz 2.1b / Vega-C: the wash sits at a *uniform* ~11-12 on every side and
# every corner, which is what a level-shifted black looks like -- a genuine
# light leak/reflection would be directional, not flat). Fixed in post
# instead of re-billing the model.
BLACK_POINT_THRESHOLD = 2.0


def crush_blacks(img: Image.Image, floor: int) -> Image.Image:
    """Levels adjustment: `floor` (0-255) maps to 0, 255 stays 255, everything
    in between rescales linearly -- `max(0, v - floor) * 255 / (255 - floor)`
    per channel, via a LUT so it's applied identically to every pixel."""
    floor = max(0, min(254, floor))
    scale = 255.0 / (255 - floor)
    lut = [int(round(max(0, min(255, (v - floor) * scale)))) for v in range(256)]
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img.point(lut * 3)  # same table applied to each of the 3 bands


def apply_black_point_correction(tile: Image.Image) -> tuple[Image.Image, float, float, bool]:
    """If the tile's border luminance is above BLACK_POINT_THRESHOLD, try a
    levels crush with the floor set a couple of levels above the measured
    background so it lands solidly at 0 (not 1-2), then keep the corrected
    version only if it actually measures darker than the original -- never
    make a border worse, and never touch a tile that's already clean (this
    is the guard that leaves Electron's genuine black-body rim light alone).
    Returns (final_tile, lum_before, lum_after, corrected)."""
    lum_before = border_luminance(tile)
    if lum_before <= BLACK_POINT_THRESHOLD:
        return tile, lum_before, lum_before, False

    floor = int(math.ceil(lum_before)) + 2
    candidate = crush_blacks(tile, floor)
    lum_candidate = border_luminance(candidate)
    if lum_candidate < lum_before:
        return candidate, lum_before, lum_candidate, True
    return tile, lum_before, lum_before, False


def save_baseline_jpeg(img: Image.Image, path: str) -> int:
    img.save(path, format="JPEG", quality=82, optimize=True, progressive=False)
    return os.path.getsize(path)


def frame_width_fraction(img: Image.Image, threshold: int = 20) -> float:
    """Fraction of the image's columns that contain at least one non-black
    pixel (grayscale > threshold). On a pure-black background this is a
    direct, measured proxy for how much of the frame's width the vehicle
    occupies -- not a visual guess."""
    gray = img.convert("L")
    w, h = gray.size
    px = gray.load()
    cols_with_content = 0
    for x in range(w):
        if any(px[x, y] > threshold for y in range(h)):
            cols_with_content += 1
    return cols_with_content / w if w else 0.0


def build_contact_sheet(processed: list[tuple[str, str]]) -> None:
    """processed: list of (label, jpg_path) for every tile currently on
    disk (not just this run's) so the sheet always reflects the full set."""
    if not processed:
        return
    label_h = 22
    tile_h = ART_H + label_h
    sheet = Image.new("RGB", (ART_W, tile_h * len(processed)), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    y = 0
    for name, path in processed:
        tile = Image.open(path).convert("RGB")
        draw.rectangle((0, y, ART_W, y + label_h), fill=(20, 20, 20))
        draw.text((6, y + 4), name, fill=(255, 176, 0), font=font)
        sheet.paste(tile, (0, y + label_h))
        y += tile_h

    sheet.save(CONTACT_SHEET, format="PNG", optimize=True)


def _process_raw_bytes(label: str, raw_bytes: bytes, out_slug: str) -> tuple[str, int, float, float, bool, float]:
    """Shared post-processing: cover-crop to the panel size, black-point
    correct if needed, save baseline JPEG, measure frame-width fraction.
    Returns (jpg_path, jpg_size_bytes, lum_before, lum_after, corrected,
    width_fraction)."""
    jpg_path = os.path.join(VEHICLES_DIR, f"{out_slug}.jpg")

    img = Image.open(io.BytesIO(raw_bytes))
    tile = cover_fit_crop(img, ART_W, ART_H)
    tile, lum_before, lum_after, corrected = apply_black_point_correction(tile)
    size = save_baseline_jpeg(tile, jpg_path)
    frac = frame_width_fraction(tile)

    print(f"[{label}] processed -> {jpg_path}")
    if corrected:
        print(
            f"[{label}] size={size} bytes  border_luminance {lum_before:.2f} -> "
            f"{lum_after:.2f} (black-point corrected)  frame_width_fraction={frac:.2f}"
        )
    else:
        print(
            f"[{label}] size={size} bytes  border_luminance={lum_before:.2f} "
            f"(0=black, uncorrected)  frame_width_fraction={frac:.2f}"
        )
    return jpg_path, size, lum_before, lum_after, corrected, frac


def _generate_and_process(label: str, prompt: str, out_slug: str) -> tuple[str, int, float, float, bool, float]:
    """Generate raw via Imagine, save it, then run the shared post-processing
    pipeline (cover-crop + black-point correction + baseline JPEG)."""
    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, f"{out_slug}.png")

    print(f"[{label}] generating via Imagine...")
    raw_bytes = generate_raw_image(prompt)
    with open(raw_path, "wb") as f:
        f.write(raw_bytes)
    print(f"[{label}] raw saved -> {raw_path} ({len(raw_bytes)} bytes)")

    return _process_raw_bytes(label, raw_bytes, out_slug)


def process_one(name: str) -> None:
    if name not in PROMPTS:
        known = ", ".join(sorted(PROMPTS))
        raise SystemExit(f"No prompt for vehicle {name!r}. Known: {known}")
    _generate_and_process(name, PROMPTS[name], slug(name))


def reprocess_one(name: str) -> None:
    """Re-run the post-processing pipeline (crop + black-point correction)
    on the existing raw/<slug>.png -- no Imagine call, no billing."""
    if name not in PROMPTS:
        known = ", ".join(sorted(PROMPTS))
        raise SystemExit(f"No prompt for vehicle {name!r}. Known: {known}")
    s = slug(name)
    raw_path = os.path.join(RAW_DIR, f"{s}.png")
    if not os.path.exists(raw_path):
        raise SystemExit(
            f"No raw image on disk for {name!r} at {raw_path} -- generate it "
            "at least once (without --from-raw) before reprocessing."
        )
    with open(raw_path, "rb") as f:
        raw_bytes = f.read()
    _process_raw_bytes(name, raw_bytes, s)


def process_variant(key: str) -> None:
    if key not in VARIANTS:
        known = ", ".join(sorted(VARIANTS))
        raise SystemExit(f"No such variant {key!r}. Known: {known}")
    label, prompt = VARIANTS[key]
    _generate_and_process(label, prompt, key)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate per-vehicle rocket art on pure black for tunastreet.tminus (#222).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "vehicles",
        nargs="*",
        help="Vehicle name(s) to generate, e.g. \"Falcon 9\" \"Starship\". "
        "Must match a key in the PROMPTS table exactly.",
    )
    ap.add_argument(
        "--list", action="store_true", help="List known vehicle names and exit (no API calls)."
    )
    ap.add_argument(
        "--variant",
        nargs="+",
        metavar="KEY",
        help="Generate one or more #222 composition-experiment variants instead "
        "of a vehicle (e.g. falcon-9-varA falcon-9-varB). Does not touch the "
        "vehicle PROMPTS path or any other vehicle's files. See VARIANTS in "
        "source for the current keys.",
    )
    ap.add_argument(
        "--from-raw",
        action="store_true",
        help="Re-run cover-crop + black-point correction on the existing "
        "raw/<slug>.png for each named vehicle instead of calling the Imagine "
        "API. No billing. Fails fast if a vehicle has no raw image on disk yet.",
    )
    args = ap.parse_args()

    if args.list or (not args.vehicles and not args.variant):
        print("Known vehicles:")
        for name in sorted(PROMPTS):
            print(f"  {name}  (slug: {slug(name)})")
        print("Known variants (--variant):")
        for key, (label, _) in sorted(VARIANTS.items()):
            print(f"  {key}  ({label})")
        if not args.vehicles and not args.variant and not args.list:
            print("\nPass one or more vehicle names, or --variant KEY, to generate. See --help.")
        return

    for name in args.vehicles:
        if args.from_raw:
            reprocess_one(name)
        else:
            process_one(name)
    for key in args.variant or []:
        process_variant(key)

    # Refresh the contact sheet from whatever's on disk now (full vehicle set
    # plus any variant tiles present), so partial re-runs still produce a
    # complete sheet and variants are visible side by side with the base.
    os.makedirs(VEHICLES_DIR, exist_ok=True)
    existing = []
    for name in sorted(PROMPTS):
        p = os.path.join(VEHICLES_DIR, f"{slug(name)}.jpg")
        if os.path.exists(p):
            existing.append((name, p))
    for key, (label, _) in sorted(VARIANTS.items()):
        p = os.path.join(VEHICLES_DIR, f"{key}.jpg")
        if os.path.exists(p):
            existing.append((label, p))
    build_contact_sheet(existing)
    print(f"contact sheet -> {CONTACT_SHEET} ({len(existing)} tiles)")


if __name__ == "__main__":
    main()
