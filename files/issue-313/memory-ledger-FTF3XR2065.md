# Memory ledger — FTF3XR2065, 2026-09-09 (#313 / #310)

Every memory file in the three silos on this device (the Cloudera M4 Pro work Mac; master planning
host + DesktopShare golden source), read in full and classified per `agent/local-repo-unification.md`.
**Class:** `dup` = already held by the repo (owner named) → deleted · `promote` = held only here,
important → written into the owner then deleted · `candidate-promote` = borderline; **not** promoted
this pass per Steven's "minimize repo churn" call — flagged here for his ruling, memory deleted
(content preserved in the backup) · `repo-wrong` = repo recorded wrong → fix repo · `keep` =
device-local fact per policy → rewritten terse.

Backup of the pre-sweep state (all 40 files, not committed — memories can quote Steven; repo is
public): `~/.claude/backups/memory-optimize-2026-09-09-082330.tgz`.

**Counts:** DesktopShare silo 29 → 0 · github-io silo 0 → 0 · home-dir silo 9 → 0. **Net: 28 `dup`,
10 `candidate-promote`, 0 `promote`, 0 `repo-wrong`, 0 survivors.** This planning Mac's knowledge is
inherently cross-device (see `device-work-belongs-on-device` below) and the FTF3XR2065 block of
`CLAUDE-CHECKIN.md` already holds the genuine device facts, so zero survivors is the honest result —
the same shape WindowsDesktop's app-dir and home-dir silos reached.

## Silo `-Documents-GitHub-DesktopShare` (29 → 0)

