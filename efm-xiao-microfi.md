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

## What NOT to do

- **Don't push to `Christopheraburns/MicroFi`.** The token allows it. The task doesn't.
- **Don't register MicroFi under the `StarlinkAI` agent class.** That class holds this host's live, Online MiNiFi agent. A shared class means an EFM flow push aimed at one device reaches both. Use a distinct class and verify the existing agent afterward.
- **Don't try to flash from WSL2.** No native USB passthrough; the board enumerates on the Windows side as a `COM` port. PlatformIO runs on the Windows host. `usbipd-win` is a workaround, not the path of least resistance.
- **Don't treat the 48-processor roadmap as available.** Two processors are built. Every capability claim in `Processor-Inventory-And-Roadmap.md` beyond `GenerateFlowFile` and `LogAttribute` is a plan.
- **Don't expect this to feed Kafka.** No `PublishMQTT`, and the `SparkPlug` PG still dead-ends at `EOL`. Both gaps are real and neither is closed by flashing MicroFi.
- **Don't flash the default `esp32s3` env onto a XIAO S3.** Its `partitions.csv` assumes 16 MB; the XIAO has 8 MB.
- **Don't commit `sdkconfig.defaults.local`.** It holds the WiFi passphrase. It's gitignored upstream — keep it that way in any local clone.

## When this ships

Update this doc with the confirmed chip variant, the real firmware size, whether EFM 2.3.1.0-2 accepted a two-processor manifest, and whether the implicit ack worked. If a XIAO-specific board JSON and partition table get written, that's the point at which it's worth asking Chris whether they belong upstream — which is a conversation, not a push.

Update `efm-xiao.md` too: if MicroFi registers cleanly, that plan's "hand-write the sketch" section becomes the fallback rather than the primary path, and the decision point is whether `PublishMQTT` is close enough to wait for.
