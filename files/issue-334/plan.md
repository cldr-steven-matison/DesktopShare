# #334 — OpenAI-compatible passthrough route to the EFM AI router (:8190)

**Status:** done — flowVersion 10 published from WindowsDesktop 2026-09-14 23:05 UTC, all doors verified over the tailnet
**Opened:** 2026-09-14

## Goal

Add OpenAI-passthrough arms to the existing `UpdateAttribute-TargetUrl` in the NvidiaSpark-1 class flow so opencode clients can reach the box's LLM at `${baseURL}/v1/chat/completions` and `${baseURL}/v1/models` — `baseURL = http://100.104.155.57:8190/v1`.

## What actually shipped (flowVersion 10, three `PUT .../processors/{id}` edits, no new processors)

The plan below this section was written on the box against the git export (flowVersion 5). By the time WindowsDesktop picked it up the live flow was already at **flowVersion 9** — richer than the export (it also had `/v1/embeddings` and `/v1/reranking` arms) but broken: its `target.url` expression ended in a bare `null` and did not parse, so every door (including `/reason`) returned 502 in 24 ms with the request body echoed back. Uploading the git copy would have regressed the live flow, so the fix was applied to the live v9 instead:

### 1. `UpdateAttribute-TargetUrl` (`3e86e8f8…`, rev 3→4)
- `target.url`: same eight arms as v9 (`/reason`, `/embed`, `/rerank`, `/v1/chat/completions`, `/v1/models`, `/v1/embeddings`, `/v1/reranking`, `/transcribe`), final `ifElse` branch `''` instead of `null`. Balanced: 8 `${`/`}`, 16 `(`/`)`.
- `route.method` = `${http.request.uri:equals('/v1/models'):ifElse('GET','POST')}`

### 2. `HandleHttpRequest-Router` (`f7211dd8…`, rev 1→2)
- `Allow GET` = `true` (was `false` — the reason `GET /v1/models` 405'd at Jetty even after v9 mapped the path). `Allowed Paths` was already `/(reason|embed|rerank|transcribe|v1/chat/completions|v1/models|v1/embeddings|v1/reranking)` in v9.

### 3. `InvokeHTTP-Router` (`14775a63…`, rev 0→1)
- `HTTP Method` = `${route.method}` (was static `POST`).

`GET .../validate` → `{"validationErrors":[]}`; `POST .../publish` → flowVersion 10, 1789423528501.

## Getting v10 onto the agent (the second half of the day)

The publish did not land: EFM's `lastSeen` for the agent was frozen at 20:25 and the `UPDATE` op timed out `DEPLOYED → FAILED`. Cause: the box's Wi-Fi had moved to a different `192.168.1.x` network, so the box session re-pointed `c2.rest.path.base` at the tailnet (`100.68.113.126:10090`) at 20:17 — and that rewrite dropped **`c2.full.heartbeat=false`**. Full beats carry the 1.19 MB manifest; over the ~875 ms DERP-relayed path with a 10 s read timeout they truncate (`Early EOF` at EFM, `SocketTimeoutException` at the agent). Restored the line (backup `conf/bootstrap.conf.bak-20260914-334`), Steven ran `sudo systemctl restart minifi-java`, v10 applied in ~10 s, zero heartbeat failures after.

## Verification (2026-09-14 23:05 UTC, from WindowsDesktop over the tailnet)

| Door | Result |
|---|---|
| `GET /v1/models` | **200**, `{"data":[{"id":"nvidia/Qwen3.6-35B-A3B-NVFP4"…}]}`, 0.51 s |
| `POST /v1/chat/completions` | **200**, 0.69 s |
| `POST /reason` | **200**, 0.63 s (was 502 since v9) |
| `POST /embed` | **200**, 0.69 s |
| `POST /rerank` | **200**, 0.56 s |
| `opencode run --model vllm/nvidia/Qwen3.6-35B-A3B-NVFP4` from `~` | `OK` in 22 s — #331 acceptance |

## Files changed
- `files/issue-226/flows/NvidiaSpark-1.designer-flow.json` — re-exported at flowVersion 10 (the git copy had been the v5 export + an unpublished v6-style edit)
- `files/issue-226/flows/NvidiaSpark-1.designer-flow.flow-notes.md` — aliases, `route.method`, the `null` trap
- `nvidia-dgx-spark-efm-agent.md` — status line, diagram, route table, as-built, #334 addendum
- `CLAUDE-CHECKIN.md` — NvidiaSpark-1 block (C2 on the tailnet, box off the array LAN), WindowsDesktop opencode fact
- `nvidia-dgx-spark-plan.md` row G, `Complete Developer Guide for Nvidia Spark with Cloudera.md` row 12
- `files/issue-334/plan.md` (this file)

## Original publish plan (superseded — kept for the record)

The box could not reach EFM's REST API (`192.168.1.121:10090`), so the intent was: upload `files/issue-226/flows/NvidiaSpark-1.designer-flow.json` → validate → publish → re-export from WindowsDesktop. There is no whole-flow upload on the Designer API for an existing flow (skill `references/minifi-efm.md` §7) and the git copy was behind live, so the edits went in per-processor instead.
