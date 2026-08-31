# The new Streamers brain on the DGX Spark — #272 and #271

> **Status (2026-08-31 — NvidiaSpark-1): the Spark side is BUILT and proven on real clips.** K2 `streamer-kb` seeded (46 points / 19 streamers, pronoun-free by construction); B2 `clip-prep` pod live (#282); B1+B3 `StreamerBrain` PG on `mynifi` behind the `:32111` door — 4/4 consecutive clips at ~6 s each, transcript + 6 frames + Postgres identity + KB → one grounded JSON answer; confirmed-pronoun (jynxzi he/him) and off-roster name-only (hutchmf) cases both correct; error path answers 500 JSON. Steven filled confirmed pronouns for all 17 active roster rows 2026-08-31. Exports/yaml under `files/streamers/`. **Next: #277 flips `BRAIN_DOOR_URL` to the contract posted there → ≥10 live clips in shadow.** *(Done 2026-08-31 afternoon — WindowsDesktop: contract-v2 app change `0d84a9c` deployed, `BRAIN_DOOR_URL`/`BRAIN_DOOR_TIMEOUT=90` set; FetchClips was STOPPED at flip time, the gate counts from the next clips that flow.)* Everything below stands as written; the earlier status lines are kept for history.
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

The **Streamer Knowledge Card** — a per-streamer X post with the GIF, our description, platform, cadence, topics, popularity — is its own enhancement issue rendered from these points. It is not part of #271 or #272.

## Order and gates

| Step | Depends on | Gate |
|---|---|---|
| K2 seed `streamer-kb` | seed files (have) | collection green at 1024-d; a search by `streamer_key` returns that streamer's profile |
| B2 `clip-prep` pod | — | `POST /prep` returns wav + frames for a real MP4 |
| B1 + B3 `StreamerBrain` PG, HTTP door | K1, K2, B2 | `curl -F /caption` returns the contract with a real transcript and `visual_summary` |
| #277 contract v2 + shadow on (WindowsDesktop) | B3 door up | ≥10 live clips side by side, gates above |
| K5 research PG | K2 | `kind=research` points visible in the assembled prompt |
| B4 promote | all above, fresh confirm | #272 closes |
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
