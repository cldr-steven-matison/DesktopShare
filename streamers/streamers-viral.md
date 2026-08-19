# Streamers — Viral Cross-Reference Pipeline (Plan)

**Status: planning only, nothing built yet.** Written 2026-07-20, same day as the Session 18 caption fixes and roster update in `cso-operator-app-streamers.md`.

## Goal

Right now the streamers pipeline posts a straight LLM reaction to whatever clip comes up in the fetch order. This is a second, independent posting stream: once an hour, post our own take on whichever roster clip had the most views in the last 24h — but instead of just reacting to the Whisper transcript, the caption should be informed by what's already happening about that clip/streamer on X (what other clippers said, what blew up, what the reaction was), so the caption can be a sharper, more "in on it" take instead of a generic hype reaction.

## Hard boundary — this is a separate process

**Everything here is new, parallel infrastructure. Do not touch `FetchClips`/`ProcessClips`/`PublishClip` or their cadence.** Reuse existing backend code/helpers where it's a real fit (streamer catalog, X publish client, vLLM call pattern, ffmpeg helpers) — but as calls *from* new PGs/endpoints, not edits *to* the existing three. Own Kafka topics, own NiFi process groups, own cron. If the existing pipeline and this one ever need to interact, that's a deliberate future decision, not a side effect of sharing code.

## Why not the official X API

Checked `config.py` — the app's X credentials (`X_API_KEY`/`X_ACCESS_TOKEN`) are OAuth1 user-context, wired for posting only. X's free API tier has no search/read access at all; that starts at the paid Basic tier (~$200/mo, as of last check). Decided against paying for it — instead, Stage 2 below is a NiFi flow that hits the public web directly (X's public pages, known clip-aggregator accounts, whatever sources turn out to actually work) rather than the official search API.

## Scope: roster only

This tracks streamers already in `_TWITCH_LOGINS`/`_KICK_LOGINS` (`backend/services/streamers.py`) — not platform-wide "who's going viral anywhere" discovery. Twitch has no site-wide trending-clips API anyway (only per-broadcaster/per-game), and Kick's site-level trending page isn't needed if we're only ranking clips from streamers we already track.

---

## Architecture overview

```
Stage 1: Daily Top Clips        Stage 2: X Cross-Reference       Stage 3: New-Take Caption      Stage 4: Hourly Post
(per roster streamer,           (public-web NiFi flow —          (vLLM call, but with           (separate cron/PG,
 both platforms, 24h             hits known X pages/accounts      cross-ref context injected      drains its own queue,
 window, ranked by views)        for "what's hot" on this          alongside the transcript)        1/hr pacing)
        │                        streamer/clip)                          │                                │
        └──────────────► candidate queue ──────────────► enriched caption ──────────────► posted, own topic
```

Four stages, each independently buildable and testable. None of them read from or write to the existing `new_clips`/`processed_clips` topics.

---

## Stage 1 — Daily Top Clips (roster-scoped)

For each streamer already in the roster, on both platforms, pull clips from the last 24h and rank by `view_count`.

| Platform | Mechanism |
|---|---|
| Twitch | `get_clips` already supports a time window (`started_at`/`ended_at`) and returns `view_count` — query per roster login with a 24h window, take top N. No new API capability needed, just a new call shape alongside the existing `_get_clips` |
| Kick | Current `_get_kick_clips` pulls the 20 most-recent per channel and sorts by `view_count` client-side, but has no date filter. Add a `created_at` ≥ 24h-ago filter on top of the existing per-channel call. Kick's site-wide trending page is **not** needed for this — roster-scoped ranking only needs each channel's own recent clips |

Output: one ranked shortlist per streamer per day (e.g. top 1-3 by views), feeding Stage 2.

**Open question:** does this run as a new NiFi PG (`InvokeHTTP` per roster entry, same shape as `FetchClips`) or a lightweight backend endpoint NiFi calls on a timer? Given the "NiFi owns the flow logic" direction from the existing NiFi-Native Refactor Plan (see `cso-operator-app-streamers.md`), lean NiFi-native for consistency, but not decided.

---

## Stage 2 — X Cross-Reference (public web, new NiFi flow)

For each Stage 1 candidate, hit the public web for what's already circulating about that streamer/clip — post text, engagement signal, the actual "what happened" narrative other accounts are running with.

**This is the riskiest, least-specified part of the plan.** `x.com`'s public search/profile pages are JS-heavy and inconsistently reachable without a logged-in session — this will need real iteration against actual scraped output once we're looking at it, not something fully specifiable ahead of time. Likely sources to try: known clip-curation accounts' profile pages, public search result pages, other aggregator sites that already do this kind of clip-tracking.

**Prerequisite to check before building anything else in this stage:** does `mynifi-0` actually have outbound internet egress to the open web? Every `InvokeHTTP` call in the existing flows so far has been either cluster-internal or made from the backend pod, not NiFi hitting arbitrary public URLs directly. This needs a real test (`InvokeHTTP` against something like `https://api.ipify.org` from inside the NiFi pod) before designing the rest of Stage 2 in detail.

---

## Stage 3 — New-Take Caption Generation

Feed the Stage 2 cross-reference text into the vLLM prompt as real context ("here's what's already being said about this") alongside the Whisper transcript, instead of transcript-only. This is the actual mechanism for "shocking, not just an LLM reaction" — the model needs something to react *to* beyond the raw clip content.

Reuses the `process_clip()` vLLM-call pattern (same `VLLM_URL`/`VLLM_MODEL` config, same client) but as a new function with a different prompt — not a modification of the existing caption prompt from Session 18.

**Dependency on the bigger-model test:** today's Session 18 work showed Qwen2.5-3B struggling to reliably follow even a single hard constraint (no gender pronouns) on a plain transcript-reaction prompt. Asking the same 3B model to synthesize two sources (transcript + scraped X context) into a sharper, more "in on it" take is a harder ask — this feature is a good real test case once bigger-model testing on the other device happens.

---

## Stage 4 — Hourly Posting Cadence

Separate cron/PG, own queue, drains one candidate per hour. Explicitly does **not** touch the existing `PublishClipPeakTimeCron` cadence or the regular pending-publish queue — runs alongside it as a second, independent posting stream, per the hard boundary above.

Can reuse `_publish_sync`'s chunked OAuth1 X upload logic (the actual signed-post mechanics don't change), called from this new flow's own trigger rather than the existing `/publish`/`/publish-next` endpoints.

---

## Open questions / prerequisites checklist

- [ ] Does `mynifi-0` have outbound internet egress? (blocks all of Stage 2 until checked)
- [ ] What specific X pages/accounts are actually scrapable without a login session? (needs hands-on iteration, not speculation)
- [ ] Stage 1: new NiFi PG vs. backend-endpoint-on-a-timer?
- [ ] Bigger-model test (separate device) — needed before Stage 3's dual-source caption quality can be trusted
- [ ] New Kafka topic naming (e.g. `viral_candidates`, `viral_posted`) — not yet chosen
- [ ] Rate/quality gate before Stage 4 posts — does a candidate need a minimum view count or cross-reference hit to qualify, or does top-1-by-views always post regardless?

## Related docs

- `cso-operator-app-streamers.md` — the existing (separate, untouched by this plan) fetch/process/publish pipeline this reuses code from
- `streamers.md` — roster source of truth
