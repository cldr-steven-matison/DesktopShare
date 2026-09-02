#!/usr/bin/env python3
"""
Generates files/issue-76/flows/ReleaseVoteWatch.json — the release-vote watch/build/recommend
Process Group for the Spark's mynifi (#76, nifi-release-vote-automation.md). Upload with the
NiFi REST API (skill: references/flow-api.md §3), set the two sensitive parameters afterwards
(IMAP Password from ~/.env SCENESERVER_IMAP_PASSWORD; k8s Dispatcher Token from the
release-build-dispatcher-token Secret), enable the controller service, start the PG.
After any live edit, re-export over ReleaseVoteWatch.json (§4).

Pipeline (doc §Architecture): watch → assess/verify → build (k8s Job) → test → recommend.
HARD BOUNDARY: this flow never sends mail — the terminus is a bulletin + Kafka topic.

Shape: one vertical trunk at x=0, rows of 200. The four product legs fan out at y=1400
(x = -900/-300/+300/+900, 600px sibling pitch) and re-join the trunk at y=1600 — the join
sits at the centre of the spread, so no merge line crosses the trunk. Error/terminal log
sinks live to the RIGHT of every working column (LogFailures hard right at x=1360), so
their inbound lines never cross the flow either.

  WatchDevList        ConsumeIMAP        steven@sceneserver.net INBOX, IMAPS 993, poll 2 min,
                                         Mark-as-Read = the primary dedup
  ExtractHeaders      ExtractEmailHeaders→ email.headers.subject / message-id
  NormalizeSubject    UpdateAttribute    vote.subject = subject minus any leading Fwd:/Fw:
                                         (Steven's forwarded test samples; harmless live)
  RouteVoteFilter     RouteOnAttribute   vote = starts-with '[VOTE] Release Apache NiFi'
                                         minus [RESULT]/[CANCEL]/[LAZY]; retire = [CANCEL]/[RESULT]
  DedupGuard          UpdateAttribute    stateful seen.subjects guard (belt-and-suspenders)
  RouteDup            RouteOnAttribute   new vs duplicate
  RouteProductLeg     RouteOnAttribute   cpp / api / nar / core (appendix taxonomy table)
  TagLeg*             UpdateAttribute    system/leg/gitRepo — all four legs are live and
                                         re-join the trunk (nothing is deferred any more)
  ParseVoteBody       ExtractText        rc.staging.url / rc.git.tag / rc.git.commit / rc.sha512
                                         / rc.keys.url (labeled-line regexes from the appendix)
  CheckParsed         RouteOnAttribute   both staging URL + tag present, else LogParseDrift
  PrepJobMeta         UpdateAttribute    k8s.job.name = rvb-<leg>-<epoch>
  RouteLegManifest    RouteOnAttribute   cpp / core / maven — picks the Job manifest
  BuildJobManifest    ReplaceText        cpp Job JSON (release-build-cpp image, 8 CPU/24Gi)
  BuildMavenManifest  ReplaceText        API + NAR Job JSON (stock maven image, 4 CPU/8Gi)
  BuildCoreManifest   ReplaceText        apache/nifi Job JSON — the whole quota (8 CPU/24Gi),
                                         #{Core Maven Args} / #{Core Maven Opts}
  DispatchJob         InvokeHTTP POST    k3s API, Bearer #{k8s Dispatcher Token} (sensitive
                                         dynamic property), K8sApiTrust CA     [Retry self-loop]
  PollJobStatus       InvokeHTTP GET     job status, 1-min schedule            [Retry self-loop]
  ExtractJobStatus    EvaluateJsonPath   .status.succeeded/.failed/.active
  RouteJobDone        RouteOnAttribute   ok / fail; still-running loops back to PollJobStatus on
                                         a 4 HOUR expiration connection — deliberate exception to
                                         the 10-min default: source builds are legitimately hours
  MarkBuild*          UpdateAttribute    job.outcome
  FetchJobPods        InvokeHTTP GET     pods by job-name label
  ExtractPodName      EvaluateJsonPath   $.items[0].metadata.name
  FetchPodLog         InvokeHTTP GET     pod log tail (the entrypoint's last line is the verdict)
  ExtractResultJson   ExtractText        job.result = {"verifyOk"...}; unmatched → MarkNoResult
  ExtractVerdict      UpdateAttribute    verify.ok/build.ok/smoke.ok via jsonPath()
  BuildRecommendation ReplaceText        the evidence + '+1/-1 suggestion' JSON (aarch64 caveat)
  RouteVerdict        RouteOnAttribute   pass → LogRecommendation (info) / LogFailedVerdict (warn)
  PublishRecommendation PublishKafka_2_6 → release_vote_recommendations, key = vote.subject
  ── log column (x=700): LogRejected, LogRetired, LogDuplicate, LogDeferredLeg, LogParseDrift,
     LogFailures (warn — the bulletin surface)
"""
import json
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ReleaseVoteWatch.json")
CA_PEM_FILE = os.path.join(HERE, "k8s-ca.pem")
VER = "2.6.0.4.3.4.0-234"
PG_NAME = "ReleaseVoteWatch"
NS = uuid.UUID("9c4d1b2a-0e5f-4a7c-8b3d-76aa76aa76aa")


