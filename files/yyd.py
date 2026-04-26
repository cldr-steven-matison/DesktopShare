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