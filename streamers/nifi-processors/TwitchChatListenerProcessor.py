# TwitchChatListenerProcessor.py
import collections
import json
import queue
import socket
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import urllib.parse

from nifiapi.flowfilesource import FlowFileSource, FlowFileSourceResult
from nifiapi.properties import PropertyDescriptor, StandardValidators


class TwitchChatListenerProcessor(FlowFileSource):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileSource']

    class ProcessorDetails:
        version = '0.0.30-SNAPSHOT'
        description = 'Holds a persistent connection to Twitch IRC chat and emits one FlowFile per detected "!load <streamer> [screen]" command (screen optional, defaults to screen1, "!l" accepted as a short alias) or "!matrix <screen1|screen2|screen3|screen4>" command (screen required, no default - unlike !load, a bare "!matrix" with no screen is not a recognized command; screen1 targets the Jetson, screen2 targets GamingPC, screen3/screen4 target TunaStarlink). Requests the twitch.tv/tags IRCv3 capability to read each message'"'"'s badges/mod tags. Mod-only short forms: "!m" for !matrix, "k:" in place of "kick:" on a streamer login, and "s1"/"s2"/"s3"/"s4" in place of screen1-4 - each is checked independently, and a non-broadcaster/non-moderator sender using any of them has the whole command silently ignored (same as an unrecognized command); the existing full-text forms (including the pre-existing "!l" alias) keep working for everyone, unchanged. Before dispatching a !load, checks the streamer'"'"'s live status via the Live Check API URL (cso-operator-app, covers both Twitch and Kick "kick:" logins) and replies "not live" instead of queuing if they'"'"'re offline - a lookup failure fails open (dispatches anyway) rather than silently blocking a real load. Also carries prefix-anchored chat triggers that need no "!" prefix, matched against a normalized copy of the message (Twitch'"'"'s invisible TAG-SELECTOR stripped, variation selectors stripped, NFKC, whitespace collapsed, lowercased) and evaluated most-specific-first: the Watchlist Trigger Command ("tuna tuna tuna" by default) or its three-fish-emoji equivalent, optionally followed by a streamer name, adds that streamer to the watchlist once Trigger Vote Count (default 3) occurrences land inside Trigger Vote Window Seconds (default 120) - every occurrence counts, including one person repeating themselves, and the tally is per (trigger, target) so three people naming three streamers is three separate tallies; it is open to everyone and posts a single progress reply one vote short of firing. The three-fish-plus-clapper form (or "<Watchlist Trigger Command> clip") is broadcaster/moderator-only, fires on one use with no vote, and requests a real clip post; a non-mod using it is ignored silently, exactly like the other mod-only short forms. It is gated behind Clip Trigger Enabled (default false - the feature ships dark and that property is the instant off-switch during a raid) and a rolling 24-hour Clip Daily Cap. The three-fish-plus-picture form (or "<Watchlist Trigger Command> gif") is its exact twin for reaction GIFs - same mod-only gate, one use, no vote - gated behind its own Gif Trigger Enabled and Gif Daily Cap on a separate rate-limit budget. A trigger with no streamer named targets whoever was last loaded by !load in this running process, and says so once (rate-limited) if nothing has been loaded yet. Rate limiting is one generic ladder: !load and !matrix share the single global Cooldown Seconds timer they always have, while each trigger must clear a global, a per-user and a per-target window (plus a rolling daily cap, for clip/gif) before it fires - a moderator/broadcaster bypasses all of them, the daily cap included, since every one of these gates only ever applied to mods (the clip/gif triggers are mod-only) and was purely slowing the operator down (#174). A fired trigger only enqueues a "chat_trigger" FlowFile and returns immediately; the listener never calls the backend itself, because blocking the IRC reader thread through a 30-90s clip job would blow past Twitch'"'"'s PING tolerance and force a reconnect, burning a refresh token every time. Announces itself once on join across two messages (a single PRIVMSG caps at 500 characters) with no auto-posted watchlist - reconnects happen often enough that repeating it every time reads as spam; responds to "!commands"/"!help" and "!watchlist" ("!w" alias accepted) on demand only. Mints a fresh access token from the refresh token before every (re)connect, so it never hits the ~4hr access-token expiry. Twitch rotates the refresh token on every one of those refreshes, so the rotated value is persisted to NiFi component state (Scope.LOCAL, key "refresh_token") and read back on the next onScheduled - a restart no longer needs a manual device-code re-auth. The write is deferred to create()/onStopped rather than done inline, because the refresh runs on the background IRC thread and the state manager is a py4j bridge into the JVM. Reconnects with backoff on disconnect. The three-fish-plus-➕ and three-fish-plus-➖ forms (#273) are broadcaster/moderator-only roster edits: "<fish>➕ <streamer>" adds that streamer to the app'"'"'s streamer roster (the catalog, not the watchlist) and "<fish>➖ <streamer>" removes them, "kick:"/"k:" prefixes accepted; a non-mod using either is ignored silently, a bare form with no name is refused with a nudge (a roster edit has to name who, there is no on-screen fallback), and like every trigger they only enqueue a "chat_trigger" FlowFile (chat_action roster_add/roster_remove) - the backend does the channel-exists check and the X-handle research and posts the real outcome through the reply processor. Also handles a broadcaster/moderator-only "!chat <streamer|off|me>" command (short form "!c <streamer|off|me>", like !l/!m/!w; a bare "!c" with no argument is short for !commands) that re-points @tunastarlink'"'"'s left-side overlay chat column at another channel'"'"'s chat for raids/collabs - a target may be a Twitch login or a "kick:"/"k:" slug (Kick relay is live), and "off"/"me" return it to this channel'"'"'s own chat; a non-mod is ignored silently. It emits an "overlay_relay" FlowFile carrying the channel argument verbatim (attribute + request body); the flow'"'"'s RouteOnAttribute -> InvokeHTTP posts it to the overlay backend'"'"'s POST /api/overlay/relay, which normalizes off/me/own and a "kick:" target to own chat (v1 relay is Twitch-only).'
        tags = ['twitch', 'irc', 'chat', 'streamers', 'chat-bot']
        dependencies = []

    BOT_USERNAME = PropertyDescriptor(
        name="Bot Username",
        description="Twitch login name of the bot account (e.g. tunastreettest).",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CHANNEL = PropertyDescriptor(
        name="Channel",
        description="Twitch channel to join, without a leading #.",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CLIENT_ID = PropertyDescriptor(
        name="Client ID",
        description="Twitch app client ID used to mint fresh access tokens via the refresh token grant.",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CLIENT_SECRET = PropertyDescriptor(
        name="Client Secret",
        description="Twitch app client secret used to mint fresh access tokens via the refresh token grant.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    REFRESH_TOKEN = PropertyDescriptor(
        name="Refresh Token",
        description="User refresh token for the bot account (chat:read+chat:edit scopes). A SEED only, not the token in ongoing use: Twitch rotates the refresh token on every use, so the rotated value is persisted to component state and this property is read only when state is empty (first ever start, or after a deliberate re-seed). To force a re-seed, paste a freshly minted token here (or in the Parameter Context) and restart - a dead stored token is dropped automatically on HTTP 400.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    COMMAND_PREFIX = PropertyDescriptor(
        name="Command Prefix",
        description="Chat command that triggers a load.",
        required=True,
        default_value="!load",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    MATRIX_COMMAND = PropertyDescriptor(
        name="Matrix Command",
        description="Chat command that turns on the Nano's matrix screensaver.",
        required=True,
        default_value="!matrix",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    WATCHLIST_COMMAND = PropertyDescriptor(
        name="Watchlist Command",
        description="Chat command that posts the active streamer watchlist on demand (same message as the on-join post).",
        required=True,
        default_value="!watchlist",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    OVERLAY_COMMAND = PropertyDescriptor(
        name="Overlay Command",
        description="Broadcaster/moderator-only chat command that re-points the left-side overlay chat "
                     "column at another channel's chat (raids/collabs). Used as \"<this> <streamer|off|me>\", "
                     "with \"!c <streamer|off|me>\" accepted as the short form (a bare \"!c\" with no argument "
                     "is short for !commands). A target may be a Twitch login or a \"kick:\"/\"k:\" slug; "
                     "off/me return the column to this channel's own chat. Emits an 'overlay_relay' FlowFile; "
                     "the flow's RouteOnAttribute -> InvokeHTTP posts it to the overlay backend.",
        required=True,
        default_value="!chat",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    WATCHLIST_TRIGGER_COMMAND = PropertyDescriptor(
        name="Watchlist Trigger Command",
        description="Word-form chat trigger that votes a streamer onto the watchlist - no leading '!', "
                     "matched prefix-anchored against a normalized message. The three-fish-emoji form is "
                     "always accepted alongside it, and appending 'clip' to this same phrase is the "
                     "word-form of the mod-only clip trigger.",
        required=True,
        default_value="tuna tuna tuna",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CLIP_TRIGGER_ENABLED = PropertyDescriptor(
        name="Clip Trigger Enabled",
        description="Master switch for the mod-only clip trigger. Default false: the feature ships dark "
                     "and is turned on with a one-key property edit. Flipping it back to false is the "
                     "instant off-switch during a raid - a clip trigger from a mod is then ignored "
                     "silently, and the clip trigger is dropped from the join/!commands help text.",
        required=True,
        default_value="false",
        validators=[StandardValidators.BOOLEAN_VALIDATOR],
    )
    TRIGGER_VOTE_COUNT = PropertyDescriptor(
        name="Trigger Vote Count",
        description="Occurrences of the watchlist trigger, for the same target, needed inside the vote "
                     "window before it fires. Every occurrence counts - the same user repeating it is "
                     "deliberately not de-duplicated.",
        required=True,
        default_value="3",
        validators=[StandardValidators.NUMBER_VALIDATOR],
    )
    TRIGGER_VOTE_WINDOW_SECONDS = PropertyDescriptor(
        name="Trigger Vote Window Seconds",
        description="Rolling window the vote count is measured over. Expired occurrences are pruned on "
                     "every match, so this is a sliding window, not a fixed round.",
        required=True,
        default_value="120",
        validators=[StandardValidators.NUMBER_VALIDATOR],
    )
    WATCHLIST_COOLDOWN_SECONDS = PropertyDescriptor(
        name="Watchlist Cooldown Seconds",
        description="Global cooldown between two watchlist triggers firing. A per-user (300s) and a "
                     "per-target (3600s) window apply on top of it - a trigger must clear all three.",
        required=True,
        default_value="60",
        validators=[StandardValidators.NUMBER_VALIDATOR],
    )
    CLIP_COOLDOWN_SECONDS = PropertyDescriptor(
        name="Clip Cooldown Seconds",
        description="Global cooldown between two clip triggers firing. A per-user (3600s) and a "
                     "per-target (21600s) window apply on top of it, plus the rolling Clip Daily Cap. "
                     "Moderators bypass all of these (and the cap) - every gate here is mod-only anyway, "
                     "so it was only ever slowing the operator down (#174).",
        required=True,
        default_value="900",
        validators=[StandardValidators.NUMBER_VALIDATOR],
    )
    CLIP_DAILY_CAP = PropertyDescriptor(
        name="Clip Daily Cap",
        description="Maximum clip triggers in any rolling 24 hours, applied to non-privileged callers "
                     "only - moderators/broadcaster bypass it (#174). Rolling rather than calendar-day on "
                     "purpose, so the budget can't be burned in a burst the moment UTC midnight ticks over.",
        required=True,
        default_value="4",
        validators=[StandardValidators.NUMBER_VALIDATOR],
    )
    GIF_TRIGGER_ENABLED = PropertyDescriptor(
        name="Gif Trigger Enabled",
        description="Master switch for the mod-only gif trigger (🐟🐟🐟🖼️). Default false, same as the "
                     "clip trigger: ships dark, turned on with a one-key edit, and flipping it back to "
                     "false is the instant off-switch - a gif trigger from a mod is then ignored silently "
                     "and dropped from the join/!commands help text.",
        required=True,
        default_value="false",
        validators=[StandardValidators.BOOLEAN_VALIDATOR],
    )
    GIF_COOLDOWN_SECONDS = PropertyDescriptor(
        name="Gif Cooldown Seconds",
        description="Global cooldown between two gif triggers firing. A per-user (3600s) and a "
                     "per-target (21600s) window apply on top of it, plus the rolling Gif Daily Cap - "
                     "the gif twin of Clip Cooldown Seconds, on its own separate budget.",
        required=True,
        default_value="900",
        validators=[StandardValidators.NUMBER_VALIDATOR],
    )
    GIF_DAILY_CAP = PropertyDescriptor(
        name="Gif Daily Cap",
        description="Maximum gif triggers in any rolling 24 hours, counted separately from clips. "
                     "Applied to non-privileged callers only - moderators/broadcaster bypass it (#174).",
        required=True,
        default_value="4",
        validators=[StandardValidators.NUMBER_VALIDATOR],
    )
    TRIGGER_PROGRESS_REPLIES = PropertyDescriptor(
        name="Trigger Progress Replies",
        description="When true (default), posts one progress reply when a watchlist vote is exactly one "
                     "short of firing - silent at every earlier count. The reply names the target so two "
                     "consecutive progress replies always differ; Twitch drops a bot's identical repeat "
                     "inside roughly 30 seconds.",
        required=True,
        default_value="true",
        validators=[StandardValidators.BOOLEAN_VALIDATOR],
    )
    WATCHLIST_API_URL = PropertyDescriptor(
        name="Watchlist API URL",
        description="cso-operator-app in-cluster URL for the active streamer watchlist, "
                     "fetched and posted to chat on join.",
        required=True,
        default_value="http://cso-operator-app.default.svc.cluster.local:8090/api/streamers/watchlist",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    LIVE_CHECK_API_URL = PropertyDescriptor(
        name="Live Check API URL",
        description="cso-operator-app in-cluster URL checked before dispatching a !load - "
                     "?login=<streamer> is appended (kick: prefix passed through as-is). "
                     "Expected JSON: {\"live\": true|false}.",
        required=True,
        default_value="http://cso-operator-app.default.svc.cluster.local:8090/api/streamers/live",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    COOLDOWN_SECONDS = PropertyDescriptor(
        name="Cooldown Seconds",
        description="Global cooldown shared by !load and !matrix (one timer, not per-command) - "
                     "protects the edge hardware from chat spam. First blocked attempt within the "
                     "window gets one warning reply, further spam in the same window is silent.",
        required=True,
        default_value="10",
        validators=[StandardValidators.NUMBER_VALIDATOR],
    )
    def __init__(self, **kwargs):
        # 'pass' is the safest initialization in many containerized environments —
        # real state is set up in onScheduled, which is guaranteed to run before create().
        pass

    def getPropertyDescriptors(self):
        return [self.BOT_USERNAME, self.CHANNEL, self.CLIENT_ID, self.CLIENT_SECRET,
                self.REFRESH_TOKEN, self.COMMAND_PREFIX, self.MATRIX_COMMAND,
                self.WATCHLIST_COMMAND, self.OVERLAY_COMMAND, self.WATCHLIST_TRIGGER_COMMAND,
                self.CLIP_TRIGGER_ENABLED, self.GIF_TRIGGER_ENABLED,
                self.TRIGGER_VOTE_COUNT,
                self.TRIGGER_VOTE_WINDOW_SECONDS, self.WATCHLIST_COOLDOWN_SECONDS,
                self.CLIP_COOLDOWN_SECONDS, self.CLIP_DAILY_CAP,
                self.GIF_COOLDOWN_SECONDS, self.GIF_DAILY_CAP,
                self.TRIGGER_PROGRESS_REPLIES, self.WATCHLIST_API_URL,
                self.LIVE_CHECK_API_URL, self.COOLDOWN_SECONDS]

    # Component-state key holding the rotated refresh token. NiFi scopes component state per
    # processor instance, so this never collides with WatchlistChatJoinerProcessor's copy.
    STATE_KEY_REFRESH_TOKEN = 'refresh_token'

    def onScheduled(self, context):
        username = context.getProperty(self.BOT_USERNAME).getValue()
        channel = context.getProperty(self.CHANNEL).getValue().lstrip('#')
        client_id = context.getProperty(self.CLIENT_ID).getValue()
        client_secret = context.getProperty(self.CLIENT_SECRET).getValue()
        prefix = context.getProperty(self.COMMAND_PREFIX).getValue()
        matrix_command = context.getProperty(self.MATRIX_COMMAND).getValue()
        watchlist_command = context.getProperty(self.WATCHLIST_COMMAND).getValue()
        overlay_command = context.getProperty(self.OVERLAY_COMMAND).getValue()
        watchlist_url = context.getProperty(self.WATCHLIST_API_URL).getValue()
        live_check_url = context.getProperty(self.LIVE_CHECK_API_URL).getValue()
        cooldown_seconds = context.getProperty(self.COOLDOWN_SECONDS).asFloat()

        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._command_prefix = prefix
        self._matrix_command = matrix_command
        self._watchlist_command = watchlist_command
        self._overlay_command = overlay_command
        self._watchlist_url = watchlist_url
        self._live_check_url = live_check_url
        self._cooldown_seconds = cooldown_seconds
        # The property is a seed, not the token in ongoing use: Twitch rotates the refresh
        # token on every use, so the live value lives in component state and the property is
        # only consulted when state is empty (first ever start, or after a deliberate re-seed).
        # Guarded: a NiFi build without the state binding must degrade to the old property-seed
        # behaviour, not fail to start the processor at all.
        try:
            self._state_manager = context.getStateManager()
        except Exception as e:
            self._state_manager = None
            if self.logger:
                self.logger.warn(f"Component state unavailable; the rotated Twitch refresh token "
                                 f"will not survive a restart: {e}")
        self._property_seed = context.getProperty(self.REFRESH_TOKEN).getValue()
        self._pending_token_write = None
        self._pending_state_clear = False
        self._reseed_attempted = False
        stored = self._read_stored_refresh_token()
        if stored:
            self._refresh_token = stored
            self._token_source = 'state'
        else:
            self._refresh_token = self._property_seed
            self._token_source = 'property'
        if self.logger:
            self.logger.info(f"Twitch refresh token seeded from {self._token_source}")

        self._configure_triggers(context)

        self._thread = threading.Thread(
            target=self._run_irc_loop,
            args=(username, channel, client_id, client_secret),
            daemon=True,
        )
        self._thread.start()

    def onStopped(self, context):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        # Join first, then flush: the thread can rotate the token one last time on its way
        # out, and a clean stop is exactly the case where losing that rotation would force
        # the manual re-auth this whole mechanism exists to remove.
        self._flush_pending_token_write()

    def create(self, context):
        # Runs on a NiFi task thread, so this is the safe place to touch the py4j state
        # bridge - _refresh_access_token cannot, it runs on the daemon IRC thread. Ahead of
        # the queue check because the common case is an empty queue and the pending write
        # still has to land.
        self._flush_pending_token_write()
        try:
            item = self._queue.get_nowait()
        except queue.Empty:
            return None

        # item.get('screen', ''): chat_trigger items carry no meaningful screen, and a
        # KeyError here would take out the whole create() call rather than just that item.
        attributes = {'command': item['command'], 'requested_by': item['requested_by'],
                      'screen': item.get('screen', '')}
        if 'streamer' in item:
            attributes['streamer'] = item['streamer']
        if 'display_screen' in item:
            attributes['display_screen'] = item['display_screen']
        # Promoted so RouteOnAttribute can fan chat_trigger items out by action without
        # parsing the body; the body itself stays the backend request payload, unchanged.
        for key in ('chat_action', 'login', 'platform', 'channel'):
            if key in item:
                attributes[key] = item[key]

        return FlowFileSourceResult(
            relationship='success',
            attributes=attributes,
            contents=json.dumps(item),
        )

    # --- IRC connection handling (background thread) ---

    def _refresh_access_token(self, client_id, client_secret):
        try:
            return self._request_access_token(client_id, client_secret)
        except urllib.error.HTTPError as e:
            # 400 here means the refresh token itself is dead, not that Twitch is unreachable.
            # If the dead one came out of component state, drop it and give the property seed
            # exactly one chance - that makes re-seeding "paste a fresh token into the Parameter
            # Context and restart" instead of a code change. Only once per run: retrying a seed
            # that is itself spent just burns calls and muddies the log.
            if e.code != 400 or self._token_source != 'state' or self._reseed_attempted:
                raise
            self._reseed_attempted = True
            if self.logger:
                self.logger.warn("Persisted Twitch refresh token was rejected (HTTP 400); "
                                 "clearing component state and retrying once from the property seed")
            self._pending_state_clear = True
            self._refresh_token = self._property_seed
            self._token_source = 'property'
            return self._request_access_token(client_id, client_secret)

    def _request_access_token(self, client_id, client_secret):
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }).encode()
        req = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=body, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            # Without this, _run_irc_loop's broad except swallows a dead/rotated refresh
            # token into the same 5->60s backoff a network blip produces, and a botched
            # deploy looks exactly like Twitch being unreachable. Log Twitch's own body.
            detail = e.read().decode('utf-8', errors='ignore')[:500]
            if self.logger:
                self.logger.error(f"Twitch token refresh rejected: HTTP {e.code} {detail}")
            raise
        if "access_token" not in payload:
            raise RuntimeError(f"Twitch token refresh returned no access_token: {json.dumps(payload)[:500]}")
        # Twitch rotates the refresh token on every use — the old one is now invalid,
        # so this new one is what every subsequent refresh (in this running process) must use.
        # It has been observed absent on some responses; keeping the previous value is
        # strictly better than a KeyError that reads as a connection failure.
        rotated = payload.get("refresh_token")
        if rotated:
            self._refresh_token = rotated
            self._token_source = 'state'
            # Stashed, not written: this runs on the daemon IRC thread and the state manager is
            # a py4j bridge into the JVM. create()/onStopped flush it from a NiFi task thread.
            # Worst case on a crash between here and the flush is one lost rotation - exactly
            # today's behaviour, so this fails no worse than the status quo.
            self._pending_token_write = rotated
        elif self.logger:
            self.logger.warn("Twitch token refresh returned no refresh_token; keeping the previous one")
        return payload["access_token"]

    # --- Component state: the rotated refresh token ---
    #
    # Imported lazily rather than at module scope: nifiapi.componentstate resolves
    # Scope.LOCAL/CLUSTER through the py4j JVM bridge at import time.
    # State is not encrypted the way a sensitive property is, and this pod's volumes are
    # emptyDir - so this survives a processor or NiFi restart, but not a pod delete. A pod
    # delete already destroys the entire flow, so that is no worse than the flow's own
    # durability. Every one of these is best-effort: a state failure must never take down the
    # IRC loop, since the in-memory token still works for the life of the process.

    def _read_stored_refresh_token(self):
        if self._state_manager is None:
            return None
        try:
            from nifiapi.componentstate import Scope
            return self._state_manager.getState(Scope.LOCAL).get(self.STATE_KEY_REFRESH_TOKEN)
        except Exception as e:
            if self.logger:
                self.logger.warn(f"Could not read the persisted Twitch refresh token from state, "
                                 f"falling back to the property seed: {e}")
            return None

    def _flush_pending_token_write(self):
        """Drain whatever the IRC thread stashed. Main/task thread only."""
        if self._state_manager is None:
            return
        if self._pending_state_clear:
            self._pending_state_clear = False
            try:
                from nifiapi.componentstate import Scope
                self._state_manager.clear(Scope.LOCAL)
            except Exception as e:
                if self.logger:
                    self.logger.warn(f"Could not clear the rejected Twitch refresh token from state: {e}")
        token = self._pending_token_write
        if not token:
            return
        # Cleared before the write, not after: a failing setState that left the value pending
        # would retry on every create() call, which at a 0-sec schedule is a hot loop.
        self._pending_token_write = None
        try:
            from nifiapi.componentstate import Scope
            state = self._state_manager.getState(Scope.LOCAL).toMap()
            state[self.STATE_KEY_REFRESH_TOKEN] = token
            self._state_manager.setState(state, Scope.LOCAL)
        except Exception as e:
            if self.logger:
                self.logger.warn(f"Could not persist the rotated Twitch refresh token; this run is "
                                 f"fine but the next restart will need a re-seed: {e}")

    def _run_irc_loop(self, username, channel, client_id, client_secret):
        backoff = 5
        while not self._stop_event.is_set():
            try:
                access_token = self._refresh_access_token(client_id, client_secret)
                self._connect_and_listen(username, channel, access_token)
                backoff = 5  # reset after a clean-ish disconnect
            except Exception as e:
                if self.logger:
                    # The exception type is the whole diagnosis here: HTTPError/RuntimeError
                    # means auth (a bad deploy), socket/ConnectionError means the network.
                    self.logger.error(f"Twitch IRC connection error [{type(e).__name__}]: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def _connect_and_listen(self, username, channel, token):
        raw_token = token[6:] if token.startswith('oauth:') else token
        sock = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=30)
        sock.settimeout(30)
        try:
            self._send(sock, f"PASS oauth:{raw_token}")
            self._send(sock, f"NICK {username.lower()}")
            # twitch.tv/tags carries each PRIVMSG's badges/mod fields - needed to
            # gate the mod-only short command forms below. Not awaited/ACK-checked;
            # by convention it's granted well before JOIN's own response arrives.
            self._send(sock, "CAP REQ :twitch.tv/tags")
            self._send(sock, f"JOIN #{channel.lower()}")
            # A reconnect means the chat context these tallies were counting is gone -
            # nobody should come back to a half-finished vote from before the drop. The
            # rate-limit ledger and the rolling clip history deliberately survive: they
            # protect the backend, and reconnects are frequent enough that clearing them
            # would hand out a fresh budget on every blip.
            self._votes.clear()
            self._current_streamer = None
            self._send_chat(sock, channel,
                             f"{username} is online! Type {self._command_prefix} (or !l) <streamer> [screen1|screen2|screen3|screen4] to load a stream, "
                             f"{self._matrix_command} <screen1|screen2|screen3|screen4> for the matrix screensaver, {self._watchlist_command} (or !w) for who's on watch, "
                             f"or !commands for help.")
            # Second message, not a longer first one: a PRIVMSG caps at 500 characters and
            # the announcement above is already ~240, so the trigger half would truncate.
            self._send_chat(sock, channel, self._trigger_help_message())

            # Bytes, not str. Decoding each 4096-byte recv on its own silently drops the
            # leading bytes of any multi-byte character straddling the boundary (a 4-byte
            # fish emoji is a regular casualty in a busy channel) - errors='ignore' makes
            # that failure invisible, and the emoji trigger would just never fire. Split
            # complete lines off the raw buffer and decode each one whole.
            buffer = b""
            while not self._stop_event.is_set():
                try:
                    data = sock.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    raise ConnectionError("Twitch IRC connection closed by server")
                buffer += data
                while b"\r\n" in buffer:
                    raw_line, buffer = buffer.split(b"\r\n", 1)
                    self._handle_line(sock, raw_line.decode('utf-8', errors='ignore'), channel)
        finally:
            sock.close()

    def _send(self, sock, message):
        sock.sendall((message + "\r\n").encode('utf-8'))

    def _send_chat(self, sock, channel, message):
        self._send(sock, f"PRIVMSG #{channel.lower()} :{message}")

    # --- Chat triggers ---

    # Written as escapes, not literals: these two are the load-bearing match tokens and
    # this file gets copied between hosts and into a container.
    _FISH = '\U0001f41f'      # 🐟
    _CLAPPER = '\U0001f3ac'   # 🎬
    # 🖼️ is FRAME WITH PICTURE + VS-16; _normalize strips the selector, so the
    # bare code point is what the registry matches, same as _CLAPPER.
    _PICTURE = '\U0001f5bc'   # 🖼
    # ➕ / ➖ (HEAVY PLUS/MINUS SIGN) - the mod-only roster add/remove triggers
    # (#273). Single code points, unchanged by NFKC, and any VS-16 a client
    # appends is stripped by _normalize, same as the two above.
    _PLUS = '\u2795'      # ➕
    _MINUS = '\u2796'     # ➖
    # Twitch clients append this invisible TAG-SELECTOR to dodge the duplicate-message
    # filter. Leave it in and the SECOND identical trigger message stops matching, which
    # means a 3-occurrence vote can never complete and nothing anywhere reports an error.
    _TAG_SELECTOR = '\U000e0000'
    # VARIATION SELECTOR-16 / -15: emoji-vs-text presentation, invisible either way.
    _VARIATION_SELECTORS = ('\ufe0f', '\ufe0e')

    # Every rate-limit class a trigger has to clear, as (class, scope). A trigger clears
    # all of its classes or none of them.
    _LIMIT_SCOPES = {
        'device': (('device', 'global'),),
        'notarget': (('notarget', 'global'),),
        'watchlist': (('watchlist', 'global'), ('watchlist:user', 'user'), ('watchlist:target', 'target')),
        'clip': (('clip', 'global'), ('clip:user', 'user'), ('clip:target', 'target')),
        'gif': (('gif', 'global'), ('gif:user', 'user'), ('gif:target', 'target')),
    }
    # The per-user/per-target windows aren't properties: they're the shape of the
    # protection, not a knob. The global window of each class is the property.
    _LIMIT_SUBWINDOWS = {
        'watchlist:user': 300.0,
        'watchlist:target': 3600.0,
        'clip:user': 3600.0,
        'clip:target': 21600.0,
        'gif:user': 3600.0,
        'gif:target': 21600.0,
        'notarget': 60.0,
    }
    # Both post-to-X triggers carry a rolling 24h cap on their own history deque.
    _CAP_WINDOW = 86400.0
    # This thread stays up for weeks; the vote table is keyed by (trigger, target) and
    # anyone can invent a new target, so it needs a hard ceiling as well as expiry.
    _VOTE_KEY_CAP = 32

    def _configure_triggers(self, context):
        self._watchlist_trigger = context.getProperty(self.WATCHLIST_TRIGGER_COMMAND).getValue()
        self._clip_trigger_enabled = context.getProperty(self.CLIP_TRIGGER_ENABLED).asBoolean()
        self._gif_trigger_enabled = context.getProperty(self.GIF_TRIGGER_ENABLED).asBoolean()
        self._vote_count = max(1, context.getProperty(self.TRIGGER_VOTE_COUNT).asInteger())
        self._vote_window_seconds = context.getProperty(self.TRIGGER_VOTE_WINDOW_SECONDS).asFloat()
        self._daily_caps = {
            'clip': max(0, context.getProperty(self.CLIP_DAILY_CAP).asInteger()),
            'gif': max(0, context.getProperty(self.GIF_DAILY_CAP).asInteger()),
        }
        self._progress_replies = context.getProperty(self.TRIGGER_PROGRESS_REPLIES).asBoolean()

        self._limit_windows = dict(self._LIMIT_SUBWINDOWS)
        self._limit_windows['device'] = self._cooldown_seconds
        self._limit_windows['watchlist'] = context.getProperty(self.WATCHLIST_COOLDOWN_SECONDS).asFloat()
        self._limit_windows['clip'] = context.getProperty(self.CLIP_COOLDOWN_SECONDS).asFloat()
        self._limit_windows['gif'] = context.getProperty(self.GIF_COOLDOWN_SECONDS).asFloat()
        # (class, scope_key) -> last fire time, and one "already warned this window" flag
        # per trigger name so the warning itself can never become the spam.
        self._limits = {}
        self._limit_warned = {}
        # Rolling 24h history per capped trigger - a deque of fire times, not a
        # calendar-day counter, so the cap can't be re-armed in a burst at UTC
        # midnight. clip and gif each get their own.
        self._cap_history = {'clip': collections.deque(), 'gif': collections.deque()}
        # (trigger, target) -> {nick: [occurrence times]}. Keyed by nick as the state
        # shape says, but holding every occurrence rather than one timestamp: the rule
        # is 3 occurrences, and one person repeating themselves counts.
        self._votes = collections.OrderedDict()
        # "Who's on screen right now" - what a bare trigger is reacting to. Set on every
        # successful !load dispatch, cleared on every (re)connect.
        self._current_streamer = None

        self._trigger_registry = self._build_trigger_registry(self._watchlist_trigger)

    def _build_trigger_registry(self, watchlist_trigger):
        """Longest prefix first, so '<phrase> clip' and the fish+clapper form are both
        settled before their plain-watchlist prefixes get a look at the same message."""
        fish = self._FISH * 3
        word = self._normalize(watchlist_trigger)
        entries = [(fish + self._CLAPPER, 'clip'), (fish + self._PICTURE, 'gif'),
                   (fish + self._PLUS, 'roster_add'), (fish + self._MINUS, 'roster_remove'),
                   (fish, 'watchlist')]
        if word:
            entries.append((word + ' clip', 'clip'))
            entries.append((word + ' gif', 'gif'))
            entries.append((word, 'watchlist'))
        return sorted(entries, key=lambda entry: len(entry[0]), reverse=True)

    @classmethod
    def _normalize(cls, text):
        """The exact text every trigger is matched against. Strips Twitch's invisible
        TAG-SELECTOR and any variation selectors, NFKC-folds, collapses whitespace runs,
        strips and lowercases - so that two visually identical messages, one of them
        carrying the duplicate-filter dodge, normalize to the same string."""
        cleaned = text.replace(cls._TAG_SELECTOR, '')
        for selector in cls._VARIATION_SELECTORS:
            cleaned = cleaned.replace(selector, '')
        cleaned = unicodedata.normalize("NFKC", cleaned)
        return " ".join(cleaned.split()).lower()

    def _match_trigger(self, normalized):
        """Returns (trigger_name, remainder) or None. Prefix-anchored with startswith,
        never a substring search: 'haha tuna tuna tuna lol', or somebody quoting the
        bot's own help message back into chat, must not fire anything."""
        for prefix, name in self._trigger_registry:
            if not normalized.startswith(prefix):
                continue
            rest = normalized[len(prefix):]
            # A word-form prefix needs a real word boundary after it, or 'tuna tuna tuna
            # clipper' reads as a clip request for the streamer 'per'. Emoji prefixes end
            # on a non-alphanumeric, so a name butted straight against them still works.
            if rest and prefix[-1].isalnum() and not rest[0].isspace():
                continue
            return name, rest.strip()
        return None

    def _resolve_trigger_target(self, rest, is_privileged):
        """(target, allowed). Same resolution as !load: an explicit argument goes through
        _expand_streamer_token so the mod-only 'k:' short form keeps working, and a bare
        trigger falls back to whoever !load put on screen last. allowed=False means a
        non-mod used 'k:' - silently ignored, like every other mod-only short form."""
        if rest:
            token = rest.split()[0]
            expanded, was_short = self._expand_streamer_token(token)
            if was_short and not is_privileged:
                return None, False
            return expanded.lstrip('@').lower(), True
        return self._current_streamer, True

    @staticmethod
    def _display_login(target):
        return target[5:] if target.startswith("kick:") else target

    def _record_vote(self, trigger_name, target, nick, now):
        """Records one occurrence and returns the fresh count for (trigger, target).
        Prunes every expired occurrence across the whole table first, then LRU-evicts
        down to the key cap - both are needed, because expiry alone still lets a burst
        of distinct targets sit in memory for a full window."""
        window = self._vote_window_seconds
        for key in list(self._votes.keys()):
            occurrences = self._votes[key]
            for voter in list(occurrences.keys()):
                fresh = [ts for ts in occurrences[voter] if now - ts < window]
                if fresh:
                    occurrences[voter] = fresh
                else:
                    del occurrences[voter]
            if not occurrences:
                del self._votes[key]

        key = (trigger_name, target)
        occurrences = self._votes.get(key)
        if occurrences is None:
            occurrences = {}
            self._votes[key] = occurrences
        occurrences.setdefault(nick, []).append(now)
        self._votes.move_to_end(key)
        while len(self._votes) > self._VOTE_KEY_CAP:
            self._votes.popitem(last=False)
        return sum(len(times) for times in occurrences.values())

    def _check_limit(self, sock, channel, name, user=None, target=None, privileged=False):
        """No-op gate: every caller proceeds, nothing is ever blocked, and no cooldown
        warning ("Slow down - try again in Ns", "cooling down", "budget is spent") is
        ever sent. The whole rate-limit ladder was only ever slowing the operator down -
        nobody but Steven and trusted mods runs these commands, so there is nothing to
        throttle. Kept as a pass-through (rather than deleting the call sites) so the
        vote mechanic, the enable switches, and the flow config all stay untouched; the
        cooldown properties and the ledger/deque machinery below are now inert.

        Historically: !load/!matrix got a single global cooldown; each trigger had to
        clear a global + per-user + per-target window plus a rolling daily cap, with
        mods bypassing all of it (#174). That gating is now gone entirely."""
        return True

    def _trigger_help_message(self):
        """Shared by the on-join announcement and !commands. The clip trigger is only
        advertised while it's actually enabled."""
        fish = self._FISH * 3
        message = (f"Chat triggers (no ! needed): say \"{self._watchlist_trigger}\" or {fish} "
                   f"[streamer] {self._vote_count}x within {int(self._vote_window_seconds)}s to add them to the watchlist "
                   f"- leave the name off and it uses whoever's on screen now.")
        if self._clip_trigger_enabled:
            message += (f" Mods: {fish}{self._CLAPPER} (or \"{self._watchlist_trigger} clip\") "
                        f"[streamer] pulls a clip - one use, no vote.")
        if self._gif_trigger_enabled:
            message += (f" Mods: {fish}{self._PICTURE} (or \"{self._watchlist_trigger} gif\") "
                        f"[streamer] posts a reaction gif - one use, no vote.")
        message += (f" Mods: {fish}{self._PLUS} / {fish}{self._MINUS} <streamer> adds/removes "
                    f"them from the roster (k:<name> for Kick).")
        return message

    def _handle_trigger(self, sock, channel, trigger, nick, is_privileged):
        name, rest = trigger

        if name in ('roster_add', 'roster_remove'):
            # Mod-only and silent for everyone else, like clip/gif. No enable
            # switch and no rate limit: it only ever fires for a mod, and it
            # posts nothing to X - the backend decides what actually changes.
            if not is_privileged:
                return
            fish = self._FISH * 3
            if not rest:
                # No bare form. A clip can reasonably mean "whoever's on screen";
                # editing the roster has to name who.
                self._send_chat(sock, channel,
                                 f"Name a streamer with that - e.g. \"{fish}{self._PLUS} xqc\" "
                                 f"or \"{fish}{self._PLUS} k:roshtein\".")
                return
            target, allowed = self._resolve_trigger_target(rest, is_privileged)
            if not allowed or not target:
                return
            display = self._display_login(target)
            self._dispatch_trigger(name, target, nick, channel)
            if name == 'roster_add':
                self._send_chat(sock, channel, f"on it - adding {display} to the roster {self._PLUS}")
            else:
                self._send_chat(sock, channel, f"on it - removing {display} from the roster {self._MINUS}")
            return

        if name in ('clip', 'gif'):
            enabled = self._clip_trigger_enabled if name == 'clip' else self._gif_trigger_enabled
            if not enabled:
                if self.logger:
                    self.logger.info(f"{name.capitalize()} trigger from '{nick}' ignored: "
                                     f"{name.capitalize()} Trigger Enabled is false")
                return
            # Silent for a non-mod, exactly like the "!m"/"k:"/"s1" short forms.
            if not is_privileged:
                return

        target, allowed = self._resolve_trigger_target(rest, is_privileged)
        if not allowed:
            return
        if not target:
            if self._check_limit(sock, channel, 'notarget'):
                self._send_chat(sock, channel,
                                 f"Name a streamer with that - e.g. \"{self._watchlist_trigger} xqc\".")
            return

        display = self._display_login(target)

        if name in ('clip', 'gif'):
            # clip/gif are mod-only, so this is always a privileged caller: it skips
            # the cooldowns and clears only the rolling daily cap.
            if not self._check_limit(sock, channel, name, user=nick, target=target,
                                     privileged=is_privileged):
                return
            if name == 'clip':
                self._dispatch_trigger('clip_request', target, nick, channel)
                # Queued first, acked second: a clip job is 30-90s on the backend,
                # and this is the fast acknowledgement sitting in front of it.
                self._send_chat(sock, channel, f"on it - pulling a clip from {display} {self._CLAPPER}")
            else:
                self._dispatch_trigger('gif_request', target, nick, channel)
                self._send_chat(sock, channel, f"on it - cutting a gif from {display} {self._PICTURE}")
            return

        # A mod/broadcaster adds instantly - no vote, no cooldown. It's their channel;
        # making them say it three times and then wait out a window was the "gating
        # makes it impossible to drive the bot" complaint.
        if is_privileged:
            if not self._check_limit(sock, channel, 'watchlist', user=nick, target=target,
                                     privileged=True):
                return
            self._votes.pop((name, target), None)
            self._dispatch_trigger('watchlist_add', target, nick, channel)
            return

        count = self._record_vote(name, target, nick, now=time.time())
        if count < self._vote_count:
            # One progress reply, one short of firing - silent at every earlier count.
            # It names the target so back-to-back replies differ; Twitch drops a bot's
            # identical repeat inside roughly 30 seconds.
            if count == self._vote_count - 1 and self._progress_replies:
                self._send_chat(sock, channel,
                                 f"{count}/{self._vote_count} for {display} - one more!")
            return
        # Blocked votes are deliberately not cleared: leaving the tally above the
        # threshold keeps the next message from dropping back to the progress-reply
        # count and re-announcing itself once a window.
        if not self._check_limit(sock, channel, 'watchlist', user=nick, target=target):
            return
        self._votes.pop((name, target), None)
        self._dispatch_trigger('watchlist_add', target, nick, channel)

    def _dispatch_trigger(self, chat_action, target, nick, channel):
        """Enqueue and return - never call the backend from here. The IRC reader thread
        is the same thread that answers Twitch's PING, and a 30-90s clip job would blow
        through that tolerance: disconnect, reconnect, and another refresh token burned."""
        is_kick = target.startswith("kick:")
        self._queue.put({
            "command": "chat_trigger",
            "chat_action": chat_action,
            "streamer": target,
            "platform": "kick" if is_kick else "twitch",
            "login": self._display_login(target),
            "requested_by": nick,
            "channel": channel,
            "screen": "",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    def _format_watchlist_message(self):
        # cso-operator-app being briefly unreachable shouldn't take down the
        # whole IRC connection — same defensive posture as the IRC reconnect
        # backoff around this method's caller.
        try:
            req = urllib.request.Request(self._watchlist_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                logins = json.loads(resp.read().decode('utf-8'))["logins"]
            if not logins:
                return "Currently watching: nobody right now."
            return "Currently watching: " + ", ".join(logins)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to fetch streamer watchlist: {e}")
            return "Currently watching: (couldn't reach the watchlist right now)"

    def _is_streamer_live(self, streamer):
        """Fails open (returns True) on any lookup error - an infra hiccup on
        cso-operator-app's side shouldn't silently block a real load."""
        try:
            url = f"{self._live_check_url}?login={urllib.parse.quote(streamer, safe='')}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
            return bool(payload.get("live"))
        except Exception as e:
            if self.logger:
                self.logger.error(f"Live-check failed for '{streamer}', dispatching anyway: {e}")
            return True

    # Mod-only short aliases - each checked independently against the sender's
    # privilege, not tied to which command word (long or "!l") introduced them.
    _SCREEN_SHORT = {"s1": "screen1", "s2": "screen2", "s3": "screen3", "s4": "screen4"}

    def _is_privileged(self, tags):
        """True for the channel's broadcaster or a moderator, read off the
        twitch.tv/tags IRCv3 tags requested at connect. Twitch tags the
        broadcaster via the 'badges' field, not always via 'mod' - check both."""
        if tags.get('mod') == '1':
            return True
        badges = tags.get('badges', '')
        return 'broadcaster/' in badges or 'moderator/' in badges

    def _expand_screen_token(self, token):
        """('s1'-'s4') -> ('screen1'-'screen4', True). Anything else (including
        an already-canonical screenN or a bogus token) passes through unchanged
        with was_short=False - unrecognized tokens still fall through to
        RouteOnAttribute's own 'unmatched', same as before this change."""
        low = token.lower()
        if low in self._SCREEN_SHORT:
            return self._SCREEN_SHORT[low], True
        return token, False

    def _expand_streamer_token(self, token):
        """'k:<login>' -> ('kick:<login>', True); anything else unchanged."""
        if token.lower().startswith("k:"):
            return "kick:" + token[2:], True
        return token, False

    def _parse_tags(self, line):
        """Splits a leading '@key=val;key=val ' IRCv3 tag block off the front of
        a raw line, if present. Returns (tags_dict, remaining_line)."""
        if not line.startswith('@'):
            return {}, line
        tag_str, sep, rest = line.partition(' ')
        if not sep:
            return {}, line
        tags = {}
        for kv in tag_str[1:].split(';'):
            if '=' in kv:
                k, v = kv.split('=', 1)
                tags[k] = v
        return tags, rest

    def _handle_line(self, sock, line, channel):
        tags, line = self._parse_tags(line)

        if line.startswith("PING"):
            self._send(sock, line.replace("PING", "PONG", 1))
            return

        # PRIVMSG line shape: :nick!user@host PRIVMSG #channel :message text
        if "PRIVMSG" not in line:
            return

        prefix, sep, rest = line.partition(" PRIVMSG ")
        if not sep:
            return
        nick = prefix.split("!", 1)[0].lstrip(":")
        _, _, message = rest.partition(":")
        message = message.strip()
        is_privileged = self._is_privileged(tags)

        # A bare "!c" (nothing after it) is short for !commands. With an argument
        # ("!c <streamer>") it's the overlay-relay short form, handled below.
        if message.lower() in ("!commands", "!help", "!c"):
            self._send_chat(sock, channel,
                             f"Commands: {self._command_prefix} (or !l) <streamer> [screen1|screen2|screen3|screen4] - loads that stream on a screen "
                             f"(defaults to screen1) | {self._matrix_command} <screen1|screen2|screen3|screen4> - turns on the matrix screensaver "
                             f"(screen required, no default) | "
                             f"{self._watchlist_command} (or !w) - shows who's currently on the watchlist | "
                             f"{self._overlay_command} (or !c) <streamer|off|me|kick:slug> - (mods) relay that channel's chat to the overlay, off/me back to this chat")
            # Split for the same reason as the join announcement: one PRIVMSG caps at
            # 500 characters and the command list above already runs close to it.
            self._send_chat(sock, channel, self._trigger_help_message())
            return

        if message.lower() in (self._watchlist_command.lower(), "!w"):
            self._send_chat(sock, channel, self._format_watchlist_message())
            return

        # Triggers carry no '!' prefix, so they're matched before the command words and
        # can't collide with them.
        trigger = self._match_trigger(self._normalize(message))
        if trigger is not None:
            self._handle_trigger(sock, channel, trigger, nick, is_privileged)
            return

        tokens = message.split()
        cmd_word = tokens[0].lower() if tokens else ""

        if cmd_word in (self._matrix_command.lower(), "!m"):
            # Array-wide numbering, same as !load: screen1 -> Jetson, screen2 ->
            # GamingPC (WindowsDesktop), screen3/screen4 -> TunaStarlink's local
            # screen2/screen3 (see claude-screen.md). Unlike !load, there is no
            # default - the screen argument is required, so a bare "!matrix"/"!m"
            # or an unrecognized token doesn't match at all and is silently
            # ignored, same as an unrecognized !load screen falling through
            # unmatched. "!m" itself, and a short "s1"-"s4" screen argument, are
            # each independently mod/broadcaster-only - the long "!matrix" form
            # with a full "screenN" argument stays open to everyone, unchanged.
            if cmd_word == "!m" and not is_privileged:
                return
            if len(tokens) != 2:
                return
            arg_expanded, arg_was_short = self._expand_screen_token(tokens[1])
            if arg_was_short and not is_privileged:
                return
            arg = arg_expanded.lower()
            screen = {
                "screen1": "matrix-screen1",
                "screen2": "matrix-screen2",
                "screen3": "matrix-screen3",
                "screen4": "matrix-screen4",
            }.get(arg)
            if screen is None:
                return
            if not self._check_limit(sock, channel, 'device'):
                return
            # display_screen is the clean chat-facing label (TwitchChatReplyProcessor's
            # Matrix Message template uses this, not the internal routing sentinel above) -
            # always the expanded canonical form, whether the sender typed it short or long.
            display_screen = arg
            # No immediate ack here - TwitchChatReplyProcessor posts the one real
            # confirmation after the dispatch actually succeeds (was double-posting
            # before: this "loading" message plus its own "now active" reply).
            self._queue.put({
                "command": "matrix",
                "screen": screen,
                "display_screen": display_screen,
                "requested_by": nick,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            return

        # Overlay chat relay (#300/#306): "!chat <streamer|off|me>" (or its short
        # form "!c <streamer|off|me>", like !l/!m/!w) re-points @tunastarlink's
        # left-side chat column at another channel. Broadcaster/moderator-only - a
        # non-mod is silently ignored, same as the other mod-only commands. The
        # target is passed through verbatim; the overlay backend (POST
        # /api/overlay/relay, via the flow's RouteOnAttribute -> InvokeHTTP)
        # normalizes off/me/own -> own chat and resolves Twitch logins or
        # "kick:"/"k:" slugs (Kick relay is live, #306). No cooldown: mod-gated and
        # cheap (a socket target swap). A bare "!c" never reaches here - it's
        # handled above as the !commands short form.
        if cmd_word in (self._overlay_command.lower(), "!c"):
            if not is_privileged:
                return
            if len(tokens) < 2:
                # bare "!chat" with no target (bare "!c" already went to !commands)
                return
            target = tokens[1].lstrip('@').lower()
            self._queue.put({
                "command": "overlay_relay",
                "channel": target,
                "requested_by": nick,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            return

        if cmd_word not in (self._command_prefix.lower(), "!l"):
            return
        if len(tokens) < 2:
            return

        if not self._check_limit(sock, channel, 'device'):
            return

        streamer_expanded, streamer_was_short = self._expand_streamer_token(tokens[1])
        if streamer_was_short and not is_privileged:
            return
        streamer = streamer_expanded.lstrip('@').lower()

        if len(tokens) > 2:
            screen_expanded, screen_was_short = self._expand_screen_token(tokens[2])
            if screen_was_short and not is_privileged:
                return
            screen = screen_expanded.lower()
        else:
            screen = "screen1"

        if not self._is_streamer_live(streamer):
            display_name = streamer[5:] if streamer.startswith("kick:") else streamer
            self._send_chat(sock, channel, f"{display_name} isn't live right now.")
            return

        # "Who's on screen right now" for a bare chat trigger - set on the dispatch, not
        # on the parse, so a rejected or offline !load never becomes the trigger target.
        self._current_streamer = streamer
        self._queue.put({
            "command": "load",
            "streamer": streamer,
            "screen": screen,
            "requested_by": nick,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
