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
  X_ACCESS_TOKEN_SECRET="${X_ACCESS_TOKEN_SECRET}"
```

(`STREAMERS_WATCH_LIST` dropped 2026-07-12 — grepped, never read anywhere in the codebase; the in-memory watch list is seeded by `_init_watchlist()` instead, see "Auto-add live streamers" section.)

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
| `GET  /api/streamers/queue` | Review UI on load; `agent-approvePosts.sh` |
| `GET  /api/streamers/clip/{clip_id}` | Video player in ClipCard |
| `POST /api/streamers/approve` | Approve button; `agent-approvePosts.sh` — queues a clip into `.pending_publish.json` |
| `POST /api/streamers/publish` | Post Now button on a Review card (direct/immediate publish, bypasses the pending queue) |
| `POST /api/streamers/publish-next` | NiFi `PublishClip`/`PublishClipPeakTimeCron` timers; `agent-PostNow.sh` — pops the front of the pending queue |
| `GET  /api/streamers/pending` | Pending Publish panel |
| `POST /api/streamers/pending/{clip_id}/cancel` | Cancel button in Pending Publish |
| `POST /api/streamers/pending/{clip_id}/publish-now` | Post Now button on a Pending Publish row — publishes that specific clip regardless of queue position |
| `GET  /api/streamers/published` | Posted Clips tile gallery |
| `POST /api/streamers/admin/backfill-metadata` | One-time repair for pending/published entries from before source/streamer/url/thumbnail_url/x_handle existed — idempotent, safe to re-run |
| `POST /api/streamers/skip` | Skip button |
| `GET  /api/streamers/topics` | Topics panel (30s cached) |
| `POST /api/streamers/reset` | Reset Kafka button |
| `GET  /api/streamers/watchlist` | Watch List section |
| `POST /api/streamers/watchlist` | Watch List add/remove; `agent-watchList.sh` (full replace) |
| `POST /api/streamers/watchlist/rotate` | Rotate button |
| `POST /api/streamers/watchlist/add` | `agent-watchList.sh add`; `LiveStreamerAlert`'s `AddToWatchlist` (pins a discovered-live streamer, additive) |
| `GET  /api/streamers/roster` | `LiveStreamerAlert`'s `GetRoster` (was `GetWatchlist`) — every catalog streamer, not just the 4-ish entry watch list |
| `GET  /api/streamers/flows` | Pipeline Status panel (30s polled) |
| `POST /api/streamers/flows/{name}/start\|stop` | Flow start/stop buttons; `agent-fetchClips.sh` (FetchClips only) |

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
| `Peak Time 4-11pm` (GenerateFlowFile) | `CRON_DRIVEN`, schedule `0 0/33 16-23 * * ?` — every 33 min, hours 16-23 UTC |
| `InvokeHTTP` | `POST http://cso-operator-app.default.svc.cluster.local:8090/api/streamers/publish-next` — same endpoint the original `PublishClip` PG calls |

**Scaled back (session 14):** interval loosened from every 9 min to every 33 min (`0 0/9 16-23 * * ?` → `0 0/33 16-23 * * ?`) — was posting too much. At :00/:33 each hour across the 8-hour window that's a ceiling of ~16 posts/day at full queue (down from ~53/day), still above the 3-5/day the 2026 X-growth research (see `x-clip-usertags.md`) says gets the best engagement per post, but a big step down from the prior cadence.

