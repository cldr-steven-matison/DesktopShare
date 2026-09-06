# Twitch overlay — left-side colorful chat + `!c overlay` relay (@tunastarlink) (plan)

**Status (2026-09-06):** Phase 1 built (overlay HTML, static-readable-first) — Phases 2–4 pending.
This is the golden-source spec for a new
overlay feature on **StarlinkAI** (`TunaStarlink` Beelink): a vertical strip of colorful chat text
pinned to the **left edge** of the @tunastarlink OBS canvas, plus a `!chat` / `!c overlay
<streamer>` command that re-points the column at *another* streamer's chat and relays it. Filed as
the `device:StarlinkAI` task the build is picked up from.

**Host:** TunaStarlink (Beelink, Windows OBS + WSL2). **Canvas:** 1920×1080.

This is the first real content for the Phase 2 HTML Browser Source promised in
[`twitch-overlay-tunastarlink-plan.md`](twitch-overlay-tunastarlink-plan.md) — same
`overlays/tunastarlink/overlay.html` file, same OBS live-safety rules, same asset/path conventions.

---

## Goal

A live, readable, colorful chat column down the left of the stream. Default it shows @tunastarlink's
own chat; on command it relays someone else's channel (raids, collabs, watch-parties). The design's
hard problem is **flood**: a big channel pushes hundreds of msgs/sec, far past readable — so the job
is to decide *what to drop and make dropping look intentional*, not to try to render everything.

---

## Decisions (locked 2026-09-06)

| Decision | Choice | Why |
|---|---|---|
| Chat source | **Twitch IRC, anonymous read** (`justinfan` nick) | No auth needed to *read* any public channel — required for relaying arbitrary streamers. |
| Command gate | **Broadcaster / mods only**, in @tunastarlink's own chat | Prevents any viewer flipping the overlay. The listener already parses IRCv3 badges, so the gate is free. |
| Stack | **Fits the NiFi/Kafka pipeline** | Relay flows through Kafka (`overlay_chat_relay`), not a rogue standalone bot — stays on-brand as a streaming demo and reuses the existing chat plumbing. |
| Relay owner | **The overlay backend (cso-operator-app) owns the anon socket** | Reuses the proven `!load → InvokeHTTP → endpoint` dispatch; keeps flood logic in JS; sidesteps the FlowFileSource-can't-consume dead end (see Constraints). |
| Idle behavior | **Idle shows @tunastarlink's own chat**; `!c overlay off` / `!c overlay me` returns to own chat / hides the column | Always something sensible on screen. |
| Flood handling v1 | **Queue + fixed drain rate + ring buffer + dedup collapse + live msg/s badge** | Looks intentional at any channel size. Sampling + sub/mod priority tiers are v2. |

---

## Reuse (don't rebuild) — existing infra

- **`TwitchChatListenerProcessor`** (custom NiFi Python, persistent IRC socket) — already parses
  IRCv3 mod/broadcaster badges, already handles `!load`/`!matrix`/`!watchlist`/`!commands`, already
  publishes @tunastarlink's own chat to Kafka `twitch_chat_activity`, and dispatches commands via
  `RouteOnAttribute → InvokeHTTP → endpoint`. See `streamers-twitch-bot.md` §5.1.
- **`!load` mid-command HTTP call** — the listener already calls a cso-operator-app endpoint
  (`GET /api/streamers/live`) before dispatching. The `!c overlay` → `POST /api/overlay/relay` call
  is the same shape. See `streamers-twitch-bot.md` §TODO / live-check.
- **Anon / arbitrary-channel IRC join** is already proven in `WatchlistChatJoiner` / `JoinAndGreet`.
- **`overlays/tunastarlink/overlay.html`** — the Phase 2 Browser Source slot, its transparent-body
  CSS, WSL↔Windows path handling, and "refresh source, never restart OBS/stream" rules all live in
  `twitch-overlay-tunastarlink-plan.md` §Phase 2 / §OBS live-safety.

---

## Constraints (learned the hard way — do not relitigate)

1. **A NiFi `FlowFileSource` processor cannot consume an incoming FlowFile** (`streamers-twitch-bot.md`
   §13). A past session spent real time trying to route a "join this channel" FlowFile into the
   persistent-socket processor; it queues forever, never read. **This is why the relay lives in the
   backend, not a new socket processor fed by a NiFi route.**
2. **Never GET-then-PUT `TwitchChatListenerProcessor`.** Its `Client Secret` / `Refresh Token` are
   Parameter Context references that a full-entity PUT overwrites with the `"********"` mask,
   destroying the credential (`streamers-twitch-bot.md` §5.1, §14 — this happened twice in one day).
   Bump the bundle version / add the command via the **UI or a narrow-scope endpoint** (`/run-status`),
   never a round-trip PUT.
3. **New automation goes in its own isolated PG** (skill rule 8), and **custom Python only for the
   one thing NiFi can't do natively** (the socket); everything else is stock processors (rule 9).
   The relay socket living in the backend keeps NiFi to just command-parse + dispatch here.

---

## Architecture

