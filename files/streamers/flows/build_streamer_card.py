#!/usr/bin/env python3
"""
Generates files/streamers/flows/StreamerCard.json — #281, the Streamer Knowledge Card door on the
Spark's mynifi. Streamers demo track (not the DGX guide).

One HandleHttpRequest on :8092 (NodePort 32112, files/streamers/streamer-card-door.yaml), three
routes, called by the Streamers app on WindowsDesktop:

  GET  /kb?streamer=<key>     every point for one streamer (no param = the whole collection)
                              → {"points":[{streamer_key, kind, source, verified, updated_at, as_of, text}…]}
  POST /card/preview          header X-Identity-B64 = base64(JSON identity from the streamer_brain
                              contract: streamer_key, platform, login, display_name, aliases,
                              pronouns (confirmed or ""), x_handle, notes); empty body
                              → {"card_text","hook","char_count","pronouns_ok","grounded","kb_points","kb_as_of"}
  POST /card/publish          body = the GIF bytes (image/gif); headers X-Identity-B64 +
                              X-Card-B64 = base64(JSON {text, hook, clip_id})
                              → {"tweet_id","tweet_url","dry_run","degraded","posted_at"} or 500 JSON

Base64 headers because card text carries emoji and HTTP headers do not; NiFi EL base64Decode is
UTF-8. The GIF stays the FlowFile content down the whole publish leg — nothing on that leg
replaces content until the response is built. The LLM runs only on preview; publish posts the
reviewed text back from the app (review-first, never auto-posted — agent/live-queues.md).
PostToX (files/streamers/processors/PostToX.py) does the X call; Dry Run defaults to true.

Shape (NiFi REST pitches: row 200, column 600): kb leg x=0, preview leg x=600, publish leg
x=1200, error column x=1800; every connection routes down; one Respond200 shared at the bottom.
"""
from flowgen import Flow, STD, PY, ROW, COL

OUT = "/home/tunas/BrainShare/files/streamers/flows/StreamerCard.json"
f = Flow("StreamerCard", "streamers/StreamerCard",
         "The Streamer Knowledge Card door (#281): KB read, card preview (35B), card publish to X "
         "(PostToX). Streamers track — not part of the DGX guide.", OUT)

CS_HTTP = f.service("StreamerCardHttpContext", "org.apache.nifi.http.StandardHttpContextMap",
                    "nifi-http-context-map-nar", "org.apache.nifi.http.HttpContextMap",
                    {"Maximum Outstanding Requests": "50", "Request Expiration": "5 mins"})

KB, PV, PB, ERR = 0, COL, 2 * COL, 3 * COL

# ── the door ──────────────────────────────────────────────────────────────────
f.proc("ReceiveCard", "org.apache.nifi.processors.standard.HandleHttpRequest", STD, KB, 0, {
    "Listening Port": "#{Door Port}", "Allowed Paths": "/kb|/card/preview|/card/publish",
    "Allow GET": "true", "Allow POST": "true", "Allow PUT": "false", "Allow DELETE": "false",
    "Allow HEAD": "false", "Allow OPTIONS": "false",
    "HTTP Context Map": CS_HTTP, "Maximum Threads": "10", "container-queue-size": "10",
    "Request Header Maximum Size": "64 KB", "multipart-request-max-size": "1 MB",
    "multipart-read-buffer-size": "512 KB", "Default URL Character Set": "UTF-8",
    "Client Authentication": "No Authentication", "HTTP Protocols": "HTTP_1_1",
}, services=("HTTP Context Map",))

