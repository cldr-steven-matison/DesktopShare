# Part 3 · RAPIDS on Cloudera — the plan for the call (issue #346)

Written 2026-09-15 evening for a customer call the next day. Part 3 of #346 is "Test with
Cloudera": the same RAPIDS work run on Cloudera surfaces, not on the DGX Spark. Owners: the Mac
(`device:FTF3XR2065`) for every Cloudera-side step (it reaches `goes01` and the internal systems and
docs); `spark-dd06` for the local half and the comparison numbers.

## 1. What is in hand tonight (facts)

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
`cloudera-anywhere-getting-started.md`):

| Env | What | GPU today | Reach |
|---|---|---|---|
| `steven-ce` | CDP Base CE on AWS, CM 7.13.2 / Runtime 7.3.2, `cloudera-ce-aws` v1.0.0 (2026-09-14 build) | none — topology is `t3a`/`r5a` | Mac |
| `srm-iceberg` | CDP Public Cloud on AWS, Runtime 7.3.2, `LIGHT_DUTY` Data Lake | none; **AWS G-instance quota** is a known gate | Mac |
| `goes01` | Cloudera Anywhere (AWC) on EKS; Cloudera AI, Data Engineering (×4), Lakehouse Engine, Object Store all `deployed` | **unknown** — GPU node group not yet checked | Mac **and the box** since #347 (2026-09-15 evening): corp VPN via `gpclient`, goes01 CA imported, `hadoop-jwt` in `~/.awc.creds`, `files/issue-347/awc-env.sh` — the four proofs pass from `spark-dd06` and every goes01 subnet is reachable (incl. `csm`, which the Mac can't reach). The goes01 steps below can run from either. |

**Docs state, researched 2026-09-15** (public sources; internal docs can move any of these):

