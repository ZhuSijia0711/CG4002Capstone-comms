import socket
import json
import time
import threading

class LaptopRelay:
    def __init__(self, ultra96_ip, ultra96_port=8888, listen_port=9999):
        self.ultra96_ip = ultra96_ip
        self.ultra96_port = ultra96_port
        self.listen_port = listen_port

    def forward_to_ultra96(self, sensor_data_text):
        """Forward text sensor data to Ultra96 and return JSON response"""
        try:
            # Connect to Ultra96
            ultra96_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ultra96_socket.settimeout(10)
            ultra96_socket.connect((self.ultra96_ip, self.ultra96_port))

            # Convert text to bytes and send with length prefix
            sensor_data_bytes = sensor_data_text.encode('utf-8')
            data_length = len(sensor_data_bytes)
            data_length_bytes = data_length.to_bytes(4, byteorder='big')
            
            ultra96_socket.send(data_length_bytes + sensor_data_bytes)
            print(f"Forwarded {data_length} bytes to Ultra96")

            # Receive response length from Ultra96
            response_length_data = ultra96_socket.recv(4)
            if not response_length_data:
                raise Exception("No response length received from Ultra96")

            response_length = int.from_bytes(response_length_data, byteorder='big')
            print(f"Expecting {response_length} byte response from Ultra96")

            # Receive JSON response from Ultra96
            response_json = b''
            while len(response_json) < response_length:
                chunk = ultra96_socket.recv(response_length - len(response_json))
                if not chunk:
                    break
                response_json += chunk

            ultra96_socket.close()

            if len(response_json) != response_length:
                raise Exception(f"Incomplete response from Ultra96: {len(response_json)}/{response_length} bytes")

            # Parse and print JSON response
            result = json.loads(response_json.decode())
            print("\n" + "="*50)
            print("PROCESSED DATA FROM ULTRA96:")
            print("="*50)
            print(json.dumps(result, indent=2))
            print("="*50 + "\n")
            
            return result

        except Exception as e:
            print(f"Error forwarding to Ultra96: {e}")
            error_result = {
                "error": f"Relay error: {str(e)}",
                "timestamp": int(time.time() * 1000)
            }
            print(json.dumps(error_result, indent=2))
            return error_result

    def handle_firebeetle_connection(self, client_socket, address):
        """Handle connection from FireBeetle - forward text data to Ultra96 only"""
        print(f"FireBeetle connected from {address}")
        
        try:
            while True:
                # Receive text data from FireBeetle (no length prefix)
                data = client_socket.recv(4096)
                if not data:
                    print("Connection closed by FireBeetle")
                    break

                # Decode the text data
                sensor_data_text = data.decode('utf-8', errors='ignore').strip()
                print(f"Received text data from FireBeetle: {sensor_data_text[:100]}...")

                # Forward to Ultra96 for processing
                self.forward_to_ultra96(sensor_data_text)
                
                # DO NOT send response back to FireBeetle

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
        print("Processing results will be displayed on laptop only (not sent back to FireBeetle)")
        print("Expected data format: 'IMU0:ax,ay,az,gx,gy,gz;IMU1:ax,ay,az,gx,gy,gz;...'")

        try:
            while True:
                client_socket, address = server_socket.accept()
                print(f"New connection from {address}")
                
                thread = threading.Thread(
                    target=self.handle_firebeetle_connection,
                    args=(client_socket, address)
                )
                thread.daemon = True
                thread.start()

        except KeyboardInterrupt:
            print("\nRelay shutdown requested")
        except Exception as e:
            print(f"Relay error: {e}")
        finally:
            server_socket.close()
            print("Relay stopped")

if __name__ == "__main__":
    ULTRA96_IP = "localhost"
    ULTRA96_PORT = 8888
    
    relay = LaptopRelay(ULTRA96_IP, ULTRA96_PORT)
    relay.start_relay()