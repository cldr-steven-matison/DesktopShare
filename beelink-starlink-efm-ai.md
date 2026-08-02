# Beelink SER9 MAX (H260): Windows-Native AI Router

## Overview

Third node in the array (alongside WindowsDesktop and Mac), hostname `TunaStarlink`. Hardware: AMD Ryzen 7 260 (8C/16T, 3.8GHz base), Radeon 780M iGPU (RDNA3, 12 CUs), no NPU, 64GB RAM. On Starlink; Windows host also runs an OBS/OBSBOT Tiny 3 Twitch stream.

This node's job: use the iGPU (Vulkan) for local inference and expose it to the rest of the array as an HTTP endpoint over Tailscale, fronted by an EFM/MiNiFi **Java** agent that does routing only.

## Architecture

```
Other array machines (Tailscale)
        │
        ▼
Tailscale (Windows host) — stable tailnet IP for this box
        │
        ▼
EFM / MiNiFi Java agent (StarlinkAIJava class, Windows native process)
  - HandleHttpRequest  : single entry point, port 8090, all 5 Lemonade
                          endpoints on one port, distinguished by path
  - InvokeHTTP          : pure reverse-proxy pass-through —
                          HTTP URL = http://localhost:13305${http.request.uri}
  - HandleHttpResponse  : returns Lemonade's real answer synchronously
        │
        ▼
Lemonade Server (Windows native, localhost:13305)
  - iGPU inference via llamacpp:vulkan backend
  - OpenAI-compatible API: /v1/chat/completions, /v1/embeddings,
    /v1/reranking, /v1/audio/speech, /v1/audio/transcriptions
```

3 processors, one port, no Kafka, no `request_id` correlation. The caller gets the real Lemonade response directly and synchronously.

