# Twitch chat stream loader — mpv/yt-dlp migration plan

**Status: planning only, nothing built yet.** This replaces the current kill-Chrome/relaunch-Chrome cycle used by both screens with a persistent `mpv` player controlled over its IPC socket. Written up before starting so I have a clear reference when I do pick it up.

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
