import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 5902
MATRIX_LAUNCHER_BASE = "http://127.0.0.1:5901"

MPV_PATHS = [
    r"C:\Program Files\MPV Player\mpv.exe",
    r"C:\Program Files\mpv\mpv.exe",
    r"C:\ProgramData\chocolatey\bin\mpv.exe",
]


def _debug_log(msg):
    with open(r"C:\minifi-manual\mpv_stream_launcher_crash.log", "a") as f:
        import datetime
        f.write(f"[{datetime.datetime.now().isoformat()}] DEBUG: {msg}\n")

# Local-screen key -> absolute virtual-desktop pixel rect, same coordinates
# already proven stable for days in windows_matrix_launcher.py's Edge kiosk
# positioning. mpv's own --screen=N (enumeration drifts across
# reboots/driver resets — confirmed live) and --geometry (monitor-relative,
# not virtual-desktop-absolute — --geometry=...+1920+0 still landed on
# DISPLAY1) were both tried and rejected on 2026-07-24. This positions the
# mpv window directly via Win32 SetWindowPos (the same OS-level call
# Chromium/Edge use under the hood for --window-position), bypassing mpv's
# own coordinate scoping entirely.
SCREENS = {
    "screen2": {"x": 1920, "y": 0, "w": 1920, "h": 1080, "pipe": r"\\.\pipe\mpv-screen2"},
    "screen3": {"x": 3840, "y": 0, "w": 1920, "h": 1080, "pipe": r"\\.\pipe\mpv-screen3"},
}


def _position_window(pid, x, y, w, h):
    """Position the window owned by pid via PowerShell's Get-Process
    MainWindowHandle + SetWindowPos — the same technique already confirmed
    live (2026-07-24) to reliably resolve mpv's window handle, unlike an
    earlier ctypes EnumWindows implementation here that returned hwnd=None
    every time (never debugged further, replaced instead — this one is
    proven). Returns the PowerShell script's stdout for logging."""
    ps_script = (
        "$deadline = (Get-Date).AddSeconds(5); $proc = $null; "
        f"while ((Get-Date) -lt $deadline) {{ $proc = Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
        "if ($proc -and $proc.MainWindowHandle -ne 0) { break }; Start-Sleep -Milliseconds 100 }; "
        "if (-not $proc -or $proc.MainWindowHandle -eq 0) { Write-Output 'NOHANDLE'; exit 1 }; "
        "Add-Type @'\n"
        "using System;\nusing System.Runtime.InteropServices;\n"
        "public class MpvPos {\n"
        '    [DllImport("user32.dll")]\n'
        "    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);\n"
        "}\n'@\n"
        f"$ok = [MpvPos]::SetWindowPos($proc.MainWindowHandle, [IntPtr]::Zero, {x}, {y}, {w}, {h}, 0x0040); "
        "Write-Output \"handle=$($proc.MainWindowHandle) setwindowpos=$ok\""
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps_script],
        capture_output=True, text=True, timeout=15,
    )
    return (result.stdout or "").strip() + (result.stderr or "").strip()


SW_RESTORE = 9
SW_MINIMIZE = 6


def _show_window(pid, sw_flag):
    """ShowWindow via PowerShell — mpv's own IPC "window-minimized" property
    was tried first but confirmed live (2026-07-24) NOT to actually iconify
    the window (IsIconic stayed False after setting it true), so falling
    back to the same proven Win32 call used for positioning."""
    ps_script = (
        f"$proc = Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
        "if (-not $proc -or $proc.MainWindowHandle -eq 0) { Write-Output 'NOHANDLE'; exit 1 }; "
        "Add-Type @'\n"
        "using System;\nusing System.Runtime.InteropServices;\n"
        "public class MpvShow {\n"
        '    [DllImport("user32.dll")]\n'
        "    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);\n"
        "}\n'@\n"
        f"$ok = [MpvShow]::ShowWindow($proc.MainWindowHandle, {sw_flag}); "
        "Write-Output \"showwindow=$ok\""
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps_script],
        capture_output=True, text=True, timeout=10,
    )
    return (result.stdout or "").strip() + (result.stderr or "").strip()

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
    """Lazy-start: launch once per screen, left running --idle forever after.
    Always restores fullscreen/un-minimizes on the way out, even for an
    already-running process — /stop (see below) minimizes the window rather
    than killing it, so a later /load on the same screen must un-minimize it
    again or the stream would load invisibly behind everything."""
    pid = _running.get(screen)
    if pid is not None:
        # Confirm it's still alive; a crashed mpv leaves a stale pid.
        check = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        if str(pid) in check.stdout:
            _show_window(pid, SW_RESTORE)
            send_ipc(screen, ["set_property", "fullscreen", True])
            return
        _running.pop(screen, None)

    cfg = SCREENS[screen]
    mpv = find_mpv()
    # --idle alone does NOT create a window until a file loads (mpv's own
    # documented behavior) — confirmed live 2026-07-24, MainWindowHandle
    # stayed 0 for the full 5s wait without this flag, so SetWindowPos had
    # nothing to act on. --force-window=immediate keeps a real window open
    # in idle mode so it can be positioned before anything plays.
    proc = subprocess.Popen(
        [mpv, "--idle", "--force-window=immediate", f"--input-ipc-server={cfg['pipe']}",
         "--ytdl-format=best", "--no-terminal"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _running[screen] = proc.pid
    # Give mpv a moment to create its IPC pipe before anything tries to write to it.
    for _ in range(50):
        if os.path.exists(cfg["pipe"]):
            break
        time.sleep(0.1)

    pos_result = _position_window(proc.pid, cfg["x"], cfg["y"], cfg["w"], cfg["h"])
    _debug_log(f"{screen}: pid={proc.pid} position result: {pos_result}")

    send_ipc(screen, ["set_property", "fullscreen", True])


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
                    # Stop playback AND get the window out of the way —
                    # a stopped-but-still-fullscreen mpv window would sit as
                    # a second GPU-composited surface underneath whatever
                    # triggered the stop (e.g. Matrix), confirmed live
                    # 2026-07-24 (still occupied the full monitor rect,
                    # title "No file - mpv", after just sending IPC "stop").
                    send_ipc(screen, ["stop"])
                    send_ipc(screen, ["set_property", "fullscreen", False])
                    time.sleep(0.3)  # let the fullscreen-exit transition settle first
                    show_result = _show_window(_running[screen], SW_MINIMIZE)
                    _debug_log(f"{screen}: stop -> minimize result: {show_result}")
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
