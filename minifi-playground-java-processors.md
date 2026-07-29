# MiNiFi Java on Kubernetes: Running the Full Processor Catalog in the Same Playground

If MiNiFi C++ doesn't have the processor you need today, MiNiFi Java does. I run both in the same Minikube playground using the same Strimzi Kafka cluster and the same EFM server. The swap is a Dockerfile change, a memory bump in the K8s YAML, and a different `agentType` in the EFM deployer curl. This doc covers exactly that: what Java gives you that C++ doesn't, the footprint you're trading for it, and how to get a Java agent running through EFM.

For the C++ stock image processor catalog and per-processor gotchas, see `minifi-playground-cpp-processors.md`.

---

## Labels used in this doc

- **[Cloudera stock]** — in `container.repo.cloudera.com/cloudera/minifi-java:latest` with no modification. Pull and run.
- **[Apache source build]** — in the Apache `nifi-minifi-cpp` or `nifi` upstream source but not in any Cloudera-shipped binary.

---

## Cloudera vs Apache: Java edition

`container.repo.cloudera.com/cloudera/minifi-java:latest` is Cloudera's build of Apache NiFi MiNiFi Java. The version staged in EFM is `2.24.08.0-19`. The EFM binary path is `binaries/java/linux/2.24.08.0-19/minifi.tar.gz`.

The processor set is a **subset** of the Apache NiFi 2.x catalog shipped as CEM agent NARs. Field-verified 2026-07-25 from a live `minifi-java` agent manifest (`2.24.08.0-19` on WindowsDesktop): **114 processors**, **45 controller services**. Full list: `files/efm/java-minifi-2.24.08.0-19-processors.txt`. Stock-tarball absences: `ExecuteScript`, `PublishKafka` / `ConsumeKafka`. The older "200+" language and "ExecuteScript out of the box" claims do **not** match this binary — use the live manifest, not marketing comparison tables. Full session write-up: `efm-windows-java-minifi.md`. **Update 2026-07-27: both absences are now closed via a NAR drop-in, field-verified on `KubernetesPodJava` (122 processors, ExecuteScript/PublishKafka/ConsumeKafka all working) — see `efm-binaries.md` → *Kafka + scripting NARs on the CEM Java agent — SOLVED*.**

The `agentType` in the EFM deployer is `java`. The `osArch` is `linux` or `windows` (same tarball — Java is platform-agnostic). As of 2026-07-25 both `java/linux` and `java/windows` are staged in EFM on WindowsDesktop; no `linuxaarch64` Java binary yet.

---

## What Java gives you that C++ doesn't

| Capability | MiNiFi C++ (`apacheminificpp:latest`) | MiNiFi Java (`minifi-java:latest`) |
|---|---|---|
| **ExecuteScript** | Not in stock image; requires extra-extensions or source build | Missing from the stock `2.24.08.0-19` tarball, but **NAR drop-in fix field-verified 2026-07-27** — Groovy execution confirmed working. See `efm-binaries.md` |
| **ExecuteProcess** | Not in stock image; only via extra-extensions | **[Cloudera stock]** — shell command execution |
| **HandleHttpRequest / HandleHttpResponse** | Not available at all — no pair exists in C++ | **[Cloudera stock]** — request-reply HTTP (Jetty-backed); both share an `HttpContextMap` controller service |
| **PublishKafka / ConsumeKafka** | Present (C++ extensions) | Missing from the stock `2.24.08.0-19` tarball, but **NAR drop-in fix field-verified 2026-07-27** — real transactional Kafka producer confirmed connecting. See `efm-binaries.md` |
| **Record Reader/Writer framework** | `ConvertRecord` and `SplitRecord` are present but require controller services | **[Cloudera stock]** — RecordReader/RecordWriter controller services present |
| **Scripting flexibility** | Limited without extra-extensions | Shell via `ExecuteProcess` / `ExecuteStreamCommand` only in this binary |
| **Total processors** | 74 (stock), more via extra-extensions | **114** (field-verified from live agent manifest 2026-07-25) |
| **Image size** | ~15 MB | ~300–400 MB |
| **Memory minimum** | ~128Mi | ~512Mi |
| **JVM startup** | None | ~30–60s cold start in the playground |
| **Kubernetes sidecar use** | Production-ready | Not recommended — footprint too large |

The C++ vs Java comparison table lives here (Java doc). The C++ doc only links to it.

---

## Footprint comparison

