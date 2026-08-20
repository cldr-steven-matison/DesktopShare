# T-MINUS — launch clock for the AMOLED

**Plan of record for [issue #184](https://github.com/cldr-steven-matison/DesktopShare/issues/184), second chance.**
Driving device: the #181 Waveshare ESP32-S3 Touch AMOLED V2 (`efm-waveshare-amoled.md`).
This is **not** the #183 X viewer and **not** Ember. Ember was bounced 2026-08-19.

## What you hold

A 368×448 true-black launch clock. Name, ticking T-minus, vehicle, pad.

```
T-MINUS
FALCON 9
STARLINK 10-39
T- 04:12:44
SLC-40 · Cape Canaveral
```

| Gesture | Does |
|---|---|
| Tap the clock, or `»` | next upcoming launch |
| `«` | previous |
| Swipe L / R | same as `«` `»` if the JSON-UI gesture fires (taps are the guaranteed path) |
| Swipe up from bottom | **Brookesia home** (system; T-MINUS does not steal it) |

No feed. No posts. No coal. No NOW/WHY/TAKE. No Imagine. No Grok API.

## Rails

Runtime JS package `tunastreet.tminus` on the #188 Brookesia v0.8 image.
Backend on WindowsDesktop `:8092` (`http://192.168.1.121:8092`).
T-0 is Launch Library 2, polled every 15 min. No keys.
Flash is **littlefs_data only** (`0xaa1000`, COM8, MAC `1c:db:d4:7b:85:84`).
Never write `0x0`–`0xaa1000`. Ask before every flash. Always re-stage
`tunastreet.xviewer` on a storage rebuild; do **not** re-stage `tunastreet.ember`.

App repo: [`TunaStreetTest/amoled-tminus`](https://github.com/TunaStreetTest/amoled-tminus).
Package id is `tunastreet.tminus`.

## LAN contract

- `GET /tminus/now`
- `POST /tminus/step` `{"dir": 1|-1}`
- `GET /health`

```json
{
  "id": "ll2-id",
  "vehicle": "Falcon 9",
  "mission": "Starlink Group 10-39",
  "pad": "SLC-40 · Cape Canaveral",
  "t0_unix": 1755732300,
  "server_unix": 1755718000,
  "status": "Go",
  "idx": 1,
  "count": 8
}
```

The device counts down locally from `t0_unix`/`server_unix` with a 1 s
`SystemTimer`, and re-fetches `/tminus/now` every 60 s for slips/scrubs.
`Hold` shows `HOLD`. Past T-0 shows `T+` until LL2 drops the row.

## Out of v1

IMU shake, audio, Imagine, ISS/sky channel-swipe, platform overlay,
stopping the X viewer backend on `:8091`.

## Done

Pick up the board with a cold eye: it is obviously a launch countdown, tapping
it obviously goes to the next one, and it cannot be mistaken for the X viewer
beside it.
