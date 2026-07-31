# Enforcement-layer audit — the claim-skip pattern and the guard hook (issue #51)

**FTF3XR2065, 2026-07-31.** Requested in [#51](https://github.com/cldr-steven-matison/DesktopShare/issues/51):
after the 7th claim-skip incident, audit the whole enforcement layer (`.claude/` hooks + settings,
`agent/*.md`, `skills/`) *before* writing an 8th point-patch — enumerate what each mechanism
actually catches vs. what it was built to catch, find drift and coverage gaps, and assess whether
per-command regex-in-bash guards are the right layer at all. **This is the audit, not a fix.** No
`.claude/` file was changed in this pass.

## TL;DR

The `head -1` regex bug is real but it is the *shallowest* of **three independent reasons** the
claim guard failed, and fixing only it would leave the other two intact — which is exactly how the
last six patches went. The deepest problem is architectural: the guard uses a PreToolUse
`permissionDecision: "ask"` to try to change the **model's** behavior, but an `"ask"` reason
**never reaches the model** and, under a low-friction permission mode, the `"ask"` can be
auto-resolved with no human in the loop at all. On top of that, `Bash(gh issue *)` and `Bash(git *)`
are on the settings **allow-list**, which is a second, competing enforcement system that the guard
doesn't know about. So the guard hook is being asked to do two different jobs, and it is the wrong
tool for one of them.

---

## Part 1 — Every enforcement mechanism, what it catches vs. what it was meant to catch

| # | Mechanism (file:line) | Meant to catch | Actually catches | Gap |
|---|---|---|---|---|
| checkin | `checkin.sh` | pull, skill-sync, inbox list, CLAIM-FIRST banner | all of it runs at session start | banner has 6+ reps of proven-ineffective nagging; Steven has ordered it removed (not yet landed — still `checkin.sh:75-86`) |
| A | `guard.sh:147` claim-on-view | opening a still-todo issue for this device → ask to claim, record N in marker | **only the FIRST `gh issue view N` in a chained command** (`head -1`, L148) | the confirmed #51 bug; #48/#43/#28/#44 never tripped it |
| B | `guard.sh:60` edit-while-pending | Edit/Write while marker non-empty → ask to claim | works, but only for issues rule A managed to record — so it inherits A's truncation | a chained-view session that edits still only gets nagged about issue #1 |
| 1 | `guard.sh:93` redeploy/restart | `deploy.sh`/`rollout restart`/`kubectl delete pod` → ask | fires; command shapes NOT allow-listed, so the ask surfaces | brittle to unseen shapes (`kubectl scale`, `helm upgrade`, editing a Deployment) |
| 2 | `guard.sh:98` commit/push | `git commit`/`git push` → ask "was this asked for?" | fires — **but `Bash(git *)`, `Bash(git push *)`, `Bash(git commit -m ' *)` are all allow-listed** | the ask is subject to the same swallow as rule A (see Part 2) |
| 3 | `guard.sh:106` port-forward/tunnel | ad-hoc `kubectl port-forward`/`minikube tunnel\|service` | fires; not allow-listed | brittle to shapes (a script that forwards, a different tool) |
| 4 | `guard.sh:116` todo→review jump | marking review/done while still todo | fires — **but also `head -1` (L119)**, so a chained `gh issue edit` only checks issue #1 | same truncation bug as A, unflagged in #51 |
| 5 | `guard.sh:137` layout self-check | `/processors` write carrying `position` → state shape+pitch vs layout.md | fires on POST/PUT to /processors with position | narrow: an API build that omits `position`, or the JSON-import one-shot, bypasses it |
| clear | `guard.sh:77` claim-clear | running the claim command removes N from marker | **`head -1` (L79)** — clears only the first issue if a claim command names several | third instance of the same bug |
| lib | `lib-device.sh` | host→label map, marker path | correct | — |

**Finding 1a.** The `head -1` truncation is not one bug — it is at **three** sites (`guard.sh:79, 119,
148`), because "extract the issue number(s) from `$cmd`" was copy-pasted three times and each copy
truncates. There is no shared helper. #51 flagged only line 148.

**Finding 1b.** Rules A, B, 2, 4 are all gh/git-command-based, and gh/git are broadly allow-listed
(Part 2). Rules 1, 3, 5 are the only ones whose guarded command shapes are *not* allow-listed, so
they are the only ones that reliably surface today.

---

## Part 2 — The three independent failure layers behind this one skip

Ordered shallow → deep. The last six patches all lived at layer 1.

**Layer 1 — regex truncation (`head -1`).** The model batches many `gh issue view N` calls into one
Bash string (`view 49; …; view 48; …`). `head -1` sees only `49`. Fixable by extracting *all*
matches and looping. But fixing it alone assumes layers 2–3 work, which they don't.

**Layer 2 — the permission-mode swallow.** A PreToolUse hook returning `"ask"` overrides an
allow-list match **in `default` permission mode** — the guide confirms the hook layer sits above
the allow/ask/deny rules. **But in `auto` (low-friction) mode, an `"ask"` is handed to the auto-mode
classifier, which can auto-approve it with no human prompt.** `Bash(gh issue *)` is allow-listed
(`settings.local.json:39`), and #51 observed that even the two issues that *did* trip the guard
(#49, #46) produced no visible prompt — consistent with the ask being auto-resolved. So the guard's
efficacy depends entirely on a runtime permission mode that nothing in the repo pins or documents.

**Layer 3 — the reason never reaches the model (the deepest).** Per the Claude Code docs
(confirmed via claude-code-guide): `permissionDecisionReason` on an `"ask"` is shown **only in the
user's prompt dialog**. It is **not** injected into the model's context. `"deny"` reasons *do* reach
the model; `"ask"` reasons do not. So the guard is trying to change the **model's** behavior (claim
the issue) with a message the **model never sees** — it only ever reaches a human, and only if a
human prompt actually renders (layer 2). The mechanism was structurally incapable of telling the
actor it is trying to redirect. The field that *does* guarantee model visibility on every call,
regardless of permission outcome, is **`additionalContext`** — which the guard does not use.

The through-line #51's author identified ("a session's first action keeps not being the claim") is
explained by layer 3: the model was never actually told, in-context, to claim. Prose in
device-comms, a session-start banner, and an invisible `"ask"` reason are all things the model
either sees once and forgets or never sees at the decision point.

---

## Part 3 — Coverage gaps found while reading (other prose-only rules)

The #51 ask included "audit `skills/` for the same class of gap — rules stated once that nothing
mechanically checks." Found:

- **GET-then-PUT of a sensitive NiFi property (credential-destroying) — NO mechanical guard.**
  Highest-severity gap. Stated in `agent/incident-rules.md` and `skills/nifi-and-ai/SKILL.md`, has
  burned a real credential, and `guard.sh` has zero coverage for it. Rule 5 (position) might
  incidentally fire on a full-entity PUT that includes `position`, but its message is about layout,
  not the credential mask. A rule this costly should not be prose-only when hazard interlocks exist
  for lesser things.
- **EFM resource-assignment JSON shape** (`minifi-efm.md`: must be `{"resourceIdsToBeAssigned":…}`,
  a bare array is silently swallowed `200 OK`) — prose-only. Lower severity (fails loud-ish).
- **Bearer-vs-cookie 403 and cert-renewal restart** (`flow-api.md`) — prose-only, operational.
- **`align` skill** is advisory by design (user-invoked grilling) — correctly *not* a candidate for
  mechanical enforcement. Noting it so it isn't mistaken for a gap.

---

## Part 4 — Doc/code drift (prose vs. what the hooks actually do)

- **The CLAIM-FIRST banner.** `agent/device-comms.md:79` still describes it as a live feature, and
  Steven has ordered it removed. Removing it from `checkin.sh` without updating device-comms.md §
  "Automated check-in" would create fresh drift. The removal itself is **still pending** —
  `checkin.sh:75-86` still emits it (this session's own start context carried it).
- **Trigger A prose overstates the code.** device-comms.md:84-95 says opening a still-todo issue
  "prompts to claim it first." The code only does this for the *first* issue in a chained command.
  The prose describes the intended behavior; the code delivers a subset. That is drift in the
  direction that hides the bug — the doc reads as if coverage is complete.

---

## Part 5 — Assessment: is per-command regex-in-bash the right enforcement layer?

**The layer is being asked to do two different jobs, and it is right for one and wrong for the other.**

**Job A — hazard interlock** (rules 1, 3, 5, and the missing credential rule): "before this
hard-to-reverse / outward-facing action runs, stop and make a human confirm." A PreToolUse guard
that returns `"ask"` (or `"deny"`) is a *reasonable* fit here, because these actions *should* block
and wait, and a `"deny"` reason *does* reach the model. Regex brittleness is a real cost but a
bounded one: the set of dangerous command shapes is finite and enumerable. **Keep this layer for
hazards** — but harden it: fix the shared extraction bug, add the credential rule, and check that
allow-list entries aren't silently voiding the ones that matter.

**Job B — workflow nudge** (rules A, B, 4, the banner): "make the model claim the issue." This is
the wrong tool:
- Claiming is not dangerous — hard-blocking every `gh issue view` is friction the model learns to
  bulldoze (which is precisely what happened).
- The thing that must change is the *model's* next action, and `"ask"` cannot inform the model.
- It is defeated by both the allow-list and the permission mode.

So the recurring failure is not "the regex was buggy" — it is "a permission gate was used to try to
steer model behavior, and permission gates don't steer model behavior; they gate humans."

### Plan — options for Steven to choose from (no fix applied yet)

**For Job B (the claim nudge) — pick a direction:**

1. **Inject, don't ask.** Switch the claim mechanism from `permissionDecision:"ask"` to emitting
   `additionalContext` (on the `gh issue view` call, or a PostToolUse hook on its result):
   *"You just opened #N, still status:todo for this device. Claim it now: `gh issue edit N …`
   before any further work."* This is the one mechanism guaranteed to reach the model regardless of
   permission mode or allow-list. Low-friction, model-visible, and it fixes the real gap (layer 3).
   Fix the `head -1` extraction as part of this so it covers every issue in the command.
2. **Auto-claim (take it out of the model's hands).** The hook itself runs
   `gh issue edit N --add-label status:in-progress` when it sees this device open a still-todo
   issue. Eliminates the human/model dependency entirely. Trade-off: opening an issue to *read* it
   now claims it — needs a deliberate "just looking" escape, and it makes the hook mutate remote
   state, which is a bigger behavior to trust. Present as the aggressive option.
3. **Both:** auto-claim + an `additionalContext` line telling the model it was auto-claimed, so the
   model's mental model stays in sync with the label.

Recommendation: **option 1** as the default (smallest trust surface, directly fixes layer 3), with
option 2 held in reserve if injection still doesn't stick.

**For Job A (hazards) — do regardless of the Job B choice:**

- Factor the issue-number extraction into one `lib-device.sh` helper that returns *all* matches;
  call it at all three sites (`guard.sh:79, 119, 148`). Kills the bug class, not the instance.
- Add the **GET-then-PUT sensitive-property** guard (a full-entity PUT to `/processors/…` whose body
  is not a `/run-status` narrow call and not parameter-context-bound) as a `"deny"`-with-reason or
  `"ask"` — this one genuinely should reach the model, and `"deny"` reasons do.
- Reconcile the **allow-list vs. guard** conflict: decide, per guarded action, whether the
  allow-list entry should exist at all. `Bash(git *)` almost certainly voids rule 2 in low-friction
  mode; if commit/push discipline matters, that entry is working against it.
- **Pin/verify the permission mode.** The guard only works in `default` mode. If sessions run in an
  auto/low-friction mode, document that hazard interlocks are *not* reliably enforced there, or
  switch hazard rules to `"deny"` (which survives better and reaches the model).

**Then update the docs in the same pass** so device-comms.md matches whatever lands (banner removal,
the new claim mechanism, the honest description of what each guard actually covers). The drift in
Part 4 is itself part of why the pattern persisted — the prose read as if the machinery worked.

---

---

## Completeness review (2026-07-31 follow-up)

Before implementing, the enforcement surface was swept end-to-end to confirm a hook fix can even
reach the failure path:

- **The whole surface is two hooks**, both project-local in DesktopShare: `checkin.sh` (SessionStart)
  + `guard.sh` (PreToolUse). **No global hooks** (`~/.claude/settings.json` defines none — only
  theme/plugins/attribution), no `PostToolUse`/`Stop`/`SubagentStop`, and no per-repo enforcement
  elsewhere (`cso-operator-app` has no `.claude`). Nothing hidden; what git ships is the mechanism.
- **PreToolUse fires in plan mode** (input carries `permission_mode: "plan"`) and **fires inside
  subagents** (input carries `agent_id`), using the same `settings.json` config. So the WindowsDesktop
  `/plan` that opened six issues *did* run the guard on every `gh issue view` — it truncated
  (`head -1`) and its `ask` was invisible/swallowed; the hook did not fail to fire. A hook fix
  therefore can catch this path. (Confirmed via claude-code-guide against code.claude.com/docs.)
- **SessionStart context does NOT reach subagents** — which is why the CLAIM-FIRST banner was doubly
  useless: a subagent reading issues never saw it. This is decisive evidence for retiring the banner
  and moving the enforcement into the always-firing PreToolUse layer.
- One documented hook gap (`EndConversation` skips PreToolUse) is irrelevant — `gh issue view` goes
  through Bash.

## Resolution — what was implemented (2026-07-31, this pass)

Per Steven's call (auto-claim, because every model-cooperation approach can be ignored by
definition):

- **`guard.sh` Rule A is now auto-claim.** On `gh issue view <n>` of a still-`todo` issue for this
  device, the hook runs `gh issue edit … status:in-progress` **itself** and emits `additionalContext`
  informing the model. No prompt, no model decision — verified end-to-end (a real todo issue flipped
  on open, then restored). Falls back to marker+ask only if the `gh edit` fails.
- **The `head -1` bug is killed at the root**: a single `ds_issue_numbers` helper in `lib-device.sh`
  extracts *every* issue number, called at all three former truncation sites (auto-claim, the
  todo→review backstop, and claim-clear). Verified it returns all issues from a chained command.
- **The CLAIM-FIRST banner is removed** from `checkin.sh` (inbox listing kept); the header comment
  records why.
- **Hazard rules 1/2/3/5 are unchanged** (still `ask`) — deliberately not touched this pass.
- **Docs synced**: `agent/device-comms.md` "Automated check-in" and "Working an issue" now describe
  auto-claim instead of the banner + ask.
- **Deferred (NOT done this pass — flagged for a separate decision):** the missing GET-then-PUT
  sensitive-property credential guard (Part 3); the allow-list-vs-guard conflict where `Bash(git *)`
  likely voids rule 2 (Part 2/5); pinning/documenting the permission mode. These are real but out of
  scope for the claim-skip fix Steven approved.
- **Local housekeeping (this Mac only, not committed — gitignored):** removed a stale
  `.claude/skills/nifi-and-ai/` copy (Jul 23) that differed from the current synced skill (Jul 27), a
  latent stale-shadow trap.

*Source read this session: `guard.sh`, `checkin.sh`, `lib-device.sh`, `settings.json`,
`settings.local.json`, `sync-skills.sh`, `agent/{device-comms,workflow,incident-rules}.md`, `skills/`,
global `~/.claude/settings.json`. Hook/permission/subagent precedence confirmed against
code.claude.com/docs (hooks, permissions).*
