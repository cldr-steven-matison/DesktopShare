# NVIDIA DGX Spark — Capability Landscape

> **Status (2026-08-28):** the box is `spark-dd06` and the **full Phase-0 model set is locked and standing up on it** — lead, capacity/stretch, and the embed / rerank / STT tier. This closes the expansion work-stream **A** ([#232](https://github.com/cldr-steven-matison/DesktopShare/issues/232)) owed: MoE-vs-dense (§2.5), the serving-engine table (§3.5), the 128 GB co-hosting budget (§5.5), and three sourced candidates per slot with the lock (§6). Numbers tagged **[box]** are measured on `spark-dd06`; the rest carry their source and date. Where a **[box]** number and a community number disagree, the box wins and the community one is kept as a dated cross-check. The dated, confidence-tagged corpus in `nvidia-dgx-spark-research.md` §2/§4/§5 is the source of record for anything not yet measured here. "The Spark" below means the DGX Spark.
>
> **Status (2026-08-26):** box landed as `spark-dd06`; first-package draft, expansion owed under #232.
> **Status (2026-08-24):** Work-stream A of the readiness EPIC ([#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226)), authored before the box was in hand.

## 1. The one number that governs everything: 273 GB/s

The DGX Spark has **128 GB of LPDDR5x unified memory at 273 GB/s** ([NVIDIA product page](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)). Two consequences drive every model choice:

- **Capacity is generous.** 128 GB *holds* models NVIDIA rates up to ~200 B params (quantized); the marketing ceiling is "100-billion-parameter models" for the Spark vs. 1-trillion-class for the larger DGX Station ([NVIDIA blog](https://blogs.nvidia.com/blog/dgx-spark-and-station-open-source-frontier-models/)).
- **Bandwidth is the governor.** Autoregressive decode reads the **active** weights + KV cache once per token. At 273 GB/s, tokens/second scales inversely with how many bytes are active per token. The box can *hold* a 2.4 T model and a 27 B model; only one is *interactive*.

The single biggest lever against the bandwidth wall is **how few bytes are active per token** — set by two things: **quantization** (NVIDIA's **NVFP4** compresses weights up to ~70% — [NVIDIA blog](https://blogs.nvidia.com/blog/dgx-spark-and-station-open-source-frontier-models/)) and **sparsity** (an MoE activates only a fraction of its parameters per token — §2.5). The two multiply, which is why the locked lead — a 35 B model with only ~3 B active, at NVFP4 — decodes faster on this box than its raw parameter count suggests.

## 2. Three regimes of what fits

| Regime | Model & stack | Footprint | Throughput |
|---|---|---|---|
| **Interactive sweet spot** — ~20–35 B MoE, NVFP4 | **`nvidia/Qwen3.6-35B-A3B-NVFP4`** via **vLLM** 0.28 (NVIDIA DGX Spark playbook recipe), OpenAI API on `:8000`, 262K ctx, fp8 KV, MTP spec-decode ×3 | ~22 GB weights; **~55 GB resident** at `--gpu-memory-utilization 0.6` (23 GB KV cache, 1.96 M-token pool) | **80–87 tok/s** single-stream decode, **~0.1 s** first token **[box, 2026-08-27]** |
| **Capacity ceiling** — ~100–120 B MoE | **`nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`** via vLLM, swap-in on `:8000` | ~72 GB weights + 14.8 GB KV at `0.72`; ~7 min load from cached weights | **15.5 tok/s** single-stream, **41.5 tok/s** at 4-way concurrency, **TTFT ~0.42 s** **[box, 2026-08-28]** (shared box, vLLM 0.28, no spec-decode); clean-box benchmark reports 22.7–23.7 tok/s ([vLLM DGX Spark](https://vllm.ai/blog/2026-06-01-vllm-dgx-spark), 2026-06-01, [med]) |
| **"Because you can" stunt** — 2.4 T | Qwen3.8-2.4T (Unsloth `UD-Q1_0`, 1.19 bpw) via **vllm.cpp**, CPU, mmap expert-offload | 370 GB on NVMe, ~62 GB resident RAM | **~0.09 tok/s** — NVMe-bound at ~6.95 GB read/token ([vllm.cpp doc](https://github.com/mudler/vllm.cpp/blob/main/docs/models/qwen3-8-2-4t.md)) |

**Reading the table.** The sweet spot is the demo workhorse — sub-second first token, 80+ tok/s, room for the embed/rerank/STT tier and the whole CSO stack alongside it (§5.5). The capacity ceiling is real but single-digit-user: a ~120 B model at ~23 tok/s is a "look what a $4k desktop runs" moment, not a throughput engine, and it cannot co-host — it is a swap-in that displaces the lead (§5.5). The 2.4 T stunt is a talking point ("this desktop is *holding* a 2.4-trillion-parameter model"), not a live demo.

**On the sweet-spot number.** The verified single-box band for a 20B–120B MoE is **~45–61 tok/s** across llama.cpp/SGLang ([research §5, `[3-0]`](https://github.com/ggml-org/llama.cpp/discussions/16578)); the lead sits **above** it because vLLM's MTP speculative decode on a 3 B-active model spends far fewer bytes per accepted token than a dense-attention baseline. Community reference points for the same class, same hardware, all dated and engine-tagged: the MiaAI-Lab Qwen3.8-27B SGLang recipe measured DSpark 51.5 (code) / 18.3 (essay), EAGLE/MTP 34.5 / 24.1, DFlash2 50.9 / 25.4 tok/s in one session ([research §2](https://github.com/MiaAI-Lab/Qwen3.8-27B-SGLang-DGX-Spark), [med]); an X report puts Qwen3.6-35B-A3B at 128 tok/s with spec decoding ([jmurillocode, 2026-08-23](https://x.com/jmurillocode/status/2091598658425004160), [med]). The old draft's "227.6 tok/s aggregate at 16 concurrent streams" had no source in the corpus and is dropped.

## 2.5 MoE vs dense — why the active-parameter shape wins here

On a bandwidth-bound box the number that sets decode speed is not total parameters but **bytes read per token**. A dense model reads *all* its weights every token; a Mixture-of-Experts model routes each token to a few experts and reads only those. So `Qwen3.6-35B-A3B` (35 B total, **~3 B active**) and `Nemotron-3-Super-120B-A12B` (120 B total, **~12 B active**) behave, for decode throughput, like a ~3 B and a ~12 B model respectively — while still *holding* their full parameter count in the 128 GB pool for quality. That is the whole reason the Spark's "100-billion-parameter" ceiling is usable at all: a dense 120 B at FP16 would read ~240 GB/token and never fit, let alone run; the same class as a 12 B-active NVFP4 MoE reads a few GB/token and clears 20 tok/s. Dense models still have a place at the small end (a 4–8 B dense embed or draft model is fine), but every **demo-driver** slot on this box is an NVFP4 MoE by design. The research corpus records the dense penalty directly: dense FP16 in the 20–120 B range runs at ~3.5 tok/s ([research §5](https://github.com/ggml-org/llama.cpp/discussions/16578)).

## 3. Serving stacks

All of these expose an **OpenAI-compatible endpoint**, which matters for the Cloudera bridge (§5) and lets the existing NiFi `InvokeHTTP` RAG flows target the box unmodified.

- **vLLM** — the lead and capacity stack, and NVIDIA's own first-party DGX Spark recipe path (the playbooks ship vLLM invocations for both Qwen3.6-35B and Nemotron-120B). fp8 KV, FlashInfer, Marlin MoE, MTP speculative decode. This is what runs on `:8000` **[box]**.
- **TEI** (Text Embeddings Inference) — the embed and rerank stack. NVIDIA's sm_121 prebuilt image (`121-latest`) runs native on GB10 — no `CUDA_COMPUTE_CAP=121` build **[box]**. Serves both embedders (`/embed`) and cross-encoder rerankers (`/rerank`).
- **whisper.cpp (CUDA)** — the STT stack. Not turnkey on GB10: a source build with `CMAKE_CUDA_ARCHITECTURES="120;121"` on an Ubuntu-24.04 CUDA-13 base (faster-whisper/CTranslate2 has no sm_121 build — §3.5).
- **SGLang** — the community interactive-tier winner in the sourced recipes (NVFP4 W4A4, EAGLE/MTP variants). Fastest community path to a usable endpoint; we run vLLM instead for NVIDIA-recipe and Cloudera-NIM alignment, and keep SGLang as the dated cross-check in §2.
- **llama.cpp** — NVIDIA collaborated on a **+35% average uplift** on Spark ([NVIDIA blog](https://blogs.nvidia.com/blog/dgx-spark-and-station-open-source-frontier-models/)); broadest GGUF coverage, best for quick "does it run" checks.
- **NVIDIA NIM microservices** — the box ships preconfigured with the NVIDIA AI stack. NIM is the shape that matches production **Cloudera AI Inference** (§5), so it is the strategically-aligned serving mode even where vLLM is faster to stand up.

## 3.5 Serving-engine picks at a glance

| Tier | Engine | Why it, not the others |
|---|---|---|
| Chat / RAG generation | **vLLM** | NVIDIA's own DGX Spark recipe for both demo-driver models; MTP spec-decode; same OpenAI shape as prod's vLLM so the cutover ladder is a drop-in |
| Embeddings | **TEI** | sm_121 prebuilt runs native on GB10 [box]; one image serves embed + rerank; `gpu_memory_utilization` barely dents the pool |
| Rerank | **TEI `/rerank`** | same image and container pattern as embeddings; cross-encoder scoring in one call |
| STT | **whisper.cpp (CUDA)** | the one path that builds on sm_121/CUDA-13/aarch64 today (RTF ~0.04 [box]); faster-whisper's CTranslate2 has no such build ([research §Whisper](https://forums.developer.nvidia.com/t/running-whisper-cpp-stt-server-on-dgx-spark-gb10-arm64-cuda-13-via-docker/371803)) |
| Cloudera-parity mode | **NIM** | matches Cloudera AI Inference's API for the "develop local → scale to Cloudera AI" demo (§5) |

## 4. Scale-up: two Sparks over ConnectX-7

The Spark has a **ConnectX-7 (200 Gb/s)** NIC. Two boxes cluster over **InfiniBand + NCCL** with `tensor-parallel-size 2`, running DeepSeek-V4-Flash at a **1M-token context** ([MiaAI-Lab dual-Spark recipe](https://github.com/MiaAI-Lab/DeepSeek-V4-Flash-Dual-DGX-Spark-1M-Context)); a field build cross-checks this on real GB10 hardware with concrete UMA and NCCL gotchas ([rajsinghtechbot/dgx-spark-vllm-k8s](https://github.com/rajsinghtechbot/dgx-spark-vllm-k8s), [research §4](https://github.com/rajsinghtechbot/dgx-spark-vllm-k8s)).

**Position for us:** single-box is the readiness target. Dual-Spark is a *phase-2 hardware* note — if a second box appears (`nvidia-request.md` "expand to additional SEs"), the same recipes scale to 1M context with no software rework. Not built now.

## 5. The Cloudera bridge (equal-weight half)

The Spark is a **local mirror of the production Cloudera AI Inference pattern**:

- **NIM is integrated into Cloudera AI Inference**, delivering up to **36× faster inference on NVIDIA GPUs**, and runs **on-prem as of Cloudera Data Services 1.5.5 (Aug 2025)** ([Cloudera + NVIDIA](https://www.cloudera.com/partners/solutions/nvidia.html)).
- The **RAPIDS Accelerator for Apache Spark** is integrated into CDP for GPU-accelerated data prep.
- Cloudera's framing is **"bring AI compute to data"** — private AI inside the security perimeter.

Because both the local Spark endpoint and Cloudera AI Inference speak the **same OpenAI/NIM API shape**, the SE story is concrete: **prototype an agent/RAG flow against the model on the desk, then repoint the base URL at Cloudera AI Inference to scale it** — same client code, same API, same NIM. That "develop local → scale to Cloudera AI" arc is the through-line of the demo plan (work-stream C).

## 5.5 The 128 GB co-hosting budget

The box runs the demo-driver models **and** its own k3s + CSO stack in one 128 GB pool, so sizing is a budget, not a single model's footprint. The authoritative, measured budget lives in `nvidia-dgx-spark-k3s-cso.md` §5; the model-side summary:

- **Usable pool ~119.67 GiB**, of which ~24–29 GiB is driver/hardware reserved — **~93 GiB is the stable ceiling**; 85 GiB OOM-kills a large model on load, 95 GiB won't schedule ([research §4](https://github.com/rajsinghtechbot/dgx-spark-vllm-k8s), field-measured).
- **The co-hostable serving tier** — lead (`~55 GB` **[box]**) + embeddings (bge-m3, `~7 GB` delta **[box]**) + rerank (bge-reranker-v2-m3, `~5 GB` delta **[box]**) + STT (whisper.cpp large-v3, `~4 GB` **[box]**) — runs alongside the k3s stack (measured ~25 GB) with headroom. **Verified all four co-resident and healthy on `spark-dd06` 2026-08-28** (`:8000`/`:8001`/`:8002`/`:8003` all answer), the box sitting at ~84–93 GB used / ~28–37 GB available.
- **The stretch ~120 B model is a mode, not a resident.** It holds ~85% of the pool, so standing it up means **stopping the lead first** — it swaps in on `:8000`, and the streaming stack scales to zero for the duration (the same scale-to-0 discipline `cso-operator-app-plan.md` documents, which destroys nothing).

## 6. Locked demo-driver models (Phase 0 — closed)

Locked before the first non-lead weight pull on `spark-dd06`. Each slot lists the pick, why, and the sourced runners-up so a re-eval starts from candidates, not a blank page.

**Lead / interactive — LOCKED `nvidia/Qwen3.6-35B-A3B-NVFP4` (vLLM, `:8000`).**
- *Why:* NVIDIA's own first-party DGX Spark recipe; 3 B-active NVFP4 MoE — the proven-fast shape on GB10; 80–87 tok/s **[box]**; same OpenAI endpoint as prod's vLLM so the cutover ladder is a drop-in.
- *Runners-up:* `Qwen3.8-27B-NVFP4` on SGLang (MiaAI-Lab recipe, 51.5 tok/s code [med]) — faster to stand up, but off the NVIDIA-recipe/NIM-parity path; `gpt-oss-120B` MXFP4 (~51 tok/s SGLang [med]) — heavier, edges into the capacity tier.

**Stretch / capacity — LOCKED `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` (vLLM, `:8000` swap-in) [box].**
- *Why:* NVIDIA's flagship NVFP4 MoE family, first-party vLLM recipe, ~12 B active; drops into the lead's vLLM pattern (same image, swap the model). **Box-measured on `spark-dd06` 2026-08-28: 15.5 tok/s single-stream, 41.5 tok/s at 4-way concurrency, TTFT ~0.42 s**, ~72 GB weights + 14.8 GB KV cache (2.35 M tokens, 17.9× concurrency) at `--gpu-memory-utilization 0.72`, ~7 min load from cached weights — run on the shared box (k3s + KB co-resident) on vLLM 0.28 with no speculative decode, so below vLLM's clean-box 22.7–23.7 tok/s benchmark ([2026-06-01](https://vllm.ai/blog/2026-06-01-vllm-dgx-spark), [med]); a cu130-nightly + MTP config is the path to close that gap. Weights pre-staged in `~/hf-hub`; swap is `vllm-stretch-serve.sh {up,down}`.
- *Thermals under sustained load* **[box, 2026-08-28]**: a 4-minute 16-client saturation run (engine pinned at its 4 decode slots, 96% GPU util, SM clocks 2522 MHz) took the GB10 from **idle 51 °C / 13 W** to a **steady ~65 °C / 41 W**, **peak 69 °C / 43 W** — the box runs the 120 B stretch model flat-out well inside its thermal envelope, no throttling. (The reported power is the GPU rail; whole-box draw is higher.) External check: an infrared scan of the chassis read **~114–115 °F (~46 °C)** case surface at peak load.
- *Runners-up:* `DeepSeek-V4-Flash-0731` EXL3 (MiaAI-Lab single-Spark, ~107 GB, 1,000 tok/s prefill / 59 tok/s multi-agent [med]) — the dual-Spark 1M-context path; `gpt-oss-120B` — simpler but lower-quality-for-size.

**Embeddings — LOCKED `BAAI/bge-m3` (TEI, `:8001`, 1024-d) [box].**
- *Why:* the 1024-d RAG-parity shape the corpus names for DGX-Spark RAG; TEI sm_121 proven native on the box; co-hosts with the lead at ~7 GB. Kept separate from the KB's nomic-768-d embedder (`tei-kb` :8080) — different collection, different dim.
- *Runners-up:* `nomic-embed-text-v1.5` (768-d — what the KB uses, and the fleet's `my-rag-collection` shape); `nvidia/Nemotron-3-Embed` 8B/1B (community "best current model" [med], heavier); `Qwen3-Embedding-4B/0.6B` for small RAG.

**Rerank — LOCKED `BAAI/bge-reranker-v2-m3` (TEI `/rerank`, `:8002`) [box].**
- *Why:* the cross-encoder pair to bge-m3; same TEI image and container pattern; scored the DGX-Spark doc 0.9997 vs 0.00002 for an unrelated doc on smoke **[box]**.
- *Runners-up:* `bge-reranker-large`; a vLLM-served reranker (AGmind's shape) — heavier, needed only if TEI can't serve a chosen model.

**STT — LOCKED whisper.cpp `large-v3` (CUDA, `:8003`) [box].**
- *Why:* parity with prod's Whisper `:8001` (Streamers captioning); the one STT path that builds on sm_121/CUDA-13/aarch64 today — the GB10 shows up as `compute capability 12.1, use gpu = 1`. Box-measured **RTF ~0.04 (≈20–25× realtime)**, 11 s of audio transcribed in 0.43–0.57 s **[box, 2026-08-28]** — the RTF the research corpus flagged as never-measured-on-this-hardware. ~4 GB (3.1 GB model + CUDA context).
- *Runners-up:* `Mekopa/whisperx-blackwell` (115× GPU, adds pyannote diarization [med]) if diarization is needed; faster-whisper — blocked upstream on GB10 until CTranslate2 ships a CUDA-13/sm_121 build.

**Talking point only:** the 2.4 T stunt — mention, don't demo.

## Verification (definition of done)

- Every throughput/footprint claim is either **[box]**-measured on `spark-dd06` or carries a source link + date (satisfied above).
- The three-regime table + §6 are the reference the runbook (B) and demo plan (C) size against.
- Phase 0 closes when the demo-driver set is locked with Steven — **the full set is locked (§6)**; the box-measured stretch and STT numbers land as those endpoints finish standing up this session.

## When this ships

- The locked list feeds `nvidia-dgx-spark-runbook.md` (which model to pull, as-built) and `nvidia-dgx-spark-cloudera-demos.md` (which model backs each demo).
- If promoted to a public blog later, strip issue numbers and internal framing per `agent/writing-style.md`.

## Resources

- [DGX Spark product page](https://www.nvidia.com/en-us/products/workstations/dgx-spark/) · [NVIDIA blog — DGX Spark & Station frontier models](https://blogs.nvidia.com/blog/dgx-spark-and-station-open-source-frontier-models/) · [Cloudera + NVIDIA](https://www.cloudera.com/partners/solutions/nvidia.html)
- [vLLM DGX Spark benchmark (Nemotron-120B)](https://vllm.ai/blog/2026-06-01-vllm-dgx-spark) · [NVIDIA/dgx-spark-playbooks](https://github.com/NVIDIA/dgx-spark-playbooks)
- MiaAI-Lab: [DeepSeek-V4-Flash single-Spark](https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-One-DGX-Spark) · [dual-Spark 1M ctx](https://github.com/MiaAI-Lab/DeepSeek-V4-Flash-Dual-DGX-Spark-1M-Context) · [Qwen3.8-27B SGLang](https://github.com/MiaAI-Lab/Qwen3.8-27B-SGLang-DGX-Spark)
- [whisper.cpp on GB10 (sm_121 build flag)](https://forums.developer.nvidia.com/t/running-whisper-cpp-stt-server-on-dgx-spark-gb10-arm64-cuda-13-via-docker/371803) · [TEI sm_121 tags](https://github.com/huggingface/text-embeddings-inference/pkgs/container/text-embeddings-inference)
- Serve scripts: `files/issue-226/vllm-serve.sh` · `tei-embed-serve.sh` · `tei-rerank-serve.sh` · `whisper-serve.sh` · `vllm-stretch-serve.sh` · budget: `nvidia-dgx-spark-k3s-cso.md` §5 · corpus: `nvidia-dgx-spark-research.md` §2/§4/§5
