---
layout: single
title: "Streamers — Twitch Clip Pipeline Module for the CSO Operator App"
date: 2026-06-28
classes: wide
categories:
  - blog
tags:
  - nifi
  - kafka
  - twitch
  - whisper
  - vllm
  - cso
  - kubernetes
  - operator-app
---

> **Status:** WORKING — pipeline live, publishing to @TunaStreetTest.
> App repo: `github.com/cldr-steven-matison/cso-operator-app`
> Companion plan: [`cso-operator-app-plan.md`](cso-operator-app-plan.md)

---

## What It Does

The **Streamers module** watches Twitch for top clips from a configured watch list, transcribes them with Whisper, generates a caption with vLLM, queues them in a review UI, and publishes approved clips to X (@TunaStreetTest) with original commentary.

Optional module — enabled at build/deploy time via `MODULES=streamers`. Layers on top of the existing Whisper + vLLM stack with no changes to those services.

---

## Pipeline

```
Twitch API (GQL)
      │
      ▼
FetchClips NiFi flow
  GenerateFlowFile (15 min) → InvokeHTTP POST /api/streamers/fetch-clips
  Backend: Twitch OAuth → GQL VideoAccessToken_Clip → download MP4 → /clips/<id>.mp4
  → PublishKafka → new_clips
      │
      ▼
ProcessClips NiFi flow
  ConsumeKafka ← new_clips → InvokeHTTP POST /api/streamers/process-clip
  Backend: POST whisper-service:8001/transcribe → POST vllm-service:8000/v1/chat/completions
  → PublishKafka → processed_clips
      │
      ▼
Streamers Page — Review UI
  Watch clip · Edit caption · Add commentary · Approve → queues in .pending_publish.json
      │
      ▼
PublishClip NiFi flow (manual/backup — GenerateFlowFile now 1/day)
PublishClipPeakTimeCron NiFi flow (primary — cron 3pm-9pm)
  → InvokeHTTP POST /api/streamers/publish-next → pops one pending clip
      │
      ▼
X API: tweepy v1 media_upload (chunked) + v2 create_tweet
```

All NiFi flows live under a `StreamersApp` parent PG — separate from `CSOOperatorApp`. Four process groups: `FetchClips`, `ProcessClips`, `PublishClip`, `PublishClipPeakTimeCron`.

---

## Existing Services Used

| Service | Use |
|---|---|
| `whisper-service:8001` | `POST /transcribe` — multipart MP4 → `{"text": "..."}` |
| `vllm-service:8000` | `POST /v1/chat/completions` — transcript → caption |
| Kafka (Strimzi) | `new_clips`, `processed_clips` topics (1 partition each) |
| NiFi (CFM) | 3 process groups under `StreamersApp` PG |

New per this module:
- Twitch + X API credentials injected via `kubectl set env` (never in YAML)
- PVC at `/clips` for MP4 storage — `streamers/pvc.yaml`
- Kafka topics — `streamers/kafka-topics.yaml`

---

## Module System

`MODULES` is a build-time flag that controls which optional tabs are active. `build-modules.py` only recognizes `streamers` as a known module; `efm` and `rag` are handled purely at the frontend/backend level via the same env var.

```
Dockerfile ARG MODULES=''
  → VITE_MODULES baked into React bundle → shows/hides nav tabs
  → ENV MODULES in backend image → registers /api/streamers/* routes only if "streamers" present
```

**Frontend** (`App.tsx`): tabs for `efm`, `rag`, `streamers` only render if their name appears in `VITE_MODULES`.

**Backend** (`main.py`): `efm` router is always included. `streamers` router is conditionally registered. `rag` panels use always-present routers (query, ingest, nifi, qdrant, kafka).

| `MODULES=` value | Active tabs |
|---|---|
| *(empty)* | Operator only |
| `rag` | Operator + RAG |
| `streamers` | Operator + Streamers |
| `rag,streamers` | Operator + RAG + Streamers |
| `efm,rag,streamers` | All tabs |

---

## Deploy

```bash
cd ~/cso-operator-app
make deploy MODULES=rag,streamers
```

App is permanently at **http://127.0.0.1:8090** via `minikube tunnel` (LoadBalancer service).
`minikube tunnel` must be running — it's the first step in the terminal setup and also auto-opens Chromium.

After any deploy that resets the pod, re-inject credentials:

```bash
source ~/.env
kubectl set env deploy/cso-operator-app \
  NIFI_USERNAME=admin \
  NIFI_PASSWORD="${NIFI_ADMIN_PASS}" \
  TWITCH_CLIENT_ID="${TWITCH_CLIENT_ID}" \
  TWITCH_CLIENT_SECRET="${TWITCH_CLIENT_SECRET}" \
  KICK_CLIENT_ID="${KICK_CLIENT_ID}" \
  KICK_CLIENT_SECRET="${KICK_CLIENT_SECRET}" \
  X_API_KEY="${X_API_KEY}" \
  X_API_SECRET="${X_API_SECRET}" \
  X_ACCESS_TOKEN="${X_ACCESS_TOKEN}" \
  X_ACCESS_TOKEN_SECRET="${X_ACCESS_TOKEN_SECRET}" \
  STREAMERS_WATCH_LIST="stableronaldo"
```

### Rebuild Whisper image

Only needed when `whisper/Dockerfile.whisper` changes:

```bash
eval $(minikube docker-env)
docker build -t streamwhisper:latest -f whisper/Dockerfile.whisper .
kubectl rollout restart deploy/whisper-server
```

### Scale down idle services

EFM, SSB, Schema Registry, and MiNiFi are not needed for the Streamers pipeline:

```bash
kubectl scale deploy efm schema-registry ssb-mve ssb-sse -n cld-streaming --replicas=0
kubectl delete pod minifi-agent-k8s -n cld-streaming
# ssb-postgresql stays running (EFM/Schema Registry config is stored there)
```

Restore: `--replicas=1` and `kubectl apply -f ~/ClouderaStreamingOperators/minifi-agent-pod.yaml`

---

## Streamers API Endpoints

| Endpoint | Called by |
|---|---|
| `POST /api/streamers/fetch-clips` | NiFi FetchClips (every 15 min) |
| `POST /api/streamers/process-clip` | NiFi ProcessClips (per Kafka message) |
| `GET  /api/streamers/queue` | Review UI on load |
| `GET  /api/streamers/clip/{clip_id}` | Video player in ClipCard |
| `POST /api/streamers/publish` | Approve button |
| `POST /api/streamers/skip` | Skip button |
| `GET  /api/streamers/topics` | Topics panel (30s cached) |
| `POST /api/streamers/reset` | Reset Kafka button |
| `GET  /api/streamers/watchlist` | Watch List section |
| `POST /api/streamers/watchlist` | Watch List add/remove |
| `GET  /api/streamers/flows` | Pipeline Status panel (30s polled) |
| `POST /api/streamers/flows/{name}/start\|stop` | Flow start/stop buttons |

---

## Clip Fetch Behavior

- Fetches 20 clips per streamer, filters to ≥ 45s, sorts longest-first
- Caps at **5 clips per streamer per run**
- Deduplication via `/clips/.seen_clips.json` — no re-download of previously fetched clips
- Skip/publish state persisted to `/clips/.skipped.json` and `/clips/.published.json`
- Reset Kafka button wipes MP4s, seen/skipped/published lists, and deletes both topics

---

## Whisper Configuration

`whisper/Dockerfile.whisper` — Whisper-large-v3, Flash Attention 2, CUDA 12.4:

```python
pipe(tmp_path, chunk_length_s=60, batch_size=24, return_timestamps=True)
```

- `chunk_length_s=60` — matches Twitch clip max duration
- `batch_size=24` — GPU-tuned for RTX 4060
- Temp file written as `.mp4` (matches actual clip format)
- Keep the server synchronous — `run_in_executor` broke startup

---

## NiFi ProcessClips Concurrency

`streamers/StreamersApp.json` sets `concurrentlySchedulableTaskCount=3` on `InvokeHTTP` and `PublishKafka_2_6` in ProcessClips. NiFi sends 3 clips to the backend simultaneously; Whisper queues them at the HTTP level. ConsumeKafka stays at 1 (single Kafka partition).

---

## PublishClipPeakTimeCron

New PG (added session 12) that publishes pending-approved clips on a cron schedule during peak viewing hours, instead of relying on the old fixed-interval `PublishClip` GenerateFlowFile.

| Processor | Config |
|---|---|
| `Peak Time 4-11pm` (GenerateFlowFile) | `CRON_DRIVEN`, schedule `0 0/9 16-23 * * ?` — every 9 min, hours 16-23 UTC |
| `InvokeHTTP` | `POST http://cso-operator-app.default.svc.cluster.local:8090/api/streamers/publish-next` — same endpoint the original `PublishClip` PG calls |

