# The new Streamers brain on the DGX Spark — #272 and #271, planned

> **Status (2026-08-30):** planning only, from a NvidiaSpark-1 session. Nothing built, nothing deployed, no container or flow touched. This is the next-steps record for [#272](https://github.com/cldr-steven-matison/DesktopShare/issues/272) (New Streamers Brain) and [#271](https://github.com/cldr-steven-matison/DesktopShare/issues/271) (Streamer KB), written so any device can pick either up from history. The vLLM history that this builds on — Jun 28 through Aug 30, every model bump and every guard that got bolted on — is WindowsDesktop's research comment on #272.

I run the Streamers demo's caption path on a Qwen2.5-3B that shares an 8 GB 4060 with Whisper. Everything the caption code does today exists because that model is weak: a comprehension gate before the caption call, a 600-character transcript cut, four retry attempts against regex guards, and a blunt rule that bans every pronoun because the 3B guesses gender from a name. The DGX Spark has a 35B-class model with a 262K context on 128 GB of unified memory, and it already serves on this LAN. The job is a brain that uses that, on top of the same audio-to-text pipeline — not a URL swap.

## Decisions taken this session

1. **Validate on the Spark box first.** The live app on WindowsDesktop posts real tweets. It is untouched until a Spark-box validation proves the new brain end to end.
2. **Phased, core first.** Phase A below; accretion is Phase B.
3. **Identity and gender come from WindowsDesktop's Postgres streamers DB**, which is being built now. I do not design a gender source here. The gender wiring is **blocked on that schema** — I coordinate first and never guess it.
4. **On the Spark box I build a retrieval KB** — a vector index over clip history and context — that joins to Postgres for name and gender at caption time.
5. **Streamers is the demo. The Nvidia/Cloudera guide is separate work.** Repointing the demo's caption model at the Spark endpoint is a demo config choice. It is not the `nvidia-dgx-spark-k3s-cso.md` §9 cutover ladder, and it is not correlated with any WindowsDesktop→Spark service migration. No guide doc changes for this work.
6. **The new brain is four capabilities the 35B/GB10 unlocks**, all on top of the unchanged Whisper→transcript pipeline: see the clip, not just hear it; one smart reasoning pass instead of the retry scaffold; full-context fusion with memory; correct, confident gendering.

## What the pipeline does today

From `backend/services/streamers.py` in [cso-operator-app](https://github.com/cldr-steven-matison/cso-operator-app/blob/main/backend/services/streamers.py), read this session:

| Step | Where | What it does |
|---|---|---|
| Transcribe | `process_clip` 3528–3558 | Whisper on 16 kHz mono WAV |
| Junk title regen | `_generate_title` 3341 | title `1` / `.` → regenerate; **`except Exception: pass` at 3372 swallows every failure** |
| Short transcript | 3574–3580 | ≤6 words → quoted caption of the streamer's own words |
| Comprehension gate | `_comprehend_topic` 3236 | TOPIC + CONFIDENCE; kept only if word-overlap grounded and not LOW |
| Persona caption | 3593–3646 | system prompt with the pronoun ban (3602–3606); user prompt with one weak `Clip title: '{title}'` line (3641) and `transcript[:600]` |
| Retry loop | 3652–3712 | 4 attempts; `_clean_caption`, `_has_degenerate_repetition`, `_has_gendered_pronoun` (3126), `_has_fabricated_quote` |
| Fallback | 3714 | quoted post, never drop the clip |
| Assemble | `_build_tweet` 3377 | ≤280 chars + attribution suffix; the gif post reuses it |

Three facts that shape the plan. The caption path makes **zero retrieval calls** — `QDRANT_URL`/`EMBED_URL` in `config.py` are never imported by streamers.py. The clip fetchers (`_fetch_twitch_clips` ~2706, `_fetch_kick_clips` ~2776) carry `title, url, thumbnail_url, duration, created_at, view_count` and **no `description`**. And streamer identity is scattered: `_STREAMER_CATALOG` (2217, login→X handle), `_STREAMER_PATH_OVERRIDES` (2257, clip/gif/gif_post flags), `.watchlist.json`, `.face_layout.json`, `.gif_index.json`, `.published_history.json` on the `/clips` PVC — and no gender anywhere.

## The box, verified live 2026-08-30

| Port | Container | What | Note |
|---|---|---|---|
| `:8000` | `vllm-qwen36` | `nvidia/Qwen3.6-35B-A3B-NVFP4`, OpenAI `/v1/chat/completions`, 262K ctx | run with `chat_template_kwargs:{"enable_thinking":false}` for a bounded answer, or the budget goes to hidden reasoning (`nvidia-dgx-spark-local-kb.md` §4.4) |
| `:8001` | `tei-embed-bge` | `BAAI/bge-m3`, **1024-d**, `POST /embed {"inputs":"…"}` | the serving-tier standard |
| `:8002` | `tei-rerank-bge` | `bge-reranker-v2-m3`, `POST /rerank` | |
| `:8003` | `whisper-cpp` | large-v3, `POST /inference` multipart | `/v1/audio/transcriptions` 404s on this build |
| `:8080` | `tei-kb` | nomic 768-d | `desktopshare-kb` only — not for the streamer KB |
| `:6333` | `qdrant-kb` | Qdrant; only `desktopshare-kb` exists | the `streamer-kb` collection goes here |

Templates to copy, not rewrite: `files/issue-226/kb/ingest.py` (chunk → TEI → Qdrant `PUT /points`, uuid ids) and `files/issue-226/kb/kb_mcp.py` (query embed + search). **No vision model is in the #232 model lock** (`nvidia-dgx-spark-landscape.md` §6) — vision is an open item to settle on the box, not a given.

## #272 — New Streamers Brain: next steps

**B0. Coordination first — it unblocks gendering.** A `device:WindowsDesktop` issue asking for the Postgres streamers DB interface: a connection reachable from `spark-dd06` (192.168.1.203), the streamer key (bare Twitch login vs `kick:` prefix, as `_parse_watch_entry` does it), and the columns for canonical name, aliases, X handle, and gender/pronouns. Shared with #271.

**B1. The brain contract.** One structured call replacing comprehend → title → caption → 4× retry.

- Inputs: the **full** transcript; title and description **when meaningful** (`_is_junk_title` stays the gate — this is a supplementary signal, the transcript brain stays underneath); a KB context block (persona, recurring bits, past moments — from #271); an identity block (name, aliases, confirmed pronouns — from Postgres); visual context when B3 lands.
- Output, JSON: `{caption, topic, confidence, grounded, quote_verbatim, pronouns_ok, used_title}`. The model self-checks what the regex guards check today. The guards stay as one thin last line, the 4-retry scaffold goes. Quoted fallback and "never drop the clip" stay. `_build_tweet` is unchanged.
- Measure on the box before choosing: thinking on vs off for this task (latency vs caption quality), `max_tokens`, whether the frequency/presence penalties still earn their place on a 35B.

**B2. Validation harness on the Spark box — no prod, no queues, no X.** A standalone runner: real clip files → local `:8003` whisper → the B1 brain on local `:8000` → caption + self-check JSON printed next to what the current 3B produced for the same clip. It reuses the app's functions and lives under `files/issue-226/streamers/` in DesktopShare, not in the prod app path. Acceptance: ≥10 clips; 0 pronoun violations on known-gender streamers; 0 fabricated quotes; `used_title` true only on meaningful titles.

**B3. Vision — verify, then choose.** First check whether the locked Qwen3.6 accepts image content on this vLLM build (`/v1/models`, then a request with an `image_url` part). If it does not, pick a VLM that fits beside the lead in the memory budget, serve it, and record it in `nvidia-dgx-spark-landscape.md` §6. Input: a few frames sampled around the cut point — the gif branch already finds `cut_start` by peak audio, reuse that — plus the facecam box from `.face_layout.json`. Gate: the visual description measurably changes captions on thin-transcript clips, which is exactly where the 20–30 % pronoun-violation rate lives today.

**B4. Title and description as a used signal.** Extend `_fetch_twitch_clips` and `_fetch_kick_clips` to carry `description` where the API provides one — Twitch Helix clips have no description field; verify Kick. Feed title/description into B1 as one input among several. Fix `_generate_title` to log its failures instead of swallowing them.

**B5. Repoint the demo's caption model.** Phase A repoints only the validation harness. Flipping the running demo — `VLLM_URL`/`VLLM_MODEL` in `backend/config.py:7-9` and `k8s/configmap.yaml:6-7`, then `MODULES=streamers bash scripts/deploy.sh` after reading the running pod's `MODULES` — is a later step with its own fresh confirmation, and the rollback is those two values. WindowsDesktop's pod has to reach `192.168.1.203:8000`. Per the issue, #272 closes when this flip is done.

## #271 — Streamer KB: next steps

**K0. The same coordination issue as B0**, plus one question for WindowsDesktop: should `_STREAMER_CATALOG` and `_STREAMER_PATH_OVERRIDES` move into Postgres as the single roster, so the app reads one source and [`streamers.md`](streamers.md) stops being hand-synced? It is their DB, so it is their call.

**K1. Identity/gender contract — consume, don't design.** Per streamer the brain needs: canonical display name, aliases, twitch/kick logins, X handle, **pronouns (confirmed only)**, tone notes. Pronoun policy: a confirmed Postgres value is used as-is; unknown falls back to today's name-only rule; **nothing is ever inferred**. For known streamers this replaces the pronoun-ban block at 3602–3606 and the corrective retry at 3675–3689.

**K2. The retrieval KB on the Spark box.** Qdrant collection `streamer-kb` on `qdrant-kb :6333`, embedded with bge-m3 1024-d via `:8001`. A fresh collection, so the dimension choice is free; the app's 768-d `my-rag-collection` on WindowsDesktop is untouched. The indexer follows `ingest.py`: one point per clip/moment, payload `{streamer, source, clip_id, title, caption, transcript, created_at, kind}`, seeded from `.gif_index.json`, `.published_history.json` (last 500) and the `processed_clips` stream. Any new PVC state file goes through `_atomic_write_json` (streamers.py:103) under a lock — the rule in cso-operator-app's own `CLAUDE.md`.

**K3. Retrieval at caption time.** Query `streamer-kb` filtered by `streamer`, top-k, reranked via `:8002` if it helps, assembled into a context block (persona, recurring bits, last N moments) and passed into the B1 contract. The client follows the app's `backend/services/embedding.py` and `qdrant.py`.

**K4. Accretion — Phase B.** After each processed clip, upsert the transcript, caption and visual summary. Periodically the brain writes its own per-streamer persona summary ("who they are, recurring bits") stored as a `kind=persona` point. The KB gets richer the longer I watch someone, which is the whole point of #271.

## Order and gates

| Step | Depends on | Gate |
|---|---|---|
| B0/K0 issue to WindowsDesktop | — | schema received |
| B1 contract + B2 harness | — | 3B-vs-35B comparison on ≥10 clips |
| B4 title/description + `_generate_title` fix | — | `used_title` only on meaningful titles |
| K2/K3 retrieval KB | — | `streamer-kb` green at 1024-d; context visible in the assembled prompt |
| B3 vision | model capability check | measurable change on thin-transcript clips |
| K1 gender join | **B0 schema** | 0 violations; correct pronouns for known streamers; name-only for unknown |
| B5 demo model flip | all of the above, fresh confirm | #272 closes |
| K4 accretion | K2 | Phase B |

## What NOT to do

- Do not change `config.py` / `configmap.yaml` on the running demo as part of Phase A. The harness repoints; production waits for its own ask.
- Do not infer a streamer's gender from a name, a transcript, or a frame. Confirmed Postgres value or name-only — nothing in between.
- Do not index the streamer KB into `my-rag-collection` or `desktopshare-kb`. Fresh collection, its own dimension.
- Do not frame the model repoint as the §9 cutover ladder or edit the guide for it. Different work stream.
- Do not run the harness against the live `/clips` queues, Kafka topics, or X. `agent/live-queues.md` applies the moment anything touches the PVC.

## When this ships

Update [`cso-operator-app-streamers.md`](cso-operator-app-streamers.md) with the session log, [`README.md`](README.md)'s pipeline block (the vLLM row and the `process-clip` line) and its "What's next", [`streamers.md`](streamers.md) if the roster moves to Postgres, and `CLAUDE-CHECKIN.md`'s NvidiaSpark-1 block with the `streamer-kb` collection and any VLM container. Every "verify on the box" item above becomes an as-built line the day it runs.
