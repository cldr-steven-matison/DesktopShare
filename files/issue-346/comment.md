## Part 3 evaluated from the box: goes01 inventory, plan rewritten

Commit [`5f707b5`](https://github.com/cldr-steven-matison/DesktopShare/commit/5f707b5). Read-only survey of `goes01` from `spark-dd06` over the #347 path (cookie auth, token by variable). Nothing on the tenant was created, changed or started.

### Verdict per surface

| Surface | On goes01 | GPU | Gate |
|---|---|---|---|
| **A · Cloudera AI** | one workbench `goes01-cai` (2.0.59-b252) at `goes01-cai-wb1.goes01-cai-cluster.demos.cloudera-labs.com`, reachable from the box; plus AI Inference `dm-inference` 1.14.0, model registry `dm-registry`, NVIDIA model hub with 24 models enabled | **unknown**: node types are not in the console API; the workbench API v2 wants a workbench API key (`401` with the cookie, `malformed apikey` with the JWT as Bearer), and `/api/v1/users/me` says `user.notFound` | **you**: log into wb1 once, User Settings → API Keys → create, store as `CAI_API_KEY` in `~/.awc.creds`. Then runtimes + GPU profiles are one `GET` each from the box |
| **B · CDE cuDF plugin** | Data Engineering **1.26.101-b65**, service `goes01-svc`, two VCs `goes-vc` + `test-virtual-cluster`, both **Spark 4.1.1**; `SPARK4_1_1_Standalone` (amd64+arm64) in the compatibility matrix | **none, proven**: `MaxVCAvailableGPU 0`, `gpuRequestActual 0` on both VCs; no `gpu`/`rapids`/`cudf` key in service or VC config | a GPU node group on the CDE cluster (creator `jenright`); the cuDF toggle in this build is still unread (job-create schema on the VC jobs API, box, read-only) |
| **C · CDS on Base** | not a goes01 surface | none | unchanged: the 7.3.2 support-matrix question (Mac, internal docs) |

So the Spark 4.1 half of the "CDE + cuDF" story is already deployed on the tenant; the GPU half is not. Surface A is one login away from a yes/no.

### Side finding for #343 (not acted on)
An AI Inference app `dm-inference` and a registry exist on goes01; the #343 thread says no endpoints exist. `POST /api/v1alpha1/listEndpoints` on the inference host returns `401` with the `hadoop-jwt`, so it also wants an API key. Pointer only.

### Files
- Inventory + commands + raw excerpts: [`goes01-inventory-2026-09-16.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/goes01-inventory-2026-09-16.md)
- Plan, rewritten: [`part3-cloudera-plan.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/part3-cloudera-plan.md): owners Mac → box, §1 live-tenant column, §6 checklist with state (rows 2–3 done, 4 and 7 are yours, 5–6 next on the box), §6a as box commands, §8 split per surface
- Unchanged on purpose: [`nvidia-dgx-spark-rapids-runbook.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-rapids-runbook.md), the guide tracker and chapters (this is the integration test for the call, not guide work)

### Next
1. You: wb1 login + API key (row 4); ask `jenright` about a GPU node group for CDE (row 7).
2. Box: row 5 (GPU runtime / GPU profile on wb1) and row 6 (cuDF field in the `goes-vc` job schema). If row 5 is yes, Surface A needs your go before a project and a session are created on the tenant.

Issue stays `status:in-progress`: the evaluation is delivered, Part 3 itself is not.
