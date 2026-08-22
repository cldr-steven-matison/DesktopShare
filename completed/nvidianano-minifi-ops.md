# NvidiaNano MiNiFi agent — operations runbook

The living ops reference for the MiNiFi agent on the Jetson Orin Nano (`tunastreet`,
`192.168.1.197`). Connection facts, health checks, service control, and a full clean
reinstall — the stuff you need when the agent is misbehaving and you don't want to re-derive
the paths off the device. The build/story version of all this is the blog
(`hacking-the-jetson-blog.md`); the enterprise EFM-on-Kubernetes side is
`efm-nvidia-jetson-nano.md`. This file is the runbook.

## What's running

**One agent: the MiNiFi *Java* agent.** The full-Java cutover landed 2026-08-14; everything in
this file's "current" sections describes that agent. The older C++ install is retired — still on
disk, service stopped and disabled — and its material is kept below under
[Retired: the C++ agent](#retired-the-c-agent) so a wedged-install recovery still has a
reference. **Don't follow the C++ paths for live work; they point at an agent that isn't running.**

- Version: `2.24.08.0-19`
- Install dir: `/home/tunastreet/minifi-java-deploy/minifi-2.24.08.0-19`
- Agent class: `NvidiaNano`
- Agent identifier: `2bcc2f9a-f584-4ac9-8c42-133b235a3201` (EFM-minted via `generateCommand`)
- App log: `/home/tunastreet/minifi-java-deploy/minifi-2.24.08.0-19/logs/minifi-app.log`
- Config: `conf/bootstrap.conf` — this is where the C2/EFM settings live on the Java agent
  (**not** `minifi.properties` / `minifi.properties.d/`, which is the C++ layout)
- Flow: the class's three-leg HandleHttp flow, EFM-managed —
  `:8080 /classify → 127.0.0.1:5910` (trt-infer), `:8081 /streamChatListener → :5902` (mpv),
  `:8082 /matrixListener → :5901` (matrix)

**Service management is SysV, not a native systemd unit.** `/etc/init.d/minifi-java` is the real
script; systemd's sysv-generator surfaces it as `minifi-java.service` at
`/run/systemd/generator.late/`. Consequence: `systemctl is-enabled minifi-java` answers
**`disabled`** and that is *not* a problem — boot start comes from the `rc2.d/S65minifi-java`
link instead. Verified live: the Jetson booted `2026-08-14 17:02:10` and the agent process
started `17:02:25`, 15 seconds later. The init script starts as root and drops to the desktop
user via `sudo -u tunastreet`, which is what keeps the X11/display legs working.

## EFM (C2) connection

- Server: `http://192.168.1.121:10090/efm/api`
  - Heartbeat: `.../c2-protocol/heartbeat`
  - Ack: `.../c2-protocol/acknowledge`
- Agent class: `NvidiaNano`
- Agent identifier: `2bcc2f9a-f584-4ac9-8c42-133b235a3201`
- Heartbeat period: 5000ms (`c2.agent.heartbeat.period` in `conf/bootstrap.conf`)

### `c2.full.heartbeat` — the one that takes EFM down

**The Java agent's `c2.full.heartbeat` defaults to `true`, and a full heartbeat carries the entire
runtime manifest — ~1.25 MB, every 5 seconds.** Confirmed in the agent's own
`MiNiFiProperties` (key and its `"true"` default sit together in
`lib/bootstrap/minifi-commons-api-2.24.08.0-19.jar`), and measured from EFM's own
`efm_heartbeat_contentLength` metric.

Measured 2026-08-22, ten minutes of a freshly-booted EFM:

| Agent | Type | Heartbeats | Payload total | Per beat |
|---|---|---|---|---|
| NvidiaNano | Java | 214 | 274.6 MB | 1.25 MB |
| WindowsDesktop | Java | 39 | 53.4 MB | 1.31 MB |
| StarlinkAI | Java | 38 | 49.0 MB | 1.25 MB |
| AMOLED | C++ | 2 | 3,652 B | 1.8 KB |

~377 MB of heartbeat payload in ten minutes, into EFM's 2 GB heap (`-Xms2048m -Xmx2048m`). The
C++ agents don't do this at all — the gap is three orders of magnitude.

On its own this is survivable; EFM ran for months on it. It becomes an outage the moment anything
makes EFM *retain* heartbeat bodies — see `blog/efm-persistance.md` / EFM's
`efm.heartbeat.persistContent`. With retention on, EFM OOMs and every request hangs rather than
errors, which reads like a dead cluster.

The fix is one line per Java agent in `conf/bootstrap.conf`:

```properties
c2.full.heartbeat=false
```

The agent then sends a manifest *hash* and EFM asks for the full manifest only when it doesn't
recognise it (`DescribeManifestOperationHandler` in `c2-client-service`). Takes effect on agent
restart. **This applies to every Java agent, not just this one.**

Applied and verified 2026-08-22:

| Agent | Before | After | Reduction |
|---|---|---|---|
| NvidiaNano | 1,245,184 B | 7,462 B | 167× |
| WindowsDesktop | 1,310,720 B | 5,799 B | 226× |
| StarlinkAI | 1,245,184 B | *not yet* — filed as #215 (needs the device) | — |

**How to tell it took:** EFM tags the metric with `agentManifestId`, so the fix shows up as a
*series split*, not as a falling number. The old `agentManifestId="minifi"` series stops
incrementing and a fresh `agentManifestId=""` series starts with small beats — sum ÷ count on the
new series is the real per-beat size. Reading only the old series makes it look like nothing
changed.

## Kafka connection

- Bootstrap broker: `192.168.1.121:31623`
- The two broker signatures below are broker-side behaviour and apply to either agent runtime.

## Health check

```bash
systemctl status minifi-java --no-pager
tail -f /home/tunastreet/minifi-java-deploy/minifi-2.24.08.0-19/logs/minifi-app.log \
  | grep -i "heartbeat\|kafka"

# port reachability, no nc needed
timeout 3 bash -c "cat < /dev/null > /dev/tcp/192.168.1.121/10090" && echo open || echo closed
timeout 3 bash -c "cat < /dev/null > /dev/tcp/192.168.1.121/31623" && echo open || echo closed
```

A wall of `Send Heartbeat failed to C2 server` in `minifi-app.log` means EFM is unreachable or
wedged, not that the agent is broken — check EFM first (`kubectl -n cld-streaming logs -l app=efm`,
and grep it for `OutOfMemoryError`). Liveness from the EFM side is
`efm_heartbeat_count_total{agentId="2bcc2f9a-..."}` on `/efm/actuator/prometheus`, **not** the
agent entity's `lastSeen` — that field freezes while heartbeats flow fine.

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

```bash
sudo systemctl start minifi-java
sudo systemctl stop minifi-java
sudo systemctl restart minifi-java
systemctl status minifi-java --no-pager

# the underlying SysV script, equivalent and sudo-free to read
/etc/init.d/minifi-java status
```

Restarting is how a `bootstrap.conf` change takes effect — there is no live-reload for C2
properties. Before restarting, remember this agent owns the three live HandleHttp legs
(`/classify`, `/streamChatListener`, `/matrixListener`), so anything driving the Jetson's display
or inference goes away for the duration.

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
- `blog/efm-persistance.md` — EFM heartbeat retention settings, the other half of the
  `c2.full.heartbeat` story above.

# Retired: the C++ agent

Everything below describes the **MiNiFi C++ agent that was replaced on 2026-08-14**. It is not
running (`systemctl is-active minifi` → `inactive`, `is-enabled` → `disabled`) but the install
directories are still on disk (`~/nifi-minifi-cpp-1.26.02`, `~/nifi-minifi-cpp-sparkplug`). Kept
for the reinstall procedure and the extension/manifest history — **not** as current operating
instructions.

- Install dir: `/home/tunastreet/nifi-minifi-cpp-1.26.02`
- systemd unit: `minifi.service` (stopped, disabled)
- Agent identifier it used: `4ca82a0d-8e04-4ede-b59d-379de1495f2b`
- Config: `conf/minifi.properties` + `minifi.properties.d/` drop-ins (EFM writes `90_c2.properties`
  there on enrollment)

## Service control (C++ agent)

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

