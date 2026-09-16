# goes01 inventory for Part 3 (issue #346), read from spark-dd06

Read-only survey of the `goes01` Cloudera Anywhere tenant, run 2026-09-16 00:20–00:45 UTC from
`spark-dd06` over the #347 path (corp VPN, goes01 CA, `hadoop-jwt` from `~/.awc.creds`,
`files/issue-347/awc-env.sh`). Every call below is a `GET`, or a `POST {}` to a `list*`/`describe*`
operation. Nothing on the tenant was created, changed, or started. The token is always passed by
variable (`$AWC_JWT`); no value appears in this file.

The question Part 3 needed answered: which Cloudera surface on goes01 can run the RAPIDS work
(cuDF/cuML on a GPU session, the Spark cuDF plugin on a GPU job) and what gates it.

## Verdict per surface

| Surface | On goes01 | GPU | Gate before a run |
|---|---|---|---|
| A · Cloudera AI workbench | `goes01-cai` at `https://goes01-cai-wb1.goes01-cai-cluster.demos.cloudera-labs.com`, workbench 2.0.59-b252, reachable from the box; Steven has a project `srm-test` there | **one NVIDIA L4, 0 used** (`nodes.nvidiaGPU.allocatable 1`; accelerator label `NVIDIA-L4`, `max_gpu_per_workload 1`, available) | No GPU-edition runtime in the catalog (6 runtimes: Hardened JupyterLab / PBJ Workbench on Python 3.11 and 3.14 at 2026.04.2-b16, Agent Studio, RAG Studio). Path: a session on Hardened Python 3.11 with `nvidia_gpu: 1`, then `pip install cudf-cu12 cuml-cu12`; or a site admin registers the NVIDIA GPU Edition runtime (`enable_register_runtimes_for_user false`) |
| B · CDE with the cuDF plugin | Data Engineering 1.26.101-b65, one service `goes01-svc`, two Spark **4.1.1** virtual clusters (`goes-vc`, `test-virtual-cluster`) | **none**: `MaxVCAvailableGPU 0` on the service, `gpuRequestActual 0` on both VCs | A GPU node group on the CDE cluster (tenant admin `jenright`); until then the Spark 4.1 prerequisite is met and the GPU one is not |
| C · CDS on CDP Base | not on goes01 (`steven-ce`, Runtime 7.3.2) | none | unchanged from the plan: the support-matrix question for 7.3.2 |

Side finding, for #343 and not acted on here: an **AI Inference** app `dm-inference` (1.14.0-b119,
owner `daming`, `dm-inference.goes01-cai-cluster.demos.cloudera-labs.com`) and a model registry
`dm-registry` (1.17.0-b34) are installed, and the NVIDIA model hub lists 24 enabled models
(Nemotron 3 Super 120B / Nano, Nemotron Parse, Cosmos Reason2 8B, Parakeet, Magpie TTS, ...).
`POST /api/v1alpha1/listEndpoints` on the inference host returns `401` with the `hadoop-jwt`; it
wants an API key too.

## How each surface answers (auth shapes that worked)

| Host | Auth that works | Auth that does not |
|---|---|---|
| CDE console `console-goes01-cde-u-a423c1.apps.goes01-cde-udf-cluster…/dex/api/v1/…` | `Cookie: hadoop-jwt=$AWC_JWT` → JSON | `Authorization: Bearer` → `302` to `knox-cdpsso/websso`. Unknown paths return the SPA shell with `200 text/html`; check the body |
| Cloudera AI control plane `goes01-cai-c-fe629e…/api/v1/ml/<op>` | `POST` with the cookie and `-d '{}'` → JSON (`listWorkspaces`, `listMlServingApps`, `listModelRegistries`, `listConfiguredModels`, `describeWorkspace`, `describeMlServingApp`, `getPlatformDetails`) | Any `GET` returns the SPA shell. `getResourcePools` → `500` nil pointer. `listAllSupportedInstances` needs `EnvironmentName`+`ProductType` |
| Workbench `goes01-cai-wb1…/api/v2/…` | needs a workbench API key (`Authorization: Bearer <key>`) | cookie → `401 no "authorization" header`; JWT as Bearer → `500 malformed apikey`. `/api/v1/users/me` with the cookie → `404 user.notFound` |
| AWC console `/api/v0/console/…` | Bearer JWT (`awc_api`) → `/experiences`, `/engines`, `/clusters` | `/infrastructure`, `/flavors` → `Failed to retrieve …`; `/clusters/{id}` → `Method not allowed` |

