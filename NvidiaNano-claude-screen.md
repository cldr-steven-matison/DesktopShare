# Jetson screensaver: Matrix digital rain

## What it is

A Chromium-kiosk "screensaver" driven by a standalone idle-watcher instead of
xscreensaver. The active scene is a classic Matrix-style falling-code effect
(binary `0`/`1`, canvas-based) with a small glowing clock in the corner.

## Why not xscreensaver

The original setup used xscreensaver's `programs:` hack mechanism to launch
Chromium in kiosk mode. This was janky: xscreensaver hacks are expected to
render *into* a window ID that xscreensaver passes them, so they stay
correctly stacked. Chromium doesn't support that — kiosk mode always opens
its own independent top-level window. xscreensaver still creates its own
black "saver" window and keeps it on top (by design, so nothing can be
clicked through during blanking/locking). Since Chromium wasn't cooperating,
its window rendered *underneath* xscreensaver's black window — so the screen
just looked black, and moving the mouse would flash the scene for a moment
right before xscreensaver killed the child process.

Fix: ditch xscreensaver's hack model entirely. `xscreensaver` is stopped and
`~/.xscreensaver` has `mode: off` so it can't reactivate. A separate systemd
user service polls real idle time and manages Chromium directly, with no
competing window ever created.

Separately, Chromium's `--kiosk` flag did not reliably get Mutter to grant
real X11 fullscreen state — the window would come up sized close to, but not
exactly, the screen (e.g. 1854x1048 at an offset instead of 1920x1080 at
0,0). Fix: after launching, force `_NET_WM_STATE_FULLSCREEN` explicitly with
`wmctrl`.

## Components

- `~/matrix-screensaver.html` — the scene itself (self-contained, no network
  calls, works as a `file://` URL).
- `~/.local/bin/lofi-idle-watcher.sh` — polls `xprintidle`; once idle time
  crosses the threshold it launches Chromium kiosk pointed at the html file,
  then force-fullscreens the window via `wmctrl` once it appears (title-match
  retry loop, since the window takes a moment to exist). Kills Chromium again
  as soon as real activity resumes. Launches with its own isolated
  `--user-data-dir` (`~/snap/chromium/common/lofi-screensaver-profile`), not
  the user's normal chromium profile — see "Known failure modes" below for
  why.
- `~/.config/systemd/user/lofi-idle-watcher.service` — runs the watcher as a
  persistent user service (`enabled`, restarts on failure). Inherits
  `DISPLAY`/`XAUTHORITY` from the systemd user environment automatically.
- `~/.xscreensaver` — `mode: off`, kept only so xscreensaver can't interfere
  if it's ever started again.

Current idle threshold: 2 minutes (`IDLE_THRESHOLD_MS` in the watcher script).

## Matrix rain implementation notes

- Canvas 2D, not DOM elements — one draw call per column per frame, not a
  per-frame redraw of the whole trail. An early version explicitly redrew a
  90-character trail every frame across ~200 dense columns (~15k `fillText`
  calls/frame) and visibly bogged down the Nano's GPU over time. The current
  version draws exactly one new glyph per column per frame and lets a very
  faint semi-transparent black overlay (`rgba(0,0,0,0.035)`) do the fading —
  this is the actual technique behind the original effect, and it's roughly
  60x cheaper per frame while still producing a long, slow-fading trail.
- Glyphs are `0`/`1` only (no katakana).
- `fontSize = 16`, `colWidth = fontSize * 0.55` (columns packed tighter than
  the glyph width for a dense wall of falling code).
- Per-column fall speed randomized (`0.2–0.6` rows/frame) so columns don't
  move in lockstep; on reaching the bottom a column has a random chance per
  frame to reset near the top again, keeping restarts staggered rather than
  synchronized.
- Occasional (~6% per glyph) bright "spark" head character for the glow pop,
  rest are solid green (`#00d94a`).
- Runs at 24 FPS via `setInterval`, not `requestAnimationFrame`, to keep a
  fixed cheap draw rate independent of monitor refresh.

## Known failure modes (both fixed, both verified)

### 1. Silent failure to launch ("dies" with no window, no error)

Chromium originally used its default shared snap profile
(`~/snap/chromium/common/chromium`) — the same one the user's *real*
chromium browsing would use, if they ever open chromium normally. Every
`stop_saver()` kill was abrupt (`pkill`, no graceful shutdown), which could
leave a stale `SingletonLock`/`SingletonSocket`/`SingletonCookie` behind
(confirmed: found a lock pointing at a dead PID). On the next launch,
chromium saw the stale lock, tried to hand the URL off to what it thought
was an already-running instance over a dead socket, that failed silently,
and the new process just exited — no window, no stderr output.

