
***

# NiFi and Music (WSL2 + MiNiFi File Drop Architecture)

**Live Musical Changes → K8s NiFi → Kafka → Nifi → MiNiFi C++ (PutFile) → Python Watchdog → loopMIDI → Strudel**

**Architecture Goal:**
Centralized infrastructure on WSL2 handles the heavy lifting (routing, parsing complex JSON). It sends a flattened, simplified payload (e.g., the string `"60"`) to Kafka. A lightweight MiNiFi C++ agent on the Windows host consumes the message and writes it to a local folder. A lightweight Python watchdog instantly reads the file, strikes the MIDI note via loopMIDI, and deletes the file. Strudel plays the result live.

---

## PHASE 0: Prerequisites (Split Environment)

We split the tools between the Windows Host (Edge) and WSL2 (Core) because WSL2 does not natively expose Windows audio/MIDI hardware.

**1. On the Windows Host (Edge):**
* **Python 3.11+**: `winget install Python.Python.3.11`
* **Python Packages**: Open PowerShell and run: `python -m pip install mido python-rtmidi`
* **loopMIDI**: Download and install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html).
* **MiNiFi C++**: Download the Windows MiNiFi C++ agent (`.zip`) from the Apache NiFi site and extract it to `C:\minifi`.

**2. Inside WSL2 (Core):**
```bash
# Core tools
sudo apt-get update
sudo apt-get install -y git python3 curl mosquitto-clients

# Node 20+ via NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
npm install -g pnpm

# Minikube & Kubectl
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

---

## PHASE 1: Enable Windows Virtual MIDI

1. Open **loopMIDI** from your Windows Start menu.
2. In the "New port-name" box, type exactly: `StrudelKafkaBus`
3. Click the **+** button.
4. Leave loopMIDI running in the background.

---

## PHASE 2: Local Strudel REPL

**Inside WSL2:**
```bash
git clone https://codeberg.org/uzu/strudel.git
cd strudel
pnpm install
pnpm dev
```
→ Open your Windows web browser to `http://localhost:4321/`. Leave this running.

---

## PHASE 3: Core Infrastructure (Minikube / Cloudera Streaming)

**Inside WSL2:**
Spin up your existing containerized data stack.

```bash
minikube start --cpus 6 --memory 12288 --disk-size 40g
kubectl create namespace cld-streaming
# ... (Deploy your docker-registry secret, cert-manager, Strimzi, Kafka, NiFi)
```

Ensure Kafka is accessible to the Windows Host by port-forwarding:
```bash
kubectl port-forward -n cld-streaming my-cluster-kafka-0 9092:9092
```

---

## PHASE 4: Core NiFi Flow (The Heavy Lift)

Open your K8s NiFi UI. This flow strips complex upstream JSON into a dead-simple string for the edge.

1. **ListenHTTP**
   * Listening Port: `8080`
   * Path: `/musical-events`
2. **EvaluateJsonPath**
   * Destination: `flowfile-content` (Replaces the entire FlowFile payload with the JSON path result).
   * Add dynamic property: `midi.note` -> `$.note`
   * *Result: If the incoming payload is `{"note": 60}`, the FlowFile content is now strictly `"60"`.*
3. **PublishKafka**
   * Kafka Brokers: `localhost:9092`
   * Topic Name: `musical.changes`
   * Use Transactions: `false`

---

## PHASE 5: The Edge Python Watchdog (Windows Host)

We create a fast, lightweight loop that watches a specific folder for FlowFiles dropped by MiNiFi. 

Create a folder `C:\midi\inbox`.
Save this script as `C:\midi\watchdog.py`:

```python
import os
import time
import mido
from mido import Message

inbox = r"C:\midi\inbox"
os.makedirs(inbox, exist_ok=True)

port_name = "StrudelKafkaBus"
available_ports = mido.get_output_names()
actual_port_name = next((p for p in available_ports if port_name in p), port_name)

print(f"🎧 Watchdog listening for MiNiFi files in {inbox} -> {actual_port_name}...")

with mido.open_output(actual_port_name) as outport:
    while True:
        for filename in os.listdir(inbox):
            filepath = os.path.join(inbox, filename)
            try:
                # Read the flattened FlowFile content
                with open(filepath, 'r') as f:
                    content = f.read().strip()
                
                # Strike the note if valid
                if content.isdigit():
                    note = int(content)
                    print(f"🎵 Playing Note: {note}")
                    outport.send(Message('note_on', note=note, velocity=100))
                    time.sleep(0.25)
                    outport.send(Message('note_off', note=note, velocity=0))
                
                # Delete the FlowFile once processed
                os.remove(filepath)
            except Exception:
                # File might be locked by MiNiFi actively writing it; skip and catch on the next loop (50ms)
                pass
        time.sleep(0.05)
```

Run it in PowerShell:
```powershell
python C:\midi\watchdog.py
```
Leave this running.

---

## PHASE 6: MiNiFi C++ Config (`PutFile`) (Windows Host)

We configure the MiNiFi C++ agent to act purely as a Kafka consumer that drops files into our watchdog's inbox.

Edit or replace `C:\minifi\conf\config.yml`:

```yaml
MiNiFi Config Version: 3
Flow Controller:
  name: MiNiFi Edge File Drop

Processors:
  - name: ConsumeKafka
    class: org.apache.nifi.minifi.processors.ConsumeKafka
    scheduling strategy: TIMER_DRIVEN
    scheduling period: 100 ms
    Properties:
      Kafka Brokers: localhost:9092
      Topic Names: musical.changes
      Group ID: minifi-midi-group
      Offset Reset: latest

  - name: DropMIDIFile
    class: org.apache.nifi.minifi.processors.PutFile
    scheduling strategy: EVENT_DRIVEN
    Properties:
      Directory: C:\midi\inbox
      Conflict Resolution Strategy: replace

Connections:
  - name: KafkaToFile
    source name: ConsumeKafka
    destination name: DropMIDIFile
    source relationship name: success
```

Run MiNiFi in a new PowerShell window:
```powershell
cd C:\minifi\bin
.\minifi.exe run
```

---

## PHASE 7: Strudel Code (Live Reaction)

In the Strudel REPL (`localhost:4321`), paste the following and hit **Play**:

```js
let cc = await midin('StrudelKafkaBus')

stack(
  note("<c4 eb4 g4 bb4>").voicing().sound("sawtooth")
    // CC listener ready for future expansion
    .decay(cc(3).range(0.1, 0.8))                  
)
.room(0.4)
```

---

## PHASE 8: Integration Test 

From either WSL2 or Windows PowerShell, simulate your upstream producer by sending a test payload to your K8s NiFi instance:

```bash
curl -X POST http://localhost:8080/musical-events \
     -H "Content-Type: application/json" \
     -d '{"note": 60, "velocity": 100}'
```

**The Final Execution Chain:**
1. K8s NiFi receives JSON, flattens to `"60"`, pushes to Kafka.
2. Windows MiNiFi pulls `"60"` from Kafka and writes it to `C:\midi\inbox\flowfile.txt`.
3. Python Watchdog instantly detects the file, reads `"60"`, hits loopMIDI, and deletes the file.
4. Strudel hears the Note On over loopMIDI and plays the sound instantly.