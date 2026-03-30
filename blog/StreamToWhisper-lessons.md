## Lessons from the Edge: Operationalizing Whisper on Local K8s

Building a production-grade inference container for the RTX 4060 required moving past "standard" tutorials and into deep infrastructure tuning. Here are the hard-won lessons from the **StreamToWhisper** build.

### 1. The CUDA Version Pinning Trap
Standard `pip install torch` often pulls a version bundled with an older CUDA toolkit (e.g., 12.1). For modern hardware like the **G1 (RTX 4060)**, we had to explicitly target the `+cu124` index. Failure to do this results in a "Runtime Device Mismatch" where the GPU is visible but unusable.

### 2. The HF_TOKEN Performance Leak
Running "unauthenticated" requests to HuggingFace during a Docker build is a silent throttle. Without passing the `HF_TOKEN` as a `BUILD_ARG` (sourced from a Minikube Secret), we hit rate limits and gated model blocks. Authenticating the build-time download ensures high-speed model baking.

### 3. The "No-Deps" Strategy (Manual Dependency Tax)
To prevent `transformers` or `whisper` from accidentally overwriting our optimized Torch version, we used the `--no-deps` flag. This created a secondary challenge: **Recursive Dependency Failures**. We learned that FastAPI physically cannot boot without its "Web Plumbing" (`starlette`, `pydantic`, `anyio`). The fix was a hybrid install approach: letting the web stack resolve naturally while keeping the AI stack in a straightjacket.

### 4. Flash Attention 2 vs. Standard Inference
For the **Large-v3** model, standard attention is too slow for real-time streaming. Compiling `flash-attn` requires `ninja-build` and `--no-build-isolation`. This adds ~3 minutes to the build time but results in a **3x-5x throughput increase** on the 4060, allowing us to use `batch_size=24` comfortably.

### 5. Multi-Stage Build & Layer Caching
By separating the **Builder** (which contains compilers and `pip` caches) from the **Runtime** (which only contains the Venv and Model weights), we reduced the final image size and ensured that minor logic changes in `main.py` don't trigger a full 20-minute CUDA recompilation.

### 6. The Audio Codec Gap
Even with a perfect model, transcription fails if the container lacks the OS-level codecs to "read" the audio header. Including `ffmpeg` in the Runtime stage and ensuring the input audio is a clean **16kHz Mono PCM** file is the difference between a `200 OK` and a `400 Malformed` error.

---
**Hardware Verified:** RTX 4060 / WSL2 / Ubuntu 22.04 / Minikube
**Throughput:** Large-v3 Inference < 1s for 5s Audio