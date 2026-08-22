#!/usr/bin/env python3
"""Generate res/screens/home.json for tunastreet.racing (#205, migrated to
the uikit/panelkit.py kit for #208).

The panel runs the actual game. Four absolute panels on one 368x448 screen,
toggled by `hidden` bindings, mirroring the browser game's flow:
  car   -> pick your car + START RACING (the driver is this device: Tuna)
  game  -> drive
  over  -> result + race again

This screen was the seed panelkit.py was generalised from: label(), box() and
button() here are now panelkit's label(), canvas() and button(), and the car
bars are panelkit's tile(). The two traps that cost a flash cycle in #205 --
a flex-layout parent silently overriding absolute children, and
container/requireValidPress swallowing a drifted tap -- are now closed by the
kit itself (see uikit/panelkit.py's module docstring), not just described in
this comment.

Text sizes below are still explicit numbers, not "whatever panelkit feels
like": every label() call passes the exact legacy size, and panelkit checks
each one against its role's token band (and the absolute text floor) at
generation time. Palette is the game's own (services/game/index.html +
leaderboard.html): Cloudera orange #F96702 on true black, podium gold/silver/
bronze, live green -- all token constants except the true-black background,
which this game deliberately keeps darker than the kit's generic screen
background (see README.md's token-rationale section).

Three lane-touch zones (g_tz0-2) need `pressed` + `pressing` + `released` --
continuous drive control while the finger is held down, not a discrete tap --
which none of panelkit's primitives emit (button()/canvas()'s click= is
pressed+released only, by design: see panelkit.py). They're kept as raw
dicts, byte-identical to the original, rather than forcing them through a
primitive that doesn't actually fit the shape.
"""
import json
import os
import sys

sys.path.insert(0, "/home/tunas/waveshare-devices/amoled-1.8-v2/uikit")
import panelkit as pk  # noqa: E402
import tokens as tk    # noqa: E402

W, H = tk.W, tk.H
ORANGE, WHITE, MUTED, GREEN = tk.ORANGE, tk.INK, tk.MUTED, tk.GREEN
DARK = tk.DARK
LANES = [61, 184, 307]           # lane centre x
CAR_W, CAR_H = 56, 74
CAR_Y = 300
ROAD_TOP, ROAD_BOTTOM = 56, 448
OBS = 6
OBS_SZ = 44  # tick is 40ms in app.js — motion is smoother, speed unchanged

NONE = pk.NONE_LAYOUT


# -------------------------------------------------------------- car panel (2)
car = pk.canvas("panel_car", 0, 0, W, H, bg="#000000", hidden="carHidden", children=[
    # header bar
    pk.canvas("c_bar", 0, 6, W, 54, bg="#141414", children=[
        pk.label("c_brand", 0, 10, 190, 36, text="CLOUDERA", role="value",
                 color=WHITE, align="right", size=28),
        pk.label("c_brand2", 194, 10, 170, 36, text=" RACING", role="value",
                 color=ORANGE, align="left", size=28)]),
    pk.canvas("c_rule", 0, 60, W, 4, bg=ORANGE),
    # car 1 / car 2 bars — panelkit's tile() generalises these (image + two
    # lines of text, whole box tappable). title_y is pinned explicitly to
    # reproduce the hand-tuned legacy pixel position (20, not the formula's
    # auto-centred 16) — see panelkit.tile()'s docstring.
    pk.tile("c_a", 16, 76, 336, 92, "${image.car_corolla}", "Toyota Corolla S",
            "reliable - steady", "racing.car_a", img_pad=14, img_w=CAR_W,
            img_h=CAR_H, title_size=24, subtitle_size=16, title_y=20,
            bindings={"style.bgColor": "carABg"}),
    pk.tile("c_b", 16, 180, 336, 92, "${image.car_porsche}", "Porsche 911",
            "speed - sharp", "racing.car_b", img_pad=14, img_w=CAR_W,
            img_h=CAR_H, title_size=24, subtitle_size=16, title_y=20,
            bindings={"style.bgColor": "carBBg"}),
    # text band — the deliberate gap between the car bars and START
    pk.label("c_greet", 0, 286, W, 30, text="", role="body", color=GREEN, size=20),
    pk.label("c_prompt", 0, 316, W, 26, text="tap a lane to steer", role="body",
              color=MUTED, size=16),
    # start
    pk.button("c_go", 16, 352, W - 32, 88, "START RACING", "racing.go", size=28),
])

