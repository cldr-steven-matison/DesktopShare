# The new Streamers brain on the DGX Spark — #272 and #271

> **Status (2026-09-06 — NvidiaSpark-1): K5 external research BUILT and running; the #281 Knowledge Card door BUILT.** `StreamerResearch` PG on `mynifi` (daily 06:17 UTC): Twitch Helix app token / Kick public API for platform facts and the week's top clips, Google News + Bing News + r/LivestreamFail RSS for what is circulating, the 35B writes two dated `kind=research` points per roster streamer into `streamer-kb` and deletes that streamer's `prior`; pronoun-free by construction (model rule → RouteOnContent → one rewrite → mechanical they/their scrub). First pass 2026-09-06 covered the 8 Kick streamers; the Twitch leg waits on the Twitch app id/secret in `~/.env`. The brain's KB scroll `limit` went 10 → 30 (one ReplaceText, targeted PUT). `StreamerCard` PG behind `:32112` — `GET /kb`, `POST /card/preview` (jynxzi: 912 chars, he/him used, self-check true; off-roster hutchmf: name-only), `POST /card/publish` → `PostToX` (tweepy, same calls as the app's `_publish_sync`). **Live since the evening of 2026-09-06:** #301 delivered the keys, #302 deployed the app tab, first real card posted (extraemily, long-form + GIF: https://x.com/TunaStreetTest/status/2096717526583435561); `Dry Run` is `false`. App side (deployed by WindowsDesktop, #302): `BRAIN_CARD_URL`, `/streamers/kb/*` routes, a **Streamers KB** tab with the selected card on top and Generate → review → Post to X, `KB →` links from the Watchlist chips and roster rows. Details: §K5 as-built and §"#281 — Knowledge Card" below.
>
> **Status (2026-08-31 — NvidiaSpark-1): the Spark side is BUILT and proven on real clips.** K2 `streamer-kb` seeded (46 points / 19 streamers, pronoun-free by construction); B2 `clip-prep` pod live (#282); B1+B3 `StreamerBrain` PG on `mynifi` behind the `:32111` door — 4/4 consecutive clips at ~6 s each, transcript + 6 frames + Postgres identity + KB → one grounded JSON answer; confirmed-pronoun (jynxzi he/him) and off-roster name-only (hutchmf) cases both correct; error path answers 500 JSON. Steven filled confirmed pronouns for all 17 active roster rows 2026-08-31. Exports/yaml under `files/streamers/`. **Next: #277 flips `BRAIN_DOOR_URL` to the contract posted there → ≥10 live clips in shadow.** *(Done 2026-08-31 afternoon — WindowsDesktop: contract-v2 app change `0d84a9c` deployed, `BRAIN_DOOR_URL`/`BRAIN_DOOR_TIMEOUT=90` set; gate met same evening — 19/20 review clips carried both captions, 3B 0-for-20 vs brain 19/19. **B5 promoted 2026-09-01** (app `c7f12a9`): the brain writes the posted caption, 3B path is fallback-only.)* Everything below stands as written; the earlier status lines are kept for history.
>
> **Status (2026-08-30, evening — WindowsDesktop):** B0/K0 delivered — [#276](https://github.com/cldr-steven-matison/DesktopShare/issues/276) (the `streamer_brain` view + role, reachable from spark-dd06 over the tailnet; pronouns populated + confirmed for all 18 rows 2026-08-31 — `she/her` for bbjess/extraemily, `he/him` for the rest); [#278](https://github.com/cldr-steven-matison/DesktopShare/issues/278) seed pulled to `files/issue-226/streamers/seed/`; [#277](https://github.com/cldr-steven-matison/DesktopShare/issues/277) shadow mode built and deployed **disabled** (`BRAIN_DOOR_URL` unset — waiting on the door); [#279](https://github.com/cldr-steven-matison/DesktopShare/issues/279) Watchlist grid live.
>
> **Status (2026-08-30, evening — NvidiaSpark-1):** rewritten after a full re-read of both issues, Steven's comments, and the WindowsDesktop deliveries ([#276](https://github.com/cldr-steven-matison/DesktopShare/issues/276) Postgres view, [#277](https://github.com/cldr-steven-matison/DesktopShare/issues/277) shadow mode built and deployed disabled, [#278](https://github.com/cldr-steven-matison/DesktopShare/issues/278) seed, [#279](https://github.com/cldr-steven-matison/DesktopShare/issues/279) Watchlist grid). Every fact about the box below was verified live this session. Nothing on the Spark side was built that day.
>
> This doc is the record for [#272](https://github.com/cldr-steven-matison/DesktopShare/issues/272) (New Streamers Brain) and [#271](https://github.com/cldr-steven-matison/DesktopShare/issues/271) (Streamer KB), written so any device can pick either up from history. The vLLM history it builds on — Jun 28 through Aug 30 — is WindowsDesktop's research comment on #272; two of that comment's "what to build" items (title/description as a primary signal; repoint the base URL) were struck by Steven and are not in this plan.

I run the Streamers demo's caption path on a Qwen2.5-3B that shares an 8 GB 4060 with Whisper. Everything the caption code does today exists because that model is weak: a comprehension gate before the caption call, a 600-character transcript cut, four retry attempts against regex guards, and a blunt rule that bans every pronoun because the 3B guesses gender from a name. The DGX Spark has a 35B-class model with a 262K context on 128 GB of unified memory, it sees images, and it already serves on this LAN. The job is a brain that evaluates the whole clip — audio and visual — with what we know about the streamer, and answers once.

## This is the Streamers demo, not the DGX guide

The DGX guide EPIC ([#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226), work-streams A–K, the `nvidia-dgx-spark-*.md` docs, `files/issue-226/`) and this work share the box and nothing else. The brain uses the endpoints the guide work stood up; it writes nothing back into a guide doc, the EPIC, or its decision log. Anything the brain needs on the box — flows, yaml, ingest scripts — lives under `files/streamers/`, and the box's `CLAUDE-CHECKIN.md` block lists it as a streamers service.

## Decisions

1. **Validate on the Spark box first, in shadow mode.** The live app on WindowsDesktop posts real tweets. It keeps captioning with the 3B until the brain proves itself side by side.
2. **The whole clip ships.** Per request, WindowsDesktop sends the clip's MP4 to the Spark; the box splits it, transcribes it, looks at it, and answers. Nothing stateful moves — the `/clips` PVC, the queues, Kafka, the review UI and the credentials stay on WindowsDesktop.
3. **Identity and pronouns come from WindowsDesktop's Postgres** — the `streamer_brain` view ([#276](https://github.com/cldr-steven-matison/DesktopShare/issues/276), live). Confirmed value or name-only; nothing is ever inferred from a name, a transcript, or a frame.
4. **The Streamer KB is about the streamer, not the clips.** A RAG checkpoint in the caption path so the post is never stupid about who the person is. Clips are inputs to it, never its contents.
5. **The X post logic is inclusive of all four:** the streamers database, the Streamer KB, the clip's transcript, and the clip's visual state.
6. **Title and description are supplementary.** Used when meaningful (`_is_junk_title` stays the gate), never the driver. No fetcher changes, no `_generate_title` work.
7. **New services on the box are k3s pods** in committed yaml, not docker runs. Whisper `:8003` is used as it is.

## What the pipeline does today

From `backend/services/streamers.py` in [cso-operator-app](https://github.com/cldr-steven-matison/cso-operator-app/blob/main/backend/services/streamers.py) at `origin/main` `c359de6`:

| Step | Where | What it does |
|---|---|---|
| Transcribe | `process_clip` | Whisper on 16 kHz mono WAV |
| Junk title regen | `_generate_title` | title `1` / `.` → regenerate |
| Short transcript | `process_clip` | ≤6 words → quoted caption of the streamer's own words |
| Comprehension gate | `_comprehend_topic` | TOPIC + CONFIDENCE; kept only if word-overlap grounded and not LOW |
| Persona caption | `process_clip` | system prompt with the pronoun ban; user prompt with one `Clip title: '{title}'` line and `transcript[:600]` |
| Retry loop | `process_clip` | 4 attempts; `_clean_caption`, `_has_degenerate_repetition`, `_has_gendered_pronoun`, `_has_fabricated_quote` |
| Fallback | `process_clip` | quoted post, never drop the clip (`d803e50`: pronoun/empty/degenerate failures fall back too) |
| Shadow hook | `_shadow_brain_caption` (~3902) | if `BRAIN_DOOR_URL` is set: POST `{clip_id, streamer, source, title, description, transcript}` after the 3B caption is final; reply lands as `brain_caption` + `brain`; never raises ([#277](https://github.com/cldr-steven-matison/DesktopShare/issues/277)) |
| Assemble | `_build_tweet` | ≤280 chars + attribution suffix; the gif post reuses it |

The caption path makes **zero retrieval calls**. Identity: the roster is in Postgres ([#275](https://github.com/cldr-steven-matison/DesktopShare/issues/275)); `_STREAMER_CATALOG` / `_STREAMER_PATH_OVERRIDES` are seed and fallback only; the `streamer_brain` view carries `display_name, aliases, x_handle, pronouns (NULL unless confirmed), pronouns_confirmed, notes, active` keyed by `streamer_key` (`login` / `kick:login`). Today all 17 rows have `pronouns` NULL — Steven enters them in the Watchlist tab ([#279](https://github.com/cldr-steven-matison/DesktopShare/issues/279)).

## The box, verified live 2026-08-30

| Port | What | Verified |
|---|---|---|
| `:8000` | `nvidia/Qwen3.6-35B-A3B-NVFP4`, vLLM 0.28.0, OpenAI `/v1/chat/completions`, 262K ctx | **Takes `image_url` and sees**: given a Twitch thumbnail it named the game, the facecam, the viewer count and the on-screen timer. Run with `chat_template_kwargs:{"enable_thinking":false}` (`reasoning_tokens: 0`). |
| `:8001` | `BAAI/bge-m3`, `POST /embed` | 1024-d |
| `:8002` | `bge-reranker-v2-m3`, `POST /rerank` | up |
| `:8003` | whisper.cpp large-v3 CUDA, `POST /inference` multipart | 200 on a wav; `/v1/audio/transcriptions` 404s |
| `:6333` | Qdrant | only `desktopshare-kb` exists; `streamer-kb` is to be created |
| `mynifi-0` | NiFi 2.6.0, CFM operator, `cfm-streaming` | 7/7 Running; from inside the pod: the internet, the Twitch CDN, `:8000/:8003/:6333` on `192.168.1.203`, and WindowsDesktop Postgres `192.168.1.121:5432` are all reachable |
| Kafka `my-cluster` | Strimzi, `cld-streaming`, NodePorts 32100–32103 | Running — and not used by the brain (see "What NOT to do") |
| ffmpeg | — | **absent** in the NiFi pod and on the host |

Not verified and not quoted: free memory (`nvidia-smi` reports N/A on unified memory). The measured residents are in the serving-tier notes; the brain adds one small CPU pod.

## Where it runs — two NiFis, one seam

Everything that owns state stays on WindowsDesktop. The Spark contributes stateless inference as a NiFi Process Group.

**`StreamerBrain` — a new PG on the Spark's `mynifi`.** `HandleHttpRequest /caption` (multipart: `clip_id, streamer, source, title, file=<mp4>`) → `InvokeHTTP` to the **`clip-prep` pod** (MP4 → 16 kHz wav + sampled frames) → `InvokeHTTP :8003/inference` with the wav (the multipart-reconstruction leg from the MiNiFi router is the precedent) → identity lookup on `streamer_brain` (DBCP to `192.168.1.121:5432`, password in a Parameter Context) → Streamer KB retrieval (`:8001` embed → `:6333` search filtered by `streamer_key`) → one `InvokeHTTP :8000` with transcript + frames + identity block + KB block + title → self-check routing → `HandleHttpResponse`. Own PG, `Retry` self-looped with an expiry, failures to one log sink. Export to `files/streamers/flows/StreamerBrain.json` the session it is built.

**The seam.** HTTP door first — synchronous, which is what `process_clip` expects. Site-to-site is the upgrade once the door works. The Spark's own Kafka is not the seam: coupling the brain to the live `new_clips` / `processed_clips` topics is `agent/live-queues.md` territory.

**The contract.** In: `{clip_id, streamer, source, title}` + the MP4. Out: `{caption, topic, confidence, grounded, quote_verbatim, pronouns_ok, used_title, visual_summary, transcript}`. The model self-checks what the regex guards check today; the guards stay as one thin last line on the WindowsDesktop side. This replaces the transcript-only payload [#277](https://github.com/cldr-steven-matison/DesktopShare/issues/277) built — one more WindowsDesktop change, posted on that issue with the door URL.

**Validation is shadow mode.** `process_clip` keeps the 3B caption *and* fires the clip at the door; `brain_caption` lands beside `caption` in review; nothing auto-posts from it. Real live clips, real side-by-side, zero queue changes.

## #272 — New Streamers Brain: steps

**B1. The brain contract.** One structured call replacing comprehend → title → caption → 4× retry. Inputs: the full transcript from `:8003`; the sampled frames; the identity block (display name, aliases, confirmed pronouns or none, notes); the Streamer KB block (profile, guidance, research); the title when it passes `_is_junk_title`. Output as above. Measure on the box before choosing: frame count and sampling, `max_tokens`, whether the frequency/presence penalties still earn their place, whether this vLLM build's `video_url` can take the MP4 directly for the visual leg (it would not remove the wav step).

**B2. `clip-prep` pod.** A k3s Deployment + Service on the box (`files/streamers/clip-prep.yaml`, arm64 image with ffmpeg and a small HTTP server, no GPU): `POST /prep` multipart MP4 → wav + N frames (evenly across the clip plus one at the audio peak — the gif branch's `cut_start` idea, reimplemented here because the brain owns the visual sampling policy). Own issue.

**B3. The `StreamerBrain` PG**, shape above. Prove with `curl -F` and a clip MP4 before anything on WindowsDesktop changes. Then post the door URL + contract on #277; WindowsDesktop sets `BRAIN_DOOR_URL`. Acceptance: ≥10 live clips with `brain_caption` beside the 3B caption; 0 pronoun violations on confirmed-pronoun streamers; 0 fabricated quotes; `visual_summary` present on every clip; `used_title` true only on meaningful titles.

**B4. Promote the brain.** `process_clip` uses `brain_caption` as `caption`; the 3B path becomes the fallback when the door is unreachable. Own confirmation; rollback is un-promoting the field. Then the S2S upgrade. #272 closes when the demo's captions come from the brain.

## #271 — Streamer KB: steps

**K1. Identity — consume the view.** `SELECT * FROM streamer_brain WHERE streamer_key = $1 AND active`. Confirmed pronouns are used as-is; NULL means the name-only rule; nothing is inferred. For known streamers this replaces the pronoun-ban block and the corrective retry.

**K2. The collection.** Qdrant `streamer-kb` on `:6333`, bge-m3 1024-d via `:8001` (fresh collection; the app's 768-d `my-rag-collection` and the box's `desktopshare-kb` are untouched). A handful of points per streamer, payload `{streamer_key, kind, text, updated_at, source}` with `kind ∈ {profile, guidance, research}`. **Seed:** `files/streamers/kb/seed_profiles.py` reads each streamer's transcripts and captions from `files/issue-226/streamers/seed/` (#278 — inputs only) and has the 35B write the first profile and guidance points. No clip is stored.

**K3. Retrieval at caption time.** Inside the PG: that streamer's points, assembled into the KB block for B1. Rerank via `:8002` only if the point count ever makes it matter.

**K4. Accretion.** After a captioned clip, the brain may update the streamer's profile — a new bit, a new topic — not append the clip. Later phase.

**K5. External research per streamer** (Steven, #271). A scheduled PG on the Spark's `mynifi`: per roster streamer, platform profile and schedule from the Twitch Helix / Kick APIs (the Kick Cloudflare block seen from a bare host may apply from the pod — check), top clips by views, what public web and clip-aggregator pages are saying — summarised by the 35B into `kind=research` points. `streamers-viral.md` Stage 1–2 is the design to reuse; its open egress question was about WindowsDesktop's NiFi — the Spark's has egress. Chat-activity signals (`streamers-chat-activity-plan.md`) join when [#89](https://github.com/cldr-steven-matison/DesktopShare/issues/89) goes live.

**K5 as built (2026-09-06).** `files/streamers/flows/build_streamer_research.py` → `StreamerResearch.json`, a root PG on the Spark's `mynifi` (shared helpers in `flowgen.py`; row pitch 200, column pitch 600). `ListRoster` (ExecuteSQLRecord, Quartz `0 17 6 * * ?`, `RUN_ONCE` for an ad-hoc pass) reads the active rows of `streamer_brain`; one FlowFile per streamer; `RoutePlatform` sends Twitch rows through Helix `users` (content) then `channels`, `channels/followers` (app token → `total` only), `streams`, `clips` (last 7 days, by views), `schedule`, `videos` (VOD dates → cadence) — bearer from a `StandardOauth2AccessTokenProvider` (client_credentials, secret in the request body, the pattern already live in `WatchlistChatJoiner`) — and Kick rows through `kick.com/api/v2/channels/{login}` + `/clips?sort=view&time=week` (both reachable from `mynifi-0`, no Cloudflare block). Both legs then read Google News RSS (`when:14d`, `<description>` HTML dropped), Bing News RSS and r/LivestreamFail search RSS. Every source lands as an attribute (`Response Body Attribute Name`, size caps 2–48 KB) so a dead source never stops the streamer's refresh. One 35B call (thinking off, JSON) returns `platform_text`, `buzz_text`, `topics`, `facts`, `sources`; `CheckPronouns` (RouteOnContent) → one rewrite call → `CheckPronounsAgain` → a four-step ReplaceText scrub (he/she→they, him→them, his/her/hers→their, himself/herself→themself — the seeder's map); then two points per streamer: `research/platform` (`verified:true`, text opens `RESEARCH — platform facts (as of DATE, Twitch Helix|Kick public API)`) and `research/press` (`verified:false`, opens `RESEARCH — what is circulating (as of DATE, news + r/LivestreamFail + platform clips)`), ids `md5("<key>::research-<sub>::0")` as UUIDs so a run overwrites, embedded via `:8001`, `PUT …/points?wait=true`, then `POST …/points/delete` for that streamer's `kind=prior`. Parameter Context `StreamerResearch`; sensitive/credential values set with `files/streamers/flows/set_params.py` from `~/.env` (`STREAMER_BRAIN_DB_PASSWORD`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`). First run 2026-09-06: 9 Kick FlowFiles, ~10 s per 35B call, 18 research points landed (61 points in the collection, `prior` gone for every Kick streamer); the 8 Twitch rows wait at `HelixUser` until the Twitch credentials land. Two lessons from that run, both folded into the generators: `EvaluateJsonPath` must use Return Type `json` (auto-detect refuses the `topics`/`sources` arrays), and **Qdrant closes idle keep-alive sockets after 5 s** — the first upsert after the model call died with `Broken pipe` on 3 of 9 streamers (the body replayed fine by hand), so every Qdrant/TEI-facing `InvokeHTTP` now carries `Socket Idle Timeout = 1 sec`, the brain's `FetchStreamerKb` included (a stale socket there meant a caption without its KB). One answer in nine needed the mechanical pronoun scrub. `x.com` itself is not a source — its public pages are a JS shell and the syndication endpoint rate-limits (probed from the box); twitchtracker / sullygnome / streamscharts block bots. `kb_dump.py` (`files/streamers/kb/`) prints what the collection holds.

## #281 — Streamer Knowledge Card

A per-streamer long-form X post (the account is Premium) with one of our GIFs: hook line (≤ 260 chars, what the timeline shows before "Show more"), Who, Streams, Known for, Numbers, Lately, Follow — written by the 35B from IDENTITY (the roster's `streamer_brain` contract, confirmed pronouns and handle only) plus the KB's profile, guidance and research points, and posted **from the Spark's NiFi** through the proven X-post processor shape (Steven's call, 2026-09-06: NiFi accepts a request from the app and publishes; reuse the framework that already posts to X).

- **Door:** `files/streamers/flows/build_streamer_card.py` → `StreamerCard.json`, HandleHttpRequest `:8092`, NodePort `32112` (`files/streamers/streamer-card-door.yaml`). Routes: `GET /kb?streamer=<key>` (the collection, or one streamer's points, as `{"points":[payload…]}`); `POST /card/preview` — header `X-Identity-B64` = base64 JSON `{streamer_key, platform, login, display_name, aliases, pronouns, x_handle, notes}`, empty body → `{card_text, hook, char_count, hook_chars, pronouns_ok, grounded, kb_points, kb_as_of, brain, …}`; `POST /card/publish` — body = the GIF bytes (`image/gif`), headers `X-Identity-B64` + `X-Card-B64` = base64 JSON `{text, hook, clip_id}` → `{tweet_id, tweet_url, dry_run, degraded, media_path, posted_at}` or 500 JSON. Base64 headers because card text carries emoji; the GIF stays the FlowFile content down the whole publish leg. Nothing posts without the reviewed text coming back on `/card/publish` (review-first, `agent/live-queues.md`).
- **`PostToX`** (`files/streamers/processors/PostToX.py`, NiFi 2.x Python `FlowFileTransform`, on the `custom-python-extensions` PVC next to `SendTelegram.py`, loaded via `files/issue-289/python-extensions-loader.yaml` + `kubectl cp`, discovered without a restart): tweepy `API.media_upload(chunked=True, media_category="tweet_gif")` + `Client.create_tweet` — the same calls as the app's `_publish_sync`; four sensitive X creds bound to `#{X …}` parameters; `Dry Run` (parameter, default `true`); degrade paths surfaced as attributes — `x.media_path=v2` if the v1.1 upload host refuses (X documents `POST /2/media/upload` initialize/append/finalize for new code), `x.degraded=short` if the long text is rejected (error 111 / too long) and the ≤ 280-char hook is posted instead. GIF guard ≤ 15 MB and GIF magic bytes.
- **Card prompt lessons (2026-09-06):** the seed guidance's "do not assume gender / use neutral terms" line made the model mark `pronouns_ok:false` even with he/him confirmed, and it padded "Lately" with "recent activity shows…" when no research existed. Both fixed in the system prompt: confirmed pronouns override the guidance line; no dated research → no Lately, no numbers. After the fix: jynxzi 912 chars, he/him, `pronouns_ok`/`grounded` true; hutchmf (unconfirmed) name-only with `they`.
- **App (cso-operator-app, authored on this box, deploy is WindowsDesktop's):** `BRAIN_CARD_URL` / `BRAIN_CARD_TIMEOUT` in `config.py`; `GET /streamers/kb/cards` (identity + points + the streamer's latest posted GIF, else latest good one), `POST /streamers/kb/{platform}/{login}/card/preview`, `POST …/card/publish` (`{text, hook, clip_id}` → ships `/clips/{clip_id}.gif` to the door; a real post is appended to `.published_history.json` as `kind:"card"` and stamped `card_tweet_url` on the gif entry, under the existing locks); frontend **Streamers KB** tab — gallery of every active streamer (GIF, name, platform, point count, "researched DATE"), the selected card on top with its GIF picker, identity, the KB blocks, Generate card → editable text with char/hook counters and the self-check flags → Post to X (confirm dialog); `KB →` from each Watchlist chip and each roster row preselects the streamer. `BRAIN_CARD_URL` empty = the tab is read-only.
- **Gates — met 2026-09-06.** Door `GET /kb` and previews proven; WindowsDesktop deployed the tab (#302, app `99076ab`) and rendered all 17 streamers; credentials landed via #301; dry-run publish through the door answered `dry_run:true`; then Steven flipped `Dry Run` to `false` and posted the **first live Knowledge Card from the app: extraemily, 1,254-char long-form post + an 8.8 MB GIF, v1.1 media path, no degrade** — https://x.com/TunaStreetTest/status/2096717526583435561. **`Dry Run` is now `false` and stays so: the card feature is live**, the human review in the tab (Generate → read → Post to X) is the gate. Flip back with `set_params.py StreamerCard 'Dry Run=literal:true'`.

## Order and gates

| Step | Depends on | Gate |
|---|---|---|
| K2 seed `streamer-kb` | seed files (have) | collection green at 1024-d; a search by `streamer_key` returns that streamer's profile |
| B2 `clip-prep` pod | — | `POST /prep` returns wav + frames for a real MP4 |
| B1 + B3 `StreamerBrain` PG, HTTP door | K1, K2, B2 | `curl -F /caption` returns the contract with a real transcript and `visual_summary` |
| #277 contract v2 + shadow on (WindowsDesktop) | B3 door up | ≥10 live clips side by side, gates above |
| K5 research PG | K2 | `kind=research` points visible in the assembled prompt — **built 2026-09-06**; Kick half of the roster researched the same day, Twitch half on the app credentials; brain scroll limit 30 |
| B4 promote | all above, fresh confirm | #272 closes — **done 2026-09-01** |
| #281 card door + `PostToX` | K2, K5 | **met 2026-09-06** — first live card posted from the app (extraemily) |
| #281 app tab (WindowsDesktop deploy) | card door | **met 2026-09-06** (#302, `99076ab`) — 17 cards rendered, preview → post round-trip live |
| S2S | B4 | the demo-grade seam |
| K4 accretion | K2 | later |

## What NOT to do

- Do not move the `/clips` PVC, the queues, Kafka topics, or credentials to the Spark. Per-clip media crosses the wire; storage never does.
- Do not store clips in `streamer-kb`. Points are about the streamer.
- Do not promote `brain_caption` to `caption` as part of shadow mode.
- Do not infer a streamer's gender from a name, a transcript, or a frame.
- Do not index into `my-rag-collection` or `desktopshare-kb`.
- Do not let the Spark NiFi consume the live `new_clips` / `processed_clips` topics as the seam.
- Do not edit a `nvidia-dgx-spark-*` doc, the guide, or the EPIC from this work.
- Do not add a docker-run service to the box for this; k3s yaml.

## When this ships

Update [`cso-operator-app-streamers.md`](cso-operator-app-streamers.md) with the session log, [`README.md`](README.md)'s pipeline block and "What's next", and `CLAUDE-CHECKIN.md`'s NvidiaSpark-1 block with `streamer-kb`, the `clip-prep` pod and the `StreamerBrain` door — as streamers services on the box.
