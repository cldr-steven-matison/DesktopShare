#!/usr/bin/env python3
"""HeyGen SRM avatar: submit -> poll -> download.

Cheap draft vs final:
  HEYGEN_ENGINE=avatar_iii   # cheap / lip-sync only (default for draft checks)
  HEYGEN_ENGINE=avatar_iv    # expressive face/head (previous POC default)
  HEYGEN_ENGINE=avatar_v     # highest-fidelity / most expressive (final, costs more)

  HEYGEN_ASPECT=9:16         # tall mobile (default for this X intro)
  HEYGEN_ASPECT=16:9         # landscape
  HEYGEN_OUT=name.mp4        # output filename under output/ (default: video.mp4)

Requires HEYGEN_API_KEY / HEYGEN_AVATAR_ID / HEYGEN_VOICE_ID in .env.local
(gitignored) or the environment.
"""
import os
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SCRIPT_FILE = HERE / "script.txt"
OUTPUT_DIR = HERE / "output"
HEYGEN_BASE = "https://api.heygen.com"

VALID_ENGINES = ("avatar_iii", "avatar_iv", "avatar_v")


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
HEYGEN_ENGINE = (
    os.environ.get("HEYGEN_ENGINE")
    or _env_local.get("HEYGEN_ENGINE")
    or "avatar_iii"
).strip().lower()
HEYGEN_ASPECT = (
    os.environ.get("HEYGEN_ASPECT")
    or _env_local.get("HEYGEN_ASPECT")
    or "9:16"
).strip()
HEYGEN_OUT = os.environ.get("HEYGEN_OUT") or _env_local.get("HEYGEN_OUT") or "video.mp4"


def heygen_generate_video(script: str) -> str:
    """Submit a generation job, poll until done, return the video_url."""
    if not HEYGEN_API_KEY or not HEYGEN_AVATAR_ID:
        raise RuntimeError(
            "HEYGEN_API_KEY and HEYGEN_AVATAR_ID must be set in .env.local or the environment"
        )
    if HEYGEN_ENGINE not in VALID_ENGINES:
        raise RuntimeError(f"HEYGEN_ENGINE must be one of {VALID_ENGINES}, got {HEYGEN_ENGINE!r}")

    headers = {"x-api-key": HEYGEN_API_KEY, "Content-Type": "application/json"}
    body = {
        "type": "avatar",
        "avatar_id": HEYGEN_AVATAR_ID,
        "script": script,
        "engine": {"type": HEYGEN_ENGINE},
        "aspect_ratio": HEYGEN_ASPECT,
        "resolution": "1080p",
    }
    if HEYGEN_VOICE_ID:
        body["voice_id"] = HEYGEN_VOICE_ID

    r = requests.post(f"{HEYGEN_BASE}/v3/videos", headers=headers, json=body, timeout=30)
    r.raise_for_status()
    video_id = r.json()["data"]["video_id"]
    print(f"    HeyGen job submitted: {video_id}  engine={HEYGEN_ENGINE} aspect={HEYGEN_ASPECT}")

    poll_url_v3 = f"{HEYGEN_BASE}/v3/videos/{video_id}"
    poll_url_v1 = f"{HEYGEN_BASE}/v1/video_status.get"
    for attempt in range(90):  # up to ~7.5 minutes at 5s intervals
        time.sleep(5)
        data = None
        try:
            r = requests.get(poll_url_v3, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()["data"]
        except Exception as e:
            # Known gotcha: v3 poll can 500 on a completed job — fall back to v1.
            print(f"    poll {attempt + 1}: v3 error ({e}); trying v1 fallback")
            r = requests.get(
                poll_url_v1,
                headers=headers,
                params={"video_id": video_id},
                timeout=30,
            )
            r.raise_for_status()
            payload = r.json()
            data = payload.get("data") or payload

        status = data.get("status")
        print(f"    poll {attempt + 1}: status={status}")
        if status == "completed":
            url = data.get("video_url") or data.get("video_url_caption")
            if not url:
                raise RuntimeError(f"completed but no video_url in response: {data}")
            return url
        if status == "failed":
            raise RuntimeError(f"HeyGen generation failed: {data}")
    raise RuntimeError("HeyGen generation timed out after ~7.5 minutes")


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
    word_count = len(script.split())
    print(f"Script: {word_count} words (~{word_count / 2.5:.0f}s at 150 wpm)")
    print(f"1/2 Calling HeyGen ({HEYGEN_ENGINE}, {HEYGEN_ASPECT}) — costs credits...")
    video_url = heygen_generate_video(script)
    dest = OUTPUT_DIR / HEYGEN_OUT
    print(f"2/2 Downloading result -> {dest.name}")
    download(video_url, dest)
    print(f"    done: {dest}")


if __name__ == "__main__":
    main()
