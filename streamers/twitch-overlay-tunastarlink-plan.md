# Twitch overlay — @tunastarlink (plan)

**Status (2026-07-27):** Phase 0 done live. Satellite + dish Image sources and `@tunastarlink` Text (GDI+) are on the OBS canvas and visible on stream. No HTML Browser Source yet. This doc is the forward plan — better assets, HTML HUD, motion, optional talking character — and how to keep generating art through **tuna-starlink-app** Imagine.

**Host:** TunaStarlink (Beelink, Windows OBS + WSL2).  
**Canvas assumption:** 1920×1080 (scale positions if different).

---

## Goal

Persistent Starlink-flavored stream identity:

| Corner | Content |
|--------|---------|
| Top right | Satellite |
| Bottom left | Dish |
| Bottom right | `@tunastarlink` |

Later: one full-screen HTML overlay that owns layout + light animation; optional mascot that “talks” on a separate track.

---

## Phase 0 — done (native OBS)

What shipped tonight:

1. **Image** `overlay-satellite` — top right  
2. **Image** `overlay-dish` — bottom left  
3. **Text (GDI+)** `overlay-username` — `@tunastarlink` bottom right  

**Asset masters (WSL):**

```
~/DesktopShare/overlays/tunastarlink/assets/
  satellite.png       # 512×512 RGBA (chroma-keyed)
  dish.png            # 512×512 RGBA
  satellite_raw.png   # Imagine green-screen original
  dish_raw.png
  *_meta.json         # prompts + model stats
```

**Windows path OBS can open:**

```
\\wsl.localhost\Ubuntu\home\tunas\DesktopShare\overlays\tunastarlink\assets\
```

Fallback: `\\wsl$\Ubuntu\...` or copy into `C:\Users\tunas\Videos\OBS\overlays\` so Browser/Image sources never depend on WSL.

**Image requirements (keep for regen):**

| Spec | Value |
|------|--------|
| Format | PNG, true alpha |
| Master size | 512×512 (display ~160–280 px wide on 1080p) |
| Background | Transparent after key; raw can be chroma green `#00FF00` |
| Style | Clean tech UI icon, cyan accent, no logos/text/wordmarks |
| Safe margin | ~40–60 px from canvas edges |

Leave Phase 0 sources as-is until HTML is ready. No need to tear them down mid-season.

---

## Phase 1 — better images via tuna-starlink-app

Do **not** invent a second Imagine client. Use the app that already has keys, model config, and cost discipline.

### App facts

| Item | Value |
|------|--------|
| Repo | `~/tuna-starlink-app` |
| Service | `systemctl --user status tuna-starlink` → `http://127.0.0.1:8010` |
| Imagine module | `backend/services/xai_imagine.py` |
| Model (default) | `grok-imagine-image` (~$0.02/image) |
| Keys | `backend/.env.local` (`XAI_API_KEY`, `XAI_IMAGE_MODEL`, …) |
| Gallery pipeline | `POST /api/generate` = Planet Hack news→art (16:9). **Wrong tool for icons.** |

### Why not `/api/generate` for overlays

That route runs art director + style seeds + landscape series look. Overlay assets need:

- Custom icon prompts  
- Square / subject-centered crop  
- Chroma or alpha for OBS  
- Files under `DesktopShare/overlays/…`, not the X gallery flow  

### How to generate (pattern that already worked)

One-shot from the app backend venv — same client as the service:

```bash
cd ~/tuna-starlink-app/backend
.venv/bin/python   # import config + services.xai_imagine
```

Recipe:

1. Prompt: game-UI icon, single subject, cyan tech accent, **solid `#00FF00` green screen**, no text/logos.  
2. Call `xai_imagine.generate_image(prompt, run_id, style_label)`.  
3. If `size`/`aspect_ratio` 1:1 is rejected (current API behavior), accept landscape raw and **center-crop to square**.  
4. Chroma-key green → RGBA, resize to **512×512**, write `assets/<name>.png` + `*_raw.png` + `*_meta.json`.  
5. In OBS: re-browse the Image source (or refresh Browser Source) — no stream restart.

Optional later: small `scripts/gen_overlay_icon.py` in tuna-starlink-app (or DesktopShare) so regen is one command, not a pasted heredoc. Still call the app’s Imagine stack; don’t fork API logic.

### Regen brief (next passes)

| Asset | Push for |
|-------|----------|
| **Satellite** | More Starlink-like **flat panel + solar wings** (less “classic box sat”), tighter subject fill (~60–70% of frame), same cyan edge language as dish |
| **Dish** | Keep current terminal-style look; optional slight larger subject; match sat materials |
| **Pair** | Same run / same prompt base so materials and cyan match |