# ------------------------------------------------------------- game panel (3)
game_children = [
    pk.label("g_name", 8, 4, 120, 26, text="", role="body", color=WHITE,
              align="left", size=16),
    pk.label("g_lives", 130, 4, 76, 26, text="***", role="body", color=GREEN,
              size=20, bindings={"style.textColor": "livesColor"}),
    pk.label("g_clock", 206, 4, 60, 26, text="0:00", role="body", color=MUTED, size=16),
    pk.label("g_score", 266, 0, 96, 34, text="0", role="value", color=ORANGE,
              align="right", size=28),
    pk.label("g_speed", 8, 32, 200, 22, text="Lv.1 - 60 km/h", role="body",
              color=MUTED, align="left", size=16),
    pk.label("g_mode", 208, 32, 152, 22, text="", role="body", color=ORANGE,
              align="right", size=16),
    pk.canvas("g_rule", 0, 52, W, 3, bg="#333333"),
]
# Touch zones sit BEHIND the sprites: LVGL hit-testing skips non-clickable
# objects, so a tap over a car/obstacle still reaches the zone underneath.
# One tap goes straight to a lane: the road is split into three zones, each
# targeting its own lane, so right->left is one tap, not two. They fire on
# `pressed` (touch-down) rather than `clicked` (release + valid-press), which
# is what makes a dodge feel immediate. This is the "pressed+pressing+
# released, no gap" shape panelkit's primitives don't build (see module
# docstring) -- kept as the original raw dicts.
LANE_ZONE_W = W // 3
for zi in range(3):
    game_children.append({
        "type": "container", "id": "g_tz%d" % zi,
        "placement": {"mode": "absolute", "x": zi * LANE_ZONE_W, "y": ROAD_TOP,
                      "width": LANE_ZONE_W if zi < 2 else W - 2 * LANE_ZONE_W,
                      "height": ROAD_BOTTOM - ROAD_TOP},
        "layout": NONE,
        "style": {"bgColor": "#000000", "padding": 0},
        "commonProps": {"scrollable": False, "pressLock": True, "clickable": True},
        # pressed = touch-down (fast path); pressing = still held, so a slow or
        # dragging finger still lands the lane; released = the catch-all. None
        # use requireValidPress, which would drop the whole tap if it drifted.
        "events": [
            {"type": "pressed", "effects": [
                {"type": "emitAction", "action": "racing.lane%d" % zi}]},
            {"type": "pressing", "effects": [
                {"type": "emitAction", "action": "racing.lane%d" % zi}]},
            {"type": "released", "effects": [
                {"type": "emitAction", "action": "racing.lane%d" % zi}]},
        ],
    })

for x in (122, 246):
    game_children.append(
        pk.canvas("g_div_%d" % x, x, ROAD_TOP, 2, ROAD_BOTTOM - ROAD_TOP,
                  bg="#1e1e1e", clickable=False))
for i in range(OBS):
    game_children.append(
        pk.sprite("g_obs%d" % i, LANES[0] - OBS_SZ // 2, -90, OBS_SZ, OBS_SZ,
                  "${image.obs_cone}", clickable=False,
                  bindings={"placement.x": "obs%dX" % i, "placement.y": "obs%dY" % i,
                            "commonProps.hidden": "obs%dH" % i}))
game_children.append(
    pk.sprite("g_car", LANES[1] - CAR_W // 2, CAR_Y, CAR_W, CAR_H,
              "${image.car_porsche}", clickable=False, bindings={"placement.x": "carX"}))
game_children.append(pk.label("g_toast", 0, 240, W, 34, text="", role="value",
                                color=ORANGE, size=24))

game = pk.canvas("panel_game", 0, 0, W, H, bg="#000000", hidden="gameHidden",
                  children=game_children)

# -------------------------------------------------------------- over panel (4)
over = pk.canvas("panel_over", 0, 0, W, H, bg="#000000", hidden="overHidden", children=[
    pk.label("o_head", 0, 12, W, 34, text="RACE OVER", role="value", color=ORANGE, size=24),
    pk.canvas("o_rule", 60, 50, 248, 4, bg=ORANGE),
    pk.label("o_rank", 0, 58, W, 32, text="", role="value", color=WHITE, size=24),
    pk.label("o_sub", 0, 90, W, 24, text="", role="footer", color=MUTED, size=16),
    pk.label("o_score", 0, 114, W, 62, text="0", role="hero", color=ORANGE, size=48),
    pk.label("o_stats", 0, 178, W, 26, text="", role="body", color=WHITE, size=16),
    pk.label("o_board_h", 0, 206, W, 22, text="TOP OF THE BOARD", role="footer",
              color=MUTED, size=16),
    pk.label("o_b1", 0, 228, W, 26, text="", role="body", color=tk.GOLD, size=16),
    pk.label("o_b2", 0, 254, W, 26, text="", role="body", color=tk.SILVER, size=16),
    pk.label("o_b3", 0, 280, W, 26, text="", role="body", color=tk.BRONZE, size=16),
    pk.button("o_again", 24, 320, 320, 84, "RACE AGAIN", "racing.again", size=28),
    pk.label("o_status", 0, 412, W, 24, text="", role="footer", color=MUTED, size=16),
])

screen = pk.screen("home", [car, game, over], bg="#000000")

if __name__ == "__main__":
    out = "/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.racing/res/screens/home.json"
    json.dump(screen, open(out, "w"), indent=4)
    print("wrote", out, len(json.dumps(screen)), "bytes")
