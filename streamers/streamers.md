### Twitch Streamers

| Streamer          | X Username          | Clip | GIF |
|-------------------|---------------------|------|-----|
| xQc               | @xQc                | Y    | N   |
| StableRonaldo     | @StableRonaldo      | Y    | N   |
| Jynxzi            | @jynxzi             | Y    | N   |
| ExtraEmily        | @ExtraEmilyy        | Y    | Y   |
| TheBurntPeanut    | @theburntpeanut     | Y    | N   |
| jasontheween      | @jasontheween       | N    | Y   |
| Lacy              | @LacyHimself        | Y    | N   |
| Kai Cenat         | @KaiCenat           | Y    | N   |

### Kick Streamers

| Streamer       | X Username              | Clip | GIF |
|----------------|-------------------------|------|-----|
| Clavicular     | @Clavicular0            | Y    | N   |
| Roshtein       | @roshteins              | Y    | N   |
| Ac7ionMan      | @Ac7ionMann             | Y    | N   |
| AdinRoss       | @adinross               | Y    | N   |
| N3on           | @N3on                   | Y    | N   |
| bbjess         | @bbjess                 | Y    | N   |
| whiz           | @crashoverride          | Y    | N   |
| trainwreckstv  | @trainwreckstv          | Y    | N   |
| rampagejackson | @rampagejackson         | Y    | N   |
| bam            | @BAM__MARGERA           | Y    | N   |

Clip = caption the clip and post the MP4 to X (the original path). GIF = cut a
reaction GIF from the clip and post that instead (the automated #173 giphy
clipping action). A streamer can have both (ExtraEmily) — one approval queues
both posts.

