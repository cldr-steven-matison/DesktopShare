# streamChat launch feature — debug + fix log (2026-07-18)

## Status: WORKING, confirmed end to end

New EFM flow: `POST :8081/streamChatListener` with `{"streamer": "<name>"}`
runs `launch_stream.py` via ExecuteScript, which opens Chromium to
`https://www.twitch.tv/<name>` on the Jetson's display. First test got an
HTTP response but Chromium never opened — three separate bugs stacked on
top of each other. All three found and fixed; final curl test launched a
real Chromium window (confirmed via `ps -ef`).

## Bug 1: ListenHTTP buffer/batch size dropped the request before it ever
reached Python (root cause of the original "worked but nothing happened")

`ListenHTTP-streamChat` (port 8081) was copy-configured from the tensorRT
listener with `Batch Size: 5` / `Buffer Size: 5`. MiNiFi won't turn a
request into a flowfile until the buffer fills, so a single test POST just
sat there and got dropped:

```
[warning] ListenHTTP buffer is NOT full 1/5, 'POST' request for
'/streamChatListener' uri was dropped
```

The tensorRT endpoint "worked" because it gets hammered with repeated
back-to-back curls that fill the buffer; streamChat only ever got one
request per test.

**Fix (applied via EFM):** `Batch Size: 1` / `Buffer Size: 1` on
`ListenHTTP-streamChat`. Confirmed in `config.yml` after the EFM push.

## Bug 2: XAUTHORITY was a literal unfilled placeholder

Original `launch_stream.py`:

```python
env["XAUTHORITY"] = "/home/<jetson-desktop-user>/.Xauthority"  # fill in real desktop user
```

That path never existed (angle brackets and all), and
`/home/tunastreet/.Xauthority` doesn't exist either. Real value, pulled
from the live GNOME session's actual process environment:

```python
env["DISPLAY"] = ":0"
env["XAUTHORITY"] = "/run/user/1000/gdm/Xauthority"
```

**Fix (applied via EFM, in the new `agent-NvidiaNano-launch_stream.py`
asset):** hardcoded to the real path above.

## Bug 3: minifi.service ran as root, desktop session is uid 1000

`ps` showed `minifi` running as `root` (no `User=` in the systemd unit),
while the GNOME/X11 session belongs to `tunastreet` (uid 1000). Root's env
had no `XDG_RUNTIME_DIR`/D-Bus session address, which snap-confined
Chromium needs, so launching as root against another user's session was
never going to work reliably.

**Fix (applied locally, not via EFM — this is a systemd/OS-level change,
outside flow config):**

```ini
[Service]
User=tunastreet
```

added to `/usr/local/lib/systemd/system/minifi.service`.

**Follow-on issue this caused:** after switching to `User=tunastreet`,
the service crash-looped on startup:

```
terminate called after throwing an instance of 'spdlog::spdlog_ex'
what(): Failed opening file .../logs/minifi-app.log for writing: Permission denied
```

`minifi-app.log`/`minifi-app.1.log` and the RocksDB state dirs
(`content_repository`, `flowfile_repository`, `corecomponentstate`) plus a
couple of `conf/minifi.properties.d/*` files were all created while minifi
ran as root, so they were `root:root`-owned and unwritable by `tunastreet`.

**Fix:** `sudo chown -R tunastreet:tunastreet /home/tunastreet/nifi-minifi-cpp-1.26.02`,
then restart. Service came up clean, no errors, both ListenHTTP endpoints
started.

## Verification

- `ps` confirms `minifi` running as `tunastreet` (PID 284109).
- `curl -X POST http://localhost:8081/streamChatListener -d '{"streamer":"xqc"}'`
  returned normally.
- `ps -ef | grep chromium` showed a live Chromium process (snap binary,
  `--ozone-platform=x11`) with `--new-window https://www.twitch.tv/xqc`,
  launched as `tunastreet`.

## Remaining idea, not applied (low priority)

`launch_stream.py` reports `python.load.status = Success` right after
`Popen()` — the current version *does* do a 1.5s sleep + `proc.poll()` +
stderr capture before declaring success (this was added between the first
and second script revisions pulled from EFM), so the original "unconditional
success" concern is already mostly addressed. Worth keeping in mind if
Chromium ever fails in a way that takes longer than ~1.5s to surface (e.g.
network-dependent errors after the window opens).

