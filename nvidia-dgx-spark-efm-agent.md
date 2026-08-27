# NvidiaSpark-1 as an EFM agent — the class, the flow, and the use cases it unlocks

> **Status (2026-08-26):** work-stream **G** of EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226), issue [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239). The box **landed 2026-08-26 as `spark-dd06`** (Ubuntu 24.04.4 DGX OS, kernel 6.17.0-1031-nvidia, driver 580.173.02, CUDA 13.0, 121 GB usable of 128 GB, LAN `192.168.1.203`, Tailscale not joined — `CLAUDE-CHECKIN.md`), and on-box execution [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235) is the next step: §1 of this doc is the second half of Phase 3. **Decided here:** MiNiFi **Java** as the runtime, agent class `NvidiaSpark-1`, enrollment only through `generateCommand` with a server-minted `agentIdentifier`, a four-front-door class flow, and a fifth `/metrics` leg matching the fleet's existing exporter convention. **Expected, not decided:** the four target endpoint URLs on the box (they follow the Phase-0 model lock and `nvidia-dgx-spark-runbook.md` §2), and every latency number below — the Jetson's numbers are real, the DGX Spark's are not measured yet. Nothing in this doc has been run on `spark-dd06`.

The array already runs four MiNiFi agents against one EFM. Adding a fifth is not new work; what is new is that this one has 121 GB of unified memory behind it, so its class flow is not "sense something and publish it" — it is "be the thing the other four agents call." The Jetson proved that shape one tier down (EFM guide Ch19): a resident GPU daemon on loopback, a MiNiFi Java agent in front of it doing nothing but `HandleHttpRequest → InvokeHTTP → HandleHttpResponse`, and every other device on the LAN getting a real synchronous answer. `NvidiaSpark-1` is that pattern with a bigger engine and four doors instead of one.

## 1. The agent

### Java, not C++ — the fleet already made this call twice

Every agent on this array that has to answer a request runs MiNiFi **Java**. The reason is one missing pair: MiNiFi C++ has no `HandleHttpRequest`/`HandleHttpResponse`, so its `ListenHTTP` gives the caller an empty ack and the real answer has to come back out-of-band over Kafka keyed on a `request_id` (`efm-nvidia-nano-inference.md` "Front door 3"; EFM guide Ch17). For an inference front door that is the whole ballgame. The fleet cut over on that reasoning twice in 2026-08: the Jetson's C++ agent was retired 2026-08-14 in favour of Java `2.24.08.0-19` (`completed/nvidianano-minifi-ops.md`), and StarlinkAI consolidated its C++ and Java classes onto one Java agent (EFM guide Ch17). The DGX Spark starts where they ended up.

Second reason, specific to this box: `ExecuteScript` is absent entirely from the stock CEM MiNiFi Java tarball — no scripting NAR ships at all, only `ExecuteProcess` (`skills/nifi-and-ai/references/minifi-efm.md` §6). That is not a limitation here — the agent is deliberately not where inference runs. It routes; the models live in resident daemons and containers next to it.

### aarch64 install path

MiNiFi Java is the one component in the Cloudera set with **no** container image on the registry — `cloudera/cem-minifi-java`, `cloudera/minifi-java` and `cloudera/cem-minifi` tag-list queries all returned no JSON, and Cloudera's own [MiNiFi Java container-image page](https://docs.cloudera.com/cem/2.3.0/using-minifi-java-agent-container-image/topics/cem-download-minifi-java-agent-image.html) says nothing about x86, ARM, arm64 or aarch64 anywhere (`nvidia-dgx-spark-research.md` §9). So the container question does not arise: the array installs it as a tarball, and that tarball is already proven on the aarch64 Jetson (`completed/nvidianano-minifi-ops.md`). The other 16 Cloudera images the fleet runs *are* multi-arch with `linux/arm64`, confirmed by a direct manifest probe on 2026-08-24 (`nvidia-dgx-spark-research.md` §9) — that covers EFM itself, not the agent.

Java first. The Jetson cost a whole debug cycle to a missing JRE — the agent was recorded as "deployed and online" on a host with no `/usr/lib/jvm/` at all (`efm-nvidia-nano-inference.md`).

```bash
# expected — verify on the box
sudo apt install -y openjdk-21-jre-headless
java -version                      # expect openjdk 21.x, aarch64
mkdir -p ~/minifi-java-deploy && cd ~/minifi-java-deploy
```

Install layout mirrors the Jetson exactly, so one runbook covers both:

| | Jetson (`NvidiaNano`, as-built) | DGX Spark (`NvidiaSpark-1`, planned) |
|---|---|---|
| Version | `2.24.08.0-19` | same tarball, same version |
| Install dir | `~/minifi-java-deploy/minifi-2.24.08.0-19` | `/home/tunas/minifi-java-deploy/minifi-2.24.08.0-19` |
| C2 config | `conf/bootstrap.conf` (**not** `minifi.properties`) | same |
| App log | `logs/minifi-app.log` | same |
| Service | SysV `/etc/init.d/minifi-java`, surfaced by systemd's sysv-generator | same — expect `systemctl is-enabled minifi-java` → `disabled`, which is **not** a fault; boot start comes from the `rc2.d/S65minifi-java` link |
| Runs as | root, drops to the desktop user via `sudo -u` | root → `tunas` |