f.update_attr("ExtractCardMeta", KB, ROW, {
    "card.route": "${http.request.uri:contains('/card/publish'):ifElse('publish', "
                  "${http.request.uri:contains('/card/preview'):ifElse('preview', 'kb')})}",
    "kb.streamer": "${http.query.param.streamer}",
    "identity.json": "${'http.headers.X-Identity-B64':isEmpty():ifElse('{}', ${'http.headers.X-Identity-B64':base64Decode()})}",
    "card.json": "${'http.headers.X-Card-B64':isEmpty():ifElse('{}', ${'http.headers.X-Card-B64':base64Decode()})}",
    "Content-Type": "application/json",
})
f.update_attr("ExtractIdentity", KB, 2 * ROW, {
    "id.key": "${identity.json:jsonPath('$.streamer_key')}",
    "id.platform": "${identity.json:jsonPath('$.platform')}",
    "id.login": "${identity.json:jsonPath('$.login')}",
    "id.display_name": "${identity.json:jsonPath('$.display_name')}",
    "id.aliases": "${identity.json:jsonPath('$.aliases')}",
    "id.pronouns": "${identity.json:jsonPath('$.pronouns')}",
    "id.x_handle": "${identity.json:jsonPath('$.x_handle')}",
    "id.notes": "${identity.json:jsonPath('$.notes')}",
    "post.text": "${card.json:jsonPath('$.text')}",
    "post.hook": "${card.json:jsonPath('$.hook')}",
    "post.clip_id": "${card.json:jsonPath('$.clip_id')}",
})
f.route_attr("RouteCard", KB, 3 * ROW, {
    "kb": "${card.route:equals('kb')}",
    "preview": "${card.route:equals('preview'):and(${id.key:isEmpty():not()})}",
    "publish": "${card.route:equals('publish'):and(${post.text:isEmpty():not()})}",
})

# ── kb leg (x=0) ──────────────────────────────────────────────────────────────
f.replace_text("BuildKbScroll", KB, 4 * ROW,
               '{${kb.streamer:isEmpty():ifElse(\'\', ${kb.streamer:prepend(\'"filter":{"must":[{"key":"streamer_key","match":{"value":"\'):append(\'"}}]},\')})}'
               '"limit":500,"with_payload":true,"with_vector":false}')
f.invoke_http("FetchKb", KB, 5 * ROW, "#{Qdrant URL}/collections/#{KB Collection}/points/scroll", read_timeout="30 secs", idle_timeout="1 sec")
f.eval_json("ExtractKbPayloads", KB, 6 * ROW, {"kb.payloads": "$.result.points[*].payload"})
f.replace_text("BuildKbResponse", KB, 7 * ROW,
               '{"collection":"#{KB Collection}","streamer":"${kb.streamer:escapeJson()}",'
               '"points":${kb.payloads:isEmpty():ifElse(\'[]\', ${kb.payloads})}}')

# ── preview leg (x=600) ───────────────────────────────────────────────────────
f.replace_text("BuildKbQuery", PV, 4 * ROW,
               '{"filter":{"must":[{"key":"streamer_key","match":{"value":"${id.key:escapeJson()}"}}]},'
               '"limit":30,"with_payload":true,"with_vector":false}')
f.invoke_http("FetchStreamerKb", PV, 5 * ROW, "#{Qdrant URL}/collections/#{KB Collection}/points/scroll", read_timeout="30 secs", idle_timeout="1 sec")
f.eval_json("ExtractKb", PV, 6 * ROW, {"kb.points": "$.result.points[*].payload.text",
                                       "kb.as_of": "$.result.points[*].payload.as_of"})

