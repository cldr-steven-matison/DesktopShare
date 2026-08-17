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
| **1** ✅📝 | Yes | EFM on Kubernetes | Done.  Blog published. |
| **2** ✅ | Yes | EFM Binaries & staging tree | Done. |
| **3** ✅ | Yes | C++ processor catalog | Done. |
| **4** ✅ | Yes | Java processor catalog | Done. |
| **5** ✅ | Yes | ExecuteScript availability (4 paths) | Done. |
| **6** ✅ | Yes | MiNiFi custom Python processors | Done.  |
| **7** ✅ | Yes | Standalone MiNiFi C++ on K8s | Done. |
| **8** ✅ | Yes | Standalone MiNiFi Java on K8s (no EFM) | Done. |
| **9** ✅ | Yes | Introduce EFM into the Playground | Done. |
| **10** ✅ | Yes | MiNiFi C++ & Java as K8s pods | Done. |
| **11** ✅ | Yes | Site-to-Site — MiNiFi to NiFi on K8s | Done |
| **12** 🟡 | Yes | EFM and MicroFi | Prose cleaned (bug count corrected to three). Agent-liveness LED strobe live on all three units 2026-08-15 ([#171](https://github.com/cldr-steven-matison/DesktopShare/issues/171) ✓ — red LED confirmed charger-IC hardware, GPIO21 the only drivable LED). MicroFi-1/2/3 R&D plan ([#134](https://github.com/cldr-steven-matison/DesktopShare/issues/134) ✓) closed 2026-08-12. Capstone structural content (final flows, custom processors, custom Python) still WIP — now re-anchored on fresh child [#178](https://github.com/cldr-steven-matison/DesktopShare/issues/178) (device:WindowsDesktop). New related edge work: [#176](https://github.com/cldr-steven-matison/DesktopShare/issues/176) (MicroFi-1 `!m`/`!l` → screen4). |
| **13** 🟡 | **Partial** | EFM and SparkPlug MQTT | Re-authored: stale "embedded Sparkplug B unsolved" prose corrected (hardware confirmed) and widened to cover both MiNiFi C++ **and** Java. Two-leg NiFi section updated 2026-08-14 for the live wiring ([#164](https://github.com/cldr-steven-matison/DesktopShare/issues/164)): `ExtractDeviceId` on the JSON leg, MicroFi-3 unified-firmware `PublishSparkplug` feeding the spB leg. MiNiFi Java native Sparkplug B decode field-**VERIFIED** 2026-08-15 ([#163](https://github.com/cldr-steven-matison/DesktopShare/issues/163) ✓ — `nifi-cdf-iiot-mqtt-nar` drop-in, zero parse.failure, decoded values match publisher). Remaining (all under [#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138)): NiFi-side `PublishKafka` round-trip on both consume legs + live XIAO, and the rebirth-request in/out decision (edge-side C++ decode still simulator-only). |
| **14** 🟡 | Yes | NiFi and AI Skill — EFM Portion | Delivered & **closed on review 2026-08-15** ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141) ✓): skill verified at exact parity with public [NiFiandAi](https://github.com/cldr-steven-matison/NiFiandAi) (diff clean, no internal terms, sync-skills clean); chapter's closer + reference table trued to the published skill, public clone link in place. Demo/field work done; **chapter prose pending Steven's read-through feedback.** |
| **15** ✅📝 | Yes | How to AI with NiFi and Python | Done. Blog published. |
| **16** 🟡 | Yes | How to AI with MiNiFi | Delivered & **closed on review 2026-08-15** ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141) ✓): chapter verified in the HOW-to shape (four edge-AI options, method, silent-drop traps, what-NOT-to-do), Ch19 on-device cross-links in place, public skill clone link added. Demo/field work done; **chapter prose pending Steven's read-through feedback.** |
| **17** ✅ | Yes | Edge-AI router case study: StarlinkAI | Re-authored to the whole-story arc: `StarlinkAIJava`→`StarlinkAI` class rename, unified-flow intro, and the consolidated `:8096` screen/matrix leg added. Complete. |
| **18** 🟡 | Scaffolded | Sample gallery of MiNiFi flows | SparkPlug two-leg card added 2026-08-14 as Entry 10 ([#167](https://github.com/cldr-steven-matison/DesktopShare/issues/167) ✓, unblocked by [#164](https://github.com/cldr-steven-matison/DesktopShare/issues/164)); pending list now empty. Two Site-to-Site cards (Ch11 C++ + Java) added earlier; Entry-7 link + S2S attribution fixed. |
| **19** 🟡 | Yes | EFM + NVIDIA Jetson use case | Java metrics path CONFIRMED 2026-08-14 ([#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166) ✓): flow-level `:9936` Prometheus exporter live, `up=1`, Grafana panel rendering; the #139 firewall/scrape question resolved empirically in the same pass. Round-trip verification **closed on review 2026-08-17** ([#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165) ✓): EFM has **no provenance view** — chapter section rewritten to Monitoring-Active per-processor counters + status-API byte reconciliation, figure captured, stale `:8090` port refs trued to live `:8080`. **All Ch19 issues closed (#139/#166/#165) — stream fully delivered; chapter prose pending Steven's read-through feedback.** |
| **20** 🟡 | **Yes** | SparkPlug Demo — Xiao · Nano · NiFi | Live `PublishKafka` wiring done + re-exported 2026-08-14 ([#164](https://github.com/cldr-steven-matison/DesktopShare/issues/164) ✓): both legs proven with real MicroFi traffic — JSON leg keyed `MicroFi-1` via new `ExtractDeviceId`, Sparkplug B leg fed by MicroFi-3's new unified-firmware `PublishSparkplug`. Remaining: S2S leg blocked on a human decision. |
| **21** 🟡 | Yes | Metrics & Observability | Layer 2 complete across all three exporter hosts 2026-08-15: NvidiaNano ([#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166) ✓), WindowsDesktop ([#170](https://github.com/cldr-steven-matison/DesktopShare/issues/170) ✓), StarlinkAI over Tailscale ([#169](https://github.com/cldr-steven-matison/DesktopShare/issues/169) ✓) — host rows live on the EFM Fleet board; fleet-dashboard + heartbeat-semantics prose folded into Ch21. Layer 3 verdict delivered 2026-08-15 ([#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140)): EFM drops the MicroFi heartbeat's `status.microfi.littleFs*` fields and re-exports nothing from the heartbeat body — the storage-metrics panel is **not buildable via EFM**; finding documented in Ch21 + `efm-metrics.md`, MicroFi fleet rows (heartbeat-transport series) stand as the Layer-3 slice; storage counters need device egress. **#140 REOPENED (status:todo, device:WindowsDesktop) with fresh feedback:** `efm-observability.md` is out of sync with WindowsDesktop work and screenshots must be added to the MD. |

## Close plan — v2 ([EPIC #137](https://github.com/cldr-steven-matison/DesktopShare/issues/137))

The v1 close plan (#59, written 2026-07-31) is done and closed — stale by the time it closed, since everything in it shipped. **[EPIC #137](https://github.com/cldr-steven-matison/DesktopShare/issues/137)** is the active plan: demos-first — finish the demos, wire the live flows through to observability, complete the `nifi-and-ai` skill, land the Nvidia Nano and Sparkplug B demos. Each 🟡 WIP chapter and its gating work-stream:

Status as of **2026-08-17**. Only **two child issues remain open** (#138 A, #140 C — both `device:WindowsDesktop`); everything else in the plan has closed on review.

| WIP Ch | Gating work-stream (child issue) |
|---|---|
| 12 EFM and MicroFi | F · MicroFi-1/2/3 R&D plan ([#134](https://github.com/cldr-steven-matison/DesktopShare/issues/134) ✓ closed 2026-08-12). Capstone structural content (final flows/processors/Python) re-anchored on **[#178](https://github.com/cldr-steven-matison/DesktopShare/issues/178) — OPEN**, device:WindowsDesktop. Related edge work: [#176](https://github.com/cldr-steven-matison/DesktopShare/issues/176). |
| 13 EFM and SparkPlug MQTT | A · Sparkplug B end-to-end ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138) — **OPEN**). Java decode field-verified ([#163](https://github.com/cldr-steven-matison/DesktopShare/issues/163) ✓); remaining = NiFi PublishKafka round-trip + rebirth-request decision. |
| 14 NiFi and AI Skill | D · **closed on review** 2026-08-15 ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141) ✓) — skill at public parity, Ch14 trued. Prose pending Steven's read-through. |
| 16 How to AI with MiNiFi | D · **closed on review** 2026-08-15 ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141) ✓) — HOW-to shape verified, public clone link added. Prose pending Steven's read-through. |
| 18 Sample gallery | SparkPlug card ([#167](https://github.com/cldr-steven-matison/DesktopShare/issues/167) ✓) + Ch10/11 S2S cards added — pending list empty. Grows further with the [#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138) end-to-end flow. |
| 19 EFM + NVIDIA Jetson | B ✓ ([#139](https://github.com/cldr-steven-matison/DesktopShare/issues/139)); metrics ✓ ([#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166)); round-trip verification ✓ ([#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165)) — **all issues closed, stream fully delivered.** Prose pending Steven's read-through. |
| 20 SparkPlug Demo | A · Sparkplug B end-to-end ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138) — **OPEN**). PublishKafka wiring + re-export ✓ ([#164](https://github.com/cldr-steven-matison/DesktopShare/issues/164)); remaining = XIAO `ListenHTTP` actuation round-trip live-confirm. |
| 21 Metrics & Observability | C · observability completeness ([#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140) — **REOPENED, OPEN**). Layer-2 (3 hosts) + Layer-3 verdict delivered; fresh feedback = `efm-observability.md` out of sync with WindowsDesktop + screenshots into the MD. |

Work-stream **E** ([#142](https://github.com/cldr-steven-matison/DesktopShare/issues/142)) is **verified end-to-end 2026-08-14**: the `TwitchChatBot` → StarlinkAI `:8096` repoint (all four `InvokeStarlink*` legs incl. matrix, #136) was found already live, and a real Twitch matrix command drove the screen with the processor's counters confirming the `:8096` path. Housekeeping done 2026-08-10: #123 (Java S2S metrics) and #126 (real-hardware Sparkplug B) closed — both were complete but still open.

**Review sweep (2026-08-15).** Eight issues closed on Steven's review in one pass: [#156](https://github.com/cldr-steven-matison/DesktopShare/issues/156) (QueryIceberg), [#159](https://github.com/cldr-steven-matison/DesktopShare/issues/159) (skill layout rules), [#164](https://github.com/cldr-steven-matison/DesktopShare/issues/164) (SparkPlug Kafka legs), [#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166)/[#169](https://github.com/cldr-steven-matison/DesktopShare/issues/169)/[#170](https://github.com/cldr-steven-matison/DesktopShare/issues/170) (flow-level Prometheus exporters — Nano, StarlinkAI, WindowsDesktop), [#167](https://github.com/cldr-steven-matison/DesktopShare/issues/167) (Ch18 card), [#171](https://github.com/cldr-steven-matison/DesktopShare/issues/171) (MicroFi liveness LED). Net effect on the work-streams: **B**'s technical scope is done (only the [#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165) provenance screenshot remains for Ch19); **C** is narrowed to the Layer-3 MicroFi panel; **A**'s wiring children are closed (remaining: [#163](https://github.com/cldr-steven-matison/DesktopShare/issues/163) decode field-verify + the S2S-leg human decision).

**Chapter cleanup + re-author pass (2026-08-14).** Every WIP chapter's stale first-draft prose was corrected against current live/source state and the re-author-ready chapters (Ch13, Ch17, Ch19, Ch20) were brought forward; in-flight sections stay marked pending. Remaining per-chapter demo/field/observability work is now tracked by five new focused issues under this EPIC: [#163](https://github.com/cldr-steven-matison/DesktopShare/issues/163) (Ch13 Java Sparkplug decode), [#164](https://github.com/cldr-steven-matison/DesktopShare/issues/164) (live PublishKafka wire + re-export), [#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165) (Ch19 provenance shot), [#166](https://github.com/cldr-steven-matison/DesktopShare/issues/166) (Java-agent metrics panel), [#167](https://github.com/cldr-steven-matison/DesktopShare/issues/167) (Ch18 SparkPlug card).

**Status reconciliation (2026-08-17).** Tracker trued to the live mailbox: **151 of 164 issues closed (~92%)**. Since the 08-15 sweep, [#165](https://github.com/cldr-steven-matison/DesktopShare/issues/165) (Ch19 round-trip) closed on review 08-17, taking work-stream **B** fully done. **Only two EPIC children remain open, both `device:WindowsDesktop`:** [#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138) (A — Sparkplug B end-to-end: NiFi PublishKafka round-trip + XIAO actuation + rebirth-request decision) and [#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140) (C — reopened: `efm-observability.md` sync + screenshots into the MD). Ch12's capstone R&D (was orphaned after #134 closed) is now re-anchored on fresh child [#178](https://github.com/cldr-steven-matison/DesktopShare/issues/178). One flag for final sessions: chapters whose demo/field work is complete (Ch14/16/17/19) are still 🟡 pending Steven's prose read-through, not a technical gap. New related edge tickets outside guide-close scope: [#176](https://github.com/cldr-steven-matison/DesktopShare/issues/176).

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
| **Field/build validation** | 17 of 21 "Yes" (Partial: Ch13, Ch16, Ch20; Ch18 scaffolded) | ~81% |
| **Published prose** | 21 of 21 chapters folded into EdgeFlowManager | 100% |
| **Blended, status-weighted** | ~19 / 21 | ~90% |
| **Issue mailbox** | 151 of 164 closed (2026-08-17; #165 Ch19 round-trip closed on review since the 08-15 sweep) | ~92% |

## Metric counts

| Metric | Count |
|---|---|
| Chapters (9 parts) | 21 |
| ✅ done / 🟡 in-progress / 🔲 not started | 13 / 8 / 0 |
| Folded chapters (EdgeFlowManager) | 21 files, ~51,400 words |
| Figures | 37 |
| Flow exports (`files/**/*.json`) | 25 |
| Scripts / K8s configs (`files/`) | 91 |
| Source + subplan docs (DesktopShare root) | ~72 `.md` |

