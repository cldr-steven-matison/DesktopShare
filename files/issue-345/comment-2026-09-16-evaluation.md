**Evaluation from the Mac: the Ozone root-cause chain in this thread is over-fitted and is contradicted by our own GOOD deploys. Correcting it before the next run.**

The streaming deliverable stands: NiFi 4/4, Kafka, Hive/Iceberg, Registry and Ranger are all proven with transcripts, and the three deploy-shape fixes (ZK plaintext port, the `libcrypto` SIGSEGV on the first encrypted Ranger-audit write, the Ranger `admin` 403) are real. No dispute there.

The 09-16 correction of the 09-15 TLD theory was right: `DomainValidator` rejects `steven-ce-…cldr.internal` exactly as it rejects `srm-…cldr.internal`, so a domain change is not the fix. Do not spend a redeploy on it.

But the corrected chain (DomainValidator rejects FQDN → DNS SAN dropped → IP-only SCM cert → Ratis mTLS `SNIHostName` failure → ring never forms) is itself falsified by two same-domain, same-parcel clusters that came up healthy:
- `cm-mcp-ce` (#292, [VALIDATION.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-292/VALIDATION.md)): same pinned parcel `p10000.82216952`, same `cldr.internal` domain, stock `ozone-cluster.yml`, deployed 2026-09-14 → `ozone-base-cluster GOOD_HEALTH`. Two days before this run.
- `steven-ce` (#180, [FACTS.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-180/FACTS.md)): Ozone GOOD on first deploy; went BAD only after an overnight stop/start.

If `DomainValidator` rejects every `*.cldr.internal` name (our own finding), those GOOD clusters carried the identical IP-only SAN and their SCM rings formed anyway. So the IP-only SAN is not what breaks Ratis here. The cert story explains the log lines but does not survive the counter-examples.

The variable neither run controlled for is `name_prefix`. Every GOOD deploy used a short prefix (`steven-ce`, `cm-mcp-ce`, 9 chars). The one BAD deploy used `srm-cloudera-ce-base` (20 chars), which produces the doubled hostname `srm-cloudera-ce-base-base-master-01.cldr.internal`. That is the strongest untested difference. (Other diffs, first-run arm64 EE and exact CM sub-build, matter less: the cluster nodes are x86_64 regardless, so the EE arch does not touch SCM cert generation.)

One cheap experiment settles it, and it was available two days ago and not taken: pull the SCM sub-CA leaf SAN off a known-GOOD cluster with `openssl x509 -ext subjectAltName`.
- GOOD shows a DNS SAN → `DomainValidator` did not reject there → the discriminator is name-specific → the fix is a short `name_prefix`, which is what every working deploy already used.
- GOOD shows IP-only SAN too → the SAN is a red herring → the `srm` ring failure has another cause (a race in primordial SCM init, or the CM build), and the cert evidence should stop being cited as the root cause.

Recommended next step (DGX-side, `spark-dd06`): before tearing down `srm-cloudera-ce-base`, redeploy once with a short `name_prefix` (stock `ozone-cluster.yml`, same parcel/domain) and capture the SCM SAN both ways. That isolates `name_prefix` and confirms or kills the hypothesis in one run. If a GOOD cluster is still up, just grab its SCM SAN first, it is a two-minute check.

Operational note: `srm-cloudera-ce-base` was kept running per Steven's call and has billed since 02:32 UTC 09-16 at ~$2/hr; the three-zero teardown proof is still owed. It is the ideal place to run the experiment before it comes down.

Analysis only, from the Mac (`FTF3XR2065`); nothing live was touched.
