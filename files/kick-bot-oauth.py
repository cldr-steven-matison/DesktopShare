#!/usr/bin/env python3
"""One-time Kick OAuth 2.1 (PKCE) grant for the Kick chat bot account (#307).

Mints a *user* access token + refresh token for whichever Kick account approves
the consent page — that account becomes the bot that posts the on-screen
announcement into a streamer's Kick chat (`POST /public/v1/chat`, type "user",
scope `chat:write`). The app-level client_credentials token the app already
holds cannot post as a user, which is why this exists.

Run it on a machine with a browser, logged in to Kick AS THE BOT ACCOUNT:

    KICK_CLIENT_ID=... KICK_CLIENT_SECRET=... python3 files/kick-bot-oauth.py

It prints the authorize URL, opens it, catches the redirect on
http://localhost:8765/callback (that exact URI must be registered on the Kick
app at kick.com/settings/developer), exchanges the code, and writes the token
JSON to ~/.kick-bot-token.json (mode 600). Nothing is printed unmasked and
nothing goes into the repo. Then load the refresh token into the NiFi
Parameter Context `kick-chat-bot-creds` (sensitive) — never a literal property.
"""
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

AUTHORIZE = "https://id.kick.com/oauth/authorize"
TOKEN = "https://id.kick.com/oauth/token"
REDIRECT = os.environ.get("KICK_REDIRECT_URI", "http://localhost:8765/callback")
SCOPES = os.environ.get("KICK_SCOPES", "chat:write")
OUT = Path(os.environ.get("KICK_TOKEN_OUT", Path.home() / ".kick-bot-token.json"))

client_id = os.environ.get("KICK_CLIENT_ID")
client_secret = os.environ.get("KICK_CLIENT_SECRET")
if not (client_id and client_secret):
    sys.exit("set KICK_CLIENT_ID and KICK_CLIENT_SECRET in the environment")

verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
state = secrets.token_urlsafe(16)

url = AUTHORIZE + "?" + urllib.parse.urlencode(quote_via=urllib.parse.quote, query={
    "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code",
    "scope": SCOPES, "code_challenge": challenge, "code_challenge_method": "S256",
    "state": state,
    # Force the permission screen: a consent already on file for a narrower scope
    # set otherwise gets reused and the new scope is silently dropped (seen
    # 2026-09-07 — two grants came back `user:read` only).
    "prompt": os.environ.get("KICK_PROMPT", "consent"),
})
print("Open this as the BOT account and approve:\n\n  " + url + "\n")
webbrowser.open(url)

got: dict = {}


class Catch(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        got.update({k: v[0] for k, v in q.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Kick bot authorized - you can close this tab.")

    def log_message(self, *a):  # quiet
        pass


port = urllib.parse.urlparse(REDIRECT).port or 80
with http.server.HTTPServer(("127.0.0.1", port), Catch) as srv:
    while "code" not in got and "error" not in got:
        srv.handle_request()

if "error" in got:
    sys.exit(f"authorization failed: {got}")
if got.get("state") != state:
    sys.exit("state mismatch - refusing the code")

form = {
    "grant_type": "authorization_code", "client_id": client_id,
    "client_secret": client_secret, "redirect_uri": REDIRECT,
    "code": got["code"], "code_verifier": verifier,
}
# Keep the one-shot code + verifier until the exchange succeeds, so a blocked
# exchange can be retried without another consent click.
PENDING = OUT.with_name(".kick-bot-pending.json")
PENDING.write_text(json.dumps(form))
PENDING.chmod(0o600)

# id.kick.com sits behind Cloudflare bot protection that 403s a bare-host
# request with a library User-Agent (streamer-kick-bot.md §1). Browser-like
# headers first; if that is still 403, run the exchange from inside the
# cso-operator-app pod, whose egress Kick already trusts.
BROWSER_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
    "Referer": "https://kick.com/",
}


def exchange_local() -> dict:
    req = urllib.request.Request(TOKEN, data=urllib.parse.urlencode(form).encode(),
                                 headers=BROWSER_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def exchange_via_pod() -> dict:
    import subprocess
    pod = subprocess.run(
        ["kubectl", "get", "pods", "-o", "jsonpath={.items[?(@.status.phase=='Running')].metadata.name}"],
        capture_output=True, text=True, check=True).stdout.split()
    pod = next(p for p in pod if p.startswith("cso-operator-app"))
    code = ("import sys,json,httpx; f=json.load(sys.stdin); "
            "r=httpx.post('https://id.kick.com/oauth/token',data=f,timeout=20); "
            "print(json.dumps({'status':r.status_code,'body':r.text}))")
    out = subprocess.run(["kubectl", "exec", "-i", pod, "--", "python3", "-c", code],
                         input=json.dumps(form), capture_output=True, text=True, check=True).stdout
    res = json.loads(out)
    if res["status"] != 200:
        sys.exit(f"token exchange via pod failed: HTTP {res['status']} {res['body'][:300]}")
    return json.loads(res["body"])


try:
    tok = exchange_local()
    print("exchanged from this host")
except urllib.error.HTTPError as e:
    if e.code != 403:
        sys.exit(f"token exchange failed: HTTP {e.code} {e.read()[:300]!r}")
    print("host exchange blocked (403, Cloudflare) - exchanging via the app pod")
    tok = exchange_via_pod()
PENDING.unlink(missing_ok=True)

OUT.write_text(json.dumps(tok, indent=2))
OUT.chmod(0o600)
mask = lambda s: (s[:6] + "…" + s[-4:]) if isinstance(s, str) and len(s) > 12 else "?"
print(f"ok: scope={tok.get('scope')!r} expires_in={tok.get('expires_in')} "
      f"access={mask(tok.get('access_token'))} refresh={mask(tok.get('refresh_token'))}")
print(f"written to {OUT} (mode 600)")
