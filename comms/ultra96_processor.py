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
        
    def process_sensor_data(self, raw_data):
        """
        Process raw binary sensor data from FireBeetle
        Expected format: [sensor_type:1B][data_length:1B][sensor_data:N bytes]
        """
        try:
            # Parse binary data (example structure)
            # You'll need to adjust this based on your actual FireBeetle data format
            if len(raw_data) < 2:
                return self._generate_error_response("Invalid data length")
            
            sensor_type = raw_data[0]
            data_length = raw_data[1]
            
            if len(raw_data) < 2 + data_length:
                return self._generate_error_response("Incomplete data")
            
            sensor_data = raw_data[2:2+data_length]
            
            # Process based on sensor type
            if sensor_type == 0x01:  # Example: Emotion sensor
                emotion_value = struct.unpack('B', sensor_data)[0] if data_length == 1 else 0
                emotion = self._get_emotion_from_value(emotion_value)
            else:
                emotion = "neutral"
            
            # Generate response
            response = {
                "session_id": self.session_counter,
                "timestamp": int(time.time() * 1000),  # Milliseconds
                "robot_state": {
                    "emotion": emotion,
                    "activity": self._get_random_activity(),
                    "battery_level": random.randint(70, 100)
                },
                "raw_data_hex": raw_data.hex(),  # For debugging
                "processed_at": datetime.now().isoformat()
            }
            
            self.session_counter += 1
            return response
            
        except Exception as e:
            return self._generate_error_response(f"Processing error: {str(e)}")
    
    def _get_emotion_from_value(self, value):
        emotions = ["happy", "sad", "excited", "calm", "curious", "tired"]
        return emotions[value % len(emotions)] if 0 <= value < len(emotions) else "neutral"
    
    def _get_random_activity(self):
        activities = ["feed", "play", "sleep", "explore", "learn", "socialize"]
        return random.choice(activities)
    
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
        """Handle client connection and process sensor data"""
        print(f"Connection from {address}")
        
        try:
            while True:
                # Receive data (first 4 bytes = length)
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
                
                print(f"Received {data_length} bytes of sensor data")
                
                # Process the sensor data
                result = self.process_sensor_data(sensor_data)
                
                # Convert to JSON and send back
                response_json = json.dumps(result)
                response_length = struct.pack('!I', len(response_json))
                
                client_socket.send(response_length + response_json.encode())
                print(f"Sent JSON response: {result['session_id']}")
                
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
            print(f"🔌 Connection closed with {address}")
    
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
                
                # Handle each client in a separate thread
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
    processor = Ultra96Processor()
    processor.start_server()
