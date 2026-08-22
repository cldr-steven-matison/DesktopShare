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

  y=0..28    topbar   -- "n/N" position (left) + status/error text (right)
  y=28..248  media    -- 368x220 card image, PLUS two edge tap zones
                         (left half / right half) wired to xviewer.prev /
                         xviewer.next, plus small non-interactive chevron
                         glyphs for affordance
  y=248..364 post_text -- wrapped post body, 20px
  y=364..448 toolbar   -- LIKE (heart image + count), VIEWS, COMMENTS
                         (replies), CLEAR -- the #198 "tools" bar

Design decisions worth explaining to a future reader:

- The old bottom bar crammed «, heart+likes, reposts, views, pos, » into one
  48px flex row -- six things in 360px, hence 13-28px everything. This
  rebuild moves navigation OFF the bottom bar entirely and onto the media
  card itself: the left/right halves of the 368x220 image are absolute
  canvas() tap zones for xviewer.prev/xviewer.next. That's a full 220px-tall,
  184px-wide target per direction -- categorically bigger than a 40x36
  corner glyph, and it reuses the exact z-order trick already proven in this
  codebase (gen_agent_screen.py's `tapzone`): a non-clickable sibling (here,
  the image itself, and the decorative chevron glyphs) sits ON TOP in child
  order but LVGL hit-testing skips non-clickable objects, so the tap falls
  through to the clickable canvas underneath. The nav zones are listed first
  (bottom of the stack), the image and chevrons after (visually on top, but
  inert to touch) -- so the photo renders untouched and unobstructed while
  the whole card is still tap-navigable. The README's gesture-bubble section
  (LV_OBJ_FLAG_GESTURE_BUBBLE) is why a screen-level swipe may never fire on
  this backend in the first place -- this keeps a *guaranteed* tap path for
  prev/next, per that same rationale, just relocated and enlarged.

- The bottom bar is genuinely a `tool_bar()`-shaped bar (#198's own docstring
  in panelkit.py names this exact bar), but it's hand-assembled here instead
  of calling tool_bar() directly: two of its four items (VIEWS, COMMENTS)
  need a two-line value-over-caption stat shape (a number and a label under
  it, the same shape gen_agent_screen.py's metrics() row uses) which none of
  tool_bar()'s three item kinds (image+caption, compact single-line, plain
  button) produce on their own. So this bar reuses tool_bar()'s own numbers
  (touch.target_gap_min gap, tool_bar()'s image-branch sizing formula for
  the heart) but lays all four out directly via canvas()/label()/sprite()
  so LIKE, VIEWS, COMMENTS and CLEAR read as one consistent row of four
  84px-tall boxes -- all comfortably inside the 76-88 tap-target band.

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

TOPBAR_H = 28
MEDIA_H = 220           # matches the backend's CARD_W x CARD_H contract exactly
TOOLBAR_H = 84          # within the 76-88 tap-target band
POST_TEXT_H = H - TOPBAR_H - MEDIA_H - TOOLBAR_H  # 116


def topbar():
    """Position ("n/N") on the left, status/error text on the right -- both
    replace the old 14px brand label + 12px status line (#205-style
    unreadable text). Both sit comfortably inside the body band (16-22)."""
    return pk.canvas("topbar", 0, 0, W, TOPBAR_H, bg=BLACK, children=[
        pk.label("pos", 16, 2, 160, 24, text="1/1", role="body", size=18,
                  color=tk.INK, align="left"),
        pk.label("status", 184, 2, 168, 24, text="", role="body", size=16,
                  color=tk.RED, align="right"),
    ])


