**Status: Single-screen version LIVE and confirmed working end-to-end (2026-07-18).** `!load <streamer>` typed in `tunastarlink`'s real chat now opens that stream full-screen on the Jetson Orin Nano's monitor. Scope was cut way down from the original 5-screen/4-device plan below — see "As-built (2026-07-18)" for what's actually running. The rest of this doc is the original aspirational draft, kept for the multi-screen expansion described at the end.

### As-built (2026-07-18)

Scope: exactly one screen, on the already-registered `NvidiaNano` (Jetson Orin Nano) EFM/MiNiFi agent. Everything else below (multi-device mapping, Windows targets) is deferred until a second screen is actually needed.

**Architecture:** `TunaStreetTest` (Twitch bot account) holds a persistent IRC chat connection *inside NiFi itself* — not a standalone script — as a custom Python processor (`TwitchChatListenerProcessor`, in `nifi-custom-processors`, deployed via the same PVC/`kubectl cp` toolchain as `XLivePostProcessor`). It emits one flowfile per detected `!load <streamer>` command. A brand-new, fully isolated process group (`TwitchChatBot`) inside `mynifi` — no shared connections with `StreamersApp`/`LiveStreamerAlert` — routes it: `TwitchChatListenerProcessor` → `RouteOnAttribute` → `InvokeHTTP` (hardcoded to the Jetson) → `LogAttribute` on failure. The OAuth user token (chat:read+chat:edit, authorized as `@TunaStreetTest`) lives in a NiFi Parameter Context, never a literal processor property.

On the Jetson: a second `ListenHTTP`(`streamChatListener`, port 8081)→`ExecuteScript` pair added onto the *same* MiNiFi canvas as the existing TensorRT flow, without touching it. The script (`files/agent-NvidiaNano-launch_stream.py`) kills any existing Chromium, relaunches it full-screen against the requested streamer's Twitch URL, and force-corrects fullscreen via `wmctrl` since Chromium's own `--kiosk`/`--start-fullscreen` flags don't reliably get Mutter to grant real fullscreen state on this device.

**Bugs hit and fixed, in the order they surfaced:**
1. **`ListenHTTP` buffer/batch size dropped single requests** — the endpoint was copy-configured from the TensorRT listener with `Batch Size: 5`/`Buffer Size: 5`, so a lone test POST just sat there and got silently dropped (`ListenHTTP buffer is NOT full 1/5 ... request was dropped`). The TensorRT endpoint "worked" only because it gets hammered with repeated back-to-back calls. Fix: `Batch Size: 1`/`Buffer Size: 1`.
2. **`XAUTHORITY` was an unfilled placeholder** — the real value, pulled from the live GNOME session's actual process environment, is `/run/user/1000/gdm/Xauthority`, not `/home/<user>/.Xauthority`.
3. **`minifi.service` ran as `root`**, while the GNOME/X11 desktop session belongs to `tunastreet` (uid 1000) — root's environment has no `XDG_RUNTIME_DIR`/D-Bus session address, which snap-confined Chromium needs. Fixed by adding `User=tunastreet` to the systemd unit — which then surfaced a follow-on permissions issue (log/state dirs still owned by `root` from when the service ran as root; fixed with a one-time `chown -R tunastreet:tunastreet` on the MiNiFi install dir).
4. **Chromium launched but wouldn't go full-screen** — `--kiosk`/`--start-fullscreen`/`--window-position=0,0` all got ignored by Mutter. Fix: force it after the fact with `wmctrl -r ' - Twitch - Chromium' -b add,fullscreen`, run as a detached/backgrounded poll (up to 60s, checking every 0.25s) since MiNiFi's `ExecuteScript` runs on a single shared thread and a blocking wait would stall the whole agent.
5. **Chromium's single-instance behavior** proxies a second launch into the existing window and silently ignores all its startup flags unless the prior process is fully dead first — fixed with `pkill -9` (not the default `SIGTERM`) plus a real wait, and a dedicated `--user-data-dir` to remove any profile-lock ambiguity.

**Token refresh (fixed 2026-07-18):** `TwitchChatListenerProcessor` v0.0.2-SNAPSHOT mints a fresh access token from the refresh token before every (re)connect, instead of relying on the one static token that expired every ~4 hours. Twitch rotates the refresh token on every use, so the processor keeps the current one in memory and updates it on each refresh — the seed value stored in the Parameter Context (`twitch-bot-refresh-token`) goes stale after the very first refresh and is never read again for the life of the running processor. Client ID/secret and the refresh-token seed live in the same `twitch-chat-bot-creds` Parameter Context as sensitive params. One real gap: if NiFi/this processor ever restarts, it reseeds from that now-stale stored refresh token and a fresh device-code re-auth would be needed — there's no mechanism yet to persist the rotated refresh token back out to the Parameter Context.

