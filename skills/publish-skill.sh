#!/usr/bin/env bash
# Publish the nifi-and-ai skill from DesktopShare -> the public NiFiandAi repo.
#
# ONE DIRECTION ONLY: repo -> public. This never pulls public content back into
# DesktopShare, mirroring sync-skills.sh's "repo is the source of truth" model.
# The public repo's own README.md is preserved; only SKILL.md + references/ sync.
#
# The skill in skills/nifi-and-ai/ is the sanitized, external-friendly copy — it
# carries no device names, internal paths, issue numbers, or topology. Keep it that
# way: anything you add to the skill must be safe to publish, because this pushes it.
#
# Usage: bash skills/publish-skill.sh
# Requires: gh/git auth for github.com and push rights on the NiFiandAi repo.

set -euo pipefail

REPO_URL="https://github.com/cldr-steven-matison/NiFiandAi.git"
proj="$(git rev-parse --show-toplevel 2>/dev/null)"
SRC="$proj/skills/nifi-and-ai"
[ -f "$SRC/SKILL.md" ] || { echo "publish-skill: $SRC/SKILL.md not found"; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone --depth 1 "$REPO_URL" "$WORK" 2>/dev/null || {
  echo "publish-skill: cannot clone $REPO_URL (create it first / check auth)"; exit 1; }

# Sync skill content only. README.md and .git in the public repo are left untouched.
rm -rf "$WORK/references"
cp "$SRC/SKILL.md" "$WORK/SKILL.md"
cp -r "$SRC/references" "$WORK/references"

cd "$WORK"
if [ -z "$(git status --porcelain)" ]; then
  echo "publish-skill: NiFiandAi already current — nothing to push"
  exit 0
fi
git add -A
git commit -m "sync nifi-and-ai skill from DesktopShare" >/dev/null
git push origin HEAD
echo "publish-skill: pushed skill update to $REPO_URL"
