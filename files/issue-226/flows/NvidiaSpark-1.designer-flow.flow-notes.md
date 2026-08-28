# NvidiaSpark-1 class flow — what it does & the pattern it shows

**Export:** `NvidiaSpark-1.designer-flow.json` · **Agent:** MiNiFi Java `2.24.08.0-19`, EFM class `NvidiaSpark-1`, on `spark-dd06` (DGX Spark GB10) · **Live:** flowVersion 5 (16 processors / 19 connections / 1 controller service).

## What this flow is

The edge-AI **front door** for the DGX Spark: it is the thing the rest of the LAN calls to reach the box's four resident inference services. Every other device sends an HTTP request and gets a real synchronous answer back — the MiNiFi agent does nothing but accept the call, proxy it to the right local GPU service, and return the response.

## The pattern it demonstrates — consolidated single-handler router (path-driven dynamic InvokeHTTP)

**One** `HandleHttpRequest` (`:8190`, `Allowed Paths = /(reason|embed|rerank|transcribe)`) accepts all four routes, a dynamic `InvokeHTTP` (`HTTP URL = ${target.url}`) calls the right upstream, and **one** `HandleHttpResponse` answers every route. A single `StandardHttpContextMap` pairs each response to its request by `http.context.identifier`, which is why one request/response pair can serve every path concurrently. This replaced an earlier verbose shape of four separate `HandleHttpRequest → InvokeHTTP → HandleHttpResponse` legs on `:8190–:8193` (~12 processors → 1 listener + 1 caller + 1 responder). #270 §2.

**Path → target map.** Because the four doors sit on different ports *and* upstream paths, `UpdateAttribute-TargetUrl` derives `target.url` from the request path with a nested `ifElse`:

- `/reason`     → `http://127.0.0.1:8000/v1/chat/completions` (vLLM chat, `nvidia/Qwen3.6-35B-A3B-NVFP4`)
- `/embed`      → `http://127.0.0.1:8001/embed` (TEI)
- `/rerank`     → `http://127.0.0.1:8002/rerank`
- `/transcribe` → `http://127.0.0.1:8003/inference` (whisper.cpp — `/inference` only; `/v1/audio/transcriptions` 404s)

(The simpler sibling of this pattern, when every door shares one host+port and only the path differs, needs no map at all — just `HTTP URL = http://localhost:PORT${http.request.uri}`, as StarlinkAI's Lemonade router does. NvidiaSpark-1 needs the map because port and upstream-path both vary.)

**Per-route request Content-Type** rides on the flowfile, not hardcoded on the shared `InvokeHTTP` (`Request Content-Type = ${Content-Type}`): the JSON routes get `Content-Type = application/json` set in `UpdateAttribute-TargetUrl`; the transcribe route overwrites it with the multipart value in its own leg. (`${Content-Type}` only resolves because something explicitly sets that attribute first — leaving it unset makes a JSON upstream answer `415`.)

**Multipart reconstruction sub-branch for `/transcribe`.** `HandleHttpRequest` splits an inbound `multipart/form-data` upload into one flowfile per part; whisper wants the original body back. `RouteOnAttribute-Transcribe` sends `/transcribe` (and only that route) through `UpdateAttribute-FragmentKeys → RouteOnAttribute-HasContentType → ReplaceText (part header, with/without Content-Type) → MergeContent (Defragment, Binary Concatenation, boundary footer) → UpdateAttribute-SetMultipartContentType`, which rejoins the shared `InvokeHTTP`. The boundary string is identical across the two `ReplaceText` part-headers, the `MergeContent` footer, and the final `Content-Type`. Cloned from StarlinkAI's transcription leg.

**Error handling.** The shared `InvokeHTTP` has `penaltyDuration = 0 sec` and routes `Response` + `Retry`/`No Retry`/`Failure` all to the one `HandleHttpResponse`, whose status is `${invokehttp.status.code:replaceEmpty('502')}` — a bad upstream returns fast (a real 5xx/502) instead of hanging 30s on the penalty.

## The `:9936 /metrics` leg (separate, unchanged)

A fifth listener (`HandleHttpRequest-Metrics :9936` → `ExecuteStreamCommand-ProcMetrics` → `HandleHttpResponse-Metrics-OK`/`-Error`) serves Prometheus exposition format from a base64-wrapped `sh` script over `/proc/loadavg`+`/proc/meminfo` — the fleet's standard flow-level exporter (the Java agent's built-in Prometheus endpoint is blocked on an EFM-managed headless agent). Not an HTTP proxy, so it is *not* part of the consolidation. Its OK/Error responders sit a full 600px branch pitch apart (#270 §1).

## Field-validated (2026-08-28, spark-dd06, flowVersion 5)

All four doors + metrics return 200 through the single `:8190` listener (`/reason`, `/embed`, `/rerank` JSON; `/transcribe` via the multipart leg); `:8191/:8192/:8193` no longer listen. Curl each with the **correct upstream model name** — `POST :8190/reason` with an unknown `model` id 404s at vLLM, not a flow fault.
