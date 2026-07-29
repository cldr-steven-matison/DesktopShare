**Cloudera Edge Flow Manager (EFM) with Jetson Orin Nano for AI at the Edge**

```terminal

│   ______    ______   __    __ 
│  /\  ___\  /\  ___\ /\ '-./  \
│  \ \  __\  \ \  __\ \ \ \-./\ \ 
│   \ \_____\ \ \_\    \ \_\ \ \_\   
│    \/_____/  \/_/     \/_/  \/_/ 
│
│  (v2.3.1.0-2)
│ >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
│ Cloudera | EFM | Edge Flow Manager
│ 
│    _  ___   _____ ___ ___   _   
│   | \| \ \ / /_ _|   \_ _| /_\  
│   | .` |\ V / | || |) | | / _ \ 
│   |_|\_| \_/ |___|___/___/_/ \_\
│ 
│  (v7.2)
│ >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  
│ NVIDIA | Nano | Jetson                            
                                     

```

Hey folks, Steven Matison here. If you’ve been following my Cloudera Community posts, my GitHub pages at [cldr-steven-matison.github.io](https://cldr-steven-matison.github.io/), or the fresh content now flowing to [stevenmatison.com](https://stevenmatison.com), you know I’m all about making complex streaming, flow management, and edge AI setups actually *work* on real hardware — windows, mac, ubuntu, docker, kubernetes, and now a new NVIDIA Jetson Orin Nano.  

Today we’re going deep: with local lab for **Cloudera Edge Flow Manager (EFM / CEM)**, next to the full **Cloudera Streaming Operator (CSO)** stack (CFM + CSM + CSA) on Minikube Kubernetes, and then deploying **MiNiFi C++ agents** to NVIDIA Jetson Orin Nano.  

The goal? Design ai enabled nifi flows + ML model assets once in EFM, push them to edge agents.  We will execute custom models *inside* MiNiFi on the Jetson, and ship system + processor + model metrics straight to the Prometheus instance living inside the CSO stack. All of it documented exactly the way I like — repeatable, with every command, and all the gotchas spelled out.

This post directly extends:
- My full **[Cloudera Streaming Operators on Minikube](https://stevenmatison.com/blog/Cloudera-Streaming-Operators/)** guide on the Cloudera Community (and the companion repo).
- My **[Observability with Cloudera Streaming Operators](https://stevenmatison.com/blog/Observability-with-Cloudera-Streaming-Operators/)** blog (Prometheus + Grafana for NiFi, Kafka, Flink).
- My **[MiNiFi Kubernetes PlayGround](https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground)** for testing MiNiFi
- Official Cloudera CEM/EFM and MiNiFi C++ docs (with my WSL2/Windows/Jetson tweaks).

Let’s dive in.


### Create a Persisted Edge Flow Manager on Kubernetes

[How to Install Persisted EFM on Kubernetes](efm-persistance.md)

### Add Compatible MiNiFi Java & C++ Binaries from Cloudera Archive

  [Installing EFM Binaries for Windows, Linux, and Nividia](efm-binaries.md).

###  Restart EFM

After installing binaries be sure to restart EFM.

```bash
kubectl rollout restart deployment/efm -n cld-streaming
kubectl wait --for=condition=ready pod -l app=efm -n cld-streaming --timeout=120s
```

**Warning** it takes several minutes for EFM to re roll.  Be patient.  Use K9s or pod logs to confirm that EFM finishes startup and discloses its final hosted URLs.

[ insert text here from startup log ]

### Expose EFM for Easy Access

```bash
minikube tunnel
```

[http://127.0.0.1:10090/efm/ui](http://127.0.0.1:10090/efm/ui)

Open that URL in your browser — you should land on the EFM login screen.

Now create a class and you can get to the Deploy Agent CLI Command Screen to verify all of the binaries are there.

[ insert screen shot of binary drop downs ]

[ I need to update this, we moved to the windows host IP for efm to be accessible to Jetson.  However the tunnel method is preferred since the url is consistent. Currently in windows the minikube sevice command the open port is random and you have to visit and append /efm/ui/ on end of the browser url  - better way would be appreciated ]

### Windows Networking: Mirrored Mode vs NAT Mode (WSL2 + Jetson)

**First — check which WSL2 networking mode you are in (PowerShell):**

```powershell
wsl hostname -I
```

- If the first IP matches your Windows LAN IP (e.g. `gaming-pc-lan-ip`) → you are in **mirrored networking mode**
- If the first IP is a `172.x.x.x` address → you are in **NAT mode**

#### Mirrored Networking Mode (current setup)

WSL2 shares the Windows host IP directly. Any port bound on `0.0.0.0` inside WSL is reachable from the LAN at `gaming-pc-lan-ip:<port>` — **no portproxy needed**.

**DO NOT add portproxy rules in mirrored mode.** Stale portproxy rules pointing to old `172.x` WSL IPs will intercept traffic and cause silent connection failures even when the TCP test succeeds. Always check for and remove stale rules:

```powershell
netsh interface portproxy show all
# Delete any stale entries pointing to old 172.x addresses
netsh interface portproxy delete v4tov4 listenport=9092 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=10090 listenaddress=0.0.0.0
```

You still need Windows Firewall inbound rules for each port. Add them once (PowerShell as Administrator):

```powershell
New-NetFirewallRule -DisplayName "WSL EFM 10090" -Direction Inbound -Protocol TCP -LocalPort 10090 -Action Allow
New-NetFirewallRule -DisplayName "WSL Kafka Brokers External" -Direction Inbound -Protocol TCP -LocalPort 31623,31850,31935,30336 -Action Allow
```

#### NAT Mode (older WSL2 setups)

If you are in NAT mode, portproxy rules are required. Replace `172.26.201.5` with your current WSL2 IP (`ip addr show eth0` in WSL):

```powershell
netsh interface portproxy add v4tov4 listenport=10090 listenaddress=0.0.0.0 connectport=10090 connectaddress=172.26.201.5
netsh interface portproxy add v4tov4 listenport=9092 listenaddress=0.0.0.0 connectport=9092 connectaddress=172.26.201.5
```

The WSL2 IP changes on every reboot in NAT mode — update portproxy entries any time the Jetson loses connectivity.

### Kafka External Access for NVIDIA / Jetson Agents

`kafka-eval.yaml` only has `internal` listeners. External agents (Jetson, NVIDIA desktop) cannot reach Kafka brokers using internal cluster DNS. Use `kafka-nodeport.yaml` which adds an external NodePort listener with `advertisedHost` overrides so agents get `gaming-pc-lan-ip` addresses back from Kafka metadata.

**Apply the external listener config:**

```bash
kubectl apply -f ClouderaStreamingOperators/kafka-nodeport.yaml -n cld-streaming
kubectl wait kafka/my-cluster --for=condition=Ready --timeout=120s -n cld-streaming
```

**Get assigned NodePorts after apply:**

```bash
kubectl get svc -n cld-streaming | grep "my-cluster-combined\|external-bootstrap"
```

Expected output (ports vary per deployment):
```
my-cluster-combined-0                 NodePort  ...  9094:31850/TCP
my-cluster-combined-1                 NodePort  ...  9094:31935/TCP
my-cluster-combined-2                 NodePort  ...  9094:30336/TCP
my-cluster-kafka-external-bootstrap   NodePort  ...  9094:31623/TCP
```

**Confirm the advertised bootstrap address:**

```bash
kubectl get kafka my-cluster -n cld-streaming -o jsonpath='{.status.listeners[?(@.name=="external")].bootstrapServers}{"\n"}'
# Should return: gaming-pc-lan-ip:31623
```

**Start port-forwards (required after every WSL/Windows restart):**

The NodePorts live on the Minikube node (`192.168.49.2`), not directly on `gaming-pc-lan-ip`. These port-forwards bridge them:

```bash
kubectl port-forward --address 0.0.0.0 svc/my-cluster-kafka-external-bootstrap 31623:9094 -n cld-streaming > /tmp/pf-kafka-bootstrap.log 2>&1 &
kubectl port-forward --address 0.0.0.0 svc/my-cluster-combined-0 31850:9094 -n cld-streaming > /tmp/pf-kafka-0.log 2>&1 &
kubectl port-forward --address 0.0.0.0 svc/my-cluster-combined-1 31935:9094 -n cld-streaming > /tmp/pf-kafka-1.log 2>&1 &
kubectl port-forward --address 0.0.0.0 svc/my-cluster-combined-2 30336:9094 -n cld-streaming > /tmp/pf-kafka-2.log 2>&1 &
```

Verify all four are listening:

```bash
ss -tlnp | grep -E "31623|31850|31935|30336"
```

**Set MiNiFi `bootstrap.servers` on the Jetson/NVIDIA machine to:**

```
gaming-pc-lan-ip:31623
```

No `/etc/hosts` entries or portproxy rules needed.

### Restarting MiNiFi on the Jetson

When deployed via EFM agent deployer with `serviceName=minifi`, try these in order:

```bash
# Option 1 — systemd service (most common)
sudo systemctl restart minifi

