# MicroFi: making the XIAO a real EFM agent instead of an MQTT publisher

`efm-xiao.md` plans to hand-write an Arduino sketch that publishes JSON to Mosquitto on `test/sensor/data`, so `ConsumeMQTT` in the `SparkPlug` PG picks it up with no NiFi-side change. That plan is sound and it still works. But Chris Burns has a private repo, `Christopheraburns/MicroFi`, that reframes the problem: it's a clean-room reimplementation of the MiNiFi C2 protocol targeting ESP32, and if it runs on our hardware the XIAO stops being a dumb publisher and becomes an agent that shows up in EFM next to `StarlinkAI`, `WindowsDesktop`, and `NvidiaNano` — flow pushed from the EFM Designer, not flashed by hand.

This is the evaluation of whether that's real, what it changes, and what `StarlinkAI` — the host the XIAO is actually plugged into — has to do to field-verify it.

## Access — confirmed, and broader than expected

`MicroFi` is private and readable as `steven-matison`:

```bash
gh api repos/Christopheraburns/MicroFi -q '.full_name, .private, .permissions'
# Christopheraburns/MicroFi
# true
# {"admin":false,"maintain":false,"pull":true,"push":true,"triage":true}
```

**The token has `push`, not just `pull`.** The task said view-only, so nothing in this evaluation writes to that repo, but the write path is open and worth knowing before someone runs a command that assumes it isn't. Read-only is a discipline here, not a permission boundary.

Last push `2026-05-29`, 355 KB, C++, PlatformIO + ESP-IDF.

## What MicroFi actually is

A clean-room reimplementation of the MiNiFi protocol contracts — FlowFile semantics, C2 heartbeat/ack — explicitly *not* a fork of `nifi-minifi-cpp`. The rationale is in `docs/MICROFI_ASSESSMENT.md`: MiNiFi C++ is a ~3.2 MB binary idling at ~5 MB RAM, which is Raspberry-Pi-class, and its design (heap-centric, RocksDB repositories, `dlopen` plugin loading) doesn't shrink to a microcontroller. So processors are compile-time-embedded and resolved by name against a static registry at flow-apply time.

What's built today, from the repo's own status list:

- Core types, minimal flow engine, WiFi station bring-up.
- HTTPS heartbeat POST to a configurable C2 URL via `esp_http_client` + mbedTLS.
- Flow-definition parsing — NiFi versioned-flow-snapshot JSON, auto-detect fall-through to MiNiFi Config Version 3 YAML.
- C2 op dispatch: `DESCRIBE/manifest` and `UPDATE/configuration`.
- LittleFS durable storage with watermark eviction, storage metrics in the heartbeat.
- **Two processors: `GenerateFlowFile` and `LogAttribute`.**

Not built: engine queue integration (replay on boot), SD overflow tier, per-flow retention override.

Read `docs/Processor-Inventory-And-Roadmap.md` for what it *wants* to be — 48 proposed processors including a WiFi-CSI sensing cluster (`GetWiFiCSI`, `WindowCSI`, `DetectMotionCSI`, `RunBistaticPair`) that is the actual research thesis. **That roadmap is aspirational.** The build target today is two processors. Any evaluation that treats the roadmap as shipped will produce a wrong answer.

The property names are deliberately MiNiFi-C++-compatible — `generate_flowfile.cpp` declares `File Size`, `Batch Size`, `Data Format`; `log_attribute.cpp` declares `Log Level`, `Log Payload`, `Log prefix`, `Attributes to Log` — so an EFM flow definition written against MiNiFi C++ resolves against MicroFi's registry unchanged. That's the design bet, and it's the thing to verify first.

## How this changes `efm-xiao.md`

| | `efm-xiao.md` today | With MicroFi |
|---|---|---|
| Firmware | Hand-written `.ino`, `PubSubClient` + `ArduinoJson` | ESP-IDF app, `pio run -t upload` |
| Config change | Reflash | EFM Designer push over heartbeat |
| Device in EFM | Invisible — Mosquitto only sees a client | Registers as an agent under a class |
| Transport | MQTT → Mosquitto → `ConsumeMQTT` | C2 heartbeat to EFM; egress still needs a processor |
| Credentials | `secrets.h`, gitignored | `sdkconfig.defaults.local`, gitignored |
| Reaches Kafka | Only if the `SparkPlug` PG dead-end gets closed | Same — unchanged by MicroFi |

