## Row 5 answered: wb1 has one idle NVIDIA L4, and no GPU-edition runtime

Commit [`a73f3d1`](https://github.com/cldr-steven-matison/DesktopShare/commit/a73f3d1). Steven logged into `goes01-cai-wb1` and created a workbench API key; read-only from the box with it. The key went through a session transcript and is to be deleted in the workbench (Key ID ending `…c4a541`).

| Check | Answer |
|---|---|
| CAI GPU | **1 × NVIDIA-L4, 0 used**, accelerator label `NVIDIA-L4` available, `max_gpu_per_workload 1` (`/api/v1/site/stats`, `/api/v2/nodelabels`) |
| CAI runtime | **no GPU edition**: 6 runtimes, Hardened JupyterLab / PBJ Workbench on Python 3.11 and 3.14 (2026.04.2-b16), Agent Studio, RAG Studio; `enable_register_runtimes_for_user false` |
| Addons | Spark Connect 3.5.4 (7.3.1 / 7.3.2) and **4.1.1**, Hadoop CLI, Ozone |
| Session API | `CreateJobRequest` takes `nvidia_gpu`, `accelerator_label_id`, `runtime_identifier`, `runtime_addon_identifiers` |
| Projects | 10, including Steven's `srm-test` |

So Surface A is runnable right now on the no-admin path: a session in `srm-test` on Hardened Python 3.11 with `nvidia_gpu 1`, then `pip install cudf-cu12 cuml-cu12` and `cudf_bench.py`. The one unknown left is whether the L4 node's driver takes the `cu12` wheel; `nvidia-smi` inside the session answers it. The clean path is a site admin registering the NVIDIA GPU Edition 2026.08 runtime. A GPU session is a tenant write, so it waits for your go (row 10).

Files:
- [`goes01-inventory-2026-09-16.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/goes01-inventory-2026-09-16.md) §"Workbench wb1" (raw outputs)
- [`part3-cloudera-plan.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/part3-cloudera-plan.md) §3 rewritten around the two paths; checklist rows 4–5 done, 10 ready
- [`cai-key-set.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/cai-key-set.sh) (hidden-prompt append of `CAI_API_KEY` to `~/.awc.creds`) and a `cai_api` wrapper in [`awc-env.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-347/awc-env.sh)

Still open: row 6 (cuDF field in the `goes-vc` job schema), row 7 (GPU node group for CDE, `jenright`), row 10 (your go for the session). Issue stays `status:in-progress`.