def uid(name):
    return str(uuid.uuid5(NS, name))


PG_ID = uid("pg")
STD = {"group": "org.apache.nifi", "artifact": "nifi-standard-nar", "version": VER}
UPD = {"group": "org.apache.nifi", "artifact": "nifi-update-attribute-nar", "version": VER}
EMAIL = {"group": "org.apache.nifi", "artifact": "nifi-email-nar", "version": VER}
KAFKA26 = {"group": "org.apache.nifi", "artifact": "nifi-kafka-2-6-nar", "version": VER}

# ── controller service: trust for the in-cluster k3s API endpoint ─────────────
CS_K8S_TLS = uid("cs-k8s-tls")

controller_services = [{
    "identifier": CS_K8S_TLS, "name": "K8sApiTrust",
    "type": "org.apache.nifi.ssl.PEMEncodedSSLContextProvider", "componentType": "CONTROLLER_SERVICE",
    "bundle": {"group": "org.apache.nifi", "artifact": "nifi-ssl-context-service-nar", "version": VER},
    "controllerServiceApis": [{"type": "org.apache.nifi.ssl.SSLContextProvider",
                               "bundle": {"group": "org.apache.nifi",
                                          "artifact": "nifi-standard-services-api-nar", "version": VER}}],
    "groupIdentifier": PG_ID, "comments": "Trusts only the k3s cluster CA (#{k8s Cluster CA}).",
    "bulletinLevel": "WARN", "scheduledState": "ENABLED",
    "properties": {"TLS Protocol": "TLS", "Private Key Source": "UNDEFINED",
                   "Certificate Authorities Source": "PROPERTIES",
                   "Certificate Authorities": "#{k8s Cluster CA}"},
    "propertyDescriptors": {k: {"name": k, "displayName": k, "dynamic": False,
                                "identifiesControllerService": False, "sensitive": False}
                            for k in ("TLS Protocol", "Private Key Source",
                                      "Certificate Authorities Source", "Certificate Authorities")},
}]

# ── processors ────────────────────────────────────────────────────────────────
processors, connections = [], []


def proc(name, typ, bundle, x, y, props, auto=(), services=(), dynamic=(), sensitive=(),
         schedule="0 sec", run_ms=0):
    p = {
        "identifier": uid(name), "name": name, "type": typ, "bundle": bundle,
        "componentType": "PROCESSOR", "groupIdentifier": PG_ID, "comments": "",
        "position": {"x": float(x), "y": float(y)},
        "properties": props,
        "propertyDescriptors": {k: {"name": k, "displayName": k, "dynamic": k in dynamic,
                                    "identifiesControllerService": k in services,
                                    "sensitive": k in sensitive}
                                for k in props},
        "autoTerminatedRelationships": list(auto),
        "schedulingPeriod": schedule, "schedulingStrategy": "TIMER_DRIVEN", "executionNode": "ALL",
        "penaltyDuration": "30 sec", "yieldDuration": "1 sec", "bulletinLevel": "WARN",
        "runDurationMillis": run_ms, "concurrentlySchedulableTaskCount": 1,
        "scheduledState": "ENABLED", "retryCount": 10, "retriedRelationships": [],
        "backoffMechanism": "PENALIZE_FLOWFILE", "maxBackoffPeriod": "10 mins", "style": {},
    }
    processors.append(p)
    return p


def conn(src, rels, dst, expiration="0 sec"):
    s, d = uid(src), uid(dst)
    connections.append({
        "identifier": uid(f"conn:{src}:{','.join(rels)}:{dst}"), "name": "", "componentType": "CONNECTION",
        "groupIdentifier": PG_ID,
        "source": {"id": s, "type": "PROCESSOR", "groupId": PG_ID, "name": src, "comments": ""},
        "destination": {"id": d, "type": "PROCESSOR", "groupId": PG_ID, "name": dst, "comments": ""},
        "selectedRelationships": list(rels), "labelIndex": 1, "zIndex": 0, "bends": [],
        "backPressureObjectThreshold": 1000, "backPressureDataSizeThreshold": "1 GB",
        "flowFileExpiration": expiration, "prioritizers": [],
        "loadBalanceStrategy": "DO_NOT_LOAD_BALANCE", "loadBalanceCompression": "DO_NOT_COMPRESS",
    })


def route_on_attr(name, x, y, routes):
    props = {"Routing Strategy": "Route to Property name"}
    props.update(routes)
    return proc(name, "org.apache.nifi.processors.standard.RouteOnAttribute", STD, x, y, props,
                dynamic=tuple(routes))


def update_attr(name, x, y, attrs, stateful=False):
    props = {"Delete Attributes Expression": None,
             "Store State": "Store state locally" if stateful else "Do not store state"}
    if stateful:
        props["Stateful Variables Initial Value"] = ""
    props.update(attrs)
    return proc(name, "org.apache.nifi.processors.attributes.UpdateAttribute", UPD, x, y, props,
                dynamic=tuple(attrs), run_ms=25)


