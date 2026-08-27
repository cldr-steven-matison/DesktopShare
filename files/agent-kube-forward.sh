#!/bin/bash
# Usage:
#   bash files/agent-kube-forward.sh add   <name> -- <kubectl port-forward args...>
#   bash files/agent-kube-forward.sh swap  <name> -- <kubectl port-forward args...>
#   bash files/agent-kube-forward.sh drop  <name>
#   bash files/agent-kube-forward.sh list
#
#   flags (before the subcommand):
#     --session <zellij-session>   override autodetect (default: the single live session)
#     --no-kdl                     touch only the live session, leave the .kdl alone
#
# WHY THIS EXISTS (issue #255, 2026-08-26):
# Every change to the canonical forward set used to mean killing and relaunching the
# zellij session -- the whole EFM/Kafka/Mosquitto array dropped for the restart and
# Steven had to answer the `minikube tunnel` sudo prompt again. It happened twice in one
# evening during the #253 cutover. Steven: "i hate zellij restart". This adds/swaps/drops
# ONE forward against the RUNNING session while every other pane stays up, and keeps the
# .kdl (source of truth for the *next* launch) in sync so the two agree afterwards.
#
# HOW A PANE IS CREATED AND TORN DOWN (verified live 2026-08-27):
#   * `zellij --session S run -c --name N -- bash -lc '<wrapper>'` opens the pane and the
#     `-c` (close-on-exit) means the pane vanishes the instant its command exits.
#   * The wrapper writes its own bash PID to a pidfile, then runs the SAME retry loop the
#     .kdl uses (byte-identical, so a script-made pane looks like a launch-made one).
#   * `drop` reads that pidfile and kills the loop (+ any child kubectl). The command
#     exits -> `-c` reaps the pane. We NEVER use `zellij action close-pane`: it closes
#     whatever pane is *focused*, and in a detached session that is unknowable -- doing so
#     once already closed the wrong pane during this feature's own bring-up.
#   * `dump-layout` does NOT list detached-run panes, so it is not used as an inventory;
#     the pidfiles under $STATE_DIR are the record of what this script manages.

set -u

REPO="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
KDL="${KUBE_FORWARD_KDL:-$HOME/.config/zellij/layouts/kube-service-ports-efm.kdl}"
STATE_DIR="${KUBE_FORWARD_STATE:-$HOME/.config/zellij/forwards.d}"
KUBECTL="/usr/local/bin/kubectl"
LOOP_TAIL="; echo '[pane] forward exited -- retrying in 5s'; sleep 5; done"

SESSION=""
DO_KDL=1

die() { echo "❌ $*" >&2; exit 1; }

# --- flag parsing (flags precede the subcommand) ---------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --session) SESSION="${2:-}"; shift 2 || die "--session needs a value" ;;
        --no-kdl)  DO_KDL=0; shift ;;
        --) shift; break ;;
        -*) die "unknown flag: $1" ;;
        *) break ;;
    esac
done

CMD="${1:-}"; shift 2>/dev/null || true

command -v zellij >/dev/null 2>&1 || die "zellij is not on PATH."

# --- session autodetect: the single non-EXITED zellij session --------------------
detect_session() {
    [ -n "$SESSION" ] && { echo "$SESSION"; return; }
    local live
    live="$(zellij list-sessions 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | grep -v 'EXITED' | awk '{print $1}')"
    local n; n="$(printf '%s\n' "$live" | grep -c .)"
    [ "$n" -eq 0 ] && die "no live zellij session found -- launch kube-service-ports-efm first."
    [ "$n" -gt 1 ] && die "more than one live session; pass --session <name>:"$'\n'"$live"
    printf '%s\n' "$live"
}

slug() { printf '%s' "$1" | tr '/:. ' '____'; }
pidfile() { printf '%s/%s.pid' "$STATE_DIR" "$(slug "$1")"; }

# --- live-session ops ------------------------------------------------------------
live_add() {
    local name="$1"; shift
    local fwd="$*"
    local S PF; S="$(detect_session)" || exit 1; PF="$(pidfile "$name")"
    mkdir -p "$STATE_DIR"
    local wrapper="echo \$\$ > '$PF'; while true; do $KUBECTL port-forward $fwd$LOOP_TAIL"
    local out; out="$(zellij --session "$S" run -c --name "$name" -- bash -lc "$wrapper" 2>&1)"
    case "$out" in
        terminal_*) echo "▶️  added '$name' -> $S ($out): kubectl port-forward $fwd" ;;
        *) die "zellij run failed for '$name': $out" ;;
    esac
}

live_drop() {
    local name="$1" PF; PF="$(pidfile "$name")"
    [ -f "$PF" ] || { echo "ℹ️  no pidfile for '$name' -- not managed by this script (nothing to kill)."; return 1; }
    local pid; pid="$(cat "$PF" 2>/dev/null)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        pkill -TERM -P "$pid" 2>/dev/null   # the child kubectl, if mid-run
        kill "$pid" 2>/dev/null             # the retry loop -> command exits -> -c reaps the pane
        echo "⏹️  dropped '$name' (killed loop pid $pid; pane closes on exit)."
    else
        echo "ℹ️  '$name' loop pid ${pid:-?} already gone."
    fi
    rm -f "$PF"
}

