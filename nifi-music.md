
***

# NiFi and Music (WSL2 + MiNiFi File Drop Architecture)

**Live Musical Changes → K8s NiFi → Kafka → Nifi → MiNiFi C++ (PutFile) → Python Watchdog → loopMIDI → Strudel**

**Architecture Goal:**
Centralized infrastructure on WSL2 handles the heavy lifting (routing, parsing complex JSON). It sends a flattened, simplified payload (e.g., the string `"60"`) to Kafka. A lightweight MiNiFi C++ agent on the Windows host consumes the message and writes it to a local folder. A lightweight Python watchdog instantly reads the file, strikes the MIDI note via loopMIDI, and deletes the file. Strudel plays the result live.

---

## PHASE 0: Prerequisites (Split Environment)

We split the tools between the Windows Host (Edge) and WSL2 (Core) to demonstrate using Minifi & NiFi across environments.  In this case from kubernetes cluster with no access to the edge device with midi and audio.

**1. On the Windows Host (Edge):**
* **Python 3.11+**: `winget install Python.Python.3.11`
* **Python Packages**: Open PowerShell and run: `python -m pip install mido python-rtmidi`
* **loopMIDI**: Download and install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html).
* **MiNiFi C++**: Download the Windows MiNiFi C++ from the Apache NiFi site and install as ApacheMiNiFi.

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

**Inside WSL2:**  ?? Redo this for install on windows??  NO, windows c++ install is more of a nitemare than strudel itself... stay in linux to break dependecy hells
```bash
git clone https://codeberg.org/uzu/strudel.git
cd strudel
pnpm install
pnpm dev
```
→ Open your Windows web browser to `http://localhost:4321/`. Leave this running.

---

## PHASE 3: Core Infrastructure (Minikube / Cloudera Streaming)

Link to blog doc for CSO.

---

## PHASE 4: Core NiFi Flow

Open your K8s NiFi UI. This flow strips complex upstream JSON into a dead-simple string for the edge.

1. **ListenHTTP**
   * Listening Port: `999`
   * Path: `/musical-events`
2. **EvaluateJsonPath**
   * Destination: `flowfile-content` (Replaces the entire FlowFile payload with the JSON path result).
   * Add dynamic property: `midi.note` -> `$.note`
   * *Result: If the incoming payload is `{"note": 60}`, the FlowFile content is now strictly `"60"`.*
3. **PublishKafka**
   * Kafka Brokers: `my-cluster-kafka-bootstrap.cld-streaming.svc:9092`
   * Topic Name: `musical_changes`
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

Edit as administrator `C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\conf\conf.yml`:

```yaml
MiNiFi Config Version: 3
Flow Controller:
  name: MiNiFi Music Edge
  id: 123e4567-e89b-12d3-a456-426614174000
Processors:
  - name: GetKafka
    id: 123e4567-e89b-12d3-a456-426614174001
    class: org.apache.nifi.minifi.processors.ConsumeKafka
    scheduling strategy: TIMER_DRIVEN
    scheduling period: 5 sec
    Properties:
      Kafka Brokers: 127.0.0.1:9092
      Topic Names: musical_changes
      Group ID: minifi-music-group-new
      Security Protocol: plaintext
      Offset Reset: earliest
      auto.offset.reset: earliest
  - name: LogAttributes
    id: 123e4567-e89b-12d3-a456-426614174004
    class: org.apache.nifi.minifi.processors.LogAttribute
    scheduling strategy: EVENT_DRIVEN
  - name: WriteToInbox
    id: 123e4567-e89b-12d3-a456-426614174002
    class: org.apache.nifi.minifi.processors.PutFile
    scheduling strategy: EVENT_DRIVEN
    Properties:
      Directory: C:\\midi\\inbox
      Conflict Resolution Strategy: replace
Connections:
  - name: KafkaToLog
    id: 123e4567-e89b-12d3-a456-426614174005
    source name: GetKafka
    destination name: LogAttributes
    source relationship name: success
  - name: LogToDisk
    id: 123e4567-e89b-12d3-a456-426614174006
    source name: LogAttributes
    destination name: WriteToInbox
    source relationship name: success

```

Run MiNiFi in a new PowerShell window:
```powershell
cd "C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\bin"
.\minifi.exe
```

---

## PHASE 7: Strudel Code (Live Reaction)

In the Strudel REPL (`localhost:4321`), paste the following and hit **Play**:

```js
// This creates a pattern that listens to your loopMIDI port
// The 'await' is crucial because it handshakes with the WebMIDI API
const kb = await midikeys('StrudelKafkaBus')

// This iterates through every incoming MIDI note and plays a synth
kb().s('sawtooth').room(0.5).gain(0.8)
```

Make sure to send new data,  1 new note should trigger a play

---

## PHASE 8: Integration Test 

From either WSL2 or Windows PowerShell, simulate your upstream producer by sending a test payload to your K8s NiFi instance:

```bash
curl -X POST http://localhost:9999/musical-events \
     -H "Content-Type: application/json" \
     -d '{"note": 60, "velocity": 100}'
```

**The Final Execution Chain:**
1. K8s NiFi receives JSON, flattens to `"60"`, pushes to Kafka.
2. Windows MiNiFi pulls `"60"` from Kafka and writes it to `C:\midi\inbox\flowfile.txt`.
3. Python Watchdog instantly detects the file, reads `"60"`, hits loopMIDI, and deletes the file.
4. Strudel hears the Note On over loopMIDI and plays the sound instantly.


## Terminal Map

1. The NiFi Flow
```wsl2
minikube tunnel
```
2. WSL2 to Localhost kafka
```wsl2
kubectl port-forward -n cld-streaming my-cluster-combined-2 9092:9092
```
3. Inbound NiFi Port for Upstream Notes
```wsl2
kubectl port-forward -n cfm-streaming pod/mynifi-0 9999:9999
```

4.  MiniFi 
```powershell
PS C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\bin> .\minifi.exe
```

5. Send a Test Note to NiFi
```powershell
curl.exe -X POST http://localhost:9999/musical-events -H "Content-Type: application/json" -d "{\""note\"": 60}"
```



X. MiDi Watchdog Notes to StrudelKafkaBus
```powershell
PS C:\Users\tunas> python C:\midi\watchdog.py
```
x. LoopMIDI ?? never got this far Total data was always 0

[ screen shot ]

X. Strudel ?? should this be on PS not WSL2?  
```wsl2
tunas@MINI-Gaming-G1:~/strudel$ pnpm dev
```





## History

```bash

   1 curl.exe -X POST http://localhost:9999/musical-events -H "Content-Type: application/json" -d "{\""note\"": 60}"

   6 cd c:\midi\inbox

  17 curl.exe -X POST http://localhost:9999/musical-events -H "Content-Type: application/json" -d "{\""note\"": 60}"
  18 Get-Content "C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\logs\minifi-app.log" -Tail 300
  29 Get-Content "C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\logs\minifi-app.log" -Tail 150
  30 dir "C:\midi\inbox"
  31 ls


```

### MiNiFi Terminal History

```powershelladmin


  55 Stop-Service -Name "Apache NiFi MiNiFi" -Force -ErrorAction SilentlyContinue
  56 Stop-Service -Name "MiNiFi" -ErrorAction SilentlyContinue
  57 .\minifi.exe
 
  
```