# #334 — OpenAI-compatible passthrough route to the EFM AI router (:8190)

**Status:** flow mod applied locally, awaiting publish from WindowsDesktop
**Opened:** 2026-09-14

## Goal

Add two OpenAI-passthrough arms to the existing `UpdateAttribute-TargetUrl` in the NvidiaSpark-1 class flow so opencode clients can reach the box's LLM at `${baseURL}/v1/chat/completions` and `${baseURL}/v1/models`.

## Flow changes (3 property edits, no new processors)

### 1. `UpdateAttribute-TargetUrl` (identifier: `3e86e8f8`)

Extended the nested `ifElse` chain to add:
- `/transcribe` → explicit arm to `http://127.0.0.1:8003/inference` (was the previous catch-all)
- `/v1/chat/completions` → `http://127.0.0.1:8000/v1/chat/completions` (same as `/reason`)
- catch-all (default) → `http://127.0.0.1:8000/v1/models`

Added attribute: `route.method = ${http.request.uri:equals('/v1/models'):ifElse('GET','POST')}`

### 2. `HandleHttpRequest-Router` (identifier: `f7211dd8`)

Updated `Allowed Paths`:
- Old: `/(reason|embed|rerank|transcribe)`
- New: `/(reason|embed|rerank|transcribe|v1/chat/completions|v1/models)`

### 3. `InvokeHTTP-Router` (identifier: `14775a63`)

Changed `HTTP Method` from `POST` to `${route.method}` (dynamic: GET for `/v1/models`, POST for everything else)

## Network blocker

EFM REST API at `192.168.1.121:10090` is unreachable from the DGX Spark — WindowsDesktop is offline or on a different subnet. The MiNiFi agent heartbeat still flows C2→EFM, but the REST API from the box fails. **Publishing must happen from WindowsDesktop** where the EFM UI/API is local.

## Publish from WindowsDesktop

Run on WindowsDesktop where EFM is accessible at `http://localhost:10090`:

```bash
FLOW_ID="7597a8f1-9a8b-4ad8-9f38-e70b6d450ca3"

# Upload modified flow
curl -X POST "http://localhost:10090/efm/api/designer/flows/$FLOW_ID/upload" \
  -H 'Content-Type: application/json' \
  -d @files/issue-226/flows/NvidiaSpark-1.designer-flow.json

# Validate
curl -s -X POST "http://localhost:10090/efm/api/designer/flows/$FLOW_ID/validate" \
  -H 'Content-Type: application/json'

# Publish
curl -s -X POST "http://localhost:10090/efm/api/designer/flows/$FLOW_ID/publish" \
  -H 'Content-Type: application/json'

# Re-export to git
curl -s "http://localhost:10090/efm/api/designer/flows/$FLOW_ID" \
  -o files/issue-226/flows/NvidiaSpark-1.designer-flow.json
```

## Verification after publish

From WindowsDesktop (tailnet):
```bash
curl http://100.104.155.57:8190/v1/models        # → 200 with model list
curl -X POST http://100.104.155.57:8190/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"nvidia/Qwen3.6-35B-A3B-NVFP4","messages":[{"role":"user","content":"hi"}]}'  # → 200 with completion
```

## Files changed
- `files/issue-226/flows/NvidiaSpark-1.designer-flow.json` (modified — 3 property edits)
- `files/issue-334/plan.md` (this file)
- `nvidia-dgx-spark-efm-agent.md` (update status line after publish)
