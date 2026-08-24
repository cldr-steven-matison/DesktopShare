# NVIDIA DGX Spark — Capability Landscape

> **Status (2026-08-24):** Work-stream **A** of the DGX Spark readiness EPIC ([#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226)). Outward research, box not yet in hand. Purpose: establish what one Grace Blackwell / 128 GB box can actually serve in mid-2026 — and at what usable speed — so the runbook (B) and Cloudera demos (C) target the right models. Every throughput/footprint number below is sourced. Scope: single-box first, dual-Spark scale-up noted as a phase-2 hardware option.

## 1. The one number that governs everything: 273 GB/s

The DGX Spark has **128 GB of LPDDR5x unified memory at 273 GB/s** ([NVIDIA product page](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)). Two consequences drive every model choice:

- **Capacity is generous.** 128 GB *holds* models NVIDIA rates up to ~200 B params (quantized), and the marketing ceiling is "100-billion-parameter models" for the Spark vs. 1-trillion-class for the larger DGX Station ([NVIDIA blog](https://blogs.nvidia.com/blog/dgx-spark-and-station-open-source-frontier-models/)).
- **Bandwidth is the governor.** Autoregressive decode reads the active weights + KV cache **once per token**. At 273 GB/s, token/second scales inversely with how many bytes are active per token. This is why a 27 B model runs at ~50 tok/s while a 2.4 T model on the same box runs at 0.09 tok/s — the box can *hold* both; only one is *interactive*.

The single most important lever against the bandwidth wall is **quantization**. NVIDIA's **NVFP4** format compresses weights up to ~70% ([NVIDIA blog](https://blogs.nvidia.com/blog/dgx-spark-and-station-open-source-frontier-models/)); fewer bytes per active weight means more tokens per second on the same 273 GB/s.

## 2. Three regimes of what fits

| Regime | Model & stack (sourced) | Footprint | Throughput |
|---|---|---|---|
| **Interactive sweet spot** — ~20–30 B, NVFP4 W4A4 | Qwen3-27B via **SGLang**, OpenAI API on `:8888`, native 262K ctx (1M with YaRN) | ~22 GB weights + ~2.7 GB draft model, FP8 KV cache | **51.5 tok/s** single-stream (code); **227.6 tok/s** aggregate at 16 concurrent streams |
| **Capacity ceiling** — ~100–200 B | **DeepSeek-V4-Flash 0731**, EXL3 3-bit, REAP-pruned to 216/256 experts, NVIDIA vLLM 26.02 + `sparkinfer`, K5 speculative decode | ~107 GB weights; server holds ~94% of unified memory | **44–47 tok/s** decode at 384K ctx; ~625 tok/s prefill (decays past ~300K accumulated) |
| **"Because you can" stunt** — 2.4 T | Qwen3.8-2.4T (Unsloth `UD-Q1_0`, 1.19 bpw) via **vllm.cpp**, CPU, mmap expert-offload | 370 GB on NVMe, ~62 GB resident RAM | **~0.09 tok/s** — NVMe-bound at ~6.95 GB read per token |

Sources: [Qwen3-27B SGLang recipe](https://github.com/MiaAI-Lab/Qwen3.8-27B-SGLang-DGX-Spark), [DeepSeek-V4-Flash single-Spark recipe](https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-One-DGX-Spark), [vllm.cpp Qwen3.8-2.4T doc](https://github.com/mudler/vllm.cpp/blob/main/docs/models/qwen3-8-2-4t.md).

**Reading the table:** the sweet spot is the demo workhorse — sub-second first token, 50+ tok/s, and it holds 16 concurrent users at 227 tok/s aggregate, which is plenty for a live booth or a multi-flow NiFi pipeline. The capacity ceiling is real but single-digit-user: a ~100 B model at 44 tok/s is a great "look what a $4k desktop runs" moment, not a throughput engine. The 2.4 T stunt is a talking point ("this desktop is *holding* a 2.4-trillion-parameter model"), not a demo you'd run live.

## 3. Serving stacks

All of these expose an **OpenAI-compatible endpoint**, which matters for the Cloudera bridge (§5) and for reuse of the existing NiFi `InvokeHTTP` RAG flows without modification.

- **SGLang** — the interactive-tier winner in the sourced recipes (NVFP4 W4A4, FP8 KV, speculative decode variants for code vs. long-form). Fastest path to a usable local endpoint.
- **NVIDIA vLLM / `sparkinfer`** — the capacity-tier stack; handles the pruned/quantized 100 B+ recipes with speculative decoding and compressed MLA KV.
- **llama.cpp** — NVIDIA collaborated on a **+35% average uplift** on Spark ([NVIDIA blog](https://blogs.nvidia.com/blog/dgx-spark-and-station-open-source-frontier-models/)); the broadest model/GGUF coverage, best for quick "does it run" checks.
- **vllm.cpp** — the extreme-offload path (mmap experts from NVMe); only relevant for the stunt tier.
- **NVIDIA NIM microservices** — the box ships preconfigured with the NVIDIA AI stack and CUDA-X libraries. NIM is the stack that matches production **Cloudera AI Inference** (§5), so it is the strategically-aligned choice even where SGLang is faster to stand up.

## 4. Scale-up: two Sparks over ConnectX-7

The Spark has a **ConnectX-7 (200 Gb/s)** NIC. Two boxes cluster over **InfiniBand + NCCL** with `tensor-parallel-size 2` / `pipeline-parallel-size 1`, head node `NODE_RANK=0` + worker `NODE_RANK=1`, running DeepSeek-V4-Flash at a **1M-token context** ([MiaAI-Lab dual-Spark recipe](https://github.com/MiaAI-Lab/DeepSeek-V4-Flash-Dual-DGX-Spark-1M-Context)). MiaAI-Lab also ships `sparkDash`, a multi-Spark monitoring dashboard.

**Position for us:** single-box is the readiness target now. Dual-Spark is a *phase-2 hardware* note — if a second box appears (team pool, per the `nvidia-request.md` "expand to additional SEs" step), the same recipes scale to 1M context with no software rework. Not built now.

## 5. The Cloudera bridge (equal-weight half)

The Spark isn't just a local toy — it's a **local mirror of the production Cloudera AI Inference pattern**:

- **NIM is integrated into Cloudera AI Inference** (formerly Cloudera Machine Learning), delivering up to **36× faster inference on NVIDIA GPUs**, and it runs **on-prem as of Cloudera Data Services 1.5.5 (Aug 2025)** ([Cloudera + NVIDIA](https://www.cloudera.com/partners/solutions/nvidia.html)).
- The **RAPIDS Accelerator for Apache Spark** is integrated into CDP for GPU-accelerated data prep.
- Cloudera's framing is **"bring AI compute to data"** — private AI inside the security perimeter.

Because both the local Spark endpoint and Cloudera AI Inference speak the **same OpenAI/NIM API shape**, the SE story is concrete, not aspirational: **prototype an agent/RAG flow against the model on the desk, then repoint the base URL at Cloudera AI Inference to scale it** — same client code, same API, same NIM. That "develop local → scale to Cloudera AI" arc is the through-line of the demo plan (work-stream C).

## 6. Recommended demo-driver models (Phase 0 stop-and-review)

Lock these before writing the runbook:

- **Lead / interactive:** a **~27 B NVFP4** model served via SGLang (or NIM for Cloudera alignment) — the workhorse for RAG, chat, and multi-stream NiFi flows at 50+ tok/s.
- **Stretch / capacity:** a **~100 B** quantized model (DeepSeek-V4-Flash-class) via NVIDIA vLLM — the "look what the desktop holds" showpiece at 44–47 tok/s.
- **Talking point only:** the 2.4 T stunt — mention, don't demo.

## Verification (definition of done)

- Every throughput/footprint claim carries a source link (satisfied above).
- The three-regime table is the reference the runbook (B) and demo plan (C) size against.
- Phase 0 closes when the 2–3 demo-driver models are locked with Steven.

## When this ships

- The locked model list feeds `nvidia-dgx-spark-runbook.md` (which model to pull first) and `nvidia-dgx-spark-cloudera-demos.md` (which model backs each demo).
- If promoted to a public blog later, strip issue numbers and internal framing per `agent/writing-style.md`.

## Resources

- [DGX Spark product page (specs)](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)
- [NVIDIA blog — DGX Spark & Station frontier models](https://blogs.nvidia.com/blog/dgx-spark-and-station-open-source-frontier-models/)
- [Cloudera + NVIDIA partner page](https://www.cloudera.com/partners/solutions/nvidia.html)
- [Red Hat — RHEL on DGX Spark](https://www.redhat.com/en/blog/supercharging-local-ai-development-rhel-nvidia-dgx-spark)
- [MiaAI-Lab — DeepSeek-V4-Flash single-Spark](https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-One-DGX-Spark) · [dual-Spark 1M ctx](https://github.com/MiaAI-Lab/DeepSeek-V4-Flash-Dual-DGX-Spark-1M-Context) · [Qwen3-27B SGLang](https://github.com/MiaAI-Lab/Qwen3.8-27B-SGLang-DGX-Spark)
- [mudler/vllm.cpp — Qwen3.8-2.4T doc](https://github.com/mudler/vllm.cpp/blob/main/docs/models/qwen3-8-2-4t.md)
- Source leads (paywalled to WebFetch, HTTP 402): x.com/jmurillocode/status/2091598658425004160 · x.com/huchkw/status/2089385814086262981 · x.com/MinLiBuilds/status/2089377416032735716