# Option 2 — find and kill the process (forces restart if watchdog is running)
sudo kill $(pgrep -f minifi)

# Option 3 — use the MiNiFi startup script directly
~/minifi-1.26.02/bin/minifi.sh restart

# Check status
sudo systemctl status minifi
tail -f ~/minifi-1.26.02/logs/minifi-app.log
```

If none of the above work, a Jetson reboot is the fallback. After reboot MiNiFi should auto-start if the service was registered at install time.


Go ahead and grab the Linux agent cli code:
 
```bash
curl -L \
 -d agentClass=KubernetesPod \
 -d agentIdentifier=e99e45f5-70f5-4847-af76-4f620b764aa9 \
 -d agentType=cpp \
 -d agentVersion=1.26.02 \
 -d autoConfigureSecurity=false \
 -d baseUrl=http%3A%2F%2F127.0.0.1%3A10090%2Fefm%2Fapi \
 -d hbPeriod=5000 \
 -d osArch=linux \
 -d serviceName=minifi \
 -d serviceUser=minifi \
 -d trustSelfSignedCertificates=false \
 http://gaming-pc-lan-ip:10090/efm/api/agent-deployer/script | bash -
```

Now that we have an agent curl code, we will wrap that up into a docker deployed kubernetes pod and test it on minikube.  

First pull the docker image we need:

```bash
eval $(minikube docker-env)
docker pull --platform linux/amd64 ubuntu:22.04
```

Next create `minifi-agent-pod.yaml`

Notice we have changed the `baseUrl` and the `http://` host to `efm.cld-streaming.svc:10090` internal hostname and port for EFM on kubernetes.
We ca do this here because this agent is local to the minikube cluster.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: minifi-agent-k8s
  namespace: cld-streaming
