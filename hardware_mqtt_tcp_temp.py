import socket
import json
import struct
import time
from threading import Thread
import paho.mqtt.client as mqtt
import ssl

class FireBeetleMQTTPublisher:
    def __init__(self):
        # TCP Configuration (for receiving data from sensors)
        self.TCP_IP = "0.0.0.0"
        self.TCP_PORT = 4210
        
        # MQTT Configuration - Connect to LAPTOP broker
        self.MQTT_BROKER = "172.17.183.135"  # Laptop's WSL IP address
        self.MQTT_PORT = 8883               # TLS MQTT port
        
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

    def setup_mqtt(self):
        """Setup MQTT connection to laptop broker"""
        self.mqtt_client = mqtt.Client(
            client_id="firebeetle_publisher"
        )
        
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
            print(f"✅ Connected to MQTT broker at {self.MQTT_BROKER}:{self.MQTT_PORT}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to MQTT broker: {e}")
            return False

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ MQTT client connected successfully")
        else:
            print(f"❌ MQTT client failed to connect: {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        print(f"⚠️  MQTT client disconnected: {rc}")

    def publish_to_mqtt(self, data, addr):
        """Publish TCP data to MQTT topic"""
        try:
            message = {
                "data": data.hex(),
                "length": len(data),
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
                print(f"📤 Published {len(data)} bytes to {self.topic_sensor_to_ultra96}")
            else:
                print("❌ MQTT client not connected, cannot publish")
                
        except Exception as e:
            print(f"❌ MQTT publish error: {e}")

    def handle_tcp_client(self, client_socket, addr):
        """Handle incoming TCP connections from sensors"""
        print(f"🔌 TCP connection from {addr}")
        try:
            while True:
                # Receive length prefix first
                raw_length = client_socket.recv(4)
                if not raw_length:
                    break
                    
                length = struct.unpack("!I", raw_length)[0]
                
                # Receive the actual data
                data = b''
                while len(data) < length:
                    packet = client_socket.recv(length - len(data))
                    if not packet:
                        break
                    data += packet
                    
                if not data:
                    break
                    
                # Process the received data
                self.publish_to_mqtt(data, addr)
                self.parse_imu_data(data)
                
        except Exception as e:
            print(f"❌ Error with TCP client {addr}: {e}")
        finally:
            client_socket.close()
            print(f"🔌 TCP connection from {addr} closed")

    def parse_imu_data(self, data):
        """Parse IMU data for display"""
        try:
            message = data.decode("utf-8", errors="ignore")
            imu_data = message.strip().split(";")
            for imu in imu_data:
                if not imu or ":" not in imu:
                    continue
                label, values = imu.split(":", 1)
                nums = values.split(",")
                while len(nums) < 6:
                    nums.append("---")
                self.imu_values[label] = nums[:6]
        except Exception as e:
            print(f"❌ Error parsing IMU data: {e}")

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
            print("🛑 TCP server shutting down...")
        finally:
            tcp_socket.close()
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()

    def start(self):
        """Start the FireBeetle publisher"""
        print("Starting FireBeetle as MQTT Publisher...")
        
        if not self.setup_mqtt():
            print("❌ Failed to setup MQTT, exiting...")
            return
            
        self.start_tcp_server()

if __name__ == "__main__":
    publisher = FireBeetleMQTTPublisher()
    publisher.start()