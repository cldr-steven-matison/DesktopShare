import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 5902
MATRIX_LAUNCHER_BASE = "http://127.0.0.1:5901"

MPV_PATHS = [
    r"C:\Program Files\mpv\mpv.exe",
    r"C:\ProgramData\chocolatey\bin\mpv.exe",
]

# Local-screen key -> mpv launch config. `screen_index` is mpv's own
# --screen enumeration, which is NOT guaranteed to match the Win32
# AllScreens-derived DISPLAY2/DISPLAY3 order windows_matrix_launcher.py's
# SCREENS dict uses (see claude-screen.md). UNVERIFIED — confirm empirically
# (does --screen=0 actually land on DISPLAY2/screen2, or DISPLAY3?) before
# trusting these indices; swap if wrong.
SCREENS = {
    "screen2": {"screen_index": 0, "pipe": r"\\.\pipe\mpv-screen2"},
    "screen3": {"screen_index": 1, "pipe": r"\\.\pipe\mpv-screen3"},
}

# PID of the mpv process currently running for each screen, once launched.
# Lazy-start: nothing here until that screen's first real /load call.
_running = {}


def find_mpv():
    for p in MPV_PATHS:
        if os.path.exists(p):
            return p
    return "mpv.exe"  # fall back to PATH


def build_url(streamer):
    """kick:<slug> -> kick.com/<slug>; bare name -> twitch.tv/<name>.
    Matches the kick:-prefix convention already used for the watchlist/roster
    (see streamers-twitch-bot.md / services/streamers.py) rather than
    inventing a new one. A chat command of `!load kick:hstikkytokky screen3`
    reaches here with streamer == "kick:hstikkytokky" (the regex in
    TwitchChatListenerProcessor captures the whole non-whitespace token).
    """
    if streamer.lower().startswith("kick:"):
        slug = streamer.split(":", 1)[1]
        return f"https://kick.com/{slug}"
    return f"https://www.twitch.tv/{streamer}"


def ensure_mpv_running(screen):
    """Lazy-start: launch once per screen, left running --idle forever after."""
    pid = _running.get(screen)
    if pid is not None:
        # Confirm it's still alive; a crashed mpv leaves a stale pid.
        check = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        if str(pid) in check.stdout:
            return
        _running.pop(screen, None)

    cfg = SCREENS[screen]
    mpv = find_mpv()
    proc = subprocess.Popen(
        [mpv, "--idle", f"--input-ipc-server={cfg['pipe']}",
         "--fullscreen", f"--screen={cfg['screen_index']}",
         "--ytdl-format=best", "--no-terminal"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _running[screen] = proc.pid
    # Give mpv a moment to create its IPC pipe before anything tries to write to it.
    for _ in range(50):
        if os.path.exists(cfg["pipe"]):
            break
        time.sleep(0.1)


def send_ipc(screen, command):
    cfg = SCREENS[screen]
    # Plain open() works here because Windows resolves \\.\pipe\... paths
    # through the same CreateFileW path io.open() uses underneath - no
    # pywin32 dependency needed for a simple "write one command, close" call.
    # If this proves unreliable in testing, switch to win32file.CreateFile.
    with open(cfg["pipe"], "w", encoding="utf-8") as f:
        f.write(json.dumps({"command": command}) + "\n")


def kill_mpv(screen):
    pid = _running.pop(screen, None)
    if pid is not None:
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        parts = self.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] not in ("load", "stop", "kill"):
            self._respond(404, {"ok": False, "error": "not found"})
            return
        action, screen = parts
        if screen not in SCREENS:
            self._respond(404, {"ok": False, "error": f"unknown screen: {screen}"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception as e:
            self._respond(400, {"ok": False, "error": f"bad request: {e}"})
            return

        try:
            if action == "load":
                streamer = payload["streamer"]
                # Best-effort: tear down matrix on this screen first, if showing.
                self._best_effort_post(f"{MATRIX_LAUNCHER_BASE}/kill/{screen}")
                ensure_mpv_running(screen)
                url = build_url(streamer)
                send_ipc(screen, ["loadfile", url, "replace"])
                self._respond(200, {"ok": True, "streamer": streamer, "screen": screen})
            elif action == "stop":
                if screen in _running:
                    send_ipc(screen, ["stop"])
                self._respond(200, {"ok": True, "screen": screen})
            elif action == "kill":
                kill_mpv(screen)
                self._respond(200, {"ok": True, "screen": screen})
        except Exception as e:
            self._respond(500, {"ok": False, "error": str(e)})

    def _best_effort_post(self, url):
        try:
            import urllib.request
            req = urllib.request.Request(url, data=b"{}", method="POST",
                                          headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass  # nothing was showing there, or matrix listener isn't up - fine either way

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # keep it quiet; rely on the JSON responses for status


if __name__ == "__main__":
    import datetime
    import traceback

    LOG_PATH = r"C:\minifi-manual\mpv_stream_launcher_crash.log"

    def log(msg):
        with open(LOG_PATH, "a") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")

    log("Starting")
    try:
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        log(f"Listening on 0.0.0.0:{PORT}")
        server.serve_forever()
    except Exception:
        log("CRASHED:\n" + traceback.format_exc())
        raise
    finally:
        log("Process exiting (serve_forever returned or crashed)")
