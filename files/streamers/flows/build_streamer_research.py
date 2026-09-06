#!/usr/bin/env python3
"""
Generates files/streamers/flows/StreamerResearch.json — #271 K5, the external-research PG for
the Streamer KB on the Spark's mynifi. Streamers demo track (not the DGX guide).

Once a day, for every active roster streamer (Postgres `streamer_brain`, #276), pull what the
public web says about them — Twitch Helix (app token) or the Kick public API for platform facts
and this week's top clips, Google News + Bing News + r/LivestreamFail RSS for what is
circulating — hand the raw sources to the box's 35B, and write two dated `kind=research` points
into `streamer-kb` (Qdrant :6333, bge-m3 :8001, 1024-d). The KB stays pronoun-free: the model is
told, RouteOnContent enforces, one rewrite pass is allowed, then the answer is dropped and
logged rather than written. A successful research upsert deletes the streamer's `prior` point
(model memory the seed wrote) — research replaces it, per streamers-new-brain-plan.md K5.

Shape (NiFi REST pitches: row 200, column 600). Twitch leg x=0, Kick leg x=600, rewrite chain
x=600, error column x=1200; every connection routes down.

  ListRoster          ExecuteSQLRecord  CRON — active roster rows from streamer_brain
  SplitRoster         SplitJson         one FlowFile per streamer
  ExtractStreamer     EvaluateJsonPath  r.*
  PrepQuery           UpdateAttribute   r.q (url-encoded name), r.since7 (ISO), r.today
  RoutePlatform       RouteOnAttribute  twitch | kick
  ── Twitch leg: HelixUser (content) → ExtractTwitchUser → HelixChannel → HelixFollowers →
     HelixStream → HelixClips → HelixSchedule → HelixVideos   (each → attribute src.*)
  ── Kick leg:   KickChannel → KickClips                       (→ attribute src.*)
  NewsGoogle → NewsBing → RedditLSF                            (→ attribute src.*)
  BuildResearchRequest → CallResearch → ExtractAnswer → AnswerToContent → CheckPronouns
     found → BuildRewriteRequest → CallRewrite → ExtractRewrite → RewriteToContent →
             CheckPronounsAgain → found → ScrubHeShe → ScrubHim → ScrubHisHer → ScrubSelf → LogScrubbed → ExtractParts
  ExtractParts → BuildPoints → SplitPoints → ExtractPoint → BuildEmbedRequest → EmbedPoint →
  PointId → BuildUpsert → UpsertPoint → BuildDeletePrior → DeletePrior → LogDone
  ── error column: MarkError → LogFailures

Upload with the NiFi REST API (skill references/flow-api.md §3), set the sensitive parameters
afterwards, enable the controller services, start the PG, RUN_ONCE ListRoster for the first pass.
After any live edit, re-export over StreamerResearch.json (§4).
"""
from flowgen import Flow, STD, ROW, COL

OUT = "/home/tunas/BrainShare/files/streamers/flows/StreamerResearch.json"
f = Flow("StreamerResearch", "streamers/StreamerResearch",
         "Daily external research per roster streamer → kind=research points in streamer-kb "
         "(#271 K5). Streamers track — not part of the DGX guide.", OUT)

# ── controller services ───────────────────────────────────────────────────────
CS_DBCP = f.service("StreamersPostgres", "org.apache.nifi.dbcp.DBCPConnectionPool",
                    "nifi-dbcp-service-nar", "org.apache.nifi.dbcp.DBCPService",
                    {"Database Connection URL": "#{Postgres JDBC URL}",
                     "Database Driver Class Name": "org.postgresql.Driver",
                     "database-driver-locations": "#{Postgres Driver Jar}",
                     "Database User": "#{Postgres User}", "Password": "#{Postgres Password}",
                     "Max Wait Time": "5 secs", "Max Total Connections": "2",
                     "Validation-query": "SELECT 1"}, sensitive=("Password",))
CS_JSONW = f.service("RosterJsonWriter", "org.apache.nifi.json.JsonRecordSetWriter",
                     "nifi-record-serialization-services-nar",
                     "org.apache.nifi.serialization.RecordSetWriterFactory",
                     {"Schema Write Strategy": "no-schema", "schema-access-strategy": "inherit-record-schema",
                      "Pretty Print JSON": "false", "suppress-nulls": "never-suppress",
                      "output-grouping": "output-array"})
