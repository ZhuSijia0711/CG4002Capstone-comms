import paho.mqtt.client as mqtt
import ssl
import json

# Broker config
MQTT_BROKER = "172.17.183.135"
MQTT_PORT = 8883

# Topics
TOPIC_SENSOR = "robot/sensor/to_ultra96"
TOPIC_AI = "robot/processed/data"

# TLS certs
TLS_CA = "/mnt/d/y4sem1/CG4002/certs/ca.crt"
TLS_CERT = "/mnt/d/y4sem1/CG4002/certs/laptop.crt"
TLS_KEY = "/mnt/d/y4sem1/CG4002/certs/laptop.key"


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to broker")
        client.subscribe([(TOPIC_SENSOR, 1), (TOPIC_AI, 1)])
        print(f"📡 Subscribed to: {TOPIC_SENSOR} and {TOPIC_AI}")
    else:
        print(f"❌ Connection failed with code {rc}")


def on_message(client, userdata, msg):
    if msg.topic == TOPIC_SENSOR:
        payload = msg.payload
        print(f"\n📥 Raw sensor data received ({len(payload)} bytes)")
        print(f"   Hex preview: {payload[:24].hex()} ...")
    elif msg.topic == TOPIC_AI:
        try:
            payload_json = json.loads(msg.payload)
            print(f"\n🤖 AI result received: {payload_json}")
        except Exception as e:
            print(f"❌ Failed to parse AI JSON: {e}")


def main():
    client = mqtt.Client(client_id="laptop_subscriber_full")
    client.tls_set(TLS_CA, TLS_CERT, TLS_KEY, tls_version=ssl.PROTOCOL_TLSv1_2)
    client.tls_insecure_set(True)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"🔑 Connecting to {MQTT_BROKER}:{MQTT_PORT} with TLS...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()

