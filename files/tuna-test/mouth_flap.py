#!/usr/bin/env python3
"""Amplitude-driven mouth animation for the blank-face tuna mascot.

No ML lip-sync model — draws a simple eye (static) and a mouth shape whose
height tracks the audio's RMS amplitude envelope, frame by frame, then muxes
with the source audio via ffmpeg. Cheapest tier from the mascot backlog doc:
static clip-art + amplitude-driven mouth-shape swap.

Usage: mouth_flap.py <base_png> <audio_wav> <output_mp4>
"""
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

FPS = 25

# Tuned by eye against tuna_blank_transparent.png (1024x559) — see the
# matching-crop comparison against the eyed reference image in the session
# that built this. Adjust here if a different base image is ever swapped in.
EYE_CENTER = (667, 231)
EYE_RADIUS = 17
BLINK_EVERY_FRAMES = 60   # ~2.4s at 25fps — more frequent so it's easy to spot
BLINK_DURATION_FRAMES = 7

# Real lip art (Steven's reference sprite, split at the seam) instead of a
# drawn shape — see assets/lip_upper.png / lip_lower.png, cropped from
# assets/tuna_lips_ref_transparent.png. The lips-ref render's head geometry
# isn't pixel-identical to tuna_blank_transparent.png's, so position is
# re-derived by aligning the lip sprite's tip point to this image's own
# snout tip (found by scanning for the rightmost opaque pixel), not copied
# from the reference image's coordinates.
LIP_ORIGIN = (665, 267)          # top-left paste position of the closed lip_upper piece
LOWER_LIP_CLOSED_Y = 304          # top-left paste y of the closed lip_lower piece
LIP_SPRITE_WIDTH = 103            # both lip_upper.png / lip_lower.png share this width
MOUTH_MAX_GAP = 22                # only the lower lip moves, so this reads as a jaw drop, not a split
MOUTH_INTERIOR_COLOR = (60, 15, 20, 255)


def load_audio_amplitude(wav_path: str, fps: int) -> np.ndarray:
    with wave.open(wav_path, "rb") as w:
        n_channels = w.getnchannels()
        sample_rate = w.getframerate()
        n_frames = w.getnframes()
        raw = w.readframes(n_frames)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels).mean(axis=1)
    samples /= 32768.0

    samples_per_video_frame = int(sample_rate / fps)
    n_video_frames = max(1, len(samples) // samples_per_video_frame)
    amplitudes = np.zeros(n_video_frames)
    for i in range(n_video_frames):
        chunk = samples[i * samples_per_video_frame:(i + 1) * samples_per_video_frame]
        amplitudes[i] = np.sqrt(np.mean(chunk ** 2)) if len(chunk) else 0.0

    peak = amplitudes.max() if amplitudes.max() > 0 else 1.0
    return amplitudes / peak


def draw_eye(draw: ImageDraw.ImageDraw, frame_idx: int):
    cx, cy = EYE_CENTER
    r = EYE_RADIUS

    # Periodic blink: collapse to a thin lid line for a few frames instead of
    # the full circle. Simple sawtooth timer, not audio-driven — blinking is
    # an idle behavior, independent of speech.
    phase = frame_idx % BLINK_EVERY_FRAMES
    if phase < BLINK_DURATION_FRAMES:
        # eased close/open across the blink window rather than an instant cut
        t = phase / BLINK_DURATION_FRAMES
        openness = abs(t - 0.5) * 2  # 1 -> 0 -> 1 across the blink
        lid_h = max(2, int(r * 2 * openness))
        draw.ellipse([cx - r, cy - lid_h / 2, cx + r, cy + lid_h / 2], fill=(255, 255, 255, 255))
        draw.line([cx - r, cy, cx + r, cy], fill=(20, 20, 25, 255), width=max(2, int(r * 0.25)))
        return

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))
    pr = int(r * 0.62)
    draw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=(20, 20, 25, 255))
    hr = int(r * 0.22)
    hx, hy = cx - int(r * 0.3), cy - int(r * 0.3)
    draw.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=(255, 255, 255, 255))


def draw_mouth(frame: Image.Image, lip_upper: Image.Image, lip_lower: Image.Image, openness: float):
    """Paste Steven's actual lip sprite (split at the seam) instead of a drawn
    shape. Only the lower lip drops, like a jaw — the upper lip stays fixed
    in place. A symmetric split (both halves sliding apart) reads as two
    disconnected chunks; a single hinge at the bottom reads as a mouth
    opening, since that's how mouths actually move.
    """
    gap = MOUTH_MAX_GAP * openness
    ox, oy = LIP_ORIGIN

    if gap > 3:
        draw = ImageDraw.Draw(frame)
        cavity_top = oy + lip_upper.height - 4
        cavity_bottom = LOWER_LIP_CLOSED_Y + gap
        draw.ellipse(
            [ox + 10, cavity_top, ox + LIP_SPRITE_WIDTH - 10, cavity_bottom],
            fill=MOUTH_INTERIOR_COLOR,
        )

    frame.alpha_composite(lip_upper, (ox, oy))
    frame.alpha_composite(lip_lower, (ox, int(LOWER_LIP_CLOSED_Y + gap)))


def main():
    base_png, audio_wav, out_mp4 = sys.argv[1], sys.argv[2], sys.argv[3]
    assets_dir = Path(base_png).parent
    base = Image.open(base_png).convert("RGBA")
    lip_upper = Image.open(assets_dir / "lip_upper.png").convert("RGBA")
    lip_lower = Image.open(assets_dir / "lip_lower.png").convert("RGBA")
    amplitudes = load_audio_amplitude(audio_wav, FPS)

    with tempfile.TemporaryDirectory(prefix="mouthflap_") as tmpdir:
        tmp = Path(tmpdir)
        for i, amp in enumerate(amplitudes):
            frame = base.copy()
            draw_mouth(frame, lip_upper, lip_lower, float(amp))
            draw = ImageDraw.Draw(frame)
            draw_eye(draw, i)
            frame.convert("RGB").save(tmp / f"frame_{i:05d}.png")

        silent_mp4 = tmp / "silent.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-threads", "1", "-framerate", str(FPS),
             "-i", str(tmp / "frame_%05d.png"),
             "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-threads", "1", "-x264opts", "threads=1:sliced-threads=0",
             "-pix_fmt", "yuv420p", str(silent_mp4)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(silent_mp4), "-i", audio_wav,
             "-c:v", "copy", "-c:a", "aac", "-shortest", out_mp4],
            check=True, capture_output=True,
        )
    print(f"Wrote {out_mp4} ({len(amplitudes)} frames, {len(amplitudes)/FPS:.2f}s)")


if __name__ == "__main__":
    main()
