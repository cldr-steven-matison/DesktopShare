# KickOnScreenAnnouncerProcessor.py
import json
import time

from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, ExpressionLanguageScope, StandardValidators


class KickOnScreenAnnouncerProcessor(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.1-SNAPSHOT'
        description = (
            'Kick twin of OnScreenAnnouncerProcessor (#307). On each incoming FlowFile - one per '
            'successful !load dispatch, tapped off TwitchChatBot\'s LoadSuccessOutput - posts a '
            'one-time "you are now on screen" announcement into the loaded streamer\'s own KICK '
            'channel via Kick\'s public API (POST /public/v1/chat, type "user"), as the bot account '
            '(@tunastreettest on Kick). Only "kick:<slug>" logins are handled; Twitch logins are '
            'skipped silently (the Twitch announcer owns those). No IRC, no threads, no timers: '
            'every FlowFile is one lookup + one POST. '
            'A streamer is announced AT MOST ONCE, ever - the announced set is persisted to '
            'component state (Scope.LOCAL, key "announced") so a repeat !load never re-posts and the '
            'dedup survives a restart / bundle bump. '
            'Two tokens: the bot\'s USER token (scope chat:write) comes from the refresh-token grant '
            '- Kick ROTATES the refresh token on every refresh, so the rotated one is persisted to '
            'component state (key "refresh_token") immediately and the Refresh Token property is '
            'only a seed; the slug -> broadcaster_user_id lookup uses an APP token '
            '(client_credentials, same app) because the user token lacks channel:read. '
            'Dry Run (default true) does the lookup but never POSTs - logs what it would send - and '
            'still records the streamer as announced, so a dry-run test cannot double-post once live.'
        )
        tags = ['kick', 'chat', 'streamers', 'on-screen', 'announcer', 'chat-bot']
        dependencies = []

    CLIENT_ID = PropertyDescriptor(
        name="Client ID",
        description="Kick app client ID (the RW app that is allowed the chat:write scope).",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CLIENT_SECRET = PropertyDescriptor(
        name="Client Secret",
        description="Kick app client secret. Bind to the kick-chat-bot-creds Parameter Context "
                     "(#{kick-rw-client-secret}); never a literal - a GET-then-PUT would write the "
                     "'********' mask over it.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    REFRESH_TOKEN = PropertyDescriptor(
        name="Refresh Token",
        description="User refresh token for the bot's Kick account (scope chat:write). A SEED only: "
                     "read on first start / whenever component state is empty; Kick rotates it on every "
                     "refresh and the rotated token is persisted to state, after which this property is "
                     "ignored. Bind to #{kick-bot-refresh-token}. To force a re-seed, paste a fresh "
                     "token (files/kick-bot-oauth.py) and restart.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    ANNOUNCEMENT_MESSAGE = PropertyDescriptor(
        name="Announcement Message",
        description="Posted once into the loaded streamer's Kick channel. '{streamer}' is replaced "
                     "with their Kick slug and '{screen}' with the screen number (1-4). Kick caps a "
                     "message at 500 characters.",
        required=True,
        default_value="\U0001F41F @{streamer} is now LIVE on screen {screen} of the TunaStreet "
                      "wall \U0001F3AC",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    STREAMER_ATTRIBUTE = PropertyDescriptor(
        name="Streamer Attribute",
        description="FlowFile attribute holding the loaded login ('kick:<slug>' for Kick).",
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
        description="When true (default), resolves the channel but never POSTs - logs what would be "
                     "sent instead. Must be explicitly set to false to post for real.",
        required=True,
        default_value="true",
        validators=[StandardValidators.BOOLEAN_VALIDATOR],
    )

    STATE_KEY_REFRESH_TOKEN = 'refresh_token'
    STATE_KEY_ANNOUNCED = 'announced'

    TOKEN_URL = "https://id.kick.com/oauth/token"
    API_BASE = "https://api.kick.com/public/v1"
    MAX_MESSAGE_CHARS = 500
    HTTP_TIMEOUT = 15
    # id.kick.com / api.kick.com sit behind Cloudflare bot protection that 403s a bare
    # library User-Agent (streamer-kick-bot.md §1); a browser-like UA gets through.
    HEADERS = {
        "Accept": "application/json",
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
        "Referer": "https://kick.com/",
    }

    def __init__(self, **kwargs):
        pass

    def getPropertyDescriptors(self):
        return [
            self.CLIENT_ID, self.CLIENT_SECRET, self.REFRESH_TOKEN,
            self.ANNOUNCEMENT_MESSAGE, self.STREAMER_ATTRIBUTE, self.SCREEN_ATTRIBUTE, self.DRY_RUN,
        ]

    def onScheduled(self, context):
        self._dry_run = context.getProperty(self.DRY_RUN).asBoolean()
        self._message_template = context.getProperty(self.ANNOUNCEMENT_MESSAGE).getValue()
        self._client_id = context.getProperty(self.CLIENT_ID).getValue()
        self._client_secret = context.getProperty(self.CLIENT_SECRET).getValue()
        try:
            self._state_manager = context.getStateManager()
        except Exception as e:
            self._state_manager = None
            if self.logger:
                self.logger.warn(f"Component state unavailable; the rotated Kick refresh token and "
                                 f"the announced-streamer dedup will not survive a restart: {e}")
        self._property_seed = context.getProperty(self.REFRESH_TOKEN).getValue()
        self._reseed_attempted = False
        stored = self._read_stored_refresh_token()
        if stored:
            self._refresh_token = stored
            self._token_source = 'state'
        else:
            self._refresh_token = self._property_seed
            self._token_source = 'property'
        if self.logger:
            self.logger.info(f"Kick refresh token seeded from {self._token_source}")

        # In-memory token caches (refreshed on expiry or on a 401).
        self._user_token = None
        self._user_token_expiry = 0.0
        self._app_token = None
        self._app_token_expiry = 0.0
        self._broadcaster_ids = {}

        self._announced = self._read_announced_set()

    def onStopped(self, context):
        pass

    def transform(self, context, flowfile):
        attributes = dict(flowfile.getAttributes())
        streamer_attr = context.getProperty(self.STREAMER_ATTRIBUTE).evaluateAttributeExpressions(flowfile).getValue()
        screen_attr = context.getProperty(self.SCREEN_ATTRIBUTE).evaluateAttributeExpressions(flowfile).getValue()
        raw_streamer = attributes.get(streamer_attr, '').strip()
        streamer = raw_streamer.lstrip('#@').lower()

        if not streamer:
            attributes['announce_error'] = f"No value found for attribute '{streamer_attr}'"
            return FlowFileTransformResult(relationship='failure', attributes=attributes)

        # Twitch logins belong to OnScreenAnnouncerProcessor - skip, don't fail, don't dedup.
        if not streamer.startswith('kick:'):
            attributes['announce_result'] = 'skipped_twitch'
            return FlowFileTransformResult(relationship='success', attributes=attributes)
        slug = streamer[len('kick:'):].strip().lstrip('@')
        if not slug:
            attributes['announce_error'] = f"Empty Kick slug in '{raw_streamer}'"
            return FlowFileTransformResult(relationship='failure', attributes=attributes)

        if slug in self._announced:
            attributes['announce_result'] = 'already_announced'
            return FlowFileTransformResult(relationship='success', attributes=attributes)

        screen_num = self._screen_number(attributes.get(screen_attr, ''))
        message = (self._message_template.replace('{streamer}', slug)
                   .replace('{screen}', screen_num))[:self.MAX_MESSAGE_CHARS]
        attributes['announce_screen'] = screen_num

        try:
            broadcaster_id = self._broadcaster_user_id(slug)
        except Exception as e:
            if self.logger:
                self.logger.error(f"KickOnScreenAnnouncerProcessor cannot resolve kick:{slug}: {e}")
            attributes['announce_error'] = f"channel lookup failed: {e}"
            return FlowFileTransformResult(relationship='failure', attributes=attributes)
        attributes['kick_broadcaster_user_id'] = str(broadcaster_id)

        if self._dry_run:
            if self.logger:
                self.logger.info(f"[dry run] would post to kick:{slug} ({broadcaster_id}): {message}")
            self._record_announced(slug)
            attributes['dry_run'] = 'true'
            attributes['announce_result'] = 'announced'
            return FlowFileTransformResult(relationship='success', attributes=attributes)

        try:
            message_id = self._post_chat(broadcaster_id, message)
            # Only record a streamer whose announcement actually went out; a failed FlowFile is
            # retried by the flow, not swallowed into the dedup set.
            self._record_announced(slug)
            attributes['dry_run'] = 'false'
            attributes['announce_result'] = 'announced'
            attributes['kick_message_id'] = message_id or ''
            return FlowFileTransformResult(relationship='success', attributes=attributes)
        except Exception as e:
            if self.logger:
                self.logger.error(f"KickOnScreenAnnouncerProcessor failed to announce kick:{slug}: {e}")
            attributes['announce_error'] = str(e)
            return FlowFileTransformResult(relationship='failure', attributes=attributes)

    @staticmethod
    def _screen_number(screen_value):
        """'screen3' -> '3'; a bare '3' -> '3'; anything with no trailing digit -> the raw value."""
        s = (screen_value or '').strip()
        digits = ''.join(c for c in s if c.isdigit())
        return digits if digits else s

    # --- Kick HTTP ---

    def _http(self, method, url, headers=None, data=None):
        """One request; returns (status, parsed JSON or text). Raises only on transport errors."""
        import urllib.error
        import urllib.request
        hdrs = dict(self.HEADERS)
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
                status = resp.status
        except urllib.error.HTTPError as e:
            raw = e.read().decode('utf-8', errors='ignore')
            status = e.code
        try:
            return status, json.loads(raw) if raw else {}
        except ValueError:
            return status, raw[:500]

    def _post_chat(self, broadcaster_id, message):
        """POST the announcement as the bot user; one token refresh + retry on 401."""
        body = json.dumps({"type": "user", "broadcaster_user_id": int(broadcaster_id),
                           "content": message}).encode('utf-8')
        for attempt in (1, 2):
            token = self._user_access_token(force=(attempt == 2))
            status, payload = self._http("POST", f"{self.API_BASE}/chat",
                                         headers={"Authorization": f"Bearer {token}",
                                                  "Content-Type": "application/json"},
                                         data=body)
            if status == 200 and isinstance(payload, dict) and payload.get("data", {}).get("is_sent"):
                return payload["data"].get("message_id")
            if status == 401 and attempt == 1:
                if self.logger:
                    self.logger.warn("Kick chat POST got 401; refreshing the user token and retrying once")
                continue
            raise RuntimeError(f"Kick chat POST failed: HTTP {status} {json.dumps(payload)[:300]}")
        raise RuntimeError("Kick chat POST failed after a token refresh")

    def _broadcaster_user_id(self, slug):
        cached = self._broadcaster_ids.get(slug)
        if cached:
            return cached
        for attempt in (1, 2):
            token = self._app_access_token(force=(attempt == 2))
            status, payload = self._http("GET", f"{self.API_BASE}/channels?slug={slug}",
                                         headers={"Authorization": f"Bearer {token}"})
            if status == 200 and isinstance(payload, dict):
                for ch in payload.get("data", []) or []:
                    if ch.get("broadcaster_user_id"):
                        self._broadcaster_ids[slug] = int(ch["broadcaster_user_id"])
                        return self._broadcaster_ids[slug]
                raise RuntimeError(f"Kick has no channel for slug '{slug}'")
            if status == 401 and attempt == 1:
                continue
            raise RuntimeError(f"Kick channel lookup failed: HTTP {status} {json.dumps(payload)[:300]}")
        raise RuntimeError("Kick channel lookup failed after a token refresh")

    # --- Tokens ---

    def _app_access_token(self, force=False):
        """client_credentials token for the read-only lookups (60-day tokens; cached)."""
        import urllib.parse
        if self._app_token and not force and time.time() < self._app_token_expiry - 60:
            return self._app_token
        body = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self._client_id, "client_secret": self._client_secret,
        }).encode()
        status, payload = self._http("POST", self.TOKEN_URL,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"},
                                     data=body)
        if status != 200 or not isinstance(payload, dict) or "access_token" not in payload:
            raise RuntimeError(f"Kick app token request failed: HTTP {status} {json.dumps(payload)[:300]}")
        self._app_token = payload["access_token"]
        self._app_token_expiry = time.time() + float(payload.get("expires_in", 3600))
        return self._app_token

    def _user_access_token(self, force=False):
        """The bot's user token via the refresh grant; persists the ROTATED refresh token at once."""
        if self._user_token and not force and time.time() < self._user_token_expiry - 60:
            return self._user_token
        try:
            return self._request_user_token()
        except RuntimeError as e:
            rejected = ('HTTP 400' in str(e) or 'HTTP 401' in str(e))
            if not rejected or self._token_source != 'state' or self._reseed_attempted:
                raise
            self._reseed_attempted = True
            if self.logger:
                self.logger.warn("Persisted Kick refresh token was rejected; clearing it from component "
                                 "state and retrying once from the property seed")
            self._clear_stored_refresh_token()
            self._refresh_token = self._property_seed
            self._token_source = 'property'
            return self._request_user_token()

    def _request_user_token(self):
        import urllib.parse
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token", "refresh_token": self._refresh_token,
            "client_id": self._client_id, "client_secret": self._client_secret,
        }).encode()
        status, payload = self._http("POST", self.TOKEN_URL,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"},
                                     data=body)
        if status != 200 or not isinstance(payload, dict) or "access_token" not in payload:
            raise RuntimeError(f"Kick user token refresh failed: HTTP {status} {json.dumps(payload)[:300]}")
        rotated = payload.get("refresh_token")
        if rotated and rotated != self._refresh_token:
            self._refresh_token = rotated
            self._token_source = 'state'
            self._store_refresh_token(rotated)
        elif not rotated and self.logger:
            self.logger.warn("Kick token refresh returned no refresh_token; keeping the previous one")
        self._user_token = payload["access_token"]
        self._user_token_expiry = time.time() + float(payload.get("expires_in", 7200))
        return self._user_token

    # --- Component state: rotated refresh token + durable announced-streamer dedup ---
    # Both live under one Scope.LOCAL map; every access is best-effort and never clears the map.

    def _read_stored_refresh_token(self):
        if self._state_manager is None:
            return None
        try:
            from nifiapi.componentstate import Scope
            return self._state_manager.getState(Scope.LOCAL).get(self.STATE_KEY_REFRESH_TOKEN)
        except Exception as e:
            if self.logger:
                self.logger.warn(f"Could not read the persisted Kick refresh token from state, "
                                 f"falling back to the property seed: {e}")
            return None

    def _store_refresh_token(self, token):
        if self._state_manager is None:
            return
        try:
            from nifiapi.componentstate import Scope
            state = self._state_manager.getState(Scope.LOCAL).toMap()
            state[self.STATE_KEY_REFRESH_TOKEN] = token
            self._state_manager.setState(state, Scope.LOCAL)
        except Exception as e:
            if self.logger:
                self.logger.warn(f"Could not persist the rotated Kick refresh token; this run is fine "
                                 f"but the next restart will need a re-seed: {e}")

    def _clear_stored_refresh_token(self):
        if self._state_manager is None:
            return
        try:
            from nifiapi.componentstate import Scope
            state = self._state_manager.getState(Scope.LOCAL).toMap()
            state.pop(self.STATE_KEY_REFRESH_TOKEN, None)   # only this key - never the dedup set
            self._state_manager.setState(state, Scope.LOCAL)
        except Exception as e:
            if self.logger:
                self.logger.warn(f"Could not clear the rejected Kick refresh token from state: {e}")

    def _read_announced_set(self):
        if self._state_manager is None:
            return set()
        try:
            from nifiapi.componentstate import Scope
            raw = self._state_manager.getState(Scope.LOCAL).get(self.STATE_KEY_ANNOUNCED)
            return set(json.loads(raw)) if raw else set()
        except Exception as e:
            if self.logger:
                self.logger.warn(f"Could not read the announced-streamer set from state; starting "
                                 f"empty (may re-announce a streamer already done in a prior run): {e}")
            return set()

    def _record_announced(self, slug):
        self._announced.add(slug)
        if self._state_manager is None:
            return
        try:
            from nifiapi.componentstate import Scope
            state = self._state_manager.getState(Scope.LOCAL).toMap()
            state[self.STATE_KEY_ANNOUNCED] = json.dumps(sorted(self._announced))
            self._state_manager.setState(state, Scope.LOCAL)
        except Exception as e:
            if self.logger:
                self.logger.warn(f"Could not persist the announced-streamer set; kick:{slug} is done "
                                 f"for this run but a restart may re-announce it: {e}")
