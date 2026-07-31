# The art of the possible: edge AI on NVIDIA Jetson in 2026

Outward planning research, done here on the master machine — the frontier of what Jetson-class edge hardware can do in 2026, and what's worth reaching for on our edge fleet. This is deliberately *not* scoped to what any one box has installed today. It's the ceiling: what NVIDIA and the community are actually shipping and demoing now, mapped to which tier of hardware you need to get there.

The point of researching this on the master machine is to plan. We run an Orin Nano at the edge today; this says what that class can already reach for, and what the next tier up unlocks if we ever want it.

:trophy: **Confidence is tagged inline** — **[3-0]** survived unanimous adversarial verification against primary NVIDIA sources; **[med]** is real but single-sourced or carries a functional caveat. Figures that got refuted in verification (a bogus "241 TOPS Super Mode," a nonexistent "NemoClaw" framework, unconfirmed Thor latency numbers) are deliberately left out — see the note at the end.
{: .notice--warning}

## The one thing that changed in 2026

A year ago, "generative AI at the edge" meant a quantized 1–3B LLM and not much else. In 2026 the whole multimodal stack — language, vision, audio, video, and *robot action* — runs on-device with no cloud dependency. Two forces got us here: the new **Jetson Thor** flagship at the top, and a stack of aggressive inference techniques (NVFP4 quantization, speculative decoding, MoE architectures, memory-efficiency tuning) that pull surprisingly large models down onto even the entry-level hardware.

The frontier has moved from "can it run a chatbot" to **physical AI** — vision-language-action models driving real robots, world foundation models, deterministic mixed-criticality inference. That's the headline. The rest of this doc is the detail, and where each thing lands on the hardware ladder.

## The hardware ladder

Three tiers matter when planning what to deploy where:

| Tier | Module | Rough capability envelope |
|---|---|---|
| **Entry** | **Orin Nano 8GB** (what we run) | Small quantized LLMs/VLMs, a *full* real-time multimodal pipeline (see Reachy Mini below), tiny TensorRT detection/classification, faster-whisper ASR, Kokoro TTS |
| **Mid** | AGX Orin 32/64GB | Larger VLMs, multi-stream video analytics (DeepStream/Metropolis), Nemotron Nano Omni-class multimodal; GR00T-family VLA is an open question at this tier (see below) |
| **Flagship** | **Jetson Thor (T5000)** | 70B-class LLMs (quantized), 120B MoE reasoning models, VLA/robotics (GR00T N1.5), world models, NVFP4, GPU partitioning (MIG) |