SYSTEM = (
    "You write the Streamer Knowledge Card for a live streamer we clip, posted on X from our account as a "
    "long-form post next to one of our GIFs of the streamer. You are given IDENTITY (our database) and "
    "KNOWLEDGE BASE entries (profile, caption guidance, dated research). Voice: a sharp, warm regular of "
    "the streamer's chat writing the definitive intro for people who keep seeing the clips. Structure, in "
    "this order, short lines, blank line between sections: 1) a hook of at most 260 characters that "
    "stands alone (only it shows in the timeline before 'Show more'); 2) Who: 2-3 sentences; 3) Streams: "
    "platform, login, how often and when, last live if known; 4) Known for: topics and recurring bits; "
    "5) Numbers: followers, partner/verified, top clip this week — only numbers the knowledge base "
    "gives; 6) Lately: 2-3 dated items from the research, newest first; 7) Follow — always the last "
    "line, never omitted: '@handle on X' when IDENTITY gives an X handle, then twitch.tv/<login> or "
    "kick.com/<login>. Rules: everything must come from "
    "the blocks — never invent; if the knowledge base has no dated RESEARCH entry, leave out 'Lately' "
    "and any follower or view number entirely rather than writing vague filler like 'recent activity "
    "shows'; never post anything the caption guidance says to avoid. Pronouns: if IDENTITY gives "
    "confirmed pronouns, use them freely — that confirmation overrides any 'do not assume gender / use "
    "neutral terms' line in the guidance, which is written for the unconfirmed case; if IDENTITY says "
    "NOT CONFIRMED, use the name or 'they' everywhere. At most two emoji, no hashtags; under 1400 "
    "characters total; plain text, no markdown. Answer with one JSON object: {\\\"hook\\\": str, "
    "\\\"card_text\\\": str (the whole card including the hook as its first line), \\\"pronouns_ok\\\": "
    "bool, \\\"grounded\\\": bool, \\\"used_sections\\\": [str]}. pronouns_ok is true when every "
    "pronoun in the card matches IDENTITY's confirmed pronouns, or no gendered pronoun appears; "
    "grounded is true when every fact traces to IDENTITY or a knowledge-base entry. Nothing outside "
    "the JSON."
)
USER = (
    "IDENTITY (database): name ${id.display_name:isEmpty():ifElse(${id.login}, ${id.display_name}):escapeJson()}; "
    "login ${id.login:escapeJson()} on ${id.platform:escapeJson()}; aliases: ${id.aliases:escapeJson()}; "
    "pronouns: ${id.pronouns:isEmpty():ifElse('NOT CONFIRMED - use the name only', ${id.pronouns}):escapeJson()}; "
    "X handle: ${id.x_handle:isEmpty():ifElse('(none)', ${id.x_handle}):escapeJson()}; notes: ${id.notes:escapeJson()}\\n\\n"
    "KNOWLEDGE BASE: ${kb.points:isEmpty():ifElse('(none — say so in the card and keep it to identity facts)', ${kb.points}):escapeJson()}"
)
f.replace_text("BuildCardRequest", PV, 7 * ROW,
               '{"model":"#{LLM Model}","max_tokens":#{Max Tokens},"temperature":0.5,'
               '"chat_template_kwargs":{"enable_thinking":false},"response_format":{"type":"json_object"},'
               '"messages":[{"role":"system","content":"' + SYSTEM + '"},'
               '{"role":"user","content":"' + USER + '"}]}')
f.invoke_http("CallCard", PV, 8 * ROW, "#{vLLM Base URL}/v1/chat/completions", read_timeout="3 mins")
f.eval_json("ExtractCardAnswer", PV, 9 * ROW, {"card.answer": "$.choices[0].message.content",
                                               "card.usage": "$.usage.total_tokens"})
f.replace_text("AnswerToContent", PV, 10 * ROW, "${card.answer}")
f.eval_json("ExtractCard", PV, 11 * ROW, {
    "card.text": "$.card_text", "card.hook": "$.hook", "card.pronouns_ok": "$.pronouns_ok",
    "card.grounded": "$.grounded",
}, return_type="auto-detect")
f.route_attr("CheckCard", PV, 12 * ROW, {"ok": "${card.text:isEmpty():not()}"})
f.replace_text("BuildPreviewResponse", PV, 13 * ROW,
               '{"streamer_key":"${id.key:escapeJson()}","card_text":"${card.text:escapeJson()}",'
               '"hook":"${card.hook:escapeJson()}","char_count":${card.text:length()},'
               '"hook_chars":${card.hook:length()},"pronouns_ok":${card.pronouns_ok:isEmpty():ifElse(\'null\', ${card.pronouns_ok})},'
               '"grounded":${card.grounded:isEmpty():ifElse(\'null\', ${card.grounded})},'
               '"kb_points":${kb.points:isEmpty():ifElse(\'[]\', ${kb.points})},'
               '"kb_as_of":${kb.as_of:isEmpty():ifElse(\'[]\', ${kb.as_of})},'
               '"brain":${card.answer},"brain_tokens":"${card.usage}","brain_model":"#{LLM Model}"}')