Source for the Jetson column: `completed/nvidianano-minifi-ops.md`. The service unit shape is the deployer's, not ours — it is generated by the enrollment script in the next section, and hand-editing it is how you lose the drop-to-user step that keeps display-bound legs working.

### Enrollment — `generateCommand`, once, with a fresh identifier

**Never hand-build the deployer command and never reuse an `agentIdentifier`.** The only sanctioned sources are EFM's Deploy Agent CLI screen or `POST /efm/api/agent-deployer/generateCommand` with `agentIdentifier` omitted, so the server mints a collision-free one (`agent/incident-rules.md` "EFM agent deployment"; `skills/nifi-and-ai/references/minifi-efm.md` §4). The recorded failure mode is exact: a Java agent re-enrolled with a hand-built `curl` that reused a retired agent's identifier, and the C2 `UPDATE` pushing its flow failed twice with `state: FAILED`. This is a brand-new class on a brand-new host — there is no identifier to inherit.

```bash
# expected — verify on the box
curl -s -X POST http://192.168.1.121:10090/efm/api/agent-deployer/generateCommand \
 -H 'Content-Type: application/json' \
 -d '{
   "agentClass": "NvidiaSpark-1",
   "agentType": "java",
   "agentVersion": "2.24.08.0-19",
   "osArch": "linux",
   "baseUrl": "http://192.168.1.121:10090/efm/api",
   "hbPeriod": 5000,
   "serviceUser": "tunas",
   "serviceName": "minifi-java",
   "autoConfigureSecurity": false,
   "trustSelfSignedCertificates": false
 }'
# → run the returned command verbatim, from ~/minifi-java-deploy. Do not edit any -d field.
```

Two prerequisites on the EFM side, both already true on WindowsDesktop and both worth re-confirming before the POST: `binaries/java/linux/2.24.08.0-19/` — the same platform-agnostic Java tarball, not an aarch64 leaf — has to be staged into EFM's binaries PVC or the deployer serves nothing (`completed/efm-windows-java-minifi.md`, `completed/minifi-playground-java-processors.md`), and EFM's Jetty takes ~2 minutes to bind on a cold start, so poll `/efm/actuator/health` before running the deployer rather than racing it (`skills/nifi-and-ai/references/minifi-efm.md` §3).

