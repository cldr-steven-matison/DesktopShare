#!/bin/bash
# ~/claw-claude.sh — headless remote entry point for the OpenClaw /bash bridge (#192).
#
# Runs a fresh, non-interactive Claude Code turn against DesktopShare and prints the
# result back to Telegram. Read-only by construction: --permission-mode dontAsk means
# any tool NOT in the allowlist is denied and the run continues and reports, so a
# remote turn can never sit parked on a permission prompt. AskUserQuestion is denied
# outright under dontAsk, so a headless turn won't try to ask either.
#
# Usage (from Telegram):  /bash ~/claw-claude.sh <your prompt>
# Install:                cp files/claw-claude.sh ~/claw-claude.sh && chmod +x ~/claw-claude.sh
#
# --continue chains context across messages (see agent-to-agent.md "Session Continuity").
# Writes and pushes are deliberately absent from the allowlist — headless remote work is
# analysis and planning only.

cd "${DS_DIR:-$HOME/DesktopShare}" || exit 1

claude --continue -p "$*" \
  --permission-mode dontAsk \
  --allowedTools "Read" "Grep" "Glob" \
    "Bash(git pull)" "Bash(git log *)" "Bash(git status *)" "Bash(git diff *)" \
    "Bash(kubectl get *)" "Bash(kubectl logs *)"
