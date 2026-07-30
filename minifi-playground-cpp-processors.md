# MiNiFi C++ on Kubernetes: The Complete Processor Reference for the Cloudera Stock Image

> **Folded into the guide:** condensed into the Complete Guide to Edge Flow Management → `guide/ch03-cpp-processor-catalog.md` (#31). This doc stays the full catalog with evidence; the chapter is the operational reference.

I was building flows with the [MiNiFi-Kubernetes-Playground](https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground) repo when I hit the `ExecuteScript` wall — the processor simply isn't in the stock Cloudera image. I went looking for a definitive list of what *is* there and found nothing I could trust without cross-checking against a running instance. So I pulled the full catalog myself. This is that reference: what's in the stock image, what the extra-extensions tarball unlocks, what each platform actually ships, and the real gotchas I found while building live flows.

---

## Labels used in this doc

- **[Cloudera stock]** — in `container.repo.cloudera.com/cloudera/apacheminificpp:latest` with no modification. Pull and run.
- **[Cloudera extra-extensions]** — in Cloudera's `extra-extensions-linux.tar.gz` tarball. Not in the stock image; requires the injection recipe in `efm-binaries.md`.
- **[Cloudera MSI + ADDLOCAL=ALL]** — in the Windows MSI when reinstalled with all features. Not enabled by the EFM deployer by default.
- **[Apache source build]** — in the Apache `nifi-minifi-cpp` upstream source but not in any Cloudera-shipped binary. Requires a multi-stage Dockerfile source build at the matching tag.

---

## Cloudera vs Apache: what ships vs what's possible

The stock image is Cloudera-curated, Apache-licensed. The source lives in Apache's `nifi-minifi-cpp` repo. The 74 processors in the catalog below are all Apache upstream processors — Cloudera curates which subset gets compiled and shipped in `apacheminificpp:latest`. Every one of those 74 traces back to the Apache upstream `PROCESSORS.md`. Apache upstream has more; getting them requires a source build or the extra-extensions tarball injection. The full Apache upstream ceiling is at `https://github.com/apache/nifi-minifi-cpp/blob/main/PROCESSORS.md`.

The EFM deployer calls these `agentType=cpp`. The Dockerfile's `MINIFI_HOME` path is `/opt/minifi/nifi-minifi-cpp-1.26.02`. The image tag is `v1.26.02`.

---

## Verified processor catalog — stock `apacheminificpp:latest` [Cloudera stock]

**Version: 1.26.02, Linux x86_64. Extracted from a running instance — not from docs.**

### HTTP and Networking

- **ListenHTTP** — embedded HTTP server; fire-and-forget (caller gets 200, no inline reply). See gotchas.
- **InvokeHTTP** — HTTP client for outbound calls (GET/POST/PUT/etc.). See gotchas.
- **GetTCP** — receive data over a persistent TCP connection
- **ListenTCP** — listen for inbound TCP connections
- **ListenUDP** — listen for inbound UDP datagrams
- **PutTCP** — send data over TCP
- **PutUDP** — send data over UDP

### Kafka

- **ConsumeKafka** — consume from a Kafka topic
- **PublishKafka** — publish to a Kafka topic. See gotchas.

### MQTT

- **ConsumeMQTT** — subscribe to an MQTT topic
- **PublishMQTT** — publish to an MQTT topic

### File and Archive

- **FetchFile** — read a file from the local filesystem
- **GetFile** — list and transfer files from a directory
- **ListFile** — list files in a directory without consuming them
- **PutFile** — write a FlowFile to the local filesystem
- **TailFile** — tail a log file or any growing file
- **CompressContent** — compress or decompress content (gzip, lz4, etc.)
- **FocusArchiveEntry** — focus a single entry inside a .tar or .zip archive
- **ManipulateArchive** — add, remove, or modify archive entries
- **MergeContent** — merge multiple FlowFiles into one (defragment, bin-pack, or concat)
- **SegmentContent** — split content into fixed-size segments
- **SplitContent** — split FlowFile content on a delimiter
- **UnfocusArchiveEntry** — return focus to the outer archive after `FocusArchiveEntry`

### Cloud Storage — AWS

- **DeleteS3Object** — delete an object from S3
- **FetchS3Object** — download an object from S3
- **ListS3** — list objects in an S3 bucket
- **PutKinesisStream** — publish records to AWS Kinesis
- **PutS3Object** — upload an object to S3

### Cloud Storage — Azure

- **DeleteAzureBlobStorage** — delete a blob
- **DeleteAzureDataLakeStorage** — delete a file in ADLS Gen2
- **FetchAzureBlobStorage** — download a blob
- **FetchAzureDataLakeStorage** — download a file from ADLS Gen2
- **ListAzureBlobStorage** — list blobs in a container
- **ListAzureDataLakeStorage** — list files in an ADLS Gen2 path
- **PutAzureBlobStorage** — upload a blob
- **PutAzureDataLakeStorage** — upload a file to ADLS Gen2

### Cloud Storage — Google Cloud

- **DeleteGCSObject** — delete an object from GCS
- **FetchGCSObject** — download an object from GCS
- **ListGCSBucket** — list objects in a GCS bucket
- **PutGCSObject** — upload an object to GCS

### Database and SQL

- **ExecuteSQL** — run a SQL query and emit results as FlowFiles
- **GetCouchbaseKey** — fetch a document from Couchbase by key
- **PutCouchbaseKey** — store a document in Couchbase by key
- **PutSQL** — execute a SQL insert/update/delete
- **QueryDatabaseTable** — incrementally poll a database table for new rows

### Data Transformation and Routing

- **AttributesToJSON** — serialize FlowFile attributes as JSON
- **ConvertRecord** — convert records between formats (requires a Record Reader/Writer controller service)
- **DefragmentText** — reassemble text fragments produced by `SplitText`
- **EvaluateJsonPath** — extract fields from JSON content into FlowFile attributes. See gotchas.
- **ExtractText** — extract content matching a regex into attributes
- **JoltTransformJSON** — apply a JOLT spec transformation to JSON
- **ReplaceText** — replace content or attributes using a regex or literal
- **RouteOnAttribute** — route FlowFiles based on attribute expressions
- **RouteText** — route FlowFiles by matching text content
- **SplitJson** — split a JSON array into individual FlowFiles
- **SplitRecord** — split a record set into individual records
- **SplitText** — split text content by line count or delimiter
- **UpdateAttribute** — add, remove, or modify FlowFile attributes

### Observability and Monitoring

- **CollectKubernetesPodMetrics** — emit pod resource metrics as FlowFiles
- **ConsumeJournald** — read systemd journald log entries as FlowFiles
- **LogAttribute** — log FlowFile attributes to `minifi-app.log`
- **ProcFsMonitor** — emit Linux `/proc` system metrics (CPU, memory, disk) as FlowFiles

### Attributes and Host Metadata

- **AttributeRollingWindow** — maintain a rolling window of attribute values over time
- **AppendHostInfo** — append hostname and IP to FlowFile attributes

### Syslog

- **ListenSyslog** — receive syslog messages (UDP or TCP)

### Observability — Sinks

- **PostElasticsearch** — index documents into Elasticsearch
- **PushGrafanaLokiGrpc** — push log entries to Grafana Loki over gRPC
- **PushGrafanaLokiREST** — push log entries to Grafana Loki over HTTP
- **PutSplunkHTTP** — send events to Splunk HEC
- **QuerySplunkIndexingStatus** — check indexing status for a Splunk HEC submission

### Industrial Protocols

- **FetchModbusTcp** — read registers from a Modbus TCP device

### Utilities

- **GenerateFlowFile** — generate synthetic FlowFiles (load testing, warm-up)
- **HashContent** — compute a hash of FlowFile content and store it as an attribute
- **RetryFlowFile** — route a FlowFile back to a previous step up to N times

**Total: 74 processors.** This is the complete verified set from the stock `apacheminificpp:latest` image (v1.26.02, Linux x86_64), extracted from a running instance — every name is preserved verbatim from that catalog, nothing added, nothing invented.

---

## Processors unlocked by extra-extensions injection [Cloudera extra-extensions]

After injecting `extra-extensions-linux.tar.gz` into the agent's `extensions/` directory (see the recipe in `efm-binaries.md`), the following `.so` files appear and enable additional processors. The extensions listing below is from a running `minifi-agent-k8s` pod verified on 2026-06-09 (timestamps in the `ls -al` output):

| `.so` filename | Enables | Notes |
|---|---|---|
| `libminifi-lua-script-extension.so` | **ExecuteScript** (Lua engine) | Together with `libminifi-script-extension.so`; Lua only |
| `libminifi-python-script-extension.so` + `libminifi-python-lib-loader-extension.so` + `minifi_native.so` | **ExecuteScript** (Python engine) | All three required for Python; also enables `PythonScriptExecutor` class |
| `libminifi-execute-process.so` | **ExecuteProcess** | Shell command execution |
| `libminifi-opc-extensions.so` | **OPC-UA processors** (FetchOPCProcessor, PutOPCProcessor) | OPC-UA client for industrial automation |
| `libminifi-llamacpp.so` | **LlamaCPP inference processor** | On-device LLM inference via llama.cpp |
| `libminifi-script-extension.so` | Script dispatch host | Required for both Lua and Python `ExecuteScript` |

The stock `.so` files already in the image before injection handle Kafka (`libminifi-rdkafka-extensions.so`), AWS (`libminifi-aws.so`), Azure (`libminifi-azure.so`), GCS (`libminifi-gcp.so`), Elasticsearch (`libminifi-elasticsearch.so`), Splunk (`libminifi-splunk.so`), SQL (`libminifi-sql.so`), MQTT (`libminifi-mqtt-extensions.so`), Kubernetes (`libminifi-kubernetes-extensions.so`), Grafana Loki (`libminifi-grafana-loki.so`), Couchbase (`libminifi-couchbase.so`), archive formats (`libminifi-archive-extensions.so`), civet web server (`libminifi-civet-extensions.so`), Prometheus (`libminifi-prometheus.so`), procfs (`libminifi-procfs.so`), systemd (`libminifi-systemd.so`), RocksDB (`libminifi-rocksdb-repos.so`), and the standard processor set (`libminifi-standard-processors.so`).

**The extra-extensions tarball is a separate Cloudera archive, not part of the stock Docker pull.** The injection recipe is in `efm-binaries.md` — unpack the tarball, `find -name "*.so" -exec cp {} extensions/`**, re-tar, and pipe into the EFM pod before the agent deploys.

There is also an ARM64-specific extra-extensions tarball: `nifi-minifi-cpp-1.26.02-b30-extra-extensions-linux-arm64.tar.gz`. The `.so` filenames it contains have not been independently verified to be identical to the x86_64 list above. **[Not yet field-verified: ARM64 extra-extensions `.so` listing vs x86_64 — tracked as #34]**

---

## Platform matrix

| Platform | Agent binary | Stock processor count | Extra-extensions | ExecuteScript | Status |
|---|---|---|---|---|---|
| Linux x86_64 | `binaries/cpp/linux/1.26.02/minifi.tar.gz` | 74 (stock image) | Injection recipe in `efm-binaries.md` | Via extra-extensions or source build | **Confirmed — running instance verified** |
| Linux aarch64 (ARM64) | `binaries/cpp/linuxaarch64/1.26.02/minifi.tar.gz` | 79 (live re-capture, 2026-07-28) | Already staged on `NvidiaNano` (Jetson) | Confirmed present, live-executed | **Field-verified.** Captured live from the `NvidiaNano` agent (class `NvidiaNano`, manifest `dab61017-33fb-44e7-a159-882601f01952`, build `1.26.02`) via `GET /efm/api/agent-manifests/{id}`, committed as `files/efm/NvidiaNano-manifest.json`. 5 more than the stock 74: `ExecuteProcess`, `ExecuteScript`, `FetchOPCProcessor`, `PutOPCProcessor`, `RunLlamaCppInference` — the extra-extensions `.so` files (`execute-process`, `lua`+`python`-script-extension, `opc-extensions`, `llamacpp`) were already staged on this device (installed 2026-06-09), same pattern as Windows' `ADDLOCAL=ALL`. No x86-only processors found missing on aarch64. `ExecuteScript` confirmed running live in Python engine (3 processors in the device's production flow — matrix-screensaver launcher, streamChat launcher, TensorRT inference — all independently confirmed working in this device's own session history) and Kafka confirmed with a genuine end-to-end delivery+consume round trip (10/10 messages, sequential offsets 0-9, topic `minifi-aarch64-test`) — the first fully-closed Kafka loop from a MiNiFi edge agent in this lab. |
| Windows x64 (MSI) | `binaries/cpp/windows/1.26.02/minifi.msi` | 81 (live re-capture, 2026-07-27) | `ADDLOCAL=ALL` enables Python scripting DLL; no Linux `.so` equivalent | `ADDLOCAL=ALL` required, confirmed present | **Field-verified.** Re-captured live from agent `40eb2f92-94c5-4478-beed-7060e41c9d7f` (`WindowsDesktopCpp`, manifest `ad8fb2bf-a4de-49e6-92ec-4d70fcbe5519`, same build revision `0d41a46e` as the earlier 76-processor capture) via `GET /efm/api/agent-manifests/{id}`, committed as `files/efm/WindowsDesktopCpp-manifest.json`. 5 more than the prior committed count: `FetchOPCProcessor`, `PutOPCProcessor`, `GetCouchbaseKey`, `PutCouchbaseKey`, `RunLlamaCppInference` — same binary, so these were extension bundles not enabled/loaded at the time of the June capture rather than a version change. `ExecuteScript`/`ConsumeKafka`/`PublishKafka` all confirmed present. |

The EFM binary path for each is strict: `${agentType}/${osArch}/${agentVersion}/` with exactly one archive file per leaf directory. `osArch` must be `linux`, `linuxaarch64`, or `windows` — hyphens are rejected by the EFM validator.

---

## The `ExecuteScript` story

### Symptom

Every 30 seconds in `minifi-app.log`:

```
Failed to start processor <uuid> (ExecuteScript):
Process Schedule Operation: Could not instantiate: PythonScriptExecutor.
Make sure that the python scripting extension is loaded
```

The processor stays in `SCHEDULED` state, retrying indefinitely. Nothing flows through it.

### Diagnosis

`ExecuteScript` (and `ExecuteProcess`, full Python scripting via `PythonScriptExecutor`) requires build-time flags: `-DENABLE_LUA_SCRIPTING=ON` and/or `-DENABLE_PYTHON_SCRIPTING=ON`. Cloudera ships the production-hardened, minimal-footprint image without those flags. The processor is listed in the Apache upstream `PROCESSORS.md` and in Cloudera's documentation for Linux — but the doc listing is for the class that *can* be built, not for what ships in `apacheminificpp:latest`.

On Linux, the tell is the `extensions/` directory: `libminifi-python-script-extension.so` is absent from the stock image. On Windows, `minifi-python-script-extension.dll` is absent from `extensions\` unless you run the MSI with `ADDLOCAL=ALL`.

### Fix path A — Extra-extensions tarball injection [Cloudera extra-extensions]

Inject the Cloudera extra-extensions tarball into the agent's `extensions/` directory before it deploys. Full recipe in `efm-binaries.md`. This is the no-compile path: you're using Cloudera-built `.so` files, just not the ones in the stock Docker image. Works for Linux x86_64 and (by inference, not yet verified) aarch64.

After injection, `ExecuteScript` is available with both Lua and Python engines. The Python engine requires Python to be present in the environment at the version the `.so` was built against.

### Fix path B — Multi-stage source build [Apache source build]

```dockerfile
FROM ubuntu:24.04 AS builder
RUN apt-get update && apt-get install -y \
    build-essential cmake git python3-dev lua5.3-dev \
    libssl-dev libcurl4-openssl-dev libarchive-dev

RUN git clone --branch v1.26.02 https://github.com/apache/nifi-minifi-cpp.git /src

RUN cmake -S /src -B /build \
    -DENABLE_LUA_SCRIPTING=ON \
    -DENABLE_PYTHON_SCRIPTING=ON \
    -DENABLE_AWS=ON \
    -DENABLE_AZURE=ON \
    -DENABLE_GCP=ON \
    -DENABLE_KAFKA=ON \
    -DCMAKE_BUILD_TYPE=Release

RUN cmake --build /build --parallel $(nproc)

FROM container.repo.cloudera.com/cloudera/apacheminificpp:latest
COPY --from=builder /build/bin/    /opt/minifi/nifi-minifi-cpp-1.26.02/bin/
COPY --from=builder /build/extensions/ /opt/minifi/nifi-minifi-cpp-1.26.02/extensions/
```

Then apply the nuclear rebuild from the playground `readme.md`:

```bash
eval $(minikube docker-env)
docker rmi -f minifi-test:latest || true
docker builder prune -a -f
docker build --no-cache --platform linux/amd64 -t minifi-test:latest .
kubectl apply -f minifi-test.yaml
```

This path builds from Apache source at the matching tag. You control exactly which features are compiled in. Build time on a modern Mac is 20–40 minutes.

### Fix path C — Switch to MiNiFi Java

If you need `ExecuteScript` today without a build step, switch to `container.repo.cloudera.com/cloudera/minifi-java:latest`. Full walkthrough in `minifi-playground-java-processors.md`. Java gives you `ExecuteScript` (Groovy, Jython, JavaScript), `ExecuteProcess`, and 200+ processors — at the cost of a ~300–400 MB image and ~512Mi memory minimum vs C++'s ~15 MB and ~128Mi.

### Fix path D — Windows MSI with ADDLOCAL=ALL [Cloudera MSI + ADDLOCAL=ALL]

On Windows, the Python scripting DLL is bundled in the MSI but installed only when you run with `ADDLOCAL=ALL`. The EFM deployer never passes this flag, so Python scripting is silently absent from a standard EFM-deployed Windows agent.

```powershell
Stop-Service "Apache NiFi MiNiFi"
Start-Process msiexec.exe -ArgumentList `
  "/i `"C:\minifi\minifi.msi`" ADDLOCAL=ALL AUTOSTART=0 INSTALL_ROOT=`"C:\minifi`" INSTALLPYTHONDIR=`"C:\Python314`" /quiet /L*v msi_repair.log" `
  -PassThru -Wait
Start-Service "Apache NiFi MiNiFi"
```

Verify it worked:

```powershell
Test-Path "C:\minifi\nifi-minifi-cpp\extensions\minifi-python-script-extension.dll"  # must be True
Test-Path "C:\minifi\nifi-minifi-cpp\extensions\minifi_native.pyd"                    # must be True
```

Full 9-step recovery plan (including clean-slate uninstall) is in `efm-binaries-windows-python.md`.

---

## `config.yml` processor class name reference

The playground repo uses `config.yml` for standalone agent configuration. EFM-deployed flows use fully-qualified class names (FQCNs). Both formats are valid but not interchangeable between contexts.

### Short class names — standalone `config.yml` format

The playground `config.yml` uses short names. Each processor needs a UUID `id` field. `class` is the bare processor name:

```yaml
Flow Controller:
  name: MiNiFi HTTP to Kafka

Processors:
- name: ListenHTTP
  id: 489c62c4-2d12-11f1-baac-62f0ccd85bcd
  class: ListenHTTP
  Properties:
    Listening Port: 8080

- name: PublishKafka
  id: 489c62c6-2d12-11f1-baac-62f0ccd85bcd
  class: PublishKafka
  Properties:
    Known Brokers: my-cluster-kafka-bootstrap.cld-streaming.svc:9092
    Topic Name: test-minifi
    Client Name: minifi-test-client
    Batch Size: '10'

- name: DebugLog
  id: 489c62c7-2d12-11f1-baac-62f0ccd85bcd
  class: PutFile
  Properties:
    Directory: /tmp/minifi-test-output

Connections:
- name: HttpToKafka
  id: 489c62c8-2d12-11f1-baac-62f0ccd85bcd
  source name: ListenHTTP
  destination name: PublishKafka
  source relationship name: success

- name: HttpToLog
  id: 489c62ca-2d12-11f1-baac-62f0ccd85bcd
  source name: ListenHTTP
  destination name: DebugLog
  source relationship name: success

Remote Processing Groups: []
```

Key requirements called out in the playground readme: explicit UUID `id` fields for all components, correct C++ class names (not Java NiFi names), and mandatory `Client Name` for `PublishKafka`.

The `readinessProbe` path in `minifi-test.yaml` must match the `ListenHTTP` endpoint — `/contentListener` by default:

```yaml
readinessProbe:
  httpGet:
    path: /contentListener
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

### FQCNs — EFM-deployed flow format

When EFM pushes a flow to an agent, it uses FQCNs. The EFM Flow Designer API's `POST .../process-groups/{pgId}/processors` body takes `type` as an FQCN. For the processors you'll actually wire in EFM:

| Processor | FQCN for EFM |
|---|---|
| ListenHTTP | `org.apache.nifi.minifi.processors.ListenHTTP` |
| InvokeHTTP | `org.apache.nifi.minifi.processors.InvokeHTTP` |
| PublishKafka | `org.apache.nifi.minifi.processors.PublishKafka` |
| EvaluateJsonPath | `org.apache.nifi.minifi.processors.EvaluateJsonPath` |
| RouteOnAttribute | `org.apache.nifi.minifi.processors.RouteOnAttribute` |
| PutFile | `org.apache.nifi.minifi.processors.PutFile` |
| ExecuteScript | `org.apache.nifi.minifi.processors.ExecuteScript` |
| UpdateAttribute | `org.apache.nifi.minifi.processors.UpdateAttribute` |
| LogAttribute | `org.apache.nifi.minifi.processors.LogAttribute` |

The bundle info from the EFM API `GET /efm/api/designer/flows/{id}` shows the exact FQCN and bundle version for each processor already in a flow — always read that before constructing a new `POST` for the same agent class. The EFM Designer API has no batch/bulk create endpoint; each processor is one `POST` call and returns a server-assigned `identifier` you then use to wire the next connection.

---

## Flow patterns and per-processor gotchas

These are real bugs found on live instances, not hypotheticals.

### ListenHTTP — Batch Size / Buffer Size (MINFICPP-2243)

**Symptom:** You POST to `ListenHTTP` on port 8080 and the request appears to succeed (HTTP 200), but no FlowFile ever reaches the downstream processor. `minifi-app.log` shows:

```
buffer is NOT full 1/5
```

**Diagnosis:** `ListenHTTP` defaults `Batch Size` and `Buffer Size` to `5`. A single request hits `1/5` — the buffer is never full, so it never flushes.

**Fix:** Set both `Batch Size` and `Buffer Size` to `1` in EFM or in `config.yml`. If you still see `1/1 buffer is NOT full` dropping requests after that, you're hitting MINFICPP-2243, fixed in MiNiFi C++ main in December 2024. Check your agent version.

**Also note:** `ListenHTTP` is fire-and-forget. The caller gets an empty HTTP 200 immediately. There is no `HandleHttpRequest`/`HandleHttpResponse` pair in MiNiFi C++. The reply must exit via Kafka (`PublishKafka`) keyed on a caller-supplied `request_id` attribute. If you need request/reply HTTP in a single connection, use MiNiFi Java — see `minifi-playground-java-processors.md`.

### InvokeHTTP — HTTP Method persistence

**Symptom:** `InvokeHTTP` sends GET requests when you configured POST. Data that should reach the upstream service gets dropped with a 405 Method Not Allowed, or worse, triggers a GET on an endpoint that expects a POST body.

**Diagnosis:** The `HTTP Method` property persists as `GET` when you create the processor in EFM's Flow Designer if you don't explicitly touch that field, even when your intent was clearly POST.

**Fix:** Always explicitly set `HTTP Method` in EFM or in `config.yml`. Don't assume default or prior value.

### PublishKafka — NodePort vs in-cluster

**Symptom:** `PublishKafka` fails with `Connection refused` or `LEADER_NOT_AVAILABLE` when the agent is running outside the Kubernetes cluster (EFM-deployed edge agent, StarlinkAI shape).

**Diagnosis:** The `Known Brokers` property is set to the in-cluster DNS name and port (`my-cluster-kafka-bootstrap.cld-streaming.svc:9092`). That address is only reachable from inside the cluster.

**Fix:** For edge agents outside the cluster, use the external NodePort: `<node-ip>:31623` (or whichever NodePort Strimzi is using). For the in-cluster `KubernetesPod` agent shape, the internal DNS is correct. The playground `config.yml` uses `my-cluster-kafka-bootstrap.cld-streaming.svc:9092` because that flow runs inside minikube.

### EvaluateJsonPath — path syntax

`$.request_id` extracts a top-level field from a JSON object. `$[0]` extracts the first element of a top-level array. These are not interchangeable. When the incoming payload is `{"request_id": "abc123", ...}`, use `$.request_id`. If `EvaluateJsonPath` produces empty attribute values, check the path syntax first.

For multipart request bodies (e.g., audio transcription), `EvaluateJsonPath` cannot extract fields from a multipart payload. Instead: set `ListenHTTP`'s `HTTP Headers to receive as Attributes (Regex)` to match the field name and have the caller send it as an HTTP header.

---

## The Dockerfile and Kubernetes YAML

The playground Dockerfile bakes `config.yml` into the specific versioned path:

```dockerfile
FROM container.repo.cloudera.com/cloudera/apacheminificpp:latest
USER root

# Set home directory verified via agent logs
ENV MINIFI_HOME=/opt/minifi/nifi-minifi-cpp-1.26.02

# Deploy configuration
COPY config.yml ${MINIFI_HOME}/conf/config.yml

# Create local sink directory for PutFile
RUN mkdir -p /tmp/minifi-test-output && chmod 777 /tmp/minifi-test-output

EXPOSE 8080

CMD ["/opt/minifi/nifi-minifi-cpp-1.26.02/bin/minifi.sh", "run"]
```

`MINIFI_HOME` is `/opt/minifi/nifi-minifi-cpp-1.26.02` — that path is verified from running instance logs. If you deploy a different version, change both the path and the `CMD`.

The nuclear rebuild script from the playground `readme.md`:

```bash
eval $(minikube docker-env)
kubectl delete deployment minifi-test --force --grace-period=0
kubectl delete service minifi-test-service --ignore-not-found
docker rmi -f minifi-test:latest || true
docker builder prune -a -f
docker login container.repo.cloudera.com
docker build --no-cache --platform linux/amd64 -t minifi-test:latest .
kubectl apply -f minifi-test.yaml
kubectl get pods -w
```

The `eval $(minikube docker-env)` is the critical step — it points your terminal's Docker client to the engine inside Minikube. Without it, `docker build` builds on your host and `kubectl apply` never sees the image.

---

## When to use C++

The stock image is ~15 MB. No JVM startup. Memory request of ~128Mi works. It deploys as a Kubernetes sidecar in seconds. It handles Kafka, S3, Azure, GCS, HTTP ingestion, SQL, MQTT, Modbus, and Kubernetes metrics out of the box without any scripting capability at all.

Use C++ when you need a lightweight agent that moves data — ingestion, routing, protocol bridging, cloud sync — and your logic lives in the flow topology, not in a script. Use it for production edge/K8s sidecars where image size and startup time matter.

When you need `ExecuteScript` or complex transformation logic that can't be expressed in the available processors, the choices are: extra-extensions injection (still C++, no recompile, adds scripting), source build (full control, 30+ min build), or switch to Java (no build, full scripting, larger footprint).

---

## What NOT to do

- **Do not assume `ExecuteScript` is in the stock image.** It isn't. The Cloudera docs list it for Linux because it can be built — not because it ships in `apacheminificpp:latest`. The tell is the missing `libminifi-python-script-extension.so` in `extensions/`.

- **Do not copy Linux `.so` files from the extra-extensions tarball onto a Windows agent.** The Windows agent uses `.dll` files compiled with MSVC. Linux `.so` files are ELF binaries — they will not load on Windows regardless of filename. The MSI `ADDLOCAL=ALL` path is the correct Windows mechanism.

- **Do not use Java NiFi FQCN class names in `config.yml`.** `org.apache.nifi.processors.standard.ListenHTTP` is the Java class name. The C++ agent uses short names like `ListenHTTP` in standalone `config.yml`. Wrong class names produce silent no-ops or a processor that fails to instantiate.

- **Do not run the EFM Windows deployer from `C:\WINDOWS\system32`.** The deployer installs to `$PWD`. Running from system32 lands the entire install tree in a system directory, creates permission issues on upgrade, and makes cleanup painful. `cd C:\minifi` first.

- **Do not skip `ADDLOCAL=ALL` on Windows and then wonder why Python doesn't work.** The EFM-generated deployer command never includes `ADDLOCAL=ALL`. The symptom is `Could not instantiate: PythonScriptExecutor` repeating every 30 seconds. The `msiexec /i ... ADDLOCAL=ALL` repair pass is mandatory.

- **The `linuxaarch64` processor manifest does not match the Linux x86_64 list — field-verified 2026-07-28.** Live-captured from the Jetson `NvidiaNano` agent: 79 processors vs. the stock 74, 5 extra (`ExecuteProcess`, `ExecuteScript`, `FetchOPCProcessor`, `PutOPCProcessor`, `RunLlamaCppInference`) because extra-extensions were already staged on that device. No x86-only processors were missing on aarch64. See the platform matrix above and `files/efm/NvidiaNano-manifest.json`.

- **Do not confuse `ExecuteScript` (C++ post-extra-extensions) with Python custom processors in Java NiFi 2.x.** They have different execution models, different Python environments, and different hot-reload behavior. C++'s `ExecuteScript` re-reads its script file from disk on every trigger with no restart needed. Java NiFi Python custom processors require a version bump + processor switch to register a new bundle version in a running instance.