spec:
  containers:
  - name: minifi
    image: ubuntu:22.04
    imagePullPolicy: IfNotPresent
    command: ["/bin/bash", "-c"]
    args:
    - |
      apt-get update && apt-get install -y curl tar python3 python3-pip python3-venv
      ln -s /usr/bin/python3 /usr/bin/python || true
      curl -L \
       -d agentClass=KubernetesPod \
       -d agentIdentifier=e99e45f5-70f5-4847-af76-4f620b764aa9 \
       -d agentType=cpp \
       -d agentVersion=1.26.02 \
       -d autoConfigureSecurity=false \
       -d baseUrl=http%3A%2F%2Fefm.cld-streaming.svc%3A10090%2Fefm%2Fapi \
       -d hbPeriod=5000 \
       -d osArch=linux \
       -d serviceName=minifi \
       -d serviceUser=root \
       -d trustSelfSignedCertificates=false \
       http://efm.cld-streaming.svc:10090/efm/api/agent-deployer/script | bash -
      tail -f /dev/null                      
```

Apply the Agent Pod:

```bash
kubectl apply -f minifi-agent-pod.yaml
kubectl wait --for=condition=ready pod minifi-agent-k8s -n cld-streaming --timeout=60s\nkubectl logs minifi-agent-k8s -n cld-streaming
```

Be patient and watch the pod log and app logs:

```bash
kubectl logs minifi-agent-k8s -n cld-streaming -f
kubectl exec -it minifi-agent-k8s -n cld-streaming -- tail -f /nifi-minifi-cpp-1.26.02/logs/minifi-app.log
```

[ add expected output here ]

Within a few minutes Minifi should be running in the pod and the agent should appear in the `KubernetesPod` Class in the EFM Dashboard.  Win!

[ screen shot here ]

### 3. Deploy the MiNiFi C++ Agent on the Jetson Orin Nano

Generate a **unique** agent identifier test class `NvidiaNano` and fetch the CLI command for arch64:

```bash
curl -L \
 -d agentClass=NvidiaNano \
 -d agentIdentifier=$(cat /proc/sys/kernel/random/uuid) \
 -d agentType=cpp \
 -d agentVersion=1.26.02 \
 -d autoConfigureSecurity=false \
 -d baseUrl=http%3A%2F%2F127.0.0.1%3A46663%2Fefm%2Fapi \
 -d hbPeriod=5000 \
 -d osArch=linuxaarch64 \
 -d serviceName=minifi \
 -d serviceUser=minifi \
 -d trustSelfSignedCertificates=false \
 http://<YOUR_EFM_HOST_IP:10090/efm/api/agent-deployer/script | bash -
