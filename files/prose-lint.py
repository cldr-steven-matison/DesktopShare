#!/usr/bin/env python3
"""
prose-lint.py -- mechanical prose scorer for Markdown docs.

Used to compare EFM-guide chapters against the author's published blog
posts (a "humanization" evaluation). Stdlib only, Python 3.12.

Usage:
    python3 prose-lint.py [--csv] [--baseline] PATH...

Each PATH is a .md file or a directory (recursed for *.md). --csv emits
CSV instead of a Markdown table. --baseline appends a final row with the
min/median/max over the given files for each metric.
"""

import argparse
import csv
import os
import re
import statistics
import sys

# ---------------------------------------------------------------------------
# Editable word/phrase lists
# ---------------------------------------------------------------------------

PROOF_WORDS = [
    "real", "genuine", "genuinely", "actually", "actual", "for real",
    "confirmed", "verified", "field-verified", "field-validated",
    "field-proven", "proven", "worked", "held",
]

META_PHRASES = [
    "worth noting", "worth knowing", "worth recording", "worth stealing",
    "the one thing to know", "here's the", "this is where", "the lesson",
    "the payoff", "in other words", "importantly", "it's worth", "note that",
]

CONTRAST_PHRASES = [
    "not just", "rather than", "instead of",
    "not inferred", "not assumed", "not guessed",
]

# ---------------------------------------------------------------------------
# Column layout
# ---------------------------------------------------------------------------

METRIC_KEYS = [
    "words", "emdash_per_k", "contrast_per_k", "proof_per_k", "meta_per_k",
    "dates", "issues", "provenance", "paren_per_k", "bullets_per_k",
    "bold_bullet_share", "sent_mean", "sent_long_pct", "colon_per_k",
    "you_per_k", "i_per_k", "contraction_per_k",
]

HEADERS = [
    "file", "words", "emdash/k", "contrast/k", "proof/k", "meta/k",
    "dates", "issues", "prov", "paren/k", "bullets/k", "bold%",
    "sent_mean", "long%", "colon/k", "you/k", "I/k", "contr/k",
]

# Metrics that are absolute counts (not per-1000-word rates).
INT_METRICS = {"words", "dates", "issues", "provenance"}

# ---------------------------------------------------------------------------
# Stripping
# ---------------------------------------------------------------------------

_FRONT_MATTER_RE = re.compile(r'\A---\s*\n.*?\n---\s*\n', re.DOTALL)
_FENCED_CODE_RE = re.compile(r'```.*?```', re.DOTALL)
_INLINE_CODE_RE = re.compile(r'`[^`]*`')
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]*\)')
_BULLET_RE = re.compile(r'^(-\s|\*\s|\d+\.\s)')
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def strip_front_matter(text):
    return _FRONT_MATTER_RE.sub('', text, count=1)


def strip_fenced_code(text):
    return _FENCED_CODE_RE.sub(' ', text)


def clean_lines_from(text):
    """Return per-line prose, with images/table rows dropped and inline
    code, HTML tags, and link URLs stripped from what remains."""
    lines = []
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('|'):
            continue
        if s.startswith('!['):
            continue
        line2 = _INLINE_CODE_RE.sub(' ', line)
        line2 = _HTML_TAG_RE.sub(' ', line2)
        line2 = _LINK_RE.sub(r'\1', line2)
        lines.append(line2)
    return lines


# ---------------------------------------------------------------------------
# Term matching helpers
# ---------------------------------------------------------------------------

_term_cache = {}


def term_count(text, term):
    pat = _term_cache.get(term)
    if pat is None:
        pat = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
        _term_cache[term] = pat
    return len(pat.findall(text))


def phrase_list_count(text, phrases):
    return sum(term_count(text, p) for p in phrases)


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def split_sentences(text):
    if not text.strip():
        return []
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [p.strip() for p in parts if p.strip()]


