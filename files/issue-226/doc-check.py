#!/usr/bin/env python3
"""Deterministic checks for the #226 DGX Spark plan docs.

Usage: doc-check.py [--repo DIR] [--research-dir DIR] [--status-date YYYY-MM-DD] [--json] DOC.md [DOC.md ...]

Errors (exit 1) are things a doc must not ship with; warnings are for the lint agent to judge.
Every check is mechanical so the same result comes back on every run — it is the second and fourth
of the "triple checks" on each doc (author → lint → this → adversarial fact-check → this again).
"""
import argparse, glob, json, os, re, sys

FORBIDDEN = [
    ("git commit", "literal 'git commit' is banned in plan docs"),
    ("git push", "literal 'git push' is banned in plan docs"),
    ("## Introduction", "no Introduction header"),
    ("## Conclusion", "no Conclusion header"),
]
LLM_TELLS = ["delve", "leverage", "in the fast-paced", "it's worth noting", "it is worth noting", "certainly!", "in conclusion", "as we can see"]
CLOSERS = ["## Definition of done", "## When this ships", "## Resources"]
SIBLINGS = ["nvidia-dgx-spark-research.md", "nvidia-dgx-spark-landscape.md", "nvidia-dgx-spark-runbook.md",
            "nvidia-dgx-spark-k3d-cso.md", "nvidia-dgx-spark-efm-agent.md", "nvidia-dgx-spark-local-kb.md",
            "nvidia-dgx-spark-cloudera-aws.md", "nvidia-dgx-spark-cloudera-demos.md", "nvidia-dgx-spark-plan.md"]
SHORT = {"research": "nvidia-dgx-spark-research.md", "landscape": "nvidia-dgx-spark-landscape.md",
         "runbook": "nvidia-dgx-spark-runbook.md", "k3d-cso": "nvidia-dgx-spark-k3d-cso.md",
         "efm-agent": "nvidia-dgx-spark-efm-agent.md", "local-kb": "nvidia-dgx-spark-local-kb.md",
         "cloudera-aws": "nvidia-dgx-spark-cloudera-aws.md", "cloudera-demos": "nvidia-dgx-spark-cloudera-demos.md",
         "demos": "nvidia-dgx-spark-cloudera-demos.md", "plan": "nvidia-dgx-spark-plan.md"}
URL_RE = re.compile(r'https?://[^\s<>"\'\)\]`]+')
ALLOW_URL_PREFIX = ("https://github.com/cldr-steven-matison/",)
FILE_RE = re.compile(r'`([^`\s]+\.(?:md|sh|js|py|json|yaml|yml|kdl|txt|csv|flow\.json))`')
SUBREPO_ROOTS = ["/home/tunas"]


def strip_url(u):
    return u.rstrip('.,;:)')


def load_known_urls(repo, research_dir):
    known = set()
    for f in glob.glob(os.path.join(research_dir, "*.json")):
        known |= {strip_url(u) for u in URL_RE.findall(open(f, encoding="utf-8", errors="ignore").read())}
    corpus = set(known)
    for root, _, files in os.walk(repo):
        if "/.git" in root or "/files/issue-226/research" in root:
            continue
        for fn in files:
            if fn.endswith(".md"):
                try:
                    known |= {strip_url(u) for u in URL_RE.findall(open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read())}
                except OSError:
                    pass
    return corpus, known


def h2_numbers(path):
    nums = set()
    if not os.path.exists(path):
        return None
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.match(r'^## (\d+)\.', line)
        if m:
            nums.add(int(m.group(1)))
    return nums


def resolve_file(name, repo, doc_dir):
    cands = [name, os.path.join(doc_dir, name), os.path.join(repo, name)]
    for sub in ("files", "completed", "blog", "research", "agent", "skills", "files/nvidia-spark-guide", "files/issue-226", "files/cso-prod-1"):
        cands.append(os.path.join(repo, sub, name))
    if name.startswith("/"):
        cands = [name]
    for c in cands:
        if os.path.exists(c):
            return True
    # bare basename anywhere in the repo (one level of tolerance for `foo.md` meaning completed/foo.md etc.)
    base = os.path.basename(name)
    for root, _, files in os.walk(repo):
        if "/.git" in root:
            continue
        if base in files:
            return True
    return False


