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
| A · Cloudera AI workbench | `goes01-cai` at `https://goes01-cai-wb1.goes01-cai-cluster.demos.cloudera-labs.com`, workbench 2.0.59-b252, reachable from the box | **unknown**; the console API does not expose node instance types, and the workbench API needs a workbench API key | Steven logs into wb1 once (user does not exist yet: `user.notFound`), creates an API key; then runtimes and resource profiles are one `GET` each from the box |
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

## What is still unknown, and the one check that closes each

1. **Does `goes01-cai-cluster` have a GPU node?** Closes with a workbench API key: `GET
   $WB/api/v2/runtimes` for a GPU-edition runtime and the Site Administration → Resource Profiles
   page (or its API) for a profile with `gpu ≥ 1`. Six nodes and an installed AI Inference app are a
   hint, not proof.
2. **Does CDE 1.26.101 expose the cuDF plugin toggle?** Closes with a `GET` of the job-create
   schema on the VC jobs API (`…/dex/api/v1/jobs` with the cookie) and a look for a GPU / cuDF
   field. Even if present, `MaxVCAvailableGPU 0` means it cannot run here.
3. **Can a GPU node group be added to the CDE cluster?** A question for `jenright` (service creator).
