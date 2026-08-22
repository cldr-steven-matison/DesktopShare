#!/usr/bin/env python3
"""Generate res/screens/home.json for tunastreet.tminus (#184, on panelkit #208).

The original screen was a flex column of labels on black -- a countdown with a
lot of empty middle and nothing to look at. This rebuild keeps the clock as
the loudest thing on the panel and gives the empty band the launch art
(files/tminus/gen_tminus_art.py).

It also had to stop being flex: an absolutely-placed background image under a
flex parent gets repositioned by the parent (panelkit trap 1), so the art
could not have been added without this change. The root is now absolute,
which is also what lets the clock, art and footer sit at fixed positions
instead of stacking wherever the flow lands them.

Every id app/app.js writes to is unchanged -- /clock, /prefix, /vehicle,
/mission, /pad, /status, /meta. The clock keeps its clockColor/clockSize
bindings.

The nav moved (2026-08-21, reported from the glass and the simulator alike):
the « / » glyphs were 64x44 targets in the top corners, and both were hard to
hit. They are gone; navigation is now two half-panel tap zones over the middle
band plus the screen swipe, which app.js debounces at 350 ms so one drag steps
one launch.

Run: python3 gen_tminus_screen.py
"""
import json
import os
import sys

UIKIT = "/home/tunas/waveshare-devices/amoled-1.8-v2/uikit"
OUT = ("/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.tminus"
       "/res/screens/home.json")

sys.path.insert(0, UIKIT)

import panelkit as pk  # noqa: E402
import tokens as tk  # noqa: E402

W, H = tk.W, tk.H
BLACK = "#000000"
AMBER = "#ffb000"
# The art sits between the mission line and the footer, and stops short
# of it: the first render ran the plume under "SLC-4E - Vandenberg".
ART_Y, ART_H = 206, 168
# The nav band covers the art and the gap under it, stopping at the footer.
NAV_Y, NAV_H = ART_Y, 174


def topbar():
    """Brand only. The nav used to live up here as two 64x44 glyphs in the
    top corners -- the two hardest pixels on the panel to hit with a thumb,
    and reported as such from both the glass and the simulator. Navigation
    moved to the middle band (nav_zones)."""
    return pk.canvas("topbar", 0, 0, W, 44, bg=BLACK, children=[
        pk.label("brand", 0, 10, W, 26, text="T-MINUS", role="body",
                 size=20, color=AMBER),
    ])


def nav_zones():
    """Two half-width tap targets filling the middle band -- 184x174 each,
    against 64x44 in a corner before. Left = previous launch, right = next.

    They sit *behind* the art and the chevrons in child order, and the
    passthrough only works because both of those are explicitly
    non-clickable. That is not free: an `image` node defaults to
    clickable:true in the runtime, so the first cut of this screen shipped
    with the art swallowing every tap in the band -- panelkit trap 3, now
    closed by `sprite()` and lint R6. Taps stay the guaranteed path; swipe
    is the nicer one, but the package README's gesture-bubble finding says
    a JSON-UI gesture may never reach an app node on this backend."""
    return [
        pk.canvas("nav_prev", 0, NAV_Y, W // 2, NAV_H, bg=BLACK,
                  click="tminus.prev"),
        pk.canvas("nav_next", W // 2, NAV_Y, W - W // 2, NAV_H, bg=BLACK,
                  click="tminus.next"),
    ]


def nav_chevrons():
    """Affordance only, drawn over the art: something has to say the middle
    of the screen is tappable."""
    cy = NAV_Y + (NAV_H - 44) // 2
    return [
        pk.label("nav_prev_g", 8, cy, 44, 44, text="<", role="value",
                 size=40, color=tk.MUTED),
        pk.label("nav_next_g", W - 52, cy, 44, 44, text=">", role="value",
                 size=40, color=tk.MUTED),
    ]


def build():
    return pk.screen("home", bg=BLACK, children=[
        # Nav zones first: everything drawn after them is non-clickable and
        # falls through.
    ] + nav_zones() + [
        topbar(),
        # T- / T+ / HOLD marker over the clock.
        pk.label("prefix", 0, 50, W, 22, text="T-", role="footer", size=16,
                 color=AMBER),
        # The clock is the panel. app.js rewrites both its colour and its size
        # (a day-scale readout has to shrink to fit), hence the two bindings.
        pk.label("clock", 0, 74, W, 68, text="--:--:--", role="hero", size=48,
                 color=AMBER,
                 bindings={"style.textColor": "clockColor",
                           "style.fontSize": "clockSize"}),
        pk.label("vehicle", 8, 148, W - 16, 32, text="", role="body", size=20,
                 color=tk.INK),
        pk.label("mission", 8, 182, W - 16, 28, text="", role="body", size=16,
                 color=tk.MUTED),
        # The art fills what used to be dead space between the mission line
        # and the footer. Not clickable: taps fall through to the nav zones
        # underneath it, which is exactly the point.
        pk.sprite("art", 0, ART_Y, W, ART_H, src="${image.launch}",
                  align="contain"),
    ] + nav_chevrons() + [
        pk.label("pad", 8, H - 68, W - 16, 22, text="", role="footer", size=16,
                 color=tk.MUTED),
        pk.label("status", 8, H - 46, W - 16, 22, text="", role="footer",
                 size=16, color=tk.MUTED),
        pk.label("meta", 8, H - 24, W - 16, 20, text="", role="footer", size=16,
                 color=tk.DARK),
    ])


def main():
    tree = build()
    # Screen-level swipe, same raw-dict escape hatch the other apps use --
    # a gesture listener isn't a tap target and has no panelkit primitive.
    tree["events"] = [{"type": "gesture", "action": "tminus.gesture"}]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(tree, f, indent=4)
        f.write("\n")
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
