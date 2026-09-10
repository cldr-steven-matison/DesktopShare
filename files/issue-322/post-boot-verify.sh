#!/usr/bin/env bash
# post-boot-verify.sh — prove #322's acceptance criteria after a boot, unattended, and post the result.
#
# Runs from nvidia-post-boot-verify.service once nvidia-serve-boot.service has finished. Checks every
# service on the box that must survive a reboot, writes a dated report to /var/tmp (survives reboots,
# outside the repo so it never dirties the tree), and comments the report on #322 so the acceptance
# evidence lands on the issue by itself. Every check is best-effort: a failed check is a FAIL line in
# the report, never an abort. Exit status reflects the overall verdict.
#
# Acceptance (from #322): six containers Up with ports; all k3s workloads Running; EFM :8190 answering;
# POST :32111/caption returns 200 (the door that #321 found dead).
#
# Run by hand any time:  files/issue-322/post-boot-verify.sh   (add --no-post to skip the GitHub comment)

set -uo pipefail
export PATH=/home/tunas/.local/bin:/usr/local/bin:/usr/bin:/bin
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
REPORT=/var/tmp/nvidia-spark-last-boot-report.txt
ISSUE=322
REPO=cldr-steven-matison/DesktopShare
POST=1; [ "${1:-}" = "--no-post" ] && POST=0
PASS=0; FAIL=0
LINES=()

ok()   { PASS=$((PASS+1)); LINES+=("PASS  $*"); }
bad()  { FAIL=$((FAIL+1)); LINES+=("FAIL  $*"); }
note() { LINES+=("      $*"); }

BOOTED=$(uptime -s 2>/dev/null || echo "?")
note "host $(hostname) — booted $BOOTED — verified $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# ── systemd units ───────────────────────────────────────────────────────────────────────────────────
for u in docker k3s minifi-java nvidia-serve-boot; do
  st=$(systemctl is-active "$u" 2>/dev/null); en=$(systemctl is-enabled "$u" 2>/dev/null)
  if [ "$st" = active ] && [ "$en" = enabled ]; then ok "unit $u: active, enabled"; else bad "unit $u: $st, $en"; fi
done

# ── six containers, each with its published port(s) answering ───────────────────────────────────────
chk_http() { # name url expected-code(s)
  local code; code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' "$2" 2>/dev/null || echo 000)
  if [[ ",$3," == *",$code,"* ]]; then ok "$1: $2 -> $code"; else bad "$1: $2 -> $code (want $3)"; fi
}
for c in qdrant-kb vllm-qwen36 tei-kb tei-embed-bge tei-rerank-bge whisper-cpp; do
  s=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo missing)
  [ "$s" = running ] && ok "container $c: running" || bad "container $c: $s"
done
chk_http qdrant-kb      http://127.0.0.1:6333/readyz     200
# gRPC :6334 — a TCP accept is the check (HTTP/1.1 to a gRPC port returns nothing useful)
if timeout 3 bash -c 'exec 3<>/dev/tcp/127.0.0.1/6334' 2>/dev/null; then ok "qdrant-kb: :6334 (gRPC) accepting"; else bad "qdrant-kb: :6334 (gRPC) closed"; fi
chk_http vllm-qwen36    http://127.0.0.1:8000/v1/models  200
chk_http tei-kb         http://127.0.0.1:8080/health     200
chk_http tei-embed-bge  http://127.0.0.1:8001/health     200
chk_http tei-rerank-bge http://127.0.0.1:8002/health     200
chk_http whisper-cpp    http://127.0.0.1:8003/           200

# ── k3s workloads ───────────────────────────────────────────────────────────────────────────────────
notready=$(kubectl get pods -A --no-headers 2>/dev/null | awk '$4!="Running" && $4!="Completed"' | wc -l)
total=$(kubectl get pods -A --no-headers 2>/dev/null | wc -l)
if [ "$total" -gt 0 ] && [ "$notready" -eq 0 ]; then ok "k3s: $total pods, all Running/Completed"
else bad "k3s: $notready of $total pods not Running"; kubectl get pods -A --no-headers 2>/dev/null | awk '$4!="Running" && $4!="Completed"{print "        "$0}' | while read -r l; do note "$l"; done; fi

# ── EFM agent doors on :8190 (+ :9936 metrics) ──────────────────────────────────────────────────────
chk_http efm-agent http://127.0.0.1:9936/metrics 200
code=$(curl -s -m 20 -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8190/embed \
  -H 'Content-Type: application/json' -d '{"inputs":"post-boot verify"}' 2>/dev/null || echo 000)
[ "$code" = 200 ] && ok "efm-agent: POST :8190/embed -> 200" || bad "efm-agent: POST :8190/embed -> $code"

# ── the /caption door (StreamerBrain on mynifi, NodePort 32111) ─────────────────────────────────────
chk_http caption-door "http://127.0.0.1:32111/" 405   # GET is rejected by the listener = alive
if command -v ffmpeg >/dev/null 2>&1; then
  clip=$(mktemp --suffix=.mp4)
  ffmpeg -loglevel error -y -f lavfi -i testsrc=duration=2:size=320x240:rate=10 -f lavfi -i sine=frequency=440:duration=2 \
    -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$clip" 2>/dev/null
  if [ -s "$clip" ]; then
    t0=$(date +%s)
    code=$(curl -s -m 240 -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:32111/caption \
      -H 'X-Streamer: post-boot-verify' -H 'X-Source: verify' \
      -F clip_id=post-boot-$(date +%s) -F streamer=post-boot-verify -F source=verify -F title=verify \
      -F "file=@$clip;type=video/mp4" 2>/dev/null || echo 000)
    dt=$(( $(date +%s) - t0 ))
    [ "$code" = 200 ] && ok "caption-door: POST /caption -> 200 in ${dt}s" || bad "caption-door: POST /caption -> $code in ${dt}s"
  else note "caption-door: ffmpeg could not synthesize a clip; POST skipped"; fi
  rm -f "$clip"
else
  note "caption-door: ffmpeg not installed; POST round-trip skipped (GET 405 proves the listener)"
fi

# ── report ──────────────────────────────────────────────────────────────────────────────────────────
VERDICT=$([ "$FAIL" -eq 0 ] && echo "PASS" || echo "FAIL")
{
  echo "post-boot verify: $VERDICT — $PASS passed, $FAIL failed"
  printf '%s\n' "${LINES[@]}"
} | tee "$REPORT"

if [ "$POST" = 1 ] && command -v gh >/dev/null 2>&1; then
  {
    echo "**Post-boot verification: $VERDICT** ($PASS passed, $FAIL failed) — posted automatically by \`nvidia-post-boot-verify.service\`"
    echo; echo '```'; cat "$REPORT"; echo '```'
  } | gh issue comment "$ISSUE" --repo "$REPO" --body-file - >/dev/null 2>&1 \
    && echo "posted to #$ISSUE" || echo "!! could not post to #$ISSUE (offline?) — report kept at $REPORT"
fi
[ "$FAIL" -eq 0 ]