```
@tunastarlink chat
  └─ TwitchChatListenerProcessor  (EXTEND: parse "!chat" / "!c overlay <streamer|off|me>",
     |                             broadcaster/mod-gated — reuse the existing badge check)
     └─ InvokeHTTP  →  cso-operator-app  POST /api/overlay/relay {channel: <streamer|null>}
                                            (mirrors the existing !load → InvokeHTTP dispatch)

cso-operator-app  (overlay backend — NEW route + relay worker):
  • holds the current relay target (in-memory; null/own = @tunastarlink default)
  • opens ONE anonymous Twitch IRC read socket (justinfan) to the target channel; swaps target
    on command; on "off"/"me" falls back to @tunastarlink's own chat
  • each PRIVMSG → {user, color (IRCv3 color tag), badges, text, ts}
     → PublishKafka  →  topic  overlay_chat_relay     (on the Kafka stack / demo record)
     → SSE  /api/overlay/chat/stream                  (serves the browser source directly)

overlays/tunastarlink/overlay.html  (NEW — Phase 2 content, LEFT column):
  • EventSource(/api/overlay/chat/stream); bottom-anchored colorful lines (name = IRCv3 color tag)
  • FLOOD HANDLING v1 (below)
  • transparent body, CSS-positioned left strip; static-readable first, motion later
```

### Message shape (relay → overlay)

```json
{ "user": "someviewer", "color": "#1E90FF", "badges": ["subscriber","moderator"],
  "text": "GG that was clean", "ts": 1725600000.123, "channel": "xqc" }
```

`color` is the chatter's IRCv3 `color` tag; when a chatter has none, assign a stable
hash-of-username color (never white-on-transparent — must read on any game background).

---

## Flood handling (v1 — the whole point)

The eye caps out around 1–2 readable lines/sec; a big channel does 100s/sec. So v1 shows a readable
*trickle* and makes the drop look deliberate:

1. **Fixed drain + ring buffer.** Incoming messages land in a JS queue; a timer pops **one every
   ~500–800 ms** and appends to a **max ~12–15 line** ring buffer (oldest scrolls off the top).
   Queue overflow drops oldest. This alone keeps the column readable at any channel size.
2. **Dedup / spam collapse.** Emote-only spam and copypasta (identical/near-identical text within a
   short window) collapse to one line with a **`×N`** counter instead of N lines.
3. **Live msg/s badge.** A small **`⚡ N msg/s`** indicator shown *only while actively dropping* —
   turns "my overlay can't keep up" into "this chat is going nuts," which is the vibe you want.

**Deferred to v2** (explicitly out of v1 scope): representative random-sampling under heavy load;
subs/mods-always-shown priority tiers.

---

## Build phases (execution order at build time)

1. **Overlay HTML (static-readable first).** ✅ **Built 2026-09-06** — `overlays/tunastarlink/overlay.html`:
   left bottom-anchored column, IRCv3-colored lines (stable hash-color fallback), badge glyphs,
   SSE client on `/api/overlay/chat/stream`, and the full flood pipeline (fixed drain + ring buffer +
   dedup `×N` collapse + live `⚡ msg/s` badge). A built-in demo feed makes it provable with **no
   backend** — open with `?sim=1` (or `?sim=40` for a flood test); it also auto-falls-back to the demo
   feed if SSE is unreachable. **Still to do here:** add to a **test OBS scene** via Browser Source
   (Studio Mode, no stream restart) — needs the human at OBS on TunaStarlink.
2. **Backend relay + SSE.** In `cso-operator-app`: `POST /api/overlay/relay`, the anon-IRC relay
   worker (one socket, target-swappable, defaults to @tunastarlink), `PublishKafka` to
   `overlay_chat_relay`, and SSE `/api/overlay/chat/stream`. **Read that repo's own `CLAUDE.md`
   first.** Create the `overlay_chat_relay` Kafka topic (short retention, mirror
   `twitch_chat_activity` conventions).
3. **Listener command.** Add `!chat` / `!c overlay <streamer|off|me>` to
   `TwitchChatListenerProcessor` (`nifi-custom-processors`), broadcaster/mod-gated, InvokeHTTP to
   `/api/overlay/relay`. Update `!commands`/`!help` output. **Bundle-version bump via UI or
   narrow-scope endpoint only** (Constraint 2). Add/extend offline tests
   (`files/test_twitch_chat_triggers.py`).
4. **Live test.** `!c overlay <streamer>` in @tunastarlink chat → column relays that channel,
   colored and readable, dropping cleanly under load with the msg/s badge; `!c overlay off` → back
   to own chat. Then optional CSS motion, matching the Phase 3 style in the sibling overlay doc.

---

## Out of scope (v1)

- Sampling + sub/mod priority tiers (v2).
- Kick relay (`kick:` channels) — the ingestion pattern exists (`streamer-kick-bot.md`) but v1 is
  Twitch-only.
- Any viewer (non-mod) being able to switch the relay.
- Alert boxes / sub goals / mascot — those belong to the sibling overlay doc's later phases.

---

## When this ships, update

- This file's **Status** line and phase checkboxes.
- The Phase 2 note in `twitch-overlay-tunastarlink-plan.md` (chat column now lives in `overlay.html`).
- `streamers-twitch-bot.md` §3 command list + the `!commands` reply, once `!c overlay` is live.
- One-liner in `CLAUDE-CHECKIN.md` TunaStarlink block if the overlay/backend ports become standing
  host facts.

---

## Quick reference

| Need | Where |
|------|--------|
| Overlay file | `overlays/tunastarlink/overlay.html` |
| Sibling overlay plan (brand chrome, Phase 2 slot, OBS rules) | `twitch-overlay-tunastarlink-plan.md` |
| Chat listener architecture + constraints | `streamers-twitch-bot.md` §5.1, §13, §14 |
| Backend home | `cso-operator-app` (read its `CLAUDE.md`) |
| Relay Kafka topic | `overlay_chat_relay` (mirror `twitch_chat_activity` retention) |
