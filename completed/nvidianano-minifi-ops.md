# NvidiaNano MiNiFi agent — operations runbook

The living ops reference for the MiNiFi C++ agent on the Jetson Orin Nano (`tunastreet`,
`192.168.1.197`). Connection facts, health checks, service control, and a full clean
reinstall — the stuff you need when the agent is misbehaving and you don't want to re-derive
the paths off the device. The build/story version of all this is the blog
(`hacking-the-jetson-blog.md`); the enterprise EFM-on-Kubernetes side is
`efm-nvidia-jetson-nano.md`. This file is the runbook.

## What's running

A MiNiFi C++ agent reports into the array's Cloudera Edge Flow Manager (EFM) for centralized
flow management and produces to Kafka. EFM + Kafka run on the **WindowsDesktop** across the LAN
(`192.168.1.121`, confirmed 2026-07-26).

- Install dir: `/home/tunastreet/nifi-minifi-cpp-1.26.02`
- Binary: `bin/minifi`
- systemd unit: `minifi.service` (enabled, starts on boot)
- App log: `/home/tunastreet/nifi-minifi-cpp-1.26.02/logs/minifi-app.log`
- Config dir: `/home/tunastreet/nifi-minifi-cpp-1.26.02/conf/`
  - `minifi.properties` — main properties (C2/EFM settings). Don't hand-edit; its own header
    warns changes are lost on upgrade. Use `minifi.properties.d/` drop-ins instead — EFM itself
    writes `90_c2.properties` there on enrollment.
  - `config.yml` — the actual flow definition (processors, connections)

## EFM (C2) connection

- Server: `http://192.168.1.121:10090/efm/api`
  - Heartbeat: `.../c2-protocol/heartbeat`
  - Ack: `.../c2-protocol/acknowledge`
- Agent class: `NvidiaNano`
- Agent identifier: `4ca82a0d-8e04-4ede-b59d-379de1495f2b`
- Heartbeat period: 5000ms

## Kafka connection

- Bootstrap broker: `192.168.1.121:31623`
- Producer client id (seen in logs): `minifi-agent-nvidia`

## Health check

```bash
systemctl status minifi --no-pager
tail -f /home/tunastreet/nifi-minifi-cpp-1.26.02/logs/minifi-app.log | grep -i "heartbeat\|kafka"

# port reachability, no nc needed
timeout 3 bash -c "cat < /dev/null > /dev/tcp/192.168.1.121/10090" && echo open || echo closed
timeout 3 bash -c "cat < /dev/null > /dev/tcp/192.168.1.121/31623" && echo open || echo closed
```

## Two Kafka signatures that look like faults but aren't

### Remote EFM/Kafka restart — a burst of `Connection refused`, then it settles

When the stack gets restarted on the WindowsDesktop side, `minifi-app.log` fills with Kafka
`Connection refused` on every broker (including bootstrap), sometimes with a
`"verify that security.protocol is correctly configured, broker might require SASL
authentication"` hint. That hint is noise from the broker bouncing mid-restart, **not** an actual
security/auth config change. It settles on its own within ~15–20 min of the ports reopening — no
Jetson-side action needed.

### Advertised-listener on a different port than bootstrap

Kafka's bootstrap response can hand the client an **advertised listener** on a *different* port
than the bootstrap port (e.g. bootstrap on `31623`, but the partition leader advertised as
`192.168.1.121:31935`). If only the bootstrap port is open on the broker side (firewall, k8s
NodePort) but the advertised port isn't, you'll see:

- `PublishKafka` "Failed to deliver ... Message timed out"
- `KafkaConnection` "Connection setup timed out in state CONNECT" on the advertised port
  specifically (not the bootstrap port)

This is a broker-side `advertised.listeners` / port-exposure issue, fixable only on the EFM/Kafka
host — not from the Jetson. See `efm-nvidia-jetson-nano.md` for the NodePort + port-forward setup
that exposes all four external broker ports.

## Service control

`minifi.sh` (preferred) and `systemctl` both work.

```bash
# minifi.sh
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh start
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh stop
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh restart
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh status

# systemctl
sudo systemctl start minifi
sudo systemctl stop minifi
sudo systemctl restart minifi
systemctl status minifi --no-pager
```

Disable / re-enable auto-start at boot:

```bash
sudo systemctl disable minifi
sudo systemctl start minifi   # manual start after disabling
```