def replace_text(name, x, y, value):
    return proc(name, "org.apache.nifi.processors.standard.ReplaceText", STD, x, y, {
        "Replacement Strategy": "Always Replace", "Evaluation Mode": "Entire text",
        "Regular Expression": "(?s)(^.*$)", "Replacement Value": value,
        "Character Set": "UTF-8", "Maximum Buffer Size": "10 MB", "Line-by-Line Evaluation Mode": "All",
    }, run_ms=25)


def eval_json(name, x, y, paths):
    props = {"Destination": "flowfile-attribute", "Return Type": "json",
             "Path Not Found Behavior": "ignore", "Null Value Representation": "empty string",
             "Max String Length": "20 MB"}
    props.update(paths)
    return proc(name, "org.apache.nifi.processors.standard.EvaluateJsonPath", STD, x, y, props,
                dynamic=tuple(paths))


def invoke_k8s(name, x, y, method, url, schedule="0 sec", body=False):
    """InvokeHTTP against the k3s API: CA-pinned TLS + Bearer token as a SENSITIVE dynamic
    property (InvokeHTTP supportsSensitiveDynamicProperties=true on this build — a plain
    dynamic header could not reference the sensitive #{k8s Dispatcher Token})."""
    return proc(name, "org.apache.nifi.processors.standard.InvokeHTTP", STD, x, y, {
        "HTTP Method": method, "HTTP URL": url,
        "SSL Context Service": CS_K8S_TLS,
        "Request Content-Type": "application/json",
        "Request Body Enabled": "true" if body else "false",
        "Connection Timeout": "10 secs", "Socket Read Timeout": "30 secs",
        "Socket Write Timeout": "30 secs",
        "Response Generation Required": "false", "Response Redirects Enabled": "True",
        "Request Failure Penalization Enabled": "false", "Request Date Header Enabled": "True",
        "Request Chunked Transfer-Encoding Enabled": "false", "Request Content-Encoding": "DISABLED",
        "Response Cookie Strategy": "DISABLED", "Response Cache Enabled": "false",
        "Response FlowFile Naming Strategy": "RANDOM", "HTTP/2 Disabled": "False",
        "Authorization": "Bearer #{k8s Dispatcher Token}",
    }, auto=("Original",), services=("SSL Context Service",),
       dynamic=("Authorization",), sensitive=("Authorization",), schedule=schedule)


def log_attr(name, x, y, level):
    return proc(name, "org.apache.nifi.processors.standard.LogAttribute", STD, x, y, {
        "Log Level": level, "Log Payload": "true", "Log FlowFile Properties": "true",
        "Output Format": "Line per Attribute", "attributes-to-log-regex": ".*", "character-set": "UTF-8",
    }, auto=("success",))


# ── Stage 1: watch ────────────────────────────────────────────────────────────
proc("WatchDevList", "org.apache.nifi.processors.email.ConsumeIMAP", EMAIL, 0, 0, {
    "host": "#{IMAP Host}", "port": "#{IMAP Port}",
    "authorization-mode": "password-based-authorization-mode",
    "user": "#{IMAP User}", "password": "#{IMAP Password}",
    "folder": "#{IMAP Folder}", "fetch.size": "10", "delete.messages": "false",
    "connection.timeout": "30 sec", "Mark Messages as Read": "true", "Use SSL": "true",
}, sensitive=("password",), schedule="2 min")

proc("ExtractHeaders", "org.apache.nifi.processors.email.ExtractEmailHeaders", EMAIL, 0, 200, {
    "CAPTURED_HEADERS": "x-mailer", "STRICT_ADDRESS_PARSING": "false",
})

update_attr("NormalizeSubject", 0, 400, {
    "vote.subject": "${email.headers.subject:trim():replaceAll('(?i)^(fwd?:\\s*)+', '')}",
})

route_on_attr("RouteVoteFilter", 0, 600, {
    "vote": "${vote.subject:startsWith('[VOTE] Release Apache NiFi')"
            ":and(${vote.subject:contains('[RESULT]'):not()})"
            ":and(${vote.subject:contains('[CANCEL]'):not()})"
            ":and(${vote.subject:contains('[LAZY]'):not()})}",
    "retire": "${vote.subject:startsWith('[CANCEL][VOTE] Release Apache NiFi')"
              ":or(${vote.subject:startsWith('[RESULT][VOTE] Release Apache NiFi')})}",
})

# Stateful guard: vote.dup reads the PREVIOUS state; seen.subjects then re-stores with this
# subject appended. Mark-as-Read on ConsumeIMAP is the primary dedup — this only catches a
# re-delivered/re-forwarded copy of a subject already seen (state survives pod restarts only
# as well as the state provider does; it is belt-and-suspenders, not the mechanism).
update_attr("DedupGuard", 0, 800, {
    "vote.dup": "${getStateValue('seen.subjects'):contains(${vote.subject})}",
    "seen.subjects": "${getStateValue('seen.subjects'):append(' | '):append(${vote.subject})}",
}, stateful=True)

