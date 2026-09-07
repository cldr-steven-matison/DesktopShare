# WatchlistChatJoinerProcessor.py
import socket
import threading
import time

from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, ExpressionLanguageScope, StandardValidators


class WatchlistChatJoinerProcessor(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.7-SNAPSHOT'
        description = (
            'Holds one persistent authenticated Twitch IRC connection and executes JOIN + PRIVMSG '
            '(the one-time greeting) for whichever streamer the incoming FlowFile names. The socket '
            'is owned by a background reader thread (started in onScheduled, stopped in onStopped) '
            'that answers Twitch\'s PINGs, reconnects with backoff when the server drops or rejects '
            'the connection, and silently re-JOINs every channel joined so far - the greeting is '
            'never repeated on a reconnect. Without that reader (0.0.6 and earlier) the socket was '
            'written to but never read, Twitch\'s PINGs went unanswered, and the next FlowFile after '
            'the server gave up on the connection failed with Broken pipe / Connection reset. '
            'Does no polling, no fan-out and no timers of its own - the upstream NiFi flow '
            '(GenerateFlowFile -> InvokeHTTP watchlist -> SplitJson -> live-check via Helix -> '
            'a DistributedMapCache dedup gate) is what decides *when* a FlowFile reaches this processor '
            'at all, exactly once per streamer per newly-detected join. '
            'Fully separate connection and refresh token from TwitchChatListenerProcessor - never '
            'shares state with it. Twitch rotates the refresh token on every use, so the rotated '
            'value is persisted to NiFi component state (Scope.LOCAL, key "refresh_token") and read '
            'back on the next onScheduled - a restart no longer needs a manual device-code re-auth. '
            'State is per processor instance, so two instances of this class (WatchlistChatJoiner and '
            'TopStreamerJoiner) keep separate tokens for their separate Twitch apps. '
            'Dry Run (default true) skips opening the real IRC connection '
            'entirely and logs what would be sent instead.'
        )
        tags = ['twitch', 'irc', 'chat', 'streamers', 'watchlist', 'chat-bot']
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
        description="Twitch app client ID for the separate TunaStreetTestBot app "
                     "(not the app TwitchChatListenerProcessor uses).",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CLIENT_SECRET = PropertyDescriptor(
        name="Client Secret",
        description="Twitch app client secret for the separate TunaStreetTestBot app.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    REFRESH_TOKEN = PropertyDescriptor(
        name="Refresh Token",
        description="Independent user refresh token for the bot account (chat:read+chat:edit scopes). "
                     "Do NOT reuse TwitchChatListenerProcessor's refresh token - Twitch rotates it on "
                     "every use and two processors refreshing from the same seed will race each other. "
                     "This is a SEED only: it is read on the first start and whenever component state is "
                     "empty, after which the rotated token is persisted to state and this property is "
                     "ignored. To force a re-seed, paste a freshly minted token here (or in the Parameter "
                     "Context) and restart - a dead stored token is dropped automatically on HTTP 400.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    GREETING_MESSAGE = PropertyDescriptor(
        name="Greeting Message",
        description="Posted once, right after joining a streamer's channel.",
        required=True,
        default_value="\U0001F41F I am Tuna \U0001F44B You are on my WatchList \U0001F3AC",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    STREAMER_ATTRIBUTE = PropertyDescriptor(
        name="Streamer Attribute",
        description="FlowFile attribute holding the Twitch login to join.",
        required=True,
        default_value="streamer",
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

    # Component-state key holding the rotated refresh token. NiFi scopes component state per
    # processor instance, so the two instances of this class do not collide.
    STATE_KEY_REFRESH_TOKEN = 'refresh_token'

    IRC_HOST = "irc.chat.twitch.tv"
    IRC_PORT = 6667
    # How long transform() waits for the reader thread to have a live, welcomed connection
    # before giving up on that FlowFile. Covers the token refresh + connect + 001 on a fresh
    # start (~1-2s); a FlowFile arriving mid-backoff after a real failure fails with that
    # failure's message rather than a bare "not connected".
    CONNECT_WAIT_SECONDS = 20
    # Twitch's JOIN limit is 20 per 10s per user; re-joining after a reconnect is paced under it.
    REJOIN_PACE_SECONDS = 0.5

    def __init__(self, **kwargs):
        # 'pass' is the safest initialization in many containerized environments —
        # real state is set up in onScheduled, which is guaranteed to run before transform().
        pass

    def getPropertyDescriptors(self):
        return [
            self.BOT_USERNAME, self.CLIENT_ID, self.CLIENT_SECRET, self.REFRESH_TOKEN,
            self.GREETING_MESSAGE, self.STREAMER_ATTRIBUTE, self.DRY_RUN,
        ]

    def onScheduled(self, context):
        self._dry_run = context.getProperty(self.DRY_RUN).asBoolean()
        self._greeting = context.getProperty(self.GREETING_MESSAGE).getValue()
        self._username = context.getProperty(self.BOT_USERNAME).getValue()
        self._client_id = context.getProperty(self.CLIENT_ID).getValue()
        self._client_secret = context.getProperty(self.CLIENT_SECRET).getValue()
        # The property is a seed, not the token in ongoing use: Twitch rotates the refresh
        # token on every use, so the live value lives in component state and the property is
        # only consulted when state is empty (first ever start, or after a deliberate re-seed).
        # Its own independent seed - never TwitchChatListenerProcessor's twitch-bot-refresh-token.
        # Guarded: a NiFi build without the state binding must degrade to the old
        # property-seed behaviour, not fail to start the processor at all.
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

        # The socket is owned by the reader thread; transform() only ever sends on it.
        # _lock guards _sock and every sendall - transform's JOIN/PRIVMSG and the reader's
        # PONG/re-JOIN interleave on one connection.
        self._lock = threading.Lock()
        self._sock = None
        self._connected = threading.Event()
        self._stop_event = threading.Event()
        self._last_connect_error = None
        # Channels the bot is supposed to be in - re-JOINed (silently) on every reconnect.
        self._channels = set()
        # Already-greeted-this-session dedup, belt-and-suspenders alongside the upstream
        # DistributedMapCache gate - a restart of this processor alone (bundle-version
        # switch, etc.) shouldn't cause a duplicate JOIN+greet within the same session.
        self._joined = set()
        self._thread = None
        if not self._dry_run:
            self._thread = threading.Thread(
                target=self._run_irc_loop,
                name=f"WatchlistChatJoiner-irc-{self._username}",
                daemon=True,
            )
            self._thread.start()

    def onStopped(self, context):
        self._stop_event.set()
        # Closing the socket is what unblocks the reader's recv(); the join below is then
        # bounded by that, not by the 30s recv timeout.
        self._close_socket()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        # Join first, then flush: the thread can rotate the token one last time on its way
        # out, and a clean stop is exactly the case where losing that rotation would force
        # the manual re-auth this whole mechanism exists to remove.
        self._flush_pending_token_write()

    def transform(self, context, flowfile):
        # Task thread: drain whatever the reader thread stashed (see _request_access_token).
        self._flush_pending_token_write()

        attributes = dict(flowfile.getAttributes())
        streamer_attr = context.getProperty(self.STREAMER_ATTRIBUTE).evaluateAttributeExpressions(flowfile).getValue()
        streamer = attributes.get(streamer_attr, '').strip().lstrip('#').lower()

        if not streamer:
            attributes['join_error'] = f"No value found for attribute '{streamer_attr}'"
            return FlowFileTransformResult(relationship='failure', attributes=attributes)

        if streamer in self._joined:
            attributes['join_result'] = 'already_joined_this_session'
            return FlowFileTransformResult(relationship='success', attributes=attributes)

        if self._dry_run:
            if self.logger:
                self.logger.info(f"[dry run] would JOIN #{streamer} and greet: {self._greeting}")
            self._joined.add(streamer)
            attributes['dry_run'] = 'true'
            return FlowFileTransformResult(relationship='success', attributes=attributes)

        if not self._connected.wait(self.CONNECT_WAIT_SECONDS):
            reason = self._last_connect_error or "reader thread has not connected yet"
            if self.logger:
                self.logger.error(f"WatchlistChatJoinerProcessor cannot join #{streamer}: IRC not connected ({reason})")
            attributes['join_error'] = f"IRC not connected: {reason}"
            return FlowFileTransformResult(relationship='failure', attributes=attributes)

        try:
            self._send(f"JOIN #{streamer}")
            self._send(f"PRIVMSG #{streamer} :{self._greeting}")
            # Only a join that actually went on the wire is kept alive across reconnects;
            # a failed FlowFile is retried by the flow, not remembered here.
            self._channels.add(streamer)
            self._joined.add(streamer)
            attributes['dry_run'] = 'false'
            attributes['join_result'] = 'joined'
            return FlowFileTransformResult(relationship='success', attributes=attributes)
        except Exception as e:
            if self.logger:
                self.logger.error(f"WatchlistChatJoinerProcessor failed to join #{streamer}: {e}")
            # A send error means the socket is dead: drop it so the reader thread's recv()
            # fails over into its reconnect path instead of waiting for the server to say so.
            self._connected.clear()
            self._close_socket()
            attributes['join_error'] = str(e)
            return FlowFileTransformResult(relationship='failure', attributes=attributes)

    # --- IRC connection handling: the reader thread ---

    def _run_irc_loop(self):
        backoff = 5
        while not self._stop_event.is_set():
            try:
                access_token = self._refresh_access_token()
                self._connect_and_listen(access_token)
                backoff = 5  # reset after a clean-ish disconnect
            except Exception as e:
                # The exception type is the whole diagnosis here: HTTPError/RuntimeError
                # means auth (a bad deploy), socket/ConnectionError means the network or
                # Twitch closing/rejecting the session (its NOTICE text is in the message).
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
        # Bytes, not str: split complete lines off the raw buffer and decode each one whole,
        # so a multi-byte character straddling a recv boundary can't be dropped.
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
                # transform() closes the socket under us when a send fails; say that rather
                # than surfacing the resulting EBADF as if it were a bug.
                with self._lock:
                    dropped_locally = self._sock is None
                if dropped_locally:
                    raise ConnectionError("IRC socket dropped after a send failure; reconnecting")
                raise
            except OSError as e:
                # transform() closes the socket under us when a send fails; say that rather
                # than surfacing the resulting EBADF as if it were a bug.
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
                            self.logger.info(f"Twitch IRC connected as {self._username.lower()}; "
                                             f"re-joined {len(self._channels)} channel(s)")
                    elif line.startswith(":tmi.twitch.tv NOTICE * :"):
                        # Pre-welcome NOTICE is a rejected login ("Login authentication failed",
                        # "Improperly formatted auth"). 0.0.6 drained and discarded this line,
                        # which is why a bad token looked like a network reset.
                        raise ConnectionError(f"Twitch rejected the IRC login: {line.split(':', 2)[-1]}")
                    continue
                if line.startswith(":tmi.twitch.tv RECONNECT"):
                    raise ConnectionError("Twitch asked the client to RECONNECT")
                if " NOTICE " in line and self.logger:
                    # Post-welcome NOTICEs are the join-side signals worth seeing: msg_banned,
                    # msg_channel_suspended, rate limits.
                    self.logger.warn(f"Twitch IRC NOTICE: {line}")

    def _login(self, access_token):
        self._send(f"PASS oauth:{access_token}")
        self._send(f"NICK {self._username.lower()}")

    def _rejoin_channels(self):
        # Silent: the greeting is a once-per-session thing, and reconnects are frequent
        # enough that repeating it would read as spam in every channel the bot sits in.
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
        # shutdown() is what actually interrupts a recv() blocked on another thread.
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
            # Stashed, not cleared inline: this runs on the reader thread (see below).
            self._pending_state_clear = True
            self._refresh_token = self._property_seed
            self._token_source = 'property'
            return self._request_access_token()

    def _request_access_token(self):
        import json
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
            # Without this, the reconnect loop reports a dead token identically to a network
            # blip, and a botched deploy looks exactly like Twitch being unreachable.
            # Log Twitch's own body. Same handling as TwitchChatListenerProcessor.
            detail = e.read().decode('utf-8', errors='ignore')[:500]
            if self.logger:
                self.logger.error(f"Twitch token refresh rejected: HTTP {e.code} {detail}")
            raise
        if "access_token" not in payload:
            raise RuntimeError(f"Twitch token refresh returned no access_token: {json.dumps(payload)[:500]}")
        # Twitch rotates the refresh token on every use - the old one is now invalid. It has
        # been observed absent on some responses; keeping the previous value is strictly better
        # than a KeyError that reads as a connection failure.
        rotated = payload.get("refresh_token")
        if rotated:
            self._refresh_token = rotated
            self._token_source = 'state'
            # Stashed, not written: this runs on the daemon reader thread and the state manager
            # is a py4j bridge into the JVM. transform()/onStopped flush it from a NiFi task
            # thread - the same arrangement as TwitchChatListenerProcessor. Worst case on a
            # crash between here and the flush is one lost rotation.
            self._pending_token_write = rotated
        elif self.logger:
            self.logger.warn("Twitch token refresh returned no refresh_token; keeping the previous one")
        return payload["access_token"]

    # --- Component state: the rotated refresh token ---
    #
    # Imported lazily rather than at module scope: nifiapi.componentstate resolves
    # Scope.LOCAL/CLUSTER through the py4j JVM bridge at import time.
    # State is not encrypted the way a sensitive property is. Every one of these is
    # best-effort: a state failure must never take down a join, since the in-memory token
    # still works for the life of the process.

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
        """Drain whatever the reader thread stashed. Main/task thread only."""
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
        # would retry on every transform() call.
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
