# Streamers

Everything about the Streamers system lives in this folder. The code lives in
[`cso-operator-app`](https://github.com/cldr-steven-matison/cso-operator-app); these docs are
the design and operations record.

The pipeline watches Twitch and Kick for clips from a watch list, downloads them, burns a
platform overlay onto them, transcribes with Whisper, writes a caption with vLLM, queues them
in a review UI, and posts the approved ones to X as **@TunaStreetTest**. Real credentials,
real posts, live queue. A second path posts "streamer is live" alerts, and a third — a NiFi
chat bot — takes `!load`/`!matrix` commands from Twitch chat and drives four physical screens
across three machines.

Everything runs as NiFi process groups against a FastAPI backend. There is no standalone bot
process anywhere in this system.

**Live state in this README was read out of the running cluster on 2026-08-18** — the NiFi
flow and `GET /api/streamers/flows`, not the docs. Several of the raw docs below still carry
older schedules and PG names; where they disagree with this page, this page was checked and
they were not. Check live yourself before acting on either.

---

## What's actually running

| System | State |
|---|---|
| Clip pipeline — `FetchClips` → `ProcessClips` → review → publish | **Live**, posting |
| `LiveStreamerAlert` — "streamer is live" posts to X | **Live** |
| `PostWatchList` — daily watch-list post, tagging X handles | **Live** |
| `TwitchChatBot` — `!load` / `!matrix` / `!watchlist` → 4 screens | **Live** |
| `WatchlistChatJoiner` — joins watchlisted channels, greets, removes on offline | **Live** |
| Inspector — one-shot chat/clip probe for any login | **Live** (Streamers tab) |
| `WatchlistChatSnapshotPoller` + `TopStreamerJoiner` (chat activity, #89) | `TopStreamerJoiner` **live 2026-08-21** (#200) — own-channel branch only; `WatchlistChatSnapshotPoller` still stopped |
| `TunaStarLinkFlows` | **Disabled** |
| Viral stream, Kick posting bot, OBS overlay phases 1-4, Talking Tuna mascot | Plans only |

## The process groups

Seven under the `StreamersApp` parent PG, plus four at NiFi root. Schedules are UTC —
`mynifi-0` runs UTC, not local.

| PG | Trigger | State |
|---|---|---|
| `FetchClips` | `0 0/4 18-23,0-2 * * ?` | RUNNING |
| `ProcessClips` | ConsumeKafka `new_clips` | RUNNING |
| `PublishClipPeakTimeCron` | `0 0/23 18-23,0-2 * * ?` | RUNNING |
| `PublishClipOffPeakDay` | `0 0 11-17 * * ?` | RUNNING |
| `LiveStreamerAlert` | `PollTimer`, `0 0/30 18-23,0-2 * * ?` | RUNNING |
| `PostWatchList` | `0 50 22 * * ?` | RUNNING |
| `TunaStarLinkFlows` | 5 min timer | DISABLED |
| `TwitchChatBot` (root) | persistent IRC socket | RUNNING |
| `WatchlistChatJoiner` (root) | `TriggerCycle`, 15 min | RUNNING |
| `WatchlistChatSnapshotPoller` (root) | `TriggerCycle`, ~2 min | stopped |
| `TopStreamerJoiner` (root) | `OwnChannelTrigger` cron 10 min; discovery `TriggerCycle` cron 1 hr | own-channel branch **running**; discovery branch stopped |

**There are two publishers, not one.** `PublishClipPeakTimeCron` covers the peak window and
`PublishClipOffPeakDay` covers 11:00–17:00 UTC hourly. The docs below describe a single
`PublishClip` PG that was "retired" and `DISABLED` — that PG was **renamed** to
`PublishClipOffPeakDay` and it is running. `STREAMER_PG_NAMES` in `services/streamers.py`
carries the new name; `TRIGGER_REQUESTS` still carries the old `PublishClip` string, which is
why `agent-trigger.sh PublishClip` works and routes to `PublishClipPeakTimeCron`'s
`TriggerInput`.

## Pipeline

```
Twitch Helix + GQL  /  Kick unofficial web API
      │
      ▼
FetchClips        GenerateFlowFile → InvokeHTTP POST /api/streamers/fetch-clips
                  backend: OAuth → clip list → GQL VideoAccessToken_Clip → MP4 → /clips/<id>.mp4
                           → burn platform overlay + glitch intro → PublishKafka new_clips
      ▼
ProcessClips      ConsumeKafka new_clips → InvokeHTTP POST /api/streamers/process-clip
                  backend: whisper-service:8001/transcribe → vllm-service:8000/v1/chat/completions
                           → PublishKafka processed_clips
      ▼
Review UI         watch · edit caption · Approve → .pending_publish.json
      ▼
PublishClipPeakTimeCron / PublishClipOffPeakDay
                  InvokeHTTP POST /api/streamers/publish-next → pops one pending clip
      ▼
X                 tweepy v1 media_upload(chunked=True) + v2 create_tweet
```

`LiveStreamerAlert` is a separate leg, not part of this one: `PollTimer` → `GetRoster` →
split → per-platform live check → `DedupLiveSession` (`DetectDuplicate`, 72h age-off) →
`GetXHandle` → `XLivePostProcessor` → a reply post with the platform URL. It also pins any
discovered-live streamer onto the watch list via `AddToWatchlist`, which is **not** dry-run
gated — it always writes.

## On-demand trigger

Every flow can be fired once, out of band, without touching its schedule:

- `Trigger` = `ListenHTTP` on port **9080**, base path `contentListener`, header
  `X-Trigger-Request` captured as an attribute → `RouteOnAttribute` → the target PG's
  `TriggerInput` port.
- Reachable at `http://mynifi.cfm-streaming.svc.cluster.local:9080/contentListener`.
  `mynifi` is headless (`ClusterIP: None`), so any pod port resolves by DNS with no Service.
- The header lands as the literal attribute name `X-Trigger-Request`, so the routing EL needs
  quoted-attribute syntax: `${'X-Trigger-Request':equals('LiveStreamerAlert')}`.
- Backend: `POST /api/streamers/flows/trigger/{name}`, gated by `TRIGGER_REQUESTS` in
  `backend/services/streamers.py` — that allow-list is the only gate. Anything not on it lands
  in NiFi's auto-terminated `unmatched` and vanishes silently. Adding a flow to the list plus
  wiring its `TriggerInput` makes it triggerable with no script change.

## Services, topics, storage

| Thing | Value |
|---|---|
| App (external) | `http://127.0.0.1:8090` via `minikube tunnel` |
| App (from NiFi) | `http://cso-operator-app.default.svc.cluster.local:8090` — NodePort 30090 is external-only and times out |
| Whisper | `POST http://whisper-service.default.svc.cluster.local:8001/transcribe` |
| vLLM | `POST http://vllm-service.default.svc.cluster.local:8000/v1/chat/completions`, `Qwen/Qwen2.5-3B-Instruct` |
| Kafka | `my-cluster-kafka-bootstrap.cld-streaming.svc:9092`, topics `new_clips` / `processed_clips`, **1 partition each** |
| Chat activity topic | `twitch_chat_activity`, 3 days retention (staged, not flowing) |
| NiFi | `mynifi-0`, namespace `cfm-streaming`, image 2.6.0 (2.x is required for Python processors) |
| Storage | PVC at `/clips` — MP4s plus `.seen_clips.json`, `.skipped.json`, `.published.json`, `.pending_publish.json`, `.watchlist.json`, `.fetch_mode.json` |

`StreamersApp` itself lives on the NiFi pod's `emptyDir`, not a PVC. A `kubectl delete pod
mynifi-0` wipes the entire flow — it has happened, and it took a restore from a flow export.

## Operating it

**Deploy.** Read the running pod's `MODULES` first, every time, and match it exactly:

```bash
kubectl exec -n default deploy/cso-operator-app -- env | grep MODULES   # currently rag,streamers,efm
cd ~/cso-operator-app && make deploy MODULES=rag,streamers,efm
```

`build-modules.py` only treats `streamers` as a real module — it gates the backend router
registration. `rag` and `efm` only toggle frontend tabs. `MODULES=all` shows the Streamers tab
but 404s every `/api/streamers/*` call, because the backend checks for the literal string.

**Credentials.** Ten keys, injected with `kubectl set env deploy/cso-operator-app` after any
deploy that resets the pod, never in `deployment.yaml` or `configmap.yaml`:
`NIFI_USERNAME`, `NIFI_PASSWORD`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`,
`KICK_CLIENT_ID`, `KICK_CLIENT_SECRET`, `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`,
`X_ACCESS_TOKEN_SECRET`. A `deployment.apps/... unchanged` result means they survived — check
that, not just rollout status. NiFi's own X credentials are separate: they live in the
`streamers-x-creds` Parameter Context bound to `StreamersApp`.

**Telegram.** Scripts are in [`../files/`](../files/), driven through the OpenClaw bot.
The one hard rule: OpenClaw's `/bash` needs a `bash -c "..."` wrapper for anything beyond a
single bare command — `&&` chains, `source`, and backgrounding (`&`) don't reliably run
without it; the bot may just chat back instead of executing.

**Agent commands.** All scripts live under `DesktopShare/files/`. Each command below is a
complete, standalone block — copy the whole line and paste it to the bot as-is. They are
kept one-per-block on purpose: they're what you actually copy and send, not a template to
fill in.

post now (that streamer's queued clip)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-PostNow.sh xqc"
```

start fetch clips
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-fetchClips.sh start"
```

stop fetch clips
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-fetchClips.sh stop"
```

approve posts
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-approvePosts.sh"
```

show watch list
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh show"
```

rotate watch list
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh rotate"
```

add to watch list without replacing it (`t:` = Twitch, `k:` = Kick)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh add t:jasontheween"
```
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh add k:n3on"
```

replace the whole watch list
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh t:extremely k:deenthegreat"
```

start PublishClipPeakTimeCron
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-publishFlow.sh PublishClipPeakTimeCron start"
```

stop PublishClipPeakTimeCron
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-publishFlow.sh PublishClipPeakTimeCron stop"
```

trigger LiveStreamerAlert (one on-demand run)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-trigger.sh LiveStreamerAlert"
```

trigger FetchClips (one fetch, without touching the FetchClips PG's start/stop state)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-trigger.sh FetchClips"
```

trigger PublishClip (routes to `PublishClipPeakTimeCron`'s `TriggerInput`, not the disabled `PublishClip` PG)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-trigger.sh PublishClip"
```

trigger PostWatchList (posts the current watch list to X — bot-confirmed 2026-07-26)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-trigger.sh PostWatchList"
```

`start`/`stop` toggles a PG's continuous/cron operation. `agent-trigger.sh` fires one flowfile
through `StreamersApp`'s shared `Trigger` (`ListenHTTP` → `RouteOnAttribute`) into the target
flow's `TriggerInput` port — it never touches schedulers or PG run state. The backend's
`TRIGGER_REQUESTS` allow-list is the single source of truth for valid names.

**API.** `/api/streamers/*` — clips (`fetch-clips`, `process-clip`, `queue`, `clip/{id}`,
`approve`, `skip`, `publish`, `publish-next`, `pending`, `pending/{id}/cancel`,
`pending/{id}/publish-now`, `published`, `reset`, `fetch-mode`), watch list (`watchlist`,
`/add`, `/remove`, `/rotate`, `roster`, `x-handle/{login}`), flows (`flows`,
`flows/{name}/start|stop`, `flows/trigger/{name}`, `flows/LiveStreamerAlert/run-once`,
`flows/LiveStreamerAlert/refresh-oauth`), live status (`live`, `live-bulk`, `live-now`), and
inspection (`inspect`, `inspect/chat`, `inspect/queue-clip`, `chat-activity/{login}`,
`chat-activity/{login}/tail`, `discover/top`, `topics`).

## Rules that break things when ignored

This is a live posting queue. [`../agent/live-queues.md`](../agent/live-queues.md) and
[`../agent/incident-rules.md`](../agent/incident-rules.md) are the authority; these are the
ones specific to this system.

**NiFi**

- **Never GET-then-PUT a processor entity that has sensitive properties.** `GET` masks them as
  the literal `"********"`, and PUTting that back writes the mask as the real value. This has
  destroyed live X credentials once and `TwitchChatReplyProcessor`'s twice. Use a narrow
  property-only PUT, `PUT /processors/{id}/run-status`, or a Parameter Context. Bundle-version
  bumps on those processors go through the NiFi UI's `Change Version`, never a script.
- **`Retry` is not `Failure`.** Auto-terminating `Retry` on `InvokeHTTP` silently drops rate
  limits and transient 5xx. Self-loop it with a bounded `FlowFile Expiration` and route
  `Failure`/`No Retry` to a shared log sink.
- **`mynifi-0` runs UTC.** The `18-23,0-2` wraparound windows on `FetchClips`,
  `PublishClipPeakTimeCron` and `PollTimer` are EDT-derived and need revisiting at the
  November DST change.
- Custom Python processors need NiFi 2.x and a PVC-backed extensions dir. A live `minikube
  mount` bridge does not work on this WSL2/docker host.
- `FlowFileSource` cannot consume an incoming FlowFile at all — a FlowFile routed into one
  queues forever. Chat-joining logic uses `FlowFileTransform` for exactly this reason.
- `SplitJson` on a bare JSON string array writes unquoted raw scalars, so the split FlowFiles
  aren't valid JSON and `EvaluateJsonPath` fails. Use `ExtractText`.
- Port **4557** is already taken by `LiveStreamerAlert`'s `LiveAlert MapCacheServer`. A second
  `MapCacheServer` on the default port silently reverts to `DISABLED` with no bulletin.

**ffmpeg**

- **Pin libx264 to one thread everywhere** — `-threads 1 -x264opts
  threads=1:sliced-threads=0`. ffmpeg reads the host's 24 CPUs, not the pod's 1-CPU limit. The
  symptom is a silent zero-frame encode with no exception, or an OOM SIGKILL.
- `-bf 0` on every intro segment. B-frame segments concat fine and then crash VLC at the splice.
- Trimming for the X duration cap must **re-encode**. A stream copy overshoots to the next
  keyframe and lands back over the limit.
- Never trust the platform's reported clip duration — `ffprobe` the real file. A Twitch clip
  self-reporting 59.9s ran 257.9s after overlay.

**Queue**

- **`getmany()` is a one-shot poll, not a drain.** After a `seek()` it returned 2 of 20 sought
  messages and hid 13 ready clips from Review. Loop it until the consumer position reaches the
  known end offset, bounded.
- A failed publish requeues at the **front** of the pending queue by design. One permanently
  failing clip blocks everything behind it.
- All `.pending_publish.json` read-modify-writes go through `fcntl.flock`. In-memory semaphores
  don't protect across processes — a standalone script running beside the app started a second
  ffmpeg encode and nearly OOM-killed the pod.
- Never hand-inject into a live trigger, and never cancel or reorder a queued item without an
  explicit per-instance ask. To check a trigger endpoint exists, use an inert name — firing a
  real flow name really queues a flowfile.

**Deploy**

- **Confirm fresh before every redeploy, and check live NiFi state first.** An earlier "deploy
  is okay" does not cover a later one. Redeploying mid-fetch has caused real data loss three
  times (`unexpected end of stream` on `FetchClips`' InvokeHTTP).

**Roster**

- [`streamers.md`](streamers.md)'s Clip/GIF table mirrors `_STREAMER_PATH_OVERRIDES` in
  `backend/services/streamers.py`. The two are kept in sync by hand — change one, change both.
- No streamer goes on the roster without a known X handle.
- `_clips_per_streamer_cap()` scales 5 / 3 / 2 / 1 clips per streamer for 1 / 2 / 3 / 4+
  watched. Because `LiveStreamerAlert` auto-adds every discovered-live streamer and the same
  watch list drives `FetchClips`, watching the full roster collapses it to 1 clip each.
- A rotate only takes effect on the next `FetchClips` stop/start — NiFi reads the watch list
  once at flow start.

## What's next

- **NiFi-native refactor** of fetch/process/publish. Designed in detail, largely unbuilt.
  `XLivePostProcessor` proves the text-post half; extending it to chunked media upload is the
  remaining piece. Recommended order is publish → process → fetch. `ClipOverlayProcessor` is
  the riskiest piece — when it's built, lift `_burn_platform_overlay`/`_burn_glitch_intro`
  verbatim rather than re-deriving the thread and B-frame flags.
- **Chat activity go-live (#89).** Both PGs are valid and stopped, backend and frontend are
  written but not deployed. Blocked on a second real Twitch bot identity for
  `TopStreamerJoiner` (its credentials are `REPLACE_ME_*` placeholders and `DRY_RUN=true`),
  and on two stuck `KafkaTopic` finalizers on `new-clips`/`processed-clips`.
- **Clip quality / scale gating.** Open design question. The lever is already free: Twitch's
  live-status response returns `viewer_count`, so `FetchClips` could skip a streamer entirely
  below a threshold.
- **Longer video.** `media_category="amplify_video"` is a one-line change and @TunaStreetTest
  already has X Premium, but the code never sets it, so the standard 140s cap applies.
- **Subtitles.** Unblocked — existing OAuth1 credentials are enough. The only blocker is that
  the Whisper server computes `return_timestamps=True` and then returns only `result["text"]`,
  discarding the `result["chunks"]` needed to build the SRT.
- **Video title / description / CTA.** Not settable on organic posts at all. Possible through
  the X Ads API without paying for promotion, but there's no Ads account for @TunaStreetTest
  and no ads credentials. Punted, don't re-investigate.
- **Posting cadence.** Two publishers now run. The X-growth research in
  [`../research/x-clip-usertags.md`](../research/x-clip-usertags.md) says 3–5 posts/day gets
  the best engagement per post; current schedules allow well above that.
- **DST changeover in November** — see the UTC note above.
- **`StreamersApp.json` snapshot is stale.** The committed export in `cso-operator-app` predates
  the current PG set, including the `PublishClipOffPeakDay` rename. Re-export it.

## The docs in this folder

Raw working docs, kept as-is. This README is the summary; these are the detail.

| Doc | What it is | State |
|---|---|---|
| [`cso-operator-app-streamers.md`](cso-operator-app-streamers.md) | The anchor doc — pipeline, deploy, endpoints, gotchas, and a 22-session history tail | Reference + log; schedules and PG names lag live |
| [`streamers.md`](streamers.md) | The roster: Twitch + Kick streamers, X handles, Clip/GIF path per streamer | Live reference, mirrors `_STREAMER_PATH_OVERRIDES` |
| [`streamers-twitch-bot.md`](streamers-twitch-bot.md) | Chat bot architecture, credentials, `WatchlistChatJoiner` | Live; its screen-mapping sections are superseded |
| [`streamers-twitch-bot-mpv-plan.md`](streamers-twitch-bot-mpv-plan.md) | The mpv + yt-dlp migration; **authoritative for screen loading** | Built and live on all four screens |
| [`streamer-kick-bot.md`](streamer-kick-bot.md) | Kick chat read path (Pusher, no auth) and the Inspector page; §4 is a posting-bot plan | §1–3 live, §4 plan only |
| [`streamers-chat-activity-plan.md`](streamers-chat-activity-plan.md) | Chat polling, engagement-ratio bot detection, cross-channel chatter index (#89) | Built, staged, not deployed |
| [`cso-operator-app-streamers-xapi.md`](cso-operator-app-streamers-xapi.md) | X API v2 media reference — chunked upload, metadata, subtitles | Reference; describes a v2/OAuth2 model the pipeline does not use yet |
| [`cso-operator-app-streamers-tuna.md`](cso-operator-app-streamers-tuna.md) | The Talking Tuna mascot — clip overlay and live co-host | Plan + prototype, not wired in |
| [`streamers-viral.md`](streamers-viral.md) | A second posting stream captioned from scraped X context | Plan only |
| [`streamer-products.md`](streamer-products.md) | Market research on streamer software/SaaS spend | Research only |
| [`twitch-overlay-tunastarlink-plan.md`](twitch-overlay-tunastarlink-plan.md) | OBS overlay for @tunastarlink | Phase 0 live, phases 1–4 planned |
| [`streamers-original-architecture.md`](streamers-original-architecture.md) | The original 2026-06 clipping-pipeline sketch | Historical |
| [`cso-operator-app-streamers-review-2026-07-17.md`](cso-operator-app-streamers-review-2026-07-17.md) | Full-series audit of the streamers docs | Historical |

### Two doc conflicts, resolved

- **Tuna avatar: HeyGen is the settled direction.** `cso-operator-app-streamers-tuna.md`'s
  upper sections commit to a fully local pipeline (Wav2Lip/SadTalker + Piper), but its
  2026-07-17 session log is the ground truth: local Wav2Lip was tried and rejected
  ("absolutely horrible" on flat cartoon art), the drawn mouth-flap composite was tried and
  rejected ("still looks crappy chopped"), and HeyGen works — real avatar ID
  `be03a5aa65f946da8cf066a7708332cd`, working multi-line batched render code, creds in
  `.env.local` under `files/tuna-test/`. Piper itself was never disproven — it simply drops
  out with the local route. This matches open issue #50 (HeyGen POC).
- **Chat-bot credentials: resolved — the migration landed 2026-07-25.** `streamers-twitch-bot.md`
  §5.1 and §9 now agree and are both current: `Client Secret` and `Refresh Token` are
  `twitch-chat-bot-creds` Parameter Context references, re-verified live 2026-08-21 via the
  context's `referencingComponents`. The conflict this entry used to record was real only
  before that date. **The "rotation" follow-on was a misdiagnosis, corrected 2026-08-21 (#202):**
  measured against the live Twitch API, the refresh grant returns the *same* refresh token, so the
  seed never went stale and a restart never needed a re-auth on its own. The `"********"` mask
  destroying the stored token was the real cause, and binding to the Parameter Context on
  2026-07-25 already fixed it.
  **Don't re-open this from `flow.json.gz`** — a parameter-referenced sensitive property
  persists there as `enc{...}`, indistinguishable from a literal (issue #199).