**Chat commands (added 2026-07-18):** `TwitchChatListenerProcessor` v0.0.3-SNAPSHOT responds in chat to `!commands`/`!help` with the available command list — the bot can now post to chat, not just read it (`PRIVMSG #<channel> :<message>` over the same IRC socket).

**Presence announcement + periodic reminder (added 2026-07-18):** v0.0.4-SNAPSHOT announces itself once on join; v0.0.5-SNAPSHOT made that repeat every `Reminder Interval (seconds)` (default 600) since Twitch shows no chat history to viewers who join after the one-time announcement — they'd otherwise never see it or know the bot exists.

**Not yet built:** the multi-screen JSON lookup table, additional device targets, and a Windows launch script — all deferred exactly as scoped below, until a second screen is actually needed. Also considered but not built: swapping the kill/relaunch Chromium cycle for a persistent browser controlled via Chrome DevTools Protocol (`Page.navigate`) for a flash-free URL swap — real win, but needs a hand-rolled websocket client since no websocket library is available in this Python environment; current kill/relaunch (~3-8s, visible flash) works fine for now.

### Second screen — LIVE (2026-07-18): `!load <streamer> screen2` confirmed working end-to-end

`TwitchChatListenerProcessor` v0.0.6-SNAPSHOT parses an optional screen argument (`!load <streamer> [screen1|screen2]`, defaults to `screen1`, no regression on the Jetson path). `TwitchChatBot`'s `RouteOnAttribute` branches on `${screen}` for real (`screen1`→`InvokeNvidiaNano`; `screen2`→`InvokeGamingPC`).

**The GUI-access blocker got solved, not worked around.** `KubernetesPod` (a pod inside minikube, Docker Desktop docker driver) genuinely has zero filesystem/env access to WSLg's GUI sockets — confirmed directly inside the container (no `/tmp/.X11-unix`, no `/mnt/wslg`, no `DISPLAY`). No mount was added (explicitly ruled out). Instead: confirmed the pod **can** reach the Windows host over plain TCP (`host.docker.internal`, the LAN IP, and the Docker Desktop gateway IP all worked), so the pod's `ExecuteScript` doesn't launch a browser itself — it POSTs the Twitch URL to a small native Python HTTP listener (`browser_launcher.py`) running directly on Windows, which owns the actual Chrome launch. Real GUI access problem solved by not needing GUI access inside the pod at all.

