#!/usr/bin/env python3
"""Generate home.json for tunastreet.xviewer, rebuilt on panelkit (#198/#208).

Why this file exists: the shipped `res/screens/home.json` predates panelkit
and is the counter-example lint.py is calibrated against -- it lints dirty
(3 requireValidPress sites, 5 sub-15px labels, a 48px-tall bottom bar with
40x36 nav targets and a 28px heart). Steven's brief for #198 named the exact
same symptoms verbatim ("text is too small, buttons too small, some text on
bottom cant even see") and asked for "an absolute miracle of difference" now
that the framework exists. This script is that rebuild, using panelkit
primitives (canvas/label/sprite) exclusively so every size comes from
tokens.json rather than from what looked right in an editor.

Writes the package's screen directly. SCRATCH_OUT is kept as a target for
trying a layout without touching the shipped file -- the harness can render
either path.

Layout (368x448, four stacked absolute regions, no gaps/overlaps):

  y=0..46    topbar   -- "n/N" position (left) + status/error text (right)
  y=46..266  media    -- 368x220 card image plus two non-interactive chevron
                         glyphs. NO tap zones: navigation is the screen-root
                         swipe and nothing else (#220)
  y=266..372 post_text -- wrapped post body, 16px (#236)
  y=372..448 toolbar   -- LIKE (heart image + count), VIEWS, COMMENTS
                         (replies) -- the #198 "tools" bar, 76px tall (#236)

Design decisions worth explaining to a future reader:

- The old bottom bar crammed «, heart+likes, reposts, views, pos, » into one
  48px flex row -- six things in 360px, hence 13-28px everything. #198 moved
  navigation off that bar and onto the media card as two half-card tap zones.
  #220 removed those too: navigation is now the swipe and only the swipe.

  The zones had to go because a tap target laid over the area a finger drags
  across IS the "tap and swipe collision" Steven reported. LVGL sends
  LV_EVENT_GESTURE to the object under the finger and climbs parents only
  while LV_OBJ_FLAG_GESTURE_BUBBLE is set, so a clickable zone takes the
  press and the swipe leaves through the zone. The zone then fires on
  `pressed` AND `released` (panelkit fires both on purpose), so one drag
  scored two steps in whichever direction the drag STARTED, regardless of
  which way it went.

  What makes swipe-only safe now is the other half of #220: the runtime
  clears GESTURE_BUBBLE on any node that declares a `gesture` event
  (gui/brookesia_gui_lvgl/src/event.cpp overlay), so the screen root actually
  receives the swipe instead of it climbing past to the LVGL screen -- the
  thing the README's gesture-bubble section correctly predicted would never
  fire. The LIKE tool is the only tap target left, and it is in the bottom
  bar, not under the drag.

- The bottom bar is genuinely a `tool_bar()`-shaped bar (#198's own docstring
  in panelkit.py names this exact bar), but it's hand-assembled here instead
  of calling tool_bar() directly: two of its three items (VIEWS, COMMENTS)
  need a two-line value-over-caption stat shape (a number and a label under
  it, the same shape gen_agent_screen.py's metrics() row uses) which none of
  tool_bar()'s three item kinds (image+caption, compact single-line, plain
  button) produce on their own. So this bar reuses tool_bar()'s own numbers
  (tool_bar()'s image-branch sizing formula for the heart) but lays all
  three out directly via canvas()/label()/sprite() so LIKE, VIEWS and
  COMMENTS read as one consistent row of three 76px-tall boxes -- the
  minimum legal height in the 76-88 tap-target band (#236).

- There is no fourth CLEAR tool (#218). It emitted `xviewer.clear` on BOTH
  `pressed` and `released` -- one tap ran two full feed refetches -- and
  the backend has no server-side "clear" at all, only `?refresh=1`, which
  returns the same 25 posts. So the whole visible effect of the button was
  "snap back to card 1", which is what "clear button doesnt actually clear,
  gets stuck on first one" describes. The 60s periodic refresh already does
  the only real work it did, so the tool was removed rather than relabelled,
  and its 84px went back to the three tools that remain.

- The old 14px "X Viewer" brand label is dropped. The launcher icon already
  brands the app; at this size, giving that row's pixels back to content
  (moved into a slightly taller topbar with real position + status text
  instead) is a better trade.

- The screen-level `gesture` event (swipe left/right) is added as a raw dict
  after pk.screen() returns, in the exact shape the shipped app.js/home.json
  already use (`{"type":"gesture","action":"xviewer.gesture"}`) -- panelkit's
  screen() has no `events` parameter (it's the same "kept as a raw dict"
  escape hatch the README describes for racing's lane-touch zones, which
  also don't fit a primitive). This shape predates panelkit and is already
  proven; there's no reason to route it through _tap_events()'s
  effects-wrapped shape, which is for pressed/released tap targets, not a
  gesture listener (lint.py's R2 explicitly exempts `gesture` from the tap
  contract it enforces).

Every node id below is addressed by app/app.js -- the paths are the contract
between the two files (this is exactly the pair that broke in #205 when a UI
rework deleted labels the app still addressed). See
files/xviewer/verify_xviewer_paths.py for the throwaway script that checks
every setText/setBinding/SetViewSrc path in app.js resolves in this output.

Run: python3 gen_xviewer_screen.py
"""
import json
import os
import sys

