#!/usr/bin/env python3
"""
clip-prep — #282. Streamers demo track. Runs as a k3s pod on spark-dd06.

The media step of the StreamerBrain PG: everything that needs ffmpeg or a large
body happens here, so the NiFi flow only ever carries small JSON.

POST /prep            body = the clip MP4 (raw, as NiFi InvokeHTTP sends FlowFile content)
    ?frames=N         evenly spaced frames across the clip (default 6)
    ?width=W          frame width in px (default 640)
    ?transcribe=0     skip whisper
  → JSON {id, duration, peak_audio_t, frame_times, frame_urls: [...], transcript}

  * wav: 16 kHz mono PCM, sent to whisper.cpp (WHISPER_URL, :8003/inference on the
    box's docker tier) — the transcript comes back in the JSON; the wav is not returned.
  * frames: N evenly spaced plus one at the loudest half-second (the gif branch's
    cut_start idea — the brain owns the visual sampling policy, so it lives here).
    Kept on disk for FRAME_TTL_S and served at GET /frames/<id>/<n>.jpg, so the vLLM
    call can reference them as image_url instead of carrying base64 through NiFi.
    frame_urls are absolute, built from PUBLIC_BASE (the address vLLM can reach).
GET /health → 200.   Stdlib + ffmpeg only.
"""
import array
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT", "8090"))
MAX_BODY = int(os.environ.get("MAX_BODY_MB", "200")) * 1024 * 1024
WHISPER_URL = os.environ.get("WHISPER_URL", "http://192.168.1.203:8003/inference")
PUBLIC_BASE = os.environ.get("PUBLIC_BASE", f"http://127.0.0.1:{PORT}").rstrip("/")
FRAME_DIR = os.environ.get("FRAME_DIR", "/tmp/frames")
FRAME_TTL_S = int(os.environ.get("FRAME_TTL_S", "3600"))
os.makedirs(FRAME_DIR, exist_ok=True)


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, timeout=300)


def duration_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def peak_audio_t(wav_path, window=0.5):
    """Loudest window by RMS over 16 kHz mono 16-bit PCM."""
    with wave.open(wav_path) as w:
        rate, n = w.getframerate(), w.getnframes()
        pcm = array.array("h"); pcm.frombytes(w.readframes(n))
    step = int(rate * window)
    best_t, best = 0.0, -1.0
    for i in range(0, max(len(pcm) - step, 1), step):
        seg = pcm[i:i + step]
        rms = (sum(s * s for s in seg) / max(len(seg), 1)) ** 0.5
        if rms > best:
            best, best_t = rms, i / rate
    return round(best_t + window / 2, 2)


def transcribe(wav_path):
    """whisper.cpp /inference — multipart by hand (stdlib), response_format=json."""
    boundary = f"----clipprep{uuid.uuid4().hex}"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n").encode() + open(wav_path, "rb").read() + \
        f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(WHISPER_URL, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return " ".join(json.loads(r.read().decode()).get("text", "").split())


def frame_at(mp4, t, width, out):
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", mp4, "-frames:v", "1",
         "-vf", f"scale={width}:-2", "-q:v", "3", out])


def prep(mp4_bytes, n_frames, width, do_transcribe):
    job = uuid.uuid4().hex[:12]
    out_dir = os.path.join(FRAME_DIR, job); os.makedirs(out_dir)
    with tempfile.TemporaryDirectory() as d:
        mp4 = os.path.join(d, "in.mp4"); wav = os.path.join(d, "audio.wav")
        open(mp4, "wb").write(mp4_bytes)
        dur = duration_of(mp4)
        run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", wav])
        peak = peak_audio_t(wav)
        times = [round(dur * (i + 0.5) / n_frames, 2) for i in range(n_frames)]
        if all(abs(peak - t) > 1.0 for t in times):
            times = sorted(times + [peak])
        for i, t in enumerate(times):
            frame_at(mp4, t, width, os.path.join(out_dir, f"{i}.jpg"))
        transcript = transcribe(wav) if do_transcribe else ""
    urls = [f"{PUBLIC_BASE}/frames/{job}/{i}.jpg" for i in range(len(times))]
    return {"id": job, "duration": round(dur, 2), "peak_audio_t": peak, "frame_times": times,
            "frame_urls": urls, "transcript": transcript,
            # ready-made OpenAI content parts, so the NiFi flow can splice the frames into
            # the chat request with one attribute instead of mapping over an array in EL
            "image_parts": [{"type": "image_url", "image_url": {"url": u}} for u in urls]}


def reaper():
    while True:
        now = time.time()
        for j in os.listdir(FRAME_DIR):
            p = os.path.join(FRAME_DIR, j)
            if now - os.path.getmtime(p) > FRAME_TTL_S:
                shutil.rmtree(p, ignore_errors=True)
        time.sleep(300)


class H(BaseHTTPRequestHandler):
    # Real HTTP/1.1 keep-alive: the default HTTP/1.0 handler closes the socket after each
    # response, and NiFi's InvokeHTTP pooled the dead connection — the next POST broke the
    # pipe before the request ever reached the server (seen 2026-08-31, run 2).
    protocol_version = "HTTP/1.1"

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._json(200, {"ok": True})
        parts = path.split("/")
        if len(parts) == 4 and parts[1] == "frames" and parts[2].isalnum() and parts[3].endswith(".jpg"):
            f = os.path.join(FRAME_DIR, parts[2], parts[3])
            if os.path.isfile(f):
                data = open(f, "rb").read()
                self.send_response(200); self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data))); self.end_headers()
                return self.wfile.write(data)
        self._json(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/prep":
            return self._json(404, {"error": "not found"})
        q = parse_qs(u.query)
        n = int(q.get("frames", ["6"])[0]); width = int(q.get("width", ["640"])[0])
        do_tr = q.get("transcribe", ["1"])[0] != "0"
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            return self._json(400, {"error": f"body length {length} out of range"})
        data = self.rfile.read(length)
        try:
            self._json(200, prep(data, n, width, do_tr))
        except subprocess.CalledProcessError as e:
            self._json(422, {"error": "ffmpeg failed", "stderr": e.stderr.decode()[-800:]})
        except Exception as e:  # noqa: BLE001 — one door, one error shape
            self._json(500, {"error": repr(e)})

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    threading.Thread(target=reaper, daemon=True).start()
    print(f"clip-prep listening on :{PORT}  whisper={WHISPER_URL}  public={PUBLIC_BASE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
