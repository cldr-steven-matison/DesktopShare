#!/usr/bin/env python3
"""
Generates files/streamers/flows/StreamerBrain.json — the StreamerBrain Process Group for the
Spark's mynifi (#272). Streamers demo track. Upload it with the NiFi REST API
(skill: references/flow-api.md §3), set the one sensitive parameter afterwards, enable the
controller services, start the PG. After any live edit, re-export over this file (§4).

Shape (NiFi REST pitches: spine x=0, row 200; error column x=+300; every connection routes down):

  ReceiveClip        HandleHttpRequest  :8091 POST /caption — body = MP4, headers X-Clip-Id/X-Streamer/X-Source/X-Title
  ExtractClipMeta    UpdateAttribute    clip.*, streamer.key (login | kick:login), sql.args.1.*
  PrepClip           InvokeHTTP         → clip-prep (k3s) : transcript + frame_urls + image_parts   [Retry self-loop]
  ExtractPrep        EvaluateJsonPath   transcript, prep.*
  LookupIdentity     ExecuteSQLRecord   streamer_brain view (WindowsDesktop Postgres, #276)         [failure → skip]
  ExtractIdentity    EvaluateJsonPath   id.*
  BuildKbQuery       ReplaceText        qdrant scroll filtered by streamer_key
  FetchStreamerKb    InvokeHTTP         → qdrant :6333 streamer-kb                                   [failure → skip]
  ExtractKb          EvaluateJsonPath   kb.points
  BuildBrainRequest  ReplaceText        one chat request: identity + KB + transcript + title + frames
  CallBrain          InvokeHTTP         → vLLM :8000, thinking off, JSON answer                      [Retry self-loop]
  ExtractAnswer      EvaluateJsonPath   brain.answer
  AnswerToContent    ReplaceText        content = the answer JSON
  ExtractCaption     EvaluateJsonPath   brain.caption / pronouns_ok / grounded / visual_summary
  CheckAnswer        RouteOnAttribute   ok = caption present
  BuildResponse      ReplaceText        the door contract
  Respond200         HandleHttpResponse
  ── error column (x=300): MarkError → BuildErrorBody → Respond500 → LogFailures
"""
import json
import uuid

OUT = "/home/tunas/BrainShare/files/streamers/flows/StreamerBrain.json"
VER = "2.6.0.4.3.4.0-234"
PG_NAME = "StreamerBrain"
NS = uuid.UUID("6f1c2a3e-7b1d-4e0a-9c5b-streamerbrain".replace("streamerbrain", "0a1b2c3d4e5f"))


def uid(name):
    return str(uuid.uuid5(NS, name))


PG_ID = uid("pg")
STD = {"group": "org.apache.nifi", "artifact": "nifi-standard-nar", "version": VER}
UPD = {"group": "org.apache.nifi", "artifact": "nifi-update-attribute-nar", "version": VER}

# ── controller services ───────────────────────────────────────────────────────
CS_HTTP = uid("cs-http")
CS_DBCP = uid("cs-dbcp")
CS_JSONW = uid("cs-jsonw")


def descriptors(props, services=(), sensitive=()):
    return {k: {"name": k, "displayName": k, "dynamic": False,
                "identifiesControllerService": k in services, "sensitive": k in sensitive}
            for k in props}


def service(ident, name, typ, artifact, api, props, sensitive=()):
    return {
        "identifier": ident, "name": name, "type": typ, "componentType": "CONTROLLER_SERVICE",
        "bundle": {"group": "org.apache.nifi", "artifact": artifact, "version": VER},
        "controllerServiceApis": [{"type": api, "bundle": {"group": "org.apache.nifi",
                                   "artifact": "nifi-standard-services-api-nar", "version": VER}}],
        "groupIdentifier": PG_ID, "comments": "", "bulletinLevel": "WARN", "scheduledState": "ENABLED",
        "properties": props, "propertyDescriptors": descriptors(props, sensitive=sensitive),
    }