| Surface | Verdict from public docs | Source |
|---|---|---|
| Spark on CDP Base, CDS-for-GPU | Every CDS-for-GPU parcel found is pinned to one Runtime: CDS 3.2.3 → 7.1.7, CDS 3.3 → 7.1.8 (bundles RAPIDS 22.06). CDS 3.5, the default on 7.3.x, states "NVIDIA RAPIDS and Spark Connect are not supported". **No GPU-Spark path found for 7.3.2.** The `latest/cds-for-gpu` tree 404'd. | [7.1.8 CDS 3 requirements](https://docs.cloudera.com/cdp-private-cloud-base/7.1.8/cds-3/topics/spark-3-requirements.html) · [CDS 3.5 post](https://community.cloudera.com/t5/What-s-New-Cloudera/Upgrade-Your-Spark-Experience-Introducing-CDS-3-5-for/ba-p/412402) |
| CDE native cuDF plugin, Spark 4.1 | Announced 2026-08-20 (Cloudera + NVIDIA, EVOLVE Singapore): zero-code, "up to 4×", part of Cloudera Anywhere Cloud. **No how-to, config key, or GA scope published.** The older CDE 1.5.4 GPU feature is Technical Preview, Spark 3, "Enable GPU Accelerations" checkbox + VC GPU quota. | [press release](https://www.cloudera.com/about/news-and-blogs/press-releases/2026-08-20-cloudera-teams-with-nvidia-to-lower-cloud-compute-spend-and-accelerate-apache-spark-pipelines.html) · [CDE 1.5.4 GPU jobs](https://docs.cloudera.com/data-engineering/1.5.4/gpu-jobs-sessions/topics/cde-accelerating-jobs-sessions-gpu.html) |
| Cloudera AI runtime | Current family is **NVIDIA GPU Edition Runtimes 2026.08, CUDA 12.5, Python 3.10–3.13**. Whether cuDF/cuML are preinstalled is not stated. The "RAPIDS Edition" pages are 2021-era (RAPIDS 0.18 / CUDA 11.0). Tutorial: NYC taxi, `import cudf as pd`, "up to 60×". | [NVIDIA GPU Edition runtimes](https://docs.cloudera.com/machine-learning/cloud/runtimes/topics/ml-runtimes-nvidia-gpu.html) · [runtimes what's new](https://docs.cloudera.com/machine-learning/cloud/runtimes-release-notes/topics/ml-runtimes-whats-new.html) · [NYC taxi tutorial](https://www.cloudera.com/services-and-support/tutorials/using-nvidia-rapids-to-accelerate-ai-training-on-cml.html) |

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

Surface order for the call, by readiness: **Cloudera AI → CDE → CDS on Base.**

## 3. Surface A · Cloudera AI (fastest visible demo)

**Prereqs**
- A Cloudera AI workspace with a GPU node group and a GPU resource profile. `goes01` has Cloudera AI
  deployed; whether it has a GPU node group is the first check. On Public Cloud (`srm-iceberg`) a
  workspace with GPU needs the G-instance quota first.
- The NVIDIA GPU Edition runtime (2026.08, CUDA 12.5) registered in the Runtime Catalog.

**Enable**
1. Start a JupyterLab session: runtime = NVIDIA GPU Edition 2026.08, resource profile with 1 GPU.
2. In the session: `nvidia-smi`; then `python -c "import cudf"`. If it is not preinstalled:
   `pip install cudf-cu12 cuml-cu12` (CUDA 12.5 → `cu12` wheels).
3. Run `cudf_bench.py` twice (stock, then `python -m cudf.pandas`), or the NYC taxi notebook.

**Verify.** `nvidia-smi` in the session shows the Python process; the GPU column of the timing table
beats CPU on the string/join stages the way it did on the box.

**Gating.** GPU node group present (goes01: check; srm-iceberg: quota). Runtime registered.

**Owner / time.** Mac. 30–60 min if the GPU profile exists; otherwise it is a provisioning task.

## 4. Surface B · CDE with the cuDF plugin (the headline, least documented)

**Prereqs**
- A CDE service on a build that carries the Aug-2026 native cuDF plugin (Spark 4.1). Public docs do
  not say which build. This is the internal-doc pull.
- A virtual cluster with a GPU quota, backed by a GPU node group on the EKS cluster.

**Enable (when the feature is present)**
1. Mac: open `goes01` → Data Engineering → the service's version, and the virtual-cluster / job
   config for a GPU or cuDF acceleration toggle.
2. Pull the internal how-to for the cuDF plugin: the enable flag, any remaining `spark.rapids.*` keys,
   supported Spark version, GPU instance guidance.
3. Create or pick a VC with GPU capacity (guaranteed / max GPU cores set, else jobs sit `Pending`).
4. Job = `spark_rapids_job.py`, `ROWS=300000000` (or a Parquet dataset already in the Object Store),
   the acceleration toggle on. Run it twice, toggle on and off.

**Verify.** History Server → SQL tab → `Gpu*` nodes in the plan; driver log `explain=ALL` if the key
is exposed; wall-clock on vs off.

**Fallback if the new plugin is not on the tenant.** The documented CDE GPU path (Technical Preview,
Spark 3): VC with GPU quota, job config "Enable GPU Accelerations", node selector to the GPU nodes.
Same job, same verify.

**Gating.** Tenant CDE build has the feature (unknown). GPU node group on `goes01` EKS (unknown). Both
are checks, not builds.

**Owner / time.** Mac. 1–2 h if both gates are already open. If the feature is not on the tenant,
say so on the call and show Surface A + the desk loop; do not promise a date.

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

## 6. Tonight → the call · ordered checklist

| # | Where | Step | Done when |
|---|---|---|---|
| 1 | box | Evidence, runbook, this plan committed and pushed | commit on `main`, #346 comment |
| 2 | Mac | `goes01` → Cloudera AI: runtime catalog (GPU Edition version; `import cudf` in a GPU session), GPU resource profiles, GPU node group | yes/no per item written in the #346 thread |
| 3 | Mac | `goes01` → Data Engineering: service version; VC/job config for a GPU or cuDF toggle | same |
| 4 | Mac | Internal docs: CDE cuDF plugin how-to; RAPIDS-on-Spark support for Runtime 7.3.2; current RAPIDS/GPU runtime contents | links or "none" in the thread |
| 5 | Mac | AWS G-instance quota for `srm-iceberg`, only if the Public Cloud Cloudera AI path is wanted for the call | quota state known |
| 6 | Mac | Run Surface A; if gates open, Surface B | timing table + `Gpu*` screenshot in the thread |
| 7 | box | Optional: the desk speedup number with vLLM paused (default `minAllocFraction`, `ROWS=300000000`) | on/off table |
| 8 | both | Pick the demo order from what passed: A → B → (C as roadmap) | one line in the thread |

## 6a. The goes01 checks, as Mac commands (rows 2 and 3)

Auth per `cloudera-anywhere-getting-started.md`: `bash ~/Documents/GitHub/awc-demo/awc-cookie.sh`
then `source ~/Documents/GitHub/awc-demo/awc-env.sh`. The token stays in `~/.awc.creds`; never on
a command line, never in this thread.

**Inventory first.** Which experiences, which versions, which hosts:

```bash
awc_api /experiences | jq -r '.[] | select(.appName|test("AI|Engineering";"i")) | "\(.appName)\t\(.status)\t\(.landingPageUrl)"'
awc_api /engines | jq -r '.[] | "\(.name)\t\(.version // "")"'
```

**Row 2 · Cloudera AI (Surface A gates).** UI paths are certain; the API line is an attempt.

1. Console → Cloudera AI experience → the workspace.
2. Site Administration → **Runtime Catalog**: is `NVIDIA GPU Edition` 2026.08 (CUDA 12.5) listed and enabled? Any runtime with RAPIDS in the name?
3. Site Administration → **Resource Profiles**: any profile with GPUs ≥ 1? (None means no GPU node group behind the workspace.)
4. Start a JupyterLab session on the GPU runtime + a GPU profile, then in a terminal:
   ```bash
   nvidia-smi
   python -c "import cudf, cuml; print(cudf.__version__, cuml.__version__)"   # ImportError => pip install cudf-cu12 cuml-cu12
   ```
5. API attempt, Workbench API v2 with the same Bearer (`CAI` = the workspace URL from step 1):
   ```bash
   curl -s -H "Authorization: Bearer $AWC_JWT" "$CAI/api/v2/runtimes" | jq '.runtimes[] | select(.edition|test("GPU|RAPIDS";"i")) | {edition,shortVersion,fullVersion,status}'
   ```
   `401` or a `302` to `knox-cdpsso` means the Workbench API is not behind this token; the UI answers are enough.

**Row 3 · Data Engineering (Surface B gates).**

1. Console → a Data Engineering experience → Administration: the CDE service **version** (this is what decides whether the Aug-2026 cuDF plugin can be there).
2. Virtual Clusters → a VC → Configuration: GPU quota fields (guaranteed / max GPU cores) present?
3. Jobs → Create: an "Enable GPU Accelerations" checkbox, or any cuDF / RAPIDS toggle, in the job or VC Spark configuration.
4. If a VC with GPU quota exists: upload `files/issue-346/scripts/spark_rapids_job.py`, set the toggle, `ROWS=300000000`, run on and off, read the SQL tab for `Gpu*`.

Write each answer as one line in the #346 thread: `CAI runtime: <yes/no, version>`, `CAI GPU profile: <yes/no>`,
`cudf in session: <version/ImportError>`, `CDE version: <x.y>`, `CDE GPU quota: <yes/no>`, `CDE cuDF toggle: <yes/no>`.

## 7. What to say on the call

- cuDF/cuML: measured on GB10, no code change, the table.
- Spark plugin: runs on Grace Blackwell arm64 from NVIDIA's published jar, whole job on the GPU,
  desk-side dev loop. Speedup is a cluster number; the "up to 4×" CDE claim is Cloudera's, not ours.
- Cloudera surfaces: which ones ran (A, B) and which one is a support question (C on 7.3.2). No
  dates for anything that did not run.

## 8. Open questions this plan cannot close from the box

1. Does `goes01` have a GPU node group, and in which experiences (Cloudera AI, CDE)?
2. Which CDE build carries the native cuDF plugin, and is `goes01` on it?
3. Is there any supported RAPIDS-on-Spark path for Runtime 7.3.2?
4. Does the NVIDIA GPU Edition 2026.08 runtime ship cuDF/cuML, or is it `pip install`?

## Sources

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
