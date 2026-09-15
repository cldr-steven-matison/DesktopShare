**Addendum 2026-09-15 — the restore order held; the gate for its last step is now written down.**

The host rebooted in the wrong order this afternoon and the §2 crash came straight back on `cso-prod-1`: `vllm-server` in `CrashLoopBackOff` (26 restarts) on `Available KV cache memory: 0.9 GiB` against the `1.1 GiB` needed at 32000 ctx, plus two dead pods (`ContainerStatusUnknown`, `UnexpectedAdmissionError`). Nothing had changed — committed manifest, the staged `v0.25.0` pin, and the live pod all agree on `Qwen2.5-3B-Instruct` / `--gpu-memory-utilization 0.75` / `--max-model-len 32000`, and the whisper deployment is untouched since 08-12.

The documented order alone restored it: whisper→0, vLLM restarted on the cleared card (the old pod has to be deleted by hand — the `nvidia.com/gpu: 1` limit deadlocks a rolling update), `/v1/models` 200, whisper→1. End state **7384 MiB with both resident** against the 7388 recorded here on 09-08; vLLM KV cache 3.66 GiB; app `/api/health` reports `vllm`/`whisper`/`nifi`/`kafka`/`efm` ok (`qdrant`/`embedding` off by design, §1); a chat completion in 2.4 s and a `/transcribe` upload in 5.4 s, back to back.

The trap worth recording: after vLLM comes up alone, `nvidia-smi` reads ~300 MiB free, and this session stopped at that reading and nearly lowered `--gpu-memory-utilization` to "make room" — backwards. WSL2's GPU is WDDM: the video-memory manager evicts a *running* process's idle allocator blocks to host RAM rather than failing the new allocation, so whisper-large-v3 loads on a "full" card (used went 7637 → 7384 MiB as it came up) and only vLLM's startup profiling refuses to over-commit. That is the whole reason the order is vLLM first, then whisper, and the only gate for whisper→1 is `/v1/models` 200.

Committed as [`b003f71`](https://github.com/cldr-steven-matison/DesktopShare/commit/b003f71):

- [`files/issue-312/perf-review.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-312/perf-review.md) — §2 gets the gate + mechanism paragraph; the §5 reversal row now says "gate the last step on `/v1/models`, not on `nvidia-smi` free".
- [`CLAUDE-CHECKIN.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md) — the WindowsDesktop #312 bullet carries the same clause with the pointer to §2.

Left as recorded here, not acted on: the fragility recurs on every wrong-order boot, and §6's "next lever" (a pre-quantized AWQ/GPTQ 3B checkpoint to shrink vLLM's footprint) is still the durable fix and still belongs in its own issue. Also noted: the `v0.25.0` pin and the `VLLM_USE_V1`/`VLLM_WSL2_ENABLE_PIN_MEMORY` envs from 08-27 are staged but never committed in `~/ClouderaStreamingOperators/vllm-Qwen2.5-3B-Instruct.yaml` — the live fix exists only in that working tree.

Issue stays closed at `status:done`; this comment is the record.
