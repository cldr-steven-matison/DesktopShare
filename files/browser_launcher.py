import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 5901
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# This is "screen2" — the secondary monitor, confirmed via
# [System.Windows.Forms.Screen]::AllScreens (DISPLAY1, non-primary, 1280x720
# at (-1920,137)). Chrome's --kiosk fullscreens whichever monitor the window
# is actually on at launch time, so it has to be positioned here first —
# without --window-position it lands on the primary monitor (DISPLAY2) by
# default, which is not what a dedicated second screen needs.
SCREEN2_POSITION = "-1920,137"
SCREEN2_SIZE = "1280,720"


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
                 f"--window-position={SCREEN2_POSITION}",
                 f"--window-size={SCREEN2_SIZE}",
                 "--kiosk", url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            # Chrome hands off to an already-running instance via IPC and the
            # specific process we launched exits cleanly regardless of whether
            # a real window appeared — checking that Popen handle's exit code
            # (like the Jetson script does for chromium-browser) is a false
            # negative here. Instead poll for an actual top-level Chrome window,
            # same "verify the visible state, don't trust process launch alone"
            # discipline as the Jetson's wmctrl check.
            if self._wait_for_chrome_window(timeout=10):
                self._respond(200, {"ok": True, "url": url})
            else:
                self._respond(500, {"ok": False, "error": "no Chrome window appeared within timeout"})
        except Exception as e:
            self._respond(500, {"ok": False, "error": str(e)})

    def _wait_for_chrome_window(self, timeout):
        deadline = time.time() + timeout
        check = [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-NoProfile", "-Command",
                 "(Get-Process chrome -ErrorAction SilentlyContinue | "
                 "Where-Object { $_.MainWindowTitle -ne '' }).Count"]
        while time.time() < deadline:
            result = subprocess.run(check, capture_output=True, text=True)
            count = result.stdout.strip()
            if count.isdigit() and int(count) > 0:
                return True
            time.sleep(0.5)
        return False

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # keep it quiet; rely on the JSON responses for status


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"browser_launcher listening on 0.0.0.0:{PORT}")
    server.serve_forever()
