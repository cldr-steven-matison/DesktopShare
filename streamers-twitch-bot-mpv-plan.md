# Twitch chat stream loader — mpv/yt-dlp migration plan

This replaces the current kill-Chrome/relaunch-Chrome cycle used by both screens with a persistent `mpv` player controlled over its IPC socket. Written up before starting so there's a clear reference when it gets picked up.

## Status as of 2026-07-25: WindowsDesktop (`screen2`) done too — both mpv screens now built, real chat test still the one open item on both

Session on WindowsDesktop itself (not StarlinkAI) replaced `!load screen2`'s Chrome/`browser_launcher.py` path with the same mpv approach below — `mpv_stream_launcher.py` ported directly (`SetWindowPos` positioning, `--force-window=immediate`, single `screen2` entry, port `5902`), verified end-to-end via direct pod-internal `curl` calls (WSL2 can't route to raw pod IPs, so central-NiFi-path testing from a dev shell isn't possible — same limitation hit on both devices' work). `browser_launcher.py`'s `BrowserLauncherListener` task stopped (not deleted). Same session also built `!matrix screen2` (Windows implementation ported from StarlinkAI, port `5903`) — see `claude-screen.md`'s "Windows implementation (WindowsDesktop / MINI-Gaming-G1)" section for the full writeup, including a real gotcha: `minifi-agent-k8s-gaming`'s EFM heartbeat had been dead 6 days, needed a pod restart to fix, which also changed the pod's IP (bare pod, no stable Service) and broke both `InvokeGamingPCScreen2` and the new `InvokeGamingPCMatrixScreen2` in central NiFi until caught and fixed same-session.

Also fixed this session: the double chat-message bug (`!matrix` was posting both an immediate "loading" ack and `TwitchChatReplyProcessor`'s own "now active" confirmation — now just the one, screen-number-aware reply), and added a global cooldown shared by `!load`/`!matrix` (`Cooldown Seconds` property, default 10s) to protect the edge hardware from chat spam.

## Status as of 2026-07-24 (night session): StarlinkAI-side built, deployed, and manually verified end-to-end; real Twitch-chat test still pending

**This session's work (2026-07-24, StarlinkAI-side Claude session):** installed
`mpv`(`shinchiro.mpv` via winget) and `yt-dlp`(`yt-dlp.yt-dlp` via winget,
pulls in `deno`/`FFmpeg` deps automatically) on StarlinkAI. Deployed
`mpv_stream_launcher.py` to `C:\minifi-manual\`, registered as Scheduled Task
`MpvStreamLauncherListener` (same shape as the Matrix tasks — see
`claude-screen.md`). Hit **three separate, real bugs** getting mpv to land on
the correct monitor, documented in detail below since the fix for each is
non-obvious and easy to reintroduce. All fixes are live in
`files/mpv_stream_launcher.py` (the checked-in copy) and confirmed byte-
identical to the deployed `C:\minifi-manual\mpv_stream_launcher.py`.

**Confirmed working, manually, via direct HTTP calls (not yet via real Twitch
chat):**
- `yt-dlp` resolves both Twitch and Kick to real stream URLs from this box —
  tested against `xqc` (live on both platforms at test time). Kick's
  extractor is **reliable**, not the "unverified" risk flagged in the
  original plan below.
- `/load/screen2` and `/load/screen3` each independently launch mpv, position
  it correctly on the right physical monitor, and fullscreen — verified both
  by `GetWindowRect` (exact monitor rect) and visual confirmation.
- The matrix↔stream handoff works **both directions**: triggering
  `/matrix/screen2` while mpv is playing stops mpv's playback, exits its
  fullscreen, and minimizes it (confirmed via `IsIconic`) before Edge's kiosk
  window launches — no two composited fullscreen surfaces stacked on one
  screen. Loading a stream again on the same screen afterward correctly
  un-minimizes and re-fullscreens the existing mpv process (not a fresh
  launch) and kills the Edge window via mpv's own best-effort call into
  `windows_matrix_launcher.py`'s `/kill/<screen>`.
- `windows_matrix_launcher.py` (live on `C:\minifi-manual`, **not** tracked in
  this repo — see `claude-screen.md`) got the one additive edit from the
  "still needed" list below: `_launch_screen()` now calls a best-effort
  `POST http://127.0.0.1:5902/stop/<screen>` before its existing Edge-launch
  logic. Nothing else in that file was touched.

**Not done this session:** the real end-to-end test from actual Twitch chat
(`!load <streamer> screen3`/`screen4`, `!load kick:<slug> screen3`) — the
array wasn't live tonight, so this is manually verified via direct HTTP calls
only, not through the real NiFi→EFM→listener path. That's the next thing to
confirm before calling this fully done. Flow definitions
(`TwitchChatBot.json`/`StarlinkAI.json`) were re-exported in an earlier
session and are still sitting uncommitted — hold off on committing until
after that real-chat test passes (see "Still needed" item 8 below).

### Three real bugs in getting mpv onto the right monitor — read before touching screen positioning again

All three were found by trial and error initially, but the final root cause
of each is understood and fixed, not worked around:

1. **`--screen=N` index isn't stable across reboots/driver resets.** First
   confirmed live: `mpv --screen=1` → DISPLAY2, `--screen=2` → DISPLAY3.
   After a couple of the box's own crash/reboot cycles that same night, the
   *identical* command (`--screen=1`) landed on DISPLAY1 instead — the
   monitor enumeration order mpv (and apparently the underlying Windows
   display topology) assigns isn't stable across driver
   resets/reboots on this box. A hardcoded index is unsafe here.
2. **`--geometry=<W>x<H>+<X>+<Y>` is monitor-relative, not virtual-desktop-
   absolute.** Tried as the fix for #1, using the same absolute pixel values
   already proven stable for `windows_matrix_launcher.py`'s Edge
   `--window-position` (`1920,0`/`3840,0`). Still landed on DISPLAY1 — mpv's
   own geometry parser positions relative to whatever monitor it already
   considers "current" (default/primary), not the full virtual desktop the
   way native Win32 `SetWindowPos` (what Chromium/Edge use under the hood)
   does.
3. **`--idle` alone doesn't create a window until a file loads** (mpv's own
   documented behavior). This one blocked the *actual* fix: bypassing mpv's
   own positioning entirely and calling `SetWindowPos` directly (via a
   `Get-Process -Id <pid> | MainWindowHandle` + `Add-Type`-declared
   `SetWindowPos` PowerShell subprocess call — the exact technique already
   used live to debug window rects earlier in this same session) — because
   with plain `--idle` and no loaded file, mpv had no window at all yet,
   so `MainWindowHandle` stayed `0`/absent for the full wait and there was
   nothing to position. Fixed by adding `--force-window=immediate`, which
   forces mpv to create and hold open a real window in idle mode. With that
   flag present, the `SetWindowPos` approach worked immediately and has been
   reliable since (confirmed on both screen2 and screen3, matching exact
   monitor rects both times).

