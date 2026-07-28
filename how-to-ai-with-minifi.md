# How to AI with MiNiFi

**Subplan — Complete Guide Ch17. Status: 🔲 blog not started (source case study is 🟡).**

The edge sibling of "How to AI with NiFi and Python" (Ch16, published). Where that post runs
Python inference inside NiFi on Kubernetes, this one is the **umbrella post for everything you
can do with EFM + AI at the edge** — not a single technique.

**Scope — this post covers the full menu, not one approach.** The AI-at-edge options each have
their own detailed source doc/chapter; this post is the tour that ties them together:

- **Route to a nearby inference server** — the primary case study below: MiNiFi routes requests to a local LLM (Lemonade/vLLM). The agent doesn't hold the model.
- **`ExecuteScript` (Python) transforms** — inline Python in one processor, now proven on C++ (Path D) and on Java via the NAR drop-in. Detail: Ch6 / `efm-executescript.md`.
- **Custom Python processors** — authored processor *types* running Python at the edge. Detail: Ch7 / `minifi-python-processors.md`. **This is one option among several — the post is not about custom Python processors specifically**, and `ExecuteScript` (above) is a separate concept from it, not a synonym.
- **On-device model execution** — e.g. TensorRT / llama.cpp via the flow (`RunLlamaCppInference` in the C++ manifest; the `*-TensorRT.json` flows). Detail: Ch20.

Keep each to a section that summarizes and cross-references its source doc; the deep how-to
lives in the chapter, not duplicated here.

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

*(For the route-to-inference case study specifically — the other options above get their own shorter sections.)*

1. **Symptom** — you want AI at the edge; the edge box is small and can't host the full model.
2. **Diagnosis** — the edge agent doesn't run the model; it routes to a nearby inference server. The value is the flow, the enrollment, and the transport. (Where the agent *can* do compute itself — ExecuteScript, a custom Python processor, or on-device TensorRT/llama.cpp — that's the other sections, not this one.)
3. **Fix** — the ListenHTTP → EvaluateJsonPath → InvokeHTTP → PublishKafka shape, the real Lemonade endpoints, the EFM per-component write contract (not whole-flow PUT), and the five bugs so the reader skips them.

## Must-carry traps

- ListenHTTP Batch/Buffer Size = 1 (MINFICPP-2243 off-by-one on multipart).
- InvokeHTTP HTTP Method persistence, Kafka NodePort vs in-cluster, Strimzi advertisedHost, EvaluateJsonPath path-expression syntax — all five documented in the source doc.
- EFM Flow Designer has no whole-flow PUT; use per-component POST.

## When this ships

Publish to blog repo `_posts/`, flip Ch17 to ✅📝, and once transcription is fixed, close the
Ch18 open item in the master guide.
