import socket
import struct
import json
import time
import threading

class LaptopRelay:
    def __init__(self, ultra96_ip, ultra96_port=8888, listen_port=9999):
        self.ultra96_ip = ultra96_ip
        self.ultra96_port = ultra96_port
        self.listen_port = listen_port

    def forward_to_ultra96(self, sensor_data):
        """Forward raw sensor data to Ultra96 and return JSON response"""
        try:
            # Connect to Ultra96
            print(f"Connecting to Ultra96 at {self.ultra96_ip}:{self.ultra96_port}")
            
            ultra96_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ultra96_socket.settimeout(10)
            ultra96_socket.connect((self.ultra96_ip, self.ultra96_port))

            # Send data length first (4 bytes), then the data
            data_length = struct.pack('!I', len(sensor_data))
            ultra96_socket.send(data_length + sensor_data)
            print(f"Sent {len(sensor_data)} bytes to Ultra96: {sensor_data.hex()}")

            # Receive response length
            response_length_data = ultra96_socket.recv(4)
            if not response_length_data:
                raise Exception("No response length received")

            response_length = struct.unpack('!I', response_length_data)[0]
            print(f"Expecting {response_length} byte response from Ultra96")

            # Receive JSON response
            response_json = b''
            while len(response_json) < response_length:
                chunk = ultra96_socket.recv(response_length - len(response_json))
                if not chunk:
                    break
                response_json += chunk

            ultra96_socket.close()

            if len(response_json) != response_length:
                raise Exception(f"Incomplete response: {len(response_json)}/{response_length} bytes")

            print(f"Received response from Ultra96: {response_json.decode()}")
            
            # Parse JSON response
            return json.loads(response_json.decode())

        except Exception as e:
            print(f"Error forwarding to Ultra96: {e}")
            return {
                "error": f"Relay error: {str(e)}",
                "timestamp": int(time.time() * 1000)
            }

    def handle_firebeetle_connection(self, client_socket, address):
        """Handle connection from FireBeetle"""
        print(f"FireBeetle connected from {address}")
        try:
            while True:
                # Receive 4-byte length prefix from FireBeetle (matching Ultra96 protocol)
                length_data = client_socket.recv(4)
                if not length_data:
                    print("No length data received, connection closed")
                    break

                data_length = struct.unpack('!I', length_data)[0]
                print(f"Expecting {data_length} bytes from FireBeetle")

                # Receive sensor data
                sensor_data = b''
                while len(sensor_data) < data_length:
                    chunk = client_socket.recv(data_length - len(sensor_data))
                    if not chunk:
                        break
                    sensor_data += chunk

                if len(sensor_data) != data_length:
                    print(f"Incomplete data from FireBeetle: {len(sensor_data)}/{data_length} bytes")
                    continue

                print(f"Received {data_length} bytes from FireBeetle: {sensor_data.hex()}")

                # Forward to Ultra96 for processing
                result = self.forward_to_ultra96(sensor_data)
                print(f"Processing result: {json.dumps(result, indent=2)}")

                # Send result back to FireBeetle (Ultra96 format: 4-byte length + JSON)
                response_json_str = json.dumps(result)
                response_length = struct.pack('!I', len(response_json_str))
                client_socket.send(response_length + response_json_str.encode())
                print(f"Sent response back to FireBeetle: {len(response_json_str)} bytes")

        except Exception as e:
            print(f"Error handling FireBeetle {address}: {e}")
        finally:
            client_socket.close()
            print(f"FireBeetle connection closed: {address}")

    def start_relay(self):
        """Start the relay server for FireBeetle connections"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.listen_port))
        server_socket.listen(5)

        print(f"Laptop Relay started on port {self.listen_port}")
        print("Waiting for FireBeetle connections...")
        print(f"Will forward to Ultra96 at {self.ultra96_ip}:{self.ultra96_port}")

        try:
            while True:
                client_socket, address = server_socket.accept()
                print(f"New connection from {address}")
                
                # Handle each FireBeetle in a separate thread
                thread = threading.Thread(
                    target=self.handle_firebeetle_connection,
                    args=(client_socket, address)
                )
                thread.daemon = True
                thread.start()
                print(f"Started thread for {address}")

        except KeyboardInterrupt:
            print("\nRelay shutdown requested")
        except Exception as e:
            print(f"Relay error: {e}")
        finally:
            server_socket.close()
            print("Relay stopped")

if __name__ == "__main__":
    # 直接使用 localhost 和端口 8888（SSH 隧道）
    ULTRA96_IP = "localhost"
    ULTRA96_PORT = 8888
    
    relay = LaptopRelay(ULTRA96_IP, ULTRA96_PORT)
    relay.start_relay()
