**HeyGen Avatar IV API — notes from a working integration**

Captured while building the tuna-mascot Phase A prototype (see `cso-operator-app-streamers-tuna.md`). We ended up going with a free/local alternative (Wav2Lip/SadTalker) instead of HeyGen for that project, but this API worked and is worth keeping for whenever a paid, higher-quality avatar-video generation service makes sense again.

---

## What it does

Takes a single photo (a "photo avatar", turned into an `avatar_id` in HeyGen's system beforehand) plus a text script, and returns a lip-synced, voiced video of that avatar speaking the script. Confirmed to work with cartoon/illustrated avatars, not just photoreal humans.

## Auth

Header `x-api-key: <HEYGEN_API_KEY>` on every request. Store the key (and the avatar ID you're using) in a gitignored `.env.local`-style file or environment variable — never in a committed file. `Idempotency-Key` header (any UUID) is accepted on the create call for safe retries within 24h.

## Create a video (submit)

```
POST https://api.heygen.com/v3/videos
Headers: x-api-key: <key>, Content-Type: application/json
```

Body (avatar-based — the relevant case for a photo avatar):
```json
{
  "type": "avatar",
  "avatar_id": "<your avatar id>",
  "script": "<text the avatar will speak>",
  "engine": {"type": "avatar_iv"},
  "aspect_ratio": "9:16",
  "voice_id": "<optional — omit to use avatar's default>",
  "resolution": "1080p",
  "background": {"type": "color", "value": "#hex"}
}
```
Other `type` values exist (`image`, `cinematic_avatar`) for different generation modes — not used here. `engine.type` can be `avatar_iv` (default), `avatar_v`, or `avatar_iii`; omit `engine` entirely to get Avatar IV.

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
`status` moves through `waiting`/`pending` → `processing` → `completed` (or `failed`). Poll every ~5s; generation is real wall-clock time, not instant — budget tens of seconds even for a ~1-2 second script. Download `data.video_url` once completed.

## Gotchas learned the hard way

- **`GET /v3/videos/{video_id}` (the documented v3 polling endpoint) can return a bare `500 internal_error` with no video data, even for a job that completed successfully.** Confirmed reproducible (consistent 500 across repeated calls) for a video whose actual status was `completed`. Workaround: fall back to the legacy `GET /v1/video_status.get?video_id=...` (still live, sunsets 2026-10-31 per its own deprecation warning) — it returned the same job correctly with `status`, `video_url`, etc. Don't build long-term automation on the v1 fallback; only reach for it if v3 polling is actively erroring.
- **`GET /v2/avatars` (list all avatars) can hang indefinitely** even with a valid key — confirmed via repeated 45s-timeout curl calls, while `GET /v2/voices` on the same key/network returned 200 immediately. If you need a specific avatar/voice ID, get it from wherever it was created rather than relying on the list endpoint.
- **The "transparent" background is not a real alpha channel.** Output is a standard mp4 — what looks like a transparent checkerboard is baked directly into the video's RGB pixels, not actual transparency. Any compositing step needs to crop or chroma-key it, not just alpha-composite it. Confirmed by extracting frames and looking at them directly, not by documentation.
- **Cost scales with generated length.** A short (~1-2 second) clip cost about 3 credits. Stretching a script to cover a full 15-60+ second base clip is meaningfully more expensive than one short reaction line — factor this in before designing around "the avatar talks for the whole video."
- **The old v1/v2 endpoints still exist** (supported through 2026-10-31 per HeyGen's migration notice) but v3 (`/v3/videos`) is the current, actively-documented API — this doc only covers v3.
- Full docs: `developers.heygen.com` (API reference) and `docs.heygen.com` (guides) — the reference pages have the complete request/response schemas; this doc only captures what was actually exercised.

## Working example

`tuna_test.py` (built for the tuna-mascot prototype, since removed/repurposed) called this exact flow successfully: submit → poll → download → ffmpeg overlay. If reviving a HeyGen integration later, that call shape is the known-good starting point.

`files/heygen-srm-poc/heygen_srm_poc.py` (issue #50) is a second working example, simpler than the tuna one since the whole video is the deliverable — no overlay/compositing step. Submit → poll → download, 16:9/1080p, with a separate `voice_id`. Used Steven's own "SRM" HeyGen avatar to narrate a short intro to installing Cloudera Streaming Operators.
