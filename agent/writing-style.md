# Writing style

Docs in DesktopShare get published — either directly to the blog, or copy-pasted into a blog post with minor edits. Write for that from the first draft, in Steven's voice.

## Voice

- **First-person, present tense.** "I hit this wall," "I fixed it by," not "one would" or "the reader should."
- **Direct.** No hedging padding. If something didn't work, say "it didn't work." If it did, say "it works." Skip the "unfortunately," "importantly," and "it's worth noting that" scaffolding.
- **Real numbers, real paths, real filenames.** `mynifi-0`, not "the NiFi pod." `31623`, not "the external port." A doc without specifics is worthless six months later.
- **No excuses.** When something broke, state plainly what happened and what's being done about it. Justification padding gets cut.

## Shape

Every technical post lands on the same three-part structure. It doesn't have to be labelled, but the flow should be readable in that order:

1. **Symptom.** What I saw. The exact error, the exact log line, the exact behavior. Paste the raw text — don't paraphrase.
2. **Diagnosis.** Why. The one or two sentences that connect the symptom to a root cause. If the root cause was surprising, say so.
3. **Fix.** The exact commands, in order, with any prerequisites called out. Copy-paste-ready.

Anything that isn't symptom, diagnosis, or fix — background, alternatives considered, "future work" — goes below or in a callout. It doesn't share space with the recipe.

## Commands