# Same shape as the live TwitchHelixAppToken service in files/WatchlistChatJoiner.json:
# client_credentials against id.twitch.tv, secret in the request body, bound to a sensitive param.
CS_OAUTH = f.service("TwitchHelixAppToken", "org.apache.nifi.oauth2.StandardOauth2AccessTokenProvider",
                     "nifi-oauth2-provider-nar", "org.apache.nifi.oauth2.OAuth2AccessTokenProvider",
                     {"Authorization Server URL": "https://id.twitch.tv/oauth2/token",
                      "Grant Type": "client_credentials", "Client Authentication Strategy": "REQUEST_BODY",
                      "Client ID": "#{Twitch Client Id}", "Client secret": "#{Twitch Client Secret}",
                      "Refresh Window": "0 s", "HTTP Protocols": "H2_HTTP_1_1"},
                     sensitive=("Client secret",))

UA = "StreamerResearch/1.0 (Apache NiFi; Streamers demo; x.com/TunaStreetTest)"
TW, KK, ERR = 0, COL, 2 * COL          # columns


def helix(name, y, url, attr, size):
    """One Helix GET → attribute, bearer from the OAuth2 provider, Client-Id header."""
    f.invoke_http(name, TW, y, url, method="GET", to_attr=attr, attr_size=size,
                  headers={"Client-Id": "#{Twitch Client Id}"}, oauth=CS_OAUTH, read_timeout="20 secs")


def public_get(name, x, y, url, attr, size, timeout="20 secs"):
    f.invoke_http(name, x, y, url, method="GET", to_attr=attr, attr_size=size,
                  user_agent=UA, read_timeout=timeout)


# ── roster ────────────────────────────────────────────────────────────────────
f.proc("ListRoster", "org.apache.nifi.processors.standard.ExecuteSQLRecord", STD, TW, 0, {
    "Database Connection Pooling Service": CS_DBCP,
    "SQL Query": ("SELECT streamer_key, platform, login, display_name, "
                  "COALESCE(x_handle, '') AS x_handle FROM streamer_brain WHERE active ORDER BY streamer_key"),
    "esqlrecord-record-writer": CS_JSONW, "Max Wait Time": "10 secs", "esql-max-rows": "0",
}, services=("Database Connection Pooling Service", "esqlrecord-record-writer"),
   schedule="0 17 6 * * ?", strategy="CRON_DRIVEN")   # Quartz cron, pod clock is UTC → 06:17 UTC daily

f.split_json("SplitRoster", TW, ROW)

f.eval_json("ExtractStreamer", TW, 2 * ROW, {
    "r.key": "$.streamer_key", "r.platform": "$.platform", "r.login": "$.login",
    "r.name": "$.display_name", "r.x": "$.x_handle",
})

f.update_attr("PrepQuery", TW, 3 * ROW, {
    "r.q": "${r.name:isEmpty():ifElse(${r.login}, ${r.name}):urlEncode()}",
    "r.since7": "${now():toNumber():minus(604800000):format(\"yyyy-MM-dd'T'HH:mm:ss'Z'\", 'UTC')}",
    "r.today": "${now():format('yyyy-MM-dd', 'UTC')}",
    "r.now": "${now():format(\"yyyy-MM-dd'T'HH:mm:ssXXX\", 'UTC')}",
    "mime.type": "application/json",
})

f.route_attr("RoutePlatform", TW, 4 * ROW, {
    "twitch": "${r.platform:equals('twitch')}", "kick": "${r.platform:equals('kick')}",
})

# ── Twitch leg (x=0) ──────────────────────────────────────────────────────────
f.invoke_http("HelixUser", TW, 5 * ROW, "https://api.twitch.tv/helix/users?login=${r.login}",
              method="GET", headers={"Client-Id": "#{Twitch Client Id}"}, oauth=CS_OAUTH,
              read_timeout="20 secs")
