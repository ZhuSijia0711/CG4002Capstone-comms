import socket
import os
import time
import struct
import json
import paho.mqtt.client as mqtt

# MQTT Configuration - Use localhost to connect to WSL
MQTT_BROKER = "localhost"  # Changed from WSL IP to localhost
MQTT_PORT = 1883
MQTT_TOPIC_SENSOR = "robot/sensor/raw"

# Create MQTT client
mqtt_client = mqtt.Client(client_id="firebeetle_sensor")
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")

UDP_IP = "0.0.0.0"
UDP_PORT = 4210

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

imu_values = {}

# 在FireBeetle发送端修改数据解析部分
def publish_sensor_data(raw_data):
    """Publish raw sensor data to MQTT broker"""
    try:
        # 尝试解析文本格式的IMU数据
        imu_readings = []
        try:
            message = raw_data.decode("utf-8", errors="ignore").strip()
            imu_data = message.split(";")
            
            for imu in imu_data:
                if not imu or ":" not in imu:
                    continue
                
                label, values = imu.split(":", 1)
                nums = [float(x.strip()) for x in values.split(",") if x.strip()]
                
                if len(nums) >= 6:
                    imu_readings.append({
                        "sensor_id": label,
                        "acceleration": {
                            "x": nums[0] * 1000,  # 转换为整数格式
                            "y": nums[1] * 1000,
                            "z": nums[2] * 1000
                        },
                        "gyroscope": {
                            "x": nums[3] * 100,
                            "y": nums[4] * 100,
                            "z": nums[5] * 100
                        }
                    })
        except Exception as e:
            print(f"Error parsing text data: {e}")
            imu_readings = []

        message = {
            "data": raw_data.hex(),
            "text_data": message if 'message' in locals() else "",
            "imu_readings": imu_readings,
            "length": len(raw_data),
            "timestamp": int(time.time() * 1000),
            "source": "firebeetle"
        }
        
        mqtt_client.publish(
            MQTT_TOPIC_SENSOR,
            json.dumps(message),
            qos=1
        )
        
        print(f"Published {len(raw_data)} bytes to MQTT")
        return True
        
    except Exception as e:
        print(f"Error publishing to MQTT: {e}")
        return False
    
while True:
    data, addr = sock.recvfrom(4096)
    
    # Publish to MQTT
    publish_sensor_data(data)
    
    # Existing display logic
    try:
        message = data.decode("utf-8", errors="ignore")
        imu_data = message.strip().split(";")
        for imu in imu_data:
            if not imu or ":" not in imu:
                continue
            label, values = imu.split(":",1)
            nums = values.split(",")
            while len(nums) < 6:
                nums.append("---")
            imu_values[label] = nums[:6]
    except Exception as e:
        print(f"Error parsing IMU data: {e}")

    os.system("cls" if os.name=="nt" else "clear")
    print("📊 Real-Time IMU Data (Accel g / Gyro °/s)")
    print("IMU\tax\tay\taz\tgx\tgy\tgz")
    for i in range(5):
        label = f"IMU{i}"
        if label in imu_values:
            print(label+"\t"+"\t".join(imu_values[label]))
        else:
            print(label+"\twaiting")

    time.sleep(0.05)