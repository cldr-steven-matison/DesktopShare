# heygen-srm-poc

Steven’s SRM HeyGen digital twin — API helper + X intro deliverable.

| File | Purpose |
|------|---------|
| `heygen_srm_poc.py` | API: submit → poll → download |
| `script.txt` | Phonetic / pause script for the X intro |
| `LEARNINGS.md` | Billing, wins, Studio path, cost rules |
| `output/Final_X_Post_v2_padded.mp4` | **Ship candidate** (Studio + pad) |
| `.env.local` | `HEYGEN_API_KEY`, `HEYGEN_AVATAR_ID`, `HEYGEN_VOICE_ID` (gitignored) |

Shared API notes: repo root `heygen-avatar-api.md`.

```bash
# API draft (burns API wallet USD — check balance first)
HEYGEN_ENGINE=avatar_iii HEYGEN_ASPECT=9:16 HEYGEN_OUT=draft.mp4 python3 heygen_srm_poc.py

# Pad any Studio or API export
ffmpeg -y -i in.mp4 \
  -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=1.5[v];[0:a]apad=pad_dur=1.5[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k \
  out_padded.mp4
```
