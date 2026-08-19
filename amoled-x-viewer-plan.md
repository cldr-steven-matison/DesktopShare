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

**The one design-deciding unknown** is whether `SystemGui.SetViewSrc` accepts a downloaded JPEG's
sandbox file path. The code path says yes (an unknown image id falls back to treating the raw src
string as a filesystem path); the docs say ids-only. This is the first on-device spike. Fallback if
ids-only is enforced: pre-declare rotating placeholder image ids in `res/images/index.json` and
rewrite the files behind them; worst case, text-only cards.

**Brookesia still owns the shell** — home grid, status bar, and the swipe-up-from-bottom home gesture.
The gesture table below is unchanged and still designed around it.

### Deployment — a package in `apps/`, no reflash

```
waveshare-devices/amoled-1.8-v2/apps/tunastreet.xviewer/   # this app (JS package)
waveshare-devices/amoled-1.8-v2/apps/tunastreet.hello/     # the proven template (#188)
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

## Phases

**Phase R0 — package + image spike.** Author `tunastreet.xviewer` (manifest, JSON-UI card screen,
`app.js`), stage into `apps/`, boot. Exit: tile appears, app opens, and the `SetViewSrc`-from-file
question is answered on the glass (or the fallback is engaged).

**Phase R1 — live feed.** `Http.RequestAsync` → `/xviewer/feed`, card renders post 0 with real text
and metrics; images downloaded to the app sandbox and shown; swipe L/R moves posts. Exit: a post I
publish appears on the panel with no reflash.

**Phase R2 — the like.** Tap heart → `POST /xviewer/action` → optimistic UI, revert on failure;
unlike too. Exit: a tap on the panel puts a real like on x.com, visible on the account.

**Phase R3 — polish.** Feed refresh timer, reconnect/error states, idle behavior, as-built doc
update.

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
