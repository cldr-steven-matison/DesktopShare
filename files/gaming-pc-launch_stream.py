import json
import urllib.request

# Callback class for reading the session stream
class ReadContentCallback:
    def __init__(self):
        self.content = ""
    def process(self, input_stream):
        self.content = input_stream.read().decode('utf-8')
        return len(self.content)


# Native Windows listener (browser_launcher.py) that owns the actual Chrome launch —
# this pod has no GUI/display access of its own (no X11/Wayland socket, confirmed),
# so the browser has to be launched by a real process on the Windows host instead.
LISTENER_URL = "http://host.docker.internal:5901/load"


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

            # 2. Hand off to the native Windows listener — it does the actual
            # kill-existing/relaunch/verify-window-appeared work and reports
            # real success/failure back, not just "the POST went out".
            body = json.dumps({"url": url}).encode('utf-8')
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
