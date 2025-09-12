#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import ssl
import time
import json

# MQTT settings (through SSH tunnel)
BROKER_HOST = "localhost"  # SSH tunnel forward
BROKER_PORT = 8888         # Local port forwarded to Ultra96's 8889
TLS_CA = "./certs/ca.crt"           # Adjust paths to your certificates
TLS_CERT = "./certs/client.crt"
TLS_KEY = "./certs/client.key"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✓ Connected to Ultra96 MQTT broker successfully!")
        client.subscribe("test/topic")
        client.subscribe("status/#")
    else:
        print(f"❌ Connection failed with result code: {rc}")

def on_message(client, userdata, msg):
    print(f"📨 Received: {msg.topic} -> {msg.payload.decode()}")

def on_publish(client, userdata, mid):
    print(f"✓ Message published (MID: {mid})")

def on_subscribe(client, userdata, mid, granted_qos):
    print(f"✓ Subscribed successfully (MID: {mid})")

def main():
    print("🔌 Connecting to Ultra96 via TLS MQTT...")
    
    client = mqtt.Client("Laptop_Client")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_publish = on_publish
    client.on_subscribe = on_subscribe

    # Setup TLS
    try:
        client.tls_set(
            ca_certs=TLS_CA,
            certfile=TLS_CERT,
            keyfile=TLS_KEY,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS
        )
        print("✓ TLS configured successfully")
    except Exception as e:
        print(f"❌ TLS setup failed: {e}")
        return

    # Connect through SSH tunnel
    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        print(f"✓ Connecting to {BROKER_HOST}:{BROKER_PORT}")
    except Exception as e:
        print(f"❌ MQTT connection failed: {e}")
        print("Make sure SSH tunnel is running: ssh -L 8888:localhost:8889 xilinx@makerslab-fpga-53.ddns.comp.nus.edu.sg")
        return

    # Start the loop
    client.loop_start()
    
    try:
        message_count = 0
        while True:
            # Send test messages every 3 seconds
            message = {
                "from": "laptop",
                "message": f"Hello Ultra96! Message #{message_count}",
                "timestamp": time.time()
            }
            
            client.publish("test/topic", json.dumps(message))
            message_count += 1
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n🛑 Disconnecting client...")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
