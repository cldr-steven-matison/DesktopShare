#!/usr/bin/env python3
"""Multi-statement Phase A test: one HeyGen request containing several short
lines, split apart by detected silence, then spaced out across the full base
clip instead of appearing once at the start.

Why: a HeyGen render covering a full ~60s clip continuously would cost far
more credits than a short render with a few lines back-to-back. Generate
one compact video (a few lines, brief pauses between them), then use ffmpeg
to find those pauses and re-place each line's video at a different timestamp
spread across the real clip's duration.

Also switches the compositing approach per Steven's direction: instead of
overlaying the tuna on top of the clip's own footage (corner bug), pad the
canvas with a new black bar below the existing clip (same technique as
_burn_platform_overlay's pad, just a second bar) and the tuna lives in that
bar only, small, bottom-left.

Requires: HEYGEN_API_KEY / HEYGEN_AVATAR_ID in .env.local (or env),
kubectl port-forward svc/vllm-service 8000:8000.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from tuna_test import (
    HERE, OUTPUT_DIR, PERSONA_FILE, VLLM_URL, VLLM_MODEL,
    HEYGEN_API_KEY, HEYGEN_AVATAR_ID, HEYGEN_BASE,
    clean_line, contains_disallowed_content, heygen_generate_video, download,
    probe_video_dims, probe_duration,
)
import requests

INPUT_VIDEO = HERE / "input" / "sample_clip.mp4"
N_STATEMENTS = 3
# Ellipses get vocalized by the TTS (produces an audible blip mid-pause, which
# fooled silence detection into finding 2 gaps for what should be 1) — a bare
# paragraph break reads as a longer natural pause without speaking anything.
STATEMENT_JOIN = "\n\n"

# New bottom bar for the tuna (separate from the existing platform-info bar
# already burned onto every clip — see [[project_streamers_next]]/
# _burn_platform_overlay). Base clip is 1920x1240 post-platform-bar.
# Bar height matches the existing top platform-info bar exactly (160px for
# a 1920x1080-source clip).
TUNA_BAR_HEIGHT = 160

# HeyGen's Avatar IV output (720x1280, 9:16) renders the character tiny in
# the corner of an otherwise fully black frame — scaling the WHOLE frame
# down wastes almost all of the overlay budget on black space. Crop to just
# the character first (bounding box measured across several frames of
# actual output to cover its animation range, plus padding), then scale
# that tight crop up — makes the character much bigger for the same bar
# height. Re-measure this if a different avatar/aspect-ratio is ever used.
TUNA_CROP = (20, 1020, 300, 190)   # x, y, w, h within the 720x1280 HeyGen frame
TUNA_OVERLAY_HEIGHT = 156           # nearly the full 160px bar — "still too small" at 140
TWITCH_LOGO_HEIGHT = 70
TUNA_FPS = 25
TUNA_MARGIN_X = 20
LOGO_MARGIN_X = 20
TWITCH_LOGO_PATH = Path("/home/tunas/cso-operator-app/backend/assets/logos/twitch.png")


def generate_statements(transcript: str, n: int, attempts_per_line: int = 4) -> list[str]:
    """Ask vLLM for n distinct short reactions in one call, safety-gate each
    individually, regenerating any single line that trips the gate rather
    than discarding the whole batch."""
    persona = PERSONA_FILE.read_text()
    r = requests.post(
        f"{VLLM_URL}/v1/chat/completions",
        json={
            "model": VLLM_MODEL,
            "messages": [
                {"role": "system", "content": persona},
                {"role": "user", "content": (
                    f"Give {n} DIFFERENT short spoken reactions to this clip's transcript — "
                    f"vary what you react to, don't repeat the same joke. Do NOT quote or mimic "
                    f"any crude language/slurs in the transcript; keep your own lines clean. "
                    f"Output exactly {n} lines, one reaction per line, numbered like '1. ...'.\n\n"
                    f"Transcript: {transcript[:800]}"
                )},
            ],
            "max_tokens": 200,
            "temperature": 0.7,
        },
        timeout=60,
    )
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"]
    lines = [re.sub(r'^\d+\.\s*', '', ln.strip()) for ln in raw.splitlines() if ln.strip()]
    lines = [clean_line(ln) for ln in lines if ln.strip()][:n]

    final_lines = []
    for i, line in enumerate(lines):
        if not contains_disallowed_content(line):
            final_lines.append(line)
            continue
        print(f"    statement {i+1} tripped safety gate ({line!r}), regenerating alone...")
        regenerated = None
        for attempt in range(attempts_per_line):
            r2 = requests.post(
                f"{VLLM_URL}/v1/chat/completions",
                json={
                    "model": VLLM_MODEL,
                    "messages": [
                        {"role": "system", "content": persona},
                        {"role": "user", "content": (
                            "React in character to this clip's transcript with ONE short spoken "
                            "line. Do NOT quote or mimic any crude language/slurs in it — keep "
                            f"your own line clean.\n\nTranscript: {transcript[:600]}"
                        )},
                    ],
                    "max_tokens": 60,
                    "temperature": 0.6,
                },
                timeout=60,
            )
            r2.raise_for_status()
            candidate = clean_line(r2.json()["choices"][0]["message"]["content"])
            if not contains_disallowed_content(candidate):
                regenerated = candidate
                break
        if regenerated is None:
            raise RuntimeError(f"Statement {i+1} kept tripping the safety gate after {attempts_per_line} retries.")
        final_lines.append(regenerated)
    return final_lines


def detect_silence_splits(audio_or_video: Path, noise_db: str = "-30dB", min_silence: float = 0.3) -> list[tuple[float, float]]:
    """Run ffmpeg silencedetect and return (start, end) pairs of silent regions."""
    r = subprocess.run(
        ["ffmpeg", "-i", str(audio_or_video), "-af",
         f"silencedetect=noise={noise_db}:d={min_silence}", "-f", "null", "-"],
        capture_output=True, timeout=60,
    )
    text = r.stderr.decode(errors="replace")
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", text)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", text)]
    return list(zip(starts, ends))


def _merge_close_gaps(silences: list[tuple[float, float]], merge_within: float = 1.2) -> list[tuple[float, float]]:
    """Merge silence gaps that are close together into one — a single intended
    pause between statements can show up as 2+ separate detected gaps if the
    TTS puts a tiny voiced blip in the middle (observed with '...' pause
    text), which would otherwise produce a false extra cut point."""
    if not silences:
        return []
    merged = [silences[0]]
    for start, end in silences[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= merge_within:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def split_into_statement_clips(heygen_video: Path, n_statements: int, out_dir: Path) -> list[Path]:
    """Cut heygen_video at detected silence midpoints into n_statements pieces."""
    duration = probe_duration(heygen_video)
    silences = _merge_close_gaps(detect_silence_splits(heygen_video))
    print(f"    detected {len(silences)} silence gaps (after merging) in {duration:.2f}s video: {silences}")

    # cut points = midpoint of each silence gap, capped to n_statements-1 cuts
    cut_points = [(s + e) / 2 for s, e in silences][: n_statements - 1]
    bounds = [0.0] + cut_points + [duration]

    clips = []
    for i in range(len(bounds) - 1):
        start, end = bounds[i], bounds[i + 1]
        out = out_dir / f"statement_{i}.mp4"
        r = subprocess.run(
            ["ffmpeg", "-y", "-threads", "1", "-i", str(heygen_video),
             "-ss", str(start), "-to", str(end),
             "-c:v", "libx264", "-preset", "veryfast", "-threads", "1",
             "-x264opts", "threads=1:sliced-threads=0", "-c:a", "aac",
             str(out)],
            capture_output=True, timeout=60,
        )
        if r.returncode != 0:
            raise RuntimeError(f"split failed for segment {i}: {r.stderr.decode(errors='replace')[-500:]}")
        clips.append(out)
    return clips


def _crop_scale_clip(src: Path, dest: Path) -> None:
    """Crop to just the character (see TUNA_CROP) and scale up — done once per
    statement clip so both the talking video and its freeze-frame stills
    downstream share the exact same size/fps."""
    crop_x, crop_y, crop_w, crop_h = TUNA_CROP
    r = subprocess.run(
        ["ffmpeg", "-y", "-threads", "1", "-i", str(src),
         "-vf", f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale=-2:{TUNA_OVERLAY_HEIGHT},fps={TUNA_FPS}",
         "-an", "-c:v", "libx264", "-preset", "veryfast", "-threads", "1",
         "-x264opts", "threads=1:sliced-threads=0", "-pix_fmt", "yuv420p", str(dest)],
        capture_output=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(f"crop/scale failed: {r.stderr.decode(errors='replace')[-500:]}")


def _extract_frame(src: Path, dest_png: Path, at_end: bool) -> None:
    if at_end:
        cmd = ["ffmpeg", "-y", "-sseof", "-0.1", "-i", str(src), "-frames:v", "1", "-update", "1", str(dest_png)]
    else:
        cmd = ["ffmpeg", "-y", "-i", str(src), "-frames:v", "1", "-update", "1", str(dest_png)]
    r = subprocess.run(cmd, capture_output=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"frame extract failed: {r.stderr.decode(errors='replace')[-500:]}")


def _freeze_segment(frame_png: Path, duration: float, dest: Path) -> None:
    duration = max(duration, 0.05)
    r = subprocess.run(
        ["ffmpeg", "-y", "-threads", "1", "-loop", "1", "-i", str(frame_png),
         "-t", str(duration), "-r", str(TUNA_FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-threads", "1",
         "-x264opts", "threads=1:sliced-threads=0", "-pix_fmt", "yuv420p", str(dest)],
        capture_output=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(f"freeze segment failed: {r.stderr.decode(errors='replace')[-500:]}")


def build_tuna_track(statement_clips: list[Path], starts: list[float], base_duration: float, out_dir: Path) -> Path:
    """One continuous video spanning the whole base clip: talk, freeze on the
    last frame until the next line, talk, freeze, talk, freeze — so the tuna
    is visible the entire time instead of only during its 3 speaking windows.
    """
    cropped = []
    for i, clip in enumerate(statement_clips):
        c = out_dir / f"tuna_cropped_{i}.mp4"
        _crop_scale_clip(clip, c)
        cropped.append(c)
    durations = [probe_duration(c) for c in cropped]

    pieces = []
    lead_frame = out_dir / "freeze_lead.png"
    _extract_frame(cropped[0], lead_frame, at_end=False)
    lead_seg = out_dir / "freeze_lead.mp4"
    _freeze_segment(lead_frame, starts[0], lead_seg)
    pieces.append(lead_seg)

    for i, clip in enumerate(cropped):
        pieces.append(clip)
        end_i = starts[i] + durations[i]
        next_start = starts[i + 1] if i + 1 < len(cropped) else base_duration
        frame_png = out_dir / f"freeze_after_{i}.png"
        _extract_frame(clip, frame_png, at_end=True)
        seg = out_dir / f"freeze_after_{i}.mp4"
        _freeze_segment(frame_png, next_start - end_i, seg)
        pieces.append(seg)

    concat_list = out_dir / "tuna_track_concat.txt"
    concat_list.write_text("\n".join(f"file '{p.resolve()}'" for p in pieces))
    track = out_dir / "tuna_track.mp4"
    r = subprocess.run(
        ["ffmpeg", "-y", "-threads", "1", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c:v", "libx264", "-preset", "veryfast", "-threads", "1",
         "-x264opts", "threads=1:sliced-threads=0", "-pix_fmt", "yuv420p", str(track)],
        capture_output=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(f"tuna track concat failed: {r.stderr.decode(errors='replace')[-800:]}")
    return track


def composite_spaced(base_clip: Path, statement_clips: list[Path], dest: Path) -> None:
    """Pad the base clip with a new bottom black bar; the tuna is visible for
    the entire clip (talking during its 3 windows, frozen on its last frame
    in between), Twitch logo bottom-right, always on."""
    base_w, base_h = probe_video_dims(base_clip)
    base_duration = probe_duration(base_clip)
    new_h = base_h + TUNA_BAR_HEIGHT

    n = len(statement_clips)
    usable = base_duration - 4.0
    starts = [2.0 + usable * (i + 0.5) / n for i in range(n)]

    out_dir = statement_clips[0].parent
    tuna_track = build_tuna_track(statement_clips, starts, base_duration, out_dir)

    inputs = ["-i", str(base_clip), "-i", str(tuna_track)]
    for clip in statement_clips:
        inputs += ["-i", str(clip)]
    logo_input_idx = 2 + len(statement_clips)
    inputs += ["-i", str(TWITCH_LOGO_PATH)]

    filter_parts = [f"[0:v]pad={base_w}:{new_h}:0:0:color=black[padded]"]
    tuna_y = base_h + (TUNA_BAR_HEIGHT - TUNA_OVERLAY_HEIGHT) // 2
    filter_parts.append(f"[padded][1:v]overlay=x={TUNA_MARGIN_X}:y={tuna_y}[vtuna]")
    prev = "vtuna"

    # Twitch logo, bottom-right of the new bar, visible for the whole clip
    # (same "always on" treatment as the existing top platform-info bar).
    logo_y = base_h + (TUNA_BAR_HEIGHT - TWITCH_LOGO_HEIGHT) // 2
    filter_parts.append(f"[{logo_input_idx}:v]scale=-2:{TWITCH_LOGO_HEIGHT}[logo]")
    filter_parts.append(
        f"[{prev}][logo]overlay=x=W-w-{LOGO_MARGIN_X}:y={logo_y}[vfinal]"
    )
    prev = "vfinal"

    # audio: mix base clip audio with each statement's audio, delayed to its start time
    # (statement clip inputs are offset by 2 now: 0=base, 1=tuna_track, 2..n+1=statements)
    audio_labels = ["[0:a]"]
    for i, start in enumerate(starts):
        delay_ms = int(start * 1000)
        filter_parts.append(f"[{i+2}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
        audio_labels.append(f"[a{i}]")
    filter_parts.append(f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:duration=first:dropout_transition=0[aout]")

    filter_complex = ";".join(filter_parts)
    cmd = [
        "ffmpeg", "-y", "-threads", "1", *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{prev}]", "-map", "[aout]",
        "-threads", "1", "-c:v", "libx264", "-preset", "veryfast",
        "-x264opts", "threads=1:sliced-threads=0",
        "-crf", "23", "-c:a", "aac", "-movflags", "+faststart",
        str(dest),
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"composite failed: {r.stderr.decode(errors='replace')[-1500:]}")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    transcript_file = OUTPUT_DIR / "transcript.txt"
    if not transcript_file.exists():
        sys.exit("No cached transcript.txt found — run tuna_test.py once first, or add Whisper transcription here.")
    transcript = transcript_file.read_text()
    print(f"Using cached transcript: {transcript[:150]!r}")

    print(f"1/4 Generating {N_STATEMENTS} distinct tuna statements with vLLM...")
    statements = generate_statements(transcript, N_STATEMENTS)
    for i, s in enumerate(statements):
        print(f"    {i+1}. {s!r}")
    (OUTPUT_DIR / "multi_statements.json").write_text(json.dumps(statements, indent=2))

    print("2/4 Submitting ONE HeyGen request with all statements + pauses...")
    combined_script = STATEMENT_JOIN.join(statements)
    video_url = heygen_generate_video(combined_script)
    heygen_video = OUTPUT_DIR / "multi_heygen_video.mp4"
    download(video_url, heygen_video)
    print(f"    downloaded: {heygen_video}")

    print("3/4 Splitting into per-statement clips by detected silence...")
    statement_clips = split_into_statement_clips(heygen_video, N_STATEMENTS, OUTPUT_DIR)
    for c in statement_clips:
        print(f"    {c} ({probe_duration(c):.2f}s)")

    print("4/4 Compositing: new bottom bar, tuna spaced across the full clip...")
    final_video = OUTPUT_DIR / "final_multi_composited.mp4"
    composite_spaced(INPUT_VIDEO, statement_clips, final_video)
    print(f"    done: {final_video}")


if __name__ == "__main__":
    main()
