# Issue #163 — Sparkplug B binary publisher (from Ch13), used to field-verify
# the MiNiFi Java edge-decode path. Publishes NBIRTH then NDATA every 5s to a
# port-forwarded Mosquitto (localhost:1883). The MiNiFi Java agent's
# ConsumeMQTTIIoT (spBv1.0/#) decodes these at the edge.
import time
import random
import paho.mqtt.client as mqtt
from pysparkplug import NBirth, NData, Metric, DataType, get_current_timestamp

BROKER = "localhost"
PORT = 1883
GROUP_ID = "MacLocalTest"
EDGE_NODE_ID = "Mac-Node-01"

TOPIC_NBIRTH = f"spBv1.0/{GROUP_ID}/NBIRTH/{EDGE_NODE_ID}"
TOPIC_NDATA = f"spBv1.0/{GROUP_ID}/NDATA/{EDGE_NODE_ID}"

client = mqtt.Client()
client.connect(BROKER, PORT, 60)
client.loop_start()

ts_birth = get_current_timestamp()
metrics_birth = (
    Metric(name="Temperature", datatype=DataType.FLOAT, value=22.0, timestamp=ts_birth),
    Metric(name="Humidity", datatype=DataType.FLOAT, value=50.0, timestamp=ts_birth),
)
client.publish(TOPIC_NBIRTH, NBirth(timestamp=ts_birth, seq=0, metrics=metrics_birth).encode(), qos=1)
print("Published NBIRTH")

seq = 1
try:
    while True:
        temp_val = round(random.uniform(20.0, 35.0), 2)
        humid_val = round(random.uniform(40.0, 60.0), 2)
        ts_data = get_current_timestamp()
        metrics_data = (
            Metric(name="Temperature", datatype=DataType.FLOAT, value=temp_val, timestamp=ts_data),
            Metric(name="Humidity", datatype=DataType.FLOAT, value=humid_val, timestamp=ts_data),
        )
        client.publish(TOPIC_NDATA, NData(timestamp=ts_data, seq=seq, metrics=metrics_data).encode(), qos=1)
        print(f"Sent Sparkplug NDATA (Seq: {seq}) -> Temp: {temp_val} | Humid: {humid_val}")
        seq = (seq + 1) % 256
        time.sleep(5)
except KeyboardInterrupt:
    client.loop_stop()
    client.disconnect()