The last row matters. **MicroFi does not close the `SparkPlug` gap.** `efm-xiao.md` established that both `ConsumeMQTT` and `ConsumeMQTTIIoT` route into a dead-end output port (`EOL`) with no `PublishKafka` wired in. That's a NiFi-side fix on `MINI-Gaming-G1`, independent of what firmware the XIAO runs. Nothing here changes that handoff spec.

And MicroFi has no `PublishMQTT` built yet — it's `P0` on the roadmap and not in the registry. So a MicroFi XIAO today can register with EFM and run `GenerateFlowFile → LogAttribute`, but it **cannot publish to Mosquitto at all.** The two paths don't merge until `PublishMQTT` exists.

That's the honest read: MicroFi is not a replacement for the `efm-xiao.md` plan right now. It's a parallel track that becomes the better plan once `PublishMQTT` lands. If the goal this month is telemetry into Kafka, the Arduino sketch is still the shorter road.

## The hardware problem — neither XIAO matches a shipped build environment

MicroFi ships three PlatformIO environments:

| Env | Board | Flash | LittleFS | PSRAM |
|---|---|---|---|---|
| `esp32s3` (default) | Lonely Binary ESP32-S3 N16R8 | 16 MB | ~11.5 MB | 8 MB OPI |
| `esp32s3-4mb` | Generic S3 (DevKitC-1 / `esp32s3box`) | 4 MB | ~2.4 MB | — |
| `esp32-c3` | ESP32-C3 DevKitM-1 | 4 MB | none | — |

`efm-xiao.md` records the chip only as VID `303a:1001`, "USB JTAG/serial debug unit," Espressif — and calls it "ESP32-S3 or -C3 family." **That VID doesn't discriminate.** `303a:1001` is Espressif's native USB JTAG/serial device and is shared by the S3, the C3, *and* the C6. If it's a C6, MicroFi has no environment for it at all and this evaluation stops there. Run `chip_id` before anything else.

Assuming it's one of the two:

- **XIAO ESP32-C3** — 4 MB flash, no PSRAM. The `esp32-c3` env fits. Volatile-only: `storage_init()` returns `NotFound`, flow definitions are lost on reboot, EFM re-pushes on reconnect. That's Tier 1, and it's a legitimate first test.
- **XIAO ESP32-S3** — 8 MB flash, 8 MB PSRAM. **This matches neither S3 environment.** `esp32s3` assumes the 16 MB Lonely Binary board and its `partitions.csv` carves 2 × 2 MB OTA slots plus ~11.5 MB LittleFS, which does not fit in 8 MB. `esp32s3-4mb` targets `esp32s3box` with a 4 MB layout, which would work but wastes half the flash and gives up OTA. Getting a XIAO S3 onto MicroFi properly means a new board JSON in `boards/` and a third partition table — real work, not a flag change.

Neither is a blocker for a *first* registration test. Both are blockers for a clean Tier 2 deployment.

## What the array requires

We run **EFM 2.3.1.0-2** (`efm-validation-agent.md`), MiNiFi C++ `1.26.02`, CEM Java `2.24.08.0-19`. MicroFi's README says it targets "Cloudera EFM 2.x" and that the ack is implicit — EFM 2.x treats a heartbeat whose `flowInfo.flowId` matches the pushed flow UUID as the acknowledgement, so `CONFIG_MICROFI_C2_ACK_URL` is set but unused. **That implicit-ack behavior against 2.3.1.0-2 specifically is unverified and is the single highest-risk assumption in the whole integration.** If EFM 2.3.1.0-2 waits for an explicit POST to `/efm/api/c2-protocol/acknowledge`, the flow push will look accepted from the server side and never complete on the device — which is exactly the failure shape `minifi-efm.md` §11 warns about, where a `200` from the publish API proves EFM accepted the write and nothing about whether an agent received it.