UIKIT = "/home/tunas/waveshare-devices/amoled-1.8-v2/uikit"
sys.path.insert(0, UIKIT)

import panelkit as pk  # noqa: E402
import tokens as tk  # noqa: E402

# Output target. SCRATCH_OUT exists so a layout can be rendered in the
# harness without overwriting the shipped screen; the harness reads either.
SCRATCH_OUT = ("/tmp/claude-1000/-home-tunas-DesktopShare/"
               "4726440b-614d-4cef-b150-b6bc9c295af2/scratchpad/xviewer-home.json")
PACKAGE_OUT = ("/home/tunas/waveshare-devices/amoled-1.8-v2/apps/tunastreet.xviewer"
               "/res/screens/home.json")
OUT = PACKAGE_OUT

W = tk.W          # 368
H = tk.H          # 448
BLACK = "#000000"  # xviewer's own chrome black, distinct from tokens' BG (#0f0f0f)

TOPBAR_H = 46          # tall enough to hold its text clear of the rounded corner
MEDIA_H = 220           # matches the backend's CARD_W x CARD_H contract exactly
TOOLBAR_H = 76          # the minimum legal tap-target height (#236)
POST_TEXT_H = H - TOPBAR_H - MEDIA_H - TOOLBAR_H  # 106


def topbar():
    """Position ("n/N") on the left, status/error text on the right.

    Both sit at y=18, not y=2. The glass is a rounded rectangle: at 2px from
    the top edge the corner arc eats ~38px of width, so text at the normal 16px
    inset was inside the curve -- reported twice as "the 1/24 in the top corner
    is not legible" / "too close". At y=18 the arc only wants 13px, so the
    standard edge inset is safe again. Enforced by lint R10."""
    return pk.canvas("topbar", 0, 0, W, TOPBAR_H, bg=BLACK, children=[
        pk.label("pos", 16, 18, 160, 24, text="1/1", role="body", size=16,
                  color=tk.INK, align="left"),
        pk.label("status", 184, 18, 168, 24, text="", role="body", size=16,
                  color=tk.RED, align="right"),
    ])


def media():
    """368x220 media card. Nothing in it is clickable (#220): this is the band
    the finger drags across, and a clickable child here takes the press and
    swallows the swipe. The chevrons are affordance only -- they say which way
    the card moves, they are not targets."""
    return pk.canvas("media", 0, TOPBAR_H, W, MEDIA_H, bg=BLACK, children=[
        pk.sprite("card_img", 0, 0, W, MEDIA_H, src="", align="contain",
                  hidden="imgHidden"),
    ])


def post_text():
    """Wrapped post body, 16px (#236: the only lower rung on the ladder below
    the old 20px, and the kit's hard floor) -- shrunk to give the text more
    room, since TOOLBAR_H dropping to 76 grows this box from 98 to 106.
    Direct screen child (screen() doesn't validate placement modes the way
    canvas()/stack() do), so no wrapping container is needed for a single
    absolute label."""
    return pk.label("post_text", 16, TOPBAR_H + MEDIA_H, W - 32, POST_TEXT_H,
                     text="loading feed...", role="body", size=16,
                     color=tk.INK, align="left")


