#!/usr/bin/env python3
"""Generate res/screens/home.json for tunastreet.agent (#197).

One glanceable screen at 368x448: is the agent beating, how many of its
processors are running, and what it ships off the device. Built on panelkit
(#208) so the type scale, tap targets and the two JSON-UI traps come from
tokens.json rather than from whatever looked right in the editor.

Every node id here is written to by app/app.js -- the paths are the contract
between the two files, which is exactly the pair that silently broke in #205
when a UI rework deleted labels the app kept addressing. The simulator's
--check walks them.

Run: python3 gen_agent_screen.py
"""
import json
import os
import sys

UIKIT = "/home/tunas/waveshare-devices/amoled-1.8-v2/uikit"
OUT = ("/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.agent"
       "/res/screens/home.json")

sys.path.insert(0, UIKIT)

import panelkit as pk  # noqa: E402
import tokens as tk  # noqa: E402

W = tk.W
BLACK = "#000000"

CELLS = 12          # sweep cells, must match CELLS in app.js
CELL_W = 24
CELL_GAP = 6


def header():
    """Title and state, both pushed to y>=18 so the rounded corner does not bite
    into edge-anchored text (lint R10)."""
    return pk.canvas("head", 0, 0, W, 52, bg=BLACK, children=[
        pk.label("head_t", 16, 18, 210, 28, text="EFM AGENT",
                 role="body", size=20, color=tk.ORANGE, align="left"),
        pk.label("head_state", 226, 20, 126, 24, text="...",
                 role="body", size=16, color=tk.MUTED, align="right",
                 bindings={"style.textColor": "stateColor"}),
    ])


def sweep():
    """Twelve cells with one bright head running across them -- a monitor
    trace drawn with bgColor writes only, which is the cheap mutation on this
    runtime. app.js addresses /hb/hb0 .. /hb/hb11 and binds hbNBg."""
    span = CELLS * CELL_W + (CELLS - 1) * CELL_GAP
    x0 = (W - span) // 2
    cells = []
    for i in range(CELLS):
        cells.append(pk.canvas(
            "hb%d" % i, x0 + i * (CELL_W + CELL_GAP), 0, CELL_W, 34,
            bg=tk.DARK, radius=4,
            bindings={"style.bgColor": "hb%dBg" % i}))
    return pk.canvas("hb", 0, 54, W, 34, bg=BLACK, children=cells)


def beat():
    return pk.canvas("beat", 0, 96, W, 92, bg=BLACK, children=[
        pk.label("beat_v", 0, 0, W, 62, text="--", role="hero", size=48,
                 color=tk.MUTED, bindings={"style.textColor": "beatColor"}),
        pk.label("beat_cap", 0, 66, W, 20, text="SINCE LAST HEARTBEAT",
                 role="footer", size=16, color=tk.MUTED),
    ])


def processors():
    return pk.canvas("proc", 0, 196, W, 118, bg=BLACK, children=[
        pk.label("proc_v", 0, 0, W, 54, text="--", role="hero", size=48,
                 color=tk.ORANGE, bindings={"style.textColor": "procColor"}),
        pk.label("proc_cap", 0, 56, W, 20, text="PROCESSORS RUNNING",
                 role="footer", size=16, color=tk.MUTED),
        pk.label("proc_list", 8, 78, W - 16, 22, text="", role="body",
                 size=16, color=tk.INK),
        pk.label("proc_cat", 8, 100, W - 16, 18, text="", role="footer",
                 size=16, color=tk.MUTED),
    ])


def metrics():
    """The three numbers the agent actually ships to EFM. Captions at the
    footer floor, values in the value band -- the #205 sizing lesson.

    BEATS replaced CPU %: this agent reports cpuUtilization 0.0 on every
    heartbeat, so the cell was a permanent zero. Heartbeats-received is a
    number that actually moves, and it comes from EFM's own counter.

    QUEUE is dropped (#220): three equal cells instead of four cramped ones."""
    cells = [
        ("mx_uptime", "UPTIME", "--"),
        ("mx_mem", "MEM MB", "--"),
        ("mx_beats", "BEATS", "--"),
    ]
    cw = W // 3
    kids = []
    for i, (cid, cap, val) in enumerate(cells):
        x = i * cw
        kids.append(pk.label(cid + "_v", x, 4, cw, 36, text=val,
                             role="value", size=28, color=tk.INK))
        kids.append(pk.label(cid + "_c", x, 42, cw, 20, text=cap,
                             role="footer", size=16, color=tk.MUTED))
    return pk.canvas("mx", 0, 322, W, 66, bg=BLACK, children=kids)


def footer():
    """Just the agent id line now (#220): foot_age ("updated Ns ago") is
    dropped, and foot_id moves up to y=0 to take its place."""
    return pk.canvas("foot", 0, 396, W, 52, bg=BLACK, children=[
        pk.label("foot_id", 8, 0, W - 16, 20, text="connecting...",
                 role="footer", size=16, color=tk.MUTED),
    ])


def build():
    # The refresh zone is first in the child list so it sits behind
    # everything: LVGL hit-testing skips non-clickable objects, so a tap
    # anywhere that isn't its own target falls through to this one.
    # (Same trick as racing's lane zones.)
    return pk.screen("home", bg=BLACK, children=[
        pk.canvas("tapzone", 0, 0, W, tk.H, bg=BLACK, click="agent.refresh"),
        header(),
        sweep(),
        beat(),
        processors(),
        metrics(),
        footer(),
    ])


def main():
    tree = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(tree, f, indent=4)
        f.write("\n")
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