def check(doc, repo, research_dir, status_date, corpus_urls, known_urls):
    errors, warnings = [], []
    text = open(doc, encoding="utf-8").read()
    lines = text.split("\n")
    doc_dir = os.path.dirname(os.path.abspath(doc))

    # 1. title + status blockquote
    if not lines or not lines[0].startswith("# "):
        errors.append("L1: must start with '# Title'")
    status_idx = next((i for i, l in enumerate(lines[:8]) if l.startswith("> **Status (")), None)
    if status_idx is None:
        errors.append("no '> **Status (YYYY-MM-DD):**' blockquote in the first 8 lines")
    elif status_date and f"> **Status ({status_date}" not in lines[status_idx]:
        errors.append(f"L{status_idx+1}: Status date must be {status_date}, got: {lines[status_idx][:40]}")
    if re.search(r'\b(has not arrived|not yet arrived|before the box arrives|until the box arrives|not yet delivered|pending arrival|awaiting hardware)\b', text, re.I):
        for i, l in enumerate(lines):
            if re.search(r'(has not arrived|not yet arrived|before the box arrives|until the box arrives|not yet delivered|pending arrival|awaiting hardware)', l, re.I):
                errors.append(f"L{i+1}: pre-arrival phrasing — the box landed 2026-08-26 as spark-dd06: {l.strip()[:100]}")

    # 2. closers in order, after numbered sections
    pos = [text.find(c + "\n") if (c + "\n") in text else text.find(c) for c in CLOSERS]
    for c, p in zip(CLOSERS, pos):
        if p < 0:
            errors.append(f"missing closing section '{c}'")
    if all(p >= 0 for p in pos) and pos != sorted(pos):
        errors.append("closing sections out of order (need Definition of done → When this ships → Resources)")
    last_numbered = max((i for i, l in enumerate(lines) if re.match(r'^## \d+\.', l)), default=-1)
    if all(p >= 0 for p in pos) and last_numbered >= 0:
        dod_line = text[:pos[0]].count("\n")
        if last_numbered > dod_line:
            errors.append("a numbered '## N.' section appears after '## Definition of done'")

    # 3. forbidden phrases / tells
    low = text.lower()
    for phrase, why in FORBIDDEN:
        if phrase.lower() in low:
            errors.append(f"forbidden: {why}")
    for t in LLM_TELLS:
        for i, l in enumerate(lines):
            if t in l.lower():
                warnings.append(f"L{i+1}: LLM tell '{t}'")

    # 4. code fences have a language tag; expected-marker coverage
    fence_open = None
    untagged, blocks, marked = 0, 0, 0
    for i, l in enumerate(lines):
        if l.startswith("```"):
            if fence_open is None:
                fence_open = i
                blocks += 1
                if l.strip() == "```":
                    untagged += 1
                    errors.append(f"L{i+1}: code fence without a language tag")
            else:
                body = "\n".join(lines[fence_open:i])
                if re.search(r'expected|verify on the box|as-built|verified', body, re.I):
                    marked += 1
                fence_open = None
    if fence_open is not None:
        errors.append(f"L{fence_open+1}: unclosed code fence")

    # 5. backticked filenames exist
    missing = set()
    for m in FILE_RE.finditer(text):
        name = m.group(1)
        if name.startswith(("http", "$", "<", "{")) or "<" in name or "*" in name or "…" in name or "NN" in name:
            continue
        if not resolve_file(name, repo, doc_dir):
            missing.add(name)
    for name in sorted(missing):
        errors.append(f"backticked file does not exist in the repo: `{name}`")

    # 6. URLs trace to the corpus or the repo
    urls = {strip_url(u) for u in URL_RE.findall(text)}
    unknown = [u for u in urls if u not in known_urls and not u.startswith(ALLOW_URL_PREFIX)]
    in_corpus = [u for u in urls if u in corpus_urls]
    for u in sorted(unknown):
        errors.append(f"URL not in the research corpus or any repo doc (unsourced): {u}")

    # 7. section cross-references resolve
    for m in re.finditer(r'`(nvidia-dgx-spark-[a-z0-9-]+\.md)` ?§ ?(\d+)', text):
        target = os.path.join(repo, m.group(1)); n = int(m.group(2))
        nums = h2_numbers(target)
        if nums is None:
            errors.append(f"§-reference to missing doc {m.group(1)}")
        elif n not in nums:
            errors.append(f"`{m.group(1)}` §{n} does not exist (it has ## {sorted(nums)})")
    for m in re.finditer(r'\b(research|landscape|runbook|k3d-cso|efm-agent|local-kb|cloudera-aws|cloudera-demos|demos|plan) ?§ ?(\d+)', text):
        target = os.path.join(repo, SHORT[m.group(1)]); n = int(m.group(2))
        nums = h2_numbers(target)
        if nums is None:
            errors.append(f"§-reference to missing doc {SHORT[m.group(1)]}")
        elif n not in nums:
            errors.append(f"{m.group(1)} §{n} does not exist in {SHORT[m.group(1)]} (it has ## {sorted(nums)})")
    for m in re.finditer(r'\bch(\d{2})\b', text):
        if not 1 <= int(m.group(1)) <= 22:
            errors.append(f"chapter ref ch{m.group(1)} outside ch01–ch22")
    for m in re.finditer(r'\bCh(\d{1,2})\b', text):
        if not 1 <= int(m.group(1)) <= 22:
            warnings.append(f"chapter ref Ch{m.group(1)} outside 1–22 (EFM-guide chapter? say so)")

    # 8. naming rule — bare "Spark" in a Cloudera sentence
    bare = re.compile(r'(?<!DGX )(?<!Apache )(?<!Apache-)(?<!Nvidia )(?<!NVIDIA )(?<!Py)\bSpark\b(?! box)(?!-hosted)(?!-side)(?!-to-)(?!s\b)')
    for i, l in enumerate(lines):
        if bare.search(l) and re.search(r'Cloudera|CDP|RAPIDS|Public Cloud|Data Hub|Iceberg|CDE\b|CDW\b', l):
            warnings.append(f"L{i+1}: bare 'Spark' in a Cloudera sentence — say 'DGX Spark' or 'Apache Spark': {l.strip()[:90]}")

    # 9. sibling docs referenced by exact name exist
    for s in SIBLINGS:
        if s in text and not os.path.exists(os.path.join(repo, s)):
            errors.append(f"references sibling {s} which does not exist yet")

    n_lines = len(lines)
    return {
        "file": os.path.relpath(doc, repo), "lines": n_lines, "h2": len([l for l in lines if l.startswith("## ")]),
        "urls_distinct": len(urls), "urls_in_corpus": len(in_corpus), "code_blocks": blocks, "code_blocks_marked_expected": marked,
        "errors": errors, "warnings": warnings,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/home/tunas/DesktopShare")
    ap.add_argument("--research-dir", default=None)
    ap.add_argument("--status-date", default="2026-08-26")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("docs", nargs="+")
    a = ap.parse_args()
    rd = a.research_dir or os.path.join(a.repo, "files/issue-226/research")
    corpus, known = load_known_urls(a.repo, rd)
    results = [check(d, a.repo, rd, a.status_date, corpus, known) for d in a.docs]
    if a.json:
        print(json.dumps(results, indent=1))
    else:
        for r in results:
            print(f"== {r['file']}: {r['lines']} lines, {r['h2']} h2, {r['urls_distinct']} URLs ({r['urls_in_corpus']} in corpus), "
                  f"{r['code_blocks']} code blocks ({r['code_blocks_marked_expected']} marked expected/verified) — "
                  f"{len(r['errors'])} errors, {len(r['warnings'])} warnings")
            for e in r["errors"]:
                print("  ERROR  ", e)
            for w in r["warnings"]:
                print("  warn   ", w)
    sys.exit(1 if any(r["errors"] for r in results) else 0)


if __name__ == "__main__":
    main()