- Every command block gets the shell language tag (```` ```bash ````, ```` ```powershell ````, ```` ```yaml ````).
- Absolute paths only when the reader needs to type that exact path. Otherwise use `~/DesktopShare/…` or a `$VAR` you defined above.
- One command per line unless the pipe is the point. If it's a compound command with `&&`, split it if the flow is complex enough that a reader might want to run half of it.
- Comments in the block, not in the surrounding prose, when the reader needs to know why *that* flag.

## Structure of a longer doc

- **Title** is the blog title — real, googlable, no "part 3" scaffolding unless it truly is a series.
- **Opening 3-5 lines** frame *why* — what I was doing when I hit this, what the reader is going to leave with. Not what's in the doc; what problem it solves.
- **Section headers** are useful in isolation. `## Fix — reinstall MSI with ADDLOCAL=ALL` beats `## Step 3`.
- **A "what NOT to do" list at the end** when there's a real trap door. This is where the ffmpeg-copy-trim / GET-then-PUT / etc. lessons go.
- **Every plan doc updates DesktopShare docs when it lands.** A working plan closes with "when this ships, update `<the.md file>` with the tweaks that came up." Otherwise the doc drifts within a week.

## Blog layout — front matter, callouts, icons, closer

The blog is the Minimal Mistakes Jekyll theme on `cldr-steven-matison.github.io`. A post that
lands in the blog repo `_posts/` needs the theme's front matter and closer, or it renders wrong.
Author these into the DesktopShare draft from the start — don't bolt them on at publish time.

**EFM-guide chapter files are the exception** (policy, #72/#73, 2026-08-03; chapters live in the
[`EdgeFlowManager`](https://github.com/cldr-steven-matison/EdgeFlowManager) repo since 2026-08-05 —
DesktopShare's `guide/` is a redirect stub). Chapters are read through the guide index on GitHub,
not published standalone to `_posts/`, so they carry **no** Jekyll front matter and **no** closer
slug — a plain `# Chapter N: Title` H1 and GitHub-flavored Markdown only. Callouts in chapters use
inline blockquotes (`> **⚠️ …**`), not the `{: .notice--danger}` class (that class needs the Jekyll
theme to render). The front-matter and notice-class rules below apply to the chapter's
**corresponding `blog/` draft** when it publishes, not to the chapter file itself.

### Front matter

Every post opens with a YAML block between `---` fences. Two forms are in use; pick by whether the post has a teaser image:

```yaml
---
layout: single
title: "How to Build and Test Custom NiFi Processors with AI (Without Breaking NiFi)"
date: 2026-04-29
classes: wide
categories:
  - blog
tags:
  - nifi
  - python
  - ai
---
```

When there's a header/teaser image, use `excerpt` (the one-line hook shown in listings and social cards) and a `header.teaser` path instead of `date`/`classes`:

```yaml
---
title: "Observability with Cloudera Streaming Operators"
excerpt: "End to end observability of NiFi, Kafka, and Flink on kubernetes with prometheus and grafana."
header:
  teaser: "/assets/images/2026-05-XX-Observability_With_CSO.png"
categories:
  - blog
tags:
  - prometheus
  - grafana
---
```

- `categories:` is always `- blog`.
- `tags:` are lowercase, hyphenated, real search terms — `lets-encrypt`, `best-practices`, not "Misc."
- `title:` is the googlable blog title, same rule as the doc title.

### Callouts

After a code box or a content section, use a callout for anything that isn't part of the recipe — a trap, a pro tip, a WIP warning. The class goes on its own line **directly below** the paragraph it styles:

```markdown
:warning: **Danger!** This is a Work in Progress article, content and code is updating frequently until this notice is removed.
{: .notice--danger}

:trophy: **Pro Tip!** Keep `watch nvidia-smi` running in another terminal — you'll see your 4060 light up during inference.
{: .notice--warning}
```

All available callout classes:

| Class | Purpose | Typical color |
|---|---|---|
| `{: .notice}` | Default | Neutral / grey |
| `{: .notice--primary}` | Primary | Theme primary (blue / purple) |
| `{: .notice--info}` | Information | Blue |
| `{: .notice--success}` | Success | Green |
| `{: .notice--warning}` | Warning | Yellow / orange |
| `{: .notice--danger}` | Danger / error | Red |

### Icons

Lead a callout (or a section header, where it fits) with a theme emoji shortcode — `:warning:`, `:trophy:`, `:rocket:`, `:hammer_and_wrench:` — from the common GitHub/Jekyll emoji set. Use them where they carry meaning (danger, pro tip, prerequisites), not as decoration on every line.

### Closer

End every post with the standard reach-out slug — the theme substitutes `{{ page.title }}` with the post title:

```markdown
## {{ page.title }}
If you would like a deeper dive, hands on experience, demos, or are interested in speaking with me further about {{ page.title }} please reach out to schedule a discussion.
```

## Terminal history and appendix — expose the operational trail (blog output)

The recipe in the body is the polished path. But I share the *real* operational trail too, on purpose — a reader who's actually rebuilding this wants the exact commands I ran, in the order I ran them, including the wrong turns. So a blog post closes with one or both of these, after the recipe and before (or alongside) Resources and the closer slug:

### `### Terminal History`

A raw dump of the actual shell history, in a ```` ```terminal ```` fenced block, **unedited**. This is deliberately not cleaned up:

- Leave the messy real sequence in — apply, then delete, then re-apply, the `helm rollback` after the upgrade that failed. The path I took *is* the content.
- Keep inline `#` notes where I flagged something mid-session ("`# a :lightbulb: moment. when helm upgrade failed rollback worked to revert`"). Those are the hard-won bits.
- Don't fix typos or reorder for tidiness — this is a transcript, not a script. Its value is that it's real.

### `### Appendix`

The same operational commands, but **organized by purpose** for someone who wants to reuse them cleanly — numbered subsections (`#### 1. Full Delete + Rebuild`, `#### 2. Source of Kafka Metrics`, `#### 5. Force Prometheus to pick up changes`), each a copy-paste-ready ```` ```bash ```` block. This is where the multi-line, backslash-continued "your exact command" forms live.

Use Terminal History when the *journey* is instructive (iteration, rollbacks, dead ends), the Appendix when there's a clean set of reusable operations worth lifting out of the prose. Longer posts carry both.

**The one thing to scrub:** paste commands freely, but never paste secret *values* or command *output* that contains them. A `kubectl get secret ... | base64 --decode` command in the history is fine — the decoded password it prints is not. Same rule as everywhere else in this repo (see `agent/incident-rules.md`).

## Reporting work — issue comments and wrap-ups

The finish-ritual comment and the session wrap-up follow the same rules as everything else here, plus one of their own:

**A detour you had to be pulled out of is not a finding.** If a tangent got cut short — you were chasing something that turned out to be irrelevant, or Steven interrupted to say it was a waste of time — that tangent is dead. It does not come back as a bullet in the issue comment, a "one thing worth flagging" note, or a line in the summary. Drop it silently and report the work that was asked for.

Writing it up anyway reads as billing him for your own mistake: he already paid for the time once in interruption, and the write-up spends his attention on it a second time. A side-observation earns a mention only when it **blocks the work** or **he asked about it**. Everything else goes nowhere.

The related tell to catch earlier: an intermittent failure you cannot reproduce is not a lead worth pulling on mid-task. Note it to yourself, finish the job.

## What to strip

- LLM tells: "delve," "leverage," "in the fast-paced world of," "certainly!" openings, em-dashes used for emphasis where a period would do, sentence-endings that summarize what you just said.
- Bullet points where a sentence is fine. Bullet lists are for genuinely enumerated things.
- Sections labelled "Introduction" or "Conclusion" — the opening and the fix ARE the introduction and conclusion.

### Published artifacts strip their own provenance

A shipped artifact is the finished product, not the work log that produced it. Write it clean from
the first draft — strip every trace of how it was built:

- **Dates** — "2026-08-04," "confirmed as of…," "field-proven end-to-end" freshness stamps.
- **Issue numbers** (#59, #99) and links to issues.
- **Agent or class names used as evidence** — `MinikubeMacJavaPyTest`, "disposable throwaway agent," "3/3 POSTs, no drops."
- **Proof-of-work language** — "proven," "field-validated," "the manifest-staleness gotcha we hit."
- **Cross-repo back-references** — a standalone README or chapter does not say "see Ch6 of the guide" or link back to a DesktopShare planning doc. It stands alone.
- **Progress notes** — "see X below," "see Solved gap," "(uncommitted)," WIP asides that only make sense mid-session.

The proof, the dates, and the issue trail live in the **living findings docs** (root-tier `.md`) and
**issue comments** — never in the shipped artifact. Cross-links *between* published chapters (via the
guide index) are fine; everything above is not.

**This governs every outbound repo, not just DesktopShare's own `.md`.** Content sourced here and
published elsewhere carries the same rule to its destination: the [`EdgeFlowManager`](https://github.com/cldr-steven-matison/EdgeFlowManager)
guide chapters, Playground scenario READMEs, the `cldr-steven-matison.github.io` blog repo, and any
app repo's shipped README. When a file leaves DesktopShare as published content, it leaves the
provenance behind — the destination repo gets clean prose, and it is the author's job to scrub it on
the way out, not the reader's to tolerate it.
