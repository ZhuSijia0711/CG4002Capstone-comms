import paho.mqtt.client as mqtt
import json
import time
import struct
import random
from datetime import datetime
import ssl

class FireBeetleSimulator:
    def __init__(self):
        # MQTT Configuration - Connect to local broker
        self.MQTT_BROKER = "localhost"
        self.MQTT_PORT = 8883
        
        # MQTT Topics
        self.topic_sensor_to_ultra96 = "robot/sensor/to_ultra96"
        self.topic_processed_data = "robot/processed/data"
        self.topic_errors = "robot/errors"
        
        # TLS Certificate paths
        self.TLS_CA = "D:/y4sem1/CG4002/certs/ca.crt"
        self.TLS_CERT = "D:/y4sem1/CG4002/certs/firebeetle.crt"
        self.TLS_KEY = "D:/y4sem1/CG4002/certs/firebeetle.key"
        
        # Simulation parameters
        self.sequence_number = 0
        self.sensor_count = 5
        
        # MQTT Client
        self.client = mqtt.Client(client_id="firebeetle_simulator")
        self.setup_mqtt()
        
        # Store received processed data
        self.processed_data = []

    def setup_mqtt(self):
        """Setup MQTT connection with TLS"""
        try:
            self.client.tls_set(
                ca_certs=self.TLS_CA,
                certfile=self.TLS_CERT,
                keyfile=self.TLS_KEY,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
            self.client.tls_insecure_set(True)  # For self-signed certs
            
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.on_disconnect = self.on_disconnect
            
        except Exception as e:
            print(f"❌ TLS setup error: {e}")

    def on_connect(self, client, userdata, flags, rc):
        """Called when connected to broker"""
        if rc == 0:
            print("✅ Connected to MQTT broker successfully")
            # Subscribe to processed data topic to see Ultra96 responses
            client.subscribe(self.topic_processed_data)
            client.subscribe(self.topic_errors)
            print(f"📝 Subscribed to response topics")
        else:
            print(f"❌ Failed to connect to MQTT broker: {rc}")

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages from Ultra96"""
        try:
            if msg.topic == self.topic_processed_data:
                message = json.loads(msg.payload.decode())
                self.processed_data.append(message)
                print(f"📥 Received processed data from Ultra96:")
                print(f"   Session ID: {message.get('session_id', 'N/A')}")
                print(f"   Status: {message.get('status', 'N/A')}")
                print(f"   Sensor count: {message.get('robot_state', {}).get('sensor_count', 0)}")
                if 'error' in message:
                    print(f"   Error: {message['error']}")
                
            elif msg.topic == self.topic_errors:
                print(f"🚨 Error from Ultra96: {msg.payload.decode()}")
                
        except Exception as e:
            print(f"❌ Error processing response: {e}")

    def on_disconnect(self, client, userdata, rc):
        print(f"⚠️  Disconnected from broker: {rc}")

    def generate_sensor_data(self):
        """Generate realistic IMU sensor data packet"""
        # Packet structure: [header][sequence][timestamp][sensor_data...]
        header = b'\xAA'  # Start byte
        sequence = struct.pack('I', self.sequence_number)
        timestamp = struct.pack('I', int(time.time()))
        
        # Generate sensor data for 5 IMUs (each IMU: 6 float values = 24 bytes)
        sensor_data = b''
        for i in range(self.sensor_count):
            # Generate realistic sensor values
            accel_x = random.uniform(-2.0, 2.0)  # Acceleration in g
            accel_y = random.uniform(-2.0, 2.0)
            accel_z = random.uniform(-1.0, 1.0)  # Z usually has gravity
            
            gyro_x = random.uniform(-200.0, 200.0)  # Gyro in dps
            gyro_y = random.uniform(-200.0, 200.0)
            gyro_z = random.uniform(-200.0, 200.0)
            
            # Pack as floats (4 bytes each)
            sensor_data += struct.pack('f', accel_x)
            sensor_data += struct.pack('f', accel_y)
            sensor_data += struct.pack('f', accel_z)
            sensor_data += struct.pack('f', gyro_x)
            sensor_data += struct.pack('f', gyro_y)
            sensor_data += struct.pack('f', gyro_z)
        
        # Create complete packet (1 + 4 + 4 + (5*24) = 129 bytes)
        packet = header + sequence + timestamp + sensor_data
        
        self.sequence_number += 1
        return packet

    def publish_sensor_data(self):
        """Publish sensor data to Ultra96"""
        try:
            # Generate binary sensor data
            binary_data = self.generate_sensor_data()
            
            # Create MQTT message
            message = {
                "source": "firebeetle_simulator",
                "timestamp": datetime.now().isoformat(),
                "sequence": self.sequence_number,
                "length": len(binary_data),
                "data": binary_data.hex(),  # Convert to hex string for JSON
                "sensor_count": self.sensor_count
            }
            
            # Publish to Ultra96
            result = self.client.publish(
                self.topic_sensor_to_ultra96,
                json.dumps(message),
                qos=1
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"📤 Published sensor data packet #{self.sequence_number} ({len(binary_data)} bytes)")
            else:
                print(f"❌ Failed to publish: {result.rc}")
                
        except Exception as e:
            print(f"❌ Error publishing data: {e}")

    def start(self):
        """Start the FireBeetle simulator"""
        try:
            print("=" * 60)
            print("🔥 FireBeetle MQTT Simulator")
            print("=" * 60)
            print(f"📍 Connecting to broker: {self.MQTT_BROKER}:{self.MQTT_PORT}")
            print(f"📤 Publishing to: {self.topic_sensor_to_ultra96}")
            print(f"📥 Listening to: {self.topic_processed_data}")
            print("=" * 60)
            
            # Connect to broker
            self.client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
            self.client.loop_start()
            
            # Start publishing data every 3 seconds
            print("🚀 Starting data transmission...")
            print("Press Ctrl+C to stop")
            print("=" * 60)
            
            while True:
                self.publish_sensor_data()
                time.sleep(3)  # Send data every 3 seconds
                
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested...")
        except Exception as e:
            print(f"❌ Failed to start: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            print("✅ FireBeetle simulator stopped")

if __name__ == "__main__":
    simulator = FireBeetleSimulator()
    simulator.start()