```

**Replace** `<YOUR_EFM_HOST_IP>` with your actual lab machine IP.

The script will:
- Contact EFM
- Download the **linux-arm64** binary + extra extensions
- Extract and configure MiNiFi C++
- Start the agent as a background process.

### 4. Verify the Agent Is Running

```bash
tail -f minifi-1.26.02/logs/minifi-app.log
```

The agent should appear almost immediately in the EFM UI → **Monitor** → **Agents** under class `NvidiaNano`.

[ screen shot here ]

### 5. Deliver Resources to the Agent

Agent Resources are manageable from within EFM.  Upload your files to EFM, then assign them as necessary to Agents in their own Resources tab, and they will appear in /assets/ directory.  

**Warning** I did have to chmod +x my agent files on the Jetson.  I will work on this later but for now its an ok manual step before testing curl on the jetson.

#### Execute Script `gpu_nifi_tensorRT-3.py`

cat `files/gpu_nifi_tensorRT-3.py`

```bash
import tensorrt as trt
import json

# Callback class for reading the session stream
class ReadContentCallback:
    def __init__(self):
        self.content = ""
    def process(self, input_stream):
        self.content = input_stream.read().decode('utf-8')
        return len(self.content) # Good practice to return bytes read

# Callback class for writing the session stream
class WriteContentCallback:
    def __init__(self, data):
        self.data = data
    def process(self, output_stream):
        encoded_data = self.data.encode('utf-8')
        output_stream.write(encoded_data)
        return len(encoded_data)  # <--- CRITICAL: MiNiFi C++ needs this integer return!


# This is the exact entrypoint MiNiFi C++ calls on every loop execution
def onTrigger(context, session):
    
    flow_file = session.get()
    
    if flow_file:
        try:
            # 1. Read upstream payload
            reader = ReadContentCallback()
            session.read(flow_file, reader)
            
            if reader.content.strip():
                payload = json.loads(reader.content)
            else:
                payload = {}
                
            # 2. Extract TensorRT Properties
            logger = trt.Logger(trt.Logger.INFO)
            tensorrt_info = {
                "version": str(trt.__version__),
                "status": "Active"
            }
            
            # 3. Append to JSON structure cleanly
            if isinstance(payload, dict):
                payload['tensorrt'] = tensorrt_info
            elif isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        item['tensorrt'] = tensorrt_info
            
            updated_json = json.dumps(payload)
            
            # 4. Write back to the flow file and update attributes
            # In MiNiFi C++, session.write modifies the flow_file in place or handles it internally.
            session.write(flow_file, WriteContentCallback(updated_json))
            
            session.putAttribute(flow_file, "python.tensorrt.execution", "Success")
            
            # 5. Route to success relationship
            session.transfer(flow_file, REL_SUCCESS)
            
        except Exception as e:
            # If it breaks, append the error message to an attribute and fail it
            session.putAttribute(flow_file, "python.error", str(e))
            session.transfer(flow_file, REL_FAILURE)

```

### 6. Import the Agent Flow

The final step is to import and publish flow so we can confirm everything is working.
I did all the hard work here getting python installed on edge devices and discovering these initial test flows.
Most important: TensorRT flow which is the one we want, but I also include the first TailLog flow.

#### EFM Agent Flow Files - TensorRT - ListenHttp -> ExecuteScript -> PublishKafka

- [NvidiaNano](files/efm/NvidiaNano-TensorRT.json) - Operational
- [WindowsDesktop](files/efm/WindowsDesktop-TensorRT.json) - Operational
- [KubernetesPod](files/efm/KubernetesPod-TensorRT.json) - Operational

#### EFM Agent Flow Files - `minifi-app.log` - TailLog -> PublishKafka

- [NvidiaNano](files/efm/NvidiaNano.json) - Operational
- [WindowsDesktop](files/efm/WindowsDesktop.json) - Operational
- [KubernetesPod](files/efm/KubernetesPod.json) - Operational

 
### 7. Testing Nvidia Jetson Flow

Chmod Command

Curl Command

Kafka Messages


### Add EFM to Your CSO Prometheus Observability

There are two metrics I want on the same Grafana that already watches NiFi/Kafka/Flink: **EFM's
own health** (server-side, scraped from the EFM pod) and **the Jetson agent's system + processor +
model-inference metrics** (edge-side, published by the agent itself). The full three-layer story —
EFM server, MiNiFi C++ native publisher, and the heartbeat path for tiny agents — is written up
canonically in `efm-metrics.md`. This section is the Jetson-specific slice; keep the two in sync.

**Layer 1 (EFM server metrics) is field-validated** — on FTF3XR2065, not this device — see
`efm-metrics.md` Layer 1. One correction that applies everywhere, including here: the actuator
Prometheus endpoint is served on the **`efm-ui`/`10090`** port under `/efm`, not `metrics/9092` as
originally written below — `9092` accepts a connection but returns an empty reply. Point any
`ServiceMonitor` or scrape config at `10090/efm/actuator/prometheus`.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: efm
  namespace: cld-streaming
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: efm
  endpoints:
  - port: efm-ui                      # NOT `metrics` — 9092 serves nothing
    path: /efm/actuator/prometheus
    interval: 15s
```

