# Validating the NvidiaSpark-1 doors from another device

The EFM class flow on spark-dd06 fronts four inference doors on one listener, port `8190`.

> **Which address.** The recipes below use the LAN address `192.168.1.203`. That works from a device
> on the 192.168.1.x LAN; it does **not** work from WindowsDesktop, where every port on that address
> times out (proven 2026-09-10, #324). From there, and from anything else off the LAN, substitute the
> Tailscale address `100.104.155.57` — same ports, same bodies. Set `SPARK` once and the recipes are
> unchanged.
 Each door forwards to the serving tier on the same box and returns the upstream body unchanged, so the response shapes below are vLLM's, TEI's and whisper.cpp's. The point of this file is the "from a device that is not the DGX Spark" proof that work-stream G still owes (`nvidia-dgx-spark-efm-agent.md` §3, definition of done). Run any recipe from WindowsDesktop, StarlinkAI or the Jetson and paste the output on #239.

| Door | Forwards to | Body |
|---|---|---|
| `POST /reason` | `:8000/v1/chat/completions` (vLLM, `nvidia/Qwen3.6-35B-A3B-NVFP4`) | OpenAI chat-completions JSON |
| `POST /embed` | `:8001/embed` (TEI, `BAAI/bge-m3`, 1024-d) | `{"inputs": "..."}` |
| `POST /rerank` | `:8002/rerank` (TEI, `BAAI/bge-reranker-v2-m3`) | `{"query": "...", "texts": [...]}` |
| `POST /transcribe` | `:8003/inference` (whisper.cpp `large-v3`) | multipart `file=@…` |
| `GET :9936/metrics` | the flow's own exporter | Prometheus text |

Two things that look like flow faults and are not. `/reason` with a `model` id vLLM does not serve returns 404 from vLLM. `/reason` with a small `max_tokens` (256) returns `"content": null` because the model spends the budget on reasoning (a one-line answer above cost 795 reasoning tokens); use 2048.

## Use case 3 — NiFi on WindowsDesktop → DGX Spark inference (the cheapest proof)

From a WindowsDesktop shell (PowerShell uses `curl.exe`), the same call `StreamTovLLM` makes, pointed at the box:

```bash
SPARK=http://192.168.1.203:8190
curl -s -X POST $SPARK/reason -H 'Content-Type: application/json' -d '{
  "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
  "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
  "max_tokens": 2048
}' | jq '{model, content: .choices[0].message.content, usage}'
```

Expected: `"model": "nvidia/Qwen3.6-35B-A3B-NVFP4"`, a one-word `content`, and a `usage` block. First-token latency from the LAN is under a second.

**Run 2026-09-10 from WindowsDesktop** (`SPARK=http://100.104.155.57:8190`), which closes work-stream
G's "§3 use case from a non-Spark device" item:

```json
{
  "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
  "content": "\n\nready",
  "usage": { "prompt_tokens": 17, "total_tokens": 196, "completion_tokens": 179,
             "completion_tokens_details": { "reasoning_tokens": 175 } }
}
```

The 175 reasoning tokens for a one-word answer are the `max_tokens: 2048` note above in action — at
256 the budget goes to reasoning and `content` comes back null.

The flow-level version is the `FlowParams` repoint described in §3 row 3: set `vLLM Base URL` to `http://192.168.1.203:8190` and leave every processor alone. Do that only after the OpenClaw bridge has been repointed and checked, and keep the old value one parameter away (row 3 is a cutover, not an experiment).

## Use case 1 — Jetson → DGX Spark escalation

The Jetson's `/classify` answers from MobileNetV2. A low-confidence result gets re-posted to the box for a second opinion. The lead model is a text model, so the escalation carries the classifier's verdict as text, not the image:

```bash
SPARK=http://192.168.1.203:8190
curl -s -X POST $SPARK/reason -H 'Content-Type: application/json' -d '{
  "model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
  "messages": [{"role": "user", "content": "A Jetson image classifier reports label=cat confidence=0.41. Answer ESCALATE or ACCEPT and one reason."}],
  "max_tokens": 2048
}' | jq -r '.choices[0].message.content'
```

In the `NvidiaNanoJava` class flow the same call is one `InvokeHTTP` after a `RouteOnAttribute` on `confidence < 0.6` (`EdgeFlowManager/files/efm/NvidiaNanoJava.json` is the export to add it to).

## Use case 2 — MicroFi-2 camera → embed / rerank

`MicroFi2CameraBridge` already lands the OV2640 frames on Kafka. The inference hop for its metadata is the embed door; the rerank door scores candidate captions:

```bash
SPARK=http://192.168.1.203:8190
curl -s -X POST $SPARK/embed -H 'Content-Type: application/json' \
  -d '{"inputs": "microfi2 camera frame, kitchen, daylight"}' | jq '.[0] | length'      # 1024

curl -s -X POST $SPARK/rerank -H 'Content-Type: application/json' -d '{
  "query": "is anyone in the kitchen?",
  "texts": ["A person stands at the kitchen counter.", "An empty kitchen at night."]
}' | jq -c 'sort_by(-.score) | .[] | {index, score}'
```

Expected: `1024` from `/embed`; from `/rerank`, index `0` scores near 1 and index `1` near 0.

## `/transcribe` and the metrics leg

```bash
SPARK=http://192.168.1.203:8190
curl -s -X POST $SPARK/transcribe -F file=@sample.wav -F response_format=json | jq .text
curl -s http://192.168.1.203:9936/metrics | head
```

Any 16 kHz WAV works for `/transcribe`; the `:9936` leg answers with `minifi_java_host_load1` and `minifi_java_host_mem_total_kb` lines.
