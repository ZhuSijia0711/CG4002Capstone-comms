import socket
import json
import struct
import time
from threading import Thread
import paho.mqtt.client as mqtt
import ssl
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class FireBeetleMQTTPublisher:
    def __init__(self):
        # TCP Configuration (for receiving data from sensors)
        self.TCP_IP = "0.0.0.0"
        self.TCP_PORT = 4210

        # MQTT Configuration - Connect to LAPTOP broker
        self.MQTT_BROKER = "172.17.183.135"  # Laptop's WSL IP address
        self.MQTT_PORT = 8883               # TLS MQTT port

        
        self.aes_key = bytes([0x2B, 0x7E, 0x15, 0x16, 0x28, 0xAE, 0xD2, 0xA6,
                              0xAB, 0xF7, 0x15, 0x88, 0x09, 0xCF, 0x4F, 0x3C])
        self.aes_iv = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
                             0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F])

        # TLS Certificate paths
        self.TLS_CA = "D:/y4sem1/CG4002/certs/ca.crt"
        self.TLS_CERT = "D:/y4sem1/CG4002/certs/firebeetle.crt"
        self.TLS_KEY = "D:/y4sem1/CG4002/certs/firebeetle.key"

        # MQTT Topics
        self.topic_sensor_to_ultra96 = "robot/sensor/to_ultra96"

        # MQTT Client
        self.mqtt_client = None

        # IMU data storage
        self.imu_values = {}

        # Buffer for TCP data
        self.buffer = b""

    def decrypt_data(self, encrypted_base64):
        """Decrypt AES-encrypted data and return raw bytes."""
        try:
            if isinstance(encrypted_base64, str):
                b64 = encrypted_base64.strip().encode("utf-8")
            else:
                b64 = encrypted_base64.strip()

            # Decode base64
            try:
                encrypted_data = base64.b64decode(b64, validate=True)
            except Exception:
                try:
                    # Add padding for base64 if needed
                    padding = 4 - (len(b64) % 4)
                    if padding != 4:
                        b64 += b'=' * padding
                    encrypted_data = base64.b64decode(b64)
                except Exception as e:
                    print(f"Base64 decode failed: {e}")
                    return None

            if len(encrypted_data) % 16 != 0:
                print(f"Invalid ciphertext length: {len(encrypted_data)}")
                return None

            # Decrypt with fixed IV
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
            decrypted_padded = cipher.decrypt(encrypted_data)
            
            # Remove padding
            decrypted_bytes = unpad(decrypted_padded, 16)
            
            return decrypted_bytes

        except Exception as e:
            print(f"Decryption error: {e}")
            return None




    def setup_mqtt(self):
        """Setup MQTT connection to laptop broker"""
        self.mqtt_client = mqtt.Client(client_id="firebeetle_publisher")

        # TLS configuration
        self.mqtt_client.tls_set(
            ca_certs=self.TLS_CA,
            certfile=self.TLS_CERT,
            keyfile=self.TLS_KEY,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )

        # For self-signed certificates
        self.mqtt_client.tls_insecure_set(True)

        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect

        try:
            self.mqtt_client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            print(f"Connected to MQTT broker at {self.MQTT_BROKER}:{self.MQTT_PORT}")
            return True
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            return False

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("MQTT client connected successfully")
        else:
            print(f"MQTT client failed to connect: {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        print(f"MQTT client disconnected: {rc}")

    def publish_to_mqtt(self, data, addr):
        """Publish TCP data to MQTT topic"""
        try:
            # support bytes (hex) or string
            if isinstance(data, (bytes, bytearray)):
                data_field = data.hex()
                length = len(data)
            else:
                data_field = data
                length = len(data.encode('utf-8'))

            message = {
                "data": data_field,
                "length": length,
                "timestamp": int(time.time() * 1000),
                "source": "firebeetle",
                "address": f"{addr[0]}:{addr[1]}"
            }
            if self.mqtt_client and self.mqtt_client.is_connected():
                self.mqtt_client.publish(
                    self.topic_sensor_to_ultra96,
                    json.dumps(message),
                    qos=1
                )
                print(f"📤 Published {length} bytes to {self.topic_sensor_to_ultra96}")
            else:
                print("MQTT client not connected, cannot publish")
        except Exception as e:
            print(f"MQTT publish error: {e}")

    def publish_binary_to_mqtt(self, data_bytes):
        """Publish raw binary payload (not JSON)"""
        if self.mqtt_client and self.mqtt_client.is_connected():
            self.mqtt_client.publish(
                self.topic_sensor_to_ultra96,
                payload=data_bytes,
                qos=1
            )
            print(f"Published {len(data_bytes)} binary bytes to {self.topic_sensor_to_ultra96}")
        else:
            print("MQTT client not connected, cannot publish binary data")


    def handle_tcp_client(self, client_socket, addr):
        """Handle incoming TCP connections from sensors"""
        print(f"🔌 TCP connection from {addr}")
        buffer = b""
        try:
            while True:
                data = client_socket.recv(2048)  # buffer size
                if not data:
                    break

                # Add to buffer
                buffer += data

                # Process complete messages (delimited by newline)
                while b'\n' in buffer:
                    message_b, buffer = buffer.split(b'\n', 1)
                    encrypted_b64_bytes = message_b.strip()   # KEEP as bytes

                    if not encrypted_b64_bytes:
                        continue

                    # Decrypt the message (pass bytes)
                    # Decrypt the message (pass bytes) -> now returns bytes or None
                    decrypted_bytes = self.decrypt_data(encrypted_b64_bytes)
                    if decrypted_bytes is not None:
                        # Try print human-readable text if it is text
                        try:
                            text = decrypted_bytes.decode('utf-8')
                            print(f"Decrypted text (preview): {text[:80]}...")
                        except UnicodeDecodeError:
                            # Not text — print hex preview
                            print(f"Decrypted raw bytes (hex preview): {decrypted_bytes[:24].hex()}...")

                        # First, parse decrypted text if possible
                        try:
                            decoded = decrypted_bytes.decode('utf-8')
                            self.parse_imu_data(decoded)  # <-- parse BEFORE packing
                        except UnicodeDecodeError:
                            # binary packet — do NOT call parse_imu_data
                            pass

                        # Pack IMUs in the order they are received
                        imu_bytes = b''
                        for imu_label in ["IMU0","IMU1","IMU2","IMU3","IMU4"]:  # adjust if your labels differ
                            imu_list = self.imu_values.get(imu_label, [0.0]*6)
                            imu_list = [float(v) for v in imu_list]
                            imu_bytes += struct.pack('!6f', *imu_list)

                        # Publish the packed binary data
                        self.publish_binary_to_mqtt(imu_bytes)

                    else:
                        print(f"Failed to decrypt message: {encrypted_b64_bytes[:50]!r}...")

        except Exception as e:
            print(f"Error with TCP client {addr}: {e}")
        finally:
            client_socket.close()
            print(f"🔌 TCP connection from {addr} closed")

    def parse_imu_data(self, data):
        """Parse IMU data for display — expects a plain Python string"""
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

                # Display IMU data (optional)
                print(f"{label}: Accel({nums[0]}, {nums[1]}, {nums[2]}), "
                    f"Gyro({nums[3]}, {nums[4]}, {nums[5]})")
        except Exception as e:
            print(f"Error parsing IMU data: {e}")


    def start_tcp_server(self):
        """Start TCP server to receive data from sensors"""
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_socket.bind((self.TCP_IP, self.TCP_PORT))
        tcp_socket.listen(5)
        print(f"🔌 TCP server listening on {self.TCP_IP}:{self.TCP_PORT}")
        try:
            while True:
                client_socket, addr = tcp_socket.accept()
                client_thread = Thread(
                    target=self.handle_tcp_client,
                    args=(client_socket, addr)
                )
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("TCP server shutting down...")
        finally:
            tcp_socket.close()
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()

    def start(self):
        """Start the FireBeetle publisher"""
        print("Starting FireBeetle as MQTT Publisher...")
        if not self.setup_mqtt():
            print("Failed to setup MQTT, exiting...")
            return
        self.start_tcp_server()

if __name__ == "__main__":
    publisher = FireBeetleMQTTPublisher()
    publisher.start() 