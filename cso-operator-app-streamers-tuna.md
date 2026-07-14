**Plan: Local Cartoon Tuna Mascot — Clips First, Live Co-Host Second**

**Project Goal**
An original cartoon tuna mascot (name/look TBD — not modeled on any existing commercial character) that reacts in character to what's happening on stream: short, punchy, voiced commentary, synced to a simple animated visual. Two rollout phases, deliberately in this order:

- **Phase A — Clip overlay (build first).** Burned onto already-recorded clips in the existing Tuna Street Streams pipeline (`cso-operator-app`), fully offline/batch. Lowest risk, fastest to something real, and proves out the character/voice before any live-audio complexity.
- **Phase B — Live stream co-host (after A works).** A real-time version running locally on the Beelink SER9 Pro during the actual stream, reusing the persona, voice, and visual assets Phase A already built and validated.

Everything stays local — no cloud LLM/TTS calls for either phase.

---

## Shared Foundation (build once, reuse in both phases)

- **Persona / system prompt** — original writing. Pick 2-3 personality traits (e.g. loud, easily distracted, tuna-pun-obsessed) and write a short system prompt around them. This is the one piece of writing that should stay identical across Phase A and Phase B, so the mascot reads as the same character in a clip and live.
- **Voice** — one local TTS voice (Piper works for both an offline batch job and a real-time loop). Same voice file used in both phases.
- **Visual asset — start cheap.** A static image plus 2-3 mouth-shape frames (closed / mid / open) is enough for a convincing talking effect when swapped in time with the TTS audio's amplitude. This works for *both* phases:
  - Phase A: ffmpeg overlays the frame sequence onto the clip video.
  - Phase B: a browser source in OBS swaps the same frames live, driven off the TTS audio as it plays.
  - **Full Live2D/VTube Studio rig is optional and deferred indefinitely** — only worth the time investment once the cheap version has proven people actually want to watch this. Don't start there.

---

## Phase A: Clip Overlay (build first)

This is the easier problem by a wide margin: a clip's transcript and duration are already fully known in advance, so there's no real-time constraint, no audio feedback-loop risk, and no risk of missing stream audio while the pipeline "thinks." It's a batch step, not a live loop.

**Where it lives**: `cso-operator-app`'s `services/streamers.py`, in the same processing stage that already burns the platform bar and glitch intro onto every clip (`_burn_platform_overlay`, `_burn_glitch_intro`) — same ffmpeg-overlay pattern, one more step in the chain.

**Per-clip pipeline (all offline, no new infra beyond what's already running in-cluster):**

1. Reuse the Whisper transcript already captured for that clip (it's already produced for the existing tweet-caption step — no new transcription work needed).
2. A new, separate vLLM prompt (distinct from the existing tweet-caption prompt) asks for one short in-character line reacting to the transcript. Keep it short — a couple seconds of TTS audio, not a monologue.
3. TTS the line locally (Piper) to a short WAV.
4. ffmpeg: overlay the mascot's mouth-frame sequence (selected per time-window from the WAV's amplitude) onto a corner of the clip for exactly the line's duration, and mix the TTS audio into the clip's own track.
5. **Trigger timing**: start simple — right after the glitch snap-back (a beat that already exists in every clip today), one line, fixed short duration. Don't try to time it to specific transcript content yet.

**Open questions to settle before building:**
- Exact mascot visual (name, look, the 2-3 mouth frames) — your call, this is the one genuinely creative piece.
- Tone/personality for the system prompt.
- Where the TTS line should sit relative to the clip's own audio — full mix, or a brief duck of the original audio while the tuna talks.

---

## Phase B: Live Stream Co-Host (after Phase A proves the character out)

Once the persona, voice, and visual read well on clips, the same pieces move to a real-time loop on the Beelink.

**Target Stack**
- **OS**: Windows 11 (Beelink SER9 Pro)
- **Streaming**: OBS Studio + obs-websocket
- **LLM**: Ollama (local) — reuse the exact system prompt from Phase A
- **STT**: faster-whisper (real-time)
- **TTS**: Piper — same voice model file as Phase A
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

1. **Phase A end to end**, one clip, manually triggered — persona prompt, TTS line, mouth-frame overlay burned in. Get this looking/sounding right before touching anything live.
2. Wire Phase A into the real ProcessClips pipeline so it runs on every new clip automatically.
3. Only then start Phase B, reusing everything Phase A already validated (prompt, voice, visual frames).
4. Live2D/VTube Studio, if ever — last, optional, after Phase B's cheap version is running and worth upgrading.