Config lives in `sdkconfig.defaults.local` (gitignored, copied from `.example`):

```
CONFIG_MICROFI_WIFI_SSID="..."
CONFIG_MICROFI_WIFI_PASSWORD="..."
CONFIG_MICROFI_C2_HEARTBEAT_URL="http://<efm-host>:10090/efm/api/c2-protocol/heartbeat"
CONFIG_MICROFI_C2_ACK_URL="http://<efm-host>:10090/efm/api/c2-protocol/acknowledge"
```

Those are the same two URLs `efm-executescript.md` already sets as `nifi.c2.rest.url` / `nifi.c2.rest.url.ack` for the C++ agent, so the endpoint shape is confirmed against our EFM. Agent class defaults to `default` and the id derives as `microfi-<mac>` from the eFuse MAC — both need overriding before first boot, or the device lands in EFM under a class that means nothing.

MicroFi's README calls out that `localhost` in the default heartbeat URL cannot work from a real ESP32. Our equivalent: the XIAO needs a routable address for EFM, which on this array is `gaming-pc-lan-ip:10090` on LAN or `efm-host-ip:10090` over Tailscale.

## This runs on `StarlinkAI`, not the Mac

The XIAO is plugged into StarlinkAI's front-facing USB — that's where `efm-xiao.md` put it and that's where it still is. So the device leg of this work belongs to `StarlinkAI`, and the host picks up three advantages plus one new hazard.

**EFM reachability is already proven from this host.** `CLAUDE-CHECKIN.md` records a MiNiFi agent installed on the Windows side, class `StarlinkAI`, confirmed Online in the EFM UI and heartbeating to `efm-host-ip:10090` over Tailscale. There's no on-site-LAN precondition and no cluster change needed anywhere — the path the XIAO needs is the path this box already uses.

For contrast, `FTF3XR2065` would have been the harder host: EFM is intentionally not deployed there, `svc/efm` doesn't exist, its `service/efm 10090:10090` port-forward pane is failing quietly, and it isn't on the tailnet. Running the test there would have meant either carrying the board across the room or a stateful EFM redeploy (Postgres + 2 PVCs, `blog/efm-persistance.md`). Neither is necessary now.

**The hazard is the agent class.** `StarlinkAI` is already a live class in EFM with a real agent in it. If MicroFi registers under that same class, it joins a class that already has an agent and a flow — and an EFM push aimed at one lands on both. **Set `CONFIG_MICROFI_AGENT_CLASS` to something distinct (`MicroFi`) before the first boot, not after.** The default is `default`, which is equally wrong but at least harmless. This is the one configuration mistake here that can disturb a working agent rather than just fail.

**The toolchain wrinkle is USB.** Claude Code on this host runs in WSL2, but the XIAO enumerates on the Windows side. WSL2 has no native USB passthrough — reaching `/dev/ttyACM0` from Ubuntu means `usbipd-win` attach-per-boot. Run PlatformIO natively on Windows instead: the board appears as a `COM` port, `pio` drives it directly, and the WSL2 session is only for editing. Don't burn a session chasing a device node that was never going to exist.

## Field validation run, 2026-07-29 — blocked at Task 2

Picked up via issue #9. Found the XIAO on `COM5` (`USB\VID_303A&PID_1001&MI_00`, matches the
documented Espressif signature exactly — `COM4`/`COM1` are unrelated devices on this host).

