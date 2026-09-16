#!/usr/bin/env python3
"""Ch18 LLM bridge on the CE NiFi (issue #341), built through Knox cdp-proxy-api.

GenerateFlowFile -> InvokeHTTP (POST /v1/chat/completions on the DGX Spark model, reached through
the reverse SSH tunnel at 127.0.0.1:8000 on every NiFi node) -> PublishKafka (SASL_SSL, Kerberos)
Failures and the published responses land on LogAttribute processors; Retry self-loops with a 10 min expiry.

Usage (from the DGX Spark):  python3 build-flow.py build|start|status|stop|export|delete
Creds: admin / common_password from ~/cloudera-ce-aws/config-srm-base.yml (never printed).
"""
import json, re, sys, time, uuid, os
import urllib3, requests
urllib3.disable_warnings()

CE = "/home/tunas/cloudera-ce-aws"
GW = os.environ.get("CE_GATEWAY_IP", "16.58.47.72")
K = f"https://knox.{GW}.nip.io/gateway/cdp-proxy-api/nifi-app/nifi-api"
PW = re.search(r'common_password:\s*"([^"]+)"', open(f"{CE}/config-srm-base.yml").read()).group(1)
OUT = "/home/tunas/BrainShare/files/issue-341"
PG_NAME = "Ch18LlmBridge"
PARAMS = {
    "LLM Base URL": "http://127.0.0.1:8000",
    "LLM Model": "nvidia/Qwen3.6-35B-A3B-NVFP4",
    "Kafka Bootstrap": ",".join(f"srm-cloudera-ce-base-base-worker-0{i}.cldr.internal:9093" for i in range(1, 5)),
    "Kafka Topic": "ch18-llm-responses",
}
PROMPT_BODY = json.dumps({
    "model": "#{LLM Model}",
    "messages": [{"role": "user", "content": "In one sentence, what is Apache NiFi? Reply as plain text."}],
    "max_tokens": 2048, "temperature": 0.2,
})

s = requests.Session(); s.auth = ("admin", PW); s.verify = False
CLIENT = str(uuid.uuid4())

def tok():
    if "Request-Token" not in s.headers:
        s.get(f"{K}/flow/current-user")
        t = s.cookies.get("__Secure-Request-Token")
        if t: s.headers["Request-Token"] = t
def api(method, path, body=None, **kw):
    tok()
    r = s.request(method, f"{K}{path}", json=body, **kw)
    if r.status_code >= 300:
        raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text[:600]}")
    return r.json() if r.text and r.headers.get("content-type", "").startswith("application/json") else r.text
def rev(ver=0): return {"clientId": CLIENT, "version": ver}
def root(): return api("GET", "/flow/process-groups/root")["processGroupFlow"]["id"]
def find_pg():
    for p in api("GET", "/process-groups/root/process-groups")["processGroups"]:
        if p["component"]["name"] == PG_NAME: return p
def find_ctx():
    for p in api("GET", "/flow/parameter-contexts")["parameterContexts"]:
        if p["component"]["name"] == PG_NAME: return p

def set_props(kind, ent, props, extra=None):
    """PUT only the named properties (plus optional component fields) on a fresh revision."""
    ent = api("GET", f"/{kind}/{ent['id']}")
    comp = {"id": ent["id"]}
    if kind == "processors":
        comp["config"] = {"properties": props}
        if extra: comp["config"].update(extra)
    else:
        comp["properties"] = props
        if extra: comp.update(extra)
    return api("PUT", f"/{kind}/{ent['id']}", {"revision": ent["revision"], "component": comp})

def descriptors(kind, cid):
    return api("GET", f"/{kind}/{cid}")["component"]["descriptors"] if kind == "controller-services" \
        else api("GET", f"/{kind}/{cid}")["component"]["config"]["descriptors"]
def prop_name(kind, cid, *cands):
    d = descriptors(kind, cid)
    for c in cands:
        if c in d: return c
    low = {k.lower(): k for k in d}
    for c in cands:
        if c.lower() in low: return low[c.lower()]
    raise SystemExit(f"none of {cands} in {kind}/{cid}; have: {sorted(d)}")