**Updated (session 14):** renamed from `Peak Time 3-9pm` (`0 0/18 19-23,0-1 * * ?`, an EDT-converted window) to `Peak Time 4-11pm` (window and interval tuned above) — a wider window (16-23 UTC is a single contiguous range vs. the old wraparound `19-23,0-1`) set directly in UTC hours rather than converted from EDT. This sidesteps the earlier DST-shift concern (session 13's note that the old expression would need to shift an hour at DST changeover) since the window is now defined in pod-local UTC terms directly, not translated from a US timezone.

**Correction (session 13, historical):** the original `15-21` cron assumed the NiFi pod's clock was pod-local EST. It isn't — `mynifi-0` runs in UTC (`date` in the pod returns `UTC`, confirmed 2026-07-02: pod showed 18:52 while local system showed 14:52 EDT). So `15-21` was actually firing 11am-5pm EDT, an hour(s) early. Corrected at the time to the UTC-equivalent of 3pm-9pm EDT (`19-23,0-1`), since superseded by the session 14 update above.

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
- **Publish history tab** — ✓ SHIPPED (session 14, as "Posted Clips") — see section below
- **Auto-publish mode** — bypass review queue, post top clips on a schedule
- **Post to real X account** — ✓ PLANNED (see section below)
- **GPU optimization** — Whisper CPU + 5B caption model — see [`gpu-optimization-plan.md`](gpu-optimization-plan.md)
- **Live Streamer Alert** — ✓ SHIPPED (session 15, as "LiveStreamerAlert") — see section below
- **TODO: bring in the `nifi-custom-processors` repo** — the real GitHub repo exists but isn't cloned locally yet (currently just a local, non-git folder at `~/nifi-custom-processors` with `XLivePostProcessor.py` sitting in it uncommitted). Planned for next week.
- **Video title/description/CTA/category** — PUNTED (session 12): needs an X Ads account for @TunaStreetTest before it's buildable. See "Untitled Videos" section above for what's confirmed.
- **Subtitles from transcript** — unblocked, deprioritized (session 12): `POST /2/media/subtitles` + existing Whisper segment timestamps could give real closed captions with no new credentials. See "Untitled Videos" section above.
- **Reply Guy** — FUTURE IDEA (added session 14): auto-reply bot behavior, threaded onto every posted clip's tweet. Reply 1 — link to the streamer's own stream/channel page (their Twitch/Kick profile URL; already have this value on every clip record as `clip.streamer` + `clip.source`). Reply 2 — the clip's transcript, likely a quotable excerpt rather than the full wall of text (not finalized; would need vLLM if excerpting rather than dumping raw text). Not scoped or built yet.
- **More Telegram scripts** — FUTURE IDEA: `Fetch Clips` and `Publish Clips` on-demand triggers, same reply-to-chat pattern as `agent-PostNow.sh`. Post Now is the first one built.
- **LiveStreamerAlert silent-drop fixes** — ✓ FIXED live in two rounds (session 16, 2026-07-12): real HTTP retry on all 5 `InvokeHTTP` calls + failure/unmatched logging across the whole PG, not just the original dedup gap. **Not yet verified against a real multi-streamer-live event** — no one was live at fix time. See "LiveStreamerAlert — Known Issues" section below.
- **LiveStreamerAlert tweet format (🟢 + "link in first comment")** — ✓ APPLIED live (session 16, 2026-07-12) — see section below.
- **Clear the LiveStreamerAlert dedup cache** — investigated, deliberately not run (risk of duplicate real X posts for still-live sessions) — needs Steven's explicit go-ahead. See section below.
- **Auto-add live streamers to the watch list** — ✓ SHIPPED AND WIRED LIVE (session 16, 2026-07-12) — `LiveStreamerAlert` now polls the full roster (`GET /api/streamers/roster`, `GetRoster`) instead of the 4-entry watch list, and pins any discovered-live streamer onto the watch list via `AddToWatchlist`. Live-tested: 7 streamers found live in one poll, all added for real. See section below.
- **Clip glitch effect rework + Talking Tuna Fish ("Charlie") overlay** — BACKLOG (session 16, moved from `streamers.md`) — see "Feature Backlog — Clip Overlay & Glitch Effect" section below.

---

## Feature Backlog — Clip Overlay & Glitch Effect (session 16, 2026-07-11)

Moved here from `streamers.md` (was sitting under the streamer roster, undocumented elsewhere). Two related asks, both about the clip visual identity — "full Tuna Street streams" branding push. Backlog only, not scoped or built.

**1. Glitch effect rework.** Current clip-processing glitch transition is too short/abrupt. Ask: make the glitch run longer, then *reverse the same distortion* for the snap-back instead of a hard cut — whatever the effect does going in, unwind it symmetrically on the way out, rather than an instant discontinuity. Lives wherever the glitch is implemented today (ffmpeg filter chain in `services/streamers.py`'s clip processing), or its equivalent once the ProcessClips NiFi-native refactor's `ClipOverlayProcessor` is built (see "NiFi-Native Refactor Plan" below) — natural to build once there rather than twice.

**2. Talking Tuna Fish overlay — "Charlie the Tuna" (expanded concept).** A recurring animated tuna-fish clip-art mascot ("Charlie") that talks over the streamed clip footage, same spirit as TheBurntPeanut's fruit-mascot overlays (`@theburntpeanut` in the roster is the reference/comp).

- **Tone**: obnoxious and wild — a personality that fights for attention on screen, not a subtle brand bug, in line with the "Tuna Street Streams" identity.
- **Script/voice — open question**: reuse the existing vLLM caption pipeline to generate a line per clip and TTS it, vs. hand-write a stock bank of obnoxious one-liners/reactions picked randomly or by context. vLLM route is more "alive" per-clip; stock bank is far cheaper to ship first.
- **Trigger timing — open question**: overlay for the whole clip, or pop in at a specific beat (e.g. right after the glitch snap-back above)?
- **Visual fidelity — open question, cheapest-to-priciest**: static clip-art with a looping talking-mouth animation → a few discrete mouth-shape frames swapped on audio amplitude (still cheap, more alive) → full animation (likely overkill for v1).
- **Pipeline dependency**: both land in the same ffmpeg/overlay processing stage — batch this with the `ClipOverlayProcessor` work already flagged as the highest-risk remaining piece of the ProcessClips native refactor, rather than building throwaway logic in the current Python path first.

---

## LiveStreamerAlert — Known Issues & Session 16 Investigation (2026-07-11 → 2026-07-12)

Follow-up to the "LiveStreamerAlert" build section above, after Steven reported: some live streamers never post even after repeated poll runs, and no error surfaces anywhere. Investigated read-only via the live `flow.json` (`kubectl exec mynifi-0 ... gunzip data/flow.json.gz`) and both NiFi log containers (`nifi`, `app-log`) over a 72h window — no live-flow changes made initially, per [[feedback-nifi-live-state-authoritative]] and [[feedback-prod-no-manual-patches]]. Steven then explicitly authorized direct canvas edits for this PG specifically ("you built the flow... NiFi is not my own space, especially if you built the flow") — see the update on [[feedback-nifi-live-state-authoritative]]. Fixes below were applied live via the NiFi REST API (authenticated with the existing `nifi-admin-creds` k8s secret, called directly from `mynifi-0` — not routed through the `cso-operator-app` prod pod, per [[feedback-prod-no-manual-patches]]).

### Root cause — silent failure past dedup — ✓ FIXED (2026-07-12)

- `DedupLiveSession` (`DetectDuplicate`, cache key `${login}-${started_at}`) sits **upstream** of `BuildTweetText` → `XLivePostProcessor` — it marks a login+session as "seen" *before* the tweet is actually posted, not after.
- `DedupLiveSession`'s `duplicate` relationship was auto-terminated (silently dropped, no log, no bulletin).
- Both `XLivePostProcessor` instances' (main post + reply) `failure` relationship was also auto-terminated — the Python processor's exception handler routes to `failure` but never calls `getLogger().error()`, so nothing surfaced in the NiFi UI either.
- **Net effect**: if the post failed for any reason *after* dedup marked it seen (X API error, transient network blip, a processor getting stopped mid-cycle during manual testing), that live session was burned — every later poll for the same `started_at` hit `duplicate` and dropped silently. Only the 24h `Age Off Duration` on `DedupLiveSession` eventually cleared it. This matched the symptom exactly: streamers that "were live and didn't come out, more runs even after some time, no results past dedupe."
- Confirmed **not** a Twitch/Kick asymmetry — `LogAlertResult` (fires only on a fully-successful main-post+reply) shows real successful posts for `stableronaldo` (twitch) and both `n3on`/`hstikkytokky` (kick) on 2026-07-10, plus `extraemily` (twitch) and a second `hstikkytokky` session (kick) on 2026-07-11. Both platforms worked end-to-end; the gap was silent failures on the unlucky runs, not a platform gap.

**Fix applied (round 1):** `DedupLiveSession`'s `duplicate` relationship and both `XLivePostProcessor` instances' `failure` relationship are now wired into the existing `LogAlertResult` (`LogAttribute`) processor instead of auto-terminating — a burned/failed entry now logs to `app-log` (same place the successful-post confirmations already show up) instead of vanishing.

**Important caveat, called out by Steven:** this round only added *visibility* into that one specific gap — it doesn't retry anything and doesn't fix delivery by itself. It also doesn't explain the reported symptom on its own: Steven observed 4+ streamers live at once with only 2 posting, and dedup-burn requires a *first successful pass* before it can bite, so it can't be the whole story. See round 2 below.

### Broader silent-drop fix — real HTTP retry + full-flow failure logging (2026-07-12, round 2)

Re-audited every processor in `LiveStreamerAlert`, not just the post-dedup gap. Found the same silent-drop pattern repeated throughout the flow:

- **All 5 `InvokeHTTP` calls** (`GetWatchlist`, `GetKickChannelId`, `GetKickLiveStatus`, `GetTwitchLiveStatus`, `GetXHandle`) auto-terminated `Retry` along with `Failure`/`No Retry`. `Retry` is NiFi's signal for a *recoverable* failure — rate limiting, a transient 5xx — and is designed to be looped back for another attempt, not discarded. With it auto-terminated, a single rate-limit or blip at any of 2-3 HTTP hops per streamer per poll silently dropped that streamer for the cycle. This is a much wider surface than the one dedup gap fixed in round 1, and is the more likely explanation for "4 live, only 2 posted."
- **Every `Extract*`/`Eval*` step** (`EvalKickLive`, `EvalKickChannelId`, `EvalTwitchLive`, `EvalXHandle`, `ExtractTwitchLogin`, `ExtractKickLogin`, `ExtractTweetText`) had the same pattern on `failure`/`unmatched` — a parse or regex miss vanished with no trace.
- `DedupLiveSession`'s own `failure` relationship (its cache-lookup-itself-errored path, distinct from `duplicate`), `BuildTweetText`'s `failure`, and `SplitLogins`'s `failure` had the same gap.

**Fix applied:** the 5 `InvokeHTTP` processors now self-loop their `Retry` relationship (a bounded 10-minute `FlowFile Expiration` on that loop connection prevents a persistently-failing request from retrying forever) and route `Failure`/`No Retry` to `LogAlertResult`. Every other processor above now routes its `failure`/`unmatched` relationship to `LogAlertResult` too. `RouteIsLive`'s `unmatched` (the normal "not live" filter — true for the large majority of checks) and the plain pass-through `original` relationships were deliberately left auto-terminated — those aren't failures, logging them would just be noise.

Verified after: all 20 processors in the PG `RUNNING` + `VALID`, all new connections (5 self-loops + all the new failure/unmatched routes) confirmed present via the NiFi REST API, `PollTimer` correctly still `STOPPED` (its normal manual-trigger state, untouched).

**Separately worth knowing — not a bug, but a real contributing factor:** `XLivePostProcessor` (the main post) is deliberately throttled to one run per 3 minutes, single-threaded — anti-spam pacing by design. If 4 streamers go live in the same poll, the 4th one doesn't post until ~9-12 minutes later. Session 15/16 testing had processors getting manually stopped/restarted every 1-5 minutes — some of the "missing" streamers may simply have still been queued, waiting their turn, when testing was interrupted to check results.

**Not yet verified end-to-end.** No streamers were live at the time of this fix, so none of this — the retry loop, the new logging, or the pacing theory — has been confirmed against a real "4 live, only 2 post" scenario. Next time that happens, `app-log` should show exactly where and why each missing streamer dropped (HTTP failure/retry-exhausted, parse miss, or just still queued behind the 3-minute pacing) instead of nothing at all.

### Dry-run test poll (2026-07-12) — pipeline confirmed working, both watch-list streamers offline

Ran one real poll cycle in test mode to sanity-check the round-2 fix: set `Dry Run` to `true` on both `XLivePostProcessor` instances (main + reply — so nothing could actually post), started `PollTimer` once, watched the queue drain, then read back the NiFi provenance log filtered to this PG's processor IDs.

**Found first: the whole PG (everything except `PollTimer`) was `STOPPED`** — not something this session touched; the round-2 verification earlier had confirmed everything `RUNNING`, so this changed sometime between then and now (most likely Steven stopping it deliberately). The first poll attempt sat queued for ~7 minutes at `GetWatchlist` because of this, until noticed and the whole PG was started via the bulk PG-level run-status endpoint. Not treated as a bug — restored to the same all-`STOPPED` state afterward, per [[feedback-nifi-live-state-authoritative]].

**Also found: two extra `LogAlertResult`-named `LogAttribute` processors** sitting on the canvas (IDs `b926ca7f...` and `066fb920...`), unconnected, not present in earlier flow.json snapshots — Steven's own addition at some point, left alone.

**Provenance trace, current watch list (`extraemily` twitch, `kick:hstikkytokky`):**
- `extraemily` — `GetTwitchLiveStatus` succeeded, `RouteIsLive` → `unmatched` (not live).
- `hstikkytokky` — `GetKickChannelId` → `GetKickLiveStatus` both succeeded, `RouteIsLive` → `unmatched` (not live).
- Zero `Retry`/`Failure`/`unmatched`-on-parse events for either — both real API calls succeeded cleanly, the pipeline correctly determined neither is live, and (correctly) didn't alert. No errors to exercise the new logging this time, but confirms the happy path runs end-to-end without regressions after the round-2 rewiring.

Restored after: `Dry Run` back to `false` on both `XLivePostProcessor` instances, whole PG back to `STOPPED` (matching the state it was found in).

**Still open:** the actual "4 live, only 2 posted" scenario, and the new retry/logging paths under a real failure, remain unverified — this run only had two streamers to check and both were offline, so nothing exercised the retry loop.

### Clearing the dedup cache manually — investigated, NOT run

Backing service is `LiveAlert MapCacheServer` (`org.apache.nifi.distributed.cache.server.map.MapCacheServer`) — in-memory only, no `Persistence Directory` set, so a NiFi restart clears it but stop/starting the *processors* doesn't (it's a separate controller service). NiFi has no "Clear" action for this service type in the UI. Standard technique: **disable, then re-enable `LiveAlert MapCacheServer`** (the server, not the client service) — reinitializes its internal map from scratch, wiping every cached dedup key.

**Deliberately not run this session.** Unlike the routing/text fixes above, clearing the cache has a real public side effect: any streamer whose live session is still ongoing would look "new" again on the next poll and could get **re-posted to X** — a duplicate real tweet, not just an internal state change. That crosses into "ask first" territory. Steven: say the word and it's a 2-line script (disable → re-enable the controller service), or just let the 24h age-off handle the currently-burned entries from testing.

### Re-occurrence / scheduling — open design question

`PollTimer` (`GenerateFlowFile`) is 1-day/stopped today, started manually per test run. Options, for Steven to pick:

- **CRON_DRIVEN** (e.g. every 5-15 min), always running — closest to real live-alert behavior. The silent-failure gap that made this risky is fixed now (see above), so this is more viable than it was; confirm Twitch/Kick rate-limit headroom at that cadence first.
- **TIMER_DRIVEN, longer period** (e.g. 30-60 min) — lighter touch, still gives visible failures if something goes wrong.
- **Stay manual** (current) — safest, no urgency to change now that failures are logged instead of silent.

### Tweet format — 🟢 instead of 🔴, add "(link in first comment)" — ✓ APPLIED (2026-07-12)

Target (Steven's sample): `🟢 {login} is LIVE now! Follow on X @{x_handle} — join me on @{platform_tag} (link in first comment)`

`BuildTweetText`'s (`ReplaceText`) "Replacement Value" property is now live as:

```
🟢 ${login} is LIVE now! Follow on X @${x_handle} — join me on @${platform_tag} (link in first comment)
```

(was: `🔴 ${login} is LIVE now! Follow me on X @${x_handle} — join me on @${platform_tag}`)

### Auto-add live streamers to the watch list — ✓ WIRED LIVE (2026-07-12)

`POST /api/streamers/watchlist/add` (`{"login": "...", "platform": "twitch"|"kick"}`) — additive/idempotent, appends one login without touching the rest of the list. See `add_to_watchlist()` in `services/streamers.py`, distinct from `set_watchlist()` (full replace) and `rotate_watchlist()` (swap 4).

**Telegram command:** `agent-watchList.sh add t:username` / `add k:username` — same additive behavior via the bot.

**The open design question is resolved: check the full roster, not the watch list.** Steven's call: "You should be checking the entire list of streamers to see who is online, NOT the watch list." Implemented live:

- New backend endpoint `GET /api/streamers/roster` — every catalog streamer (`_TWITCH_LOGINS` + `_KICK_LOGINS`, same `login`/`kick:login` shape as `/watchlist`), see `get_roster()` in `services/streamers.py`.
- `GetWatchlist` (the `InvokeHTTP` processor) renamed to **`GetRoster`** and repointed from `/api/streamers/watchlist` to `/api/streamers/roster` — done live via the NiFi REST API, no canvas rewiring needed beyond the URL/name.
- New branch: `RouteIsLive`'s `is_live` relationship now fans out to *both* the existing `GetXHandle` chain (builds and posts the alert) *and* a new `BuildWatchlistAddBody` (`ReplaceText`, builds `{"login": "...", "platform": "..."}`) → `AddToWatchlist` (`InvokeHTTP POST /watchlist/add`) — so a discovered-live streamer gets pinned onto the watch list (which still separately drives `FetchClips`) as a side effect of being found live, independent of whether the alert itself posts.
- `AddToWatchlist`'s `Failure` relationship routes to `LogAlertResult`, same convention as the rest of the flow.

**Important: this write path is *not* gated by `XLivePostProcessor`'s `Dry Run` flag** — it's a separate, always-real call. Confirmed live-tested 2026-07-12 (see below) — flagged and confirmed with Steven before the first live-write run, since a "test" poll would otherwise silently mutate the real watch list.

**Gotcha discovered this session:** the watch list is in-memory only (`_watchlist` module global) — it resets to a fresh random 2-Twitch/2-Kick sample on every `cso-operator-app` pod restart (redeploys, crashes, etc.), same as it always has, but this interacts with `AddToWatchlist` now: a redeploy right before/during a poll cycle silently drops whatever was manually curated. Not fixed this session — no persistence layer for the watch list exists yet.

### Dry-run roster test (2026-07-12) — 7 streamers found live, watch list updated for real

Ran the same dry-run pattern as before (`Dry Run=true` on both `XLivePostProcessor` instances, so no alert could actually post) but against the newly-repointed full-roster check (30 catalog streamers — includes `joe_bartolozzi` and `whiz`, added to the catalog this session at Steven's request). `AddToWatchlist` was explicitly confirmed with Steven to run for real before triggering (see above).

**Found live:** `eliasn97` (twitch), `joe_bartolozzi` (twitch), `roshtein` (kick), `deenthegreat` (kick), `n3on` (kick), `adrienbroner` (kick), `whiz` (kick) — 7 total, all via provenance-confirmed real API responses (`live_id` populated, `RouteIsLive` → `is_live`), zero HTTP failures/retries across all 30 streamers checked.

**Discrepancy worth flagging, not chased down further:** Steven had reported `adinross` live too; this poll's real Kick API check for `adinross` came back clean (`GetKickChannelId`/`GetKickLiveStatus` both succeeded, no errors) but with `live_id` empty → correctly routed `unmatched` (not live). Most likely explanation: enough time passed between Steven's message and this poll actually running (~10 min of deploy/wiring work) that the stream ended in between — not treated as a bug, no code changes made chasing this specific case.

**Confirmed real side effects:** all 7 found-live streamers got added to the watch list via `AddToWatchlist` (`GET /api/streamers/watchlist` after the run showed all 7 present). No alerts posted to X (dry run held).

**State restored after:** `Dry Run` back to `false` on both `XLivePostProcessor` instances, whole PG back to `STOPPED` — same resting-state pattern as the previous test.

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

Today `FetchClips`/`ProcessClips`/`PublishClip` are thin NiFi shells that hand all real work to Python (`backend/services/streamers.py`). Goal: NiFi owns the actual flow logic; backend shrinks to orchestration (loops the watch list / reacts to UI actions, POSTs work into a NiFi listener — same shape as `files/midi_melody2.py` already does against MiNiFi).

**Native vs. custom Python:** default to native processors (`InvokeHTTP`, `EvaluateJsonPath`, `StandardOauth2AccessTokenProvider`, etc.) — custom Python only where native genuinely can't do the job. Two real blockers: OAuth1-signed X media upload (`InvokeHTTP` only supports OAuth2), and the ffmpeg overlay/glitch-intro orchestration (too many hard-won gotcha-fixes to safely re-express as chained `ExecuteStreamCommand`).

**Custom processor deployment — now validated**, not just planned: see "LiveStreamerAlert" above for the actual working setup (`FlowFileTransform` base class, PVC-backed extensions dir since `minikube mount` failed on this host, `nifi.python.extensions.directories` config, NiFi must be 2.x). `XPublishProcessor` below is superseded by `XLivePostProcessor` for the text-post case — the same processor extends to chunked media upload once video posting moves here too.

**Candidate custom processors:**

| Processor | Leg | Replaces | Why native can't do it |
|---|---|---|---|
| `ClipOverlayProcessor` | Fetch | `_burn_platform_overlay` + `_burn_glitch_intro` | Multi-step ffmpeg orchestration with hard-won gotcha-fixes (B-frame-free concat, `-threads 1` pinning) — brittle to reproduce as chained `ExecuteStreamCommand` |
| `CaptionCleanProcessor` (optional) | Process | `_clean_caption` + `_build_tweet` | Not a hard blocker — simpler to leave backend-side at read-time |
| `XPublishProcessor`/`XLivePostProcessor` | Publish | `_publish_sync` | OAuth1-signed — `InvokeHTTP` has no OAuth1 support. **Built** (see LiveStreamerAlert) |

---

### Fetch

`FetchClips` PG calls `fetch_clips()`, which does everything itself — token refresh, pagination, GQL lookup, download, overlay/glitch burn, dedup, Kafka publish.

| Current backend function | Native replacement |
|---|---|
| `_twitch_token_refresh`/`_kick_token_refresh` | `StandardOauth2AccessTokenProvider` (client-credentials) |
| `_get_broadcaster_id`, `_get_clips` (pages 5×100 in top_mode) | `InvokeHTTP`+`EvaluateJsonPath`, self-looping connection for pagination |
| `_gql_clip_mp4_url` | `InvokeHTTP` POST to `gql.twitch.tv/gql` → `EvaluateJsonPath` → `UpdateAttribute` assembles signed URL |
| `_download_clip`, Kick's `_get_kick_clips` (needs browser UA/Referer) | `InvokeHTTP` w/ static headers → `PutFile` |
| `_download_hls_sync` (Kick HLS → MP4) | `ExecuteStreamCommand` invoking ffmpeg directly |
| `_burn_platform_overlay`+`_burn_glitch_intro` | `ClipOverlayProcessor` (custom — strongest case in Fetch) |
| `.seen_clips.json` dedup | `DetectDuplicate` + `MapCacheServer`/`MapCacheClientService` (same pair LiveStreamerAlert uses) |
| `_publish_clips_to_kafka` | Already native (`PublishKafka_2_6`) |

Rate limiting: Twitch Helix is 800 points/min — `Wait`/`ControlRate` between paginated calls.

---

### Process

Move Whisper transcription + vLLM caption generation out of the Python backend into NiFi-native `InvokeHTTP` — same pattern as the existing `StreamToWhisper`/`StreamTovLLM` RAG flows. Fixes the current risk: `ConsumeKafka → InvokeHTTP POST /process-clip → PublishKafka`, where a slow Whisper transcription (120s+ on a long Kick clip) can trip NiFi's InvokeHTTP timeout and lose the clip. Per-step timeouts + visible intermediate state fix that.

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

#### Optional — CaptionCleanProcessor

`_clean_caption`/`_build_tweet` currently run at UI-read-time in `clip_queue()`. Could become a `CaptionCleanProcessor` (`FlowFileTransform`) after the vLLM step instead of chained `ReplaceText` regexes — not a requirement, backend-side is simpler and only runs on queue-read, not the hot path.

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

`PublishClip`'s `HandleHttpRequest`(:9001)/`HandleHttpResponse` listener shape is already correct and stays as-is. Only the inner step changes: `InvokeHTTP → backend /api/streamers/publish` → `XPublishProcessor` (custom, takes `clip_path`+`tweet_text` in, returns `tweet_id`/`url`, lifts `_publish_sync`'s chunked OAuth1 media upload nearly verbatim). Rate limiting (X's ~10-20/hr anti-ban pacing) is native `Wait`/`ControlRate` ahead of it — only the signed post itself needs custom code.

---

### App Backend's Role After the Refactor

Backend keeps watch-list management and UI-triggered orchestration (Approve/Post Now/Skip/Reset) — doesn't go away, just stops doing the Twitch/ffmpeg/Whisper/vLLM/tweepy work itself. Instead it POSTs work into NiFi's own `HandleHttpRequest`/`ListenHTTP` listeners (same shape `files/midi_melody2.py` already uses against MiNiFi). Fetch trigger is the only one that changes shape (backend loops the watch list, POSTs `{login, source}` into a new Fetch listener); Process and Publish triggers are already this shape today.

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

**Fetch/Publish legs** — mostly *removal* once native/custom NiFi processors own the work: `fetch_clips()` and everything it calls (`_twitch_token_refresh`/`_kick_token_refresh`, `_get_broadcaster_id`/`_get_clips`, `_gql_clip_mp4_url`, `_download_clip`, `_get_kick_clips`, `_download_hls_sync`, overlay/glitch burn, `.seen_clips.json` dedup) can be deleted from `services/streamers.py`. `_publish_sync` deletes once `XPublishProcessor` is live; `publish_clip()`/`publish_next()` shrink to thin POST-into-`HandleHttpRequest` wrappers. New: a `HandleHttpRequest` listener on `FetchClips` (doesn't have one today) + a backend loop replacing `fetch_clips()`'s body that POSTs `{login, source}` into it.

---

### Rollout Sequencing

Recommended order: **Publish → Process → Fetch** (smallest/highest-value first, riskiest custom processor — `ClipOverlayProcessor`'s ffmpeg gotcha-fixes — last, once the custom-processor deployment pattern is proven). **Publish is now underway** — `XLivePostProcessor` proves the pattern for text posts; extending it to chunked media upload for real clip-posting is the remaining piece of this leg.

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

## Clip Selection, Duration Cap & Live-Timing Investigation

Prompted by: uncertainty about whether fetched clips are actually the *best* moments, whether the duration cap is discarding good longer clips, whether Twitch/Kick are both being used to full capability, and interest in posting closer to when a streamer is actually live. Read against the real code (`backend/services/streamers.py`), not guessed. Research-only — nothing implemented yet, per current priority.

### Clip selection — confirmed gap

`get_fetch_mode()` defaults to `{"mode": "recent"}` (and that's what's live right now: `recent/all`). In `recent` mode, Twitch's `_get_clips` ranks candidates by **longest duration**, not views (`sorted(valid, key=lambda c: c.get("duration", 0), reverse=True)`) — we are not selecting for quality at all in the default mode, only for length within the cap. View-based ranking only happens in `top` mode, and even then only for Twitch. **Not touched yet** — flagged for a future decision, not urgent per current priority.

### Kick vs. Twitch — structural asymmetry, not a bug

Twitch `top_mode` pages up to 5×100 clips and ranks by `view_count` — real work. Kick cannot do this: confirmed via Kick's own docs (`docs.kick.com`) that **no `/clips` endpoint exists anywhere in the official Public API v1** — Categories, Users, Channels, Chat, Livestreams, Channel Rewards, Moderation, KICKs leaderboard are the entire surface. Our `_get_kick_clips` uses the *unofficial* web endpoint (`kick.com/api/v2/channels/{slug}/clips`), which only supports `sort=date` — no view-count sort, no date-range filter server-side. That's why `_get_kick_clips` always pulls the 20 most recent clips and ranks by views only among those 20, regardless of `top_mode`/`period` (both parameters are accepted but silently ignored for Kick). A viral Kick clip that ages out of the most-recent-20 can never surface — this is a platform ceiling, not something fixable in our code.

**Kick feedback opportunity:** worth emailing Kick's dev/feedback contact to ask for a public `/clips` endpoint with view-count sort + date-range filtering (Twitch's Get Clips already does this) — a concrete, specific, well-grounded ask now that we've confirmed the gap against their actual docs rather than assuming. Draft below.

### Duration cap — why it exists, and what Premium actually changes

Twitch capped to 45–100s, Kick to 45–90s, because session 13 hit a live X 403 ("video longer than 2 minutes") — the caps are a safety margin under X's **standard 2:20 (140s) non-Premium API limit**.

**@TunaStreetTest already has X Premium** (confirmed 2026-07-10). Researched what that actually unlocks via the *API* (not the web-upload UI, which quotes much bigger numbers — hours — that don't apply to programmatic posting):

- Standard API limit: 2:20 (140s), any account.
- Premium/Amplify-eligible accounts can post **up to ~10 minutes** via chunked upload — but only when the upload explicitly sets `media_category=amplify_video` instead of the default `tweet_video`. A real dev-community report (2026) shows a Premium account still hitting a 403 at >10 min even with the right category — so ~10 min looks like the actual API ceiling regardless of what the marketing pages for the web app claim.
- **Our code never sets `media_category`** — `_publish_sync` calls `api_v1.media_upload(str(path), chunked=True)` (`services/streamers.py:1601`) with no category, which defaults to `tweet_video` and the standard 2:20 limit. Premium being active on the account doesn't help until the upload call explicitly asks for the Premium-eligible category.
- **Not implemented yet** — per current priority, nothing to build until fetch-mode/selection direction is settled. When it's time: change `media_category="amplify_video"` on that one call and test against a real >2:20 clip before touching the fetch-side duration caps at all.

Sources: [X Developer Community — Premium 403 at >10min with amplify_video](https://devcommunity.x.com/t/gettiing-a-403-error-that-user-cant-post-a-video-longer-than-10-mins-unless-verified-but-already-on-premium/258219), [X Chunked Media Upload docs](https://docs.x.com/x-api/media/quickstart/media-upload-chunked), [help.x.com — Longer videos for Premium subscribers](https://help.x.com/en/using-x/premium-longer-videos)

### Live-status timing — cheaper than expected on both platforms

Confirmed no live-status check exists anywhere in the current code (the session-12 "Live Streamer Alert" idea is still just a one-liner, not designed). Checked what each platform's *official* API actually offers, since this is the piece closest to what's driving the ReplyGuy views:

- **Twitch**: `GET /helix/streams?user_login=...` — up to 100 logins per call, well-documented, already how similar bots do it. No research needed, just not built.
- **Kick**: confirmed via official docs — `GET /public/v1/users/livestreams` takes up to 100 `user_id`s in one call (app access token / client_credentials is sufficient, same auth we already use for `_kick_token_refresh`), returns `started_at` + `viewer_count` per currently-live streamer. Kick also has a deprecated `GET /public/v1/livestreams` with a `sort=viewer_count|started_at` param, but the non-deprecated `users/livestreams` is the right one for "is X currently live."
- Both platforms make a whole-watch-list live check cheap (one call each, not per-streamer), which is the missing piece for "fetch more aggressively while live, publish faster after a good clip lands."

Sources: [Kick API docs](https://docs.kick.com/) (llms-full.txt endpoint index).

**Kick feedback email:** sent by Steven directly (2026-07-10) — no draft kept here.

---

## Post Now — Immediate Single-Clip Publish (UI + Telegram)

Three fast paths, all reuse existing endpoints (no new backend needed):

- **UI, Review queue** — `Post Now` button on each `ClipCard` publishes *that specific clip*, pre-Approve. `POST /api/streamers/publish` (`publish_clip()`), marks published, excluded from normal rotation after.
- **UI, Pending queue** — per-row `Post Now` publishes that one already-approved clip immediately regardless of queue position. `POST /api/streamers/pending/{clip_id}/publish-now` (`publish_pending()`) — safe out of order since the pending queue is a flat JSON file, not Kafka (see Pending Publish Panel below).
- **Telegram** (`agent-PostNow.sh`) — no arg pops the pending queue (`/publish-next`, same as the cron timers); optional usertag arg finds that streamer's pending clip and posts it out of order via the same endpoint the Pending-row button uses, falling back to `/publish-next` if no match. Live-tested all 4 paths.

No NiFi PG needed — ad-hoc, not scheduled (candidate to fold into the NiFi-Native Refactor later). Dismiss delay on both UI surfaces is 6s (was 1.2s — too fast to read/click the tweet link).

---

## Pending Publish Panel

Each row shows thumbnail, platform badge, streamer/X links, title linked to the clip — `approve_clip()` threads `source`/`streamer`/`url`/`thumbnail_url`/`x_handle` through into `.pending_publish.json`. Older pre-change entries fall back gracefully (no thumbnail).

**Safe to Post Now out of order?** Yes — `.pending_publish.json` is a flat JSON list, not Kafka. `publish_pending(clip_id)` removes that one id from wherever it sits (same pattern as `cancel_pending()`), restores it to the front on failure. Rest of the queue and the normal cron pop-index-0 rotation are unaffected.

---

## Posted Clips

Tile gallery (now its own sub-page, session 15) showing recently-published clips: thumbnail, platform badge, streamer, title, timestamp, link to the live tweet.

- `mark_published()` still adds to the flat `.published.json` id set (dedup check), and now also appends a full record to `.published_history.json` (capped at 500).
- `GET /api/streamers/published` serves the most recent 60 for the gallery.

---

## LiveStreamerAlert — NiFi-Native "Streamer Is Live" Post (session 15)

**Status: LIVE — first real post confirmed 2026-07-10.**

New process group under `StreamersApp`, built entirely in NiFi (no backend business logic) — the first real leg of the NiFi-Native Refactor Plan below, proven out end-to-end.

**Flow:** `PollTimer` (manual/1-day, Steven starts it to test) → `GET /watchlist` (only backend touch — passive data read) → split per streamer → Twitch/Kick live-status branches (`Get Streams` / `users/livestreams`, both OAuth2 client-credentials) → `RouteOnAttribute` on `is_live` → `DetectDuplicate` (keyed `login-started_at`, so a still-live stream doesn't re-alert but a new session does) → `GET /x-handle/{login}` (new backend endpoint, passive lookup) → build tweet → `XLivePostProcessor` (posts) → `XLivePostProcessor` again as a reply (platform URL only, avoids the link-in-body reach penalty).

**Tweet format:** `🔴 {streamer} is LIVE now! Follow me on X @{handle} — join me on @Twitch` (or `@Kick`) — no link in the main post. Reply posts the platform URL (`twitch.tv/{login}` or `kick.com/{login}`) immediately after.

**Custom processor — `XLivePostProcessor`** (`cso-operator-app/nifi-processors/`): OAuth1-signed `POST /2/tweets` via `requests-oauthlib`. `Dry Run` property (default true) logs instead of posting. Optional `Reply To Tweet ID` property reuses the same processor for both the main post and the reply. Credentials come from a NiFi Parameter Context (`streamers-x-creds`, sensitive params) bound to `StreamersApp` — not env vars, since this NiFi instance is CFM-operator-managed and env-var drift on the reconciled StatefulSet doesn't stick.

**Pacing:** `XLivePostProcessor` itself is scheduled every 3 minutes (not a separate rate-limit processor) — if several streamers go live in the same poll, they post one at a time instead of bursting. `PollTimer` is left at 1-day/stopped; Steven starts/stops it manually to trigger a real check-and-post cycle.

**Infra notes:**
- Custom Python processors need a `custom-python-extensions` PVC mounted at `/opt/nifi/nifi-current/python/extensions` (a live `minikube mount` bridge failed on this WSL2/docker-driver host — PVC + a small loader pod for `kubectl cp` is the reliable path here) plus `nifi.python.extensions.directories` set in `configOverride.nifiProperties.upsert`.
- The live NiFi image was actually pinned to 1.28.1 despite the CR's `nifiVersion: "2.6.0"` label — Python processors don't exist in 1.x at all. Fixed by correcting `image.tag` to the real 2.6.0 build.
- Framework followed: [How to Build and Test Custom NiFi Processors with AI](https://stevenmatison.com/blog/How-to-AI-with-NiFi-and-Python/) — prove a bare `GenericTransformTemplate` skeleton on canvas first, inject logic only after, defensive error handling (route to `failure`, never crash).

`XLivePostProcessor.py` is mirrored into `~/nifi-custom-processors/` (now has a `README.md`) as the first local example of a `FlowFileTransform`-style (not source-style) custom processor — that folder isn't a git repo yet locally, see What's Next. Custom card/media for the alert — future idea, not scoped yet.

---

## Telegram Scripts (DesktopShare `files/`)

| Script | Does |
|---|---|
| `agent-PostNow.sh [usertag]` | No arg: pops and publishes the next clip in the **pending** queue — `POST /api/streamers/publish-next`. With a usertag (streamer login or X handle, case-insensitive, leading `@` optional): finds that streamer's pending clip via `GET /api/streamers/pending` and publishes that one specific clip out of order via `POST /api/streamers/pending/{clip_id}/publish-now`. If no pending clip matches, replies saying so and falls back to `publish-next` instead |
| `agent-approvePosts.sh` (added session 14) | Approves **every** clip currently in the review queue, if any — `GET /api/streamers/queue`, loops the whole array, `POST /api/streamers/approve` per clip with full metadata. Moves clips from Review into Pending; doesn't post them. Renamed from the singular `agent-approvePost.sh` after it was changed to hit the full queue instead of just the top clip |
| `agent-watchList.sh` (added session 14; `show`/`rotate` added session 15; `add` added session 16) | 1-4 args like `t:username` (Twitch) or `k:username` (Kick): translates to the `login`/`kick:login` format the backend expects and **replaces the whole watch list** with exactly those entries — `POST /api/streamers/watchlist`. Rejects bad prefixes or >4 args before touching the live list. `show`: prints the current list, no changes — `GET /api/streamers/watchlist`. `rotate`: swaps in 4 fresh streamers not already on the list — `POST /api/streamers/watchlist/rotate`. `add t:username` / `add k:username`: appends one streamer without replacing the rest — `POST /api/streamers/watchlist/add`, not yet confirmed via a real Telegram round-trip |
| `agent-fetchClips.sh` (added session 14) | Takes one arg, `start` or `stop` — starts/stops the `FetchClips` NiFi process group via `POST /api/streamers/flows/FetchClips/{start\|stop}`, same endpoint the Pipeline Status panel's Start/Stop buttons call. Replies with the resulting state (`RUNNING`/`STOPPED`) or a usage error if the arg is missing/wrong |

All follow the same shape as `agent-minikube-reset.sh`: check `TOKEN`/`CHAT_ID` env vars, do the HTTP work against `APP_URL` (default `http://127.0.0.1:8090`), then `curl` a plain-text result back to the Telegram chat. All were live-tested this session against the running app (`agent-watchList.sh` tested as a round-trip against the real 4-streamer watch list — same streamers in, same streamers out, so no net change to live fetch behavior; `agent-fetchClips.sh` tested stop → start round-trip against the live `FetchClips` PG, confirmed restored to `RUNNING`).

---

## Session History

### Session 16 (2026-07-11)

| Change | Details |
|---|---|
| Feature notes moved out of `streamers.md` | Roster file now stays roster-only; glitch-effect rework + Talking Tuna Fish overlay concept moved and expanded into "Feature Backlog — Clip Overlay & Glitch Effect" above |
| **LiveStreamerAlert dedup/failure root cause found and fixed live (round 1)** | Read-only investigation (live `flow.json` + `app-log`/`nifi` container logs, 72h) found `DedupLiveSession` marks an entry seen *before* the post succeeds, and both its `duplicate` relationship and `XLivePostProcessor`'s `failure` relationship were auto-terminated — a downstream failure silently burned that live session with zero log until the 24h age-off. Confirmed successful posts both days/both platforms (`stableronaldo`, `n3on`, `hstikkytokky` on 07-10; `extraemily`, `hstikkytokky` again on 07-11), ruling out a Twitch/Kick asymmetry. Steven then authorized direct canvas edits ("you built the flow... go ahead and finish the changes") — fixed live via the NiFi REST API (rerouted both relationships into `LogAlertResult`), confirmed all touched processors back to `RUNNING`/`VALID`. See "LiveStreamerAlert — Known Issues" section above |
| **Round 1 called out as incomplete, round 2 shipped** | Steven correctly pushed back: round 1 only logged one gap, didn't retry anything, and doesn't explain "4 live, only 2 posted" since dedup-burn needs a first successful pass to even trigger. Re-audited the whole PG: all 5 `InvokeHTTP` calls were silently dropping `Retry` (recoverable failures — rate limits, transient 5xx) along with `Failure`/`No Retry`, and every `Extract*`/`Eval*` step had the same silent-drop pattern on `failure`/`unmatched`. Fixed live: the 5 HTTP calls now self-loop `Retry` (10 min bounded expiration) and log `Failure`/`No Retry`; every other silent-drop path now logs to `LogAlertResult` too. All 20 processors confirmed `RUNNING`/`VALID` after. Also surfaced a non-bug contributing factor: `XLivePostProcessor` posts one streamer per 3 minutes by design, so 4 simultaneous live streamers take ~9-12 min to all post — plausibly why some looked "missing" during short test windows. Not yet verified against a real multi-streamer-live event (none were live at fix time) |
| Mapcache-clear technique identified, not run | `LiveAlert MapCacheServer` is in-memory, no UI "Clear" action exists for the type — disable/re-enable the controller service is the standard reset. Deliberately not executed — would risk duplicate real X posts for any still-live session. Needs Steven's explicit go-ahead |
| `POST /api/streamers/watchlist/add` shipped, plus the Telegram command for it | New additive endpoint (`add_to_watchlist()` in `services/streamers.py`) so the watch list can gain one streamer without replacing the whole list. Original ask was the bot command itself ("add the necessary bot commands so we could see what the watch list was, add to it") — `agent-watchList.sh add t:username` / `add k:username` wraps it, same dispatch pattern as `show`/`rotate`. Not live-tested via a real Telegram round-trip (didn't want to mutate the live watch list to self-test) — syntax-checked and reviewed against the endpoint contract only. Separately, not wired into `LiveStreamerAlert`'s own NiFi flow yet — needs Steven's call on whether `GetWatchlist` should poll the full roster instead of the current 4-entry list first |
| Tweet format applied live (🟢 + "link in first comment") | `BuildTweetText`'s Replacement Value updated via the NiFi REST API to match Steven's requested copy exactly |
| `agent-commands.md` gaps from session 15 patched | Added `show`/`rotate` Telegram commands that were missing from the bottom command list |
| NiFi API access pattern established | Auth via the existing `nifi-admin-creds` k8s secret + NiFi's `/access/token` endpoint, called from `mynifi-0` directly (never through the `cso-operator-app` prod pod, never printing credentials to the transcript) — reusable for future Claude-built-flow edits |
| Dry-run test poll run against the round-2 fix | Set `Dry Run=true`, ran one real `PollTimer` cycle, read back via provenance. Found the whole PG had been stopped since the round-2 verification (restored after, not investigated further — Steven's own state); both current watch-list streamers (`extraemily`, `kick:hstikkytokky`) checked cleanly and were offline, no errors to exercise the new retry/logging paths. Also found two extra unconnected `LogAlertResult` processors on the canvas (Steven's own addition, left alone). See "Dry-run test poll" section above |
| Roster catalog additions | `joe_bartolozzi` (twitch, `@JoeBartolozzi_`) and `whiz` (kick, `@crashoverride`) added to `streamers.md` and the backend catalog, redeployed |
| `LiveStreamerAlert` repointed to poll the full roster, not the watch list | Steven's explicit correction to the earlier "open design question." New `GET /api/streamers/roster` endpoint; `GetWatchlist` renamed to `GetRoster` and repointed live via the NiFi REST API; new `BuildWatchlistAddBody` → `AddToWatchlist` branch pins a discovered-live streamer onto the watch list. Confirmed with Steven before running live, since this write path isn't Dry-Run-gated. See "Auto-add live streamers" section above |
| Second dry-run test, full roster (30 streamers) | 7 found live (`eliasn97`, `joe_bartolozzi`, `roshtein`, `deenthegreat`, `n3on`, `adrienbroner`, `whiz`), zero HTTP failures/retries, all added to the watch list for real. One discrepancy noted (`adinross` reported live by Steven, checked clean but not-live by the time this poll ran — likely just went offline in the interim, not chased further). See "Dry-run roster test" section above |
| Credential re-injection tightened | Dropped `STREAMERS_WATCH_LIST` from the standard post-deploy `kubectl set env` command — grepped the codebase and confirmed it's never read anywhere, was a stale/unused var from the doc's example |

---

### Session 15 (2026-07-10)

| Change | Details |
|---|---|
| `agent-startup.sh` shipped | Resumes minikube after a host restart, restores headless port-forwards (`vllm-service:8000`, `cso-operator-app:8090`) without needing `minikube tunnel` |
| `agent-commands.md` fixed | `bash -c "..."` wrapper is the real fix for OpenClaw `/bash` — confirmed live via Telegram for all 5 streamers scripts |
| New Kick streamers | `adrienbroner`, `bbjess` added to catalog, deployed |
| Clip selection / duration cap / live-timing research | See "Clip Selection..." section above — default fetch mode ranks by duration not views; Kick's official API has no `/clips` endpoint (feedback emailed to Kick); X Premium needs `media_category=amplify_video` to unlock longer video (not implemented); both platforms support cheap batch live-status checks — seeded the LiveStreamerAlert build below |
| Approve All button | Clip Review Queue header — approves the whole visible queue in one click, reuses existing `/approve` endpoint |
| Posted Clips → own sub-page | Pill nav ("Overview" / "Posted Clips") added to Streamers page instead of one long scroll |
| Watch list `show`/`rotate` added to `agent-watchList.sh` | Wraps the already-existing `GET /watchlist` / `POST /watchlist/rotate` endpoints |
| **LiveStreamerAlert shipped, first real post confirmed** | New NiFi-native PG: polls Twitch/Kick for the watch list going live, posts "streamer is live" to X, then replies with the platform URL. First real custom NiFi Python processor in this project — see "LiveStreamerAlert" section below. Along the way: discovered the live NiFi image was actually 1.28.1 (Python needs 2.x) and upgraded it; a pod delete to force a config reload wiped `StreamersApp` (ephemeral `emptyDir`, not PVCs) — Steven restored it from his own backup; confirmed live NiFi state is authoritative over this doc going forward |



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
| Future Ideas relocated | Moved the "Future Ideas" subsection out from under "Post Now" into the main "What's Next" list, so all forward-looking ideas live in one place |
| **Post Now dismiss delay bumped** | User tried the first live Post Now in the app and confirmed it works, but the card/row vanished (1.2s) before the tweet URL was readable/clickable. Bumped to 6s on both the Review-card and Pending-row Post Now paths |
| **Posted Clips tile gallery shipped** | New section at the bottom of the app. `mark_published()` now also appends a full record (title/source/streamer/url/thumbnail/x_handle/tweet_id/tweet_url/published_at) to a new `.published_history.json` log (capped at 500), alongside the existing flat id-set membership check it already did. New `GET /api/streamers/published` serves the most recent 60 to a new `PostedClipsPanel` tile grid. Delivers the "Publish history tab" item that had been sitting in What's Next since session 4/5 |
| **`agent-approvePosts.sh` shipped** | Approves whatever's at the top of the Review queue (`GET /queue` → `POST /approve` with full metadata), if anything. Live-tested: approved one real clip, confirmed it landed in Pending Publish |
| **`agent-watchList.sh` shipped** | Accepts 1-4 `t:`/`k:`-prefixed args, translates and replaces the whole watch list. Live-tested as a round-trip against the real 4-streamer list (same streamers in as out — no net change) plus two rejected-input cases (bad prefix, 5 args), confirming validation runs before any mutation |
| **Missing thumbnails — root cause + backfill** | User reported no thumbnails in Pending Publish / Posted Clips. Root cause: not a bug — new approvals/publishes correctly capture full metadata (verified live), but ~40 pending clips and 4 published clips already existed from *before* the enrichment code was deployed, so those JSON records structurally never had the fields. Added `POST /api/streamers/admin/backfill-metadata` — full scan of `processed_clips` (every message still carries the original fetch metadata, since Kafka topics aren't mutated by later approve/publish) to fill in only the missing fields on existing entries; idempotent, safe to re-run. Ran once after redeploy via plain `curl`: patched 40/41 pending and 4/4 published entries, thumbnails confirmed live |
| **Session-numbering corrected** | Had split one day's work into "Session 14" and "Session 15" — corrected: one calendar day is one session, so everything from today lives in this Session 14 table. Session History going forward follows that rule |
| **`x-clip-usertags.md` expanded — X growth research** | Appended a research-backed analysis of the clip-account landscape and 2026 X algorithm/growth mechanics, checked against our actual publish code. Confirmed native video upload + no links in tweet body already match best practice; flagged `PublishClipPeakTimeCron`'s cadence (~53 posts/day at full queue) as well past the 3-5/day the research says gets the best engagement per post. Logged X Premium, a 1-hashtag A/B test, and manual reply-guy activity as concrete next ideas |
| **`PublishClipPeakTimeCron` scaled back — was posting too much** | Directly acting on the above: interval loosened `0 0/9 16-23 * * ?` → `0 0/33 16-23 * * ?` (every 9 min → every 33 min, same 16-23 UTC window). Ceiling drops from ~53 posts/day to ~16/day at full queue. Still above the research-ideal 3-5/day but a big step down |
| **`agent-approvePost.sh` → `agent-approvePosts.sh` — full queue, not just one clip** | Changed to loop the entire review queue and approve every clip present (was: approve only the top/first clip). Renamed singular → plural to match. Live-tested against the real queue: approved 19/19 clips in one run, review queue confirmed drained to 0, pending queue grew by 19 |
| **`agent-fetchClips.sh` shipped** | Telegram script taking one arg, `start` or `stop` — calls `POST /api/streamers/flows/FetchClips/{start\|stop}`, the same start/stop endpoint the Pipeline Status panel buttons use. Live-tested a full stop → start round-trip against the real `FetchClips` PG, confirmed restored to `RUNNING` |
| **`agent-PostNow.sh` gained an optional usertag arg** | Now accepts a streamer login or X handle (case-insensitive, `@` optional) and posts that streamer's pending clip specifically, via the same `/pending/{clip_id}/publish-now` endpoint the Pending panel's per-row button uses (found via a case-insensitive scan of `GET /api/streamers/pending`). No match found → replies saying so and falls back to the original `publish-next` behavior. Live-tested all 4 paths (login match, X-handle match with different case + `@`, no-match fallback, plain no-arg default) — all posted real clips correctly |

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
| Fixed "Untitled" on X Analytics | `_stamp_video_title()` embeds a title into the MP4 container via `-c copy` remux before upload (source title if it passes `_is_junk_title`, else the vLLM caption). *(Later reverted session 11 — X Analytics never reads container metadata for organic tweets, see Session 11.)* |
| **Glitch intro effect** shipped | `_burn_glitch_intro()` — freeze-frame → color-mosaic fade+strobe → hard-snap intro, only on brand-new downloads. Overlay bar stays crisp/static, only footage below animates; mosaic colors sampled from the clip's own first frame, hold/fade randomized per clip |
| Gotcha: B-frames break stream-copy concat | Every intro segment needs `-bf 0` — B-frame segments concat fine in ffmpeg but crash VLC (DTS discontinuities at splices) |
| Gotcha: bar-height detection | Use `_burn_platform_overlay`'s actual return value (bar height in px), not a re-derived formula guess — formula falsely detected a bar on bar-less clips |
| **PublishClip race bug fixed** | `approve_clip`/`publish_next`/`cancel_pending` did unlocked read-modify-write on `.pending_publish.json` — concurrent writes could silently drop or double-publish a clip. Fixed with the same `fcntl.flock` pattern as `_overlay_lock` |
| Watch List moved to Section 2 | Was last on the page, now under Pipeline Status |
| Health bar is module-aware | `/api/health` only pings services owned by the active `MODULES` flag instead of always probing all 7 |
| Gotcha: configmap `MODULES` was stale | `k8s/configmap.yaml` hardcoded `"efm,rag,streamers"`, out of sync with the real `rag,streamers` deploy — backend kept pinging a nonexistent EFM service. Fixed |
| Clips-per-streamer cap: 4th tier | 1 clip/streamer once watch list hits 4+ entries (was pulling up to 8/run right after Rotate) |
| Gotcha: glitch intro silently no-op'd — libx264 thread oversubscription | ffmpeg auto-detected the *host's* CPU count (24) instead of the pod's 1-CPU cgroup limit, causing a silent zero-frame encode with no exception. Fixed with `-threads 1` + `x264opts threads=1:sliced-threads=0` on every libx264 call, matching `_burn_platform_overlay`'s existing pin |
| Backlog of ~20 pre-fix clips patched in place | Re-ran the now-fixed `_burn_glitch_intro` directly against existing `/clips/` files via `kubectl exec`, no re-fetch needed |

### Session 9 (2026-06-30)

| Change | Details |
|---|---|
| ExtraEmily handle typo fixed | `_STREAMER_CATALOG["extraemily"]` and `streamers.md` corrected `@ExtraEmily` → `@ExtraEmilyy` |
| Clip cap scales with watch list size | 1 streamer → 5 clips/run, 2 → 3, 3+ → unchanged at 2. Added `_clips_per_streamer_cap()` |
| Tab order changed | Streamers, RAG, Operator (was Operator, EFM, RAG, Streamers). First tab is now the default landing view |
| Pending Publish panel added | New `GET /api/streamers/pending` + `POST /api/streamers/pending/{clip_id}/cancel`; frontend card shows the X-publish queue with per-clip cancel |
| Platform logo overlay on clips | Extends the canvas via ffmpeg `pad` (1080p → 1240p) to add a Kick/Twitch logo + `PLATFORM.COM/HANDLE` bar — original footage fully preserved below it. Rejected a frontend-only badge and a compositing overlay (both looked worse) |
| Logo assets | Pre-cropped/colorkeyed PNGs at `backend/assets/logos/{kick,twitch}.png`; `DejaVuSans-Bold.ttf` bundled locally for the handle text |
| Gotcha: `scale2ref` breaks tiny images | Collapsed a 151x51 logo to ~9x5px instead of scaling up. Fixed by `ffprobe`-ing real dimensions and computing overlay sizes as literal pixels |
| Gotcha: `ultrafast` preset bloats files 5-7x | `-preset ultrafast -tune zerolatency -bf 0` ballooned clips 50-100MB → 130-230MB, likely causing X-upload timeouts. Switched to `-preset veryfast` w/ B-frames — back to ~44-63MB at 2-3x slower encode |
| Gotcha: in-memory semaphore doesn't protect across processes | A standalone reprocessing script running alongside the live app's own fetch pipeline caused two concurrent ffmpeg encodes, nearly OOM-killing the pod. Replaced `threading.Semaphore` with an `fcntl.flock` on a shared file — serializes across every process |
| Gotcha: NiFi client timeout ≠ backend failure | A slow (bloated-file) upload timed out client-side but the backend completed the tweepy post anyway (confirmed via `.published.json`) — check backend state before assuming a NiFi timeout means real failure |
| Resumable batch pattern | Reprocessing scripts persist per-clip status to a JSON state file — a killed/interrupted run resumes without redoing finished clips |

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

