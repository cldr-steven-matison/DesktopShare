"""Persistent mpv + IPC stream launcher — Linux/X11 port (NvidiaNano/Jetson).

Linux counterpart to mpv_stream_launcher.py (Windows, used by StarlinkAI and
WindowsDesktop). Same HTTP contract — POST /load/<screen>, /stop/<screen>,
/kill/<screen> — so the MiNiFi-side ExecuteScript is the same thin forwarder on
every device.

Three things are genuinely different here and are why this is a separate file
rather than a branch inside the Windows one:

1. IPC is a Unix domain socket, not a named pipe. That also lets us *read* mpv's
   JSON reply, so a failed loadfile is a real error instead of a silent no-op —
   the Windows version writes and closes without ever seeing the response.
2. The Jetson drives a single 1920x1080 display (DP-0). None of the Windows
   version's SetWindowPos virtual-desktop positioning applies; mpv's own
   --fullscreen is enough, because the flags-ignored problem on this device was
   Chromium/Mutter-specific (see agent-NvidiaNano-launch_stream.py's history),
   not a general window-manager fault.
3. The matrix screensaver on this device is a Chromium page launched directly by
   agent-NvidiaNano-launch_matrix.py, not an HTTP launcher on :5901. So the
   matrix teardown here is a scoped pkill rather than a POST.

Runs as a systemd service; see mpv-stream-launcher.service alongside this file.
"""

import json
import os
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# MiNiFi runs natively on this host (unlike the KubernetesPod/Windows cases that
# needed 0.0.0.0 to be reachable across a container boundary), so keep the
# listener loopback-only.
BIND_HOST = "127.0.0.1"
PORT = 5902

YTDLP = "/home/tunastreet/bin/yt-dlp"

# "best" is source quality — on Twitch that can be 1080p60. If the Orin Nano
# turns out to be CPU-bound on decode, cap it here (e.g. "best[height<=720]");
# it is deliberately a single constant so that is a one-line change.
YTDL_FORMAT = "best"

# The matrix screensaver's Chromium, identified by its full --user-data-dir flag
# rather than a bare "chromium" match. Every process in Chromium's tree carries
# this flag in its own argv, so it still catches the whole tree, while a looser
# pattern also matches unrelated processes that merely mention the string —
# confirmed live 2026-08-02, a bare "chromium" pkill in the matrix script
# SIGKILLed an unrelated shell.
#
# No leading "--": pkill parses a pattern beginning with dashes as an option and
# silently kills nothing (also confirmed live 2026-08-02 — matrix windows piled
# up because every kill was a no-op). The tail of the flag is just as unique.
MATRIX_PROFILE = "user-data-dir=/tmp/chromium-matrix-display"

SCREENS = {
    "screen1": {"socket": "/tmp/mpv-screen1.sock"},
}

LOG_PATH = "/home/tunastreet/mpv_stream_launcher.log"


def log(msg):
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}\n")
    except Exception:
        pass  # logging must never take the service down


def display_env():
    """The exact env a GUI launch needs from a systemd service context.

    A systemd *system* service (even with User=tunastreet) does not inherit
    these the way an interactive login does — the same finding that
    agent-NvidiaNano-launch_stream.py documents for Chromium applies to mpv.
    XAUTHORITY is the live GNOME session's, not the one in the user's home dir.
    """
    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    env["XAUTHORITY"] = "/run/user/1000/gdm/Xauthority"
    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/run/user/1000/bus"
    return env


def build_url(streamer):
    """kick:<slug> -> kick.com/<slug>; bare name -> twitch.tv/<name>.

    Copied verbatim from mpv_stream_launcher.py so both platforms resolve a
    chat command identically. This function is the actual fix for
    `!load kick:<slug> screen1`: the old Jetson script hardcoded
    f"https://www.twitch.tv/{streamer}", which turned a kick: token into a
    Twitch 404 that still reported success.
    """
    if streamer.lower().startswith("kick:"):
        slug = streamer.split(":", 1)[1]
        return f"https://kick.com/{slug}"
    return f"https://www.twitch.tv/{streamer}"


# request_id is echoed back by mpv, which is how a reply is told apart from the
# event lines mpv emits continuously on the same socket.
_request_id = 0


