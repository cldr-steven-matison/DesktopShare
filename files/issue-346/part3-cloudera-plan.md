# Part 3 · RAPIDS on Cloudera — the plan for the call (issue #346)

Written 2026-09-15 evening for a customer call the next day; **revised 2026-09-16 from the box**
after `spark-dd06` gained goes01 access (#347) and a read-only inventory of the tenant was taken
(`goes01-inventory-2026-09-16.md`, same directory). Part 3 of #346 is "Test with Cloudera": the
same RAPIDS work run on Cloudera surfaces, not on the DGX Spark. Owners: **the box** for every
goes01 step that has an API (it reaches every goes01 subnet, the Mac cannot reach `csm`); the Mac
only for internal docs and corp GitHub, which the box cannot reach; Steven for the two browser
steps named in §6.

## 1. What is in hand (facts)

**On the box, done, committed** (`nvidia-dgx-spark-rapids-runbook.md`, `files/issue-346/results.md`):

- cuDF/cuML in the `rapidsai/notebooks:26.06-cuda13` container on GB10 (`sm_121`): cuDF 4.6× overall,
  131× on strings at 10M rows, zero code change via `cudf.pandas`; cuML RandomForest 1.51× with
  accuracy parity.
- The Spark RAPIDS plugin runs on aarch64 from NVIDIA's `rapids-4-spark_2.13-26.08.1-cuda13-arm64.jar`
  (Spark 4.0.4, Scala 2.13, Java 21). Final plan carries 9 `Gpu*` operators
  (`GpuRange`, `GpuProject`, `GpuFilter`, `GpuFileGpuScan`, `GpuBroadcastExchange`,
  `GpuBroadcastHashJoin`, `GpuBuildRight`, `GpuCoalesceBatches`, `GpuColumnarToRow`). No speedup
  at 10M rows with an 816 MiB pool next to a live 35B model; the plugin is functional, the number
  needs a dedicated GPU and a bigger job.
- The job to port: `files/issue-346/scripts/spark_rapids_job.py` + the confs in
  `run-spark-rapids.sh`. Range → groupBy/agg → Parquet write/read → broadcast join → count, `ROWS`
  as an env var. Same script on every backend.

**Environments we run** (from `nvidia-dgx-spark-cloudera-aws.md`, `cloudera-ce-aws-runbook.md`,
`cloudera-anywhere-getting-started.md`, and the 2026-09-16 inventory):

| Env | What | GPU today | Reach |
|---|---|---|---|
| `steven-ce` | CDP Base CE on AWS, CM 7.13.2 / Runtime 7.3.2, `cloudera-ce-aws` v1.0.0 (2026-09-14 build) | none — topology is `t3a`/`r5a` | Mac |
| `srm-iceberg` | CDP Public Cloud on AWS, Runtime 7.3.2, `LIGHT_DUTY` Data Lake | none; **AWS G-instance quota** is a known gate | Mac |
| `goes01` · CDE | Data Engineering 1.26.101-b65, service `goes01-svc`, VCs `goes-vc` + `test-virtual-cluster`, both **Spark 4.1.1** | **none, proven**: `MaxVCAvailableGPU 0`, `gpuRequestActual 0` on both VCs | box (cookie auth) and Mac |
| `goes01` · Cloudera AI | workbench `goes01-cai` 2.0.59-b252 at `goes01-cai-wb1…`; AI Inference `dm-inference` 1.14.0; model registry `dm-registry`; NVIDIA model hub with 24 models enabled | **unknown**: node types not exposed by the console API; the workbench API needs a workbench API key and Steven's user does not exist on wb1 yet | box and Mac, after one browser login |

**Docs state, researched 2026-09-15** (public sources; internal docs can move any of these), with
the **live tenant** answer beside each:

| Surface | Verdict from public docs | Live on goes01 (2026-09-16) | Source |
|---|---|---|---|
| Spark on CDP Base, CDS-for-GPU | Every CDS-for-GPU parcel found is pinned to one Runtime: CDS 3.2.3 → 7.1.7, CDS 3.3 → 7.1.8 (bundles RAPIDS 22.06). CDS 3.5, the default on 7.3.x, states "NVIDIA RAPIDS and Spark Connect are not supported". **No GPU-Spark path found for 7.3.2.** The `latest/cds-for-gpu` tree 404'd. | not a goes01 surface | [7.1.8 CDS 3 requirements](https://docs.cloudera.com/cdp-private-cloud-base/7.1.8/cds-3/topics/spark-3-requirements.html) · [CDS 3.5 post](https://community.cloudera.com/t5/What-s-New-Cloudera/Upgrade-Your-Spark-Experience-Introducing-CDS-3-5-for/ba-p/412402) |
| CDE native cuDF plugin, Spark 4.1 | Announced 2026-08-20 (Cloudera + NVIDIA, EVOLVE Singapore): zero-code, "up to 4×", part of Cloudera Anywhere Cloud. **No how-to, config key, or GA scope published.** The older CDE 1.5.4 GPU feature is Technical Preview, Spark 3, "Enable GPU Accelerations" checkbox + VC GPU quota. | CDE 1.26.101 carries `SPARK4_1_1_Standalone` (amd64+arm64) and both VCs run 4.1.1, so the Spark side is in place. Zero GPU on the service. No `gpu`/`rapids`/`cudf` key in the service or VC config; the job-create schema is unread. | [press release](https://www.cloudera.com/about/news-and-blogs/press-releases/2026-08-20-cloudera-teams-with-nvidia-to-lower-cloud-compute-spend-and-accelerate-apache-spark-pipelines.html) · [CDE 1.5.4 GPU jobs](https://docs.cloudera.com/data-engineering/1.5.4/gpu-jobs-sessions/topics/cde-accelerating-jobs-sessions-gpu.html) |
| Cloudera AI runtime | Current family is **NVIDIA GPU Edition Runtimes 2026.08, CUDA 12.5, Python 3.10–3.13**. Whether cuDF/cuML are preinstalled is not stated. The "RAPIDS Edition" pages are 2021-era (RAPIDS 0.18 / CUDA 11.0). Tutorial: NYC taxi, `import cudf as pd`, "up to 60×". | One workbench, reachable. Runtime catalog and resource profiles sit behind the workbench API key (`/api/v2/runtimes` → `401` with the cookie). | [NVIDIA GPU Edition runtimes](https://docs.cloudera.com/machine-learning/cloud/runtimes/topics/ml-runtimes-nvidia-gpu.html) · [runtimes what's new](https://docs.cloudera.com/machine-learning/cloud/runtimes-release-notes/topics/ml-runtimes-whats-new.html) · [NYC taxi tutorial](https://www.cloudera.com/services-and-support/tutorials/using-nvidia-rapids-to-accelerate-ai-training-on-cml.html) |

## 2. Design · the arc for the call

One story, three backends, same code:

1. **Desk.** cuDF/cuML numbers and the Spark plugin running on the DGX Spark. Shown, measured.
2. **Cloudera AI.** The cuDF/cuML half on a GPU session: same `cudf_bench.py` pattern (or the NYC
   taxi notebook), same GPU-vs-CPU table, on Cloudera.
3. **Cloudera Data Engineering.** The Spark half on a dedicated GPU: `spark_rapids_job.py` with
   `ROWS` in the hundreds of millions, `Gpu*` in the History Server SQL tab, a wall-clock delta.

The innovation angle is the desk-side loop. The DGX Spark is the place a data engineer develops and
checks a RAPIDS Spark job (arm64 plugin, `explain=ALL`, final plan) before it goes to the cluster.
Nothing about the job changes on promotion; only the confs that describe the GPU do
(`minAllocFraction` back to default, `spark.executor.resource.gpu.*` on a cluster manager).

Surface order for the call, by readiness after the inventory: **Cloudera AI → CDE → CDS on Base.**
A is one login away from a yes/no; B is a talking point until the CDE cluster has a GPU node; C is
a support question.

## 3. Surface A · Cloudera AI (fastest visible demo)

**Prereqs**
- A Cloudera AI workbench with a GPU node group and a GPU resource profile. `goes01` has the
  workbench (`goes01-cai`, wb1); whether it has a GPU node group is the first check. On Public Cloud
  (`srm-iceberg`) a workbench with GPU needs the G-instance quota first.
- The NVIDIA GPU Edition runtime (2026.08, CUDA 12.5) registered in the Runtime Catalog.
- **A workbench API key.** The wb1 API v2 refuses the `hadoop-jwt` (`401` as a cookie, `malformed
  apikey` as Bearer) and `/api/v1/users/me` says `user.notFound`, so the user has to exist first.

**Enable**
1. Steven, browser (Firefox on the box or the Mac): open
   `https://goes01-cai-wb1.goes01-cai-cluster.demos.cloudera-labs.com`, log in through Knox SSO
   (creates the user), then User Settings → API Keys → create. Store it with the #347 helper as a
   `CAI_API_KEY=` line in `~/.awc.creds` (never on a command line, never in a thread).
2. Box: `GET $WB/api/v2/runtimes` for a GPU-edition runtime; the resource-profile list for a
   profile with `gpu ≥ 1`. (A `cai_api` wrapper for `awc-env.sh` lands with that pass.)
3. If both exist: a JupyterLab session on the GPU runtime with the GPU profile, then in a terminal
   `nvidia-smi` and `python -c "import cudf"`; if not preinstalled, `pip install cudf-cu12 cuml-cu12`
   (CUDA 12.5 → `cu12` wheels).
4. Run `cudf_bench.py` twice (stock, then `python -m cudf.pandas`), or the NYC taxi notebook.
   Steps 3–4 are tenant writes (a project, a session) and get their own go from Steven.

**Verify.** `nvidia-smi` in the session shows the Python process; the GPU column of the timing table
beats CPU on the string/join stages the way it did on the box.

**Gating.** wb1 login + API key (Steven). GPU node group present (unknown until step 2). Runtime
registered.

**Owner / time.** Box, after the login. 30–60 min if the GPU profile exists; otherwise it is a
provisioning task for the tenant admin.

## 4. Surface B · CDE with the cuDF plugin (the headline, least documented)

**Facts from the tenant.** CDE 1.26.101-b65 on goes01 lists `SPARK4_1_1_Standalone` in its
compatibility matrix and both VCs (`goes-vc`, `test-virtual-cluster`) already run Spark 4.1.1, so the
version prerequisite for the Aug-2026 cuDF plugin is met. The service reports `MaxVCAvailableGPU 0`
and both VCs `gpuRequestActual 0`: **there is no GPU to run it on**. Nothing named `gpu`, `rapids` or
`cudf` appears in the service or VC configuration.

**Prereqs**
- A CDE build that carries the native cuDF plugin. Public docs do not say which; the job-create
  schema on the VC jobs API is the cheap check for a GPU / cuDF field (box, read-only).
- A GPU node group on the CDE cluster and a VC with GPU quota. Neither exists; the ask goes to the
  service creator `jenright`.

**Enable (when both gates open)**
1. Box: `GET https://c8wxv76g.cde-6gqzwzb4.goes01-cde-udf-cluster.demos.cloudera-labs.com/dex/api/v1/jobs`
   with the cookie; read the job schema for a GPU or cuDF acceleration field.
2. Mac: pull the internal how-to for the cuDF plugin: the enable flag, any remaining `spark.rapids.*`
   keys, supported Spark version, GPU instance guidance.
3. Tenant admin: GPU node group on the CDE cluster; VC guaranteed / max GPU set (else jobs sit
   `Pending`).
4. Job = `spark_rapids_job.py`, `ROWS=300000000` (or a Parquet dataset already in the Object Store),
   the acceleration toggle on. Run it twice, toggle on and off.

**Verify.** History Server (`…/hs` on the VC host) → SQL tab → `Gpu*` nodes in the plan; driver log
`explain=ALL` if the key is exposed; wall-clock on vs off.

**Fallback if the new plugin is not on the tenant.** The documented CDE GPU path (Technical Preview,
Spark 3): VC with GPU quota, job config "Enable GPU Accelerations", node selector to the GPU nodes.
Same job, same verify. Same GPU gate.

**Gating.** GPU node group on the CDE cluster (none today). cuDF toggle in this build (unread).

**Owner / time.** Box for the schema check (minutes). The GPU node group is not ours to add; on the
call, B is "the Spark 4.1 side is deployed, the GPU node is the next step", with no date.

## 5. Surface C · Spark on CDP Base with a CDS GPU parcel (needs a support answer first)

**Facts.** `steven-ce` is Runtime 7.3.2 / CM 7.13.2 with no GPU node. Public docs pin every
CDS-for-GPU parcel to a 7.1.x Runtime and say CDS 3.5 has no RAPIDS.

**Step 0, before anything is built.** Internal support matrix: is there any RAPIDS-on-Spark path
for Runtime 7.3.2 (a CDS-for-GPU parcel, a Runtime feature, a private build)? If the answer is no,
this surface is a roadmap line on the call and the effort goes to B.

**Enable (only if step 0 says yes)**
1. Add a GPU worker to `steven-ce`: `g5.xlarge` (A10G) or `g4dn.xlarge` (T4), NVIDIA driver +
   CUDA on the host, CM agent, host added to the cluster.
2. CM: Hosts → enable cgroup-based resource management. YARN → "Use CGroups", "Always use Linux
   Container Executor", a NodeManager role group for the GPU host with "Enable GPU Usage",
   allowed devices `auto`, discovery path `/usr/bin`. That sets `yarn.nodemanager.resource-plugins=yarn.io/gpu`,
   `yarn.resource-types=yarn.io/gpu`, cgroups mount, and `DominantResourceCalculator`. Restart stale
   services, redeploy client config.
3. Activate the CDS-for-GPU parcel; the RAPIDS jar is in the parcel.
4. `spark-submit` confs: `spark.plugins=com.nvidia.spark.SQLPlugin`, `spark.rapids.sql.enabled=true`,
   `spark.executor.resource.gpu.amount=1`, `spark.task.resource.gpu.amount=0.125`,
   `spark.executor.resource.gpu.discoveryScript=/usr/lib/spark/scripts/gpu/getGpusResources.sh`,
   `spark.rapids.sql.explain=ALL`. Shuffle Manager + UCX stay off (no RDMA on plain EC2).
5. Job = `spark_rapids_job.py`, `ROWS` large, on and off.

**Verify.** YARN RM shows `yarn.io/gpu` allocated to the app; Spark UI SQL tab `Gpu*`; driver log
`explain=ALL`.

**Gating.** Step 0. Then a GPU EC2 host (quota, cost), a CM restart window on `steven-ce`.

**Owner / time.** Mac. Multi-hour; not a same-day item unless the GPU host is pre-staged.

## 6. Ordered checklist (state as of 2026-09-16)

| # | Where | Step | Done when | State |
|---|---|---|---|---|
| 1 | box | Evidence, runbook, this plan committed and pushed | commit on `main`, #346 comment | done (`a0ffa19`) |
| 2 | box | `goes01` → Cloudera AI inventory: workbench, inference app, registry, model hub | answers in the thread | done, `goes01-inventory-2026-09-16.md` |
| 3 | box | `goes01` → Data Engineering inventory: service version, VCs, Spark version, GPU quota | same | done, same file: 1.26.101, Spark 4.1.1, GPU 0 |
| 4 | **Steven** | Log into `goes01-cai-wb1` once; User Settings → API Keys → create; store as `CAI_API_KEY` in `~/.awc.creds` | key on the box, masked line printed by `awc-env.sh` | open |
| 5 | box | wb1 API: GPU-edition runtime in the catalog; a resource profile with `gpu ≥ 1` | `CAI runtime: <yes/no, version>` · `CAI GPU profile: <yes/no>` in the thread | blocked on 4 |
| 6 | box | `goes-vc` jobs API: job-create schema for a GPU / cuDF field | `CDE cuDF toggle: <yes/no>` in the thread | open |
| 7 | **Steven** | Ask `jenright` whether a GPU node group can be added to the CDE cluster | yes/no + date, or "not on this tenant" | open |
| 8 | Mac | Internal docs: CDE cuDF plugin how-to; RAPIDS-on-Spark support for Runtime 7.3.2; GPU runtime contents | links or "none" in the thread | open |
| 9 | Mac | AWS G-instance quota for `srm-iceberg`, only if the Public Cloud Cloudera AI path is wanted | quota state known | open |
| 10 | box | Run Surface A (own go from Steven: a project and a session are tenant writes); Surface B only after 6 and 7 | timing table + `Gpu*` screenshot in the thread | blocked on 5 |
| 11 | box | Optional: the desk speedup number with vLLM paused (default `minAllocFraction`, `ROWS=300000000`) | on/off table | open, needs the live-service confirm |
| 12 | both | Pick the demo order from what passed: A → B → (C as roadmap) | one line in the thread | after 10 |

## 6a. The goes01 checks, as box commands

Auth per `cloudera-anywhere-getting-started.md` and #347: `source files/issue-347/awc-env.sh`
(reads `~/.awc.creds`, prints one masked line). The token stays in the file; never on a command
line, never in a thread. The full command set that produced the inventory is in
`goes01-inventory-2026-09-16.md` §"Commands"; the shape:

```bash
source files/issue-347/awc-env.sh
CDE=https://console-goes01-cde-u-a423c1.apps.goes01-cde-udf-cluster.demos.cloudera-labs.com
CAI=https://goes01-cai-c-fe629e.goes01-cai-cluster.demos.cloudera-labs.com
WB=https://goes01-cai-wb1.goes01-cai-cluster.demos.cloudera-labs.com
cde()    { curl -sS -k -H "Cookie: hadoop-jwt=$AWC_JWT" -H "Accept: application/json" "$CDE$1"; }
cai_ml() { curl -sS -X POST -H "Cookie: hadoop-jwt=$AWC_JWT" -H "Content-Type: application/json" -d '{}' "$CAI/api/v1/ml/$1"; }

# rows 2–3 (done): what the tenant has
cde /dex/api/v1/info | jq -r .version
cde /dex/api/v1/cluster | jq -r '.[] | [.name,.clusterInfo.MaxVCAvailableGPU] | @tsv'
cde /dex/api/v1/cluster/cluster-6gqzwzb4/instance | jq -r '.[] | [.name,.appInfo.sparkVersion,.appInfo.gpuRequestActual,.appInfo.dexApiUrl] | @tsv'
cai_ml listWorkspaces | jq -r '.workspaces[] | [.instanceName,.version,.instanceUrl] | @tsv'

# row 5 (after the API key): the Surface A gates
curl -sS -H "Authorization: Bearer $CAI_API_KEY" "$WB/api/v2/runtimes" | jq '.runtimes[] | select(.edition|test("GPU|RAPIDS";"i")) | {edition,shortVersion,fullVersion,status}'

# row 6: the Surface B toggle
curl -sS -k -H "Cookie: hadoop-jwt=$AWC_JWT" -H "Accept: application/json" \
  https://c8wxv76g.cde-6gqzwzb4.goes01-cde-udf-cluster.demos.cloudera-labs.com/dex/api/v1/jobs | jq 'keys'
```

Two shapes to remember: the CDE console and the workbench answer `302 → knox-cdpsso/websso` to a
Bearer JWT and JSON to the same JWT as a `Cookie`; the CAI control plane is `POST`-only
(`/api/v1/ml/list*`), and a `GET` there returns the SPA shell with `200`. Check the body, not the code.

Write each answer as one line in the #346 thread: `CAI runtime: <yes/no, version>`, `CAI GPU profile: <yes/no>`,
`cudf in session: <version/ImportError>`, `CDE version: 1.26.101` (done), `CDE GPU quota: 0` (done),
`CDE cuDF toggle: <yes/no>`.

## 7. What to say on the call

- cuDF/cuML: measured on GB10, no code change, the table.
- Spark plugin: runs on Grace Blackwell arm64 from NVIDIA's published jar, whole job on the GPU,
  desk-side dev loop. Speedup is a cluster number; the "up to 4×" CDE claim is Cloudera's, not ours.
- Cloudera surfaces: the tenant already runs Spark 4.1.1 on CDE (the plugin's prerequisite) and
  has a Cloudera AI workbench with an NVIDIA model hub; which ones ran (A, B) and which one is a
  support question (C on 7.3.2). No dates for anything that did not run, and no GPU claim for
  goes01 until row 5 answers.

## 8. Open questions, and who closes each

1. Does `goes01` have a GPU node group? **CDE: no** (`MaxVCAvailableGPU 0`, proven 2026-09-16).
   **Cloudera AI: unknown**; closes with the wb1 API key (row 5).
2. Which CDE build carries the native cuDF plugin, and is `goes01` on it? goes01 is **1.26.101-b65
   with Spark 4.1.1 VCs**; whether the toggle is in this build closes with the job-schema read (row 6).
3. Is there any supported RAPIDS-on-Spark path for Runtime 7.3.2? Unchanged; Mac, internal docs (row 8).
4. Does the NVIDIA GPU Edition 2026.08 runtime ship cuDF/cuML, or is it `pip install`? Unchanged;
   answered inside the first GPU session (Surface A step 3).

## Sources

- `goes01-inventory-2026-09-16.md` (this directory): the tenant facts above, with the commands and raw excerpts
- https://repo1.maven.org/maven2/com/nvidia/rapids-4-spark_2.13/26.08.1/ (arm64 classifier jars)
- https://github.com/NVIDIA/cudf-spark/issues/6881 · https://nvidia.github.io/cudf-spark/docs/download.html
- https://docs.nvidia.com/spark-rapids/user-guide/26.06/getting-started/yarn-gpu.html
- https://docs.cloudera.com/cdp-private-cloud-base/7.1.8/cds-3/topics/spark-3-requirements.html
- https://docs.cloudera.com/cdp-private-cloud-base/7.1.8/cds-3/topics/spark-activate-cds-for-gpu.html
- https://docs.cloudera.com/runtime/7.3.1/yarn-allocate-resources/topics/yarn-configuring-gpu-scheduling-and-isolation.html
- https://community.cloudera.com/t5/What-s-New-Cloudera/Upgrade-Your-Spark-Experience-Introducing-CDS-3-5-for/ba-p/412402
- https://www.cloudera.com/about/news-and-blogs/press-releases/2026-08-20-cloudera-teams-with-nvidia-to-lower-cloud-compute-spend-and-accelerate-apache-spark-pipelines.html
- https://docs.cloudera.com/data-engineering/1.5.4/gpu-jobs-sessions/topics/cde-accelerating-jobs-sessions-gpu.html
- https://docs.cloudera.com/machine-learning/cloud/runtimes/topics/ml-runtimes-nvidia-gpu.html
- https://docs.cloudera.com/machine-learning/cloud/runtimes-release-notes/topics/ml-runtimes-whats-new.html
- https://docs.cloudera.com/machine-learning/cloud/engines/topics/ml-managing-resource-profiles.html
- https://www.cloudera.com/services-and-support/tutorials/using-nvidia-rapids-to-accelerate-ai-training-on-cml.html
