# SendTelegram.py
#
# Custom NiFi 2.x Python processor for issue #289 (NvidiaSpark-1 / TelegramNotify PG).
#
# Why a custom processor instead of InvokeHTTP: Telegram has no header auth, so the bot
# token must sit in the request URL path. With InvokeHTTP the *resolved* URL — token
# included — lands in provenance and in the `invokehttp.request.url` attribute. This
# processor builds the URL internally from a sensitive property, so the token never
# becomes a NiFi-recorded attribute and never reaches provenance or the failure log.
#
# It owns the three things the notifier must never get wrong, centrally, so no caller
# can forget them:
#   - the roster `[Device Name]` prefix every fleet ping must carry (agent/device-comms.md),
#   - the 4096-char Telegram hard cap (the recommendation JSON can exceed it),
#   - JSON escaping (via json.dumps — free and correct, vs a hand-rolled escapeJson).
#
# The FlowFile *content* is the human message text (composed upstream). Credentials come
# from the TelegramNotify Parameter Context as #{param} references — never inline literals.

import json
import urllib.error
import urllib.request

from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, StandardValidators

TELEGRAM_MAX_CHARS = 4096  # Telegram sendMessage hard cap on `text`.


class SendTelegram(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.1'
        description = (
            'Sends the FlowFile content as a Telegram message via the bot sendMessage API. '
            'Builds the request URL internally from a sensitive Bot Token so the token never '
            'reaches provenance or the invokehttp.request.url attribute (the reason this is a '
            'custom processor and not InvokeHTTP). Prepends the [Device Name] roster prefix, '
            'truncates to 4096 chars, and escapes via json.dumps. Dry Run (default true) logs '
            'the intended send without posting.'
        )
        tags = ['telegram', 'notify', 'release-vote', 'nvidiaspark-1']
        dependencies = []  # stdlib urllib only — nothing for NiFi to pip-install on load

    BOT_TOKEN = PropertyDescriptor(
        name="Bot Token",
        description="Telegram bot token. Bind to the TelegramNotify Parameter Context as "
                    "#{Telegram Bot Token} — never a literal. Used only to build the request URL "
                    "in memory; it is never written to an attribute, the log, or provenance.",
        required=True,
        sensitive=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    CHAT_ID = PropertyDescriptor(
        name="Chat Id",
        description="Telegram chat id to deliver to. Bind to #{Telegram Chat Id}.",
        required=True,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    DEVICE_NAME = PropertyDescriptor(
        name="Device Name",
        description="Roster name of the sending device. Bind to #{Device Name}. Every message is "
                    "prefixed '[<Device Name>] ' so no caller can forget the fleet attribution "
                    "(agent/device-comms.md); a message already starting with '[' is left as-is.",
        required=True,
        default_value="NvidiaSpark-1",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )
    DRY_RUN = PropertyDescriptor(
        name="Dry Run",
        description="When true (default), logs what would be sent instead of calling Telegram. "
                    "Must be explicitly set to false to post for real.",
        required=True,
        default_value="true",
        validators=[StandardValidators.BOOLEAN_VALIDATOR],
    )

    def __init__(self, **kwargs):
        pass

    def getPropertyDescriptors(self):
        return [self.BOT_TOKEN, self.CHAT_ID, self.DEVICE_NAME, self.DRY_RUN]

    def transform(self, context, flowfile):
        contents_str = flowfile.getContentsAsBytes().decode('utf-8', errors='replace')
        attributes = dict(flowfile.getAttributes())

        try:
            device = context.getProperty(self.DEVICE_NAME).getValue().strip()
            chat_id = context.getProperty(self.CHAT_ID).getValue()
            dry_run = context.getProperty(self.DRY_RUN).asBoolean()

            text = contents_str.strip()
            if not text:
                raise ValueError("FlowFile content was empty — nothing to send")

            # Central [Device] prefix (skip if the message already leads with a bracketed tag).
            if not text.startswith('['):
                text = f"[{device}] {text}"
            # Truncate to Telegram's hard cap, leaving room for a visible marker.
            if len(text) > TELEGRAM_MAX_CHARS:
                text = text[:TELEGRAM_MAX_CHARS - 2].rstrip() + '…'

            payload = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }

            if dry_run:
                # Log the intended send; never log the token or the resolved URL.
                if self.logger:
                    self.logger.info(f"SendTelegram DRY RUN — would POST to chat {chat_id}: {text}")
                attributes['telegram.dry_run'] = 'true'
                attributes['telegram.text'] = text
                return FlowFileTransformResult(
                    relationship='success', attributes=attributes, contents=contents_str,
                )

            token = context.getProperty(self.BOT_TOKEN).getValue()
            # Token used only here, in a local — never stored on an attribute or logged.
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            if not result.get('ok'):
                # Telegram's own error text carries no token; safe to surface.
                raise RuntimeError(f"Telegram rejected the message: {result.get('description')}")

            attributes['telegram.sent'] = 'true'
            attributes['telegram.message_id'] = str((result.get('result') or {}).get('message_id', ''))
            return FlowFileTransformResult(
                relationship='success', attributes=attributes, contents=contents_str,
            )

        except urllib.error.HTTPError as e:
            # Read the body (Telegram error JSON — no token) but NEVER log e.url / the request URL,
            # which would leak the token in the path.
            detail = e.read().decode('utf-8', errors='ignore')[:500]
            if self.logger:
                self.logger.warn(f"SendTelegram HTTP {e.code} from Telegram API: {detail}")
            attributes['telegram.error'] = f"HTTP {e.code}: {detail}"
            return FlowFileTransformResult(
                relationship='failure', attributes=attributes, contents=contents_str,
            )
        except Exception as e:
            # Trap everything — never crash, never leak. The URL (with the token) is never in `e`
            # here because urllib errors other than HTTPError don't carry it; still, log only str(e).
            if self.logger:
                self.logger.warn(f"SendTelegram failed to deliver: {e}")
            attributes['telegram.error'] = str(e)
            return FlowFileTransformResult(
                relationship='failure', attributes=attributes, contents=contents_str,
            )
