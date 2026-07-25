# Twitch chat stream loader — mpv/yt-dlp migration plan

This replaces the current kill-Chrome/relaunch-Chrome cycle used by both screens with a persistent `mpv` player controlled over its IPC socket. Written up before starting so there's a clear reference when it gets picked up.

## Status as of 2026-07-25: live-cluster side built and published; Beelink-side pending

Real scope decision (2026-07-24/25): build `screen3`/`screen4` (array-facing) stream loading on TunaStarlink/Beelink directly via `mpv`+IPC now — **not** the Jetson-first rollout order this doc originally proposed below. Went straight to the Beelink because StarlinkAI/EFM was already confirmed ready and Steven asked for `screen2`/`screen3` (Beelink's local names) in chat now. The "prototype on the Jetson first" section further down is superseded for this build; kept for reference only.

**Decisions locked in (confirmed with Steven):**
- Separate sibling script (`mpv_stream_launcher.py`, port 5902), not folded into `windows_matrix_launcher.py` — different process-lifecycle models (persistent-IPC vs. kill-relaunch).
- Rollout pace: move fast, no long soak requirement — but still bring each screen up and test it **one at a time**, not both simultaneously, until each is independently confirmed working. (The known `DPC_WATCHDOG_VIOLATION` crash was from 3 *matrix* screens at once, a different load profile than mpv's decode path — Steven's call was not to over-apply that caution here, just to keep proving screens independently before combining.)
- **Kick is in scope now**, not deferred. `!load kick:<slug> [screen]` reaches the launcher with the whole `kick:<slug>` token as one string (regex already generic, no `TwitchChatListenerProcessor` change needed beyond the screen-count text update below) — `mpv_stream_launcher.py`'s `build_url()` strips the `kick:` prefix and builds `kick.com/<slug>`, matching the same prefix convention already used for the watchlist/roster (`services/streamers.py`). Kick's `yt-dlp` extractor reliability is **unverified** — check this for real as part of first testing, don't assume parity with Twitch.

**Already built and live (2026-07-25, this session, from the gaming-PC-side Claude session — not the Beelink):**
- `StarlinkAI` EFM flow: `ListenHTTP-StreamScreen3` (port `8085`) → `InvokeHTTP-StreamScreen3` (`POST 127.0.0.1:5902/load/screen2`), and the `screen4`/`8086`/`screen3` pair. Built via the EFM Designer API (`minifi-efm.md` §7), published — flow version 13 → 14, confirmed cross-Tailscale reachable (`curl` from the gaming PC to `100.110.253.66:8085` and `:8086` both returned `200`).
- Central NiFi `TwitchChatBot` PG: `RouteOnAttribute` gained `screen3`/`screen4` dynamic properties; new `InvokeStarlinkScreen3`/`InvokeStarlinkScreen4` `InvokeHTTP` processors point at `http://100.110.253.66:8085` / `:8086` (TunaStarlink's real Tailscale IP — pulled live via `powershell.exe -Command "tailscale status"` interop from WSL2, since the checked-in docs deliberately store this as redacted placeholder text). Both new processors auto-terminate `Response`/`No Retry`/`Retry`/`Failure` and route `Original` → `TwitchChatReplyProcessor`, matching the existing `InvokeNvidiaNano`/`InvokeGamingPC` pattern exactly (confirmed against live flow state, not the stale checked-in export — `LogInvokeFailure` is wired from `TwitchChatReplyProcessor`'s `failure` only, not per-`InvokeHTTP`, contrary to an earlier draft of this plan). All processors `RUNNING`/`VALID`.
- `TwitchChatListenerProcessor.py`: chat-text updated to advertise `[screen1|screen2|screen3|screen4]` in both the join announcement and `!commands`/`!help`. Version bumped `0.0.13-SNAPSHOT` → `0.0.14-SNAPSHOT`, `kubectl cp`'d onto `mynifi-0`, running instance switched to the new bundle version and restarted. Live.
- `files/mpv_stream_launcher.py` (this repo) — the actual script to drop onto the Beelink, written but **not yet deployed there**. Port 5902, endpoints `POST /load/<screen>`, `POST /stop/<screen>`, `POST /kill/<screen>` (screen = `screen2`/`screen3`, Beelink-local names). Lazy-starts `mpv --idle --input-ipc-server=... --fullscreen --screen=<N> --ytdl-format=best` on first `/load` for that screen, then only sends IPC `loadfile`/`stop` commands after. Calls `windows_matrix_launcher.py`'s `:5901/kill/<screen>` best-effort before loading a stream.
- Flow definitions re-exported and pretty-printed (not yet committed): `cso-operator-app/flows/TwitchChatBot.json`, `DesktopShare/files/StarlinkAI.json`.

**Still needed — Beelink-side, hands-on (a separate Claude session running on TunaStarlink, per Steven's call on 2026-07-25):**
1. Install `mpv` (`winget install mpv` or the mpv.io Windows build — must land at one of `mpv_stream_launcher.py`'s `MPV_PATHS`, or add the real path there) and `yt-dlp` (on `PATH`, or point `--script-opts=ytdl_hook-ytdl_path=<path>` — not currently set in the script).
2. **Step 0 before anything else**: confirm `yt-dlp` can actually pull Twitch *and* Kick streams from this box — hand-test both, don't assume.
3. Confirm `mpv`'s `--screen=0`/`--screen=1` indices actually land on DISPLAY2/DISPLAY3 (`screen2`/`screen3` in `mpv_stream_launcher.py`'s `SCREENS` dict) — **unverified**, flagged in the script's own comment. Swap the `screen_index` values if wrong.
4. Copy `mpv_stream_launcher.py` to `C:\minifi-manual\mpv_stream_launcher.py`, register it as Scheduled Task `MpvStreamLauncherListener` (`AtLogOn`, `TunaStarlink\tunas`, `RestartCount=3`/`RestartInterval=1min`, unlimited execution time — same shape as `MatrixLauncherListener`/`MatrixIdleWatcher`).
5. One additive edit to the live `windows_matrix_launcher.py`: at the top of its `/matrix/<screen>` handler (and the `/matrix` alias), add a best-effort `POST http://127.0.0.1:5902/stop/<screen>` before the existing Edge-launch logic — mirrors `mpv_stream_launcher.py`'s own best-effort call into `:5901/kill/<screen>`. Don't touch anything else in that file (it's live and working).
6. Test one screen at a time first (`screen2` alone, then `screen3` alone) via direct `Invoke-WebRequest`/`curl` against `:5902/load/<screen>`, both Twitch and `kick:`-prefixed streamers, before testing both together. Then test the matrix↔stream handoff both directions on one screen (does killing Edge naturally re-expose a fullscreen mpv window underneath, or does something else grab focus — genuinely unverified, a `SetForegroundWindow`/topmost fallback may be needed if not).
7. Once both screens are individually solid: real `!load <streamer> screen3` / `!load <streamer> screen4` and `!load kick:<slug> screen3` from actual Twitch chat.
8. Commit the re-exported `TwitchChatBot.json`/`StarlinkAI.json` (already refreshed, sitting uncommitted) once the Beelink side is confirmed working, so the checked-in exports don't go stale before anyone notices.

---

**Original planning note (superseded rollout order above, kept for the mpv/IPC mechanics reference):**

## Why

`!load <streamer> [screen1|screen2]` works end-to-end today on both the Jetson (`NvidiaNano`) and the gaming PC (`KubernetesPod`, via the `browser_launcher.py` Windows bridge), but every single command does a full kill-and-relaunch of Chrome/Chromium:

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
- Windows (gaming PC): `--input-ipc-server=\\.\pipe\mpv-screen2`

**Control script** (replaces `agent-NvidiaNano-launch_stream.py` / `gaming-pc-launch_stream.py` + `browser_launcher.py`'s launch logic): reads `{"streamer": "..."}` from the flowfile/POST body same as today, builds the Twitch URL, and instead of spawning a browser, opens the IPC socket/pipe and sends the `loadfile` JSON command. Same `onTrigger`/success/failure contract as the existing scripts — failure now means "couldn't write to the IPC socket" or "mpv returned an error event," not "process exit code lied to us."

**Gaming PC bridge stays the same shape.** `KubernetesPod` still has no GUI access from inside the container, so the pod's `ExecuteScript` still needs to call out to something running natively on Windows — that part of the architecture (`browser_launcher.py`'s role) doesn't go away, it just controls `mpv` over the named pipe instead of launching/repositioning Chrome. Everything upstream of it (NiFi routing, `RouteOnAttribute` on `${screen}`) is untouched.

**Windows-native option, worth testing alongside this (separate, already-corrected finding):** a real `WindowsDesktop` MiNiFi agent does reach EFM fine — the earlier "Windows can't reach EFM" note was wrong and has been corrected in memory. The actual Windows limitation is that *custom compiled* NiFi/MiNiFi processors don't have Windows binaries; the built-in `ExecuteScript` processor works fine there. That reopens running the gaming-PC screen2 flow as a native `WindowsDesktop` agent (talking to a local `mpv` pipe directly) instead of the pod+bridge-listener shape — worth trying once `WindowsDesktop` class testing happens, independent of the mpv work itself.

## Rollout order

1. **Prototype on the Jetson only.** Simplest target — already Linux/native, no bridge process involved, no Windows named-pipe unknowns. Install `mpv`+`yt-dlp`, hand-test IPC control from a shell (`socat - /tmp/mpv-screen1.sock` or similar) before touching the MiNiFi flow.
2. Swap `agent-NvidiaNano-launch_stream.py`'s Chromium kill/relaunch for the IPC `loadfile` call. Confirm `!load <streamer>` (no screen arg, defaults to screen1) still works via real chat, with no regression.
3. Only once that's solid, do the same for the gaming PC: persistent `mpv` on Windows, `browser_launcher.py` rewritten to speak the named-pipe IPC instead of launching Chrome. Re-verify screen2 positioning is a non-issue here (the player never moves, it's launched once already fullscreen on the correct monitor — no more `AllScreens`/`GetWindowRect` juggling per command).
4. Re-test both screens together, same as always: `!load <streamer>`, `!load <streamer> screen1`, `!load <streamer> screen2`, no cross-regression.

## Real tradeoffs, going in with eyes open

- **New dependency on every device** — `mpv` isn't installed anywhere in this fleet yet. Small install, but it's one more thing to keep patched/present after a rebuild or reimage.
- **`yt-dlp` is the actual Twitch-resolution layer**, not `mpv` itself — if Twitch changes its site/player in a way that breaks `yt-dlp`'s extractor, streams stop resolving until `yt-dlp` ships an update. This is an external dependency risk that the current Chrome/Chromium approach doesn't have (a real browser just renders whatever Twitch serves, no separate extraction step).
- **Persistent process means persistent failure mode**: if `mpv` itself crashes or its IPC socket goes stale, there's no per-command relaunch to paper over it — need the same kind of health-check/self-heal thinking already added for `browser_launcher.py` (logging, and something bringing it back if it dies), just applied to `mpv` instead.
- **Ad-supported/logged-out Twitch playback** — worth checking whether `yt-dlp`'s Twitch extractor supports passing session cookies/auth the same way a real logged-in browser does, especially since the current screen2 profile-login question (separate item, see main doc) is exactly about avoiding the logged-out ad experience. If `yt-dlp` can't carry a logged-in session, this migration could make the ad situation *worse*, not better — needs to be checked as step 0 of the prototype, before committing to the direction.

## Not doing

- Chrome DevTools Protocol (`Page.navigate` on a persistent browser) — considered earlier as a flash-free alternative, superseded by the mpv direction since it avoids browser-specific issues (kiosk quirks, single-instance flag-eating, "did a window really appear") entirely rather than working around them inside a browser. Kept as a fallback only if `mpv`/`yt-dlp` turns out not to fit some device.
