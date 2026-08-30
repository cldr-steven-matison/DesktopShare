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

To add a streamer: the mod-only chat command `🐟🐟🐟➕ <streamer>` (#273; `k:`
for Kick) once its listener is deployed, or a direct `INSERT`/`UPDATE` on the
table. Keep the roster table above in sync by hand. A row added from chat gets
its X handle only from a source the streamer controls (Kick profile socials, a
Twitch-bio x.com link, an X profile linking back); otherwise it's stored as the
login with `needs_review` — check `SELECT login, x_handle FROM streamer WHERE
x_handle_status = 'needs_review'` and fix it with `UPDATE`. `bam` →
`@BAM__MARGERA` was the last hand-added seed example (#174).

## In-channel chat bot

`TwitchChatListenerProcessor` (NiFi Python processor, currently `0.0.26`, source
in `cso-operator-app/nifi-processors/`) holds a persistent Twitch IRC connection
to the channel and turns chat into actions. It reads each message's mod/broadcaster
badges (IRCv3 `twitch.tv/tags`), so it can gate the mod-only forms. It never calls
the backend inline — a fired trigger only enqueues one `chat_trigger` FlowFile and
returns, because blocking the IRC reader thread through a 30–90s clip job would
blow past Twitch's PING tolerance and force a reconnect (which burns a refresh
token). NiFi's `ChatTriggers` PG routes those FlowFiles to the backend
(`/api/streamers/chat-trigger/{clip,gif}`) and posts the reply back to chat.

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

### Chat triggers (no `!` prefix)
Matched prefix-anchored against a normalized copy of the message (invisible
tag-selector + variation selectors stripped, NFKC, whitespace collapsed,
lowercased), evaluated most-specific-first. A trigger with no streamer named
targets whoever was last `!load`ed in this process.

| Trigger | Who | Effect |
|---|---|---|
| `tuna tuna tuna [streamer]` or `🐟🐟🐟 [streamer]` | Everyone | **Watchlist vote** — adds the streamer once it lands `Trigger Vote Count` (3) times inside `Trigger Vote Window Seconds` (120). Every occurrence counts (including one person repeating); the tally is per (trigger, target). Posts one progress reply when it's exactly one vote short. |
| `🐟🐟🐟🎬 [streamer]` or `tuna tuna tuna clip` | **Mods/broadcaster** | Pulls a **clip** and posts it — one use, no vote. |
| `🐟🐟🐟🖼️ [streamer]` or `tuna tuna tuna gif` | **Mods/broadcaster** | Cuts a **reaction GIF** and posts it — one use, no vote. |

A non-mod using the clip/gif trigger is ignored silently. Both name a streamer on
either platform — `🐟🐟🐟🖼️ k:<login>` pulls from Kick. The manual pull does **not**
require the target to be live or on the watch list (there just has to be a clip to
grab); the watch list only governs who the pipeline polls on its own.

### Enable switches & rate limits (NiFi processor properties)
- **`Clip Trigger Enabled` / `Gif Trigger Enabled`** — both default **false**: the
  clip/gif triggers ship dark, and these are the instant off-switch during a raid.
- **Rate-limit ladder** — `!load`/`!matrix` share one global `Cooldown Seconds`.
  Each trigger must clear a global window, a per-user window, and a per-target
  window, plus a rolling-24h daily cap for clip/gif (`Clip Daily Cap` /
  `Gif Daily Cap`, separate budgets). Watchlist windows: 300s/user, 3600s/target;
  clip & gif: per-target 21600s.
- **Mod/broadcaster bypass** — a moderator or the broadcaster bypasses **every**
  window *and* the daily cap. Every one of these gates only ever applied to the
  mod-only clip/gif triggers, so they were purely slowing the operator down (#174).

### Watchlist / X-post link
Voting a streamer onto the watchlist only makes the pipeline poll them for clips;
whether a fetched clip/gif actually posts to X, and under which handle, comes from
the roster + `_STREAMER_CATALOG` above. A manual clip/gif trigger reaches X through
the same `publish_clip` path as the GIFs-tab **Post Now** button.
