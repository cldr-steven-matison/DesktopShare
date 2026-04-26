import time
import requests # Used for the MiNiFi pipeline

# Use your MiNiFi endpoint for the pipeline test
MINIFI_URL = "http://localhost:9998/contentListener"

# Melody: (note, duration) 
# Use 'None' for a rest/pause
melody = [
    (72, 0.3), (72, 0.3), (74, 0.3), (76, 0.3), # Yan-kee Doo-dle
    (72, 0.3), (76, 0.3), (74, 0.6),           # went to town
    (None, 0.2),                               # <--- Short Pause
    (72, 0.3), (72, 0.3), (74, 0.3), (76, 0.3), # Rid-ing on a
    (72, 0.5), (71, 0.5),                      # po-ny
    (None, 0.8)                                # <--- Long Pause before loop
]

def send_to_pipeline(note, duration):
    if note is None:
        print(f"⏸️  Resting for {duration}s...")
        time.sleep(duration)
    else:
        print(f"🎵 Sending Note: {note}")
        try:
            # Send note to MiNiFi InvokeHttp listener
            requests.post(MINIFI_URL, data=str(note), headers={"Content-Type": "text/plain"})
        except Exception as e:
            print(f"❌ Connection Error: {e}")
        
        # This sleep determines the rhythm of the sequence arriving at MiNiFi
        time.sleep(duration)

print("🎹 Playing melody through the MiNiFi Pipeline...")

try:
    while True:
        for note, dur in melody:
            send_to_pipeline(note, dur)
        print("🔄 Looping...")
except KeyboardInterrupt:
    print("\n🛑 Stopped.")