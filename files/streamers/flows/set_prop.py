#!/usr/bin/env python3
"""
Change ONE non-sensitive property on a live processor, the safe way (skill flow-api.md §5):
run-status STOPPED → PUT with only that property → run-status RUNNING. Never a full-entity
GET-then-PUT. Refuses if the named property is sensitive.

  set_prop.py <pg-name> <processor-name> 'Property Name=value' ['Other=value' ...]
  set_prop.py StreamerResearch UpsertPoint 'Socket Idle Timeout=1 sec'
"""
import json
import os
import ssl
import sys
import time
import urllib.request

NIFI = "https://mynifi-web.mynifi.cfm-streaming.svc.cluster.local/nifi-api"
CERT_DIR = os.path.expanduser("~/nifi-admin-spark")


def ctx():
    c = ssl.create_default_context(cafile=f"{CERT_DIR}/ca.crt")
    c.load_cert_chain(f"{CERT_DIR}/admin.crt", f"{CERT_DIR}/admin.key")
    return c


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(NIFI + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx(), timeout=30) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")


def main():
    pg_name, proc_name, pairs = sys.argv[1], sys.argv[2], sys.argv[3:]
    pgs = call("GET", "/process-groups/root/process-groups")["processGroups"]
    pg = [p for p in pgs if p["component"]["name"] == pg_name]
    if not pg:
        sys.exit(f"no root PG named {pg_name!r}")
    procs = call("GET", f"/flow/process-groups/{pg[0]['id']}")["processGroupFlow"]["flow"]["processors"]
    proc = [p for p in procs if p["component"]["name"] == proc_name]
    if not proc:
        sys.exit(f"no processor named {proc_name!r} in {pg_name}")
    pid = proc[0]["id"]
    ent = call("GET", f"/processors/{pid}")
    desc = ent["component"]["config"]["descriptors"]
    props = {}
    for pair in pairs:
        k, v = pair.split("=", 1)
        if k in desc and desc[k].get("sensitive"):
            sys.exit(f"{k!r} is sensitive — bind it to a Parameter Context instead")
        props[k] = v
    was_running = ent["component"]["state"] == "RUNNING"
    if was_running:
        call("PUT", f"/processors/{pid}/run-status", {"revision": ent["revision"], "state": "STOPPED"})
        for _ in range(30):
            time.sleep(1)
            ent = call("GET", f"/processors/{pid}")
            if ent["status"]["aggregateSnapshot"]["activeThreadCount"] == 0 and ent["component"]["state"] == "STOPPED":
                break
    ent = call("PUT", f"/processors/{pid}", {"revision": ent["revision"],
                                            "component": {"id": pid, "config": {"properties": props}}})
    print(f"{pg_name}/{proc_name}: set {props} -> {ent['component'].get('validationStatus')}")
    if was_running:
        call("PUT", f"/processors/{pid}/run-status", {"revision": ent["revision"], "state": "RUNNING"})
        print("  restarted")


if __name__ == "__main__":
    main()
