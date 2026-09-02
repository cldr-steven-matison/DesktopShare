#!/usr/bin/env python3
"""
Generates files/issue-289/flows/TelegramNotify.json — a REUSABLE root-level Process Group
that delivers a message to Telegram (#289, child of #76). Any logical PG on this box feeds it
through the notify-in input port; ReleaseVoteWatch is just the first caller.

  notify-in (INPUT PORT) → SendTelegram (custom Python processor) ─success→ (terminal)
                                                  └─failure→ LogNotifyFailure (warn — bulletin)

The caller writes the human message text as the FlowFile BODY and hands it off. SendTelegram
owns the credentials, the [Device] roster prefix, the 4096-char cap, JSON escaping, and the
POST. Callers never see the token. SendTelegram is a CUSTOM processor (not InvokeHTTP) so the
bot token — which Telegram forces into the URL path — never lands in provenance or in an
invokehttp.request.url attribute.

Deploy: (1) load files/issue-289/processors/SendTelegram.py into mynifi's python extensions
(files/issue-289/python-extensions-loader.yaml + the nifi-spark.yaml mount), (2) upload this PG
(skill: references/flow-registry.md), (3) set the sensitive Telegram Bot Token + Chat Id into
the TelegramNotify Parameter Context via the API from ~/.env (never inline, never GET-then-PUT),
(4) wire ReleaseVoteWatch's telegram-out → this PG's notify-in at the root. Re-export after any
live edit.

⚠️ SEND_TELEGRAM_TYPE / SEND_TELEGRAM_BUNDLE below are the coordinates NiFi assigns the loaded
Python processor. CONFIRM THEM LIVE before the upload:
    GET /nifi-api/flow/processor-types | jq '.processorTypes[]|select(.type|test("SendTelegram"))'
and correct the two constants if they differ, then regenerate.
"""
import json
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "TelegramNotify.json")
VER = "2.6.0.4.3.4.0-234"                     # CFM/NiFi bundle version on mynifi
PG_NAME = "TelegramNotify"
NS = uuid.UUID("2b8f7e10-1c3d-4a9e-9f77-289289289289")   # distinct namespace from #76's PG

# --- custom SendTelegram processor coordinates — CONFIRM LIVE (see header) -----
SEND_TELEGRAM_TYPE = "SendTelegram"
SEND_TELEGRAM_BUNDLE = {"group": "python", "artifact": "send-telegram", "version": "0.0.1"}

STD = {"group": "org.apache.nifi", "artifact": "nifi-standard-nar", "version": VER}


def uid(name):
    return str(uuid.uuid5(NS, name))


PG_ID = uid("pg")
processors, connections = [], []


def proc(name, typ, bundle, x, y, props, auto=(), dynamic=(), sensitive=(),
         schedule="0 sec", run_ms=0):
    processors.append({
        "identifier": uid(name), "name": name, "type": typ, "bundle": bundle,
        "componentType": "PROCESSOR", "groupIdentifier": PG_ID, "comments": "",
        "position": {"x": float(x), "y": float(y)},
        "properties": props,
        "propertyDescriptors": {k: {"name": k, "displayName": k, "dynamic": k in dynamic,
                                    "identifiesControllerService": False, "sensitive": k in sensitive}
                                for k in props},
        "autoTerminatedRelationships": list(auto),
        "schedulingPeriod": schedule, "schedulingStrategy": "TIMER_DRIVEN", "executionNode": "ALL",
        "penaltyDuration": "30 sec", "yieldDuration": "1 sec", "bulletinLevel": "WARN",
        "runDurationMillis": run_ms, "concurrentlySchedulableTaskCount": 1,
        "scheduledState": "ENABLED", "retryCount": 10, "retriedRelationships": [],
        "backoffMechanism": "PENALIZE_FLOWFILE", "maxBackoffPeriod": "10 mins", "style": {},
    })


def conn(src, rels, dst, expiration="0 sec", src_type="PROCESSOR", dst_type="PROCESSOR"):
    connections.append({
        "identifier": uid(f"conn:{src}:{','.join(rels)}:{dst}"), "name": "",
        "componentType": "CONNECTION", "groupIdentifier": PG_ID,
        "source": {"id": uid(src), "type": src_type, "groupId": PG_ID, "name": src, "comments": ""},
        "destination": {"id": uid(dst), "type": dst_type, "groupId": PG_ID, "name": dst, "comments": ""},
        "selectedRelationships": list(rels), "labelIndex": 1, "zIndex": 0, "bends": [],
        "backPressureObjectThreshold": 1000, "backPressureDataSizeThreshold": "1 GB",
        "flowFileExpiration": expiration, "prioritizers": [],
        "loadBalanceStrategy": "DO_NOT_LOAD_BALANCE", "loadBalanceCompression": "DO_NOT_COMPRESS",
    })