route_on_attr("RouteDup", 0, 1000, {
    "new": "${vote.dup:equals('true'):not()}",
})

route_on_attr("RouteProductLeg", 0, 1200, {
    "cpp": "${vote.subject:contains('MiNiFi C++')}",
    "api": "${vote.subject:contains('Apache NiFi API')}",
    "nar": "${vote.subject:contains('NAR Maven Plugin')}",
    "core": "${vote.subject:contains('MiNiFi C++'):not()"
            ":and(${vote.subject:contains('Apache NiFi API'):not()})"
            ":and(${vote.subject:contains('NAR Maven Plugin'):not()})}",
})

update_attr("TagLegCpp", -900, 1400, {"system": "minifi", "leg": "cpp", "gitRepo": "apache/nifi-minifi-cpp"})
update_attr("TagLegApi", -300, 1400, {"system": "nifi", "leg": "java-api", "gitRepo": "apache/nifi-api"})
update_attr("TagLegNar", 300, 1400, {"system": "nifi", "leg": "java-nar", "gitRepo": "apache/nifi-maven"})
update_attr("TagLegCore", 900, 1400, {"system": "nifi", "leg": "java-core", "gitRepo": "apache/nifi"})

# ── Stage 2: assess (cpp leg only for now — Maven legs deferred to their dry-run) ──
# ConsumeIMAP emits the RAW RFC822 message; list mail and forwarded samples alike are
# quoted-printable (soft `=\r\n` line breaks, `=3D` escapes) — verified live 2026-09-01
# against a forwarded Gmail sample (multipart/alternative, both parts quoted-printable).
# Two content passes un-QP the body enough for the labeled-line regexes: unwrap soft
# breaks, then decode `=3D`. (Full QP decode isn't needed for these ASCII targets.)
replace_qp = proc("UnwrapQpBreaks", "org.apache.nifi.processors.standard.ReplaceText", STD, 0, 1600, {
    "Replacement Strategy": "Regex Replace", "Evaluation Mode": "Entire text",
    "Regular Expression": "=\\r?\\n", "Replacement Value": "",
    "Character Set": "UTF-8", "Maximum Buffer Size": "10 MB", "Line-by-Line Evaluation Mode": "All",
}, run_ms=25)

proc("DecodeQpEquals", "org.apache.nifi.processors.standard.ReplaceText", STD, 0, 1800, {
    "Replacement Strategy": "Regex Replace", "Evaluation Mode": "Entire text",
    "Regular Expression": "=3D", "Replacement Value": "=",
    "Character Set": "UTF-8", "Maximum Buffer Size": "10 MB", "Line-by-Line Evaluation Mode": "All",
}, run_ms=25)

proc("ParseVoteBody", "org.apache.nifi.processors.standard.ExtractText", STD, 0, 2000, {
    "Character Set": "UTF-8", "Maximum Buffer Size": "1 MB", "Maximum Capture Group Length": "1024",
    "Enable Case-insensitive Matching": "false", "Enable Multiline Mode": "true",
    "Enable DOTALL Mode": "false", "Include Capture Group 0": "false",
    "rc.staging.url": "(https://dist\\.apache\\.org/repos/dist/dev/nifi/[^\\s\"<>]+)",
    "rc.git.tag": "Git [Tt]ag(?::| is)\\s*(\\S+)",
    "rc.git.commit": "Git [Cc]ommit ID(?::| is)\\s*([0-9a-fA-F]{7,40})",
    "rc.sha512": "SHA512[^0-9a-fA-F]{0,80}([0-9a-fA-F]{128})",
    "rc.keys.url": "(https://dist\\.apache\\.org/repos/dist/release/nifi/KEYS)",
}, dynamic=("rc.staging.url", "rc.git.tag", "rc.git.commit", "rc.sha512", "rc.keys.url"))

route_on_attr("CheckParsed", 0, 2200, {
    "parsed": "${rc.staging.url:isEmpty():not():and(${rc.git.tag:isEmpty():not()})}",
})

# ── Stage 3: dispatch as a k8s Job ────────────────────────────────────────────
update_attr("PrepJobMeta", 0, 2400, {
    "k8s.job.name": "rvb-${leg}-${now():toNumber()}",
    "mime.type": "application/json",
})

route_on_attr("RouteLegManifest", 0, 2600, {
    "cpp": "${leg:equals('cpp')}",
    "core": "${leg:equals('java-core')}",
    "maven": "${leg:startsWith('java-'):and(${leg:equals('java-core'):not()})}",
})

