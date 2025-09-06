import socket
import struct
import time
import random
import json

class FakeFireBeetle:
    def __init__(self, laptop_ip, laptop_port=9999):
        self.laptop_ip = laptop_ip
        self.laptop_port = laptop_port

    def generate_sensor_data(self, sensor_type):
        """Generate fake sensor data based on sensor type"""
        # Sensor type definitions:
        # 0x01: Emotion sensor (1 byte value)
        # 0x02: Temperature sensor (4 bytes float)
        # 0x03: Humidity sensor (4 bytes float)
        # 0x04: Motion sensor (6 bytes: x,y,z as 2-byte integers each)

        if sensor_type == 0x01:  # Emotion sensor
            emotion_value = random.randint(0, 5)  # 0-5 different emotions
            data = struct.pack('B', emotion_value)
            return data

        elif sensor_type == 0x02:  # Temperature sensor
            temperature = random.uniform(20.0, 35.0)  # 20-35 degrees Celsius
            data = struct.pack('f', temperature)
            return data
        
        elif sensor_type == 0x03:  # Humidity sensor
            humidity = random.uniform(30.0, 80.0)  # 30-80% humidity
            data = struct.pack('f', humidity)
            return data

        elif sensor_type == 0x04:  # Motion sensor
            x = random.randint(-1000, 1000)  # X-axis acceleration
            y = random.randint(-1000, 1000)  # Y-axis acceleration
            z = random.randint(-1000, 1000)  # Z-axis acceleration
            data = struct.pack('!hhh', x, y, z)  # 3 signed short integers (2 bytes each)
            return data

        else:
            # Default: emotion sensor
            emotion_value = random.randint(0, 5)
            data = struct.pack('B', emotion_value)
            return data

    def send_sensor_data(self, sensor_type=0x01):
        """Send fake sensor data to the laptop relay - UPDATED PROTOCOL"""
        try:
            # Generate sensor data
            sensor_data = self.generate_sensor_data(sensor_type)

            # Create the packet in Ultra96 format: [sensor_type:1B][data_length:1B][sensor_data:N bytes]
            data_length = len(sensor_data)
            packet = struct.pack('BB', sensor_type, data_length) + sensor_data
            
            # Connect to laptop relay
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.laptop_ip, self.laptop_port))

            # Send data with 4-byte length prefix (matching Ultra96 protocol)
            length_prefix = struct.pack('!I', len(packet))  # Changed from '!H' to '!I'
            sock.send(length_prefix + packet)

            print(f"📤 Sent {len(packet)} bytes of sensor data (type: 0x{sensor_type:02x})")
            print(f"📦 Packet content: {packet.hex()}")

            # Wait for response from laptop relay (Ultra96 response)
            try:
                # First receive 4-byte response length
                response_length_data = sock.recv(4)
                if response_length_data:
                    response_length = struct.unpack('!I', response_length_data)[0]
                    print(f"📥 Expecting {response_length} byte response")
                    
                    # Receive the JSON response
                    response_json = b''
                    while len(response_json) < response_length:
                        chunk = sock.recv(response_length - len(response_json))
                        if not chunk:
                            break
                        response_json += chunk
                    
                    if response_json:
                        try:
                            response_data = json.loads(response_json.decode())
                            print(f"📥 Received JSON response: {json.dumps(response_data, indent=2)}")
                        except json.JSONDecodeError:
                            print(f"📥 Received raw response: {response_json.decode()}")
            except socket.timeout:
                print("⏰ No response received (timeout)")
            except Exception as e:
                print(f"❌ Error receiving response: {e}")

            sock.close()
            return True

        except Exception as e:
            print(f"❌ Error sending data: {e}")
            return False

    def run_continuous_test(self, interval=5, sensor_type=0x01):
        """Continuously send sensor data at specified intervals"""
        print(f"🔁 Starting continuous test. Sending data every {interval} seconds")
        print("Press Ctrl+C to stop")

        try:
            while True:
                success = self.send_sensor_data(sensor_type)
                time.sleep(interval)

                # Occasionally change sensor type for variety
                if random.random() < 0.2:  # 20% chance to change sensor type
                    sensor_type = random.choice([0x01, 0x02, 0x03, 0x04])
                    print(f"🔄 Changed to sensor type: 0x{sensor_type:02x}")

        except KeyboardInterrupt:
            print("\n🛑 Test stopped by user")

if __name__ == "__main__":
    # Replace with your laptop's IP address
    LAPTOP_IP = "172.17.183.135"  # Change this to your laptop's IP

    # Create fake FireBeetle
    fake_beetle = FakeFireBeetle(LAPTOP_IP)

    # Test options:
    # 1. Send a single packet
    # fake_beetle.send_sensor_data(sensor_type=0x01)  # Emotion sensor

    # 2. Run continuous test
    fake_beetle.run_continuous_test(interval=3, sensor_type=0x01)