## Helper scripts

`fix-minifi-user.sh` (added `User=tunastreet` to the systemd unit) and
`fix-minifi-perms.sh` (chowned the install dir back to `tunastreet` and
restarted) were used one-off to apply Bug 3's fix and have been deleted.

## Bug 4: Chromium launches but doesn't go fullscreen (2026-07-18, later)

Chromium was already opening correctly (Python-side fixes from Bugs 1-3
adjusted further via EFM) but the window came up small instead of
filling the screen. Live-tested and reproduced — this is the exact same
failure mode already documented for the matrix-rain screensaver in
`NvidiaNano-claude-screen.md` ("Known failure modes #3"): Chromium's own
`--kiosk`/`--start-fullscreen`/`--window-position=0,0` flags don't
reliably get Mutter to grant real X11 fullscreen state.

Confirmed live: window `xQc - Twitch - Chromium` came up at `912x991`
positioned at `88,122` (screen is `1920x1080`) despite the script passing
`--new-window --kiosk --start-fullscreen --window-position=0,0`.

**Fix, tested live and confirmed working:**

```bash
wmctrl -r "xQc - Twitch - Chromium" -b add,fullscreen
```

— immediately resized/repositioned the real window to `1920x1080` at
`0,0`. Same mechanism the screensaver's `force_fullscreen()` in
`~/.local/bin/lofi-idle-watcher.sh` already uses; the required addition
to `launch_stream.py` is the same shape:

1. After launching Chromium, poll `wmctrl -l` for a window title
   matching the stream (screensaver polls for up to 240 × 0.25s = 1 min,
   since under system load the window can take several seconds to
   appear — a short timeout risks never firing the fix).
2. Match on something stable regardless of streamer name — the title is
   always `"<Streamer> - Twitch - Chromium"`, so matching the
   `" - Twitch - Chromium"` suffix works for any streamer, not just a
   hardcoded name.
3. Run this poll-and-fullscreen step as a **backgrounded/detached
   subprocess**, not inline in `onTrigger` — MiNiFi's `ExecuteScript`
   runs on a single shared thread (`max concurrent threads: 1`), so a
   blocking wait of up to a minute here would stall the whole flow
   (heartbeats, Kafka, the other listener) exactly like the screensaver
   script backgrounds+disowns its own `force_fullscreen &`.

**Gotcha hit live while testing:** forcing fullscreen via `wmctrl`
bypasses Chromium's own fullscreen-toggle state, so normal escape keys
don't undo it — got the window stuck fullscreen mid-test with no
visible way out. Fixed the same way it was forced:

```bash
wmctrl -r "xQc - Twitch - Chromium" -b remove,fullscreen
```

Worth remembering for any future live test on this feature: if a test
window gets stuck fullscreen, `wmctrl -r "<title>" -b remove,fullscreen`
is the escape hatch, not F11/Esc.

**Update (2026-07-19): applied and confirmed working end to end.**

New `agent-NvidiaNano-launch_stream.py` arrived via EFM push with the
poll-loop + backgrounded `wmctrl`/`xdotool` fix built in: after launching
Chromium it backgrounds a detached `bash -c` that polls `wmctrl -l` (up
to 240 × 0.25s) for a window title ending in `" - Twitch - Chromium"`,
forces `wmctrl -b add,fullscreen` on it, waits 2.5s for Twitch's SPA to
finish rendering the player, then uses `xdotool` to click the video
center and send the `f` hotkey — triggering Twitch's own player
fullscreen (hides sidebar/chat/nav), the same approach as the Windows
side's `reposition_chrome.ps1`.

**Prerequisite found missing on this device:** `xdotool` was not
installed (only `wmctrl` was). Installed via
`sudo apt-get install -y xdotool` (v3.20160805.1).

**Verified live:** `curl -X POST :8081/streamChatListener -d
'{"streamer":"xqc"}'` → HTTP 200 → Chromium window opened and was
confirmed fullscreen end to end (window-manager fullscreen + Twitch
player fullscreen both applied). No manual `wmctrl`/`xdotool` steps
needed — the script's own backgrounded poll handled it.
