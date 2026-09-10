#!/usr/bin/env python3
"""EspiFi -- a lightweight drop that registers in Cloudera EFM (#315).

One file, standard library only, written to run unchanged on CPython (a host)
and on MicroPython (an ESP32). It speaks the two EFM C2 endpoints a MiNiFi
agent speaks -- nothing more:

    POST <efm>/efm/api/c2-protocol/heartbeat     periodic; manifest on first beat
    POST <efm>/efm/api/c2-protocol/acknowledge   per operation, minimal body

and it runs the flow EFM pushes (UPDATE/configuration) with interpreted
processors -- a processor is a Python function, so adding one is a file copy,
not a firmware rebuild. The wire contract is taken verbatim from the MicroFi
fork's c2_client.cpp / manifest.cpp (the only field-verified EFM 2.3.1 client
in the array); the traps it documents are kept as comments here.

Run on a host:      python3 espifi.py --efm http://100.68.113.126:10090
Run on MicroPython: put espifi.py + espifi_config.py on the board, `import espifi`
"""

import json
import sys
import time

try:
    import hashlib
except ImportError:            # some MicroPython builds ship uhashlib only
    import uhashlib as hashlib

# ---------------------------------------------------------------- platform shims

MICROPYTHON = sys.implementation.name == "micropython"

if MICROPYTHON:
    import binascii
    import network
    import os

    try:
        import requests as _rq          # MicroPython >= 1.21 (mip "requests")
    except ImportError:
        import urequests as _rq         # older builds

    def http(method, url, body=None, headers=None, timeout=10):
        r = _rq.request(method, url, data=body, headers=headers or {})
        try:
            return r.status_code, r.text
        finally:
            r.close()

    def now_ms():
        return time.ticks_ms()

    def elapsed_ms(since):
        return time.ticks_diff(time.ticks_ms(), since)

    def mac_hex():
        w = network.WLAN(network.STA_IF)
        w.active(True)
        return binascii.hexlify(w.config("mac")).decode()

    def wifi_connect(ssid, password="", timeout_ms=20000):
        """Join the configured network; an empty password means an open AP."""
        w = network.WLAN(network.STA_IF)
        w.active(True)
        if not w.isconnected():
            w.connect(ssid, password or "")
            t = time.ticks_ms()
            while not w.isconnected() and time.ticks_diff(time.ticks_ms(), t) < timeout_ms:
                time.sleep(0.2)
        return w.isconnected()

    def ip_address():
        try:
            return network.WLAN(network.STA_IF).ifconfig()[0]
        except Exception:
            return ""

    def free_mem():
        import gc
        return gc.mem_free()

    def sha256_hex(s):
        return binascii.hexlify(hashlib.sha256(s.encode()).digest()).decode()

    def getenv(name, default):
        return default

    ARCH, OS_NAME = "esp32", "MicroPython"
else:
    import os
    import socket
    import urllib.error
    import urllib.request
    import uuid

    def http(method, url, body=None, headers=None, timeout=10):
        req = urllib.request.Request(url, data=body, method=method)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def now_ms():
        return int(time.time() * 1000)

    def elapsed_ms(since):
        return now_ms() - since

    def mac_hex():
        return "%012x" % uuid.getnode()

    def ip_address():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return ""

    def free_mem():
        return 0

    def sha256_hex(s):
        return hashlib.sha256(s.encode()).hexdigest()

    def getenv(name, default):
        return os.environ.get(name, default)

    def wifi_connect(ssid, password="", timeout_ms=20000):
        return True                                   # a host is already on the network

    ARCH, OS_NAME = "x86_64", "CPython " + sys.version.split()[0]

# ---------------------------------------------------------------- configuration

CONFIG = {
    "efm": getenv("ESPIFI_EFM", "http://127.0.0.1:10090"),
    "agent_class": getenv("ESPIFI_CLASS", "EspiFi"),
    "agent_id": getenv("ESPIFI_ID", ""),           # blank -> espifi-<mac>
    "heartbeat_ms": int(getenv("ESPIFI_HEARTBEAT_MS", "5000")),
    "tick_ms": 250,
    "wifi_ssid": "",                                # MicroPython only; blank = already connected
    "wifi_password": "",
    "flow_file": "espifi_flow.txt",
    "flow_id_file": "espifi_flow_id.txt",
    "verbose": False,
}
try:
    import espifi_config                           # optional overrides, both platforms
    CONFIG.update(getattr(espifi_config, "CONFIG", {}))
