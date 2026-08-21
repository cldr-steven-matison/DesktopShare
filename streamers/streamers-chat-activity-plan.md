# Streamers Chat Activity — continuous polling, watchlist recording, presence bot

**Status (2026-08-02):** Built, not yet live. All 5 phases below are implemented for issue [#89](https://github.com/cldr-steven-matison/DesktopShare/issues/89) — backend code, both new NiFi process groups, frontend live mode. Nothing has been deployed or started yet; see §8 for exactly what's pending and why.

## 1. What this is

Issue #89 asked for a broad set of chat-bot improvements: a continuously-updating chat/viewer view instead of the current short snapshot, having the watchlist bot actually record who's chatting (not just its own join event), a new bot to expand chat presence to non-followed top streamers, and eventually a Grafana dashboard. After aligning scope with Steven, three pieces are in scope for this plan:

1. **Continuous chat/viewer polling** — the Users/Bots page currently runs a one-shot 10–60s capture (`inspector.inspect_chat()`); it should show an ongoing view for watchlisted channels.
2. **Watchlist bot records real chat activity** — `WatchlistChatJoiner` currently only publishes its own join/greet event to Kafka (`twitch_chat_joined`); it needs to record per-user chat activity as people enter/interact.
3. **New "join top non-followed streamers" bot** — pure chat-presence expansion, no automatic watchlist-seeding via followers (explicitly descoped).

**Out of scope this pass:** Grafana dashboarding (follow-up issue once real activity data exists), and any direct dependency on botted.wtf (see §4 — inspiration only, no integration).

## 2. Why the first design was rejected — scale

The first draft of this plan called for a new NiFi custom processor holding one persistent IRC socket, joined to every watchlisted channel at once, publishing **one Kafka message per individual chat line**. Steven flagged this before any implementation: some watchlisted streamers (e.g. xQc-scale channels) can sustain dozens of messages/second with tens of thousands of unique chatters. A raw per-message firehose would have meant:

- FlowFile-per-message in NiFi — provenance-repo pressure and backpressure from FlowFile *count*, independent of payload size.
- An in-memory backend aggregator with no eviction policy, growing unbounded per stream over hours.
- JSON snapshot files rewritten every 30s ballooning on big channels.
- SSE pushing every raw line to an open browser tab, flooding it.

**Resolution: don't build a firehose — poll.** The existing one-shot `inspector.inspect_chat()` (`backend/services/inspector.py`) is already scale-safe: hard-capped at `_MAX_MESSAGES = 4000`, returns only the top 40 chatters and top 10 spam clusters, bounded capture window. Instead of a persistent multi-channel IRC listener, NiFi re-runs that existing bounded capture **on a timer** per watchlisted channel (e.g. every 1–2 min) and publishes each cycle's result as one summary message. This means:

- No new custom NiFi processor at all — pure native-processor chain (`GenerateFlowFile` → `InvokeHTTP` → `PublishKafka`), which is a *better* fit for this app's own convention (custom Python only for what NiFi can't hold natively — see `nifi-and-ai` skill) than the firehose design was.
- Resource use per channel is now **constant**, bounded by the existing capture caps, regardless of whether the channel has 10 or 50,000 chatters.
- "Continuous" becomes "refreshes every 1–2 minutes" rather than true per-message real-time — an acceptable reading of "keep a streaming view," confirmed with Steven.

## 3. Design decisions (settled)

