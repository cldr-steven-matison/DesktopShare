#!/usr/bin/env python3
"""HeyGen POC for issue #50: SRM avatar reads a script describing how to
install Cloudera Streaming Operators. Submit -> poll -> download, same call
shape as files/tuna-test/tuna_test.py's heygen_generate_video/download, just
without the vLLM/Whisper/ffmpeg-overlay steps this POC doesn't need — the
whole video IS the output, not an overlay onto other footage.

Requires HEYGEN_API_KEY / HEYGEN_AVATAR_ID / HEYGEN_VOICE_ID in .env.local
(gitignored) or the environment.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SCRIPT_FILE = HERE / "script.txt"
OUTPUT_DIR = HERE / "output"
HEYGEN_BASE = "https://api.heygen.com"


def _load_env_local() -> dict:
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
HEYGEN_VOICE_ID = os.environ.get("HEYGEN_VOICE_ID") or _env_local.get("HEYGEN_VOICE_ID", "")


def heygen_generate_video(script: str) -> str:
    """Submit an Avatar IV generation job, poll until done, return the video_url."""
    if not HEYGEN_API_KEY or not HEYGEN_AVATAR_ID:
        raise RuntimeError("HEYGEN_API_KEY and HEYGEN_AVATAR_ID must be set in .env.local or the environment")
    headers = {"x-api-key": HEYGEN_API_KEY, "Content-Type": "application/json"}
    body = {
        "type": "avatar",
        "avatar_id": HEYGEN_AVATAR_ID,
        "script": script,
        "engine": {"type": "avatar_iv"},
        "aspect_ratio": "16:9",
        "resolution": "1080p",
    }
    if HEYGEN_VOICE_ID:
        body["voice_id"] = HEYGEN_VOICE_ID
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


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    if not SCRIPT_FILE.exists():
        sys.exit(f"Script file not found: {SCRIPT_FILE}")
    script = SCRIPT_FILE.read_text().strip()

    print("1/2 Calling HeyGen Avatar IV (this costs credits and takes real time)...")
    video_url = heygen_generate_video(script)
    dest = OUTPUT_DIR / "cso_install_intro.mp4"
    print("2/2 Downloading result...")
    download(video_url, dest)
    print(f"    done: {dest}")


if __name__ == "__main__":
    main()
