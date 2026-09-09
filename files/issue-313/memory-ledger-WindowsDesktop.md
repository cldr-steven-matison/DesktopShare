# Memory ledger — WindowsDesktop, 2026-09-09 (#313)

WindowsDesktop was the **#310 worked example** (85 + 9 + 6 → 4). The full per-file
classification of all three silos already lives in
[`files/issue-310/memory-ledger.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-310/memory-ledger.md)
(143 rows) and is not restated here. This #313 pass is a **verification** that the
post-#310 state still conforms to the policy as **amended 2026-09-09** (`type: feedback`
banned, `approved:` line required, #247 retired as the incident funnel — lint checks 3b/3c
in [`files/memory-lint.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/memory-lint.sh)).

Backup of the pre-verify state (all silos, not committed — the tree is public):
`~/.claude/backups/memory-optimize-313-2026-09-09-143427.tgz` (plus the original #310
sweep backup `~/.claude/backups/memory-optimize-2026-09-08-100020.tgz`).

## Silos on this device (all read in full, not the MEMORY.md pointers)

| silo (`~/.claude/projects/<path>/memory`) | before (#310) | now | lint |
|---|---|---|---|
| `-home-tunas-DesktopShare` | 85 → 4 | 4 | CLEAN |
| `-home-tunas-cso-operator-app` | 9 → 0 | 0 (header only) | CLEAN |
| `-home-tunas` | 6 → 0 | 0 (header only) | CLEAN |
| `-tmp-claude-1000-…-scratchpad-notiftest` | — | empty, no `MEMORY.md` | ephemeral scratchpad silo; ignored |

No older-path / renamed-clone silo found (the DesktopShare clone path is unchanged on this host).

## The 4 survivors — policy conformance (DesktopShare silo)

| memory | type | approved: | lines | verdict |
|---|---|---|---|---|
| [`amoled-this-device`](amoled-this-device.md) | reference | `2026-09-08 …/issues/310` | 15 | keep — compliant |
| [`x-live-pipeline`](x-live-pipeline.md) | reference | `2026-09-08 …/issues/310` | 14 | keep — compliant |
| [`iceberg-on-this-box`](iceberg-on-this-box.md) | reference | `2026-09-08 …/issues/310` | 13 | keep — compliant |
| [`local-paths-and-quirks`](local-paths-and-quirks.md) | reference | `2026-09-08 …/issues/310` | 14 | keep — compliant |

All four are genuine device-local facts (COM ports, flash partitions, WSL2 tunnel/port-forward
collisions, vLLM pin-memory flag, mediamtx X-stream chain, Iceberg NAR/demo-rig leftovers) that no
other device needs and the repo does not hold. `type: reference`, an `approved:` line, ≤ 15 lines
each. **0 promotions, 0 repo-wrong, 0 deletes this pass** — all of that was done in #310.

## Finding — not session-fixable (reported, not fixed)

- **All three `MEMORY.md` headers still cite the retired `#247 comment` funnel.** The canonical
  header in [`agent/local-repo-unification.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/local-repo-unification.md)
  §"MEMORY.md — the header every silo carries" was changed to
  *"issue → incident (agent/incident-rules.md) → a new issue summarizing the triggering event"*
  on 2026-09-09. A session **cannot** refresh it: **guard rule M denies every write to the memory
  dir, including a hand-edit of `MEMORY.md`**, and `memory-propose.sh --index` only *appends a
  pointer line* — it never rewrites the header. So there is no sanctioned session path to bring a
  header current after a policy amendment. Same staleness will exist on every other device's silos.
  Flagging for a guard-M-exempt refresh path (or Steven doing it out-of-band); left untouched here.

## Reported (procedure step 3)

- **Model pin:** `~/.claude/settings.json` → `"model": "claude-fable-5-1[1m]"` (Fable 5.1, 1M-context).
  Steven-set; differs from the canon base `claude-opus-4-8`
  ([`agent/workflow.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/agent/workflow.md)
  §"Model, effort & context hygiene"), which is expected — the pin is Steven's per-device choice.
- **Un-pushed clone:** `~/NiFi-Templates` has 1 un-pushed commit `0cebd32` ("Add flow templates
  from DesktopShare …"). Worth pushing so it isn't only local. No other clone under `~` has un-pushed work.
- **Local-only hooks/skills/agents:** none. `~/.claude/hooks` does not exist (repo hooks run from
  `.claude/hooks`); `~/.claude/agents` does not exist; installed skills `align`, `nifi-and-ai`
  match `skills/`. Nothing local diverges from the repo.