The `/api/v1/ml/*` operation names came from the CAI SPA bundle (`/ml/<build>/index-bundle.js`):
`describeEnvironment describeMlServingApp describeModelRegistry describeWorkspace getResourcePools
getUser listConfiguredModels listEntitlements listEnvironments listMlServingApps listModelRegistries
listSupportedCmlVersions listWorkspaces listWorkspaceAccess …` (the CDP control-plane ML API shape).

## Commands (box)

```bash
source files/issue-347/awc-env.sh          # exports AWC_JWT from ~/.awc.creds, prints one masked line
CDE=https://console-goes01-cde-u-a423c1.apps.goes01-cde-udf-cluster.demos.cloudera-labs.com
CAI=https://goes01-cai-c-fe629e.goes01-cai-cluster.demos.cloudera-labs.com
cde()    { curl -sS -k -H "Cookie: hadoop-jwt=$AWC_JWT" -H "Accept: application/json" "$CDE$1"; }
cai_ml() { curl -sS -X POST -H "Cookie: hadoop-jwt=$AWC_JWT" -H "Content-Type: application/json" -d "${2:-{\}}" "$CAI/api/v1/ml/$1"; }

cde /dex/api/v1/info | jq -r .version
cde /dex/api/v1/cluster | jq -r '.[] | [.name,.status,.clusterInfo.MaxVCAvailableGPU,.clusterInfo.MaxVCAvailableCPUMilli,.clusterInfo.ARM64Enabled] | @tsv'
cde /dex/api/v1/cluster/cluster-6gqzwzb4/instance | jq -r '.[] | [.id,.name,.status,.appInfo.sparkVersion,.appInfo.gpuRequestActual,.appInfo.dexApiUrl] | @tsv'
cde /dex/api/v1/info | jq -r '.compatibilityMatrix[].Components.Spark.Labels | to_entries[] | "\(.key)\t\(.value.full_version)\t\(.value.supported_architectures)"' | sort -u
cai_ml listWorkspaces     | jq -r '.workspaces[] | [.instanceName,.version,.instanceStatus,.instanceUrl] | @tsv'
cai_ml listMlServingApps  | jq -r '.apps[] | [.appName,.mlServingVersion,.status,.cluster.domainName] | @tsv'
cai_ml listModelRegistries | jq -r '.modelRegistry[] | [.workspaceName,.version,.status,.domain] | @tsv'
cai_ml listConfiguredModels | jq -r '.models[] | select(.enabled) | "\(.modelName)\t\(.source)\t\(.category)"'
awc_api /clusters | jq -r '.[] | [.name,.status,.kubernetesVersion,.nodes] | @tsv'
```

## Evidence

Headline re-check, 2026-09-16T00:43Z, from `spark-dd06` (output verbatim, token never printed):

```
$ cde /dex/api/v1/info | jq -r .version
1.26.101-b65
$ cde /dex/api/v1/cluster | jq -r '.[] | [.name,.status,.clusterInfo.MaxVCAvailableGPU,.clusterInfo.MaxVCAvailableCPUMilli,.clusterInfo.ARM64Enabled] | @tsv'
goes01-svc	ClusterCreationCompleted	0	47700	false
$ cde /dex/api/v1/cluster/cluster-6gqzwzb4/instance | jq -r '.[] | [.id,.name,.status,.appInfo.sparkVersion,.appInfo.gpuRequestActual] | @tsv'
dex-app-c8wxv76g	goes-vc	AppInstalled	4.1.1	0
dex-app-zt74d28w	test-virtual-cluster	AppInstalled	4.1.1	0
$ cai_ml listWorkspaces | jq -r '.workspaces[] | [.instanceName,.version,.instanceStatus,.instanceUrl] | @tsv'
goes01-cai	2.0.59-b252	installation:finished	https://goes01-cai-wb1.goes01-cai-cluster.demos.cloudera-labs.com
$ cai_ml listMlServingApps | jq -r '.apps[] | [.appName,.mlServingVersion,.status,.cluster.domainName] | @tsv'
dm-inference	1.14.0-b119	installation:finished	dm-inference.goes01-cai-cluster.demos.cloudera-labs.com
```

