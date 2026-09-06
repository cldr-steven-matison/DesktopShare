"""
Shared flow-definition builder for the Streamers-track NiFi PGs on the Spark's mynifi
(#271 StreamerResearch, #281 StreamerCard). Same conventions as build_streamer_brain.py:
uuid5 ids from a per-flow namespace, `Retry` self-loops with a bounded expiration, every
connection routes down, an error column to the right, Parameter Context carried in the
export with sensitive values null (set via the API after upload, never in the file).

Layout (skill references/layout.md, NiFi 2.x): row pitch 200, branch/column pitch 600.
"""
import json
import uuid

VER = "2.6.0.4.3.4.0-234"
STD = {"group": "org.apache.nifi", "artifact": "nifi-standard-nar", "version": VER}
UPD = {"group": "org.apache.nifi", "artifact": "nifi-update-attribute-nar", "version": VER}
PY = {"group": "org.apache.nifi", "artifact": "python-extensions", "version": "0.0.1"}
ROW, COL = 200, 600


class Flow:
    def __init__(self, name, ns_seed, comments, out):
        self.name, self.out, self.comments = name, out, comments
        self.NS = uuid.uuid5(uuid.NAMESPACE_URL, ns_seed)
        self.PG_ID = self.uid("pg")
        self.processors, self.connections, self.services, self.params = [], [], [], []

    def uid(self, name):
        return str(uuid.uuid5(self.NS, name))

    # ── controller services ───────────────────────────────────────────────────
    def service(self, name, typ, artifact, api, props, sensitive=(), api_artifact="nifi-standard-services-api-nar"):
        ident = self.uid(f"cs:{name}")
        self.services.append({
            "identifier": ident, "name": name, "type": typ, "componentType": "CONTROLLER_SERVICE",
            "bundle": {"group": "org.apache.nifi", "artifact": artifact, "version": VER},
            "controllerServiceApis": [{"type": api, "bundle": {"group": "org.apache.nifi",
                                       "artifact": api_artifact, "version": VER}}],
            "groupIdentifier": self.PG_ID, "comments": "", "bulletinLevel": "WARN",
            "scheduledState": "ENABLED", "properties": props,
            "propertyDescriptors": {k: {"name": k, "displayName": k, "dynamic": False,
                                        "identifiesControllerService": False,
                                        "sensitive": k in sensitive} for k in props},
        })
        return ident

    # ── processors ────────────────────────────────────────────────────────────
    def proc(self, name, typ, bundle, x, y, props, auto=(), services=(), dynamic=(),
             run_ms=0, tasks=1, schedule="0 sec", strategy="TIMER_DRIVEN", penalty="30 sec"):
        p = {
            "identifier": self.uid(name), "name": name, "type": typ, "bundle": bundle,
            "componentType": "PROCESSOR", "groupIdentifier": self.PG_ID, "comments": "",
            "position": {"x": float(x), "y": float(y)},
            "properties": props,
            "propertyDescriptors": {k: {"name": k, "displayName": k, "dynamic": k in dynamic,
                                        "identifiesControllerService": k in services, "sensitive": False}
                                    for k in props},
            "autoTerminatedRelationships": list(auto),
            "schedulingPeriod": schedule, "schedulingStrategy": strategy, "executionNode": "ALL",
            "penaltyDuration": penalty, "yieldDuration": "1 sec", "bulletinLevel": "WARN",
            "runDurationMillis": run_ms, "concurrentlySchedulableTaskCount": tasks,
            "scheduledState": "ENABLED", "retryCount": 10, "retriedRelationships": [],
            "backoffMechanism": "PENALIZE_FLOWFILE", "maxBackoffPeriod": "10 mins", "style": {},
        }
        self.processors.append(p)
        return p

    def conn(self, src, rels, dst, expiration="0 sec"):
        s, d = self.uid(src), self.uid(dst)
        self.connections.append({
            "identifier": self.uid(f"conn:{src}:{','.join(rels)}:{dst}"), "name": "",
            "componentType": "CONNECTION", "groupIdentifier": self.PG_ID,
            "source": {"id": s, "type": "PROCESSOR", "groupId": self.PG_ID, "name": src, "comments": ""},
            "destination": {"id": d, "type": "PROCESSOR", "groupId": self.PG_ID, "name": dst, "comments": ""},
            "selectedRelationships": list(rels), "labelIndex": 1, "zIndex": 0, "bends": [],
            "backPressureObjectThreshold": 1000, "backPressureDataSizeThreshold": "1 GB",
            "flowFileExpiration": expiration, "prioritizers": [],
            "loadBalanceStrategy": "DO_NOT_LOAD_BALANCE", "loadBalanceCompression": "DO_NOT_COMPRESS",
        })

    def invoke_http(self, name, x, y, url, method="POST", content_type="application/json",
                    read_timeout="30 secs", to_attr=None, attr_size=65536, headers=None,
                    oauth=None, user_agent=None, body=None, idle_timeout=None):
        """InvokeHTTP. `to_attr` = Response Body Attribute Name: the body lands on the ORIGINAL
        FlowFile (relationship `Original`) and no Response FlowFile is made — the way a step
        enriches without replacing content. Content mode (to_attr=None) routes `Response`."""
        props = {
            "HTTP Method": method, "HTTP URL": url, "Request Content-Type": content_type,
            "Request Body Enabled": "true" if (body if body is not None else method != "GET") else "false",
            "Connection Timeout": "10 secs", "Socket Read Timeout": read_timeout,
            "Socket Write Timeout": "60 secs", "Response Generation Required": "false",
            "Response Redirects Enabled": "True", "Request Failure Penalization Enabled": "false",
            "Request Date Header Enabled": "True", "Request Chunked Transfer-Encoding Enabled": "false",
            "Request Content-Encoding": "DISABLED", "Response Cookie Strategy": "DISABLED",
            "Response Cache Enabled": "false", "Response FlowFile Naming Strategy": "RANDOM",
            "HTTP/2 Disabled": "False",
        }
        auto = ["Original"] if to_attr is None else ["Response"]
        if to_attr:
            props["Response Body Attribute Name"] = to_attr
            props["Response Body Attribute Size"] = str(int(attr_size))   # bytes, integer only
        if user_agent:
            props["Request User-Agent"] = user_agent
        if idle_timeout:
            # Servers with a short keep-alive (Qdrant/actix: 5 s) close idle pooled connections;
            # the first call after a pause then dies with "Broken pipe". Evict idle sockets first.
            props["Socket Idle Timeout"] = idle_timeout
        services = ()
        if oauth:
            props["Request OAuth2 Access Token Provider"] = oauth
            props["OAuth2 Access Token Refresh Strategy"] = "ON_TOKEN_EXPIRATION"
            services = ("Request OAuth2 Access Token Provider",)
        dyn = ()
        if headers:
            props.update(headers)
            dyn = tuple(headers)
        p = self.proc(name, "org.apache.nifi.processors.standard.InvokeHTTP", STD, x, y, props,
                      auto=auto, services=services, dynamic=dyn, penalty="2 secs")
        return p

    def eval_json(self, name, x, y, paths, return_type="json", auto=()):
        props = {"Destination": "flowfile-attribute", "Return Type": return_type,
                 "Path Not Found Behavior": "ignore", "Null Value Representation": "empty string",
                 "Max String Length": "20 MB"}
        props.update(paths)
        return self.proc(name, "org.apache.nifi.processors.standard.EvaluateJsonPath", STD, x, y, props,
                         dynamic=tuple(paths), auto=auto)

    def replace_text(self, name, x, y, value, auto=()):
        return self.proc(name, "org.apache.nifi.processors.standard.ReplaceText", STD, x, y, {
            "Replacement Strategy": "Always Replace", "Evaluation Mode": "Entire text",
            "Regular Expression": "(?s)(^.*$)", "Replacement Value": value,
            "Character Set": "UTF-8", "Maximum Buffer Size": "10 MB", "Line-by-Line Evaluation Mode": "All",
        }, auto=auto, run_ms=25)

    def update_attr(self, name, x, y, attrs):
        props = {"Delete Attributes Expression": None, "Store State": "Do not store state"}
        props.update(attrs)
        return self.proc(name, "org.apache.nifi.processors.attributes.UpdateAttribute", UPD, x, y, props,
                         dynamic=tuple(attrs), run_ms=25)

    def route_attr(self, name, x, y, routes, auto=()):
        props = {"Routing Strategy": "Route to Property name"}
        props.update(routes)
        return self.proc(name, "org.apache.nifi.processors.standard.RouteOnAttribute", STD, x, y, props,
                         dynamic=tuple(routes), auto=auto)

    def route_content(self, name, x, y, routes):
        props = {"Match Requirement": "content must contain match", "Character Set": "UTF-8",
                 "Content Buffer Size": "1 MB"}
        props.update(routes)
        return self.proc(name, "org.apache.nifi.processors.standard.RouteOnContent", STD, x, y, props,
                         dynamic=tuple(routes))

    def split_json(self, name, x, y, path="$[*]", auto=("original",)):
        return self.proc(name, "org.apache.nifi.processors.standard.SplitJson", STD, x, y, {
            "JsonPath Expression": path, "Null Value Representation": "empty string",
            "Max String Length": "20 MB"}, auto=auto)

    def log(self, name, x, y, level="warn", auto=("success",)):
        return self.proc(name, "org.apache.nifi.processors.standard.LogAttribute", STD, x, y, {
            "Log Level": level, "Log Payload": "true", "Log FlowFile Properties": "true",
            "Output Format": "Line per Attribute", "attributes-to-log-regex": ".*", "character-set": "UTF-8",
        }, auto=auto)

    # ── parameters + export ───────────────────────────────────────────────────
    def param(self, name, value, description, sensitive=False):
        self.params.append((name, value, description, sensitive))

    def build(self):
        return {
            "flowEncodingVersion": "1.0", "latest": False,
            "externalControllerServices": {}, "parameterProviders": {},
            "parameterContexts": {self.name: {
                "componentType": "PARAMETER_CONTEXT", "name": self.name,
                "description": f"Endpoints and credentials the {self.name} PG uses (Streamers track).",
                "inheritedParameterContexts": [],
                "parameters": [{"name": n, "value": v, "description": d, "sensitive": s, "provided": False}
                               for n, v, d, s in self.params],
            }},
            "flowContents": {
                "identifier": self.PG_ID, "name": self.name, "componentType": "PROCESS_GROUP",
                "comments": self.comments, "position": {"x": 0.0, "y": 0.0},
                "parameterContextName": self.name,
                "processors": self.processors, "connections": self.connections,
                "controllerServices": self.services,
                "funnels": [], "inputPorts": [], "outputPorts": [], "labels": [], "processGroups": [],
                "remoteProcessGroups": [], "scheduledState": "ENABLED",
                "defaultFlowFileExpiration": "0 sec", "defaultBackPressureObjectThreshold": 10000,
                "defaultBackPressureDataSizeThreshold": "1 GB", "executionEngine": "INHERITED",
                "flowFileConcurrency": "UNBOUNDED", "flowFileOutboundPolicy": "STREAM_WHEN_AVAILABLE",
                "maxConcurrentTasks": 1, "statelessFlowTimeout": "1 min",
            },
        }

    def write(self):
        json.dump(self.build(), open(self.out, "w"), indent=2)
        print(f"wrote {self.out}: {len(self.processors)} processors, {len(self.connections)} connections, "
              f"{len(self.services)} services, {len(self.params)} parameters")
        pos = {p["name"]: p["position"] for p in self.processors}
        names = set(pos)
        for c in self.connections:
            for end in ("source", "destination"):
                if c[end]["name"] not in names:
                    raise SystemExit(f"connection references unknown processor {c[end]['name']!r}")
        bad = [(c["source"]["name"], c["destination"]["name"]) for c in self.connections
               if c["source"]["id"] != c["destination"]["id"]
               and pos[c["destination"]["name"]]["y"] < pos[c["source"]["name"]]["y"]]
        print("connections routing upward:", bad or "none")
        # every processor's relationships that are neither connected nor auto-terminated show up
        # as INVALID on import — surface the obvious misses (unknown rel names) here.
        rels = {}
        for c in self.connections:
            rels.setdefault(c["source"]["name"], set()).update(c["selectedRelationships"])
        for p in self.processors:
            if not rels.get(p["name"]) and not p["autoTerminatedRelationships"]:
                print(f"  note: {p['name']} has no outbound connection and no auto-terminated relationship")
