import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 5901
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# This is "screen2" — the physical right-hand monitor, confirmed by Steven
# directly (left=Screen1=Display1=DISPLAY1 non-primary at -1920,137;
# right=Screen2=Display2=DISPLAY2 primary at 0,0,1920x1080) via
# [System.Windows.Forms.Screen]::AllScreens. Position is force-applied after
# launch via reposition_chrome.ps1 (MoveWindow), not trusted from the flag.
SCREEN2_POSITION = "0,0"
SCREEN2_SIZE = "1920,1080"


def find_chrome():
    import os
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return "chrome.exe"  # fall back to PATH


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/load":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            url = payload["url"]
        except Exception as e:
            self._respond(400, {"ok": False, "error": f"bad request: {e}"})
            return

        try:
            # Replace any existing launch rather than piling up windows.
            subprocess.run(["taskkill", "/IM", "chrome.exe", "/F"], capture_output=True)
            time.sleep(1.0)

            chrome = find_chrome()
            subprocess.Popen(
                [chrome, "--new-window",
                 r"--user-data-dir=C:\minifi-manual\chrome-kiosk-profile",
                 f"--window-position={SCREEN2_POSITION}",
                 f"--window-size={SCREEN2_SIZE}",
                 url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            # Chrome hands off to an already-running instance via IPC and the
            # specific process we launched exits cleanly regardless of whether
            # a real window appeared — checking that Popen handle's exit code
            # is a false negative here. No --kiosk here on purpose: kiosk
            # fullscreen locks its rendered output to whichever monitor the
            # cursor is on at launch, and that stays wrong even after
            # MoveWindow relocates the window frame afterward (frame moves,
            # pixels don't). Instead: launch windowed, force it onto the
            # right monitor via MoveWindow, then trigger fullscreen (F11)
            # only once it's already there — done in reposition_chrome.ps1.
            x, y = (int(v) for v in SCREEN2_POSITION.split(","))
            w, h = (int(v) for v in SCREEN2_SIZE.split(","))
            ok, detail = self._reposition_chrome(x, y, w, h, timeout=10)
            if ok:
                self._respond(200, {"ok": True, "url": url, "rect": detail})
            else:
                self._respond(500, {"ok": False, "error": detail})
        except Exception as e:
            self._respond(500, {"ok": False, "error": str(e)})

    def _reposition_chrome(self, x, y, w, h, timeout):
        result = subprocess.run(
            [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-NoProfile", "-File",
             r"C:\minifi-manual\reposition_chrome.ps1",
             "-X", str(x), "-Y", str(y), "-W", str(w), "-H", str(h),
             "-TimeoutSeconds", str(timeout)],
            capture_output=True, text=True,
        )
        out = result.stdout.strip()
        if out.startswith("OK"):
            return True, out
        return False, out or result.stderr.strip()

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

    LOG_PATH = r"C:\minifi-manual\browser_launcher_crash.log"

    def log(msg):
        with open(LOG_PATH, "a") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")

    log(f"Starting, pid check next")
    try:
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        log(f"Listening on 0.0.0.0:{PORT}")
        server.serve_forever()
    except Exception:
        log("CRASHED:\n" + traceback.format_exc())
        raise
    finally:
        log("Process exiting (serve_forever returned or crashed)")
