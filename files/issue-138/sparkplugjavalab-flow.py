#!/usr/bin/env python3
"""SparkplugJavaLab class flow via EFM Flow Designer API (#138 / #248 live-verify).

    python3 sparkplugjavalab-flow.py show | clear | build publish | publish "<comment>"

Contract functions verbatim from files/issue-191/amoled-class-flow.py.
Flow: GenerateFlowFile (flat JSON metrics, 5 s) -> PublishSparkplug
(tcp://mosquitto.mqtt.svc:1883, group SparkplugLab, node MiNiFi-Java-1).
EFM Designer pitch: vertical chain, row 300.
"""
import json
import sys
import urllib.request
import urllib.error
import uuid

EFM = "http://192.168.1.121:10090/efm/api"
CLASS = "SparkplugJavaLab"

STD_BUNDLE = {"group": "org.apache.nifi.minifi", "artifact": "minifi-standard-nar",
              "version": "2.24.08.0-19"}
SPB_BUNDLE = {"group": "com.example", "artifact": "nifi-sparkplug-nar",
              "version": "1.0.0-SNAPSHOT"}

METRICS = '{"Sensors/Temperature": 22.5, "Sensors/Count": 1013, "Sensors/Online": true}'

SPECS = {
    "publish": {
        "processors": [
            {"key": "gen", "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
             "bundle": STD_BUNDLE, "pos": (300, 100), "sched": "5000 ms",
             "props": {"generate-ff-custom-text": METRICS, "File Size": "0B",
                       "Batch Size": "1", "Data Format": "Text",
                       "Unique FlowFiles": "false"},
             "auto": []},
            {"key": "spb", "type": "com.example.processors.sparkplug.PublishSparkplug",
             "bundle": SPB_BUNDLE, "pos": (300, 400), "sched": "1000 ms",
             "props": {"broker-uri": "tcp://mosquitto.mqtt.svc:1883",
                       "client-id": "sparkplug-lab-1",
                       "group-id": "SparkplugLab",
                       "edge-node-id": "MiNiFi-Java-1",
                       "qos": "0"},
             "auto": ["success", "failure"]},
        ],
        "connections": [("gen", "spb")],
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
                "componentType": "PROCESSOR", "type": p["type"], "bundle": p["bundle"],
                "name": p["type"].rsplit(".", 1)[-1],
                "position": {"x": float(p["pos"][0]), "y": float(p["pos"][1])},
                "properties": p["props"], "autoTerminatedRelationships": p["auto"],
                "schedulingPeriod": p.get("sched", "1000 ms"),
                "schedulingStrategy": "TIMER_DRIVEN",
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
        publish(flow, sys.argv[2] if len(sys.argv) > 2 else "#138/#248")
    else:
        raise SystemExit(__doc__)
