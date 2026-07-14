**Plan: Local Cartoon Tuna Mascot — Clips First, Live Co-Host Second**

**Project Goal**
An original cartoon tuna mascot (name/look TBD — not modeled on any existing commercial character) that reacts in character to what's happening on stream: short, punchy, voiced commentary, synced to a simple animated visual. Two rollout phases, deliberately in this order:

- **Phase A — Clip overlay (build first).** Burned onto already-recorded clips in the existing Tuna Street Streams pipeline (`cso-operator-app`), fully offline/batch. Lowest risk, fastest to something real, and proves out the character/voice before any live-audio complexity.
- **Phase B — Live stream co-host (after A works).** A real-time version running locally on the Beelink SER9 Pro during the actual stream, reusing the persona, voice, and visual assets Phase A already built and validated.

Everything stays local and free — no cloud LLM/TTS/avatar-generation calls for either phase, and no per-generation cost. (A HeyGen-based version of Phase A was prototyped and worked, but was dropped in favor of this fully local route — see the Session Log below and `heygen-avatar-api.md` if that path is ever revisited.)

---

## Shared Foundation (build once, reuse in both phases)

- **Persona / system prompt** — original writing. Pick 2-3 personality traits (e.g. loud, easily distracted, tuna-pun-obsessed) and write a short system prompt around them, with an explicit rule to never use slurs/profanity/hate speech regardless of source material tone (see safety-gate finding below — this is not optional). This is the one piece of writing that stays identical across Phase A and Phase B, so the mascot reads as the same character in a clip and live. It also becomes the prompt vLLM uses to write the per-clip *script* that gets spoken — one prompt, two consumers.
- **Voice — now identical across both phases.** Both Phase A and Phase B synthesize speech with **Piper** (local TTS), the same voice model file in both places. This is a simplification from the earlier HeyGen-based design, which needed a separate cloud voice for Phase A and a "look-matched" local voice for Phase B — with everything local now, there's only one voice to pick, ever.
- **Visual asset — one photo, not a frame set.** A local lip-sync model (Wav2Lip or SadTalker — see Phase A) generates the talking video from a single source image + the Piper audio.
  - Needs a **clean, solid (or removable) background**, not the transparent-checkerboard-style artwork used during prototyping — that checkerboard is baked into any exported video as literal pixels, not real alpha, so it has to be cropped or chroma-keyed out downstream either way. Cleanest fix is a version of the mascot art on a plain/green background so a simple crop or chroma-key does the job.
  - Phase A feeds this photo + audio straight into the lip-sync model.
  - Phase B still needs its own cheap 2-3 mouth-shape PNGs, since neither Wav2Lip nor SadTalker run fast enough for a live loop (both are batch/offline-oriented, same constraint HeyGen had) — pull a clean frame from a Phase A-generated video as the base for those, so the two phases look like the same character instead of being drawn twice.
  - **Full Live2D/VTube Studio rig is optional and deferred indefinitely** — only worth the time investment once the cheap version has proven people actually want to watch this. Don't start there.

---

## Phase A: Clip Overlay (build first)

This is the easier problem by a wide margin: a clip's transcript and duration are already fully known in advance, so there's no real-time constraint, no audio feedback-loop risk, and no risk of missing stream audio while the pipeline "thinks." It's a batch step, not a live loop.

**Where it lives**: `cso-operator-app`'s `services/streamers.py`, in the same processing stage that already burns the platform bar and glitch intro onto every clip (`_burn_platform_overlay`, `_burn_glitch_intro`) — same ffmpeg-overlay pattern, one more step in the chain.

**Per-clip pipeline** (fully local/offline — no external API calls):

