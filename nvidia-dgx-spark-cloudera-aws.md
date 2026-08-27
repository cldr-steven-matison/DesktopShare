# The DGX Spark and Cloudera on AWS

> **Status (2026-08-26):** work-stream **I** of the DGX Spark readiness EPIC — [#226](https://github.com/cldr-steven-matison/DesktopShare/issues/226), issue [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241). The box landed 2026-08-26 as `spark-dd06` at `192.168.1.203` and runs its own session; on-box bring-up ([#235](https://github.com/cldr-steven-matison/DesktopShare/issues/235)) is the next execution step, and nothing in this doc has been run yet. **Decided:** both AWS shapes stay in scope, the DGX Spark is a *client* of them and never a cluster node, and the parity payload is the OpenAI-compatible API on both sides. **Expected, not decided:** which of the two live AWS footprints hosts the first integration, whether a GPU node group gets added to a Base cluster at all, and the Phase-0 model lock — every model named below is a lead-model *candidate* with its citation, not a lock. Feeds `files/nvidia-spark-guide/` chapters ch05, ch18, ch19 and ch20.

## 1. The two shapes, side by side

Cloudera on AWS is two different products that share a name and almost nothing else. Getting the DGX Spark into the story means knowing which one is on the other end of the wire, because the inbound path, the auth, the cost and the teardown all change.

**CDP Base / Community Edition on EC2** is the on-prem distribution running on cloud instances — Cloudera Manager, parcels, Kerberos, Auto-TLS, a fixed node topology. It is what a customer's data centre looks like, hosted where I can afford to leave it running for an afternoon. We run it: [`cloudera-labs/cloudera-ce-aws`](https://cloudera-labs.github.io/cloudera-ce-aws/) v1.0.0, deploying Cloudera Manager 7.13.2 / Runtime 7.3.2, field-run and written up in `blog/cloudera-ce-cm-evaluation.md`, with the repo cloned on this box at `/home/tunas/cloudera-ce-aws`.

**CDP Public Cloud on AWS** is the SaaS control plane: an environment, a Data Lake, Data Hubs and Data Services provisioned into my own VPC and driven from Cloudera's control plane. We run that too — the `srm-iceberg` environment behind `cloudera-iceberg-rest-catalog-aws-plan.md`, currently `deployment_template = "semi-private"`, `LIGHT_DUTY` Data Lake, Runtime 7.3.2, with an Iceberg REST Catalog live and a weekly reaper.

| | CDP Base / CE on EC2 | CDP Public Cloud on AWS |
|---|---|---|
| What it is | Cloudera Manager + parcels on ~11 EC2 nodes, self-contained DNS/Kerberos/PostgreSQL/Auto-TLS | Control-plane-managed environment, Data Lake, Data Hubs, Data Services in my VPC |
| What we already run | `cloudera-ce-aws` v1.0.0, CM 7.13.2 / Runtime 7.3.2 (`blog/cloudera-ce-cm-evaluation.md`) | `srm-iceberg`, Runtime 7.3.2, Iceberg REST Catalog + Impala/Trino/Hive VWs (`cloudera-iceberg-rest-catalog-aws-plan.md`) |
| Time to stand up | ~40–50 min per the project docs ([cloudera-ce-aws](https://cloudera-labs.github.io/cloudera-ce-aws/)); **~2.5 h measured** on our own run under an emulated amd64 EE (`blog/cloudera-ce-cm-evaluation.md`) | up to **60 min** for the base environment, **~20 min** to tear down ([cdp-tf-quickstarts](https://raw.githubusercontent.com/cloudera-labs/cdp-tf-quickstarts/main/README.md)); our full redeploy.sh restore is ~1 h 40 m (`cloudera-iceberg-rest-catalog-aws-plan.md`) |
| Inbound from outside | **None built in.** Ring-fenced behind SSH + reverse HTTPS proxies ([cloudera-ce-aws](https://cloudera-labs.github.io/cloudera-ce-aws/)) — a tunnel or a jump host, or nothing | DataFlow **Inbound Connections** (stable public hostname, auto mTLS) ([inbound connections](https://docs.cloudera.com/dataflow/cloud/about-inbound-connections.html)); or Data Hub Kafka direct on **9093** ([outside-VPC clients](https://docs.cloudera.com/cdf-datahub/7.3.1/connecting-kafka/topics/kafka-dh-connect-clients-outside-vpc.html)) |
| The AI story | Nothing GPU in the shipped topology — instance types are `t3a`/`r5a` (`blog/cloudera-ce-cm-evaluation.md`) | Cloudera AI: Workbench → AI Registry → AI Inference on GPU node groups ([CAII sizing](https://docs.cloudera.com/machine-learning/cloud/setup-cloudera-ai-inference/topics/ml-caii-caii-configuration-sizing.html)) |
| What the DGX Spark is to it | An **external inference and edge node** reached through a tunnel; the CE cluster is the data platform | An **external client** of DataFlow / Kafka / Iceberg, and the *local* half of the same-code-two-backends demo against AI Inference |
| Cost control | pause.yml / resume.yml / infrastructure-teardown.yml, ~$2/hr ~$45/day (`blog/cloudera-ce-cm-evaluation.md`) | Weekly reaper + redeploy.sh; the 60-day Cloudera on Cloud trial is the entry ([cdp-tf-quickstarts](https://raw.githubusercontent.com/cloudera-labs/cdp-tf-quickstarts/main/README.md)) |

The thing both columns have in common: **the DGX Spark never joins either cluster.** It is a 20-core aarch64 box with one GPU and 121 GB usable of unified memory (`CLAUDE-CHECKIN.md`), sitting on a home LAN with no public IP. It is a peer of WindowsDesktop, not of an EC2 fleet. Every integration below is edge-to-platform, and the local half of each one is built by the two sibling work-streams: the on-box cluster in `nvidia-dgx-spark-k3s-cso.md` and the agent class in `nvidia-dgx-spark-efm-agent.md`.

## 2. CDP Base / Community Edition on AWS

### 2.1 The deploy path

Everything is baked into an Ansible execution-environment image, so the local machine needs a clone, a venv, `ansible-core` + `ansible-navigator`, a container runtime, AWS SSO and a Cloudera license text file ([cloudera-ce-aws getting started](https://cloudera-labs.github.io/cloudera-ce-aws/getting-started/index.html)). The one command that does everything, from our own run:

```bash
# as-built (blog/cloudera-ce-cm-evaluation.md) — v1.0.0, CM 7.13.2 / Runtime 7.3.2
ansible-navigator run playbooks/infrastructure.yml playbooks/services.yml \
  playbooks/cms.yml playbooks/ozone-cluster.yml -e @config.yml -m stdout
```

Four playbooks, four stages: Terraform provisions VPC + security groups + 11 EC2 nodes, Ansible configures FreeIPA/PostgreSQL/Caddy TLS, Cloudera Manager installs and licenses, then CM builds the cluster. Only the gateway node gets a public IP; everything else is private and reached through the Caddy reverse proxy on a `nip.io` hostname. The topology is selectable — Ozone, Kafka, Flink, NiFi, CSA or ECS ([cloudera-ce-aws](https://cloudera-labs.github.io/cloudera-ce-aws/)) — and **the NiFi and Kafka topologies are the ones this work-stream cares about.**

### 2.2 The amd64 fact, and why it does not matter

CE on AWS is x86_64 top to bottom. Two independent confirmations, and neither is a doc-site statement — this closes the architecture question `nvidia-dgx-spark-research.md` §8 leaves open:

1. The published execution-environment image tag is `ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0-amd64`; `:latest` does not exist, and on Apple Silicon the EE runs emulated with `--platform=linux/amd64` (`blog/cloudera-ce-cm-evaluation.md`).
2. The Terraform AMI filter in the clone at `/home/tunas/cloudera-ce-aws` pins `architecture = ["x86_64"]` (`tf_cluster_aws/hosts_common.tf`, read 2026-08-26 on `spark-dd06`) — the EC2 nodes themselves are x86_64 by construction, not by accident.

That is a real constraint and it costs us nothing, because **Base was never going to run *on* the DGX Spark.** The EE is an orchestration controller that drives Terraform and SSHes to nodes; it does no local compute, so even running it emulated here is a non-issue. The demo statement is: *Base runs on AWS at customer shape; the DGX Spark feeds it and serves inference to it.* Anything that promises "CDP Base on the desk" is a promise we cannot keep, and ch18 has to say so in its first paragraph.

> The corollary for this box specifically: the EE image has no `arm64` tag published, so driving a CE deploy *from* `spark-dd06` means the same emulation the Mac used. Untested here. If it stalls, drive CE from WindowsDesktop and keep `spark-dd06` on the data side.

### 2.3 Inbound paths for a Spark-hosted NiFi

CE has **no Inbound Connections equivalent**. The cluster is sealed behind SSH and reverse HTTPS proxies, so an external NiFi cannot simply POST at it. Three honest options, in order of preference:

| Path | Mechanism | Cost |
|---|---|---|
| **Reverse SSH tunnel from the box** | `ssh -R` from `spark-dd06` to the CE gateway publishes the Spark-hosted endpoint *inside* the cluster's network | No SG change, no public exposure; dies with the SSH session |
| **Gateway SG rule + Kafka external listener** | Open the broker port on the gateway SG to my public IP `/32`, produce straight in | Needs a Kafka topology, an SG edit, and my egress IP is not static |
| **Bastion + SOCKS proxy** | The pattern already proven on Public Cloud (`cloudera-iceberg-rest-catalog-aws-plan.md`, [#190](https://github.com/cldr-steven-matison/DesktopShare/issues/190)) | Browser/manual access, not a data path |

The reverse tunnel is the one to build first, because it inverts the direction that actually blocks us — the home LAN has no inbound path, so the connection must originate here:

```bash
# expected — verify on the box
# From spark-dd06: publish the local OpenAI-compatible endpoint on the CE gateway node.
ssh -N -R 8000:127.0.0.1:8000 -i ~/.ssh/ce-aws.pem ec2-user@cm.<gateway-public-ip>.nip.io
# On the gateway, NiFi and Apache Spark jobs then reach it at
#   http://127.0.0.1:8000/v1/chat/completions
# For other cluster nodes to reach it, sshd needs GatewayPorts clientspecified and the
# forward bound to the node's private IP instead of loopback — confirm before promising it.
```

Site-to-Site NiFi→NiFi is the *right* shape once the tunnel exists, and it is a package deal: `userCertAuth` set at CR creation, one CA signing every cert, identity mapped by SAN not DN, peers declared as `User` CRs and never hand-POSTed policies — all of it in `skills/nifi-and-ai/references/site-to-site.md` and proven on our own cluster in `files/cso-prod-1/VALIDATION.md`. On CE the CA is Cloudera Manager's Auto-TLS rather than cert-manager, so the trust join is the unknown leg, not the flow.

### 2.4 RAPIDS for Apache Spark on Base GPU nodes

This is the one place where "Apache Spark" and "DGX Spark" sit in the same paragraph, so the naming rule earns its keep. RAPIDS Accelerator for Apache Spark gives GPU acceleration for SQL/DataFrame work with no code changes ([NVIDIA, April 12 2021](https://developer.nvidia.com/blog/cloudera-and-nvidia-collaborate-to-accelerate-data-analytics-and-ai-at-scale), which cites the IRS reporting "over three times speed improvements"). The current number is third-party: an analyst post dated **August 20, 2026** reports Cloudera Data Engineering running **Apache Spark 4.1** with cuDF-based acceleration at "up to four times the speed" of a CPU setup, with the author's own caution that gains vary by workload ([shashi.co](https://www.shashi.co/2026/08/cloudera-speeds-up-spark-41-fourfold.html)). That is not Cloudera's press room and it is not a DGX Spark number — do not let it drift into a GB10 claim.

Two facts bound what we can plan:

- The shipped CE topology has **no GPU instance type** — `t3a.medium` through `r5a.4xlarge` (`blog/cloudera-ce-cm-evaluation.md`). A RAPIDS demo on CE means adding a GPU node group and wiring YARN GPU scheduling, which `nvidia-dgx-spark-research.md` §8 records as documented only generically and never for this topology.
- NVIDIA's own DGX Spark playbook set has **no RAPIDS-Accelerator-for-Apache-Spark content at all**. The closest is [CUDA-X Data Science](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/cuda-x-data-science/README.md) (conda `rapids=26.06`, `cuda-version=13.0`), which is standalone cuDF/cuML, and the [single-cell playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/single-cell/README.md) with a measured ~130 s end-to-end run on GB10 using cuPy/cuML/cuGraph/cuDF.

So the honest position for ch18: **cuDF/cuML on GB10 is proven and cheap to demo; RAPIDS-on-Apache-Spark belongs on the AWS side and needs a GPU node group we have not built.** Do not imply the DGX Spark accelerates a Cloudera Data Engineering job.

### 2.5 The concrete first integration

One demo, four moving parts, nothing invented:

1. CE on AWS with the **NiFi topology** (Kafka topology second).
2. `spark-dd06` serving a NIM endpoint on `:8000` (§4).
3. A reverse SSH tunnel from `spark-dd06` to the CE gateway (§2.3).
4. On the CE cluster, a **new** Process Group — never inline in a running one — of `GenerateFlowFile → InvokeHTTP (POST /v1/chat/completions) → PublishKafka`, following the `StreamTovLLM` shape documented in `completed/how-to-nifi-and-ai.md`. `InvokeHTTP`'s `HTTP Method` persists as `GET` unless the field is explicitly set, and its `Retry` relationship self-loops; both traps are in that reference.

What it shows a customer: their own on-prem-shaped cluster calling a private, desk-side model, with no token leaving the tunnel. Feeds ch18.

## 3. CDP Public Cloud on AWS

### 3.1 The environment we already have is the target

`srm-iceberg` exists, is rebuilt weekly, and already carries everything the DGX Spark needs on the far end. From `cloudera-iceberg-rest-catalog-aws-plan.md` and `cloudera-iceberg-rest-catalog-cso-plan.md`:

| Coordinate | Value |
|---|---|
| Data Lake gateway (public Knox front door) | `srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site` |
| Iceberg REST base URI | `https://<gateway>/srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest` (client appends `/v1/`) |
| Knox token URI | `.../cdp-datashare-access/knoxtoken/api/v2/token` — OAuth2 `client_credentials`, `REQUEST_BODY` |
| Namespace / tables | `poc_uc2.airlines` (3 rows), `poc_uc2.flights` (120k rows, partitioned by `flight_month`) |
| Template / scale | `semi-private`, `LIGHT_DUTY` — HA IDBroker breaks credential vending, so never `ENTERPRISE` |

The environment is provisioned by [`cdp-tf-quickstarts`](https://raw.githubusercontent.com/cloudera-labs/cdp-tf-quickstarts/main/README.md) (tfvars: `env_prefix` ≤12 chars lowercase, `aws_region`, `deployment_template`); AWS publishes the alternate [`aws-ia/terraform-cloudera-cdp`](https://github.com/aws-ia/terraform-cloudera-cdp) Partner Solution module, whose `ingress_extra_cidrs_and_ports` variable is the lever for letting a home-LAN client CIDR in. The prerequisite easiest to miss on a first registration: DNS enabled on the VPC, and VPC + subnets tagged `shared`, private subnets `kubernetes.io/role/internal-elb:1`, public subnets `kubernetes.io/role/elb:1` ([AWS VPC requirements](https://docs.cloudera.com/cdp-public-cloud/cloud/requirements-aws/topics/mc-aws-req-vpc.html)). The same three prerequisite buckets — network, S3, cross-account IAM — are restated in the [reference architecture](https://docs.cloudera.com/cdp-public-cloud/cloud/aws-refarch/topics/cloudera-private-link-network-iam-requirement.html).

### 3.2 DataFlow inbound — the mechanism that makes this work at all

[Inbound Connections](https://docs.cloudera.com/dataflow/cloud/about-inbound-connections.html) give a CDF flow deployment a stable public hostname with TLS/mTLS auto-provisioned, on AWS and Azure: the server cert is signed by a public root CA and a single intermediate CA signs client certs. Every NiFi Listen-family processor is supported, including custom ones, but the listen processor needs a `StandardRestrictedSSLContextService` named **exactly** `Inbound SSL Context Service`, auto-populated at cluster deployment ([configuring inbound connection support](https://docs.cloudera.com/dataflow/cloud/develop-flow-definitions/topics/cdf-configuring-inbound-connection-support.html)). There is an off-the-shelf ListenHTTP "filter to Kafka" ReadyFlow that schema-validates incoming events against Schema Registry before writing to a topic ([announcement](https://community.cloudera.com/t5/What-s-New-Cloudera/Cloudera-DataFlow-for-the-Public-Cloud-introduces-Inbound/ba-p/343616)).

That is the clean edge path: **NiFi on `spark-dd06` POSTs HTTPS into CDF, the event gets validated, it lands in Kafka — no broker exposed, no security-group work on the Cloudera side.** When CDF is not in the picture, the direct path is Data Hub Kafka on port **9093** with `security.protocol=SASL_SSL`, `sasl.mechanism=PLAIN`, the FreeIPA cert imported into the client truststore via `keytool`, and workload credentials from the Management Console; broker hostnames come from Cloudera Manager per cluster and there is no documented DNS naming pattern ([outside-VPC Kafka clients](https://docs.cloudera.com/cdf-datahub/7.3.1/connecting-kafka/topics/kafka-dh-connect-clients-outside-vpc.html)).

### 3.3 Iceberg REST Catalog from a Spark-hosted NiFi

This is the integration with the least new work, because all three read paths are already validated from a NiFi we control (`cloudera-iceberg-rest-catalog-cso-plan.md`, #152/#154/#156):

1. **`InvokeHTTP`** with a `StandardOauth2AccessTokenProvider` controller service pointed at the Knox token endpoint (`client_credentials`, `REQUEST_BODY` — Knox's two-step endpoint refuses Basic). Zero dependencies, works on any CFM build.
2. **`GetIceberg` + `RESTCatalogService`** — full-table read; needs the `nifi-iceberg-read-bundle` NAR from the `NiFi2-Processor-Playground` clone at `/home/tunas/NiFi2-Processor-Playground`.
3. **`QueryIceberg` + `RESTCatalogService`** — SQL with Iceberg-native predicate and projection pushdown; a partition filter pruned **11 of 12 manifests** on `poc_uc2.flights`.

The exports to lift are `files/cso-prod-1/flows/prod/GetIcebergDemo.flow.json` and `files/cso-prod-1/flows/prod/QueryIcebergDemo.flow.json`. Three traps carry over unchanged: the client's public egress IP must be in the Data Lake `*-knox-sg` on 443 — the DGX Spark egresses on the same home IP as WindowsDesktop, so that is a one-line SG check, not new work; the `X-Iceberg-Access-Delegation: vended-credentials` header is what unlocks the datashare's S3 read credentials on `loadTable`; and the datashare is **read-only by design**, so a write is a different endpoint, identity and catalog service entirely. Cloudera's [REST Catalog overview](https://docs.cloudera.com/runtime/7.3.1/overview/topics/cr-ds-cloudera-iceberg-rest-catalog.html) describes it as the Apache Iceberg REST Catalog Open API extended with Ranger for authorization and Knox as gateway, serving Apache Spark, Trino, Snowflake, AWS Athena, AWS EMR and Databricks — a Spark-hosted NiFi is one more REST client on that list, not a special case.

### 3.4 Cloudera AI — Workbench → AI Registry → AI Inference

The chain, in the order a demo walks it:

- **Workbench** is the workspace formerly called CML — projects, sessions, ML Runtimes (CPU or GPU), experiments, models as REST endpoints, jobs, applications. Our live build is `2.0.56-h3000-b120` (`get-started-cloudera-ai-workbench.md`), and the MCP bridge to it is cloned at `/home/tunas/CAI_Workbench_MCP_Server`.
- **AI Registry** stores the model plus version, dependencies, performance and lineage, and the deploy flow is AI Registry → select model → Actions → Deploy → choose project → Go. Its [standalone API](https://docs.cloudera.com/machine-learning/cloud/models/topics/ml-registry-standalone-api.html) imports external models from NVIDIA NGC or Hugging Face by POST but **cannot upload a model from a local machine**, and "the Cloudera AI Registry API is available only on AWS and Azure." Hugging Face import through Model Hub is explicitly ["in Technical Preview and not recommended for production deployments"](https://docs.cloudera.com/machine-learning/1.5.5/model-hub/topics/ml-import-model-hugging-face.html).
- **AI Inference** serves the endpoint, powered by NVIDIA NIM microservices ([Cloudera + NVIDIA](https://www.cloudera.com/partners/solutions/nvidia.html)). NIM auto-selects its backend — TensorRT-LLM, vLLM or SGLang — based on model and GPU ([GTC Paris blog, June 11 2025](https://www.cloudera.com/blog/partners/cloudera-supercharges-your-private-ai-with-cloudera-ai-inference-nvidia-ai-q-and-nvidia-nim.html)), and exposes the three NIM optimization profiles Latency, Throughput and Generic ([AI Inference announcement](https://www.cloudera.com/blog/business/cloudera-introduces-ai-inference-service-with-nvidia-nim.html)). GPU-instance-type validators run during NVIDIA model deployment as of the July 2025 Cloudera on Cloud release ([release summary](https://docs.cloudera.com/cdp-public-cloud/cloud/release-summaries/topics/announcement-202507.html)).

**Instance types and quota.** The [sizing guide](https://docs.cloudera.com/machine-learning/cloud/setup-cloudera-ai-inference/topics/ml-caii-caii-configuration-sizing.html) names `g5.12xlarge` (A10G GPUs) as the cost-efficient node group — one instance carries two replicas at normal load and a second autoscales in at peak or during a rolling update; `g5.48xlarge` is the less efficient single-node alternative. Worked for Llama 3.1 70B FP16 at two replicas with tensor parallelism 2: **4 A10G at normal load, 6 at peak, and 8 additional simultaneously during a rolling update**, with storage `S = So + Σ(ri×Si) + Sc` = ~40 GB OS + ~296 GB model artifacts + ~20 GB container images → **512 GB recommended**. Llama 3.1 8B Instruct is sized at two A10G per replica on the same node group. Quota is the step that bites before any of that: the account's running On-Demand G-instance vCPU limit in the target region has to cover the node group, and **what our account actually holds is unverified** — check it before the first deploy, not after the validator fails.

**Status, stated carefully.** The February 9, 2026 press release says AI Inference is ["now available on premises"](https://www.cloudera.com/about/news-and-blogs/press-releases/2026-02-09-cloudera-unveils-next-phase-of-ai-inferencing-and-unified-data-access-capabilities.html), accelerated by NVIDIA Blackwell GPUs, the NVIDIA Dynamo-Triton Inference Server and NIM microservices, with support for the latest Nemotron open models — and it uses neither "GA" nor "Technical Preview." The earlier on-prem Technical-Preview milestone is **refuted as commonly stated**: two of three verification lenses knocked down the exact date and the maturity label (`nvidia-dgx-spark-research.md` §7). So write it as *available, status not GA-labeled*, never as GA. Several adjacent features are openly pre-GA: [Application Serving is titled "(Technical Preview)"](https://docs.cloudera.com/machine-learning/cloud/ai-inference/topics/ml-caii-application-serving-overview.html), and authorization, canary/blue-green, A/B testing and GenAI business monitoring are all marked "coming soon" on the [product page](https://www.cloudera.com/products/machine-learning/ai-inference-service.html) — the same page that carries the vendor's "up to 36x faster inference on NVIDIA GPUs and nearly 4x the throughput on CPUs," quoted here as marketing, not measurement. The [docs index](https://docs.cloudera.com/machine-learning/cloud/ai-inference/index.html) confirms canary deployment strategies and autoscaling are documented features — a real parity gap against a bare container on a desk, which has neither.

**Agent Studio + Nemotron.** Agent Studio is ["a versatile low-code to high-code platform for building, testing, and deploying multi-agent workflows"](https://docs.cloudera.com/machine-learning/cloud/use-ai-studios/topics/ml-agent-studio-overview.html) that graduates to high-code through Workbench, with built-in observability and logging. The [March 18, 2026 blog](https://www.cloudera.com/blog/partners/cloudera-agent-studio-and-nvidia-bring-next-gen-agents-to-enterprise-ai.html) puts NVIDIA Nemotron models underneath it, on NVIDIA Blackwell GPUs with Dynamo-Triton, across four pillars: dynamic multi-step planning with iterative self-evaluation, multi-agent collaboration with artifact-driven communication, context engineering, and sandboxed execution with policy-enforced isolation. **GB10 is a Blackwell-family die** — that is the strongest concrete tie between this hardware and Cloudera's current AI roadmap, and it is also why running a Nemotron locally is worth doing: NVIDIA's [Nemotron playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nemotron/README.md) serves Nemotron Nano through `vllm/vllm-openai:v0.20.0` on port 8000 with `--max-model-len 131072`. Lead-model candidate, not a lock. What no fetched page documents: how an Agent Studio workflow deploys as an endpoint and how it picks between AI Inference and an external provider. That gap is open, not omitted.

### 3.5 The API shape, and the base-URL swap

Per the [authentication doc](https://docs.cloudera.com/machine-learning/cloud/ai-inference/topics/ml-caii-authentication.html): two mechanisms — Cloudera Workload Authentication JWTs (short-lived, issued by the Knox Gateway Server or the User Management Service) and Knox API keys for long-lived connectivity — both carried as `Authorization: Bearer`. Per the [OpenAI-API invocation doc](https://docs.cloudera.com/machine-learning/cloud/ai-inference/topics/ml-caii-make-inference-call-model-endpoint-with-openai-api.html), the endpoint pattern is `https://[DOMAIN]/namespaces/serving-default/endpoints/[ENDPOINT_NAME]/v1`, the SDK's `base_url` is that URL with the last two path components removed, and `model=` must be the **AI-Registry-assigned name**, not the raw Hugging Face or NGC id.

| | Local on `spark-dd06` | Cloudera AI Inference |
|---|---|---|
| Base URL | `http://192.168.1.203:8000/v1` | `https://[DOMAIN]/namespaces/serving-default/endpoints/[NAME]/v1` |
| Auth | none | `Authorization: Bearer <JWT>` (Knox or UMS) |
| Model name | raw HF/NGC id, e.g. `meta/llama-3.1-8b-instruct` | the AI-Registry-assigned name |
| Protocol | OpenAI-compatible | OpenAI-compatible (LLMs) or Open Inference Protocol (predictive models) |

Three lines differ. That table is the whole thesis of ch20.

## 4. NIM on the DGX Spark, for parity

If the point is parity with Cloudera AI Inference, then the local half runs **NIM**, not a hand-rolled vLLM — same microservice, same optimization profiles, same API surface. NVIDIA ships DGX Spark-specific NIM images: `nvcr.io/nim/meta/llama-3.1-8b-instruct-dgx-spark:latest`, with `nvcr.io/nim/teams/qwen/containers/qwen3-32b-dgx-spark` as the larger alternative ([NIM playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nim-llm/README.md)). Llama 3.1 8B is also the model Cloudera's own sizing guide works through on `g5.12xlarge`, which makes it the natural first parity pair — two A10G on AWS versus one unified-memory GB10 here.

```bash
# expected — verify on the box (spark-dd06, aarch64, driver 580.173.02 / CUDA 13.0)
docker login nvcr.io                 # NGC API key — 86 characters, == suffix
mkdir -p ~/.cache/nim
docker run -d --name nim-llama31-8b --gpus all \
  --shm-size=16GB \
  -v ~/.cache/nim:/opt/nim/.cache \
  -p 8000:8000 \
  nvcr.io/nim/meta/llama-3.1-8b-instruct-dgx-spark:latest
# Model cache ~/.cache/nim, workspace ~/.local/share/nim/workspace, 10-50 GB per model.
# Playbook estimate: 15-30 minutes for the first pull and start.
```

Three GB10 specifics the playbook calls out, which the runbook has to inherit: `--shm-size=16GB` is the stated minimum recommendation; the unified-memory architecture "enables dynamic GPU/CPU memory sharing, though applications may need manual buffer cache flushing" — the flush is `sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'` per the [vLLM playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vllm/README.md); and `nvidia-smi` reports memory as "Not Supported" on this box because it shares the 128 GB pool (`CLAUDE-CHECKIN.md`), so any memory panel reads `/proc/meminfo`, not NVML. That same README contains **no Cloudera mentions at all**, and no repo anywhere in the research corpus combines a DGX Spark with any Cloudera component — the bridge in §5 is ours to build, first of its kind.

The identical request, both ends:

```bash
# expected — verify on the box
# Local NIM on spark-dd06
curl -s http://192.168.1.203:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"meta/llama-3.1-8b-instruct","messages":[{"role":"user","content":"Name three Iceberg table maintenance operations."}]}'

# Cloudera AI Inference — same body, two additions: the bearer token and the registry model name
curl -s "https://${CAII_DOMAIN}/namespaces/serving-default/endpoints/${ENDPOINT}/v1/chat/completions" \
  -H "Authorization: Bearer ${CDP_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"model":"'"${REGISTRY_MODEL_NAME}"'","messages":[{"role":"user","content":"Name three Iceberg table maintenance operations."}]}'
```

## 5. "Same code, two backends", formalized

Three artifacts, one config delta each. Nothing here is new code — all three already exist in the repo pointed at a local endpoint.

### 5.1 One Python client

```python
# expected — verify on the box
import os
from openai import OpenAI

# Local:  BASE_URL=http://192.168.1.203:8000/v1  TOKEN=not-needed  MODEL=meta/llama-3.1-8b-instruct
# CAII:   BASE_URL=https://<domain>/namespaces/serving-default/endpoints/<name>/v1
#         TOKEN=<Knox or UMS JWT>                MODEL=<AI-Registry-assigned name>
client = OpenAI(base_url=os.environ["BASE_URL"], api_key=os.environ["TOKEN"])
print(client.chat.completions.create(
    model=os.environ["MODEL"],
    messages=[{"role": "user", "content": "Summarise this flow's failure relationships."}],
).choices[0].message.content)
```

Config delta: **three environment variables.** The JWT is short-lived by default, so a demo that runs longer than the token's life either refreshes it or uses a Knox API key — that choice is a demo-design decision, not an implementation detail.

### 5.2 One NiFi flow

The flow is `InvokeHTTP` POSTing to `/v1/chat/completions`, in **its own new Process Group** — never inline in a live one. The delta between backends is two properties and one controller service:

| | Local | Cloudera AI Inference |
|---|---|---|
| `InvokeHTTP` `Remote URL` | `http://192.168.1.203:8000/v1/chat/completions` | `https://<domain>/namespaces/serving-default/endpoints/<name>/v1/chat/completions` |
| Auth | none | `Request OAuth2 Access Token Provider` = a `StandardOauth2AccessTokenProvider` CS, client id/secret from a Parameter Context |
| Model field in the request body | raw HF/NGC id | AI-Registry-assigned name |

The OAuth2-provider controller service is exactly the chain already validated against the Iceberg REST Catalog (`cloudera-iceberg-rest-catalog-cso-plan.md`) — it generalizes to any Knox-fronted endpoint by swapping the URL, and the provider is reused unchanged. **Credentials go in a Parameter Context, never as a literal processor property**, and never GET-then-PUT a processor that has sensitive properties: the masked `********` writes straight back as a literal and destroys the credential.

### 5.3 One Flink Agents job

`files/cso-prod-1/flink-agents/vllm_review_agent.py` is the job that already ran stable on the `cso-prod-1` profile — JobManager plus one TaskManager, **199 end-to-end vLLM calls including the tool leg** ([#231](https://github.com/cldr-steven-matison/DesktopShare/issues/231), recorded in `files/cso-prod-1/VALIDATION.md`), on image `cso-operator-flink-agents:0.3.1` built from source and deployed by `files/cso-prod-1/flink-agents/flinkdeployment.yaml`. flink-agents 0.3.1 ships no vLLM integration — `OPENAI_COMPLETIONS_CONNECTION` is the supported path, which is precisely why it repoints at Cloudera AI Inference with no code change:

```python
# expected — verify on the box
# files/cso-prod-1/flink-agents/vllm_review_agent.py — the backend swap
vllm_server_descriptor = ResourceDescriptor(
    clazz=ResourceName.ChatModel.OPENAI_COMPLETIONS_CONNECTION,
    api_base_url=os.environ["BASE_URL"],   # was http://vllm-service.default.svc.cluster.local:8000/v1
    api_key=os.environ["TOKEN"],           # was "not-needed"
)
VLLM_MODEL = os.environ["MODEL"]           # was Qwen/Qwen2.5-7B-Instruct-AWQ
```

Two operational notes carry over from that run and belong in ch20. The agent class must live in **its own importable module** shipped with `flink run -pyfs`, not defined in the submitted `__main__` script, or pemja fails on the TaskManager with `module '__main__' has no attribute ...`. And the model has to be able to hold a "reply with bare JSON" contract — the 3B that job started on managed 2–5 parseable replies out of 15, the AWQ 4-bit 7B did it reliably. On a 121 GB box that constraint mostly evaporates, which is itself the demo point.

## 6. Out-of-box integration catalogue

Every row is a pattern we already run on at least one side. "Spark side" means what runs on `spark-dd06`; nothing here requires the DGX Spark to be a cluster member.

| # | Spark side | AWS side | Data path | Demo value | Chapter |
|---|---|---|---|---|---|
| 1 | NiFi `InvokeHTTP` + Knox OAuth2 CS | Iceberg REST Catalog on the Data Lake | HTTPS out, Knox `client_credentials`, `vended-credentials` header | Read a governed Iceberg table from a desk-side flow with no Iceberg jars | ch19 |
| 2 | NiFi `QueryIceberg` + `RESTCatalogService` | Same catalog, `poc_uc2.flights` | Iceberg-native predicate and projection pushdown | Metadata-layer partition pruning — 11 of 12 manifests skipped | ch19 |
| 3 | NiFi posting out over HTTPS | CDF Inbound Connection → ReadyFlow → Kafka | mTLS to an auto-provisioned public hostname | Edge-to-cloud ingest with no broker exposed | ch18, ch19 |
| 4 | Kafka producer on the box | Data Hub Kafka, port 9093 | `SASL_SSL`/`PLAIN` + FreeIPA cert in the truststore | Direct-broker fallback when CDF is not in play | ch19 |
| 5 | NIM on `:8000` (Llama 3.1 8B) | AI Inference endpoint, same model class | One client, two base URLs | The SE money shot: identical output, three lines changed | ch05, ch20 |
| 6 | Flink Agents job on the local cluster | AI Inference as the chat-model resource | `OPENAI_COMPLETIONS_CONNECTION` swap | An agentic Flink job that runs desk-local or cloud-scale | ch11, ch20 |
| 7 | Whisper + embeddings tier on GB10 | Workbench project consuming the transcripts | Batch push into the Data Lake bucket | Private speech-to-text feeding a governed project | ch07, ch19 |
| 8 | Reverse SSH tunnel from the box | CE on AWS, NiFi topology | CE-side `InvokeHTTP` → tunnelled `:8000` | On-prem-shaped cluster calling a private desk model | ch18 |
| 9 | cuDF/cuML notebooks on GB10 | Apache Spark + RAPIDS on a Cloudera cluster | Same libraries, two scales | Explains the RAPIDS story without over-claiming GB10 | ch18 |
| 10 | MiNiFi Java agent, EFM class `NvidiaSpark-1` | Kafka topic on Data Hub or CE | Agent → local NiFi → cloud sink | Extends the Jetson → desk → cluster ladder to AWS | ch12, ch19 |

Rows 1, 2 and 6 are the cheapest — their local half is already built and validated. Row 5 is the one to record on video.

## 7. Stand-up runbook pointers and cost control

Neither environment is something to leave running. Both have a documented exit; use it.

```bash
# as-built (blog/cloudera-ce-cm-evaluation.md) — CE on AWS, the three exits
ansible-navigator run playbooks/pause.yml -e @config.yml -m stdout      # stop EC2, keep EBS + state
ansible-navigator run playbooks/resume.yml -e @config.yml -m stdout     # start it back up
ansible-navigator run playbooks/infrastructure-teardown.yml -e @config.yml -m stdout
```

```bash
# as-built (blog/cloudera-ce-cm-evaluation.md) — confirm nothing is left billing
aws ec2 describe-instances --profile <your-profile> --region us-east-2 \
  --filters "Name=tag:deployment,Values=<name_prefix>" \
            "Name=instance-state-name,Values=running,pending,stopping,stopped" \
  --query 'length(Reservations[].Instances[])' --output text
# -> 0
```

The numbers to plan around, all from our own records or the cited project docs:

| Thing | Number | Source |
|---|---|---|
| CE on AWS running cost | ~$2/hr, ~$45/day at on-demand rates | `blog/cloudera-ce-cm-evaluation.md` |
| CE stand-up, documented | ~40–50 min | [cloudera-ce-aws](https://cloudera-labs.github.io/cloudera-ce-aws/) |
| CE stand-up, our measured run | ~2.5 h — long poles are parcel distribution and 14 Kerberized services, not Terraform (~10 min) | `blog/cloudera-ce-cm-evaluation.md` |
| Public Cloud base environment | up to 60 min deploy, ~20 min teardown | [cdp-tf-quickstarts](https://raw.githubusercontent.com/cloudera-labs/cdp-tf-quickstarts/main/README.md) |
| Our Public Cloud weekly restore | ~1 h 40 m redeploy.sh + ~15 min CDW playbook | `cloudera-iceberg-rest-catalog-aws-plan.md` |
| Bastion for private-subnet UIs | `t3.small` ≈ $0.02/hr, stop it when idle | `cloudera-iceberg-rest-catalog-aws-plan.md` |

The Public Cloud reaper is the cost control that already works: the environment goes EOD Thursday and Monday's redeploy.sh restores full state. The operating assumption for any DGX Spark integration demo is therefore **the far end may not exist right now** — every credential, CRN and share id churns on rebuild and lands in `config.env`. Design the flow so the endpoint URL and the OAuth client id/secret come from a Parameter Context, and a rebuild becomes a parameter edit instead of a flow edit.

Setup friction worth pre-empting, all from `blog/cloudera-ce-cm-evaluation.md`: pin the EE tag `1.0.0-amd64`, because `:latest` is not published; a browser session on the AWS access portal is not CLI credentials, and an SSO profile missing `sso_account_id`/`sso_role_name` still cannot resolve them; the license is the `.txt`, not the `.zip`; keep `common_password` alphanumeric, because Cloudera's automation sets service passwords through `https://admin:PASSWORD@host/...` basic-auth calls and an `@` inside the password corrupts the URL — the failing task is `no_log`, so the error is censored and a teardown plus redeploy is the clean fix; `enable_prometheus` is declared twice in the project's `group_vars`, and last-wins makes the effective default `true`; and piping an `ansible-navigator` run through `tee` reports `tee`'s exit code, so a failed run looks green — trust the `PLAY RECAP` counts.

## 8. What NOT to do

- **Don't promise CDP Base or CE running on the DGX Spark.** The EE image publishes only `1.0.0-amd64` and the Terraform AMI filter pins `architecture = ["x86_64"]`. Base runs on AWS; the box feeds it.
- **Don't call Cloudera AI Inference on-prem GA.** The February 2026 press release avoids both labels and the Technical-Preview milestone as commonly stated is refuted in `nvidia-dgx-spark-research.md` §7. Say "available, status not GA-labeled."
- **Don't let the Apache Spark 4.1 "4x" figure become a GB10 number.** It is a third-party analyst post about Cloudera Data Engineering with cuDF, carrying the author's own workload caveat.
- **Don't GET-then-PUT a NiFi processor with sensitive properties.** The masked `********` writes back as a literal and destroys the credential — use a Parameter Context.
- **Don't add the AI-Inference call inline to a live Process Group.** New logic goes in its own new PG, and `Retry` is not `Failure`.
- **Don't hand-build an EFM agent-deployer command, and never reuse an `agentIdentifier` for a new enrollment.** The command comes only from EFM's Deploy Agent CLI screen or `POST /efm/api/agent-deployer/generateCommand` with `agentIdentifier` omitted.
- **Don't start an ad-hoc `kubectl port-forward` or `minikube tunnel` on WindowsDesktop.** The canonical set lives as zellij panes in ~/.config/zellij/layouts/kube-service-ports-efm.kdl, and a LAN-exposed port there also needs a Windows Firewall inbound rule — the 2026-07-31 Mosquitto/1883 lesson.
- **Don't plan anything that takes WindowsDesktop's vLLM `:8000` away.** It also serves the OpenClaw Telegram bridge; the bridge has to be repointed and proven before that endpoint moves.
- **Don't restart or redeploy a live service to make a demo work.** Ask fresh every time — and never `kubectl delete pod mynifi-0` as a restart, because those volumes are `emptyDir` and the flow goes with them.
- **Don't build the Public Cloud environment at `ENTERPRISE` scale.** HA IDBroker breaks credential vending and kills the REST Catalog's vended-credentials step; keep `LIGHT_DUTY` pinned explicitly even when only the deployment template changes.
- **Don't leave either environment running unwatched.** pause.yml or teardown for CE; the reaper handles Public Cloud, and the `aws ec2 describe-instances` count is the proof.

## Open questions

- Which footprint hosts the first integration — the existing `srm-iceberg` Public Cloud environment, already live and rebuilt weekly, or a fresh CE cluster that is customer-shaped but costs ~$45/day? Steven's call; the Public Cloud path is cheaper because it already exists.
- What the AWS account's running On-Demand G-instance vCPU quota is in the target region. Unverified, and it gates any `g5.12xlarge` AI Inference node group.
- Whether a fully custom NIM container — specifically a `-dgx-spark` tagged image — can be registered into AI Registry at all, or only the curated Model Hub catalogue can. Neither confirmed nor ruled out in any fetched source.
- How an Agent Studio workflow deploys as an endpoint, and how it selects between AI Inference and an external provider. Not documented on any page fetched.
- Whether driving a CE deploy from `spark-dd06` works under emulation, since no `arm64` EE tag is published. Untested.
- Whether GPU node groups are supportable inside the `cloudera-ce-aws` topology unmodified, or need separate work. The generic CDP Base GPU guidance exists; its applicability to this topology does not.
- No ARM64 or Graviton statement for any Cloudera AI component was found in any source — absence of evidence, not evidence of absence.

## Definition of done

- Both AWS shapes are described with their real stand-up time, inbound mechanism, auth and cost, each traced to a source.
- The amd64 question for CE is answered from two independent places, and the consequence is stated plainly rather than worked around.
- The DGX-Spark-side NIM run and the Cloudera AI Inference call appear as the *same* request, with the delta isolated to base URL, auth header and model name.
- The three "same code" artifacts each name the exact file that already exists and the exact config delta — not a rewrite.
- The integration catalogue has ten rows, each mapped to a chapter, and each row's local half is either already built or one command away.
- Every number carries its URL or the repo doc it came from; the Phase-0 model lock is presented as open, and no model is called locked.
- `python3 files/issue-226/doc-check.py` reports zero errors against this file.

## When this ships

- `nvidia-dgx-spark-plan.md` §4 flips work-stream I from "doc not yet written" to drafted, and the Phase-5 gate — the AWS demos running against a real environment — becomes executable.
- Chapters ch05, ch18, ch19 and ch20 under `files/nvidia-spark-guide/` are unblocked and take their content from §2–§6 here; the tracker `Complete Developer Guide for Nvidia Spark with Cloudera.md` records the state change.
- The first executed integration turns every "# expected — verify on the box" block in §2.3, §4 and §5 into an as-built block the same day, and the measured numbers replace the estimates.
- If the NiFi legs change shape, the result is recorded back into `skills/nifi-and-ai/references/patterns.md` and `cloudera-iceberg-rest-catalog-cso-plan.md` rather than only here — and a skill change always gets its own commit.
- Anything customer-facing gets a clean blog per `agent/writing-style.md`, with the issue numbers stripped.

## Resources

- Companion docs: `nvidia-dgx-spark-plan.md` · `nvidia-dgx-spark-research.md` (§7 Cloudera AI, §8 Cloudera on AWS) · `nvidia-dgx-spark-landscape.md` · `nvidia-dgx-spark-runbook.md` · `nvidia-dgx-spark-k3s-cso.md` · `nvidia-dgx-spark-efm-agent.md` · `nvidia-dgx-spark-local-kb.md` · `nvidia-dgx-spark-cloudera-demos.md` · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- Precedent in this repo: `cloudera-iceberg-rest-catalog-aws-plan.md` · `cloudera-iceberg-rest-catalog-cso-plan.md` · `blog/cloudera-ce-cm-evaluation.md` · `get-started-cloudera-ai-workbench.md` · `flink-agents-cso-plan.md` · `cso-prod-1-cutover-plan.md` · `files/cso-prod-1/VALIDATION.md` · `files/cso-prod-1/flink-agents/vllm_review_agent.py` · `files/cso-prod-1/flink-agents/flinkdeployment.yaml` · `files/cso-prod-1/flows/prod/GetIcebergDemo.flow.json` · `files/cso-prod-1/flows/prod/QueryIcebergDemo.flow.json` · `skills/nifi-and-ai/references/site-to-site.md` · `skills/nifi-and-ai/references/patterns.md` · `CLAUDE-CHECKIN.md`
- Sub-repos cloned on this box: `/home/tunas/cloudera-ce-aws` · `/home/tunas/iceberg-mcp-server` · `/home/tunas/CAI_Workbench_MCP_Server` · `/home/tunas/NiFi2-Processor-Playground`
- Cloudera AI: [AI Inference docs index](https://docs.cloudera.com/machine-learning/cloud/ai-inference/index.html) · [authentication](https://docs.cloudera.com/machine-learning/cloud/ai-inference/topics/ml-caii-authentication.html) · [OpenAI-API calls](https://docs.cloudera.com/machine-learning/cloud/ai-inference/topics/ml-caii-make-inference-call-model-endpoint-with-openai-api.html) · [configuration and sizing](https://docs.cloudera.com/machine-learning/cloud/setup-cloudera-ai-inference/topics/ml-caii-caii-configuration-sizing.html) · [AI Registry standalone API](https://docs.cloudera.com/machine-learning/cloud/models/topics/ml-registry-standalone-api.html) · [Agent Studio overview](https://docs.cloudera.com/machine-learning/cloud/use-ai-studios/topics/ml-agent-studio-overview.html)
- Cloudera on AWS: [cdp-tf-quickstarts](https://raw.githubusercontent.com/cloudera-labs/cdp-tf-quickstarts/main/README.md) · [aws-ia/terraform-cloudera-cdp](https://github.com/aws-ia/terraform-cloudera-cdp) · [AWS VPC requirements](https://docs.cloudera.com/cdp-public-cloud/cloud/requirements-aws/topics/mc-aws-req-vpc.html) · [DataFlow Inbound Connections](https://docs.cloudera.com/dataflow/cloud/about-inbound-connections.html) · [Kafka clients outside the VPC](https://docs.cloudera.com/cdf-datahub/7.3.1/connecting-kafka/topics/kafka-dh-connect-clients-outside-vpc.html) · [Iceberg REST Catalog](https://docs.cloudera.com/runtime/7.3.1/overview/topics/cr-ds-cloudera-iceberg-rest-catalog.html) · [cloudera-ce-aws](https://cloudera-labs.github.io/cloudera-ce-aws/)
- NVIDIA: [NIM on DGX Spark playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nim-llm/README.md) · [vLLM playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vllm/README.md) · [Nemotron playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nemotron/README.md) · [CUDA-X Data Science playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/cuda-x-data-science/README.md) · [Cloudera + NVIDIA](https://www.cloudera.com/partners/solutions/nvidia.html)
