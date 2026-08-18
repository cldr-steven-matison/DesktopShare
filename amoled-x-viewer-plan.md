# AMOLED X viewer — swipe + like my X posts on the panel

**Plan for [issue #183](https://github.com/cldr-steven-matison/DesktopShare/issues/183).**
Claude's app for the Waveshare ESP32-S3-Touch-AMOLED-1.8 **V2**: swipe through my X posts like a tiny
feed, tap to heart one. Sibling app on the same board and the same launcher: **Ember** (Grok,
StarlinkAI) — issue #184, [`amoled-ember-plan.md`](amoled-ember-plan.md).

**Target: both apps deployed together** — one ESP-Brookesia image carrying Ember *and* X viewer as two
tiles on the home screen.

## Scope — an app, not agent work

This work stream is **an in-device app and the backend leg that feeds it.** MicroFi, EFM, agent class
`AMOLED`, C2 heartbeats and flow definitions are a separate work stream
([issue #181](https://github.com/cldr-steven-matison/DesktopShare/issues/181), golden source
`efm-waveshare-amoled.md`). Nothing in this issue modifies or depends on the MicroFi firmware.

## Architecture — a Brookesia app, not a replacement OS

**Corrected 2026-08-18 to match #184.** An earlier draft of this plan called for standalone firmware with
its own partition table, which would have made the two apps mutually exclusive on one board. They are
not. Ember is an ESP-Brookesia launcher app, and X viewer is built the same way:

- a `systems::phone::App` registered through `ESP_UTILS_REGISTER_PLUGIN_WITH_CONSTRUCTOR`
- a **112 × 112** launcher tile (`img_app_x_viewer`) sitting next to Ember, Settings, Calculator
- shipped as a **drop-in component**, `firmware/components/x_viewer/`, copied into factory Brookesia

**Brookesia owns the shell** — home grid, status bar, recents, and the swipe-up-from-bottom home gesture.
The app must not steal the system gesture; see the gesture table below, which is designed around it.

Still not a MicroFi processor — the flow engine's 256-byte FlowFile ceiling and absent display stack rule
it out, same as for Ember.

**There is no MicroFi-vs-Brookesia swap. Corrected 2026-08-18 on #181.** An earlier version of this
paragraph said flashing Brookesia takes the `AMOLED` EFM agent dark and `pio run -e amoled -t upload`
restores it. That whole-image path wiped the board's factory OS once already and has been deleted from
MicroFi. The agent now ships *inside* the same Brookesia image as a third drop-in component,
`firmware/components/microfi_agent/` — so the board runs the launcher, both apps, and the EFM agent on
one boot. Golden source: [`efm-waveshare-amoled.md`](efm-waveshare-amoled.md).

**The board-contention worry is retracted.** It was an artifact of the standalone-firmware assumption.
Both apps ship in one image as two tiles, so #183 and #184 do not compete for the board.

### Deployment — one image, two tiles

The shape Steven asked for. Factory Brookesia plus both components:

```
firmware/components/ember/      # from steven-matison/ember  (#184)
firmware/components/x_viewer/   # from this issue            (#183)
```

Both register into Brookesia's app registry, both get a tile, one flash to COM8. Ember also ships a
"slim host" (phone + Ember only) for solo use — that shape is *not* how the pair deploys, and choosing it
would drop this app.

**Access needed:** `steven-matison/ember` returns 404 to this session's GitHub login (`TunaStreetTest`),
so its `firmware/components/ember/` tree can't be read yet. Combining the two into one image needs read
access to that repo.

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
| Power | USB-C only, **no battery** — a tethered desk panel. No battery UI, no charge state, no AXP2101 percentage (the chip is there; there's nothing to measure) |

What the real numbers change:

- **Framebuffers**: 368 × 448 × 2 B = **322 KB** per full 16-bit frame — comfortable in 8 MB PSRAM.
  Brookesia's own buffers share that budget, so the app allocates image caches from PSRAM deliberately
  rather than assuming it has the panel to itself.
- **Card layout targets a 368 × 448 portrait panel** — a tall, narrow card, minus Brookesia's status bar.
  One image per card wants roughly **368 × 220**, leaving room for text and the heart row. That is the
  size the backend pre-scales media to.
- **The TCA9554 is the bring-up gotcha** — reset lines behind an I2C expander, so init order is
  AXP2101 → TCA9554 → panel. Factory Brookesia for this SKU already handles it, which is a further
  argument for the drop-in shape over a hand-rolled host.

## Gestures — designed around the system gesture

| Input | Does |
|---|---|
| Swipe **L / R** | previous / next post |
| Tap the heart | like / unlike (optimistic, reverts on failure) |
| Tap the text | expand / collapse a truncated post |
| Swipe **up from bottom** | **Brookesia home — system, never intercepted** |

Horizontal navigation is deliberate. A vertical "scroll the feed" gesture is the obvious instinct for a
timeline, and it is exactly what collides with Brookesia's home gesture — so posts move left/right, the
same convention Ember uses for channels.

## The device never talks to api.x.com

OAuth, TLS to X, rate-limit bookkeeping, and timeline-sized JSON don't belong on a microcontroller. A
backend leg on the array does the X work; the panel speaks a small LAN contract, **app-namespaced the way
Ember's is** (`/ember/*` → `/xviewer/*`; "amoled" would name the device, and two apps live there):

| Endpoint | Behaviour |
|---|---|
| `GET /xviewer/feed` | newest N posts: `{id, text, ts, metrics:{likes,reposts,views}, img:"/xviewer/img/<id>.jpg", liked}` |
| `GET /xviewer/img/<id>.jpg` | the post's media, **pre-scaled server-side to 368 × 220**, baseline JPEG |
| `POST /xviewer/action` | `{id, action:"like"\|"unlike"}` → calls X, returns the new state |

Bounded response sizes, no redirects, no chunked surprises. **Pre-scaling is non-negotiable** — decoding
a JPEG into PSRAM is fine, resizing full-size X media on-device is not. HTTP failure is a UI state (stale
badge, reverted heart), never a crash.

### X API — fully verified 2026-08-18

Creds live in the `cso-operator-app` pod as `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` /
`X_ACCESS_TOKEN_SECRET` — **OAuth 1.0a user context**, signed, not bearer.

| Call | Result |
|---|---|
| `GET /2/users/me` | OK — id `2036858257877188608`, **@TunaStreetTest** |
| `GET /2/users/:id/tweets` | OK — posts with `public_metrics` (likes/reposts) populated |
| `POST /2/users/:id/likes` | OK — `{'liked': True}` |
| `DELETE /2/users/:id/likes` | OK — `{'liked': False}`, like count restored, no residue |

Probed on Steven's explicit go against the account's own newest post. **Read, like, and unlike are all
proven** — no open X API questions, and nothing about the tier can invalidate a later phase. The feed is
the real timeline with live metrics; the published-queue tweet ids remain only as a degraded path if rate
limits bite.

### Backend home — decided at Phase 2, live flow dumped first

Per the match-existing-X-post-precedent rule: the X posting path lives in NiFi today, so the default is a
new central-NiFi PG (`HandleHttpRequest → … → HandleHttpResponse`) shaped like the existing posting flow,
with a custom Python processor only if image resize forces it. The alternative — a feed endpoint in
`cso-operator-app`'s backend — wins only if the NiFi shape fights binary responses and on-the-fly
scaling. Decide from the dumped flow, not from this doc. Note this backend runs on the **WindowsDesktop
array**, while Ember's runs on **StarlinkAI** — the two apps share a launcher, not a backend.

## Built and running locally — 2026-08-18

The board is unplugged, so the deliverable is the same split Ember used: **backend + pixel-true simulator
now, flash later.** Both are running on WindowsDesktop.

```bash
cd ~/amoled-x-viewer && ./scripts/run.sh     # -> http://127.0.0.1:8091
./scripts/test.sh                            # 13-check contract evaluation
```

App code lives at `~/amoled-x-viewer` (committed locally, `b6991c4`), waiting on the repo to exist before
it can be pushed. Every `.md` stays here in DesktopShare.

**Evaluation — 13 checks, 13 passed**, against live X, not fixtures:

| Check | Result |
|---|---|
| `GET /xviewer/feed` | 10 real posts from **@TunaStreetTest**, live `public_metrics` |
| `GET /xviewer/img/<id>.jpg` | **368 × 220**, baseline JPEG (not progressive — the S3's ROM tjpgd needs baseline), ~17 KB |
| unknown media id | 404, not a 500 |
| `POST /xviewer/action` bad input | 400 |
| like → unlike | `{'liked': true}` → `{'liked': false}`, state restored on the account |
| simulator page | 200 |

Media on these posts is video, so the backend serves X's `preview_image_url` and cover-fits it to the
card slot — centre-cropped, never letterboxed.

**The simulator is the product at this stage.** It renders the exact 368 × 448 panel inside a Brookesia
shell — home screen with the **X viewer and Ember tiles**, status bar, home indicator — so the tile model
this issue got wrong twice is now visible rather than described. Swipe L/R moves posts, tap the heart
lands a real like on X, drag up from the bottom edge returns to the launcher. Deep links `#app` and
`#app-2` jump straight in for testing.

One real bug the screenshots caught: `.media{display:block}` was overriding the `hidden` attribute, so an
empty image box rendered alongside the "no media" placeholder. Fixed with an explicit `[hidden]` rule.

**Not built, and not claimed as built:** `firmware/components/x_viewer/` is a skeleton that has never been
compiled — there's no ESP-IDF on this host and the board is unplugged. Its geometry, contract, and JSON
are pinned by the verified backend, but the Brookesia class and registration details still need
reconciling against Ember's actual component, which isn't readable from this account.

## Phases

**Phase 0 — Brookesia bring-up.** Stand up factory ESP-Brookesia for this exact SKU and flash it; confirm
the home screen, status bar, and touch on this unit. Exit: a working launcher on the board. *(SKU gate
already closed.)*

**Phase 1 — the app tile, no network.** Register `x_viewer` as a `systems::phone::App` with its 112 × 112
tile; card-per-post layout with ~10 canned posts baked in; swipe L/R between them; heart animates
locally. Exit: tap the tile, swipe cards, swipe up returns home. **Swipe latency and card layout are the
actual product** — the phase worth iterating on.

**Phase 2 — live feed.** Backend leg built in its decided home; fetch `/xviewer/feed` on boot and on
swipe-past-end; cache images in PSRAM. Exit: a post I publish appears on the panel with no reflash.

**Phase 3 — the like.** Tap heart → `POST /xviewer/action` → optimistic UI, revert on failure; unlike
too. **Unblocked** — like and unlike are both proven against the live account. Exit: a tap on the panel
puts a real like on x.com.

**Phase 4 — both tiles.** Combine `components/ember/` and `components/x_viewer/` into one Brookesia image
and flash it. Exit: **both apps on the home screen**, each reaching its own backend. This is Steven's
stated goal and it is a joint deliverable with #184.

**Phase 5 — polish.** Idle dim/sleep (the whole point of AMOLED), a WiFi/connection status pill (no
battery pill — there's no battery), reconnect handling, doc update with as-built deviations.

## Where the code lives vs where the docs live

**Decided 2026-08-18: a new repo for the app; every `.md` stays in DesktopShare.** Same split already used
for MicroFi, cso-operator-app, and Ember — code in its own repo, planning and golden-source docs here.

**`amoled-x-viewer` is a TunaStreetTest project and repo.** Code is committed locally at
`~/amoled-x-viewer` and waits there; DesktopShare keeps the docs.

## Open items

Every design question is settled.

1. **Push the app repo** once it exists.
2. **`components/ember/` is not readable from here** — `steven-matison/ember` returns 404 to this
   session's login, so Phase 4's combined image can't be assembled yet.

## Done condition

The panel sits on the desk running Brookesia with **two tiles**. Tapping X viewer shows the newest posts
from @TunaStreetTest; swipe L/R moves between them; a tap on the heart lands a real like visible on
x.com; swipe up returns to the home screen with Ember beside it. Firmware repo, backend flow export, and
this doc are committed.
