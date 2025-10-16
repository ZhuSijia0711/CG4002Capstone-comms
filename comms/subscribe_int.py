import paho.mqtt.client as mqtt
import ssl
import json
import time

# -------------------------------
# MQTT Broker (Laptop Mosquitto)
# -------------------------------
BROKER_IP = "172.17.183.135"      # <--- replace with your laptop LAN IP
BROKER_PORT = 8883
TOPIC_RAW = "robot/processed/data"     # Ultra96 publishes JSON here
TOPIC_CLASS = "robot/movement/class"  # Bridge republishes integer here

# TLS certs (for the laptop broker)
TLS_CA = "/mnt/d/y4sem1/CG4002/certs/ca.crt"
TLS_CERT = "/mnt/d/y4sem1/CG4002/certs/laptop.crt"
TLS_KEY = "/mnt/d/y4sem1/CG4002/certs/laptop.key"

# -------------------------------
# MQTT Client
# -------------------------------
client = mqtt.Client(client_id="laptop_bridge")

# TLS setup
client.tls_set(TLS_CA, TLS_CERT, TLS_KEY, tls_version=ssl.PROTOCOL_TLSv1_2)
client.tls_insecure_set(True)  # Only for self-signed certs

# -------------------------------
# Callback functions
# -------------------------------
def on_connect(c, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to broker")
        c.subscribe(TOPIC_RAW, qos=1)
        print(f"📡 Subscribed to Ultra96 topic: {TOPIC_RAW}")
    else:
        print(f"❌ Connection failed with code {rc}")

def on_message(c, userdata, msg):
    try:
        payload_json = json.loads(msg.payload)
        movement_class = payload_json.get("movement_class")

        if movement_class is not None:
            print(f"🤖 Movement class received: {movement_class}")

            # Republish integer to local clients
            c.publish(TOPIC_CLASS, movement_class, qos=1)
            print(f"📡 Forwarded to local clients: {TOPIC_CLASS} -> {movement_class}")
        else:
            print("⚠️  No movement_class in payload")
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}")

def on_disconnect(c, userdata, rc):
    print(f"⚠️  Disconnected from broker: {rc}")
    # Optionally, you can try reconnecting here

# -------------------------------
# Main loop
# -------------------------------
def main():
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Connect to laptop Mosquitto broker
    client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
    client.loop_start()

    print("🚀 Laptop bridge running. Press Ctrl+C to exit.")

    try:
        while True:
            time.sleep(1)  # Keep alive
    except KeyboardInterrupt:
        print("\n🛑 Stopping bridge...")
    finally:
        client.loop_stop()
        client.disconnect()
        print("✅ Bridge stopped")

if __name__ == "__main__":
    main()

