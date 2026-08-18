# AMOLED X viewer — swipe + like my X posts on the panel

**Plan for [issue #183](https://github.com/cldr-steven-matison/DesktopShare/issues/183).**
Claude's app for the Waveshare ESP32-S3 Touch AMOLED **V2**: swipe through my X posts like a tiny feed,
tap to heart one. Sibling app on the same board: **Ember** (Grok, StarlinkAI) — issue #184. This doc is
the spec; the issue is the thread.

## Scope — an app, not agent work

This work stream is **an in-device app and the backend leg that feeds it.** MicroFi, EFM, agent class
`AMOLED`, C2 heartbeats, flow definitions, the flow engine — **all of that is a separate work stream**
([issue #181](https://github.com/cldr-steven-matison/DesktopShare/issues/181), golden source
`efm-waveshare-amoled.md`). Nothing in this issue modifies, extends, or depends on the MicroFi firmware.

If a question here can only be answered by talking about agents or heartbeats, it belongs in #181.

**Same firmware convention as #184:** dedicated app firmware, not a MicroFi processor. Flashing this app
takes the board dark in EFM, exactly as Ember does; `pio run -e amoled -t upload` restores the agent
whenever wanted. That swap is expected and reversible — it is not a design constraint on this app, and it
is not this issue's decision to re-litigate.

**Board contention, flagged not solved:** three firmwares now want one physical board — the MicroFi agent
(#181), this viewer (#183), and Ember (#184). Only one is flashed at a time. Worth knowing before two
sessions reach for it on the same evening; a second board would remove the conflict entirely.

## The device

**SKU confirmed 2026-08-18** from the rear label (photo on #181) — the hardware gate is closed:

| | |
|---|---|
| Board | **Waveshare ESP32-S3-Touch-AMOLED-1.8, V2** |
| Display | **CO5300**, 1.8″ AMOLED, **368 × 448** — QSPI |
| Touch | **CST820** (I2C) |
| IO expander | **TCA9554** — panel/touch reset and enable lines sit behind it, not on direct GPIO |
| PMIC | **AXP2101** — powers the display rails, so it must be brought up even with no battery |
| Flash / PSRAM | 16 MB quad / 8 MB embedded octal |
| Also on board | 6-axis IMU **QMI8658**, RTC **PCF85063**, codec **ES8311**, speaker, mic, microSD |
| Power | USB-C only, **no battery** — a tethered desk panel, not a handheld. No battery UI, no charge state, no AXP2101 percentage (the chip is there; there's just nothing to measure) |

**Standalone ESP-IDF + LVGL v9 app**, its own repo (`amoled-x-viewer`), its own build and partition
table. Swipe = LVGL gesture events on a card-per-post layout; heart = a tap target on the card.

What the real numbers change:

- **Framebuffers**: 368 × 448 × 2 B = **322 KB** per full 16-bit frame — comfortable in 8 MB PSRAM, and
  double buffering (644 KB) is still fine. Internal SRAM was never an option; now that's arithmetic, not
  a guess.
- **Card layout targets a 368 × 448 portrait panel** — a tall, narrow card. Post text wraps early; one
  image per card wants roughly 368 × 220 to leave room for text and the heart row. This is the number
  the backend pre-scales media to.
- **The TCA9554 is the bring-up gotcha.** Reset lines behind an I2C expander mean the panel cannot come
  up before I2C and the expander do; a "dead panel" during Phase 0 is far more likely to be expander
  ordering than a bad display.
- **Extras are out of scope but worth knowing they exist** — the IMU, mic, speaker, and SD are on the
  board and cost nothing to ignore. (The IMU is what makes #184's shake gesture possible.)

## The device never talks to api.x.com

OAuth, TLS to X, rate-limit bookkeeping, and timeline-sized JSON don't belong on a microcontroller. A
backend leg on the array does the X work; the panel speaks a tiny LAN contract, the same shape Ember
uses:

| Endpoint | Behaviour |
|---|---|
| `GET /amoled/feed` | newest N posts: `{id, text, ts, metrics:{likes,reposts,views}, img:"/amoled/img/<id>.jpg", liked}` |
| `GET /amoled/img/<id>.jpg` | the post's media, **pre-scaled server-side to panel resolution**, baseline JPEG |
| `POST /amoled/action` | `{id, action:"like"\|"unlike"}` → calls X, returns the new state |

Bounded response sizes, no redirects, no chunked surprises. **Pre-scaling is non-negotiable** — decoding
a JPEG into PSRAM is fine, resizing full-size X media on-device is not. The app treats HTTP failure as a
UI state (stale badge, revert the optimistic heart), never as a crash.

### X API — what's verified

Creds live in the `cso-operator-app` pod as `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` /
`X_ACCESS_TOKEN_SECRET` — **OAuth 1.0a user context**, so calls are signed, not bearer.

**Probed live 2026-08-18 — reads work:**

| Call | Result |
|---|---|
| `GET /2/users/me` | OK — id `2036858257877188608`, **@TunaStreetTest** |
| `GET /2/users/:id/tweets` | OK — 5 posts, `public_metrics` (likes/reposts) populated |

So the feed is the account's **real timeline with live metrics**. The old worry — a read-poor free tier
forcing the feed to come from published-queue tweet ids — is retired to a degraded path if rate limits
bite.

**Not verified: the like write** (`POST /2/users/:id/likes`). That probe puts a real, publicly visible
like on the account, so it waits on Steven's go. It gates Phase 3 and nothing earlier. Reversible.

### Backend home — decided at Phase 2, live flow dumped first

Per the match-existing-X-post-precedent rule: the X posting path lives in NiFi today, so the default is a
new central-NiFi PG (`HandleHttpRequest → … → HandleHttpResponse`) shaped like the existing posting flow,
with a custom Python processor only if image resize forces it. The alternative — a feed endpoint in
`cso-operator-app`'s backend — wins only if the NiFi shape fights binary responses and on-the-fly
scaling. Decide from the dumped flow, not from this doc.

## Phases

**Phase 0 — hardware bring-up.** ~~Read the rear label~~ **done** — SKU, display, touch, and expander are
all pinned above. Remaining: pull the Waveshare BSP for the `ESP32-S3-Touch-AMOLED-1.8` V2 and light the
panel + touch on this unit, minding the AXP2101-then-TCA9554-then-panel init order. Exit: the panel lights
and a touch registers. **Unblocked.**

**Phase 1 — the UI, no network.** LVGL card-per-post layout, swipe between ~10 canned posts baked into
the image, heart animates locally. Exit: it feels right under the thumb. **Swipe latency and card layout
are the actual product** — this is the phase worth iterating on.

**Phase 2 — live feed.** Backend leg built in its decided home; device fetches `/amoled/feed` on boot and
on swipe-past-end; images cached. Exit: a post I publish appears on the panel with no reflash.

**Phase 3 — the like.** Tap heart → `POST /amoled/action` → optimistic UI, revert on failure; unlike too.
Gated on the like-write probe. Exit: a tap on the panel puts a real like on x.com.

**Phase 4 — polish.** Idle dim/sleep, a WiFi/connection status pill (no battery pill — there's no
battery), reconnect handling, doc update with as-built deviations.

## Open decisions

1. **Repo name/home** — `amoled-x-viewer` as a new repo is the default; it shares no code with MicroFi.
2. **The like-write probe** — needs an explicit go, because it's a public action on the real account.
3. ~~SKU size~~ — **answered 2026-08-18**: ESP32-S3-Touch-AMOLED-1.8 V2, CO5300 / 368×448 / CST820.
4. ~~Which X account~~ — **answered**: @TunaStreetTest (`2036858257877188608`), verified live 2026-08-18.
5. ~~Firmware repo home / EFM coexistence~~ — **not this issue.** Dedicated firmware per #184's
   convention; the agent is #181's business.

## Done condition

The panel sits on the desk showing the newest posts from @TunaStreetTest; swipe moves between them; a tap
on the heart lands a real like visible on x.com. Firmware repo, backend flow export, and this doc are
committed.
