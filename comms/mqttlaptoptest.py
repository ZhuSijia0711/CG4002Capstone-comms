import paho.mqtt.client as mqtt
import json
import struct

class WSLReceiver:
    def __init__(self, broker_host="localhost", broker_port=1884):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ Connected to MQTT broker")
            # 订阅二进制主题和JSON主题
            client.subscribe("sensors/imu")
            client.subscribe("sensors/imu/json")
        else:
            print(f"❌ Connection failed with code {rc}")
    
    def parse_binary_packet(self, data):
        """解析二进制数据包"""
        try:
            if len(data) != 71:
                print(f"⚠️  Invalid packet length: {len(data)} bytes")
                return None
            
            # 解析包结构
            packet_type = struct.unpack('B', data[0:1])[0]
            sequence = struct.unpack('I', data[1:5])[0]
            timestamp = struct.unpack('I', data[5:9])[0]
            
            print(f"📦 Packet: type={packet_type}, seq={sequence}, ts={timestamp}")
            
            # 解析IMU数据
            imu_data = []
            for i in range(5):
                offset = 9 + i * 12
                values = struct.unpack('6h', data[offset:offset+12])
                imu_data.append({
                    'accel_x': values[0],
                    'accel_y': values[1],
                    'accel_z': values[2],
                    'gyro_x': values[3],
                    'gyro_y': values[4],
                    'gyro_z': values[5]
                })
            
            # 解析CRC（最后2字节）
            crc_received = struct.unpack('H', data[69:71])[0]
            
            return {
                'type': packet_type,
                'sequence': sequence,
                'timestamp': timestamp,
                'imu_data': imu_data,
                'crc_received': crc_received
            }
            
        except Exception as e:
            print(f"❌ Error parsing binary packet: {e}")
            return None
    
    def on_message(self, client, userdata, msg):
        try:
            if msg.topic == "sensors/imu/json":
                # 处理JSON数据
                data = json.loads(msg.payload.decode())
                print(f"📊 JSON Data - Seq: {data['sequence']}")
                for sensor in data['sensors']:
                    print(f"   {sensor['sensor_id']}: "
                          f"a({sensor['accel_x']}, {sensor['accel_y']}, {sensor['accel_z']}) "
                          f"g({sensor['gyro_x']}, {sensor['gyro_y']}, {sensor['gyro_z']})")
            
            elif msg.topic == "sensors/imu":
                # 处理二进制数据
                result = self.parse_binary_packet(msg.payload)
                if result:
                    print(f"🔢 Binary Data - Seq: {result['sequence']}")
                    for i, imu in enumerate(result['imu_data']):
                        print(f"   IMU{i}: "
                              f"a({imu['accel_x']}, {imu['accel_y']}, {imu['accel_z']}) "
                              f"g({imu['gyro_x']}, {imu['gyro_y']}, {imu['gyro_z']})")
            
            print("-" * 50)
            
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    def start(self):
        print(f"🔗 Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
        self.client.connect(self.broker_host, self.broker_port, 60)
        print("🎧 Starting to listen for messages...")
        print("🔄 Press Ctrl+C to stop")
        self.client.loop_forever()

if __name__ == "__main__":
    receiver = WSLReceiver(broker_host="localhost", broker_port=1883)
    receiver.start()