### CDE service `goes01-svc` (`cluster-6gqzwzb4`), the keys that matter

| Key | Value |
|---|---|
| `Version` / `CreatedVersion` | `1.26.101-b65` |
| `status` | `ClusterCreationCompleted` |
| `MaxVCAvailableGPU` | **`0`** |
| `MaxVCAvailableCPUMilli` / `MaxVCAvailableMemMB` | `47700` / `188703` |
| `ARM64Enabled` | `false` |
| `YunikornEnabled` / `RSSEnabled` | `true` / `false` |
| `CloudPlatform` / `ClusterType` | `CSK` / `managed` |
| `DockerRegistry` | `container.repository.cloudera.com` |
| `CreatorName` | `jenright` |
| `global.awcAuth.enabled` | `true` |

`grep -i 'gpu\|rapids\|cudf'` over the `/info` and `/cluster` payloads matches only `MaxVCAvailableGPU`.

### Virtual clusters

| VC | id | Spark | `gpuRequestActual` | cpu / mem actual | creator | jobs API |
|---|---|---|---|---|---|---|
| `goes-vc` | `dex-app-c8wxv76g` | 4.1.1 (`securityhardened`) | 0 | 13 / 44Gi | `jenright` | `https://c8wxv76g.cde-6gqzwzb4.goes01-cde-udf-cluster.demos.cloudera-labs.com/dex/api/v1` |
| `test-virtual-cluster` | `dex-app-zt74d28w` | 4.1.1 (`securityhardened`) | 0 | 13 / 44Gi | `dschoberle` | `https://zt74d28w.cde-6gqzwzb4.goes01-cde-udf-cluster.demos.cloudera-labs.com/dex/api/v1` |

Both carry `appInfoQuotaEnabled=true`; the History Server is `…/hs` on the same host.

### CDE Spark labels in the 1.26.101 compatibility matrix (deduplicated)

| Label | Spark | Arch | Runtime |
|---|---|---|---|
| `SPARK4_1_1_Standalone` | 4.1.1 | amd64, arm64 | Scala 2.13.16, Python 3.14 |
| `SPARK3_5_4_Standalone` | 3.5.4 | amd64, arm64 | Scala 2.12.18, Python 3.11 |
| `SPARK3_5_4_732` | 3.5.4 | amd64, arm64 | CDP 7.3.2.0, Scala 2.12.19, Python 3.11 |
| `SPARK3_5_4` / `SPARK3_5_4_719` | 3.5.4 | amd64, arm64 | CDP 7.3.1.x / 7.1.9 SP1 |
| `SPARK3_5` | 3.5.1 | amd64, arm64 | CDP 7.2.18.x |
| `SPARK3_4`, `SPARK3_3`, `SPARK3`, `SPARK248`, `SPARK2` | 3.4.1 … 2.4.5 | amd64 | CDP 7.1.x / 7.2.x |

### Cloudera AI control plane

| Object | Value |
|---|---|
| Workbench | `goes01-cai`, `2.0.59-b252`, `installation:finished`, `https://goes01-cai-wb1.goes01-cai-cluster.demos.cloudera-labs.com`, `isStandalone true`, NFS `10.80.143.250:/srv/nfs_share/wb1`, `instanceGroups []` |
| AI Inference | `dm-inference`, `1.14.0-b119`, owner `daming`, `dm-inference.goes01-cai-cluster.demos.cloudera-labs.com`, `instanceGroups []` |
| Model registry | `dm-registry`, `1.17.0-b34`, `INSTALLED`, `https://dm-registry.goes01-cai-cluster.demos.cloudera-labs.com` |
| Model hub | 24 enabled NVIDIA models (`listConfiguredModels`) |
| Platform | `controlPlaneNamespace goes01-cai-c-fe629e`, `engineInstanceName goes01-cai-cai` |
| K8s cluster (`awc_api /clusters`) | `goes01-cai-cluster`, `cluster-016`, `ready`, `v1.33.5`, `6` nodes, infra `AWS : goes01-aws-se-goes-taikun-1az`, created 2026-08-13 |

DNS from the box: `goes01-cai-wb1…` and `dm-inference…` both resolve to `10.80.186.131` (the same
ingress as the control plane); TLS answers on `:443`.

## Workbench wb1, read with a workbench API key (row 5, 00:50–00:58 UTC)

