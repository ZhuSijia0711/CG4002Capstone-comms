import socket
import os
import time
import struct
import json
import paho.mqtt.client as mqtt
import ssl
from threading import Thread

class LaptopRelayMQTT:
    def __init__(self):
        # TCP Configuration
        self.TCP_IP = "0.0.0.0"
        self.TCP_PORT = 4210
        
        # MQTT Configuration for Ultra96 with TLS
        self.MQTT_BROKER = "makerslab-fpga-53.ddns.comp.nus.edu.sg"
        self.MQTT_PORT = 8883
        self.topic_sensor_to_ultra96 = "robot/sensor/to_ultra96"
        self.topic_processed_data = "robot/processed/data"
        self.topic_errors = "robot/errors"
        
        # TLS Certificate paths (WSL paths - update your_wsl_username)
        self.TLS_CA = "/home/your_wsl_username/tls_certs/ca.crt"
        self.TLS_CERT = "/home/your_wsl_username/tls_certs/laptop.crt"
        self.TLS_KEY = "/home/your_wsl_username/tls_certs/laptop.key"
        
        # MQTT Client for Ultra96
        self.ultra96_client = mqtt.Client(client_id="ultra96_forwarder_tls")
        self.setup_mqtt()
        
        # TCP server
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind((self.TCP_IP, self.TCP_PORT))
        
        # IMU data storage
        self.imu_values = {}
        
    def setup_mqtt(self):
        """Setup MQTT connection to Ultra96 with TLS"""
        # TLS configuration
        self.ultra96_client.tls_set(
            ca_certs=self.TLS_CA,
            certfile=self.TLS_CERT,
            keyfile=self.TLS_KEY,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )
        
        # For self-signed certificates
        self.ultra96_client.tls_insecure_set(True)
        
        self.ultra96_client.on_connect = self.on_connect_ultra96
        self.ultra96_client.on_message = self.on_message_ultra96
        
    def on_connect_ultra96(self, client, userdata, flags, rc):
        if rc == 0:
            print("Ultra96 TLS client connected successfully")
            client.subscribe(self.topic_processed_data)
            client.subscribe(self.topic_errors)
        else:
            print(f"Ultra96 TLS client failed to connect: {rc}")
    
    def on_message_ultra96(self, client, userdata, msg):
        """Handle messages from Ultra96"""
        try:
            if msg.topic == self.topic_processed_data:
                result = json.loads(msg.payload.decode())
                self.display_processed_data(result)
            elif msg.topic == self.topic_errors:
                print(f"Error from Ultra96: {msg.payload.decode()}")
        except Exception as e:
            print(f"Error processing Ultra96 message: {e}")
    
    def handle_tcp_client(self, client_socket, addr):
        """Handle incoming TCP connections"""
        print(f"Connection from {addr}")
        
        try:
            while True:
                # First receive the length of the data
                raw_length = client_socket.recv(4)
                if not raw_length:
                    break
                    
                length = struct.unpack('!I', raw_length)[0]
                
                # Then receive the actual data
                data = b''
                while len(data) < length:
                    packet = client_socket.recv(length - len(data))
                    if not packet:
                        break
                    data += packet
                
                if not data:
                    break
                
                # Process the received data
                self.process_sensor_data(data, addr)
                
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            client_socket.close()
            print(f"Connection from {addr} closed")
    
    def process_sensor_data(self, data, addr):
        """Process received sensor data"""
        # Publish to Ultra96 via MQTT
        try:
            message = {
                "data": data.hex(),
                "length": len(data),
                "timestamp": int(time.time() * 1000),
                "source": "firebeetle",
                "address": f"{addr[0]}:{addr[1]}"
            }
            
            self.ultra96_client.publish(
                self.topic_sensor_to_ultra96,
                json.dumps(message),
                qos=1
            )
            
            print(f"Forwarded to Ultra96: {len(data)} bytes from {addr}")
            
        except Exception as e:
            print(f"Error forwarding to Ultra96: {e}")
        
        # Parse and display IMU data
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
            print(f"Error parsing IMU data: {e}")
    
    def display_processed_data(self, result):
        """Display processed data from Ultra96"""
        print("\n" + "="*50)
        print("PROCESSED DATA FROM ULTRA96:")
        print("="*50)
        print(json.dumps(result, indent=2))
        print("="*50 + "\n")
    
    def display_imu_data(self):
        """Display IMU data in console"""
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print("📊 Real-Time IMU Data (Accel g / Gyro °/s)")
            print("IMU\tax\tay\taz\tgx\tgy\tgz")
            for i in range(5):
                label = f"IMU{i}"
                if label in self.imu_values:
                    print(label + "\t" + "\t".join(self.imu_values[label]))
                else:
                    print(label + "\twaiting")
            time.sleep(0.1)
    
    def start(self):
        """Start the TCP server and MQTT connection"""
        # Start MQTT connection to Ultra96
        try:
            self.ultra96_client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
            self.ultra96_client.loop_start()
            print(f"Connected to Ultra96 via TLS at {self.MQTT_BROKER}:{self.MQTT_PORT}")
        except Exception as e:
            print(f"Failed to connect to Ultra96 MQTT: {e}")
        
        # Start TCP server
        self.tcp_socket.listen(5)
        print(f"TCP server listening on {self.TCP_IP}:{self.TCP_PORT}")
        
        # Start display thread
        display_thread = Thread(target=self.display_imu_data)
        display_thread.daemon = True
        display_thread.start()
        
        # Accept connections
        try:
            while True:
                client_socket, addr = self.tcp_socket.accept()
                client_thread = Thread(target=self.handle_tcp_client, args=(client_socket, addr))
                client_thread.daemon = True
                client_thread.start()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.tcp_socket.close()
            self.ultra96_client.loop_stop()
            self.ultra96_client.disconnect()

if __name__ == "__main__":
    relay = LaptopRelayMQTT()
    relay.start()