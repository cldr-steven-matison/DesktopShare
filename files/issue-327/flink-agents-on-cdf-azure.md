# Deploying Cloudera Flink Agents Alongside Cloudera DataFlow on Azure (CDP Public Cloud 7.3.2)

This guide stands up **Apache Flink Agents** as Flink jobs on the **Cloudera Streaming Analytics (CSA) Operator**, running in your own AKS cluster next to your CDP Public Cloud environment on Azure, and wires those agents to the NiFi flows you already run in **Cloudera DataFlow (CDF)**. The agents observe your deployed flows and Kafka topics, reason over what they see with a model served by Cloudera AI Inference, and take corrective action behind an explicit approval gate. You leave with a running agents cluster, three working integration paths into CDF, and a set of gated Workflow and ReAct agents.

The design has two kinds of agents. **Workflow agents** are deterministic and rule-based. They watch a flow or a topic and raise a signal. **ReAct agents** reason with an LLM and propose a runbook, but never mutate a live system without a human approving the step first. Both run as ordinary Flink jobs on a session-mode cluster, so you submit and cancel them the same way you would any Flink job.

```
Cloudera DataFlow (CDP Public Cloud, Azure)          Your AKS cluster (same VNet)
┌───────────────────────────────┐                   ┌──────────────────────────────────┐
│  NiFi flow deployments         │  NiFi REST / Knox │  CSA Operator                      │
│  Data Hub Kafka (9093)         │◀─────────────────▶│    └─ flink-agents FlinkDeployment │
│  DataFlow service (control     │  Kafka SASL_SSL   │         Workflow + ReAct agents    │
│  plane API)                    │  Control Plane API│         run here as Flink jobs     │
└───────────────────────────────┘                   │            │                       │
                                                     │            ▼                       │
                                                     │   Cloudera AI Inference (ReAct)    │
                                                     └──────────────────────────────────┘
```

---

## Prerequisites

- A **CDP Public Cloud environment on Azure**, Runtime **7.3.2**, with a **Cloudera DataFlow** service and at least one deployed NiFi flow.
- A **customer-managed AKS cluster** in the same Azure subscription, peered to the VNet your CDP environment runs in, so in-VNet hostnames and the Data Hub brokers are reachable.
- `kubectl` and `helm` (v3) configured against that AKS cluster, and an **Azure Container Registry (ACR)** the cluster can pull from.
- A **Cloudera license file** and credentials for `container.repository.cloudera.com` (the Cloudera image registry).
- A **CDP workload user** and **workload password** from the Management Console, used for both the NiFi REST and Kafka paths.
- For ReAct agents, a **Cloudera AI Inference** endpoint serving a chat model, plus a Knox JWT or Knox API key to call it.

---

## Step 1. Install the CSA Operator into AKS

The CSA Operator ships as an OCI Helm chart. It installs the Flink Kubernetes Operator, which manages the `FlinkDeployment` and `FlinkSessionJob` custom resources, and the SQL Stream Builder services. Create a namespace for it and a pull secret for the Cloudera registry first.

```bash
kubectl create namespace flink-agents

kubectl create secret docker-registry cloudera-creds \
  --namespace flink-agents \
  --docker-server=container.repository.cloudera.com \
  --docker-username='<cloudera-registry-user>' \
  --docker-password='<cloudera-registry-token>'
```

Install the operator, passing your license file inline and the pull secret to each subchart.

```bash
helm install csa-operator \
  oci://container.repository.cloudera.com/cloudera-helm/csa-operator/csa-operator \
  --namespace flink-agents \
  --version 1.5.0-b275 \
  --set 'flink-kubernetes-operator.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.sse.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.sqlRunner.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.mve.image.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.database.imagePullSecrets[0].name=cloudera-creds' \
  --set 'ssb.flink.image.imagePullSecrets[0].name=cloudera-creds' \
  --set-file flink-kubernetes-operator.clouderaLicense.fileContent=./license.txt
```

Confirm the operator is up before going further.

```bash
kubectl get deploy -n flink-agents
kubectl get crd | grep flink.apache.org   # flinkdeployments, flinksessionjobs
```

The operator's admission webhook **requires** `spec.serviceAccount` on every `FlinkDeployment`. Step 3 creates that service account.

