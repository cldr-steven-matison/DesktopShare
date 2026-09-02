#!/usr/bin/env bash
# Issue #76 — Maven build-leg entrypoint (NiFi API / NAR Maven Plugin; core NiFi stays
# deferred — multi-hour). Runs in stock maven:3.9-eclipse-temurin-21 (arm64), mounted
# from the maven-build-entrypoint ConfigMap at /entry. Same env contract + verdict JSON
# as cpp-build/entrypoint.sh; "extensionCount" carries the built-jar count so the flow's
# Stage-4 scrape stays leg-agnostic.
#
# Env: TAG, ARTIFACT_URL (file or staging-dir URL), SHA512 (falls back to the .sha512
# file), KEYS_URL, GIT_REPO (apache/nifi-api | apache/nifi-maven — clone fallback only).
set -uo pipefail
mkdir -p /work && cd /work

TAG="${TAG:-}"; ARTIFACT_URL="${ARTIFACT_URL:-}"; SHA512="${SHA512:-}"
KEYS_URL="${KEYS_URL:-https://dist.apache.org/repos/dist/release/nifi/KEYS}"
GIT_REPO="${GIT_REPO:-apache/nifi}"

VERIFY_OK=false; BUILD_OK=false; SMOKE_OK=false; JAR_COUNT=0; NOTE=""

finish() {
  printf '{"verifyOk":%s,"buildOk":%s,"smokeOk":%s,"extensionCount":%s,"tag":"%s","note":"%s"}\n' \
    "$VERIFY_OK" "$BUILD_OK" "$SMOKE_OK" "$JAR_COUNT" "$TAG" "$NOTE"
  [ "$VERIFY_OK" = true ] && [ "$BUILD_OK" = true ] && exit 0 || exit 1
}
trap finish EXIT

# stock temurin/maven images ship without curl/gpg — pull them in once at start
if ! command -v curl >/dev/null || ! command -v gpg >/dev/null; then
  apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq curl gnupg ca-certificates >/dev/null 2>&1 \
    || { NOTE="toolchain install failed (curl/gnupg)"; exit 1; }
fi

echo "== resolve source artifact =="
SRC_ARCHIVE=""
if [ -n "$ARTIFACT_URL" ]; then
  case "$ARTIFACT_URL" in
    *.tar.gz|*.zip) SRC_ARCHIVE="$ARTIFACT_URL" ;;
    *) SRC_ARCHIVE=$(curl -fsSL "${ARTIFACT_URL%/}/" \
         | grep -oE 'href="[^"]*-source[^"]*\.(tar\.gz|zip)"' \
         | head -1 | sed 's/^href="//; s/"$//')
       [ -n "$SRC_ARCHIVE" ] && SRC_ARCHIVE="${ARTIFACT_URL%/}/${SRC_ARCHIVE##*/}" ;;
  esac
fi

if [ -n "$SRC_ARCHIVE" ]; then
  echo "== verify: $SRC_ARCHIVE =="
  ARCHIVE_FILE="${SRC_ARCHIVE##*/}"
  curl -fsSL "$KEYS_URL" -o KEYS               || { NOTE="KEYS fetch failed"; exit 1; }
  gpg -q --import KEYS 2>/dev/null             || { NOTE="KEYS import failed"; exit 1; }
  curl -fsSL "$SRC_ARCHIVE" -o "$ARCHIVE_FILE" || { NOTE="artifact fetch failed"; exit 1; }
  if [ -z "$SHA512" ]; then
    SHA512=$(curl -fsSL "$SRC_ARCHIVE.sha512" | grep -oE '[0-9a-fA-F]{128}' | head -1)
  fi
  echo "$SHA512  $ARCHIVE_FILE" | sha512sum -c -        || { NOTE="sha512 mismatch"; exit 1; }
  curl -fsSL "$SRC_ARCHIVE.asc" -o "$ARCHIVE_FILE.asc"  || { NOTE="asc fetch failed"; exit 1; }
  gpg --verify "$ARCHIVE_FILE.asc" "$ARCHIVE_FILE"      || { NOTE="gpg verify failed"; exit 1; }
  VERIFY_OK=true
  echo "== extract verified source =="
  mkdir -p /src-extract
  case "$ARCHIVE_FILE" in
    *.tar.gz) tar -xzf "$ARCHIVE_FILE" -C /src-extract ;;
    *.zip)    (cd /src-extract && jar -xf "/work/$ARCHIVE_FILE") ;;   # jar extracts zips; unzip isn't in the image
  esac
  SRC_DIR=$(find /src-extract -mindepth 1 -maxdepth 1 -type d | head -1)
  # a source-release zip may extract flat (no top dir)
  [ -n "$SRC_DIR" ] || { ls /src-extract/pom.xml >/dev/null 2>&1 && SRC_DIR=/src-extract; }
else
  echo "== no source artifact — cloning $GIT_REPO at $TAG =="
  NOTE="tag-only build, no artifact verification"
  command -v git >/dev/null || apt-get install -y -qq git >/dev/null 2>&1
  git clone --branch "$TAG" --depth 1 "https://github.com/$GIT_REPO.git" /src-git \
    || { NOTE="git clone failed"; exit 1; }
  SRC_DIR=/src-git
fi
[ -n "${SRC_DIR:-}" ] || { NOTE="no source dir after extract"; exit 1; }

echo "== maven build ($SRC_DIR) =="
cd "$SRC_DIR"
MVN=mvn; [ -x ./mvnw ] && MVN=./mvnw
$MVN -B clean install || { NOTE="maven build failed"; exit 1; }
BUILD_OK=true

echo "== smoke =="
JAR_COUNT=$(find . -path '*/target/*.jar' ! -name '*-sources.jar' ! -name '*-javadoc.jar' | wc -l)
[ "$JAR_COUNT" -gt 0 ] && SMOKE_OK=true || NOTE="${NOTE:+$NOTE; }no jars produced"
echo "jars built: $JAR_COUNT"
