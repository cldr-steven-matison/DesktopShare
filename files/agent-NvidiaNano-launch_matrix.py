import subprocess
import os
import time

# This is the exact entrypoint MiNiFi C++ calls on every loop execution
def onTrigger(context, session):

    flow_file = session.get()

    if flow_file:
        try:
            # Same fixed launch — no payload needed, "on" is the only mode.
            # File URL, not a bare path: Chromium needs the file:// scheme to
            # load a local page in --kiosk mode the same way it loads a real URL.
            url = "file:///home/tunastreet/matrix-screensaver.html"

            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XAUTHORITY"] = "/run/user/1000/gdm/Xauthority"  # confirmed live value, see agent-NvidiaNano-launch_stream.py
            env["XDG_RUNTIME_DIR"] = "/run/user/1000"
            env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/run/user/1000/bus"

            # Same kill-then-relaunch discipline as agent-NvidiaNano-launch_stream.py:
            # SIGKILL + a real wait, because a surviving process holding its
            # profile lock makes the new launch silently proxy into it and
            # ignore --kiosk. This also correctly tears down a live Twitch
            # stream if !matrix is typed while one is showing.
            subprocess.run(["pkill", "-9", "-f", "chromium"], check=False)
            time.sleep(1.5)

            # Separate profile dir from the stream loader's
            # (/tmp/chromium-stream-display) — never used at the same time
            # since the pkill above always clears the field first, but keeps
            # the two launch paths independent rather than sharing a lock.
            proc = subprocess.Popen(
                ["chromium-browser", "--new-window", "--kiosk", "--start-fullscreen",
                 "--window-position=0,0", "--user-data-dir=/tmp/chromium-matrix-display", url],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )

            time.sleep(1.5)
            exit_code = proc.poll()
            if exit_code is not None:
                stderr_output = proc.stderr.read().decode('utf-8', errors='ignore')[:500]
                raise RuntimeError(f"chromium exited immediately (code {exit_code}): {stderr_output}")

            # Chromium's own --kiosk/--start-fullscreen don't reliably get
            # Mutter to grant real X11 fullscreen state on this device (see
            # agent-NvidiaNano-launch_stream.py) — force it after the fact
            # with wmctrl, backgrounded since ExecuteScript runs on a single
            # shared thread. First attempt matched on WM_CLASS via `wmctrl -lx`
            # ("chromium.chromium") — wrong, real WM_CLASS strings like
            # "chromium-browser.Chromium-browser" don't contain that literal
            # substring, so the poll silently never found the window and
            # fullscreen never fired (confirmed live: page loaded, stayed
            # windowed). Real fix: match on window *title* instead, same as
            # agent-NvidiaNano-launch_stream.py — Chromium always appends
            # " - Chromium" to the title bar regardless of page content, so
            # this doesn't depend on knowing the matrix HTML's own <title>.
            fullscreen_poll = (
                "for i in $(seq 1 240); do "
                "  if wmctrl -l | grep -qi -- ' - Chromium'; then "
                "    wmctrl -r 'Chromium' -b add,fullscreen; "
                "    break; "
                "  fi; "
                "  sleep 0.25; "
                "done"
            )
            subprocess.Popen(
                ["bash", "-c", fullscreen_poll],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            session.putAttribute(flow_file, "python.matrix.status", "Success")
            session.transfer(flow_file, REL_SUCCESS)

        except Exception as e:
            session.putAttribute(flow_file, "python.error", str(e))
            session.transfer(flow_file, REL_FAILURE)
