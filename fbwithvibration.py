import socket
import json
import struct
import time
from threading import Thread
import paho.mqtt.client as mqtt
import ssl
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class FireBeetleMQTTPublisher:
    def __init__(self):
        # TCP Configuration
        self.TCP_IP = "0.0.0.0"
        self.TCP_PORT = 4210

        # MQTT Configuration
        self.MQTT_BROKER = "172.17.183.135"
        self.MQTT_PORT = 8883

        # AES Key and IV (16 bytes each)
        self.aes_key = bytes([0x2B, 0x7E, 0x15, 0x16, 0x28, 0xAE, 0xD2, 0xA6,
                              0xAB, 0xF7, 0x15, 0x88, 0x09, 0xCF, 0x4F, 0x3C])
        self.aes_iv = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
                             0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F])

        # TLS Certificates
        self.TLS_CA = "D:/y4sem1/CG4002/certs/ca.crt"
        self.TLS_CERT = "D:/y4sem1/CG4002/certs/firebeetle.crt"
        self.TLS_KEY = "D:/y4sem1/CG4002/certs/firebeetle.key"

        # MQTT Topics
        self.topic_sensor_to_ultra96 = "robot/sensor/to_ultra96"
        self.topic_ultra96_to_sensor = "robot/processed/data"

        # MQTT client
        self.mqtt_client = None

        # IMU data cache
        self.imu_values = {}

        # Active TCP clients (FireBeetles)
        self.tcp_clients = set()

    # ---------------- AES Encryption / Decryption ----------------
    def decrypt_data(self, encrypted_base64):
        """Decrypt AES-CBC Base64-encoded data from FireBeetle"""
        try:
            if isinstance(encrypted_base64, str):
                b64 = encrypted_base64.strip().encode("utf-8")
            else:
                b64 = encrypted_base64.strip()

            encrypted_data = base64.b64decode(b64)
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
            decrypted_padded = cipher.decrypt(encrypted_data)
            decrypted_bytes = unpad(decrypted_padded, 16)
            return decrypted_bytes
        except Exception as e:
            print(f"Decryption error: {e}")
            return None

    def encrypt_data(self, plaintext_bytes):
        """Encrypt raw bytes using AES-CBC and return Base64-encoded ciphertext"""
        try:
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
            padded = pad(plaintext_bytes, 16)
            encrypted = cipher.encrypt(padded)
            return base64.b64encode(encrypted)
        except Exception as e:
            print(f"Encryption error: {e}")
            return None

    # ---------------- MQTT Setup ----------------
    def setup_mqtt(self):
        """Setup MQTT client with TLS"""
        self.mqtt_client = mqtt.Client(client_id="firebeetle_publisher")

        self.mqtt_client.tls_set(
            ca_certs=self.TLS_CA,
            certfile=self.TLS_CERT,
            keyfile=self.TLS_KEY,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )
        self.mqtt_client.tls_insecure_set(True)

        # Register callbacks
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.on_message = self.on_mqtt_message

        try:
            self.mqtt_client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            print(f"✅ Connected to MQTT broker at {self.MQTT_BROKER}:{self.MQTT_PORT}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to MQTT broker: {e}")
            return False

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ MQTT connection successful")
            client.subscribe(self.topic_ultra96_to_sensor, qos=1)
            print(f"Subscribed to topic: {self.topic_ultra96_to_sensor}")
        else:
            print(f"❌ MQTT connection failed (code {rc})")

    def on_mqtt_disconnect(self, client, userdata, rc):
        print(f"⚠️ MQTT disconnected (code {rc})")

    # ---------------- MQTT Message Handler ----------------
    def on_mqtt_message(self, client, userdata, msg):
        """Handle incoming message from robot/processed/data."""
        try:
            payload = msg.payload.decode('utf-8').strip()
            print(f"📩 Received from MQTT ({msg.topic}): {payload}")

            # Try to parse JSON
            try:
                data = json.loads(payload)
                if "movement_class" in data:
                    number = int(data["movement_class"])
                else:
                    print(f"⚠️ JSON missing 'movement_class': {data}")
                    return
            except json.JSONDecodeError:
                # If not JSON, try plain integer
                try:
                    number = int(payload)
                except ValueError:
                    print(f"⚠️ Invalid integer payload: {payload}")
                    return

            # Encrypt integer as string bytes
            plaintext_bytes = str(number).encode('utf-8')
            encrypted_b64 = self.encrypt_data(plaintext_bytes)
            if not encrypted_b64:
                print("❌ Encryption failed, skipping send.")
                return

            # Send encrypted Base64 string to each FireBeetle
            for s in list(self.tcp_clients):
                try:
                    s.sendall(encrypted_b64 + b'\n')
                    print(f"🔁 Sent encrypted integer '{number}' to FireBeetle {s.getpeername()}")
                except Exception as e:
                    print(f"⚠️ Failed to send to {s}: {e}")
                    self.tcp_clients.remove(s)
                    s.close()

        except Exception as e:
            print(f"Error handling MQTT message: {e}")

    # ---------------- MQTT Publish ----------------
    def publish_binary_to_mqtt(self, data_bytes):
        """Publish binary IMU data to Ultra96"""
        if self.mqtt_client and self.mqtt_client.is_connected():
            self.mqtt_client.publish(
                self.topic_sensor_to_ultra96,
                payload=data_bytes,
                qos=1
            )
            print(f"📤 Published {len(data_bytes)} binary bytes to {self.topic_sensor_to_ultra96}")
        else:
            print("⚠️ MQTT not connected, cannot publish")

    # ---------------- TCP Handling ----------------
    def handle_tcp_client(self, client_socket, addr):
        """Handle data from FireBeetle (encrypted Base64 IMU readings)"""
        print(f"🔌 New TCP connection from {addr}")
        self.tcp_clients.add(client_socket)
        buffer = b""

        try:
            while True:
                data = client_socket.recv(2048)
                if not data:
                    break

                buffer += data
                while b'\n' in buffer:
                    message_b, buffer = buffer.split(b'\n', 1)
                    encrypted_b64_bytes = message_b.strip()
                    if not encrypted_b64_bytes:
                        continue

                    decrypted_bytes = self.decrypt_data(encrypted_b64_bytes)
                    if decrypted_bytes is not None:
                        try:
                            text = decrypted_bytes.decode('utf-8')
                            print(f"🔓 Decrypted text: {text[:80]}...")
                            self.parse_imu_data(text)
                        except UnicodeDecodeError:
                            print(f"🔓 Decrypted raw bytes: {decrypted_bytes[:24].hex()}...")

                        # Pack IMU values into binary format
                        imu_bytes = b''
                        for imu_label in ["IMU0", "IMU1", "IMU2", "IMU3", "IMU4"]:
                            imu_list = self.imu_values.get(imu_label, [0.0]*6)
                            imu_list = [float(v) for v in imu_list]
                            imu_bytes += struct.pack('!6f', *imu_list)

                        self.publish_binary_to_mqtt(imu_bytes)
                    else:
                        print(f"❌ Failed to decrypt message from {addr}")

        except Exception as e:
            print(f"⚠️ TCP client error {addr}: {e}")
        finally:
            client_socket.close()
            self.tcp_clients.discard(client_socket)
            print(f"🔌 TCP connection closed: {addr}")

    def parse_imu_data(self, data):
        """Parse IMU data from decrypted FireBeetle string"""
        try:
            imu_data = data.strip().split(";")
            for imu in imu_data:
                if not imu or ":" not in imu:
                    continue
                label, values = imu.split(":", 1)
                nums = values.split(",")
                while len(nums) < 6:
                    nums.append("---")
                self.imu_values[label] = nums[:6]

                print(f"{label}: Accel({nums[0]}, {nums[1]}, {nums[2]}), "
                      f"Gyro({nums[3]}, {nums[4]}, {nums[5]})")
        except Exception as e:
            print(f"Error parsing IMU data: {e}")

    def start_tcp_server(self):
        """Start TCP server to receive FireBeetle data"""
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_socket.bind((self.TCP_IP, self.TCP_PORT))
        tcp_socket.listen(5)
        print(f"🚀 TCP server listening on {self.TCP_IP}:{self.TCP_PORT}")

        try:
            while True:
                client_socket, addr = tcp_socket.accept()
                client_thread = Thread(target=self.handle_tcp_client, args=(client_socket, addr))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("🛑 TCP server shutting down...")
        finally:
            tcp_socket.close()
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()

    def start(self):
        """Start MQTT + TCP components"""
        print("🚀 Starting FireBeetle MQTT Publisher & TCP Bridge...")
        if not self.setup_mqtt():
            print("❌ MQTT setup failed. Exiting...")
            return
        self.start_tcp_server()


if __name__ == "__main__":
    publisher = FireBeetleMQTTPublisher()
    publisher.start()
