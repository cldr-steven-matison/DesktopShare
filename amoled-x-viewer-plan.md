# AMOLED X viewer — swipe + like my X posts on the panel

**Plan for [issue #183](https://github.com/cldr-steven-matison/DesktopShare/issues/183).**
Claude's app for the Waveshare ESP32-S3-Touch-AMOLED-1.8 **V2**: swipe through my X posts like a tiny
feed, tap to heart one. Sibling app on the same board and the same launcher: **Ember** (Grok,
StarlinkAI) — issue #184, [`amoled-ember-plan.md`](amoled-ember-plan.md).

## Scope — an app, not agent work

This work stream is **an in-device app and the backend leg that feeds it.** MicroFi, EFM, agent class
`AMOLED`, C2 heartbeats and flow definitions are the platform work stream (#181 design, #185/#188
build, golden source [`efm-waveshare-amoled.md`](efm-waveshare-amoled.md)). Nothing in this issue
modifies the agent.

## Architecture — a runtime app package, third revision (2026-08-19)

**The board now runs the Brookesia v0.8 platform image built under #188** — launcher, JS runtime, and
the MicroFi EFM agent baked in natively, on IDF 6.0.2. That platform changes this app's shape a third
time, and this one is structural, not cosmetic:

- **Apps deploy at runtime, not compile time.** A package — `manifest.json` + `app/app.js` +
  `res/` JSON-UI — dropped into `apps/` on the board's filesystem is scanned at `System::init()` and
  gets a launcher tile. No per-app reflash, no combined-image assembly, no component drop-in.
- **Runtime apps are sandboxed JavaScript + JSON-UI**, not C++/LVGL. The JS talks to the system only
  through the `brookesia` bridge (`call_service_function` and friends) — there is no `fetch`, no
  `setTimeout`; HTTP, timers, and UI mutation are all system services.
- Everything the previous revision assumed is dead API: `systems::phone::App`,
  `ESP_UTILS_REGISTER_PLUGIN_WITH_CONSTRUCTOR`, `firmware/components/x_viewer/`, and the
  "combine both components into one image" deployment phase. The never-compiled C++ skeleton in
  `~/amoled-x-viewer/firmware/` is retired outright.

What a runtime JS app verifiably **can** do (read out of the v0.8 sources, 2026-08-19):

| Need | Service | Notes |
|---|---|---|
| HTTP(S) to the backend | `Http` — `Request` / `RequestAsync` | already a dependency of the flashed super image; url/method/headers/body/timeout/retry, response body or file download |
| Image download to disk | `Http` `download_path` + `$brookesiaStoragePath` | per-app sandbox `apps/<id>/{cache,data,files}` |
| Show a card / update text | `SystemGui` — `SetText`, `SetViewSrc`, `CreateView`, `ExecuteBatch` | JSON-UI screens from `res/`; LVGL backend decodes baseline JPEG |
| Swipe / tap | JSON-UI events → `SubscribeAction` → `on_action` | `gesture` events carry `{"direction": "left"|"right"|...}` |
| Refresh / retry | `SystemTimer` — `StartPeriodic` / `StartDelayed` → `on_timer` | |

**The `SetViewSrc`-from-file question is answered on the glass (2026-08-19): YES.** A downloaded
JPEG's sandbox path (via the `$brookesiaStoragePath` marker) renders fine — real post images show on
the card. The fallback paths (placeholder ids / text-only cards) were never needed.

**Brookesia still owns the shell** — home grid, status bar, and the swipe-up-from-bottom home gesture.
The gesture table below is unchanged and still designed around it.

### Deployment — a package in `apps/`, no reflash

```
waveshare-devices/amoled-1.8-v2/apps/tunastreet.xviewer/   # this app (JS package)
waveshare-devices/amoled-1.8-v2/apps/tunastreet.hello/     # the template (#188) — repo only, removed from the device at Steven's call
```

Staging today bakes the package into the littlefs partition image
(`littlefs_create_partition_image` in the super example build) — one storage-partition flash per
staging round while the platform is iterating anyway. The v0.8 install path prefers an SD card
(`apps/` on the card is scanned too), which drops even that flash once a card is in the slot.
Ember (#184) deploys the same way as its own package — nothing to combine, no cross-repo read
access needed. The old "one image, two components" phase and its `steven-matison/ember` blocker are
gone with the compile-time model.

## The device

**SKU confirmed 2026-08-18** from the rear label (photo on #181):

| | |
|---|---|
| Board | **Waveshare ESP32-S3-Touch-AMOLED-1.8, V2** |
| Display | **CO5300**, 1.8″ AMOLED, **368 × 448** — QSPI |
| Touch | **CST820** (I2C) |
| IO expander | **TCA9554** — panel/touch reset and enable lines sit behind it, not on direct GPIO |
| PMIC | **AXP2101** — powers the display rails, so it must be brought up even with no battery |
| Flash / PSRAM | 16 MB quad / 8 MB embedded octal |
| Also on board | 6-axis IMU **QMI8658**, RTC **PCF85063**, codec **ES8311**, speaker, mic, microSD |
| Power | USB-C only, **no battery** — a tethered desk panel. No battery UI, no charge state |

What the real numbers still drive:

- **Card layout targets a 368 × 448 portrait panel** — a tall, narrow card, minus Brookesia's status
  bar. One image per card is **368 × 220**, leaving room for text and the heart row; that is the size
  the backend pre-scales media to.
- **JPEG decode cache**: the platform image already carries the `CONFIG_LV_CACHE_DEF_SIZE ≥ 720000`
  lesson from #188 — 368 × 220 card JPEGs live under the same ceiling as the boot screen did.
- Bring-up gotchas (TCA9554 init order, AXP2101 rails) are the platform's problem now, solved in the
  #188 board port — no longer this app's concern.

## Gestures — designed around the system gesture

| Input | Does |
|---|---|
| Swipe **L / R** | previous / next post |
| Tap the heart | like / unlike (optimistic, reverts on failure) |
| Tap the text | expand / collapse a truncated post |
| Swipe **up from bottom** | **Brookesia home — system, never intercepted** |

Horizontal navigation is deliberate. A vertical "scroll the feed" gesture is the obvious instinct for
a timeline, and it is exactly what collides with Brookesia's home gesture — so posts move left/right.

## The device never talks to api.x.com

OAuth, TLS to X, rate-limit bookkeeping, and timeline-sized JSON don't belong on a microcontroller. A
backend leg on the array does the X work; the panel speaks a small LAN contract, app-namespaced
(`/xviewer/*`, the way Ember's is `/ember/*`):

| Endpoint | Behaviour |
|---|---|
| `GET /xviewer/feed` | newest N posts: `{id, text, ts, metrics:{likes,reposts,views}, img:"/xviewer/img/<id>.jpg", liked}` |
| `GET /xviewer/img/<id>.jpg` | the post's media, **pre-scaled server-side to 368 × 220**, baseline JPEG |
| `POST /xviewer/action` | `{id, action:"like"\|"unlike"}` → calls X, returns the new state |

Bounded response sizes, no redirects, no chunked surprises. **Pre-scaling is non-negotiable** —
decoding a JPEG on-device is fine, resizing full-size X media on-device is not. HTTP failure is a UI
state (stale badge, reverted heart), never a crash.

### X API — fully verified 2026-08-18

Creds live in the `cso-operator-app` pod as `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` /
`X_ACCESS_TOKEN_SECRET` — **OAuth 1.0a user context**, signed, not bearer.

| Call | Result |
|---|---|
| `GET /2/users/me` | OK — id `2036858257877188608`, **@TunaStreetTest** |
| `GET /2/users/:id/tweets` | OK — posts with `public_metrics` populated |
| `POST /2/users/:id/likes` | OK — `{'liked': True}` |
| `DELETE /2/users/:id/likes` | OK — `{'liked': False}`, like count restored, no residue |

Probed on Steven's explicit go against the account's own newest post. **Read, like, and unlike are
all proven.** The feed is the real timeline with live metrics; the published-queue tweet ids remain
only as a degraded path if rate limits bite.

## Backend + simulator — built, 13/13 against live X (2026-08-18)

```bash
cd ~/amoled-x-viewer && ./scripts/run.sh     # -> http://127.0.0.1:8091 (LAN: 192.168.1.121:8091)
./scripts/test.sh                            # 13-check contract evaluation
```

All 13 checks pass against live X: real feed with live metrics, 368 × 220 baseline JPEG (the S3's ROM
tjpgd can't do progressive), 404/400 on bad input, like → unlike with account state restored. Media on
current posts is video, so the backend serves X's `preview_image_url` cover-fit to the card slot. The
pixel-true simulator renders the 368 × 448 panel inside a Brookesia-shell mock — still useful for card
layout iteration, though the JS package is now the on-device truth. **The backend and contract carry
over to the runtime model unchanged.**

Backend home question stays open: it runs today as the small Python app in `~/amoled-x-viewer`
(started by `run.sh`, creds pulled from the `cso-operator-app` pod). Whether it stays there, moves
into `cso-operator-app`, or becomes a NiFi PG gets decided when it needs to survive unattended — not
blocking any phase.

## Phases — R0–R2 done eyes-on 2026-08-19; R3 code shipped, on-glass verification remains

**Phase R0 + R1 — DONE 2026-08-19.** Tile on the Brookesia home screen, app opens, feed loads real
@TunaStreetTest posts with images, swipe L/R navigates. Two as-built fixes got it there:

- **littlefs re-stage**: every runtime package must be re-staged in
  `examples/system/super/littlefs/apps/` before a storage-partition flash — apps not in the staged
  image vanish on flash.
- **Windows Firewall rule `Allow XViewer Port 8091`** (inbound allow) — WSL mirrored networking
  exposes the bind but the firewall drops LAN clients without a per-port rule (the #52 pattern).
  Verified still enabled 2026-08-19.

**Phase R2 — DONE 2026-08-19.** Heart tap on the panel landed a real like on x.com (count 0 → 1,
backend-verified), unliked/reverted paths wired. One behavior note, not a bug: a feed response
served from cache (`cached: true`) can show `liked` from before the tap — the backend *does* update
its cached entry on every `/xviewer/action`, so this only appears when the feed render raced the
action.

**Phase R3 — code shipped in `db5f06f`; what remains is verifying it on the glass.** Already in
`app.js`: 60 s periodic feed refresh (`xv_refresh`), 10 s retry on failure (`xv_retry`),
error/status states ("backend unreachable - retrying", "bad feed payload", "feed is empty",
"like failed" with optimistic revert), stale-download guards, and full timer/service cleanup in
`on_stop`. Idle is the system's: the app ignores vertical gestures and Brookesia owns the shell.
The verification pass is the section below — it runs from **StarlinkAI**, which now holds the
board's USB (COM6).

## Final test pass — StarlinkAI

The board's USB moved to StarlinkAI (enumerates **COM6**; re-identify by MAC `1c:db:d4:7b:85:84`
with `python -m serial.tools.list_ports -v`). The panel's WiFi still reaches the backend at
`http://192.168.1.121:8091` on WindowsDesktop — StarlinkAI itself is off that LAN, so backend-side
checks go through WindowsDesktop (issue-comment coordination or Tailscale). Serial/flash tooling and
the no-IDF littlefs recipe: [`amoled-1.8-v2/tools/README.md`](https://github.com/TunaStreetTest/waveshare-devices/blob/main/amoled-1.8-v2/tools/README.md);
the current flash image is already staged on StarlinkAI at `~/amoled-x-ember/cache/device/`.

1. **Verify before flashing.** Extract `/apps/tunastreet.xviewer/app/app.js` from the staged
   `littlefs_data.bin` (littlefs-python, block_size 4096 × block_count 1250) and diff against the
   repo copy at `main`. Identical → **no flash needed**, the glass already runs the final code.
   Drift → patch the bin per the tools README and flash `0xaa1000` only — **ask before flashing**
   (board hard-resets, EFM agent drops ~15 s).
2. **Regression:** tile opens, feed renders real posts with images, swipe L/R moves posts,
   swipe-up home gesture works, EFM agent stays online.
3. **Refresh timer:** with the app open, capture serial — `python tools/readlog.py COM6 180` —
   and expect `[xviewer] fetching feed` / `feed ok: N posts` roughly every 60 s.
4. **Error + reconnect:** coordinate a brief backend stop/start on the issue first (it's a live
   service on WindowsDesktop — fresh ask, every time). Expect "backend unreachable - retrying" on
   the status line, then recovery within ~10 s of the backend returning. If not coordinated, report
   it as untested — don't skip silently.
5. **Idle soak:** leave the app open ≥ 15 min. No crash/reset on serial, feed still refreshing,
   agent heartbeats intact (EFM is Tailscale-exposed on 10090 for a remote check).
6. **Report back** on the StarlinkAI issue with per-item results + serial snippets, and
   cross-comment on [#183](https://github.com/cldr-steven-matison/DesktopShare/issues/183).

## Where the code lives vs where the docs live

- **App package**: [`TunaStreetTest/waveshare-devices`](https://github.com/TunaStreetTest/waveshare-devices)
  `amoled-1.8-v2/apps/tunastreet.xviewer/` — the platform repo is where runtime packages live, beside
  the `tunastreet.hello` template.
- **Backend + simulator**: `~/amoled-x-viewer` on WindowsDesktop (local git, `b6991c4`). Its repo
  home rides the open backend-home question; the retired C++ `firmware/` skeleton in that tree is
  historical.
- **Every `.md` stays here in DesktopShare.**

## Done condition

The panel sits on the desk running the #188 platform. The X viewer tile sits on the Brookesia home
screen next to the hello tile (and Ember's, when #184 ships its package). Tapping it shows the newest
posts from @TunaStreetTest; swipe L/R moves between them; a tap on the heart lands a real like
visible on x.com; swipe up returns home and the EFM agent never blinked. Package committed to
waveshare-devices, this doc updated with as-built deviations.
