# NVIDIA DGX Spark — Day-1 Setup Runbook

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

- [ ] Publish the endpoint at `http://<spark-lan-ip>:8888/v1` (behind the §4 firewall rule).
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
