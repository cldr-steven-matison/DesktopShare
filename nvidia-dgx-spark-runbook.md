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
- Tools: `kubectl v1.32.13`, `helm v3.21.4` (user-local, `~/.local/bin`); k3s `v1.32.13+k3s1`; OpenJDK `21.0.12`; Tailscale joined as `100.68.14.110` / `nvidiaspark-1` — **on the `tunastreet@outlook.com` tailnet, not the array's `steven.matison@gmail.com` one**; re-login pending before any tailnet path is relied on.
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

## 3. Stand up the capacity endpoint (stretch — NVIDIA vLLM)

Only after the interactive tier works. Using the DeepSeek-V4-Flash single-Spark recipe shape:

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

- [x] Published at `http://192.168.1.203:8000/v1` (2026-08-27; ufw LAN rule, Docker bind to the LAN address only).
- [ ] From another device, confirm reachability: `curl http://<spark-lan-ip>:8888/v1/models`.
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