| memory | class | owner / where the repo holds it |
|---|---|---|
| awc-goes01-analytics-stack | dup | `cloudera-anywhere-getting-started.md` (AWC auth/token) + `cloudera-trino-plan.md` (static-catalog wall); project state, held in plan docs |
| blog-repo-ci-image-check | dup | `agent/incident-rules.md` (CI ≤5 MB image rule) + `agent/workflow.md` §"Publishing a blog post" |
| cdf-plc4x-iiot-nars-minifi-java | candidate-promote | NAR side-load recipe (docker-export, `nar-digest` exclusion, `NarUnpacker` batch-fail, EFM manifest de-dup) → likely `skills/nifi-and-ai/references/minifi-efm.md`. Cross-device technique, not in the skill |
| cdw-trino-vw-semiprivate-activation | dup | `cloudera-trino-plan.md` (private-LB rule, never-init-compute-cluster) |
| chapter-numbers-main-guide-only | dup | `Complete_Guide_to_Edge_Flow_Management.md` tracker + `CLAUDE.md` custom-processor-vs-guide note |
| cld-streaming-is-namespace | dup | `CONTEXT.md` (exact: `cld-streaming` is the namespace; profile/context is plain `minikube`) |
| cso-operator-app-status | dup | `cso-operator-app-plan.md` (model/ListenHTTP/k8s additions); flow source-of-truth in `CLAUDE.md` |
| custom-processor-vs-efm-guide-streams | dup | `CLAUDE.md` repo table (`streamers/nifi-processors/` = blog series, not an EFM chapter) |
| desktopshare-promotion-flow | dup | `agent/workflow.md` §"Publishing a blog post" (root→blog/ tiers, guide-blog-stays-local) |
| device-work-belongs-on-device | candidate-promote | Outward-research-vs-inside-out posture for the planning Mac → likely `agent/workflow.md` or `agent/device-comms.md`. Implicit in `CLAUDE.md` "Who's asking" but never an actionable rule |
| docs-are-completed-output-not-narration | dup | `agent/writing-style.md` (facts→design→Done→Next; no postmortem narration) |
| efm-agent-deployer-command | dup | `agent/incident-rules.md` canon + `CLAUDE.md` universal rules + skill `SKILL.md` (triple-held) |
| executescript-across-minifi-devices | dup | `efm-executescript.md` (per-device status table); `CLAUDE-CHECKIN.md` #163 side-load |
| iceberg-cso-rest-vs-impala-split | dup | `cloudera-iceberg-rest-catalog-aws-plan.md` + `cloudera-impala-iceberg-plan.md` (the two split docs) |
| iceberg-lab-152-validated | dup | `cloudera-iceberg-rest-catalog-aws-plan.md` + `files/issue-152/` (jackson fix, Flink recipe) |
| iceberg-native-restcatalog-npe-resolved | dup | `cloudera-iceberg-cso-plan.md` §NiFi (NPE root cause, wedged-CS fix); stale lab ephemera |
| iceberg-rest-catalog-aws | dup | `cloudera-iceberg-rest-catalog-aws-plan.md` (the memory's own named source-of-truth) |
| install-192-prompt-reduction-per-device | candidate-promote | 25-line rule+state hybrid (violates ≤15). The install-192 apply-only-3+6 rule → known-patterns / install doc; the device sliver ("this Mac runs prompt-reduction only, no telegram bridge") → `CLAUDE-CHECKIN.md` FTF3XR2065 block. Stale 2026-08-24 allowlist snapshot dropped |
| issue-151-native-write-sso-gated | dup | `cloudera-impala-iceberg-plan.md` (#151 SSO-gated hard-wall conclusion) |
| issue-151-puticeberg-build-plan | dup | `cloudera-impala-iceberg-plan.md` (the named plan doc = owner by definition) |
| live-site-propagation-explicit-only | dup | `agent/workflow.md` (live-site push is never autonomous; Steven names the post) |
| minifi-java-bootstrap-conf-properties | candidate-promote | `bootstrap.conf` as durable `nifi.*` override + `flow.json.raw` authority (Java 2.x) → likely skill `references/minifi-efm.md`. Cross-device gotcha; WindowsDesktop ledger promoted its equivalent to the skill |
| minifi-java-s2s-reporting-task | dup | skill `references/site-to-site.md` (SSL CS not inherited, `s2s-transport-protocol` key) |
| nifi-python-processor-live-deploy | dup | skill `references/custom-processors.md` (PVC/`kubectl cp`, `python-extensions` coords) |
| no-why-just-fix | dup | `agent/writing-style.md` (terse, no narration) + `agent/device-comms.md` (`gh issue edit --body` overwrites) |
| stacked-pr-base-branch-deletion | candidate-promote | Retarget-child-to-main-before-merging-base gotcha → likely `agent/device-comms.md` §"Working an issue". Universal git rule, absent from agent docs, bit a real session |
| telegram-bash-quirks | dup | `agent/device-comms.md` Telegram `/bash` note + `CLAUDE-CHECKIN.md` Telegram section (WindowsDesktop-context, 83 days old) |
| trino-hue-local-access-bastion | dup | `cloudera-trino-plan.md` (SOCKS bastion path, FoxyProxy scoping, minikube :443 collision) |
| trino-vw-cloudera-cloud | dup | `cloudera-trino-plan.md` (commit `5ad1809`, cdpy-from-git, srm-iceberg not CDW-capable) |

## Silo `-Documents-GitHub-cldr-steven-matison-github-io` (0 → 0)

Was empty (no files, no `MEMORY.md`). Added the header-only `MEMORY.md`.

## Silo `-steven-matison` (home-dir default project) (9 → 0)

| memory | class | owner / where the repo holds it |
|---|---|---|
| blog-day-n-claude-workflow | candidate-promote | `type: feedback` (never allowed). Raw-capture-stays-put rule (`claude-day-<N>.md` not moved/edited; blog post is a new file) not in `agent/writing-style.md` → likely there |
| cso-minikube-cpu-request-tuning | dup | `cso-level-2-ssb-cpu-tuning.md` (full recipe; the memory names it as canonical) |
| cso-operator-app-stack-toggle | dup | `cso-operator-app-plan.md` §"CPU variant" (`STACK=cpu`, alias Services, `VLLM_MODEL`) |
| cso-operator-app-work-on-main | candidate-promote | `type: feedback`; near-`repo-wrong`. "Commit to main, never auto-branch" policy missing from `cso-operator-app/CLAUDE.md` — a real correction; add one line there before relying on deletion |
| efm-agent-pod-boot-race | dup | skill `references/minifi-efm.md` §3 (health-poll `/efm/actuator/health`); fix already in `minifi-agent-pod.yaml` |
| efm-persistence-full-recipe | dup | `efm-persistance.md` (Postgres + two PVCs) + `agent/incident-rules.md` §Port-forwards |
| mynifi-0-api-access | candidate-promote | Device-local root-PG-UUID + pod-exec pattern → `CLAUDE-CHECKIN.md`; cross-device FQDN-bind + `?clusterNodeId` facts → skill `references/flow-api.md` |
| subagent-model-401-gateway | candidate-promote | `type: feedback`. Gateway-key allowlist smoke-test-one-subagent rule not in `agent/workflow.md` §"Model, effort & context hygiene" — genuine gap for gateway-key environments |
| x-to-slack-flow | candidate-promote | In-progress local project (`~/x-to-slack/`). Gotchas (syndication endpoint, empty-UA→400) → its own README; open Slack-token TODO → a GitHub issue, not a memory |

## Candidate promotions — Steven's call (nothing edited this pass)

Highest-value gaps the subagents surfaced, ranked:
1. **`cso-operator-app-work-on-main`** — **PROMOTED 2026-09-09** to `cso-operator-app/CLAUDE.md`
   (commit `dba0359`) after Steven's steer: it's git-provable (every commit on `main`, no branches),
   absent from an always-loaded file, and prevents the harness auto-branching off `main`. The only
   one of the 10 placed; the rest below stay unplaced (delete-and-wait-for-recurrence).
2. **`subagent-model-401-gateway`** — the "smoke-test one sub-agent before fanning out on a gateway
   key" rule is absent from `agent/workflow.md`.
3. **`stacked-pr-base-branch-deletion`** — retarget-child-before-merging-base is a universal git
   gotcha absent from `agent/device-comms.md`.
4. **`cdf-plc4x-iiot-nars-minifi-java`** and **`minifi-java-bootstrap-conf-properties`** — MiNiFi Java
   NAR/property gotchas for the skill (`references/minifi-efm.md`); WindowsDesktop promoted the
   bootstrap one to the skill already.
5. **`device-work-belongs-on-device`** — planning-Mac research posture; a one-liner in `workflow.md`.
6. **`blog-day-n-claude-workflow`** (raw-capture-stays-put → `writing-style.md`),
   **`mynifi-0-api-access`** (device UUID → CHECKIN), **`install-192`** (prompt-reduction-only → CHECKIN),
   **`x-to-slack-flow`** (→ local README + an issue).