controller_services = [
    service(CS_HTTP, "StreamerBrainHttpContext", "org.apache.nifi.http.StandardHttpContextMap",
            "nifi-http-context-map-nar", "org.apache.nifi.http.HttpContextMap",
            {"Maximum Outstanding Requests": "100", "Request Expiration": "3 mins"}),
    service(CS_DBCP, "StreamersPostgres", "org.apache.nifi.dbcp.DBCPConnectionPool",
            "nifi-dbcp-service-nar", "org.apache.nifi.dbcp.DBCPService",
            {"Database Connection URL": "#{Postgres JDBC URL}",
             "Database Driver Class Name": "org.postgresql.Driver",
             "database-driver-locations": "#{Postgres Driver Jar}",
             "Database User": "#{Postgres User}",
             "Password": "#{Postgres Password}",
             "Max Wait Time": "5 secs", "Max Total Connections": "4",
             "Validation-query": "SELECT 1"}, sensitive=("Password",)),
    service(CS_JSONW, "IdentityJsonWriter", "org.apache.nifi.json.JsonRecordSetWriter",
            "nifi-record-serialization-services-nar", "org.apache.nifi.serialization.RecordSetWriterFactory",
            {"Schema Write Strategy": "no-schema", "schema-access-strategy": "inherit-record-schema",
             "Pretty Print JSON": "false", "suppress-nulls": "never-suppress",
             "output-grouping": "output-array"}),
]

# ── processors ────────────────────────────────────────────────────────────────
processors, connections = [], []


def proc(name, typ, bundle, x, y, props, auto=(), services=(), dynamic=(), run_ms=0, tasks=1):
    p = {
        "identifier": uid(name), "name": name, "type": typ, "bundle": bundle,
        "componentType": "PROCESSOR", "groupIdentifier": PG_ID, "comments": "",
        "position": {"x": float(x), "y": float(y)},
        "properties": props,
        "propertyDescriptors": {k: {"name": k, "displayName": k, "dynamic": k in dynamic,
                                    "identifiesControllerService": k in services, "sensitive": False}
                                for k in props},
        "autoTerminatedRelationships": list(auto),
        "schedulingPeriod": "0 sec", "schedulingStrategy": "TIMER_DRIVEN", "executionNode": "ALL",
        "penaltyDuration": "30 sec", "yieldDuration": "1 sec", "bulletinLevel": "WARN",
        "runDurationMillis": run_ms, "concurrentlySchedulableTaskCount": tasks,
        "scheduledState": "ENABLED", "retryCount": 10, "retriedRelationships": [],
        "backoffMechanism": "PENALIZE_FLOWFILE", "maxBackoffPeriod": "10 mins", "style": {},
    }
    processors.append(p)
    return p


def conn(src, rels, dst, expiration="0 sec"):
    s, d = uid(src), uid(dst)
    connections.append({
        "identifier": uid(f"conn:{src}:{','.join(rels)}:{dst}"), "name": "", "componentType": "CONNECTION",
        "groupIdentifier": PG_ID,
        "source": {"id": s, "type": "PROCESSOR", "groupId": PG_ID, "name": src, "comments": ""},
        "destination": {"id": d, "type": "PROCESSOR", "groupId": PG_ID, "name": dst, "comments": ""},
        "selectedRelationships": list(rels), "labelIndex": 1, "zIndex": 0, "bends": [],
        "backPressureObjectThreshold": 1000, "backPressureDataSizeThreshold": "1 GB",
        "flowFileExpiration": expiration, "prioritizers": [],
        "loadBalanceStrategy": "DO_NOT_LOAD_BALANCE", "loadBalanceCompression": "DO_NOT_COMPRESS",
    })


def invoke_http(name, x, y, url, content_type, read_timeout, auto=("Original",)):
    return proc(name, "org.apache.nifi.processors.standard.InvokeHTTP", STD, x, y, {
        "HTTP Method": "POST", "HTTP URL": url, "Request Content-Type": content_type,
        "Request Body Enabled": "true", "Connection Timeout": "10 secs",
        "Socket Read Timeout": read_timeout, "Socket Write Timeout": "60 secs",
        "Response Generation Required": "false", "Response Redirects Enabled": "True",
        "Request Failure Penalization Enabled": "false", "Request Date Header Enabled": "True",
        "Request Chunked Transfer-Encoding Enabled": "false", "Request Content-Encoding": "DISABLED",
        "Response Cookie Strategy": "DISABLED", "Response Cache Enabled": "false",
        "Response FlowFile Naming Strategy": "RANDOM", "HTTP/2 Disabled": "False",
    }, auto=auto)
    processors[-1]["penaltyDuration"] = "2 secs"   # a failed call answers the caller now, not after 30 s


def eval_json(name, x, y, paths, return_type="json"):
    props = {"Destination": "flowfile-attribute", "Return Type": return_type,
             "Path Not Found Behavior": "ignore", "Null Value Representation": "empty string",
             "Max String Length": "20 MB"}
    props.update(paths)
    return proc(name, "org.apache.nifi.processors.standard.EvaluateJsonPath", STD, x, y, props,
                dynamic=tuple(paths))


