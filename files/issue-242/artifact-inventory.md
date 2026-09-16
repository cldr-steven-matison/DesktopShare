# Guide artifact inventory — files attached to the DGX Spark guide issues

Taken 2026-09-16 for [#242](https://github.com/cldr-steven-matison/DesktopShare/issues/242) and handed to [#359](https://github.com/cldr-steven-matison/DesktopShare/issues/359), where the placement decision is made. One row per file. **Kind**: as-built-doc · plan-doc · comment-body · transcript · script · flow-export · manifest · patch · data. **Referenced from**: root docs, chapter stubs, trackers or the device register that cite the file by name (issue dirs excluded). **Proposed home** is a proposal, not a decision:

- **guide files/** — a chapter will need it; it becomes part of the public repo under `files/nvidia-spark-guide/files/`.
- **external repo** — belongs beside the code it patches or the flow it exports (`cloudera-ce-aws`, `NiFiandAi`, …).
- **evidence** — stays under `files/issue-<n>/` (transcripts, raw output, comment bodies, point-in-time reports).
- **delete** — build artifact or byte-identical duplicate.

Prose findings from the same sweep (as-built docs whose substance was not in any root doc) were folded into the root docs in the same pass; see the #242 closing comment. The two `files/issue-342/` items marked *#355* are the live hand-off for that issue and are not to be moved until it closes.

## files/issue-242/

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| comment-343-sweep.md | 1676 | comment-body | sweep note after #343 | — | evidence |
| consolidated-dangling-work.md | 12466 | plan-doc | the #320 dangling-work tracker (superseded) | — | evidence |
| report-2026-09-10.md | 2703 | plan-doc | tracker/plan/README sync report | — | evidence |
| artifact-inventory.md | — | this file | | #359 | evidence |
| eval-2026-09-16.md | — | plan-doc | the correctness-evaluation record | #242 | evidence |
| epic-body.md, child-*-body.md | — | comment-body | issue bodies as filed | — | evidence |

## files/issue-341/ — Ch18 CE Base LLM bridge

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| build-flow.py | 13580 | script | builds/starts/stops/exports the Ch18 NiFi PG through Knox | cloudera-aws doc, #358 | guide files/ (or NiFiandAi) |
| verify-kafka.sh | 1762 | script | reads the PG's Kafka output via SSH jump + kinit | #358 | guide files/ |
| ranger-kafka-grant.sh | 1825 | script | Ranger grant for nifi/admin on `ch18-*` | — | guide files/ |
| Ch18LlmBridge.flow.json | 52304 | flow-export | the PG export, sensitive values null | cloudera-aws doc | guide files/ |
| kafka-readback-2026-09-16.txt | 1712 | transcript | console-consumer readback of 3 completions | cloudera-aws doc | evidence |
| tunnel-probe-2026-09-16.txt | 378 | transcript | probe of the 4 tunneled workers | cloudera-aws doc | evidence |
| build-2026-09-16.txt | 17212 | transcript | verbose build-flow.py run | — | evidence |
| ranger-kafka-grant-result.txt | 290 | transcript | the two policy POST results | — | evidence |
| comment-2026-09-16-wrapup.md | 3886 | comment-body | posted wrap-up | — | evidence |
| session-draft.md | 1115 | transcript | pre-post draft of the first status comment (moved from `files/`) | — | evidence |

## files/issue-342/ — Ch19 CDP Public Cloud

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| as-built-2026-09-16.md | 11002 | as-built-doc | `srm-iceberg` env / Data Lake / Data Hub / Trino VW / REST Catalog live state + Tier-A proof | cloudera-aws doc §3 (folded) | evidence |
| rest-catalog-validation-2026-09-16T1344Z.txt | 1763 | transcript | Tier-A curl proof | cloudera-aws doc | evidence |
| rest-catalog-flights-2026-09-16T1216Z.txt | 43 | transcript | aborted early run | — | evidence |
| nifi-tier-b-plan-2026-09-16.md | 17099 | plan-doc | hand-off for the in-NiFi read | — | *#355*, leave |
| comment-2026-09-16.md | 3992 | comment-body | posted comment | — | evidence |
| session-draft.md | 581 | transcript | pre-correction draft (moved from `files/`) | — | evidence |

## files/issue-343/ — Ch20 AWC

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| claude-chrome-cdp.js | 11662 | script | Node CDP driver for automated browsing | — | guide files/ (reusable tool) or `files/` root beside `headless-shot.mjs` |
| claude-chrome.sh | 866 | script | Chrome launcher with CDP | — | same as above |
| swagger-console.json / swagger-cai.json / swagger-lakehouse.json | 93152 / 104387 / 46474 | manifest | AWC OpenAPI specs | — | evidence |
| field-validation.txt, awc-check-latest.txt, ozone-s3-validation.txt | 5810 / 5033 / 3875 | transcript | validation transcripts | — | evidence |
| comment.md, comment-done.md | 4324 / 2220 | comment-body | posted comments | — | evidence |

## files/issue-345/ — CE Base runbook

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| ozone-nifi-cluster.yml | 33590 | manifest | the Ozone + NiFi graft cluster template | ce runbook, blog | external repo `cloudera-ce-aws` (fork) + guide files/ |
| ozone-nifi-cluster.diff | 8918 | patch | stock vs graft diff (11 edits) | ce runbook | with the template |
| patches/RedHat-pre.yml | 5549 | patch | Caddy on RHEL 9 without subscription (#292) | ce runbook | external repo `cloudera-ce-aws` |
| patches/jdk_facts.py | 4877 | patch | custom fact module | ce runbook | external repo `cloudera-ce-aws` |
| ansible-navigator.yml | 2327 | manifest | navigator EE config | ce runbook, blog | with the template |
| config-srm-base.example.yml | 897 | manifest | scrubbed per-run config | ce runbook | with the template |
| srm-smoke.flow.json | 6448 | flow-export | smoke PG | ce runbook | evidence |
| cm-services-after-first-run.json | 14871 | data | CM health dump | ce runbook | evidence |
| worker-sizing-2026-09-16.txt, nifi-*.txt, ozone-*.txt, smoke-*.txt, restart-*.txt, stop-unneeded-services-2026-09-16.txt, config-changes-2026-09-16.txt, ranger-nifi-admin-grant.txt | — | transcript | 17 validation and incident transcripts | ce runbook (most) | evidence |
| comment-2026-09-16-*.md (4) | — | comment-body | posted comments and the source analysis | ce runbook | evidence |

## files/issue-346/ — RAPIDS

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| scripts/cudf_bench.py | 2243 | script | cuDF zero-code-change benchmark | rapids runbook, demo, cloudera-aws doc, tracker | guide files/ |
| scripts/cuml_bench.py | 3162 | script | cuML vs scikit-learn benchmark | rapids runbook, demo | guide files/ |
| scripts/spark_rapids_job.py | 2902 | script | Apache Spark job checking for `Gpu*` operators | rapids runbook | guide files/ |
| scripts/run-spark-rapids.sh | 1267 | script | Spark 4.0.4 local-mode + plugin launcher | rapids runbook | guide files/ |
| cai-key-set.sh | 816 | script | writes the Workbench API key into `~/.awc.creds` | — | guide files/ (beside the #347 helpers) |
| results.md | 8632 | as-built-doc | measured tables (cuDF/cuML/Spark) | rapids runbook, demo, cloudera-aws doc | evidence (runbook carries the tables) |
| goes01-inventory-2026-09-16.md | 13879 | as-built-doc | goes01 tenant survey for RAPIDS placement | rapids runbook | evidence |
| chrome-cert-fix.md | 1440 | as-built-doc | Chrome NSS trust fix for the goes01 CA | rapids runbook | evidence |
| part3-cloudera-plan.md | 23954 | plan-doc | Cloudera-surfaces test plan | rapids runbook | evidence |
| spark-explain*.txt, spark-gpu-vs-cpu.txt, nvidia-smi-*.txt, cudf-results.txt, cuml-results.txt | — | transcript / data | 11 raw outputs | rapids runbook | evidence |
| comment.md, comment-rewrite.md | — | comment-body | posted comments | — | evidence |

## files/issue-347/ — corp VPN + goes01 (device helpers)

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| awc-env.sh | 4602 | script | AWC shell env (awc_api/cdf_api/ssb_api/trino_q) | device register, awc doc, anywhere ref, KB doc | guide files/ (Ch20/Ch22 need it) |
| awc-cookie.sh | 1856 | script | pulls `hadoop-jwt`/XSRF from Firefox | device register, awc doc, anywhere ref | guide files/ |
| goes-certs-import-linux.sh | 2211 | script | imports the goes01 CA chain | device register, anywhere ref | guide files/ |
| awc-creds-set.sh, awc-check.sh, vpn-connect.sh, vpn-check.sh | — | script | credential writer, four-proof check, VPN connect/check | device register, anywhere ref, KB doc | stays (device-local helpers the register points at) |
| awc-check-*.txt (4) | — | transcript | reachability runs | — | evidence |
| comment.md | 5671 | comment-body | posted account | — | evidence |

## files/issue-351/ — CAI Inference + Kafka on AWC

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| step1-cai-findings.md, step2-kafka-findings.md, step3-cai-registry-blocked.md | 2550 / 4384 / 4153 | as-built-doc | CAI SPA-only, Kafka OAUTHBEARER proof, AI Registry 503 | awc doc (folded) | evidence |
| step*-*.txt / *.json (12) | — | transcript / data | probes and proofs | — | evidence |

## files/issue-352/ — k3s under the corp VPN

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| k3s-vpn-route.sh | 1506 | script | keeps `10.43.0.0/16` off `tun0` | — | guide files/ (Ch3) |
| k3s-vpn-route.service / .timer | 186 / 206 | manifest | systemd oneshot + 30 s timer | runbook, plan, device register | guide files/ (Ch3) |
| install.sh | 1012 | script | installs the three | device register | guide files/ (Ch3) |
| as-built-2026-09-16.md | 8561 | as-built-doc | the two stacked causes and fixes | runbook §2, tracker, cloudera-aws doc | evidence |

## Outside the issue dirs

| file | bytes | kind | what it is | referenced from | proposed home |
|---|---|---|---|---|---|
| files/nifi-iceberg-rest-catalog-demo.flow.json | 1611226 | flow-export | the box's full NiFi flow export with the `IcebergRestCatalogDemo` PG | — | *#355*, leave; then external repo `NiFiandAi` |
| files/issue-344/body-full-analysis.md | 3443 | comment-body | the #344 incident body with the longer opencode-vs-Claude analysis (moved from `files/`) | — | evidence |

## Removed in this pass

Byte-identical copies of live GitHub text: `files/issue-342-body.md`, `files/issue-343-body.md`, `files/issue-343-session.md`. Untracked build artifact deleted from disk: `files/issue-341/__pycache__/` (already gitignored). Duplicate 43-byte aborted run: `files/issue-342/rest-catalog-flights-2026-09-16T1220Z.txt`. `files/issue-353/` is empty and stays as the directory for that closed issue's future artifacts.
