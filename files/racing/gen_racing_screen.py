#!/usr/bin/env python3
"""Generate res/screens/home.json for tunastreet.racing (#205).

The panel runs the actual game: start -> drive -> game over, three absolute
panels on one 368x448 screen toggled by `hidden` bindings. Written as a
generator because the play field is repetitive (6 recycled obstacle nodes,
3 lanes) and hand-maintaining ~1200 lines of JSON is how layout bugs hide.

Palette is the game's own (services/game/index.html + leaderboard.html):
Cloudera orange #F96702 on true black, podium gold/silver/bronze, live green.
"""
import json

W, H = 368, 448
ORANGE, WHITE, MUTED, GREEN, RED = "#F96702", "#f0f0f0", "#888888", "#22c55e", "#e5484d"
LANES = [61, 184, 307]          # lane centre x
CAR_W, CAR_H = 52, 68
CAR_Y = 320
ROAD_TOP, ROAD_H = 52, 396
OBS = 6                          # recycled obstacle nodes
OBS_SZ = 38


def label(id, x, y, w, h, size, color, text="", align="center", bindings=None,
          click=None, hidden=None):
    n = {
        "type": "label", "id": id,
        "placement": {"mode": "absolute", "x": x, "y": y, "width": w, "height": h},
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
        hidden=None, radius=0):
    n = {
        "type": "container", "id": id,
        "placement": {"mode": "absolute", "x": x, "y": y, "width": w, "height": h},
        "style": {"bgColor": color, "padding": 0, "radius": radius},
        "commonProps": {"scrollable": False, "clickable": bool(click)},
        "layout": {"type": "flex", "flexFlow": "row", "mainAlign": "center",
                   "crossAlign": "center", "gap": 0},
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


# ---------------------------------------------------------------- start panel
start = box("panel_start", 0, 0, W, H, "#000000", hidden="startHidden", children=[
    label("s_brand_l", 0, 26, 200, 34, 24, WHITE, "CLOUDERA", "right"),
    label("s_brand_r", 204, 26, 120, 34, 24, ORANGE, " RACING", "left"),
    box("s_rule", 40, 64, 288, 3, ORANGE),
    label("s_prompt", 0, 80, W, 20, 14, MUTED, "ENTER YOUR NAME"),
    {
        "type": "textInput", "id": "s_name",
        "placement": {"mode": "absolute", "x": 44, "y": 104, "width": 280, "height": 44},
        "style": {"textColor": WHITE, "fontSize": 20, "textAlign": "center",
                  "bgColor": "#1a1a1a", "radius": 8},
        "commonProps": {"clickable": True},
        "textInputProps": {"text": "", "placeholder": "Driver", "maxLength": 12},
    },
    label("s_car_hint", 0, 156, W, 18, 12, MUTED, "PICK YOUR CAR"),
    box("s_car_a", 30, 178, 145, 54, "#1a1a1a", radius=8, click="racing.car_a",
        bindings={"style.borderColor": "carAColor"}, children=[
            label("s_car_a_t", 0, 0, 145, 20, 14, WHITE, "Toyota", "center")]),
    box("s_car_b", 193, 178, 145, 54, "#1a1a1a", radius=8, click="racing.car_b",
        bindings={"style.borderColor": "carBColor"}, children=[
            label("s_car_b_t", 0, 0, 145, 20, 14, WHITE, "Porsche 911", "center")]),
    label("s_car_a_s", 30, 214, 145, 16, 11, MUTED, "Corolla S · reliable"),
    label("s_car_b_s", 193, 214, 145, 16, 11, MUTED, "911 · speed"),
    box("s_go", 104, 246, 160, 56, ORANGE, radius=10, click="racing.go", children=[
        label("s_go_t", 0, 0, 160, 30, 26, "#0f0f0f", "GO!", "center")]),
    label("s_hint", 0, 310, W, 18, 12, MUTED, "tap left / right side to steer"),
    label("s_status", 0, 330, W, 18, 12, MUTED, ""),
    {
        "type": "keyboard", "id": "s_kb",
        "placement": {"mode": "absolute", "x": 0, "y": 352, "width": W, "height": 96},
        "keyboardProps": {"target": "s_name"},
        "bindings": {"commonProps.hidden": "kbHidden"},
    },
])

# ----------------------------------------------------------------- game panel
game_children = [
    # HUD
    label("g_name", 8, 6, 130, 20, 14, WHITE, "", "left"),
    label("g_lives", 140, 6, 88, 20, 14, GREEN, "***", "center"),
    label("g_clock", 230, 6, 60, 20, 14, MUTED, "0:00", "center"),
    label("g_score", 292, 4, 70, 24, 20, ORANGE, "0", "right"),
    label("g_speed", 8, 28, 180, 18, 12, MUTED, "Lv.1 · 60 km/h", "left"),
    label("g_mode", 188, 28, 172, 18, 12, MUTED, "", "right"),
    box("g_rule", 0, 48, W, 2, "#333333"),
]
# touch zones sit BEHIND the sprites: LVGL hit-testing skips non-clickable
# objects, so a tap over a car/obstacle still reaches the zone underneath.
game_children += [
    box("g_tz_l", 0, ROAD_TOP, W // 2, ROAD_H - ROAD_TOP, "#000000", click="racing.left"),
    box("g_tz_r", W // 2, ROAD_TOP, W // 2, ROAD_H - ROAD_TOP, "#000000", click="racing.right"),
]
# lane dividers
for x in (122, 246):
    game_children.append(box("g_div_%d" % x, x, ROAD_TOP, 2, ROAD_H - ROAD_TOP, "#1e1e1e"))
# obstacles
for i in range(OBS):
    game_children.append(box(
        "g_obs%d" % i, LANES[0] - OBS_SZ // 2, -80, OBS_SZ, OBS_SZ, "#f5a623", radius=6,
        bindings={"placement.x": "obs%dX" % i, "placement.y": "obs%dY" % i,
                  "style.bgColor": "obs%dC" % i, "commonProps.hidden": "obs%dH" % i}))
# the car
game_children.append(box(
    "g_car", LANES[1] - CAR_W // 2, CAR_Y, CAR_W, CAR_H, "#e8e8ee", radius=8,
    bindings={"placement.x": "carX", "style.bgColor": "carColor"}, children=[
        label("g_car_t", 0, 0, CAR_W, 20, 12, "#111111", "", "center")]))
game_children.append(label("g_toast", 0, 268, W, 22, 15, ORANGE, "", "center"))

game = box("panel_game", 0, 0, W, H, "#000000", hidden="gameHidden", children=game_children)

# ------------------------------------------------------------ game-over panel
over = box("panel_over", 0, 0, W, H, "#000000", hidden="overHidden", children=[
    label("o_head", 0, 22, W, 26, 20, ORANGE, "RACE OVER"),
    box("o_rule", 60, 52, 248, 3, ORANGE),
    label("o_rank", 0, 64, W, 30, 22, WHITE, ""),
    label("o_sub", 0, 96, W, 36, 12, MUTED, ""),
    label("o_score_l", 0, 140, W, 18, 13, MUTED, "SCORE"),
    label("o_score", 0, 158, W, 52, 44, ORANGE, "0"),
    label("o_stats", 0, 214, W, 20, 14, WHITE, ""),
    label("o_board_h", 0, 244, W, 18, 12, MUTED, "TOP OF THE BOARD"),
    label("o_b1", 0, 264, W, 20, 15, "#FFD700", ""),
    label("o_b2", 0, 286, W, 20, 15, "#C0C0C0", ""),
    label("o_b3", 0, 308, W, 20, 15, "#CD7F32", ""),
    box("o_again", 84, 340, 200, 54, ORANGE, radius=10, click="racing.again", children=[
        label("o_again_t", 0, 0, 200, 28, 20, "#0f0f0f", "RACE AGAIN", "center")]),
    label("o_status", 0, 404, W, 20, 13, MUTED, ""),
])

screen = {
    "type": "viewScreen", "id": "home",
    "style": {"bgColor": "#000000", "padding": 0},
    "commonProps": {"scrollable": False, "clickable": True},
    "children": [start, game, over],
}

if __name__ == "__main__":
    out = "/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.racing/res/screens/home.json"
    json.dump(screen, open(out, "w"), indent=4)
    print("wrote", out, len(json.dumps(screen)), "bytes")
