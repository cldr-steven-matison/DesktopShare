# NVIDIA DGX Spark — Cloudera Integration Demo Plan

> **Status (2026-08-26):** the box landed as `spark-dd06`. This is still the four-demo first-package draft; the re-map onto F/G/H/I and Demos 5–10 are owed under [#234](https://github.com/cldr-steven-matison/DesktopShare/issues/234). Two facts moved: the live RAG LLM on WindowsDesktop today is `Qwen/Qwen2.5-3B-Instruct` at `:8000` (the manifest default in `cso-operator-app-plan.md` is 1.5B), and the endpoint convention on the box is `:8000`. "The Spark" in this draft means the DGX Spark.
>
> **Status (2026-08-24):** Work-stream **C** of the DGX Spark readiness EPIC ([#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226)). Demo designs only — authored on the Mac, built on-box in the deferred execution phase. **Reuse-first: every demo maps to a pattern we already run**, with the Spark swapped in as a bigger, faster local inference target. The through-line is the SE arc from `nvidia-dgx-spark-landscape.md` §5: *develop against the model on the desk, repoint the base URL at Cloudera AI Inference to scale it — same OpenAI/NIM API.*

## 1. Why these demos exist

`nvidia-request.md` justifies the box as a way to build **local AI + CDP Base / CDP Operators** demos that scale to full Cloudera AI. The landscape doc confirmed the technical bridge is real: the Spark's local endpoint and **Cloudera AI Inference** (NIM, on-prem since Cloudera Data Services 1.5.5) speak the **same API**. So each demo below is designed to run first against `http://<spark>:8888/v1` and then, unchanged except for a base URL, against Cloudera AI Inference. That "same code, two backends" moment is the demo payload.

## 2. Reusable building blocks (do not reinvent)

| Building block | Where it lives today | Role on the Spark |
|---|---|---|
| RAG service stack — vLLM + Qdrant + TEI embeddings + Whisper | `cso-operator-app-plan.md` (vLLM `Qwen2.5-1.5B` @ `vllm-service.default:8000`, Qdrant `my-rag-collection` 768-d @ `qdrant.default:6333`, TEI `nomic-embed-text-v1` @ `embedding-server-service.default:80`, Whisper-large-v3 @ `whisper-service.default:8001`) | Repoint the RAG app's LLM base URL at the Spark's ~27 B model — same app, 10× the model |
| NiFi RAG flow shapes | `completed/how-to-nifi-and-ai.md` — `IngestDataToStream`, `StreamToWhisper`, `StreamTovLLM` | Spark becomes the `InvokeHTTP` inference target for `StreamTovLLM` |
| "Resident daemon behind a thin HTTP front door" | `efm-nvidia-nano-inference.md` (Jetson TensorRT daemon at `127.0.0.1:5910`) | Same architecture, one tier up — the Spark *is* the resident daemon for the LAN |
| VRAM/model sizing method | `research/gpu-optimization-plan.md` (RTX 4060 8 GB analysis) | Same method, applied to 128 GB unified — see landscape §2 |

The Jetson→Spark relationship is the hardware ladder from `efm-nvidia-nano-research.md`: Orin Nano (edge) → DGX Spark (desk) → Cloudera AI Inference (cluster). The demos walk that ladder.

## 3. Demo designs

### Demo 1 — RAG app, big-model swap (CDP-adjacent, lowest lift)
Take the existing Streamers/RAG app (`cso-operator-app-plan.md`) and change one thing: the LLM base URL from the in-cluster 1.5 B vLLM to the Spark's ~27 B endpoint. Qdrant, TEI embeddings, and Whisper stay exactly as they are.
- **Shows:** the same app, visibly better answers, running on a desktop.
- **Reuses:** the entire cso-operator-app stack; only the base URL changes.
- **Bridge:** repoint that same base URL at Cloudera AI Inference → identical app, cluster-scale.

### Demo 2 — NiFi flow → Spark inference (CDP Operators)
Wire an existing NiFi flow so `StreamTovLLM` (from `completed/how-to-nifi-and-ai.md`) targets `http://<spark>:8888/v1/chat/completions` via `InvokeHTTP`. Data ingested through CDF/NiFi on the k8s stack, inference on the Spark, results landed back (Kafka/Iceberg).
- **Shows:** CDP Operators (NiFi on k8s) orchestrating; the Spark doing the heavy inference locally and privately.
- **Reuses:** the `IngestDataToStream` → `StreamTovLLM` flow shape; the Bearer-token / `InvokeHTTP` convention from the `nifi-and-ai` skill.
- **Bridge:** swap the `InvokeHTTP` URL to Cloudera AI Inference — same flow, no processor rewiring.

### Demo 3 — Voice/agentic pipeline (edge → desk → cluster ladder)
Audio in (MiNiFi/edge, e.g. the Jetson from `efm-nvidia-nano-inference.md`) → Whisper transcription → the Spark's ~27 B model for reasoning/RAG → response. This exercises the full hardware ladder in one story.
- **Shows:** edge capture, desk-class local inference, private end-to-end — no cloud round-trip.
- **Reuses:** the `StreamToWhisper` flow, the Jetson daemon-behind-HTTP pattern, the RAG stack.
- **Bridge:** the desk tier scales to Cloudera AI Inference; the edge tier stays MiNiFi.

### Demo 4 — "Same code, two backends" (the SE money shot)
A minimal agent/RAG client pointed at a `BASE_URL` env var. Run it once against the Spark (`http://<spark>:8888/v1`), once against Cloudera AI Inference (NIM). Identical output; only the URL changed.
- **Shows:** the develop-local → scale-to-Cloudera-AI arc explicitly, in 30 seconds.
- **Reuses:** any of the above clients; NVIDIA NIM as the common API contract.
- **Decision it forces (see runbook §5):** stand the Spark model up **as NIM** (exact Cloudera AI Inference API parity) vs. the SGLang/vLLM OpenAI endpoint (faster to run, ~equivalent API). Recommend NIM for this demo specifically.

## 4. Sequencing

Demo 1 first (lowest lift, proves the endpoint). Demo 2 next (CDP Operators story). Demo 4 as the closer for customer conversations. Demo 3 is the showcase set-piece once the others work. All gated on the runbook (B) producing a hardened, LAN-reachable endpoint.

## Verification (definition of done)

- Each demo names the exact existing pattern it reuses (satisfied above) — nothing reinvented.
- At least Demo 1 and Demo 2 have a concrete "change one URL" delta from an already-working artifact.
- The NIM-vs-OpenAI-endpoint decision (Demo 4) is recorded before on-box execution.

## When this ships

- On-box execution (deferred `device:<box>` issue, work-stream D) picks up these designs and builds Demo 1 first.
- Any demo that becomes customer-facing gets a clean blog per `agent/writing-style.md` (no issue numbers, no internal justification).
- Confirmed demo endpoints/flows get recorded back into `cso-operator-app-plan.md` and the `nifi-and-ai` skill if they change the canonical flow shapes.

## Resources

- `nvidia-dgx-spark-landscape.md` (§5 the bridge) · `nvidia-dgx-spark-runbook.md` (§5 the endpoint)
- `cso-operator-app-plan.md` · `completed/how-to-nifi-and-ai.md` · `efm-nvidia-nano-inference.md` · `efm-nvidia-nano-research.md`
- [Cloudera + NVIDIA (Cloudera AI Inference, NIM, RAPIDS)](https://www.cloudera.com/partners/solutions/nvidia.html)
