# streamChat — launching a Twitch stream on the Jetson's display over HTTP

**Status: WORKING, confirmed end to end.** The `streamChat` feature lets a NiFi/EFM flow open a
Twitch stream fullscreen on the Jetson's *physical* display with a single HTTP POST. It took four
stacked bugs to get there; each is a lesson worth keeping. The reader-facing version of this is in
`hacking-the-jetson-blog.md`; this is the debug record and the operational reference.

## What it is

`POST :8081/streamChatListener` with `{"streamer": "<name>"}` runs `launch_stream.py` via a MiNiFi
`ListenHTTP` → `ExecuteScript` pair, opening Chromium to `https://www.twitch.tv/<name>` fullscreen
on the Jetson (agent runs as `tunastreet`, see the ownership fix below). The agent runbook is
`nvidianano-minifi-ops.md`.

First test returned an HTTP 200 but Chromium never opened — three bugs stacked under that, plus a
fourth on fullscreen once it did open.

## Bug 1 — `ListenHTTP` dropped the request before Python ever saw it

`ListenHTTP-streamChat` (port 8081) was copy-configured from the tensorRT listener with
`Batch Size: 5` / `Buffer Size: 5`. MiNiFi won't turn a request into a FlowFile until the buffer
fills, so a single test POST just sat there and got dropped:

```
[warning] ListenHTTP buffer is NOT full 1/5, 'POST' request for
'/streamChatListener' uri was dropped
```

The tensorRT endpoint "worked" only because it gets hammered with back-to-back curls that fill the
buffer; streamChat only ever gets one request per test.

**Fix (via EFM):** `Batch Size: 1` / `Buffer Size: 1` on `ListenHTTP-streamChat`. Confirmed in
`config.yml` after the push.

## Bug 2 — `XAUTHORITY` was a literal unfilled placeholder

The original script shipped with an angle-brackets-and-all placeholder that never existed:

```python
env["XAUTHORITY"] = "/home/<jetson-desktop-user>/.Xauthority"  # fill in real desktop user
```

Real values, pulled from the live GNOME session's own process environment:

```python
env["DISPLAY"] = ":0"
env["XAUTHORITY"] = "/run/user/1000/gdm/Xauthority"
```

**Fix (via EFM, in `agent-NvidiaNano-launch_stream.py`):** hardcoded to the real path above.

## Bug 3 — the agent ran as root, the desktop is uid 1000

`ps` showed `minifi` running as `root` (no `User=` in the systemd unit), while the GNOME/X11
session belongs to `tunastreet` (uid 1000). Root's environment has no
`XDG_RUNTIME_DIR`/D-Bus session address, which snap-confined Chromium needs.

**Fix (OS-level, not flow config):** add `User=tunastreet` to
`/usr/local/lib/systemd/system/minifi.service`. That immediately caused a follow-on crash-loop:

```
terminate called after throwing an instance of 'spdlog::spdlog_ex'
what(): Failed opening file .../logs/minifi-app.log for writing: Permission denied
```

`minifi-app.log`, the RocksDB state dirs (`content_repository`, `flowfile_repository`,
`corecomponentstate`), and a couple of `conf/minifi.properties.d/*` files had been created
`root:root` while the agent ran as root. **Fix:**
`sudo chown -R tunastreet:tunastreet /home/tunastreet/nifi-minifi-cpp-1.26.02`, then restart. (This
`User=`/ownership pairing is now baked into the reinstall runbook in `nvidianano-minifi-ops.md`.)

## Bug 4 — Chromium opened but wouldn't go fullscreen

Chromium came up at `912x991` at `88,122` on a 1920x1080 screen despite
`--new-window --kiosk --start-fullscreen --window-position=0,0`. Same failure mode as the matrix
screensaver (`claude-screen.md`, Jetson "Known failure modes" #3): Chromium's own fullscreen flags
don't reliably get Mutter to grant real X11 fullscreen state.

**Fix (applied via EFM in `agent-NvidiaNano-launch_stream.py`, confirmed working):** after
launching Chromium, background a **detached** `bash -c` that:

1. Polls `wmctrl -l` (up to 240 × 0.25s = 1 min — under load the window can take several seconds to
   appear; a short timeout risks never firing the fix) for a title ending in
   `" - Twitch - Chromium"`. Matching the suffix works for any streamer, not a hardcoded name.
2. Forces `wmctrl -r "<title>" -b add,fullscreen`.
3. Waits 2.5s for Twitch's SPA to render the player, then uses `xdotool` to click the video center
   and send the `f` hotkey — triggering Twitch's *own* player fullscreen (hides sidebar/chat/nav),
   same approach as the Windows side's `reposition_chrome.ps1`.

The poll-and-fullscreen step **must** be backgrounded, not inline in `onTrigger`: MiNiFi's
`ExecuteScript` runs on a single shared thread (`max concurrent threads: 1`), so a blocking wait of
up to a minute would stall the whole flow — heartbeats, Kafka, the other listener.

**Prerequisite that was missing:** `xdotool` wasn't installed on this device (only `wmctrl` was) —
`sudo apt-get install -y xdotool` (v3.20160805.1).

## Gotcha — `wmctrl` fullscreen ignores Esc/F11

Forcing fullscreen via `wmctrl` bypasses Chromium's own fullscreen-toggle state, so Esc/F11 won't
undo it. I got a test window stuck fullscreen with no visible way out. The escape hatch is the same
mechanism in reverse:

```bash
wmctrl -r "xQc - Twitch - Chromium" -b remove,fullscreen
```

## Verification

- `ps` confirms `minifi` running as `tunastreet`.
- `curl -X POST http://localhost:8081/streamChatListener -d '{"streamer":"xqc"}'` → HTTP 200.
- `ps -ef | grep chromium` showed a live snap Chromium (`--ozone-platform=x11`) with
  `--new-window https://www.twitch.tv/xqc`, launched as `tunastreet`, and confirmed fullscreen end
  to end (window-manager fullscreen + Twitch player fullscreen) with no manual steps.

## Note on success reporting (low priority, not applied)

`launch_stream.py` does a 1.5s sleep + `proc.poll()` + stderr capture before declaring
`python.load.status = Success`, so the original "unconditional success" concern is mostly handled.
Worth keeping in mind only if Chromium ever fails in a way that takes longer than ~1.5s to surface
(e.g. a network error after the window opens).