# ── publish leg (x=1200): content = the GIF the whole way ─────────────────────
f.proc("PostToX", "PostToX", PY, PB, 4 * ROW, {
    "Tweet Text": "${post.text}", "Fallback Text": "${post.hook}", "Attach Media": "true",
    "Consumer Key": "#{X API Key}", "Consumer Secret": "#{X API Secret}",
    "Access Token": "#{X Access Token}", "Access Token Secret": "#{X Access Token Secret}",
    "Dry Run": "#{Dry Run}", "Reply To Tweet ID": None,
})
for k in ("Consumer Key", "Consumer Secret", "Access Token", "Access Token Secret"):
    f.processors[-1]["propertyDescriptors"][k]["sensitive"] = True
f.replace_text("BuildPublishResponse", PB, 5 * ROW,
               '{"streamer_key":"${id.key:escapeJson()}","clip_id":"${post.clip_id:escapeJson()}",'
               '"tweet_id":"${tweet_id}","tweet_url":"${tweet_url}","dry_run":${x.dry_run:isEmpty():ifElse(\'true\', ${x.dry_run})},'
               '"degraded":"${x.degraded}","media_path":"${x.media_path}","text_chars":"${x.text_chars}",'
               '"media_bytes":"${x.media_bytes}","posted_at":"${now():format("yyyy-MM-dd\'T\'HH:mm:ssXXX", \'UTC\')}"}')

# ── shared responder ──────────────────────────────────────────────────────────
f.proc("Respond200", "org.apache.nifi.processors.standard.HandleHttpResponse", STD, PV, 14 * ROW, {
    "HTTP Status Code": "200", "HTTP Context Map": CS_HTTP,
    "Attributes to add to the HTTP Response (Regex)": "Content-Type",
}, auto=("success",), services=("HTTP Context Map",))

# ── error column (x=1800) ─────────────────────────────────────────────────────
f.update_attr("MarkError", ERR, 13 * ROW, {"mime.type": "application/json", "Content-Type": "application/json"})
f.replace_text("BuildErrorBody", ERR, 14 * ROW,
               '{"error":"card pipeline failure","route":"${card.route}","streamer_key":"${id.key:escapeJson()}",'
               '"failed_at":"${invokehttp.request.url:escapeJson()}","status":"${invokehttp.status.code}",'
               '"exception":"${invokehttp.java.exception.message:escapeJson()}","x_error":"${x.error:escapeJson()}",'
               '"card_text":"","tweet_url":""}')
f.proc("Respond500", "org.apache.nifi.processors.standard.HandleHttpResponse", STD, ERR, 15 * ROW, {
    "HTTP Status Code": "500", "HTTP Context Map": CS_HTTP,
    "Attributes to add to the HTTP Response (Regex)": "Content-Type",
}, services=("HTTP Context Map",))
f.log("LogFailures", ERR, 16 * ROW, level="warn")

# ── wiring ────────────────────────────────────────────────────────────────────
c = f.conn
c("ReceiveCard", ["success"], "ExtractCardMeta")
c("ExtractCardMeta", ["success"], "ExtractIdentity")
c("ExtractIdentity", ["success"], "RouteCard")
c("RouteCard", ["kb"], "BuildKbScroll")
c("RouteCard", ["preview"], "BuildKbQuery")
c("RouteCard", ["publish"], "PostToX")
c("RouteCard", ["unmatched"], "MarkError")

