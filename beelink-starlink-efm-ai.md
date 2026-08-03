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

## Proposed fix — transcription multipart reassembly (#88)

**Status 2026-08-02: built live on `StarlinkAIJava`, isolated on a new test port, NOT published, incomplete.**
EFM access from StarlinkAI is real and works (WSL2 → Windows-side `curl.exe`/`tailscale.exe` interop
reaches `mini-gaming-g1.tail1f447b.ts.net:10090` directly) — an earlier "no access" conclusion this same
session was wrong, corrected mid-session. What actually blocked completion was the Claude Code harness's
own auto-mode classifier intermittently refusing repeated live-write Bash calls in that session — a tool
permission gate, not a device or network problem. Next session (any device) can pick this up with real
EFM access; no re-diagnosis needed.

**Root cause (confirmed live via `minifi-app.log`, not guessed):** `HandleHttpRequest` splits a multipart
request into one FlowFile per form field and forwards each independently; `InvokeHTTP` sends each
fragment's raw bytes with the *original* multipart `Content-Type` header, which is never valid on its own.
A real probe (`curl.exe -F model=... -F file=...` against the live `:8090` production endpoint, then diffed
against `minifi-app.log`) confirmed the exact attributes `HandleHttpRequest` sets per fragment — this
supersedes the earlier from-the-doc guesses:

| Attribute | model fragment | file fragment |
|---|---|---|
| `http.context.identifier` | `016f4c23-...` | **same value** — this is the correlation key across fragments of one request |
| `http.multipart.fragments.sequence.number` | `1` | `2` (**1-indexed**) |
| `http.multipart.fragments.total.number` | `2` | `2` |
| `http.multipart.name` | `model` | `file` |
| `http.multipart.filename` | *(absent)* | `test-audio.wav` |
| `http.multipart.content.type` | *(absent — dot, not hyphen)* | `audio/wav` |
| `http.headers.multipart.Content-Disposition` | `form-data; name="model"` | `form-data; name="file"; filename="test-audio.wav"` |
| `http.headers.multipart.Content-Type` | *(absent)* | `audio/wav` |

`http.headers.multipart.Content-Disposition`/`.Content-Type` carry the **original raw per-part header
text** — reuse them directly instead of hand-reconstructing the header string from `http.multipart.name`/
`.filename`, which avoids the conditional-filename EL problem entirely.

**Isolated build (done, on a new unconnected branch — the live production `:8090` pair was never touched):**
new `HandleHttpRequest` on port **`:8095`**, own `HTTP Context Map` (shared existing `StandardHttpContextMap`,
id `5e0fc869-b7d6-478b-ab1c-edcea8a36325`), feeding a reassembly chain, built via the EFM Designer API on
flow `09400bac-f259-4f6a-8f87-f757a5031dd3` / PG `20bf8dfd-aae4-4f81-bedd-edb0b9ddcf76`:

