Here is the clean, commit-ready structure for your repository. This will package your agent configuration so it’s ready for the Jetson *offline*.

### 1. Repository Structure

Organize your commit like this. This is declarative and doesn't rely on the network to bootstrap:

```text
/minifi-edge-agent
├── binaries
│   └── nifi-minifi-cpp-1.26.02-b30-bin-linux.tar.gz
├── config
│   └── config.yml
└── install.sh

```

### 2. The `install.sh` (Offline Install)

This script ignores EFM networking entirely. It just sets up the agent locally. You can commit this to the repo.

```bash
#!/usr/bin/env bash
# install.sh
set -e

# Extract the binary
mkdir -p /opt/minifi
tar -xzf ./binaries/nifi-minifi-cpp-1.26.02-b30-bin-linux.tar.gz -C /opt/minifi --strip-components=1

# Move config
cp ./config/config.yml /opt/minifi/conf/config.yml

# Set permissions
chown -R minifi:minifi /opt/minifi

# Start (or register as systemd service)
/opt/minifi/bin/minifi.sh start
echo "Agent installed and started locally."

```

### 3. The `config.yml` (The "Last Mile")

This is the only file that matters for the agent to find your server. Edit this file once, commit it, and you're done. Set the `nifi.c2.agent.heartbeat.reporter.url` to the static IP of your host machine (the one running the Minikube EFM service).

```yaml
# conf/config.yml
nifi.c2.enable=true
nifi.c2.agent.heartbeat.reporter.url=http://<YOUR_WINDOWS_HOST_IP>:30517/efm/api/c2
nifi.c2.agent.class=jetson-orin
nifi.c2.agent.identifier=jetson-orin-01
nifi.c2.flow.id=your-flow-id

```

### To "Move Forward" now:

1. **Commit these three files** to your repo.
2. **Pull the repo** directly onto the Jetson.
3. **Run `./install.sh**`.

The agent will immediately attempt to heartbeat to the host IP you defined in `config.yml`. If the network is alive, it connects. If it isn't, the agent simply logs "Connection Failed" to its own logs, but the agent itself is installed and running, which clears your deployment goal.