def replace_text(name, x, y, value, auto=()):
    return proc(name, "org.apache.nifi.processors.standard.ReplaceText", STD, x, y, {
        "Replacement Strategy": "Always Replace", "Evaluation Mode": "Entire text",
        "Regular Expression": "(?s)(^.*$)", "Replacement Value": value,
        "Character Set": "UTF-8", "Maximum Buffer Size": "10 MB", "Line-by-Line Evaluation Mode": "All",
    }, auto=auto, run_ms=25)


def update_attr(name, x, y, attrs):
    props = {"Delete Attributes Expression": None, "Store State": "Do not store state"}
    props.update(attrs)
    return proc(name, "org.apache.nifi.processors.attributes.UpdateAttribute", UPD, x, y, props,
                dynamic=tuple(attrs), run_ms=25)


# ── the door ──────────────────────────────────────────────────────────────────
proc("ReceiveClip", "org.apache.nifi.processors.standard.HandleHttpRequest", STD, 0, 0, {
    "Listening Port": "#{Door Port}", "Allowed Paths": "/caption",
    "Allow GET": "false", "Allow POST": "true", "Allow PUT": "false", "Allow DELETE": "false",
    "Allow HEAD": "false", "Allow OPTIONS": "false",
    "HTTP Context Map": CS_HTTP, "Maximum Threads": "20", "container-queue-size": "20",
    "Request Header Maximum Size": "16 KB", "multipart-request-max-size": "1 MB",
    "multipart-read-buffer-size": "512 KB", "Default URL Character Set": "UTF-8",
    "Client Authentication": "No Authentication", "HTTP Protocols": "HTTP_1_1",
}, services=("HTTP Context Map",))

update_attr("ExtractClipMeta", 0, 200, {
    "clip.id": "${'http.headers.X-Clip-Id'}",
    "clip.streamer": "${'http.headers.X-Streamer':toLower()}",
    "clip.source": "${'http.headers.X-Source':toLower()}",
    "clip.title": "${'http.headers.X-Title'}",
    "streamer.key": "${'http.headers.X-Source':toLower():equals('kick'):ifElse('kick:',''):append(${'http.headers.X-Streamer':toLower()})}",
    "sql.args.1.value": "${'http.headers.X-Source':toLower():equals('kick'):ifElse('kick:',''):append(${'http.headers.X-Streamer':toLower()})}",
    "sql.args.1.type": "12",
    "mime.type": "video/mp4",
    "Content-Type": "application/json",   # for the responders (HandleHttpResponse adds matching attributes as headers)
})

invoke_http("PrepClip", 0, 400, "#{Clip Prep URL}/prep?frames=#{Frames Per Clip}", "video/mp4", "5 mins")

eval_json("ExtractPrep", 0, 600, {
    "transcript": "$.transcript", "prep.duration": "$.duration", "prep.peak": "$.peak_audio_t",
    "prep.frame_urls": "$.frame_urls", "prep.image_parts": "$.image_parts",
})

proc("LookupIdentity", "org.apache.nifi.processors.standard.ExecuteSQLRecord", STD, 0, 800, {
    "Database Connection Pooling Service": CS_DBCP,
    "SQL Query": ("SELECT display_name, array_to_string(aliases, ', ') AS aliases, x_handle, "
                  "x_handle_confirmed, pronouns, pronouns_confirmed, notes "
                  "FROM streamer_brain WHERE streamer_key = ? AND active"),
    "esqlrecord-record-writer": CS_JSONW, "Max Wait Time": "10 secs", "esql-max-rows": "1",
}, services=("Database Connection Pooling Service", "esqlrecord-record-writer"))

eval_json("ExtractIdentity", 0, 1000, {
    "id.display_name": "$[0].display_name", "id.aliases": "$[0].aliases", "id.x_handle": "$[0].x_handle",
    "id.pronouns": "$[0].pronouns", "id.pronouns_confirmed": "$[0].pronouns_confirmed", "id.notes": "$[0].notes",
})

replace_text("BuildKbQuery", 0, 1200,
             '{"filter":{"must":[{"key":"streamer_key","match":{"value":"${streamer.key}"}}]},'
             '"limit":10,"with_payload":true,"with_vector":false}')

invoke_http("FetchStreamerKb", 0, 1400, "#{Qdrant URL}/collections/#{KB Collection}/points/scroll",
            "application/json", "30 secs")

