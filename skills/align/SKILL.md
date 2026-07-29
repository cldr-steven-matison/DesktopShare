---
name: align
description: Grill for unstated assumptions, constraints, and success criteria before starting non-trivial work. Use when the user types /align, or asks to "align", "grill me", "make sure we're on the same page", or "pin down requirements" before planning or implementing — and proactively at the start of any task whose goal, scope, approach, or done-condition is ambiguous.
---

# /align — converge before you build

Most wasted work comes from building confidently against an assumption the user never
actually held. This skill is the deliberate step that surfaces those assumptions *before* a
plan or a diff exists — the cheapest point to catch them. It converges on **what**, **why**,
and **done**; it does not design the **how** (that's plan mode / `ExitPlanMode`, which this
hands off to).

## When to run it

- The user typed `/align`, or asked to be grilled / to nail down requirements before starting.
- A task's goal, scope, or success condition is ambiguous, or there is more than one
  reasonable approach with meaningfully different blast radius.
- **Skip it** for trivial, unambiguous, single-step asks — grilling those is friction, not
  alignment.

## The procedure

1. **Read the ground first, then ask.** Don't grill from zero. Skim the relevant code/docs and
   this repo's `CONTEXT.md` glossary so your questions are informed and use the right shared
   terms. A question you could have answered by reading is noise.
2. **Grill along the axes that actually change the work** — ask only the ones genuinely open:
   - **Goal / why** — the outcome behind the request, not the literal ask. What does success unlock?
   - **Done-condition** — how we'll both know it's finished: the observable/verifiable check.
   - **Scope boundary** — what's explicitly *out*. Name the tempting-but-excluded.
   - **Constraints** — which device/env it must run on, tools allowed, what it must not touch, timing.
   - **Approach forks** — where >1 reasonable path exists, surface the tradeoff and let the user pick.
   - **Live-state / safety** — anything touching a running service, a live posting queue, or
     credentials pulls in `agent/incident-rules.md`; confirm the blast radius up front.

   Use **AskUserQuestion** for discrete forks (faster for the user than prose back-and-forth);
   use plain questions for open-ended ones. Batch related questions — don't dribble them one at
   a time.
3. **Restate the aligned understanding** — crisply, in the repo's shared terms: goal,
   done-condition, scope in/out, constraints, chosen approach. One tight paragraph or short
   list, not a transcript of the Q&A.
4. **Hand off.** For anything needing an implementation strategy, go into plan mode and design
   the *how* — `/align` is the step *before* the plan, not a replacement for it.

## What it is not

- **Not plan mode.** It settles *what / why / done*, not *how*. It feeds plan mode.
- **Not a checkbox interrogation.** Ask what's genuinely open; skip what the request or the code
  already answers. Over-grilling a clear ask is as bad as under-grilling a vague one.
- **Not permission to expand scope.** Surfacing an adjacent improvement is fine; bundling it in
  without an explicit yes is not (`agent/incident-rules.md` — "do exactly what's asked").