> **Durable state.** For anything beyond a demo, back SQL Stream Builder's metadata and the Flink checkpoints with persistent volumes rather than the defaults. Configure the persistence values in a `csa-values.yaml` and pass it with `--values` at install time. On AKS, use a managed-disk `storageClassName`.

---

## Step 2. Build the Flink Agents runtime image

There is no official Flink Agents image, so you build one. It is a multi-stage build. A Maven stage compiles Apache Flink Agents `release-0.3.1` from source (the Java dist jars plus a Python wheel), and a runtime stage layers those onto the official `flink:1.20.5-java17` image with an isolated Python virtualenv. This Flink version sits above the Flink Agents 1.20.3 floor and matches the 1.20 line the CSA Operator runs.

```dockerfile
# ---- Stage 1: build Flink Agents from source ----
FROM maven:3-eclipse-temurin-17 AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
        git python3 python3-venv python3-pip && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 --branch release-0.3.1 https://github.com/apache/flink-agents.git
WORKDIR /src/flink-agents
RUN mvn clean install -DskipTests -B -Dspotless.skip=true
RUN set -eux; \
    LIB=python/flink_agents/lib; rm -rf "$LIB"; mkdir -p "$LIB/common"; \
    cp dist/common/target/flink-agents-dist-common-*.jar "$LIB/common/"; \
    for d in dist/flink-*; do v=$(basename "$d"); mkdir -p "$LIB/$v"; \
        cp "$d"/target/flink-agents-dist-"$v"-*-thin.jar "$LIB/$v/"; done; \
    python3 -m venv /buildvenv && /buildvenv/bin/pip install --no-cache-dir build; \
    cd python && /buildvenv/bin/python -m build --wheel

# ---- Stage 2: runtime image ----
FROM flink:1.20.5-java17
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev build-essential && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/flink-agents/python/dist/*.whl /tmp/wheels/
RUN python3.11 -m venv /opt/flink/agents-venv \
    && /opt/flink/agents-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/flink/agents-venv/bin/pip install --no-cache-dir \
        apache-flink==1.20.5 kafka-python /tmp/wheels/*.whl && rm -rf /tmp/wheels
# Put the dist jars and the flink-python jar on the Flink classpath so PythonDriver runs.
COPY --from=build /src/flink-agents/dist/common/target/flink-agents-dist-common-*.jar /opt/flink/lib/
COPY --from=build /src/flink-agents/dist/flink-1.20/target/flink-agents-dist-flink-1.20-*-thin.jar /opt/flink/lib/
RUN cp /opt/flink/opt/flink-python-*.jar /opt/flink/lib/
# Your agent entry scripts.
RUN mkdir -p /opt/flink/usrlib/agents
COPY agents/ /opt/flink/usrlib/agents/
ENV PYFLINK_CLIENT_EXECUTABLE=/opt/flink/agents-venv/bin/python
ENV PYTHONPATH=/opt/flink/agents-venv/lib/python3.11/site-packages
RUN ln -sf /opt/flink/agents-venv/bin/python /usr/local/bin/python \
    && chown -R flink:flink /opt/flink/agents-venv /opt/flink/usrlib
USER flink
```

Two things this image gets right that are easy to miss. Flink Agents runs the Python agent code through `pemja` in embedded-libpython mode, so the virtualenv's site-packages has to be exposed on `PYTHONPATH`, because pemja does not pick up the venv on its own. And the `flink-python` jar has to be copied into `/opt/flink/lib/` so `PythonDriver` is on the classpath at submit time.

Build it and push it to your ACR.

```bash
az acr build --registry <your-acr> --image cso-flink-agents:0.3.1 .
```

---

## Step 3. Deploy the agents FlinkDeployment and RBAC

The agents run on a **session-mode** cluster, one long-lived Flink cluster that many small agent jobs are submitted to and cancelled from, which matches how agents come and go. First create the service account the admission webhook requires and the role the JobManager needs to manage its TaskManager pods.

```yaml
# rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: flink
  namespace: flink-agents
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: flink
  namespace: flink-agents
rules:
  - apiGroups: [""]
    resources: ["pods", "configmaps", "services", "secrets", "events"]
    verbs: ["create", "get", "list", "watch", "update", "delete", "patch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets"]
    verbs: ["create", "get", "list", "watch", "update", "delete", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: flink
  namespace: flink-agents
subjects:
  - kind: ServiceAccount
    name: flink
    namespace: flink-agents
roleRef:
  kind: Role
  name: flink
  apiGroup: rbac.authorization.k8s.io
```

