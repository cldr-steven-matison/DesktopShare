# `agent/` — how Claude works on this repo

DesktopShare is worked on from several devices (see `../CLAUDE-CHECKIN.md`). This directory is the device-agnostic home for the working rules those sessions share. Nothing here names a specific hostname or absolute path — if a rule only applies on one machine, it belongs in that machine's device-delta block in `CLAUDE-CHECKIN.md`, not here.

## What's in here

| File | When to read it |
|---|---|
| `device-comms.md` | Every session. Two mandatory session-start rules — `git pull` first, then check this device's GitHub-issue inbox — plus the cross-device issue protocol and label taxonomy. |
| `workflow.md` | Every session. Covers commit/push discipline, when to branch, when live state outranks docs. |
| `incident-rules.md` | Every session. The short list of don't-do-this items that each came from a real incident — read this before touching NiFi flows or credentials in particular. |
| `writing-style.md` | Before writing or editing any `.md` in DesktopShare that could become a blog post — which is most of them. |
| `live-queues.md` | Only if you're touching a system that has an active, live-posting queue — today that's `cso-operator-app` and the Streamers pipeline. |

## What is not in here

- **Technical playbook** for building NiFi / MiNiFi / EFM flows — that's the `nifi-and-ai` skill (`../skills/nifi-and-ai/`).
- **Device specs and per-device port-forwards / service maps** — that's `../CLAUDE-CHECKIN.md`.
- **App-specific rules** — those live alongside each app's code. e.g. `cso-operator-app/CLAUDE.md`.

## Contributing

Fix in place with a one-line dated note, don't fork. If something here turns out to only apply to one device, demote it to that device's block in `CLAUDE-CHECKIN.md`.
