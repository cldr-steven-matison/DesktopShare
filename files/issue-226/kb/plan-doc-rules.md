# Plan-doc lint rulebook — what the local first pass judges, and what it does not

This is the rulebook `measure.py lint` hands the box's model for a root-tier DesktopShare plan doc (`nvidia-dgx-spark-*.md` and its siblings). It exists because the first local lint pass (#294, L4) returned 13 findings and **0 were actionable**: it applied the `_posts/` blog-article rules in `agent/writing-style.md` to a plan doc — front matter, a Jekyll closer, `{: .notice}` classes, a "How to…" title — and hallucinated one finding outright. The blog rules are right for a blog post. A plan doc is a different shape, and this file says how. It is derived from `agent/writing-style.md`; that file stays the human source of the voice rules.

## What a plan doc IS — do not report any of this as a violation

- It opens with `# Title` and then a `> **Status (YYYY-MM-DD …):**` blockquote, newest first; older status blocks may follow. That blockquote *is* the opening.
- Its body is numbered `## N. …` sections, then these closers in this order: `## Open questions` (optional), `## Definition of done`, `## When this ships`, `## Resources`.
- It has **no** Jekyll front matter, **no** `{: .notice-*}` callout classes (they need the blog theme), **no** closer slug, and needs **no** emoji shortcodes. Callouts are plain `>` blockquotes. Never report the absence of any of these.
- Symptom → Diagnosis → Fix is a *flow*, not three labelled headers. A plan doc's first section usually carries it unlabelled. Never report a "missing Symptom section" or "missing Fix section".
- Its title is a real, googlable noun phrase. "How to…" is not required.
- It is the **living record**: dates, issue numbers, commit shas, proof-of-work language and cross-links to other DesktopShare docs belong in it. The rule that strips provenance applies to *published* artifacts, not to this.
- Background, alternatives and measurements are its content, not padding to move to a callout.

## Already checked deterministically by `doc-check.py` — say nothing about these

Fence language tags · the status date · closers present and in order · no `## Introduction` / `## Conclusion` · the literal words "git commit" / "git push" · backticked filenames existing · URLs traceable to the corpus · `§`-references resolving · bare "Spark" in a Cloudera sentence · the LLM tells *delve, leverage, it's worth noting, in the fast-paced, certainly!, in conclusion, as we can see*.

If you believe one of these is violated, you are misreading the document. Do not report it.

## What you DO judge — the voice rules that still apply to a plan doc

1. **Voice.** First person, present tense, direct. Flag "one would", "the reader should", passive hedging, "unfortunately" / "importantly" / "it should be noted" scaffolding, and justification padding after a failure.
2. **The opening frames *why*.** What problem, what the reader leaves with — not a list of what is in the doc.
3. **Headers useful in isolation.** `## Fix — reinstall MSI with ADDLOCAL=ALL` beats `## Step 3`. A header that names its subject — `### aarch64 install path`, `### Heartbeat, and the liveness trap`, `## 4. Observability` — **is** useful in isolation. Flag only headers that say nothing without their section: `## Step 3`, `## Overview`, `## Notes`, `## Misc`.
4. **Specifics — missing values only.** Flag a sentence only when a concrete value is *absent where the reader needs it*: "the port" where a number belongs, "the file" where a path belongs, "a few seconds" where a measurement exists, a command described rather than shown. A device or system already named by its fleet name — `the Jetson`, `the array`, `this box`, `this fleet`, `WindowsDesktop`, `EFM`, `the DGX Spark` — **is specific**; never flag it and never propose a different name for it.
5. **Raw text, not paraphrase**, for error messages, log lines and commands.
6. **A "What NOT to do" list** exists when the doc describes a real trap door.
7. **Bullets only for genuinely enumerated things**; a sentence otherwise.
8. **Commands:** one per line unless the pipe is the point; `~/DesktopShare/…` or a defined `$VAR` rather than an absolute path unless the reader must type that exact path; the *why* of a flag as a comment in the block, not in the prose.

## Output

A bullet list of **violations only**, at most **10**, the most consequential first. Each finding is: the rule number, the **exact quoted text** from the document, and a one-line fix. Every quoted phrase must appear verbatim in the document — never invent, paraphrase or infer a quote. Never list an item you judge acceptable, borderline, "specific enough" or "valid" — if it is not a violation it does not appear. Do not reason out loud, and do not revise a finding inside the list. If more than ten violations exist, add one closing line: `+N more`. If the document is clean under rules 1–8, output exactly: `clean`.
