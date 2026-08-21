# Cloudera Racing — two game-balance findings from kiosk/bot play

Found while running an automated player against a hardware port of the game — a 368×448 AMOLED
panel that reimplements these rules natively and shares the same leaderboard and telemetry
pipeline as the browser game. Filing both together, since the second one also blunts the first
from a different angle.

Our deployment is a clone of this repo, running on Kubernetes with only the nginx upstream, the
Kafka bootstrap and the k8s manifests changed — the game itself is byte-identical to HEAD
(`git status` clean, `git log --oneline -3` showing the single commit `00888b4 Cloudera Racing
Standalone`). Nothing here describes a fork's behaviour; it is this repo's code, unmodified, and
we are deliberately not patching our copy — these are proposals for this repo, not a local fix.

**How this was measured:** an automated player — not a human — drove the panel port, which applies
these rules unchanged, for 20 minutes per run. So this is a kiosk/bot-fairness and
shared-leaderboard issue rather than a human-play complaint: a person can't reliably take every
iceberg for twenty minutes, and a bot can. That's exactly the gap these two findings expose.

---

## 1. The Iceberg power-up can pin difficulty at Lv.1

**Observed:** past 3,000 points, the Iceberg power-up spawns (~18% of obstacles — `spawnObs()`,
`services/game/index.html:443`: `if(score>=ICEBERG_MIN&&rng<0.18){type='iceberg';...}`). Picking one
up both scores points *and* lowers the speed level:

```js
// services/game/index.html:424-431
if(type==='iceberg'){
  if(speedLevel>1){speedLevel--;baseKmh=Math.max(60,baseKmh-20);}
  boostCd=BOOST_SEC;
  document.getElementById('spd-lv').textContent='Lv.'+speedLevel+' · '+baseKmh+' km/h';
  document.getElementById('spd-fill').style.width='0%';
  document.getElementById('spd-wrap').classList.add('slow-flash');
  setTimeout(()=>document.getElementById('spd-wrap').classList.remove('slow-flash'),1100);
  score+=200;toast('🧊 Iceberg! Speed cooled · +200 pts');sendTelemetry(updateMetrics(),'powerup_iceberg');
}
```

The speed ramp itself is `services/game/index.html:396`: every `BOOST_SEC` (15s),
`speedLevel++;baseKmh+=20;`.

Because the iceberg is worth chasing (+200) *and* it undoes the ramp, a player who reliably takes
every one holds the game at Lv.1 indefinitely. The ramp is fine on its own — a player who dodges
icebergs climbs normally. It's the combination that breaks:

| Bot behavior | Duration | Score | Lives lost | Result |
|---|---|---|---|---|
| Take every iceberg | 20 min | 44,860 | 0 | still Lv.1 |
| Dodge every iceberg | 20 min | 32,050 | — | Lv.81 / 1,660 km/h |

Since browser and kiosk/panel players share one leaderboard, a score built by iceberg-farming isn't
comparable to one that actually survived the ramp — the farmed run is both higher-scoring and
zero-risk.

### Options considered

1. **Floor the reduction** — an iceberg can drop `speedLevel` at most N levels below the peak level
   reached this run. Farming icebergs stops being able to reset difficulty to 1; it can only walk
   the level back down to a floor near the run's own high-water mark. Keeps the +200 bonus and the
   "cooled" visual/toast exactly as-is.
2. One-shot per level, or put the iceberg pickup on its own cooldown.
3. Keep the score bonus, drop the speed reduction — a pure points pickup, no difficulty interaction.
4. Cap total icebergs per run.

