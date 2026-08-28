# NVIDIA DGX Spark — Day-1 Setup Runbook

> **Status (2026-08-27):** on-box execution started under [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235). The Phase-0 model lock is made — lead model **`nvidia/Qwen3.6-35B-A3B-NVFP4` on NVIDIA's own DGX Spark vLLM playbook recipe** (`files/issue-226/vllm-serve.sh`), which supersedes §2's community SGLang recipe and §3 stays the stretch tier. Kubernetes on the box is **k3s** `v1.32.13+k3s1` on the host (`nvidia-dgx-spark-k3s-cso.md` §3). The root-level steps of §1/§4/§5 — OS updates, docker group, NVIDIA runtime, Java 21, Tailscale, ufw, k3s — are one idempotent script, `files/issue-226/spark-bootstrap.sh`; `kubectl`/`helm` are installed user-local. Each block below turns as-built as it runs.
>
> **Status (2026-08-26):** the box landed as `spark-dd06` and its as-built facts are in `CLAUDE-CHECKIN.md` — they supersede the §0/§1 expectations below (121 GB usable, 16 GB swap, 3.7 TB NVMe, driver 580.173.02, CUDA 13.0, Docker 29.2.1). Two conventions changed after this draft: the serving endpoint is **`:8000`** everywhere (this draft's `:8888` is superseded — the playbooks, the fleet and `nvidia-dgx-spark-k3s-cso.md` / `-efm-agent.md` all use `:8000`), and the NIM-vs-OpenAI-endpoint decision lives in `nvidia-dgx-spark-cloudera-aws.md` §4, not in work-stream C. The full device runbook expansion is owed under [#233](https://github.com/cldr-steven-matison/DesktopShare/issues/233); on-box execution is [#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235).
>
> **Status (2026-08-24):** Work-stream **B** of the DGX Spark readiness EPIC ([#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226)). **Authored on the Mac; executed on-box when the Spark lands.** This is the arrival-day checklist: from unbox to a hardened, LAN-reachable OpenAI-compatible endpoint. Commands are the *expected* shape from the sourced recipes and NVIDIA/Red Hat docs — verify each against the actual box (live state outranks docs) and fill the confirmed values back in on first run. Model choices come from `nvidia-dgx-spark-landscape.md` §6.

## 0. Before it arrives (do on the Mac now)

- [ ] Lock the demo-driver models with Steven (landscape §6): lead ~27 B NVFP4, stretch ~100 B.
- [ ] Reserve a static LAN IP / hostname for the box; decide its device label (`device:<box>`) and add its block to `CLAUDE-CHECKIN.md` on arrival.
- [ ] Pre-stage the recipe repos to clone on day 1 (landscape Resources).
- [ ] Confirm a Hugging Face token is available for weight pulls (~107 GB for the stretch model).

## 1. Boot & baseline

- [ ] First boot, complete DGX OS setup. Confirm the OS/kernel: `uname -a` (aarch64 expected).
- [ ] Confirm the GPU + driver + CUDA stack: `nvidia-smi` and `nvcc --version`. Record the CUDA-X / driver versions in the checkin block.
- [ ] Confirm unified memory: `free -g` should show ~128 GB. Note actual free headroom.
- [ ] Confirm NVMe free space: `df -h` — need ≥ ~110 GB free for the stretch model weights, more for the stunt tier.
- [ ] Docker + NVIDIA container runtime working: `docker run --rm --gpus all <cuda-base> nvidia-smi`.

> **RHEL option:** if running RHEL 10 instead of DGX OS (per the [Red Hat DGX Spark guidance](https://www.redhat.com/en/blog/supercharging-local-ai-development-rhel-nvidia-dgx-spark)), confirm the NVIDIA driver + container toolkit are installed before proceeding; the serving steps below are OS-agnostic once Docker+GPU works.

**As built, 2026-08-27 (`spark-dd06`).** Every root step of §1, §4 and §5 ran once from `files/issue-226/spark-bootstrap.sh` (`sudo bash …`, idempotent) — the user-level pieces from the Claude session. Results:

- Baseline unchanged from the roster: `uname -a` aarch64, kernel `6.17.0-1031-nvidia`; `nvidia-smi` driver `580.173.02` / CUDA `13.0`; `free -g` 121 GB total, ~111 GB free before serving; `df -h` 3.5 TB free. 17 DGX OS package updates applied, no reboot required.
- GPU in a container: `docker run --rm --gpus all nvcr.io/nvidia/cuda:13.0.1-base-ubuntu24.04 nvidia-smi` shows the GB10 — after `nvidia-ctk runtime configure --runtime=docker` + `systemctl restart docker` (the toolkit ships preinstalled but unregistered; Docker's default runtime stays `runc`). `tunas` added to the `docker` group (`sg docker -c` until re-login).
- Tools: `kubectl v1.32.13`, `helm v3.21.4` (user-local, `~/.local/bin`); k3s `v1.32.13+k3s1`; OpenJDK `21.0.12`; Tailscale joined as `100.104.155.57` / `nvidiaspark-1` on the array's `steven.matison@gmail.com` tailnet (a first join landed on `tunastreet@outlook.com` by picking the wrong account at the browser step — `tailscale logout` + `tailscale up` again fixed it); WindowsDesktop and StarlinkAI online as peers, EFM UP over the tailnet.
- §4 hardening: ufw enabled, default deny incoming (the box has a public IPv6 address); allowed: 22, 8000 and the four k3s NodePorts from `192.168.1.0/24`, everything on `tailscale0`, k3s pod/service CIDRs `10.42.0.0/16`, `10.43.0.0/16`. `earlyoom` was not installed. The serving container publishes `:8000` on `127.0.0.1` and `192.168.1.203` only (Docker-published ports bypass ufw), so it is never on `0.0.0.0`.
- Network: the box is on Wi-Fi (`wlP9s9`, `f8:3d:c6:f1:12:5a`, DHCP `192.168.1.203`); the 10 GbE port `enP7s7` (`4c:bb:47:2d:dd:06`) is unplugged. Static reservation on the router still to do.

## 2. Stand up the first endpoint (interactive tier — SGLang)

Fastest path to a usable endpoint (landscape §3). Using the sourced Qwen3-27B SGLang recipe shape:

```bash
git clone https://github.com/MiaAI-Lab/Qwen3.8-27B-SGLang-DGX-Spark
cd Qwen3.8-27B-SGLang-DGX-Spark
cp .env.sample .env          # set HF token, model path, context here
./start.sh                    # EAGLE/MTP speculative decode; OpenAI API on :8888
# ./start-dspark.sh           # coding-optimized variant
```

- [ ] Endpoint answers: `curl http://127.0.0.1:8888/v1/models`.
- [ ] First inference: `curl http://127.0.0.1:8888/v1/chat/completions -d '{"model":"...","messages":[{"role":"user","content":"hi"}]}'`.
- [ ] Record actual tok/s and first-token latency (compare against landscape: ~51 tok/s single-stream expected).

**As built, 2026-08-27 — the lead endpoint is vLLM, not SGLang.** `files/issue-226/vllm-serve.sh` runs NVIDIA's DGX Spark vLLM playbook recipe for `nvidia/Qwen3.6-35B-A3B-NVFP4` (weights pre-pulled to `~/hf-hub`, 22 GB, public repo, no token) on `vllm/vllm-openai@sha256:61fc8a896b0a4fbbbdc063bc4b0dbc25ce98e02b5050c24aeb7830ac02039b14` (vLLM 0.28.0), published on `127.0.0.1:8000` and `192.168.1.203:8000`. One recipe value had to change: the playbook's `--gpu-memory-utilization 0.4` crash-looped six times with `Available KV cache memory: -1.75 GiB` → `No available memory for the cache blocks`, because this vLLM enables CUDA-graph memory profiling by default (the log says so in as many words); **0.6** gives `Available KV cache memory: 23.22 GiB`, a 1,960,381-token KV cache and 7.48× concurrency at the 262,144 max context. Everything else is the recipe verbatim (fp8 KV, FlashInfer, Marlin MoE, MTP speculative decode ×3, `fastsafetensors`, qwen3 reasoning + `qwen3_xml` tool parsers).

- `curl http://127.0.0.1:8000/v1/models` → `nvidia/Qwen3.6-35B-A3B-NVFP4`; same on `http://192.168.1.203:8000`.
- First inference: the playbook's `12*17` test → `12 × 17 = **204**` (15 prompt / 367 completion tokens, 352 of them reasoning).
- Measured (streaming, thinking off, 600-token answers, three prompts): **first token 0.09–0.11 s, decode 80–87 tok/s single-stream** — above the ~51 tok/s the landscape expected from the community SGLang recipe. Resident footprint: `free -g` 64 GB used / 57 GB available with the model loaded and idle; GPU 52 °C, 34 W during generation.
- Start-up from cached weights to `Application startup complete`: ~4 min (weights 18 s; the rest is graph capture and MTP draft setup).

### 2.5 The embed / rerank / STT tier (as built, 2026-08-28 — co-hosted with the lead)

The RAG + captioning parity set, standing up alongside the live lead (`§5.5` budget in `nvidia-dgx-spark-landscape.md` — the four co-host inside ~93 GB used / ~28 GB free). Each is one idempotent serve script under `files/issue-226/`, same hardening as `vllm-serve.sh` (digest-pin, `127.0.0.1` + LAN bind, `--restart unless-stopped`).

- **Embeddings — `BAAI/bge-m3` on `:8001`** (`tei-embed-serve.sh`, container `tei-embed-bge`). TEI `ghcr.io/huggingface/text-embeddings-inference:121-latest` (sm_121 prebuilt — the same image `tei-kb` proved native on the box). `curl :8001/embed` → **1024-d** vector; ~7 GB delta co-hosted. Separate from the KB's nomic-768-d `tei-kb` (`:8080`).
- **Rerank — `BAAI/bge-reranker-v2-m3` on `:8002`** (`tei-rerank-serve.sh`, container `tei-rerank-bge`). Same TEI image, `/rerank` route. Smoke: the DGX-Spark doc scored **0.9997** vs **0.00002** for an unrelated doc; ~5 GB delta. Lead `:8000` confirmed healthy alongside both.
- **STT — whisper.cpp `large-v3` (CUDA) on `:8003`** (`whisper-serve.sh` + `files/issue-226/whisper/`, container `whisper-cpp`). Not turnkey: a source build with `CMAKE_CUDA_ARCHITECTURES="120;121"` on `nvidia/cuda:13.0.1-devel-ubuntu24.04` (faster-whisper/CTranslate2 has no sm_121 build). Exposes `/inference` and OpenAI `/v1/audio/transcriptions` (prod-Whisper-`:8001` parity). GPU confirmed (`NVIDIA GB10, compute capability 12.1, use gpu = 1`); box-measured **RTF ~0.04 (≈20–25× realtime)** — 11 s of audio in 0.43–0.57 s. Runtime image needs `curl`/`wget` for the first-boot model download (added to the Dockerfile); here the model was pre-staged on the host at `~/whisper-models/ggml-large-v3.bin`.

## 3. Stand up the capacity endpoint (stretch — NVIDIA vLLM)

**Locked stretch model (2026-08-28): `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`** via `files/issue-226/vllm-stretch-serve.sh {up|down|status}` — a **swap-in on `:8000`**, not a co-resident (landscape §5.5: it holds most of the pool). **The swap is reversible by construction:** `up` runs `docker stop` (never `rm`) on the whole co-hosted serving set — lead `vllm-qwen36`, `tei-embed-bge`, `tei-rerank-bge`, `whisper-cpp` — leaving their containers and weights on disk, then serves Nemotron in its own container `vllm-nemotron120`. `down` removes only the Nemotron container and `docker start`s the four back, waiting on the lead's `/health`. So the old models always come back with one command. NVIDIA's flagship NVFP4 MoE, ~12 B active, `vllm/vllm-openai:cu130-nightly` (pinned releases hit MoE/NVFP4 kernel errors — research §2), `--max-model-len 131072 --max-num-seqs 4`, `--gpu-memory-utilization` tuned to the freed pool. **As built, 2026-08-28 (`spark-dd06`):** weights pre-staged to `~/hf-hub` (75 GB on disk, via a `--dns 8.8.8.8` `snapshot_download` — the box's WiFi resolver drops `huggingface.co` intermittently, so a plain container pull fails `Temporary failure in name resolution`; public DNS + a retry loop fixes it). Swapped in at `--gpu-memory-utilization 0.72` → **14.79 GiB KV cache (2.35 M tokens, 17.9× concurrency)**, ~7 min load from cache. Measured: **15.5 tok/s single-stream, 41.5 tok/s at 4-way concurrency, TTFT ~0.42 s** — below the [vLLM DGX Spark benchmark](https://vllm.ai/blog/2026-06-01-vllm-dgx-spark)'s clean-box 22.7–23.7 tok/s because this ran on the shared box (k3s + KB resident) on vLLM 0.28 with no spec-decode; `cu130-nightly` + MTP is the path to close it. `down` restored the lead + three sidecars cleanly. **Sustained-load thermals (4-min, 16-client saturation, 96% GPU util, SM 2522 MHz):** idle 51 °C / 13 W → steady ~65 °C / 41 W → peak **69 °C / 43 W** (GPU rail) on the internal sensor; an IR scan of the chassis read **~114–115 °F (~46 °C)** case surface at peak — no throttling, the box runs the 120 B flat-out inside its envelope. `DeepSeek-V4-Flash` (below) stays the documented alternative / dual-Spark 1M-context path.

Alternative — the DeepSeek-V4-Flash single-Spark recipe shape:

```bash
git clone https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-One-DGX-Spark
cd DeepSeek-v4-Flash-One-DGX-Spark
# reads config; ~107 GB weights download into ./hf-hub on first boot
docker compose up            # NVIDIA vLLM + sparkinfer; OpenAI API on :8888
```

- [ ] Expect a **long first boot**: image pull + ~107 GB weight download + TP4→TP1 coalesce + draft-model build + CUDA-graph capture. Do not kill it.
- [ ] Confirm it serves at 384K ctx (~44–47 tok/s decode expected).

## 4. Security hardening (do NOT skip — from the recipe gotchas)

The community recipes optimize for speed, not safety. Every one of these bit us in the source docs:

- [ ] **Bind to localhost / trusted LAN only.** Recipes bind `0.0.0.0` on `:8888` with **no authentication**. Restrict to `127.0.0.1`, or front with a reverse proxy + auth, or firewall `:8888` to the trusted LAN before exposing to other devices.
- [ ] **Disable EarlyOOM.** The server intentionally holds ~94% of unified memory; an OOM-killer will reap it mid-serve.
- [ ] **Leave load-bearing tunables alone.** `MAX_NUM_BATCHED_TOKENS` (default 8224 in the DeepSeek recipe) gates prefill budget and the locked MLA workspace — lowering it causes mid-serve assertion failures. Tune `MAX_NUM_SEQS` for concurrency vs. depth instead.
- [ ] **Ensure ≥114 GiB free host memory at launch** for the capacity model; keep the stunt tier off the box unless deliberately demoing it.

## 5. Expose on the LAN for NiFi / edge flows

The point of the box is that flows on other devices hit it as an inference target (work-stream C).

- [x] Published on the LAN address + loopback (2026-08-27/28; ufw LAN rule, Docker bind to the LAN address only). The serving surface on `192.168.1.203`: **`:8000`** vLLM chat (`/v1`), **`:8001`** bge-m3 embeddings (`/embed`), **`:8002`** bge-reranker rerank (`/rerank`), **`:8003`** whisper.cpp STT (`/inference`, `/v1/audio/transcriptions`). (This supersedes the draft's single `:8888`.)
- [ ] From another device, confirm reachability: `curl http://<spark-lan-ip>:8000/v1/models`.
- [ ] Record the endpoint URL in `CLAUDE-CHECKIN.md` so NiFi `InvokeHTTP` / RAG flows can target it.
- [ ] For the Cloudera-alignment path, note whether to also stand up the model as a **NIM microservice** (matches Cloudera AI Inference API) vs. the SGLang/vLLM OpenAI endpoint — decided in work-stream C.

## Verification (definition of done)

- `nvidia-smi`, `nvcc`, `free -g`, `df -h` baseline recorded in the box's `CLAUDE-CHECKIN.md` block.
- At least the interactive endpoint answers `/v1/chat/completions` locally and from one other LAN device.
- §4 hardening applied and confirmed (not bound to `0.0.0.0` unrestricted).
- Actual throughput numbers recorded and compared against `nvidia-dgx-spark-landscape.md`.

## When this ships

- Add the box to `CLAUDE-CHECKIN.md` (device block, paths, the `:8888` endpoint, port-forward/firewall notes).
- The confirmed endpoint URL unblocks work-stream **C** (Cloudera demos) and the deferred on-box `device:<box>` execution issue (D).
- Fill the *expected* command blocks above with the *actual* commands/values used, so this becomes a true as-built runbook.

## Resources

- [DeepSeek-V4-Flash single-Spark recipe](https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-One-DGX-Spark) · [Qwen3-27B SGLang recipe](https://github.com/MiaAI-Lab/Qwen3.8-27B-SGLang-DGX-Spark)
- [Red Hat — RHEL on DGX Spark](https://www.redhat.com/en/blog/supercharging-local-ai-development-rhel-nvidia-dgx-spark)
- `nvidia-dgx-spark-landscape.md` (model sizing) · `nvidia-dgx-spark-cloudera-demos.md` (what the endpoint feeds)
