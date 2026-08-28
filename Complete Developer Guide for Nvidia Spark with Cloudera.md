# The Complete Developer Guide for NVIDIA DGX Spark with Cloudera

*by Steven Matison*

> **Status (2026-08-28):** the full serving tier is **built and benchmarked on `spark-dd06`** ([#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232)) — lead Qwen3.6-35B-A3B-NVFP4 (`:8000`, 80–87 tok/s), embed bge-m3 (TEI `:8001`, 1024-d), rerank bge-reranker-v2-m3 (TEI `:8002`), STT whisper.cpp large-v3 CUDA (`:8003`, RTF ~0.04), and stretch Nemotron-3-Super-120B-A12B-NVFP4 (`:8000` swap-in, 15.5 tok/s single / 41.5 @4-way; thermal soak peak 69 °C GPU / ~114–115 °F case, no throttling). The model lock (Phase-gate) is **closed**, and the A source doc `nvidia-dgx-spark-landscape.md` is now expanded (MoE-vs-dense, engine table, co-host budget, 3 candidates per slot). This gives **Ch1/4/6/7 field-validated serving substance** — chapter prose extraction still pending. Serve scripts: `files/issue-226/{vllm-serve,tei-embed-serve,tei-rerank-serve,whisper-serve,vllm-stretch-serve}.sh`.
>
> **Status (2026-08-26):** the box landed as `spark-dd06` and the five source docs E–I (`nvidia-dgx-spark-research.md`, `-k3s-cso.md`, `-efm-agent.md`, `-local-kb.md`, `-cloudera-aws.md`) were written on it the same day — rows below say so per chapter. Every chapter is still a stub: field validation starts with on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). A/B/C source docs are still the first-package drafts.
>
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
| **1** 🟡 | Partial | DGX Spark hardware and the 273 GB/s reality | `nvidia-dgx-spark-landscape.md` · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | Source doc expanded + field-validated on `spark-dd06` 2026-08-28 (#232): 273 GB/s bandwidth-wall sizing now backed by measured decode across the model set; thermal envelope measured (peak 69 °C GPU / ~46 °C case at full saturation). Chapter prose still a stub. |
| **2** 🔲 | No | DGX OS day one: first boot, NVIDIA Sync, Dashboard, updates, recovery | `nvidia-dgx-spark-runbook.md` · [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **3** 🔲 | No | Joining the array: LAN, Tailscale, firewall, roster, EFM reachability | `nvidia-dgx-spark-runbook.md` · [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) | Stub filed 2026-08-24. Box landed 2026-08-26; the roster part is done (`CLAUDE-CHECKIN.md`). Blocked on B's expansion — the runbook draft does not yet cover Tailscale, firewall or EFM reachability; the as-built network facts are in the roster block. |
| **4** 🟡 | Partial | Inference stacks on GB10 and the model lock | `nvidia-dgx-spark-landscape.md` · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | **Model lock CLOSED 2026-08-28 (#232)** — full set locked + measured on `spark-dd06`: lead Qwen3.6-35B (vLLM :8000), stretch Nemotron-120B (:8000 swap-in), embed bge-m3 (:8001), rerank bge-reranker-v2-m3 (:8002), STT whisper.cpp (:8003). Serving-engine table (vLLM/TEI/whisper.cpp/SGLang/llama.cpp/NIM) in landscape §3.5. Chapter prose still a stub. |
| **5** 🔲 | No | NIM on the DGX Spark — Cloudera AI Inference parity | `nvidia-dgx-spark-cloudera-aws.md` · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Source doc `nvidia-dgx-spark-cloudera-aws.md` written 2026-08-26 on NvidiaSpark-1 (#241, `b348aca`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **6** 🟡 | Partial | NVFP4, speculative decoding, MoE vs dense, concurrency | `nvidia-dgx-spark-landscape.md` · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | MoE-vs-dense argument written (landscape §2.5 — active-param shape on the 273 GB/s wall); concurrency measured on `spark-dd06` 2026-08-28 (#232): lead 80–87 tok/s single, Nemotron-120B 15.5 single → 41.5 @4-way (server max_num_seqs=4). Spec-decode gap (vLLM 0.28 vs cu130-nightly+MTP) noted. Chapter prose still a stub. |
| **7** 🟡 | Partial | Embeddings, reranking, Whisper — migrating the RAG service tier | `nvidia-dgx-spark-k3s-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | **RAG service tier built + measured on `spark-dd06` 2026-08-28 (#232):** bge-m3 embeddings (TEI :8001, 1024-d, ~7 GB), bge-reranker-v2-m3 (TEI /rerank :8002, ~5 GB), whisper.cpp large-v3 CUDA (:8003, RTF ~0.04) — the TEI sm_121 image and the `120;121` whisper build both proven native on GB10. k3s-cso §5 budget updated with measured footprints. Sources also in `nvidia-dgx-spark-landscape.md` §3.5/§6. Chapter prose still a stub. |
| **8** 🔲 | No | k3s with GPU on GB10 | `nvidia-dgx-spark-k3s-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Source doc `nvidia-dgx-spark-k3s-cso.md` written 2026-08-26 on NvidiaSpark-1 (#238, `f67cfeb`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **9** 🔲 | No | Cloudera Streaming Operators on aarch64 — feasibility and install | `nvidia-dgx-spark-k3s-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Source doc `nvidia-dgx-spark-k3s-cso.md` written 2026-08-26 on NvidiaSpark-1 (#238, `f67cfeb`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **10** 🔲 | No | NiFi → local LLM: custom Python processors and InvokeHTTP shapes | `nvidia-dgx-spark-k3s-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Source doc `nvidia-dgx-spark-k3s-cso.md` written 2026-08-26 on NvidiaSpark-1 (#238, `f67cfeb`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **11** 🔲 | No | Flink on GPU + Flink Agents | `nvidia-dgx-spark-k3s-cso.md` · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Source doc `nvidia-dgx-spark-k3s-cso.md` written 2026-08-26 on NvidiaSpark-1 (#238, `f67cfeb`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **12** 🔲 | No | EFM agent class NvidiaSpark-1 | `nvidia-dgx-spark-efm-agent.md` · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | Source doc `nvidia-dgx-spark-efm-agent.md`; **§1–§2 fully field-validated on-box 2026-08-28** — class flow v1 published (flowVersion 4), **all four inference doors + `:9936` meter return 200** over the LAN (`/transcribe` via multipart-reconstruction leg), export `files/issue-226/flows/NvidiaSpark-1.designer-flow.json`. Chapter still a stub. |
| **13** 🔲 | No | Out-of-box edge-AI use cases — the Jetson → Spark ladder | `nvidia-dgx-spark-efm-agent.md` · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | Source doc `nvidia-dgx-spark-efm-agent.md` written 2026-08-26 on NvidiaSpark-1 (#239, `2d59285`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **14** 🔲 | No | Observability: Prometheus exporters, the EFM fleet board, DGX Dashboard | `nvidia-dgx-spark-efm-agent.md` · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | Source doc `nvidia-dgx-spark-efm-agent.md`; **`:9936 /metrics` leg live on-box 2026-08-28** (`GET :9936/metrics` → 200, real `/proc` GB10 values). Cluster-side scrape (ServiceMonitor + fleet-board row) and `:9835` host exporter still to wire. Chapter still a stub. |
| **15** 🔲 | No | Local knowledge base for Claude Code (MCP + Qdrant) | `nvidia-dgx-spark-local-kb.md` · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) | Source doc `nvidia-dgx-spark-local-kb.md` written 2026-08-26 on NvidiaSpark-1 (#240, `59801a6`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **16** 🔲 | No | Local agentic validation loops | `nvidia-dgx-spark-local-kb.md` · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) | Source doc `nvidia-dgx-spark-local-kb.md` written 2026-08-26 on NvidiaSpark-1 (#240, `59801a6`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **17** 🔲 | No | What moves off cloud tokens — cost control, measured | `nvidia-dgx-spark-local-kb.md` · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) | Source doc `nvidia-dgx-spark-local-kb.md` written 2026-08-26 on NvidiaSpark-1 (#240, `59801a6`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **18** 🔲 | No | CDP Base on AWS + the DGX Spark | `nvidia-dgx-spark-cloudera-aws.md` · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Source doc `nvidia-dgx-spark-cloudera-aws.md` written 2026-08-26 on NvidiaSpark-1 (#241, `b348aca`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **19** 🔲 | No | CDP Public Cloud on AWS: Cloudera AI Inference, NIM, AI Registry, Agent Studio, DataFlow | `nvidia-dgx-spark-cloudera-aws.md` · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Source doc `nvidia-dgx-spark-cloudera-aws.md` written 2026-08-26 on NvidiaSpark-1 (#241, `b348aca`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **20** 🔲 | No | Same code, two backends — the arc | `nvidia-dgx-spark-cloudera-aws.md` · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Source doc `nvidia-dgx-spark-cloudera-aws.md` written 2026-08-26 on NvidiaSpark-1 (#241, `b348aca`), in review. Chapter still a stub; field validation waits on on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **21** 🔲 | No | Demo catalogue | `nvidia-dgx-spark-cloudera-demos.md` · [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |
| **22** 🔲 | No | Two, three, four Sparks: ConnectX-7, NCCL, 1M context | `nvidia-dgx-spark-landscape.md` · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | Stub filed 2026-08-24. Gated on hardware ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)). |

## Parts

| Part | Chapters | What it covers |
|---|---|---|
| I — The box | 1, 2, 3 | What a DGX Spark actually is, how it boots, and how it joins a working fleet — the part every later chapter assumes. |
| II — Serving on GB10 | 4, 5, 6, 7 | Turning 128 GB of unified memory at 273 GB/s into endpoints the rest of the stack can hit: which engine, which model, which quantization, and the API contract that makes Cloudera AI a base-URL swap. |
| III — Kubernetes on the DGX Spark | 8, 9, 10, 11 | k3s with a real GPU, then Cloudera Streaming Operators — NiFi, Kafka, Flink — running on Arm, with the box's own models as an inference target. |
| IV — EFM at the desk | 12, 13, 14 | The Spark as an EFM-managed MiNiFi agent: the same class/flow/enrollment model the Jetson and the ESP32s use, one tier up in capability. |
| V — Local AI for development | 15, 16, 17 | Keeping Claude Code's execution, retrieval, and validation on the desk: a local knowledge base over our own docs, a local reviewer loop, and the measured cost that moves off cloud tokens. |
| VI — Cloudera on AWS | 18, 19, 20 | The two Cloudera-on-AWS shapes — CDP Base / Community Edition on EC2 and CDP Public Cloud — as integration targets for a local DGX Spark, ending in the same-code-two-backends arc. |
| VII — Demos | 21 | The field-validated demo catalogue: each demo names the chapter it exercises and the exact artifact it reuses. |
| VIII — Scale-out | 22 | When one box isn't enough: two, three, and four Sparks over ConnectX-7. |

## Phase gates before any chapter can validate

| Gate | Decided by | State |
|---|---|---|
| Model lock — lead (~27–35 B NVFP4) and stretch (~100–120 B) demo drivers, plus embed/rerank/STT | `nvidia-dgx-spark-landscape.md` §6 → Steven | **closed 2026-08-28** — full set locked + measured on `spark-dd06` (#232); three sourced candidates per slot in landscape §6 |
| CSO image architecture on aarch64 | Answered 2026-08-24 from WindowsDesktop — all 16 Cloudera images are `linux/arm64` multi-arch on the registry; [#243](https://github.com/cldr-steven-matison/DesktopShare/issues/243) re-scoped 2026-08-26 to an on-box pull check, optional | **closed — arm64 native** |
| Kubernetes substrate | `nvidia-dgx-spark-k3s-cso.md` — k3s on the host, pinned v1.32.13+k3s1 | closed 2026-08-27 |
| Guide repo | staged in `files/nvidia-spark-guide/` now; public repo at first validated chapter | decided 2026-08-24 |
| Hardware on the LAN | [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235) `device:NvidiaSpark-1` | **closed — landed 2026-08-26 (`spark-dd06`)**; D unblocked, Phase 3 next |

## Subplans (source docs → chapters)

- `nvidia-dgx-spark-plan.md` — EPIC spine; phases, work-streams, decision log, risk register
- `nvidia-dgx-spark-research.md` — the sourced corpus every chapter cites (E, [#237](https://github.com/cldr-steven-matison/DesktopShare/issues/237))
- `nvidia-dgx-spark-landscape.md` — Ch1, Ch4, Ch6, Ch22 (A, [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232))
- `nvidia-dgx-spark-runbook.md` — Ch2, Ch3 (B, [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233))
- `nvidia-dgx-spark-k3s-cso.md` — Ch7, Ch8, Ch9, Ch10, Ch11 (F, [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238))
- `nvidia-dgx-spark-efm-agent.md` — Ch12, Ch13, Ch14 (G, [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239))
- `nvidia-dgx-spark-local-kb.md` — Ch15, Ch16, Ch17 (H, [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240))
- `nvidia-dgx-spark-cloudera-aws.md` — Ch5, Ch18, Ch19, Ch20 (I, [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241))
- `nvidia-dgx-spark-cloudera-demos.md` — Ch21 (C, [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234))
- EFM guide chapters this one leans on (numbered in the EdgeFlowManager repo, not this guide): EFM guide Ch19 (`ch19-efm-and-nvidia-jetson.md`, the ladder's lower rung), EFM guide Ch21 (`ch21-metrics-and-observability.md`, fleet board), EFM guide Ch14 (`ch14-nifi-and-ai-skill-efm-portion.md`) and Ch16 (`ch16-how-to-ai-with-minifi.md`) for the `nifi-and-ai` skill.

## Repos, paths, promotion flow

| Repo | Path (WindowsDesktop / WSL2 and NvidiaSpark-1 — both `/home/tunas/<repo>`) | Role |
|---|---|---|
| DesktopShare | `~/DesktopShare` | This tracker, source docs, subplans, the staged skeleton `files/nvidia-spark-guide/` |
| *(guide repo — not yet created)* | — | Cut from the skeleton at first validated chapter; same layout as EdgeFlowManager (chapters flat at root, `files/`, `images/`) |
| EdgeFlowManager | `~/EdgeFlowManager` | The published EFM guide — depth bar (chapters run 400–620 lines) and cross-link target |
| ClouderaStreamingOperators | `~/ClouderaStreamingOperators` | Operator install manifests the k3s port starts from |
| cso-operator-app | `~/cso-operator-app` | The RAG stack (Qdrant/TEI/Whisper/vLLM) the local knowledge base and Demo 1 reuse |
| NiFi2-Processor-Playground | `~/NiFi2-Processor-Playground` | Custom processors for Ch10 |
| MiNiFi-Kubernetes-Playground | `~/MiNiFi-Kubernetes-Playground` | MiNiFi-on-k8s precedent for Ch12 |
| cloudera-ce-aws | `~/cloudera-ce-aws` | CE-on-AWS deploy path for Ch18 |
| iceberg-mcp-server, CAI_Workbench_MCP_Server | `~/iceberg-mcp-server`, `~/CAI_Workbench_MCP_Server` | The MCP-into-Claude precedents Ch15 reuses; Ch19 Workbench |
| NiFiandAi | `~/NiFiandAi` | NiFi + AI examples Ch10 draws on |
| Blog | Mac: `~/Documents/GitHub/cldr-steven-matison.github.io` | Jekyll `_posts/`, per `agent/writing-style.md` |

Promotion flow is the EFM guide's: source doc at the DesktopShare root (in progress) → chapter extracted into the guide → `completed/` for the source doc → optional `blog/` draft → `_posts/`.

# Completion summary

## Overall: serving tier field-validated (Ch1/4/6/7 partial) · skeleton 100 %

| Axis | State | % |
|---|---|---|
| Field/build validation | 4 of 22 partial (Ch1/4/6/7 — serving tier built + benchmarked on `spark-dd06` 2026-08-28, #232); other chapters await further Phase-3/4/5 bring-up | ~18 % partial |
| Chapter stubs staged | 22 of 22 | 100 % |
| Source docs authored | 5 of 9 at full depth (E–I, 2026-08-26); A (`-landscape.md`) expanded 2026-08-28 (#232); B/C are first-package drafts | see `nvidia-dgx-spark-plan.md` §4 for per-doc state |
| Issue mailbox | EPIC #226 + children A–K: A **done + closed** (#232, `67cb1da`/`e50e471`); B/C/E–J in review, D/K open | — |
