# EFM / MiNiFi Agent Notes

## What this is
This Jetson runs a MiNiFi C++ agent that reports into a remote Apache NiFi
EFM (Edge Flow Manager) server for centralized flow management, plus a
Kafka producer flow (`PublishKafka`) that ships data out.

The EFM + Kafka stack at `192.168.1.121` runs on the user's **Windows
Desktop** (confirmed 2026-07-26). Restarting things over there produces a
very recognizable signature in `minifi-app.log`: a burst of Kafka
`Connection refused` on every broker (including bootstrap), sometimes with
a `"verify that security.protocol is correctly configured, broker might
require SASL authentication"` hint — this hint is just noise from the
broker bouncing mid-restart, not an actual security/auth config change.
Settles on its own within ~15-20 min of ports reopening; no Jetson-side
action needed.

## Install / service
- Install dir: `/home/tunastreet/nifi-minifi-cpp-1.26.02`
- Binary: `bin/minifi`
- Managed by systemd unit: `minifi.service` (enabled, starts on boot)
  - Start: `sudo systemctl start minifi`
  - Status: `systemctl status minifi --no-pager`
  - Logs (app log): `/home/tunastreet/nifi-minifi-cpp-1.26.02/logs/minifi-app.log`
- Config dir: `/home/tunastreet/nifi-minifi-cpp-1.26.02/conf/`
  - `minifi.properties` — main properties (C2/EFM settings live here)
  - `minifi.properties.d/` — drop-in overrides
  - `config.yml` — the actual flow definition (processors, etc.)

## EFM (C2) connection
- Server: `http://192.168.1.121:10090/efm/api`
  - Heartbeat: `.../c2-protocol/heartbeat`
  - Ack: `.../c2-protocol/acknowledge`
- Agent class: `NvidiaNano`
- Agent identifier: `4ca82a0d-8e04-4ede-b59d-379de1495f2b`
- Heartbeat period: 5000ms
- Confirmed working: agent shows up in the EFM UI as of 2026-07-17.

## Kafka connection
- Bootstrap broker: `192.168.1.121:31623`
- Producer client id seen in logs: `minifi-agent-nvidia`
- Confirmed working (no delivery errors) as of 2026-07-17 18:20 EDT.

### Known gotcha (seen this session, self-resolved)
Kafka's bootstrap response can hand the client an **advertised listener**
on a *different* port than the bootstrap port (e.g. bootstrap on `31623`,
but the actual partition leader advertised as `192.168.1.121:31935`).
If only the bootstrap port is exposed/open on the broker side (firewall,
k8s NodePort, etc.) but the advertised port isn't, you'll see:
- `PublishKafka` "Failed to deliver ... Message timed out"
- `KafgaConnection` "Connection setup timed out in state CONNECT" on the
  advertised port specifically (not the bootstrap port)

This is a broker-side `advertised.listeners` / port-exposure issue, not
something fixable from the Jetson side. During this session both
`192.168.1.121:10090` (EFM) and `192.168.1.121:31623` / `31935` (Kafka)
were flapping (refused → open → timeout → open) for a while, consistent
with the remote services still starting up. Everything settled and
confirmed healthy by 2026-07-17 18:20 EDT.

## Quick health check commands
```bash
systemctl status minifi --no-pager
tail -f /home/tunastreet/nifi-minifi-cpp-1.26.02/logs/minifi-app.log | grep -i "heartbeat\|kafka"

# port reachability (no nc needed)
timeout 3 bash -c "cat < /dev/null > /dev/tcp/192.168.1.121/10090" && echo open || echo closed
timeout 3 bash -c "cat < /dev/null > /dev/tcp/192.168.1.121/31623" && echo open || echo closed
```
