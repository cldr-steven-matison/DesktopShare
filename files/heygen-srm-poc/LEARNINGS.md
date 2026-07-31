# HeyGen SRM — X intro playbook (2026-07-31)

**Goal:** ~1 min tall video for **@StevenMatison** introducing the SRM digital twin, what Steven does, and **Articles** (Claude Code day 1–40+, Grok).

**Outcome:** Final ship candidate generated in **HeyGen Studio** (plan credits), then padded locally. API used only for earlier cheap drafts until the API wallet ran dry.

---

## Deliverables

| File | Role |
|------|------|
| `script.txt` | Locked phonetic/pause script (Studio may have small wording edits) |
| `heygen_srm_poc.py` | API submit → poll → download (`HEYGEN_ENGINE` / `ASPECT` / `OUT`) |
| `output/Final_X_Post_v2_padded.mp4` | **Ship this** (or copy under Downloads) |
| `output/Final_X_Post_v2.mp4` | Raw Studio export |
| `C:\Users\tunas\Downloads\Final_X_Post_v2_padded.mp4` | Same pad on WindowsDesktop |
| Root `heygen-avatar-api.md` | Shared API + billing notes for any HeyGen work |

**Do not post the unpadded Studio file** — ending feels cut off without the 1.5s hold.

---

## Billing (do not re-learn)

- **Plan credits ≠ API wallet.** Plan is for **app.heygen.com**. API key calls use **USD wallet** only.
- Check: `GET /v3/users/me` → `wallet.remaining_balance`; `GET /v2/user/remaining_quota` → `details.api` vs `plan_credit`.
- This session: ~**4.3 min** of successful Avatar III API video (~**$4+** wallet) across six full drafts; two v8 jobs failed with `MOVIO_PAYMENT_INSUFFICIENT_CREDIT` (no video). Final was done in **Studio** on plan credits after topping API wallet for future use.

### API rates (Digital Twin, 1080p)

| Engine | $/sec | ~50s |
|--------|-------|------|
| Avatar III | $0.0167 | ~$0.85 |
| Avatar IV / V | $0.0667 | ~$3.30 |

---

## Wins (keep these)

1. **9:16** / 1080×1920 for X mobile.
2. **Simple intro** — no Jetson flex, no CORDYCEPT, no hardware gloat.
3. **Hello** (not Hey); **sales engineering** (not “sales engineer”); say **Articles** explicitly.
4. **Short sentences + blank lines** → pauses (critical when voice speed is high).
5. Soft close: **Thanks for watching.** + **ffmpeg 1.5s freeze + silence** (HeyGen hard-cuts ~0.3s after last word).
6. Phonetics (inconsistent but useful): Mattison, Clouderah, Nye Fye, Klaude, Grock — always re-listen.
7. **Iterate cheap:** III samples or Studio short clips; full expressive engine **once**.
8. For one-off public posts: **Studio (plan credits) > full-length API drafts**.

## What still sounds imperfect (TTS)

Whisper on the Studio final still often hears: Madison, Cloud Era, Cloud Code, GROC, “Exit” for X. Human ear is the judge; caption on the X post can spell names correctly.

---

## Cost-control rule

- Never re-render a full ~40–60s clip for a tiny wording tweak if a **10–15s sample** can test it.
- Pattern: short sample → fix → **one** full render → pad → stop.

## Studio checklist (plan credits)

1. Studio → SRM twin → same voice (elevated speed if saved on voice).
2. Aspect **9:16**, 1080p if available.
3. Paste `script.txt` (keep blank lines / short beats).
4. Download MP4 → pad with ffmpeg (command in `heygen-avatar-api.md`).
5. Post padded file only.

## ffmpeg pad (always)

```bash
ffmpeg -y -i in.mp4 \
  -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=1.5[v];[0:a]apad=pad_dur=1.5[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k \
  out_padded.mp4
```

## Related

- Issue #50 — original SRM CSO-install API POC.
- `heygen-grok-build-instructor.md` — longer automated tutorial pipeline (future; not used for this X clip).
- Voice ID used in API POC: set in gitignored `.env.local` (`HEYGEN_VOICE_ID`).
