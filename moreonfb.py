import socket
import json
import struct
import time
from threading import Thread, Lock
import paho.mqtt.client as mqtt
import ssl
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

class FireBeetleMQTTPublisher:
    def __init__(self):
        # TCP Configuration (IMU inbound)
        self.TCP_IP = "0.0.0.0"
        self.TCP_PORT = 4210

        # MQTT Configuration
        self.MQTT_BROKER = "172.17.183.135"
        self.MQTT_PORT = 8883

        # AES Key and IV (16 bytes each) — used for battery data to Unity
        self.aes_key = bytes([0x2B, 0x7E, 0x15, 0x16, 0x28, 0xAE, 0xD2, 0xA6,
                              0xAB, 0xF7, 0x15, 0x88, 0x09, 0xCF, 0x4F, 0x3C])
        self.aes_iv = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
                             0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F])

        # XOR Key for movement commands (simple encryption) - must match Arduino
        self.xor_key = b"CG4002Robot2024!"  # 16-byte XOR key

        # TLS Certificates
        self.TLS_CA = "D:/y4sem1/CG4002/certs/ca.crt"
        self.TLS_CERT = "D:/y4sem1/CG4002/certs/firebeetle.crt"
        self.TLS_KEY = "D:/y4sem1/CG4002/certs/firebeetle.key"

        # MQTT Topics
        self.topic_sensor_to_ultra96 = "robot/sensor/to_ultra96"
        self.topic_ultra96_to_sensor = "ultra96/processed/to_firebeetle"

        # Unity TCP connection
        self.unity_socket = None
        self.UNITY_IP = "172.20.10.3"
        self.UNITY_PORT = 4211

        # MQTT client
        self.mqtt_client = None

        # IMU data cache
        self.imu_values = {}

        # Active TCP clients
        self.tcp_clients = set()

        # Command TCP clients to FireBeetles
        self.FIREBEETLE_CMD_IPS = ["172.20.10.4"]
        self.FIREBEETLE_CMD_PORT = 5001
        self.command_sockets = {}
        self.command_lock = Lock()

        # Connect to Unity
        self.connect_to_unity()

    def connect_to_unity(self):
        """Connect to Unity via TCP for battery data"""
        try:
            self.unity_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.unity_socket.connect((self.UNITY_IP, self.UNITY_PORT))
            print(f"✅ Connected to Unity at {self.UNITY_IP}:{self.UNITY_PORT}")
        except Exception as e:
            print(f"❌ Failed to connect to Unity: {e}")
            self.unity_socket = None

    def encrypt_battery_data(self, voltage, percentage):
        """Encrypt battery data using AES-CBC for Unity"""
        try:
            plaintext = f"VOLTAGE:{voltage:.3f},PERCENTAGE:{percentage:.0f}"
            plaintext_bytes = plaintext.encode('utf-8')
            padded_data = pad(plaintext_bytes, AES.block_size)
            cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
            encrypted_data = cipher.encrypt(padded_data)
            encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
            return encrypted_b64
        except Exception as e:
            print(f"❌ Battery data encryption failed: {e}")
            return None

    def send_battery_to_unity(self, voltage, percentage):
        """Send encrypted battery data to Unity via TCP"""
        if self.unity_socket:
            try:
                encrypted_battery = self.encrypt_battery_data(voltage, percentage)
                if encrypted_battery:
                    message = encrypted_battery + '\n'
                    self.unity_socket.sendall(message.encode('utf-8'))
                    print(f"🔋 Sent encrypted battery data to Unity: {voltage}V, {percentage}%")
            except Exception as e:
                print(f"❌ Failed to send battery data to Unity: {e}")
                try:
                    self.unity_socket.close()
                except:
                    pass
                self.unity_socket = None
                # Try to reconnect to Unity
                self.connect_to_unity()

    # ---------------- XOR Encryption for Movement Commands ----------------
    def xor_encrypt(self, plaintext):
        """Simple XOR encryption for movement commands (no Base64)"""
        plaintext_bytes = plaintext.encode('utf-8')
        encrypted = bytearray()
        key_length = len(self.xor_key)
        
        for i, byte in enumerate(plaintext_bytes):
            encrypted.append(byte ^ self.xor_key[i % key_length])
        
        # Return raw bytes (no Base64)
        return bytes(encrypted)

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
        """Handle incoming message from ultra96/processed/to_firebeetle."""
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

            # ---------- XOR ENCRYPTED COMMANDS ----------
            plaintext = str(number) + '\n'
            
            # Encrypt the command using XOR
            encrypted_command = self.xor_encrypt(plaintext)
            
            # Add newline for TCP framing
            encrypted_command_with_newline = encrypted_command + b'\n'

            to_remove = []
            with self.command_lock:
                for ip, sock in list(self.command_sockets.items()):
                    try:
                        if sock:
                            sock.sendall(encrypted_command_with_newline)
                            print(f"🔐 Sent XOR-encrypted movement '{number}' to FireBeetle {ip}:{self.FIREBEETLE_CMD_PORT}")
                            print(f"   Encrypted hex: {encrypted_command.hex()}")
                        else:
                            raise Exception("socket is None")
                    except Exception as e:
                        print(f"⚠️ Failed to send encrypted command to {ip}: {e}")
                        to_remove.append(ip)

                # Attempt reconnects for failed sockets
                for ip in to_remove:
                    try:
                        old = self.command_sockets.pop(ip, None)
                        if old:
                            try:
                                old.close()
                            except:
                                pass
                        self._connect_command_socket(ip)
                    except Exception as e:
                        print(f"⚠️ Reconnect attempt to {ip} failed: {e}")

        except Exception as e:
            print(f"Error handling MQTT message: {e}")

    # ---------------- TCP Handling (IMU inbound) ----------------
    def handle_tcp_client(self, client_socket, addr):
        """Handle plaintext IMU data from FireBeetle"""
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
                    message = message_b.decode('utf-8').strip()
                    if not message:
                        continue

                    print(f"📨 Received IMU data: {message[:80]}...")

                    # Parse data and separate IMU and battery
                    imu_sets, battery_data = self.parse_sensor_data(message)

                    # Send encrypted battery data to Unity
                    if battery_data:
                        self.send_battery_to_unity(battery_data['voltage'], battery_data['percentage'])

                    # Pack IMU data and send to MQTT
                    if imu_sets:
                        all_bytes = self.pack_imu_data(imu_sets)
                        self.publish_binary_to_mqtt(all_bytes)
                        print(f"📤 Published {len(all_bytes)} bytes to Ultra96 "
                              f"({len(imu_sets)} sets, {len(imu_sets)*5} IMUs)")

        except Exception as e:
            print(f"⚠️ TCP client error {addr}: {e}")
        finally:
            client_socket.close()
            self.tcp_clients.discard(client_socket)
            print(f"🔌 TCP connection closed: {addr}")

    def parse_sensor_data(self, text):
        """Parse sensor data string"""
        imu_sets = []
        battery_data = None

        entries = [entry.strip() for entry in text.split(";") if entry.strip()]
        current_set = {}

        for entry in entries:
            if entry.startswith("Fuel:"):
                # Parse battery data
                try:
                    data_part = entry.replace("Fuel:", "").replace("V", "")
                    voltage_str, percentage_str = data_part.split(",")
                    voltage = float(voltage_str)
                    percentage = float(percentage_str.replace("%", ""))
                    battery_data = {'voltage': voltage, 'percentage': percentage}
                except Exception as e:
                    print(f"❌ Failed to parse battery data: {e}")
            elif ":" in entry:
                # Parse IMU data
                label, vals = entry.split(":", 1)
                nums = [float(v) for v in vals.split(",") if v]
                if len(nums) == 6:
                    current_set[label] = nums
                    if len(current_set) == 5:
                        imu_sets.append(current_set)
                        current_set = {}

        return imu_sets, battery_data

    def pack_imu_data(self, imu_sets):
        """Pack IMU data into binary format for MQTT"""
        all_bytes = b''
        for imu_set in imu_sets:
            for imu_label in ["IMU0", "IMU1", "IMU2", "IMU3", "IMU4"]:
                imu_list = imu_set.get(imu_label, [0.0]*6)
                imu_list = [float(v) for v in imu_list]
                all_bytes += struct.pack('!6f', *imu_list)
        return all_bytes

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
            if self.unity_socket:
                self.unity_socket.close()
            tcp_socket.close()
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()

    def _connect_command_socket(self, ip):
        """Connect to FireBeetle command server"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, self.FIREBEETLE_CMD_PORT))
            s.settimeout(None)
            with self.command_lock:
                self.command_sockets[ip] = s
            print(f"✅ Connected to FireBeetle command server at {ip}:{self.FIREBEETLE_CMD_PORT}")
            return True
        except Exception as e:
            print(f"⚠️ Could not connect to {ip}:{self.FIREBEETLE_CMD_PORT} - {e}")
            with self.command_lock:
                self.command_sockets[ip] = None
            return False

    def connect_command_sockets(self):
        """Connect to all configured FireBeetle command servers"""
        for ip in self.FIREBEETLE_CMD_IPS:
            self._connect_command_socket(ip)

    def start(self):
        """Start MQTT + TCP components"""
        print("🚀 Starting FireBeetle MQTT Publisher & TCP Bridge...")
        self.connect_command_sockets()

        if not self.setup_mqtt():
            print("❌ MQTT setup failed. Exiting...")
            return

        self.start_tcp_server()

if __name__ == "__main__":
    publisher = FireBeetleMQTTPublisher()
    publisher.start()