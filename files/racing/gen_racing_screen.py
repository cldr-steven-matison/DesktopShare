#!/usr/bin/env python3
"""Generate res/screens/home.json for tunastreet.racing (#205).

The panel runs the actual game. Four absolute panels on one 368x448 screen,
toggled by `hidden` bindings, mirroring the browser game's flow:
  car   -> pick your car + START RACING (the driver is this device: Tuna)
  game  -> drive
  over  -> result + race again

Sizing rule for this device: nothing is "normal UI" scale. It is a 368x448
panel viewed at arm's length and driven by a fingertip, so type is 20-46px and
every tap target is >=64px tall and near-full-width.

LAYOUT TRAP (cost a flash): a parent with layout.type flex/grid lays out its
children and ignores their absolute x/y. Every panel here therefore declares
layout {"type": "none"} — absolute placement only works under a none-layout
parent.

Palette is the game's own (services/game/index.html + leaderboard.html):
Cloudera orange #F96702 on true black, podium gold/silver/bronze, live green.
"""
import json

W, H = 368, 448
ORANGE, WHITE, MUTED, GREEN = "#F96702", "#f0f0f0", "#888888", "#22c55e"
DARK = "#1a1a1a"
LANES = [61, 184, 307]           # lane centre x
CAR_W, CAR_H = 56, 74
CAR_Y = 300
ROAD_TOP, ROAD_BOTTOM = 56, 448
OBS = 6
OBS_SZ = 44

NONE = {"type": "none"}


def label(id, x, y, w, h, size, color, text="", align="center",
          bindings=None, click=None, hidden=None):
    n = {
        "type": "label", "id": id,
        "placement": {"mode": "absolute", "x": x, "y": y, "width": w, "height": h},
        "layout": NONE,
        "style": {"textColor": color, "fontSize": size, "textAlign": align},
        "labelProps": {"text": text},
    }
    b = dict(bindings or {})
    if hidden:
        b["commonProps.hidden"] = hidden
    if b:
        n["bindings"] = b
    if click:
        n["commonProps"] = {"clickable": True}
        n["events"] = [{"type": "clicked", "effects": [
            {"type": "emitAction", "action": click, "requireValidPress": True}]}]
    return n


def box(id, x, y, w, h, color, children=None, bindings=None, click=None,
        hidden=None, radius=0, clickable=None):
    n = {
        "type": "container", "id": id,
        "placement": {"mode": "absolute", "x": x, "y": y, "width": w, "height": h},
        "layout": NONE,
        "style": {"bgColor": color, "padding": 0, "radius": radius},
        "commonProps": {"scrollable": False,
                        "clickable": bool(click) if clickable is None else clickable},
        "children": children or [],
    }
    b = dict(bindings or {})
    if hidden:
        b["commonProps.hidden"] = hidden
    if b:
        n["bindings"] = b
    if click:
        n["events"] = [{"type": "clicked", "effects": [
            {"type": "emitAction", "action": click, "requireValidPress": True}]}]
    return n


