# Plan: MicroFi-1/2/3 — three XIAO devices, three processor-constrained test tracks

**Status: planning only, filed for review — [issue #134](https://github.com/cldr-steven-matison/DesktopShare/issues/134).** No EFM classes created, no firmware flashed, no devices touched yet.

Steven now owns 3 physical Seeed XIAO ESP32-S3 units (1 existing + 2 new) and wants each
assigned its own EFM MicroFi class (`MicroFi-1`/`MicroFi-2`/`MicroFi-3`) with a distinct test
focus, since MicroFi's compile-time, processor-count-limited architecture makes each device
realistically its own small research track rather than one flow reused three ways.

## Proposed device roster

- **`MicroFi-1`** (existing unit) → repurposed as the permanent **Sparkplug Sensor Emit** device
- **`MicroFi-2`** (new unit) → **Camera/Mic**
- **`MicroFi-3`** (new unit) → **Inbound Trigger Events** (LED control, action-dispatch,
  custom-processor home)

## What's already known — read this before touching anything

Rolled up from `efm-xiao.md`, `efm-xiao-microfi.md`, `efm-sparkplug-b-hardware-lab-plan.md`,
and a live EFM check of the current `MicroFi` class canvas done for this plan (not from docs
alone). A future session should be able to read only this section and not re-derive any of it.

- **One physical XIAO exists today**: ESP32-S3 **Sense** (camera+mic+SD), MAC
  `e0:72:a1:fb:fd:04`, **real flash is 2MB** (docs assumed 8MB/4MB twice before a live flash
  warning corrected it — the 2 new units could hit the same trap if they're a different SKU;
  verify chip/flash before assuming parity). Currently physically on WindowsDesktop; originally
  built/flashed from StarlinkAI. PlatformIO must run on **native Windows**, not WSL2 (no USB
  passthrough) — `usbipd-win` per-boot attach is a workaround only for serial-monitor access.
- **Live EFM state, confirmed via `GET /efm/api/designer/...` this session**: class `MicroFi`,
  agent `microfi_1`. Canvas has `GenerateFlowFile-XiaoTelemetry --success--> PublishMQTT-XiaoTelemetry`
  (real loop to `mqtt://192.168.1.121:1883`, topic `test/sensor/data`) plus an **unconnected**
  `ListenHTTP-Trigger` (`:8095`, base path `/test`) parked on the canvas.
- **MicroFi's real processor registry (6 shipped, field-verified in this order):**
  `GenerateFlowFile`, `LogAttribute`, `PublishMQTT` (minimal props, no TLS), `UpdateAttribute`
  (4 literal slots, not true dynamic properties), `ListenHTTP` (fire-and-forget only, no
  request/response pairing), `GetGPIO` (read-only, onboard BOOT/GPIO0 pin only).
  `RouteOnAttribute` is **explicitly deferred** — MicroFi has no Expression Language engine at
  all.
- **Sparkplug B was NOT done through MicroFi.** It's a separate, mutually-exclusive Arduino/
  PlatformIO sketch (`EmbeddedSparkplugNode` + `nanopb`, real NBIRTH/NDATA verified decoding
  correctly in NiFi's `ConsumeMQTTIIoT` → Kafka). **The physical unit can only run one firmware
  image at a time** — MicroFi-flow-based and the Arduino-Sparkplug sketch overwrite each other.
  This is the single most important nuance for "MicroFi-1 does sparkplug" — a native MicroFi
  `PublishSparkplug` processor (wrapping the already-proven library) is the real option to make
  this a first-class EFM-pushed flow instead of a separate hand-flashed sketch.
- **Hard architectural ceilings, apply to every future device:**
  - No Python/scripting/EL, ever — compile-time static processor registry, not `dlopen`. Adding
    any capability is a firmware rebuild + reflash, full stop.
  - `kMaxFlowNodes=4` — a silent-drop cap on total processors per flow graph (only a WARN log,
    hit once for real, poorly cross-referenced in its own source doc).
  - `Session::transfer()` matches the **first** relationship binding and returns — a
    one-relationship, two-consumer fan-out silently starves the second consumer. Design flows
    with one downstream consumer per relationship.
  - Flash headroom is real and shrinking: device 1's 2MB app slot is at ~97% with 6 processors
    built in. A 7th (e.g. a native Sparkplug processor) may not fit without trimming others out
    of that image.
  - MicroFi never POSTs `/acknowledge` (implicit-ack design) — every EFM `operation` row for it
    shows FAILED forever; cleanup is a manual two-table SQL `DELETE` against EFM's Postgres,
    recurring, no real fix planned. Will happen again for every new class.
  - EFM Designer palette needs a rename-then-rename-back trick (or an
    `agent-class-manifest-config` pin) to pick up a genuinely new processor even when the create
    API already accepted it.
- **Camera/mic: zero prior art anywhere in this array.** No MiNiFi binary-ingestion pattern has
  ever been proven (`efm-xiao.md` explicitly punted this in v1). No MicroFi camera/mic processor
  was ever designed. This is real R&D, not a config exercise.
- **AI-on-the-edge / inbound-HTTP-triggers-a-model: real, working prior art exists, just not
  called from a XIAO yet.** `NvidiaNanoJava` (Jetson) already runs a verified MiNiFi **Java**
  `HandleHttpRequest → InvokeHTTP → HandleHttpResponse` flow fronting a resident TensorRT
  MobileNetV2 classifier on `:8090`/`/classify`, bound to `*:8090` specifically so a LAN device
  can call it directly (p50 132ms round trip, real image classification verified — see
  `efm-nvidia-nano-inference.md`). The natural "AI-ish on the XIAO" answer is composition — XIAO
  ships a frame/reading to this endpoint and gets a real synchronous answer — not running
  inference on the ESP32 itself.
- **"Inbound HTTP triggers new code to run against the sensor" needs reframing for this
  architecture**: no scripting means no literal new bytecode at runtime. What's actually
  achievable: (a) EFM pushing a different **flow graph** live over C2 (already how MicroFi
  works), or (b) a fixed menu of pre-compiled actions selected by inbound HTTP path/body
  (`POST /action/blink`, `POST /action/read-temp`) — an upstream model/agent picks *which*
  pre-built action to invoke, not what code runs.
- **No LED/GPIO-write processor exists** — only `GetGPIO` (read). A `SetGPIO`/`PulseGPIO`
  processor is new, small, real firmware work — good first deliverable to prove the
  build→flash→EFM-push loop on a new unit before the harder devices.
- **Access/topology facts that will bite a future session**: MicroFi firmware lives in the
  private `Christopheraburns/MicroFi` (read-only upstream) / `steven-matison/MicroFi` (dev fork)
  — reachable as the `steven-matison` gh identity, **not** `cldr-steven-matison`. WindowsDesktop
  has no direct fork push access; commits relay through StarlinkAI over SSH.
- **Related issues**: #126 (open) is the Sparkplug field-validation umbrella — distinct from this
  new plan, don't conflate. Everything else XIAO/MicroFi-related is closed.

## Per-device plan

### MicroFi-1 — Sparkplug Sensor Emit

Already proven on this exact unit: `GenerateFlowFile`, `LogAttribute`, `UpdateAttribute`,
`PublishMQTT`, `ListenHTTP`, `GetGPIO` (all native MicroFi processors); Sparkplug B (via the
separate non-MicroFi Arduino sketch, see above).

1. **Decide firmware strategy** — the biggest single lift in this whole plan: keep the two-
   mutually-exclusive-firmware-images reality, or invest in a native MicroFi `PublishSparkplug`
   processor (C++ compile-time, wrapping the already-proven `EmbeddedSparkplugNode`/`nanopb`
   path) so Sparkplug becomes a real EFM-pushed flow node instead of a separate hand-flashed
   sketch.
2. **Check flash headroom first** — device 1 is already at ~97% of its 2MB app slot with 6
   processors built in; a Sparkplug/protobuf processor may not fit without trimming
   `ListenHTTP`/`GetGPIO`/`UpdateAttribute` out of this specific image.
3. If built: `GenerateFlowFile` (synthetic sensor value) → `PublishSparkplug` (NBIRTH/NDATA),
   verified the same way as before (`ConsumeMQTTIIoT` → `PublishKafka` → real decode).
4. Watch the two known engine bugs (`kMaxFlowNodes=4`, single-relationship fan-out) when wiring.

### MicroFi-2 — Camera/Mic

Genuinely new territory — nothing built anywhere in this array for XIAO camera/mic.

- **Prereq**: confirm this unit is actually the ESP32-S3 **Sense** variant (camera + mic + SD)
  via chip-id/board inspection before promising this track at all.
- New MicroFi processor candidates: `CaptureImage`/`GetCameraFrame` (JPEG via the `esp32-camera`
  component) emitting a FlowFile with binary content.
- `PublishMQTT` likely can't carry a JPEG-sized payload without the same buffer-size gotcha
  `PublishMQTT` already hit once on MicroFi-1's Sparkplug leg (`mqttClient.setBufferSize(...)`) —
  and 2MB flash + limited PSRAM-vs-heap tradeoffs need scoping before committing to an MQTT-out
  design.
- **Alternative to MQTT-out**: mirror the `NvidiaNanoJava` pattern — POST the JPEG directly to
  the Jetson's already-proven `/classify` endpoint for real synchronous image classification.
  This directly answers "AI-ish on the XIAO, triggered from a model" via composition rather than
  building AI on the XIAO itself. Would need a MiNiFi-style outbound-HTTP processor, which
  doesn't exist in MicroFi's confirmed-6 registry today — real new work either way.
- **Mic**: same shape, one step behind camera in priority — I2S mic capture → ship a raw audio
  chunk upstream to a Whisper-class endpoint elsewhere in the array (Jetson-tier compute;
  reuse the endpoint, don't try to run STT on the XIAO itself).
- Flag: no MiNiFi processor for chunked/multipart HTTP POST from an embedded device has been
  proven in this array at all — this is real R&D, size the pass accordingly.

### MicroFi-3 — Inbound Trigger Events

Builds directly on MicroFi-1's already-proven `ListenHTTP` (fire-and-forget, verified). Ideas,
roughly ascending complexity:

1. **`ListenHTTP → SetGPIO` LED trigger** — concrete, small, good first deliverable. Needs a new
   `SetGPIO`/`PulseGPIO` write processor (only `GetGPIO`, read-only, exists today) — real
   firmware work, but small and contained; proves the build→flash→EFM-push loop before the
   harder devices.
2. **Inbound HTTP dispatch to different sensor actions** — path/body-driven branching. MicroFi
   has no `RouteOnAttribute` (no EL engine, explicitly deferred), so branching logic either
   lives upstream (separate `ListenHTTP` + flow per action, matching the one-relationship-one-
   consumer constraint) or waits on a minimal predicate evaluator, which was scoped elsewhere
   but never built. Don't assume this exists.
3. **"Model-triggered new code to run against the sensor"** — reframe as: an upstream model/
   agent decides *which pre-built flow or action* to invoke on the XIAO (via EFM flow-push or a
   fixed HTTP action menu), not literally shipping new bytecode to the device. See the
   architecture note above.
4. **Custom processor experiments generally** — this device is the natural home for small,
   purpose-built C++ processors (the only real extension path), given #1–#3 above already
   require at least one new processor (`SetGPIO`).

## Cross-cutting must-verify-first

- Confirm the 2 new units' actual chip/flash/peripherals before assuming Sense-variant parity —
  MicroFi-2's whole premise depends on this.
- Decide the `MicroFi` → `MicroFi-1` class-rename question. EFM has no rename endpoint; likely
  needs the export/delete/recreate pattern from `skills/nifi-and-ai/references/minifi-efm.md`
  §14 (export the live flow first, recreate the class, reimport — never point a recreated class
  at the old `designerFlowId`).
- Firmware-image-per-class reality: each physical unit runs exactly one firmware image at a
  time. If MicroFi-1 gets a native Sparkplug processor, that supersedes needing the separate
  Arduino sketch at all — worth deciding early since it changes MicroFi-1's whole flash/processor
  budget.
- All the engine ceilings (`kMaxFlowNodes=4`, single-relationship fan-out, no Python/scripting/
  EL ever, shrinking 2MB-class flash headroom) and EFM operational gotchas (manifest-refresh
  rename trick, `operation`/`bulk_operation` FAILED-forever cleanup SQL) above apply to every new
  class, not just device 1.
- MicroFi firmware dev happens in the private fork under the `steven-matison` gh identity, with
  WindowsDesktop→StarlinkAI push relay — plan for this topology on whichever host does the work.

## Suggested phased rollout

1. Hardware triage: identify/confirm the 2 new units' exact chip/flash/peripherals; decide
   physical host assignment (which box each gets flashed/plugged into).
2. EFM class setup: create `MicroFi-2`/`MicroFi-3` classes (and decide the `MicroFi`→`MicroFi-1`
   rename), get fresh `generateCommand` deployer commands per the standard rule (never
   hand-built, never a reused `agentIdentifier`).
3. `MicroFi-3` first (lowest new-processor cost): `SetGPIO`/LED flow — validates the new-
   processor + reflash + EFM-push loop before investing in the harder devices.
4. `MicroFi-1` Sparkplug-native-processor decision — the biggest single lift.
5. `MicroFi-2` camera/mic last — largest R&D scope; consider whether the media path even goes
   through MiNiFi/EFM at all, or whether the XIAO just acts as a plain HTTP client to the Jetson
   while still registering with EFM for management/heartbeat.

## Reference docs

- `efm-xiao.md` — original XIAO hardware/Arduino-track history
- `efm-xiao-microfi.md` — MicroFi processor development history
- `efm-sparkplug-b-hardware-lab-plan.md` — the separate Arduino/Sparkplug B firmware track
- `efm-nvidia-nano-inference.md` — the Jetson `/classify` endpoint (`NvidiaNanoJava`)
- `skills/nifi-and-ai/references/minifi-efm.md` — EFM Designer API mechanics, including §14's
  class-recreation pattern
