# How to AI with MiNiFi

**Subplan — Complete Guide Ch17. Status: 🔲 blog not started (source case study is 🟡).**

The edge sibling of "How to AI with NiFi and Python" (Ch16, published). Where that post runs
Python inference inside NiFi on Kubernetes, this one pushes inference to the edge: a MiNiFi
agent routing requests to a local LLM server.

## Source of truth

`beelink-starlink-efm-ai.md` — the working StarlinkAI router: `ListenHTTP → EvaluateJsonPath
→ InvokeHTTP → PublishKafka` over Tailscale to a Lemonade Server (Vulkan/llama.cpp). Five
bugs found and fixed 2026-07-17; four Lemonade endpoints (embeddings, reranking, speech,
transcription) exposed via the per-component EFM Designer API.

## Blocker before drafting

Transcription endpoint drops 100% of multipart POSTs (buffer-full, confirmed reproducible
2026-07-23). The post shouldn't ship claiming a capability that drops everything — resolve
the transcription drop first (Ch18 open item), then draft.

## Post spine (Symptom → Diagnosis → Fix)

1. **Symptom** — you want AI at the edge but the agent has no ExecuteScript / limited processors.
2. **Diagnosis** — the edge agent doesn't run the model; it routes to a nearby inference server. The value is the flow, the enrollment, and the transport.
3. **Fix** — the ListenHTTP → EvaluateJsonPath → InvokeHTTP → PublishKafka shape, the real Lemonade endpoints, the EFM per-component write contract (not whole-flow PUT), and the five bugs so the reader skips them.

## Must-carry traps

- ListenHTTP Batch/Buffer Size = 1 (MINFICPP-2243 off-by-one on multipart).
- InvokeHTTP HTTP Method persistence, Kafka NodePort vs in-cluster, Strimzi advertisedHost, EvaluateJsonPath path-expression syntax — all five documented in the source doc.
- EFM Flow Designer has no whole-flow PUT; use per-component POST.

## When this ships

Publish to blog repo `_posts/`, flip Ch17 to ✅📝, and once transcription is fixed, close the
Ch18 open item in the master guide.