def compute_metrics(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()

    text = strip_front_matter(raw)
    text = strip_fenced_code(text)
    lines = clean_lines_from(text)

    # --- bullets (line-structure dependent) ---
    bullets = 0
    bold_bullets = 0
    for line in lines:
        s = line.lstrip()
        m = _BULLET_RE.match(s)
        if m:
            bullets += 1
            rest = s[m.end():]
            if rest.startswith('**'):
                bold_bullets += 1

    # --- colon_per_k (line-start-excluded ": ", plus " — " joins) ---
    colon_count = 0
    for line in lines:
        s = line.strip()
        if not s:
            continue
        for m in re.finditer(r': ', s):
            if m.start() != 0:
                colon_count += 1
        colon_count += len(re.findall(r' — ', line))

    # --- flattened prose blob for the remaining metrics ---
    blob = re.sub(r'\s+', ' ', ' '.join(lines)).strip()

    words = len(_WORD_RE.findall(blob))
    safe_words = words if words > 0 else 1  # avoid div/0; rates come out 0

    def rate(count):
        return round(count / safe_words * 1000, 1) if words > 0 else 0.0

    # emdash_per_k
    emdash_count = blob.count('—') + len(re.findall(r' -- ', blob))

    # contrast_per_k
    contrast_count = phrase_list_count(blob, CONTRAST_PHRASES)
    contrast_count += len(re.findall(r'\bnot\b[^.—]{1,40}—', blob, re.IGNORECASE))
    contrast_count += len(re.findall(r'— not ', blob, re.IGNORECASE))

    # proof_per_k
    proof_count = phrase_list_count(blob, PROOF_WORDS)
    proof_count += len(re.findall(r'\blive\s+[a-z]+', blob))

    # meta_per_k
    meta_count = phrase_list_count(blob, META_PHRASES)

    # provenance: dates, issues, flowVersion, shas, Task/Session/Phase N,
    # "as of", "at the time"
    dates = len(re.findall(r'\b20\d{2}-\d{2}-\d{2}\b', blob))
    issues = len(re.findall(r'#\d{2,4}\b', blob))
    flowver = len(re.findall(r'flowversion|flow version \d+', blob, re.IGNORECASE))
    shas = 0
    for m in re.findall(r'\b[0-9a-f]{7,40}\b', blob):
        if any(c.isdigit() for c in m) and any(c.isalpha() for c in m):
            shas += 1
    tsp = len(re.findall(r'\b(Task|Session|Phase) \d+\b', blob))
    asof = term_count(blob, 'as of')
    atthetime = term_count(blob, 'at the time')
    provenance = dates + issues + flowver + shas + tsp + asof + atthetime

    # paren_per_k
    paren_count = blob.count('(')

    # sentence stats
    sentences = split_sentences(blob)
    sent_lengths = [len(_WORD_RE.findall(s)) for s in sentences]
    sent_mean = round(statistics.mean(sent_lengths), 1) if sent_lengths else 0.0
    sent_long_pct = round(
        sum(1 for n in sent_lengths if n > 35) / len(sent_lengths) * 100, 1
    ) if sent_lengths else 0.0

    # you / I / contractions
    you_count = len(re.findall(r"\byou(r|'re|'ll|'ve)?\b", blob, re.IGNORECASE))
    i_count = len(re.findall(r"\bI('m|'d|'ve)?\b", blob))
    i_count += len(re.findall(r'\bmy\b', blob))
    contraction_count = len(re.findall(r"\w+'(t|s|re|ll|ve|d|m)\b", blob, re.IGNORECASE))

    bold_bullet_share = round(bold_bullets / bullets * 100, 1) if bullets else 0.0

    return {
        "words": words,
        "emdash_per_k": rate(emdash_count),
        "contrast_per_k": rate(contrast_count),
        "proof_per_k": rate(proof_count),
        "meta_per_k": rate(meta_count),
        "dates": dates,
        "issues": issues,
        "provenance": provenance,
        "paren_per_k": rate(paren_count),
        "bullets_per_k": rate(bullets),
        "bold_bullet_share": bold_bullet_share,
        "sent_mean": sent_mean,
        "sent_long_pct": sent_long_pct,
        "colon_per_k": rate(colon_count),
        "you_per_k": rate(you_count),
        "i_per_k": rate(i_count),
        "contraction_per_k": rate(contraction_count),
    }


# ---------------------------------------------------------------------------
# Formatting / output
# ---------------------------------------------------------------------------

def fmt_val(key, v):
    if key in INT_METRICS:
        if float(v).is_integer():
            return str(int(v))
        return f"{v:.1f}"
    return f"{v:.1f}"


def row_for(path, metrics):
    base = os.path.basename(path)[:40]
    return [base] + [fmt_val(k, metrics[k]) for k in METRIC_KEYS]


def baseline_row(all_metrics):
    cells = ["baseline (min/median/max)"]
    for k in METRIC_KEYS:
        values = [m[k] for m in all_metrics]
        lo = min(values)
        med = statistics.median(values)
        hi = max(values)
        cells.append(f"{fmt_val(k, lo)}/{fmt_val(k, med)}/{fmt_val(k, hi)}")
    return cells


def print_markdown_table(rows):
    headers = HEADERS
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    def fmt_row(cells):
        return "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)) + " |"
    print(fmt_row(headers))
    print("| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |")
    for row in rows:
        print(fmt_row(row))


def print_csv_table(rows):
    w = csv.writer(sys.stdout)
    w.writerow(HEADERS)
    for row in rows:
        w.writerow(row)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def collect_files(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, names in os.walk(p):
                for name in sorted(names):
                    if name.lower().endswith('.md'):
                        files.append(os.path.join(root, name))
        else:
            files.append(p)
    return files


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Mechanical prose scorer for Markdown docs.")
    parser.add_argument('--csv', action='store_true', help='emit CSV instead of a Markdown table')
    parser.add_argument('--baseline', action='store_true',
                         help='append a min/median/max row over the given files')
    parser.add_argument('paths', nargs='+', metavar='PATH', help='.md file or directory')
    args = parser.parse_args()

    files = collect_files(args.paths)

    rows = []
    all_metrics = []
    for f in files:
        metrics = compute_metrics(f)
        all_metrics.append(metrics)
        rows.append(row_for(f, metrics))

    if args.baseline and all_metrics:
        rows.append(baseline_row(all_metrics))

    if args.csv:
        print_csv_table(rows)
    else:
        print_markdown_table(rows)

    return 0


if __name__ == '__main__':
    sys.exit(main())