# ── the notifier ───────────────────────────────────────────────────────────────
# SendTelegram: token+chat+device from the Parameter Context, Dry Run on until creds land.
proc("SendTelegram", SEND_TELEGRAM_TYPE, SEND_TELEGRAM_BUNDLE, 0, 200, {
    "Bot Token": "#{Telegram Bot Token}",     # sensitive; resolved in-processor, never in provenance
    "Chat Id": "#{Telegram Chat Id}",
    "Device Name": "#{Device Name}",
    "Dry Run": "#{Telegram Dry Run}",         # 'true' until WindowsDesktop delivers creds (#293)
}, auto=("success",), sensitive=("Bot Token",))

# LogNotifyFailure: a dropped notification surfaces on the bulletin board at WARN. Scope the
# attributes-to-log-regex to telegram.* only — never log a URL attribute (defence-in-depth per
# #289, though SendTelegram never emits one).
proc("LogNotifyFailure", "org.apache.nifi.processors.standard.LogAttribute", STD, 600, 400, {
    "Log Level": "warn", "Log Payload": "true", "Log FlowFile Properties": "true",
    "Output Format": "Line per Attribute", "attributes-to-log-regex": "telegram\\..*",
    "character-set": "UTF-8",
}, auto=("success",))

conn("notify-in", [""], "SendTelegram", src_type="INPUT_PORT")   # a port's outbound rel is anonymous
conn("SendTelegram", ["failure"], "LogNotifyFailure")

# ── parameter context ──────────────────────────────────────────────────────────
# Telegram Bot Token: SENSITIVE, value null — set via the API after upload from ~/.env TOKEN
# (delivered by WindowsDesktop, #293). Telegram Chat Id: from ~/.env CHAT_ID, also set via API.
params = [
    ("Telegram Bot Token", None, "Sensitive — the shared fleet bot token; set via the API after "
        "upload from ~/.env TOKEN (delivered by WindowsDesktop #293). Never inline, never committed.", True),
    ("Telegram Chat Id", None, "Set via the API after upload from ~/.env CHAT_ID; the shared fleet chat.", False),
    ("Device Name", "NvidiaSpark-1", "Roster name prefixed to every message so no caller can drop "
        "the fleet attribution (agent/device-comms.md).", False),
    ("Telegram Dry Run", "true", "SendTelegram logs the intended send instead of posting while this "
        "is 'true'. Flip to 'false' once the token + chat id are set (after #293).", False),
]

flow = {
    "flowEncodingVersion": "1.0", "latest": False,
    "externalControllerServices": {}, "parameterProviders": {},
    "parameterContexts": {PG_NAME: {
        "componentType": "PARAMETER_CONTEXT", "name": PG_NAME,
        "description": "The shared Telegram bot credentials and device prefix the TelegramNotify PG uses (#289).",
        "inheritedParameterContexts": [],
        "parameters": [{"name": n, "value": v, "description": d, "sensitive": s, "provided": False}
                       for n, v, d, s in params],
    }},
    "flowContents": {
        "identifier": PG_ID, "name": PG_NAME, "componentType": "PROCESS_GROUP",
        "comments": "Reusable Telegram notifier (#289): any PG feeds the notify-in input port with "
                    "the message text as the FlowFile body; SendTelegram owns the token, the [Device] "
                    "prefix, the 4096 cap, and the send. Delivers a NOTIFICATION only — never a vote.",
        "position": {"x": 0.0, "y": 0.0}, "parameterContextName": PG_NAME,
        "processors": processors, "connections": connections, "controllerServices": [],
        "funnels": [], "labels": [], "processGroups": [], "remoteProcessGroups": [],
        "inputPorts": [{
            "identifier": uid("notify-in"), "name": "notify-in",
            "comments": "The only entrance — callers connect their output port here at the root.",
            "position": {"x": 0.0, "y": 0.0}, "type": "INPUT_PORT", "componentType": "INPUT_PORT",
            "groupIdentifier": PG_ID, "concurrentlySchedulableTaskCount": 1,
            "scheduledState": "ENABLED", "allowRemoteAccess": False, "portFunction": "STANDARD",
        }],
        "outputPorts": [],
        "scheduledState": "ENABLED", "defaultFlowFileExpiration": "0 sec",
        "defaultBackPressureObjectThreshold": 10000, "defaultBackPressureDataSizeThreshold": "1 GB",
        "executionEngine": "INHERITED", "flowFileConcurrency": "UNBOUNDED",
        "flowFileOutboundPolicy": "STREAM_WHEN_AVAILABLE", "maxConcurrentTasks": 1,
        "statelessFlowTimeout": "1 min",
    },
}

if __name__ == "__main__":
    json.dump(flow, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}: {len(processors)} processors, {len(connections)} connections, "
          f"{len(params)} parameters, 1 input port")
    print(f"SendTelegram coords (CONFIRM LIVE): type={SEND_TELEGRAM_TYPE} bundle={SEND_TELEGRAM_BUNDLE}")