f.eval_json("ExtractTwitchUser", TW, 6 * ROW, {
    "tw.id": "$.data[0].id", "tw.display": "$.data[0].display_name", "tw.created": "$.data[0].created_at",
    "tw.type": "$.data[0].broadcaster_type", "tw.desc": "$.data[0].description",
})
helix("HelixChannel", 7 * ROW, "https://api.twitch.tv/helix/channels?broadcaster_id=${tw.id}", "src.channel", 4096)
helix("HelixFollowers", 8 * ROW, "https://api.twitch.tv/helix/channels/followers?broadcaster_id=${tw.id}&first=1", "src.followers", 2048)
helix("HelixStream", 9 * ROW, "https://api.twitch.tv/helix/streams?user_id=${tw.id}", "src.stream", 4096)
helix("HelixClips", 10 * ROW, "https://api.twitch.tv/helix/clips?broadcaster_id=${tw.id}&started_at=${r.since7}&first=15", "src.clips", 24576)
helix("HelixSchedule", 11 * ROW, "https://api.twitch.tv/helix/schedule?broadcaster_id=${tw.id}&first=10", "src.schedule", 8192)
helix("HelixVideos", 12 * ROW, "https://api.twitch.tv/helix/videos?user_id=${tw.id}&type=archive&first=15", "src.videos", 16384)

# ── Kick leg (x=600) ──────────────────────────────────────────────────────────
public_get("KickChannel", KK, 5 * ROW, "https://kick.com/api/v2/channels/${r.login}", "src.kick", 12288)
public_get("KickClips", KK, 6 * ROW, "https://kick.com/api/v2/channels/${r.login}/clips?sort=view&time=week", "src.kickclips", 24576)

# ── shared: what others are saying ────────────────────────────────────────────
JOIN = 14 * ROW
public_get("NewsGoogle", TW, JOIN,
           "https://news.google.com/rss/search?q=${r.q}+streamer+when:#{News Window Days}d&hl=en-US&gl=US&ceid=US:en",
           "src.gnews", 49152)
public_get("NewsBing", TW, JOIN + ROW, "https://www.bing.com/news/search?q=${r.q}+streamer&format=rss", "src.bing", 12288)
public_get("RedditLSF", TW, JOIN + 2 * ROW,
           "https://www.reddit.com/r/LivestreamFail/search.rss?q=${r.q}&sort=new&restrict_sr=1&t=month",
           "src.lsf", 32768)

# ── the 35B writes the research ───────────────────────────────────────────────
SYSTEM = (
    "You are the research desk for an automated system that posts clips of live streamers on X and "
    "keeps a knowledge base about each streamer. You are given raw source material fetched just now "
    "(platform API JSON, news RSS, a Reddit RSS) about ONE streamer. Write two knowledge-base entries "
    "about the streamer, in plain English, for a model that will later write posts about them. Rules: "
    "1) Only state what the sources support; when a source is empty or an error, say so in a few "
    "words, never fill the gap from memory. 2) Every dated item carries its date (YYYY-MM-DD) and its "
    "source name. 3) NOWHERE in your answer use a gendered pronoun (he, she, him, his, her, hers, "
    "himself, herself) — use the streamer's name, 'the streamer', or singular they; rewrite any "
    "headline that contains one. 4) Numbers stay exact (followers, views). 5) No hashtags, no URLs "
    "inside the texts. Answer with one JSON object and nothing else: "
    "{\\\"as_of\\\": \\\"YYYY-MM-DD\\\", "
    "\\\"platform_text\\\": \\\"4-8 sentences: platform, partner/verified status, follower count, when "
    "the account was made, current category and stream title if live, how often and when they stream "
    "(from schedule and recent VOD dates), and this week's top clips with view counts and dates\\\", "
    "\\\"buzz_text\\\": \\\"what is circulating about the streamer in the last two weeks: one line per "
    "item as '- YYYY-MM-DD: what happened (source)', up to 8 items, newest first; then 'Viral this "
    "week:' with the clip moments people are sharing; then one hedged sentence on the overall "
    "tone of the coverage\\\", "
    "\\\"topics\\\": [\\\"3-8 short tags\\\"], "
    "\\\"facts\\\": {\\\"followers\\\": int or null, \\\"partner_or_verified\\\": bool or null, "
    "\\\"last_live\\\": \\\"YYYY-MM-DD\\\" or null, \\\"cadence\\\": \\\"short phrase or unknown\\\", "
    "\\\"top_clip\\\": \\\"title (views, date) or none\\\"}, "
    "\\\"sources\\\": [\\\"names of the sources that actually had content\\\"]}"
)


def src(label, attr, strip_desc=False):
    """One labelled source block for the prompt; empty sources say so. Google News' <description>
    is an HTML digest of related links — dropped to keep the prompt small."""
    val = f"${{{attr}:replaceAll('(?s)<description>.*?</description>', ''):escapeJson()}}" if strip_desc \
        else f"${{{attr}:escapeJson()}}"
    return f"=== {label} ===\\n${{{attr}:isEmpty():ifElse('(empty or unavailable)', {val})}}\\n\\n"


