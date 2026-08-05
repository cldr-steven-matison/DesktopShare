# The Complete Guide to Edge Flow Management

*by Steven Matison*

> **The published guide lives in → https://github.com/cldr-steven-matison/EdgeFlowManager**
> (extracted 2026-08-05). All chapters, figures, and runnable artifacts are there, with its
> `README.md` as the reader entry point and single source of truth for the guide's structure.
> **Do all guide work in EdgeFlowManager** — DesktopShare's `guide/` is only a redirect stub.
>
> This document is the **internal status tracker of record**: per-chapter status, field-validation
> state, source docs, and genuinely-open work. It is not the guide. Construction history (who folded
> what, when, and which issue drove it) lives in git, the source docs, and the extracted chapters —
> not here.


Edge Flow Management is the central manager for organizing agent Classes, Resources, and Edge Flows.
NiFi in the datacenter is well documented; EFM is not — until now. What happens out at the edge — a
MiNiFi agent on a Jetson, a Windows box over Tailscale, a Kubernetes pod with no persistent identity
— is where the real problems live: binary delivery, agent enrollment, which processors actually
exist in which build, managing custom processors and resources, and getting a flow from a designer
canvas onto a device that keeps changing its IP. Every chapter marked ✅ points at a source doc and a
flow that actually ran on real hardware.