Fix: give the kiosk launcher its own isolated `--user-data-dir`
(`~/snap/chromium/common/lofi-screensaver-profile`) so it never shares or
contends for a lock with anything else. `start_saver()` also proactively
clears any stale `Singleton*` files in that dir before every launch as a
defensive backstop.

Note: the isolated profile dir must live somewhere the snap's confinement
can actually write to — `~/snap/chromium/common/` works, `/run/user/1000/`
does *not* (chromium shows a "Failed To Create Data Directory" / "Profile
error occurred" dialog storm and silently falls back to the default shared
profile, reintroducing the exact problem this was meant to fix).

### 2. Stacked/duplicate windows ("file not found" on top of the rain)

`stop_saver()` killed chromium by matching the target URL
(`pkill -f matrix-screensaver.html`). That string only appears in the
top-level browser process's argv — chromium's zygote/renderer/gpu-process
children don't carry it. So a kill only ever removed the parent; children
(and the window they owned, and the profile's `SingletonLock`) could survive
mid-teardown. If the watcher's next loop tick fired before that teardown
finished, it would launch a *second* instance while the first was still
partially alive — hitting the still-held lock, failing to load, and
showing a blank/"file not found" window stacked in front of the still-live
(but orphaned) matrix window behind it. (Not an actual multi-monitor issue —
only one display was ever connected when this happened.)

Fix: match/kill on `--user-data-dir=$PROFILE_DIR` instead of the URL. Every
process in chromium's tree carries `--user-data-dir` in its own argv, so
this catches the whole tree in one `pkill -f`, not just the parent.
`stop_saver()` also now runs once at script startup, in case a previous
instance (or one from before a service restart) was still running or
mid-shutdown when this one starts.

Also fixed at the same time: `start_saver()`'s resolution detection used to
read a single output's active mode from `xrandr`, which picks an arbitrary
output if more than one is connected. It now reads the `Screen 0: ...
current WxH` line instead, which is the full virtual desktop size across
all connected outputs — correct even if a second monitor ever gets plugged
in.

**Verified 2026-07-02**: manually confirmed the new kill pattern takes down
the entire chromium process tree (parent + zygotes + renderers +
gpu-process) in one shot, then confirmed a fully hands-off run at the real
2-minute `IDLE_THRESHOLD_MS` — self-launched with no manual trigger, exactly
one process/window, real fullscreen geometry, valid non-stale lock.

### 3. Window comes up sized/positioned wrong (not full 1920x1080 @ 0,0)

`force_fullscreen()`'s retry loop only polled for the window for 5 seconds
(20 × 0.25s) before giving up. That's fine when the system is idle, but
right after a reboot, or with apt/dpkg/snap updates running in the
background, chromium can take much longer than 5 seconds to actually create
its window — reproduced directly with system load average ~4.5 (post-reboot
+ updates in progress): the window didn't exist until ~7s after launch,
well past the old timeout, so `wmctrl -r ... fullscreen` was never called
and the window was left at chromium's imperfect default kiosk geometry
(e.g. `1854x1011` at `80,118` instead of `1920x1080` at `0,0`).

Fix: extended the retry loop to poll for up to a minute (240 × 0.25s)
instead of 5 seconds. Cheap to wait longer since this runs in its own
backgrounded/disowned subshell and doesn't block anything else.

**Verified 2026-07-10**: reproduced the bad geometry under real load (apt/
dpkg mid-update, load average ~4.5), applied the fix, then confirmed a
fully hands-off run at the real 2-minute threshold under the same load —
window came up at the correct `1920x1080` @ `0,0` with no manual
intervention.

## Adjusting

Edit `~/matrix-screensaver.html` (glyph size/speed/color/trail fade) or
`~/.local/bin/lofi-idle-watcher.sh` (idle threshold), then:

```bash
systemctl --user restart lofi-idle-watcher.service
```

To check it's alive: `systemctl --user status lofi-idle-watcher.service`.
To watch it fire without waiting: temporarily set `IDLE_THRESHOLD_MS` low
(e.g. `8000`), restart, then stop touching the mouse/keyboard entirely for a
few seconds — any input, including interacting with a terminal, resets the
idle clock.
