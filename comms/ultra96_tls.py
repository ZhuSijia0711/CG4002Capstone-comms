import paho.mqtt.client as mqtt
import json
import time
import struct
from datetime import datetime
import random
import csv
import os
import ssl

class Ultra96MQTTSubscriber:
    def __init__(self):
        self.session_counter = 1000
        
        # MQTT Configuration - Connect to LAPTOP broker
        self.MQTT_BROKER = "localhost"  # Laptop's IP address
        self.MQTT_PORT = 8883               # TLS MQTT port
        
        # MQTT Topics
        self.topic_sensor_to_ultra96 = "robot/sensor/to_ultra96"
        self.topic_processed_data = "robot/processed/data"
        self.topic_errors = "robot/errors"
        
        # TLS Certificate paths (on Ultra96)
        self.TLS_CA = "/home/xilinx/tls_certs/ca.crt"
        self.TLS_CERT = "/home/xilinx/tls_certs/ultra96.crt"
        self.TLS_KEY = "/home/xilinx/tls_certs/ultra96.key"
        
        # CSV file setup
        self.csv_file = "imu_data.csv"
        
        # Initialize CSV file
        self._initialize_csv()
        
        # MQTT Client
        self.client = mqtt.Client(client_id="ultra96_subscriber_tls")
        self.setup_mqtt()

    def _initialize_csv(self):
        """Initialize CSV file with headers"""
        if not os.path.exists(self.csv_file):
            try:
                with open(self.csv_file, 'w', newline='') as file:
                    writer = csv.writer(file)
                    headers = []
                    for i in range(5):
                        headers.extend([
                            f"IMU{i}_ax", f"IMU{i}_ay", f"IMU{i}_az",
                            f"IMU{i}_gx", f"IMU{i}_gy", f"IMU{i}_gz"
                        ])
                    writer.writerow(headers)
                print(f"✅ Initialized CSV file: {self.csv_file}")
            except Exception as e:
                print(f"❌ Error initializing CSV: {e}")

    def setup_mqtt(self):
        """Setup MQTT connection to laptop broker"""
        # TLS configuration
        self.client.tls_set(
            ca_certs=self.TLS_CA,
            certfile=self.TLS_CERT,
            keyfile=self.TLS_KEY,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )
        
        # For self-signed certificates
        self.client.tls_insecure_set(True)
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc):
        """Called when connected to laptop broker"""
        if rc == 0:
            print("✅ Connected to Laptop MQTT broker successfully")
            client.subscribe(self.topic_sensor_to_ultra96)
            print(f"📝 Subscribed to topic: {self.topic_sensor_to_ultra96}")
        else:
            print(f"❌ Failed to connect to MQTT broker: {rc}")

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages from laptop broker"""
        try:
            if msg.topic == self.topic_sensor_to_ultra96:
                message = json.loads(msg.payload.decode())
                
                print(f"📥 Received {message['length']} bytes from laptop")
                print(f"   Source: {message.get('source', 'unknown')}")
                
                result = self.process_sensor_data(message)
                
                # Send processing result back to laptop
                self.client.publish(
                    self.topic_processed_data,
                    json.dumps(result),
                    qos=1
                )
                
                print(f"📤 Sent processed data back to laptop")
                    
        except Exception as e:
            error_msg = f"❌ Error processing MQTT message: {e}"
            print(error_msg)
            self.client.publish(self.topic_errors, error_msg, qos=1)

    def process_sensor_data(self, message):
        """Process sensor data from FireBeetle"""
        try:
            if "data" in message and message["data"]:
                sensor_data = bytes.fromhex(message["data"])
                return self.process_binary_sensor_data(sensor_data)
            else:
                return self._generate_error_response("No processable data found")
                
        except Exception as e:
            return self._generate_error_response(f"Processing error: {str(e)}")

    def process_binary_sensor_data(self, raw_data):
        """Process binary SENSOR_DATA packet"""
        try:
            if len(raw_data) != 71:
                return self._generate_error_response("Invalid packet length")
            
            # Parse packet (simplified for example)
            sequence = struct.unpack('I', raw_data[1:5])[0]
            timestamp = struct.unpack('I', raw_data[5:9])[0]
            
            # Process sensor data (simplified)
            sensor_readings = []
            for i in range(5):
                sensor_readings.append({
                    "sensor_id": i,
                    "acceleration": {"x": 0.1, "y": 0.2, "z": 0.3},
                    "gyroscope": {"x": 0.4, "y": 0.5, "z": 0.6}
                })
            
            # Write to CSV
            self.write_to_csv(sensor_readings)
            
            # Generate response
            return {
                "session_id": self.session_counter,
                "sequence": sequence,
                "timestamp": timestamp,
                "robot_state": {
                    "emotion": "calm",
                    "activity": "exploring",
                    "battery_level": 95,
                    "sensor_count": len(sensor_readings)
                },
                "sensor_data": sensor_readings,
                "processing_time_ms": 50,
                "processed_at": datetime.now().isoformat(),
                "status": "success"
            }
            
        except Exception as e:
            return self._generate_error_response(f"Binary processing error: {str(e)}")

    def write_to_csv(self, sensor_readings):
        """Write IMU data to CSV file"""
        try:
            with open(self.csv_file, 'a', newline='') as file:
                writer = csv.writer(file)
                row = []
                for i in range(5):
                    imu_found = False
                    for imu_data in sensor_readings:
                        if str(imu_data['sensor_id']) == str(i):
                            accel = imu_data['acceleration']
                            gyro = imu_data['gyroscope']
                            row.extend([accel['x'], accel['y'], accel['z'],
                                      gyro['x'], gyro['y'], gyro['z']])
                            imu_found = True
                            break
                    if not imu_found:
                        row.extend([0.0] * 6)
                writer.writerow(row)
                print(f"💾 Data written to CSV: {len(row)} values")
                
        except Exception as e:
            print(f"❌ Error writing to CSV: {e}")

    def _generate_error_response(self, error_msg):
        """Generate error response"""
        return {
            "session_id": -1,
            "sequence": -1,
            "timestamp": int(time.time() * 1000),
            "robot_state": {
                "emotion": "error",
                "activity": "error",
                "battery_level": 0,
                "sensor_count": 0
            },
            "error": error_msg,
            "processing_time_ms": 0,
            "processed_at": datetime.now().isoformat(),
            "status": "error"
        }

    def on_disconnect(self, client, userdata, rc):
        print(f"⚠️  Disconnected from broker: {rc}")

    def start(self):
        """Start the MQTT subscriber"""
        try:
            self.client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
            self.client.loop_start()
            print(f"✅ Connected to Laptop broker at {self.MQTT_BROKER}:{self.MQTT_PORT}")
            
            # Keep running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested...")
        except Exception as e:
            print(f"❌ Failed to start: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 Ultra96 MQTT Subscriber (TLS)")
    print("=" * 60)
    
    # IMPORTANT: Replace with your laptop's actual IP address
    laptop_ip = "localhost"  # CHANGE THIS to your laptop's IP
    print(f"📍 Connecting to Laptop broker at: {laptop_ip}:8883")
    print(f"💾 CSV file: imu_data.csv")
    print("=" * 60)
    
    subscriber = Ultra96MQTTSubscriber()
    subscriber.MQTT_BROKER = laptop_ip  # Set the correct IP
    subscriber.start()