USER = (
    "STREAMER: key ${r.key:escapeJson()}; login ${r.login:escapeJson()} on ${r.platform:escapeJson()}; "
    "display name ${r.name:escapeJson()}; X handle ${r.x:isEmpty():ifElse('(none)', ${r.x}):escapeJson()}. "
    "TODAY is ${r.today}. Clip window: the last 7 days. News window: the last #{News Window Days} days.\\n\\n"
    + "=== Twitch Helix users (account) ===\\n${tw.id:isEmpty():ifElse('(empty or unavailable)', "
      "${tw.display:prepend('display '):append(', id '):append(${tw.id}):append(', created '):append(${tw.created})"
      ":append(', broadcaster_type '):append(${tw.type}):append(', bio: '):append(${tw.desc}):escapeJson()})}\\n\\n"
    + src("Twitch Helix channels (current category/title)", "src.channel")
    + src("Twitch Helix followers (total)", "src.followers")
    + src("Twitch Helix streams (live right now?)", "src.stream")
    + src("Twitch Helix clips, last 7 days, by views", "src.clips")
    + src("Twitch Helix schedule", "src.schedule")
    + src("Twitch Helix videos (recent VODs — infer cadence from dates)", "src.videos")
    + src("Kick channel (followers_count, verified, recent_categories, livestream)", "src.kick")
    + src("Kick clips, this week, by views", "src.kickclips")
    + src("Google News RSS", "src.gnews", strip_desc=True)
    + src("Bing News RSS", "src.bing")
    + src("Reddit r/LivestreamFail RSS", "src.lsf")
)

f.replace_text("BuildResearchRequest", TW, JOIN + 3 * ROW,
               '{"model":"#{LLM Model}","max_tokens":#{Max Tokens},"temperature":0.3,'
               '"chat_template_kwargs":{"enable_thinking":false},"response_format":{"type":"json_object"},'
               '"messages":[{"role":"system","content":"' + SYSTEM + '"},'
               '{"role":"user","content":"' + USER + '"}]}')
f.invoke_http("CallResearch", TW, JOIN + 4 * ROW, "#{vLLM Base URL}/v1/chat/completions", read_timeout="5 mins")
f.eval_json("ExtractAnswer", TW, JOIN + 5 * ROW, {"research.answer": "$.choices[0].message.content",
                                                  "research.usage": "$.usage.total_tokens"})
f.replace_text("AnswerToContent", TW, JOIN + 6 * ROW, "${research.answer}")

PRONOUN = "(?i)\\b(he|she|him|his|hers|her|himself|herself)\\b"
f.route_content("CheckPronouns", TW, JOIN + 7 * ROW, {"found": PRONOUN})

# one rewrite pass (x=600), same instruction the seeder's depronoun() uses
REWRITE_SYS = ("Rewrite the JSON so that no string in it contains a gendered pronoun (he, she, him, his, "
               "her, hers, himself, herself). Use the streamer's name, 'the streamer' or singular they. "
               "Keep every key, every number and every date exactly as they are. Return only the JSON.")
f.replace_text("BuildRewriteRequest", KK, JOIN + 8 * ROW,
               '{"model":"#{LLM Model}","max_tokens":#{Max Tokens},"temperature":0.0,'
               '"chat_template_kwargs":{"enable_thinking":false},"response_format":{"type":"json_object"},'
               '"messages":[{"role":"system","content":"' + REWRITE_SYS + '"},'
               '{"role":"user","content":"Streamer name: ${r.name:escapeJson()}\\n\\n${research.answer:escapeJson()}"}]}')
f.invoke_http("CallRewrite", KK, JOIN + 9 * ROW, "#{vLLM Base URL}/v1/chat/completions", read_timeout="5 mins")
f.eval_json("ExtractRewrite", KK, JOIN + 10 * ROW, {"research.answer": "$.choices[0].message.content"})
f.replace_text("RewriteToContent", KK, JOIN + 11 * ROW, "${research.answer}")
f.route_content("CheckPronounsAgain", KK, JOIN + 12 * ROW, {"found": PRONOUN})
# Last resort, same map as seed_profiles.depronoun's _SCRUB: a pronoun that survives the rewrite is
# replaced mechanically (he/she→they, him→them, his/her/hers→their, himself/herself→themself)
# rather than losing the whole day's research for that streamer. Runs 2026-09-06: 2 of 9 answers
# needed it — headlines quoted from the news feeds.
def scrub(name, y, regex, repl):
    f.proc(name, "org.apache.nifi.processors.standard.ReplaceText", STD, ERR, y, {
        "Replacement Strategy": "Regex Replace", "Evaluation Mode": "Entire text",
        "Regular Expression": regex, "Replacement Value": repl,
        "Character Set": "UTF-8", "Maximum Buffer Size": "10 MB", "Line-by-Line Evaluation Mode": "All",
    }, run_ms=25)
