import json
import os
import subprocess
import sys
import time

# Invoked once per ExecuteStreamCommand trigger (a native MiNiFi Java agent
# process on WindowsDesktop), replacing the always-on
# mpv_stream_launcher.py/windows_matrix_launcher.py HTTP listeners' role for
# screen2. Ported logic, not re-derived — see claude-screen.md and
# streamers/streamers-twitch-bot-mpv-plan.md for the originals this is based on.
#
# Key design change from the originals: no in-memory `_running` dict, since
# each invocation is a fresh process with no memory of the last one. "Is mpv
# already running" is answered from OS state instead — a live process whose
# command line carries this screen's --input-ipc-server pipe name — rather
# than a persistent Python server tracking a PID in memory. This is what lets
# ExecuteStreamCommand "connect to mpv's existing persistent IPC socket"
# instead of relaunching it: the pipe/process are the source of truth, not a
# long-lived helper process.

MPV_PATHS = [
    r"C:\Program Files\MPV Player\mpv.exe",
    r"C:\Program Files\mpv\mpv.exe",
    r"C:\ProgramData\chocolatey\bin\mpv.exe",
]
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
MATRIX_HTML = r"C:\minifi-manual\matrix-screensaver.html"
PROFILE_DIR_PREFIX = r"C:\minifi-manual\edge-matrix-profile-"
LOG_PATH = r"C:\minifi-manual\windows_screen_control.log"

SCREENS = {
    "screen2": {
        "x": 0, "y": 0, "w": 1920, "h": 1080,
        "pipe": r"\\.\pipe\mpv-screen2",
        "matrix_position": "0,0", "matrix_size": "1920,1080",
    },
}


def _log(msg):
    with open(LOG_PATH, "a") as f:
        import datetime
        f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")


def _find_exe(paths, fallback):
    for p in paths:
        if os.path.exists(p):
            return p
    return fallback


def build_url(streamer):
    if streamer.lower().startswith("kick:"):
        slug = streamer.split(":", 1)[1]
        return f"https://kick.com/{slug}"
    return f"https://www.twitch.tv/{streamer}"


def _ps(script, timeout=15):
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    return (result.stdout or "").strip() + (result.stderr or "").strip()


def find_process_pid_by_cmdline_substring(substring):
    """Resolve a live PID from OS state via its command line — the
    stateless replacement for an in-memory pid dict. Returns None if no
    matching process is running."""
    ps_script = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -like '*{substring}*' }} | "
        "Select-Object -First 1 -ExpandProperty ProcessId"
    )
    out = _ps(ps_script, timeout=10)
    out = out.strip()
    return int(out) if out.isdigit() else None


def _position_window(pid, x, y, w, h):
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
    return _ps(ps_script)


SW_RESTORE = 9
SW_MINIMIZE = 6


def _show_window(pid, sw_flag):
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
    return _ps(ps_script)


_request_id = 0


def send_ipc(screen, command, timeout=10):
    """Send one IPC command over mpv's named pipe, return the decoded reply.
    Raises on a mpv-reported error or on no reply (pipe missing/dead)."""
    global _request_id
    _request_id += 1
    rid = _request_id
    cfg = SCREENS[screen]
    with open(cfg["pipe"], "r+", encoding="utf-8", newline="") as f:
        f.write(json.dumps({"command": command, "request_id": rid}) + "\n")
        f.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = f.readline()
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("request_id") != rid:
                continue
            if msg.get("error") != "success":
                raise RuntimeError(f"mpv rejected {command!r}: {msg.get('error')}")
            return msg
    raise TimeoutError(f"no reply from mpv for {command!r} on {cfg['pipe']}")


def mpv_is_running(screen):
    """True + live pid if a real mpv process for this screen is alive and
    answering IPC. The IPC round-trip itself is the only reliable proof —
    os.path.exists()/Test-Path both give false negatives on a live Windows
    named pipe (confirmed empirically: a working pipe a .NET
    Directory.GetFiles enumeration could see was invisible to both), so a
    pre-check gate here caused a real duplicate-mpv-launch bug during
    testing. Try the round-trip directly; any failure means not running."""
    cfg = SCREENS[screen]
    try:
        send_ipc(screen, ["get_property", "idle-active"], timeout=4)
    except Exception:
        return None
    return find_process_pid_by_cmdline_substring(f"input-ipc-server={cfg['pipe']}")


