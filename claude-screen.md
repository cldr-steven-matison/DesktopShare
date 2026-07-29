# Matrix digital rain screensaver

Two independent implementations of the same idea, one per platform. Both
drive the same self-contained HTML canvas scene; the launch/idle mechanics
are platform-specific because Linux/X11 and Windows need genuinely different
tricks. Read the section for the device you're touching — don't assume a fix
on one side applies to the other without checking.

- **Jetson Orin Nano** (native Ubuntu desktop) — see "Jetson implementation" below. Live since 2026-07-02, wired to Twitch chat's `!matrix` since 2026-07-21; command syntax unified to `!matrix screen1` (explicit, no bare `!matrix`) on 2026-07-25 — see "Chat command syntax" note below.
- **StarlinkAI (TunaStarlink / Beelink, Windows 11 + WSL2)** — see "Windows implementation (TunaStarlink)" below. Built and verified 2026-07-23; extended to independent per-screen targeting and a 3rd monitor 2026-07-24 (capped at 2 simultaneous screens after a real crash — see "Known failure mode" #2). Same day, both Scheduled Tasks were switched from `python.exe` to `pythonw.exe` after a separate discovery — see "Known failure mode" #3. **Wired to Twitch chat since 2026-07-25** — `!matrix screen3`/`!matrix screen4` (array-wide numbering, same mismatch-with-local-names as `!load` — see `streamers-twitch-bot-mpv-plan.md`).
- **WindowsDesktop (MINI-Gaming-G1 / Windows gaming PC)** — see "Windows implementation (WindowsDesktop / MINI-Gaming-G1)" below. Built, verified, and wired to Twitch chat 2026-07-25 (`!matrix screen2`) — ported from the StarlinkAI implementation, ported over close to verbatim as expected. Same session also replaced this device's `!load` (Chrome/`browser_launcher.py`) with the mpv-based approach — see `streamers-twitch-bot-mpv-plan.md`.

**Chat command syntax (updated 2026-07-25):** `!matrix` now always requires an explicit screen argument — `!matrix screen1|screen2|screen3|screen4` — matching `!load`'s own explicit numbering. There is no more bare `!matrix` defaulting to the Jetson; a bare `!matrix` (or any unrecognized screen token) is simply not a recognized command and gets no reply, same as an unrecognized `!load` screen. Changed in `TwitchChatListenerProcessor` (`0.0.18-SNAPSHOT`) and in central NiFi's `TwitchChatBot` `RouteOnAttribute`, which had its `matrix` dynamic property/relationship renamed to `matrix-screen1` (still targets the same Jetson `matrixListener` endpoint — only the internal routing name changed, not the wiring). Nothing on the edge/device side needed to change for this — `windows_matrix_launcher.py` never had a `screen1` entry (see "Known failure mode" #2 below), and the Jetson's own launcher script only ever served one screen.

## Jetson implementation

### What it is

A Chromium-kiosk "screensaver" driven by a standalone idle-watcher instead of
xscreensaver. The active scene is a classic Matrix-style falling-code effect
(binary `0`/`1`, canvas-based) with a small glowing clock in the corner.

### Why not xscreensaver

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

### Components

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

### Matrix rain implementation notes

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

### Known failure modes (both fixed, both verified)

#### 1. Silent failure to launch ("dies" with no window, no error)

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

#### 2. Stacked/duplicate windows ("file not found" on top of the rain)

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

#### 3. Window comes up sized/positioned wrong (not full 1920x1080 @ 0,0)

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

#### 4. Device went fully unresponsive to `!load`/`!matrix` — inbound dead, outbound fine (found and fixed 2026-07-26)

`!load screen1`/`!matrix screen1` stopped doing anything. Diagnosed before
Steven had hands on the device: EFM showed the `NvidiaNano` agent `ONLINE`
with a heartbeat only seconds old, but the device (`192.168.1.195`) was
100% unreachable for everything inbound — `ping` and direct `curl` to all
three relevant listener ports (8080/8081/8082) all timed out. Confirmed
both from WindowsDesktop and from *inside* the `mynifi-0` pod (the
actual source of the real `InvokeNvidiaNano`/`InvokeNvidiaNanoMatrix`
trigger calls), ruling out a routing fluke specific to one machine.

That split — outbound heartbeat to EFM still succeeding, everything
inbound (including ICMP) completely dead — means the device's own network
stack/listeners were wedged, not a NiFi/EFM/flow-config problem on the
central-NiFi side. Nothing to fix there; central NiFi's wiring was already
correct.

**Fix:** Steven restarted the Jetson directly. Confirmed back up and
responding to `!load`/`!matrix` afterward.

Worth remembering as a diagnostic signature for next time this class of
device (or any EFM-heartbeating edge box) looks unresponsive: check
whether the EFM heartbeat is still fresh *before* assuming the flow or the
trigger wiring is broken — a live heartbeat with dead inbound reachability
points straight at the device itself, not the flow.

### Adjusting

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

## Windows implementation (StarlinkAI / TunaStarlink)

### What it is

Same HTML scene, ported to Windows 11 (native Win32, not WSL2/WSLg — WSLg's
virtualized X11 socket produces app windows *inside* Windows, it doesn't
control real monitor output the way a screensaver needs to). Edge kiosk mode
stands in for Chromium; a small Python HTTP listener stands in for the
xscreensaver-hack-avoidance problem (which doesn't exist on Windows — no
xscreensaver-equivalent conflict to route around); a Python idle-watcher
polling `GetLastInputInfo` stands in for `xprintidle`. Both run as persistent
Scheduled Tasks instead of systemd user services.

Built to match WindowsDesktop's existing `browser_launcher.py` /
`gaming-pc-launch_stream.py` pattern (see `streamers-twitch-bot.md` and
`files/browser_launcher.py`) as closely as possible, since that pattern is
the one already proven to work for triggering Windows GUI actions from NiFi
without touching native MiNiFi C++'s broken Python `ExecuteScript` support
(see `efm-binaries-windows-python.md`).

### Components

- `C:\minifi-manual\matrix-screensaver.html` — the scene, unchanged from the
  Jetson version except it's a fresh reconstruction from this doc's spec
  (the Jetson's actual file lives only on that device, not in git — if the
  two ever need to be byte-identical, diff them directly rather than trusting
  this doc word-for-word).
- `C:\minifi-manual\windows_matrix_launcher.py` — HTTP listener, port 5901,
  `0.0.0.0` bound (matches `browser_launcher.py`'s existing bind — loopback-
  only by convention today, not by firewall; see "Next steps" on wiring this
  up before it becomes reachable from a pod). Per-screen model as of
  2026-07-24: a `SCREENS` dict keyed by logical name (`screen2`, `screen3` —
  see below for why there's no `screen1` entry), each with its own
  `position`/`size`/profile-dir prefix. `POST /matrix/<screen>` launches that
  screen only; `POST /kill/<screen>` tears down that screen only. Each
  screen's Edge process is tracked by its own PID (`_running[name]`), and
  kill/relaunch acts on that PID specifically (`taskkill /PID ... /F /T`) —
  **not** `taskkill /IM msedge.exe`, which would kill every Edge process on
  the box (the user's own regular browsing included) and, with multiple
  independent kiosk targets, would also kill the other screen's window.
  `POST /matrix` and `POST /kill` (no screen name) remain as aliases for
  `screen2`, kept only so the existing `idle_watcher.py` calls (see below)
  and any already-wired external caller keep working unchanged. Registered
  as Scheduled Task `MatrixLauncherListener`.
- `C:\minifi-manual\idle_watcher.py` — polls `GetLastInputInfo`/`GetTickCount`
  every 2s, 2-minute threshold (`IDLE_THRESHOLD_MS`, same default as the
  Jetson). Idle detection is desktop-wide (`GetLastInputInfo` has no
  per-monitor concept), so on crossing the threshold it self-POSTs to launch
  **both** `screen2` and `screen3` from the one idle signal, and kills both
  on real activity resuming. Registered as Scheduled Task `MatrixIdleWatcher`.
- Both Scheduled Tasks: `AtLogOn` trigger for `TunaStarlink\tunas`,
  `RestartCount=3`/`RestartInterval=1min`, unlimited execution time — same
  shape as WindowsDesktop's `BrowserLauncherListener` task. Action is
  `pythonw.exe` (not `python.exe`) as of 2026-07-24 — see "Known failure
  mode" #3.

Screens, confirmed via `[System.Windows.Forms.Screen]::AllScreens`:

| Logical name | Monitor | Position/size | Idle-watcher driven? |
|---|---|---|---|
| (none — excluded) | DISPLAY1, primary, `0,0` `1536x864` | n/a | No — Steven's active work screen, never touched |
| `screen2` | DISPLAY2 | `1920,0` `1920x1080` | Yes |
| `screen3` | DISPLAY3 (added 2026-07-24, USB-C→HDMI on the rear port) | `3840,0` `1920x1080` | Yes |

`screen1` was added briefly on 2026-07-24 to cover DISPLAY1 too, tested once, and removed after it caused the crash documented in "Known failure mode" #2 below. It is not in `windows_matrix_launcher.py`'s `SCREENS` dict at all (not just excluded from the idle watcher) — `POST /matrix/screen1` now 404s.

### Why this diverged from the Jetson's approach

- **No wmctrl/F11 fullscreen-force needed.** Confirmed live: unlike Linux
  Chromium (which locks `--kiosk`'s rendered output to whichever monitor the
  *cursor* is on at launch, ignoring `--window-position` entirely — this is
  why WindowsDesktop's `reposition_chrome.ps1` exists, launching windowed then
  forcing position+fullscreen after the fact), Edge on Windows honors
  `--window-position`/`--window-size` together with `--kiosk` directly. A
  first attempt at porting WindowsDesktop's MoveWindow+simulated-F11 approach
  actually shipped and was tested first — it worked for *positioning* but the
  simulated F11 keypress (`keybd_event`) never actually triggered fullscreen,
  most likely because a background/non-interactive process can't reliably
  win `SetForegroundWindow` (Windows' foreground-lock protection), so the
  synthetic keypress had nowhere reliable to land. Rather than fight that,
  switched to passing kiosk + position flags in one launch — simpler and it
  just works. `--edge-kiosk-type=fullscreen` is used alongside plain
  `--kiosk` for reliability (Edge's own explicit kiosk-variant flag).
- **No xscreensaver-equivalent problem.** Windows has no competing
  screensaver process fighting for window stacking the way xscreensaver did
  on the Jetson — there was simply nothing to disable.

### Known failure mode #1: InPrivate/windowed fallback (found and fixed, verified 2026-07-23)

**Symptom:** an unattended, idle-watcher-triggered launch came up as a
normal windowed Edge window (visible tabs/address bar, title bar showing
`Matrix - [InPrivate] - Microsoft​ Edge`) instead of a clean fullscreen
kiosk — on the correct monitor, just not fullscreen.

**Root cause:** the first version of the launcher reused a single profile
dir path (`edge-matrix-profile`), deleting and recreating it
(`shutil.rmtree` then relaunch) on every trigger to avoid session-restore
duplicate-tab issues (which did happen once, live — reusing without deleting
first restored a stale tab, producing two "Matrix" tabs in one window).
Deleting and immediately reusing the *same* path raced a not-quite-dead
previous Edge process still holding a handle on it — `taskkill /F /T`
returning doesn't guarantee every file handle in the process tree is
released yet. Edge then silently fell back to a windowed/ephemeral profile
instead of failing loudly.

**Fix:** every launch now gets a fresh, uniquely-named profile dir
(`edge-matrix-profile-<epoch-ms>`) instead of delete-then-reuse. Old ones are
best-effort cleaned up at the start of the next launch
(`shutil.rmtree(..., ignore_errors=True)` on any stale ones except the one
about to be used) — a directory still locked by a slow-dying previous
process just gets skipped and retried next time, never blocks the current
launch.

**Note, not a bug:** the `[InPrivate]` label in the window title is cosmetic
and harmless — Edge defaults a brand-new `--user-data-dir` (no prior `Local
State` file) into an ephemeral/InPrivate-flavored profile, and it's
invisible in real kiosk mode anyway (no title bar rendered). It was only
ever visible in the *broken* windowed-fallback case above, which is what
made it look alarming — the actual bug was the missing fullscreen, not the
InPrivate labeling. Confirmed via screenshot: a normal successful kiosk
launch carries the same internal title string and looks completely clean.

**Verified 2026-07-23:** manual `/matrix` trigger (repeated, clean kiosk
every time after the fix), `/kill` trigger (confirmed `msedge.exe` count
drops to 0), full idle cycle with a temporarily-lowered threshold (auto-
launch after crossing idle, auto-kill after simulated real input via
`mouse_event` — `SetCursorPos` alone does *not* reset Windows' idle clock,
unlike a real hardware move), and the real registered Scheduled Tasks
(stopped ad-hoc manual processes, started via `Start-ScheduledTask`,
retested through those). Confirmed via `GetWindowRect` that the kiosk window
lands exactly at `1920,0 → 3840,1080` (DISPLAY2) and Steven's primary
monitor/work session is never touched.

### Known failure mode #2: 3-screen simultaneous trigger crashes the box (found 2026-07-24, not a software bug — a hardware/driver ceiling)

**Symptom:** after adding a 3rd monitor (DISPLAY3) and refactoring the
launcher to support independent per-screen targeting (see Components above),
`screen1`/`screen2`/`screen3` were triggered simultaneously as a one-off test
("turn matrix on all 3 of this device's screens"). All three came up
correctly (confirmed via `Get-Process msedge` showing 3 independent kiosk
windows at the right rects, plus Steven's own regular Edge window untouched)
— but within roughly two minutes the whole box hard-crashed and rebooted.

**Root cause:** confirmed via `Get-WinEvent` — Kernel-Power ID 41 (unexpected
shutdown) and a WER bugcheck event: **`0x00000133`
(`DPC_WATCHDOG_VIOLATION`)**, dump saved to
`C:\WINDOWS\Minidump\072426-15234-01.dmp`. This means a driver — near-
certainly the AMD Radeon 780M's display/compositor path — held a deferred
procedure call too long while compositing three simultaneous full-HD, 24fps,
GPU-accelerated kiosk surfaces, and Windows' watchdog forced a full reboot
rather than let the system hang. This is a real OS-level crash, not a
performance hiccup or a bug in the launcher/HTML — the per-screen process
isolation worked exactly as designed (all 3 windows launched cleanly, no
profile-dir collisions, no Python exceptions in the crash log), the
underlying integrated GPU simply couldn't sustain the composited load.

One caveat worth flagging: the **exact same bugcheck (`0x133`) also occurred
once before, on 2026-07-23 at 9:29 AM**, unrelated to any of this Matrix
work — so this box's AMD driver has some baseline DPC watchdog fragility.
3-simultaneous-screen Matrix load is a strong, reproducible trigger for it
here, but may not be the *only* thing that can trigger it.

**Decision (not a fix — a scope limit):** this device runs **at most 2**
Matrix screens simultaneously: `screen2` + `screen3`. `screen1` (DISPLAY1,
the primary/work monitor) was removed from `windows_matrix_launcher.py`'s
`SCREENS` dict entirely — see Components above — rather than merely left out
of the idle watcher, specifically so an accidental/future `/matrix/screen1`
call can't recreate the 3-screen combination that caused this. If a real
need for `screen1` support ever comes up, re-add it deliberately, and do not
trigger it alongside both `screen2` and `screen3` at once.

**Verified 2026-07-24 post-recovery:** confirmed clean state after reboot —
no leftover Edge/kiosk processes, `MatrixLauncherListener`/`MatrixIdleWatcher`
scheduled tasks manually restarted and responsive (`Start-ScheduledTask` +
port-5901 reachability check), `screen1` removed from the running listener's
code and confirmed `/matrix/screen1` now returns `404`.

### Known failure mode #3: scheduled task opens a visible Windows Terminal window, and closing it kills the listener (found and fixed 2026-07-24)

**Symptom:** every time `MatrixLauncherListener`/`MatrixIdleWatcher` was
(re)started via `Start-ScheduledTask`, a new Windows Terminal window popped up
on screen, titled with the raw `python.exe` path. Separately, the launcher
listener was found dead (`LastTaskResult` = `3221225786` / `0xC000013A`,
`STATUS_CONTROL_C_EXIT`) shortly after being restarted, with no exception in
its own crash log — implying something external killed it.

**Root cause:** this Windows 11 build has Windows Terminal set as the default
host application for console apps. Any scheduled task whose action is
`python.exe` (a console app) with no console already attached gets a brand
new, visible Windows Terminal window created to host it. Closing that window
(or anything that tears it down) sends a close signal to the process it's
hosting — killing the listener with exactly the `STATUS_CONTROL_C_EXIT` code
observed. This was happening silently on every restart, not something either
script did wrong.

**Fix:** both tasks' action was switched from
`...\Python312\python.exe "<script>"` to `...\Python312\pythonw.exe "<script>"`
— `pythonw.exe` is the windowless variant that ships with every CPython
install, so no console is ever created and no terminal window ever opens.
Confirmed via a full `EnumWindows` scan after restart: no extra window
appears, listener stays up.

**Applies beyond Matrix:** this is a property of the box, not this script —
`MpvStreamLauncherListener` (see the mpv/stream-loader work,
`streamers-twitch-bot-mpv-plan.md`) was registered with `pythonw.exe` from the
start for the same reason. Any *future* scheduled task on this device running
a plain Python console script should default to `pythonw.exe` too, not
`python.exe`.

### Adjusting

Edit `C:\minifi-manual\matrix-screensaver.html` or the `MATRIX_POSITION`/
`MATRIX_SIZE`/`IDLE_THRESHOLD_MS` constants, then from an elevated or normal
PowerShell prompt:

```powershell
Stop-ScheduledTask -TaskName MatrixLauncherListener
Stop-ScheduledTask -TaskName MatrixIdleWatcher
Get-Process pythonw | Stop-Process -Force
Start-ScheduledTask -TaskName MatrixLauncherListener
Start-ScheduledTask -TaskName MatrixIdleWatcher
```

To trigger manually without waiting for idle (per-screen — `screen2` and/or
`screen3`, never both plus a hypothetical `screen1` at once, see "Known
failure mode" #2):

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:5901/matrix/screen2 -Method POST -Body '{}' -ContentType 'application/json' -UseBasicParsing
Invoke-WebRequest -Uri http://127.0.0.1:5901/matrix/screen3 -Method POST -Body '{}' -ContentType 'application/json' -UseBasicParsing
```

(`/matrix` with no screen name is still accepted as an alias for `screen2`,
kept only for `idle_watcher.py`'s existing calls — prefer the explicit
`/matrix/screen2` form for anything new.)

(`-UseBasicParsing` matters here — without it, `Invoke-WebRequest` on this
box throws a `NullReferenceException` from its HTML-parsing path, unrelated
to the actual HTTP response. Basic parsing skips that entirely.)

## Windows implementation (WindowsDesktop / MINI-Gaming-G1)

### What it is

Ported from StarlinkAI's implementation above, close to verbatim as
expected (`claude-screen.md`'s own earlier "Next steps" note predicted this).
Built 2026-07-25 from a Claude Code session running directly on this box
(WSL2), which meant direct filesystem access to `C:\minifi-manual\` via
`/mnt/c/minifi-manual/` and `powershell.exe` interop for testing — unlike
StarlinkAI, no separate device session was needed.

Single target screen in scope: the right/primary monitor (`0,0` `1920x1080`),
the same monitor `!load` already used before this work — see
`streamers-twitch-bot.md` for the original `screen1`=left-non-primary /
`screen2`=right-primary layout. `screen1` (left monitor) was never in scope
here, matching StarlinkAI's own primary-monitor exclusion for a different
reason (there it's Steven's own work screen; here it's simply not the
`!load`-targeted screen).

### Components

- `C:\minifi-manual\matrix-screensaver.html` — reconstructed from this doc's
  own "Matrix rain implementation notes" section (canvas technique, fontSize,
  fade rate, spark-glyph chance, 24fps `setInterval`), not copied from either
  existing device (neither's actual file is in git).
- `C:\minifi-manual\windows_matrix_launcher.py` — port `5903` (not `5901`:
  that port is `browser_launcher.py`'s, now retired — see below). `SCREENS`
  dict has one entry, `screen2`. Same unique-profile-dir-per-launch and
  PID-tracked kill discipline as StarlinkAI's version. One additive
  coexistence call: `POST 127.0.0.1:5902/stop/screen2` (the mpv listener)
  before showing matrix. Registered as Scheduled Task
  `MatrixLauncherListener`, `pythonw.exe`.
- `C:\minifi-manual\mpv_stream_launcher.py` — port `5902`, single `screen2`
  entry, same `SetWindowPos`/`--force-window=immediate` approach already
  proven on StarlinkAI (ported directly, not re-derived — see
  `streamers-twitch-bot-mpv-plan.md` for why `--screen=N`/`--geometry` don't
  work). Replaces `browser_launcher.py`'s role for `!load` entirely: calls
  `:5903/kill/screen2` best-effort before playing, same as StarlinkAI's
  coexistence pattern in the other direction. Registered as Scheduled Task
  `MpvStreamLauncherListener`, `pythonw.exe`.
- `browser_launcher.py`'s `BrowserLauncherListener` Scheduled Task —
  **stopped**, not deleted, once `mpv_stream_launcher.py`'s `/load/screen2`
  was confirmed working. Files left on disk.
- Pod-side (`minifi-agent-k8s-gaming`, `KubernetesPod` class): existing
  `ListenHTTP-StreamLoad`(8082)→`LaunchGamingPCStream` had its resource
  script updated (`gaming-pc-launch_stream.py` — `LISTENER_URL` now points at
  `:5902/load/screen2`, and it stopped constructing the Twitch URL itself,
  since `mpv_stream_launcher.py` does that now — Kick support for free). New
  pair added: `ListenHTTP-MatrixLoad`(8081)→`LaunchGamingPCMatrix` (runs new
  resource `gaming-pc-launch_matrix.py`, fixed single action mirroring
  `agent-NvidiaNano-launch_matrix.py`'s shape → `POST :5903/matrix/screen2`).
- Central NiFi `TwitchChatBot`: `RouteOnAttribute` gained `matrix-screen2`;
  `InvokeGamingPCMatrixScreen2` → the pod's `:8081`. `InvokeGamingPCScreen2`
  (existing, `!load`) unchanged in shape, only its URL's IP (see gotcha
  below).

### A real gotcha hit doing this work: this pod's EFM heartbeat had been dead for 6 days, and its IP changes on every restart

Two separate problems, found and fixed in the same session:

1. **`minifi-agent-k8s-gaming`'s EFM heartbeat had silently stopped 6 days
   before this session** (confirmed via `agent.last_seen` in EFM's Postgres —
   stale, matching the pod's own uptime with 0 restarts). The pod was still
   running fine on its last-deployed config the whole time — MiNiFi C++
   doesn't need EFM once a flow is deployed — but any *new* EFM-side push
   (new processors, resource re-uploads) had nowhere live to land. Fixed by
   restarting the pod: this is a **bare pod, no Deployment/StatefulSet owner**
   (`kubectl get pod ... -o jsonpath='{.metadata.ownerReferences}'` empty) —
   `kubectl delete` does **not** get it rescheduled automatically. Recovery
   path: save the exact manifest from the
   `kubectl.kubernetes.io/last-applied-configuration` annotation before
   deleting, `kubectl apply` it back after. Confirmed the deployer curl args
   (including `agentIdentifier`) are baked into that annotation, so the
   restarted pod re-registers as the *same* EFM agent record, not a new one.
2. **A fresh pod boot doesn't guarantee the EFM-assigned resource *files*
   land on disk in time for the flow's first start attempt.** Even though
   the freshly-pulled `config.yml` had the right processor definitions
   immediately, `/nifi-minifi-cpp-1.26.02/asset/` stayed empty (`{"digest":
   "", "assets": {}}` in `.state`) well past the point where all three
   `ExecuteScript` processors (including one pre-existing, unrelated to this
   work) had already failed to start and given up retrying after 3 attempts
   (30s apart, then stopped — no infinite retry). Fixed with a direct
   `kubectl cp` of all three script assets onto the pod, then killing and
   restarting just the `minifi` background process inside the container
   (`kill <pid>`, `./bin/minifi &` from `/nifi-minifi-cpp-1.26.02`) — cheaper
   and lower-risk than another full pod delete/reapply, and it picked up the
   already-correct `config.yml` cleanly with the assets now actually present.
3. **This pod's IP changes on every restart** (it's bare, no stable
   `Service`) — `10.244.2.115` → `10.244.2.127` across this one restart.
   Both `InvokeGamingPCScreen2` and the new `InvokeGamingPCMatrixScreen2` in
   central NiFi have this IP hardcoded in their `HTTP URL` property. Caught
   and fixed same-session (both updated to the new IP), but this will recur
   on any *future* restart of this specific pod — worth remembering, and
   worth considering a real `Service` for this pod if it keeps needing
   manual restarts.

## Next steps / advice for next agent

All three devices are now built and wired to chat (`!matrix screen1|screen2|screen3|screen4`, screen argument required — see "Chat command syntax" note above) as of 2026-07-25. What's left:

1. **Real chat-triggered end-to-end test for GamingPC.** Everything was verified directly (pod-internal `curl` calls, Windows-side window rect/title checks — see the gotcha section above), but not yet through an actual `!matrix screen2` typed in real Twitch chat. Same caveat applies to `!load screen2` now that it's mpv-based instead of Chrome-based.
2. **Housekeeping.** `C:\minifi-manual\edge-matrix-profile-<timestamp>` directories accumulate one per launch on both Windows devices; best-effort cleanup runs on every new launch but only opportunistically. Not a problem yet, worth a periodic sweep if `!matrix` traffic grows. Listener ports (`5901`/`5903` for matrix, `5902` for mpv, device-dependent) bind `0.0.0.0` — fine while effectively loopback/pod-bridge-only in practice, revisit if a real external network caller ever needs one directly.
3. **`minifi-agent-k8s-gaming`'s IP instability** (see the gotcha section above) — worth a real `Service` in front of this pod if it needs restarting again, so central NiFi's `InvokeGamingPCScreen2`/`InvokeGamingPCMatrixScreen2` don't need a manual IP fix every time.
4. **The InvokeHTTP-per-screen fan-out in `TwitchChatBot`** (7 `InvokeHTTP`s off one `RouteOnAttribute` as of this session) — Steven flagged wanting a less repetitive shape for this, explicitly deferred to a separate dedicated review, not done here.
