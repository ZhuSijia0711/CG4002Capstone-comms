import socket
import os
import time
import struct
import json

# 配置 WSL 的 IP 地址和端口
WSL_IP = "172.17.183.135"  # 或者你的 WSL2 IP
WSL_PORT = 9999

# 创建 TCP 连接到 WSL
tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_sock.connect((WSL_IP, WSL_PORT))
print(f"Connected to WSL relay at {WSL_IP}:{WSL_PORT}")

UDP_IP = "0.0.0.0"
UDP_PORT = 4210

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

imu_values = {}

while True:
    data, addr = sock.recvfrom(4096)  # data 是原始二进制数据
    
    # 转发原始二进制数据到 WSL（保持二进制格式）
    try:
        # 发送数据长度前缀 + 原始二进制数据
        data_length = struct.pack('!I', len(data))
        tcp_sock.send(data_length + data)  # 不解码，直接发送二进制
        print(f"Forwarded {len(data)} bytes raw data to WSL relay")
    except Exception as e:
        print(f"Error forwarding to WSL: {e}")
        # 重连逻辑...

    # 原有的显示逻辑（解码用于显示）
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

    # 显示逻辑保持不变...
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