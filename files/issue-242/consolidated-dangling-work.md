## Why this issue exists

> **Update 2026-09-10.** Full pass on the DGX Spark issues: #241 and #294 closed (accepted); runbook B expanded (#233, 7327283); efm-agent.md editorial pass + scrape manifests (#239, 9c95abc) with the cluster-side work handed to WindowsDesktop as #324; reboot survival built (#322, 56c489b/ae3c92c — install pending one root command); plan, tracker and README swept (af7a7c9). Items ticked below carry the sha; decision 2 is answered, decisions 1/3/4/5/6 stay open.


The *Complete Developer Guide for Nvidia Spark with Cloudera* (#242) has real work left on most of its 26 chapters, but that work is scattered across a dozen subplan docs whose parent issues have **mostly closed**. Nobody is tracking the remainder in one place, and several docs still describe their parent issue as "open / in review" when GitHub says otherwise. This issue re-homes every dangling item into a single actionable tracker for the box (`spark-dd06`).

### Docs vs. GitHub reality (2026-09-09)

| Subplan | Issue | GitHub state | The doc still says | Remaining work with no open parent |
|---|---|---|---|---|
| A — landscape | #232 | **CLOSED** | closed | Ch1/4/6 prose; Ch26 (2nd-Spark hardware) |
| C — demos | #234 | **CLOSED** | "in review" | Ch25 prose (4 flows validated 09-08) |
| D — bring-up | #235 | **CLOSED** | "next / Phase 3" | Ch13 §3 e2e + Ch14 Prometheus scrape |
| F — k3s + CSO | #238 | **CLOSED** | "in review" | Ch7–11 prose; §9 cutover ladder |
| H — local AI | #240 | **CLOSED** | "open pending H5" | Ch15 H5 soak verdict; Ch15/16/17 prose |
| I-AWC | #283 | **CLOSED** | open | Ch20/22 `[TO-VERIFY]`, box→goes01 |
| EPIC | #226 | **CLOSED** | "open EPIC" | ~12 chapters still live |

Genuinely still open: **#233 (B, todo)**, **#239 (G, todo)**, **#241 (I, review)**, **#294 (L, review)**. Mac-side and blocked: #284.

> Note: [`nvidia-dgx-spark-efm-agent.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-efm-agent.md)'s status block says *"#239 closed 2026-08-28"* — #239 is actually **open**. That doc needs the fix in §5 below. And the plan/tracker's WS table should be reconciled to the states above in the same pass.

---

## 1. Closed-task orphans — priority (no open parent issue)

These lost their tracking home when the parent closed. Do these first.

- [ ] **Ch13 — §3 use-case end-to-end from a non-Spark device.** Enroll at least one non-Spark edge device in EFM and prove one escalation path to `NvidiaSpark-1` (e.g. Jetson `/classify` low-confidence → `192.168.1.203:8190/classify` VLM second opinion) end-to-end. *(Carried out of #239 into #235 — #235 closed.)*
- [ ] **Ch14 — cluster-side Prometheus scrape.** Wire it: selector-less `Service` + manual `Endpoints` at `192.168.1.203:9936`; `ServiceMonitor` with the `fallbackScrapeProtocol` patch; add the `:9835` host exporter as a second target; add the fleet-board row. Prove `up{job=…}=1` from inside the cluster (busybox `wget` first). *(Carried out of #239 into #235 — #235 closed.)*
- [ ] **Ch15 — record the H5 one-week soak verdict.** The `ds-kb` KB was built 2026-08-27; the one-week soak window has long elapsed but no pass/fail is recorded anywhere. Needs a call (see Decisions). *(#240 closed.)*
- [ ] **Ch7–11 — author prose** for the field-validated k3s/CSO chapters (k3s+GPU, operators on aarch64, SparkLlmBridge, Flink-on-GPU). Substance was validated 2026-08-27; only prose is missing. §9 cutover ladder is planning-only by decision — note it, don't build it. *(#238 closed.)*
- [ ] **Ch25 — author prose** for the demo catalogue. Four on-box EFM+NiFi flows are field-validated with committed exports (source rewritten 2026-09-08); the runnable-catalogue chapter text doesn't exist yet. *(#234 closed.)*
- [ ] **Ch1/4/6 — author prose** from the validated sizing/model-lock/concurrency substance (measured 2026-08-28). *(#232 closed.)*
- [ ] **Ch20/22 — AWC `[TO-VERIFY]` items**, gated on box→`goes01` reachability. Blocked, but the tracking home is gone (#283 closed); relates to #284. *(See Blocked/gated.)*

---

## 2. Per-subplan concrete steps

### B — [`nvidia-dgx-spark-runbook.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-runbook.md) → Ch2, Ch3  (#233, OPEN)
- [x] Expand the runbook narrative: full unbox → DGX OS → network → containers → k3s → roster → endpoints → hardening. The doc's own header says this is "still owed." *done 2026-09-10, 7327283 (#233)*
- [x] Strike the stale pre-arrival `[ ]` checkboxes in §0/§1/§5 (the box is up as `spark-dd06`; the as-built block supersedes them) and drop the retired `:8888`/SGLang/DeepSeek `[ ]` items. *done 2026-09-10, 7327283*
- [ ] Ch2/Ch3 prose can only be authored once B is expanded.

### G — [`nvidia-dgx-spark-efm-agent.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-efm-agent.md) → Ch12, Ch13, Ch14  (#239, OPEN)
- [ ] Ch12 — author prose (class flow v5 validated on-box).
- [ ] Ch13/Ch14 — the two orphan items in §1 above. *→ #324 hand-off (2026-09-10)*
- [x] Editorial cleanup of the source doc — see §5. *done 2026-09-10, 9c95abc*

### H/L — [`nvidia-dgx-spark-local-kb.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-local-kb.md), [`nvidia-dgx-spark-offload.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-offload.md) → Ch15, Ch16, Ch17  (#240 CLOSED / #294 OPEN)
- [ ] Ch15 — H5 soak verdict (§1) + prose.
- [x] Ch16 — resolve the L2 gate (windowed KB adoption ≥ 50% and cache-create trending down over ≥3 rows); record the local-lint outcome; then prose. *L2 accepted as not met (9.4 % adoption vs 50 %), local lint recorded as not moved; #294 closed 2026-09-10*
- [x] Ch17 — lock the offload-share measurement (currently a projection past row 1); then prose. *ledger row 12, 2026-09-10: 7.97 % generation share over 149 sessions; #294 closed*

### C — [`nvidia-dgx-spark-cso-demos.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cso-demos.md) → Ch25  (#234, CLOSED)
- [ ] Author prose (§1 orphan).

### A — [`nvidia-dgx-spark-landscape.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-landscape.md) → Ch1, Ch4, Ch6, Ch26  (#232, CLOSED)
- [ ] Ch1/4/6 — author prose (§1 orphan).
- [ ] Ch26 — hardware-gated (see Blocked).

### F — [`nvidia-dgx-spark-k3s-cso.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-k3s-cso.md) → Ch7–Ch11  (#238, CLOSED)
- [ ] Author prose (§1 orphan). Refresh the stale 08-27 header (§8 was updated 09-06; the "model lock still open" line is wrong — lock closed 08-28).

### I — [`nvidia-dgx-spark-cloudera-aws.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-aws.md) → Ch5, Ch18, Ch19, Ch21, Ch24  (#241, OPEN/review)
- [ ] Field-run each of the three platform paths on AWS (CDP Base CE, CDP Public Cloud, Cloudera AI) against the box as an external OpenAI-compatible client; replace the `# expected — verify on the box` blocks with as-built. Then prose. (Gated on the respective AWS envs — see Blocked.) *(#241 closed 2026-09-10 as design-accepted; the field run stays tracked here)*

### I-AWC — [`nvidia-dgx-spark-cloudera-awc.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-cloudera-awc.md) → Ch20, Ch22  (#283, CLOSED)
- [ ] Establish box→`goes01` reachability, then verify every `[TO-VERIFY]` claim. Then prose. (Gated — see Blocked.)

---

## 3. Blocked / gated — no action until the gate clears

- **Ch23 — Cloudera AI on Data Services.** No source doc, no CDS 1.5.5+ test environment, no scoped work-stream. Fully blocked pending an environment (Decision).
- **Ch26 — multi-Spark (ConnectX-7, NCCL, 1M context).** Gated on a 2nd/3rd/4th DGX Spark unit not yet acquired (Decision).
- **Ch20 / Ch22 — AWC.** Gated on box→`goes01` reachability (relates to #284).
- **Ch5 / Ch18 / Ch19 / Ch21.** Gated on access to the respective Cloudera-on-AWS environments.
- **Ch24 — same-code-N-backends arc.** Gated on at least one of Ch21/Ch22 being field-validated first.

---

## 4. Housekeeping — reconcile docs to issue reality

- [x] Update [`nvidia-dgx-spark-plan.md`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-plan.md) WS table and the tracker so the states match GitHub (A/C/D/F/H/AWC/EPIC closed; B/G/I/L open). *done 2026-09-10, af7a7c9 — plan, tracker and README all match GitHub*
- [ ] Decide the EPIC question (below) and, if kept, point the docs at the live tracker.

---

## 5. efm-agent.md editorial cleanup (folded in per Steven)

`nvidia-dgx-spark-efm-agent.md` feeds Ch12/13/14. It reads as a war-story of Claude figuring things out and over-teaches the Jetson differences. Make it about deploying the EFM agent on *this* aarch64 device — facts only.

**Cut — war-story / session narration:**
- [x] Status block's "how it was designed / design-record" meta-narration (L7).
- [x] Fleet-cutover history with dates — "cut over on that reasoning twice… 2026-08-14…" (L15).
- [x] "tag-list queries all returned no JSON" research-session narration (L21).
- [x] "The Jetson cost a whole debug cycle to a missing JRE" (L23).
- [x] "both already true on WindowsDesktop" (L68); the "As built, 2026-08-27" session-log voice (L70) — keep the facts (install path, bootstrap values, `/efm/api/agents` 404), drop the voice.
- [x] "Measured on this fleet 2026-08-22" per-device byte counts (L80) — keep the 167× ratio + OOM conclusion.
- [x] "cost debug cycles on this fleet" (L86); "all learned the hard way on this fleet" (L164).
- [x] Consolidation build-iteration history / "retrievable from StarlinkAI's flow before building" regret note (L105–116) — keep the canonical router shape.
- [x] "the completeness critic found zero sources… first-of-its-kind" (L198).
- [x] "the diagnostic that proved it is worth repeating" (L218).

**Trim Jetson to only deploy-relevant differences — cut:**
- [x] Fleet cutover history (L15); JRE incident (L23); Jetson port/daemon map in the §2 opener (L90 first sentence); MobileNetV2 4.05 ms / 8× preprocessing detail (L159); `systemctl --user restart trt-infer` example (L161); Jetson p50/p95 sourcing (L170 — keep the "~117 ms agent overhead; GB10 makes the model faster not the agent" conclusion); "Jetson proved the cost" in §7 (L265); "Cluster→Jetson needed zero ufw" precedent (L218); Beelink/Jetson scrape-path list (L218, L280).

**Keep Jetson where it carries a real difference:** architectural lineage (L9), aarch64 tarball proven (L21), "the Jetson shape exactly" deploy confirmation (L70), display-vs-inference cargo (L90 2nd sentence), model-lives-in-resident-process rule (L161, cut the example), escalation use case (L180/L198), Linux-generic exporter reused verbatim (L206, L213), don't-push-large-binaries-through-EFM principle (L248).

**Also:**
- [x] Refresh the stale `Status (2026-08-28)` header to current; fix "#239 closed 2026-08-28" (it's open).
- [x] Strike the stale "model lock still open" open question (L276 — lock closed 08-28) and the answered VLM/Whisper items where locked.
- [x] Convert the "When this ships" section (L296–300) to as-built.

---

## Decisions needed from Steven (surface, not invent)

1. **H5 soak** (Ch15): pass or fail? The window elapsed with no verdict recorded. *2026-09-10: no data was ever logged — see #242 comment; a ledger has to exist before this can be called.*
2. **L2/L4 offload gates** (#294): accept "not met" as the finding, or keep soaking? **Answered 2026-09-10: accepted as not met; #294 closed.**
3. **Ch23 — Cloudera AI on Data Services**: stand up a CDS 1.5.5+ test env, or leave blocked?
4. **Ch26**: acquire a 2nd DGX Spark, or keep as a hardware-gated stub?
5. **EPIC #226 is closed** while ~12 chapters remain: reopen it, or let this issue be the tracking home? *Recommendation 2026-09-10: leave closed, this issue is the home; plan and tracker now point here.*
6. **Open technical unknowns** (from `nvidia-dgx-spark-k3s-cso.md`): GPU device-plugin `v0.17.4` vs `v0.18.1`; do the NiFi Python extension wheels (`unstructured`, `detectron2_onnx`) resolve for aarch64; which PyTorch `sm_121` wheel index for the Flink GPU image rebuild.
