# Plan — Widen the #295 "sweep surfaces" rule to every linked surface

**Issue:** #325 · **Device:** FTF3XR2065 · **State:** plan-only. Evals run on the logical changes below before any execution.

## Context

The #295 humanization pass rewrote all 21 EFM guide chapters but left `EdgeFlowManager/README.md` stale — Steven caught it, not the session. That failure produced the rule **"Touch an asset, sweep all three surfaces"** (`agent/workflow.md`, commit `171f6a4`). The rule is written EFM-guide-specific: it names three surfaces (plan doc, tracker, `EdgeFlowManager/README.md`) and carries one generalizing sentence.

The #320 pass exposed the same class of miss one layer out: it field-validated sixteen Nvidia-guide chapters and updated the tracker, but left the chapter *files* empty — so the guide a reader opens shows none of the work. The **published files themselves are a surface too**, and neither guide's rule names them (#242 bottom comment).

Steven's ask: go back into the #295 rule and **widen it to be inclusive** — cover the guide-chapters surface, and generalize to the broader pattern where work here has counterparts elsewhere (public repos or other in-repo surfaces) that must move in the same pass.

## Decided scope

Generalize the rule to "sweep **every** linked surface" (count-agnostic). Name every linkage family, each **pointing to its existing canon** — not restated, because the rule-canon discipline (`agent/incident-rules.md` §"Rule canon") forbids drift-prone copies (the #247 failure). No bespoke per-repo rules; no executing stale mirror sweeps. Land as this issue's finish ritual once evals pass.

Editing this rule touches exactly its own four linked surfaces — the change is self-demonstrating.

## The linkage landscape (from exploration)

Already ruled, currently scattered:

| Family | Surfaces that move together | Existing canon |
|---|---|---|
| Guide work (EFM, Nvidia Spark) | plan/subplan doc · status tracker (row + work-stream row + status paragraph + Completion Summary counts) · public README · **the chapter files themselves** | `agent/workflow.md` (this rule) + `device-comms.md` §"Working an issue" step 4 |
| App repo (cso-operator-app) | code · checked-in flow exports · DesktopShare source doc · README | `cso-operator-app/CLAUDE.md` |
| Skill | source in `skills/` · public `NiFiandAi` mirror (manual `publish-skill.sh`) | `skills/README.md` |
| Blog post | `DesktopShare/blog/` draft · `cldr-steven-matison.github.io` live post + assets | `agent/workflow.md` §"Publishing a blog post end-to-end" |
| AMOLED app | app package · its `backend/`, both in the per-app leader repo | `device-comms.md` §"Closing an issue" |

Two genuine gaps stay **out of scope** per the decision — the playground repos (`ClouderaStreamingOperators`, `NiFi2-Processor-Playground`, `MiNiFi-Kubernetes-Playground`, no CLAUDE.md) and the public `edge-flow-manager-mcp-server`. The generalized rule covers them by shape without bespoke rows.

## The four edits (this rule's own linked surfaces)

Canon lives in `agent/workflow.md` only — confirmed `agent/subagent-rules.md` does **not** carry this rule.

### Edit 1 — `agent/workflow.md`: rewrite the canonical section

Rename `### Touch an asset, sweep all three surfaces` → `### Touch an asset, sweep every linked surface`. Proposed replacement body:

> **Whenever you change an asset that has counterparts elsewhere — a status tracker, a plan doc, a public repo, the published files themselves — you update every linked surface in the same pass, before you report the work done.** Not just the one you were looking at. Steven should never be the one who notices a surface went stale. An asset and its linked surfaces are one unit of work.
>
> A "linked surface" is any place the same work also has to show up — here in this repo or out in a public one. The families we have, each with its own mechanics (pointed to, not restated here):
>
> | Family | The surfaces that move together | Canon for the mechanics |
> |---|---|---|
> | Guide work (EFM, Nvidia Spark) | the plan/subplan doc · the status tracker (row + work-stream row + status paragraph + Completion Summary counts) · the public README · **the chapter files themselves** | this section + `device-comms.md` §"Working an issue" step 4; trackers `Complete Guide to Edge Flow Management.md` and `Complete Developer Guide for Nvidia Spark with Cloudera.md` |
> | App repo (cso-operator-app) | the code · the checked-in flow exports · the DesktopShare source doc · its README | `cso-operator-app/CLAUDE.md` |
> | Skill | the source in `skills/` · the public `NiFiandAi` mirror (manual `publish-skill.sh`) | `skills/README.md` |
> | Blog post | the `DesktopShare/blog/` draft · the `cldr-steven-matison.github.io` live post + assets | §"Publishing a blog post end-to-end" |
> | AMOLED app | the app package · its `backend/` — both in the per-app leader repo | `device-comms.md` §"Closing an issue" |
>
> The public README and any published chapter are themselves outbound prose — `writing-style.md` §"The blog-voice band" applies. The tracker is the live chapter↔issue correlation; keep its **Issues** column linked to the driving issue(s).
>
> This is a rule because it failed. The #295 humanization pass rewrote all 21 EFM guide chapters and never opened `EdgeFlowManager/README.md`, the guide's front door — it scored worse than any chapter (em-dash 58.8/k, proof 17.2/k, colon 63.1/k) and only got caught because Steven asked. The same audit found a month-old Completion Summary and a chapter still 🟡 after he'd cleared it. Then #320 field-validated sixteen Nvidia chapters and updated the tracker but left the chapter files empty — the *published files are a surface too*. A pass that stops at the artifact it was editing is not finished.

### Edit 2 — `CLAUDE.md` (root, summary bullet, ~line 35)

Generalize and fix the section pointer. Proposed:

> - **Touch an asset and you sweep every linked surface in the same pass** — its plan doc, its status tracker, its public README, and the published files themselves — here and in any public repo (guide incl. the chapter files, app repo, skill→NiFiandAi, blog→live site, AMOLED leader repo), before reporting the work done, not just the artifact you were editing. Canon: `agent/workflow.md` §"Touch an asset, sweep every linked surface" (#295 left `EdgeFlowManager/README.md` stale; #320 updated the Nvidia tracker but left the chapter files empty).

Stays one summary line pointing to canon — the families table is **not** restated here.

### Edit 3 — `agent/incident-rules.md` (rule-canon row)

> `| Touch an asset → sweep every linked surface (plan doc, tracker, public README, the published files themselves) in the same pass — here or in any public repo | `workflow.md` §"Touch an asset, sweep every linked surface" | known-patterns `linked-surfaces` |`

### Edit 4 — `agent/known-patterns.tsv` (row, tab-separated)

Rename trigger `guide-assets` → `linked-surfaces`; widen the regex to also match the Nvidia guide; update pointer files and description. Proposed row (tabs between the four fields):

- **name:** `linked-surfaces`
- **regex:** `ch[0-9]{2}-.*\.md|EdgeFlowManager|Complete Guide to Edge Flow|Complete Developer Guide for Nvidia|nvidia-spark-guide|efm-guide-.*plan|nvidia-dgx-spark-.*plan`
- **pointers:** `agent/workflow.md,Complete Guide to Edge Flow Management.md,Complete Developer Guide for Nvidia Spark with Cloudera.md`
- **description:** `Changing an asset with linked surfaces is not done until every linked surface moves in the same pass — plan doc, status tracker (row + work-stream row + status paragraph + Completion Summary counts), the public README AND the published files themselves (guide chapters, app code, skill mirror). #295 left EdgeFlowManager/README.md out of band; #320 updated the Nvidia tracker but left the chapter files empty. Canon: agent/workflow.md §"Touch an asset, sweep every linked surface".`

## Landing (finish ritual, after evals pass)

Make the four edits · commit (plain local git user — **no** `Co-Authored-By` / `Claude-Session` trailers) · push · comment on #325 with the commit sha · set `status:review`. Do **not** close — Steven reviews. No memory writes; no unrequested changes.

## Verification

- `grep -rn "sweep all three surfaces\|guide-assets" agent/ CLAUDE.md` → returns nothing (all pointers renamed).
- `grep -rn "sweep every linked surface\|linked-surfaces" agent/ CLAUDE.md` → hits in all four spots, consistently.
- Widened trigger regex matches both guides — test against `files/nvidia-spark-guide/ch09-cso-operators-on-aarch64.md` and an EFM chapter path.
- Re-read the rewritten `workflow.md` section end-to-end: every family row points to a canon location that exists.
- Confirm the four edited files are exactly this rule's own linked surfaces (self-consistency check).
