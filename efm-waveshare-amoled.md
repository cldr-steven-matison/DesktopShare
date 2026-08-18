# EFM agent AMOLED — Waveshare ESP32-S3 Touch AMOLED

**Status: agent live in EFM 2026-08-18 — [issue #181](https://github.com/cldr-steven-matison/DesktopShare/issues/181).**
A fourth MicroFi-firmware device joined the array: a Waveshare ESP32-S3 Touch AMOLED board,
running the unified MicroFi image as EFM agent class `AMOLED`. This doc is the device's
golden source — hardware facts, firmware env, and EFM state. The XIAO units' doc
(`efm-xiao-microfi-1-2-3.md`) stays the roster for MicroFi-1/2/3; this board gets its own
because it's a different hardware family with a display track ahead of it.

## Device facts (esptool-verified 2026-08-18)

| Fact | Value |
|---|---|
| Board | Waveshare ESP32-S3 Touch AMOLED, **revision V2** (Steven, 2026-08-18) — **size/SKU still unread**. If it's the 1.8″ (the model #181 calls out with a V1→V2 transition), V2 means the CO5300 display driver, not the V1 SH8601 |
| Chip | ESP32-S3 (QFN56) rev v0.2, USB-Serial/JTAG mode |
| PSRAM | 8MB embedded octal (`Embedded PSRAM 8MB (AP_3v3)`) |
| Flash | 16MB quad (JEDEC mfr `0x20` dev `0x4018`, eFuse "quad (4 data lines)", 3.3V) |
| MAC | `1c:db:d4:7b:85:84` |
| COM port | COM8 this session (`VID_303A&PID_1001`, MAC as SER — Windows may renumber on replug, re-identify by MAC) |
| EFM agent id | `microfi-1cdbd47b8584` (MAC-derived, blank `CONFIG_MICROFI_AGENT_ID`) |
| Agent class | `AMOLED` |
| IP | 192.168.1.202 |

Same identification commands as the XIAOs (native Windows, no WSL passthrough):

```bash
python -m serial.tools.list_ports -v          # MAC rides in SER= without resetting the device
python -m esptool --port COM8 flash-id        # chip, PSRAM, flash JEDEC -- this DOES reset it
```

## Firmware — `amoled` env in the MicroFi fork

Branch `feature/amoled-agent` (off the `feature/agent-liveness-led` stack tip) in
`C:\Users\tunas\MicroFi`. The board's memory shape (16MB flash + 8MB octal PSRAM) matches the
primary `esp32s3` env's Lonely Binary N16R8 target, so the new env extends it and rides the
existing `partitions.csv` (2×2MB OTA slots + ~11.5MB LittleFS — no new partition table):

- `[env:amoled]` in `platformio.ini` — `extends = env:esp32s3`, defaults chain
  `sdkconfig.defaults;sdkconfig.defaults.local;sdkconfig.defaults.amoled`.
- `sdkconfig.defaults.amoled` — `CONFIG_MICROFI_AGENT_CLASS="AMOLED"`, blank agent id,
  `CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y` (ESP-IDF defaults to 2MB when unset), the three octal
  PSRAM lines from the 8mb overlay, and `CONFIG_MICROFI_LIVENESS_LED=n`.
- **Liveness LED is off on this board on purpose.** The #171 strobe defaults to GPIO21 —
  safe on the XIAO (user LED), unverified on the Waveshare family where GPIO21's wiring is
  model-dependent. Re-enable with a schematic-verified pin once the SKU is known.

Build + flash (image 58.9% of the 2MB app slot, identical registry to the XIAO builds):

```bash
pio run -e amoled -t upload --upload-port COM8   # MAC-verify the port first
```

### The build gap this env exposed — `liveness_led.cpp` vs `MICROFI_LIVENESS_LED=n`

Symptom: first `amoled` build failed with
`error: 'CONFIG_MICROFI_LIVENESS_LED_GPIO' was not declared in this scope`.
Diagnosis: this was the first env ever built with the strobe disabled — `liveness_led_start()`
was `#if`-guarded but `strobe_task` above it compiled unconditionally, and the
`MICROFI_LIVENESS_LED_*` pin/period symbols only exist in sdkconfig when the bool is on
(they sit inside Kconfig's `if MICROFI_LIVENESS_LED`). Fix: the anonymous-namespace task body
in `src/liveness_led.cpp` is now gated with the same `#if CONFIG_MICROFI_LIVENESS_LED`,
in the same commit as the env.

## EFM state

No deployer command — MicroFi class + id are compile-time, EFM auto-created `AMOLED` on the
first heartbeat (registered 2026-08-18 20:06 UTC). The manifest content-hash-deduped onto the
existing 9-processor build manifest — `AMOLED` and `MicroFi-3` both carry
`9c1cb1b3-2a3b-4ad4-87b7-f91dbb1dec91`. Designer palette pinned and read back:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"agentClassName":"AMOLED","agentManifestId":"9c1cb1b3-2a3b-4ad4-87b7-f91dbb1dec91"}' \
  http://192.168.1.121:10090/efm/api/agent-class-manifest-config
curl http://192.168.1.121:10090/efm/api/agent-class-manifest-config/AMOLED
```

Liveness ground truth (no list-agents REST endpoint — `efm-operations-manual.md` rules apply):

```bash
kubectl exec -n cld-streaming <ssb-postgresql-pod> -- psql -U postgres -d efm -c \
  "SELECT id, agent_class, agent_state, last_seen FROM agent WHERE agent_class = 'AMOLED';"
# microfi-1cdbd47b8584 | AMOLED | ONLINE | 2026-08-18 20:06:10.991
```

No flow is published to the class yet — the agent heartbeats with the empty class flow.

## Open items

- **Exact model size** — revision is V2 (confirmed); the size is what's left to read off the
  rear label. Together they decide the display driver (CO5300 on the 1.8″ V2), touch IC
  (CST820/FT3168/CST9217), resolution, and which GPIO is safe for the liveness LED.
- **Display track** — the AMOLED panel is the whole point of this board; MicroFi has no display
  processor yet. That's a new-processor track like `CaptureImage`/`PublishSparkplug` were,
  sized against the ~0.9MB app-slot headroom.
- **Serial boot log not captured this session** — WSL→Windows interop died mid-session
  (`UtilAcceptVsock:271: accept4 failed 110` on every Windows exe after the flash), so the
  boot capture never ran. Liveness is proven one rung down the precedence order (Postgres
  `agent_state=ONLINE` + esptool flash hash verification). Capture script staged at
  `C:\Users\tunas\AppData\Local\Temp\amoled_serial.py` (DTR/RTS-safe open, per
  `efm-xiao-microfi-1-2-3.md`).
- ~~MicroFi-3 went MISSING 2026-08-18 19:52~~ **Resolved same evening**: its USB cable had
  been borrowed for the AMOLED board; replugged on another cable and back ONLINE at 20:30 UTC
  (Postgres-verified). Sparkplug B emit restored.