eval_json("ExtractKb", 0, 1600, {"kb.points": "$.result.points[*].payload.text"})

SYSTEM_PROMPT = (
    "You write the X post for a clip from a live stream, as a cocky, trash-talking regular of the "
    "streamer's chat who was watching live. You are given who the streamer is (from our database), "
    "what we know about them (our knowledge base), the clip's transcript (Whisper), the stream title, "
    "and frames from the clip. Rules: 1) Everything you say must be grounded in the transcript or the "
    "frames — never invent what happened. 2) NOWHERE in your answer — caption, topic, visual_summary, "
    "anywhere — use a gendered pronoun (he/she/him/his/her) unless the identity block gives confirmed "
    "pronouns; otherwise use the name or 'they'. pronouns_ok means the WHOLE answer obeys this. "
    "3) A quote must be character-for-character verbatim from the transcript — never censor, star out, "
    "or paraphrase inside quotation marks; if you would have to censor it, do not quote it, and set "
    "quote_verbatim false if any quoted text differs from the transcript. "
    "4) Under 200 characters, one emoji, no hashtags, "
    "no links. 5) Use the stream title only if it is meaningful. 6) Never post something the knowledge "
    "base says to avoid. Answer with one JSON object: {\\\"caption\\\": str, \\\"topic\\\": str, "
    "\\\"confidence\\\": \\\"HIGH|MEDIUM|LOW\\\", \\\"grounded\\\": bool, \\\"quote_verbatim\\\": bool, "
    "\\\"pronouns_ok\\\": bool, \\\"used_title\\\": bool, \\\"visual_summary\\\": str}. "
    "visual_summary is two sentences on what the frames show. Nothing outside the JSON."
)

USER_TEXT = (
    "IDENTITY (database): name ${id.display_name:isEmpty():ifElse(${clip.streamer}, ${id.display_name}):escapeJson()}; "
    "login ${clip.streamer:escapeJson()} on ${clip.source:escapeJson()}; "
    "aliases: ${id.aliases:escapeJson()}; "
    "pronouns: ${id.pronouns:isEmpty():ifElse('NOT CONFIRMED - use the name only', ${id.pronouns}):escapeJson()}; "
    "notes: ${id.notes:escapeJson()}\\n\\n"
    "KNOWLEDGE BASE: ${kb.points:isEmpty():ifElse('(none)', ${kb.points}):escapeJson()}\\n\\n"
    "STREAM TITLE: ${clip.title:trim():length():lt(4):ifElse('(none)', ${clip.title}):escapeJson()}\\n\\n"
    "TRANSCRIPT (${prep.duration}s clip): ${transcript:isEmpty():ifElse('(no speech)', ${transcript}):escapeJson()}\\n\\n"
    "FRAMES: the images that follow are ${prep.frame_urls:isEmpty():ifElse('0', ${prep.frame_urls:replaceAll('[^,]', ''):length():plus(1)})} frames from the clip in time order."
)

replace_text("BuildBrainRequest", 0, 1800,
             '{"model":"#{LLM Model}","max_tokens":#{Max Tokens},"temperature":0.7,'
             '"chat_template_kwargs":{"enable_thinking":false},"response_format":{"type":"json_object"},'
             '"messages":[{"role":"system","content":"' + SYSTEM_PROMPT + '"},'
             '{"role":"user","content":[{"type":"text","text":"' + USER_TEXT + '"}'
             "${prep.image_parts:length():gt(2):ifElse(${prep.image_parts:substringAfter('['):substringBeforeLast(']'):prepend(',')}, '')}"
             ']}]}')

invoke_http("CallBrain", 0, 2000, "#{vLLM Base URL}/v1/chat/completions", "application/json", "3 mins")

eval_json("ExtractAnswer", 0, 2200, {"brain.answer": "$.choices[0].message.content",
                                     "brain.usage": "$.usage.total_tokens"})

replace_text("AnswerToContent", 0, 2400, "${brain.answer}")

eval_json("ExtractCaption", 0, 2600, {
    "brain.caption": "$.caption", "brain.pronouns_ok": "$.pronouns_ok", "brain.grounded": "$.grounded",
    "brain.visual_summary": "$.visual_summary", "brain.confidence": "$.confidence",
})

proc("CheckAnswer", "org.apache.nifi.processors.standard.RouteOnAttribute", STD, 0, 2800, {
    "Routing Strategy": "Route to Property name",
    "ok": "${brain.caption:isEmpty():not()}",
}, dynamic=("ok",))

