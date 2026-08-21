# AMOLED Cloudera Racing — the game on the panel (#205)

As-built record for [#205](https://github.com/cldr-steven-matison/DesktopShare/issues/205). Data
source is the racing deploy in [#201](https://github.com/cldr-steven-matison/DesktopShare/issues/201)
([`cloudera-racing-deploy-plan.md`](cloudera-racing-deploy-plan.md)).

**What it is:** the Cloudera Racing game itself, playable on the Waveshare
ESP32-S3-Touch-AMOLED-1.8 V2 — pick a car, dodge villains across three lanes — with real telemetry
going into the same pipeline as the browser game, so a run on the glass lands on the same
leaderboard as a run in a browser.

## Where the pieces live

| Piece | Path | Notes |
|---|---|---|
| Panel package | `waveshare-devices/amoled-1.8-v2/apps/tunastreet.racing/` | Brookesia v0.8 runtime JS + JSON-UI, no reflash of the platform |
| Backend | `~/amoled-racing/` (own git repo) | FastAPI on `0.0.0.0:8093`, firewall rule `Allow Racing Port 8093` |
| Simulator | `~/amoled-racing/simulator/` | runs the **real** package off disk; browser + headless + CDP driver |
| Screen / art generators | `DesktopShare/files/racing/gen_racing_screen.py`, `gen_racing_art.py` | the JSON-UI and the sprite PNGs are generated, not hand-maintained |

## The app

Three panels on one 368×448 screen, toggled by `hidden` bindings:

1. **CAR** — CLOUDERA / RACING header, `DRIVER: TUNA` (the device knows who it is — no name entry),
   two car slabs with their own sprites, full-width **START RACING**.
2. **RACE** — HUD (driver, lives, clock, score, speed level, HERO MODE), three lanes, sprite
   obstacles falling, your car at the bottom. **Tap the lane you want** — the road is split into
   three zones, so right→left is one tap.
3. **RESULT** — achievement rank, score, stats, live top-3 from the board, **RACE AGAIN**.

Game rules match the browser game: 3 Datahero lives, speed level every 15 s (+20 km/h), Cloudera
Hero Mode at 2:00, iceberg power-up past 3,000 points. Telemetry (`heartbeat` every second, plus
`collision` / `powerup_iceberg` / `game_over`) POSTs to `/racing/metrics`, which forwards to the
game's `/api/metrics` → NiFi ListenHTTP → Kafka → leaderboard.

Backend contract: `GET /health`, `GET /racing/leaderboard` (digested: ≤8 rows, names ≤12 chars,
`server_unix` because QuickJS `Date` can be epoch-0), `POST /racing/metrics`, plus the simulator at
`/`, `/sim/*.js`, `/pkg/*` (package files, path-checked).

## The simulator — build this first next time

`http://localhost:8093/` runs the **actual shipped package** — it fetches `app/app.js` and
`res/screens/home.json` off disk and executes them against a shim that emulates the Brookesia host
bridge (`SystemGui`, `SystemTimer`, `Http`), rendering the JSON-UI tree at true 368×448.

- `simulator/shim.js` — the host-bridge emulation + view tree. Two renderers share it: DOM (browser)
  and state-only (node).
- `simulator/panel.html` — the panel, nothing else, plus a **CLAUDE DRIVES** autopilot toggle (`C`).
- `simulator/bot.js` — the autopilot, shared by browser and headless, so what you watch is what scores.
- `simulator/headless.js` — `node simulator/headless.js [--dumb] [--pure] [--as NAME]`. Plays a full
  race with no board and no DOM and prints the result; `--dumb` crashes deliberately to prove
  game-over.
- `simulator/drive.js` — launches its **own** Chromium (own `--user-data-dir`, else it just opens a
  tab in the running instance and the debug port never binds), engages the autopilot over CDP, and
  screenshots the run. Node 24's built-in `WebSocket` speaks CDP with no puppeteer install.

## Lessons — what cost flashes, and the rule now

Every one of these was found *after* shipping to the glass, and every one would have been caught in
seconds by the simulator that now exists.

| What broke | Why | The rule now |
|---|---|---|
| Near-blank start screen (only two buttons rendered) | Panels used `layout.type: flex`; a flex parent positions its children and **ignores their absolute x/y** | Every container declares `layout: {"type": "none"}`. Absolute placement only works under a none-layout parent |
| Buttons "wanted to slide, not take the press" | `requireValidPress: true` **drops the whole tap** if the finger drifts, and `container` defaults to `scrollable: true`, so a slight drag became a scroll | Tap targets fire on `pressed` + `released` with no validity gate; lane zones add `pressing`; every container pins `scrollable: false` |
| Steering felt unresponsive | Relative left/right meant right→left needed two clean taps | Absolute lane zones — tap the lane you want, one tap from anywhere |
| Race clock and lives colour silently dead | UI rework deleted the labels; `app.js` kept writing to the old paths, erroring every second | The generator owns the layout; the simulator surfaces every `SystemGui` failure as an app error |
| Sprites drawn as black boxes | PNGs generated as RGB — an opaque backdrop is a visible box on a true-black road | Sprite art is RGBA with a transparent ground |
| RACE OVER painting over a live race (simulator only) | The DOM renderer built nodes **flat** instead of nested, so hiding a container left its children painting | Renderer nests children in their parent element, matching LVGL |
| Simulator showed "leaderboard unreachable" | The page is served from `127.0.0.1:8093` but `app.js` targets `192.168.1.121:8093` — cross-origin, so requests land but **CORS blocks reading the reply** | The simulator rewrites the app's LAN base to `location.origin` |

**Sizing, measured on the glass** (input for the [#208](https://github.com/cldr-steven-matison/DesktopShare/issues/208) UI kit): status text needs a **15px floor** (11px was unreadable), body 16–20px, primary values 28–56px, buttons **76–88px tall with ≥40px between distinct targets** and near-full-width (320 of 368), and in-game controls as full-height thirds rather than small zones. Rule of thumb: **at 368×448 at arm's length, traditional UI sizing is about half of what works.**

**The meta-lesson: for device UI, build the off-device harness before the first flash.** A flash
cycle is minutes plus a person with a finger; the simulator turns that into seconds and catches
exactly the class of bug (layout, event wiring, missing paths) that a boot log cannot show.

**Balance finding (in the game itself, not the port):** past 3,000 points the iceberg power-up
*lowers* the speed level, so farming icebergs pins difficulty at Lv.1 permanently — an autopilot ran
20 minutes / 44,860 points without losing a life. Dodging icebergs instead, the curve works: Lv.81 /
1,660 km/h by the same 20-minute mark. A human can't grab them all, so this only matters if bots
ever share the board; capping the level reduction is the fix.

## Flash / deploy mechanics

Stage into `esp-brookesia/examples/system/super/littlefs/apps/` (re-stage-or-vanish), then patch
`/mnt/c/temp/amoled-super/littlefs_data.bin` **in place** with littlefs-python (4096 × 1250) and
flash `0xaa1000` on **COM8**, asking fresh every time. Note the WSL build tree's
`littlefs_data.bin` was **stale** (pre-#193, no debounce) — `C:\temp\amoled-super\littlefs_data.bin`
is the live-truth image.

`tunastreet.ember` was **deleted from the board** on 2026-08-21 per Steven; `tunastreet.tminus` was
never on the flashed image (it exists in the repo only). Remaining apps on the glass:
`tunastreet.racing`, `tunastreet.xviewer`, and the three `brookesia.general.*`.

## Open / next — filed as sub-issues

| Issue | What |
|---|---|
| [#209](https://github.com/cldr-steven-matison/DesktopShare/issues/209) | Iceberg power-up pins difficulty at Lv.1 — **upstream** game-balance PR (upstream code, not our deploy) |
| [#210](https://github.com/cldr-steven-matison/DesktopShare/issues/210) | No finish line — propose a race/finish mode **upstream** (the game is endless survival today) |
| [#211](https://github.com/cldr-steven-matison/DesktopShare/issues/211) | Confirm the board can reach the backend on `:8093` (firewall rule exists; the obvious test is invalid) |
| [#212](https://github.com/cldr-steven-matison/DesktopShare/issues/212) | Panel simulator harness — the preview half of the **[#208](https://github.com/cldr-steven-matison/DesktopShare/issues/208) AMOLED UI Developer Kit** |
| [#213](https://github.com/cldr-steven-matison/DesktopShare/issues/213) | Tilt steering via the board IMU (no left/right buttons exist) — check sandbox exposure first |

**Upstream vs ours:** the speed-level reset and the missing finish line are both **upstream game logic**
(`services/game/index.html:425` and the single `endGame()` call site at `:434`). Our clone is
byte-identical to upstream HEAD — #201 changed only the nginx upstream, the Kafka bootstrap, and k8s
manifests — so #209/#210 belong upstream as PR/collaboration with
`cldr-jquiroscr/cloudera-racing-standalone` (and the internal `cloudera-racing`), not as a local patch.