except ImportError:
    pass

VERSION = "0.1.0"
BUNDLE = {"group": "org.apache.nifi", "artifact": "espifi-system", "version": VERSION}
ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def log(*a):
    print("[espifi]", *a)


def dbg(*a):
    if CONFIG["verbose"]:
        print("[espifi]", *a)


# ---------------------------------------------------------------- identity
# MicroFi: agent id "microfi-<mac>", deviceInfo.identifier = bare mac hex, and a
# deterministic per-device root process-group UUID -- EFM's Monitor view keys
# per-processor counters by (processGroupId, processorId).

DEVICE_ID = mac_hex()
AGENT_ID = CONFIG["agent_id"] or ("espifi-" + DEVICE_ID)


def _uuid_from(seed):
    h = sha256_hex(seed)
    return "%s-%s-4%s-8%s-%s" % (h[0:8], h[8:12], h[13:16], h[17:20], h[20:32])


PROCESS_GROUP_ID = _uuid_from("espifi-pg-" + DEVICE_ID)

# ---------------------------------------------------------------- processor registry
# A processor is a dict: name, description, input ("INPUT_FORBIDDEN"|"INPUT_REQUIRED"|
# "INPUT_ALLOWED"), properties (list of {name, description, default, allowable}) and
# `run(node, session)`. Adding a processor is adding a dict here (or in a module
# copied onto the board) -- no rebuild, no reflash.


class FlowFile:
    _seq = 0

    def __init__(self, content=b"", attrs=None):
        FlowFile._seq += 1
        self.id = "%s-%d" % (_uuid_from("ff-%s-%d" % (DEVICE_ID, FlowFile._seq)), FlowFile._seq)
        self.content = content
        self.attrs = dict(attrs or {})
        self.attrs.setdefault("uuid", self.id)
        self.attrs.setdefault("filename", self.id)


class Session:
    """What a processor sees: read inbound FlowFiles, transfer outbound ones."""

    def __init__(self, engine, node):
        self.engine, self.node = engine, node

    def get(self):
        for c in self.engine.connections:
            if c["dst"] == self.node["id"] and c["queue"]:
                self.node["stats"]["ff_in"] += 1
                return c["queue"].pop(0)
        return None

    def transfer(self, ff, relationship="success"):
        self.node["stats"]["ff_out"] += 1
        self.node["stats"]["bytes_out"] += len(ff.content)
        for c in self.engine.connections:
            if c["src"] == self.node["id"] and relationship in c["rels"]:
                c["queue"].append(ff)


def _generate_flowfile(node, session):
    p = node["props"]
    text = p.get("Custom Text") or ""
    if not text:
        text = "espifi %s %d" % (AGENT_ID, now_ms())
    n = int(p.get("Batch Size") or 1)
    for _ in range(n):
        session.transfer(FlowFile(text.encode(), {"espifi.agent": AGENT_ID}))


def _log_attribute(node, session):
    ff = session.get()
    while ff is not None:
        prefix = node["props"].get("Log prefix") or node["name"]
        line = "%s: FlowFile %s attrs=%s" % (prefix, ff.id, json.dumps(ff.attrs))
        if (node["props"].get("Log Payload") or "false") == "true":
            line += " content=%r" % ff.content
        log(line)
        session.transfer(ff)
        ff = session.get()


REGISTRY = [
    {
        "name": "GenerateFlowFile",
        "description": "Emits a FlowFile per tick; content and batch size configurable via EFM.",
        "input": "INPUT_FORBIDDEN",
        "properties": [
            {"name": "Batch Size", "description": "FlowFiles emitted per invocation.", "default": "1"},
            {"name": "Custom Text", "description": "Content for each FlowFile; blank means a generated line."},
        ],
        "run": _generate_flowfile,
    },
    {
        "name": "LogAttribute",
        "description": "Logs FlowFile id and attributes, optionally the content.",
        "input": "INPUT_REQUIRED",
        "properties": [
            {"name": "Log prefix", "description": "Identifier prepended to each log line."},
            {"name": "Log Payload", "description": "Also log the FlowFile content.",
             "default": "false", "allowable": ["true", "false"]},
        ],
        "run": _log_attribute,
    },
]


def find_processor(type_name):
    for d in REGISTRY:
        if d["name"] == type_name:
            return d
    return None