**Source of truth since 2026-08-30 (#275): the `streamer` table in the
`streamers` Postgres database on `ssb-postgresql` (`cld-streaming`)** — one row
per (platform, login) with the X handle, `x_handle_status`
(`confirmed`/`needs_review`), the clip/gif/gif_post flags and `active`
(soft-delete). The app (`backend/services/roster_store.py`) loads it into an
in-process cache at startup and after every write. The old constants in
`backend/services/streamers.py` (`_TWITCH_LOGINS`/`_KICK_LOGINS`,
`_STREAMER_CATALOG`, `_STREAMER_PATH_OVERRIDES`) are now only the **seed** for a
fresh database (inserted once, never overwriting) and the **fallback** if the
database is unreachable — editing them no longer changes a running roster.

**Reboot race (2026-09-07):** after a host reboot the app container came back before
CoreDNS/`ssb-postgresql` did, the one-shot startup connect failed with
`Temporary failure in name resolution`, and — because `start()` never retried — the app
sat on the hardcoded fallback (Watchlist empty, `roster_store_unavailable` from
`/roster/rows`, KB roster path dead) until a pod restart. Fixed the same day:
`roster_store.start()` now hands a failed first connect to a background reconnect loop
(2s → 4s → 8s → 16s, then every 30s) that opens the pool, runs the idempotent migrations
and loads the cache when Postgres becomes reachable, so startup never blocks and a boot
race heals itself; `stop()` cancels the loop. Deployed on `cso-prod-1` 2026-09-07
(`MODULES=rag,streamers,efm`). Symptom to recognise: the log line
`roster_store unavailable, falling back to hardcoded roster …` with no later
`roster_store loaded N streamers` line.

To add a streamer: the mod-only chat command `🐟🐟🐟➕ <streamer>` (#273; `k:`
for Kick — live since listener 0.0.27, 2026-08-30), the **Watchlist sub-tab** in the
Streamers App (#279, 2026-08-30 — the whole table as a grid: inline edit, Deactivate =
the chat ➖ soft-delete, a separate hard Delete for test rows, Add with the chat path's
guards, Pin/Unpin to the feed list), or a direct `INSERT`/`UPDATE` on the table. Keep
the roster table above in sync by hand. A row added from chat or the grid gets its X
handle only from a source the streamer controls (Kick profile socials, a Twitch-bio
x.com link, an X profile linking back); otherwise it's stored as the login with
`needs_review` — the grid highlights those rows amber, and typing the real handle (or
pressing Confirm) flips them to `confirmed`. `bam` → `@BAM__MARGERA` was the last
hand-added seed example (#174).

**Identity columns for the DGX Spark caption brain (#276, 2026-08-30):** `display_name`,
`aliases text[]`, `pronouns` + `pronouns_status` (`confirmed`/`needs_review`) and `notes`
(tone / caption guidance) on the same table, all hand-entered in the grid — **nothing infers
pronouns**; typing them stores `needs_review`, an explicit Confirm makes them `confirmed`.
The Spark reads the **view `streamer_brain`** (`streamer_key` = `login` / `kick:login`,
`display_name`, `aliases`, `x_handle`, `x_handle_confirmed`, `pronouns` — NULL unless
confirmed — `pronouns_confirmed`, `notes`, `active`) as role `streamer_brain`, which can
SELECT that view only, over the `ssb-postgresql-126:5432` / `-121:5432` zellij forwards
(see `CLAUDE-CHECKIN.md`). Role SQL: `files/issue-226/streamers/streamer_brain_role.sql`.
Pronouns were populated 2026-08-31 for all 18 rows via the roster PATCH API, all
`confirmed`: `she/her` for bbjess and ExtraEmily, `he/him` for everyone else.

## In-channel chat bot

`TwitchChatListenerProcessor` (NiFi Python processor, currently **`0.0.30`** — deployed 2026-09-07;
`0.0.28` dropped the rate-limit ladder 2026-09-04, `0.0.29` added `!chat` for the overlay relay
#300, `0.0.30` added its `!c` short form #306. Deploy source is the local-only
`nifi-custom-processors` copy; the `cso-operator-app/nifi-processors/` copy stopped at `0.0.28` —
pull the deployed `.py` from `mynifi-0` before editing) holds a persistent Twitch IRC connection
to the channel and turns chat into actions. It reads each message's mod/broadcaster
badges (IRCv3 `twitch.tv/tags`), so it can gate the mod-only forms. It never calls
the backend inline — a fired trigger only enqueues one `chat_trigger` FlowFile and
returns, because blocking the IRC reader thread through a 30–90s clip job would
blow past Twitch's PING tolerance and force a reconnect (which burns a refresh
token). NiFi's `ChatTriggers` PG routes those FlowFiles to the backend
(`/api/streamers/chat-trigger/{clip,gif,roster}`) and posts the reply back to chat.

### On join
Announces itself once per (re)connect, split across two PRIVMSGs (a single message
caps at 500 chars): first the loader commands, then the chat-trigger help. It does
**not** auto-post the watchlist — reconnects are frequent enough that repeating it
reads as spam.

### Info commands (anyone, on demand)
| Command | Alias | What it does |
|---|---|---|
| `!commands` | `!help` | Reprints the chat-trigger help. |
| `!watchlist` | `!w` | Posts the active streamer watchlist. |

### Stream loader (drives the local screens, not X)
| Command | Alias | What it does |
|---|---|---|
| `!load <streamer> [screen]` | `!l` | Load a stream onto a screen (default `screen1`). Checks live status first via the Live Check API and replies "not live" instead of queuing if they're offline (a lookup failure fails open). |
| `!matrix <screen>` | `!m` (mod-only) | Matrix screensaver on a screen (screen required — no default). |

Screens: `screen1` = Jetson, `screen2` = GamingPC, `screen3`/`screen4` = TunaStarlink.
Mod-only short forms: `!m` for `!matrix`, `k:` in place of `kick:` on a login, and
`s1`–`s4` for `screen1`–`screen4`. A non-mod using any short form is silently
ignored, same as an unknown command; the full-text forms stay open to everyone.

A successful `!load` also fires the **On-Screen Announcer** (#307, live 2026-09-07): the
watchlist bot posts once-ever into the loaded streamer's *own* Twitch channel that they're
up on screen N — see `streamers-twitch-bot.md` §16. **Kick loads are announced too, since
2026-09-07 (evening):** `kick:` logins are skipped by the Twitch announcer and picked up by its
twin `KickOnScreenAnnouncer`, which posts the same line into the streamer's *Kick* channel as
`@tunastreettest` on Kick through the public API (§17; needed a second Kick app for `chat:write`).

### Overlay chat relay (mods/broadcaster only — #300/#306)
| Command | Alias | What it does |
|---|---|---|
| `!chat <streamer\|off\|me>` | `!c` | Re-points @tunastarlink's left-side overlay chat column at another channel's chat (raids/collabs). `off`/`me` return it to @tunastarlink. Twitch channels via the login, Kick via `kick:`/`k:` (relay V2, 0.0.30). Routed through `ChatTriggers` → `InvokeOverlayRelay` → the app's overlay relay. Details: `twitch-overlay-chat-relay-plan.md`. |

### Chat triggers (no `!` prefix)
Matched prefix-anchored against a normalized copy of the message (invisible
tag-selector + variation selectors stripped, NFKC, whitespace collapsed,
lowercased), evaluated most-specific-first. A trigger with no streamer named
targets whoever was last `!load`ed in this process.

| Trigger | Who | Effect |
|---|---|---|
| `tuna tuna tuna [streamer]` or `🐟🐟🐟 [streamer]` | Everyone | **Watchlist vote** — adds the streamer once it lands `Trigger Vote Count` (3) times inside `Trigger Vote Window Seconds` (120). Every occurrence counts (including one person repeating); the tally is per (trigger, target). Posts one progress reply when it's exactly one vote short. |
| `🐟🐟🐟🎬 [streamer]` or `tuna tuna tuna clip` | **Mods/broadcaster** | Pulls a **clip** and posts it — one use, no vote. Falls back to the streamer's all-time top clips when the current month window is empty (#299, 2026-09-06). |
| `🐟🐟🐟🖼️ [streamer]` or `tuna tuna tuna gif` | **Mods/broadcaster** | Cuts a **reaction GIF** and posts it — one use, no vote. |
| `🐟🐟🐟➕ <streamer>` | **Mods/broadcaster** | **Adds the streamer to the roster** (#273, listener 0.0.27) — the catalog above, not the watch list. The name is required (no on-screen fallback). The backend checks the channel exists, then researches the X handle: confirmed only from a source the streamer controls (Kick profile socials, a Twitch-bio x.com link, an X profile linking back to the channel); otherwise stored as `@login` + `needs_review` and the reply says to verify it. |
| `🐟🐟🐟➖ <streamer>` | **Mods/broadcaster** | **Removes the streamer from the roster** (soft-delete — the row and its curated handle are kept; a later ➕ restores it as it was). |

A non-mod using the clip/gif/➕/➖ triggers is ignored silently. All of them name a
streamer on either platform — `🐟🐟🐟🖼️ k:<login>` pulls from Kick, `🐟🐟🐟➕ k:<login>`
adds a Kick streamer. The manual pull does **not** require the target to be live or
on the watch list (there just has to be a clip to grab); the watch list only governs
who the pipeline polls on its own. The chat trigger for clip/gif has a one-shot
retry on a transient X failure (429 / timeout / 5xx — #274); permanent rejections
(duplicate, too long, credentials) are reported straight back.

### Enable switches (NiFi processor properties)
- **`Clip Trigger Enabled` / `Gif Trigger Enabled`** — both default **false**: the
  clip/gif triggers ship dark, and these are the instant off-switch during a raid.
- **There is no rate limiting any more.** The whole ladder — the shared `!load`/`!matrix`
  `Cooldown Seconds`, the per-trigger global / per-user / per-target windows, the rolling-24h
  `Clip Daily Cap` / `Gif Daily Cap`, the mod bypass, and every "slow down" / "cooling down" /
  "budget is spent" reply — was **removed in `0.0.28` (2026-09-04)**. Only the operator and
  trusted mods run these commands, so the throttles only ever slowed them down. `_check_limit`
  is now a pass-through. The watchlist **vote gate** (`Trigger Vote Count` / `Trigger Vote
  Window Seconds`) and the two enable switches are unchanged — they aren't speed throttles.

### Watchlist / X-post link
Voting a streamer onto the watchlist only makes the pipeline poll them for clips;
whether a fetched clip/gif actually posts to X, and under which handle, comes from
the roster + `_STREAMER_CATALOG` above. A manual clip/gif trigger reaches X through
the same `publish_clip` path as the GIFs-tab **Post Now** button.
