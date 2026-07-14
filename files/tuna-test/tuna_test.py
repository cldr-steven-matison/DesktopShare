#!/usr/bin/env python3
"""Standalone Phase A test: ffmpeg overlay + vLLM tuna commentary + HeyGen Avatar IV.

Not part of cso-operator-app — a manual test harness per
cso-operator-app-streamers-tuna.md's Execution Order steps 1-2, run by hand
before any of this touches services/streamers.py.

Requires (see Setup in the plan):
  - kubectl port-forward svc/vllm-service 8000:8000   (already running)
  - kubectl port-forward svc/whisper-service 8001:8001
  - HEYGEN_API_KEY and HEYGEN_AVATAR_ID exported in the environment
"""
import html
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
# The real base clip to react to/overlay onto — NOT Avatar_Video.mp4, which is
# the tuna mascot's own reference art/video used to build the HeyGen avatar.
INPUT_VIDEO = HERE / "input" / "sample_clip.mp4"
OUTPUT_DIR = HERE / "output"
PERSONA_FILE = HERE / "persona.txt"

VLLM_URL = "http://127.0.0.1:8000"
VLLM_MODEL = "Qwen/Qwen2.5-3B-Instruct"  # matches what vllm-server actually serves
WHISPER_URL = "http://127.0.0.1:8001"

def _load_env_local() -> dict:
    """Parse KEY=VALUE lines from .env.local (gitignored) — same pattern as
    cso-operator-app/backend/.env.example, so credentials never touch git or chat."""
    env_file = HERE / ".env.local"
    values = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


_env_local = _load_env_local()
HEYGEN_API_KEY = os.environ.get("HEYGEN_API_KEY") or _env_local.get("HEYGEN_API_KEY", "")
HEYGEN_AVATAR_ID = os.environ.get("HEYGEN_AVATAR_ID") or _env_local.get("HEYGEN_AVATAR_ID", "")
HEYGEN_BASE = "https://api.heygen.com"

OVERLAY_HEIGHT_FRACTION = 0.28  # fraction of base clip HEIGHT the tuna overlay occupies.
# Height, not width: the HeyGen output is a tall portrait clip (720x1280) while
# real stream clips are landscape/16:9-ish — sizing off width made the overlay
# scale to ~70% of frame height ("old video and new one over each other").
# Sizing off height instead gives a normal small corner-bug look.
OVERLAY_MARGIN = 24  # pixels from the corner


def probe_video_dims(path: Path) -> tuple[int, int]:
    """ffprobe width/height — same technique as _probe_video_dims in streamers.py."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        capture_output=True, timeout=30,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return int(stream["width"]), int(stream["height"])


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, timeout=30,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def transcribe(clip_path: Path) -> str:
    """Extract 16kHz mono WAV, POST to Whisper — identical to process_clip's whisper block."""
    wav_path = clip_path.with_suffix(".wav")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(clip_path), "-vn", "-ac", "1", "-ar", "16000", str(wav_path)],
        capture_output=True, timeout=60,
    )
    if proc.returncode != 0 or not wav_path.exists():
        raise RuntimeError(f"ffmpeg wav extraction failed: {proc.stderr.decode(errors='replace')[:300]}")
    try:
        with open(wav_path, "rb") as f:
            r = requests.post(f"{WHISPER_URL}/transcribe", files={"file": ("clip.wav", f, "audio/wav")}, timeout=120)
        r.raise_for_status()
        return r.json().get("text", "").strip()
    finally:
        wav_path.unlink(missing_ok=True)