**Jetson Thor (T5000)** is the new top of the stack **[3-0]**: Blackwell GPU, **2070 TFLOPS sparse FP4**, **128 GB LPDDR5X** at 273 GB/s, 40–130W envelope, **up to 7.5× the AI compute and 3.5× the energy efficiency of AGX Orin**. The AGX Thor Developer Kit is shipping at **$3,499**. ([Jetson Thor intro](https://developer.nvidia.com/blog/introducing-nvidia-jetson-thor-the-ultimate-platform-for-physical-ai/), [product page](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-thor/), [module comparison](https://developer.nvidia.com/embedded/jetson-modules))

One caveat to keep honest: "2070 TFLOPS sparse FP4" is a theoretical peak under ideal sparsity — standard industry quoting, real throughput is lower. The 7.5× vs AGX Orin is NVIDIA's own published ratio and directionally sound.

## What's newly possible, by domain

### Generative AI — the quantization dividend

The reason bigger models fit on small boxes is quantization, not more RAM. Concrete, verified figures **[3-0 / 2-1]**: quantizing **Qwen3-8B** FP16→**W4A16 saves ~10 GB**; **Qwen3-4B** BF16→**INT4 saves ~5.6 GB** (measured on Orin NX 16GB). AWQ, GGUF, W4A16, INT4, and MoE architectures are what make otherwise-infeasible deployments run locally with no cloud. ([Maximizing memory efficiency on Jetson](https://developer.nvidia.com/blog/maximizing-memory-efficiency-to-run-bigger-models-on-nvidia-jetson/), [Jetson AI Lab](https://jetson-ai-lab.com))

The inference engine behind the frontier is **TensorRT Edge-LLM** **[3-0]** — open source ([github.com/NVIDIA/TensorRT-Edge-LLM](https://github.com/NVIDIA/TensorRT-Edge-LLM)), targeting JetPack 7.1, shipping **EAGLE-3 speculative decoding, NVFP4 quantization, and chunked prefill**. Note NVFP4 is native only on Blackwell — i.e. Thor, not Orin. ([TensorRT Edge-LLM announcement](https://developer.nvidia.com/blog/accelerating-llm-and-vlm-inference-for-automotive-and-robotics-with-nvidia-tensorrt-edge-llm/))

New model families worth knowing about:
- **Nemotron 3 Nano Omni (30B-A3B)** **[2-1]** — Mamba2-Transformer hybrid MoE, ~30B total / ~3B active, handles **text, vision, audio, and video**, in BF16/FP8/NVFP4. Targets Orin and up. ([HF card](https://huggingface.co/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16))
- **Nemotron 3 Super (120B-A12B)** **[2-1]** — 120B total / 12B active hybrid MoE reasoning model, Thor + NVFP4 only.
- On Thor directly **[3-0]**: Llama 3.1/3.3, Qwen3-30B-A3B, DeepSeek-R1-Distill variants, VLMs like Qwen2.5-VL-3B/7B. The 70B-class only fits *quantized* (FP4/FP8) within Thor's 128 GB — "on-device" ≠ full precision at the top end.

### The proof point that matters for our Orin Nano

**Reachy Mini runs a full multimodal conversational-robot pipeline in 4.5 GB on an Orin Nano 8GB** **[3-0]** — VLM + ASR + TTS *concurrently*: Cosmos-Reason2-2B VLM (Q4_K_M 4-bit GGUF via llama.cpp, 2.2 GB) + Faster-Whisper small.en + Kokoro TTS, down from 7.6 GB via 4-bit quant, headless OS (-0.7 GB), and pipeline restructuring. ([source](https://developer.nvidia.com/blog/maximizing-memory-efficiency-to-run-bigger-models-on-nvidia-jetson/))

That's the ceiling for the box we actually have: not a version-check stub, not a single tiny classifier — a real-time see/hear/speak loop. Everything below "small LLM/VLM + faster-whisper + Kokoro TTS" is in reach on the current hardware.

### Vision frontier

Open-vocabulary and foundation-model perception, TensorRT-optimized for Jetson: **NanoOWL** (open-vocab detection, [repo](https://github.com/NVIDIA-AI-IOT/nanoowl)) and **NanoSAM** (promptable segmentation, [repo](https://github.com/NVIDIA-AI-IOT/nanosam)) run on the Orin tier. For multi-stream video analytics and production pipelines, **DeepStream** ([blog](https://developer.nvidia.com/blog/tag/deepstream)) and **Metropolis** ([platform](https://developer.nvidia.com/metropolis)) are the flagship stacks — those scale with the tier.

### Speech & audio

Real-time on-device conversational AI is solved at the edge now: **Riva** ASR/TTS ([release notes](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/release-notes.html)), plus the lightweight community path proven in Reachy Mini — **Faster-Whisper** + **Kokoro TTS**, both small enough for the Orin Nano tier.

### Robotics & physical AI — the actual frontier

This is where 2026 is genuinely new. **Vision-Language-Action (VLA)** models drive real robots on-device:
- **Isaac GR00T** **[3-0]** — NVIDIA's open reference platform for humanoid robot foundation models ([GR00T](https://developer.nvidia.com/isaac/gr00t), [end-to-end policies](https://developer.nvidia.com/blog/develop-humanoid-robot-policies-end-to-end-with-nvidia-isaac-gr00t/)). GR00T N1.5 runs on Thor for real-time robot inference/control.
- Real 2026 deployment: **Matcha Bot** — dual robotic arms driven by GR00T N1.5 VLA on Jetson Thor, 1st place at an Embodied AI Hackathon **[3-0]** ([Jetson AI Lab](https://www.jetson-ai-lab.com/), [project](https://hackster.io/sigrobotics)).
- **Isaac ROS** ([platform](https://developer.nvidia.com/isaac/ros)) is the ROS2 integration layer; sim-to-real via Isaac Sim.
- **Cosmos3 Edge** **[med]** — 4B omnimodal *world foundation model* (multimodal reasoning + video generation + robot action policies), targeting AGX Orin/Thor ([models](https://jetson-ai-lab.com/models), [HF](https://huggingface.co/nvidia/cosmos3)). Caveats: no video-to-video yet, 256p/480p at 12–30fps, and Orin Nano deployment needs the *upcoming* FP8/NVFP4 variants — so at our tier it's aspirational today.

### Deterministic mixed-criticality (Thor only)

**JetPack 7.2 adds MIG on Thor** **[med]** — partitions the Blackwell GPU into two isolated instances (12 SMs/1536 CUDA cores for AI, 8 SMs/1024 for robotics/safety-critical), giving deterministic execution for mixed-criticality systems. Robotics-specific, Thor-exclusive. ([JetPack 7.2 agentic-edge blog](https://developer.nvidia.com/blog/deploy-agentic-ready-ai-at-the-edge-with-memory-efficiency-in-nvidia-jetpack-7-2/))

## Capability → minimum tier (planning map)

| Capability to reach for | Minimum Jetson tier |
|---|---|
| Tiny TensorRT detection/classification | Orin Nano |
| Small quantized LLM (1–4B, GGUF/INT4) | Orin Nano |
| Real-time VLM + ASR + TTS pipeline (Reachy-style) | **Orin Nano 8GB** (proven at 4.5 GB) |
| Open-vocab vision (NanoOWL/NanoSAM) | Orin Nano → AGX Orin |
| Multi-stream video analytics (DeepStream/Metropolis) | AGX Orin+ |
| Nemotron 3 Nano Omni (30B-A3B, 4-modality) | AGX Orin+ |
| VLA / GR00T-family robot control | Thor (AGX Orin 64GB unconfirmed — open question) |
| 70B-class LLM / Nemotron Super 120B (NVFP4) | **Thor only** |
| World foundation models (Cosmos3 Edge, full) | AGX Orin/Thor |
| GPU partitioning / deterministic mixed-criticality (MIG) | **Thor only** |

## What to reach for on our fleet

Given we run an Orin Nano 8GB today, the honest ambition ladder — cheap to aspirational:

1. **A real multimodal loop on the Orin Nano**, not a stub. The Reachy Mini recipe (Cosmos-Reason2-2B VLM Q4 GGUF + Faster-Whisper + Kokoro TTS, 4.5 GB) is a documented, reproducible target. This is the biggest jump in ambition available *on hardware we already own*.
2. **A small quantized LLM/VLM served locally** via llama.cpp GGUF — the quantization dividend (W4A16/INT4) makes 4–8B models tractable.
3. **Open-vocab vision** (NanoOWL/NanoSAM) if a camera's attached — foundation-model perception, TensorRT-optimized.
4. **The Thor tier is the reach-goal**, not today's box: VLA/robotics (GR00T), 70B-class reasoning, world models. If physical AI ever becomes the goal for the fleet, that's the $3,499 dev-kit conversation.

## Caveats — read before quoting any of this

- **"On-device" for big models means quantized.** Llama 3.3 70B and Nemotron Super 120B fit Thor's 128 GB only in FP4/FP8, not full precision.
- **NVFP4 is Blackwell/Thor-only.** The NVFP4 numbers do not transfer to Orin.
- **Some things are aspirational/"upcoming."** Cosmos3-Edge on Orin Nano needs FP4 variants NVIDIA listed as upcoming as of this research (July 2026). Confirm shipping status before planning a deployment on it.
- **jetson-ai-lab.com is NVIDIA's community lab (dusty-nv team), not product documentation.** Claims sourced only from it carry slightly less weight than developer.nvidia.com blog posts.
- **Refuted, deliberately excluded:** a "241 TOPS AGX Orin Super Mode," a curl-installable "NemoClaw" agentic framework, sub-200ms Thor TTFT, a "2× on top of 5×" Thor speedup, and a 10.5B "Alpamayo R1" VLA — all failed verification and are *not* in this doc. If you see them elsewhere, they didn't hold up here.

## Open questions worth a follow-up pass

- Real shipping status + throughput of NVFP4 Cosmos3-Edge on Orin Nano 8GB — available now, or still upcoming?
- Can GR00T N1.5 run on AGX Orin 64GB with quantization, or is Thor strictly required for the VLA family?
- What's the *actually supported* on-device agentic-loop stack for Jetson in 2026 (function-calling, tool use, memory)? The "NemoClaw" claim was bogus, so this is genuinely open.
- EAGLE-3 speculative-decoding gains (TTFT/TPOT) on Thor, and which model families benefit most.

## Sources

Primary unless noted. Retrieved 2026-07-31.

- Jetson Thor platform: [intro blog](https://developer.nvidia.com/blog/introducing-nvidia-jetson-thor-the-ultimate-platform-for-physical-ai/), [product page](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-thor/), [module comparison](https://developer.nvidia.com/embedded/jetson-modules)
- JetPack 7.2 / agentic edge / MIG: [blog](https://developer.nvidia.com/blog/deploy-agentic-ready-ai-at-the-edge-with-memory-efficiency-in-nvidia-jetpack-7-2/)
- TensorRT Edge-LLM: [announcement](https://developer.nvidia.com/blog/accelerating-llm-and-vlm-inference-for-automotive-and-robotics-with-nvidia-tensorrt-edge-llm/), [GitHub](https://github.com/NVIDIA/TensorRT-Edge-LLM)
- Memory efficiency / quantization / Reachy Mini: [blog](https://developer.nvidia.com/blog/maximizing-memory-efficiency-to-run-bigger-models-on-nvidia-jetson/)
- Model catalog (Nemotron, Cosmos3, VLA): [jetson-ai-lab.com/models](https://jetson-ai-lab.com/models), [jetson-ai-lab.com](https://www.jetson-ai-lab.com/)
- Isaac GR00T / ROS: [GR00T](https://developer.nvidia.com/isaac/gr00t), [end-to-end policies](https://developer.nvidia.com/blog/develop-humanoid-robot-policies-end-to-end-with-nvidia-isaac-gr00t/), [Isaac ROS](https://developer.nvidia.com/isaac/ros)
- Vision: [NanoOWL](https://github.com/NVIDIA-AI-IOT/nanoowl), [NanoSAM](https://github.com/NVIDIA-AI-IOT/nanosam), [DeepStream](https://developer.nvidia.com/blog/tag/deepstream), [Metropolis](https://developer.nvidia.com/metropolis)
- Speech: [Riva release notes](https://docs.nvidia.com/deeplearning/riva/user-guide/docs/release-notes.html)
- Edge-AI getting started / foundation models: [blog](https://developer.nvidia.com/blog/getting-started-with-edge-ai-on-nvidia-jetson-llms-vlms-and-foundation-models-for-robotics/)
- Benchmarks & containers: [jetson-ai-lab benchmarks](https://jetson-ai-lab.com/archive/benchmarks.html), [jetson-containers](https://github.com/dusty-nv/jetson-containers)
