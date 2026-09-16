NvidiaSpark-1: tear down the CDP CE Base cluster that [cloudera-ce-aws-runbook.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/cloudera-ce-aws-runbook.md) stood up on 2026-09-16, and prove the three zeros.

**Live state when filed (2026-09-16 ~19:40 UTC, read-only check):** 11 EC2 instances tagged `deployment=srm-cloudera-ce-base` in `us-east-2` are `running` (10 × t3a/r5a workers and masters, 1 × t3a.medium), billing ~$2/h since 02:32 UTC. The cluster was kept up at the end of the validation session on Steven's call.

**What to run:** runbook §6 (exits) — `infrastructure-teardown.yml` with the same `config-srm-base.yml`, then the three-zero proof (EC2, EBS, VPC counts at 0 for the `deployment` tag) from runbook §6 as well. `CDP_LICENSE_FILE` must resolve for the teardown too.

**Rule:** this is an explicit-go action. Nothing runs until Steven says yes to the teardown in that turn; guard 17 asks at the command. State the cost line first: the cluster bills ~$2/h until it is gone.

**Done when:** the three counts print 0, the transcript is committed under `files/issue-<this>/`, and the runbook §0 line "the teardown and its three zeros are still owed" is replaced with the date it ran.

Parent: EPIC #356. Filed from #345 ("Make a new task to destroy this env").