scrub("ScrubHeShe", JOIN + 13 * ROW, "(?i)\\b(he|she)\\b", "they")
scrub("ScrubHim", JOIN + 14 * ROW, "(?i)\\bhim\\b", "them")
scrub("ScrubHisHer", JOIN + 15 * ROW, "(?i)\\b(his|her|hers)\\b", "their")
scrub("ScrubSelf", JOIN + 16 * ROW, "(?i)\\b(himself|herself)\\b", "themself")
f.log("LogScrubbed", ERR, JOIN + 17 * ROW, level="warn", auto=())

# ── points ────────────────────────────────────────────────────────────────────
P0 = JOIN + 18 * ROW
f.eval_json("ExtractParts", TW, P0, {
    "pt.platform_text": "$.platform_text", "pt.buzz_text": "$.buzz_text", "pt.as_of": "$.as_of",
    "pt.topics": "$.topics", "pt.sources": "$.sources", "pt.facts": "$.facts",
})   # Return Type json: arrays come back as JSON text (auto-detect refuses them)

f.replace_text("BuildPoints", TW, P0 + ROW,
               '[{"sub":"platform","source":"platform","verified":true,'
               '"text":"RESEARCH \\u2014 platform facts (as of ${pt.as_of:isEmpty():ifElse(${r.today}, ${pt.as_of})}, '
               '${r.platform:equals(\'kick\'):ifElse(\'Kick public API\', \'Twitch Helix\')}): '
               '${pt.platform_text:escapeJson()} Topics: ${pt.topics:replaceAll(\'[\\\\[\\\\]"]\', \'\'):escapeJson()}"},'
               '{"sub":"buzz","source":"press","verified":false,'
               '"text":"RESEARCH \\u2014 what is circulating (as of ${pt.as_of:isEmpty():ifElse(${r.today}, ${pt.as_of})}, '
               'news + r/LivestreamFail + platform clips): ${pt.buzz_text:escapeJson()}"}]')
f.split_json("SplitPoints", TW, P0 + 2 * ROW)
f.eval_json("ExtractPoint", TW, P0 + 3 * ROW, {
    "point.sub": "$.sub", "point.source": "$.source", "point.verified": "$.verified", "point.text": "$.text",
})
f.replace_text("BuildEmbedRequest", TW, P0 + 4 * ROW, '{"inputs":["${point.text:escapeJson()}"]}')
f.invoke_http("EmbedPoint", TW, P0 + 5 * ROW, "#{TEI URL}/embed", to_attr="embed.vec", attr_size=65536,
              read_timeout="60 secs", idle_timeout="1 sec")
# deterministic id: md5("<key>::research-<sub>::0") as a UUID — the daily run overwrites, nothing accretes
f.update_attr("PointId", TW, P0 + 6 * ROW, {
    "point.hex": "${r.key:append('::research-'):append(${point.sub}):append('::0'):hash('MD5')}",
})
f.replace_text("BuildUpsert", TW, P0 + 7 * ROW,
               '{"points":[{"id":"${point.hex:substring(0,8)}-${point.hex:substring(8,12)}-${point.hex:substring(12,16)}-'
               '${point.hex:substring(16,20)}-${point.hex:substring(20,32)}",'
               '"vector":${embed.vec:substring(1, ${embed.vec:length():minus(1)})},'
               '"payload":{"streamer_key":"${r.key:escapeJson()}","platform":"${r.platform}","login":"${r.login:escapeJson()}",'
               '"x_handle":"${r.x:escapeJson()}","kind":"research","source":"${point.source}","verified":${point.verified},'
               '"as_of":"${pt.as_of:isEmpty():ifElse(${r.today}, ${pt.as_of})}","updated_at":"${r.now}",'
               '"sources":${pt.sources:isEmpty():ifElse(\'[]\', ${pt.sources})},'
               '"text":"${point.text:escapeJson()}"}}]}')