These are real numbers from the playground, not marketing estimates.

**C++ (`apacheminificpp:latest`):**
- Image: ~15 MB compressed pull
- Memory request: `128Mi` works; agents run stable at that allocation
- Startup: near-instant — the agent is ready before Kubernetes' `initialDelaySeconds: 5` readiness probe fires
- Pod spec default: no JVM, no warm-up

**Java (`minifi-java:latest`):**
- Image: ~300–400 MB compressed pull
- Memory request: `512Mi` minimum; 1Gi is safer for flows with `ExecuteScript` or Record processing
- Startup: ~30–60 seconds for the JVM + agent bootstrap before it can receive a flow from EFM
- The readiness probe path and initial delay need to match the Java agent's startup time (see Dockerfile section below)

The tradeoff is real. C++ for production edge/K8s sidecars. Java for dev/test, complex flows that need scripting, or flows that require the full NiFi processor catalog.

---

## EFM deployer setup for Java

The deployer curl is the same shape as C++, with `agentType=java`, `agentVersion=2.24.08.0-19`, and `osArch=linux`:

```bash
curl -L \
 -d agentClass=test \
 -d agentIdentifier=e9faec53-6301-4ba1-a9e9-2403674ccdb2 \
 -d agentType=java \
 -d agentVersion=2.24.08.0-19 \
 -d autoConfigureSecurity=false \
 -d baseUrl=http%3A%2F%2F127.0.0.1%3A46663%2Fefm%2Fapi \
 -d hbPeriod=5000 \
 -d osArch=linux \
 -d serviceName=minifi \
 -d serviceUser=minifi \
 -d trustSelfSignedCertificates=false \
 http://127.0.0.1:46663/efm/api/agent-deployer/script | bash -
```

Replace `agentClass=test` with your actual agent class name. Replace `agentIdentifier` with a fresh UUID for each new agent (`uuidgen` on Linux/macOS). The `baseUrl` is the EFM API endpoint reachable from the machine running the deployer — adjust for your port-forward or `minikube service` tunnel address.

The EFM binary tree for Java must have the archive at exactly this path before the deployer runs:

```
/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/java/linux/2.24.08.0-19/minifi.tar.gz
```

To verify it's staged:

```bash
EFM_POD=$(kubectl get pod -n cld-streaming -l app=efm -o jsonpath='{.items[0].metadata.name}')
kubectl exec -i $EFM_POD -n cld-streaming -- find /opt/efm/efm-2.3.1.0-2/agent-deployer/ -type f | grep java
```

Expected output: `/opt/efm/efm-2.3.1.0-2/agent-deployer/binaries/java/linux/2.24.08.0-19/minifi.tar.gz`

Staging recipe from source: in `efm-binaries.md`, the local file is `minifi-2.24.08.0-19-bin.tar.gz`, copied to `staging/binaries/java/linux/2.24.08.0-19/minifi.tar.gz`, then tar-piped into the EFM pod.

---

## Dockerfile.java and minifi-java-test.yaml

### Dockerfile.java

```dockerfile
FROM container.repo.cloudera.com/cloudera/minifi-java:latest
USER root

# Java MiNiFi config path — [Not yet field-verified: exact MINIFI_HOME path for minifi-java:latest]
# C++ uses /opt/minifi/nifi-minifi-cpp-1.26.02; Java path may differ — verify with:
# docker run --rm container.repo.cloudera.com/cloudera/minifi-java:latest find /opt -name "config.yml" 2>/dev/null
ENV MINIFI_HOME=/opt/minifi/minifi-2.24.08.0-19

COPY config.yml ${MINIFI_HOME}/conf/config.yml

EXPOSE 8080

CMD ["${MINIFI_HOME}/bin/minifi.sh", "run"]
```

**[Not yet field-verified: the `MINIFI_HOME` path for `minifi-java:latest`. The C++ image uses `/opt/minifi/nifi-minifi-cpp-1.26.02`; the Java image likely uses a different directory name reflecting the Java version string `2.24.08.0-19`. Run the `find` command above against the image to confirm before building.]**

### minifi-java-test.yaml