def clean_line(text: str) -> str:
    """Strip model formatting artifacts — same approach as _clean_caption in streamers.py."""
    text = html.unescape(text).strip()
    text = text.split("\n\n")[0].strip()
    text = re.sub(r'^\*{0,2}[\w][\w ]*\*{0,2}:\s*', '', text)
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s*#\w+', '', text)
    text = re.sub(r'\s*@\w+', '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


# Hard content-safety gate. Small local models will sometimes pick up slurs
# or slang straight from a garbled transcript instead of filtering it out —
# this must be checked BEFORE anything reaches HeyGen, since HeyGen turns the
# text into a spoken video with the mascot's own likeness/voice. This is a
# blunt word-boundary blocklist, not a substitute for real moderation — if it
# trips, the run aborts and nothing gets sent to HeyGen. No silent retry: a
# trip here means the prompt/persona needs a human look, not a second guess.
_DISALLOWED_TERMS = [
    r"nigg\w*", r"fagg\w*", r"chink\w*", r"spic\w*", r"kike\w*",
    r"retard\w*", r"tranny", r"wetback\w*", r"beaner\w*", r"coon\w*",
    r"cunt\w*",
]
_DISALLOWED_RE = re.compile(r"\b(" + "|".join(_DISALLOWED_TERMS) + r")\b", re.IGNORECASE)


def contains_disallowed_content(text: str) -> bool:
    return bool(_DISALLOWED_RE.search(text))


def generate_tuna_line(transcript: str, attempts: int = 4) -> str:
    """Ask vLLM for the tuna's line, retrying if the safety gate trips.

    This transcript's source audio is confrontational slang, and the model
    tends to mirror that register instead of filtering it — lower temperature
    plus an explicit reminder in the user turn (not just the system prompt)
    cuts down on that; the retry loop covers the cases those don't."""
    persona = PERSONA_FILE.read_text()
    last_line = ""
    for attempt in range(1, attempts + 1):
        r = requests.post(
            f"{VLLM_URL}/v1/chat/completions",
            json={
                "model": VLLM_MODEL,
                "messages": [
                    {"role": "system", "content": persona},
                    {"role": "user", "content": (
                        "React in character to this clip's transcript with one short spoken line. "
                        "Stay grounded in the transcript's situation, but do NOT quote or mimic any "
                        "crude language, slurs, or profanity in it — keep your own line clean regardless "
                        "of the source tone. Do not invent facts.\n\n"
                        f"Transcript: {transcript[:600]}"
                    )},
                ],
                "max_tokens": 60,
                "temperature": 0.6,
            },
            timeout=60,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        line = clean_line(raw)
        if not contains_disallowed_content(line):
            return line
        print(f"    [attempt {attempt}/{attempts}] safety gate tripped on {line!r}, retrying...")
        last_line = line
    raise RuntimeError(
        f"Refusing to continue: {attempts} attempts all tripped the content-safety gate "
        f"(last: {last_line!r}). Nothing was sent to HeyGen. Adjust persona.txt/prompt and rerun."
    )


def heygen_generate_video(script: str) -> str:
    """Submit an Avatar IV generation job, poll until done, return the video_url."""
    if not HEYGEN_API_KEY or not HEYGEN_AVATAR_ID:
        raise RuntimeError("HEYGEN_API_KEY and HEYGEN_AVATAR_ID must be set in the environment")
    headers = {"x-api-key": HEYGEN_API_KEY, "Content-Type": "application/json"}
    body = {
        "type": "avatar",
        "avatar_id": HEYGEN_AVATAR_ID,
        "script": script,
        "engine": {"type": "avatar_iv"},
        "aspect_ratio": "9:16",
    }
    r = requests.post(f"{HEYGEN_BASE}/v3/videos", headers=headers, json=body, timeout=30)
    r.raise_for_status()
    video_id = r.json()["data"]["video_id"]
    print(f"    HeyGen job submitted: {video_id}")

    poll_url = f"{HEYGEN_BASE}/v3/videos/{video_id}"
    for attempt in range(60):  # up to ~5 minutes at 5s intervals
        time.sleep(5)
        r = requests.get(poll_url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()["data"]
        status = data.get("status")
        print(f"    poll {attempt + 1}: status={status}")
        if status == "completed":
            return data["video_url"]
        if status == "failed":
            raise RuntimeError(f"HeyGen generation failed: {data}")
    raise RuntimeError("HeyGen generation timed out after 5 minutes")


def download(url: str, dest: Path) -> None:
    r = requests.get(url, timeout=120, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            f.write(chunk)


def burn_tuna_overlay(base_clip: Path, tuna_clip: Path, dest: Path) -> None:
    """Composite the HeyGen video onto the bottom-left corner of the base clip —
    same filter_complex/overlay technique as _burn_platform_overlay in streamers.py."""
    _base_w, base_h = probe_video_dims(base_clip)
    tuna_duration = probe_duration(tuna_clip)

    overlay_h = round(base_h * OVERLAY_HEIGHT_FRACTION / 2) * 2  # keep even for libx264

    filter_complex = (
        f"[1:v]scale=-2:{overlay_h}[tuna];"
        f"[0:v][tuna]overlay=x={OVERLAY_MARGIN}:y=H-h-{OVERLAY_MARGIN}:"
        f"enable='between(t,0,{tuna_duration})'[vout];"
        f"[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-threads", "1",
            "-i", str(base_clip), "-i", str(tuna_clip),
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-threads", "1", "-c:v", "libx264", "-preset", "veryfast",
            "-x264opts", "threads=1:sliced-threads=0",
            "-crf", "23", "-c:a", "aac", "-movflags", "+faststart",
            str(dest),
        ],
        capture_output=True, timeout=240,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg overlay failed: {result.stderr.decode(errors='replace')[-1000:]}")


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    if not INPUT_VIDEO.exists():
        sys.exit(f"Input clip not found: {INPUT_VIDEO}")

    print("1/4 Transcribing base clip with Whisper...")
    transcript = transcribe(INPUT_VIDEO)
    (OUTPUT_DIR / "transcript.txt").write_text(transcript)
    print(f"    transcript: {transcript[:200]!r}")

    print("2/4 Generating tuna commentary line with vLLM...")
    tuna_line = generate_tuna_line(transcript)
    (OUTPUT_DIR / "tuna_line.txt").write_text(tuna_line)
    print(f"    tuna line: {tuna_line!r}")

    print("3/4 Calling HeyGen Avatar IV (this costs credits and takes real time)...")
    video_url = heygen_generate_video(tuna_line)
    heygen_video = OUTPUT_DIR / "heygen_video.mp4"
    download(video_url, heygen_video)
    print(f"    downloaded: {heygen_video}")

    print("4/4 Compositing tuna overlay onto base clip with ffmpeg...")
    final_video = OUTPUT_DIR / "final_composited.mp4"
    burn_tuna_overlay(INPUT_VIDEO, heygen_video, final_video)
    print(f"    done: {final_video}")


if __name__ == "__main__":
    main()