Then the session cluster itself, pointed at the image in your ACR.

```yaml
# flinkdeployment.yaml
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: flink-agents
  namespace: flink-agents
spec:
  image: <your-acr>.azurecr.io/cso-flink-agents:0.3.1
  imagePullPolicy: IfNotPresent
  flinkVersion: v1_20
  serviceAccount: flink
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "2"
    classloader.parent-first-patterns.additional: pemja
    python.executable: /opt/flink/agents-venv/bin/python
    python.client.executable: /opt/flink/agents-venv/bin/python
  jobManager:
    resource:
      memory: 1536m
      cpu: 1
  taskManager:
    resource:
      memory: 1536m
      cpu: 1
```

The `classloader.parent-first-patterns.additional: pemja` line is not optional. Without it, pemja's embedded libpython loads two copies of its classes and the TaskManager crashes.

```bash
kubectl apply -f rbac.yaml
kubectl apply -f flinkdeployment.yaml
kubectl get flinkdeployment -n flink-agents   # wait for STABLE
```

Smoke-test the cluster by submitting one of the built-in quickstart agents as a Flink job from the JobManager pod and watching it in the Flink UI.

```bash
kubectl exec -it deploy/flink-agents -n flink-agents -- \
  flink run -py /opt/flink/usrlib/agents/<quickstart>.py
```

---

## Step 4. Wire the agents to Cloudera DataFlow

There are three integration surfaces, and most deployments use more than one. Take them in the order below.

### Watch and heal the flow over the NiFi REST API

