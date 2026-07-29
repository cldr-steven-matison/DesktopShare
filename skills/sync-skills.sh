#!/usr/bin/env bash
# Skill auto-sync. Keeps ~/.claude/skills/<name> current with this repo's
# skills/<name>, using the git tree hash as the version marker so nobody has to
# remember to bump a number (the failure mode this replaces: a manual `cp -r`
# that a session forgets, leaving a stale local copy that silently wins).
#
# Version marker: `git rev-parse HEAD:skills/<name>` (the committed tree hash).
# After `git pull` brings a newer skill, that hash changes; we detect the drift
# and re-copy repo -> installed. We never copy installed -> repo, and we only
# touch skills THIS repo provides (dirs under skills/ that have a SKILL.md).
#
# Fails OPEN throughout (always exit 0): a missing git, a detached/empty tree, an
# unwritable ~/.claude/skills, or a failed copy must never block a session.
# Prints one line per skill synced; silent when everything is already current.
# The SessionStart hook (.claude/hooks/checkin.sh) calls this after the pull.

set -u

proj="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$proj" ] || exit 0
cd "$proj" 2>/dev/null || exit 0

command -v git >/dev/null 2>&1 || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

dest="$HOME/.claude/skills"
mkdir -p "$dest" 2>/dev/null || exit 0

for dir in skills/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || continue                 # only real skills, not README etc.

  want="$(git rev-parse "HEAD:skills/$name" 2>/dev/null)" || continue
  [ -n "$want" ] || continue

  have="$(cat "$dest/$name/.synced-from" 2>/dev/null || echo none)"
  [ "$want" = "$have" ] && continue                  # already current

  rm -rf "$dest/$name" 2>/dev/null
  if cp -r "skills/$name" "$dest/" 2>/dev/null; then
    printf '%s\n' "$want" > "$dest/$name/.synced-from" 2>/dev/null
    echo "skill-sync: updated ${name} (${have:0:8} -> ${want:0:8})"
  fi
done

exit 0