replace_text("BuildJobManifest", -600, 2800, json.dumps({
    "apiVersion": "batch/v1", "kind": "Job",
    "metadata": {"name": "${k8s.job.name}", "namespace": "release-builds",
                 "labels": {"leg": "${leg}", "system": "${system}", "source": "releasevotewatch"}},
    "spec": {"backoffLimit": 0, "ttlSecondsAfterFinished": 86400,
             "template": {"spec": {"restartPolicy": "Never", "containers": [{
                 "name": "build", "image": "#{Build Image Cpp}", "imagePullPolicy": "Never",
                 "env": [
                     {"name": "TAG", "value": "${rc.git.tag:escapeJson()}"},
                     {"name": "ARTIFACT_URL", "value": "${rc.staging.url:escapeJson()}"},
                     {"name": "SHA512", "value": "${rc.sha512:escapeJson()}"},
                     {"name": "KEYS_URL", "value": "${rc.keys.url:isEmpty():ifElse('https://dist.apache.org/repos/dist/release/nifi/KEYS', ${rc.keys.url}):escapeJson()}"},
                 ],
                 "resources": {"requests": {"cpu": "4", "memory": "8Gi"},
                               "limits": {"cpu": "8", "memory": "24Gi"}},
             }]}}},
}, separators=(",", ":")))

replace_text("BuildMavenManifest", 0, 2800, json.dumps({
    "apiVersion": "batch/v1", "kind": "Job",
    "metadata": {"name": "${k8s.job.name}", "namespace": "release-builds",
                 "labels": {"leg": "${leg}", "system": "${system}", "source": "releasevotewatch"}},
    "spec": {"backoffLimit": 0, "ttlSecondsAfterFinished": 86400,
             "template": {"spec": {"restartPolicy": "Never", "containers": [{
                 "name": "build", "image": "#{Build Image Maven}", "imagePullPolicy": "IfNotPresent",
                 "command": ["bash", "/entry/entrypoint.sh"],
                 "env": [
                     {"name": "TAG", "value": "${rc.git.tag:escapeJson()}"},
                     {"name": "ARTIFACT_URL", "value": "${rc.staging.url:escapeJson()}"},
                     {"name": "SHA512", "value": "${rc.sha512:escapeJson()}"},
                     {"name": "KEYS_URL", "value": "${rc.keys.url:isEmpty():ifElse('https://dist.apache.org/repos/dist/release/nifi/KEYS', ${rc.keys.url}):escapeJson()}"},
                     {"name": "GIT_REPO", "value": "${gitRepo}"},
                 ],
                 "volumeMounts": [{"name": "entry", "mountPath": "/entry"}],
                 "resources": {"requests": {"cpu": "2", "memory": "4Gi"},
                               "limits": {"cpu": "4", "memory": "8Gi"}},
             }],
             "volumes": [{"name": "entry", "configMap": {"name": "maven-build-entrypoint"}}]}}},
}, separators=(",", ":")))

replace_text("BuildCoreManifest", 600, 2800, json.dumps({
    "apiVersion": "batch/v1", "kind": "Job",
    "metadata": {"name": "${k8s.job.name}", "namespace": "release-builds",
                 "labels": {"leg": "${leg}", "system": "${system}", "source": "releasevotewatch"}},
    "spec": {"backoffLimit": 0, "ttlSecondsAfterFinished": 86400,
             "template": {"spec": {"restartPolicy": "Never", "containers": [{
                 "name": "build", "image": "#{Build Image Maven}", "imagePullPolicy": "IfNotPresent",
                 "command": ["bash", "/entry/entrypoint.sh"],
                 "env": [
                     {"name": "TAG", "value": "${rc.git.tag:escapeJson()}"},
                     {"name": "ARTIFACT_URL", "value": "${rc.staging.url:escapeJson()}"},
                     {"name": "SHA512", "value": "${rc.sha512:escapeJson()}"},
                     {"name": "KEYS_URL", "value": "${rc.keys.url:isEmpty():ifElse('https://dist.apache.org/repos/dist/release/nifi/KEYS', ${rc.keys.url}):escapeJson()}"},
                     {"name": "GIT_REPO", "value": "${gitRepo}"},
                     {"name": "MAVEN_ARGS", "value": "#{Core Maven Args}"},
                     {"name": "MAVEN_OPTS", "value": "#{Core Maven Opts}"},
                 ],
                 "volumeMounts": [{"name": "entry", "mountPath": "/entry"}],
                 "resources": {"requests": {"cpu": "8", "memory": "16Gi"},
                               "limits": {"cpu": "8", "memory": "24Gi"}},
             }],
             "volumes": [{"name": "entry", "configMap": {"name": "maven-build-entrypoint"}}]}}},
}, separators=(",", ":")))

invoke_k8s("DispatchJob", 0, 3000, "POST",
           "#{k8s API Base}/apis/batch/v1/namespaces/release-builds/jobs", body=True)

# ── poll loop (the 4h expiration lives on the loop-back connection) ───────────
invoke_k8s("PollJobStatus", 0, 3200, "GET",
           "#{k8s API Base}/apis/batch/v1/namespaces/release-builds/jobs/${k8s.job.name}",
           schedule="1 min")

eval_json("ExtractJobStatus", 0, 3400, {
    "job.succeeded": "$.status.succeeded", "job.failed": "$.status.failed",
    "job.active": "$.status.active",
})