:warning: **Restarting to apply a config change is not as forgiving as it looks.**
`sudo systemctl restart minifi` is the only reliable path, and it needs an interactive password —
there's no `NOPASSWD` sudoers entry on this device. `minifi.sh restart/start/stop` are **not** a
sudo-free alternative: the script's Linux path just calls `systemctl restart minifi.service`
internally. And killing the process directly does **not** reliably bring it back — this build's
`Restart=on-failure` only force-restarts on the specific C2-triggered exit code
(`RestartForceExitStatus=3`), not on an externally sent `SIGTERM`. Confirmed live: a `kill` left
the agent `inactive` with no watchdog respawn until a human ran `systemctl start`.

## Full clean reinstall

When the install is wedged badly enough that a restart won't fix it — corrupted state repos,
a bad `User=`/ownership tangle, a half-applied EFM push. Assumes a fresh
`nifi-minifi-cpp-1.26.02/` tarball is re-extracted to the same path.

### 1. Uninstall / remove completely

```bash
# stop any running agent
sudo pkill -9 minifi

# remove the systemd service
sudo systemctl stop minifi 2>/dev/null
sudo systemctl disable minifi 2>/dev/null
sudo rm -f /usr/local/lib/systemd/system/minifi.service
sudo systemctl daemon-reload

# delete the install directory
sudo rm -rf /home/tunastreet/nifi-minifi-cpp-1.26.02

# delete leftover state/config/cache
rm -rf ~/.cache/minifi ~/.config/minifi ~/.local/share/minifi
sudo rm -rf /var/lib/minifi 2>/dev/null
```

### 2. Install the service (after re-extracting the tarball)

```bash
sudo /home/tunastreet/nifi-minifi-cpp-1.26.02/bin/minifi.sh install
# creates /usr/local/lib/systemd/system/minifi.service
```

### 3. Run as the desktop user, not root

The agent must run as `tunastreet` (uid 1000), not root, or any flow that touches the GNOME/X11
display (the streamChat / matrix launchers) breaks — root has no `XDG_RUNTIME_DIR`/D-Bus session.
Add to `/usr/local/lib/systemd/system/minifi.service`:

```ini
[Service]
User=tunastreet
```

Then fix ownership of anything created while it ran as root, or it crash-loops on startup with
`Failed opening file .../minifi-app.log for writing: Permission denied`:

```bash
sudo chown -R tunastreet:tunastreet /home/tunastreet/nifi-minifi-cpp-1.26.02
sudo systemctl daemon-reload
sudo systemctl restart minifi
```

## This build's extensions

Extra C++ extensions are staged into this agent — `libminifi-execute-process`,
`-lua-script-extension`, `-python-script-extension`, `-opc-extensions`, `-llamacpp` — pushing it
to **79 processors vs. the stock 74**. The manifest is `files/efm/NvidiaNano-manifest.json`. The
`python-script` and `llamacpp` extensions are what make edge inference real: Python inside the
agent, or a local model.

**Inference no longer lives in the agent, though.** As of 2026-08-02 the TensorRT leg runs against
a resident daemon on `127.0.0.1:5910` (`trt-infer.service`, a systemd *user* unit) rather than
loading an engine inside `ExecuteScript` — which can't work, because `ExecuteScript` re-reads its
script on every trigger. Restarting the model is `systemctl --user restart trt-infer` and does
**not** touch this agent. See `efm-nvidia-nano-inference.md`.

## Related

- `efm-nvidia-jetson-nano.md` — persisted EFM on Kubernetes, binary staging, Kafka NodePort +
  port-forward exposure, WSL2 mirrored-vs-NAT networking.
- `efm-metrics.md` / `efm-nvidia-jetson-nano.md` §metrics — the native Prometheus publisher
  (`nifi.metrics.publisher.*`, port `9936` on this device), field-validated on this Jetson.
- `efm-nvidia-nano-inference.md` — real TensorRT inference on this agent: the resident daemon,
  the three front doors (C++ `ExecuteScript`, custom Python processor, Java synchronous
  round-trip), and measured latency.
- `hacking-the-jetson-blog.md` — the build story (screensaver, OLED, streamChat, sensors).
- `completed/nvidianano-streamchat-launcher.md` — the `:8081/streamChatListener` HTTP-to-display
  feature that runs through this agent.
