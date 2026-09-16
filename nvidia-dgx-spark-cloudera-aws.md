# The DGX Spark and Cloudera on AWS

> **Status (2026-09-16).** Work-stream **I** of the DGX Spark series (design [#241](https://github.com/cldr-steven-matison/DesktopShare/issues/241), closed; field runs [#341](https://github.com/cldr-steven-matison/DesktopShare/issues/341), [#342](https://github.com/cldr-steven-matison/DesktopShare/issues/342), [#345](https://github.com/cldr-steven-matison/DesktopShare/issues/345); EPIC [#356](https://github.com/cldr-steven-matison/DesktopShare/issues/356)). This doc is the source for the **platform** scope: using the DGX Spark with each Cloudera platform form factor on AWS, in three explicit paths — **(1) CDP Base CE on AWS, (2) CDP Public Cloud on AWS, (3) Cloudera AWC on AWS.** Path 3 keeps its own peer doc, `nvidia-dgx-spark-cloudera-awc.md` (#283); this doc carries the reference and the field-validation checklist, not a duplicate runbook. In every path the DGX Spark is a *client*, never a cluster node, and the parity payload is the OpenAI-compatible API on both sides. **Field state:** path 1 is as built end to end from the box (§2.5, 2026-09-16; the cluster is still up, teardown [#357](https://github.com/cldr-steven-matison/DesktopShare/issues/357), clean redeploy [#358](https://github.com/cldr-steven-matison/DesktopShare/issues/358)); path 2's environment is live and the REST Catalog read is proven from the box with curl, the in-NiFi read is [#355](https://github.com/cldr-steven-matison/DesktopShare/issues/355) (§3.6); path 3's reachability, data plane and Kafka are proven in the peer doc and Cloudera AI Inference is blocked there ([#351](https://github.com/cldr-steven-matison/DesktopShare/issues/351)). Cloudera AI on AWS (§3.4, §5) is not field-run; every model named there is a candidate with its citation. Feeds guide chapters ch05, ch18, ch19, ch21 (Cloudera AI on AWS) and ch24 (the same-code arc); the AWC form factor is ch20 (platform) and ch22 (Cloudera AI on AWC, where RAPIDS lives), sourced from the peer doc.

## 1. The three platform paths, side by side

Cloudera on AWS is three different things that share a name and little else. Getting the DGX Spark into the story means knowing which one is on the other end of the wire, because the inbound path, the auth, the cost and the teardown all change.

**Path 1 — CDP Base / Community Edition on EC2** is the on-prem distribution running on cloud instances — Cloudera Manager, parcels, Kerberos, Auto-TLS, a fixed node topology. It is what a customer's data centre looks like, hosted where I can afford to leave it running for an afternoon. We run it: [`cloudera-labs/cloudera-ce-aws`](https://cloudera-labs.github.io/cloudera-ce-aws/) v1.0.0, deploying Cloudera Manager 7.13.2 / Runtime 7.3.2, field-run and written up in `blog/cloudera-ce-cm-evaluation.md`, with the repo cloned on this box at `/home/tunas/cloudera-ce-aws`. Detail in §2.

**Path 2 — CDP Public Cloud on AWS** is the SaaS control plane: an environment, a Data Lake, Data Hubs and Data Services provisioned into my own VPC and driven from Cloudera's control plane. We run that too — the `srm-iceberg` environment behind `cloudera-iceberg-rest-catalog-aws-plan.md`, currently `deployment_template = "semi-private"`, `LIGHT_DUTY` Data Lake, Runtime 7.3.2, with an Iceberg REST Catalog live and a weekly reaper. Detail in §3.

**Path 3 — Cloudera AWC on AWS** is Cloudera Anywhere, the `goes01` environment on AWS EKS: a containerized Cloudera platform whose Cloudera AI, Lakehouse Engine (Trino) and Object Store (Ozone) experiences the DGX Spark also targets. Its runbook lives in the peer doc `nvidia-dgx-spark-cloudera-awc.md` (#283); §4 here carries the reference and the field-validation checklist.

| | Path 1 — CDP Base / CE on EC2 | Path 2 — CDP Public Cloud on AWS | Path 3 — Cloudera AWC on AWS |
|---|---|---|---|
| What it is | Cloudera Manager + parcels on ~11 EC2 nodes, self-contained DNS/Kerberos/PostgreSQL/Auto-TLS | Control-plane-managed environment, Data Lake, Data Hubs, Data Services in my VPC | Containerized Cloudera platform on AWS EKS (`goes01`) — Cloudera AI, Trino, Ozone |
| What we already run | `cloudera-ce-aws` v1.0.0, CM 7.13.2 / Runtime 7.3.2 (`blog/cloudera-ce-cm-evaluation.md`) | `srm-iceberg`, Runtime 7.3.2, Iceberg REST Catalog + Impala/Trino/Hive VWs (`cloudera-iceberg-rest-catalog-aws-plan.md`) | `goes01` reachable from the box (#347); Knox SSO, Trino, Iceberg, Ozone S3 and Kafka (OAUTHBEARER) proven (#343, #351); Cloudera AI Inference blocked on a UI model deploy that fails on an AI Registry 503 (#351) |
| Inbound from outside | **None built in.** SSH + reverse HTTPS proxies ([cloudera-ce-aws](https://cloudera-labs.github.io/cloudera-ce-aws/)) — a tunnel or a jump host | DataFlow **Inbound Connections** (stable public hostname, auto mTLS) ([inbound connections](https://docs.cloudera.com/dataflow/cloud/about-inbound-connections.html)); or Data Hub Kafka on **9093** ([outside-VPC clients](https://docs.cloudera.com/cdf-datahub/7.3.1/connecting-kafka/topics/kafka-dh-connect-clients-outside-vpc.html)) | Peer-doc scope; box→`goes01` reachability is the gating open item |
| The AI story | Nothing GPU in the shipped topology — `t3a`/`r5a` (`blog/cloudera-ce-cm-evaluation.md`) | Cloudera AI: Workbench → AI Registry → AI Inference on GPU node groups ([CAII sizing](https://docs.cloudera.com/machine-learning/cloud/setup-cloudera-ai-inference/topics/ml-caii-caii-configuration-sizing.html)) | Cloudera AI experience on AWC — the ch22 form factor |
| What the DGX Spark is to it | An **external inference and edge node** reached through a tunnel | An **external client** of DataFlow / Kafka / Iceberg, and the *local* half of the same-code arc | An **external client** of the AWC experiences |
| Cost control | pause.yml / resume.yml / infrastructure-teardown.yml, ~$2/hr ~$45/day (`blog/cloudera-ce-cm-evaluation.md`) | Weekly reaper + redeploy.sh; the 60-day Cloudera on Cloud trial is the entry ([cdp-tf-quickstarts](https://raw.githubusercontent.com/cloudera-labs/cdp-tf-quickstarts/main/README.md)) | Per peer doc |

The thing all three paths have in common: **the DGX Spark never joins any of them.** It is a 20-core aarch64 box with one GPU and 121 GB usable of unified memory (`CLAUDE-CHECKIN.md`), sitting on a home LAN with no public IP. It is a peer of WindowsDesktop, not of an EC2 fleet. Every integration below is edge-to-platform, and the local half of each one is built by the two sibling work-streams: the on-box cluster in `nvidia-dgx-spark-k3s-cso.md` and the agent class in `nvidia-dgx-spark-efm-agent.md`.

## 2. CDP Base / Community Edition on AWS

### 2.1 The deploy path

Everything is baked into an Ansible execution-environment image, so the local machine needs a clone, a venv, `ansible-core` + `ansible-navigator`, a container runtime, AWS SSO and a Cloudera license text file ([cloudera-ce-aws getting started](https://cloudera-labs.github.io/cloudera-ce-aws/getting-started/index.html)). The one command that does everything, from our own run:

```bash
# as-built (blog/cloudera-ce-cm-evaluation.md) — v1.0.0, CM 7.13.2 / Runtime 7.3.2
ansible-navigator run playbooks/infrastructure.yml playbooks/services.yml \
  playbooks/cms.yml playbooks/ozone-cluster.yml -e @config.yml -m stdout
```

Four playbooks, four stages: Terraform provisions VPC + security groups + 11 EC2 nodes, Ansible configures FreeIPA/PostgreSQL/Caddy TLS, Cloudera Manager installs and licenses, then CM builds the cluster. Only the gateway node gets a public IP; everything else is private and reached through the Caddy reverse proxy on a `nip.io` hostname. The topology is selectable — Ozone, Kafka, Flink, NiFi, CSA or ECS ([cloudera-ce-aws](https://cloudera-labs.github.io/cloudera-ce-aws/)) — and **the NiFi and Kafka topologies are the ones this work-stream cares about.**

> **Ranger authz note (from #180, this Base deploy — source-verified 2026-09-15 PM).** Integrating the **CFM NiFi operator** with this cluster's Ranger: `spec.security.ranger` is an **authorizer**; the plugin downloads policies over **mTLS** (`xasecure.policymgr.clientssl.*` from `tls.secretName`; `adminIdentity` = the Ranger **server** DN) and has **no Kerberos login** (`krb5confSecret` "does not enable Kerberos based authentication"; `spec.security.kerberos` is NiFi *user* auth). So `RangerAdminRESTClient` calls the **plain** `/service/plugins/policies/download/<svc>` — never the `/secure/` SPNEGO endpoint every #180 probe hit. The plain endpoint bypasses Spring Security and is gated by `ranger.admin.allow.unauthenticated.download.access=true` (default false → 400 "Unauthenticated access not allowed") and, with `ranger.service.http.enabled=false`, a client-cert SAN/CN match against the service config `commonNameForCertificate`. Three Ranger-side settings, nothing de-Kerberized. Solr audit stays Kerberos-gated (deny record via `xasecure.audit.destination.file`). **Not runnable on this box:** `cfm-operator` ≥ 3.3.x is amd64-only (eng-confirmed 2026-09-15) and the DGX Spark is aarch64 — the 3.3.1-b15 upgrade hit `exec format error` and was rolled back to 3.0.0-b126. The proof is child issue #338 on WindowsDesktop: `files/issue-338/RUNBOOK.md`; authoritative operator doc: `files/issue-180/cfm-operator-ranger-authorization.md`.

### 2.2 The amd64 fact, and why it does not matter

CE on AWS is x86_64 top to bottom. Two independent confirmations, and neither is a doc-site statement — this closes the architecture question `nvidia-dgx-spark-research.md` §8 leaves open:

1. The execution-environment image is published for both architectures: `ghcr.io/cloudera-labs/cloudera-ce-aws:1.0.0` (and `1.0.1`, `latest`) is a multi-arch manifest with `1.0.0-amd64` and `1.0.0-arm64` behind it. On this box the deploy runs the `1.0.0-arm64` image natively with no `--platform` flag (`cloudera-ce-aws-runbook.md` §1); on Apple Silicon the amd64 pin runs emulated (`blog/cloudera-ce-cm-evaluation.md`). The EE's architecture is the driver's, not the cluster's.
2. The Terraform AMI filter in the clone at `/home/tunas/cloudera-ce-aws` pins `architecture = ["x86_64"]` (`tf_cluster_aws/hosts_common.tf`, read 2026-08-26 on `spark-dd06`) — the EC2 nodes themselves are x86_64 by construction, not by accident.

That is a real constraint and it costs us nothing, because **Base was never going to run *on* the DGX Spark.** The EE is an orchestration controller that drives Terraform and SSHes to nodes; it does no local compute, so even running it emulated here is a non-issue. The demo statement is: *Base runs on AWS at customer shape; the DGX Spark feeds it and serves inference to it.* Anything that promises "CDP Base on the desk" is a promise we cannot keep, and ch18 has to say so in its first paragraph.

> The corollary for this box, as built 2026-09-16 (#345): the deploy runs from `spark-dd06` on the native `1.0.0-arm64` image in 3 h 40 min, no emulation and no hand-off to WindowsDesktop. The cluster it builds is still x86_64.

### 2.3 Inbound paths for a Spark-hosted NiFi

CE has **no Inbound Connections equivalent**. The cluster is sealed behind SSH and reverse HTTPS proxies, so an external NiFi cannot simply POST at it. Three honest options, in order of preference:

| Path | Mechanism | Cost |
|---|---|---|
| **Reverse SSH tunnel from the box** | `ssh -R` from `spark-dd06` to the CE gateway publishes the Spark-hosted endpoint *inside* the cluster's network | No SG change, no public exposure; dies with the SSH session |
| **Gateway SG rule + Kafka external listener** | Open the broker port on the gateway SG to my public IP `/32`, produce straight in | Needs a Kafka topology, an SG edit, and my egress IP is not static |
| **Bastion + SOCKS proxy** | The pattern already proven on Public Cloud (`cloudera-iceberg-rest-catalog-aws-plan.md`, [#190](https://github.com/cldr-steven-matison/DesktopShare/issues/190)) | Browser/manual access, not a data path |

The reverse tunnel is the one to build first, because it inverts the direction that actually blocks us — the home LAN has no inbound path, so the connection must originate here:

```bash
# as-built 2026-09-16 (#341). NiFi runs on the four base workers, not on the gateway, and the
# gateway sshd has GatewayPorts no, so the forward goes to each worker through the gateway as a
# jump. Each NiFi node then sees the box's model at http://127.0.0.1:8000. No SG change, nothing
# exposed; the tunnels die with the shell.
CFG=~/cloudera-ce-aws/srm-cloudera-ce-base-ssh.config
O="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes"
for ip in 10.10.1.165 10.10.1.4 10.10.1.235 10.10.1.174; do
  ssh -F $CFG $O -o ProxyCommand="ssh -F $CFG $O -W %h:%p jump" \
      -N -R 127.0.0.1:8000:127.0.0.1:8000 ec2-user@$ip &
done
# proof from every worker: curl -s http://127.0.0.1:8000/v1/models -> nvidia/Qwen3.6-35B-A3B-NVFP4
# (files/issue-341/tunnel-probe-2026-09-16.txt). The gateway's 22/443 rules are pinned to the
# deploy-time egress IP; from the box that is a corp-VPN NAT address, so add the current /32 to
# the deployment's ingress prefix list when the gateway stops answering.
```

Site-to-Site NiFi→NiFi is the *right* shape once the tunnel exists, and it is a package deal: `userCertAuth` set at CR creation, one CA signing every cert, identity mapped by SAN not DN, peers declared as `User` CRs and never hand-POSTed policies — all of it in `skills/nifi-and-ai/references/site-to-site.md` and proven on our own cluster in `files/cso-prod-1/VALIDATION.md`. On CE the CA is Cloudera Manager's Auto-TLS rather than cert-manager, so the trust join is the unknown leg, not the flow.

### 2.4 RAPIDS for Apache Spark on Base GPU nodes

This is the one place where "Apache Spark" and "DGX Spark" sit in the same paragraph, so the naming rule earns its keep. RAPIDS Accelerator for Apache Spark gives GPU acceleration for SQL/DataFrame work with no code changes ([NVIDIA, April 12 2021](https://developer.nvidia.com/blog/cloudera-and-nvidia-collaborate-to-accelerate-data-analytics-and-ai-at-scale), which cites the IRS reporting "over three times speed improvements"). The current number is third-party: an analyst post dated **August 20, 2026** reports Cloudera Data Engineering running **Apache Spark 4.1** with cuDF-based acceleration at "up to four times the speed" of a CPU setup, with the author's own caution that gains vary by workload ([shashi.co](https://www.shashi.co/2026/08/cloudera-speeds-up-spark-41-fourfold.html)). That is not Cloudera's press room and it is not a DGX Spark number — do not let it drift into a GB10 claim.

**Measured on GB10 (#346, 2026-09-15):** cuDF/cuML in the `rapidsai/notebooks:26.06-cuda13-py3.14` container runs on sm_121 (cuDF 26.06.01, cuML 26.06.00): zero-code-change (`cudf.pandas`) 4.6× overall, 131× on string ops at 10M rows, cuML RandomForest 1.51× with accuracy parity. The Spark RAPIDS plugin runs on aarch64 from NVIDIA's `-cuda13-arm64` jar (537 MB) — 9 `Gpu*` operators in the final plan, functional on a shared GPU with a 35B model serving alongside. The plugin needs the classifier jar (`rapids-4-spark_2.13-26.08.1-cuda13-arm64.jar`), not the default amd64 jar; and `spark.rapids.memory.gpu.minAllocFraction=0.005` to start with vLLM resident (the default 0.25 demands 25% of 74 GiB free). The same `cudf_bench.py`, unchanged, on the Cloudera AI Workbench `goes01-cai` NVIDIA L4 (pip `cudf-cu12`, 2026-09-16) gives 4.6× overall at 100k rows (join 6.8×); the 10M-row run needs a 16 GB+ session. Full details in [`nvidia-dgx-spark-rapids-runbook.md`](nvidia-dgx-spark-rapids-runbook.md) and [`files/issue-346/results.md`](files/issue-346/results.md).

Two facts bound what we can plan:

- The shipped CE topology has **no GPU instance type** — `t3a.medium` through `r5a.4xlarge` (`blog/cloudera-ce-cm-evaluation.md`). A RAPIDS demo on CE means adding a GPU node group and wiring YARN GPU scheduling, which `nvidia-dgx-spark-research.md` §8 records as documented only generically and never for this topology.
- NVIDIA's own DGX Spark playbook set has **no RAPIDS-Accelerator-for-Apache-Spark content at all**. The closest is [CUDA-X Data Science](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/cuda-x-data-science/README.md) (conda `rapids=26.06`, `cuda-version=13.0`), which is standalone cuDF/cuML, and the [single-cell playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/single-cell/README.md) with a measured ~130 s end-to-end run on GB10 using cuPy/cuML/cuGraph/cuDF.

So the honest position — recorded in ch22 (Cloudera AI on AWC), where RAPIDS lives in the guide, not in a chapter of its own: **cuDF/cuML on GB10 is proven and cheap to demo, and the same script runs at the same speed-up in a Cloudera AI Workbench GPU session; RAPIDS-on-Apache-Spark on a Cloudera cluster needs a GPU node group that neither CE nor CDE on `goes01` has today (`MaxVCAvailableGPU 0`), and Runtime 7.3.2 has no CDS GPU path.** Do not imply the DGX Spark accelerates a Cloudera Data Engineering job.

### 2.5 The concrete first integration

One demo, four moving parts, nothing invented:

1. CE on AWS with the **NiFi topology** (Kafka topology second).
2. `spark-dd06` serving a NIM endpoint on `:8000` (§5).
3. A reverse SSH tunnel from `spark-dd06` to the CE gateway (§2.3).
4. On the CE cluster, a **new** Process Group — never inline in a running one — of `GenerateFlowFile → InvokeHTTP (POST /v1/chat/completions) → PublishKafka`, following the `StreamTovLLM` shape documented in `completed/how-to-nifi-and-ai.md`. `InvokeHTTP`'s `HTTP Method` persists as `GET` unless the field is explicitly set, and its `Retry` relationship self-loops; both traps are in that reference.

What it shows a customer: their own on-prem-shaped cluster calling a private, desk-side model, with no token leaving the tunnel. Feeds ch18.

**As built 2026-09-16 (#341, #345).** All four parts ran on `srm-cloudera-ce-base`: CE with the Ozone base and NiFi 2.3 grafted in (`cloudera-ce-aws-runbook.md`), the box's `nvidia/Qwen3.6-35B-A3B-NVFP4` on `:8000`, one tunnel per NiFi worker, and the `Ch18LlmBridge` PG built through Knox by `files/issue-341/build-flow.py` (GenerateFlowFile on the primary node every 60 s → InvokeHTTP POST → PublishKafka over SASL_SSL/GSSAPI with the per-node keytab at `${CONF_DIR}/nifi.keytab`). Three chat completions landed on `ch18-llm-responses` and were read back by the console consumer on sdx-01 (`files/issue-341/kafka-readback-2026-09-16.txt`); export `files/issue-341/Ch18LlmBridge.flow.json`. Two build traps worth the sentence: the CFM 4.10 `Kafka3ConnectionService` needs `StandardSSLContextService` (the PEM provider fails the cast at enable), and an InvokeHTTP property name that does not exist becomes a request header, which OkHttp rejects for the space in it. The Ozone ring on that cluster needed `hdds.grpc.tls.enabled=false` marked `final` in the service safety valve; the reason is in the runbook §4.1.

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

The exports to lift are `files/cso-prod-1/flows/prod/GetIcebergDemo.flow.json` and `files/cso-prod-1/flows/prod/QueryIcebergDemo.flow.json`. Three traps carry over unchanged: the client's public egress IP must be in the Data Lake `*-knox-sg` on 443 — the DGX Spark egresses on the same home IP as WindowsDesktop, so that is a one-line SG check, not new work; the `X-Iceberg-Access-Delegation: vended-credentials` header is what unlocks the datashare's S3 read credentials on `loadTable`; and the datashare is **read-only by design**, so a write is a different endpoint, identity and catalog service entirely. Cloudera's [REST Catalog overview](https://docs.cloudera.com/runtime/7.3.1/overview/topics/cr-ds-cloudera-iceberg-rest-catalog.html) describes it as the Apache Iceberg REST Catalog Open API extended with Ranger for authorization and Knox as gateway, serving Apache Spark, Trino, Snowflake, AWS Athena, AWS EMR and Databricks — a DGX-Spark-hosted NiFi is one more REST client on that list, not a special case.

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

Three lines differ. That table is the whole thesis of the same-code arc, ch24.

### 3.6 Field-validation status (as-built, 2026-09-16)

Read live from `spark-dd06` for #342 with the `cdp` CLI (`~/.venvs/cdpcli`) and the `aws` CLI (profile `cldr-se`, `us-east-2`); the raw capture is [`files/issue-342/as-built-2026-09-16.md`](files/issue-342/as-built-2026-09-16.md).

The `srm-iceberg` environment is **fully live** — the weekly rebuild (2026-09-15, after #344) completed: environment and Data Lake created 19:45 UTC, the Trino VW 21:46 UTC.

| Component | Live state (2026-09-16) |
|---|---|
| Environment `srm-iceberg-cdp-env` | `AVAILABLE`, `us-east-2`, VPC `vpc-07c7013dbb80d491e` (`10.10.0.0/16`), credential `srm-iceberg-xaccount-cred` |
| Data Lake `srm-iceberg-aw-dl` | `RUNNING`, `LIGHT_DUTY` (by design — HA IDBroker breaks credential vending), Runtime `7.3.2-1.cdh7.3.2.p100.81274879`, Ranger RAZ on; public gateway `srm-iceberg-aw-dl-gateway.srm-iceb.a465-9q4k.cloudera.site` |
| Impala Data Hub `srm-iceberg-impala` | `AVAILABLE`, "7.3.2 - Data Mart: Apache Impala, Hue", 4 nodes (coordinator + 2 executors `r5d.4xlarge`, master `r5.2xlarge`); Knox exposes HUE, CM-UI/API, KNOX, IMPALAD (HTTP + JDBC: `jdbc:impala://srm-iceberg-impala-gateway.srm-iceb.a465-9q4k.cloudera.site:443/;ssl=1;transportMode=http;httpPath=srm-iceberg-impala/cdp-proxy-api/impala;AuthMech=3;`), RANGER_RAZ_SERVER |
| CDW cluster `env-9jhw58` | Trino VW `srm-trino-vw` `Running`; DBCs `srm-iceberg-aw-dl-default` and `srm-iceberg-dbc` `Running`; its own EKS stack (`env-9jhw58-dwx-stack-*`) in the VPC |
| Iceberg REST Catalog (data share) | base `https://<dl-gateway>/srm-iceberg-aw-dl/cdp-datashare-access/iceberg-rest` (client appends `/v1/`); token `…/cdp-datashare-access/knoxtoken/api/v2/token` (OAuth2 `client_credentials`, `REQUEST_BODY`); share configured (`DATA_SHARE_ID`, `credentials.json`, `credentials-nifi.json` in the demo clone); tables `poc_uc2.airlines` (3 rows) and `poc_uc2.flights` (120k rows, partitioned by `flight_month`) |
| Security groups on 443 | `srm-iceberg-knox-sg` (`sg-0938cb277fe790c79`) and `srm-iceberg-default-sg`: one external `/32` (a stale VPN-pool exit IP, see below) + intra-VPC; `srm-iceberg-endpoint-sg`: intra-VPC only |
| AWS quota for AI Inference | On-Demand G/VT vCPU in `us-east-2`: 920, 0 in use — a `g5.12xlarge` node group is not quota-gated |
| Not deployed | CDF DataFlow (`cdp df list-services` → none on this env CRN; §3.2 needs it stood up first); Cloudera AI Inference (§3.4, no Workbench / AI Inference / GPU node group) |

Read-only commands behind the table: `cdp environments describe-environment`, `cdp datalake describe-datalake`, `cdp datahub describe-cluster`, `cdp dw list-clusters | list-vws | list-dbcs --cluster-id env-9jhw58`, `cdp df list-services`, `aws ec2 describe-security-group-rules`, `aws service-quotas get-service-quota --service-code ec2 --quota-code L-DB2E81BA`.

**REST Catalog read path — PROVEN from the box (§3.3 path 1, 2026-09-16).** With the corp VPN up (the box egresses on `165.1.200.192`; the tunnel carries the route to the semi-private environment), `test-rest-catalog.sh` ran the full read end to end: Knox `client_credentials` → JWT, `GET /v1/namespaces` → `default, information_schema, poc_uc2, sys`, `GET /v1/namespaces/poc_uc2/tables` → `airlines, flights`, and `loadTable` on both tables returning `metadata-location` plus IDBroker-vended S3 STS credentials (`s3.session-token`, region `us-east-2`) under the `X-Iceberg-Access-Delegation: vended-credentials` header. Capture: [`files/issue-342/rest-catalog-validation-2026-09-16T1344Z.txt`](files/issue-342/rest-catalog-validation-2026-09-16T1344Z.txt).

The one prerequisite was a Knox-SG entry for the box's public source IP. The SG (`srm-iceberg-knox-sg`, `sg-0938cb277fe790c79`) allowed only `179.64.39.45/32` on 443 — a **stale VPN-pool exit IP**, not a home IP; the corp VPN pool now exits on `165.1.200.x`. `165.1.200.192/32` was added to the SG on 443 for the validation window and **revoked afterward** (baseline restored). The corp VPN exit rotates within `165.1.200.x`, so a `/32` goes stale on reconnect — the durable fix is the corp range.

Still outstanding:

- **NiFi-hosted read (§3.3 paths 1–3 inside NiFi) is [#355](https://github.com/cldr-steven-matison/DesktopShare/issues/355).** It was blocked on 2026-09-16 by two stacked causes on the box, both fixed the same day under [#352](https://github.com/cldr-steven-matison/DesktopShare/issues/352): the corp full-tunnel VPN installs `default dev tun0` with no route for the k3s ClusterIP range `10.43.0.0/16`, so the NiFi pod could not reach the API server (leader election fails, Jetty 503, crash-loop) — `k3s-vpn-route.timer` (`files/issue-352/`) now keeps that route off the tunnel; and `/etc/rancher/k3s/config.yaml` pinned a `node-ip` the Wi-Fi lease had moved away from, so k3s itself was flapping — re-pinning it recovered the cluster (`nvidia-dgx-spark-runbook.md` §2). The curl proof above exercises the identical Knox-OAuth2 + `loadTable` interaction the `InvokeHTTP` path makes. The hand-off for the in-NiFi build is `files/issue-342/nifi-tier-b-plan-2026-09-16.md`.
- **Native `GetIceberg` / `QueryIceberg` (§3.3 paths 2–3)** additionally need the `nifi-iceberg-read-bundle` NAR built (source-only in `/home/tunas/NiFi2-Processor-Playground`) and deployed into the NiFi pod — also #355.
- **CDF DataFlow (§3.2) is not enabled** on this environment (`cdp df list-services` returns none for its CRN); the Inbound Connection path needs CDF stood up first.
- **Cloudera AI Inference (§3.4) is not deployed.** The AWS On-Demand G/VT vCPU quota in `us-east-2` is 920 (0 in use), so quota does not gate the node group when that deploy happens.

## 4. Cloudera AWC on AWS

The third platform path is **Cloudera Anywhere (AWC)** — the `goes01` environment on AWS EKS. Its full using-runbook is the peer doc [`nvidia-dgx-spark-cloudera-awc.md`](nvidia-dgx-spark-cloudera-awc.md) (#283); AWC setup, API and auth are in [`cloudera-anywhere-getting-started.md`](cloudera-anywhere-getting-started.md) (#284). This section is the pointer and the field-validation checklist, not a duplicate.

The shape: AWC is a containerized Cloudera platform, so the DGX Spark reaches its Cloudera AI, Lakehouse Engine (Trino) and Object Store (Ozone) experiences as an external client over the same OpenAI-compatible / REST surfaces as the two AWS shapes above. The Cloudera-AI-on-AWC angle is guide chapter ch22; this platform-integration angle is ch20.

**Field validation (state on 2026-09-16; detail in the peer doc):**

- Box→`goes01` reachability — the private network is VPN-only (`10.80.x`). **Done (#347, 2026-09-15):** the box is on the corp VPN with the goes01 CA imported; every goes01 subnet answers, the four API proofs pass from `spark-dd06` (`cloudera-anywhere-getting-started.md` §"From Linux").
- Trino (Lakehouse Engine), Iceberg via Trino, and Ozone S3 from the box with AWC auth — **proven (#343, 2026-09-16)**, peer doc §4.
- Kafka produce/consume from the box — **proven (#351, 2026-09-16)** over SASL_SSL/OAUTHBEARER with an `access-keys/token` client_credentials access-token (the broker's only enabled mechanism; the `hadoop-jwt` cookie fails for lacking `exp`), peer doc §4.
- The AWC Cloudera AI endpoint answers the same OpenAI-compatible request as the desk and CDP Public Cloud (the ch24 arc's third backend) — **blocked ([#351](https://github.com/cldr-steven-matison/DesktopShare/issues/351))**: the auth is solved (the same access-token, Bearer'd at the model's `…/openai/v1/…` route) but no model endpoint exists and the UI deploy fails on a goes01 AI Registry 503, peer doc §3.

Path 3 is field-run for everything except Cloudera AI Inference; the peer doc is the record.

## 5. NIM on the DGX Spark, for parity

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

Three GB10 specifics the playbook calls out, which the runbook has to inherit: `--shm-size=16GB` is the stated minimum recommendation; the unified-memory architecture "enables dynamic GPU/CPU memory sharing, though applications may need manual buffer cache flushing" — the flush is `sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'` per the [vLLM playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vllm/README.md); and `nvidia-smi` reports memory as "Not Supported" on this box because it shares the 128 GB pool (`CLAUDE-CHECKIN.md`), so any memory panel reads `/proc/meminfo`, not NVML. That same README contains **no Cloudera mentions at all**, and no repo anywhere in the research corpus combines a DGX Spark with any Cloudera component — the bridge in §6 is ours to build, first of its kind.

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

## 6. "Same code, N backends", formalized

Three artifacts, one config delta each. Nothing here is new code — all three already exist in the repo pointed at a local endpoint. The backends are the desk endpoint, Cloudera AI on CDP Public Cloud, and Cloudera AI on AWC; this is the ch24 arc.

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

Two operational notes carry over from that run and belong in ch24. The agent class must live in **its own importable module** shipped with `flink run -pyfs`, not defined in the submitted `__main__` script, or pemja fails on the TaskManager with `module '__main__' has no attribute ...`. And the model has to be able to hold a "reply with bare JSON" contract — the 3B that job started on managed 2–5 parseable replies out of 15, the AWQ 4-bit 7B did it reliably. On a 121 GB box that constraint mostly evaporates, which is itself the demo point.

## 7. Out-of-box integration catalogue

Every row is a pattern we already run on at least one side. "Box side" means what runs on `spark-dd06`; nothing here requires the DGX Spark to be a cluster member.

| # | Box side | AWS side | Data path | Demo value | Chapter |
|---|---|---|---|---|---|
| 1 | NiFi `InvokeHTTP` + Knox OAuth2 CS | Iceberg REST Catalog on the Data Lake | HTTPS out, Knox `client_credentials`, `vended-credentials` header | Read a governed Iceberg table from a desk-side flow with no Iceberg jars | ch19 |
| 2 | NiFi `QueryIceberg` + `RESTCatalogService` | Same catalog, `poc_uc2.flights` | Iceberg-native predicate and projection pushdown | Metadata-layer partition pruning — 11 of 12 manifests skipped | ch19 |
| 3 | NiFi posting out over HTTPS | CDF Inbound Connection → ReadyFlow → Kafka | mTLS to an auto-provisioned public hostname | Edge-to-cloud ingest with no broker exposed | ch18, ch19 |
| 4 | Kafka producer on the box | Data Hub Kafka, port 9093 | `SASL_SSL`/`PLAIN` + FreeIPA cert in the truststore | Direct-broker fallback when CDF is not in play | ch19 |
| 5 | NIM on `:8000` (Llama 3.1 8B) | AI Inference endpoint, same model class | One client, two base URLs | The SE money shot: identical output, three lines changed | ch05, ch21, ch24 |
| 6 | Flink Agents job on the local cluster | AI Inference as the chat-model resource | `OPENAI_COMPLETIONS_CONNECTION` swap | An agentic Flink job that runs desk-local or cloud-scale | ch11, ch24 |
| 7 | Whisper + embeddings tier on GB10 | Workbench project consuming the transcripts | Batch push into the Data Lake bucket | Private speech-to-text feeding a governed project | ch07, ch19 |
| 8 | Reverse SSH tunnel from the box | CE on AWS, NiFi topology | CE-side `InvokeHTTP` → tunnelled `:8000` | On-prem-shaped cluster calling a private desk model | ch18 |
| 9 | cuDF/cuML notebooks on GB10 | The same cuDF script in a Cloudera AI Workbench GPU session; Apache Spark + RAPIDS on a Cloudera cluster once a GPU node group exists | Same libraries, two scales | Explains the RAPIDS story without over-claiming GB10 (measured: 4.6× on both) | ch22 |
| 10 | MiNiFi Java agent, EFM class `NvidiaSpark-1` | Kafka topic on Data Hub or CE | Agent → local NiFi → cloud sink | Extends the Jetson → desk → cluster ladder to AWS | ch12, ch19 |

Rows 1, 2 and 6 are the cheapest — their local half is already built and validated. Row 5 is the one to record on video.

## 8. Stand-up runbook pointers and cost control

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

## 9. What NOT to do

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
- Chapters ch05, ch18, ch19, ch20, ch21, ch22 and ch24 under `files/nvidia-spark-guide/` are unblocked and take their content from §2–§7 here (ch20/ch22 also from the AWC peer doc); the tracker `Complete Developer Guide for Nvidia Spark with Cloudera.md` records the state change.
- The first executed integration turns every "# expected — verify on the box" block in §2.3, §5 and §6 into an as-built block the same day, and the measured numbers replace the estimates.
- If the NiFi legs change shape, the result is recorded back into `skills/nifi-and-ai/references/patterns.md` and `cloudera-iceberg-rest-catalog-cso-plan.md` rather than only here — and a skill change always gets its own commit.
- Anything customer-facing gets a clean blog per `agent/writing-style.md`, with the issue numbers stripped.

## Resources

- Companion docs: `nvidia-dgx-spark-plan.md` · `nvidia-dgx-spark-research.md` (§7 Cloudera AI, §8 Cloudera on AWS) · `nvidia-dgx-spark-landscape.md` · `nvidia-dgx-spark-runbook.md` · `nvidia-dgx-spark-k3s-cso.md` · `nvidia-dgx-spark-efm-agent.md` · `nvidia-dgx-spark-local-kb.md` · `nvidia-dgx-spark-cso-demos.md` · `Complete Developer Guide for Nvidia Spark with Cloudera.md` · `files/nvidia-spark-guide/README.md`
- Precedent in this repo: `cloudera-iceberg-rest-catalog-aws-plan.md` · `cloudera-iceberg-rest-catalog-cso-plan.md` · `blog/cloudera-ce-cm-evaluation.md` · `get-started-cloudera-ai-workbench.md` · `flink-agents-cso-plan.md` · `completed/cso-prod-1-cutover-plan.md` · `files/cso-prod-1/VALIDATION.md` · `files/cso-prod-1/flink-agents/vllm_review_agent.py` · `files/cso-prod-1/flink-agents/flinkdeployment.yaml` · `files/cso-prod-1/flows/prod/GetIcebergDemo.flow.json` · `files/cso-prod-1/flows/prod/QueryIcebergDemo.flow.json` · `skills/nifi-and-ai/references/site-to-site.md` · `skills/nifi-and-ai/references/patterns.md` · `CLAUDE-CHECKIN.md`
- Sub-repos cloned on this box: `/home/tunas/cloudera-ce-aws` · `/home/tunas/iceberg-mcp-server` · `/home/tunas/CAI_Workbench_MCP_Server` · `/home/tunas/NiFi2-Processor-Playground`
- Cloudera AI: [AI Inference docs index](https://docs.cloudera.com/machine-learning/cloud/ai-inference/index.html) · [authentication](https://docs.cloudera.com/machine-learning/cloud/ai-inference/topics/ml-caii-authentication.html) · [OpenAI-API calls](https://docs.cloudera.com/machine-learning/cloud/ai-inference/topics/ml-caii-make-inference-call-model-endpoint-with-openai-api.html) · [configuration and sizing](https://docs.cloudera.com/machine-learning/cloud/setup-cloudera-ai-inference/topics/ml-caii-caii-configuration-sizing.html) · [AI Registry standalone API](https://docs.cloudera.com/machine-learning/cloud/models/topics/ml-registry-standalone-api.html) · [Agent Studio overview](https://docs.cloudera.com/machine-learning/cloud/use-ai-studios/topics/ml-agent-studio-overview.html)
- Cloudera on AWS: [cdp-tf-quickstarts](https://raw.githubusercontent.com/cloudera-labs/cdp-tf-quickstarts/main/README.md) · [aws-ia/terraform-cloudera-cdp](https://github.com/aws-ia/terraform-cloudera-cdp) · [AWS VPC requirements](https://docs.cloudera.com/cdp-public-cloud/cloud/requirements-aws/topics/mc-aws-req-vpc.html) · [DataFlow Inbound Connections](https://docs.cloudera.com/dataflow/cloud/about-inbound-connections.html) · [Kafka clients outside the VPC](https://docs.cloudera.com/cdf-datahub/7.3.1/connecting-kafka/topics/kafka-dh-connect-clients-outside-vpc.html) · [Iceberg REST Catalog](https://docs.cloudera.com/runtime/7.3.1/overview/topics/cr-ds-cloudera-iceberg-rest-catalog.html) · [cloudera-ce-aws](https://cloudera-labs.github.io/cloudera-ce-aws/)
- NVIDIA: [NIM on DGX Spark playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nim-llm/README.md) · [vLLM playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vllm/README.md) · [Nemotron playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/nemotron/README.md) · [CUDA-X Data Science playbook](https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/cuda-x-data-science/README.md) · [Cloudera + NVIDIA](https://www.cloudera.com/partners/solutions/nvidia.html)