def kill_matrix_for_screen(screen):
    """Coexistence: tear down any Edge matrix kiosk on this screen before
    mpv takes it over. Was a POST to windows_matrix_launcher.py's /kill;
    now resolved directly from process list instead of a cross-process call."""
    pid = find_process_pid_by_cmdline_substring(PROFILE_DIR_PREFIX)
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True)


def ensure_mpv_running(screen):
    cfg = SCREENS[screen]
    pid = mpv_is_running(screen)
    if pid:
        _show_window(pid, SW_RESTORE)
        send_ipc(screen, ["set_property", "fullscreen", True])
        return pid

    mpv = _find_exe(MPV_PATHS, "mpv.exe")
    proc = subprocess.Popen(
        [mpv, "--idle", "--force-window=immediate", f"--input-ipc-server={cfg['pipe']}",
         "--ytdl-format=best", "--no-terminal"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if os.path.exists(cfg["pipe"]):
            break
        time.sleep(0.1)

    pos_result = _position_window(proc.pid, cfg["x"], cfg["y"], cfg["w"], cfg["h"])
    _log(f"{screen}: launched pid={proc.pid} position result: {pos_result}")
    send_ipc(screen, ["set_property", "fullscreen", True])
    return proc.pid


def get_property(screen, name):
    try:
        return send_ipc(screen, ["get_property", name]).get("data")
    except RuntimeError:
        return None


def confirm_playing(screen, timeout=12.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if get_property(screen, "playback-time") is not None:
            return True
        if time.monotonic() > deadline - timeout + 3.0 and get_property(screen, "idle-active"):
            return False
        time.sleep(0.4)
    return None


def cmd_mpv_load(screen, streamer):
    kill_matrix_for_screen(screen)
    ensure_mpv_running(screen)
    url = build_url(streamer)
    send_ipc(screen, ["loadfile", url, "replace"])
    playing = confirm_playing(screen)
    if playing is False:
        return {"ok": False, "streamer": streamer, "screen": screen, "url": url,
                "error": "stream did not start (channel offline, or yt-dlp could not resolve it)"}
    return {"ok": True, "streamer": streamer, "screen": screen, "url": url, "playing": playing}


def cmd_mpv_stop(screen):
    pid = mpv_is_running(screen)
    if pid:
        send_ipc(screen, ["stop"])
        send_ipc(screen, ["set_property", "fullscreen", False])
        time.sleep(0.3)
        _show_window(pid, SW_MINIMIZE)
    return {"ok": True, "screen": screen}


def cmd_matrix_load(screen):
    cfg = SCREENS[screen]
    # Coexistence: stop mpv on this screen first, best-effort — was a POST
    # to mpv_stream_launcher.py's /stop; a missing/dead mpv is not an error.
    try:
        cmd_mpv_stop(screen)
    except Exception:
        pass

    kill_matrix_for_screen(screen)

    profile_dir = f"{PROFILE_DIR_PREFIX}{int(time.time() * 1000)}"
    try:
        for name in os.listdir(os.path.dirname(PROFILE_DIR_PREFIX)):
            full = os.path.join(os.path.dirname(PROFILE_DIR_PREFIX), name)
            if name.startswith(os.path.basename(PROFILE_DIR_PREFIX)) and full != profile_dir:
                import shutil
                shutil.rmtree(full, ignore_errors=True)
    except Exception:
        pass

    edge = _find_exe(EDGE_PATHS, "msedge.exe")
    x, y = cfg["matrix_position"].split(",")
    w, h = cfg["matrix_size"].split(",")
    url = f"file:///{MATRIX_HTML.replace(chr(92), '/')}"
    subprocess.Popen(
        [edge, "--kiosk", "--edge-kiosk-type=fullscreen",
         f"--window-position={x},{y}", f"--window-size={w},{h}",
         "--new-window", f"--user-data-dir={profile_dir}", "--no-first-run", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"ok": True, "screen": screen}


def main():
    args = sys.argv[1:]
    try:
        if len(args) == 3 and args[0] == "mpv-load":
            result = cmd_mpv_load(args[1], args[2])
        elif len(args) == 2 and args[0] == "mpv-stop":
            result = cmd_mpv_stop(args[1])
        elif len(args) == 2 and args[0] == "matrix-load":
            result = cmd_matrix_load(args[1])
        else:
            result = {"ok": False, "error": f"bad args: {args!r}"}
    except Exception as e:
        _log(f"EXCEPTION: {args!r}: {e}")
        result = {"ok": False, "error": str(e)}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