def build():
    if find_pg(): raise SystemExit(f"{PG_NAME} already exists; run delete first")
    ctx = find_ctx()
    if not ctx:
        ctx = api("POST", "/parameter-contexts", {"revision": rev(), "component": {"name": PG_NAME,
            "description": "Ch18 LLM bridge (issue #341)",
            "parameters": [{"parameter": {"name": k, "value": v, "sensitive": False}} for k, v in PARAMS.items()]}})
    print("parameter context", ctx["id"])
    # place the PG to the right of the existing srm-smoke PG (new work goes right of existing canvas)
    xs = [p["position"]["x"] for p in api("GET", "/process-groups/root/process-groups")["processGroups"]]
    px = (max(xs) if xs else 0) + 600
    pg = api("POST", f"/process-groups/{root()}/process-groups", {"revision": rev(),
        "component": {"name": PG_NAME, "position": {"x": px, "y": 0}, "parameterContext": {"id": ctx["id"]}}})
    pid = pg["id"]; print("pg", pid, "at x", px)

    def svc(type_, bundle, name):
        e = api("POST", f"/process-groups/{pid}/controller-services", {"revision": rev(), "component": {
            "type": type_, "bundle": {"group": "org.apache.nifi", "artifact": bundle, "version": "2.3.0.4.10.0.0-154"}, "name": name}})
        print("service", name, e["id"]); return e
    ssl = svc("org.apache.nifi.ssl.PEMEncodedSSLContextProvider", "nifi-ssl-context-service-nar", "CM AutoTLS CA (PEM)")
    d = descriptors("controller-services", ssl["id"]); print("  ssl descriptors:", sorted(d))
    ssl_props = {}
    for k in d:
        kl = k.lower()
        if "authorit" in kl and "source" in kl: ssl_props[k] = "FILES"
        if "authorit" in kl and ("location" in kl or "path" in kl or "file" in kl): ssl_props[k] = "/var/lib/cloudera-scm-agent/agent-cert/cm-auto-global_cacerts.pem"
        if "private" in kl and "source" in kl: ssl_props[k] = "UNDEFINED"
    print("  ssl props:", ssl_props); set_props("controller-services", ssl, ssl_props)

    krb = svc("org.apache.nifi.kerberos.KerberosKeytabUserService", "nifi-kerberos-user-service-nar", "NiFi service keytab (per node)")
    d = descriptors("controller-services", krb["id"]); print("  krb descriptors:", {k: v.get("expressionLanguageScope") for k, v in d.items()})
    set_props("controller-services", krb, {
        prop_name("controller-services", krb["id"], "Kerberos Principal"): "nifi/${hostname(true)}@CLDR.INTERNAL",
        prop_name("controller-services", krb["id"], "Kerberos Keytab"): "${CONF_DIR}/nifi.keytab"})

    kc = svc("org.apache.nifi.kafka.service.Kafka3ConnectionService", "nifi-kafka-3-service-nar", "CE Kafka (SASL_SSL GSSAPI)")
    d = descriptors("controller-services", kc["id"]); print("  kafka descriptors:", sorted(d))
    kprops = {prop_name("controller-services", kc["id"], "bootstrap.servers", "Bootstrap Servers"): "#{Kafka Bootstrap}",
              prop_name("controller-services", kc["id"], "security.protocol", "Security Protocol"): "SASL_SSL",
              prop_name("controller-services", kc["id"], "sasl.mechanism", "SASL Mechanism"): "GSSAPI",
              prop_name("controller-services", kc["id"], "Kerberos User Service", "kerberos-user-service"): krb["id"],
              prop_name("controller-services", kc["id"], "SSL Context Service", "ssl.context.service"): ssl["id"]}
    for k in d:
        if "kerberos" in k.lower() and "service name" in k.lower(): kprops[k] = "kafka"
        if k == "sasl.kerberos.service.name": kprops[k] = "kafka"
    print("  kafka props:", kprops); set_props("controller-services", kc, kprops)

    def proc(type_, name, x, y, props, sched=None, extra=None):
        cfg = {"properties": props, "autoTerminatedRelationships": []}
        if sched: cfg.update(sched)
        if extra: cfg.update(extra)
        e = api("POST", f"/process-groups/{pid}/processors", {"revision": rev(), "component": {
            "type": type_, "bundle": {"group": "org.apache.nifi", "artifact": "nifi-standard-nar" if "standard" in type_ else "nifi-kafka-nar", "version": "2.3.0.4.10.0.0-154"},
            "name": name, "position": {"x": x, "y": y}, "config": cfg}})
        print("processor", name, e["id"]); return e
    # vertical chain, row pitch 200, failure branch +300 to the right
    gen = proc("org.apache.nifi.processors.standard.GenerateFlowFile", "AskTheModel", 0, 0,
               {"generate-ff-custom-text": PROMPT_BODY, "File Size": "0B", "Batch Size": "1",
                "mime.type": "application/json"},
               {"schedulingPeriod": "60 sec", "executionNode": "PRIMARY"})
    inv = proc("org.apache.nifi.processors.standard.InvokeHTTP", "InvokeLLM", 0, 200, {
        "HTTP Method": "POST", "HTTP URL": "#{LLM Base URL}/v1/chat/completions",
        "Request Content-Type": "application/json", "Socket Read Timeout": "300 secs", "Socket Connect Timeout": "10 secs"},
        {"schedulingPeriod": "0 sec", "penaltyDuration": "30 sec"})
    pub = proc("org.apache.nifi.kafka.processors.PublishKafka", "PublishResponse", 0, 400,
               {"Kafka Connection Service": kc["id"], "Topic Name": "#{Kafka Topic}", "Delivery Guarantee": "1",
                "Publish Strategy": "USE_VALUE"})
    logok = proc("org.apache.nifi.processors.standard.LogAttribute", "LogPublished", 0, 600, {"Log Level": "info", "Log Payload": "false"})
    logfail = proc("org.apache.nifi.processors.standard.LogAttribute", "LogFailure", 300, 400, {"Log Level": "warn", "Log Payload": "true"})
    # descriptors sanity for the two processors whose property names matter
    dinv = descriptors("processors", inv["id"]); missing = [k for k in ("HTTP Method", "HTTP URL", "Request Content-Type") if k not in dinv]
    if missing: print("  WARNING InvokeHTTP descriptor names differ:", missing, sorted(dinv)[:40])
    dpub = descriptors("processors", pub["id"]); missing = [k for k in ("Kafka Connection Service", "Topic Name") if k not in dpub]
    if missing: print("  WARNING PublishKafka descriptor names differ:", missing, sorted(dpub))

    def conn(src, rels, dst, name=None, expire=None):
        c = {"source": {"id": src["id"], "groupId": pid, "type": "PROCESSOR"},
             "destination": {"id": dst["id"], "groupId": pid, "type": "PROCESSOR"}, "selectedRelationships": rels}
        if name: c["name"] = name
        if expire: c["flowFileExpiration"] = expire
        e = api("POST", f"/process-groups/{pid}/connections", {"revision": rev(), "component": c}); print("connection", rels, "->", dst["component"]["name"]); return e
    conn(gen, ["success"], inv)
    conn(inv, ["Response"], pub)
    conn(inv, ["Retry"], inv, "retry (10 min expiry)", "10 min")
    conn(inv, ["Failure", "No Retry"], logfail)
    conn(pub, ["success"], logok)
    conn(pub, ["failure"], logfail)
    # auto-terminate the leftovers explicitly (Original on InvokeHTTP, success on the logs)
    set_props("processors", inv, {}, {"autoTerminatedRelationships": ["Original"]})
    set_props("processors", logok, {}, {"autoTerminatedRelationships": ["success"]})
    set_props("processors", logfail, {}, {"autoTerminatedRelationships": ["success"]})
    # enable services (dependency order)
    for e in (ssl, krb, kc):
        cur = api("GET", f"/controller-services/{e['id']}")
        api("PUT", f"/controller-services/{e['id']}/run-status", {"revision": cur["revision"], "state": "ENABLED"})
    time.sleep(5)
    for e in (ssl, krb, kc):
        cur = api("GET", f"/controller-services/{e['id']}")["component"]
        print("service", cur["name"], cur["state"], cur.get("validationStatus"), (cur.get("validationErrors") or [])[:3])
    for e in (gen, inv, pub, logok, logfail):
        cur = api("GET", f"/processors/{e['id']}")["component"]
        print("processor", cur["name"], cur.get("validationStatus"), (cur.get("validationErrors") or [])[:3])
    print("BUILD DONE pg", pid)

