# whisper.cpp with CUDA for GB10 (sm_121) — the STT tier on NvidiaSpark-1.
#
# The GB10 gotcha the research corpus records (nvidia-dgx-spark-research.md §Whisper):
#   * CMAKE_CUDA_ARCHITECTURES must be "120;121", NOT "121" and NOT "120" alone — plain 120 targets
#     sm_120a and fails on GB10 with "no kernel image available"; the forum thread quotes the error.
#   * Ubuntu 24.04 base is required — DGX OS ships GLIBC 2.38 and 22.04 containers carry 2.35.
#   * nvcr.io/nvidia/cuda has no ARM64 tags — use Docker Hub's nvidia/cuda (sbsa/arm64).
# faster-whisper/CTranslate2 is the upstream that has NO CUDA-13/aarch64/sm_121 support (the gap that
# forces this source build); whisper.cpp builds clean with the flag above.
FROM nvidia/cuda:13.0.1-devel-ubuntu24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
      git cmake build-essential libcurl4-openssl-dev ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*
# curl is the runtime dep too: entrypoint.sh's download-ggml-model.sh needs curl/wget in the image
# (the cuda -devel base ships neither). Pre-staging the model into the mounted /models also satisfies it.

RUN git clone --depth 1 https://github.com/ggml-org/whisper.cpp /whisper.cpp
WORKDIR /whisper.cpp
# The -devel image ships the CUDA driver stub (libcuda) under lib64/stubs, not on the default link
# path — without it the ggml-cuda shared lib link leaves cuMem*/cuDevice* (CUDA Driver API) undefined.
# Put the stubs dir on LIBRARY_PATH and force -lcuda into both link steps. The stub's SONAME is
# libcuda.so.1, so at runtime the real driver injected by --gpus all takes over transparently.
ENV LIBRARY_PATH=/usr/local/cuda/lib64/stubs:${LIBRARY_PATH}
RUN cmake -B build -DGGML_CUDA=1 -DCMAKE_CUDA_ARCHITECTURES="120;121" -DWHISPER_SDL2=OFF \
      -DCMAKE_EXE_LINKER_FLAGS="-L/usr/local/cuda/lib64/stubs -lcuda" \
      -DCMAKE_SHARED_LINKER_FLAGS="-L/usr/local/cuda/lib64/stubs -lcuda" \
 && cmake --build build --config Release -j --target whisper-server

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
