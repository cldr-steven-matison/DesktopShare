# The Complete Guide to Edge Flow Management

*by Steven Matison*

> **The published guide lives in → https://github.com/cldr-steven-matison/EdgeFlowManager**
> All chapters, figures, and runnable artifacts are there, with its
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
| **4** ✅ | Yes | Java processor catalog | Done. 114 stock → 122 with the Kafka+scripting NAR drop-in. #121: the not-yet-field-verified SSL/Record-Reader FQCN caveat was **removed** from the chapter; that validation is now field work (**[#122](https://github.com/cldr-steven-matison/DesktopShare/issues/122)**). Known follow-up (unfiled): `Dockerfile.java` needs a new base image (no `minifi-java` registry image exists). |
| **5** ✅ | Yes | ExecuteScript availability (4 paths) | Done. Status table + Paths A–D + phantom-processor & Session-0 traps. |
| **6** ✅ | Yes | MiNiFi custom Python processors | Done. All 6 platform legs proven (incl. CEM Java via `nifi.python.command` in `bootstrap.conf` + a `python3` in the image) and packaged as a runnable Playground scenario. Distinct from `ExecuteScript` (Ch5). |
| **7** ✅ | Yes | Standalone MiNiFi C++ on K8s | Done. v1.26.02 `ListenHTTP → PublishKafka + PutFile` Playground scenario. |
| **8** ✅ | Yes | Standalone MiNiFi Java on K8s (no EFM) | **Rewritten (#121)** to pure standalone, mirroring Ch7: `config.yml`-baked `nifi-minifi-java:latest` (1.23.04-b15), `ListenHTTP → PutFile`, the TCP-probe-not-httpGet gotcha. All EFM references removed — EFM enters at Ch9. Source of truth = the playground repo's `config-java.yml`/`Dockerfile.java`/`minifi-test-java.yaml`. |
| **9** ✅ | Yes | Introduce EFM into the Playground | Done. Level-2 EFM-managed C++ & Java variants built and verified (correct Designer pitch, live positions API-dumped), then decommissioned after proof. Exports: `files/efm/PlaygroundCpp.json`, `PlaygroundJava.json`. |
| **10** ✅ | Yes | MiNiFi C++ & Java as K8s pods | **New chapter (#121)** — Part IV re-themed to *MiNiFi on Kubernetes*. EFM-managed pod pattern for both runtimes (`KubernetesPod` / `KubernetesPodJava`, mirroring `PlaygroundCpp`/`PlaygroundJava`) authored from proven playground YAMLs. **Live production-agent introspection field-validated (#122, 2026-08-06)**: both agents ONLINE since 2026-07-25, real manifest counts corrected (76/16 C++, 122/51 Java — no "stock 114" manifest live anywhere), real applied flows dumped, real resource footprint measured (C++ ~75Mi/BestEffort no limits set; Java ~566Mi combined RSS against its 768Mi/1536Mi request/limit). Found a live instance of the chapter's own manifest-mismatch gotcha (`KubernetesPod`'s agent-reported manifest doesn't match its class-mapped one — currently harmless, worth a look). Ch4's "114/45" processor count is now confirmed stale against the same live manifest (122/51) — not fixed here, flagged for its own pass. |
| **11** ✅ | Yes | Site-to-Site — MiNiFi to NiFi on K8s | **Merged (#121)** old Ch10 (C++) + Ch11 (Java) into one chapter: S2S intro (what/why/how on K8s), shared NiFi side (declarative `User` CR), C++ leg (SSL in `minifi.properties`), Java leg (SSL in `bootstrap.conf`, unmanaged image). Fixed the broken `../images/` path. |
| **12** ✅ | Yes | EFM and MicroFi | Done. From-scratch ESP32 C2 agent (XIAO S3), processors built & verified on hardware, EFM enrollment confirmed. Open upstream: **#56** (`Session::transfer()` fan-out bug) in `steven-matison/MicroFi` — documented as a worked-around engine bug, not fixed. |
| **13** ✅ | **Partial** | EFM and SparkPlug MQTT | Chapter done; **#121** removed the "further design exists…" edge-AI paragraph (belongs to Ch19/20) and the internal issue-# reference — reframed as a protocol-mechanics chapter to revise once the SparkPlug demo field work lands. Field **Partial**: no real embedded device has produced genuine Sparkplug B protobuf yet; `ConsumeMQTTIIoT` Primary-Host/Rebirth untested. **Path identified 2026-08-06** — `EmbeddedSparkplugNode` (ESP32-compatible, `nanopb`-based) targeting the live `xiao-telemetry.ino` sketch; plan + reassignment to `device:StarlinkAI` (XIAO's physical host) in [`efm-sparkplug-b-hardware-lab-plan.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/efm-sparkplug-b-hardware-lab-plan.md), tracked as **[#126](https://github.com/cldr-steven-matison/DesktopShare/issues/126)**. |
| **14** ✅ | Yes | NiFi and AI Skill — EFM Portion | Done. **#121**: skill carved out to its own **public repo [NiFiandAi](https://github.com/cldr-steven-matison/NiFiandAi)** (sanitized — no device names/paths/issue-#s), synced from `skills/nifi-and-ai/` via `skills/publish-skill.sh` (repo→public only), and cross-linked from the chapter + DesktopShare README. |
| **15** ✅📝 | Yes | How to AI with NiFi and Python | Done. The 4 rules, GenericTransform skeleton, FraudModel example, hot-reload. Blog published. |
| **16** ✅ | Partial | How to AI with MiNiFi | **Rewritten (#121)** from war-story to how-to: the four edge-AI options, using the skill + Designer API, custom Python, testing/delivery, and the hard-won traps. StarlinkAI setup/router specifics consolidated into Ch17 (were duplicated). Blog: expand content is #92 (`status:review`); publish deferred. |
| **17** ✅ | Yes | Edge-AI router case study: StarlinkAI | Done. Unified Java `HandleHttpRequest → InvokeHTTP → HandleHttpResponse` on `:8090`, all 5 Lemonade endpoints live incl. the multipart-reassembly fix. Related open elsewhere: **#54** (`device:NvidiaNano`, same C++ drop class, candidate fix not yet applied). |
| **18** 🟡 | Scaffolded | Sample gallery of MiNiFi flows | Scaffolded + folded. Accumulates as remaining flows land (S2S, SparkPlug slots still pending). |
| **19** ✅ | Yes | EFM + NVIDIA Jetson use case | Field-validated (live §7 test on the Jetson; class + agent-row screenshots embedded). Fold tracked by **#69** (`status:todo`, open). Export: `files/efm/WindowsDesktop-TensorRT.json`. **`NvidiaNano` HandleHttp synchronous-flow section landed ([#125](https://github.com/cldr-steven-matison/DesktopShare/issues/125))** — real 3-leg flow (Inference/Matrix/StreamChat), all 5 real Designer/EFM screenshots wired in 2026-08-06. Corrected mid-flight: the class is `NvidiaNano` (Java, current), not `NvidiaNanoJava` (retired field-test class) — noted inline as the device-class-roster shift the chapter's own caveat anticipated. One optional round-trip provenance capture still outstanding, not blocking. |
| **20** 🟡 | **Partial** | SparkPlug Demo — Xiao · Nano · NiFi | Chapter narrative done (trimmed to the pure end-to-end demo; protocol/broker content moved to Ch13). **Live cross-device assembly not done — #109** (`status:in-progress`). Hard blocker: Site-to-Site into production `mynifi-0` needs a `Nifi` CR patch + prod-pod restart (human approval); XIAO power-on also outstanding. Exports: `files/efm/MicroFi.json`, `NvidiaNanoSparkPlug.json`. |
| **21** ✅ | Yes | Metrics & Observability | Done. Layer 1 (EFM actuator) + Layer 2 C++ publisher (Jetson + Windows) into the shared CSO Prometheus/Grafana stack. Java Layer 2's built-in Prometheus endpoint conclusively blocked (platform limit); **unblock designed 2026-08-06** — `SiteToSiteReportingRecordSink` + `PutRecord` (a controller service, not a ReportingTask — EFM Designer has no reporting-task API at all, confirmed 404) confirmed available in the live Java manifest. Field test needs a separate environment (not the live WindowsDesktop cluster); plan + reassignment to `device:FTF3XR2065` in [`efm-metrics-java-s2s-lab-plan.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/efm-metrics-java-s2s-lab-plan.md), tracked as **[#123](https://github.com/cldr-steven-matison/DesktopShare/issues/123)**. |

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

## Subplans (source docs → chapter)

- `efm-binaries-blog.md` — Ch2 blog draft
- `minifi-python-processors.md` — Ch6
- MiNiFi Kubernetes Playground repo (`config-java.yml`, `Dockerfile.java`, `minifi-test-java.yaml`) — Ch8 (standalone Java); the `minifi-test-efm-*.yaml` variants — Ch10 (MiNiFi as k8s pods)
- `minifi-site-to-site.md`, `minifi-site-to-site-lab.md` — Ch11 (merged Site-to-Site)
- `efm-xiao-microfi.md` — Ch12
- `sparkplug-iott.md` — Ch13
- `how-to-ai-with-minifi-blog.md` — Ch16 blog draft (subplan archived at `completed/how-to-ai-with-minifi.md`)
- `beelink-starlink-efm-ai.md` — Ch16/Ch17
- `minifi-sample-gallery.md` — Ch18
- `efm-nvidia-jetson-nano.md` — Ch19
- `sparkplug-demo.md`, `efm-xiao.md` — Ch20
- `efm-metrics.md` — Ch21

# EFM Guide — Completion Summary

## Overall: ~88% complete

| Axis | State | % |
|---|---|---|
| **Field/build validation** | ~18 of 21 "Yes" (Partial: Ch13, Ch20; Ch18 scaffolded) | ~86% |
| **Published prose** | 21 of 21 chapters folded into EdgeFlowManager | 100% |
| **Blended, status-weighted** | ~19 / 21 | ~90% |
| **Issue mailbox** | 94 of 108 closed | ~87% |

## Metric counts

| Metric | Count |
|---|---|
| Chapters (9 parts) | 21 |
| ✅ done / 🟡 in-progress / 🔲 not started | 19 / 2 / 0 |
| Folded chapters (EdgeFlowManager) | 21 files, ~51,400 words |
| Figures | 37 |
| Flow exports (`files/**/*.json`) | 25 |
| Scripts / K8s configs (`files/`) | 91 |
| Source + subplan docs (DesktopShare root) | ~72 `.md` |