> **Close plan → [#59](https://github.com/cldr-steven-matison/DesktopShare/issues/59)** is the
> authoritative to-do list for finishing. This tracker stays the per-chapter status of record.

## Status legend

✅ done / field-validated · 🟡 in-progress · 🔲 not started · 📝 blog published

- **Ch · Status** — chapter number and status icons.
- **Field** — field-validation state (Yes / Partial / No).
- **Chapter** — title; the chapter file is `chNN-…` in EdgeFlowManager.
- **Status / open items** — current state and anything genuinely still open. Issues base URL:
  `https://github.com/cldr-steven-matison/DesktopShare/issues/`.

## Status tracker

| Ch · Status | Field | Chapter | Status / open items |
|---|---|---|---|
| **1** ✅📝 | Yes | EFM on Kubernetes | Done. 8-phase deploy, Postgres + 2-PVC persistence (incl. the `efm-resources` trap). Blog published. |
| **2** ✅ | Yes | EFM Binaries & staging tree | Done. Five-leaf staging tree, C++/ARM unpack-inject-repack, Windows MSI Path A/B, Maven NAR build. EFM Binaries blog tracked in #60 (closed). |
| **3** ✅ | Yes | C++ processor catalog | Done. 74 x86_64 / 79 aarch64 / 81 Windows MSI; ARM64 extra-extensions confirmed on NvidiaNano. |
| **4** ✅ | Yes | Java processor catalog | Done. 114 stock → 122 with the Kafka+scripting NAR drop-in. Known follow-up (unfiled): `Dockerfile.java` needs a new base image (no `minifi-java` registry image exists). |
| **5** ✅ | Yes | ExecuteScript availability (4 paths) | Done. Status table + Paths A–D + phantom-processor & Session-0 traps. |
| **6** ✅ | Yes | MiNiFi custom Python processors | Done. All 6 platform legs proven (incl. CEM Java via `nifi.python.command` in `bootstrap.conf` + a `python3` in the image) and packaged as a runnable Playground scenario. Distinct from `ExecuteScript` (Ch5). |
| **7** ✅ | Yes | Standalone MiNiFi C++ on K8s | Done. v1.26.02 `ListenHTTP → PublishKafka + PutFile` Playground scenario. |
| **8** ✅ | Yes | MiNiFi Playground Java setup | Done. End-to-end on WindowsDesktop minikube, incl. real Kafka produce+consume round trip. |
| **9** ✅ | Yes | Introduce EFM into the Playground | Done. Level-2 EFM-managed C++ & Java variants built and verified (correct Designer pitch, live positions API-dumped), then decommissioned after proof. Exports: `files/efm/PlaygroundCpp.json`, `PlaygroundJava.json`. |
| **10** ✅ | Yes | S2S: MiNiFi C++ → NiFi K8s | Done. Secure S2S over HTTPS/mTLS to CFM-operator NiFi; peer authorized declaratively via the operator's `User` CR. Lab: `minifi-site-to-site-lab.md`. |
| **11** ✅ | Yes | S2S: MiNiFi Java → NiFi K8s | Done on the `s2s-lab` profile. Fix: set `nifi.minifi.security.*` + `nifi.minifi.flow.use.parent.ssl=true` durably in `bootstrap.conf` (Java regenerates `minifi.properties` from it each start); shipped as a custom unmanaged `minifi-java` image. Recipe: `files/site-to-site/ch11-java/`. |
| **12** ✅ | Yes | EFM and MicroFi | Done. From-scratch ESP32 C2 agent (XIAO S3), processors built & verified on hardware, EFM enrollment confirmed. Open upstream: **#56** (`Session::transfer()` fan-out bug) in `steven-matison/MicroFi` — documented as a worked-around engine bug, not fixed. |
| **13** ✅ | **Partial** | EFM and SparkPlug MQTT | Chapter done. Field **Partial**: no real embedded device has produced genuine Sparkplug B protobuf yet — every binary-payload test is `pysparkplug` on a workstation; `ConsumeMQTTIIoT` Primary-Host/Rebirth behavior untested. |
| **14** ✅ | Yes | NiFi and AI Skill — EFM Portion | Done. The `nifi-and-ai` skill's EFM machinery as the Part VI lead-in. |
| **15** ✅📝 | Yes | How to AI with NiFi and Python | Done. The 4 rules, GenericTransform skeleton, FraudModel example, hot-reload. Blog published. |
| **16** ✅ | Partial | How to AI with MiNiFi | Chapter done (StarlinkAI unified Java router section). Blog: expand content is #92 (`status:review`); publish intentionally deferred. |
| **17** ✅ | Yes | Edge-AI router case study: StarlinkAI | Done. Unified Java `HandleHttpRequest → InvokeHTTP → HandleHttpResponse` on `:8090`, all 5 Lemonade endpoints live incl. the multipart-reassembly fix. Related open elsewhere: **#54** (`device:NvidiaNano`, same C++ drop class, candidate fix not yet applied). |
| **18** 🟡 | Scaffolded | Sample gallery of MiNiFi flows | Scaffolded + folded. Accumulates as remaining flows land (S2S, SparkPlug slots still pending). |
| **19** ✅ | Yes | EFM + NVIDIA Jetson use case | Field-validated (live §7 test on the Jetson; class + agent-row screenshots embedded). Fold tracked by **#69** (`status:todo`, open). Export: `files/efm/WindowsDesktop-TensorRT.json`. |
| **20** 🟡 | **Partial** | SparkPlug Demo — Xiao · Nano · NiFi | Chapter narrative done (trimmed to the pure end-to-end demo; protocol/broker content moved to Ch13). **Live cross-device assembly not done — #109** (`status:in-progress`). Hard blocker: Site-to-Site into production `mynifi-0` needs a `Nifi` CR patch + prod-pod restart (human approval); XIAO power-on also outstanding. Exports: `files/efm/MicroFi.json`, `NvidiaNanoSparkPlug.json`. |
| **21** ✅ | Yes | Metrics & Observability | Done. Layer 1 (EFM actuator) + Layer 2 C++ publisher (Jetson + Windows) into the shared CSO Prometheus/Grafana stack. Java Layer 2 conclusively blocked — a platform limit (no standalone Prometheus reporting-task NAR; C2 `UPDATE_PROPERTIES` denylisted), not open-ended. |

## What's left

The guide is extracted and largely complete. Open guide work (live issues):

- **[#59](https://github.com/cldr-steven-matison/DesktopShare/issues/59)** — EPIC: finish the guide (close plan); the authoritative to-do list.
- **[#73](https://github.com/cldr-steven-matison/DesktopShare/issues/73)** — guide-wide consistency + publish-readiness pass.
- **[#109](https://github.com/cldr-steven-matison/DesktopShare/issues/109)** — Ch20 live end-to-end SparkPlug assembly (blocked on S2S into `mynifi-0` + XIAO power-on).
- **[#106](https://github.com/cldr-steven-matison/DesktopShare/issues/106)** — Ch12 / Ch13 / Ch20 epic.
- **[#92](https://github.com/cldr-steven-matison/DesktopShare/issues/92)** — Ch16 blog: add content (`status:review`).
- **[#69](https://github.com/cldr-steven-matison/DesktopShare/issues/69)** — Ch19 fold (`status:todo`).
- **[#56](https://github.com/cldr-steven-matison/DesktopShare/issues/56)** — `Session::transfer()` fan-out bug, open upstream in `steven-matison/MicroFi` (worked around in Ch12).

Adjacent / future: **[#75](https://github.com/cldr-steven-matison/DesktopShare/issues/75)** native NiFi processor guide · **[#76](https://github.com/cldr-steven-matison/DesktopShare/issues/76)** NiFi/MiNiFi build-automation & release-vote system · **[#116](https://github.com/cldr-steven-matison/DesktopShare/issues/116)** adopt Site-to-Site on WindowsDesktop.

> **Incoming:** a new `SensorClass` agent class and a new physical device for the IoT/edge demo
> stacks. Not checked in yet (see `CLAUDE-CHECKIN.md`) — when it lands, revisit Ch19–20's device
> assignment; it may take over or extend the Jetson's role.

## Guide structure

The part/chapter layout is defined once, in **[EdgeFlowManager's `README.md`](https://github.com/cldr-steven-matison/EdgeFlowManager#table-of-contents)** — the published table of contents. It is the single source of truth; this tracker deliberately does not duplicate it (that duplication is what drifted and had to be fixed under #111).

## Repos, paths, promotion flow

| Repo | Path (Mac) | Role |
|---|---|---|
| DesktopShare | `~/Documents/GitHub/DesktopShare` | This tracker, source docs, subplans, blog drafts |
| EdgeFlowManager | `~/Documents/GitHub/EdgeFlowManager` | **The published guide** — chapters, figures, runnable artifacts |
| MiNiFi Kubernetes Playground | `~/Documents/GitHub/MiNiFi Kubernetes Playground` | Runnable scenarios (additive layout) |
| ClouderaStreamingOperators | `~/Documents/GitHub/ClouderaStreamingOperators` | EFM + CSO K8s manifests |
| NiFi2 Processor Playground | `~/Documents/GitHub/NiFi2 Processor Playground` | Custom Python/Java processors (companion) |
| Blog | `~/Documents/GitHub/cldr-steven-matison.github.io` | Jekyll `_posts/`, published on commit |

Per-device paths (WindowsDesktop, StarlinkAI, Jetson, Macbook, droplet) live in `CLAUDE-CHECKIN.md`.

Content promotion: `DesktopShare root (in-progress)` → `completed/` (done iterating) → `blog/`
(polished draft) → blog repo `_posts/YYYY-MM-DD-Title.md` (published on commit).

## Subplans (source docs → chapter)

- `efm-binaries-blog.md` — Ch2 blog draft
- `minifi-python-processors.md` — Ch6
- `minifi-site-to-site.md`, `minifi-site-to-site-lab.md` — Ch10–11
- `efm-xiao-microfi.md` — Ch12
- `sparkplug-iott.md` — Ch13
- `how-to-ai-with-minifi-blog.md` — Ch16 blog draft (subplan archived at `completed/how-to-ai-with-minifi.md`)
- `beelink-starlink-efm-ai.md` — Ch16/Ch17
- `minifi-sample-gallery.md` — Ch18
- `efm-nvidia-jetson-nano.md` — Ch19
- `sparkplug-demo.md`, `efm-xiao.md` — Ch20
- `efm-metrics.md` — Ch21

## Ground rules while building this

- **Live state outranks docs:** dump live `flow.json.gz`, hit health endpoints, `git log` before editing. Full incident background in `agent/incident-rules.md`.
- **Never GET-then-PUT a NiFi processor with sensitive properties** — the masked `********` writes back literal and destroys the credential. Use Parameter Contexts or `/run-status`.
- **Confirm before any restart or redeploy of a live service**; drain in-flight `InvokeHTTP` first.
- **Cross-reference, don't cross-link.** A chapter's content comes from its source doc(s) (the Subplans map above) — write the real content into the chapter and name its source, rather than linking out. Update the source doc in the same pass whenever a chapter changes; the source is never left to drift.
- **Keep `efm-guide-summary.md` in sync** whenever a chapter's status changes here. That file holds the high-level completion snapshot only (overall %, metric counts, chapter status list) — per-chapter detail and next actions stay here and in the issues.
- Commit only when explicitly asked (except the finish-an-issue ritual — see `agent/device-comms.md`).
