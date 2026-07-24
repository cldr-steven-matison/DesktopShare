# Canvas layout & arrangement

The canonical home for the layout technique — the NiFi REST API build path (`flow-api.md`) and the EFM Designer API build path (`minifi-efm.md`) both point here, because both produce the same problem: a functionally-correct flow that's visually rough. Processors land wherever the call's `position` said, connections cross, and it reads nothing like a hand-laid flow.

**Read this first, because it sets the honesty bar:** the technique below gets a build *close* to hand-laid, but it does **not** eliminate the manual align/tidy pass in the Designer or NiFi UI. Even with role-matched columns and consistent rows, connections still cross and it won't look finished. Don't claim a build is visually done — say what it functionally does, and expect (or explicitly ask about) a cleanup pass.

Real example, 2026-07-23/24: the `WatchlistChatJoiner` PG was built with role-matched columns and consistent row spacing, and Steven *still* did a "processor sliding and human cleanup" pass afterward — good coordinates alone are not enough.

### Coordinate model (same for both build paths)

NiFi canvas and EFM Designer share one position model: each component has `position:{x, y}`, origin **top-left**, +x right, **+y down**. A flow reads **top-to-bottom** — source at the top (lowest, sometimes negative y), sinks at the bottom. So the technique here is identical whether you're building via the NiFi REST API or the EFM Designer API.

### Grounded constants

These are read off real hand-tidied flows in `DesktopShare/files/`, not invented — re-derive with `jq '.. | objects | select(has("processors")) | .processors[] | {name, x:.position.x, y:.position.y}'` if in doubt:

- **Row pitch (one stage to the next): 200 default**, down to **150** for dense flows. `TwitchChatBot.json` steps 200 (y = 0, 200, 400, 600); `StreamersApp.json`'s live-check subchain steps 150 (600 → 750 → 900 → 1050 → 1200).
- **Center column: x = 0.** The spine of a linear chain sits at x = 0.
- **Branch column pitch: ~300 (dense) to ~480 (roomy).** `StreamersApp` Twitch-vs-Kick split sits at x = −300 / +300; `TwitchChatBot`'s three-way fan-out sits at −488 / 0 / 480.

### Per-shape placement rules

- **Linear chain** — same x, `y += 200` each step. (`TwitchChatListener` 0,0 → `RouteOnAttribute` 0,200 → …)
- **Branch / fan-out** (a `RouteOnAttribute`/`RouteOnContent` feeding N targets) — router stays at center; the N targets **share one row** (`y = router.y + 200`) and spread symmetric `x = center ± pitch`. Odd count keeps one target on center (−pitch, 0, +pitch); even count straddles (−pitch/2, +pitch/2 or ±pitch).
- **Join / merge** (funnel, or several branches into one processor) — the merge target sits at center **x = 0**, one row below the lowest branch row.
- **Self-loop** (e.g. `Retry` self-loop on `InvokeHTTP`, rule 7) — leave the processor where it is; the loop renders as a small bend, no new column needed. Route the terminal `Failure`/`No Retry` to a log processor one row down — exactly what `TwitchChatBot` does with `LogInvokeFailure` at (0, 600).
- **Pre-source timers** (a `GenerateFlowFile` timer or roster fetch ahead of the real source) — negative y, above the source (`StreamersApp`: `PollTimer` at y = −264, `GetRoster` at −120).

### Deriving from a live flow (the precise "match the existing column")

When you're adding to a flow that already exists, don't pick fresh numbers — inherit them. This is rule 1 (live state is truth) applied to layout:

1. Dump the live flow and read `position.x` grouped by processor role/type — the flow already has a de-facto column layout (all `ListenHTTP`s at one x, all `InvokeHTTP`s at another).
2. Reuse that role's x for your new processor of the same role.
3. Set y to the next free row below the existing chain.

### Worked example

A `ListenHTTP → EvaluateJsonPath → RouteOnAttribute → {InvokeA, InvokeB} → LogFailure`, using the constants above (mirrors the real `TwitchChatBot` shape):

```
ListenHTTP         (0,   0)
EvaluateJsonPath   (0,   200)
RouteOnAttribute   (0,   400)
InvokeA  (-300, 600)      InvokeB  (300, 600)     ← branch row, symmetric ±300
LogFailure         (0,   800)                     ← merge, back on center
```

## Other human-pass gaps

Layout is the biggest thing a programmatic build gets functionally-right-but-not-done, but it isn't the only one. This is the running list of everything else Steven has had to clean up by hand after an API build — read it before claiming a build is "finished," and add to it the next time something new turns up.

- _(nothing else logged yet — add the next one here)_