- **Pieces 1+2 share one pipeline.** A new NiFi PG polls `inspect_chat()` per watchlisted (Twitch-only) channel on a timer and publishes each snapshot to a new Kafka topic `twitch_chat_activity`. Backend consumes it into a persisted per-streamer store and streams updates to the frontend. No raw per-message capture anywhere in this design.
- **Persistence**: plain JSON snapshot files under `CLIP_STORAGE_PATH/.chat_activity/<streamer>.json`, matching this app's existing (imperfect, accepted) JSON-file persistence convention — not a new database. One long-lived backend aggregator consumer (new: first background `asyncio.create_task` in this app's `lifespan()`) maintains the latest snapshot + a short rolling history per streamer; separate short-lived per-connection SSE consumers serve live tails (mirrors `services/kafka.py::tail()`'s existing per-request pattern).
- **Engagement-ratio bot-likelihood flag** (adopted from botted.wtf, see §4): `engagement_ratio = unique_chatters / viewer_count`; flag `bot_flag_likely` when ratio < 10% and viewer_count ≥ 100 (both thresholds tunable constants). Computed inside `inspector.inspect_chat()` itself, so both the existing one-shot inspector and the new periodic snapshot pipeline get it for free — it's a few-line addition on data already being returned.
- **Cross-channel chatter identity tracking** (adopted from botted.wtf, see §4): a username-keyed index (`.chat_activity/_chatter_index.json`) mapping `username → {channels_seen: {streamer: last_seen_ts, message_count}, first_seen}`, updated by the aggregator on every snapshot. Each chatter/bot entry gets annotated with `cross_channel_count` before being persisted/served — an account showing up as an active chatter across many different watchlisted channels is a real bot-farm signal the original per-channel-only design didn't catch, and it's what makes the "persisted store" requirement do more than log per-channel data.
- **Piece 3 trigger cadence**: its own local `CRON_DRIVEN` (UTC) timer, standalone PG — *not* wired into the shared `Trigger`/`RouteOnAttribute`/`TriggerInput` circuit used by `StreamersApp.json`'s newer flows. A same-app precedent (`ManualPollTrigger`, added and removed same-day on 2026-07-23) showed layering a second trigger mechanism onto a PG broke it, and there's no on-demand use case for background presence-expansion the way there is for `FetchClips`/`PublishClip`. Revisit batching into the shared circuit later if more flows want it.
- **Piece 3 reuses `WatchlistChatJoinerProcessor` unchanged** (already login-agnostic via its `STREAMER_ATTRIBUTE` property) as a second instance with its own `BOT_USERNAME`/`CLIENT_ID`/`CLIENT_SECRET`/`REFRESH_TOKEN`/`GREETING_MESSAGE`, matching this app's existing separate-bot-identity precedent. It does **not** call `add_to_watchlist` — that would wrongly feed the clip-pulling pipeline, which is out of scope here.
- **Twitch-only** for both the snapshot poller and the discovery bot, matching `WatchlistChatJoiner`'s existing structural boundary (`FilterKickEntries`) — no posting-capable Kick chat path exists in this app yet.

## 4. botted.wtf — what it is, what we're taking, what we're not

Steven asked to look at [botted.wtf/tools](https://www.botted.wtf/tools) before finalizing detection design.

**What it is:** an independent fraud-detection/authenticity database for Twitch/Kick/Rumble streamers — flags channels using artificial engagement, and separately vets legit creators for brand deals. Explicitly built on "public APIs and live monitoring," no platform partnerships — same category of access we already have.

**Their methodology** (5 signals, sampled every 30s): concurrent viewers, unique chatters (rolling 30-min window), active chatters, messages/minute (normalized against category baselines), and a "lexical fingerprint" for synthetic-vs-organic message patterns (vague marketing language, no real technical detail exposed). Flag rule: engagement rate < 10% AND ≥100 concurrent viewers.

**Their tools:** StreamScan (live single-channel audit — basically what our polling redesign already gives us), Viewer Intel (Kick-only, tracks accounts that "hop between known botted channels" — a real idea we didn't have), VOD Downloader and OBS overlays (archival/visualization, not detection, not adopted).

**Decision: remake, don't integrate.** No public API, and it'd be a silent third-party dependency for no real benefit — everything genuinely useful is cheap to build with data we already have or already planned to collect:
- Engagement-ratio flag → adopted, §3.
- Cross-channel chatter tracking → adopted, §3 (our version of "Viewer Intel," generalized to Twitch since that's our only posting-capable platform today).
- Lexical fingerprint → **not** adopted — too vague to replicate meaningfully, and our existing `_find_message_clusters` heuristic (identical text across many senders) already covers the closest actionable case.

## 5. Phased implementation

### Phase 0 — Kafka topic
- `cso-operator-app/streamers/kafka-topics.yaml`: add `twitch-chat-activity` / `spec.topicName: twitch_chat_activity` as a proper Strimzi `KafkaTopic` CRD (3 partitions/3 replicas, `retention.ms: "259200000"` — 3 days). This also fixes forward the gap where the existing `twitch_chat_joined` topic was never declared as a CRD, without touching that topic.
- Verify: `kubectl get kafkatopic twitch-chat-activity -n cld-streaming` → `Ready`; `GET /api/kafka/all-topics` lists it.

### Phase 1 — Backend
- `backend/services/inspector.py`: add `engagement_ratio` and `bot_flag_likely` fields to `inspect_chat()`'s response (uses `viewer_count`/`unique_chatters` already computed there); new module constants `_ENGAGEMENT_RATIO_THRESHOLD = 0.10`, `_ENGAGEMENT_MIN_VIEWERS = 100`.
- `backend/config.py`: `TOPIC_CHAT_ACTIVITY: str = "twitch_chat_activity"`.
- `backend/services/chat_activity.py` (new):
  - `tail_streamer(streamer) -> AsyncIterator[dict]` — per-connection `AIOKafkaConsumer` (`auto_offset_reset="latest"`), same shape as `services/kafka.py::tail()`, filtered to one streamer.
  - `start_aggregator()`/`stop_aggregator()` — one long-lived consumer over the whole topic. Per snapshot received: updates `.chat_activity/_chatter_index.json` (cross-channel index), annotates each chatter/bot with `cross_channel_count`, stores latest snapshot + short rolling history per streamer, persists to `.chat_activity/<streamer>.json`. On start, loads existing snapshot files before consuming.
- `backend/main.py`: in `lifespan()`, guarded by `"streamers" in _enabled_modules` (same guard the streamers router already uses), start/stop the aggregator task.
- `backend/routers/streamers.py`: `GET /chat-activity/{login}` (snapshot + short history, field-shape-compatible with `ChatInspectResult`), `GET /chat-activity/{login}/tail` (SSE, mirrors `routers/kafka.py::tail()`'s `StreamingResponse` shape).
- Verify: publish a few fake snapshot-shaped messages to `twitch_chat_activity` with a throwaway `aiokafka` producer script; confirm the GET and SSE routes work and a snapshot file survives a backend restart.

### Phase 2 — NiFi: new isolated PG `WatchlistChatSnapshotPoller`
- `cso-operator-app/streamers/WatchlistChatSnapshotPoller.json` (new export, built live first). Native chain, no custom processor:
  `TriggerCycle` (`GenerateFlowFile`, `TIMER_DRIVEN`, ~2 min) → `FetchWatchlist` (`InvokeHTTP GET /api/streamers/watchlist`) → `SplitWatchlistLogins` (`SplitJson`) → `ExtractStreamerAttr` (`ExtractText`) → `FilterKickEntries` (`RouteOnAttribute`, Twitch-only — same shape as `WatchlistChatJoiner`'s existing filter) → `InvokeHTTP GET /api/streamers/inspect/chat?login=${streamer}&chat_seconds=30` → `PublishKafka_2_6` (topic `twitch_chat_activity`, key `${streamer}`).
- Fully isolated PG, zero connections to `WatchlistChatJoiner`'s live canvas, per the `nifi-and-ai` isolation convention.
- Verify: per `agent/incident-rules.md`, dump live flow state and ask before starting; confirm `twitch_chat_activity` depth climbing; confirm end-to-end via Phase 1's routes against a real watchlisted login. Re-export the JSON after the session.

### Phase 3 — Frontend: live mode for Users/Bots
- `frontend/src/lib/api.ts`: snapshot type/client call for `GET /chat-activity/{login}`; SSE tail via the existing `openSSE()` helper.
- `frontend/src/components/StreamersPage.tsx`, `UsersBots` component: check `login` against `api.streamersWatchlist()` (Twitch only — Kick always falls back to the existing one-shot path). If watchlisted: `openSSE()` on the tail endpoint plus a periodic GET for the latest snapshot — copy `KafkaActivity.tsx`'s existing SSE+interval hybrid directly. Show `bot_flag_likely`/`engagement_ratio` as a warning badge, and `cross_channel_count` per chatter row. Otherwise: today's one-shot behavior, unchanged.
- Verify: open Users/Bots on a watchlisted Twitch login, confirm it updates every poll cycle without a manual re-click; confirm non-watchlisted logins are unaffected.

### Phase 4 — Piece 3: `TopStreamerJoiner` (independent, can run in parallel with 1–3)
- `backend/services/streamers.py`: `discover_top_unfollowed(client, limit=5)` — Twitch Helix `GET /streams` with no `user_login` (viewer_count-desc default), diffed against `get_roster()` (the broader known-catalog set, not just the active watchlist).
- `backend/routers/streamers.py`: `GET /discover/top`. Explicitly does **not** call `add_to_watchlist`/`set_watchlist`.
- `nifi-custom-processors/WatchlistChatJoinerProcessor.py`: unchanged, reused as a second processor instance.
- `cso-operator-app/streamers/TopStreamerJoiner.json` (new export): standalone PG — `GenerateFlowFile` (`CRON_DRIVEN`, UTC, ~30–60 min) → `InvokeHTTP GET /discover/top` → `SplitJson` → `ExtractText` → `JoinAndGreet` (new `WatchlistChatJoinerProcessor` instance, own credentials/greeting, `DRY_RUN=true` initially). No Kafka publish, no shared-trigger wiring.
- Verify: run once manually with `DRY_RUN=true`, confirm via logs it picks genuinely-new logins correctly. Flip `DRY_RUN=false` only after an explicit fresh ask, confirm real JOIN+greet lands, then leave the CRON timer running.

### Phase 5 — Docs / export cleanup
- Confirm all live-built flow JSONs (`WatchlistChatSnapshotPoller.json`, `TopStreamerJoiner.json`) are freshly re-exported and committed.
- Check `streamers/README.md` (or equivalent) for a topic list that needs `twitch_chat_activity` added alongside `new_clips`/`processed_clips`.

## 6. Critical files

- `backend/services/inspector.py`, `backend/services/kafka.py`, `backend/services/streamers.py`, `backend/routers/streamers.py`, `backend/main.py`, `backend/config.py`
- `nifi-custom-processors/WatchlistChatJoinerProcessor.py` (reused unchanged)
- `streamers/WatchlistChatJoiner.json`, `streamers/kafka-topics.yaml`
- `frontend/src/components/KafkaActivity.tsx`, `frontend/src/components/StreamersPage.tsx`, `frontend/src/lib/api.ts`

## 7. Process notes

- Report progress and blockers on [issue #89](https://github.com/cldr-steven-matison/DesktopShare/issues/89) (comment + `status:review` when delivered — the issue stays open until Steven closes it, per `agent/device-comms.md`).
- Any live NiFi build session: dump live flow first, ask before starting/stopping a PG, re-export JSON afterward (`agent/incident-rules.md`).

## 8. Implementation status (2026-08-02)

All 5 phases built. Nothing started/deployed yet — one combined confirmation is still needed before anything goes live (see "What's pending" below).

**Built:**
- **Phase 0** — `twitch-chat-activity` Strimzi `KafkaTopic` CRD applied, confirmed `Ready`, visible via `/api/kafka/all-topics`. (Along the way, found two unrelated month-old stuck `KafkaTopic` finalizers on `new-clips`/`processed-clips` — real broker topics unaffected, confirmed via `kafka-topics.sh --list`. Steven approved clearing them but the `kubectl patch` itself was blocked by the local permission classifier both times it was attempted from this session — still stuck as of this writing, see §8 pending list below.)
- **Phase 1** — `inspector.py` engagement-ratio fields, `chat_activity.py` (aggregator + cross-channel index + SSE tail), `main.py` lifespan wiring, two new routes in `routers/streamers.py`. Verified: an offline unit test of the index/persistence logic, and a real produce/consume round-trip against the live broker confirming the JSON payload shape matches exactly.
- **Phase 2** — `WatchlistChatSnapshotPoller` PG built live via the NiFi REST API (7 native processors, no custom code), all `VALID`, exported to `streamers/WatchlistChatSnapshotPoller.json`. Left **stopped**.
- **Phase 3** — `UsersBots` component live mode (watchlist-membership check, SSE tail, engagement/cross-channel badges). `tsc --noEmit` clean.
- **Phase 4** — `discover_top_unfollowed()` + `/discover/top` route. `TopStreamerJoiner` PG built live (5 processors, reuses `WatchlistChatJoinerProcessor` unchanged as a second instance), exported to `streamers/TopStreamerJoiner.json`. Left **stopped**.

**What's pending:**
- ~~**A real second Twitch bot identity for `TopStreamerJoiner`.**~~ **Done 2026-08-21 (#200).** Its own Twitch app (`TopStreamerJoiner`, client `2esm418w`, Confidential — a Public client is not usable here, the processor's refresh grant sends a client secret and the property is `required=True`). Same `tunastreettest` account, own device-code grant, own refresh-token seed, so it cannot race the watchlist bot. `Client Secret`/`Refresh Token` are `#{twitch-chat3-client-secret}` / `#{twitch-topstreamer-bot-refresh-token}` in `twitch-chat-bot-creds` — **which also had to be bound to the PG**, it had no Parameter Context at all until #200. `Dry Run=false` and the PG is live, but only the own-channel branch: see §5 Phase 4.
- **The two stuck `KafkaTopic` finalizers (`new-clips`/`processed-clips`) are still stuck.** Steven approved clearing them, but `kubectl patch kafkatopic ... --type=json -p='[{"op":"remove","path":"/metadata/finalizers"}]'` was blocked by the session's local permission classifier on both attempts — not something a re-ask resolves, needs either a Bash permission rule added or Steven running the two patch commands directly (given in-conversation). Unrelated to this issue's original scope — surfaced along the way, real broker topics unaffected either way.
- **One combined go-live check, not yet done**: both PGs are built+valid+stopped, backend/frontend code is written+typechecked but not deployed to the running pod. Starting the pollers means real IRC connections and real Twitch/Kick API calls on a schedule — deploying the backend means a pod restart. Per `agent/incident-rules.md`, this needs a fresh live-flow-state check and an explicit ask immediately before it happens, not an earlier general go-ahead.