Steven logged into wb1 and created an API key (User Settings → API Keys); stored as `CAI_API_KEY`
in `~/.awc.creds` by `cai-key-set.sh`, read by the `cai_api` wrapper in `awc-env.sh`
(`Authorization: Bearer $CAI_API_KEY` against `/api/v2`). The v1 site endpoints answer to the
`hadoop-jwt` cookie now that the user exists. The key was pasted into a session transcript and is
to be deleted in the workbench after this pass.

```
$ curl … -H "Cookie: hadoop-jwt=$AWC_JWT" $CAI_WB/api/v1/site/stats | jq -r '.[] | "\(.name)\t\(.value)"'
Total Nodes	5
Total Memory	274.61 GiB        Used Memory	82.65 GiB
Total vCPUs	79.40             Used vCPUs	36.26
Total GPUs	1                 Used GPUs	0
NVIDIA-L4 GPUs Used	0 / 1
Total Projects	10              Total Running Sessions	5
$ cai_api /nodelabels | jq -c '.accelerator_node_label[]'
{"id":"1","label_key":"nvidia.com/gpu.product","label_value":"NVIDIA-L4","availability":true,"max_gpu_count":"1","current_gpu_count":"1","max_gpu_per_workload":"1","default_quota":"0","display_name":"NVIDIA-L4"}
$ cai_api '/runtimes?page_size=500' | jq -r '.runtimes[] | [.edition,.editor,.kernel,.full_version,.status] | @tsv'
Hardened	JupyterLab	Python 3.11	2026.04.2-b16	ENABLED
Hardened	JupyterLab	Python 3.14	2026.04.2-b16	ENABLED
Hardened	PBJ Workbench	Python 3.11	2026.04.2-b16	ENABLED
Hardened	PBJ Workbench	Python 3.14	2026.04.2-b16	ENABLED
Agent Studio	PBJ Workbench	Agent Studio	2.3.0.40	ENABLED
RAG Studio	PBJ Workbench	RAG Studio	2.1.0.30	ENABLED
$ cai_api '/runtimeaddons?page_size=100' | jq -r '.runtime_addons[] | [.identifier,.component,.status] | @tsv'
hadoop-cli-7.3.1.709-1 / hadoop-cli-7.3.2.0-957	HadoopCLI	AVAILABLE
ozone-731.1.0-b2 / ozone-732.1.0-b4	Ozone	AVAILABLE
sparkconnect354-731-26 / sparkconnect354-732-26 / sparkconnect411-26	Spark	AVAILABLE
```

Site config (`/api/v1/site/config`, cookie): `max_gpu_per_engine 0` (legacy engines; ML Runtimes are
governed by the accelerator label above), `default_accelerator_label_id 1`,
`enable_register_runtimes_for_user false` (registering a GPU-edition runtime is a site-admin action),
`enable_runtime_addons true`. Job/session create schema (`/api/v2/swagger.json`, 119 paths):
`CreateJobRequest` carries `nvidia_gpu`, `accelerator_label_id`, `runtime_identifier`,
`runtime_addon_identifiers`, `cpu`, `memory`. The `/cpuprofiles` endpoint returns "Operation is not
supported". Projects: 10, including Steven's `srm-test` (private).

Reading for Surface A: the GPU exists and is idle, the session API can request it, and the missing
piece is only the runtime image. A Hardened Python 3.11 session with `nvidia_gpu 1` plus a
`pip install cudf-cu12 cuml-cu12` is the no-admin path (the node's driver version decides whether
the `cu12` wheels load); the clean path is a site admin registering the NVIDIA GPU Edition 2026.08
runtime. The `sparkconnect411-26` addon is a second story for the call: a CAI session speaking Spark
Connect to CDE's Spark 4.1.1.

## What is still unknown, and the one check that closes each

1. **Does the L4 node's driver satisfy `cudf-cu12`?** Closes inside the first GPU session:
   `nvidia-smi` for the driver version, then `python -c "import cudf"` after the pip install. A
   session is a tenant write; it gets its own go.
2. **Does CDE 1.26.101 expose the cuDF plugin toggle?** Closes with a `GET` of the job-create
   schema on the VC jobs API (`…/dex/api/v1/jobs` with the cookie) and a look for a GPU / cuDF
   field. Even if present, `MaxVCAvailableGPU 0` means it cannot run here.
3. **Can a GPU node group be added to the CDE cluster?** A question for `jenright` (service creator).