# ---------------------------------------------------------------- manifest
# Shape from MicroFi manifest.cpp, which EFM 2.3.1 stores and renders. Traps kept:
# bundle coordinates repeated on every processor entry (EFM needs them for the
# component identity), and `propertyDescriptors` OMITTED when empty (EFM stores
# {} as "" and the processor disappears from the palette).


def build_manifest():
    procs = []
    for d in REGISTRY:
        p = dict(BUNDLE)
        p.update({
            "type": d["name"],
            "typeDescription": d["description"],
            "inputRequirement": d["input"],
            "isSingleThreaded": False,
            "supportsDynamicProperties": False,
            "supportsDynamicRelationships": False,
            "supportedRelationships": [
                {"name": "success", "description": "FlowFiles produced by this processor."}],
        })
        if d["properties"]:
            pd = {}
            for prop in d["properties"]:
                e = {"name": prop["name"], "description": prop.get("description", ""),
                     "required": False}
                if prop.get("default") is not None:
                    e["defaultValue"] = prop["default"]
                if prop.get("allowable"):
                    e["allowableValues"] = [{"value": v, "displayName": v} for v in prop["allowable"]]
                pd[prop["name"]] = e
            p["propertyDescriptors"] = pd
        procs.append(p)

    bundle = dict(BUNDLE)
    bundle["componentManifest"] = {"processors": procs, "controllerServices": [], "reportingTasks": []}
    m = {
        "identifier": "0" * 64,
        "agentType": "cpp",        # EFM knows this type; it decides the flow format it pushes
        "version": VERSION,
        "buildInfo": {"version": VERSION, "revision": "dev", "timestamp": 0,
                      "targetArch": ARCH, "compiler": sys.implementation.name,
                      "compilerFlags": OS_NAME},
        "bundles": [bundle],
        "schedulingDefaults": {"defaultSchedulingStrategy": "TIMER_DRIVEN",
                               "defaultSchedulingPeriodMillis": 1000,
                               "defaultRunDurationNanos": 0, "defaultMaxConcurrentTasks": 1,
                               "penalizationPeriodMillis": 30000, "yieldDurationMillis": 1000},
        "supportedOperations": [
            {"type": "HEARTBEAT", "properties": {}},
            {"type": "ACKNOWLEDGE", "properties": {}},
            {"type": "DESCRIBE", "properties": {"manifest": {}, "configuration": {}}},
            {"type": "UPDATE", "properties": {"configuration": {}}},
        ],
    }
    # nifi-minifi-cpp convention, kept by MicroFi: the id is the hash of the manifest
    # serialized with the placeholder id.
    m["identifier"] = sha256_hex(json.dumps(m))
    return m


MANIFEST = build_manifest()
MANIFEST_HASH = MANIFEST["identifier"]

# ---------------------------------------------------------------- flow parsing
# EFM 2.x hands a cpp agent either a NiFi versioned-flow-snapshot JSON
# ({"flowContents": {...}}) or a "MiNiFi Config Version: 3" YAML. Only the subset
# an agent needs is read: processors (id, name, type, properties) and connections
# (source, destination, relationships).


def _parse_json_flow(body):
    doc = json.loads(body)
    fc = doc.get("flowContents") or doc.get("content") or doc
    nodes, conns = [], []
    for p in fc.get("processors", []):
        nodes.append({"id": p.get("identifier") or p.get("id"), "name": p.get("name", ""),
                      "type": p["type"].split(".")[-1], "props": p.get("properties") or {},
                      "period": p.get("schedulingPeriod", "")})
    for c in fc.get("connections", []):
        conns.append({"src": c["source"]["id"], "dst": c["destination"]["id"],
                      "rels": list(c.get("selectedRelationships") or ["success"])})
    return fc.get("identifier", ""), nodes, conns


