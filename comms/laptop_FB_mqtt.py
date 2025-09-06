import paho.mqtt.client as mqtt
import json
import time

class LaptopRelayMQTT:
    def __init__(self):
        # MQTT Topics
        self.topic_sensor_raw = "robot/sensor/raw"
        self.topic_sensor_to_ultra96 = "robot/sensor/to_ultra96"
        self.topic_processed_data = "robot/processed/data"
        self.topic_errors = "robot/errors"
        
        # MQTT Clients - Connect to Ultra96 via SSH tunnel
        self.ultra96_client = mqtt.Client(client_id="ultra96_forwarder")
        self.local_client = mqtt.Client(client_id="laptop_local")
        
        self.setup_mqtt()
        
    def setup_mqtt(self):
        """Setup MQTT connections and callbacks"""
        # Local client for FireBeetle communication
        self.local_client.on_connect = self.on_connect_local
        self.local_client.on_message = self.on_message_local
        
        # Ultra96 client for forwarding via SSH tunnel
        self.ultra96_client.on_connect = self.on_connect_ultra96
        self.ultra96_client.on_message = self.on_message_ultra96
        
    def on_connect_local(self, client, userdata, flags, rc):
        if rc == 0:
            print("Local client connected to MQTT broker")
            client.subscribe(self.topic_sensor_raw)
        else:
            print(f"Local client failed to connect: {rc}")
    
    def on_connect_ultra96(self, client, userdata, flags, rc):
        if rc == 0:
            print("Ultra96 client connected via SSH tunnel")
            # Subscribe to processed data from Ultra96
            client.subscribe(self.topic_processed_data)
            client.subscribe(self.topic_errors)
        else:
            print(f"Ultra96 client failed to connect: {rc}")
    
    def on_message_local(self, client, userdata, msg):
        """Handle messages from FireBeetle"""
        try:
            if msg.topic == self.topic_sensor_raw:
                message = json.loads(msg.payload.decode())
                print(f"Received from FireBeetle: {message['length']} bytes")
                self.forward_to_ultra96(message)
                
        except Exception as e:
            print(f"Error processing local message: {e}")
    
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
    
    def forward_to_ultra96(self, message):
        """Forward sensor data to Ultra96 via SSH tunnel"""
        try:
            self.ultra96_client.publish(
                self.topic_sensor_to_ultra96,
                json.dumps(message),
                qos=1
            )
            print(f"Forwarded to Ultra96 via SSH tunnel: {message['length']} bytes")
            
        except Exception as e:
            print(f"Error forwarding to Ultra96: {e}")
    
    def display_processed_data(self, result):
        """Display processed data from Ultra96"""
        print("\n" + "="*50)
        print("PROCESSED DATA FROM ULTRA96 (via SSH tunnel):")
        print("="*50)
        print(json.dumps(result, indent=2))
        print("="*50 + "\n")
    
    def start_mqtt_connections(self):
        """Start MQTT connections"""
        try:
            # Local connection for FireBeetle
            self.local_client.connect("localhost", 1883, 60)
            
            # Connection to Ultra96 via SSH tunnel (localhost:8888 → Ultra96:8889)
            self.ultra96_client.connect("localhost", 8888, 60)
            
            self.local_client.loop_start()
            self.ultra96_client.loop_start()
            
            return True
            
        except Exception as e:
            print(f"Failed to connect to MQTT brokers: {e}")
            return False
    
    def stop_mqtt_connections(self):
        self.local_client.loop_stop()
        self.ultra96_client.loop_stop()
        self.local_client.disconnect()
        self.ultra96_client.disconnect()

if __name__ == "__main__":
    relay = LaptopRelayMQTT()
    
    if relay.start_mqtt_connections():
        print("Laptop MQTT relay started!")
        print("FireBeetle → localhost:1883")
        print("Ultra96 → localhost:8888 (SSH tunnel)")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            relay.stop_mqtt_connections()
    else:
        print("Failed to start MQTT relay")