**Alternative Virtual MIDI Tools (for Windows + Strudel WebMIDI)**

Your current setup uses **loopMIDI** (by Tobias Erichsen), which is still popular and lightweight. However, as of early 2026, Windows MIDI Services (a major OS-level update) has introduced **native built-in loopback/virtual MIDI ports**. This has changed the landscape—many third-party tools like loopMIDI and LoopBe now have occasional compatibility quirks with the new stack (dynamic ports sometimes not visible until after a service restart or specific naming tricks). The native option is often more stable for browser/WebMIDI use cases like Strudel.

Here’s a concise comparison of the best current options (as of April 2026):

| Tool | Type | Key Pros | Key Cons | Best For Your Use Case? | Download / Info |
|------|------|----------|----------|-------------------------|-----------------|
| **Windows MIDI Services Native Loopback** | Built-in (no extra install) | Zero latency, fully multi-client, MIDI 2.0 ready, rock-solid stability with WebMIDI/Chrome/Edge, no third-party driver issues | Requires Windows 11 + recent update; setup is slightly different (create ports via MIDI Settings app) | **Strongly recommended first** — try this before anything else. Solves the exact “port disappears after recreate” problem you hit. | Built into Windows → search “MIDI Settings” or check Microsoft’s Windows Music Dev blog for the quick-start guide. |
| **LoopBe1** (free version) / LoopBe30 (paid) | Free/paid kernel driver | Extremely low latency, simple “invisible cable”, proven with many apps, still works on Win11 | Free version limited to 1 port; some users report muting/overload on very high traffic | Great lightweight alternative if native doesn’t suit you. Often more reliable than loopMIDI in older reports. | https://www.nerds.de/en/loopbe1.html |
| **loopMIDI** (your current tool) | Free | Unlimited named ports, very easy GUI, lightweight | Compatibility hiccups with 2026 Windows MIDI Services (ports may not show until service restart or renaming) | Still viable with the midisrv restart workaround you already know. | https://www.tobias-erichsen.de/software/loopmidi.html |
| **Bome MIDI Translator Pro** | Paid (with trial) | Acts as virtual ports **plus** powerful MIDI translation/routing/filtering | Paid; overkill if you only need a simple pipe | If you ever want to add logic (e.g., filter or remap notes before Strudel). | https://www.bome.com/products/miditranslator |
| **MIDI-OX** | Free monitoring + mapping tool | Excellent for debugging traffic; can also map ports | Not a pure virtual cable by itself (pair with one of the above) | Debugging companion tool (highly recommended regardless). | http://www.midiox.com/ |

**Quick recommendation for your MIDIFI demo**:  
Start with the **native Windows MIDI Services loopback ports** (create a port named `StrudelKafkaBus` directly in the MIDI Settings app). It eliminates most of the recreation headaches you saw. If you still prefer a simple third-party tool, switch to **LoopBe1**—it’s frequently praised for stability with WebMIDI apps. After creating the port, always restart the `midisrv` service as you already do.

**Upstream Tools to Trigger MIDI Events into the MIDIFI Demo (before NiFi)**

Your current architecture is: [Data source] → NiFi (on K8s) → Kafka → MiNiFi (edge) → Python watchdog → virtual MIDI → Strudel.  

“Upstream of NiFi” means any tool or system that **generates or forwards real-time events** that NiFi can easily ingest (via its built-in processors like `GetMQTT`, `ListenHTTP`, `ConsumeKafka`, `GetFile`, etc.). These events become the “notes” or triggers in your sonification pipeline.

Here are the most practical categories and specific tools (focused on real-time, low-code, and easy integration with NiFi/Kafka):

1. **IoT / Sensor Data (most common for live “data music” demos)**  
   - **MQTT brokers** (lightweight pub/sub perfect for sensors): EMQX, HiveMQ, or Mosquitto. Devices/sensors publish temperature, stock ticks, button presses, etc. → NiFi’s `GetMQTT` or `ConsumeMQTT` processor picks them up instantly.  
     - Links: EMQX Cloud (managed) → https://www.emqx.com/; HiveMQ → https://www.hivemq.com/  
   - **Node-RED**: Visual low-code flow tool. Great for wiring sensors, APIs, or webhooks → MQTT/Kafka. You can prototype an entire upstream trigger in minutes.  
     - Link: https://nodered.org/ (runs on Raspberry Pi, Windows, or in a container).

2. **API / Webhook Triggers (real-world data like stocks, weather, social)**  
   - **Custom lightweight producers** (Python/Node.js scripts or Zapier/Make.com) that poll APIs and push JSON events to Kafka or MQTT.  
   - **Kafka Connect** with source connectors (if you want NiFi to sit after Kafka, but you can also have NiFi consume directly).  
   - NiFi itself has processors for HTTP polling (`InvokeHTTP`), Twitter (deprecated but alternatives exist), etc.

3. **Industrial / Enterprise Data**  
   - **OPC-UA** or **Modbus** servers (for factory sensors) → NiFi has native processors.  
   - **SCADA / PI Historian** systems (common in your CSO world).

4. **Sonification-Specific Data Generators (for testing/demoing MIDI directly)**  
   - Tools that turn CSV/spreadsheets/websites into MIDI patterns (you could run these upstream and pipe output into NiFi via file or HTTP). Examples:  
     - csv-to-midi (web app) → https://csv-to-midi.evanking.io/  
     - Highcharts Sonification Studio (web-based) → https://sonification.highcharts.com/  
     - Data Sonifyer → https://studio.datasonifyer.de/  
   These are more “data → MIDI” than pure upstream, but you could use their output as a test feed into NiFi.

**Suggested quick wins for your demo**:
- Add a **Node-RED** flow that reads a simple sensor (or even a fake timer/stock API) and publishes to MQTT → NiFi consumes it → the rest of your pipeline turns it into notes. Super visual and fast to prototype.
- Or just use a Python script as a Kafka producer (you already have Python in the edge layer) sending test events upstream.

This gives you tons of flexibility—real sensors for live demos, or simulated data for development. Let me know if you want a sample Node-RED flow, a Python upstream producer script, or help updating your .md with any of this! Your MIDIFI project is shaping up to be really cool. 🎛️