def send_ipc(screen, command, timeout=10):
    """Send one IPC command and return mpv's decoded reply.

    Raises on transport failure or on an mpv-reported error, so callers get a
    real failure instead of the Windows version's write-and-hope.
    """
    global _request_id
    _request_id += 1
    rid = _request_id
    path = SCREENS[screen]["socket"]

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(path)
        s.sendall((json.dumps({"command": command, "request_id": rid}) + "\n").encode("utf-8"))

        buf = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except ValueError:
                    continue
                # Skip async event lines; only our own reply carries request_id.
                if msg.get("request_id") != rid:
                    continue
                if msg.get("error") != "success":
                    raise RuntimeError(f"mpv rejected {command!r}: {msg.get('error')}")
                return msg
    raise TimeoutError(f"no reply from mpv for {command!r} on {path}")


def mpv_alive(screen):
    """Liveness by socket probe rather than a remembered PID.

    Survives a restart of this service with mpv still running — a PID table in
    memory would not, and would then launch a second mpv onto the same display.
    """
    path = SCREENS[screen]["socket"]
    if not os.path.exists(path):
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect(path)
        return True
    except OSError:
        # Stale socket file from a crashed mpv — remove it so mpv can rebind.
        try:
            os.unlink(path)
        except OSError:
            pass
        return False


def ensure_mpv_running(screen):
    """Lazy-start: launch once per screen, then leave it running --idle forever."""
    if mpv_alive(screen):
        return False

    path = SCREENS[screen]["socket"]
    # --force-window=immediate: --idle alone creates no window until a file
    # loads (mpv's documented behavior), so there would be nothing to fullscreen
    # or hand focus to. Same reason the Windows port passes it.
    proc = subprocess.Popen(
        [
            "mpv",
            "--idle",
            "--force-window=immediate",
            "--fullscreen",
            f"--input-ipc-server={path}",
            f"--ytdl-format={YTDL_FORMAT}",
            f"--script-opts=ytdl_hook-ytdl_path={YTDLP}",
            "--hwdec=auto-safe",
            "--no-osc",
            "--no-input-default-bindings",
            "--cursor-autohide=always",
            "--no-terminal",
        ],
        env=display_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # outlive this service; mpv is the persistent part
    )

    for _ in range(100):  # up to 10s for the IPC socket to appear
        if mpv_alive(screen):
            log(f"{screen}: mpv started pid={proc.pid}")
            return True
        if proc.poll() is not None:
            raise RuntimeError(f"mpv exited immediately (code {proc.returncode})")
        time.sleep(0.1)
    raise TimeoutError(f"mpv started (pid={proc.pid}) but never created {path}")


def kill_mpv(screen):
    path = SCREENS[screen]["socket"]
    subprocess.run(["pkill", "-9", "-f", f"input-ipc-server={path}"], check=False)
    time.sleep(0.5)
    try:
        os.unlink(path)
    except OSError:
        pass


def kill_matrix():
    """Best-effort teardown of the matrix screensaver before showing a stream."""
    subprocess.run(["pkill", "-9", "-f", MATRIX_PROFILE], check=False)


def get_property(screen, name):
    """Read one mpv property, returning None if mpv has no value for it."""
    try:
        return send_ipc(screen, ["get_property", name]).get("data")
    except RuntimeError:
        return None  # property unavailable (e.g. playback-time while idle)