f.invoke_http("UpsertPoint", TW, P0 + 8 * ROW, "#{Qdrant URL}/collections/#{KB Collection}/points?wait=true",
              method="PUT", read_timeout="30 secs", idle_timeout="1 sec")
f.replace_text("BuildDeletePrior", TW, P0 + 9 * ROW,
               '{"filter":{"must":[{"key":"streamer_key","match":{"value":"${r.key:escapeJson()}"}},'
               '{"key":"kind","match":{"value":"prior"}}]}}')
f.invoke_http("DeletePrior", TW, P0 + 10 * ROW, "#{Qdrant URL}/collections/#{KB Collection}/points/delete?wait=true",
              read_timeout="30 secs", idle_timeout="1 sec")
f.log("LogDone", TW, P0 + 11 * ROW, level="info")

# ── error column ──────────────────────────────────────────────────────────────
f.update_attr("MarkError", ERR, P0 + 10 * ROW, {"research.failed_at": "${invokehttp.request.url}",
                                                 "research.status": "${invokehttp.status.code}",
                                                 "research.exception": "${invokehttp.java.exception.message}"})
f.log("LogFailures", ERR, P0 + 11 * ROW, level="warn")

# ── wiring ────────────────────────────────────────────────────────────────────
c = f.conn
c("ListRoster", ["success"], "SplitRoster")
c("ListRoster", ["failure"], "MarkError")
c("SplitRoster", ["split"], "ExtractStreamer")
c("SplitRoster", ["failure"], "MarkError")
c("ExtractStreamer", ["matched"], "PrepQuery")
c("ExtractStreamer", ["unmatched", "failure"], "MarkError")
c("PrepQuery", ["success"], "RoutePlatform")
c("RoutePlatform", ["twitch"], "HelixUser")
c("RoutePlatform", ["kick"], "KickChannel")
c("RoutePlatform", ["unmatched"], "MarkError")

# Twitch leg — a dead source never kills the streamer's refresh: failures fall through
c("HelixUser", ["Retry"], "HelixUser", "2 mins")
c("HelixUser", ["Response"], "ExtractTwitchUser")
c("HelixUser", ["Failure", "No Retry"], "NewsGoogle")
c("ExtractTwitchUser", ["matched"], "HelixChannel")
c("ExtractTwitchUser", ["unmatched", "failure"], "NewsGoogle")
chain = ["HelixChannel", "HelixFollowers", "HelixStream", "HelixClips", "HelixSchedule", "HelixVideos", "NewsGoogle"]
for a, b in zip(chain, chain[1:]):
    c(a, ["Retry"], a, "2 mins")
    c(a, ["Original", "Failure", "No Retry"], b)

# Kick leg
c("KickChannel", ["Retry"], "KickChannel", "2 mins")
c("KickChannel", ["Original", "Failure", "No Retry"], "KickClips")
c("KickClips", ["Retry"], "KickClips", "2 mins")
c("KickClips", ["Original", "Failure", "No Retry"], "NewsGoogle")

# shared sources
for a, b in (("NewsGoogle", "NewsBing"), ("NewsBing", "RedditLSF"), ("RedditLSF", "BuildResearchRequest")):
    c(a, ["Retry"], a, "2 mins")
    c(a, ["Original", "Failure", "No Retry"], b)

c("BuildResearchRequest", ["success"], "CallResearch")
c("BuildResearchRequest", ["failure"], "MarkError")
c("CallResearch", ["Retry"], "CallResearch", "10 mins")
c("CallResearch", ["Response"], "ExtractAnswer")
c("CallResearch", ["Failure", "No Retry"], "MarkError")
c("ExtractAnswer", ["matched"], "AnswerToContent")
c("ExtractAnswer", ["unmatched", "failure"], "MarkError")
c("AnswerToContent", ["success"], "CheckPronouns")
c("AnswerToContent", ["failure"], "MarkError")
c("CheckPronouns", ["unmatched"], "ExtractParts")
c("CheckPronouns", ["found"], "BuildRewriteRequest")
c("BuildRewriteRequest", ["success"], "CallRewrite")
c("BuildRewriteRequest", ["failure"], "MarkError")
c("CallRewrite", ["Retry"], "CallRewrite", "10 mins")
c("CallRewrite", ["Response"], "ExtractRewrite")
c("CallRewrite", ["Failure", "No Retry"], "MarkError")
c("ExtractRewrite", ["matched"], "RewriteToContent")
c("ExtractRewrite", ["unmatched", "failure"], "MarkError")
c("RewriteToContent", ["success"], "CheckPronounsAgain")
c("RewriteToContent", ["failure"], "MarkError")
c("CheckPronounsAgain", ["unmatched"], "ExtractParts")
c("CheckPronounsAgain", ["found"], "ScrubHeShe")           # mechanical scrub, then written
for a, b in (("ScrubHeShe", "ScrubHim"), ("ScrubHim", "ScrubHisHer"), ("ScrubHisHer", "ScrubSelf"), ("ScrubSelf", "LogScrubbed")):
    c(a, ["success"], b)
    c(a, ["failure"], "MarkError")
