# AXIOMETA — introducing an ESP32-S3 board to the device array as an EFM agent

**Status: research effort (Phase 0), 2026-09-08 — [issue #315](https://github.com/cldr-steven-matison/DesktopShare/issues/315) (`device:StarlinkAI`).** The board is **not yet plugged in.** This doc is the golden source for bringing it up; the peripheral-inventory table and the chip/flash pins are filled at inspection (Phase 1) once it's connected to StarlinkAI. Nothing here has been run on hardware yet.

AXIOMETA ([github.com/axiometa](https://github.com/axiometa), [axiometa.io](https://www.axiometa.io/pages/genesis-getting-started)) is a **modular ESP32-S3 prototyping platform — not a Linux SBC.** That single fact settles the integration shape: it is the same silicon the array has already onboarded twice — the XIAO ESP32-S3 boards ([efm-xiao-microfi.md](efm-xiao-microfi.md), [efm-xiao-microfi-1-2-3.md](efm-xiao-microfi-1-2-3.md)) and the Waveshare AMOLED boards ([efm-waveshare-amoled.md](efm-waveshare-amoled.md)). So AXIOMETA joins the same proven way: as a **MicroFi agent** (the clean-room MiNiFi C2 firmware for ESP32) under a new **`AXIOMETA` EFM agent class**, with each board capability exposed as a compile-time C++ processor. That is exactly what #315 asks for ("EFM Agent install as AXIOMETA class with Apache MiNiFi Flow and custom processors for all of the different out of the box capabilities"). The per-capability processor ladder lives in [efm-axiometa-capabilities.md](efm-axiometa-capabilities.md).

## What AXIOMETA Genesis is (external research)

Axiometa (Lithuania) makes the **Genesis IoT Discovery Lab** — a wire-free ESP32-S3 platform where modules plug into standardized **AX22** ports instead of a breadboard. Product line: **Genesis One** (8 AX22 ports), **Genesis Mini** (4 ports), sold as bare boards and as Starter/Extension kits. Which physical unit lands on StarlinkAI is confirmed at inspection.

### Board (Genesis One — the 8-port variant)

| | |
|---|---|
| SoC / module | `ESP32-S3-N8R2`, `ESP32-S3-WROOM-1` — dual-core Tensilica LX7 @ 240 MHz (vector ext for AI/ML), WiFi 4 + BLE 5, PCB antenna |
| Flash / PSRAM | **8 MB flash, 2 MB PSRAM** (the `N8R2` suffix) |
| Power | USB-C (power / programming / single-cell LiPo-Li-Ion charging), `TPS63001` buck-boost (1.8–5.5 V in → 3.3 V, 1.8 A), short-circuit + ESD protection |
| Expansion | **8 × AX22 ports** + 1 × STEMMA QT / Qwiic (Adafruit / SparkFun compatible) |
| Board | 55 × 103 mm, 4-layer, 4 mounting holes |

> **Contrast with the XIAO** (the closest array precedent): the XIAO ESP32-S3 **Sense** is `N8R8` (8 MB PSRAM) with an onboard camera + microSD; Genesis is `N8R2` (**2 MB** PSRAM), WROOM-1, **no camera**. Flash size matches (8 MB), so the mature `partitions_8mb.csv` layout applies — but the board JSON and PSRAM config differ, so AXIOMETA needs its **own** PlatformIO board env (see "Firmware" below). Don't assume the XIAO's `seeed_xiao_esp32s3` board JSON.

### AX22 connector standard

A universal keyed port carrying **I²C / SPI / UART / GPIO / analog** — modules "lock in place" for a reliable connection, no wiring. Board aggregate across the 8 ports: **12-bit ADC (up to 20 channels), 31 PWM, 45 GPIO, 15 touch**. Arduino pin naming is `P[PORT]_IO[PIN]` (e.g. `P7_IO0`). **60+ AX22 modules** exist (sensors BME280 / VL53L0X / MPU6050, buttons, switches, LEDs, buzzers, motor drivers, displays, relays, NeoPixel matrices).

### Starter-Kit modules — the "in the box" peripherals #315 asks to report

The Genesis Mini Starter Kit ships these AX22 modules (finalize against the actual box at inspection):

| Module | Interface (expected) | Note |
|---|---|---|
| DHT11 temperature + humidity | 1-wire over GPIO | |
| 0.96" IPS LCD | SPI | |
| LED tactile button | GPIO in + GPIO out (LED) | |
| Rotary encoder | GPIO (A / B / switch) | |
| 5×5 LED matrix (NeoPixel) | RMT / single-wire GPIO | |
| Passive buzzer | PWM (LEDC) | |
| Light sensor (LDR) | analog / ADC | |
| IR transceiver (remote) | RMT (carrier) | |

### Programming paths

Arduino IDE (Espressif ESP32 core; board "Axiometa GENESIS One / Mini"), **MicroPython**, **CircuitPython**, **MicroBlocks**, and **Axiometa Studio** (browser: describe a project → it generates ESP32 firmware and flashes a live device). The Axiometa GitHub org itself holds mostly the BrodBoost breadboard-PSU hardware designs — no firmware/SDK repo relevant to EFM.

For **our** purpose the path is none of the above by default: it's **MicroFi (ESP-IDF / PlatformIO)**, because that is what makes the board a first-class EFM agent rather than a hand-flashed device (see decision below).

## The onboarding decision: MicroFi, not a hand-written sketch

Three candidate paths, same conclusion the XIAO evaluation reached:

1. **MicroFi (recommended, and what #315 describes).** The board registers in EFM under class `AXIOMETA`, appears next to `StarlinkAI` / `AMOLED` / `MicroFi`, and takes its flow pushed from the EFM Designer. Capabilities are C++ processors compiled into a static registry. This is the established array pattern with two prior real deployments.
2. **Hand-written Arduino/ESP-IDF sketch → MQTT.** Simpler for a one-off telemetry demo, but the device stays invisible to EFM (Mosquitto only sees a client) and every change is a reflash. Fallback only.
3. **Axiometa Studio.** Fast for novel senses / demos, but produces a standalone sketch, not an EFM agent. Interesting for Phase 5 experimentation, not the onboarding path.

MicroFi it is. The rest of this doc is the MicroFi bring-up.

## How MicroFi enrollment works (confirmed on the XIAO / AMOLED boards)

- **MicroFi** — [`cldr-steven-matison/MicroFi`](https://github.com/cldr-steven-matison/MicroFi) (public fork of upstream [`Christopheraburns/MicroFi`](https://github.com/Christopheraburns/MicroFi)) — is a clean-room reimplementation of the MiNiFi C2 contracts (FlowFile semantics, heartbeat/ack), **not** a fork of `nifi-minifi-cpp` (too heavy: ~3.2 MB binary, ~5 MB RAM). Processors are **compile-time-embedded C++** resolved by name against a static registry; there is **no dynamic plugin load and no Python** on the device.
- **Enrollment needs no deployer step.** `CONFIG_MICROFI_AGENT_CLASS` (set to `AXIOMETA`) and a blank `CONFIG_MICROFI_AGENT_ID` (→ MAC-derived `microfi-<mac>`) are baked into `sdkconfig` before first boot. **EFM auto-creates the class on the first heartbeat** — different from the C++/Java MiNiFi path, which uses the deployer.
- **First heartbeat carries the full manifest inline** (processor list + property descriptors, ~3.8 KB); later heartbeats send only the manifest hash.
- **Ack.** The `feature/c2-ack` firmware line POSTs an explicit `/acknowledge` after each `UPDATE/configuration` apply (`FULLY_APPLIED` → EFM `DONE`), which cleared the old stale-`FAILED`-operation problem the implicit-ack builds had. Use a c2-ack build.
- **Designer palette pin.** After the manifest exists, pin the class to it: `POST /efm/api/agent-class-manifest-config` `{"agentClassName":"AXIOMETA","agentManifestId":"<id>"}` (`PUT`, or `DELETE`+`POST`, if a mapping already exists). Re-pin after **every** manifest change (new processor), or the Designer palette won't offer the new type.
- **`kMaxFlowNodes = 4`** — a MicroFi class flow silently drops nodes past 4 (only a `WARN`). Design AXIOMETA flows in ≤4-node chunks.

Full REST mechanics and the dozen numbered gotchas: `skills/nifi-and-ai/references/minifi-efm.md` (read before building the class flow). Class-migration / flow-port mechanics: [efm-xiao-microfi-1-2-3.md](efm-xiao-microfi-1-2-3.md) §"EFM class mechanics".

## Firmware (PlatformIO env AXIOMETA needs)

- Base off the 8 MB layout: **`partitions_8mb.csv`** (OTA-preserving, ~3.9 MB LittleFS) + an `esp32s3-8mb`-style base (`CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y` — ESP-IDF defaults to 2 MB when unset and PlatformIO only *warns* on the mismatch, it never reads the chip).
- **New `axiometa` env + board JSON** — Genesis is WROOM-1 / `N8R2`, not `seeed_xiao_esp32s3`. Set PSRAM to **2 MB** (quad, not the XIAO's 8 MB octal) and no-camera. Per-device overlay `sdkconfig.defaults.axiometa` setting only `CONFIG_MICROFI_AGENT_CLASS="AXIOMETA"` and a blank agent id. Overlays must live in the `sdkconfig.defaults.*` namespace (a file named `sdkconfig.<env>` gets clobbered and disables the whole defaults chain).
- WiFi creds + C2 URL go in the **untracked** `sdkconfig.defaults.local` (gitignored — holds the passphrase; entered directly on the Windows host, never through chat).

## Network path on StarlinkAI (reuse the AMOLED C2 relay)

The board joins WiFi on StarlinkAI's Starlink LAN (`192.168.1.x`), which **cannot reach EFM's ATT LAN** (`192.168.1.121:10090`). StarlinkAI already runs the **EFM C2 relay** `~/amoled-agent/efm_relay.py` on `:10090` (see the StarlinkAI block in [CLAUDE-CHECKIN.md](CLAUDE-CHECKIN.md)) — it forwards heartbeats/acks to EFM over Tailscale (`100.68.113.126:10090`) and rewrites EFM's tailnet IP → the relay's own LAN IP in responses so the board's flow-fetch/ack calls route back through it. **AXIOMETA points its C2 URL at the relay (`192.168.1.245:10090`)**, exactly like the Tuna Starlink AMOLED board — no new infrastructure. Each service port needs its own Windows Firewall inbound rule (`tsl-firewall.bat`). Confirm topology at inspection: if the board instead lands LAN-direct on an EFM-reachable host, skip the relay.

Do **not** trust EFM's own `lastSeen` for liveness of a relayed device — EFM freezes it for a healthy agent; the relay stamps `/tmp/amoled_last_hb` on every heartbeat and the monitor derives ONLINE/STALE from that.

## Bring-up phases (post-plug-in)

1. **Inspect.** Windows host, native (the board is a COM port; WSL2 has no USB passthrough). `esptool --port <COM> chip-id` + `flash-id` (pin S3 / PSRAM / JEDEC flash before any assumption). Visually inventory every AX22 module connected and every one still in the box; finalize the tables above. Verify by MAC (`esptool read-mac`) if other ESP32 units are attached.
2. **Firmware bring-up.** Build the `axiometa` env, flash + monitor in one `pio run -t upload -t monitor`, capture the first-heartbeat log verbatim (`heartbeat #0 -> 200`).
3. **EFM registration.** Confirm class `AXIOMETA` auto-created (`GET /efm/api/agent-classes`), manifest = exactly the compiled processors, agent `microfi-<mac>` ONLINE (check EFM Postgres `agent_state`, not just the UI). **Verify `AMOLED` / `StarlinkAI` / `MicroFi` are untouched.** Pin the Designer palette.
4. **Custom processors.** Build the [efm-axiometa-capabilities.md](efm-axiometa-capabilities.md) ladder one at a time, each its own `device:StarlinkAI` sub-task, with an independent confirmation of real data movement per processor.
5. **Out of the box (the issue's "think out of the box").** Candidates to weigh, not build speculatively: (a) the 60+-module AX22 ecosystem as a rapid **EFM-edge sensor-kit demo**; (b) **Axiometa Studio** as a fast path to novel senses vs. hand-written C++ processors; (c) **Sparkplug B emit** (`PublishSparkplug`) → Kafka, matching MicroFi-3; (d) an **AXIOMETA tile** on the AMOLED agent-monitor.

## Hard rules

- **Distinct class only.** Register as `AXIOMETA` — never under `StarlinkAI` / `AMOLED` / `MicroFi`; an EFM push aimed at one agent lands on the whole class.
- **Flash from Windows**, not WSL2. Verify the unit by MAC before flashing when others are attached.
- **Never commit `sdkconfig.defaults.local`** (WiFi passphrase). Keep it gitignored.
- MicroFi needs no deployer command — but the general EFM rule stands: never hand-build an agent-deployer command or reuse an `agentIdentifier` for a C++/Java install (`agent/incident-rules.md`).
- **Publishing a flow to a class is a live push to every agent in it** — confirm first, same as any redeploy; dump the live state before editing.
- **Never push to `Christopheraburns/MicroFi` upstream** — work lands on the `cldr-steven-matison/MicroFi` fork; anything for upstream is a PR.
- Issue artifacts under `files/issue-315/`; verification screenshots in the #315 comment as raw GitHub URLs; link every file named. **Never close #315** — stop at `status:review`.
