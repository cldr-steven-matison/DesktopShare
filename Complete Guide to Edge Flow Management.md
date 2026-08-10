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
| **12** 🟡 | Yes | EFM and MicroFi | Done. WIP |
| **13** 🟡 | **Partial** | EFM and SparkPlug MQTT | WIP — real hardware now confirmed producing genuine Sparkplug B ([#126](https://github.com/cldr-steven-matison/DesktopShare/issues/126), 2026-08-06); remaining gaps are rebirth-request and edge-side decode, both still simulator-only |
| **14** 🟡 | Yes | NiFi and AI Skill — EFM Portion | Done. WIP |
| **15** ✅📝 | Yes | How to AI with NiFi and Python | Done. Blog published. |
| **16** 🟡 | Partial | How to AI with MiNiFi | WIP |
| **17** ✅ | Yes | Edge-AI router case study: StarlinkAI | Done. |
| **18** 🟡 | Scaffolded | Sample gallery of MiNiFi flows | WIP |
| **19** 🟡 | Yes | EFM + NVIDIA Jetson use case | WIP |
| **20** 🟡 | **Partial** | SparkPlug Demo — Xiao · Nano · NiFi | WIP |
| **21** 🟡 | Yes | Metrics & Observability | WIP |

## Close plan — v2 ([EPIC #137](https://github.com/cldr-steven-matison/DesktopShare/issues/137))

The v1 close plan (#59, written 2026-07-31) is done and closed — stale by the time it closed, since everything in it shipped. **[EPIC #137](https://github.com/cldr-steven-matison/DesktopShare/issues/137)** is the active plan: demos-first — finish the demos, wire the live flows through to observability, complete the `nifi-and-ai` skill, land the Nvidia Nano and Sparkplug B demos. Each 🟡 WIP chapter and its gating work-stream:

| WIP Ch | Gating work-stream (child issue) |
|---|---|
| 12 EFM and MicroFi | F · MicroFi-1/2/3 ([#134](https://github.com/cldr-steven-matison/DesktopShare/issues/134)) — **stays open until the full R&D lands; capstone chapter collecting all final flows, custom processors, and custom Python** |
| 13 EFM and SparkPlug MQTT | A · Sparkplug B end-to-end ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138)) |
| 14 NiFi and AI Skill | D · complete + publicly sync the skill ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141)) |
| 16 How to AI with MiNiFi | D · complete skill + How to AI with MiNiFi ([#141](https://github.com/cldr-steven-matison/DesktopShare/issues/141)) |
| 18 Sample gallery | A · SparkPlug card ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138)) + promote Ch10/11 S2S cards |
| 19 EFM + NVIDIA Jetson | B · Nano → observability ([#139](https://github.com/cldr-steven-matison/DesktopShare/issues/139)) |
| 20 SparkPlug Demo | A · Sparkplug B end-to-end ([#138](https://github.com/cldr-steven-matison/DesktopShare/issues/138)) |
| 21 Metrics & Observability | C · observability completeness ([#140](https://github.com/cldr-steven-matison/DesktopShare/issues/140)) |

Work-stream **E** ([#142](https://github.com/cldr-steven-matison/DesktopShare/issues/142)) hardens the already-done Ch17 live-stream path (repoint central NiFi's `TwitchChatBot` to StarlinkAI's new `:8091–8094`). Housekeeping done 2026-08-10: #123 (Java S2S metrics) and #126 (real-hardware Sparkplug B) closed — both were complete but still open.

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
| **Issue mailbox** | 114 of 129 closed (2026-08-10; +2 closed #123/#126, +6 open Close Plan v2 EPIC/children) | ~88% |

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

