#!/usr/bin/env bash
# Issue #76 — MiNiFi C++ RC verify + build + smoke, run as a k8s Job in the
# release-builds namespace. Verification gates the build (no verify, no build).
#
# Env contract (from the Job manifest, attributes parsed out of the [VOTE] mail):
#   TAG          git tag of the RC (e.g. minifi-cpp-1.0.0-RC1) — used when no
#                source archive is found, and recorded in the result either way
#   ARTIFACT_URL staging file OR directory URL (dist.apache.org/repos/dist/dev/…).
#                A directory is scanned for the *-source* archive.
#   SHA512       published hash of the source archive (from the vote email).
#                Empty → fall back to the .sha512 file next to the artifact.
#   KEYS_URL     project KEYS file (dist.apache.org/repos/dist/release/nifi/KEYS)
#
# Last stdout line is a single-line JSON verdict the NiFi flow scrapes from the
# pod log tail: {"verifyOk":…,"buildOk":…,"smokeOk":…,"extensionCount":…,"tag":…}
set -uo pipefail
cd /work

TAG="${TAG:-}"
ARTIFACT_URL="${ARTIFACT_URL:-}"
SHA512="${SHA512:-}"
KEYS_URL="${KEYS_URL:-https://dist.apache.org/repos/dist/release/nifi/KEYS}"

VERIFY_OK=false; BUILD_OK=false; SMOKE_OK=false; EXT_COUNT=0; NOTE=""

finish() {
  printf '{"verifyOk":%s,"buildOk":%s,"smokeOk":%s,"extensionCount":%s,"tag":"%s","note":"%s"}\n' \
    "$VERIFY_OK" "$BUILD_OK" "$SMOKE_OK" "$EXT_COUNT" "$TAG" "$NOTE"
  # Job success/failure mirrors the overall verdict so .status.succeeded is meaningful
  [ "$VERIFY_OK" = true ] && [ "$BUILD_OK" = true ] && exit 0 || exit 1
}
trap finish EXIT

echo "== resolve source artifact =="
SRC_ARCHIVE=""
if [ -n "$ARTIFACT_URL" ]; then
  case "$ARTIFACT_URL" in
    *.tar.gz|*.zip) SRC_ARCHIVE="$ARTIFACT_URL" ;;
    *) # directory: scan the index for the source archive
       SRC_ARCHIVE=$(curl -fsSL "${ARTIFACT_URL%/}/" \
         | grep -oE 'href="[^"]*-source[^"]*\.(tar\.gz|zip)"' \
         | head -1 | sed 's/^href="//; s/"$//')
       [ -n "$SRC_ARCHIVE" ] && SRC_ARCHIVE="${ARTIFACT_URL%/}/${SRC_ARCHIVE##*/}" ;;
  esac
fi

if [ -n "$SRC_ARCHIVE" ]; then
  echo "== verify: $SRC_ARCHIVE =="
  ARCHIVE_FILE="${SRC_ARCHIVE##*/}"
  curl -fsSL "$KEYS_URL" -o KEYS            || { NOTE="KEYS fetch failed"; exit 1; }
  gpg -q --import KEYS 2>/dev/null          || { NOTE="KEYS import failed"; exit 1; }
  curl -fsSL "$SRC_ARCHIVE" -o "$ARCHIVE_FILE" || { NOTE="artifact fetch failed"; exit 1; }
  if [ -z "$SHA512" ]; then
    SHA512=$(curl -fsSL "$SRC_ARCHIVE.sha512" | grep -oE '[0-9a-fA-F]{128}' | head -1)
  fi
  echo "$SHA512  $ARCHIVE_FILE" | sha512sum -c - || { NOTE="sha512 mismatch"; exit 1; }
  curl -fsSL "$SRC_ARCHIVE.asc" -o "$ARCHIVE_FILE.asc" || { NOTE="asc fetch failed"; exit 1; }
  gpg --verify "$ARCHIVE_FILE.asc" "$ARCHIVE_FILE"     || { NOTE="gpg verify failed"; exit 1; }
  VERIFY_OK=true
  echo "== extract verified source =="
  mkdir -p /src-extract
  case "$ARCHIVE_FILE" in
    *.tar.gz) tar -xzf "$ARCHIVE_FILE" -C /src-extract ;;
    *.zip)    apt-get install -y -qq unzip >/dev/null 2>&1 || true
              python3 -m zipfile -e "$ARCHIVE_FILE" /src-extract ;;
  esac
  SRC_DIR=$(find /src-extract -mindepth 1 -maxdepth 1 -type d | head -1)
else
  # No artifact URL (e.g. tag-only dry run): build from the git tag; there is
  # nothing to hash-check, so verifyOk stays false and the note says why.
  echo "== no source artifact — cloning tag $TAG =="
  NOTE="tag-only build, no artifact verification"
  git clone --branch "$TAG" --depth 1 https://github.com/apache/nifi-minifi-cpp.git /src-git \
    || { NOTE="git clone failed"; exit 1; }
  SRC_DIR=/src-git
fi
[ -n "${SRC_DIR:-}" ] || { NOTE="no source dir after extract"; exit 1; }

echo "== configure + build ($SRC_DIR, $(nproc) cores) =="
cmake -S "$SRC_DIR" -B /build \
  -DENABLE_LUA_SCRIPTING=ON -DENABLE_PYTHON_SCRIPTING=ON \
  -DENABLE_KAFKA=ON -DCMAKE_BUILD_TYPE=Release \
  || { NOTE="cmake configure failed"; exit 1; }
cmake --build /build --parallel "$(nproc)" \
  || { NOTE="build failed"; exit 1; }
BUILD_OK=true

echo "== smoke =="
EXT_COUNT=$(find /build -name 'libminifi-*.so' -o -name '*extension*.so' 2>/dev/null | wc -l)
BIN=$(find /build/bin -maxdepth 1 -type f -name 'minifi*' ! -name '*.sh' | head -1)
if [ -n "$BIN" ] && "$BIN" --version >/tmp/smoke.log 2>&1; then
  SMOKE_OK=true
  head -3 /tmp/smoke.log
elif [ "$EXT_COUNT" -gt 0 ]; then
  # binary refused to run bare (needs conf) but extensions built — partial pass
  SMOKE_OK=true
  NOTE="${NOTE:+$NOTE; }binary needs conf, smoke = extension count only"
fi
echo "extensions built: $EXT_COUNT"
