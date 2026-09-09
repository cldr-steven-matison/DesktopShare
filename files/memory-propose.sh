#!/usr/bin/env bash
# memory-propose.sh — the ONLY sanctioned way a session adds a memory (#310).
#
#   bash files/memory-propose.sh <slug> <proposal.md>
#       Validates the proposal, OPENS a new "[memory proposal] <slug>" issue that
#       summarizes the triggering event (the incident record; #247 was retired as the
#       funnel on 2026-09-09 — it stayed open too long to be usable), and registers a
#       PENDING row in .claude/.memory-proposals. It does NOT write the memory and does
#       NOT ask: the next Write/Edit to the memory path raises guard rule M's bridged ask
#       to Steven (phone first, desk fallback) carrying the fact + why the repo can't hold
#       it. Only his yes lets that write through.
#
#   bash files/memory-propose.sh --index <slug> "<one-line hook>"
#       After an approved write: mark the row WRITTEN and append the MEMORY.md pointer.
#
# Proposal file format (<= 15 body lines; the whole file <= 30 lines):
#   ---
#   name: <slug>
#   description: "<one line>"
#   metadata:
#     type: reference | project        # never feedback — lessons go to the incident file + a new issue
#   ---
#   Why the repo cannot hold it: <one line — must be a device-local fact no other device needs>
#   <the fact(s), terse>
#
# Policy: agent/incident-rules.md "Memories are not the instrument"; procedure:
# agent/local-repo-unification.md. Fails closed on validation, fails open on gh (prints
# the issue body so it can be opened by hand).
set -u
proj="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
. "$proj/.claude/hooks/lib-device.sh" 2>/dev/null || true
reg="$proj/.claude/.memory-proposals"
memdir="$HOME/.claude/projects/$(printf '%s' "$proj" | sed 's#/#-#g')/memory"

die() { echo "memory-propose: $*" >&2; exit 1; }

if [ "${1:-}" = "--index" ]; then
  slug="${2:-}"; hook="${3:-}"
  [ -n "$slug" ] && [ -n "$hook" ] || die "usage: --index <slug> \"<one-line hook>\""
  f="$memdir/$slug.md"
  [ -f "$f" ] || die "$f does not exist — the memory was never written (approved?)"
  grep -q '^approved:' "$f" || die "$f has no 'approved:' frontmatter line — add the date + the triggering-event issue URL first"
  title="$(awk -F': *' '/^name:/{gsub(/["'"'"']/,"",$2); print $2; exit}' "$f")"
  grep -qF "($slug.md)" "$memdir/MEMORY.md" 2>/dev/null || printf -- '- [%s](%s.md) — %s\n' "${title:-$slug}" "$slug" "$hook" >> "$memdir/MEMORY.md"
  if [ -f "$reg" ]; then
    awk -F'\t' -v s="$slug" -v d="$(date +%F)" 'BEGIN{OFS="\t"} $1==s {$4="WRITTEN"; $5=d} {print}' "$reg" > "$reg.tmp" && mv "$reg.tmp" "$reg"
  fi
  echo "indexed $slug in $memdir/MEMORY.md"
  exit 0
fi

slug="${1:-}"; prop="${2:-}"
[ -n "$slug" ] && [ -n "$prop" ] || die "usage: memory-propose.sh <slug> <proposal.md>   |   --index <slug> \"<hook>\""
printf '%s' "$slug" | grep -Eq '^[a-z0-9][a-z0-9-]{2,60}$' || die "slug must be kebab-case: $slug"
[ -f "$prop" ] || die "proposal file not found: $prop"

# ---- validation: this is the shape a memory is allowed to have ----
total="$(wc -l < "$prop")"
[ "$total" -le 30 ] || die "proposal is $total lines; the whole file must be <= 30"
grep -Eq '^ *type: *(reference|project) *$' "$prop" || die "metadata.type must be reference or project (never feedback — a lesson goes to the incident file + a new issue)"
grep -Eq '^ *type: *feedback' "$prop" && die "feedback memories are not allowed (#310)"
grep -q '^Why the repo cannot hold it:' "$prop" || die "missing the line 'Why the repo cannot hold it: ...'"
body="$(awk 'BEGIN{fm=0} /^---$/{fm++; next} fm>=2 {print}' "$prop" | grep -c .)"
[ "$body" -le 15 ] || die "body is $body non-empty lines; max 15 — a memory is a fact, not a narrative"
grep -Eq 'Steven (said|told|:)|"[^"]{40,}"' "$prop" && die "proposal quotes a person — memories carry facts, not quotes"
target="$memdir/$slug.md"
[ -e "$target" ] && echo "note: $target already exists — this proposal is an edit; it still needs approval at write time"

# ---- the incident record: a NEW issue summarizing the triggering event (#247 retired 2026-09-09) ----
mkdir -p "$(dirname "$reg")" 2>/dev/null
dev="$(ds_device_labels 2>/dev/null | awk '{print $1}')"; dev="${dev:-$(hostname -s)}"
body_file="$(mktemp)"
{
  printf 'Target: `%s`. Trigger: a session wanted to save a memory (#310 gate; the harness default is overridden). Approve or decline at write time on the phone/desk prompt; the fact stays in this issue either way. If it belongs in the repo rather than a memory, close this with a pointer to the doc.\n\n```markdown\n' "$target"
  cat "$prop"
  printf '\n```\n'
} > "$body_file"
url=""
if command -v gh >/dev/null 2>&1; then
  lbl=""; [ -n "$dev" ] && lbl="--label device:$dev"
  url="$(cd "$proj" && gh issue create --title "[memory proposal] $slug — $dev $(date +%F)" $lbl --label status:review --body-file "$body_file" 2>/dev/null | tail -1)"
fi
if [ -z "$url" ]; then
  echo "memory-propose: could not open the triggering-event issue (gh offline?). Open an issue titled '[memory proposal] $slug' with this body by hand, then re-run:" >&2
  cat "$body_file" >&2; rm -f "$body_file"; exit 1
fi
rm -f "$body_file"
summary="$(grep -m1 '^Why the repo cannot hold it:' "$prop" | cut -c1-200)"
fact="$(awk -F': *' '/^description:/{gsub(/["'"'"']/,"",$2); print $2; exit}' "$prop" | cut -c1-160)"
grep -v "^$slug	" "$reg" 2>/dev/null > "$reg.tmp"; mv "$reg.tmp" "$reg"
printf '%s\t%s\t%s\tPENDING\t%s\t%s | %s\n' "$slug" "$target" "$url" "$(date +%F)" "$fact" "$summary" >> "$reg"
echo "proposal registered: $url"
echo "now Write the memory to exactly: $target  (guard rule M will ask Steven; after his yes, run: bash files/memory-propose.sh --index $slug \"<one-line hook>\")"