def toolbar():
    """The #198 tools bar: LIKE (heart image + count), VIEWS, COMMENTS
    (replies). Three 76px-tall boxes (the minimum legal tap-target height,
    #236), sized to the total width exactly (116 + 10 + 116 + 10 + 116 ==
    368) -- see the module docstring for why this doesn't just call
    tool_bar() directly, and why there is no fourth CLEAR box (#218).

    LIKE's image sizing mirrors tool_bar()'s own image-branch formula
    (img_h = h - 26 when a caption is present, img_w = min(iw - 12, img_h))
    so it reads as the same design system even though it's assembled here by
    hand.

    Spacing: lint R4's 40px minimum is a rule about two *tap targets* being
    far enough apart to disambiguate a slightly-off tap -- it only looks at
    nodes with events, and only when both sit inside the tap-target band.
    LIKE is now the only target on this bar, so the gap is a purely visual
    one: three equal boxes at 10px, which reads as a row rather than as
    three separate widgets.
    """
    like_w = views_w = comments_w = 116
    gap = 10
    x_like = 0
    x_views = x_like + like_w + gap
    x_comments = x_views + views_w + gap
    assert x_comments + comments_w == W, "toolbar item widths must fill the panel exactly"

    like_img_h = TOOLBAR_H - 26
    like_img_w = min(like_w - 12, like_img_h)

    t_like = pk.canvas("t_like", x_like, 0, like_w, TOOLBAR_H, bg=tk.DARK,
                        radius=tk.RADIUS, click="xviewer.like", children=[
        pk.sprite("t_like_img", (like_w - like_img_w) // 2, 6, like_img_w,
                  like_img_h, src="${image.heart_off}", align="contain"),
        pk.label("t_like_c", 0, TOOLBAR_H - 22, like_w, 20, text="0",
                  role="footer", size=16, color=tk.MUTED, align="center",
                  bindings={"style.textColor": "likeColor"}),
    ])

    t_views = pk.canvas("t_views", x_views, 0, views_w, TOOLBAR_H, bg=tk.DARK,
                         radius=tk.RADIUS, children=[
        pk.label("t_views_v", 0, 10, views_w, 34, text="0", role="value",
                  size=24, color=tk.INK, align="center"),
        pk.label("t_views_c", 0, 46, views_w, 20, text="VIEWS", role="footer",
                  size=16, color=tk.MUTED, align="center"),
    ])

    t_comments = pk.canvas("t_comments", x_comments, 0, comments_w, TOOLBAR_H,
                            bg=tk.DARK, radius=tk.RADIUS, children=[
        pk.label("t_comments_v", 0, 10, comments_w, 34, text="0", role="value",
                  size=24, color=tk.INK, align="center"),
        pk.label("t_comments_c", 0, 46, comments_w, 20, text="REPLIES",
                  role="footer", size=16, color=tk.MUTED, align="center"),
    ])

    return pk.canvas("toolbar", 0, TOPBAR_H + MEDIA_H + POST_TEXT_H, W, TOOLBAR_H,
                      bg=BLACK, children=[t_like, t_views, t_comments])


def build():
    tree = pk.screen("home", bg=BLACK, children=[
        topbar(),
        media(),
        post_text(),
        toolbar(),
    ])
    # Screen-level swipe gesture -- since #220 the ONLY navigation path.
    # panelkit.screen() has no `events` param, so this is the same "raw dict,
    # doesn't fit a primitive" escape hatch the README describes for racing's
    # lane-touch zones (flat "action", not the pressed/released effects-wrapped
    # shape _tap_events() emits -- a gesture listener is not a tap target, and
    # lint's R2 exempts it). The runtime clears LV_OBJ_FLAG_GESTURE_BUBBLE on
    # this node so the swipe stops here.
    tree["events"] = [{"type": "gesture", "action": "xviewer.gesture"}]
    return tree


def main():
    tree = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(tree, f, indent=4)
        f.write("\n")
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