**Architecture, confirmed live 2026-07-18:**
- `gaming-pc-launch_stream.py` (pod-side `ExecuteScript`, on `minifi-agent-k8s-gaming`, asset dir) — same `onTrigger`/`session` contract as `agent-NvidiaNano-launch_stream.py`, but POSTs `{"url": "..."}` to `http://host.docker.internal:5901/load` instead of spawning Chromium locally.
- `browser_launcher.py` (native Windows listener, `C:\minifi-manual\`, port 5901, stdlib-only `http.server`) — kills existing Chrome, launches `--kiosk`, and **verifies a real window actually appeared** (`MainWindowTitle` non-empty) before reporting success. Real bug found and fixed here: checking the launched process's own exit code is a false negative — Chrome hands off to an already-running instance via IPC and that specific child process exits 0 regardless of whether a window appeared. Poll for the actual window state instead, same discipline as the Jetson's `wmctrl` check.
- New `ListenHTTP-StreamLoad`(port 8082, `streamChatListener`) → `LaunchGamingPCStream` pair added onto `minifi-agent-k8s-gaming`'s canvas.

**Done properly through EFM's actual API, not left as a local hack.** EFM exposes no OpenAPI spec and its Flow Designer REST schema isn't documented anywhere, so the initial attempt (direct `config.yml` edit + manual `minifi` restart) was corrected by reverse-engineering the real API straight from EFM's own Angular frontend bundle (`main.<hash>.js` — it's an auto-generated OpenAPI client, so every operation name/URL/body-shape is discoverable verbatim in the minified JS, e.g. `FlowDesignerService.createProcessor` → `POST /designer/flows/{flowId}/process-groups/{pgId}/processors` with body `{revision:{version,clientId}, componentConfiguration:{...}}`). Used the proper flow: `GET /designer/client-identifier` → `createProcessor` ×2 → `createConnection` → `validate` → `POST /designer/flows/{id}/publish`. EFM's own C2 heartbeat then pushed the properly-tracked flow down and **replaced** the pod's hand-edited config automatically (new server-assigned processor IDs confirmed present afterward) — no manual restart needed once published correctly. The script itself was also re-registered as a real EFM Resource (`POST /resource-manager/resources/file`, `resourceType=ASSET`) and assigned to the class (`PUT /agent-class-resource-manager/KubernetesPod/save` with `{resourceIdsToBeAssigned, resourceIdsToBeUnassigned}` — the exact field names only found by grepping the frontend bundle for the real assign-dialog's save call), matching the SHA-512 digest of the file already delivered — no content drift. **EFM's UI now correctly shows both new processors and the resource assignment for this class.**

**Other known fragility:**
- `InvokeGamingPC`'s URL is hardcoded to the pod's current IP (`10.244.2.115`) — will break if the pod restarts/reschedules and gets a new IP.
- `browser_launcher.py` isn't persistent across a Windows reboot yet (plain running process, not a service/scheduled task).
- No kiosk escape hatch wired up (fine for the eventual dedicated-screen deployment; for ad-hoc testing, `Alt+F4` or `Ctrl+Shift+Esc` gets out manually).

---

**Full Detailed Implementation Plan (original draft — superseded by the as-built section above for the single-screen MVP)**  
**Project: Chat-Controlled Multi-Monitor Stream Loader (Twitch + Edge Automation)**

**Version:** 1.0  
**Date:** July 18, 2026  
**Goal:** Allow viewers in your Twitch chat to type simple commands that dynamically open Chromium browsers showing specific streams on designated physical monitors/screens across multiple devices. Use one bot account and leverage your existing MiNiFi / Edge Flow Manager infrastructure.

### 1. Project Overview & Objectives

**Primary Goal**  
Enable chat-driven control of 4–5 physical screens/monitors by launching Chromium browsers with stream URLs.

**Scope (Current Phase)**  
- Twitch bot account (`@TunaStreetTest`)
- Load streams using Chromium browser
- Distributed execution using MiNiFi agents on edge devices
- Central routing and mapping handled in NiFi

**Success Criteria**  
- Bot joins chat when your main channel goes live  
- Command `!load xqc screen3` reliably opens the correct stream on the correct monitor  
- System works across mixed Windows + Linux devices  
- Easy to manage and extend via Edge Flow Manager

### 2. High-Level Architecture

```
Twitch Chat (@tunastarlink)
        ↓
Twitch Bot (@TunaStreetTest)          ← Lightweight Python bot
        ↓ (HTTP POST)
Central NiFi Instance (Master Brain)  ← Runs on main PC
        ↓ (Lookup + Route)
Edge MiNiFi Agents (per device)
        ↓ ListenHTTP
        ↓ ExecuteScript (Python)
Chromium Browser on correct monitor
```

**Key Components**
- **Twitch Bot**: Handles chat connection, live detection, command parsing, and forwarding to Central NiFi.
- **Central NiFi**: Acts as the intelligent router. Contains the screen-to-device mapping and decides which edge agent to call.
- **Edge MiNiFi Agents**: Lightweight agents on each physical device. Receive triggers via HTTP and execute local Python scripts to launch Chromium on the correct monitor.
- **Mapping Layer**: Central lookup table that translates logical screen names (screen1, screen2, …) into specific devices + monitor indices.

### 3. Command Format

**Recommended Starting Format**
```
!load <streamer> <screen>
```

**Examples**
- `!load xqc screen2`
- `!load ninja screen4`
- `!clear screen3`

**Future Possible Extensions**
- `!load xqc screen2 volume=50`
- `!swap screen1 screen2`

### 4. Screen-to-Device Mapping

Create a central mapping (stored as JSON in NiFi or a file):

```json
{
  "screen1": {
    "device": "windows-main",
    "os": "windows",
    "monitor_index": 1,
    "agent_url": "http://192.168.1.50:8080/streamChatListener"
  },
  "screen2": {
    "device": "windows-main",
    "os": "windows",
    "monitor_index": 2,
    "agent_url": "http://192.168.1.50:8080/streamChatListener"
  },
  "screen3": {
    "device": "jetson-nano-01",
    "os": "linux",
    "monitor_index": 1,
    "agent_url": "http://192.168.1.101:8080/streamChatListener"
  },
  "screen4": {
    "device": "linux-box-02",
    "os": "linux",
    "monitor_index": 2,
    "agent_url": "http://192.168.1.102:8080/streamChatListener"
  },
  "screen5": {
    "device": "windows-laptop",
    "os": "windows",
    "monitor_index": 3,
    "agent_url": "http://192.168.1.60:8080/streamChatListener"
  }
}
```

This mapping lives in Central NiFi and is easy to update.

### 5. Detailed Component Specifications

#### 5.1 Twitch Bot (@TunaStreetTest)
- **Language**: Python (recommended: `twitchio` library) (code already working in streamers app)
- **Responsibilities**:
  - Check every 30–60 seconds if main channel is live (Twitch Helix API)
  - When live → connect to chat and send intro message
  - Listen for messages starting with `!load` or `!clear`
  - Parse command → extract streamer name + target screen
  - Send HTTP POST to Central NiFi with payload:
    ```json
    {
      "command": "load",
      "streamer": "xqc",
      "screen": "screen3",
      "timestamp": "..."
    }
    ```
- **Auth**: Use OAuth token with `chat:read` + `chat:edit` scopes
- **Hosting**: Runs on main PC 

#### 5.2 Central NiFi (Master Brain)
- **Role**: Routing, mapping lookup, logging, error handling
- **Key Processors**:
  - `HandleHttpRequest` or `ListenHTTP` (to receive from Twitch bot)
  - `EvaluateJsonPath` or `UpdateAttribute` for parsing
  - Lookup table (JSON file or attributes) for screen mapping
  - `InvokeHTTP` to forward to the correct edge MiNiFi agent
- **Benefits**: Visual flows, easy to modify routing logic, central logging

#### 5.3 Edge MiNiFi Agents
- One agent per physical device
- Use `ListenHTTP` processor to receive triggers from Central NiFi
- `ExecuteScript` processor (Python) to run the browser launch logic
- need alternative for python on windows - will do linux only for now.
- Pass parameters: `streamer`, `screen`, `monitor_index`, `os`

### 6. Browser Launch Logic (Device-Specific)

Each edge device will have its own Python script logic:

**Linux (Jetson Nano, etc.)**
```python
import subprocess
import os

def open_stream(streamer, monitor_index):
    display = f":0.{monitor_index - 1}" if monitor_index > 1 else ":0.0"
    url = f"https://www.twitch.tv/{streamer}"
    env = os.environ.copy()
    env["DISPLAY"] = display
    subprocess.Popen(["chromium-browser", "--new-window", url], env=env)
```

**Windows**
- Use Chrome command line with window positioning or libraries like `pyautogui` + `pywin32`
- Or launch Chrome then move/resize the window to the correct monitor

You will maintain separate Python scripts (or conditional logic) per OS inside the MiNiFi `ExecuteScript` processor.

### 7. Implementation Phases

**Phase 1: Foundation (Twitch Bot + Basic Forwarding)**
- Create and authorize `@TunaStreetTest` bot account
- Build basic Python bot that detects live status and joins chat
- Implement command parsing for `!load`
- Make bot send simple HTTP POST to a test endpoint (your main PC)

**Phase 2: Central NiFi Brain**
- Set up Central NiFi instance
- Create flow that receives HTTP from Twitch bot
- Implement screen-to-device mapping lookup
- Forward to a test `ListenHTTP` endpoint

**Phase 3: Edge MiNiFi + Browser Launch**
- Install/configure MiNiFi agents on all devices via Edge Flow Manager
- Create `ListenHTTP` → `ExecuteScript` flow on each agent
- Write and test Python browser launch scripts (Linux + Windows versions)
- Test end-to-end on one screen

**Phase 4: Full Integration & Polish**
- Deploy full mapping to Central NiFi
- Add intro message when bot joins chat
- Add basic error handling and logging
- Test across all 4–5 screens
- Document the mapping table

### 8. Tools & Technologies

- **Twitch Bot**: Python + twitchio (or tmi.js)
- **Central Brain**: Apache NiFi
- **Edge Agents**: Apache MiNiFi (Java or C++ agent) + Edge Flow Manager
- **Browser Control**: Chromium + Python `subprocess` / automation libraries
- **Communication**: HTTP (POST) between all components
- **Configuration**: JSON mapping file

### 9. Security & Best Practices

- Use internal network IPs only (no public exposure)
- Add simple token-based auth on `ListenHTTP` endpoints if desired
- Rate-limit commands in the Twitch bot
- Log all commands with timestamps
- Keep the bot account as a regular moderator (not broadcaster)
- Test thoroughly in a test channel first

### 10. Risks & Mitigations

| Risk                        | Mitigation                              |
|----------------------------|-----------------------------------------|
| Bot gets rate-limited      | Add delays and respect Twitch limits    |
| Browser windows pile up    | Add `!clear` command + periodic cleanup |
| Mapping becomes outdated   | Store mapping in version-controlled file|
| Device goes offline        | Add retry logic + status reporting in NiFi |
| Windows vs Linux differences | Maintain separate scripts per OS     |


### 12. Next Actions (Recommended Order)

1. Finalize the exact command syntax you want.
2. Create the `@TunaStreetTest` bot account and get it modded.
3. Build the basic Twitch bot that can parse commands and send HTTP (Phase 1).
4. Set up Central NiFi flow with mapping lookup.
5. Deploy MiNiFi agents and test browser launch scripts on each device type.
6. Connect everything end-to-end.

---