def button(id, x, y, w, h, text, action, bg=ORANGE, fg="#0f0f0f", size=30,
           bindings=None, hidden=None):
    """A big tap target: the label fills the box so the whole slab is the button."""
    return box(id, x, y, w, h, bg, radius=12, click=action, bindings=bindings,
               hidden=hidden, children=[
                   label(id + "_t", 0, (h - size - 8) // 2, w, size + 8, size, fg, text)])


# -------------------------------------------------------------- car panel (2)
car = box("panel_car", 0, 0, W, H, "#000000", hidden="carHidden", children=[
    # header bar
    box("c_bar", 0, 6, W, 54, "#141414", children=[
        label("c_brand", 0, 10, 190, 36, 28, WHITE, "CLOUDERA", "right"),
        label("c_brand2", 194, 10, 170, 36, 28, ORANGE, " RACING", "left")]),
    box("c_rule", 0, 60, W, 4, ORANGE),
    # car 1 bar
    box("c_a", 16, 76, 336, 92, DARK, radius=12, click="racing.car_a",
        bindings={"style.bgColor": "carABg"}, children=[
            {"type": "image", "id": "c_a_img",
             "placement": {"mode": "absolute", "x": 14, "y": 9, "width": 56, "height": 74},
             "layout": NONE,
             "imageProps": {"src": "${image.car_corolla}", "innerAlign": "contain"}},
            label("c_a_t", 84, 20, 240, 34, 26, WHITE, "Toyota Corolla S", "left"),
            label("c_a_s", 84, 54, 240, 26, 18, MUTED, "reliable · steady", "left")]),
    # car 2 bar
    box("c_b", 16, 180, 336, 92, DARK, radius=12, click="racing.car_b",
        bindings={"style.bgColor": "carBBg"}, children=[
            {"type": "image", "id": "c_b_img",
             "placement": {"mode": "absolute", "x": 14, "y": 9, "width": 56, "height": 74},
             "layout": NONE,
             "imageProps": {"src": "${image.car_porsche}", "innerAlign": "contain"}},
            label("c_b_t", 84, 20, 240, 34, 26, WHITE, "Porsche 911", "left"),
            label("c_b_s", 84, 54, 240, 26, 18, MUTED, "speed · sharp", "left")]),
    # text band — the deliberate gap between the car bars and START
    label("c_greet", 0, 286, W, 30, 22, GREEN, ""),
    label("c_prompt", 0, 316, W, 26, 18, MUTED, "tap a lane to steer"),
    # start
    button("c_go", 16, 352, 336, 88, "START RACING", "racing.go", size=30),
])

# ------------------------------------------------------------- game panel (3)
game_children = [
    label("g_name", 8, 6, 150, 28, 20, WHITE, "", "left"),
    label("g_lives", 158, 6, 90, 28, 22, GREEN, "***"),
    label("g_score", 250, 2, 112, 36, 30, ORANGE, "0", "right"),
    label("g_speed", 8, 32, 200, 22, 16, MUTED, "Lv.1 · 60 km/h", "left"),
    label("g_mode", 208, 32, 152, 22, 16, ORANGE, "", "right"),
    box("g_rule", 0, 52, W, 3, "#333333"),
]
# Touch zones sit BEHIND the sprites: LVGL hit-testing skips non-clickable
# objects, so a tap over a car/obstacle still reaches the zone underneath.
# One tap goes straight to a lane: the road is split into three zones, each
# targeting its own lane, so right->left is one tap, not two. They fire on
# `pressed` (touch-down) rather than `clicked` (release + valid-press), which
# is what makes a dodge feel immediate.
LANE_ZONE_W = W // 3
for zi in range(3):
    game_children.append({
        "type": "container", "id": "g_tz%d" % zi,
        "placement": {"mode": "absolute", "x": zi * LANE_ZONE_W, "y": ROAD_TOP,
                      "width": LANE_ZONE_W if zi < 2 else W - 2 * LANE_ZONE_W,
                      "height": ROAD_BOTTOM - ROAD_TOP},
        "layout": NONE,
        "style": {"bgColor": "#000000", "padding": 0},
        "commonProps": {"scrollable": False, "clickable": True},
        # `pressed` is the fast path (touch-down). `clicked` is kept as a
        # belt-and-braces second trigger in case pressed does not fire in this
        # runtime; steerTo() is idempotent so a double-fire costs nothing.
        "events": [
            {"type": "pressed", "effects": [
                {"type": "emitAction", "action": "racing.lane%d" % zi}]},
            {"type": "clicked", "effects": [
                {"type": "emitAction", "action": "racing.lane%d" % zi}]},
        ],
    })

for x in (122, 246):
    game_children.append(
        box("g_div_%d" % x, x, ROAD_TOP, 2, ROAD_BOTTOM - ROAD_TOP, "#1e1e1e", clickable=False))
for i in range(OBS):
    game_children.append({
        "type": "image", "id": "g_obs%d" % i,
        "placement": {"mode": "absolute", "x": LANES[0] - OBS_SZ // 2, "y": -90,
                      "width": OBS_SZ, "height": OBS_SZ},
        "layout": NONE,
        "commonProps": {"clickable": False},
        "imageProps": {"src": "${image.obs_cone}", "innerAlign": "contain"},
        "bindings": {"placement.x": "obs%dX" % i, "placement.y": "obs%dY" % i,
                     "commonProps.hidden": "obs%dH" % i},
    })
game_children.append({
    "type": "image", "id": "g_car",
    "placement": {"mode": "absolute", "x": LANES[1] - CAR_W // 2, "y": CAR_Y,
                  "width": CAR_W, "height": CAR_H},
    "layout": NONE,
    "commonProps": {"clickable": False},
    "imageProps": {"src": "${image.car_porsche}", "innerAlign": "contain"},
    "bindings": {"placement.x": "carX"},
})
game_children.append(label("g_toast", 0, 240, W, 34, 24, ORANGE, ""))

game = box("panel_game", 0, 0, W, H, "#000000", hidden="gameHidden", children=game_children)

# -------------------------------------------------------------- over panel (4)
over = box("panel_over", 0, 0, W, H, "#000000", hidden="overHidden", children=[
    label("o_head", 0, 12, W, 34, 26, ORANGE, "RACE OVER"),
    box("o_rule", 60, 50, 248, 4, ORANGE),
    label("o_rank", 0, 60, W, 34, 24, WHITE, ""),
    label("o_score", 0, 96, W, 68, 56, ORANGE, "0"),
    label("o_stats", 0, 166, W, 28, 18, WHITE, ""),
    label("o_board_h", 0, 200, W, 24, 16, MUTED, "TOP OF THE BOARD"),
    label("o_b1", 0, 224, W, 28, 20, "#FFD700", ""),
    label("o_b2", 0, 252, W, 28, 20, "#C0C0C0", ""),
    label("o_b3", 0, 280, W, 28, 20, "#CD7F32", ""),
    button("o_again", 24, 320, 320, 84, "RACE AGAIN", "racing.again", size=30),
    label("o_status", 0, 412, W, 24, 16, MUTED, ""),
])

screen = {
    "type": "viewScreen", "id": "home",
    "style": {"bgColor": "#000000", "padding": 0},
    "layout": NONE,
    "commonProps": {"scrollable": False, "clickable": True},
    "children": [car, game, over],
}

if __name__ == "__main__":
    out = "/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.racing/res/screens/home.json"
    json.dump(screen, open(out, "w"), indent=4)
    print("wrote", out, len(json.dumps(screen)), "bytes")
