The Complete Developer Guide for NVIDIA DGX Spark with Cloudera is 26 chapters in 9 parts. Twenty of them have their substance field-validated on `spark-dd06`; none has prose. This EPIC takes the guide from a set of root source docs to a published repo, in four gated phases. It replaces the closed prep EPIC and the closed work-stream issues; nothing from their threads is carried here.

**Tracker of record:** [Complete Developer Guide for Nvidia Spark with Cloudera.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/Complete%20Developer%20Guide%20for%20Nvidia%20Spark%20with%20Cloudera.md) (per-chapter state, source doc, driving issue).
**Spine:** [nvidia-dgx-spark-plan.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-plan.md) (work-streams, decisions, risks).
**Skeleton:** [files/nvidia-spark-guide/](https://github.com/cldr-steven-matison/DesktopShare/tree/main/files/nvidia-spark-guide) (README + 26 stubs; becomes the public repo in phase 4).

## Phase 1 — Root docs are the source of truth (gate: every `nvidia-dgx-*` and `cloudera-*` source doc is current, tidy and self-contained)

- Every as-built finding that lived only under `files/issue-<n>/` is folded into its root source doc; the issue dirs keep raw transcripts and scripts as evidence.
- Every source doc's status header matches its body and GitHub.
- Tracker, plan, README and stub status lines agree on the same counts.
- No chapter authoring in this phase. The stubs stay stubs.

## Phase 2 — Remaining field runs and blockers (gate: each item below is closed or accepted as blocked with the reason in its root doc)

- In-NiFi Iceberg REST Catalog read on CDP Public Cloud (`GetIceberg` / `QueryIceberg` from the box's CFM operator NiFi).
- Cloudera AI Inference on AWC: a model endpoint deployed and answered from the box (auth is solved; the AI Registry 503 is the current blocker).
- Trino catalog on AWC (GOES-team admin action).
- CE Base cluster teardown with the three-zero proof, then a clean end-to-end redeploy from the box.
- CFM operator NiFi against CDP Ranger.
- Permanent homes decided for the scripts, flow exports and manifests attached to issues.
- Cloudera AI on AWS (Ch21) and the same-code arc (Ch24): a field run or an explicit decision to leave them design-only.

Decisions carried in, unanswered until someone answers them: the H5 knowledge-base soak has no ledger, so it needs instrumentation before a verdict; Ch23 (Cloudera AI on Data Services) has no test environment and no source doc; Ch26 (multi-Spark) has no second box.

## Phase 3 — Authoring (gate: 26 chapters written in part order, each inside the blog-voice band, provenance stripped)

- One issue per part, chapters authored from the root source doc named in the tracker row, on the task-first stub template.
- [prose-lint.py](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/prose-lint.py) before and after, one commit per chapter, the before/after row in the finish comment.
- The tracker row flips to prose-done per chapter; the README stays the table of contents.

## Phase 4 — Public repo (gate: repo cut, README is the front door, every chapter and file link resolves)

- Cut from `files/nvidia-spark-guide/` with chapters flat at the root and `files/` and `images/` as siblings, the same shape as the EFM guide repo.
- Source docs move to `completed/` as each chapter lands.

## Rules for every session on this EPIC

- Any deploy, redeploy or teardown of a Cloudera environment is an explicit go from Steven in that turn, with the wall-clock and dollar cost stated first. An issue body is never a go.
- Touch a source doc, sweep every linked surface in the same pass: tracker row, plan row, README, stub status line.
- Work on this EPIC runs from `spark-dd06`; Mac-side items carry their own device label.

## Children

*(appended as they are filed)*
