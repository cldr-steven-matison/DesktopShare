# Kick chat bot — plan and first build

**Status (2026-07-26):** Built and confirmed live today: an "Inspector" sub-page in `cso-operator-app`'s Streamers tab that, given any streamer (Twitch or Kick), shows live status, recent clips, and who's actually talking in their chat right now — with third-party bots flagged separately from real viewers. This came out of live-testing `!load clavicular screen4` against an offline streamer, which led to poking around bbjess's Kick channel, finding two real bots (`BotRix`, `KickBot`) running there, and reverse-engineering how Kick chat itself works well enough to read it directly. What's below is both the writeup of that (Inspector, live) and the plan for the next step: an actual Kick chat bot that posts, not just reads (not built).

## 1. How Kick chat actually works (the discovery)

Kick's live chat runs over a public Pusher websocket — the same one BotRix and KickBot themselves are presumably built on. No auth needed to *read* it:

- Endpoint: `wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679?protocol=7&client=<anything>&version=1.0&flash=false` — this app key/cluster is Kick's real production one, confirmed by a live connection succeeding, not assumed from docs.
- First frame back is `pusher:connection_established`.
- Subscribe with `{"event": "pusher:subscribe", "data": {"auth": "", "channel": "chatrooms.<chatroom_id>.v2"}}`.
- `chatroom_id` comes from `GET https://kick.com/api/v2/channels/<slug>/chatroom` (returns chatroom settings, not the ID's meaning documented anywhere — just present as `.id`).
- Every chat message then streams in as `{"event": "App\\Events\\ChatMessageEvent", "data": "<JSON string>"}`, where the inner JSON has `sender.username`, `sender.identity.badges` (each `{"type": ..., "text": ...}`), and `content`.

Confirmed live 2026-07-26 against bbjess's channel (`chatroom_id` 1341076): a 45s capture caught 5 real messages, a 240s capture caught 10 unique senders including two bots.

**One gotcha, worth remembering:** `kick.com`'s own REST API (the clips/channel endpoints) is behind Cloudflare bot protection that blocks direct requests from this dev host — curling `kick.com/api/v2/...` from a bare shell here gets `{"error": "Request blocked by security policy"}`. The same request works fine from inside the `cso-operator-app` pod (different egress path, apparently trusted). The Pusher websocket itself is on Pusher's own infrastructure, not `kick.com`, so it was never subject to this block either way. If a future session hits the same Cloudflare block, don't assume Kick is down — check whether the request is coming from the pod or the bare host first.

## 2. Bot detection — the actual signature

Kick doesn't have a documented "this account is a bot" flag. Empirically, both real bots found in bbjess's chat carried the exact same badge pair:

```json
[{"type": "moderator", ...}, {"type": "verified", "text": "Verified channel", ...}]
```

`moderator` alone isn't enough — real human mods exist without the `verified` badge. The combination is the tell: a streamer grants a third-party bot integration moderator rights, and Kick separately marks the *integration itself* as a verified channel. Detection rule used in code: `"moderator" in badge_types and "verified" in badge_types`.

**Bots found live in bbjess's channel (2026-07-26, 240s capture):**

| Bot | What it does |
|---|---|
| `BotRix` | Join/follow greetings — `"Thank you for the follow @Shakurblyomm"`, `"Welcome to the stream, @mockingbird417!"`. A hosted, multi-platform (Kick/Twitch/YouTube) SaaS bot — bbjess just authorized it into her channel, it isn't something she built. |
| `KickBot` | Random novelty one-liners on what looks like a timer — `"🧠 WinMP Fact #129: The streamer is 73% caffeine and 27% trauma."` Looks like a community/custom fact bot, not user-triggered. |

Twitch has no equivalent universal badge signature — its bots (Nightbot, StreamElements, Fossabot, etc.) are just regular accounts, usually with a `moderator` badge but nothing else distinguishing. The Inspector's Twitch-side detection falls back to a known-bot-username list plus a bare `"bot"` substring match — weaker, and it'll miss anything not on the list. Worth revisiting if a real gap shows up.

## 3. What's built: the Inspector sub-page

New "Inspector" pill inside `cso-operator-app`'s existing Streamers tab (`StreamersPage.tsx`), alongside "Overview" and "Posted Clips". Type a login (`xqc` or `kick:bbjess`), pick a chat-capture window (10-60s, default 25), hit Inspect. Returns:

- Live status (reuses `is_streamer_live()` directly — no watchlist side effect, this is a read-only tool)
- Recent clips, metadata only — title, duration, views, thumbnail, link. No download, no ffmpeg, nothing touches `/clips` or the fetch pipeline.
- Chat: everyone who spoke during the capture window, bots split out into their own section, each chatter's badges and message count and up to 3 sample messages shown.

**Backend:** new `backend/services/inspector.py` — `inspect_streamer()` ties together clip listing (`_list_twitch_clips`/`_list_kick_clips`, both new, both metadata-only reads against Helix/Kick's clips endpoints) and chat capture (`_capture_kick_chat` via the Pusher technique above, `_capture_twitch_chat_sync` via an anonymous `justinfan<N>` IRC join — no OAuth needed to *read* a public Twitch chat, same trick Twitch chat overlay tools have used for years). New route: `GET /api/streamers/inspect?login=&chat_seconds=&clip_limit=`, wired into the existing `routers/streamers.py`. Reuses `streamers.py`'s existing Twitch/Kick auth helpers (`_twitch_token_refresh`, `_get_broadcaster_id`, `_kick_token_refresh`, `_get_kick_broadcaster_id`) rather than re-deriving credential plumbing.

Twitch's anonymous chat capture is genuinely blocking (raw sockets) so it runs via `asyncio.to_thread` — confirmed this matters live: without it, the whole FastAPI event loop would stall for the full capture window on every request. Kick's side uses the `websockets` package (new dependency, added to `backend/requirements.txt`) and is natively async, no thread needed.

**Confirmed live 2026-07-26** against both platforms post-deploy: `kick:bbjess` returned real clips + `live: true`; `xqc` (offline at test time) correctly skipped chat capture with a note; `jasontheween` (live) captured 49 real unique chatters with real badges (subscriber tiers, channel-specific badges, sub-gifter counts) in a 20s window.

## 4. What's NOT built yet: an actual posting Kick bot

Everything above only *reads* Kick chat. The natural next step — mirroring `TwitchChatListenerProcessor`'s shape (`streamers-twitch-bot.md` §5.1) — is a Kick equivalent that can also *post*, i.e. a real `!load`/`!matrix`-style command bot for Kick chat, not just the anonymous read-only probe.

**Why this is a bigger lift than it looks:** everything in this doc so far works with zero authentication because reading a public Pusher channel needs none. *Posting* to Kick chat needs a real Kick bot account and Kick's actual send-message API, which (unlike the clips/channel reads) is behind Kick's OAuth2 `public/v1` API — the same `client_credentials`-grant pattern already used elsewhere in this app (`_kick_token_refresh` in `services/streamers.py`, and the `Kick OAuth2 (client_credentials)` controller service already configured in the live `StreamersApp` NiFi flow) is for *app-level* access (clips, channel info) — sending a chat message as a specific bot user is a different, user-scoped grant Kick's public API supports via `POST /public/v1/chat` with a **user access token** for the bot's own Kick account, not just an app token. That means: register/authorize a real Kick bot account (equivalent to `@tunastreettest` on Twitch), go through Kick's OAuth device/user flow once to mint a user token + refresh token, and store those the same way `twitch-chat-bot-creds` stores the Twitch bot's — as a NiFi Parameter Context, never a literal property (see `reference_nifi_api_access` memory on why that matters, especially for a processor that also holds a client secret).

**Shape, if built as a NiFi custom Python processor (mirroring `TwitchChatListenerProcessor`):**

- `KickChatListenerProcessor` — holds the Pusher websocket connection open (same subscribe-to-`chatrooms.<id>.v2` pattern proven in `inspector.py`, just persistent instead of a bounded capture window), parses `!load`/`!matrix`-style commands, emits FlowFiles the same shape as the Twitch listener does.
- Routing: since this session's array (`screen1`-`screen4`) is already keyed by "which physical device," a Kick-triggered `!load`/`!matrix` could reuse the *exact same* `TwitchChatBot` `RouteOnAttribute`/`InvokeHTTP` fan-out already built — the screen-dispatch side doesn't care which chat platform the command came from.
- Reply posting: `POST https://api.kick.com/public/v1/chat` with the bot's user access token — needs the same "mint a fresh token before every reconnect" discipline the Twitch listener already has for refresh-token rotation (Kick's OAuth also rotates refresh tokens on use, same as Twitch's).
- Multi-channel: unlike the Twitch bot which lives in one channel (`#tunastarlink`), a Kick bot could plausibly want to watch multiple streamers' channels at once (anyone on the Kick side of the watchlist) — worth deciding up front whether that's one processor with multiple Pusher subscriptions, or one processor instance per channel. Not designed yet.

## TODO / Next steps

- [ ] Decide whether a posting Kick bot is actually wanted, or whether read-only Inspector-style tooling is enough for now — this doc's §4 is a plan, not a commitment.
- [ ] If building it: register a real Kick bot account, complete Kick's OAuth user-token flow once, store creds via a new Parameter Context (never literal properties — this exact processor category is the one that's bitten this session twice already on the Twitch side, see `reference_nifi_api_access` memory).
- [ ] Widen the Twitch bot-detection heuristic in `inspector.py` beyond the static known-bots list if a real gap shows up (it will miss anything not on the list, unlike Kick's clean badge signature).
- [ ] `KickChatListenerProcessor`, if built, should get the same `nifi-custom-processors` deployment discipline as every other processor in this repo — see `reference_nifi_custom_processor_toolchain` memory (PVC + `kubectl cp`, bundle-version bump, `Change Version` in the NiFi UI rather than a scripted GET-then-PUT once any sensitive property exists on it).
- [ ] This doc should get updated the moment any of the above actually gets built, same as `streamers-twitch-bot.md` has been all along.