def confirm_playing(screen, timeout=12.0):
    """Wait until playback actually starts, or report that it never did.

    `loadfile` returns success the moment mpv accepts the command — it says
    nothing about whether yt-dlp could resolve the channel. An offline channel
    therefore looked identical to a working one: confirmed live 2026-08-02,
    `!load kick:<offline-slug>` returned ok:true while mpv sat at "No file -
    mpv". Reporting success for a load that put nothing on screen is exactly the
    failure mode that let the original twitch.tv/kick:<slug> bug go unnoticed,
    so the load is verified rather than assumed.

    Returns True once playback-time advances. Returns False if mpv falls back to
    idle (yt-dlp failed). A timeout returns None — genuinely unknown, treated as
    non-fatal, since a very slow resolve is not the same as a failure.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if get_property(screen, "playback-time") is not None:
            return True
        # idle-active goes False the instant loadfile is accepted and only
        # returns True once mpv has given up, so it is only meaningful after
        # giving the resolve a moment to start.
        if time.monotonic() > deadline - timeout + 3.0 and get_property(screen, "idle-active"):
            return False
        time.sleep(0.4)
    return None


def restore_mpv(screen, timeout=8.0):
    """Un-minimize the mpv window and verify it actually reached the front.

    Confirmed live on this device (2026-08-02): after a /stop minimizes the
    window, an IPC `set_property fullscreen true` on the next /load re-adds
    _NET_WM_STATE_FULLSCREEN but leaves _NET_WM_STATE_HIDDEN set — Mutter does
    not un-iconify on a fullscreen request, so the stream would play invisibly
    behind everything. windowactivate clears HIDDEN properly. This is the same
    class of bug the Windows port hit from the other direction (mpv's own
    "window-minimized" IPC property did not actually iconify there).

    Issue #206: a single fire-and-forget windowactivate sometimes left the
    stream playing behind whatever had focus, and a second !load fixed it. Two
    ways the one-shot could miss: on a cold start the IPC socket appears before
    the X11 window is mapped, so the search found nothing to activate; and on a
    load that replaces the matrix screensaver, the activate races the SIGKILLed
    Chromium's fullscreen window — when that window dies a moment later, Mutter
    hands focus to its idea of the most-recent window, not mpv. So: poll until
    an mpv window exists, activate it, and re-check that it really is the
    active window, retrying until the deadline. The retry is exactly what the
    manual second !load was doing by hand.
    """
    deadline = time.monotonic() + timeout
    last = "no mpv window appeared"
    while time.monotonic() < deadline:
        found = subprocess.run(
            ["xdotool", "search", "--class", "mpv"],
            env=display_env(), capture_output=True, text=True,
        )
        ids = (found.stdout or "").split()
        if not ids:
            time.sleep(0.25)
            continue
        result = subprocess.run(
            ["xdotool", "windowactivate", ids[-1]],
            env=display_env(), capture_output=True, text=True,
        )
        time.sleep(0.3)  # let Mutter apply (or refuse) the activation
        active = subprocess.run(
            ["xdotool", "getactivewindow"],
            env=display_env(), capture_output=True, text=True,
        )
        if (active.stdout or "").strip() in ids:
            return f"active={ids[-1]}"
        last = (f"activate did not stick (active={(active.stdout or '').strip()!r}, "
                f"err={(result.stderr or '').strip()!r})")
        time.sleep(0.4)
    return last


def minimize_mpv(screen):
    """Get the mpv window out of the way without killing the process.

    A stopped-but-still-fullscreen mpv window would sit on top of whatever
    triggered the stop (i.e. the matrix screensaver) — the same behavior
    confirmed live on the Windows side. Reported back to the caller rather than
    swallowed, so a failure here is visible in testing instead of silent.
    """
    result = subprocess.run(
        ["xdotool", "search", "--class", "mpv", "windowminimize", "%@"],
        env=display_env(), capture_output=True, text=True,
    )
    return (result.stdout or "").strip() + (result.stderr or "").strip()


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
        except ValueError as e:
            self._respond(400, {"ok": False, "error": f"bad request: {e}"})
            return

        try:
            if action == "load":
                streamer = payload["streamer"]
                url = build_url(streamer)
                kill_matrix()
                started = ensure_mpv_running(screen)
                send_ipc(screen, ["loadfile", url, "replace"])
                # Un-minimize *and* re-assert fullscreen on every load: /stop
                # minimizes rather than kills, so a warm mpv may be iconified and
                # would otherwise play the stream invisibly behind everything.
                # Both steps are needed — fullscreen alone does not clear
                # _NET_WM_STATE_HIDDEN (see restore_mpv).
                restored = restore_mpv(screen)
                send_ipc(screen, ["set_property", "fullscreen", True])

                playing = confirm_playing(screen)
                if playing is False:
                    log(f"{screen}: {url} resolved to nothing playable")
                    self._respond(502, {
                        "ok": False, "streamer": streamer, "screen": screen,
                        "url": url,
                        "error": "stream did not start (channel offline, or "
                                 "yt-dlp could not resolve it)",
                    })
                    return

                log(f"{screen}: loaded {url} (cold_start={started}, playing={playing}, restore={restored!r})")
                self._respond(200, {"ok": True, "streamer": streamer,
                                    "screen": screen, "url": url,
                                    "cold_start": started, "playing": playing})
            elif action == "stop":
                if mpv_alive(screen):
                    send_ipc(screen, ["stop"])
                    send_ipc(screen, ["set_property", "fullscreen", False])
                    time.sleep(0.3)  # let the fullscreen-exit transition settle
                    log(f"{screen}: stop -> minimize {minimize_mpv(screen)!r}")
                self._respond(200, {"ok": True, "screen": screen})
            elif action == "kill":
                kill_mpv(screen)
                log(f"{screen}: killed")
                self._respond(200, {"ok": True, "screen": screen})
        except Exception as e:
            log(f"{screen}: {action} FAILED: {e}")
            self._respond(500, {"ok": False, "error": str(e)})

    def _respond(self, code, body):
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
