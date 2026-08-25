# The Complete Developer Guide for NVIDIA DGX Spark with Cloudera

*by Steven Matison*

> **Status (2026-08-24):** Tracker of record for the guide, work-stream **J** of EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226) ([#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242)). The guide skeleton (README table of contents + 22 chapter stubs) is staged at `files/nvidia-spark-guide/`; the public repo is cut when the first field-validated chapter exists, after the box lands. This document is the internal status tracker — per-chapter status, field-validation state, source doc, driving issue — mirroring `Complete Guide to Edge Flow Management.md`. It is not the guide.

The DGX Spark is documented as a personal AI supercomputer and as nothing else. What is missing — and what this guide is for — is the box as a node in a working Cloudera platform: inference endpoint for NiFi and Flink, Kubernetes host for Cloudera Streaming Operators on Arm, EFM-managed edge agent, home of a local knowledge base for Claude Code, and the desk-side prototype that promotes unchanged into Cloudera AI on AWS.

**Naming rule (every chapter, every doc):** *DGX Spark* is the NVIDIA box; *Apache Spark* is the engine RAPIDS accelerates. Never bare "Spark" in a Cloudera-integration sentence.

## Status legend

✅ done / field-validated · 🟡 in-progress · 🔲 not started (stub) · 📝 blog published

- **Ch · Status** — chapter number and status icons.
- **Field** — field-validation state (Yes / Partial / No). Nothing can be Yes before the box lands.
- **Chapter** — title; the chapter file is `chNN-…` under `files/nvidia-spark-guide/` (later the guide repo).
- **Source doc · Issue** — the DesktopShare doc that holds the runbook the chapter is extracted from, and the driving issue.
- **Status / open items** — current state and what is genuinely still open.

## Status tracker

| Ch · Status | Field | Chapter | Source doc · Issue | Status / open items |
|---|---|---|---|---|
| **1** 🔲 | No | DGX Spark hardware and the 273 GB/s reality | `nvidia-dgx-spark-landscape.md` · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **2** 🔲 | No | DGX OS day one: first boot, NVIDIA Sync, Dashboard, updates, recovery | `nvidia-dgx-spark-runbook.md` · [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **3** 🔲 | No | Joining the array: LAN, Tailscale, firewall, roster, EFM reachability | `nvidia-dgx-spark-runbook.md` · [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **4** 🔲 | No | Inference stacks on GB10 and the model lock | `nvidia-dgx-spark-landscape.md` · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **5** 🔲 | No | NIM on the DGX Spark — Cloudera AI Inference parity | `nvidia-dgx-spark-cloudera-aws.md` · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **6** 🔲 | No | NVFP4, speculative decoding, MoE vs dense, concurrency | `nvidia-dgx-spark-landscape.md` · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **7** 🔲 | No | Embeddings, reranking, Whisper — migrating the RAG service tier | `nvidia-dgx-spark-k3d-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **8** 🔲 | No | k3d with GPU on GB10 | `nvidia-dgx-spark-k3d-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **9** 🔲 | No | Cloudera Streaming Operators on aarch64 — feasibility and install | `nvidia-dgx-spark-k3d-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **10** 🔲 | No | NiFi → local LLM: custom Python processors and InvokeHTTP shapes | `nvidia-dgx-spark-k3d-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **11** 🔲 | No | Flink on GPU + Flink Agents | `nvidia-dgx-spark-k3d-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **12** 🔲 | No | EFM agent class NvidiaSpark-1 | `nvidia-dgx-spark-efm-agent.md` · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **13** 🔲 | No | Out-of-box edge-AI use cases — the Jetson → Spark ladder | `nvidia-dgx-spark-efm-agent.md` · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **14** 🔲 | No | Observability: Prometheus exporters, the EFM fleet board, DGX Dashboard | `nvidia-dgx-spark-efm-agent.md` · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **15** 🔲 | No | Local knowledge base for Claude Code (MCP + Qdrant) | `nvidia-dgx-spark-local-kb.md` · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **16** 🔲 | No | Local agentic validation loops | `nvidia-dgx-spark-local-kb.md` · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **17** 🔲 | No | What moves off cloud tokens — cost control, measured | `nvidia-dgx-spark-local-kb.md` · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **18** 🔲 | No | CDP Base on AWS + the DGX Spark | `nvidia-dgx-spark-cloudera-aws.md` · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **19** 🔲 | No | CDP Public Cloud on AWS: Cloudera AI Inference, NIM, AI Registry, Agent Studio, DataFlow | `nvidia-dgx-spark-cloudera-aws.md` · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **20** 🔲 | No | Same code, two backends — the arc | `nvidia-dgx-spark-cloudera-aws.md` · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **21** 🔲 | No | Demo catalogue | `nvidia-dgx-spark-cloudera-demos.md` · [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **22** 🔲 | No | Two, three, four Sparks: ConnectX-7, NCCL, 1M context | `nvidia-dgx-spark-landscape.md` · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |

## Parts

| Part | Chapters | What it covers |
|---|---|---|
| I — The box | 1, 2, 3 | What a DGX Spark actually is, how it boots, and how it joins a working fleet — the part every later chapter assumes. |
| II — Serving on GB10 | 4, 5, 6, 7 | Turning 128 GB of unified memory at 273 GB/s into endpoints the rest of the stack can hit: which engine, which model, which quantization, and the API contract that makes Cloudera AI a base-URL swap. |
| III — Kubernetes on the DGX Spark | 8, 9, 10, 11 | k3d with a real GPU, then Cloudera Streaming Operators — NiFi, Kafka, Flink — running on Arm, with the box's own models as an inference target. |
| IV — EFM at the desk | 12, 13, 14 | The Spark as an EFM-managed MiNiFi agent: the same class/flow/enrollment model the Jetson and the ESP32s use, one tier up in capability. |
| V — Local AI for development | 15, 16, 17 | Keeping Claude Code's execution, retrieval, and validation on the desk: a local knowledge base over our own docs, a local reviewer loop, and the measured cost that moves off cloud tokens. |
| VI — Cloudera on AWS | 18, 19, 20 | The two Cloudera-on-AWS shapes — CDP Base / Community Edition on EC2 and CDP Public Cloud — as integration targets for a local DGX Spark, ending in the same-code-two-backends arc. |
| VII — Demos | 21 | The field-validated demo catalogue: each demo names the chapter it exercises and the exact artifact it reuses. |
| VIII — Scale-out | 22 | When one box isn't enough: two, three, and four Sparks over ConnectX-7. |

## Phase gates before any chapter can validate

| Gate | Decided by | State |
|---|---|---|
| Model lock — lead (~27 B NVFP4) and stretch (~100 B) demo drivers | `nvidia-dgx-spark-landscape.md` §6 → Steven | open |
| CSO image architecture on aarch64 | Answered 2026-08-24 from WindowsDesktop — all 16 Cloudera images are `linux/arm64` multi-arch on the registry; [#243](https://github.com/cldr-steven-matison/DesktopShare/issues/243) on the Mac is optional confirmation | **closed — arm64 native** |
| k3d with GPU vs k3s bare | `nvidia-dgx-spark-k3d-cso.md` — k3d primary as asked, k3s documented fallback | recorded |
| Guide repo | staged in `files/nvidia-spark-guide/` now; public repo at first validated chapter | decided 2026-08-24 |
| Hardware on the LAN | [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235) `device:NvidiaSpark-1` | blocked — awaiting delivery |

## Subplans (source docs → chapters)

- `nvidia-dgx-spark-plan.md` — EPIC spine; phases, work-streams, decision log, risk register
- `nvidia-dgx-spark-research.md` — the sourced corpus every chapter cites (E, [#237](https://github.com/cldr-steven-matison/DesktopShare/issues/237))
- `nvidia-dgx-spark-landscape.md` — Ch1, Ch4, Ch6, Ch22 (A, [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232))
- `nvidia-dgx-spark-runbook.md` — Ch2, Ch3 (B, [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233))
- `nvidia-dgx-spark-k3d-cso.md` — Ch7, Ch8, Ch9, Ch10, Ch11 (F, [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238))
- `nvidia-dgx-spark-efm-agent.md` — Ch12, Ch13, Ch14 (G, [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239))
- `nvidia-dgx-spark-local-kb.md` — Ch15, Ch16, Ch17 (H, [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240))
- `nvidia-dgx-spark-cloudera-aws.md` — Ch5, Ch18, Ch19, Ch20 (I, [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241))
- `nvidia-dgx-spark-cloudera-demos.md` — Ch21 (C, [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234))
- EFM guide chapters this one leans on: `EdgeFlowManager/ch19-efm-and-nvidia-jetson.md` (the ladder's lower rung), `ch21-metrics-and-observability.md` (fleet board), `ch14`/`ch16` (the `nifi-and-ai` skill).

## Repos, paths, promotion flow

| Repo | Path (WindowsDesktop / WSL2) | Role |
|---|---|---|
| DesktopShare | `~/DesktopShare` | This tracker, source docs, subplans, the staged skeleton `files/nvidia-spark-guide/` |
| *(guide repo — not yet created)* | — | Cut from the skeleton at first validated chapter; same layout as EdgeFlowManager (chapters flat at root, `files/`, `images/`) |
| EdgeFlowManager | `~/EdgeFlowManager` | The published EFM guide — depth bar (chapters run 400–620 lines) and cross-link target |
| ClouderaStreamingOperators | `~/ClouderaStreamingOperators` | Operator install manifests the k3d port starts from |
| cso-operator-app | `~/cso-operator-app` | The RAG stack (Qdrant/TEI/Whisper/vLLM) the local knowledge base and Demo 1 reuse |
| NiFi2-Processor-Playground | `~/NiFi2-Processor-Playground` | Custom processors for Ch10 |
| Blog | Mac: `~/Documents/GitHub/cldr-steven-matison.github.io` | Jekyll `_posts/`, per `agent/writing-style.md` |

Promotion flow is the EFM guide's: source doc at the DesktopShare root (in progress) → chapter extracted into the guide → `completed/` for the source doc → optional `blog/` draft → `_posts/`.

# Completion summary

## Overall: 0 % field-validated · skeleton 100 %

| Axis | State | % |
|---|---|---|
| Field/build validation | 0 of 22 (hardware not delivered) | 0 % |
| Chapter stubs staged | 22 of 22 | 100 % |
| Source docs authored | 9 of 9 planned (see Subplans) | see `nvidia-dgx-spark-plan.md` §4 for per-doc state |
| Issue mailbox | EPIC #226 + children A–K: A/B/C/E–J in review, D/K open, none closed | — |
