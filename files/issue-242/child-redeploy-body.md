NvidiaSpark-1: redeploy CDP CE Base on AWS end to end from the DGX Spark, from an empty account, and re-run [cloudera-ce-aws-runbook.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/cloudera-ce-aws-runbook.md) top to bottom as written. The 2026-09-16 run reached a working Ozone + NiFi + Kafka cluster only after live fixes; this run proves the runbook is clean when followed cold.

**Prerequisite:** the teardown issue for the current `srm-cloudera-ce-base` cluster has run and printed its three zeros.

**Cost line (say it before asking for the go):** ~3 h 40 min wall-clock, ~$2/h while up, 11 EC2 nodes in `us-east-2`. Explicit go from Steven in the turn that runs `infrastructure.yml`; tear down or pause in the same session unless told to keep it.

**Carry into this run (owed from the first one):**
- Apply the worker sizing recorded in runbook §2a (`r5a.2xlarge` for the graft) to `hosts_base.tf` before `infrastructure.yml`, instead of resizing after the fact.
- Run Cloudera Manager's **Deploy Client Configuration** after the Ozone safety valve so the gateway host does not carry stale TLS config.
- The Ozone ring safety valve `hdds.grpc.tls.enabled=false` marked `final` goes in the template, not as a live edit.
- Re-run the Ch18 proof at the end: reverse tunnel per worker, `Ch18LlmBridge` PG published to Kafka and read back ([build-flow.py](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-341/build-flow.py), [verify-kafka.sh](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-341/verify-kafka.sh)).

**Done when:** every runbook step ran without a live fix, the transcript is committed under `files/issue-<this>/`, runbook §0's wall-clock table has the second run's column, the Ch18 tracker row cites this issue, and the cluster is torn down with its three zeros in the same session unless Steven says keep.

Runs after #357 (teardown). Parent: EPIC #356. Filed from #341 ("Make a new task to test re-deploying end to end").
