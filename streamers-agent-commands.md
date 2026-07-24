Streamers pipeline — Telegram bot commands. All scripts live under `DesktopShare/files/`.

See [agent-commands.md](agent-commands.md) for kubectl/minikube/git bootstrap commands.

## Streamers pipeline — Telegram bot scripts

**Core finding:** OpenClaw's `/bash` needs a `bash -c "..."` wrapper for anything
beyond a single bare command — `&&` chains, `source`, and backgrounding (`&`)
don't reliably run (the bot sometimes just chats back instead of executing)
without it.

Confirmed tested and working — live-tested end-to-end against the real
cluster/app, see `cso-operator-app-streamers.md` Session 14/16 for test details.

post now with user
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-PostNow.sh xqc"
```

start fetch clips
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-fetchClips.sh start"
```

stop fetch clips
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-fetchClips.sh stop"
```

approve posts
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-approvePosts.sh"
```

update watch list
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh t:extremely k:deenthegreat"
```

show watch list
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh show"
```

rotate watch list
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh rotate"
```

add to watch list without replacing it
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh add t:jasontheween"
```
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-watchList.sh add k:n3on"
```

run LiveStreamerAlert once (manual PollTimer pulse, one poll cycle — restores whatever RUNNING/STOPPED state PollTimer was already in afterward, does not unconditionally stop it; see session 20)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-liveStreamerAlert.sh"
```

**`PublishClip` start/stop — retired, do not use.** Both of its processors are `DISABLED` live (2026-07-24, Steven: "publish clip is gone, we only use PublishClipPeakTime w/ Trigger") — a start/stop call against a disabled processor will fail or no-op. Left here as a record of what used to exist, not a working command.

start PublishClipPeakTimeCron
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-publishFlow.sh PublishClipPeakTimeCron start"
```

stop PublishClipPeakTimeCron
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-publishFlow.sh PublishClipPeakTimeCron stop"
```
