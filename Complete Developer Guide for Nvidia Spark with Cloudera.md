# The Complete Developer Guide for NVIDIA DGX Spark with Cloudera

*by Steven Matison*

> **Status (2026-09-10).** Internal tracker of record for the guide — work-stream **J** of EPIC [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226) ([#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242)). It records per-chapter state, field-validation state, source doc, and driving issue. It is not the guide. The box runs as `spark-dd06`; the guide is **26 chapters in 9 parts**. The dangling per-chapter and source-doc work is tracked in one place, [#320](https://github.com/cldr-steven-matison/DesktopShare/issues/320).
>
> **What is field-validated on the box.** Serving tier — the model set is locked and benchmarked (#232, 2026-08-28): lead Qwen3.6-35B-A3B-NVFP4 (`:8000`), stretch Nemotron-3-Super-120B-A12B-NVFP4 (`:8000` swap-in), embed bge-m3 (TEI `:8001`), rerank bge-reranker-v2-m3 (`:8002`), STT whisper.cpp large-v3 CUDA (`:8003`). Platform — k3s + GPU, the Cloudera operators (all 16 images arm64-native), the box's own Kafka and `mynifi`, the `SparkLlmBridge` flow, and Flink on GPU with flink-agents 0.3.1 are all built on-box (#238, 2026-08-27). Day one — runbook B is the as-built narrative from unbox to the exposed port surface, including reboot survival (#233, #322, 2026-09-10). Edge — the EFM agent class `NvidiaSpark-1` with its single-handler router flow is validated over the LAN (#239, 2026-08-28), and both carried-forward items closed from WindowsDesktop on 2026-09-10 (#324) — the cluster-side scrape of `:9936` and `:9835` is green over the tailnet with a fleet-board row, and a §3 use case answered from a non-Spark shell. Local AI — the knowledge base is live and the offload scoreboard has twelve readings (#240 2026-08-27; #294 closed 2026-09-10 at 7.97 % generation share, the L2 soak gate accepted as not met). Demos — the four on-box EFM + NiFi flows are catalogued with committed exports (#234, 2026-09-08). Prose for every chapter is still to be authored.
>
> **What is still open.** The AWS and Cloudera AI integrations are documented and design-accepted but not field-run (I, #241 closed 2026-09-10; the field run stays in #320); AWC (`goes01`) claims are `[TO-VERIFY]` pending box→`goes01` reachability (#283); Cloudera AI on Data Services is **blocked — no test environment yet**; multi-Spark scale-out is gated on hardware. The H5 KB-validator soak has no verdict because no soak data was ever logged — the validator writes no ledger — so the call needs instrumentation first (#320 decision 1).
>
> **The Cloudera coverage is two scopes.** Part VI covers using the DGX Spark with the Cloudera **platform** form factors (CDP Base CE on AWS, CDP Public Cloud on AWS, Cloudera AWC on AWS). Part VII covers the DGX Spark with **Cloudera AI** as a form factor in its own right (Cloudera AI on AWS, on AWC, and on Data Services), ending in the same-code-N-backends arc.
>
> **Authoring rule for every chapter.** Write for a developer following the steps: plain facts, the shortest path to the goal. No war-story — the hurdles, dead ends, and decision history stay in the source docs and issues, not the guide. Do not mirror the EFM guide's phrasing or section structure; this guide's only likeness to that one is breadth and depth.

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
| **1** 🟡 | Partial | DGX Spark hardware and the 273 GB/s reality | [`nvidia-dgx-spark-landscape.md`](nvidia-dgx-spark-landscape.md) · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | Sizing field-validated on `spark-dd06` 2026-08-28 (#232): the 273 GB/s bandwidth wall is backed by measured decode across the model set; thermal envelope measured. Prose pending. |
| **2** 🟡 | Partial | DGX OS day one: first boot, NVIDIA Sync, Dashboard, updates, recovery | [`nvidia-dgx-spark-runbook.md`](nvidia-dgx-spark-runbook.md) · [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) | Runbook B expanded 2026-09-10 (#233): boot and baseline, the container runtime, the first endpoint and reboot survival (#322) as built on `spark-dd06`. NVIDIA Sync and the Dashboard are not covered by the runbook. Prose pending. |
| **3** 🟡 | Partial | Joining the array: LAN, Tailscale, firewall, roster, EFM reachability | [`nvidia-dgx-spark-runbook.md`](nvidia-dgx-spark-runbook.md) · [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233) | Runbook B §2 network, §5 roster, §6 exposed surface, §7 hardening as built 2026-09-10 (#233). Still owed on the box: the static IP reservation and the ufw NodePort re-run. Prose pending. |
| **4** 🟡 | Partial | Inference stacks on GB10 and the model lock | [`nvidia-dgx-spark-landscape.md`](nvidia-dgx-spark-landscape.md) · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | Model lock closed + measured 2026-08-28 (#232): lead Qwen3.6-35B (:8000), stretch Nemotron-120B (:8000 swap-in), embed bge-m3 (:8001), rerank bge-reranker-v2-m3 (:8002), STT whisper.cpp (:8003); serving-engine table in landscape §3.5. Prose pending. |
| **5** 🔲 | No | NIM on the DGX Spark — Cloudera AI Inference parity | [`nvidia-dgx-spark-cloudera-aws.md`](nvidia-dgx-spark-cloudera-aws.md) · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Source doc design-accepted, #241 closed 2026-09-10; not field-run, the run is tracked in [#320](https://github.com/cldr-steven-matison/DesktopShare/issues/320). Stub. |
| **6** 🟡 | Partial | NVFP4, speculative decoding, MoE vs dense, concurrency | [`nvidia-dgx-spark-landscape.md`](nvidia-dgx-spark-landscape.md) · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | MoE-vs-dense written (landscape §2.5); concurrency measured 2026-08-28 (#232) — lead 80–87 tok/s single, Nemotron-120B 15.5 single → 41.5 @4-way. Prose pending. |
| **7** 🟡 | Partial | Embeddings, reranking, Whisper — the RAG service tier | [`nvidia-dgx-spark-k3s-cso.md`](nvidia-dgx-spark-k3s-cso.md) · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | RAG tier built + measured 2026-08-28: bge-m3 (TEI :8001), bge-reranker-v2-m3 (:8002), whisper.cpp large-v3 CUDA (:8003); measured footprints in k3s-cso §5. Prose pending. |
| **8** 🟡 | Partial | k3s with GPU on GB10 | [`nvidia-dgx-spark-k3s-cso.md`](nvidia-dgx-spark-k3s-cso.md) · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | k3s v1.32.13+k3s1 with the GPU device plugin built on-box 2026-08-27 (#238). Prose pending. |
| **9** 🟡 | Partial | Cloudera Streaming Operators on aarch64 — install | [`nvidia-dgx-spark-k3s-cso.md`](nvidia-dgx-spark-k3s-cso.md) · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Operators installed on-box 2026-08-27 (#238): all 16 Cloudera images arm64-native; order cert-manager → Strimzi → CSA → CFM; ingress-nginx with ssl-passthrough; budget inside 128 GB. Prose pending. |
| **10** 🟡 | Partial | NiFi → local LLM: custom Python processors and InvokeHTTP shapes | [`nvidia-dgx-spark-k3s-cso.md`](nvidia-dgx-spark-k3s-cso.md) · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | `SparkLlmBridge` flow built on-box 2026-08-27 (#238): the box's `mynifi` calls its own `/v1/chat/completions` and publishes to Kafka (export `files/issue-226/flows/SparkLlmBridge.json`). Prose pending. |
| **11** 🟡 | Partial | Flink on GPU + Flink Agents | [`nvidia-dgx-spark-k3s-cso.md`](nvidia-dgx-spark-k3s-cso.md) · [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238) | Flink TaskManager claiming `nvidia.com/gpu`, flink-agents 0.3.1 `STABLE` against the box's own endpoint, built on-box 2026-08-27 (#238). Prose pending. |
| **12** 🟡 | Partial | EFM agent class NvidiaSpark-1 | [`nvidia-dgx-spark-efm-agent.md`](nvidia-dgx-spark-efm-agent.md) · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | Class flow consolidated to the single-handler router (flowVersion 5, 2026-08-28): one `HandleHttpRequest` on `:8190` fronts all four doors; all four + `:9936` return 200 over the LAN. Export `files/issue-226/flows/NvidiaSpark-1.designer-flow.json`. #239 reopened; source doc's editorial pass done 2026-09-10 (facts only, Jetson kept where it carries a difference). Prose pending. |
| **13** 🔲 | No | Out-of-box edge-AI use cases — the Jetson → Spark ladder | [`nvidia-dgx-spark-efm-agent.md`](nvidia-dgx-spark-efm-agent.md) · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) | Source doc done (#239): 10 use-case designs, Jetson → Spark ladder. The non-Spark run is a hand-off to WindowsDesktop with the `curl` recipes in `files/issue-239/validate-from-remote.md` (2026-09-10); the door responses are checked on the box. Prose pending. |
| **14** 🟡 | Partial | Observability: Prometheus exporters, the EFM fleet board, DGX Dashboard | [`nvidia-dgx-spark-efm-agent.md`](nvidia-dgx-spark-efm-agent.md) · [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239) · [#324](https://github.com/cldr-steven-matison/DesktopShare/issues/324) | `:9936/metrics` leg live on-box. Cluster-side scrape **done 2026-09-10 from WindowsDesktop (#324)**: both jobs `up=1` over the tailnet (the LAN path is blocked at `spark-dd06`'s `ufw`, which never allowed the exporter ports — [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233)), fleet board carries a seventh heartbeat tile and a NvidiaSpark-1 Layer-2/3 row. The fleet Prometheus stack is up and staying up (all seven targets `up=1`); manifests in `files/issue-239/`, live record in [`efm-observability.md`](efm-observability.md). Prose pending. |
| **15** 🟡 | Partial | Local knowledge base for Claude Code (MCP + Qdrant) | [`nvidia-dgx-spark-local-kb.md`](nvidia-dgx-spark-local-kb.md) · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) | KB live on `spark-dd06` since 2026-08-27 (#240): docs indexed, queryable via the `ds-kb` tool; a hook hands a session matching sections on repo search (#294). H5 validator soak: no verdict, because no firing was ever logged (the validator writes no ledger); instrumentation first, then the call (#320 decision 1). Prose pending. |
| **16** 🟡 | Partial | Local agentic validation loops | [`nvidia-dgx-spark-local-kb.md`](nvidia-dgx-spark-local-kb.md) + [`nvidia-dgx-spark-offload.md`](nvidia-dgx-spark-offload.md) · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) / [#294](https://github.com/cldr-steven-matison/DesktopShare/issues/294) | Measured on real docs 2026-09-03 (#294): the box flags, Claude adjudicates; useful first pass on a flawed doc, invents findings on a clean one, so Claude keeps the final say. #294 closed 2026-09-10 with the L2 soak gate accepted as not met (KB adoption 9.4 % of sessions against a 50 % gate). Prose pending. |
| **17** 🟡 | Partial | What moves off cloud tokens — cost control, measured | [`nvidia-dgx-spark-local-kb.md`](nvidia-dgx-spark-local-kb.md) §5 + [`nvidia-dgx-spark-offload.md`](nvidia-dgx-spark-offload.md) · [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240) / [#294](https://github.com/cldr-steven-matison/DesktopShare/issues/294) | Measured 2026-09-02 → 09-10 (#294, twelve ledger rows): generation-offload share 1.50 % → 7.97 % as log digestion and per-section fact extraction moved over. Moves: doc lookups, long-log summaries, fact extraction. Stays hosted: judgement, proofreading, writing. `offload.py snapshot` records the share; #294 closed 2026-09-10. Prose pending. |
| **18** 🔲 | No | CDP Base CE on AWS + the DGX Spark | [`nvidia-dgx-spark-cloudera-aws.md`](nvidia-dgx-spark-cloudera-aws.md) · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Platform form factor. Source doc design-accepted (#241 closed 2026-09-10); not field-run, tracked in #320. The box feeds Base, never runs it (amd64). Stub. |
| **19** 🔲 | No | CDP Public Cloud on AWS + the DGX Spark | [`nvidia-dgx-spark-cloudera-aws.md`](nvidia-dgx-spark-cloudera-aws.md) · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | Platform form factor: `srm-iceberg`, DataFlow Inbound, Iceberg REST Catalog from a Spark-hosted NiFi. Source doc design-accepted (#241 closed 2026-09-10); not field-run, tracked in #320. Stub. |
| **20** 🔲 | No | Cloudera AWC on AWS + the DGX Spark | [`nvidia-dgx-spark-cloudera-awc.md`](nvidia-dgx-spark-cloudera-awc.md) · [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) | Platform form factor: `goes01` AWC on EKS; DGX Spark as external client. Setup in `cloudera-anywhere-getting-started.md` (#284). All AWC-runtime claims `[TO-VERIFY]`; gating open item is box→`goes01` reachability. Stub. |
| **21** 🔲 | No | Cloudera AI on AWS | [`nvidia-dgx-spark-cloudera-aws.md`](nvidia-dgx-spark-cloudera-aws.md) · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) | AI form factor: Workbench → AI Registry → AI Inference, NIM microservices, OpenAI-compatible endpoint, the base-URL swap. Source doc design-accepted (#241 closed 2026-09-10); not field-run, tracked in #320. Stub. |
| **22** 🔲 | No | Cloudera AI on AWC | [`nvidia-dgx-spark-cloudera-awc.md`](nvidia-dgx-spark-cloudera-awc.md) · [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) | AI form factor: the Cloudera AI experience on AWC (`goes01`), DGX Spark as the local half. All AWC-runtime claims `[TO-VERIFY]` pending `goes01` reachability. Stub. |
| **23** 🔲 | No | Cloudera AI on Data Services | [#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242) | AI form factor: Cloudera AI on on-prem Cloudera Data Services (CDS 1.5.5+). **Blocked — no test environment yet.** No source doc; field-validation work-stream to be scoped when an environment exists. |
| **24** 🔲 | No | Same code, N backends — the arc | [`nvidia-dgx-spark-cloudera-aws.md`](nvidia-dgx-spark-cloudera-aws.md) + [`nvidia-dgx-spark-cloudera-awc.md`](nvidia-dgx-spark-cloudera-awc.md) · [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241) / [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283) | One Python client / one NiFi flow / one Flink Agents job — base-URL + auth + model-name delta across the desk endpoint, Cloudera AI on AWS, and Cloudera AI on AWC. Design-accepted (#241 closed 2026-09-10); the arc is not recorded end-to-end until the AWS side runs (#320). Stub. |
| **25** 🟡 | Partial | Demo catalogue | [`nvidia-dgx-spark-cso-demos.md`](nvidia-dgx-spark-cso-demos.md) · [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234) | Source doc rewritten 2026-09-08 as the four on-box EFM + NiFi flows, each with a committed export. Chapter prose pending. |
| **26** 🔲 | No | Two, three, four Sparks: ConnectX-7, NCCL, 1M context | [`nvidia-dgx-spark-landscape.md`](nvidia-dgx-spark-landscape.md) · [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232) | Gated on hardware (multiple Sparks over ConnectX-7). Stub. |

## Parts

| Part | Chapters | What it covers |
|---|---|---|
| I — The box | 1, 2, 3 | What a DGX Spark actually is, how it boots, and how it joins a working fleet — the part every later chapter assumes. |
| II — Serving on GB10 | 4, 5, 6, 7 | Turning 128 GB of unified memory at 273 GB/s into endpoints the rest of the stack can hit: which engine, which model, which quantization, and the API contract that makes Cloudera AI a base-URL swap. |
| III — Kubernetes on the DGX Spark | 8, 9, 10, 11 | k3s with a real GPU, then Cloudera Streaming Operators — NiFi, Kafka, Flink — running on Arm, with the box's own models as an inference target. |
| IV — EFM at the desk | 12, 13, 14 | The Spark as an EFM-managed MiNiFi agent: the same class/flow/enrollment model the Jetson and the ESP32s use, one tier up in capability. |
| V — Local AI for development | 15, 16, 17 | Keeping Claude Code's execution, retrieval, and validation on the desk: a local knowledge base over our own docs, a local reviewer loop, and the measured cost that moves off cloud tokens. |
| VI — DGX Spark with the Cloudera platform | 18, 19, 20 | Using the box with each Cloudera platform form factor as an external client: CDP Base CE on AWS, CDP Public Cloud on AWS, and Cloudera AWC on AWS. |
| VII — DGX Spark with Cloudera AI | 21, 22, 23, 24 | Cloudera AI as a form factor in its own right — on AWS, on AWC, and on Data Services (on-prem) — with the box as the local half, ending in the same-code-N-backends arc. |
| VIII — Demos | 25 | The field-validated demo catalogue: each demo names the chapter it exercises and the exact artifact it reuses. |
| IX — Scale-out | 26 | When one box isn't enough: two, three, and four Sparks over ConnectX-7. |

## Phase gates before any chapter can validate

| Gate | Decided by | State |
|---|---|---|
| Model lock — lead (~27–35 B NVFP4) and stretch (~100–120 B) demo drivers, plus embed/rerank/STT | `nvidia-dgx-spark-landscape.md` §6 → Steven | **closed 2026-08-28** — full set locked + measured on `spark-dd06` (#232); three sourced candidates per slot in landscape §6 |
| CSO image architecture on aarch64 | Answered 2026-08-24 from WindowsDesktop — all 16 Cloudera images are `linux/arm64` multi-arch on the registry; [#243](https://github.com/cldr-steven-matison/DesktopShare/issues/243) re-scoped 2026-08-26 to an on-box pull check, optional | **closed — arm64 native** |
| Kubernetes substrate | `nvidia-dgx-spark-k3s-cso.md` — k3s on the host, pinned v1.32.13+k3s1 | closed 2026-08-27 |
| Guide repo | staged in `files/nvidia-spark-guide/` now; public repo at first validated chapter | decided 2026-08-24 |
| Hardware on the LAN | [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235) `device:NvidiaSpark-1` | **closed — landed 2026-08-26 (`spark-dd06`)**; D unblocked, Phase 3 next |

## Subplans (source docs → chapters)

- [`nvidia-dgx-spark-plan.md`](nvidia-dgx-spark-plan.md) — EPIC spine; phases, work-streams, decision log, risk register
- [`nvidia-dgx-spark-research.md`](nvidia-dgx-spark-research.md) — the sourced corpus every chapter cites (E, [#237](https://github.com/cldr-steven-matison/DesktopShare/issues/237))
- [`nvidia-dgx-spark-landscape.md`](nvidia-dgx-spark-landscape.md) — Ch1, Ch4, Ch6, Ch26 (A, [#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232))
- [`nvidia-dgx-spark-runbook.md`](nvidia-dgx-spark-runbook.md) — Ch2, Ch3 (B, [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233))
- [`nvidia-dgx-spark-k3s-cso.md`](nvidia-dgx-spark-k3s-cso.md) — Ch7, Ch8, Ch9, Ch10, Ch11 (F, [#238](https://github.com/cldr-steven-matison/DesktopShare/issues/238))
- [`nvidia-dgx-spark-efm-agent.md`](nvidia-dgx-spark-efm-agent.md) — Ch12, Ch13, Ch14 (G, [#239](https://github.com/cldr-steven-matison/DesktopShare/issues/239))
- [`nvidia-dgx-spark-local-kb.md`](nvidia-dgx-spark-local-kb.md) — Ch15, Ch16, Ch17 (H, [#240](https://github.com/cldr-steven-matison/DesktopShare/issues/240))
- [`nvidia-dgx-spark-offload.md`](nvidia-dgx-spark-offload.md) — Ch16, Ch17 (L, [#294](https://github.com/cldr-steven-matison/DesktopShare/issues/294)): what the box takes over from Claude Code, measured
- [`nvidia-dgx-spark-cloudera-aws.md`](nvidia-dgx-spark-cloudera-aws.md) — Ch5, Ch18, Ch19, Ch21, Ch24 (I, [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241)); the three platform-and-AI-on-AWS paths and the same-code arc
- [`nvidia-dgx-spark-cloudera-awc.md`](nvidia-dgx-spark-cloudera-awc.md) — Ch20, Ch22 (I-AWC, [#283](https://github.com/cldr-steven-matison/DesktopShare/issues/283)); AWC setup ref is [`cloudera-anywhere-getting-started.md`](cloudera-anywhere-getting-started.md) ([#284](https://github.com/cldr-steven-matison/DesktopShare/issues/284))
- Ch23 (Cloudera AI on Data Services) has **no source doc yet** — blocked on a test environment ([#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242))
- [`nvidia-dgx-spark-cso-demos.md`](nvidia-dgx-spark-cso-demos.md) — Ch25 (C, [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234)); the four on-box EFM + NiFi flows, nothing from other devices
- EFM guide chapters this one cross-references (in the [EdgeFlowManager](https://github.com/cldr-steven-matison/EdgeFlowManager) repo, not this guide): EFM Ch19 (Jetson, the ladder's lower rung), EFM Ch21 (metrics/fleet board), EFM Ch14 and Ch16 (the `nifi-and-ai` skill).

## Repos, paths, promotion flow

| Repo | Path (WindowsDesktop / WSL2 and NvidiaSpark-1 — both `/home/tunas/<repo>`) | Role |
|---|---|---|
| DesktopShare | `~/DesktopShare` | This tracker, source docs, subplans, the staged skeleton `files/nvidia-spark-guide/` |
| *(guide repo — not yet created)* | — | Cut from the skeleton at first validated chapter; chapters flat at the root with `files/` and `images/` siblings |
| EdgeFlowManager | `~/EdgeFlowManager` | The published EFM guide — cross-link target for the Jetson/EFM chapters |
| ClouderaStreamingOperators | `~/ClouderaStreamingOperators` | Operator install manifests the k3s port starts from |
| cso-operator-app | `~/cso-operator-app` | The RAG stack (Qdrant/TEI/Whisper/vLLM) the local knowledge base and Demo 1 reuse |
| NiFi2-Processor-Playground | `~/NiFi2-Processor-Playground` | Custom processors for Ch10 |
| MiNiFi-Kubernetes-Playground | `~/MiNiFi-Kubernetes-Playground` | MiNiFi-on-k8s precedent for Ch12 |
| cloudera-ce-aws | `~/cloudera-ce-aws` | CE-on-AWS deploy path for Ch18 |
| iceberg-mcp-server, CAI_Workbench_MCP_Server | `~/iceberg-mcp-server`, `~/CAI_Workbench_MCP_Server` | The MCP-into-Claude precedents Ch15 reuses; Ch21 Workbench |
| NiFiandAi | `~/NiFiandAi` | NiFi + AI examples Ch10 draws on |
| Blog | Mac: `~/Documents/GitHub/cldr-steven-matison.github.io` | Jekyll `_posts/`, per `agent/writing-style.md` |

Promotion flow: source doc at the DesktopShare root (in progress) → chapter extracted into the guide → `completed/` for the source doc → optional `blog/` draft → `_posts/`.

# Completion summary

## Overall: serving + platform + edge + local-AI field-validated on the box · skeleton 100 %

| Axis | State | % |
|---|---|---|
| Field/build validation | 16 of 26 have validated on-box substance (Ch1/4/6/7 serving 2026-08-28; Ch2/3 day one + reboot survival 2026-09-10; Ch8/9/10/11 k3s + operators + flows 2026-08-27; Ch12/14 EFM agent 2026-08-28; Ch15/16/17 local AI 2026-08-27→09-10; Ch25 demos 2026-09-08) — prose pending. Ch13's remote run is a WindowsDesktop hand-off. The AWS/Cloudera-AI/AWC/Data-Services and scale-out chapters (5, 18–24, 26) are not field-run. | ~62 % partial, 0 % prose |
| Chapter stubs staged | 26 of 26 on the task-first template; restructured into 9 parts (VI platform / VII Cloudera AI incl. Data Services / VIII demos / IX scale-out) 2026-09-09 | 100 % |
| Source docs authored | E–I at full depth (2026-08-26); AWC peer doc 2026-08-31 (`[TO-VERIFY]` pending live `goes01`); A expanded 2026-08-28; C rewritten 2026-09-08; L written 2026-09-03 and closed 09-10; **B expanded to the as-built day-one narrative 2026-09-10**; G's editorial pass 2026-09-10; Data Services (Ch23) has no source doc | see [`nvidia-dgx-spark-plan.md`](nvidia-dgx-spark-plan.md) §4 for per-doc state |
| Issue mailbox | EPIC #226 **closed** with A/C/D/E/F/H/K/AWC (#232, #234, #235, #237, #238, #240, #243, #283) and, 2026-09-10, I and L (#241, #294). Open on `NvidiaSpark-1`: B (#233), G (#239), J (#242), the dangling-work tracker [#320](https://github.com/cldr-steven-matison/DesktopShare/issues/320), reboot survival [#322](https://github.com/cldr-steven-matison/DesktopShare/issues/322). AWC setup ref #284 is open on the Mac, blocked. | — |
