# The Complete Developer Guide for NVIDIA DGX Spark with Cloudera

*by Steven Matison*

> **Skeleton (2026-09-10).** Staged table of contents for the guide, work-stream J of [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226), 26 chapters in 9 parts. Every chapter is a stub on the task-first template. Sixteen of the 26 have their substance validated on `spark-dd06` and none has prose yet. Each chapter field-validates before its prose is authored, and the public repo is cut when the first validated chapter exists. Internal tracker of record is `Complete Developer Guide for Nvidia Spark with Cloudera.md` at the DesktopShare root; the remaining per-chapter work is tracked in [#320](https://github.com/cldr-steven-matison/DesktopShare/issues/320). Naming rule throughout. **DGX Spark** is the box, **Apache Spark** is the engine.

NVIDIA's DGX Spark is documented as a personal AI supercomputer. What it is not documented as is a node in a working data platform, and this guide is that missing half. The box as an inference endpoint for NiFi and Flink, as a Kubernetes host for Cloudera Streaming Operators on Arm, as an EFM-managed edge agent, as the home of a local knowledge base for a coding agent, and as the desk-side prototype that promotes unchanged into Cloudera AI on AWS. Every chapter marked done in the tracker points at a runbook that ran on the hardware.

## Table of Contents

### Part I. The box

What a DGX Spark is, how it boots, and how it joins a working fleet. Every later chapter assumes this part.

| Ch | Chapter |
|---|---|
| 1 | [DGX Spark hardware and the 273 GB/s reality](ch01-dgx-spark-hardware-and-273-gbs.md) |
| 2 | [DGX OS day one: first boot, NVIDIA Sync, Dashboard, updates, recovery](ch02-dgx-os-day-one.md) |
| 3 | [Joining the array: LAN, Tailscale, firewall, roster, EFM reachability](ch03-joining-the-array.md) |

### Part II. Serving on GB10

Turning 128 GB of unified memory at 273 GB/s into endpoints the rest of the stack can hit. Which engine, which model, which quantization, and the API contract that makes Cloudera AI a base-URL swap.

| Ch | Chapter |
|---|---|
| 4 | [Inference stacks on GB10 and the model lock](ch04-inference-stacks-and-model-lock.md) |
| 5 | [NIM on the DGX Spark — Cloudera AI Inference parity](ch05-nim-on-spark-cloudera-ai-parity.md) |
| 6 | [NVFP4, speculative decoding, MoE vs dense, concurrency](ch06-nvfp4-spec-decode-moe-concurrency.md) |
| 7 | [Embeddings, reranking, Whisper — the RAG service tier](ch07-embeddings-rerank-whisper-tier.md) |

### Part III. Kubernetes on the DGX Spark

k3s with a real GPU, then Cloudera Streaming Operators (NiFi, Kafka, Flink) running on Arm, with the box's own models as an inference target.

| Ch | Chapter |
|---|---|
| 8 | [k3s with GPU on GB10](ch08-k3s-with-gpu.md) |
| 9 | [Cloudera Streaming Operators on aarch64 — install](ch09-cso-operators-on-aarch64.md) |
| 10 | [NiFi → local LLM: custom Python processors and InvokeHTTP shapes](ch10-nifi-to-local-llm.md) |
| 11 | [Flink on GPU + Flink Agents](ch11-flink-on-gpu-and-flink-agents.md) |

### Part IV. EFM at the desk

The Spark as an EFM-managed MiNiFi agent, the same class, flow and enrollment model the Jetson and the ESP32s use, one tier up in capability.

| Ch | Chapter |
|---|---|
| 12 | [EFM agent class NvidiaSpark-1](ch12-efm-agent-class-nvidiaspark-1.md) |
| 13 | [Out-of-box edge-AI use cases — the Jetson → Spark ladder](ch13-edge-ai-use-cases-jetson-to-spark.md) |
| 14 | [Observability: Prometheus exporters, the EFM fleet board, DGX Dashboard](ch14-observability.md) |

### Part V. Local AI for development

Keeping Claude Code's execution, retrieval and validation on the desk. A local knowledge base over our own docs, a local reviewer loop, and the measured cost that moves off cloud tokens.

| Ch | Chapter |
|---|---|
| 15 | [Local knowledge base for Claude Code (MCP + Qdrant)](ch15-local-knowledge-base-for-claude-code.md) |
| 16 | [Local agentic validation loops](ch16-local-agentic-validation-loops.md) |
| 17 | [What moves off cloud tokens — cost control, measured](ch17-what-moves-off-cloud-tokens.md) |

### Part VI. DGX Spark with the Cloudera platform

Using the box with each Cloudera platform form factor as an external client, never a cluster node.

| Ch | Chapter |
|---|---|
| 18 | [CDP Base CE on AWS + the DGX Spark](ch18-cdp-base-ce-on-aws.md) |
| 19 | [CDP Public Cloud on AWS + the DGX Spark](ch19-cdp-public-cloud-on-aws.md) |
| 20 | [Cloudera AWC on AWS + the DGX Spark](ch20-cloudera-awc-on-aws.md) |

### Part VII. DGX Spark with Cloudera AI

Cloudera AI as a form factor in its own right, with the DGX Spark as the local half, ending in the same-code arc.

| Ch | Chapter |
|---|---|
| 21 | [Cloudera AI on AWS](ch21-cloudera-ai-on-aws.md) |
| 22 | [Cloudera AI on AWC](ch22-cloudera-ai-on-awc.md) |
| 23 | [Cloudera AI on Data Services](ch23-cloudera-ai-on-data-services.md) |
| 24 | [Same code, N backends — the arc](ch24-same-code-n-backends.md) |

### Part VIII. Demos

The demo catalogue. Each demo names the chapter it exercises and the exact artifact it reuses.

| Ch | Chapter |
|---|---|
| 25 | [Demo catalogue](ch25-demo-catalogue.md) |

### Part IX. Scale-out

When one box isn't enough. Two, three, and four Sparks over ConnectX-7.

| Ch | Chapter |
|---|---|
| 26 | [Two, three, four Sparks: ConnectX-7, NCCL, 1M context](ch26-multi-spark-scale-out.md) |

## What you have here

Twenty-six chapters in nine parts. Parts I and II are the box on its own. III and IV put it inside the Cloudera edge and streaming stack. V is the developer-workflow payoff. VI takes the same artifacts to the three Cloudera platform form factors and VII to Cloudera AI (on AWS, AWC, and Data Services). VIII is the demo catalogue and IX is scale-out. `files/` holds flow exports, manifests and scripts and `images/` the figures, both at this directory's root, siblings of the chapters.
