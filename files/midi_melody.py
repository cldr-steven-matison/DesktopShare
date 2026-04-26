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