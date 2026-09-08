#!/usr/bin/env bash
# relabel-closed-issues.sh [--dry-run]
#
# A CLOSED issue must carry status:done and nothing else from the status:* set
# (agent/device-comms.md "Closing an issue"). 2026-09-08 audit (#247/#310): 25 closed
# issues still carried status:todo|in-progress|review, four of them next to status:done,
# because guard.sh rule 6's old auto-flip removed only the FIRST status label. This
# strips every stale status:* label from every closed issue and adds status:done.
# Idempotent. --dry-run lists what would change.
set -u
dry=""; [ "${1:-}" = "--dry-run" ] && dry=1
repo="${DS_REPO:-cldr-steven-matison/DesktopShare}"
stale='^status:(todo|in-progress|review|blocked)$'
n=0
gh issue list -R "$repo" --state closed --limit 500 --json number,labels \
  --jq '.[] | select([.labels[].name] | any(test("^status:(todo|in-progress|review|blocked)$"))) | "\(.number) \([.labels[].name]|join(","))"' \
| while read -r num labels; do
    rm=""; for l in $(printf '%s' "$labels" | tr ',' ' '); do printf '%s' "$l" | grep -Eq "$stale" && rm="$rm --remove-label $l"; done
    add=""; printf '%s' "$labels" | grep -q '(^|,)status:done(,|$)' || add="--add-label status:done"
    printf '%s' "$labels" | grep -Eq '(^|,)status:done(,|$)' || add="--add-label status:done"
    n=$((n+1))
    if [ -n "$dry" ]; then
      echo "#$num [$labels] ->$rm ${add:+$add}"
    else
      # shellcheck disable=SC2086
      if gh issue edit "$num" -R "$repo" $rm $add >/dev/null 2>&1; then echo "#$num fixed:$rm ${add}"; else echo "#$num FAILED"; fi
    fi
  done