c("LogScrubbed", ["success"], "ExtractParts")

c("ExtractParts", ["matched"], "BuildPoints")
c("ExtractParts", ["unmatched", "failure"], "MarkError")
c("BuildPoints", ["success"], "SplitPoints")
c("BuildPoints", ["failure"], "MarkError")
c("SplitPoints", ["split"], "ExtractPoint")
c("SplitPoints", ["failure"], "MarkError")
c("ExtractPoint", ["matched"], "BuildEmbedRequest")
c("ExtractPoint", ["unmatched", "failure"], "MarkError")
c("BuildEmbedRequest", ["success"], "EmbedPoint")
c("BuildEmbedRequest", ["failure"], "MarkError")
c("EmbedPoint", ["Retry"], "EmbedPoint", "5 mins")
c("EmbedPoint", ["Original"], "PointId")
c("EmbedPoint", ["Failure", "No Retry"], "MarkError")
c("PointId", ["success"], "BuildUpsert")
c("BuildUpsert", ["success"], "UpsertPoint")
c("BuildUpsert", ["failure"], "MarkError")
c("UpsertPoint", ["Retry"], "UpsertPoint", "5 mins")
c("UpsertPoint", ["Response"], "BuildDeletePrior")
c("UpsertPoint", ["Failure", "No Retry"], "MarkError")
c("BuildDeletePrior", ["success"], "DeletePrior")
c("BuildDeletePrior", ["failure"], "MarkError")
c("DeletePrior", ["Retry"], "DeletePrior", "5 mins")
c("DeletePrior", ["Response"], "LogDone")
c("DeletePrior", ["Failure", "No Retry"], "MarkError")
c("MarkError", ["success"], "LogFailures")

# ── parameter context ─────────────────────────────────────────────────────────
f.param("vLLM Base URL", "http://192.168.1.203:8000", "The box's vLLM (docker, LAN-published); pods reach it at the LAN address.")
f.param("LLM Model", "nvidia/Qwen3.6-35B-A3B-NVFP4", "The lead model; thinking off.")
f.param("Max Tokens", "1600", "Answer budget for the two research texts.")
f.param("TEI URL", "http://192.168.1.203:8001", "bge-m3 embeddings (1024-d) — the collection's embedder.")
f.param("Qdrant URL", "http://192.168.1.203:6333", "qdrant-kb (docker); the streamer-kb collection lives here.")
f.param("KB Collection", "streamer-kb", "Per-streamer profile/guidance/research points (#271).")
f.param("News Window Days", "14", "Google News `when:` window for what is circulating.")
f.param("Postgres JDBC URL", "jdbc:postgresql://192.168.1.121:5432/streamers", "WindowsDesktop's streamers DB, LAN path (#276).")
f.param("Postgres Driver Jar", "/opt/nifi/nifi-current/ext/jdbc/postgresql/postgresql-8.2-and-newer/postgresql-42.7.7.jar", "Ships in the CFM NiFi image.")
f.param("Postgres User", "streamer_brain", "SELECT on the streamer_brain view only.")
f.param("Postgres Password", None, "Sensitive — set via the API after upload from ~/.env STREAMER_BRAIN_DB_PASSWORD; never in this file.", True)
f.param("Twitch Client Id", None, "Twitch app client id (Helix app token). Set via the API from ~/.env TWITCH_CLIENT_ID; never in this file.")
f.param("Twitch Client Secret", None, "Sensitive — set via the API from ~/.env TWITCH_CLIENT_SECRET; never in this file.", True)

if __name__ == "__main__":
    f.write()
