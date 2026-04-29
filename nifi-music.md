
***

# NiFi and Music (NiFi MiNiFi & MiDi)

**Live Musical Changes → K8s NiFi → Kafka → Nifi → MiNiFi C++ (PutFile) → Python Watchdog → loopMIDI → Strudel**

?? alternate:  remove kafka, use nifi -> invokeHttp -> MiNiFi or Site to Site ??

**Architecture Goal:**
Our Cloudera Streaming Operator infrastructure on WSL2 (minikube) handles the incoming midi, parses complex JSON. NiFi sends a flattened, simplified payload (e.g., the string `"60"`) to Kafka/MiNiFi. A MiNiFi C++ agent on the Windows host consumes the message and writes it to a local folder. A python watchdog instantly reads the files, strikes the MIDI note via loopMIDI, and deletes the file. Strudel running in the browser plays the result live.

---

## PHASE 0: Prerequisites

We split the tools between the Windows Host (Edge) and Kubernetes on WSL2 (Core) to demonstrate using Minifi & NiFi across environments.  In this case midi passes through our kubernetes cluster to the edge device's c++ agent which can take audible action using a music as code tool called Strudel.

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

**Inside WSL2:**  

```bash
git clone https://codeberg.org/uzu/strudel.git
cd strudel
pnpm install
pnpm dev

## get all of the strudel instal commands, including midi packages
```
→ Open your Windows web browser to `http://localhost:4321/`. Leave this running.

---

## PHASE 3: Core Infrastructure


