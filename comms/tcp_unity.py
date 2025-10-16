import paho.mqtt.client as mqtt
import ssl
import json
import time
import socket
from Crypto.Cipher import AES

# -------------------------------
# MQTT Broker (WSL Mosquitto)
# -------------------------------
BROKER_IP = "172.17.183.135"
BROKER_PORT = 8883
TOPIC_RAW = "robot/processed/data"

# TLS certs
TLS_CA = "D:/y4sem1/CG4002/certs/ca.crt"
TLS_CERT = "D:/y4sem1/CG4002/certs/fb2.crt"
TLS_KEY = "D:/y4sem1/CG4002/certs/fb2.key"

# -------------------------------
# FireBeetle TCP + XOR config
# -------------------------------
FIREBEETLE_IP = "172.20.10.10"
FIREBEETLE_PORT = 5000

# -------------------------------
# Unity TCP + AES config
# -------------------------------
UNITY_IP = "127.0.0.1"   # Unity runs on same laptop
UNITY_PORT = 6000

AES_KEY = b"1234567890abcdef"
AES_BLOCK_SIZE = 16

tcp_socket = None
unity_socket = None

XOR_KEY = bytes([0x55, 0xAA, 0x33, 0xCC, 0x0F, 0xF0, 0x99, 0x66,
                 0x12, 0x34, 0x56, 0x78, 0xAB, 0xCD, 0xEF, 0x01])


# -------------------------------
# TCP to FireBeetle
# -------------------------------
def connect_tcp():
    global tcp_socket
    if tcp_socket:
        tcp_socket.close()
        tcp_socket = None

    while tcp_socket is None:
        try:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.settimeout(10)
            tcp_socket.connect((FIREBEETLE_IP, FIREBEETLE_PORT))
            print("✅ Connected to FireBeetle")
        except Exception as e:
            print(f"❌ FireBeetle connection failed: {e}, retrying...")
            time.sleep(3)


def send_to_firebeetle(movement_class: int):
    global tcp_socket
    if tcp_socket is None:
        connect_tcp()

    try:
        plaintext = str(movement_class).encode('utf-8').ljust(16, b'\x00')
        encrypted = bytes([plaintext[i] ^ XOR_KEY[i] for i in range(16)])
        print(f"📤 Sending to FireBeetle: {movement_class}")
        tcp_socket.sendall(encrypted)

        try:
            ack = tcp_socket.recv(1024)
            print(f"📨 FireBeetle ACK: {ack.decode().strip()}")
        except socket.timeout:
            print("⏰ No ACK received")
    except Exception as e:
        print(f"❌ FireBeetle send error: {e}")
        tcp_socket = None


# -------------------------------
# TCP to Unity (AES)
# -------------------------------
def connect_unity():
    global unity_socket
    if unity_socket:
        unity_socket.close()
        unity_socket = None

    while unity_socket is None:
        try:
            unity_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            unity_socket.settimeout(10)
            unity_socket.connect((UNITY_IP, UNITY_PORT))
            print("✅ Connected to Unity")
        except Exception as e:
            print(f"❌ Unity connection failed: {e}, retrying...")
            time.sleep(3)


def send_to_unity(movement_class: int):
    global unity_socket
    if unity_socket is None:
        connect_unity()

    try:
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=b'\x00' * 16)
        plaintext = str(movement_class).encode('utf-8').ljust(16, b'\x00')
        encrypted = cipher.encrypt(plaintext)

        print(f"🎮 Sending to Unity: {movement_class}")
        unity_socket.sendall(encrypted)
    except Exception as e:
        print(f"❌ Unity send error: {e}")
        unity_socket = None


# -------------------------------
# MQTT Setup
# -------------------------------
client = mqtt.Client(client_id="laptop_bridge")
client.tls_set(TLS_CA, TLS_CERT, TLS_KEY, tls_version=ssl.PROTOCOL_TLSv1_2)
client.tls_insecure_set(True)


def on_connect(c, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to WSL broker")
        c.subscribe(TOPIC_RAW, qos=1)
        print(f"📡 Subscribed to Ultra96 topic: {TOPIC_RAW}")
    else:
        print(f"❌ MQTT connection failed with code {rc}")


def on_message(c, userdata, msg):
    try:
        payload_json = json.loads(msg.payload)
        movement_class = payload_json.get("movement_class")
        if movement_class is not None:
            print(f"\n🎯 Movement class from MQTT: {movement_class}")
            send_to_firebeetle(int(movement_class))
            send_to_unity(int(movement_class))
        else:
            print("⚠️ No 'movement_class' in payload")
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
    except Exception as e:
        print(f"❌ Error processing message: {e}")


def on_disconnect(c, userdata, rc):
    print(f"⚠️ Disconnected from WSL broker: {rc}")


# -------------------------------
# Main Loop
# -------------------------------
def main():
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    print("🚀 Laptop bridge starting...")
    connect_tcp()
    connect_unity()

    try:
        client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
        client.loop_start()
        print("✅ Bridge running. Press Ctrl+C to exit.")

        while True:
            time.sleep(1)
            if tcp_socket is None:
                connect_tcp()
            if unity_socket is None:
                connect_unity()

    except KeyboardInterrupt:
        print("\n🛑 Stopping bridge...")
    finally:
        client.loop_stop()
        client.disconnect()
        if tcp_socket:
            tcp_socket.close()
        if unity_socket:
            unity_socket.close()
        print("✅ Bridge stopped")


if __name__ == "__main__":
    main()