**Recommended: option 1 (floor the reduction).** It's the smallest change — one new state variable
(`peakLevel`, tracking the run's highest `speedLevel`) and one comparison changed from `speedLevel>1`
to `speedLevel>Math.max(1,peakLevel-ICEBERG_FLOOR)`. It preserves every part of the pickup a player
already expects (points, cooldown reset, "cooled" flash/toast) and only changes how far down the
speed can go. Option 3 removes a mechanic players like (the visible "cooled" moment); option 2 and 4
add new UI/cooldown surfaces to explain. Floor-the-reduction is invisible to a player who isn't
farming and closes the exploit for one who is.

Patch: `iceberg-balance.patch` (this directory). Adds `ICEBERG_FLOOR=3` (an iceberg can't push you
more than 3 levels below your peak) alongside the existing constants, a `peakLevel` state variable
updated at the same site the ramp increments `speedLevel`, and the one-line floor check at the
pickup site. Five lines changed, no new UI, no reformatting.

**What our AMOLED port would do:** nothing — it runs whatever `services/game/index.html` upstream
ships. If this lands upstream, the panel port picks it up on the next image rebuild with no port-side
changes.

---

## 2. There is no finish line

Steven's question watching the panel port: *"at a high score level the game goes back into speed
1 — is there a finish line instead?"*

**Observed:** there isn't one. `endGame()` (`services/game/index.html:520`) has exactly one call
site: `if(collisions>=MAX_LIVES)endGame();` at line 434. The game is endless survival — a run ends
only when the player has lost all 3 Datahero lives. Achievements top out at 12,000 points ("Data
Hero"), but nothing concludes a race; score is mostly a function of how long you can keep from
crashing, not how well you play a fixed course.

This also matters for #1 from the other direction: on a fixed course, farming icebergs to stay slow
would cost time against the clock instead of buying an endless, zero-risk run. A finish line and the
iceberg floor fix are complementary, not redundant — either helps, together they close the exploit
from both sides.

### Shapes considered

1. **Distance course** — finish at N metres/obstacles; score = points, tiebreak on time.
2. **Timed sprint** — fixed duration (e.g. 90s), highest score wins; every turn is the same length.
3. **Lap mode** — N laps with a lap counter, closest to a literal "racing" framing.
4. Keep endless as a mode toggle so today's behavior isn't lost.

**Recommended: option 2 (timed sprint), as an opt-in mode, with option 4's toggle to preserve the
current endless default.** The game already tracks wall-clock `elapsed` in whole seconds
(`services/game/index.html:390`, `elapsed++` inside the existing 1s `clockLoop`) and already prints
it to the HUD clock and to the telemetry payload's `elapsed_sec`. A timed sprint reuses that clock
directly — check `elapsed>=FINISH_SEC` in the same interval that already increments it. A distance
course would need a new "distance traveled" accumulator decoupled from the obstacle-scroll pixel math
(obstacles move by `speedLevel`-scaled pixels per 16ms tick, not by a real distance unit), and a lap
mode needs a full course/waypoint concept the game doesn't have at all. Timed sprint is the smallest
change that gives every player the same race length and a run that ends on its own — which is exactly
what a booth/demo setting needs.

Patch: `finish-mode.patch` (this directory). Adds a `FINISH_SEC=90` constant, a `finishMode` boolean
set from a new opt-in checkbox on the car-select screen (default unchecked — endless play is
unchanged), a check in the existing clock interval that ends the race and swaps the HUD clock to a
countdown when the mode is on, and an `endGame(reason)` parameter (defaulting to `'game_over'`) so a
timed finish can report its own telemetry event.

**Telemetry:** the metrics POST is built in `updateMetrics()` (`services/game/index.html:470-493`)
and sent by `sendTelemetry(payload, eventType)` (`services/game/index.html:496-505`), which stamps
`event_type` onto the JSON body posted to `/api/metrics`. Today's pipeline sees `heartbeat`,
`collision`, `powerup_iceberg`, and `game_over`. The patch adds a `race_finished` event — same
payload shape, `event_type:'race_finished'` — emitted once when the sprint clock hits zero. This is
the natural next case for a pipeline that already keys off `event_type`; no new fields.

**What our AMOLED port would do:** nothing beyond following whatever this repo ships — like #1, the
panel port runs the shipped `index.html` as-is. If finish-mode lands as an opt-in, the port would
pick it up passively; whether to default it on for the kiosk specifically is a separate, later
decision for whoever operates that panel, not part of this proposal.

---

## Status

Nothing has been sent upstream. This document and the two patches below are proposals only — no
fork, no branch, no PR, no issue on `cldr-jquiroscr/cloudera-racing-standalone`. Filing upstream, and
in what form, is Steven's call.

- `iceberg-balance.patch` — unified diff, `services/game/index.html`, implements option 1 above.
- `finish-mode.patch` — unified diff, `services/game/index.html`, implements option 2 above.

Both were generated by diffing a scratch copy against the untouched clone (`diff -u`), and both were
dry-run verified (`git apply --check` and `patch -p1 --dry-run`) against a fresh copy of the file —
the clone at `/home/tunas/cloudera-racing-standalone` was never edited or written to.
