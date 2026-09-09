# Memory ledger — NvidiaSpark-1 (spark-dd06), 2026-09-09 (#313 / #310)

Every memory file in the one populated silo on this box (`~/.claude/projects/-home-tunas-BrainShare/memory/`),
read in full and classified per `agent/local-repo-unification.md` §"Optimize sweep". This is the actual DGX
Spark box, not a planning host; its genuine device-local facts already live in the rich `CLAUDE-CHECKIN.md`
NvidiaSpark-1 block (L369–406), so — as on FTF3XR2065 — nearly everything is a `dup`.

**Class:** `dup` = repo already holds it → deleted · `candidate-promote` = held only here, borderline → not
edited into the repo this pass, flagged for Steven's ruling / moved to its own issue (content preserved in the
backup) · `keep` = device-local fact per policy → promoted terse into CHECKIN, then deleted.

Backup of the pre-sweep state (all 12 memories + MEMORY.md — not committed; memories can quote Steven and this
repo is public): `~/.claude/backups/memory-optimize-2026-09-09-192146.tgz`.

**Counts:** silo `-home-tunas-BrainShare` 12 → 0. No second older-path silo held memory files. Dup-vs-candidate
calls confirmed by a repo-coverage search (skill `references/`, `agent/*`, CHECKIN, DGX docs, committed `files/`).

## Silo `-home-tunas-BrainShare` (12 → 0)

| memory | type | class | owner / where the repo holds it |
|---|---|---|---|
| nvidiaspark-1-owns-dgx-spark-epic | project | dup | 183-line EPIC narrative → `nvidia-dgx-spark-plan.md`, the EPIC #226 tracker, `files/issue-226/*`, and the CHECKIN NvidiaSpark-1 block. Project state that changes; not a device-local fact. |
| dgx-spark-k3s-not-k3d | feedback | dup | k3s substrate + model lock → CHECKIN L389, `nvidia-dgx-spark-plan.md`, `known-patterns.tsv` `k3s-gb10`. |
| verify-spark-box-live-before-claiming | feedback | dup | `CLAUDE.md` universal rule "Live state outranks docs" + `agent/workflow.md` §"Live infra vs. docs". |
| no-commit-trailers-overrides-harness | feedback | dup | Verbatim `CLAUDE.md` universal rule (no `Co-Authored-By`/`Claude-Session`). Deleting it also clears the dangling `[[issue-work-ends-in-commit-push-comment]]` wikilink. |
| streamers-and-dgx-guide-are-separate-tracks | feedback | dup | `nvidia-dgx-spark-cso-demos.md`, `nvidia-dgx-spark-offload.md`, and `streamers/streamers-new-brain-plan.md` all state "share the box and nothing else". |
| streamer-kb-is-about-the-streamer-not-clips | project | dup | Streamers-track design fact (#271) → belongs to the Streamers docs, not this box's device silo. |
| spark-prefers-k8s-pods-over-docker | user | dup | `streamers/streamers-new-brain-plan.md` L29 verbatim ("new services = k3s pods in committed yaml, not docker runs; Whisper :8003 used as-is"); demonstrated across the CHECKIN NvidiaSpark-1 block (docker serving tier vs k3s additions). |
| additive-not-reimport-for-live-credential-pgs | feedback | candidate-promote → **#319** | Genuine skill gap (credential-loss safeguard); moved to its own nifi-and-ai skill issue #319 with the change plan. Not edited into the skill this session. |
| nifi-2x-generator-gotchas-spark | project | candidate-promote → **#319** | 4 of 6 gotchas already in the repo (`custom-processors.md`, `layout.md`, `set_params.py`, `build_streamer_research.py`); the 2 absent slivers (Response-Body-Attribute-Size bytes; RUN_ONCE-needs-STOPPED) moved to #319. |
| scope-from-the-research-not-the-aside | feedback | candidate-promote (flagged) | Planning lesson, absent from `agent/*`. Per #310 a lesson goes issue → incident → issue, not a memory; flagged in the #313 comment for Steven's ruling. |
| write-plainly-dont-edit-rules-on-an-aside | feedback | candidate-promote (flagged) | Writing/scope lesson, both halves absent from `agent/writing-style.md`. Per #310 → issue/incident; flagged in the #313 comment. |
| spark-k3s-api-rides-on-wifi | project | **keep → CHECKIN** | Promoted one terse "Network / link" line into the CHECKIN NvidiaSpark-1 block: k3s API on `wlP9s9 192.168.1.203`, both wired NICs carrier=0, a Wi-Fi drop makes `10.43.0.1:443` unreachable and cycles cainjector/flink-operator/ingress-nginx (self-recover, don't tune their probes; mynifi/Kafka ride it out), durable fix = wired link. The base Wi-Fi/NIC fact was in `nvidia-dgx-spark-runbook.md` (one NIC only); the causal chain was absent from CHECKIN. |

## Candidate promotions — dispositions

- **`additive-not-reimport` + `nifi-2x-generator-gotchas` (2 slivers)** → **new issue #319** (nifi-and-ai skill;
  `device:NvidiaSpark-1`, `status:todo`), change plan dropped as a comment. Changes will land here
  (`skills/nifi-and-ai/references/`) and public. No skill execution this session (Steven's steer).
- **`scope-from-the-research-not-the-aside`, `write-plainly-dont-edit-rules-on-an-aside`** → left unplaced.
  Both are planning/writing lessons; per #310 a lesson is not a memory and not automatically a doc edit —
  delete-and-wait-for-recurrence (content preserved in the backup). Flagged in the #313 comment.

## Report (procedure step 3)

- **Model pin:** `~/.claude/settings.json` `"model": "claude-fable-5-1[1m]"` (Steven-set; 1M-context tier).
  Canonical base is `claude-opus-4-8` (`agent/workflow.md` §"Model, effort & context hygiene"). No override
  in a `settings.local.json` — none exists on this box.
- **Un-pushed clones:** none (the procedure's `find ~ -maxdepth 2 -name .git` scan found no un-pushed commits).
- **Local-only hooks / skills / agents:** none. `~/.claude/hooks/` is empty (hooks run from the repo's
  `.claude/hooks/`, including the spark-dd06-guarded `kb-retrieve.sh` / `compress-advise.sh`); installed skills
  `align`, `nifi-and-ai` match `skills/`.
