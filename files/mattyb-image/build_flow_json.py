#!/usr/bin/env python3
"""Emit flow-mattyb-image.json — the end-to-end mattyB flow as a NiFi 2.x
versioned-flow snapshot (the format NiFi's flow-definition download/upload uses).

Deterministic (fixed identifiers, no randomness) so re-running produces an
identical file. Stock processors carry the live cluster's real standard-nar
coordinates (org.apache.nifi:nifi-standard-nar:2.6.0.4.3.4.0-234, read off
mynifi-0). The two custom Python processors carry best-effort bundle coordinates
(version = their ProcessorDetails.version); if you import this into NiFi and the
Python bundle isn't matched, re-select the bundle on each custom processor — or,
authoritatively, build the flow live via the API and re-export it.

    python3 build_flow_json.py   # writes flow-mattyb-image.json
"""
import json

STD = {"group": "org.apache.nifi", "artifact": "nifi-standard-nar",
       "version": "2.6.0.4.3.4.0-234"}
PY = {"group": "org.apache.nifi", "artifact": "python-extensions",
      "version": "0.0.1"}   # real coords read off mynifi-0's /flow/processor-types


def proc(pid, name, ptype, bundle, x, y, props, auto=None):
    return {
        "identifier": pid,
        "name": name,
        "type": ptype,
        "bundle": bundle,
        "position": {"x": x, "y": y},
        "properties": props,
        "propertyDescriptors": {},
        "style": {},
        "schedulingStrategy": "TIMER_DRIVEN",
        "schedulingPeriod": "0 sec",
        "penaltyDuration": "30 sec",
        "yieldDuration": "1 sec",
        "runDurationMillis": 0,
        "concurrentlySchedulableTaskCount": 1,
        "autoTerminatedRelationships": auto or [],
        "scheduledState": "ENABLED",
        "componentType": "PROCESSOR",
    }


def conn(cid, name, src, sname, dst, dname, rels, x=0, y=0):
    return {
        "identifier": cid,
        "name": name,
        "source": {"id": src, "type": "PROCESSOR", "name": sname},
        "destination": {"id": dst, "type": "PROCESSOR", "name": dname},
        "selectedRelationships": rels,
        "backPressureObjectThreshold": 10000,
        "backPressureDataSizeThreshold": "1 GB",
        "flowFileExpiration": "0 sec",
        "loadBalanceStrategy": "DO_NOT_LOAD_BALANCE",
        "partitioningAttribute": "",
        "loadBalanceCompression": "DO_NOT_COMPRESS",
        "componentType": "CONNECTION",
        "bends": [],
    }


# --- fixed component ids -----------------------------------------------------
P_GET   = "a1000000-0000-1000-8000-00000000000a"
P_DET   = "a1000000-0000-1000-8000-00000000000b"
P_CROP  = "a1000000-0000-1000-8000-00000000000c"
P_SPLIT = "a1000000-0000-1000-8000-00000000000d"
P_FETCH = "a1000000-0000-1000-8000-00000000000e"
P_PUT   = "a1000000-0000-1000-8000-00000000000f"
P_LOG   = "a1000000-0000-1000-8000-000000000010"

X = 400
processors = [
    proc(P_GET, "GetFile", "org.apache.nifi.processors.standard.GetFile", STD, X, 0,
         {"Input Directory": "/tmp/mattyb-in", "Keep Source File": "false",
          "File Filter": r"[^\.].*\.(png|jpg|jpeg)"}),
    proc(P_DET, "MattyBShapeDetector", "MattyBShapeDetector", PY, X, 200, {}),
    proc(P_CROP, "MattyBBoundingBoxCropper", "MattyBBoundingBoxCropper", PY, X, 400,
         {"Output Directory": "/tmp/mattyb"}),
    proc(P_SPLIT, "SplitJson", "org.apache.nifi.processors.standard.SplitJson", STD, X, 600,
         {"JsonPath Expression": "$.*"}, auto=["original", "failure"]),
    proc(P_FETCH, "FetchFile", "org.apache.nifi.processors.standard.FetchFile", STD, X, 800,
         {"File to Fetch": "${path}", "Completion Strategy": "None"}),
    proc(P_PUT, "PutFile", "org.apache.nifi.processors.standard.PutFile", STD, X, 1000,
         {"Directory": "/tmp/mattyb-out", "Conflict Resolution Strategy": "replace"},
         auto=["success", "failure"]),
    proc(P_LOG, "LogFailure", "org.apache.nifi.processors.standard.LogAttribute", STD,
         X + 400, 400, {"Log Level": "error"}, auto=["success"]),
]

connections = [
    conn("c0000000-0000-1000-8000-000000000001", "", P_GET, "GetFile", P_DET,
         "MattyBShapeDetector", ["success"]),
    conn("c0000000-0000-1000-8000-000000000002", "", P_DET, "MattyBShapeDetector", P_CROP,
         "MattyBBoundingBoxCropper", ["success"]),
    conn("c0000000-0000-1000-8000-000000000003", "", P_DET, "MattyBShapeDetector", P_LOG,
         "LogFailure", ["failure"]),
    conn("c0000000-0000-1000-8000-000000000004", "", P_CROP, "MattyBBoundingBoxCropper",
         P_SPLIT, "SplitJson", ["success"]),
    conn("c0000000-0000-1000-8000-000000000005", "", P_CROP, "MattyBBoundingBoxCropper",
         P_LOG, "LogFailure", ["failure"]),
    conn("c0000000-0000-1000-8000-000000000006", "", P_SPLIT, "SplitJson", P_FETCH,
         "FetchFile", ["split"]),
    conn("c0000000-0000-1000-8000-000000000007", "", P_FETCH, "FetchFile", P_PUT, "PutFile",
         ["success"]),
    conn("c0000000-0000-1000-8000-000000000008", "", P_FETCH, "FetchFile", P_LOG, "LogFailure",
         ["failure", "not.found", "permission.denied"]),
]

flow = {
    "flowContents": {
        "identifier": "b0000000-0000-1000-8000-000000000000",
        "instanceIdentifier": "b0000000-0000-1000-8000-000000000000",
        "name": "MattyBImageProcessor",
        "comments": "GetFile -> ShapeDetector -> BoundingBoxCropper -> SplitJson -> "
                    "FetchFile -> PutFile (LogFailure sink). SplitJson is the fan-out: "
                    "one manifest FlowFile becomes one FlowFile per crop.",
        "position": {"x": 0, "y": 0},
        "processGroups": [], "remoteProcessGroups": [], "inputPorts": [],
        "outputPorts": [], "labels": [], "funnels": [], "controllerServices": [],
        "variables": {}, "parameterContextName": None,
        "flowFileConcurrency": "UNBOUNDED", "flowFileOutboundPolicy": "STREAM_WHEN_AVAILABLE",
        "defaultFlowFileExpiration": "0 sec",
        "defaultBackPressureObjectThreshold": 10000,
        "defaultBackPressureDataSizeThreshold": "1 GB",
        "componentType": "PROCESS_GROUP",
        "processors": processors,
        "connections": connections,
    },
    "externalControllerServices": {},
    "parameterContexts": {},
    "parameterProviders": {},
    "flowEncodingVersion": "1.0",
    "latest": False,
}

if __name__ == "__main__":
    with open("flow-mattyb-image.json", "w") as f:
        json.dump(flow, f, indent=2)
    print(f"wrote flow-mattyb-image.json  ({len(processors)} processors, "
          f"{len(connections)} connections)")
