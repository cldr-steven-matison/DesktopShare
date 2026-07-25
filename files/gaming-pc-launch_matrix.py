import json
import urllib.request

# Native Windows listener (windows_matrix_launcher.py) that owns the actual
# Edge kiosk launch - this pod has no GUI/display access of its own, so the
# matrix screensaver has to be shown by a real process on the Windows host
# instead. Mirrors gaming-pc-launch_stream.py's bridge pattern exactly.
LISTENER_URL = "http://host.docker.internal:5903/matrix/screen2"


# This is the exact entrypoint MiNiFi C++ calls on every loop execution
def onTrigger(context, session):

    flow_file = session.get()

    if flow_file:
        try:
            # Fixed single action, same as agent-NvidiaNano-launch_matrix.py -
            # no payload needed, "on" is the only mode, one screen in scope.
            req = urllib.request.Request(LISTENER_URL, data=b"{}", method="POST",
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            if not result.get("ok"):
                raise RuntimeError(f"listener reported failure: {result.get('error')}")

            session.putAttribute(flow_file, "python.matrix.status", "Success")
            session.transfer(flow_file, REL_SUCCESS)

        except Exception as e:
            session.putAttribute(flow_file, "python.error", str(e))
            session.transfer(flow_file, REL_FAILURE)