route_on_attr("RouteJobDone", 0, 3600, {
    "ok": "${job.succeeded:gt(0)}",
    "fail": "${job.failed:gt(0)}",
})

# ── Stage 4: read the Job's verdict out of its pod log ────────────────────────
update_attr("MarkBuildSucceeded", -300, 3800, {"job.outcome": "succeeded"})
update_attr("MarkBuildFailed", 300, 3800, {"job.outcome": "failed"})

invoke_k8s("FetchJobPods", 0, 4000, "GET",
           "#{k8s API Base}/api/v1/namespaces/release-builds/pods?labelSelector=job-name%3D${k8s.job.name}")

eval_json("ExtractPodName", 0, 4200, {"pod.name": "$.items[0].metadata.name"})

invoke_k8s("FetchPodLog", 0, 4400, "GET",
           "#{k8s API Base}/api/v1/namespaces/release-builds/pods/${pod.name}/log?tailLines=60")

proc("ExtractResultJson", "org.apache.nifi.processors.standard.ExtractText", STD, 0, 4600, {
    "Character Set": "UTF-8", "Maximum Buffer Size": "1 MB", "Maximum Capture Group Length": "4096",
    "Enable Multiline Mode": "true", "Enable DOTALL Mode": "false", "Include Capture Group 0": "false",
    "job.result": "(\\{\"verifyOk\".*\\})",
}, dynamic=("job.result",))

update_attr("MarkNoResult", 600, 4800,
            {"job.note": "no result JSON in job log", "verify.ok": "false",
             "build.ok": "false", "smoke.ok": "false", "ext.count": "0"})

update_attr("ExtractVerdict", 0, 4800, {
    "verify.ok": "${job.result:jsonPath('$.verifyOk')}",
    "build.ok": "${job.result:jsonPath('$.buildOk')}",
    "smoke.ok": "${job.result:jsonPath('$.smokeOk')}",
    "ext.count": "${job.result:jsonPath('$.extensionCount')}",
    "job.note": "${job.result:jsonPath('$.note')}",
})

# ── Stage 5: recommend (a SUGGESTION — the human casts the vote) ──────────────
replace_text("BuildRecommendation", 0, 5000,
    '{"subject":"${vote.subject:escapeJson()}","leg":"${leg}","system":"${system}",'
    '"gitRepo":"${gitRepo}","tag":"${rc.git.tag:escapeJson()}","commit":"${rc.git.commit:escapeJson()}",'
    '"stagingUrl":"${rc.staging.url:escapeJson()}","jobName":"${k8s.job.name}",'
    '"jobOutcome":"${job.outcome}","verifyOk":"${verify.ok}","buildOk":"${build.ok}",'
    '"smokeOk":"${smoke.ok}","extensionCount":"${ext.count}","note":"${job.note:escapeJson()}",'
    '"recommendation":"${verify.ok:equals(\'true\'):and(${build.ok:equals(\'true\')})'
    ':and(${smoke.ok:equals(\'true\')}):ifElse(\'+1 suggested — all gates green\','
    '\'-1/0 suggested — a gate failed, read the evidence\')}",'
    '"caveat":"Built and smoke-tested on aarch64 (GB10); the RC reference binaries are x86 — weigh accordingly.",'
    '"emittedBy":"ReleaseVoteWatch on spark-dd06 — recommendation only, never a vote"}')

route_on_attr("RouteVerdict", 0, 5200, {
    "pass": "${verify.ok:equals('true'):and(${build.ok:equals('true')})"
            ":and(${smoke.ok:equals('true')})}",
})

log_attr("LogRecommendation", -300, 5400, "info")
log_attr("LogFailedVerdict", 300, 5400, "warn")
processors[-1]["autoTerminatedRelationships"] = []
processors[-2]["autoTerminatedRelationships"] = []

proc("PublishRecommendation", "org.apache.nifi.processors.kafka.pubsub.PublishKafka_2_6", KAFKA26,
     0, 5600, {
    "bootstrap.servers": "#{Kafka Bootstrap}", "topic": "#{Recommendations Topic}",
    "use-transactions": "false", "Failure Strategy": "Route to Failure", "acks": "all",
    "kafka-key": "${vote.subject}", "key-attribute-encoding": "utf-8",
    "max.request.size": "1 MB", "ack.wait.time": "5 secs", "max.block.ms": "5 sec",
    "compression.type": "none", "security.protocol": "PLAINTEXT",
}, auto=("success",))

# ── log column (x=700) ────────────────────────────────────────────────────────
log_attr("LogRejected", 1500, 1400, "info")
log_attr("LogRetired", 700, 800, "info")
log_attr("LogDuplicate", 700, 1000, "info")
log_attr("LogParseDrift", 900, 2400, "warn")
log_attr("LogFailures", 1360, 5600, "warn")

