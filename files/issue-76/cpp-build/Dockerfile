# Issue #76 — MiNiFi C++ release-candidate build image (aarch64).
# Toolchain recipe from the EFM guide's ch05 source-build path (EdgeFlowManager
# repo, ch05-executescript-availability.md), plus gnupg/curl for the verify
# gates. The RC tag/artifact are RUNTIME env vars (TAG, ARTIFACT_URL, SHA512,
# KEYS_URL) read by the entrypoint — one image serves every RC.
#
# Build + import into k3s (this box):
#   docker build -t release-build-cpp:0.1 files/issue-76/cpp-build/
#   sudo bash -c 'docker save release-build-cpp:0.1 | k3s ctr images import -'
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git ca-certificates \
    python3-dev lua5.3 liblua5.3-dev \
    libssl-dev libcurl4-openssl-dev libarchive-dev \
    bison flex libfl-dev libtool autoconf automake \
    perl pkg-config patch gnupg curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