Agents reach the NiFi flow through its REST API to read processor state, queue depth, and bulletins, and (only after Step 5's approval gate) to change run status. There are two ways in.

- **DataFlow Inbound Connections.** A CDF flow deployment can expose a stable public hostname with TLS/mTLS auto-provisioned. The listen processor uses a `StandardRestrictedSSLContextService` named **exactly** `Inbound SSL Context Service`, which CDF auto-populates at deployment. This is the clean edge path when the agent needs to push data or reach the flow from outside the VNet.
- **NiFi REST through Knox.** For read-only monitoring, authenticate to the flow's NiFi API with your workload user through the environment's Knox gateway and call the read endpoints (processor status, connection queues, bulletin board).

Keep the monitor phase on **read-only** endpoints. When a heal action does write, follow the two rules below without exception.

- **Never GET-then-PUT a NiFi processor that has sensitive properties.** NiFi masks a sensitive value as `********` on read. PUT it back and that literal overwrites the real credential and destroys it. Change run status through the narrow `/processors/{id}/run-status` endpoint, or manage the value in a **Parameter Context**, never a full-entity PUT.
- **Put credentials in a Parameter Context**, not in a processor property and not in the FlinkDeployment YAML.

### The data plane over Data Hub Kafka

When the agents need to consume the events a flow produces (or feed enriched results back), connect directly to the environment's **Data Hub Kafka** on port **9093** with these client settings.

```properties
security.protocol=SASL_SSL
sasl.mechanism=PLAIN
# workload user / workload password via a JAAS config or client-supplied callback
```

Import the environment's FreeIPA certificate into the client truststore with `keytool`, and take the broker hostnames from Cloudera Manager for that cluster. Agents subscribe to the topic the flow writes and publish their enriched output to a topic of your choosing.

### Deployment health from the DataFlow Control Plane API

The flow's own state is not the whole picture; the deployment's health is a separate signal. Query the **CDP DataFlow service API** with a CDP access key to read deployment status and KPIs, and feed that into the agents as a distinct input from the NiFi-flow-level view.

---

## Step 5. Point ReAct agents at Cloudera AI Inference

Flink Agents 0.3.1 does not ship a vendor-specific Cloudera integration, but Cloudera AI Inference exposes an **OpenAI-compatible** endpoint, and the SDK's `OPENAI_COMPLETIONS_CONNECTION` speaks exactly that. So a ReAct agent points at AI Inference with no code fork. You supply the endpoint, a token, and the model name.

The AI Inference endpoint follows the pattern `https://<domain>/namespaces/serving-default/endpoints/<endpoint-name>/v1`. The client `base_url` is that URL with the last two path segments removed. Auth is a bearer token, either a Knox JWT or a Knox API key. The `model` you pass must be the **name assigned in the AI Registry**, not a raw Hugging Face or NGC id.

```python
from flink_agents.api.resource import ResourceDescriptor, ResourceName

ai_inference_connection = ResourceDescriptor(
    clazz=ResourceName.ChatModel.OPENAI_COMPLETIONS_CONNECTION,
    api_base_url="https://<domain>/namespaces/serving-default/endpoints/<endpoint-name>/v1",
    api_key="<knox-jwt-or-api-key>",
)

# On the agent, the setup references the connection by name and names the registry model:
#   ResourceDescriptor(
#       clazz=ResourceName.ChatModel.OPENAI_COMPLETIONS_SETUP,
#       connection="ai_inference",
#       model="<ai-registry-model-name>",
#   )
```

The Knox JWT is short-lived. For an agent job that runs longer than the token's lifetime, use a **Knox API key** rather than a JWT so the job does not lose auth mid-run.

If you would rather run your own model, the same `OPENAI_COMPLETIONS_CONNECTION` works against any OpenAI-compatible endpoint. Point `api_base_url` at it and set `api_key` accordingly.

---

## Heal-phase guardrails

The agents move through three phases, and the gate between them is where policy is enforced in code, not just documented.

- **monitor** is read-only. Agents observe and raise signals, and nothing is changed.
- **safe** covers low-risk, reversible actions, each one approved by a human before it runs.
- **lab** covers broader actions, in a non-production flow only.

Every ReAct runbook is **human-in-the-loop**. The agent proposes the action and a person approves it before any mutation. Fold the NiFi rules from Step 4 into this gate. No GET-then-PUT of sensitive properties, credentials in a Parameter Context, and confirm before you restart or redeploy any live service. An approval you gave for one action does not carry to the next.

---

## Running on a CSA Data Hub instead of your own operator

If you would rather not run the operator yourself, provision a **Streaming Analytics Data Hub** in your CDP environment and use its Flink cluster as the substrate. Build the same agents artifacts and submit the agent jobs to the Data Hub's Flink cluster instead of a FlinkDeployment in your AKS. You trade operator-level control over the image, Flink version, and sizing for a Cloudera-managed cluster. Check the Data Hub's Flink version against the Flink Agents 1.20.3 floor before you commit to this path. The operator route above lets you pin `flink:1.20.5-java17` directly, which is why it is the recommended one.

---

## What NOT to do

- **Don't expose a Kafka broker directly when Inbound Connections will do.** The Inbound Connection gives you a public hostname with auto-provisioned mTLS and no broker exposure. Reach for the direct 9093 path only when a flow is not in the picture.
- **Don't GET-then-PUT a NiFi processor with sensitive properties.** The masked `********` writes back as a literal and destroys the credential. Use `/run-status` or a Parameter Context.
- **Don't hardcode credentials in the FlinkDeployment YAML.** Inject them as environment or secret references, and keep flow credentials in a NiFi Parameter Context.
- **Don't call Cloudera AI Inference "GA."** State it as available, and do not attach a maturity label it does not carry.

---

## References

- [Cloudera DataFlow Inbound Connections](https://docs.cloudera.com/dataflow/cloud/about-inbound-connections.html) · [Configuring inbound connection support](https://docs.cloudera.com/dataflow/cloud/develop-flow-definitions/topics/cdf-configuring-inbound-connection-support.html)
- [Connecting Kafka clients outside the VPC](https://docs.cloudera.com/cdf-datahub/7.3.1/connecting-kafka/topics/kafka-dh-connect-clients-outside-vpc.html)
- [Cloudera AI Inference authentication](https://docs.cloudera.com/machine-learning/cloud/ai-inference/topics/ml-caii-authentication.html) · [Making a call with the OpenAI API](https://docs.cloudera.com/machine-learning/cloud/ai-inference/topics/ml-caii-make-inference-call-model-endpoint-with-openai-api.html)
- [Apache Flink Agents](https://github.com/apache/flink-agents) · [Flink Agents deployment docs (0.3)](https://nightlies.apache.org/flink/flink-agents-docs-release-0.3/docs/operations/deployment/)
- [Official Flink images](https://hub.docker.com/_/flink)
