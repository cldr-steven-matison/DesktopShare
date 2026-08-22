"""Standalone matrix-screensaver launcher — Linux/X11 (NvidiaNano/Jetson).

Same shape as mpv_stream_launcher_linux.py: a small resident HTTP daemon that
owns one piece of on-screen state, called by a thin EFM/MiNiFi front door
instead of running the display logic inline. Built for issue #84 — MiNiFi
Java's ExecuteScript is Groovy/Clojure only, so the Chromium-kiosk launch that
used to live directly inside agent-NvidiaNano-launch_matrix.py's C++-agent
onTrigger() has to run as its own always-on process for a
HandleHttpRequest -> InvokeHTTP -> HandleHttpResponse pair to call into.

Logic below is carried over unchanged from agent-NvidiaNano-launch_matrix.py
(same pkill pattern, same wmctrl fullscreen poll, same env) — only the
entrypoint changes, from onTrigger(context, session) to an HTTP handler.

Runs as a systemd --user service; see matrix-stream-launcher.service alongside
this file.
"""

import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

BIND_HOST = "127.0.0.1"
PORT = 5901

# The stream launcher's /stop endpoint (mpv_stream_launcher_linux.py). Get a
# live stream out of the way first, same as the C++-agent version did.
STREAM_LAUNCHER_STOP = "http://127.0.0.1:5902/stop/screen1"

MATRIX_URL = "file:///home/tunastreet/matrix-screensaver.html"

# Scoped to the profile dir rather than a bare "chromium": every process in
# Chromium's tree carries --user-data-dir in its own argv, so this still
# catches the whole tree, while a looser pattern also matches unrelated
# processes that merely mention the string (confirmed live 2026-08-02, a bare
# "chromium" pkill in the original script SIGKILLed an unrelated shell).
# No leading "--": pkill parses a pattern beginning with dashes as an option
# and silently kills nothing (also confirmed live 2026-08-02).
MATRIX_PROFILE = "user-data-dir=/tmp/chromium-matrix-display"

SCREENS = {"screen1": {}}

LOG_PATH = "/home/tunastreet/matrix_stream_launcher.log"


def log(msg):
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}\n")
    except Exception:
        pass  # logging must never take the service down


def display_env():
    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    env["XAUTHORITY"] = "/run/user/1000/gdm/Xauthority"
    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/run/user/1000/bus"
    return env


def stop_stream_best_effort():
    """Nothing playing, or launcher not up? Either is fine — still show matrix."""
    try:
        import urllib.request
        req = urllib.request.Request(STREAM_LAUNCHER_STOP, data=b"{}", method="POST",
                                      headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def kill_matrix():
    subprocess.run(["pkill", "-9", "-f", MATRIX_PROFILE], check=False)


def show_matrix(screen):
    """Launch the matrix screensaver, replacing whatever else is on screen."""
    env = display_env()
    stop_stream_best_effort()

    # SIGKILL + a real wait: a surviving process holding its profile lock
    # makes the new launch silently proxy into it and ignore --kiosk.
    kill_matrix()
    time.sleep(1.5)

    proc = subprocess.Popen(
        ["chromium-browser", "--new-window", "--kiosk", "--start-fullscreen",
         "--window-position=0,0", f"--{MATRIX_PROFILE}", MATRIX_URL],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )

    time.sleep(1.5)
    exit_code = proc.poll()
    if exit_code is not None:
        stderr_output = proc.stderr.read().decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"chromium exited immediately (code {exit_code}): {stderr_output}")

    # Chromium's own --kiosk/--start-fullscreen don't reliably get Mutter to
    # grant real X11 fullscreen state on this device — force it after the
    # fact with wmctrl, backgrounded so this HTTP handler can return without
    # waiting the full poll window. Matches on window *title* rather than
    # WM_CLASS: real WM_CLASS strings ("chromium-browser.Chromium-browser")
    # don't contain a clean substring to match, but Chromium always appends
    # " - Chromium" to the title bar regardless of page content.
    #
    # Issue #206: add,fullscreen sets the fullscreen *state* but never raises
    # or activates the window, and a window mapped by a daemon has no user
    # timestamp, so Mutter's focus-stealing prevention could leave the matrix
    # fullscreened *behind* whatever had focus — a second !matrix brought it
    # up. So after fullscreening, `wmctrl -a` (raise + activate) and re-check
    # that Chromium really is the active window, retrying for up to 6s. The
    # final active-window name is appended to the log either way, so a future
    # "sometimes" report has evidence to read.
    fullscreen_poll = (
        "for i in $(seq 1 240); do "
        "  if wmctrl -l | grep -qi -- ' - Chromium'; then "
        "    wmctrl -r 'Chromium' -b add,fullscreen; "
        "    for j in $(seq 1 12); do "
        "      wmctrl -a 'Chromium'; "
        "      sleep 0.5; "
        "      xdotool getactivewindow getwindowname 2>/dev/null "
        "        | grep -qi -- 'Chromium' && break; "
        "    done; "
        "    break; "
        "  fi; "
        "  sleep 0.25; "
        "done; "
        "active=$(xdotool getactivewindow getwindowname 2>/dev/null); "
        f"echo \"[$(date +%Y-%m-%dT%H:%M:%S)] {screen}: fullscreen-poll done, "
        f"active window: $active\" >> {LOG_PATH}"
    )
    subprocess.Popen(
        ["bash", "-c", fullscreen_poll],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    log(f"{screen}: matrix shown, pid={proc.pid}")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        parts = self.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] not in ("show", "kill"):
            self._respond(404, {"ok": False, "error": "not found"})
            return
        action, screen = parts
        if screen not in SCREENS:
            self._respond(404, {"ok": False, "error": f"unknown screen: {screen}"})
            return

        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)  # no payload fields used today; drain it

        try:
            if action == "show":
                show_matrix(screen)
                self._respond(200, {"ok": True, "screen": screen})
            elif action == "kill":
                kill_matrix()
                log(f"{screen}: killed")
                self._respond(200, {"ok": True, "screen": screen})
        except Exception as e:
            log(f"{screen}: {action} FAILED: {e}")
            self._respond(500, {"ok": False, "error": str(e)})

    def _respond(self, code, body):
        import json
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # rely on the JSON responses and LOG_PATH for status


if __name__ == "__main__":
    log(f"Starting on {BIND_HOST}:{PORT}")
    try:
        HTTPServer((BIND_HOST, PORT), Handler).serve_forever()
    except Exception as e:
        log(f"CRASHED: {e}")
        raise
