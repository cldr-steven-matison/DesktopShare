# TwitchChatReplyProcessor.py
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, ExpressionLanguageScope, StandardValidators


class TwitchChatReplyProcessor(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.4-SNAPSHOT'
        description = (
            'Posts a one-off Twitch chat confirmation via the Helix "Send Chat Message" REST API '
            '(POST /helix/chat/messages) once a dispatch to an edge device has actually succeeded — '
            'wired downstream of InvokeHTTP\'s "Original" relationship in TwitchChatBot, not at parse '
            'time. Deliberately does NOT use TwitchChatListenerProcessor\'s user refresh token (that '
            'grant rotates on every use and is already owned by the listener\'s IRC reconnect loop — a '
            'second independent refresh from the same seed would race it and can invalidate whichever '
            'one loses). Instead mints a stateless App Access Token via the Client Credentials grant '
            '(Client ID/Secret only, never rotates) and resolves broadcaster/sender IDs once via Helix '
            '"Get Users", caching both in memory for the life of the processor. Message text comes '
            'from a "chat_reply_text" flowfile attribute when one is present - posted verbatim, no '
            'template and no substitution, which is how the backend answers a chat_trigger (watchlist '
            'add / clip request) in its own words. With no such attribute it falls back to the original '
            'command-keyed templates, so every pre-existing !load and !matrix reply behaves exactly as '
            'before. Dry Run property for safe testing.'
        )
        tags = ['twitch', 'helix', 'chat', 'streamers', 'chat-bot']
        dependencies = []

    SENDER_LOGIN = PropertyDescriptor(
        name="Sender Login",
        description="Twitch login of the bot account sending the confirmation (e.g. tunastreettest).",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    BROADCASTER_LOGIN = PropertyDescriptor(
        name="Broadcaster Login",
        description="Twitch login of the channel to post the confirmation into, without a leading #.",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CLIENT_ID = PropertyDescriptor(
        name="Client ID",
        description="Twitch app client ID used to mint an App Access Token via the client_credentials grant.",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CLIENT_SECRET = PropertyDescriptor(
        name="Client Secret",
        description="Twitch app client secret used to mint an App Access Token via the client_credentials grant.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    MESSAGE_TEMPLATE = PropertyDescriptor(
        name="Message Template",
        description="Chat confirmation text for a load command. Supports Expression Language against "
                     "flowfile attributes (streamer, screen).",
        required=True,
        default_value="${streamer} is now showing on ${screen}.",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    MATRIX_MESSAGE = PropertyDescriptor(
        name="Matrix Message",
        description="Chat confirmation text when the dispatched command was the matrix screensaver "
                     "(no streamer attribute present). Supports Expression Language against flowfile attributes.",
        required=True,
        default_value="Matrix screensaver is loading ${display_screen}.",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    DRY_RUN = PropertyDescriptor(
        name="Dry Run",
        description="When true (default), logs what would be posted instead of calling Twitch. Must be "
                     "explicitly set to false to post for real.",
        required=True,
        default_value="true",
        validators=[StandardValidators.BOOLEAN_VALIDATOR],
    )

    def __init__(self, **kwargs):
        # 'pass' is the safest initialization in many containerized environments —
        # real state is set up in onScheduled, which is guaranteed to run before transform().
        pass

    def getPropertyDescriptors(self):
        return [
            self.SENDER_LOGIN,
            self.BROADCASTER_LOGIN,
            self.CLIENT_ID,
            self.CLIENT_SECRET,
            self.MESSAGE_TEMPLATE,
            self.MATRIX_MESSAGE,
            self.DRY_RUN,
        ]

    def onScheduled(self, context):
        # App Access Token cache (client_credentials never rotates/invalidates, so it's safe to
        # reuse across calls/instances — unlike the listener's user refresh token).
        self._app_token = None
        self._app_token_expiry = 0.0
        # Resolved once, cached for the life of the running processor — same login names every time.
        self._sender_id_cache = None
        self._broadcaster_id_cache = None

    def transform(self, context, flowfile):
        contents_str = flowfile.getContentsAsBytes().decode('utf-8')
        attributes = dict(flowfile.getAttributes())

        try:
            command = attributes.get('command', 'load')
            dry_run = context.getProperty(self.DRY_RUN).asBoolean()

            # An upstream that already knows what to say - the backend's own answer to a
            # chat_trigger - puts it on chat_reply_text, and it is posted verbatim: no
            # template, no substitution, so text carrying a literal ${...} survives intact.
            # Anything without that attribute takes the original template path, unchanged.
            verbatim = attributes.get('chat_reply_text')
            if verbatim and verbatim.strip():
                message = verbatim
            else:
                # NOT context.getProperty(...).evaluateAttributeExpressions(flowfile).getValue():
                # confirmed live 2026-07-22 that this NiFi Python binding's EL evaluator only
                # resolves the FIRST ${attr} token in a property and silently drops any literal
                # text and additional tokens around it (a real "jynxzi is now showing on screen1."
                # template evaluated to just "jynxzi"). Substitute manually instead.
                template = context.getProperty(self.MATRIX_MESSAGE).getValue() if command == 'matrix' \
                    else context.getProperty(self.MESSAGE_TEMPLATE).getValue()
                message = re.sub(r'\$\{(\w+)\}', lambda m: attributes.get(m.group(1), ''), template)

            if not message or not message.strip():
                raise ValueError("Chat reply text evaluated to empty")

            if dry_run:
                attributes['dry_run'] = 'true'
                attributes['dry_run_chat_message'] = message
                return FlowFileTransformResult(
                    relationship='success',
                    attributes=attributes,
                    contents=contents_str,
                )

            client_id = context.getProperty(self.CLIENT_ID).getValue()
            client_secret = context.getProperty(self.CLIENT_SECRET).getValue()
            sender_login = context.getProperty(self.SENDER_LOGIN).getValue().lstrip('@').lower()
            broadcaster_login = context.getProperty(self.BROADCASTER_LOGIN).getValue().lstrip('#').lower()

            access_token = self._get_app_access_token(client_id, client_secret)
            sender_id = self._resolve_user_id(sender_login, client_id, access_token, '_sender_id_cache')
            broadcaster_id = self._resolve_user_id(broadcaster_login, client_id, access_token, '_broadcaster_id_cache')

            body = json.dumps({
                "broadcaster_id": broadcaster_id,
                "sender_id": sender_id,
                "message": message,
            }).encode('utf-8')
            req = urllib.request.Request(
                "https://api.twitch.tv/helix/chat/messages",
                data=body,
                method="POST",
                headers={
                    "Client-Id": client_id,
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            sent = (result.get('data') or [{}])[0]
            if sent.get('is_sent') is False:
                raise RuntimeError(f"Twitch rejected the message: {sent.get('drop_reason')}")

            attributes['chat_reply_sent'] = 'true'
            attributes['chat_reply_message'] = message
            return FlowFileTransformResult(
                relationship='success',
                attributes=attributes,
                contents=contents_str,
            )

        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', errors='ignore')[:500]
            if self.logger:
                self.logger.error(f"TwitchChatReplyProcessor HTTP {e.code}: {detail}")
            attributes['chat_reply_error'] = f"HTTP {e.code}: {detail}"
            return FlowFileTransformResult(
                relationship='failure',
                attributes=attributes,
                contents=contents_str,
            )
        except Exception as e:
            # Trap everything — never let the processor crash. Route to failure with the
            # error on an attribute so the flow can log/alert instead of losing the flowfile.
            if self.logger:
                self.logger.error(f"TwitchChatReplyProcessor failed: {e}")
            attributes['chat_reply_error'] = str(e)
            return FlowFileTransformResult(
                relationship='failure',
                attributes=attributes,
                contents=contents_str,
            )

    # --- Twitch auth/lookup helpers ---

    def _get_app_access_token(self, client_id, client_secret):
        now = time.time()
        if self._app_token and now < self._app_token_expiry - 60:
            return self._app_token
        body = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }).encode('utf-8')
        req = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=body, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        self._app_token = payload["access_token"]
        self._app_token_expiry = now + payload.get("expires_in", 3600)
        return self._app_token

    def _resolve_user_id(self, login, client_id, access_token, cache_attr):
        cached = getattr(self, cache_attr, None)
        if cached:
            return cached
        req = urllib.request.Request(
            f"https://api.twitch.tv/helix/users?login={urllib.parse.quote(login)}",
            headers={"Client-Id": client_id, "Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        data = payload.get("data") or []
        if not data:
            raise RuntimeError(f"Twitch user lookup returned no results for login '{login}'")
        user_id = data[0]["id"]
        setattr(self, cache_attr, user_id)
        return user_id