Cost: ~$0.02 per attempt. Keep `DRY_RUN=false` only when intentionally billing; dry-run placeholders are useless for OBS.

### Quality gate before swapping live

- [ ] Preview at ~200 px on dark *and* light backgrounds  
- [ ] No green fringe, no gray box  
- [ ] Readable at stream bitrate  
- [ ] No official Starlink marks  

---

## Phase 2 — single HTML full-screen overlay

One **Browser Source** = full canvas (e.g. 1920×1080), transparent body, CSS-positioned sat / dish / handle. Replaces three native sources when ready (or runs alone on a clean scene).

```
~/DesktopShare/overlays/tunastarlink/
  overlay.html
  assets/satellite.png
  assets/dish.png
```

OBS Browser Source:

- Local file → `overlay.html` (Windows-visible path)  
- Width/Height = canvas  
- Custom CSS: `body { background-color: rgba(0,0,0,0); margin: 0; overflow: hidden; }`  
- Edit file → right-click source → Refresh  

**Can:** layout, CSS/JS animation, Lottie, local `fetch` to StarlinkAI services, chat-driven widgets.  
**Can’t alone:** true mic lip-sync, heavy 3D without taxing the encode, transparent MP4 (use WebM+alpha or sprites).

Ship static HTML first (parity with Phase 0), then add motion.

> **First real Phase 2 content — left-side chat column + `!c overlay` relay:** the colorful
> left-edge chat overlay (default @tunastarlink's own chat, `!c overlay <streamer>` relays another
> channel, with flood handling) is speced in
> [`twitch-overlay-chat-relay-plan.md`](twitch-overlay-chat-relay-plan.md). It lives in this same
> `overlay.html` Browser Source.

---

## Phase 3 — motion (no talking yet)

Light, always-on, cheap on CPU:

- Satellite: slow float / drift (8–12s loop)  
- Dish: soft idle pulse or cyan rim breathe  
- Handle: subtle text-shadow / glow pulse  

Stay CSS-only until something needs audio or chat. Avoid full-screen particle spam while gaming.

---

## Phase 4 — “talks” (optional, separate from HUD)

Do not block brand overlay on this.

| Tier | What | Tools |
|------|------|--------|
| **A — Easy** | Mascot idle + mouth flap on alert/chat/`!hi` + optional TTS file | HTML/JS + local sound |
| **B — Medium** | Bot/service → TTS → overlay subtitle + flap | StarlinkAI Python + overlay events |
| **C — Real lips** | Audio → lip-sync clip → Media/Browser play | Wav2Lip / SadTalker path (see `heygen-avatar-api.md` / tuna mascot notes); HeyGen if paying |

Tier A is enough for “the brand is alive.” Tier C is event moments, not continuous commentary, unless we commit GPU + latency budget.

---

## Execution order (when we pick this up)

1. **Regen images** via tuna-starlink-app Imagine (Phase 1) → swap files, keep OBS sources.  
2. **Write `overlay.html`** parity layout (Phase 2 static).  
3. **Browser Source** on a test scene; Studio Mode transition; retire duplicate Image/Text when happy.  
4. **CSS motion** (Phase 3).  
5. **Talking tier A** only if still wanted (Phase 4).  

Do not auto-publish overlay gens to X. Overlay assets are local stream chrome, not Planet Hack gallery posts.

---

## OBS live-safety (standing rules)

- Prefer **Studio Mode**: edit Preview → Transition.  
- Adding/replacing Image or Browser sources does **not** require ending the stream.  
- Don’t restart OBS for asset swaps — refresh/re-browse the source.  
- Copy assets to a pure Windows path if WSL UNC flakes during a stream.

---

## Out of scope (for now)

- StreamElements/Streamlabs cloud overlay packs  
- Alert boxes / sub goals (can share the HTML later)  
- Official Starlink trademarks or wordmarks  
- Multistream / vertical canvas variants  

---

## When this ships, update

- This file’s **Status** line and Phase checkboxes.  
- Optional one-liner in `CLAUDE-CHECKIN.md` TunaStarlink block if overlay path becomes a standing host fact.  
- If `gen_overlay_icon.py` lands in tuna-starlink-app, link it from that repo’s README under a short “Stream overlay icons” note.

---

## Quick reference

| Need | Where |
|------|--------|
| Overlay files | `DesktopShare/overlays/tunastarlink/` |
| Imagine app | `tuna-starlink-app` · port **8010** · `xai_imagine.generate_image` |
| Live stream rules | Studio Mode; no OBS restart for PNG swap |
| Talking research | `heygen-avatar-api.md`, tuna mascot notes under `files/tuna-test/` |
