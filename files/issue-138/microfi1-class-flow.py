#!/usr/bin/env python3
"""MicroFi-1 class-flow swap via EFM Flow Designer API (#138 actuation re-confirm).

    python3 microfi1-class-flow.py show
    python3 microfi1-class-flow.py clear
    python3 microfi1-class-flow.py build <spec>     # led | json-emit
    python3 microfi1-class-flow.py publish "<comment>"

Functions copied verbatim from files/issue-191/amoled-class-flow.py (the
reverse-engineered Designer API contract); only EFM host, CLASS, and SPECS
changed. led = files/issue-164/microfi3-led-flow-backup.json shape;
json-emit = the live MicroFi-1 flow dumped 2026-09-01 for restore
(scratchpad/microfi1-live-flow-backup.json).
"""
import json
import sys
import urllib.request
import urllib.error
import uuid

EFM = "http://192.168.1.121:10090/efm/api"
CLASS = "MicroFi-1"
BUNDLE = {"group": "org.apache.nifi", "artifact": "microfi-system", "version": "0.1.0"}
BROKER = "mqtt://192.168.1.121:1883"

SPECS = {
    "led": {
        "processors": [
            {"key": "http", "type": "ListenHTTP", "pos": (400, 100),
             "props": {"Base Path": "/led", "Listening Port": "8095"}, "auto": []},
            {"key": "gpio", "type": "SetGPIO", "pos": (400, 400),
             "props": {"Invert": "true", "GPIO Pin": "21", "Pin Level": "from-content"},
             "auto": ["success"]},
        ],
        "connections": [("http", "gpio")],
    },
    "json-emit": {
        "processors": [
            {"key": "trig", "type": "ListenHTTP", "pos": (800, 100),
             "props": {"Base Path": "/test", "Listening Port": "8095"},
             "auto": ["success"]},
            {"key": "gen", "type": "GenerateFlowFile", "pos": (100, 100),
             "props": {"File Size": "64 B", "Batch Size": "1",
                       "Unique FlowFiles": "false",
                       "Custom Text": "{\"device_id\":\"MicroFi-1\"}",
                       "Data Format": "Text"},
             "auto": []},
            {"key": "mqtt", "type": "PublishMQTT", "pos": (100, 400),
             "props": {"Broker URI": BROKER, "Client ID": "xiao-microfi-sparkplug",
                       "Topic": "test/sensor/data", "Quality of Service": "0"},
             "auto": ["success"]},
        ],
        "connections": [("gen", "mqtt")],
    },
}


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(EFM + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def flow_ids():
    _, summaries = call("GET", "/designer/flows/summaries")
    for e in (summaries["elements"] if isinstance(summaries, dict) else summaries):
        if e.get("agentClass") == CLASS:
            return e["identifier"], e["rootProcessGroupIdentifier"]
    raise SystemExit(f"no designer flow for class {CLASS}")


def client_id():
    _, r = call("GET", "/designer/client-identifier")
    return r["clientId"]


def show(flow):
    _, d = call("GET", f"/designer/flows/{flow}")
    fc = d["flowContent"]
    for p in fc.get("processors", []):
        print("PROC", p["identifier"], p["type"], json.dumps({k: v for k, v in p["properties"].items() if v}),
              p.get("autoTerminatedRelationships"))
    for c in fc.get("connections", []):
        print("CONN", c["identifier"], c["source"]["id"], "->", c["destination"]["id"], c["selectedRelationships"])
    return fc


def clear(flow, cid):
    fc = show(flow)
    for c in fc.get("connections", []):
        _, ent = call("GET", f"/designer/flows/{flow}/connections/{c['identifier']}")
        ver = ent["revision"]["version"]
        st, _ = call("DELETE", f"/designer/flows/{flow}/connections/{c['identifier']}?version={ver}&clientId={cid}")
        print("del conn", c["identifier"], st)
    for p in fc.get("processors", []):
        _, ent = call("GET", f"/designer/flows/{flow}/processors/{p['identifier']}")
        ver = ent["revision"]["version"]
        st, _ = call("DELETE", f"/designer/flows/{flow}/processors/{p['identifier']}?version={ver}&clientId={cid}")
        print("del proc", p["type"], st)


def build(flow, pg, cid, spec):
    ids = {}
    for p in spec["processors"]:
        body = {
            "revision": {"version": 0, "clientId": cid},
            "componentConfiguration": {
                "componentType": "PROCESSOR", "type": p["type"], "bundle": BUNDLE,
                "name": p["type"], "position": {"x": float(p["pos"][0]), "y": float(p["pos"][1])},
                "properties": p["props"], "autoTerminatedRelationships": p["auto"],
            },
            "requestId": str(uuid.uuid4()),
        }
        st, r = call("POST", f"/designer/flows/{flow}/process-groups/{pg}/processors", body)
        if st != 201:
            raise SystemExit(f"create {p['type']}: {st} {r}")
        ids[p["key"]] = r["componentConfiguration"]["identifier"]
        print("created", p["type"], ids[p["key"]])
    for a, b in spec["connections"]:
        body = {
            "revision": {"version": 0, "clientId": cid},
            "componentConfiguration": {
                "componentType": "CONNECTION",
                "source": {"id": ids[a], "type": "PROCESSOR", "groupId": pg},
                "destination": {"id": ids[b], "type": "PROCESSOR", "groupId": pg},
                "selectedRelationships": ["success"], "bends": [],
            },
            "requestId": str(uuid.uuid4()),
        }
        st, r = call("POST", f"/designer/flows/{flow}/process-groups/{pg}/connections", body)
        print("connect", a, "->", b, st if st == 201 else r)
    st, v = call("GET", f"/designer/flows/{flow}/validate")
    print("validate", st, v)


def publish(flow, comment):
    st, r = call("POST", f"/designer/flows/{flow}/publish", {"comments": comment})
    print("publish", st, json.dumps(r)[:300] if r else r)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    flow, pg = flow_ids()
    if cmd == "show":
        show(flow)
    elif cmd == "clear":
        clear(flow, client_id())
    elif cmd == "build":
        build(flow, pg, client_id(), SPECS[sys.argv[2]])
    elif cmd == "publish":
        publish(flow, sys.argv[2] if len(sys.argv) > 2 else "#138")
    else:
        raise SystemExit(__doc__)
