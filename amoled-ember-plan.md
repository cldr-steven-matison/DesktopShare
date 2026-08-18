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
| Tap the text | cycle **NOW → WHY → TAKE** |
| Swipe up from bottom | **Brookesia home** (system; Ember does not steal it) |
| Long-press the coal | **PAINT** — Imagine forges a 368×448 card (billable; opt-in) |

Idle is almost all pixels off. One living ember at the bottom. Heat of the
current pulse drives how bright the coal burns. That is the whole product.

`YOU` is the array channel: StarlinkAI / Lemonade / the AMOLED agent itself —
Grok interpreting a live local snapshot, not a news wire.

## Architecture — same hard calls as #183, different payload

### 1. Brookesia app, not a replacement OS

Steven asked for an on-screen icon. Ember is a `systems::phone::App`
(`ESP_UTILS_REGISTER_PLUGIN_WITH_CONSTRUCTOR`) with a **112×112** launcher
tile (`img_app_ember`). Brookesia keeps the home grid, status bar, swipe-up-
to-home, and recents. Ember does not steal the vertical system gesture —
in-app, tap cycles NOW/WHY/TAKE and swipe L/R changes channel.

Still not a MicroFi processor (same 256-byte / no-display reasons as #183).
Still a flash — ESP32 has no sideload — but the image is **Brookesia + Ember**,
not Ember instead of Brookesia.

Two install shapes, both in [`amoled-x-ember`](https://github.com/steven-matison/amoled-x-ember) `firmware/`:

| Shape | What you get |
|---|---|
| Slim host (`firmware/main`) | Phone + Ember only. Default for the #181 1.8″ V2. |
| Drop-in (`firmware/components/ember`) | Copy into factory Brookesia; registry install puts the tile next to Settings / Calculator / AI Chat. |

Default SKU assumption: **1.8″ V2, 368×448, CO5300 + CST820**. Rear-label
size still unread. Flashing the slim host still darkens the `AMOLED` EFM
agent from #181 (`pio run -e amoled -t upload` puts it back). Dropping Ember
into factory Brookesia and flashing *that* image is how the rest of the
suite stays.

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

### 3. App home is `steven-matison/amoled-x-ember`. Spec stays in DesktopShare.

DesktopShare keeps the plan (`amoled-ember-plan.md` on `issue-184-amoled-ember`)
while we build and iterate. The runnable tree — backend, simulator, Brookesia
firmware — is [`steven-matison/amoled-x-ember`](https://github.com/steven-matison/amoled-x-ember)
(clone on StarlinkAI: `/home/tunas/amoled-x-ember`). Sibling of the #183
`amoled-x-viewer` repo. Keys are sourced at launch from
`tuna-starlink-app/backend/.env.local` (`XAI_API_KEY`); they are never copied
into the app tree.

## What runs tonight vs what flashes later

The board is on WindowsDesktop COM8, not on this Beelink. So the v1 deliverable
is split on purpose:

| Surface | Status |
|---|---|
| Backend on StarlinkAI `:8088` | live — Grok + optional Imagine |
| Pixel-true simulator (`368×448`) | live — same contract, same gestures |
| Brookesia app + slim phone host in `amoled-x-ember/firmware` | written, unflashed (no IDF on this host, board is elsewhere) |
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
3. **App repo** — [`steven-matison/amoled-x-ember`](https://github.com/steven-matison/amoled-x-ember).
   Spec stays in this file.

## Done condition

Pick up the board: Ember is a tile on the Brookesia home screen. Tap it,
shake for a live pulse, swipe L/R for channel, tap to cycle faces, swipe
up to go home. The panel spends most of its in-app life black. When this
ships, update `efm-waveshare-amoled.md` with whichever image is on the
board (slim host vs factory Brookesia + Ember).