```bash
kubectl apply -f efm-service-monitor.yaml
```

The EFM image ships no `curl` — check the endpoint via a host port-forward, not `kubectl exec`:

```bash
kubectl port-forward -n cld-streaming deploy/efm 10190:10090 &
curl -s http://localhost:10190/efm/actuator/prometheus | head
```

**Layer 2 — Jetson agent metrics (published on the edge device) — field-validated 2026-07-29 on
this device (NvidiaNano, real Jetson hardware, systemd-managed agent).** MiNiFi C++ has a native
Prometheus publisher — no ExecuteScript, no sidecar — shipped as the `libminifi-prometheus.so`
extension. **The property names below are corrected from what this doc originally said**:
`nifi.c2.enable.metrics` / `nifi.c2.metrics.publisher` / `nifi.c2.metrics.publisher.prometheus.port`
don't exist in this build (confirmed against the binary and the shipped config template) — the
real namespace is `nifi.metrics.publisher.*`. Add a new file under `conf/minifi.properties.d/`
(don't edit `minifi.properties` directly — its own header warns changes there are lost on upgrade,
and this build already uses the `.d/` convention: EFM writes its own `90_c2.properties` there on
enrollment):

```properties
# conf/minifi.properties.d/95-metrics.properties
nifi.metrics.publisher.agent.identifier=<agent-uuid, matches nifi.c2.agent.identifier>
nifi.metrics.publisher.class=PrometheusMetricsPublisher
nifi.metrics.publisher.PrometheusMetricsPublisher.port=9936
nifi.metrics.publisher.metrics=QueueMetrics,RepositoryMetrics,DeviceInfoNode,FlowInformation
```

That stands up a Prometheus endpoint **on the Jetson itself** (`9936` here is the agent's own port
on the Nano — unrelated to EFM's port on the EFM pod; they'd only collide if you pick the same
number). Prometheus reaches it one of two ways: a static scrape config pointing at the Jetson
host:port (simplest for a fixed-IP Nano), or via EFM knowing the scrape target once the agent is
enrolled.

Confirmed live on this Jetson after a restart:

```text
[...] [PrometheusExposerWrapper] [info] Started Prometheus metrics publisher on port 9936
$ ss -tlnp | grep 9936
LISTEN 0  200  0.0.0.0:9936  0.0.0.0:*  users:(("minifi",pid=203867,fd=18))
$ curl -s http://127.0.0.1:9936/metrics | wc -l
204
```

Binds `0.0.0.0` (confirmed via `ss`), so it's reachable from the LAN in principle, not just the
device itself — the second half of the edge-networking check (a host firewall rule allowing
`9936` in) was **not validated** on this pass; this device's `ufw` state needs a human with sudo to
inspect, and the rule shouldn't be added reflexively before the CSO Prometheus side is ready to use
it. That, plus the actual scrape-target wiring on the CSO Prometheus, is the remaining work — see
"Status & next owner" below.

**Restarting the agent to apply this config is not as forgiving as it looks.** Field-tested here:
`sudo systemctl restart minifi` is the only reliable path, and it needs an interactive password —
no `NOPASSWD` sudoers entry exists on this device. `minifi.sh restart`/`start`/`stop` are **not** a
sudo-free alternative — the script's Linux path just calls `systemctl restart minifi.service`
internally. And killing the process directly does **not** reliably bring it back: this build's
`Restart=on-failure` only force-restarts on a specific C2-triggered exit code
(`RestartForceExitStatus=3`), not on an externally sent `SIGTERM` — confirmed live, a `kill` left
the agent `inactive` with no watchdog respawn until a human ran `systemctl start`. This supersedes
the "Restarting MiNiFi on the Jetson" section above — treat Option 1 there as the only dependable
one, and don't rely on Option 2 as an unattended fallback.

Once both layers are wired into the actual CSO Prometheus scrape config, the Grafana dashboard
shows Jetson CPU/GPU/temp + model-inference latency + flow throughput alongside the datacenter
NiFi/Kafka/Flink panels. **Status:** the agent-side publisher itself is now confirmed working
end-to-end on real hardware; getting a scrape target pointed at it and a Grafana panel built is the
open item, handed to WindowsDesktop (see `efm-metrics.md` and the issue thread for #16).

### Resources

### Appendix 