def _yaml_lines(body):
    """Yield (indent, key, value) for the simple block-YAML MiNiFi emits."""
    for raw in body.split("\n"):
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        s = line.strip()
        item = s.startswith("- ")
        if item:
            s = s[2:]
        if ":" in s:
            k, v = s.split(":", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            yield indent, item, k.strip(), v
        else:
            yield indent, item, s, None


def _parse_yaml_flow(body):
    """MiNiFi Config Version 3 subset, written against the body EFM 2.3.1 pushes:
    list items sit at indent 0 ("- id: ..."), their keys at indent 2, Properties
    at indent 4, relationship lists as "- name" items at indent 2."""
    section, cur, sub = None, None, None
    nodes, conns = [], []
    for indent, item, k, v in _yaml_lines(body):
        if indent == 0 and not item:                    # section header
            section, cur, sub = k, None, None
            continue
        if section == "Processors":
            if item and indent == 0:
                cur = {"id": "", "name": "", "type": "", "props": {}, "period": ""}
                nodes.append(cur)
                sub = None
            if cur is None:
                continue
            if (item and indent == 0) or (not item and indent == 2):
                sub = "props" if k == "Properties" else None
                if k == "id":
                    cur["id"] = v or ""
                elif k == "name":
                    cur["name"] = v or ""
                elif k == "class":
                    cur["type"] = v or ""
                elif k == "scheduling period":
                    cur["period"] = v or ""
                continue
            if sub == "props" and indent >= 4 and v is not None:
                cur["props"][k] = v
        elif section == "Connections":
            if item and indent == 0:
                cur = {"id": "", "src": "", "dst": "", "rels": []}
                conns.append(cur)
                sub = None
            if cur is None:
                continue
            if (item and indent == 0) or (not item and indent == 2):
                sub = "rels" if k == "source relationship names" else None
                if k == "id":
                    cur["id"] = v or ""
                elif k == "source id":
                    cur["src"] = v or ""
                elif k == "destination id":
                    cur["dst"] = v or ""
                continue
            if sub == "rels" and item and indent == 2:
                cur["rels"].append(k)
    for n in nodes:
        n["type"] = n["type"].split(".")[-1]
        if not n["id"]:
            n["id"] = _uuid_from("node-" + n["name"])
    for c in conns:
        if not c["rels"]:
            c["rels"] = ["success"]
    return "", nodes, conns


def parse_flow(body):
    if body.lstrip().startswith("{"):
        return _parse_json_flow(body)
    if "MiNiFi Config Version" in body[:200]:
        return _parse_yaml_flow(body)
    raise ValueError("unrecognised flow format: %r" % body[:60])


def uuid_in(s):
    """First UUID-shaped token in s (EFM's flow URL carries the flow id)."""
    for i in range(len(s) - 35):
        t = s[i:i + 36]
        if t[8] == t[13] == t[18] == t[23] == "-":
            ok = True
            for j, ch in enumerate(t):
                if j in (8, 13, 18, 23):
                    continue
                if ch not in "0123456789abcdefABCDEF":
                    ok = False
                    break
            if ok:
                return t
    return ""


# ---------------------------------------------------------------- flow engine


class Engine:
    def __init__(self):
        self.flow_id = ZERO_UUID
        self.nodes, self.connections = [], []
        self.produced = self.consumed = 0
        self._last = {}

    def apply(self, flow_id, nodes, conns):
        live = []
        for n in nodes:
            d = find_processor(n["type"])
            if d is None:
                raise ValueError("unknown processor type %s" % n["type"])
            period = n.get("period") or n["props"].get("Scheduling Period") or "1000 ms"
            n["period_ms"] = _period_ms(period)
            n["desc"] = d
            n["stats"] = {"ff_in": 0, "ff_out": 0, "bytes_out": 0, "invocations": 0}
            live.append(n)
        for c in conns:
            c["queue"] = []
            c["id"] = c.get("id") or _uuid_from("conn-%s-%s" % (c["src"], c["dst"]))
            c["name"] = ",".join(c["rels"])
        self.nodes, self.connections = live, conns
        self.flow_id = flow_id or ZERO_UUID
        self._last = {}
        log("flow applied: %d processor(s), %d connection(s), flow_id=%s"
            % (len(live), len(conns), self.flow_id))

    def tick(self):
        t = now_ms()
        for n in self.nodes:
            last = self._last.get(n["id"])
            if last is not None and elapsed_ms(last) < n["period_ms"]:
                continue
            self._last[n["id"]] = t
            n["stats"]["invocations"] += 1
            before_out = n["stats"]["ff_out"]
            n["desc"]["run"](n, Session(self, n))
            self.produced += n["stats"]["ff_out"] - before_out

    def queue_depth(self):
        return sum(len(c["queue"]) for c in self.connections)


def _period_ms(text):
    text = str(text).strip().lower()
    num = ""
    for ch in text:
        if ch.isdigit() or ch == ".":
            num += ch
        else:
            break
    if not num:
        return 1000
    val = float(num)
    if "min" in text:
        return int(val * 60000)
    if "ms" in text:
        return int(val)
    if "sec" in text or text.endswith("s"):
        return int(val * 1000)
    return int(val)


ENGINE = Engine()

# ---------------------------------------------------------------- C2 client


class C2:
    def __init__(self):
        self.base = CONFIG["efm"].rstrip("/")
        self.hb_url = self.base + "/efm/api/c2-protocol/heartbeat"
        self.ack_url = self.base + "/efm/api/c2-protocol/acknowledge"
        self.counter = 0
        self.send_manifest = True
        self.started = now_ms()

    # ---- envelope (field-for-field what MicroFi sends) ----
    def heartbeat_body(self):
        uptime = elapsed_ms(self.started)
        components = {"FlowController": {"running": True, "uuid": PROCESS_GROUP_ID}}
        statuses = []
        for n in ENGINE.nodes:
            components[n["desc"]["name"]] = {"running": True, "uuid": n["id"]}
            st = n["stats"]
            statuses.append({
                "id": n["id"], "groupId": PROCESS_GROUP_ID, "runStatus": "RUNNING",
                "bytesRead": 0, "bytesWritten": st["bytes_out"],
                "flowFilesIn": st["ff_in"], "flowFilesOut": st["ff_out"],
                "bytesIn": 0, "bytesOut": st["bytes_out"], "invocations": st["invocations"],
                "processingNanos": 0,
                # -1 is MiNiFi's "unknown"; a literal 0 trips Monitor's liveness check
                "activeThreadCount": -1, "terminatedThreadCount": -1,
            })
        queues = {}
        for c in ENGINE.connections:
            queues[c["id"]] = {"dataSize": 0, "dataSizeMax": 104857600, "name": c["name"],
                               "size": len(c["queue"]), "sizeMax": 2000, "uuid": c["id"]}
        agent_info = {
            "identifier": AGENT_ID,
            "agentClass": CONFIG["agent_class"],
            "agentManifestHash": MANIFEST_HASH,
            "heartbeatPeriod": CONFIG["heartbeat_ms"],
            "status": {
                "uptime": uptime,
                "components": components,
                "repositories": {"flowFile": {"size": ENGINE.queue_depth(), "sizeMax": None,
                                              "dataSize": None, "dataSizeMax": None}},
                "resourceConsumption": {"memoryUsage": free_mem(), "cpuUtilization": 0.0},
                "espifi": {"queueDepth": ENGINE.queue_depth(), "produced": ENGINE.produced,
                           "runtime": OS_NAME},
            },
        }
        if self.send_manifest:
            agent_info["agentManifest"] = MANIFEST
        body = {
            "identifier": "%s-%d-%d" % (AGENT_ID, self.counter, uptime),
            "operation": "HEARTBEAT",
            "agentInfo": agent_info,
            "deviceInfo": {
                "identifier": DEVICE_ID,
                "systemInfo": {"machineArch": ARCH, "operatingSystem": OS_NAME,
                               "physicalMem": free_mem(), "vCores": 1},
                "networkInfo": {"deviceId": DEVICE_ID, "hostname": AGENT_ID,
                                "ipAddress": ip_address()},
            },
            "flowInfo": {
                "flowId": ENGINE.flow_id,
                "runStatus": "RUNNING",
                "versionedFlowSnapshotURI": {"registryUrl": "", "bucketId": "default",
                                             "flowId": ENGINE.flow_id},
                "queues": queues,
                "processorStatuses": statuses,
            },
        }
        return json.dumps(body)

    def heartbeat(self):
        body = self.heartbeat_body()
        code, text = http("POST", self.hb_url, body.encode(),
                          {"Content-Type": "application/json"})
        log("heartbeat #%d -> %d (sent %d bytes, manifest=%s)"
            % (self.counter, code, len(body), "yes" if self.send_manifest else "no"))
        if code >= 400:
            dbg("response:", text[:300])
            return False
        if self.send_manifest:
            self.send_manifest = False
        self.counter += 1
        self.handle(text)
        return True

    # ---- operations ----
    def handle(self, text):
        try:
            doc = json.loads(text) if text else {}
        except ValueError:
            log("response not JSON:", text[:80])
            return
        for op in doc.get("requestedOperations") or []:
            kind, operand, op_id = op.get("operation"), op.get("operand"), op.get("identifier")
            log("EFM op=%s operand=%s id=%s" % (kind, operand, op_id))
            if kind == "DESCRIBE" and operand == "manifest":
                self.send_manifest = True          # next heartbeat carries it
            elif kind == "UPDATE" and operand == "configuration":
                self.update_configuration(op)
            else:
                self.ack(op_id, False, "unsupported operation %s/%s" % (kind, operand))

    def update_configuration(self, op):
        op_id = op.get("identifier")
        args = op.get("args") or {}
        url = ""
        for key in ("location", "flowUrl", "configuration", "url"):   # EFM 2.x: location
            if args.get(key):
                url = args[key]
                break
        if not url:
            url = self.hb_url.rsplit("/", 1)[0] + "/configContent/" + str(op_id)
        log("fetching flow:", url)
        code, body = http("GET", url)
        if code >= 400:
            self.ack(op_id, False, "flow fetch failed: HTTP %d" % code)
            return
        try:
            flow_id, nodes, conns = parse_flow(body)
            flow_id = flow_id or uuid_in(url)          # YAML v3 carries no id; the URL does
            ENGINE.apply(flow_id, nodes, conns)
        except Exception as e:                          # noqa: BLE001 -- report, don't die
            log("flow apply failed:", e)
            self.ack(op_id, False, "flow apply failed: %s" % e)
            return
        _save(CONFIG["flow_file"], body)
        _save(CONFIG["flow_id_file"], flow_id)
        self.ack(op_id, True, "flow applied")

    def ack(self, op_id, applied, details=""):
        if not op_id:
            return
        # Body is deliberately only {operationId, operationState}: adding agentInfo /
        # deviceInfo / flowInfo makes EFM process the ack as a second heartbeat.
        state = {"state": "FULLY_APPLIED" if applied else "NOT_APPLIED"}
        if details:
            state["details"] = details
        body = json.dumps({"operationId": op_id, "operationState": state})
        code, _ = http("POST", self.ack_url, body.encode(), {"Content-Type": "application/json"})
        log("ack op=%s state=%s -> %d" % (op_id, state["state"], code))


def _save(name, text):
    try:
        with open(name, "w") as f:
            f.write(text)
    except Exception as e:                              # noqa: BLE001
        log("save %s failed: %s" % (name, e))


def _restore():
    """Re-apply the last pushed flow so the first heartbeat already carries its id."""
    try:
        with open(CONFIG["flow_file"]) as f:
            body = f.read()
        with open(CONFIG["flow_id_file"]) as f:
            flow_id = f.read().strip()
    except Exception:
        return
    try:
        _, nodes, conns = parse_flow(body)
        ENGINE.apply(flow_id, nodes, conns)
        log("restored saved flow", flow_id)
    except Exception as e:                              # noqa: BLE001
        log("saved flow ignored:", e)


# ---------------------------------------------------------------- main loop


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    while argv:
        a = argv.pop(0)
        if a == "--efm":
            CONFIG["efm"] = argv.pop(0)
        elif a == "--class":
            CONFIG["agent_class"] = argv.pop(0)
        elif a == "--id":
            CONFIG["agent_id"] = argv.pop(0)
        elif a == "--period":
            CONFIG["heartbeat_ms"] = int(argv.pop(0))
        elif a in ("-v", "--verbose"):
            CONFIG["verbose"] = True
        elif a == "--manifest":
            print(json.dumps(MANIFEST, indent=2))
            return 0
        elif a == "--once":
            CONFIG["once"] = True
    global AGENT_ID
    AGENT_ID = CONFIG["agent_id"] or ("espifi-" + DEVICE_ID)

    log("EspiFi %s on %s" % (VERSION, OS_NAME))
    log("agent_id=%s class=%s manifest_hash=%s" % (AGENT_ID, CONFIG["agent_class"], MANIFEST_HASH[:16]))
    log("%d processor(s): %s" % (len(REGISTRY), ", ".join(d["name"] for d in REGISTRY)))
    if CONFIG.get("wifi_ssid"):
        up = wifi_connect(CONFIG["wifi_ssid"], CONFIG.get("wifi_password", ""))
        log("wifi %s -> %s ip=%s" % (CONFIG["wifi_ssid"], "up" if up else "DOWN", ip_address()))
    _restore()
    c2 = C2()
    log("heartbeating to", c2.hb_url)

    last_hb = None
    while True:
        if last_hb is None or elapsed_ms(last_hb) >= CONFIG["heartbeat_ms"]:
            ok = c2.heartbeat()
            last_hb = now_ms() if ok else now_ms() - CONFIG["heartbeat_ms"] + 5000
            if CONFIG.get("once"):
                return 0 if ok else 1
        ENGINE.tick()
        time.sleep(CONFIG["tick_ms"] / 1000.0)


if __name__ == "__main__":
    sys.exit(main())
