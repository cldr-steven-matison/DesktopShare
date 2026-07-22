#!/usr/bin/env python3
"""
Adds 4 new ListenHTTP -> [EvaluateJsonPath ->] InvokeHTTP pairs to the live
StarlinkAI EFM flow, exposing Lemonade's embeddings/reranking/TTS/transcription
endpoints the same way chat/completions is already exposed. Run this FROM
MINI-Gaming-G1 (WindowsDesktop), where the EFM server is local -- see
beelink-starlink-efm-ai.md "Handoff to WindowsDesktop" section for the full
story and why this wasn't done from the Beelink itself.

Usage:
    python3 agent-WindowsDesktop-efm-add-starlinkai-endpoints.py [--dry-run] [--efm-host HOST]

Defaults to --efm-host 127.0.0.1 (EFM is local on this box, per the
2026-07-21 check-in doc). Pass --efm-host 100.68.113.126 if running this
from elsewhere.

WHAT THIS DOES NOT KNOW FOR CERTAIN (verify before trusting the result):
- The exact PUT/publish contract of the EFM designer API. GET was confirmed
  working from the Beelink on 2026-07-21; PUT was never actually executed
  (an unmodified round-trip PUT was attempted and blocked by an unrelated
  Claude Code permission gate before getting a response). This script's PUT
  step is my best-effort construction from NiFi/EFM's usual versioned-flow
  shape (echo back flowMetadata/parameterContexts/versionInfo/
  localFlowRevision as received). If it 4xxs, that's real information --
  stop and check the EFM UI's own network calls (browser devtools, Publish
  button) for the actual contract rather than guessing further.
- Whether a POST .../publish (or similar) step is required after the PUT
  to push the change to the running StarlinkAI agent, or whether saving the
  flow content alone is enough. The script attempts a publish call and
  prints clearly whether it succeeded, failed, or wasn't found (404) --
  in the 404 case, use the EFM UI's Publish button manually, don't guess
  at alternate endpoint names.
- Whether InvokeHTTP's "Content-type" property forwards correctly for the
  transcription pair. That processor's incoming request is multipart/
  form-data with a boundary in the Content-Type header; hardcoding
  "application/json" (like the existing chat pair does) would corrupt it.
  This script sets it to "${mime.type}" instead, betting that MiNiFi's
  ListenHTTP sets that attribute from the incoming Content-Type header the
  same way NiFi's does -- UNCONFIRMED. Test with a real audio file POST
  before trusting this pair; if it's wrong, the fix is that one property.

Safe to re-run: checks for existing processor names before adding, so a
partial or repeat run won't duplicate processors.
"""
import argparse
import json
import urllib.request
import urllib.error
import uuid

AGENT_CLASS = "StarlinkAI"
LEMONADE_BASE = "http://localhost:13305/api/v1"

# (name_suffix, port, base_path, remote_path, needs_json_path_extraction, listen_http_header_capture)
NEW_ENDPOINTS = [
    ("Embeddings", 8081, "embeddings", "/embeddings", True, None),
    ("Reranking", 8082, "reranking", "/reranking", True, None),
    ("Speech", 8083, "speech", "/audio/speech", True, None),
    # Transcription: multipart body, no top-level JSON to path into -- caller
    # sends `request_id` as an HTTP header instead, captured directly as a
    # FlowFile attribute (no EvaluateJsonPath needed for this one).
    ("Transcription", 8084, "transcriptions", "/audio/transcriptions", False, "request_id"),
]


