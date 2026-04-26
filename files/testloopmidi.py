import mido
from mido import Message
import time

# Use a partial match to find the port
target_name = 'StrudelKafkaBus'
all_ports = mido.get_output_names()
print(f"Available ports: {all_ports}")

# Find the full name string that contains our target
port_name = next((p for p in all_ports if target_name in p), None)

if port_name:
    print(f"Opening port: {port_name}")
    try:
        with mido.open_output(port_name) as outport:
            for i in range(10):
                print(f"Sending note {i+1}/10")
                outport.send(Message('note_on', note=60, velocity=100))
                time.sleep(0.25)
                outport.send(Message('note_off', note=60, velocity=0))
                time.sleep(0.75)
        print('Test notes sent successfully.')
    except Exception as e:
        print(f"Failed to open or send: {e}")
else:
    print(f"Error: Could not find a port containing '{target_name}'")