import json
import urllib.request

# Callback class for reading the session stream
class ReadContentCallback:
    def __init__(self):
        self.content = ""
    def process(self, input_stream):
        self.content = input_stream.read().decode('utf-8')
        return len(self.content)


# Native Windows listener that owns the actual playback — this pod has no
# GUI/display access of its own (no X11/Wayland socket, confirmed), so
# playback has to be launched by a real process on the Windows host instead.
# As of 2026-07-25: mpv_stream_launcher.py (persistent mpv + IPC), not
# browser_launcher.py's Chrome kill-relaunch — same fix already proven on
# TunaStarlink for the flashing/instability the kill-relaunch cycle caused.
LISTENER_URL = "http://host.docker.internal:5902/load/screen2"


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

            # 2. Hand off to the native Windows listener — mpv_stream_launcher.py
            # builds the actual Twitch/Kick URL itself from the raw streamer
            # value now (gains kick:<slug> support for free, matching
            # TunaStarlink), so this script no longer constructs a URL at all.
            body = json.dumps({"streamer": streamer}).encode('utf-8')
            req = urllib.request.Request(LISTENER_URL, data=body, method="POST",
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            if not result.get("ok"):
                raise RuntimeError(f"listener reported failure: {result.get('error')}")

            session.putAttribute(flow_file, "python.load.status", "Success")
            session.putAttribute(flow_file, "python.load.streamer", streamer)
            session.transfer(flow_file, REL_SUCCESS)

        except Exception as e:
            session.putAttribute(flow_file, "python.error", str(e))
            session.transfer(flow_file, REL_FAILURE)