| Processor | id | Key config |
|---|---|---|
| `HandleHttpRequest-TranscriptionTest` | `3262f727-3329-4b4d-a3e2-724d9205c185` | Listening Port `8095`, POST only |
| `UpdateAttribute-FragmentKeys` | `fdf3b1d8-f49e-4cb2-8656-207de611e5d4` | `fragment.identifier`=`${http.context.identifier}`, `fragment.count`=`${http.multipart.fragments.total.number}`, `fragment.index`=`${http.multipart.fragments.sequence.number:minus(1)}` (**0-indexed** — `MergeContent`'s Defragment strategy requires `fragment.index` between `0` and `fragment.count-1`, one off from the 1-indexed `sequence.number`) |
| `RouteOnAttribute-HasContentType` | `4c7e7990-e72b-4316-be44-d8b210b53523` | dynamic property `hasType` = `${'http.multipart.content.type':isEmpty():not()}` |
| `ReplaceText-PrependPartHeaderWithType` | `11c74bd7-2140-4de9-9af7-b5fd7c0c374d` | Prepend, Entire text: `--ClaudeStarlinkBoundary7f3a2b91\r\nContent-Disposition: ${'http.headers.multipart.Content-Disposition'}\r\nContent-Type: ${'http.headers.multipart.Content-Type'}\r\n\r\n` |
| `ReplaceText-PrependPartHeaderNoType` | `a1afe1a9-f923-4851-9cbe-d794befd23ac` | same, without the `Content-Type:` line |
| `MergeContent-Multipart` | `65003e4d-4c8b-4db0-b7ee-a3e52f7d43d0` | Merge Strategy `Defragment`, Delimiter Strategy `Text`, Demarcator `\r\n`, Footer `\r\n--ClaudeStarlinkBoundary7f3a2b91--\r\n`, `original` auto-terminated |
| `UpdateAttribute-SetMultipartContentType` | `fbe54062-ae59-4c7d-993b-35d82d77095b` | `Content-Type` = `multipart/form-data; boundary=ClaudeStarlinkBoundary7f3a2b91` |
| `InvokeHTTP-TranscriptionTest` | `74aec6a4-e955-41a2-b62d-87747400a3e8` | same as prod `InvokeHTTP-Lemonade` (10 min timeouts) except `Request Content-Type` = `${Content-Type}`, not `${mime.type}` |
| `HandleHttpResponse-TranscriptionTest` | `56b240bd-0887-403d-b9fd-8e71aae69389` | `HTTP Status Code` = `${invokehttp.status.code:replaceEmpty('502')}` |
| `LogAttribute-TranscriptionTest` | `ba0bac17-2ef1-486b-85c9-16aac651032d` | error/visibility tap |

Note `Delimiter Strategy: Text` lets `MergeContent`'s Demarcator/Footer be literal property values —
`Filename` mode (a file on disk) was the other option but isn't needed here.

**Connections done (13 of 19):** `req[success]→frag[success]→route`; `route[hasType]→rt_with`,
`[unmatched]→rt_without`; both `[success]→merge`, `[failure]→log`; `merge[merged]→set_ct[success]→invoke`;
`invoke[Response]→resp`, `invoke[Retry]→resp`.

**Connections still needed (6):** `invoke[No Retry]→resp`, `invoke[Failure]→resp`, `invoke[Retry]→log`,
`invoke[No Retry]→log`, `invoke[Failure]→log`, `invoke[Original]→log` — mirrors the same fan-out pattern
already proven on the production `InvokeHTTP-Lemonade` (flowVersion 23 fix, see above).

**Not done after that:** `GET .../flows/{id}/validate` (confirm `validationErrors: []`), then a real curl
test against `:8095` directly (bypassing the router's public port entirely, safe — this is a brand-new
port, not live traffic) before touching anything on `:8090`. Only **after** `:8095` round-trips a real
transcript should `RouteOnAttribute-HasFragments` be added ahead of the *shared* `HandleHttpRequest-Lemonade`
(`:8090`) to fork multipart traffic into this branch — that cutover is a separate, deliberate step per the
`nifi-and-ai` skill (rule 8: build new logic in its own PG/branch first, wire into a live path as a second
step), and needs a fresh go-ahead since it touches the shared production entry point. `GET .../flows/{id}/publish`
is what actually pushes any of this to the running agent — nothing above has been published; the live
`:8090` production pair is completely unaffected by any of this work.

**Test plan once cutover happens:**
```powershell
curl.exe -X POST http://localhost:8090/api/v1/audio/transcriptions `
  -F "model=Whisper-Large-v3-Turbo" -F "file=@test-audio.wav"
```
Expect the same real `200` + transcript text that hitting Lemonade directly on `:13305` already returns.
**Also re-verify chat/embeddings/reranking/speech** afterward — inserting `RouteOnAttribute` ahead of the
existing `InvokeHTTP` is a real wiring change to their path even though their processor configs don't
change, so it's a regression risk worth a real check, not an assumption.

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
