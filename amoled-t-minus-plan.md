# AMOLED T-Minus — the next launch, counting down on the panel

**Plan for [issue #269](https://github.com/cldr-steven-matison/DesktopShare/issues/269).** Claude's
countdown app for the Waveshare ESP32-S3-Touch-AMOLED-1.8 **V2**: the next rocket that has not lifted
off yet, its clock ticking down to T-0, with the vehicle drawn under it. This is the as-built record
that every sibling app already has and T-Minus was missing — the app itself shipped under #184; #269
is the writeup catching up.

T-Minus **is** the Ember redesign. The Grok "pocket instrument" (#184,
[`completed/amoled-ember-plan.md`](completed/amoled-ember-plan.md)) read too close to the X viewer, so
it was retired and rebuilt as a launch countdown. Sibling apps on the same boards and the same
launcher: **X-Viewer** (#183, [`amoled-x-viewer-plan.md`](amoled-x-viewer-plan.md)) and **Racing**
(#205, [`amoled-racing-plan.md`](amoled-racing-plan.md)).

## Scope — an app, not agent work

This is **an in-device app and the backend leg that feeds it.** MicroFi, EFM, agent class `AMOLED`,
C2 heartbeats and flow definitions are the platform work stream (golden source
[`efm-waveshare-amoled.md`](efm-waveshare-amoled.md)). Nothing here touches the agent. The app runs
identically on the boards that carry an agent (Tuna Street) and the one that doesn't (Cloudera,
`hasAgent=false`).

## Architecture — a runtime app package on the panelkit

A runtime package — `manifest.json` + `app/app.js` + `res/` JSON-UI — dropped into `apps/` on the
board's filesystem, scanned at `System::init()`, given a launcher tile. Same runtime model as the
X viewer: sandboxed **QuickJS + JSON-UI**, no `fetch`, no `setTimeout`; HTTP, timers, and UI
mutation are all system services (`SystemGui`, `SystemTimer`). What differs from the X viewer is the
screen, and one hard constraint the countdown forced:

- **The home screen is absolute-positioned, not flex.** A flex parent repositions a background image
  out from under the clock; the screen had to leave flex to pin the launch art beneath the countdown
  at all. The screen JSON is generated from panelkit primitives, not hand-written —
  `files/tminus/gen_tminus_screen.py` emits `res/screens/home.json` via
  `waveshare-devices/amoled-1.8-v2/uikit/panelkit.py` (`pk.screen` / `pk.label` / `pk.sprite`).
- **The launch art is `clickable:false`.** An `image` node defaults to `clickable:true`
  (`parser_node.cpp`), and a decorative picture over the nav band swallows every swipe. The art
  covers the whole middle of the panel, so `sprite()`'s default `clickable:false` (panelkit lint R6)
  is what keeps navigation alive — the exact bug from the #184/#220 round.
- **Text is ASCII, always.** The panel font is LVGL's built-in Montserrat (no FreeType) — anything
  above `0x7E` renders as a white tofu box. The app folds every backend string (vehicle, mission,
  pad) to ASCII before it hits `SetText`, and the backend abbreviates on its side too.

## The device

Same board as every Tuna Street app (SKU on #181): **CO5300** 1.8″ AMOLED, **368 × 448** portrait,
QSPI; **CST820** touch; **AXP2101** PMIC; 16 MB flash / 8 MB PSRAM. What the numbers drive here:

- **The layout targets 368 × 448 portrait.** The countdown is the hero: a 48 pt clock under a 20 pt
  `T-MINUS` brand bar, with the vehicle name and mission below, then the art band, then pad + status
  in the footer. Exact bands are in the screen table below.
- **The art band is 368 × 168** — narrower than the X viewer's 368 × 220 card, measured to leave room
  for the clock stack above and the two footer rows below. Per-vehicle JPEGs are pre-cropped to that.
- Bring-up (TCA9554 order, AXP2101 rails) is the platform's problem, solved in the #188 board port.

## Gestures — swipe only, no tap targets

| Input | Does |
|---|---|
| Swipe **L** | next launch (`step(+1)`) |
| Swipe **R** | previous launch (`step(-1)`) |
| Swipe **up from bottom** | **Brookesia home — system, never intercepted** |

Navigation is **gesture-only**. An earlier round tried half-panel tap zones (#220); they collided
with drag detection, so the whole screen root listens for one `tminus.gesture` action and steps the
launch window on it. There is no heart, no button — the app is a glanceable readout, not a control
surface. A panelkit tap target fires on both `pressed` and `released`, so any tap handler would need
a debounce; sidestepping taps entirely avoids that.

## The device never talks to the Space Devs API

LL2 fetches, the upcoming-window bookkeeping, TTL caching, and the vehicle-art lookup don't belong on
a microcontroller. A backend leg on WindowsDesktop does the launch work; the panel speaks a small
app-namespaced LAN contract (`/tminus/*`), the way the X viewer's is `/xviewer/*`:

| Endpoint | Behaviour |
|---|---|
| `GET /health` | `{ok:true, app:"tminus"}` |
| `GET /tminus/now` | current launch: `{id, vehicle, mission, pad, t0_unix, server_unix, status, idx, count, img}` |
| `POST /tminus/step` | body `{dir: 1\|-1}` → same shape, moves to the next/previous launch in the window |
| `GET /tminus/img/<id>.jpg` | the vehicle's art, **pre-cropped server-side to 368 × 168**, baseline JPEG |

`server_unix` ships with every payload so the panel counts down against the backend's clock, not its
own (the board has no reliable wall time until SNTP lands). Status drives the clock face: `T-` and a
descending clock before liftoff (`Xd HH:MM` when more than a day out), `T+` and an ascending clock for
`IN FLIGHT`, and a static amber `HOLD` / `--:--:--` for a hold. The app refreshes `/tminus/now` every
60 s and backs off 10 s on error; HTTP failure is a stale readout, never a crash.

### Data source — SpaceX Launch Library 2

`backend/launches.py` pulls the **Launch Library 2** upcoming window
(`https://ll.thespacedevs.com/2.2.0/launch/upcoming/`, `LIMIT = 8`), cached 15 min
(`LL2_TTL_S = 900`). The default launch is **the first one that has not lifted off** — `_next_idx()`
picks the first entry with `t0_unix >= now_unix`. LL2 keeps a launch in `upcoming` for hours after
T-0, so an unfiltered feed headlined a Falcon 9 that had already flown; that filter is the fix. The
backend also normalizes for the panel: vehicle/mission/pad clipped to 24/36/40 chars, "Space Launch
Complex X" → "SLC-X", location mapped to a short place hint.

## Backend + art pipeline

```bash
cd ~/amoled-tminus && ./scripts/run.sh     # -> uvicorn server:app on :8092 (LAN 192.168.1.121:8092)
```

Runs as the small FastAPI app in `~/amoled-tminus/backend` (`server.py`), venv shared with
`tuna-starlink-app`. The panel reaches it over the ATT LAN at `192.168.1.121:8092`; the Windows
Firewall rule **`Allow T-Minus Port 8092`** (inbound) is what lets LAN clients through WSL mirrored
networking — the same per-port pattern as `:8091` / `:8093` / `:8094`.

Vehicle art is a three-generator pipeline, outputs committed under `files/tminus/`:

| Generator | Produces |
|---|---|
| `gen_tminus_art.py` | the vector fallback rocket (`res/images/launch.png`, 368 × 200 RGBA starfield + silhouette) — shown when no per-vehicle JPEG exists |
| `gen_vehicle_art.py` | per-vehicle studio art via xAI Imagine (`grok-imagine-image`) → cropped `files/tminus/vehicles/<slug>.jpg` (368 × 168) + a raw PNG + a contact sheet. Costs real money per image, so it is name-driven (`gen_vehicle_art.py "Falcon 9"`), no generate-all |
| `gen_tminus_screen.py` | `res/screens/home.json` from panelkit |

The backend digests the LL2 vehicle name to a slug and serves `files/tminus/vehicles/<slug>.jpg`
if present, else the vector fallback. Eleven vehicles are drawn as of 2026-08-25 (falcon-9, starship,
falcon-heavy, electron, vulcan, ariane-62, long-march-6c, long-march-12a, soyuz-2-1b, vega-c,
new-glenn); the app caches the downloaded JPEG in a 2-slot app-cache so a swipe back doesn't refetch.

## Screen — as generated (`res/screens/home.json`)

368 × 448 black root, absolute layout. Amber is `#ffb000`, hold is `#ff5a1f`.

| Band | y, h | Content |
|---|---|---|
| Brand bar | 0, 44 | `T-MINUS`, amber, 20 pt |
| Prefix | 50, 22 | `T-` / `T+` / `HOLD`, amber, 16 pt (bound `clockColor`/`clockSize`) |
| Clock | 74, 68 | `--:--:--` hero, amber, 48 pt |
| Vehicle | 148, 32 | rocket name, white `#f0f0f0`, 20 pt |
| Mission | 182, 28 | mission, muted `#888888`, 16 pt |
| Launch art | 206, 168 | `src=${image.launch}`, **`clickable:false`**, hidden via `artHidden` |
| Pad | 380, 22 | location / pad, muted, 16 pt |
| Status | 402, 22 | status + `idx/count`, muted, 16 pt |

## Phases — DONE; app live on both boards

**Built and deployed under #184** as the Ember redesign, rebuilt on the panelkit. As-built state:

- **Live on both WindowsDesktop boards** (panelkit rebuild 2026-08-27, `waveshare-devices` `15105fb`
  + `db2caa9`): the **Tuna Street** board (COM8, tile on the 2×2 paged launcher) and the **Cloudera**
  board (COM10, single-page launcher). After that reflash all three backends were down and were
  restarted from each repo's `scripts/run.sh` — the standard "apps don't work after a flash = check
  the backends first" check (`efm-waveshare-amoled.md`).
- **Countdown + swipe confirmed on the glass**: clock ticks against `server_unix`, swipe L/R walks the
  8-launch window, per-vehicle art renders with the vector fallback on a miss.
- **The two hard-won fixes** are both in place: absolute layout so the art sits under the clock, and
  `clickable:false` on the art so swipes reach the handler.

**Staging**: `tools/stage_apps.py <image.bin> tunastreet.tminus …` mirrors the package into
`littlefs_data.bin` with littlefs-python, leaving the `brookesia.general.*` system apps untouched. A
storage-partition flash (`0xaa1000`) carries it; a firmware-only reflash (e.g. the #265 power-button
change) touches `0x60000` only and leaves the staged apps — T-Minus included — in place.

## Where the code lives vs where the docs live

- **App package + backend**: [`TunaStreetTest/amoled-tminus`](https://github.com/TunaStreetTest/amoled-tminus),
  cloned at `~/amoled-tminus` (app under `apps/tunastreet.tminus/`, backend under `backend/`). The
  app is also staged into `waveshare-devices/amoled-1.8-v2/apps/tunastreet.tminus/` by the build.
- **Art generators + committed vehicle art**: `files/tminus/` in DesktopShare (`gen_*.py`,
  `vehicles/<slug>.jpg`, the raw PNGs, the contact sheet).
- **Every `.md` stays here in DesktopShare.**

## Done condition — MET

The panel sits on the desk running the #188 platform. The T-MINUS tile is on the launcher; tapping it
shows the next un-launched flight with its clock counting down to T-0; one swipe moves exactly one
launch through the LL2 upcoming window; the drawn vehicle matches the rocket; a hold shows `HOLD` and
`T+` counts up in flight; swipe up returns home and (on Tuna Street) the EFM agent never blinks. Live
on both boards since the 2026-08-27 panelkit rebuild.
