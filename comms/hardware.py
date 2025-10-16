import socket
import os
import time

UDP_IP = "0.0.0.0"
UDP_PORT = 4210

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

imu_values = {}

while True:
    data, addr = sock.recvfrom(4096)
    message = data.decode("utf-8", errors="ignore")

    # Parse IMU packets
    imu_data = message.strip().split(";")
    for imu in imu_data:
        if not imu or ":" not in imu:
            continue
        label, values = imu.split(":",1)
        nums = values.split(",")
        while len(nums) < 6:
            nums.append("---")
        imu_values[label] = nums[:6]

    # Clear terminal
    os.system("cls" if os.name=="nt" else "clear")
    print("📊 Real-Time IMU Data (Accel g / Gyro °/s)")
    print("IMU\tax\tay\taz\tgx\tgy\tgz")
    for i in range(5):
        label = f"IMU{i}"
        if label in imu_values:
            print(label+"\t"+"\t".join(imu_values[label]))
        else:
            print(label+"\twaiting")

    time.sleep(0.05)  # 20 Hz refresh