**The final, working approach** (implemented in `_position_window()` and
`ensure_mpv_running()` in `files/mpv_stream_launcher.py`): launch mpv
windowed with `--force-window=immediate` (no `--screen`/`--geometry` flags at
all), find its window via `Get-Process -Id <pid>` from a PowerShell
subprocess, `SetWindowPos` it to the absolute target rect, *then* toggle
fullscreen via mpv's own JSON IPC (`set_property fullscreen true`) only after
that placement has settled — mirrors the "position first, fullscreen after"
technique already used for WindowsDesktop's Chrome (`reposition_chrome.ps1`,
see `streamers-twitch-bot.md`) for exactly the same underlying reason
(fullscreening onto "whichever monitor the window is currently on" only works
if the window is already actually on the right monitor first).

**A fourth, smaller bug found stopping mpv cleanly:** mpv's own IPC property
`window-minimized` does **not** actually iconify the window (confirmed via
`IsIconic` staying `False` after setting it `true` — likely not fully wired
up for this VO/platform combination in this mpv build). Fixed the same way
as the positioning bugs: bypassed mpv's own property and called
`ShowWindow(hwnd, SW_MINIMIZE)` directly via the same
PowerShell-subprocess-plus-`Add-Type` technique. `/stop` now: sends IPC
`stop` (halts playback) → sets `fullscreen` `false` via IPC → waits ~0.3s for
that transition to settle → `ShowWindow(..., SW_MINIMIZE)`. `ensure_mpv_running()`
mirrors this on the way back in for an *already-running* process (not just a
fresh launch): `ShowWindow(..., SW_RESTORE)` then IPC `fullscreen` `true` —
without this, a second `/load` on a screen that was previously stopped would
have loaded the stream invisibly behind a still-minimized window.

