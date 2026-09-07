# Twitch overlay — left-side colorful chat + `!c overlay` relay (@tunastarlink) (plan)

**Status (2026-09-07):** ✅ **Live end-to-end.** Phases 1–4 complete. Backend relay + SSE + Kafka on
prod (`cso-prod-1`); the `!chat` / `!c overlay` command shipped in `TwitchChatListenerProcessor`
v0.0.29 with the `overlay_relay` flow branch; and the overlay is showing real relayed chat in OBS on
StarlinkAI as a Browser Source. Verified: a real `!chat xqc` in @tunastarlink chat flowed all the way
to the left-side column. Only v2 polish (sampling/priority tiers, CSS motion, the mistaken-target
self-correct guard) remains. See the build record at the bottom.
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
2. **Backend relay + SSE.** ✅ **Deployed 2026-09-06.** In `cso-operator-app`:
   `backend/services/overlay_relay.py` (one anon `justinfan` IRC socket, target-swappable, defaults
   to @tunastarlink, reconnect w/ backoff) + `backend/routers/overlay.py` (`POST /api/overlay/relay`,
   `GET /api/overlay/relay`, SSE `GET /api/overlay/chat/stream`), wired into `main.py` lifespan under
   the `streamers` module. Each PRIVMSG → Kafka `overlay_chat_relay` + SSE. Topic auto-creates on the
   Strimzi cluster (short retention is a Surveyor op). Verified live: swap → SSE delivers real relayed
   chat, Kafka topic receiving, `off`/`me` → own chat.
3. **Listener command.** ✅ **Deployed 2026-09-06** as `TwitchChatListenerProcessor` **v0.0.29**.
   `!chat <streamer|off|me>` (+ `!c overlay <…>` long form), broadcaster/mod-gated, emits an
   `overlay_relay` FlowFile. Flow branch: `RouteChatAction` gained an `overlay_relay` route (keyed on
   the promoted `command` attr) → new `InvokeOverlayRelay` (POST `/api/overlay/relay`, Retry self-loop,
   Failure/No-Retry→Log) in the `ChatTriggers` child PG — mirrors the existing chat-trigger dispatch.
   **Rebased onto the live 0.0.28 source** (the local copy was 5 versions stale — lacked the gif/roster
   feature set); bundle-only partial PUT preserved the sensitive Twitch creds (Constraint 2).
4. **Live test.** ✅ **Done 2026-09-07.** A real `!chat xqc` in @tunastarlink chat relayed that
   channel to the left column; `!chat me` → back to own chat. `overlay.html` added as an OBS Browser
   Source on StarlinkAI (URL below). Optional CSS motion (Phase 3 style in the sibling doc) is v2.

   **OBS Browser Source (StarlinkAI):** uncheck "Local file", 1920×1080, URL =
   `file:///<path>/overlays/tunastarlink/overlay.html?endpoint=http://100.68.113.126:8090/api/overlay/chat/stream`.
   The `?endpoint=` overrides the overlay's default relative SSE path (unresolvable from a `file://`
   origin) with WindowsDesktop's **Tailscale** IP — StarlinkAI reaches the backend over the tailnet,
   **not** the LAN (both hosts sit on unrelated `192.168.1.x` networks). Requires the cso-operator-app
   `:8090` port-forward (zellij `kube-service-ports-efm.kdl`, bound to `.121`+`.126`) and a Windows
   inbound firewall allow for 8090.

---

## Build record — 2026-09-06 (WindowsDesktop / cso-prod-1)

- **Backend** deployed via `MODULES=rag,streamers,efm bash scripts/deploy.sh` (the running pod's real
  MODULES — a bare `MODULES=streamers` would have dropped rag+efm). One pod `Running`, creds intact.
- **NiFi flow** built via REST on `mynifi-0` (cfm-streaming): `InvokeOverlayRelay`
  (`78d02d5b-…`) + `overlay_relay` route on `RouteChatAction` (`238b5cf0-…`) in `ChatTriggers`
  (`5aa71641-…`). Processor version switch: cp 0.0.29 → registered → stop → bundle-only PUT → start,
  VALID.
- **Verification:** backend relay/SSE/Kafka proven against a live busy channel; processor `!chat`/`!c
  overlay` parse validated in isolation against the rebased 0.0.29 module.
- **Not yet done:** re-export `flows/TwitchChatBot.json` (the ChatTriggers PG changed); update
  `streamers-twitch-bot.md` §3 command list + `!commands` reply; the two Phase-4 human steps. The
  committed `files/test_twitch_chat_triggers.py` is stale vs deployed 0.0.28 (pre-existing #174/gif
  drift) — overlay tests added but the unrelated expectations were left for a separate sync.

---

## Out of scope (v1)

- Sampling + sub/mod priority tiers (v2).
- Kick relay (`kick:` channels) — the ingestion pattern exists (`streamer-kick-bot.md`) but v1 is
  **Twitch-only**. ⚠️ `!chat k:<name>` / `!chat kick:<name>` **silently fails to switch the relay**
  (verified 2026-09-07): unlike the `clip`/`watchlist` triggers, the `!chat` parser does **not**
  expand `k:`→`kick:` — it only lstrips `@` and lowercases, so the literal `k:<name>` is handed to
  the backend's anonymous *Twitch* IRC socket, which can't join it and leaves the target unchanged.
  Kick relay is a **v2** item (WindowsDesktop).
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
