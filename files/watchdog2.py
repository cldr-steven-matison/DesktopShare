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
                with open(filepath, 'r') as f:
                    content = f.read().strip()
                
                if content.isdigit():
                    note = int(content)
                    # The cool output you wanted back
                    print(f"🎵 Playing Note: {note}") 
                    
                    # Fire the note immediately
                    outport.send(Message('note_on', note=note, velocity=100))
                    
                    # Minimal hold (0.05s) prevents lag while ensuring the synth triggers
                    time.sleep(0.05) 
                    outport.send(Message('note_off', note=note, velocity=0))
                
                os.remove(filepath)
            except Exception:
                # Catching locks from MiNiFi writes
                pass
        # High-speed polling so we don't miss the next note in the sequence
        time.sleep(0.01)