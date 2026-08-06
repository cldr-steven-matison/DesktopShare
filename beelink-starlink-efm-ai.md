# Beelink SER9 MAX (H260): Windows-Native AI Router

<!-- Folded into the Complete Guide to Edge Flow Management → guide/ch17-edge-ai-router.md (#67, 2026-08-04). This doc stays the full field record (live processor UUIDs, the complete #88 saga); the chapter is the synthesized case study. -->

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
| Transcription | `/api/v1/audio/transcriptions` | **Yes** (fixed 2026-08-04, #88) — real 200, real transcript. Intake was always clean; the round trip through `InvokeHTTP` used to `400` until the multipart fragments were reassembled ahead of it — see "Transcription multipart reassembly — FIXED (#88)" below |

**The bug (found 2026-08-02, fixed 2026-08-04 — see the FIXED section below): multipart fragments never got reassembled before forwarding.** `HandleHttpRequest` splits a multipart request into one FlowFile per form field (confirmed via `minifi-app.log`: `http.multipart.fragments.total.number: 2`, one fragment for `model`, one for `file`). Each fragment is then forwarded to `InvokeHTTP-Lemonade` **independently**, as its own request, with `Content-Type` still set to the *original* multipart header (`multipart/form-data; boundary=...`) but a body that's only that one fragment's raw bytes — never valid multipart. Lemonade correctly rejects it: `invokehttp.response.body: {"error":{"message":"Bad request","type":"bad_request"}}`. Confirmed the request itself is well-formed by sending the identical multipart POST straight to Lemonade on `:13305` — real `200`, real transcript text back. The pure `HandleHttpRequest → InvokeHTTP → HandleHttpResponse` pass-through design (no reassembly step) works for single-part bodies (JSON, raw binary) but cannot proxy a true multi-field multipart request as-is; fixing it needs the fragments recombined (e.g. a `MergeContent` keyed on `http.multipart.fragments.*`) before `InvokeHTTP`. Filed as a new issue rather than folded into this fix, since it's a materially different problem from the error-routing gap above.

Test command:
```powershell
curl.exe -X POST http://localhost:8090/api/v1/chat/completions `
  -H 'Content-Type: application/json' `
  --data '@chat_body.json'
```
Use `--data @file.json` for the body, not an inline `-d '{...}'` string — PowerShell/`curl.exe` argument handling has silently stripped quotes out of inline JSON in past testing on this box.

## Transcription multipart reassembly — FIXED (#88)

**Status 2026-08-04: DONE. Fixed, cut over into production `:8090`, all 5 Lemonade endpoints confirmed
with real data (flowVersion 27). #88 closed.** The reassembly branch was built and proven in isolation on
port `:8095` first (flowVersion 26 — real `200`, real transcript), then wired into the shared production
entry point behind a `RouteOnAttribute-HasFragments` fork (flowVersion 27), with chat/embeddings/reranking/
speech regression-tested immediately after — zero regressions. The build detail below is the record of what
was built and the two gotchas that cost the most time.

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
| `ReplaceText-PrependPartHeaderWithType` | `11c74bd7-2140-4de9-9af7-b5fd7c0c374d` | Prepend. **The header text goes in `Replacement Value`, NOT `Text to Prepend`** — see gotcha below. Value: `--ClaudeStarlinkBoundary7f3a2b91\r\nContent-Disposition: ${'http.headers.multipart.Content-Disposition'}\r\nContent-Type: ${'http.headers.multipart.Content-Type'}\r\n\r\n` |
| `ReplaceText-PrependPartHeaderNoType` | `a1afe1a9-f923-4851-9cbe-d794befd23ac` | same (in `Replacement Value`), without the `Content-Type:` line |
| `MergeContent-Multipart` | `65003e4d-4c8b-4db0-b7ee-a3e52f7d43d0` | Merge Strategy `Defragment`, Delimiter Strategy `Text`, Demarcator `\r\n`, Footer `\r\n--ClaudeStarlinkBoundary7f3a2b91--\r\n`, `original` auto-terminated |
| `UpdateAttribute-SetMultipartContentType` | `fbe54062-ae59-4c7d-993b-35d82d77095b` | `Content-Type` = `multipart/form-data; boundary=ClaudeStarlinkBoundary7f3a2b91` |
| `InvokeHTTP-TranscriptionTest` | `74aec6a4-e955-41a2-b62d-87747400a3e8` | same as prod `InvokeHTTP-Lemonade` (10 min timeouts) except `Request Content-Type` = `${Content-Type}`, not `${mime.type}` |
| `HandleHttpResponse-TranscriptionTest` | `56b240bd-0887-403d-b9fd-8e71aae69389` | `HTTP Status Code` = `${invokehttp.status.code:replaceEmpty('502')}` |
| `LogAttribute-TranscriptionTest` | `ba0bac17-2ef1-486b-85c9-16aac651032d` | error/visibility tap |

Note `Delimiter Strategy: Text` lets `MergeContent`'s Demarcator/Footer be literal property values —
`Filename` mode (a file on disk) was the other option but isn't needed here.

**All 19 connections wired** (flowVersion 25), mirroring the production `InvokeHTTP-Lemonade` fan-out
pattern: `req[success]→frag[success]→route`; `route[hasType]→rt_with`, `[unmatched]→rt_without`; both
`[success]→merge`, `[failure]→log`; `merge[merged]→set_ct[success]→invoke`; `invoke[Response/Retry/No
Retry/Failure]→resp` and `→log`; `invoke[Original]→log`. Validation also caught that
`LogAttribute-TranscriptionTest`'s `success` and `HandleHttpResponse-TranscriptionTest`'s `success`/
`failure` needed `autoTerminatedRelationships` set — matching their production twins.

**Two gotchas cost the most time — both traced against `:8095` in isolation before any production traffic:**

1. **`ReplaceText` prepends `Replacement Value`, not `Text to Prepend`** (on this `minifi-standard-nar
   2.24.08.0-19` build). The real boundary/header text was sitting in the intuitively-correct `Text to
   Prepend` field while `Replacement Value` was left at its literal default `$1` — so the reconstructed
   multipart body came out missing its opening boundary with every part starting with a literal `$1`.
   Moving the header text into `Replacement Value` on both `ReplaceText` processors fixed it (flowVersion 26).
2. **MiNiFi's `InvokeHTTP` does not replace FlowFile content with the HTTP response body on a non-2xx** —
   the `Response` relationship's content stays the original *outgoing* request bytes. Reproduced against
   production with a deliberately bad chat request, so this is router-wide, not branch-specific; it just
   never surfaced before because prior testing only exercised the success path. Useful side effect: it let
   me read the exact bytes MiNiFi sent to Lemonade, which is how gotcha #1 was found.

**Proven in isolation (flowVersion 26):** real `curl` against `:8095` returned `200`, `{"text":" .\n"}` — a
genuine Whisper response (the test WAV is a pure 1s tone, not speech, so minimal text is expected; the round
trip is what's proven). Note the original `test-audio.wav` in this repo turned out to be an 18-byte
placeholder (`RIFF....WAVEtest`) — a real 1s tone had to be generated to test.

**Cutover into production (flowVersion 27):** added `RouteOnAttribute-HasFragments` between
`HandleHttpRequest-Lemonade` and `InvokeHTTP-Lemonade` — dynamic property `hasFragments` =
`${http.multipart.fragments.total.number:isEmpty():not()}`, mirroring the existing
`RouteOnAttribute-HasContentType` pattern. Multipart requests fork into the proven reassembly branch;
everything else (`unmatched` — chat/embeddings/reranking/speech, none of which carry multipart fragment
attributes) continues straight to `InvokeHTTP-Lemonade`, unchanged. No new response-side wiring was needed:
`HandleHttpResponse-TranscriptionTest` and `HandleHttpResponse-Lemonade` share the same
`StandardHttpContextMap`, and NiFi correlates the reply to the original caller via the
`http.context.identifier` attribute — not by which `HandleHttpResponse` instance fires — so a request that
arrives on `:8090` is answered correctly even though it routes through the `:8095`-branch's response processor.

**Confirmed on production `:8090` (flowVersion 27):**
```powershell
curl.exe -X POST http://localhost:8090/api/v1/audio/transcriptions `
  -F "model=Whisper-Large-v3-Turbo" -F "file=@test-audio.wav"
```
returned `200`, `{"text":" .\n"}`. **Chat/embeddings/reranking/speech regression-tested immediately after**
(inserting `RouteOnAttribute` ahead of the shared `InvokeHTTP` is a real wiring change to their path even
though their configs don't change): chat → real completion, embeddings → real vector, reranking → real
relevance scores, speech → real 34KB MP3. **All 5 Lemonade endpoints round-trip real data through `:8090`,
zero regressions.**

## Status

**2026-08-06 (#131/#133): consolidated onto a single `StarlinkAI` class.** The C++ `StarlinkAI` (Twitch stream-screen control) and this doc's `StarlinkAIJava` (Lemonade router) were merged into one Java agent under a recreated `StarlinkAI` class — the flow described below was ported in via EFM's `flows/export`/`flows/import`, the old C++ agent stopped/disabled, and `StarlinkAIJava`'s agent + class deleted from EFM. Everything below that refers to `StarlinkAIJava` now runs under `StarlinkAI` instead; install path is `C:\Users\tunas\efm-agent\StarlinkAI-java\minifi-2.24.08.0-19\`, still port `8090`. The architecture, flow build, and endpoint behavior described below are unchanged — only the class name and install path moved.

**Done:**
- [x] Tailscale, Lemonade Server (5 models loaded, Vulkan GPU offload confirmed), JDK 21, MiNiFi Java agent all installed and running on `TunaStarlink`
- [x] `StarlinkAI` EFM class online, heartbeating (consolidated 2026-08-06, formerly `StarlinkAIJava`)
- [x] Unified 3-processor pass-through flow built, validated, published
- [x] Root-caused and fixed the timeout bug (`Socket Read Timeout` 15s default → 10 min)
- [x] Chat confirmed working end-to-end with real content, real synchronous answer
- [x] Transcription's multipart intake confirmed clean under `HandleHttpRequest` (the failure mode that blocked the old `ListenHTTP`-based design is gone)
- [x] Full end-to-end retest of embeddings/reranking/speech with real data — all 3 confirmed working
- [x] Forward `InvokeHTTP`'s non-2xx responses back to the caller instead of leaving them stuck on `LogAttribute-Error` only (flowVersion 23)
- [x] Fix multipart fragment reassembly so transcription's real round trip works (#88, flowVersion 26 isolated → 27 cutover) — **all 5 endpoints now confirmed on production `:8090`, zero regressions**
- [x] **2026-08-06 (#133 reopen): screen/matrix Twitch-chat control rebuilt on this class, native-agent style.** The `StarlinkAI` class canvas still carried a leftover `HandleHttpRequest → InvokeHTTP → HandleHttpResponse` relay for stream-load (`StreamScreen3`/`StreamScreen4` on `:8091`/`:8092`, POSTing to the always-on `mpv_stream_launcher.py`/`windows_matrix_launcher.py` Scheduled Tasks on `:5902`/`:5901`) — the old middle-layer shape #130 already retired on `WindowsDesktop`, and matrix (`!matrix screen3/4`) was never wired into EFM at all. Rebuilt in place on the *same* single Java agent (no second agent/class — one MiNiFi process on this host) using #130's exact pattern: `HandleHttpRequest → [EvaluateJsonPath] → ExecuteStreamCommand → HandleHttpResponse`, `ExecuteStreamCommand` invoking `files/starlinkai_screen_control.py` (deployed to `C:\minifi-manual\`) directly per request — no persistent listener. Four new port pairs, all on the same `StarlinkAI` class alongside the Lemonade flow:
  - `:8091` → `mpv-load screen2` (array-facing `screen3`)
  - `:8092` → `mpv-load screen3` (array-facing `screen4`)
  - `:8093` → `matrix-load screen2` (array-facing `screen3`)
  - `:8094` → `matrix-load screen3` (array-facing `screen4`)

  Old `StreamScreen3`/`StreamScreen4`/`InvokeHTTP`/`LogAttribute-Error-Screens` processors deleted; flow published (flowVersion 2), validated `0` errors. `MatrixLauncherListener`/`MpvStreamLauncherListener` Scheduled Tasks stopped (files left on disk, not deleted) — ports `5901`/`5902` confirmed closed. `idle_watcher.py` updated to call `starlinkai_screen_control.py` directly as a local subprocess instead of POSTing to the now-retired `:5901` listener. Verified end-to-end live: `mpv-load`/`matrix-load`/`mpv-stop` on both screens via loopback `curl` to all 4 new ports, confirmed correct monitor placement (`GetWindowRect`: screen2 → `1920,0`–`3840,1080`, screen3 → `3840,0`–`5760,1080`), and confirmed true per-screen isolation (both screens' matrix kiosks running simultaneously, one screen's `matrix-load` doesn't touch the other's window — required a fix to `kill_matrix_for_screen`/profile-dir naming to be screen-scoped, since the single-screen `WindowsDesktop` original never had to handle two matrix windows at once). Old C++ Windows service (`Apache NiFi MiNiFi`) reconfirmed `Stopped`/`Disabled`, no `minifi.exe` process — was already fully off from the #131 cutover despite the reopen comment's concern. **Central NiFi's `TwitchChatBot` wiring (`InvokeStarlinkScreen3`/`InvokeStarlinkScreen4` pointed at the stale pre-#131 `:8085`/`:8086`, no matrix `InvokeHTTP`s existed at all) is handled separately on WindowsDesktop, not from this doc's side.**

**Open:**
- [ ] Cross-Tailscale test from a second array machine (only local curl tested so far)