This example integration was built with [Cloudera Streaming Operators](https://cldr-steven-matison.github.io/blog/Cloudera-Streaming-Operators/).

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

### InvokeHttp

Using the sample from [MiNiFi Kubernetes Playground](https://github.com/cldr-steven-matison/MiNiFi-Kubernetes-Playground) I was able to get InvokeHttp working to write notes to c:/midi/inbox.
```yaml
MiNiFi Config Version: 3
Flow Controller:
  name: MiNiFi Music Edge
Processors:
  - name: ListenForNotes
    id: 888e4567-e89b-12d3-a456-426614174001
    class: org.apache.nifi.minifi.processors.ListenHTTP
    scheduling strategy: TIMER_DRIVEN
    scheduling period: 0 sec
    Properties:
      Listening Port: 9998
      Listening IP: 0.0.0.0
      HTTP Rest URL: /midi
  - name: WriteToInbox
    id: 123e4567-e89b-12d3-a456-426614174002
    class: org.apache.nifi.minifi.processors.PutFile
    scheduling strategy: EVENT_DRIVEN
    Properties:
      Directory: C:\midi\inbox
      Conflict Resolution Strategy: replace
Connections:
  - name: HttpToDisk
    id: 999e4567-e89b-12d3-a456-426614174003
    source name: ListenForNotes
    destination name: WriteToInbox
    source relationship name: success
```

### Consume Kafka

Had issues getting a ConsumeKafka processor to work in MiNiFi

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

If minifi is running and the flow of data is still not working right,  this command helps show errors:

```wsl2
PS C:\Users\tunas> Get-Content "C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\logs\minifi-app.log" -Wait | Select-String "Kafka|Consumer|Broker"
```
---

## PHASE 7: Setup and Initial Testing of loopMIDI + Strudel MIDI (Windows Host)

**Critical:** Windows MIDI stack (especially on Windows 11 24H2/25H2+) can “forget” virtual ports after you delete/recreate them in loopMIDI. Always follow the exact order below. TotalData increasing in loopMIDI + your Python test script working but Strudel not seeing the port is the classic symptom — it is fixable with a MIDI service restart.

### Step-by-Step Setup

1. **Start loopMIDI FIRST (as Administrator recommended)**
   - Open **loopMIDI** from the Start menu (right-click → Run as administrator).
   - In “New port-name” box, type exactly: `StrudelKafkaBus`
   - Click **+**.
   - Leave the loopMIDI window open in the background (it must stay running).

2. **Restart the Windows MIDI Service (do this every time you recreate a port)**
   - Open Command Prompt **as Administrator** and run:
     ```
     net stop midisrv
     net start midisrv
     ```
   - Or open `services.msc`, find **Windows MIDI Service**, and Restart it.
   - This rebuilds the MIDI device list and makes the new port visible to browsers/WebMIDI.

3. **Verify the port exists (quick test)**
   - Open PowerShell and run your simple test script (save as `C:\midi\test-midi.py`):
     ```python
     import mido
     import time
     from mido import Message

     port_name = "StrudelKafkaBus"
     available = mido.get_output_names()
     actual = next((p for p in available if port_name in p), port_name)
     print(f"Available ports: {available}")
     print(f"Using: {actual}")

     with mido.open_output(actual) as outport:
         for note in [60, 64, 67, 72]:  # C4, E4, G4, C5
             print(f"→ Sending note {note}")
             outport.send(Message('note_on', note=note, velocity=100))
             time.sleep(0.5)
             outport.send(Message('note_off', note=note, velocity=0))
             time.sleep(0.3)
     ```
   - Run: `python C:\midi\test-midi.py`
   - You should see notes in the console **and** TotalData counter increasing in the loopMIDI window.

4. **Launch Strudel and Test MIDI Input**
   - Make sure your Strudel dev server is running (`pnpm dev` in the strudel folder).
   - Open **Chrome or Edge** (best WebMIDI support) and go to `http://localhost:4321/`.
   - The browser will prompt “Allow MIDI devices?” — click **Allow**.
   - In the Strudel REPL, paste and run this test code (replaces the incomplete example in PHASE 7):
     ```js
     // Listen for MIDI note input from our virtual bus
     const kb = await midikeys('StrudelKafkaBus')
     console.log('✅ MIDI input ready:', kb)  // check browser console (F12)

     // Simple test: play whatever notes arrive from Kafka/Python
     kb.note  // this turns incoming MIDI notes into a Strudel pattern
       .sound("sawtooth")  // or "piano", "gm_acoustic_bass", etc.
       .room(0.5)
       .out()
     ```
   - Now run your Python test script again (step 3). You should hear the notes playing live through Strudel’s browser audio **and** see activity in the Strudel console.


### Testing Audible End

Here is a Python script for the WSL2 side.  Yankee Doodle Script (yyd.py)

```python
Python
import os
import time
import uuid

# Path to your Windows inbox from WSL2
INBOX_PATH = "/mnt/c/midi/inbox/"

# (MIDI_Note, Duration)
# Melody: "Yankee Doodle went to town..."
yankee_doodle = [
    (72, 0.3), (72, 0.3), (74, 0.3), (76, 0.3), # Yan-kee Doo-dle
    (72, 0.3), (76, 0.3), (74, 0.6),            # went to town
    (72, 0.3), (72, 0.3), (74, 0.3), (76, 0.3), # rid-ing on a
    (72, 0.6), (71, 0.6),                       # po-ny
    (72, 0.3), (72, 0.3), (74, 0.3), (76, 0.3), # stuck a feath-er
    (77, 0.3), (76, 0.3), (74, 0.3), (72, 0.3), # in his cap and
    (71, 0.3), (67, 0.3), (69, 0.3), (71, 0.3), # called it mac-a-
    (72, 0.6), (72, 0.6)                        # ro-ni
]

def send_note_file(note_val):
    unique_id = uuid.uuid4().hex[:6]
    filepath = os.path.join(INBOX_PATH, f"note_{unique_id}.txt")
    try:
        with open(filepath, "w") as f:
            f.write(str(note_val))
    except Exception as e:
        print(f"File system lag: {e}")

def play_yankee():
    print(f"🏇 Riding the KafkaBus to {INBOX_PATH}...")
    for note, duration in yankee_doodle:
        send_note_file(note)
        # We wait slightly less than the duration to keep the rhythm tight
        time.sleep(duration)

if __name__ == "__main__":
    if os.path.exists(INBOX_PATH):
        play_yankee()
        print("Stuck a feather in his cap!")
    else:
        print("Check your mount! /mnt/c/midi/inbox/ is missing.")
```

Create and Run.  This is our expected result of Yankee Doodle Dandy.

---

## PHASE 8: Strudel Code (Live Reaction)

In the Strudel REPL (`localhost:4321`), paste the following and hit **Play**:

```js
// This creates a pattern that listens to your loopMIDI port
// The 'await' is crucial because it handshakes with the WebMIDI API
const kb = await midikeys('StrudelKafkaBus')

// This iterates through every incoming MIDI note and plays a synth
kb().s('sawtooth').room(0.5).gain(0.8)
```

**The Final Execution Chain:**
1. K8s NiFi receives JSON, flattens to `"60"`, pushes to Kafka.
2. Windows MiNiFi pulls `"60"` from Kafka and writes it to `C:\midi\inbox\flowfile.txt`.
3. Python Watchdog instantly detects the file, reads `"60"`, hits loopMIDI, and deletes the file.
4. Strudel hears the Note On over loopMIDI and plays the sound instantly.

---

## PHASE 9: End to End Integration Test 

From either WSL2 or Windows PowerShell, simulate your upstream producer by sending a test payload to your K8s NiFi instance:

```bash
curl -X POST http://localhost:9999/musical-events \
     -H "Content-Type: application/json" \
     -d '{"note": 60, "velocity": 100}'
```

You should hear a single note from Strudel.  Try a few different notes and confirm they play in Strudel.


## PHASE 10:  End to End Yankee Doodle Dandy

In this section we are going to stream the Yankee Doodle Dandy midi through Nifi to Strudel.

[ add integration example content ]




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

4.  MiNiFi 
```powershelladmin
cd 'C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\bin'
 .\minifi.exe
```

5. Send Test Notes
```powershell
curl.exe -X POST http://localhost:9999/musical-events -H "Content-Type: application/json" -d "{\""note\"": 60}"
```
```powershell
curl.exe -X POST http://localhost:9998/midi -H "Content-Type: application/json" -d "60"

PS C:\Users\tunas> Invoke-RestMethod -Uri "http://localhost:9998/contentListener" -Method Post -Body "64" -ContentType "text/plain"

```


6. MiDi Watchdog Notes to StrudelKafkaBus
```powershell
python C:\midi\watchdog.py
```

7. LoopMIDI 

[ screen shot ]

8. Strudel 
```wsl2
pnpm dev
```

## Common Issues & Fixes (Troubleshooting Guide)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Port not listed in Strudel (even though Python sees it) | MIDI service stale after port recreation | Restart `midisrv` (step 2), recreate port in loopMIDI, refresh browser page (hard refresh Ctrl+Shift+R) |
| TotalData increases but no sound in Strudel | Name mismatch or WebMIDI permission | Use exact name shown in loopMIDI (sometimes has " 1" suffix). Re-allow MIDI in browser. |
| Strudel never prompts for MIDI | Browser not Chrome/Edge or page not reloaded after service restart | Switch browser or restart Strudel server + page |
| Persistent problems after multiple recreations | Windows MIDI driver cache | Reinstall loopMIDI as Administrator + reboot, or try alternative virtual MIDI tools |
| No ports visible at all | Hidden/old MIDI devices conflicting | Device Manager → View → Show hidden devices → delete any greyed-out MIDI entries → restart MIDI service |

**Pro tip:** Install free **MIDI-OX** (or loopMIDI’s built-in monitor) to watch raw MIDI traffic on `StrudelKafkaBus` — great for confirming data is flowing before Strudel even starts.

This section gives you a reliable, repeatable test harness before you wire up the full NiFi → Kafka → MiNiFi pipeline. Once this works reliably, the rest of your architecture should light up perfectly.



## History

```bash
curl.exe -X POST http://localhost:9999/musical-events -H "Content-Type: application/json" -d "{\""note\"": 60}"
Get-Content "C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\logs\minifi-app.log" -Tail 300
Get-Content "C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\logs\minifi-app.log" -Tail 150
dir "C:\midi\inbox"

# when testing minifi port
kubectl port-forward -n cfm-streaming pod/mynifi-0 9998:9998
```

### MiNiFi Terminal History

```powershelladmin
Stop-Service -Name "Apache NiFi MiNiFi" -Force -ErrorAction SilentlyContinue
Stop-Service -Name "MiNiFi" -ErrorAction SilentlyContinue
.\minifi.exe

[2026-04-25 11:41:39.005] [main] [info] Found MINIFI_HOME=C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp in environment
[2026-04-25 11:41:39.006] [main] [info] MiNiFi Locations=
Working dir:             C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp
Lock path:               C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\LOCK
Log properties path:     C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\conf\minifi-log.properties
UID properties path:     C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\conf\minifi-uid.properties
Properties path:         C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\conf\minifi.properties
Logs dir:                C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\logs
Fips binary path:        C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\fips
Fips conf path:          C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\fips
[2026-04-25 11:41:39.006] [org::apache::nifi::minifi::Properties] [info] Using configuration file to load configuration for Logger properties from C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\conf\minifi-log.properties (located at C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp\conf\minifi-log.properties)
%4|1777131699.193|CONFWARN|123e4567-e89b-12d3-a456-426614174001#consumer-1| [thrd:app]:Configuration property `sasl.mechanism` set to `GSSAPI` but `security.protocol` is not configured for SASL: recommend setting `security.protocol` to SASL_SSL or SASL_PLAINTEXT
```


## Resources

- [Strudel Docs](https://strudel.cc/learn/getting-started/)
- [LoopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html).
- [Cloudera Streaming Operators](https://cldr-steven-matison.github.io/blog/Cloudera-Streaming-Operators/)
- [My Github](https://github.com/cldr-steven-matison/)

## Scripts

Used this to test,  need to get the strudel snippet that works best with this midi stream

```python
import time
import rtmidi
from rtmidi.midiconstants import NOTE_ON, NOTE_OFF

PORT_NAME = "StrudelKafkaBus"
CHANNEL = 1
VELOCITY = 95

midiout = rtmidi.MidiOut()
available_ports = midiout.get_ports()

port_opened = False
for i, port in enumerate(available_ports):
    if PORT_NAME.lower() in port.lower():
        midiout.open_port(i)
        print(f"âœ… Connected to: {port}")
        port_opened = True
        break

if not port_opened:
    midiout.open_virtual_port(PORT_NAME)
    print(f"âœ… Created virtual port: {PORT_NAME}")

# Melody: (note, duration) â€” I slowed it down a bit and added a tiny gap
melody = [
    (72, 0.35), (72, 0.35), (74, 0.35), (76, 0.35),
    (72, 0.35), (76, 0.35), (74, 0.55),
    (72, 0.35), (72, 0.35), (74, 0.35), (76, 0.35),
    (72, 0.55), (71, 0.55)
]

def play_note(note, duration, velocity=VELOCITY):
    note_on = [NOTE_ON | (CHANNEL - 1), note, velocity]
    note_off = [NOTE_OFF | (CHANNEL - 1), note, 0]

    midiout.send_message(note_on)
    time.sleep(duration)      # this is how long the note is "held"
    midiout.send_message(note_off)

    time.sleep(0.08)          # â† small gap after note-off so notes don't bleed into each other

print("ðŸŽ¹ Playing slower, cleaner melody...")

try:
    while True:
        for note, dur in melody:
            play_note(note, dur)
        print("â†º Looping...")
except KeyboardInterrupt:
    print("\nðŸ›‘ Stopped.")
finally:
    del midiout
```

## Reset MiNiFi

Run these commands in PowerShell:

```powershell
# 1. Stop MiNiFi (if it isn't already)
# (Ctrl+C in the minifi window)

# 2. Navigate to the MiNiFi directory
cd "C:\Program Files\ApacheNiFiMiNiFi\nifi-minifi-cpp"

# 3. Wipe the persistent flow data
Remove-Item -Path ".\flowfile_repository\*" -Recurse -Force
Remove-Item -Path ".\content_repository\*" -Recurse -Force
Remove-Item -Path ".\provenance_repository\*" -Recurse -Force

# 4. Restart MiNiFi
.\bin\minifi.exe
```

## Strudel Piano + Beat

This strudel code is working very well with default flow of midi as piano.

```strudel
hush()

const kb = await midikeys('StrudelKafkaBus')

stack(
  // PIANO WITH LONG SUSTAIN
  kb()
    .s('piano')
    .n(note)
    // .sustain(2) keeps the sample playing longer before the fade starts
    .sustain(2) 
    // .release(3) creates a very long, smooth fade out (the "decay" feel)
    .release(3) 
    .room(0.8)
    .gain(0.7),

  s("bd [~ sd] bd sd").gain(0.8),
  s("hh:27*8").gain(0.4)
)

```

## NiFi Mount for testing PutFile ListFile 

This works to mount /home/tuna/midi_inbox to /mnt/midi_inbox on the nifi pod.

```terminal

minikube mount /home/tuna/midi_inbox:/home/tuna/midi_inbox
kubectl apply -f nifi-cluster-30-nifi2x-midi.yaml -n cfm-streaming

```