def media():
    """368x220 media card. nav_prev/nav_next are absolute tap zones covering
    the left/right halves of the whole card (0-184 / 184-368, full 220px
    tall) -- listed first so they sit behind the image and chevrons in child
    order. card_img and the chevron glyphs are never clickable, so a tap
    anywhere on the photo falls through to whichever zone it lands in (the
    same non-clickable-sibling passthrough gen_agent_screen.py's `tapzone`
    uses). Both zones are >88px tall, so lint's R4 spacing rule doesn't apply
    to them at all (same gating as racing's zero-gap lane thirds)."""
    return pk.canvas("media", 0, TOPBAR_H, W, MEDIA_H, bg=BLACK, children=[
        pk.canvas("nav_prev", 0, 0, W // 2, MEDIA_H, bg=BLACK, click="xviewer.prev"),
        pk.canvas("nav_next", W // 2, 0, W // 2, MEDIA_H, bg=BLACK, click="xviewer.next"),
        pk.sprite("card_img", 0, 0, W, MEDIA_H, src="", align="contain",
                  hidden="imgHidden"),
        pk.label("chev_prev", 16, (MEDIA_H - 40) // 2, 40, 40, text="<",
                  role="value", size=32, color=tk.MUTED, align="center"),
        pk.label("chev_next", W - 16 - 40, (MEDIA_H - 40) // 2, 40, 40, text=">",
                  role="value", size=32, color=tk.MUTED, align="center"),
    ])


def post_text():
    """Wrapped post body, 20px (top of the 16-22 body band, per the brief's
    18-20px ask) -- up from the old 16px. Direct screen child (screen()
    doesn't validate placement modes the way canvas()/stack() do), so no
    wrapping container is needed for a single absolute label."""
    return pk.label("post_text", 16, TOPBAR_H + MEDIA_H, W - 32, POST_TEXT_H,
                     text="loading feed...", role="body", size=20,
                     color=tk.INK, align="left")


def toolbar():
    """The #198 tools bar: LIKE (heart image + count), VIEWS, COMMENTS
    (replies), CLEAR. Four 84px-tall boxes (within the 76-88 band), 40px
    gaps (touch.target_gap_min), widths sized to the total width exactly
    (48 + 40 + 68 + 40 + 68 + 40 + 64 == 368) -- see the module docstring for
    why this doesn't just call tool_bar() directly.

    LIKE's image sizing mirrors tool_bar()'s own image-branch formula
    (img_h = h - 26 when a caption is present, img_w = min(iw - 12, img_h))
    so it reads as the same design system even though it's assembled here by
    hand.

    Spacing: the 40px minimum is a rule about two *tap targets* being far
    enough apart to disambiguate a slightly-off tap (lint R4 only looks at
    nodes with events, and only when both sit inside the tap-target band).
    VIEWS and COMMENTS are readouts, not targets, so spending 40px on either
    side of them buys nothing and costs the captions their room -- the first
    render clipped COMMENTS to "OMMENT" and pushed CLEAR past both its
    edges. They're packed at 8px instead, and the two real targets (LIKE and
    CLEAR) end up 200px apart, five times the minimum.
    """
    like_w, views_w, comments_w, clear_w = 84, 88, 88, 84
    gap = 8
    x_like = 0
    x_views = x_like + like_w + gap
    x_comments = x_views + views_w + gap
    x_clear = x_comments + comments_w + gap
    assert x_clear + clear_w == W, "toolbar item widths must fill the panel exactly"

    like_img_h = TOOLBAR_H - 26
    like_img_w = min(like_w - 12, like_img_h)

    t_like = pk.canvas("t_like", x_like, 0, like_w, TOOLBAR_H, bg=tk.DARK,
                        radius=tk.RADIUS, click="xviewer.like", children=[
        pk.sprite("t_like_img", (like_w - like_img_w) // 2, 6, like_img_w,
                  like_img_h, src="${image.heart_off}", align="contain"),
        pk.label("t_like_c", 0, TOOLBAR_H - 22, like_w, 20, text="0",
                  role="footer", size=15, color=tk.MUTED, align="center",
                  bindings={"style.textColor": "likeColor"}),
    ])

    t_views = pk.canvas("t_views", x_views, 0, views_w, TOOLBAR_H, bg=tk.DARK,
                         radius=tk.RADIUS, children=[
        pk.label("t_views_v", 0, 10, views_w, 34, text="0", role="value",
                  size=28, color=tk.INK, align="center"),
        pk.label("t_views_c", 0, 46, views_w, 20, text="VIEWS", role="footer",
                  size=15, color=tk.MUTED, align="center"),
    ])

    t_comments = pk.canvas("t_comments", x_comments, 0, comments_w, TOOLBAR_H,
                            bg=tk.DARK, radius=tk.RADIUS, children=[
        pk.label("t_comments_v", 0, 10, comments_w, 34, text="0", role="value",
                  size=28, color=tk.INK, align="center"),
        pk.label("t_comments_c", 0, 46, comments_w, 20, text="REPLIES",
                  role="footer", size=15, color=tk.MUTED, align="center"),
    ])

    t_clear = pk.canvas("t_clear", x_clear, 0, clear_w, TOOLBAR_H, bg=tk.RED,
                         radius=tk.RADIUS, click="xviewer.clear", children=[
        pk.label("t_clear_t", 0, (TOOLBAR_H - 32) // 2, clear_w, 32,
                  text="CLEAR", role="body", size=20, color=tk.INK,
                  align="center"),
    ])

    return pk.canvas("toolbar", 0, TOPBAR_H + MEDIA_H + POST_TEXT_H, W, TOOLBAR_H,
                      bg=BLACK, children=[t_like, t_views, t_comments, t_clear])


def build():
    tree = pk.screen("home", bg=BLACK, children=[
        topbar(),
        media(),
        post_text(),
        toolbar(),
    ])
    # Screen-level swipe gesture. panelkit.screen() has no `events` param --
    # this is the same "raw dict, doesn't fit a primitive" escape hatch the
    # README describes for racing's lane-touch zones. Shape matches the
    # already-proven shipped app.js/home.json exactly (flat "action", not
    # the pressed/released effects-wrapped shape _tap_events() emits -- this
    # is a gesture listener, not a tap target, and lint's R2 exempts it).
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
