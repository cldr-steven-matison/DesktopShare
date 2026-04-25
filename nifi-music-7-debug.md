**Got the updated nifi-music.md plan.** PHASE 7 was missing the Strudel side, which is why no audible changes happened even though LoopMIDI shows 42 data and your test messages arrive. Strudel (browser WebMIDI) needs `midikeys()` to receive the exact MIDI note_on messages your watchdog already sends.

Here is the exact operational setup to confirm everything in order.

**1. Confirm Strudel can see the StrudelKafkaBus port (and therefore the 42 data events)**  
Open your Strudel REPL at http://localhost:4321/ (the one running from WSL2).  
Paste this exact block and hit Play:

```js
const kb = await midikeys('StrudelKafkaBus')
kb().s('sawtooth').room(0.5).delay(0.3).play()
```

If it connects, browser console (F12) will log MIDI devices and “Midi connected!”.  
If the port name is slightly different (common on Windows), try these one at a time:

```js
const kb = await midikeys('StrudelKafkaBus 1')
kb().s('sawtooth').room(0.5).delay(0.3).play()
```

or

```js
const kb = await midikeys('StrudelKafkaBus 0')
kb().s('sawtooth').room(0.5).delay(0.3).play()
```

**2. Confirm you are sending the right MIDI messages to LoopMIDI**  
Run this clean test sender in a new PowerShell window (bypasses watchdog/MiNiFi for instant verification):

```powershell
python -c "
import mido
from mido import Message
import time
port_name = 'StrudelKafkaBus'
print(mido.get_output_names())
with mido.open_output(port_name) as outport:
    for i in range(10):
        outport.send(Message('note_on', note=60, velocity=100))
        time.sleep(0.25)
        outport.send(Message('note_off', note=60, velocity=0))
        time.sleep(0.75)
print('Test notes sent')
"
```

It will first print all available output ports so you see the exact StrudelKafkaBus name, then fire 10 audible test notes (MIDI 60).

**3. Confirm audibly that new events sent to StrudelKafkaBus arrive**  
Keep the Strudel `midikeys` block above running in the REPL.  
Now trigger your real pipeline (or just run the test sender above again).  
Every note that hits LoopMIDI will instantly play as a sawtooth tone in Strudel.  
You will hear the change live.

Your existing watchdog.py already sends the exact same note_on/note_off messages, so once the midikeys code is in Strudel, Kafka → MiNiFi → watchdog → LoopMIDI will make sound immediately.

Drop the test sender or a real Kafka event and you’ll hear it. That’s the integration confirmed. Let me know when you hear the notes.