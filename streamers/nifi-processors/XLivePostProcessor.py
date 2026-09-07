import json
from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, ExpressionLanguageScope, StandardValidators


class XLivePostProcessor(FlowFileTransform):
    # Mandatory: Registers the processor with the NiFi backend
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.2-SNAPSHOT'
        description = 'Posts a text-only tweet via OAuth1-signed X API v2 (POST /2/tweets), optionally as a reply. Dry Run mode logs the request instead of sending it.'
        tags = ['x', 'twitter', 'oauth1', 'streamers', 'live-alert']
        dependencies = ['requests-oauthlib']

    TWEET_TEXT = PropertyDescriptor(
        name="Tweet Text",
        description="The text to post. Supports Expression Language against flowfile attributes.",
        required=True,
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CONSUMER_KEY = PropertyDescriptor(
        name="Consumer Key",
        description="X API consumer key (app-level, X_API_KEY).",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CONSUMER_SECRET = PropertyDescriptor(
        name="Consumer Secret",
        description="X API consumer secret (app-level, X_API_SECRET).",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    ACCESS_TOKEN = PropertyDescriptor(
        name="Access Token",
        description="X API account access token (X_ACCESS_TOKEN).",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    ACCESS_TOKEN_SECRET = PropertyDescriptor(
        name="Access Token Secret",
        description="X API account access token secret (X_ACCESS_TOKEN_SECRET).",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    DRY_RUN = PropertyDescriptor(
        name="Dry Run",
        description="When true (default), logs what would be posted instead of calling X. Must be explicitly set to false to post for real.",
        required=True,
        default_value="true",
        validators=[StandardValidators.BOOLEAN_VALIDATOR],
    )
    REPLY_TO_TWEET_ID = PropertyDescriptor(
        name="Reply To Tweet ID",
        description="Optional. If set (and non-empty after EL evaluation), posts as a reply to this tweet ID instead of a new top-level tweet.",
        required=False,
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES,
    )

    def __init__(self, **kwargs):
        # 'pass' is the safest initialization in many containerized environments
        pass

    def getPropertyDescriptors(self):
        return [
            self.TWEET_TEXT,
            self.CONSUMER_KEY,
            self.CONSUMER_SECRET,
            self.ACCESS_TOKEN,
            self.ACCESS_TOKEN_SECRET,
            self.DRY_RUN,
            self.REPLY_TO_TWEET_ID,
        ]

    def transform(self, context, flowfile):
        contents_str = flowfile.getContentsAsBytes().decode('utf-8')
        attributes = dict(flowfile.getAttributes())

        try:
            tweet_text = context.getProperty(self.TWEET_TEXT).evaluateAttributeExpressions(flowfile).getValue()
            if not tweet_text or not tweet_text.strip():
                raise ValueError("Tweet Text evaluated to empty")

            reply_to_tweet_id = context.getProperty(self.REPLY_TO_TWEET_ID).evaluateAttributeExpressions(flowfile).getValue()
            reply_to_tweet_id = reply_to_tweet_id.strip() if reply_to_tweet_id else ""

            dry_run = context.getProperty(self.DRY_RUN).asBoolean()

            if dry_run:
                attributes['dry_run'] = 'true'
                attributes['dry_run_tweet_text'] = tweet_text
                attributes['dry_run_reply_to'] = reply_to_tweet_id
                return FlowFileTransformResult(
                    relationship='success',
                    attributes=attributes,
                    contents=contents_str,
                )

            # Real post — import here so a dry-run-only deployment never needs the dependency resolved eagerly
            from requests_oauthlib import OAuth1
            import requests

            consumer_key = context.getProperty(self.CONSUMER_KEY).getValue()
            consumer_secret = context.getProperty(self.CONSUMER_SECRET).getValue()
            access_token = context.getProperty(self.ACCESS_TOKEN).getValue()
            access_token_secret = context.getProperty(self.ACCESS_TOKEN_SECRET).getValue()

            body_json = {"text": tweet_text}
            if reply_to_tweet_id:
                body_json["reply"] = {"in_reply_to_tweet_id": reply_to_tweet_id}

            auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)
            response = requests.post(
                "https://api.twitter.com/2/tweets",
                auth=auth,
                json=body_json,
                timeout=15,
            )

            if response.status_code >= 300:
                raise RuntimeError(f"X API {response.status_code}: {response.text[:500]}")

            body = response.json()
            tweet_id = body.get("data", {}).get("id", "")
            attributes['tweet_id'] = tweet_id
            attributes['tweet_url'] = f"https://x.com/i/status/{tweet_id}" if tweet_id else ""

            return FlowFileTransformResult(
                relationship='success',
                attributes=attributes,
                contents=contents_str,
            )

        except Exception as e:
            # Trap everything — never let the processor crash. Route to failure with the
            # error on an attribute so the flow can log/alert instead of losing the flowfile.
            attributes['x_error'] = str(e)
            return FlowFileTransformResult(
                relationship='failure',
                attributes=attributes,
                contents=contents_str,
            )
