# The Complete Developer Guide for NVIDIA DGX Spark with Cloudera

*by Steven Matison*

> **Skeleton (2026-09-09).** Staged table of contents for the guide, work-stream J of [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226) — **26 chapters in 9 parts**. Chapters are stubs; each field-validates before its prose is authored, and the public repo is cut when the first validated chapter exists. Internal tracker of record: `Complete Developer Guide for Nvidia Spark with Cloudera.md` at the DesktopShare root. Naming rule throughout: **DGX Spark** is the box, **Apache Spark** is the engine.

NVIDIA's DGX Spark is documented as a personal AI supercomputer; what it is *not* documented as is a node in a working data platform. This guide is the missing half: the box as an inference endpoint for NiFi and Flink, as a Kubernetes host for Cloudera Streaming Operators on Arm, as an EFM-managed edge agent, as the home of a local knowledge base for a coding agent, and as the desk-side prototype that promotes unchanged into Cloudera AI on AWS. Every chapter marked done in the tracker points at a runbook that ran on the real hardware.

## Table of Contents

### Part I — The box

What a DGX Spark actually is, how it boots, and how it joins a working fleet — the part every later chapter assumes.

- **Ch1** — [DGX Spark hardware and the 273 GB/s reality](ch01-dgx-spark-hardware-and-273-gbs.md)
- **Ch2** — [DGX OS day one: first boot, NVIDIA Sync, Dashboard, updates, recovery](ch02-dgx-os-day-one.md)
- **Ch3** — [Joining the array: LAN, Tailscale, firewall, roster, EFM reachability](ch03-joining-the-array.md)

### Part II — Serving on GB10

Turning 128 GB of unified memory at 273 GB/s into endpoints the rest of the stack can hit: which engine, which model, which quantization, and the API contract that makes Cloudera AI a base-URL swap.

- **Ch4** — [Inference stacks on GB10 and the model lock](ch04-inference-stacks-and-model-lock.md)
- **Ch5** — [NIM on the DGX Spark — Cloudera AI Inference parity](ch05-nim-on-spark-cloudera-ai-parity.md)
- **Ch6** — [NVFP4, speculative decoding, MoE vs dense, concurrency](ch06-nvfp4-spec-decode-moe-concurrency.md)
- **Ch7** — [Embeddings, reranking, Whisper — migrating the RAG service tier](ch07-embeddings-rerank-whisper-tier.md)

### Part III — Kubernetes on the DGX Spark

k3s with a real GPU, then Cloudera Streaming Operators — NiFi, Kafka, Flink — running on Arm, with the box's own models as an inference target.

- **Ch8** — [k3s with GPU on GB10](ch08-k3s-with-gpu.md)
- **Ch9** — [Cloudera Streaming Operators on aarch64 — install](ch09-cso-operators-on-aarch64.md)
- **Ch10** — [NiFi → local LLM: custom Python processors and InvokeHTTP shapes](ch10-nifi-to-local-llm.md)
- **Ch11** — [Flink on GPU + Flink Agents](ch11-flink-on-gpu-and-flink-agents.md)

### Part IV — EFM at the desk

The Spark as an EFM-managed MiNiFi agent: the same class/flow/enrollment model the Jetson and the ESP32s use, one tier up in capability.

- **Ch12** — [EFM agent class NvidiaSpark-1](ch12-efm-agent-class-nvidiaspark-1.md)
- **Ch13** — [Out-of-box edge-AI use cases — the Jetson → Spark ladder](ch13-edge-ai-use-cases-jetson-to-spark.md)
- **Ch14** — [Observability: Prometheus exporters, the EFM fleet board, DGX Dashboard](ch14-observability.md)

### Part V — Local AI for development

Keeping Claude Code's execution, retrieval, and validation on the desk: a local knowledge base over our own docs, a local reviewer loop, and the measured cost that moves off cloud tokens.

- **Ch15** — [Local knowledge base for Claude Code (MCP + Qdrant)](ch15-local-knowledge-base-for-claude-code.md)
- **Ch16** — [Local agentic validation loops](ch16-local-agentic-validation-loops.md)
- **Ch17** — [What moves off cloud tokens — cost control, measured](ch17-what-moves-off-cloud-tokens.md)

### Part VI — DGX Spark with the Cloudera platform

Using the box with each Cloudera platform form factor as an external client — never a cluster node.

- **Ch18** — [CDP Base CE on AWS + the DGX Spark](ch18-cdp-base-ce-on-aws.md)
- **Ch19** — [CDP Public Cloud on AWS + the DGX Spark](ch19-cdp-public-cloud-on-aws.md)
- **Ch20** — [Cloudera AWC on AWS + the DGX Spark](ch20-cloudera-awc-on-aws.md)

### Part VII — DGX Spark with Cloudera AI

Cloudera AI as a form factor in its own right, with the DGX Spark as the local half, ending in the same-code arc.

- **Ch21** — [Cloudera AI on AWS](ch21-cloudera-ai-on-aws.md)
- **Ch22** — [Cloudera AI on AWC](ch22-cloudera-ai-on-awc.md)
- **Ch23** — [Cloudera AI on Data Services](ch23-cloudera-ai-on-data-services.md)
- **Ch24** — [Same code, N backends — the arc](ch24-same-code-n-backends.md)

### Part VIII — Demos

The field-validated demo catalogue: each demo names the chapter it exercises and the exact artifact it reuses.

- **Ch25** — [Demo catalogue](ch25-demo-catalogue.md)

### Part IX — Scale-out

When one box isn't enough: two, three, and four Sparks over ConnectX-7.

- **Ch26** — [Two, three, four Sparks: ConnectX-7, NCCL, 1M context](ch26-multi-spark-scale-out.md)

## What you have here

Twenty-six chapters in nine parts. Parts I–II are the box on its own; III–IV put it inside the Cloudera edge and streaming stack; V is the developer-workflow payoff; VI takes the same artifacts to the three Cloudera platform form factors and VII to Cloudera AI (on AWS, AWC, and Data Services); VIII is the demo catalogue and IX is scale-out. `files/` holds flow exports, manifests and scripts; `images/` the figures — both at this directory's root, siblings of the chapters.