def http_json(method, url, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode("utf-8", errors="replace")


def find_flow_id(base):
    status, flows = http_json("GET", f"{base}/efm/api/designer/flows?agentClass={AGENT_CLASS}")
    if status != 200:
        raise SystemExit(f"Could not list flows for {AGENT_CLASS}: HTTP {status} {flows}")
    for f in flows["elements"]:
        if f["agentClass"] == AGENT_CLASS:
            return f["identifier"]
    raise SystemExit(f"No flow found for agent class {AGENT_CLASS}")


def new_listen_http(group_id, name, port, base_path, header_capture, pos):
    return {
        "identifier": str(uuid.uuid4()),
        "instanceIdentifier": str(uuid.uuid4()),
        "name": f"ListenHTTP-{name}",
        "comments": "",
        "position": pos,
        "type": "org.apache.nifi.minifi.processors.ListenHTTP",
        "bundle": {"group": "org.apache.nifi.minifi", "artifact": "minifi-civet-extensions", "version": "1.26.02"},
        "properties": {
            "Base Path": base_path,
            "SSL Verify Peer": "no",
            "Batch Size": "1",
            "SSL Minimum Version": "TLS1.2",
            "Buffer Size": "1",
            "Listening Port": str(port),
            "SSL Certificate": None,
            "HTTP Headers to receive as Attributes (Regex)": header_capture,
            "Authorized DN Pattern": ".*",
            "SSL Certificate Authority": None,
        },
        "style": {},
        "annotationData": None,
        "schedulingPeriod": "1000 ms",
        "schedulingStrategy": "TIMER_DRIVEN",
        "executionNode": "ALL",
        "penaltyDuration": "30000 ms",
        "yieldDuration": "1000 ms",
        "bulletinLevel": "WARN",
        "runDurationMillis": 0,
        "concurrentlySchedulableTaskCount": 1,
        "autoTerminatedRelationships": [],
        "scheduledState": None,
        "retryCount": None,
        "retriedRelationships": None,
        "backoffMechanism": None,
        "maxBackoffPeriod": None,
        "componentType": "PROCESSOR",
        "groupIdentifier": group_id,
    }


def new_evaluate_json_path(group_id, name, pos):
    return {
        "identifier": str(uuid.uuid4()),
        "instanceIdentifier": str(uuid.uuid4()),
        "name": f"EvaluateJsonPath-{name}",
        "comments": "",
        "position": pos,
        "type": "org.apache.nifi.minifi.processors.EvaluateJsonPath",
        "bundle": {"group": "org.apache.nifi.minifi", "artifact": "minifi-standard-processors", "version": "1.26.02"},
        "properties": {
            "Destination": "flowfile-attribute",
            "Return Type": "auto-detect",
            "Null Value Representation": "empty string",
            "Path Not Found Behavior": "ignore",
            "request_id": "$.request_id",
        },
        "style": {},
        "annotationData": None,
        "schedulingPeriod": "0 sec",
        "schedulingStrategy": "TIMER_DRIVEN",
        "executionNode": "ALL",
        "penaltyDuration": "30000 ms",
        "yieldDuration": "1000 ms",
        "bulletinLevel": "WARN",
        "runDurationMillis": 0,
        "concurrentlySchedulableTaskCount": 1,
        "autoTerminatedRelationships": [],
        "scheduledState": None,
        "retryCount": None,
        "retriedRelationships": None,
        "backoffMechanism": None,
        "maxBackoffPeriod": None,
        "componentType": "PROCESSOR",
        "groupIdentifier": group_id,
    }


def new_invoke_http(group_id, name, remote_url, content_type, pos):
    return {
        "identifier": str(uuid.uuid4()),
        "instanceIdentifier": str(uuid.uuid4()),
        "name": f"InvokeHTTP-{name}",
        "comments": "",
        "position": pos,
        "type": "org.apache.nifi.minifi.processors.InvokeHTTP",
        "bundle": {"group": "org.apache.nifi.minifi", "artifact": "minifi-standard-processors", "version": "1.26.02"},
        "properties": {
            "Proxy Host": None,
            "Upload Speed Limit": None,
            "Attributes to Send": "request_id",
            "Invalid HTTP Header Field Handling Strategy": "transform",
            "Download Speed Limit": None,
            "Read Timeout": "10 min",
            "invokehttp-proxy-password": None,
            "Send Message Body": "true",
            "Proxy Port": None,
            "invokehttp-proxy-username": None,
            "Put Response Body in Attribute": None,
            "Connection Timeout": "5 min",
            "send-message-body": "true",
            "Content-type": content_type,
            "SSL Context Service": None,
            "Always Output Response": "false",
            "HTTP Method": "POST",
            "Include Date Header": "true",
            "Use Chunked Encoding": "false",
            "Disable Peer Verification": "false",
            "Penalize on \"No Retry\"": "false",
            "Follow Redirects": "true",
            "Remote URL": remote_url,
        },
        "style": {},
        "annotationData": None,
        "schedulingPeriod": "0 sec",
        "schedulingStrategy": "TIMER_DRIVEN",
        "executionNode": "ALL",
        "penaltyDuration": "30000 ms",
        "yieldDuration": "1000 ms",
        "bulletinLevel": "WARN",
        "runDurationMillis": 0,
        "concurrentlySchedulableTaskCount": 1,
        # Deliberately auto-terminate failure/retry/no-retry here rather than
        # wiring into the existing debug funnel -- that funnel is already
        # flagged for removal (see Next Steps item 3 in the doc), no sense
        # growing it by 4x right before it's torn out.
        "autoTerminatedRelationships": ["failure", "retry", "no retry"],
        "scheduledState": None,
        "retryCount": None,
        "retriedRelationships": None,
        "backoffMechanism": None,
        "maxBackoffPeriod": None,
        "componentType": "PROCESSOR",
        "groupIdentifier": group_id,
    }


def connection(group_id, source, dest, relationships, pos_bend=None):
    return {
        "identifier": str(uuid.uuid4()),
        "instanceIdentifier": str(uuid.uuid4()),
        "name": "",
        "source": {"id": source["identifier"], "type": "PROCESSOR", "groupId": group_id},
        "destination": {"id": dest["identifier"], "type": "PROCESSOR", "groupId": group_id},
        "selectedRelationships": relationships,
        "bendPoints": pos_bend or [],
        "labelIndex": 1,
        "zIndex": 0,
        "flowFileExpiration": "0 sec",
        "backPressureObjectThreshold": 10000,
        "backPressureDataSizeThreshold": "1 GB",
        "prioritizers": [],
        "componentType": "CONNECTION",
        "groupIdentifier": group_id,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--efm-host", default="127.0.0.1")
    ap.add_argument("--efm-port", default="10090")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = f"http://{args.efm_host}:{args.efm_port}"

    flow_id = find_flow_id(base)
    status, flow = http_json("GET", f"{base}/efm/api/designer/flows/{flow_id}")
    if status != 200:
        raise SystemExit(f"Could not fetch flow {flow_id}: HTTP {status}")

    fc = flow["flowContent"]
    group_id = fc["identifier"]
    existing_names = {p["name"] for p in fc["processors"]}

    # PublishKafka is the shared sink every new InvokeHTTP's success/response
    # routes into, same as the existing chat pair -- request_id already
    # disambiguates responses on the consumer side, no need for new topics.
    publish_kafka = next(p for p in fc["processors"] if p["type"].endswith("PublishKafka"))

    added_processors = []
    added_connections = []
    y_offset = -700  # existing processors cluster around y ~ -466 to -200; stack new ones below

    for idx, (name, port, base_path, remote_path, needs_json_path, header_capture) in enumerate(NEW_ENDPOINTS):
        if f"ListenHTTP-{name}" in existing_names:
            print(f"[skip] ListenHTTP-{name} already present, not re-adding")
            continue

        y = y_offset + idx * 250
        listen = new_listen_http(group_id, name, port, base_path, header_capture, {"x": -600, "y": y})
        invoke = new_invoke_http(
            group_id, name, f"{LEMONADE_BASE}{remote_path}",
            "${mime.type}" if name == "Transcription" else "application/json",
            {"x": 0, "y": y},
        )
        added_processors += [listen, invoke]

        if needs_json_path:
            eval_json = new_evaluate_json_path(group_id, name, {"x": -300, "y": y})
            added_processors.append(eval_json)
            added_connections.append(connection(group_id, listen, eval_json, ["success"]))
            added_connections.append(connection(group_id, eval_json, invoke, ["matched"]))
        else:
            added_connections.append(connection(group_id, listen, invoke, ["success"]))

        added_connections.append(connection(group_id, invoke, publish_kafka, ["success", "response"]))

        print(f"[add] {name}: ListenHTTP :{port}/{base_path} -> "
              f"{'EvaluateJsonPath -> ' if needs_json_path else ''}InvokeHTTP -> {remote_path} -> PublishKafka")

    if not added_processors:
        print("Nothing to add -- all 4 pairs already present.")
        return

    fc["processors"] += added_processors
    fc["connections"] += added_connections

    if args.dry_run:
        print("\n--dry-run: not writing. New processor names:")
        for p in added_processors:
            print(" -", p["name"])
        return

    put_status, put_result = http_json("PUT", f"{base}/efm/api/designer/flows/{flow_id}", flow)
    print(f"\nPUT flow: HTTP {put_status}")
    if put_status not in (200, 201, 204):
        print("PUT failed -- flow NOT modified on the server side (or modification unconfirmed).")
        print("Response:", put_result)
        print("Stop here. Check the EFM UI directly before retrying; do not guess at a different endpoint shape.")
        return

    # Publish step is a guess -- confirm this is the right path via the EFM
    # UI's own network calls if it 404s.
    pub_status, pub_result = http_json("POST", f"{base}/efm/api/designer/flows/{flow_id}/publish",
                                        {"comments": "Add embeddings/reranking/speech/transcription endpoints"})
    print(f"POST publish: HTTP {pub_status}")
    if pub_status == 404:
        print("No /publish endpoint at that path -- flow content was saved (if the PUT above succeeded) "
              "but likely NOT yet pushed live to the StarlinkAI agent. Open the EFM UI and click Publish "
              "manually to complete this.")
    elif pub_status not in (200, 201, 204):
        print("Publish call failed:", pub_result)
    else:
        print("Published. Verify in the EFM UI that StarlinkAI shows the new processors and is not in a "
              "'stale'/pending-publish state, then run the curl verification steps in the doc.")


if __name__ == "__main__":
    main()