**Updated (session 15):** renamed from `Peak Time 3-9pm` (`0 0/18 19-23,0-1 * * ?`, an EDT-converted window) to `Peak Time 4-11pm` (`0 0/9 16-23 * * ?`) — a wider, more frequent window (16-23 UTC is a single contiguous range vs. the old wraparound `19-23,0-1`; interval tightened from every 18 min to every 9 min) set directly in UTC hours rather than converted from EDT. This sidesteps the earlier DST-shift concern (session 13's note that the old expression would need to shift an hour at DST changeover) since the window is now defined in pod-local UTC terms directly, not translated from a US timezone.

**Correction (session 13, historical):** the original `15-21` cron assumed the NiFi pod's clock was pod-local EST. It isn't — `mynifi-0` runs in UTC (`date` in the pod returns `UTC`, confirmed 2026-07-02: pod showed 18:52 while local system showed 14:52 EDT). So `15-21` was actually firing 11am-5pm EDT, an hour(s) early. Corrected at the time to the UTC-equivalent of 3pm-9pm EDT (`19-23,0-1`), since superseded by the session 15 update above.

Both processors are `ENABLED`. The original `PublishClip` PG's `Publish On Demand` GenerateFlowFile was throttled from its prior interval down to `1 day`, effectively demoting it to a manual/backup trigger now that the cron PG owns regular peak-hour publishing. No new backend endpoint was needed — both PGs hit the same `/api/streamers/publish-next`, which pops one clip off `.pending_publish.json` per call.

Flow exported to `StreamersApp_PeakTime_Cron.json` (Downloads) — not yet folded into the committed `streamers/StreamersApp.json` snapshot.

---

## Key Technical Gotchas

| Issue | Fix |
|---|---|
| Twitch CDN changed 2024 — thumbnail→.mp4 URL dead | GQL `VideoAccessToken_Clip` query → `sourceURL?sig=&token=` |
| aiokafka hangs after manual `seek()` with `async for` | Use `getmany(tp, timeout_ms=5000)` one-shot fetch |
| Strimzi created 1 partition despite spec saying 3 | Hardcode `TopicPartition(topic, 0)` |
| X API v1.1 `update_status` retired | tweepy v2 `create_tweet` + v1 `media_upload(chunked=True)` |
| X API 402 "no credits" | Pay-per-use billing — add credits at developer.x.com |
| HuggingFace pipeline has no `beam_size` param | Use `num_beams` or omit — default is already greedy |
| `asyncio.Semaphore` + `run_in_executor` in Whisper | Broke server startup — HTTP queuing at NiFi layer is sufficient |
| NiFi InvokeHTTP URL to app | Use `http://cso-operator-app.default.svc.cluster.local:8090/api/...` — NodePort 30090 is external only and will timeout |
| Kick public API `/clips` endpoint | Returns 404 — use `kick.com/api/v2/clips?channel=<slug>` with browser `User-Agent` + `Referer: https://kick.com/` headers |
| Kick HLS clips need ffmpeg remux | `clip_url` is `.m3u8` — download with `ffmpeg -c copy -movflags +faststart`; do NOT re-encode with libx264 (too slow) |
| Whisper can't read MP4 directly | Whisper server saves uploads as `.wav`; soundfile fails on MP4 content — extract 16kHz mono WAV with ffmpeg before uploading |
| Parallel fetch race condition | `seen` set must be updated before download, not after, to prevent concurrent streamers downloading the same clip |

---

## What's Next

- **NiFi-native refactor (Fetch, Process, Publish)** — ✓ PLANNED, expanded from Process-only to all three legs (see section below)
- **Post Now (Telegram + UI)** — ✓ SHIPPED (session 14, see section below)
- **Publish history tab** — `.published.json` already written per clip; just needs a UI to surface tweet URLs + timestamps
- **Auto-publish mode** — bypass review queue, post top clips on a schedule
- **Post to real X account** — ✓ PLANNED (see section below)
- **GPU optimization** — Whisper CPU + 5B caption model — see [`gpu-optimization-plan.md`](gpu-optimization-plan.md)
- **Live Streamer Alert** — FUTURE IDEA (added session 12): when a watched streamer goes live, ramp up clip fetch/publish frequency for that streamer and possibly post an X alert that they're live now. Built entirely in NiFi, likely needs a custom Python processor to poll Twitch/Kick live status and branch the flow (idle vs. live-heavy) — not scoped or designed yet.
- **Video title/description/CTA/category** — PUNTED (session 12): needs an X Ads account for @TunaStreetTest before it's buildable. See "Untitled Videos" section above for what's confirmed.
- **Subtitles from transcript** — unblocked, deprioritized (session 12): `POST /2/media/subtitles` + existing Whisper segment timestamps could give real closed captions with no new credentials. See "Untitled Videos" section above.
- **Reply Guy** — FUTURE IDEA (added session 15): auto-reply bot behavior, threaded onto every posted clip's tweet. Reply 1 — link to the streamer's own stream/channel page (their Twitch/Kick profile URL; already have this value on every clip record as `clip.streamer` + `clip.source`). Reply 2 — the clip's transcript, likely a quotable excerpt rather than the full wall of text (not finalized; would need vLLM if excerpting rather than dumping raw text). Not scoped or built yet.
- **More Telegram scripts** — FUTURE IDEA: `Fetch Clips` and `Publish Clips` on-demand triggers, same reply-to-chat pattern as `agent-PostNow.sh`. Post Now is the first one built.

---

## Posting to a Real X Account (Multi-Account Setup)

**Goal:** Keep the X app registered under @TunaStreetTest (developer account) but post to a different real account. No public app needed — only you can authorize it.

### How It Works

The X app owner (developer account) and the account that grants OAuth access are separate concepts. The app stays registered under @TunaStreetTest. Your real account authorizes the app via OAuth and you capture those tokens. Posts flow through the same tweepy code — just different credentials.

### Steps

**1. Confirm OAuth 1.0a User Context is enabled on the app**

In [developer.twitter.com](https://developer.twitter.com) (logged in as @TunaStreetTest):
- Open the app → Settings → User authentication settings
- Enable OAuth 1.0a
- Set callback URL: `http://localhost:3000/callback` (or any localhost port)
- Save

**2. Run the one-shot OAuth dance for your real account**

```python
# oauth_dance.py — run once, prints real account tokens
import tweepy

API_KEY = "..."        # your app's consumer key (from @TunaStreetTest dev portal)
API_SECRET = "..."     # your app's consumer secret

auth = tweepy.OAuthHandler(API_KEY, API_SECRET, callback="oob")
print("Go to this URL and log in as your REAL account:")
print(auth.get_authorization_url())

pin = input("Enter the PIN from Twitter: ")
auth.get_access_token(pin)

print(f"\nX_ACCESS_TOKEN={auth.access_token}")
print(f"X_ACCESS_TOKEN_SECRET={auth.access_token_secret}")
```

Run `python oauth_dance.py` — it prints a URL, you open it logged in as the real account, approve, paste the PIN. Done.

**3. Inject real account tokens into the pod**

```bash
source ~/.env
kubectl set env deploy/cso-operator-app \
  X_ACCESS_TOKEN="<real_account_access_token>" \
  X_ACCESS_TOKEN_SECRET="<real_account_access_token_secret>"
# X_API_KEY and X_API_SECRET stay the same (they're the app's consumer keys, not account-specific)
```

**4. Verify**

Post a test clip through the review UI — it should appear on the real account, not @TunaStreetTest.

### Notes

- App stays private — no listing, no approval process, only you can authorize
- Consumer key/secret belong to the app (stay the same)
- Access token/secret belong to the account (swap these to switch accounts)
- To switch back to @TunaStreetTest, re-inject the original access token/secret
- Add `oauth_dance.py` to `.gitignore` — don't commit it with keys filled in

---

## NiFi-Native Refactor Plan — Fetch, Process, Publish

Today all three legs of the pipeline — `FetchClips`, `ProcessClips`, `PublishClip` — are thin NiFi process groups (`ConsumeKafka`/`HandleHttpRequest` in, one `InvokeHTTP` out) that hand ALL the real work to Python in `backend/services/streamers.py`: Twitch/Kick API calls, ffmpeg overlay/glitch-intro/remux, Whisper/vLLM calls, tweepy X posting. That's backwards from the intended shape of this system — the repo owner is a NiFi person, and NiFi should own the actual flow logic, with the app backend reduced to orchestration. This plan expands the earlier Process-only refactor (kept below, close to verbatim — it's already reviewed and correct) to cover all three legs, and describes what's left of the backend once the real work moves into NiFi.

### The integration direction flips

Today: NiFi calls the backend (`InvokeHTTP POST /api/streamers/{fetch-clips,process-clip,publish}`) and blocks on a synchronous HTTP response while the backend does everything.

After this refactor: the backend calls NiFi. It becomes a looper/orchestrator — walk the watch list, react to UI actions (Approve/Skip/Post Now/Reset) — and POSTs each unit of work into a NiFi HTTP listener (`HandleHttpRequest`/`ListenHTTP`) so NiFi's own native/custom processors execute it and drive the flow forward. This isn't a novel idea here — `/home/tunas/DesktopShare/files/midi_melody2.py` already does exactly this shape against a MiNiFi flow: a standalone Python loop (`send_to_pipeline()`) `requests.post()`s each unit of work (one note at a time) to a `HandleHttpRequest`/`ListenHTTP` endpoint (`http://localhost:9998/contentListener`) and lets the flow take it from there. Same pattern: backend loops over data, POSTs into a NiFi listener, NiFi executes — just applied to clips instead of MIDI notes.

### Native vs. custom-Python split logic

Default to native NiFi processors — `InvokeHTTP`, `EvaluateJsonPath`, `UpdateAttribute`, `ExecuteStreamCommand`, `Wait`/`ControlRate`, `DetectDuplicate`, and the built-in `StandardOauth2AccessTokenProvider` controller service cover most of what Fetch/Process/Publish actually need. Drop to a custom Python processor only where a native processor genuinely can't do the job — not just because Python is more familiar. Concretely there are two hard blockers in this pipeline: (1) X's chunked media upload is OAuth 1.0a-signed, and `InvokeHTTP` has no OAuth1 signing support (only OAuth2, via the access-token-provider controller service); and (2) the ffmpeg overlay/glitch-intro pipeline is a long, conditional, randomized multi-step orchestration with hard-won gotcha-fixes (thread pinning, B-frame-free encodes for stream-copy concat) that would be brittle and painful to re-express as a chain of `ExecuteStreamCommand` calls stitched together with NiFi expression language.

---

### Custom Python Processor Strategy

NiFi 2.x's native Python processor API (`nifiapi`) has two processor shapes in the same package family:

- **Source-style** — `nifiapi.flowfilesource.FlowFileSource`, used when a processor has no incoming flowfile and originates content itself. This is the pattern actually demonstrated locally, in `/home/tunas/nifi-custom-processors/NewTransactionGenerator.py` and its packaged/`hatch`-built form `/home/tunas/nifi-custom-processors/TransactionGenerator/python/processors/TransactionGenerator.py` (built into `custom-transaction-generator.nar`). Both declare:
  ```python
  class Java:
      implements = ['org.apache.nifi.python.processor.FlowFileSource']
  class ProcessorDetails:
      version = '0.0.x-SNAPSHOT'
      description = '...'
  ```
  and implement `create(self, context)`, returning `FlowFileSourceResult(relationship='success', attributes={...}, contents=...)`.
- **Transform-style** — `nifiapi.flowfiletransform.FlowFileTransform`, same package family, different base class: takes an incoming flowfile and returns a transformed one via `transform(self, context, flowfile)` → `FlowFileTransformResult`. **This repo only demonstrates the source-style API directly** — there's no local transform-style example checked in — but it's the same `nifiapi` family, and it's what all three custom processors below actually need (flowfile in, transformed/enriched flowfile + attributes out), not the source-style no-input shape.

**Deployment/packaging** — proven locally via the CFM `Nifi` CRD manifests and `DesktopShare/files/`:
- `nifi-cluster-30-nifi2x-nar.yaml` — NAR-only (Java) baseline, no Python.
- `nifi-cluster-30-nifi2x-python.yaml` — adds a `hostPath: /extensions` volume mounted at `/opt/nifi/nifi-current/python/extensions` on the NiFi statefulset, plus `narProvider.volumes` pointing at a `custom-nars` PVC for Java NARs.
- `/home/tunas/DesktopShare/files/nifi-cluster-30-nifi2x-statefulset-2.yaml` and `-3.yaml` — the most complete/authoritative version: sets `nifi.python.extensions.directories: "./python_extensions,/opt/nifi/nifi-current/python/extensions"` under `configOverride.nifiProperties.upsert`, and adds env vars `NIFI_PYTHON_LISTENER_STARTUP_TIMEOUT: "600 sec"` (gives `pip` time to install heavy deps) and `NIFI_PYTHON_PROXIED_LOG_LEVEL: "DEBUG"` (verbose `nifi-python.log` output on load failure). Both explicitly comment that the extensions directory is expected to be built with `hatch build` and dropped onto that host path.
- `nar-loader.yaml` — a `custom-nars` PVC + throwaway `ubuntu` pod used to `kubectl cp` built NAR files onto the shared volume the NiFi statefulset mounts — how NARs land on the cluster without rebuilding the NiFi image itself.

**Candidate custom processors**:

| Processor | Leg | Replaces | Why native can't do it |
|---|---|---|---|
| `ClipOverlayProcessor` | Fetch | `_burn_platform_overlay` (~line 478) + `_burn_glitch_intro` (~line 544) | Multi-step ffmpeg orchestration — `ffprobe`-driven dimension detection, computed pixel-perfect overlay sizing, randomized freeze-frame/mosaic-color-sample/strobe intro — with hard-won gotcha-fixes (B-frame-free stream-copy concat to avoid VLC DTS-discontinuity crashes, `-threads 1` pinning to avoid silent zero-frame encodes under the pod's cgroup limit) that would be brittle to reproduce as chained `ExecuteStreamCommand` calls glued together with expression language |
| `CaptionCleanProcessor` (optional) | Process | `_clean_caption` (~line 1185) + `_build_tweet` (~line 1247) | Not a hard blocker — just an awkward chain of `ReplaceText` regexes vs. one small Python function; noted as an option, not a requirement (see Process below) |
| `XPublishProcessor` | Publish | `_publish_sync` (~line 1417) | X media upload is OAuth 1.0a-signed (`tweepy.OAuth1UserHandler` + chunked `media_upload`); `InvokeHTTP` has no OAuth1 signing support at all (OAuth2 only, via the access-token-provider controller service) |

---

### Fetch

Today: `FetchClips` PG (`InvokeHTTP POST /api/streamers/fetch-clips`) calls `fetch_clips()` (~line 940), which does everything itself — token refresh, pagination, GQL lookup, download, overlay/glitch burn, dedup, and the Kafka publish.

| Current backend function | Native replacement | Custom processor |
|---|---|---|
| `_twitch_token_refresh` / `_kick_token_refresh` (~209, ~366) | `StandardOauth2AccessTokenProvider` controller service (client-credentials grant), wired into every InvokeHTTP's "OAuth2 Access Token Provider" property. This is general NiFi capability, not a local precedent — noting that explicitly rather than misattributing it. | — |
| `_get_broadcaster_id`, `_get_clips` (~238, ~251 — pages up to 5×100 in top_mode) | `InvokeHTTP` (`GET /helix/users`, `GET /helix/clips`) + `EvaluateJsonPath`; pagination via a self-looping connection — `UpdateAttribute` increments a `cursor`/`page` attribute, `RouteOnAttribute` routes back into the same InvokeHTTP vs. downstream — a standard NiFi loop-back idiom, not custom code | — |
| `_gql_clip_mp4_url` (~318) | `InvokeHTTP` POST to `gql.twitch.tv/gql` with a templated JSON body via `ReplaceText`, then `EvaluateJsonPath` to pull `sourceURL`/`signature`/`value`, then `UpdateAttribute` expression language to assemble the signed MP4 URL (`${sourceURL}?sig=${signature}&token=${value:urlEncode()}`) | — |
| `_download_clip` (~713); Kick's `_get_kick_clips` (~408, needs browser UA/Referer headers) | `InvokeHTTP` (static header properties for UA/Referer; binary content is fine), then `PutFile` to the `/clips` PVC | — |
| `_download_hls_sync` (~1136 — Kick HLS `.m3u8` → MP4 via `ffmpeg -c copy -movflags +faststart`) | `ExecuteStreamCommand`/`ExecuteProcess` invoking ffmpeg directly — fixed-argument invocation, exactly what `files/Streamers.md`'s own draft already suggests ("DownloadClip — InvokeHTTP... or ExecuteStreamCommand with curl/wget") | — |
| `_burn_platform_overlay` (~478) + `_burn_glitch_intro` (~544) | — | `ClipOverlayProcessor` (see Custom Python Processor Strategy above — the strongest custom-processor case in Fetch) |
| `.seen_clips.json` dedup (keyed on `clip_id`) | `DetectDuplicate` + `DistributedMapCache` — demoed locally in `/home/tunas/NiFi-Templates`'s 1.x `DetectDuplicate` + `DistributedMapCache` template | — |
| `_publish_clips_to_kafka` (~1155) | Already native (`PublishKafka_2_6`) — no change | — |

Rate limiting: Twitch Helix is 800 points/minute — add `Wait`/`ControlRate` between paginated `GET /helix/clips` calls, per `files/Streamers.md`'s own anti-ban guidance ("space requests... 1-5 min intervals").

---

### Process

Move Whisper transcription and vLLM caption generation out of the Python backend into NiFi-native InvokeHTTP processors — same pattern as the existing `StreamToWhisper` and `StreamTovLLM` RAG flows. Eliminates backend HTTP timeout risk; all intermediate state is visible in NiFi as flowfile attributes. This subsection is the original Process-only plan, carried over close to verbatim since it's already reviewed and correct.

#### Why

Current `ProcessClips` PG: `ConsumeKafka → InvokeHTTP POST /process-clip → PublishKafka`

The backend's `/process-clip` does: ffmpeg WAV extract → POST whisper:8001 → POST vllm:8000 → clean caption → build tweet → return JSON. If Whisper takes 120s on a long Kick clip, NiFi's InvokeHTTP timeout fires and the clip is lost. In NiFi we can set per-step timeouts, see intermediate flowfile content, and retry individual steps.

#### New ProcessClips NiFi Flow (12 processors)

```
ConsumeKafka_2_6 (new_clips)
  group.id: StreamersProcessClips
  auto.offset.reset: earliest
  concurrentlySchedulableTaskCount: 1   ← keep at 1; Whisper is synchronous
  ↓ flowfile = JSON clip record from Kafka

EvaluateJsonPath
  Destination: flowfile-attribute
  clip_id:       $.clip_id
  source:        $.source
  streamer:      $.streamer
  title:         $.title
  clip_path:     $.clip_path
  url:           $.url
  thumbnail_url: $.thumbnail_url
  duration:      $.duration
  created_at:    $.created_at
  ↓ flowfile unchanged; attributes populated

InvokeHTTP  [GET WAV]
  HTTP Method:  GET
  Remote URL:   http://cso-operator-app.default.svc.cluster.local:8090/api/streamers/wav/${clip_id}
  Read Timeout: 90 secs
  Connection Timeout: 10 secs
  → Response relationship only (route Failure/No Retry to error log)
  ↓ flowfile = raw WAV bytes (16kHz mono)

UpdateAttribute
  filename:  ${clip_id}.wav
  mime.type: audio/wav

InvokeHTTP  [POST Whisper]
  HTTP Method:          POST
  Remote URL:           http://whisper-service.default.svc.cluster.local:8001/transcribe
  Content-Type:         ${mime.type}
  send-message-body:    true
  set-form-filename:    true
  file:                 ${filename}
  form-body-form-name:  file
  Read Timeout:         300 secs
  Connection Timeout:   10 secs
  → Response → flowfile = {"text": "transcript..."}

EvaluateJsonPath
  Destination: flowfile-attribute
  transcript: $.text
  ↓ flowfile unchanged; transcript attribute set

ReplaceText  [build vLLM request]
  Replacement Strategy: Regex Replace
  Regular Expression: (?s)(^.*$)
  Replacement Value:
    {
      "model": "Qwen/Qwen2.5-1.5B-Instruct",
      "messages": [
        {"role": "system", "content": "You are a hype gaming content creator writing tweets. Output ONLY the tweet text — no labels, no quotes around it."},
        {"role": "user", "content": "Write a punchy tweet reaction (under 200 chars) to this clip by ${streamer:escapeJson()}. React to what actually happened — quote the funniest or wildest line if it fits. Use 1-2 emojis. Keep it natural, no hashtags. Clip title: '${title:escapeJson()}'. Transcript: ${transcript:substring(0, 600):escapeJson()}"}
      ],
      "max_tokens": 120,
      "temperature": 0.85
    }
  ↓ flowfile = vLLM request JSON body

InvokeHTTP  [POST vLLM]
  HTTP Method:     POST
  Remote URL:      http://vllm-service.default.svc.cluster.local:8000/v1/chat/completions
  Content-Type:    application/json
  Read Timeout:    60 secs
  Connection Timeout: 10 secs
  → Response → flowfile = OpenAI-format JSON response

EvaluateJsonPath
  Destination: flowfile-attribute
  raw_caption: $.choices[0].message.content
  ↓ flowfile unchanged; raw_caption attribute set

ReplaceText  [build processed_clips Kafka message]
  Replacement Strategy: Regex Replace
  Regular Expression: (?s)(^.*$)
  Replacement Value:
    {"clip_id":"${clip_id}","source":"${source}","streamer":"${streamer}","title":"${title:escapeJson()}","url":"${url}","thumbnail_url":"${thumbnail_url}","duration":${duration},"created_at":"${created_at}","clip_path":"${clip_path}","transcript":"${transcript:escapeJson()}","raw_caption":"${raw_caption:escapeJson()}"}

PublishKafka_2_6  (processed_clips)
  topic: processed_clips
  bootstrap.servers: my-cluster-kafka-bootstrap.cld-streaming.svc:9092
```

#### Optional Addendum — CaptionCleanProcessor

`_clean_caption` (~line 1185) and `_build_tweet` (~line 1247) currently run at UI-read-time in `clip_queue()` (see Backend Changes Required #2 below), doing multi-step regex cleanup: strip model label prefixes, strip surrounding quotes, strip hashtags, cap emoji spam, normalize the platform/handle suffix. This is a second, optional custom-processor candidate — could be lifted into a small `CaptionCleanProcessor` (`FlowFileTransform`) inserted right after the vLLM `InvokeHTTP` step above, replacing what would otherwise be an awkward chain of `ReplaceText` regex processors. Noted as an option, not a requirement — keeping it backend-side at read-time also works fine and is simpler, since it only runs when the review UI loads the queue, not on the hot path.

#### Process Rollout Steps

1. Add `GET /wav/{clip_id}` endpoint — deploy app
2. Test endpoint manually: `curl http://localhost:8090/api/streamers/wav/<clip_id> -o test.wav`
3. Update `clip_queue()` to compute caption from `raw_caption` — deploy app
4. Update `setup-streamers-flows.py` to build new 12-processor ProcessClips PG
5. Stop current ProcessClips PG in NiFi UI
6. Run updated `setup-streamers-flows.py` to replace ProcessClips PG
7. Start new ProcessClips PG — verify flowfile attributes visible in NiFi
8. End-to-end test: fetch clips → watch NiFi → processed_clips → review UI shows transcripts + captions
9. Update `StreamersApp.json` to snapshot the new flow for future import

---

### Publish

Today: the `PublishClip` PG already uses `HandleHttpRequest`(:9001)/`HandleHttpResponse` (per `setup-streamers-flows.py`: `HandleHttpRequest(:9001) → InvokeHTTP → /api/streamers/publish → HandleHttpResponse`) — this native listener pattern is correct and should be **kept as-is**. The only thing that changes is what sits between the request and the response.

- **Keep**: `HandleHttpRequest`(:9001) / `HandleHttpResponse` — already the right shape for an ad-hoc/triggered publish, and it's also the eventual landing spot for the backend-pushes-into-NiFi direction described below (the backend already POSTs into this pattern today — see "App Backend's Role" below).
- **Replace**: the inner `InvokeHTTP → backend /api/streamers/publish` step is replaced by `XPublishProcessor`, the custom `FlowFileTransform` processor described in the Custom Python Processor Strategy table above. It takes `clip_path` + `tweet_text` (flowfile content/attributes) in and returns `tweet_id`/`url` as output attributes, lifting `_publish_sync` (~line 1417) nearly verbatim — chunked `tweepy.OAuth1UserHandler` media upload + `Client.create_tweet(media_ids=[...])`. This cuts the backend out of the posting path entirely: the backend only forwards the HTTP call in, it doesn't build or sign the tweet itself anymore.
- **Rate limiting**: X's anti-ban pacing (~2,400 posts/day, semi-hourly rolling windows, target 10-20/hour with randomized 3-6 min gaps, per `files/Streamers.md`'s own guidance) → native `Wait`/`ControlRate` processors ahead of `XPublishProcessor`, no custom code needed for the pacing itself — only the OAuth1-signed post is a custom-processor case.

---

### App Backend's Role After the Refactor

The backend keeps watch-list management and UI-triggered orchestration (Approve / Post Now / Skip / Reset) — it does not go away. What changes is that it stops doing the Twitch/ffmpeg/Whisper/vLLM/tweepy work itself. Instead it loops over data (e.g. iterating the watch list on a timer, or reacting to a UI button click) and POSTs into NiFi's own `HandleHttpRequest`/`ListenHTTP` listeners to queue work into the appropriate flow, the same way `/home/tunas/DesktopShare/files/midi_melody2.py` loops over a melody and `requests.post()`s each note into a MiNiFi `HandleHttpRequest`/`ListenHTTP` endpoint (`http://localhost:9998/contentListener`) rather than doing anything with the note itself. Concretely:

- **Fetch trigger**: instead of `fetch_clips()` reaching out to Twitch/Kick directly, the backend loops the watch list and POSTs `{login, source}` into a new `HandleHttpRequest` listener on the `FetchClips` PG, one call per streamer — NiFi's native/custom processors do the actual API calls, download, and overlay burn from there.
- **Process trigger**: unchanged in shape — already Kafka-driven (`ConsumeKafka` on `new_clips`), no backend involvement either before or after this refactor.
- **Publish trigger**: unchanged in shape — the backend already POSTs into `HandleHttpRequest`(:9001) for Post Now / cron-driven publish today; after the refactor it's still the backend doing the POST, just landing on `XPublishProcessor` instead of an `InvokeHTTP`-to-backend hop.

---

### Backend Changes Required

**Process leg** (unchanged from the original plan — still required regardless of Fetch/Publish timing):

##### 1. Add `GET /api/streamers/wav/{clip_id}` (router + service)

New endpoint in `routers/streamers.py`:
```python
@router.get("/wav/{clip_id}")
async def serve_wav(clip_id: str):
    """Extract 16kHz mono WAV from MP4. Called by NiFi ProcessClips GET WAV step."""
    if not re.match(r'^[A-Za-z0-9_\-]+$', clip_id):
        raise HTTPException(status_code=400, detail="Invalid clip_id")
    mp4_path = Path(settings.CLIP_STORAGE_PATH) / f"{clip_id}.mp4"
    if not mp4_path.exists():
        raise HTTPException(status_code=404, detail="Clip not found")
    wav_path = Path(settings.CLIP_STORAGE_PATH) / f"{clip_id}.wav"
    import asyncio, subprocess
    proc = await asyncio.to_thread(
        subprocess.run,
        ["ffmpeg", "-y", "-i", str(mp4_path), "-vn", "-ac", "1", "-ar", "16000", str(wav_path)],
        capture_output=True, timeout=60,
    )
    if proc.returncode != 0 or not wav_path.exists():
        raise HTTPException(status_code=500, detail="ffmpeg WAV extraction failed")
    return FileResponse(str(wav_path), media_type="audio/wav")
```

WAV files accumulate alongside MP4s in `/clips/`. Add `*.wav` to reset cleanup in `reset_kafka()`.

##### 2. Update `clip_queue()` in `services/streamers.py`

Kafka messages now store `raw_caption` (not final tweet text). Apply `_clean_caption` + `_build_tweet` at queue-read time so the catalog and suffix format are always fresh:

```python
# Inside the per-message loop in clip_queue():
raw = record.get("raw_caption")
if raw and not raw.startswith("["):
    x_handle = get_x_handle(record.get("streamer", ""))
    record["caption"] = _build_tweet(
        _clean_caption(raw),
        record.get("source", "twitch"),
        record.get("streamer", ""),
        x_handle,
    )
# Fall through: old records with pre-built "caption" field are used as-is
```

##### 3. Keep `POST /api/streamers/process-clip`

Endpoint stays for manual/debug use. NiFi will no longer call it once the new ProcessClips PG is live.

##### 4. Kafka reset — wipe WAV files

In `reset_kafka()`, add WAV cleanup alongside MP4:
```python
for wav in glob.glob(str(storage / "*.wav")):
    Path(wav).unlink(missing_ok=True)
```

**Fetch/Publish legs** — mostly *removal*, not addition. Once native/custom NiFi processors own the work:

- `fetch_clips()`, `_twitch_token_refresh`/`_kick_token_refresh`, `_get_broadcaster_id`/`_get_clips`, `_gql_clip_mp4_url`, `_download_clip`, `_get_kick_clips`, `_download_hls_sync`, `_burn_platform_overlay`/`_burn_glitch_intro`, and the `.seen_clips.json` dedup logic can all be deleted from `services/streamers.py` — that logic now lives in the `FetchClips` PG (native processors + `ClipOverlayProcessor`).
- `_publish_sync` can be deleted once `XPublishProcessor` is live; `publish_clip()`/`publish_next()` shrink to thin wrappers that just POST into `HandleHttpRequest`(:9001) instead of calling tweepy directly.
- New small pieces needed for the backend-pushes-into-NiFi direction: a `HandleHttpRequest` listener added to the `FetchClips` PG (new — Fetch doesn't have one today, since Fetch is Kafka-consumer-free and currently only entered via `InvokeHTTP` from NiFi's own timer-driven PG), and a small backend loop (replacing `fetch_clips()`'s body) that walks the watch list and POSTs each `{login, source}` pair into it.

---

### Rollout Sequencing

Recommended order: **Publish → Process → Fetch**.

1. **Publish first** — smallest scope, highest value-per-effort. The `HandleHttpRequest`(:9001)/`HandleHttpResponse` skeleton already exists and doesn't change; only one custom processor (`XPublishProcessor`) needs to be built and swapped in for the inner `InvokeHTTP`. Low design risk, immediate payoff (removes the OAuth1 tweepy dependency from the backend's request path).
2. **Process second** — already fully planned and reviewed (see Process subsection above) — lowest new-design risk of the three, since the flow and backend changes are already spelled out precisely.
3. **Fetch last** — the most complex leg: multiple native-loop patterns (pagination, dedup) plus the highest-risk custom processor in the whole plan (`ClipOverlayProcessor`, carrying the ffmpeg overlay/glitch-intro gotcha-fixes). Doing this last means the custom-processor deployment pattern (hatch build → hostPath volume → NiFi Python listener restart) is already proven out by `XPublishProcessor` and (optionally) `CaptionCleanProcessor` before attempting the riskiest lift.

---

### Key Gotchas

| Risk | Mitigation |
|---|---|
| Whisper server still synchronous (no semaphore) | Keep ConsumeKafka concurrentlySchedulableTaskCount=1 |
| WAV file left on disk if NiFi crashes mid-flow | Reset button now also wipes *.wav |
| Old processed_clips records have `caption` not `raw_caption` | clip_queue() falls back to raw `caption` field for old records |
| InvokeHTTP WAV URL uses EL `${clip_id}` — must set Dynamic Property disabled | clip_id comes from EvaluateJsonPath attribute, use it directly in URL field |
| Return Timestamps must be True in Whisper for clips >30s | Already set in Whisper ConfigMap — no change needed |
| Custom Python processor changes require a full rebuild/redeploy cycle, not a simple app redeploy | `hatch build` → copy output onto the `/extensions` hostPath (or `custom-nars` PVC via the `nar-loader.yaml` pattern) → restart NiFi's Python process (`NIFI_PYTHON_LISTENER_STARTUP_TIMEOUT` gives it up to 600s to reload) — budget for this, it's slower than `kubectl rollout restart` on the app |
| OAuth1 signing has no native NiFi equivalent | Must stay in `XPublishProcessor` — don't attempt to hand-roll OAuth1 HMAC-SHA1 signing in expression language |
| ffmpeg thread-pinning and B-frame gotchas already fixed in `_burn_platform_overlay`/`_burn_glitch_intro` | Preserve verbatim when lifting into `ClipOverlayProcessor` — don't rewrite the ffmpeg calls from scratch; re-deriving `-threads 1`/`-bf 0` from first principles is exactly how these bugs got reintroduced before |
| Reversed integration direction means the backend and NiFi must agree on listener contracts | Version/document each `HandleHttpRequest` payload shape (Fetch's new listener, Publish's existing one) in `setup-streamers-flows.py` comments so backend and flow don't drift independently |

---

## Untitled Videos / Video Title, Description, CTA, Category — PUNTED (session 12)

X Media Studio shows every published clip as "Untitled" and has a per-video Settings panel (Title, Description, Category, Call-to-action, embed/download toggles, content restrictions) that our pipeline doesn't touch. Investigated setting these programmatically — punted for now. Findings, so this isn't re-investigated from scratch:

- **Not settable via the standard/organic X API** (`POST /2/media/metadata`, `POST /2/tweets`) — confirmed no `title`/`description`/`category`/CTA params exist there. This part of Session 10's original conclusion was right, just for a more specific reason than first assumed.
- **Is settable via the X Ads API** — `POST accounts/:account_id/tweet` accepts `video_id`, `video_title`, `video_description`, `video_cta`, `video_cta_value`. Separately, `media_library` (`POST`/`PUT accounts/:account_id/media_library[/:media_key]`) accepts `title`, `description`, `name`, `file_name`, `poster_media_key` — no CTA/category field there. "Ads API" is just the name of that API surface — using it does not require spending money on a promoted/paid tweet.
- **`video_cta` confirmed values**: `GO_TO`, `SEE_MORE`, `SHOP`, `VISIT_SITE`, `WATCH_NOW` (from preroll-ad CTA docs). **Unconfirmed**: whether a "Follow @handle" CTA exists at all — the documented CTAs look link-style (site/app/shop), not account-follow. May require a different creative type, or may not be supported for this use case.
- **Category** (Esports & Video Games, Comedy, etc. — see Media Studio Settings modal): not found on any documented `media_library` or tweet-creation param. Unclear if it's UI-only or lives somewhere undocumented (possibly tied to `curated_categories`/targeting rather than a per-video tag).
- **Blocking prerequisite**: none of this can be built or even empirically verified without an X Ads account tied to @TunaStreetTest. Checked `~/.env` — zero ads-related credentials or account_id configured. This is the actual blocker, not the API design.

**To resume this**: get an Ads account (unfunded/$0 is fine) set up for @TunaStreetTest first, get an `account_id`, then the CTA/category questions can be answered empirically against the live API instead of guessing from docs.

**Separate, unblocked idea from the same investigation — subtitles**: `POST /2/media/subtitles` (v2, standard API, no Ads account needed) can attach an `.srt` to an already-uploaded video, using the same OAuth1 creds already in use (confirmed `tweepy.Client.create_tweet` already signs v2 calls with our existing OAuth1 creds — no new auth setup needed). Blocker there is smaller: the Whisper ConfigMap (`whisper-server-code`) already computes per-segment timestamps (`return_timestamps=True` is set) but the server only returns `result["text"]`, discarding `result["chunks"]` needed to build a valid SRT. Not built yet — deprioritized alongside the title/CTA work, but not blocked on anything external.

---

## Post Now — Immediate Single-Clip Publish (UI + Telegram)

Two distinct fast paths, both skip a wait — but they target two different queues:

- **UI Post Now** — publish *the specific clip you're looking at* in the Clip Review Queue, before it's even been Approved. Bypasses Approve → pending-queue entirely. Reuses the existing direct-publish endpoint — `POST /api/streamers/publish` (`services.publish_clip()`) — which posts via tweepy and calls `mark_published(clip_id)` on success, so it's excluded from the normal Approve/rotation flow afterward (no double-post).
- **Telegram Post Now** — publish *the next already-approved clip sitting in the pending-publish queue*, right now, instead of waiting for a NiFi timer (`PublishClip` backup, 1/day, or `PublishClipPeakTimeCron`, 3pm-9pm EDT) to drain it. Reuses the existing rotation-pop endpoint — `POST /api/streamers/publish-next` (`services.publish_next()`) — same call the cron timers make, just triggered on demand. **Corrected mid-session**: first draft had this hitting the Review queue (`/api/streamers/queue` + `/publish`) like the UI button — wrong target; the Telegram command is meant to drain the *pending* backlog (there were 49 real approved clips sitting there waiting), not jump the Review queue.

Neither path needed a new backend endpoint — both reuse existing ones.

- **UI**: every card in the Clip Review Queue has a `Post Now` button next to `Approve`/`Skip` (`ClipCard` in `frontend/src/components/StreamersPage.tsx`). Calls `api.streamersPublish(clip_path, tweet_text, clip_id, title)` with that card's own clip/caption, shows the returned tweet URL inline, and dismisses the card on success.
- **Telegram**: `agent-PostNow.sh` (DesktopShare `files/`) — `POST /api/streamers/publish-next`, replies to the Telegram chat with the resulting X URL + remaining queue depth, or the "pending queue is empty" / error case. Modeled on `agent-minikube-reset.sh`'s env-check → do the thing → curl a reply back to Telegram pattern. Verified live end-to-end (session 14): posted one real clip off the 49-deep pending queue, confirmed `queue_remaining` ticked down and the Telegram reply landed correctly.
- **No new NiFi PG.** Post Now is an ad-hoc trigger, not a scheduled/polled action, so it doesn't need one to work. We're planning a larger redo later that moves fetch/process/post logic natively into NiFi processors (see NiFi-Native Refactor Plan below) instead of NiFi being a thin caller into FastAPI — Post Now is a candidate to fold into that redo rather than getting its own throwaway interim PG now.

---

## Session History

### Session 14 (2026-07-03)

| Change | Details |
|---|---|
| **Post Now shipped — UI button + Telegram script** | Two fast paths added, each targeting a different queue (see "Post Now" section above for the final split). Reused existing endpoints as-is — no backend changes for either. Added a `Post Now` button to every `ClipCard` in the Review Queue (`StreamersPage.tsx`) and a new `agent-PostNow.sh` Telegram script |
| **Design correction #1, mid-session** | First pass mistakenly modeled Post Now on `/publish-next` (pop the pending FIFO queue) for both UI and Telegram. Corrected: UI Post Now publishes *the specific clip you're on* in the Review queue via `/publish`, not whatever's been Approved into the pending queue |
| **Design correction #2, later in session** | Telegram script had then been pointed at the Review queue (top of `/queue` → `/publish`) to match the UI. Corrected again: Telegram Post Now should drain the *pending, already-approved* queue instead — there were 49 real approved clips waiting — so `agent-PostNow.sh` now calls `/publish-next` (same endpoint the cron timers use), while the UI button stays on `/publish` against the Review queue. Two different queues, two different endpoints, by design |
| **No new NiFi PG this session** | Considered adding a stopped placeholder `PostNow` PG for parity with FetchClips/ProcessClips/PublishClip, but skipped — Post Now is ad-hoc, not scheduled, so it doesn't need one, and a bigger future redo will move fetch/process/post logic natively into NiFi processors anyway (see NiFi-Native Refactor Plan). Not worth building throwaway interim infra for |
| Live-tested end-to-end | Ran `agent-PostNow.sh` against the live app/cluster twice: first version posted the one real clip sitting in the Review queue (confirmed drained, no reappearance in Pending Publish); corrected version posted one real clip off the 49-deep pending queue (confirmed `queue_remaining` ticked down) |
| New future idea logged | **Reply Guy** — auto-reply to a posted clip's tweet with (1) a link to the streamer's own channel page and (2) the clip's transcript — see "What's Next" above |
| **NiFi-Native Refactor Plan expanded to Fetch + Process + Publish** | Prior plan only covered Process (Whisper/vLLM via InvokeHTTP chaining). Expanded to all three legs per direction from the repo owner (a NiFi person) — real pipeline logic should live in NiFi, backend becomes an orchestrator that loops and queues work into NiFi rather than NiFi calling back into the backend. Identified two hard custom-Python-processor cases grounded in real local precedent (`nifi-custom-processors`' `nifiapi.flowfilesource`/`FlowFileTransform` pattern, `hatch build` → hostPath `/extensions` deployment): `ClipOverlayProcessor` (Fetch — ffmpeg overlay/glitch-intro orchestration) and `XPublishProcessor` (Publish — OAuth1-signed chunked X media upload, which `InvokeHTTP` can't do natively). Everything else mapped to native processors (`StandardOauth2AccessTokenProvider`, `InvokeHTTP`/`EvaluateJsonPath` chains, loop-back pagination, `ExecuteStreamCommand` for ffmpeg remux, `DetectDuplicate` for dedup, `Wait`/`ControlRate` for rate limiting). Recommended rollout order: Publish → Process → Fetch (smallest/highest-value first, riskiest custom processor last). See "NiFi-Native Refactor Plan" section above |
| **Pending Publish panel enriched + per-row Post Now** | `PendingPanel` was clip_id + truncated tweet text only. `approve_clip()`/`PublishRequest` now carry `source`/`streamer`/`url`/`thumbnail_url`/`x_handle` through from the Review card into `.pending_publish.json`, so each pending row now shows thumbnail, platform badge, streamer/X links, and title-linked-to-clip-URL, matching the Review card's layout. Added a per-row `Post Now` button — new `POST /api/streamers/pending/{clip_id}/publish-now` → `services.publish_pending(clip_id)`, which removes that specific `clip_id` from wherever it sits in the pending list (same pattern `cancel_pending` already used) and publishes it immediately, restoring it to the front of the queue on failure (same safety net as `publish_next`) |
| **Confirmed: out-of-order pending publish is safe** | The pending queue is a flat JSON file (`.pending_publish.json`), not Kafka — Kafka's `processed_clips` topic is only read by the Review tab, which already filters by clip_id membership in the pending/skipped/published sets at read time. Publishing a specific pending clip out of order just removes that one entry from the list wherever it sits; the relative order of the remaining clips (and the normal cron rotation popping index 0) is unaffected |
| `PublishClipPeakTimeCron` renamed/re-tuned | `Peak Time 3-9pm` (`0 0/18 19-23,0-1 * * ?`, an EDT-converted wraparound window) → `Peak Time 4-11pm` (`0 0/9 16-23 * * ?`) — wider single-range window, tighter interval (18min → 9min), defined directly in UTC hours instead of converted from EDT, sidestepping the earlier DST-shift concern |

### Session 13 (2026-07-02)

| Change | Details |
|---|---|
| **PublishClipPeakTimeCron fired early — pod is UTC, not EST** | Cron `15-21` was written assuming pod-local time = EST, but `mynifi-0`'s clock is UTC (confirmed via `kubectl exec ... date`). Actual window was 11am-5pm EDT. Corrected the `Peak Time 3-9pm` GenerateFlowFile cron to `0 0/18 19-23,0-1 * * ?` (UTC-equivalent of 3pm-9pm EDT) — **applied via NiFi UI, not yet re-exported to `StreamersApp_PeakTime_Cron.json`**. Needs revisiting at DST changeover (November) or a `TZ=America/New_York` fix on the statefulset. See "PublishClipPeakTimeCron" section above |
| **`publish-next` 502 — Twitch clip exceeded X's 2-min post limit** | Live `InvokeHTTP` log showed `502` wrapping X's real error: `403 — This user is not allowed to post a video longer than 2 minutes`. Root cause: `_get_clips` (Twitch fetch, `services/streamers.py`) only enforced a lower duration bound (`>= 45`) with no upper bound, unlike Kick's `45 <= duration <= 90`. A long clip slipped through fetch → review → approve → publish and got rejected at post time. Capped Twitch fetch to `45 <= duration <= 100`, matching Kick's pattern. Fixed, rebuilt, redeployed, rollout confirmed settled |
| **`publish_next()` silently dropped clips on publish failure** | Found while fixing the above: `publish_next()` popped the clip off `.pending_publish.json` *before* attempting the X post; when the post raised (as with the oversized clip), the clip was gone from the queue with no record and no retry. Fixed to push the clip back to the front of the queue on any publish exception, so a stuck/bad clip stays visible in `/pending` and can be cancelled via the review UI instead of vanishing silently. Deployed alongside the duration-cap fix |
| New Kick streamer: ac7ionman | Added `ac7ionman` to `_KICK_LOGINS` and `_STREAMER_CATALOG` (`"ac7ionman": "Ac7ionMann"`) in `services/streamers.py` |
| n3on X handle updated | `_STREAMER_CATALOG["n3on"]` corrected `@N3on` → `@n3ononyt` |

### Session 12 (2026-07-02)

| Change | Details |
|---|---|
| **PublishClipPeakTimeCron PG added** | New cron-driven PG publishes pending-approved clips during peak hours (3pm-9pm EST) instead of a fixed idle-interval GenerateFlowFile. `Peak Time 3-9pm` GenerateFlowFile: `CRON_DRIVEN`, `0 0/18 15-21 * * ?` (every 18 min, hours 15-21) → `InvokeHTTP POST /api/streamers/publish-next`, the same endpoint the original `PublishClip` PG calls. No backend changes needed. Original `PublishClip`'s `Publish On Demand` GenerateFlowFile throttled to `1 day`, demoting it to manual/backup. Flow exported to `StreamersApp_PeakTime_Cron.json`; not yet folded into the committed `streamers/StreamersApp.json` snapshot |
| **Future item logged: Live Streamer Alert** | When a watched streamer goes live, ramp up clip activity for them and possibly post an X "live now" alert. Scoped as NiFi-native, likely needs a custom Python processor for live-status polling + flow branching. Not designed yet — see "What's Next" |
| **Untitled video investigation — punted** | Chased title/description/CTA/category settability across the organic API, Ads API `media_library`, and Ads API tweet-creation endpoint. Confirmed it's only settable via the Ads API, but we have zero Ads account credentials configured — punted until an Ads account exists for @TunaStreetTest. See "Untitled Videos" section above. Surfaced a separate, unblocked opportunity: subtitles via `/2/media/subtitles` using our existing Whisper transcript + OAuth1 creds |

### Session 11 (2026-07-01)

| Change | Details |
|---|---|
| Service port 8000 → 8090 | `k8s/service.yaml` LoadBalancer `port` changed from `8000` to `8090` (`targetPort` stays `8000` — only the Service-facing port moved). App tunnel URL is now `http://127.0.0.1:8090`, and the cluster-internal DNS address used by NiFi's InvokeHTTP processors is now `cso-operator-app.default.svc.cluster.local:8090` |
| **Gotcha:** publish timed out after the port move | The service.yaml port change had already been applied live once before (repo file had drifted, just committed to match), but the NiFi ProcessClips/PublishClip flows still pointed InvokeHTTP at the old `:8000` internal address — so calls from NiFi to the app (WAV fetch, publish-next) failed/timed out until the flow's Remote URL was updated to `:8090` to match the Service's new port |
| Twitch top-mode clip pagination fix | `_get_clips` only fetched a single page (`first=20`, no cursor) even in top_mode, so "top clips" really meant "highest-viewed among the ~20 most recent" — Helix returns clips in recency order, not by views. Now pages up to 5×100 when `top_mode=True` before ranking by `view_count` |
| **Reverted Session 10's video-title MP4 stamping — wrong assumption** | Session 10 added `_stamp_video_title` (ffmpeg `-c copy` remux embedding the clip's title into the MP4 container's `title` tag) to fix clips showing "Untitled" in X Analytics. Verified live: the freshest published clip had a confirmed correct `title` tag in the container, but X Analytics still showed Untitled. Root cause — X's organic tweet flow (`media/upload` chunked + v2 `create_tweet`, what this bot uses) has **no title field at all**. `video_title`/`video_description` only exist on the X **Ads API**'s Promoted/Amplify tweet-creation endpoint (`POST accounts/:account_id/tweet`), which requires an Ads account — container metadata is never read for a standard organic video tweet. Removed `_stamp_video_title`/`_video_title_for`/`_is_junk_title` — it was a no-op ffmpeg pass on every publish with zero effect on Analytics. **Untitled is an unavoidable characteristic of organic (non-Ads) video tweets** unless the bot is rearchitected to post through the Ads API |

### Session 10 (2026-07-01)

| Change | Details |
|---|---|
| New streamers added to catalog + doc | chickenandy (@ChickenAndy_, Kick), Asmongold (@asmongold, Kick), MrBeast (@mrbeast, Kick), Clavicular (@Clavicular0, Kick), Kai Cenat (@KaiCenat, Twitch) — added to `_TWITCH_LOGINS`/`_KICK_LOGINS`/`_STREAMER_CATALOG` in `services/streamers.py` and to `streamers.md` |
| Reginald / DGDecor removed | Both had no known X handle; policy going forward is no streamer without a known X handle. They were already absent from code, only present in the doc — doc now matches code |
| Watch List "Rotate" button | `POST /api/streamers/watchlist/rotate` + `rotate_watchlist()` swaps in 2 fresh Twitch + 2 fresh Kick streamers not already on the list. Takes effect on the next FetchClips stop/start (NiFi reads the watch list once at flow start) |
| Fetch mode label clarified | "Fetch mode:" → "Twitch Fetch Mode:" in the Watch List card — Kick has no real time-windowed "Top Clips" API (only `sort=date`, no view-count sort or window), so the toggle only meaningfully applies to Twitch |
| Fixed "Untitled" on X Analytics | X's media analytics reads the MP4 container's own title tag, not the tweet text — clips uploaded without one always showed "Untitled". `_stamp_video_title()` now does a cheap `-c copy` remux to embed a title before upload: the source clip's own title if it passes a junk filter (`_is_junk_title`), else the vLLM-generated caption body. Threaded through Approve → pending queue → publish-next → `_publish_sync` |
| **Glitch intro effect** (new clips only) | `_burn_glitch_intro()` prepends a freeze-frame → color-mosaic fade+strobe → hard-snap intro to every freshly fetched clip, called right after `_burn_platform_overlay()` inside the `if not dest.exists()` branch in both `_fetch_twitch_clips` and `_fetch_kick_clips` — so it only ever touches brand-new downloads, never clips already sitting in `/clips/`. Sequence: ~1s frozen first frame → crossfade *directly* into a flickering strobe of mosaic-color variants (fade and flash happen concurrently, not fade-then-strobe) → instant hard cut into the real clip, no fade out. The platform overlay bar (already burned in) is cropped out, held perfectly crisp the whole time, and stacked back on top — only the footage below it animates. Mosaic colors are sampled from the clip's own first frame. Hold/fade duration and which mosaic variants get used are randomized per clip so consecutive intros don't look identical |
| **Gotcha:** B-frames break stream-copy concat | Every intro segment must be encoded with `-bf 0` (no B-frames). A version using default B-frames produced a file ffmpeg itself decoded fine (just a "Non-monotonic DTS" warning) but crashed VLC on playback — stream-copy concatenating independently-encoded B-frame segments creates DTS discontinuities at each splice that VLC's demuxer doesn't tolerate |
| **Gotcha:** bar-height detection needs a real signal | Clips predate the platform overlay (1080p, no bar) vs. post-overlay clips (1240p, 160px bar) look almost the same height-wise under a naive ratio guess — a formula-based estimate incorrectly detected a phantom bar on a bar-less 1080p clip. Fixed by using the exact `_burn_platform_overlay` return value (bar height in pixels, 0 if none) instead of re-deriving it after the fact |
| **PublishClip ordering/race bug fixed** | `approve_clip`/`publish_next`/`cancel_pending` all did an unlocked read-modify-write on `.pending_publish.json`. Two near-simultaneous approvals (or an approval racing a slow `publish_next`, e.g. from NiFi's GenerateFlowFile timer overlapping a previous InvokeHTTP call) could each read the same list and overwrite each other's write, silently dropping an approved clip or letting one get published twice — symptom: newer clips appearing to jump ahead of older un-published ones. Fixed with the same `fcntl.flock` pattern already used for `_overlay_lock` — pop-and-save now happens atomically, and the slow X upload itself still runs outside the lock so it doesn't block new approvals |
| Watch List moved under Pipeline Status | Reordered `StreamersPage.tsx` sections — was last (after Pending Publish), now Section 2 |
| Health bar is module-aware | `/api/health` only pings services owned by an active `MODULES` flag (vllm/nifi/kafka for rag+streamers, qdrant/embedding for rag, whisper for streamers, efm only if the efm module is active) instead of unconditionally probing all 7, including EFM when it isn't even deployed. Frontend `HealthBar` only renders dots for keys the backend actually returns |
| **Gotcha:** configmap `MODULES` was stale | `k8s/configmap.yaml` hardcoded `MODULES: "efm,rag,streamers"` — out of sync with the actual `rag,streamers` standard deploy. This is the backend's *runtime* env var (via `configMapRef`), completely separate from the Docker `--build-arg MODULES` that only bakes `VITE_MODULES` into the frontend bundle. Frontend correctly hid the EFM tab while the backend kept pinging a nonexistent EFM service and reporting `ok: false` forever. Fixed the configmap value to `"rag,streamers"` |
| Clips-per-streamer cap tightened for 4+ streamers | `_clips_per_streamer_cap()` gained a 4th tier: 1 clip/streamer once the watch list has 4+ entries (was 2/streamer, so a 4-streamer list — e.g. right after Rotate — pulled up to 8 clips/run). Now caps at 4 clips/run for any watch list of 4 or more |
| **Gotcha:** glitch intro silently no-op'd in the pod — libx264 thread oversubscription | First real fetch after deploying the glitch intro showed clips with the platform bar but no intro, and pod logs had zero errors. Root cause: every ffmpeg encode in `_burn_glitch_intro` let libx264 auto-detect thread count from the *host's* CPU count (seen: `threads=24`) instead of the pod's 1-CPU cgroup limit — unlike `_burn_platform_overlay`, which already pins `-threads 1`. Under real cgroup constraints this produced a silent zero-frame encode (exits with a real non-zero returncode, not a timeout, so no exception either) — reproduced directly inside the pod via `kubectl exec`, confirmed fixed by adding `-threads 1` + `x264opts threads=1:sliced-threads=0` to every libx264 call. Also added failure logging (`print` of the failing command + stderr tail) since `_burn_glitch_intro` previously swallowed every error with zero visibility |
| Backlog of ~20 pre-fix clips batch-patched in place | Clips fetched before the thread-pinning fix (both in the review queue and already-approved in the pending-publish queue) had the overlay bar but no glitch intro. Rather than re-fetch, ran `_burn_glitch_intro` directly against each existing file in `/clips/` via a one-off `kubectl exec` script (bar height re-derived per clip by inverting the `orig_h + round(orig_h*0.1481/2)*2 == total_h` formula since the original pre-overlay height isn't stored) — no code change needed, just applying the now-fixed function to already-downloaded files |

### Session 9 (2026-06-30)

| Change | Details |
|---|---|
| ExtraEmily handle typo fixed | `_STREAMER_CATALOG["extraemily"]` and `streamers.md` corrected `@ExtraEmily` → `@ExtraEmilyy` |
| Clip cap scales with watch list size | 1 streamer → 5 clips/run, 2 → 3, 3+ → unchanged at 2. Added `_clips_per_streamer_cap()` |
| Tab order changed | Streamers, RAG, Operator (was Operator, EFM, RAG, Streamers). First tab is now the default landing view |
| Pending Publish panel added | New `GET /api/streamers/pending` + `POST /api/streamers/pending/{clip_id}/cancel`; frontend card shows the X-publish queue with per-clip cancel |
| Platform logo overlay on clips | Burns a bar with the Kick/Twitch logo + `PLATFORM.COM/HANDLE` above each fetched clip. Rejected a frontend-only badge (looked wrong, made videos look "weird") and a compositing overlay (covered footage) in favor of extending the canvas via ffmpeg `pad` — original footage is fully preserved below the bar, output is simply taller (1080p → 1240p) |
| Logo assets | User-supplied Kick/Twitch logo images pre-cropped + colorkeyed to transparent PNGs at `backend/assets/logos/{kick,twitch}.png`; `DejaVuSans-Bold.ttf` bundled at `backend/assets/fonts/` for the handle text (avoids relying on fonts being present in the slim Python image) |
| **Gotcha:** `scale2ref` silently breaks tiny images | Used to scale the logo relative to the main video's height; collapsed the 151x51 Twitch logo down to ~9x5px instead of scaling up, making it invisible. Fixed by `ffprobe`-ing the clip's real dimensions up front and computing all overlay sizes as literal pixel values instead |
| **Gotcha:** `ultrafast` preset bloats files 5-7x | First batch used `-preset ultrafast -tune zerolatency -bf 0` to minimize ffmpeg memory/CPU (see below) — but that setting produces much bigger output for the same CRF. Clips went from ~50-100MB to 130-230MB, which is almost certainly why NiFi's `PublishClip` InvokeHTTP started timing out on the X upload. Switched to `-preset veryfast` with B-frames re-enabled — files came back down near original size (~44-63MB) at the cost of ~2-3x slower encode (45s → ~90-120s/clip) |
| **Gotcha:** in-memory semaphore doesn't protect across processes | First serialized ffmpeg overlay burns with a `threading.Semaphore(1)` — this only guards one Python process. A standalone reprocessing script (its own process) ran concurrently with the live app's own fetch pipeline, and two ffmpeg encodes at once pegged the pod's 1 CPU / 1Gi limits and nearly OOM-killed it. Replaced with an `fcntl.flock` on a shared `/tmp` lock file, which correctly serializes across every process in the pod |
| **Gotcha:** NiFi client timeout ≠ backend failure | `PublishClip`'s InvokeHTTP gave up waiting on a slow (bloated-file) upload and reported "timeout" to the user, but the FastAPI backend kept running server-side and completed the tweepy upload successfully anyway — confirmed via `.published.json`. Don't assume a NiFi-reported timeout means the underlying action failed; check backend state first |
| Recovered already-bloated pending clips | Since `pad` never touches pixels below the bar, wrote a one-off script to crop the old bar off + re-apply the new (smaller) overlay in one pass for clips already bloated by the `ultrafast` run, instead of re-fetching from Kick/Twitch. Stopped partway through at user's direction — accepted that already-queued bloated clips still publish successfully (just slowly), and only bothered fixing ones not yet in flight |
| Resumable batch pattern | Reprocessing scripts persist per-clip status to a JSON state file in `/clips/`, so a killed/interrupted run resumes without redoing finished clips or double-stamping |

### Session 8 (2026-06-30)

| Change | Details |
|---|---|
| Fetch mode toggle | Watch List card has `Recent \| Top Clips` toggle + period selector (`1 Month \| All Time`). Mode persisted to `/clips/.fetch_mode.json` — survives pod restarts |
| Twitch top clips | Top mode sets `started_at` to 30 days ago (month) or omits it (all time); sorts by `view_count` instead of duration. Pulled many high-view historical clips successfully |
| Kick top clips | Kick channel endpoint only accepts `sort=date` — 422 on any other sort value. No time window support. Top mode fetches 20 most recent and sorts by `view_count` client-side |
| Kick wrong-channel bug fixed | Global `kick.com/api/v2/clips?channel=slug` param is ignored server-side — was returning random global clips. Switched to `kick.com/api/v2/channels/{slug}/clips` (channel-specific endpoint). Added client-side `channel.slug` validation as safety net |
| Clip card links + metadata | Title links to clip URL on platform; streamer name links to Twitch/Kick profile; `@x_handle` links to X. View count and created date shown inline |
| x_handle in queue response | `get_x_handle()` called at queue-read time in `clip_queue()`; injected into each clip dict returned to frontend |
| Commentary textarea removed | Caption field is the only editable field — commentary box removed. Caption textarea taller (rows=4) |
| Approve message cleaned | Removed "~2 min" time estimate from post-approve confirmation |
| X multi-account plan | Documented OAuth 1.0a dance to post to real account via app registered under @TunaStreetTest — see "Posting to a Real X Account" section |
| GPU optimization plan | New `gpu-optimization-plan.md` — VRAM analysis for RTX 4060 8GB, three options for running 5B model alongside Whisper, open questions before acting |
| Full Kafka reset | Wiped 76 stale clips + both topics after Kick bug discovered — fresh start with correct channel filtering |

### Session 6 (2026-06-29)

| Change | Details |
|---|---|
| Kick.com clip support | `kick:slug` prefix in watch list routes to Kick; bare names stay Twitch. `kick.com/api/v2/clips` with browser headers fetches clips |
| Kick HLS download | ffmpeg `-c copy -movflags +faststart` remuxes HLS `.m3u8` to MP4 in seconds |
| WAV pre-extraction for Whisper | ffmpeg extracts 16kHz mono WAV before Whisper upload — fixes transcription for both Kick and Twitch |
| Platform badge in review queue | TWITCH/KICK badge always shown next to streamer name; defaults to twitch for old clips |
| Platform badge in Kafka Topics panel | `src` column added to topic record table |
| Platform-aware watch list UI | Twitch/Kick toggle + auto-prefixes `kick:` when adding; pills show platform badge |
| Caption always names platform | vLLM prompt requires "Twitch" or "Kick" in every generated caption |
| Clips per run 5 → 2 | Reduces fetch time and NiFi timeout risk |
| Parallel streamer fetch | All streamers fetched concurrently via `asyncio.gather` |
| Seen-set race condition fix | Clip marked seen before download so concurrent streamers skip duplicates |
| ffmpeg added to app Dockerfile | Required for HLS remux and WAV extraction in the app container |

### Session 5 (2026-06-29)

| Change | Details |
|---|---|
| Approve → queue | Approve button now instant — adds to `.pending_publish.json`, returns `Queued #N`. NiFi PublishClip flow changed to `GenerateFlowFile (120s) → InvokeHTTP POST /api/streamers/publish-next` to rate-limit X posts |
| `/approve` + `/publish-next` endpoints | Approve queues to `.pending_publish.json`; publish-next pops one and calls tweepy. `/publish` kept for direct/debug use |
| Hashtag normalizer | `_clean_caption()` now normalizes `#ALL_CAPS` → `#TitleCase` and `#WORD_UNDERSCORE` → `#WordUnderscore` |
| Caption label fix | System message tells vLLM output-only; `_clean_caption()` strips `**Label:**` prefix and surrounding quotes as fallback |
| All polls slowed + visibility pause | HealthBar 30s→60s, Operators 15s→60s, PodSummary 5s→30s, NifiControls 4s→30s. All now pause when browser tab is hidden |
| HealthBar operators call removed | HealthBar was calling `k8sOperators()` every tick on every tab just for the Flink dot — removed. Operators component (Operator tab only) already covers it |
| NiFi URL for internal calls | Always `http://cso-operator-app.default.svc.cluster.local:8090/api/...` — not NodePort 30090 |

### Session 4 (2026-06-29)

| Change | Details |
|---|---|
| Clips per streamer 2 → 5 | `fetch_clips` cap raised — fetch pool is 20 clips (≥45s, longest-first) |
| Deploy without EFM tab | `make deploy MODULES=rag,streamers` omits EFM from frontend |
| Whisper `chunk_length_s=60` | Matches clip max duration; fewer pipeline passes per clip |
| ProcessClips concurrency | `concurrentlySchedulableTaskCount=3` on InvokeHTTP + PublishKafka in ProcessClips |
| Kafka Topics auto-load | Topics panel fetches on page mount; 30s backend TTL cache |
| Temp file `.wav` → `.mp4` | Whisper server now writes clips with correct extension |
| Router imports cleaned up | `os` and `json` moved to module level in `routers/streamers.py` |

### Session 3 (2026-06-29)

| Change | Details |
|---|---|
| NiFi group ID cache | `_resolve_streamer_groups` BFS result cached 5 min |
| Parallel Kafka consumers | `topic_stats` runs both consumers concurrently via `asyncio.gather` |
| topic_stats result cache | 30s TTL — repeated Refresh clicks don't spin new consumers |
| Flow poll 5s → 30s | Frontend poll interval reduced 6× |
| Page-visibility pause | Poll stops when browser tab is hidden, resumes on focus |
| Lazy thumbnails | `loading="lazy"` on clip thumbnail images |
| Skip persistence | Skip writes clip_id to `/clips/.skipped.json`; filtered from queue on next load |
| Publish persistence | `publish_clip` writes clip_id to `/clips/.published.json` on successful tweet |
| Reset clears skip+publish | Reset Kafka button also wipes `.skipped.json` and `.published.json` |
| Video player in review | `<video controls preload="none">` in each ClipCard, served via `GET /api/streamers/clip/{clip_id}` |

### Session 2 (2026-06-28)

| Feature | Details |
|---|---|
| Kafka topic panels | Live message count + last 5 records for `new_clips` and `processed_clips` in the Streamers UI |
| Reset Kafka button | Deletes topics via Kafka Admin API, wipes `/clips/*.mp4`, resets `.seen_clips.json` |
| Dismiss on publish | Cards vanish after 1.2s "Posted ✓" flash; Refresh clears stale dismissed state |
| Fallback captions | 5 rotating Tuna Street fallbacks when vLLM returns empty |
| Duration filter | Fetch 20 clips per streamer, drop < 45s, sort longest-first, cap at 3 per streamer |
| File-exists gate | Review queue only surfaces clips whose MP4 is on disk |
| 404 on missing file | Publish endpoint returns actionable 404 instead of opaque 502 |
| RBAC | Added `kafkatopics get/list/delete` to `cso-operator-app-writer` role in `cld-streaming` |