replace_text("BuildResponse", 0, 3000,
             '{"clip_id":"${clip.id:escapeJson()}","streamer_key":"${streamer.key:escapeJson()}",'
             '"caption":"${brain.caption:escapeJson()}","brain":${brain.answer},'
             '"transcript":"${transcript:escapeJson()}","duration":"${prep.duration}",'
             '"frame_urls":${prep.frame_urls:isEmpty():ifElse(\'[]\', ${prep.frame_urls})},'
             '"identity":{"display_name":"${id.display_name:escapeJson()}","aliases":"${id.aliases:escapeJson()}",'
             '"pronouns":"${id.pronouns:escapeJson()}","pronouns_confirmed":"${id.pronouns_confirmed}","notes":"${id.notes:escapeJson()}"},'
             '"kb_points":${kb.points:isEmpty():ifElse(\'[]\', ${kb.points})},'
             '"brain_tokens":"${brain.usage}","brain_model":"#{LLM Model}"}')

proc("Respond200", "org.apache.nifi.processors.standard.HandleHttpResponse", STD, 0, 3200, {
    "HTTP Status Code": "200", "HTTP Context Map": CS_HTTP,
    "Attributes to add to the HTTP Response (Regex)": "Content-Type",
}, auto=("success",), services=("HTTP Context Map",))

# ── error column ──────────────────────────────────────────────────────────────
update_attr("MarkError", 300, 3000, {"mime.type": "application/json", "Content-Type": "application/json"})
replace_text("BuildErrorBody", 300, 3200,
             '{"error":"brain pipeline failure","clip_id":"${clip.id:escapeJson()}",'
             '"failed_at":"${invokehttp.request.url:escapeJson()}","status":"${invokehttp.status.code}","exception":"${invokehttp.java.exception.message:escapeJson()}",'
             '"caption":""}')
proc("Respond500", "org.apache.nifi.processors.standard.HandleHttpResponse", STD, 300, 3400, {
    "HTTP Status Code": "500", "HTTP Context Map": CS_HTTP,
    "Attributes to add to the HTTP Response (Regex)": "Content-Type",
}, services=("HTTP Context Map",))
proc("LogFailures", "org.apache.nifi.processors.standard.LogAttribute", STD, 300, 3600, {
    "Log Level": "warn", "Log Payload": "true", "Log FlowFile Properties": "true",
    "Output Format": "Line per Attribute", "attributes-to-log-regex": ".*", "character-set": "UTF-8",
}, auto=("success",))

# ── wiring (every destination at or below its source) ─────────────────────────
conn("ReceiveClip", ["success"], "ExtractClipMeta")
conn("ExtractClipMeta", ["success"], "PrepClip")
conn("PrepClip", ["Retry"], "PrepClip", "10 mins")
conn("PrepClip", ["Response"], "ExtractPrep")
conn("PrepClip", ["Failure", "No Retry"], "MarkError")
conn("ExtractPrep", ["matched"], "LookupIdentity")
conn("ExtractPrep", ["failure", "unmatched"], "MarkError")
conn("LookupIdentity", ["success"], "ExtractIdentity")
conn("LookupIdentity", ["failure"], "BuildKbQuery")          # no DB → name-only, keep going
conn("ExtractIdentity", ["matched", "unmatched", "failure"], "BuildKbQuery")
conn("BuildKbQuery", ["success"], "FetchStreamerKb")
conn("BuildKbQuery", ["failure"], "MarkError")
conn("FetchStreamerKb", ["Retry"], "FetchStreamerKb", "2 mins")
conn("FetchStreamerKb", ["Response"], "ExtractKb")
conn("FetchStreamerKb", ["Failure", "No Retry"], "BuildBrainRequest")   # no KB → keep going
conn("ExtractKb", ["matched", "unmatched", "failure"], "BuildBrainRequest")
conn("BuildBrainRequest", ["success"], "CallBrain")
conn("BuildBrainRequest", ["failure"], "MarkError")
conn("CallBrain", ["Retry"], "CallBrain", "10 mins")
conn("CallBrain", ["Response"], "ExtractAnswer")
conn("CallBrain", ["Failure", "No Retry"], "MarkError")
conn("ExtractAnswer", ["matched"], "AnswerToContent")
conn("ExtractAnswer", ["unmatched", "failure"], "MarkError")
conn("AnswerToContent", ["success"], "ExtractCaption")
conn("AnswerToContent", ["failure"], "MarkError")
conn("ExtractCaption", ["matched", "unmatched"], "CheckAnswer")
conn("ExtractCaption", ["failure"], "MarkError")
conn("CheckAnswer", ["ok"], "BuildResponse")
conn("CheckAnswer", ["unmatched"], "MarkError")
conn("BuildResponse", ["success"], "Respond200")
conn("BuildResponse", ["failure"], "MarkError")
conn("Respond200", ["failure"], "LogFailures")
conn("MarkError", ["success"], "BuildErrorBody")
conn("BuildErrorBody", ["success", "failure"], "Respond500")
conn("Respond500", ["success", "failure"], "LogFailures")