# ── wiring ────────────────────────────────────────────────────────────────────
conn("WatchDevList", ["success"], "ExtractHeaders")
conn("ExtractHeaders", ["success"], "NormalizeSubject")
conn("ExtractHeaders", ["failure"], "LogRejected")
conn("NormalizeSubject", ["success"], "RouteVoteFilter")
conn("RouteVoteFilter", ["vote"], "DedupGuard")
conn("RouteVoteFilter", ["retire"], "LogRetired")     # future: clear the dedup state key
conn("RouteVoteFilter", ["unmatched"], "LogRejected")
conn("DedupGuard", ["success"], "RouteDup")
conn("DedupGuard", ["set state fail"], "LogFailures")   # stateful mode adds this relationship
conn("RouteDup", ["new"], "RouteProductLeg")
conn("RouteDup", ["unmatched"], "LogDuplicate")
conn("RouteProductLeg", ["cpp"], "TagLegCpp")
conn("RouteProductLeg", ["api"], "TagLegApi")
conn("RouteProductLeg", ["nar"], "TagLegNar")
conn("RouteProductLeg", ["core"], "TagLegCore")
conn("RouteProductLeg", ["unmatched"], "LogRejected")
conn("TagLegCpp", ["success"], "UnwrapQpBreaks")
conn("UnwrapQpBreaks", ["success"], "DecodeQpEquals")
conn("UnwrapQpBreaks", ["failure"], "LogFailures")
conn("DecodeQpEquals", ["success"], "ParseVoteBody")
conn("DecodeQpEquals", ["failure"], "LogFailures")
conn("TagLegApi", ["success"], "UnwrapQpBreaks")
conn("TagLegNar", ["success"], "UnwrapQpBreaks")
conn("TagLegCore", ["success"], "UnwrapQpBreaks")
conn("ParseVoteBody", ["matched"], "CheckParsed")
conn("ParseVoteBody", ["unmatched"], "LogParseDrift")
conn("CheckParsed", ["parsed"], "PrepJobMeta")
conn("CheckParsed", ["unmatched"], "LogParseDrift")
conn("PrepJobMeta", ["success"], "RouteLegManifest")
conn("RouteLegManifest", ["cpp"], "BuildJobManifest")
conn("RouteLegManifest", ["maven"], "BuildMavenManifest")
conn("RouteLegManifest", ["core"], "BuildCoreManifest")
conn("RouteLegManifest", ["unmatched"], "LogFailures")
conn("BuildMavenManifest", ["success"], "DispatchJob")
conn("BuildMavenManifest", ["failure"], "LogFailures")
conn("BuildCoreManifest", ["success"], "DispatchJob")
conn("BuildCoreManifest", ["failure"], "LogFailures")
conn("BuildJobManifest", ["success"], "DispatchJob")
conn("BuildJobManifest", ["failure"], "LogFailures")
conn("DispatchJob", ["Retry"], "DispatchJob", "10 mins")
conn("DispatchJob", ["Response"], "PollJobStatus")
conn("DispatchJob", ["Failure", "No Retry"], "LogFailures")
conn("PollJobStatus", ["Retry"], "PollJobStatus", "10 mins")
conn("PollJobStatus", ["Response"], "ExtractJobStatus")
conn("PollJobStatus", ["Failure", "No Retry"], "LogFailures")
conn("ExtractJobStatus", ["matched", "unmatched"], "RouteJobDone")
conn("ExtractJobStatus", ["failure"], "LogFailures")
conn("RouteJobDone", ["ok"], "MarkBuildSucceeded")
conn("RouteJobDone", ["fail"], "MarkBuildFailed")
# Still running → poll again. 4 HOURS, not the 10-min default: source builds run for hours;
# this expiration is the build-watch timeout, and expiry surfaces as a dropped-FlowFile stat.
conn("RouteJobDone", ["unmatched"], "PollJobStatus", "4 hours")
conn("MarkBuildSucceeded", ["success"], "FetchJobPods")
conn("MarkBuildFailed", ["success"], "FetchJobPods")
conn("FetchJobPods", ["Response"], "ExtractPodName")
conn("FetchJobPods", ["Retry"], "FetchJobPods", "10 mins")
conn("FetchJobPods", ["Failure", "No Retry"], "LogFailures")
conn("ExtractPodName", ["matched"], "FetchPodLog")
conn("ExtractPodName", ["unmatched", "failure"], "LogFailures")
conn("FetchPodLog", ["Response"], "ExtractResultJson")
conn("FetchPodLog", ["Retry"], "FetchPodLog", "10 mins")
conn("FetchPodLog", ["Failure", "No Retry"], "LogFailures")
conn("ExtractResultJson", ["matched"], "ExtractVerdict")
conn("ExtractResultJson", ["unmatched"], "MarkNoResult")
conn("MarkNoResult", ["success"], "BuildRecommendation")
conn("ExtractVerdict", ["success"], "BuildRecommendation")
conn("BuildRecommendation", ["success"], "RouteVerdict")
conn("BuildRecommendation", ["failure"], "LogFailures")
conn("RouteVerdict", ["pass"], "LogRecommendation")
conn("RouteVerdict", ["unmatched"], "LogFailedVerdict")
conn("LogRecommendation", ["success"], "PublishRecommendation")
conn("LogFailedVerdict", ["success"], "PublishRecommendation")
conn("PublishRecommendation", ["failure"], "LogFailures")