# --- .kdl sync (name-keyed, block-structured) ------------------------------------
# A managed pane block is exactly:
#         pane name="<NAME>" {
#             command "bash"
#             args "-lc" "while true; do /usr/local/bin/kubectl port-forward <FWD>; echo ...; sleep 5; done"
#         }
kdl_block() {   # $1=name $2..=fwd  -> prints the 4-line block (8-space indent, matching the file)
    local name="$1"; shift
    printf '        pane name="%s" {\n' "$name"
    printf '            command "bash"\n'
    printf '            args "-lc" "while true; do %s port-forward %s%s"\n' "$KUBECTL" "$*" "$LOOP_TAIL"
    printf '        }\n'
}

kdl_has() { grep -qF "pane name=\"$1\"" "$KDL" 2>/dev/null; }

kdl_set() {   # replace the args line of an existing named block, or append a new block
    local name="$1"; shift
    [ -f "$KDL" ] || { echo "⚠️  kdl $KDL missing -- skipping kdl sync."; return; }
    cp -f "$KDL" "$KDL.bak"
    if kdl_has "$name"; then
        local newargs; newargs="$(printf '            args "-lc" "while true; do %s port-forward %s%s"' "$KUBECTL" "$*" "$LOOP_TAIL")"
        awk -v name="$name" -v newargs="$newargs" '
            $0 ~ ("pane name=\"" name "\"") { inblk=1 }
            inblk && $0 ~ /^[[:space:]]*args "-lc"/ { print newargs; inblk=0; next }
            inblk && /}/ { inblk=0 }
            { print }
        ' "$KDL.bak" > "$KDL"
        echo "📝 kdl: replaced args for '$name'."
    else
        # append as a top-level pane before the final closing brace (a new column next launch)
        awk -v blk="$(kdl_block "$name" "$@")" '
            { lines[NR]=$0 }
            END {
                for (i=1;i<NR;i++) print lines[i]
                print blk
                print lines[NR]
            }
        ' "$KDL.bak" > "$KDL"
        echo "📝 kdl: appended new pane '$name'."
    fi
}

kdl_del() {   # remove the named block (brace-balanced from the pane line)
    local name="$1"
    [ -f "$KDL" ] || return
    kdl_has "$name" || { echo "ℹ️  kdl: no pane '$name' to remove."; return; }
    cp -f "$KDL" "$KDL.bak"
    awk -v name="$name" '
        $0 ~ ("pane name=\"" name "\"") && !skip { skip=1; depth=0 }
        skip {
            depth += gsub(/{/,"{"); depth -= gsub(/}/,"}")
            if (depth<=0) skip=0
            next
        }
        { print }
    ' "$KDL.bak" > "$KDL"
    echo "📝 kdl: removed pane '$name'."
}

# --- dispatch --------------------------------------------------------------------
case "$CMD" in
    add)
        name="${1:-}"; shift 2>/dev/null || true
        [ "${1:-}" = "--" ] && shift
        [ -n "$name" ] && [ $# -gt 0 ] || die "usage: add <name> -- <port-forward args...>"
        [ -f "$(pidfile "$name")" ] && kill -0 "$(cat "$(pidfile "$name")" 2>/dev/null)" 2>/dev/null \
            && die "'$name' already managed and alive -- use swap to change it."
        live_add "$name" "$@"
        [ "$DO_KDL" = 1 ] && kdl_set "$name" "$@"
        ;;
    swap)
        name="${1:-}"; shift 2>/dev/null || true
        [ "${1:-}" = "--" ] && shift
        [ -n "$name" ] && [ $# -gt 0 ] || die "usage: swap <name> -- <port-forward args...>"
        live_drop "$name" || true
        sleep 1
        live_add "$name" "$@"
        [ "$DO_KDL" = 1 ] && kdl_set "$name" "$@"
        ;;
    drop)
        name="${1:-}"
        [ -n "$name" ] || die "usage: drop <name>"
        live_drop "$name" || true
        [ "$DO_KDL" = 1 ] && kdl_del "$name"
        ;;
    list)
        S="$(detect_session)" || exit 1
        echo "session: $S"
        echo "managed forwards (pidfiles in $STATE_DIR):"
        shopt -s nullglob
        found=0
        for f in "$STATE_DIR"/*.pid; do
            found=1
            pid="$(cat "$f" 2>/dev/null)"
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then st="alive ($pid)"; else st="DEAD"; fi
            printf '  %-40s %s\n' "$(basename "$f" .pid)" "$st"
        done
        [ "$found" = 0 ] && echo "  (none yet)"
        ;;
    *)
        die "usage: agent-kube-forward.sh [--session S] [--no-kdl] {add|swap|drop|list} ..."
        ;;
esac
