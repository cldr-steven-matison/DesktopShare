## Runbook rewritten as the complete RAPIDS document

Commit [`96a0120`](https://github.com/cldr-steven-matison/DesktopShare/commit/96a0120).

[`nvidia-dgx-spark-rapids-runbook.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-rapids-runbook.md) is now one technical document instead of the first-run narrative. Same filename, same commands, error text and tables. What changed:

**Removed:** the dated issue header, the "I wanted to know two things" opener, "Trap 1/2/3", "I tried", "I am not going to dress that up", and the integration-test wrap-up section.

**Added (was only under `files/issue-346/` before):**
- Spark 4.0.4 install steps and the full local-mode `spark-submit` configuration, with why the executor/task GPU confs are omitted in `local[*]`.
- What `spark_rapids_job.py` does, and the launcher's environment variables.
- The Cloudera AI Workbench L4 section: workbench facts (one L4, no GPU-edition runtime, session API fields), the pip path and the admin path to a GPU session, UI start, 16 GB+ sizing, the Chrome NSS import, and the 100k-row table (4.6× overall, join 6.8×).
- A three-row table of the Cloudera surfaces for the Spark job with their measured state (Workbench, CDE with `MaxVCAvailableGPU 0`, Spark on Base with no CDS GPU path for 7.3.2).
- Gotchas as short technical statements, plus a scripts and raw-output index with every parameter.

**Swept:** the RAPIDS row and both status paragraphs in [`Complete Developer Guide for Nvidia Spark with Cloudera.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/Complete%20Developer%20Guide%20for%20Nvidia%20Spark%20with%20Cloudera.md) (L4 result, CDE/CDS state, chapter prose still pending), and one sentence in [`nvidia-dgx-spark-cloudera-aws.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-aws.md) §2.4. [`files/issue-346/results.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-346/results.md) and the plan/inventory files are unchanged.

**Prose lint** (`files/prose-lint.py`, per 1,000 words):

| | words | emdash/k | proof/k | colon/k | dates | issues | prov |
|---|---|---|---|---|---|---|---|
| before | 1263 | 0.0 | 1.6 | 1.6 | 2 | 2 | 4 |
| after | 1839 | 0.0 | 1.1 | 12.0 | 1 | 1 | 2 |

The remaining date is the arm64 jar publication date (2026-08-28) and the remaining issue reference is the public NVIDIA/cudf-spark#6881 link. Every relative link in the scripts section resolves.
