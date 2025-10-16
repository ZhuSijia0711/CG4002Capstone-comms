import socket
import struct
import time
import random

class FakeFireBeetle:
    def __init__(self, laptop_ip, laptop_port=9999):
        self.laptop_ip = laptop_ip
        self.laptop_port = laptop_port
        self.sequence_number = 0

    def calculate_crc16(self, data):
        """Calculate CRC16-CCITT checksum for data (polynomial 0x1021)"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return crc

    def create_sensor_data_packet(self):
        """Create SENSOR_DATA packet (71 bytes total)"""
        self.sequence_number += 1
        timestamp = int(time.time())
        
        # Generate sensor data for 5 IMU sensors
        accel_x = [random.randint(-20000, 20000) for _ in range(5)]
        accel_y = [random.randint(-20000, 20000) for _ in range(5)]
        accel_z = [random.randint(-20000, 20000) for _ in range(5)]
        gyro_x = [random.randint(-32768, 32767) for _ in range(5)]
        gyro_y = [random.randint(-32768, 32767) for _ in range(5)]
        gyro_z = [random.randint(-32768, 32767) for _ in range(5)]
        
        # Create packet data (without CRC) - 69 bytes
        packet_data = struct.pack('B I I', 0x10, self.sequence_number, timestamp)
        packet_data += struct.pack('5h', *accel_x)
        packet_data += struct.pack('5h', *accel_y)
        packet_data += struct.pack('5h', *accel_z)
        packet_data += struct.pack('5h', *gyro_x)
        packet_data += struct.pack('5h', *gyro_y)
        packet_data += struct.pack('5h', *gyro_z)
        
        # Calculate CRC
        crc = self.calculate_crc16(packet_data)
        
        # Add CRC to packet - total 71 bytes
        sensor_packet = packet_data + struct.pack('H', crc)
        
        return sensor_packet

    def send_sensor_data(self):
        """Send sensor data to the laptop relay"""
        try:
            # Connect to laptop relay
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.laptop_ip, self.laptop_port))

            # Send SENSOR_DATA packet
            sensor_packet = self.create_sensor_data_packet()
            
            # Send with length prefix
            length_prefix = struct.pack('!I', len(sensor_packet))
            sock.send(length_prefix + sensor_packet)

            print(f"📤 Sent SENSOR_DATA packet: {len(sensor_packet)} bytes")
            print(f"Sequence: {self.sequence_number}")
            print("Waiting for processing... (no response expected back)")

            # Wait a moment to ensure data is processed
            time.sleep(1)
            
            sock.close()
            return True

        except Exception as e:
            print(f"❌ Error sending data: {e}")
            return False

    def run_continuous_test(self, interval=5):
        """Continuously send sensor data at specified intervals"""
        print(f"🔁 Starting continuous test. Sending data every {interval} seconds")
        print("Data will be forwarded to Ultra96 for processing")
        print("Results will be displayed on laptop only (no response to FireBeetle)")
        print("Press Ctrl+C to stop")

        try:
            while True:
                success = self.send_sensor_data()
                if not success:
                    print("Failed to send data, retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                    
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n🛑 Test stopped by user")

if __name__ == "__main__":
    LAPTOP_IP = "172.17.183.135"  # Change to your laptop's IP

    fake_beetle = FakeFireBeetle(LAPTOP_IP)
    fake_beetle.run_continuous_test(interval=3)