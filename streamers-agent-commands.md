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

start PublishClipPeakTimeCron
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-publishFlow.sh PublishClipPeakTimeCron start"
```

stop PublishClipPeakTimeCron
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-publishFlow.sh PublishClipPeakTimeCron stop"
```

`agent-fetchClips.sh`/`agent-publishFlow.sh` start/stop toggle a process group's continuous/cron operation on or off — that's their one job now. They used to also double as the manual "get me one run right now" mechanism (start, let it tick, stop again) — that's what `Trigger` below replaces. `PublishClip` (the old GenerateFlowFile-timer flavor) is retired — both its processors are `DISABLED` live (2026-07-24, Steven: "publish clip is gone, we only use PublishClipPeakTime w/ Trigger") — `agent-publishFlow.sh` no longer accepts it as an arg; use `Trigger PublishClip` instead.

## Trigger — one-shot on-demand run, any flow

**Not yet bot-confirmed — `POST /api/streamers/flows/trigger/{name}` exists in code but isn't deployed to the live pod yet (2026-07-24).** Needs a deploy before any of these will actually work; test for real once that's done, then this note comes out.

`agent-trigger.sh` replaces three separate old mechanisms with one script: `agent-liveStreamerAlert.sh`'s PollTimer pulse (removed), and the start-then-stop-immediately hack that used to be how you'd force a single `FetchClips`/`PublishClip` run. Fires one flowfile through `StreamersApp`'s shared `Trigger` (`ListenHTTP`) → `RouteOnAttribute` entry point, straight into the target flow's `TriggerInput` port — bypasses that flow's own top-level scheduler entirely, so it never touches `PollTimer`'s cron or any PG's running state. The flow name **isn't validated client-side** — the backend's `TRIGGER_REQUESTS` allow-list is the single source of truth, so a new flow wired onto `RouteOnAttribute` + added to that allow-list is triggerable from here immediately, no script edit needed.

trigger LiveStreamerAlert (replaces the old PollTimer pulse — this is the one Steven specifically needs back, since PollTimer being CRON_DRIVEN/RUNNING made the old direct-pulse approach awkward)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-trigger.sh LiveStreamerAlert"
```

trigger FetchClips (one fetch run, without touching the FetchClips PG's own start/stop state)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-trigger.sh FetchClips"
```

trigger PublishClip (one publish — despite the name, routes to PublishClipPeakTimeCron's TriggerInput port, not the disabled PublishClip PG; see cso-operator-app-streamers.md's PublishClipPeakTimeCron section for why)
```bash
/bash bash -c "source .env && bash ./DesktopShare/files/agent-trigger.sh PublishClip"
```
