import paho.mqtt.client as mqtt
import json
import time
import struct
from datetime import datetime
import csv
import os
import ssl
import random

#import sys
#sys.path.append("/home/xilinx/ai_code")  # <-- path to ai_model.py

#from ai_model import classify_from_csv


class Ultra96MQTTSubscriber:
    def __init__(self):
        self.session_counter = 1000
        
        # MQTT Configuration - Connect to Laptop broker
        self.MQTT_BROKER = "localhost"  # Laptop IP
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
        self._initialize_csv()
        
        # MQTT Client
        self.client = mqtt.Client(client_id="ultra96_subscriber_tls")
        self.setup_mqtt()

    # ---------------- CSV handling ----------------
    def _initialize_csv(self):
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
                print(f"Initialized CSV file: {self.csv_file}")
            except Exception as e:
                print(f"Error initializing CSV: {e}")

    def write_to_csv(self, sensor_readings):
        try:
            with open(self.csv_file, 'a', newline='') as file:
                writer = csv.writer(file)
                row = []
                for i in range(5):
                    imu_found = False
                    for imu_data in sensor_readings:
                        if imu_data['sensor_id'] == i:
                            accel = imu_data['acceleration']
                            gyro = imu_data['gyroscope']
                            row.extend([
                                round(accel['x'], 3), round(accel['y'], 3), round(accel['z'], 3),
                                round(gyro['x'], 3), round(gyro['y'], 3), round(gyro['z'], 3)
                            ])
                            imu_found = True
                            break
                    if not imu_found:
                        row.extend([0.0] * 6)
                writer.writerow(row)
                print(f"Data written to CSV: {len(row)} values")
        except Exception as e:
            print(f"Error writing to CSV: {e}")

    # ---------------- MQTT setup ----------------
    def setup_mqtt(self):
        self.client.tls_set(
            ca_certs=self.TLS_CA,
            certfile=self.TLS_CERT,
            keyfile=self.TLS_KEY,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )
        self.client.tls_insecure_set(True)  # for self-signed certs
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to Laptop MQTT broker successfully")
            client.subscribe(self.topic_sensor_to_ultra96)
            print(f"Subscribed to topic: {self.topic_sensor_to_ultra96}")
        else:
            print(f"Failed to connect to MQTT broker: {rc}")

    def on_disconnect(self, client, userdata, rc):
        print(f"Disconnected from broker: {rc}")

    # ---------------- Sensor data handling ----------------
    def process_binary_sensor_data(self, raw_data):
        try:
            if len(raw_data) != 120:
                return self._generate_error_response(f"Invalid packet length: {len(raw_data)}")

            sensor_readings = []
            offset = 0
            for imu_id in range(5):
                imu_values = struct.unpack('!6f', raw_data[offset:offset+24])
                accel = {"x": imu_values[0], "y": imu_values[1], "z": imu_values[2]}
                gyro  = {"x": imu_values[3], "y": imu_values[4], "z": imu_values[5]}
                sensor_readings.append({
                    "sensor_id": imu_id,
                    "acceleration": accel,
                    "gyroscope": gyro
                })
                offset += 24

            self.write_to_csv(sensor_readings)

            return {"session_id": self.session_counter, "sensor_data": sensor_readings, "status": "success"}
        except Exception as e:
            return self._generate_error_response(f"Binary processing error: {str(e)}")

    def _generate_error_response(self, error_msg):
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

    # ---------------- AI simulation ----------------
    def run_ai_inference(self, sensor_data):
        """Simulate AI: assign a random integer 0-3 as movement class"""
        return random.randint(0, 3)
    #def run_ai_inference(self, sensor_data):
    #"""Call external AI model that reads from CSV"""
    #try:
     #   movement_class = classify_from_csv(self.csv_file)
      #  return movement_class
    #except Exception as e:
     #   print(f"AI inference error: {e}")
      #  return -1


    # ---------------- MQTT message handler ----------------
    def on_message(self, client, userdata, msg):
        try:
            if msg.topic == self.topic_sensor_to_ultra96:
                raw_data = msg.payload
                print(f"Received {len(raw_data)} bytes from laptop")

                processed = self.process_binary_sensor_data(raw_data)
                if processed["status"] != "success":
                    self.client.publish(self.topic_errors, json.dumps(processed), qos=1)
                    return

                # Run simulated AI
                movement_class = self.run_ai_inference(processed["sensor_data"])
                response = {
                    "session_id": self.session_counter,
                    "movement_class": int(movement_class),
                    "status": "success",
                    "timestamp": datetime.now().isoformat()
                }

                # Publish response over TLS
                self.client.publish(self.topic_processed_data, json.dumps(response), qos=1)
                # Publish just the integer as a string
                #self.client.publish(self.topic_processed_data, str(movement_class), qos=1)
                print(f"Sent movement class {movement_class} back to laptop")

        except Exception as e:
            error_msg = f"Error processing MQTT message: {e}"
            print(error_msg)
            self.client.publish(self.topic_errors, error_msg, qos=1)

    # ---------------- Start subscriber ----------------
    def start(self):
        try:
            self.client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
            self.client.loop_start()
            print(f"Connected to Laptop broker at {self.MQTT_BROKER}:{self.MQTT_PORT}")

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutdown requested...")
        except Exception as e:
            print(f"Failed to start: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    print("="*60)
    print("Ultra96 MQTT Subscriber (TLS, AI Simulation)")
    print("="*60)
    subscriber = Ultra96MQTTSubscriber()
    subscriber.start()

