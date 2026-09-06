# PostToX.py
#
# Custom NiFi 2.x Python processor for the Streamers demo (#281, StreamerCard PG on the
# Spark's mynifi). Posts the FlowFile content as a media attachment (an animated GIF) with the
# given text to X as @TunaStreetTest — the same library calls the app's proven `_publish_sync`
# makes (tweepy: v1.1 chunked media upload as tweet_gif, then v2 create_tweet), and the same
# OAuth1 / Dry-Run / trap-everything shape as XLivePostProcessor.py and SendTelegram.py.
#
# Credentials come from the StreamerCard Parameter Context as #{param} references on the four
# sensitive properties — never inline literals, never logged, never written to an attribute.
#
# Degrade paths (each surfaced as an attribute, never silent):
#   x.media_path = v1.1 | v2      the v1.1 upload host is what the app uses today; if it is
#                                 refused, the v2 initialize/append/finalize endpoints are tried
#   x.degraded   = short          the long text (X Premium, >280 chars) was rejected, so the
#                                 <=280-char Fallback Text was posted instead
#
# FlowFile content in = the GIF bytes; content out = unchanged. success carries tweet_id /
# tweet_url; failure carries x.error.

import io
import json
import time

from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, ExpressionLanguageScope, StandardValidators

GIF_MAX_BYTES = 15 * 1024 * 1024   # X's animated-GIF cap
X_V2_MEDIA = "https://api.x.com/2/media/upload"


