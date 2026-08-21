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

Every node id is unchanged from the flex version -- /clock, /prefix, /vehicle,
/mission, /pad, /status, /meta, /topbar/nav_prev, /topbar/nav_next -- so
app/app.js needs no edit. The clock keeps its clockColor/clockSize bindings.

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


def topbar():
    """« and » stay as real tap targets -- the package README's gesture-bubble
    finding means a swipe may never fire on this backend, so the taps are the
    guaranteed path, not a decoration."""
    return pk.canvas("topbar", 0, 0, W, 44, bg=BLACK, children=[
        pk.label("nav_prev", 0, 0, 64, 44, text="«", role="value", size=28,
                 color=tk.MUTED, click="tminus.prev"),
        pk.label("brand", 64, 10, W - 128, 26, text="T-MINUS", role="body",
                 size=20, color=AMBER),
        pk.label("nav_next", W - 64, 0, 64, 44, text="»", role="value",
                 size=28, color=tk.MUTED, click="tminus.next"),
    ])


def build():
    return pk.screen("home", bg=BLACK, children=[
        topbar(),
        # T- / T+ / HOLD marker over the clock.
        pk.label("prefix", 0, 50, W, 22, text="T-", role="footer", size=16,
                 color=AMBER),
        # The clock is the panel. app.js rewrites both its colour and its size
        # (a day-scale readout has to shrink to fit), hence the two bindings.
        pk.label("clock", 0, 74, W, 68, text="--:--:--", role="hero", size=56,
                 color=AMBER,
                 bindings={"style.textColor": "clockColor",
                           "style.fontSize": "clockSize"}),
        pk.label("vehicle", 8, 148, W - 16, 32, text="", role="body", size=22,
                 color=tk.INK),
        pk.label("mission", 8, 182, W - 16, 28, text="", role="body", size=18,
                 color=tk.MUTED),
        # The art fills what used to be dead space between the mission line
        # and the footer. Not clickable: taps fall through to nothing, which
        # is correct -- navigation lives in the topbar and the swipe.
        pk.sprite("art", 0, ART_Y, W, ART_H, src="${image.launch}",
                  align="contain"),
        pk.label("pad", 8, H - 68, W - 16, 22, text="", role="footer", size=16,
                 color=tk.MUTED),
        pk.label("status", 8, H - 46, W - 16, 22, text="", role="footer",
                 size=16, color=tk.MUTED),
        pk.label("meta", 8, H - 24, W - 16, 20, text="", role="footer", size=15,
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
