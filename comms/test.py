import paho.mqtt.client as mqtt
import ssl
import json
import time
import random

# -------------------------------
# MQTT Broker (Laptop Mosquitto)
# -------------------------------
BROKER_IP = "172.17.183.135"       # Replace with your laptop LAN IP
BROKER_PORT = 8883
TOPIC_RAW = "robot/processed/data"  # Same as in the bridge

# TLS certs
TLS_CA = "/mnt/d/y4sem1/CG4002/certs/ca.crt"
TLS_CERT = "/mnt/d/y4sem1/CG4002/certs/laptop.crt"
TLS_KEY = "/mnt/d/y4sem1/CG4002/certs/laptop.key"

# -------------------------------
# MQTT Client
# -------------------------------
client = mqtt.Client(client_id="dummy_publisher")

client.tls_set(
    ca_certs=TLS_CA,
    certfile=TLS_CERT,
    keyfile=TLS_KEY,
    tls_version=ssl.PROTOCOL_TLSv1_2
)
client.tls_insecure_set(True)  # only if using self-signed certs

def on_connect(c, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to broker")
    else:
        print(f"❌ Connection failed with code {rc}")

def on_disconnect(c, userdata, rc):
    print(f"⚠️ Disconnected with code {rc}")

client.on_connect = on_connect
client.on_disconnect = on_disconnect

# -------------------------------
# Main
# -------------------------------
client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
client.loop_start()

print("🚀 Dummy publisher running. Press Ctrl+C to stop.")

try:
    while True:
        # Create fake payload
        payload = {
            "movement_class": random.randint(0, 3),  # simulate 4 possible movement classes
            "timestamp": time.time()
        }
        msg = json.dumps(payload)
        client.publish(TOPIC_RAW, msg, qos=1)
        print(f"📤 Published: {msg}")
        time.sleep(2)
except KeyboardInterrupt:
    print("\n🛑 Stopping publisher...")
finally:
    client.loop_stop()
    client.disconnect()
    print("✅ Publisher stopped")