**Task 1 — chip pinned: ESP32-S3.** `esptool` wasn't installed on the Windows host yet (`pip
install esptool`, v5.3.1); `python -m esptool --port COM5 chip-id` (the `chip_id` subcommand is
now deprecated in favor of `chip-id`, same output):
```
Chip type:          ESP32-S3 (QFN56) (revision v0.2)
Features:           Wi-Fi, BT 5 (LE), Dual Core + LP Core, 240MHz, Embedded PSRAM 8MB (AP_3v3)
MAC:                e0:72:a1:fb:fd:04
```
8MB embedded PSRAM confirms this is the XIAO ESP32-S3 case this doc already analyzed (not a C6 —
not a stop condition). Per the doc's own hardware table, this means **`esp32s3-4mb`** is the
right build env (4MB layout on 8MB flash, OTA given up) — not bare `esp32s3` (assumes a 16MB
board and would overflow).

**Task 2 — EFM reachability: failed, 4/4 retries, `Invoke-WebRequest` to
`http://100.68.113.126:10090/efm/ui/` all timed out.** This is the same symptom found the same
day working issue #18 (`beelink-starlink-efm-ai.md`'s "Re-verification from StarlinkAI
(2026-07-29)" section) and already tracked by
[#11](https://github.com/cldr-steven-matison/DesktopShare/issues/11) — Tailscale itself is fine
(`tailscale ping` to `mini-gaming-g1` returns in ~56ms), the failure is TCP to port 10090
specifically, most likely WindowsDesktop's `kubectl port-forward` pane for `svc/efm` down or
flapping again.

**Stopped here per the doc's own instruction**: "if it fails, Tailscale is down or the
port-forward pane on `MINI-Gaming-G1` died — fix that before flashing anything." Tasks 3-8 all
either need EFM to actually confirm a heartbeat/registration (5, 6, 7) or would be flashing a
device toward a C2 endpoint that can't be reached yet (3, 4, 8) — none of that is worth doing
blind when the core point of the exercise (register in EFM, verify the manifest, test the
implicit ack) can't be completed until connectivity is back. Read-only work only this pass; no
firmware built, no flash attempted, `MicroFi` repo not yet cloned.

**Next step**: once #11/#25 restore EFM reachability from StarlinkAI, resume at Task 3 using the
env pinned above (`esp32s3-4mb`).

## Field validation resumed, 2026-07-29 — Tasks 3-6 done, stopped before Task 7 (real hardware risk)

WindowsDesktop restarted the flapping port-forwards; EFM reachable again (4/4 clean `200`s from
StarlinkAI). Resumed at Task 3.

**Per Steven's direction, this run goes LAN-direct to WindowsDesktop, not over Tailscale** — the
XIAO joins a WiFi network (`ATTyjuHfEi`) on the same subnet as WindowsDesktop's LAN IP
(`192.168.1.121`), bypassing Starlink and Tailscale entirely for the device's own path. Skips the
doc's original `efm-host-ip`/Tailscale assumption; `sdkconfig.defaults.local` points both C2 URLs
at `http://192.168.1.121:10090/efm/api/c2-protocol/...` instead. The WiFi password was entered
directly into the gitignored local file on the Windows host, never through chat.

**Toolchain gap found and closed**: neither `esptool` nor PlatformIO Core was actually installed
on the Windows host (contrary to this doc's "VS Code + PlatformIO" prerequisite) — installed both
via `pip install esptool platformio` (esptool 5.3.1, PlatformIO 6.1.19). No VS Code needed; every
doc-specified step is a `pio`/`esptool` CLI command.

**Task 3 — build: succeeded, but over the size budget.** `CONFIG_MICROFI_AGENT_CLASS` set to
`MicroFi` in `sdkconfig.defaults` (its actual default was `"ESP32"`, not `"default"` as this doc
previously assumed — minor drift, corrected). `pio run -e esp32s3-4mb`: **Flash 66.4% (1,044,597 /
1,572,864 bytes)** — over MicroFi's own stated "under 50%" success criterion. RAM 36.1%.

**Task 4 — flash + first heartbeat: succeeded, real EFM 200.** `pio run -e esp32s3-4mb -t upload
-t monitor` (upload and monitor must be chained in one invocation — attaching monitor after a
separate upload misses the boot sequence, the device has already reset and moved on). WiFi
associated with `ATTyjuHfEi` in ~2.5s (one retry), got `192.168.1.198`. First heartbeat:
```
I (7575) microfi.c2: heartbeat #0 -> 200 (sent 5677 bytes, manifest=yes, recv 28 bytes)
```
Full manifest (3840 bytes) sent inline on this first heartbeat, exactly as the doc predicted.

**Task 5 — EFM registration: confirmed, `StarlinkAI` unaffected.** `GET
/efm/api/agent-classes` (via Tailscale, `100.68.113.126` — this Windows host's own network path
can't reach `192.168.1.121` directly, only the XIAO's separate WiFi join can) lists a new
`MicroFi` class with a real manifest id. `StarlinkAI`'s class entry is present with its same
manifest id as before this test, and its own agent's `minifi-app.log` shows no renewed heartbeat
failures since the connectivity fix — the live production agent is untouched.

**Task 6 — manifest verified: exactly 2 processors, no more.** `GET
/efm/api/agent-manifests/{id}` on the new manifest returns exactly `GenerateFlowFile` and
`LogAttribute` with their full property descriptors — confirms the clean-room registry design bet
this doc opened with.

**Stopped before Task 7 — real hardware risk found, not a software gate.** The upload step logged:
```
Warning! Flash memory size mismatch detected. Expected 4MB, found 2MB!
```
This specific XIAO unit's physical flash is **2MB**, not the 8MB this doc's hardware section
assumed for "XIAO ESP32-S3." `partitions_4mb.csv`'s `littlefs` partition is declared
`0x1A0000`-`0x400000` (ending exactly at the 4MB boundary) — **roughly 2MB of that declared range
doesn't exist on this chip.** Task 7 pushes a flow, which MicroFi persists to
`/littlefs/.flowdef`; Task 8's power-cycle test depends on the same filesystem. Most SPI NOR flash
aliases (wraps) addresses past the physical chip boundary back to low addresses — a write aimed at
the "high" end of the declared LittleFS space could land on the bootloader/partition table/app
image instead of failing cleanly. The device booted and mounted LittleFS fine for Task 4 (a
read-only check for an absent file), which doesn't prove writes into the out-of-bounds region are
safe.

Given Steven's call to stop rather than build a custom 2MB-fit partition table, **Tasks 7 and 8
were not attempted.** No flow was pushed, no write beyond boot-time LittleFS mount was made to
this board.

**This is itself a real, useful finding, not a null result**: neither of MicroFi's two sub-16MB
S3 environments (`esp32s3`, 16MB Lonely Binary; `esp32s3-4mb`, 4MB DevKitC) fits this specific XIAO
unit's actual 2MB flash. A genuinely XIAO-S3-safe env needs its own board JSON and a partition
table sized for 2MB, not the existing 4MB one accepted with a warning. **Correction**: this unit
has a camera, so it's the **XIAO ESP32-S3 Sense** variant, not the base board — it does have a
microSD slot (small push-type, on the back of the camera expansion board, easy to miss visually).
That means `CONFIG_MICROFI_SD_OVERFLOW` is a real option here, not a dead end — worth revisiting
as an alternative to a from-scratch 2MB partition table if a card is available: overflow the
LittleFS durability tier onto SD instead of trying to fit it inside the tiny onboard flash.

**Open**: whether EFM 2.3.1.0-2 accepts the implicit ack (the doc's original "load-bearing
unknown") is still untested — that requires Task 7's flow push, which requires the partition-table
fix above first.

## Field validation completed, 2026-07-29 — Tasks 7-8, all 8 tasks done

Picked back up once the 2MB-safe partition table (`partitions_2mb.csv`, `esp32s3-2mb` env — see
above) was built and flashed clean, no mismatch warning. Forked `Christopheraburns/MicroFi` to
`steven-matison/MicroFi` (`--remote`, remote name `fork`) and pushed the partition-table fix to a
`xiao-s3-2mb-partition` branch there — `origin` still points at the real repo, untouched, no PR
opened yet ("when the time is right" per Steven). The field-test-specific
`CONFIG_MICROFI_AGENT_CLASS` override stayed local-only, not committed.

**Task 7 — pushed the flow, implicit ack confirmed.** Built `GenerateFlowFile → LogAttribute` via
the EFM Designer's real per-component API (`GET .../client-identifier` for the write-clientId,
`POST .../process-groups/{pgId}/processors` ×2, `POST .../process-groups/{pgId}/connections`,
`GET .../validate`, `POST .../publish`) — the envelope needs
`{"revision":{...},"componentConfiguration":{...},"requestId":...}`, not a flat or
`component`-wrapped body; a flat/wrong-wrapper body 400s with the unhelpful `"Component details
must be specified."` regardless of which wrapper is missing, so this is worth remembering as its
own trap. Every new component's create-request needs `revision.version: 0` — that field tracks
the component's own revision line, not the flow's overall version. `LogAttribute` needs `success`
explicitly auto-terminated (no downstream consumer); `GET .../validate` came back
`{"validationErrors":[]}` before publish.

Published clean (`flowVersion: 1`, `dirty: false`). **EFM itself went down mid-test** (same
flapping-connectivity shape as #11/#25 — confirmed both from this session's own Tailscale checks
and the live `StarlinkAI` agent's own heartbeat timeouts, not caused by the publish) and came back
after Steven restarted it. Once stable, `GET /efm/api/agents/microfi_1` showed `state: ONLINE`,
`flowId: e9aac4e6-4124-45a6-92d3-ce09505974d1` (the boot-default's all-zero placeholder replaced
by a real UUID), `flowUpdateDate` matching `lastSeen`, both `GenerateFlowFile`/`LogAttribute`
`running: true` — **all of that with MicroFi never once POSTing to `/acknowledge`** (confirmed
absent from every log across the whole session). **This answers the doc's original load-bearing
question: EFM 2.3.1.0-2 does accept the implicit ack** — a heartbeat whose `flowInfo.flowId`
matches the published flow is sufficient on its own.

**Task 8 — power-cycle: flow definition persists.** Two real physical unplug/replugs (Steven's
hand on the cable) both resumed `GenerateFlowFile`/`LogAttribute` cleanly with reset FlowFile
counters (genuine reboots, not soft resets) — but capturing the exact boot-log line proved to be
a real tooling problem: `pio device monitor` attached *before* a physical unplug reliably lost
everything from the disconnect gap through the reconnect burst, across three separate attempts,
even via PlatformIO's own `log2file` filter (writes to a *different* file than the redirect, same
loss). Root cause not nailed down (not a COM-port renumber — confirmed same `COM5` after
reconnect); reads like an internal buffer that doesn't survive the physical link actually dropping
mid-session, as opposed to a tool-triggered reset which keeps the OS-level handle alive throughout.
**Fix that actually worked**: re-run `pio run -t upload -t monitor` (re-flashes identical firmware
— LittleFS is a separate partition, untouched — and its own RTS-pin hard-reset is a real full
reboot) instead of relying on a physical disconnect for the capture. That caught it cleanly:
```
microfi.flowstore: flow def loaded: 2872 bytes from /littlefs/.flowdef
microfi.flowstore: flow_id loaded: e9aac4e6-4124-45a6-92d3-ce09505974d1
```
Exact match to the published flow's `flowId`. Persistence confirmed for real, not inferred from
absence of an error.

**All 8 tasks complete.** Chip: XIAO ESP32-S3 **Sense** (has a camera + microSD slot — corrected
mid-session, not the base board), 2MB actual flash (not the 8MB assumed), custom
`esp32s3-2mb`/`partitions_2mb.csv` env built for it. Firmware 1,044,597 bytes (88.6% of the 2MB
layout's app slot). Agent class `MicroFi`, isolated from the live `StarlinkAI` agent throughout
(confirmed unaffected at every check). Manifest: exactly `GenerateFlowFile` + `LogAttribute`, no
more. Implicit ack: confirmed working on EFM 2.3.1.0-2. Persistence: confirmed working via
LittleFS on the corrected partition table.

## Field validation instructions — `StarlinkAI`

Prerequisites: the XIAO on StarlinkAI's front USB (it's already there), Tailscale up, VS Code + PlatformIO **on the Windows host, not in WSL2**. Do **not** push to `Christopheraburns/MicroFi` — read-only, despite the token.

**Task 1 — pin the chip.** Nothing else is decidable until this is known. Windows host, PowerShell:

```powershell
esptool.py --port COM3 chip_id      # substitute the real COM port
```

Find the port first in Device Manager under "Ports (COM & LPT)", or `[System.IO.Ports.SerialPort]::GetPortNames()`. Record S3 vs C3 vs C6. **If C6, stop and report** — MicroFi has no environment for it and everything below is moot.

**Task 2 — confirm EFM is reachable.** This host already heartbeats there with its MiNiFi agent, so this should pass on the first try:

```powershell
(Invoke-WebRequest -Uri "http://efm-host-ip:10090/efm/ui/" -UseBasicParsing).StatusCode
```

Expect `200`. If it fails, Tailscale is down or the port-forward pane on `MINI-Gaming-G1` died — fix that before flashing anything.

**Task 3 — build.** Clone read-only, copy the config template, fill in WiFi + the Tailscale EFM address:

```powershell
gh repo clone Christopheraburns/MicroFi
cd MicroFi
copy sdkconfig.defaults.local.example sdkconfig.defaults.local
# edit: SSID, password, and both C2 URLs -> http://efm-host-ip:10090/efm/api/c2-protocol/...
```

**Set `CONFIG_MICROFI_AGENT_CLASS` in `sdkconfig.defaults` to `MicroFi` before building.** Not `StarlinkAI` — that class already holds this host's live MiNiFi agent, and a shared class means an EFM push aimed at one reaches both. Not `default` either. Then, per what Task 1 found:

```powershell
pio run -e esp32-c3                 # C3
pio run -e esp32s3-4mb              # S3, accepting the 4 MB layout on 8 MB flash
```

Record the firmware size from `.pio/build/<env>/firmware.bin` — MicroFi's own success criterion is under 50% of flash.

**Task 4 — flash and watch the first heartbeat.**

```powershell
pio run -e <env> -t upload -t monitor
```

Serial should show WiFi association then an HTTP POST to the heartbeat URL. Capture the exact first-heartbeat log lines verbatim — that's the artifact.

**Task 5 — confirm registration in EFM.** The agent should appear under class `MicroFi` in the EFM UI at `http://efm-host-ip:10090/efm/ui/`. Per `minifi-efm.md`, don't trust the UI alone — query the `agent` table's `last_seen` / `agent_state` in EFM's Postgres directly to confirm the heartbeat is landing and not just that a row exists. **Also confirm the existing `StarlinkAI` agent is still Online and unchanged** — that's the check that proves the new class didn't disturb it.

**Task 6 — verify the manifest.** This is the real test of the clean-room bet. The first heartbeat carries a full manifest derived from the static registry; subsequent ones send only the hash. Confirm EFM parses it and that the Designer offers exactly `GenerateFlowFile` and `LogAttribute` for that class — no more, no less. If EFM rejects a manifest advertising two processors, that's the finding and the whole approach needs rework.

**Task 7 — push a flow and check the implicit ack.** Build `GenerateFlowFile → LogAttribute` in the EFM Designer for the class, publish it, and watch the serial monitor for the `UPDATE/configuration` fetch, parse, and apply. Then confirm the next heartbeat advertises a `flowInfo.flowId` matching the pushed flow UUID, and that **EFM marks the operation complete without an explicit ack POST.** This is the EFM 2.3.1.0-2 compatibility question from above. If EFM sits in a pending state, capture that — it's the most valuable negative result available here.

**Task 8 — power-cycle.** On C3 expect the flow to be lost and re-pushed (volatile-only, by design). On S3 with LittleFS expect it to survive. Confirm which actually happens.

Report back with: chip variant, chosen env, firmware size, the first-heartbeat log lines, whether the manifest was accepted, whether the implicit ack worked on 2.3.1.0-2, and the reboot behavior.

## Next: processors for deeper testing

All 8 validation tasks passed, but they only ever exercised MicroFi's two built-in processors,
and both are synthetic: `GenerateFlowFile` fabricates payload from nothing, `LogAttribute` writes
it to the serial log. The flow round-trips entirely inside the device — **nothing enters from a
real source and nothing leaves the board.** That's enough to prove registration, the implicit ack,
and LittleFS persistence. It is not enough to test MicroFi as a data agent. Deeper testing needs
real ingress and real egress, which means new processors compiled into the static registry.

Filed as **[#26](https://github.com/cldr-steven-matison/DesktopShare/issues/26)** (sub-issue of #9)
for `FTF3XR2065` — this is eval + dev work against the compile-time registry, so it lands on the
Mac rather than StarlinkAI where the board is; anything built there gets on-hardware verification
back on StarlinkAI as a follow-up. Priority order:

1. **`PublishMQTT` — P0, the load-bearing gap.** This is the same missing piece flagged in the
   opening comparison and the "What NOT to do" list: with no `PublishMQTT` in the registry, a
   MicroFi XIAO cannot publish to Mosquitto at all, so it can't feed `ConsumeMQTT` in the
   `SparkPlug` PG and can't reach Kafka. It's `P0` on MicroFi's own roadmap and unbuilt. Until it
   exists, MicroFi stays a parallel track to the hand-written sketch in `efm-xiao.md`, never a
   replacement. Everything else on this list is secondary to closing this.
2. **A real ingress processor.** `GenerateFlowFile` is a stand-in. The XIAO ESP32-S3 **Sense**
   variant this array actually runs has a camera and onboard sensors — a processor that emits real
   device telemetry (even a simple periodic sensor read) is what turns the round-trip into an
   actual edge-data test rather than a loopback.
3. **Attribute / routing processors** — `UpdateAttribute`, `RouteOnAttribute`. The current flow is
   linear (source → log); testing branch logic and attribute mutation needs these, and they're
   cheap to embed.

Two design constraints carry over from the validation and bound this work: processors are
**compile-time-embedded and resolved by name against a static registry** (no `dlopen`, no runtime
plugin load — adding a processor means a rebuild and reflash), and property names must stay
**MiNiFi-C++-compatible** (as `GenerateFlowFile`/`LogAttribute` already are) so an EFM flow
definition written against MiNiFi C++ resolves unchanged. Any dev branches go on the
`steven-matison/MicroFi` fork, not upstream — `Christopheraburns/MicroFi` stays read-only unless
Steven says otherwise.

## What NOT to do

- **Don't push to `Christopheraburns/MicroFi`.** The token allows it. The task doesn't.
- **Don't register MicroFi under the `StarlinkAI` agent class.** That class holds this host's live, Online MiNiFi agent. A shared class means an EFM flow push aimed at one device reaches both. Use a distinct class and verify the existing agent afterward.
- **Don't try to flash from WSL2.** No native USB passthrough; the board enumerates on the Windows side as a `COM` port. PlatformIO runs on the Windows host. `usbipd-win` is a workaround, not the path of least resistance.
- **Don't treat the 48-processor roadmap as available.** Two processors are built. Every capability claim in `Processor-Inventory-And-Roadmap.md` beyond `GenerateFlowFile` and `LogAttribute` is a plan.
- **Don't expect this to feed Kafka.** No `PublishMQTT`, and the `SparkPlug` PG still dead-ends at `EOL`. Both gaps are real and neither is closed by flashing MicroFi.
- **Don't flash the default `esp32s3` env onto a XIAO S3.** Its `partitions.csv` assumes 16 MB; the XIAO has 8 MB.
- **Don't commit `sdkconfig.defaults.local`.** It holds the WiFi passphrase. It's gitignored upstream — keep it that way in any local clone.

## When this ships

**Done** (2026-07-29): chip variant confirmed (XIAO ESP32-S3 Sense, 2MB flash), real firmware
size (1,044,597 bytes / 88.6% of a 2MB-sized layout), EFM 2.3.1.0-2 confirmed accepting the
implicit ack, persistence confirmed via LittleFS. The `esp32s3-2mb` partition-table fix is pushed
to `steven-matison/MicroFi`'s `xiao-s3-2mb-partition` branch — that's the point to ask Chris
whether it belongs upstream, once a PR is actually opened (not yet, per Steven — "when the time is
right").

Update `efm-xiao.md` too: MicroFi registers cleanly and the implicit ack works, so its "hand-write
the sketch" plan is now genuinely the fallback rather than the primary path — the open decision is
still whether `PublishMQTT` (unbuilt, `P0` on MicroFi's roadmap) is close enough to wait for before
committing to one path for real telemetry-to-Kafka work.
