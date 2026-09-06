#!/usr/bin/env python3
"""
Set Parameter Context values on the Spark's mynifi from ~/.env — the out-of-band step after a
flow-definition upload (the export carries sensitive parameters as null; skill flow-api.md §3).
Values never print; only the parameter names and the update-request state do.

Usage:
  set_params.py <context-name> 'Param Name=ENV_KEY' ['Other Param=OTHER_KEY' ...]
  set_params.py StreamerResearch 'Postgres Password=STREAMER_BRAIN_DB_PASSWORD' \
                                 'Twitch Client Id=TWITCH_CLIENT_ID' 'Twitch Client Secret=TWITCH_CLIENT_SECRET'
  set_params.py StreamerCard 'Dry Run=literal:false'      # literal:<value> for a non-secret value

Auth: the nifi-admin client cert in ~/nifi-admin-spark (CLAUDE-CHECKIN.md, NvidiaSpark-1 block).
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
        # NiFi's error body is plain text and never echoes a parameter value.
        sys.exit(f"{method} {path} -> HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")


def load_env():
    env = {}
    for line in open(os.path.expanduser("~/.env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    name, pairs = sys.argv[1], sys.argv[2:]
    env = load_env()
    contexts = call("GET", "/flow/parameter-contexts")["parameterContexts"]
    match = [c for c in contexts if c["component"]["name"] == name]
    if not match:
        sys.exit(f"no Parameter Context named {name!r}")
    pc_id = match[0]["id"]
    full = call("GET", f"/parameter-contexts/{pc_id}")
    existing = {p["parameter"]["name"]: p["parameter"] for p in full["component"]["parameters"]}
    params = []
    for pair in pairs:
        pname, key = pair.split("=", 1)
        if pname not in existing:
            sys.exit(f"{name!r} has no parameter {pname!r}")
        if key.startswith("literal:"):
            value = key[len("literal:"):]
        elif key in env:
            value = env[key]
        else:
            sys.exit(f"~/.env has no {key} (needed for {pname!r})")
        params.append({"parameter": {"name": pname, "sensitive": existing[pname]["sensitive"], "value": value}})
    req = call("POST", f"/parameter-contexts/{pc_id}/update-requests", {
        "revision": full["revision"], "id": pc_id,
        "component": {"id": pc_id, "parameters": params},     # a ParameterContextEntity
    })
    rid = req["request"]["requestId"]
    for _ in range(60):
        st = call("GET", f"/parameter-contexts/{pc_id}/update-requests/{rid}")["request"]
        if st.get("complete"):
            break
        time.sleep(1)
    call("DELETE", f"/parameter-contexts/{pc_id}/update-requests/{rid}")
    if st.get("failureReason"):
        sys.exit(f"update failed: {st['failureReason']}")
    print(f"{name}: set {', '.join(p['parameter']['name'] for p in params)} "
          f"(state: {st.get('state')}, complete: {st.get('complete')})")


if __name__ == "__main__":
    main()
