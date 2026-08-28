#!/bin/bash
# ~/claw-claude-do.sh — WRITE-CAPABLE headless entry point for the OpenClaw /bash bridge.
#
# Sibling of claw-claude.sh, which is read-only (analysis/planning only). This one runs a
# full task to completion — Write, Edit, git, gh — and prints the result back to Telegram.
#
# WHY THIS EXISTS (issue #267 diagnosis, 2026-08-28):
#   Headless `claude -p` does NOT emit the Notification / permission_prompt hook, so the
#   "always-fires desk ping" can never page you from a remote run. Worse, a `-p` run that
#   hits ANY normal permission prompt (e.g. a plain Write) doesn't run to completion — it
#   stops at the first one with "pending on your end" and never asks. That is exactly why
#   `claude -p "Do 267..."` did nothing from the phone: it parked at the README write with
#   no page and no completion.
#
# HOW THIS STAYS GOVERNED:
#   Runs with --dangerously-skip-permissions so it never stalls at a generic Write/commit/
#   push prompt. guard.sh is a PreToolUse hook, which DOES run under skip-permissions, so its
#   #192 phone bridge still fires on the dangerous rules (live-service restart, GET-then-PUT
#   of sensitive NiFi props, EFM agent deploy, …): it Telegrams you, waits ~180s for
#   `/bash bash ~/reply.sh yes`, and a "no" hard-denies the command. So the run is autonomous
#   on the safe mechanics and human-in-the-loop on exactly the operations guard guards.
#
# Usage (from Telegram):  /bash ~/claw-claude-do.sh Do 267 to completion, commit, push, comment
# Install:                cp files/claw-claude-do.sh ~/claw-claude-do.sh && chmod +x ~/claw-claude-do.sh
#
# CAVEATS:
#   - A long full-task run can exceed OpenClaw's poll window; !poll may time out even though
#     the run is still going — it will still print its result to Telegram when it finishes.
#   - The phone bridge needs the 127.0.0.1:8000 vllm pane up to deliver (see #192); down ⇒
#     guard falls back to the desk prompt, which a headless run can't answer, so a guard-rule
#     command would then time the hook out and PASS. Keep that pane up for unattended runs.
#   - Fresh session per invocation (no --continue): a build task shouldn't inherit prior
#     remote chat context. The SessionStart hook still runs `git pull --ff-only` first.

cd "${DS_DIR:-$HOME/DesktopShare}" || exit 1

# Load TOKEN/CHAT_ID so guard.sh's phone bridge can reach Telegram (guard reads ~/.env too).
[ -f "$HOME/.env" ] && { set -a; . "$HOME/.env"; set +a; }

exec claude -p "$*" --dangerously-skip-permissions
