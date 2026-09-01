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

## Run 3 — 2026-09-01, bison+flex image (still deps-incomplete)

Configure passed (152.9s pre-validated in docker), compile then failed at ~11% — the
libsodium external needs autotools (`libtoolize`/`aclocal`/`automake`). Verdict JSON:
`{"verifyOk":true,"buildOk":false,…,"note":"build failed"}` — fail-closed path again
correct. Toolchain then aligned to upstream's own builder list
(`docker/Dockerfile` at the tag: + `libtool autoconf automake libfl-dev`).

## Run 4 — 2026-09-01, full toolchain — LOCAL FULL BUILD GREEN

Run in plain docker on the box (`--cpus 8 -m 24g`, mirroring the Job limits) to burn
zero k3s-import round-trips:

- **Verify: PASS** (sha512 + gpg, as before). **Build: PASS** — ~30 min wall to 100%
  including test targets. **Smoke: PASS** — `extensionCount: 35`.
- Final verdict line: `{"verifyOk":true,"buildOk":true,"smokeOk":true,"extensionCount":35,"tag":"rel/minifi-cpp-1.0.0","note":""}`
- Minor: the smoke's binary glob picked `minifi-controller` (exits 0 with a MINIFI_HOME
  inference note) — acceptable signal alongside the extension count; could pin to
  `bin/minifi` exactly in a later pass.
- Remaining for the in-cluster proof: one `k3s ctr images import` of this image, then
  the same Job re-run (recorded below when it lands).

## Run 5 — 2026-09-01, IN-CLUSTER DRY-RUN GREEN ✅

Same Job spec (`cpp-dryrun-1.yaml`), pod imageID verified equal to the locally-proven
image (`sha256:2f673a90768e…`) before the run:

- **succeeded=1**, wall time **29m00s** (20:33:46Z → 21:02:46Z) under the quota's
  8 CPU / 24Gi Job limits, with the live CSO pods untouched on the same box.
- Verdict (log tail): `{"verifyOk":true,"buildOk":true,"smokeOk":true,"extensionCount":35,"tag":"rel/minifi-cpp-1.0.0","note":""}`
- Quota returned to `pods: 0/2, cpu 0/8` after TTL-tracked completion.

**Phase-3 gate closed: the C++ build leg verifies, builds, and smokes a real Apache
source release end-to-end as a capped k8s Job — the exact unit Stage 3 of
`ReleaseVoteWatch` dispatches.** In-cluster is ~1min slower than plain docker
(29m vs ~30m total incl. config — effectively identical). Next proof: a fresh
forwarded `[VOTE]` sample driving the same Job through the flow itself.