**As built, 2026-08-27 (spark-dd06).** `java -version` → `openjdk 21.0.12` (from `files/issue-226/spark-bootstrap.sh`). The `generateCommand` POST above, sent verbatim with no `agentIdentifier`, returned the deployer command; EFM served the Java binary (`agent-deployer/binary?agentType=java&agentVersion=2.24.08.0-19&osArch=linux`, 214 MB `application/gzip`). The command was saved as `~/minifi-java-deploy/enroll-NvidiaSpark-1.sh` and run once with `sudo` — the deployer needs root (`EUID == 0`, writes `/etc/init.d/minifi-java`). Two things differ from the table above: the deployer installed to **`/home/tunas/minifi-2.24.08.0-19`** (the service user's home, not `~/minifi-java-deploy/…`), and the service is `systemctl is-active minifi-java` → `active` via systemd's sysv-generator (`/run/systemd/generator.late/minifi-java.service`, `SourcePath=/etc/init.d/minifi-java`), running as root and dropping to `tunas` with `sudo -u tunas` — the Jetson shape exactly. `conf/bootstrap.conf` carries `c2.agent.class=NvidiaSpark-1`, `c2.rest.path.base=http://192.168.1.121:10090/efm/api`. Heartbeat proof from EFM's side: `GET /efm/api/agent-classes` shows `NvidiaSpark-1` with manifest `d81ca4b5-…`, and `GET /efm/api/agent-manifests/d81ca4b5-…` is `agentType: minifi-java`, `version: 2.24.08.0-19`, 20 bundles — a manifest only exists once the agent has heartbeated. Note for the next reader: on this EFM build `GET /efm/api/agents` answers `404 No static resource` — the class/manifest pair and `GET /efm/api/events` are the API-side liveness checks; the fleet board is the UI one.

Then the one line that is not optional on this fleet:

```properties
# expected — verify on the box; conf/bootstrap.conf, then restart the agent
c2.full.heartbeat=false
c2.agent.heartbeat.period=5000
```

`c2.full.heartbeat` defaults to `true` on the Java agent and a full heartbeat carries the entire runtime manifest. Measured on this fleet 2026-08-22: 1.25 MB per beat every 5 seconds on the Jetson, 1.31 MB on WindowsDesktop, ~377 MB of heartbeat payload in ten minutes into EFM's 2 GB heap. With the flag off, the Jetson went from 1,245,184 B to 7,462 B per beat — **167×** (`completed/nvidianano-minifi-ops.md`). A fifth Java agent with the default on is a straightforward way to OOM EFM.

### Heartbeat, and the liveness trap

The class is `NvidiaSpark-1` — device name, EFM agent class and GitHub label are the same string across the fleet by convention (`CLAUDE-CHECKIN.md`, `nvidia-dgx-spark-plan.md` §4).

**`lastSeen` on the agent entity is not liveness.** It freezes while heartbeats flow perfectly fine; the durable signal is `efm_heartbeat_count_total{agentId=...}` off `/efm/actuator/prometheus`, and `efm_heartbeat_lastSeenTime_seconds` for seconds-since-beat (`completed/nvidianano-minifi-ops.md`, `efm-observability.md`). Two more registry facts that cost debug cycles on this fleet: every manifest change mints a new `agentManifestId` label value, so one physical box accumulates several series and you always aggregate with `max by`/`sum by`; and EFM never garbage-collects a retired agent record, so a stale one keeps a red "N agents failed to update" badge lit indefinitely (`efm-observability.md`).

## 2. The class flow v1 — four front doors and a meter

The Jetson's flow is three `HandleHttp` legs into local daemons — `:8080 /classify → 127.0.0.1:5910` (trt-infer), `:8081 /streamChatListener → :5902` (mpv), `:8082 /matrixListener → :5901` (matrix) — plus a fourth `:9936 /metrics` leg (`completed/nvidianano-minifi-ops.md`, `efm-observability.md`). Same skeleton here, different cargo: on the Jetson two of three legs drive a display, on the DGX Spark all four legs are inference.

```text
NvidiaSpark-1 class flow (EFM-designed, C2-pushed)

  :8190 /classify   → InvokeHTTP → local VLM        ┐
  :8191 /transcribe → InvokeHTTP → local Whisper    │  each leg:
  :8192 /reason     → InvokeHTTP → local LLM /v1    │  HandleHttpRequest → InvokeHTTP
  :8193 /embed      → InvokeHTTP → local TEI        ┘   → HandleHttpResponse-OK (200)
                                                        → HandleHttpResponse-Error (502)
  :9936 /metrics    → ExecuteStreamCommand → 200 (Prometheus exposition, §4)
```

Every leg is the same four-processor shape and one shared `StandardHttpContextMap` controller service. Per-leg detail:

| Leg | Listener | Target on the box | Request | Response |
|---|---|---|---|---|
| `/classify` | `:8190` | `#{vlm.url}` — a local VLM (candidate: Cosmos Reason 2 8B from the [VSS playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vss/README.md), or `gemma3:4b` on Ollama `:11434` per the [Live VLM WebUI playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/live-vlm-webui/README.md)) | raw JPEG bytes, `application/octet-stream` | JSON: labels + confidence, same envelope the Jetson returns |
| `/transcribe` | `:8191` | `#{whisper.url}` — Whisper on GPU | WAV/PCM bytes | JSON transcript |
| `/reason` | `:8192` | `#{llm.url}` — OpenAI-compatible `/v1/chat/completions` | chat-completions JSON, passed through | the model's JSON response, passed through |
| `/embed` | `:8193` | `#{tei.url}` — text-embeddings-inference | `{"inputs": [...]}` | float vectors |

The four target URLs live in an **EFM parameter context**, not in the processor properties. That is what makes the Phase-0 model lock a one-parameter change instead of a flow edit, and it is the same trick the production `CSOOperatorAppWindows` PG already uses on WindowsDesktop, where `FlowParams` holds `vLLM Base URL`, `WhisperServerUrl`, `Qdrant Url` and `Kafka Broker Endpoint` as non-sensitive parameters (`cso-prod-1-cutover-plan.md`, export `files/cso-prod-1/flows/prod/CSOOperatorAppWindows.flow.json`). The values themselves are not decided: `nvidia-dgx-spark-runbook.md` §2 stands the first endpoint up on `:8888`, the [vLLM playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vllm/README.md) uses `:8000`, [SGLang](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/sglang/README.md) `:30000`, Ollama `:11434`. Resolve them on the box during #235 and write them into the parameter context once.

**What changes from the Jetson.** Four things, and only one of them is about the GPU:

1. **A VLM instead of a 7.5 MB TensorRT engine.** The Jetson's `/classify` fronts a resident daemon on `127.0.0.1:5910` holding a MobileNetV2 FP16 engine — 4.05 ms p50 GPU inference with preprocessing costing 8× that (`efm-nvidia-nano-inference.md`). On the DGX Spark the same door fronts a real vision-language model, so the answer is a description rather than an ImageNet-1k label — and the latency will be a different order of magnitude. Nothing in the corpus measures a VLM's per-image latency on GB10; that number gets measured here (`nvidia-dgx-spark-research.md` §5 has decode tok/s for text models, nothing for images).
2. **Four legs, not three, plus the meter.** More doors on one agent means more `HandleHttpRequest` listeners sharing one context map, and each listener's `container-queue-size` needs setting deliberately rather than left at default.
3. **The daemons are containers, not user systemd units.** The Jetson's `trt-infer.service` is a `systemctl --user` unit. On this box the serving tier comes up under Docker 29.2.1 with `nvidia-ctk` 1.20.0 (`CLAUDE-CHECKIN.md`), or inside k3s once `nvidia-dgx-spark-k3s-cso.md` lands. Either way the rule the Jetson taught holds: **the model lives in the resident process, never in the processor** — `systemctl --user restart trt-infer` reloaded the model mid-session and the agent never noticed.
4. **The agent is not on the tailnet yet.** Tailscale is not installed on `spark-dd06` (`CLAUDE-CHECKIN.md`), so v1 is LAN-only at `192.168.1.203` and every caller is a 192.168.1.x device. The static reservation and the Tailscale join are `nvidia-dgx-spark-runbook.md` work, not agent work.

**Three settings that are not defaults and are not optional**, all learned the hard way on this fleet (`skills/nifi-and-ai/references/minifi-efm.md` §13, `efm-nvidia-nano-inference.md`):

- `InvokeHTTP` timeouts `Connection 5 secs` / `Socket Read 10 secs` / `Socket Write 10 secs`, not the 15 s framework default. A local daemon that answers in milliseconds should not make a caller hang for fifteen seconds on a failure that was knowable immediately. Whisper and a long-context LLM call are the exceptions — size their read timeouts to the real work, per leg.
- Route `Retry` (HTTP 500–599) to the **same terminal `HandleHttpResponse`** as `Failure`/`No Retry`. A `Retry` self-loop copied from a working template loops forever and the caller never gets an answer.
- `penaltyDuration: 0 sec` on every `InvokeHTTP`. It is a top-level field on `componentConfiguration`, invisible in the Designer's property list, and defaults to 30 seconds — so any 5xx adds a flat ~30 s hang before the error response ever leaves.

Cost of the wrapper, measured on the Jetson: 132 ms p50 / 258 ms p95 through the Java agent against 14.9 ms straight to the daemon on loopback — about 117 ms of FlowFile repository, scheduling and Jetty (`efm-nvidia-nano-inference.md`). Expect the same order here; the GB10 makes the model faster, not the agent.

**Build it through the Designer API, not by hand.** `POST /efm/api/designer/flows/{flowId}/process-groups/{pgId}/processors` per component, one `POST` per connection, `revision.version: 0` on every create, `GET .../validate` clean before `POST .../publish` — there is no whole-flow `PUT` (`skills/nifi-and-ai/references/minifi-efm.md` §7). EFM canvas pitch is 300 rows / 600–900 columns and a linear chain runs **vertically**, which is not the NiFi pitch (`skills/nifi-and-ai/references/layout.md`).

## 3. Out-of-box use cases

Ten flows that work the day the agent is up, ordered roughly by how little new work each needs. "Reuses" names a real export in this repo or the EFM guide; the DGX Spark leg is the new part in every row.

| # | Use case | Shape | Reuses | Chapter |
|---|---|---|---|---|
| 1 | **Jetson → DGX Spark escalation** | Jetson `/classify` answers from MobileNetV2; low-confidence results get re-POSTed to `192.168.1.203:8190/classify` for a VLM second opinion | `NvidiaNanoJava` class flow (EFM guide Ch19); [files/efm/NvidiaNanoJava.json](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/files/efm/NvidiaNanoJava.json) | ch13 |
| 2 | **MicroFi-2 camera → VLM** | OV2640 `CaptureImage` → MQTT `microfi2/camera/jpg` → NiFi `ConsumeMQTT` → `InvokeHTTP` to `/classify` → Kafka | `files/cso-prod-1/flows/prod/MicroFi2CameraBridge.flow.json` (already MQTT→Kafka; add the inference hop) | ch13 |
| 3 | **NiFi-on-WindowsDesktop → DGX Spark inference** | Repoint `FlowParams` `vLLM Base URL` / `WhisperServerUrl` at the Spark box; no processor edit | `files/cso-prod-1/flows/prod/CSOOperatorAppWindows.flow.json` (sub-PGs `StreamTovLLM`, `StreamToWhisper`) | ch13, ch10 |
| 4 | **AMOLED voice clip → transcript → answer → glass** | `CaptureAudio` publishes a WAV broker-direct plus a JSON meta FlowFile → NiFi → `/transcribe` → `/reason` → `InvokeHTTP` POST to the board's `:8095 /message` → `DisplayMessage` | `files/cso-prod-1/flows/prod/AmoledShakeToDisplay.flow.json` (the `InvokeHTTP`-to-board leg exists and returns 200 in ~0.3 s); `efm-waveshare-amoled.md` | ch13 |
| 5 | **AMOLED shake → LLM one-liner** | `GetIMU` shake → Kafka `amoled.imu` → `/reason` for a short generated line → `DisplayMessage` instead of the fixed `SHAKE HH:mm:ss` string | same export as #4 | ch13 |
| 6 | **Twitch chat → classifier** | `TwitchChatBot` chat events → `/classify` (text) or `/reason` for intent/toxicity scoring → back into `ChatTriggers` | `files/cso-prod-1/flows/prod/TwitchChatBot.flow.json` (16 processors, sub-PG `ChatTriggers`) | ch13, ch10 |
| 7 | **Streamer summariser** | Clip metadata and watchlist rows → `/reason` → a generated summary published with the post | `files/cso-prod-1/flows/prod/StreamersApp.flow.json`, `files/cso-prod-1/flows/prod/WatchlistChatSnapshotPoller.flow.json` | ch13 |
| 8 | **Sparkplug B anomaly scoring** | Sparkplug device metrics → NiFi → `/reason` with a rolling window as context → anomaly verdict back to Kafka | `files/cso-prod-1/flows/prod/SparkPlug.flow.json` (5 processors); EFM guide Ch20 | ch13, ch11 |
| 9 | **Doc ingestion into the local KB** | `ParseDocument` → `ChunkDocument` → `/embed` → Qdrant, the vendor-documented CFM ingestion shape with our own embed endpoint | design work; `nvidia-dgx-spark-research.md` §10 carries the processor chain and the Qdrant/TEI arm64 evidence | ch13, ch15 |
| 10 | **IMU stream → LLM narrator** | `AmoledImuBridge` MQTT→Kafka leg unchanged; a new PG consumes `amoled.imu` and asks `/reason` for a plain-English motion description | `files/cso-prod-1/flows/prod/AmoledImuBridge.flow.json` (3 processors) | ch13 |

Four rules govern every row, and they are not negotiable because each one has an incident behind it:

- **New NiFi logic goes in its own new Process Group**, never inline in a running shared one. `AmoledImuBridge` and `MicroFi2CameraBridge` were each built as their own root-canvas PG beside the existing ones for exactly this reason (`efm-amoled-capabilities.md`).
- **Never GET-then-PUT a NiFi processor that has sensitive properties.** `TwitchChatBot` and `WatchlistChatJoiner` both bind `twitch-chat-bot-creds`, 7 parameters, all sensitive (`cso-prod-1-cutover-plan.md`). A GET masks them as `********` and the PUT writes that literal back, destroying the credential. Use the Parameter Context.
- **Row 3 is a cutover, not an experiment.** WindowsDesktop's vLLM on `:8000` also serves the OpenClaw Telegram bridge's model — the bridge fails silently with `llm request failed` if that endpoint moves (`CLAUDE-CHECKIN.md`, [#192](https://github.com/cldr-steven-matison/DesktopShare/issues/192)). Repoint `FlowParams` only after the bridge itself has been repointed and proven, and keep the rollback one parameter away. The rung order lives in `nvidia-dgx-spark-k3s-cso.md`.
- **Confirm before any restart of a live service**, fresh, every time — and never `kubectl delete pod mynifi-0` as a restart, because that NiFi's repositories are `emptyDir` and the delete wipes the flow (`agent/incident-rules.md`).

Rows 1, 2, 4, 5 and 10 are what makes this class interesting: the DGX Spark is not a peer of the edge devices, it is the tier they escalate *to*. That is the argument `files/nvidia-spark-guide/ch13-edge-ai-use-cases-jetson-to-spark.md` makes, and the corpus is honest that nobody else has made it — the completeness critic found **zero sources linking a DGX Spark to the array's Jetson/MicroFi/AMOLED devices or to EFM-fed sensor data**, and zero repos combining a DGX Spark with any Cloudera component (`files/issue-226/research/critic.json`). Every row above is first-of-its-kind integration work.

## 4. Observability

Three independent layers, none of which replaces the others.

**Layer 1 — EFM heartbeat.** Free the moment the agent enrolls. Prometheus already scrapes EFM's actuator on WindowsDesktop, so `NvidiaSpark-1` appears as a new `agentClass` label the first time it beats (`efm-observability.md`). The fleet board gets one more seconds-since-heartbeat tile (green <120 s / yellow <600 s / red beyond) and one more sawtooth line; the dashboard JSON is EFM guide Ch21's, source of truth [files/efm-fleet-dashboard.json](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/files/efm-fleet-dashboard.json).

**Layer 2 — the flow-level exporter.** The Java agent's built-in Prometheus endpoint is conclusively blocked on an EFM-managed headless agent — embedded web API off, `nifi.web.http.*` on the C2 denylist, no Prometheus NAR in the build. The pattern that ships instead is a fifth `HandleHttp` leg on the class flow serving Prometheus exposition format on `:9936`, via `ExecuteStreamCommand` running a base64-wrapped `sh` script (`ExecuteStreamCommand` mangles inline quoted `sh -c`; the base64 wrapper is mandatory). Live today on NvidiaNano, WindowsDesktop and StarlinkAI (`efm-observability.md`).

On this box the script has more to say than `/proc/loadavg` and `/proc/meminfo`. Two GB10 facts shape it: `nvidia-smi` reports `Memory-Usage: Not Supported` because an integrated GPU has no dedicated framebuffer, and `cudaMemGetInfo` ignores memory recoverable from swap under unified memory so allocatable memory reads low — NVIDIA's own guidance is to read `/proc/meminfo` instead ([known-issues.html](https://docs.nvidia.com/dgx/dgx-spark/known-issues.html)). Our box shows exactly that (`CLAUDE-CHECKIN.md`). So **every memory gauge on this device comes from `/proc/meminfo`, never from an NVML memory call.**

Cluster side, reuse the external-target pattern verbatim: a selector-less `Service` plus manual `Endpoints` at `192.168.1.203:9936`, a `ServiceMonitor` labeled `release: prometheus`, and the Prometheus-3 fix that the flow-level responder always needs because it sends no `Content-Type`:

```bash
# as-built (efm-observability.md) — the same patch NvidiaNano and StarlinkAI needed
kubectl patch servicemonitor nvidiaspark1-minifi-metrics -n cld-streaming --type merge \
  -p '{"spec":{"fallbackScrapeProtocol":"PrometheusText0.0.4"}}'
```

Two reachability notes. Cluster→Jetson on `:9936` needed **zero** `ufw` changes, and the diagnostic that proved it is worth repeating: a `connection refused` means the host answered and the port was closed, while a firewall drop looks like a *timeout*. Read the error text before touching a firewall. And the target address is per-device and only an in-cluster test decides it — the Beelink scrapes over Tailscale while the Jetson and WindowsDesktop scrape over LAN (`efm-observability.md`). Run the busybox-pod `wget` test from inside the cluster against `192.168.1.203:9936` before writing the `Endpoints`.

**Layer 3 — host and GPU telemetry, which the agent does not carry.** Three options, all arm64-native, none of them EFM's business:

| Tool | What it gives | Port |
|---|---|---|
| [ateska/dgx-spark-prometheus](https://github.com/ateska/dgx-spark-prometheus) | single-binary Go exporter plus a systemd unit — CPU usage/temp/freq, GPU utilization/temp/freq/power, RAM, disk I/O, network; 5 s scrape recommended | 9835 |
| [MiaAI-Lab/sparkDash](https://github.com/MiaAI-Lab/sparkDash) | web dashboard with a unified-memory pool breakdown and LLM stats — decode/prefill tok/s, KV cache, queue depth | 5555 |
| [NVIDIA DGX Dashboard](https://docs.nvidia.com/dgx/dgx-spark/dgx-dashboard.html) | the built-in update/telemetry/JupyterLab UI, reached over an SSH tunnel or NVIDIA Sync | 11000 |

`dgx-spark-prometheus` on `:9835` is the one that belongs in the CSO Prometheus, wired with the same selector-less-Service pattern as `:9936`. It is a second scrape target on the same host, not a replacement — `:9936` says the *agent* is healthy, `:9835` says the *box* is. Expect GPU utilization to read 0 % from any NVML-based collector: traditional utilization metrics do not apply to unified memory, per the [community NVML shim thread](https://forums.developer.nvidia.com/t/nvml-support-for-dgx-spark-grace-blackwell-unified-memory-community-solution/358869). Grafana's provisioned Prometheus datasource UID on this stack is `PBFA97CFB590B2093`, not `prometheus` — a dashboard JSON with the wrong UID renders every panel "No data" while Prometheus is fine (`efm-observability.md`).

## 5. Resources and assets EFM pushes

The class needs no Python assets — Java `ExecuteScript` cannot run Python, and pushing Python at a Java class is a live failure mode, not a harmless leftover: three orphaned Python assets left assigned to a class after a C++→Java migration produced a `SYNC RESOURCE` operation failing every ~10 minutes with `Resource content retrieval failed with HTTP return code 500`, permanently (`skills/nifi-and-ai/references/minifi-efm.md` §14). Check what is assigned before assuming the class is clean:

```bash
# expected — verify on the box
curl -s http://192.168.1.121:10090/efm/api/agent-class-resource-manager/NvidiaSpark-1/assigned
```

What the class *does* want pushed is small and shell-shaped:

| Asset | Type | Why it goes through EFM |
|---|---|---|
| the `/metrics` exposition script | `ASSET` | so the exporter is EFM-designed and C2-pushed like the other three devices' — no agent-host config, survives republish |
| model/endpoint config (a JSON of the four target URLs) | `ASSET` | one file to diff when the model lock changes; the parameter context stays the runtime source |

Mechanics, from `skills/nifi-and-ai/references/minifi-efm.md` §9: `POST /efm/api/resource-manager/resources/file` (multipart, returns a SHA-512 digest to diff against a local `sha512sum`), then `PUT /efm/api/agent-class-resource-manager/NvidiaSpark-1/save` with a body that is **exactly** `{"resourceIdsToBeAssigned":[...],"resourceIdsToBeUnassigned":[...]}` — a bare array or `{"resourceIds":[...]}` returns `200 OK` and assigns nothing. There is no in-place update: changing an assigned asset is unassign → delete → upload as new → reassign.

Anything larger — model weights, engine files, container images — does **not** go through EFM. The Jetson rule stands: don't check in a `.engine`, it is bound to that GPU and that TensorRT version; keep the build line instead (`efm-nvidia-nano-inference.md`).

## 6. Gallery entries this produces

The EFM guide's sample gallery (EFM guide Ch18) takes a card only after the flow is field-validated somewhere in the guide. Three cards come out of this work-stream, in this order:

1. **`spark-inference-router-java`** — the four-front-door class flow. Agent: MiNiFi Java `2.24.08.0-19`, class `NvidiaSpark-1`, EFM-managed. Shape: four `HandleHttpRequest → InvokeHTTP → HandleHttpResponse` triples on `:8190`–`:8193` plus one shared `StandardHttpContextMap`. Verification: one `curl` per door returning a real body and a 200, and one deliberate bad payload returning 502 fast rather than hanging. Successor to EFM guide Ch18's Entry 9 (Edge-AI Router), one tier up.
2. **`spark-metrics-exporter-java`** — the `:9936 /metrics` leg with the GB10-specific `/proc/meminfo` script. Verification: `up{job="nvidiaspark1-minifi-metrics"}=1` in Prometheus with real values, and a fleet-board row.
3. **`jetson-to-spark-escalation`** — the two-agent flow from use case 1, the first card in the gallery that spans two EFM classes. Verification: a low-confidence Jetson classification arriving as a VLM answer, with both agents' `agentId`s in the trace.

Each card carries the standard fields — name, purpose, agent, shape, files, verification, status — and links its flow export rather than duplicating it.

## 7. What NOT to do

- **Don't hand-build the deployer command, and never reuse an `agentIdentifier`.** `generateCommand` with `agentIdentifier` omitted, or EFM's Deploy Agent CLI screen. Nothing else.
- **Don't leave `c2.full.heartbeat` at its default.** 1.25 MB every 5 seconds into a 2 GB heap, times five agents.
- **Don't read `lastSeen` as liveness.** It freezes while heartbeats flow. Use `efm_heartbeat_count_total`.
- **Don't put the model in the processor.** Resident daemon or container, thin front door. The Jetson proved the cost of the alternative: `ExecuteScript` re-reads its script every trigger, so nothing stays resident.
- **Don't leave `InvokeHTTP`'s `penaltyDuration` at 30 s or wire `Retry` back to itself.** One adds a flat 30 s to every error; the other hangs the caller forever.
- **Don't GET-then-PUT a NiFi processor with sensitive properties**, and don't add new logic inline in a live Process Group — new PG, every time.
- **Don't start an ad-hoc `kubectl port-forward` or `minikube tunnel` for any of this.** The canonical forwards live as zellij panes in the **kube-service-ports-efm.kdl** layout under `~/.config/zellij/layouts/` on WindowsDesktop; check what is already running and reuse it. A LAN-exposed port there also needs a Windows Firewall inbound rule — the `netsh advfirewall firewall add rule ... localport=9936` lesson, and before it the Mosquitto `:1883` one (`efm-observability.md`, `CLAUDE-CHECKIN.md`).
- **Don't move WindowsDesktop's vLLM `:8000` to the DGX Spark without repointing the OpenClaw bridge first.** It fails silently.
- **Don't `kubectl delete pod mynifi-0` to restart NiFi.** `emptyDir` repositories; the delete wipes the flow.
- **Don't claim MiNiFi Java "supports ARM" from Cloudera's docs.** The docs do not say it; the tarball-on-aarch64 precedent does. Cloudera ships a `cfmctl-linux-arm64` CLI and the CSA/CSM system-requirements pages are architecture-silent — the [registry manifest probe](https://container.repository.cloudera.com/v2/) is what actually confirms the container images (`nvidia-dgx-spark-research.md` §9).
- **Don't pick a listener port without checking the box for a collision.** `:8090` is the Live VLM WebUI's UI port, `:3100` belongs to `dgx-agentskills`, `:11000` to the DGX Dashboard, `:9835` to `dgx-spark-prometheus`. Run `ss -tlnp` first.

## Open questions

- The four target endpoint URLs. They follow the Phase-0 model lock, which is still open and is Steven's call — `nvidia-dgx-spark-landscape.md` §6 presents candidates. Until then the parameter context holds placeholders.
- Which VLM answers `/classify`. The corpus offers Cosmos Reason 2 8B (the VSS blueprint) and `gemma3:4b` on Ollama, neither with a measured per-image latency on GB10 (`nvidia-dgx-spark-research.md` §5).
- Which Whisper build. [whisperx-blackwell](https://github.com/Mekopa/whisperx-blackwell) reports 24 minutes of audio in 62 s on GPU against ~2 hours on CPU fallback, about 115×, by forcing `get_device_capability()` to return `(9,0)`; whisper.cpp needs `CMAKE_CUDA_ARCHITECTURES="120;121"` and Ubuntu 24.04 in the container because DGX OS ships GLIBC 2.38 ([forum thread](https://forums.developer.nvidia.com/t/running-whisper-cpp-stt-server-on-dgx-spark-gb10-arm64-cuda-13-via-docker/371803)). Upstream [faster-whisper](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/README.md) mentions no CUDA 13, ARM or sm_121 at all. Pick one on the box, measure it, then decide whether WindowsDesktop's `:8001` Whisper moves.
- Whether the four legs live on one agent or two classes. StarlinkAI consolidated two classes into one and was better for it (EFM guide Ch17); four inference legs plus a meter on one flow is still more than any agent on this fleet carries today.
- Tailscale. Once `spark-dd06` joins, does the in-cluster scrape reach `:9936` over LAN or over the tailnet? The Beelink's answer was the opposite of the Jetson's, and only an in-cluster test decides it.

## Definition of done

- `NvidiaSpark-1` enrolled via `generateCommand` with a server-minted `agentIdentifier`, heartbeating to `http://192.168.1.121:10090/efm/api`, visible as an online agent in EFM.
- `c2.full.heartbeat=false` applied and confirmed the right way — a *new* `agentManifestId` series with small beats, not a falling number on the old series.
- The class flow published with four `HandleHttp` legs, `GET .../validate` clean before publish, and one `curl` per door returning a real body from another LAN device.
- All four `InvokeHTTP` processors carry non-default timeouts, `penaltyDuration: 0 sec`, and `Retry` routed to the terminal error response.
- The `:9936` leg scraped: `up{job="nvidiaspark1-minifi-metrics"}=1` with real values, `fallbackScrapeProtocol` set, and a `NvidiaSpark-1` row on the fleet board.
- `dgx-spark-prometheus` on `:9835` scraped as a second target on the same host, with every memory gauge sourced from `/proc/meminfo`.
- At least one use case from §3 running end-to-end from a device that is not the DGX Spark — use case 1 or 2 is the cheapest proof.
- The class's flow definition exported and checked in under `files/` before anything republishes it.

## When this ships

- `CLAUDE-CHECKIN.md`'s `NvidiaSpark-1` block gets the agent row: version, install dir, class, the EFM-minted `agentIdentifier`, the five listener ports, and the log path — the same shape the `NvidiaNano` block already carries.
- Every `# expected — verify on the box` block above becomes an `# as-built` block with the real values, and the four parameter-context URLs get written down.
- `nvidia-dgx-spark-plan.md` §4 flips G to done and Phase 3's gate ("EFM shows `NvidiaSpark-1` online") closes; #235's execution thread gets the enrollment comment.
- The three chapters this doc feeds get their first real content: `files/nvidia-spark-guide/ch12-efm-agent-class-nvidiaspark-1.md` (§1–§2), `files/nvidia-spark-guide/ch13-edge-ai-use-cases-jetson-to-spark.md` (§3), `files/nvidia-spark-guide/ch14-observability.md` (§4).
- Anything here that changes a canonical flow shape goes back into the `nifi-and-ai` skill — `skills/nifi-and-ai/references/minifi-efm.md` for enrollment or Designer-API changes, and a skill change always lands as its own commit.
- The gallery cards in §6 get filed against EFM guide Ch18 once each is field-validated.

## Resources

- Companion docs: `nvidia-dgx-spark-plan.md` (EPIC spine) · `nvidia-dgx-spark-research.md` §5, §9, §10 · `nvidia-dgx-spark-runbook.md` (the endpoints this agent fronts) · `nvidia-dgx-spark-landscape.md` (model lock) · `nvidia-dgx-spark-k3s-cso.md` (cutover ladder) · `nvidia-dgx-spark-local-kb.md` (use case 9) · `nvidia-dgx-spark-cloudera-demos.md` · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- Fleet precedent: `completed/nvidianano-minifi-ops.md` (the agent ops runbook this one copies) · `efm-nvidia-nano-inference.md` (resident daemon plus thin front doors, measured) · `efm-nvidia-jetson-nano.md` (EFM on Kubernetes, binary staging, Kafka NodePort) · `efm-observability.md` (the exporter pattern and the fleet board) · `efm-metrics.md` · `efm-operations-manual.md` · `efm-waveshare-amoled.md` · `efm-amoled-capabilities.md` · `cso-prod-1-cutover-plan.md`
- Rules: `agent/incident-rules.md` "EFM agent deployment" · `skills/nifi-and-ai/SKILL.md` · `skills/nifi-and-ai/references/minifi-efm.md` §1, §4, §7, §9, §13, §14 · `skills/nifi-and-ai/references/layout.md`
- Flow exports reused in §3: `files/cso-prod-1/flows/prod/MicroFi2CameraBridge.flow.json` · `files/cso-prod-1/flows/prod/CSOOperatorAppWindows.flow.json` · `files/cso-prod-1/flows/prod/AmoledShakeToDisplay.flow.json` · `files/cso-prod-1/flows/prod/AmoledImuBridge.flow.json` · `files/cso-prod-1/flows/prod/TwitchChatBot.flow.json` · `files/cso-prod-1/flows/prod/StreamersApp.flow.json` · `files/cso-prod-1/flows/prod/SparkPlug.flow.json` · `files/cso-prod-1/flows/prod/WatchlistChatSnapshotPoller.flow.json`
- EFM guide: [Ch17 Edge-AI Router](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch17-edge-ai-router.md) · [Ch18 Sample Gallery](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch18-sample-gallery.md) · [Ch19 EFM and NVIDIA Jetson](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch19-efm-and-nvidia-jetson.md) · [Ch21 Metrics and Observability](https://github.com/cldr-steven-matison/EdgeFlowManager/blob/main/ch21-metrics-and-observability.md)
- External: [DGX Dashboard](https://docs.nvidia.com/dgx/dgx-spark/dgx-dashboard.html) · [GB10 known issues](https://docs.nvidia.com/dgx/dgx-spark/known-issues.html) · [dgx-spark-prometheus](https://github.com/ateska/dgx-spark-prometheus) · [sparkDash](https://github.com/MiaAI-Lab/sparkDash) · [whisperx-blackwell](https://github.com/Mekopa/whisperx-blackwell) · [whisper.cpp on GB10](https://forums.developer.nvidia.com/t/running-whisper-cpp-stt-server-on-dgx-spark-gb10-arm64-cuda-13-via-docker/371803) · [Live VLM WebUI playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/live-vlm-webui/README.md) · [VSS playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vss/README.md) · [Cloudera MiNiFi Java container image](https://docs.cloudera.com/cem/2.3.0/using-minifi-java-agent-container-image/topics/cem-download-minifi-java-agent-image.html)