The memory and probe changes from the C++ YAML:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: minifi-java-test-service
spec:
  type: NodePort
  selector:
    app: minifi-java-test
  ports:
    - protocol: TCP
      port: 8080
      targetPort: 8080
      nodePort: 30081        # use a different NodePort than C++ (30080)
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minifi-java-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minifi-java-test
  template:
    metadata:
      labels:
        app: minifi-java-test
    spec:
      containers:
      - name: minifi-java
        image: minifi-java-test:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
        resources:
          requests:
            memory: "512Mi"     # C++ runs on 128Mi; Java needs 512Mi minimum
            cpu: "250m"
          limits:
            memory: "1Gi"
        readinessProbe:
          httpGet:
            path: /contentListener
            port: 8080
          initialDelaySeconds: 60   # Java JVM + agent bootstrap takes 30-60s; C++ uses 5s
          periodSeconds: 10
          failureThreshold: 6
```

Key differences from the C++ `minifi-test.yaml`:
- `resources.requests.memory: 512Mi` (was unset or 128Mi for C++)
- `readinessProbe.initialDelaySeconds: 60` (was 5 for C++) — the JVM needs time
- `nodePort: 30081` to avoid conflict with the C++ deployment on 30080
- No `serviceAccountName: minifi-controller` needed unless the flow uses `CollectKubernetesPodMetrics`

---

## Controller services

This is the biggest structural difference between Java and C++ flows in EFM.

**C++** inlines connection properties directly on the processor. A `PublishKafka` in C++ takes `Known Brokers`, `Topic Name`, and `Client Name` as flat properties. No controller service required.

**Java** uses NiFi's controller service architecture. A `PublishKafka` in Java MiNiFi requires a **`Kafka3ConnectionService`** (`org.apache.nifi.kafka.service.Kafka3ConnectionService`, from `nifi-kafka-3-service-nar` — field-verified 2026-07-27, wired via the processor's "Kafka Connection Service" property) controller service. Same pattern for SSL contexts, Record Readers, and Record Writers.

Examples:

**Kafka SSL in C++** — flat properties on `PublishKafka`:
```
Known Brokers: my-cluster-kafka-bootstrap.cld-streaming.svc:9093
Security Protocol: ssl
SSL Certificate Authority: /etc/ssl/certs/ca.crt
```

**Kafka SSL in Java MiNiFi via EFM** — requires a `StandardSSLContextService` controller service:

1. In EFM Flow Designer, add a controller service to the flow: type `org.apache.nifi.ssl.StandardSSLContextService`
2. Configure the service with your truststore/keystore paths
3. On the `PublishKafka` processor, set `SSL Context Service` to reference the controller service by its ID

**Record Reader/Writer in C++**: `ConvertRecord` and `SplitRecord` exist in the C++ stock image, but controller service wiring for them (JsonTreeReader, JsonRecordSetWriter, etc.) works the same way as Java — you define the controller service in EFM and reference it from the processor.

**Kafka controller service wiring is now field-verified (2026-07-27)** — see above and `efm-binaries.md`. SSL/Record Reader/Writer controller service FQCNs and wiring are still **not yet field-verified** for MiNiFi Java `2.24.08.0-19`; the above for those describes the general NiFi 2.x pattern, not a confirmed one. Verify against a running EFM flow before building a production dependency on those specific controller service types.

---

## Flow patterns

> **Scope caveat — these patterns need the scripting + Kafka NARs, which are NOT in the stock EFM-staged CEM `2.24.08.0-19` tarball.** That CEM binary is field-verified (2026-07-25) to lack `ExecuteScript` and `PublishKafka`/`ConsumeKafka` out of the box. **Update 2026-07-27: the NAR drop-in is now solved and field-verified** — see `efm-binaries.md` → *Kafka + scripting NARs on the CEM Java agent — SOLVED* for the exact build-from-source recipe (3 NARs, ~3 min build, no restart needed to autoload). Any pattern below using `ExecuteScript`/`PublishKafka`/`ConsumeKafka` needs either that drop-in applied to the agent, or full NiFi / the Docker `minifi-java:latest` image (unverified — may differ) as an alternative.

### ListenHTTP → PublishKafka + ExecuteScript (Java)

The canonical kitchen-sink flow, on a Java build that includes the scripting + Kafka NARs (see the caveat above):

```
ListenHTTP (port 8080) → ExecuteScript (transform/filter logic) → PublishKafka
```

`ExecuteScript` with `Script Engine: Groovy` and a Groovy script body works once the scripting NAR is present — either via full NiFi, or the drop-in fix (`efm-binaries.md`), field-verified 2026-07-27. Only Groovy and Clojure engines are bundled in the built `nifi-scripting-nar`, no Jython. This is the "kitchen sink" flow that requires either extra-extensions or a source build in C++ — see `minifi-playground-cpp-processors.md`.

### HandleHttpRequest → logic → HandleHttpResponse (Java only)

This pattern does not exist in MiNiFi C++. Use it in Java when you need the caller to receive the actual response body from the flow, not just a 200 ack:

```
HandleHttpRequest → [your processing logic] → HandleHttpResponse
```

Both processors must share the same `StandardHttpContextMap` controller service. The `HandleHttpRequest` processor starts an embedded Jetty server on your configured port. The caller blocks until `HandleHttpResponse` sends the reply. This is the only way to do synchronous request/reply HTTP in MiNiFi. C++ has `ListenHTTP` which acks immediately and requires a separate Kafka response path.

### `ConsumeKafka` → `ExecuteScript` → `PublishKafka`

Standard transform pipeline in Java:

```
ConsumeKafka (input topic) → ExecuteScript (Groovy transform) → PublishKafka (output topic)
```

This is a practical alternative to building a custom Python processor in full NiFi when the transform logic is contained and doesn't need to be versioned independently.

---

## When to use Java

Use Java when:

- You need `ExecuteScript` and your Java build includes the scripting NAR. Full NiFi does; the stock EFM-staged CEM `2.24.08.0-19` doesn't but the drop-in fix now covers it (`efm-binaries.md`). Groovy and Clojure are the engines actually bundled in the built NAR — no Jython/Python, unlike the C++ side.
- You need `HandleHttpRequest`/`HandleHttpResponse` for synchronous HTTP request/reply. C++ can't do this at all.
- You're building complex transform flows that need the Record framework (`ConvertRecord`, `SplitRecord`, `QueryRecord`) with custom reader/writer controller services.
- You're developing and testing flow logic before committing to a C++ deployment — Java gives you the full toolkit while you figure out what you actually need.

Don't use Java for:
- Production Kubernetes sidecar patterns where image size and startup time matter — 300–400 MB and a 60-second JVM cold start disqualify it.
- Edge agents on constrained hardware (Jetson Nano, Raspberry Pi variants) — 512Mi+ memory minimum is too high for most embedded targets.

---

## What NOT to do

- **Do not deploy Java MiNiFi as a production Kubernetes sidecar.** A ~400 MB image that takes 60 seconds to start is not a sidecar. Use C++ for that. Java is for dev/test and flows where scripting flexibility matters more than footprint.

- **Do not mix C++ short class names in a Java EFM flow.** Java MiNiFi flows in EFM use FQCNs like `org.apache.nifi.processors.standard.GenerateFlowFile` (standard processors) — note `PublishKafka`/`ConsumeKafka` specifically are `org.apache.nifi.kafka.processors.*`, not under `.standard.` (field-verified 2026-07-27). Typing a bare class name may result in a no-op or a processor that fails to instantiate. Read the bundle info from `GET /efm/api/designer/flows/{id}` to see the exact FQCN format the agent class expects.

- **Do not assume the Java agent binary path in EFM matches the C++ path.** C++ is `binaries/cpp/linux/1.26.02/minifi.tar.gz`. Java is `binaries/java/linux/2.24.08.0-19/minifi.tar.gz`. Different `agentType`, different version string, different path. The EFM deployer resolves the binary from the `agentType` + `osArch` + `agentVersion` coordinates in the curl — send the wrong combination and the deployer returns a 404 or downloads the wrong binary.

- **Do not skip the `initialDelaySeconds` bump in the readiness probe.** The C++ probe fires at 5 seconds and the pod is up. The Java JVM + MiNiFi bootstrap takes 30–60 seconds. A 5-second initial delay will fail the probe, mark the pod NotReady, and Kubernetes will restart it in a loop before the agent has had a chance to connect to EFM.

- **Do not assume no `agentClass` flow is needed in EFM before running the Java deployer.** EFM must have an agent class defined and a flow published for the agent class before the deployer runs — otherwise the agent heartbeats with no flow to apply and nothing happens. Create the class and publish a minimal flow in EFM first.

- **Do not treat the "200+ processors" count as exact.** The earlier C++-vs-Java comparison work and Cloudera's own comparison tables both say "200+" without a specific number from a running Java MiNiFi 2.24.08.0-19 instance manifest. The actual count has not been extracted from a running instance in this lab. [Not yet field-verified.]
