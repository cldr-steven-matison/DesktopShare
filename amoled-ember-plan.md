# Ember — a Grok pocket instrument for the AMOLED

**Plan for [issue #184](https://github.com/cldr-steven-matison/DesktopShare/issues/184).**
Driving device: the #181 Waveshare ESP32-S3 Touch AMOLED V2 (`efm-waveshare-amoled.md`).
This is **not** the #183 X viewer. #183 is Claude's app (swipe my posts, tap to like).
Ember is Grok's: one coal of signal in the dark.

## Why this, not a feed

A 368×448 panel is a terrible timeline and a perfect instrument. The world
already has infinite scroll. What it does not have is a thing you pick up, shake,
and get *one* true thing — named, dated, opinionated — then put down.

Grok is the only model in this array that can do all three on a live wire:

1. **Search the current moment** (web search tool, not a cached briefing).
2. **Take a side** (not "it remains to be seen").
3. **Paint the moment** onto true-black AMOLED via Imagine, only when asked.

The X viewer consumes Steven's own posts. Ember consumes the universe and
compresses it until it fits in a matchbox.

## What you hold

Four channels, three faces, two gestures that matter:

| Gesture | Does |
|---|---|
| Shake (IMU) or tap the coal | New pulse on this channel |
| Swipe L / R | `WORLD` · `SCIENCE` · `SPACE` · `YOU` |
| Swipe up | **WHY** — why a sharp person cares in the next 24h |
| Swipe down | **TAKE** — Grok's actual opinion |
| Long-press the coal | **PAINT** — Imagine forges a 368×448 card (billable; opt-in) |

Idle is almost all pixels off. One living ember at the bottom. Heat of the
current pulse drives how bright the coal burns. That is the whole product.

`YOU` is the array channel: StarlinkAI / Lemonade / the AMOLED agent itself —
Grok interpreting a live local snapshot, not a news wire.

## Architecture — same hard calls as #183, different payload

### 1. Dedicated app firmware, not a MicroFi processor

Same reasons as `amoled-x-viewer-plan.md`: 256-byte FlowFile ceiling, no display
stack, every UI tweak would be a firmware rebuild anyway. Ember is a standalone
**ESP-IDF + LVGL v9** app on the Waveshare BSP
(`waveshare/esp32_s3_touch_amoled_1_8` ^2.0.3). Default SKU assumption: **1.8″
V2, 368×448, CO5300 + CST820**. Rear-label size still unread on #181 — if it's
a different size, only the BSP + resolution change.

While Ember is flashed, the `AMOLED` EFM agent from #181 is dark. Expected.
`pio run -e amoled -t upload` puts the agent back. No heartbeat-embed in v1.

### 2. The device never talks to api.x.ai

TLS to xAI, search tool-calls, Imagine bytes, and JSON bigger than a pulse do
not belong on the panel. A backend on **StarlinkAI** does the Grok work and
serves a dumb LAN contract:

- `GET  /ember/pulse?channel=world|science|space|you` → current pulse
- `POST /ember/refresh` `{"channel"}` → force a new pulse (shake)
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
  "heat": 0.15,
  "ts":   "2026-08-18T16:45:00Z",
  "art":  null
}
```

### 3. App home is `~/ember` on StarlinkAI, not DesktopShare

DesktopShare stays docs. The runnable app — backend, AMOLED simulator, firmware
— lives at `/home/tunas/ember`. Keys are sourced at launch from
`tuna-starlink-app/backend/.env.local` (`XAI_API_KEY`); they are never copied
into the Ember tree.

## What runs tonight vs what flashes later

The board is on WindowsDesktop COM8, not on this Beelink. So the v1 deliverable
is split on purpose:

| Surface | Status |
|---|---|
| Backend on StarlinkAI `:8088` | live — Grok + optional Imagine |
| Pixel-true simulator (`368×448`) | live — same contract, same gestures |
| ESP-IDF firmware in `~/ember/firmware` | written, unflashed (no IDF on this host, board is elsewhere) |
| Flash + IMU bring-up | WindowsDesktop follow-up, once SKU is read off the rear label |

The simulator is not a cop-out. It is the same product at the same resolution,
so we can iterate the feel before burning a flash.

## Phases

**Phase 0 — this session.** Backend + simulator + firmware source + this doc.
Exit: open the simulator, shake, get a live Grok pulse.

**Phase 1 — flash.** WindowsDesktop installs IDF 5.5, sets Wi-Fi +
`CONFIG_EMBER_BACKEND_URL`, flashes COM8. Exit: the physical panel shows the
same pulse the simulator did.

**Phase 2 — IMU + power.** QMI8658 shake instead of BOOT; AXP2101 battery
pill; display sleep on idle (AMOLED's whole point).

**Phase 3 — paint on-device.** Long-press downloads the 368×448 JPEG into
PSRAM and sets it as the card background.

## Open decisions

1. **Exact SKU** — still unread. Default 1.8″ V2.
2. **Auto-paint** — off. Imagine is ~$0.02–0.05/image; paint is a deliberate
   long-press, not a side effect of shake.
3. **Firmware repo** — `~/ember` for now. Promote to its own GitHub repo if
   this survives a week in the hand.

## Done condition

Pick up the board (or the simulator tonight): shake gives a new live pulse,
swipe L/R changes channel, swipe up/down changes face, long-press paints.
The panel spends most of its life black. When this ships to the physical
board, update `efm-waveshare-amoled.md` with the firmware-swap note (same
sentence #183 will need).
