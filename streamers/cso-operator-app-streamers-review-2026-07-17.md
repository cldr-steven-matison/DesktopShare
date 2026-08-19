---
layout: single
title: "Streamers Module Review — 2026-07-17"
date: 2026-07-17
classes: wide
categories:
  - review
tags:
  - streamers
  - nifi
  - review
---

Full line-by-line review, requested after the video-length trim incident. Scope: every file in the streamers module I've written or touched — `backend/services/streamers.py` (2049 lines), `backend/routers/streamers.py` (285 lines), `backend/config.py`, `frontend/src/components/StreamersPage.tsx` + `frontend/src/lib/api.ts` (targeted, not full-file), and `~/nifi-custom-processors/XLivePostProcessor.py` (148 lines). **No changes applied — this is findings only, for review before anything gets touched.**

## The one that actually matters

**I re-solved a problem that was already solved in the same file, and used a weaker fix.**

`backend/services/streamers.py:727-730`, inside `_burn_glitch_intro`'s `encode_still` helper, has this comment — written in an earlier session, months before today's incident:

> `-threads 1` + `threads=1:sliced-threads=0` matches `_burn_platform_overlay` — without it, libx264 auto-detects the *host's* full core count (seen: threads=24) instead of the pod's 1-CPU cgroup limit, which produced silent zero-frame encodes under this pod's actual constraints even though the same command worked fine on an unconstrained machine.

