# Memory ledger — TunaStarlink (StarlinkAI), 2026-09-09 (#313 / #310)

Every memory file in the silos on this device (Beelink SER9 MAX H260, StarlinkAI), read in full and
classified per `agent/local-repo-unification.md`. **Class:** `dup` = already held by the repo (owner
named) → deleted · `promote` = held only here → written into the owner (CHECKIN block / a repo doc) then
deleted · `candidate` = a lesson/feedback the policy bars as a memory; **not** promoted this pass per the
minimize-churn steer (FTF3XR2065 ledger) — flagged here for Steven's ruling, memory deleted (content in
the backup and, for the crash lessons, embodied in the promoted doc).

Backup of the pre-sweep state (all 6 files, not committed — memories can quote Steven; repo is public):
`~/.claude/backups/memory-optimize-2026-09-09-143259.tgz`.

**Counts:** Brainshare silo (`-home-tunas-Brainshare`) 1 → 0 · home-dir silo (`-home-tunas`) 5 → 0 ·
old-path silo (`-home-tunas-DesktopShare`) 0 → 0 (already migrated in the #288 sweep, per CHECKIN
"Repo homes"). **Net: 2 `dup`, 2 `promote`, 2 `candidate`, 0 survivors.** StarlinkAI's real device facts
already live in its `CLAUDE-CHECKIN.md` block; the two genuine device facts missing from it were promoted
there this pass, so zero survivors is the honest result — the same shape the WindowsDesktop app-dir/home
silos and the FTF3XR2065 planning Mac reached.

## Silo `-home-tunas-Brainshare` (1 → 0)

| memory | class | owner / where the repo holds it |
|---|---|---|
| project-starlinkai-wsl2-networking | dup | `CLAUDE-CHECKIN.md` StarlinkAI block (line ~103) already holds the canonical facts: WSL2 `mirrored` mode, `.wslconfig` `[wsl2] networkingMode=mirrored`, the `wsl --shutdown`-to-apply requirement, and `wslinfo --networking-mode` to verify. The memory's residual "check networking-mode FIRST when a call fails" heuristic + powershell.exe-interop-scope are debugging residue, not device facts — covered by that block + `CLAUDE.md` "Live state outranks docs". Had no `approved:` line (lint HARD). |

## Silo `-home-tunas` (home-dir default project) (5 → 0)

| memory | class | owner / where the repo holds it |
|---|---|---|
| petru-now-playing-hack | dup | repo doc `petru-now-playing-hack.md` (20 KB, full house-style write-up) + assets `files/petru-now-playing-hack/`. The memory names that doc as canonical; a blog post is planned from it. |
| azw-ser-front-usbc-power-only | promote | Genuine device hardware quirk, absent from the repo → **promoted** to `CLAUDE-CHECKIN.md` StarlinkAI **Hardware** block (front USB-C power-only; use rear USB4 for data). |
| project-tunastarlink-dpc-crashes | promote | 293-line narrative — barred as a memory (policy: "never a narrative"), but holds a WinDbg-confirmed root cause. **Promoted** to a new repo doc `starlinkai-dpc-crash-investigation.md` (Type A `amdgpio2.sys` 2.2.0.137 → rollback fix, confirmed; Type B no-bugcheck resets, open) + a terse operational entry in `CLAUDE-CHECKIN.md` StarlinkAI **OS** block. |
| feedback-recurring-investigation-discipline | candidate | `type: feedback` (barred; lint HARD). Lesson: on a multi-session investigation, re-read the full doc and cross-check every "next step" against the ruled-out list before proposing it. Overlaps `CLAUDE.md` "Don't over-claim"; embodied in the promoted crash doc's "Investigation discipline" section. Candidate for a sharper `incident-rules.md` entry — **Steven's call**, not promoted this pass. |
| feedback-verify-crash-signature-before-claiming-same | candidate | `type: feedback` (barred; lint HARD). Lesson: never say "same crash / fixed" without pulling the actual `BugcheckCode` from that event (~15 rounds of confident wrong root causes burned trust). Overlaps `CLAUDE.md` "Don't over-claim"; the crash doc's Type A/Type B split is its concrete embodiment. Candidate for `incident-rules.md` — **Steven's call**. |

## Silo `-home-tunas-DesktopShare` (0 → 0)

Empty memory dir — the stranded old-path silo left by the `DesktopShare → Brainshare` local rename was
already migrated into the Brainshare silo during the #288 sweep (per `CLAUDE-CHECKIN.md` → StarlinkAI
"Repo homes on this host"). Nothing to classify; no `MEMORY.md` present.

## Candidate promotions — Steven's call (nothing edited into agent docs this pass)

Both are `type: feedback` crash-investigation trust lessons. They are already **largely covered** by the
`CLAUDE.md` universal rule "Don't over-claim — state plainly what happened," and their concrete method is
now written into `starlinkai-dpc-crash-investigation.md`. If Steven wants them sharper than the universal
rule, the home is one `incident-rules.md` entry (cause → check): *"On a long multi-session hardware
investigation, read the whole tracking doc and pull the actual bugcheck/dump for the event before
claiming 'same' or 'fixed' or proposing a next step — re-litigating ruled-out ground reads as not
listening."* Not created this pass to minimize repo churn.
