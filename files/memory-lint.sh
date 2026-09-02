#!/usr/bin/env bash
# memory-lint.sh — mechanical rogue-memory checks for a device's LOCAL ~/.claude memory silo.
# Part of the local↔repo unification sweep (agent/local-repo-unification.md, #247).
#
# Usage:  bash files/memory-lint.sh [MEMDIR] [REPO]
#   MEMDIR defaults to the first ~/.claude/projects/*/memory it finds; REPO to $CLAUDE_PROJECT_DIR|$PWD.
#
# HARD findings (exit 1): dangling [[wikilinks]], dead MEMORY.md pointers, orphaned memory files.
# SOFT findings (printed, exit unaffected): repo-relative *.md paths that don't resolve — often a
# moved/renamed file, but the check is naïve so a human triages. Semantic checks — a memory that
# (a) DUPLICATES or (b) CONTRADICTS a committed repo rule — are NOT mechanical; they need a read
# (a periodic LLM audit), per agent/local-repo-unification.md.
set -u

MEMDIR="${1:-$(ls -d "$HOME"/.claude/projects/*/memory 2>/dev/null | head -1)}"
REPO="${2:-${CLAUDE_PROJECT_DIR:-$PWD}}"
[ -n "$MEMDIR" ] && [ -d "$MEMDIR" ] || { echo "memory dir not found: '${MEMDIR:-}'"; exit 2; }
[ -f "$MEMDIR/MEMORY.md" ] || { echo "no MEMORY.md in $MEMDIR"; exit 2; }
cd "$MEMDIR" || exit 2

canon() { tr '_' '-'; }
fail=0

echo "== memory-lint: $MEMDIR (repo: $REPO) =="
echo "body memories: $(ls *.md | grep -v '^MEMORY.md$' | wc -l)"

# 1. MEMORY.md pointers must resolve (bare local filenames only; a path is a repo ref, checked later)
dead="$(grep -oE '\]\([A-Za-z0-9_.-]+\.md\)' MEMORY.md | sed -E 's/^\]\(//; s/\)$//' \
        | while read -r p; do [ -f "$p" ] || echo "$p"; done)"
if [ -n "$dead" ]; then echo "HARD — dead MEMORY.md pointers:"; echo "$dead" | sed 's/^/  /'; fail=1; fi

# 2. Orphans: a body memory with no MEMORY.md pointer
orph="$(for f in $(ls *.md | grep -v '^MEMORY.md$'); do grep -q "($f)" MEMORY.md || echo "$f"; done)"
if [ -n "$orph" ]; then echo "HARD — memory files with no MEMORY.md pointer:"; echo "$orph" | sed 's/^/  /'; fail=1; fi

# 3. Dangling [[wikilinks]] — resolve against filename OR frontmatter name:, hyphen/underscore-normalized
avail="$(for f in $(ls *.md | grep -v '^MEMORY.md$'); do
           echo "${f%.md}" | canon
           awk -F': *' '/^name:/{gsub(/["'"'"']/,"",$2); print $2; exit}' "$f" | canon
         done | sort -u)"
dangle="$(grep -rhoE '\[\[[A-Za-z0-9_./-]+\]\]' *.md | sed -E 's/^\[\[//; s/\]\]$//' | canon | sort -u \
          | while read -r s; do grep -qxF "$s" <(printf '%s\n' "$avail") || echo "$s"; done)"
if [ -n "$dangle" ]; then echo "HARD — dangling [[wikilinks]] (no matching memory):"; echo "$dangle" | sed 's/^/  [[/; s/$/]]/'; fail=1; fi

# 4. SOFT: repo-relative *.md paths mentioned in memories that don't exist in the repo (moved/renamed?)
stale="$(grep -rhoE '[A-Za-z0-9_][A-Za-z0-9_/-]*\.md' *.md | sort -u | while read -r p; do
           case "$p" in (*/*) ;; (*) continue ;; esac      # only path-like refs (bare filenames handled above)
           case "$p" in (com/*|*github*|http*) continue ;; esac
           [ -e "$REPO/$p" ] || echo "$p"
         done)"
if [ -n "$stale" ]; then
  echo "SOFT — *.md paths not found under $REPO (triage: moved file, other-repo path, or fine):"
  echo "$stale" | sed 's/^/  ? /'
fi

echo "-- memory-lint: $([ "$fail" = 0 ] && echo CLEAN || echo "FINDINGS") --"
exit "$fail"