c("BuildKbScroll", ["success"], "FetchKb")
c("BuildKbScroll", ["failure"], "MarkError")
c("FetchKb", ["Retry"], "FetchKb", "2 mins")
c("FetchKb", ["Response"], "ExtractKbPayloads")
c("FetchKb", ["Failure", "No Retry"], "MarkError")
c("ExtractKbPayloads", ["matched", "unmatched"], "BuildKbResponse")
c("ExtractKbPayloads", ["failure"], "MarkError")
c("BuildKbResponse", ["success"], "Respond200")
c("BuildKbResponse", ["failure"], "MarkError")

c("BuildKbQuery", ["success"], "FetchStreamerKb")
c("BuildKbQuery", ["failure"], "MarkError")
c("FetchStreamerKb", ["Retry"], "FetchStreamerKb", "2 mins")
c("FetchStreamerKb", ["Response"], "ExtractKb")
c("FetchStreamerKb", ["Failure", "No Retry"], "BuildCardRequest")     # no KB → identity-only card
c("ExtractKb", ["matched", "unmatched", "failure"], "BuildCardRequest")
c("BuildCardRequest", ["success"], "CallCard")
c("BuildCardRequest", ["failure"], "MarkError")
c("CallCard", ["Retry"], "CallCard", "10 mins")
c("CallCard", ["Response"], "ExtractCardAnswer")
c("CallCard", ["Failure", "No Retry"], "MarkError")
c("ExtractCardAnswer", ["matched"], "AnswerToContent")
c("ExtractCardAnswer", ["unmatched", "failure"], "MarkError")
c("AnswerToContent", ["success"], "ExtractCard")
c("AnswerToContent", ["failure"], "MarkError")
c("ExtractCard", ["matched", "unmatched"], "CheckCard")
c("ExtractCard", ["failure"], "MarkError")
c("CheckCard", ["ok"], "BuildPreviewResponse")
c("CheckCard", ["unmatched"], "MarkError")
c("BuildPreviewResponse", ["success"], "Respond200")
c("BuildPreviewResponse", ["failure"], "MarkError")

c("PostToX", ["success"], "BuildPublishResponse")
c("PostToX", ["failure"], "MarkError")
c("BuildPublishResponse", ["success"], "Respond200")
c("BuildPublishResponse", ["failure"], "MarkError")

c("Respond200", ["failure"], "LogFailures")
c("MarkError", ["success"], "BuildErrorBody")
c("BuildErrorBody", ["success", "failure"], "Respond500")
c("Respond500", ["success", "failure"], "LogFailures")

# ── parameter context ─────────────────────────────────────────────────────────
f.param("Door Port", "8092", "HandleHttpRequest port inside mynifi-0; exposed by files/streamers/streamer-card-door.yaml (NodePort 32112).")
f.param("vLLM Base URL", "http://192.168.1.203:8000", "The box's vLLM (docker, LAN-published).")
f.param("LLM Model", "nvidia/Qwen3.6-35B-A3B-NVFP4", "The lead model; thinking off.")
f.param("Max Tokens", "1200", "Answer budget for the card JSON.")
f.param("Qdrant URL", "http://192.168.1.203:6333", "qdrant-kb (docker); the streamer-kb collection lives here.")
f.param("KB Collection", "streamer-kb", "Per-streamer profile/guidance/research points (#271).")
f.param("Dry Run", "true", "PostToX Dry Run. true = log the would-be post, never call X. Flip to false only for a confirmed post, then back.")
f.param("X API Key", None, "Sensitive — set via the API after upload from ~/.env X_API_KEY; never in this file.", True)
f.param("X API Secret", None, "Sensitive — set via the API from ~/.env X_API_SECRET; never in this file.", True)
f.param("X Access Token", None, "Sensitive — set via the API from ~/.env X_ACCESS_TOKEN; never in this file.", True)
f.param("X Access Token Secret", None, "Sensitive — set via the API from ~/.env X_ACCESS_TOKEN_SECRET; never in this file.", True)

if __name__ == "__main__":
    f.write()
