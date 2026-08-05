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

## Processor design specs (eval — 2026-07-30, FTF3XR2065)

Desk eval of the shortlist against the compile-time registry — no clone on this Mac, so this is a
spec to build against on the fork, not code. The built-ins set the naming pattern to copy:
`generate_flowfile.cpp` → `File Size` / `Batch Size` / `Data Format`; `log_attribute.cpp` →
`Log Level` / `Log Payload` / `Log prefix` / `Attributes to Log`. Every property below is Title
Case to match. **Confirm the exact strings against the pinned `nifi-minifi-cpp` version at build
time** — property sets drift between releases.

### 1. `PublishMQTT` — P0, the egress gap

MiNiFi C++ `PublishMQTT` declares (upstream `PROCESSORS.md`, `main`): **Broker URI**, **Client ID**,
**MQTT Version**, **Topic**, **Quality of Service**, **Connection Timeout**, **Keep Alive
Interval**, **Last Will Topic**, **Last Will Message**, **Last Will QoS**, **Last Will Retain**,
**Last Will Content Type**, **Username**, **Password**, **Security Protocol**, **Security CA**,
**Security Cert**, **Security Private Key**, **Security Pass Phrase**. Relationship: **success**.

Minimal ESP32 subset to embed first: **Broker URI**, **Client ID**, **Topic**, **Quality of
Service**, plus **Username**/**Password** for an auth'd Mosquitto. Defer the `Security *` (TLS) props
— the `SparkPlug` PG's Mosquitto is plaintext on the LAN, and ESP32 TLS is heavier weight for a first
cut. This is the piece that turns the XIAO from a loopback into a real publisher: XIAO → Mosquitto →
`ConsumeMQTT` → Kafka.

### 2. Real ingress source — MicroFi-original

No MiNiFi C++ equivalent to mirror, so there's no upstream property schema to match — follow the
convention instead (Title Case, GenerateFlowFile-shaped so flows stay familiar). The XIAO ESP32-S3
**Sense** has onboard sensors (mic, IMU on some carriers) + camera. Design as a scheduled source:
properties like **Read Interval** / **Batch Size**, emitting one FlowFile per read with the sensor
value as content (and/or a Title-Case attribute). Relationship: **success**. Simplest proof-of-life:
a periodic read of one onboard value, published via `PublishMQTT` — that's the real ingress + real
egress test the round-trip has been missing.

### 3. `UpdateAttribute` — cheap, do it with #2

MiNiFi C++ model: **no fixed properties** — it takes **dynamic properties** (`attribute name` →
`value`, Expression-Language-capable) and writes each as a FlowFile attribute. Relationships:
**success**, **failure**. MicroFi needs to accept user-defined dynamic properties from the flow def
and set them as attributes. If there's no EL engine (see #4), support **literal values first** — that
covers nearly all branch-logic test cases without an evaluator.

### 4. `RouteOnAttribute` — defer; it hides an EL dependency

MiNiFi C++ model: property **Routing Strategy** (`Route to Property name` / matched-if-all /
matched-if-any) + **dynamic properties** (`relationship name` → an EL predicate); relationships:
**unmatched**, **failure**, and one per dynamic property. **The eval finding: RouteOnAttribute is
fundamentally an Expression-Language evaluator** — evaluating predicates against attributes is its
entire job. MicroFi's tiny runtime almost certainly has no EL engine, making this the most expensive
of the four to embed. Recommendation: **defer** until a minimal predicate evaluator (equals / exists
/ contains on a named attribute) is separately scoped. #1–#3 already deliver the "real ingress +
egress + attribute mutation" goal without EL.

### Build & verify order

1. **`PublishMQTT`** (minimal subset) — unblocks egress.
2. **Real ingress source** — makes it a true edge-data test.
3. **`UpdateAttribute`** (literal values) — attribute mutation.
4. **`RouteOnAttribute`** — deferred, pending a predicate-evaluator scope.

Per processor: add to the static registry (compile-time), keep the Title-Case MiNiFi-C++ property
names so an EFM flow def resolves unchanged, rebuild + reflash on the `steven-matison/MicroFi` fork,
then hand to **StarlinkAI** (where the board lives) for on-hardware verify — register in EFM, push a
flow exercising the processor, confirm the implicit ack and real data movement. That StarlinkAI
verification is a `device:StarlinkAI` follow-up (to file).

## PublishMQTT built + on-hardware registered, 2026-07-31 (`StarlinkAI`, issue #45)

Picked up via [#45](https://github.com/cldr-steven-matison/DesktopShare/issues/45). #26's Mac-side
pass was eval-only (no clone, no code, per its own report), so the actual implementation happened
here instead of a hand-off — checked with Steven first, who confirmed writing it on `StarlinkAI`
directly was fine for this one.

**Built**: `src/processors/publish_mqtt.cpp` on a new `feature/publish-mqtt` branch off
`xiao-s3-2mb-partition`, pushed to `steven-matison/MicroFi` (not upstream). Minimal ESP32 subset per
the design spec above — Broker URI, Client ID, Topic, Quality of Service, Username, Password,
`success` relationship — using ESP-IDF's `esp_mqtt_client_*` API. The client starts lazily on the
first `on_trigger` call (once Broker URI/Topic are known from `on_configure`); a FlowFile that
arrives before the broker's `CONNECTED` event lands is logged and dropped rather than retried —
MicroFi's engine has no session commit/rollback, so a sink that doesn't explicitly transfer a
FlowFile out loses it regardless. Acceptable for a periodic ingress source (next tick just
republishes); flagged in the file's own header comment as worth revisiting before production.

**Toolchain surprise**: the PlatformIO `espressif32` platform now resolves to ESP-IDF **6.0.1**,
which no longer bundles `mqtt` in-tree (`components/mqtt` exists but is an empty stub — component
manager territory now). Fixed by adding `espressif/mqtt: "*"` to `src/idf_component.yml` (the
correct registry name — `espressif/esp-mqtt` from the GitHub repo name doesn't exist as a package;
confirmed via the component registry). Worth remembering if the next processor needs another
component that used to ship in-tree.

**Build**: `esp32s3-2mb` (this specific XIAO's confirmed-correct env, see the 2026-07-29 field
validation above) — **Flash 91.1% (1,074,733 / 1,179,648 bytes)**, up from 88.6% pre-MQTT. Still
fits, but the margin is thin; a future processor may need TLS/OTA trimmed or a bigger partition.
RAM 36.1%, unchanged.

**Flashed and confirmed on real hardware** (COM5, same unit as the 2026-07-29 validation): boots
into the previously-persisted `GenerateFlowFile → LogAttribute` flow (LittleFS untouched by a
reflash, as expected), heartbeats clean (`heartbeat #0 -> 200`), and **the manifest now advertises
three processors** — `GenerateFlowFile`, `LogAttribute`, `PublishMQTT` — with `PublishMQTT`'s
property descriptors matching the design spec exactly (`Broker URI`/`Topic` required, `Quality of
Service` allowable values `0`/`1`/`2`, `Username`/`Password` optional). Confirmed via EFM's API
(`GET /efm/api/agents/microfi_1`): `state: ONLINE`, `agentManifestHash` matches the new build.
**Existing `StarlinkAI`-class agent confirmed unaffected**: `GET
/efm/api/agent-classes/StarlinkAI` unchanged, its agent (`6e6707f3-...`) still `state: ONLINE` in
EFM, and the Windows `Apache NiFi MiNiFi` service is `Running` — untouched by any of this session's
changes (a stale `lastSeen` on that agent is a pre-existing condition already tracked by #11/#25,
not something this session caused).

**Blocked on real data movement**: haven't yet pushed a flow that actually exercises
`PublishMQTT` (e.g. `GenerateFlowFile → PublishMQTT`), because the XIAO's WiFi join
(`ATTyjuHfEi`, same LAN as `WindowsDesktop` at `192.168.1.121` — see the 2026-07-29 LAN-direct
note above) currently has no path to the `SparkPlug` PG's Mosquitto. `CLAUDE-CHECKIN.md` records
Mosquitto as a plain NodePort (`mqtt` namespace, `1883:32478`) on `WindowsDesktop`'s
`cld-streaming` cluster (confirmed via `efm-xiao.md`, not the same-named service on `FTF3XR2065`'s
own local minikube) — unlike EFM/Kafka, it has no `kube-service-ports-efm.kdl` pane exposing it to
either the LAN IP or Tailscale, and adding one is a `WindowsDesktop`-side change per
`agent/incident-rules.md`'s port-forward rule. Filed as
[#52](https://github.com/cldr-steven-matison/DesktopShare/issues/52) (`device:WindowsDesktop`) —
Steven asked for both the LAN and Tailscale exposure, matching the EFM/Kafka paired-pane pattern.
Once that lands, resume here: push `GenerateFlowFile → PublishMQTT`, point `Broker URI` at
whichever address the new pane exposes, and confirm the message actually lands (independent
`mosquitto_sub` check, not just the firmware's own serial log — same rule `efm-xiao.md` already
calls out).

## PublishMQTT real data movement confirmed, 2026-07-31 (`StarlinkAI`, issue #45)

- **EFM Designer never had `PublishMQTT` available to place.** `agent-classes/MicroFi` had no
  `agent-class-manifest-config` mapping, so the Designer kept resolving the class to its original
  manifest (`GenerateFlowFile` + `LogAttribute` only) even though the live agent had already
  registered the newer manifest with `PublishMQTT` — confirmed via `GET
  /efm/api/agent-classes/MicroFi/manifest-diff` (`newManifestAvailable: true`). Fixed with `POST
  /efm/api/agent-class-manifest-config` pinning `MicroFi` to the manifest that includes
  `PublishMQTT`.
- Built `GenerateFlowFile → PublishMQTT` in the Designer (`Broker URI: mqtt://192.168.1.121:1883`,
  `Topic: test/sensor/data`, `QoS 0`) and published. Confirmed via live serial (COM5, `usbipd
  attach --wsl` into the StarlinkAI WSL2 session) that the agent fetched and applied it —
  **EFM's own `/efm/api/agents/{id}` REST view is unreliable for this**: it froze on a stale
  snapshot across real heartbeats and a real reboot; live serial is what actually confirmed
  delivery, consistent with the existing "query Postgres, not the REST heuristics" caution in
  `references/minifi-efm.md`.
- **Found a real engine bug in `steven-matison/MicroFi`.** `Session::transfer()`
  (`src/session.cpp`) matches a relationship name against `bindings_` and returns on the *first*
  match. A one-relationship, multi-connection fan-out (the pre-existing `GenerateFlowFile →
  LogAttribute` connection plus the new `→ PublishMQTT` one, both on `success`) silently starves
  every connection registered after the first — `PublishMQTT` never received a FlowFile as long as
  `LogAttribute` stayed on the same relationship. Confirmed by inspecting the source directly, not
  just inferring from logs.
- **Quick fix applied (not the engine fix):** deleted the `GenerateFlowFile → LogAttribute`
  connection and the now-orphaned `LogAttribute` node, leaving `GenerateFlowFile → PublishMQTT` as
  the flow's only connection. Republished; `PublishMQTT` now receives every FlowFile.
- First retest after that still failed at the transport layer (`transport_base: Failed to open a
  new connection`, repeated disconnects) even though EFM's own LAN pane (port `10090`) was working
  fine — isolating the gap to Mosquitto's LAN pane (`192.168.1.121:1883`, added in `#52`)
  specifically, not general LAN reachability. Steven opened the WindowsDesktop firewall for port
  `1883`; confirmed working on the next retest.
- **Real data movement confirmed end-to-end.** Live serial shows `published 32 bytes to
  'test/sensor/data'` every ~1s; an independent subscriber (Node `mqtt` client against
  `mqtt://100.68.113.126:1883`, run from `StarlinkAI`, not reading the firmware's own log)
  received 60 consecutive `MicroFi GenerateFlowFile payload` messages on `test/sensor/data`. XIAO
  → Mosquitto is proven.
- **Still outstanding:** `Session::transfer()`'s single-binding-per-relationship limitation is
  unfixed — only worked around by removing the fan-out. Any flow needing two consumers on one
  relationship (e.g. bringing `LogAttribute` back alongside `PublishMQTT` for debugging) will hit
  this again until `transfer()` is patched to keep scanning `bindings_` instead of returning on
  the first match, followed by a rebuild + reflash.

## Deeper-testing processors, wrap-up — 2026-07-31 (`StarlinkAI`, issues #45/#26)

Status against the original build order (`PublishMQTT` → real ingress source → `UpdateAttribute`):

**Shipped and verified on hardware:**
- `PublishMQTT` — see the two sections above. XIAO → Mosquitto → independent subscriber confirmed end-to-end.
- `UpdateAttribute` (`feature/update-attribute`, fork commit `ad53dcf`) — literal-value attribute writes
  via 4 declared `Attribute N Name`/`Attribute N Value` property slots (not true dynamic properties —
  EFM's flow validation rejects any property not in the processor's declared list, confirmed on
  hardware, so upstream's arbitrary-key-per-flow shape isn't reachable through the Designer API today).
  Verified via `GenerateFlowFile → UpdateAttribute → LogAttribute`: `verify_key = verify_value` appeared
  in serial output as expected. **This is the build currently flashed on the unit.**

**Attempted, not shipped:**
- `GetGPIO` (real ingress source, reads the onboard BOOT button/GPIO0) — code is correct in isolation and
  compiles clean, but linking the ESP-IDF `driver` component regressed the *whole binary's* stability:
  `PublishMQTT`, which ran error-free for many consecutive minutes everywhere else in this session, started
  throwing MQTT transport errors once `driver` was linked in, and `GetGPIO`'s own state exhibited what looks
  like memory corruption (a `bool` reverting without any code path that should touch it). Root cause not
  found — no debugger or heap-corruption instrumentation available in this session to go further safely.
  Code is on `feature/get-gpio` (fork commit `553688b`), pushed but **not flashed** — the device was
  reverted to the last known-stable build (`feature/update-attribute`) and confirmed clean (236 error-free
  publishes over 60s) before stopping. Don't flash `feature/get-gpio` as-is.

**Two real engine/infra bugs found and documented along the way** (both still open, low urgency —
worked around, not blocking anything currently running):
- `Session::transfer()` only delivers to the first relationship binding that matches by name (fan-out
  silently drops every connection after the first) — see the PublishMQTT section above.
- EFM's manifest store doesn't refresh a processor's property descriptors when its name is already known
  to the agent class, even on a genuine new manifest hash — only a fresh processor *name* reliably gets a
  new manifest record. Bit the `UpdateAttribute` property redesign; workaround (temporarily rename, verify,
  rename back) is documented in the fork commit history.

**Net for #26's original 3-item list: 2 of 3 done** (`PublishMQTT`, `UpdateAttribute`), real ingress
source blocked on the `driver`-component regression. `RouteOnAttribute` remains deferred per the original
design spec (needs an Expression-Language evaluator this runtime doesn't have).

## Can the XIAO run custom Python processors? (eval — 2026-07-31, FTF3XR2065)

Short answer: **not the way NiFi and MiNiFi C++ do it. Custom processors on the XIAO are C++,
compiled into the static registry — the "Python" part is the piece that doesn't port.** Three
layers to it:

**1. The MiNiFi C++ Python extension can't run on an ESP32.** MiNiFi C++ supports Python
processors (and `ExecuteScript` with Python) by embedding a full CPython interpreter — it
dynamically links `libpython` at runtime, needs a system Python install (`libpython3-dev` /
`python3-libs`), and loads `libminifi-python-script-extension.so` through the same `.so` extension
mechanism (confirmed against apache `extensions/python/PYTHON.md`, `main`). None of that exists on
an ESP32: there is no libpython build for ESP-IDF, no `.so`/dlopen loader, and no room — CPython +
stdlib is many MB, and this XIAO unit's *entire* flash is 2 MB with firmware already at ~1.04 MB.
It doesn't fit and there's no port that would make it fit.

**2. MicroFi's architecture rules out the delivery model, not just the size.** MicroFi resolves
processors by name against a **compile-time static registry** — "no `dlopen`, no runtime plugin
load," the design bet this doc opened with. The entire point of a NiFi/MiNiFi Python processor is
*ship a script in the flow definition, no rebuild*. MicroFi is the opposite: adding a processor is
a firmware rebuild + reflash. So even if CPython fit, the "push Python without reflashing" property
— the reason you'd reach for a Python processor — is exactly what MicroFi's model doesn't offer.
And MicroFi exists *because* MiNiFi C++'s heavier machinery (heap-centric, RocksDB, dlopen) doesn't
shrink to a microcontroller (`docs/MICROFI_ASSESSMENT.md`); embedding CPython is strictly heavier
than any of that.

**3. What IS possible.**

- **Custom processors: yes — in C++, compile-time.** That's exactly the #26 processor-dev track
  (`PublishMQTT`, a real ingress source, `UpdateAttribute`). If the goal behind the question is
  "extend the XIAO with our own logic," the answer is yes — just not in Python.
- **An embedded MicroPython scripting processor: buildable in principle, but it's not "MiNiFi
  Python."** MicroPython *does* run on ESP32 (it's a common standalone firmware). One could build a
  C++ MicroFi processor — say `ExecuteMicroPython` — that embeds a MicroPython VM and runs a script
  string carried in the flow def, which *would* restore the "push logic without reflashing"
  property. Three caveats make it a distinct feature, not a port: (a) it's a from-scratch MicroFi
  processor, real work; (b) MicroPython ≠ CPython — reduced stdlib, different C API, so existing
  NiFi/MiNiFi Python processors don't run unchanged; (c) its property/script contract wouldn't match
  MiNiFi C++'s `ExecuteScript`, which **breaks MicroFi's compatibility bet** — an EFM flow def
  written for MiNiFi C++ would no longer resolve unchanged. Worth scoping on its own if wanted, but
  it's a MicroFi-specific scripting capability, not "MiNiFi Python on the XIAO."

This is the same shape as the `RouteOnAttribute` deferral above: the tiny runtime has no embedded
interpreter — whether that's a NiFi Expression-Language evaluator or a Python VM — and every
"just run a script/predicate" feature hits that same wall. Ingress + egress + attribute mutation
(#1–#3 on the shortlist) clear it because they're native C++; anything script-driven doesn't, until
an interpreter is deliberately embedded.

*Verification note:* couldn't re-read the MicroFi repo this session — the `gh` login here is the
work account (`cldr-steven-matison`), which lacks access to the private `Christopheraburns/MicroFi`;
the earlier eval read it as `steven-matison`. The architectural facts above are this doc's prior
captures; the CPython/libpython requirement is freshly confirmed against apache
`extensions/python/PYTHON.md`.

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

## GetGPIO resolved, ListenHTTP shipped — 2026-08-04 (WindowsDesktop, issues #58/#26)

The XIAO moved from StarlinkAI to WindowsDesktop (SSH into StarlinkAI's WSL2 over Tailscale to pull
the `steven-matison/MicroFi` clone — gh CLI on this host has no access to the private fork; the
existing native-Windows clone at `C:\Users\tunas\MicroFi` on StarlinkAI was the real source, cloned
over `ssh://` since a straight `git push` into its currently-checked-out branch is refused by git).
Same MAC (`e0:72:a1:fb:fd:04`) confirmed via `esptool chip-id` before touching anything.

**#58 (`GetGPIO` memory corruption) — closed, no regression found.** ~35 minutes of clean runtime
across multiple boots with `CONFIG_FREERTOS_CHECK_STACKOVERFLOW_CANARY` +
`CONFIG_COMPILER_STACK_CHECK_MODE_STRONG` added (heap poisoning alone, already tried by a prior
session, doesn't cover `FlowEngine::nodes_[]`'s static/BSS storage — correctly flagged then, held
this time). Survived a real chip reset and a real MQTT transport disconnect with the *exact*
original signature (`esp_mqtt_handle_transport_read_error... errno=128`) with zero corruption.
First real physical validation: held the BOOT/GPIO0 button, confirmed `payload: 0` while held,
`1` on release — proves a genuine hardware read, not just "doesn't crash." Root-cause confirmation
via the hardware GDB watchpoint (staged by a prior session, JTAG driver binding is host-specific
and wasn't redone here) is still the only thing that would make this airtight; closed anyway per
direct instruction, reopen if it resurfaces.

Found and fixed a small real bug along the way: `wifi.cpp`'s disconnect handler had no visibility
into *why* a disconnect happened. Added `ESP_LOGW` on `WIFI_EVENT_STA_DISCONNECTED`'s `reason`/
`rssi` fields — this is what caught `WIFI_REASON_NO_AP_FOUND` (201, rssi=-128, real "scan came back
empty") during this session's own WiFi setup, distinguishing it cleanly from an auth failure.

**New processor: `ListenHTTP`** (`src/processors/listen_http.cpp`) — inbound HTTP ingress,
`esp_http_server`-backed, MiNiFi C++-compatible property names (`Listening Port`, `Base Path`).
Fire-and-forget ack, matching MiNiFi C++'s real `ListenHTTP` (not the synchronous
`HandleHttpRequest`/`HandleHttpResponse` pairing built elsewhere in the array today — that needs a
request/response correlation model this single-task engine doesn't have yet, a natural follow-up).
The httpd server's own FreeRTOS task can't safely touch `Session`/`Queue` state directly (engine
state is single-task-owned per `flow_engine.h`), so the URI handler only ever pushes a fixed-size
item onto a small `xQueueCreate`d FreeRTOS queue; `on_trigger` (engine task, every tick) drains it —
same cross-task bridge shape `FlowEngine::apply()` already uses for the C2 task. Verified end-to-end
on hardware: `curl -X POST http://192.168.1.198:8095/test -d "hello from windowsdesktop"` → real
200 in 205ms → `LogAttribute` logged `payload: hello from windowsdesktop`, exact content preserved.

Needed the same `agent-class-manifest-config` pin-to-latest-manifest step documented earlier in this
file for `PublishMQTT` — a `POST` returned "mapping already exists," a `PUT` was needed instead
(though the processor-create API itself worked before the pin took effect either way; the pin's
effect seems scoped to the Designer's palette, not the write API).

**Re-confirmed live**: the `kMaxFlowNodes=4` silent-drop bug (documented earlier in this file) fired
again — pushing the `ListenHTTP` pair on top of the existing 4-node repro flow (6 processors total)
silently dropped `LogAttribute-Repro58` and `PublishMQTT`, only a `WARN` log. Still unfixed, still
worth its own issue.

**Capacity note**: flash is now at 96.8% on this unit's 2MB layout (1,141,317 / 1,179,648 bytes) —
very little headroom left before either trimming a processor or moving to a bigger-flash unit.

Commits on `feature/get-gpio` (`steven-matison/MicroFi`): `7607380` (wifi disconnect-reason
logging), `4e23be8` (`ListenHTTP`). Pushed via the same StarlinkAI-clone relay (this host has no
direct `fork` remote access) — push to `origin` (StarlinkAI's clone) under a temp branch name
(pushing directly to its checked-out `feature/get-gpio` is refused by git), then `ssh` in and
`git merge --ff-only` + `git push fork` from there.