1. Reuse the Whisper transcript already captured for that clip (it's already produced for the existing tweet-caption step — no new transcription work needed).
2. A new, separate vLLM prompt (distinct from the existing tweet-caption prompt) asks for one short in-character line reacting to the transcript — this becomes the **script**. Keep it short, a couple seconds spoken, not a monologue. **Must pass through a content-safety gate before going any further** — see the safety-gate finding below; the 3B model has been observed generating real slurs when reacting to rough transcripts.
3. **Piper** synthesizes the script into audio locally.
4. **Wav2Lip or SadTalker** (pick one during setup — see Execution Order) generates a lip-synced video from the mascot photo + that audio. Runs on the same local GPU already serving vLLM. Not instant — budget real wall-clock render time per clip, similar order of magnitude to what HeyGen needed, but GPU-time-bounded rather than credit-bounded, so there's no per-generation dollar cost to gate against.
5. ffmpeg: overlay the generated video onto a corner of the clip. **Size it off the base clip's height, not width** — the lip-sync output is portrait while real clips are landscape/16:9-ish, and sizing off width was measured to cover ~70% of frame height instead of reading as a small corner bug. Mix its audio into the clip's own track.
6. **Trigger timing / duration**: since generation is no longer credit-metered, a full-clip-duration presence (tuna stays on screen the whole clip, reacts at more than one point) is back on the table and worth designing for properly, rather than the single-short-line-then-gone approach the HeyGen prototype used to control cost. Still an open design question — see below.

**Open questions to settle before building:**
- The mascot's actual photo (name, look) — your call, this is the one genuinely creative piece. Needs a clean/solid-background version for compositing (see Shared Foundation).
- Tone/personality for the system prompt — a placeholder draft exists at `files/tuna-test/persona.txt` from the prototype, ready to be tuned further.
- Wav2Lip vs. SadTalker — which one to standardize on; try both on one clip during setup and compare quality/speed.
- Whether the tuna stays visible for the whole clip (vs. one short window) and whether the script should react at multiple points through the clip instead of a single line at the start — no longer cost-constrained the way it was under HeyGen, so this is worth designing properly now instead of deferring.
- Where the tuna's audio should sit relative to the clip's own audio — full mix, or a brief duck of the original audio while the tuna talks.

---

## Phase B: Live Stream Co-Host (after Phase A proves the character out)

Once the persona, voice, and visual read well on clips, the same pieces move to a real-time loop on the Beelink.

**Target Stack**
- **OS**: Windows 11 (Beelink SER9 Pro)
- **Streaming**: OBS Studio + obs-websocket
- **LLM**: Ollama (local) — reuse the exact system prompt from Phase A
- **STT**: faster-whisper (real-time)
- **TTS**: Piper — same voice model file as Phase A (no translation step needed now — it's literally the same voice)
- **Visual**: Phase A's mouth-swap frames as a browser source first; Live2D/VTube Studio only if/when that's proven worth it
- **Orchestration**: single Python 3.12+ script (`tuna_brain.py`)
- **Audio Routing**: VB-Audio Virtual Cable
- **Automation Glue**: Python + asyncio + websockets

**Repo Structure (Recommended)**
```
stream-tuna-ai/
├── tuna_brain.py              # Main orchestrator script
├── config.yaml                # All settings (model, intervals, emotions, etc.)
├── prompts/
│   └── tuna_system.txt        # Same persona prompt as Phase A
├── assets/
│   └── mouth_frames/          # Same PNG frames used in Phase A's ffmpeg overlay
├── tts/
│   └── models/                # Same Piper voice model as Phase A
├── logs/
├── requirements.txt
└── README.md
```

### Phase 0: Prerequisites (One-Time Setup)
1. Install **Ollama** → `winget install Ollama.Ollama`
2. Pull a model:
   ```bash
   ollama pull llama3.2
   ```
3. Install **VB-Audio Virtual Cable**.
4. Confirm which OBS websocket protocol version is in use before picking a client library — modern OBS (28+) defaults to obs-websocket **v5**, which needs `obsws-python`, not the older `obs-websocket-py` (v4-only). Get this wrong and it fails silently.
5. Install Python 3.12+ and create a venv.
6. Install packages (note: `asyncio` is stdlib, not a pip package — drop it from requirements):
   ```bash
   pip install faster-whisper ollama piper-tts obsws-python websockets pyyaml sounddevice
   ```
7. Reuse the Piper voice model from Phase A.

### Phase 1: Reuse the Phase A persona prompt
Same `prompts/tuna_system.txt` as Phase A — don't rewrite it. Add the response-format contract on top:
```
Always respond in this exact format:
COMMENT: [your short commentary in character]
EMOTION: [neutral | excited | annoyed | happy]

Keep responses under 25 words.
```

### Phase 2: Audio Listening + Real-Time STT
- `sounddevice` + `faster-whisper`, capture from the Virtual Cable's stream-audio output.
- **Important**: the tuna's own TTS output must go out on a *different* route than the one STT listens on, or it'll start reacting to its own commentary. Route TTS playback directly to OBS/speakers, never back through the STT input cable.
- Run transcription on a fixed interval or VAD — fixed interval is simpler for v1 but will sometimes cut mid-sentence; that's an acceptable v1 tradeoff, not a bug to chase.

### Phase 3: LLM Call + Emotion Parsing
- Feed recent transcription + last few tuna comments to Ollama each cycle.
- Parse `EMOTION:` to pick which mouth-frame/expression state to show; send `COMMENT:` to the TTS queue.

### Phase 4: TTS Playback
- Piper synthesizes the COMMENT text; play through OBS.
- Drive the mouth-frame swap off the playing audio's amplitude, same logic as Phase A's ffmpeg version, just live instead of baked-in.

### Phase 5: Visual (start with Phase A's assets)
- Browser source swapping the same mouth-frame PNGs used in Phase A, driven by playback amplitude.
- Live2D/VTube Studio is a later upgrade, not a v1 requirement.

### Phase 6: Full Automation Loop
```python
while True:
    audio_chunk = capture_stream_audio(15)          # seconds
    transcription = whisper.transcribe(audio_chunk)
    llm_response = ollama.generate(transcription + context)
    emotion, comment = parse_response(llm_response)

    tts_audio = piper.synthesize(comment)
    play_audio_in_obs(tts_audio)                     # never routed back into STT input

    update_mascot_frame(emotion)                     # swap mouth/expression frame
    await asyncio.sleep(20)                          # configurable interval
```
**Known limitation, not a bug**: this loop is sequential — while transcribing/generating/synthesizing, it isn't listening. Fine for an occasional-commentary sidekick; worth a note in the README so it isn't "discovered" later as a mystery gap.

### Configurability
Put in `config.yaml`: `listen_interval_seconds`, `emotion_mappings`, `max_comment_length`, `voice_model_path`, `whisper_model_size`.

---

## Execution Order (Recommended)

1. Set up **Wav2Lip and/or SadTalker** locally on the GPU already serving vLLM. Get the mascot photo (clean/solid background), pick a Piper voice, and make **one manual lip-sync generation** outside the pipeline entirely — confirm quality and real generation latency before writing any pipeline code.
2. **Phase A end to end**, one clip, manually triggered — persona prompt → vLLM script (through the safety gate) → Piper TTS → Wav2Lip/SadTalker → ffmpeg overlay burned in. Get this looking/sounding right before touching anything live.
3. Wire Phase A into the real ProcessClips pipeline so it runs automatically. No cost-based gating needed now (unlike the HeyGen design) — the constraint is GPU render time, not credits, so it can reasonably run on every processed clip.
4. Only then start Phase B, reusing the persona prompt and the same Piper voice/mouth-frames derived from Phase A's output.
5. Live2D/VTube Studio, if ever — last, optional, after Phase B's cheap version is running and worth upgrading.

---

## Session Log — Execution Order step 1-2, prototyped manually (standalone, outside the app)

A working standalone prototype was built at `/home/tunas/DesktopShare/files/tuna-test/` (Whisper transcribe → vLLM commentary → HeyGen Avatar IV → ffmpeg overlay) to validate the character/voice/pipeline shape before writing any pipeline code, per the Execution Order above. It used **HeyGen** for the avatar-video step at the time; that choice was since replaced with the free/local Wav2Lip-or-SadTalker route described above, so the HeyGen-specific API details were moved out to `heygen-avatar-api.md` (kept for reference in case a paid service is ever revisited). The findings below are the parts that carry forward regardless of which generation method is used:

**Findings — still applicable to the local route:**
- **Safety gap (important, must be in the real pipeline, not just a prototype script)**: the 3B model, reacting to a rough/aggressive transcript, generated real slurs on 3 of 4 attempts in one run. Nothing in `process_clip`'s existing caption path (in `services/streamers.py`) filters for this today. The prototype added a hard word-boundary blocklist gate + bounded retry + an explicit no-slurs rule in the persona prompt — this needs to live in `services/streamers.py` itself once Phase A is wired in for real, since whatever text comes out of vLLM ends up as spoken audio one way or another.
- The original sample file used for early testing (`Avatar_Video.mp4`) was **not** a stream clip — it was the tuna's own reference art/video. The actual base clip for overlay testing must be a real fetched clip from `/clips`.
- Overlay sizing must be computed off frame **height**, not width — the avatar-video output is portrait (720x1280) while real clips are landscape/16:9-ish; sizing off width made the overlay cover ~70% of frame height instead of reading as a small corner bug. (Carries over directly to Wav2Lip/SadTalker output, which will have the same portrait-vs-landscape mismatch.)
- Any avatar-video output with a "transparent" background is not a real alpha channel — it's baked into the pixels as a checkerboard (or whatever the source photo's background was). Whatever tool generates the video, plan to crop or chroma-key, not alpha-composite.
- Tested end-to-end on a real clip copied from prod `/clips` (read-only): small, bottom-left overlay, appearing only during its spoken line and gone afterward — mechanically correct positioning/timing logic to reuse.

**Separately found and fixed, live production bug** (unrelated to the mascot work, found while testing): `backend/config.py` and `k8s/configmap.yaml` both still had `VLLM_MODEL` set to the old `Qwen/Qwen2.5-1.5B-Instruct` after `vllm-server` was upgraded to the 3B model — every vLLM call in `process_clip` (title + caption) was 404ing against the live server, silently swallowed by the existing try/except, so ProcessClips returned HTTP 200 with empty/error captions on every clip. Fixed both files to `Qwen/Qwen2.5-3B-Instruct`, rebuilt and redeployed via `make deploy MODULES=rag,streamers`, confirmed the new pod calls vLLM successfully.