That is **exactly** the bug I spent today's session diagnosing from scratch in `_publish_sync`'s trim step — same root cause (`threads=24` from host CPU detection vs. the pod's real 1 CPU / 1Gi limit), same symptom (silent failure that looked like a corrupt-file mystery). `_burn_platform_overlay` (line 666-671) and every `encode_still`/xfade/vstack call in `_burn_glitch_intro` (lines 666-843) already use `-threads 1 -x264opts threads=1:sliced-threads=0` for this reason. Both of those functions run on **every single fetched clip** and have apparently never hit this failure — because they're already capped correctly.

The trim step in `_publish_sync` (added session 17, commit `ae2c8cd`, before I existed in this project) never got that same treatment. That's the actual root cause of both the 2026-07-16 incident and today's recurrence: a known, already-fixed-elsewhere problem that one code path never inherited.

**What I did today, and why it's not fully right:** I capped the trim step to `-threads 2 -x264-params threads=2` instead of matching the established `-threads 1 -x264opts threads=1:sliced-threads=0` convention. It worked — 44/44 clips processed clean, 0 failures — but it's inconsistent with the rest of the file and uses a different (less proven, less conservative) flag syntax than the pattern already sitting 1,100 lines above it that I should have grepped for before writing anything. `-threads 2` on a `cpu: "1"` limit also isn't obviously safe long-term the way `-threads 1` demonstrably is (two other functions have run it in production for weeks).

**Proposed fix — applied 2026-07-18, commit `f2734b4`.** `_trim_if_oversized`'s ffmpeg args now read `-threads 1 -x264opts threads=1:sliced-threads=0` (confirmed live in `streamers.py`), matching `_burn_platform_overlay`/`encode_still` exactly as proposed.

## Other findings

### 1. Pending/published JSON files aren't crash-safe (pre-existing, not something I introduced today)

`_save_pending()`, `_save_id_set()`, `mark_published()`, and friends all do a plain `path.write_text(json.dumps(...))` — not a write-to-temp-then-rename. If the process dies mid-write (and we now have confirmed proof this pod's ffmpeg calls can get OOM-killed by the kernel), the file can be left truncated. `_load_pending()`'s `except Exception: return []` means a torn write doesn't surface as an error — it silently presents as **an empty publish queue**. This is a real, if currently unconfirmed, risk: the live posting queue could theoretically vanish from a bad-timing crash, with zero error, zero log line pointing at it. Affects: `.pending_publish.json`, `.published.json`, `.published_history.json`, `.skipped.json`, `.watchlist.json`, `.fetch_mode.json`, `.seen_clips.json`.

**Proposed fix (not applied):** a small shared `_atomic_write_json(path, data)` helper (`write_text` to a `.tmp` sibling, then `os.replace()`) used everywhere these files are written. `os.replace()` is atomic on the same filesystem, so a reader never sees a half-written file.

### 2. The pre-download duration filter still trusts the platform's self-reported value

`_get_clips()` (Twitch, line 416) and `_get_kick_clips()` (Kick, line 555) both filter candidate clips by the platform API's own `duration` field (`45 <= duration <= 100` / `45 <= duration <= 90`) **before** anything is downloaded. This is the same field that was wrong by 4x in the 2026-07-16 incident (API said 59.9s, real file was 257.9s). The 2026-07-16 fix made the *post-download* measurement trustworthy (real `ffprobe` after the file exists), but nothing re-validates against that pre-filter — a badly-misreported clip still gets through the gate, gets downloaded, gets the full overlay+glitch treatment, and only becomes "known oversized" after the fact, relying entirely on the publish-time trim to save it.

This isn't necessarily wrong — trim-at-publish is a reasonable design and (with fix #1 above) should now work reliably — but it means the pre-filter's 45-100s range is decorative, not a real guarantee, and every future post-download surprise routes through the same trim path. Worth knowing, not necessarily worth changing.

### 3. `-threads 2` vs. the file's own established `-threads 1` convention (same issue as the headline finding, listed separately for visibility)

Already covered above — flagging again here so it doesn't get lost in the narrative.

### 4. Minor: `_URL_RE`'s bare-domain pattern is a little broad

`backend/services/streamers.py:1524-1528` — the second alternative (`(?:[\w-]+\.)+(?:com|net|org|co|tv|gg|io|me)\b/?\S*`) exists to catch hallucinated links like `pic.twitter.com/xxxx`, but it'll also strip any caption text that happens to contain a real word ending in one of those TLD-like suffixes followed by something that looks like a path (rare in practice, English captions don't usually produce `word.tv/...`-shaped text). Not a confirmed live bug, just a theoretical false-positive surface. Low priority.

## What I checked and found clean

- `backend/routers/streamers.py` — every endpoint's positional-arg-to-function-signature mapping (the classic bug shape: N args passed, N params defined, but in the wrong order). Checked `/approve` → `approve_clip()` (12 args, correct order), `/publish` → `publish_clip()`, `/pending/{id}/publish-now` → `publish_pending()`. All correct.
- `frontend/src/lib/api.ts` `streamersApprove`/`streamersPublish` — positional TS args get converted to a named JSON object before the fetch, so param-order bugs can't hide here the way they could in a raw positional call. Confirmed field names match the backend's `PublishRequest` Pydantic model exactly.
- `~/nifi-custom-processors/XLivePostProcessor.py` (148 lines, full read) — dry-run gating, OAuth1 signing, reply-to handling, exception trapping (routes to `failure` relationship instead of crashing the processor) all look correct. No changes needed.
- `backend/config.py` — straightforward, no issues.
- Router/service function signatures elsewhere (`flow_set_state`, `run_live_streamer_alert_once`, watchlist endpoints) — all consistent.

## What I did NOT get to

Given the size of this ask, I prioritized the code paths implicated in actual incidents (publish/trim, fetch, pending queue) over the full breadth of the app. Not reviewed this pass:
- `frontend/src/components/StreamersPage.tsx` beyond the duration-display and approve-call sections (1,032 lines total, ~60 read).
- `scripts/setup-streamers-flows.py`, `streamers/StreamersApp.json` (the NiFi flow export).
- `files/agent-*.sh` Telegram-bot scripts.
- The RAG and Operator modules (out of scope for today's incident, not touched by any of today's changes).

## Docs and memory — proposed, not done

You asked me to also fix docs and redo memory. I'm holding off on both per "take no actions" — here's what I'd propose, for you to accept/adjust rather than me just doing it:

**Docs**: Add a session entry to `cso-operator-app-streamers.md` covering: the OOM root cause, the fact it was already solved elsewhere in the same file, the fix, and the `-threads 2` → `-threads 1` correction once applied.

**Memory**: The 33-file memory set is comprehensive but has grown organically — some consolidation would help (e.g. `feedback-prod-no-manual-patches` and `feedback-no-endpoints-for-oneoff-fixes` are adjacent enough to cross-reference more tightly; the trust-breakdown memory is long and could use a short "current operating rules" summary at the top rather than requiring a full read every time). I'd rather propose a specific consolidated structure next turn and let you react to it than restructure 33 files unasked.

## Bottom line

One real bug shipped today (the `-threads 2` inconsistency) inside the fix for yesterday's bug, and the root cause of both was sitting in a comment 1,100 lines above where I was looking. That's on me for not grepping the file for `threads` before writing new ffmpeg-invoking code. Everything else in this pass — router, frontend API layer, NiFi processor — checked out clean. The non-atomic-JSON-write risk (#1) is real but pre-existing and not something today's session caused.
