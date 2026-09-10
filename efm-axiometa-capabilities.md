# AXIOMETA capabilities — AX22 modules as MicroFi processors

Companion to [efm-axiometa.md](efm-axiometa.md). This is the discovery pass #315 asks for: **each out-of-box AX22 capability mapped to a MicroFi processor**, ordered easiest→hardest by bus and dependency weight, so the build proceeds one earned slot at a time. Same shape as [efm-amoled-capabilities.md](efm-amoled-capabilities.md).

**Status: design.** Pin/bus assignments follow the `axiometa_genesis_mini` Arduino variant and the axiometa.io module pages (see [efm-axiometa.md](efm-axiometa.md) §1–2). Nothing built.

**Runtime, 2026-09-10:** the board now runs [EspiFi](efm-espifi.md) on MicroPython as class `AXIOMETA`, so each rung below is a Python `run(node, session)` function copied to the board with `mpremote fs cp`, not a C++ source and a reflash. The ground rules in the next section describe the MicroFi path and stay for a MicroFi build; the ladder order still applies.

## Ground rules for every AXIOMETA processor

- **C++, compile-time.** Add a `.cpp` to the [`cldr-steven-matison/MicroFi`](https://github.com/cldr-steven-matison/MicroFi) fork, register with `MICROFI_REGISTER_PROCESSOR`. No Python, no runtime load — adding a processor is a rebuild + reflash.
- **Gate behind a compile define.** Wrap each source in `MICROFI_BOARD_AXIOMETA_<PERIPHERAL>` so it compiles to an empty translation unit on boards that lack it (the XIAO / AMOLED builds must stay green — regression-build every existing env when adding a source).
- **Title-Case MiNiFi-C++-compatible property names**, so an EFM flow def written against MiNiFi C++ resolves unchanged (the design bet MicroFi is built on).
- **≤4-node flows.** `kMaxFlowNodes=4` silently drops extra nodes — design each demo flow within that cap.
- **Re-pin the manifest** after each new processor, and confirm real data movement with an **independent** check (subscriber / HTTP), never the firmware's own serial log.

## Already available (reuse — no new code)

`GenerateFlowFile`, `LogAttribute`, `UpdateAttribute`, `PublishMQTT`, `ListenHTTP`, `PublishSparkplug`, `GetGPIO`, `SetGPIO`, `DisplayMessage` — shipped and hardware-verified on the XIAO / AMOLED lines. These give AXIOMETA a working round-trip (`Get… → PublishMQTT`) on day one, before any AX22-specific processor exists.

## The ladder (easiest → hardest)

Ordered by how much the processor has to own: an ADC read or a single GPIO is nearly free; anything driving a timed protocol (NeoPixel, IR, SPI display) is heavier and later.

### 1. `ReadAnalog` — LDR light sensor (ADC) · **start here**
Lightest possible sense: one ADC channel, no bus, no timing. Properties: **ADC Channel** / **Read Interval** (and optional **Samples** for averaging). Emits one FlowFile per read, value as content and/or a Title-Case attribute. Relationship: **success**. Proof-of-life: `ReadAnalog → PublishMQTT` → an independent `mosquitto_sub` sees the light level. This is AXIOMETA's real ingress equivalent of the XIAO `GetGPIO` first-light test.

### 2. Button + LED via existing `GetGPIO` / `SetGPIO` — **no new code**
The LED tactile button is one GPIO in (button) and one GPIO out (LED), both already covered. Flow: `GetGPIO(button) → …`, and `ListenHTTP → SetGPIO(LED)` for a remote-controlled light. Use this to prove the AX22 pin mapping (`P[PORT]_IO[PIN]`) before writing anything new.

### 3. `GetTempHumidity` — DHT11 (1-wire over GPIO)
First genuinely new processor. A DHT11 is a bit-banged single-wire read with tight timing (µs-level), but self-contained — no shared bus. Properties: **GPIO Pin** / **Read Interval**. Emits temp + humidity (JSON content, or two attributes). Relationship: **success**, **failure** (checksum). The archetype "real sensor telemetry into EFM/Kafka."

### 4. `GetEncoder` — rotary encoder (GPIO A/B/SW)
Quadrature decode on two GPIOs + a switch line. Best as an interrupt/PCNT-backed counter read on trigger (ESP32 has a hardware pulse counter — prefer it over bit-bang to avoid missed steps). Properties: **Pin A** / **Pin B** / **Switch Pin** / **Read Interval**. Emits delta or absolute position. Watch the cross-task rule: an ISR/PCNT updates a counter, `on_trigger` reads it — never touch `Session`/`Queue` from the ISR (same bridge shape `ListenHTTP` uses).

### 5. `PlayTone` — passive buzzer (PWM / LEDC)
Egress, not ingress. Drives an LEDC channel at a frequency for a duration. Properties: **GPIO Pin** / **Frequency** / **Duration** (from FlowFile content/attributes for a data-driven tone). Relationship: **success**. Turns an inbound event into an audible alert — pairs with `ListenHTTP → PlayTone`.

### 6. `SetNeoPixel` / `DisplayMatrix` — 5×5 NeoPixel matrix (RMT single-wire)
WS2812-style timed protocol — use the ESP32 **RMT** peripheral (not bit-bang). Properties: **GPIO Pin** / **LED Count** / and a content contract for the frame (per-pixel RGB, or a named pattern). Relationship: **success**. A visible EFM-driven status display; heavier because it owns RMT timing and a frame buffer in PSRAM.

### 7. `SendIR` / `ReceiveIR` — IR transceiver (RMT carrier)
Two directions, both on RMT with a 38 kHz carrier. `SendIR`: transmit a code (NEC/RC5) carried in the FlowFile. `ReceiveIR`: RMT-RX capture → decode → emit a code as a FlowFile (an ingress source that turns a physical remote into edge data). Heaviest of the sense set — carrier timing + protocol decode. Defer unless a demo needs IR specifically.

### 8. `DisplayMessage` (adapt) — 0.96" IPS LCD (SPI)
The AMOLED line already has a `DisplayMessage`; adapt it to this panel's controller — **ST7735S**, 160×80 SPI (AX22-0034). Bring the panel up minimally first (light it, one string) before wiring it into a processor. Properties: **Message** (+ optional **Line** / **Color**). Egress sink for text/status from a flow.

## Suggested build order

`ReadAnalog` → (button/LED via existing GPIO) → `GetTempHumidity` → `GetEncoder` → `PlayTone` → `SetNeoPixel` → `SendIR`/`ReceiveIR` → `DisplayMessage`. The first three deliver "real ingress + real egress + a real sensor into Kafka" — the meaningful milestone — with the ADC read and DHT11 being the two that most justify their manifest slot. Steven picks which capability "earns its slot first" if the order should change; the compile-define gating means slots can be swapped per build without disturbing other boards.

## What does NOT port

- **No Python / MicroPython processor** — the ESP32 has no room for CPython and MicroFi's static-registry model defeats the "push a script without reflashing" point anyway (full reasoning in [efm-xiao-microfi.md](efm-xiao-microfi.md) §"Can the XIAO run custom Python processors?"). AX22 logic is C++.
- **No `RouteOnAttribute`** without a predicate evaluator MicroFi's runtime doesn't have — deferred on the XIAO for the same reason.
- Watch flash headroom: firmware was ~1.1 MB (~52% of an 8 MB app slot) with 6 processors on the XIAO; the full AX22 set is more sources, so track `.pio/build/<env>/firmware.bin` size and trim (TLS/OTA) if it approaches the slot.
