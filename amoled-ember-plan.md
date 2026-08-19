# Ember — a Grok pocket instrument for the AMOLED

**Plan of record for [issue #184](https://github.com/cldr-steven-matison/DesktopShare/issues/184).**
Driving device: the #181 Waveshare ESP32-S3 Touch AMOLED V2 (`efm-waveshare-amoled.md`).
This is **not** the #183 X viewer. #183 is Claude's app (swipe my posts, tap to like).
Ember is Grok's: one coal of signal in the dark.

## State — on the glass, bounced on product, back to Grok (2026-08-19)

Ember runs as the ESP-Brookesia v0.8 **runtime JS package `tunastreet.ember`**
on the #188 platform image, a launcher tile next to the agent status tile and
the X viewer. Deployed with a `littlefs_data`-partition-only flash — the
platform image and the baked-in MicroFi agent were untouched, and heartbeats
stayed 200 through the session. Eyes-on: pulse, coal-tap refresh, channel
swipe all confirmed from the panel on first boot.

**Steven's verdict same evening: the mechanics pass, the product doesn't.**
Picking up the panel, you can't tell what the app is, what the coal means, or
why you'd tap it — and a text card you page through lands too close to the
X viewer beside it. The task is shipped back to Grok for the product
iteration; the rails below (runtime package, backend, deploy path) are proven
and stay.

- App package: [`steven-matison/amoled-x-ember`](https://github.com/steven-matison/amoled-x-ember)
  `apps/tunastreet.ember/` (JSON-UI + QuickJS, modeled line-for-line on
  `tunastreet.xviewer` — HTTP via the `Http` service with RequestAsync +
  events, no fetch/setTimeout in the sandbox).
- Backend: same repo `backend/` — Grok's original FastAPI tree from the
  2026-08-18 session, salvaged nearly intact. Runs on **WindowsDesktop
  `:8092`** (sibling of the X viewer's `:8091`): StarlinkAI left the
  192.168.1.x LAN, and the panel can only reach 192.168.1.121. `XAI_API_KEY`
  is sourced at launch from `tuna-starlink-app/backend/.env.local`, never
  copied into the tree. Windows Firewall rule `Allow Ember Port 8092`
  (the #52 per-port pattern).
- The failed C++ firmware story (7 black flashes, $51.96):
  [`amoled-ember-postmortem.md`](amoled-ember-postmortem.md). Its
  `firmware/` tree stays in the repo as the record; the runtime package
  replaced it entirely.

## Why this, not a feed

A 368×448 panel is a terrible timeline and a perfect instrument. The world
already has infinite scroll. What it does not have is a thing you pick up,
tap, and get *one* true thing — named, dated, opinionated — then put down.

Grok does all three on a live wire: **search the current moment** (web search
at forge time), **take a side** (never "it remains to be seen"), **paint the
moment** onto true-black AMOLED via Imagine, only when asked.

## What you hold

Four channels, three faces:

| Gesture | Does |
|---|---|
| Tap the coal | New pulse on this channel (`POST /ember/refresh`) |
| Swipe L / R (or the `«` `»` taps) | `WORLD` · `SCIENCE` · `SPACE` · `YOU` |
| Tap the text | cycle **NOW → WHY → TAKE** |
| Long-press the coal | **PAINT** — Imagine forges a 368×448 card (billable; opt-in); tap the card to put it away |
| Swipe up from bottom | **Brookesia home** (system; Ember does not steal it) |

The coal is cropped from Grok's own hero still, in three heat states —
`heat` from the pulse drives how bright it burns. `YOU` is the array
channel: a host-aware local snapshot (EFM server, sibling X viewer backend
on WindowsDesktop; Lemonade on StarlinkAI) interpreted by Grok, not a news
wire.

## LAN contract (device ↔ backend, `http://192.168.1.121:8092`)

- `GET  /ember/pulse?channel=world|science|space|you` → current pulse
  (backend caches 180 s per channel; forges anew past TTL)
- `POST /ember/refresh` `{"channel"}` → force a new pulse (coal tap)
- `POST /ember/paint` `{"id"}` → Imagine card, returns `art` URL
- `GET  /ember/art/<id>.jpg` → pre-scaled **368×448** JPEG

Pulse shape (device-sized on purpose):

```json
{
  "id": "…",
  "channel": "world",
  "now":  "≤120 chars, one sentence, specific",
  "why":  "≤180 chars, two sentences",
  "take": "≤140 chars, an actual opinion",
  "heat": 0.85,
  "ts":   "2026-08-19T19:55:59+00:00",
  "art":  null
}
```

The device never talks to api.x.ai — TLS to xAI, search tool-calls, and
Imagine bytes all stay on the backend.

## Deploy shape

Runtime package on littlefs, no per-app reflash: stage
`apps/tunastreet.ember/` into `waveshare-devices` →
`examples/system/super/littlefs/apps/`, rebuild, flash **only** the
`littlefs_data` partition (`0xaa1000`, COM8 Windows-side esptool). Re-stage
every app you want to keep — anything missing from the staging tree vanishes
on the next storage flash. Ask before every flash, fresh each session.

## Remaining

0. **Product redesign — Grok's court.** Make the thing legible in one glance
   and unmistakably not-a-viewer. Everything below is polish behind that.
1. **Shake = new pulse** — the QMI8658 is real hardware, but the JS sandbox
   has no IMU service today. Needs a platform-image service (native, #188
   overlay) before the gesture can exist; tap-the-coal is the v1 shake.
2. **Idle ember** — display sleep / dimmed idle state (AMOLED's whole point);
   pairs with #183's idle polish.
3. **Backend as a persistent service** — `run.sh` is a foreground uvicorn;
   decide whether it joins the X viewer backend's supervision story.
4. **Auto-paint stays off** — Imagine costs money; paint remains a deliberate
   long-press.

## Done condition

The 2026-08-19 build met the mechanical bar (tile on home, live pulse,
channel swipe, face cycle, paint, system swipe-up intact) — and that bar
turned out to be too low. The real done condition: pick up the board cold
and know within five seconds what the app is telling you and what touching
it will do, without it reading as another post viewer.
