# EFM Guide — Humanization Pass

**Work-stream G of EPIC #137, tracked in #295 (`device:WindowsDesktop`). Status: method + baseline landed 2026-09-02; A/B and the all-chapter pass not started.**

Steven, 2026-09-02, after reading the 09-01 delivery: *"we need to rewrite some of the war story stuff. Once those are refined, i think an entire pass of humanization and evaluate the content output versus author writing style."* Ch20 and Ch12 were re-authored the same day under `agent/writing-style.md` as committed (#138, #178). This doc is the second half: measure every chapter against Steven's own published voice, decide with evidence whether the committed style rules are enough, and run the pass in the order the numbers say.

## What "author writing style" means here — the baseline

Steven's decision (2026-09-02): **every post on the live blog back to its start, minus the release emails.** The older posts are mostly hand-written; everything published is voice he accepted.

- Source: `cldr-steven-matison/cldr-steven-matison.github.io`, `_posts/*.md`, cloned read-only on WindowsDesktop at `/home/tunas/cldr-steven-matison.github.io`.
- **64 posts kept, 47 excluded.** Excluded = release/GA announcements and vote-email reposts (titles carry "Release", "Release Voting", "General Availability", "GA", an operator/product version number, or the body is a pasted product announcement). The audit list is at the end of this doc.
- Scorer: [`files/prose-lint.py`](files/prose-lint.py) (stdlib Python, Markdown in, Markdown table out). It strips front matter, code blocks, inline code, link URLs, images, HTML and table rows, then measures the prose that is left. `--baseline` appends a min/median/max row over the set.

```bash
# the blog band (paths from the audit list; filenames contain spaces)
xargs -d '\n' python3 files/prose-lint.py --baseline < baseline-posts.txt
# every chapter
python3 files/prose-lint.py --baseline ~/EdgeFlowManager/ch*.md
# one chapter, before and after an edit
python3 files/prose-lint.py ~/EdgeFlowManager/ch20-sparkplug-demo.md
```

## The measured gap (medians, per 1,000 prose words unless noted)

| metric | Steven's blog (64 posts) | guide chapters (21) | Ch20 after re-author | Ch12 after re-author |
|---|---|---|---|---|
| em-dashes | **1.5** | 23.9 | 5.8 | 3.8 |
| proof-of-work words (real, genuine, actually, confirmed, verified, proven…) | **2.7** | 10.0 | 2.3 | 5.2 |
| contrast constructions (not just / rather than / "not X — Y") | **0.0** | 2.8 | 2.9 | 1.5 |
| colon- or dash-joined clauses | **8.2** | 32.6 | 15.6 | 13.1 |
| bold-led bullets (% of bullets) | **0** | 55 | 17 | 81 |
| parentheticals | 7.7 | 15.1 | 12.7 | 11.1 |
| "you" | **16.8** | 2.9 | 0.6 | 2.0 |
| "I" | **6.1** | 0.0 | 0.0 | 0.0 |
| contractions | 3.7 | 13.2 | 13.9 | 16.3 |
| mean sentence length (words) | 32.6 | 33.0 | 35.3 | 33.3 |
| sentences over 35 words (%) | 32.5 | 31.5 | 34.7 | 37.9 |
| provenance hits (dates, issue #s, shas, "Task N", "as of") | **0** | 0 (max 10) | 0 | 0 |

Read across the rows:

- **Sentence length is not the problem.** Steven's sentences are as long as the chapters'. Nobody should be chopping prose to hit a readability score.
- **Punctuation is.** The chapters carry sixteen times the em-dashes and four times the colon-joins. That is the single loudest LLM tell in the corpus, and `writing-style.md` already names it ("em-dashes used for emphasis where a period would do").
- **Proof-of-work vocabulary is.** "Real", "genuine", "actually", "confirmed", "verified", "field-validated" run four times denser in the chapters. Steven states a thing; the chapters keep insisting the thing is true. The provenance rule strips the dates; this is the adverb residue the rule does not name yet.
- **Address is.** Steven talks to the reader ("you") six times as often and to himself ("I") where the chapters never do. The chapters are written in an impersonal third voice. `writing-style.md` says first person; the chapters do not do it.
- **Bold-led bullets are.** Steven's bullets are plain sentences or plain list items. Over half the chapter bullets open with a bolded label, and the two re-authored chapters still do (Ch12's What-NOT-to-Do list is the bulk of its 81%).
- **Contractions run the other way.** The chapters are chattier than Steven, who writes "do not" more often than "don't". A small signal; do not force it either way.
- Ch20 and Ch12 after re-author sit inside the band on punctuation, proof words and provenance, and still outside it on address and bold bullets. That is what the committed rules buy on their own.

## The rewrite rubric — ten checkable lines

Derived from the band above and `agent/writing-style.md`. A chapter passes when a reader can tick every line without arguing.

1. **Zero provenance.** No dates, issue numbers, commit shas, flow versions, "Task N", "as of", "at the time", agent or class names used as evidence. (Existing rule; lint columns `dates`/`issues`/`prov` = 0.)
2. **Em-dashes at most 2 per 1,000 words.** A period, a comma, or a new sentence instead. (Lint `emdash/k` ≤ 2.)
3. **No proof-of-work adverbs.** Say what happened; do not certify it. "The consumer decodes it" not "the consumer genuinely decodes it, confirmed live." (Lint `proof/k` ≤ 3.)
4. **No contrast scaffolding.** Drop "not X, but Y", "rather than", "not inferred", "not just". State Y. (Lint `contrast/k` ≤ 1.)
5. **Colon- and dash-joined clauses at most 10 per 1,000 words.** (Lint `colon/k` ≤ 10.)
6. **Talk to the reader.** Instructions in second person ("you"), the author's own actions in first person ("I hit this", "I fixed it by"). Target `you/k` ≥ 10 in how-to sections; `I/k` above zero in every chapter that narrates work.
7. **Bullets are sentences or items, not labels.** No bold-led bullet unless the bold is the rule itself in a What-NOT-to-Do list, and even there the rule reads as a sentence. (Lint `bold%` ≤ 20 outside What-NOT-to-Do.)
8. **Shape: symptom, diagnosis, fix.** Every trap section opens with the exact error or behavior, gives the one-or-two-sentence why, then the copy-paste fix. Recipe steps numbered. Background, alternatives and future work below the recipe, never inside it.
9. **Traps are rules, not incidents.** "Don't X; Y happens" with the mechanism. No "we hit this on the second attempt" narrative.
10. **No meta-commentary.** No "worth noting", "the one thing to know", "the lesson generalizes", "importantly". (Lint `meta/k` = 0.)

Lines 1–5 and 10 are mechanical and the lint checks them. Lines 6–9 need a human read, which is what the A/B below is for.

## The A/B — does `writing-style.md` alone close the gap?

Take one section of Ch20 (candidate: "Verify End to End", about 350 words). Produce two versions from the same source facts:

- **A — rules only.** `agent/writing-style.md` as committed, nothing else. This is what Ch20/Ch12 already got; A is the current text.
- **B — rules + rubric.** The ten lines above applied on top, with lines 6 and 7 pushed hard: second person throughout, first person where the author acted, plain bullets.

Steven reads both without labels and picks. Three outcomes, each with a consequence:

| pick | conclusion | then |
|---|---|---|
| B, clearly | the committed rules are not enough; the rubric is the bar | fold lines 2–7 and 10 into `writing-style.md`, run the pass with the rubric |
| A, or no preference | the rules are enough; the remaining gap is acceptable | fold only lines 2, 3 and 5 (punctuation + proof words) into `writing-style.md`, run the pass with the rules |
| neither | voice needs something the rubric does not capture | Steven marks up B by hand; the markup becomes rubric lines; re-run the A/B once |

One section, one read, one decision. Do not A/B every chapter.

## Order of the pass — chapters ranked by distance from the band

Distance = (em-dash/k over 1.5) + (proof/k over 2.7) + half the colon/k over 8.2 + bold% ÷ 10 + provenance hits + a quarter of the "you" shortfall. It is a ranking, not a score to optimize.

| rank | chapter | words | em-dash/k | proof/k | colon/k | bold-bullet % | you/k | prov | distance |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `ch03-cpp-processor-catalog.md` | 1813 | 56.3 | 7.7 | 64.5 | 97.6 | 5.5 | 0 | 101 |
| 2 | `ch18-sample-gallery.md` | 2023 | 26.2 | 14.8 | 39.1 | 89.3 | 1.0 | 8 | 73 |
| 3 | `ch13-efm-and-sparkplug-mqtt.md` | 3774 | 25.2 | 18.8 | 31.5 | 55.8 | 2.9 | 5 | 66 |
| 4 | `ch21-metrics-and-observability.md` | 4169 | 25.4 | 12.5 | 32.6 | 80.6 | 1.9 | 7 | 65 |
| 5 | `ch01-efm-on-kubernetes.md` | 969 | 27.9 | 5.2 | 34.1 | 83.3 | 1.0 | 10 | 64 |
| 6 | `ch04-java-processor-catalog.md` | 1256 | 22.3 | 20.7 | 37.4 | 30.0 | 12.7 | 1 | 58 |
| 7 | `ch10-minifi-on-k8s.md` | 1640 | 25.6 | 11.6 | 33.5 | 46.2 | 1.2 | 2 | 56 |
| 8 | `ch05-executescript-availability.md` | 1390 | 20.9 | 18.7 | 29.5 | 38.5 | 7.2 | 2 | 54 |
| 9 | `ch16-how-to-ai-with-minifi.md` | 1743 | 22.9 | 10.3 | 32.7 | 76.2 | 7.5 | 3 | 54 |
| 10 | `ch17-edge-ai-router.md` | 1788 | 23.5 | 15.7 | 30.2 | 0.0 | 0.6 | 2 | 52 |
| 11 | `ch19-efm-and-nvidia-jetson.md` | 3049 | 23.9 | 10.5 | 33.8 | 14.3 | 2.0 | 2 | 50 |
| 12 | `ch14-nifi-and-ai-skill-efm-portion.md` | 3408 | 23.2 | 10.0 | 29.0 | 64.9 | 4.4 | 0 | 49 |
| 13 | `ch06-minifi-custom-python-processors.md` | 1407 | 27.0 | 2.1 | 33.4 | 60.0 | 2.1 | 0 | 48 |
| 14 | `ch09-efm-in-the-playground.md` | 975 | 25.6 | 10.3 | 32.8 | 0.0 | 2.1 | 0 | 48 |
| 15 | `ch08-minifi-java-setup.md` | 835 | 27.5 | 6.0 | 34.7 | 0.0 | 9.6 | 0 | 44 |
| 16 | `ch07-standalone-minifi-cpp-on-k8s.md` | 866 | 25.4 | 6.9 | 31.2 | 0.0 | 17.3 | 0 | 40 |
| 17 | `ch02-efm-binaries.md` | 2005 | 19.5 | 8.5 | 24.9 | 55.0 | 11.5 | 0 | 39 |
| 18 | `ch11-site-to-site.md` | 1383 | 18.8 | 0.7 | 28.2 | 85.7 | 9.4 | 0 | 38 |
| 19 | `ch15-how-to-ai-with-nifi-and-python.md` | 1089 | 19.3 | 6.4 | 30.3 | 30.0 | 18.4 | 0 | 36 |
| 20 | `ch12-efm-and-microfi.md` | 3429 | 3.8 | 5.2 | 13.1 | 81.2 | 2.0 | 0 | 19 |
| 21 | `ch20-sparkplug-demo.md` | 1732 | 5.8 | 2.3 | 15.6 | 16.7 | 0.6 | 0 | 14 |

Two notes on the ranking. Ch03 and Ch18 lead because they are catalogs and cards: dash-separated one-liners and bold-led entries are their format, so their pass is a format decision (keep the tables, humanize the prose around them), not a rewrite. Ch13 and Ch21 rank high despite Steven's "pretty good" and "approved": they pass on shape and fail on punctuation and proof words, which is the exact axis this pass exists for. Ch14/16/19 are still waiting on his read-through; run their pass before that read so he reads them once.

## Procedure per chapter

1. `git pull` both repos. Lint the chapter; keep the row as "before".
2. Confirm the facts the chapter states against live state where it names a live thing (EFM class list, NiFi root PGs, ports, topics). Write the live way; drop what is gone.
3. Rewrite under `writing-style.md` plus whichever rubric lines the A/B kept. Keep every command, path, port, and figure. Move any dated or incident material to the chapter's DesktopShare source doc (the tracker's "Subplans" list says which).
4. Lint again. Lines 1–5 and 10 must pass; note `you/k` and `bold%` in the finish comment even if they are not gated.
5. Verify every `files/` and `images/` link resolves: `grep -oE '\]\((files|images)/[^)#]+' chNN.md | sed 's/](//' | while read p; do test -e "$p" || echo MISSING $p; done`.
6. Commit EdgeFlowManager (`chNN (#295): humanize — …`), commit the tracker row + source-doc move in DesktopShare, push both, comment on #295 with the before/after row and both shas.