Real scope decision (2026-07-24/25): build `screen3`/`screen4` (array-facing) stream loading on StarlinkAI directly via `mpv`+IPC now — **not** the Jetson-first rollout order this doc originally proposed below. Went straight to StarlinkAI because StarlinkAI/EFM was already confirmed ready and Steven asked for `screen2`/`screen3` (StarlinkAI's local names) in chat now. The "prototype on the Jetson first" section further down is superseded for this build; kept for reference only.

**Decisions locked in (confirmed with Steven):**
- Separate sibling script (`mpv_stream_launcher.py`, port 5902), not folded into `windows_matrix_launcher.py` — different process-lifecycle models (persistent-IPC vs. kill-relaunch).
- Rollout pace: move fast, no long soak requirement — but still bring each screen up and test it **one at a time**, not both simultaneously, until each is independently confirmed working. (The known `DPC_WATCHDOG_VIOLATION` crash was from 3 *matrix* screens at once, a different load profile than mpv's decode path — Steven's call was not to over-apply that caution here, just to keep proving screens independently before combining.)
- **Kick is in scope now**, not deferred. `!load kick:<slug> [screen]` reaches the launcher with the whole `kick:<slug>` token as one string (regex already generic, no `TwitchChatListenerProcessor` change needed beyond the screen-count text update below) — `mpv_stream_launcher.py`'s `build_url()` strips the `kick:` prefix and builds `kick.com/<slug>`, matching the same prefix convention already used for the watchlist/roster (`services/streamers.py`). Kick's `yt-dlp` extractor reliability is **unverified** — check this for real as part of first testing, don't assume parity with Twitch.

**Already built and live (2026-07-25, this session, from the WindowsDesktop-side Claude session — not StarlinkAI):**
- `StarlinkAI` EFM flow: `ListenHTTP-StreamScreen3` (port `8085`) → `InvokeHTTP-StreamScreen3` (`POST 127.0.0.1:5902/load/screen2`), and the `screen4`/`8086`/`screen3` pair. Built via the EFM Designer API (`minifi-efm.md` §7), published — flow version 13 → 14, confirmed cross-Tailscale reachable (`curl` from WindowsDesktop to `100.110.253.66:8085` and `:8086` both returned `200`).
- Central NiFi `TwitchChatBot` PG: `RouteOnAttribute` gained `screen3`/`screen4` dynamic properties; new `InvokeStarlinkScreen3`/`InvokeStarlinkScreen4` `InvokeHTTP` processors point at `http://100.110.253.66:8085` / `:8086` (TunaStarlink's real Tailscale IP — pulled live via `powershell.exe -Command "tailscale status"` interop from WSL2, since the checked-in docs deliberately store this as redacted placeholder text). Both new processors auto-terminate `Response`/`No Retry`/`Retry`/`Failure` and route `Original` → `TwitchChatReplyProcessor`, matching the existing `InvokeNvidiaNano`/`InvokeGamingPC` pattern exactly (confirmed against live flow state, not the stale checked-in export — `LogInvokeFailure` is wired from `TwitchChatReplyProcessor`'s `failure` only, not per-`InvokeHTTP`, contrary to an earlier draft of this plan). All processors `RUNNING`/`VALID`.
- `TwitchChatListenerProcessor.py`: chat-text updated to advertise `[screen1|screen2|screen3|screen4]` in both the join announcement and `!commands`/`!help`. Version bumped `0.0.13-SNAPSHOT` → `0.0.14-SNAPSHOT`, `kubectl cp`'d onto `mynifi-0`, running instance switched to the new bundle version and restarted. Live.
- `files/mpv_stream_launcher.py` (this repo) — **deployed and running on StarlinkAI as of 2026-07-24** (see the status section at the top for what changed getting it there). Port 5902, endpoints `POST /load/<screen>`, `POST /stop/<screen>`, `POST /kill/<screen>` (screen = `screen2`/`screen3`, StarlinkAI-local names). Lazy-starts `mpv --idle --force-window=immediate --input-ipc-server=...` on first `/load` for that screen (no `--screen`/`--fullscreen` flags at launch — positioned via `SetWindowPos` and fullscreened via IPC only after placement settles, see above), then only sends IPC `loadfile`/`stop` commands after. Calls `windows_matrix_launcher.py`'s `:5901/kill/<screen>` best-effort before loading a stream.
- Flow definitions re-exported and pretty-printed (not yet committed): `cso-operator-app/flows/TwitchChatBot.json`, `DesktopShare/files/StarlinkAI.json`.

**Still needed — StarlinkAI-side, hands-on (a separate Claude session running on StarlinkAI, per Steven's call on 2026-07-25):**
1. ~~Install `mpv`...~~ **Done 2026-07-24.** Installed via `winget install shinchiro.mpv` and `winget install yt-dlp.yt-dlp` (the latter pulled in `deno`/`FFmpeg` deps automatically). Real path: `C:\Program Files\MPV Player\mpv.exe` — added to `MPV_PATHS` in the checked-in script.
2. ~~Step 0...~~ **Done 2026-07-24.** `yt-dlp -g` resolved both `https://www.twitch.tv/xqc` and `https://kick.com/xqc` to real playable stream URLs. Kick's extractor is reliable, not unverified.
3. ~~Confirm `mpv`'s `--screen=N` indices...~~ **Superseded 2026-07-24.** `--screen=N` turned out to be unstable across reboots (see the "Three real bugs" section above) — abandoned entirely in favor of direct `SetWindowPos`, which doesn't depend on any enumeration index at all.
4. ~~Copy `mpv_stream_launcher.py`...~~ **Done 2026-07-24.** Deployed to `C:\minifi-manual\mpv_stream_launcher.py`, registered as `MpvStreamLauncherListener` (`AtLogOn`, `tunas`, `RestartCount=3`/`RestartInterval=1min`, unlimited execution time) — using `pythonw.exe`, not `python.exe`, from the start (see `claude-screen.md` "Known failure mode #3" for why that matters on this box).
5. ~~One additive edit to `windows_matrix_launcher.py`...~~ **Done 2026-07-24.** `_launch_screen()` now calls `POST http://127.0.0.1:5902/stop/<screen>` best-effort before its existing Edge-launch logic. Nothing else in that file was touched.
6. ~~Test one screen at a time...~~ **Done 2026-07-24.** Both screens individually confirmed via direct HTTP calls (Twitch only — Kick was verified at the `yt-dlp` level in step 2 but not re-tested through the full `/load` endpoint; worth a quick real check before calling Kick fully proven end-to-end). The matrix↔stream handoff was tested and fixed in **both** directions — see the "fourth, smaller bug" note above (mpv's own `window-minimized` IPC property doesn't work; fixed via `ShowWindow`).
7. **Still open.** Once the array is live: real `!load <streamer> screen3` / `!load <streamer> screen4` and `!load kick:<slug> screen3` from actual Twitch chat — this is the one thing tonight's session couldn't do (not live).
8. **Still open**, blocked on 7. Commit the re-exported `TwitchChatBot.json`/`StarlinkAI.json` once the real-chat test in item 7 passes.

---

**Original planning note (superseded rollout order above, kept for the mpv/IPC mechanics reference):**

## Why

`!load <streamer> [screen1|screen2]` works end-to-end today on both the Jetson (`NvidiaNano`) and WindowsDesktop (`KubernetesPod`, via the `browser_launcher.py` Windows bridge), but every single command does a full kill-and-relaunch of Chrome/Chromium:

1. `taskkill`/`pkill` the existing browser
2. Launch a new one, positioned and sized for the target monitor
3. Force it fullscreen (`wmctrl` on Linux, `MoveWindow`+F11 or `--kiosk` on Windows)

That's visibly slow (a few seconds of black screen / flashing terminal each time) and it's also where almost every bug this week came from: kiosk fullscreen following the cursor's monitor instead of the configured one, `MoveWindow` not matching where pixels actually render, Chrome's single-instance flag-ignoring behavior, "did a window actually appear" false negatives on process exit codes. All of that is downstream of relaunching a full browser process per command.

## The idea

Run `mpv` (with the `yt-dlp` extractor for resolving Twitch URLs to a real stream) as a **persistent process per screen**, left running indefinitely instead of killed and relaunched. `mpv` exposes a JSON IPC socket for control — a Unix domain socket on Linux, a named pipe on Windows, same message format both places. A `!load` command becomes a single `loadfile <url> replace` command sent over that socket to the already-running player, not a process kill/relaunch:

```json
{"command": ["loadfile", "https://www.twitch.tv/<streamer>", "replace"]}
```

No window ever closes. No kiosk/fullscreen negotiation happens more than once (at initial player startup, on a screen that never changes). No "is chrome.exe actually a real window yet" polling.

## What each piece looks like

**Per-screen persistent `mpv` instance** (one per physical monitor, started once — at boot/login, not per-command):
```
mpv --idle --input-ipc-server=<socket-or-pipe> --fullscreen --screen=<N> --ytdl-format=best
```
- Linux (Jetson): `--input-ipc-server=/tmp/mpv-screen1.sock`
- Windows (WindowsDesktop): `--input-ipc-server=\\.\pipe\mpv-screen2`

**Control script** (replaces `agent-NvidiaNano-launch_stream.py` / `gaming-pc-launch_stream.py` + `browser_launcher.py`'s launch logic): reads `{"streamer": "..."}` from the flowfile/POST body same as today, builds the Twitch URL, and instead of spawning a browser, opens the IPC socket/pipe and sends the `loadfile` JSON command. Same `onTrigger`/success/failure contract as the existing scripts — failure now means "couldn't write to the IPC socket" or "mpv returned an error event," not "process exit code lied to us."

**WindowsDesktop bridge stays the same shape.** `KubernetesPod` still has no GUI access from inside the container, so the pod's `ExecuteScript` still needs to call out to something running natively on Windows — that part of the architecture (`browser_launcher.py`'s role) doesn't go away, it just controls `mpv` over the named pipe instead of launching/repositioning Chrome. Everything upstream of it (NiFi routing, `RouteOnAttribute` on `${screen}`) is untouched.

**Windows-native option, worth testing alongside this (separate, already-corrected finding):** a real `WindowsDesktop` MiNiFi agent does reach EFM fine — the earlier "Windows can't reach EFM" note was wrong and has been corrected in memory. The actual Windows limitation is that *custom compiled* NiFi/MiNiFi processors don't have Windows binaries; the built-in `ExecuteScript` processor works fine there. That reopens running the WindowsDesktop screen2 flow as a native `WindowsDesktop` agent (talking to a local `mpv` pipe directly) instead of the pod+bridge-listener shape — worth trying once `WindowsDesktop` class testing happens, independent of the mpv work itself.

## Rollout order

1. **Prototype on the Jetson only.** Simplest target — already Linux/native, no bridge process involved, no Windows named-pipe unknowns. Install `mpv`+`yt-dlp`, hand-test IPC control from a shell (`socat - /tmp/mpv-screen1.sock` or similar) before touching the MiNiFi flow.
2. Swap `agent-NvidiaNano-launch_stream.py`'s Chromium kill/relaunch for the IPC `loadfile` call. Confirm `!load <streamer>` (no screen arg, defaults to screen1) still works via real chat, with no regression.
3. Only once that's solid, do the same for WindowsDesktop: persistent `mpv` on Windows, `browser_launcher.py` rewritten to speak the named-pipe IPC instead of launching Chrome. Re-verify screen2 positioning is a non-issue here (the player never moves, it's launched once already fullscreen on the correct monitor — no more `AllScreens`/`GetWindowRect` juggling per command).
4. Re-test both screens together, same as always: `!load <streamer>`, `!load <streamer> screen1`, `!load <streamer> screen2`, no cross-regression.

## Real tradeoffs, going in with eyes open

- **New dependency on every device** — `mpv` isn't installed anywhere in this fleet yet. Small install, but it's one more thing to keep patched/present after a rebuild or reimage.
- **`yt-dlp` is the actual Twitch-resolution layer**, not `mpv` itself — if Twitch changes its site/player in a way that breaks `yt-dlp`'s extractor, streams stop resolving until `yt-dlp` ships an update. This is an external dependency risk that the current Chrome/Chromium approach doesn't have (a real browser just renders whatever Twitch serves, no separate extraction step).
- **Persistent process means persistent failure mode**: if `mpv` itself crashes or its IPC socket goes stale, there's no per-command relaunch to paper over it — need the same kind of health-check/self-heal thinking already added for `browser_launcher.py` (logging, and something bringing it back if it dies), just applied to `mpv` instead.
- **Ad-supported/logged-out Twitch playback** — worth checking whether `yt-dlp`'s Twitch extractor supports passing session cookies/auth the same way a real logged-in browser does, especially since the current screen2 profile-login question (separate item, see main doc) is exactly about avoiding the logged-out ad experience. If `yt-dlp` can't carry a logged-in session, this migration could make the ad situation *worse*, not better — needs to be checked as step 0 of the prototype, before committing to the direction.

## Not doing

- Chrome DevTools Protocol (`Page.navigate` on a persistent browser) — considered earlier as a flash-free alternative, superseded by the mpv direction since it avoids browser-specific issues (kiosk quirks, single-instance flag-eating, "did a window really appear") entirely rather than working around them inside a browser. Kept as a fallback only if `mpv`/`yt-dlp` turns out not to fit some device.
