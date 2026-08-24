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

Navigation is a SWIPE, and only a swipe (#220). Two earlier rounds tried taps:
64x44 « / » glyphs in the top corners (unhittable), then two half-panel tap
zones over the middle band (this file, 2026-08-21). Both were wrong for the
same reason -- a tap target laid over the area a finger drags across collides
with the drag:

  * LVGL delivers LV_EVENT_GESTURE to the object under the finger, climbing
    parents only while LV_OBJ_FLAG_GESTURE_BUBBLE is set. A clickable zone
    takes the press, so the gesture leaves through the zone, not the screen.
  * The zone then fires on `pressed` AND on `released` -- so a drag that
    starts on the left half steps BACKWARD however you swiped.

The zones are gone. The chevrons stay, non-clickable, as the affordance that
says which way the panel moves. The screen-root `gesture` event is the only
nav path, and it fires at most once per finger-down/up (LVGL latches
`pointer.gesture_sent`), so app.js needs no debounce at all.

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
# The band the chevrons sit in -- the art and the gap under it, stopping at
# the footer. Nothing in it is clickable; it is where the swipe is expected.
NAV_Y, NAV_H = ART_Y, 174


def topbar():
    """Brand only. The nav used to live up here as two 64x44 glyphs in the
    top corners -- the two hardest pixels on the panel to hit with a thumb,
    and reported as such from both the glass and the simulator. There is no
    tap target anywhere on this screen any more (#220)."""
    return pk.canvas("topbar", 0, 0, W, 44, bg=BLACK, children=[
        pk.label("brand", 0, 10, W, 26, text="T-MINUS", role="body",
                 size=20, color=AMBER),
    ])


def build():
    return pk.screen("home", bg=BLACK, children=[
        # Nothing on this screen is clickable. That is the point: a clickable
        # child under the finger swallows the swipe (see the module docstring).
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
        # and the footer. Not clickable -- an `image` node defaults to
        # clickable:true in the runtime, and a clickable node under the finger
        # is exactly what stops the swipe from reaching the screen root
        # (panelkit trap 3, closed by sprite() and lint R6).
        pk.sprite("art", 0, ART_Y, W, ART_H, src="${image.launch}",
                  align="contain"),
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
    # The screen root is the ONLY thing on this panel that reacts to touch.
    # The runtime clears LV_OBJ_FLAG_GESTURE_BUBBLE on a node that declares a
    # `gesture` event (#220, gui/brookesia_gui_lvgl/src/event.cpp overlay), so
    # the swipe stops climbing here instead of running past to the LVGL screen.
    tree["events"] = [{"type": "gesture", "action": "tminus.gesture"}]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(tree, f, indent=4)
        f.write("\n")
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
