import paho.mqtt.client as mqtt
import ssl
import json
import time
import socket
from Crypto.Cipher import AES
from threading import Thread, Lock
import queue

# -------------------------------
# MQTT Broker (WSL Mosquitto)
# -------------------------------
BROKER_IP = "172.17.183.135"
BROKER_PORT = 8883
TOPIC_RAW = "ultra96/processed/to_firebeetle"

# TLS certs
TLS_CA = "D:/y4sem1/CG4002/certs/ca.crt"
TLS_CERT = "D:/y4sem1/CG4002/certs/fb2_new.crt"
TLS_KEY = "D:/y4sem1/CG4002/certs/fb2_new.key"

# -------------------------------
# FireBeetle TCP + XOR config
# -------------------------------
FIREBEETLE_IP = "172.20.10.10"
FIREBEETLE_PORT = 5000

# -------------------------------
# Unity TCP + AES config
# -------------------------------
UNITY_IP = "172.20.10.3"
UNITY_PORT = 6000

AES_KEY = b"1234567890abcdef"
XOR_KEY = bytes([0x55, 0xAA, 0x33, 0xCC, 0x0F, 0xF0, 0x99, 0x66,
                 0x12, 0x34, 0x56, 0x78, 0xAB, 0xCD, 0xEF, 0x01])

# -------------------------------
# Non-blocking TCP Managers
# -------------------------------
class TCPManager:
    def __init__(self, target_ip, target_port, name):
        self.target_ip = target_ip
        self.target_port = target_port
        self.name = name
        self.socket = None
        self.lock = Lock()
        self.send_queue = queue.Queue()
        self.connected = False
        self.thread = None
        self.running = True
        
    def start(self):
        self.thread = Thread(target=self._connection_worker, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
            
    def send(self, data):
        self.send_queue.put(data)
        
    def _connection_worker(self):
        while self.running:
            try:
                # Create new socket connection
                with self.lock:
                    if self.socket:
                        self.socket.close()
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.socket.settimeout(5.0)
                    self.socket.connect((self.target_ip, self.target_port))
                    self.connected = True
                    print(f"✅ Connected to {self.name}")
                
                # Process messages while connected
                while self.connected and self.running:
                    try:
                        # Wait for message with timeout
                        data = self.send_queue.get(timeout=1.0)
                        self._send_data(data)
                    except queue.Empty:
                        # Check if socket is still alive
                        try:
                            self.socket.settimeout(0.1)
                            self.socket.recv(1, socket.MSG_PEEK)
                        except (socket.timeout, BlockingIOError):
                            # Socket still good, continue
                            continue
                        except:
                            # Socket broken, reconnect
                            self.connected = False
                            break
                            
            except Exception as e:
                print(f"❌ {self.name} connection failed: {e}")
                self.connected = False
                time.sleep(2)  # Wait before retry
                
    def _send_data(self, data):
        try:
            with self.lock:
                if self.socket and self.connected:
                    self.socket.sendall(data)
                    print(f"📤 Sent to {self.name}: {data}")
        except Exception as e:
            print(f"❌ {self.name} send error: {e}")
            self.connected = False

# Initialize TCP managers
firebeetle_manager = TCPManager(FIREBEETLE_IP, FIREBEETLE_PORT, "FireBeetle")
unity_manager = TCPManager(UNITY_IP, UNITY_PORT, "Unity")

# -------------------------------
# Message processing
# -------------------------------
def send_to_firebeetle(movement_class: int):
    plaintext = str(movement_class).encode('utf-8').ljust(16, b'\x00')
    encrypted = bytes([plaintext[i] ^ XOR_KEY[i] for i in range(16)])
    firebeetle_manager.send(encrypted)

def send_to_unity(movement_class: int):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv=b'\x00' * 16)
    plaintext = str(movement_class).encode('utf-8').ljust(16, b'\x00')
    encrypted = cipher.encrypt(plaintext)
    unity_manager.send(encrypted)

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
        movement_class = payload_json.get("prediction")
        if movement_class is not None:
            movement_class = int(movement_class)
            print(f"\n🎯 Movement class from MQTT: {movement_class}")
            
            # Non-blocking sends
            send_to_firebeetle(movement_class)
            send_to_unity(movement_class)
        else:
            print("⚠️ No 'prediction' in payload")
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
    
    # Start TCP managers
    firebeetle_manager.start()
    unity_manager.start()

    try:
        client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
        client.loop_start()
        print("✅ Bridge running. Press Ctrl+C to exit.")

        # Main loop just sleeps - no blocking operations
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Stopping bridge...")
    finally:
        client.loop_stop()
        client.disconnect()
        firebeetle_manager.stop()
        unity_manager.stop()
        print("✅ Bridge stopped")

if __name__ == "__main__":
    main()