AWC field validation complete (#343, 2026-09-16) — swept all linked surfaces:

- [nvidia-dgx-spark-plan.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-plan.md) — Status header (line 3), WS row I (line 52): AWC reachability proven, Knox SSO/Trino/Iceberg/Ozone confirmed, CAI/Kafka blocked with root causes
- [Complete Developer Guide for Nvidia Spark with Cloudera.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/Complete%20Developer%20Guide%20for%20Nvidia%20Spark%20with%20Cloudera.md) — Status header line 5 (updated 2026-09-16), chapter 20 row (line 53 — Kafka/CAI blocked documented), chapter 22 row (line 55 — reachability proven, no inference endpoints)
- [files/nvidia-spark-guide/README.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/README.md) — Status line (line 5 — date + AWC proven note)
- [nvidia-dgx-spark-cloudera-awc.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-awc.md) — All `[TO-VERIFY]` blocks replaced with confirmed results or blocked + root cause
- [files/nvidia-spark-guide/ch20-cloudera-awc-on-aws.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/nvidia-spark-guide/ch20-cloudera-awc-on-aws.md) — As-built chapter with walk-through commands

**PROVEN:** reachability, CA chain, Knox SSO, CDF, SSB, Trino, Iceberg, Ozone S3  
**BLOCKED:** Cloudera AI Inference (needs UI model deployment), Kafka produce/consume (SASL auth blocked — Knox cookie ≠ Kafka workload identity token)

sha: [8248463](https://github.com/cldr-steven-matison/DesktopShare/commit/8248463)