# ── parameter context ─────────────────────────────────────────────────────────
try:
    K8S_CA = open(CA_PEM_FILE).read().strip()
except FileNotFoundError:
    K8S_CA = ""   # set via the parameter-context API after upload

params = [
    ("IMAP Host", "sceneserver.net", "cPanel mail host (Dovecot); MX for sceneserver.net is itself.", False),
    ("IMAP Port", "993", "IMAPS.", False),
    ("IMAP User", "steven@sceneserver.net", "The identity subscribed to dev@nifi.apache.org — the same identity the human votes from.", False),
    ("IMAP Password", None, "Sensitive — set via the API after upload from ~/.env SCENESERVER_IMAP_PASSWORD; never in this file.", True),
    ("IMAP Folder", "INBOX", "Folder ConsumeIMAP watches; switch if a server-side filter pre-sorts dev@ mail.", False),
    ("k8s API Base", "https://kubernetes.default.svc", "In-cluster k3s API endpoint.", False),
    ("k8s Cluster CA", K8S_CA, "k3s cluster CA (public cert, valid to 2036) — pinned by the K8sApiTrust service.", False),
    ("k8s Dispatcher Token", None, "Sensitive — release-build-dispatcher SA token (secret release-build-dispatcher-token, ns release-builds); set via the API after upload.", True),
    ("Kafka Bootstrap", "my-cluster-kafka-bootstrap.cld-streaming.svc:9092", "The box's my-cluster, internal listener.", False),
    ("Recommendations Topic", "release_vote_recommendations", "Stage 5 terminus (files/issue-76/release_vote_topic.yaml).", False),
    ("Build Image Cpp", "docker.io/library/release-build-cpp:0.1", "files/issue-76/cpp-build/, imported into k3s containerd.", False),
    ("Build Image Maven", "docker.io/library/maven:3.9-eclipse-temurin-21", "Stock arm64 image, pulled by containerd; entrypoint mounted from the maven-build-entrypoint ConfigMap.", False),
    ("Core Maven Args", "-T 1C -DskipTests", "apache/nifi is the heavyweight reactor: parallel build, tests skipped so the run fits the poll window. The entrypoint stamps -DskipTests into the verdict note, so a recommendation always says tests were not run. Clear this to build with tests once the wall time is known to fit.", False),
    ("Core Maven Opts", "-Xmx8g -XX:+UseG1GC", "MAVEN_OPTS for the core leg only; the API/NAR legs build fine on the default heap.", False),
]

flow = {
    "flowEncodingVersion": "1.0", "latest": False,
    "externalControllerServices": {}, "parameterProviders": {},
    "parameterContexts": {PG_NAME: {
        "componentType": "PARAMETER_CONTEXT", "name": PG_NAME,
        "description": "Endpoints and the two credentials the ReleaseVoteWatch PG uses (#76).",
        "inheritedParameterContexts": [],
        "parameters": [{"name": n, "value": v, "description": d, "sensitive": s, "provided": False}
                       for n, v, d, s in params],
    }},
    "flowContents": {
        "identifier": PG_ID, "name": PG_NAME, "componentType": "PROCESS_GROUP", "comments":
            "Release-vote automation (#76): watch dev@nifi.apache.org over IMAP, verify+build+"
            "smoke an RC as a capped k8s Job in release-builds, publish a recommendation. "
            "This flow NEVER casts a vote — the human replies from steven@sceneserver.net.",
        "position": {"x": 0.0, "y": 0.0}, "parameterContextName": PG_NAME,
        "processors": processors, "connections": connections, "controllerServices": controller_services,
        "funnels": [], "inputPorts": [], "outputPorts": [], "labels": [], "processGroups": [],
        "remoteProcessGroups": [], "scheduledState": "ENABLED",
        "defaultFlowFileExpiration": "0 sec", "defaultBackPressureObjectThreshold": 10000,
        "defaultBackPressureDataSizeThreshold": "1 GB", "executionEngine": "INHERITED",
        "flowFileConcurrency": "UNBOUNDED", "flowFileOutboundPolicy": "STREAM_WHEN_AVAILABLE",
        "maxConcurrentTasks": 1, "statelessFlowTimeout": "1 min",
    },
}

if __name__ == "__main__":
    json.dump(flow, open(OUT, "w"), indent=2)
    print(f"wrote {OUT}: {len(processors)} processors, {len(connections)} connections, "
          f"{len(controller_services)} services, {len(params)} parameters")
    ups = [(c["source"]["name"], c["destination"]["name"]) for c in connections
           if c["source"]["id"] != c["destination"]["id"]]
    pos = {p["name"]: p["position"] for p in processors}
    bad = [(s, d) for s, d in ups if pos[d]["y"] < pos[s]["y"]]
    print("connections routing upward (poll loop-back expected):", bad or "none")