# ── parameter context ─────────────────────────────────────────────────────────
params = [
    ("Door Port", "8091", "HandleHttpRequest port inside mynifi-0; exposed by files/streamers/streamer-brain-door.yaml (NodePort 32111).", False),
    ("Clip Prep URL", "http://clip-prep.streamers.svc.cluster.local:8090", "The clip-prep pod (#282), in-cluster.", False),
    ("Frames Per Clip", "6", "Evenly spaced frames per clip (+1 at the audio peak, added by clip-prep).", False),
    ("vLLM Base URL", "http://192.168.1.203:8000", "The box's vLLM (docker, LAN-published); pods reach it at the LAN address.", False),
    ("LLM Model", "nvidia/Qwen3.6-35B-A3B-NVFP4", "The lead model; verified to take image_url on this build (2026-08-30).", False),
    ("Max Tokens", "400", "Answer budget; thinking is off.", False),
    ("Qdrant URL", "http://192.168.1.203:6333", "qdrant-kb (docker); the streamer-kb collection lives here.", False),
    ("KB Collection", "streamer-kb", "Per-streamer profile/guidance/prior points (#271 K2).", False),
    ("Postgres JDBC URL", "jdbc:postgresql://192.168.1.121:5432/streamers", "WindowsDesktop's streamers DB, LAN path (#276).", False),
    ("Postgres Driver Jar", "/opt/nifi/nifi-current/ext/jdbc/postgresql/postgresql-8.2-and-newer/postgresql-42.7.7.jar", "Ships in the CFM NiFi image.", False),
    ("Postgres User", "streamer_brain", "SELECT on the streamer_brain view only.", False),
    ("Postgres Password", None, "Sensitive — set via the API after upload from ~/.env STREAMER_BRAIN_DB_PASSWORD; never in this file.", True),
]

flow = {
    "flowEncodingVersion": "1.0", "latest": False,
    "externalControllerServices": {}, "parameterProviders": {},
    "parameterContexts": {PG_NAME: {
        "componentType": "PARAMETER_CONTEXT", "name": PG_NAME,
        "description": "Endpoints and the one credential the StreamerBrain PG uses (#272 / #271).",
        "inheritedParameterContexts": [],
        "parameters": [{"name": n, "value": v, "description": d, "sensitive": s, "provided": False}
                       for n, v, d, s in params],
    }},
    "flowContents": {
        "identifier": PG_ID, "name": PG_NAME, "componentType": "PROCESS_GROUP", "comments":
            "The Streamers demo's caption brain on the Spark (#272): MP4 in, one grounded JSON answer out. "
            "Streamers track — not part of the DGX guide.",
        "position": {"x": 0.0, "y": 0.0}, "parameterContextName": PG_NAME,
        "processors": processors, "connections": connections, "controllerServices": controller_services,
        "funnels": [], "inputPorts": [], "outputPorts": [], "labels": [], "processGroups": [],
        "remoteProcessGroups": [], "scheduledState": "ENABLED",
        "defaultFlowFileExpiration": "0 sec", "defaultBackPressureObjectThreshold": 10000,
        "defaultBackPressureDataSizeThreshold": "1 GB", "executionEngine": "INHERITED",
        "flowFileConcurrency": "UNBOUNDED", "flowFileOutboundPolicy": "STREAM_WHEN_AVAILABLE",
        "maxConcurrentTasks": 1, "statelessFlowTimeout": "1 min",
    },
}

if __name__ == "__main__":
    json.dump(flow, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}: {len(processors)} processors, {len(connections)} connections, "
          f"{len(controller_services)} services, {len(params)} parameters")
    ups = [(c["source"]["name"], c["destination"]["name"]) for c in connections
           if c["source"]["id"] != c["destination"]["id"]]
    pos = {p["name"]: p["position"] for p in processors}
    bad = [(s, d) for s, d in ups if pos[d]["y"] < pos[s]["y"]]
    print("connections routing upward:", bad or "none")