Everything runs natively on Windows — no containers, no WSL2 in the serving path. WSL2 (this session's environment) is only used for repo/doc access.

Why Vulkan, not ROCm/vLLM: this chip has no NPU, and AMD's ROCm does not support this iGPU either. `llamacpp:vulkan` uses the standard GPU driver stack directly, no special driver package needed.

Why Java, not C++: MiNiFi C++'s `ListenHTTP` has no synchronous request/response pair — the caller always gets an empty ack, and a real answer needs an out-of-band channel (Kafka, in the earlier design). It also silently drops multipart POSTs (transcription) at its buffer-full check. MiNiFi Java ships `HandleHttpRequest`/`HandleHttpResponse`, which returns a real response inline — no Kafka, no drop.

## The live flow (EFM UI)

![HandleHttpRequest-Lemonade → InvokeHTTP-Lemonade → HandleHttpResponse-Lemonade, live per-processor throughput in the EFM Flow Designer](/images/efm-starlink-ai-unified-lemonade-flow.png)

The deployed router flow in the **EFM Flow Designer**, monitoring active — real per-processor throughput (In / Read-Write / Out / Tasks). 3 processors, 2 connections on the primary path (plus an error-observability branch off `InvokeHTTP`'s `Failure`/`Retry`/`No Retry`/`Original` relationships, not shown here — see "Known gap" below).

## Setup

### 1. Tailscale (Windows host)
```powershell
winget install tailscale.tailscale
tailscale up
```
`tailscale up` opens an interactive browser auth — run by hand, join the same tailnet as the other array machines.

**Tailscale IP: `beelink-ip`. EFM host (WindowsDesktop, hostname `MINI-Gaming-G1`) Tailscale IP: `efm-host-ip`** — the `baseUrl` target for the agent deployer script below.

### 2. Lemonade Server (Windows host)
```powershell
winget install --id AMD.LemonadeServer --silent --accept-package-agreements --accept-source-agreements
lemonade backends install llamacpp:vulkan
```
- `lemonade list` / `lemonade pull <model>` to manage models.
- 5 models loaded, 1 concurrent per category: chat (`Qwen3-4B-GGUF`), embeddings (`Qwen3-Embedding-0.6B-GGUF`), reranking (`jina-reranker-v1-tiny-en-GGUF`), transcription (`Whisper-Large-v3-Turbo`), TTS (`kokoro-v1`, `device: cpu` — that backend was only installed as `kokoro:cpu`).
- Confirm Vulkan GPU offload is active (`GET /api/v1/health` → `device: gpu`) once a model is loaded, not silently falling back to CPU.

### 3. EFM / MiNiFi Java agent (Windows host, router only)

```powershell
winget install Microsoft.OpenJDK.21
```

Deploy via the agent-deployer script from the EFM server, targeting the **Java** agent type and a dedicated class (`StarlinkAIJava` — kept separate from any earlier C++ class so the two never share a canvas):
```powershell
$env:JAVA_HOME = 'C:\Program Files\Microsoft\jdk-21.0.12.8-hotspot'
$env:Path = "$env:JAVA_HOME\bin;" + $env:Path
Invoke-WebRequest -Uri 'http://<EFM_HOST>:10090/efm/api/agent-deployer/script' -Method Post -Body @{
  agentClass  = 'StarlinkAIJava'
  agentType   = 'java'
  agentVersion = '2.24.08.0-19'
  osArch      = 'windows'
  baseUrl     = 'http://<EFM_HOST>:10090/efm/api'
  hbPeriod    = '5000'
} -OutFile deploy.ps1
.\deploy.ps1
```
Lands at `~\minifi-java\minifi-2.24.08.0-19\`, runs as a plain background process via `bin\run-minifi.bat` (no service install needed on this box). The class picks up the Java manifest automatically on first heartbeat — no manual class-manifest re-pointing needed for a fresh class.

## Flow build

Built via the EFM Designer's per-component API (`POST .../processors`, `POST .../connections`, `GET .../validate`, `POST .../publish` — there is no whole-flow `PUT`). Key processor settings:

**`HandleHttpRequest-Lemonade`**
| Property | Value |
|---|---|
| Listening Port | `8090` |
| HTTP Context Map | `StandardHttpContextMap` (shared controller service) |
| Allowed Paths | unset — accepts any path, distinguished downstream by `${http.request.uri}` |

**`InvokeHTTP-Lemonade`**
| Property | Value |
|---|---|
| HTTP URL | `http://localhost:13305${http.request.uri}` — pure pass-through, no per-endpoint branching |
| HTTP Method | `POST` |
| Request Content-Type | `${mime.type}` — forwards the client's real content type, so both JSON and multipart bodies pass through unchanged |
| Request Body Enabled | `true` |
| **Socket Read Timeout / Socket Write Timeout** | **`10 mins`** |
| Connection Timeout | `30 secs` |

The 10-minute read/write timeout is load-bearing, not cosmetic: it's the difference between this flow working and every request silently dying. LLM inference routinely takes 10-25s+; the framework default (`15 secs`) fails every real call with a `SocketTimeoutException`, invisible to the caller because it auto-terminates on `Failure` with nothing routed back — the client just sits until `StandardHttpContextMap`'s own 60s expiration gives up with a generic 503. Match this to whatever the slowest endpoint on the box needs, not the framework default.

**`HandleHttpResponse-Lemonade`**
| Property | Value |
|---|---|
| HTTP Status Code | `200` |
| HTTP Context Map | same shared `StandardHttpContextMap` |

Wired: `HandleHttpRequest[success] → InvokeHTTP[success] → HandleHttpResponse[Response]`.

**Fixed 2026-08-02 (flowVersion 23):** `InvokeHTTP`'s `Retry`, `No Retry`, and `Failure` relationships now *also* connect to `HandleHttpResponse-Lemonade` (fan-out alongside the existing `LogAttribute-Error` connections, which stay for visibility). `HandleHttpResponse-Lemonade`'s `HTTP Status Code` property changed from the hardcoded literal `"200"` to `${invokehttp.status.code:replaceEmpty('502')}` — it now reflects the real upstream status on every outcome (2xx via `Response`, the real 4xx/5xx via `Retry`/`No Retry`, or `502` via `Failure` when no response came back at all — that relationship carries no `invokehttp.status.code` attribute). `Original` (the pass-through duplicate of the incoming request, which always fires alongside whichever real outcome relationship also fires) deliberately stays unconnected to `HandleHttpResponse` — wiring it in too would deliver a second FlowFile to the same HTTP context and double-respond.

Verified live: a GET-turned-POST health probe through the router (`curl http://localhost:8090/api/v1/health`) now returns a real `404` in well under a second, instead of hanging for the 60s `StandardHttpContextMap` expiration.

## Endpoints

All 5 Lemonade services, one port, one flow — the path the client POSTs to is forwarded verbatim to Lemonade:

| Service | Path | Confirmed |
|---|---|---|
| Chat | `/api/v1/chat/completions` | **Yes** — real client, real content, real synchronous answer returned (`200`, ~12-37s depending on response length) |
| Embeddings | `/api/v1/embeddings` | **Yes** — real 200, real embedding vector (`Qwen3-Embedding-0.6B-GGUF`), ~0.2s |
| Reranking | `/api/v1/reranking` | **Yes** — real 200, real relevance scores (`jina-reranker-v1-tiny-en-GGUF`), correctly ranked the on-topic document highest, ~2.5s |
| Speech (TTS) | `/api/v1/audio/speech` | **Yes** — real 200, real Kokoro MP3 (valid ID3/MPEG, 78KB), ~7s |
| Transcription | `/api/v1/audio/transcriptions` | **No — new bug found, see below.** Intake at `HandleHttpRequest` is clean (no drops), but the full round trip through `InvokeHTTP` fails with a real `400` every time |

**New bug found 2026-08-02 — multipart fragments never get reassembled before forwarding.** `HandleHttpRequest` splits a multipart request into one FlowFile per form field (confirmed via `minifi-app.log`: `http.multipart.fragments.total.number: 2`, one fragment for `model`, one for `file`). Each fragment is then forwarded to `InvokeHTTP-Lemonade` **independently**, as its own request, with `Content-Type` still set to the *original* multipart header (`multipart/form-data; boundary=...`) but a body that's only that one fragment's raw bytes — never valid multipart. Lemonade correctly rejects it: `invokehttp.response.body: {"error":{"message":"Bad request","type":"bad_request"}}`. Confirmed the request itself is well-formed by sending the identical multipart POST straight to Lemonade on `:13305` — real `200`, real transcript text back. The pure `HandleHttpRequest → InvokeHTTP → HandleHttpResponse` pass-through design (no reassembly step) works for single-part bodies (JSON, raw binary) but cannot proxy a true multi-field multipart request as-is; fixing it needs the fragments recombined (e.g. a `MergeContent` keyed on `http.multipart.fragments.*`) before `InvokeHTTP`. Filed as a new issue rather than folded into this fix, since it's a materially different problem from the error-routing gap above.

Test command:
```powershell
curl.exe -X POST http://localhost:8090/api/v1/chat/completions `
  -H 'Content-Type: application/json' `
  --data '@chat_body.json'
```
Use `--data @file.json` for the body, not an inline `-d '{...}'` string — PowerShell/`curl.exe` argument handling has silently stripped quotes out of inline JSON in past testing on this box.

## Status

**Done:**
- [x] Tailscale, Lemonade Server (5 models loaded, Vulkan GPU offload confirmed), JDK 21, MiNiFi Java agent all installed and running on `TunaStarlink`
- [x] `StarlinkAIJava` EFM class online, heartbeating
- [x] Unified 3-processor pass-through flow built, validated, published
- [x] Root-caused and fixed the timeout bug (`Socket Read Timeout` 15s default → 10 min)
- [x] Chat confirmed working end-to-end with real content, real synchronous answer
- [x] Transcription's multipart intake confirmed clean under `HandleHttpRequest` (the failure mode that blocked the old `ListenHTTP`-based design is gone)
- [x] Full end-to-end retest of embeddings/reranking/speech with real data — all 3 confirmed working
- [x] Forward `InvokeHTTP`'s non-2xx responses back to the caller instead of leaving them stuck on `LogAttribute-Error` only (flowVersion 23)

**Open:**
- [ ] Fix multipart fragment reassembly so transcription's real round trip works (new bug, see "Endpoints" above)
- [ ] Cross-Tailscale test from a second array machine (only local curl tested so far)
