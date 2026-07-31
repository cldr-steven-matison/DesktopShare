**HeyGen Avatar API — notes from working integrations**

Captured across two real projects: the tuna-mascot Phase A prototype (see `cso-operator-app-streamers-tuna.md`) and the 2026-07-31 **@StevenMatison X intro** (SRM digital twin — see `files/heygen-srm-poc/`). API path works; for one-off polished clips, **HeyGen Studio (plan credits)** is often cheaper and clearer than burning the API wallet on full-length drafts.

Session playbook and wins for the X video live in `files/heygen-srm-poc/LEARNINGS.md`.

---

## What it does

Takes a photo avatar / digital twin (`avatar_id`) plus a text script, and returns a lip-synced, voiced video. Confirmed to work with cartoon/illustrated avatars, not just photoreal humans.

## Auth

Header `x-api-key: <HEYGEN_API_KEY>` on every request. Store the key (and avatar/voice IDs) in a gitignored `.env.local` — never in a committed file. `Idempotency-Key` header (any UUID) is accepted on the create call for safe retries within 24h.

## Billing — plan credits vs API wallet (critical)

HeyGen keeps **two separate balances**. Mixing them up looks like “I have plenty of credits” while the API returns `MOVIO_PAYMENT_INSUFFICIENT_CREDIT`.

| Balance | Where you see it | What spends it |
|---------|------------------|----------------|
| **Plan credits** | Main HeyGen app UI (Creator/Pro/Business) | Studio, browser generation, some integrations |
| **API wallet (USD)** | Settings → API; `GET /v3/users/me` → `wallet.remaining_balance` | Any call with `x-api-key` (`POST /v3/videos`, etc.) |

Check before a paid API run:

```bash
curl -s -H "x-api-key: $HEYGEN_API_KEY" https://api.heygen.com/v3/users/me
# data.wallet.remaining_balance

curl -s -H "x-api-key: $HEYGEN_API_KEY" https://api.heygen.com/v2/user/remaining_quota
# data.details.api  vs  data.details.plan_credit
```

Failed jobs that error at debit (`DEDUCT_QUOTA` / insufficient credit) do not produce a downloadable video. Prefer **Studio + plan credits** for full-length human-reviewed finals when you are not automating.

### API self-serve rates (Digital Twin, 1080p — 2026)

| Engine | $/sec | ~$/min | Use for |
|--------|-------|--------|---------|
| **Avatar III** | $0.0167 | ~$1 | Cheap script/TTS drafts only |
| **Avatar IV** | $0.0667 | ~$4 | Mid |
| **Avatar V** | $0.0667 | ~$4 | Expressive final (once script is locked) |

Source: https://developers.heygen.com/docs/pricing  

**Cost-control rule:** iterate on **10–15 s** samples (or Studio short clips), not repeated full ~45–60 s API renders. A single afternoon of six full Avatar III drafts can burn ~$4+ of wallet on TTS tuning alone.

---

## Create a video (submit)

```
POST https://api.heygen.com/v3/videos
Headers: x-api-key: <key>, Content-Type: application/json
```

Body (avatar-based):
```json
{
  "type": "avatar",
  "avatar_id": "<your avatar id>",
  "script": "<text the avatar will speak>",
  "engine": {"type": "avatar_iii"},
  "aspect_ratio": "9:16",
  "voice_id": "<optional — omit to use avatar's default>",
  "resolution": "1080p",
  "background": {"type": "color", "value": "#hex"}
}
```

- `engine.type`: `avatar_iii` (cheap), `avatar_iv` (default if omitted), `avatar_v` (highest fidelity / more expressive).
- `aspect_ratio`: `9:16` for X/mobile tall; `16:9` for landscape.
- Other top-level `type` values exist (`image`, `cinematic_avatar`) — not used in these POCs.

Response (200):
```json
{"data": {"video_id": "v_abc123...", "status": "waiting", "output_format": "mp4"}}
```

## Poll for completion

```
GET https://api.heygen.com/v3/videos/{video_id}
Headers: x-api-key: <key>
```

Response:
```json
{"data": {"id": "...", "status": "completed", "video_url": "https://files.heygen.ai/...", "duration": 1.58, ...}}
```

`status` moves through `waiting`/`pending` → `processing` → `completed` (or `failed`). Poll every ~5s; generation is real wall-clock time. Download `data.video_url` once completed.

List recent jobs: `GET /v1/video.list` (still useful for auditing what the key produced).

## Gotchas learned the hard way

- **`GET /v3/videos/{video_id}` can return a bare `500 internal_error`** even for a job that completed. Workaround: fall back to legacy `GET /v1/video_status.get?video_id=...` (sunsets 2026-10-31). Don't build long-term automation only on v1; use it when v3 is actively erroring. The SRM POC poller already falls back.
- **`GET /v2/avatars` can hang indefinitely** with a valid key; `GET /v2/voices` may still return 200. Prefer IDs from creation time / Studio, not list endpoints.
- **“Transparent” background is not real alpha** — baked RGB in an mp4; composite with crop/chroma, not alpha.
- **Hard cut at end of speech.** Trailing silence is often under half a second. Always post-process:
  ```bash
  ffmpeg -y -i in.mp4 \
    -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=1.5[v];[0:a]apad=pad_dur=1.5[a]" \
    -map "[v]" -map "[a]" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k \
    out_padded.mp4
  ```
- **TTS mangles proper nouns.** Phonetic spellings in the script help inconsistently (e.g. `Klaude`→Claude, `Grock`→Grok, `Nye Fye`→NiFi, `Clouderah`→Cloudera, `Mattison`→Matison). Re-verify per voice/engine; Whisper on the export is a good cheap check.
- **High voice speed needs more written pauses** — short sentences, periods, blank lines between beats. One long paragraph becomes a run-on.
- **v1/v2 endpoints** still exist through 2026-10-31; prefer v3 for new work.
- Full docs: `developers.heygen.com`, `docs.heygen.com`.

---

## Working examples

| Path | What it is |
|------|------------|
| `files/heygen-srm-poc/heygen_srm_poc.py` | Submit → poll (v3 + v1 fallback) → download. Env: `HEYGEN_ENGINE`, `HEYGEN_ASPECT`, `HEYGEN_OUT`. Issue #50 + X-intro iteration. |
| `files/heygen-srm-poc/script.txt` | Phonetic / pause-oriented script used for the X intro. |
| `files/heygen-srm-poc/LEARNINGS.md` | Billing wins, cost rules, Studio path, final deliverable notes. |
| `files/heygen-srm-poc/output/Final_X_Post_v2_padded.mp4` | Studio final + 1.5s pad (ship candidate for X). |
| Tuna-era `tuna_test.py` | Older submit → poll → download → ffmpeg overlay shape (overlay path). |

For a **single public video**, prefer: lock script in notes → generate in **Studio (plan credits)** → download → **ffmpeg pad** → post. Keep the API POC for automation or batch later.