class PostToX(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.1'
        description = (
            'Posts the FlowFile content (an animated GIF) with Tweet Text to X via OAuth1: v1.1 '
            'chunked media upload (tweet_gif) + v2 POST /2/tweets — the same tweepy calls the '
            'Streamers app makes. Long text needs an X Premium account; if X rejects it the '
            'Fallback Text (<=280 chars) is posted and x.degraded=short is set. If the v1.1 upload '
            'host refuses, the v2 media endpoints are tried once (x.media_path=v2). Dry Run '
            '(default true) logs the intended post without calling X.'
        )
        tags = ['x', 'twitter', 'oauth1', 'streamers', 'knowledge-card', 'gif']
        dependencies = ['tweepy>=4.14', 'requests-oauthlib>=1.3']

    TWEET_TEXT = PropertyDescriptor(
        name="Tweet Text", description="The post text (long form allowed on Premium). Expression Language.",
        required=True, expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR])
    FALLBACK_TEXT = PropertyDescriptor(
        name="Fallback Text", description="<=280-char text posted instead when X rejects the long text "
        "(error 111 / too long). Expression Language. Empty = no fallback, the post fails.",
        required=False, expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES)
    MEDIA_ENABLED = PropertyDescriptor(
        name="Attach Media", description="true = upload the FlowFile content as an animated GIF and "
        "attach it; false = text-only post (content ignored).",
        required=True, default_value="true", validators=[StandardValidators.BOOLEAN_VALIDATOR])
    CONSUMER_KEY = PropertyDescriptor(name="Consumer Key", description="X API key (bind #{X API Key}).",
                                      required=True, sensitive=True, validators=[StandardValidators.NON_EMPTY_VALIDATOR])
    CONSUMER_SECRET = PropertyDescriptor(name="Consumer Secret", description="X API secret (bind #{X API Secret}).",
                                         required=True, sensitive=True, validators=[StandardValidators.NON_EMPTY_VALIDATOR])
    ACCESS_TOKEN = PropertyDescriptor(name="Access Token", description="X access token (bind #{X Access Token}).",
                                      required=True, sensitive=True, validators=[StandardValidators.NON_EMPTY_VALIDATOR])
    ACCESS_TOKEN_SECRET = PropertyDescriptor(name="Access Token Secret", description="X access token secret (bind #{X Access Token Secret}).",
                                             required=True, sensitive=True, validators=[StandardValidators.NON_EMPTY_VALIDATOR])
    DRY_RUN = PropertyDescriptor(
        name="Dry Run", description="When true (default), logs what would be posted instead of calling X. "
        "Must be explicitly set to false to post for real.",
        required=True, default_value="true", validators=[StandardValidators.BOOLEAN_VALIDATOR])
    REPLY_TO = PropertyDescriptor(
        name="Reply To Tweet ID", description="Optional. Post as a reply to this tweet id.",
        required=False, expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES)

    def __init__(self, **kwargs):
        pass

    def getPropertyDescriptors(self):
        return [self.TWEET_TEXT, self.FALLBACK_TEXT, self.MEDIA_ENABLED, self.CONSUMER_KEY,
                self.CONSUMER_SECRET, self.ACCESS_TOKEN, self.ACCESS_TOKEN_SECRET, self.DRY_RUN, self.REPLY_TO]

    # ── media upload ──────────────────────────────────────────────────────────
    def _upload_v1(self, creds, data):
        import tweepy
        ck, cs, at, ats = creds
        api = tweepy.API(tweepy.OAuth1UserHandler(ck, cs, at, ats))
        # Same call the app makes for its gif posts (chunked, tweet_gif). tweepy polls
        # processing_info until the GIF is ready.
        media = api.media_upload(filename="card.gif", file=io.BytesIO(data), chunked=True,
                                 media_category="tweet_gif")
        return str(media.media_id)

    def _upload_v2(self, creds, data):
        import requests
        from requests_oauthlib import OAuth1
        auth = OAuth1(*creds)
        r = requests.post(f"{X_V2_MEDIA}/initialize", auth=auth, timeout=30, json={
            "media_type": "image/gif", "total_bytes": len(data), "media_category": "tweet_gif"})
        if r.status_code >= 300:
            raise RuntimeError(f"v2 initialize {r.status_code}: {r.text[:300]}")
        media_id = (r.json().get("data") or {}).get("id")
        if not media_id:
            raise RuntimeError(f"v2 initialize returned no id: {r.text[:300]}")
        chunk = 4 * 1024 * 1024
        for i in range(0, len(data), chunk):
            r = requests.post(f"{X_V2_MEDIA}/{media_id}/append", auth=auth, timeout=120,
                              data={"segment_index": i // chunk},
                              files={"media": ("card.gif", data[i:i + chunk], "image/gif")})
            if r.status_code >= 300:
                raise RuntimeError(f"v2 append {r.status_code}: {r.text[:300]}")
        r = requests.post(f"{X_V2_MEDIA}/{media_id}/finalize", auth=auth, timeout=60)
        if r.status_code >= 300:
            raise RuntimeError(f"v2 finalize {r.status_code}: {r.text[:300]}")
        info = (r.json().get("data") or {}).get("processing_info") or {}
        deadline = time.time() + 120
        while info.get("state") in ("pending", "in_progress") and time.time() < deadline:
            time.sleep(max(1, int(info.get("check_after_secs", 2))))
            r = requests.get(X_V2_MEDIA, auth=auth, timeout=30,
                             params={"media_id": media_id, "command": "STATUS"})
            info = (r.json().get("data") or {}).get("processing_info") or {}
        if info.get("state") == "failed":
            raise RuntimeError(f"v2 processing failed: {json.dumps(info)[:300]}")
        return str(media_id)

    def _create_tweet(self, creds, text, media_id, reply_to):
        import tweepy
        ck, cs, at, ats = creds
        client = tweepy.Client(consumer_key=ck, consumer_secret=cs, access_token=at, access_token_secret=ats)
        kwargs = {"text": text}
        if media_id:
            kwargs["media_ids"] = [media_id]
        if reply_to:
            kwargs["in_reply_to_tweet_id"] = reply_to
        resp = client.create_tweet(**kwargs)
        return str(resp.data["id"])

    # ── transform ─────────────────────────────────────────────────────────────
    def transform(self, context, flowfile):
        data = flowfile.getContentsAsBytes()
        attributes = dict(flowfile.getAttributes())
        try:
            text = (context.getProperty(self.TWEET_TEXT).evaluateAttributeExpressions(flowfile).getValue() or "").strip()
            if not text:
                raise ValueError("Tweet Text evaluated to empty")
            fb = context.getProperty(self.FALLBACK_TEXT).evaluateAttributeExpressions(flowfile).getValue()
            fallback = (fb or "").strip()
            reply_to = (context.getProperty(self.REPLY_TO).evaluateAttributeExpressions(flowfile).getValue() or "").strip()
            attach = context.getProperty(self.MEDIA_ENABLED).asBoolean()
            dry_run = context.getProperty(self.DRY_RUN).asBoolean()

            if attach:
                if not data or data[:6] not in (b"GIF89a", b"GIF87a"):
                    raise ValueError(f"content is not a GIF ({len(data or b'')} bytes, magic {data[:6]!r})")
                if len(data) > GIF_MAX_BYTES:
                    raise ValueError(f"GIF is {len(data)} bytes, over X's {GIF_MAX_BYTES} cap")

            attributes['x.text_chars'] = str(len(text))
            attributes['x.media_bytes'] = str(len(data) if attach else 0)

            if dry_run:
                if self.logger:
                    self.logger.info(f"PostToX DRY RUN — would post {len(text)} chars"
                                     f"{' + GIF ' + str(len(data)) + ' B' if attach else ''}"
                                     f"{' as reply to ' + reply_to if reply_to else ''}: {text[:200]!r}")
                attributes['x.dry_run'] = 'true'
                attributes['tweet_id'] = ''
                attributes['tweet_url'] = ''
                return FlowFileTransformResult(relationship='success', attributes=attributes, contents=data)

            creds = (context.getProperty(self.CONSUMER_KEY).getValue(),
                     context.getProperty(self.CONSUMER_SECRET).getValue(),
                     context.getProperty(self.ACCESS_TOKEN).getValue(),
                     context.getProperty(self.ACCESS_TOKEN_SECRET).getValue())

            media_id = None
            if attach:
                try:
                    media_id = self._upload_v1(creds, data)
                    attributes['x.media_path'] = 'v1.1'
                except Exception as e1:
                    if self.logger:
                        self.logger.warn(f"PostToX v1.1 media upload failed ({e1}); trying v2 media endpoints")
                    media_id = self._upload_v2(creds, data)
                    attributes['x.media_path'] = 'v2'
                attributes['x.media_id'] = media_id

            try:
                tweet_id = self._create_tweet(creds, text, media_id, reply_to)
            except Exception as e2:
                msg = str(e2)
                too_long = ("111" in msg or "too long" in msg.lower()) and len(text) > 280
                if not (too_long and fallback):
                    raise
                if self.logger:
                    self.logger.warn(f"PostToX long text rejected ({msg[:120]}); posting the fallback text")
                tweet_id = self._create_tweet(creds, fallback[:280], media_id, reply_to)
                attributes['x.degraded'] = 'short'

            attributes['x.dry_run'] = 'false'
            attributes['tweet_id'] = tweet_id
            attributes['tweet_url'] = f"https://x.com/TunaStreetTest/status/{tweet_id}"
            return FlowFileTransformResult(relationship='success', attributes=attributes, contents=data)

        except Exception as e:
            # Trap everything — never crash, never leak a credential (none is ever in `e`).
            if self.logger:
                self.logger.warn(f"PostToX failed: {e}")
            attributes['x.error'] = str(e)[:1000]
            return FlowFileTransformResult(relationship='failure', attributes=attributes, contents=data)
