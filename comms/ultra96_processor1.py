import socket
import json
import time
import struct
from datetime import datetime
import threading
import random

class Ultra96Processor:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.session_counter = 1000
        
    def calculate_crc16(self, data):
        """Calculate CRC16-CCITT checksum for data (polynomial 0x1021)"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc = crc << 1
                crc &= 0xFFFF
        return crc
        
    def process_sensor_data(self, raw_data):
        """
        Process SENSOR_DATA packet from FireBeetle
        Packet format: 
        - packetType: 1B (0x10)
        - sequence: 4B
        - timestamp: 4B
        - accel_x[5]: 10B (5x int16_t)
        - accel_y[5]: 10B (5x int16_t)
        - accel_z[5]: 10B (5x int16_t)
        - gyro_x[5]: 10B (5x int16_t)
        - gyro_y[5]: 10B (5x int16_t)
        - gyro_z[5]: 10B (5x int16_t)
        - crc: 2B
        Total: 71 bytes
        """
        try:
            if len(raw_data) != 71:
                return self._generate_error_response("Invalid SENSOR_DATA packet length")
            
            # Verify CRC first
            received_crc, = struct.unpack('H', raw_data[69:71])
            calculated_crc = self.calculate_crc16(raw_data[0:69])
            
            if calculated_crc != received_crc:
                return self._generate_error_response("CRC mismatch in SENSOR_DATA packet")
            
            # Parse sensor data
            packet_type, = struct.unpack('B', raw_data[0:1])
            if packet_type != 0x10:
                return self._generate_error_response("Not a SENSOR_DATA packet")
            
            sequence, = struct.unpack('I', raw_data[1:5])
            timestamp, = struct.unpack('I', raw_data[5:9])
            
            # Parse acceleration data for 5 sensors
            sensor_readings = []
            for i in range(5):
                # Acceleration data starts at offset 9
                accel_x = struct.unpack('5h', raw_data[9:19])[i]
                accel_y = struct.unpack('5h', raw_data[19:29])[i]
                accel_z = struct.unpack('5h', raw_data[29:39])[i]
                
                # Gyroscope data starts at offset 39
                gyro_x = struct.unpack('5h', raw_data[39:49])[i]
                gyro_y = struct.unpack('5h', raw_data[49:59])[i]
                gyro_z = struct.unpack('5h', raw_data[59:69])[i]
                
                sensor_readings.append({
                    "sensor_id": i + 1,
                    "acceleration": {"x": accel_x, "y": accel_y, "z": accel_z},
                    "gyroscope": {"x": gyro_x, "y": gyro_y, "z": gyro_z}
                })
            
            # Calculate overall robot state based on sensor readings
            emotion = self._calculate_emotion(sensor_readings)
            activity = self._determine_activity(sensor_readings)
            
            # Generate response
            response = {
                "session_id": self.session_counter,
                "sequence": sequence,
                "timestamp": timestamp,
                "robot_state": {
                    "emotion": emotion,
                    "activity": activity,
                    "battery_level": random.randint(70, 100)
                },
                "sensor_data": sensor_readings,
                "processed_at": datetime.now().isoformat()
            }
            
            self.session_counter += 1
            return response
            
        except Exception as e:
            return self._generate_error_response(f"Processing error: {str(e)}")
    
    def _calculate_emotion(self, sensor_readings):
        """Calculate emotion based on sensor data patterns"""
        total_acc = 0
        for reading in sensor_readings:
            acc = reading["acceleration"]
            total_acc += (acc["x"]**2 + acc["y"]**2 + acc["z"]**2)**0.5
        
        avg_acc = total_acc / len(sensor_readings)
        
        if avg_acc < 1000:
            return "calm"
        elif avg_acc < 3000:
            return "curious"
        elif avg_acc < 6000:
            return "excited"
        else:
            return "agitated"
    
    def _determine_activity(self, sensor_readings):
        """Determine activity based on sensor data patterns"""
        gyro_variance = 0
        gyro_means = {"x": 0, "y": 0, "z": 0}
        
        for reading in sensor_readings:
            gyro = reading["gyroscope"]
            gyro_means["x"] += gyro["x"]
            gyro_means["y"] += gyro["y"]
            gyro_means["z"] += gyro["z"]
        
        gyro_means["x"] /= len(sensor_readings)
        gyro_means["y"] /= len(sensor_readings)
        gyro_means["z"] /= len(sensor_readings)
        
        for reading in sensor_readings:
            gyro = reading["gyroscope"]
            gyro_variance += (gyro["x"] - gyro_means["x"])**2
            gyro_variance += (gyro["y"] - gyro_means["y"])**2
            gyro_variance += (gyro["z"] - gyro_means["z"])**2
        
        gyro_variance /= len(sensor_readings) * 3
        
        if gyro_variance < 100:
            return "sleeping"
        elif gyro_variance < 1000:
            return "resting"
        elif gyro_variance < 5000:
            return "exploring"
        elif gyro_variance < 10000:
            return "playing"
        else:
            return "agitated"
    
    def _generate_error_response(self, error_msg):
        return {
            "session_id": -1,
            "timestamp": int(time.time() * 1000),
            "robot_state": {
                "emotion": "error",
                "activity": "error",
                "battery_level": 0
            },
            "error": error_msg,
            "processed_at": datetime.now().isoformat()
        }
    
    def handle_client(self, client_socket, address):
        """Handle client connection - only process SENSOR_DATA"""
        print(f"Connection from {address}")
        
        try:
            while True:
                # Receive packet length first (4 bytes)
                length_data = client_socket.recv(4)
                if not length_data:
                    break
                
                data_length = struct.unpack('!I', length_data)[0]
                
                # Receive the actual sensor data
                sensor_data = b''
                while len(sensor_data) < data_length:
                    chunk = client_socket.recv(data_length - len(sensor_data))
                    if not chunk:
                        break
                    sensor_data += chunk
                
                if len(sensor_data) != data_length:
                    print(f"⚠️ Incomplete data received: {len(sensor_data)}/{data_length} bytes")
                    continue
                
                print(f"Received {data_length} bytes of sensor data from {address}")
                
                # Process the sensor data
                result = self.process_sensor_data(sensor_data)
                
                # Convert to JSON and send back to laptop only
                response_json = json.dumps(result)
                response_length = struct.pack('!I', len(response_json))
                
                client_socket.send(response_length + response_json.encode())
                print(f"Sent JSON response to laptop for sequence: {result.get('sequence', 'N/A')}")
                
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
            print(f"Connection closed with {address}")
    
    def start_server(self):
        """Start the processing server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        print(f"Ultra96 Processor started on {self.host}:{self.port}")
        print("Waiting for sensor data from laptop relay...")
        
        try:
            while True:
                client_socket, address = server_socket.accept()
                print(f"Accepted connection from {address}")
                
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                thread.daemon = True
                thread.start()
                
        except KeyboardInterrupt:
            print("\nServer shutdown requested")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            server_socket.close()
            print("Server stopped")

if __name__ == "__main__":
    processor = Ultra96Processor(port=8889)
    processor.start_server()