# Issue #76 — C++ build-leg dry-run record (real released tag, no live vote)

Target: **nifi-minifi-cpp 1.0.0** GA source release —
`https://downloads.apache.org/nifi/nifi-minifi-cpp/1.0.0/nifi-minifi-cpp-1.0.0-source.tar.gz`,
published sha512 passed inline in the Job env exactly as a `[VOTE]` mail would carry it
(`test/cpp-dryrun-1.yaml`).

## Run 1 — 2026-09-01, image `release-build-cpp:0.1` (first build)

- **Verify gates: PASS** — `sha512sum -c` OK; `gpg: Good signature` from the RM key
  `EB2F8D74…E596197A` (Martin Zink, imported from the project KEYS). The web-of-trust
  "key is not certified" warning is expected — same thing a human verifier sees.
- **Build: FAIL at cmake configure** — `Could NOT find BISON` (ExpressionLanguage.cmake
  needs bison + flex; the ch05 toolchain list predates the 1.x line and didn't carry them).
- Job behaved as designed: `backoffLimit: 0`, pod `Error`, verdict JSON as the last log line:
  `{"verifyOk":true,"buildOk":false,"smokeOk":false,"extensionCount":0,"tag":"rel/minifi-cpp-1.0.0","note":"cmake configure failed"}`
  — i.e. the fail-closed path works end to end.
- **Fix:** `bison flex` added to `cpp-build/Dockerfile`; configure stage re-validated locally
  in docker before re-importing the image into k3s (one sudo import per image, so dependency
  hunting happens in docker, not in Job round-trips).

## Run 2 — 2026-09-01, stale-image false start

Re-applied the Job seconds before the fixed image's `k3s ctr images import` landed, so the
pod ran the old image and failed at bison again in ~4 min. No new information — noted only
because `imagePullPolicy: Never` + a same-tag re-import means *pod creation time vs import
time* decides which bits run; check `kubectl get node -o json | jq .status.images` ordering
or just relaunch after the import is confirmed.

## Run 3 — 2026-09-01, fixed image (bison + flex)

Configure stage pre-validated in plain docker (152.9s, clean). Job relaunched on the
imported fix; result recorded below when the build completes.
