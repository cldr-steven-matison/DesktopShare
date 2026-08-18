# AMOLED X viewer — swipe my X posts on the Waveshare panel

**Plan for [issue #183](https://github.com/cldr-steven-matison/DesktopShare/issues/183). Driving device: the
#181 board — Waveshare ESP32-S3 Touch AMOLED V2 (`efm-waveshare-amoled.md`), 16MB flash, 8MB octal PSRAM,
capacitive touch.** I want to pick the board up, swipe through my X posts like a tiny feed, and tap to
heart one. This doc is the spec; the issue is the thread.

## Architecture — three hard calls up front

### 1. Dedicated app firmware, not a MicroFi processor

MicroFi's engine is the wrong shape for a rich interactive UI: 256-byte FlowFile ceiling, 4-node flow cap,
no display stack, and a compile-time registry that makes every UI iteration a firmware rebuild anyway.
This is a **standalone ESP-IDF + LVGL v9 app** using the Waveshare BSP for the exact V2 SKU (display is
QSPI — CO5300 on the 1.8″ V2 — touch on I2C). Swipe = LVGL gesture events on a card-per-post layout;
heart = tap target on the card.

Consequence to accept: while the app firmware is flashed, the `AMOLED` EFM agent from #181 is dark
(class goes MISSING — that's expected, not a failure; `pio run -e amoled -t upload` puts the agent back
anytime). Embedding a minimal C2 heartbeat task inside the app so the board stays visible in EFM is a
nice-to-have gated behind Phase 4, not a blocker.

### 2. The device never talks to api.x.com

OAuth, TLS to X, rate-limit bookkeeping, and JSON the size of a timeline response don't belong on the
panel. A backend leg on the array does the X work and serves the device a dumb little LAN contract:

- `GET /amoled/feed` → JSON array of the newest N posts:
  `{id, text, ts, metrics:{likes,reposts,views}, img:"/amoled/img/<id>.jpg", liked}`
- `GET /amoled/img/<id>.jpg` → the post's media **pre-scaled server-side to the panel resolution**
  (device-side JPEG decode into PSRAM is fine; device-side resize of full-size X media is not)
- `POST /amoled/action` `{id, action:"like"|"unlike"}` → backend calls the X API, returns the new state

**Backend home is a decision point, checked against live state before building** (the
match-existing-X-post-precedent rule): the X posting path lives in NiFi today, so the default is a new
central-NiFi PG (`HandleHttpRequest → … → HandleHttpResponse` — full NiFi has the pair) with the X
calls shaped like the existing posting flow, and a custom Python processor only if image resize can't
be avoided. The alternative — a small feed-cache endpoint in `cso-operator-app`'s backend — only wins
if the NiFi shape fights the image serving. Decide in Phase 2 planning, live flow dumped first, not now.

### 3. Where the feed comes from — the X API tier gates this

Write-scope OAuth 2.0 user tokens exist and work (the Streamers posting path). What I have NOT verified
is the current tier's ceiling for **reads** (`GET /2/users/:id/tweets`) and **likes**
(`POST /2/users/:id/likes`) — the free tier is write-heavy and nearly read-free. Phase 0 settles this
empirically with two curls against the real account, not with docs research.

Fallback that works even on the free tier: the pipeline already knows every post it publishes (the
published queue holds the tweet ids). Feed = own published posts from app data + sparing on-demand
metric lookups. Reading the timeline via API is the nicer path if the tier allows it.

## Phases

**Phase 0 — gates (cheap, do first):**
read the rear label for the exact size/SKU → pin the BSP + drivers; curl the reads/likes endpoints with
the live creds to learn the tier truth; flash the Waveshare BSP demo to prove display+touch on this V2
unit. Exit: panel lights up, touch registers, tier question answered with HTTP responses.

**Phase 1 — viewer MVP, no network:** LVGL card UI, swipe between ~10 canned posts bundled in LittleFS
(text + pre-scaled JPEGs), heart animates locally. Exit: it feels good in the hand — swipe latency and
card layout are the product here.

**Phase 2 — live feed:** backend leg built in its decided home; device fetches `/amoled/feed` on boot +
swipe-past-end refresh; images cached in PSRAM/LittleFS. Exit: a post I publish shows up on the panel
without a reflash.

**Phase 3 — actions:** tap heart → `POST /amoled/action` → X like lands (verify on x.com), optimistic
UI with revert on failure; unlike; repost/bookmark only if the tier is friendly.

**Phase 4 — coexistence + polish:** decide the EFM presence (embed a heartbeat task vs accept the
re-flash swap); AXP2101 battery pill in the status bar; display sleep on idle; doc + roster updates.

## Open decisions for Steven

1. **Exact SKU** (rear label size) — gates the BSP; everything in Phase 0 hangs on it.
2. **Firmware repo home** — new repo (e.g. `amoled-x-viewer` alongside the MicroFi fork) vs a folder in
   an existing one. I lean new repo; this shares no code with MicroFi.
3. **Which X account** — the Streamers posting account is what the creds cover today.
4. **Backend home** — NiFi PG (default, precedent) vs cso-operator-app endpoint; decided at Phase 2
   with the live flow dumped first.

## Done condition

Pick up the board: newest posts of the account are on the panel, swipe moves between them, tap-heart
lands a real like on X (visible on x.com), and the whole path — firmware repo, backend flow export,
this doc — is committed. When this ships, update `efm-waveshare-amoled.md` (device state + firmware
swap note) and this plan's phase table with the as-built deviations.