Batch three to five chapters per session; one commit per chapter so a bad rewrite reverts alone. Model: the rewriting is the session model's job; lint runs and link checks go to `haiku`.

## When this ships

- Fold the surviving rubric lines into `agent/writing-style.md` §"What to strip" and add a Rule-canon row in `agent/incident-rules.md` pointing at it, so every device writing chapters or READMEs has the bar. Delete nothing from this doc; it stays the record of how the bar was set.
- Add a `humanize` topic row to `agent/known-patterns.tsv` pointing at this doc and `files/prose-lint.py`, so a session that starts rewriting prose gets the lint injected.
- Flip the tracker: each chapter's row notes "humanized (#295)" with its after-row; the EPIC #137 close then waits only on the Ch14/16/19 read-through.
- Re-run the blog baseline whenever a new non-release post publishes; the band is a moving target by design.

## Appendix — excluded posts (release emails, 47)

Kept-list and this list live at the scratchpad paths used on 2026-09-02; regenerate by title from `_posts/` when re-running. Excluded:

```
2023-06-08-NiFi 1.22 Release Voting.md
2023-07-26-NiFi 1.23 Release Voting.md
2023-08-16-NiFi 1.23.1 Release Voting.md
2024-03-11-CEM-2.1.2-Release.md
2024-08-19-CSA-1.13-Release.md
2024-09-06-Cloudera Streams Messaging Operator 1.1.md
2024-12-12-Cloudera Unified Runtime 7.3.1.md
2024-12-16-CSA-1.14-Release.md
2024-12-23-CSM-Kubernetes-Operator1-2-Release.md
2025-01-16-Cloudera-Migration-Assistant 3.5.0.md
2025-01-21-Cloudera-Flow-Management-4.0.0.md
2025-03-11-Cloudera Streams Messaging Kubernetes Operator 1.3.md
2025-03-13-Cloudera Streams Analytics Kubernetes Operator 1.2.md
2025-03-23-Nifi 1.0 to Nifi 2.0 Migration Tool.md
2025-04-30-CSA-1.15-Release.md
2025-04-30-Cloudera DataFlow 2.10.md
2025-04-30-Cloudera Flow Management Kubernetes Operator 2.10.md
2025-06-02-Cloudera Nifi 2.0 Migration Tool GA.md
2025-06-11-Cloudera Data Services 1.5.5 GA.md
2025-06-17-Cloudera Flow Management Migration Tool 7.0.1 Release Announcement.md
2025-07-18-Cloudera-Flow-Management-2.2.9 General Availability.md
2025-07-22-Cloudera Streaming Analytics - Kubernetes Operator 1.3.md
2025-07-24-Cloudera Streams Messaging Kubernetes Operator 1.4.md
2026-01-30-Trino for Cloudera Data Warehouse.md
2026-02-05-Cloudera AI Inference.md
2026-02-05-Cloudera AI January Release.md
2026-02-20-Cloudera Streams Messaging Kubernetes Operator 1.6.md
2026-03-02-Cloudera-Flow-Management-3.0 For Cloudera On Cloud.md
2026-03-03-Cloudera Flow Management Kubernetes Operator 3.0.md
2026-03-04-Cloudera Streaming Analytics - Kubernetes Operator 1.5.md
2026-03-17-Cloudera Data Lineage Trino.md
2026-03-18-Cloudera Data Engineering 1.25.2.md
2026-04-01-Introducing Cloudera Runtime 7.3.2.md
2026-04-02-Cloudera-Flow-Management-4.12.0.md
2026-04-14-All the New in 7.3.2.md
2026-04-22-Cloudera AI April Release.md
2026-05-05-Cloudera Streaming Analytics 1.17.0.md
2026-05-11-Real-Time Monitoring with Observability.md
2026-05-16-Cloudera Data Services On Premises 1.5.5 SP3 GA Schedule Revised.md
2026-05-20-Cloudera Data Flow 3.1 for Cloudera on Cloud.md
2026-06-01-Cloudera Flow Management Operator for Kubernetes 3.1.md
2026-06-25-Cloudera Data Services On Premises 1.5.5 SP3 Release.md
2026-06-25-Cloudera Flow Management 2.1.7 Service Pack 4 Release Announcement.md
2026-08-11-Cloudera Streaming Analytics 1.17.1.md
2026-08-24-Cloudera Streams Messaging Kubernetes Operator 1.7.md
2026-08-31-Cloudera Flow Management Operator for Kubernetes 3.3.md
2026-08-31-Cloudera Observability for Cloudera AI on Public Cloud.md
```
