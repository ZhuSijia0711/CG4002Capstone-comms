import paho.mqtt.client as mqtt
import json
import time
import struct
from datetime import datetime
import random
import csv
import os

class Ultra96ProcessorMQTT:
    def __init__(self):
        self.session_counter = 1000
        
        # MQTT Topics
        self.topic_sensor_to_ultra96 = "robot/sensor/to_ultra96"
        self.topic_processed_data = "robot/processed/data"
        self.topic_errors = "robot/errors"
        
        # CSV file setup
        self.csv_file = "imu_data.csv"
        
        # 初始化CSV文件
        self._initialize_csv()
        
        # MQTT Client - Listen on port 8889
        self.client = mqtt.Client(client_id="ultra96_processor")
        self.setup_mqtt()
    
    def _initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
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
        """Write IMU data to CSV file - 30 columns per row (5 IMUs × 6 values each)"""
        try:
            with open(self.csv_file, 'a', newline='') as file:
                writer = csv.writer(file)
                
                # 准备行数据 - 按IMU顺序排列
                row = []
                
                # 按IMU0到IMU4的顺序添加数据
                for i in range(5):
                    imu_found = False
                    for imu_data in sensor_readings:
                        sensor_id = imu_data['sensor_id']
                        # 支持多种ID格式: "IMU0", 0, "0", 等
                        if (str(sensor_id) == f"IMU{i}" or 
                            str(sensor_id) == str(i) or 
                            (isinstance(sensor_id, int) and sensor_id == i)):
                            accel = imu_data['acceleration']
                            gyro = imu_data['gyroscope']
                            row.extend([
                                accel['x'], accel['y'], accel['z'],
                                gyro['x'], gyro['y'], gyro['z']
                            ])
                            imu_found = True
                            break
                    
                    if not imu_found:
                        # 如果没有该IMU的数据，填充空值
                        row.extend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
                
                writer.writerow(row)
                print(f"📝 Data written to CSV: {len(sensor_readings)} IMUs, {len(row)} values")
                return True
                
        except Exception as e:
            print(f"❌ Error writing to CSV: {e}")
            return False
    
    def setup_mqtt(self):
        """Setup MQTT connection and callbacks"""
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print("Ultra96 MQTT server started on port 8889")
            print("Subscribed to topic: robot/sensor/to_ultra96")
            client.subscribe(self.topic_sensor_to_ultra96)
        else:
            print(f"Failed to start MQTT server: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages from laptop"""
        try:
            if msg.topic == self.topic_sensor_to_ultra96:
                message = json.loads(msg.payload.decode())
                
                print(f"Received {message['length']} bytes from laptop")
                print(f"Source: {message.get('source', 'unknown')}")
                print(f"Timestamp: {message.get('timestamp', 'N/A')}")
                
                result = None
                
                # 首先尝试处理二进制数据
                if "data" in message and message["data"]:
                    try:
                        sensor_data = bytes.fromhex(message["data"])
                        if len(sensor_data) == 71:  # 预期的二进制包大小
                            result = self.process_binary_sensor_data(sensor_data)
                            if result.get("status") == "success":
                                result["data_format"] = "binary"
                        else:
                            print(f"Unexpected binary data size: {len(sensor_data)} bytes")
                    except Exception as e:
                        print(f"Binary processing failed: {e}")
                
                # 如果二进制处理失败，尝试处理文本数据
                if result is None and "text_data" in message and message["text_data"]:
                    try:
                        result = self.process_text_sensor_data(
                            message["text_data"], 
                            message.get("timestamp", int(time.time() * 1000))
                        )
                        if result.get("status") == "success":
                            result["data_format"] = "text"
                    except Exception as e:
                        print(f"Text processing failed: {e}")
                
                # 如果都有预处理的数据，使用预处理的数据
                if result is None and "imu_readings" in message and message["imu_readings"]:
                    try:
                        result = self.process_preprocessed_data(message)
                        if result.get("status") == "success":
                            result["data_format"] = "preprocessed"
                    except Exception as e:
                        print(f"Preprocessed data processing failed: {e}")
                
                if result is None:
                    result = self._generate_error_response("No processable data found in message")
                
                # 添加消息元数据
                result["source"] = message.get("source", "unknown")
                result["original_timestamp"] = message.get("timestamp")
                result["received_at"] = datetime.now().isoformat()
                
                # 写入CSV
                if result.get("status") == "success" and "sensor_data" in result:
                    csv_success = self.write_to_csv(result["sensor_data"])
                    result["csv_written"] = csv_success
                
                # 发送处理结果
                self.client.publish(
                    self.topic_processed_data,
                    json.dumps(result),
                    qos=1
                )
                
                print(f"Processed and sent back sequence: {result.get('sequence', 'N/A')}")
                print(f"Data format: {result.get('data_format', 'unknown')}")
                print(f"CSV written: {result.get('csv_written', False)}")
                    
        except Exception as e:
            error_msg = f"Error processing MQTT message: {e}"
            print(error_msg)
            self.client.publish(self.topic_errors, error_msg, qos=1)
    
    def process_binary_sensor_data(self, raw_data):
        """
        Process binary SENSOR_DATA packet from FireBeetle
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
            received_crc = struct.unpack('H', raw_data[69:71])[0]
            calculated_crc = self.calculate_crc16(raw_data[0:69])
            
            if calculated_crc != received_crc:
                return self._generate_error_response("CRC mismatch in SENSOR_DATA packet")
            
            # Parse packet header
            packet_type = struct.unpack('B', raw_data[0:1])[0]
            if packet_type != 0x10:
                return self._generate_error_response("Not a SENSOR_DATA packet")
            
            sequence = struct.unpack('I', raw_data[1:5])[0]
            timestamp = struct.unpack('I', raw_data[5:9])[0]
            
            # Parse acceleration data for 5 sensors
            accel_x_values = struct.unpack('5h', raw_data[9:19])
            accel_y_values = struct.unpack('5h', raw_data[19:29])
            accel_z_values = struct.unpack('5h', raw_data[29:39])
            
            # Parse gyroscope data for 5 sensors
            gyro_x_values = struct.unpack('5h', raw_data[39:49])
            gyro_y_values = struct.unpack('5h', raw_data[49:59])
            gyro_z_values = struct.unpack('5h', raw_data[59:69])
            
            sensor_readings = []
            for i in range(5):
                sensor_readings.append({
                    "sensor_id": i,
                    "acceleration": {
                        "x": accel_x_values[i] / 1000.0,  # 转换为浮点数
                        "y": accel_y_values[i] / 1000.0,
                        "z": accel_z_values[i] / 1000.0
                    },
                    "gyroscope": {
                        "x": gyro_x_values[i] / 100.0,
                        "y": gyro_y_values[i] / 100.0,
                        "z": gyro_z_values[i] / 100.0
                    }
                })
            
            # Calculate overall robot state
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
                    "battery_level": random.randint(70, 100),
                    "sensor_count": len(sensor_readings)
                },
                "sensor_data": sensor_readings,
                "processing_time_ms": int((time.time() * 1000) - timestamp),
                "processed_at": datetime.now().isoformat(),
                "status": "success"
            }
            
            self.session_counter += 1
            return response
            
        except struct.error as e:
            return self._generate_error_response(f"Struct unpack error: {str(e)}")
        except Exception as e:
            return self._generate_error_response(f"Binary processing error: {str(e)}")
    
    def process_text_sensor_data(self, text_data, timestamp):
        """Process text format IMU data"""
        try:
            imu_readings = []
            lines = text_data.strip().split(';')
            
            for line in lines:
                if not line or ':' not in line:
                    continue
                    
                parts = line.split(':', 1)
                if len(parts) < 2:
                    continue
                    
                label, values = parts[0], parts[1]
                nums = []
                
                # 解析数值
                for val in values.split(','):
                    try:
                        nums.append(float(val.strip()))
                    except:
                        continue
                
                if len(nums) >= 6:
                    # 提取传感器ID
                    sensor_id = label
                    if label.startswith("IMU"):
                        try:
                            sensor_id = int(label[3:])
                        except:
                            sensor_id = label
                    
                    imu_readings.append({
                        "sensor_id": sensor_id,
                        "acceleration": {
                            "x": nums[0],
                            "y": nums[1], 
                            "z": nums[2]
                        },
                        "gyroscope": {
                            "x": nums[3],
                            "y": nums[4],
                            "z": nums[5]
                        }
                    })
            
            if not imu_readings:
                return self._generate_error_response("No valid IMU data found in text")
            
            # 计算机器人状态
            emotion = self._calculate_emotion(imu_readings)
            activity = self._determine_activity(imu_readings)
            
            response = {
                "session_id": self.session_counter,
                "sequence": int(time.time() * 1000),
                "timestamp": timestamp,
                "robot_state": {
                    "emotion": emotion,
                    "activity": activity,
                    "battery_level": random.randint(70, 100),
                    "sensor_count": len(imu_readings)
                },
                "sensor_data": imu_readings,
                "processing_time_ms": int((time.time() * 1000) - timestamp),
                "processed_at": datetime.now().isoformat(),
                "status": "success"
            }
            
            self.session_counter += 1
            return response
            
        except Exception as e:
            return self._generate_error_response(f"Text processing error: {str(e)}")
    
    def process_preprocessed_data(self, message):
        """Process preprocessed IMU data"""
        try:
            imu_readings = message["imu_readings"]
            timestamp = message.get("timestamp", int(time.time() * 1000))
            
            if not imu_readings:
                return self._generate_error_response("Empty preprocessed data")
            
            # 计算机器人状态
            emotion = self._calculate_emotion(imu_readings)
            activity = self._determine_activity(imu_readings)
            
            response = {
                "session_id": self.session_counter,
                "sequence": int(time.time() * 1000),
                "timestamp": timestamp,
                "robot_state": {
                    "emotion": emotion,
                    "activity": activity,
                    "battery_level": random.randint(70, 100),
                    "sensor_count": len(imu_readings)
                },
                "sensor_data": imu_readings,
                "processing_time_ms": 0,
                "processed_at": datetime.now().isoformat(),
                "status": "success"
            }
            
            self.session_counter += 1
            return response
            
        except Exception as e:
            return self._generate_error_response(f"Preprocessed data error: {str(e)}")
    
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
        
    def _calculate_emotion(self, sensor_readings):
        """Calculate emotion based on sensor data patterns"""
        try:
            total_acc = 0
            count = 0
            for reading in sensor_readings:
                acc = reading["acceleration"]
                total_acc += (acc["x"]**2 + acc["y"]**2 + acc["z"]**2)**0.5
                count += 1
            
            if count == 0:
                return "unknown"
                
            avg_acc = total_acc / count
            
            if avg_acc < 0.5:
                return "calm"
            elif avg_acc < 1.5:
                return "curious"
            elif avg_acc < 3.0:
                return "excited"
            else:
                return "agitated"
        except:
            return "error"
    
    def _determine_activity(self, sensor_readings):
        """Determine activity based on sensor data patterns"""
        try:
            gyro_variance = 0
            gyro_means = {"x": 0, "y": 0, "z": 0}
            count = len(sensor_readings)
            
            if count == 0:
                return "unknown"
            
            # Calculate mean values
            for reading in sensor_readings:
                gyro = reading["gyroscope"]
                gyro_means["x"] += gyro["x"]
                gyro_means["y"] += gyro["y"]
                gyro_means["z"] += gyro["z"]
            
            gyro_means["x"] /= count
            gyro_means["y"] /= count
            gyro_means["z"] /= count
            
            # Calculate variance
            for reading in sensor_readings:
                gyro = reading["gyroscope"]
                gyro_variance += (gyro["x"] - gyro_means["x"])**2
                gyro_variance += (gyro["y"] - gyro_means["y"])**2
                gyro_variance += (gyro["z"] - gyro_means["z"])**2
            
            gyro_variance /= count * 3
            
            # Determine activity based on variance
            if gyro_variance < 0.1:
                return "sleeping"
            elif gyro_variance < 1.0:
                return "resting"
            elif gyro_variance < 5.0:
                return "exploring"
            elif gyro_variance < 10.0:
                return "playing"
            else:
                return "agitated"
        except:
            return "error"
    
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
        """MQTT disconnection callback"""
        print(f"Client disconnected: {rc}")
    
    def start_mqtt_server(self):
        """Start the MQTT server on Ultra96"""
        try:
            # Ultra96 listens on port 8889
            self.client.connect("localhost", 8889, 60)
            self.client.loop_start()
            print("MQTT server started successfully on port 8889")
            return True
        except Exception as e:
            print(f"Failed to start MQTT server: {e}")
            return False
    
    def stop_mqtt_server(self):
        """Stop the MQTT server"""
        self.client.loop_stop()
        self.client.disconnect()
        print("MQTT server stopped")

if __name__ == "__main__":
    print("=" * 60)
    print("Ultra96 MQTT Processor with CSV Logging")
    print("=" * 60)
    print("Listening on port: 8889")
    print("Waiting for sensor data from laptop via SSH tunnel...")
    print(f"CSV file: imu_data.csv (30 columns: 5 IMUs × 6 values each)")
    print("=" * 60)
    
    processor = Ultra96ProcessorMQTT()
    
    if processor.start_mqtt_server():
        try:
            # Keep the server running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutdown requested by user...")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            processor.stop_mqtt_server()
    else:
        print("Failed to start Ultra96 processor")
        exit(1)