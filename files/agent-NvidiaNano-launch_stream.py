import subprocess
import os
import json
import time

# Callback class for reading the session stream
class ReadContentCallback:
    def __init__(self):
        self.content = ""
    def process(self, input_stream):
        self.content = input_stream.read().decode('utf-8')
        return len(self.content)  # Good practice to return bytes read


# This is the exact entrypoint MiNiFi C++ calls on every loop execution
def onTrigger(context, session):

    flow_file = session.get()

    if flow_file:
        try:
            # 1. Read upstream payload — expects JSON like {"streamer": "xqc", ...}
            reader = ReadContentCallback()
            session.read(flow_file, reader)

            payload = json.loads(reader.content) if reader.content.strip() else {}
            streamer = payload.get("streamer")
            if not streamer:
                raise ValueError("payload missing 'streamer' field")

            url = f"https://www.twitch.tv/{streamer}"

            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XAUTHORITY"] = "/run/user/1000/gdm/Xauthority"  # confirmed from the live GNOME session's env, not the user's home dir
            # A systemd *system* service (even with User=tunastreet) doesn't inherit these the
            # way an interactive login does — snap-confined Chromium needs both to fully attach
            # as its own window instead of falling back to proxying into an existing instance.
            env["XDG_RUNTIME_DIR"] = "/run/user/1000"
            env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/run/user/1000/bus"

            # Replace any existing stream window instead of piling up new ones.
            # SIGKILL (not the default SIGTERM) + a real wait for it to die matters here:
            # if any old chromium process is still holding its profile lock when we
            # relaunch, Chromium just proxies the new invocation to it as a plain window
            # and silently ignores --kiosk (and any other startup flag).
            subprocess.run(["pkill", "-9", "-f", "chromium"], check=False)
            time.sleep(1.5)

            # A dedicated user-data-dir avoids any ambiguity with a lingering profile
            # lock from a not-fully-reaped process, independent of the pkill above.
            proc = subprocess.Popen(
                ["chromium-browser", "--new-window", "--kiosk", "--start-fullscreen",
                 "--window-position=0,0", "--user-data-dir=/tmp/chromium-stream-display", url],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )

            # Popen() returning just means fork/exec succeeded — it says nothing about
            # whether Chromium actually stayed up, so give it a moment and check.
            time.sleep(1.5)
            exit_code = proc.poll()
            if exit_code is not None:
                stderr_output = proc.stderr.read().decode('utf-8', errors='ignore')[:500]
                raise RuntimeError(f"chromium exited immediately (code {exit_code}): {stderr_output}")

            # Chromium's own --kiosk/--start-fullscreen/--window-position flags don't
            # reliably get Mutter to grant real X11 fullscreen state on this device
            # (confirmed live: window came up windowed despite all three flags).
            # wmctrl forcing it after the fact is the proven fix. This has to run
            # detached (start_new_session=True) rather than inline here — MiNiFi's
            # ExecuteScript runs on a single shared thread, so a blocking poll of up
            # to a minute would stall the whole agent (heartbeats, Kafka, the other
            # listener) exactly like the matrix-rain screensaver's force_fullscreen()
            # backgrounds+disowns itself for the same reason.
            fullscreen_poll = (
                "for i in $(seq 1 240); do "
                "  if wmctrl -l | grep -qF -- ' - Twitch - Chromium'; then "
                "    wmctrl -r ' - Twitch - Chromium' -b add,fullscreen; "
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

            session.putAttribute(flow_file, "python.load.status", "Success")
            session.putAttribute(flow_file, "python.load.streamer", streamer)

            # 2. Route to success relationship
            session.transfer(flow_file, REL_SUCCESS)

        except Exception as e:
            # If it breaks, append the error message to an attribute and fail it
            session.putAttribute(flow_file, "python.error", str(e))
            session.transfer(flow_file, REL_FAILURE)
