import socket
import os
import time
import struct
import json
import paho.mqtt.client as mqtt
import random

class FireBeetleMQTT:
    def __init__(self, broker_host="localhost", broker_port=1883, topic="sensors/imu"):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        # 使用更新的Callback API版本
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.sequence = 0
        
        # Setup MQTT callbacks
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Connected to MQTT broker successfully")
        else:
            print(f"Failed to connect to MQTT broker with code {reason_code}")
    
    def on_publish(self, client, userdata, mid, reason_code, properties):
        print(f"Message published with MID: {mid}")
    
    def calculate_crc16(self, data):
        """Calculate CRC16-CCITT checksum"""
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
    
    def process_imu_data(self, raw_udp_data):
        """处理原始UDP数据并转换为标准的71字节包"""
        try:
            # 解码用于解析IMU值（显示用）
            message = raw_udp_data.decode("utf-8", errors="ignore")
            
            # 创建标准的71字节传感器数据包
            packet_type = 0x10  # SENSOR_DATA packet
            self.sequence += 1
            timestamp = int(time.time() * 1000)
            
            # 解析IMU数据（从你的原始代码）
            imu_data = message.strip().split(";")
            sensor_readings = []
            
            for i in range(min(5, len(imu_data))):  # 最多5个IMU
                if not imu_data[i] or ":" not in imu_data[i]:
                    # 如果没有数据，使用默认值
                    accel_x, accel_y, accel_z = 0, 0, 0
                    gyro_x, gyro_y, gyro_z = 0, 0, 0
                else:
                    label, values = imu_data[i].split(":", 1)
                    nums = values.split(",")
                    # 确保有6个值
                    while len(nums) < 6:
                        nums.append("0")
                    
                    # 转换为整数
                    try:
                        accel_x = int(nums[0]) if nums[0] != "---" else 0
                        accel_y = int(nums[1]) if nums[1] != "---" else 0
                        accel_z = int(nums[2]) if nums[2] != "---" else 0
                        gyro_x = int(nums[3]) if nums[3] != "---" else 0
                        gyro_y = int(nums[4]) if nums[4] != "---" else 0
                        gyro_z = int(nums[5]) if nums[5] != "---" else 0
                    except ValueError:
                        accel_x, accel_y, accel_z = 0, 0, 0
                        gyro_x, gyro_y, gyro_z = 0, 0, 0
            
            # 构建二进制包（保持71字节结构）
            packet = struct.pack('B', packet_type)
            packet += struct.pack('I', self.sequence)
            packet += struct.pack('I', timestamp)
            
            # 添加5个IMU的数据（每个IMU 12字节，共60字节）
            for i in range(5):
                if i < len(sensor_readings):
                    accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z = sensor_readings[i]
                else:
                    accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z = 0, 0, 0, 0, 0, 0
                
                packet += struct.pack('6h', accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)
            
            # 计算CRC
            crc = self.calculate_crc16(packet)
            packet += struct.pack('H', crc)
            
            return packet
            
        except Exception as e:
            print(f"Error processing IMU data: {e}")
            return None
    
    def start_publishing(self):
        """开始发布IMU数据"""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            print(f"Starting MQTT publisher at 20Hz")
            print(f"Publishing to topic: {self.topic}")
            
            # 设置UDP接收（保持你的原始UDP代码）
            UDP_IP = "0.0.0.0"
            UDP_PORT = 4210
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((UDP_IP, UDP_PORT))
            
            imu_values = {}
            
            while True:
                data, addr = sock.recvfrom(4096)
                
                # 处理并发布数据
                sensor_packet = self.process_imu_data(data)
                if sensor_packet:
                    result = self.client.publish(self.topic, sensor_packet, qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        print(f"Published sequence {self.sequence} - {len(sensor_packet)} bytes")
                    else:
                        print(f"Publish failed for sequence {self.sequence}")
                
                # 显示逻辑（保持你的原始显示代码）
                try:
                    message = data.decode("utf-8", errors="ignore")
                    imu_data = message.strip().split(";")
                    for imu in imu_data:
                        if not imu or ":" not in imu:
                            continue
                        label, values = imu.split(":", 1)
                        nums = values.split(",")
                        while len(nums) < 6:
                            nums.append("---")
                        imu_values[label] = nums[:6]
                except Exception as e:
                    print(f"Error parsing IMU data: {e}")
                
                # 显示
                os.system("cls" if os.name == "nt" else "clear")
                print("📊 Real-Time IMU Data (Accel g / Gyro °/s)")
                print("IMU\tax\tay\taz\tgx\tgy\tgz")
                for i in range(5):
                    label = f"IMU{i}"
                    if label in imu_values:
                        print(label + "\t" + "\t".join(imu_values[label]))
                    else:
                        print(label + "\twaiting")
                
                time.sleep(0.05)
                
        except KeyboardInterrupt:
            print("\nStopping publisher...")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    # 连接到笔记本电脑的MQTT broker
    publisher = FireBeetleMQTT(broker_host="localhost", broker_port=1883)
    publisher.start_publishing()