def start(state="RUNNING"):
    pg = find_pg(); api("PUT", f"/flow/process-groups/{pg['id']}", {"id": pg["id"], "state": state}); print(state, pg["id"])
def status():
    pg = find_pg(); st = api("GET", f"/flow/process-groups/{pg['id']}/status?recursive=true")["processGroupStatus"]["aggregateSnapshot"]
    print(f"PG {st['name']} in {st['flowFilesIn']} out {st['flowFilesOut']} queued {st['queuedCount']} ({st['queued']})")
    for p in st["processorStatusSnapshots"]:
        p = p["processorStatusSnapshot"]; print(f"  {p['name']:16} {p['runStatus']:8} in {p['flowFilesIn']:3} out {p['flowFilesOut']:3}")
    for c in st["connectionStatusSnapshots"]:
        c = c["connectionStatusSnapshot"]
        if c["flowFilesQueued"]: print(f"  queued {c['flowFilesQueued']} on {c['name']}")
    bl = api("GET", f"/flow/process-groups/{pg['id']}/status?recursive=true")
    for p in api("GET", f"/process-groups/{pg['id']}/processors")["processors"]:
        for b in p.get("bulletins", [])[-2:]: print("  bulletin", p["component"]["name"], b["bulletin"]["level"], b["bulletin"]["message"][:200])
def export():
    pg = find_pg(); d = api("GET", f"/process-groups/{pg['id']}/download")
    if isinstance(d, str): d = json.loads(d)
    json.dump(d, open(f"{OUT}/{PG_NAME}.flow.json", "w"), indent=2); print("exported", f"{OUT}/{PG_NAME}.flow.json")
def delete():
    pg = find_pg()
    if not pg: return print("no pg")
    start("STOPPED"); time.sleep(3)
    for e in api("GET", f"/flow/process-groups/{pg['id']}/controller-services")["controllerServices"]:
        cur = api("GET", f"/controller-services/{e['id']}")
        api("PUT", f"/controller-services/{e['id']}/run-status", {"revision": cur["revision"], "state": "DISABLED"})
    time.sleep(3); pg = find_pg()
    api("DELETE", f"/process-groups/{pg['id']}?version={pg['revision']['version']}&clientId={CLIENT}"); print("deleted")
    ctx = find_ctx()
    if ctx: api("DELETE", f"/parameter-contexts/{ctx['id']}?version={ctx['revision']['version']}&clientId={CLIENT}"); print("context deleted")

if __name__ == "__main__":
    {"build": build, "start": start, "status": status, "stop": lambda: start("STOPPED"), "export": export, "delete": delete}[sys.argv[1]]()
