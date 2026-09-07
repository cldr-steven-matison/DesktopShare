# OnScreenAnnouncerProcessor.py
import json
import socket
import threading
import time

from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, ExpressionLanguageScope, StandardValidators


class OnScreenAnnouncerProcessor(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.1-SNAPSHOT'
        description = (
            'On each incoming FlowFile - one per successful !load dispatch, tapped off the '
            'TwitchChatBot InvokeHTTP "Original" relationships - JOINs the loaded streamer\'s own '
            'Twitch channel and PRIVMSGs a one-time "you are now on screen" announcement that names '
            'the screen number they went up on. The bot identity is the same watchlist bot account '
            '(@tunastreettest); this is a THIRD, independent persistent IRC connection, owned by a '
            'background reader thread (started in onScheduled, stopped in onStopped) that answers '
            'Twitch\'s PINGs and reconnects with backoff, exactly like WatchlistChatJoinerProcessor. '
            'A streamer is announced AT MOST ONCE, ever - the announced set is persisted to NiFi '
            'component state (Scope.LOCAL, key "announced"), so a repeat !load of the same streamer '
            'never re-posts, and the dedup survives a processor restart / bundle-version bump. '
            'Kick logins ("kick:<slug>") are skipped silently - they have no Twitch channel to post '
            'into. Does no polling, no fan-out and no timers of its own: the upstream flow decides '
            '*when* a FlowFile arrives (only on a real, live, dispatched !load). '
            'Refresh token is persisted to component state (key "refresh_token") and rotated exactly '
            'like WatchlistChatJoinerProcessor, on its own per-instance state so it never collides '
            'with the watchlist / top-streamer bots. '
            'Dry Run (default true) skips opening the real IRC connection entirely and logs what it '
            'would JOIN and post instead - but still records the streamer as announced, so a dry-run '
            'test does not leave it primed to double-post once flipped live.'
        )
        tags = ['twitch', 'irc', 'chat', 'streamers', 'on-screen', 'announcer', 'chat-bot']
        dependencies = []

    BOT_USERNAME = PropertyDescriptor(
        name="Bot Username",
        description="Twitch login name of the bot account (e.g. tunastreettest).",
        required=True,
        default_value="tunastreettest",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CLIENT_ID = PropertyDescriptor(
        name="Client ID",
        description="Twitch app client ID for the watchlist bot app (TunaStreetTestBot).",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CLIENT_SECRET = PropertyDescriptor(
        name="Client Secret",
        description="Twitch app client secret for the watchlist bot app. Bind to the "
                     "twitch-chat-bot-creds Parameter Context (#{twitch-chat2-client-secret}); "
                     "never a literal - a GET-then-PUT would write the '********' mask over it.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    REFRESH_TOKEN = PropertyDescriptor(
        name="Refresh Token",
        description="User refresh token for the bot account (chat:read+chat:edit scopes). This is a "
                     "SEED only: read on first start / whenever component state is empty, after which "
                     "the (possibly) rotated token is persisted to state and this property is ignored. "
                     "Bind to #{twitch-watchlist-bot-refresh-token}. To force a re-seed, paste a fresh "
                     "token and restart.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    ANNOUNCEMENT_MESSAGE = PropertyDescriptor(
        name="Announcement Message",
        description="Posted once, right after joining the loaded streamer's channel. "
                     "'{streamer}' is replaced with their login and '{screen}' with the screen "
                     "number they were loaded on (1-4).",
        required=True,
        default_value="\U0001F41F @{streamer} is now LIVE on screen {screen} of the TunaStreet "
                      "wall \U0001F3AC twitch.tv/tunastarlink",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    STREAMER_ATTRIBUTE = PropertyDescriptor(
        name="Streamer Attribute",
        description="FlowFile attribute holding the Twitch login that was loaded.",
        required=True,
        default_value="streamer",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    SCREEN_ATTRIBUTE = PropertyDescriptor(
        name="Screen Attribute",
        description="FlowFile attribute holding the screen the stream was loaded on "
                     "(e.g. 'screen1'..'screen4'). The trailing digit is what appears in the message.",
        required=True,
        default_value="screen",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    DRY_RUN = PropertyDescriptor(
        name="Dry Run",
        description="When true (default), never opens a real IRC connection - logs what would be "
                     "sent instead. Must be explicitly set to false to join/post for real.",
        required=True,
        default_value="true",
        validators=[StandardValidators.BOOLEAN_VALIDATOR],
    )

    # Component-state keys. NiFi scopes component state per processor instance, so this does not
    # collide with any other instance's token or dedup set.
    STATE_KEY_REFRESH_TOKEN = 'refresh_token'
    STATE_KEY_ANNOUNCED = 'announced'

    IRC_HOST = "irc.chat.twitch.tv"
    IRC_PORT = 6667
    CONNECT_WAIT_SECONDS = 20
    REJOIN_PACE_SECONDS = 0.5

    def __init__(self, **kwargs):
        # 'pass' is the safest initialization in many containerized environments -
        # real state is set up in onScheduled, which is guaranteed to run before transform().
        pass

    def getPropertyDescriptors(self):
        return [
            self.BOT_USERNAME, self.CLIENT_ID, self.CLIENT_SECRET, self.REFRESH_TOKEN,
            self.ANNOUNCEMENT_MESSAGE, self.STREAMER_ATTRIBUTE, self.SCREEN_ATTRIBUTE, self.DRY_RUN,
        ]

    def onScheduled(self, context):
        self._dry_run = context.getProperty(self.DRY_RUN).asBoolean()
        self._message_template = context.getProperty(self.ANNOUNCEMENT_MESSAGE).getValue()
        self._username = context.getProperty(self.BOT_USERNAME).getValue()
        self._client_id = context.getProperty(self.CLIENT_ID).getValue()
        self._client_secret = context.getProperty(self.CLIENT_SECRET).getValue()
        try:
            self._state_manager = context.getStateManager()
        except Exception as e:
            self._state_manager = None
            if self.logger:
                self.logger.warn(f"Component state unavailable; the rotated Twitch refresh token and "
                                 f"the announced-streamer dedup will not survive a restart: {e}")
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

        # Durable once-ever dedup set, loaded from component state.
        self._announced = self._read_announced_set()

        # The socket is owned by the reader thread; transform() only ever sends on it.
        self._lock = threading.Lock()
        self._sock = None
        self._connected = threading.Event()
        self._stop_event = threading.Event()
        self._last_connect_error = None
        # Announcer does not stay resident in channels - dedup is durable, so nothing needs
        # re-JOINing on a reconnect. Kept empty on purpose; _rejoin_channels is then a no-op.
        self._channels = set()
        self._thread = None
        if not self._dry_run:
            self._thread = threading.Thread(
                target=self._run_irc_loop,
                name=f"OnScreenAnnouncer-irc-{self._username}",
                daemon=True,
            )
            self._thread.start()

    def onStopped(self, context):
        self._stop_event.set()
        self._close_socket()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._flush_pending_token_write()

    def transform(self, context, flowfile):
        # Task thread: drain whatever the reader thread stashed (see _request_access_token).
        self._flush_pending_token_write()

        attributes = dict(flowfile.getAttributes())
        streamer_attr = context.getProperty(self.STREAMER_ATTRIBUTE).evaluateAttributeExpressions(flowfile).getValue()
        screen_attr = context.getProperty(self.SCREEN_ATTRIBUTE).evaluateAttributeExpressions(flowfile).getValue()
        raw_streamer = attributes.get(streamer_attr, '').strip()
        # Upstream already strips '@'/'#' and lowercases, but normalise here too so the durable
        # dedup set can never be fooled into re-announcing the same channel by a stray prefix/case.
        streamer = raw_streamer.lstrip('#@').lower()

        if not streamer:
            attributes['announce_error'] = f"No value found for attribute '{streamer_attr}'"
            return FlowFileTransformResult(relationship='failure', attributes=attributes)

        # Kick streamers have no Twitch channel to announce into - skip, don't fail, don't dedup.
        if streamer.startswith('kick:'):
            attributes['announce_result'] = 'skipped_kick'
            return FlowFileTransformResult(relationship='success', attributes=attributes)

        if streamer in self._announced:
            attributes['announce_result'] = 'already_announced'
            return FlowFileTransformResult(relationship='success', attributes=attributes)

        screen_num = self._screen_number(attributes.get(screen_attr, ''))
        message = self._message_template.replace('{streamer}', streamer).replace('{screen}', screen_num)
        attributes['announce_screen'] = screen_num

        if self._dry_run:
            if self.logger:
                self.logger.info(f"[dry run] would JOIN #{streamer} and announce: {message}")
            self._record_announced(streamer)
            attributes['dry_run'] = 'true'
            attributes['announce_result'] = 'announced'
            return FlowFileTransformResult(relationship='success', attributes=attributes)

        if not self._connected.wait(self.CONNECT_WAIT_SECONDS):
            reason = self._last_connect_error or "reader thread has not connected yet"
            if self.logger:
                self.logger.error(f"OnScreenAnnouncerProcessor cannot announce #{streamer}: IRC not connected ({reason})")
            attributes['announce_error'] = f"IRC not connected: {reason}"
            return FlowFileTransformResult(relationship='failure', attributes=attributes)

        try:
            self._send(f"JOIN #{streamer}")
            self._send(f"PRIVMSG #{streamer} :{message}")
            # Only record a streamer whose announcement actually went on the wire; a failed
            # FlowFile is retried by the flow, not swallowed into the dedup set.
            self._record_announced(streamer)
            attributes['dry_run'] = 'false'
            attributes['announce_result'] = 'announced'
            return FlowFileTransformResult(relationship='success', attributes=attributes)
        except Exception as e:
            if self.logger:
                self.logger.error(f"OnScreenAnnouncerProcessor failed to announce #{streamer}: {e}")
            self._connected.clear()
            self._close_socket()
            attributes['announce_error'] = str(e)
            return FlowFileTransformResult(relationship='failure', attributes=attributes)

    @staticmethod
    def _screen_number(screen_value):
        """'screen3' -> '3'; a bare '3' -> '3'; anything with no trailing digit -> the raw value."""
        s = (screen_value or '').strip()
        digits = ''.join(c for c in s if c.isdigit())
        return digits if digits else s

    # --- IRC connection handling: the reader thread ---

    def _run_irc_loop(self):
        backoff = 5
        while not self._stop_event.is_set():
            try:
                access_token = self._refresh_access_token()
                self._connect_and_listen(access_token)
                backoff = 5  # reset after a clean-ish disconnect
            except Exception as e:
                self._last_connect_error = f"{type(e).__name__}: {e}"
                if self.logger and not self._stop_event.is_set():
                    self.logger.error(f"Twitch IRC connection error [{type(e).__name__}]: {e}")
            finally:
                self._connected.clear()
                self._close_socket()
            if self._stop_event.wait(backoff):
                break
            backoff = min(backoff * 2, 60)

    def _connect_and_listen(self, access_token):
        sock = socket.create_connection((self.IRC_HOST, self.IRC_PORT), timeout=30)
        sock.settimeout(30)
        with self._lock:
            self._sock = sock
        self._login(access_token)
        buffer = b""
        welcomed = False
        while not self._stop_event.is_set():
            try:
                data = sock.recv(4096)
            except socket.timeout:
                if not welcomed:
                    raise ConnectionError("no welcome (001) from Twitch within 30s of login")
                continue
            except OSError:
                with self._lock:
                    dropped_locally = self._sock is None
                if dropped_locally:
                    raise ConnectionError("IRC socket dropped after a send failure; reconnecting")
                raise
            if not data:
                raise ConnectionError("Twitch IRC connection closed by server")
            buffer += data
            while b"\r\n" in buffer:
                raw_line, buffer = buffer.split(b"\r\n", 1)
                line = raw_line.decode('utf-8', errors='ignore')
                if line.startswith("PING"):
                    self._send(line.replace("PING", "PONG", 1))
                    continue
                if not welcomed:
                    if " 001 " in line:
                        welcomed = True
                        self._rejoin_channels()
                        self._connected.set()
                        if self.logger:
                            self.logger.info(f"Twitch IRC connected as {self._username.lower()}")
                    elif line.startswith(":tmi.twitch.tv NOTICE * :"):
                        raise ConnectionError(f"Twitch rejected the IRC login: {line.split(':', 2)[-1]}")
                    continue
                if line.startswith(":tmi.twitch.tv RECONNECT"):
                    raise ConnectionError("Twitch asked the client to RECONNECT")
                if " NOTICE " in line and self.logger:
                    self.logger.warn(f"Twitch IRC NOTICE: {line}")

    def _login(self, access_token):
        self._send(f"PASS oauth:{access_token}")
        self._send(f"NICK {self._username.lower()}")

    def _rejoin_channels(self):
        # No-op in practice: the announcer keeps _channels empty (durable dedup means nothing
        # needs re-JOINing). Kept for parity with the watchlist bot's reconnect path.
        for streamer in sorted(self._channels):
            if self._stop_event.is_set():
                return
            self._send(f"JOIN #{streamer}")
            time.sleep(self.REJOIN_PACE_SECONDS)

    def _send(self, message):
        with self._lock:
            if self._sock is None:
                raise ConnectionError("IRC socket is not connected")
            self._sock.sendall((message + "\r\n").encode('utf-8'))

    def _close_socket(self):
        with self._lock:
            sock, self._sock = self._sock, None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass

    # --- Twitch OAuth ---

    def _refresh_access_token(self):
        import urllib.error
        try:
            return self._request_access_token()
        except urllib.error.HTTPError as e:
            if e.code != 400 or self._token_source != 'state' or self._reseed_attempted:
                raise
            self._reseed_attempted = True
            if self.logger:
                self.logger.warn("Persisted Twitch refresh token was rejected (HTTP 400); "
                                 "clearing it from component state and retrying once from the property seed")
            self._pending_state_clear = True
            self._refresh_token = self._property_seed
            self._token_source = 'property'
            return self._request_access_token()

    def _request_access_token(self):
        import urllib.error
        import urllib.parse
        import urllib.request
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }).encode()
        req = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=body, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', errors='ignore')[:500]
            if self.logger:
                self.logger.error(f"Twitch token refresh rejected: HTTP {e.code} {detail}")
            raise
        if "access_token" not in payload:
            raise RuntimeError(f"Twitch token refresh returned no access_token: {json.dumps(payload)[:500]}")
        rotated = payload.get("refresh_token")
        if rotated:
            self._refresh_token = rotated
            self._token_source = 'state'
            self._pending_token_write = rotated
        elif self.logger:
            self.logger.warn("Twitch token refresh returned no refresh_token; keeping the previous one")
        return payload["access_token"]

    # --- Component state: rotated refresh token + durable announced-streamer dedup ---
    #
    # Both live under one Scope.LOCAL map. Every access is best-effort: a state failure must never
    # take down an announcement, since the in-memory copies still work for the life of the process.

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

    def _read_announced_set(self):
        if self._state_manager is None:
            return set()
        try:
            from nifiapi.componentstate import Scope
            raw = self._state_manager.getState(Scope.LOCAL).get(self.STATE_KEY_ANNOUNCED)
            if not raw:
                return set()
            return set(json.loads(raw))
        except Exception as e:
            if self.logger:
                self.logger.warn(f"Could not read the announced-streamer set from state; starting "
                                 f"empty (may re-announce a streamer already done in a prior run): {e}")
            return set()

    def _record_announced(self, streamer):
        """Add to the in-memory set and persist the whole set. Main/task thread only."""
        self._announced.add(streamer)
        if self._state_manager is None:
            return
        try:
            from nifiapi.componentstate import Scope
            state = self._state_manager.getState(Scope.LOCAL).toMap()
            state[self.STATE_KEY_ANNOUNCED] = json.dumps(sorted(self._announced))
            self._state_manager.setState(state, Scope.LOCAL)
        except Exception as e:
            if self.logger:
                self.logger.warn(f"Could not persist the announced-streamer set; #{streamer} is done "
                                 f"for this run but a restart may re-announce it: {e}")

    def _flush_pending_token_write(self):
        """Drain whatever the reader thread stashed. Main/task thread only."""
        if self._state_manager is None:
            return
        if self._pending_state_clear:
            self._pending_state_clear = False
            # Remove ONLY the dead token key - never clear(Scope.LOCAL), which would also wipe the
            # durable announced-streamer dedup set and prime a wave of re-announcements.
            try:
                from nifiapi.componentstate import Scope
                state = self._state_manager.getState(Scope.LOCAL).toMap()
                state.pop(self.STATE_KEY_REFRESH_TOKEN, None)
                self._state_manager.setState(state, Scope.LOCAL)
            except Exception as e:
                if self.logger:
                    self.logger.warn(f"Could not clear the rejected Twitch refresh token from state: {e}")
        token = self._pending_token_write
        if not token:
            return
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
